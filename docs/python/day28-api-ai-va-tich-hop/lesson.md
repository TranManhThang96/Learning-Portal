# Ngày 28: AI APIs & Integrations

## 🎯 Mục tiêu học tập
- Sử dụng thành thạo Anthropic Claude SDK và Google Gemini API trong Python
- Xử lý multi-modal inputs (hình ảnh với vision API, audio với Whisper)
- Implement function calling / tool use cho cả Claude và Gemini
- Xây dựng abstraction layer để swap giữa các AI providers

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Claude SDK | `@anthropic-ai/sdk` | `anthropic` |
| Gemini SDK | `@google/genai` | `google-genai` (`from google import genai`) |
| Whisper | Dùng API | `openai-whisper` (local) hoặc API |
| OpenAI text/tools | Responses API | `client.responses.create(...)` |
| Function/tool calling | `tools: [...]` trong request body | Provider-specific schema, app tự execute tool |
| Streaming | `for await (const chunk of stream)` | `for chunk in stream:` |
| Error handling | `try/catch` với typed errors | `try/except` với SDK errors |
| Type safety | Strict TypeScript interfaces | Python type hints (less strict) |

Điểm thú vị: API contracts của Claude và Gemini khá giống OpenAI, nên nếu biết một cái sẽ hiểu nhanh cái kia.

## API surface hiện hành cần nhớ

- **OpenAI:** dạy Responses API làm path chính cho text/image, streaming, structured outputs và tool calling. Audio transcription dùng Audio API; realtime voice dùng Realtime API. Chat Completions vẫn được hỗ trợ cho compatibility nhưng không nên là default cho project mới.
- **Anthropic:** Messages API dùng `system` ở top-level, không có role `"system"` trong `messages`. Tool use trả về `tool_use`; app chạy function rồi gửi `tool_result` trong turn kế tiếp.
- **Gemini:** Google khuyến nghị Google GenAI SDK (`google-genai`) với `client.models.generate_content(...)` và `client.chats.create(...)`. Package `google-generativeai` là surface cũ, chỉ giữ khi maintain code legacy.
- **Model names/pricing:** luôn đọc từ config/env (`CLAUDE_MODEL`, `GEMINI_MODEL`, `OPENAI_MODEL`) và pricing page hiện hành. Không hardcode model/cost vào business logic hoặc slide bài học.

## 📖 Lý thuyết

### 1. Anthropic Claude SDK

**WHY:** Claude API là một trong những API AI mạnh nhất, đặc biệt giỏi về code analysis, reasoning dài, và following complex instructions. Python SDK wrap REST API với type safety tốt.

```python
# uv add anthropic
import anthropic
import os

# Client tự động dùng ANTHROPIC_API_KEY từ environment
client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)
CLAUDE_MODEL = os.environ["CLAUDE_MODEL"]

# === BASIC MESSAGE ===
def simple_claude_call(prompt: str) -> str:
    """Gọi Claude cơ bản"""
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return message.content[0].text

response = simple_claude_call("Giải thích Python generators trong 3 câu")
print(response)
```

```python
# === SYSTEM PROMPT + MULTI-TURN ===
import anthropic
import os

client = anthropic.Anthropic()

def chat_with_system(
    system: str,
    conversation: list[dict],
    new_message: str
) -> str:
    """
    Multi-turn conversation với system prompt.
    conversation: list of {"role": "user"/"assistant", "content": "..."}
    """
    messages = conversation + [{"role": "user", "content": new_message}]

    response = client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=2048,
        system=system,   # system prompt đặt ngoài messages array
        messages=messages
    )

    return response.content[0].text

# Khởi tạo conversation
system = "Bạn là Python expert. Trả lời ngắn gọn, luôn có code example."
history = []

# Turn 1
r1 = chat_with_system(system, history, "Decorator là gì?")
print("Claude:", r1)
history.extend([
    {"role": "user", "content": "Decorator là gì?"},
    {"role": "assistant", "content": r1}
])

# Turn 2 — có context từ turn 1
r2 = chat_with_system(system, history, "Cho ví dụ về timing decorator")
print("\nClaude:", r2)
```

```python
# === STREAMING ===
import anthropic
import os

client = anthropic.Anthropic()

def stream_claude(prompt: str):
    """Stream response từng token"""
    print("Claude: ", end="", flush=True)

    # Context manager tự động close stream
    with client.messages.stream(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print()  # newline
    print(f"\n[Total tokens: {stream.get_final_message().usage.input_tokens} in, "
          f"{stream.get_final_message().usage.output_tokens} out]")

stream_claude("Viết quicksort bằng Python với comments")
```

```python
# === VISION — Phân tích hình ảnh ===
import anthropic
import base64
import os
from pathlib import Path

client = anthropic.Anthropic()

def analyze_image_from_file(image_path: str, question: str) -> str:
    """Phân tích hình ảnh từ local file"""
    # Đọc và encode image sang base64
    image_data = Path(image_path).read_bytes()
    base64_image = base64.standard_b64encode(image_data).decode("utf-8")

    # Xác định media type từ extension
    ext = Path(image_path).suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    response = client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_image,
                    },
                },
                {
                    "type": "text",
                    "text": question
                }
            ],
        }]
    )

    return response.content[0].text

def analyze_image_from_url(image_url: str, question: str) -> str:
    """Phân tích hình ảnh từ URL"""
    response = client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": image_url,
                    },
                },
                {
                    "type": "text",
                    "text": question
                }
            ],
        }]
    )

    return response.content[0].text

# Test với URL (không cần file local)
# result = analyze_image_from_url(
#     "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png",
#     "Mô tả hình ảnh này"
# )
# print(result)
```

### 2. Google Gemini API

**WHY:** Gemini có các model Flash/Pro tối ưu cho latency, multimodal và long-context. Tên model cụ thể thay đổi theo thời gian, nên code production nên lấy model từ config thay vì hardcode trong business logic.

```python
# uv add google-genai
from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
GEMINI_MODEL = os.environ["GEMINI_MODEL"]

# === BASIC USAGE ===
def gemini_simple(prompt: str, model_name: str = GEMINI_MODEL) -> str:
    """Gọi Gemini cơ bản"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    return response.text

result = gemini_simple("Giải thích async/await trong Python trong 2 câu")
print(result)
```

```python
# === CHAT SESSION (giữ history) ===
from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
GEMINI_MODEL = os.environ["GEMINI_MODEL"]

def chat_gemini(chat_session, message: str) -> str:
    """Gửi message trong session"""
    response = chat_session.send_message(message)
    return response.text

# Demo
chat = client.chats.create(model=GEMINI_MODEL)
r1 = chat_gemini(chat, "Context manager là gì?")
print("Gemini:", r1)

r2 = chat_gemini(chat, "Tạo custom context manager cho timing")
print("\nGemini:", r2)

# Xem history
print(f"\nConversation turns: {len(chat.get_history())}")
```

```python
# === GEMINI VISION ===
from google import genai
from pathlib import Path
import PIL.Image  # uv add Pillow
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
GEMINI_MODEL = os.environ["GEMINI_MODEL"]

def analyze_image_gemini(image_path: str, question: str) -> str:
    """Phân tích image với Gemini Vision"""
    image = PIL.Image.open(image_path)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[image, question],
    )
    return response.text

def compare_images(image_paths: list[str], question: str) -> str:
    """So sánh nhiều hình ảnh"""
    content = [question]
    for path in image_paths:
        content.append(PIL.Image.open(path))

    response = client.models.generate_content(
        model=os.getenv("GEMINI_PRO_MODEL", GEMINI_MODEL),
        contents=content,
    )
    return response.text
```

### 3. Multi-modal: Audio với Whisper

**WHY:** Whisper là model speech-to-text của OpenAI, chạy được local (không tốn tiền) và hỗ trợ 99 ngôn ngữ bao gồm tiếng Việt.

```python
# uv add openai-whisper
# Cần ffmpeg: sudo apt install ffmpeg (Linux) hoặc brew install ffmpeg (Mac)
import whisper
import time

def transcribe_audio(
    audio_path: str,
    model_size: str = "base",  # tiny, base, small, medium, large
    language: str = None        # None = auto-detect
) -> dict:
    """
    Transcribe audio file sang text dùng local Whisper.

    Model sizes và trade-offs:
    - tiny:   39M params, ~1GB VRAM, ~32x realtime, less accurate
    - base:   74M params, ~1GB VRAM, ~16x realtime, good for English
    - small:  244M params, ~2GB VRAM, ~6x realtime
    - medium: 769M params, ~5GB VRAM, ~2x realtime
    - large:  1550M params, ~10GB VRAM, ~1x realtime, most accurate
    """
    print(f"Loading Whisper {model_size} model...")
    model = whisper.load_model(model_size)

    start = time.time()
    result = model.transcribe(
        audio_path,
        language=language,
        verbose=False,
        word_timestamps=True  # cho biết timestamp của từng từ
    )
    elapsed = time.time() - start

    return {
        "text": result["text"],
        "language": result["language"],
        "duration_seconds": elapsed,
        "segments": result.get("segments", [])  # timestamp per segment
    }

# Test (cần file audio thực)
# result = transcribe_audio("meeting.mp3", model_size="base")
# print(f"Language detected: {result['language']}")
# print(f"Transcript: {result['text']}")
# print(f"Processing time: {result['duration_seconds']:.1f}s")
```

```python
# === WHISPER VIA API (không cần local compute) ===
import os
from openai import OpenAI
from pathlib import Path

client = OpenAI()  # dùng OPENAI_API_KEY

def transcribe_via_api(audio_path: str, language: str = None) -> dict:
    """
    Transcribe qua OpenAI API — không cần GPU local.
    Model và giá đọc từ docs/pricing hiện hành; `whisper-1` là compatibility path,
    còn các model transcribe mới hơn nên cấu hình qua env.
    """
    with open(audio_path, "rb") as audio_file:
        params = {
            "model": os.environ.get("OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
            "file": audio_file,
            "response_format": "verbose_json",  # bao gồm timestamps
        }
        if language:
            params["language"] = language

        transcript = client.audio.transcriptions.create(**params)

    return {
        "text": transcript.text,
        "language": transcript.language,
        "duration": transcript.duration,
        "segments": transcript.segments
    }

# Kết hợp Whisper + LLM: transcribe meeting rồi tóm tắt
def meeting_summarizer(audio_path: str) -> dict:
    """Pipeline: audio → transcript → summary"""
    # Bước 1: Transcribe
    print("Transcribing audio...")
    transcript = transcribe_via_api(audio_path)

    # Bước 2: Tóm tắt với Claude
    import anthropic
    claude = anthropic.Anthropic()

    print("Summarizing transcript...")
    summary = claude.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Dưới đây là transcript của cuộc họp.
Hãy tóm tắt:
1. Các chủ đề chính được thảo luận
2. Các quyết định đã đưa ra
3. Action items (ai làm gì, deadline)

TRANSCRIPT:
{transcript['text']}"""
        }]
    ).content[0].text

    return {
        "transcript": transcript["text"],
        "language": transcript["language"],
        "summary": summary
    }
```

### 4. Function Calling / Tool Use Cross-Provider

**WHY:** Function calling cho phép LLM "gọi" functions của bạn khi cần thông tin real-time hoặc thực hiện actions. Đây là cơ sở của AI agents.

```python
# === TOOL USE VỚI CLAUDE ===
import anthropic
import json
import math
import os

client = anthropic.Anthropic()

# Định nghĩa tools — Claude sẽ quyết định khi nào cần gọi
TOOLS = [
    {
        "name": "get_weather",
        "description": "Lấy thông tin thời tiết hiện tại cho một thành phố",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Tên thành phố (tiếng Anh)"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Đơn vị nhiệt độ"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate",
        "description": "Thực hiện phép tính toán học",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Biểu thức toán học (Python syntax)"
                }
            },
            "required": ["expression"]
        }
    }
]

# Implementations của tools
def get_weather(city: str, unit: str = "celsius") -> dict:
    """Giả lập weather API — thực tế gọi OpenWeatherMap, etc."""
    # Mock data
    weather_data = {
        "hanoi": {"temp": 25, "condition": "Sunny", "humidity": 70},
        "ho chi minh": {"temp": 32, "condition": "Partly cloudy", "humidity": 80},
        "london": {"temp": 12, "condition": "Rainy", "humidity": 90},
        "new york": {"temp": 18, "condition": "Clear", "humidity": 55},
    }

    city_lower = city.lower()
    data = weather_data.get(city_lower, {"temp": 20, "condition": "Unknown", "humidity": 60})

    if unit == "fahrenheit":
        data["temp"] = data["temp"] * 9/5 + 32

    return {
        "city": city,
        "temperature": data["temp"],
        "unit": unit,
        "condition": data["condition"],
        "humidity": data["humidity"]
    }

def calculate(expression: str) -> dict:
    """Tính toán an toàn — chỉ cho phép math operations"""
    try:
        # Chỉ cho phép math operations để tránh code injection
        allowed_names = {
            k: v for k, v in math.__dict__.items()
            if not k.startswith("_")
        }
        allowed_names.update({"abs": abs, "round": round, "int": int, "float": float})

        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"result": result, "expression": expression}
    except Exception as e:
        return {"error": str(e), "expression": expression}

# Dispatch tools
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
}

def run_tool(tool_name: str, tool_input: dict) -> str:
    """Chạy tool và trả về result dưới dạng JSON string"""
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    result = TOOL_FUNCTIONS[tool_name](**tool_input)
    return json.dumps(result)

# === AGENTIC LOOP: Claude gọi tools cho đến khi có answer ===
def agent_with_tools(user_message: str) -> str:
    """
    Agentic loop:
    1. Gửi message + tools đến Claude
    2. Claude trả về tool_use block (nếu cần tool)
    3. Chạy tool, gửi result lại cho Claude
    4. Lặp cho đến khi Claude trả về text (không gọi tool nữa)
    """
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=1024,
            tools=TOOLS,
            messages=messages
        )

        # Nếu Claude trả về text → done
        if response.stop_reason == "end_turn":
            # Extract text content
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text

        # Nếu Claude muốn gọi tool
        if response.stop_reason == "tool_use":
            # Thêm Claude's response vào history
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Chạy tất cả tools Claude yêu cầu
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  → Calling tool: {block.name}({block.input})")
                    result = run_tool(block.name, block.input)
                    print(f"  ← Result: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Gửi tool results lại cho Claude
            messages.append({
                "role": "user",
                "content": tool_results
            })

# Test
print("Query: Thời tiết Hà Nội hiện tại và nhiệt độ theo Fahrenheit là bao nhiêu?")
result = agent_with_tools(
    "Thời tiết Hà Nội hiện tại là gì? Và nếu tôi muốn đổi sang Fahrenheit thì là bao nhiêu?"
)
print(f"\nAnswer: {result}")
```

```python
# === FUNCTION CALLING VỚI GEMINI ===
from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
GEMINI_MODEL = os.environ["GEMINI_MODEL"]

def get_stock_price(ticker: str) -> dict:
    """
    Lấy giá cổ phiếu cho ticker symbol.

    Args:
        ticker: Stock ticker symbol (ví dụ: AAPL, GOOGL)
    """
    # Mock data
    prices = {"AAPL": 185.5, "GOOGL": 175.2, "MSFT": 420.1, "TSLA": 240.0}
    price = prices.get(ticker.upper(), 100.0)
    return {"ticker": ticker.upper(), "price": price, "currency": "USD"}

def get_company_info(company_name: str) -> dict:
    """
    Lấy thông tin về công ty.

    Args:
        company_name: Tên công ty
    """
    info = {
        "Apple": {"ticker": "AAPL", "sector": "Technology", "employees": 164000},
        "Google": {"ticker": "GOOGL", "sector": "Technology", "employees": 182000},
    }
    data = info.get(company_name, {"ticker": "N/A", "sector": "Unknown"})
    return data

# Current GenAI SDK path: khai báo function schema, app tự execute tool.
stock_tool = types.Tool(function_declarations=[
    {
        "name": "get_stock_price",
        "description": "Lấy giá cổ phiếu hiện tại cho ticker symbol",
        "parameters": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_company_info",
        "description": "Lấy thông tin công ty theo tên",
        "parameters": {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"],
        },
    },
])

response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents="Giá cổ phiếu Apple hiện tại là bao nhiêu?",
    config=types.GenerateContentConfig(tools=[stock_tool]),
)

part = response.candidates[0].content.parts[0]
function_call = part.function_call
if function_call:
    tool_map = {
        "get_stock_price": get_stock_price,
        "get_company_info": get_company_info,
    }
    result = tool_map[function_call.name](**function_call.args)
    print(f"Gemini requested {function_call.name}: {result}")
else:
    print("Gemini:", response.text)
```

```python
# === PROVIDER ABSTRACTION LAYER ===
# Tạo interface chung để dễ swap giữa Claude và Gemini

from abc import ABC, abstractmethod
from typing import Any
import anthropic
from openai import OpenAI
import os

class AIProvider(ABC):
    """Abstract base class cho AI providers"""

    @abstractmethod
    def complete(self, messages: list[dict], system: str = None, **kwargs) -> str:
        """Gửi messages và nhận text response"""
        pass

    @abstractmethod
    def stream(self, messages: list[dict], system: str = None, **kwargs):
        """Stream response — trả về generator"""
        pass

class ClaudeProvider(AIProvider):
    def __init__(self, model: str = None):
        self.client = anthropic.Anthropic()
        self.model = model or os.environ["CLAUDE_MODEL"]

    def complete(self, messages: list[dict], system: str = None, **kwargs) -> str:
        params = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": messages,
        }
        if system:
            params["system"] = system

        response = self.client.messages.create(**params)
        return response.content[0].text

    def stream(self, messages: list[dict], system: str = None, **kwargs):
        params = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": messages,
        }
        if system:
            params["system"] = system

        with self.client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield text

class GeminiProvider(AIProvider):
    def __init__(self, model: str = None):
        from google import genai
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        self.model_name = model or os.environ["GEMINI_MODEL"]

    def complete(self, messages: list[dict], system: str = None, **kwargs) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=self._to_prompt(messages, system),
        )
        return response.text

    def stream(self, messages: list[dict], system: str = None, **kwargs):
        stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=self._to_prompt(messages, system),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    def _to_prompt(self, messages: list[dict], system: str = None) -> str:
        """Provider-neutral fallback: flatten messages. Production code can map roles to native Content objects."""
        parts = [f"System: {system}"] if system else []
        for msg in messages:
            parts.append(f"{msg['role'].title()}: {msg['content']}")
        return "\n".join(parts)

class OpenAIProvider(AIProvider):
    def __init__(self, model: str = None):
        self.client = OpenAI()
        self.model = model or os.environ["OPENAI_MODEL"]

    def complete(self, messages: list[dict], system: str = None, **kwargs) -> str:
        input_items = []
        if system:
            input_items.append({"role": "system", "content": system})
        input_items.extend(messages)

        response = self.client.responses.create(
            model=self.model,
            input=input_items,
            max_output_tokens=kwargs.get("max_tokens", 1024),
        )
        return response.output_text

    def stream(self, messages: list[dict], system: str = None, **kwargs):
        input_items = []
        if system:
            input_items.append({"role": "system", "content": system})
        input_items.extend(messages)

        stream = self.client.responses.create(
            model=self.model,
            input=input_items,
            max_output_tokens=kwargs.get("max_tokens", 1024),
            stream=True,
        )
        for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta

# Factory function
def create_provider(provider: str = "claude", **kwargs) -> AIProvider:
    providers = {
        "claude": ClaudeProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
    }
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}. Choose from: {list(providers.keys())}")
    return providers[provider](**kwargs)

# Sử dụng — dễ swap provider
def summarize_text(text: str, provider_name: str = "claude") -> str:
    provider = create_provider(provider_name)
    messages = [{"role": "user", "content": f"Tóm tắt đoạn văn sau trong 2 câu:\n{text}"}]
    return provider.complete(messages)

# Test với cùng function, khác provider
sample_text = "Python is a high-level programming language known for its clean syntax..."
# summary_claude = summarize_text(sample_text, "claude")
# summary_gemini = summarize_text(sample_text, "gemini")
```

### 5. Mock Client Strategy cho Provider Abstraction

**WHY:** Unit tests không nên gọi API thật. Mock ở boundary `AIProvider` giúp test retry, routing, formatting và fallback deterministic; integration tests thật chạy riêng khi có API key.

```python
from dataclasses import dataclass
import time

@dataclass
class FakeProvider(AIProvider):
    name: str = "fake"
    response: str = "Mocked provider response"
    delay_ms: int = 0
    should_fail: bool = False

    def complete(self, messages: list[dict], system: str = None, **kwargs) -> str:
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        if self.should_fail:
            raise RuntimeError(f"{self.name} unavailable")
        return self.response

    def stream(self, messages: list[dict], system: str = None, **kwargs):
        for token in self.complete(messages, system, **kwargs).split():
            yield token + " "

def test_provider_routing_without_api_key():
    primary = FakeProvider(name="primary", should_fail=True)
    fallback = FakeProvider(name="fallback", response="Fallback OK")

    try:
        result = primary.complete([{"role": "user", "content": "hello"}])
    except RuntimeError:
        result = fallback.complete([{"role": "user", "content": "hello"}])

    assert result == "Fallback OK"
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Hardcode API key trong code | Security breach, key leak lên git | Luôn dùng environment variables |
| Không handle rate limit errors | App crash khi API bận | Retry với exponential backoff |
| Gửi image quá lớn qua API | Tốn token, chậm, có thể bị reject | Resize image < 1MB trước khi gửi |
| Không validate tool input | Tool function crash với invalid input | Validate trong tool function, trả về error message |
| Ignore stop_reason trong Claude | Bỏ sót tool_use, infinite loop | Always check `response.stop_reason` |
| Whisper model quá lớn cho hardware | OOM, slow | Bắt đầu với "base", tăng lên nếu cần |
| Không close streaming connection | Resource leak | Dùng context manager `with client.messages.stream()` |

## ✅ Best Practices

- **Dùng environment variables** cho API keys, không bao giờ commit vào git.
- **Implement retry logic** với exponential backoff cho rate limit và timeout errors.
- **Log token usage** để tracking chi phí và phát hiện anomalies.
- **Validate tool inputs** trước khi gọi external services.
- **Test với mock providers** trong unit tests để tránh gọi API thật.
- **Set reasonable max_tokens** để tránh bị overcharge.
- **Dùng model tier phù hợp:** Flash/Haiku cho simple tasks, Pro/Sonnet cho complex reasoning.

## ⚖️ Trade-offs

**Claude vs Gemini vs OpenAI:**

| | Claude Sonnet tier | Gemini Flash/Pro tier | OpenAI GPT tier |
|--|------------------|----------------|--------|
| Context window | Lớn, phụ thuộc model | Rất mạnh cho long-context/multimodal | Phụ thuộc model, Responses API hỗ trợ multimodal/tools |
| Strength | Reasoning, code | Long docs, multimodal | General purpose, tool ecosystem |
| Price | Theo tier/model | Theo tier/model | Theo tier/model |
| Vietnamese | Tốt | Tốt | Tốt |
| Function calling | Mature | Good | Mature |

**Local Whisper vs API Whisper:**
| | Local | API |
|--|-------|-----|
| Chi phí | Không trả API, vẫn tốn điện/hardware | Theo pricing hiện hành của provider |
| Privacy | 100% private | Data gửi lên OpenAI |
| Speed | Phụ thuộc GPU | Nhanh và stable |
| Setup | Phức tạp (ffmpeg, model) | 5 phút |

## 🚀 Performance Notes

- **Parallel API calls:** Dùng `asyncio` + async SDK/httpx khi bài toán I/O-bound; throughput tăng tùy rate limit, connection pooling và provider quota.
- **Prompt caching (Claude):** Anthropic có prompt caching cho system prompts và long documents; mức tiết kiệm phụ thuộc model, cache hit và provider policy.
- **Batch processing (Gemini):** Gemini hỗ trợ batch API cho offline processing với giá rẻ hơn.
- **Image preprocessing:** Resize/compress theo ngưỡng chất lượng và giới hạn provider; đừng dùng một kích thước cố định cho mọi use case vì OCR, chart và UI screenshot cần độ phân giải khác nhau.
- **Response format control:** Dùng structured outputs/JSON schema theo từng provider thay vì chỉ prompt "return JSON"; validate bằng Pydantic trước khi dùng.

## 📝 Tóm tắt

- Claude SDK mạnh về reasoning và code, sử dụng messages array với system prompt riêng biệt
- Gemini có các model long-context/multimodal; giới hạn cụ thể thay đổi theo model nên phải đọc model docs trước khi thiết kế ingestion
- Whisper chạy được local (miễn phí) hoặc qua API — transcribe audio với accuracy cao
- Function calling / tool use cho phép LLM tương tác với external APIs, databases, functions của bạn
- Agentic loop: gửi tools → LLM quyết định gọi tool → chạy tool → trả kết quả → LLM tiếp tục
- Provider abstraction layer giúp swap giữa Claude/Gemini/GPT mà không đổi application code
- Luôn handle rate limits, set max_tokens, log usage để control cost
