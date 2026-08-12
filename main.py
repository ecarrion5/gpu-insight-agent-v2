"""Entrypoint. Wires the whole stack and runs one analysis pass.

Run:  python main.py            (uses OpenAI or a local OpenAI-compatible endpoint)
      python main.py --mcp      (also connect the MCP server for domain-knowledge tools)

The __main__ guard is required (sandbox spawns processes).
"""

import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC))

from spec import load_spec
from make_sample_data import build_dataset
from llm_client import LLMClient
from tools import build_default_registry
from hooks import HookManager, log_tool_call, human_approval_gate
from memory import InsightMemory
from observability import Tracer
from orchestrator import Orchestrator


def main(use_mcp: bool = False) -> None:
    spec = load_spec(Path(__file__).parent / "specs" / "gpu_analysis.spec.yaml")
    df = build_dataset()
    constitution = (Path(__file__).parent / "constitution.md").read_text()

    registry = build_default_registry()
    hooks = HookManager()
    hooks.register("post_tool_call", log_tool_call)
    hooks.register("pre_report", human_approval_gate)
    memory = InsightMemory()
    tracer = Tracer()

    mcp = None
    if use_mcp:
        from mcp_client import MCPToolProvider
        mcp = MCPToolProvider(str(SRC / "mcp_server.py"))
        print(f"MCP tools available: {mcp.list_tool_names()}")

    orch = Orchestrator(LLMClient(), registry, hooks, memory, tracer, constitution, mcp)
    print(f"Running spec '{spec.name}' over {len(df):,} rows\n")

    insights = orch.run(spec, df)

    print("\n=== GROUNDED INSIGHTS ===")
    for i, ins in enumerate(insights, 1):
        print(f"{i}. [{ins.confidence}/{ins.novelty}] {ins.finding}")
        print(f"   evidence: {ins.result_summary}")
    print(f"\ntrace: {tracer.summary()}")
    tracer.dump()
    if mcp:
        mcp.close()


if __name__ == "__main__":
    main(use_mcp="--mcp" in sys.argv)
