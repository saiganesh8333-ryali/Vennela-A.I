"""Phase 4 (P0-02): Memory Reliability, Startup Validation & Controlled Degraded Mode tests."""

from __future__ import annotations

import os
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("VENNELA_BOSS_ID", "boss_p0_02_test")
os.environ.setdefault("VENNELA_AGENT_TOKEN", "token-p0-02-secret-123456789")
os.environ.setdefault("LIGHTWEIGHT_MODE", "true")
os.environ.setdefault("LLM_ROUTER_MOCK", "true")

import app as app_module
from core.memory_contracts import (
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    TemporaryMarkIMemoryProvider,
    get_memory_subsystem,
    reset_memory_subsystem,
)
from llm_router.adapter import VennelaLLMAdapter
import memory.repository as mem_repo_module


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['VENNELA_AGENT_TOKEN']}"}


@pytest.fixture(autouse=True)
def clean_p0_02_env():
    reset_memory_subsystem()
    app_module._brain_instance = None
    app_module._llm_adapter_instance = VennelaLLMAdapter(mock=True)
    saved = {
        k: os.environ.get(k)
        for k in (
            "VENNELA_MEMORY_PROVIDER",
            "VENNELA_MEMORY_ENABLED",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "ENVIRONMENT",
            "RENDER",
        )
    }
    yield
    reset_memory_subsystem()
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class ControllableSupabaseClient:
    """In-memory PostgREST client that supports outage injection and recovery."""

    def __init__(self, *, fail_mode: str | None = None):
        self.fail_mode = fail_mode  # None, "raise", "error_obj"
        self.rows: list[dict] = []
        self.probe_calls = 0

    def table(self, name: str):
        assert name == "memories"
        outer = self

        class Query:
            def __init__(self):
                self._op = None
                self._payload = None
                self._filters: list[tuple[str, object]] = []
                self._cols = "*"
                self._order_col = None
                self._order_desc = False
                self._limit = None

            def select(self, cols="*"):
                self._op = "select"
                self._cols = cols
                return self

            def insert(self, payload):
                self._op = "insert"
                self._payload = dict(payload)
                return self

            def update(self, payload):
                self._op = "update"
                self._payload = dict(payload)
                return self

            def eq(self, col, val):
                self._filters.append((col, val))
                return self

            def order(self, col, desc=False):
                self._order_col = col
                self._order_desc = desc
                return self

            def limit(self, count):
                self._limit = count
                return self

            def execute(self):
                if self._op == "select" and self._cols == "memory_id" and not self._filters:
                    outer.probe_calls += 1

                if outer.fail_mode == "raise":
                    raise TimeoutError("Simulated Supabase timeout")
                if outer.fail_mode == "error_obj":
                    return SimpleNamespace(data=None, error={"message": "connection refused"})

                if self._op == "insert":
                    row = dict(self._payload)
                    outer.rows.append(row)
                    return SimpleNamespace(data=[dict(row)], error=None)

                if self._op == "select":
                    matched = [
                        dict(r)
                        for r in outer.rows
                        if all(r.get(c) == v for c, v in self._filters)
                    ]
                    if self._order_col:
                        matched.sort(key=lambda r: r.get(self._order_col, ""), reverse=self._order_desc)
                    if self._limit is not None:
                        matched = matched[: self._limit]
                    return SimpleNamespace(data=matched, error=None)

                if self._op == "update":
                    updated = []
                    for r in outer.rows:
                        if all(r.get(c) == v for c, v in self._filters):
                            r.update(self._payload)
                            updated.append(dict(r))
                    return SimpleNamespace(data=updated, error=None)

                raise AssertionError(f"Unsupported op {self._op}")

        return Query()


def test_01_missing_production_credentials_fail_startup():
    """Production/Render startup with mark_i fails immediately if SUPABASE_URL or SUPABASE_KEY is missing."""
    for env_patch in (
        {"ENVIRONMENT": "production", "VENNELA_MEMORY_PROVIDER": "mark_i"},
        {"RENDER": "true", "VENNELA_MEMORY_PROVIDER": "mark_i", "SUPABASE_URL": "https://example.supabase.co"},
        {"ENVIRONMENT": "staging", "VENNELA_MEMORY_PROVIDER": "mark_i", "SUPABASE_KEY": "service-role-key"},
    ):
        reset_memory_subsystem()
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("SUPABASE_KEY", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("RENDER", None)
        for k, v in env_patch.items():
            os.environ[k] = v

        with pytest.raises(RuntimeError, match=r"P0-02 FATAL|SUPABASE_URL"):
            get_memory_subsystem()

        with pytest.raises(RuntimeError, match=r"P0-02 FATAL|SUPABASE_URL"):
            TemporaryMarkIMemoryProvider().validate_startup()

        with pytest.raises(RuntimeError, match=r"P0-02 FATAL|SUPABASE_URL"):
            app_module.validate_memory_startup()


def test_02_successful_initialization_configures_explicit_timeouts_without_replace():
    """ClientOptions(postgrest_client_timeout=10, storage_client_timeout=10) passed directly without .replace()."""
    from supabase import ClientOptions

    captured: dict[str, object] = {}
    replace_called = False
    orig_replace = ClientOptions.replace

    def forbidden_replace(self, *args, **kwargs):
        nonlocal replace_called
        replace_called = True
        return orig_replace(self, *args, **kwargs)

    fake_client = ControllableSupabaseClient(fail_mode=None)

    def spy_create_client(url: str, key: str, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return fake_client

    os.environ["ENVIRONMENT"] = "production"
    os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
    os.environ["SUPABASE_URL"] = "https://staging.example.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-service-role-key"

    with (
        patch.object(ClientOptions, "replace", forbidden_replace),
        patch("supabase.create_client", side_effect=spy_create_client),
    ):
        provider = get_memory_subsystem()

    assert isinstance(provider, TemporaryMarkIMemoryProvider)
    assert provider.memory_status == "healthy"
    assert captured["url"] == "https://staging.example.supabase.co"
    assert captured["key"] == "test-service-role-key"
    opts = captured["options"]
    assert opts is not None
    assert getattr(opts, "postgrest_client_timeout", None) == 10
    assert getattr(opts, "storage_client_timeout", None) == 10
    assert replace_called is False
    assert fake_client.probe_calls == 1


def test_03_startup_connectivity_failure_aborts_production_startup():
    """Failing initial probe aborts get_memory_subsystem() and FastAPI startup immediately."""
    os.environ["ENVIRONMENT"] = "production"
    os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
    os.environ["SUPABASE_URL"] = "https://staging.example.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-service-role-key"

    failing_client = ControllableSupabaseClient(fail_mode="raise")
    with patch("supabase.create_client", return_value=failing_client):
        with pytest.raises(RuntimeError, match="P0-02 FATAL"):
            get_memory_subsystem()

        with pytest.raises(RuntimeError, match="P0-02 FATAL"):
            app_module.validate_memory_startup()

    # Also test non-raising Supabase .error response during probe
    error_client = ControllableSupabaseClient(fail_mode="error_obj")
    reset_memory_subsystem()
    with patch("supabase.create_client", return_value=error_client):
        with pytest.raises(RuntimeError, match="P0-02 FATAL"):
            get_memory_subsystem()


def test_04_production_never_substitutes_in_memory_repository():
    """Missing credentials or DB failure in production never falls back to InMemoryMemoryRepository."""
    instantiated_in_memory = False
    orig_init = mem_repo_module.InMemoryMemoryRepository.__init__

    def spy_in_mem_init(self, *args, **kwargs):
        nonlocal instantiated_in_memory
        instantiated_in_memory = True
        return orig_init(self, *args, **kwargs)

    os.environ["ENVIRONMENT"] = "production"
    os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
    os.environ.pop("SUPABASE_URL", None)
    os.environ.pop("SUPABASE_KEY", None)

    with patch.object(mem_repo_module.InMemoryMemoryRepository, "__init__", spy_in_mem_init):
        with pytest.raises(RuntimeError):
            get_memory_subsystem()

    assert instantiated_in_memory is False

    # DB failure during runtime outage also must never construct InMemoryMemoryRepository
    os.environ["SUPABASE_URL"] = "https://staging.example.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-service-role-key"
    client = ControllableSupabaseClient(fail_mode=None)

    with (
        patch("supabase.create_client", return_value=client),
        patch.object(mem_repo_module.InMemoryMemoryRepository, "__init__", spy_in_mem_init),
    ):
        provider = get_memory_subsystem()
        client.fail_mode = "raise"
        resp = provider.retrieve(MemoryRetrievalRequest(query="hello", user_id="boss_p0_02_test"))
        stored = provider.store("My name is Ganesh", user_id="boss_p0_02_test")

    assert instantiated_in_memory is False
    assert resp.memory_count == 0
    assert resp.metadata["memory_status"] == "degraded"
    assert stored is False


def test_05_06_07_runtime_outage_readiness_503_stateless_brain_b_and_recovery():
    """Simulate healthy -> runtime outage (/ready 503 + Brain B degraded stateless) -> recovery (/ready 200)."""
    os.environ["ENVIRONMENT"] = "production"
    os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
    os.environ["SUPABASE_URL"] = "https://staging.example.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-service-role-key"

    client_db = ControllableSupabaseClient(fail_mode=None)
    test_client = TestClient(app_module.app)

    with patch("supabase.create_client", return_value=client_db):
        provider = get_memory_subsystem()
        assert provider.memory_status == "healthy"

        # Healthy state: /ready returns 200
        ready_ok = test_client.get("/ready")
        assert ready_ok.status_code == 200
        assert ready_ok.json()["status"] == "ready"
        assert ready_ok.json()["memory_status"] == "healthy"

        # Seed a real memory via /chat while healthy
        chat_healthy = test_client.post(
            "/chat",
            headers=_auth_headers(),
            json={"message": "Remember my favorite city is Hyderabad", "session_id": "s-p02"},
        )
        assert chat_healthy.status_code == 200
        assert "memory_status" not in chat_healthy.json()
        assert len(client_db.rows) >= 1

        # Simulate runtime Supabase outage
        client_db.fail_mode = "raise"

        # /ready must report HTTP 503 with memory_status="degraded"
        ready_down = test_client.get("/ready")
        assert ready_down.status_code == 503
        assert ready_down.json()["status"] == "not_ready"
        assert ready_down.json()["memory_status"] == "degraded"

        # /health liveness remains 200 but shows memory_status="degraded"
        health_down = test_client.get("/health")
        assert health_down.status_code == 200
        assert health_down.json()["memory_status"] == "degraded"

        # Brain B stays operational cleanly with degraded stateless response
        chat_degraded = test_client.post(
            "/chat",
            headers=_auth_headers(),
            json={"message": "Explain microservices briefly", "session_id": "s-p02"},
        )
        assert chat_degraded.status_code == 200
        body = chat_degraded.json()
        assert len(body["response"]) > 0
        assert body["memory_status"] == "degraded"

        # Streaming also stays operational with X-Memory-Status: degraded header
        stream_degraded = test_client.post(
            "/chat/stream",
            headers=_auth_headers(),
            json={"message": "Hello Vennela", "session_id": "s-p02"},
        )
        assert stream_degraded.status_code == 200
        assert stream_degraded.headers.get("X-Memory-Status") == "degraded"

        # Provider store never pretends persistence during outage
        assert provider.store("I prefer Rust", user_id="boss_p0_02_test") is False

        # Restore Supabase connectivity -> recovers cleanly without restart
        client_db.fail_mode = None
        ready_recovered = test_client.get("/ready")
        assert ready_recovered.status_code == 200
        assert ready_recovered.json()["status"] == "ready"
        assert ready_recovered.json()["memory_status"] == "healthy"
        assert provider.memory_status == "healthy"

        chat_recovered = test_client.post(
            "/chat",
            headers=_auth_headers(),
            json={"message": "Remember my favorite color is Cobalt", "session_id": "s-p02"},
        )
        assert chat_recovered.status_code == 200
        assert "memory_status" not in chat_recovered.json()


def test_08_mark_ii_devsecops_block_remains_intact():
    """RULE B: MARK-II Cognitive Memory remains blocked in both dev and production."""
    for env in ("development", "production"):
        reset_memory_subsystem()
        os.environ["ENVIRONMENT"] = env
        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_ii"
        with pytest.raises(RuntimeError, match=r"\[DEVSECOPS BLOCK\]"):
            get_memory_subsystem()


def test_09_readiness_endpoint_matrix(monkeypatch, caplog):
    """Category H: verify /ready across all 7 live connectivity, credential, failure, and stateless cases."""
    test_client = TestClient(app_module.app)

    # 1 & 2. Supabase connection succeeds with records (never leaks content)
    reset_memory_subsystem()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VENNELA_MEMORY_PROVIDER", "mark_i")
    monkeypatch.setenv("SUPABASE_URL", "https://ymsbhyslvkcyipnglvlf.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-service-role-key")
    db_with_records = ControllableSupabaseClient(fail_mode=None)
    db_with_records.rows.append({
        "memory_id": "mem-ready-1",
        "owner_id": os.environ["VENNELA_BOSS_ID"],
        "domain": "boss_personal",
        "category": "Fact",
        "content": {"text": "TOP_SECRET_READY_CANARY"},
        "session_id": None,
        "created_at": "2026-11-27T00:00:00Z",
        "updated_at": "2026-11-27T00:00:00Z",
        "active": True,
    })
    with patch("supabase.create_client", return_value=db_with_records):
        resp_with_rows = test_client.get("/ready")
    assert resp_with_rows.status_code == 200
    body_rows = resp_with_rows.json()
    assert body_rows["status"] == "ready"
    assert body_rows["memory_status"] == "healthy"
    assert body_rows["owner_scoped"] is True
    assert body_rows["owner_records_present"] is True
    assert "TOP_SECRET_READY_CANARY" not in resp_with_rows.text

    # 3. Supabase query succeeds with zero records for configured owner
    reset_memory_subsystem()
    db_empty = ControllableSupabaseClient(fail_mode=None)
    with patch("supabase.create_client", return_value=db_empty), caplog.at_level("WARNING"):
        resp_empty = test_client.get("/ready")
    assert resp_empty.status_code == 200
    body_empty = resp_empty.json()
    assert body_empty["status"] == "ready"
    assert body_empty["memory_status"] == "healthy"
    assert body_empty["owner_scoped"] is True
    assert body_empty["owner_records_present"] is False
    assert "returned 0 rows" in "\n".join(r.getMessage() for r in caplog.records)

    # 4. Supabase credentials missing with mark_i (even in non-production) -> 503 not_ready
    reset_memory_subsystem()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    resp_missing_creds = test_client.get("/ready")
    assert resp_missing_creds.status_code == 503
    assert resp_missing_creds.json()["status"] == "not_ready"
    assert resp_missing_creds.json()["memory_status"] == "degraded"
    assert resp_missing_creds.json()["reason"] == "missing_supabase_credentials"

    # 5. Supabase query fails -> 503 not_ready
    reset_memory_subsystem()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SUPABASE_URL", "https://ymsbhyslvkcyipnglvlf.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-service-role-key")
    db_ok_then_fail = ControllableSupabaseClient(fail_mode=None)
    with patch("supabase.create_client", return_value=db_ok_then_fail):
        get_memory_subsystem()
        db_ok_then_fail.fail_mode = "error_obj"
        resp_query_fail = test_client.get("/ready")
    assert resp_query_fail.status_code == 503
    assert resp_query_fail.json()["status"] == "not_ready"
    assert resp_query_fail.json()["memory_status"] == "degraded"

    # 6. Memory provider unavailable -> 503 not_ready
    reset_memory_subsystem()
    with patch.object(app_module, "get_memory_subsystem", return_value=None):
        resp_unavail = test_client.get("/ready")
    assert resp_unavail.status_code == 503
    assert resp_unavail.json()["status"] == "not_ready"
    assert resp_unavail.json()["memory_status"] == "degraded"

    # 7. Memory intentionally disabled (stateless) -> 200 ready with disabled semantics
    reset_memory_subsystem()
    monkeypatch.setenv("VENNELA_MEMORY_PROVIDER", "stateless")
    monkeypatch.setenv("VENNELA_MEMORY_ENABLED", "false")
    resp_disabled = test_client.get("/ready")
    assert resp_disabled.status_code == 200
    body_disabled = resp_disabled.json()
    assert body_disabled["status"] == "ready"
    assert body_disabled["memory_mode"] == "STATELESS_ISOLATED"
    assert body_disabled["memory_status"] == "disabled"
    assert body_disabled["memory_enabled"] is False
    assert body_disabled["reason"] == "provider_disabled"
    reset_memory_subsystem()


def test_10_safe_diagnostic_logging_enabled_disabled_and_failure_modes(monkeypatch, caplog):
    """Verify safe startup and /ready diagnostic logs across enabled, disabled, alias, and failure paths."""
    secret_key = "canary-sr-key-DO-NOT-LOG-998877"
    secret_alias = "canary-alias-key-DO-NOT-LOG-445566"
    secret_agent = "canary-agent-token-DO-NOT-LOG-112233"
    monkeypatch.setenv("VENNELA_AGENT_TOKEN", secret_agent)

    test_client = TestClient(app_module.app)

    # 1. Memory disabled via unset env vars -> startup & /ready log provider_disabled with zero secrets
    reset_memory_subsystem()
    monkeypatch.delenv("VENNELA_MEMORY_PROVIDER", raising=False)
    monkeypatch.delenv("VENNELA_MEMORY_ENABLED", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", secret_key)
    caplog.clear()
    with caplog.at_level("INFO"):
        app_module.validate_memory_startup()
        resp_unset = test_client.get("/ready")

    assert resp_unset.status_code == 200
    assert resp_unset.json()["memory_mode"] == "STATELESS_ISOLATED"
    assert resp_unset.json()["memory_enabled"] is False
    assert resp_unset.json()["reason"] == "provider_disabled"
    disabled_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "STATELESS_ISOLATED" in disabled_logs
    assert "reason=provider_disabled" in disabled_logs
    assert secret_key not in disabled_logs
    assert secret_agent not in disabled_logs

    # 2. Memory enabled with SUPABASE_SERVICE_ROLE_KEY fallback -> startup & /ready log healthy with zero secrets
    reset_memory_subsystem()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VENNELA_MEMORY_PROVIDER", "mark_i")
    monkeypatch.setenv("VENNELA_MEMORY_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://ymsbhyslvkcyipnglvlf.supabase.co")
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", secret_alias)

    captured_auth: dict[str, str] = {}
    db_ok = ControllableSupabaseClient(fail_mode=None)

    def fake_create_client(url: str, key: str, options=None):
        captured_auth["url"] = url
        captured_auth["key"] = key
        return db_ok

    caplog.clear()
    with patch("supabase.create_client", side_effect=fake_create_client), caplog.at_level("INFO"):
        app_module.validate_memory_startup()
        resp_enabled = test_client.get("/ready")

    assert captured_auth["key"] == secret_alias
    assert resp_enabled.status_code == 200
    assert resp_enabled.json()["memory_mode"] == "MARK_I_TEMPORARY"
    assert resp_enabled.json()["memory_status"] == "healthy"
    assert resp_enabled.json()["memory_enabled"] is True
    enabled_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "MARK-I memory startup validation passed" in enabled_logs
    assert "memory_mode=MARK_I_TEMPORARY" in enabled_logs
    assert "memory_status=healthy" in enabled_logs
    assert secret_alias not in enabled_logs
    assert secret_alias not in resp_enabled.text
    assert secret_agent not in enabled_logs

    # 3. Missing SUPABASE_KEY specifically -> diagnostic_reason=missing_env:SUPABASE_KEY
    reset_memory_subsystem()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://ymsbhyslvkcyipnglvlf.supabase.co")
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    caplog.clear()
    with caplog.at_level("WARNING"):
        resp_missing_key = test_client.get("/ready")
    assert resp_missing_key.status_code == 503
    assert resp_missing_key.json()["reason"] == "missing_supabase_credentials"
    assert resp_missing_key.json()["diagnostic_reason"] == "missing_env:SUPABASE_KEY"
    assert "reason=missing_env:SUPABASE_KEY" in "\n".join(r.getMessage() for r in caplog.records)

    # 4. Missing supabase package -> missing_package:supabase without leaking secrets
    reset_memory_subsystem()
    monkeypatch.setenv("SUPABASE_KEY", secret_key)
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "supabase" or name.startswith("supabase."):
            raise ImportError("No module named 'supabase'", name="supabase")
        return real_import(name, *args, **kwargs)

    caplog.clear()
    with patch("builtins.__import__", side_effect=fake_import), caplog.at_level("WARNING"):
        resp_missing_pkg = test_client.get("/ready")
    assert resp_missing_pkg.status_code == 503
    assert resp_missing_pkg.json()["reason"] == "missing_package:supabase"
    pkg_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "reason=missing_package:supabase" in pkg_logs
    assert secret_key not in pkg_logs
    assert secret_key not in resp_missing_pkg.text

    # 5. Supabase HTTP probe failure -> supabase_probe_failed:<status>/<ErrorType> without leaking secrets
    reset_memory_subsystem()

    class HttpAuthError(RuntimeError):
        def __init__(self, msg: str, status_code: int):
            super().__init__(msg)
            self.status_code = status_code

    class HttpErrorSupabaseClient:
        def table(self, name: str):
            class _Q:
                def select(self, *a, **kw):
                    return self

                def limit(self, *a, **kw):
                    return self

                def execute(self):
                    raise HttpAuthError(f"Invalid API key {secret_key}", status_code=401)

            return _Q()

    with patch("supabase.create_client", return_value=HttpErrorSupabaseClient()):
        # Non-prod allows caching TemporaryMarkIMemoryProvider then probing on /ready
        caplog.clear()
        with caplog.at_level("WARNING"):
            resp_http_err = test_client.get("/ready")

    assert resp_http_err.status_code == 503
    assert resp_http_err.json()["reason"] == "supabase_probe_failed:401/HttpAuthError"
    err_logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "reason=supabase_probe_failed:401/HttpAuthError" in err_logs
    assert secret_key not in err_logs
    assert secret_key not in resp_http_err.text
    reset_memory_subsystem()
