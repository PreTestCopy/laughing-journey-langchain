from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_le86r98i"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import yaml
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
except Exception:
    try:
        from opentelemetry.instrumentation.langchain import LangChainInstrumentor
    except Exception:
        from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor

from langchain_openai import ChatOpenAI

import agent as agent_module
import tools as tools_module
from agent import invoke as agent_invoke

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

EVAL_DIR = Path(".codevalid/agent/eval/task_8130871272_20260712041906/invoke")
PROVIDERS_DIR = EVAL_DIR / "providers"

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
try:
    trace.set_tracer_provider(_provider)
except Exception:
    pass
try:
    LangChainInstrumentor().instrument(tracer_provider=_provider)
except Exception:
    try:
        LangChainInstrumentor().instrument()
    except Exception:
        pass

_ORIGINAL_GET_LLM = getattr(agent_module, "get_llm", None)


@contextmanager
def _patched_llm_builder(llm: Any):
    original = getattr(agent_module, "get_llm", None)

    def _replacement_get_llm(*, traceparent: str | None = None):
        headers = dict(getattr(llm, "default_headers", {}) or {})
        if traceparent:
            headers["traceparent"] = traceparent
        if headers and hasattr(llm, "default_headers"):
            try:
                llm.default_headers = headers
            except Exception:
                pass
        return llm

    setattr(agent_module, "get_llm", _replacement_get_llm)
    try:
        yield
    finally:
        setattr(agent_module, "get_llm", original)


@contextmanager
def _patch_create_agent(llm: Any):
    # Present for completeness and future-proofing; this fixture uses create_tool_calling_agent
    # with get_llm(), so get_llm patching is the effective override.
    try:
        import langchain.agents as lc_agents
    except Exception:
        lc_agents = None

    original_global = getattr(lc_agents, "create_agent", None) if lc_agents else None
    original_module = getattr(agent_module, "create_agent", None)

    def _wrapped_create_agent(*args, **kwargs):
        kwargs["model"] = llm
        if args:
            args = list(args)
            args[0] = llm
        return (original_module or original_global)(*args, **kwargs)

    try:
        if lc_agents and original_global:
            setattr(lc_agents, "create_agent", _wrapped_create_agent)
        if original_module:
            setattr(agent_module, "create_agent", _wrapped_create_agent)
        yield
    finally:
        if lc_agents and original_global:
            setattr(lc_agents, "create_agent", original_global)
        if original_module:
            setattr(agent_module, "create_agent", original_module)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    path = PROVIDERS_DIR / f"{model_name}.yaml"
    return _load_yaml(path)


def _get_var_mapping(prompt: str, context: dict | None) -> dict[str, Any]:
    context = context or {}
    vars_ = context.get("vars") or {}
    return vars_ if isinstance(vars_, dict) else {}


def _extract_user_input(prompt: str, context: dict | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if value is not None and str(value).strip():
            return str(value)
    if isinstance(prompt, str):
        stripped = prompt.strip()
        if stripped:
            return stripped
    return ""


def _extract_order_ids(text: str) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for match in re.findall(r"\b[A-Za-z0-9-]{2,}\b", text):
        token = match.strip().strip(".,!?;:\"")
        if any(ch.isdigit() for ch in token) and token not in seen:
            seen.append(token)
    return seen


def _normalize_precondition(precondition: Any) -> dict[str, Any]:
    if precondition is None or precondition == "":
        return {}
    if isinstance(precondition, dict):
        return precondition
    if isinstance(precondition, list):
        return {"items": precondition, "hints": precondition}
    if isinstance(precondition, str):
        stripped = precondition.strip()
        if not stripped:
            return {}
        try:
            loaded = json.loads(stripped)
            if isinstance(loaded, dict):
                return loaded
            if isinstance(loaded, list):
                return {"items": loaded, "hints": loaded}
        except Exception:
            pass
        return {"hint": stripped, "hints": [stripped]}
    return {"value": precondition}


def _apply_hint_to_orders(hint: str) -> None:
    if not hint:
        return
    text = str(hint).strip()
    order_ids = _extract_order_ids(text)
    lowered = text.lower()

    if "does not exist" in lowered or "not exist" in lowered or "not found" in lowered:
        for order_id in order_ids:
            tools_module.ORDERS.pop(order_id, None)
        return

    status_match = re.search(r"status\s+'?([a-z_ -]+)'?", text, re.IGNORECASE)
    if not status_match:
        status_match = re.search(r"with status\s+'?([a-z_ -]+)'?", text, re.IGNORECASE)
    if not status_match:
        if "delivered" in lowered:
            status = "delivered"
        elif "processing" in lowered:
            status = "processing"
        else:
            status = None
    else:
        status = status_match.group(1).strip().lower()

    for order_id in order_ids:
        if status:
            tools_module.ORDERS[str(order_id).strip()] = {"status": status}


def setup_dependencies(precondition: Any, config: dict | None) -> None:
    _ = config
    base_orders = {
        "123": {"status": "delivered"},
        "456": {"status": "processing"},
    }
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update(base_orders)

    normalized = _normalize_precondition(precondition)

    if isinstance(normalized.get("orders"), dict):
        for order_id, value in normalized["orders"].items():
            if value is None:
                tools_module.ORDERS.pop(str(order_id), None)
            elif isinstance(value, dict):
                status = value.get("status")
                if status:
                    tools_module.ORDERS[str(order_id)] = {"status": str(status)}
            else:
                tools_module.ORDERS[str(order_id)] = {"status": str(value)}

    hints: list[Any] = []
    for key in ("hints", "items", "preconditions"):
        value = normalized.get(key)
        if isinstance(value, list):
            hints.extend(value)
        elif value:
            hints.append(value)
    if normalized.get("hint"):
        hints.append(normalized["hint"])

    for hint in hints:
        if isinstance(hint, str):
            _apply_hint_to_orders(hint)


def _build_llm(config: dict | None, context: dict | None = None) -> Any:
    config = config or {}
    vars_ = _get_var_mapping("", context)
    selected_model = config.get("model") or vars_.get("model")
    if not selected_model:
        selected_model = os.environ.get("MODEL_NAME")
    if not selected_model:
        raise RuntimeError("No model selected for eval provider")

    base_url = os.environ["LITELLM_BASE_URL"].rstrip("/")
    api_key = os.environ["LITELLM_API_KEY"]
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    model_cfg = _load_model_config(str(selected_model))
    kwargs: dict[str, Any] = {
        "model": str(selected_model),
        "base_url": base_url,
        "api_key": api_key,
        "disable_streaming": True,
    }
    for src_key, dst_key in (("temperature", "temperature"), ("max_tokens", "max_tokens"), ("timeout", "timeout")):
        if model_cfg.get(src_key) is not None:
            kwargs[dst_key] = model_cfg[src_key]
    if "temperature" not in kwargs:
        kwargs["temperature"] = 0
    return ChatOpenAI(**kwargs)


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if hasattr(result, "content"):
        content = getattr(result, "content", "")
        if isinstance(content, list):
            return " ".join(_extract_answer(item) for item in content if item is not None).strip()
        return str(content).strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "result"):
            if key in result and result[key] is not None:
                return _extract_answer(result[key])
        if "messages" in result:
            return _extract_answer(result["messages"])
        try:
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return str(result).strip()
    if isinstance(result, list):
        parts = [_extract_answer(item) for item in result]
        parts = [p for p in parts if p]
        return "\n".join(parts).strip()
    return str(result).strip()


def _extract_gen_ai_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "gen_ai.system",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.operation.name",
        "gen_ai.prompt",
        "gen_ai.completion",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "input.value",
        "output.value",
        "llm.input_messages",
        "llm.output_messages",
        "gen_ai.tool.name",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    ]
    compact: dict[str, Any] = {}
    for key in keys:
        if key in attrs:
            value = attrs.get(key)
            try:
                json.dumps(value)
                compact[key] = value
            except Exception:
                compact[key] = str(value)
    return compact


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        return str(value)


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = {str(k): _json_safe(v) for k, v in dict(getattr(span, "attributes", {}) or {}).items()}
    gen_ai = _extract_gen_ai_attrs(attrs)
    operation = gen_ai.get("gen_ai.operation.name") or attrs.get("gen_ai.operation.name") or span.name
    node_type = "span"
    lowered = str(operation).lower()
    if lowered == "chat":
        node_type = "llm"
    elif lowered == "execute_tool":
        node_type = "tool"
    elif lowered in {"invoke_agent", "invoke_workflow"} or "agent" in lowered:
        node_type = "agent"

    node = {
        "name": span.name,
        "type": node_type,
        "span_id": format(span.context.span_id, "016x"),
        "parent_span_id": format(span.parent.span_id, "016x") if getattr(span, "parent", None) else None,
        "attributes": attrs,
        "gen_ai": gen_ai,
        "children": [],
    }

    if node_type == "tool":
        node["tool_name"] = (
            attrs.get("gen_ai.tool.name")
            or attrs.get("tool.name")
            or attrs.get("name")
            or span.name
        )
    return node


def _spans_to_tree(spans: list[Any], user_input: str, answer: str) -> dict[str, Any]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    root_children: list[dict[str, Any]] = []

    for span in spans:
        node = _span_to_node(span)
        nodes_by_id[node["span_id"]] = node

    synthetic_root_id: str | None = None
    for node in nodes_by_id.values():
        if node.get("name") == "user_input":
            synthetic_root_id = node["span_id"]
            break

    for node in nodes_by_id.values():
        parent_id = node.get("parent_span_id")
        if parent_id and parent_id in nodes_by_id:
            nodes_by_id[parent_id]["children"].append(node)
        elif node["span_id"] != synthetic_root_id:
            root_children.append(node)

    def _sort_tree(node: dict[str, Any]) -> None:
        node["children"].sort(key=lambda child: (child.get("name") or "", child.get("span_id") or ""))
        for child in node["children"]:
            _sort_tree(child)

    for child in root_children:
        _sort_tree(child)

    return {
        "type": "user_input",
        "input": user_input,
        "output": answer,
        "children": root_children,
    }


def _normalize_invocation_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, dict):
        if "input" in user_input:
            return _normalize_invocation_input(user_input["input"])
        if "messages" in user_input and isinstance(user_input["messages"], list):
            contents: list[str] = []
            for msg in user_input["messages"]:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    contents.append(str(msg.get("content", "")))
                elif hasattr(msg, "content"):
                    contents.append(str(getattr(msg, "content", "")))
            return "\n".join(part for part in contents if part).strip()
    return str(user_input or "").strip()


def _invoke_agent(user_input: Any, llm: Any) -> tuple[str, dict[str, Any]]:
    normalized_input = _normalize_invocation_input(user_input)
    _exporter.clear()
    tracer = trace.get_tracer("codevalid.promptfoo.provider.invoke")
    with tracer.start_as_current_span("user_input") as root_span:
        root_span.set_attribute("input.value", normalized_input)
        with _patch_create_agent(llm), _patched_llm_builder(llm):
            result = agent_invoke(normalized_input)
        answer = _extract_answer(result)
        root_span.set_attribute("output.value", answer)
    spans = list(_exporter.get_finished_spans())
    trace_tree = _spans_to_tree(spans, normalized_input, answer)
    return answer, trace_tree


def call_api(prompt: str, options: dict, context: dict) -> dict:
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = _get_var_mapping(prompt, context)
    precondition = vars_.get("precondition")
    if precondition is None:
        precondition = vars_.get("preconditions")

    setup_dependencies(precondition, config)
    llm = _build_llm(config, context)
    user_input = _extract_user_input(prompt, context)
    answer, trace_tree = _invoke_agent(user_input, llm)
    return {"output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False)}
