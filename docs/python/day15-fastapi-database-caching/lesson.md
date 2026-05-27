# Ngày 15: FastAPI + Database + Caching

## 🎯 Mục tiêu học tập

Sau ngày 14, bạn sẽ có thể:

- Xây dựng full-stack dependency injection chain: `get_db` → `Repository` → `Service` trong FastAPI
- Implement pagination API với `PaginatedResponse[T]` Generic model, cả offset-based và cursor-based
- Phát hiện và sửa N+1 Query Problem với SQLAlchemy `selectinload`, `joinedload`, và explicit JOIN
- Implement Redis cache-aside cơ bản và cache invalidation cho single-object lookup
- Nhận biết thundering herd problem; distributed lock là optional deep dive

**Primary app flow trong 2 giờ:**

1. `GET /users` dùng `Depends(get_db)` → `UserRepository` → `PaginatedResponse[UserResponse]`.
2. Thêm endpoint posts để tái hiện N+1, đo SQL log, rồi sửa bằng eager loading.
3. Nếu còn thời gian, thêm Redis cache-aside cho `GET /users/{id}` và invalidate khi update. Write-through, distributed lock, cache stats dashboard, và gRPC là optional.

---

## 🔄 So sánh với NestJS + TypeORM/Prisma + Redis

| Khái niệm NestJS | Tương đương Python/FastAPI | Ghi chú |
|---|---|---|
| `TypeORM Repository` | `SQLAlchemy AsyncSession` + custom Repository class | Python không có built-in `@InjectRepository()` |
| `@InjectRepository(User)` | `Depends(get_db)` + `UserRepository(db)` | Dependency injection thủ công, explicit hơn |
| Prisma `include: { posts: true }` | `selectinload(User.posts)` hoặc `joinedload` | SQLAlchemy eager loading |
| TypeORM `relations: ["posts"]` | `relationship("Post", back_populates="user")` | Khai báo trong model |
| `cache-manager` (NestJS) | `redis.asyncio` | Python async Redis client trong redis-py |
| `@CacheKey()` / `@CacheTTL()` | Tự implement cache-aside pattern | Không có decorator magic, nhưng explicit hơn |
| Prisma `findMany({ skip, take })` | `select().offset(skip).limit(limit)` | SQLAlchemy query builder |
| TypeORM `findAndCount()` | `select(func.count())` + `select(User)` | 2 queries riêng biệt trong SQLAlchemy |

**Tư duy chính:** NestJS/TypeORM ẩn nhiều complexity trong decorators. SQLAlchemy buộc bạn viết explicit — verbose hơn nhưng bạn biết chính xác SQL nào được chạy.

---

## 📖 Lý thuyết

### Section 1: Full Stack Dependency Injection

#### Cấu trúc layer

```
Request → Router → Dependency → Service → Repository → Database
                     (get_db,        (business         (SQLAlchemy
                      get_service)     logic)            queries)
```

#### database.py — Engine và Session factory

```python
# src/myapp/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from myapp.config import get_settings

settings = get_settings()

# create_async_engine cho async I/O — KHÔNG dùng create_engine với async frameworks
engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DB_POOL_SIZE,       # Số connections trong pool
    max_overflow=10,                        # Connections thêm khi pool đầy
    pool_pre_ping=True,                     # Ping DB trước khi lấy connection từ pool
    echo=settings.DEBUG,                   # Log SQL queries khi DEBUG=True
)

# async_sessionmaker tạo session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # QUAN TRỌNG: Không expire objects sau commit (tránh lazy load error)
)


class Base(DeclarativeBase):
    pass
```

#### dependencies.py — Dependency chain

```python
# src/myapp/dependencies.py
from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.database import AsyncSessionLocal
from myapp.users.repository import UserRepository
from myapp.users.service import UserService
from myapp.cache import CacheService


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    Dependency tạo DB session cho mỗi request.
    Session tự động đóng sau khi request kết thúc (dù thành công hay lỗi).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_user_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRepository:
    """Tạo UserRepository với DB session hiện tại."""
    return UserRepository(db)


async def get_cache_service() -> CacheService:
    """Trả về CacheService singleton (redis connection pool shared)."""
    from myapp.cache import cache_service
    return cache_service


async def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> UserService:
    """Tạo UserService với repository và cache service."""
    return UserService(repo, cache)


# Type aliases để dùng trong route handlers
DBDep = Annotated[AsyncSession, Depends(get_db)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

#### UserService với cache-aside pattern

```python
# src/myapp/users/service.py
import json
from typing import Optional

import structlog

from myapp.users.models import User
from myapp.users.repository import UserRepository
from myapp.users.schemas import UserCreate, UserUpdate, PaginatedResponse, UserResponse
from myapp.cache import CacheService

logger = structlog.get_logger()


class UserService:
    CACHE_TTL = 300  # 5 phút
    CACHE_KEY_PREFIX = "user:"

    def __init__(self, repo: UserRepository, cache: CacheService):
        self.repo = repo
        self.cache = cache

    def _cache_key(self, user_id: int) -> str:
        return f"{self.CACHE_KEY_PREFIX}{user_id}"

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Cache-aside pattern:
        1. Kiểm tra cache
        2. Cache hit → trả về ngay
        3. Cache miss → lấy từ DB → lưu vào cache → trả về
        """
        cache_key = self._cache_key(user_id)

        # Bước 1: Check cache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            logger.debug("cache_hit", key=cache_key)
            return User(**json.loads(cached))  # Deserialize từ JSON

        logger.debug("cache_miss", key=cache_key)

        # Bước 2: Query DB
        user = await self.repo.get_by_id(user_id)
        if user is None:
            return None

        # Bước 3: Lưu vào cache
        await self.cache.set(
            cache_key,
            json.dumps({"id": user.id, "username": user.username, "email": user.email}),
            ttl=self.CACHE_TTL,
        )

        return user

    async def update(self, user_id: int, update_data: UserUpdate) -> Optional[User]:
        """Update user và invalidate cache."""
        user = await self.repo.update(user_id, update_data)
        if user:
            # Cache invalidation: xóa cache sau khi update
            await self.cache.delete(self._cache_key(user_id))
            logger.info("cache_invalidated", user_id=user_id)
        return user

    async def list_users(
        self, skip: int = 0, limit: int = 20
    ) -> PaginatedResponse[UserResponse]:
        """List users với pagination — không cache list queries."""
        total = await self.repo.count()
        users = await self.repo.list(skip=skip, limit=limit)

        return PaginatedResponse(
            items=[UserResponse.model_validate(u) for u in users],
            total=total,
            skip=skip,
            limit=limit,
        )
```

---

### Section 2: Pagination Patterns

#### PaginatedResponse[T] Generic model

```python
# src/myapp/schemas/pagination.py
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageInfo(BaseModel):
    total: int = Field(description="Tổng số items")
    skip: int = Field(ge=0, description="Số items bỏ qua")
    limit: int = Field(ge=1, le=100, description="Số items mỗi trang")
    has_next: bool = Field(description="Còn trang tiếp theo không")
    has_prev: bool = Field(description="Có trang trước không")

    @property
    def current_page(self) -> int:
        return (self.skip // self.limit) + 1

    @property
    def total_pages(self) -> int:
        if self.limit == 0:
            return 0
        return (self.total + self.limit - 1) // self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic pagination response dùng cho bất kỳ resource nào.

    Ví dụ dùng:
        PaginatedResponse[UserResponse]
        PaginatedResponse[PostResponse]
    """
    items: list[T]
    page_info: PageInfo

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        skip: int,
        limit: int,
    ) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            page_info=PageInfo(
                total=total,
                skip=skip,
                limit=limit,
                has_next=(skip + limit) < total,
                has_prev=skip > 0,
            ),
        )
```

#### Offset-based pagination — đơn giản, phổ biến

```python
# src/myapp/users/repository.py (phần pagination)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.users.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count(self, search: str | None = None) -> int:
        """Đếm tổng số users (có filter nếu cần)."""
        query = select(func.count(User.id))
        if search:
            query = query.where(User.username.ilike(f"%{search}%"))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> list[User]:
        """Lấy danh sách users với offset pagination."""
        query = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        if search:
            query = query.where(User.username.ilike(f"%{search}%"))
        result = await self.db.execute(query)
        return list(result.scalars().all())
```

**Route handler:**

```python
# src/myapp/users/router.py
from fastapi import APIRouter, Query
from myapp.dependencies import UserServiceDep
from myapp.users.schemas import UserResponse
from myapp.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    service: UserServiceDep,
    skip: int = Query(0, ge=0, description="Số records bỏ qua"),
    limit: int = Query(20, ge=1, le=100, description="Số records mỗi trang"),
    search: str | None = Query(None, description="Tìm theo username"),
):
    return await service.list_users(skip=skip, limit=limit, search=search)
```

**Response ví dụ:**
```json
{
  "items": [
    {"id": 1, "username": "alice", "email": "alice@example.com"},
    {"id": 2, "username": "bob", "email": "bob@example.com"}
  ],
  "page_info": {
    "total": 150,
    "skip": 0,
    "limit": 20,
    "has_next": true,
    "has_prev": false
  }
}
```

#### Cursor-based pagination — tốt hơn cho real-time data

```python
# Offset-based: trang 2 có thể bị lệch nếu có insert giữa 2 requests
# Cursor-based: dùng ID hoặc timestamp của item cuối làm "cursor"

from pydantic import BaseModel


class CursorPaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None  # None nếu đây là trang cuối
    prev_cursor: str | None
    has_more: bool


async def list_users_cursor(
    db: AsyncSession,
    cursor: str | None = None,  # ID của item cuối trên trang trước
    limit: int = 20,
    direction: str = "forward",  # "forward" hoặc "backward"
) -> CursorPaginatedResponse:
    query = select(User).order_by(User.id.asc()).limit(limit + 1)  # +1 để biết có trang tiếp

    if cursor:
        # Chỉ lấy items sau cursor
        cursor_id = int(cursor)
        if direction == "forward":
            query = query.where(User.id > cursor_id)
        else:
            query = query.where(User.id < cursor_id).order_by(User.id.desc())

    result = await db.execute(query)
    users = list(result.scalars().all())

    has_more = len(users) > limit
    if has_more:
        users = users[:limit]  # Bỏ item +1

    if direction == "backward":
        users.reverse()

    next_cursor = str(users[-1].id) if has_more else None
    prev_cursor = str(users[0].id) if cursor else None

    return CursorPaginatedResponse(
        items=users,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
        has_more=has_more,
    )


# So sánh:
# Offset pagination:  GET /users?skip=40&limit=20
# Cursor pagination:  GET /users?cursor=42&limit=20
#
# Offset:  Đơn giản, có thể "nhảy" đến trang bất kỳ, nhưng bị shift khi có insert/delete
# Cursor:  Consistent khi data thay đổi, không thể jump đến trang arbitrary
```

---

### Section 3: N+1 Query Problem

Đây là lỗi hiệu năng phổ biến nhất khi làm việc với ORM.

#### Setup — Models với relationships

```python
# src/myapp/models.py
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myapp.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)

    # Relationship — lazy load mặc định (CHỈ load khi access .posts)
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", lazy="select")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    author: Mapped["User"] = relationship("User", back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="post")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))

    post: Mapped["Post"] = relationship("Post", back_populates="comments")
```

#### BAD: N+1 Query Problem

```python
# BAD EXAMPLE — ĐỪNG LÀM NÀY
async def get_posts_with_authors_bad(db: AsyncSession) -> list[dict]:
    """
    Lấy 20 posts và author của mỗi post.

    Số queries: 1 (lấy posts) + 20 (mỗi post lấy author) = 21 queries!
    Với 100 posts = 101 queries. N posts = N+1 queries.
    """
    # Query 1: Lấy tất cả posts
    result = await db.execute(select(Post).limit(20))
    posts = result.scalars().all()

    post_list = []
    for post in posts:
        # Query 2, 3, 4... N+1: Mỗi lần access post.author → trigger lazy load query
        # KHÔNG hoạt động với async SQLAlchemy (lazy load bị disabled)
        # → Raise MissingGreenlet error!
        author = post.author  # ← MissingGreenlet: lazy load in async context

        post_list.append({
            "id": post.id,
            "title": post.title,
            "author_username": author.username,
        })

    return post_list
```

**Lỗi sẽ gặp:**
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

Async SQLAlchemy **không cho phép** lazy load — đây là tính năng bảo vệ, buộc bạn phải explicit về queries.

#### FIX 1: `selectinload` — 2 queries, tốt cho collections

```python
from sqlalchemy.orm import selectinload

async def get_posts_with_authors_selectinload(db: AsyncSession) -> list[Post]:
    """
    selectinload: Load relationship bằng SELECT ... WHERE id IN (1, 2, 3, ...)
    Phù hợp cho: one-to-many relationships (1 post → nhiều comments)

    Queries:
    1. SELECT * FROM posts LIMIT 20
    2. SELECT * FROM users WHERE id IN (1, 2, 3, ...)  -- tất cả authors một lần
    """
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.author))  # Eagerly load author
        .limit(20)
        .order_by(Post.created_at.desc())
    )
    return list(result.scalars().all())


# Load multiple levels:
async def get_posts_with_authors_and_comments(db: AsyncSession) -> list[Post]:
    """
    Queries:
    1. SELECT posts
    2. SELECT users WHERE id IN (...)
    3. SELECT comments WHERE post_id IN (...)
    """
    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.author),           # Load authors (User)
            selectinload(Post.comments),         # Load comments
        )
        .limit(20)
    )
    return list(result.scalars().all())
```

#### FIX 2: `joinedload` — 1 query với JOIN, tốt cho many-to-one

```python
from sqlalchemy.orm import joinedload

async def get_posts_joinedload(db: AsyncSession) -> list[Post]:
    """
    joinedload: Load relationship bằng LEFT OUTER JOIN trong cùng query.
    Phù hợp cho: many-to-one (nhiều posts → 1 author)

    Queries:
    1. SELECT posts.*, users.* FROM posts
       LEFT JOIN users ON posts.user_id = users.id
       LIMIT 20

    CHÚ Ý: joinedload với collections (one-to-many) tạo duplicate parent rows.
    → SQLAlchemy 2.0 yêu cầu Result.unique() explicit khi materialize.
    → LIMIT/OFFSET có thể khó đọc hơn; ưu tiên selectinload cho collections.
    """
    result = await db.execute(
        select(Post)
        .options(joinedload(Post.author))  # JOIN với users table
        .limit(20)
    )
    # unique() harmless ở many-to-one; bắt buộc khi joinedload collection
    return list(result.unique().scalars().all())
```

#### FIX 3: Explicit JOIN + Aggregate — khi cần aggregate data

```python
from sqlalchemy import func

async def get_posts_with_comment_count(db: AsyncSession) -> list[dict]:
    """
    Lấy posts kèm số lượng comments — dùng GROUP BY + COUNT.

    Không dùng selectinload/joinedload vì ta chỉ cần COUNT, không cần load Comment objects.

    Queries:
    1. SELECT posts.id, posts.title, users.username, COUNT(comments.id) as comment_count
       FROM posts
       JOIN users ON posts.user_id = users.id
       LEFT JOIN comments ON comments.post_id = posts.id
       GROUP BY posts.id, posts.title, users.username
       ORDER BY posts.created_at DESC
       LIMIT 20
    """
    result = await db.execute(
        select(
            Post.id,
            Post.title,
            Post.created_at,
            User.username.label("author_username"),
            func.count(Comment.id).label("comment_count"),
        )
        .join(User, Post.user_id == User.id)
        .outerjoin(Comment, Comment.post_id == Post.id)  # outerjoin = LEFT JOIN
        .group_by(Post.id, Post.title, Post.created_at, User.username)
        .order_by(Post.created_at.desc())
        .limit(20)
    )

    rows = result.all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "author": row.author_username,
            "comment_count": row.comment_count,
        }
        for row in rows
    ]
```

#### So sánh chiến lược

| Chiến lược | Số queries | Khi nào dùng |
|---|---|---|
| Lazy load | N+1 | KHÔNG dùng với async SQLAlchemy |
| `selectinload` | 2 | Collection relationships (one-to-many) |
| `joinedload` | 1 (JOIN) | Single object relationships (many-to-one) |
| Explicit JOIN | 1 | Cần aggregate, custom projection |
| `contains_eager` | 1 | Khi đã có JOIN và muốn populate relationship |

---

### Section 4: Redis Caching Patterns

> **Optional sau primary flow:** trong 2 giờ chỉ cần cache-aside cho single user + TTL + invalidate khi update. Write-through, pattern delete, distributed lock, và pool stats là advanced cache lab.

#### Setup Redis client

```python
# src/myapp/cache.py
import json
from typing import Any

import redis.asyncio as redis
from myapp.config import get_settings

settings = get_settings()

# Connection pool — shared toàn bộ application
redis_pool = redis.ConnectionPool.from_url(
    str(settings.REDIS_URL),
    max_connections=20,
    decode_responses=True,  # Auto decode bytes → str
)


class CacheService:
    def __init__(self):
        self._client = redis.Redis(connection_pool=redis_pool)

    async def get(self, key: str) -> str | None:
        """Lấy value từ cache. None nếu không tồn tại."""
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        """Set cache với TTL (giây)."""
        await self._client.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        """Xóa cache key."""
        await self._client.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Xóa tất cả keys khớp pattern. VD: delete_pattern('user:*')"""
        keys = await self._client.keys(pattern)
        if keys:
            return await self._client.delete(*keys)
        return 0

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def ping(self) -> bool:
        """Kiểm tra Redis connection còn sống không."""
        try:
            return await self._client.ping()
        except redis.RedisError:
            return False

    async def get_pool_stats(self) -> dict:
        """Thống kê connection pool cho health check."""
        info = await self._client.info("clients")
        return {
            "connected_clients": info.get("connected_clients"),
            "blocked_clients": info.get("blocked_clients"),
        }


# Singleton instance
cache_service = CacheService()
```

#### Pattern 1: Cache-Aside (Lazy Loading)

```python
# Đây là pattern phổ biến nhất
# Application chủ động quản lý cache, không phải cache layer

async def get_user_cached(user_id: int, db: AsyncSession, cache: CacheService) -> dict | None:
    """
    Cache-aside flow:
    Read:  App → Cache (hit? return) → DB → App → Cache (set) → return
    Write: App → DB → Cache (invalidate hoặc update)
    """
    cache_key = f"user:{user_id}"

    # 1. Đọc từ cache
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. Cache miss → đọc từ DB
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Cache negative result để tránh DB spam
        await cache.set(cache_key, json.dumps(None), ttl=60)
        return None

    # 3. Lưu vào cache
    user_data = {"id": user.id, "username": user.username, "email": user.email}
    await cache.set(cache_key, json.dumps(user_data), ttl=300)

    return user_data
```

#### Pattern 2 (Optional): Write-Through

```python
async def update_user_write_through(
    user_id: int,
    update_data: dict,
    db: AsyncSession,
    cache: CacheService,
) -> dict:
    """
    Write-through: Update DB VÀ cache đồng thời.
    Đảm bảo cache luôn fresh, nhưng write chậm hơn.
    """
    # 1. Update DB
    result = await db.execute(
        update(User).where(User.id == user_id).values(**update_data).returning(User)
    )
    user = result.scalar_one()
    await db.commit()

    # 2. Update cache ngay lập tức (không invalidate, update luôn)
    cache_key = f"user:{user_id}"
    user_data = {"id": user.id, "username": user.username, "email": user.email}
    await cache.set(cache_key, json.dumps(user_data), ttl=300)

    return user_data
```

#### Pattern 3: Cache Invalidation

```python
async def invalidate_user_cache(user_id: int, cache: CacheService) -> None:
    """
    Xóa cache sau khi update/delete.
    Request tiếp theo sẽ cache miss và lấy fresh data từ DB.
    """
    await cache.delete(f"user:{user_id}")

    # Nếu có list cache liên quan, xóa luôn
    await cache.delete_pattern("users:list:*")

    # Hoặc dùng tags-based invalidation nếu dùng thư viện như aiocache
```

#### Pattern 4 (Optional): Distributed Lock (tránh Thundering Herd)

Thundering Herd: Khi cache expire, hàng trăm requests cùng lúc vào DB để lấy data.

```python
import asyncio
import uuid

async def get_user_with_lock(
    user_id: int,
    db: AsyncSession,
    cache: CacheService,
) -> dict | None:
    """
    Dùng distributed lock để chỉ một worker query DB khi cache miss.
    Các workers khác chờ và đọc từ cache sau khi lock release.
    """
    cache_key = f"user:{user_id}"
    lock_key = f"lock:user:{user_id}"
    lock_value = str(uuid.uuid4())  # Unique value để chỉ owner mới được release

    # Kiểm tra cache trước
    cached = await cache._client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Thử lấy lock (NX = only if Not eXists, EX = expire)
    acquired = await cache._client.set(lock_key, lock_value, nx=True, ex=5)

    if acquired:
        # Được lock → query DB
        try:
            # Double-check: request khác có thể đã fill cache trong khi ta chờ lock
            cached = await cache._client.get(cache_key)
            if cached:
                return json.loads(cached)

            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                user_data = {"id": user.id, "username": user.username, "email": user.email}
                await cache._client.setex(cache_key, 300, json.dumps(user_data))
                return user_data
            return None

        finally:
            # Chỉ release lock nếu ta là owner
            current_value = await cache._client.get(lock_key)
            if current_value == lock_value:
                await cache._client.delete(lock_key)
    else:
        # Không lấy được lock → chờ và retry
        for _ in range(10):  # Retry tối đa 10 lần
            await asyncio.sleep(0.1)  # Chờ 100ms
            cached = await cache._client.get(cache_key)
            if cached:
                return json.loads(cached)

        # Timeout → fallback về DB
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return {"id": user.id, "username": user.username} if user else None
```

#### Health Check với pool stats

```python
# src/myapp/routers/health.py
from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from myapp.dependencies import get_db
from myapp.cache import cache_service

router = APIRouter(tags=["Health"])


@router.get("/health")
async def liveness():
    """Liveness probe — app đang chạy không."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe — app có sẵn sàng nhận traffic không.
    Kiểm tra kết nối DB và Redis.
    Kubernetes dùng endpoint này để quyết định route traffic vào pod.
    """
    checks = {}

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Check Redis
    redis_ok = await cache_service.ping()
    checks["redis"] = "ok" if redis_ok else "error"

    # Lấy Redis pool stats
    if redis_ok:
        try:
            stats = await cache_service.get_pool_stats()
            checks["redis_stats"] = stats
        except Exception:
            pass

    all_ok = all(v == "ok" for k, v in checks.items() if k != "redis_stats")

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
```

---

## ⚠️ Common Mistakes

| Lỗi | Vấn đề | Cách sửa |
|---|---|---|
| Lazy load trong async context | `MissingGreenlet` error | Dùng `selectinload` hoặc `joinedload` khi cần relationship |
| Không dùng `expire_on_commit=False` | Objects expire sau commit, access tiếp → lazy load error | Set `expire_on_commit=False` trong `async_sessionmaker` |
| Cache không có TTL | Data stale mãi mãi | Luôn set TTL khi cache |
| Cache list queries | Invalidation khó | Chỉ cache single-object lookups, không cache list |
| `joinedload` cho collections | LIMIT bị ảnh hưởng bởi JOIN duplicates | Dùng `selectinload` cho one-to-many |
| Không close session | Connection pool exhausted | Dùng `async with AsyncSessionLocal() as session` hoặc `Depends(get_db)` |
| Redis `keys("*")` trong production | Blocking operation, scan toàn bộ keyspace | Dùng `scan_iter()` hoặc cấu trúc key tốt để tránh pattern matching |

---

## ✅ Best Practices

1. **Repository pattern** — tách DB queries khỏi business logic. Service không biết về SQLAlchemy
2. **Generic `PaginatedResponse[T]`** — một model dùng cho tất cả resources
3. **Không cache list queries** — invalidation quá phức tạp, chỉ cache single-item lookups
4. **Cache key convention** — `{resource}:{id}` (ví dụ: `user:42`, `post:10`)
5. **Luôn set TTL** — không cache vĩnh viễn trừ static data
6. **`pool_pre_ping=True`** — tự động reconnect khi DB connection bị drop
7. **Đo trước khi optimize** — dùng `EXPLAIN ANALYZE` hoặc SQLAlchemy echo để xác nhận N+1 trước khi fix

---

## ⚖️ Trade-offs

| Quyết định | Ưu điểm | Nhược điểm |
|---|---|---|
| `selectinload` | 2 queries, không duplicate rows | 2 round trips thay vì 1 |
| `joinedload` | 1 query, tốt cho many-to-one | JOIN có thể tốn memory, LIMIT issue với collections |
| Cache-aside | App kiểm soát cache logic | Code phức tạp hơn, có thể stale |
| Write-through | Cache luôn fresh | Write chậm hơn (2 writes) |
| Cache invalidation | Simple logic | Race condition: read cũ xảy ra giữa DB write và cache delete |
| Offset pagination | Đơn giản, có thể jump trang | Inconsistent khi data thay đổi, slow với large offset |
| Cursor pagination | Consistent, fast | Không thể jump trang, implementation phức tạp hơn |

---

## 🚀 Performance Notes

- **SQLAlchemy connection pool:** `pool_size=10` phù hợp cho hầu hết workloads. Đặt = số CPU cores * 2 + 1 cho CPU-bound, hoặc cao hơn cho IO-bound
- **Redis pipeline:** Khi cần nhiều Redis operations, dùng `pipeline()` để batch gửi một lần
- **Cache hit ratio:** Target > 80%. Dưới đó, xem lại TTL và cache key strategy
- **`EXPLAIN ANALYZE`** trong PostgreSQL: Chạy trực tiếp trên DB để xem query plan và actual execution time
- **`echo=True`** trong SQLAlchemy: Log tất cả SQL statements — dùng trong development để phát hiện N+1
- **Lazy load với `lazy="raise"`:** Cấu hình relationship với `lazy="raise"` để raise error ngay khi lazy load được attempt (detect sớm trong tests)

```python
# Cấu hình lazy="raise" để detect N+1 sớm trong tests
posts: Mapped[list["Post"]] = relationship(
    "Post",
    back_populates="author",
    lazy="raise",  # Raise nếu lazy load được attempt
)
```

---

## 📡 gRPC trong Python (Optional Quick Reference)

> **Phần mở rộng** — dành cho team đã dùng gRPC ở NodeJS. Thời gian ước tính: 20 phút.

```bash
# Setup
uv add grpcio grpcio-tools
```

```protobuf
# user.proto — giống NodeJS gRPC, syntax y chang
syntax = "proto3";
package user;

service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc CreateUser (CreateUserRequest) returns (User);
  rpc ListUsers (ListUsersRequest) returns (stream User);  // server streaming
}

message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
}
message GetUserRequest { int32 id = 1; }
message CreateUserRequest { string name = 1; string email = 2; }
message ListUsersRequest {}
```

```bash
# Generate Python code từ proto
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. user.proto
# → user_pb2.py (messages) + user_pb2_grpc.py (stubs)
```

```python
# AsyncIO server/client — phù hợp FastAPI stack async
import asyncio
import grpc
import user_pb2, user_pb2_grpc

class UserServicer(user_pb2_grpc.UserServiceServicer):
    async def GetUser(self, request, context):
        return user_pb2.User(id=request.id, name="Alice", email="alice@example.com")

    async def ListUsers(self, request, context):
        for i in range(3):
            yield user_pb2.User(id=i, name=f"User {i}", email=f"user{i}@example.com")

async def serve():
    server = grpc.aio.server()
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()

async def client():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = user_pb2_grpc.UserServiceStub(channel)
        user = await stub.GetUser(user_pb2.GetUserRequest(id=1))
        print(f"Got: {user.name}")

# asyncio.run(serve())
# asyncio.run(client())

# gRPC vs REST trong Python microservices:
# gRPC: bidirectional streaming, strict typing, binary protocol, cần codegen
# REST: browser-friendly, simpler debugging, easier third-party integration
# → Dùng gRPC cho internal service-to-service, REST cho public APIs
```

## 📝 Tóm tắt

Ngày 15 đã kết nối FastAPI với lớp data:

- **Dependency chain** `get_db → Repository → Service` tạo separation of concerns rõ ràng — tương tự NestJS nhưng explicit thay vì decorator magic
- **`PaginatedResponse[T]`** Generic model tái sử dụng cho mọi resource, tránh viết lại pagination logic
- **N+1 là kẻ thù số 1** của ORM performance — `selectinload` (collections) và `joinedload` (single objects) là hai vũ khí chính
- **Cache-aside** là pattern phổ biến nhất, kết hợp với invalidation khi write
- **Thundering herd** với distributed lock khi cache expire là optional cho high-traffic endpoints
- **gRPC** là quick reference optional: proto → codegen → server/client cho internal service-to-service

**Ngày mai (Day 16):** Deployment — Dockerfile multi-stage, Gunicorn/Uvicorn workers, CI/CD, Task Queues.
