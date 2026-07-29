# Day 12: Connection Pooling & Client Behavior — Reference Document

---

## 1. Cheat Sheet: Client Commands

```txt
-- List all connected clients
CLIENT LIST

-- List with specific fields
CLIENT LIST TYPE=normal

-- Kill specific client (by id, addr, type, laddr, etc.)
CLIENT KILL ID 5
CLIENT KILL ADDR 192.168.1.100:6379
CLIENT KILL TYPE normal     -- kill all normal clients
CLIENT KILL LADDR 127.0.0.1:6379

-- Set client name (for identification in CLIENT LIST)
CLIENT SETNAME my-service-pool-3
CLIENT GETNAME

-- Prevent client from being evicted during maxmemory eviction
CLIENT NO-EVICT ON
CLIENT NO-EVICT OFF

-- Pause all Redis commands (for maintenance)
CLIENT PAUSE 5000 WRITES    -- pause 5 seconds, writes only
CLIENT PAUSE 0 WRITES       -- unpause

-- Get client connection info
CLIENT INFO

-- Key fields in CLIENT LIST output:
--   id: unique connection ID
--   addr: client IP:port
--   laddr: local Redis IP:port
--   fd: file descriptor number
--   name: client name (set via CLIENT SETNAME)
--   db: database ID
--   cmd: last command
--   lib-name / lib-ver: client library name/version
--   flags: N=normal, O=monitor, M=master, P=pubsub, X=close-after-reply
--   idle: seconds idle (0 = active)
--   idle: 0 means active, >0 means idle in seconds
```

### Key Metrics from INFO clients

```txt
INFO clients
```

| Field | Description |
|---|---|
| `connected_clients` | Current number of connected clients (excluding replicas) |
| `client_recent_max_input_buffer` | Largest input buffer seen recently |
| `client_recent_max_output_buffer` | Largest output buffer seen recently |
| `blocked_clients` | Clients waiting for blocking command (BLPOP, etc.) |
| `tracking_clients` | Clients using RESP3 client-side tracking |
| `total_connections_received` | Total connections accepted since server start |
| `rejected_connections` | Connections rejected due to maxclients |

```txt
-- Server-side connection limits
CONFIG GET maxclients
CONFIG GET timeout          -- client timeout (seconds idle before close)
CONFIG GET tcp-keepalive    -- TCP keepalive (seconds)
```

---

## 2. Per-Language Configuration Reference

### Go — go-redis/v9

```go
import "github.com/redis/go-redis/v9"

rdb := redis.NewClient(&redis.Options{
    Addr:            "redis-host:6379",
    Password:        "secret",         // "" = no password
    DB:              0,
    PoolSize:        50,                // connections per node (not per goroutine)
    MinIdleConns:    10,                // keep N connections warm always
    MaxIdleConns:    50,                // max idle connections (≤ PoolSize)
    PoolTimeout:     4 * time.Second,   // wait when pool exhausted
    ReadTimeout:     3 * time.Second,   // read deadline per command
    WriteTimeout:    3 * time.Second,   // write deadline per command
    DialTimeout:     5 * time.Second,   // TCP/TLS/AUTH handshake timeout
    TLSConfig:       &tls.Config{...},   // nil = no TLS
})

// For Redis Cluster
clusterClient := redis.NewClusterClient(&redis.ClusterOptions{
    Addrs:         []string{"redis-1:6379", "redis-2:6379", "redis-3:6379"},
    Password:      "secret",
    PoolSize:      50,   // per-node, not total
    MinIdleConns:  5,
})
```

### TypeScript — ioredis

```typescript
import Redis from 'ioredis';

const redis = new Redis({
  host: 'redis-host',
  port: 6379,
  password: 'secret',
  db: 0,

  // Connection
  connectionName: 'my-service',
  lazyConnect: true,
  enableAutoPipelining: true,
  maxRetriesPerRequest: 3,

  // Retry
  retryStrategy(times: number) {
    if (times > 10) return null; // stop retrying
    return Math.min(times * 100, 3000); // ms
  },
  reconnectOnError(err: Error) {
    return (err.message as string).includes('READONLY');
  },

  // Timeouts
  connectTimeout: 10000,
  commandTimeout: 3000,

  // TLS
  tls: { /* TLSConfig */ },
});

// Cluster
import Redis from 'ioredis/cluster';
const cluster = new Redis.Cluster(['redis-1:6379', 'redis-2:6379'], {
  redisOptions: {
    password: 'secret',
    enableAutoPipelining: true,
    maxRetriesPerRequest: 3,
  },
  retryDelayOnFailover: 100,
  retryDelayOnClusterDown: 100,
  maxRedirections: 3,
});
```

### Java — Lettuce (Netty-based, thread-safe)

```java
import io.lettuce.core.*;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.sync.RedisCommands;

// Simple setup
RedisClient client = RedisClient.create("redis://secret@redis-host:6379/0");
StatefulRedisConnection<String, String> conn = client.connect();

// Connection is thread-safe — share across threads, no pool needed

// With pool (only if needed)
import io.lettuce.core.resource.ClientResources;
import io.lettuce.core.codec.StringCodec;
import io.lettuce.core.codec.Utf8StringCodec;

ClientResources res = ClientResources.builder()
    .ioThreadPoolSize(4)
    .computationThreadPoolSize(4)
    .build();

RedisClient client = RedisClient.create(res, RedisURI.create("redis-host", 6379));

// For Cluster
import io.lettuce.core.cluster.RedisClusterClient;
import io.lettuce.core.cluster.ClusterClientOptions;

RedisClusterClient clusterClient = RedisClusterClient.create(
    res,
    Arrays.asList(
        RedisURI.create("redis-1:6379"),
        RedisURI.create("redis-2:6379")
    )
);
```

### Java — Jedis (legacy, pool required, NOT thread-safe)

```java
import redis.clients.jedis.*;
import redis.clients.jedis.params.SetParams;

JedisPoolConfig poolConfig = new JedisPoolConfig();
poolConfig.setMaxTotal(50);
poolConfig.setMaxIdle(10);
poolConfig.setMinIdle(5);
poolConfig.setMaxWait(java.time.Duration.ofMillis(3000));
poolConfig.setTestOnBorrow(true);
poolConfig.setBlockWhenExhausted(true);

JedisPooled jedis = new JedisPooled(poolConfig, "redis-host", 6379, "secret");

// Or manual pool management
JedisPool pool = new JedisPool(poolConfig, "redis-host", 6379, 3000, "secret");
try (Jedis j = pool.getResource()) {
    j.set("key", "value", new SetParams().ex(3600));
}
```

### Python — redis-py

```python
import redis

# Sync: ConnectionPool
pool = redis.ConnectionPool(
    host='redis-host',
    port=6379,
    password='secret',
    db=0,
    max_connections=50,
    socket_timeout=3.0,
    socket_connect_timeout=5.0,
    decode_responses=True,
)
client = redis.Redis(connection_pool=pool)

# BlockingConnectionPool (sync, blocks when exhausted)
blocking_pool = redis.BlockingConnectionPool(
    host='redis-host',
    port=6379,
    password='secret',
    max_connections=50,
    timeout=10,  # seconds to wait
)
client = redis.Redis(connection_pool=blocking_pool)

# Async: redis.asyncio
import redis.asyncio as aioredis

async_pool = aioredis.ConnectionPool(
    host='redis-host',
    port=6379,
    password='secret',
    max_connections=50,
    decode_responses=True,
)
client = aioredis.Redis(connection_pool=async_pool)

# Cluster
import redis.asyncio as aioredis
cluster_pool = aioredis.RedisCluster(
    host='redis-host',
    port=6379,
    password='secret',
    max_connections_per_node=50,
)
```

---

## 3. Recommended Timeout/Retry Profiles

### Profile A: Latency-Sensitive Web API (p99 < 100ms SLA)

```go
// Timeout budget: 100ms SLA
rdb := redis.NewClient(&redis.Options{
    PoolSize:    30,
    MinIdleConns: 10,
    PoolTimeout:  50 * time.Millisecond,
    ReadTimeout: 80 * time.Millisecond,
    WriteTimeout: 80 * time.Millisecond,
    DialTimeout:  500 * time.Millisecond,
})

// Per-command timeout: 80ms (leave 20ms for processing)
ctx, cancel := context.WithTimeout(ctx, 80*time.Millisecond)
val, err := rdb.Get(ctx, key).Result()

// Retry: 1 attempt only (fail fast)
if errors.Is(err, context.DeadlineExceeded) {
    return ErrRedisTimeout
}
```

| Timeout | Value | Reason |
|---|---|---|
| DialTimeout | 500ms | Connection setup |
| PoolTimeout | 50ms | Wait for idle connection |
| ReadTimeout | 80ms | Per-command (p99 SLA budget) |
| MaxRetries | 0-1 | Fail fast |

### Profile B: Batch Job / Background Worker

```go
rdb := redis.NewClient(&redis.Options{
    PoolSize:    20,
    MinIdleConns: 2,
    PoolTimeout: 30 * time.Second,
    ReadTimeout: 60 * time.Second,
    WriteTimeout: 30 * time.Second,
    DialTimeout:  10 * time.Second,
})

// Retry: 2-3 times with exponential backoff
func withRetry(ctx context.Context, rdb *redis.Client, key string) (string, error) {
    var lastErr error
    for attempt := 0; attempt < 3; attempt++ {
        if attempt > 0 {
            select {
            case <-ctx.Done():
                return "", ctx.Err()
            case <-time.After(backoff(attempt)):
            }
        }
        val, err := rdb.Get(ctx, key).Result()
        if err == nil || err == redis.Nil {
            return val, nil
        }
        if !isRetryable(err) {
            return "", err
        }
        lastErr = err
    }
    return "", fmt.Errorf("max retries exceeded: %w", lastErr)
}
```

| Timeout | Value | Reason |
|---|---|---|
| DialTimeout | 10s | Batch job, startup not critical |
| PoolTimeout | 30s | May have many concurrent batch jobs |
| ReadTimeout | 60s | Batch reads on large keys |
| MaxRetries | 3 | Safe for idempotent GET |
| Backoff | 100ms-10s | Exponential with jitter |

### Profile C: Critical Payment / Idempotency

```go
rdb := redis.NewClient(&redis.Options{
    PoolSize:    10,       // Low concurrency expected for payments
    MinIdleConns: 3,
    PoolTimeout: 5 * time.Second,
    ReadTimeout: 2 * time.Second,
    WriteTimeout: 2 * time.Second,
    DialTimeout:  5 * time.Second,
})

// NO RETRY for non-idempotent operations
// Use SETNX for idempotency BEFORE INCR
func idempotentIncrement(ctx context.Context, token string) (int64, error) {
    key := "idempotent:" + token
    ok, err := rdb.SetNX(ctx, key, "processing", 24*time.Hour).Result()
    if err != nil {
        return 0, fmt.Errorf("redis error: %w", err)
    }
    if !ok {
        return 0, ErrDuplicateRequest
    }

    // Safe to increment now (idempotent protected)
    result, err := rdb.Incr(ctx, "counter").Result()
    if err != nil {
        rdb.Del(ctx, key) // cleanup on failure
        return 0, err
    }

    rdb.Set(ctx, key, fmt.Sprintf("done:%d", result), 24*time.Hour)
    return result, nil
}
```

| Timeout | Value | Reason |
|---|---|---|
| DialTimeout | 5s | Normal startup |
| PoolTimeout | 5s | Low concurrency, fail fast |
| ReadTimeout | 2s | Payment operations must be fast |
| WriteTimeout | 2s | Payment writes |
| MaxRetries | 0 | NO RETRY for non-idempotent |
| Circuit Breaker | Yes | Prevent cascade failure |

---

## 4. Circuit Breaker — Simple Implementation

```go
package main

import (
    "context"
    "errors"
    "fmt"
    "math/rand"
    "sync"
    "time"
)

// CircuitState represents the circuit breaker state.
type CircuitState int

const (
    StateClosed CircuitState = iota
    StateOpen
    StateHalfOpen
)

func (s CircuitState) String() string {
    switch s {
    case StateClosed:
        return "closed"
    case StateOpen:
        return "open"
    case StateHalfOpen:
        return "half-open"
    }
    return "unknown"
}

// CircuitBreaker is a simple state machine circuit breaker.
type CircuitBreaker struct {
    mu sync.RWMutex

    name             string
    failureThreshold int           // failures in window to trip
    successThreshold int           // successes in half-open to close
    window           time.Duration // time window for counting
    timeout          time.Duration // time in open before half-open

    state            CircuitState
    failureCount     int
    successCount     int
    lastFailureTime  time.Time
    lastStateChange  time.Time
}

func NewCircuitBreaker(name string, threshold int, window, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        name:             name,
        failureThreshold: threshold,
        successThreshold: 3,
        window:           window,
        timeout:          timeout,
        state:            StateClosed,
    }
}

func (cb *CircuitBreaker) State() CircuitState {
    cb.mu.RLock()
    defer cb.mu.RUnlock()
    return cb.state
}

func (cb *CircuitBreaker) recordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    switch cb.state {
    case StateClosed:
        cb.failureCount = 0
    case StateHalfOpen:
        cb.successCount++
        if cb.successCount >= cb.successThreshold {
            cb.transitionTo(StateClosed)
        }
    }
}

func (cb *CircuitBreaker) recordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    cb.lastFailureTime = time.Now()

    switch cb.state {
    case StateClosed:
        cb.failureCount++
        if cb.failureCount >= cb.failureThreshold {
            cb.transitionTo(StateOpen)
        }
    case StateHalfOpen:
        cb.transitionTo(StateOpen)
    }
}

func (cb *CircuitBreaker) transitionTo(state CircuitState) {
    old := cb.state
    cb.state = state
    cb.lastStateChange = time.Now()
    if state == StateClosed {
        cb.failureCount = 0
        cb.successCount = 0
    }
    if state == StateHalfOpen {
        cb.successCount = 0
    }
    fmt.Printf("[circuit-breaker] %s: %s -> %s\n", cb.name, old, state)
}

var (
    ErrCircuitOpen = errors.New("circuit breaker is open")
    ErrTooManyAttempts = errors.New("too many attempts")
)

// Execute runs fn if the circuit is closed or half-open.
// Returns ErrCircuitOpen if the circuit is open.
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
    cb.mu.RLock()
    state := cb.state
    lastFailure := cb.lastFailureTime
    cb.mu.RUnlock()

    // Check if we should transition from Open to Half-Open
    if state == StateOpen {
        cb.mu.Lock()
        // Double-check after acquiring write lock
        if cb.state == StateOpen && time.Since(lastFailure) > cb.timeout {
            cb.transitionTo(StateHalfOpen)
            state = StateHalfOpen
        }
        cb.mu.Unlock()
    }

    if state == StateOpen {
        return ErrCircuitOpen
    }

    err := fn()

    if err != nil {
        cb.recordFailure()
    } else {
        cb.recordSuccess()
    }

    return err
}

// Helper: exponential backoff with jitter
func Backoff(attempt int) time.Duration {
    base := 100 * time.Millisecond
    max := 30 * time.Second
    delay := base * time.Duration(1<<uint(attempt))
    if delay > max {
        delay = max
    }
    // Add jitter: 0-50% of delay
    jitter := time.Duration(rand.Int63n(int64(delay) / 2))
    return delay + jitter
}

// Helper: check if error is retryable
func IsRetryable(err error) bool {
    if err == nil {
        return false
    }
    // Connection errors, timeouts
    if errors.Is(err, context.DeadlineExceeded) ||
        errors.Is(err, context.Canceled) {
        return true
    }
    // Redis connection errors (check error message)
    msg := err.Error()
    retryablePrefixes := []string{
        "connection refused",
        "connection reset",
        "connection timeout",
        "broken pipe",
        "ECONNRESET",
        "ETIMEDOUT",
    }
    for _, prefix := range retryablePrefixes {
        if len(msg) >= len(prefix) && msg[:len(prefix)] == prefix {
            return true
        }
    }
    return false
}
```

**Usage with go-redis**:

```go
cb := NewCircuitBreaker("redis", 5, 10*time.Second, 30*time.Second)

func GetWithProtection(ctx context.Context, rdb *redis.Client, key string) (string, error) {
    var result string
    err := cb.Execute(ctx, func() error {
        var execErr error
        result, execErr = rdb.Get(ctx, key).Result()
        return execErr
    })
    return result, err
}
```

---

## 5. Connection Pool Monitoring Checklist

```bash
# 1. Current connections (alert if > 80% maxclients)
redis-cli INFO clients | grep connected_clients

# 2. Rejected connections (maxclients exceeded)
redis-cli INFO clients | grep rejected_connections

# 3. List top clients by connection count
redis-cli CLIENT LIST | awk '{print $2}' | cut -d= -f2 | sort | uniq -c | sort -rn | head -10

# 4. Idle connections (potential leaks)
redis-cli CLIENT LIST | grep 'idle=[0-9]' | sort -t= -k2 -n -r | head -10

# 5. Connection by client library
redis-cli CLIENT LIST | grep 'lib-ver' | awk '{print $NF}' | sort | uniq -c

# 6. Alert thresholds (Prometheus rules)
#   - connected_clients > 8000 (80% of 10000)
#   - rejected_connections > 0 (any rejection is incident)
#   - blocked_clients > 0 (unexpected blocking)
```

---

## 6. Docker Compose — Connection Test Setup

```yaml
# docker-compose.connection-lab.yml
version: "3.9"

services:
  redis:
    image: redis:7.2
    container_name: redis-conn-test
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --maxclients 10000
      --timeout 300
      --tcp-keepalive 60
      --loglevel notice
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-replica:
    image: redis:7.2
    container_name: redis-conn-replica
    ports:
      - "6380:6379"
    command: redis-server --replicaof redis 6379 --maxmemory 256mb
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

---

## 7. Links & References

### Official Documentation
- https://redis.io/docs/management/optimize/redis-throughput/ — Redis throughput optimization
- https://redis.io/docs/management/security/clients/ — Client management
- https://redis.io/docs/reference/clients/ — Client protocol
- https://redis.io/docs/reference/protocol-spec/ — RESP3 spec

### Client Libraries
- https://github.com/redis/go-redis — go-redis v9 documentation
- https://github.com/redis/ioredis — ioredis (Node.js)
- https://lettuce.io/ — Lettuce (Java, Netty-based)
- https://github.com/redis/jedis — Jedis (Java, legacy)
- https://github.com/redis/redis-py — redis-py (Python)

### Circuit Breaker
- https://github.com/sony/gobreaker — Sony's Go circuit breaker (recommended)
- https://github.com/afex/hystrix-go — Hystrix port for Go
- https://github.com/rubyist/circuitbreaker — Ruby circuit breaker pattern

### RESP3 Client-Side Caching
- https://redis.io/docs/manual/client-side-caching/ — Official CSC docs
- https://github.com/redis/redis-py/discussions/2376 — Python CSC discussion

### Real-world Incident Reports
- Shopify retry storm: engineering.shopify.com/blogs/engineering/
- Discord connection architecture: discord.com/blog/

### Redis Client Design
- https://github.com/redis/redis-py/blob/master/redis/connection.py — Connection pool implementation reference
- https://github.com/redis/go-redis/blob/master/internal/pool.go — go-redis pool internals

### Key Metrics for Monitoring (Prometheus)
```yaml
# Prometheus alerting rules for connections
- alert: RedisHighConnectionCount
  expr: redis_connected_clients{instance="redis:6379"} > 8000
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "Redis high connection count ({{ $value }} / 10000)"

- alert: RedisConnectionRejected
  expr: redis_rejected_connections_total{instance="redis:6379"} > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Redis is rejecting connections (maxclients exceeded)"
```
