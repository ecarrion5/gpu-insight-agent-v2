"""Observability: a structured trace of the whole run + token/cost accounting.

Main points:
You cannot improve, debug, or cost-control what you don't measure. Every step appends
to a trace you can replay; every LLM call meters tokens. This is the systems-level
version of the token-cost concern -- you don't just worry about it, you instrument it.

Prototype: in-memory trace + JSON dump. Production: OpenTelemetry spans to Langfuse /
Phoenix / Grafana, tied back to eval cases.
"""

import json
import time
from pathlib import Path


class Tracer:
    def __init__(self):
        self.events: list[dict] = []
        self.tokens = 0
        self._t0 = time.time()

    def event(self, kind: str, **data):
        self.events.append({"t": round(time.time() - self._t0, 3), "kind": kind, **data})

    def add_tokens(self, n: int):
        self.tokens += n

    def estimated_cost(self, per_1k: float = 0.0005) -> float:
        return round(self.tokens / 1000 * per_1k, 4)

    def dump(self, path: str = "trace.json"):
        Path(path).write_text(json.dumps(
            {"events": self.events, "tokens": self.tokens,
             "est_cost_usd": self.estimated_cost()}, indent=2))

    def summary(self) -> str:
        kinds = {}
        for e in self.events:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        return (f"{len(self.events)} events {dict(kinds)} | "
                f"~{self.tokens} tokens | ~${self.estimated_cost()}")
