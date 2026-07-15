import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

WORKSPACE_ROOT = Path("/tmp/test_gen_juhpxps5")
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

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
from langchain_core.messages import BaseMessage

import agent as agent_module
from agent import invoke as agent_invoke
import tools as tools_module

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
    pass

_ORIGINAL_ORDERS = json.loads(json.dumps(getattr(tools_module, "ORDERS", {})))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    provider_dir = WORKSPACE_ROOT / ".codevalid/agent/eval/task_6088100935_20260714175150/invoke/providers"
    return _load_yaml(provider_dir / f"{model_name}.yaml")


def _get_var_mapping(prompt: str, context: dict | None) -> dict[str, Any]:
    ctx = context or {}
    vars_ = ctx.get("vars") or {}
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


def _message_content(message: Any) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text is not None:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return " ".join(part for part in parts if part)
    if content is not None:
        return str(content)
    return str(message)


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, BaseMessage):
        return _message_content(result).strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "result"):
            value = result.get(key)
            if value is not None:
                return _extract_answer(value)
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            return _extract_answer(messages[-1])
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, (list, tuple)):
        if not result:
            return ""
        return _extract_answer(result[-1])
    if hasattr(result, "content"):
        return _message_content(result).strip()
    return str(result).strip()


def _normalize_precondition(precondition: Any) -> Any:
    if precondition is None or precondition == "":
        return None
    if isinstance(precondition, dict):
        return precondition
    if isinstance(precondition, list):
        return precondition
    if isinstance(precondition, str):
        text = precondition.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return text
    return precondition


def _seed_order(order_id: str, status: str | None = None, *, exists: bool = True) -> None:
    normalized_id = str(order_id).strip()
    if not normalized_id:
        return
    if not exists:
        tools_module.ORDERS.pop(normalized_id, None)
        return
    tools_module.ORDERS[normalized_id] = {"status": (status or "processing").strip("'\"")}


def _parse_hint_text(text: str) -> None:
    if not text:
        return
    delivered_or_processing = re.search(
        r"Order\s+([A-Za-z0-9-]+)\s+exists\s+with\s+status\s+['\"]?(delivered|processing)['\"]?",
        text,
        re.IGNORECASE,
    )
    if delivered_or_processing:
        _seed_order(delivered_or_processing.group(1), delivered_or_processing.group(2).lower(), exists=True)
        return
    missing = re.search(
        r"Order\s+([A-Za-z0-9-]+)\s+does\s+not\s+exist",
        text,
        re.IGNORECASE,
    )
    if missing:
        _seed_order(missing.group(1), exists=False)
        return


def setup_dependencies(precondition: Any, config: dict | None) -> None:
    del config
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update(json.loads(json.dumps(_ORIGINAL_ORDERS)))

    normalized = _normalize_precondition(precondition)
    if normalized is None:
        return

    if isinstance(normalized, str):
        _parse_hint_text(normalized)
        return

    if isinstance(normalized, list):
        for item in normalized:
            if isinstance(item, str):
                _parse_hint_text(item)
            elif isinstance(item, dict):
                setup_dependencies(item, None)
        return

    if not isinstance(normalized, dict):
        return

    orders = normalized.get("orders")
    if isinstance(orders, list):
        for item in orders:
            if not isinstance(item, dict):
                continue
            order_id = item.get("order_id") or item.get("id")
            if order_id:
                exists = item.get("exists", True)
                _seed_order(str(order_id), str(item.get("status", "processing")), exists=bool(exists))

    for key in ("hints", "preconditions"):
        hints = normalized.get(key)
        if isinstance(hints, str):
            _parse_hint_text(hints)
        elif isinstance(hints, list):
            for hint in hints:
                if isinstance(hint, str):
                    _parse_hint_text(hint)

    for key in ("hint", "note", "text"):
        value = normalized.get(key)
        if isinstance(value, str):
            _parse_hint_text(value)

    sql_text = normalized.get("sql") or normalized.get("psql")
    if sql_text:
        raise RuntimeError("SQL preconditions are not supported for this in-memory refund fixture")



def _build_llm(config: dict | None, context: dict | None = None) -> ChatOpenAI:
    cfg = dict(config or {})
    vars_ = _get_var_mapping("", context)
    model_name = cfg.get("model") or vars_.get("model") or os.environ.get("MODEL_NAME")
    if not model_name:
        raise RuntimeError("No model selected for provider invocation")

    model_cfg = _load_model_config(str(model_name))
    model_section = model_cfg.get("config") if isinstance(model_cfg.get("config"), dict) else model_cfg

    base_url = os.environ["LITELLM_BASE_URL"].rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    api_key = os.environ["LITELLM_API_KEY"]

    kwargs: dict[str, Any] = {
        "model": str(model_name),
        "base_url": base_url,
        "api_key": api_key,
        "temperature": model_section.get("temperature", 0),
        "disable_streaming": True,
    }
    for src_key, dst_key in (("max_tokens", "max_tokens"), ("timeout", "timeout"), ("request_timeout", "timeout")):
        if src_key in model_section and model_section.get(src_key) is not None:
            kwargs[dst_key] = model_section.get(src_key)
    return ChatOpenAI(**kwargs)


@contextmanager
def _patch_agent_llm(llm: ChatOpenAI):
    original_get_llm = agent_module.get_llm

    def _replacement_get_llm(*, traceparent: str | None = None):
        if traceparent:
            headers = dict(getattr(llm, "default_headers", {}) or {})
            headers["traceparent"] = traceparent
            try:
                return llm.__class__(
                    model=getattr(llm, "model_name", None) or getattr(llm, "model", None),
                    base_url=getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None),
                    api_key=getattr(llm, "openai_api_key", None) or os.environ.get("LITELLM_API_KEY"),
                    temperature=getattr(llm, "temperature", 0),
                    default_headers=headers,
                    disable_streaming=True,
                )
            except Exception:
                pass
        return llm

    agent_module.get_llm = _replacement_get_llm
    try:
        yield
    finally:
        agent_module.get_llm = original_get_llm


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
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "to_json"):
        try:
            return value.to_json()
        except Exception:
            return str(value)
    return str(value)


def _extract_gen_ai_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    for key in _GEN_AI_KEYS:
        if key in attrs and attrs[key] is not None:
            extracted[key] = _json_safe(attrs[key])
    return extracted


def _span_kind(span_name: str, gen_ai: dict[str, Any]) -> str:
    operation = str(gen_ai.get("gen_ai.operation.name") or "").lower()
    name = span_name.lower()
    if "execute_tool" in operation or "tool" in name:
        return "tool"
    if operation in {"chat", "completion"} or "chat" in name or "llm" in name:
        return "llm"
    if "agent" in name or operation in {"invoke_agent", "invoke_workflow"}:
        return "agent"
    return "span"


def _span_input(attrs: dict[str, Any], gen_ai: dict[str, Any]) -> Any:
    for key in (
        "gen_ai.input.messages",
        "llm.input_messages",
        "gen_ai.prompt",
        "input.value",
        "gen_ai.tool.call.arguments",
    ):
        if key in gen_ai:
            return gen_ai[key]
        if key in attrs:
            return _json_safe(attrs[key])
    return None


def _span_output(attrs: dict[str, Any], gen_ai: dict[str, Any]) -> Any:
    for key in (
        "gen_ai.output.messages",
        "llm.output_messages",
        "gen_ai.completion",
        "output.value",
        "gen_ai.tool.call.result",
    ):
        if key in gen_ai:
            return gen_ai[key]
        if key in attrs:
            return _json_safe(attrs[key])
    return None


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = {str(k): _json_safe(v) for k, v in dict(getattr(span, "attributes", {}) or {}).items()}
    gen_ai = _extract_gen_ai_attrs(attrs)
    node = {
        "type": _span_kind(getattr(span, "name", ""), gen_ai),
        "name": getattr(span, "name", ""),
        "span_id": format(getattr(getattr(span, "context", None), "span_id", 0), "x"),
        "parent_span_id": format(getattr(getattr(span, "parent", None), "span_id", 0), "x") if getattr(span, "parent", None) is not None else None,
        "input": _span_input(attrs, gen_ai),
        "output": _span_output(attrs, gen_ai),
        "attributes": attrs,
        "gen_ai": gen_ai,
        "children": [],
    }
    tool_name = gen_ai.get("gen_ai.tool.name") or attrs.get("tool.name") or attrs.get("name")
    if node["type"] == "tool" and tool_name:
        node["name"] = str(tool_name)
    return node


def _spans_to_tree(spans: list[Any], *, exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    exclude_names = exclude_names or set()
    filtered = sorted(
        [s for s in spans if getattr(s, "name", "") not in exclude_names],
        key=lambda s: getattr(s, "start_time", 0) or 0,
    )
    nodes = {s.context.span_id: _span_to_node(s) for s in filtered}
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

    def attach(span_id: int) -> dict[str, Any]:
        node = nodes[span_id]
        node["children"] = [attach(child_id) for child_id in child_ids.get(span_id, [])]
        return node

    return [attach(root_id) for root_id in roots]


def _build_trace(user_input: str, answer: str, spans: list[Any]) -> dict[str, Any]:
    return {
        "type": "user_input",
        "input": user_input,
        "output": answer,
        "children": _spans_to_tree(spans, exclude_names={"user_input"}),
    }


def _normalize_input_shape(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, dict):
        if isinstance(user_input.get("input"), str):
            return user_input["input"]
        messages = user_input.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                content = last.get("content")
                if isinstance(content, str):
                    return content
            return _extract_answer(last)
    return _extract_answer(user_input)


def _invoke_agent(llm: ChatOpenAI, user_input: Any, config: dict | None = None) -> tuple[str, dict[str, Any]]:
    del config
    normalized_input = _normalize_input_shape(user_input).strip()
    _exporter.clear()
    tracer = trace.get_tracer("promptfoo-eval")
    with tracer.start_as_current_span("user_input") as root_span:
        root_span.set_attribute("input.value", normalized_input)
        with _patch_agent_llm(llm):
            result = agent_invoke(normalized_input)
        answer = _extract_answer(result)
        root_span.set_attribute("output.value", answer)
    spans = list(_exporter.get_finished_spans())
    return answer, _build_trace(normalized_input, answer, spans)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = _get_var_mapping(prompt, context)
    precondition = vars_.get("precondition")
    if precondition is None:
        precondition = vars_.get("preconditions")
    user_input = _extract_user_input(prompt, context)
    setup_dependencies(precondition, config)
    llm = _build_llm(config, context)
    answer, trace_tree = _invoke_agent(llm, user_input, config)
    return {"output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False)}
