# Day 12: Connection Pooling & Client Behavior — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: Go (go-redis/v9)
**Docker images**: redis:7-alpine

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Inspect Connected Clients

```bash
redis-cli CLIENT LIST
```

Đọc và phân tích các field quan trọng trong output:

- `id`, `addr`, `laddr`, `fd`
- `name` (client name — hữu ích để identify service)
- `cmd` (last command)
- `flags` (N=normal, P=pubsub, M=master, O=monitor)
- `idle` (seconds idle: 0 = active, >0 = idle)
- `lib-name`/`lib-ver` (client library)

**Expected output** (định dạng):

```txt
id=5 addr=192.168.1.10:52341 laddr=192.168.1.100:6379 fd=8 name= my-db=0 cmd=GET flags=N ...
```

### 1.2. Set Client Name và Verify

```bash
redis-cli CLIENT SETNAME warmup-exercise
redis-cli CLIENT GETNAME
```

**Expected output**:

```txt
warmup-exercise
```

### 1.3. Check Server Connection Limits

```bash
redis-cli CONFIG GET maxclients
redis-cli CONFIG GET timeout
redis-cli CONFIG GET tcp-keepalive
```

**Expected output** (default Redis 7):

```txt
1) "maxclients"
2) "10000"

1) "timeout"
2) "0"

1) "tcp-keepalive"
2) "300"
```

- `maxclients = 10000` — tổng connections tối đa (server-side limit)
- `timeout = 0` — không tự động disconnect idle clients
- `tcp-keepalive = 300` — ping client mỗi 300s để keep connection alive

### 1.4. Monitor Connection Count Real-time

```bash
redis-cli INFO clients
```

Trích xuất:

- `connected_clients` — số clients hiện tại
- `rejected_connections` — connections bị reject do exceed maxclients
- `total_connections_received` — tổng connections kể từ start

### 1.5. Simulate Connection Load

Tạo nhiều connections bằng `redis-cli --intrinsic-latency`:

```bash
# Mở 3 terminal, mỗi terminal chạy:
redis-cli
```

Trong terminal 1:

```bash
redis-cli CLIENT LIST | wc -l
```

Mở thêm 2 `redis-cli` connections (mỗi terminal chạy `redis-cli`), sau đó:

```bash
redis-cli INFO clients | grep connected_clients
```

**Expected**: `connected_clients` tăng tương ứng. Sau đó `QUIT` từng terminal và kiểm tra lại.

### 1.6. Test CLIENT PAUSE

```bash
# Terminal 1: Bắt đầu blocking command
redis-cli BLPOP myqueue 0

# Terminal 2: Pause writes trong 5 giây
redis-cli CLIENT PAUSE 5000 WRITES

# Terminal 3: Thử SET (sẽ bị block bởi CLIENT PAUSE)
redis-cli SET testkey testvalue

# Sau 5 giây: Terminal 3 SET thực hiện được.
# Terminal 1 vẫn chờ BLPOP cho đến khi có LPUSH vào myqueue.
```

> **Lưu ý**: `CLIENT PAUSE ... WRITES` chỉ pause write commands; `CLIENT PAUSE ... ALL` mới pause cả read/write. Dùng rất cẩn thận trong maintenance window ngắn.

---

## 2. Hands-on Lab (60-70 phút)

### Setup: Docker Compose

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    container_name: redis-conn-lab
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

volumes:
  redis-data:
```

**File**: `go.mod`

```go
module redis-conn-lab

go 1.21

require github.com/redis/go-redis/v9 v9.5.1
```

### Go Starter Code

**File**: `cmd/lab/main.go`

```go
package main

import (
    "context"
    "errors"
    "fmt"
    "log"
    "math/rand"
    "sync"
    "time"

    "github.com/redis/go-redis/v9"
)

func main() {
    ctx := context.Background()

    rdb := redis.NewClient(&redis.Options{
        Addr:        "localhost:6379",
        DB:          0,
        PoolSize:    50,
        MinIdleConns: 5,
        PoolTimeout: 4 * time.Second,
        ReadTimeout: 3 * time.Second,
        WriteTimeout: 3 * time.Second,
        DialTimeout: 5 * time.Second,
    })
    defer rdb.Close()

    // Verify connectivity
    if err := rdb.Ping(ctx).Err(); err != nil {
        log.Fatalf("Cannot connect to Redis: %v", err)
    }
    fmt.Println("Connected to Redis OK")
}
```

---

### Step 1: Implement Resilient Client Wrapper (Timeout + Retry + Backoff)

Thêm các function sau vào `main.go`:

```go
// Backoff returns exponential backoff with full jitter.
func backoff(attempt int) time.Duration {
    base := 100 * time.Millisecond
    max := 30 * time.Second
    delay := base * time.Duration(1<<uint(attempt))
    if delay > max {
        delay = max
    }
    // Full jitter: 0 to delay
    jitter := time.Duration(int64(delay) / 2)
    if jitter > 0 {
        delay = delay/2 + time.Duration(int64(time.Now().UnixNano())%int64(jitter))
    }
    return delay
}

// isRetryable checks if error should trigger a retry.
func isRetryable(err error) bool {
    if err == nil {
        return false
    }
    // Connection/timeout errors
    msg := err.Error()
    prefixes := []string{
        "connection refused",
        "connection reset",
        "connection timeout",
        "broken pipe",
        "EOF",
        "i/o timeout",
    }
    for _, p := range prefixes {
        if len(msg) >= len(p) && msg[:len(p)] == p {
            return true
        }
    }
    return false
}

// GetWithRetry executes GET with exponential backoff retry.
func GetWithRetry(ctx context.Context, rdb *redis.Client, key string, maxRetries int) (string, error) {
    var lastErr error
    for attempt := 0; attempt <= maxRetries; attempt++ {
        if attempt > 0 {
            select {
            case <-ctx.Done():
                return "", ctx.Err()
            case <-time.After(backoff(attempt)):
            }
        }
        val, err := rdb.Get(ctx, key).Result()
        if err == nil {
            return val, nil
        }
        if err == redis.Nil {
            return "", err
        }
        if !isRetryable(err) {
            return "", err
        }
        lastErr = err
        fmt.Printf("[retry] attempt %d: %v\n", attempt, err)
    }
    return "", fmt.Errorf("max retries (%d) exceeded: %w", maxRetries, lastErr)
}
```

Trong `main()`, thêm:

```go
// Step 1: Write test keys
ctx := context.Background()
for i := 0; i < 100; i++ {
    key := fmt.Sprintf("lab:key:%03d", i)
    if err := rdb.Set(ctx, key, fmt.Sprintf("value-%03d", i), 0).Err(); err != nil {
        log.Fatalf("SET failed: %v", err)
    }
}
fmt.Println("Step 1: 100 keys written")

// Test GetWithRetry (normal case — should succeed on first attempt)
val, err := GetWithRetry(ctx, rdb, "lab:key:000", 3)
if err != nil {
    log.Fatalf("GetWithRetry failed: %v", err)
}
fmt.Printf("Step 1: GetWithRetry returned '%s'\n", val)
```

**Expected output**:

```txt
Connected to Redis OK
Step 1: 100 keys written
Step 1: GetWithRetry returned 'value-000'
```

---

### Step 2: Implement Circuit Breaker

Thêm struct và methods:

```go
// CircuitState represents the circuit breaker state machine.
type CircuitState int

const (
    StateClosed CircuitState = iota
    StateOpen
    StateHalfOpen
)

var ErrCircuitOpen = errors.New("circuit breaker OPEN")

func (s CircuitState) String() string {
    switch s {
    case StateClosed:
        return "CLOSED"
    case StateOpen:
        return "OPEN"
    case StateHalfOpen:
        return "HALF-OPEN"
    }
    return "UNKNOWN"
}

// CircuitBreaker implements a simple 3-state circuit breaker.
type CircuitBreaker struct {
    mu sync.RWMutex

    name             string
    failureThreshold int
    successThreshold int
    timeout          time.Duration

    state           CircuitState
    failureCount    int
    successCount    int
    lastFailureTime time.Time
}

func NewCircuitBreaker(name string, failureThreshold int, successThreshold int, timeout time.Duration) *CircuitBreaker {
    return &CircuitBreaker{
        name:             name,
        failureThreshold: failureThreshold,
        successThreshold: successThreshold,
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
            cb.transitionToLocked(StateClosed)
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
            cb.transitionToLocked(StateOpen)
        }
    case StateHalfOpen:
        cb.transitionToLocked(StateOpen)
    }
}

func (cb *CircuitBreaker) transitionToLocked(state CircuitState) {
    cb.state = state
    if state == StateClosed {
        cb.failureCount = 0
        cb.successCount = 0
    }
    if state == StateHalfOpen {
        cb.successCount = 0
    }
    fmt.Printf("[circuit-breaker] %s: %s\n", cb.name, state)
}

// Execute runs fn if the circuit allows it.
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
    cb.mu.RLock()
    state := cb.state
    lastFailure := cb.lastFailureTime
    cb.mu.RUnlock()

    // Transition Open -> Half-Open after timeout
    if state == StateOpen {
        cb.mu.Lock()
        if cb.state == StateOpen && time.Since(lastFailure) > cb.timeout {
            cb.transitionToLocked(StateHalfOpen)
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
```

---

### Step 3: Integrate Circuit Breaker vào Redis Calls

Thêm function:

```go
// RedisWithCircuitBreaker wraps a Redis GET call with circuit breaker protection.
func RedisGetWithCB(ctx context.Context, cb *CircuitBreaker, rdb *redis.Client, key string) (string, error) {
    var result string
    err := cb.Execute(ctx, func() error {
        val, err := rdb.Get(ctx, key).Result()
        if err == redis.Nil {
            return nil // cache miss không phải infrastructure failure
        }
        if err != nil {
            return err
        }
        result = val
        return nil
    })
    return result, err
}
```

Trong `main()`, thêm test:

```go
// Step 3: Test circuit breaker
fmt.Println("\n=== Step 3: Circuit Breaker Test ===")
cb := NewCircuitBreaker("redis-get", 3, 2, 10*time.Second)

// Normal call — circuit stays CLOSED
val, err = RedisGetWithCB(ctx, cb, rdb, "lab:key:001")
fmt.Printf("Circuit state: %s, val: %s, err: %v\n", cb.State(), val, err)

// Simulate failures bằng client trỏ vào port không có Redis
badRedis := redis.NewClient(&redis.Options{
    Addr:        "localhost:6390",
    DialTimeout: 200 * time.Millisecond,
    ReadTimeout: 200 * time.Millisecond,
})
defer badRedis.Close()

for i := 0; i < 3; i++ {
    _, err := RedisGetWithCB(ctx, cb, badRedis, "lab:key:001")
    if err != nil {
        fmt.Printf("  Failure %d: %v\n", i+1, err)
    }
}
fmt.Printf("Circuit state after failures: %s\n", cb.State())
```

**Expected output** (before killing Redis):

```txt
=== Step 3: Circuit Breaker Test ===
Circuit state: CLOSED, val: value-001, err: <nil>
  Failure 1: connection refused ...
  Failure 2: connection refused ...
  Failure 3: connection refused ...
Circuit state after failures: OPEN
```

---

### Step 4: Simulate Redis Unavailable — Observe Circuit Breaker Behavior

**Bước 4a**: Kill Redis container (terminal khác):

```bash
docker kill redis-conn-lab
echo "Redis killed"
```

**Bước 4b**: Chạy test circuit breaker (trong terminal đang chạy Go):

Thêm vào `main.go`:

```go
// Step 4: Observe circuit breaker with Redis down
fmt.Println("\n=== Step 4: Circuit Breaker — Redis Unavailable ===")
cb4 := NewCircuitBreaker("redis-get", 3, 2, 5*time.Second)

start := time.Now()
successCount := 0
failFastCount := 0
redisErrorCount := 0

for i := 0; i < 20; i++ {
    _, err := RedisGetWithCB(ctx, cb4, rdb, "lab:key:005")
    if err != nil {
        if errors.Is(err, ErrCircuitOpen) {
            failFastCount++
        } else {
            redisErrorCount++
        }
    } else {
        successCount++
    }
    time.Sleep(100 * time.Millisecond)
}

elapsed := time.Since(start)
fmt.Printf("20 calls in %v\n", elapsed)
fmt.Printf("  Success: %d, Redis errors before OPEN: %d, Fail-fast (circuit OPEN): %d\n", successCount, redisErrorCount, failFastCount)
fmt.Printf("  Circuit state: %s\n", cb4.State())
fmt.Printf("  Without CB: 20 × ~5s = 100s total blocking\n")
fmt.Printf("  With CB (OPEN after 3 failures): fail-fast = near-instant\n")
```

**Expected output** (Redis down):

```txt
=== Step 4: Circuit Breaker — Redis Unavailable ===
[circuit-breaker] redis-get: CLOSED -> OPEN
circuit-breaker] redis-get: HALF-OPEN
[circuit-breaker] redis-get: HALF-OPEN -> OPEN
...
20 calls in ~1-2s
  Success: 0, Redis errors before OPEN: 3, Fail-fast (circuit OPEN): 17
  Circuit state: OPEN
  Without CB: 20 × ~5s = 100s total blocking
  With CB (OPEN after 3 failures): fail-fast = near-instant
```

**Bước 4c**: Restart Redis:

```bash
docker compose -f docker-compose.yml up -d
sleep 3
docker exec redis-conn-lab redis-cli PING
```

---

### Step 5: Benchmark Pool Size — 5 / 20 / 50 / 100

Benchmark pool size impact trên throughput và latency. Thêm function:

```go
func benchmarkPoolSize(ctx context.Context, poolSize int, duration time.Duration) (ops int64, avgLatency time.Duration) {
    rdb := redis.NewClient(&redis.Options{
        Addr:        "localhost:6379",
        PoolSize:    poolSize,
        MinIdleConns: poolSize / 5,
        ReadTimeout: 2 * time.Second,
    })
    defer rdb.Close()

    if err := rdb.Ping(ctx).Err(); err != nil {
        log.Printf("[pool=%d] Ping failed: %v", poolSize, err)
        return 0, 0
    }

    var mu sync.Mutex
    var totalOps int64
    var totalLatency time.Duration

    var wg sync.WaitGroup
    for i := 0; i < poolSize; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            end := time.Now().Add(duration)
            localOps := int64(0)
            localLatency := time.Duration(0)

            for time.Now().Before(end) {
                start := time.Now()
                key := fmt.Sprintf("lab:key:%03d", rand.Intn(100))
                _, err := rdb.Get(ctx, key).Result()
                localLatency += time.Since(start)
                localOps++
                if err != nil && err != redis.Nil {
                    // ignore redis.Nil
                }
            }
            mu.Lock()
            totalOps += localOps
            totalLatency += localLatency
            mu.Unlock()
        }()
    }
    wg.Wait()

    return totalOps, totalLatency / time.Duration(totalOps)
}
```

Trong `main()`, thêm benchmark loop:

```go
// Step 5: Benchmark pool sizes
fmt.Println("\n=== Step 5: Pool Size Benchmark ===")
poolSizes := []int{5, 20, 50, 100}
duration := 3 * time.Second

for _, ps := range poolSizes {
    ops, avgLat := benchmarkPoolSize(ctx, ps, duration)
    if ops == 0 {
        continue
    }
    throughput := float64(ops) / duration.Seconds()
    fmt.Printf("PoolSize=%3d | Throughput: %8.0f ops/sec | Avg latency: %7s\n",
        ps, throughput, avgLat.Round(time.Microsecond))
}
```

> **Hint**: Kết quả benchmark phụ thuộc hardware. Quan sát:
> - Pool 5 vs 20: throughput tăng đáng kể
> - Pool 20 vs 50: throughput tăng ít hơn
> - Pool 50 vs 100: throughput gần như không tăng hoặc giảm (mutex contention + memory overhead)

---

## 3. Challenge Exercise (30-40 phút)

### Challenge: Design Connection Strategy Cho 50 Microservices × 20 Instances × 1000 RPS

**Scenario**:

```txt
50 microservices
  × 20 instances mỗi microservice (Kubernetes deployment, 20 pods per service)
  × 1000 RPS average per instance
  = 1,000,000 RPS total
  = 50,000 potential concurrent operations per second

Redis deployment:
  - 1 primary + 2 replicas (Redis Sentinel)
  - maxclients server-side: 10000 (default)
  - Instance: c5.xlarge (4 vCPU, 8GB RAM)
  - Network: VPC internal (LAN latency ~0.5-1ms)
```

**Yêu cầu**: Thiết kế connection strategy để hệ thống hoạt động ổn định mà không:

- Exceed `maxclients` server-side
- Gây retry storm khi Redis failover
- Gây connection storm khi rolling deploy 20 instances đồng thời

---

### 3a. Tính toán Connection Requirements

Tính toán từng bước, điền vào bảng:

```txt
Total microservices:           50
Total instances:               50 × 20 = 1000
Average RPS per instance:      1000
Total RPS:                     1,000,000

Expected command latency:      ~1ms (LAN)
Concurrency per instance:      1000 RPS × 1ms = 10 concurrent operations
Pool size per instance:        ~10-20 (formula: concurrency × latency / 1000)
Pool size per instance (safe): 30 (with headroom)

Total client connections (baseline):
  1000 instances × 30 = 30,000 connections
  → Exceeds maxclients = 10,000
```

**Câu hỏi 1**: Tại sao mỗi instance cần pool size 30 dù chỉ có ~10 concurrent operations?

> **Hint**: Command latency không đều. p99 có thể = 5-10ms thay vì 1ms. Pool cần đủ để handle burst.

**Câu hỏi 2**: Nếu dùng connection pool = 30, cần bao nhiêu Redis instances để không exceed maxclients?

```txt
Connection per Redis node: 30 × 1000 = 30,000 (impossible)
Thực tế: mỗi service chỉ cần pool nhỏ hơn nhiều.
```

**Phân tích chi tiết**:

```txt
Per-service pool size:
  avg_concurrent_ops = RPS × p99_latency = 1000 × 0.001 = 1
  pool_size_with_headroom = 10-20

Connection distribution (giả định traffic đều):
  50 services × 20 instances × 15 pool = 15,000 connections
  → maxclients 10,000: NOT OK

Cách 1: Giảm pool size
  pool_size = 10
  50 × 20 × 10 = 10,000 → at limit, no headroom
  → Risky: monitoring tools, Sentinel connections chiếm thêm

Cách 2: Tăng maxclients
  maxclients = 20000 (requires ulimit and kernel tuning)
  50 × 20 × 15 = 15,000 < 20,000 → OK, 25% headroom

Cách 3: Service mesh / shared connection proxy
  1 proxy per 5 services → 10 proxies × 5 services × 20 instances × 15 pool
  = 15,000 connections đến proxy
  Proxy → Redis: 10 × 30 = 300 connections
  → maxclients OK, nhưng thêm layer phức tạp
```

---

### 3b. Thiết kế Connection Config Cho Từng Service

**Service A — API Gateway (Critical, latency-sensitive, p99 < 50ms)**:

```go
rdb := redis.NewClient(&redis.Options{
    Addr:         "sentinel:26379",  // via Sentinel
    PoolSize:     30,
    MinIdleConns: 10,
    PoolTimeout:  50 * time.Millisecond,  // short — fail fast
    ReadTimeout:  30 * time.Millisecond,
    WriteTimeout: 30 * time.Millisecond,
    DialTimeout:  500 * time.Millisecond,
})
```

**Service B — Background Worker (Non-critical, batch, p99 < 30s)**:

```go
rdb := redis.NewClient(&redis.Options{
    Addr:        "redis-primary:6379",
    PoolSize:    20,
    MinIdleConns: 2,
    PoolTimeout: 30 * time.Second,
    ReadTimeout: 30 * time.Second,
    WriteTimeout: 10 * time.Second,
    DialTimeout:  10 * time.Second,
})
```

**Service C — Rate Limiter (High-volume, fail-open)**:

```go
rdb := redis.NewClient(&redis.Options{
    Addr:        "redis-cluster:6379",
    PoolSize:    15,       // small — fail fast is acceptable
    MinIdleConns: 5,
    PoolTimeout: 20 * time.Millisecond,
    ReadTimeout: 10 * time.Millisecond,
    WriteTimeout: 10 * time.Millisecond,
})
// NO retry for rate limiting — fail-open is correct behavior
```

---

### 3c. Connection Storm — Rolling Deploy Analysis

**Scenario**: Rolling deploy 20 instances mới, mỗi instance tạo pool 30 connections đồng thời.

```txt
Connection storm peak: 20 × 30 = 600 connections trong 1-2s
Baseline: 1000 × 30 = 30,000 connections
Peak during storm: 30,600 connections

maxclients = 20000 → EXCEEDED → 10,600 connections REJECTED
→ All 20 new instances fail to connect → deployment fails
```

**Mitigation strategies** — đánh giá từng cách:

| Strategy | Pros | Cons | Recommendation |
|---|---|---|---|
| Staggered startup (random 0-10s delay) | Simple, effective | Adds to startup time | **Recommended** |
| Lazy pool grow (MinIdleConns=0) | No idle connections | First requests slower | Recommended for workers |
| Connection rate limiting at K8s level | Prevents thundering herd | Complex to tune | Advanced |
| Gradual maxclients increase | Controlled | Operational overhead | Not recommended |

**Cách implement staggered startup**:

```go
// Staggered connection on startup (prevent connection storm)
func withJitter(baseDelay time.Duration, maxJitter time.Duration) time.Duration {
    jitter := time.Duration(int64(time.Now().UnixNano()) % int64(maxJitter))
    return baseDelay + jitter
}

// On service startup:
startupDelay := withJitter(0, 10*time.Second)
fmt.Printf("Waiting %v before connecting to Redis...\n", startupDelay)
time.Sleep(startupDelay)

rdb := redis.NewClient(&redis.Options{
    Addr:         "redis:6379",
    PoolSize:     30,
    MinIdleConns: 0,  // lazy grow under traffic
    // ...
})
```

---

### 3d. Circuit Breaker Policy Design

Thiết kế circuit breaker cho từng service:

**API Gateway** (circuit breaker nghiêm ngặt):

```go
cb := NewCircuitBreaker(
    name="api-gateway",
    failureThreshold=5,      // trip sau 5 failures
    successThreshold=3,      // close sau 3 successes trong half-open
    timeout=15*time.Second,  // thử lại sau 15s
)
// Open → fail-fast → user nhận error ngay
// Half-open → probe → nếu healthy → close
// Recovery: serve from local fallback cache nếu circuit OPEN
```

**Background Worker** (circuit breaker lenient):

```go
cb := NewCircuitBreaker(
    name="background-worker",
    failureThreshold=20,     // lenient: worker xử lý nhiều retry tự nhiên
    successThreshold=5,
    timeout=60*time.Second,  // chờ lâu hơn trước khi thử lại
)
// Khi OPEN: queue job trong memory, retry khi circuit half-open
// Risk: job overflow nếu Redis down lâu → cần bounded queue
```

**Rate Limiter** (no circuit breaker — fail-open):

```go
// Rate limiter: fail-open = correct behavior
// → Nếu Redis down, cho phép tất cả requests đi qua
// → Không block user vì lỗi infrastructure
// → Monitoring: alert khi rate limiter fails liên tục
// → Business logic: accept more risk than data integrity
```

---

### 3e. Failure Scenario: Redis Failover During Peak Traffic

```txt
t=0: Redis primary down → Sentinel triggers failover
t=0-5s: Failover in progress (5s SLA)
t=5s: New primary elected
t=5s+: All 1000 instances reconnect simultaneously

Connection storm during failover:
  - 1000 instances × retry strategy = massive reconnect burst
  - Exponential backoff spread: 100ms, 200ms, 400ms... → spread helps
  - Jittered reconnect: adds 0-5s random → further spread
  - After 30s: all connected

Mitigation:
  1. Sentinel notify → client tự discover new master
  2. go-redis/v9: tự động handle reconnection
  3. Exponential backoff + jitter: prevents thundering herd
  4. Circuit breaker: prevent retry storm
  5. Read from replica during failover (if acceptable consistency)
```

**Verification checklist**:

- [ ] maxclients set to 20000+ (not default 10000)
- [ ] Pool size per instance = 15-30 (not 100+)
- [ ] Total expected connections = 1000 × 15 = 15,000 < 20,000
- [ ] Circuit breaker: failureThreshold=5, timeout=15s
- [ ] Retry: exponential backoff with jitter, maxRetries=3
- [ ] Staggered startup: 0-10s random delay
- [ ] MinIdleConns=0 for workers (lazy grow)
- [ ] PoolTimeout=50ms for API Gateway (fail fast)
- [ ] Prometheus alert: connected_clients > 16000 (80% of 20000)

---

## 4. Reflection Questions

### Question 1: Khi nào pool size lớn (100+) là lựa chọn đúng?

Pool size 100+ **đúng** khi:
- Redis được vận hành bởi **multiple threads/processes** (VD: Python gunicorn với 100 workers, mỗi worker gọi Redis riêng)
- Dùng **Redis Cluster** (mỗi node chỉ nhận 1/16384 traffic, single-threaded bottleneck giảm)
- Command latency **cao** (>10ms per command, VD: Redis over WAN)

Pool size 100+ **sai** khi:
- Single-threaded language (Go, Node.js): goroutine/async concurrency không tương đương với connection count
- LAN network: 1ms latency → pool 10 đủ cho 10 concurrent operations

**Reflection**: Trong Go, nếu bạn cần 100 goroutines access Redis đồng thời, bạn chỉ cần pool size 10-20. Go scheduler sẽ multiplex 100 goroutines qua 10-20 connections.

### Question 2: Tại sao hầu hết retry storm incidents xảy ra dù developer đã implement retry?

Retry storm xảy ra vì retry logic **amplifies load** thay vì giảm. Ví dụ: 1000 RPS × 3 retries = 3000 RPS khi Redis có vấn đề. 3000 RPS làm Redis chậm hơn → retry nhiều hơn → exponential growth.

**Reflection**: Retry chỉ giúp khi Redis failure là **transient** (VD: network blip 100ms). Nếu Redis down hoàn toàn, retry không giúp gì — chỉ làm tệ hơn. Circuit breaker = fail-fast = đúng behavior khi Redis down.

### Question 3: CLIENT PAUSE có phải là công cụ production-ready để handle maintenance không?

`CLIENT PAUSE` **có thể** dùng cho maintenance ngắn (< 1 phút) trên single-node Redis. Nhưng có caveats:

- Pauses **tất cả** clients — production traffic bị impact
- Không pause commands từ `redis-cli` (internal commands vẫn chạy)
- Với Redis Sentinel/Cluster: failover không bị pause, nhưng client reconnect sau failover có thể gặp race condition
- **Better approach**: DRAIN mode (Redis 7.2+) hoặc redirect traffic trước khi maintenance

**Reflection**: Nếu bạn dùng `CLIENT PAUSE` cho maintenance, bạn đang trading availability cho simplicity. Is it worth it?

### Question 4: MinIdleConns nên đặt bao nhiêu?

`MinIdleConns` giữ N connections luôn warm. Giá trị phụ thuộc:

- Traffic pattern: steady traffic → higher MinIdleConns; burst traffic → lower
- Connection cost: high-latency network (WAN) → higher MinIdleConns justified
- Memory: MinIdleConns × 16KB per instance → với 1000 instances × 10 = 160MB client memory

**Reflection**: MinIdleConns = PoolSize / 3 là rule of thumb hợp lý. Nếu pool=30, MinIdleConns=10. Nhưng nếu startup không có traffic ngay, MinIdleConns=0 tránh wasted connections.

### Question 5: go-redis tự động reconnect — vậy khi nào cần manual connection management?

go-redis **tự động** reconnect khi connection bị đóng. Manual management **chỉ cần** khi:

- Bạn muốn control **khi nào** reconnect (VD: startup delay, graceful shutdown)
- Bạn cần **custom health check** thay vì ping định kỳ
- Bạn dùng **Sentinel/Cluster** và muốn force topology refresh
- Bạn muốn **connection event** callbacks (VD: log, metric)

**Reflection**: 95% trường hợp, go-redis auto-reconnect là đủ. Chỉ implement manual management khi có requirement cụ thể.

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1**: `CLIENT LIST` output format:
```txt
id=5 addr=... laddr=... fd=8 name=my-client db=0 cmd=GET flags=N idle=0
```
Key fields: `addr` (client IP:port), `idle` (0=active, >0=idle seconds), `cmd` (last command).

**1.3**: Default values:
- `maxclients=10000`: tổng connections server-side limit
- `timeout=0`: không auto-disconnect idle clients
- `tcp-keepalive=300`: gửi TCP keepalive mỗi 5 phút để detect dead connections

**1.6**: `CLIENT PAUSE` blocks ALL Redis commands từ ALL clients. `WRITES` mode chỉ pause write commands. Dùng cho short maintenance, không phải long-running operation.

---

### Hands-on Lab Solutions

**Step 1** — `GetWithRetry` logic:
- Retry 0: execute immediately
- Retry 1+: `backoff(attempt)` delay trước khi execute
- `isRetryable`: check error message prefixes (connection refused, EOF, timeout)
- `redis.Nil`: NOT retryable (key not found — expected behavior)

**Step 2** — Circuit breaker states:
- `CLOSED`: cho phép calls, count failures
- `OPEN`: fail-fast, không execute, sau `timeout` chuyển HALF-OPEN
- `HALF-OPEN`: cho 1-N test calls, nếu success → CLOSED, nếu fail → OPEN

**Step 3** — Circuit breaker integration:
- `Execute()` wraps Redis call
- `recordFailure()`: tăng counter, trip nếu >= threshold
- `recordSuccess()`: reset counter (CLOSED) hoặc close circuit (HALF-OPEN)

**Step 4** — Redis unavailable simulation:
- Kill container → connection refused → retry attempts → circuit trips OPEN
- After 3 failures: circuit OPEN → subsequent calls return immediately (fail-fast)
- Without circuit breaker: mỗi call chờ `DialTimeout=5s` → 20 calls × 5s = 100s blocking
- With circuit breaker: 20 calls in ~1s (fail-fast after OPEN)

**Step 5** — Pool size benchmark:
- Pool 5: throughput ~2-5K ops/sec (limited by pool)
- Pool 20: throughput ~10-20K ops/sec (Redis starts to be bottleneck)
- Pool 50: throughput ~40-50K ops/sec (Redis single-threaded ~50K ops/sec)
- Pool 100: throughput ~45-50K ops/sec (same as pool 50, context switch overhead adds)

**Key insight**: Redis single-threaded → throughput plateaus at pool 50. Larger pools only add memory overhead and mutex contention.

---

### Challenge Solutions

**3a — Connection calculation**:

```txt
Real pool size needed: concurrency × p99_latency
= 1000 RPS × 1ms = 1 concurrent operation average
= pool 10-15 with headroom (for burst)

Total connections baseline: 50 services × 20 instances × 15 = 15,000
maxclients default 10,000: NOT OK → increase to 20,000
maxclients 20,000: 15,000 < 20,000 → OK (25% headroom)

Plus:
- Sentinel connections: 3 × 3 = 9
- Monitoring/Redis exporter: ~10
- Redis Cluster nodes (if used): ~10
- Total overhead: ~30

Final: 15,030 < 20,000 → OK
```

**3b — Service-specific configs**:

- **API Gateway**: PoolTimeout=50ms (short — fail fast), ReadTimeout=30ms (p99 SLA budget). Circuit breaker strict (failureThreshold=5).
- **Background Worker**: PoolTimeout=30s (batch jobs can wait), ReadTimeout=30s. Circuit breaker lenient (failureThreshold=20).
- **Rate Limiter**: NO retry (fail-open is correct), PoolTimeout=20ms (fast fail). No circuit breaker — just fail and log.

**3c — Connection storm mitigation**:

```txt
Rolling deploy 20 instances:
  With staggered startup (0-10s jitter):
    Spread: 0s, 1s, 2s, ... 9s = connections spread over 10s
    Peak concurrent connections during deploy: 20 × 15 / 10 = ~30 extra/second
    Baseline: 15,000 → Peak: 15,300 < 20,000 → OK

Without jitter:
  All 20 instances connect simultaneously
  Peak: 15,000 + 300 = 15,300 → still OK (but margin is thin)
  If any instance has pool 30: 15,000 + 600 = 15,600 → OK
  If all 50 services deploy simultaneously (blue-green): 50 × 20 × 15 = 15,000 new → total 30,000 > 20,000 → REJECTED

Solution: Never deploy all services simultaneously. Staggered deployment + maxclients tuning.
```

**3d — Circuit breaker rationale**:

- **API Gateway**: 5 failures trip circuit → 15s cooldown → probe. Aggressive because user-facing SLA is critical.
- **Background Worker**: 20 failures trip → 60s cooldown. Lenient because jobs can be retried later, and some failures are expected.
- **Rate Limiter**: No circuit breaker → fail-open is correct. Rate limiter failure = allow traffic (availability > correctness for rate limiting).

---

### Reflection Solutions

**Q1**: Pool 100+ đúng khi: multi-process (gunicorn workers), Redis Cluster (sharded), WAN latency (>10ms). Sai khi: Go/Node.js single-threaded với LAN.

**Q2**: Retry storm xảy ra vì retry **amplifies** load khi Redis đã có vấn đề. Fix: exponential backoff + jitter + circuit breaker + max retries cap.

**Q3**: `CLIENT PAUSE` là quick hack, không phải production tool. DRAIN mode (Redis 7.2+) hoặc traffic redirection tốt hơn.

**Q4**: `MinIdleConns = PoolSize / 3`. MinIdleConns cao = better for steady traffic, thấp = better for bursty traffic.

**Q5**: go-redis auto-reconnect cover 95% cases. Manual management chỉ khi: custom health check, force topology refresh, connection event callbacks.
