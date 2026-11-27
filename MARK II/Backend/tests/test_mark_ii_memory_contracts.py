"""Production verification tests for MARK-II memory contracts, isolation, and safeguards."""

import os
import sys
import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from core.memory_contracts import (
    ALLOWED_MEMORY_PROVIDERS,
    MemoryIsolationMode,
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    StatelessMemoryProvider,
    get_memory_subsystem,
    reset_memory_subsystem,
)


@pytest.fixture(autouse=True)
def clean_memory_env():
    """Ensure clean memory environment before and after every test."""
    reset_memory_subsystem()
    old_provider = os.environ.get("VENNELA_MEMORY_PROVIDER")
    old_enabled = os.environ.get("VENNELA_MEMORY_ENABLED")
    old_mock = os.environ.get("LLM_ROUTER_MOCK")
    old_env = os.environ.get("ENVIRONMENT")
    old_render = os.environ.get("RENDER")

    yield

    reset_memory_subsystem()
    for var, old_val in [
        ("VENNELA_MEMORY_PROVIDER", old_provider),
        ("VENNELA_MEMORY_ENABLED", old_enabled),
        ("LLM_ROUTER_MOCK", old_mock),
        ("ENVIRONMENT", old_env),
        ("RENDER", old_render),
    ]:
        if old_val is not None:
            os.environ[var] = old_val
        elif var in os.environ:
            del os.environ[var]


class TestMemoryContractsAndAllowlist:
    """Verify strict allowlist and gating of memory providers."""

    def test_allowed_providers_set(self):
        """Allowlist contains stateless, mark_i, and mark_ii."""
        assert ALLOWED_MEMORY_PROVIDERS == {"stateless", "mark_i", "mark_ii"}

    def test_default_provider_is_stateless_when_unset(self):
        """Unset VENNELA_MEMORY_PROVIDER and disabled flag defaults deterministically to stateless."""
        os.environ.pop("VENNELA_MEMORY_PROVIDER", None)
        os.environ.pop("VENNELA_MEMORY_ENABLED", None)
        provider = get_memory_subsystem()
        assert isinstance(provider, StatelessMemoryProvider)
        assert provider.mode == MemoryIsolationMode.STATELESS_ISOLATED

    def test_explicit_stateless_provider(self):
        """VENNELA_MEMORY_PROVIDER=stateless returns StatelessMemoryProvider."""
        os.environ["VENNELA_MEMORY_PROVIDER"] = "stateless"
        provider = get_memory_subsystem()
        assert isinstance(provider, StatelessMemoryProvider)
        assert provider.mode == MemoryIsolationMode.STATELESS_ISOLATED

    def test_explicit_mark_i_provider_activates_temporary_mark_i(self):
        """VENNELA_MEMORY_PROVIDER=mark_i activates TemporaryMarkIMemoryProvider."""
        from core.memory_contracts import TemporaryMarkIMemoryProvider

        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_i"
        provider = get_memory_subsystem()
        assert isinstance(provider, TemporaryMarkIMemoryProvider)
        assert provider.mode == MemoryIsolationMode.MARK_I_TEMPORARY

    def test_rejection_of_legacy_string_provider(self):
        """VENNELA_MEMORY_PROVIDER=legacy fails fast with ValueError."""
        os.environ["VENNELA_MEMORY_PROVIDER"] = "legacy"
        with pytest.raises(ValueError, match=r"\[SEC-MEM-INVALID-PROVIDER\]"):
            get_memory_subsystem()

    def test_rejection_of_unknown_provider(self):
        """Unknown memory provider string fails fast with ValueError."""
        os.environ["VENNELA_MEMORY_PROVIDER"] = "supabase_vector_v2"
        with pytest.raises(ValueError, match=r"\[SEC-MEM-INVALID-PROVIDER\]"):
            get_memory_subsystem()

    def test_blocking_of_premature_mark_ii_activation(self):
        """VENNELA_MEMORY_PROVIDER=mark_ii fails fast with RuntimeError until Phase 4 validation."""
        os.environ["VENNELA_MEMORY_PROVIDER"] = "mark_ii"
        with pytest.raises(RuntimeError, match=r"\[DEVSECOPS BLOCK\]"):
            get_memory_subsystem()

    def test_memory_enabled_flag_does_not_override_stateless(self):
        """VENNELA_MEMORY_ENABLED=true does not bypass stateless mode."""
        os.environ["VENNELA_MEMORY_PROVIDER"] = "stateless"
        os.environ["VENNELA_MEMORY_ENABLED"] = "true"
        provider = get_memory_subsystem()
        assert isinstance(provider, StatelessMemoryProvider)
        assert provider.mode == MemoryIsolationMode.STATELESS_ISOLATED


class TestStatelessMemoryProviderBehavior:
    """Verify isolation, behavior, and security constraints of StatelessMemoryProvider."""

    def test_retrieve_returns_empty_isolated_response(self):
        provider = StatelessMemoryProvider()
        req = MemoryRetrievalRequest(query="Tell me about myself", user_id="boss_verified")
        resp = provider.retrieve(req)
        assert isinstance(resp, MemoryRetrievalResponse)
        assert resp.context_strings == []
        assert resp.memory_count == 0
        assert resp.mode == MemoryIsolationMode.STATELESS_ISOLATED
        assert resp.duration_ms == 0.0

    def test_store_is_noop_in_stateless_mode(self):
        provider = StatelessMemoryProvider()
        result = provider.store("User loves coffee", user_id="boss_verified")
        assert result is False

    def test_retrieve_fails_closed_without_user_id(self):
        """Missing or whitespace-only user_id raises ValueError."""
        with pytest.raises(ValueError, match=r"\[SEC-ID-01\]"):
            MemoryRetrievalRequest(query="test", user_id="")

        with pytest.raises(ValueError, match=r"\[SEC-ID-01\]"):
            MemoryRetrievalRequest(query="test", user_id="   ")

    def test_store_fails_closed_without_user_id(self):
        """Missing or whitespace-only user_id in store raises ValueError."""
        provider = StatelessMemoryProvider()
        with pytest.raises(ValueError, match=r"\[SEC-ID-01\]"):
            provider.store("test note", user_id="")


class TestProductionMockGuard:
    """Verify SEC-MOCK-01 guard preventing mock mode in production environments."""

    def test_mock_mode_rejected_in_production(self):
        from app import validate_startup_security_config

        os.environ["VENNELA_BOSS_ID"] = "boss_test"
        os.environ["VENNELA_AGENT_TOKEN"] = "token_test"
        os.environ["LLM_ROUTER_MOCK"] = "true"
        os.environ["ENVIRONMENT"] = "production"

        with pytest.raises(RuntimeError, match=r"\[SEC-MOCK-01 FATAL\]"):
            validate_startup_security_config()

    def test_mock_mode_rejected_in_render(self):
        from app import validate_startup_security_config

        os.environ["VENNELA_BOSS_ID"] = "boss_test"
        os.environ["VENNELA_AGENT_TOKEN"] = "token_test"
        os.environ["LLM_ROUTER_MOCK"] = "true"
        os.environ["RENDER"] = "true"

        with pytest.raises(RuntimeError, match=r"\[SEC-MOCK-01 FATAL\]"):
            validate_startup_security_config()

    def test_mock_mode_allowed_in_development(self):
        from app import validate_startup_security_config

        os.environ["VENNELA_BOSS_ID"] = "boss_test"
        os.environ["VENNELA_AGENT_TOKEN"] = "token_test"
        os.environ["LLM_ROUTER_MOCK"] = "true"
        os.environ["ENVIRONMENT"] = "development"
        if "RENDER" in os.environ:
            del os.environ["RENDER"]

        # Should not raise
        validate_startup_security_config()
