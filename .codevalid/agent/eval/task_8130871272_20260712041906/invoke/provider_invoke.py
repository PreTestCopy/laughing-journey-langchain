from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path("/private/var/folders/64/v39k3dlx3kl6dhmf1gjqpmr4rlcd68/T/test_gen_djm_x7n8")
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "SPAN_ONLY")

import agent as agent_module
import tools as tools_module
from opentelemetry import trace
from opentelemetry.instrumentation.genai.langchain import LangChainInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_ORDERS_BASELINE = copy.deepcopy(getattr(tools_module, "ORDERS", {}))
_ORIGINAL_MODEL_NAME = os.environ.get("MODEL_NAME")


def _seed_happy_path_delivered_order_gets_refund(precondition: Any, config: dict[str, Any]) -> None:
    tools_module.ORDERS["ORD-12345"] = {"status": "delivered"}


def _seed_happy_path_processing_order_refund_blocked(precondition: Any, config: dict[str, Any]) -> None:
    tools_module.ORDERS["ORD-67890"] = {"status": "processing"}


def _seed_tool_selection_lookup_must_precede_refund(precondition: Any, config: dict[str, Any]) -> None:
    tools_module.ORDERS["ORD-11111"] = {"status": "delivered"}


def _seed_missing_info_user_does_not_provide_order_id(precondition: Any, config: dict[str, Any]) -> None:
    return None


def _seed_edge_case_order_not_found(precondition: Any, config: dict[str, Any]) -> None:
    tools_module.ORDERS.pop("ORD-99999", None)


def _seed_edge_case_invalid_order_id_format(precondition: Any, config: dict[str, Any]) -> None:
    return None


_SEEDERS = {
    "happy_path_delivered_order_gets_refund": _seed_happy_path_delivered_order_gets_refund,
    "happy_path_processing_order_refund_blocked": _seed_happy_path_processing_order_refund_blocked,
    "tool_selection_lookup_must_precede_refund": _seed_tool_selection_lookup_must_precede_refund,
    "missing_info_user_does_not_provide_order_id": _seed_missing_info_user_does_not_provide_order_id,
    "edge_case_order_not_found": _seed_edge_case_order_not_found,
    "edge_case_invalid_order_id_format": _seed_edge_case_invalid_order_id_format,
}


def setup_dependencies(test_case_id: str, precondition: Any, config: dict[str, Any]) -> None:
    seeder = _SEEDERS.get(test_case_id)
    if seeder is None:
        raise ValueError(f"Unknown test_case_id for setup: {test_case_id!r}")
    seeder(precondition, config)


def cleanup_dependencies() -> None:
    tools_module.ORDERS.clear()
    tools_module.ORDERS.update(copy.deepcopy(_ORDERS_BASELINE))
    if _ORIGINAL_MODEL_NAME is None:
        os.environ.pop("MODEL_NAME", None)
    else:
        os.environ["MODEL_NAME"] = _ORIGINAL_MODEL_NAME


def _serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _serialize_value(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _serialize_value(value.dict())
        except Exception:
            pass
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, dict):
        for key in ("output", "answer", "content", "text", "final_output", "final_answer"):
            if key in value:
                text = _extract_text(value.get(key))
                if text:
                    return text
        try:
            return json.dumps(_serialize_value(value), ensure_ascii=False)
        except Exception:
            return str(value).strip()
    content = getattr(value, "content", None)
    if content is not None:
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    if item.strip():
                        parts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or item.get("output")
                    if text:
                        parts.append(str(text).strip())
                else:
                    text = getattr(item, "text", None) or getattr(item, "content", None)
                    if text:
                        parts.append(str(text).strip())
            if parts:
                return "\n".join(part for part in parts if part)
        else:
            text = _extract_text(content)
            if text:
                return text
    for attr in ("text", "output", "answer"):
        attr_value = getattr(value, attr, None)
        if attr_value is not None:
            text = _extract_text(attr_value)
            if text:
                return text
    if isinstance(value, list):
        parts = [_extract_text(v) for v in value]
        parts = [p for p in parts if p]
        if parts:
            return "\n".join(parts)
    return str(value).strip()


def _span_kind(span_name: str, mapped: dict[str, Any]) -> str:
    operation = str(mapped.get("operation_name") or "").lower()
    tool_name = mapped.get("tool_name")
    if tool_name or operation == "execute_tool" or "tool" in span_name.lower():
        return "tool"
    if operation in {"chat", "completion", "generate_content"}:
        return "llm"
    if operation in {"invoke_agent", "invoke_workflow", "agent", "chain"}:
        return "agent"
    lower = span_name.lower()
    if "agent" in lower:
        return "agent"
    if "chat" in lower or "llm" in lower:
        return "llm"
    return "span"


def _span_to_node(span: Any) -> dict[str, Any]:
    attributes = dict(getattr(span, "attributes", {}) or {})
    mapped: dict[str, Any] = {}
    candidate_map = {
        "system": ["gen_ai.system", "llm.system"],
        "operation_name": ["gen_ai.operation.name", "llm.operation.name"],
        "request_model": ["gen_ai.request.model", "llm.request.model", "gen_ai.response.model"],
        "prompt": [
            "gen_ai.prompt",
            "llm.prompts",
            "gen_ai.input.messages",
            "input.value",
            "input",
            "gen_ai.tool.call.arguments",
        ],
        "completion": [
            "gen_ai.completion",
            "llm.output_messages",
            "gen_ai.output.messages",
            "output.value",
            "output",
            "gen_ai.tool.call.result",
        ],
        "tool_name": ["gen_ai.tool.name", "tool.name"],
        "input": ["input.value", "input", "gen_ai.input.messages", "llm.prompts"],
        "output": ["output.value", "output", "gen_ai.output.messages", "llm.output_messages"],
    }
    for stable_key, candidate_keys in candidate_map.items():
        for key in candidate_keys:
            if key in attributes and attributes[key] is not None:
                mapped[stable_key] = _serialize_value(attributes[key])
                break
    node = {
        "name": span.name,
        "type": _span_kind(span.name, mapped),
        "span_id": format(span.context.span_id, "016x") if getattr(span, "context", None) else None,
        "parent_span_id": format(span.parent.span_id, "016x") if getattr(span, "parent", None) else None,
        "start_time": getattr(span, "start_time", None),
        "end_time": getattr(span, "end_time", None),
        "status": str(getattr(getattr(span, "status", None), "status_code", "")),
        "attributes": {str(k): _serialize_value(v) for k, v in attributes.items()},
        "gen_ai": mapped,
        "children": [],
    }
    if mapped.get("tool_name"):
        node["name"] = mapped["tool_name"]
        node["tool_name"] = mapped["tool_name"]
    if mapped.get("input") is not None:
        node["input"] = mapped["input"]
    elif mapped.get("prompt") is not None:
        node["input"] = mapped["prompt"]
    if mapped.get("output") is not None:
        node["output"] = mapped["output"]
    elif mapped.get("completion") is not None:
        node["output"] = mapped["completion"]
    return node


def _spans_to_tree(spans: list[Any], *, exclude_names: set[str]) -> list[dict[str, Any]]:
    filtered = sorted(
        [span for span in spans if span.name not in exclude_names],
        key=lambda span: getattr(span, "start_time", 0) or 0,
    )
    nodes = {span.context.span_id: _span_to_node(span) for span in filtered}
    child_ids: dict[int, list[int]] = {}
    roots: list[int] = []
    span_ids = set(nodes.keys())

    for span in filtered:
        sid = span.context.span_id
        parent_id = span.parent.span_id if getattr(span, "parent", None) is not None else None
        if parent_id is not None and parent_id in span_ids:
            child_ids.setdefault(parent_id, []).append(sid)
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
        "spans": [_span_to_node(span) for span in sorted(spans, key=lambda s: getattr(s, "start_time", 0) or 0)],
    }


def _invoke_agent(user_input: str, config: dict[str, Any], tracer: Any, _exporter: InMemorySpanExporter) -> tuple[str, dict[str, Any]]:
    model = config.get("model")
    if not model:
        raise ValueError("Missing required config['model'] for eval provider")
    os.environ["MODEL_NAME"] = str(model)
    _exporter.clear()
    with tracer.start_as_current_span("user_input") as root_span:
        root_span.set_attribute("input.value", user_input)
        answer_obj = agent_module.invoke(user_input)
        answer = _extract_text(answer_obj)
        root_span.set_attribute("output.value", answer)
    spans = list(_exporter.get_finished_spans())
    trace_tree = _build_trace(user_input, answer, spans)
    return answer, trace_tree


def call_api(prompt: str, options: dict | None, context: dict | None) -> dict[str, str]:
    options = options or {}
    context = context or {}
    vars_dict = context.get("vars", {}) or {}
    test_case_id = vars_dict.get("test_case_id", "")
    precondition = vars_dict.get("precondition")
    config = options.get("config", {}) or {}

    base_url = os.environ["LITELLM_BASE_URL"]
    api_key = os.environ["LITELLM_API_KEY"]
    if not base_url:
        raise ValueError("LITELLM_BASE_URL must be set")
    if not api_key:
        raise ValueError("LITELLM_API_KEY must be set")

    setup_dependencies(test_case_id, precondition, config)

    _exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_exporter))
    tracer = provider.get_tracer("promptfoo-eval")
    instrumentor = LangChainInstrumentor()
    instrumented = False

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass

    try:
        instrumentor.instrument(tracer_provider=provider)
        instrumented = True
        answer, trace_tree = _invoke_agent(prompt, config, tracer, _exporter)
        return {
            "output": json.dumps(
                {"answer": answer, "trace": trace_tree},
                ensure_ascii=False,
            )
        }
    finally:
        try:
            cleanup_dependencies()
        finally:
            if instrumented:
                try:
                    instrumentor.uninstrument()
                except Exception:
                    pass
