import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_gkajy6bh"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    from openinference.instrumentation.langchain import LangChainInstrumentor
except Exception:
    try:
        from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor
    except Exception:
        from opentelemetry.instrumentation.langchain import LangChainInstrumentor

import agent as agent_module
import tools as tools_module
from agent import invoke as agent_invoke

_provider = TracerProvider()
_exporter = InMemorySpanExporter()
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


class _PromptfooCallbackHandler:
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    provider_dir = Path(".codevalid/agent/eval/task_8130871272_20260712041906/invoke/providers")
    model_path = provider_dir / f"{model_name}.yaml"
    data = _load_yaml(model_path)
    if not data:
        return {}
    if isinstance(data.get("config"), dict):
        return data["config"]
    return data


def _get_var_mapping(prompt: Any, context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    vars_ = context.get("vars") or {}
    return vars_ if isinstance(vars_, dict) else {}


def _extract_user_input(prompt: Any, context: dict[str, Any] | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    if isinstance(prompt, dict):
        for key in ("user_input", "input", "message"):
            value = prompt.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        messages = prompt.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
    return ""


def _extract_text_from_message(message: Any) -> str:
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
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join([p for p in parts if p])
    return str(message)


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if hasattr(result, "content"):
        return _extract_text_from_message(result).strip()
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


def _parse_precondition(precondition: Any) -> Any:
    if precondition in (None, "", []):
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
            loaded = json.loads(text)
            return loaded
        except Exception:
            return {"hints": [text]}
    return {}


def _seed_order(order_id: str, status: str | None = None, exists: bool | None = None) -> None:
    normalized_id = str(order_id).strip()
    if not normalized_id:
        return
    if exists is False:
        tools_module.ORDERS.pop(normalized_id, None)
        return
    if status:
        tools_module.ORDERS[normalized_id] = {"status": str(status).strip()}


def _extract_order_hints(text: str) -> None:
    if not isinstance(text, str):
        return
    delivered_match = re.search(r"Order\s+([A-Za-z0-9\-]+)\s+exists(?:\s+in\s+system)?\s+with\s+status\s+'([^']+)'", text, re.IGNORECASE)
    if delivered_match:
        _seed_order(delivered_match.group(1), delivered_match.group(2), True)
    returned_match = re.search(r"lookup_order\s+(?:will\s+)?return(?:s)?\s+status\s+'([^']+)'\s+for\s+([A-Za-z0-9\-]+)", text, re.IGNORECASE)
    if returned_match:
        _seed_order(returned_match.group(2), returned_match.group(1), True)
    missing_match = re.search(r"Order\s+([A-Za-z0-9\-]+)\s+does\s+not\s+exist", text, re.IGNORECASE)
    if missing_match:
        _seed_order(missing_match.group(1), exists=False)
    invalid_match = re.search(r"Order ID\s+'([^']+)'\s+will\s+be\s+rejected", text, re.IGNORECASE)
    if invalid_match:
        tools_module.ORDERS.pop(invalid_match.group(1).strip(), None)


def setup_dependencies(precondition: Any, config: dict[str, Any] | None) -> None:
    _ = config
    parsed = _parse_precondition(precondition)
    base_orders = {
        "123": {"status": "delivered"},
        "456": {"status": "processing"},
    }
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update(base_orders)

    if isinstance(parsed, dict):
        orders = parsed.get("orders")
        if isinstance(orders, dict):
            for order_id, order_value in orders.items():
                if isinstance(order_value, dict):
                    if order_value.get("exists") is False:
                        _seed_order(order_id, exists=False)
                    else:
                        _seed_order(order_id, order_value.get("status"), True)
                elif isinstance(order_value, str):
                    _seed_order(order_id, order_value, True)

        for key in ("hints", "preconditions", "items"):
            value = parsed.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        _extract_order_hints(item)
            elif isinstance(value, str):
                _extract_order_hints(value)

        for key in ("sql", "psql"):
            if parsed.get(key):
                raise RuntimeError("This fixture uses in-memory order state only; SQL preconditions are unsupported.")
    elif isinstance(parsed, str):
        _extract_order_hints(parsed)



def _build_llm(config: dict[str, Any] | None):
    config = config or {}
    selected_model = config.get("model") or (_get_var_mapping(None, {"vars": config}).get("model")) or os.environ.get("MODEL_NAME")
    model_cfg = _load_model_config(selected_model)
    base_url = os.environ["LITELLM_BASE_URL"].rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    api_key = os.environ["LITELLM_API_KEY"]

    temperature = model_cfg.get("temperature", config.get("temperature", 0))
    max_tokens = model_cfg.get("max_tokens", config.get("max_tokens"))
    timeout = model_cfg.get("timeout", config.get("timeout"))

    try:
        from langchain_community.chat_models import ChatLiteLLM

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
        from langchain_openai import ChatOpenAI

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



def _serialize_attributes(attrs: Any) -> dict[str, Any]:
    if not attrs:
        return {}
    result: dict[str, Any] = {}
    for key, value in dict(attrs).items():
        try:
            json.dumps(value)
            result[str(key)] = value
        except Exception:
            result[str(key)] = str(value)
    return result



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
            extracted[key] = attrs[key]
    return extracted



def _span_kind(span_name: str, attrs: dict[str, Any]) -> str:
    operation = attrs.get("gen_ai.operation.name") or attrs.get("openinference.span.kind")
    if operation == "execute_tool" or attrs.get("gen_ai.tool.name"):
        return "tool"
    if operation == "chat" or "llm" in span_name.lower() or "chat" in span_name.lower():
        return "llm"
    if "agent" in span_name.lower() or operation in {"invoke_agent", "invoke_workflow"}:
        return "agent"
    return "span"



def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = _serialize_attributes(getattr(span, "attributes", {}) or {})
    node = {
        "name": span.name,
        "type": _span_kind(span.name, attrs),
        "attributes": attrs,
        "gen_ai": _extract_gen_ai_attrs(attrs),
        "children": [],
    }
    if node["type"] == "tool":
        node["name"] = attrs.get("gen_ai.tool.name") or attrs.get("tool.name") or span.name
        node["input"] = attrs.get("gen_ai.tool.call.arguments") or attrs.get("input.value") or attrs.get("gen_ai.input.messages")
        node["output"] = attrs.get("gen_ai.tool.call.result") or attrs.get("output.value")
    elif node["type"] == "llm":
        node["input"] = attrs.get("gen_ai.prompt") or attrs.get("input.value") or attrs.get("llm.input_messages") or attrs.get("gen_ai.input.messages")
        node["output"] = attrs.get("gen_ai.completion") or attrs.get("output.value") or attrs.get("llm.output_messages") or attrs.get("gen_ai.output.messages")
    else:
        if "input.value" in attrs:
            node["input"] = attrs.get("input.value")
        if "output.value" in attrs:
            node["output"] = attrs.get("output.value")
    return node



def _spans_to_tree(spans: list[Any]) -> list[dict[str, Any]]:
    filtered = sorted(
        [s for s in spans if getattr(s, "name", "") != "user_input"],
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
        "children": _spans_to_tree(spans),
    }



def _normalize_agent_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, dict):
        if isinstance(user_input.get("input"), str):
            return user_input["input"]
        messages = user_input.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    return msg["content"]
    return str(user_input)



def _invoke_agent(user_input: Any, config: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    normalized_input = _normalize_agent_input(user_input).strip()
    llm = _build_llm(config or {})
    tracer = trace.get_tracer("promptfoo-eval")

    def _patched_get_llm(*, traceparent: str | None = None):
        if traceparent and hasattr(llm, "default_headers"):
            try:
                current_headers = dict(getattr(llm, "default_headers", {}) or {})
                current_headers["traceparent"] = traceparent
                setattr(llm, "default_headers", current_headers)
            except Exception:
                pass
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



def call_api(prompt: Any, options: dict[str, Any] | None, context: dict[str, Any] | None) -> dict[str, str]:
    options = options or {}
    context = context or {}
    config = options.get("config") or {}
    vars_ = _get_var_mapping(prompt, context)
    precondition = vars_.get("precondition")
    user_input = vars_.get("user_input") or vars_.get("input") or vars_.get("message") or _extract_user_input(prompt, context)
    if vars_.get("model") and not config.get("model"):
        config = {**config, "model": vars_["model"]}

    setup_dependencies(precondition, config)
    answer, trace_tree = _invoke_agent(user_input, config)
    return {
        "output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False),
    }
