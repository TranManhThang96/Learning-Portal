# Tài Liệu Tham Khảo — Ngày 01: Môi trường & Tooling

## 📚 Official Docs

- **pyenv** — https://github.com/pyenv/pyenv — README đầy đủ, installation guide cho mọi OS
- **uv** — https://docs.astral.sh/uv/ — Document chính thức, rất dễ đọc, có migration guide từ pip/Poetry
- **Poetry** — https://python-poetry.org/docs/ — Docs đầy đủ với configuration reference
- **ruff** — https://docs.astral.sh/ruff/ — Linting rules, configuration options, rule reference
- **mypy** — https://mypy.readthedocs.io/ — Type checking documentation và cheat sheet
- **pre-commit** — https://pre-commit.com/ — Hook configuration guide và available hooks

## 🎥 Video / Courses

- **"Python in 100 Seconds"** - Fireship (YouTube) — Overview nhanh 2 phút về Python
- **"uv: The Python Package Manager"** - ArjanCodes (YouTube) — Deep dive về uv vs Poetry
- **"Setting Up Python Development Environment 2024"** — Nhiều channels, tìm trên YouTube

## 📝 Articles / Blog Posts

- **"Why I switched from Poetry to uv"** — dev.to, medium.com — Nhiều bài chia sẻ kinh nghiệm thực tế
- **"pyproject.toml: The Modern Python Project Configuration"** — realpython.com
- **"Python Virtual Environments: A Primer"** — realpython.com — Hiểu sâu về venv vs pyenv

## 🔧 Tools / Libraries

- **pyenv** — github.com/pyenv/pyenv — Python version manager
- **uv** — github.com/astral-sh/uv — Ultra-fast Python package manager (viết bằng Rust)
- **Poetry** — github.com/python-poetry/poetry — Mature dependency management
- **ruff** — github.com/astral-sh/ruff — Fast Python linter + formatter (Rust)
- **mypy** — github.com/python/mypy — Static type checker chính thức
- **pre-commit** — github.com/pre-commit/pre-commit — Git hook framework
- **pipx** — github.com/pypa/pipx — Install CLI tools Python globally (isolated)
- **rich** — github.com/Textualize/rich — Beautiful terminal output (dùng trong exercises)

## 💡 Ghi chú thêm

- **uv đang phát triển rất nhanh** — check changelog thường xuyên, nhiều tính năng mới mỗi tuần
- **pipx** là cách đúng để install CLI tools Python globally: `pipx install poetry`, `pipx install black`
- **`.python-version` file**: commit file này để cả team dùng cùng Python version; pyenv, asdf và `uv python` đều có thể đọc/pin theo workflow của team
- **Pyright** (Microsoft): alternative cho mypy, được dùng trong Pylance VS Code extension — nhanh hơn mypy
- **Trong CI/CD**: dùng `uv sync --locked` để fail nếu `uv.lock` lệch với `pyproject.toml`, giống tinh thần `npm ci`
- **Với team lớn**: Poetry có ecosystem plugin phong phú hơn (openapi-generator, etc.) ở thời điểm hiện tại
- **ruff rules**: `UP` = pyupgrade (modernize code), `B` = flake8-bugbear, `SIM` = flake8-simplify — nên enable
