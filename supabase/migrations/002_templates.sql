-- Adds the per-user base resume template.
-- Run this in the Supabase SQL editor if you created your project before
-- this feature existed (schema.sql already contains it for new projects).

create table if not exists public.templates (
  user_id     uuid primary key references auth.users (id) on delete cascade,
  tex         text not null,
  updated_at  timestamptz not null default now()
);

alter table public.templates enable row level security;
