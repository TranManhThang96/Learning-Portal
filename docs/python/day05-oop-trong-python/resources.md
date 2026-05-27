# Tài Liệu Tham Khảo — Ngày 05: OOP trong Python

## 📚 Official Docs

- **Python Classes**: https://docs.python.org/3/tutorial/classes.html
- **Data Model (Dunder Methods)**: https://docs.python.org/3/reference/datamodel.html
- **ABC module**: https://docs.python.org/3/library/abc.html
- **typing.Protocol**: https://docs.python.org/3/library/typing.html#typing.Protocol
- **PEP 544 — Protocols**: https://peps.python.org/pep-0544/
- **PEP 3119 — Abstract Base Classes**: https://peps.python.org/pep-3119/
- **`__slots__`**: https://docs.python.org/3/reference/datamodel.html#slots
- **`super()`**: https://docs.python.org/3/library/functions.html#super
- **MRO (C3 Linearization)**: https://docs.python.org/3/howto/mro.html

## 📝 Articles / Blog Posts

- **Fluent Python (Chapters 11-14: OOP)** — Luciano Ramalho: https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/
  - Chapter 11: A Pythonic Object
  - Chapter 12: Special Methods for Sequences
  - Chapter 13: Interfaces, Protocols, ABCs
  - Chapter 14: Inheritance: For Better or Worse
- **Python Cookbook (Chapter 8: Classes and Objects)** — David Beazley
- **Real Python — OOP in Python**: https://realpython.com/python3-object-oriented-programming/
- **Real Python — Python's super()**: https://realpython.com/python-super/
- **Real Python — Python Protocols**: https://realpython.com/python-protocol/
- **Real Python — Descriptors**: https://realpython.com/python-descriptors/
- **Real Python — Abstract Base Classes**: https://realpython.com/python-interface/

## 🎥 Video / Courses

- **Raymond Hettinger — Python's Class Development Toolkit (PyCon 2013)**: https://www.youtube.com/watch?v=HTLu2DFOdTg
  - Optional deep dive: giải thích super(), MRO, Mixin rất rõ ràng
- **James Powell — Help, I just inherited 100k lines of code (PyData 2018)**: https://www.youtube.com/watch?v=tKTZoB2Vjuk
- **Corey Schafer — Python OOP (YouTube Series)**:
  - Part 1 (Classes): https://www.youtube.com/watch?v=ZDa-Z5JzLYM
  - Part 2 (Class/Static Methods): https://www.youtube.com/watch?v=rq8cL2XMM5M
  - Part 3 (Inheritance): https://www.youtube.com/watch?v=RSl87lqOXDE
  - Part 4 (Dunder Methods): https://www.youtube.com/watch?v=3ohzBxoFHAY
- **mCoding — Python Slots**: https://www.youtube.com/watch?v=Iwf17zsDAnY
- **mCoding — Protocol vs ABC**: https://www.youtube.com/watch?v=xvb5hGLoK0A

## 📝 Articles / Blog Posts Bổ Sung

- **Python MRO Explained**: https://rhettinger.wordpress.com/2011/05/26/super-considered-super/
  - Optional deep dive: Raymond Hettinger's canonical post về super() và MRO
- **Interfaces in Python: Protocol vs ABC**: https://andrewbrookins.com/python/using-protocols-and-abstract-base-classes-in-python/
- **Python Descriptors Guide**: https://realpython.com/python-descriptors/
- **When to use `__slots__`**: https://wiki.python.org/moin/UsingSlots
- **Design Patterns in Python**: https://refactoring.guru/design-patterns/python

## 💡 Ghi chú thêm

### NodeJS → Python OOP Cheat Sheet

| Pattern | NodeJS/TypeScript | Python |
|---------|-------------------|--------|
| Constructor | `constructor(private x: T)` | `def __init__(self, x: T): self.x = x` |
| Getter | `get x() { return this._x; }` | `@property def x(self): return self._x` |
| Setter | `set x(v) { this._x = v; }` | `@x.setter def x(self, v): self._x = v` |
| Private | `private _x: T` | `self.__x` (name mangled) |
| Static | `static method()` | `@staticmethod def method():` |
| Factory | `static create(): T` | `@classmethod def create(cls): return cls(...)` |
| Abstract | `abstract method(): T` | `@abstractmethod def method(self) -> T: ...` |
| Interface (structural) | `interface Flyable` | `class Flyable(Protocol):` |
| Interface (nominal) | Không có | `class Flyable(ABC): @abstractmethod def fly(): ...` |
| Extends | `class A extends B` | `class A(B):` |
| Multiple inherit | Không hỗ trợ | `class A(B, C, D):` |
| `super()` | `super().method()` | `super().method()` |
| `toString()` | `toString(): string` | `def __str__(self) -> str:` |
| Operator overload | Không | `def __add__(self, other):` |
| `instanceof` | `x instanceof Dog` | `isinstance(x, Dog)` |
| Destructuring | `const {x, y} = obj` | `x, y = obj.x, obj.y` hoặc `@dataclass` |

### Dunder Methods Cheat Sheet

```python
# Initialization & Representation
__init__(self, ...)         # Constructor
__repr__(self) -> str       # Developer string: repr(obj)
__str__(self) -> str        # User string: str(obj), print(obj)
__format__(self, spec)      # f"{obj:.2f}"
__bytes__(self) -> bytes    # bytes(obj)

# Comparison
__eq__(self, other) -> bool    # ==
__ne__(self, other) -> bool    # != (auto from __eq__)
__lt__(self, other) -> bool    # <
__le__(self, other) -> bool    # <=
__gt__(self, other) -> bool    # >
__ge__(self, other) -> bool    # >=
__hash__(self) -> int          # hash(obj), dùng trong set/dict

# Arithmetic
__add__(self, other)        # +
__sub__(self, other)        # -
__mul__(self, other)        # *
__truediv__(self, other)    # /
__floordiv__(self, other)   # //
__mod__(self, other)        # %
__pow__(self, other)        # **
__neg__(self)               # unary -
__abs__(self)               # abs()

# Reflected arithmetic (right operand)
__radd__(self, other)       # other + self
__rmul__(self, other)       # other * self

# In-place arithmetic
__iadd__(self, other)       # +=
__imul__(self, other)       # *=

# Container
__len__(self) -> int        # len()
__contains__(self, item)    # in operator
__getitem__(self, key)      # obj[key]
__setitem__(self, key, val) # obj[key] = val
__delitem__(self, key)      # del obj[key]
__iter__(self)              # iter(), for loops
__next__(self)              # next()

# Context Manager
__enter__(self)             # with statement
__exit__(self, exc_type, exc_val, exc_tb)

# Callable
__call__(self, ...)         # obj()

# Boolean
__bool__(self) -> bool      # bool(obj), if obj:

# Attribute access
__getattr__(self, name)     # obj.name (only if not found normally)
__setattr__(self, name, val) # obj.name = val
__delattr__(self, name)     # del obj.name
```
