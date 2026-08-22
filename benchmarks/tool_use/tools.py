"""The pilot's 10 domain-grounded retail tools.

Each tool has two parts, kept side by side on purpose:

1. `TOOL_SCHEMAS[name]` — the full tool representation from SCHEMA.md section 4
   (primitive, domain, task, inputs, outputs, side_effect, risk, preconditions,
   postconditions). This is what the benchmark reasons about.
2. `TOOL_IMPLS[name]` — a plain Python function `(store, **kwargs) -> dict` that
   actually enforces those preconditions against a RetailStore and mutates it on
   success. This is what makes the pilot's precondition/postcondition checks real
   rather than declarative-only.

`build_langchain_tools(store)` wraps TOOL_IMPLS as LangChain tools bound to one
store instance, for agent adapters built on LangChain (Agent A). Agent B calls
TOOL_IMPLS directly through its own manual dispatch, proving the same tool set
and store work without a specific agent framework.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from store import RetailStore


# ---------------------------------------------------------------------------
# 1. Full schema representation (SCHEMA.md section 4) for every tool
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "search_products": {
        "name": "search_products",
        "description": "Search the product catalog by keyword, optionally capped by max price.",
        "primitive": "SEARCH",
        "domain": ["PRODUCT_CATALOG", "ECOMMERCE"],
        "task": {"type": "SEARCH_ENTITY", "description": "Find products matching a keyword query"},
        "inputs": [
            {"name": "query", "type": "STRING", "required": True, "source": "USER"},
            {"name": "max_price", "type": "FLOAT", "required": False, "source": "USER"},
        ],
        "outputs": {"type": "ENTITY_LIST", "entity_type": "PRODUCT"},
        "side_effect": {"has_side_effect": False, "type": "NONE", "reversible": "NOT_APPLICABLE"},
        "risk": {"level": "NONE", "categories": ["NONE"]},
        "preconditions": [],
        "postconditions": [],
    },
    "check_inventory": {
        "name": "check_inventory",
        "description": "Check current stock quantity for a specific SKU.",
        "primitive": "READ",
        "domain": ["INVENTORY"],
        "task": {"type": "GET_DETAILS", "description": "Check SKU availability"},
        "inputs": [
            {"name": "sku", "type": "IDENTIFIER", "required": True, "source": "USER"},
        ],
        "outputs": {"type": "RECORD", "entity_type": "INVENTORY_RECORD"},
        "side_effect": {"has_side_effect": False, "type": "NONE", "reversible": "NOT_APPLICABLE"},
        "risk": {"level": "NONE", "categories": ["NONE"]},
        "preconditions": ["PRODUCT_EXISTS"],
        "postconditions": [],
    },
    "get_order_status": {
        "name": "get_order_status",
        "description": "Look up the current status and details of an existing order.",
        "primitive": "READ",
        "domain": ["ORDER_MANAGEMENT"],
        "task": {"type": "GET_STATUS", "description": "Find order status"},
        "inputs": [
            {"name": "order_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
        ],
        "outputs": {"type": "ENTITY", "entity_type": "ORDER"},
        "side_effect": {"has_side_effect": False, "type": "NONE", "reversible": "NOT_APPLICABLE"},
        "risk": {"level": "NONE", "categories": ["NONE"]},
        "preconditions": ["ORDER_EXISTS"],
        "postconditions": [],
    },
    "add_item_to_cart": {
        "name": "add_item_to_cart",
        "description": "Add a quantity of a product SKU to an existing cart.",
        "primitive": "CREATE",
        "domain": ["ORDER_MANAGEMENT", "ECOMMERCE"],
        "task": {"type": "ADD_ITEM", "description": "Add a product to the customer's cart"},
        "inputs": [
            {"name": "cart_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "sku", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "quantity", "type": "INTEGER", "required": True, "source": "USER"},
        ],
        "outputs": {"type": "ENTITY", "entity_type": "CART"},
        "side_effect": {"has_side_effect": True, "type": "STATE_CHANGE", "reversible": "REVERSIBLE"},
        "risk": {"level": "LOW", "categories": ["OPERATIONAL"]},
        "preconditions": ["CART_EXISTS", "PRODUCT_EXISTS", "SUFFICIENT_INVENTORY"],
        "postconditions": ["ITEM_ADDED_TO_CART"],
    },
    "update_shipping_address": {
        "name": "update_shipping_address",
        "description": "Update the shipping address on an order that has not yet shipped.",
        "primitive": "UPDATE",
        "domain": ["ORDER_MANAGEMENT"],
        "task": {"type": "UPDATE_ENTITY", "description": "Update an order's shipping address"},
        "inputs": [
            {"name": "order_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "address", "type": "STRING", "required": True, "source": "USER"},
        ],
        "outputs": {"type": "ENTITY", "entity_type": "ORDER"},
        "side_effect": {"has_side_effect": True, "type": "STATE_CHANGE", "reversible": "REVERSIBLE"},
        "risk": {"level": "LOW", "categories": ["PRIVACY"]},
        "preconditions": ["ORDER_EXISTS", "ORDER_NOT_SHIPPED"],
        "postconditions": ["ADDRESS_UPDATED"],
    },
    "cancel_order": {
        "name": "cancel_order",
        "description": "Cancel an existing order before it has shipped.",
        "primitive": "DELETE",
        "domain": ["ORDER_MANAGEMENT"],
        "task": {"type": "CANCEL_ENTITY", "description": "Cancel an order before shipment"},
        "inputs": [
            {"name": "order_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {
                "name": "reason",
                "type": "ENUM",
                "required": True,
                "source": "USER",
                "enum_values": ["CUSTOMER_REQUEST", "DUPLICATE", "OUT_OF_STOCK", "OTHER"],
            },
        ],
        "outputs": {"type": "STATUS", "entity_type": "ORDER"},
        "side_effect": {"has_side_effect": True, "type": "STATE_CHANGE", "reversible": "PARTIALLY_REVERSIBLE"},
        "risk": {"level": "MEDIUM", "categories": ["CUSTOMER_IMPACT", "FINANCIAL"]},
        "preconditions": ["ORDER_EXISTS", "ORDER_NOT_SHIPPED"],
        "postconditions": ["ORDER_CANCELLED"],
    },
    "place_order": {
        "name": "place_order",
        "description": "Submit a customer's cart as an order and charge the given payment method.",
        "primitive": "EXECUTE",
        "domain": ["ORDER_MANAGEMENT", "PAYMENTS"],
        "task": {"type": "PLACE_ORDER", "description": "Submit the customer's cart as an order"},
        "inputs": [
            {"name": "customer_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "cart_id", "type": "IDENTIFIER", "required": True, "source": "TOOL_OUTPUT"},
            {
                "name": "payment_method",
                "type": "ENUM",
                "required": True,
                "source": "USER",
                "enum_values": ["SAVED_CARD", "PAYPAL", "GIFT_CARD"],
            },
        ],
        "outputs": {"type": "ENTITY", "entity_type": "ORDER"},
        "side_effect": {"has_side_effect": True, "type": "FINANCIAL_TRANSACTION", "reversible": "PARTIALLY_REVERSIBLE"},
        "risk": {"level": "HIGH", "categories": ["FINANCIAL", "CUSTOMER_IMPACT"]},
        "preconditions": ["CART_EXISTS", "CART_NOT_EMPTY", "SUFFICIENT_INVENTORY"],
        "postconditions": ["ORDER_CREATED", "CART_CLEARED", "INVENTORY_DECREMENTED"],
    },
    "issue_refund": {
        "name": "issue_refund",
        "description": "Issue a refund against a paid order.",
        "primitive": "EXECUTE",
        "domain": ["PAYMENTS"],
        "task": {"type": "MAKE_PAYMENT", "description": "Refund an amount to the customer for an order"},
        "inputs": [
            {"name": "order_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "amount", "type": "FLOAT", "required": True, "source": "USER"},
            {
                "name": "reason",
                "type": "ENUM",
                "required": True,
                "source": "USER",
                "enum_values": ["DAMAGED_ITEM", "WRONG_ITEM", "CUSTOMER_REQUEST", "DUPLICATE_CHARGE"],
            },
        ],
        "outputs": {"type": "RECORD", "entity_type": "REFUND"},
        "side_effect": {"has_side_effect": True, "type": "FINANCIAL_TRANSACTION", "reversible": "IRREVERSIBLE"},
        "risk": {"level": "HIGH", "categories": ["FINANCIAL"]},
        "preconditions": ["ORDER_EXISTS", "ORDER_PAID", "REFUND_AMOUNT_WITHIN_ORDER_TOTAL"],
        "postconditions": ["REFUND_ISSUED"],
    },
    "calculate_order_total": {
        "name": "calculate_order_total",
        "description": "Calculate the total cost for a list of SKU/quantity pairs, including tax.",
        "primitive": "COMPUTE",
        "domain": ["PRICING"],
        "task": {"type": "CALCULATE", "description": "Calculate an order's total cost"},
        "inputs": [
            {"name": "sku_quantities", "type": "ARRAY", "required": True, "source": "USER"},
            {"name": "tax_rate", "type": "FLOAT", "required": False, "source": "SYSTEM"},
        ],
        "outputs": {"type": "NUMBER"},
        "side_effect": {"has_side_effect": False, "type": "NONE", "reversible": "NOT_APPLICABLE"},
        "risk": {"level": "NONE", "categories": ["NONE"]},
        "preconditions": ["ALL_PRODUCTS_EXIST"],
        "postconditions": [],
    },
    "create_support_ticket": {
        "name": "create_support_ticket",
        "description": "Create a customer support ticket for an issue that needs human follow-up.",
        "primitive": "CREATE",
        "domain": ["CUSTOMER_SERVICE"],
        "task": {"type": "CREATE_REQUEST", "description": "Create a support ticket"},
        "inputs": [
            {"name": "customer_id", "type": "IDENTIFIER", "required": True, "source": "USER"},
            {"name": "subject", "type": "STRING", "required": True, "source": "AGENT"},
            {"name": "description", "type": "STRING", "required": True, "source": "AGENT"},
            {
                "name": "priority",
                "type": "ENUM",
                "required": True,
                "source": "AGENT",
                "enum_values": ["LOW", "MEDIUM", "HIGH", "URGENT"],
            },
        ],
        "outputs": {"type": "ENTITY", "entity_type": "TICKET"},
        "side_effect": {"has_side_effect": True, "type": "RESOURCE_ALLOCATION", "reversible": "REVERSIBLE"},
        "risk": {"level": "LOW", "categories": ["OPERATIONAL"]},
        "preconditions": [],
        "postconditions": ["TICKET_CREATED"],
    },
}


# ---------------------------------------------------------------------------
# 2. Implementations — enforce preconditions against a RetailStore for real
# ---------------------------------------------------------------------------

def _err(code: str, message: str) -> Dict[str, Any]:
    return {"status": "PRECONDITION_FAILED", "error": {"code": code, "message": message}, "output": None}


def _ok(output: Any) -> Dict[str, Any]:
    return {"status": "SUCCESS", "error": None, "output": output}


def _search_products(store: RetailStore, query: str, max_price: float = None) -> Dict[str, Any]:
    query_lower = (query or "").lower()
    matches = []
    for sku, product in store.products.items():
        if query_lower and query_lower not in product["name"].lower() and query_lower not in product["category"].lower():
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        matches.append({"sku": sku, **product})
    return _ok(matches)


def _check_inventory(store: RetailStore, sku: str) -> Dict[str, Any]:
    if sku not in store.products:
        return _err("PRODUCT_EXISTS", f"No product with SKU {sku}")
    return _ok({"sku": sku, "quantity_in_stock": store.inventory.get(sku, 0)})


def _get_order_status(store: RetailStore, order_id: str) -> Dict[str, Any]:
    order = store.orders.get(order_id)
    if order is None:
        return _err("ORDER_EXISTS", f"No order with id {order_id}")
    return _ok(dict(order, order_id=order_id))


def _add_item_to_cart(store: RetailStore, cart_id: str, sku: str, quantity: int) -> Dict[str, Any]:
    if cart_id not in store.carts:
        return _err("CART_EXISTS", f"No cart with id {cart_id}")
    if sku not in store.products:
        return _err("PRODUCT_EXISTS", f"No product with SKU {sku}")
    available = store.inventory.get(sku, 0)
    if quantity > available:
        return _err("SUFFICIENT_INVENTORY", f"Only {available} of {sku} in stock, requested {quantity}")
    cart = store.carts[cart_id]
    cart.setdefault("items", [])
    cart["items"].append({"sku": sku, "quantity": quantity})
    return _ok({"cart_id": cart_id, "items": cart["items"]})


def _update_shipping_address(store: RetailStore, order_id: str, address: str) -> Dict[str, Any]:
    order = store.orders.get(order_id)
    if order is None:
        return _err("ORDER_EXISTS", f"No order with id {order_id}")
    if order.get("status") in ("shipped", "delivered"):
        return _err("ORDER_NOT_SHIPPED", f"Order {order_id} has already shipped; address can't be changed")
    order["shipping_address"] = address
    return _ok({"order_id": order_id, "shipping_address": address})


def _cancel_order(store: RetailStore, order_id: str, reason: str) -> Dict[str, Any]:
    order = store.orders.get(order_id)
    if order is None:
        return _err("ORDER_EXISTS", f"No order with id {order_id}")
    if order.get("status") in ("shipped", "delivered"):
        return _err("ORDER_NOT_SHIPPED", f"Order {order_id} has already shipped and can't be cancelled")
    order["status"] = "cancelled"
    order["cancellation_reason"] = reason
    return _ok({"order_id": order_id, "status": "cancelled"})


def _place_order(store: RetailStore, customer_id: str, cart_id: str, payment_method: str) -> Dict[str, Any]:
    cart = store.carts.get(cart_id)
    if cart is None:
        return _err("CART_EXISTS", f"No cart with id {cart_id}")
    items = cart.get("items", [])
    if not items:
        return _err("CART_NOT_EMPTY", f"Cart {cart_id} is empty")
    for item in items:
        available = store.inventory.get(item["sku"], 0)
        if item["quantity"] > available:
            return _err(
                "SUFFICIENT_INVENTORY",
                f"Only {available} of {item['sku']} in stock, cart requests {item['quantity']}",
            )
    total = sum(store.products[item["sku"]]["price"] * item["quantity"] for item in items)
    order_id = f"ORD-{1000 + len(store.orders) + 1}"
    for item in items:
        store.inventory[item["sku"]] -= item["quantity"]
    store.orders[order_id] = {
        "customer_id": customer_id,
        "items": items,
        "status": "processing",
        "paid": True,
        "payment_method": payment_method,
        "total": round(total, 2),
    }
    cart["items"] = []
    return _ok({"order_id": order_id, "total": round(total, 2), "status": "processing"})


def _issue_refund(store: RetailStore, order_id: str, amount: float, reason: str) -> Dict[str, Any]:
    order = store.orders.get(order_id)
    if order is None:
        return _err("ORDER_EXISTS", f"No order with id {order_id}")
    if not order.get("paid"):
        return _err("ORDER_PAID", f"Order {order_id} was never paid; nothing to refund")
    already_refunded = order.get("refunded_amount", 0.0)
    if already_refunded + amount > order.get("total", 0.0) + 1e-6:
        return _err(
            "REFUND_AMOUNT_WITHIN_ORDER_TOTAL",
            f"Refund of {amount} would exceed order total {order.get('total')} (already refunded {already_refunded})",
        )
    order["refunded_amount"] = round(already_refunded + amount, 2)
    return _ok({"order_id": order_id, "refunded_amount": order["refunded_amount"], "reason": reason})


def _calculate_order_total(store: RetailStore, sku_quantities: List[Dict[str, Any]], tax_rate: float = 0.0) -> Dict[str, Any]:
    subtotal = 0.0
    for entry in sku_quantities:
        sku = entry["sku"]
        qty = entry["quantity"]
        if sku not in store.products:
            return _err("ALL_PRODUCTS_EXIST", f"No product with SKU {sku}")
        subtotal += store.products[sku]["price"] * qty
    total = subtotal * (1 + (tax_rate or 0.0))
    return _ok({"subtotal": round(subtotal, 2), "tax_rate": tax_rate or 0.0, "total": round(total, 2)})


def _create_support_ticket(store: RetailStore, customer_id: str, subject: str, description: str, priority: str) -> Dict[str, Any]:
    ticket_id = store.new_ticket_id()
    store.tickets[ticket_id] = {
        "customer_id": customer_id,
        "subject": subject,
        "description": description,
        "priority": priority,
        "status": "open",
    }
    return _ok({"ticket_id": ticket_id, "status": "open"})


TOOL_IMPLS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "search_products": _search_products,
    "check_inventory": _check_inventory,
    "get_order_status": _get_order_status,
    "add_item_to_cart": _add_item_to_cart,
    "update_shipping_address": _update_shipping_address,
    "cancel_order": _cancel_order,
    "place_order": _place_order,
    "issue_refund": _issue_refund,
    "calculate_order_total": _calculate_order_total,
    "create_support_ticket": _create_support_ticket,
}


def call_tool(store: RetailStore, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a tool by name against a store. Used by every agent adapter."""
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"status": "UNKNOWN_TOOL", "error": {"code": "UNKNOWN_TOOL", "message": f"No such tool: {name}"}, "output": None}
    try:
        return impl(store, **arguments)
    except TypeError as exc:
        return {"status": "INVALID_ARGUMENTS", "error": {"code": "INVALID_ARGUMENTS", "message": str(exc)}, "output": None}


# ---------------------------------------------------------------------------
# 3. LangChain bindings (Agent A) — thin wrappers over TOOL_IMPLS/call_tool
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "STRING": str,
    "INTEGER": int,
    "FLOAT": float,
    "BOOLEAN": bool,
    "DATE": str,
    "DATETIME": str,
    "ENUM": str,
    "OBJECT": dict,
    "ARRAY": list,
    "FILE": str,
    "URL": str,
    "IDENTIFIER": str,
}


def _args_model(name: str, schema: Dict[str, Any]):
    from pydantic import Field, create_model

    fields = {}
    for inp in schema["inputs"]:
        py_type = _TYPE_MAP[inp["type"]]
        desc = inp["type"]
        if inp.get("enum_values"):
            desc += f" one of {inp['enum_values']}"
        if inp["required"]:
            fields[inp["name"]] = (py_type, Field(..., description=desc))
        else:
            fields[inp["name"]] = (Optional[py_type], Field(default=None, description=desc))
    return create_model(f"{name}_Args", **fields)


def build_langchain_tools(store: RetailStore) -> List[Any]:
    from langchain_core.tools import StructuredTool

    def make(name: str):
        schema = TOOL_SCHEMAS[name]
        args_model = _args_model(name, schema)

        def _run(**kwargs) -> str:
            import json
            return json.dumps(call_tool(store, name, kwargs))

        return StructuredTool.from_function(
            func=_run,
            name=name,
            description=schema["description"],
            args_schema=args_model,
        )

    return [make(name) for name in TOOL_SCHEMAS]
