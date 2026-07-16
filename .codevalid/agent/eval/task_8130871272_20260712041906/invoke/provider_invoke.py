import ast
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = "/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_gl7f8suk"
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
except ImportError:
    try:
        from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor
    except ImportError:
        from opentelemetry.instrumentation.langchain import LangChainInstrumentor

from langchain_openai import ChatOpenAI

import agent as agent_module
from agent import invoke as agent_invoke
import tools as tools_module

_PROVIDER_DIR = Path(".codevalid/agent/eval/task_8130871272_20260712041906/invoke")
_PROMPTFOOCONFIG_PATH = Path(".codevalid/agent/eval/task_8130871272_20260712041906/invoke/promptfooconfig.yaml")
_DEPENDENCIES_JSON_PATH = Path(".codevalid/agent/dependencies.json")

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

_BASE_ORDERS = json.loads(json.dumps(getattr(tools_module, "ORDERS", {})))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    return data or {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _load_model_config(model_name: str | None) -> dict[str, Any]:
    if not model_name:
        return {}
    model_path = _PROVIDER_DIR / "providers" / f"{model_name}.yaml"
    if model_path.exists():
        data = _load_yaml(model_path)
        if isinstance(data, dict):
            return data.get("config", data) or {}
    providers_yaml = _PROVIDER_DIR / "providers.yaml"
    if providers_yaml.exists():
        data = yaml.safe_load(providers_yaml.read_text()) or []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                provider_id = str(item.get("id", ""))
                if provider_id.endswith(f":{model_name}") or provider_id == model_name:
                    return item.get("config", {}) or {}
    return {}


def _get_var_mapping(prompt: str, context: dict | None) -> dict[str, Any]:
    context = context or {}
    vars_ = context.get("vars") or {}
    if isinstance(vars_, str):
        try:
            parsed = json.loads(vars_)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return vars_ if isinstance(vars_, dict) else {}


def _extract_user_input(prompt: str, context: dict | None) -> str:
    vars_ = _get_var_mapping(prompt, context)
    for key in ("user_input", "input", "message"):
        value = vars_.get(key)
        if value:
            return str(value)
    return str(prompt or "").strip()


def _parse_order_hint(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    lowered = text.lower()
    order_match = re.search(r"\b(ORD-[A-Za-z0-9-]+|[A-Za-z0-9-]{3,})\b", text)
    if not order_match:
        return None
    order_id = order_match.group(1).strip()
    if "does not exist" in lowered or "not exist" in lowered or "not found" in lowered:
        return {"order_id": order_id, "exists": False}
    status_match = re.search(r"status\s+["'“”]?([A-Za-z_ -]+)["'“”]?", text, re.IGNORECASE)
    status = None
    if status_match:
        status = status_match.group(1).strip().strip(".').\"")
    else:
        for candidate in ("delivered", "processing", "shipped", "cancelled"):
            if candidate in lowered:
                status = candidate
                break
    if status:
        return {"order_id": order_id, "exists": True, "status": status}
    return None


def _normalize_precondition(precondition: Any) -> list[Any]:
    if precondition in (None, "", []):
        return []
    if isinstance(precondition, str):
        stripped = precondition.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except Exception:
            return [stripped]
    if isinstance(precondition, list):
        return precondition
    if isinstance(precondition, dict):
        return [precondition]
    return [precondition]


def setup_dependencies(precondition: Any, config: dict | None) -> None:
    del config
    if hasattr(tools_module, "ORDERS") and isinstance(tools_module.ORDERS, dict):
        tools_module.ORDERS.clear()
        tools_module.ORDERS.update(json.loads(json.dumps(_BASE_ORDERS)))

    items = _normalize_precondition(precondition)
    for item in items:
        if isinstance(item, dict):
            orders = item.get("orders")
            if isinstance(orders, dict):
                for order_id, order_data in orders.items():
                    if isinstance(order_data, dict):
                        tools_module.ORDERS[str(order_id).strip()] = {
                            "status": str(order_data.get("status", "")).strip()
                        }
            for key in ("hints", "hint"):
                hints = item.get(key)
                if isinstance(hints, list):
                    for hint in hints:
                        parsed = _parse_order_hint(str(hint))
                        if parsed:
                            _apply_order_seed(parsed)
                elif hints:
                    parsed = _parse_order_hint(str(hints))
                    if parsed:
                        _apply_order_seed(parsed)
            if "order_id" in item:
                _apply_order_seed(item)
        else:
            parsed = _parse_order_hint(str(item))
            if parsed:
                _apply_order_seed(parsed)


def _apply_order_seed(item: dict[str, Any]) -> None:
    order_id = str(item.get("order_id", "")).strip()
    if not order_id:
        return
    exists = item.get("exists", True)
    if exists is False:
        tools_module.ORDERS.pop(order_id, None)
        return
    status = str(item.get("status", "")).strip() or "processing"
    tools_module.ORDERS[order_id] = {"status": status}


def _build_llm(config: dict | None, context: dict | None = None):
    config = config or {}
    vars_ = _get_var_mapping("", context)
    model_name = config.get("model") or vars_.get("model") or os.environ.get("MODEL_NAME")
    if not model_name:
        raise RuntimeError("No model selected for eval")

    base_url = os.environ.get("LITELLM_BASE_URL")
    api_key = os.environ.get("LITELLM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LITELLM_BASE_URL and LITELLM_API_KEY must be set")
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    model_cfg = _load_model_config(model_name)
    kwargs: dict[str, Any] = {
        "model": model_name,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": model_cfg.get("temperature", 0),
        "disable_streaming": True,
    }
    for key in ("max_tokens", "timeout"):
        if model_cfg.get(key) is not None:
            kwargs[key] = model_cfg[key]
    return ChatOpenAI(**kwargs)


@contextmanager
def _patch_get_llm(llm):
    original = agent_module.get_llm

    def _replacement_get_llm(*, traceparent: str | None = None):
        if traceparent:
            try:
                headers = getattr(llm, "default_headers", None) or {}
                headers = dict(headers)
                headers["traceparent"] = traceparent
                if hasattr(llm, "model_copy"):
                    return llm.model_copy(update={"default_headers": headers})
            except Exception:
                pass
        return llm

    agent_module.get_llm = _replacement_get_llm
    try:
        yield
    finally:
        agent_module.get_llm = original


def _message_content(message: Any) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content") or ""
                if text:
                    parts.append(str(text))
        return "\n".join(p for p in parts if p)
    return str(content) if content is not None else str(message)


def _extract_answer(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    content = getattr(result, "content", None)
    if content is not None:
        return _message_content(result).strip()
    if isinstance(result, dict):
        for key in ("output", "answer", "result"):
            if key in result and result[key] is not None:
                return _extract_answer(result[key])
        messages = result.get("messages")
        if messages:
            return _extract_answer(messages[-1])
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, list):
        if not result:
            return ""
        return _extract_answer(result[-1])
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
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.tool.name",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
    ]
    extracted: dict[str, Any] = {}
    for key in keys:
        if key in attrs:
            value = attrs.get(key)
            try:
                json.dumps(value)
                extracted[key] = value
            except TypeError:
                extracted[key] = str(value)
    return extracted


def _safe_attr_dict(span: Any) -> dict[str, Any]:
    attrs = dict(getattr(span, "attributes", {}) or {})
    safe: dict[str, Any] = {}
    for key, value in attrs.items():
        try:
            json.dumps(value)
            safe[str(key)] = value
        except TypeError:
            safe[str(key)] = str(value)
    return safe


def _span_kind(span: Any, attrs: dict[str, Any]) -> str:
    name = getattr(span, "name", "") or ""
    op = str(attrs.get("gen_ai.operation.name", "") or "").lower()
    if op == "execute_tool" or "tool" in name.lower():
        return "tool"
    if op == "chat" or "llm" in name.lower() or "chatopenai" in name.lower():
        return "llm"
    if op in {"invoke_agent", "invoke_workflow"} or "agent" in name.lower():
        return "agent"
    return "span"


def _coerce_possible_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text[0] not in "[{\"":
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


def _span_to_node(span: Any) -> dict[str, Any]:
    attrs = _safe_attr_dict(span)
    gen_ai = _extract_gen_ai_attrs(attrs)
    name = getattr(span, "name", "") or ""
    node: dict[str, Any] = {
        "name": name,
        "type": _span_kind(span, attrs),
        "span_id": format(span.context.span_id, "x"),
        "parent_span_id": format(span.parent.span_id, "x") if span.parent is not None else None,
        "attributes": attrs,
        "gen_ai": gen_ai,
        "children": [],
    }

    tool_name = attrs.get("gen_ai.tool.name") or attrs.get("tool.name")
    if tool_name:
        node["name"] = str(tool_name)
    if node["type"] == "tool":
        node["input"] = _coerce_possible_json(
            attrs.get("gen_ai.tool.call.arguments")
            or attrs.get("input.value")
            or attrs.get("tool.arguments")
            or ""
        )
        node["output"] = _coerce_possible_json(
            attrs.get("gen_ai.tool.call.result")
            or attrs.get("output.value")
            or attrs.get("tool.result")
            or ""
        )
    elif node["type"] == "llm":
        node["input"] = (
            attrs.get("gen_ai.input.messages")
            or attrs.get("llm.input_messages")
            or attrs.get("input.value")
            or attrs.get("gen_ai.prompt")
            or ""
        )
        node["output"] = (
            attrs.get("gen_ai.output.messages")
            or attrs.get("llm.output_messages")
            or attrs.get("output.value")
            or attrs.get("gen_ai.completion")
            or ""
        )
    else:
        if "input.value" in attrs:
            node["input"] = attrs.get("input.value")
        if "output.value" in attrs:
            node["output"] = attrs.get("output.value")
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

    return [attach(root_id) for root_id in roots]


def _build_trace(user_input: str, answer: str, spans: list[Any]) -> dict[str, Any]:
    return {
        "type": "user_input",
        "input": user_input,
        "output": answer,
        "children": _spans_to_tree(spans, exclude_names={"user_input"}),
    }


def _invoke_agent(llm, agent_input: Any, config: dict | None = None) -> tuple[str, dict[str, Any]]:
    config = config or {}
    normalized_input = ""
    if isinstance(agent_input, str):
        normalized_input = agent_input
    elif isinstance(agent_input, dict):
        if "input" in agent_input:
            normalized_input = str(agent_input.get("input", ""))
        elif "messages" in agent_input and agent_input["messages"]:
            last = agent_input["messages"][-1]
            if isinstance(last, dict):
                normalized_input = str(last.get("content", ""))
            else:
                normalized_input = _message_content(last)
    if not normalized_input:
        raise RuntimeError("Unable to normalize user input for agent invocation")

    _exporter.clear()
    tracer = trace.get_tracer("codevalid.promptfoo.eval")
    with _patch_get_llm(llm):
        with tracer.start_as_current_span("user_input") as root_span:
            root_span.set_attribute("input.value", normalized_input)
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
    user_input = _extract_user_input(prompt, context)
    llm = _build_llm(config, context)
    answer, trace_tree = _invoke_agent(llm, {"input": user_input}, config=config)
    return {
        "output": json.dumps({"answer": answer, "trace": trace_tree}, ensure_ascii=False)
    }
