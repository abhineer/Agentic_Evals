"""Agent B — a hand-rolled ReAct-style prompting loop against the raw Groq
client, with no LangChain, no native tool-calling API, and manual text
parsing. Deliberately a different implementation path (different framework,
different model, different prompting style) from Agent A, so that a passing
score on both is real evidence the schema/trace format is agent-independent
rather than an artifact of one library's conventions.

Tool calls are dispatched straight through tools.call_tool(store, name, args)
— the same ground-truth implementation Agent A's LangChain tools wrap, so both
agents are being held to the same world model.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict

from groq import Groq, RateLimitError

from store import RetailStore
from tools import TOOL_SCHEMAS, call_tool

AGENT_ID = "agent_b_manual_react"
MODEL = "qwen/qwen3.6-27b"
MAX_STEPS = 6

_ACTION_HEADER_RE = re.compile(r"Action:\s*(\S+)\s*\nAction Input:\s*")
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


def _extract_action(text: str):
    """Find 'Action: <name>\nAction Input: <json>' and return (tool_name, json_str,
    match_start). A regex alone can't safely capture the JSON body: a non-greedy
    `\\{.*?\\}` stops at the FIRST closing brace, truncating any nested object
    (exactly what happened with calculate_order_total's list-of-objects argument
    during the pilot run — see results/spot_check.md). Scan for the balanced
    closing brace instead, respecting quoted strings."""
    header = _ACTION_HEADER_RE.search(text)
    if not header:
        return None
    # Strip markdown the model sometimes wraps the bare tool name in
    # (`calculate_order_total`, "calculate_order_total", **name**) — seen
    # live during the pilot run, see results/spot_check.md.
    tool_name = header.group(1).strip().strip("`*\"'")
    brace_start = text.find("{", header.end())
    if brace_start == -1:
        return tool_name, text[header.end():].strip(), header.start()

    depth = 0
    in_string = False
    escape = False
    end = brace_start
    for i in range(brace_start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
    return tool_name, text[brace_start:end + 1], header.start()


def _tool_catalog_block() -> str:
    lines = []
    for name, schema in TOOL_SCHEMAS.items():
        arg_descs = ", ".join(
            f"{i['name']}: {i['type']}" + (f" (one of {i['enum_values']})" if i.get("enum_values") else "")
            for i in schema["inputs"]
        )
        lines.append(f"- {name}({arg_descs}): {schema['description']}")
    return "\n".join(lines)


def _system_prompt() -> str:
    return f"""You are a retail operations assistant. You solve the user's request by reasoning step by step and calling tools when needed.

Available tools:
{_tool_catalog_block()}

Respond using EXACTLY this format for every turn, one block per response:

Thought: <your reasoning>
Action: <tool name>
Action Input: <a single-line JSON object of arguments>

When you have enough information to answer, respond instead with:

Thought: <your reasoning>
Final Answer: <your answer to the user>

Never call a tool that isn't in the list above. Never invent tool output — wait for the Observation. If a tool call fails, read the error and decide how to respond; do not repeat the identical failing call."""


def _create_with_retry(client: Groq, **kwargs):
    """The free-tier TPM budget for qwen/qwen3.6-27b (8000 TPM) is easy to
    exceed running 10 tasks back to back. Retry with the delay Groq reports
    rather than failing the whole pilot run."""
    for attempt in range(6):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            wait = 5.0 * (attempt + 1)
            message = str(exc)
            match = re.search(r"try again in ([\d.]+)s", message)
            if match:
                wait = float(match.group(1)) + 1.0
            time.sleep(wait)
    return client.chat.completions.create(**kwargs)


def run(store: RetailStore, prompt: str) -> Dict[str, Any]:
    client = Groq()
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": prompt},
    ]
    steps = []
    raw_log = []

    for _ in range(MAX_STEPS):
        t0 = time.time()
        completion = _create_with_retry(client, model=MODEL, temperature=0, messages=messages)
        latency_ms = (time.time() - t0) * 1000
        text = completion.choices[0].message.content or ""
        raw_log.append({"role": "assistant", "content": text})
        messages.append({"role": "assistant", "content": text})

        final_match = _FINAL_RE.search(text)
        action = _extract_action(text)

        if final_match and (not action or final_match.start() < action[2]):
            steps.append({"step_index": len(steps), "type": "FINAL_ANSWER", "content": final_match.group(1).strip()})
            break

        if not action:
            # Model didn't follow the format — treat whatever it said as the final answer.
            steps.append({"step_index": len(steps), "type": "FINAL_ANSWER", "content": text.strip()})
            break

        tool_name, raw_args, _ = action
        raw_args = raw_args.strip()
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            result = {"status": "INVALID_ARGUMENTS", "error": {"code": "INVALID_ARGUMENTS", "message": f"Unparseable Action Input: {exc}"}, "output": None}
            args = {"_raw": raw_args}
        else:
            if tool_name not in TOOL_SCHEMAS:
                result = {"status": "UNKNOWN_TOOL", "error": {"code": "UNKNOWN_TOOL", "message": tool_name}, "output": None}
            else:
                result = call_tool(store, tool_name, args)

        steps.append(
            {
                "step_index": len(steps),
                "type": "TOOL_CALL",
                "tool_name": tool_name,
                "arguments": args,
                "result": result,
                "latency_ms": round(latency_ms, 1),
            }
        )
        observation = f"Observation: {json.dumps(result)}"
        messages.append({"role": "user", "content": observation})
        raw_log.append({"role": "user", "content": observation})
    else:
        steps.append({"step_index": len(steps), "type": "FINAL_ANSWER", "content": "(step limit reached without a final answer)"})

    return {"steps": steps, "raw_agent_output": raw_log}
