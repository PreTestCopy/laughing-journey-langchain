"""Customer support refund tools backed by in-memory order data."""

from __future__ import annotations

import json

from langchain_core.tools import tool

ORDERS: dict[str, dict[str, str]] = {
    "123": {"status": "delivered"},
    "456": {"status": "processing"},
}


@tool
def lookup_order(order_id: str) -> str:
    """Look up the status of a customer order by order ID."""
    normalized_id = str(order_id).strip()
    if len(normalized_id) < 3:
        return json.dumps({"order_id": normalized_id, "error": "invalid order id"})
    order = ORDERS.get(normalized_id)
    if order is None:
        return json.dumps({"order_id": normalized_id, "error": "order not found"})
    status = order["status"]
    next_action = (
        "Call refund_order for this order_id before responding to the customer."
        if status == "delivered"
        else "Do not call refund_order. Tell the customer the refund is not allowed."
    )
    return json.dumps(
        {
            "order_id": normalized_id,
            "status": status,
            "next_action": next_action,
        }
    )


@tool
def refund_order(order_id: str) -> str:
    """Issue a refund for an order. Only use when the order status is delivered."""
    normalized_id = str(order_id).strip()
    return json.dumps({"success": True, "order_id": normalized_id})
