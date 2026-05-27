# Ngày 25: Multi-Agent Systems

## 🎯 Mục tiêu học tập
- Hiểu các kiến trúc multi-agent: orchestrator/sub-agents, peer-to-peer, hierarchical
- Design và implement tools theo best practices (single responsibility, idempotency)
- Xây dựng parallel agent execution với proper state management
- Implement error recovery patterns: retry, fallback, circuit breaker trong agent workflows
- Biết khi nào nên dùng single agent vs multi-agent system

> **Scope cho 2 giờ:** Primary path là Section 1.1 + Section 2: một orchestrator nhỏ, 2-3 tools tốt, budget/rate guard, và log rõ agent nào chạy. Section 3-5 là optional deep dive; không cần làm hết trong một ngày học.
>
> **Version note:** LangGraph/LangChain prebuilt agent APIs thay đổi theo version. Ví dụ `create_react_agent(..., prompt=...)` là style hiện hành trong nhiều docs; nếu version pin của bạn dùng `state_modifier`, ghi rõ trong README và smoke-test import/signature.

## 🔄 So sánh với NodeJS

| Khái niệm Multi-Agent | Tương đương NodeJS | Ghi chú |
|----------------------|-------------------|---------|
| Orchestrator Agent | API Gateway / BFF layer | Nhận request, phân chia cho sub-agents |
| Sub-Agent | Microservice | Chuyên biệt, một nhiệm vụ cụ thể |
| Agent Tool | Service method / gRPC endpoint | Function agent có thể gọi |
| Agent Communication | gRPC / message queue | Sub-agents giao tiếp qua messages |
| Parallel Agents | `Promise.all()` / Worker threads | Chạy nhiều agents cùng lúc |
| Agent State | Redux store / application state | Shared state giữa agents |
| Error Recovery | Retry middleware / circuit breaker | Xử lý lỗi trong agent pipeline |
| Tool Registry | Service registry (Consul) | Catalog các tools available |

**Analogy quan trọng:** Multi-agent system giống như microservices architecture. Orchestrator = API Gateway nhận request từ user và route đến đúng microservice (sub-agent). Mỗi sub-agent chuyên biệt: research agent = search service, code agent = code service, writing agent = content service. Nhưng thay vì HTTP calls, agents communicate qua LLM messages và tool calls.

**Khi nào NÊN dùng multi-agent:**
- Task quá phức tạp cho một agent (context window limit)
- Tasks có thể parallelized (research nhiều topics cùng lúc)
- Cần specialization (code reviewer agent + security scanner agent)
- Cần validation (writer agent + fact-checker agent)

**Khi nào KHÔNG nên dùng multi-agent:**
- Task đơn giản, linear — overhead không đáng
- Budget constrained — mỗi agent = thêm LLM calls
- Latency critical — multi-agent chậm hơn single agent
- Debugging phức tạp vượt quá benefit

## 📖 Lý thuyết

### Section 1: Agent Architectures

**WHY architecture matters?**

Chọn sai architecture = agent hỏng hoặc inefficient. Giống như chọn sai database cho use case — relational cho time series data là disaster.

#### 1.1 Orchestrator / Sub-Agent Pattern

```python
# uv add langgraph langchain-openai langchain-community

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
import json

# === Define Sub-Agent Tools ===
# Tools là cách agents communicate với world (và với nhau)

@tool
def search_web(query: str) -> str:
    """
    Search the web for information about a topic.
    Returns: A summary of relevant search results.

    Tool docstring = tool description cho LLM.
    LLM đọc docstring để biết khi nào nên dùng tool này.
    Viết docstring rõ ràng, cụ thể.
    """
    # Simulate web search (trong production: dùng Tavily, SerpAPI, etc.)
    search_results = {
        "python performance": "Python is interpreted but can be optimized with Cython, NumPy. Typically 10-100x slower than C.",
        "nodejs performance": "Node.js excels at I/O-bound tasks with event loop. Single-threaded but highly concurrent.",
        "default": f"Search results for '{query}': [Relevant information about {query}]"
    }

    for key in search_results:
        if key in query.lower():
            return search_results[key]
    return search_results["default"]


@tool
def analyze_code(code: str, language: str = "python") -> str:
    """
    Analyze code for bugs, performance issues, and style problems.
    Args:
        code: The source code to analyze
        language: Programming language (python, javascript, typescript)
    Returns: Analysis report with issues and recommendations.
    """
    # Simulate code analysis
    issues = []
    if "try" not in code and "except" not in code:
        issues.append("Missing error handling")
    if not any(c == ':' for c in code.split('\n')[0] if 'def ' in code):
        issues.append("Function missing type hints")
    if len(code.split('\n')) > 50:
        issues.append("Function too long, consider refactoring")

    if issues:
        return f"Code analysis for {language}:\nIssues found:\n" + "\n".join(f"- {i}" for i in issues)
    return f"Code analysis for {language}: No major issues found. Code looks good."


@tool
def write_report(
    title: str,
    sections: list[str],
    content: list[str]
) -> str:
    """
    Write a formatted report with title and multiple sections.
    Args:
        title: Report title
        sections: List of section names
        content: List of content for each section (must match sections length)
    Returns: Formatted markdown report.
    """
    if len(sections) != len(content):
        return "Error: sections and content must have the same length"

    report = f"# {title}\n\n"
    for section, text in zip(sections, content):
        report += f"## {section}\n{text}\n\n"

    return report


@tool
def fact_check(statement: str, context: str) -> str:
    """
    Verify if a statement is factually supported by the given context.
    Args:
        statement: The claim to verify
        context: Background information to check against
    Returns: Verdict (SUPPORTED/REFUTED/UNCERTAIN) with explanation.
    """
    # Simulate fact checking
    # Trong production: dùng retrieval + LLM verification
    return f"Fact check for: '{statement}'\nVerdict: UNCERTAIN\nExplanation: Requires additional sources to verify definitively."


# === Orchestrator State ===
class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_request: str
    research_output: str
    code_analysis: str
    report: str
    current_agent: str      # Tracking which agent is working
    agent_step_count: int   # Guard against orchestrator loops
    estimated_tokens: int   # Rough budget tracking
    budget_exceeded: bool


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=800,  # Output cap per LLM call; check provider/version naming if needed
)

MAX_AGENT_STEPS = 8
MAX_ESTIMATED_TOKENS = 15_000


def estimate_tokens(text: str) -> int:
    """Rough guard only; use provider usage metadata for billing-grade tracking."""
    return max(1, len(text) // 4)


def budget_update(state: OrchestratorState, new_text: str = "", llm_calls: int = 1) -> dict:
    """Update simple workflow budget counters."""
    step_count = state.get("agent_step_count", 0) + llm_calls
    estimated = state.get("estimated_tokens", 0) + estimate_tokens(new_text)
    exceeded = step_count >= MAX_AGENT_STEPS or estimated >= MAX_ESTIMATED_TOKENS
    return {
        "agent_step_count": step_count,
        "estimated_tokens": estimated,
        "budget_exceeded": exceeded,
    }


# === Sub-Agents (ReAct pattern) ===
# ReAct = Reasoning + Acting: LLM reason → choose tool → observe → repeat

# Research Sub-Agent: có quyền dùng search
research_agent = create_react_agent(
    llm,
    tools=[search_web, fact_check],
    prompt="""You are a specialized research agent.
Your job: Find accurate, comprehensive information about technical topics.
Be thorough and verify facts when possible.
Always cite your sources (search results)."""
)

# Code Sub-Agent: có quyền dùng code analysis
code_agent = create_react_agent(
    llm,
    tools=[analyze_code],
    prompt="""You are a specialized code analysis agent.
Your job: Review code for bugs, performance, and best practices.
Provide specific, actionable feedback with code examples when helpful."""
)

# Writer Sub-Agent: có quyền tạo report
writer_agent = create_react_agent(
    llm,
    tools=[write_report],
    prompt="""You are a specialized technical writer agent.
Your job: Synthesize research and technical analysis into clear reports.
Write for a senior developer audience. Be precise and structured."""
)


# === Orchestrator Nodes ===
def orchestrator_node(state: OrchestratorState) -> dict:
    """
    Orchestrator: nhận request, lên kế hoạch, delegate cho sub-agents.
    Không tự làm việc — chỉ coordinate.
    """
    response = llm.invoke([
        HumanMessage(content=f"""
You are an orchestrator coordinating multiple specialized agents.

User request: {state['user_request']}

Current state:
- Research done: {bool(state.get('research_output'))}
- Code analyzed: {bool(state.get('code_analysis'))}
- Report written: {bool(state.get('report'))}

Decide the NEXT action:
- If research needed → respond with "DELEGATE:research"
- If code analysis needed → respond with "DELEGATE:code"
- If report writing needed → respond with "DELEGATE:writing"
- If everything done → respond with "COMPLETE"

Only respond with one of these options, nothing else.
""")
    ])

    decision = response.content.strip()
    print(f"[Orchestrator] Decision: {decision}")
    budget = budget_update(state, response.content)
    if budget["budget_exceeded"]:
        decision = "COMPLETE"
        print("[Orchestrator] Budget guard triggered; stopping workflow")

    return {
        "current_agent": decision,
        **budget,
        "messages": [AIMessage(content=f"Orchestrator decision: {decision}")],
    }


def research_node(state: OrchestratorState) -> dict:
    """Invoke research sub-agent"""
    print("[Research Agent] Starting research...")

    agent_result = research_agent.invoke({
        "messages": [HumanMessage(content=f"Research this topic: {state['user_request']}")]
    })

    research_output = agent_result["messages"][-1].content
    print(f"[Research Agent] Complete ({len(research_output)} chars)")

    return {
        "research_output": research_output,
        **budget_update(state, research_output),
        "messages": [AIMessage(content=f"Research complete: {research_output[:100]}...")],
    }


def code_analysis_node(state: OrchestratorState) -> dict:
    """Invoke code analysis sub-agent"""
    print("[Code Agent] Starting analysis...")

    # Extract any code from the request or use placeholder
    code_to_analyze = "# Sample code from user request\ndef example(): pass"

    agent_result = code_agent.invoke({
        "messages": [HumanMessage(
            content=f"Analyze this code:\n{code_to_analyze}\n\nContext: {state['user_request']}"
        )]
    })

    analysis = agent_result["messages"][-1].content
    print(f"[Code Agent] Complete ({len(analysis)} chars)")

    return {
        "code_analysis": analysis,
        **budget_update(state, analysis),
        "messages": [AIMessage(content=f"Code analysis complete")],
    }


def writing_node(state: OrchestratorState) -> dict:
    """Invoke writer sub-agent"""
    print("[Writer Agent] Writing report...")

    agent_result = writer_agent.invoke({
        "messages": [HumanMessage(content=f"""
Write a technical report synthesizing:

RESEARCH FINDINGS:
{state.get('research_output', 'No research available')}

CODE ANALYSIS:
{state.get('code_analysis', 'No code analysis available')}

Original request: {state['user_request']}

Create a comprehensive technical report.
""")]
    })

    report = agent_result["messages"][-1].content
    print(f"[Writer Agent] Complete ({len(report)} chars)")

    return {
        "report": report,
        **budget_update(state, report),
        "messages": [AIMessage(content="Report written successfully")],
    }


def route_orchestrator(state: OrchestratorState) -> str:
    """Route based on orchestrator's decision"""
    if state.get("budget_exceeded", False):
        return "end"

    decision = state.get("current_agent", "")

    if "DELEGATE:research" in decision:
        return "research"
    elif "DELEGATE:code" in decision:
        return "code_analysis"
    elif "DELEGATE:writing" in decision:
        return "writing"
    elif "COMPLETE" in decision:
        return "end"
    else:
        return "end"  # Default fallback


# Build orchestrator graph
orchestrator_graph = StateGraph(OrchestratorState)
orchestrator_graph.add_node("orchestrator", orchestrator_node)
orchestrator_graph.add_node("research", research_node)
orchestrator_graph.add_node("code_analysis", code_analysis_node)
orchestrator_graph.add_node("writing", writing_node)

orchestrator_graph.add_edge(START, "orchestrator")
orchestrator_graph.add_conditional_edges(
    "orchestrator",
    route_orchestrator,
    {
        "research": "research",
        "code_analysis": "code_analysis",
        "writing": "writing",
        "end": END,
    }
)

# Sub-agents route back to orchestrator sau khi xong
orchestrator_graph.add_edge("research", "orchestrator")
orchestrator_graph.add_edge("code_analysis", "orchestrator")
orchestrator_graph.add_edge("writing", "orchestrator")

orchestrator_app = orchestrator_graph.compile()

# Test
# result = orchestrator_app.invoke({
#     "messages": [],
#     "user_request": "Analyze Python vs NodeJS performance for web APIs. Include code example.",
#     "research_output": "",
#     "code_analysis": "",
#     "report": "",
#     "current_agent": "",
#     "agent_step_count": 0,
#     "estimated_tokens": 0,
#     "budget_exceeded": False,
# })
```

### Section 2: Tool Design Best Practices

**WHY tool design quan trọng?**

LLM chọn tool dựa trên tool description. Tool design tệ = LLM chọn sai tool = agent hoạt động sai. Đây là một trong những failure points phổ biến nhất trong production agents.

```python
from langchain_core.tools import tool, StructuredTool
from pydantic import BaseModel, Field
from typing import Optional, Union
import httpx
import asyncio

# Simple process-local rate guard. Production nên dùng shared limiter/queue
# nếu nhiều workers cùng gọi một API provider.
api_rate_limit = asyncio.Semaphore(3)

# === BAD Tool Design ===
@tool
def bad_tool(input: str) -> str:
    """Does stuff with data"""  # Quá vague — LLM không biết khi nào dùng
    return "done"

# Vấn đề:
# - Description "Does stuff with data" vô nghĩa
# - Parameter "input: str" không có context
# - Return type không clear
# - Không có error handling


# === GOOD Tool Design ===
class WeatherInput(BaseModel):
    """Input schema cho weather tool"""
    city: str = Field(description="City name, e.g., 'Ho Chi Minh City', 'Hanoi'")
    country_code: str = Field(
        default="VN",
        description="ISO 3166-1 alpha-2 country code, e.g., 'VN', 'US', 'GB'"
    )
    unit: str = Field(
        default="celsius",
        description="Temperature unit: 'celsius' or 'fahrenheit'"
    )


@tool(args_schema=WeatherInput)
def get_weather(city: str, country_code: str = "VN", unit: str = "celsius") -> str:
    """
    Get current weather information for a specific city.

    Use this tool when the user asks about:
    - Current weather conditions
    - Temperature in a city
    - Whether to bring an umbrella

    Do NOT use for:
    - Weather forecasts (use get_forecast instead)
    - Historical weather data

    Returns: Weather description with temperature, humidity, and conditions.
    Example return: "Ho Chi Minh City: 32°C, Humidity 80%, Partly cloudy"
    """
    # Simulate weather API call
    mock_data = {
        "ho chi minh": {"temp": 32, "humidity": 80, "condition": "Partly cloudy"},
        "hanoi": {"temp": 25, "humidity": 70, "condition": "Clear"},
        "default": {"temp": 28, "humidity": 75, "condition": "Sunny"},
    }

    city_lower = city.lower()
    weather = mock_data.get(city_lower, mock_data["default"])
    temp = weather["temp"]
    if unit == "fahrenheit":
        temp = temp * 9/5 + 32

    return (
        f"{city}, {country_code}: {temp}°{'C' if unit == 'celsius' else 'F'}, "
        f"Humidity {weather['humidity']}%, {weather['condition']}"
    )


# === Tool với Error Handling ===
class DatabaseQueryInput(BaseModel):
    table: str = Field(description="Table name to query")
    conditions: Optional[dict] = Field(
        default=None,
        description="Filter conditions as key-value pairs, e.g., {'status': 'active', 'age': 25}"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of records to return (1-100)"
    )


@tool(args_schema=DatabaseQueryInput)
def query_database(table: str, conditions: Optional[dict] = None, limit: int = 10) -> str:
    """
    Query database records from a specified table.

    IMPORTANT: This is a READ-ONLY operation. Cannot modify data.
    For write operations, use database_write tool (requires approval).

    Args:
        table: Must be one of: users, orders, products, inventory
        conditions: Optional WHERE clause conditions
        limit: Max records (default 10, max 100)

    Returns: JSON string of matching records, or error message.
    """
    # Validate table name (security!)
    allowed_tables = {"users", "orders", "products", "inventory"}
    if table not in allowed_tables:
        return f"Error: Table '{table}' not allowed. Must be one of: {allowed_tables}"

    # Validate conditions (prevent injection)
    if conditions:
        for key, value in conditions.items():
            if not isinstance(value, (str, int, float, bool)):
                return f"Error: Condition value for '{key}' must be a primitive type"

    # Simulate query result
    mock_data = [
        {"id": i, "table": table, **({} if not conditions else conditions)}
        for i in range(1, min(limit + 1, 6))
    ]

    return json.dumps({
        "table": table,
        "conditions": conditions,
        "count": len(mock_data),
        "records": mock_data,
    }, indent=2)


# === Async Tool ===
@tool
async def fetch_api_data(url: str, timeout: int = 10) -> str:
    """
    Fetch data from an external API endpoint.

    Use for: Getting real-time data from REST APIs
    Do NOT use for: Internal database queries (use query_database instead)

    Args:
        url: Must be a valid HTTPS URL
        timeout: Request timeout in seconds (default 10, max 30)

    Returns: API response as string, or error message with status code.
    """
    if not url.startswith("https://"):
        return "Error: Only HTTPS URLs are allowed for security"

    timeout = min(timeout, 30)  # Enforce max timeout

    try:
        async with api_rate_limit:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text[:2000]  # Limit response size
    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout}s"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} - {e.response.text[:200]}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


# === Tool Registry Pattern ===
class ToolRegistry:
    """
    Centralized tool registry.
    Giống như service registry trong microservices.
    """

    def __init__(self):
        self._tools = {}
        self._categories = {}

    def register(self, tool_func, category: str = "general"):
        """Register a tool với category"""
        tool_name = tool_func.name
        self._tools[tool_name] = tool_func
        self._categories.setdefault(category, []).append(tool_name)
        print(f"Registered tool: {tool_name} ({category})")
        return tool_func  # Allow use as decorator

    def get_tools_by_category(self, category: str) -> list:
        """Get all tools in a category"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_all_tools(self) -> list:
        return list(self._tools.values())

    def get_tool_descriptions(self) -> str:
        """Generate human-readable tool catalog"""
        lines = ["Available Tools:"]
        for category, tools in self._categories.items():
            lines.append(f"\n{category.upper()}:")
            for tool_name in tools:
                tool = self._tools[tool_name]
                first_line = tool.description.split('\n')[0]
                lines.append(f"  - {tool_name}: {first_line}")
        return "\n".join(lines)


# Setup registry
registry = ToolRegistry()
registry.register(get_weather, "data_retrieval")
registry.register(query_database, "data_retrieval")
registry.register(fetch_api_data, "data_retrieval")
registry.register(search_web, "research")
registry.register(analyze_code, "analysis")
registry.register(write_report, "output")

print(registry.get_tool_descriptions())
```

### Section 3: Parallel Agent Execution (Optional Deep Dive)

**WHY parallel agents?**

Sequential agents: research → write → review = sum of all latencies.
Parallel agents: research || write (với different parts) → review = max latency nếu tasks thật sự độc lập.

Speedup chỉ xuất hiện khi bottleneck là I/O/LLM latency và provider rate limits cho phép concurrency. Nếu các agents tranh cùng API quota, context chung, hoặc state reducer không merge an toàn, parallelism có thể làm chậm hơn và khó debug hơn.

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated
import operator
import asyncio
import time

def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer an toàn cho fan-in: merge shallow dict, key sau ghi đè key trước."""
    return {**left, **right}

class ParallelResearchState(TypedDict):
    main_topic: str
    subtopics: list[str]
    # Annotated với operator.add = accumulate (không overwrite)
    research_results: Annotated[list[dict], operator.add]
    synthesis: str
    execution_times: Annotated[dict, merge_dicts]  # Merge timing từ parallel branches


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def split_into_subtopics(state: ParallelResearchState) -> dict:
    """Phân tích topic và tạo subtopics để research song song"""
    start = time.perf_counter()

    response = llm.invoke([
        HumanMessage(content=f"""
Split this topic into 3 independent subtopics for parallel research:
Topic: {state['main_topic']}

Return exactly 3 subtopics, one per line, no numbering or bullets.
""")
    ])

    subtopics = [s.strip() for s in response.content.split('\n') if s.strip()][:3]
    print(f"[Split] Subtopics: {subtopics}")

    return {
        "subtopics": subtopics,
        "execution_times": {"split": time.perf_counter() - start}
    }


def make_research_agent(subtopic_index: int):
    """
    Factory function tạo research node cho một subtopic cụ thể.
    Closure pattern để capture subtopic_index.

    Giống như factory function tạo Express route handlers với different configs.
    """
    def research_agent(state: ParallelResearchState) -> dict:
        if subtopic_index >= len(state.get("subtopics", [])):
            return {"research_results": []}

        subtopic = state["subtopics"][subtopic_index]
        start = time.perf_counter()

        print(f"[Research {subtopic_index+1}] Starting: '{subtopic}'")

        response = llm.invoke([
            HumanMessage(content=f"""
Research this specific subtopic thoroughly:
Subtopic: {subtopic}

Provide:
1. Key facts and findings
2. Current state/trends
3. Important considerations

Be concise but comprehensive (max 200 words).
""")
        ])

        elapsed = time.perf_counter() - start
        print(f"[Research {subtopic_index+1}] Complete in {elapsed:.2f}s")

        return {
            "research_results": [{
                "subtopic": subtopic,
                "content": response.content,
                "index": subtopic_index,
            }],
            "execution_times": {f"research_{subtopic_index}": elapsed}
        }

    return research_agent


def synthesize_research(state: ParallelResearchState) -> dict:
    """Fan-in: Tổng hợp tất cả research results"""
    start = time.perf_counter()
    results = state.get("research_results", [])

    # Sort theo index để có thứ tự consistent
    results_sorted = sorted(results, key=lambda x: x.get("index", 0))

    print(f"[Synthesize] Combining {len(results_sorted)} research results")

    research_text = "\n\n".join([
        f"### {r['subtopic']}\n{r['content']}"
        for r in results_sorted
    ])

    response = llm.invoke([
        HumanMessage(content=f"""
Synthesize these research findings into a coherent summary:

{research_text}

Main topic: {state['main_topic']}

Write a 3-paragraph synthesis that:
1. Highlights key findings across all subtopics
2. Identifies patterns and connections
3. Provides actionable insights
""")
    ])

    elapsed = time.perf_counter() - start
    print(f"[Synthesize] Complete in {elapsed:.2f}s")

    return {
        "synthesis": response.content,
        "execution_times": {"synthesize": elapsed}
    }


# Build parallel graph
parallel_research_graph = StateGraph(ParallelResearchState)

# Add nodes
parallel_research_graph.add_node("split", split_into_subtopics)
parallel_research_graph.add_node("research_0", make_research_agent(0))
parallel_research_graph.add_node("research_1", make_research_agent(1))
parallel_research_graph.add_node("research_2", make_research_agent(2))
parallel_research_graph.add_node("synthesize", synthesize_research)

# Fan-out: split → 3 parallel research nodes
parallel_research_graph.add_edge(START, "split")
parallel_research_graph.add_edge("split", "research_0")
parallel_research_graph.add_edge("split", "research_1")
parallel_research_graph.add_edge("split", "research_2")

# Fan-in: tất cả research nodes → synthesize
parallel_research_graph.add_edge("research_0", "synthesize")
parallel_research_graph.add_edge("research_1", "synthesize")
parallel_research_graph.add_edge("research_2", "synthesize")

parallel_research_graph.add_edge("synthesize", END)

parallel_research_app = parallel_research_graph.compile()


def run_and_benchmark():
    """Run parallel agents và show performance stats"""
    topic = "The impact of AI on software development productivity"

    print(f"=== Parallel Research: '{topic}' ===\n")
    overall_start = time.perf_counter()

    result = parallel_research_app.invoke({
        "main_topic": topic,
        "subtopics": [],
        "research_results": [],
        "synthesis": "",
        "execution_times": {},
    })

    total_time = time.perf_counter() - overall_start
    times = result.get("execution_times", {})

    print(f"\n=== Performance Summary ===")
    print(f"Total wall clock time: {total_time:.2f}s")

    research_times = [v for k, v in times.items() if k.startswith("research_")]
    if research_times:
        sequential_time = sum(research_times) + times.get("split", 0) + times.get("synthesize", 0)
        print(f"Sequential would take: {sequential_time:.2f}s")
        print(f"Parallel speedup: {sequential_time/total_time:.1f}x")

    print(f"\nSynthesis preview:")
    print(result.get("synthesis", "")[:300] + "...")

    return result
```

### Section 4: Error Recovery trong Agent Workflows (Optional Deep Dive)

**WHY cần error recovery?**

Production agents thất bại vì:
- LLM timeout / rate limit
- Tool call trả về lỗi
- Invalid JSON trong tool args
- Tool không available
- Context window exceeded

Không có error handling = agent crash, user thấy 500 error. Với error handling tốt = agent tự recovery.

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
import time
import random

# === Retry Pattern ===
def with_retry(func, max_retries: int = 3, backoff_factor: float = 1.5):
    """
    Decorator-style retry cho tool calls.
    Giống như axios-retry hoặc got retry config trong NodeJS.
    """
    def wrapper(*args, **kwargs):
        last_error = None
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    print(f"  ✓ Succeeded on attempt {attempt + 1}")
                return result
            except Exception as e:
                last_error = e
                wait_time = backoff_factor ** attempt
                print(f"  ✗ Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    print(f"  → Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)

        raise RuntimeError(f"All {max_retries} attempts failed. Last error: {last_error}")

    return wrapper


# === Circuit Breaker Pattern ===
class CircuitBreaker:
    """
    Circuit breaker cho tool calls.
    Nếu tool fail nhiều lần → "open circuit" → skip tool, dùng fallback.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Circuit tripped, calls blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.recovery_timeout:
                self.state = "HALF_OPEN"
                print(f"[CircuitBreaker] HALF_OPEN — testing recovery")
                return True
            return False

        if self.state == "HALF_OPEN":
            return True

        return False

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        print(f"[CircuitBreaker] CLOSED — service recovered")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            print(f"[CircuitBreaker] OPEN — circuit tripped after {self.failure_count} failures")

    def execute(self, func, *args, fallback=None, **kwargs):
        if not self.can_execute():
            print(f"[CircuitBreaker] BLOCKED — circuit is OPEN")
            if fallback:
                return fallback(*args, **kwargs)
            raise RuntimeError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            if self.state == "OPEN" and fallback:
                return fallback(*args, **kwargs)
            raise


# === Error-Resilient Agent State ===
class ResilientAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    task: str
    result: Optional[str]
    errors: Annotated[list[str], operator.add]  # Accumulate errors
    retry_count: int
    fallback_used: bool


# Circuit breakers cho từng tool
search_circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
db_circuit = CircuitBreaker(failure_threshold=2, recovery_timeout=60)


def unreliable_search(query: str) -> str:
    """Simulate một flaky search service"""
    if random.random() < 0.4:  # 40% failure rate
        raise ConnectionError("Search service temporarily unavailable")
    return f"Search results for '{query}': [relevant data...]"


def fallback_search(query: str) -> str:
    """Fallback khi search service down"""
    print("[Fallback] Using cached/static search results")
    return f"[CACHED] Basic information about '{query}' from local knowledge base"


def resilient_search_node(state: ResilientAgentState) -> dict:
    """Node với full error recovery"""
    errors = []

    # Attempt 1: Try primary with circuit breaker
    try:
        result = search_circuit.execute(
            with_retry(unreliable_search, max_retries=3),
            state["task"],
            fallback=fallback_search,
        )
        return {
            "result": result,
            "fallback_used": "[CACHED]" in result,
        }
    except Exception as e:
        error_msg = f"Search failed: {str(e)}"
        errors.append(error_msg)
        print(f"[Error] {error_msg}")

    # Attempt 2: Direct fallback nếu circuit breaker fail
    print("[Recovery] Attempting direct fallback...")
    fallback_result = fallback_search(state["task"])

    return {
        "result": fallback_result,
        "errors": errors,
        "fallback_used": True,
        "messages": [AIMessage(content=f"[Using fallback] {fallback_result}")],
    }


def handle_errors_node(state: ResilientAgentState) -> dict:
    """Node tổng hợp và xử lý errors"""
    errors = state.get("errors", [])
    retry_count = state.get("retry_count", 0)

    if errors:
        print(f"[Error Handler] {len(errors)} errors encountered:")
        for error in errors:
            print(f"  - {error}")

    if state.get("fallback_used"):
        print(f"[Error Handler] Fallback was used — result may be less accurate")

    return {
        "messages": [AIMessage(
            content=f"Task completed with {len(errors)} errors. "
                    f"{'Fallback used.' if state.get('fallback_used') else 'Primary succeeded.'}"
        )],
    }


# Resilient graph
resilient_graph = StateGraph(ResilientAgentState)
resilient_graph.add_node("search", resilient_search_node)
resilient_graph.add_node("handle_errors", handle_errors_node)

resilient_graph.add_edge(START, "search")
resilient_graph.add_edge("search", "handle_errors")
resilient_graph.add_edge("handle_errors", END)

resilient_app = resilient_graph.compile()


# === Error Pattern: LLM Self-Correction ===
def run_with_self_correction(app, initial_state: dict, max_attempts: int = 3) -> dict:
    """
    Wrapper để retry toàn bộ agent nếu output không valid.
    Pattern: try → validate → retry nếu invalid

    Giống như request validation middleware với retry logic.
    """
    for attempt in range(max_attempts):
        try:
            result = app.invoke(initial_state)

            # Validate output
            if not result.get("result"):
                raise ValueError("Agent returned empty result")

            if len(result.get("result", "")) < 10:
                raise ValueError(f"Result too short: '{result.get('result')}'")

            print(f"✓ Agent succeeded on attempt {attempt + 1}")
            return result

        except Exception as e:
            print(f"✗ Attempt {attempt + 1}/{max_attempts} failed: {e}")

            if attempt < max_attempts - 1:
                # Add error context cho next attempt
                initial_state = {
                    **initial_state,
                    "messages": initial_state.get("messages", []) + [
                        HumanMessage(content=f"Previous attempt failed: {e}. Please try a different approach.")
                    ],
                    "retry_count": attempt + 1,
                }

    raise RuntimeError(f"Agent failed after {max_attempts} attempts")
```

### Section 5: Production Multi-Agent Patterns (Optional Reference)

```python
# === Pattern: Supervisor Agent ===
# Supervisor quyết định agent nào làm việc tiếp theo
# Linh hoạt hơn hardcoded routing

from langchain_core.output_parsers import JsonOutputParser

class SupervisorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    task: str
    available_agents: list[str]
    next_agent: str
    agent_outputs: Annotated[list[dict], operator.add]
    final_answer: str


def supervisor_node(state: SupervisorState) -> dict:
    """
    Supervisor: dynamically decide which agent goes next.
    Khác với static routing — supervisor có thể thay đổi quyết định
    dựa trên outputs của previous agents.
    """
    agent_outputs = state.get("agent_outputs", [])
    available = state.get("available_agents", [])

    # Remove already-used agents từ available list
    used_agents = [o["agent"] for o in agent_outputs]
    remaining = [a for a in available if a not in used_agents]

    if not remaining:
        return {"next_agent": "FINISH"}

    # LLM quyết định agent tiếp theo dựa trên progress
    outputs_summary = "\n".join([
        f"- {o['agent']}: {str(o.get('output', ''))[:100]}"
        for o in agent_outputs
    ])

    response = llm.invoke([
        HumanMessage(content=f"""
You are a supervisor managing a team of specialized agents.

Task: {state['task']}

Agents already completed:
{outputs_summary if outputs_summary else 'None yet'}

Remaining agents: {remaining}

Which agent should work next? Choose ONE from: {remaining}
Or if task is complete, say: FINISH

Respond with ONLY the agent name or FINISH.
""")
    ])

    next_agent = response.content.strip()
    if next_agent not in remaining and next_agent != "FINISH":
        next_agent = remaining[0] if remaining else "FINISH"

    print(f"[Supervisor] Next agent: {next_agent}")
    return {"next_agent": next_agent}


# === Pattern: Debate / Validation ===
def create_debate_pattern(topic: str, llm: ChatOpenAI) -> dict:
    """
    Hai agents với opposing viewpoints debate một topic.
    Pattern: Writer → Critic → Writer (incorporate criticism) → Final

    Useful for: code review, content quality, decision validation
    """

    writer_response = llm.invoke([
        HumanMessage(content=f"Write a position paper supporting: {topic}")
    ])

    critic_response = llm.invoke([
        HumanMessage(content=f"""
Here is a position paper:
{writer_response.content}

As a critical reviewer, identify 3 weaknesses or gaps in this argument.
Be constructive but thorough.
""")
    ])

    final_response = llm.invoke([
        HumanMessage(content=f"""
Revise this paper incorporating the critical feedback:

ORIGINAL:
{writer_response.content}

CRITICISM:
{critic_response.content}

Write an improved version that addresses all criticism.
""")
    ])

    return {
        "original": writer_response.content,
        "criticism": critic_response.content,
        "final": final_response.content,
    }
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Tool docstring quá vague | LLM chọn sai tool | Viết rõ: "Use for X. Do NOT use for Y." |
| Không validate tool inputs | Security issues, unexpected behavior | Dùng Pydantic BaseModel làm args_schema |
| Sub-agents dùng chung context window | Context pollution, confused outputs | Mỗi sub-agent có messages riêng |
| Không có error handling trong tools | Agent crash khi tool fail | Try/except trong mọi tool, trả về error string |
| Parallel agents với shared mutable state | Race conditions, data corruption | Dùng immutable state, accumulate-only reducers |
| Không có termination condition | Orchestrator loop vô tận | Max iterations, explicit FINISH condition |
| Agent gọi agent (nested) không có limit | Stack overflow, cost explosion | Max depth limit, timeout |
| Không có token/rate budget | Bill tăng nhanh, rate-limit storm | Max steps, max tokens/USD, semaphore/queue per provider |
| Quá nhiều agents cho task đơn giản | Overhead, chậm, tốn tiền | Bắt đầu với single agent, scale khi cần |

## ✅ Best Practices

- **Tool naming là critical:** Tên tool phải mô tả rõ action — `search_academic_papers` tốt hơn `search`.
- **Tool idempotency:** Tools nên idempotent khi có thể — gọi nhiều lần với cùng input = cùng output.
- **Agent specialization:** Mỗi agent một nhiệm vụ cụ thể. Generalist agent = jack of all trades, master of none.
- **Timeout cho mọi tool:** Không có timeout = agent hang indefinitely. Default: 30s cho API calls.
- **Rate limiting:** Nhiều parallel agents gọi cùng API = rate limit errors. Dùng semaphore/queue/shared rate limiter, không chỉ `sleep`.
- **Cost monitoring:** Track tokens per agent, per tool, per workflow. Set hard stop: max steps, max output tokens, max estimated USD.
- **Gradual scaling:** Bắt đầu với 2 agents, thêm khi cần. Đừng over-engineer từ đầu.
- **Logging per agent:** Mỗi agent log với prefix `[AgentName]` — critical cho debugging.

## ⚖️ Trade-offs

| Approach | Latency | Cost | Accuracy | Complexity | Khi nào |
|----------|---------|------|----------|------------|---------|
| Single agent | Nhanh nhất | Thấp | Tốt | Thấp | Tasks đơn giản |
| Sequential multi-agent | Chậm nhất | Trung bình | Tốt hơn | Trung bình | Tasks cần pipeline |
| Parallel multi-agent | Nhanh (= slowest agent) | Cao | Tốt hơn | Cao | Independent subtasks |
| Orchestrator + sub-agents | Trung bình | Cao | Tốt nhất | Cao nhất | Complex workflows |
| Debate pattern | Chậm | Cao | Tốt nhất | Trung bình | Quality-critical output |

## 🚀 Performance Notes

- **Async agents:** `await app.ainvoke(state)` cho toàn bộ graph — tận dụng async I/O.
- **Tool caching:** Cache tool results khi input giống nhau — tránh redundant API calls.
- **Agent batching:** Nếu nhiều users cùng task tương tự → batch inference với LLM.
- **Context pruning:** Truncate long messages trong state trước khi pass cho sub-agents.
- **Token budgeting:** Set output token cap cho mỗi agent, track usage metadata khi provider trả về, và stop workflow khi vượt budget.
- **Parallel tools:** Chỉ bật parallel tool calls khi tools độc lập và rate-limit guard đã có; nếu không, queue tuần tự an toàn hơn.

## 📝 Tóm tắt

- **Multi-agent = microservices cho AI:** Mỗi agent chuyên biệt, orchestrator coordinate — không phải cure-all, cần justify complexity
- **Tool design là nền tảng:** Clear docstrings với "Use for X, NOT for Y", Pydantic schemas, error handling trong mọi tool
- **Parallel execution với fan-out/fan-in:** Độc lập tasks chạy song song, merge kết quả bằng accumulate reducers
- **3 tầng error recovery:** Retry (transient errors) → Circuit breaker (systemic failures) → Fallback (graceful degradation)
- **Orchestrator pattern vs Supervisor pattern:** Orchestrator có hardcoded routing (predictable), Supervisor có LLM-driven routing (flexible)
- **Cost awareness là bắt buộc:** Multi-agent có thể tốn nhiều hơn single agent — luôn track step/token/tool usage và set hard budget limits
- **Start simple:** Single agent trước, thêm agents khi có evidence cần specialization — premature multi-agent là anti-pattern
