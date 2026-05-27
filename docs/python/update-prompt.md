# PROMPT CHO CLAUDE CODE — Cập Nhật Curriculum 35 Ngày Học Python

---

## Vai trò

Bạn là một kỹ sư phần mềm cấp senior với hơn 10 năm kinh nghiệm Python, chuyên sâu về:
- Python core & ecosystem (CPython internals, GIL, async/await, metaclass...)
- FastAPI, Pydantic, SQLAlchemy, Alembic
- AI/ML stack: LangChain, LlamaIndex, OpenAI SDK, HuggingFace Transformers, LangGraph
- Performance optimization, profiling, benchmarking
- Clean Architecture, DDD, SOLID trong Python
- DevOps cho Python: Docker, Poetry, uv, pre-commit, CI/CD

Học viên là Senior NodeJS Developer (5+ năm), thành thạo TypeScript, async/await, REST/gRPC, Kafka, Redis, PostgreSQL, Docker, microservices. Chưa bao giờ viết Python.

Toàn bộ nội dung viết bằng **Tiếng Việt**. Code và thuật ngữ kỹ thuật giữ nguyên tiếng Anh.

---

## Nhiệm vụ

Cập nhật toàn bộ curriculum 35 ngày học Python đã có sẵn trong project. Dưới đây là danh sách các vấn đề cần sửa, sắp xếp theo thứ tự ưu tiên.

---

## 1. THAY ĐỔI CẤU TRÚC — Gộp & Tái phân bổ ngày

### 1.1. Gộp Ngày 19 + 20 (LangChain) thành 1 ngày

- **Lý do:** LangChain API thay đổi liên tục, không nên đầu tư 2 ngày riêng.
- **Cách làm:** Gộp thành 1 ngày "LangChain: Chains, Tools & Agents". Giữ lại core concepts (PromptTemplate, OutputParsers, Chains, Tools, ReAct Agents, LangSmith basics). Bỏ bớt Memory types chi tiết (chỉ mention ngắn). Bỏ Callbacks deep dive.
- **Kết quả:** Giải phóng 1 ngày trống.

### 1.2. Tách Ngày 09 (Async Python) thành 2 ngày

- **Lý do:** Ngày 09 hiện tại quá nặng — nhồi cả async/await, GIL, threading, multiprocessing, httpx, aiofiles vào 2 tiếng. Đây là khác biệt lớn nhất giữa Python và Node.js, cần dạy kỹ.
- **Cách làm:**
  - **Ngày 09A — Async Python:** Event loop, coroutines, async/await (so sánh sâu với Node.js event loop), asyncio tasks/gather/timeout/queue, async context managers, async generators, httpx, aiofiles.
  - **Ngày 09B — Concurrency & Parallelism:** GIL deep dive (tại sao tồn tại, ảnh hưởng thực tế), threading vs multiprocessing vs asyncio (khi nào dùng cái nào), `concurrent.futures` (ThreadPoolExecutor, ProcessPoolExecutor), kết hợp asyncio + multiprocessing cho CPU-bound tasks, `asyncio.to_thread()`.
- **Kết quả:** Sử dụng 1 ngày trống từ việc gộp LangChain.

### 1.3. Đánh lại số ngày

Sau khi gộp/tách, đánh lại số thứ tự ngày từ 01 đến 35 cho liền mạch. Cập nhật tất cả cross-references giữa các bài.

---

## 2. BỔ SUNG NỘI DUNG THIẾU — Thêm vào ngày hiện có

Các phần dưới đây KHÔNG tạo ngày mới, mà bổ sung vào ngày phù hợp đã có.

### 2.1. Debugging Tools → Thêm vào Ngày 01 (Môi trường & Tooling)

Thêm section mới trong `lesson.md`:
```
### Debugging trong Python
- `breakpoint()` (Python 3.7+) — tương đương `debugger` trong Node.js
- `pdb` commands cơ bản: n (next), s (step), c (continue), p (print), l (list)
- VS Code Python debugger: launch.json config, breakpoints, watch variables
- `icecream` library (ic()) — debug nhanh hơn print()
- So sánh: console.log → print() → ic() → breakpoint() → VS Code debugger
```
Thêm 1 bài tập debug vào `exercises.md`: cho sẵn code có bug, dùng pdb/breakpoint để tìm và fix.

### 2.2. Regex & String Processing → Thêm vào Ngày 02 (Python Syntax Cơ Bản)

Thêm section:
```
### Regular Expressions
- `re` module: match, search, findall, sub, compile
- Named groups, lookahead/lookbehind
- So sánh regex syntax Python vs JavaScript (gần như giống, khác ở flags)
- Ứng dụng thực tế: validate email, parse log, clean text cho AI pipeline
```

### 2.3. Pydantic v2 Deep Dive → Mở rộng Ngày 08

Ngày 08 hiện có Pydantic nhưng chưa đủ sâu. Bổ sung:
```
- Custom validators (@field_validator, @model_validator)
- Computed fields (@computed_field)
- Model inheritance và discriminated unions
- Serialization aliases (alias, validation_alias, serialization_alias)
- model_config: strict mode, extra fields handling
- Pydantic Settings cho environment variables
- Performance: Pydantic v2 vs v1 (Rust core)
```

### 2.4. WebSocket → Thêm vào Ngày 13 (FastAPI Nâng Cao)

Thêm section:
```
### WebSocket trong FastAPI
- WebSocket endpoint cơ bản
- Connection manager pattern (broadcast, rooms)
- Authentication cho WebSocket
- So sánh WebSocket vs SSE — khi nào dùng cái nào
- Ứng dụng: real-time chat, AI streaming responses qua WebSocket
```

### 2.5. Security Practices → Thêm vào Ngày 13 (cùng Authentication)

Thêm section:
```
### Security Best Practices
- Password hashing: bcrypt, argon2 (passlib)
- `secrets` module cho token generation
- Input sanitization, SQL injection prevention (SQLAlchemy đã handle)
- Dependency vulnerability scanning: pip-audit, safety
- HTTPS, secure headers
- So sánh với helmet.js trong Express
```

### 2.6. CI/CD Pipeline → Thêm vào Ngày 15 (Deployment)

Thêm section:
```
### CI/CD cho Python
- GitHub Actions workflow cho Python: lint → test → build → deploy
- tox/nox cho multi-version testing
- Docker image build & push trong CI
- Secrets management trong CI/CD
- Pre-commit CI integration
- So sánh với Node.js CI pipeline (gần tương tự, thêm tox)
```

### 2.7. Matplotlib / Visualization cơ bản → Thêm vào Ngày 16 (Numpy & Pandas)

Thêm section ngắn:
```
### Data Visualization Cơ Bản
- Matplotlib: plot, bar, scatter, histogram — chỉ cần biết đủ dùng
- Seaborn cho statistical plots
- Khi nào cần visualize: debug embeddings (t-SNE/UMAP), analyze data distribution, model evaluation
- Lưu ý: không cần master — chỉ cần biết đủ để phục vụ AI/ML workflow
```

### 2.8. Vector DB Comparison → Mở rộng Ngày 21 (RAG)

Thêm bảng so sánh chi tiết:
```
### So sánh Vector Databases
| Tiêu chí | Chroma | Qdrant | pgvector | Pinecone | Weaviate |
|----------|--------|--------|----------|----------|----------|
| Self-hosted | ✅ | ✅ | ✅ (PostgreSQL extension) | ❌ (managed only) | ✅ |
| Managed option | ❌ | ✅ | ✅ (Supabase, Neon) | ✅ | ✅ |
| Scaling | Đơn giản, nhỏ | Tốt, production-ready | Phụ thuộc PostgreSQL | Tốt nhất | Tốt |
| Use case | Prototype, dev | Production | Đã có PostgreSQL | Enterprise | Multi-modal |
| Hybrid search | ❌ | ✅ | Cần config | ✅ | ✅ |

- Khi nào dùng cái nào: decision tree cho team
- Performance benchmarks reference
- Migration strategy giữa các vector DBs
```

### 2.9. AI Safety & Guardrails → Mở rộng Ngày 29 (Production AI Systems)

Thêm section:
```
### AI Safety & Responsible AI
- Content filtering: input/output moderation
- Bias detection cơ bản trong LLM outputs
- PII detection và redaction
- Guardrails libraries: NeMo Guardrails, Guardrails AI
- Logging & auditing cho AI decisions
- Regulatory awareness: EU AI Act basics
```

---

## 3. BỔ SUNG NỘI DUNG MỚI HOÀN TOÀN — Cần tìm chỗ lồng ghép

Các phần này cần được lồng ghép vào ngày phù hợp hoặc thêm như section phụ. KHÔNG tạo ngày mới.

### 3.1. Design Patterns trong Python → Lồng vào Ngày 06 (Modules & Project Structure)

```
### Design Patterns phổ biến trong Python
- Tại sao patterns trong Python khác TypeScript/Java: first-class functions, duck typing
- Singleton: module-level instance (Python way) vs class-based
- Factory: function-based factory (không cần abstract class)
- Strategy: dùng functions thay vì class hierarchy
- Observer: signals/events pattern
- Dependency Injection: không cần framework phức tạp như NestJS
- Repository pattern (preview — sẽ dùng nhiều ở Ngày 11)
```

### 3.2. gRPC trong Python → Lồng vào Ngày 14 hoặc 15

Thêm section ngắn (không cần deep dive vì học viên đã biết gRPC từ Node.js):
```
### gRPC trong Python (Quick Reference)
- grpcio + grpcio-tools setup
- Proto file → Python codegen
- Async gRPC server với grpcio
- So sánh developer experience: Node.js gRPC vs Python gRPC
- Khi nào dùng gRPC vs REST trong Python microservices
```

### 3.3. Task Queue / Background Jobs → Lồng vào Ngày 15 (Deployment) hoặc Ngày 30

Hiện tại Celery chỉ được nhắc qua. Bổ sung:
```
### Async Task Queues
- Celery: architecture, broker (Redis/RabbitMQ), worker, beat
- ARQ: lightweight alternative (async-native, dùng Redis)
- Dramatiq: middle ground
- So sánh: BullMQ (Node.js) → Celery/ARQ (Python)
- Khi nào dùng: long-running AI tasks, email, report generation
- Code example: Celery task cơ bản với FastAPI
```

---

## 4. SỬA VẤN ĐỀ PHÂN BỔ THỜI GIAN

### 4.1. Ngày 16 (Numpy + Pandas) — Giảm scope

- Ngày 16 hiện quá nặng cho 2 tiếng. Giảm bớt Pandas scope.
- **Giữ:** Numpy arrays, vectorized operations, broadcasting, Pandas DataFrame basics (read, filter, groupby, merge).
- **Bỏ/Giảm:** Pandas advanced (pivot tables, multi-index, window functions). Chỉ mention và để link tài liệu.
- **Thêm note:** "Pandas advanced topics — tự học khi cần, đây là reference skill không cần master ngày đầu."

### 4.2. Ngày 27 (Fine-tuning) — Chuyển sang demo-oriented

- Fine-tuning LoRA/QLoRA trong 2 tiếng là không thực tế (cần GPU setup, dataset prep).
- **Cách sửa:** Chuyển sang approach "Theory + Demo + When to Use":
  - 40 phút: Lý thuyết — khi nào fine-tune vs RAG vs prompt engineering (decision tree)
  - 20 phút: Demo walkthrough — xem code LoRA fine-tuning (không chạy thực tế, giải thích từng bước)
  - 30 phút: Hands-on dataset preparation với Pydantic (phần này chạy được)
  - 30 phút: Bài tập — evaluate model với BLEU/ROUGE (dùng pre-trained model)
- **Ghi rõ trong lesson.md:** "Fine-tuning thực tế cần GPU (Colab/RunPod) và 2–4 giờ training time. Bài này focus vào understanding, không expect chạy full fine-tune trong 2 tiếng."

### 4.3. Ngày 33–34 (Project thực chiến) — Cung cấp scaffold nhiều hơn

- 2 tiếng cho full-stack project là không đủ nếu code từ đầu.
- **Cách sửa:**
  - Tạo folder `project/` với **scaffold code đầy đủ** (~70% hoàn thiện)
  - Học viên chỉ cần implement các phần core (RAG pipeline, agent logic, streaming)
  - Các phần boilerplate đã có sẵn: Docker Compose, database setup, auth, project structure
  - Đánh dấu rõ trong code: `# TODO: Implement this` với instructions
  - Thêm `project/README.md` với hướng dẫn step-by-step

---

## 5. QUY TẮC THỰC HIỆN

### Format bắt buộc

Mỗi ngày phải có 3 file trong folder `dayXX/`:
1. `lesson.md` — đúng format: Mục tiêu, So sánh NodeJS, Lý thuyết (WHY→HOW), Common Mistakes, Best Practices, Trade-offs, Performance Notes, Tóm tắt
2. `exercises.md` — 3 bài (Cơ bản, Trung bình, Nâng cao), mỗi bài có mô tả, yêu cầu, expected output, hint
3. `resources.md` — Official Docs, Videos, Articles, Tools, Ghi chú thêm

Ngày 33–34 thêm folder `project/` với scaffold code.

### Nguyên tắc chỉnh sửa

1. **Không thay đổi phong cách giảng dạy** — vẫn giữ: so sánh Node.js, WHY trước HOW, Common Mistakes, production-focused.
2. **Khi thêm nội dung vào ngày có sẵn** — cân nhắc bỏ bớt phần ít quan trọng hơn để giữ tổng thời gian 2 tiếng/ngày. Ghi rõ "phần mở rộng — đọc thêm nếu có thời gian" cho nội dung phụ.
3. **Cập nhật bảng tổng quan curriculum** ở đầu project sau khi thay đổi.
4. **Cập nhật cross-references** — nếu ngày A reference ngày B và số ngày thay đổi, phải update.
5. **Code example phải chạy được** — đủ import, không thiếu dependency, có comment tiếng Việt.
6. **Mỗi file thay đổi cần commit message rõ ràng** mô tả thay đổi gì.

### Thứ tự thực hiện

1. Gộp Ngày 19+20, tách Ngày 09, đánh lại số ngày (Phần 1)
2. Bổ sung nội dung vào các ngày hiện có (Phần 2)
3. Lồng ghép nội dung mới (Phần 3)
4. Sửa phân bổ thời gian (Phần 4)
5. Cập nhật bảng tổng quan curriculum
6. Review lại toàn bộ cross-references

---

## 6. CHECKLIST KIỂM TRA SAU KHI HOÀN THÀNH

- [x] Tổng số ngày vẫn là 35
- [x] Mỗi ngày có đủ 3 file (lesson.md, exercises.md, resources.md)
- [x] Ngày 33–34 có folder project/ với scaffold + README.md
- [x] Bảng tổng quan curriculum (mega-prompt.md, python-prompt.md) đã được cập nhật
- [x] Tất cả cross-references đúng số ngày mới
- [x] Các section mới thêm có đủ: code example, so sánh Node.js (nếu relevant)
- [x] Phần concurrency (Ngày 10 mới) có đủ: GIL, threading, multiprocessing, concurrent.futures
- [x] Debugging tools có trong Ngày 01 (breakpoint, pdb, icecream, VS Code)
- [x] Regex & String Processing có trong Ngày 02
- [x] Pydantic v2 deep dive (aliases, discriminated unions, strict mode) có trong Ngày 08
- [x] WebSocket có trong Ngày 14 (FastAPI Nâng Cao)
- [x] Security practices có trong Ngày 14 (bcrypt, secrets, secure headers)
- [x] CI/CD có trong Ngày 16 (Deployment)
- [x] Design Patterns có trong Ngày 06 (Project Structure)
- [x] Vector DB comparison table có trong Ngày 21 (RAG)
- [x] Task Queue (Celery/ARQ) được cover trong Ngày 16 (Deployment)
- [x] AI Safety & Guardrails có trong Ngày 29 (Production AI)
- [x] gRPC Quick Reference có trong Ngày 15
- [x] Visualization (Matplotlib/Seaborn) có trong Ngày 17
- [x] Ngày 17 (Numpy/Pandas) — giảm scope: pivot/window functions đánh dấu "reference skill"
- [x] Ngày 27 (Fine-tuning) đã chuyển sang demo-oriented với lưu ý thực tế rõ ràng
- [x] Ngày 33–34 có scaffold code + README step-by-step

**Cập nhật hoàn thành ngày 2026-03-24**