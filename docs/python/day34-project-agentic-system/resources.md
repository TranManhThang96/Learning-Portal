# Tài Liệu Tham Khảo — Ngày 34

## 📚 Official Docs

- **LangGraph Python** — https://docs.langchain.com/oss/python/langgraph/overview — Official docs, tutorials, how-to guides
- **LangGraph Interrupts** — https://docs.langchain.com/oss/python/langgraph/interrupts — Human-in-the-loop với `interrupt()` và `Command(resume=...)`
- **LangGraph Persistence** — https://docs.langchain.com/oss/python/langgraph/persistence — Checkpointers và `thread_id`
- **LangGraph Memory/Checkpointers** — https://docs.langchain.com/oss/python/langgraph/add-memory — Postgres checkpointer examples
- **LangChain Tools** — https://docs.langchain.com/oss/python/langchain/tools — Tool definition guide

## 🎥 Video / Courses

- **LangGraph Tutorial** — LangChain YouTube — Official tutorials playlist
- **Building Agentic RAG** — LangChain YouTube — Combine RAG + agents
- **AI Agents Full Course** — freeCodeCamp YouTube — 5 hour course on AI agents

## 📝 Articles / Blog Posts

- **LangGraph: Multi-Agent Workflows** — LangChain Blog — Architecture patterns
- **Human-in-the-Loop AI** — https://blog.langchain.dev/human-in-the-loop/ — When and how
- **AI Agent Security** — OWASP — Security considerations cho AI agents

## 🔧 Tools / Libraries

- **langgraph** — `uv add langgraph` — Core framework
- **langgraph-checkpoint-postgres** — `uv add langgraph-checkpoint-postgres` — PostgreSQL persistence
- **tavily-python** — `uv add tavily-python` — Best web search tool for agents
- **langsmith** — `uv add langsmith` — Tracing agent runs
- **e2b** — `uv add e2b` — Cloud sandboxed code execution (production alternative)

## 💡 Ghi chú thêm

**Khi nào dùng LangGraph vs simple ReAct:**
- Simple Q&A với tools: ReAct agent (`create_react_agent`)
- Complex multi-step workflows: LangGraph
- Human-in-the-loop required: LangGraph
- Need persistence/resume: LangGraph
- Multiple specialized sub-agents: LangGraph với supervisor node

**Code execution safety levels:**
1. **Restricted exec()** (Bài 1): Đơn giản, đủ cho learning
2. **Docker container** (Production): Isolated, full Python nhưng cần Docker
3. **E2B sandbox** (Cloud): Managed sandboxing service, pay-per-use

**LangGraph Checkpointer options:**
- `MemorySaver`: In-memory, mất khi restart — dùng cho development
- `AsyncPostgresSaver`: Production-ready, durable
- `AsyncRedisSaver`: Fast, nhưng có thể mất data

**Tool design principles:**
1. Single responsibility — mỗi tool làm một việc
2. Clear docstring — LLM dùng này để quyết định gọi khi nào
3. Return strings — không return complex objects
4. Handle errors gracefully — return error message, không raise exception
5. Idempotent nếu có thể — safe to retry
