-- Additive security hardening migration for Basic Memory Layer (P0-01).
-- Preserves existing schema, indexes, and all existing user memory records.
--
-- Pre-flight inspection queries (run in staging/production SQL editor before apply):
--   SELECT relname, relrowsecurity, relforcerowsecurity
--   FROM pg_class WHERE oid = 'public.memories'::regclass;
--   SELECT grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_schema = 'public' AND table_name = 'memories';
--   SELECT policyname, roles, cmd, qual, with_check
--   FROM pg_policies WHERE schemaname = 'public' AND tablename = 'memories';

-- 1. Enable PostgreSQL Row Level Security on public.memories.
--    With no permissive RLS policies for anon/authenticated, direct PostgREST
--    client access is denied by default while service_role bypasses RLS.
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

-- 2. Revoke direct table privileges from public PostgREST API roles.
REVOKE ALL ON TABLE public.memories FROM PUBLIC;
REVOKE ALL ON TABLE public.memories FROM anon, authenticated;

-- 3. Explicitly preserve required backend service_role privileges.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memories TO service_role;

-- Documented Rollback Procedure (execute ONLY if explicitly authorized; never drop/truncate data):
--   REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE public.memories FROM service_role;
--   GRANT ALL ON TABLE public.memories TO anon, authenticated; -- restore prior role grants if recorded
--   ALTER TABLE public.memories DISABLE ROW LEVEL SECURITY;
