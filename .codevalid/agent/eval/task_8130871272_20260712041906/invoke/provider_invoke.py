from __future__ import annotations

import copy
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_93tk5upn"
DEFAULT_MODELS = ["gpt-5.1", "claude-haiku-4-5"]

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


class ToolTraceCallback:
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> None:
        name = (
            serialized.get("name")
            or serialized.get("kwargs", {}).get("name")
            or serialized.get("id")
            or "tool"
        )
        args: dict[str, Any]
        try:
            parsed = json.loads(input_str) if isinstance(input_str, str) else input_str
            if isinstance(parsed, dict):
                args = parsed
            else:
                args = {"input": parsed}
        except Exception:
            args = {"input": input_str}
        self.tool_calls.append({"toolName": name, "args": args})


def _extract_vars(options: Any, context: Any) -> dict[str, Any]:
    options = options or {}
    context = context or {}
    if isinstance(options, dict) and isinstance(options.get("vars"), dict):
        return options["vars"]
    if isinstance(context, dict) and isinstance(context.get("vars"), dict):
        return context["vars"]
    return {}


def _select_model(options: Any, context: Any, vars_: dict[str, Any]) -> str:
    options = options or {}
    context = context or {}
    if isinstance(options, dict):
        config = options.get("config") or {}
        if isinstance(config, dict) and config.get("model"):
            return str(config["model"])
        if options.get("model"):
            return str(options["model"])
    if vars_.get("model"):
        return str(vars_["model"])
    if DEFAULT_MODELS:
        return DEFAULT_MODELS[0]
    return "gpt-5.1"


def _load_model_config(model: str) -> dict[str, Any]:
    providers_dir = Path(WORKSPACE_ROOT) / ".codevalid" / "agent" / "eval" / "task_8130871272_20260712041906" / "invoke" / "providers"
    yaml_path = providers_dir / f"{model}.yaml"
    config: dict[str, Any] = {"model": model}
    if not yaml_path.exists():
        return config
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(yaml_path.read_text())
        if isinstance(data, dict):
            merged = dict(data)
            merged["model"] = model
            return merged
    except Exception:
        pass
    return config


def _normalize_output(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if isinstance(result.get("output"), str):
            return result["output"]
        if isinstance(result.get("content"), str):
            return result["content"]
        messages = result.get("messages")
        if isinstance(messages, list):
            parts: list[str] = []
            for message in messages:
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(message, dict) and isinstance(message.get("content"), str):
                    parts.append(message["content"])
            if parts:
                return "\n".join(parts)
        return json.dumps(result, default=str)
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    try:
        return json.dumps(result, default=str)
    except Exception:
        return str(result)


def setup_dependencies(precondition: Any, config: dict[str, Any]) -> None:
    tools_module = importlib.import_module("tools")
    if not hasattr(tools_module, "ORDERS") or not isinstance(tools_module.ORDERS, dict):
        return

    tools_module.ORDERS.clear()

    if not precondition:
        return

    data = precondition
    if isinstance(precondition, list):
        merged: dict[str, Any] = {}
        for item in precondition:
            if isinstance(item, dict):
                merged.update(item)
        data = merged

    orders_payload = None
    if isinstance(data, dict):
        if isinstance(data.get("orders"), dict):
            orders_payload = data.get("orders")
        elif isinstance(data.get("ORDERS"), dict):
            orders_payload = data.get("ORDERS")

    if orders_payload is None:
        return

    for order_id, order_value in copy.deepcopy(orders_payload).items():
        tools_module.ORDERS[str(order_id)] = order_value


def call_api(prompt: str, options: Any, context: Any) -> dict[str, Any]:
    options = options or {}
    context = context or {}
    vars_ = _extract_vars(options, context)
    model = _select_model(options, context, vars_)
    config = _load_model_config(model)
    config["model"] = model

    os.environ["LITELLM_BASE_URL"] = os.environ["LITELLM_BASE_URL"]
    os.environ["LITELLM_API_KEY"] = os.environ["LITELLM_API_KEY"]

    previous_model_name = os.environ.get("MODEL_NAME")
    os.environ["MODEL_NAME"] = model

    precondition = vars_.get("precondition")
    setup_dependencies(precondition, config)

    agent_module = importlib.import_module("agent")
    tools_module = importlib.import_module("tools")

    callback = ToolTraceCallback()

    originals: dict[str, Any] = {}
    wrapped_targets = ["lookup_order", "refund_order"]

    def _make_wrapper(name: str, tool_obj: Any):
        func = getattr(tool_obj, "func", None)
        if callable(func):
            if getattr(func, "_codevalid_wrapped", False):
                return tool_obj

            def wrapped(*args: Any, **kwargs: Any) -> Any:
                if kwargs:
                    payload = dict(kwargs)
                elif len(args) == 1:
                    payload = {"order_id": args[0]}
                else:
                    payload = {"input": list(args)}
                callback.tool_calls.append({"toolName": name, "args": payload})
                return func(*args, **kwargs)

            wrapped._codevalid_wrapped = True  # type: ignore[attr-defined]
            tool_obj.func = wrapped
            return tool_obj

        if callable(tool_obj):
            if getattr(tool_obj, "_codevalid_wrapped", False):
                return tool_obj

            def wrapped_callable(*args: Any, **kwargs: Any) -> Any:
                if kwargs:
                    payload = dict(kwargs)
                elif len(args) == 1:
                    payload = {"order_id": args[0]}
                else:
                    payload = {"input": list(args)}
                callback.tool_calls.append({"toolName": name, "args": payload})
                return tool_obj(*args, **kwargs)

            wrapped_callable._codevalid_wrapped = True  # type: ignore[attr-defined]
            return wrapped_callable

        return tool_obj

    try:
        for name in wrapped_targets:
            if hasattr(tools_module, name):
                original = getattr(tools_module, name)
                originals[f"tools.{name}"] = original
                wrapped = _make_wrapper(name, original)
                setattr(tools_module, name, wrapped)
                if hasattr(agent_module, name):
                    originals[f"agent.{name}"] = getattr(agent_module, name)
                    setattr(agent_module, name, wrapped)

        invoke_fn = getattr(agent_module, "invoke")
        result = invoke_fn(prompt, callbacks=[callback])
        response: dict[str, Any] = {"output": _normalize_output(result)}
        if callback.tool_calls:
            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in callback.tool_calls:
                key = json.dumps(item, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            response["toolCalls"] = deduped
        return response
    finally:
        for key, original in originals.items():
            module_name, attr = key.split(".", 1)
            module = agent_module if module_name == "agent" else tools_module
            setattr(module, attr, original)
        if previous_model_name is None:
            os.environ.pop("MODEL_NAME", None)
        else:
            os.environ["MODEL_NAME"] = previous_model_name
