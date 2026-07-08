"""LangChain refund agent."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from tools import lookup_order, refund_order

load_dotenv()


def get_llm(*, traceparent: str | None = None) -> ChatOpenAI:
    base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    default_headers: dict[str, str] | None = None
    if traceparent:
        default_headers = {"traceparent": traceparent}

    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5.1"),
        base_url=base_url,
        api_key=os.getenv("LITELLM_API_KEY"),
        temperature=0,
        default_headers=default_headers,
        # LiteLLM streaming echoes tool-call name/id chunks twice; LangChain
        # concatenates them (e.g. lookup_orderlookup_order) unless streaming is off.
        disable_streaming=True,
    )


def _build_system_prompt() -> str:
    return (
        "You are a Customer Support Refund Specialist.\n\n"
        "Goal: Resolve refund requests by checking order status and applying "
        "refund business rules accurately.\n\n"
        "Backstory: You are a careful customer support agent. You never guess order status. "
        "You always call lookup_order first, then call refund_order only when "
        "lookup_order returns status 'delivered'. You never skip required tools."
    )


def _build_task_input(customer_request: str) -> str:
    return (
        f"Customer request: {customer_request}\n\n"
        "Follow these rules exactly:\n"
        "1. You MUST call lookup_order for the requested order ID before answering.\n"
        "2. If lookup_order returns status 'delivered', you MUST call refund_order "
        "and then respond with exactly: Refund successful\n"
        "3. If lookup_order returns status 'processing', you MUST NOT call "
        "refund_order and respond with exactly: Refund not allowed because order "
        "is still processing\n"
        "4. Never guess order status. Never skip lookup_order. Never call "
        "refund_order before lookup_order.\n"
        "5. Return only the final customer-facing message."
    )


def build_agent_executor(*, traceparent: str | None = None) -> AgentExecutor:
    tools = [lookup_order, refund_order]
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _build_system_prompt()),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(get_llm(traceparent=traceparent), tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=15,
    )


def invoke(
    user_input: str,
    *,
    callbacks: list[BaseCallbackHandler] | None = None,
    traceparent: str | None = None,
) -> str:
    """Run the refund agent and return the final answer."""
    executor = build_agent_executor(traceparent=traceparent)
    config = {"callbacks": callbacks} if callbacks else None
    result = executor.invoke({"input": _build_task_input(user_input)}, config=config)
    return str(result.get("output", "")).strip()
