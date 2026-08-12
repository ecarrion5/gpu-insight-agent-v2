# CLAUDE.md — project constitution for coding agents

> This file is **development-time context**. When I build or extend this repo *with*
> Claude Code (or Cursor/Codex), the agent loads this so it follows our conventions
> instead of reinventing them. It governs how code gets WRITTEN.
>
> Do not confuse it with `constitution.md`, which is **runtime context** the analysis
> agent loads into its own prompt to govern how it BEHAVES. Two different "constitutions"
> for two different agents — being precise about that distinction is the point.

## What this project is
A spec-driven, tool-calling analysis agent that surfaces grounded insights from GPU
performance telemetry. See `specs/gpu_analysis.spec.yaml` for the task contract.

## Architecture (respect these boundaries)
- `src/spec.py` — the versioned task contract. The spec is the source of truth.
- `src/orchestrator.py` — the state machine. All control flow lives here, nowhere else.
- `src/tools.py` — every capability the agent has is a registered tool with a schema.
- `src/guardrails.py`, `src/hooks.py` — safety and lifecycle. Never bypass them.
- `src/sandbox.py` — the ONLY place LLM-generated code executes. Never `exec()` elsewhere.
- MCP tools come from `src/mcp_server.py` via `src/mcp_client.py`.

## Conventions
- Python 3.11+, type hints everywhere, Pydantic for all model I/O and validation.
- No capability without a test in `tests/` and, if it affects output quality, an eval case.
- Temperature 0 for anything validated or grounded; higher only for exploration.
- Every tool call goes through the hook + guardrail path. No shortcuts.
- Keep the LLM behind `llm_client.py`. No SDK calls scattered through the codebase.

## Definition of done for any change
1. Tests pass (`pytest`).
2. Evals don't regress (`python -m evals.run_evals`).
3. New behavior is covered by a test and/or an eval case.
4. The spec still validates and still describes what the system does.

## What NOT to do
- Don't add a framework (LangGraph, etc.) without a clear reason; the hand-rolled
  orchestrator is intentional so control flow is fully visible.
- Don't let generated code touch the filesystem, network, or imports (see sandbox).
- Don't produce an insight that isn't grounded in an executed result.
