# Bài Tập — Ngày 01: Môi trường & Tooling

## Bài 1 — Setup môi trường cơ bản (Cơ bản)

**Mô tả:** Thiết lập môi trường Python development đầy đủ trên máy tính.

**Yêu cầu:**
1. Chọn Python **3.12.x** cho project bằng `uv python`, `pyenv`, hoặc tool chuẩn của team
2. Tạo project mới: `uv init hello-python`
3. Thêm package `rich` (library print đẹp trong terminal)
4. Viết `main.py` in ra "Hello from Python!" với màu xanh dùng `rich`
5. Chạy với `uv run python main.py`

**Expected project state:**
```
hello-python/
├── .python-version      # 3.12 hoặc 3.12.x team pin
├── .venv/               # local only, không commit
├── main.py
├── pyproject.toml       # requires-python = ">=3.12,<3.13"
└── uv.lock
```

**Expected output:**
```
Hello from Python!  ← màu xanh trong terminal
```

**Hint:**
```python
from rich.console import Console

console = Console()
console.print("[green]Hello from Python![/green]")
console.print(f"[bold blue]Python version:[/bold blue] {__import__('sys').version}")
```

---

## Bài 2 — Cấu hình linting và formatting (Trung bình)

**Mô tả:** Setup môi trường development với linting và formatting tự động.

**Yêu cầu:**
1. Tạo project mới với uv
2. Thêm dev dependencies: `ruff`, `mypy`
3. Cấu hình ruff trong `pyproject.toml` (line-length=88, select E,F,I,UP)
4. Viết file `bad_code.py` với các vấn đề sau (cố tình viết xấu):
   - Import không dùng (`import os`, `import json`)
   - Function không có type hints
   - Khoảng trắng thừa
   - Import không đúng thứ tự (stdlib sau third-party)
5. Chạy `uv run ruff check bad_code.py` → xem lỗi
6. Chạy `uv run ruff check --fix bad_code.py` → auto-fix
7. Chạy `uv run mypy bad_code.py` → xem type errors

**File bad_code.py để test:**
```python
import os
import sys
import json

x = 1
y = "hello"

def add(a,b):
    return a+b

def greet(name):
    return "Hello " + name

result = greet(123)  # mypy sẽ catch lỗi này nếu có type hints
print(result)
```

**Expected:**
- ruff báo lỗi imports, missing whitespace, unused imports
- Sau `--fix`: imports được sắp xếp, unused imports removed
- mypy báo lỗi thiếu type annotations (sau khi thêm `--strict`)

---

## Bài 3 — Pre-commit workflow hoàn chỉnh (Nâng cao)

**Mô tả:** Setup pre-commit workflow giống production team thực tế.

**Yêu cầu:**
1. Tạo Git repository mới (`git init`)
2. Thêm `pre-commit` vào dev dependencies: `uv add --dev pre-commit`
3. Setup pre-commit với hooks: ruff, mypy, trailing-whitespace, end-of-file-fixer
4. Viết file Python với type hints đúng và commit thành công
5. Thêm file có lỗi type:
   ```python
   def multiply(a: int, b: int) -> int:
       return a * b

   result: str = multiply(3, 4)  # TypeError: assigning int to str
   print(result)
   ```
6. Thử `git commit` → verify pre-commit blocks commit
7. Fix lỗi và commit thành công
8. Kiểm tra `git log` để thấy commit history

**Expected:**
```
$ git commit -m "add buggy code"
mypy....................................................................Failed
- hook id: mypy
- exit code: 1

error: Incompatible types in assignment (expression has type "int", variable has type "str")
Found 1 error in 1 file
```

**Sau khi fix:**
```
$ git commit -m "add correct code"
ruff....................................................................Passed
mypy....................................................................Passed
[main abc1234] add correct code
```

---

## Bài 4 — Debug bug với breakpoint và pdb (Debug)

**Mô tả:** Cho sẵn một function tính discount bị sai logic. Dùng `breakpoint()` hoặc VS Code debugger để inspect từng biến và sửa bug, không đoán bằng mắt.

**Yêu cầu:**
1. Tạo file `debug_discount.py`
2. Cài `icecream` nếu muốn log nhanh: `uv add --dev icecream`
3. Thêm `breakpoint()` trước dòng tính `final_price`
4. Chạy `uv run python debug_discount.py`
5. Trong pdb, dùng tối thiểu các lệnh: `n`, `p user_level`, `p discount`, `l`, `c`
6. Sửa bug, rồi xóa/comment `breakpoint()` trước lần chạy cuối để tất cả assertions pass

**Code ban đầu:**
```python
def calculate_discount(price: float, user_level: str) -> float:
    discount = 0.0
    if user_level == "gold":
        discount = 0.20
    if user_level == "silver":
        discount = 0.10
    else:
        discount = 0.05

    breakpoint()
    final_price = price * (1 - discount)
    return round(final_price, 2)


assert calculate_discount(100.0, "gold") == 80.0
assert calculate_discount(100.0, "silver") == 90.0
assert calculate_discount(100.0, "guest") == 95.0
print("All discount tests passed")
```

**Expected output sau khi fix:**
```text
All discount tests passed
```

**Hint:** Bug nằm ở control flow: với `"gold"`, branch `else` đang gắn với `if user_level == "silver"` chứ không gắn với toàn bộ chain. Dùng `elif` để chỉ một branch chạy.

## 🔍 Gợi ý kiểm tra kết quả

```bash
# Verify Python version
uv run python --version  # phải là 3.12.x

# Verify đang dùng virtualenv (không phải system Python)
uv run python -c "import sys; print(sys.executable)"  # phải trỏ tới .venv/.../python

# Verify uv hoạt động
uv --version
uv lock
uv sync --locked
uv pip list  # xem packages đã cài trong môi trường project

# Verify ruff hoạt động
uv run ruff --version
uv run ruff check .  # check toàn bộ project

# Verify mypy hoạt động
uv run mypy --version
uv run mypy --strict src/

# Verify pre-commit hoạt động
uv run pre-commit run --all-files
```
