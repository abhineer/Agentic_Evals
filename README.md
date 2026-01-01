# AI Agent Evaluation Notebooks

A collection of Jupyter notebooks for evaluating different aspects of AI agents. Each notebook is **Google Colab ready** and designed for educational purposes.

## Quick Start

1. Open any notebook in Google Colab
2. Run the setup cell to install dependencies
3. Enter your GROQ API key when prompted
4. Run all cells to see the evaluation results

---

## Notebooks

### 1. Prompt Evaluation (`prompt_evals_v2.ipynb`)

Evaluates how different system prompts affect agent response quality.

| | |
|---|---|
| **Agent** | Physics Teacher |
| **Model** | Llama 3.1 8B (GROQ) |
| **Dataset** | 9 challenging physics questions targeting common misconceptions |

#### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| **Accuracy** | Binary (0/1) | Is the answer factually correct with no errors? |
| **Clarity** | Binary (0/1) | Would a confused student understand without follow-up? |
| **Completeness** | Binary (0/1) | Does it address the nuance/trap in the question? |

#### Prompt Versions Tested

- **Version 1**: Minimal prompt ("Answer the question")
- **Version 2**: Structured prompt with explicit instructions to address misconceptions

#### Key Insight

Structured prompts that explicitly instruct the model to address misconceptions and edge cases score higher on completeness.

---

### 2. Tool Calling Evaluation (`tool_eval_v2.ipynb`)

Evaluates precision and efficiency of tool selection by an LLM agent.

| | |
|---|---|
| **Agent** | Tool-calling assistant |
| **Model** | Llama 3.1 70B (GROQ) |
| **Framework** | LangChain |
| **Tools** | 6 (calculator, square_root, temperature_converter, string_reverser, word_counter, date_info) |

#### Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| **Tool Invocation Precision** | correct_calls / total_calls | Were the right tools called? |
| **Tool Invocation Recall** | recalled / expected | Were all needed tools called? |
| **Avg Tool Calls per Task** | total_calls / num_tasks | Efficiency of tool usage |
| **Tool Success Rate** | successful / total_calls | Did tools execute without errors? |
| **Tool-Attributable Success** | attributable / tool_required | Did tools contribute to the answer? |
| **Cost per Successful Task** | total_cost / successful_tasks | Cost efficiency |

#### Test Scenarios

| Category | Description |
|----------|-------------|
| `single_tool` | Tasks requiring exactly one tool |
| `multi_tool` | Tasks requiring multiple tools |
| `ambiguous` | Tasks where multiple tools could work |
| `no_tool` | Tasks that don't need any tools |

---

### 3. RAG Evaluation (`rag_evals.ipynb`)

Evaluates Retrieval-Augmented Generation systems for a Physics Tutor agent.

| | |
|---|---|
| **Agent** | Physics Tutor (RAG) |
| **Model** | Llama 3.1 8B (GROQ) |
| **Corpus** | 12 physics concept documents |
| **Dataset** | 10 physics questions with reference answers |

#### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| **Context Relevance** | Binary (0/1) | Does retrieved context contain relevant information? |
| **Answer Groundedness** | Binary (0/1) | Is the answer supported by the context (not hallucinated)? |
| **Answer Correctness** | Binary (0/1) | Is the answer factually correct? |

#### RAG Configurations Tested

| Config | k (docs) | Prompt Style |
|--------|----------|--------------|
| Config A | 1 | Minimal |
| Config B | 2 | Structured |
| Config C | 3 | Detailed |

#### Key Insight

RAG evaluation requires measuring both retrieval AND generation quality. A system can retrieve well but hallucinate, or generate well from irrelevant context.

---

### 4. Planning & Reasoning Evaluation (`planning_evals.ipynb`)

Compares agent reasoning approaches: **Direct** vs **ReAct** (Reasoning + Acting).

| | |
|---|---|
| **Task Type** | Multi-step reasoning tasks requiring facts and calculations |
| **Generation Model** | Llama 3.1 8B (GROQ) |
| **Evaluation Model** | Llama 3.3 70B (GROQ) |
| **Tools** | Calculator, Search (simulated knowledge base) |
| **Dataset** | 8 tasks requiring tool use and multi-step reasoning |

#### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| **Answer Correctness** | Binary (0/1) | Is the final answer factually correct? |
| **Reasoning Quality** | Binary (0/1) | Did the agent show clear, logical reasoning steps? |
| **Tool Use Appropriateness** | Binary (0/1) | Did the agent use tools when needed? |

#### Approaches Tested

| Approach | Description |
|----------|-------------|
| **Direct** | Answer immediately without explicit reasoning |
| **ReAct** | Thought → Action → Observation loop with tool use |

#### ReAct Example
```
Thought: I need to find the distance to the Moon
Action: search: moon distance
Observation: The Moon is approximately 384,400 km from Earth
Thought: Now I calculate time = distance / speed of light
Action: calculator: 384400 / 300000
Observation: Result: 1.28
Final Answer: Light takes about 1.28 seconds to reach the Moon
```

#### Key Insight

ReAct's explicit reasoning loop produces more accurate answers by using tools for facts/calculations rather than relying on parametric memory. The trace is also auditable and debuggable.

---

### 5. Synthetic Data Generation (`synthetic_data_gen.ipynb`)

Teaches structured approaches to generating diverse, realistic synthetic data for evaluation.

| | |
|---|---|
| **Use Case** | Product search queries for e-commerce |
| **Model** | Llama 3.1 8B (GROQ) |
| **Output** | Diverse query dataset with metadata |

#### The Problem

Asking LLMs for queries without structure → repetitive, generic outputs.

#### The Solution: Dimension-Based Generation

| Step | Description |
|------|-------------|
| **1. Define Dimensions** | Category, Price Intent, Specificity, User Context, Urgency |
| **2. Identify Failures** | Misspellings, abbreviations, negations, implicit constraints |
| **3. Manual Tuples** | ~20 hand-crafted (category, price, specificity, ...) combinations |
| **4. Scale with LLM** | Generate more tuples + convert to natural language separately |

#### Key Insight

**Separate tuple generation from query phrasing** to avoid repetitive patterns. The structured approach guarantees coverage and makes the dataset traceable.

---

### 6. Memory Evaluation (`memory_evals.ipynb`)

Evaluates agent memory - the ability to store, recall, update, and forget information across conversation turns.

| | |
|---|---|
| **Agent Type** | Memory-augmented conversational agent |
| **Model** | Llama 3.1 8B (GROQ) |
| **Memory** | Explicit key-value store with logging |

#### Metrics

| Metric | Abbreviation | Description |
|--------|--------------|-------------|
| **Memory Recall Accuracy** | MRA | Can the agent recall stored facts? |
| **Temporal Consistency Score** | TCS | Are answers consistent over multiple turns? |
| **Memory Update Correctness** | MUC | Does memory update when facts change? |
| **Forgetting Appropriateness** | FAS | Does agent forget when asked? |
| **Memory Pollution Rate** | MPR | Does agent store hallucinated facts? |
| **Cross-Episode Transfer** | CETS | Do facts persist across sessions? |

#### Key Difference from RAG

| Aspect | RAG | Memory |
|--------|-----|--------|
| Data Source | Static corpus | Dynamic, user-provided |
| Updates | Index rebuild | Real-time |
| Forgetting | N/A | Critical capability |

#### Key Insight

Memory evaluation tests **dynamic information management** - storing, recalling, updating, and forgetting personal facts during conversations. This is distinct from RAG's static retrieval.

---

### 7. Error Analysis (`error_analysis.ipynb`)

Demonstrates systematic error analysis and evidence-based prompt improvement.

| | |
|---|---|
| **Use Case** | Product description generation for e-commerce |
| **Generation Model** | Llama 3.1 8B (GROQ) |
| **Evaluation Model** | Llama 3.3 70B (GROQ) |
| **Test Data** | 10 products (initial) + 20 products (validation) |

#### The Process

| Step | Description |
|------|-------------|
| **1. Define Criteria** | What makes a "good" product description? |
| **2. Build Baseline** | Simple V1 agent with minimal prompt |
| **3. Collect Feedback** | Expert critiques on agent outputs |
| **4. Extract Patterns** | LLM identifies recurring failure modes |
| **5. Create Taxonomy** | 5-7 named failure categories |
| **6. Tag & Analyze** | Measure failure frequency on new data |
| **7. Improve Prompt** | Target top failure modes in V2 |

#### Failure Mode Taxonomy

| Code | Description |
|------|-------------|
| `HALLUCINATION` | Made-up specs, features, or claims not in title |
| `OVERLY_PROMOTIONAL` | Excessive marketing language, superlatives |
| `VAGUE_GENERIC` | Generic filler that could apply to any product |
| `MISSING_KEY_INFO` | Fails to mention important details from title |
| `WRONG_CATEGORY` | Misunderstands the product type or use case |
| `FORMATTING_ISSUES` | Poor structure, awkward sentences |
| `FACTUAL_ERROR` | Incorrect claims that contradict the title |

#### Key Insight

**Evidence-based prompt improvement** targets observed issues rather than intuition. By measuring failure frequency, you can prioritize fixes that have the highest impact.

---

## Requirements

- Python 3.8+
- GROQ API key ([Get one here](https://console.groq.com))

### Dependencies

```
groq
langchain
langchain-groq
pandas
matplotlib
```

---

## Project Structure

```
evals/
├── README.md
├── prompt_evals_v2.ipynb      # Prompt evaluation
├── tool_eval_v2.ipynb         # Tool calling evaluation
├── rag_evals.ipynb            # RAG evaluation
├── planning_evals.ipynb       # Planning/ReAct evaluation
├── synthetic_data_gen.ipynb   # Synthetic data generation
├── memory_evals.ipynb         # Memory evaluation
├── error_analysis.ipynb       # Error analysis & prompt improvement
└── (future notebooks)
```

---

## License

MIT
