# Ngày 34: Project Thực Chiến — Agentic System

## 🎯 Mục tiêu học tập
- Xây dựng production-grade AI Agent với LangGraph
- Implement Human-in-the-loop approval flow
- Persistent agent state với PostgreSQL checkpointer
- Expose agent qua FastAPI REST API
- Tool design patterns: web search, code execution, file I/O

## 🔄 So sánh với NodeJS

| Khía cạnh | NodeJS | Python/LangGraph |
|-----------|--------|-----------------|
| **State machines** | XState, robot | LangGraph (AI-native) |
| **Agent framework** | LangChain.js (limited) | LangGraph — production-ready |
| **Persistence** | Custom Redis/DB | Built-in checkpointers (PostgreSQL, Redis) |
| **Tool calling** | Manual function calling | LangChain Tool + ToolNode |
| **Human review** | Custom webhook flow | Built-in `interrupt()` mechanism |
| **Streaming** | SSE/WebSocket | `astream_events()` |

## 📖 Lý thuyết & Hướng Dẫn

### 1. Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────────┐
│                    Agentic System                        │
│                                                         │
│  ┌──────────┐    ┌──────────────────────────────────┐  │
│  │  Client  │───▶│        FastAPI REST API           │  │
│  └──────────┘    │  POST /agent/run                 │  │
│                  │  GET  /agent/{id}/status          │  │
│                  │  POST /agent/{id}/approve         │  │
│                  └──────────────┬───────────────────┘  │
│                                 │                       │
│                  ┌──────────────▼───────────────────┐  │
│                  │         LangGraph Agent           │  │
│                  │                                   │  │
│                  │  ┌──────────────────────────┐    │  │
│                  │  │     State Machine         │    │  │
│                  │  │                           │    │  │
│                  │  │  START                    │    │  │
│                  │  │    ↓                      │    │  │
│                  │  │  [llm_node]               │    │  │
│                  │  │    ↓                      │    │  │
│                  │  │  [should_continue?]        │    │  │
│                  │  │   ↙          ↘            │    │  │
│                  │  │ [tools]   [human_review]  │    │  │
│                  │  │   ↘          ↙            │    │  │
│                  │  │  [llm_node] ← ← ←         │    │  │
│                  │  │    ↓                      │    │  │
│                  │  │   END                     │    │  │
│                  │  └──────────────────────────┘    │  │
│                  └───────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────┐  ┌────────────────────────────┐  │
│  │   Tools          │  │   PostgreSQL Checkpointer  │  │
│  │  - web_search    │  │   (Persistent State)       │  │
│  │  - code_execute  │  └────────────────────────────┘  │
│  │  - file_io       │                                   │
│  └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

### 2. Agent State Definition

```python
# app/agent/state.py
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    State được pass qua tất cả nodes trong LangGraph.
    Annotated[list, operator.add] = append-only list (messages không bị overwrite)
    """
    messages: Annotated[list[BaseMessage], operator.add]

    # Metadata
    task_id: str
    user_id: str

    # Human-in-the-loop
    pending_tool_calls: list[dict]  # Tool calls chờ approval
    human_approved: bool | None     # None = chưa review, True/False = quyết định

    # Tracking
    iteration_count: int
    total_tokens_used: int
```

### 3. Tool Definitions

```python
# app/agent/tools/web_search.py
import os
from langchain_core.tools import tool

@tool
async def web_search(query: str) -> str:
    """
    Tìm kiếm thông tin trên web.

    Args:
        query: Câu hỏi hoặc từ khóa cần tìm kiếm

    Returns:
        Kết quả tìm kiếm dưới dạng text
    """
    # Dùng Tavily API (tốt nhất cho agents)
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        response = client.search(query, max_results=3)
        results = response.get("results", [])
        return "\n\n".join(
            f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
            for r in results
        )
    except ImportError:
        # Fallback nếu không có Tavily
        return f"[Mock search result for: {query}]\nFound relevant information about {query}."
```

```python
# app/agent/tools/code_executor.py
import ast
import io
import sys
from langchain_core.tools import tool

BLOCKED_MODULES = {"os", "subprocess", "sys", "shutil", "socket"}
ALLOWED_BUILTINS = {
    "print", "len", "range", "enumerate", "zip", "map", "filter",
    "list", "dict", "set", "tuple", "str", "int", "float", "bool",
    "sum", "min", "max", "abs", "round", "sorted",
}

@tool
def execute_python_code(code: str) -> str:
    """
    Thực thi Python code an toàn trong sandbox.
    Chỉ cho phép built-in functions an toàn, không có file system access.

    Args:
        code: Python code cần thực thi

    Returns:
        Output của code hoặc error message
    """
    # Parse AST để check imports
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax Error: {e}"

    # Check blocked imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in BLOCKED_MODULES:
                    return f"Security Error: Import '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module in BLOCKED_MODULES:
                return f"Security Error: Import from '{node.module}' is not allowed"

    # Execute với restricted globals
    output_buffer = io.StringIO()
    restricted_globals = {
        "__builtins__": {k: __builtins__[k] for k in ALLOWED_BUILTINS if k in __builtins__}
        if isinstance(__builtins__, dict)
        else {k: getattr(__builtins__, k) for k in ALLOWED_BUILTINS if hasattr(__builtins__, k)},
    }

    old_stdout = sys.stdout
    sys.stdout = output_buffer
    try:
        exec(code, restricted_globals)  # noqa: S102
        output = output_buffer.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Runtime Error: {type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout
```

```python
# app/agent/tools/file_io.py
from pathlib import Path
from langchain_core.tools import tool

ALLOWED_BASE_DIR = Path("/tmp/agent_workspace")
ALLOWED_BASE_DIR.mkdir(parents=True, exist_ok=True)

def _safe_path(filename: str) -> Path:
    """Ensure path là trong allowed directory (path traversal prevention)."""
    safe_path = (ALLOWED_BASE_DIR / filename).resolve()
    if not str(safe_path).startswith(str(ALLOWED_BASE_DIR)):
        raise ValueError(f"Access denied: {filename}")
    return safe_path

@tool
def read_file(filename: str) -> str:
    """
    Đọc nội dung file từ workspace directory.

    Args:
        filename: Tên file (không bao gồm path)
    """
    try:
        path = _safe_path(filename)
        if not path.exists():
            return f"File not found: {filename}"
        return path.read_text(encoding="utf-8")
    except ValueError as e:
        return f"Security Error: {e}"

@tool
def write_file(filename: str, content: str) -> str:
    """
    Ghi nội dung vào file trong workspace directory.

    Args:
        filename: Tên file
        content: Nội dung cần ghi
    """
    try:
        path = _safe_path(filename)
        path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {filename}"
    except ValueError as e:
        return f"Security Error: {e}"

@tool
def list_files() -> str:
    """Liệt kê tất cả files trong workspace directory."""
    files = list(ALLOWED_BASE_DIR.glob("*"))
    if not files:
        return "Workspace is empty"
    return "\n".join(f"- {f.name} ({f.stat().st_size} bytes)" for f in files)
```

### 4. LangGraph Graph Definition

```python
# app/agent/graph.py
import operator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from app.agent.state import AgentState
from app.agent.tools.code_executor import execute_python_code
from app.agent.tools.file_io import list_files, read_file, write_file
from app.agent.tools.web_search import web_search
from app.config import get_settings

settings = get_settings()

# All available tools
TOOLS = [web_search, execute_python_code, read_file, write_file, list_files]

# Tools requiring human approval trước khi execute
TOOLS_REQUIRING_APPROVAL = {"execute_python_code", "write_file"}

# LLM với tools bound
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0,
    api_key=settings.require_openai_api_key(),
).bind_tools(TOOLS)


def llm_node(state: AgentState) -> dict:
    """Node: gọi LLM để quyết định bước tiếp theo."""
    response = llm.invoke(state["messages"])

    # Track token usage
    usage = getattr(response, "usage_metadata", None)
    tokens_used = (usage.get("total_tokens", 0) if usage else 0)

    return {
        "messages": [response],
        "iteration_count": state["iteration_count"] + 1,
        "total_tokens_used": state["total_tokens_used"] + tokens_used,
    }


def human_review_node(state: AgentState) -> dict:
    """
    Node: Pause bằng interrupt() để chờ human approval.
    Resume bằng Command(resume={"approved": bool}) với cùng thread_id.
    """
    last_message = state["messages"][-1]

    # Extract tool calls cần approval
    pending = []
    if hasattr(last_message, "tool_calls"):
        for tc in last_message.tool_calls:
            if tc["name"] in TOOLS_REQUIRING_APPROVAL:
                pending.append(tc)

    decision = interrupt(
        {"question": "Approve these tool calls?", "tool_calls": pending}
    )
    approved = (
        decision.get("approved", False)
        if isinstance(decision, dict)
        else bool(decision)
    )
    return {"pending_tool_calls": pending, "human_approved": approved}


def route_after_llm(state: AgentState) -> Literal["tools", "human_review", "end"]:
    """Conditional edge: quyết định node tiếp theo sau LLM."""
    last_message = state["messages"][-1]

    # Không có tool calls — done
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "end"

    # Quá nhiều iterations — dừng để tránh infinite loop
    if state["iteration_count"] >= 10:
        return "end"

    # Check xem có tool nào cần approval không
    for tc in last_message.tool_calls:
        if tc["name"] in TOOLS_REQUIRING_APPROVAL:
            return "human_review"

    return "tools"


def route_after_human_review(state: AgentState) -> Literal["tools", "end"]:
    """Conditional edge: sau khi human review."""
    if state["human_approved"] is True:
        return "tools"
    return "end"  # Rejected → end


def build_graph() -> StateGraph:
    """Build và return compiled LangGraph graph."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", llm_node)
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.add_node("human_review", human_review_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        route_after_llm,
        {"tools": "tools", "human_review": "human_review", "end": END},
    )
    workflow.add_edge("tools", "agent")  # Sau tools → quay lại agent
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {"tools": "tools", "end": END},
    )

    return workflow
```

### 5. PostgreSQL Checkpointer

```python
# app/agent/checkpointer.py
"""
PostgreSQL checkpointer để persist agent state.
Cho phép resume agent từ bất kỳ điểm nào.
"""
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def checkpointer_lifespan() -> AsyncIterator[AsyncPostgresSaver]:
    """Mở PostgreSQL checkpointer một lần trong FastAPI lifespan."""
    # Chuyển asyncpg URL sang psycopg URL
    db_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        await checkpointer.setup()  # Tạo tables nếu chưa có
        yield checkpointer
```

FastAPI app mở checkpointer và compile graph một lần:

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.agent.checkpointer import checkpointer_lifespan
from app.agent.graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with checkpointer_lifespan() as checkpointer:
        app.state.agent_graph = build_graph().compile(checkpointer=checkpointer)
        yield


app = FastAPI(lifespan=lifespan)
```

Điểm review quan trọng: route handler không được tạo `AsyncPostgresSaver` hoặc gọi `build_graph().compile(...)` mỗi request. Checkpointer có connection pool và graph compile có state/tool wiring; mở trong lifespan một lần giúp tránh connection leak, latency spike và state resume sai.

### 6. FastAPI Interface

```python
# app/api/agent.py
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.state import AgentState

router = APIRouter(prefix="/agent", tags=["agent"])


class RunRequest(BaseModel):
    task: str
    user_id: str = "default"


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    reason: str | None = None


class RunResponse(BaseModel):
    thread_id: str
    status: str
    message: str


@router.post("/run", response_model=RunResponse)
async def run_agent(request: RunRequest, http_request: Request) -> RunResponse:
    """Start một agent run."""
    thread_id = str(uuid.uuid4())
    graph = http_request.app.state.agent_graph

    initial_state: AgentState = {
        "messages": [HumanMessage(content=request.task)],
        "task_id": thread_id,
        "user_id": request.user_id,
        "pending_tool_calls": [],
        "human_approved": None,
        "iteration_count": 0,
        "total_tokens_used": 0,
    }

    config = {"configurable": {"thread_id": thread_id}}

    # Run graph (có thể pause tại human_review node)
    result = await graph.ainvoke(initial_state, config=config)

    # interrupt() trả về __interrupt__; resume bằng /approve cùng thread_id
    if result.get("__interrupt__"):
        return RunResponse(
            thread_id=thread_id,
            status="awaiting_approval",
            message="Agent is waiting for human approval",
        )

    last_message = result["messages"][-1]
    return RunResponse(
        thread_id=thread_id,
        status="completed",
        message=last_message.content,
    )


@router.post("/approve")
async def approve_action(request: ApprovalRequest, http_request: Request) -> dict:
    """Human approval/rejection cho pending tool calls."""
    graph = http_request.app.state.agent_graph
    config = {"configurable": {"thread_id": request.thread_id}}

    # Resume đúng interrupt point. Không dùng aupdate_state để skip node.
    result = await graph.ainvoke(
        Command(resume={"approved": request.approved}),
        config=config,
    )

    if request.approved:
        last_message = result["messages"][-1]
        return {"status": "completed", "result": last_message.content}
    else:
        return {"status": "rejected", "message": "Action was rejected by user"}


@router.get("/{thread_id}/status")
async def get_agent_status(thread_id: str, request: Request) -> dict[str, Any]:
    """Lấy trạng thái hiện tại của agent run."""
    graph = request.app.state.agent_graph
    config = {"configurable": {"thread_id": thread_id}}

    state = await graph.aget_state(config)
    if not state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread {thread_id} not found",
        )

    return {
        "thread_id": thread_id,
        "iteration_count": state.values.get("iteration_count", 0),
        "tokens_used": state.values.get("total_tokens_used", 0),
        "pending_approvals": state.values.get("pending_tool_calls", []),
        "message_count": len(state.values.get("messages", [])),
    }
```

### 7. Streaming Agent Responses

```python
# Streaming với astream_events (SSE)
import json
from fastapi import Request
from fastapi.responses import StreamingResponse

@router.post("/run/stream")
async def stream_agent_run(request: RunRequest, http_request: Request) -> StreamingResponse:
    """Stream agent execution steps via SSE."""
    thread_id = str(uuid.uuid4())
    graph = http_request.app.state.agent_graph

    initial_state: AgentState = {
        "messages": [HumanMessage(content=request.task)],
        "task_id": thread_id,
        "user_id": request.user_id,
        "pending_tool_calls": [],
        "human_approved": None,
        "iteration_count": 0,
        "total_tokens_used": 0,
    }

    config = {"configurable": {"thread_id": thread_id}}

    async def generate():
        # Stream events từ graph
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_type = event["event"]

            if event_type == "on_chat_model_stream":
                # LLM token streaming
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    data = json.dumps({"type": "token", "content": chunk.content})
                    yield f"data: {data}\n\n"

            elif event_type == "on_tool_start":
                # Tool execution started
                data = json.dumps({
                    "type": "tool_start",
                    "tool": event["name"],
                    "input": str(event["data"].get("input", ""))[:200],
                })
                yield f"data: {data}\n\n"

            elif event_type == "on_tool_end":
                # Tool execution finished
                data = json.dumps({
                    "type": "tool_end",
                    "tool": event["name"],
                    "output": str(event["data"].get("output", ""))[:500],
                })
                yield f"data: {data}\n\n"

        # Done signal
        yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Không set `max_iterations` | Agent loop vô hạn, tốn tiền | Set limit và kiểm tra trong conditional edge |
| Tool có side effects mà không có approval | Nguy hiểm: xóa files, gửi email không mong muốn | Classify tools: safe vs dangerous, yêu cầu approval |
| State không serialize được | Checkpointing fails | Dùng TypedDict với serializable types |
| Không handle tool errors | Agent stuck hoặc crash | Wrap tool calls với try/except, return error string |
| `temperature > 0` cho tool-using agents | Tools được gọi với wrong arguments | `temperature=0` cho deterministic tool use |
| Code execution không có sandbox | RCE vulnerability | Restrict globals, block dangerous imports |

## ✅ Best Practices

- **Classify tools**: Safe (read-only) vs Dangerous (write/execute) — approve dangerous ones
- **Tool docstrings rõ ràng**: LLM dùng docstring để biết khi nào gọi tool — viết rõ args và returns
- **Giới hạn iterations**: `max_iterations=10` — tránh infinite loops và runaway costs
- **Persist state** ngay từ đầu — users expect to resume conversations
- **Stream intermediate steps** — giảm perceived latency, users thấy progress
- **Log tất cả tool calls** — critical cho debugging agents
- **Test với mock tools** — tránh real API calls trong tests

## ⚖️ Trade-offs

### ReAct vs LangGraph
| | ReAct (simple) | LangGraph |
|---|---|---|
| **Complexity** | Đơn giản | Phức tạp hơn |
| **Flexibility** | Ít flexible | Rất flexible |
| **Human-in-loop** | Khó implement | Built-in support |
| **Persistence** | Manual | Built-in checkpointers |
| **Use when** | Simple linear tasks | Complex workflows, HITL |

### PostgreSQL vs Redis Checkpointer
- **PostgreSQL**: Durable, queryable, dùng chung với app DB — recommended cho production
- **Redis**: Nhanh hơn, nhưng có thể mất data, phù hợp cho short-lived sessions

## 🚀 Performance Notes

- **Async tools**: Tools phải là `async def` để không block event loop
- **Tool parallelism**: LangGraph tự động parallel execute independent tool calls
- **Checkpoint frequency**: Checkpoint sau mỗi node — có thể tắt để tăng speed
- **Token optimization**: Truncate long tool outputs trước khi add vào messages

## 📝 Tóm tắt

- LangGraph = state machine cho AI agents: nodes (functions) + edges (routing logic)
- AgentState là TypedDict — define rõ data flow qua toàn bộ graph
- Human-in-the-loop: `interrupt()` pause graph thật; API resume bằng `Command(resume=...)` với cùng `thread_id`
- Tools phải có docstrings tốt, error handling, và safety restrictions
- PostgreSQL checkpointer cho persistence — agents có thể resume sau restart
- Streaming với `astream_events()` cho real-time UX
- Always set max_iterations — agents can loop indefinitely without it
