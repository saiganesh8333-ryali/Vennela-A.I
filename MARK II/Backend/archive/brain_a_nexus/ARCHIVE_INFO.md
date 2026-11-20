# Brain A NEXUS — Archive Record

## Identity

| Field | Value |
|---|---|
| Archive Name | `brain_a_nexus` |
| Original Module | `Backend/agents/` |
| Archive Path | `Backend/archive/brain_a_nexus/` |
| Project | Vennela AI 2.0 (MARK-II) |
| Archived By | ANTIGRAVITY — Migration Phase 4 |
| Migration Date | 2026-11-20 |
| Status | **ARCHIVED — NOT ACTIVE** |

## What This Is

Brain A is the original Vennela intelligence engine, code-named **NEXUS**. It
was the primary AI processing backend prior to the Brain B LangGraph migration.

Brain A comprised:

| File | Role |
|---|---|
| `brain.py` | `VennelaBrain` — top-level orchestration entry point |
| `models.py` | `DelegationType`, `DelegationDecision` — shared contracts (now in `core/intelligence_contracts.py`) |
| `orchestrator.py` | `AgentOrchestrator` — task routing and agent dispatch |
| `planner.py` | `VennelaPlanner` — task decomposition and planning |
| `reasoning.py` | `VennelaReasoningAdapter` — LLM reasoning wrapper |
| `registry.py` | `AgentRegistry` — agent registration and lookup |
| `__init__.py` | Package exports |
| `web_hunt_original/` | Original `WebHuntAgent` (now promoted to `web_intelligence/web_hunt/`) |

## Why It Was Archived

The Brain B (LangGraph) system (`vennela_langgraph` / `production_langgraph_adapter.py`)
was verified as the sole active intelligence engine. Brain A is no longer
imported, instantiated, or invoked by any active production code path.

Shared contracts (`BrainResult`, `DelegationType`, `DelegationDecision`) were
extracted to `Backend/core/intelligence_contracts.py` before archival.

The `WebHuntAgent` was promoted to `Backend/web_intelligence/web_hunt/` and
Brain A's original copy is preserved here as `web_hunt_original/`.

## Recovery

To restore Brain A, run the rollback script in DRY-RUN mode first:

```powershell
# DRY-RUN (safe — no changes):
.\archive\brain_a_nexus\rollback_brain_a.ps1

# EXECUTE actual restoration:
.\archive\brain_a_nexus\rollback_brain_a.ps1 -Execute
```

The rollback script:
- Verifies archive integrity before any file operation
- Restores all Brain A files to `Backend/agents/`
- Does NOT modify `app.py` or re-activate Brain A automatically
- Requires manual `app.py` update to re-enable Brain A

## Integrity

Verify archive integrity at any time:

```powershell
Set-Location "D:\Vennela A.I\MARK II\Backend"
Get-Content archive\brain_a_nexus\SHA256_MANIFEST.txt
```

## Protected Infrastructure (NOT archived — still active)

The following shared infrastructure was used by Brain A and remains active for Brain B:

- `Backend/llm_router/` — LLM provider routing
- `Backend/memory/` — Supabase memory tiers
- `Backend/conversation/` — Conversation management
- `Backend/automation/` — Automation engine
- `Backend/web_intelligence/` — Web research engines

> [!CAUTION]
> Do NOT permanently delete this archive directory.
> Brain A must remain recoverable at all times per migration policy.
