#!/usr/bin/env python3
"""Run the 10-task Tool Use Benchmark pilot against both agent adapters and
write scored results to results/.

Usage:
    export GROQ_API_KEY=...
    python run_pilot.py

Requires: langchain-core, langchain-groq, groq, pydantic (see repo requirements).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "harness"))
sys.path.insert(0, str(HERE / "harness" / "agents"))

import runner  # noqa: E402
import scorer  # noqa: E402
import langchain_groq_agent as agent_a  # noqa: E402
import manual_react_agent as agent_b  # noqa: E402


def main() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is not set.")

    tasks = json.loads((HERE / "tasks.json").read_text())
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)

    all_scores = {}
    for agent_module in (agent_a, agent_b):
        print(f"\n=== Running {agent_module.AGENT_ID} ({agent_module.MODEL}) ===")
        traces = runner.run_agent_on_tasks(agent_module, tasks)
        (results_dir / f"{agent_module.AGENT_ID}_traces.json").write_text(json.dumps(traces, indent=2, default=str))

        scores = scorer.score_all(tasks, traces)
        (results_dir / f"{agent_module.AGENT_ID}_scores.json").write_text(json.dumps(scores, indent=2, default=str))
        all_scores[agent_module.AGENT_ID] = scores

    (results_dir / "all_scores.json").write_text(json.dumps(all_scores, indent=2, default=str))
    print(f"\nWrote traces and scores to {results_dir}")


if __name__ == "__main__":
    main()
