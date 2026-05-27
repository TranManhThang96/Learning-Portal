# Python Course Version Matrix

File này ghi mốc version để giảm rủi ro lệch API khi học hoặc sửa curriculum. Nếu project thực tế dùng version khác, hãy kiểm tra docs hiện hành trước khi copy code.

| Stack | Target | Notes |
|---|---|---|
| Python | 3.12.x | Course dùng cú pháp `X | None`, `asyncio.TaskGroup` optional và typing hiện đại. Nếu dùng Python 3.13 free-threaded, các phần GIL cần caveat riêng. |
| uv | current stable | Dùng cho package/project workflow. Pin lockfile khi chuyển sang project thật. |
| Ruff | current stable | Dùng lint/format; rule names có thể thay đổi nhẹ theo version. |
| mypy | current stable | `strict = true` phù hợp production nhưng có thể cần overrides cho thư viện thiếu stubs. |
| FastAPI | 0.128.x target / pin project minor | Pydantic v2 native, lifespan được ưu tiên hơn startup/shutdown events cũ. |
| Pydantic | 2.x | Dùng `field_validator`, `model_validator`, `computed_field`, `model_config`. |
| SQLAlchemy | 2.0.x | Dùng `create_async_engine`, `async_sessionmaker`, `Mapped`, `mapped_column`. Với `joinedload()` collection cần `Result.unique()`. |
| Alembic | 1.14+ | Async migrations cần template/cookbook riêng; production không nên dựa vào `Base.metadata.create_all()`. |
| Redis Python | redis-py 5.x/6.x | Async API nằm trong `redis.asyncio`; tránh package `aioredis` cũ. |
| OpenAI Python SDK | current pinned minor | Dạy Responses API-first cho streaming, tools và structured outputs; Chat Completions là compatibility path. Snapshot docs kiểm tra ngày 2026-05-25. |
| LangChain | 1.x target / pin project minor | Dùng v1 `create_agent`, `langchain.tools.tool`, LCEL primitives từ `langchain_core`, và provider package `langchain_openai`. Packages retrieval/vector DB vẫn tách riêng theo integration. |
| LangGraph | 1.x target / pin project minor | `interrupt()`/`Command(resume=...)` cần checkpointer. Production checkpointer nên quản lý lifecycle trong app lifespan/context manager và invoke với `configurable.thread_id`. |
| LlamaIndex | pinned minor | Global `Settings` và index APIs thay đổi nhanh; examples cần smoke test theo version target. |
| Qdrant Client | 1.12+ | Collection vector size phải khớp embedding model. Không đổi embedding model mà reuse collection cũ nếu dimension khác. |
| Chroma | pinned minor | Phù hợp dev/prototype; production cần đánh giá persistence, concurrency và deployment model. |
| HuggingFace Transformers | pinned minor | Model download lớn; luôn ghi rõ CPU/GPU/RAM fallback trong exercises. |

## Update Rule

Khi sửa bài học có framework/API:

1. Dùng Context7 hoặc official docs để xác minh syntax.
2. Ghi target version nếu API hay thay đổi.
3. Thêm smoke command hoặc import check nếu bài có code runnable.
4. Không dùng wording tuyệt đối như "luôn tốt nhất" nếu phụ thuộc workload, dataset, model hoặc infrastructure.
