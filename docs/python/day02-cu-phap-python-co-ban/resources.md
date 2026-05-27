# Tài Liệu Tham Khảo — Ngày 02: Python Syntax Cơ Bản

## 📚 Official Docs

- **Python Built-in Types** — https://docs.python.org/3/library/stdtypes.html — String methods, list methods đầy đủ
- **f-strings spec** — https://docs.python.org/3/reference/lexical_analysis.html#f-strings — Format mini-language
- **match/case** — https://docs.python.org/3/reference/compound_stmts.html#match — Structural pattern matching PEP 634
- **typing module** — https://docs.python.org/3/library/typing.html — Type hints reference
- **re module** — https://docs.python.org/3/library/re.html — Regular expressions, raw string examples, flags
- **unicodedata** — https://docs.python.org/3/library/unicodedata.html — Unicode normalization khi xử lý text user nhập
- **Unicode HOWTO** — https://docs.python.org/3/howto/unicode.html — Nền tảng để hiểu text có dấu, combining marks, normalization

## 🎥 Video / Courses

- **"Python Match Statement"** - Arjan Codes (YouTube) — Deep dive match/case với real examples
- **"Python Type Hints"** - mCoding (YouTube) — Hiểu type system Python
- **"Python Comprehensions"** - Corey Schafer (YouTube) — List/dict/set/generator comprehensions

## 📝 Articles / Blog Posts

- **"Python f-strings are awesome"** — realpython.com — Tất cả f-string format specs
- **"Python's match Statement: A Practical Guide"** — realpython.com
- **"Type Hints Cheat Sheet"** — mypy.readthedocs.io/en/stable/cheat_sheet_py3.html

## 🔧 Tools / Libraries

- **mypy** — static type checker
- **rich** — beautiful terminal output với colors, tables

## 💡 Ghi chú thêm

- **Python 3.10+ features** (match/case, `int | str`) cần Python >= 3.10 — verify với pyenv
- **Walrus operator** `:=` (Python 3.8+): `if (n := len(data)) > 10: print(f"Too long: {n}")` — assign và check cùng lúc
- **Type narrowing**: sau `if isinstance(x, str):`, mypy biết `x` là `str` trong block đó
- **`TypeAlias`** (3.10+): `UserId: TypeAlias = int` — đặt tên cho type
- `*` trong function signature: tất cả params sau `*` là keyword-only — đây là pattern quan trọng trong production APIs
- **Regex raw strings**: pattern nên viết `r"\d+"`, không viết `"\d+"`; nếu text có dấu/Unicode, normalize trước khi compare hoặc dedupe
