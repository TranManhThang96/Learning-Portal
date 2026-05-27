# Ngày 12: Tài Liệu Tham Khảo - Database với Python

## Tài liệu chính thức

### SQLAlchemy 2.0
- **Official Docs**: https://docs.sqlalchemy.org/en/20/
- **ORM Tutorial**: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- **Async I/O**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Mapped Columns**: https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html
- **Relationships**: https://docs.sqlalchemy.org/en/20/orm/relationships.html
- **Loading Strategies** (selectinload, joinedload, lazyload): https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html
- **ORM Queries (2.0 style)**: https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html
- **Connection Pooling**: https://docs.sqlalchemy.org/en/20/core/pooling.html

### Alembic
- **Official Docs**: https://alembic.sqlalchemy.org/en/latest/
- **Getting Started**: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- **Async Support**: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
- **Auto-generating Migrations**: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- **Operations Reference**: https://alembic.sqlalchemy.org/en/latest/ops.html

### redis-py (redis.asyncio)
- **GitHub**: https://github.com/redis/redis-py
- **Docs**: https://redis-py.readthedocs.io/
- **Async support**: https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html
- **Commands Reference**: https://redis-py.readthedocs.io/en/stable/commands.html

### asyncpg (PostgreSQL async driver)
- **GitHub**: https://github.com/MagicStack/asyncpg
- **Docs**: https://magicstack.github.io/asyncpg/current/
- **Performance**: asyncpg nhanh hơn psycopg2 đáng kể cho async workloads

### aiosqlite (SQLite async driver - dùng cho development/testing)
- **GitHub**: https://github.com/omnilib/aiosqlite
- **Docs**: https://aiosqlite.omnilib.dev/

---

## Quick Reference

### SQLAlchemy Relationships Loading

```python
from sqlalchemy.orm import selectinload, joinedload, subqueryload, noload

# selectinload: 2 queries, no duplicate rows -> dùng cho collections (one-to-many)
stmt = select(User).options(selectinload(User.posts))

# joinedload: 1 JOIN query -> dùng cho single objects (many-to-one)
stmt = select(Post).options(joinedload(Post.author))

# joinedload với collection vẫn dùng được, nhưng SQLAlchemy 2.0 yêu cầu unique()
stmt = select(User).options(joinedload(User.posts))
result = await session.execute(stmt)
users = result.scalars().unique().all()

# Nested loading: posts với comments
stmt = select(User).options(
    selectinload(User.posts).selectinload(Post.comments)
)

# Multiple relationships
stmt = select(User).options(
    selectinload(User.posts),
    selectinload(User.comments),
)

# noload: không load, raise error nếu access
# raiseload: không load, raise error - tốt hơn noload để phát hiện N+1
from sqlalchemy.orm import raiseload
stmt = select(User).options(raiseload(User.posts))
```

### SQLAlchemy Common Queries

```python
# SELECT * FROM users
result = await session.execute(select(User))
users = result.scalars().all()

# SELECT * FROM users WHERE id = :id
user = await session.get(User, user_id)

# SELECT * FROM users WHERE email = :email
result = await session.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()

# SELECT * FROM users WHERE name LIKE '%query%'
stmt = select(User).where(User.name.ilike(f"%{query}%"))

# SELECT * FROM users WHERE id IN (1, 2, 3)
stmt = select(User).where(User.id.in_([1, 2, 3]))

# SELECT COUNT(*) FROM users
result = await session.execute(select(func.count()).select_from(User))
count = result.scalar_one()

# SELECT * FROM users LIMIT 10 OFFSET 20
stmt = select(User).limit(10).offset(20).order_by(User.created_at.desc())

# UPDATE users SET is_active = false WHERE id = :id
stmt = update(User).where(User.id == user_id).values(is_active=False)
await session.execute(stmt)

# JOIN users với posts, count posts
stmt = (
    select(User, func.count(Post.id).label("post_count"))
    .outerjoin(Post, Post.user_id == User.id)
    .group_by(User.id)
)
```

### Alembic Cheat Sheet

**Lab scope 2 giờ:** chạy được `init → revision --autogenerate → upgrade head → downgrade -1` là đủ. Data migration, branching, multiple databases, và CI migration checks để đọc thêm.

```bash
# Init
alembic init alembic

# Tạo migration tự động
alembic revision --autogenerate -m "description"

# Tạo migration trống
alembic revision -m "custom migration"

# Apply tất cả
alembic upgrade head

# Apply 1 step
alembic upgrade +1

# Rollback 1 step
alembic downgrade -1

# Rollback tất cả
alembic downgrade base

# Xem lịch sử
alembic history --verbose

# Xem current version
alembic current

# Show SQL thay vì chạy (dry run)
alembic upgrade head --sql
```

### Redis Commands thường dùng

```python
import redis.asyncio as redis

r = redis.from_url("redis://localhost:6379", decode_responses=True)

# String operations
await r.set("key", "value", ex=60)          # Set với TTL 60 giây
await r.get("key")                            # Get
await r.delete("key")                         # Delete
await r.exists("key")                         # Check exists
await r.expire("key", 300)                    # Set TTL
await r.ttl("key")                            # Get TTL
await r.incrby("counter", 1)                  # Atomic increment

# Hash operations (tương đương Redis object)
await r.hset("user:1", mapping={"name": "Alice", "age": "30"})
await r.hget("user:1", "name")
await r.hgetall("user:1")
await r.hdel("user:1", "age")

# Set operations
await r.sadd("tags:post:1", "python", "fastapi")
await r.smembers("tags:post:1")
await r.srem("tags:post:1", "python")

# Sorted Set (cho sliding window rate limiting)
await r.zadd("requests", {str(timestamp): timestamp})
await r.zremrangebyscore("requests", "-inf", cutoff)
await r.zcard("requests")

# Pipeline (batch operations)
async with r.pipeline(transaction=True) as pipe:
    pipe.set("k1", "v1")
    pipe.set("k2", "v2")
    pipe.expire("k1", 60)
    results = await pipe.execute()

# Pub/Sub
pubsub = r.pubsub()
await pubsub.subscribe("channel")
async for message in pubsub.listen():
    if message["type"] == "message":
        print(message["data"])
```

---

## Packages quan trọng

| Package | Mục đích | Install |
|---|---|---|
| `sqlalchemy[asyncio]` | Async ORM | `uv add sqlalchemy[asyncio]` |
| `asyncpg` | PostgreSQL async driver | `uv add asyncpg` |
| `aiosqlite` | SQLite async driver | `uv add aiosqlite` |
| `alembic` | Database migrations | `uv add alembic` |
| `redis[hiredis]` | Redis client + C parser | `uv add redis[hiredis]` |
| `fakeredis` | Redis giả lập cho tests | `uv add fakeredis` |
| `psycopg[binary]` | PostgreSQL driver (psycopg3) | `uv add psycopg[binary]` |

---

## So sánh loading strategies

| Strategy | Queries | Use case |
|---|---|---|
| `selectinload` | 2 queries | Collections (one-to-many, many-to-many) |
| `joinedload` | 1 JOIN query | Single objects (many-to-one, one-to-one); với collection phải gọi `Result.unique()` |
| `subqueryload` | 2 queries (subquery) | Ít dùng trong 2.0 |
| `lazyload` | N+1 | Không dùng trong async |
| `noload` | 0 (không load) | Khi không cần relationship |
| `raiseload` | 0 (raise nếu access) | Phát hiện N+1 trong development |

---

## Bài đọc thêm

- **"SQLAlchemy ORM Tutorial"**: https://docs.sqlalchemy.org/en/20/orm/tutorial.html
- **"Async SQLAlchemy with FastAPI"**: https://fastapi.tiangolo.com/tutorial/sql-databases/
- **"Alembic Tutorial"**: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- **"Redis Best Practices"**: https://redis.io/docs/manual/patterns/
- **"Caching Strategies"**: https://codeahoy.com/2017/08/11/caching-strategies-and-how-to-choose-the-right-one/
- **"N+1 Problem"**: https://www.sqlalchemy.org/features.html#eager-loading

---

## Debugging tips

```python
# Log tất cả SQL queries
engine = create_async_engine(DATABASE_URL, echo=True)

# Log chỉ slow queries (dùng event listener)
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop(-1)
    if total > 0.5:  # Log queries chậm hơn 500ms
        print(f"SLOW QUERY ({total:.2f}s): {statement[:200]}")
```
