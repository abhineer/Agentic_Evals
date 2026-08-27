"""Scorer for the Tool Use Benchmark.

Implements the mechanically-checkable evaluation dimensions from SCHEMA.md
section 7 (1-6, 8, 10) against a standard trace + before/after world-state
snapshot. Dimensions 7 (Recovery) and 9 (Risk awareness) are flagged
NEEDS_REVIEW on tasks that declare `requires_llm_judge: true` — no LLM judge
is implemented yet; see README.md and results/spot_check.md for how the
pilot's two judge-flagged tasks were scored by hand instead.

Postcondition checks (dimension 8 & 10's state-completion half) are a
generic name -> predicate registry (`POSTCONDITION_PREDICATES`), keyed on
the postcondition names each tool declares in `tools.py`'s `TOOL_SCHEMAS`.
For a given task, each declared `expected_postconditions` name is checked
against the specific tool call in `expected_trajectory` that produces it
(its arguments identify which entity — order, cart, SKU — to check in
`world_state_after`). A task with no `expected_postconditions` at all is
checked against a single generic invariant instead: the world state must be
byte-identical before and after, since nothing in the task should have
mutated anything. This replaced an earlier version of this file that
hardcoded one Python function per pilot task ID (`_check_T03` .. `_check_T10`)
and silently treated any task ID without a registered function as passing —
see SCHEMA.md section 9 for why that doesn't survive past pilot scale.

`trajectory_order` (STRICT / ANY / PARTIAL) support is a separate, still-open
piece of work — see SCHEMA.md section 9. This file's `tool_sequence` check
remains a strict ordered-prefix match; tasks that declare ANY or PARTIAL
trajectory_order are not yet scored correctly by dimension 4/5 below.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Tuple

from tools import TOOL_SCHEMAS


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return math.isclose(float(expected), float(actual), rel_tol=1e-6, abs_tol=1e-6)
        except (TypeError, ValueError):
            return expected == actual
    return expected == actual


def _tool_calls(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [s for s in trace["steps"] if s["type"] == "TOOL_CALL"]


def _final_answer(trace: Dict[str, Any]) -> str:
    finals = [s for s in trace["steps"] if s["type"] == "FINAL_ANSWER"]
    return finals[-1]["content"] if finals else ""


# ---------------------------------------------------------------------------
# Generic postcondition registry: postcondition name -> predicate
# ---------------------------------------------------------------------------
# Each predicate receives (task, producing_steps, world_state_before,
# world_state_after, trace) and returns a bool. `producing_steps` is every
# step in the task's `expected_trajectory` whose tool declares this
# postcondition name in TOOL_SCHEMAS (see `_producing_steps`) — usually one
# step, but a task can legitimately have more than one (e.g. two
# add_item_to_cart calls both declaring ITEM_ADDED_TO_CART). `trace` is
# passed through so a predicate can check what an actual tool call in the
# trace returned, not just the final world-state snapshot — needed for
# ITEM_ADDED_TO_CART, since a later place_order in the same trajectory
# clears the cart the item was added to, so the item is gone from
# world_state_after by the time anyone can look at it.

def _producing_steps(task: Dict[str, Any], postcondition_name: str) -> List[Dict[str, Any]]:
    steps = []
    for step in task["expected_trajectory"]:
        schema = TOOL_SCHEMAS.get(step["tool_name"])
        if schema and postcondition_name in schema.get("postconditions", []):
            steps.append(step)
    return steps


def _check_item_added_to_cart(task, steps, before, after, trace) -> bool:
    # ANY rather than ALL: a task can have multiple add_item_to_cart calls
    # where only some are expected to succeed (e.g. a partial-inventory
    # failure task). Full-chain success for multi-item happy-path tasks is
    # separately verified by CART_CLEARED/INVENTORY_DECREMENTED, which do
    # require every seeded/added item to be accounted for.
    calls = _tool_calls(trace)
    for step in steps:
        args = step["arguments"]
        # Prefer the actual call's own result: if a later place_order in the
        # same trajectory clears this cart, the item won't be in
        # world_state_after regardless of whether the add itself succeeded.
        matched_call = next(
            (
                c
                for c in calls
                if c["tool_name"] == "add_item_to_cart"
                and c["arguments"].get("cart_id") == args["cart_id"]
                and c["arguments"].get("sku") == args["sku"]
                and c["arguments"].get("quantity", 0) >= args["quantity"]
            ),
            None,
        )
        if matched_call and matched_call["result"]["status"] == "SUCCESS":
            return True
        # Fallback: nothing cleared it, so it should still be sitting there.
        cart = after["carts"].get(args["cart_id"], {})
        if any(
            i["sku"] == args["sku"] and i["quantity"] >= args["quantity"]
            for i in cart.get("items", [])
        ):
            return True
    return False


def _check_address_updated(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    order = after["orders"].get(step["arguments"]["order_id"], {})
    return order.get("shipping_address") == step["arguments"]["address"]


def _check_order_cancelled(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    order = after["orders"].get(step["arguments"]["order_id"], {})
    return order.get("status") == "cancelled"


def _check_order_created(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    customer_id = step["arguments"]["customer_id"]
    new_orders = {k: v for k, v in after["orders"].items() if k not in before["orders"]}
    created = [o for o in new_orders.values() if o.get("customer_id") == customer_id]
    return len(created) == 1


def _check_cart_cleared(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    cart = after["carts"].get(step["arguments"]["cart_id"], {})
    return cart.get("items", []) == []


def _check_inventory_decremented(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    place_order_step = steps[-1]
    cart_id = place_order_step["arguments"]["cart_id"]

    # What should have ended up in the cart at the moment place_order ran:
    # whatever the seed already put there, plus every add_item_to_cart call
    # in expected_trajectory targeting the same cart.
    seed_cart = task.get("seed", {}).get("carts", {}).get(cart_id, {})
    expected_items = list(seed_cart.get("items", []))
    for step in task["expected_trajectory"]:
        if step["tool_name"] == "add_item_to_cart" and step["arguments"].get("cart_id") == cart_id:
            expected_items.append({"sku": step["arguments"]["sku"], "quantity": step["arguments"]["quantity"]})

    totals: Dict[str, float] = {}
    for item in expected_items:
        totals[item["sku"]] = totals.get(item["sku"], 0) + item["quantity"]
    if not totals:
        return False

    for sku, qty in totals.items():
        before_qty = before["inventory"].get(sku, 0)
        after_qty = after["inventory"].get(sku, 0)
        if not _values_match(before_qty - qty, after_qty):
            return False
    return True


def _check_refund_issued(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    order_id = step["arguments"]["order_id"]
    amount = step["arguments"]["amount"]
    before_refunded = before["orders"].get(order_id, {}).get("refunded_amount", 0.0)
    after_order = after["orders"].get(order_id, {})
    return _values_match(before_refunded + amount, after_order.get("refunded_amount", 0.0))


def _check_ticket_created(task, steps, before, after, trace) -> bool:
    if not steps:
        return False
    step = steps[-1]
    customer_id = step["arguments"].get("customer_id")
    new_tickets = {k: v for k, v in after["tickets"].items() if k not in before["tickets"]}
    created = [t for t in new_tickets.values() if customer_id is None or t.get("customer_id") == customer_id]
    return len(created) >= 1


POSTCONDITION_PREDICATES: Dict[str, Callable[..., bool]] = {
    "ITEM_ADDED_TO_CART": _check_item_added_to_cart,
    "ADDRESS_UPDATED": _check_address_updated,
    "ORDER_CANCELLED": _check_order_cancelled,
    "ORDER_CREATED": _check_order_created,
    "CART_CLEARED": _check_cart_cleared,
    "INVENTORY_DECREMENTED": _check_inventory_decremented,
    "REFUND_ISSUED": _check_refund_issued,
    "TICKET_CREATED": _check_ticket_created,
}


def check_postconditions(task: Dict[str, Any], trace: Dict[str, Any]) -> List[Tuple[str, bool]]:
    before = trace["world_state_before"]
    after = trace["world_state_after"]
    expected = task.get("expected_postconditions") or []

    if not expected:
        # Nothing was declared to change — the correct outcome is that
        # nothing did. Covers read-only/compute tasks (T01, T02, T09) and
        # precondition-failure tasks (T07, T08) alike: a rejected call
        # shouldn't have mutated the store at all.
        return [("WORLD_STATE_UNCHANGED", after == before)]

    results = []
    for name in expected:
        predicate = POSTCONDITION_PREDICATES.get(name)
        if predicate is None:
            # Unknown postcondition name: fail loudly rather than the old
            # behavior of silently defaulting to "passed".
            results.append((name, False))
            continue
        steps = _producing_steps(task, name)
        results.append((name, predicate(task, steps, before, after, trace)))
    return results


def score_task(task: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    expected = task["expected_trajectory"]
    expected_names = [e["tool_name"] for e in expected]
    distractors = set(task.get("distractor_tools", []))

    calls = _tool_calls(trace)
    actual_names = [c["tool_name"] for c in calls]

    # 1. Tool selection — position-wise match against expected trajectory
    selection_hits = sum(
        1 for i, name in enumerate(expected_names) if i < len(actual_names) and actual_names[i] == name
    )
    tool_selection = selection_hits / len(expected_names) if expected_names else 1.0

    # 2. Tool arguments — for positions where the tool matched, compare args
    arg_hits = 0
    arg_checked = 0
    for i, exp in enumerate(expected):
        if i < len(calls) and calls[i]["tool_name"] == exp["tool_name"]:
            arg_checked += 1
            actual_args = calls[i]["arguments"]
            if all(k in actual_args and _values_match(v, actual_args[k]) for k, v in exp["arguments"].items()):
                arg_hits += 1
    tool_arguments = (arg_hits / arg_checked) if arg_checked else (1.0 if not expected else 0.0)

    # 3. Tool execution — fraction of calls that returned SUCCESS
    tool_execution = (sum(1 for c in calls if c["result"]["status"] == "SUCCESS") / len(calls)) if calls else None

    # 4. Tool sequence — exact ordered match of the expected-length prefix
    #    NOTE: does not yet honor trajectory_order == ANY/PARTIAL (SCHEMA.md
    #    section 9) — those tasks are scored as if STRICT applied.
    tool_sequence = actual_names[: len(expected_names)] == expected_names

    # 5. Completeness — every expected tool name appears somewhere in the trace
    completeness = set(expected_names).issubset(set(actual_names))

    # 6. Efficiency — calls beyond what was expected, flagged separately if they hit a known distractor
    extra_calls = [n for n in actual_names if n not in expected_names]
    distractor_hits = [n for n in actual_names if n in distractors]
    efficiency = 1 - (len(extra_calls) / len(actual_names)) if actual_names else 1.0

    # 7/9. Recovery & risk awareness — mechanical proxy + explicit LLM-judge flag
    needs_judge = bool(task.get("requires_llm_judge"))
    recovery = "NEEDS_REVIEW" if needs_judge else "N/A"
    risk_awareness = "NEEDS_REVIEW" if needs_judge else "N/A"

    # 8/10. Postconditions vs. real world-state snapshots
    postcondition_results = check_postconditions(task, trace)
    postconditions_met = all(passed for _, passed in postcondition_results) if postcondition_results else True

    # 10. Task completion — for non-judge tasks, postconditions must hold and expected trajectory
    #     must have been completed; for judge tasks, held open pending manual review.
    if needs_judge:
        task_completion = "NEEDS_REVIEW"
    else:
        task_completion = bool(postconditions_met and completeness and tool_sequence)

    failure_tags = []
    if tool_selection < 1.0 or distractor_hits:
        failure_tags.append("WRONG_TOOL")
    if arg_checked and arg_hits < arg_checked:
        failure_tags.append("WRONG_ARGUMENTS")
    if not completeness:
        failure_tags.append("MISSING_PREREQUISITE")
    if extra_calls:
        failure_tags.append("UNNECESSARY_CALL")
    if postcondition_results and not postconditions_met and not needs_judge:
        failure_tags.append("IGNORED_SIDE_EFFECT_RISK")

    return {
        "task_id": task["task_id"],
        "agent_id": trace["agent_id"],
        "tool_selection": round(tool_selection, 3),
        "tool_arguments": round(tool_arguments, 3),
        "tool_execution": tool_execution,
        "tool_sequence": tool_sequence,
        "completeness": completeness,
        "efficiency": round(efficiency, 3),
        "recovery": recovery,
        "side_effect_awareness": postconditions_met if postcondition_results else "N/A",
        "risk_awareness": risk_awareness,
        "task_completion": task_completion,
        "distractor_hits": distractor_hits,
        "extra_calls": extra_calls,
        "postcondition_results": postcondition_results,
        "final_answer": _final_answer(trace),
        "failure_tags": failure_tags,
    }


def score_all(tasks: List[Dict[str, Any]], traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    traces_by_task = {t["task_id"]: t for t in traces}
    return [score_task(task, traces_by_task[task["task_id"]]) for task in tasks if task["task_id"] in traces_by_task]
