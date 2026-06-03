# Python 35 Days

Curriculum này dành cho Senior NodeJS Developer học Python, FastAPI và AI engineering trong 35 ngày.

## Bắt đầu

- [Version Matrix](./version-matrix.md): kiểm tra version mục tiêu trước khi chạy bài có FastAPI, SQLAlchemy, OpenAI SDK, LangChain, LangGraph hoặc LlamaIndex.
- [Ngày 01: Môi trường & Tooling](./day01-moi-truong-va-tooling/lesson.md): setup Python runtime, package manager, linting và type checking.
- [Review tổng thể](./review-python.md): danh sách lỗi, ưu tiên chỉnh sửa và hướng cải thiện course.

## Phân tích 80/20

Xem phân tích chi tiết: [80-20 Learning Priority](./80-20-phan-tich-uu-tien.md)

**Tóm tắt 80/20:** ~20% kiến thức mang lại ~80% hiệu quả. Ưu tiên: Async Python + FastAPI, Python Core, OpenAI SDK + Prompt Engineering, RAG Pipeline, Testing + Deployment.

## Cách học khuyến nghị (theo 80/20)

### Nhóm A — Học ngay, bắt buộc (15 chủ đề)
Python Core: Tooling → Syntax → Data Structures → Functions → OOP → Async → Error Handling
Backend: FastAPI (routing, DI, auth) → SQLAlchemy async → Testing → Docker
AI: OpenAI SDK → Prompt Engineering → RAG basic

### Nhóm B — Học sớm (12 chủ đề)
LangChain, LangGraph, RAG advanced, Production AI, AI System Design, NumPy/Pandas, AI APIs, Concurrency

### Nhóm C — Học sau khi có basic project
LlamaIndex, Multi-agent, HuggingFace, Agentic System project

### Nhóm D — Đọc lướt / tra cứu
Fine-tuning, Python internals, Advanced multiprocessing, Final review

### Ghi chú
Mỗi ngày nên giới hạn vào một primary path trong 2 giờ:

1. Đọc mục tiêu, so sánh với NodeJS và phần lý thuyết chính.
2. Chạy một ví dụ hoặc một primary lab nhỏ.
3. Làm bài tập cơ bản hoặc trung bình.
4. Đẩy deep dive, matrix lớn, benchmark và challenge sang cuối tuần hoặc ngày ôn tập.

Các ngày có nội dung dài hơn nên được đọc theo nhãn scope trong bài:

- **Must Learn**: học trong 2 giờ.
- **Optional Reference**: đọc khi cần triển khai thật.
- **Challenge**: làm sau khi primary lab đã chạy được.

## Lộ trình

| Giai đoạn | Ngày | Nội dung |
|:---|---:|---|
| Python Core | 01-12 | Tooling, syntax, data structures, functions, OOP, modules, typing, file I/O, async, concurrency, testing, database |  
| Backend & Data | 13-18 | FastAPI, database, caching, production deployment, NumPy/Pandas, OpenAI SDK |  
| AI Engineering | 19-30 | Prompting, LangChain, RAG, LlamaIndex, LangGraph, multi-agent systems, Hugging Face, fine-tuning, AI system design |  
| Review & Projects | 31-35 | Review Python/FastAPI/LLM stack, AI backend project, agentic system project, roadmap review |  

## Smoke checks chung

Các project scaffold nên có ít nhất các lệnh sau trong README riêng của ngày:

```bash
uv sync
uv run ruff check .
uv run mypy .
uv run pytest
```

Với bài không có project riêng, exercise nên ghi rõ command tối thiểu để learner tự kiểm tra output.
