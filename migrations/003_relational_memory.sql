-- Relational Memory Layer (Level 4) canonical schema.
-- Supabase is the production source of truth.
create table if not exists memory_relationships (
    relationship_id text primary key,
    source_memory_id text not null references memories(memory_id) on delete cascade,
    target_memory_id text not null references memories(memory_id) on delete cascade,
    relationship_type text not null check (relationship_type in (
        'PROJECT_GOAL',
        'PROJECT_PREFERENCE',
        'PROJECT_EVENT',
        'GOAL_PREFERENCE',
        'EVENT_PROJECT',
        'RELATED_TO'
    )),
    strength float not null default 1.0 check (strength >= 0.0 and strength <= 1.0),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    active boolean not null default true,
    check (source_memory_id <> target_memory_id)
);

create unique index if not exists memory_relationships_active_unique_idx
    on memory_relationships (source_memory_id, target_memory_id, relationship_type)
    where active = true;

create index if not exists memory_relationships_source_idx
    on memory_relationships (source_memory_id, relationship_type, updated_at desc)
    where active = true;

create index if not exists memory_relationships_target_idx
    on memory_relationships (target_memory_id, relationship_type, updated_at desc)
    where active = true;
