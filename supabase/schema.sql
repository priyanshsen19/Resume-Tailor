-- Resume Tailor: per-user resume metadata + private storage bucket.
-- Run once in the Supabase SQL editor (Dashboard -> SQL -> New query).
--
-- Also enable anonymous sign-ins:
--   Dashboard -> Authentication -> Sign In / Providers -> "Allow anonymous sign-ins" = ON
--
-- The backend talks to Supabase with the service-role key (bypasses RLS) and
-- checks ownership itself; browsers never touch this table directly, so RLS is
-- enabled with no policies (= deny everything for anon/authenticated keys).

create table if not exists public.resumes (
  id          uuid primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  company     text not null,
  role        text not null,
  folder      text not null,
  tex_path    text not null,          -- storage object path: {user_id}/{id}/file.tex
  pdf_path    text,                   -- storage object path: {user_id}/{id}/file.pdf
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  expires_at  timestamptz not null    -- created_at + RESUME_TTL_HOURS (24h by default)
);

create index if not exists resumes_user_updated_idx on public.resumes (user_id, updated_at desc);
create index if not exists resumes_expires_idx      on public.resumes (expires_at);

alter table public.resumes enable row level security;

-- Private bucket for the .tex/.pdf files (served via short-lived signed URLs).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 10485760, array['application/pdf', 'text/x-tex', 'text/plain'])
on conflict (id) do nothing;

-- Per-user base resume template (the LaTeX the tailor starts from).
-- No expiry: unlike generated resumes, a template is kept until replaced.
create table if not exists public.templates (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  tex         text not null,
  updated_at  timestamptz not null default now()
);

alter table public.templates enable row level security;
