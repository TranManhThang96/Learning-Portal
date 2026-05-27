# Ngày 12: Bài Tập Database với Python

**Scope 2 giờ:** Bài 1 là bắt buộc. Bài 2 làm phần model + query chống N+1 nếu còn thời gian. Bài 3 Redis là optional lab, tách khỏi Alembic/SQLAlchemy core để tránh biến ngày học thành project caching đầy đủ.

## Bài 1 (Cơ bản): UserRepository với SQLAlchemy Async

**Mục tiêu:** Implement đầy đủ UserRepository với SQLAlchemy 2.0 async, thực hành CRUD operations và hiểu cách sessions hoạt động.

**Setup:**

```bash
uv add sqlalchemy aiosqlite pytest pytest-asyncio
```

**Cấu trúc project:**

```
day11_ex1/
├── src/
│   ├── __init__.py
│   ├── database.py       # Engine, session setup
│   ├── models.py         # User model
│   └── user_repository.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_user_repository.py
└── pyproject.toml
```

**Bước 1 - `src/database.py`:**

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./dev.db"

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_tables() -> None:
    """Tạo tất cả tables trong DB."""
    from src.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop tất cả tables."""
    from src.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

**Bước 2 - `src/models.py`:**

```python
# src/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} email={self.email!r}>"
```

**Bước 3 - `src/user_repository.py` (Cần implement):**

```python
# src/user_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_
from src.models import User


class UserNotFoundError(Exception):
    pass


class EmailAlreadyExistsError(Exception):
    pass


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, name: str, email: str, age: int | None = None) -> User:
        """
        TODO: Implement
        1. Kiểm tra email đã tồn tại chưa -> raise EmailAlreadyExistsError nếu rồi
        2. Tạo User object và add vào session
        3. flush() để write vào DB (chưa commit)
        4. refresh() để load server-side defaults (id, created_at)
        5. Return user
        """
        raise NotImplementedError

    async def get_by_id(self, user_id: int) -> User | None:
        """
        TODO: Implement
        Dùng session.get() - cách ngắn nhất để get by primary key
        """
        raise NotImplementedError

    async def get_by_email(self, email: str) -> User | None:
        """
        TODO: Implement
        Dùng select(User).where(User.email == email)
        """
        raise NotImplementedError

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> list[User]:
        """
        TODO: Implement
        Hỗ trợ pagination (skip/limit) và filter active_only
        Order by created_at descending
        """
        raise NotImplementedError

    async def update(self, user_id: int, **kwargs) -> User:
        """
        TODO: Implement
        1. Get user by id -> raise UserNotFoundError nếu không tìm thấy
        2. Update các fields được truyền vào kwargs
        3. flush() + refresh()
        4. Return updated user

        Chú ý: Không cho phép update 'id' và 'created_at'
        """
        raise NotImplementedError

    async def deactivate(self, user_id: int) -> User:
        """
        TODO: Implement
        Set is_active = False cho user với user_id
        Raise UserNotFoundError nếu không tìm thấy
        """
        raise NotImplementedError

    async def delete(self, user_id: int) -> bool:
        """
        TODO: Implement
        Xóa user. Return True nếu đã xóa, False nếu không tìm thấy.
        """
        raise NotImplementedError

    async def count(self, active_only: bool = False) -> int:
        """
        TODO: Implement
        Đếm số users. Hỗ trợ filter active_only.
        """
        raise NotImplementedError

    async def search(self, query: str) -> list[User]:
        """
        TODO: Implement
        Tìm users có name hoặc email chứa query string (case-insensitive)
        Dùng ilike() cho case-insensitive search
        """
        raise NotImplementedError
```

**Bước 4 - `tests/conftest.py`:**

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from src.models import Base


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine):
    """Fresh session với rollback sau mỗi test."""
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.rollback()
```

**Bước 5 - `tests/test_user_repository.py` (Viết tests để verify implementation):**

```python
# tests/test_user_repository.py
import pytest
from src.user_repository import UserRepository, UserNotFoundError, EmailAlreadyExistsError


class TestCreate:
    async def test_create_returns_user_with_id(self, session):
        repo = UserRepository(session)
        user = await repo.create("Alice", "alice@test.com")
        assert user.id is not None
        assert user.name == "Alice"
        assert user.email == "alice@test.com"
        assert user.is_active is True

    async def test_create_duplicate_email_raises(self, session):
        repo = UserRepository(session)
        await repo.create("Alice", "alice@test.com")
        with pytest.raises(EmailAlreadyExistsError):
            await repo.create("Alice2", "alice@test.com")

    async def test_create_with_age(self, session):
        repo = UserRepository(session)
        user = await repo.create("Bob", "bob@test.com", age=25)
        assert user.age == 25

    async def test_create_without_age(self, session):
        repo = UserRepository(session)
        user = await repo.create("Charlie", "charlie@test.com")
        assert user.age is None


class TestRead:
    async def test_get_by_id_existing(self, session):
        repo = UserRepository(session)
        created = await repo.create("Alice", "alice@test.com")
        found = await repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_by_id_not_found(self, session):
        repo = UserRepository(session)
        found = await repo.get_by_id(99999)
        assert found is None

    async def test_get_by_email(self, session):
        repo = UserRepository(session)
        await repo.create("Alice", "alice@test.com")
        user = await repo.get_by_email("alice@test.com")
        assert user is not None
        assert user.email == "alice@test.com"

    async def test_get_all_empty(self, session):
        repo = UserRepository(session)
        users = await repo.get_all()
        assert users == []

    async def test_get_all_with_pagination(self, session):
        repo = UserRepository(session)
        for i in range(5):
            await repo.create(f"User{i}", f"user{i}@test.com")

        first_page = await repo.get_all(skip=0, limit=3)
        second_page = await repo.get_all(skip=3, limit=3)

        assert len(first_page) == 3
        assert len(second_page) == 2

    async def test_get_all_active_only(self, session):
        repo = UserRepository(session)
        u1 = await repo.create("Active", "active@test.com")
        u2 = await repo.create("Inactive", "inactive@test.com")
        await repo.deactivate(u2.id)

        all_users = await repo.get_all(active_only=False)
        active_users = await repo.get_all(active_only=True)

        assert len(all_users) >= 2
        assert all(u.is_active for u in active_users)


class TestUpdate:
    async def test_update_name(self, session):
        repo = UserRepository(session)
        user = await repo.create("Old Name", "update@test.com")
        updated = await repo.update(user.id, name="New Name")
        assert updated.name == "New Name"
        assert updated.email == "update@test.com"  # Không thay đổi

    async def test_update_nonexistent_raises(self, session):
        repo = UserRepository(session)
        with pytest.raises(UserNotFoundError):
            await repo.update(99999, name="New Name")

    async def test_update_cannot_change_id(self, session):
        repo = UserRepository(session)
        user = await repo.create("Alice", "alice@test.com")
        original_id = user.id
        # id không được thay đổi dù truyền vào
        updated = await repo.update(user.id, id=9999, name="Alice Updated")
        assert updated.id == original_id


class TestDelete:
    async def test_delete_existing(self, session):
        repo = UserRepository(session)
        user = await repo.create("Delete Me", "delete@test.com")
        result = await repo.delete(user.id)
        assert result is True
        assert await repo.get_by_id(user.id) is None

    async def test_delete_nonexistent(self, session):
        repo = UserRepository(session)
        result = await repo.delete(99999)
        assert result is False


class TestSearch:
    async def test_search_by_name(self, session):
        repo = UserRepository(session)
        await repo.create("Nguyen Van A", "nguyenvana@test.com")
        await repo.create("Tran Thi B", "tranthib@test.com")

        results = await repo.search("nguyen")
        assert len(results) >= 1
        assert any("Nguyen" in u.name for u in results)

    async def test_search_case_insensitive(self, session):
        repo = UserRepository(session)
        await repo.create("Alice Smith", "alice.smith@test.com")

        results = await repo.search("ALICE")
        assert len(results) >= 1
```

**Tiêu chí hoàn thành:**
- [ ] Tất cả methods trong UserRepository được implement
- [ ] Tất cả tests pass
- [ ] Không có N+1 queries
- [ ] Exception handling đúng (EmailAlreadyExistsError, UserNotFoundError)

---

## Bài 2 (Trung bình): Blog System với N+1 Fix

**Mục tiêu:** Xây dựng blog system với User + Post models, xử lý N+1 problem bằng `selectinload`, implement pagination và filtering.

**Models:**

```python
# src/models.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, func
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="author",
        lazy="noload",
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    author: Mapped["User"] = relationship("User", back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        lazy="noload",
        cascade="all, delete-orphan",
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    author: Mapped["User"] = relationship("User", back_populates="comments")
```

**Nhiệm vụ - Implement `BlogService`:**

```python
# src/blog_service.py
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload, joinedload
from src.models import User, Post, Comment
import re


@dataclass
class PaginatedResult:
    items: list
    total: int
    skip: int
    limit: int

    @property
    def has_next(self) -> bool:
        return self.skip + self.limit < self.total

    @property
    def has_prev(self) -> bool:
        return self.skip > 0


def slugify(title: str) -> str:
    """Convert title thành URL slug."""
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


class BlogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(self, username: str, email: str, bio: str | None = None) -> User:
        """TODO: Implement - tạo user, check duplicate username/email."""
        raise NotImplementedError

    async def create_post(
        self,
        user_id: int,
        title: str,
        content: str,
        published: bool = False,
    ) -> Post:
        """
        TODO: Implement
        - Tạo slug từ title (dùng hàm slugify)
        - Xử lý duplicate slug (thêm -1, -2, v.v.)
        - Set is_published = published
        """
        raise NotImplementedError

    async def get_posts_paginated(
        self,
        skip: int = 0,
        limit: int = 10,
        published_only: bool = True,
        user_id: int | None = None,
    ) -> PaginatedResult:
        """
        TODO: Implement
        - Trả về posts với author info (dùng joinedload cho many-to-one)
        - Hỗ trợ filter published_only và user_id
        - Đếm total count cho pagination
        - Order by created_at DESC
        """
        raise NotImplementedError

    async def get_post_with_comments(self, post_id: int) -> Post | None:
        """
        TODO: Implement
        Load post + comments + comment authors (nested selectinload)
        Tăng view_count thêm 1 (atomic update)

        Gợi ý:
        selectinload(Post.comments).selectinload(Comment.author)
        """
        raise NotImplementedError

    async def get_users_with_post_counts(self) -> list[dict]:
        """
        TODO: Implement - sử dụng SQL aggregation
        Trả về list [{user, post_count}]

        Gợi ý: dùng func.count() với GROUP BY
        SELECT users.*, COUNT(posts.id) as post_count
        FROM users LEFT JOIN posts ON posts.user_id = users.id
        GROUP BY users.id
        """
        raise NotImplementedError

    async def add_comment(self, post_id: int, user_id: int, content: str) -> Comment:
        """TODO: Implement"""
        raise NotImplementedError

    async def get_user_feed(self, user_id: int, limit: int = 20) -> list[Post]:
        """
        TODO: Implement
        Lấy posts mới nhất (published), kèm author info.
        Không bao gồm posts của chính user_id đó.
        """
        raise NotImplementedError
```

**Tests để verify (viết trong `tests/test_blog_service.py`):**

```python
import pytest
from src.blog_service import BlogService


class TestCreatePost:
    async def test_slug_generation(self, session):
        service = BlogService(session)
        user = await service.create_user("alice", "alice@test.com")
        post = await service.create_post(user.id, "Hello World", "Content")
        assert post.slug == "hello-world"

    async def test_duplicate_slug_gets_suffix(self, session):
        service = BlogService(session)
        user = await service.create_user("alice2", "alice2@test.com")
        post1 = await service.create_post(user.id, "Hello World", "Content 1")
        post2 = await service.create_post(user.id, "Hello World", "Content 2")
        assert post1.slug != post2.slug
        assert "hello-world" in post2.slug


class TestPagination:
    async def test_paginated_result(self, session):
        service = BlogService(session)
        user = await service.create_user("blogger", "blogger@test.com")
        for i in range(5):
            await service.create_post(user.id, f"Post {i}", "content", published=True)

        result = await service.get_posts_paginated(skip=0, limit=3, published_only=True)
        assert len(result.items) == 3
        assert result.total == 5
        assert result.has_next is True
        assert result.has_prev is False

    async def test_no_n1_queries(self, session):
        """
        Verify không có N+1 queries bằng cách dùng SQLAlchemy event hoặc
        đơn giản là kiểm tra author được load cho mỗi post.
        """
        service = BlogService(session)
        user = await service.create_user("n1user", "n1user@test.com")
        for i in range(3):
            await service.create_post(user.id, f"N1 Post {i}", "content", published=True)

        result = await service.get_posts_paginated(published_only=True)
        # Verify author được load (không trigger lazy load)
        for post in result.items:
            assert post.author is not None
            assert post.author.username is not None


class TestPostWithComments:
    async def test_loads_comments_with_authors(self, session):
        service = BlogService(session)
        user = await service.create_user("author_u", "author_u@test.com")
        commenter = await service.create_user("commenter", "commenter@test.com")
        post = await service.create_post(user.id, "Test Post", "content", published=True)
        await service.add_comment(post.id, commenter.id, "Great post!")

        loaded_post = await service.get_post_with_comments(post.id)
        assert loaded_post is not None
        assert len(loaded_post.comments) == 1
        assert loaded_post.comments[0].author.username == "commenter"

    async def test_increments_view_count(self, session):
        service = BlogService(session)
        user = await service.create_user("viewuser", "viewuser@test.com")
        post = await service.create_post(user.id, "View Test", "content", published=True)
        initial_views = post.view_count

        await service.get_post_with_comments(post.id)
        await service.get_post_with_comments(post.id)

        updated_post = await service.get_post_with_comments(post.id)
        assert updated_post.view_count >= initial_views + 2
```

**Tiêu chí hoàn thành:**
- [ ] Tất cả methods implement xong
- [ ] Không có N+1 queries (sử dụng selectinload/joinedload đúng cách)
- [ ] Pagination hoạt động đúng (skip, limit, total, has_next, has_prev)
- [ ] Slug generation và deduplication hoạt động
- [ ] Tất cả tests pass

---

## Bài 3 (Optional/Nâng cao): Redis Caching Layer với Cache-Aside Pattern

> Làm bài này như lab riêng. Trong ngày 12, chỉ cần hiểu cache-aside cơ bản (`get` → miss → DB → `set` + TTL). Distributed lock, rate limiting, tag-based invalidation, và Pub/Sub là deep dive.

**Mục tiêu:** Implement Redis caching layer cho Blog API, ưu tiên cache-aside pattern, cache invalidation, và TTL. Distributed lock/rate limiting là phần bonus.

**Setup:**

```bash
uv add redis[hiredis] pytest-asyncio fakeredis
# fakeredis: Redis giả lập cho tests, không cần Redis thật
```

**Nhiệm vụ:**

**Phần A - `src/cache_manager.py`:**

```python
# src/cache_manager.py
import json
import hashlib
from typing import Any, Callable, TypeVar
from functools import wraps
import redis.asyncio as redis
from datetime import timedelta


T = TypeVar("T")


class CacheManager:
    """
    Comprehensive Redis cache manager.
    Tương đương CacheModule trong NestJS + custom Redis service.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    async def get(self, key: str) -> Any | None:
        """TODO: Implement - get + JSON deserialize + track stats"""
        raise NotImplementedError

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | timedelta | None = None,
    ) -> None:
        """TODO: Implement - JSON serialize + set with optional TTL + track stats"""
        raise NotImplementedError

    async def delete(self, *keys: str) -> int:
        """TODO: Implement - delete keys + track stats. Return số keys đã xóa."""
        raise NotImplementedError

    async def delete_pattern(self, pattern: str) -> int:
        """
        TODO: Implement
        Dùng SCAN thay vì KEYS cho production-safe pattern deletion.
        SCAN: non-blocking, chia nhỏ thành nhiều operations.

        Gợi ý:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += await self.redis.delete(*keys)
            if cursor == 0:
                break
        return deleted
        """
        raise NotImplementedError

    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: int = 300,
    ) -> Any:
        """
        TODO: Implement Cache-aside trong một method.
        1. Try get from cache
        2. If miss: call factory() to get data
        3. Set in cache
        4. Return data
        """
        raise NotImplementedError

    def get_stats(self) -> dict:
        """Return cache stats: hits, misses, hit_rate, sets, deletes."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {**self._stats, "hit_rate": round(hit_rate, 3)}

    async def invalidate_tags(self, *tags: str) -> int:
        """
        Tag-based invalidation: xóa tất cả cache entries có tag cụ thể.

        TODO: Implement
        Cách làm:
        - Mỗi tag được store trong Redis Set: "tag:{tag_name}" -> set of keys
        - Khi set cache với tag, thêm key vào tag set
        - Khi invalidate tag, lấy tất cả keys từ tag set và delete chúng

        Gợi ý:
        for tag in tags:
            tag_key = f"tag:{tag}"
            keys = await self.redis.smembers(tag_key)
            if keys:
                await self.redis.delete(*keys, tag_key)
        """
        raise NotImplementedError

    async def set_with_tags(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        tags: list[str] | None = None,
    ) -> None:
        """
        TODO: Implement
        Set value trong cache VÀ register key trong tag sets.
        """
        raise NotImplementedError
```

**Phần B - `src/rate_limiter.py`:**

```python
# src/rate_limiter.py
import redis.asyncio as redis
import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp khi counter reset


class RateLimiter:
    """
    Fixed window rate limiter dùng Redis.
    Tương đương @nestjs/throttler trong NestJS.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def check(
        self,
        identifier: str,  # VD: user_id hoặc IP address
        limit: int = 100,
        window: int = 60,  # Giây
        action: str = "default",
    ) -> RateLimitResult:
        """
        TODO: Implement Fixed Window Rate Limiting

        Algorithm:
        1. key = f"ratelimit:{action}:{identifier}:{current_window}"
        2. current_window = int(time.time()) // window
        3. count = INCR key
        4. Nếu count == 1: EXPIRE key window (set TTL lần đầu)
        5. Tính reset_at = (current_window + 1) * window

        Return RateLimitResult với allowed = count <= limit
        """
        raise NotImplementedError

    async def reset(self, identifier: str, action: str = "default") -> None:
        """TODO: Implement - reset rate limit counter cho identifier."""
        raise NotImplementedError


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter - chính xác hơn fixed window.
    Dùng sorted set để track timestamps.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def check(
        self,
        identifier: str,
        limit: int = 100,
        window: int = 60,
    ) -> RateLimitResult:
        """
        TODO: Implement Sliding Window Rate Limiting

        Algorithm:
        1. key = f"sliding:{identifier}"
        2. now = time.time()
        3. window_start = now - window
        4. Dùng pipeline:
           - ZREMRANGEBYSCORE key -inf window_start  (xóa entries cũ)
           - ZADD key now now  (thêm request hiện tại với score=timestamp)
           - ZCARD key  (đếm số requests trong window)
           - EXPIRE key window
        5. count = result của ZCARD
        6. Return RateLimitResult
        """
        raise NotImplementedError
```

**Phần C - `src/cached_blog_service.py`:**

```python
# src/cached_blog_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.blog_service import BlogService
from src.cache_manager import CacheManager
from src.models import Post


class CachedBlogService:
    """
    Blog service với caching layer.
    Implement cache-aside pattern với tag-based invalidation.
    """

    POST_TTL = 300      # 5 phút
    LIST_TTL = 60       # 1 phút
    USER_TTL = 600      # 10 phút

    def __init__(self, session: AsyncSession, cache: CacheManager) -> None:
        self.blog = BlogService(session)
        self.cache = cache

    async def get_post(self, post_id: int) -> Post | None:
        """
        TODO: Implement với cache-aside:
        - key = f"post:{post_id}"
        - tags = [f"post:{post_id}", "posts"]
        - TTL = POST_TTL

        Chú ý: Post object không thể serialize trực tiếp.
        Cần convert sang dict trước khi cache.
        """
        raise NotImplementedError

    async def get_posts_list(
        self,
        skip: int = 0,
        limit: int = 10,
        published_only: bool = True,
    ) -> dict:
        """
        TODO: Implement với caching cho list
        Cache key phải bao gồm tất cả params: skip, limit, published_only
        Tag: "posts" để dễ invalidate toàn bộ list cache
        """
        raise NotImplementedError

    async def create_post(
        self,
        user_id: int,
        title: str,
        content: str,
        published: bool = False,
    ) -> Post:
        """
        TODO: Implement
        Sau khi tạo post:
        - Invalidate tag "posts" (tất cả list caches)
        - Invalidate tag f"user:{user_id}:posts"
        """
        raise NotImplementedError

    async def update_post(self, post_id: int, **kwargs) -> Post | None:
        """
        TODO: Implement
        Sau khi update:
        - Invalidate cache của post cụ thể
        - Invalidate list caches
        """
        raise NotImplementedError

    async def delete_post(self, post_id: int) -> bool:
        """
        TODO: Implement với cache invalidation
        """
        raise NotImplementedError
```

**Phần D - Tests với `fakeredis`:**

```python
# tests/test_cache_manager.py
import pytest
import pytest_asyncio
import fakeredis.redis
from src.cache_manager import CacheManager
from src.rate_limiter import RateLimiter


@pytest_asyncio.fixture
async def fake_redis():
    """Fake Redis server cho tests - không cần Redis thật."""
    client = fakeredis.redis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
def cache(fake_redis):
    return CacheManager(fake_redis)


class TestCacheManager:
    async def test_get_returns_none_for_missing_key(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    async def test_set_and_get(self, cache):
        await cache.set("key1", {"name": "Alice", "age": 30})
        result = await cache.get("key1")
        assert result == {"name": "Alice", "age": 30}

    async def test_set_with_ttl(self, cache, fake_redis):
        await cache.set("temp_key", "value", ttl=60)
        ttl = await fake_redis.ttl("temp_key")
        assert ttl > 0
        assert ttl <= 60

    async def test_delete_existing_key(self, cache):
        await cache.set("to_delete", "value")
        deleted = await cache.delete("to_delete")
        assert deleted == 1
        assert await cache.get("to_delete") is None

    async def test_delete_pattern(self, cache):
        await cache.set("user:1", "Alice")
        await cache.set("user:2", "Bob")
        await cache.set("post:1", "Hello")

        deleted = await cache.delete_pattern("user:*")
        assert deleted == 2
        assert await cache.get("user:1") is None
        assert await cache.get("post:1") == "Hello"

    async def test_get_or_set_on_miss(self, cache):
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return {"data": "from db"}

        result1 = await cache.get_or_set("key", factory, ttl=60)
        result2 = await cache.get_or_set("key", factory, ttl=60)

        assert result1 == {"data": "from db"}
        assert result2 == {"data": "from db"}
        assert call_count == 1  # Factory chỉ gọi 1 lần

    async def test_stats_tracking(self, cache):
        await cache.set("k1", "v1")
        await cache.get("k1")    # hit
        await cache.get("k2")    # miss
        await cache.delete("k1")  # delete

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["deletes"] == 1
        assert stats["hit_rate"] == 0.5

    async def test_tag_based_invalidation(self, cache):
        await cache.set_with_tags("post:1", {"id": 1}, tags=["posts", "user:1:posts"])
        await cache.set_with_tags("post:2", {"id": 2}, tags=["posts", "user:2:posts"])

        # Invalidate tất cả posts
        await cache.invalidate_tags("posts")

        assert await cache.get("post:1") is None
        assert await cache.get("post:2") is None


class TestRateLimiter:
    @pytest_asyncio.fixture
    def limiter(self, fake_redis):
        return RateLimiter(fake_redis)

    async def test_allows_within_limit(self, limiter):
        for _ in range(5):
            result = await limiter.check("user:1", limit=10, window=60)
            assert result.allowed is True

    async def test_blocks_over_limit(self, limiter):
        for _ in range(10):
            await limiter.check("user:2", limit=10, window=60)

        result = await limiter.check("user:2", limit=10, window=60)
        assert result.allowed is False
        assert result.remaining == 0

    async def test_remaining_decrements(self, limiter):
        r1 = await limiter.check("user:3", limit=5, window=60)
        r2 = await limiter.check("user:3", limit=5, window=60)

        assert r1.remaining == 4
        assert r2.remaining == 3

    async def test_different_identifiers_independent(self, limiter):
        for _ in range(10):
            await limiter.check("user:4", limit=10, window=60)

        # user:5 chưa dùng, phải được phép
        result = await limiter.check("user:5", limit=10, window=60)
        assert result.allowed is True

    async def test_reset(self, limiter):
        for _ in range(10):
            await limiter.check("user:6", limit=10, window=60)

        await limiter.reset("user:6")
        result = await limiter.check("user:6", limit=10, window=60)
        assert result.allowed is True
```

**Tiêu chí hoàn thành:**
- [ ] CacheManager: get/set/delete/delete_pattern/get_or_set/stats/tag invalidation
- [ ] RateLimiter: fixed window rate limiting hoạt động đúng
- [ ] CachedBlogService: cache-aside pattern với tag invalidation
- [ ] Tất cả tests với fakeredis pass
- [ ] delete_pattern dùng SCAN (không dùng KEYS)
- [ ] Stats tracking chính xác

**Chạy tests:**

```bash
pytest tests/test_cache_manager.py -v --asyncio-mode=auto
```
