"""Hooks: callbacks fired AT lifecycle moments. Mirrors the Claude Code hooks idea.

A hook doesn't decide what's allowed (that's a guardrail) -- it reacts to an event:
log it, meter it, or pause for human approval. Registering behavior this way keeps the
orchestrator clean: cross-cutting concerns (observability, cost, approval) live here,
not tangled into the control flow.

Events: 'pre_tool_call', 'post_tool_call', 'pre_report'.
"""

from collections import defaultdict
from typing import Callable


class HookManager:
    def __init__(self):
        self._hooks: dict[str, list[Callable]] = defaultdict(list)

    def register(self, event: str, fn: Callable) -> None:
        self._hooks[event].append(fn)

    def fire(self, event: str, **ctx):
        for fn in self._hooks[event]:
            fn(**ctx)


# ---- example hooks -----------------------------------------------------------

def log_tool_call(**ctx):
    print(f"  [hook] tool={ctx.get('name')} args={ctx.get('args')}")


def human_approval_gate(**ctx):
    """A human-in-the-loop checkpoint. In a prototype this is a console prompt; in
    production it's a UI approval step or a Slack message. The point is the GATE exists."""
    insights = ctx.get("insights", [])
    print(f"\n  [approval] {len(insights)} insights ready to finalize.")
    # Non-interactive default = approve; flip to input() for a real gate.
    # resp = input("  approve report? [y/N] ")
    # if resp.strip().lower() != "y":
    #     raise SystemExit("report rejected by human reviewer")
