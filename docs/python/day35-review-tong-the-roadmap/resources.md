# Tài Liệu Tham Khảo — Ngày 35 (Comprehensive Final Resource Guide)

## 📚 Sách Bắt Buộc (Must-Read)

- **Fluent Python, 2nd Ed.** — Luciano Ramalho — O'Reilly — *The* Python book cho experienced developers. Covers data model, generators, decorators, async, metaclasses sâu nhất
- **Architecture Patterns with Python** — Harry Percival & Bob Gregory — O'Reilly — DDD, Clean Architecture, Event-driven trong Python. Free online: https://www.cosmicpython.com
- **Python Cookbook, 3rd Ed.** — David Beazley & Brian Jones — O'Reilly — 300+ recipes cho advanced Python patterns
- **Designing Data-Intensive Applications** — Martin Kleppmann — O'Reilly — System design foundation (language-agnostic nhưng essential)
- **Building LLM Applications** — Valentina Alto — Packt — Practical guide cho AI engineering

## 📚 Sách Nâng Cao

- **High Performance Python** — Micha Gorelick — O'Reilly — Profiling, optimization, Cython, concurrency
- **Python Testing with pytest** — Brian Okken — Pragmatic Bookshelf — Pytest deep dive
- **The Pragmatic Programmer** — Hunt & Thomas — Timeless software engineering wisdom

## 🎥 YouTube Channels

- **ArjanCodes** — https://youtube.com/@ArjanCodes — Clean code, design patterns, Python architecture
- **mCoding** — https://youtube.com/@mCoding — CPython internals, advanced Python
- **Patrick Loeber** — https://youtube.com/@PatrickLoeber — FastAPI, ML, practical tutorials
- **LangChain** — https://youtube.com/@LangChain — Official LangChain tutorials
- **Matt Pocock** — TypeScript guru (hữu ích để compare với Python typing)
- **Andrej Karpathy** — https://youtube.com/@AndrejKarpathy — ML fundamentals, LLM internals

## 🎓 Courses Nâng Cao

- **FastAPI Advanced** — https://fastapi.tiangolo.com/advanced/ — Official advanced guide, miễn phí
- **LangChain Academy** — https://academy.langchain.com — Official courses về LangGraph
- **Deep Learning Specialization** — Coursera (Andrew Ng) — ML foundation
- **Full Stack Deep Learning** — https://fullstackdeeplearning.com — Production ML systems
- **Fast.ai** — https://fast.ai — Practical deep learning, hands-on approach

## 📝 Blogs & Newsletters

- **Real Python** — https://realpython.com — Tutorials chất lượng cao, mọi cấp độ
- **Python Weekly** — https://pythonweekly.com — Newsletter tổng hợp Python news
- **The Batch** — https://deeplearning.ai/the-batch — AI news newsletter của Andrew Ng
- **LangChain Blog** — https://blog.langchain.dev — RAG patterns, agent tutorials
- **Hacker News** — https://news.ycombinator.com — Tech news, filter by "python" hoặc "llm"
- **Martin Fowler's Blog** — https://martinfowler.com — Software architecture patterns
- **Tib Zawadzki's Blog** — https://fastapi-best-practices.github.io — FastAPI patterns

## 🔧 Tools & Libraries Nâng Cao

### Performance
- **Cython** — `uv add cython` — Compile Python to C, 10-100x speedup
- **Numba** — `uv add numba` — JIT compiler cho numerical code
- **PyPy** — Alternative Python interpreter, 4-10x faster
- **Scalene** — `uv add scalene` — Best profiler: CPU + memory + GPU

### Testing & Quality
- **Hypothesis** — `uv add hypothesis` — Property-based testing
- **mutmut** — `uv add mutmut` — Mutation testing
- **Locust** — `uv add locust` — Load testing cho APIs
- **Faker** — `uv add faker` — Generate fake data cho tests
- **factory-boy** — `uv add factory-boy` — Test fixtures

### AI/ML Production
- **MLflow** — `uv add mlflow` — Experiment tracking, model registry
- **Weights & Biases** — `uv add wandb` — ML experiment tracking
- **RAGAS** — `uv add ragas` — RAG evaluation
- **DeepEval** — `uv add deepeval` — LLM evaluation framework
- **Guardrails AI** — `uv add guardrails-ai` — LLM output validation
- **Langfuse** — `uv add langfuse` — LLM observability (open source LangSmith alternative)

### Infrastructure
- **Celery** — `uv add celery` — Distributed task queue
- **ARQ** — `uv add arq` — Async task queue với Redis (lighter than Celery)
- **Kafka** — `uv add confluent-kafka` — Message streaming
- **OpenTelemetry** — `uv add opentelemetry-api opentelemetry-sdk` — Observability

## 🌐 Communities

- **Python Discord** — https://discord.gg/python — 200K+ members
- **FastAPI GitHub Discussions** — https://github.com/fastapi/fastapi/discussions
- **LangChain Discord** — Official LangChain community
- **r/Python** — https://reddit.com/r/Python — News, questions, projects
- **r/MachineLearning** — https://reddit.com/r/MachineLearning
- **Hacker News** — https://news.ycombinator.com — Tech discussions

## 🎤 Conference Talks (Must Watch)

- **PyCon US** — https://youtube.com/@PyConUS — Annual conference, excellent talks
  - "Transformers From Scratch" — Understanding LLM architecture
  - "Practical Async Python" — Deep dive async patterns
  - "SQLAlchemy 2.0 is Here" — New features deep dive
- **EuroPython** — https://youtube.com/@EuroPython
- **PyData** — Data science + Python talks

## 💼 Job Search Resources

- **LinkedIn Python Jobs** — Filter: "Python Engineer" + "FastAPI" + "AI"
- **levels.fyi** — Salary data cho Python/AI roles
- **Glassdoor Interview Questions** — "FastAPI interview questions", "LLM engineer interview"
- **GitHub** — Contributions là CV tốt nhất

## 🏆 Open Source để Contribute

### Starter (Good First Issues)
- **FastAPI** — https://github.com/fastapi/fastapi — Documentation, bug fixes
- **LangChain** — https://github.com/langchain-ai/langchain — Very active, docs & examples
- **Pydantic** — https://github.com/pydantic/pydantic — Good first issues labeled

### Intermediate
- **SQLAlchemy** — https://github.com/sqlalchemy/sqlalchemy — Complex, learn a lot
- **LangGraph** — https://github.com/langchain-ai/langgraph — Growing fast
- **FastAPI-Users** — https://github.com/fastapi-users/fastapi-users — Authentication library

### Advanced
- **uvicorn/starlette** — ASGI framework internals
- **Qdrant** — Vector database (Rust core, Python client)
- **Anthropic SDK** — https://github.com/anthropics/anthropic-sdk-python

## 💡 Ghi chú Cuối Khóa

**Bạn đã học được những gì sau 35 ngày:**
- Python syntax và idioms từ góc nhìn NodeJS developer
- FastAPI production patterns (auth, DB, caching, testing)
- AI/ML stack: OpenAI, LangChain, LlamaIndex, LangGraph
- RAG pipeline từ concept đến production
- Agentic systems với human-in-the-loop
- Docker, observability, deployment

**Điều quan trọng nhất để tiếp tục phát triển:**
1. **Build things** — Không có gì thay thế được việc tự build project thực
2. **Read code** — Đọc source code của FastAPI, Pydantic, LangChain
3. **Contribute** — Open source contribution là cách học nhanh nhất
4. **Stay current** — AI/ML thay đổi rất nhanh, follow LangChain blog, Andrej Karpathy

**Python AI Engineering vẫn là một trong những skill quan trọng nhất cho backend/AI engineering năm 2026, nhưng API thay đổi nhanh nên phải pin version và smoke test mọi lab.**
Bạn đã có nền tảng vững chắc. Hãy tiếp tục xây dựng!

---

*"The best way to learn is to build something you actually care about."*
