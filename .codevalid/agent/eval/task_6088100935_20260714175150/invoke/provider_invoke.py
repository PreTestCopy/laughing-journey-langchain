import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

WORKSPACE_ROOT = "/tmp/test_gen_sk4hsbqt"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agent import invoke as agent_invoke  # type: ignore
import agent as agent_module  # type: ignore
import tools as tools_module  # type: ignore

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor  # type: ignore
except Exception:  # pragma: no cover
    try:
        from opentelemetry.instrumentation.langchain import LangChainInstrumentor  # type: ignore
    except Exception:
        from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor  # type: ignore

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

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

_BASE_ORDERS = {k: dict(v) for k, v in getattr(tools_module, "ORDERS", {}).items()}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    provider_dir = Path(__file__).resolve().parent / "providers"
    model_path = provider_dir / f"{model_name}.yaml"
    return _load_yaml(model_path)


def _get_var_mapping(prompt: str, context: dict | None) -> dict[str, Any]:
    context = context or {}
    vars_ = context.get("vars") or {}
    return vars_ if isinstance(vars_, dict) else {}


def _extract_user_input(prompt: str, context: dict | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return ""


def _normalize_precondition(precondition: Any) -> dict[str, Any]:
    if precondition is None or precondition == "":
        return {}
    if isinstance(precondition, dict):
        return precondition
    if isinstance(precondition, list):
        return {"items": precondition}
    if isinstance(precondition, str):
        text = precondition.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        except Exception:
            pass
        return {"hint": text, "items": [text]}
    return {"value": precondition}


def _seed_order(order_id: str, status: str | None = None, exists: bool | None = True) -> None:
    normalized_id = str(order_id).strip()
    if not normalized_id:
        return
    if exists is False:
        tools_module.ORDERS.pop(normalized_id, None)
        return
    tools_module.ORDERS[normalized_id] = {"status": (status or "processing").strip()}


def _parse_hint_text(text: str) -> None:
    hint = text.strip()
    if not hint:
        return

    m = re.search(r"Order\s+([A-Za-z0-9\-]+)\s+exists\s+with\s+status\s+'([^']+)'", hint, re.IGNORECASE)
    if m:
        _seed_order(m.group(1), m.group(2), True)
        return

    m = re.search(r"Order\s+([A-Za-z0-9\-]+)\s+does\s+not\s+exist", hint, re.IGNORECASE)
    if m:
        _seed_order(m.group(1), None, False)
        return

    m = re.search(r"status\s+'([^']+)'", hint, re.IGNORECASE)
    if m:
        status = m.group(1)
        ids = re.findall(r"([A-Z]{2,}(?:-[A-Za-z0-9]+)+|[A-Z0-9]{3,})", hint)
        for oid in ids:
            if oid.upper() != status.upper():
                _seed_order(oid, status, True)
        return


def setup_dependencies(precondition: Any, config: dict | None) -> None:
    _ = config
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update({k: dict(v) for k, v in _BASE_ORDERS.items()})

    normalized = _normalize_precondition(precondition)

    orders = normalized.get("orders")
    if isinstance(orders, dict):
        for order_id, details in orders.items():
            if isinstance(details, dict):
                if details.get("exists") is False:
                    _seed_order(order_id, None, False)
                else:
                    _seed_order(order_id, str(details.get("status", "processing")), True)
            else:
                _seed_order(order_id, str(details), True)

    for key in ("hint", "hints"):
        value = normalized.get(key)
        if isinstance(value, str):
            _parse_hint_text(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    _parse_hint_text(item)

    items = normalized.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                _parse_hint_text(item)
            elif isinstance(item, dict):
                oid = item.get("order_id") or item.get("id")
                if oid:
                    if item.get("exists") is False:
                        _seed_order(str(oid), None, False)
                    else:
                        _seed_order(str(oid), str(item.get("status", "processing")), True)


def _build_llm(config: dict | None):
    config = config or {}
    selected_model = config.get("model") or os.environ.get("MODEL_NAME")
    model_cfg = _load_model_config(selected_model)

    base_url = os.environ["LITELLM_BASE_URL"].rstrip("/")
    api_key = os.environ["LITELLM_API_KEY"]
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    temperature = model_cfg.get("temperature", config.get("temperature", 0))
    max_tokens = model_cfg.get("max_tokens", config.get("max_tokens"))
    timeout = model_cfg.get("timeout", config.get("timeout"))

    try:
        from langchain_community.chat_models import ChatLiteLLM  # type: ignore

        kwargs = {
            "model": selected_model,
            "api_base": base_url,
            "api_key": api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if timeout is not None:
            kwargs["timeout"] = timeout
        return ChatLiteLLM(**kwargs)
    except Exception:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore

            kwargs = {
                "model": selected_model,
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
        except Exception:
            return None


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if hasattr(result, "content") and isinstance(getattr(result, "content"), str):
        return getattr(result, "content").strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "result"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list)):
                return str(value).strip()
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            return _extract_answer(messages[-1])
    if isinstance(result, list) and result:
        return _extract_answer(result[-1])
    return str(result).strip()


_GEN_AI_KEYS = [
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
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.tool.name",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
]


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, (list, tuple)):
            return [_json_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        return str(value)


def _extract_gen_ai_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in _GEN_AI_KEYS:
        if key in attrs:
            compact[key] = _json_safe(attrs[key])
    return compact


def _span_type_and_name(span_name: str, attrs: dict[str, Any]) -> tuple[str, str | None]:
    op = attrs.get("gen_ai.operation.name") or attrs.get("operation.name")
    tool_name = attrs.get("gen_ai.tool.name") or attrs.get("tool.name")
    if op == "execute_tool" or tool_name:
        return "tool", str(tool_name or span_name)
    if op in {"invoke_agent", "invoke_workflow"}:
        return "agent", span_name
    if op == "chat" or any(k in attrs for k in ("llm.input_messages", "llm.output_messages", "gen_ai.request.model")):
        return "llm", span_name
    return "span", span_name


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = {str(k): _json_safe(v) for k, v in dict(getattr(span, "attributes", {}) or {}).items()}
    node_type, node_name = _span_type_and_name(getattr(span, "name", "span"), attrs)
    node = {
        "span_id": getattr(getattr(span, "context", None), "span_id", None),
        "parent_span_id": getattr(getattr(span, "parent", None), "span_id", None) if getattr(span, "parent", None) else None,
        "name": getattr(span, "name", "span"),
        "type": node_type,
        "attributes": attrs,
        "gen_ai": _extract_gen_ai_attrs(attrs),
        "children": [],
    }
    if node_name:
        node["tool_name" if node_type == "tool" else "label"] = node_name
    if "input.value" in attrs:
        node["input"] = attrs["input.value"]
    elif "gen_ai.prompt" in attrs:
        node["input"] = attrs["gen_ai.prompt"]
    elif "gen_ai.input.messages" in attrs:
        node["input"] = attrs["gen_ai.input.messages"]
    elif "llm.input_messages" in attrs:
        node["input"] = attrs["llm.input_messages"]
    elif "gen_ai.tool.call.arguments" in attrs:
        node["input"] = attrs["gen_ai.tool.call.arguments"]

    if "output.value" in attrs:
        node["output"] = attrs["output.value"]
    elif "gen_ai.completion" in attrs:
        node["output"] = attrs["gen_ai.completion"]
    elif "gen_ai.output.messages" in attrs:
        node["output"] = attrs["gen_ai.output.messages"]
    elif "llm.output_messages" in attrs:
        node["output"] = attrs["llm.output_messages"]
    elif "gen_ai.tool.call.result" in attrs:
        node["output"] = attrs["gen_ai.tool.call.result"]
    return node


def _spans_to_tree(spans: list[Any], exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    exclude_names = exclude_names or set()
    filtered = sorted(
        [s for s in spans if getattr(s, "name", "") not in exclude_names],
        key=lambda s: getattr(s, "start_time", 0) or 0,
    )
    nodes = {getattr(s.context, "span_id", None): _span_to_node(s) for s in filtered}
    child_ids: dict[int, list[int]] = {}
    roots: list[int] = []
    span_ids = {sid for sid in nodes if sid is not None}

    for s in filtered:
        sid = getattr(s.context, "span_id", None)
        if sid is None:
            continue
        parent = getattr(getattr(s, "parent", None), "span_id", None) if getattr(s, "parent", None) else None
        if parent is not None and parent in span_ids:
            child_ids.setdefault(parent, []).append(sid)
        else:
            roots.append(sid)

    def attach(sid: int) -> dict[str, Any]:
        node = nodes[sid]
        node["children"] = [attach(cid) for cid in child_ids.get(sid, [])]
        return node

    return [attach(rid) for rid in roots if rid in nodes]


def _build_trace(user_input: str, answer: str, spans: list[Any]) -> dict[str, Any]:
    return {
        "type": "user_input",
        "input": user_input,
        "output": answer,
        "children": _spans_to_tree(spans, exclude_names={"user_input"}),
    }


def _invoke_agent(user_input: Any, config: dict | None = None) -> tuple[str, dict[str, Any]]:
    config = config or {}
    llm = _build_llm(config)

    if isinstance(user_input, dict):
        if isinstance(user_input.get("input"), str):
            normalized_input = user_input["input"]
        elif isinstance(user_input.get("messages"), list) and user_input["messages"]:
            last = user_input["messages"][-1]
            if isinstance(last, dict):
                normalized_input = str(last.get("content", ""))
            else:
                normalized_input = _extract_answer(last)
        else:
            normalized_input = _extract_answer(user_input)
    else:
        normalized_input = str(user_input or "")

    if not normalized_input.strip():
        raise ValueError("No user input available for agent invocation")

    selected_model = config.get("model") or os.environ.get("MODEL_NAME")
    if selected_model:
        os.environ["MODEL_NAME"] = str(selected_model)

    tracer = trace.get_tracer("promptfoo-eval")
    _exporter.clear()
    with tracer.start_as_current_span("user_input") as root:
        root.set_attribute("input.value", normalized_input)
        result = agent_invoke(normalized_input)
        answer = _extract_answer(result)
        root.set_attribute("output.value", answer)
    trace_tree = _build_trace(normalized_input, answer, list(_exporter.get_finished_spans()))
    return answer, trace_tree


def call_api(prompt: str, options: dict | None, context: dict | None) -> dict:
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = _get_var_mapping(prompt, context)

    precondition = vars_.get("precondition")
    if precondition is None:
        precondition = vars_.get("preconditions")

    setup_dependencies(precondition, config)

    selected_model = config.get("model") or vars_.get("model")
    if selected_model:
        config = dict(config)
        config["model"] = selected_model

    user_input = _extract_user_input(prompt, context)
    answer, trace_tree = _invoke_agent(user_input, config)
    return {"output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False)}
