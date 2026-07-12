from __future__ import annotations

import copy
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from langchain_core.callbacks.base import BaseCallbackHandler


_WORKSPACE_ROOT = os.environ.get(
    "CODEVALID_WORKSPACE_ROOT",
    "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_00renm0v",
)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)


def _import_symbol(module_path: str, qualified_name: str):
    module = importlib.import_module(module_path)
    target = module
    for part in qualified_name.split("."):
        target = getattr(target, part)
    return module, target


def _extract_vars(options: dict[str, Any] | None, context: dict[str, Any] | None) -> dict[str, Any]:
    options = options or {}
    context = context or {}
    vars_ = options.get("vars")
    if isinstance(vars_, dict):
        return vars_
    vars_ = context.get("vars")
    if isinstance(vars_, dict):
        return vars_
    return {}


def _load_model_config(model: str) -> dict[str, Any]:
    config: dict[str, Any] = {"model": model}
    providers_dir = Path(_WORKSPACE_ROOT) / ".codevalid" / "agent" / "eval" / "task_8130871272_20260712041906" / "invoke" / "providers"
    model_path = providers_dir / f"{model}.yaml"
    if model_path.exists():
        with model_path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if isinstance(loaded, dict):
            if isinstance(loaded.get("config"), dict):
                config.update(loaded["config"])
            else:
                config.update(loaded)
    config["model"] = model
    config["apiBaseUrl"] = os.environ["LITELLM_BASE_URL"]
    config["apiKey"] = os.environ["LITELLM_API_KEY"]
    return config


def _select_model(options: dict[str, Any] | None, context: dict[str, Any] | None, vars_: dict[str, Any]) -> str:
    options = options or {}
    model = (
        ((options.get("config") or {}).get("model"))
        or options.get("model")
        or vars_.get("model")
        or "gpt-5.1"
    )
    return str(model)


def setup_dependencies(precondition: Any, config: dict[str, Any]):
    tools_module = importlib.import_module("tools")
    if hasattr(tools_module, "ORDERS") and isinstance(getattr(tools_module, "ORDERS"), dict):
        orders_store = getattr(tools_module, "ORDERS")
        orders_store.clear()
        if isinstance(precondition, dict):
            source_orders = precondition.get("orders")
            if isinstance(source_orders, dict):
                orders_store.update(copy.deepcopy(source_orders))
                return
        orders_store.update(
            {
                "123": {"status": "delivered"},
                "456": {"status": "processing"},
                "ORD-12345": {"status": "delivered"},
                "ORD-99999": {"status": "processing"},
                "ORD-54321": {"status": "delivered"},
            }
        )


class ToolTraceCallback(BaseCallbackHandler):
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        name = (
            serialized.get("name")
            or serialized.get("id")
            or serialized.get("lc")
            or "tool"
        )
        parsed_args: dict[str, Any]
        try:
            loaded = json.loads(input_str) if isinstance(input_str, str) else input_str
            if isinstance(loaded, dict):
                parsed_args = loaded
            else:
                parsed_args = {"input": loaded}
        except Exception:
            parsed_args = {"input": input_str}
        self.tool_calls.append({"toolName": str(name), "args": parsed_args})


def _normalize_output(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("output", "content"):
            value = result.get(key)
            if value is not None:
                return _normalize_output(value)
        messages = result.get("messages")
        if messages is not None:
            return _normalize_output(messages)
        return json.dumps(result, default=str)
    if isinstance(result, list):
        return "\n".join(_normalize_output(item) for item in result)
    content = getattr(result, "content", None)
    if content is not None:
        return _normalize_output(content)
    return str(result)


def call_api(prompt, options, context):
    options = options or {}
    context = context or {}
    vars_ = _extract_vars(options, context)
    model = _select_model(options, context, vars_)
    config = _load_model_config(model)
    setup_dependencies(vars_.get("precondition"), config)

    _agent_module, invoke_fn = _import_symbol("agent", "invoke")

    callback = ToolTraceCallback()
    callbacks = [callback]

    previous_model_name = os.environ.get("MODEL_NAME")
    os.environ["MODEL_NAME"] = str(config["model"])
    os.environ["LITELLM_BASE_URL"] = os.environ["LITELLM_BASE_URL"]
    os.environ["LITELLM_API_KEY"] = os.environ["LITELLM_API_KEY"]

    try:
        result = invoke_fn(str(prompt), callbacks=callbacks)
    finally:
        if previous_model_name is None:
            os.environ.pop("MODEL_NAME", None)
        else:
            os.environ["MODEL_NAME"] = previous_model_name

    response = {"output": _normalize_output(result)}
    if callback.tool_calls:
        response["toolCalls"] = callback.tool_calls
    return response
