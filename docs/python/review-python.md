# Course Review — Python 35 Days

## Executive Summary

Khóa học Python 35 ngày có định hướng rất tốt cho đối tượng Senior NodeJS Developer: nội dung dùng cầu nối NodeJS/TypeScript thường xuyên, có WHY/HOW, common mistakes, trade-offs, performance notes, và đã có đủ `lesson.md`, `resources.md`, `exercises.md` cho cả 35 ngày. Các ngày 33-34 còn có scaffold project thật, đây là điểm mạnh lớn so với một curriculum chỉ có lý thuyết.

Điểm trung bình hiện tại khoảng **7.2/10**. Vấn đề chính không phải thiếu nội dung, mà là **quá tải so với 2 giờ/ngày**, **một số bài/lab chưa runnable hoặc chưa kiểm chứng end-to-end**, và **một số API/version-sensitive đã lệch với tài liệu hiện hành**. Có 12 lesson dài hơn 1.000 dòng, exercises của Day 12/13 vượt 1.000 dòng, nên learner rất dễ biến một ngày học thành một mini-book 1-2 ngày.

Ưu tiên sửa trước:

1. Cập nhật OpenAI content từ Chat Completions-first sang Responses API-first cho Day 18/19/28/30/33.
2. Chuẩn hóa LangChain/LangGraph import và version target; tránh mix API cũ như `langchain.text_splitter`, `langchain_community.vectorstores.Qdrant`, `langchain.retrievers.*` khi đã có packages tách riêng.
3. Sửa lỗi kỹ thuật rõ ràng: Day 07 duplicate + sai claim về `except Exception`; Day 10 `sys.sleep()` typo; Day 34 Postgres checkpointer lifecycle; Day 33 migration/scaffold chưa thật sự runnable theo README.
4. Giảm scope các bài quá dài bằng cách tách Must Learn / Deep Dive / Optional Lab rõ hơn.
5. Thêm acceptance criteria runnable cho từng project/lab: lệnh setup, test, expected output, cleanup, env vars.

## Score Table

| Lesson | Title | Score | Main Issues | Priority |
|---|---|---:|---|---|
| 01 | Môi trường & Tooling | 8.0 | Tốt, có debugging; nên cập nhật uv/Poetry version target và tránh khuyến nghị "luôn dùng pyenv" quá tuyệt đối | Medium |
| 02 | Python Syntax Cơ Bản | 8.0 | Nền tảng tốt; regex thêm vào nhưng còn nhẹ về Unicode/raw string pitfalls | Medium |
| 03 | Data Structures | 8.2 | Gọn và phù hợp; nên thêm mutability/copy pitfalls sâu hơn | Low |
| 04 | Functions Nâng Cao | 7.2 | Rất dài cho decorators/generators; exercises nhiều TODO, dễ quá tải | Medium |
| 05 | OOP trong Python | 7.3 | Bao phủ rộng; inheritance/MRO/Protocol có thể quá nặng với người mới Python | Medium |
| 06 | Modules, Packages & Project Structure | 7.0 | 1.037 dòng; trộn packaging, logging, design patterns, DI, config trong một ngày | High |
| 07 | Error Handling & Typing | 5.8 | Bị duplicate gần như hai bài trong một file; có claim sai về `except Exception` bắt `SystemExit/KeyboardInterrupt` | High |
| 08 | File I/O, Context Managers & Serialization | 7.2 | Pydantic v2 deep dive tốt nhưng quá nặng; cần tách Pydantic Settings/validators sang reference | Medium |
| 09 | Async Python | 8.0 | Đúng trọng tâm; nên thêm `TaskGroup` sớm hơn và cancellation semantics | Medium |
| 10 | Concurrency & Parallelism | 7.5 | Tốt nhưng có typo `sys.sleep()`; multiprocessing guidance cần caveat Linux/macOS/Windows rõ hơn | Medium |
| 11 | Testing với pytest | 7.0 | Nội dung mạnh nhưng quá dài; async fixture guidance cần pin pytest-asyncio behavior/version | Medium |
| 12 | Database với Python | 6.8 | 1.243 dòng + 1.097 dòng exercises; SQLAlchemy async tốt nhưng lab quá lớn, migration/runnability cần chia nhỏ | High |
| 13 | FastAPI Cơ Bản | 6.8 | Lesson/exercises quá lớn; exercises nâng cao đã bao gồm auth/JWT/DB khiến trùng Day 14/15 | High |
| 14 | FastAPI Nâng Cao | 7.2 | Nội dung tốt; BackgroundTasks cần caveat không dùng cho job nặng/retry; security section cần argon2/Passlib maintenance caveat | Medium |
| 15 | FastAPI + Database + Caching | 7.0 | Có N+1/cache/grPC tốt; exercises lớn và overlap với Day 12/13/16 | Medium |
| 16 | Deployment & Production Readiness | 7.0 | Quan trọng nhưng 1.242 dòng; Docker/Gunicorn/Celery/CI/CD quá nhiều cho 2 giờ | High |
| 17 | Numpy & Pandas | 7.8 | Tốt, có scope giảm; nên thêm env/setup nhẹ cho heavy packages và data-size caveats | Low |
| 18 | OpenAI SDK & LLM Basics | 6.2 | Dựa Chat Completions-first; pricing/model/context info hardcoded dễ stale; cần Responses API-first | High |
| 19 | Prompt Engineering | 6.5 | Rất dài, nhiều model/cost claims stale; cần chuyển examples sang Responses API hoặc ghi rõ legacy | High |
| 20 | LangChain — Chains, Tools & Agents | 7.0 | Gọn hơn các bài AI khác; cần pin LangChain version và cập nhật agent API theo LangGraph/LangChain hiện hành | High |
| 21 | RAG | 7.0 | Nội dung rất đầy đủ nhưng 1.245 dòng; import mix cũ/mới; vector DB comparison hơi tuyệt đối | High |
| 22 | RAG Nâng Cao | 6.8 | Nhiều kỹ thuật tốt nhưng nhiều claim "production default/always better" cần caveat; API imports cần kiểm chứng | High |
| 23 | LlamaIndex | 6.8 | Hữu ích nhưng LlamaIndex API đổi nhanh; `KnowledgeGraphIndex`/global `Settings` cần version pin/caveat | High |
| 24 | LangGraph & Agentic Workflows | 7.0 | Có interrupt/checkpointer đúng hướng; claim auto parallel và API persistence cần nuance/version pin | High |
| 25 | Multi-Agent Systems | 6.8 | Quá rộng, 1.171 dòng; multi-agent cost/rate-limit caveats tốt nhưng lab khó runnable trong 2 giờ | High |
| 26 | HuggingFace & Local Models | 7.3 | Tốt; cần caveat GPU/RAM/download size rõ hơn và fallback CPU realistic hơn | Medium |
| 27 | Fine-tuning & Model Customization | 7.5 | Đã demo-oriented hợp lý; cần làm rõ exercise nào không kỳ vọng chạy full training | Medium |
| 28 | AI APIs & Integrations | 7.0 | Nên cập nhật OpenAI/Anthropic provider surface và tool-calling API hiện hành | Medium |
| 29 | Production AI Systems | 7.2 | Có safety/guardrails; cần bớt overclaim deterministic/caching và thêm privacy/compliance caveat | Medium |
| 30 | AI System Design | 7.0 | Tốt cho tổng hợp; vẫn cần runnable scaffold và rõ dependency/API key strategy | Medium |
| 31 | Ôn tập Python Core + FastAPI | 8.0 | Review tốt; nên liên kết checklist với lỗi thực tế từ Day 33 project | Low |
| 32 | Ôn tập AI/LLM Stack | 7.2 | Hữu ích; import LangChain cũ cần cập nhật; local-vs-cloud matrix cần caveat | Medium |
| 33 | Project — AI Backend Service | 6.2 | Scaffold có giá trị nhưng migration không có versions; pipeline init mỗi upload; Qdrant/LangChain API cũ; env placeholder unsafe | High |
| 34 | Project — Agentic System | 5.8 | Checkpointer lifecycle có khả năng sai; no real interrupt usage in project; creates checkpointer/graph per request | High |
| 35 | Review Tổng Thể & Roadmap | 7.5 | Tổng kết tốt; cần đồng bộ với các fixes thực tế sau khi sửa Day 33/34 | Medium |

## Cross-Lesson Issues

1. **Scope 2 giờ/ngày chưa thực tế**

   12 bài `lesson.md` vượt 1.000 dòng: Day 21, 12, 16, 19, 25, 11, 29, 13, 14, 08, 15, 06. Exercises của Day 13 và Day 12 lần lượt 1.130 và 1.097 dòng. Với format 60 phút lý thuyết + 30 phút guided + 30 phút bài tập, các bài này cần tách thành:

   - `lesson.md`: Must Learn + 1 runnable primary lab.
   - `resources.md` hoặc `document.md`: internals, matrices, optional recipes.
   - `exercises.md`: 3 bài vừa sức, có expected output và test command.

2. **Version-sensitive AI stack cần version matrix**

   LangChain, LangGraph, LlamaIndex, OpenAI SDK, Qdrant integrations đổi nhanh. Course hiện để ranges rộng (`langgraph>=0.2.0`, `langchain>=0.3.0`) nhưng code lại dùng APIs có thể thuộc các thế hệ khác nhau. Nên thêm `python/version-matrix.md` hoặc section đầu README:

   | Tool | Target Version | Notes |
   |---|---|---|
   | Python | 3.12.x | Nếu dùng Python 3.13 free-threaded thì GIL discussion cần caveat |
   | FastAPI | 0.12x | Pydantic v2 native |
   | SQLAlchemy | 2.0.x | AsyncSession, `async_sessionmaker` |
   | OpenAI SDK | current pinned minor | Responses API-first |
   | LangChain | pinned minor | LCEL/import paths |
   | LangGraph | pinned minor/1.x | checkpointer + interrupt syntax |
   | LlamaIndex | pinned minor | Settings/index APIs |

3. **OpenAI API content đã lệch hướng hiện hành**

   Day 18/19 dùng `client.chat.completions.create()` và `client.beta.chat.completions.parse()` làm luồng chính. Tài liệu OpenAI hiện mô tả Responses API là interface chính cho response generation, streaming semantic events, tools, structured outputs, và migration từ Chat Completions. Chat Completions vẫn tồn tại, nhưng course nên dạy:

   - Responses API là default path mới.
   - Chat Completions là legacy/compatibility path.
   - Structured outputs chuyển sang `client.responses.parse()` hoặc `client.responses.stream(..., text_format=Model)` tùy SDK version.
   - Streaming nên dùng event types như `response.output_text.delta`, không chỉ chunk delta kiểu Chat Completions.

4. **Lab runnable chưa đủ mạnh**

   Nhiều bài có code snippets tốt nhưng thiếu một trong các phần: `pyproject.toml`, pinned deps, `.env.example`, `pytest`, expected output, cleanup, Docker healthcheck, migration files. Day 33/34 có scaffold nhưng chưa có test suite và có rủi ro runtime lớn.

5. **Imports cũ/mới bị trộn trong LangChain ecosystem**

   Có chỗ dùng package tách riêng hiện đại (`langchain_chroma`, `langchain_qdrant`) nhưng cũng có chỗ dùng imports cũ như `langchain.text_splitter`, `langchain_community.vectorstores.Qdrant`, `langchain.retrievers.*`. Cần chuẩn hóa theo version target và thêm smoke test import cho Day 20-24, 32-34.

6. **Một số wording quá tuyệt đối**

   Các câu như "hybrid search luôn tốt hơn", "Qdrant production-ready", "temperature=0 deterministic", "threading OK cho numpy", "LangGraph tự động parallel independent nodes" cần caveat. Với senior learner, wording nên là điều kiện hóa: phụ thuộc workload, model, library backend, dataset, infra, version.

7. **Project days cần artifact rõ hơn**

   Day 33/34 theo update prompt yêu cầu scaffold 70% hoàn thiện. Scaffold có nhưng chưa có:

   - `.env.example` trong file listing thực tế.
   - Alembic revision file.
   - Tests/smoke scripts.
   - Seed/test data.
   - Clear "what learner implements" markers trong code files, không chỉ README.

8. **Không có README Python entry point**

   Thư mục `python/` có prompts nhưng chưa có README khóa học dạng entry point: bảng 35 ngày, prerequisites, target versions, expected daily workflow, trạng thái runnable/reviewed của từng ngày.

## Detailed Review

### Lesson 01 — Môi trường & Tooling

Score: **8.0/10**. Priority: **Medium**.

Điểm mạnh: đúng nhu cầu NodeJS developer, giải thích uv/Poetry/venv/pre-commit/debugging rõ. Debugging section bổ sung tốt.

Fix đề xuất:
- Thêm target versions cho Python/uv/ruff/mypy.
- Cập nhật best practice từ "luôn dùng pyenv" thành "pin Python version; dùng pyenv/asdf/uv python tùy team".
- Thêm `.python-version`, `pyproject.toml`, `uv.lock` expected state cho exercise.

### Lesson 02 — Python Syntax Cơ Bản

Score: **8.0/10**. Priority: **Medium**.

Nội dung syntax, type hints, f-string, match/case, comprehensions ổn. Regex được thêm vào đúng chỗ.

Fix đề xuất:
- Thêm raw string pitfalls (`r"\d+"`), Unicode normalization, greedy vs non-greedy regex.
- Nhấn mạnh mutable default args bằng một runnable failing example.

### Lesson 03 — Data Structures

Score: **8.2/10**. Priority: **Low**.

Bài gọn, line count hợp lý, có complexity và so sánh JS tốt.

Fix đề xuất:
- Thêm shallow vs deep copy cho list/dict nested.
- Thêm `Counter`, `defaultdict` ở mức preview nếu chưa đủ.

### Lesson 04 — Functions Nâng Cao

Score: **7.2/10**. Priority: **Medium**.

Decorators, closures, generators, `functools` đều quan trọng nhưng lesson/exercises dài. Bài tập retry decorator + generator pipeline hay nhưng có thể quá nặng với ngày 4.

Fix đề xuất:
- Giữ decorators + generator basics trong lesson.
- Đưa retry/backoff production decorator sang exercises hoặc Day 31 review.
- Thêm test command cho từng exercise.

### Lesson 05 — OOP trong Python

Score: **7.3/10**. Priority: **Medium**.

Bao phủ nhiều: class, dunder, MRO, ABC, Protocol. So sánh TypeScript hữu ích.

Fix đề xuất:
- Tách MRO/multiple inheritance thành optional deep dive.
- Làm rõ dataclass vs class thường nên xuất hiện trước một số dunder use case.
- Cẩn thận với runtime Protocol: `@runtime_checkable` chỉ kiểm tra shape hạn chế, không đảm bảo type signatures đầy đủ.

### Lesson 06 — Modules, Packages & Project Structure

Score: **7.0/10**. Priority: **High**.

Bài rất có giá trị nhưng ôm quá nhiều: import system, project layout, `pyproject.toml`, logging, config, design patterns, DI. 1.037 dòng là quá nhiều cho 2 giờ.

Fix đề xuất:
- Chuyển design patterns vào `resources.md`/reference hoặc Day 31.
- Giữ primary lab là một package nhỏ có `pyproject.toml`, `src/`, tests, ruff/mypy.
- Thêm smoke commands: `uv run pytest`, `uv run ruff check`, `uv run mypy`.

### Lesson 07 — Error Handling & Typing

Score: **5.8/10**. Priority: **High**.

Đây là bài cần sửa trước. File có dấu hiệu bị ghép duplicate: sau phần tóm tắt đầu tiên lại bắt đầu lại "So sánh với NodeJS/TypeScript" và "Lý thuyết". Ngoài ra có lỗi kỹ thuật: bảng Common Mistakes nói `except Exception` bắt cả `SystemExit`, `KeyboardInterrupt`; thực tế `except Exception` không bắt hai exception này vì chúng kế thừa `BaseException`, không phải `Exception`. Lỗi đúng là bare `except:` hoặc `except BaseException:`.

Fix đề xuất:
- Xóa phần duplicate, giữ một version nhất quán.
- Sửa claim `except Exception`.
- Thêm `ExceptionGroup`/`except*` như optional note cho Python 3.11+ nếu có `TaskGroup`.
- Giảm exercises từ 900 dòng xuống 3 bài rõ ràng.

### Lesson 08 — File I/O, Context Managers & Serialization

Score: **7.2/10**. Priority: **Medium**.

Pydantic v2 coverage tốt, có settings/validators/computed fields. Nhưng bài đang chuyển từ File I/O sang Pydantic deep dive quá sâu.

Fix đề xuất:
- Giữ File I/O/context manager/serialization là main path.
- Đưa Pydantic advanced vào reference hoặc chia thành "Pydantic v2 Cheat Sheet".
- Thêm security note về YAML, path traversal khi đọc file upload.

### Lesson 09 — Async Python

Score: **8.0/10**. Priority: **Medium**.

Bài này đúng trọng tâm và line count hợp lý. So sánh Node event loop tốt.

Fix đề xuất:
- Thêm `asyncio.TaskGroup` sau `gather` để chuẩn bị cho structured concurrency.
- Thêm cancellation propagation và cleanup pattern.
- Làm rõ `create_task` fire-and-forget trong app server cần lifecycle management.

### Lesson 10 — Concurrency & Parallelism

Score: **7.5/10**. Priority: **Medium**.

GIL/thread/process decision matrix hữu ích. Có lỗi nhỏ nhưng rõ: comment liệt kê `sys.sleep()` thay vì `time.sleep()`. Một số khuyến nghị ProcessPool cần caveat về startup method, pickling, Windows/macOS guard.

Fix đề xuất:
- Sửa `sys.sleep()` thành `time.sleep()`.
- Thêm `if __name__ == "__main__"` vào mọi example ProcessPool runnable.
- Nói rõ NumPy/PyTorch release GIL tùy operation/backend, không phải mọi operation.

### Lesson 11 — Testing với pytest

Score: **7.0/10**. Priority: **Medium**.

Nội dung mạnh: fixtures, parametrize, mocking, async tests, FastAPI tests, coverage. Nhưng 1.132 dòng cho một ngày là quá tải.

Fix đề xuất:
- Tách pytest basics + fixtures + parametrize là Must Learn.
- Đưa FastAPI TestClient/httpx và coverage config sang exercises/reference.
- Pin pytest-asyncio config behavior vì `asyncio_mode` và async fixtures thay đổi theo version.

### Lesson 12 — Database với Python

Score: **6.8/10**. Priority: **High**.

SQLAlchemy 2.0 async content đúng hướng: `create_async_engine`, `async_sessionmaker`, `expire_on_commit=False`, `selectinload` discussion. Nhưng lesson + exercises rất lớn. Với `joinedload` collection, cần nhắc rõ SQLAlchemy 2.0 yêu cầu `Result.unique()` trước khi materialize results.

Fix đề xuất:
- Thêm explicit `result.unique()` caveat khi dùng `joinedload()` với collections.
- Chia Redis caching/distributed lock/rate limit sang separate optional lab.
- Tách Alembic async migration runnable demo riêng, có revision file thật.

### Lesson 13 — FastAPI Cơ Bản

Score: **6.8/10**. Priority: **High**.

FastAPI basics tốt nhưng exercises đã phình sang auth, JWT, Alembic, nested resources. Điều này làm overlap Day 14/15 và vượt quá beginner-FastAPI day.

Fix đề xuất:
- Day 13 chỉ nên là routing, validation, dependency basics, response model, error handling cơ bản.
- Chuyển auth/JWT/blog DB exercise sang Day 14/15.
- Thêm official pattern `Annotated[..., Depends(...)]` nhất quán.

### Lesson 14 — FastAPI Nâng Cao

Score: **7.2/10**. Priority: **Medium**.

Middleware, CORS, JWT/OAuth2, WebSocket, BackgroundTasks, security đều cần thiết. Tài liệu FastAPI hiện xác nhận BackgroundTasks integrate với DI và chạy sau response, nhưng course cần nói rõ nó không thay thế queue cho job nặng/retry/durable tasks.

Fix đề xuất:
- BackgroundTasks: chỉ cho task nhỏ cùng process; dùng Celery/ARQ/Taskiq cho durable jobs.
- WebSocket auth nên có disconnect/close-code example.
- Security section nên thêm password hashing recommendation hiện đại hơn bcrypt-only và dependency scanning caveat.

### Lesson 15 — FastAPI + Database + Caching

Score: **7.0/10**. Priority: **Medium**.

N+1, pooling, Redis cache-aside, pagination, gRPC quick reference đều tốt. Bài tập vẫn lớn và overlap với Day 12/13/16.

Fix đề xuất:
- Giữ one cohesive app flow: FastAPI + SQLAlchemy + Redis cache.
- Đưa gRPC quick reference vào resources hoặc appendix.
- Thêm integration test command với test DB/Redis fake.

### Lesson 16 — Deployment & Production Readiness

Score: **7.0/10**. Priority: **High**.

Đây là bài production quan trọng nhưng quá rộng: Docker, Gunicorn/Uvicorn, pydantic-settings, CI/CD, Celery/ARQ, migrations. 1.242 dòng là không hợp với 2 giờ.

Fix đề xuất:
- Tách "Deploy FastAPI container" làm primary lab.
- Đưa Celery/ARQ và CI/CD templates sang reference.
- Thêm healthcheck, graceful shutdown, migration-on-deploy policy.

### Lesson 17 — Numpy & Pandas

Score: **7.8/10**. Priority: **Low**.

Scope đã được giảm hợp lý. Có performance notes về vectorization/Parquet.

Fix đề xuất:
- Thêm setup notes về package size và optional notebook.
- Cẩn thận với "Pandas vs SQL" decision: thêm caveat data size, memory, pushdown.

### Lesson 18 — OpenAI SDK & LLM Basics

Score: **6.2/10**. Priority: **High**.

Nội dung LLM fundamentals tốt nhưng API path đã cần cập nhật. Bài đang dạy Chat Completions làm default. Tài liệu OpenAI hiện khuyến nghị Responses API cho streaming, structured outputs, tools, và các agentic workflows. Giá/context window/model names hardcoded cũng dễ stale.

Fix đề xuất:
- Viết lại examples chính bằng `client.responses.create`, `client.responses.stream`, structured outputs với Pydantic trên Responses API.
- Giữ Chat Completions trong box "legacy/compatibility".
- Xóa giá hardcoded hoặc ghi "snapshot, check pricing page".
- Cập nhật "Assistants API" notes vì official migration/sunset đã thay đổi.

### Lesson 19 — Prompt Engineering

Score: **6.5/10**. Priority: **High**.

Bài có nhiều nội dung hữu ích: few-shot, prompt injection, evaluation, model routing. Nhưng quá dài và phụ thuộc model/cost claims cũ. `temperature=0` không nên được mô tả như deterministic tuyệt đối.

Fix đề xuất:
- Tách prompt patterns và evaluation harness.
- Chuyển examples OpenAI sang Responses API.
- Biến model/cost table thành "example matrix" có ngày cập nhật.
- Thêm eval dataset nhỏ runnable không cần API bằng mock mode.

### Lesson 20 — LangChain — Chains, Tools & Agents

Score: **7.0/10**. Priority: **High**.

Bài ngắn hơn và có cảnh báo LangChain API thay đổi. LCEL direction ổn.

Fix đề xuất:
- Pin LangChain version trong bài.
- Kiểm tra `create_react_agent` path và agent invocation theo target version.
- Thêm `uv run python smoke_langchain.py` import test.

### Lesson 21 — RAG

Score: **7.0/10**. Priority: **High**.

RAG coverage rất đầy đủ: loaders, splitters, embeddings, Chroma/Qdrant/pgvector, LCEL. Nhưng 1.245 dòng và nhiều imports cần chuẩn hóa. Một số vector DB matrix có wording quá chắc chắn.

Fix đề xuất:
- Chuẩn hóa imports: `langchain_text_splitters`, `langchain_chroma`, `langchain_qdrant`, `langchain_postgres`.
- Tách vector DB comparison sang resources.
- Thêm runnable tiny RAG lab với local docs và optional OpenAI key.
- Thêm note: embedding dimension phải match model và collection.

### Lesson 22 — RAG Nâng Cao

Score: **6.8/10**. Priority: **High**.

Chunking, hybrid search, reranking, RAGAS, hallucination detection rất đáng học. Tuy nhiên nhiều "production default" claims cần caveat; API imports như retrievers/compressors cần test theo LangChain version target.

Fix đề xuất:
- Đổi "hybrid search luôn tốt hơn" thành "often better, validate with eval".
- Thêm benchmark assumptions cho latency/accuracy examples.
- Cập nhật retriever imports theo version target.

### Lesson 23 — LlamaIndex

Score: **6.8/10**. Priority: **High**.

LlamaIndex là bài hữu ích cho document-heavy RAG, nhưng API đổi nhanh. Course dùng `Settings.llm`, `KnowledgeGraphIndex`, router/sub-question engines; cần version pin và smoke test.

Fix đề xuất:
- Pin LlamaIndex target version.
- Xác minh `KnowledgeGraphIndex` status và dependency requirements.
- Thêm minimal runnable index/query example trước khi dạy nhiều index types.

### Lesson 24 — LangGraph & Agentic Workflows

Score: **7.0/10**. Priority: **High**.

StateGraph, interrupt/resume, checkpointer, streaming, subgraph là đúng trọng tâm. Tài liệu LangGraph hiện xác nhận `interrupt()` cần checkpointer và resume qua `Command(resume=...)`. Tuy nhiên cần caveat về checkpointer lifecycle và deployment.

Fix đề xuất:
- Thêm example production checkpointer bằng `async with`/app lifespan thay vì tạo mới mỗi request.
- Sửa wording "LangGraph tự động detect nodes không dependency" nếu không được target version bảo đảm rõ; diễn đạt là fan-out edges có thể chạy song song.
- Thêm max-iteration/cost budget vào code chính, không chỉ notes.

### Lesson 25 — Multi-Agent Systems

Score: **6.8/10**. Priority: **High**.

Nội dung mạnh nhưng quá rộng: orchestrator, tool design, parallel agents, retry, circuit breaker, debate pattern. Đây gần như mini-course riêng.

Fix đề xuất:
- Giữ one orchestrator + two tools làm primary lab.
- Đưa debate/circuit breaker/parallel research sang optional.
- Thêm token budget/rate limit guard vào runnable code.

### Lesson 26 — HuggingFace & Local Models

Score: **7.3/10**. Priority: **Medium**.

Pipeline, embeddings, Ollama/local model decision matrix hữu ích.

Fix đề xuất:
- Thêm RAM/GPU/disk estimates cho từng exercise.
- Có CPU-only fallback nhỏ để learner không bị block.
- Cẩn thận với quantization/Flash Attention notes vì phụ thuộc GPU/OS/package.

### Lesson 27 — Fine-tuning & Model Customization

Score: **7.5/10**. Priority: **Medium**.

Bài đã đúng hướng demo-oriented, có warning fine-tuning cần GPU/thời gian.

Fix đề xuất:
- Ghi rõ exercise nâng cao không bắt buộc chạy full training.
- Tách dataset preparation/evaluation thành runnable local lab.
- Thêm "fine-tune vs RAG vs prompt" decision artifact printable.

### Lesson 28 — AI APIs & Integrations

Score: **7.0/10**. Priority: **Medium**.

Multi-provider, tool use, multimodal integration đúng nhu cầu.

Fix đề xuất:
- Cập nhật provider API theo target versions.
- Thêm provider abstraction test bằng mock clients.
- Đảm bảo OpenAI examples dùng Responses API nếu là path chính.

### Lesson 29 — Production AI Systems

Score: **7.2/10**. Priority: **Medium**.

Cost tracking, caching, fallback, observability, safety/guardrails là nội dung production cần có.

Fix đề xuất:
- Tránh nói temperature=0 deterministic tuyệt đối; nói "more stable, still validate/cache carefully".
- Thêm PII redaction before logging examples.
- Thêm policy về prompt/user data retention và audit trail.

### Lesson 30 — AI System Design

Score: **7.0/10**. Priority: **Medium**.

Tổng hợp RAG/streaming/API/system design tốt.

Fix đề xuất:
- Thêm architecture decision record template.
- Tạo scaffold runnable tối thiểu hoặc link sang Day 33.
- Làm rõ API key/mock strategy cho exercises.

### Lesson 31 — Ôn tập Python Core + FastAPI

Score: **8.0/10**. Priority: **Low**.

Bài review tốt, có anti-patterns, profiling, code review checklist.

Fix đề xuất:
- Liên kết trực tiếp checklist với lỗi Day 33/34.
- Thêm "run this checklist" exercise trên project scaffold.

### Lesson 32 — Ôn tập AI/LLM Stack

Score: **7.2/10**. Priority: **Medium**.

RAG debugging, memory, eval, local/cloud comparison hữu ích. Nhưng có imports LangChain cũ như `langchain.text_splitter`, `langchain_community.vectorstores.Chroma`, `langchain.agents` cần kiểm chứng theo version target.

Fix đề xuất:
- Chuẩn hóa imports với Day 20-24.
- Thêm smoke test script cho AI stack imports.
- Thêm no-API-key mock mode.

### Lesson 33 — Project Thực Chiến: AI Backend Service

Score: **6.2/10**. Priority: **High**.

Scaffold có nhiều thứ tốt: FastAPI, SQLAlchemy async, Redis, Qdrant, JWT, Docker Compose. Nhưng hiện chưa đủ production/runnable như mô tả:

- `alembic/versions` không có revision file, nhưng README yêu cầu `alembic upgrade head`.
- App startup lại `create_all()`, trái với best practice dùng Alembic trong production.
- `documents.py` tạo `RAGPipeline()` mỗi upload, trong khi `chat.py` mới singleton; pipeline init gọi Qdrant/OpenAI embeddings mỗi lần.
- `langchain_community.vectorstores.Qdrant` và `langchain.text_splitter` là API cần cập nhật.
- `openai_api_key = "sk-placeholder"` là default nguy hiểm; nên fail fast nếu missing.
- `.env.example` được nhắc trong README nhưng không thấy trong file listing.

Fix đề xuất:
- Thêm Alembic initial revision hoặc bỏ bước Alembic khỏi README nếu dùng `create_all()` cho scaffold.
- Dùng app lifespan để khởi tạo singleton RAG/Redis clients.
- Fail fast khi `OPENAI_API_KEY` là placeholder.
- Thêm tests/smoke: health, register/login, upload text, query scoped by user.

### Lesson 34 — Project Thực Chiến: Agentic System

Score: **5.8/10**. Priority: **High**.

Ý tưởng project tốt nhưng scaffold có rủi ro runtime/architecture:

- `create_checkpointer()` dùng `AsyncPostgresSaver.from_conn_string(db_url)` rồi `await checkpointer.setup()` mà không dùng async context manager/lifespan. Tài liệu LangGraph hiện dùng checkpointer trong context manager và giữ lifecycle rõ ràng; tạo mới mỗi request cũng tốn kém và dễ leak connection.
- Project không dùng `interrupt()` thật trong approval flow; nó tự set state bằng `aupdate_state` sau một node `human_review`, nên không demo đúng built-in interrupt/resume như Day 24.
- Graph/checkpointer được build/compile mỗi request.
- `openai_api_key = "sk-placeholder"` default nguy hiểm.
- No tests, no `.env.example`, no Tavily fallback clarity.

Fix đề xuất:
- Khởi tạo graph/checkpointer ở lifespan và reuse.
- Nếu muốn dạy human-in-the-loop thật, dùng `interrupt()` + `Command(resume=...)`.
- Thêm persistence setup/teardown rõ và smoke test `/run`, `/approve`, `/status`.
- Thêm rate limiting/token budget.

### Lesson 35 — Review Tổng Thể & Roadmap

Score: **7.5/10**. Priority: **Medium**.

Tổng kết tốt, có roadmap và self-assessment. Tuy nhiên nên cập nhật sau khi Day 33/34 được sửa để learner review trên artifact thật.

Fix đề xuất:
- Thêm final checklist chạy được trên Day 33/34.
- Thêm "portfolio deliverables" rõ: repo, tests, docs, architecture note, demo script.

## Recommended Fix Plan

### Phase 1 — High-Impact Corrections

1. Sửa Day 07 duplicate và lỗi `except Exception`.
2. Sửa Day 10 `sys.sleep()`.
3. Cập nhật Day 18/19 sang Responses API-first.
4. Sửa Day 33/34 scaffold blockers: env, migrations, checkpointer lifecycle, singleton resources.
5. Tạo `python/README.md` và version matrix.

### Phase 2 — Runnability

1. Thêm smoke command cho mỗi bài có code nặng.
2. Thêm `.env.example` cho Day 33/34.
3. Thêm tests tối thiểu cho project days.
4. Chạy import/syntax smoke cho LangChain/LangGraph/LlamaIndex examples theo pinned versions.

### Phase 3 — Scope Reduction

1. Các bài >1.000 dòng: tách Must Learn vs Optional Reference.
2. Exercises >700 dòng: giảm scope hoặc tách challenge.
3. Đưa benchmark/cost/model tables sang resources có ngày cập nhật.

### Phase 4 — Technical Nuance

1. Điều kiện hóa wording "always/best/production default".
2. Thêm caveats cho API pricing/model availability.
3. Thêm security/privacy notes cho AI logging, file upload, code execution.

## Final Checklist

- [ ] `python/review-python.md` được dùng làm checklist sửa.
- [ ] Có `python/README.md` entry point.
- [ ] Có version matrix cho Python/FastAPI/SQLAlchemy/OpenAI/LangChain/LangGraph/LlamaIndex.
- [ ] Day 07 không còn duplicate và claim sai.
- [ ] Day 18/19 dùng Responses API-first.
- [ ] Day 20-24/32-34 imports pass theo pinned versions.
- [ ] Day 33 project có `.env.example`, migration hoặc policy rõ, và smoke tests.
- [ ] Day 34 project dùng checkpointer/interrupt đúng lifecycle.
- [ ] Mỗi ngày có một primary exercise runnable trong 30 phút.
- [ ] Các bài quá dài đã tách optional/deep dive.

## References Checked

- FastAPI docs via Context7: BackgroundTasks DI, WebSocket dependencies, Pydantic v2 response models.
- SQLAlchemy 2.0 docs via Context7: `create_async_engine`, `async_sessionmaker`, `expire_on_commit=False`, `selectinload`, `Result.unique()` for joined eager loads.
- LangGraph docs via Context7: `StateGraph`, checkpointers, `interrupt()`, `Command(resume=...)`, streaming with persistent checkpointers.
- OpenAI official docs: Responses API, streaming responses, structured outputs, and migration guidance from Chat Completions.
