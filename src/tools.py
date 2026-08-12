"""The tool layer: every capability the agent has is a registered tool with a schema.

Interview points:
  * This is real function calling (the model picks a tool + arguments), not free-form
    code-gen. Constrained tools are safer and more predictable than "write any pandas."
  * I keep ONE powerful escape-hatch tool (run_analysis_code, sandboxed) alongside
    narrow, safe tools -- the tradeoff between flexibility and control, made explicit.
  * MCP tools register through the same interface, so the agent can't tell a local tool
    from a remote MCP one. That uniformity is the whole point of MCP.
"""

from dataclasses import dataclass
from typing import Callable
import pandas as pd

from sandbox import run_pandas


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON schema
    fn: Callable              # (df, **args) -> str

    def schema(self) -> dict:
        """OpenAI-style tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def call(self, name: str, args: dict, df: pd.DataFrame) -> str:
        if name not in self._tools:
            return f"error: unknown tool `{name}`"
        return self._tools[name].fn(df, **args)


# ---- local tools -------------------------------------------------------------

def _aggregate(df: pd.DataFrame, group_by: str, metric: str, agg: str = "mean") -> str:
    if group_by not in df.columns or metric not in df.columns:
        return f"error: unknown column(s). available: {list(df.columns)}"
    out = df.groupby(group_by)[metric].agg(agg).round(2).to_dict()
    return f"{agg} of {metric} by {group_by}: {out}"


def _run_code(df: pd.DataFrame, code: str) -> str:
    """The escape hatch: sandboxed arbitrary pandas. Guardrailed in sandbox.py."""
    status, payload = run_pandas(code, df)
    return f"{status}: {payload}"


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(Tool(
        name="aggregate",
        description="Aggregate a metric grouped by a column (safe, no code execution).",
        parameters={
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "description": "column to group by"},
                "metric": {"type": "string", "description": "numeric column to aggregate"},
                "agg": {"type": "string", "enum": ["mean", "max", "min", "std", "count"]},
            },
            "required": ["group_by", "metric"],
        },
        fn=_aggregate,
    ))
    reg.register(Tool(
        name="run_analysis_code",
        description="Run arbitrary pandas for complex analysis. Assign the answer to "
                    "`result`. Use only when the narrow tools can't express the question.",
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        fn=_run_code,
    ))
    return reg
