# Tài Liệu Tham Khảo — Ngày 25: Multi-Agent Systems

## 📚 Official Docs

- **LangGraph Multi-Agent** — https://langchain-ai.github.io/langgraph/concepts/multi_agent/ — Official multi-agent concepts và patterns
- **LangGraph Agent Supervisor** — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/ — Supervisor pattern tutorial với code
- **LangGraph Hierarchical Agents** — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/ — Multi-tier agent teams
- **LangChain Tools** — https://python.langchain.com/docs/how_to/#tools — Tất cả về tool creation, structured tools
- **LangGraph Parallel Execution** — https://langchain-ai.github.io/langgraph/how-tos/branching/ — Fan-out, fan-in patterns
- **Pydantic Field Validators** — https://docs.pydantic.dev/latest/concepts/validators/ — Validate tool inputs với Pydantic

## 🎥 Video / Courses

- **Multi-Agent Systems with LangGraph** (DeepLearning.AI) — https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/ — Lessons về multi-agent (free)
- **Building Production Agents** (LangChain YouTube) — https://www.youtube.com/watch?v=v9fkbTxPzs0 — Production-ready multi-agent
- **LangGraph Agent Patterns** — https://www.youtube.com/watch?v=hvAPnpSfSGo — Orchestrator, supervisor, debate patterns
- **Tool Design for LLM Agents** — https://www.youtube.com/watch?v=DP1degDiW6o — Best practices với examples
- **AutoGen vs LangGraph vs CrewAI** — https://www.youtube.com/watch?v=qU2zHSW3hGM — Comprehensive framework comparison

## 📝 Articles / Blog Posts

- **The Multi-Agent Framework Landscape** — https://blog.langchain.dev/the-landscape-of-multi-agent-frameworks/ — LangChain's overview của tất cả frameworks
- **Building Reliable AI Agents** — https://www.anthropic.com/research/building-effective-agents — Anthropic's guide, highly recommended
- **Tool Design Best Practices** — https://python.langchain.com/docs/how_to/tools_few_shot/ — Few-shot examples cho tool selection
- **Circuit Breaker Pattern** — https://martinfowler.com/bliki/CircuitBreaker.html — Martin Fowler's classic article (NodeJS developer đã biết rồi, apply cho agents)
- **Agent Failure Modes** — https://www.anyscale.com/blog/llm-based-agents-best-practices — Common failure modes và fixes
- **Parallel Processing in LangGraph** — https://medium.com/@ahong.guo/langgraph-parallel-execution-f6f1e0d0c0c4 — Deep dive parallel patterns
- **When to Use Multi-Agent** — https://eugeneyan.com/writing/llm-patterns/ — Eugene Yan's analysis của khi nào nên/không nên dùng

## 🔧 Tools / Libraries

- **langgraph** — `uv add langgraph` — Core framework
- **langchain-openai** — `uv add langchain-openai` — OpenAI integration
- **tavily-python** — `uv add tavily-python` — Web search API (100 free searches/month)
- **langchain-community** — `uv add langchain-community` — Community tools, integrations
- **pydantic** — `uv add pydantic` — Tool input validation
- **httpx** — `uv add httpx` — Async HTTP client cho tools
- **CrewAI** — `uv add crewai` — Alternative multi-agent framework, simpler API
- **AutoGen** — `uv add pyautogen` — Microsoft's multi-agent framework, mature
- **Swarm** — `uv add openai-swarm` — OpenAI's experimental lightweight framework

## 💡 Ghi chú thêm

### Minimum production guards cho multi-agent:
```python
MAX_AGENT_STEPS = 8
MAX_ESTIMATED_TOKENS = 15_000
MAX_PARALLEL_TOOL_CALLS = 3

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def should_stop(state: dict) -> bool:
    return (
        state.get("agent_step_count", 0) >= MAX_AGENT_STEPS
        or state.get("estimated_tokens", 0) >= MAX_ESTIMATED_TOKENS
        or state.get("budget_exceeded", False)
    )
```

Rate limit phải nằm ngoài từng agent riêng lẻ. Nếu 4 agents cùng gọi Tavily/OpenAI/Cohere, dùng shared queue/semaphore hoặc provider-level limiter; nếu không, parallelism chỉ chuyển lỗi rate limit đến nhanh hơn.

### Khi nào nên dùng framework nào:

| Framework | Strengths | Best For |
|-----------|-----------|---------|
| LangGraph | Control, flexibility, production | Complex stateful workflows |
| CrewAI | Simplicity, role-based | Quick prototypes, simpler tasks |
| AutoGen | Multi-turn conversations, code execution | Coding agents, research |
| Swarm | Lightweight, educational | Learning multi-agent concepts |

### Tavily Search API (Recommended cho production):
```python
from langchain_community.tools.tavily_search import TavilySearchResults
import os

os.environ["TAVILY_API_KEY"] = "your-key"  # 100 free searches/month

search_tool = TavilySearchResults(
    max_results=5,
    search_depth="advanced",    # "basic" hoặc "advanced"
    include_answer=True,        # Include AI-generated answer
    include_raw_content=False,  # Include raw webpage content
)
```

### Monitoring agents với LangSmith:
```python
# Setup
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "ls__..."
os.environ["LANGCHAIN_PROJECT"] = "multi-agent-day25"

# Mọi agent call sẽ được trace tự động
# Dashboard tại: https://smith.langchain.com
# Xem: latency, token count, tool calls, errors
```

### Pattern: Tool Error Messages phải human-readable:
```python
# Bad — LLM không hiểu gì để fix
return "Error: 404"

# Good — LLM biết phải làm gì tiếp theo
return (
    "Error: Stock symbol 'XYZ123' not found on HOSE exchange. "
    "Please verify the symbol. Common Vietnamese stocks: VCB, FPT, VNM, HPG, MSN. "
    "Try searching with search_company_news tool first to find the correct symbol."
)
```

### CrewAI quick comparison:
```python
# CrewAI — simpler API, good cho learning
from crewai import Agent, Task, Crew

researcher = Agent(
    role='Researcher',
    goal='Find accurate information',
    backstory='Expert at research',
    tools=[search_web],
    llm=llm,
)

research_task = Task(
    description='Research {topic}',
    agent=researcher,
    expected_output='Comprehensive research report',
)

crew = Crew(agents=[researcher], tasks=[research_task])
result = crew.kickoff(inputs={"topic": "Python vs NodeJS"})
```
