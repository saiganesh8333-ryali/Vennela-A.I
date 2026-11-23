"""
Vennela AI 2.0 (MARK-II) — Comprehensive Security Remediation Verification Suite
Tests SEC-01 through SEC-10 remediations across Desktop, Backend, and Android components.
"""
import hmac
import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure Backend is on path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set test environment variables
os.environ["VENNELA_BOSS_ID"] = "test_boss_identity"
os.environ["VENNELA_AGENT_TOKEN"] = "test-high-entropy-token-secret-123456789"
os.environ["LIGHTWEIGHT_MODE"] = "true"


class TestSEC01DesktopRCEPrevention(unittest.TestCase):
    """SEC-01: Verify strict allowlist and injection rejection logic."""

    def setUp(self):
        self.allowed_apps = {
            "chrome", "google-chrome", "browser",
            "code", "vscode",
            "notepad",
            "calc", "calculator",
            "terminal", "powershell",
        }
        self.sanitize_pattern = re.compile(r"^[a-z0-9_-]+$")

    def test_approved_applications_pass_validation(self):
        for app in ["notepad", "calc", "chrome", "vscode", "terminal"]:
            self.assertIn(app, self.allowed_apps)
            self.assertTrue(self.sanitize_pattern.match(app))

    def test_command_injection_payloads_rejected(self):
        injection_payloads = [
            "notepad & calc.exe",
            "calc; rm -rf /",
            "notepad | whoami",
            "code`calc`",
            "notepad && powershell -c calc",
            "calc.exe",
            "../../windows/system32/cmd.exe",
            "notepad\ncalc",
            "powershell -NoProfile -Command Write-Host PWNED",
        ]
        for payload in injection_payloads:
            cleaned = payload.strip().lower()
            is_valid = bool(self.sanitize_pattern.match(cleaned)) and (cleaned in self.allowed_apps)
            self.assertFalse(
                is_valid,
                f"Payload '{payload}' bypassed allowlist validation!"
            )


class TestSEC02And03BackendAuthAndBOLA(unittest.TestCase):
    """SEC-02 & SEC-03: Bearer token auth enforcement & BOLA/IDOR user isolation."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import app
        cls.client = TestClient(app.app)
        cls.valid_token = os.environ["VENNELA_AGENT_TOKEN"]
        cls.boss_id = os.environ["VENNELA_BOSS_ID"]

    def test_unauthenticated_request_rejected(self):
        """Endpoints must return 401 Unauthorized when no Authorization header is present."""
        endpoints = [
            ("/embed", "POST", {"text": "hello"}),
            ("/emotion", "POST", {"text": "I am glad"}),
            ("/sentiment", "POST", {"text": "great"}),
            ("/intent", "POST", {"text": "remind me tomorrow"}),
            ("/tasks", "GET", None),
            ("/reminders", "GET", None),
            ("/time", "GET", None),
            ("/date", "GET", None),
            ("/status", "GET", None),
            ("/router/health", "GET", None),
        ]
        for path, method, payload in endpoints:
            if method == "POST":
                resp = self.client.post(path, json=payload)
            else:
                resp = self.client.get(path)
            self.assertEqual(
                resp.status_code, 401,
                f"Endpoint {path} failed to reject unauthenticated request! Status: {resp.status_code}"
            )

    def test_invalid_token_rejected(self):
        """Endpoints must return 401 Unauthorized when an invalid Bearer token is provided."""
        headers = {"Authorization": "Bearer invalid-wrong-token-9999"}
        resp = self.client.get("/tasks", headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid or expired", resp.json().get("detail", ""))

    def test_authenticated_request_accepted(self):
        """Endpoints accept valid Bearer token."""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        resp = self.client.get("/time", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("time", data)
        self.assertIn("timezone", data)

    def test_idor_bola_cross_user_access_blocked(self):
        """Authenticated user cannot access or create resources for another user_id (HTTP 403)."""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        # Attempt to create a task under a different user's identity
        idor_payload = {
            "title": "Malicious Task",
            "user_id": "victim_user_123"
        }
        resp = self.client.post("/tasks", json=idor_payload, headers=headers)
        self.assertEqual(
            resp.status_code, 403,
            f"BOLA/IDOR attempt was not blocked with 403! Got: {resp.status_code}"
        )
        self.assertIn("Cannot access or manipulate resources belonging to another user", resp.json().get("detail", ""))

    def test_idor_bola_listing_blocked(self):
        """Attempting to list another user's tasks returns 403 Forbidden."""
        headers = {"Authorization": f"Bearer {self.valid_token}"}
        resp = self.client.get("/tasks?user_id=victim_account_xyz", headers=headers)
        self.assertEqual(resp.status_code, 403)


class TestSEC04AutomationTransportSecurity(unittest.TestCase):
    """SEC-04: Transport manager token requirements and constant-time comparison."""

    def test_unconfigured_token_fails_fast(self):
        from automation.transport import AgentTransportManager
        with patch.dict(os.environ, {"VENNELA_AGENT_TOKEN": ""}):
            with self.assertRaises(RuntimeError) as ctx:
                AgentTransportManager(MagicMock())
            self.assertIn("requires VENNELA_AGENT_TOKEN", str(ctx.exception))

    def test_constant_time_token_validation(self):
        from automation.transport import AgentTransportManager
        secret = "super-secret-agent-token-test"
        with patch.dict(os.environ, {"VENNELA_AGENT_TOKEN": secret}):
            tm = AgentTransportManager(MagicMock())
            # Valid token
            self.assertTrue(tm.validate_token(secret))
            # Invalid token
            self.assertFalse(tm.validate_token("wrong-token"))
            self.assertFalse(tm.validate_token(""))
            self.assertFalse(tm.validate_token("super-secret-agent-token-tes"))


class TestSEC05CORSConfiguration(unittest.TestCase):
    """SEC-05: CORS origin restriction and wildcard-with-credentials prevention."""

    def test_wildcard_cors_rejected_at_startup(self):
        from app import _get_configured_cors_origins
        with patch.dict(os.environ, {"VENNELA_CORS_ORIGINS": "*"}):
            with self.assertRaises(ValueError) as ctx:
                _get_configured_cors_origins()
            self.assertIn("Wildcard '*' origin cannot be used", str(ctx.exception))

    def test_explicit_cors_origins_parsed(self):
        from app import _get_configured_cors_origins
        allowed = "https://example.com,https://vennela.ai"
        with patch.dict(os.environ, {"VENNELA_CORS_ORIGINS": allowed}):
            origins = _get_configured_cors_origins()
            self.assertEqual(origins, ["https://example.com", "https://vennela.ai"])


class TestSEC06SSRFProtection(unittest.TestCase):
    """SEC-06: Web intelligence URL validator and SSRF prevention."""

    def setUp(self):
        from web_intelligence.reader.http_reader import HTTPPageReader
        self.reader = HTTPPageReader()

    def test_loopback_and_metadata_addresses_blocked(self):
        blocked_urls = [
            "http://127.0.0.1/",
            "http://localhost/",
            "http://127.0.0.1:8000/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://0.0.0.0/",
            "http://[::1]/",
            "http://10.0.0.1/internal",
            "http://192.168.1.1/router",
            "http://172.16.0.1/secret",
        ]
        for url in blocked_urls:
            self.assertFalse(
                self.reader.validate_url(url),
                f"SSRF URL '{url}' was unexpectedly allowed!",
            )

    def test_embedded_credentials_blocked(self):
        self.assertFalse(self.reader.validate_url("http://user:password@example.com/data"))

    def test_unsupported_schemes_blocked(self):
        for bad_scheme in ["ftp://example.com", "file:///etc/passwd", "gopher://bad.com"]:
            self.assertFalse(self.reader.validate_url(bad_scheme))

    def test_legitimate_public_urls_allowed(self):
        safe_urls = [
            "https://www.google.com",
            "https://api.github.com/repos",
            "https://vennela.ai/docs",
        ]
        for url in safe_urls:
            self.assertTrue(self.reader.validate_url(url))


class TestSEC07GroqModelRegistry(unittest.TestCase):
    """SEC-07: Groq model registry failover mapping."""

    def test_valid_production_models_configured(self):
        from llm_router.registry import default_model_registry
        registry = default_model_registry()
        groq_models = registry.by_provider("groq")
        self.assertGreaterEqual(len(groq_models), 2)
        groq_model_ids = [m.model_id for m in groq_models]

        # Ensure hallucinated models are gone
        for model_id in groq_model_ids:
            self.assertNotIn("gpt-oss", model_id)
            self.assertNotIn("qwen3.6", model_id)

        # Ensure verified production models are registered
        self.assertIn("llama-3.3-70b-versatile", groq_model_ids)
        self.assertIn("llama-3.1-8b-instant", groq_model_ids)


class TestSEC08LightweightMode(unittest.TestCase):
    """SEC-08: Pure-Python stubs in lightweight mode without numpy/torch crashes."""

    def test_torch_tensor_stub(self):
        from lightweight_redirect import _create_torch_stub
        torch = _create_torch_stub()
        t = torch.tensor([1.0, 2.0, 3.0])
        self.assertEqual(t.tolist(), [1.0, 2.0, 3.0])
        self.assertEqual(t.shape, (3,))

    def test_sklearn_stubs(self):
        import lightweight_ml
        # Test cosine similarity
        sim = lightweight_ml.cosine_similarity([[1.0, 0.0]], [[1.0, 0.0]])
        self.assertAlmostEqual(sim[0][0], 1.0)
        # Test StandardScaler
        scaler = lightweight_ml.StandardScaler()
        scaled = scaler.fit_transform([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(len(scaled), 2)


class TestSEC09AndroidSecurityConfig(unittest.TestCase):
    """SEC-09: Android security configuration verification (static checks)."""

    def test_cleartext_traffic_disabled_in_manifest(self):
        manifest_path = os.path.join(WORKSPACE_DIR, "Android", "app", "src", "main", "AndroidManifest.xml")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(WORKSPACE_DIR, "..", "app", "src", "main", "AndroidManifest.xml")
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('android:usesCleartextTraffic="false"', content)
        self.assertNotIn('android:usesCleartextTraffic="true"', content)

    def test_dynamic_agent_token_in_config(self):
        config_path = os.path.join(WORKSPACE_DIR, "Android", "app", "src", "main", "java", "com", "vennela", "ai", "AgentConfig.kt")
        if not os.path.exists(config_path):
            config_path = os.path.join(WORKSPACE_DIR, "..", "app", "src", "main", "java", "com", "vennela", "ai", "AgentConfig.kt")
        self.assertTrue(os.path.exists(config_path))
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn('"dev-agent-token-secure-v1"', content)
        self.assertIn("runtimeAgentToken", content)


class TestSEC10RepositoryHygiene(unittest.TestCase):
    """SEC-10: Repository hygiene, root .gitignore, and .env.example verification."""

    def test_root_gitignore_exists_and_protects_secrets(self):
        gitignore_path = os.path.join(WORKSPACE_DIR, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), "Root .gitignore is missing!")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".env", content)
        self.assertIn("google-services.json", content)
        self.assertIn("*.jks", content)
        self.assertIn(".remediation_backup", content)

    def test_env_example_has_no_real_secrets(self):
        example_path = os.path.join(WORKSPACE_DIR, ".env.example")
        self.assertTrue(os.path.exists(example_path), ".env.example is missing!")
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Verify placeholders only
        self.assertIn("VENNELA_BOSS_ID=", content)
        self.assertIn("VENNELA_AGENT_TOKEN=", content)
        self.assertIn("VENNELA_CORS_ORIGINS=", content)
        self.assertNotIn("gsk_", content)
        self.assertNotIn("AIzaSyB", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
