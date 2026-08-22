"""Mock retail backend that pilot tools operate against.

Each task gets a fresh RetailStore, seeded per-task (tasks.json's "seed" field),
so tool calls have real, checkable state to read and mutate. Preconditions and
postconditions in SCHEMA.md are checked against this store, not against what the
agent claims happened.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_PRODUCTS = {
    "SKU-1001": {"name": "Wireless Earbuds Pro", "price": 79.99, "category": "audio"},
    "SKU-2004": {"name": "Noise Cancelling Headphones", "price": 149.99, "category": "audio"},
    "SKU-3001": {"name": "USB-C Charging Cable", "price": 12.99, "category": "accessories"},
    "SKU-4002": {"name": "Bluetooth Speaker Mini", "price": 39.99, "category": "audio"},
    "SKU-5003": {"name": "Smartwatch Series 3", "price": 199.99, "category": "wearables"},
}


@dataclass
class RetailStore:
    """In-memory world state for one pilot task run."""

    products: Dict[str, Dict[str, Any]] = field(default_factory=lambda: copy.deepcopy(DEFAULT_PRODUCTS))
    inventory: Dict[str, int] = field(default_factory=dict)
    carts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    orders: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tickets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _next_ticket_id: int = 9000

    @classmethod
    def from_seed(cls, seed: Optional[Dict[str, Any]]) -> "RetailStore":
        store = cls()
        seed = seed or {}
        store.inventory = dict(seed.get("inventory", {}))
        store.carts = copy.deepcopy(seed.get("carts", {}))
        store.orders = copy.deepcopy(seed.get("orders", {}))
        store.tickets = copy.deepcopy(seed.get("tickets", {}))
        if "products" in seed:
            store.products.update(copy.deepcopy(seed["products"]))
        return store

    def snapshot(self) -> Dict[str, Any]:
        return {
            "products": copy.deepcopy(self.products),
            "inventory": copy.deepcopy(self.inventory),
            "carts": copy.deepcopy(self.carts),
            "orders": copy.deepcopy(self.orders),
            "tickets": copy.deepcopy(self.tickets),
        }

    def new_ticket_id(self) -> str:
        self._next_ticket_id += 1
        return f"TCK-{self._next_ticket_id}"
