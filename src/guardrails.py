"""Guardrails: validation at the boundaries of the system. WHAT is allowed.

A guardrail inspects data and blocks or flags it. Contrast with hooks.py, which fire
AT lifecycle moments to observe/act. These are separate things:
  * Guardrail  = a gate on content ("is this allowed to pass?").
  * Hook       = a callback at an event ("something happened; react").

Three guardrails here: input (scope/PII), tool-argument (before a tool runs), and
output (grounding -- the most important one for a data agent).
"""

import re
from schemas import Insight
from spec import Spec


class GuardrailViolation(Exception):
    pass


# ---- input guardrail ---------------------------------------------------------

_PII_HINTS = re.compile(r"\b(ssn|social security|email|phone|patient|name)\b", re.I)


def check_input(goal: str, spec: Spec) -> None:
    """Reject a planned goal that violates scope or the no-PII constraint."""
    if not spec.constraints.pii_allowed and _PII_HINTS.search(goal):
        raise GuardrailViolation(f"goal appears to request PII, disallowed by spec: {goal!r}")


# ---- tool-argument guardrail -------------------------------------------------

def check_tool_args(name: str, args: dict, allowed_columns: list[str]) -> None:
    """Cheap pre-execution checks so a bad call fails before it costs anything."""
    for key in ("group_by", "metric"):
        if key in args and args[key] not in allowed_columns:
            raise GuardrailViolation(
                f"{name}: column {args[key]!r} not in dataset {allowed_columns}"
            )


# ---- output guardrail (the important one) ------------------------------------

def check_grounding(insight: Insight, executed_results: set[str], spec: Spec) -> None:
    """An insight is only valid if its supporting code actually ran and produced the
    result it cites. This is the anti-hallucination gate."""
    if not spec.constraints.require_grounding:
        return
    key = insight.supporting_code.strip()
    if key not in executed_results:
        raise GuardrailViolation(
            "ungrounded insight: supporting_code was never executed this run"
        )
