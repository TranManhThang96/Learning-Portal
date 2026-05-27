# Ngày 15: Tài Liệu Tham Khảo

## SQLAlchemy Relationship Loading

### Tài liệu chính thức
- **SQLAlchemy Async IO:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Relationship Loading Techniques:** https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- **selectinload:** https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#select-in-loading
- **joinedload:** https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#joined-eager-loading
- **lazy="raise":** https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#raise-loading

### Quick Reference: Các loading strategies

```python
from sqlalchemy.orm import (
    selectinload,    # 2 queries, IN clause — tốt cho collections
    joinedload,      # 1 query với JOIN — tốt cho many-to-one
    subqueryload,    # 1 query với subquery — cũ hơn, ít dùng
    noload,          # Không load relationship
    raiseload,       # Raise error nếu access (detect N+1 trong tests)
    immediateload,   # Load ngay, tương tự selectinload nhưng dùng scalar select
)

# Nested loading
from sqlalchemy.orm import selectinload

# Load posts → load mỗi post's author → load mỗi post's comments
result = await db.execute(
    select(User).options(
        selectinload(User.posts).options(
            joinedload(Post.author),        # many-to-one: dùng joinedload
            selectinload(Post.comments),    # one-to-many: dùng selectinload
        )
    )
)

# Nếu dùng joinedload với collection, SQLAlchemy 2.0 yêu cầu unique()
result = await db.execute(select(User).options(joinedload(User.posts)))
users = result.scalars().unique().all()
```

### contains_eager — khi bạn đã có JOIN

```python
# Dùng khi tự viết JOIN query và muốn SQLAlchemy populate relationship
from sqlalchemy.orm import contains_eager

result = await db.execute(
    select(Post)
    .join(Post.author)  # Explicit JOIN
    .options(contains_eager(Post.author))  # Dùng kết quả JOIN để fill relationship
    .where(User.is_active == True)  # Filter trên joined table
)
```

### lazy="raise" trong testing

```python
# models.py — cấu hình để catch N+1 early
class Post(Base):
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        lazy="raise",  # Raise nếu lazy load được attempt
    )

# Trong test, nếu code có N+1:
# sqlalchemy.exc.InvalidRequestError: 'Post.author' is not available due to lazy='raise'
```

### EXPLAIN ANALYZE trong PostgreSQL

```sql
-- Xem query plan thực tế
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT posts.id, posts.title, users.username, COUNT(comments.id)
FROM posts
JOIN users ON posts.user_id = users.id
LEFT JOIN comments ON comments.post_id = posts.id
GROUP BY posts.id, posts.title, users.username
LIMIT 20;

-- Output quan trọng:
-- Seq Scan vs Index Scan (Index Scan = có index, nhanh hơn)
-- actual time=X.X..X.X rows=X (thời gian thực tế)
-- Buffers: shared hit=X read=X (cache hits vs disk reads)
```

---

## Redis Caching Patterns

> Trong Day 15, cache-aside cho single-object lookup là primary. Distributed lock, write-through, cache stats, và pattern delete là optional/advanced.

### Tài liệu chính thức
- **Redis documentation:** https://redis.io/docs/
- **Redis data types:** https://redis.io/docs/data-types/
- **redis-py async:** https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html
- **Redis patterns:** https://redis.io/docs/manual/patterns/

### redis.asyncio quick reference

```python
import redis.asyncio as redis

# Connection pool (khuyến nghị cho production)
pool = redis.ConnectionPool.from_url(
    "redis://localhost:6379",
    max_connections=20,
    decode_responses=True,
)
client = redis.Redis(connection_pool=pool)

# Các commands hay dùng
await client.set("key", "value")           # Set string
await client.setex("key", 300, "value")    # Set với TTL (giây)
await client.get("key")                    # Get (None nếu không tồn tại)
await client.delete("key")                 # Xóa 1 key
await client.delete("k1", "k2", "k3")     # Xóa nhiều keys
await client.exists("key")                 # 1 nếu tồn tại, 0 nếu không
await client.expire("key", 600)           # Set/update TTL
await client.ttl("key")                    # Xem TTL còn lại (-1 = no TTL, -2 = không tồn tại)
await client.incr("counter")              # Atomic increment
await client.keys("user:*")               # NGUY HIỂM trong production (blocking)
await client.scan_iter("user:*")          # An toàn hơn, iterative scan

# Pipeline — batch multiple commands
async with client.pipeline() as pipe:
    pipe.get("key1")
    pipe.get("key2")
    pipe.setex("key3", 300, "value")
    results = await pipe.execute()
    # results = [value1, value2, True]

# Pub/Sub
pubsub = client.pubsub()
await pubsub.subscribe("channel")
async for message in pubsub.listen():
    print(message)

# Distributed lock với SET NX EX
acquired = await client.set("lock:resource", "unique_id", nx=True, ex=30)
# nx=True: chỉ set nếu key KHÔNG tồn tại (N = Not eXists)
# ex=30: expire sau 30 giây (tự release nếu crash)
```

### Cache key naming convention

```
{resource}:{id}                    → user:42
{resource}:list:{filter_hash}      → user:list:abc123 (tránh — invalidation khó)
{resource}:{id}:{sub_resource}     → user:42:posts
lock:{resource}:{id}               → lock:user:42
rate_limit:{client_ip}             → rate_limit:192.168.1.1
session:{session_id}               → session:abc123
```

### Redis caching best practices

```python
# 1. Luôn set TTL
await client.setex(key, ttl=300, value=data)  # Không dùng set() không có TTL

# 2. Serialize với JSON (đơn giản) hoặc MessagePack (nhanh hơn, compact hơn)
import json
import msgpack  # uv add msgpack

# JSON
data = json.dumps({"id": 1, "name": "Alice"})
await client.setex(key, 300, data)
cached = json.loads(await client.get(key))

# MessagePack (nhanh hơn ~2x, nhỏ hơn ~30%)
data = msgpack.packb({"id": 1, "name": "Alice"})
await client.setex(key, 300, data)
cached = msgpack.unpackb(await client.get(key))

# 3. Cache negative results để tránh DB spam
user = await db.get_user(user_id)
if user is None:
    await cache.setex(f"user:{user_id}", 60, "null")  # Cache "không tồn tại" với TTL ngắn
    return None
```

### aiocache — higher-level caching library

```bash
uv add aiocache[redis]
```

```python
from aiocache import Cache, cached
from aiocache.serializers import JsonSerializer

# Decorator approach (giống NestJS @CacheKey)
cache = Cache(Cache.REDIS, endpoint="localhost", port=6379, namespace="myapp")

@cached(ttl=300, cache=Cache.REDIS, key_builder=lambda f, *args, **kw: f"user:{args[0]}")
async def get_user(user_id: int):
    return await db.get_user(user_id)
```

---

## Pagination Best Practices

### Tài liệu
- **Cursor Pagination (Slack Engineering):** https://slack.engineering/evolving-api-pagination-at-slack/
- **Cursor vs Offset (Prisma):** https://www.prisma.io/docs/orm/prisma-client/queries/pagination
- **REST API pagination patterns:** https://nordicapis.com/everything-you-need-to-know-about-api-pagination/

### Offset-based: khi nào phù hợp

```
- Admin dashboards (data không thay đổi liên tục)
- Reporting (export toàn bộ data)
- Khi user cần nhảy đến trang cụ thể (trang 1, 2, 3...)
- Data nhỏ (< 100K rows)
```

### Cursor-based: khi nào phù hợp

```
- Social feeds (Twitter, Facebook)
- Real-time data (mới insert liên tục)
- Infinite scroll
- Data lớn (> 1M rows, OFFSET chậm vì phải scan từ đầu)
```

### Vì sao OFFSET chậm với large datasets

```sql
-- OFFSET 100000 LIMIT 20 phải:
-- 1. Scan và đọc 100000 rows đầu tiên
-- 2. Bỏ qua chúng
-- 3. Trả về 20 rows tiếp theo
-- → O(n) với n là offset value

-- Cursor-based: luôn O(1) với index trên cursor column
SELECT * FROM posts WHERE id > 100000 ORDER BY id ASC LIMIT 20
```

### Keyset pagination với composite keys

```python
# Khi sort theo created_at (có thể bị tie — nhiều rows cùng timestamp)
# Cursor = (created_at, id) để đảm bảo unique

async def list_posts_keyset(
    db: AsyncSession,
    after_created_at: datetime | None = None,
    after_id: int | None = None,
    limit: int = 20,
) -> list[Post]:
    query = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)

    if after_created_at and after_id:
        # Rows có created_at nhỏ hơn, HOẶC cùng created_at nhưng id nhỏ hơn
        query = query.where(
            or_(
                Post.created_at < after_created_at,
                and_(
                    Post.created_at == after_created_at,
                    Post.id < after_id,
                )
            )
        )

    result = await db.execute(query)
    return list(result.scalars().all())
```

---

## SQLAlchemy Performance Tips

### Connection pool tuning

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # Số connections thường trực
    max_overflow=20,       # Connections thêm khi pool đầy (tổng max = pool_size + max_overflow)
    pool_timeout=30,       # Giây chờ lấy connection từ pool (raise TimeoutError nếu quá)
    pool_recycle=3600,     # Tái tạo connections sau 1 giờ (tránh "gone away" lỗi)
    pool_pre_ping=True,    # Test connection trước khi dùng (tránh dùng dead connection)
)
```

### Query optimization

```python
# Chỉ select columns cần thiết thay vì toàn bộ model
result = await db.execute(
    select(User.id, User.username, User.email)  # Không load hashed_password, created_at, v.v.
    .where(User.is_active == True)
    .limit(20)
)
rows = result.all()  # list of Row, không phải list of User

# Bulk insert thay vì loop
await db.execute(
    insert(User),
    [{"username": f"user{i}", "email": f"user{i}@example.com"} for i in range(100)]
)
await db.commit()

# Bulk update
await db.execute(
    update(User)
    .where(User.created_at < cutoff_date)
    .values(is_active=False)
)
```

### Index hints

```python
# Thêm index vào model
from sqlalchemy import Index

class User(Base):
    __tablename__ = "users"
    # ...

    # Composite index cho search + sort
    __table_args__ = (
        Index("idx_users_username_created", "username", "created_at"),
        Index("idx_users_email", "email", unique=True),
    )
```

---

## Công cụ hữu ích

### Redis GUI
- **RedisInsight** (official, miễn phí): https://redis.io/insight/
- **Another Redis Desktop Manager:** https://github.com/qishibo/AnotherRedisDesktopManager

### SQLAlchemy echo với filter

```python
# Xem tất cả SQL (verbose)
engine = create_async_engine(DATABASE_URL, echo=True)

# Chỉ xem slow queries (> threshold)
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
# → Chỉ log queries raise warning (ít noise hơn)
```

### pytest với async SQLAlchemy

```python
# conftest.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSession() as session:
        yield session

    await engine.dispose()

@pytest.mark.asyncio
async def test_user_repository(db: AsyncSession):
    repo = UserRepository(db)
    user = await repo.create(UserCreate(username="alice", email="alice@test.com"))
    assert user.id is not None
```
