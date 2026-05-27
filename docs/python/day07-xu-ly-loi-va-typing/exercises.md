# Bài Tập — Ngày 07: Error Handling & Typing

## Bài 1: Exception Hierarchy cho E-Commerce Domain

**Mô tả:** Xây dựng exception hierarchy hoàn chỉnh cho một e-commerce application với exception chaining, proper HTTP status codes, và serialization cho API responses.

**Yêu cầu:**
- Base class `EcommerceError` với `code`, `message`, `details`, `http_status`
- Domain exceptions: `ProductError`, `OrderError`, `PaymentError`, `UserError`
- Sub-exceptions cụ thể cho từng domain với proper details
- `to_api_response()` method serialize cho FastAPI
- Exception registry với MRO-based handler lookup
- Proper exception chaining (`from e`) khi wrap external errors

**Implement:**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Type
from enum import Enum


class ErrorCode(str, Enum):
    """Machine-readable error codes."""
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_INACTIVE = "PRODUCT_INACTIVE"
    PRODUCT_OUT_OF_STOCK = "PRODUCT_OUT_OF_STOCK"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    ORDER_ALREADY_CONFIRMED = "ORDER_ALREADY_CONFIRMED"
    ORDER_EMPTY = "ORDER_EMPTY"
    PAYMENT_DECLINED = "PAYMENT_DECLINED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    DUPLICATE_EMAIL = "DUPLICATE_EMAIL"


@dataclass
class ApiErrorResponse:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    status_code: int = 500

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


# ============================================================
# TODO: Implement exception hierarchy
# ============================================================

class EcommerceError(Exception):
    """
    Base exception cho toàn bộ e-commerce domain.

    TODO: __init__(message, code, details=None, http_status=500)
          to_api_response() → ApiErrorResponse
          __repr__()
    """
    pass


class ProductError(EcommerceError):
    pass


class ProductNotFoundError(ProductError):
    """code=PRODUCT_NOT_FOUND, http_status=404, details={"product_id": ...}"""
    def __init__(self, product_id: str | int) -> None:
        pass  # TODO


class ProductOutOfStockError(ProductError):
    """code=PRODUCT_OUT_OF_STOCK, http_status=409, details={requested, available}"""
    def __init__(self, product_id: str, requested: int, available: int) -> None:
        pass  # TODO


class ProductInactiveError(ProductError):
    """code=PRODUCT_INACTIVE, http_status=422"""
    def __init__(self, product_id: str) -> None:
        pass  # TODO


class OrderError(EcommerceError):
    pass


class OrderNotFoundError(OrderError):
    def __init__(self, order_id: str) -> None:
        pass  # TODO


class OrderAlreadyConfirmedError(OrderError):
    """Cannot modify a confirmed order."""
    def __init__(self, order_id: str) -> None:
        pass  # TODO


class OrderEmptyError(OrderError):
    """Cannot checkout empty cart. http_status=400"""
    def __init__(self) -> None:
        pass  # TODO


class PaymentError(EcommerceError):
    pass


class PaymentDeclinedError(PaymentError):
    """http_status=402. Include last_four trong details nếu có."""
    def __init__(self, reason: str, last_four: str | None = None) -> None:
        pass  # TODO


class InsufficientFundsError(PaymentError):
    """http_status=402, details={required, available}"""
    def __init__(self, required: float, available: float) -> None:
        pass  # TODO


class UserError(EcommerceError):
    pass


class UserNotFoundError(UserError):
    def __init__(self, user_id: str | int) -> None:
        pass  # TODO


class DuplicateEmailError(UserError):
    """http_status=409, details={"email": email}"""
    def __init__(self, email: str) -> None:
        pass  # TODO


# ============================================================
# Exception Registry
# ============================================================

class ExceptionRegistry:
    """
    Registry mapping exception types to handlers.
    Lookup dùng MRO: nếu không có handler cho subclass,
    fallback lên parent class handler.
    """

    def __init__(self) -> None:
        self._handlers: dict[Type[EcommerceError], Any] = {}

    def handler(self, *exception_types: Type[EcommerceError]):
        def decorator(func):
            for exc_type in exception_types:
                self._handlers[exc_type] = func
            return func
        return decorator

    def get_handler(self, error: EcommerceError):
        """MRO-based lookup: duyệt theo __mro__ để tìm handler gần nhất."""
        # TODO: Implement
        # Hint: for cls in type(error).__mro__: if cls in self._handlers: return ...
        pass

    def handle(self, error: EcommerceError) -> Any:
        handler = self.get_handler(error)
        if handler:
            return handler(error)
        return error.to_api_response().to_dict()


# ============================================================
# OrderService demo
# ============================================================

class OrderService:
    def __init__(self) -> None:
        self._products = {
            "p1": {"name": "Laptop", "price": 999.99, "stock": 5, "active": True},
            "p2": {"name": "Mouse", "price": 29.99, "stock": 0, "active": True},
            "p3": {"name": "Keyboard", "price": 59.99, "stock": 3, "active": False},
        }
        self._orders: dict[str, dict] = {}

    def add_to_cart(self, product_id: str, quantity: int, cart: list) -> None:
        """Raises: ProductNotFoundError, ProductInactiveError, ProductOutOfStockError"""
        # TODO: Implement
        pass

    def checkout(self, cart: list, payment_info: dict) -> dict:
        """
        Raises: OrderEmptyError, PaymentDeclinedError (if total > 1000).
        Returns: {"order_id": ..., "total": ..., "status": "confirmed"}
        """
        # TODO: Implement
        pass

    def cancel_order(self, order_id: str) -> None:
        """Raises: OrderNotFoundError, OrderAlreadyConfirmedError"""
        # TODO: Implement
        pass


# ============================================================
# Tests
# ============================================================

import pytest


class TestExceptionHierarchy:

    def test_product_not_found_is_product_error(self):
        error = ProductNotFoundError("p999")
        assert isinstance(error, ProductError)
        assert isinstance(error, EcommerceError)
        assert isinstance(error, Exception)

    def test_product_not_found_code(self):
        error = ProductNotFoundError("p1")
        assert error.code == ErrorCode.PRODUCT_NOT_FOUND.value
        assert error.http_status == 404

    def test_out_of_stock_details(self):
        error = ProductOutOfStockError("p2", requested=5, available=1)
        assert error.details["requested"] == 5
        assert error.details["available"] == 1

    def test_payment_declined_with_card(self):
        error = PaymentDeclinedError("Card expired", last_four="4242")
        assert error.http_status == 402
        assert "4242" in str(error.details)

    def test_order_empty_http_status(self):
        assert OrderEmptyError().http_status == 400

    def test_api_response_format(self):
        error = ProductNotFoundError("p1")
        d = error.to_api_response().to_dict()
        assert "error" in d
        assert d["error"]["code"] == ErrorCode.PRODUCT_NOT_FOUND.value

    def test_exception_chaining(self):
        original = ConnectionError("DB down")
        try:
            try:
                raise original
            except ConnectionError as e:
                raise PaymentError("Service down", code="PAYMENT_DECLINED", http_status=502) from e
        except PaymentError as e:
            assert e.__cause__ is original

    def test_catch_by_base_class(self):
        with pytest.raises(PaymentError):
            raise PaymentDeclinedError("Declined")

    def test_catch_by_root_class(self):
        with pytest.raises(EcommerceError):
            raise UserNotFoundError("u1")


class TestExceptionRegistry:

    def test_handler_registration(self):
        registry = ExceptionRegistry()
        results = []

        @registry.handler(ProductNotFoundError)
        def handle(error):
            results.append("product_not_found")

        registry.handle(ProductNotFoundError("p1"))
        assert results == ["product_not_found"]

    def test_mro_based_lookup(self):
        registry = ExceptionRegistry()
        results = []

        @registry.handler(ProductError)
        def handle(error):
            results.append(type(error).__name__)

        registry.handle(ProductNotFoundError("p1"))
        registry.handle(ProductOutOfStockError("p2", 3, 1))
        assert "ProductNotFoundError" in results
        assert "ProductOutOfStockError" in results

    def test_specific_handler_takes_priority(self):
        registry = ExceptionRegistry()
        results = []

        @registry.handler(ProductError)
        def base_handler(error):
            results.append("base")

        @registry.handler(ProductNotFoundError)
        def specific_handler(error):
            results.append("specific")

        registry.handle(ProductNotFoundError("p1"))
        assert results == ["specific"]


class TestOrderService:

    def setup_method(self):
        self.service = OrderService()
        self.cart = []

    def test_add_nonexistent_product(self):
        with pytest.raises(ProductNotFoundError):
            self.service.add_to_cart("p999", 1, self.cart)

    def test_add_inactive_product(self):
        with pytest.raises(ProductInactiveError):
            self.service.add_to_cart("p3", 1, self.cart)

    def test_add_out_of_stock(self):
        with pytest.raises(ProductOutOfStockError):
            self.service.add_to_cart("p2", 1, self.cart)

    def test_checkout_empty_cart(self):
        with pytest.raises(OrderEmptyError):
            self.service.checkout([], {})

    def test_successful_checkout(self):
        self.service.add_to_cart("p1", 1, self.cart)
        result = self.service.checkout(self.cart, {"card": "4242"})
        assert "order_id" in result
        assert result["status"] == "confirmed"

    def test_cancel_nonexistent_order(self):
        with pytest.raises(OrderNotFoundError):
            self.service.cancel_order("order-999")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Bài 2: Generic `Result[T, E]` Type

**Mô tả:** Implement `Result[T, E]` type — functional pattern để handle errors mà không dùng exceptions. Pattern phổ biến trong Rust, Go, và TypeScript (`neverthrow`).

**Yêu cầu:**
- `Result[T, E]` Generic với hai type parameters
- `Result.ok(value)` và `Result.err(error)` factory classmethods
- Methods: `is_ok()`, `is_err()`, `unwrap()`, `unwrap_or()`, `map()`, `map_err()`, `and_then()`, `or_else()`, `match()`
- `@result_wrap` decorator convert exception-throwing → Result-returning functions
- Type-safe: mypy phải infer đúng types

```python
from __future__ import annotations

from typing import Generic, TypeVar, Callable
import functools


T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class Result(Generic[T, E]):
    """
    Result type — functional error handling.

    TypeScript/neverthrow:
        const r = ok(42);
        r.map(x => x * 2).match({ ok: v => v, err: e => 0 })

    Rust:
        match result { Ok(v) => process(v), Err(e) => handle(e) }

    Usage:
        def divide(a: float, b: float) -> Result[float, str]:
            if b == 0:
                return Result.err("Division by zero")
            return Result.ok(a / b)

        value = divide(10, 2).map(lambda x: x * 2).unwrap_or(0.0)
    """

    def __init__(self, value: T | None, error: E | None, is_success: bool) -> None:
        self._value = value
        self._error = error
        self._is_success = is_success

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """Create success result."""
        # TODO: Implement
        pass

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        """Create failure result."""
        # TODO: Implement
        pass

    def is_ok(self) -> bool:
        # TODO: Implement
        pass

    def is_err(self) -> bool:
        return not self.is_ok()

    def unwrap(self) -> T:
        """Lấy value nếu ok, raise ValueError nếu err."""
        # TODO: Include error message trong ValueError message
        pass

    def unwrap_or(self, default: T) -> T:
        # TODO: Implement
        pass

    def unwrap_err(self) -> E:
        """Lấy error nếu err, raise ValueError nếu ok."""
        # TODO: Implement
        pass

    def map(self, func: Callable[[T], U]) -> "Result[U, E]":
        """Transform value nếu ok, propagate err unchanged."""
        # TODO: Implement
        pass

    def map_err(self, func: Callable[[E], F]) -> "Result[T, F]":
        """Transform error nếu err, propagate ok unchanged."""
        # TODO: Implement
        pass

    def and_then(self, func: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        """
        Chain operations. Short-circuit on error (flatMap/bind).
        Nếu ok: return func(value) — func phải return Result
        Nếu err: propagate error
        """
        # TODO: Implement
        pass

    def or_else(self, func: Callable[[E], "Result[T, F]"]) -> "Result[T, F]":
        """
        Chain error recovery.
        Nếu err: return func(error) — cơ hội recover
        Nếu ok: propagate unchanged
        """
        # TODO: Implement
        pass

    def match(self, *, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        """Exhaustive pattern matching."""
        # TODO: Implement
        pass

    def __repr__(self) -> str:
        if self._is_success:
            return f"Ok({self._value!r})"
        return f"Err({self._error!r})"


def result_wrap(*exception_types: type[Exception]) -> Callable:
    """
    Decorator: convert exception-throwing → Result-returning function.

    Usage:
        @result_wrap(ValueError, TypeError)
        def parse_int(s: str) -> int:
            return int(s)

        result = parse_int("42")   # Result.ok(42)
        result = parse_int("abc")  # Result.err(ValueError(...))
    """
    def decorator(func: Callable[..., T]) -> Callable[..., "Result[T, Exception]"]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> "Result[T, Exception]":
            # TODO: wrap in try/except, return Result.ok or Result.err
            pass
        return wrapper
    return decorator


# ============================================================
# Sample functions
# ============================================================

def safe_divide(a: float, b: float) -> Result[float, str]:
    if b == 0:
        return Result.err("Division by zero")
    return Result.ok(a / b)


def safe_sqrt(x: float) -> Result[float, str]:
    if x < 0:
        return Result.err(f"Cannot take sqrt of {x}")
    import math
    return Result.ok(math.sqrt(x))


def safe_parse_int(s: str) -> Result[int, str]:
    try:
        return Result.ok(int(s))
    except ValueError:
        return Result.err(f"'{s}' is not a valid integer")


def process_pipeline(raw_value: str, divisor: str) -> Result[float, str]:
    """Parse → divide → sqrt. Short-circuit on any failure."""
    return (
        safe_parse_int(raw_value)
        .map(float)
        .and_then(lambda value:
            safe_parse_int(divisor)
            .map(float)
            .and_then(lambda d: safe_divide(value, d))
        )
        .and_then(safe_sqrt)
    )


# ============================================================
# Tests
# ============================================================

import pytest


class TestResult:

    def test_ok_is_ok(self):
        assert Result.ok(42).is_ok() is True
        assert Result.ok(42).is_err() is False

    def test_err_is_err(self):
        assert Result.err("oops").is_ok() is False
        assert Result.err("oops").is_err() is True

    def test_unwrap_ok(self):
        assert Result.ok(42).unwrap() == 42

    def test_unwrap_err_raises(self):
        with pytest.raises(ValueError):
            Result.err("error").unwrap()

    def test_unwrap_or(self):
        assert Result.ok(42).unwrap_or(0) == 42
        assert Result.err("error").unwrap_or(0) == 0

    def test_unwrap_err(self):
        assert Result.err("oops").unwrap_err() == "oops"

    def test_map_ok(self):
        assert Result.ok(5).map(lambda x: x * 2).unwrap() == 10

    def test_map_preserves_err(self):
        result = Result.err("error").map(lambda x: x * 2)
        assert result.is_err()
        assert result.unwrap_err() == "error"

    def test_map_err(self):
        result = Result.err("original").map_err(lambda e: f"Wrapped: {e}")
        assert result.unwrap_err() == "Wrapped: original"

    def test_and_then_chains(self):
        result = (
            Result.ok(100)
            .and_then(lambda x: safe_divide(x, 4))
            .and_then(safe_sqrt)
        )
        assert result.is_ok()
        assert abs(result.unwrap() - 5.0) < 0.0001

    def test_and_then_short_circuits(self):
        calls = []
        def tracking(x):
            calls.append(x)
            return Result.ok(x)
        Result.err("error").and_then(tracking)
        assert calls == []

    def test_or_else_recovers(self):
        result = Result.err("error").or_else(lambda e: Result.ok(99))
        assert result.is_ok()
        assert result.unwrap() == 99

    def test_match_ok(self):
        msg = Result.ok(42).match(ok=lambda v: f"got {v}", err=lambda e: f"err {e}")
        assert msg == "got 42"

    def test_match_err(self):
        msg = Result.err("oops").match(ok=lambda v: f"got {v}", err=lambda e: f"err {e}")
        assert msg == "err oops"

    def test_repr(self):
        assert repr(Result.ok(42)) == "Ok(42)"
        assert repr(Result.err("oops")) == "Err('oops')"

    def test_result_wrap_success(self):
        @result_wrap(ValueError)
        def parse(s: str) -> int:
            return int(s)

        result = parse("42")
        assert result.is_ok() and result.unwrap() == 42

    def test_result_wrap_failure(self):
        @result_wrap(ValueError)
        def parse(s: str) -> int:
            return int(s)

        result = parse("abc")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)

    def test_result_wrap_unhandled_reraises(self):
        @result_wrap(ValueError)
        def risky(x: int) -> int:
            if x == 0:
                raise ZeroDivisionError("zero!")
            return x

        with pytest.raises(ZeroDivisionError):
            risky(0)

    def test_pipeline_success(self):
        result = process_pipeline("100", "4")
        assert result.is_ok()
        assert abs(result.unwrap() - 5.0) < 0.0001

    def test_pipeline_invalid_input(self):
        assert process_pipeline("abc", "4").is_err()

    def test_pipeline_division_by_zero(self):
        assert process_pipeline("100", "0").is_err()

    def test_pipeline_negative_sqrt(self):
        assert process_pipeline("-100", "4").is_err()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Bài 3: Typed Repository Pattern

**Mô tả:** Implement type-safe Repository pattern với Generics, Protocol, và proper type annotations.

```python
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Generic, TypeVar, Protocol, runtime_checkable, Callable


@dataclass
class Entity:
    id: str


@dataclass
class User(Entity):
    name: str
    email: str
    age: int
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.email or "@" not in self.email:
            raise ValueError(f"Invalid email: {self.email}")
        if not (0 <= self.age <= 150):
            raise ValueError(f"Invalid age: {self.age}")


@dataclass
class Product(Entity):
    name: str
    price: float
    category: str
    stock: int = 0

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError(f"Price cannot be negative: {self.price}")


T = TypeVar("T", bound=Entity)


@runtime_checkable
class Repository(Protocol[T]):
    def find_by_id(self, entity_id: str) -> T | None: ...
    def find_all(self) -> list[T]: ...
    def save(self, entity: T) -> T: ...
    def delete(self, entity_id: str) -> bool: ...
    def count(self) -> int: ...


class InMemoryRepository(Generic[T]):
    """
    Generic in-memory repository.

    TODO: Implement all methods.
    Note: `update()` dùng `dataclasses.replace(entity, **kwargs)` để tạo bản sao với fields đã update.
    """

    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def find_by_id(self, entity_id: str) -> T | None:
        # TODO
        pass

    def find_all(self) -> list[T]:
        # TODO
        pass

    def save(self, entity: T) -> T:
        # TODO: self._store[entity.id] = entity; return entity
        pass

    def delete(self, entity_id: str) -> bool:
        # TODO
        pass

    def count(self) -> int:
        # TODO
        pass

    def find_where(self, predicate: Callable[[T], bool]) -> list[T]:
        # TODO: Return list of entities where predicate(entity) is True
        pass

    def find_one_where(self, predicate: Callable[[T], bool]) -> T | None:
        # TODO: Return first match or None
        pass

    def update(self, entity_id: str, **kwargs) -> T | None:
        """
        Update entity fields.
        Dùng: replace(entity, **kwargs) từ dataclasses module.
        """
        # TODO: find, replace, store back, return updated
        pass


class UserRepository(InMemoryRepository[User]):
    def find_by_email(self, email: str) -> User | None:
        return self.find_one_where(lambda u: u.email.lower() == email.lower())

    def find_active(self) -> list[User]:
        return self.find_where(lambda u: u.is_active)

    def find_by_age_range(self, min_age: int, max_age: int) -> list[User]:
        return self.find_where(lambda u: min_age <= u.age <= max_age)

    def deactivate(self, user_id: str) -> User | None:
        return self.update(user_id, is_active=False)

    def email_exists(self, email: str) -> bool:
        return self.find_by_email(email) is not None


class ProductRepository(InMemoryRepository[Product]):
    def find_by_category(self, category: str) -> list[Product]:
        return self.find_where(lambda p: p.category == category)

    def find_in_stock(self) -> list[Product]:
        return self.find_where(lambda p: p.stock > 0)

    def find_by_price_range(self, min_price: float, max_price: float) -> list[Product]:
        return self.find_where(lambda p: min_price <= p.price <= max_price)

    def update_stock(self, product_id: str, delta: int) -> Product | None:
        product = self.find_by_id(product_id)
        if product is None:
            return None
        return self.update(product_id, stock=max(0, product.stock + delta))


# ============================================================
# Tests
# ============================================================

import pytest


class TestInMemoryRepository:

    def setup_method(self) -> None:
        self.repo: InMemoryRepository[User] = InMemoryRepository()
        for user in [
            User("1", "Alice", "alice@example.com", 30),
            User("2", "Bob", "bob@example.com", 25),
            User("3", "Charlie", "charlie@example.com", 35, is_active=False),
        ]:
            self.repo.save(user)

    def test_save_and_find(self):
        new_user = User("4", "Dave", "dave@example.com", 28)
        self.repo.save(new_user)
        found = self.repo.find_by_id("4")
        assert found is not None and found.name == "Dave"

    def test_find_all_count(self):
        assert len(self.repo.find_all()) == 3
        assert self.repo.count() == 3

    def test_find_by_id_not_found(self):
        assert self.repo.find_by_id("999") is None

    def test_delete_existing(self):
        assert self.repo.delete("1") is True
        assert self.repo.find_by_id("1") is None
        assert self.repo.count() == 2

    def test_delete_nonexistent(self):
        assert self.repo.delete("999") is False

    def test_find_where(self):
        active = self.repo.find_where(lambda u: u.is_active)
        assert len(active) == 2

    def test_find_one_where_found(self):
        user = self.repo.find_one_where(lambda u: u.name == "Bob")
        assert user is not None and user.email == "bob@example.com"

    def test_find_one_where_not_found(self):
        assert self.repo.find_one_where(lambda u: u.name == "Zach") is None

    def test_update(self):
        updated = self.repo.update("1", name="Alice Smith", age=31)
        assert updated is not None
        assert updated.name == "Alice Smith"
        assert updated.age == 31
        assert updated.email == "alice@example.com"  # Unchanged

    def test_update_persisted(self):
        self.repo.update("1", name="Alice Updated")
        found = self.repo.find_by_id("1")
        assert found is not None and found.name == "Alice Updated"

    def test_update_nonexistent(self):
        assert self.repo.update("999", name="Ghost") is None


class TestUserRepository:

    def setup_method(self) -> None:
        self.repo = UserRepository()
        for user in [
            User("1", "Alice", "alice@example.com", 30),
            User("2", "Bob", "BOB@EXAMPLE.COM", 25),
            User("3", "Charlie", "charlie@example.com", 35, is_active=False),
            User("4", "Dave", "dave@example.com", 22),
        ]:
            self.repo.save(user)

    def test_find_by_email_case_insensitive(self):
        user = self.repo.find_by_email("bob@example.com")
        assert user is not None and user.name == "Bob"

    def test_find_active(self):
        active = self.repo.find_active()
        names = {u.name for u in active}
        assert "Alice" in names and "Charlie" not in names

    def test_find_by_age_range(self):
        users = self.repo.find_by_age_range(25, 30)
        assert {u.name for u in users} == {"Alice", "Bob"}

    def test_deactivate(self):
        updated = self.repo.deactivate("1")
        assert updated is not None and updated.is_active is False
        found = self.repo.find_by_id("1")
        assert found is not None and found.is_active is False

    def test_email_exists(self):
        assert self.repo.email_exists("alice@example.com") is True
        assert self.repo.email_exists("unknown@example.com") is False


class TestProtocolCompliance:

    def test_repository_protocol(self):
        assert isinstance(UserRepository(), Repository)
        assert isinstance(ProductRepository(), Repository)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```
