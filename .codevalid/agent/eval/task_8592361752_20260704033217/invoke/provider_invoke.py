"""Promptfoo provider — generated for agent root invoke."""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
except ImportError:
    BaseCallbackHandler = object  # type: ignore[misc,assignment]

_STATE: dict[str, Any] = {}


class _ToolCallCaptureHandler(BaseCallbackHandler):
    """Record LangChain tool invocations for promptfoo llm-rubric grading."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []
        self._pending: dict[str, str] | None = None

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name", "unknown")
        tool_input = inputs if inputs is not None else input_str
        self._pending = {"name": str(name), "input": str(tool_input)}

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        if self._pending is not None:
            self.calls.append({**self._pending, "output": str(output)})
            self._pending = None

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        if self._pending is not None:
            self.calls.append({**self._pending, "output": f"error: {error}"})
            self._pending = None


def _format_tool_trace(calls: list[dict[str, str]]) -> str:
    if not calls:
        return ""
    lines = ["", "--- Tool calls ---"]
    for index, call in enumerate(calls, start=1):
        lines.append(f"{index}. {call['name']}({call['input']})")
        lines.append(f"   Result: {call['output']}")
    return "\n".join(lines)


def _parse_hints_into_orders(hints: list) -> dict[str, dict[str, str]]:
    """Parse precondition hint strings into an orders dict for tools.ORDERS."""
    orders: dict[str, dict[str, str]] = {}
    for hint in hints:
        if not isinstance(hint, str):
            continue
        # Match: "Order <ID> exists in system with status '<status>'"
        # Also handles "status 'shipped' or 'processing'" — use first status found.
        m = re.search(
            r"Order\s+(\S+)\s+exists\s+in\s+system\s+with\s+status\s+'([^']+)'",
            hint,
            re.IGNORECASE,
        )
        if m:
            order_id = m.group(1).strip()
            status = m.group(2).strip()
            orders[order_id] = {"status": status}
    return orders


def setup_dependencies(precondition: dict | None, config: dict | None) -> None:
    """Seed mock/tool state before invoking the agent."""
    global _STATE
    _STATE = dict(precondition or {})
    if config:
        _STATE.setdefault("config", config)

    # Resolve workspace root to import tools
    here = Path(__file__).resolve()
    workspace = here
    for _ in range(8):
        workspace = workspace.parent
        if (workspace / ".codevalid").is_dir():
            break

    agents_dir = str(workspace / "agents")
    if agents_dir not in sys.path:
        sys.path.insert(0, agents_dir)
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))

    try:
        tools_mod = importlib.import_module("tools")
        hints = []
        if precondition and isinstance(precondition, dict):
            hints = precondition.get("hints", [])
        seeded = _parse_hints_into_orders(hints)
        # Reset ORDERS to seeded data for this test; fall back to defaults when empty
        if seeded:
            tools_mod.ORDERS.clear()
            tools_mod.ORDERS.update(seeded)
        else:
            # Restore defaults so non-preconditioned tests still work
            tools_mod.ORDERS.clear()
            tools_mod.ORDERS.update({"123": {"status": "delivered"}, "456": {"status": "processing"}})
    except Exception:
        pass  # If tools module not yet importable, skip seeding


def _resolve_llm(config: dict):
    base_url = os.environ["LITELLM_BASE_URL"]
    api_key = os.environ["LITELLM_API_KEY"]
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("langchain_openai is required for agent eval") from exc
    return ChatOpenAI(
        model=config.get("model", "gpt-5.1"),
        base_url=base_url,
        api_key=api_key,
        temperature=config.get("temperature", 0),
    )


def _invoke_agent(llm, user_input: str) -> str:
    workspace = Path(__file__).resolve()
    for _ in range(8):
        workspace = workspace.parent
        if (workspace / ".codevalid").is_dir():
            break
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))
    agents_dir = str(workspace / "agents")
    if agents_dir not in sys.path:
        sys.path.insert(0, agents_dir)
    module = importlib.import_module("agent")
    target = getattr(module, "invoke", None)
    if target is None:
        raise RuntimeError("Agent entry invoke not found in agent")
    if hasattr(target, "invoke"):
        result = target.invoke({"input": user_input}, config={"configurable": {"llm": llm}})
        if isinstance(result, dict):
            return str(result.get("output", result))
        return str(result)
    capture = _ToolCallCaptureHandler()
    output = str(target(user_input, callbacks=[capture]))
    return f"{output}{_format_tool_trace(capture.calls)}"


def call_api(prompt: str, options: dict, context: dict) -> dict:
    config = options.get("config", {})
    vars_ = context.get("vars", {})
    setup_dependencies(vars_.get("precondition"), config)
    model = config.get("model")
    if model:
        os.environ["MODEL_NAME"] = model
    output = _invoke_agent(_resolve_llm(config), prompt)
    return {"output": output}
