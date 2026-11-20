-- Tasks and Reminders subsystem schema. Supabase is the production source of truth.

create table if not exists tasks (
    task_id text primary key,
    owner_id text not null,
    title text not null,
    description text not null default '',
    status text not null check (status in ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    priority text not null check (priority in ('LOW', 'NORMAL', 'HIGH', 'URGENT')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    start_at timestamptz null,
    due_at timestamptz null,
    completed_at timestamptz null
);

create index if not exists tasks_owner_status_idx on tasks (owner_id, status, created_at desc);
create index if not exists tasks_owner_due_idx on tasks (owner_id, due_at);

create table if not exists reminders (
    reminder_id text primary key,
    owner_id text not null,
    title text not null,
    description text not null default '',
    remind_at timestamptz not null,
    timezone text not null default 'Asia/Kolkata',
    status text not null check (status in ('PENDING', 'TRIGGERED', 'CANCELLED')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    task_id text null references tasks(task_id) on delete set null
);

create index if not exists reminders_owner_status_idx on reminders (owner_id, status, remind_at asc);
create index if not exists reminders_pending_due_idx on reminders (status, remind_at asc);
