# Ngày 05: OOP trong Python

## 🎯 Mục tiêu học tập

- Viết Python classes với `__init__`, properties, class methods, static methods
- Hiểu `__dunder__` methods để customize behavior (operator overloading, string representation)
- Implement inheritance và hiểu MRO (Method Resolution Order)
- Sử dụng ABC (Abstract Base Classes) để định nghĩa interfaces
- Áp dụng Protocol cho duck typing với type safety
- So sánh class-based OOP giữa Python và TypeScript

**Scope 2 giờ cho ngày này:**
- **Must Learn:** class cơ bản, `@property`, `@classmethod`, `@staticmethod`, dunder phổ biến, `@dataclass` vs class thường, inheritance 1 cấp, ABC vs Protocol ở mức API design.
- **Skim:** MRO output (`Class.__mro__`) và `super()` cơ bản.
- **Optional Reference:** multiple inheritance/mixins, cooperative MRO, `@runtime_checkable` runtime checks, `__slots__` performance.

## 🔄 So sánh TypeScript vs Python

| Khái niệm | TypeScript | Python |
|-----------|-----------|--------|
| Constructor | `constructor(private x: number)` | `def __init__(self, x: int)` |
| Self reference | `this` | `self` (convention, không phải keyword) |
| Private | `private x: number` (compile-time only) | `self.__x` (name mangling) hoặc `self._x` (convention) |
| Protected | `protected x: number` | `self._x` (convention only) |
| Getter/Setter | `get x() { return this._x; }` | `@property` / `@x.setter` |
| Extends | `class Dog extends Animal` | `class Dog(Animal):` |
| Interface | `interface Flyable { fly(): void }` | `Protocol` hoặc `ABC` |
| Implements | `class Bird implements Flyable` | `class Bird(Flyable):` hoặc structural (Protocol) |
| Static method | `static create(): Dog` | `@staticmethod def create():` |
| Class method | Không có trực tiếp | `@classmethod def from_dict(cls, d):` |
| Abstract | `abstract class Animal` | `class Animal(ABC): @abstractmethod` |
| `toString` | `toString(): string` | `__str__(self) -> str` |
| `valueOf` | `valueOf(): number` | `__int__`, `__float__` |
| Operator overload | Không hỗ trợ | `__add__`, `__mul__`, `__eq__`, etc. |
| `instanceof` | `x instanceof Dog` | `isinstance(x, Dog)` |
| `typeof` | `typeof x === "string"` | `isinstance(x, str)` |

**Điểm khác biệt quan trọng:**
- Python không có `private` thực sự — `_` là convention (protected), `__` là name mangling
- Python `self` phải viết tường minh trong mọi method (khác JS không cần `this` trong arrow functions)
- Python `@classmethod` nhận `cls` thay vì `self` — dùng để tạo factory methods
- Python `@staticmethod` không nhận `self` hay `cls` — giống static method trong TS
- Python Protocol là structural typing (duck typing) — không cần khai báo `implements`

---

## 📖 Lý thuyết

### 1. Class Cơ Bản

**WHY:** Python class syntax tương tự TS nhưng có một số patterns khác biệt quan trọng: factory methods với `@classmethod`, computed properties với `@property`, và dunder methods để customize behavior.

```python
from __future__ import annotations  # Cho phép type hints forward references

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar


class BankAccount:
    """
    Ví dụ đầy đủ về Python class với tất cả các patterns.

    Python convention:
    - _single_underscore: protected (convention, không enforced)
    - __double_underscore: name mangling (tránh override vô tình)
    - __dunder__: special methods (Python protocol)
    """

    # Class variable — shared across all instances
    # TypeScript equivalent: static INTEREST_RATE: number = 0.05
    INTEREST_RATE: ClassVar[float] = 0.05
    _account_count: ClassVar[int] = 0

    def __init__(self, owner: str, balance: Decimal = Decimal("0")) -> None:
        """Constructor — equivalent to TypeScript constructor."""
        # Instance variables
        self._owner = owner               # "Protected" by convention
        self.__balance = balance          # Name mangled → _BankAccount__balance
        self._transactions: list[dict] = []

        # Update class variable
        BankAccount._account_count += 1

    # ========== Properties (Getter/Setter) ==========

    @property
    def owner(self) -> str:
        """Getter — gọi bằng account.owner (không phải account.owner())."""
        return self._owner

    @property
    def balance(self) -> Decimal:
        return self.__balance

    @balance.setter
    def balance(self, value: Decimal) -> None:
        """Setter với validation."""
        if value < Decimal("0"):
            raise ValueError(f"Balance cannot be negative: {value}")
        self.__balance = value

    @property
    def transaction_count(self) -> int:
        """Read-only property — không có setter."""
        return len(self._transactions)

    # ========== Instance Methods ==========

    def deposit(self, amount: Decimal, description: str = "") -> None:
        """Nạp tiền vào tài khoản."""
        if amount <= Decimal("0"):
            raise ValueError(f"Deposit amount must be positive: {amount}")
        self.__balance += amount
        self._transactions.append({
            "type": "deposit",
            "amount": amount,
            "description": description,
            "balance_after": self.__balance,
        })

    def withdraw(self, amount: Decimal, description: str = "") -> None:
        """Rút tiền từ tài khoản."""
        if amount <= Decimal("0"):
            raise ValueError(f"Withdrawal amount must be positive: {amount}")
        if amount > self.__balance:
            raise ValueError(f"Insufficient funds: balance={self.__balance}, requested={amount}")
        self.__balance -= amount
        self._transactions.append({
            "type": "withdrawal",
            "amount": amount,
            "description": description,
            "balance_after": self.__balance,
        })

    def apply_interest(self) -> Decimal:
        """Tính và áp dụng lãi suất. Returns amount added."""
        interest = self.__balance * Decimal(str(self.INTEREST_RATE))
        self.deposit(interest, description="Annual interest")
        return interest

    # ========== Class Methods (Factory Pattern) ==========

    @classmethod
    def from_dict(cls, data: dict) -> BankAccount:
        """
        Factory method — tạo instance từ dict.

        TypeScript equivalent:
        static fromDict(data: Record<string, any>): BankAccount {
            return new BankAccount(data.owner, data.balance);
        }
        """
        return cls(
            owner=data["owner"],
            balance=Decimal(str(data.get("balance", 0))),
        )

    @classmethod
    def create_savings(cls, owner: str, initial_deposit: Decimal) -> BankAccount:
        """Factory method tạo savings account với deposit ban đầu."""
        account = cls(owner=owner)
        account.deposit(initial_deposit, description="Initial deposit")
        return account

    @classmethod
    def get_account_count(cls) -> int:
        """Class method truy cập class variable."""
        return cls._account_count

    # ========== Static Methods ==========

    @staticmethod
    def validate_amount(amount: Decimal) -> bool:
        """
        Utility method — không cần access instance hay class.

        TypeScript equivalent:
        static validateAmount(amount: Decimal): boolean { ... }
        """
        return amount > Decimal("0") and amount <= Decimal("1000000")

    @staticmethod
    def format_currency(amount: Decimal, currency: str = "USD") -> str:
        return f"{currency} {amount:,.2f}"

    # ========== Dunder Methods (Special Methods) ==========

    def __str__(self) -> str:
        """Human-readable string — dùng với print() và str()."""
        return f"BankAccount({self._owner}, balance={self.format_currency(self.__balance)})"

    def __repr__(self) -> str:
        """
        Unambiguous representation — dùng trong REPL, debugging, logging.
        Convention: nên return string có thể eval() để tái tạo object.
        """
        return f"BankAccount(owner={self._owner!r}, balance={self.__balance!r})"

    def __eq__(self, other: object) -> bool:
        """Equality check — `==` operator."""
        if not isinstance(other, BankAccount):
            return NotImplemented
        return self._owner == other._owner and self.__balance == other.__balance

    def __hash__(self) -> int:
        """
        Hash — cần thiết nếu define __eq__.
        Objects với cùng hash phải có __eq__ == True.
        Dùng frozen attributes (không thay đổi).
        """
        return hash(self._owner)  # Dùng owner vì balance thay đổi được

    def __len__(self) -> int:
        """Trả về số transactions — `len(account)`."""
        return len(self._transactions)

    def __bool__(self) -> bool:
        """Boolean context — `if account:` True nếu balance > 0."""
        return self.__balance > Decimal("0")

    def __contains__(self, transaction_type: str) -> bool:
        """Membership test — `"deposit" in account`."""
        return any(t["type"] == transaction_type for t in self._transactions)

    def __iter__(self):
        """Iterable — `for t in account:`."""
        return iter(self._transactions)


# ========== Demo ==========

# Tạo account
account1 = BankAccount("Alice", Decimal("1000"))
account2 = BankAccount.from_dict({"owner": "Bob", "balance": "500.00"})
account3 = BankAccount.create_savings("Charlie", Decimal("2000"))

# Properties
print(account1.owner)   # Alice
print(account1.balance) # 1000

# Operations
account1.deposit(Decimal("200"), "Salary")
account1.withdraw(Decimal("50"), "Coffee")

# Dunder methods
print(str(account1))    # BankAccount(Alice, balance=USD 1,150.00)
print(repr(account1))   # BankAccount(owner='Alice', balance=Decimal('1150'))
print(len(account1))    # 2 (số transactions)
print(bool(account1))   # True

# Iterate transactions
for transaction in account1:
    print(f"  {transaction['type']}: {transaction['amount']}")

# Membership
print("deposit" in account1)   # True
print("transfer" in account1)  # False

# Class variable
print(BankAccount.get_account_count())  # 3
```

---

### 2. Inheritance và MRO

**WHY:** Python hỗ trợ multiple inheritance (TS không có), điều này tạo ra MRO (Method Resolution Order) — Python dùng C3 linearization algorithm để xác định thứ tự gọi methods. Trong 2 giờ, cần hiểu single inheritance + `super()` trước; multiple inheritance/MRO chỉ nên là optional deep dive.

**Abstract Base Class và Inheritance:**

```python
from abc import ABC, abstractmethod
from typing import ClassVar


class Animal(ABC):
    """
    Abstract base class — không thể instantiate trực tiếp.
    Equivalent TypeScript:
    abstract class Animal {
        abstract speak(): string;
        abstract move(): void;
    }
    """

    species: ClassVar[str] = "Unknown"  # Class variable, override in subclass

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    @abstractmethod
    def speak(self) -> str:
        """Mỗi animal phải implement speak()."""
        ...

    @abstractmethod
    def move(self) -> str:
        """Mỗi animal phải implement move()."""
        ...

    def describe(self) -> str:
        """Concrete method — có thể dùng bởi subclasses."""
        return f"{self.__class__.__name__}({self.name}, age={self.age})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, age={self.age!r})"


class Dog(Animal):
    """
    Concrete class — implements Animal.

    TypeScript equivalent:
    class Dog extends Animal {
        constructor(name: string, age: number, breed: string) {
            super(name, age);
            this.breed = breed;
        }
    }
    """

    species: ClassVar[str] = "Canis lupus familiaris"

    def __init__(self, name: str, age: int, breed: str) -> None:
        super().__init__(name, age)  # Gọi parent constructor
        self.breed = breed

    def speak(self) -> str:
        return f"{self.name} says: Woof!"

    def move(self) -> str:
        return f"{self.name} runs on 4 legs"

    def fetch(self, item: str) -> str:
        return f"{self.name} fetches the {item}!"


class PoliceDog(Dog):
    """Multi-level inheritance."""

    def __init__(self, name: str, age: int, breed: str, badge_number: str) -> None:
        super().__init__(name, age, breed)
        self.badge_number = badge_number

    def speak(self) -> str:
        base = super().speak()  # Gọi Dog.speak()
        return f"{base} (Badge: {self.badge_number})"

    def search(self, target: str) -> str:
        return f"K-9 {self.name} ({self.badge_number}) searching for {target}..."


# Sử dụng
dog = Dog("Rex", 3, "German Shepherd")
police_dog = PoliceDog("Bruno", 4, "Belgian Malinois", "K9-007")

print(dog.speak())         # Rex says: Woof!
print(police_dog.speak())  # Bruno says: Woof! (Badge: K9-007)
print(police_dog.fetch("ball"))  # Bruno fetches the ball! (inherited from Dog)

# MRO
print(PoliceDog.__mro__)
# (<class 'PoliceDog'>, <class 'Dog'>, <class 'Animal'>, <class 'ABC'>, <class 'object'>)
print(PoliceDog.mro())  # Cùng kết quả, dạng list

# isinstance checks
print(isinstance(police_dog, PoliceDog))  # True
print(isinstance(police_dog, Dog))         # True
print(isinstance(police_dog, Animal))      # True
```

**Multiple Inheritance và Mixin Pattern (optional deep dive):**

Mixin hữu ích cho cross-cutting behavior, nhưng dễ tạo dependency ẩn qua MRO. Với app code thông thường, ưu tiên composition/service helper trước khi tạo nhiều mixin.

```python
from datetime import datetime


class TimestampMixin:
    """
    Mixin thêm created_at và updated_at vào bất kỳ class nào.

    TypeScript equivalent: không có built-in, dùng interface + decorator hoặc generic class
    Mixin pattern trong Python: class MyModel(TimestampMixin, BaseModel)
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

    def touch(self) -> None:
        """Cập nhật updated_at."""
        self.updated_at = datetime.now()


class AuditMixin:
    """Mixin thêm audit trail."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._audit_log: list[dict] = []

    def log_action(self, action: str, user: str, details: str = "") -> None:
        self._audit_log.append({
            "action": action,
            "user": user,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def audit_log(self) -> list[dict]:
        return self._audit_log.copy()


class SerializeMixin:
    """Mixin thêm serialization."""

    def to_dict(self) -> dict:
        return {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


# MRO với multiple inheritance: C3 linearization
# Python giải quyết diamond problem qua MRO
class User(TimestampMixin, AuditMixin, SerializeMixin):
    def __init__(self, name: str, email: str, **kwargs):
        super().__init__(**kwargs)  # **kwargs propagate qua MRO chain
        self.name = name
        self.email = email

    def __repr__(self) -> str:
        return f"User(name={self.name!r}, email={self.email!r})"


# MRO của User:
print(User.__mro__)
# User → TimestampMixin → AuditMixin → SerializeMixin → object

user = User("Alice", "alice@example.com")
print(user.created_at)      # datetime từ TimestampMixin
user.log_action("LOGIN", "alice")  # AuditMixin
print(user.to_dict())       # SerializeMixin
user.touch()                # TimestampMixin
```

**super() và cooperative multiple inheritance (optional deep dive):**

```python
class A:
    def method(self) -> list[str]:
        return ["A"]

class B(A):
    def method(self) -> list[str]:
        return super().method() + ["B"]

class C(A):
    def method(self) -> list[str]:
        return super().method() + ["C"]

class D(B, C):
    def method(self) -> list[str]:
        return super().method() + ["D"]

d = D()
print(d.method())       # ['A', 'C', 'B', 'D']
print(D.__mro__)        # D → B → C → A → object
# super() trong B gọi C (theo MRO), không phải A trực tiếp!
```

**MRO caveats:**
- Thứ tự base classes trong `class D(B, C)` là API quan trọng; đổi thứ tự có thể đổi behavior.
- Cooperative multiple inheritance chỉ ổn khi mọi class trong chain dùng `super()` nhất quán và nhận/forward `**kwargs` đúng cách.
- Nếu mixin cần state phức tạp hoặc thứ tự init nhạy cảm, composition thường dễ test và dễ đọc hơn.

---

### 3. Protocol — Duck Typing với Type Safety

**WHY:** Protocol là Python's answer to TypeScript interfaces cho structural typing. Không cần khai báo `implements` — nếu object có đúng methods/attributes, nó thỏa mãn Protocol. Đây là "duck typing" nhưng có type checker support.

**Caveat quan trọng:** `Protocol` chủ yếu là công cụ cho static type checker (mypy/pyright). `@runtime_checkable` chỉ mở khóa `isinstance()`/`issubclass()` ở runtime và check shape ở mức hạn chế; nó không thay thế validation và không đảm bảo đầy đủ method signatures/type parameters.

```python
from typing import Protocol, runtime_checkable
from abc import abstractmethod


# Protocol = structural subtyping (duck typing với type checker)
@runtime_checkable  # Cho phép dùng isinstance() checks
class Drawable(Protocol):
    """Bất kỳ object nào có method draw() đều thỏa mãn Drawable."""

    def draw(self, canvas: str) -> None:
        """Draw this object on canvas."""
        ...


@runtime_checkable
class Resizable(Protocol):
    width: float
    height: float

    def resize(self, factor: float) -> None:
        ...


@runtime_checkable
class Saveable(Protocol):
    def save(self, filepath: str) -> None:
        ...

    def load(self, filepath: str) -> None:
        ...


# Classes không cần khai báo implements
class Circle:
    def __init__(self, radius: float) -> None:
        self.radius = radius
        self.width = radius * 2
        self.height = radius * 2

    def draw(self, canvas: str) -> None:
        print(f"Drawing circle (r={self.radius}) on {canvas}")

    def resize(self, factor: float) -> None:
        self.radius *= factor
        self.width = self.radius * 2
        self.height = self.radius * 2

    def save(self, filepath: str) -> None:
        print(f"Saving circle to {filepath}")

    def load(self, filepath: str) -> None:
        print(f"Loading circle from {filepath}")


class Rectangle:
    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height

    def draw(self, canvas: str) -> None:
        print(f"Drawing rect ({self.width}x{self.height}) on {canvas}")

    def resize(self, factor: float) -> None:
        self.width *= factor
        self.height *= factor


# Type-safe functions nhận Protocol
def render_all(shapes: list[Drawable], canvas: str) -> None:
    for shape in shapes:
        shape.draw(canvas)  # mypy biết shape có method draw()


def resize_all(shapes: list[Resizable], factor: float) -> None:
    for shape in shapes:
        shape.resize(factor)


# Sử dụng
circle = Circle(5.0)
rect = Rectangle(10.0, 20.0)

# isinstance check với @runtime_checkable
print(isinstance(circle, Drawable))   # True
print(isinstance(circle, Resizable))  # True
print(isinstance(circle, Saveable))   # True
print(isinstance(rect, Saveable))     # False (không có save/load)

# Type-safe function calls
render_all([circle, rect], "main_canvas")
resize_all([circle, rect], 2.0)

# Composing Protocols
class DrawableAndResizable(Drawable, Resizable, Protocol):
    """Composed protocol."""
    ...

def process_shape(shape: DrawableAndResizable, canvas: str) -> None:
    shape.draw(canvas)
    shape.resize(1.5)

process_shape(circle, "canvas")  # OK
process_shape(rect, "canvas")    # OK: rect có draw + resize nên thỏa mãn DrawableAndResizable
```

**`@runtime_checkable` pitfalls:**

```python
@runtime_checkable
class HasDraw(Protocol):
    def draw(self, canvas: str) -> None:
        ...


class BadDraw:
    # Runtime check thấy có attribute "draw", nhưng signature/return type sai.
    def draw(self) -> int:
        return 123


obj = BadDraw()
print(isinstance(obj, HasDraw))  # Có thể True ở runtime shape-check
# mypy/pyright mới là nơi bắt signature mismatch nếu object được type-check đúng.
```

Rule of thumb:
- Dùng `Protocol` cho function signatures/library APIs.
- Chỉ dùng `@runtime_checkable` khi thật sự cần `isinstance()` guard nhẹ.
- Nếu cần validate input/runtime contract nghiêm túc, dùng explicit checks, ABC, hoặc validation layer.

---

### 4. Abstract Classes với ABC

**WHY:** ABC (Abstract Base Class) khác Protocol ở chỗ: ABC là **nominal typing** (phải kế thừa rõ ràng), Protocol là **structural typing** (không cần kế thừa). Dùng ABC khi muốn enforce inheritance hierarchy và shared implementation.

```python
from abc import ABC, abstractmethod
from typing import Any


class DataRepository(ABC):
    """
    Abstract repository interface.

    TypeScript equivalent:
    abstract class DataRepository<T> {
        abstract findById(id: string): Promise<T | null>;
        abstract save(entity: T): Promise<void>;
        abstract delete(id: string): Promise<void>;
    }
    """

    @abstractmethod
    def find_by_id(self, entity_id: str) -> Any | None:
        """Tìm entity theo ID."""
        ...

    @abstractmethod
    def save(self, entity: Any) -> None:
        """Lưu entity."""
        ...

    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Xóa entity. Returns True nếu thành công."""
        ...

    # Concrete methods có thể gọi abstract methods
    def find_or_raise(self, entity_id: str) -> Any:
        """Template method pattern."""
        entity = self.find_by_id(entity_id)
        if entity is None:
            raise KeyError(f"Entity not found: {entity_id}")
        return entity

    def save_all(self, entities: list) -> None:
        """Batch save — gọi abstract save() cho mỗi item."""
        for entity in entities:
            self.save(entity)


class InMemoryRepository(DataRepository):
    """Concrete implementation dùng dict làm storage."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def find_by_id(self, entity_id: str) -> Any | None:
        return self._store.get(entity_id)

    def save(self, entity: Any) -> None:
        entity_id = getattr(entity, "id", None) or str(id(entity))
        self._store[entity_id] = entity
        print(f"Saved entity {entity_id}")

    def delete(self, entity_id: str) -> bool:
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    def find_all(self) -> list:
        """Extra method không có trong abstract class."""
        return list(self._store.values())


# Không thể instantiate abstract class
try:
    repo = DataRepository()  # type: ignore
except TypeError as e:
    print(f"Cannot instantiate ABC: {e}")
    # Can't instantiate abstract class DataRepository with abstract method...

# Phải implement tất cả abstract methods
repo = InMemoryRepository()

from dataclasses import dataclass

@dataclass
class User:
    id: str
    name: str
    email: str

user = User("1", "Alice", "alice@example.com")
repo.save(user)
found = repo.find_by_id("1")
print(found)  # User(id='1', name='Alice', email='alice@example.com')

# Template method
try:
    repo.find_or_raise("999")
except KeyError as e:
    print(f"Not found: {e}")

# abstractmethod + property
class Shape(ABC):
    @property
    @abstractmethod
    def area(self) -> float:
        """Computed property — must be implemented."""
        ...

    @property
    @abstractmethod
    def perimeter(self) -> float:
        ...

    def describe(self) -> str:
        return f"{self.__class__.__name__}: area={self.area:.2f}, perimeter={self.perimeter:.2f}"


class Circle(Shape):
    def __init__(self, radius: float) -> None:
        self.radius = radius

    @property
    def area(self) -> float:
        import math
        return math.pi * self.radius ** 2

    @property
    def perimeter(self) -> float:
        import math
        return 2 * math.pi * self.radius


circle = Circle(5)
print(circle.describe())  # Circle: area=78.54, perimeter=31.42
```

---

## ⚠️ Common Mistakes

| Mistake | Sai | Đúng |
|---------|-----|------|
| Quên `self` trong method | `def get_name(): return self.name` | `def get_name(self): return self.name` |
| Mutable default arg trong `__init__` | `def __init__(self, items=[]):` | `def __init__(self, items=None): self.items = items or []` |
| Quên define `__hash__` khi define `__eq__` | Chỉ có `__eq__` | `__hash__ = None` hoặc implement cả hai |
| Nhầm class var và instance var | `class Dog: count = 0; count += 1` | `Dog._count += 1` hoặc `self.__class__._count += 1` |
| `super()` không nhận args | `super(Dog, self).__init__()` | `super().__init__()` (Python 3) |
| Nhầm `@classmethod` và `@staticmethod` | `@staticmethod def create(cls):` | `@classmethod def create(cls):` (cls là tham số tự động) |
| Dùng `isinstance(x, Protocol)` không có `@runtime_checkable` | `TypeError` | Thêm `@runtime_checkable` hoặc bỏ runtime check |
| Tin `@runtime_checkable` validate type signatures | Runtime chỉ check shape hạn chế | Dùng mypy/pyright hoặc validation rõ ràng |
| Lạm dụng mixin/multiple inheritance | Behavior phụ thuộc MRO, khó debug | Ưu tiên composition; mixin chỉ cho behavior nhỏ, stateless |

---

## ✅ Best Practices

**Class Design:**
- Prefer composition over inheritance (đặc biệt khi hierarchy quá sâu)
- Dùng `@dataclass` cho simple data-holding classes (xem Day 03)
- Implement `__repr__` trước `__str__` — `__repr__` là ưu tiên cao hơn khi debug
- Khi implement `__eq__`, luôn implement `__hash__` (hoặc set `__hash__ = None`)

**Inheritance:**
- Dùng `super().__init__(**kwargs)` trong Mixin để support cooperative multiple inheritance
- Giữ inheritance hierarchy nông (tối đa 2-3 levels)
- Prefer ABC over Protocol khi cần enforce code-sharing qua `super()`
- Prefer Protocol over ABC khi muốn structural typing (không cần kế thừa)
- Xem multiple inheritance/MRO là advanced tool; dùng khi lợi ích composition không đủ

**Properties:**
- Dùng `@property` cho computed values và validation
- Không làm heavy computation trong `@property` — dùng `@cached_property` nếu expensive
- Prefix `_` cho backing attribute: `self._name` → property `name`

---

## ⚖️ Trade-offs

| Pattern | Pros | Cons | Khi dùng |
|---------|------|------|-----------|
| ABC | Enforce hierarchy, share implementation | Tight coupling, phải kế thừa | Framework internals, template method |
| Protocol | Flexible, no coupling, structural | Runtime check hạn chế, cần `@runtime_checkable` nếu dùng `isinstance` | Library APIs, type hints |
| Mixin | Reusable behavior, composable | MRO complexity, implicit dependencies | Optional: cross-cutting concerns nhỏ (timestamp, audit) |
| `@dataclass` | Boilerplate reduction, auto dunder | Less control | Data transfer objects, value objects |
| `@property` | Clean API, validation | Overhead vs plain attribute | When setter logic needed |

---

## 🚀 Performance Notes

```python
import timeit

# Attribute access: __slots__ vs __dict__
class WithDict:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class WithSlots:
    __slots__ = ("x", "y")  # Thay __dict__ bằng fixed-size array
    def __init__(self, x, y):
        self.x = x
        self.y = y

import sys
d = WithDict(1, 2)
s = WithSlots(1, 2)

print(f"__dict__ size: {sys.getsizeof(d.__dict__)} bytes")
print(f"__slots__ size: ~{sys.getsizeof(s)} bytes (no __dict__)")
# __slots__ tiết kiệm ~40-50% memory cho objects nhỏ

# Speed comparison
dict_time = timeit.timeit("o.x; o.y", setup="o = WithDict(1,2)", globals=globals(), number=10_000_000)
slot_time = timeit.timeit("o.x; o.y", setup="o = WithSlots(1,2)", globals=globals(), number=10_000_000)
print(f"__dict__: {dict_time:.3f}s")
print(f"__slots__: {slot_time:.3f}s")  # Nhanh hơn ~10-30%
```

**Khi dùng `__slots__`:**
- Classes được tạo hàng triệu instances (e.g., data points, events)
- Memory-constrained environments
- Không cần dynamic attribute assignment

---

## 📝 Tóm tắt

| Concept | Key Point | TypeScript Analogy |
|---------|-----------|-------------------|
| `__init__` | Constructor, nhận `self` | `constructor` |
| `@property` | Getter với computed/validated access | `get x(): T` |
| `@x.setter` | Setter với validation | `set x(v: T)` |
| `@classmethod` | Factory methods, nhận `cls` | `static` method trả về `this` type |
| `@staticmethod` | Utility, không nhận `self`/`cls` | `static` method |
| `__str__` / `__repr__` | String representation | `toString()` |
| `__eq__` / `__hash__` | Equality và hashing | Custom `equals()` |
| `ABC + @abstractmethod` | Nominal interface | `abstract class` |
| `Protocol` | Structural interface (duck typing) | `interface` (TypeScript style) |
| Mixin | Reusable behavior via multiple inheritance | Không có built-in |
| MRO | C3 linearization cho multiple inheritance | Không có (single inheritance) |
| `__slots__` | Memory optimization, fixed attributes | Không có direct equivalent |
