-- JARVIS Memory Layer (Level 6) schema optimizations.
-- Supabase is the production source of truth.

-- Compound index to accelerate active user model projection and category queries
create index if not exists memories_owner_active_category_idx
    on memories (owner_id, active, category, updated_at desc);
