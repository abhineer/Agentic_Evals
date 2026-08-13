# Resources

A short, curated list of papers and writing that shaped how this repository thinks about agent evaluation. Not an exhaustive reading list — each entry is here because it maps directly onto something in `notebooks/` or `benchmarks/`, with a note on why it's relevant.

## RAG

- **[Ragas: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217)** — reference-free RAG metrics (context precision/recall, faithfulness, answer relevance) without needing human-annotated ground truth. `notebooks/rag/rag_evals_v1.ipynb` uses the same split between retrieval quality and generation quality (context relevance, groundedness, correctness).

## Tool Use

- **[The Berkeley Function-Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html)** — the closest thing to a standard benchmark for tool/function-calling correctness, evaluating single, parallel, and multi-turn function calls via AST comparison. The direction `benchmarks/tool_use/` is heading in.

## Planning & Reasoning

- **[ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)** — the Thought → Action → Observation loop that `notebooks/planning/planning_evals.ipynb` implements and compares against a direct-answer baseline.

## Memory

- **[Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)](https://arxiv.org/abs/2402.17753)** — a benchmark and dataset for testing whether agents actually retain and reason over facts across long, multi-session conversations. `notebooks/memory/memory_evals.ipynb` tests a lighter-weight version of the same idea (recall, update correctness, forgetting) with an explicit key-value store instead of raw dialogue history.

## Safety

- **[InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents](https://arxiv.org/abs/2403.02691)** — shows how content an agent retrieves or processes (not just user input) can carry adversarial instructions. Relevant background for the planned Safety Evaluation Benchmark ([issue #4](https://github.com/abhineer/Agentic_Evals/issues/4)).

## Evaluation Methodology

- **[Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685)** — the paper behind the LLM-as-judge pattern this repo's notebooks lean on for binary pass/fail scoring, including known failure modes (position bias, verbosity bias) worth being aware of before trusting a judge model's output.
- **[Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/) — Hamel Husain** — the practitioner case for why eval infrastructure, not more prompting, is usually what's actually blocking an AI product from improving.
- **[LLM Evals: Everything You Need to Know](https://hamel.dev/blog/posts/evals-faq/) — Hamel Husain & Shreya Shankar** — a systematic workflow for error analysis (open/axial coding of failures) that `notebooks/error_analysis/error_analysis_v1.ipynb` follows a simplified version of.

## Agent Benchmarks (general)

- **[AgentBench: Evaluating LLMs as Agents](https://arxiv.org/abs/2308.03688)** — one of the first multi-environment benchmarks to evaluate agents on end-to-end task completion rather than single-turn QA, and an early argument for judging agents on trajectory quality, not just the final answer. Relevant to the planned Agent Trajectory Evaluation work ([issue #2](https://github.com/abhineer/Agentic_Evals/issues/2)).

---

Know a paper or writeup that's shaped how you evaluate agents and belongs here? Open a PR — see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
