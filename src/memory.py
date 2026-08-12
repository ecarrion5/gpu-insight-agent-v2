"""Agent memory: a persistent store of past insights.

This directly fixes the weak-feedback limitation of the v1 agent. By persisting prior
findings and injecting them into planning, the agent (a) doesn't repeat itself across
runs, and (b) can build on what it already knows. This is the difference between an
agent with working memory only and one with long-term memory.

Prototype uses a JSON file; production would be a vector store (semantic recall of
relevant past analyses) or a database.
"""

import json
from pathlib import Path
from schemas import Insight


class InsightMemory:
    def __init__(self, path: str = "memory.json"):
        self._path = Path(path)
        self._items: list[dict] = []
        if self._path.exists():
            self._items = json.loads(self._path.read_text())

    def add(self, insight: Insight) -> None:
        self._items.append(insight.model_dump())
        self._path.write_text(json.dumps(self._items, indent=2))

    def recent_findings(self, k: int = 10) -> list[str]:
        """Compact recall to inject into the planner's context (token-frugal)."""
        return [it["finding"] for it in self._items[-k:]]

    def __len__(self) -> int:
        return len(self._items)
