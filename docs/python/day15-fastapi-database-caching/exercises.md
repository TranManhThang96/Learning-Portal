# Ngày 15: Bài Tập Thực Hành

**Primary app flow:** Bài 1 + Bài 2 là mục tiêu chính trong 2 giờ: pagination endpoint chạy được, rồi tái hiện/sửa N+1. Bài 3 Redis là optional nếu hai bài đầu đã pass.

## Bài 1 (Cơ bản): Paginated Users List Endpoint

### Mục tiêu

Implement endpoint `GET /users` với SQLite in-memory, SQLAlchemy async, và `PaginatedResponse[T]` Generic model.

### Yêu cầu

1. **Setup SQLite in-memory database** với SQLAlchemy async
2. **Model `User`** với fields: `id`, `username`, `email`, `created_at`
3. **`PaginatedResponse[T]`** Generic Pydantic model với `items`, `total`, `skip`, `limit`, `has_next`, `has_prev`
4. **`UserRepository`** với methods:
   - `count(search: str | None = None) -> int`
   - `list(skip: int, limit: int, search: str | None = None) -> list[User]`
5. **Route `GET /users`** với query params: `skip` (default 0), `limit` (default 5, max 20), `search` (optional)
6. **Seed 20 users** khi startup để test pagination

### Setup

```bash
uv add fastapi uvicorn sqlalchemy aiosqlite
```

### Khung code

```python
# exercise1/main.py
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ===================== Database =====================
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ===================== Model =====================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# ===================== Schemas =====================
class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    model_config = {"from_attributes": True}


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(cls, items: list[T], total: int, skip: int, limit: int):
        # TODO: Tạo PaginatedResponse với has_next và has_prev đúng
        pass


# ===================== Repository =====================
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count(self, search: str | None = None) -> int:
        # TODO: COUNT query với optional search filter
        pass

    async def list(
        self, skip: int = 0, limit: int = 20, search: str | None = None
    ) -> list[User]:
        # TODO: SELECT query với OFFSET, LIMIT, optional search
        pass


# ===================== Dependencies =====================
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ===================== Lifespan =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tạo tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed 20 users
    async with AsyncSessionLocal() as session:
        # TODO: Insert 20 users với username "user01" đến "user20"
        pass

    yield

    await engine.dispose()


# ===================== App =====================
app = FastAPI(lifespan=lifespan)


@app.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=20),
    search: str | None = Query(None),
):
    # TODO: Dùng UserRepository để lấy count và list
    # TODO: Trả về PaginatedResponse.create(...)
    pass
```

### Test thủ công

```bash
# Chạy server
uvicorn exercise1.main:app --reload

# Test pagination
curl "http://localhost:8000/users?skip=0&limit=5"
# Expect: 5 users, has_next=true, has_prev=false

curl "http://localhost:8000/users?skip=15&limit=5"
# Expect: 5 users, has_next=false, has_prev=true

curl "http://localhost:8000/users?search=user1"
# Expect: users 10-19 (tên chứa "user1")
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
# exercise1/solution.py
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    model_config = {"from_attributes": True}


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(cls, items: list, total: int, skip: int, limit: int):
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_next=(skip + limit) < total,
            has_prev=skip > 0,
        )


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count(self, search: str | None = None) -> int:
        query = select(func.count(User.id))
        if search:
            query = query.where(User.username.ilike(f"%{search}%"))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list(self, skip: int = 0, limit: int = 20, search: str | None = None) -> list[User]:
        query = select(User).offset(skip).limit(limit).order_by(User.id.asc())
        if search:
            query = query.where(User.username.ilike(f"%{search}%"))
        result = await self.db.execute(query)
        return list(result.scalars().all())


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for i in range(1, 21):
            session.add(User(
                username=f"user{i:02d}",
                email=f"user{i:02d}@example.com",
            ))
        await session.commit()

    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=20),
    search: str | None = Query(None),
):
    repo = UserRepository(db)
    total = await repo.count(search=search)
    users = await repo.list(skip=skip, limit=limit, search=search)
    items = [UserResponse.model_validate(u) for u in users]
    return PaginatedResponse.create(items=items, total=total, skip=skip, limit=limit)
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Tại sao `count()` và `list()` là 2 queries riêng thay vì 1 query? Có cách nào làm 1 query không?
2. `expire_on_commit=False` ảnh hưởng gì đến behavior của `UserResponse.model_validate(u)` sau `session.commit()`?
3. `has_next = (skip + limit) < total` — điều gì xảy ra nếu `total = 20`, `skip = 15`, `limit = 10`?

---

## Bài 2 (Trung bình): Phát Hiện và Sửa N+1 Problem

### Mục tiêu

Viết một endpoint có N+1 problem, quan sát số queries, sau đó sửa bằng `selectinload` và `joinedload`.

### Setup models

```python
# User → nhiều Posts → nhiều Comments (3 levels)
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author")


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
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

### Seed data

```python
# 5 users, mỗi user có 3 posts, mỗi post có 2 comments
# Tổng: 5 users, 15 posts, 30 comments
```

### Yêu cầu

**Phần A: Tái hiện N+1 problem**

Implement endpoint `GET /posts/bad` với SQLAlchemy echo=True:

```python
# BAD: Attempt lazy load trong async context → MissingGreenlet error
# Thay vào đó, demo N+1 bằng cách query DB trong loop

async def get_posts_n_plus_1(db: AsyncSession) -> list[dict]:
    """
    Query 1: Lấy 15 posts
    Query 2-16: Mỗi post query author riêng
    Query 17-46: Mỗi post query comments riêng (hoặc mỗi comment query post)

    Tổng: ~31-46 queries cho 15 posts
    """
    result = await db.execute(select(Post).limit(15))
    posts = result.scalars().all()

    post_list = []
    for post in posts:
        # Explicit N+1: mỗi post chạy thêm 2 queries
        author_result = await db.execute(select(User).where(User.id == post.user_id))
        author = author_result.scalar_one_or_none()

        comment_count_result = await db.execute(
            select(func.count(Comment.id)).where(Comment.post_id == post.id)
        )
        comment_count = comment_count_result.scalar_one()

        post_list.append({
            "id": post.id,
            "title": post.title,
            "author": author.username if author else None,
            "comment_count": comment_count,
        })

    return post_list
```

**Phần B: Fix với selectinload (2 queries)**

```python
# FIX 1: selectinload — load tất cả authors và comments trong 2 IN queries
async def get_posts_selectinload(db: AsyncSession) -> list[dict]:
    # TODO: Implement với selectinload(Post.author) và selectinload(Post.comments)
    pass
```

**Phần C: Fix với JOIN + aggregate (1 query)**

```python
# FIX 2: Explicit JOIN — 1 query với COUNT
async def get_posts_join_aggregate(db: AsyncSession) -> list[dict]:
    # TODO: Implement với JOIN users + LEFT JOIN comments + GROUP BY + COUNT
    pass
```

**Phần D: So sánh performance**

```python
# Đo thời gian của 3 approaches:
import time

@app.get("/benchmark")
async def benchmark(db: AsyncSession = Depends(get_db)):
    results = {}

    start = time.perf_counter()
    await get_posts_n_plus_1(db)
    results["n_plus_1_ms"] = round((time.perf_counter() - start) * 1000, 2)

    start = time.perf_counter()
    await get_posts_selectinload(db)
    results["selectinload_ms"] = round((time.perf_counter() - start) * 1000, 2)

    start = time.perf_counter()
    await get_posts_join_aggregate(db)
    results["join_aggregate_ms"] = round((time.perf_counter() - start) * 1000, 2)

    return results
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
# FIX với selectinload
from sqlalchemy.orm import selectinload

async def get_posts_selectinload(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.comments),
        )
        .limit(15)
    )
    posts = result.scalars().all()

    return [
        {
            "id": post.id,
            "title": post.title,
            "author": post.author.username if post.author else None,
            "comment_count": len(post.comments),
        }
        for post in posts
    ]


# FIX với JOIN + aggregate
async def get_posts_join_aggregate(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(
            Post.id,
            Post.title,
            User.username.label("author_username"),
            func.count(Comment.id).label("comment_count"),
        )
        .join(User, Post.user_id == User.id)
        .outerjoin(Comment, Comment.post_id == Post.id)
        .group_by(Post.id, Post.title, User.username)
        .limit(15)
    )

    return [
        {
            "id": row.id,
            "title": row.title,
            "author": row.author_username,
            "comment_count": row.comment_count,
        }
        for row in result.all()
    ]
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Kết quả benchmark: approach nào nhanh nhất với SQLite? Với PostgreSQL production, kết quả có thể khác không?
2. `selectinload(Post.comments)` rồi `len(post.comments)` vs `JOIN + COUNT` — khi nào dùng cái nào?
3. Nếu cần load `post.comments` và mỗi `comment.author` (3 levels), `selectinload` cần bao nhiêu queries?

---

## Bài 3 (Optional/Nâng cao): Cache-Aside Layer với Redis

### Mục tiêu

Implement cache-aside pattern tối thiểu: get → cache miss → DB → cache set, với invalidation khi update và TTL configuration. Cache stats, pattern delete, và race-condition handling là bonus.

### Yêu cầu

1. **`CacheService`** wrapping `redis.asyncio`:
   - `get(key) -> str | None`
   - `set(key, value, ttl=300)`
   - `delete(key)`
   - `delete_pattern(pattern)` — xóa nhiều keys theo pattern

2. **`UserService`** với cache-aside:
   - `get_by_id(user_id)` — cache-aside, key `user:{id}`, TTL 5 phút
   - `update(user_id, data)` — update DB rồi invalidate cache
   - Ghi log mỗi cache hit/miss

3. **Endpoints**:
   - `GET /users/{user_id}` — dùng cache
   - `PATCH /users/{user_id}` — update rồi invalidate cache
   - `GET /cache/stats` — thống kê hit/miss count

4. **Cache stats counter** (in-memory, chỉ để demo):

```python
class CacheStats:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

### Setup

```bash
# Cần Redis đang chạy
docker run -d -p 6379:6379 redis:7-alpine

uv add fastapi uvicorn sqlalchemy asyncpg redis aiosqlite
```

### Khung code

```python
# exercise3/main.py
import json
from contextlib import asynccontextmanager
from typing import Annotated, Any

import redis.asyncio as redis
import structlog
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import String, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = structlog.get_logger()

# ===================== Database setup =====================
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255))


# ===================== Schemas =====================
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    username: str | None = None


# ===================== Cache Stats =====================
class CacheStats:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 3) if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total": self.hits + self.misses,
            "hit_ratio": self.hit_ratio,
        }


cache_stats = CacheStats()


# ===================== Cache Service =====================
class CacheService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._client = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        # TODO: Implement
        pass

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        # TODO: Implement
        pass

    async def delete(self, key: str) -> None:
        # TODO: Implement
        pass

    async def delete_pattern(self, pattern: str) -> int:
        # TODO: Scan và delete tất cả keys khớp pattern
        pass

    async def ping(self) -> bool:
        # TODO: Implement
        pass


# ===================== User Service =====================
class UserService:
    CACHE_TTL = 300  # 5 phút
    CACHE_KEY_PREFIX = "user:"

    def __init__(self, db: AsyncSession, cache: CacheService, stats: CacheStats):
        self.db = db
        self.cache = cache
        self.stats = stats

    def _key(self, user_id: int) -> str:
        return f"{self.CACHE_KEY_PREFIX}{user_id}"

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Cache-aside:
        1. Check cache → hit: return
        2. Cache miss → query DB
        3. DB result → serialize → cache set
        4. Return
        """
        # TODO: Implement với logging và stats tracking
        pass

    async def update(self, user_id: int, update_data: UserUpdate) -> User | None:
        """
        1. Update DB
        2. Invalidate cache
        """
        # TODO: Implement
        pass


# ===================== Dependencies =====================
cache_service = CacheService()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    return UserService(db, cache_service, cache_stats)


# ===================== Lifespan =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for i in range(1, 6):
            session.add(User(username=f"user{i}", email=f"user{i}@example.com"))
        await session.commit()

    yield
    await engine.dispose()


# ===================== App =====================
app = FastAPI(lifespan=lifespan)


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    service: Annotated[UserService, Depends(get_user_service)],
):
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    service: Annotated[UserService, Depends(get_user_service)],
):
    user = await service.update(user_id, update_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/cache/stats")
async def get_cache_stats():
    return cache_stats.to_dict()
```

### Test flow

```bash
# 1. Lần đầu: cache miss → query DB
curl http://localhost:8000/users/1
# Log: cache_miss user:1

# 2. Lần 2: cache hit → không query DB
curl http://localhost:8000/users/1
# Log: cache_hit user:1

# 3. Update → invalidate cache
curl -X PATCH http://localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"email": "newemail@example.com"}'
# Log: cache_invalidated user:1

# 4. Lần 3: cache miss lại (vì đã invalidate)
curl http://localhost:8000/users/1
# Log: cache_miss user:1

# 5. Kiểm tra stats
curl http://localhost:8000/cache/stats
# Expect: {"hits": 1, "misses": 2, "total": 3, "hit_ratio": 0.333}
```

### Lời giải tham khảo

<details>
<summary>Bấm để xem lời giải</summary>

```python
class CacheService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._client = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        await self._client.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        keys = await self._client.keys(pattern)
        if keys:
            return await self._client.delete(*keys)
        return 0

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False


class UserService:
    CACHE_TTL = 300
    CACHE_KEY_PREFIX = "user:"

    def __init__(self, db: AsyncSession, cache: CacheService, stats: CacheStats):
        self.db = db
        self.cache = cache
        self.stats = stats

    def _key(self, user_id: int) -> str:
        return f"{self.CACHE_KEY_PREFIX}{user_id}"

    async def get_by_id(self, user_id: int) -> User | None:
        cache_key = self._key(user_id)

        cached = await self.cache.get(cache_key)
        if cached is not None:
            self.stats.record_hit()
            logger.info("cache_hit", key=cache_key)
            data = json.loads(cached)
            if data is None:
                return None
            # Reconstruct User object từ cached data
            user = User(id=data["id"], username=data["username"], email=data["email"])
            return user

        self.stats.record_miss()
        logger.info("cache_miss", key=cache_key)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            await self.cache.set(cache_key, json.dumps(None), ttl=60)
            return None

        user_data = {"id": user.id, "username": user.username, "email": user.email}
        await self.cache.set(cache_key, json.dumps(user_data), ttl=self.CACHE_TTL)

        return user

    async def update(self, user_id: int, update_data: UserUpdate) -> User | None:
        update_values = {k: v for k, v in update_data.model_dump().items() if v is not None}
        if not update_values:
            return await self.get_by_id(user_id)

        result = await self.db.execute(
            update(User).where(User.id == user_id).values(**update_values).returning(User)
        )
        user = result.scalar_one_or_none()

        if user is None:
            return None

        await self.db.commit()

        # Invalidate cache
        await self.cache.delete(self._key(user_id))
        logger.info("cache_invalidated", user_id=user_id)

        return user
```

</details>

### Câu hỏi kiểm tra hiểu biết

1. Trong `get_by_id`, tại sao cache `None` với TTL ngắn hơn (60s vs 300s)?
2. Race condition: nếu 2 requests đồng thời gọi `update(user_id=1)`, cache có thể ở trạng thái không nhất quán không?
3. `delete_pattern("user:*")` có vấn đề gì trong production với Redis cluster?
