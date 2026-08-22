"""Agent A — LangChain's native tool-calling loop (bind_tools), same framework
family as the existing notebooks/tools/tool_eval_v2.ipynb, on Groq's
openai/gpt-oss-120b.

Produces a standard trace (SCHEMA.md section 5) from LangChain's tool-calling
message loop. This is the "reference" adapter — closest to how an agent built
on LangChain today would actually be wired.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq

from store import RetailStore
from tools import build_langchain_tools

AGENT_ID = "agent_a_langchain_bind_tools"
MODEL = "openai/gpt-oss-120b"
MAX_STEPS = 6

SYSTEM_PROMPT = (
    "You are a retail operations assistant with tools to look up, search, "
    "create, update, cancel, and execute retail actions (orders, inventory, "
    "refunds, cart, support tickets). Use a tool whenever it's needed to "
    "answer the request or carry out the requested action. If a tool call "
    "fails, read the error and decide whether to adapt (e.g. report the "
    "problem to the user) rather than repeating the same call. When you have "
    "enough information, respond with a final plain-text answer and no "
    "further tool calls."
)


def run(store: RetailStore, prompt: str) -> Dict[str, Any]:
    llm = ChatGroq(model=MODEL, temperature=0)
    tools = build_langchain_tools(store)
    llm_with_tools = llm.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    steps = []
    raw_log = []

    for _ in range(MAX_STEPS):
        t0 = time.time()
        ai_msg: AIMessage = llm_with_tools.invoke(messages)
        latency_ms = (time.time() - t0) * 1000
        messages.append(ai_msg)
        raw_log.append({"role": "assistant", "content": ai_msg.content, "tool_calls": ai_msg.tool_calls})

        if not ai_msg.tool_calls:
            steps.append({"step_index": len(steps), "type": "FINAL_ANSWER", "content": ai_msg.content})
            break

        for tc in ai_msg.tool_calls:
            tool = tools_by_name.get(tc["name"])
            if tool is None:
                result = {"status": "UNKNOWN_TOOL", "error": {"code": "UNKNOWN_TOOL", "message": tc["name"]}, "output": None}
            else:
                try:
                    result = json.loads(tool.invoke(tc["args"]))
                except Exception as exc:  # malformed args reaching the tool boundary
                    result = {"status": "INVALID_ARGUMENTS", "error": {"code": "INVALID_ARGUMENTS", "message": str(exc)}, "output": None}
            steps.append(
                {
                    "step_index": len(steps),
                    "type": "TOOL_CALL",
                    "tool_name": tc["name"],
                    "arguments": tc["args"],
                    "result": result,
                    "latency_ms": round(latency_ms, 1),
                }
            )
            messages.append(ToolMessage(content=json.dumps(result), tool_call_id=tc["id"]))
    else:
        steps.append({"step_index": len(steps), "type": "FINAL_ANSWER", "content": "(step limit reached without a final answer)"})

    return {"steps": steps, "raw_agent_output": raw_log}
