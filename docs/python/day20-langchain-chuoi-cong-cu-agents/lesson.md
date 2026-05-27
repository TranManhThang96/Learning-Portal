# Ngày 20: LangChain — Chains, Tools & Agents

## 🎯 Mục tiêu học tập

- Hiểu WHY LangChain tồn tại và khi nào nên/không nên dùng
- Xây dựng chains với LCEL pipe syntax (PromptTemplate | LLM | OutputParser)
- Định nghĩa Tools để extend khả năng LLM
- Implement agent tự động reasoning + tool calling bằng LangChain v1 `create_agent`
- Trace và debug với LangSmith basics

### Version target và API caveat

Snapshot cập nhật ngày 2026-05-25, theo LangChain/LangGraph docs hiện hành qua Context7:

```bash
uv add "langchain>=1.0,<2.0" "langgraph>=1.0,<2.0" "langchain-openai>=1.0,<2.0" "langsmith>=0.4,<1.0"
```

- LangChain v1 docs dùng `from langchain.tools import tool` và high-level `from langchain.agents import create_agent` cho agent mới.
- LCEL vẫn là mental model tốt cho deterministic chains: `prompt | llm | parser`.
- LangGraph vẫn hữu ích khi cần workflow/state machine rõ ràng; `langgraph.prebuilt.create_react_agent(..., prompt=...)` là optional reference, không phải path chính của bài.
- `AgentExecutor`, `initialize_agent`, `LLMChain`, và nhiều imports từ blog LangChain cũ nên xem là legacy cho course này. Pin minor version và chạy smoke import sau mỗi upgrade.
- Model ví dụ đọc được qua env/config trong production. Trong bài dùng `gpt-5` theo docs examples; nếu cần latest frontier model, cấu hình `OPENAI_DEFAULT_MODEL=gpt-5.5` sau khi chạy eval.

Smoke import sau khi cài dependency:

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

agent = create_agent("openai:gpt-5", tools=[ping], system_prompt="You are a concise assistant.")
print("langchain imports OK:", ChatOpenAI, ChatPromptTemplate, StrOutputParser, agent)
PY
```

---

## 🔄 So sánh với NodeJS

| Khái niệm NodeJS/TypeScript | Tương đương LangChain Python | Ghi chú |
|---|---|---|
| `axios` gọi OpenAI API | `ChatOpenAI` wrapper | Abstract hóa, hỗ trợ nhiều provider |
| Template string + Zod | `PromptTemplate` + `PydanticOutputParser` | Type-safe prompt + structured output |
| `pipe()` / RxJS | LCEL `prompt \| llm \| parser` | Chain các bước xử lý |
| Plugin system / Service layer | Tools | LLM gọi services tự động |
| Orchestrator service | Agent | LLM tự quyết định workflow |
| OpenTelemetry / Datadog APM | LangSmith | Tracing cho LLM calls |
| Circuit breaker | Agent max_iterations | Prevent infinite loops |

**Điểm khác biệt quan trọng:**
- NodeJS: bạn tự quyết định gọi service nào, thứ tự nào
- LangChain Agent: LLM tự quyết định gọi tool nào, bao nhiêu lần — bạn chỉ define tools và goal

---

## 📖 Lý thuyết

### 1. Khi Nào Dùng (Và Không Dùng) LangChain

**DÙNG khi:**
- Build chatbot với conversation history
- RAG applications (search + generate)
- Multi-step reasoning với agents
- Cần swap provider dễ dàng (dev=OpenAI, prod=Anthropic)
- Team lớn cần standardized patterns

**KHÔNG dùng khi:**
- Simple one-off LLM call (overkill)
- Cần full control — LangChain có nhiều hidden behavior
- Performance-critical — abstractions có overhead
- LangChain/LangGraph API thay đổi nhanh — pin version, đọc changelog, chạy smoke import trước khi upgrade

### 2. LLM Wrappers & Streaming

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Khởi tạo — giống new OpenAI() trong NodeJS
llm = ChatOpenAI(
    model="gpt-5",
    temperature=0.7,
    max_tokens=1000,
    timeout=30,
    max_retries=2,
)

# invoke — basic call
response = llm.invoke("Giải thích async/await trong 2 câu")
print(response.content)        # string
print(response.usage_metadata)  # token usage

# Với messages — role-based
messages = [
    SystemMessage(content="Bạn là Python tutor cho Senior NodeJS developer."),
    HumanMessage(content="Tại sao Python cần GIL?"),
]
response = llm.invoke(messages)

# Streaming — giống SSE trong NodeJS
for chunk in llm.stream("Giải thích Python generators"):
    print(chunk.content, end="", flush=True)
print()

# Switch provider — đây là power của LangChain
from langchain_anthropic import ChatAnthropic

def get_llm(provider: str = "openai"):
    if provider == "openai":
        return ChatOpenAI(model="gpt-5", temperature=0.7)
    elif provider == "anthropic":
        return ChatAnthropic(model="claude-sonnet-4-6", temperature=0.7)
    raise ValueError(f"Unknown: {provider}")

llm = get_llm("openai")  # đổi sang "anthropic" là xong — code còn lại không đổi
```

### 3. LCEL — LangChain Expression Language

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

# Pipe operator | — giống pipe() trong RxJS
# prompt | llm | parser = chain tự động pass output từng bước

# --- Chain cơ bản ---
prompt = ChatPromptTemplate.from_messages([
    ("system", "Bạn là code reviewer cho {language}."),
    ("human", "Review đoạn code này:\n```\n{code}\n```"),
])

chain = prompt | ChatOpenAI(model="gpt-5", temperature=0) | StrOutputParser()

review = chain.invoke({
    "language": "Python",
    "code": "result = [x for x in range(100) if x % 2 == 0]",
})
print(review)  # string response

# --- Structured output với Pydantic ---
class CodeReview(BaseModel):
    score: int = Field(ge=1, le=10, description="Điểm tổng thể 1-10")
    issues: list[str] = Field(description="Danh sách issues tìm được")
    approved: bool = Field(description="True nếu code đủ tốt")

parser = PydanticOutputParser(pydantic_object=CodeReview)

structured_prompt = ChatPromptTemplate.from_messages([
    ("system", "Review Python code và trả về structured feedback.\n{format_instructions}"),
    ("human", "Code:\n```python\n{code}\n```"),
]).partial(format_instructions=parser.get_format_instructions())

structured_chain = structured_prompt | ChatOpenAI(model="gpt-5", temperature=0) | parser

result = structured_chain.invoke({"code": "x = []; [x.append(i) for i in range(10)]"})
print(f"Score: {result.score}, Approved: {result.approved}")
print(f"Issues: {result.issues}")

# --- Async invoke ---
import asyncio

async def async_review(code: str) -> CodeReview:
    return await structured_chain.ainvoke({"code": code})

# --- Batch invoke (Promise.all equivalent) ---
codes = ["x = 1", "def foo(): pass", "import *"]
reviews = structured_chain.batch([{"code": c} for c in codes])
```

### 4. Memory (Ngắn gọn)

```python
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Pattern đơn giản: lưu history in-memory
store: dict = {}

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

prompt = ChatPromptTemplate.from_messages([
    ("system", "Bạn là Python tutor."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

chain = prompt | ChatOpenAI(model="gpt-5") | StrOutputParser()
chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)

# Mỗi session_id = conversation độc lập
config = {"configurable": {"session_id": "user_alice"}}
r1 = chain_with_history.invoke({"input": "Python list là gì?"}, config=config)
r2 = chain_with_history.invoke({"input": "Cho ví dụ về nó?"}, config=config)
# r2 biết "nó" là list vì có history

# NOTE: Đây chỉ là in-memory — production cần persist to Redis/DB
# Dùng langchain_community.chat_message_histories.RedisChatMessageHistory
```

### 5. Tools

```python
from langchain.tools import tool
from langchain_openai import ChatOpenAI

# @tool decorator — docstring là instructions cho LLM
@tool
def calculate_compound_interest(
    principal: float,
    annual_rate: float,
    years: int,
    compounds_per_year: int = 12,
) -> float:
    """
    Tính lãi suất kép.
    Args:
        principal: Số tiền gốc
        annual_rate: Lãi suất năm dưới dạng decimal (0.07 = 7%)
        years: Số năm đầu tư
        compounds_per_year: Số lần ghép lãi mỗi năm (12=monthly)
    Returns:
        Tổng số tiền sau khi đầu tư
    """
    amount = principal * (1 + annual_rate / compounds_per_year) ** (compounds_per_year * years)
    return round(amount, 2)

@tool
def run_python_code(code: str) -> str:
    """
    Thực thi đoạn Python code ngắn và trả về output.
    Chỉ dùng cho code an toàn, không có file I/O hay network calls.
    """
    import io, contextlib
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {})
        return output.getvalue() or "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"

@tool
def get_stock_price(ticker: str) -> str:
    """Lấy giá cổ phiếu hiện tại. ticker: mã như AAPL, GOOG."""
    prices = {"AAPL": 185.50, "GOOG": 175.20, "NVDA": 875.40}
    price = prices.get(ticker.upper())
    return f"{ticker.upper()}: ${price}" if price else f"Không tìm thấy {ticker}"

# Bind tools vào LLM — LLM tự quyết định khi nào gọi tool
llm = ChatOpenAI(model="gpt-5", temperature=0)
llm_with_tools = llm.bind_tools([calculate_compound_interest, run_python_code, get_stock_price])

from langchain_core.messages import HumanMessage, ToolMessage

# Manual tool loop — hiểu internals trước khi dùng Agent
def run_with_tools(question: str) -> str:
    tools_map = {
        "calculate_compound_interest": calculate_compound_interest,
        "run_python_code": run_python_code,
        "get_stock_price": get_stock_price,
    }
    messages = [HumanMessage(content=question)]

    for _ in range(5):  # max iterations
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            return response.content  # final answer

        for tool_call in response.tool_calls:
            result = tools_map[tool_call["name"]].invoke(tool_call["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

    return "Max iterations reached"

answer = run_with_tools("100 triệu VND gửi ngân hàng lãi 7%/năm sau 10 năm được bao nhiêu?")
print(answer)
```

### 6. Agent với `create_agent` (LangChain v1 path chính)

```python
import os

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent

# Tất cả tools từ section trên
tools = [calculate_compound_interest, run_python_code, get_stock_price]

agent = create_agent(
    model=f"openai:{os.getenv('OPENAI_DEFAULT_MODEL', 'gpt-5')}",
    tools=tools,
    system_prompt="Bạn là assistant kỹ thuật. Luôn dùng tool khi cần tính toán hoặc kiểm tra code.",
)

def run_agent(question: str) -> str:
    result = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })
    # Print intermediate steps
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"[AI] Calling: {[tc['name'] for tc in msg.tool_calls]}")
        elif hasattr(msg, "name") and msg.name:
            print(f"[Tool: {msg.name}] {str(msg.content)[:200]}")

    return result["messages"][-1].content

print("=== Multi-step ===")
answer = run_agent(
    "Nếu tôi đầu tư 50M VND ở lãi suất 8%/năm trong 5 năm, "
    "tính số tiền thu được và viết Python code để verify kết quả."
)
print(f"\nFinal: {answer}")

# Agent với system prompt
system_prompt = (
    "Bạn là financial advisor chuyên nghiệp. "
    "Luôn dùng tools để tính toán chính xác, không đoán. "
    "Giải thích kết quả bằng tiếng Việt."
)
agent_with_prompt = create_agent(
    model=f"openai:{os.getenv('OPENAI_DEFAULT_MODEL', 'gpt-5')}",
    tools=tools,
    system_prompt=system_prompt,
)
```

#### Optional reference: LangGraph prebuilt ReAct

Khi workflow cần checkpointing, human-in-the-loop, hoặc state machine rõ ràng, chuyển sang LangGraph:

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"), temperature=0)
graph_agent = create_react_agent(
    llm,
    tools,
    prompt="Bạn là assistant kỹ thuật. Luôn dùng tool khi cần tính toán hoặc kiểm tra code.",
)
```

### 7. LangSmith — Observability

```python
import os

# Setup — thêm vào .env
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=your_key
# LANGCHAIN_PROJECT=my-python-project

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your_langsmith_key"
os.environ["LANGCHAIN_PROJECT"] = "python-learning-day20"

# Sau khi set env vars, mọi chain/agent invocation tự động được trace
# Xem traces tại: https://smith.langchain.com

# Thêm run_name để dễ identify trong dashboard
from langchain_core.runnables import RunnableConfig

chain.invoke(
    {"code": "x = 1"},
    config=RunnableConfig(run_name="code_review_v1", tags=["review", "python"]),
)

# Evaluate với LangSmith
# from langsmith.evaluation import evaluate
# evaluate(chain, data="my-dataset", evaluators=[...])

# Nếu chưa có LangSmith account: set_debug để print locally
from langchain.globals import set_debug
set_debug(True)  # In tất cả LLM calls ra console — useful khi dev
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix |
|---------|---------|---------|
| Tool docstring không rõ ràng | LLM không biết khi nào dùng tool | Viết docstring chi tiết, ví dụ khi nào dùng |
| Nghĩ `temperature=0` làm agent deterministic tuyệt đối | Tool choice/output vẫn có thể đổi theo model snapshot, provider, hoặc context | Dùng temperature thấp/0 khi model hỗ trợ, cộng với eval và tracing |
| Agent không có max_iterations | Infinite loop tốn tiền API | Luôn set giới hạn iterations |
| Import `langchain` thay `langchain_core` | Deprecated APIs | Dùng `langchain_core` cho stable APIs |
| Upgrade LangChain mà không test | API breaking changes | Pin version, test kỹ trước upgrade |

## ✅ Best Practices

- **LCEL pipe syntax** (`|`) cho chains — readable và composable
- **Temperature thấp/0** cho structured output và agents nếu model hỗ trợ, nhưng vẫn cần eval vì không deterministic tuyệt đối
- **LangSmith** ngay từ đầu — debugging LLM apps mà không trace rất khó
- **Tool docstrings** phải rõ ràng — LLM đọc để quyết định khi nào dùng
- **Fallback providers**: `with_fallbacks([backup_llm])` cho production reliability
- **Dùng import theo docs v1:** `langchain_core` cho primitives, `langchain.tools` cho `@tool`, `langchain.agents.create_agent` cho agent mới

## ⚖️ Trade-offs

| Approach | Pros | Cons | Khi dùng |
|----------|------|------|---------|
| Raw OpenAI SDK | Full control, simple | Boilerplate, provider-locked | Simple scripts |
| LangChain chains | Composable, provider-agnostic | Magic behavior, overhead | Multi-step pipelines |
| LangChain agents | Automatic reasoning | Non-deterministic, expensive | Complex tasks |
| LangGraph | More control than agents | More complex setup | Production agents |

## 📝 Tóm tắt

- LangChain = abstractions cho LLM apps — avoid khi simple, embrace khi complex
- LCEL: `prompt | llm | parser` — composable chain building
- Tools: functions với docstrings mà LLM có thể call tự động
- Agents: `create_agent(model="openai:gpt-5", tools=[...], system_prompt=...)` là path chính; LangGraph `create_react_agent(..., prompt=...)` là optional khi cần state machine/checkpointing
- Memory: `RunnableWithMessageHistory` cho multi-turn conversations
- LangSmith: trace mọi LLM call, không thể thiếu khi debug production
- **Ngày 21**: RAG — kết hợp LangChain với Vector Database cho Retrieval Augmented Generation
