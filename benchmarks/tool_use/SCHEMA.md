# Tool Use Benchmark — Schema

Finalized for the Phase 1 (Specification) + Phase 2 (10-task pilot) stage of the
Tool Use Benchmark, per `Agentic_Evals_Tool_Use_Benchmark_Design.md`. This is the
schema the pilot tool set, pilot tasks, and harness in this directory implement.

Nothing here contradicts the design doc. Where the design doc offered a broad
initial vocabulary, this document narrows it to what the pilot's 10 tools and 10
tasks actually use — the rest of each controlled vocabulary stays available for
Phase 3/4 without a schema change.

## 1. Primitive Taxonomy

Adopted as-is from the design doc — no gap surfaced while drafting the pilot tools:

```text
READ      Retrieve known information/state
SEARCH    Find entities matching criteria
CREATE    Create a new entity/resource
UPDATE    Modify an existing entity
DELETE    Remove/cancel an entity
EXECUTE   Cause an external action/side effect
COMPUTE   Calculate or derive information
```

## 2. Domain Vocabulary (Pilot Subset)

The design doc lists ~30 domains. The pilot tool set only needs six:

```text
ECOMMERCE
PRODUCT_CATALOG
INVENTORY
ORDER_MANAGEMENT
PAYMENTS
PRICING
CUSTOMER_SERVICE
```

A tool may belong to more than one domain (e.g. `place_order` is both
`ORDER_MANAGEMENT` and `PAYMENTS`). The remaining ~24 domains from the design doc
stay in the controlled vocabulary for later phases; do not populate them until a
tool actually needs one.

## 3. Task Schema

Controlled `type` + free-form `description`, exactly as specified:

```json
{
  "task": {
    "type": "CANCEL_ENTITY",
    "description": "Cancel an existing order before it ships"
  }
}
```

Task types actually used by the pilot's 10 tools (a subset of the design doc's
suggested list):

```text
GET_STATUS            get_order_status
SEARCH_ENTITY         search_products
GET_DETAILS           check_inventory
ADD_ITEM              add_item_to_cart
UPDATE_ENTITY         update_shipping_address
CANCEL_ENTITY         cancel_order
PLACE_ORDER           place_order
MAKE_PAYMENT          issue_refund
CALCULATE             calculate_order_total
CREATE_REQUEST        create_support_ticket
```

## 4. Tool Representation

Full schema — every field below is required on every tool in `tools.py`.

```json
{
  "tool": {
    "name": "string, matches the callable name",
    "description": "string, shown to the agent",

    "primitive": "one of the 7 primitives",

    "domain": ["one or more domain values"],

    "task": {
      "type": "controlled task type",
      "description": "free-form"
    },

    "inputs": [
      {
        "name": "string",
        "type": "STRING | INTEGER | FLOAT | BOOLEAN | DATE | DATETIME | ENUM | OBJECT | ARRAY | FILE | URL | IDENTIFIER",
        "required": true,
        "source": "USER | AGENT | TOOL_OUTPUT | MEMORY | SYSTEM | ENVIRONMENT | EXTERNAL"
      }
    ],

    "outputs": {
      "type": "ENTITY | ENTITY_LIST | RECORD | RECORD_LIST | STATUS | BOOLEAN | NUMBER | STRING | OBJECT | FILE | URL | MESSAGE | ERROR",
      "entity_type": "optional, e.g. ORDER, PRODUCT, TICKET"
    },

    "side_effect": {
      "has_side_effect": true,
      "type": "NONE | READ_ONLY | STATE_CHANGE | EXTERNAL_ACTION | COMMUNICATION | FINANCIAL_TRANSACTION | DATA_DELETION | SECURITY_CHANGE | RESOURCE_ALLOCATION",
      "reversible": "REVERSIBLE | PARTIALLY_REVERSIBLE | IRREVERSIBLE | NOT_APPLICABLE"
    },

    "risk": {
      "level": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
      "categories": ["NONE | FINANCIAL | PRIVACY | SECURITY | DATA_LOSS | CUSTOMER_IMPACT | LEGAL | COMPLIANCE | REPUTATIONAL | OPERATIONAL | SAFETY | ACCESS_CONTROL"]
    },

    "preconditions": ["symbolic condition names, checked against benchmark world state before the call"],
    "postconditions": ["symbolic condition names, checked against benchmark world state after the call"]
  }
}
```

This is unchanged from the design doc's section 9 — drafting the 10 pilot tools
did not surface a need to add or remove a field.

## 5. Standard Trace Format

This is what makes the benchmark agent/framework-independent: every agent
adapter, regardless of framework (LangChain, a manual ReAct loop, an SDK-native
tool-calling agent, etc.), normalizes its run into this JSON shape before
scoring ever sees it. The scorer only ever reads traces in this format — it has
no framework-specific code path.

```json
{
  "task_id": "T01",
  "agent_id": "agent_a_langchain_groq",
  "started_at": "2026-08-22T10:00:00Z",
  "finished_at": "2026-08-22T10:00:03Z",

  "steps": [
    {
      "step_index": 0,
      "type": "TOOL_CALL",
      "tool_name": "get_order_status",
      "arguments": {"order_id": "ORD-1001"},
      "result": {
        "status": "SUCCESS",
        "output": { "...": "..." },
        "error": null
      },
      "latency_ms": 412
    },
    {
      "step_index": 1,
      "type": "FINAL_ANSWER",
      "content": "Order ORD-1001 is currently In Transit."
    }
  ],

  "world_state_before": { "...": "snapshot of the mock store" },
  "world_state_after": { "...": "snapshot of the mock store" },

  "raw_agent_output": "optional, framework-native trace for debugging only — never scored directly"
}
```

Rules for adapters producing a trace:

- Every tool invocation the agent makes — successful, failed, or malformed —
  becomes one `TOOL_CALL` step, in the order the agent made it. Nothing is
  reordered or deduplicated by the adapter.
- A tool call the agent attempted with arguments that don't match the tool's
  schema is still recorded as a `TOOL_CALL` step with `result.status: "SUCCESS"`
  replaced by `"INVALID_ARGUMENTS"` — the scorer decides what that means, the
  adapter doesn't.
- The final natural-language response is always the last step, `type:
  "FINAL_ANSWER"`.
- `world_state_before` / `world_state_after` are snapshots of the mock retail
  store (`tools.py`'s `RetailStore`), used to check postconditions
  independently of what the agent claims happened.
- `raw_agent_output` is kept for human debugging (e.g. LangChain's
  `intermediate_steps`) but the scorer must never read it — that would leak a
  framework-specific shortcut into a benchmark meant to be framework-independent.

## 6. Failure Taxonomy (Tool-Use Scoped)

Scoped specifically to tool-use failures, distinct from the broader, cross-cutting
Agent Failure Taxonomy tracked in issue #7.

```text
WRONG_TOOL              Agent called a tool other than an expected/acceptable one
                         for the task (includes wrong-tool-temptation failures).

WRONG_ARGUMENTS          Agent called the right tool with incorrect, missing, or
                         malformed argument values.

MISSING_PREREQUISITE     Agent called a tool before a required precondition was
                         satisfied (e.g. cancel_order before checking order status,
                         place_order with an empty cart).

UNNECESSARY_CALL         Agent called a tool that wasn't needed to complete the
                         task (redundant lookups, calls whose output goes unused).

NO_RECOVERY              A tool call failed (simulated failure or a genuine
                         precondition violation) and the agent did not adapt —
                         it either gave up silently, hallucinated a success, or
                         retried the identical call without changing anything.

IGNORED_SIDE_EFFECT_RISK Agent invoked a tool with real side effects or non-NONE
                         risk without appropriate care (e.g. no confirmation-style
                         check before an EXECUTE/DELETE call marked HIGH risk,
                         or skipped a precondition check the tool declares as
                         a state-change guard).
```

Each pilot task in `tasks.json` declares which of these failure modes it's
designed to stress-test (`stress_tests` field), so a scored run can be read
against intent, not just against pass/fail.

## 7. Evaluation Dimensions

From the design doc's section 12, with a note on how each is scored in the
pilot harness (`harness/scorer.py`):

| # | Dimension | Pilot scoring |
|---|---|---|
| 1 | Tool selection | Mechanical — compare called tool(s) against each task's `expected_trajectory` |
| 2 | Tool arguments | Mechanical — compare argument values against `expected_trajectory` per step |
| 3 | Tool execution | Mechanical — read `result.status` from the trace |
| 4 | Tool sequence | Mechanical — compare step order against `expected_trajectory` (ordered list, not a set) |
| 5 | Completeness | Mechanical — did every step in `expected_trajectory` occur |
| 6 | Efficiency | Mechanical — any `TOOL_CALL` step not in `expected_trajectory` (or a legitimate acceptable alternative) |
| 7 | Recovery | **Needs an LLM judge.** Detecting "gave up silently" or "hallucinated success" from a final answer requires reading intent, not just structure. Pilot harness flags these tasks for manual review instead of auto-scoring. |
| 8 | Side-effect awareness | Partly mechanical (precondition checks against `world_state_before`), partly judgment — pilot harness checks preconditions mechanically, flags HIGH/CRITICAL-risk calls for manual review of whether the agent behaved appropriately given the risk. |
| 9 | Risk awareness | **Needs an LLM judge** for tasks 7 and 8 (tool failure / high-risk action) — see `results/spot_check.md`. |
| 10 | Task completion | Mechanical — check `postconditions` against `world_state_after`, plus a simple keyword/entity check on the final answer |

Dimensions 7 and 9 are the two the design doc's Phase 2 goal — proving the
schema and trace format generalize across agents — could not fully validate
mechanically. That's expected at pilot scale; see `README.md` for how this was
handled and what it means for Phase 3.

## 8. What Changed From the Design Doc

Nothing was changed. Drafting 10 tools and 10 tasks against this schema did not
surface a gap in the primitive taxonomy, the tool representation, or the
side-effect/risk model. The only additions are pilot-scoped: the domain and
task-type *subsets* actually in use (sections 2–3), the standard trace format
(section 5, which the design doc specified only as a requirement, not a shape),
and the tool-use failure taxonomy (section 6, which the design doc left as a
placeholder — "failure taxonomy" — under Phase 1's deliverables).

## 9. Phase 3 Draft — Proposed Additions

`tasks_phase3_draft.json`'s 40 draft tasks (T11–T50) surfaced two schema gaps
the pilot's 10 tasks were too uniform to hit — recorded here so the
proposal lives with the schema, not just in a task file's comments. One is
implemented; `trajectory_order` is not.

**New task types**, beyond the pilot subset in section 3:

```text
COMPOUND_QUERY        Two or more tools needed to answer one request, with
                       no data dependency between them (e.g. an independent
                       READ and a COMPUTE in the same turn).
NO_TOOL_RESPONSE       Correct behavior is zero tool calls — the request is
                       conversational, conceptual, or already answerable from
                       information stated in the prompt itself.
AMBIGUOUS_REQUEST      The request under-specifies the target entity and/or
                       a required argument; correct behavior is to ask,
                       not guess.
PARALLEL_QUERY         Two or more tool calls that are fully independent of
                       each other and of each other's output.
```

**`trajectory_order`** — a proposed new field on `expected_trajectory`, still
not implemented, needed because `harness/scorer.py`'s `tool_sequence` check
is a strict ordered-prefix match with no way to express anything looser:

```text
STRICT   Default (matches current pilot behavior). Calls must occur in
         exactly the given order.
ANY      Calls may occur in any order — used for COMPOUND_QUERY and
         PARALLEL_QUERY tasks with no data dependency between steps.
PARTIAL  A named subset of calls may occur in any order relative to each
         other, but all of them must precede (or follow) another named
         call — e.g. two disambiguating reads that can happen in either
         order, both required before a destructive call.
```

**The postcondition checker is now data-driven. (Resolved.)**
`harness/scorer.py` previously hardcoded one Python function per task ID
(`_check_T03` through `_check_T10` in `POSTCONDITION_CHECKS`) rather than
evaluating each task's `expected_postconditions` generically — a reasonable
shortcut at 10 tasks sharing few postcondition shapes, but one that produced
a silent failure mode at 50: any task ID without a registered function
defaulted `postconditions_met` to `True` rather than being flagged as
unscored. `harness/scorer.py`'s `POSTCONDITION_PREDICATES` replaces this
with a name -> predicate registry keyed on the postcondition strings already
declared in `tools.py`'s `TOOL_SCHEMAS` (`ORDER_CANCELLED`,
`ITEM_ADDED_TO_CART`, etc.), and a task declaring no postconditions at all is
now checked against a real invariant (`WORLD_STATE_UNCHANGED`) instead of
being silently skipped.

Validated by re-scoring the pilot's recorded traces through the new checker
(identical results to the original hardcoded functions, plus two intentional
improvements — see `harness/scorer.py`'s module docstring) and by simulating
a "golden" agent that executes exactly the `expected_trajectory` for all 40
draft tasks against the real store: every task scores `task_completion: True`
(or `NEEDS_REVIEW` for judge-flagged tasks). That golden-trace pass also
caught a genuine task-data bug — T14 and T22 called `create_support_ticket`
with only `customer_id`, omitting the tool's other required arguments
(`subject`/`description`/`priority`), which is fine for a real agent (it
supplies its own values) but made the tasks non-executable as written;
both now include illustrative values for those fields.
