"""An MCP server exposing domain knowledge the agent needs: a metric glossary and a
data catalog. Run standalone:  python src/mcp_server.py

Interview points:
  * MCP standardizes how an agent gets external tools/context. This same server could be
    consumed by Claude Desktop, Cursor, or my agent -- write once, use anywhere.
  * I expose a `resource` (readable context: the catalog) AND a `tool` (a callable:
    glossary lookup). Knowing the difference between MCP resources, tools, and prompts
    is the vocabulary that shows you actually understand the protocol.

NOTE (version churn): the `mcp` package went to v2 in 2026 and renamed FastMCP ->
MCPServer. This uses the standalone `fastmcp` package, which keeps the stable API.
Pin it (see requirements.txt) and verify against current docs.
"""

from fastmcp import FastMCP

mcp = FastMCP("gpu-domain-knowledge")

_GLOSSARY = {
    "util_pct": "GPU compute utilization, 0-100%. Sustained high util with rising temp "
                "can indicate cooling degradation.",
    "temp_c": "Die temperature in Celsius. Thermal throttling risk climbs past ~85C.",
    "power_w": "Board power draw in watts. Perf-per-watt is the key efficiency metric.",
}

_CATALOG = {
    "dataset": "gpu_perf_multiyear",
    "years": [2021, 2022, 2023, 2024, 2025],
    "models": ["MI250", "MI300X", "MI325X"],
    "note": "Yearly files had schema drift; column names were normalized on load.",
}


@mcp.tool
def define_metric(metric: str) -> str:
    """Return the domain definition and analysis caveats for a GPU metric."""
    return _GLOSSARY.get(metric, f"No glossary entry for '{metric}'.")


@mcp.resource("catalog://gpu")
def data_catalog() -> dict:
    """Readable context: what the dataset contains."""
    return _CATALOG


if __name__ == "__main__":
    mcp.run()   # stdio transport by default
