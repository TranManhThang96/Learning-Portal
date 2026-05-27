# Ngày 12: Database với Python

## 🎯 Mục tiêu học tập

Sau bài học này, bạn sẽ:
- Hiểu cách dùng SQLAlchemy 2.0 async với kiến thức từ Prisma/TypeORM
- Implement Repository pattern tương tự TypeScript
- Setup và chạy Alembic migrations (tương đương prisma migrate)
- Dùng Redis async với `redis.asyncio`
- Tránh các lỗi phổ biến (N+1, connection pool exhaustion)

**Phạm vi 2 giờ:** core path là SQLAlchemy async setup, typed models, session lifecycle, repository CRUD, và 1 migration Alembic tối thiểu. Redis cache/distributed lock/rate limit là optional lab; không cần hoàn thành cùng ngày nếu primary DB flow chưa chạy end-to-end.

---

## 🔄 So sánh với TypeScript ecosystem

### ORM/Query Builder

| TypeScript | Python |
|---|---|
| **Prisma** (schema-first, code-gen) | **SQLAlchemy 2.0** (Python-first, typed) |
| **TypeORM** (decorator-based) | **SQLAlchemy ORM** (mapped_column) |
| **Knex** (query builder) | **SQLAlchemy Core** (select/insert/update) |
| **Sequelize** | **SQLAlchemy** (tương tự) |

### Prisma/TypeORM vs SQLAlchemy 2.0

| Tính năng | Prisma | SQLAlchemy 2.0 |
|---|---|---|
| **Schema definition** | `schema.prisma` file | Python class với `Mapped[type]` |
| **Type safety** | Generated types | `Mapped[int]`, `Mapped[str \| None]` |
| **Relations** | `include: { posts: true }` | `selectinload(User.posts)` |
| **Create** | `prisma.user.create({data: {...}})` | `session.add(User(...)); await session.flush()` |
| **Find unique** | `prisma.user.findUnique({where: {id}})` | `session.get(User, id)` |
| **Find many** | `prisma.user.findMany({where: {...}})` | `session.execute(select(User).where(...))` |
| **Update** | `prisma.user.update({where, data})` | `user.field = value; await session.flush()` |
| **Delete** | `prisma.user.delete({where: {id}})` | `await session.delete(user)` |
| **Transactions** | `prisma.$transaction([...])` | `async with session.begin():` |
| **Raw query** | `prisma.$queryRaw\`...\`` | `session.execute(text("SELECT ..."))` |

### Migration tools

| TypeScript | Python |
|---|---|
| `prisma migrate dev` | `alembic revision --autogenerate -m "desc"` |
| `prisma migrate deploy` | `alembic upgrade head` |
| `prisma migrate reset` | `alembic downgrade base` |
| `prisma db seed` | Custom seed script |

### Redis

| TypeScript (ioredis) | Python (redis.asyncio) |
|---|---|
| `const redis = new Redis(url)` | `redis = redis.from_url(url)` |
| `await redis.get(key)` | `await redis.get(key)` |
| `await redis.set(key, val, 'EX', 60)` | `await redis.set(key, val, ex=60)` |
| `await redis.del(key)` | `await redis.delete(key)` |
| `await redis.keys('prefix:*')` | `await redis.keys('prefix:*')` |
| `pipeline()` | `redis.pipeline()` |

---

## 📖 Lý thuyết

### Section 1: SQLAlchemy 2.0 Async Setup (Must Learn)

**Cài đặt:**

```bash
uv add sqlalchemy asyncpg alembic
# Hoặc SQLite cho development:
uv add sqlalchemy aiosqlite
```

**Database models với type annotations:**

```python
# src/models.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, Text, func
from datetime import datetime


# Engine với connection pooling
# Tương đương PgPool trong pg / connection pool trong TypeORM
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/mydb"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,          # Số connections tối thiểu trong pool
    max_overflow=20,       # Số connections thêm khi pool đầy
    pool_timeout=30,       # Timeout khi chờ connection từ pool (giây)
    pool_recycle=1800,     # Tái tạo connections sau 30 phút (tránh "gone away")
    pool_pre_ping=True,    # Kiểm tra connection trước khi dùng
    echo=False,            # True để log SQL queries (dev only)
)

# Session factory
# Tương đương DataSource.createEntityManager() trong TypeORM
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # QUAN TRỌNG: False = objects vẫn accessible sau commit
                             # True (default) = lazy load trong async sẽ lỗi
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship: Mapped[list["Post"]] = ORM relation
    # Tương đương @OneToMany trong TypeORM hoặc posts[] trong Prisma schema
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="author",
        lazy="noload",  # Không load tự động - phải dùng selectinload explicitly
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Index cho foreign key - LUÔN index FK
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Many-to-one relationship
    author: Mapped["User"] = relationship("User", back_populates="posts")

    def __repr__(self) -> str:
        return f"<Post id={self.id} title={self.title!r}>"
```

**Async context manager cho session:**

```python
# src/database.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager cho database session.
    Tương đương:
    // TypeORM
    const queryRunner = dataSource.createQueryRunner();
    await queryRunner.connect();
    try {
        await queryRunner.startTransaction();
        yield queryRunner.manager;
        await queryRunner.commitTransaction();
    } catch {
        await queryRunner.rollbackTransaction();
    } finally {
        await queryRunner.release();
    }
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Dùng trong code
async def create_user_example():
    async with get_session() as session:
        user = User(name="Alice", email="alice@example.com")
        session.add(user)
        # commit tự động khi exit context manager
    print(f"Created user: {user.id}")  # Hoạt động vì expire_on_commit=False
```

---

### Section 2: Repository Pattern (Must Learn)

Repository pattern trong SQLAlchemy - tương đương Prisma service hoặc TypeORM repository.

```python
# src/repositories/user_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from src.models import User, Post
from typing import Optional


class UserRepository:
    """
    Encapsulate tất cả database operations cho User.
    Tương đương:
    // TypeORM
    @Injectable()
    class UsersRepository {
        constructor(
            @InjectRepository(User)
            private usersRepo: Repository<User>
        ) {}
    }
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        """
        Tương đương:
        - Prisma: prisma.user.findUnique({ where: { id } })
        - TypeORM: usersRepo.findOne({ where: { id } })
        """
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """
        Tương đương:
        - Prisma: prisma.user.findUnique({ where: { email } })
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """
        Tương đương:
        - Prisma: prisma.user.findMany({ skip, take: limit })
        - TypeORM: usersRepo.find({ skip, take: limit })
        """
        stmt = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_posts(self, user_id: int) -> User | None:
        """
        Eager load posts để tránh N+1 query.
        Tương đương:
        - Prisma: prisma.user.findUnique({ where: { id }, include: { posts: true } })
        - TypeORM: usersRepo.findOne({ where: { id }, relations: { posts: true } })

        selectinload: thực hiện 2 queries:
        1. SELECT * FROM users WHERE id = :id
        2. SELECT * FROM posts WHERE user_id IN (:user_ids)
        """
        stmt = (
            select(User)
            .options(selectinload(User.posts))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users_with_posts(self) -> list[User]:
        """Query phức tạp với filter và eager loading."""
        stmt = (
            select(User)
            .options(selectinload(User.posts))
            .where(User.is_active == True)
            .order_by(User.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, name: str, email: str) -> User:
        """
        Tương đương:
        - Prisma: prisma.user.create({ data: { name, email } })
        - TypeORM: usersRepo.save(usersRepo.create({ name, email }))
        """
        user = User(name=name, email=email)
        self.session.add(user)
        await self.session.flush()        # Write to DB trong transaction, chưa commit
        await self.session.refresh(user)  # Reload từ DB để lấy server-side defaults
        return user

    async def update(self, user_id: int, **kwargs) -> User | None:
        """
        Tương đương:
        - Prisma: prisma.user.update({ where: { id }, data: kwargs })
        - TypeORM: usersRepo.update(id, kwargs)
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None

        for field, value in kwargs.items():
            if hasattr(user, field):
                setattr(user, field, value)

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_bulk(self, user_ids: list[int], **kwargs) -> int:
        """
        Bulk update - hiệu quả hơn update từng record.
        Tương đương:
        - Prisma: prisma.user.updateMany({ where: { id: { in: ids } }, data: kwargs })
        - TypeORM: usersRepo.update({ id: In(ids) }, kwargs)
        """
        stmt = (
            update(User)
            .where(User.id.in_(user_ids))
            .values(**kwargs)
            .execution_options(synchronize_session="fetch")
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def delete(self, user_id: int) -> bool:
        """
        Tương đương:
        - Prisma: prisma.user.delete({ where: { id } })
        - TypeORM: usersRepo.delete(id)
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        await self.session.delete(user)
        await self.session.flush()
        return True

    async def count(self) -> int:
        """
        Tương đương:
        - Prisma: prisma.user.count()
        - TypeORM: usersRepo.count()
        """
        stmt = select(func.count()).select_from(User)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(func.count()).select_from(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def search(self, query: str, skip: int = 0, limit: int = 20) -> list[User]:
        """Full-text search đơn giản với LIKE."""
        stmt = (
            select(User)
            .where(
                (User.name.ilike(f"%{query}%")) |
                (User.email.ilike(f"%{query}%"))
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

**PostRepository:**

```python
# src/repositories/post_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from src.models import Post, User


class PostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(
        self,
        user_id: int,
        published_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Post]:
        stmt = select(Post).where(Post.user_id == user_id)
        if published_only:
            stmt = stmt.where(Post.is_published == True)
        stmt = stmt.offset(skip).limit(limit).order_by(Post.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_author(self, post_id: int) -> Post | None:
        """Load post cùng với author data."""
        stmt = (
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.id == post_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_id: int, title: str, content: str) -> Post:
        post = Post(user_id=user_id, title=title, content=content)
        self.session.add(post)
        await self.session.flush()
        await self.session.refresh(post)
        return post

    async def count_by_user(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Post).where(Post.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
```

**Service layer sử dụng repositories:**

```python
# src/services/user_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.user_repository import UserRepository
from src.repositories.post_repository import PostRepository
from src.models import User, Post


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.post_repo = PostRepository(session)

    async def register(self, name: str, email: str) -> User:
        if await self.user_repo.exists_by_email(email):
            raise UserAlreadyExistsError(f"Email {email} is already registered")
        return await self.user_repo.create(name=name, email=email)

    async def get_user_profile(self, user_id: int) -> dict:
        """Lấy user profile với post count."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        post_count = await self.post_repo.count_by_user(user_id)
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "post_count": post_count,
            "member_since": user.created_at.isoformat(),
        }

    async def transfer_posts(
        self,
        from_user_id: int,
        to_user_id: int,
    ) -> int:
        """
        Transfer tất cả posts từ user này sang user khác.
        Dùng transaction để đảm bảo atomicity.
        """
        from_user = await self.user_repo.get_by_id(from_user_id)
        to_user = await self.user_repo.get_by_id(to_user_id)

        if not from_user:
            raise UserNotFoundError(f"Source user {from_user_id} not found")
        if not to_user:
            raise UserNotFoundError(f"Target user {to_user_id} not found")

        # Bulk update - một query thay vì N queries
        count = await self.post_repo.update_bulk_user(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
        )
        return count
```

---

### Section 3: Alembic Migrations (Must Learn)

> **Lab scope:** trong 2 giờ chỉ cần init Alembic, cấu hình `target_metadata`, tạo 1 revision, chạy `alembic upgrade head`, rồi rollback 1 bước. Autogenerate edge cases, data migrations, branching, và multi-env config để đọc thêm.

**Setup Alembic:**

```bash
uv add alembic

# Khởi tạo trong project root
alembic init alembic
```

Cấu trúc sau khi init:

```
project/
├── alembic/
│   ├── env.py           # Configuration file
│   ├── script.py.mako   # Template cho migration files
│   └── versions/        # Migration files
│       └── (empty)
├── alembic.ini          # Alembic config
└── src/
    └── models.py
```

**Cấu hình `alembic.ini`:**

```ini
[alembic]
# Đường dẫn đến thư mục versions
script_location = alembic

# Database URL - dùng biến môi trường trong production
sqlalchemy.url = postgresql+asyncpg://user:password@localhost/mydb
```

**Cấu hình `alembic/env.py` cho async:**

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import tất cả models để autogenerate detect được
from src.models import Base  # Base phải import tất cả models

config = context.config
fileConfig(config.config_file_name)

# target_metadata: Alembic so sánh DB hiện tại với schema này
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Chạy migrations mà không cần DB connection thật."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Chạy migrations với async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Các lệnh Alembic thường dùng:**

```bash
# Tạo migration tự động dựa trên model changes
# Tương đương: prisma migrate dev --name "add_users_table"
alembic revision --autogenerate -m "add users and posts tables"

# Apply tất cả pending migrations
# Tương đương: prisma migrate deploy
alembic upgrade head

# Rollback 1 migration
# Tương đương: prisma migrate reset (nhưng chỉ 1 step)
alembic downgrade -1

# Rollback về trạng thái ban đầu (xóa tất cả tables)
alembic downgrade base

# Xem lịch sử migrations
alembic history --verbose

# Xem migration hiện tại
alembic current

# Upgrade lên một revision cụ thể
alembic upgrade <revision_id>

# Tạo migration trống (viết tay)
alembic revision -m "custom migration"
```

**Migration file mẫu:**

```python
# alembic/versions/001_add_users_posts.py
"""add users and posts tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-01-15 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_posts_user_id"), "posts", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_posts_user_id"), table_name="posts")
    op.drop_table("posts")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
```

---

### Section 4: Redis với redis.asyncio (Optional Lab)

> **Optional lab:** phần Redis dùng để hiểu cache-aside và TTL. Distributed lock, rate limit, Pub/Sub, và tag-based invalidation là deep dive sau khi SQLAlchemy + Alembic đã ổn.

**Cài đặt:**

```bash
uv add redis[hiredis]  # hiredis: C extension, nhanh hơn pure Python parser
```

**RedisCache class:**

```python
# src/cache.py
import json
import redis.asyncio as redis
from typing import Any, Callable
from functools import wraps


class RedisCache:
    """
    Wrapper cho redis.asyncio với type safety và helper methods.
    Tương đương ioredis client trong Node.js.
    """

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        # from_url tự động xử lý connection pooling
        self.redis = redis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,  # Tự động decode bytes -> str
            max_connections=20,
        )

    async def get(self, key: str) -> Any | None:
        """Get value từ cache. Trả về None nếu key không tồn tại."""
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,  # TTL tính bằng giây
    ) -> None:
        """Set value vào cache với optional TTL."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            await self.redis.set(key, serialized, ex=ttl)
        else:
            await self.redis.set(key, serialized)

    async def delete(self, key: str) -> bool:
        """Xóa key. Trả về True nếu key tồn tại và đã xóa."""
        return bool(await self.redis.delete(key))

    async def delete_pattern(self, pattern: str) -> int:
        """
        Xóa tất cả keys matching pattern.
        VD: delete_pattern("user:*") xóa tất cả user keys.
        CẢNH BÁO: KEYS command block Redis, dùng SCAN trên production.
        """
        keys = await self.redis.keys(pattern)
        if not keys:
            return 0
        return await self.redis.delete(*keys)

    async def exists(self, key: str) -> bool:
        return bool(await self.redis.exists(key))

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL cho key đã tồn tại."""
        return bool(await self.redis.expire(key, ttl))

    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomic increment - dùng cho counters, rate limiting."""
        return await self.redis.incrby(key, amount)

    async def close(self) -> None:
        await self.redis.aclose()


# Cache decorator - tương đương cache() trong NestJS với @nestjs/cache-manager
def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator để cache kết quả của async function.

    Dùng:
    @cached(ttl=60, key_prefix="user")
    async def get_user(user_id: int) -> dict:
        ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Tạo cache key từ function name và arguments
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"

            # Thử lấy từ cache
            cached_value = await self.cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Cache miss: gọi function thật
            result = await func(self, *args, **kwargs)

            # Lưu vào cache
            if result is not None:
                await self.cache.set(cache_key, result, ttl=ttl)

            return result
        return wrapper
    return decorator


# Distributed lock pattern
# Tương đương Redlock trong Node.js (redlock package)
class DistributedLock:
    """
    Redis-based distributed lock.
    Dùng khi cần đảm bảo chỉ một instance chạy một task.
    """

    def __init__(self, cache: RedisCache, lock_name: str, ttl: int = 30) -> None:
        self.cache = cache
        self.lock_key = f"lock:{lock_name}"
        self.ttl = ttl

    async def acquire(self) -> bool:
        """
        Acquire lock. Trả về True nếu thành công.
        NX: SET only if Not eXists (atomic operation).
        """
        result = await self.cache.redis.set(
            self.lock_key,
            "locked",
            nx=True,    # Only set if not exists
            ex=self.ttl,
        )
        return result is not None

    async def release(self) -> None:
        await self.cache.delete(self.lock_key)

    async def __aenter__(self) -> "DistributedLock":
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Could not acquire lock: {self.lock_key}")
        return self

    async def __aexit__(self, *args) -> None:
        await self.release()
```

**Cache-aside pattern với Repository:**

```python
# src/repositories/cached_user_repository.py
import json
from src.repositories.user_repository import UserRepository
from src.cache import RedisCache
from src.models import User
from sqlalchemy.ext.asyncio import AsyncSession


class CachedUserRepository:
    """
    Repository với cache layer - Cache-aside pattern.
    Tương đương CacheModule trong NestJS.

    Cache-aside: Application tự quản lý cache
    1. Check cache
    2. Cache miss -> query DB -> store in cache
    3. On update/delete -> invalidate cache
    """

    USER_TTL = 300       # 5 phút
    USER_LIST_TTL = 60   # 1 phút (list thay đổi thường xuyên hơn)

    def __init__(self, session: AsyncSession, cache: RedisCache) -> None:
        self.repo = UserRepository(session)
        self.cache = cache

    def _user_key(self, user_id: int) -> str:
        return f"user:{user_id}"

    def _email_key(self, email: str) -> str:
        return f"user:email:{email}"

    def _list_key(self, skip: int, limit: int) -> str:
        return f"users:list:{skip}:{limit}"

    async def get_by_id(self, user_id: int) -> User | None:
        key = self._user_key(user_id)

        # 1. Check cache
        cached = await self.cache.get(key)
        if cached:
            # Reconstruct User object từ cached dict
            return User(**cached)

        # 2. Cache miss -> query DB
        user = await self.repo.get_by_id(user_id)
        if user is None:
            return None

        # 3. Store in cache
        user_dict = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
        }
        await self.cache.set(key, user_dict, ttl=self.USER_TTL)
        return user

    async def create(self, name: str, email: str) -> User:
        user = await self.repo.create(name=name, email=email)
        # Invalidate list cache khi tạo user mới
        await self.cache.delete_pattern("users:list:*")
        return user

    async def update(self, user_id: int, **kwargs) -> User | None:
        user = await self.repo.update(user_id, **kwargs)
        if user:
            # Invalidate caches liên quan
            await self.cache.delete(self._user_key(user_id))
            await self.cache.delete_pattern("users:list:*")
        return user

    async def delete(self, user_id: int) -> bool:
        user = await self.repo.get_by_id(user_id)
        result = await self.repo.delete(user_id)
        if result and user:
            # Invalidate
            await self.cache.delete(self._user_key(user_id))
            await self.cache.delete(self._email_key(user.email))
            await self.cache.delete_pattern("users:list:*")
        return result
```

**Redis Pub/Sub cho real-time events:**

```python
# src/events.py
import redis.asyncio as redis
import json
import asyncio
from typing import Callable


class EventBus:
    """Simple Redis Pub/Sub event bus."""

    def __init__(self, url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(url, decode_responses=True)

    async def publish(self, channel: str, event: dict) -> None:
        await self.redis.publish(channel, json.dumps(event))

    async def subscribe(self, channel: str, handler: Callable) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await handler(data)
```

---

## ⚠️ Common Mistakes

### 1. N+1 Query Problem

```python
# SAI: N+1 queries
# 1 query lấy users + N queries lấy posts cho mỗi user
async def get_users_wrong(session: AsyncSession):
    users = (await session.execute(select(User))).scalars().all()
    for user in users:
        # LỖI: Truy cập user.posts trong async context gây ra lazy load
        # Nếu lazy="select" (default): raise MissingGreenlet error
        # Nếu lazy="noload": posts sẽ rỗng
        posts = user.posts  # Đây là N+1 nếu lazy loading
        print(f"{user.name}: {len(posts)} posts")


# ĐÚNG: Dùng selectinload
async def get_users_correct(session: AsyncSession):
    stmt = select(User).options(selectinload(User.posts))
    users = (await session.execute(stmt)).scalars().all()
    for user in users:
        posts = user.posts  # Đã được load trong 1 query
        print(f"{user.name}: {len(posts)} posts")
```

### 2. expire_on_commit=True với async

```python
# SAI: expire_on_commit=True (default)
AsyncSessionLocal = async_sessionmaker(engine)  # expire_on_commit=True by default

async def create_user_wrong(session: AsyncSession):
    user = User(name="Alice", email="alice@test.com")
    session.add(user)
    await session.commit()
    # LỖI: user.id sẽ trigger lazy reload
    # Trong async: "greenlet_spawn has not been called"
    return user.id  # MissingGreenlet error!


# ĐÚNG: expire_on_commit=False
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def create_user_correct(session: AsyncSession):
    user = User(name="Alice", email="alice@test.com")
    session.add(user)
    await session.flush()    # Write to DB
    await session.refresh(user)  # Load server defaults
    return user  # Attributes accessible sau refresh
```

### 3. Commit trong Repository

```python
# SAI: Repository tự commit
class UserRepository:
    async def create(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.session.add(user)
        await self.session.commit()  # SAI! Repository không nên commit
        return user

# VẤN ĐỀ: Không thể làm transaction spanning multiple repositories
async def create_user_and_post_wrong(session):
    user_repo = UserRepository(session)
    post_repo = PostRepository(session)

    user = await user_repo.create("Alice", "alice@test.com")
    # user_repo đã commit -> nếu tạo post fail, user đã được lưu
    post = await post_repo.create(user.id, "Hello")  # Nếu fail, data inconsistent!


# ĐÚNG: Service layer quản lý transaction
class UserRepository:
    async def create(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self.session.add(user)
        await self.session.flush()   # flush, không commit
        await self.session.refresh(user)
        return user

# Service commit sau khi tất cả operations thành công
async def create_user_and_post_correct(session: AsyncSession):
    user_repo = UserRepository(session)
    post_repo = PostRepository(session)

    user = await user_repo.create("Alice", "alice@test.com")
    post = await post_repo.create(user.id, "Hello")

    await session.commit()  # Commit một lần duy nhất
    return user, post
```

### 4. Connection Pool Exhaustion

```python
# SAI: Không close session
async def get_all_users_wrong():
    session = AsyncSessionLocal()  # Lấy connection từ pool
    result = await session.execute(select(User))
    return result.scalars().all()
    # session không được đóng -> connection bị giữ mãi -> pool exhausted

# ĐÚNG: Dùng context manager
async def get_all_users_correct():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        return result.scalars().all()
    # Context manager tự động close session và trả connection về pool
```

---

## ✅ Best Practices

**1. Luôn dùng `expire_on_commit=False` với async:**

```python
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

**2. Index foreign keys và columns thường query:**

```python
class Post(Base):
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,  # LUÔN index FK
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,  # Index nếu thường sort/filter theo thời gian
    )
```

**3. Dùng `selectinload` thay vì `joinedload` cho collections:**

```python
# selectinload: 2 queries riêng biệt, không duplicate rows
stmt = select(User).options(selectinload(User.posts))

# joinedload: 1 query với JOIN, có thể duplicate rows nếu many-to-many
stmt = select(User).options(joinedload(User.posts))

# Rule: selectinload cho collections (one-to-many), joinedload cho single objects (many-to-one)
stmt = select(Post).options(joinedload(Post.author))  # Tốt cho many-to-one
```

**Caveat SQLAlchemy 2.0:** nếu vẫn dùng `joinedload()` với collection (`one-to-many`/`many-to-many`), phải gọi `Result.unique()` trước khi materialize kết quả. Nếu thiếu, SQLAlchemy 2.0 sẽ yêu cầu unique explicit vì JOIN tạo duplicate parent rows.

```python
stmt = select(User).options(joinedload(User.posts))
result = await session.execute(stmt)
users = result.scalars().unique().all()
```

**4. Pagination cursor-based thay vì offset cho large datasets:**

```python
# Offset-based: chậm với large offset
stmt = select(User).offset(10000).limit(20)  # Phải skip 10000 rows

# Cursor-based: luôn nhanh
stmt = select(User).where(User.id > last_id).limit(20).order_by(User.id)
```

**5. Đặt TTL cho tất cả Redis keys:**

```python
# SAI: Key không có TTL -> memory leak
await redis.set("user:1", data)

# ĐÚNG: Luôn set TTL
await redis.set("user:1", data, ex=300)  # 5 phút
```

---

## ⚖️ Trade-offs

### SQLAlchemy vs Prisma

| | SQLAlchemy 2.0 | Prisma |
|---|---|---|
| **Setup** | Phức tạp hơn | Đơn giản hơn |
| **Type safety** | Tốt với `Mapped[type]` | Xuất sắc (generated types) |
| **Flexibility** | Rất cao (raw SQL dễ) | Trung bình |
| **Learning curve** | Cao hơn | Thấp hơn |
| **Async** | Native support | Hỗ trợ tốt |
| **Community** | Lớn, lâu đời | Đang phát triển |

### Redis Cache-aside vs Write-through

| | Cache-aside | Write-through |
|---|---|---|
| **Khi nào update cache** | Khi read (lazy) | Khi write (eager) |
| **Stale data** | Có thể xảy ra | Ít hơn |
| **Implementation** | Đơn giản hơn | Phức tạp hơn |
| **Cache miss penalty** | Có (first read) | Không |
| **Phù hợp** | Read-heavy workloads | Write-heavy workloads |

---

## 🚀 Performance Notes

**1. Connection pooling:**

```python
# Production settings
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,       # Tương đương max connections trong pg_bouncer
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # Tránh "connection already closed" errors
)
```

**2. Bulk operations thay vì loop:**

```python
# CHẬM: N insert queries
for user_data in users_data:
    await session.execute(insert(User).values(**user_data))

# NHANH: 1 bulk insert
await session.execute(insert(User), users_data)
```

**3. Redis pipeline cho multiple operations:**

```python
# N round trips
for key, value in items:
    await redis.set(key, value, ex=300)

# 1 round trip
async with redis.pipeline(transaction=True) as pipe:
    for key, value in items:
        pipe.set(key, value, ex=300)
    await pipe.execute()
```

---

## 📝 Tóm tắt

| Tính năng | Cú pháp |
|---|---|
| **Model** | `class User(Base): id: Mapped[int] = mapped_column(...)` |
| **Engine** | `create_async_engine(url, pool_size=10)` |
| **Session** | `async_sessionmaker(engine, expire_on_commit=False)` |
| **Query all** | `(await session.execute(select(User))).scalars().all()` |
| **Query one** | `(await session.execute(select(User).where(...))).scalar_one_or_none()` |
| **Get by PK** | `await session.get(User, user_id)` |
| **Eager load** | `select(User).options(selectinload(User.posts))` |
| **Insert** | `session.add(user); await session.flush(); await session.refresh(user)` |
| **Bulk update** | `session.execute(update(User).where(...).values(...))` |
| **Delete** | `await session.delete(user); await session.flush()` |
| **Migration** | `alembic revision --autogenerate -m "msg"` |
| **Apply** | `alembic upgrade head` |
| **Rollback** | `alembic downgrade -1` |
| **Redis get** | `await redis.get(key)` |
| **Redis set** | `await redis.set(key, value, ex=ttl)` |
| **Redis delete** | `await redis.delete(key)` |
