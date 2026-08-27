# Tool Use Benchmark

A domain-independent, agent-independent benchmark for whether AI agents select
and use tools correctly — not whether they use a *particular* tool, but
whether they perform the right operation, with the right arguments, at the
right time, with the right consequences. Full design rationale in
[`Agentic_Evals_Tool_Use_Benchmark_Design.md`](../../Agentic_Evals_Tool_Use_Benchmark_Design.md).

**Status: Phase 1 (Specification) + Phase 2 (10-task pilot) complete. Phase 3
task set drafted (not yet runnable — see "Phase 3 Draft" below).**
Phase 3 (25–50 tasks) and Phase 4 (100+ tasks) are tracked in
[issue #1](https://github.com/abhineer/Agentic_Evals/issues/1) and scoped for
subsequent weeks — see "What This Surfaced" below for why 10 tasks came
first.

In the meantime, [`notebooks/tools/tool_eval_v2.ipynb`](../../notebooks/tools/tool_eval_v2.ipynb)
still covers tool selection precision/recall, success rate, and cost-per-task
on its own smaller, ad-hoc set of generic scenarios (calculator, string
utilities). That notebook and this benchmark are separate efforts: the
notebook's tools can't exercise `CREATE`/`UPDATE`/`DELETE`/`EXECUTE`, side
effects, or risk, which is exactly what this benchmark's domain-grounded tool
set was built to cover.

## What's Here

| File | What it is |
|---|---|
| [`SCHEMA.md`](SCHEMA.md) | The finalized tool/task/trace schema and tool-use failure taxonomy (Phase 1) |
| `store.py` | In-memory retail backend (`RetailStore`) tools operate against |
| `tools.py` | The 10 pilot tools — full schema representation + real implementation, enforcing preconditions against `RetailStore` |
| `tasks.json` | The 10 pilot tasks — prompt, seed world state, expected trajectory, stress-test tag |
| `tasks_phase3_draft.json` | 40 additional draft tasks (T11–T50) toward Phase 3's 25–50 target — **not yet wired into `run_pilot.py`**, see "Phase 3 Draft" below |
| `harness/runner.py` | Executes an agent adapter against the task set, produces standard traces |
| `harness/scorer.py` | Scores traces against the mechanically-checkable evaluation dimensions |
| `harness/agents/langchain_groq_agent.py` | Agent A — LangChain `bind_tools` loop, `openai/gpt-oss-120b` |
| `harness/agents/manual_react_agent.py` | Agent B — hand-rolled ReAct prompt loop, raw Groq client, `qwen/qwen3.6-27b` |
| `run_pilot.py` | Runs both agents against all 10 tasks, writes `results/` |
| `results/` | Traces, scores, and the by-hand spot-check (`results/spot_check.md`) |

## Running It

```bash
pip install -r requirements.txt
export GROQ_API_KEY=...
python run_pilot.py
```

Deterministic (`temperature=0`) but not guaranteed byte-identical across runs
— Groq's `on_demand` tier doesn't guarantee reproducible sampling even at
temperature 0. Three runs during this pilot produced identical mechanical
scores on 18 of 20 (task, agent) pairs and the same qualitative behavior on
the remaining 2 (T07, T08 — see below); nothing in the results changed
conclusions between runs.

## The Tool Set

10 retail/e-commerce tools, covering all 7 primitives from `SCHEMA.md`:

| Tool | Primitive | Side Effect | Risk |
|---|---|---|---|
| `search_products` | SEARCH | NONE | NONE |
| `check_inventory` | READ | NONE | NONE |
| `get_order_status` | READ | NONE | NONE |
| `add_item_to_cart` | CREATE | STATE_CHANGE | LOW |
| `update_shipping_address` | UPDATE | STATE_CHANGE | LOW |
| `cancel_order` | DELETE | STATE_CHANGE | MEDIUM |
| `place_order` | EXECUTE | FINANCIAL_TRANSACTION | HIGH |
| `issue_refund` | EXECUTE | FINANCIAL_TRANSACTION | HIGH |
| `calculate_order_total` | COMPUTE | NONE | NONE |
| `create_support_ticket` | CREATE | RESOURCE_ALLOCATION | LOW |

6 of the 10 carry real side effects, well above the design doc's "at least
2–3" floor — preconditions and risk-awareness need tools that can actually
fail or actually cost something, and `place_order`/`issue_refund` genuinely
mutate a shared `RetailStore` (inventory decrements, orders get created,
refunds get recorded against a real order total).

## The 10 Tasks

Not an even split of Phase 3's ~12 categories — the design doc is explicit
that 10 tasks should stress-test the schema, not pre-enumerate every future
category. Picked instead: 2 baseline correct-selection tasks, 3 wrong-tool
temptations, 1 argument-correctness stress test, 2 sequential-dependency
tasks (one unconditional, one conditional on a precondition), 1 tool-failure
task, and 1 high-risk-action task. Full task definitions with expected
trajectories in `tasks.json`.

## Pilot Results

Both agents run against the identical 10 tasks and identical `RetailStore`
seed data, scored against the mechanical dimensions in `SCHEMA.md` section 7.
Every row below was spot-checked by hand against the raw trace —
see `results/spot_check.md` for the full verification and the manual
verdicts on the two tasks that need judgment rather than mechanical scoring.

### Agent A — LangChain `bind_tools`, `openai/gpt-oss-120b`

```
Tool Selection        90%
Argument Accuracy     90%
Sequence Accuracy     90%
Completeness          90%
Efficiency           100%
Task Completion        8/10 pass, 2 needs manual review (T07, T08)

Failure tags:
- WRONG_TOOL:           1  (T08 — no order-status check before cancel_order)
- MISSING_PREREQUISITE: 1  (T08 — same root cause)
```

### Agent B — manual ReAct loop, `qwen/qwen3.6-27b`

```
Tool Selection         80%
Argument Accuracy      80%
Sequence Accuracy      80%
Completeness           90%
Efficiency              95%
Task Completion         8/10 pass, 2 needs manual review (T07, T08)

Failure tags:
- WRONG_TOOL:            2  (T07 — tried place_order before add_item_to_cart;
                               T08 — same root cause as Agent A)
- UNNECESSARY_CALL:      1  (T07 — the place_order false start)
- MISSING_PREREQUISITE:  1  (T08)
```

Both agents got every task right except T07 (tool failure / recovery) and
T08 (high-risk cancellation) — and both handled those two identically in
substance: correct final answers once the tool rejected the call, but
neither agent proactively checked state before attempting the risky
operation. See `results/spot_check.md` for the full trace-level read of
both.

## Phase 3 Draft

`tasks_phase3_draft.json` holds 40 new tasks (T11–T50), taking the total
toward Phase 3's 25–50 target (10 pilot + 40 draft = 50, sized to the top of
that range). These are content-complete against the real `tools.py`/
`store.py` — real SKUs, real preconditions, real enum values — but **one
harness gap still has to close before they can run through `run_pilot.py`**:

1. ~~The postcondition checker isn't generic yet.~~ **Resolved.**
   `harness/scorer.py`'s `POSTCONDITION_PREDICATES` now reads each task's
   `expected_postconditions` generically instead of hardcoding one Python
   function per task ID, and a task with no declared postconditions is
   checked against a real invariant (`WORLD_STATE_UNCHANGED`) rather than
   silently defaulting to "passed." Validated two ways: re-scoring the
   pilot's recorded traces (`results/*_traces.json`) through the new checker
   reproduces every original score exactly, plus two documented
   improvements (T01/T02/T09 now get a real check instead of `N/A`; T05's
   previously-unchecked `ITEM_ADDED_TO_CART` postcondition — silently
   dropped by the old per-task function — now passes); and simulating a
   "golden" agent that executes exactly the `expected_trajectory` for all
   40 draft tasks against the real store scores `task_completion: True` (or
   `NEEDS_REVIEW` for judge-flagged tasks) on all 40.
2. **The scorer still only supports one trajectory shape.** `tool_sequence`
   (`harness/scorer.py`) is a strict ordered-prefix match with no concept of
   order-independence. 15 of the 40 draft tasks need something else: two
   `add_item_to_cart` calls that can happen in either order before a
   `place_order` (T19), two disambiguating reads that can happen in either
   order before a destructive call (T35, T36), or fully independent parallel
   calls (T13–T16, T44–T50). Each draft task carries a new `trajectory_order`
   field (`STRICT` / `ANY` / `PARTIAL`) proposing this — documented in
   `SCHEMA.md` section 9 — but the scorer doesn't read it yet. This is the
   one remaining blocker before `tasks_phase3_draft.json` can be merged into
   the live `tasks.json` and actually run.

**Category breakdown** (40 new + 10 reused/kept from the pilot = 50 total),
weighted toward categories the pilot showed actually discriminate agent
quality (wrong-tool, argument errors, failure recovery) rather than pure
production-frequency, plus three categories the pilot never touched at all
(no-tool, ambiguous, parallel):

| Category | Total | From pilot | New (draft) |
|---|---|---|---|
| single-tool | 3 | 1 | 2 |
| multi-tool | 5 | 1 | 4 |
| dependency | 5 | 1 | 4 |
| sequential | 5 | 1 | 4 |
| wrong-tool | 6 | 3 | 3 |
| argument errors | 5 | 1 | 4 |
| tool failures | 4 | 1 | 3 |
| failure recovery | 6 | 1 | 5 |
| no-tool | 4 | 0 | 4 |
| ambiguous | 4 | 0 | 4 |
| parallel | 3 | 0 | 3 |
| **Total** | **50** | **10** | **40** |

**The pilot's "unguarded risk" gap closed without a new tool.** The pilot
flagged that all 10 tools self-protect via preconditions, so no task could
tell "agent checked first" apart from "agent got caught by the tool and
recovered." T35/T36 close this using the *existing* tool set: two orders (or
two paid orders) for the same customer that satisfy `cancel_order`'s or
`issue_refund`'s preconditions equally, where only the agent confirming
which one matches the customer's description — not any tool-level guard —
prevents cancelling/refunding the wrong one. A wrong-target outcome is
mechanically checkable (world state shows the wrong order mutated); the
residual case (right outcome, no verification, i.e. a lucky guess) is what
still needs a judge to read from the trace.

## What This Surfaced

The point of running 10 tasks against 2 independently-built agents before
writing 90 more, per the design doc: find out where the schema/trace format
breaks *before* it's expensive to fix.

**The schema held.** Every field in the tool/task/trace representation
(`SCHEMA.md` sections 1–5) was exercised by at least one pilot task, and
nothing needed to change. Both agents' very different execution paths —
LangChain's native `bind_tools` message loop vs. a hand-rolled text-parsed
ReAct loop on a different model from a different lineage — normalized into
the same trace shape without a framework-specific escape hatch, which was
the actual thing Phase 2 was supposed to prove.

**Recovery and risk awareness genuinely need a judge, not a proxy metric.**
This was a hypothesis in `SCHEMA.md` section 7 going in; the pilot confirmed
it isn't avoidable. A mechanical score for T07 correctly says "the expected
tool call failed" but can't distinguish Agent A's clean, honest response from
Agent B's overshoot-then-recover — both "failed" the same call, only one of
the two needed a second attempt to get there. This has to stay a manual
(Phase 3: LLM-judge) read.

**The task design, not just the agent, decides whether risk awareness is
even testable.** Both agents handled T08 identically: neither checked order
status before attempting `cancel_order`, both got caught by the tool's own
`ORDER_NOT_SHIPPED` precondition, both then answered honestly. That's not
evidence both agents are equally risk-aware — it's evidence this task
doesn't discriminate between "agent that checks first" and "agent that
attempts and handles rejection," because the tool's precondition check
catches the mistake either way. Phase 3 needs at least one high-risk task
where skipping the proactive check actually causes irreversible harm (e.g. a
tool with no precondition guard, so the only thing preventing damage is the
agent's own judgment) — this pilot's tools all self-protect, which was the
right conservative default for a first pilot but understates real risk.

**Running two real agents caught two real bugs in the harness, not the
tools under test.** A non-greedy JSON regex silently truncated nested
arguments, and an unescaped tool name (`` `calculate_order_total` `` with
markdown backticks) broke exact-match tool lookup — both are now fixed and
covered in `results/spot_check.md`. Both would have been invisible running
only one agent, since Agent A's structured `bind_tools` output never goes
through free-text parsing at all. This is the concrete payoff of the design
doc's "test against at least two different agent implementations"
requirement — it's not just about proving portability, it's about exercising
code paths a single well-behaved agent never touches.

**Next:** Phase 3 (25–50 tasks) should keep the wrong-tool-temptation and
sequential-dependency categories that worked cleanly here, add a task whose
risk depends entirely on the agent's own judgment rather than a
tool-enforced precondition, and put a real LLM judge behind Recovery and
Risk Awareness instead of manual review. Tracked in issue #1 (not closed —
spec + pilot is one milestone within it, not the whole scope).
