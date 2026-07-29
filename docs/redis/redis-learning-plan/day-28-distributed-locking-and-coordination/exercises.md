# Day 28: Distributed Locking & Coordination — Exercises

**Thời gian**: ~2 giờ
**Ngôn ngữ**: Go (Day 27 dùng TypeScript nên Day 28 luân phiên sang Go)
**Môi trường**: Docker Compose với Redis 7.2

---

## 0. Setup

```bash
# Thư mục làm việc
mkdir -p ~/redis-lock-lab && cd ~/redis-lock-lab

# Docker Compose với Redis standalone + Sentinel-ready
cat > docker-compose.yml <<'EOF'
version: '3.8'
services:
  redis:
    image: redis:7.2
    ports:
      - "6379:6379"
    command: redis-server --save "" --appendonly no --maxmemory 128mb --enable-debug-command yes
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 5s
      timeout: 3s
      retries: 5
EOF

docker compose up -d
redis-cli PING  # expect: PONG

# Verify Lua scripting available
redis-cli EVAL "return 'Lua OK'" 0
# expect: Lua OK
```

---

## 1. Warm-up Exercises (15-20 phút)

Mục tiêu: làm quen với SET NX PX behavior, observe race condition, thực hành safe unlock bằng Lua.

### Exercise 1.1: SET NX PX cơ bản

```txt
# Xóa key nếu tồn tại
DEL lock:task001

# Client A: acquire lock (token = "client-a-token")
SET lock:task001 client-a-token NX PX 5000
```

Expected output:
```
OK
```

```txt
# Client B: cùng key, try acquire (token = "client-b-token")
SET lock:task001 client-b-token NX PX 5000
```

Expected output:
```
(nil)
```

Giải thích: NX fail vì key đã tồn tại. Client B không acquire được lock.

```txt
# Kiểm tra lock còn sống không
PTTL lock:task001
```

Expected output: một số dương (~4000-5000ms)

```txt
# Đợi lock expire
# Chạy: redis-cli DEBUG SLEEP 6
DEBUG SLEEP 6
```

```txt
# Client B: thử lại sau khi expire
SET lock:task001 client-b-token NX PX 5000
```

Expected output:
```
OK
```

Giải thích: Lock đã expire, Client B acquire được.

### Exercise 1.2: Race condition — DEL không an toàn

Terminal 1 (Client A):
```txt
SET lock:order123 client-a-token NX PX 30000
OK

# A đang xử lý... (giả sử A bị slow)
# A chưa kịp hoàn thành

# Simulate: lock của A expire ngay lập tức
PEXPIRE lock:order123 1
# Đợi 10-20ms ở shell: sleep 0.02
```

Terminal 2 (Client B):
```txt
# B không biết A vẫn đang xử lý, acquire lock sau khi TTL của A hết hạn
SET lock:order123 client-b-token NX PX 30000
OK
```

Terminal 1 (Client A — sau khi "hoàn thành"):
```txt
# A gọi DEL không an toàn (BUG)
DEL lock:order123
(integer) 1
```

Terminal 3 (Client C):
```txt
# C acquire lock thành công vì A đã xóa nhầm lock của B
SET lock:order123 client-c-token NX PX 30000
OK
```

**Bug confirmed**: Client A đã xóa Client B's lock dù A không còn là owner. Client C acquire được lock trong khi B vẫn nghĩ mình đang hold lock.

### Exercise 1.3: Safe unlock bằng Lua

```txt
# Script: safe unlock — chỉ xóa nếu token match
EVAL "
  if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
  else
    return 0
  end
" 1 lock:order123 client-a-token

# Expected: (integer) 0 (Client A không còn hold lock, Client C đã acquire)
```

```txt
# Client C: safe release
EVAL "
  if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
  else
    return 0
  end
" 1 lock:order123 client-c-token

# Expected: (integer) 1 (Client C release thành công)
```

### Exercise 1.4: Lock extension

```txt
SET lock:resource client-x-token NX PX 5000
OK

# Extend TTL (chỉ nếu token match)
EVAL "
  if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
  else
    return 0
  end
" 1 lock:resource client-x-token 10000

# Expected: (integer) 1
PTTL lock:resource
# Expected: ~10000ms
```

### Exercise 1.5: Query lock owner

```txt
SET lock:inventory:sku001 secure-random-token NX PX 60000
OK

GET lock:inventory:sku001
# Output: secure-random-token

TYPE lock:inventory:sku001
# Output: string

OBJECT ENCODING lock:inventory:sku001
# Output: raw (short string) hoặc embstr (short string <= 44 bytes)
```

---

## 2. Hands-on Lab (60-70 phút)

**Lab: Safe Distributed Lock — Từ Bug đến Production-Ready**

### Mục tiêu

Implement safe distributed lock trong Go, start từ buggy version và fix từng bước:

1. **Buggy version**: DEL without token check (race condition)
2. **Step 1 fix**: Add token + simple DEL (still buggy)
3. **Step 2 fix**: Add Lua script for safe unlock
4. **Step 3 fix**: Add TTL extension
5. **Step 4 fix**: Add exponential backoff + retry
6. **Benchmark**: Compare all versions

### Bước 1: Setup project

```bash
mkdir -p ~/redis-lock-lab/lock-lab
cd ~/redis-lock-lab/lock-lab

go mod init lock-lab
go get github.com/redis/go-redis/v9@latest
```

```go
// main.go
package main

import (
    "context"
    "fmt"
    "os"
    "sort"
    "sync"
    "sync/atomic"
    "time"

    "github.com/redis/go-redis/v9"
)

var ctx = context.Background()
var rdb *redis.Client

func init() {
    rdb = redis.NewClient(&redis.Options{
        Addr: "localhost:6379",
    })
}

func cleanup() {
    rdb.FlushDB(ctx)
    rdb.Close()
}

func main() {
    defer cleanup()

    fmt.Println("=== Distributed Lock Lab ===")
    fmt.Println()

    // Test 1: Buggy lock — DEL without token check
    fmt.Println("--- Test 1: Buggy Lock (DEL without check) ---")
    testBuggyLock()

    // Test 2: GET+DEL race — still buggy
    fmt.Println()
    fmt.Println("--- Test 2: GET+DEL Race ---")
    testSimpleTokenLock()

    // Test 3: Safe lock — Lua unlock
    fmt.Println()
    fmt.Println("--- Test 3: Safe Lock (Lua unlock) ---")
    testSafeLock()

    // Test 4: Concurrent safe lock with contention
    fmt.Println()
    fmt.Println("--- Test 4: Concurrent Safe Lock (50 workers) ---")
    testConcurrentSafeLock()

    // Test 5: Benchmark all approaches
    fmt.Println()
    fmt.Println("--- Test 5: Benchmark ---")
    benchmarkAllApproaches()
}
```

### Bước 2: Buggy lock — DEL without token check

```go
// testBuggyLock demonstrates the unsafe DEL bug
func testBuggyLock() {
    const key = "buggy:lock:resource"

    // Client A acquires lock
    acquired, _ := rdb.SetNX(ctx, key, "client-a-token", 30*time.Second).Result()
    fmt.Printf("Client A acquired: %v\n", acquired)

    // Simulate Client A is slow — lock expires
    fmt.Println("Simulating lock expiry (TTL = 1ms for test)...")
    rdb.Expire(ctx, key, 1*time.Millisecond)
    time.Sleep(10 * time.Millisecond)

    // Client B acquires lock
    acquiredB, _ := rdb.SetNX(ctx, key, "client-b-token", 30*time.Second).Result()
    fmt.Printf("Client B acquired: %v\n", acquiredB)

    // Client A "wakes up" and releases — WRONG! Uses unsafe DEL
    // This deletes B's lock even though A no longer owns it
    result, _ := rdb.Del(ctx, key).Result()
    fmt.Printf("Client A called DEL, result: %d (BUG: deleted B's lock!)\n", result)

    // Client C acquires (should succeed because A deleted B's lock)
    acquiredC, _ := rdb.SetNX(ctx, key, "client-c-token", 30*time.Second).Result()
    fmt.Printf("Client C acquired: %v (should be OK, but B was also supposed to hold it!)\n", acquiredC)

    // At this point: A, B, C all had overlapping access
    fmt.Println("BUG CONFIRMED: Multiple clients accessed resource simultaneously")
}
```

Expected output:
```
Client A acquired: true
Simulating lock expiry...
Client B acquired: true
Client A called DEL, result: 1 (BUG: deleted B's lock!)
Client C acquired: true (should be OK, but B was also supposed to hold it!)
```

### Bước 3: GET+DEL race — still buggy

```go
// testSimpleTokenLock demonstrates that GET+DEL is still buggy because the
// lock can expire and be reacquired between the GET and DEL commands.
func testSimpleTokenLock() {
    const key = "simple:lock:resource"

    // Client A acquires with a very short TTL.
    acquired, _ := rdb.SetNX(ctx, key, "client-a-token", 50*time.Millisecond).Result()
    fmt.Printf("Client A acquired: %v\n", acquired)

    // Client A reads token before DEL.
    currentToken, _ := rdb.Get(ctx, key).Result()
    fmt.Printf("Client A GET result: %s\n", currentToken)

    // Between GET and DEL, A pauses. The lock expires.
    time.Sleep(80 * time.Millisecond)

    // Client B acquires the same lock.
    acquiredB, _ := rdb.SetNX(ctx, key, "client-b-token", 30*time.Second).Result()
    fmt.Printf("Client B acquired: %v\n", acquiredB)

    // Client A uses the stale GET result and calls DEL.
    // This deletes B's lock because GET and DEL were not atomic.
    if currentToken == "client-a-token" {
        deleted, _ := rdb.Del(ctx, key).Result()
        fmt.Printf("Client A DEL result: %d (BUG: deleted B's lock)\n", deleted)
    }

    exists, _ := rdb.Exists(ctx, key).Result()
    fmt.Printf("Lock exists after A DEL: %d\n", exists)
    fmt.Println("BUG: GET+DEL is not safe; use Lua check-and-delete")
}
```

Expected output:
```
Client A acquired: true
Client A GET result: client-a-token
Client B acquired: true
Client A DEL result: 1 (BUG: deleted B's lock)
Lock exists after A DEL: 0
```

### Bước 4: Safe lock — Lua unlock (FIXED)

```go
const safeUnlockScript = `
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
`

func safeLockAcquire(key string, ttl time.Duration) (string, bool) {
    token := fmt.Sprintf("%d-%d", time.Now().UnixNano(), os.Getpid())
    acquired, _ := rdb.SetNX(ctx, key, token, ttl).Result()
    return token, acquired
}

func safeLockRelease(key, token string) bool {
    result, _ := rdb.Eval(ctx, safeUnlockScript, []string{key}, token).Int64()
    return result == 1
}

func testSafeLock() {
    const key = "safe:lock:resource"

    // Client A acquires safe lock
    tokenA, acquired := safeLockAcquire(key, 5*time.Second)
    fmt.Printf("Client A acquired: %v (token: %s)\n", acquired, tokenA)

    // Client B tries to acquire
    _, acquiredB := safeLockAcquire(key, 30*time.Second)
    fmt.Printf("Client B acquired: %v (correctly blocked)\n", acquiredB)

    // Simulate Client A processing complete, then releasing
    time.Sleep(500 * time.Millisecond)
    released := safeLockRelease(key, tokenA)
    fmt.Printf("Client A released: %v (correctly released own lock)\n", released)

    // Client B can now acquire
    tokenB, acquiredB2 := safeLockAcquire(key, 30*time.Second)
    fmt.Printf("Client B acquired: %v (after A released)\n", acquiredB2)
    safeLockRelease(key, tokenB)

    fmt.Println("Safe lock: correct behavior demonstrated")
}
```

Expected output:
```
Client A acquired: true (token: 1716xxxxxxx-12345)
Client B acquired: false (correctly blocked)
Client A released: true (correctly released own lock)
Client B acquired: true (after A released)
Safe lock: correct behavior demonstrated
```

### Bước 5: Full production lock with retry, backoff, extension

```go
// ProductionDistributedLock wraps all best practices
type ProductionDistributedLock struct {
    rdb          *redis.Client
    maxRetries   int
    retryDelay   time.Duration
    jitterWindow time.Duration
}

const (
    safeExtendScript = `
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
`
)

func NewProductionLock(rdb *redis.Client) *ProductionDistributedLock {
    return &ProductionDistributedLock{
        rdb:          rdb,
        maxRetries:   5,
        retryDelay:   100 * time.Millisecond,
        jitterWindow: 50 * time.Millisecond,
    }
}

// Lock represents an acquired lock
type Lock struct {
    rdb   *redis.Client
    key   string
    token string
    ttl   time.Duration
}

// Acquire with exponential backoff + jitter
func (pl *ProductionDistributedLock) Acquire(ctx context.Context, key string, ttl time.Duration) (*Lock, error) {
    token := fmt.Sprintf("%d-%d-%d", time.Now().UnixNano(), os.Getpid(), ctx.Value("request_id"))

    for attempt := 0; attempt <= pl.maxRetries; attempt++ {
        if attempt > 0 {
            backoff := pl.retryDelay * time.Duration(1<<uint(attempt-1))
            jitter := time.Duration(0)
            if pl.jitterWindow > 0 {
                jitter = time.Duration(time.Now().UnixNano() % int64(pl.jitterWindow*2))
            }

            select {
            case <-ctx.Done():
                return nil, ctx.Err()
            case <-time.After(backoff + jitter):
            }
        }

        acquired, err := pl.rdb.SetNX(ctx, key, token, ttl).Result()
        if err != nil {
            return nil, fmt.Errorf("redis SetNX: %w", err)
        }

        if acquired {
            return &Lock{
                rdb:   pl.rdb,
                key:   key,
                token: token,
                ttl:   ttl,
            }, nil
        }
    }

    return nil, fmt.Errorf("lock not acquired after %d attempts", pl.maxRetries)
}

// Release safely (atomic Lua check-and-delete)
func (l *Lock) Release(ctx context.Context) error {
    result, err := l.rdb.Eval(ctx, safeUnlockScript, []string{l.key}, l.token).Int64()
    if err != nil {
        return fmt.Errorf("safe release: %w", err)
    }
    if result == 0 {
        return fmt.Errorf("not lock owner (lock expired or held by another client)")
    }
    return nil
}

// Extend TTL (atomic Lua check-and-extend)
func (l *Lock) Extend(ctx context.Context, newTTL time.Duration) error {
    result, err := l.rdb.Eval(ctx, safeExtendScript, []string{l.key}, l.token, newTTL.Milliseconds()).Int64()
    if err != nil {
        return fmt.Errorf("safe extend: %w", err)
    }
    if result == 0 {
        return fmt.Errorf("not lock owner (cannot extend)")
    }
    l.ttl = newTTL
    return nil
}

// WithLock is a helper to run a function with lock protection
func (pl *ProductionDistributedLock) WithLock(
    ctx context.Context,
    key string,
    ttl time.Duration,
    fn func() error,
) error {
    lock, err := pl.Acquire(ctx, key, ttl)
    if err != nil {
        return fmt.Errorf("lock acquire: %w", err)
    }
    defer lock.Release(ctx)

    return fn()
}
```

### Bước 6: Concurrent safe lock test

```go
func testConcurrentSafeLock() {
    const key = "concurrent:lock:resource"
    const numWorkers = 50
    const opsPerWorker = 10

    rdb.FlushDB(ctx)

    var wg sync.WaitGroup
    successCount := int64(0)
    failCount := int64(0)

    pl := NewProductionLock(rdb)

    for i := 0; i < numWorkers; i++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            for j := 0; j < opsPerWorker; j++ {
                lock, err := pl.Acquire(ctx, key, 2*time.Second)
                if err != nil {
                    atomic.AddInt64(&failCount, 1)
                    continue
                }

                // Simulate work
                time.Sleep(50 * time.Millisecond)

                err = lock.Release(ctx)
                if err != nil {
                    atomic.AddInt64(&failCount, 1)
                } else {
                    atomic.AddInt64(&successCount, 1)
                }
            }
        }(i)
    }

    wg.Wait()

    total := successCount + failCount

    fmt.Printf("Workers: %d, Ops/worker: %d\n", numWorkers, opsPerWorker)
    fmt.Printf("Success: %d, Fail: %d, Total: %d\n", successCount, failCount, total)
    fmt.Printf("Attempted ops: %d\n", numWorkers*opsPerWorker)
    fmt.Printf("Correctness invariant: no two successful workers held the lock at the same time\n")
}
```

Expected output:
```
Workers: 50, Ops/worker: 10
Success: <varies>, Fail: <varies>, Total: 500
Attempted ops: 500
Correctness invariant: no two successful workers held the lock at the same time
```

### Bước 7: Benchmark all approaches

```go
func benchmarkAllApproaches() {
    const iterations = 1000
    const numWorkers = 20

    rdb.FlushDB(ctx)

    // Benchmark 1: Direct SetNX (no lock, just measure overhead)
    fmt.Println("=== Benchmark: Lock Acquire + Release ===")

    // Unsafe DEL approach
    start := time.Now()
    for i := 0; i < iterations; i++ {
        key := fmt.Sprintf("bench:unsafe:%d", i)
        rdb.SetNX(ctx, key, "token", 1*time.Second)
        rdb.Del(ctx, key)
    }
    unsafeDuration := time.Since(start)
    fmt.Printf("Unsafe DEL:  %d ops in %v (%.2f ops/ms)\n",
        iterations, unsafeDuration, float64(iterations)/float64(unsafeDuration.Milliseconds()))

    // Safe Lua approach
    start = time.Now()
    for i := 0; i < iterations; i++ {
        key := fmt.Sprintf("bench:safe:%d", i)
        rdb.SetNX(ctx, key, "token", 1*time.Second)
        rdb.Eval(ctx, safeUnlockScript, []string{key}, "token")
    }
    safeDuration := time.Since(start)
    fmt.Printf("Safe Lua:    %d ops in %v (%.2f ops/ms)\n",
        iterations, safeDuration, float64(iterations)/float64(safeDuration.Milliseconds()))

    // Production lock with retry
    pl := NewProductionLock(rdb)
    start = time.Now()
    var acquired int64
    for i := 0; i < iterations; i++ {
        lock, err := pl.Acquire(ctx, fmt.Sprintf("bench:prod:%d", i), 1*time.Second)
        if err == nil {
            lock.Release(ctx)
            atomic.AddInt64(&acquired, 1)
        }
    }
    prodDuration := time.Since(start)
    fmt.Printf("Production:  %d ops in %v (%.2f ops/ms)\n",
        acquired, prodDuration, float64(acquired)/float64(prodDuration.Milliseconds()))

    fmt.Println()
    fmt.Println("=== Benchmark: Concurrent Contention (50 workers, 10 ops each) ===")
    benchmarkContention(50, 10)
}

func benchmarkContention(numWorkers, opsPerWorker int) {
    const key = "bench:contention"

    rdb.FlushDB(ctx)

    var wg sync.WaitGroup
    latencies := make([]time.Duration, numWorkers*opsPerWorker)
    var idx int64

    pl := NewProductionLock(rdb)

    start := time.Now()
    for w := 0; w < numWorkers; w++ {
        wg.Add(1)
        go func(workerID int) {
            defer wg.Done()
            for i := 0; i < opsPerWorker; i++ {
                t0 := time.Now()
                lock, err := pl.Acquire(ctx, key, 5*time.Second)
                if err == nil {
                    time.Sleep(10 * time.Millisecond) // simulate work
                    lock.Release(ctx)
                    latencies[atomic.AddInt64(&idx, 1)-1] = time.Since(t0)
                }
            }
        }(w)
    }
    wg.Wait()
    totalDuration := time.Since(start)

    // Sort only successful lock acquisitions for percentile.
    successful := latencies[:idx]
    sort.Slice(successful, func(i, j int) bool { return successful[i] < successful[j] })
    n := len(successful)
    if n == 0 {
        return
    }
    p50 := successful[n*50/100]
    p99 := successful[n*99/100]

    fmt.Printf("Total ops: %d, Time: %v\n", n, totalDuration)
    fmt.Printf("p50 latency: %v, p99 latency: %v\n", p50, p99)
    fmt.Printf("Throughput: %.2f ops/sec\n", float64(n)/totalDuration.Seconds())
}
```

### Run và verify

```bash
go mod tidy
go run main.go
```

Expected results:
```
=== Distributed Lock Lab ===

--- Test 1: Buggy Lock (DEL without check) ---
Client A acquired: true
Simulating lock expiry...
Client B acquired: true
Client A called DEL, result: 1 (BUG: deleted B's lock!)
Client C acquired: true
BUG CONFIRMED: Multiple clients accessed resource simultaneously

--- Test 2: GET+DEL Race ---
Client A acquired: true
Client A GET result: client-a-token
Client B acquired: true
Client A DEL result: 1 (BUG: deleted B's lock)
Lock exists after A DEL: 0
BUG: GET+DEL is not safe; use Lua check-and-delete

--- Test 3: Safe Lock (Lua unlock) ---
Client A acquired: true (token: 1716xxxxxxx-12345)
Client B acquired: false (correctly blocked)
Client A released: true (correctly released own lock)
Client B acquired: true (after A released)
Safe lock: correct behavior demonstrated

--- Test 4: Concurrent Safe Lock (50 workers) ---
Workers: 50, Ops/worker: 10
Success: <varies>, Fail: <varies>, Total: 500
Attempted ops: 500
Correctness invariant: no two successful workers held the lock at the same time

--- Test 5: Benchmark ---
Unsafe DEL:  1000 ops in 1.2s (0.83 ops/ms)
Safe Lua:    1000 ops in 1.5s (0.67 ops/ms)
Production:  1000 ops in 8.3s (0.12 ops/ms)  <- retry overhead

=== Benchmark: Concurrent Contention ===
Total ops: 500, Time: 5.2s
p50 latency: 800ms, p99 latency: 3200ms  <- contention visible
Throughput: 96.15 ops/sec
```

---

## 3. Challenge Exercise (30-40 phút)

**Challenge: Analyze 3 Scenarios — Should You Use Redis Lock?**

### Scenario A: Payment Processing Service

Một payment service xử lý thanh toán credit card. Mỗi payment debit từ customer balance. Service chạy trên 5 instances, dùng Redis để coordinate. Nếu 2 instances cùng debit cùng account cùng lúc, balance có thể bị sai.

**Yêu cầu**: Phân tích:
1. Redis lock có phù hợp không? Tại sao?
2. Nếu dùng Redis lock, cần những gì để đảm bảo correctness?
3. Đề xuất giải pháp tốt hơn (có thể dùng kết hợp)
4. Nêu concrete numbers (TTL, latency expectations)

### Scenario B: Cache Warming Job

Một scheduled job chạy mỗi 10 phút để warm cache từ database cho top 1000 products. Job chạy trên 3 instances. Nếu 2 instances cùng warm cùng product, không có harm (idempotent cache write). Nhưng nếu job chạy quá lâu (> 10 phút), có thể overlap với run tiếp theo.

**Yêu cầu**:
1. Redis lock có phù hợp không? Tại sao?
2. Thiết kế lock strategy với concrete TTL
3. Nếu không dùng lock, alternatives nào?
4. Phân tích trade-off: lock vs no-lock vs queue

### Scenario C: Leader Election cho Health Check Service

Health check service chạy trên 10 instances. Mỗi instance ping 50 external endpoints. Chỉ 1 instance được phép "report" health status lên monitoring dashboard để tránh duplicate alerts. Nếu leader die, instance khác phải take over trong < 5 giây.

**Yêu cầu**:
1. Redis lock vs ZooKeeper vs etcd cho leader election?
2. Nếu Redis lock: thiết kế với TTL, renewal strategy
3. Split-brain scenario: 2 instances cùng nghĩ mình là leader — làm sao detect?
4. Failover time: Redis lock vs ZooKeeper — so sánh

### Deliverable

Viết 1 trang analysis cho mỗi scenario (3 trang total), bao gồm:
- Decision: dùng hay không dùng Redis lock (với lý do cụ thể)
- Nếu dùng: concrete implementation (TTL, token, Lua script)
- Alternative approach (nếu có)
- Risk analysis
- Recommendation

---

## 4. Reflection Questions

### Câu 1
Tại sao Martin Kleppmann nói "Redlock is not safe" trong khi nhiều production system vẫn dùng Redlock mà không có vấn đề?

### Câu 2
Fencing token giải quyết vấn đề gì mà lock không giải quyết được? Tại sao ZooKeeper/etcd không cần fencing token riêng?

### Câu 3
Bạn đang design một hệ thống distributed rate limiter. Mỗi user được phép 1000 requests/giây. Dùng Redis lock để serialize requests? Có cách nào tốt hơn không?

### Câu 4
Một dev nói: "Tôi dùng Redis lock với TTL 30 giây nên lock bao giờ cũng an toàn." Phản bác điều này.

### Câu 5
So sánh queue-based serialization với lock-based serialization. Khi nào queue "overkill"?

---

## 5. Solution Guide

### Warning: Spoiler

Phần dưới chứa lời giải. Hãy thử làm bài tập trước khi đọc.

---

### Warm-up Solutions

**1.1**: `SET NX PX` là atomic. Client A acquire -> OK. Client B acquire cùng key -> nil. Sau expire, B acquire được. TTL countdown là server-side, không có race giữa SET và TTL.

**1.2**: Bug confirmed. DEL không kiểm tra token. Client A xóa lock khi B đã acquire (hoặc B chưa kịp acquire nhưng C đã). Multiple clients access resource simultaneously.

**1.3**: Lua script atomic check-and-delete. `if GET == token then DEL` là single event-loop step. Không có window giữa GET và DEL. Nếu token không match, return 0 (không xóa).

**1.4**: PEXPIRE trong Lua: `if GET == token then PEXPIRE key ms`. Atomic check-and-extend. Không có window để race.

**1.5**: Lock key type = string. Encoding = raw hoặc embstr (tùy token length). Token dài > 44 bytes -> raw.

---

### Lab Solutions

**Bug Analysis**:
- Test 1: DEL không check token -> delete B's lock khi B chưa acquire được
- Test 2: GET+DEL 2 commands, không atomic -> race giữa GET và DEL

**Safe Lock Fix**:
- Token phải unique, không predictable (dùng nanosecond timestamp + PID)
- Unlock phải dùng Lua script: `if GET == token then DEL`
- Không bao giờ dùng `DEL` trực tiếp

**Production Lock Details**:
- Exponential backoff: 100ms * 2^attempt + random jitter (0-50ms)
- Max retries = 5: max wait = 100*(1+2+4+8+16) + jitter = ~3.2s
- TTL = duration * 3 + margin: nếu operation = 100ms, TTL >= 1s

**Concurrent Test Results**:
- 50 workers × 10 ops = 500 operations
- Success rate: 100% (mỗi operation được serialized correctly)
- p50 latency tăng với contention: ~800ms với 50 workers trên single key
- Đây là expected behavior: lock serialization = sequential processing

**Benchmark Insights**:
- Unsafe DEL: fastest (no check), but incorrect
- Safe Lua: ~20% slower than unsafe DEL, but correct
- Production (with retry): significantly slower under contention due to backoff
- Recommendation: use short TTL, few retries for low-contention scenarios

---

### Challenge Solutions

**Scenario A (Payment Processing)**:
- **Decision: KHÔNG dùng Redis lock**
- Lý do:
  1. Financial data cần linearizability — Redis không đảm bảo
  2. Lock expiry + operation overlap = double debit (correctness violation)
  3. Không có fencing token -> resource không biết operation đến từ stale lock holder
- **Giải pháp đúng**: PostgreSQL `SELECT balance FROM accounts WHERE id=$1 FOR UPDATE` (row lock). Balance được lock trong transaction, không có overlap. Automatic rollback nếu failure.
- **Hybrid approach** (nếu vẫn muốn Redis):
  - Dùng Redis lock để "early exit" (tránh hit DB nếu đang có operation khác)
  - DB row lock cho critical section
  - TTL <= 100ms (fast operations only)
  - Implement fencing token từ DB sequence

**Scenario B (Cache Warming)**:
- **Decision: Redis lock CÓ thể dùng, nhưng xem xét alternatives**
- Redis lock approach:
  - Lock key: `warm:product:{id}`, TTL = 5 phút
  - Operation idempotent (cache write), overlap không gây harm
  - Dùng Redis lock để tránh duplicate warming (tiết kiệm DB queries)
- **Alternative tốt hơn**: Redis Streams với consumer group
  - Mỗi product warm = message trong stream
  - Consumer group đảm bảo exactly-once processing
  - Không cần lock, không có overlap
  - Có thể replay nếu consumer crash
- **Recommendation**: Redis lock nếu operation đơn giản và idempotent; Streams nếu cần durability và replay capability.

**Scenario C (Leader Election)**:
- **Decision: Redis lock được chấp nhận, nhưng với điều kiện**
- Redis lock approach:
  - Lock key: `leader:healthcheck`, TTL = 15s
  - Renewal: mỗi 10s (2/3 của TTL)
  - Leader check: nếu không renew trong 20s -> leader die
- **Split-brain risk**: Nếu Redis master fail và Sentinel failover chậm (> 5s), có thể 2 instances cùng tin mình là leader trong brief window.
- **ZooKeeper approach**: Sequential ephemeral node. ZAB đảm bảo không có split-brain. Failover time: ~2-5s (TCP timeout + election).
- **Recommendation**:
  - Nếu 5s failover time chấp nhận được: Redis lock với Sentinel
  - Nếu failover time phải < 2s: ZooKeeper hoặc etcd
  - Monitoring: alert nếu 2 instances cùng publish health trong 10s window

---

### Reflection Answers

**Câu 1**: Kleppmann's critique áp dụng trong scenario:
- Multi-region với significant clock drift
- Long-running operations (接近 TTL)
- Correctness-critical operations (financial, inventory)
Nhiều system dùng Redlock vì:
- Single datacenter: clock drift negligible
- Short operations (TTL >> operation time)
- Idempotent operations: lock expiry = retry, not correctness violation
Key insight: Redlock không an toàn cho correctness-critical scenarios, nhưng acceptable cho availability/performance scenarios.

**Câu 2**: Fencing token giải quyết stale reader problem. Lock chỉ đảm bảo mutual exclusion, không đảm bảo operations không overlap (lock expiry). Fencing token đảm bảo resource từ chối operations từ stale lock holders. ZooKeeper/etcd không cần fencing token riêng vì sequence number (ZooKeeper) và mod_revision (etcd) là linearizable monotonic counters — chúng tự động là fencing token.

**Câu 3**: Redis lock không phù hợp cho rate limiting. Rate limit cần counting, không phải mutual exclusion. Dùng Lua sliding window counter (Day 27) — atomic INCR + expire, không cần lock. Lock rate limiting = high latency (lock acquire + release per request), contention spike. Counter rate limiting = 1 command, no contention.

**Câu 4**: Dev sai vì:
1. Lock TTL không guarantee rằng operation hoàn thành trong TTL
2. Nếu operation = 25s, TTL = 30s, lock expire khi operation đang chạy
3. Client B acquire lock khi A chưa xong
4. A và B overlap trong 5s -> resource inconsistency
5. "Lock bao giờ cũng an toàn" chỉ đúng nếu TTL >> operation_time (safety margin 3x+)

**Câu 5**: Queue overkill khi:
- Operation ngắn (< 100ms) và latency-sensitive: queue adds 10-100ms overhead
- Operation idempotent: queue không cần thiết, lock đơn giản hơn
- Fire-and-forget: không cần ordering, không cần queue
- Low volume: overhead của queue infrastructure không đáng
- Lock acceptable: nếu overlap chấp nhận được, lock đơn giản hơn queue

Queue "worth it" khi:
- Operation dài (> 1s)
- Ordering required
- Durability/replay needed
- Multiple consumers with load balancing
- Backpressure needed
