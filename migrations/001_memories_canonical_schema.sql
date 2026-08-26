-- Safe, read-only-safe migration planning file for the current empty public.memories table.
-- This file is not executed automatically. It creates the canonical Vennela memory schema
-- for a fresh Supabase/PostgreSQL database while preserving the existing empty table.

create extension if not exists pgcrypto;

create table if not exists public.memories (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    profile jsonb not null default '{}'::jsonb,
    short_term jsonb not null default '[]'::jsonb,
    long_term jsonb not null default '[]'::jsonb,
    episodic jsonb not null default '[]'::jsonb,
    emotions jsonb not null default '{}'::jsonb,
    sentiments jsonb not null default '{}'::jsonb,
    importance jsonb not null default '[]'::jsonb,
    summary text not null default '',
    embeddings jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.memories
    add column if not exists profile jsonb not null default '{}'::jsonb,
    add column if not exists short_term jsonb not null default '[]'::jsonb,
    add column if not exists long_term jsonb not null default '[]'::jsonb,
    add column if not exists episodic jsonb not null default '[]'::jsonb,
    add column if not exists emotions jsonb not null default '{}'::jsonb,
    add column if not exists sentiments jsonb not null default '{}'::jsonb,
    add column if not exists importance jsonb not null default '[]'::jsonb,
    add column if not exists summary text not null default '',
    add column if not exists embeddings jsonb not null default '[]'::jsonb,
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now();

create index if not exists idx_memories_user_id on public.memories(user_id);
create index if not exists idx_memories_updated_at on public.memories(updated_at desc);

-- Canonical long_term payload shape for the Vennela memory system:
-- [
--   {
--     "text": "memory text",
--     "timestamp": "2026-08-26T19:00:00Z",
--     "importance": 0.85
--   }
-- ]
--
-- This design matches the current application memory model, avoids row-per-memory complexity,
-- and is reliable for a single-user memory snapshot stored as JSONB.
