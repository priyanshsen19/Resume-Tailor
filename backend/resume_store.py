"""
Per-user resume persistence on Supabase (Postgres table + private Storage bucket).

Why: the API's disk is ephemeral on free hosts, so "recent resumes" must live
elsewhere.  Each browser signs in anonymously with Supabase Auth; the frontend
sends that session's JWT and the backend (service role) verifies it, then reads
and writes only that user's rows/objects.  Files are served through short-lived
signed URLs.  Everything expires after RESUME_TTL_HOURS (default 24) and a
background task purges expired rows *and* their storage objects.

Layout in the bucket:   {user_id}/{resume_id}/{filename}

Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY to enable; when they are absent the
API falls back to the local ./resumes folder (single-user dev mode).
"""

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

SIGNED_URL_TTL_SECONDS = 60 * 60          # links in API responses live 1h
TOKEN_CACHE_TTL_SECONDS = 5 * 60          # verified JWT -> user_id cache


class AuthError(Exception):
    pass


@dataclass
class ResumeRecord:
    id: str
    user_id: str
    company: str
    role: str
    folder: str
    tex_path: str
    pdf_path: Optional[str]
    created_at: str
    updated_at: str
    expires_at: str

    @classmethod
    def from_row(cls, row: dict) -> "ResumeRecord":
        return cls(**{k: row.get(k) for k in cls.__dataclass_fields__})


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeStore:
    def __init__(self, url: Optional[str], service_key: Optional[str], bucket: str, ttl_hours: int):
        self.enabled = bool(url and service_key)
        self.bucket = bucket
        self.ttl = timedelta(hours=ttl_hours)
        self._token_cache: Dict[str, tuple] = {}
        self.client = None
        if self.enabled:
            from supabase import create_client
            self.client = create_client(url, service_key)
            print(f"[STORE] Supabase enabled (bucket={bucket}, ttl={ttl_hours}h)")
        else:
            print("[STORE] Supabase not configured; using local ./resumes folder")

    # ------------------------------------------------------------------ auth
    def verify_user(self, access_token: str) -> str:
        """Return the Supabase user id for a session JWT (cached briefly)."""
        cached = self._token_cache.get(access_token)
        if cached and cached[1] > time.time():
            return cached[0]
        try:
            resp = self.client.auth.get_user(access_token)
        except Exception as e:
            raise AuthError(f"Invalid session: {e}")
        if not resp or not resp.user:
            raise AuthError("Invalid session")
        if len(self._token_cache) > 500:
            self._token_cache.clear()
        self._token_cache[access_token] = (resp.user.id, time.time() + TOKEN_CACHE_TTL_SECONDS)
        return resp.user.id

    # ------------------------------------------------------------------ storage helpers
    def _storage(self):
        return self.client.storage.from_(self.bucket)

    def _upload(self, path: str, data: bytes, content_type: str) -> None:
        self._storage().upload(path, data, {"content-type": content_type, "upsert": "true"})

    def _signed(self, path: Optional[str], download_name: Optional[str] = None) -> Optional[str]:
        if not path:
            return None
        options = {"download": download_name} if download_name else None
        resp = self._storage().create_signed_url(path, SIGNED_URL_TTL_SECONDS, options)
        return resp.get("signedURL") or resp.get("signedUrl")

    def urls_for(self, rec: ResumeRecord) -> dict:
        pdf_name = Path(rec.pdf_path).name if rec.pdf_path else None
        return {
            "pdf_url": self._signed(rec.pdf_path),
            "pdf_download_url": self._signed(rec.pdf_path, pdf_name),
            "tex_url": self._signed(rec.tex_path, Path(rec.tex_path).name),
        }

    # ------------------------------------------------------------------ CRUD
    def save(self, user_id: str, company: str, role: str, folder: str,
             tex_file: Path, pdf_file: Path, resume_id: Optional[str] = None) -> ResumeRecord:
        """Upload tex+pdf and insert (or refresh) the row. Returns the record."""
        is_new = resume_id is None
        resume_id = resume_id or str(uuid.uuid4())
        base = f"{user_id}/{resume_id}"
        tex_path = f"{base}/{tex_file.name}"
        pdf_path = f"{base}/{pdf_file.name}"

        self._upload(tex_path, tex_file.read_bytes(), "text/x-tex")
        self._upload(pdf_path, pdf_file.read_bytes(), "application/pdf")

        now = _now()
        if is_new:
            row = {
                "id": resume_id, "user_id": user_id, "company": company, "role": role,
                "folder": folder, "tex_path": tex_path, "pdf_path": pdf_path,
                "created_at": now.isoformat(), "updated_at": now.isoformat(),
                "expires_at": (now + self.ttl).isoformat(),
            }
            data = self.client.table("resumes").insert(row).execute().data
        else:
            data = (
                self.client.table("resumes")
                .update({"tex_path": tex_path, "pdf_path": pdf_path, "updated_at": now.isoformat()})
                .eq("id", resume_id).eq("user_id", user_id).execute().data
            )
        if not data:
            raise RuntimeError("Supabase did not return the saved resume row")
        return ResumeRecord.from_row(data[0])

    def list(self, user_id: str) -> List[ResumeRecord]:
        data = (
            self.client.table("resumes").select("*")
            .eq("user_id", user_id)
            .gt("expires_at", _now().isoformat())
            .order("updated_at", desc=True)
            .execute().data
        )
        return [ResumeRecord.from_row(r) for r in data]

    def get(self, user_id: str, resume_id: str) -> Optional[ResumeRecord]:
        data = (
            self.client.table("resumes").select("*")
            .eq("id", resume_id).eq("user_id", user_id)
            .gt("expires_at", _now().isoformat())
            .limit(1).execute().data
        )
        return ResumeRecord.from_row(data[0]) if data else None

    def download_tex(self, rec: ResumeRecord) -> str:
        return self._storage().download(rec.tex_path).decode("utf-8", errors="replace")

    def delete(self, user_id: str, resume_id: str) -> bool:
        rec = self.get(user_id, resume_id)
        if not rec:
            return False
        self._remove_objects([rec])
        self.client.table("resumes").delete().eq("id", resume_id).eq("user_id", user_id).execute()
        return True

    # ------------------------------------------------------------------ expiry
    def purge_expired(self) -> int:
        """Delete rows past expires_at and their storage objects. Returns count."""
        data = (
            self.client.table("resumes").select("*")
            .lt("expires_at", _now().isoformat())
            .limit(500).execute().data
        )
        if not data:
            return 0
        recs = [ResumeRecord.from_row(r) for r in data]
        self._remove_objects(recs)
        ids = [r.id for r in recs]
        self.client.table("resumes").delete().in_("id", ids).execute()
        print(f"[STORE] Purged {len(ids)} expired resume(s)")
        return len(ids)

    def _remove_objects(self, recs: List[ResumeRecord]) -> None:
        paths = [p for r in recs for p in (r.tex_path, r.pdf_path) if p]
        if paths:
            try:
                self._storage().remove(paths)
            except Exception as e:
                print(f"[STORE] Could not remove storage objects: {e}")


def store_from_env() -> ResumeStore:
    return ResumeStore(
        url=os.getenv("SUPABASE_URL"),
        service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        bucket=os.getenv("SUPABASE_BUCKET", "resumes"),
        ttl_hours=int(os.getenv("RESUME_TTL_HOURS", "24")),
    )
