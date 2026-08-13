# GPU Insight Agent v2 — a robust agentic system

A spec-driven, tool-calling, MCP-integrated analysis agent that surfaces grounded
insights from GPU performance telemetry — built to demonstrate the full modern agentic
stack, with every concept in one clear place and all of it composing into one flow.

This is v2 of the earlier prototype. v1 showed "how to build an agent loop." v2 shows
"how to build a *production-shaped* agentic system."

## The flow (one coherent pipeline)

```
                    ┌─────────── constitution.md (runtime agent context)
   spec.yaml ──► LOAD ─► PROFILE ─► PLAN ─┐         spec = source of truth
   (contract)          (deterministic)    │  (plan-and-execute: N goals up front)
                                          ▼
                            ┌──── for each goal ────┐
                            │  ACT  (ReAct loop):   │  model picks a TOOL ─► HOOK fires
                            │   tool ─► GUARDRAIL ─► │  ─► sandbox executes ─► observe ─┐
                            │   repeat until answer  │◄────────────────────────────────┘
                            │  GROUND ─► output GUARDRAIL (must be grounded)            │
                            └───────────────────────┘                                  │
                                          ▼                                            │
                       MEMORY (persist) ─► APPROVE (human gate hook) ─► REPORT         │
                                          ▲                                            │
                          TRACER meters every step + tokens ◄──────────────────────────┘
```

## Concepts covered in prototype

| Concept covered | File | Wwhat it does |
|---|---|---|
| **Spec** (spec-driven) | `specs/gpu_analysis.spec.yaml` + `src/spec.py` | Versioned task contract, validated at startup. |
| **CLAUDE.md** (dev-time context) | `CLAUDE.md` | How coding agents build *this repo*. |
| **Runtime constitution** | `constitution.md` | How the analysis agent *behaves*. (Two different constitutions.) |
| **Calling a tool** | `src/tools.py` + orchestrator ACT loop | Real function-calling with JSON schemas, not code-gen. |
| **Calling an MCP server** | `src/mcp_server.py` + `src/mcp_client.py` | FastMCP server (tool + resource); sync facade over the async client. |
| **Guardrail** | `src/guardrails.py` | Input (PII/scope), tool-arg, and output (grounding) gates. |
| **Hook** | `src/hooks.py` | Lifecycle callbacks: logging, cost, human-approval gate. |
| **TDD loop** | `tests/` (dev-time) + orchestrator retry/validate (runtime) | Test-first for safety-critical code; generate > validate > retry at runtime. |
| **Eval set** | `evals/eval_set.yaml` + `evals/run_evals.py` | Golden cases with deterministic ground truth + scoring. |
| **Memory** (long-term) | `src/memory.py` | Persists insights; fixes v1's weak cross-step feedback. |
| **Observability** | `src/observability.py` | Full trajectory trace + token/cost accounting. |
| **Orchestration** | `src/orchestrator.py` | Explicit state machine; plan-and-execute + ReAct hybrid. |

## Build order (adding one layer at a time)

1. **Spec** (`spec.py`) — load and validate the contract. Everything reads from it.
2. **Tools** (`tools.py`) — register capabilities with schemas; see function-calling.
3. **Orchestrator** (`orchestrator.py`) — the state machine.
4. **Guardrails + Hooks** — wire the safety/lifecycle path into ACT.
5. **Memory + Observability** — persistence and tracing.
6. **MCP** (`mcp_server.py`, `mcp_client.py`) — add external domain-knowledge tools.
7. **Evals + Tests** — lock it down so nothing regresses.

## Ollama setup (fully local option)
If you want Option B below (no API key), install and start Ollama first:
```bash
curl -fsSL https://ollama.com/install.sh | sh   # install
systemctl status ollama 2>&1 || ollama serve &  # make sure the server is running
ollama pull llama3.1                            # pull the model
curl http://localhost:11434/api/tags            # sanity check
```

## Create virtual environment if desired
```bash
python3 -m venv ~/gpu-insight-agent-v2-env
source ~/gpu-insight-agent-v2-env/bin/activate
```
- Deactive when done
```bash
deactivate
```

## Run it

```bash
pip install -r requirements.txt

# No API key needed — these prove the deterministic + safety + eval machinery:
pytest -q                          # 8 TDD tests (sandbox, guardrails, spec)
python -m evals.run_evals          # 3 ground-truth eval cases

# MCP handshake (in-memory, no subprocess) — check to see if its wired:
python -c "import asyncio,sys; sys.path.insert(0,'src'); from fastmcp import Client; \
from mcp_server import mcp; \
asyncio.run((lambda: (lambda c: None)(Client(mcp)))())" 2>/dev/null; echo "see README for the full MCP test"

# Full agent (needs a model): OpenAI, or set OPENAI_BASE_URL for local Ollama/vLLM
export OPENAI_API_KEY=sk-...
python main.py                     # or:  python main.py --mcp
```

## The plan-and-execute vs. ReAct point (be ready to explain this)
Top level is **plan-and-execute**: the planner emits all N analytical goals up front from
the spec + memory. Inside each goal is a **ReAct** loop: the model picks a tool, the tool
runs (through hooks + guardrails), the observation feeds back, repeat until it answers or
hits the per-goal tool budget. Plan once at the top, react within a step — the common
production shape. (v1 was pure iterative/ReAct with a weak feedback signal; v2 adds real
planning and memory.)

## Some Caveats
- **Sandbox is prototype-grade**, not a boundary for adversarial code. For Production: a
  container with no network, read-only FS, seccomp, cgroup limits, or a hosted executor.
- **MCP SDK is churning** (the `mcp` package hit v2 in 2026, renaming FastMCP->MCPServer).
  This uses standalone `fastmcp`, verified on 3.4.6 - pin it and check current docs.
- **Memory is a JSON file**; production is a vector store for semantic recall of past analyses.
- **Grounding check is exact-match** on executed code; a real version would normalize and
  verify the *result* is actually reflected in the claim, not just that code ran.
- **Eval graders are structural**. A fuller suite adds semantic
  scoring (LLM-as-judge, validated against human labels) and runs in CI.

## One level up (how I'd productionize)
- LangGraph for the state machine with checkpointing + durable human-in-the-loop 
- Vector store memory 
- OpenTelemetry traces to Langfuse/Phoenix 
- MCP over HTTP with auth 
- Warehouse + lineage for the data layer 
- Evals gated in CI 
```
