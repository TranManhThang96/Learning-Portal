# Tài Liệu Tham Khảo — Ngày 20: LangChain — Chains, Tools & Agents

## 📚 Official Docs

- **LangChain Python Overview** — https://docs.langchain.com/oss/python/langchain/overview — v1 concepts và install path
- **LangChain Agents** — https://docs.langchain.com/oss/python/langchain/agents — `create_agent`, static/dynamic tools
- **LangChain Tools** — https://docs.langchain.com/oss/python/langchain/tools — `@tool`, docstring/schema guidance
- **LCEL Concepts** — https://python.langchain.com/docs/concepts/lcel/ — `prompt | llm | parser`
- **LangGraph ReAct Agent** — https://langchain-ai.github.io/langgraph/tutorials/introduction/ — Optional workflow/agent graph tutorial
- **`create_react_agent`** — https://langchain-ai.github.io/langgraph/reference/prebuilt/#langgraph.prebuilt.chat_agent_executor.create_react_agent — LangGraph API reference
- **LangChain Callbacks** — https://python.langchain.com/docs/concepts/callbacks — Callback system architecture
- **LangSmith Docs** — https://docs.smith.langchain.com/ — Setup, tracing, evaluation
- **LangSmith Python SDK** — https://docs.smith.langchain.com/reference/sdk/python — `@traceable`, `Client` API
- **Tool calling concepts** — https://python.langchain.com/docs/concepts/tool_calling — OpenAI function calling internals
- **LangGraph Docs** — https://langchain-ai.github.io/langgraph/ — State machine approach cho agents

## 🎥 Video / Courses

- **LangGraph Agent Tutorial** (Official) — https://www.youtube.com/watch?v=jGT1O6aQW5Q — Build agents với LangGraph
- **ReAct Paper Explained** — https://www.youtube.com/watch?v=Eug2clsLtFs — Understand the theory behind ReAct agents
- **LangSmith Full Tutorial** — https://www.youtube.com/watch?v=tFXFnMZfNqQ — Setup, tracing, evaluation workflow
- **Building Production Agents** — https://www.youtube.com/watch?v=RF3_8pJ6bgo — Real-world considerations
- **Streaming LLM Responses** — https://www.youtube.com/watch?v=eRVQaxBH7eY — SSE, WebSocket, LCEL streaming

## 📝 Articles / Blog Posts

- **ReAct: Synergizing Reasoning and Acting in LLMs** — https://arxiv.org/abs/2210.03629 — Paper gốc của ReAct pattern, đọc abstract và Figure 1
- **LangGraph vs AgentExecutor** — https://blog.langchain.dev/langgraph-vs-agentexecutor/ — Historical migration context, kiểm tra docs v1 trước khi copy code
- **Tool Design Best Practices** — https://docs.langchain.com/oss/python/langchain/tools — Viết tools tốt cho LLM
- **LangSmith for Production Debugging** — https://blog.langchain.dev/langsmith-for-production/ — Real use cases
- **Agent Reliability Patterns** — https://www.anthropic.com/research/building-effective-agents — Anthropic's guide (language-agnostic, concepts apply)
- **Function Calling Deep Dive (OpenAI)** — https://platform.openai.com/docs/guides/function-calling — Hiểu internals của tool calling
- **Callbacks Architecture** — https://python.langchain.com/docs/concepts/callbacks — Khi nào dùng loại callback nào

## 🔧 Tools / Libraries

- **langchain** — `uv add "langchain>=1.0,<2.0"` — Core framework, tools, agents, LCEL helpers
- **langgraph** — `uv add "langgraph>=1.0,<2.0"` — Agent/workflow framework; dùng `create_react_agent(..., prompt=...)`
- **langsmith** — `uv add "langsmith>=0.4,<1.0"` — Observability SDK
- **langchain-openai** — `uv add "langchain-openai>=1.0,<2.0"` — ChatOpenAI với tool calling support
- **langchain-tavily** — `uv add langchain-tavily` — Tavily search integration theo package tách riêng hiện hành
- **langchain-community** — `uv add langchain-community` — Community tools: SerpAPI, Wikipedia, etc.

### Smoke import command

```bash
uv run python - <<'PY'
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.tools import tool
from langchain.agents import create_agent

@tool
def ping() -> str:
    """Return a simple health string."""
    return "pong"

agent = create_agent("openai:gpt-5", tools=[ping], system_prompt="You are concise.")
print("imports OK:", ChatOpenAI, ChatPromptTemplate, StrOutputParser, agent)
PY
```

### Useful tools để integrate vào agent:
```python
# Web search (cần TAVILY_API_KEY)
from langchain_tavily import TavilySearch
search = TavilySearch(max_results=3)

# Wikipedia
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

# Python REPL (cẩn thận trong production!)
from langchain_experimental.tools import PythonREPLTool
repl = PythonREPLTool()

# File system (giới hạn trong specific directory)
from langchain_community.agent_toolkits import FileManagementToolkit
tools = FileManagementToolkit(root_dir="/tmp/agent_workspace").get_tools()
```

### LangSmith Setup script:
```bash
# 1. Tạo account tại https://smith.langchain.com
# 2. Tạo API key
# 3. Set environment variables

export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY="ls-..."
export LANGCHAIN_PROJECT="my-project-name"

# Verify
python -c "from langsmith import Client; c = Client(); print('Connected:', c.list_projects())"
```

## 💡 Ghi chú thêm

### Legacy AgentExecutor vs LangChain v1

Course này không dùng `AgentExecutor` làm path chính. Nếu bạn thấy code cũ dùng `AgentExecutor`, migrate theo use case:

```python
# CŨ — legacy trong course này
from langchain.agents import AgentExecutor, create_openai_tools_agent
agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": "question"})

# MỚI — LangChain v1 high-level agent
from langchain.agents import create_agent
agent = create_agent("openai:gpt-5", tools=tools, system_prompt="You are helpful.")
result = agent.invoke({"messages": [{"role": "user", "content": "question"}]})
```

Nếu workflow cần checkpointing/human-in-the-loop/state graph, dùng LangGraph `create_react_agent` hoặc tự dựng graph thay vì cố ép `AgentExecutor`.

### Tool Safety Considerations

Khi build agents cho production, cân nhắc:
1. **Least privilege**: Tools chỉ có access vào resources cần thiết
2. **Human-in-the-loop**: Với actions destructive (delete, send email), thêm confirmation step
3. **Rate limiting**: Wrap tools với rate limiting để tránh abuse
4. **Sandboxing**: Python REPL tools phải chạy trong isolated environment (Docker)
5. **Logging**: Log mọi tool call với input/output cho audit trail

```python
# Human-in-the-loop pattern
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

@tool
def delete_database_record(table: str, record_id: str) -> str:
    """Delete một record từ database. DESTRUCTIVE operation."""
    # Pause và wait for human confirmation
    confirmed = interrupt(f"Confirm delete from {table} where id={record_id}? (yes/no)")
    if confirmed.lower() == "yes":
        # Actually delete
        return f"Deleted record {record_id} from {table}"
    return "Operation cancelled by user"
```

### Debugging Agent Issues

Khi agent behave unexpectedly:
```python
# 1. Enable debug mode
import langchain
langchain.debug = True

# 2. Print all messages
result = agent.invoke({"messages": [...]})
for msg in result["messages"]:
    print(f"\n{'='*40}")
    print(f"Type: {type(msg).__name__}")
    print(f"Content: {getattr(msg, 'content', '')[:300]}")
    if hasattr(msg, 'tool_calls'):
        print(f"Tool calls: {msg.tool_calls}")

# 3. Use LangSmith để xem visual trace
# Đặc biệt hữu ích cho multi-step agents

# 4. Test tools independently trước
tool_result = my_tool.invoke({"arg": "test_value"})
print("Tool output:", tool_result)
assert isinstance(tool_result, str), "Tool phải return string!"
```

### Cost Management cho Agents

Agents tốn tiền hơn simple chains vì nhiều LLM calls:
- Mỗi "thought" = 1 LLM call
- Mỗi tool call result → LLM phải process = thêm 1 call
- Complex task có thể cần 10-20 LLM calls

Strategies để giảm cost:
1. Dùng model nhỏ/nhanh đã qua eval cho tool selection; đọc model từ config thay vì hardcode
2. Cache tool results: `@lru_cache` cho deterministic tools
3. `max_iterations` limit để prevent runaway agents
4. Log và analyze LangSmith để find expensive patterns
5. Consider task decomposition: break complex task thành multiple focused agents

Ước tính cost cho bài tập ngày 20: $0.50 - $2.00 tùy số lần test.
