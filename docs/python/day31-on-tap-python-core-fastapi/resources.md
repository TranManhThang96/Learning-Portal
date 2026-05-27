# Tài Liệu Tham Khảo — Ngày 31

## 📚 Official Docs

- **Python cProfile** — https://docs.python.org/3/library/profile.html — Built-in profiler
- **Python tracemalloc** — https://docs.python.org/3/library/tracemalloc.html — Memory tracing
- **mypy strict mode** — https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict
- **Ruff linter** — https://docs.astral.sh/ruff/ — Fast Python linter
- **FastAPI Testing** — https://fastapi.tiangolo.com/tutorial/testing/ — Official testing guide

## 🎥 Video / Courses

- **Python Profiling Tutorial** — ArjanCodes YouTube — Profiling với cProfile và py-spy
- **FastAPI Best Practices** — Patrick Loeber YouTube — Production patterns
- **Clean Code in Python** — mCoding YouTube — Code quality deep dive

## 📝 Articles / Blog Posts

- **py-spy: A sampling profiler for Python** — https://github.com/benfred/py-spy — Readme đầy đủ
- **FastAPI Production Checklist** — https://github.com/zhanymkanov/fastapi-best-practices
- **Python Type Hints Cheat Sheet** — mypy docs — Comprehensive reference

## 🔧 Tools / Libraries

- **py-spy** — `uv add py-spy` — Production profiler, không cần modify code
- **memory-profiler** — `uv add memory-profiler` — Line-by-line memory profiling
- **snakeviz** — `uv add snakeviz` — Visualize cProfile output trong browser
- **scalene** — `uv add scalene` — GPU/CPU/memory profiler kết hợp
- **objgraph** — `uv add objgraph` — Visualize Python object references
- **fakeredis** — `uv add fakeredis` — In-memory Redis cho testing

## 💡 Ghi chú thêm

**Workflow profiling khuyến nghị:**
1. Đo với `time.perf_counter()` trước — xác định endpoint nào chậm
2. Dùng `cProfile` để tìm function nào tốn thời gian
3. Dùng `py-spy` nếu cần profile production mà không restart
4. Dùng `memory_profiler` nếu nghi ngờ memory leak
5. Đo lại sau khi fix để verify improvement

**Profiling trong FastAPI:**
- Middleware profiling: thêm `time.perf_counter()` trong middleware
- Per-route profiling: sử dụng `cProfile.Profile()` trong route handler
- Production: `py-spy` attach vào uvicorn process PID
