"""Runner — executes one agent adapter against the 10-task pilot and
normalizes its behavior into the standard trace format (SCHEMA.md section 5).

Each task gets a fresh RetailStore built from its `seed`. The adapter (a
module exposing `AGENT_ID`, `MODEL`, and `run(store, prompt) -> {"steps": [...],
"raw_agent_output": ...}`) is responsible only for producing steps; the runner
adds task_id/agent_id/timestamps and the before/after world-state snapshots
that the scorer checks postconditions against.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

from store import RetailStore


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def run_agent_on_tasks(agent_module, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    traces = []
    for task in tasks:
        store = RetailStore.from_seed(task.get("seed"))
        world_before = store.snapshot()

        started_at = _now()
        adapter_output = agent_module.run(store, task["prompt"])
        finished_at = _now()

        trace = {
            "task_id": task["task_id"],
            "agent_id": agent_module.AGENT_ID,
            "started_at": started_at,
            "finished_at": finished_at,
            "steps": adapter_output["steps"],
            "world_state_before": world_before,
            "world_state_after": store.snapshot(),
            "raw_agent_output": adapter_output.get("raw_agent_output"),
        }
        traces.append(trace)
        print(f"  [{agent_module.AGENT_ID}] {task['task_id']}: {len(trace['steps'])} steps")
    return traces
