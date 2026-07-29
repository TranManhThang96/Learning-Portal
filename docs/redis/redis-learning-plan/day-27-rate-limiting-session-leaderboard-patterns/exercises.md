# Day 27: Rate Limiting, Session & Leaderboard Patterns — Exercises

Thời gian: ~2 giờ
Tool: `redis-cli`, TypeScript + ioredis, Go + go-redis, Docker Compose

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Fixed Window Rate Limiter với INCR + EXPIRE (5 phút)

```bash
redis-cli

# Fixed window: 1 phút window, limit = 5 requests
# Window timestamp = phút hiện tại
TIME
# Expected: [unixtimestamp, microseconds]

# Tính window key (thay bằng timestamp phút hiện tại của bạn)
# Ví dụ: timestamp = 1716000000, window = 60s
# Window start = 1716000000 / 60 * 60 = 1716000000

# Set một rate limit key với count = 3
INCR ratelimit:user:123:1716000000
# Expected: (integer) 1

INCR ratelimit:user:123:1716000000
# Expected: (integer) 2

INCR ratelimit:user:123:1716000000
# Expected: (integer) 3

# Check limit (limit = 5)
# 3 <= 5 -> ALLOWED

INCR ratelimit:user:123:1716000000
# Expected: (integer) 4

INCR ratelimit:user:123:1716000000
# Expected: (integer) 5

# Lần thứ 6: 6 > 5 -> DENIED

# Set TTL (chỉ set khi count == 1)
EXPIRE ratelimit:user:123:1716000000 120
# Expected: 1

# Kiểm tra TTL
TTL ratelimit:user:123:1716000000
# Expected: ~120

# Cleanup
DEL ratelimit:user:123:1716000000
```

### 1.2. Sliding Window Rate Limiter với Sorted Set (5 phút)

```bash
redis-cli

# Sliding window với Sorted Set
# Window: 10 giây, limit = 3 requests

# Lấy timestamp hiện tại (ms)
TIME
# Expected: [seconds, microseconds]

# Giả sử now_ms = 1716000000000

# Add 2 request entries
ZADD ratelimit:sw:user:456 1716000000000 "req:1"
# Expected: 1

ZADD ratelimit:sw:user:456 1716000000500 "req:2"
# Expected: 1

# Remove expired (entries older than now - 10000ms)
ZREMRANGEBYSCORE ratelimit:sw:user:456 0 1715999990000
# Expected: 0 (chưa có entry nào expired)

# Count current window
ZCARD ratelimit:sw:user:456
# Expected: 2

# Thêm request thứ 3 (allowed: 3 <= 3)
ZADD ratelimit:sw:user:456 1716000001000 "req:3"
# Expected: 1
ZCARD ratelimit:sw:user:456
# Expected: 3

# Thêm request thứ 4 (denied: 4 > 3)
ZADD ratelimit:sw:user:456 1716000001500 "req:4"
# Expected: 1
ZCARD ratelimit:sw:user:456
# Expected: 4 (vẫn cần reject)

# Set TTL
EXPIRE ratelimit:sw:user:456 11
# Expected: 1

# Cleanup
DEL ratelimit:sw:user:456
```

### 1.3. Leaderboard với Sorted Set (5-7 phút)

```bash
redis-cli

# Tạo leaderboard global
ZADD leaderboard:game:1 1500 "player:Alice"
# Expected: 1

ZADD leaderboard:game:1 2300 "player:Bob"
# Expected: 1

ZADD leaderboard:game:1 1800 "player:Charlie"
# Expected: 1

# Lấy top 3
ZREVRANGE leaderboard:game:1 0 2 WITHSCORES
# Expected:
# player:Bob 2300
# player:Charlie 1800
# player:Alice 1500

# Lấy rank của Alice (1-indexed, descending)
ZREVRANK leaderboard:game:1 "player:Alice"
# Expected: 2  (3rd place, 0-indexed = 2)

# Lấy rank của Bob
ZREVRANK leaderboard:game:1 "player:Bob"
# Expected: 0  (1st place)

# Update Alice score
ZINCRBY leaderboard:game:1 100 "player:Alice"
# Expected: 1600

# Kiểm tra Alice rank sau update
ZREVRANK leaderboard:game:1 "player:Alice"
# Expected: 1  (2nd place now)

# Lấy score của Charlie
ZSCORE leaderboard:game:1 "player:Charlie"
# Expected: 1800

# Tie-breaking: cùng score, earlier timestamp wins
# Encode: final = score * 1e10 + (MAX_TS - timestamp)
# MAX_TS = 9999999999
ZADD leaderboard:game:1 1000000005006 "player:X"  # score=1000, ts=4993 (wins)
ZADD leaderboard:game:1 1000000005005 "player:Y"  # score=1000, ts=4994
# ZREVRANGE trả score cao hơn trước, nên timestamp sớm hơn đứng trước
ZREVRANGE leaderboard:game:1 0 1 WITHSCORES
# Expected: player:X 1000000005006, player:Y 1000000005005

# Cleanup
DEL leaderboard:game:1
```

---

## 2. Hands-on Lab (60-70 phút)

### Mục tiêu

Implement đầy đủ: Rate Limiter (Lua), Session Store, Leaderboard, Idempotency Key cho một payment-like API mini bằng TypeScript + ioredis.

### 2.1. Setup Project (5 phút)

```bash
mkdir -p day27-patterns && cd day27-patterns
npm init -y
npm install ioredis typescript ts-node @types/node
npx tsc --init
```

```yaml
# docker-compose.yml
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
```

```bash
docker-compose up -d
docker-compose ps
```

### 2.2. Rate Limiter Implementation

Tạo `src/ratelimiter.ts`:

```typescript
// src/ratelimiter.ts
import Redis from 'ioredis';

// ===== LUA SCRIPTS =====

// Sliding Window Rate Limiter
const SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

-- Remove expired entries (older than window)
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests in window
local count = redis.call('ZCARD', key)

if count < limit then
    -- Allowed: add request
    redis.call('ZADD', key, now, unique_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return {1, count + 1, limit, 'allowed'}
else
    -- Denied: quota exceeded
    return {0, count, limit, 'rate_limit_exceeded'}
end
`;

// Token Bucket Rate Limiter
const TOKEN_BUCKET_LUA = `
local key = KEYS[1]
local bucket_size = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])

-- Use Redis TIME to avoid clock skew across app servers
local now_arr = redis.call('TIME')
local now = tonumber(now_arr[1]) + tonumber(now_arr[2]) / 1000000

-- Get stored state
local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

-- Initialize bucket if not exists
if tokens == nil then
    tokens = bucket_size
    last_refill = now
end

-- Refill tokens based on elapsed time
local elapsed = now - last_refill
local refilled = elapsed * refill_rate
tokens = math.min(bucket_size, tokens + refilled)

-- Try to consume token
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {1, tokens, bucket_size, 'allowed'}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(bucket_size / refill_rate) + 10)
    return {0, 0, bucket_size, 'rate_limit_exceeded'}
end
`;

export interface RateLimitResult {
  allowed: boolean;
  current: number;
  limit: number;
  reason: string;
}

export class RateLimiter {
  constructor(private redis: Redis) {}

  /**
   * Sliding Window Rate Limiter
   * @param userId - User identifier
   * @param limit - Max requests in window
   * @param windowMs - Window size in milliseconds (default: 60s)
   */
  async slidingWindow(
    userId: string,
    limit: number,
    windowMs: number = 60000,
  ): Promise<RateLimitResult> {
    const key = `ratelimit:sw:${userId}`;
    const now = Date.now();
    const uniqueId = `${now}:${Math.random().toString(36).slice(2, 9)}`;

    const result = (await this.redis.eval(
      SLIDING_WINDOW_LUA,
      1,
      key,
      now.toString(),
      windowMs.toString(),
      limit.toString(),
      uniqueId,
    )) as [number, number, number, string];

    return {
      allowed: result[0] === 1,
      current: result[1],
      limit: result[2],
      reason: result[3],
    };
  }

  /**
   * Token Bucket Rate Limiter
   * @param userId - User identifier
   * @param bucketSize - Max tokens (burst capacity)
   * @param refillRate - Tokens per second (sustain rate)
   */
  async tokenBucket(
    userId: string,
    bucketSize: number,
    refillRate: number,
  ): Promise<RateLimitResult> {
    const key = `ratelimit:tb:${userId}`;

    const result = (await this.redis.eval(
      TOKEN_BUCKET_LUA,
      1,
      key,
      bucketSize.toString(),
      refillRate.toString(),
    )) as [number, number, number, string];

    return {
      allowed: result[0] === 1,
      current: bucketSize - result[1], // consumed tokens
      limit: result[2],
      reason: result[3],
    };
  }

  /**
   * Fixed Window Rate Limiter (simple, non-Lua)
   * @param userId - User identifier
   * @param limit - Max requests per window
   * @param windowSec - Window size in seconds (default: 60s)
   */
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
    const [[incrErr, count], [ttlErr, ttl]] = await pipeline.exec() as any;

    if (count === 1) {
      await this.redis.expire(key, windowSec * 2);
    }

    return {
      allowed: (count as number) <= limit,
      current: count as number,
      limit,
      reason: (count as number) <= limit ? 'allowed' : 'rate_limit_exceeded',
    };
  }
}
```

Tạo `src/test-ratelimiter.ts`:

```typescript
// src/test-ratelimiter.ts
import Redis from 'ioredis';
import { RateLimiter } from './ratelimiter';

async function main() {
  const redis = new Redis('redis://localhost:6379');
  const limiter = new RateLimiter(redis);

  console.log('=== Sliding Window Rate Limiter Test ===');
  const swUser = 'user:sw:test';

  for (let i = 1; i <= 5; i++) {
    const result = await limiter.slidingWindow(swUser, 3, 60000);
    console.log(`Request ${i}: allowed=${result.allowed}, count=${result.current}/${result.limit}, reason=${result.reason}`);
  }

  // Request 6 should be denied
  const result6 = await limiter.slidingWindow(swUser, 3, 60000);
  console.log(`Request 6: allowed=${result6.allowed}, count=${result6.current}/${result6.limit}, reason=${result6.reason}`);

  console.log('\n=== Token Bucket Rate Limiter Test ===');
  const tbUser = 'user:tb:test';
  // Bucket: 5 tokens, refill 2 tokens/sec

  for (let i = 1; i <= 7; i++) {
    const result = await limiter.tokenBucket(tbUser, 5, 2);
    console.log(`Request ${i}: allowed=${result.allowed}, consumed=${result.current}/${result.limit}, reason=${result.reason}`);
    await new Promise(r => setTimeout(r, 300)); // wait 300ms between requests
  }

  console.log('\n=== Fixed Window Rate Limiter Test ===');
  const fwUser = 'user:fw:test';

  for (let i = 1; i <= 5; i++) {
    const result = await limiter.fixedWindow(fwUser, 3, 60);
    console.log(`Request ${i}: allowed=${result.allowed}, count=${result.current}/${result.limit}, reason=${result.reason}`);
  }

  await redis.quit();
  console.log('\nAll tests passed!');
}

main().catch(console.error);
```

```bash
npx ts-node src/test-ratelimiter.ts
# Expected output:
# === Sliding Window Rate Limiter Test ===
# Request 1: allowed=true, count=1/3, reason=allowed
# Request 2: allowed=true, count=2/3, reason=allowed
# Request 3: allowed=true, count=3/3, reason=allowed
# Request 4: allowed=false, count=3/3, reason=rate_limit_exceeded
# ...
```

### 2.3. Session Store Implementation

Tạo `src/session.ts`:

```typescript
// src/session.ts
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

const SESSION_TTL_SECONDS = 86400; // 24 hours

// Lua script for atomic get + TTL refresh
const SESSION_GET_LUA = `
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local now = ARGV[2]

local exists = redis.call('EXISTS', key)
if exists == 0 then
    return nil
end

redis.call('HSET', key, 'last_accessed', now)
redis.call('EXPIRE', key, ttl)
return redis.call('HGETALL', key)
`;

export class SessionStore {
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

    // Index session by user for bulk invalidation
    await this.redis.sadd(`session:user:${userId}`, sessionId);

    return session;
  }

  async get(sessionId: string): Promise<Session | null> {
    const key = `session:${sessionId}`;
    const data = (await this.redis.eval(
      SESSION_GET_LUA,
      1,
      key,
      SESSION_TTL_SECONDS,
      Date.now().toString(),
    )) as string[] | null;

    if (!data || data.length === 0) return null;

    // Convert flat array to object
    const session: any = {};
    for (let i = 0; i < data.length; i += 2) {
      session[data[i]] = data[i + 1];
    }

    // Parse roles JSON
    if (session.roles) {
      session.roles = JSON.parse(session.roles);
    }

    session.userId = parseInt(session.userId);
    session.createdAt = parseInt(session.createdAt);
    session.lastAccessed = parseInt(session.lastAccessed);

    return session as Session;
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

  async getActiveSessionCount(userId: number): Promise<number> {
    return await this.redis.scard(`session:user:${userId}`);
  }
}
```

Tạo `src/test-session.ts`:

```typescript
// src/test-session.ts
import Redis from 'ioredis';
import { SessionStore } from './session';

async function main() {
  const redis = new Redis('redis://localhost:6379');
  const store = new SessionStore(redis);

  console.log('=== Session Store Test ===');

  // Create session
  const session = await store.create(
    1001,
    'alice@example.com',
    ['user', 'premium'],
    '192.168.1.1',
    'Mozilla/5.0',
  );
  console.log('Created session:', session.sessionId);

  // Read session (should refresh TTL)
  await new Promise(r => setTimeout(r, 100));
  const retrieved = await store.get(session.sessionId);
  console.log('Retrieved session:', retrieved?.email, retrieved?.roles);

  // Check active session count
  const count = await store.getActiveSessionCount(1001);
  console.log('Active sessions for user 1001:', count);

  // Create second session for same user
  const session2 = await store.create(
    1001,
    'alice@example.com',
    ['user', 'premium'],
    '10.0.0.1',
    'Chrome/120',
  );

  const count2 = await store.getActiveSessionCount(1001);
  console.log('Active sessions after 2nd login:', count2);

  // Revoke single session
  await store.revoke(session2.sessionId);
  const count3 = await store.getActiveSessionCount(1001);
  console.log('Active sessions after revoke one:', count3);

  // Test non-existent session
  const nonExistent = await store.get('non-existent-id');
  console.log('Non-existent session:', nonExistent);

  // Cleanup
  await store.revokeAllUserSessions(1001);

  await redis.quit();
  console.log('\nSession store tests passed!');
}

main().catch(console.error);
```

```bash
npx ts-node src/test-session.ts
# Expected:
# Created session: <uuid>
# Retrieved session: alice@example.com [ 'user', 'premium' ]
# Active sessions for user 1001: 1
# Active sessions after 2nd login: 2
# Active sessions after revoke one: 1
# Non-existent session: null
```

### 2.4. Leaderboard Implementation

Tạo `src/leaderboard.ts`:

```typescript
// src/leaderboard.ts
import Redis from 'ioredis';

export interface LeaderboardEntry {
  member: string;
  score: number;
  rank: number;
}

export class LeaderboardService {
  constructor(private redis: Redis) {}

  async submitScore(boardId: string, member: string, score: number): Promise<void> {
    await this.redis.zadd(`leaderboard:${boardId}`, score, member);
  }

  async incrementScore(boardId: string, member: string, delta: number): Promise<number> {
    return await this.redis.zincrby(`leaderboard:${boardId}`, delta, member);
  }

  async getTopN(boardId: string, n: number = 100): Promise<LeaderboardEntry[]> {
    const results = await this.redis.zrevrange(
      `leaderboard:${boardId}`, 0, n - 1, 'WITHSCORES'
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
      `leaderboard:${boardId}`, start, end, 'WITHSCORES'
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

  async getTotalPlayers(boardId: string): Promise<number> {
    return await this.redis.zcard(`leaderboard:${boardId}`);
  }

  async submitScoreWithTiebreaker(
    boardId: string,
    member: string,
    score: number,
    timestamp: number,
    maxTimestamp: number = 9999999999,
  ): Promise<void> {
    // Encode: final_score = score * 1e10 + (maxTimestamp - timestamp)
    // Higher final_score wins tie; earlier timestamp has larger (maxTimestamp - timestamp).
    // Keep score and timestamp ranges bounded to avoid exceeding Number.MAX_SAFE_INTEGER.
    const finalScore = score * 1e10 + (maxTimestamp - timestamp);
    await this.redis.zadd(`leaderboard:${boardId}`, finalScore, member);
  }
}
```

### 2.5. Idempotency Key Implementation

Tạo `src/idempotency.ts`:

```typescript
// src/idempotency.ts
import Redis from 'ioredis';

const IDEMPOTENCY_TTL_MS = 86400000; // 24 hours

export interface IdempotencyResult<T> {
  isNew: boolean;
  response: T | null;
  cached: boolean;
}

export class IdempotencyService {
  constructor(private redis: Redis) {}

  async executeOnce<T>(
    idempotencyKey: string,
    requestHash: string,
    processFn: () => Promise<T>,
  ): Promise<IdempotencyResult<T>> {
    const key = `idempotency:${idempotencyKey}`;
    const processing = JSON.stringify({
      state: 'processing',
      requestHash,
      createdAt: Date.now(),
    });

    const reserved = await this.redis.set(
      key,
      processing,
      'EX',
      Math.ceil(IDEMPOTENCY_TTL_MS / 1000),
      'NX',
    );

    if (reserved === null) {
      const existing = await this.redis.get(key);
      if (!existing) {
        throw new Error('idempotency_state_lost');
      }
      const parsed = JSON.parse(existing);
      if (parsed.requestHash && parsed.requestHash !== requestHash) {
        throw new Error('idempotency_key_reused_with_different_request');
      }
      if (parsed.state === 'processing') {
        return {
          isNew: false,
          cached: true,
          response: null,
        };
      }
      return {
        isNew: false,
        cached: true,
        response: parsed.response,
      };
    }

    try {
      const response = await processFn();
      await this.redis.set(
        key,
        JSON.stringify({
          state: 'completed',
          requestHash,
          response,
          completedAt: Date.now(),
        }),
        'EX',
        Math.ceil(IDEMPOTENCY_TTL_MS / 1000),
        'XX',
      );
      return {
        isNew: true,
        cached: false,
        response,
      };
    } catch (error) {
      await this.redis.del(key);
      throw error;
    }
  }

  async getResponse(key: string): Promise<unknown | null> {
    const value = await this.redis.get(`idempotency:${key}`);
    return value ? JSON.parse(value) : null;
  }
}
```

Tạo `src/test-all.ts`:

```typescript
// src/test-all.ts
import Redis from 'ioredis';
import { RateLimiter } from './ratelimiter';
import { SessionStore } from './session';
import { LeaderboardService } from './leaderboard';
import { IdempotencyService } from './idempotency';

async function main() {
  const redis = new Redis('redis://localhost:6379');
  const limiter = new RateLimiter(redis);
  const sessionStore = new SessionStore(redis);
  const leaderboard = new LeaderboardService(redis);
  const idempotency = new IdempotencyService(redis);

  console.log('=== Integration Test ===\n');

  // 1. Rate Limiter
  console.log('1. Rate Limiter');
  for (let i = 1; i <= 3; i++) {
    const r = await limiter.slidingWindow('user:integration:test', 3, 60000);
    console.log(`   req ${i}: allowed=${r.allowed}`);
  }
  const denied = await limiter.slidingWindow('user:integration:test', 3, 60000);
  console.log(`   req 4 (should deny): allowed=${denied.allowed}`);

  // 2. Session Store
  console.log('\n2. Session Store');
  const session = await sessionStore.create(
    2001, 'bob@test.com', ['user'], '1.1.1.1', 'Test/1.0'
  );
  console.log(`   created: ${session.sessionId.slice(0, 8)}...`);
  const retrieved = await sessionStore.get(session.sessionId);
  console.log(`   retrieved email: ${retrieved?.email}`);
  await sessionStore.revokeAllUserSessions(2001);

  // 3. Leaderboard
  console.log('\n3. Leaderboard');
  await leaderboard.submitScore('integration:game', 'player:A', 1500);
  await leaderboard.submitScore('integration:game', 'player:B', 2000);
  await leaderboard.submitScore('integration:game', 'player:C', 1750);
  const top3 = await leaderboard.getTopN('integration:game', 3);
  console.log('   top 3:', top3.map(e => `${e.rank}. ${e.member}(${e.score})`).join(', '));
  const rank = await leaderboard.getUserRank('integration:game', 'player:A');
  console.log(`   player:A rank: #${rank}`);
  await redis.del('leaderboard:integration:game');

  // 4. Idempotency Key
  console.log('\n4. Idempotency Key');
  const key = 'payment:user:2001:order:5001';
  let processedCount = 0;

  const requestHash = 'sha256:payment:user:2001:order:5001:amount:50000';

  const result1 = await idempotency.executeOnce(key, requestHash, async () => {
    processedCount++;
    return { status: 'success', amount: 50000, txId: 'tx:abc123' };
  });
  console.log(`   first call: isNew=${result1.isNew}, cached=${result1.cached}, response=`, result1.response);

  const result2 = await idempotency.executeOnce(key, requestHash, async () => {
    processedCount++;
    return { status: 'success', amount: 50000, txId: 'tx:def456' }; // won't be called
  });
  console.log(`   second call (retry): isNew=${result2.isNew}, cached=${result2.cached}, response=`, result2.response);
  console.log(`   processedCount=${processedCount} (should be 1)`);

  // Cleanup
  await redis.del(`idempotency:${key}`);
  await redis.quit();

  console.log('\n=== All integration tests passed! ===');
}

main().catch(console.error);
```

```bash
npx ts-node src/test-all.ts
```

---

## 3. Challenge Exercise (30-40 phút)

### Thiết kế: Multi-tenant Rate Limiter + Quota System

**Yêu cầu**: Implement một hệ thống rate limiting + quota tracking cho multi-tenant SaaS API.

**Requirements**:

1. **Per-tenant rate limit**: Mỗi tenant có quota riêng (req/min)
2. **Per-endpoint rate limit**: `/api/expensive` có quota thấp hơn `/api/standard`
3. **Per-user within tenant**: Mỗi user trong tenant có quota con
4. **Multi-dimensional quota**: Track API calls, bandwidth (bytes), compute time
5. **Atomic**: Tất cả checks trong 1 Redis round-trip
6. **Graceful degradation**: Khi Redis unavailable, fail CLOSED cho payment endpoints, có thể fail OPEN cho non-critical endpoints

**Key structure**:
```
ratelimit:tenant:{tenant_id}:endpoint:{endpoint}:user:{user_id}
quota:{tenant_id}:{user_id}:{dimension}:daily
```

**Deliverable**: Lua script + TypeScript wrapper + benchmark script đo p50/p95/p99 latency với 1000 requests concurrent.

**Hint**: Dùng `redis.call('TIME')` trong Lua để tránh clock skew. Gộp rate limit check và quota check trong 1 Lua script khi cần atomicity end-to-end; chỉ tách thành 2 scripts nếu chấp nhận quota/rate-limit có thể lệch khi request fail giữa chừng. Đo latency với `console.time()`.

**Trade-off to discuss**:
- Tại sao multi-dimensional quota check nên dùng Lua thay vì pipeline?
- Khi nào nên cache rate limit result ở application layer? Trade-off là gì?
- Nếu quota check fail (Redis timeout), nên allow hay deny?

---

## 4. Reflection Questions

### Câu hỏi 1
Bạn vừa implement 4 thuật toán rate limiting khác nhau. Nếu phải chọn 1 algorithm duy nhất cho tất cả API endpoints trong production, bạn sẽ chọn algorithm nào? Tại sao? Trade-off là gì?

### Câu hỏi 2
Trong bài tập session store, bạn dùng Redis Hash + sliding TTL refresh. Nếu session traffic là 100K req/s và mỗi request phải HGETALL + EXPIRE = 2 Redis round-trips, memory là bao nhiêu và latency impact là gì? Có cách nào giảm round-trips không?

### Câu hỏi 3
Leaderboard với 5 triệu users trên single Redis key. Mỗi second có 500 score updates (ZINCRBY) và 10K read requests (ZREVRANGE top 100). Phân tích bottleneck và đề xuất solution.

### Câu hỏi 4
Idempotency key với 24h TTL cho payment API. Sau 25h, client retry với cùng idempotency key nhưng key đã expired. Điều gì xảy ra? Đây có phải bug không? Thiết kế nào tránh được scenario này?

---

## 5. Solution Guide

> **⚠️ SPOILER WARNING**: Phần này chứa đáp án. Đọc sau khi đã thử tự giải quyết challenge exercise.

---

### Challenge Solution: Multi-tenant Rate Limiter + Quota System

**Lua Script: Combined Rate Limit + Quota Check**

```lua
-- KEYS[1] = ratelimit key
-- KEYS[2] = quota:{tenant}:{user}:{dim}:daily
-- ARGV[1] = now (ms)
-- ARGV[2] = rate_window (ms)
-- ARGV[3] = rate_limit
-- ARGV[4] = unique_request_id
-- ARGV[5] = quota_limit
-- ARGV[6] = quota_used_increment

local rate_window = tonumber(ARGV[2])
local rate_limit = tonumber(ARGV[3])
local quota_limit = tonumber(ARGV[5])
local quota_increment = tonumber(ARGV[6])

-- Check rate limit (sliding window)
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, tonumber(ARGV[1]) - rate_window)
local rate_count = redis.call('ZCARD', KEYS[1])

if rate_count >= rate_limit then
    return {0, rate_count, rate_limit, 'rate_limit_exceeded', 0, quota_limit}
end

-- Check quota
local quota_used = tonumber(redis.call('GET', KEYS[2]) or '0')
if quota_used >= quota_limit then
    return {0, rate_count, rate_limit, 'quota_exceeded', quota_used, quota_limit}
end

-- Pass: increment both
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], math.ceil(rate_window / 1000) + 1)
local new_quota = redis.call('INCRBY', KEYS[2], quota_increment)
if new_quota == quota_increment then
    redis.call('EXPIRE', KEYS[2], 90000)  -- 25h
end

return {1, rate_count + 1, rate_limit, 'allowed', new_quota, quota_limit}
```

**TypeScript Wrapper**:

```typescript
async checkRateLimitAndQuota(
  tenantId: string,
  userId: string,
  endpoint: string,
  rateLimit: number,
  rateWindowMs: number,
  quotaLimit: number,
): Promise<{allowed: boolean; reason: string; rateCount: number; quotaUsed: number; quotaLimit: number}> {
  const key = `ratelimit:tenant:${tenantId}:endpoint:${endpoint}:user:${userId}`;
  const quotaKey = `quota:${tenantId}:${userId}:api:daily`;

  const result = (await this.redis.eval(
    COMBINED_LUA,
    2,
    key,
    quotaKey,
    Date.now().toString(),
    rateWindowMs.toString(),
    rateLimit.toString(),
    `${Date.now()}:${Math.random()}`,
    quotaLimit.toString(),
    '1',  // increment by 1 API call
  )) as [number, number, number, string, number, number];

  return {
    allowed: result[0] === 1,
    reason: result[3],
    rateCount: result[1],
    quotaUsed: result[4],
    quotaLimit: result[5],
  };
}
```

**Benchmark Script**:

```typescript
// src/benchmark.ts
import Redis from 'ioredis';
import { RateLimiter } from './ratelimiter';

async function benchmark() {
  const redis = new Redis('redis://localhost:6379');
  const limiter = new RateLimiter(redis);

  const CONCURRENT = 100;
  const TOTAL = 1000;
  const latencies: number[] = [];

  console.log(`Benchmarking sliding window rate limiter: ${TOTAL} requests, ${CONCURRENT} concurrent`);

  async function makeRequest(i: number) {
    const start = Date.now();
    await limiter.slidingWindow(`user:bench:${i % 100}`, 1000, 60000);
    return Date.now() - start;
  }

  const batches = Math.ceil(TOTAL / CONCURRENT);
  for (let b = 0; b < batches; b++) {
    const promises = [];
    for (let i = 0; i < CONCURRENT && b * CONCURRENT + i < TOTAL; i++) {
      promises.push(makeRequest(b * CONCURRENT + i));
    }
    const batchLatencies = await Promise.all(promises);
    latencies.push(...batchLatencies);
  }

  latencies.sort((a, b) => a - b);
  const p50 = latencies[Math.floor(latencies.length * 0.5)];
  const p95 = latencies[Math.floor(latencies.length * 0.95)];
  const p99 = latencies[Math.floor(latencies.length * 0.99)];
  const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;

  console.log(`Results: avg=${avg.toFixed(2)}ms, p50=${p50}ms, p95=${p95}ms, p99=${p99}ms`);
  console.log(`Throughput: ${(TOTAL / (latencies[latencies.length - 1] / 1000)).toFixed(0)} req/s`);

  await redis.quit();
}

benchmark().catch(console.error);
```

**Trade-off Analysis**:

1. **Lua vs Pipeline**: Lua đảm bảo atomicity — nếu quota check pass nhưng INCR fail (network blip), ta có inconsistent state. Pipeline không atomic. Với financial quota, atomic là bắt buộc.

2. **Application-layer caching**: Cache rate limit result 100-500ms có thể giảm Redis load đáng kể, nhưng introduce eventual consistency — user có thể bypass rate limit trong cache window. Trade-off: đổi latency cố định lấy Redis load. Chỉ nên cache cho non-critical endpoints.

3. **Redis timeout -> allow vs deny**: Payment endpoints = fail closed (deny). Non-critical display endpoints = fail open có thể chấp nhận. Luôn log và alert khi Redis unavailable. Production best practice: circuit breaker pattern — sau N failures, stop trying Redis và fail open/closed theo configured policy.

---

### Reflection Answers

**Câu 1**: Chọn sliding window. Reason: boundary burst của fixed window gây production incidents (đã phân tích ở lesson). Token bucket và leaky bucket phức tạp hơn cần thiết cho đa số use case. Sliding window cung cấp accuracy tốt với complexity chấp nhận được.

**Câu 2**: 100K req/s × 2 RTT × ~0.5ms/RTT = ~100ms total latency added. Redis handle 100K req/s dễ dàng, nhưng 2 RTT × 100K = 200K ops/s. Memory: 100K sessions × 500 bytes ≈ 50MB. Round-trip reduction: dùng Lua script cho `HGETALL + EXPIRE` trong 1 call.

**Câu 3**: Bottleneck là single hot key `leaderboard:global`. Solution: shard thành 16 shards bằng `user_id % 16`. Mỗi shard ~312K users. Top-N global = lấy top-N từ mỗi shard (16 × O(log 312K)) rồi merge + sort. Hoặc dùng read replica cho read-only leaderboard display.

**Câu 4**: Sau 25h, key expired. Client retry -> Redis sees no key -> processes payment lại -> duplicate charge. Đây là bug trong thiết kế TTL quá ngắn. Fix: TTL phải >= 2× operation time. Payment operations nên có TTL = operation duration × safety factor × 2. Minimum 7 days cho payment APIs. Hoặc: dùng DB unique constraint làm safety net, không chỉ Redis.
