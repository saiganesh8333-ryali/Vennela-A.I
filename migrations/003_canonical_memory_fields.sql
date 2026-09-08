-- Canonical Memory Layer fields. Existing rows remain valid and active.
alter table memories
    add column if not exists source text not null default 'conversation',
    add column if not exists confidence double precision not null default 0.5,
    add column if not exists importance double precision not null default 0.0,
    add column if not exists status text not null default 'active',
    add column if not exists last_accessed_at timestamptz null,
    add column if not exists expires_at timestamptz null,
    add column if not exists embedding jsonb null,
    add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table memories
    drop constraint if exists memories_status_check;

alter table memories
    add constraint memories_status_check
    check (status in ('candidate', 'active', 'stale', 'archived', 'deleted'));

alter table memories
    drop constraint if exists memories_confidence_check;

alter table memories
    add constraint memories_confidence_check
    check (confidence >= 0 and confidence <= 1);

alter table memories
    drop constraint if exists memories_importance_check;

alter table memories
    add constraint memories_importance_check
    check (importance >= 0 and importance <= 1);

create index if not exists memories_owner_domain_status_idx
    on memories (owner_id, domain, status, updated_at desc);

create index if not exists memories_session_status_idx
    on memories (owner_id, session_id, status, updated_at desc);
