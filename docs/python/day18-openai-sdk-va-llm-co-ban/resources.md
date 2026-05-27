# Tài Liệu Tham Khảo — Ngày 18: OpenAI SDK & LLM Basics

## 📚 Official Docs

- **OpenAI API Reference** — https://platform.openai.com/docs/api-reference — Reference đầy đủ tất cả endpoints
- **OpenAI Python SDK (GitHub)** — https://github.com/openai/openai-python — Source code, examples, changelog
- **Responses API Reference** — https://platform.openai.com/docs/api-reference/responses/create — Interface chính để tạo model responses
- **Text Generation Guide** — https://platform.openai.com/docs/guides/text?api-mode=responses — Ví dụ text generation bằng Responses API
- **Migrate to Responses** — https://platform.openai.com/docs/guides/migrate-to-responses — So sánh Responses với Chat Completions và migration notes
- **Streaming Responses** — https://platform.openai.com/docs/guides/streaming-responses — SSE event types như `response.output_text.delta`
- **Structured Outputs Guide** — https://platform.openai.com/docs/guides/structured-outputs — Pydantic integration, JSON schema
- **Token Usage & Pricing** — https://platform.openai.com/docs/pricing — Luôn kiểm tra giá mới nhất, thay đổi thường xuyên
- **Rate Limits** — https://platform.openai.com/docs/guides/rate-limits — Tier limits, headers, best practices
- **Batch API** — https://platform.openai.com/docs/guides/batch — Offline processing; pricing/discount phụ thuộc model và endpoint
- **Tiktoken (GitHub)** — https://github.com/openai/tiktoken — OpenAI's tokenizer, đếm tokens trước khi gửi

## 🎥 Video / Courses

- **OpenAI API for Beginners (FreeCodeCamp)** — https://www.youtube.com/watch?v=uRQH2CFvedY — 4 giờ, đầy đủ từ basic đến advanced
- **LangChain + OpenAI Tutorial** — https://www.youtube.com/watch?v=lG7Uxts9SXs — Giới thiệu ecosystem rộng hơn
- **Prompt Engineering Course (DeepLearning.AI)** — https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/ — Free, do Andrew Ng và OpenAI hợp tác, rất chuẩn
- **Building LLM Applications (Andrej Karpathy intro)** — https://www.youtube.com/watch?v=zjkBMFhNj_g — "Let's build GPT" — hiểu internals

## 📝 Articles / Blog Posts

- **"How GPT Tokenization Works"** — https://platform.openai.com/tokenizer — Interactive tokenizer tool — thử paste text, xem từng token
- **"OpenAI Cookbook"** — https://cookbook.openai.com — Official recipes cho common use cases: RAG, function calling, batch processing
- **"Structured Outputs with Pydantic"** — https://platform.openai.com/docs/guides/structured-outputs/supported-schemas — Supported schemas, limitations
- **"LLM Cost Calculator"** — https://openai.com/pricing — Dùng để estimate cost trước khi build
- **"Rate Limit Best Practices"** — https://platform.openai.com/docs/guides/rate-limits/usage-tiers — Tier progression, how to request increases
- **"Tenacity Documentation"** — https://tenacity.readthedocs.io — Python retry library, đọc phần "Before attempting a retry" và "After attempting a retry"

## 🔧 Tools / Libraries

- **openai** — `uv add openai` — Official Python SDK
- **tiktoken** — `uv add tiktoken` — Token counting, essential cho cost estimation
- **tenacity** — `uv add tenacity` — Retry logic với exponential backoff, decorator-based
- **python-dotenv** — `uv add python-dotenv` — Load `.env` file, quản lý API keys
- **httpx** — `uv add httpx` — Async HTTP client, dùng bởi OpenAI SDK internally
- **aiolimiter** — `uv add aiolimiter` — Rate limiting cho async code, production-ready
- **pydantic** — `uv add pydantic` — Data validation, structured output (đã có sẵn với openai package)
- **litellm** — `uv add litellm` — Unified interface cho 100+ LLM providers (OpenAI, Anthropic, Cohere...) — nếu muốn provider-agnostic

## 💡 Ghi chú thêm

**OpenAI SDK: Python vs NodeJS — Những điểm giống nhau:**

API design rất giống nhau vì được thiết kế cùng team:
```
# NodeJS
const response = await openai.responses.create({...})
response.output_text

# Python
response = client.responses.create(...)
response.output_text
```

Streaming cũng giống:
```
# NodeJS
for await (const event of stream) {
  if (event.type === "response.output_text.delta") event.delta
}

# Python
async for event in stream:
    if event.type == "response.output_text.delta":
        event.delta
```

**Chat Completions compatibility:** Nếu codebase cũ dùng `client.chat.completions.create(...)`, chưa cần panic: endpoint vẫn supported. Với bài học và project mới, ưu tiên `client.responses.create(...)` / `client.responses.parse(...)`.

**Tránh những sai lầm phổ biến:**

1. **API key trong code:** Không bao giờ hardcode API key. Luôn dùng `.env` file và đưa vào `.gitignore`.

2. **Không set timeout:** OpenAI requests có thể timeout sau 60-120s. Set `timeout=30` trong client config:
   ```python
   client = OpenAI(timeout=30.0)
   ```

3. **Nhầm `openai.OpenAI` với `openai.AsyncOpenAI`:** Dùng sync client trong async function sẽ block event loop. Luôn dùng `AsyncOpenAI` trong FastAPI và asyncio contexts.

4. **Model name typos:** model IDs thay đổi theo thời gian. Luôn verify với:
   ```python
   models = client.models.list()
   print([m.id for m in models.data])
   ```

**Environment setup khuyến nghị:**
```bash
# .env file
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...  # Optional, nếu thuộc organization
OPENAI_DEFAULT_MODEL=gpt-5  # Ví dụ theo docs; kiểm tra model catalog khi học/deploy

# .gitignore — PHẢI CÓ
.env
*.env
.env.*
```

**Cost monitoring — thiết lập ngay từ đầu:**
1. Vào https://platform.openai.com/usage → set Usage Limits → Hard limit = $20/month
2. Enable Usage alerts tại 50% và 80% budget
3. Với production: dùng cost tracking middleware từ bài 18 hoặc LangSmith/Langfuse

**Useful API features chưa cover trong bài:**
- **Function Calling / Tools**: Để LLM gọi functions của bạn — powerful cho agentic workflows
- **Vision**: Gửi ảnh kèm text với model multimodal hiện hành
- **Embeddings**: `client.embeddings.create()` — vectorize text cho semantic search, RAG
- **Assistants API**: Legacy/migration topic; OpenAI đang chuyển agentic workflows sang Responses API
- **Fine-tuning**: Customize model với data của bạn — advanced use case
