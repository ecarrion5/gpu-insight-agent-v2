"""Model access, isolated to one module. Adds tool-calling support and a MockLLM.

Interview points:
  * Single access point -> swapping OpenAI for local vLLM/Ollama or a gateway is a
    one-line base_url change.
  * MockLLM lets the whole agent, evals, and tests run with NO API key and NO network,
    deterministically. Testability is a design requirement, not an afterthought.
"""

import os
import json
from openai import OpenAI


class LLMClient:
    def __init__(self, model: str | None = None):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", "not-needed-for-local"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.0):
        """Returns the raw message object so the caller can inspect tool_calls."""
        kwargs = {"model": self.model, "temperature": temperature, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs).choices[0].message


class MockLLM:
    """A scriptable stand-in. You queue up responses; it returns them in order.
    Each scripted item is either {'content': str} or
    {'tool_calls': [{'name': str, 'arguments': dict}]}."""

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.model = "mock"

    def chat(self, messages, tools=None, temperature=0.0):
        from types import SimpleNamespace
        item = self._script.pop(0)
        if "tool_calls" in item:
            calls = [
                SimpleNamespace(
                    id=f"call_{i}",
                    function=SimpleNamespace(
                        name=c["name"], arguments=json.dumps(c["arguments"])
                    ),
                )
                for i, c in enumerate(item["tool_calls"])
            ]
            return SimpleNamespace(content=None, tool_calls=calls)
        return SimpleNamespace(content=item["content"], tool_calls=None)
