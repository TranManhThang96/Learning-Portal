# Day 27: Rate Limiting, Session & Leaderboard Patterns — Reference Document

---

## 1. Redis Commands Cheat Sheet

### Rate Limiting

```bash
# ============ FIXED WINDOW ============
INCR ratelimit:{user_id}:{window_ts}
EXPIRE ratelimit:{user_id}:{window_ts} 120   # 2x window size

# Check: if INCR result > LIMIT -> DENY

# ============ SLIDING WINDOW (Sorted Set) ============
# Add request timestamp
ZADD ratelimit:sw:{user_id} {timestamp_ms} {unique_id}

# Remove expired entries
ZREMRANGEBYSCORE ratelimit:sw:{user_id} 0 {timestamp_ms - window_ms}

# Count current window
ZCARD ratelimit:sw:{user_id}

# Set TTL
EXPIRE ratelimit:sw:{user_id} {window_sec + 10}

# ============ TOKEN BUCKET ============
HMGET ratelimit:tb:{user_id} tokens last_refill
HMSET ratelimit:tb:{user_id} tokens {val} last_refill {ts}
INCRBYFLOAT ratelimit:tb:{user_id} tokens {delta}
EXPIRE ratelimit:tb:{user_id} {bucket_size/refill_rate + 10}

# ============ SLIDING WINDOW COUNTER ============
# Sum last N minutes
INCR rate:{user_id}:{minute_bucket}
EXPIRE rate:{user_id}:{minute_bucket} 120

# Get last 60 minute counts
MGET rate:{user_id}:{t-59} rate:{user_id}:{t-58} ... rate:{user_id}:{t}
```

### Session Storage

```bash
# ============ SESSION CRUD ============
HSET session:{session_id} user_id 123 email "a@b.com" created_at 1710000000
HGET session:{session_id} user_id
HGETALL session:{session_id}
HEXISTS session:{session_id} user_id      # check exists
HDEL session:{session_id} field_name       # delete field
DEL session:{session_id}                   # logout (delete entire session)
EXPIRE session:{session_id} 86400          # refresh TTL (sliding)

# User-session index for bulk invalidation
SADD session:user:123 {session_id}
SMEMBERS session:user:123

# ============ REFRESH TOKEN ============
SET refresh:{user_id}:{device_id} {hashed_token} EX 604800 NX
GET refresh:{user_id}:{device_id}
DEL refresh:{user_id}:{device_id}           # revoke device

# ============ SESSION INVALIDATION ============
# Logout single session
DEL session:{session_id}

# Logout all user sessions
SMEMBERS session:user:{user_id}
# Process each: DEL session:{id}, then DEL session:user:{user_id}
```

### Leaderboard

```bash
# ============ LEADERBOARD BASIC ============
ZADD leaderboard:{board_id} {score} {member}
ZADD leaderboard:{board_id} 1000 "user:1" 1500 "user:2" 1200 "user:3"

# Top N (descending by score)
ZREVRANGE leaderboard:{board_id} 0 9 WITHSCORES

# User rank (0-indexed, descending)
ZRANK leaderboard:{board_id} "user:1"   # rank in ascending order
ZREVRANK leaderboard:{board_id} "user:1"  # rank in descending order

# User score
ZSCORE leaderboard:{board_id} "user:1"

# Update score atomically
ZINCRBY leaderboard:{board_id} 50 "user:1"

# Remove member
ZREM leaderboard:{board_id} "user:1"

# Count members
ZCARD leaderboard:{board_id}

# Range by score
ZCOUNT leaderboard:{board_id} 1000 2000   # members with score 1000-2000

# ============ LEADERBOARD PAGINATION ============
# Page 1: items 0-9
ZREVRANGE leaderboard:global 0 9 WITHSCORES

# Page 2: items 10-19
ZREVRANGE leaderboard:global 10 19 WITHSCORES

# ============ LEADERBOARD TIE-BREAKING ============
# Encode: final_score = score * 1e10 + (MAX_TS - timestamp)
# Earlier timestamp wins because ZREVRANGE returns higher score first.
ZADD leaderboard:global 100000000005 "user:1"  # score=10, ts=5, wins
ZADD leaderboard:global 100000000003 "user:2"  # score=10, ts=7

# ============ MULTIPLE LEADERBOARDS ============
ZADD leaderboard:global:weekly:{week} {score} {member}
ZADD leaderboard:global:daily:{YYYY-MM-DD} {score} {member}
```

### Idempotency Key

```bash
# ============ IDEMPOTENCY KEY ============
# Reserve before processing
SET idempotency:{key} '{"state":"processing","request_hash":"..."}' NX PX 86400000

# Store completed response after business operation succeeds
SET idempotency:{key} '{"state":"completed","response":{...}}' XX PX 86400000

# Read cached response
GET idempotency:{key}

# Delete (manual, rarely needed)
DEL idempotency:{key}

# Check exists
EXISTS idempotency:{key}
```

### Quota Tracking

```bash
# ============ QUOTA ============
INCR quota:{user_id}:requests:daily
EXPIRE quota:{user_id}:requests:daily 90000   # 25h

GET quota:{user_id}:requests:daily
GET quota:{user_id}:bandwidth:daily
GET quota:{user_id}:compute:daily
```

---

## 2. Lua Scripts Reference

### Fixed Window Rate Limiter (TypeScript/Go-friendly)

```lua
-- KEYS[1] = rate limit key
-- ARGV[1] = limit (max requests)
-- ARGV[2] = window size in seconds
-- ARGV[3] = current timestamp (use Redis TIME in app)

local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('INCR', key)
if current == 1 then
    redis.call('EXPIRE', key, window * 2)
end

if current > limit then
    return {0, current, limit, 'rate_limit_exceeded'}
else
    return {1, current, limit, 'allowed'}
end
```

### Sliding Window Rate Limiter

```lua
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

-- Remove entries older than window
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, unique_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return {1, count + 1, limit}
else
    return {0, count, limit}
end
```

### Token Bucket Rate Limiter

```lua
local key = KEYS[1]
local bucket_size = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])

-- Use Redis TIME for clock skew prevention
local now_arr = redis.call('TIME')
local now = tonumber(now_arr[1]) + tonumber(now_arr[2]) / 1000000

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = bucket_size
    last_refill = now
end

-- Refill tokens
local elapsed = now - last_refill
local refilled = elapsed * refill_rate
tokens = math.min(bucket_size, tokens + refilled)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {1, tokens, bucket_size}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {0, 0, bucket_size}
end
```

### Session Store with Sliding TTL

```lua
local session_key = KEYS[1]
local ttl = tonumber(ARGV[1])

-- Check session exists
local exists = redis.call('EXISTS', session_key)
if exists == 0 then
    return nil
end

-- Update last_accessed and refresh TTL
redis.call('HSET', session_key, 'last_accessed', ARGV[2])
redis.call('EXPIRE', session_key, ttl)

-- Return session data
return redis.call('HGETALL', session_key)
```

### Idempotency Key Reservation

```lua
local key = KEYS[1]
local ttl_ms = tonumber(ARGV[1])
local request_hash = ARGV[2]
local now = ARGV[3]

local existing = redis.call('GET', key)
if existing then
    return {0, existing}  -- cached completed response or in-progress marker
end

local marker = cjson.encode({
    state = 'processing',
    request_hash = request_hash,
    created_at = now
})

redis.call('SET', key, marker, 'NX', 'PX', ttl_ms)
return {1, marker}
```

### Multi-Dimensional Quota Check

```lua
local user_id = KEYS[1]
local api_limit = tonumber(ARGV[1])
local bandwidth_limit = tonumber(ARGV[2])
local compute_limit = tonumber(ARGV[3])

local api_key = 'quota:' .. user_id .. ':api:daily'
local bw_key = 'quota:' .. user_id .. ':bandwidth:daily'
local compute_key = 'quota:' .. user_id .. ':compute:daily'

local api_used = tonumber(redis.call('GET', api_key) or '0')
local bw_used = tonumber(redis.call('GET', bw_key) or '0')
local compute_used = tonumber(redis.call('GET', compute_key) or '0')

if api_used >= api_limit then
    return {0, 'api_quota_exceeded', api_used, api_limit}
end
if bw_used >= bandwidth_limit then
    return {0, 'bandwidth_quota_exceeded', bw_used, bandwidth_limit}
end
if compute_used >= compute_limit then
    return {0, 'compute_quota_exceeded', compute_used, compute_limit}
end

redis.call('INCR', api_key)
if api_used == 0 then redis.call('EXPIRE', api_key, 90000) end

return {1, 'allowed', api_used + 1, api_limit}
```

---

## 3. TypeScript Code Snippets

### Rate Limiter Service

```typescript
// src/services/ratelimiter.ts
import Redis from 'ioredis';

const SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, unique_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return {1, count + 1, limit}
else
    return {0, count, limit}
end
`;

export interface RateLimitResult {
  allowed: boolean;
  current: number;
  limit: number;
}

export class RateLimiter {
  constructor(private redis: Redis) {}

  async slidingWindow(
    userId: string,
    limit: number,
    windowMs: number = 60000,
  ): Promise<RateLimitResult> {
    const key = `ratelimit:sw:${userId}`;
    const now = Date.now();
    const uniqueId = `${now}:${Math.random().toString(36).slice(2)}`;

    const result = (await this.redis.eval(
      SLIDING_WINDOW_LUA,
      1,
      key,
      now.toString(),
      windowMs.toString(),
      limit.toString(),
      uniqueId,
    )) as [number, number, number];

    return {
      allowed: result[0] === 1,
      current: result[1],
      limit: result[2],
    };
  }

  async fixedWindow(
    userId: string,
    limit: number,
    windowSec: number = 60,
  ): Promise<RateLimitResult> {
    const nowSec = Math.floor(Date.now() / 1000);
    const windowStart = Math.floor(nowSec / windowSec) * windowSec;
    const key = `ratelimit:fw:${userId}:${windowStart}`;

    const pipeline = this.redis.pipeline();
    pipeline.incr(key);
    pipeline.ttl(key);
    const results = await pipeline.exec();

    if (!results) throw new Error('Redis pipeline failed');

    const count = results[0][1] as number;
    const ttl = results[1][1] as number;

    if (count === 1 && ttl === -1) {
      await this.redis.expire(key, windowSec * 2);
    }

    return {
      allowed: count <= limit,
      current: count,
      limit,
    };
  }
}
```

### Session Service

```typescript
// src/services/session.ts
import Redis from 'ioredis';
import { randomUUID } from 'crypto';

export interface Session {
  sessionId: string;
  userId: number;
  email: string;
  roles: string[];
  createdAt: number;
  lastAccessed: number;
  ipAddress: string;
  userAgent: string;
}

const SESSION_TTL_SECONDS = 86400; // 24h

export class SessionService {
  constructor(private redis: Redis) {}

  async create(
    userId: number,
    email: string,
    roles: string[],
    ipAddress: string,
    userAgent: string,
  ): Promise<Session> {
    const sessionId = randomUUID();
    const now = Date.now();

    const session: Session = {
      sessionId,
      userId,
      email,
      roles,
      createdAt: now,
      lastAccessed: now,
      ipAddress,
      userAgent,
    };

    const key = `session:${sessionId}`;
    await this.redis
      .multi()
      .hset(key, {
        sessionId: session.sessionId,
        userId: session.userId.toString(),
        email: session.email,
        roles: JSON.stringify(session.roles),
        createdAt: session.createdAt.toString(),
        lastAccessed: session.lastAccessed.toString(),
        ipAddress: session.ipAddress,
        userAgent: session.userAgent,
      })
      .expire(key, SESSION_TTL_SECONDS)
      .exec();

    // Index: user -> session
    await this.redis.sadd(`session:user:${userId}`, sessionId);

    return session;
  }

  async get(sessionId: string): Promise<Session | null> {
    const key = `session:${sessionId}`;
    const data = await this.redis.hgetall(key);

    if (!data || Object.keys(data).length === 0) {
      return null;
    }

    // Refresh TTL
    await this.redis.expire(key, SESSION_TTL_SECONDS);

    return {
      sessionId: data.sessionId,
      userId: Number(data.userId),
      email: data.email,
      roles: JSON.parse(data.roles || '[]'),
      createdAt: Number(data.createdAt),
      lastAccessed: Number(data.lastAccessed),
      ipAddress: data.ipAddress,
      userAgent: data.userAgent,
    };
  }

  async revoke(sessionId: string): Promise<void> {
    const key = `session:${sessionId}`;
    const session = await this.redis.hgetall(key);
    if (session?.userId) {
      await this.redis.srem(`session:user:${session.userId}`, sessionId);
    }
    await this.redis.del(key);
  }

  async revokeAllUserSessions(userId: number): Promise<number> {
    const sessionIds = await this.redis.smembers(`session:user:${userId}`);
    if (sessionIds.length === 0) return 0;

    const pipeline = this.redis.pipeline();
    for (const sessionId of sessionIds) {
      pipeline.del(`session:${sessionId}`);
    }
    pipeline.del(`session:user:${userId}`);
    await pipeline.exec();

    return sessionIds.length;
  }
}
```

### Leaderboard Service

```typescript
// src/services/leaderboard.ts
import Redis from 'ioredis';

export interface LeaderboardEntry {
  member: string;
  score: number;
  rank?: number;
}

export class LeaderboardService {
  constructor(private redis: Redis) {}

  async submitScore(
    boardId: string,
    member: string,
    score: number,
  ): Promise<void> {
    await this.redis.zadd(`leaderboard:${boardId}`, score, member);
  }

  async incrementScore(
    boardId: string,
    member: string,
    delta: number,
  ): Promise<number> {
    return await this.redis.zincrby(`leaderboard:${boardId}`, delta, member);
  }

  async getTopN(
    boardId: string,
    n: number = 100,
  ): Promise<LeaderboardEntry[]> {
    const results = await this.redis.zrevrange(
      `leaderboard:${boardId}`,
      0,
      n - 1,
      'WITHSCORES',
    );

    const entries: LeaderboardEntry[] = [];
    for (let i = 0; i < results.length; i += 2) {
      entries.push({
        member: results[i],
        score: parseFloat(results[i + 1]),
        rank: Math.floor(i / 2) + 1,
      });
    }
    return entries;
  }

  async getUserRank(boardId: string, member: string): Promise<number | null> {
    const rank = await this.redis.zrevrank(`leaderboard:${boardId}`, member);
    return rank !== null ? rank + 1 : null;
  }

  async getUserScore(boardId: string, member: string): Promise<number | null> {
    const score = await this.redis.zscore(`leaderboard:${boardId}`, member);
    return score !== null ? parseFloat(score) : null;
  }

  async getAroundUser(
    boardId: string,
    member: string,
    range: number = 5,
  ): Promise<LeaderboardEntry[]> {
    const rank = await this.redis.zrevrank(`leaderboard:${boardId}`, member);
    if (rank === null) return [];

    const start = Math.max(0, rank - range);
    const end = rank + range;

    const results = await this.redis.zrevrange(
      `leaderboard:${boardId}`,
      start,
      end,
      'WITHSCORES',
    );

    const entries: LeaderboardEntry[] = [];
    for (let i = 0; i < results.length; i += 2) {
      entries.push({
        member: results[i],
        score: parseFloat(results[i + 1]),
        rank: start + Math.floor(i / 2) + 1,
      });
    }
    return entries;
  }
}
```

### Idempotency Service

```typescript
// src/services/idempotency.ts
import Redis from 'ioredis';

const IDEMPOTENCY_TTL_MS = 86400000; // 24h

export interface IdempotencyResult<T> {
  isNew: boolean;
  response: T | null;
}

export class IdempotencyService {
  constructor(private redis: Redis) {}

  async reserveOrGet<T>(
    idempotencyKey: string,
    requestHash: string,
  ): Promise<IdempotencyResult<T> & { reserved: boolean; inProgress: boolean }> {
    const key = `idempotency:${idempotencyKey}`;
    const marker = JSON.stringify({
      state: 'processing',
      requestHash,
      createdAt: Date.now(),
    });

    const result = await this.redis.set(
      key,
      marker,
      'EX',
      Math.ceil(IDEMPOTENCY_TTL_MS / 1000),
      'NX',
    );

    if (result === null) {
      const existing = await this.redis.get(key);
      const parsed = existing ? JSON.parse(existing) : null;
      return {
        isNew: false,
        reserved: false,
        inProgress: parsed?.state === 'processing',
        response: parsed?.response ?? null,
      };
    }

    return {
      isNew: true,
      reserved: true,
      inProgress: true,
      response: null,
    };
  }

  async complete<T>(idempotencyKey: string, response: T): Promise<void> {
    await this.redis.set(
      `idempotency:${idempotencyKey}`,
      JSON.stringify({ state: 'completed', response, completedAt: Date.now() }),
      'EX',
      Math.ceil(IDEMPOTENCY_TTL_MS / 1000),
      'XX',
    );
  }

  async get(key: string): Promise<unknown | null> {
    const value = await this.redis.get(`idempotency:${key}`);
    return value ? JSON.parse(value) : null;
  }

  async exists(key: string): Promise<boolean> {
    const result = await this.redis.exists(`idempotency:${key}`);
    return result === 1;
  }
}
```

---

## 4. Go Code Snippets

### Rate Limiter in Go

```go
// internal/ratelimiter/ratelimiter.go
package ratelimiter

import (
    "context"
    "fmt"
    "math/rand"
    "time"

    "github.com/redis/go-redis/v9"
)

const SlidingWindowLua = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, unique_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return {1, count + 1, limit}
else
    return {0, count, limit}
end
`

type Result struct {
    Allowed bool
    Current int64
    Limit   int64
}

type RateLimiter struct {
    rdb *redis.Client
}

func New(rdb *redis.Client) *RateLimiter {
    return &RateLimiter{rdb: rdb}
}

func (rl *RateLimiter) SlidingWindow(ctx context.Context, userID string, limit int, windowMs int64) (*Result, error) {
    key := fmt.Sprintf("ratelimit:sw:%s", userID)
    now := time.Now().UnixMilli()
    uniqueID := fmt.Sprintf("%d:%d", now, rand.Int63())

    result, err := rl.rdb.Eval(ctx, SlidingWindowLua, []string{key},
        now, windowMs, limit, uniqueID,
    ).IntSlice()
    if err != nil {
        return nil, fmt.Errorf("sliding window eval: %w", err)
    }

    return &Result{
        Allowed: result[0] == 1,
        Current: int64(result[1]),
        Limit:   int64(result[2]),
    }, nil
}
```

### Session Store in Go

```go
// internal/session/session.go
package session

import (
    "context"
    "encoding/json"
    "fmt"
    "github.com/redis/go-redis/v9"
    "time"
)

type Session struct {
    SessionID    string   `json:"session_id"`
    UserID       int64    `json:"user_id"`
    Email        string   `json:"email"`
    Roles        []string `json:"roles"`
    CreatedAt    int64   `json:"created_at"`
    LastAccessed int64   `json:"last_accessed"`
    IPAddress    string   `json:"ip_address"`
    UserAgent    string   `json:"user_agent"`
}

const sessionTTL = 24 * time.Hour

type SessionStore struct {
    rdb *redis.Client
}

func New(rdb *redis.Client) *SessionStore {
    return &SessionStore{rdb: rdb}
}

func (s *SessionStore) Create(ctx context.Context, userID int64, email string, roles []string, ip, ua string) (*Session, error) {
    now := time.Now().UnixMilli()
    session := &Session{
        SessionID:    generateUUID(),
        UserID:       userID,
        Email:        email,
        Roles:        roles,
        CreatedAt:    now,
        LastAccessed: now,
        IPAddress:    ip,
        UserAgent:    ua,
    }

    data, err := json.Marshal(session)
    if err != nil {
        return nil, err
    }

    key := fmt.Sprintf("session:%s", session.SessionID)
    pipe := s.rdb.Pipeline()
    pipe.Set(ctx, key, data, sessionTTL)
    pipe.SAdd(ctx, fmt.Sprintf("session:user:%d", userID), session.SessionID)
    _, err = pipe.Exec(ctx)
    if err != nil {
        return nil, fmt.Errorf("create session: %w", err)
    }

    return session, nil
}

func (s *SessionStore) Get(ctx context.Context, sessionID string) (*Session, error) {
    key := fmt.Sprintf("session:%s", sessionID)
    data, err := s.rdb.Get(ctx, key).Bytes()
    if err == redis.Nil {
        return nil, nil
    }
    if err != nil {
        return nil, err
    }

    // Refresh TTL on access (sliding)
    s.rdb.Expire(ctx, key, sessionTTL)

    var session Session
    if err := json.Unmarshal(data, &session); err != nil {
        return nil, err
    }

    return &session, nil
}

func (s *SessionStore) RevokeAll(ctx context.Context, userID int64) (int64, error) {
    sessionIDs, err := s.rdb.SMembers(ctx, fmt.Sprintf("session:user:%d", userID)).Result()
    if err != nil {
        return 0, err
    }
    if len(sessionIDs) == 0 {
        return 0, nil
    }

    pipe := s.rdb.Pipeline()
    for _, sid := range sessionIDs {
        pipe.Del(ctx, fmt.Sprintf("session:%s", sid))
    }
    pipe.Del(ctx, fmt.Sprintf("session:user:%d", userID))
    _, err = pipe.Exec(ctx)
    if err != nil {
        return 0, err
    }

    return int64(len(sessionIDs)), nil
}
```

---

## 5. Production Checklist

### Rate Limiting

- [ ] Rate limiter dùng Redis TIME thay vì application time (clock skew prevention)
- [ ] Rate limit key có đủ granularity: `{tenant}:{user}:{endpoint}` hoặc `{ip}:{path}`
- [ ] Lua script atomic cho tất cả rate limiter phức tạp (sliding window, token bucket)
- [ ] Fixed window có EXPIRE set ngay khi INCR == 1
- [ ] Rate limiter fail CLOSED (reject when Redis unavailable) cho security-sensitive endpoints
- [ ] Rate limit response có `X-RateLimit-*` headers để client biết quota còn lại
- [ ] Token bucket dùng INCRBYFLOAT hoặc HMSET + Lua, không dùng GET + SET (race condition)
- [ ] Rate limit metrics được expose: `ratelimit_allowed_total`, `ratelimit_rejected_total`
- [ ] Alert khi rejection rate > 5% (indicates potential abuse)

### Session Storage

- [ ] Session keys có TTL luôn luôn được set (không có session key không có EXPIRE)
- [ ] Session TTL refresh trên mỗi request (sliding expiration)
- [ ] Password change trigger immediate session revocation
- [ ] All session invalidation operations là atomic
- [ ] Session data không chứa sensitive info plaintext (dùng encryption hoặc reference-only)
- [ ] Session cleanup job chạy periodic để clean orphaned sessions
- [ ] Session store monitored: `session:active_count`, memory usage
- [ ] Refresh token rotation implemented (revoke old + issue new on refresh)
- [ ] Session data audit: log session creation/destruction for security

### Leaderboard

- [ ] Hot key mitigation: shard leaderboard hoặc read from replica
- [ ] Tie-breaking encoded in score: `score * 1e10 + (MAX_TS - timestamp)`
- [ ] Leaderboard cleanup job: DEL old frozen leaderboards
- [ ] Write/read separation: ZADD to primary, ZREVRANGE from replica
- [ ] Monitor `replication_lag_seconds` — alert if > 500ms
- [ ] Leaderboard size monitored: ZCARD periodic check
- [ ] ZREMRANGEBYSCORE periodic để trim stale entries (nếu dùng sorted set for windowing)
- [ ] Pagination boundary check (avoid ZREVRANGE with very large offset)

### Idempotency Key

- [ ] Idempotency key TTL >= operation duration + buffer (min 24h for payments)
- [ ] Idempotency key format includes user_id hoặc client identifier
- [ ] Idempotency response stored as JSON with full original response
- [ ] Idempotency reserve atomic trước khi processing (`SET processing NX PX`, sau đó `SET completed XX PX`)
- [ ] Idempotency key checked BEFORE processing, not after
- [ ] Large response compressed before storing (use LZF compression)
- [ ] Idempotency key cleanup: Redis TTL handles auto-cleanup

### Quota Tracking

- [ ] Multi-dimensional quota check atomic trong single Lua script
- [ ] Quota key có tenant identifier để tránh cross-tenant bypass
- [ ] Quota increment atomic (INCR, không GET + SET)
- [ ] Quota reset strategy documented (daily, weekly, monthly)
- [ ] Quota near-limit alerts set (> 80% quota used)

---

## 6. Docker Compose Reference

```yaml
# docker-compose.yml for Day 27 exercises
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    command: >
      redis-server
      --save ""
      --appendonly no
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --lua-time-limit 5000
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-replica:
    image: redis:7.2-alpine
    ports:
      - "6380:6379"
    command: >
      redis-server
      --save ""
      --appendonly no
      --replicaof redis 6379
      --readonly
    depends_on:
      redis:
        condition: service_healthy

  app:
    image: node:20-alpine
    working_dir: /app
    volumes:
      - ./src:/app/src
      - ./package.json:/app/package.json
    ports:
      - "3000:3000"
    depends_on:
      redis:
        condition: service_healthy
    environment:
      REDIS_URL: redis://redis:6379
      REDIS_REPLICA_URL: redis://redis-replica:6379
    command: tail -f /dev/null
```

---

## 7. Useful Links

- Redis Rate Limiting Patterns: https://redis.io/docs/manual/redis-cli/
- Redis Sorted Set Commands: https://redis.io/commands/?group=sorted-set
- Redis Lua Scripting: https://redis.io/docs/interact/programmability/lua-api/
- Stripe Idempotency: https://stripe.com/docs/api/idempotent_requests
- GitHub Rate Limiting: https://docs.github.com/en/rest/rate-limit
- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket
- Cloudflare Rate Limiting: https://developers.cloudflare.com/cache/
- "Rate Limiting: Strategies and Algorithms" — Google SRE Book, Chapter 8
- "Scaling Redis Sessions" — Shopify Engineering Blog
- "How Discord Stores Trillions of Messages" — Discord Engineering Blog
