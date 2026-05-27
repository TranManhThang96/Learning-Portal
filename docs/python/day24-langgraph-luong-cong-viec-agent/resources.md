# Tài Liệu Tham Khảo — Ngày 24: LangGraph & Agentic Workflows

## 📚 Official Docs

- **LangGraph Documentation** — https://langchain-ai.github.io/langgraph/ — Official docs với tutorials đầy đủ
- **LangGraph Concepts** — https://langchain-ai.github.io/langgraph/concepts/ — Core concepts: state, nodes, edges
- **Human-in-the-Loop** — https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/ — Interrupt patterns, approval workflows
- **Persistence & Checkpointing** — https://langchain-ai.github.io/langgraph/concepts/persistence/ — Checkpointers, thread management
- **Streaming** — https://langchain-ai.github.io/langgraph/how-tos/streaming-tokens/ — Token streaming, state streaming
- **Subgraphs** — https://langchain-ai.github.io/langgraph/how-tos/subgraph/ — Modular graph composition
- **LangGraph Cloud** — https://langchain-ai.github.io/langgraph/concepts/langgraph_cloud/ — Managed deployment

## 🎥 Video / Courses

- **LangGraph Tutorial** (LangChain YouTube) — https://www.youtube.com/watch?v=R8KB-Zcynxc — Official tutorial, 45 minutes
- **Build AI Agents with LangGraph** (DeepLearning.AI) — https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/ — Free course, comprehensive
- **LangGraph from Scratch** — https://www.youtube.com/watch?v=mvNG5ZFrRt4 — Build từ đầu, không dùng shortcuts
- **Human-in-the-Loop Agents** — https://www.youtube.com/watch?v=9BPCV5TYPmg — Deep dive interrupt patterns
- **LangGraph vs AutoGen vs CrewAI** — https://www.youtube.com/watch?v=qU2zHSW3hGM — Framework comparison

## 📝 Articles / Blog Posts

- **LangGraph: Build Stateful Agents** — https://blog.langchain.dev/langgraph/ — Official introduction blog post
- **Understanding LangGraph State** — https://medium.com/@tahreemrasul/building-your-own-chatbot-with-langgraph-and-streamlit-c26b44f12b4e — State management explained
- **LangGraph vs Traditional Agents** — https://towardsdatascience.com/langgraph-the-future-of-complex-llm-workflows-5f1e0e6e3b0e — WHY use LangGraph
- **Checkpointing in LangGraph** — https://blog.langchain.dev/langgraph-v0-1/ — Persistence deep dive
- **Building Production Agents** — https://www.sequoiacap.com/article/llm-agents-perspective/ — High-level strategy (không code)

## 🔧 Tools / Libraries

- **langgraph** — `uv add langgraph` — Core package
- **langgraph-checkpoint-postgres** — `uv add langgraph-checkpoint-postgres` — Production checkpointing
- **langgraph-checkpoint-sqlite** — `uv add langgraph-checkpoint-sqlite` — Lightweight persistent checkpointing
- **langchain-openai** — `uv add langchain-openai` — OpenAI integration
- **LangSmith** — https://smith.langchain.com — Tracing và monitoring (free tier available)
- **psycopg** — `uv add psycopg[binary]` — PostgreSQL driver cho PostgresSaver

## 💡 Ghi chú thêm

### Setup LangSmith Tracing (Highly Recommended):
LangSmith cho phép visualize toàn bộ graph execution — rất hữu ích cho debugging:
```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your-key>
export LANGCHAIN_PROJECT=day24-langgraph
```
Sau đó mọi `app.invoke()` sẽ được tự động traced trên LangSmith dashboard.

### SQLite Checkpointer (Dễ setup hơn PostgreSQL):
```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

with sqlite3.connect("checkpoints.db", check_same_thread=False) as conn:
    checkpointer = SqliteSaver(conn)
    app = graph.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "demo-thread"}}
    result = app.invoke(inputs, config=config, version="v2")
```
File `checkpoints.db` sẽ persist state ngay cả khi process restart.
Trong app thật, connection/pool phải sống lâu hơn một request nếu bạn muốn resume interrupt sau đó; đừng tạo checkpointer trong context rồi đóng connection trước khi resume.
Với interrupt, docs hiện hành thường dùng `result.interrupts` + `Command(resume=...)` khi gọi `version="v2"`; một số version cũ vẫn trả `result["__interrupt__"]`.

### Visualize Graph trong Terminal:
```python
# ASCII visualization
print(app.get_graph().draw_ascii())

# Mermaid diagram (dùng https://mermaid.live để view)
print(app.get_graph().draw_mermaid())

# PNG (cần graphviz)
app.get_graph().draw_png("graph.png")
```

### Pattern phổ biến cho Thread IDs:
```python
import uuid
from datetime import datetime

# Conversation thread
thread_id = f"conv_{user_id}_{session_id}"

# Job thread
thread_id = f"job_{job_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

# Always store thread_id khi start workflow → cần để resume sau interrupt
```

### Guardrails cho workflow có loop:
```python
config = {
    "configurable": {"thread_id": thread_id},
    "recursion_limit": 30,  # stop runaway cycles
}

# Bên cạnh recursion_limit, tự track:
# - max_llm_calls per workflow
# - max_tokens hoặc budget_usd
# - timeout per tool/agent
# - max human approval wait time
```

### XState so sánh với LangGraph:
Nếu bạn quen XState từ frontend:
- XState `states` → LangGraph nodes
- XState `transitions` → LangGraph edges
- XState `guards` → LangGraph conditional edges
- XState `context` → LangGraph state
- XState `services` → LangGraph nodes với async/LLM calls
- XState `persist` → LangGraph checkpointing
