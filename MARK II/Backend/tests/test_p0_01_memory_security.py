"""Phase 3 (P0-01): Supabase Memory Security & Explicit Ownership Enforcement tests."""

from __future__ import annotations

import os
import pathlib
import sys
from types import SimpleNamespace

import pytest

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.memory_contracts import MemoryRetrievalRequest, TemporaryMarkIMemoryProvider
from memory.api import MemoryAPI
from memory.models import AuthContext, MemoryCategory, MemoryDomain, MemoryRecord
from memory.repository import InMemoryMemoryRepository, SupabaseMemoryRepository


class SimulatedPostgRESTError(RuntimeError):
    """Simulates PostgreSQL SQLSTATE 42501 when RLS/privileges deny access."""

    def __init__(self, message: str, sqlstate: str = "42501"):
        super().__init__(message)
        self.code = sqlstate


class _FakeTableQuery:
    """In-memory PostgREST query simulator evaluating filters, RLS, and role grants."""

    def __init__(self, store: list[dict], role: str, rls_enabled: bool, revoked_roles: set[str]):
        self._store = store
        self._role = role
        self._rls_enabled = rls_enabled
        self._revoked_roles = revoked_roles
        self._op: str | None = None
        self._payload: dict | list[dict] | None = None
        self._filters: list[tuple[str, object]] = []
        self._order_col: str | None = None
        self._order_desc: bool = False
        self._limit: int | None = None

    def select(self, columns: str = "*"):
        self._op = "select"
        return self

    def insert(self, payload: dict):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload: dict):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, column: str, value: object):
        self._filters.append((column, value))
        return self

    def order(self, column: str, *, desc: bool = False):
        self._order_col = column
        self._order_desc = desc
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def _matches(self, row: dict) -> bool:
        return all(row.get(col) == val for col, val in self._filters)

    def execute(self):
        # Enforce Postgres privilege + RLS model for public API roles
        if self._role in self._revoked_roles:
            return SimpleNamespace(
                data=None,
                error={
                    "code": "42501",
                    "message": f"permission denied for table memories (role={self._role})",
                },
            )
        if self._rls_enabled and self._role != "service_role":
            return SimpleNamespace(
                data=None,
                error={
                    "code": "42501",
                    "message": f"new row/query violates row-level security policy (role={self._role})",
                },
            )

        if self._op == "insert":
            assert isinstance(self._payload, dict)
            row = dict(self._payload)
            self._store.append(row)
            return SimpleNamespace(data=[dict(row)], error=None)

        if self._op == "select":
            matched = [dict(r) for r in self._store if self._matches(r)]
            if self._order_col:
                matched.sort(key=lambda r: r.get(self._order_col, ""), reverse=self._order_desc)
            if self._limit is not None:
                matched = matched[: self._limit]
            return SimpleNamespace(data=matched, error=None)

        if self._op == "update":
            assert isinstance(self._payload, dict)
            updated_rows: list[dict] = []
            for row in self._store:
                if self._matches(row):
                    row.update(self._payload)
                    updated_rows.append(dict(row))
            return SimpleNamespace(data=updated_rows, error=None)

        raise AssertionError(f"Unsupported op: {self._op}")


class FakeSupabaseClient:
    """Faithful table-level mock tracking executed predicates and simulating DB roles."""

    def __init__(
        self,
        *,
        role: str = "service_role",
        rls_enabled: bool = True,
        revoked_roles: set[str] | None = None,
        shared_rows: list[dict] | None = None,
    ):
        self.role = role
        self.rls_enabled = rls_enabled
        self.revoked_roles = {"anon", "authenticated"} if revoked_roles is None else set(revoked_roles)
        self.rows: list[dict] = shared_rows if shared_rows is not None else []
        self.recorded_queries: list[tuple[str, list[tuple[str, object]]]] = []

    def table(self, name: str):
        assert name == "memories"
        outer = self

        class RecordingQuery(_FakeTableQuery):
            def execute(self_q):
                outer.recorded_queries.append((self_q._op or "", list(self_q._filters)))
                return super().execute()

        return RecordingQuery(
            self.rows,
            role=self.role,
            rls_enabled=self.rls_enabled,
            revoked_roles=self.revoked_roles,
        )


def test_01_rls_and_privilege_migration_is_additive_and_reversible():
    """Verify migration 007 enables RLS, revokes public roles, preserves service_role and data."""
    sql_path = BACKEND_ROOT / "migrations" / "007_memories_rls_security.sql"
    assert sql_path.exists(), "007_memories_rls_security.sql migration is missing"
    sql = sql_path.read_text(encoding="utf-8")

    # Must enable RLS and revoke anon/authenticated/PUBLIC privileges
    assert "ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;" in sql
    assert "REVOKE ALL ON TABLE public.memories FROM anon, authenticated;" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memories TO service_role;" in sql

    # Rule C: no destructive table/schema/data operations in active SQL statements
    active_lines = [
        line.strip().upper()
        for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    active_sql = "\n".join(active_lines)
    for forbidden in ("DROP TABLE", "DROP SCHEMA", "TRUNCATE", "DELETE FROM", "DROP COLUMN"):
        assert forbidden not in active_sql, f"Forbidden destructive statement found: {forbidden}"

    # Verify simulated anon & authenticated fail while service_role succeeds
    shared_rows: list[dict] = []
    service_client = FakeSupabaseClient(role="service_role", shared_rows=shared_rows)
    anon_client = FakeSupabaseClient(role="anon", shared_rows=shared_rows)
    auth_client = FakeSupabaseClient(role="authenticated", shared_rows=shared_rows)

    service_repo = SupabaseMemoryRepository(service_client)
    rec = MemoryRecord.now(
        "mem-rls-1",
        "owner-1",
        MemoryDomain.BOSS_PERSONAL,
        MemoryCategory.FACT,
        {"text": "Confidential note"},
    )
    service_repo.create(rec)
    assert len(shared_rows) == 1

    for restricted_client in (anon_client, auth_client):
        restricted_repo = SupabaseMemoryRepository(restricted_client)
        with pytest.raises(RuntimeError, match="42501"):
            restricted_repo.retrieve("owner-1", MemoryDomain.BOSS_PERSONAL)
        with pytest.raises(RuntimeError, match="42501"):
            restricted_repo.get("mem-rls-1", owner_id="owner-1")
        with pytest.raises(RuntimeError, match="42501"):
            restricted_repo.update(rec, owner_id="owner-1")
        with pytest.raises(RuntimeError, match="42501"):
            restricted_repo.forget("mem-rls-1", owner_id="owner-1")


def test_02_every_supabase_repository_query_enforces_explicit_owner_predicate():
    """Verify retrieve/get/update/forget fail closed without owner_id and include owner_id filter."""
    client = FakeSupabaseClient(role="service_role")
    repo = SupabaseMemoryRepository(client)

    owner_a_rec = MemoryRecord.now(
        "mem-a1",
        "owner-a",
        MemoryDomain.BOSS_PERSONAL,
        MemoryCategory.PROFILE,
        {"text": "Owner A profile"},
    )
    owner_b_rec = MemoryRecord.now(
        "mem-b1",
        "owner-b",
        MemoryDomain.BOSS_PERSONAL,
        MemoryCategory.PROFILE,
        {"text": "Owner B profile"},
    )
    repo.create(owner_a_rec)
    repo.create(owner_b_rec)

    # Missing or blank owner_id must fail closed on every user-scoped method
    with pytest.raises(ValueError, match="SEC-ID-01"):
        repo.retrieve("", MemoryDomain.BOSS_PERSONAL)
    with pytest.raises(ValueError, match="SEC-ID-01"):
        repo.get("mem-a1", owner_id="  ")
    with pytest.raises(ValueError, match="SEC-ID-01"):
        repo.forget("mem-a1", owner_id="")
    with pytest.raises(ValueError, match="SEC-ID-01"):
        repo.update(owner_a_rec, owner_id="")

    # Calling get/forget without owner_id argument raises TypeError (cannot omit)
    with pytest.raises(TypeError):
        repo.get("mem-a1")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        repo.forget("mem-a1")  # type: ignore[call-arg]

    # Verify owner-scoped reads are isolated
    assert [r.memory_id for r in repo.retrieve("owner-a", MemoryDomain.BOSS_PERSONAL)] == ["mem-a1"]
    assert [r.memory_id for r in repo.retrieve("owner-b", MemoryDomain.BOSS_PERSONAL)] == ["mem-b1"]
    assert repo.get("mem-a1", owner_id="owner-b") is None
    assert repo.get("mem-a1", owner_id="owner-a") is not None

    # Verify every recorded non-insert query carried an owner_id predicate
    non_insert_queries = [q for q in client.recorded_queries if q[0] in {"select", "update"}]
    assert len(non_insert_queries) >= 4
    for op, filters in non_insert_queries:
        filter_cols = {col for col, _ in filters}
        assert "owner_id" in filter_cols, f"Query op={op} omitted owner_id filter: {filters}"


def test_03_cross_owner_update_and_forget_are_blocked_and_preserve_data():
    """Cross-owner update and forget leave victim record intact and return safe results."""
    client = FakeSupabaseClient(role="service_role")
    repo = SupabaseMemoryRepository(client)
    api = MemoryAPI(repo)

    owner_a = AuthContext(user_id="owner-a", authenticated=True)
    owner_b = AuthContext(user_id="owner-b", authenticated=True)

    victim = api.create(owner_a, {"text": "Top secret victim fact"}, MemoryCategory.FACT.value)

    # 1. Cross-owner update via MemoryAPI fails without exposing victim text or modifying row
    with pytest.raises(KeyError, match="memory not found"):
        api.update(owner_b, victim.memory_id, {"text": "HIJACKED"})

    # 2. Forged MemoryRecord carrying attacker owner_id targeting victim memory_id fails
    forged = MemoryRecord(
        memory_id=victim.memory_id,
        owner_id="owner-b",
        domain=victim.domain,
        category=victim.category,
        content={"text": "FORGED_OVERWRITE"},
        session_id=victim.session_id,
        created_at=victim.created_at,
        updated_at=victim.updated_at,
        active=True,
    )
    with pytest.raises(KeyError, match="memory not found"):
        repo.update(forged, owner_id="owner-b")

    # 3. Direct repo update with mismatched owner_id parameter fails
    with pytest.raises(PermissionError, match="ownership"):
        repo.update(victim, owner_id="owner-b")

    # 4. Cross-owner forget via repo and MemoryAPI fails safely and leaves record active
    assert repo.forget(victim.memory_id, owner_id="owner-b") is False
    with pytest.raises(KeyError, match="memory not found"):
        api.forget(owner_b, victim.memory_id)

    # Victim record remains completely unmodified and active
    intact = repo.get(victim.memory_id, owner_id="owner-a")
    assert intact is not None
    assert intact.active is True
    assert intact.owner_id == "owner-a"
    assert intact.content == {"text": "Top secret victim fact"}


def test_04_valid_owner_crud_works_across_mark_i_provider_and_supabase_repo():
    """Legitimate owner create/retrieve/update/forget flow works cleanly through TemporaryMarkIMemoryProvider."""
    client = FakeSupabaseClient(role="service_role")
    api = MemoryAPI(SupabaseMemoryRepository(client))
    provider = TemporaryMarkIMemoryProvider(api_factory=lambda: api)

    assert provider.store(
        "My favorite programming language is Python",
        user_id="valid-boss",
        session_id="sess-1",
        metadata={"store_session": True},
    )

    resp = provider.retrieve(
        MemoryRetrievalRequest(
            query="programming language",
            user_id="valid-boss",
            session_id="sess-1",
        )
    )
    assert resp.memory_count >= 1
    assert "Python" in "\n".join(resp.context_strings)

    # Find record ID via owner-scoped retrieve
    recs = api.retrieve(AuthContext("valid-boss", authenticated=True), MemoryDomain.BOSS_PERSONAL.value)
    assert len(recs) == 1
    rec_id = recs[0].memory_id

    # Intruder provider call fails safely without modifying owner record
    assert provider.update(rec_id, {"text": "Hacked"}, user_id="intruder") is False
    assert provider.delete(rec_id, user_id="intruder") is False

    # Valid owner update & delete succeed
    assert provider.update(
        rec_id,
        {"text": "My favorite programming language is Rust"},
        user_id="valid-boss",
        category=MemoryCategory.PREFERENCE.value,
    ) is True
    updated = provider.retrieve(MemoryRetrievalRequest(query="language", user_id="valid-boss"))
    assert "Rust" in "\n".join(updated.context_strings)

    assert provider.delete(rec_id, user_id="valid-boss") is True
    after = provider.retrieve(MemoryRetrievalRequest(query="Rust", user_id="valid-boss"))
    assert after.memory_count == 0


def test_05_supabase_service_role_env_docs_dotenv_and_anon_jwt_warning(tmp_path, caplog, monkeypatch):
    """Category A: .env.example requires service_role, dotenv does not override env, anon JWT warns safely."""
    import base64

    monkeypatch.setenv("VENNELA_BOSS_ID", "boss_p0_01_cat_a")
    monkeypatch.setenv("VENNELA_AGENT_TOKEN", "token-cat-a-secret-123456")
    monkeypatch.setenv("LIGHTWEIGHT_MODE", "true")
    monkeypatch.setenv("LLM_ROUTER_MOCK", "true")
    import app as app_module
    from core.memory_contracts import _warn_if_anon_supabase_key

    env_example = (BACKEND_ROOT.parent / ".env.example").read_text(encoding="utf-8")
    assert "SUPABASE_KEY must contain the Supabase service_role key, NOT the anon/public key." in env_example
    assert "privileged server-side credential" in env_example

    # Dotenv loading sets unset vars without overriding pre-existing environment values
    env_file = tmp_path / ".env"
    env_file.write_text(
        "VENNELA_TEST_DOTENV_KEEP=from_file\nVENNELA_TEST_DOTENV_NEW=loaded_from_file\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VENNELA_TEST_DOTENV_KEEP", "from_render_env")
    monkeypatch.delenv("VENNELA_TEST_DOTENV_NEW", raising=False)
    assert app_module._load_backend_dotenv(env_file) is True
    assert os.environ["VENNELA_TEST_DOTENV_KEEP"] == "from_render_env"
    assert os.environ["VENNELA_TEST_DOTENV_NEW"] == "loaded_from_file"

    # Simulated anon JWT emits a warning without ever exposing the token itself
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    anon_payload = base64.urlsafe_b64encode(b'{"role":"anon","iss":"supabase"}').decode().rstrip("=")
    anon_jwt = f"{header}.{anon_payload}.CANARY_SIG_DO_NOT_LOG"
    sr_payload = base64.urlsafe_b64encode(b'{"role":"service_role","iss":"supabase"}').decode().rstrip("=")
    sr_jwt = f"{header}.{sr_payload}.CANARY_SR_SIG"

    with caplog.at_level("WARNING"):
        _warn_if_anon_supabase_key(anon_jwt)
        _warn_if_anon_supabase_key(sr_jwt)

    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "role='anon'" in log_text
    assert "CANARY_SIG_DO_NOT_LOG" not in log_text
    assert anon_jwt not in log_text
    assert sr_jwt not in log_text


def test_06_owner_identity_and_nine_column_write_compatibility(monkeypatch):
    """Category B: VENNELA_BOSS_ID routes through owner verification and writes exactly 9 MARK-I columns."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("VENNELA_BOSS_ID", "boss_mark_i_owner")
    monkeypatch.setenv("VENNELA_AGENT_TOKEN", "token-cat-b-secret-123456")
    monkeypatch.setenv("LIGHTWEIGHT_MODE", "true")
    monkeypatch.setenv("VENNELA_MEMORY_PROVIDER", "mark_i")
    monkeypatch.setenv("VENNELA_MEMORY_ENABLED", "true")
    monkeypatch.setenv("LLM_ROUTER_MOCK", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://ymsbhyslvkcyipnglvlf.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-service-role-key")

    import app as app_module
    from core.memory_contracts import reset_memory_subsystem
    from llm_router.adapter import VennelaLLMAdapter

    reset_memory_subsystem()
    client_db = FakeSupabaseClient(role="service_role")
    monkeypatch.setattr(app_module, "_brain_instance", None)
    monkeypatch.setattr(app_module, "_llm_adapter_instance", VennelaLLMAdapter(mock=True))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("supabase.create_client", lambda url, key, options=None: client_db)
        test_client = TestClient(app_module.app)
        headers = {"Authorization": "Bearer token-cat-b-secret-123456"}

        # Cross-owner attempt is rejected with 403 before touching memory
        forbidden = test_client.post(
            "/chat",
            headers=headers,
            json={"message": "Remember my favorite editor is Neovim", "user_id": "other_user"},
        )
        assert forbidden.status_code == 403

        ok = test_client.post(
            "/chat",
            headers=headers,
            json={"message": "Remember my favorite editor is Neovim", "session_id": "sess-cat-b"},
        )
        assert ok.status_code == 200

    assert len(client_db.rows) >= 1
    expected_cols = {
        "memory_id", "owner_id", "domain", "category", "content",
        "session_id", "created_at", "updated_at", "active",
    }
    for row in client_db.rows:
        assert set(row.keys()) == expected_cols
        assert row["owner_id"] == "boss_mark_i_owner"

    select_queries = [q for q in client_db.recorded_queries if q[0] == "select"]
    assert any(("owner_id", "boss_mark_i_owner") in filters for _, filters in select_queries)
    reset_memory_subsystem()
