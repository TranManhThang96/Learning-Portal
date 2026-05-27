# Tài Liệu Tham Khảo — Ngày 04: Functions Nâng Cao

## 📚 Official Docs

- **Python Closures**: https://docs.python.org/3/reference/executionmodel.html#closures
- **Decorators (PEP 318)**: https://peps.python.org/pep-0318/
- **functools module**: https://docs.python.org/3/library/functools.html
- **Generator Functions**: https://docs.python.org/3/reference/expressions.html#yield-expressions
- **Generator Iterator Methods**: https://docs.python.org/3/reference/expressions.html#generator-iterator-methods
- **PEP 255 — Simple Generators**: https://peps.python.org/pep-0255/
- **PEP 289 — Generator Expressions**: https://peps.python.org/pep-0289/
- **PEP 342 — Coroutines via Enhanced Generators**: https://peps.python.org/pep-0342/
- **PEP 612 — ParamSpec**: https://peps.python.org/pep-0612/
- **typing module**: https://docs.python.org/3/library/typing.html
- **itertools module**: https://docs.python.org/3/library/itertools.html

## 📝 Articles / Blog Posts

- **Fluent Python (Chapter 7: Functions as First-Class Objects)** — Luciano Ramalho: https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/
- **Fluent Python (Chapter 9: Decorators and Closures)** — Luciano Ramalho
- **Python Cookbook (Chapter 9: Metaprogramming)** — David Beazley: https://www.oreilly.com/library/view/python-cookbook-3rd/9781449357337/
- **Real Python — Decorators**: https://realpython.com/primer-on-python-decorators/
- **Real Python — Generators**: https://realpython.com/introduction-to-python-generators/
- **Real Python — functools**: https://realpython.com/python-functools-module/
- **Real Python — lru_cache**: https://realpython.com/lru-cache-python/

## 🎥 Video / Courses

- **David Beazley — Generator Tricks for Systems Programmers (PyCon 2008)**: https://www.dabeaz.com/generators/
  - Classic talk về generator pipelines — rất hay, nhưng nên xem như optional deep dive sau bài core
- **David Beazley — Generators: The Final Frontier (PyCon 2014)**: https://www.youtube.com/watch?v=D1twn9kLmYg
- **James Powell — So you want to be a Python expert? (PyData 2017)**: https://www.youtube.com/watch?v=cKPlPJyQrt4
  - Cover decorators, generators, context managers sâu sắc
- **Raymond Hettinger — Beyond PEP 8**: https://www.youtube.com/watch?v=wf-BqAjZb8M
- **Corey Schafer — Decorators (YouTube)**: https://www.youtube.com/watch?v=FsAPt_9Bf3U
- **mCoding — Python Decorators**: https://www.youtube.com/watch?v=QH5fw9kxDQA

## 📝 Articles / Blog Posts Bổ Sung

- **Primer on Python Decorators**: https://realpython.com/primer-on-python-decorators/
- **Python Tips — Decorators**: https://book.pythontips.com/en/latest/decorators.html
- **Understanding Python's nonlocal**: https://realpython.com/python-nonlocal-statement/
- **Itertools Recipes**: https://docs.python.org/3/library/itertools.html#itertools-recipes
- **Generators as Pipelines** (David Beazley): https://www.dabeaz.com/generators/Generators.pdf
- **Python functools.partial Explained**: https://towardsdatascience.com/functools-the-power-of-higher-order-functions-in-python-8e6e61c2e5af

## 🔧 Tools / Libraries

- **decorator library**: https://pypi.org/project/decorator/
  - Optional: thư viện giúp viết decorators dễ dàng hơn, preserve signature tốt hơn
- **wrapt**: https://pypi.org/project/wrapt/
  - Optional production deep dive: decorator framework handle edge cases tốt
- **more-itertools**: https://more-itertools.readthedocs.io/en/stable/
  - Mở rộng itertools với nhiều utilities hữu ích
- **toolz**: https://toolz.readthedocs.io/en/latest/
  - Functional programming utilities: `compose`, `pipe`, `curry`, `memoize`

## 💡 Ghi chú thêm

### NodeJS → Python Migration

| NodeJS Pattern | Python Equivalent |
|----------------|-------------------|
| `_.memoize(fn)` | `@functools.lru_cache` |
| `_.partial(fn, arg)` | `functools.partial(fn, arg)` |
| `_.compose(f, g)` | `lambda x: f(g(x))` hoặc `toolz.compose` |
| `_.curry(fn)` | `toolz.curry(fn)` |
| `function* gen()` | `def gen(): yield ...` |
| `yield*` | `yield from` |
| `async function*` | `async def gen(): yield await ...` |
| Readable Stream | Generator / async generator |
| Transform Stream | Generator-to-generator function |

### Cheat Sheet

```python
# Closure với nonlocal
def outer():
    x = 0
    def inner():
        nonlocal x
        x += 1
        return x
    return inner

# Basic decorator với @wraps
import functools
def my_dec(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# Decorator với parameters
def dec_with_params(param):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Generator
def my_gen():
    yield 1
    yield 2
    yield 3

# yield from
def delegate():
    yield from [1, 2, 3]
    yield from range(4, 7)

# Generator expression
gen = (x**2 for x in range(10))

# lru_cache
from functools import lru_cache
@lru_cache(maxsize=128)
def cached_fn(n: int) -> int:
    return n * 2

# partial
from functools import partial
add = lambda x, y: x + y
add_5 = partial(add, 5)

# cached_property
from functools import cached_property
class MyClass:
    @cached_property
    def expensive(self) -> int:
        return sum(range(1000000))
```
