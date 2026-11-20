"""
Brain B Standalone Migration Verification Test
===============================================
Vennela AI 2.0 (MARK-II) — Phase 5 Verification

Verifies that Brain B (ProductionLangGraphBrain) is fully independent of Brain A (NEXUS):
  - No Brain A imports in production code paths
  - ProductionLangGraphBrain constructor takes no legacy_brain parameter
  - Contracts are sourced from core.intelligence_contracts (not agents.*)
  - WebHuntAgent is sourced from web_intelligence.web_hunt (not agents.web_hunt)
  - Rollback script dry-run succeeds

These are STATIC / IMPORT-LEVEL tests — no network calls, no LLM, no Supabase.
"""
import importlib
import inspect
import sys
import os
import pathlib
import subprocess
import ast

# ---- resolve Backend root ---------------------------------------------------
BACKEND_ROOT = pathlib.Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BACKEND_ROOT))


# =============================================================================
# TEST 1: Brain B init signature has NO legacy_brain parameter
# =============================================================================
def test_production_langgraph_brain_has_no_legacy_brain_param():
    """ProductionLangGraphBrain.__init__ must not accept legacy_brain."""
    adapter = importlib.import_module("production_langgraph_adapter")
    cls = getattr(adapter, "ProductionLangGraphBrain")
    sig = inspect.signature(cls.__init__)
    param_names = list(sig.parameters.keys())
    assert "legacy_brain" not in param_names, (
        f"ProductionLangGraphBrain still has legacy_brain parameter: {param_names}"
    )
    # Must have llm_adapter and adjuster
    assert "llm_adapter" in param_names
    assert "adjuster" in param_names


# =============================================================================
# TEST 2: BrainResult and DelegationType come from core.intelligence_contracts
# =============================================================================
def test_contracts_sourced_from_core_not_agents():
    """BrainResult and DelegationType must be importable from core.intelligence_contracts."""
    contracts = importlib.import_module("core.intelligence_contracts")
    assert hasattr(contracts, "BrainResult"), "BrainResult missing from core.intelligence_contracts"
    assert hasattr(contracts, "DelegationType"), "DelegationType missing from core.intelligence_contracts"
    assert hasattr(contracts, "DelegationDecision"), "DelegationDecision missing from core.intelligence_contracts"

    # Verify that core module does NOT import from agents.*
    src = pathlib.Path(BACKEND_ROOT / "core" / "intelligence_contracts.py").read_text(encoding="utf-8")
    assert "from agents" not in src, "core.intelligence_contracts imports from agents.*"
    assert "import agents" not in src, "core.intelligence_contracts imports agents.*"


# =============================================================================
# TEST 3: WebHuntAgent sourced from web_intelligence.web_hunt
# =============================================================================
def test_web_hunt_agent_from_web_intelligence():
    """WebHuntAgent must be importable from web_intelligence.web_hunt."""
    pkg = importlib.import_module("web_intelligence.web_hunt")
    assert hasattr(pkg, "WebHuntAgent"), "WebHuntAgent missing from web_intelligence.web_hunt"
    agent = pkg.WebHuntAgent()
    assert agent.agent_id == "web_hunt", f"Unexpected agent_id: {agent.agent_id}"


# =============================================================================
# TEST 4: agents/ directory no longer exists (Brain A fully archived)
# =============================================================================
def test_brain_a_agents_directory_removed():
    """Backend/agents/ must not exist — Brain A is archived."""
    agents_dir = BACKEND_ROOT / "agents"
    assert not agents_dir.exists(), (
        f"agents/ directory still exists at {agents_dir} — Brain A not fully archived"
    )


# =============================================================================
# TEST 5: Archive directory exists and contains Brain A files
# =============================================================================
def test_brain_a_archive_exists():
    """Brain A archive must exist and contain key files."""
    archive = BACKEND_ROOT / "archive" / "brain_a_nexus"
    assert archive.is_dir(), f"Archive directory missing: {archive}"

    required_files = [
        "brain.py", "models.py", "orchestrator.py", "planner.py",
        "reasoning.py", "registry.py", "__init__.py",
        "web_hunt_original/agent.py", "web_hunt_original/models.py",
        "brain_a_manifest.json", "SHA256_MANIFEST.txt",
        "ARCHIVE_INFO.md", "rollback_brain_a.ps1",
    ]
    missing = [f for f in required_files if not (archive / f.replace("/", os.sep)).exists()]
    assert not missing, f"Archive missing files: {missing}"


# =============================================================================
# TEST 6: app.py does not call _build_legacy_brain or reference agents.*
# =============================================================================
def test_app_py_has_no_brain_a_calls():
    """app.py must not reference _build_legacy_brain, _get_web_agent, or from agents."""
    app_src = (BACKEND_ROOT / "app.py").read_text(encoding="utf-8")
    forbidden = ["_build_legacy_brain(", "_get_web_agent(", "from agents ", "import agents"]
    violations = [f for f in forbidden if f in app_src]
    assert not violations, (
        f"app.py still references Brain A: {violations}"
    )


# =============================================================================
# TEST 7: production_langgraph_adapter.py has no active legacy_brain references
# =============================================================================
def test_adapter_has_no_active_legacy_brain_refs():
    """production_langgraph_adapter.py must not have active (non-comment) legacy_brain code."""
    src = (BACKEND_ROOT / "production_langgraph_adapter.py").read_text(encoding="utf-8")
    active_lines = [
        line for line in src.splitlines()
        if "legacy_brain" in line and not line.strip().startswith("#")
    ]
    assert not active_lines, (
        f"Active legacy_brain code remains in production_langgraph_adapter.py:\n"
        + "\n".join(active_lines)
    )


# =============================================================================
# TEST 8: Rollback dry-run succeeds (no -Execute flag — safe)
# =============================================================================
def test_rollback_dry_run_succeeds():
    """Rollback script dry-run must complete with exit code 0."""
    rollback_script = BACKEND_ROOT / "archive" / "brain_a_nexus" / "rollback_brain_a.ps1"
    assert rollback_script.exists(), f"Rollback script missing: {rollback_script}"

    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(rollback_script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Rollback dry-run exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
    assert "DRY-RUN COMPLETE" in result.stdout, (
        f"Expected DRY-RUN COMPLETE in output:\n{result.stdout}"
    )
    assert "Archive integrity: VERIFIED" in result.stdout


# =============================================================================
# TEST 9: core/intelligence_contracts.py re-exports all original fields
# =============================================================================
def test_contracts_field_parity():
    """BrainResult and contract types must retain their original fields."""
    from core.intelligence_contracts import BrainResult, DelegationType, DelegationDecision
    import dataclasses

    # BrainResult is a dataclass — check required fields
    fields = {f.name for f in dataclasses.fields(BrainResult)}
    required = {"request_id", "status", "task", "decision"}
    missing = required - fields
    assert not missing, f"BrainResult missing fields: {missing}"

    # DelegationType must have DIRECT
    assert hasattr(DelegationType, "DIRECT"), "DelegationType.DIRECT missing"


# =============================================================================
# TEST 10: No live production .py file (outside archive) imports agents.*
# =============================================================================
def test_no_live_code_imports_agents():
    """Zero live Python files outside archive/ must import from agents.*"""
    violations = []
    for py_file in BACKEND_ROOT.rglob("*.py"):
        rel = py_file.relative_to(BACKEND_ROOT)
        parts = rel.parts
        # Skip archive, __pycache__, and this test file itself
        # (which contains string literals like "from agents" in assert messages)
        if "archive" in parts or "__pycache__" in parts:
            continue
        if py_file.name == "test_brain_b_standalone.py":
            continue
        content = py_file.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ("from agents" in line or "import agents" in line or
                    "agents.brain" in line or "agents.models" in line or
                    "agents.registry" in line or "agents.orchestrator" in line):
                violations.append(f"{py_file}:{lineno}: {line.rstrip()}")
    assert not violations, (
        "Live code still imports Brain A agents.*:\n" + "\n".join(violations)
    )
