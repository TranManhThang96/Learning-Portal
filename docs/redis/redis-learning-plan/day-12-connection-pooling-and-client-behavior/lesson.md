# Day 12: Connection Pooling & Client Behavior

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Tính toán được connection cost thực tế (TCP handshake, AUTH, TLS, SELECT db) và đo lường bằng `CLIENT LIST` / `CLIENT INFO`.
- Thiết kế connection pool size tối ưu dựa trên concurrency, command latency, và Redis single-threaded constraint.
- Implement timeout, retry với exponential backoff, và circuit breaker bằng Go/TypeScript — có khả năng chịu đựng Redis unavailable mà không gây cascading failure.
- Phân tích connection storm scenario khi rolling deploy 50 pods và đề xuất mitigation strategy (jittered startup, lazy pool grow).
- So sánh được client-side caching RESP3 vs Pub/Sub vs invalidation complexity — biết khi nào trade-off hợp lý.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: K8s Rolling Restart 50 Pods -> Connection Storm -> maxclients Limit

Ngày Black Friday, team deploy 50 microservice instances mới. Mỗi instance khởi động, tạo connection pool 50 connections đồng thời. 50 x 50 = 2500 connections đổ vào Redis server cùng lúc. Redis `maxclients` default = 10000, nhưng mỗi connection tốn ~17KB server-side memory + các Redis instance khác cũng đang chạy. Kết quả: vài instance đạt maxclients → connection refused → tất cả pod fail to connect → cascading failure toàn bộ service.

Không ai đặt câu hỏi: "Nếu 50 instance restart cùng lúc, max connection count của Redis là bao nhiêu?"

### Incident 2: Aggressive Retry -> Retry Storm -> Redis CPU 100%

Một API endpoint dùng Redis cho rate limiting. Khi Redis trễ 200ms (network blip), client retry 3 lần ngay lập tức (no backoff). 1000 requests/giây × 3 retry = 3000 requests/giây đổ vào Redis. Redis single-threaded bị overload → latency tăng → more retry → exponential explosion → 5x normal traffic → Redis CPU 100% → real outage kéo dài 15 phút.

Root cause: retry strategy không có exponential backoff, không có max retry count, không có circuit breaker.

### Incident 3: Pool Size 200 -> Throughput Lower Than Pool Size 30

Một dev nghĩ "pool càng lớn throughput càng cao". Set `PoolSize: 200` cho Redis single-threaded. Kết quả: 200 goroutines compete cho một connection thông qua mutex → context switch overhead cao → throughput thấp hơn pool 30. Thêm vào đó, 200 connections × 17KB = 3.4MB server-side memory overhead cho một service duy nhất.

**Bottom line**: Connection behavior là nơi nhiều senior developer mắc sai lầm nhất — không phải thiếu kiến thức, mà vì họ đưa ra assumption mà không benchmark.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model, event loop, I/O multiplexing (Day 1)
- TCP handshake, RTT, TLS basics (network fundamentals)
- Context của pool size với single-threaded Redis: vượt quá ~50-100 connections không cải thiện throughput
- `CLIENT LIST`, `CLIENT KILL`, `CLIENT INFO` (Day 1 đã giới thiệu)

---

## 4. Lý thuyết chi tiết

### 4.1. Connection Cost

Mỗi Redis connection có **real cost** — không phải miễn phí.

#### Cold Connect Cost

```txt
TCP handshake (no TLS):
  Client          Server
    |---- SYN ---->|
    |<--- SYN+ACK -|
    |---- ACK ---->|
  = 1 RTT (~1ms LAN, 10-30ms WAN)

TCP handshake (TLS 1.3):
  Client          Server
    |---- ClientHello ---->|
    |<--- ServerHello -----|   0.5 RTT
    |<--- [Finished] -----|   0.5 RTT
    |---- [Finished] ---->|
  = 1 RTT

AUTH command (optional):
  Client: AUTH password "..."
  Server: +OK
  = 1 RTT

SELECT db (optional):
  Client: SELECT 5
  Server: +OK
  = 1 RTT

Total cold connect:
  TCP only:     ~1ms   (LAN) / 10-30ms (WAN)
  TCP + AUTH:   ~2ms   (LAN) / 20-60ms (WAN)
  TCP + TLS:    ~2ms   (LAN) / 30-80ms (WAN)
  TCP + TLS + AUTH + SELECT: ~3-5ms (LAN) / 50-150ms (WAN)
```

**Per-connection memory**:
- Client-side: ~8-16KB per connection (socket buffer, runtime state)
- Server-side: ~17KB per connection (Redis internal data structures)

```txt
1000 cold connects from 1 service:
  = 1000 × 17KB = 17MB server memory
  + 1000 × 16KB = 16MB client memory
  + TCP handshake time: 1000 × 1ms = 1s total (sequential)
```

**Implication**: Nếu mỗi request tạo connection mới (connection per-request), với 10K requests/sec:
- Cold connect cost alone = 10K × 1ms = 10 giây/giây overhead = 100% CPU time chỉ để handshake.

### 4.2. Connection Pooling

Connection pooling giải quyết vấn đề trên: tái sử dụng connection thay vì tạo mới mỗi request.

#### Pool Architecture

```txt
Application
   |
   |-- Acquire connection from pool
   |     |
   |     v
   |   [Pool]
   |   +-------+-------+-------+-------+
   |   | Conn1 | Conn2 | Conn3 | idle  |  (max pool_size connections)
   |   +-------+-------+-------+-------+
   |     |
   |     |<-- available for reuse -->
   |     |
   |     v
   |   Execute Redis command
   |
   |-- Return connection to pool
```

#### Pool Lifecycle

```txt
acquire() {
    if idle_connection_available:
        conn = idle.pop()
        if conn.health_check_needed:
            ping()  // health check
        return conn
    elif pool_size < max_pool_size:
        conn = create_new_connection()  // TCP handshake
        return conn
    else:
        wait(timeout)   // pool exhausted
        if timeout:
            return ERROR_POOL_EXHAUSTED
}

release(conn) {
    if conn.error != nil:
        conn.close()    // remove from pool
        pool_size--
    else:
        conn.idle = true
        pool.push(conn)
}

health_check() {
    // Periodic: check idle connections are still alive
    // Run in background or on acquire
}
```

#### Pool Size Formula

```txt
pool_size = max_concurrent_requests × command_latency_ms / 1000

Example:
  - max_concurrent_requests = 100 (goroutines/processes)
  - command_latency_p99 = 1ms
  - pool_size = 100 × 1 / 1000 = 0.1 → round up = 1-5

  Conservative (high latency variance):
  - command_latency_p99 = 10ms
  - pool_size = 100 × 10 / 1000 = 1 → 10-20

  With pipelining (batch 100 commands, latency ~10ms for batch):
  - batch_latency = 10ms
  - pool_size = 100 × 10 / 1000 = 1 → 5-10
```

**Critical insight**: Vì Redis single-threaded, vượt quá ~50-100 connections cho một shard **không tăng throughput**, chỉ tăng:
- Context switch overhead (mutex contention)
- Server-side memory (17KB × connections)
- Complexity của pool management

```txt
Redis single-threaded:
  1 thread processes commands sequentially

  Pool size 1:  [====]
  Pool size 10: [====][====][====]... (all wait for 1 Redis thread)
  Pool size 100: [====][====][====]... × 10 (10× memory, same throughput)

  Effective throughput: pool_size_10 ≈ pool_size_100 (Redis bottleneck)
  Memory: pool_size_100 = 10× pool_size_10
```

**Rule of thumb**:

| Concurrency | Pool Size (LAN ~1ms) | Pool Size (WAN ~10ms) |
|---|---|---|
| 10 | 1-5 | 10-20 |
| 50 | 5-15 | 50-100 |
| 100 | 10-30 | 100-200 |
| 500 | 30-50 | 200-500 |

### 4.3. Per-Language Client Best Practices

#### Go: go-redis/v9

```go
import "github.com/redis/go-redis/v9"

rdb := redis.NewClient(&redis.Options{
    Addr:            "localhost:6379",
    DB:              0,
    PoolSize:        50,           // connections per node (not per goroutine)
    MinIdleConns:    10,           // always keep 10 connections warm
    MaxIdleConns:    50,           // max idle connections (≤ PoolSize)
    PoolTimeout:     4 * time.Second, // acquire timeout when pool exhausted
    ReadTimeout:     3 * time.Second,  // read deadline
    WriteTimeout:    3 * time.Second,  // write deadline
    DialTimeout:     5 * time.Second, // TCP/TLS handshake timeout
    // ConnMaxIdleTime/ConnMaxLifetime có thể dùng để kiểm soát vòng đời connection nếu cần
})

// Context timeout = per-command timeout (not pool acquire timeout)
ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
defer cancel()
val, err := rdb.Get(ctx, "key").Result()
```

**Key points**:
- `PoolSize`: total connections per Redis node. For Cluster: per-node, not total.
- `MinIdleConns`: keep N connections warm to avoid cold connect latency spikes.
- `PoolTimeout`: how long to wait when pool exhausted before returning error.
- `PoolSize` recommended: N×CPU cores × (command_latency / 1ms). For 1ms commands, 16 cores → 16×16×1 = 256 theoretical max. But Redis single-threaded → cap at 50-100.
- go-redis v9 tự động dùng internal connection pool (no external pool library needed).

#### TypeScript: ioredis

```typescript
import Redis from 'ioredis';

const redis = new Redis({
  host: 'localhost',
  port: 6379,
  connectionName: 'my-service-pool',   // for CLIENT LIST identification
  lazyConnect: true,                  // don't connect on init (use with retryStrategy)
  enableAutoPipelining: true,           // batch multiple commands automatically
  maxRetriesPerRequest: 3,             // retry on transient errors
  retryStrategy(times: number) {
    if (times > 10) return null;      // stop retrying, emit error
    const delay = Math.min(times * 100, 3000);
    return delay;                      // ms
  },
  // Backpressure: slow subscriber drops messages
  // For pub/sub: use separate connection or Stream consumer group
});

// Connect explicitly
await redis.connect();

// For Cluster:
import Redis from 'ioredis/cluster';
const cluster = new Redis.Cluster([...nodes], {
  maxRetriesPerRequest: 3,
  enableAutoPipelining: true,
  retryStrategy: (times) => Math.min(times * 200, 2000),
});
```

**Key points**:
- `connectionName`: set via `CLIENT SETNAME`, rất hữu ích khi debug.
- `lazyConnect: true`: don't connect on init → control startup timing → prevent connection storm.
- `enableAutoPipelining`: batch commands transparently → reduce RTT.
- `maxRetriesPerRequest`: retry logic per-command, NOT idempotent-safe by default.
- ioredis **is NOT thread-safe** (single-threaded Node.js → not an issue, but don't use in worker threads).

#### Java: Lettuce vs Jedis

**Lettuce (Netty-based, recommended)**:
```java
import io.lettuce.core.RedisClient;
import io.lettuce.core.RedisURI;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.sync.RedisCommands;
import io.lettuce.core.resource.ClientResources;
import io.lettuce.core.resource.DefaultClientResources;

ClientResources res = DefaultClientResources.builder()
    .ioThreadPoolSize(4)
    .computationThreadPoolSize(4)
    .build();

RedisClient client = RedisClient.create(res, RedisURI.create("localhost", 6379));
StatefulRedisConnection<String, String> conn = client.connect();

// Connection is thread-safe (Netty) — share across threads
// No Jedis-style pool needed for Lettuce
conn.sync().set("key", "value");

// For Cluster:
import io.lettuce.core.cluster.RedisClusterClient;
import io.lettuce.core.cluster.api.StatefulRedisClusterConnection;
```

**Lettuce key points**:
- `StatefulRedisConnection` là **thread-safe** (Netty Channel).
- Share 1 connection across all threads — no pool needed.
- `PoolSize` parameter in `ClientOptions` if pooling needed.
- `maxTotal` for connection pool (if using `redis.clients.jedis.JedisPooled`).

**Jedis (legacy, blocking, pool needed)**:
```java
import redis.clients.jedis.JedisPooled;
import redis.clients.jedis.params.SetParams;

JedisPooled jedis = new JedisPooled(
    new JedisPoolConfig(),
    "localhost", 6379
);

// Pool config
JedisPoolConfig poolConfig = new JedisPoolConfig();
poolConfig.setMaxTotal(50);
poolConfig.setMaxIdle(10);
poolConfig.setMinIdle(5);
poolConfig.setMaxWait(java.time.Duration.ofMillis(3000));

// Use
jedis.set("key", "value", new SetParams().ex(3600));
```

**Jedis key points**:
- Connection **NOT thread-safe** → need pool.
- `JedisPooled` is convenience wrapper over `JedisPool`.
- Jedis 4.x+ hỗ trợ reactive (non-blocking).

#### Python: redis-py

```python
import redis

# Sync: ConnectionPool (recommended over Jedis-style single connection)
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,      # total connections in pool
    socket_timeout=3.0,       # command timeout
    socket_connect_timeout=5.0,  # TCP handshake timeout
    decode_responses=True,
)

client = redis.Redis(connection_pool=pool)

# BlockingConnectionPool: blocks caller when pool exhausted
blocking_pool = redis.BlockingConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    timeout=10,  # seconds to wait for a connection
)

# Async: redis.asyncio
import redis.asyncio as aioredis

async_pool = aioredis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    decode_responses=True,
)
client = aioredis.Redis(connection_pool=async_pool)

# Usage
async def main():
    await client.set("key", "value")
    val = await client.get("key")
```

**Key points**:
- `ConnectionPool`: returns connection to pool after each operation (caller must not hold across await).
- `BlockingConnectionPool`: blocks (not async) → for sync code when pool exhausted.
- `redis.asyncio`: true async, uses `aioredis` protocol — preferred for FastAPI, asyncio apps.
- `max_connections=50` is reasonable; with single-threaded Redis, >100 connections rarely help.

### 4.4. Timeout Strategy

Timeouts cần phân lớp, không phải một giá trị duy nhất.

```txt
                    Request Lifecycle
                    =================
                    |
                    v
              Connect Timeout          (DNS + TCP + TLS + AUTH)
                    |
                    v
              Pool Acquire Timeout      (wait for idle connection)
                    |
                    v
              Command Timeout           (execute + wait for response)
                    |
                    v
              Fail / Return Error

Timeout Budget Rule:
  connect_timeout + pool_timeout + command_timeout < user-facing SLA budget
```

#### Timeout Guidelines

| Timeout Type | Default (LAN) | Default (WAN) | Notes |
|---|---|---|---|
| `DialTimeout` / `socket_connect_timeout` | 5s | 10s | TCP handshake |
| `PoolTimeout` / `connection_timeout` | 3-5s | 10s | Acquire from pool |
| `ReadTimeout` / `socket_timeout` | 2-3s | 5s | Per-command |
| `WriteTimeout` | 2-3s | 5s | Usually same as ReadTimeout |
| Per-command context timeout (Go) | 1-2s | 3s | Hard deadline |

**Timeout > p99 expected latency, < user-facing SLA budget**:

```txt
Expected p99 latency: 50ms
Timeout = 50ms × 5 = 250ms  (too tight, false failures)
Timeout = 50ms × 50 = 2500ms (too loose, hangs too long)

Right: p99 × 3-5 = 150-250ms
  → Low enough to fail fast
  → High enough to not false-fail on p99 spikes
```

### 4.5. Retry Strategy

#### Idempotent vs Non-Idempotent Commands

| Safe to Retry | NOT Safe to Retry |
|---|---|
| GET, MGET, SET, SETEX, MSET | INCR, DECR, INCRBY, DECRBY |
| DEL, HDEL, SADD, SREM | LPUSH, RPUSH, LTRIM (data loss) |
| EXPIRE, RENAME | SETNX (race condition) |
| SINTER, SUNION | GETSET (deprecated) |
| HSET (if overwriting) | SPOP, SRANDMEMBER |

**Critical rule**: `INCR` NOT safe to retry. Nếu server nhận `INCR counter` nhưng chưa return, retry → counter tăng 2 lần thay vì 1.

#### Exponential Backoff with Jitter

```go
// Backoff formula: base * 2^attempt + jitter
func backoff(attempt int) time.Duration {
    base := 100 * time.Millisecond
    max := 30 * time.Second
    jitter := time.Duration(rand.Int63n(int64(base))) // 0-100ms random

    delay := base * time.Duration(1<<attempt) // 100ms, 200ms, 400ms, 800ms...
    if delay > max {
        delay = max
    }
    return delay + jitter
}
```

**Jitter types**:
- **Full jitter** (recommended): `base * rand(0, 2^attempt)` — best for preventing thundering herd
- **Equal jitter**: `base * 2^attempt / 2 + rand(0, base/2)`
- **Decorrelated jitter**: `base * rand(base, base*3*2^attempt)`

#### Retry Configuration

```go
// Max retries per command: 2-3 is usually enough
// Retry on: connection errors, timeout errors
// DO NOT retry on: Redis errors (MOVED, ASK, WRONGTYPE, etc.)

retryableErrors := []error{
    redis.ErrClosed,           // connection closed
    context.DeadlineExceeded,  // command timeout
    syscall.ECONNRESET,        // connection reset
    syscall.ETIMEDOUT,         // connection timeout
}

// Non-retryable:
redis.Nil,      // key not found (expected, not error)
redis.ErrTxFailed, // transaction failed (WATCH conflict)
```

### 4.6. Reconnect Behavior

```txt
Client reconnect states:
  1. Connected: normal operation
  2. Disconnected: connection lost
      |
      v
  3. Reconnecting: client attempts reconnect
      |   - Exponential backoff
      |   - Max retries
      |   - Emit " reconnecting" event
      |
      v
  4. Connected: resumed
      |   - Topology may have changed (cluster/sentinel)
      v
  5. Failed: max retries exceeded
      |   - Emit " error" event
      |   - Application must handle
      v
  6. Circuit open: fast fail (see 4.8)
```

**Sentinel/Cluster topology refresh**:
- Sentinel: client subscribe `+switch-master` channel → auto-discover new master
- Cluster: client tracks `MOVED` redirects → updates slot mapping
- Với Sentinel: `sentinel.masterName` config → client tự reconnect khi failover xảy ra
- Với Cluster: MOVED response → update routing table → retry on correct node

**go-redis reconnect behavior**: Tự động reconnect khi connection bị đóng. Không cần manual reconnect logic.

### 4.7. Connection Storm

Connection storm xảy ra khi nhiều client instance connect đồng thời.

```txt
Normal:
  App Start (1 instance)
  → Create pool (50 connections)
  → Redis: 50 connections

Connection Storm (rolling deploy 50 instances):
  t=0s:  App Start (instance 1)  → Redis: 50 connections
  t=0s:  App Start (instance 2)  → Redis: 100 connections
  t=0s:  App Start (...50)       → Redis: 2500 connections
  t=0s:  Redis maxclients maybe hit → REJECTED → all instances fail to start
```

#### Mitigation: Staggered Startup

```go
// Random delay before creating connections
delay := time.Duration(rand.Int63n(int64(maxDelay)))
time.Sleep(delay)

// Or: gradual pool grow (go-redis MinIdleConns approach)
rdb := redis.NewClient(&redis.Options{
    MinIdleConns: 0,   // don't pre-create connections
    PoolSize: 50,
})
// Connections created lazily on first use
// → app starts fast, pool grows gradually under traffic
```

#### Mitigation: Jittered Connect

```go
// Add random jitter to retry delay to spread out reconnect attempts
func withJitter(baseDelay time.Duration, maxJitter time.Duration) time.Duration {
    jitter := time.Duration(rand.Int63n(int64(maxJitter)))
    return baseDelay + jitter
}

// Spread out reconnects after Redis restart
for i := 0; i < 50; i++ {
    go func() {
        time.Sleep(withJitter(0, 5*time.Second)) // spread over 5s
        client.Ping(ctx)
    }()
}
```

### 4.8. Backpressure

Backpressure = khi consumer không theo kịp producer, cascade ngược lại.

```txt
Client (1000 req/s) → Redis (single-threaded, 50K ops/s)
                            ↓
                      Works fine (headroom)
                            ↓
Client (50K req/s) → Redis (overloaded)
                            ↓
Redis latency spike → 1000 clients retry → 150K req/s
                            ↓
Redis more overloaded → 200K req/s → OOM / maxclients
                            ↓
All requests fail → cascading failure to upstream services
```

#### Strategies

| Strategy | Behavior | Trade-off |
|---|---|---|
| **Block** (default pool behavior) | Caller blocks until connection available | Latency spikes, thread exhaustion |
| **Fail fast** | Return error immediately when pool exhausted | Low latency, client must handle |
| **Bounded queue** | Queue requests with timeout | Middle ground, queue overflow risk |
| **Circuit breaker** | Fast fail when error rate high | Degrade gracefully |

```go
// Fail fast > queue indefinitely
ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
defer cancel()

select {
case <-pool.Acquire(ctx):
    // got connection
    defer pool.Release(conn)
    // do work
case <-ctx.Done():
    return ErrPoolExhausted // fail fast, don't queue forever
}
```

### 4.9. Circuit Breaker

Circuit breaker ngăn chặn cascade failure bằng cách stop calling a failing service.

```txt
Circuit Breaker States:

CLOSED (normal operation)
  │  Error rate > threshold (e.g., >50% in 10 requests)
  v
OPEN (fast fail)
  │  After reset timeout (e.g., 30s)
  v
HALF-OPEN (allow 1 test request)
  │  Test request succeeds
  v
CLOSED (back to normal)

  │  Test request fails
  v
OPEN (reset timeout)
```

```txt
         Request
             |
             v
    +----------------+
    |    CLOSED      |
    | (allow calls)  |
    +-------+--------+
            |
    error? | success?
            |         +---------+
            v         | timeout |
    +-------+----+    +----+----+
    |  failure++ |          |
    +------------+          |
            |               |
   failure > threshold?      |
        /     \             |
       NO     YES           |
       |        |            |
       v        v            |
   [stay]    OPEN            |
   CLOSED   (block)          |
            |                |
            | after timeout  |
            v                |
         HALF-OPEN --------->+
    (allow 1 test call)
```

#### gobreaker (sony/gobreaker) Integration

```go
import "github.com/sony/gobreaker"

cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{
    Name:        "redis-circuit-breaker",
    MaxRequests: 3,          // # requests allowed in HALF-OPEN state
    Interval:    10 * time.Second, // cyclic period to reset counts
    Timeout:     30 * time.Second, // time OPEN state before HALF-OPEN
    ReadyToTrip: func(counts gobreaker.Counts) bool {
        ratio := float64(counts.TotalFailures) / float64(counts.Requests)
        return counts.Requests >= 10 && ratio >= 0.5 // 50% failure rate
    },
    OnStateChange: func(name string, from, to gobreaker.State) {
        log.Printf("circuit breaker [%s] %s -> %s", name, from, to)
    },
})

// Wrap Redis call
func redisWithCircuitBreaker(ctx context.Context, rdb *redis.Client, key string) (string, error) {
    result, err := cb.Execute(func() (interface{}, error) {
        return rdb.Get(ctx, key).Result()
    })
    if err != nil {
        return "", err
    }
    return result.(string), nil
}
```

### 4.10. Client-Side Caching RESP3 (Redis 6+)

RESP3 client-side caching = server push invalidation to clients, giảm round-trips.

#### Two Modes

**Tracking Mode** (single connection, best for simple cases):
```txt
Client: CLIENT TRACKING ON
Server: +OK

[Key modified by another client]
Server: >INVALIDATE
        3
        mykey
```

**Broadcasting Mode** (prefix-based, scalable):
```txt
Client: CLIENT TRACKING ON BCAST
        OPTIN
Server: +OK

[Key matching prefix "user:*" modified]
Server: >INVALIDATE
        1
        user:*
```

#### When to Use

**Use when**:
- Read-heavy workload (90%+ reads)
- Same data read by many clients
- Data changes infrequently
- Want to avoid Redis round-trips entirely for reads

**Don't use when**:
- High write rate → invalidation overhead > benefit
- Cross-node/Cluster data mà client library không quản lý tracking theo từng node rõ ràng
- Need Pub/Sub (use Pub/Sub instead)
- Data has complex invalidation dependencies

```go
// go-redis: enable tracking
rdb.Do(ctx, "CLIENT", "TRACKING", "ON")
// go-redis handles INVALIDATE messages via PubSub
```

#### Trade-off vs Pub/Sub

| Aspect | RESP3 Client-Side Caching | Pub/Sub |
|---|---|---|
| Invalidation direction | Server → Client (push) | Bidirectional |
| Scope | Per-key or prefix | Channel-based |
| Complexity | Lower (auto-invalidation) | Higher (manual channel management) |
| Cross-node | Khó hơn: cần tracking theo node/slot và client support tốt | Yes |
| Scalability | Good for single-node hoặc per-shard cache | Good for fanout |

---

## 5. Trade-off Analysis

### 5.1. Large Pool vs Small Pool

| Aspect | Large Pool (100+) | Small Pool (10-50) |
|---|---|---|
| Memory client-side | High (100×16KB = 1.6MB/client) | Low |
| Memory server-side | High (100×17KB = 1.7MB/shard) | Low |
| Context switch overhead | High (goroutine/thread contention) | Low |
| Throughput (single-threaded Redis) | Same as small pool (Redis bottleneck) | Same |
| Connection storm risk | High (50 instances × 100 = 5000 connections) | Lower |
| Cold start latency | Lower (connections already warm) | Higher (connections created on demand) |
| Pool exhaust probability | Lower | Higher under high concurrency |
| Use when | High concurrency + pipelining + multi-node | Standard web service |

### 5.2. Aggressive Retry vs Fail Fast

| Aspect | Aggressive Retry (5+ retries, no backoff) | Fail Fast (0-2 retries, backoff) |
|---|---|---|
| Transient error survival | High | Low |
| Retry storm risk | HIGH | LOW |
| Latency on failure | High (multiple waits) | Low |
| Cascading failure risk | HIGH | LOW |
| Availability | Reduces failures | Accepts failures |
| Use when | Non-critical background jobs | User-facing APIs, SLA-bound |
| Recommended | NEVER without backoff | Default for production |

### 5.3. Timeout Short vs Timeout Long

| Aspect | Short Timeout (p99 × 2) | Long Timeout (p99 × 10) |
|---|---|---|
| False failure rate | Higher (p99 spikes → timeout) | Lower |
| Latency on success | Low | Low |
| Cascading failure | Lower (fail fast) | Higher (hanging requests) |
| User experience | Faster error feedback | Slower failure feedback |
| Debugging | Easier (errors surface fast) | Harder (hanging requests) |
| Recommended | User-facing APIs | Background jobs, batch |

### 5.4. Client-Side Caching vs Invalidation Complexity

| Aspect | RESP3 Client-Side Caching | No CSC (direct Redis) |
|---|---|---|
| Read latency | Ultra-low (0 network hops) | ~0.1-1ms |
| Memory client-side | Medium (cache storage) | Low |
| Implementation complexity | Medium | Low |
| Invalidation correctness | Hard (invalidation races) | Trivial |
| Cross-node (Cluster) | Phức tạp hơn, phụ thuộc client support và slot routing | Supported |
| Use when | Read-heavy, low write, single-node/per-shard | Any |
| Risk | Stale data if invalidation races | None |

### 5.5. Sync Pool vs Async Client

| Aspect | Sync (blocking pool) | Async (non-blocking) |
|---|---|---|
| Concurrency model | Thread per request | Single thread + event loop |
| Memory per connection | Higher (goroutine/thread stack) | Lower |
| Throughput per core | Lower (GIL/thread switch) | Higher |
| Code complexity | Lower (linear) | Higher (callback/promise) |
| Use when | CPU-bound, low concurrency | I/O-bound, high concurrency |
| Example | Jedis, redis-py blocking | go-redis, ioredis, redis.asyncio |

### 5.6. Connection Per Request vs Connection Pool

| Aspect | Connection Per Request | Connection Pool |
|---|---|---|
| Connection cost | ~1-5ms per request (LAN) | Amortized (0ms for reuse) |
| Memory | High (N connections per N requests) | Low (fixed pool size) |
| Throughput | Low (connection overhead) | High |
| Implementation | Trivial | Moderate |
| Error on connection failure | Per-request | Pool-level |
| Thread safety | N/A (new connection each time) | Must handle |
| Use when | Rarely (benchmark only) | All production workloads |

---

## 6. Best Solution & Best Practices

### Theo Scenario

#### Low-latency Web API (<10ms p99 SLA)

```go
rdb := redis.NewClient(&redis.Options{
    Addr:         "localhost:6379",
    PoolSize:     30,
    MinIdleConns: 10,
    PoolTimeout:  2 * time.Second,
    ReadTimeout:  3 * time.Second,
})

// Context timeout = SLA budget
ctx, cancel := context.WithTimeout(context.Background(), 8*time.Millisecond)
defer cancel()
val, err := rdb.Get(ctx, key).Result()
```

#### Background Job / Batch Processing

```go
rdb := redis.NewClient(&redis.Options{
    Addr:        "localhost:6379",
    PoolSize:    50,
    MinIdleConns: 5,  // less idle needed for batch
    ReadTimeout: 30 * time.Second, // batch reads can be slow
})

// Retry with backoff, up to 3 times
for attempt := 0; attempt < 3; attempt++ {
    if attempt > 0 {
        time.Sleep(backoff(attempt))
    }
    val, err := rdb.Get(ctx, key).Result()
    if err == nil || err == redis.Nil {
        break
    }
    if !isRetryable(err) {
        return err
    }
}
```

#### Critical Payment / Idempotency Service

```go
// No retry for INCR — idempotent design required
// Use SET NX EX for idempotent check-and-set

idempotentKey := "idempotent:" + idempotencyToken
ok, err := rdb.SetNX(ctx, idempotentKey, "processing", 24*time.Hour).Result()
if err != nil {
    return fmt.Errorf("redis error: %w", err)
}
if !ok {
    return ErrDuplicateRequest
}

// Process payment
// Update idempotentKey with result
rdb.Set(ctx, idempotentKey, "success:"+responseID, 24*time.Hour)
```

### Anti-patterns — Không bao giờ làm

1. **Connection per request without pool**: `redis := NewClient(); redis.Get()` per HTTP request = 10K requests/sec × 1ms = 10s CPU time wasted on handshake.
2. **Retry INCR/DECR without idempotency check**: Non-idempotent command → retry = double-count → data corruption.
3. **Retry without exponential backoff**: Retry storm → Redis overload → real outage.
4. **Pool size 200+ without benchmark**: Redis single-threaded → pool size 200 vs 50 = same throughput, 4× memory.
5. **No pool timeout**: `poolTimeout=0` (infinite wait) → request hangs forever → thread exhaustion → cascading failure.
6. **No circuit breaker**: Unbounded retries when Redis is down → retry storm → never recovers.
7. **Connection storm on deploy**: No jitter in startup → 50 instances × 50 connections = 2500 simultaneous connection attempts → maxclients exceeded.
8. **Ignore CLIENT LIST**: Never audit which clients are connected → don't know connection distribution → surprise maxclients issues.

---

## 7. Performance Considerations

### 7.1. Connection Overhead vs Command Cost

```txt
Connection cost breakdown (LAN, no TLS, no AUTH):
  TCP handshake:      ~0.5-1ms
  Redis AUTH:         0ms (no AUTH) or 0.5ms
  Redis SELECT db:    0ms (DB 0) or 0.5ms
  Total cold connect: ~1-2ms

Command cost breakdown (LAN):
  GET:                ~0.1-0.3ms (1-3 RTT if local)
  MGET 100 keys:      ~0.5-1ms
  Pipeline 100 GET:   ~0.5-1ms (1 RTT for all)

Ratio: cold connect / command = 1ms / 0.3ms = 3x command cost
       cold connect / pipeline = 1ms / 0.5ms = 2x pipeline cost
```

**Conclusion**: Connection pool amortizes cold connect cost. Without pool, every request pays cold connect cost → 2-3× slower.

### 7.2. Pool Exhaustion Latency Impact

```txt
Pool size: 10 connections
Concurrency: 100 requests/sec
Command latency: 1ms

Available throughput: 10 connections × 1000 ops/sec = 10,000 ops/sec
Demand: 100 requests/sec × 1ms = 10 concurrent requests on average

Expected: pool exhausted probability ≈ P(>10 concurrent) for Poisson(λ=10)

If pool_timeout = 0 (infinite):
  All 100 concurrent requests wait → 99 requests wait in queue
  Wait time: grows linearly → p99 = 99 × 1ms = 99ms

If pool_timeout = 3s:
  After 3s wait, error returned → fail fast

If pool_size = 50:
  Enough for 100 concurrent requests → no waiting → p99 = 1ms
```

### 7.3. Pipelining + Pool Interaction

```txt
Without pipelining:
  1000 GET requests
  1000 × 0.3ms = 300ms total (sequential)
  With pool size 10: 1000/10 × 0.3ms = 30ms (parallel)

With pipelining (batch 100):
  10 batches × 0.5ms = 5ms total
  With pool size 10: same 5ms (all batches can run in parallel)
```

**Key insight**: Pipelining đã giảm RTT overhead, nhưng pool vẫn cần để:
- Keep connections warm
- Limit concurrent connections to server
- Prevent connection storm on startup

### 7.4. Memory Impact Per Shard

```txt
Per connection memory (server-side, Redis):
  ~17KB (socket buffer, client struct, query buffer, etc.)

Per connection memory (client-side, Go):
  ~8-16KB (socket buffer, runtime state)

Pool size 50, 1 service:
  Server:  50 × 17KB = 850KB
  Client:  50 × 16KB = 800KB

Pool size 50, 10 services (each connecting to same shard):
  Server:  50 × 10 × 17KB = 8.5MB
  → 10 services × 50 = 500 connections to 1 shard
  → 500 × 17KB = 8.5MB just for client tracking

maxclients default: 10000
  → 10000 × 17KB = 170MB server memory for connections alone
  → With dataset 10GB → 170MB / 10GB = 1.7% overhead (acceptable)
  → With dataset 512MB → 170MB / 512MB = 33% overhead (NOT acceptable)
```

**Rule**: Connection memory overhead có thể significant trên small instances. Monitor `INFO clients` regularly.

---

## 8. Production Failure Modes

### 8.1. Connection Pool Exhaustion

**Nguyên nhân**: Pool size quá nhỏ cho concurrency hoặc Redis latency tăng (replication lag, slow command) làm connection occupied lâu hơn expected.

**Dấu hiệu**:
- `PoolTimeout` errors trong application logs
- Latency spike đúng time window (consistent pattern)
- `redis-cli INFO clients` → connected clients count stable but pool exhausted errors

**Fix**:
1. Tăng `poolTimeout` để có thêm buffer
2. Tăng `PoolSize` nếu Redis throughput cho phép
3. Debug Redis latency (slow command, replication lag)
4. Thêm circuit breaker để prevent cascading

### 8.2. Connection Leak

**Nguyên nhân**: Connection không return về pool (code path exit early, error không close connection).

**Dấu hiệu**:
- `redis-cli INFO clients` → connected_clients tăng liên tục theo thời gian
- `redis-cli CLIENT LIST` → nhiều connection có `idle` time = 0 (never released)
- Eventually hitting `maxclients`

**Fix**:
1. Use `defer` / `finally` để always release
2. Use context timeout để auto-cleanup
3. Monitor `connected_clients` trend trong Prometheus

### 8.3. Connection Storm on Deploy

**Nguyên nhân**: Rolling deploy restart nhiều instance cùng lúc, mỗi instance tạo pool đồng thời.

**Dấu hiệu**:
- `redis-cli INFO clients` spike từ 500 → 5000 connections trong 5 giây
- `maxclients` exceeded errors
- Redis CPU spike từ connection management overhead

**Fix**:
1. Staggered startup với random delay
2. Lazy pool grow (MinIdleConns = 0)
3. Connection rate limiting ở load balancer

### 8.4. Retry Storm

**Nguyên nhân**: Aggressive retry strategy không có backoff, khi Redis có transient slowness.

**Dấu hiệu**:
- Error rate tăng → retry attempts → error rate tăng nhanh (exponential)
- Redis CPU normal nhưng client retry traffic × 5 normal load
- Latency spike followed by outage

**Fix**:
1. Exponential backoff with jitter (mandatory)
2. Max retries = 2-3 (not 10)
3. Circuit breaker để stop calling when error rate high
4. Non-idempotent commands: implement idempotency key

### 8.5. Redis AUTH Token Rotation Failure

**Nguyên nhân**: Rotate Redis password → existing connections still use old password → all fail.

**Dấu hiệu**:
- Sudden spike in `NOAUTH` errors across all instances simultaneously
- All services restart/reconnect simultaneously → connection storm

**Fix**:
1. Dual-write: support both old and new password during rotation window
2. Graceful restart: close existing connections before applying new password
3. Use ACL (Redis 6+) per application credentials

---

## 9. Real-world Examples

### Discord — Connection Pool Sizing for 300M Users

Discord dùng Redis cluster cho session và presence. Mỗi gateway connection tạo 1 Redis connection để track presence. Ban đầu dùng pool-per-user → 300M connections = impossible. Họ chuyển sang connection-multiplexing qua Redis Cluster (1 connection per shard per service, shared).

**Key learning**: Connection architecture phụ thuộc vào user model. Per-user-connection works at small scale, fails at millions.

### Shopify — Retry Storm on Redis Upgrade

Shopify gặp retry storm khi upgrade Redis version. Rolling restart triggered failover → Redis temporarily slower → clients retried aggressively → 5× normal traffic → Redis overloaded → real outage. Fix: implement exponential backoff + circuit breaker globally.

### Twitter — Client-side Caching for Timelines

Twitter dùng RESP3 client-side caching để cache timeline reads tại client (không phải Redis-level cache). Khi user tweet → invalidate cached timeline của followers. Với hàng triệu followers → broadcasting mode invalidation. Kết quả: significant reduction in Redis read traffic for timeline reads.

### Uber — Graceful Degradation với Circuit Breaker

Uber's Redis client library có built-in circuit breaker. Khi Redis unavailable → fast fail → serve from fallback (stale cache hoặc local default). Người dùng thấy degraded response (stale data) thay vì error. Recovery: circuit half-open → probe Redis → if healthy → resume normal operation.

---

## 10. Common Pitfalls

1. **Pool size = number of goroutines/processes**: 200 goroutines × 200 pool size = 40,000 potential connections. Redis single-threaded → same throughput as pool 50.

2. **Dùng retry cho non-idempotent commands**: INCR, LPUSH, SADD, GETSET → retry = double execution → data corruption.

3. **Retry without backoff**: Retry immediately on failure → retry storm → cascading failure.

4. **PoolTimeout = 0 (infinite wait)**: Request hangs forever → thread/goroutine exhaustion → all requests back up → system crash.

5. **Không đặt per-command timeout**: Chỉ có pool timeout nhưng command chạy mãi → connection occupied lâu → pool exhaustion.

6. **Connection storm trên rolling deploy**: Không có startup jitter → 50 instance × 50 connections = 2500 simultaneous connections → maxclients exceeded.

7. **Dùng RESP3 CSC trên Cluster mà không kiểm tra client support**: Tracking theo node/slot không rõ → invalidation miss → stale data.

8. **MinIdleConns quá cao**: MinIdleConns: 50 nhưng chỉ có 10 concurrent users → 40 connections wasted, server memory overhead.

9. **Client tự reconnect nhưng không refresh Sentinel/Cluster topology**: Failover xảy ra → client reconnect tới old master → NOAUTH or MOVED errors liên tục.

10. **Sử dụng Jedis trong async context**: Jedis is blocking → không designed cho async. Dùng Lettuce hoặc redis-py async.

---

## 11. Câu hỏi tự kiểm tra

### Câu 1

Hệ thống: 100 microservice instances, mỗi instance có pool 50 connections. Redis server có `maxclients = 10000`. Trong rolling deploy 10% instances mỗi phút, tại peak connection storm, có bao nhiêu connections tới Redis? Có vấn đề gì không?

<details>
<summary>Đáp án</summary>

```txt
Total instances: 100
10% deploy = 10 instances restart simultaneously
Each instance: creates 50 connections

Connection storm: 10 × 50 = 500 connections created simultaneously
Steady state: 90 instances × 50 = 4500 connections

maxclients = 10000 → 5000 < 10000 → OK (no immediate issue)

BUT:
- 500 simultaneous connection attempts = TCP handshake storm
- If 100% deploy simultaneously = 100 × 50 = 5000 connections → near limit
- If each instance also has replica connections (read from replica): × 2 = 10000 → AT LIMIT

Risk: Near maxclients during deploy. With any additional connection (monitoring,
observability tool, other services) → exceeded.
```

</details>

### Câu 2

Bạn có một batch job chạy 1 lần mỗi giờ, đọc 1 triệu keys từ Redis. Nên config pool size bao nhiêu? Retry strategy như thế nào?

<details>
<summary>Đáp án</summary>

**Pool size**: 10-20 là đủ. Batch job là sequential processing (single goroutine), pool size lớn không help.

**Retry strategy**:
- Batch jobs: retry 2-3 lần, exponential backoff
- GET operations are idempotent → safe to retry
- Command timeout: 30-60s (batch reads can be slow)
- Không cần circuit breaker (batch job có thể fail và retry later)

```go
rdb := redis.NewClient(&redis.Options{
    PoolSize:    20,
    MinIdleConns: 2,
    ReadTimeout: 60 * time.Second,  // batch reads can be slow
    PoolTimeout: 30 * time.Second,
})
```

</details>

### Câu 3

Tại sao `INCR counter` NOT safe to retry, nhưng `SET key value` thì safe?

<details>
<summary>Đáp án</summary>

**SET**: Idempotent — `SET key value` executed 3 times = key có value = result cuối cùng (same outcome).

**INCR**: Non-idempotent — `INCR counter` executed 3 times = counter tăng 3 lần thay vì 1.

```txt
Normal flow:
  Client sends: INCR counter
  Redis: counter = 5
  Redis returns: 6
  Client receives: 6

Retry flow (timeout after INCR but before client receives):
  Client sends: INCR counter
  Redis: counter = 6
  Redis sends response
  Response lost (network)
  Client retries: INCR counter
  Redis: counter = 7
  Client receives: 7

Actual: counter = 7
Expected: counter = 6
= Data corruption
```

**Solution for INCR**: Dùng idempotency key pattern:
```go
// Use SETNX to claim idempotency before INCR
ok, err := rdb.SetNX(ctx, "idempotent:"+token, "processing", 24*time.Hour).Result()
if !ok { return ErrDuplicate }
// Safe to INCR now
```

</details>

### Câu 4

Bạn phát hiện `connected_clients` trên Redis tăng liên tục mà không giảm. Từ 1000 → 2000 → 3000 trong 2 giờ. Nguyên nhân có thể là gì? Bước đầu tiên để debug?

<details>
<summary>Đáp án</summary>

**Nguyên nhân có thể**:
1. **Connection leak**: Application không return connection về pool (code path exit early, error không close)
2. **Lỗi AUTH**: All connections fail AUTH → new connections created → old ones never reused
3. **Client reconnect logic bug**: On error, client tạo new connection thay vì reuse existing
4. **minIdleConns tăng dần**: Nếu pool được recreate liên tục

**Bước đầu tiên**:
```bash
# Check which clients are connecting
redis-cli CLIENT LIST | head -20

# Look for patterns:
# - Same connection name? (service name leak)
# - Same IP? (single instance leaking)
# - Idle time = 0? (never released)

# Count connections by name
redis-cli CLIENT LIST | cut -d' ' -f6 | sort | uniq -c | sort -rn | head -10

# Check maxclients
redis-cli CONFIG GET maxclients
```

</details>

### Câu 5

Pool size 100 cho Redis single-threaded vs pool size 10. Throughput khác nhau bao nhiêu? Tại sao?

<details>
<summary>Đáp án</summary>

```txt
Redis single-threaded processes 50,000 ops/sec (1ms per command)

Pool size 10:
  10 connections available
  All 10 process commands in parallel (but Redis serializes)
  Effective throughput: 50,000 ops/sec (Redis bottleneck)
  Wait time: 10 goroutines compete for 1 Redis thread
  Context switches: minimal

Pool size 100:
  100 connections available
  100 goroutines compete for 1 Redis thread
  Effective throughput: ~50,000 ops/sec (same Redis bottleneck)
  Wait time: 100 goroutines compete → more context switches
  Memory: 100 × 17KB = 1.7MB server-side (vs 0.17MB for pool 10)
  Client-side: 100 × 16KB = 1.6MB (vs 0.16MB for pool 10)

Conclusion: Throughput same, memory 10× higher, complexity higher.
```

</details>

### Câu 6

Khi nào nên dùng RESP3 client-side caching thay vì regular Redis reads?

<details>
<summary>Đáp án</summary>

**Dùng RESP3 CSC khi**:
- Read-heavy workload (>90% reads, <10% writes)
- Same data accessed by many clients (e.g., config, product catalog, leaderboard)
- Data changes infrequently (minutes/hours between changes)
- Single-node Redis hoặc Cluster với client library support tracking theo node/slot rõ ràng
- Want lowest possible read latency (0 network hops after cache warm)

**Không dùng khi**:
- High write rate (invalidation overhead > benefit)
- Cross-node data nhưng client không quản lý invalidation theo node/slot
- Need real-time consistency
- Complex invalidation dependencies
- Already have Redis-side cache (double caching redundant)

**Example use case**: Product catalog read (90% reads, product info changes daily) → RESP3 CSC reduces Redis read load by 80%.

</details>

### Câu 7

Bạn có 50 microservices × 20 instances × pool size 50 = 50,000 potential connections. Redis maxclients = 10000. Design connection strategy để không exceed maxclients.

<details>
<summary>Đáp án</summary>

```txt
Step 1: Calculate actual concurrent connections needed
  Average load: not all instances at peak simultaneously
  Actual concurrent = 50,000 × 0.1 (peak factor) = 5,000 connections
  maxclients = 10,000 → headroom = 5,000 → OK but tight

Step 2: Reduce pool size per instance
  pool_size = N × 1ms / 1000 = N/1000
  For N=10 concurrent requests (per instance): pool_size = 10-20
  50 instances × 20 = 1,000 connections → comfortable headroom

Step 3: Connection sharing (shared pool across instances)
  TypeScript/Node.js: single Redis connection (event loop model)
  Go: 1 client with pool size 30 (shared across all goroutines in 1 instance)
  Result: 50 instances × 30 = 1,500 connections

Step 4: Redis Cluster (per-shard)
  3 shards × 500 connections = 1,500 connections total
  Each shard handles ~3,333 ops/sec

Step 5: Implement connection rate limiting
  maxclients margin = 10,000 - 1,500 = 8,500 headroom
  Alert when > 8,000 (80% threshold)
```

</details>
