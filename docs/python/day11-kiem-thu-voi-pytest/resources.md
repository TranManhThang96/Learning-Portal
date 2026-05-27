# Ngày 11: Tài Liệu Tham Khảo - Testing

## Tài liệu chính thức

### pytest
- **Official Docs**: https://docs.pytest.org/en/stable/
- **Getting Started**: https://docs.pytest.org/en/stable/getting-started.html
- **Fixtures**: https://docs.pytest.org/en/stable/how-to/fixtures.html
- **Parametrize**: https://docs.pytest.org/en/stable/how-to/parametrize.html
- **Markers**: https://docs.pytest.org/en/stable/how-to/mark.html
- **Configuration**: https://docs.pytest.org/en/stable/reference/customize.html

### pytest-asyncio
- **GitHub**: https://github.com/pytest-dev/pytest-asyncio
- **Docs**: https://pytest-asyncio.readthedocs.io/
- **Modes**: https://pytest-asyncio.readthedocs.io/en/latest/reference/modes/index.html

### pytest-mock
- **GitHub**: https://github.com/pytest-dev/pytest-mock
- **Docs**: https://pytest-mock.readthedocs.io/
- `mocker.patch`, `mocker.spy`, `mocker.MagicMock`, `mocker.AsyncMock`

### Coverage
- **pytest-cov**: https://pytest-cov.readthedocs.io/
- **Coverage.py**: https://coverage.readthedocs.io/
- Configuration trong `pyproject.toml`: https://coverage.readthedocs.io/en/latest/config.html

### unittest.mock (built-in)
- **Python docs**: https://docs.python.org/3/library/unittest.mock.html
- `Mock`, `MagicMock`, `AsyncMock`, `patch`, `call`, `sentinel`

### Testing FastAPI
- **Official guide**: https://fastapi.tiangolo.com/tutorial/testing/
- **TestClient**: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient
- **Async client**: https://fastapi.tiangolo.com/advanced/async-tests/
- **Dependency override**: https://fastapi.tiangolo.com/advanced/testing-dependencies/

---

## Quick Reference

### Cài đặt

```bash
uv add pytest pytest-asyncio pytest-mock pytest-cov httpx

# Hoặc thêm vào pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    # Course nên pin minor trong lockfile vì pytest-asyncio đổi behavior theo release.
    "pytest-asyncio>=0.24",
    "pytest-mock>=3.0",
    "pytest-cov>=4.0",
    "httpx>=0.24",
]
```

### Cấu hình pyproject.toml đầy đủ

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "strict"
addopts = [
    "--strict-markers",
    "--tb=short",
    "-ra",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/migrations/*", "*/__init__.py"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 80
```

**pytest-asyncio caveat:**

- `strict` mode là cấu hình an toàn cho course: async tests dùng `@pytest.mark.asyncio`, async fixtures dùng `@pytest_asyncio.fixture`.
- `auto` mode tiện cho app nhỏ nhưng tự claim async tests/fixtures; nếu dùng, ghi rõ trong `pyproject.toml` và pin dependency trong lockfile.
- Với fixture dùng scope rộng, kiểm tra `loop_scope`; event loop scope phải bằng hoặc rộng hơn fixture caching scope.

### Các lệnh pytest hay dùng

```bash
uv run pytest                          # Chạy tất cả
uv run pytest -v                       # Verbose
uv run pytest -s                       # Show stdout (print)
uv run pytest -x                       # Stop on first failure
uv run pytest --lf                     # Re-run last failed
uv run pytest --ff                     # Run failed first
uv run pytest -k "keyword"             # Filter by name
uv run pytest -m "not slow"            # Filter by mark
uv run pytest --co                     # Collect only (list tests)
uv run pytest -n auto                  # Parallel (pytest-xdist)
uv run pytest --durations=10           # Show slowest tests
uv run pytest --cov=src --cov-report=html  # With coverage
```

---

## Bài đọc thêm

- **"Python Testing with pytest" (book)** - Brian Okken: https://pragprog.com/titles/bopytest2/python-testing-with-pytest-second-edition/
- **Real Python - Getting Started with Testing**: https://realpython.com/python-testing/
- **Effective Python Testing With Pytest**: https://realpython.com/pytest-python-testing/
- **Testing FastAPI with SQLAlchemy**: https://sqlalchemytutorial.com/async-tests

---

## So sánh với Jest ecosystem

| Jest/Vitest | Python equivalent |
|---|---|
| `jest` | `pytest` |
| `@testing-library` | `fastapi.testclient.TestClient` |
| `jest.mock()` | `unittest.mock.patch` / `mocker.patch` |
| `jest.spyOn()` | `mocker.spy()` |
| `jest.fn()` | `unittest.mock.Mock()` |
| `msw` (mock service worker) | `respx` (httpx mock) hoặc `responses` |
| `supertest` | `httpx.AsyncClient` + `TestClient` |
| `jest --coverage` | `pytest --cov=src --cov-report=html` |
| `jest --watch` | `pytest-watch` (ptw) |
| `@jest/globals` | Không cần import (auto-discovered) |

---

## Plugins hữu ích

| Plugin | Mục đích | Install |
|---|---|---|
| `pytest-xdist` | Chạy parallel | `uv add pytest-xdist` |
| `pytest-watch` | Watch mode | `uv add pytest-watch` |
| `pytest-randomly` | Random test order | `uv add pytest-randomly` |
| `factory-boy` | Test data factories | `uv add factory-boy` |
| `faker` | Fake data generation | `uv add faker` |
| `freezegun` | Mock datetime | `uv add freezegun` |
| `respx` | Mock httpx requests | `uv add respx` |
| `responses` | Mock requests library | `uv add responses` |
| `syrupy` | Snapshot testing | `uv add syrupy` |
| `pytest-benchmark` | Performance testing | `uv add pytest-benchmark` |
