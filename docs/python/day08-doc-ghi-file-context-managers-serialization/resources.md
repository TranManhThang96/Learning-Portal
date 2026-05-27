# Tài Liệu Tham Khảo — Ngày 08: File I/O, Context Managers & Serialization

## 📚 Official Docs

- **pathlib** — https://docs.python.org/3/library/pathlib.html — Path object API đầy đủ
- **contextlib** — https://docs.python.org/3/library/contextlib.html — @contextmanager, suppress, ExitStack
- **json module** — https://docs.python.org/3/library/json.html — Encoding/decoding, custom encoders
- **csv module** — https://docs.python.org/3/library/csv.html — DictReader, DictWriter
- **tomllib** (3.11+) — https://docs.python.org/3/library/tomllib.html — TOML parsing
- **Pydantic v2 docs** — https://docs.pydantic.dev/latest/ — Field, validators, model_config
- **Pydantic Settings** — https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — BaseSettings, SettingsConfigDict, env_file

## 🎥 Video / Courses

- **"Pydantic v2 Tutorial"** - Arjan Codes (YouTube) — Migration từ v1, new validators
- **"Python Context Managers"** - Corey Schafer (YouTube) — class-based và @contextmanager
- **"pathlib Tutorial"** - mCoding (YouTube) — Modern file operations

## 📝 Articles / Blog Posts

- **"Working with Files in Python"** — realpython.com — pathlib vs os.path comparison
- **"Python Context Managers and the 'with' Statement"** — realpython.com
- **"Pydantic v2: Migration Guide"** — docs.pydantic.dev — v1 → v2 changes

## 🔧 Tools / Libraries

- **pydantic** — docs.pydantic.dev — Data validation (core của FastAPI)
- **pydantic-settings** — docs.pydantic.dev — Load configuration từ environment và `.env`
- **pyyaml** — pyyaml.org — YAML parsing (nhớ dùng `safe_load`)
- **tomli** — github.com/hukkin/tomli — TOML parsing cho Python < 3.11
- **tomli-w** — github.com/hukkin/tomli-w — TOML writing
- **orjson** — github.com/ijl/orjson — Fastest JSON library (Rust), hỗ trợ datetime, numpy
- **ujson** — github.com/ultrajson/ultrajson — Fast JSON alternative

## 💡 Ghi chú thêm

- **Pydantic v2 breaking changes từ v1**: `@validator` → `@field_validator`, `.dict()` → `.model_dump()`, `.json()` → `.model_dump_json()`, `.parse_obj()` → `.model_validate()`
- **`orjson`** nhanh hơn `json` built-in ~3-10x và tự động serialize datetime — dùng trong high-throughput APIs
- **Security**: `yaml.load()` có thể execute arbitrary Python code — LUÔN dùng `yaml.safe_load()`
- **`pathlib.Path.resolve()`**: convert relative path thành absolute, resolve symlinks
- **Path traversal**: với filename/path từ user, dùng `Path.resolve()` và kiểm tra `candidate.is_relative_to(base_dir)` trước khi đọc/ghi file
- **Pydantic `model_config = {"frozen": True}`**: immutable model — objects không thể bị modify sau khi tạo
