-- Basic Memory Layer canonical schema. Supabase is the production source of truth.
create table if not exists memories (
    memory_id text primary key,
    owner_id text not null,
    domain text not null check (domain in ('boss_personal', 'vennela_core', 'session')),
    category text not null check (category in ('Profile', 'Preference', 'Interest', 'Goal', 'Project', 'Skill', 'Fact', 'Task', 'Event', 'Relationship')),
    content jsonb not null,
    session_id text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    active boolean not null default true,
    check ((domain = 'session' and session_id is not null) or (domain <> 'session' and session_id is null))
);
create index if not exists memories_owner_domain_idx on memories (owner_id, domain, updated_at desc);
create index if not exists memories_session_idx on memories (owner_id, session_id, updated_at desc);
