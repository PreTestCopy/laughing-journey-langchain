from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_dhaa6hms"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

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

try:
    from langchain_community.chat_models import ChatLiteLLM
except Exception:
    ChatLiteLLM = None

from langchain_openai import ChatOpenAI

import agent as agent_module
import tools as tools_module
from agent import invoke as agent_invoke

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
        target = original_module or original_global
        if target is None:
            raise RuntimeError("create_agent patch requested but no target exists")
        return target(*args, **kwargs)

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
    return _load_yaml(PROVIDERS_DIR / f"{model_name}.yaml")


def _get_var_mapping(prompt: str, context: dict | None) -> dict[str, Any]:
    _ = prompt
    context = context or {}
    vars_ = context.get("vars") or {}
    return vars_ if isinstance(vars_, dict) else {}


def _extract_user_input(prompt: str, context: dict | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if value is not None and str(value).strip():
            return str(value)
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return ""


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


def _extract_order_ids(text: str) -> list[str]:
    if not text:
        return []
    seen: list[str] = []
    for match in re.findall(r"\b[A-Za-z0-9-]{2,}\b", text):
        token = match.strip().strip(".,!?;:\"'")
        if any(ch.isdigit() for ch in token) and token not in seen:
            seen.append(token)
    return seen


def _apply_hint_to_orders(hint: str) -> None:
    if not hint:
        return
    text = str(hint).strip()
    lowered = text.lower()
    order_ids = _extract_order_ids(text)

    if "does not exist" in lowered or "not exist" in lowered or "not found" in lowered:
        for order_id in order_ids:
            tools_module.ORDERS.pop(order_id, None)
        return

    status_match = re.search(r"status\s+'?([a-z_ -]+)'?", text, re.IGNORECASE)
    if not status_match:
        status_match = re.search(r"with status\s+'?([a-z_ -]+)'?", text, re.IGNORECASE)

    if status_match:
        status = status_match.group(1).strip().lower()
    elif "delivered" in lowered:
        status = "delivered"
    elif "processing" in lowered:
        status = "processing"
    else:
        status = None

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

    orders = normalized.get("orders")
    if isinstance(orders, dict):
        for order_id, value in orders.items():
            key = str(order_id).strip()
            if value is None:
                tools_module.ORDERS.pop(key, None)
            elif isinstance(value, dict):
                status = value.get("status")
                if status is not None:
                    tools_module.ORDERS[key] = {"status": str(status)}
            else:
                tools_module.ORDERS[key] = {"status": str(value)}

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
    temperature = model_cfg.get("temperature", 0)
    max_tokens = model_cfg.get("max_tokens")
    timeout = model_cfg.get("timeout")

    if ChatLiteLLM is not None:
        kwargs: dict[str, Any] = {
            "model": str(selected_model),
            "api_base": base_url,
            "api_key": api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if timeout is not None:
            kwargs["timeout"] = timeout
        try:
            return ChatLiteLLM(**kwargs)
        except Exception:
            pass

    kwargs = {
        "model": str(selected_model),
        "base_url": base_url,
        "api_key": api_key,
        "temperature": temperature,
        "disable_streaming": True,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if timeout is not None:
        kwargs["timeout"] = timeout
    return ChatOpenAI(**kwargs)


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if hasattr(result, "content"):
        content = getattr(result, "content", "")
        if isinstance(content, list):
            pieces = [_extract_answer(item) for item in content if item is not None]
            return " ".join(piece for piece in pieces if piece).strip()
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
        return "\n".join(part for part in parts if part).strip()
    return str(result).strip()


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
            compact[key] = _json_safe(attrs.get(key))
    return compact


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = {str(k): _json_safe(v) for k, v in dict(getattr(span, "attributes", {}) or {}).items()}
    gen_ai = _extract_gen_ai_attrs(attrs)
    operation = gen_ai.get("gen_ai.operation.name") or attrs.get("gen_ai.operation.name") or span.name
    lowered = str(operation).lower()
    node_type = "span"
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


def _spans_to_tree(spans: list[Any], *, exclude_names: set[str]) -> list[dict[str, Any]]:
    filtered = sorted(
        [span for span in spans if getattr(span, "name", None) not in exclude_names],
        key=lambda span: getattr(span, "start_time", 0) or 0,
    )
    nodes = {span.context.span_id: _span_to_node(span) for span in filtered}
    child_ids: dict[int, list[int]] = {}
    roots: list[int] = []
    span_ids = set(nodes)

    for span in filtered:
        sid = span.context.span_id
        parent = span.parent.span_id if getattr(span, "parent", None) is not None else None
        if parent is not None and parent in span_ids:
            child_ids.setdefault(parent, []).append(sid)
        else:
            roots.append(sid)

    def attach(sid: int) -> dict[str, Any]:
        node = nodes[sid]
        node["children"] = [attach(cid) for cid in child_ids.get(sid, [])]
        return node

    return [attach(rid) for rid in roots]


def _build_trace(user_input: str, answer: str, spans: list[Any]) -> dict[str, Any]:
    return {
        "type": "user_input",
        "input": user_input,
        "output": answer,
        "children": _spans_to_tree(spans, exclude_names={"user_input"}),
    }


def _normalize_invocation_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input.strip()
    if isinstance(user_input, dict):
        if "input" in user_input:
            return _normalize_invocation_input(user_input["input"])
        if "messages" in user_input and isinstance(user_input["messages"], list):
            parts: list[str] = []
            for msg in user_input["messages"]:
                if isinstance(msg, dict) and str(msg.get("role", "")).lower() == "user":
                    parts.append(str(msg.get("content", "")))
                elif hasattr(msg, "content"):
                    parts.append(str(getattr(msg, "content", "")))
            return "\n".join(part for part in parts if part).strip()
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
    trace_tree = _build_trace(normalized_input, answer, spans)
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
