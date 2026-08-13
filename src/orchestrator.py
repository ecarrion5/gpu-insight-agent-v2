"""The orchestrator: an explicit state machine that ties every piece together.

Control-flow design (ties back to the plan-and-execute vs ReAct distinction):
  * TOP LEVEL is plan-and-execute: a Planner reads the spec + memory and emits N goals
    up front.
  * INSIDE each goal is a ReAct tool-calling loop: the model picks a tool, we execute it
    (through hooks + guardrails), feed the observation back, and repeat until it produces
    a grounded answer or hits the per-goal tool budget.
That hybrid -- plan once at the top, react within a step -- is the common production
shape, and being able to name it is the point.

States: LOAD -> PROFILE -> PLAN -> for each goal[ ACT (ReAct loop) -> GROUND ] -> APPROVE -> REPORT
"""

import json
import pandas as pd

from spec import Spec
from schemas import Insight
from profiler import profile, compact_schema
from tools import ToolRegistry
from guardrails import check_input, check_tool_args, check_grounding, GuardrailViolation
from hooks import HookManager
from memory import InsightMemory
from observability import Tracer


class Orchestrator:
    def __init__(self, llm, registry: ToolRegistry, hooks: HookManager,
                 memory: InsightMemory, tracer: Tracer, constitution: str,
                 mcp=None):
        self.llm = llm
        self.registry = registry
        self.hooks = hooks
        self.memory = memory
        self.tracer = tracer
        self.constitution = constitution
        self.mcp = mcp  # optional MCPToolProvider

    # -- PLAN (top-level, plan-and-execute) ------------------------------------
    def _plan(self, spec: Spec, schema: str) -> list[str]:
        recall = self.memory.recent_findings()
        sys = (self.constitution + "\n\nYou are planning. Given the goal and schema, "
               "output a JSON list of distinct analytical questions to pursue. "
               "Avoid anything similar to the prior findings.")
        user = (f"GOAL: {spec.goal}\nSCHEMA:\n{schema}\n"
                f"PRIOR FINDINGS (don't repeat): {recall}\n"
                f"Output exactly {spec.constraints.max_insights} questions as a JSON list of "
                f'plain strings, e.g. ["question one", "question two"]. Do not wrap each '
                f"question in an object.")
        msg = self.llm.chat([{"role": "system", "content": sys},
                             {"role": "user", "content": user}],
                            temperature=spec.constraints.temperature_planning)
        self.tracer.event("plan")
        raw = json.loads(msg.content[msg.content.find("["):msg.content.rfind("]") + 1])
        goals = [_normalize_goal(g) for g in raw[: spec.constraints.max_insights]]
        return goals

    # -- ACT (per-goal ReAct tool-calling loop) --------------------------------
    def _act(self, spec: Spec, goal: str, df: pd.DataFrame) -> tuple[str, set[str]]:
        cols = list(df.columns)
        messages = [
            {"role": "system", "content": self.constitution +
             "\nUse tools to answer the question. When done, reply with the final "
             "numeric finding in plain text."},
            {"role": "user", "content": f"Question: {goal}\nColumns: {cols}"},
        ]
        executed: set[str] = set()
        for _ in range(spec.constraints.max_tool_calls_per_goal):
            msg = self.llm.chat(messages, tools=self.registry.schemas(),
                                temperature=0.0)
            if not getattr(msg, "tool_calls", None):
                return (msg.content or "", executed)      # model produced final answer

            messages.append({"role": "assistant", "content": msg.content,
                             "tool_calls": [_tc_to_dict(tc) for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                self.hooks.fire("pre_tool_call", name=name, args=args)
                try:
                    check_tool_args(name, args, cols)
                    result = self.registry.call(name, args, df)
                    if name == "run_analysis_code":
                        executed.add(args.get("code", "").strip())
                except GuardrailViolation as e:
                    result = f"blocked by guardrail: {e}"
                self.hooks.fire("post_tool_call", name=name, args=args, result=result)
                self.tracer.event("tool_call", name=name)

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return ("(tool budget exhausted)", executed)

    # -- GROUND ----------------------------------------------------------------
    def _ground(self, spec: Spec, goal: str, answer: str, executed: set[str]) -> Insight | None:
        sys = (self.constitution + "\nSummarize into JSON matching: finding, "
               "supporting_question, supporting_code, result_summary, confidence "
               "(low|medium|high), novelty (expected|surprising). supporting_code must be "
               "code you actually ran.")
        user = f"QUESTION: {goal}\nFINAL ANSWER: {answer}\nEXECUTED CODE: {list(executed)}"
        msg = self.llm.chat([{"role": "system", "content": sys},
                             {"role": "user", "content": user}],
                            temperature=spec.constraints.temperature_grounding)
        try:
            data = json.loads(msg.content[msg.content.find("{"):msg.content.rfind("}") + 1])
            insight = Insight(**data)
            check_grounding(insight, executed, spec)      # output guardrail
            self.tracer.event("insight_grounded")
            return insight
        except (ValueError, GuardrailViolation) as e:
            self.tracer.event("insight_rejected", reason=str(e)[:80])
            return None

    # -- RUN (drives the states) -----------------------------------------------
    def run(self, spec: Spec, df: pd.DataFrame) -> list[Insight]:
        schema = compact_schema(profile(df))              # PROFILE (deterministic)
        goals = self._plan(spec, schema)                  # PLAN
        insights: list[Insight] = []
        for goal in goals:                                # per goal
            try:
                check_input(goal, spec)                   # input guardrail
            except GuardrailViolation:
                continue
            answer, executed = self._act(spec, goal, df)  # ACT (ReAct loop)
            insight = self._ground(spec, goal, answer, executed)  # GROUND
            if insight:
                insights.append(insight)
                self.memory.add(insight)                  # long-term memory
        if spec.human_in_the_loop.approve_before_report:  # APPROVE (hook gate)
            self.hooks.fire("pre_report", insights=insights)
        return insights                                   # REPORT


def _tc_to_dict(tc) -> dict:
    return {"id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


def _normalize_goal(g) -> str:
    """The planner is asked for a JSON list of strings but sometimes wraps each
    question in an object instead (e.g. {"question": "..."}). Accept that shape
    too rather than letting a dict reach the string-only guardrails/prompts."""
    if isinstance(g, str):
        return g
    if isinstance(g, dict):
        for key in ("question", "goal", "text"):
            if isinstance(g.get(key), str):
                return g[key]
    raise ValueError(f"planner returned a goal in an unexpected shape: {g!r}")
