# Tài Liệu Tham Khảo — Ngày 06: Modules, Packages & Project Structure

## 📚 Official Docs

- **Python Modules**: https://docs.python.org/3/tutorial/modules.html
- **Import System**: https://docs.python.org/3/reference/import.html
- **`importlib`**: https://docs.python.org/3/library/importlib.html
- **PEP 328 — Relative Imports**: https://peps.python.org/pep-0328/
- **PEP 366 — `__package__`**: https://peps.python.org/pep-0366/
- **PEP 517/518 — Build system (pyproject.toml)**: https://peps.python.org/pep-0517/
- **PEP 621 — Project metadata in pyproject.toml**: https://peps.python.org/pep-0621/
- **Packaging User Guide**: https://packaging.python.org/en/latest/

## 🔧 Tools / Libraries

- **uv**: https://docs.astral.sh/uv/
  - Extremely fast Python package manager
  - `uv init`, `uv add`, `uv run`, `uv sync`
- **ruff**: https://docs.astral.sh/ruff/
  - Fast Python linter và formatter (Rust-based)
  - Replaces: flake8, isort, black, pylint
- **mypy**: https://mypy.readthedocs.io/en/stable/
  - Static type checker
  - `mypy --strict src/`
- **structlog**: https://www.structlog.org/en/stable/
  - Structured logging library
  - Docs rất tốt: https://www.structlog.org/en/stable/getting-started.html
- **pytest**: https://docs.pytest.org/en/latest/
- **typer**: https://typer.tiangolo.com/
  - CLI framework dựa trên type hints

## 📝 Articles / Blog Posts

- **FastAPI Full Stack**: https://github.com/tiangolo/full-stack-fastapi-template
- **Python Project Template (Cookiecutter)**: https://github.com/audreyfeldroy/cookiecutter-pypackage
- **Hypermodern Python (Claudio Jolowicz)**: https://cjolowicz.github.io/posts/hypermodern-python-01-setup/
  - Series bài viết về modern Python tooling

- **Real Python — Python Packages**: https://realpython.com/python-modules-packages/
- **Real Python — Python Application Layouts**: https://realpython.com/python-application-layouts/
- **Src Layout vs Flat Layout**: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- **Python Packaging Tutorial**: https://packaging.python.org/en/latest/tutorials/packaging-projects/
- **structlog Getting Started**: https://www.structlog.org/en/stable/getting-started.html
- **structlog with FastAPI**: https://www.structlog.org/en/stable/frameworks.html
- **Hypermodern Python**: https://cjolowicz.github.io/posts/hypermodern-python-01-setup/

## 🎥 Video / Courses

- **ArjanCodes — How to Structure a Python Project**: https://www.youtube.com/watch?v=mQAzBqxeHEU
- **ArjanCodes — Python Project Setup**: https://www.youtube.com/watch?v=Kj85ZbBVANI
- **mCoding — Python Project Structure**: https://www.youtube.com/watch?v=DhUpxWjOhME
- **Tech With Tim — Python Package Tutorial**: https://www.youtube.com/watch?v=GxCXiSkm6no

## 💡 Ghi chú thêm

- Dùng `uv add <package>` cho runtime dependencies và `uv add --dev <package>` cho tooling/test dependencies.
- Commit `uv.lock` với application projects để môi trường học và CI reproduce được.
- `src/` layout giúp phát hiện lỗi import sớm vì code chạy giống package đã install hơn flat layout.

## Import System Cheat Sheet

```python
# Absolute import (preferred)
from myapp.models.user import User
import myapp.utils.helpers

# Relative import (chỉ dùng trong package)
from . import sibling_module          # Same package
from .sibling import SomeClass        # Same package
from ..parent_module import Something # Parent package
from ..sibling.other import Thing     # Parent's sibling

# Conditional import (fallback)
try:
    import ujson as json
except ImportError:
    import json

# Type-checking only import (no runtime cost)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from myapp.models import HeavyModel

# Dynamic import
import importlib
module = importlib.import_module("myapp.plugins.csv_plugin")

# __all__ in __init__.py
__all__ = ["PublicClass", "public_function"]
# Không export: _internal_helper, _PrivateClass
```

## pyproject.toml Quick Reference

```toml
[project]
name = "myproject"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.111", "pydantic>=2.7"]

[project.scripts]
myapp = "myapp.main:main"     # CLI entry point

[dependency-groups]
dev = ["pytest", "ruff", "mypy"]

[tool.uv]
default-groups = ["dev"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## NodeJS → Python Module Equivalents

| NodeJS | Python |
|--------|--------|
| `package.json` | `pyproject.toml` |
| `npm install` | `uv add` / `pip install` |
| `npm run build` | `uv run python -m build` |
| `npm publish` | `uv publish` / `twine upload` |
| `node_modules/` | `.venv/` |
| `index.ts` (barrel) | `__init__.py` |
| `export { Foo }` | Anything at module top-level |
| `export default Foo` | Không có; dùng tên rõ ràng |
| `import { Foo } from './foo'` | `from .foo import Foo` |
| `import * as utils from './utils'` | `import utils` |
| `require('./plugin')` | `importlib.import_module('plugin')` |
| `.eslintrc.json` | `[tool.ruff]` trong pyproject.toml |
| `jest.config.js` | `[tool.pytest.ini_options]` |
| `tsconfig.json` | `[tool.mypy]` |
| `pino` / `winston` | `structlog` |
| `AsyncLocalStorage` | `contextvars.ContextVar` |
