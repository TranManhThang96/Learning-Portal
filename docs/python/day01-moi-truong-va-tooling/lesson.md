# Ngày 01: Môi trường & Tooling

## 🎯 Mục tiêu học tập
- Pin và quản lý Python versions bằng công cụ phù hợp với team (`pyenv`, `asdf`, hoặc `uv python`)
- Sử dụng uv/Poetry để quản lý packages (so sánh với npm/yarn)
- Hiểu virtual environments (so sánh với node_modules)
- Setup VS Code cho Python development với linting và type checking
- Cấu hình pre-commit hooks

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python |
|-----------|-------------------|--------|
| Version manager | nvm | pyenv / asdf / uv python |
| Package manager | npm / yarn / pnpm | pip / Poetry / uv |
| Package registry | npmjs.com | PyPI (pypi.org) |
| Dependencies file | package.json | pyproject.toml |
| Lock file | package-lock.json / yarn.lock | poetry.lock / uv.lock |
| Isolated env | node_modules (per project) | virtualenv (thư mục riêng) |
| Run scripts | npm run xxx | uv run xxx / python -m xxx / poetry run xxx |
| Dev dependencies | devDependencies | dependency groups (`[dependency-groups]`) / Poetry groups |
| Global install | npm install -g | pipx |
| Linter | ESLint | ruff |
| Formatter | Prettier | ruff format / black |
| Type checker | TypeScript compiler | mypy / pyright |

**Điểm khác biệt quan trọng:**
- Node: `node_modules` nằm trong thư mục project, mỗi project tách biệt
- Python: virtualenv là thư mục độc lập, thường đặt trong `.venv/` của project hoặc `~/.venvs/`
- uv tự động quản lý `.venv` — không cần activate thủ công khi dùng `uv run`

**Target cho khóa học này:**
- Python: **3.12.x** (ổn định, đủ modern syntax cho course; tránh nhảy sang 3.13/3.14 nếu team chưa pin)
- Tooling: dùng **uv stable hiện tại của team**; `ruff`/`mypy` được pin qua `uv.lock` thay vì học thuộc version trong lesson
- Project state sau setup: có `.python-version`, `pyproject.toml`, `uv.lock`; có `.venv/` local nhưng **không commit**
- `pyproject.toml`: `requires-python = ">=3.12,<3.13"` để bài học và CI dùng cùng major/minor

## 📖 Lý thuyết

### 1. Pin Python Version — pyenv/asdf/uv python

**WHY:** Python 2.x và 3.x incompatible hoàn toàn. Nhiều projects dùng Python 3.9, 3.10, 3.11, 3.12 — cần switch nhanh. System Python thường outdated và không nên dùng cho development.

`pyenv` rất phổ biến và gần với `nvm`, nhưng **không phải lựa chọn bắt buộc**. Team có thể dùng `asdf`, Docker devcontainer, hoặc `uv python` miễn là repo pin version rõ ràng và CI chạy đúng version đó.

**HOW:**
```bash
# Option A: uv quản lý Python runtime cho project
uv python install 3.12
uv python pin 3.12        # tạo/cập nhật .python-version
uv run python --version   # Python 3.12.x

# Option B: pyenv (Linux/Mac), nếu team đã chuẩn hóa pyenv
curl https://pyenv.run | bash

# Thêm vào ~/.zshrc hoặc ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Cài Python version cụ thể theo team pin (ví dụ bên dưới)
pyenv install 3.12.8

# Set global default
pyenv global 3.12.8

# Set local (per project) — tạo file .python-version
pyenv local 3.12.8

# Set tạm thời cho shell hiện tại — không ghi vào repo
pyenv shell 3.12.8

# Xem versions đang có
pyenv versions
# * 3.12.8 (set by /home/user/project/.python-version)
```

**Khác biệt `pyenv global/local/shell`:**

| Command | Scope | Ghi vào đâu | Khi nào dùng |
|---------|-------|-------------|--------------|
| `pyenv global 3.12.8` | User default | `~/.pyenv/version` | Default cho máy cá nhân |
| `pyenv local 3.12.8` | Project hiện tại | `.python-version` | Pin version cho repo/team |
| `pyenv shell 3.12.8` | Terminal session | env var `PYENV_VERSION` | Test nhanh một version, không commit |

Thứ tự ưu tiên thực tế: `pyenv shell` thắng `pyenv local`, và `pyenv local` thắng `pyenv global`.

### 2. uv — Package Manager Thế Hệ Mới (Khuyến dùng)

**WHY:** uv (2024) viết bằng Rust, nhanh hơn pip 10-100x. Syntax quen với npm. Đang nhanh chóng thay thế Poetry trong projects mới.

**HOW:**
```bash
# Cài uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Tạo project mới (giống npm init)
uv init my-project
cd my-project

# Pin Python target cho project
uv python pin 3.12

# Thêm dependency (giống npm install fastapi)
uv add fastapi

# Thêm dev dependency (giống npm install -D jest)
uv add --dev pytest ruff mypy

# Tạo/cập nhật lock file, rồi sync dependencies từ lock file
uv lock
uv sync --locked

# Run script trong virtualenv
uv run python main.py
uv run pytest

# Xem packages đã cài
uv pip list
```

`uv run` là workflow mặc định trong project: uv sẽ đảm bảo `.venv` tồn tại, kiểm tra `uv.lock` có khớp `pyproject.toml` không, sync môi trường nếu cần, rồi mới chạy command. Vì vậy learner không cần nhớ `source .venv/bin/activate` trong daily workflow.

```toml
# pyproject.toml được tạo tự động — tương đương package.json
[project]
name = "my-project"
version = "0.1.0"
description = "Add your description here"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.104.0",
]

[dependency-groups]
dev = [
    "pytest",
    "ruff",
    "mypy",
]
```

### 3. Poetry — Package Manager Truyền Thống

**WHY:** Mature, nhiều tài liệu, plugin system. Vẫn phổ biến trong production projects hiện tại.

```bash
# Cài Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Tạo project mới
poetry new my-project
cd my-project

# Thêm dependencies
poetry add fastapi
poetry add --group dev pytest ruff mypy

# Activate shell với virtualenv
poetry shell

# Install từ lock file (sau khi clone repo)
poetry install

# Run command
poetry run python main.py
```

### 4. Virtual Environments

**WHY:** Python install packages globally theo default → conflict giữa projects. Virtualenv tạo Python isolated cho từng project.

```bash
# uv tự quản lý — không cần activate thủ công
uv run python main.py  # dùng .venv tự động

# Cách thủ công (biết để đọc legacy docs)
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate       # Windows
which python                 # verify đang dùng venv
deactivate                   # exit venv
```

### 5. VS Code Setup

**Extensions cần thiết:**
```
- Python (Microsoft) — language support, interpreter selection
- Pylance — type checking, IntelliSense
- Ruff — linting + formatting (thay thế flake8 + black + isort)
- mypy type checker — static type analysis
```

**.vscode/settings.json:**
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  },
  "mypy-type-checker.args": ["--strict"]
}
```

**Cấu hình ruff trong pyproject.toml:**
```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
ignore = ["B008"]  # B008: do not perform function calls in default arguments

[tool.mypy]
python_version = "3.12"
strict = true
```

### 6. pre-commit Hooks

**WHY:** Tương tự Husky trong Node.js, đảm bảo code quality trước mỗi commit.

```bash
uv add --dev pre-commit
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.6.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

```bash
# Cài hooks vào git
pre-commit install

# Chạy thủ công trên tất cả files
pre-commit run --all-files
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Install packages globally với pip | Conflict giữa projects | Luôn dùng virtualenv / uv / Poetry |
| Commit thư mục `.venv` | Repo nặng GB, paths khác nhau mỗi máy | Thêm `.venv` vào `.gitignore` |
| Dùng `pip freeze > requirements.txt` | Không pin transitive deps, deploy lỗi | Dùng `poetry.lock` hoặc `uv.lock` |
| Dùng system Python không pin version | System Python outdated, conflict OS packages | Pin `.python-version` và dùng pyenv/asdf/uv python theo team |
| Bỏ qua type hints | Code khó maintain, lỗi runtime khó debug | Bật mypy strict từ đầu |
| `pip install` bên ngoài virtualenv | Pollute global Python | Kiểm tra `which python` trước khi install |

## ✅ Best Practices

- **Dùng uv cho projects mới** — nhanh nhất, syntax gần npm nhất
- **Luôn pin Python version** trong pyproject.toml: `requires-python = ">=3.12,<3.13"`
- **Đặt `.python-version` file** trong repo để cả team dùng cùng version, bất kể tool là pyenv/asdf/uv python
- **ruff thay vì black + flake8** — một tool làm tất cả, nhanh hơn 10x
- **Bật mypy strict** từ ngày đầu — dễ hơn enable sau
- **Commit `.pre-commit-config.yaml`** vào repo để toàn team áp dụng
- **Dùng `pipx`** để install CLI tools globally (như `npm install -g`): `pipx install poetry`

## ⚖️ Trade-offs

| Tool | Pros | Cons | Khi nào dùng |
|------|------|------|--------------|
| **uv** | Siêu nhanh (Rust), syntax quen npm | Còn mới (2024), plugin ecosystem nhỏ | Projects mới |
| **Poetry** | Mature, plugin phong phú, docs tốt | Chậm hơn uv | Legacy projects, cần plugins |
| **pip + venv** | Built-in, không cần cài thêm | Thủ công, không có lock file tốt | Scripts đơn giản |

## 🚀 Performance Notes

- **uv nhanh hơn pip 10-100x** nhờ parallel downloads và Rust runtime
- Dùng `uv sync --locked` trong CI/CD — fail nếu lock file không khớp, giống tinh thần `npm ci`
- Cache pyenv downloads: `~/.pyenv/cache/` — giữ lại để tái dùng, tiết kiệm download
- ruff nhanh hơn flake8 + black + isort cộng lại vì viết bằng Rust

## 🐛 Debugging trong Python

Đây là skill cần có ngay từ ngày đầu — đừng debug bằng `print()` mãi.

```python
# breakpoint() — Python 3.7+ — tương đương debugger trong NodeJS
def calculate_discount(price: float, user_level: str) -> float:
    discount = 0.0
    if user_level == "gold":
        discount = 0.2
    elif user_level == "silver":
        discount = 0.1

    breakpoint()  # Dừng lại đây, mở interactive debugger
    # Trong terminal: n (next), s (step into), c (continue), p price (print var), l (list code)
    final_price = price * (1 - discount)
    return final_price

# pdb commands cơ bản:
# n → next line (không step vào function)
# s → step into (bước vào function)
# c → continue (chạy đến breakpoint tiếp theo)
# p <expr> → print expression
# pp <expr> → pretty-print
# l → list source code quanh vị trí hiện tại
# q → quit debugger
# w → where (print call stack)
# b 42 → set breakpoint tại line 42
```

```python
# icecream — debug nhanh hơn print()
# uv add icecream
from icecream import ic

def process_user(user_id: int, data: dict) -> dict:
    result = {"id": user_id}
    ic(user_id)          # In: ic| user_id: 42
    ic(data)             # In: ic| data: {'name': 'Alice', 'age': 30}
    result["name"] = data["name"].upper()
    ic(result)           # In: ic| result: {'id': 42, 'name': 'ALICE'}
    return result

# So sánh với NodeJS:
# console.log("user_id:", user_id)  →  ic(user_id)
# console.log("data:", JSON.stringify(data))  →  ic(data)
# ic() tự in tên variable — không cần viết label thủ công
```

```python
# VS Code debugger — launch.json
# Tạo .vscode/launch.json:
# {
#   "version": "0.2.0",
#   "configurations": [
#     {
#       "name": "Python: Current File",
#       "type": "debugpy",
#       "request": "launch",
#       "program": "${file}",
#       "console": "integratedTerminal"
#     },
#     {
#       "name": "Python: FastAPI",
#       "type": "debugpy",
#       "request": "launch",
#       "module": "uvicorn",
#       "args": ["main:app", "--reload"],
#       "jinja": true
#     }
#   ]
# }

# Khi debug: click vào margin bên trái để set breakpoint
# F5: Start debugging, F10: Step Over, F11: Step Into, Shift+F11: Step Out
```

> **Progression tốt nhất**: `print()` → `ic()` → `breakpoint()` → VS Code debugger
> - `print()`: OK cho quick check
> - `ic()`: debug nhanh hơn, tự in tên variable
> - `breakpoint()`: khi cần inspect state phức tạp, multi-variable
> - VS Code debugger: khi cần step through và watch variables visually

## 📝 Tóm tắt

- **pyenv/asdf/uv python** = nhóm công cụ pin Python runtime; pyenv quen thuộc nhưng không bắt buộc
- **uv** = npm thế hệ mới: nhanh, hiện đại, quản lý `.venv` và lock file → dùng cho projects mới
- **Poetry** = npm truyền thống: mature → thường gặp trong projects cũ
- **Virtual env** ≠ node_modules: env nằm riêng biệt, dùng `uv run` hoặc `poetry run`
- **pyproject.toml** = package.json: cấu hình toàn bộ project Python
- **ruff** = ESLint + Prettier cho Python: linting + formatting trong một tool
- Bật **mypy strict** và **pre-commit** từ ngày đầu để tiết kiệm technical debt
