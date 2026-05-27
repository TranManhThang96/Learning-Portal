# Ngày 18: OpenAI SDK & LLM Basics

## 🎯 Mục tiêu học tập
- Hiểu cách Responses API hoạt động và mô hình request/response hiện hành
- Implement streaming responses với async/await Python — connect với kiến thức NodeJS
- Hiểu tokens, context window, và cách tính toán cost để optimize
- Dùng Pydantic để ép LLM trả về structured JSON đáng tin cậy
- Xây dựng retry logic, error handling, và rate limiting production-ready

---

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| SDK | `openai` npm package | `openai` pip package — API gần như giống hệt |
| Async | `async/await` + Promise | `async/await` + asyncio — cú pháp giống nhau |
| Streaming | `AsyncIterable`, `for await...of` | `async for chunk in stream` |
| Type validation | Zod, class-validator | Pydantic — mạnh hơn, tích hợp native với OpenAI SDK |
| HTTP client | axios, node-fetch | httpx (async), requests (sync) |
| Retry logic | axios-retry, p-retry | tenacity — decorator-based, rất clean |
| Rate limiting | bottleneck, p-limit | asyncio.Semaphore hoặc `aiolimiter` |
| Environment vars | `dotenv` + `process.env` | `python-dotenv` + `os.environ` |
| Structured output | Zod schema + parse | Pydantic model + `client.responses.parse(...)` |

**API direction hiện hành:** dùng **Responses API** cho code mới. OpenAI docs mô tả Responses là API primitive mới và khuyến nghị cho project mới; Chat Completions vẫn supported để tương thích với code cũ.

> Snapshot tài liệu: cập nhật theo OpenAI docs ngày 2026-05-25. Model names, pricing, context window, và parameter support thay đổi thường xuyên; production code nên đọc model từ config/env, dùng model catalog/pricing page tại thời điểm deploy, và chạy eval trước khi đổi model.

---

## 📖 Lý thuyết

### Section 1: Responses API — Cách hoạt động

**WHY — Tại sao cần hiểu internals của API?**

Nhiều developer dùng OpenAI như "black box" — gửi prompt, nhận text. Nhưng nếu bạn build production application với LLM, bạn cần hiểu: tại sao đôi khi response chậm? Tại sao cùng prompt đôi khi cho kết quả khác nhau? Tại sao cost tăng đột biến? Hiểu cách API hoạt động giúp bạn debug, optimize, và estimate cost chính xác.

**Model là một stateless function:** `f(context) → next_token`. Model không "nhớ" conversation — mỗi lần call API, bạn phải gửi **toàn bộ lịch sử** conversation trong request. Đây là lý do cost tăng theo số lượt chat.

**Autoregressive generation:** Model tạo ra text theo từng token một. Mỗi token mới được predict dựa trên tất cả token trước đó. Đây là lý do streaming response xuất hiện từng chữ một, và tại sao không thể "undo" một phần response đã generate.

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load .env file

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")

# ===== Request cơ bản =====
response = client.responses.create(
    model=MODEL,
    input=[
        {
            "role": "system",
            "content": "Bạn là trợ lý kỹ thuật. Trả lời ngắn gọn, chính xác bằng tiếng Việt."
        },
        {
            "role": "user",
            "content": "Giải thích sự khác biệt giữa process và thread trong 2 câu."
        }
    ],
    max_output_tokens=200,  # Giới hạn độ dài output
    store=False,            # Tắt lưu response nếu không cần conversation state server-side
    # temperature=0.7,      # Chỉ dùng nếu model/endpoint hỗ trợ; không đảm bảo deterministic tuyệt đối
)

# ===== Phân tích response object =====
print(f"Model: {response.model}")
print(f"Content: {response.output_text}")
print(f"Response id: {response.id}")

print(f"\n--- Token Usage ---")
print(f"Input tokens:  {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
print(f"Total tokens:  {response.usage.total_tokens}")
```

```python
import os
from openai import OpenAI

client = OpenAI()
MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")

# ===== Multi-turn Conversation — Quản lý lịch sử =====
# Model stateless → bạn phải maintain conversation history

conversation_history = [
    {"role": "system", "content": "Bạn là expert Python developer. Giúp user học Python từ góc nhìn NodeJS developer."}
]

def chat(user_message: str) -> str:
    """Gửi message và nhận response, tự động maintain history."""
    # Thêm user message vào history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    response = client.responses.create(
        model=MODEL,
        input=conversation_history,
        max_output_tokens=500,
        store=False,
    )

    assistant_message = response.output_text

    # Thêm assistant response vào history để maintain context
    conversation_history.append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message

# Ví dụ conversation
# reply1 = chat("Python list comprehension là gì?")
# reply2 = chat("Cho tôi xem ví dụ với dữ liệu phức tạp hơn")  # Model nhớ context!
# reply3 = chat("Cái đó tương đương với cái gì trong NodeJS?")

# ===== Vấn đề: Context window overflow =====
# Nếu conversation dài, input_tokens sẽ vượt context window → error
# Giải pháp: Sliding window — chỉ giữ N messages gần nhất

MAX_HISTORY_MESSAGES = 10  # Giữ 10 messages gần nhất + system prompt

def chat_with_window(user_message: str, history: list, system_prompt: str) -> tuple[str, list]:
    """Chat với sliding window để tránh context overflow."""
    history.append({"role": "user", "content": user_message})

    # Sliding window: system + N messages gần nhất
    windowed = [{"role": "system", "content": system_prompt}] + history[-MAX_HISTORY_MESSAGES:]

    response = client.responses.create(
        model=MODEL,
        input=windowed,
        max_output_tokens=500,
        store=False,
    )

    assistant_msg = response.output_text
    history.append({"role": "assistant", "content": assistant_msg})

    return assistant_msg, history
```

#### Compatibility note: Chat Completions

Bạn vẫn sẽ gặp code cũ dạng `client.chat.completions.create(model=..., messages=[...])`. Cách đọc nhanh:
- `messages` trong Chat Completions gần tương đương `input` trong Responses cho text conversation đơn giản.
- Output cũ nằm ở `response.choices[0].message.content`; Responses có helper `response.output_text`.
- Structured outputs trong Responses dùng `client.responses.parse(..., text_format=MyPydanticModel)`, không dùng `client.beta.chat.completions.parse(...)` làm path chính.

### Section 2: Streaming Responses với Async

**WHY — Tại sao cần streaming?**

Nếu bạn build chatbot hay interactive assistant, user sẽ nhìn màn hình trống 2-5 giây chờ response hoàn chỉnh. Streaming cho phép hiển thị text ngay khi được generate — cải thiện UX đáng kể. Đây chính xác là cách ChatGPT hoạt động.

Về kỹ thuật, streaming dùng Server-Sent Events (SSE) — HTTP connection giữ mở, server push chunks. Bạn đã biết SSE từ NodeJS, cú pháp Python rất tương tự.

```python
import asyncio
import os
from openai import AsyncOpenAI

# Dùng AsyncOpenAI cho async context
async_client = AsyncOpenAI()

# ===== Streaming cơ bản =====
async def stream_response(prompt: str) -> str:
    """Stream response và print từng token."""
    full_response = ""

    # stream=True → trả về event stream từ Responses API
    stream = await async_client.responses.create(
        model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
        input=[{"role": "user", "content": prompt}],
        stream=True,
        max_output_tokens=300,
    )

    print("Streaming response: ", end="", flush=True)

    # async for → tương đương `for await...of` trong NodeJS
    async for event in stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)  # Print không xuống dòng
            full_response += event.delta
        elif event.type == "response.error":
            raise RuntimeError(event.error)

    print()  # Xuống dòng sau khi xong
    return full_response

# Chạy async function
# asyncio.run(stream_response("Giải thích async/await trong Python so với NodeJS"))

# ===== Streaming với FastAPI — Pattern thực tế =====
# from fastapi import FastAPI
# from fastapi.responses import StreamingResponse
#
# app = FastAPI()
#
# @app.post("/chat/stream")
# async def chat_stream(request: ChatRequest):
#     async def generate():
#         stream = await async_client.responses.create(
#             model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
#             input=[{"role": "user", "content": request.message}],
#             stream=True,
#         )
#         async for event in stream:
#             if event.type == "response.output_text.delta":
#                 yield f"data: {event.delta}\n\n"
#         yield "data: [DONE]\n\n"
#
#     return StreamingResponse(generate(), media_type="text/event-stream")
```

```python
import asyncio
import os
from openai import AsyncOpenAI

async_client = AsyncOpenAI()

# ===== Parallel requests — Tận dụng async =====
# Tương tự Promise.all() trong NodeJS

async def analyze_multiple(texts: list[str]) -> list[str]:
    """Gửi nhiều requests song song thay vì tuần tự."""

    async def analyze_one(text: str, idx: int) -> str:
        response = await async_client.responses.create(
            model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
            input=[
                {"role": "system", "content": "Classify sentiment: positive/negative/neutral. Reply with one word only."},
                {"role": "user", "content": text}
            ],
            max_output_tokens=10,
            temperature=0,
        )
        result = response.output_text.strip().lower()
        print(f"  [{idx}] '{text[:30]}...' → {result}")
        return result

    # asyncio.gather = Promise.all() — chạy song song
    tasks = [analyze_one(text, i) for i, text in enumerate(texts)]
    results = await asyncio.gather(*tasks)
    return list(results)

reviews = [
    "Sản phẩm tuyệt vời, giao hàng nhanh, rất hài lòng!",
    "Chất lượng tệ, vỡ sau 1 tuần sử dụng.",
    "Bình thường, không có gì đặc biệt.",
    "Đóng gói cẩn thận, nhưng màu sắc khác hình.",
    "Mua lần 2 rồi, sẽ tiếp tục ủng hộ shop!",
]

# asyncio.run(analyze_multiple(reviews))
```

### Section 3: Tokens, Context Window, Cost Optimization

**WHY — Tại sao cần hiểu tokens?**

Token là đơn vị billing của OpenAI. Không hiểu tokens = không biết tại sao bill cao, không biết giới hạn input, không biết tại sao bị lỗi. Với production system xử lý hàng nghìn requests/ngày, việc hiểu và optimize token usage có thể tiết kiệm 50-80% cost.

**Token là gì?** Không phải là từ, không phải ký tự. Một token ≈ 4 ký tự tiếng Anh ≈ 0.75 từ tiếng Anh. Tiếng Việt thường tốn nhiều token hơn tiếng Anh vì tokenizer được train chủ yếu trên tiếng Anh.

```python
import os
import tiktoken  # uv add tiktoken — OpenAI's tokenizer library

# ===== Đếm tokens trước khi gửi request =====
def count_tokens(messages: list[dict], model: str | None = None) -> int:
    """Đếm số tokens trong conversation — tránh surprise khi bị lỗi context overflow."""
    model = model or os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")  # fallback cho model mới nếu tiktoken chưa update

    # Mỗi message có overhead tokens (role, formatting)
    tokens_per_message = 3  # Overhead cho mỗi message
    tokens_per_name = 1     # Overhead nếu có 'name' field

    total = 0
    for message in messages:
        total += tokens_per_message
        for key, value in message.items():
            total += len(encoding.encode(value))
            if key == "name":
                total += tokens_per_name

    total += 3  # Reply prime
    return total

# Demo
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain the difference between TCP and UDP protocols."}
]

token_count = count_tokens(messages)
print(f"Tokens in messages: {token_count}")

# Context window thay đổi theo model. Không hardcode trong production.
# Khi estimate batch lớn, đọc context limit từ model catalog hiện hành hoặc config nội bộ.
context_limit = int(os.getenv("OPENAI_CONTEXT_LIMIT_TOKENS", "0"))
if context_limit:
    print(f"Remaining context estimate: {context_limit - token_count:,} tokens")
else:
    print("Context limit chưa cấu hình; kiểm tra model catalog trước khi chạy batch lớn.")
```

```python
import os
import tiktoken
from openai import OpenAI

client = OpenAI()
MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")

# ===== Cost Tracking Decorator =====
# Tương tự middleware tracking trong NodeJS

class CostTracker:
    """Track tổng token usage và cost trong session."""

    def __init__(self, pricing_per_1m: dict[str, dict[str, float]] | None = None):
        # Không hardcode pricing trong source course. Inject từ config cập nhật theo pricing page.
        self.pricing_per_1m = pricing_per_1m or {}
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.cost_breakdown = []

    def track(self, usage, model: str):
        """Record token usage từ API response."""
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1

        pricing = self.pricing_per_1m.get(model)
        if pricing:
            call_cost = (
                input_tokens / 1_000_000 * pricing["input"] +
                output_tokens / 1_000_000 * pricing["output"]
            )
            self.cost_breakdown.append(call_cost)

    @property
    def total_cost(self) -> float:
        return sum(self.cost_breakdown)

    def report(self):
        print(f"\n{'='*40}")
        print(f"Total API calls:        {self.call_count}")
        print(f"Total input tokens:     {self.total_input_tokens:,}")
        print(f"Total output tokens:    {self.total_output_tokens:,}")
        print(f"Total tokens:           {self.total_input_tokens + self.total_output_tokens:,}")
        if self.cost_breakdown:
            print(f"Estimated total cost:   ${self.total_cost:.4f} (pricing from config)")
            print(f"Avg cost per call:      ${self.total_cost/max(self.call_count,1):.6f}")
        else:
            print("Estimated cost:         pricing chưa cấu hình; dùng token totals để tính ngoài code.")
        print(f"{'='*40}")

tracker = CostTracker()

def tracked_response(input_items: list[dict], model: str = MODEL, **kwargs):
    """Wrap API call với cost tracking."""
    response = client.responses.create(
        model=model,
        input=input_items,
        **kwargs
    )
    tracker.track(response.usage, model)
    return response

# Demo usage
# resp = tracked_response(
#     input_items=[{"role": "user", "content": "Hello"}],
#     max_output_tokens=50
# )
# tracker.report()
```

```python
# ===== Cost Optimization Strategies =====

# Strategy 1: Chọn model phù hợp với task
# - Classification, extraction → model mini/nano hiện hành sau khi eval
# - Complex reasoning / tool-heavy → frontier model hiện hành sau khi eval
# - Luôn đọc model từ config để upgrade có kiểm soát

def classify_with_small_model(texts: list[str]) -> list[str]:
    """Dùng model nhỏ đã qua eval cho task classification đơn giản."""
    results = []
    for text in texts:
        response = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": "Classify as SPAM or HAM. Reply with one word."},
                {"role": "user", "content": text}
            ],
            max_output_tokens=5,  # Task đơn giản → limit output tokens
            temperature=0,        # Stable hơn, nhưng không deterministic tuyệt đối
        )
        results.append(response.output_text.strip())
    return results

# Strategy 2: Caching với functools.lru_cache hoặc Redis
import hashlib
import json
from functools import lru_cache

@lru_cache(maxsize=1000)  # Cache trong memory — thay bằng Redis cho production
def cached_classify(text: str) -> str:
    """Cache kết quả cho các text giống nhau — tiết kiệm cost đáng kể."""
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": "Classify sentiment: positive/negative/neutral. One word only."},
            {"role": "user", "content": text}
        ],
        max_output_tokens=5,
        temperature=0,  # stable enough for cache-by-input in many apps, but validate with evals
    )
    return response.output_text.strip()

# Strategy 3: Batch nhiều items trong 1 request
def batch_classify(items: list[str]) -> list[str]:
    """Gửi nhiều items trong 1 request thay vì N requests riêng lẻ."""
    items_formatted = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])

    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": "Classify each item as positive/negative/neutral. Return a JSON array of strings."},
            {"role": "user", "content": f"Items:\n{items_formatted}"}
        ],
        max_output_tokens=200,
        text={"format": {"type": "json_object"}},
    )

    import json
    result = json.loads(response.output_text)
    return result.get("classifications", [])

# Tiết kiệm: N requests → 1 request = N * overhead_tokens tiết kiệm được
# Trade-off: Response quality có thể kém hơn khi batch quá nhiều items
```

### Section 4: Structured Outputs với Pydantic

**WHY — Tại sao cần structured outputs?**

LLM trả về plain text. Nếu bạn cần dữ liệu có cấu trúc (JSON để lưu vào database, object để process tiếp), bạn có 2 vấn đề:
1. LLM có thể không tuân theo format JSON bạn yêu cầu
2. Parsing thủ công brittle và error-prone

Pydantic + OpenAI structured output giải quyết bằng cách: bạn định nghĩa schema bằng Pydantic model, OpenAI **đảm bảo** response match schema (constrained decoding). Không cần parse JSON thủ công, không bị `KeyError`, không bị malformed JSON.

Với NodeJS dev: đây giống như Zod + tự động validation, nhưng OpenAI enforce ở model level chứ không phải client-side parse.

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from openai import OpenAI
import json
import os

client = OpenAI()

# ===== Định nghĩa Schema với Pydantic =====

class PersonInfo(BaseModel):
    """Extract thông tin cá nhân từ text không có cấu trúc."""
    full_name: str = Field(description="Họ và tên đầy đủ")
    age: Optional[int] = Field(None, description="Tuổi, None nếu không rõ")
    email: Optional[str] = Field(None, description="Email address")
    occupation: Optional[str] = Field(None, description="Nghề nghiệp")
    skills: list[str] = Field(default_factory=list, description="Danh sách kỹ năng")

class SentimentAnalysis(BaseModel):
    """Phân tích sentiment của một đoạn text."""
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy từ 0 đến 1")
    key_phrases: list[str] = Field(description="Các cụm từ quan trọng")
    summary: str = Field(max_length=200, description="Tóm tắt trong 1-2 câu")

class BugReport(BaseModel):
    """Parse bug report thành structured format."""
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    affected_component: str
    steps_to_reproduce: list[str]
    expected_behavior: str
    actual_behavior: str
    suggested_fix: Optional[str] = None

# ===== Sử dụng Structured Output =====
def extract_person_info(text: str) -> PersonInfo:
    """Extract thông tin từ text không có cấu trúc."""
    response = client.responses.parse(
        model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
        input=[
            {"role": "system", "content": "Extract person information from the text. Return null for unknown fields."},
            {"role": "user", "content": text}
        ],
        text_format=PersonInfo,  # Pass Pydantic model trực tiếp
    )
    # response.output_parsed đã là PersonInfo object!
    return response.output_parsed

def analyze_sentiment(review: str) -> SentimentAnalysis:
    """Phân tích sentiment với structured output."""
    response = client.responses.parse(
        model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
        input=[
            {"role": "system", "content": "Analyze the sentiment of the customer review."},
            {"role": "user", "content": review}
        ],
        text_format=SentimentAnalysis,
    )
    return response.output_parsed

# Demo
sample_text = """
Xin giới thiệu, tôi là Nguyễn Văn An, 28 tuổi, hiện đang làm Senior Backend Developer
tại một startup fintech. Email của tôi là van.an@example.com. Tôi có kinh nghiệm với
Python, NodeJS, PostgreSQL, và Docker. Hiện tôi đang học thêm về Machine Learning.
"""

# person = extract_person_info(sample_text)
# print(f"Name: {person.full_name}")
# print(f"Age: {person.age}")
# print(f"Skills: {person.skills}")
# Không cần json.loads, không bị KeyError, type-safe!

review = "Sản phẩm tốt nhưng giao hàng chậm hơn dự kiến 3 ngày. Sẽ xem xét lại lần sau."
# sentiment = analyze_sentiment(review)
# print(f"Sentiment: {sentiment.sentiment} (confidence: {sentiment.confidence:.0%})")
# print(f"Summary: {sentiment.summary}")
```

```python
import os
import json
import re
from typing import Optional, Literal, Union

from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

client = OpenAI()

# ===== Nested Structured Output — Complex schemas =====

class Address(BaseModel):
    street: Optional[str] = None
    city: str
    country: str = "Vietnam"

class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Invalid email format')
        return v

class CompanyProfile(BaseModel):
    company_name: str
    industry: str
    employee_count: Optional[int] = None
    founded_year: Optional[int] = None
    contact: ContactInfo
    products: list[str] = Field(default_factory=list, max_length=10)
    is_startup: bool = False
    funding_stage: Optional[Literal["seed", "series_a", "series_b", "series_c", "ipo", "bootstrapped"]] = None

def extract_company_profile(text: str) -> CompanyProfile:
    response = client.responses.parse(
        model=os.getenv("OPENAI_REASONING_MODEL", "gpt-5.5"),  # Dùng model mạnh hơn nếu schema/phân tích khó
        input=[
            {
                "role": "system",
                "content": "Extract company information from the text. Be precise and only include information explicitly mentioned."
            },
            {"role": "user", "content": text}
        ],
        text_format=CompanyProfile,
    )
    return response.output_parsed

# ===== Khi nào dùng json_object vs Pydantic parse? =====

# json_object: Response là valid JSON, nhưng bạn tự handle structure
response_json = client.responses.create(
    model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
    input=[
        {"role": "system", "content": "Return a JSON object with keys: title, tags (array), priority (1-5)."},
        {"role": "user", "content": "Urgent: Fix login bug blocking all users"}
    ],
    text={"format": {"type": "json_object"}},
)
raw_dict = json.loads(response_json.output_text)
# raw_dict có thể có key sai tên, value sai type — không safe

# Pydantic parse: Type-safe, validated, IDE autocomplete
class TaskInfo(BaseModel):
    title: str
    tags: list[str]
    priority: int = Field(ge=1, le=5)

response_parsed = client.responses.parse(
    model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"),
    input=[
        {"role": "system", "content": "Parse the task information."},
        {"role": "user", "content": "Urgent: Fix login bug blocking all users"}
    ],
    text_format=TaskInfo,
)
task = response_parsed.output_parsed
# task.title → str guaranteed
# task.priority → int in [1,5] guaranteed
# IDE sẽ autocomplete task.
```

### Section 5: Error Handling, Retry Logic, Rate Limiting

**WHY — Tại sao production LLM apps cần robust error handling?**

OpenAI API có nhiều loại lỗi khác nhau: rate limits (429), server errors (500/503), timeout, context overflow (400). Không handle đúng sẽ làm app crash hoặc tệ hơn — charge tiền nhưng không trả kết quả. Retry logic không đúng có thể spam API và bị block.

Trong NodeJS, bạn thường dùng `p-retry` hay `axios-retry`. Python có `tenacity` — thư viện mạnh hơn, decorator-based, rất clean.

```python
import time
import random
import asyncio
from openai import OpenAI, AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI()

# ===== Error Types trong OpenAI SDK =====
# openai.RateLimitError   → 429: Too many requests
# openai.APIConnectionError → Network issues
# openai.APIStatusError   → 4xx/5xx từ API
# openai.AuthenticationError → Invalid API key
# openai.BadRequestError  → 400: Malformed request, context overflow

# ===== Retry với Tenacity — Production-grade =====
@retry(
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    wait=wait_exponential(multiplier=1, min=4, max=60),  # 4s, 8s, 16s, 32s, 60s
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def response_with_retry(input_items: list[dict], model: str = "gpt-5", **kwargs):
    """
    API call với automatic retry cho transient errors.

    Retry khi: RateLimitError (429), ConnectionError (network)
    KHÔNG retry: AuthenticationError, BadRequestError (client errors — sẽ fail lại)
    """
    return client.responses.create(
        model=model,
        input=input_items,
        **kwargs
    )

# ===== Full Error Handling =====
from openai import AuthenticationError, BadRequestError

def safe_response(input_items: list[dict], **kwargs) -> str | None:
    """
    Comprehensive error handling cho production.
    Trả về None thay vì raise exception — caller quyết định fallback.
    """
    try:
        response = response_with_retry(input_items=input_items, **kwargs)
        return response.output_text

    except AuthenticationError:
        logger.error("Invalid API key — kiểm tra OPENAI_API_KEY")
        raise  # Config error → không retry, raise để alert

    except BadRequestError as e:
        if "context_length_exceeded" in str(e):
            logger.error(f"Context window overflow: {e}")
            # Xử lý: truncate messages, dùng model với context lớn hơn
            return None
        logger.error(f"Bad request: {e}")
        return None

    except RateLimitError:
        logger.error("Rate limit exceeded sau 5 retries")
        return None  # Caller xử lý fallback

    except APIConnectionError:
        logger.error("Network error sau 5 retries")
        return None

    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        return None

# ===== Rate Limiting với asyncio.Semaphore =====
# Tránh gửi quá nhiều requests song song → bị rate limit
# Tương tự bottleneck hay p-limit trong NodeJS

async def batch_completions_with_rate_limit(
    prompts: list[str],
    max_concurrent: int = 5,  # Tối đa 5 requests song song
    requests_per_minute: int = 60,
) -> list[str]:
    """
    Xử lý batch prompts với rate limiting.

    Args:
        prompts: Danh sách prompts cần xử lý
        max_concurrent: Số requests song song tối đa
        requests_per_minute: Rate limit (phụ thuộc vào tier của bạn)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async_client = AsyncOpenAI()
    min_interval = 60.0 / requests_per_minute  # Khoảng cách tối thiểu giữa 2 requests
    last_request_time = 0.0

    async def process_one(prompt: str, idx: int) -> tuple[int, str]:
        nonlocal last_request_time

        async with semaphore:
            # Simple rate limiting: đảm bảo không gửi quá nhanh
            now = asyncio.get_event_loop().time()
            wait_time = min_interval - (now - last_request_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            last_request_time = asyncio.get_event_loop().time()

            try:
                response = await async_client.responses.create(
                    model="gpt-5",
                    input=[{"role": "user", "content": prompt}],
                    max_output_tokens=100,
                )
                return idx, response.output_text
            except Exception as e:
                logger.error(f"Request {idx} failed: {e}")
                return idx, f"ERROR: {e}"

    # Chạy tất cả với rate limiting
    tasks = [process_one(prompt, i) for i, prompt in enumerate(prompts)]
    raw_results = await asyncio.gather(*tasks)

    # Sort lại theo index để giữ thứ tự
    sorted_results = sorted(raw_results, key=lambda x: x[0])
    return [result for _, result in sorted_results]

# ===== OpenAI Batch API — Cho throughput cao, giá batch có thể thấp hơn =====
# Thích hợp cho: offline processing, không cần realtime
# Xử lý trong completion window; kiểm tra pricing page vì discount thay đổi theo model/endpoint.

# Tạo batch file
# import jsonlines  # uv add jsonlines
# with open('batch_input.jsonl', 'w') as f:
#     for i, prompt in enumerate(prompts):
#         f.write(json.dumps({
#             "custom_id": f"request-{i}",
#             "method": "POST",
#             "url": "/v1/responses",
#             "body": {
#                 "model": "gpt-5",
#                 "input": [{"role": "user", "content": prompt}],
#                 "max_output_tokens": 100
#             }
#         }) + '\n')
#
# # Upload và tạo batch
# batch_input_file = client.files.create(file=open("batch_input.jsonl", "rb"), purpose="batch")
# batch = client.batches.create(
#     input_file_id=batch_input_file.id,
#     endpoint="/v1/responses",
#     completion_window="24h",
# )
# print(f"Batch created: {batch.id}, status: {batch.status}")
```

---

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Không set `max_output_tokens` | Response dài, tốn tiền, có thể timeout | Luôn set `max_output_tokens` phù hợp với task |
| Retry tất cả exception types | Retry AuthenticationError, BadRequestError vô nghĩa | Chỉ retry transient errors (429, 5xx, network) |
| Gửi toàn bộ conversation history | Context overflow khi chat dài | Implement sliding window hoặc summarize cũ |
| Dùng sync client trong async context | Blocking event loop | Dùng `AsyncOpenAI` trong async functions |
| Không giới hạn output | Response dài, tốn tiền, có thể timeout | Set `max_output_tokens` theo task |
| Hardcode API key | Security leak, bị charge ngoài ý muốn | Dùng env variables, không commit vào git |
| Parse JSON thủ công từ LLM response | Fragile, thường bị lỗi | Dùng `client.responses.parse(..., text_format=PydanticModel)` |
| Gọi API từ frontend | API key bị expose | Luôn proxy qua backend của bạn |
| `temperature=1` cho extraction tasks | Kết quả inconsistent hơn | Dùng temperature thấp/0 nếu model hỗ trợ, nhưng vẫn phải eval vì output không deterministic tuyệt đối |

---

## ✅ Best Practices

- **Luôn dùng environment variables cho API key:** `os.environ.get("OPENAI_API_KEY")` — không hardcode, không commit vào git.
- **Set `max_output_tokens` explicit:** Tránh surprise bill, tránh timeout. Estimate dựa trên task — classification cần 5-20 tokens, summary cần 200-500.
- **Temperature thấp/0 cho tasks cần ổn định:** Classification, extraction, code generation nên giảm sampling nếu model hỗ trợ. `temperature=0` không đảm bảo output giống tuyệt đối giữa mọi lần gọi/model snapshot.
- **Dùng Pydantic structured output thay vì parse JSON thủ công:** Type-safe, validated, không bị surprise KeyError.
- **Implement retry với exponential backoff:** Đừng retry ngay lập tức — đợi 4s, 8s, 16s... tránh làm tình trạng rate limit tệ hơn.
- **Track token usage và cost:** Đặt budget alert, review cost weekly, optimize khi cost tăng bất thường.
- **Đọc model từ config:** Bắt đầu với model nhỏ/nhanh hiện hành đã qua eval, chỉ upgrade lên model mạnh hơn khi có metric chứng minh cần thiết.
- **Dùng OpenAI Batch API cho offline processing:** Throughput cao hơn cho workloads không realtime; discount/pricing phải check pricing page tại thời điểm chạy.

---

## ⚖️ Trade-offs

| | Sync Client | Async Client |
|-|------------|--------------|
| **Dùng khi** | Script, CLI tools, simple backends | FastAPI, high-concurrency, batch processing |
| **Performance** | Request tuần tự | Nhiều requests song song |
| **Complexity** | Đơn giản | Cần hiểu asyncio |
| **Streaming** | Supported | Supported (native async) |

| | `json_object` mode | Pydantic `parse()` |
|-|-------------------|-------------------|
| **Validation** | Không — chỉ ensure valid JSON | Có — field types, constraints |
| **Type safety** | Không | Có — IDE autocomplete |
| **Flexibility** | Schema có thể thay đổi | Schema cố định trong code |
| **Error handling** | Bạn tự validate | SDK raise nếu không match schema |

---

## 🚀 Performance Notes

- **Parallel requests > Sequential:** Dùng `asyncio.gather()` để gửi N requests song song, giảm wall time từ N×latency xuống max(latencies).
- **Cache stable responses:** Với prompt/model giống nhau và sampling thấp, output thường ổn định hơn nhưng không guaranteed. Cache bằng Redis với key = hash(model + input + prompt_version) và có TTL.
- **Prefer streaming cho interactive UX:** First token thường đến trong 0.5-1s, full response có thể 5-30s. Streaming cải thiện perceived latency.
- **OpenAI Batch API cho throughput:** ideal cho offline pipelines; kiểm tra completion window và batch pricing theo model/endpoint.
- **Prompt caching:** Nếu provider/model có cached-input pricing, thiết kế static prefix ổn định và đo thực tế trong usage report; không hardcode discount.

---

## 📝 Tóm tắt

- **Responses API là path chính:** Model vẫn không tự nhớ history nếu bạn không dùng stored response/conversation state; thiết kế sliding window hoặc `previous_response_id` khi phù hợp.
- **Tokens là đơn vị billing và giới hạn:** Hiểu token count giúp estimate cost, tránh context overflow. Dùng `tiktoken` để đếm trước khi gửi.
- **Streaming cải thiện UX:** `stream=True` + event `response.output_text.delta` — cú pháp Python rất giống `for await...of` trong NodeJS.
- **Pydantic structured output là must-have cho production:** Đảm bảo response type-safe, validated, không cần parse thủ công.
- **Retry chỉ transient errors:** 429 và 5xx → retry với exponential backoff. 401 và 400 → fix code, không retry.
- **Model routing cần dựa trên eval:** Không hardcode "model X cho 80% tasks"; dùng default model từ env, eval theo workload, rồi mới route/cascade.
- **Cost optimization:** Cache các call có input/model/prompt_version ổn định, batch non-realtime work, track usage theo feature/endpoint để biết đâu tốn nhất.
