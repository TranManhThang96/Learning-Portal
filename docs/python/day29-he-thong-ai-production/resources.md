# Tài Liệu Tham Khảo — Ngày 29

## 📚 Official Docs

- **Langfuse Docs** — https://langfuse.com/docs — Observability platform, free tier, self-hostable
- **Langfuse Python SDK** — https://langfuse.com/docs/sdk/python — Python SDK reference
- **LangSmith Docs** — https://docs.smith.langchain.com — LangChain's observability platform
- **Phoenix (Arize)** — https://docs.arize.com/phoenix — Open-source LLM observability, local first
- **Tenacity Docs** — https://tenacity.readthedocs.io — Retry library, cực kỳ flexible
- **Guardrails AI Docs** — https://www.guardrailsai.com/docs — Framework cho output validation
- **NeMo Guardrails** — https://github.com/NVIDIA/NeMo-Guardrails — NVIDIA's guardrails cho LLM
- **OpenAI Data Controls** — https://platform.openai.com/docs/guides/your-data — Chính sách xử lý dữ liệu/API retention cần đọc trước khi log prompt/output
- **Anthropic Privacy & Data Usage** — https://support.anthropic.com/en/articles/7996866-how-is-my-data-used — Tham khảo retention/training policy khi chọn provider

## 🎥 Video / Courses

- **LLM Ops Course (DeepLearning.AI)** — https://www.deeplearning.ai/short-courses/llmops/ — Production LLM systems
- **Building Production AI (Anthropic)** — https://www.youtube.com/watch?v=T9aRN5JkmL8 — Anthropic eng talk
- **Langfuse Demo** — https://www.youtube.com/watch?v=Y3MvFBJkSHM — 15 phút hands-on
- **LLM Cost Optimization** — https://www.youtube.com/watch?v=FBiIpNL5t4E — Tips thực tế

## 📝 Articles / Blog Posts

- **Production LLM Systems Checklist** — https://eugeneyan.com/writing/llm-patterns — Danh sách comprehensive
- **Semantic Caching for LLMs** — https://redis.io/blog/what-is-semantic-caching — Redis blog, concept và implementation
- **Circuit Breaker Pattern** — https://martinfowler.com/bliki/CircuitBreaker.html — Martin Fowler's canonical explanation
- **LLM Cost Control** — https://www.pinecone.io/learn/series/langchain/langchain-costs/ — Practical tips
- **Guardrails for LLMs** — https://www.anthropic.com/research/many-shot-jailbreaking — Anthropic research

## 🔧 Tools / Libraries

- **langfuse** — `uv add langfuse` — Observability với tracing, evals
- **langsmith** — `uv add langsmith` — LangChain observability
- **arize-phoenix** — `uv add arize-phoenix` — Local-first observability
- **tenacity** — `uv add tenacity` — Retry với rich configuration
- **guardrails-ai** — `uv add guardrails-ai` — Output validation framework
- **limits** — `uv add limits` — Rate limiting strategies
- **redis** — `uv add redis` — Semantic caching với Redis backend
- **backoff** — `uv add backoff` — Alternative retry library
- **circuit-breaker** — `uv add circuitbreaker` — Simple circuit breaker decorator

## 💡 Ghi chú thêm

**Langfuse quick setup:**
```bash
# Option 1: Cloud (langfuse.com — kiểm tra plan/quota hiện hành)
uv add langfuse
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."

# Option 2: Self-hosted với Docker
docker compose up -d  # từ github.com/langfuse/langfuse
```

**Phoenix local setup (không cần cloud):**
```python
import phoenix as px
session = px.launch_app()  # mở UI tại localhost:6006
```

**Semantic caching với Redis:**
```python
# uv add redis sentence-transformers
import redis
import numpy as np
from sentence_transformers import SentenceTransformer

r = redis.Redis(host='localhost', port=6379, decode_responses=False)

def cache_key(embedding: np.ndarray) -> str:
    # Store vector và query với TTL
    pass

# Thực tế dùng Redis Stack (có vector search):
# docker run -p 6379:6379 redis/redis-stack-server
```

**Rate limiting strategies:**
| Strategy | Mô tả | Khi nào dùng |
|----------|--------|--------------|
| Fixed window | Reset counter mỗi phút | Simple, dễ implement |
| Sliding window | Window di chuyển liên tục | Smoother, ít burst |
| Token bucket | Bucket tích điểm theo thời gian | Cho burst traffic |
| Leaky bucket | Queue requests | Smooth output rate |

**Provider rate limits:**
- Rate limit thay đổi theo provider, workspace tier, region và model.
- Lưu `requests_per_minute`, `tokens_per_minute`, `concurrent_requests` trong config thay vì hardcode vào code.
- Test retry/circuit breaker bằng mock 429/timeout để không phụ thuộc quota thật.

**Cost optimization tips:**
1. Dùng model tier nhanh/rẻ cho classification/extraction, model mạnh hơn cho reasoning; đọc pricing hiện hành trước khi chọn
2. Prompt caching cho long system prompts/context — có thể giảm cost đáng kể nếu provider/model đủ điều kiện cache hit
3. Semantic cache cho repeated queries — giảm model calls trên cache hit, nhưng cần TTL, tenant scope và PII policy
4. Batch/offline API có thể rẻ hơn hoặc ổn định hơn cho workload không cần streaming; kiểm tra provider hiện hành
5. Compress long documents trước khi gửi (summarize → embed)
