-- Intelligent Memory Layer (Level 5) schema optimizations.
-- Supabase is the production source of truth.

-- Optimize JSONB search within memory content for consolidation and conflict metadata
create index if not exists memories_content_gin_idx
    on memories using gin (content);
