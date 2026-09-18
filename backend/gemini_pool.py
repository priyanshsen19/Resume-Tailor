"""
Gemini API key pool.

Rotates across several free-tier keys so the app gets N x (per-key daily
quota) requests per day.  Each call picks the least-used healthy key, binds a
per-key gRPC client to the model (no global `genai.configure` races between
threads), and reacts to errors:

    429 ...PerDay...      -> key is exhausted until the quota reset (midnight PT)
    429 ...PerMinute...   -> key cools down for 60s, another key is tried now
    401 / 403 / bad key   -> key is disabled until restart
    anything else         -> counted against the key and re-raised

Per-day usage is persisted to a small JSON file so restarts (uvicorn --reload)
don't forget how many calls each key has already made today.

Configuration (env):
    GEMINI_API_KEYS              comma/newline/semicolon separated keys
    GEMINI_API_KEY               single key (still supported; merged into the pool)
    GEMINI_DAILY_LIMIT_PER_KEY   soft cap per key per day (default 20)
    GEMINI_USAGE_FILE            where to persist usage (default backend/key_usage.json)
"""

import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import google.ai.generativelanguage as glm
import google.generativeai as genai
from google.api_core import exceptions as gexc

# Google resets free-tier daily quotas at midnight Pacific time.
QUOTA_TZ = ZoneInfo("America/Los_Angeles")
PER_MINUTE_COOLDOWN_SECONDS = 60
# gRPC deadline per request. The SDK default (60s) is too short for a full
# resume from a long JD -> "504 Deadline expired before operation could complete".
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "240"))
DEADLINE_RETRIES = 1


class _TimeoutClient:
    """Proxy around GenerativeServiceClient that applies our deadline to every call."""

    def __init__(self, inner):
        self._inner = inner

    def generate_content(self, request, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT_SECONDS)
        return self._inner.generate_content(request, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class AllKeysExhausted(Exception):
    pass


def _parse_keys(*raw_values: Optional[str]) -> List[str]:
    keys: List[str] = []
    for raw in raw_values:
        for k in re.split(r"[,\n;]+", raw or ""):
            k = k.strip().strip('"').strip("'")
            if k and not k.startswith("your_") and k not in keys:
                keys.append(k)
    return keys


class _KeyState:
    def __init__(self, index: int, key: str):
        self.index = index
        self.key = key
        self.label = f"key{index + 1}(...{key[-4:]})"
        self.used_today = 0
        self.exhausted_on: Optional[str] = None   # quota-day string when hit PerDay limit
        self.cooldown_until: float = 0.0
        self.disabled_reason: Optional[str] = None
        self.client: Optional[glm.GenerativeServiceClient] = None


class GeminiKeyPool:
    def __init__(self, keys: List[str], daily_limit_per_key: int, usage_file: Path):
        if not keys:
            raise ValueError("No Gemini API keys configured (set GEMINI_API_KEYS or GEMINI_API_KEY in .env)")
        self._keys = [_KeyState(i, k) for i, k in enumerate(keys)]
        self._by_label = {s.label: s for s in self._keys}
        self._limit = daily_limit_per_key
        self._usage_file = usage_file
        self._lock = threading.Lock()
        self._day = self._quota_day()
        self._load()

    # ------------------------------------------------------------------ persistence
    @staticmethod
    def _quota_day() -> str:
        return datetime.now(QUOTA_TZ).strftime("%Y-%m-%d")

    def _load(self) -> None:
        try:
            data = json.loads(self._usage_file.read_text())
        except Exception:
            return
        if data.get("day") != self._day:
            return  # stale: new quota day, start from zero
        for label, entry in data.get("keys", {}).items():
            state = self._by_label.get(label)
            if state:
                state.used_today = int(entry.get("used", 0))
                state.exhausted_on = entry.get("exhausted_on")

    def _save(self) -> None:
        data = {
            "day": self._day,
            "keys": {
                s.label: {"used": s.used_today, "exhausted_on": s.exhausted_on}
                for s in self._keys
            },
        }
        try:
            tmp = self._usage_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self._usage_file)
        except Exception as e:
            print(f"[KEYPOOL] Could not persist usage: {e}")

    def _roll_day_if_needed(self) -> None:
        today = self._quota_day()
        if today != self._day:
            print(f"[KEYPOOL] New quota day {today}: resetting counters")
            self._day = today
            for s in self._keys:
                s.used_today = 0
                s.exhausted_on = None
                s.cooldown_until = 0.0
            self._save()

    # ------------------------------------------------------------------ selection
    def _available(self, state: _KeyState, now: float) -> bool:
        return (
            state.disabled_reason is None
            and state.exhausted_on != self._day
            and state.cooldown_until <= now
            and state.used_today < self._limit
        )

    def _pick(self, exclude: set) -> Optional[_KeyState]:
        now = time.time()
        candidates = [s for s in self._keys if s.label not in exclude and self._available(s, now)]
        if not candidates:
            return None
        return min(candidates, key=lambda s: (s.used_today, s.index))

    def _soonest_cooldown(self) -> Optional[float]:
        now = time.time()
        waits = [
            s.cooldown_until - now
            for s in self._keys
            if s.disabled_reason is None and s.exhausted_on != self._day
            and s.used_today < self._limit and s.cooldown_until > now
        ]
        return min(waits) if waits else None

    def _client_for(self, state: _KeyState) -> glm.GenerativeServiceClient:
        if state.client is None:
            state.client = _TimeoutClient(glm.GenerativeServiceClient(client_options={"api_key": state.key}))
        return state.client

    # ------------------------------------------------------------------ public API
    def generate(self, model_name: str, contents, generation_config=None):
        """Call `GenerativeModel.generate_content` with automatic key rotation."""
        tried: set = set()
        cooldown_waits = 0
        deadline_retries = 0
        while True:
            with self._lock:
                self._roll_day_if_needed()
                state = self._pick(tried)
                if state is None:
                    wait = self._soonest_cooldown()
                    if wait is None or cooldown_waits >= 3:
                        raise AllKeysExhausted(self._exhausted_message())
                else:
                    client = self._client_for(state)

            if state is None:
                # Every healthy key is in a per-minute cooldown; wait for the first one.
                cooldown_waits += 1
                time.sleep(min(max(wait, 1.0), PER_MINUTE_COOLDOWN_SECONDS))
                tried.clear()
                continue

            model = genai.GenerativeModel(model_name)
            model._client = client
            try:
                response = model.generate_content(contents, generation_config=generation_config)
            except gexc.ResourceExhausted as e:
                self._on_quota_error(state, str(e))
                tried.add(state.label)
                continue
            except gexc.DeadlineExceeded:
                # Gemini took too long (504). The call may still have counted; retry once.
                self._record(state)
                if deadline_retries < DEADLINE_RETRIES:
                    deadline_retries += 1
                    print(f"[KEYPOOL] {state.label} deadline exceeded after {REQUEST_TIMEOUT_SECONDS}s; retrying")
                    continue
                raise
            except (gexc.PermissionDenied, gexc.Unauthenticated) as e:
                self._disable(state, f"rejected: {e.__class__.__name__}")
                tried.add(state.label)
                continue
            except gexc.InvalidArgument as e:
                if "api key" in str(e).lower():
                    self._disable(state, "invalid API key")
                    tried.add(state.label)
                    continue
                self._record(state)
                raise
            except Exception:
                self._record(state)
                raise

            self._record(state)
            return response

    def status(self) -> Dict:
        with self._lock:
            self._roll_day_if_needed()
            now = time.time()
            keys = []
            for s in self._keys:
                if s.disabled_reason:
                    st = f"disabled ({s.disabled_reason})"
                elif s.exhausted_on == self._day:
                    st = "quota exhausted (resets midnight PT)"
                elif s.cooldown_until > now:
                    st = f"cooling down {int(s.cooldown_until - now)}s"
                elif s.used_today >= self._limit:
                    st = "daily limit reached"
                else:
                    st = "available"
                keys.append({
                    "key": s.label,
                    "used_today": s.used_today,
                    "daily_limit": self._limit,
                    "status": st,
                })
            remaining = sum(
                max(self._limit - s.used_today, 0)
                for s in self._keys if self._available(s, now)
            )
            return {
                "quota_day": self._day,
                "keys": keys,
                "total_keys": len(self._keys),
                "requests_remaining_today": remaining,
            }

    # ------------------------------------------------------------------ bookkeeping
    def _record(self, state: _KeyState) -> None:
        with self._lock:
            state.used_today += 1
            self._save()

    def _on_quota_error(self, state: _KeyState, message: str) -> None:
        with self._lock:
            lowered = message.lower()
            if "perminute" in lowered or "per minute" in lowered:
                state.cooldown_until = time.time() + PER_MINUTE_COOLDOWN_SECONDS
                print(f"[KEYPOOL] {state.label} hit per-minute limit; cooling down {PER_MINUTE_COOLDOWN_SECONDS}s")
            else:
                state.exhausted_on = self._day
                state.used_today = max(state.used_today, self._limit)
                print(f"[KEYPOOL] {state.label} hit daily quota; disabled until reset")
            self._save()

    def _disable(self, state: _KeyState, reason: str) -> None:
        with self._lock:
            state.disabled_reason = reason
            print(f"[KEYPOOL] {state.label} disabled: {reason}")

    def _exhausted_message(self) -> str:
        reset = datetime.now(QUOTA_TZ).strftime("%H:%M %Z")
        return (
            f"All {len(self._keys)} Gemini API key(s) are out of quota for today "
            f"(it is {reset} now; free-tier quotas reset at midnight Pacific). "
            f"Add more keys to GEMINI_API_KEYS in backend/.env."
        )


def pool_from_env() -> GeminiKeyPool:
    keys = _parse_keys(os.getenv("GEMINI_API_KEYS"), os.getenv("GEMINI_API_KEY"))
    limit = int(os.getenv("GEMINI_DAILY_LIMIT_PER_KEY", "20"))
    usage_file = Path(os.getenv("GEMINI_USAGE_FILE", Path(__file__).parent / "key_usage.json"))
    pool = GeminiKeyPool(keys, limit, usage_file)
    print(f"[KEYPOOL] {len(keys)} key(s) loaded, {limit} requests/day each "
          f"=> up to {len(keys) * limit} requests/day")
    return pool
