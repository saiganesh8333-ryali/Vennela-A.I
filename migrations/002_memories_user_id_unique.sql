-- Enforce one aggregate memory row per user.
-- This intentionally fails if duplicate user_id rows already exist.

alter table public.memories
    add constraint memories_user_id_key unique (user_id);
