# Ngày 05: Exercises — OOP trong Python

## Scope & cách chạy

Trong 2 giờ, làm **Bài 1** là đủ để luyện dunder methods và class design. **Bài 2** là **Optional Reference** cho ABC/registry. **Bài 3** là **Optional Reference** vì kéo thêm Observer pattern, typing nâng cao và thread-safety.

Setup nhanh:

```bash
uv init day05-oop
cd day05-oop
uv add --dev mypy ruff
```

Mỗi bài nên đặt vào một file riêng:

| Bài | File gợi ý | Command |
|-----|------------|---------|
| 1 | `vector2d.py` | `uv run python vector2d.py` |
| 2 optional | `exporters.py` | `uv run python exporters.py` |
| 3 optional | `event_emitter.py` | `uv run python event_emitter.py` |

## Bài 1: Implement Vector2D

**Mô tả:** Implement class `Vector2D` đầy đủ với operator overloading, cho phép viết code mathematical expressions tự nhiên như `v1 + v2`, `v * 3`, `abs(v)`.

**Yêu cầu implement:**
- `__init__(x, y)` — khởi tạo vector
- `__add__(other)` — cộng vector: `v1 + v2`
- `__sub__(other)` — trừ vector: `v1 - v2`
- `__mul__(scalar)` — nhân với scalar: `v * 3`
- `__rmul__(scalar)` — nhân ngược: `3 * v`
- `__truediv__(scalar)` — chia: `v / 2`
- `__neg__()` — đảo dấu: `-v`
- `__abs__()` — magnitude/length: `abs(v)`
- `__eq__(other)` — equality: `v1 == v2`
- `__hash__()` — hashable (dùng trong set/dict)
- `__repr__()` — `Vector2D(3.0, 4.0)`
- `__str__()` — `(3.00, 4.00)`
- `__iter__()` — `x, y = v` (unpacking)
- `__len__()` — luôn trả về 2 (2D vector)
- `__getitem__(index)` — `v[0]` → x, `v[1]` → y
- `dot(other)` — dot product
- `normalize()` — unit vector
- `angle_to(other)` — góc giữa 2 vectors (radians)
- `rotate(angle)` — xoay vector (radians)
- Acceptance: `uv run python vector2d.py` chạy toàn bộ `unittest` pass

**Starter code:**

```python
from __future__ import annotations

import math
from typing import Iterator


class Vector2D:
    """
    2D Vector với full operator overloading.

    Usage:
        v1 = Vector2D(3, 4)
        v2 = Vector2D(1, 2)

        v3 = v1 + v2        # Vector2D(4.0, 6.0)
        v4 = v1 * 2         # Vector2D(6.0, 8.0)
        v5 = 2 * v1         # Vector2D(6.0, 8.0) — via __rmul__
        magnitude = abs(v1) # 5.0

        x, y = v1           # Unpacking via __iter__
        print(v1[0])        # 3.0 — via __getitem__
    """

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)

    # TODO: Implement all required methods

    def dot(self, other: Vector2D) -> float:
        """Dot product: v1 · v2 = x1*x2 + y1*y2"""
        # TODO
        pass

    def normalize(self) -> Vector2D:
        """Unit vector với magnitude = 1."""
        # TODO: Handle zero vector case
        pass

    def angle_to(self, other: Vector2D) -> float:
        """
        Góc giữa 2 vectors tính bằng radians.
        Formula: cos(θ) = (v1 · v2) / (|v1| * |v2|)
        """
        # TODO
        pass

    def rotate(self, angle: float) -> Vector2D:
        """
        Xoay vector ngược chiều kim đồng hồ.
        Formula:
            x' = x*cos(θ) - y*sin(θ)
            y' = x*sin(θ) + y*cos(θ)
        """
        # TODO
        pass


# ============================================================
# Tests — tất cả phải pass
# ============================================================

import unittest


class TestVector2D(unittest.TestCase):

    def test_init(self):
        v = Vector2D(3, 4)
        self.assertEqual(v.x, 3.0)
        self.assertEqual(v.y, 4.0)

    def test_add(self):
        v1 = Vector2D(1, 2)
        v2 = Vector2D(3, 4)
        result = v1 + v2
        self.assertEqual(result, Vector2D(4, 6))

    def test_sub(self):
        v1 = Vector2D(5, 7)
        v2 = Vector2D(2, 3)
        self.assertEqual(v1 - v2, Vector2D(3, 4))

    def test_mul_scalar(self):
        v = Vector2D(2, 3)
        self.assertEqual(v * 2, Vector2D(4, 6))

    def test_rmul_scalar(self):
        v = Vector2D(2, 3)
        self.assertEqual(3 * v, Vector2D(6, 9))

    def test_truediv(self):
        v = Vector2D(4, 6)
        self.assertEqual(v / 2, Vector2D(2, 3))

    def test_neg(self):
        v = Vector2D(3, -4)
        self.assertEqual(-v, Vector2D(-3, 4))

    def test_abs_magnitude(self):
        v = Vector2D(3, 4)
        self.assertAlmostEqual(abs(v), 5.0)

    def test_eq(self):
        v1 = Vector2D(1, 2)
        v2 = Vector2D(1, 2)
        v3 = Vector2D(1, 3)
        self.assertEqual(v1, v2)
        self.assertNotEqual(v1, v3)

    def test_hash(self):
        """Vector2D có thể dùng trong set và dict."""
        v1 = Vector2D(1, 2)
        v2 = Vector2D(1, 2)
        v3 = Vector2D(3, 4)
        s = {v1, v2, v3}
        self.assertEqual(len(s), 2)  # v1 và v2 là cùng vector

    def test_repr(self):
        v = Vector2D(3, 4)
        self.assertEqual(repr(v), "Vector2D(3.0, 4.0)")

    def test_str(self):
        v = Vector2D(3, 4)
        self.assertEqual(str(v), "(3.00, 4.00)")

    def test_iter_unpacking(self):
        v = Vector2D(3, 4)
        x, y = v  # Sử dụng __iter__
        self.assertEqual(x, 3.0)
        self.assertEqual(y, 4.0)

    def test_len(self):
        v = Vector2D(1, 2)
        self.assertEqual(len(v), 2)

    def test_getitem(self):
        v = Vector2D(3, 4)
        self.assertEqual(v[0], 3.0)
        self.assertEqual(v[1], 4.0)
        with self.assertRaises(IndexError):
            _ = v[2]

    def test_dot_product(self):
        v1 = Vector2D(1, 2)
        v2 = Vector2D(3, 4)
        self.assertAlmostEqual(v1.dot(v2), 11.0)  # 1*3 + 2*4

    def test_normalize(self):
        v = Vector2D(3, 4)
        n = v.normalize()
        self.assertAlmostEqual(abs(n), 1.0)
        self.assertAlmostEqual(n.x, 0.6)
        self.assertAlmostEqual(n.y, 0.8)

    def test_normalize_zero_vector(self):
        v = Vector2D(0, 0)
        with self.assertRaises(ZeroDivisionError):
            v.normalize()

    def test_angle_to(self):
        v1 = Vector2D(1, 0)  # Pointing right
        v2 = Vector2D(0, 1)  # Pointing up
        angle = v1.angle_to(v2)
        self.assertAlmostEqual(angle, math.pi / 2)  # 90 degrees

    def test_rotate(self):
        v = Vector2D(1, 0)
        rotated = v.rotate(math.pi / 2)  # 90 degrees
        self.assertAlmostEqual(rotated.x, 0, places=10)
        self.assertAlmostEqual(rotated.y, 1, places=10)

    def test_chaining(self):
        """Test method chaining và complex expressions."""
        v1 = Vector2D(1, 0)
        result = (v1.rotate(math.pi / 4) * 2).normalize()
        self.assertAlmostEqual(abs(result), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

---

## Bài 2: Plugin System với ABC và Registry (Optional)

**Mô tả:** Implement một plugin system linh hoạt sử dụng ABC và `@classmethod` registry pattern. System cho phép tự động discover và register plugins chỉ bằng cách import module.

**Scope note:** Bài này phù hợp sau khi đã nắm ABC. Không cần làm trong 2 giờ nếu Bài 1 chưa xong.

**Yêu cầu:**
- Base class `DataExporter` với `@classmethod register` và auto-registry
- Concrete plugins: `CSVExporter`, `JSONExporter`, `XMLExporter`
- `ExporterRegistry` singleton quản lý tất cả registered exporters
- Plugin discovery qua class inheritance (tự động khi define subclass)
- Type-safe factory method `get_exporter(format: str) -> DataExporter`
- Acceptance: `uv run python exporters.py` in "All tests passed!" và có output CSV/JSON/Markdown mẫu

**Starter code:**

```python
from __future__ import annotations

import csv
import json
import io
from abc import ABC, abstractmethod
from typing import ClassVar, Type, Any


class DataExporter(ABC):
    """
    Base class cho tất cả data exporters.

    Plugin registration xảy ra tự động khi subclass được define.
    Pattern này dùng __init_subclass__ hook.
    """

    # Registry lưu tất cả registered exporters
    _registry: ClassVar[dict[str, Type[DataExporter]]] = {}

    def __init_subclass__(cls, format_name: str | None = None, **kwargs) -> None:
        """
        Hook được gọi tự động khi một subclass được define.

        Usage:
            class CSVExporter(DataExporter, format_name="csv"):
                ...
        """
        super().__init_subclass__(**kwargs)
        if format_name is not None:
            # TODO: Đăng ký exporter vào registry
            pass

    @classmethod
    def get_exporter(cls, format_name: str) -> DataExporter:
        """
        Factory method: lấy exporter theo format name.

        Raises:
            ValueError: nếu format không được hỗ trợ
        """
        # TODO: Implement
        pass

    @classmethod
    def available_formats(cls) -> list[str]:
        """Trả về danh sách formats đã được register."""
        # TODO: Implement
        pass

    @abstractmethod
    def export(self, data: list[dict[str, Any]], **kwargs) -> str:
        """
        Export data ra format cụ thể.

        Args:
            data: List of dicts (rows)
            **kwargs: Format-specific options

        Returns:
            Exported content as string
        """
        ...

    @abstractmethod
    def file_extension(self) -> str:
        """Trả về file extension (e.g., '.csv', '.json')."""
        ...

    def export_to_file(self, data: list[dict[str, Any]], filepath: str, **kwargs) -> None:
        """Template method: export và lưu ra file."""
        content = self.export(data, **kwargs)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Exported {len(data)} rows to {filepath}")


# TODO: Implement các concrete exporters

class CSVExporter(DataExporter, format_name="csv"):
    """Export data sang CSV format."""

    def export(self, data: list[dict[str, Any]], **kwargs) -> str:
        """
        Args:
            delimiter: Ký tự phân cách (default: ',')
            include_header: Có include header row không (default: True)
        """
        # TODO: Implement
        pass

    def file_extension(self) -> str:
        return ".csv"


class JSONExporter(DataExporter, format_name="json"):
    """Export data sang JSON format."""

    def export(self, data: list[dict[str, Any]], **kwargs) -> str:
        """
        Args:
            indent: JSON indentation (default: 2)
            ensure_ascii: (default: False để support Unicode)
        """
        # TODO: Implement
        pass

    def file_extension(self) -> str:
        return ".json"


class MarkdownExporter(DataExporter, format_name="markdown"):
    """Export data sang Markdown table format."""

    def export(self, data: list[dict[str, Any]], **kwargs) -> str:
        """
        Output format:
        | col1 | col2 | col3 |
        |------|------|------|
        | val1 | val2 | val3 |
        """
        # TODO: Implement
        pass

    def file_extension(self) -> str:
        return ".md"


# ============================================================
# Tests
# ============================================================

sample_data = [
    {"name": "Alice", "age": 30, "city": "Hanoi"},
    {"name": "Bob", "age": 25, "city": "HCMC"},
    {"name": "Charlie", "age": 35, "city": "Da Nang"},
]


def test_registry():
    """Test auto-registration."""
    formats = DataExporter.available_formats()
    assert "csv" in formats
    assert "json" in formats
    assert "markdown" in formats
    print(f"Registered formats: {formats}")


def test_factory():
    """Test factory method."""
    exporter = DataExporter.get_exporter("csv")
    assert isinstance(exporter, CSVExporter)

    exporter = DataExporter.get_exporter("json")
    assert isinstance(exporter, JSONExporter)

    try:
        DataExporter.get_exporter("xml")
        assert False, "Should raise ValueError"
    except ValueError as e:
        print(f"Correct error: {e}")


def test_csv_export():
    exporter = DataExporter.get_exporter("csv")
    result = exporter.export(sample_data)
    print("CSV output:")
    print(result)
    # Expected:
    # name,age,city
    # Alice,30,Hanoi
    # Bob,25,HCMC
    # Charlie,35,Da Nang


def test_json_export():
    exporter = DataExporter.get_exporter("json")
    result = exporter.export(sample_data, indent=2)
    print("JSON output:")
    print(result)
    data = json.loads(result)
    assert len(data) == 3
    assert data[0]["name"] == "Alice"


def test_markdown_export():
    exporter = DataExporter.get_exporter("markdown")
    result = exporter.export(sample_data)
    print("Markdown output:")
    print(result)
    # Expected:
    # | name | age | city |
    # |------|-----|------|
    # | Alice | 30 | Hanoi |
    # ...


def test_adding_new_exporter():
    """
    Test thêm exporter mới — chỉ cần define subclass,
    không cần sửa code hiện tại.
    """
    class TSVExporter(DataExporter, format_name="tsv"):
        def export(self, data: list[dict], **kwargs) -> str:
            if not data:
                return ""
            headers = list(data[0].keys())
            lines = ["\t".join(headers)]
            for row in data:
                lines.append("\t".join(str(row[h]) for h in headers))
            return "\n".join(lines)

        def file_extension(self) -> str:
            return ".tsv"

    assert "tsv" in DataExporter.available_formats()
    exporter = DataExporter.get_exporter("tsv")
    result = exporter.export(sample_data)
    print("TSV output:")
    print(result)


if __name__ == "__main__":
    test_registry()
    test_factory()
    test_csv_export()
    test_json_export()
    test_markdown_export()
    test_adding_new_exporter()
    print("\nAll tests passed!")
```

---

## Bài 3: Observer Pattern — Event Emitter (Optional Deep Dive)

**Mô tả:** Implement Observer pattern (Event Emitter) hoàn chỉnh bằng Python classes. Đây là pattern cực kỳ quen thuộc với NodeJS developers (EventEmitter trong Node.js).

**Scope note:** Đây là bài pattern tổng hợp, không phải core OOP Day 05. `Thread-safe` và `TypedEventEmitter` là bonus; hoàn thành `on/off/once/emit` sync là đủ.

**Yêu cầu:**
- `EventEmitter` base class với `on`, `off`, `emit`, `once`
- `on(event, handler)` — đăng ký handler
- `off(event, handler)` — hủy đăng ký
- `emit(event, *args, **kwargs)` — trigger event
- `once(event, handler)` — handler chỉ chạy 1 lần rồi tự remove
- Support wildcard listeners `on("*", handler)` — lắng nghe mọi events
- Type-safe với Generic types
- Thread-safe (optional bonus)
- Acceptance: `uv run python event_emitter.py` chạy toàn bộ `unittest` pass

**Starter code:**

```python
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable, Any, Generic, TypeVar
from functools import wraps


# Type alias
EventHandler = Callable[..., None]


class EventEmitter:
    """
    Observer pattern / Event Emitter.

    NodeJS equivalent:
        const emitter = new EventEmitter();
        emitter.on('data', (payload) => console.log(payload));
        emitter.emit('data', { value: 42 });

    Python usage:
        emitter = EventEmitter()
        emitter.on('data', lambda payload: print(payload))
        emitter.emit('data', {'value': 42})
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[EventHandler]] = defaultdict(list)
        self._once_listeners: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event: str, handler: EventHandler) -> EventEmitter:
        """
        Đăng ký handler cho event.
        Returns self để support method chaining.

        Usage:
            emitter.on("click", handler1).on("click", handler2)
        """
        # TODO: Implement (thread-safe)
        pass

    def off(self, event: str, handler: EventHandler) -> EventEmitter:
        """
        Hủy đăng ký handler.
        Không raise error nếu handler không tồn tại.
        """
        # TODO: Implement
        pass

    def once(self, event: str, handler: EventHandler) -> EventEmitter:
        """
        Handler chỉ được gọi một lần, sau đó tự động unregister.
        """
        # TODO: Implement
        pass

    def emit(self, event: str, *args: Any, **kwargs: Any) -> bool:
        """
        Trigger event với arguments.

        Returns:
            True nếu có ít nhất 1 handler, False nếu không có handler nào.

        Thứ tự gọi:
        1. Regular listeners của event
        2. Once listeners của event (sau đó remove)
        3. Wildcard listeners "*"
        """
        # TODO: Implement
        pass

    def listener_count(self, event: str) -> int:
        """Số lượng listeners cho một event."""
        # TODO: Implement
        pass

    def event_names(self) -> list[str]:
        """Danh sách events đang có listeners."""
        # TODO: Implement
        pass

    def remove_all_listeners(self, event: str | None = None) -> EventEmitter:
        """
        Remove tất cả listeners.
        Nếu event=None, remove tất cả listeners của tất cả events.
        """
        # TODO: Implement
        pass


# ============================================================
# Typed Event Emitter — Advanced version
# ============================================================

from typing import TypedDict, overload


class UserCreatedEvent(TypedDict):
    user_id: str
    email: str
    name: str


class OrderPlacedEvent(TypedDict):
    order_id: str
    user_id: str
    total: float


class TypedEventEmitter(EventEmitter):
    """
    Typed EventEmitter — handlers nhận typed payloads.

    Usage:
        emitter = TypedEventEmitter()

        @emitter.on_typed("user.created")
        def handle_user_created(event: UserCreatedEvent) -> None:
            send_welcome_email(event["email"])

        emitter.emit("user.created", UserCreatedEvent(
            user_id="123", email="alice@example.com", name="Alice"
        ))
    """

    def on_typed(self, event: str) -> Callable:
        """Decorator version của on()."""
        def decorator(handler: EventHandler) -> EventHandler:
            self.on(event, handler)
            return handler
        return decorator


# ============================================================
# Concrete implementation: UserService với events
# ============================================================

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    name: str
    email: str
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()


class UserService(EventEmitter):
    """
    Service class kế thừa EventEmitter.

    Events emitted:
    - "user.created" → (user: User)
    - "user.updated" → (user: User, changes: dict)
    - "user.deleted" → (user_id: str)
    - "error" → (error: Exception)
    """

    def __init__(self) -> None:
        super().__init__()
        self._users: dict[str, User] = {}

    def create_user(self, name: str, email: str) -> User:
        user_id = f"user_{len(self._users) + 1}"
        user = User(id=user_id, name=name, email=email)
        self._users[user_id] = user

        # Emit event
        self.emit("user.created", user)
        return user

    def update_user(self, user_id: str, **changes) -> User:
        if user_id not in self._users:
            error = KeyError(f"User not found: {user_id}")
            self.emit("error", error)
            raise error

        user = self._users[user_id]
        for key, value in changes.items():
            setattr(user, key, value)

        self.emit("user.updated", user, changes)
        return user

    def delete_user(self, user_id: str) -> bool:
        if user_id not in self._users:
            return False
        del self._users[user_id]
        self.emit("user.deleted", user_id)
        return True


# ============================================================
# Tests
# ============================================================

import unittest


class TestEventEmitter(unittest.TestCase):

    def test_on_and_emit(self):
        emitter = EventEmitter()
        received = []

        emitter.on("data", lambda x: received.append(x))
        emitter.emit("data", 42)
        emitter.emit("data", "hello")

        self.assertEqual(received, [42, "hello"])

    def test_multiple_handlers(self):
        emitter = EventEmitter()
        log = []

        emitter.on("event", lambda: log.append("handler1"))
        emitter.on("event", lambda: log.append("handler2"))
        emitter.emit("event")

        self.assertEqual(log, ["handler1", "handler2"])

    def test_off(self):
        emitter = EventEmitter()
        log = []

        def handler():
            log.append("called")

        emitter.on("event", handler)
        emitter.emit("event")   # "called"
        emitter.off("event", handler)
        emitter.emit("event")   # Không gọi

        self.assertEqual(log, ["called"])

    def test_once(self):
        emitter = EventEmitter()
        count = [0]

        emitter.once("event", lambda: count.__setitem__(0, count[0] + 1))
        emitter.emit("event")  # count = 1
        emitter.emit("event")  # Không gọi
        emitter.emit("event")  # Không gọi

        self.assertEqual(count[0], 1)

    def test_wildcard_listener(self):
        emitter = EventEmitter()
        all_events = []

        emitter.on("*", lambda event, *args, **kwargs: all_events.append(event))
        emitter.emit("user.created", {"id": "1"})
        emitter.emit("order.placed", {"id": "2"})

        self.assertEqual(all_events, ["user.created", "order.placed"])

    def test_emit_returns_true_with_handlers(self):
        emitter = EventEmitter()
        emitter.on("event", lambda: None)
        self.assertTrue(emitter.emit("event"))

    def test_emit_returns_false_without_handlers(self):
        emitter = EventEmitter()
        self.assertFalse(emitter.emit("no_listeners"))

    def test_listener_count(self):
        emitter = EventEmitter()
        emitter.on("event", lambda: None)
        emitter.on("event", lambda: None)
        emitter.once("event", lambda: None)
        self.assertEqual(emitter.listener_count("event"), 3)

    def test_method_chaining(self):
        emitter = EventEmitter()
        log = []

        (emitter
            .on("a", lambda: log.append("a"))
            .on("b", lambda: log.append("b"))
            .on("a", lambda: log.append("a2"))
        )

        emitter.emit("a")
        emitter.emit("b")
        self.assertEqual(log, ["a", "a2", "b"])

    def test_user_service_events(self):
        service = UserService()
        events = []

        service.on("user.created", lambda u: events.append(("created", u.name)))
        service.on("user.updated", lambda u, c: events.append(("updated", u.name, c)))
        service.on("user.deleted", lambda uid: events.append(("deleted", uid)))

        user = service.create_user("Alice", "alice@example.com")
        service.update_user(user.id, name="Alice Smith")
        service.delete_user(user.id)

        self.assertEqual(events[0], ("created", "Alice"))
        self.assertEqual(events[1][0], "updated")
        self.assertEqual(events[2], ("deleted", user.id))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```
