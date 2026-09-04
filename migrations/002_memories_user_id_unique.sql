-- Ensure one canonical memory snapshot per user for safe upserts.
create unique index if not exists memories_user_id_unique on memories (user_id);
