# Day 16: Lua Scripting & Redis Functions — Exercises

Thời gian: ~2 giờ
Tool: `redis-cli`, TypeScript + ioredis, Docker Compose

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. EVAL Cơ Bản (5 phút)

```bash
# Kết nối redis-cli
redis-cli

# Test EVAL đơn giản
EVAL "return 'Hello from Lua'" 0
# Expected: "Hello from Lua"

# EVAL với KEYS[] và ARGV[]
EVAL "return 'Key: ' .. KEYS[1] .. ', Arg: ' .. ARGV[1]" 1 mykey myarg
# Expected: "Key: mykey, Arg: myarg"

# EVAL với redis.call
SET mycounter 10
EVAL "return redis.call('INCR', KEYS[1])" 1 mycounter
# Expected: 11

# EVAL với redis.call trả về nil
EVAL "return redis.call('GET', 'nonexistent_key_xyz')" 0
# Expected: (nil)
```

### 1.2. SCRIPT LOAD & EVALSHA (5 phút)

```bash
# Load script vào cache
SCRIPT LOAD "return redis.call('INCR', KEYS[1])"
# Expected: "sha1hash..." (ghi lại SHA1 này)

# Chạy bằng EVALSHA (cache hit)
EVALSHA "<paste SHA1 ở trên>" 1 mycounter
# Expected: 12

# Gây NOSCRIPT bằng script chưa load
EVALSHA "0000000000000000000000000000000000000000" 1 mycounter
# Expected: -NOSCRIPT No matching script. Use EVAL.

# Kiểm tra script tồn tại
SCRIPT EXISTS "<paste SHA1 ở trên>"
# Expected: 1

SCRIPT EXISTS "0000000000000000000000000000000000000000"
# Expected: 0
```

### 1.3. SCRIPT KILL — Tạo và Kill Long-Running Script (5-7 phút)

```bash
# Load script có vòng lặp lớn (script này sẽ block Redis)
SCRIPT LOAD "
local i = 0
while i < 100000000 do
  i = i + 1
end
return i
"
# Lưu SHA1

# Chạy script (nó sẽ block ~100-500ms)
# Mở terminal 2, chạy command sau TRƯỚC KHI chạy script:
# redis-cli --latency-history

# EVALSHA với SHA1 vừa load (chạy trong terminal 1)
# Expected: p99 latency spike ở terminal 2

# Trong terminal 2, kill script
SCRIPT KILL
# Expected: OK

# Verify Redis still responsive
redis-cli PING
# Expected: +PONG
```

### 1.4. redis.call vs redis.pcall (3-5 phút)

```bash
# redis.call — error propagation
EVAL "
redis.call('INVALID_COMMAND')
return 'unreachable'
" 0
# Expected: -ERR Unknown Redis command

# redis.pcall — error catch
EVAL "
local ok, err = redis.pcall('INVALID_COMMAND')
if not ok then
  return 'Caught error: ' .. err
end
return 'OK'
" 0
# Expected: "Caught error: ERR Unknown Redis command"
```

---

## 2. Hands-on Lab (60-70 phút)

### Mục tiêu

Implement sliding window rate limiter bằng Lua script trong TypeScript + ioredis. Benchmark vs application-level approach (3 round-trips). Đo latency improvement.

### 2.1. Setup Project (5 phút)

```bash
mkdir -p ~/day16-lua-ratelimiter && cd ~/day16-lua-ratelimiter
npm init -y
npm install ioredis typescript ts-node @types/node
npx tsc --init
```

### 2.2. docker-compose.yml

```yaml
version: '3.8'
services:
  redis:
    image: redis:7.2
    ports:
      - "6379:6379"
    command: redis-server --save "" --appendonly no --lua-time-limit 5000
    # save "" = disable RDB (lab environment)
    # appendonly no = disable AOF
    # lua-time-limit = 5000ms
```

```bash
docker-compose up -d
docker-compose ps
```

### 2.3. Starter Code — Sliding Window Rate Limiter

Tạo file `src/ratelimiter.ts`:

```typescript
// src/ratelimiter.ts
import Redis from 'ioredis';

// Sliding window rate limiter bằng Lua script
// Keys[1] = rate limit key (e.g., "ratelimit:user:123")
// ARGV[1] = window size in seconds
// ARGV[2] = max requests in window
// ARGV[3] = current timestamp
// Returns: {allowed (0/1), current_count, limit}

const SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local request_id = ARGV[4]

local window_start = now - window

-- Remove old entries outside window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count requests in window
local current = redis.call('ZCARD', key)

if current < limit then
  -- Add new request with deterministic member supplied by client
  redis.call('ZADD', key, now, request_id)
  redis.call('EXPIRE', key, window + 1)
  return {1, current + 1, limit}
end

return {0, current, limit}
`;

class SlidingWindowRateLimiter {
  private redis: Redis;
  private scriptSha: string | null = null;

  constructor(redis: Redis) {
    this.redis = redis;
  }

  // SCRIPT LOAD on startup — bắt buộc production
  async init(): Promise<void> {
    this.scriptSha = await this.redis.script('LOAD', SLIDING_WINDOW_LUA);
    console.log(`[init] Script loaded, SHA: ${this.scriptSha}`);
  }

  // EVALSHA with NOSCRIPT fallback
  async check(key: string, windowSec: number, limit: number): Promise<{
    allowed: boolean;
    current: number;
    limit: number;
    method: 'EVALSHA' | 'EVAL';
  }> {
    const now = Math.floor(Date.now() / 1000);
    const requestId = `${now}:${process.pid}:${Math.random().toString(36).slice(2)}`;
    let result: any;
    let method: 'EVALSHA' | 'EVAL' = 'EVALSHA';

    if (this.scriptSha) {
      try {
        result = await this.redis.evalsha(
          this.scriptSha, 1, key, windowSec, limit, now, requestId
        );
      } catch (err: any) {
        if (err.message.includes('NOSCRIPT')) {
          // Fallback: re-load script
          this.scriptSha = await this.redis.script('LOAD', SLIDING_WINDOW_LUA);
          console.log(`[noscript] Script reloaded, SHA: ${this.scriptSha}`);
          result = await this.redis.evalsha(
            this.scriptSha, 1, key, windowSec, limit, now, requestId
          );
          method = 'EVAL';
        } else {
          throw err;
        }
      }
    } else {
      result = await this.redis.eval(
        SLIDING_WINDOW_LUA, 1, key, windowSec, limit, now, requestId
      );
      method = 'EVAL';
    }

    return {
      allowed: result[0] === 1,
      current: result[1],
      limit: result[2],
      method,
    };
  }
}

// ============ Application-level rate limiter (baseline) ============
// 3 round-trips: ZREMRANGEBYSCORE + ZCARD + ZADD + EXPIRE

async function appLevelCheck(
  redis: Redis,
  key: string,
  windowSec: number,
  limit: number
): Promise<{ allowed: boolean; current: number; limit: number }> {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - windowSec;

  await redis.zremrangebyscore(key, '-inf', windowStart);
  const current = await redis.zcard(key);

  if (current < limit) {
    const pipeline = redis.pipeline();
    pipeline.zadd(key, now, `${now}:${Math.random()}`);
    pipeline.expire(key, windowSec + 1);
    await pipeline.exec();
    return { allowed: true, current: current + 1, limit };
  }

  return { allowed: false, current, limit };
}

// ============ Benchmark ============

async function benchmark() {
  const redis = new Redis({ host: 'localhost', port: 6379 });
  const limiter = new SlidingWindowRateLimiter(redis);

  await limiter.init();
  await redis.flushdb();

  const key = 'ratelimit:test';
  const window = 60;
  const limit = 100;
  const iterations = 500;

  // Warm-up
  for (let i = 0; i < 10; i++) {
    await limiter.check(key, window, limit);
  }

  // Benchmark Lua script (EVALSHA)
  const luaTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const t0 = performance.now();
    await limiter.check(key, window, limit);
    const t1 = performance.now();
    luaTimes.push(t1 - t0);
  }

  // Benchmark application-level (3 round-trips)
  await redis.flushdb();
  const appTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const t0 = performance.now();
    await appLevelCheck(redis, key, window, limit);
    const t1 = performance.now();
    appTimes.push(t1 - t0);
  }

  // Stats
  function percentile(arr: number[], p: number): number {
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, idx)];
  }

  function avg(arr: number[]): number {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }

  console.log('\n========== Benchmark Results ==========');
  console.log(`Iterations: ${iterations}`);
  console.log('');
  console.log('Lua Script (EVALSHA):');
  console.log(`  Avg:   ${avg(luaTimes).toFixed(2)}us`);
  console.log(`  p50:   ${percentile(luaTimes, 50).toFixed(2)}us`);
  console.log(`  p95:   ${percentile(luaTimes, 95).toFixed(2)}us`);
  console.log(`  p99:   ${percentile(luaTimes, 99).toFixed(2)}us`);
  console.log('');
  console.log('Application-level (3 RTT):');
  console.log(`  Avg:   ${avg(appTimes).toFixed(2)}us`);
  console.log(`  p50:   ${percentile(appTimes, 50).toFixed(2)}us`);
  console.log(`  p95:   ${percentile(appTimes, 95).toFixed(2)}us`);
  console.log(`  p99:   ${percentile(appTimes, 99).toFixed(2)}us`);
  console.log('');
  const speedup = avg(appTimes) / avg(luaTimes);
  console.log(`Speedup: ${speedup.toFixed(2)}x faster with Lua`);

  await redis.quit();
}

benchmark().catch(console.error);
```

### 2.4. Chạy và Verify

```bash
npx ts-node src/ratelimiter.ts
```

**Expected output:**

```
[init] Script loaded, SHA: abc123...
[noscript] Script reloaded, SHA: abc123...

========== Benchmark Results ==========
Iterations: 500

Lua Script (EVALSHA):
  Avg:   ~150-250us
  p50:   ~140-200us
  p95:   ~200-300us
  p99:   ~300-500us

Application-level (3 RTT):
  Avg:   ~400-800us
  p50:   ~350-700us
  p95:   ~600-1000us
  p99:   ~800-1500us

Speedup: ~3-5x faster with Lua
```

### 2.5. Test Atomicity — Simulate Concurrent Requests

Thêm test này vào cuối `src/ratelimiter.ts`:

```typescript
async function testAtomicity() {
  const redis = new Redis({ host: 'localhost', port: 6379 });
  const limiter = new SlidingWindowRateLimiter(redis);
  await limiter.init();
  await redis.flushdb();

  const key = 'ratelimit:atomicity-test';
  const window = 1; // 1 second
  const limit = 10; // allow only 10

  // Simulate 20 concurrent requests
  const results = await Promise.all(
    Array.from({ length: 20 }, () => limiter.check(key, window, limit))
  );

  const allowed = results.filter((r) => r.allowed).length;
  const denied = results.filter((r) => !r.allowed).length;

  console.log('\n========== Atomicity Test ==========');
  console.log(`Total requests: 20`);
  console.log(`Allowed: ${allowed} (expected: 10)`);
  console.log(`Denied:  ${denied} (expected: 10)`);
  console.log(`Atomic:  ${allowed === 10 ? 'PASS' : 'FAIL'}`);

  await redis.quit();
}

testAtomicity().catch(console.error);
```

### 2.6. Verify NOSCRIPT Fallback

```typescript
async function testNoscriptFallback() {
  const redis = new Redis({ host: 'localhost', port: 6379 });
  const limiter = new SlidingWindowRateLimiter(redis);
  await limiter.init();

  // Force cache miss: flush script cache
  await redis.script('FLUSH');
  console.log('[test] Script cache flushed');

  // Check should fallback to EVAL automatically
  const result = await limiter.check('ratelimit:fallback-test', 60, 10);
  console.log('\n========== NOSCRIPT Fallback Test ==========');
  console.log(`Method:  ${result.method} (expected: EVAL — fallback worked)`);
  console.log(`Result:  allowed=${result.allowed}, current=${result.current}`);
  console.log(`Fallback: ${result.method === 'EVAL' ? 'PASS' : 'FAIL'}`);

  await redis.quit();
}

testNoscriptFallback().catch(console.error);
```

**Expected output:**
```
[test] Script cache flushed
[noscript] Script reloaded, SHA: abc123...

========== NOSCRIPT Fallback Test ==========
Method:  EVAL (expected: EVAL — fallback worked)
Result:  allowed=true, current=1
Fallback: PASS
```

---

## 3. Challenge Exercise (30-40 phút)

### Mục tiêu

Convert logic 3 round-trip (`GET + DECRBY + HSET + EXPIRE`) thành Lua script + Redis Function. Benchmark blocking impact khi script phức tạp hơn.

### 3.1. Convert 3-Round-Trip Logic Sang Lua

Logic cần convert: **Atomic inventory reservation**

```
Round-trip 1: GET inventory:SKU001
Round-trip 2: DECRBY inventory:SKU001 <qty>
Round-trip 3: HSET orders:reservations <order_id> <qty>
Round-trip 4: EXPIRE inventory:SKU001 3600  (optional)
```

Yêu cầu:
- Tất cả trong 1 Lua script
- Check stock trước khi decrement (không âm)
- Log reservation bằng HSET
- Redis Function version (Redis 7+)
- Benchmark latency vs 4 round-trip application-level

### 3.2. Expected Lua Script

```lua
-- KEYS[1] = inventory key (inventory:SKU001)
-- ARGV[1] = quantity to reserve
-- ARGV[2] = order ID
-- ARGV[3] = TTL for inventory key (optional, seconds)
-- Returns: {ok, remaining_stock} or {err, reason}

local inv_key = KEYS[1]
local qty = tonumber(ARGV[1])
local order_id = ARGV[2]
local ttl = tonumber(ARGV[3]) or 0

-- Check stock
local stock = redis.call('GET', inv_key)
if not stock then
    return {'err', 'ITEM_NOT_FOUND'}
end

stock = tonumber(stock)
if stock < qty then
    return {'err', 'INSUFFICIENT_STOCK', stock, qty}
end

-- Reserve
local new_stock = redis.call('DECRBY', inv_key, qty)

-- Log reservation
redis.call('HSET', 'orders:reservations', order_id, qty .. ':' .. new_stock)

-- Set TTL if provided
if ttl > 0 then
    redis.call('EXPIRE', inv_key, ttl)
end

return {'ok', new_stock}
```

### 3.3. Benchmark Script Blocking Impact

```typescript
// src/blocking-impact.ts
// Tạo script có 10ms execution time (bằng loop)
// Quan sát impact lên các request khác

const BLOCKING_SCRIPT = `
local start = redis.call('TIME', 'MONOTONIC')
local target = start[1] * 1000000 + start[2] + 10000
-- Loop cho đến khi đủ 10ms (10,000 microseconds)
while true do
  local now = redis.call('TIME', 'MONOTONIC')
  local current = now[1] * 1000000 + now[2]
  if current >= target then
    break
  end
end
return 'done'
`;

async function measureBlockingImpact() {
  const redis = new Redis({ host: 'localhost', port: 6379 });

  // Load blocking script
  const sha = await redis.script('LOAD', BLOCKING_SCRIPT);
  console.log(`Blocking script SHA: ${sha}`);

  // Pre-warm: execute normal request
  const warmTimes: number[] = [];
  for (let i = 0; i < 100; i++) {
    const t0 = performance.now();
    await redis.ping();
    warmTimes.push(performance.now() - t0);
  }

  const warmAvg = warmTimes.reduce((a, b) => a + b, 0) / warmTimes.length;
  console.log(`\nWarm ping avg: ${warmAvg.toFixed(2)}us`);

  // Run blocking script in background (fire-and-forget)
  console.log('\nRunning blocking script...');
  const blockStart = performance.now();
  redis.evalsha(sha, 0).catch(() => {}); // ignore error

  // Immediately after, try to execute normal ping
  // These should be delayed by the blocking script
  const delayedPings: number[] = [];
  for (let i = 0; i < 10; i++) {
    const t0 = performance.now();
    await redis.ping();
    const t1 = performance.now();
    delayedPings.push(t1 - t0);
  }

  const blockEnd = performance.now();
  console.log(`Blocking script duration: ${(blockEnd - blockStart).toFixed(0)}ms`);
  console.log('\nPings during blocking:');
  delayedPings.forEach((t, i) => {
    console.log(`  Ping ${i + 1}: ${t.toFixed(0)}us ${t > 5000 ? '<-- BLOCKED' : ''}`);
  });

  await redis.quit();
}

measureBlockingImpact().catch(console.error);
```

**Expected output:**

```
Warm ping avg: ~150us

Running blocking script...

Pings during blocking:
  Ping 1: 10123us  <-- BLOCKED (queued behind Lua VM)
  Ping 2: 9800us   <-- BLOCKED
  Ping 3: 9500us   <-- BLOCKED
  ...
```

### 3.4. Challenge Questions

Sau khi hoàn thành benchmark, trả lời:

1. Lua script 10ms làm p99 latency của 10 ping tăng bao nhiêu lần?
2. Nếu cần 1ms script execution, pool size = 10, throughput max là bao nhiêu ops/sec?
3. Khi nào trade-off của Lua atomicity không worth it?

---

## 4. Reflection Questions (5-10 phút)

### Câu 1

Bạn implement rate limiter bằng Lua. Sau 1 tháng, dev team phát hiện Lua script không persist trong RDB/AOF. Redis restart → script cache bị flush → tất cả request bị NOSCRIPT. Tại sao điều này xảy ra và làm sao fix triệt để?

### Câu 2

Trên Redis Cluster 6 nodes (3 master, 3 replica), bạn chạy SCRIPT LOAD trên master. Replica mới join vào cluster. Replica có script trong cache không? Tại sao? Nếu không, làm sao để đảm bảo?

### Câu 3

Bạn viết Lua script 3ms. Nhưng incident last week: p99 latency tăng từ 2ms lên 800ms trong 30 giây. Không có slow command trong SLOWLOG. Điều gì có thể gây ra và làm sao phát hiện?

### Câu 4

Khi nào bạn chọn Redis Functions thay vì Lua script ad-hoc? Nêu 3 scenario cụ thể.

---

## 5. Solution Guide

> **WARNING: Spoiler — đọc sau khi đã thử tự làm**

### Warm-up Solutions

**1.1 — EVAL Cơ Bản**: EVAL hoạt động giống như command thông thường. Lua VM execute script và return kết quả. `redis.call()` gọi Redis command. Return value phải là Lua primitive type (string, number, nil, array).

**1.2 — SCRIPT LOAD & EVALSHA**: `SCRIPT LOAD` compute SHA1 và store trong script cache (server-side). `EVALSHA` lookup SHA1 trong cache → cache hit: execute; cache miss: NOSCRIPT. Production pattern bắt buộc: SCRIPT LOAD on startup → EVALSHA on each call → catch NOSCRIPT → fallback EVAL.

**1.3 — SCRIPT KILL**: SCRIPT KILL chỉ work khi script CHƯA gọi write command. Nếu script đã write, Redis không thể rollback partial side effects an toàn; phương án cuối là `SHUTDOWN NOSAVE` và có rủi ro data loss. Đây là lý do phải benchmark script với dữ liệu lớn, giới hạn loop, và test long-running path trước khi deploy.

**1.4 — redis.call vs redis.pcall**: `redis.call()` propagate error về client (script stops). `redis.pcall()` (protected call) catch error và return error như string. Dùng `redis.pcall()` khi muốn handle error trong script thay vì crash.

### Hands-on Lab Solutions

**2.3 — Starter Code**: Code đã cung cấp đầy đủ. Điểm quan trọng:

- Trên Redis 7+, replication effects của script được xử lý theo command stream; ưu tiên script deterministic và khai báo key qua `KEYS[]`
- Unique member cho Sorted Set được tạo ở client và truyền qua `ARGV[4]`, tránh `math.random()` trong Lua
- `ZREMRANGEBYSCORE` với `-inf` xóa entries cũ
- Script trả về array `{}` → ioredis parse thành array

**2.5 — Atomicity Test**: Với 20 concurrent requests và limit = 10, kết quả phải đúng 10 allowed, 10 denied. Nếu > 10 allowed → atomicity bug (race condition). Sliding window rate limiter đúng atomic vì tất cả operations trong 1 Lua script.

**2.6 — NOSCRIPT Fallback**: SCRIPT FLUSH xóa cache → EVALSHA fail với NOSCRIPT → code catch và re-load → EVAL fallback. Pattern này đảm bảo script work ngay cả khi cache miss.

### Challenge Solutions

**3.1 — Lua Script cho Inventory Reservation**: Script đã cung cấp ở 3.2. Điểm chính:
- Check stock TRƯỚC khi decrement (atomic)
- Nếu không đủ stock, return error mà không thay đổi data
- Redis replicate effects của write script; code vẫn phải deterministic và không hardcode key ngoài `KEYS[]`
- TTL chỉ set khi > 0 (optional)

**3.3 — Blocking Impact**: Blocking script 10ms làm tất cả 10 ping phải đợi trong queue. Total wait time = 10ms × 10 = 100ms, chia cho 10 ping → mỗi ping đợi ~10ms. Đây là proof-of-concept: Lua atomicity là con dao hai lưỡi.

### Reflection Solutions

**Câu 1**: Lua script không persist trong RDB/AOF. Khi Redis restart, script cache bị flush. Fix: dùng Redis Functions (persist trong RDB/AOF) hoặc SCRIPT LOAD trong application startup hook.

**Câu 2**: Không. SCRIPT LOAD không replicate qua replication stream. Fix: SCRIPT LOAD trên mỗi node riêng (master + replica) hoặc dùng Redis Functions (library được replicate qua RDB).

**Câu 3**: p99 latency spike 800ms mà không có slow command = long-running Lua script. Script có thể chạy > lua-time-limit. Check: `redis-cli INFO stats | grep -E 'blocked_clients|instantaneous_ops'`; `redis-cli CLIENT LIST | grep cmd=eval`.

**Câu 4**: Chọn Redis Functions khi: (1) library lớn, nhiều team sử dụng — versioning giúp rollback dễ; (2) cần persist qua restart và replica sync; (3) muốn declarative deployment, có thể dump/restore.
