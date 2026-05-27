# Các “bẫy” Python nên học sớm

Đây là danh sách các lỗi/bẫy Python thường gặp, đặc biệt hữu ích nếu bạn đã biết một ngôn ngữ lập trình khác và đang học Python.

---

## 1. Mutable default argument

Đây là bẫy kinh điển nhất.

Sai:

```python
def add_item(item, items=[]):
    items.append(item)
    return items

print(add_item("a"))  # ['a']
print(add_item("b"))  # ['a', 'b']  <-- bất ngờ
```

Bạn tưởng `items=[]` được tạo mới mỗi lần gọi hàm, nhưng thực ra nó được tạo **một lần duy nhất khi hàm được định nghĩa**.

Đúng:

```python
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

Quy tắc nhớ:

```text
Không dùng list/dict/set làm default argument.
Dùng None rồi khởi tạo bên trong hàm.
```

---

## 2. Gán biến không copy object

Trong Python, biến thường là **reference tới object**, không phải bản copy.

```python
a = [1, 2, 3]
b = a

b.append(4)

print(a)  # [1, 2, 3, 4]
```

`a` và `b` đang trỏ tới cùng một list.

Muốn copy:

```python
a = [1, 2, 3]
b = a.copy()

b.append(4)

print(a)  # [1, 2, 3]
print(b)  # [1, 2, 3, 4]
```

Nhưng lưu ý: `.copy()` là **shallow copy**.

```python
a = [[1, 2], [3, 4]]
b = a.copy()

b[0].append(99)

print(a)  # [[1, 2, 99], [3, 4]]
```

Với object lồng nhau, dùng:

```python
import copy

b = copy.deepcopy(a)
```

---

## 3. `is` khác `==`

`==` so sánh **giá trị**.  
`is` so sánh **có phải cùng một object trong memory không**.

```python
a = [1, 2]
b = [1, 2]

print(a == b)  # True
print(a is b)  # False
```

Dùng `is` chủ yếu cho:

```python
x is None
x is True
x is False
```

Không nên viết:

```python
if x == None:
    ...
```

Nên viết:

```python
if x is None:
    ...
```

---

## 4. Scope trong function dễ gây nhầm

Ví dụ:

```python
count = 0

def increment():
    count += 1
    return count
```

Code này lỗi:

```text
UnboundLocalError
```

Vì khi bạn gán `count += 1`, Python hiểu `count` là biến local trong function. Nhưng trước đó nó chưa được khởi tạo trong function.

Cách sửa:

```python
count = 0

def increment():
    global count
    count += 1
    return count
```

Nhưng trong code sạch, nên hạn chế `global`. Tốt hơn:

```python
def increment(count):
    return count + 1

count = 0
count = increment(count)
```

Hoặc dùng class/state object nếu cần quản lý trạng thái.

---

## 5. List comprehension có thể tạo side effect khó đọc

Dùng list comprehension để tạo list thì tốt:

```python
squares = [x * x for x in range(5)]
```

Nhưng đừng dùng nó chỉ để gọi function có side effect:

```python
[print(x) for x in range(5)]
```

Nên viết:

```python
for x in range(5):
    print(x)
```

Quy tắc:

```text
List comprehension dùng khi bạn cần kết quả list.
For loop dùng khi bạn cần thực hiện hành động.
```

---

## 6. `for else` không giống nhiều người tưởng

Python có `else` sau vòng lặp:

```python
for item in items:
    if item == target:
        print("Found")
        break
else:
    print("Not found")
```

`else` chạy khi vòng lặp **không bị break**.

Nó không có nghĩa là “nếu vòng for không chạy”. Đây là điểm rất dễ hiểu nhầm.

---

## 7. Exception quá rộng làm che lỗi thật

Sai:

```python
try:
    result = risky_operation()
except:
    pass
```

Cái này nguy hiểm vì nó nuốt mọi lỗi, kể cả bug nghiêm trọng.

Tốt hơn:

```python
try:
    result = int("abc")
except ValueError:
    print("Invalid number")
```

Hoặc ít nhất:

```python
try:
    result = risky_operation()
except Exception as e:
    print(f"Error: {e}")
```

Nhưng khi code production, nên bắt đúng loại exception càng cụ thể càng tốt.

---

## 8. `dict.get()` và giá trị mặc định

Nhiều người viết:

```python
name = user["name"]
```

Nếu key không tồn tại, sẽ lỗi `KeyError`.

Dùng:

```python
name = user.get("name")
```

Hoặc:

```python
name = user.get("name", "Unknown")
```

Nhưng cẩn thận với dữ liệu phân biệt giữa “không có key” và “key có giá trị None”.

```python
user = {"name": None}

print(user.get("name", "Unknown"))  # None
```

Nếu muốn kiểm tra key có tồn tại thật không:

```python
if "name" in user:
    ...
```

---

## 9. Truthy / falsy dễ gây bug

Trong Python, các giá trị sau được xem là `False`:

```python
None
False
0
0.0
""
[]
{}
set()
```

Ví dụ bug:

```python
age = 0

if not age:
    print("No age")
```

Nhưng `0` có thể là giá trị hợp lệ.

Tốt hơn:

```python
if age is None:
    print("No age")
```

Quy tắc:

```text
Nếu muốn kiểm tra thiếu dữ liệu: dùng is None.
Nếu muốn kiểm tra rỗng: dùng if not list/string/dict.
```

---

## 10. Import path và circular import

Ví dụ:

```text
project/
  main.py
  user.py
  order.py
```

Nếu `user.py` import `order.py`, rồi `order.py` lại import `user.py`, có thể gây lỗi circular import.

```python
# user.py
from order import Order

# order.py
from user import User
```

Cách tránh:

```text
Tách phần dùng chung ra file riêng
Tránh import lẫn nhau giữa 2 module ngang cấp
Đưa import vào trong function nếu thật sự cần
Thiết kế lại dependency direction
```

Ví dụ:

```text
models/
  user.py
  order.py
  common.py
```

---

## 11. Virtual environment và package manager

Python rất dễ loạn môi trường nếu bạn không quản lý venv.

Không nên cài bừa bằng:

```bash
pip install something
```

mà không biết đang cài vào đâu.

Nên luôn kiểm tra:

```bash
which python
which pip
python --version
pip --version
```

Nếu bạn dùng `uv`, flow gọn hơn:

```bash
uv init
uv add requests
uv run python main.py
```

Hoặc chạy script:

```bash
uv run main.py
```

Tư duy đúng:

```text
Mỗi project có môi trường riêng.
Không cài package lung tung vào Python global.
```

---

## 12. Indentation là syntax, không phải style

Python dùng indentation để xác định block.

Sai:

```python
if True:
print("hello")
```

Đúng:

```python
if True:
    print("hello")
```

Nên dùng formatter như `ruff format` hoặc `black`.

Với VSCode, nên bật format on save để tránh lỗi lặt vặt.

---

## 13. `lambda` không phải thay thế function bình thường

Dùng được:

```python
items = [1, 2, 3]
squares = list(map(lambda x: x * x, items))
```

Nhưng trong Python, thường đọc dễ hơn nếu viết:

```python
squares = [x * x for x in items]
```

Nếu logic phức tạp, dùng function thật:

```python
def calculate_score(user):
    return user["age"] * 2 + user["level"]

users.sort(key=calculate_score)
```

Quy tắc:

```text
lambda chỉ nên dùng cho logic rất ngắn.
```

---

## 14. Class variable và instance variable

Bẫy này khá giống mutable default argument.

Sai:

```python
class User:
    tags = []

    def add_tag(self, tag):
        self.tags.append(tag)

u1 = User()
u2 = User()

u1.add_tag("admin")

print(u2.tags)  # ['admin']  <-- bất ngờ
```

`tags` là class variable, được share giữa các instance.

Đúng:

```python
class User:
    def __init__(self):
        self.tags = []

    def add_tag(self, tag):
        self.tags.append(tag)
```

Quy tắc:

```text
Dữ liệu riêng từng object đặt trong self.
Dữ liệu chung cho cả class mới đặt ở class level.
```

---

## 15. Dataclass với mutable default

Sai:

```python
from dataclasses import dataclass

@dataclass
class User:
    tags: list = []
```

Sẽ lỗi hoặc gây vấn đề vì list là mutable default.

Đúng:

```python
from dataclasses import dataclass, field

@dataclass
class User:
    tags: list = field(default_factory=list)
```

Cái này rất nên nhớ nếu bạn dùng Python hiện đại.

---

## 16. Float không chính xác tuyệt đối

```python
print(0.1 + 0.2)  # 0.30000000000000004
```

Không phải lỗi riêng Python, mà là cách số thực được biểu diễn trong máy tính.

Nếu làm tiền tệ, không dùng float:

```python
from decimal import Decimal

price = Decimal("0.1") + Decimal("0.2")
print(price)  # 0.3
```

---

## 17. GIL và đa luồng

Python có GIL, nên `threading` không giúp tăng tốc tốt cho tác vụ CPU-heavy.

Ví dụ CPU-heavy:

```text
xử lý ảnh lớn
tính toán số học nhiều
nén/giải nén lớn
machine learning thuần CPU
```

Với CPU-heavy, cân nhắc:

```text
multiprocessing
native library như NumPy
Rust/C extension
job queue
```

Với I/O-heavy, thread hoặc async vẫn hữu ích:

```text
gọi API
đọc ghi file
network
database
web scraping
```

---

## 18. Async không tự làm code nhanh hơn

Nhiều người mới Python thấy `async/await` tưởng là cứ dùng sẽ nhanh.

Không đúng.

`async` hữu ích khi bạn có nhiều tác vụ I/O chờ đợi:

```text
gọi nhiều API cùng lúc
websocket
server nhiều connection
crawler
```

Không hữu ích nhiều cho CPU-heavy.

Sai tư duy:

```text
Code chậm → thêm async
```

Đúng hơn:

```text
Chậm vì chờ network/database nhiều → async có thể giúp.
Chậm vì tính toán nặng → async thường không giúp.
```

---

## 19. `type hint` không tự kiểm tra lúc runtime

Ví dụ:

```python
def add(a: int, b: int) -> int:
    return a + b

print(add("1", "2"))  # "12"
```

Python vẫn chạy, vì type hint chủ yếu phục vụ IDE, static checker, readability.

Muốn check type, dùng công cụ như:

```text
mypy
pyright
basedpyright
pydantic
```

Với project thực tế, type hint vẫn rất đáng dùng vì giúp bạn code nhanh và ít lỗi hơn trong VSCode.

---

## 20. Python code “chạy được” chưa chắc là Pythonic

Ví dụ:

```python
items = [1, 2, 3]

for i in range(len(items)):
    print(items[i])
```

Chạy được, nhưng không Pythonic.

Nên viết:

```python
for item in items:
    print(item)
```

Nếu cần index:

```python
for index, item in enumerate(items):
    print(index, item)
```

Nếu cần duyệt 2 list cùng lúc:

```python
names = ["A", "B"]
ages = [20, 30]

for name, age in zip(names, ages):
    print(name, age)
```

---

# Thứ tự nên học các bẫy Python

Với developer đang học Python, nên ưu tiên như này:

```text
1. mutable default argument
2. reference/copy/deepcopy
3. is vs ==
4. truthy/falsy và None
5. exception handling
6. import path + virtual environment
7. class variable vs instance variable
8. dataclass default_factory
9. type hint không check runtime
10. async/GIL/threading
```

Bạn không cần học hết trong một ngày. Nhưng nên biết sớm để khi gặp bug còn nhận ra: “À, đây là bẫy Python chứ không phải mình ngu.”
