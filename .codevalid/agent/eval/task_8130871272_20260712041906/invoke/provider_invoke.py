import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
except ImportError:
    try:
        from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor
    except ImportError:
        from opentelemetry.instrumentation.langchain import LangChainInstrumentor

WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_gsiv3pmd"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from langchain_openai import ChatOpenAI

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


_DEFAULT_ORDERS = {
    key: dict(value) if isinstance(value, dict) else value
    for key, value in getattr(tools_module, "ORDERS", {}).items()
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    provider_dir = Path(".codevalid/agent/eval/task_8130871272_20260712041906/invoke/providers")
    candidate = provider_dir / f"{model_name}.yaml"
    if candidate.exists():
        data = _load_yaml(candidate)
        config = data.get("config", data)
        return config if isinstance(config, dict) else {}
    return {}


def _get_var_mapping(prompt: Any, context: dict | None) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    if isinstance(context, dict):
        vars_ = context.get("vars")
        if isinstance(vars_, dict):
            mapping.update(vars_)
    if isinstance(prompt, dict):
        mapping.update(prompt)
    return mapping


def _extract_user_input(prompt: Any, context: dict | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if value:
            return str(value)
    if isinstance(prompt, str) and prompt.strip():
        return prompt
    if isinstance(prompt, dict):
        if isinstance(prompt.get("input"), str):
            return prompt["input"]
        messages = prompt.get("messages")
        if isinstance(messages, list):
            for item in reversed(messages):
                if isinstance(item, dict) and item.get("role") == "user":
                    content = item.get("content")
                    if isinstance(content, str):
                        return content
    return ""


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "result"):
            value = result.get(key)
            if value is not None:
                return _extract_answer(value)
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            return _extract_answer(messages[-1])
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, list):
        if not result:
            return ""
        return _extract_answer(result[-1])
    return str(result).strip()


def _parse_precondition(precondition: Any) -> dict[str, Any]:
    if precondition is None or precondition == "":
        return {}
    if isinstance(precondition, dict):
        return precondition
    if isinstance(precondition, list):
        return {"hints": precondition}
    if isinstance(precondition, str):
        text = precondition.strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {"hints": data}
        except Exception:
            pass
        return {"hints": [text]}
    return {"value": precondition}


def _seed_order(order_id: str, status: str) -> None:
    normalized_id = str(order_id).strip()
    if not normalized_id:
        return
    tools_module.ORDERS[normalized_id] = {"status": str(status).strip()}


def _apply_hint_string(hint: str) -> None:
    text = str(hint).strip()
    if not text:
        return
    patterns = [
        re.compile(r"Order\s+(.+?)\s+exists\s+in\s+system\s+with\s+status\s+'([^']+)'", re.IGNORECASE),
        re.compile(r"Order\s+(.+?)\s+exists\s+in\s+system\s+with\s+status\s+\"([^\"]+)\"", re.IGNORECASE),
        re.compile(r"order\s+(.+?)\s+status\s+(delivered|processing|cancelled|refunded)", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            _seed_order(match.group(1), match.group(2).lower())
            return


def setup_dependencies(precondition: Any, config: dict | None) -> None:
    del config
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update(
        {
            key: dict(value) if isinstance(value, dict) else value
            for key, value in _DEFAULT_ORDERS.items()
        }
    )

    parsed = _parse_precondition(precondition)

    orders = parsed.get("orders")
    if isinstance(orders, dict):
        for order_id, value in orders.items():
            if isinstance(value, dict):
                status = value.get("status")
            else:
                status = value
            if status:
                _seed_order(order_id, status)

    for key in ("order", "seed_order"):
        item = parsed.get(key)
        if isinstance(item, dict):
            order_id = item.get("order_id") or item.get("id")
            status = item.get("status")
            if order_id and status:
                _seed_order(order_id, status)

    hints = parsed.get("hints")
    if isinstance(hints, str):
        hints = [hints]
    if isinstance(hints, list):
        for hint in hints:
            _apply_hint_string(str(hint))

    raw_hint = parsed.get("hint")
    if isinstance(raw_hint, str):
        _apply_hint_string(raw_hint)


def _build_llm(config: dict | None, context: dict | None = None) -> ChatOpenAI:
    config = config or {}
    vars_ = _get_var_mapping({}, context)
    model_name = config.get("model") or vars_.get("model") or os.environ.get("MODEL_NAME")
    if not model_name:
        raise RuntimeError("No model selected for provider invocation")

    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LITELLM_BASE_URL and LITELLM_API_KEY must be set")
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    model_cfg = _load_model_config(str(model_name))
    kwargs: dict[str, Any] = {
        "model": str(model_name),
        "base_url": base_url,
        "api_key": api_key,
        "disable_streaming": True,
    }
    if "temperature" in model_cfg:
        kwargs["temperature"] = model_cfg["temperature"]
    else:
        kwargs["temperature"] = 0
    if "max_tokens" in model_cfg:
        kwargs["max_tokens"] = model_cfg["max_tokens"]
    if "timeout" in model_cfg:
        kwargs["timeout"] = model_cfg["timeout"]
    return ChatOpenAI(**kwargs)


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
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.tool.name",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    ]
    extracted: dict[str, Any] = {}
    for key in keys:
        if key in attrs:
            value = attrs[key]
            try:
                json.dumps(value)
                extracted[key] = value
            except TypeError:
                extracted[key] = str(value)
    return extracted


def _normalize_attr_value(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, (list, tuple)):
            return [_normalize_attr_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _normalize_attr_value(v) for k, v in value.items()}
        return str(value)


def _span_kind(span: Any, attrs: dict[str, Any]) -> str:
    operation = str(attrs.get("gen_ai.operation.name", "")).lower()
    name = str(span.name).lower()
    if operation == "execute_tool" or "tool" in name:
        return "tool"
    if operation == "chat" or "llm" in name or "chatopenai" in name:
        return "llm"
    if operation in {"invoke_agent", "invoke_workflow"} or "agent" in name or "chain" in name:
        return "agent"
    return "span"


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = {str(k): _normalize_attr_value(v) for k, v in dict(span.attributes or {}).items()}
    node = {
        "name": span.name,
        "type": _span_kind(span, attrs),
        "span_id": format(span.context.span_id, "x"),
        "parent_span_id": format(span.parent.span_id, "x") if span.parent is not None else None,
        "attributes": attrs,
        "gen_ai": _extract_gen_ai_attrs(attrs),
        "children": [],
    }
    tool_name = attrs.get("gen_ai.tool.name") or attrs.get("tool.name")
    if tool_name:
        node["tool_name"] = tool_name
    if "input.value" in attrs:
        node["input"] = attrs["input.value"]
    elif "gen_ai.prompt" in attrs:
        node["input"] = attrs["gen_ai.prompt"]
    elif "gen_ai.input.messages" in attrs:
        node["input"] = attrs["gen_ai.input.messages"]
    elif "llm.input_messages" in attrs:
        node["input"] = attrs["llm.input_messages"]
    if "output.value" in attrs:
        node["output"] = attrs["output.value"]
    elif "gen_ai.completion" in attrs:
        node["output"] = attrs["gen_ai.completion"]
    elif "gen_ai.output.messages" in attrs:
        node["output"] = attrs["gen_ai.output.messages"]
    elif "llm.output_messages" in attrs:
        node["output"] = attrs["llm.output_messages"]
    return node


def _spans_to_tree(spans: list[Any], exclude_names: set[str] | None = None) -> list[dict[str, Any]]:
    exclude_names = exclude_names or set()
    filtered = sorted(
        [span for span in spans if span.name not in exclude_names],
        key=lambda s: getattr(s, "start_time", 0) or 0,
    )
    nodes = {span.context.span_id: _span_to_node(span) for span in filtered}
    child_ids: dict[int, list[int]] = {}
    roots: list[int] = []
    span_ids = set(nodes.keys())

    for span in filtered:
        sid = span.context.span_id
        parent = span.parent.span_id if span.parent is not None else None
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


def _normalize_prompt_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, dict):
        if isinstance(user_input.get("input"), str):
            return user_input["input"]
        messages = user_input.get("messages")
        if isinstance(messages, list):
            for item in reversed(messages):
                if isinstance(item, dict) and item.get("role") == "user":
                    content = item.get("content")
                    if isinstance(content, str):
                        return content
    return _extract_answer(user_input)


def _invoke_agent(user_input: Any, config: dict | None = None, context: dict | None = None) -> tuple[str, dict[str, Any]]:
    normalized_input = _normalize_prompt_input(user_input)
    llm = _build_llm(config, context)
    tracer = trace.get_tracer("codevalid.promptfoo.provider.invoke")

    def _patched_get_llm(*, traceparent: str | None = None):
        if traceparent:
            headers = {"traceparent": traceparent}
            extra = getattr(llm, "model_kwargs", {}) or {}
            merged = dict(extra)
            merged["default_headers"] = headers
            return ChatOpenAI(
                model=getattr(llm, "model_name", None) or getattr(llm, "model", None),
                base_url=getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None),
                api_key=getattr(llm, "openai_api_key", None) or os.environ.get("LITELLM_API_KEY"),
                temperature=getattr(llm, "temperature", 0),
                max_tokens=getattr(llm, "max_tokens", None),
                timeout=getattr(llm, "request_timeout", None),
                disable_streaming=True,
                default_headers=headers,
            )
        return llm

    _exporter.clear()
    with tracer.start_as_current_span("user_input") as root_span:
        root_span.set_attribute("input.value", normalized_input)
        with patch.object(agent_module, "get_llm", _patched_get_llm):
            result = agent_invoke(normalized_input)
        answer = _extract_answer(result)
        root_span.set_attribute("output.value", answer)

    spans = list(_exporter.get_finished_spans())
    trace_tree = _build_trace(normalized_input, answer, spans)
    return answer, trace_tree


def call_api(prompt: Any, options: dict | None, context: dict | None) -> dict:
    options = options or {}
    context = context or {}
    config = options.get("config", {}) or {}
    vars_ = _get_var_mapping(prompt, context)
    precondition = vars_.get("precondition")
    user_input = _extract_user_input(prompt, context)
    if not user_input:
        raise RuntimeError("Unable to resolve user input for agent invocation")

    setup_dependencies(precondition, config)
    answer, trace_tree = _invoke_agent(user_input, config=config, context=context)
    return {
        "output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False)
    }
