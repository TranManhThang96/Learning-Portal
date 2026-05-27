# Tài Liệu Tham Khảo — Ngày 33

## 📚 Official Docs

- **FastAPI** — https://fastapi.tiangolo.com — Docs chính thức, rất đầy đủ và có ví dụ thực tế
- **SQLAlchemy 2.0 Async** — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html — Async ORM patterns
- **OpenAI Responses API** — https://developers.openai.com/api/docs/guides/migrate-to-responses — Default path cho direct OpenAI SDK code mới
- **LangChain Python** — https://docs.langchain.com/oss/python/langchain/overview — Agents, models, tools, streaming
- **Qdrant Python Client** — https://qdrant.tech/documentation/quick-start/ — Vector store operations
- **Pydantic Settings** — https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — Config management
- **Alembic** — https://alembic.sqlalchemy.org/en/latest/ — Database migrations

## 🎥 Video / Courses

- **Build a Production RAG App** — freeCodeCamp YouTube — End-to-end tutorial
- **FastAPI Full Course** — Amigoscode YouTube — Covers auth, DB, testing
- **LangChain Crash Course** — Greg Kamradt YouTube — Practical LangChain patterns

## 📝 Articles / Blog Posts

- **RAG from Scratch** — LangChain Blog — https://blog.langchain.dev/rag-from-scratch/ — Hiểu sâu từng bước
- **FastAPI Best Practices** — GitHub awesome-fastapi — Production patterns
- **Async SQLAlchemy Patterns** — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-orm — Official guide

## 🔧 Tools / Libraries

- **qdrant-client** — `uv add qdrant-client` — Python client cho Qdrant
- **langchain-openai** — `uv add langchain-openai` — OpenAI integration
- **langchain-qdrant** — `uv add langchain-qdrant` — Qdrant vector store integration hiện hành
- **langchain-text-splitters** — `uv add langchain-text-splitters` — Text splitters tách package
- **python-jose** — `uv add python-jose[cryptography]` — JWT handling
- **passlib** — `uv add passlib[bcrypt]` — Password hashing
- **redis-py** — `uv add redis` — Async Redis client (redis.asyncio)
- **pypdf** — `uv add pypdf` — PDF text extraction
- **python-multipart** — `uv add python-multipart` — File upload support
- **structlog** — `uv add structlog` — Structured logging

## 💡 Ghi chú thêm

**Qdrant vs pgvector Trade-off:**
- Dùng Qdrant khi: > 1M vectors, cần filtering phức tạp, scale độc lập
- Dùng pgvector khi: đã có PostgreSQL, < 1M vectors, đơn giản hóa infrastructure

**LangChain LCEL (LangChain Expression Language):**
LCEL là paradigm mới để compose chains. Thay vì `LLMChain(...)` cũ, dùng `prompt | llm | parser`. Đây là cách modern và được recommend cho mọi code mới.

**Streaming trong production:**
- Nginx: thêm `proxy_buffering off;` trong config
- AWS ALB: mặc định buffer 60s, cần request timeout cao hơn
- Cloudflare: streaming được support với Enterprise plan
