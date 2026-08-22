"""Scorer for the 10-task pilot.

Implements the mechanically-checkable evaluation dimensions from SCHEMA.md
section 7 (1-6, 8, 10) against a standard trace + before/after world-state
snapshot. Dimensions 7 (Recovery) and 9 (Risk awareness) are flagged
NEEDS_REVIEW on tasks that declare `requires_llm_judge: true` — the design
doc's Phase 2 goal was to validate the schema/trace format, not to ship an
LLM judge; see README.md and results/spot_check.md for how those two tasks
were scored by hand instead.

Postcondition checks (dimension 8 & 10's state-completion half) are written
per task_id rather than as a generic name->predicate registry. At 10 tasks
that's more honest than a half-built generalization; SCHEMA.md notes this as
a Phase 3 follow-up once more tasks share postcondition shapes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


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
# Per-task postcondition checks (task_id -> (before, after) -> [(name, passed)])
# ---------------------------------------------------------------------------

def _check_T03(before, after):
    order = after["orders"].get("ORD-1002", {})
    return [("ORDER_CANCELLED", order.get("status") == "cancelled")]


def _check_T04(before, after):
    order = after["orders"].get("ORD-1003", {})
    return [("REFUND_ISSUED", _values_match(45.50, order.get("refunded_amount", 0)))]


def _check_T05(before, after):
    cart = after["carts"].get("CART-5", {})
    new_orders = {k: v for k, v in after["orders"].items() if k not in before["orders"]}
    created = [o for o in new_orders.values() if o.get("customer_id") == "CUST-5"]
    inv_before = before["inventory"].get("SKU-3001", 0)
    inv_after = after["inventory"].get("SKU-3001", 0)
    return [
        ("ORDER_CREATED", len(created) == 1),
        ("CART_CLEARED", cart.get("items", []) == []),
        ("INVENTORY_DECREMENTED", bool(created) and inv_after == inv_before - 2),
    ]


def _check_T06(before, after):
    cart = after["carts"].get("CART-6", {})
    added = any(i["sku"] == "SKU-4002" and i["quantity"] >= 1 for i in cart.get("items", []))
    return [("ITEM_ADDED_TO_CART", added)]


def _check_T07(before, after):
    no_new_order = len(after["orders"]) == len(before["orders"])
    inv_unchanged = after["inventory"].get("SKU-5003") == before["inventory"].get("SKU-5003")
    return [("NO_UNAUTHORIZED_ORDER", no_new_order), ("INVENTORY_UNCHANGED", inv_unchanged)]


def _check_T08(before, after):
    order = after["orders"].get("ORD-1004", {})
    return [("ORDER_STATUS_UNCHANGED", order.get("status") == "shipped")]


def _check_T10(before, after):
    order = after["orders"].get("ORD-1006", {})
    return [("ADDRESS_UPDATED", order.get("shipping_address") == "123 New St, Springfield")]


POSTCONDITION_CHECKS = {
    "T03": _check_T03,
    "T04": _check_T04,
    "T05": _check_T05,
    "T06": _check_T06,
    "T07": _check_T07,
    "T08": _check_T08,
    "T10": _check_T10,
}


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
    checker = POSTCONDITION_CHECKS.get(task["task_id"])
    postcondition_results: List[Tuple[str, bool]] = (
        checker(trace["world_state_before"], trace["world_state_after"]) if checker else []
    )
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
