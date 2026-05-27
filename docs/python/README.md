# Python 35 Days

Curriculum này dành cho Senior NodeJS Developer học Python, FastAPI và AI engineering trong 35 ngày. Mỗi ngày vẫn giữ format chính:

- `lesson.md`: phần phải học trong buổi chính.
- `resources.md`: tài liệu, links, tooling và phần đọc thêm.
- `exercises.md`: bài tập tự làm.

## Cách Học Khuyến Nghị

Mỗi ngày nên giới hạn vào một primary path trong 2 giờ:

1. Đọc mục tiêu, so sánh với NodeJS và phần lý thuyết chính.
2. Chạy một ví dụ hoặc một primary lab nhỏ.
3. Làm bài tập cơ bản hoặc trung bình.
4. Đẩy deep dive, matrix lớn, benchmark và challenge sang cuối tuần hoặc ngày ôn tập.

Các ngày có nội dung dài hơn 900 dòng cần được đọc theo nhãn scope trong bài:

- **Must Learn**: học trong 2 giờ.
- **Optional Reference**: đọc khi cần triển khai thật.
- **Challenge**: làm sau khi primary lab đã chạy được.

## Version Matrix

Xem [version-matrix.md](version-matrix.md) trước khi chạy các bài liên quan đến FastAPI, SQLAlchemy, OpenAI SDK, LangChain, LangGraph hoặc LlamaIndex. Các thư viện AI thay đổi nhanh, nên code trong bài nên được hiểu theo target version thay vì copy mù quáng vào project dùng version khác.

## Giai Đoạn 1 — Python Fundamentals, Days 06-10

| Ngày | Folder | Chủ đề |
|---|---|---|
| 06 | `day06-modules-packages-cau-truc-du-an/` | Modules, Packages & Project Structure |
| 07 | `day07-xu-ly-loi-va-typing/` | Error Handling & Typing |
| 08 | `day08-doc-ghi-file-context-managers-serialization/` | File I/O, Context Managers & Serialization |
| 09 | `day09-async-python-bat-dong-bo/` | Async Python |
| 10 | `day10-dong-thoi-va-song-song/` | Concurrency & Parallelism |

## Giai Đoạn 3 — Tổng Hợp & Thực Chiến

| Ngày | Folder | Chủ đề |
|---|---|---|
| 31 | `day31-on-tap-python-core-fastapi/` | Review Python Core + FastAPI |
| 32 | `day32-on-tap-ai-llm-stack/` | Review AI/LLM stack, RAG, agents |
| 33 | `day33-project-ai-backend-service/` | Project AI Backend Service |
| 34 | `day34-project-agentic-system/` | Project Agentic System |
| 35 | `day35-review-tong-the-roadmap/` | Review tổng thể và roadmap |

## Review Và Fix Plan

Review tổng thể nằm ở [review-python.md](review-python.md). Khi cập nhật course, ưu tiên:

1. Sửa lỗi kỹ thuật High priority.
2. Làm primary lab chạy được.
3. Giảm scope bài quá dài bằng cách chuyển phần nâng cao sang optional/reference.
4. Cập nhật API docs hiện hành với Context7 hoặc official docs.

## Smoke Checks Chung

Các project scaffold nên có ít nhất các lệnh sau trong README riêng của ngày:

```bash
uv sync
uv run ruff check .
uv run mypy .
uv run pytest
```

Với bài không có project riêng, exercise nên ghi rõ command tối thiểu để learner tự kiểm tra output.
