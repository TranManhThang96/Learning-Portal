# Day 21: Failover, Client Retry & Chaos Lab — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: Go (luân phiên với Day 20 TypeScript)
**Redis**: 7.2+ với Sentinel
**Tools**: Docker Compose, Pumba/tc netem, Toxiproxy, vegeta

---

## 0. Setup

```bash
# Directory structure
mkdir -p day21-chaos && cd day21-chaos

# Clone docker-compose template
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    ports: ["6379:6379"]
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --enable-debug-command yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-replica:
    image: redis:7.2-alpine
    container_name: redis-replica
    ports: ["6380:6379"]
    command: >
      redis-server
      --replicaof redis-master 6379
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    ports: ["26379:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-1
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
      --sentinel failover-timeout mymaster 18000
      --sentinel parallel-syncs mymaster 1
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    ports: ["26380:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-2
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
      --sentinel failover-timeout mymaster 18000
      --sentinel parallel-syncs mymaster 1
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    ports: ["26381:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-3
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
      --sentinel failover-timeout mymaster 18000
      --sentinel parallel-syncs mymaster 1
    depends_on:
      redis-master:
        condition: service_healthy

  # Toxiproxy for programmatic chaos
  toxiproxy:
    image: shopify/toxiproxy:latest
    container_name: toxiproxy
    ports: ["8474:8474", "16379:6379"]
    command: ""
EOF

docker-compose up -d
sleep 5

# Verify setup
docker exec redis-master redis-cli PING
docker exec redis-replica redis-cli PING
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Simulate Master Hang (DEBUG SLEEP) and Crash (docker kill)

```bash
# Terminal 1: Watch replication status continuously
watch -n 1 "docker exec redis-master redis-cli INFO replication | grep -E 'role|master_link'"

# Terminal 2: Seed some data
docker exec redis-master redis-cli SET test:key "initial-value"
docker exec redis-master redis-cli SET test:counter 0

# Terminal 3: Simulate a hang using DEBUG SLEEP (requires --enable-debug-command yes in lab compose)
# This pauses the Redis process for 5 seconds — mimics a hang
docker exec redis-master redis-cli DEBUG SLEEP 5

# Observe: During DEBUG SLEEP, all clients timeout
# After recovery, check value still intact
docker exec redis-master redis-cli GET test:key
# Expected: "initial-value" (data persisted)

# Terminal 4: Monitor client connections during hang
docker exec redis-master redis-cli CLIENT LIST
# Expected: clients in blocked state
```

Hard crash để Sentinel thật sự failover:

```bash
docker kill redis-master
sleep 10
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
# Expected: redis-replica 6379 hoặc IP/container mới của promoted replica
```

### 1.2. CLIENT KILL — Simulate Connection Drop

```bash
# Get current client connections
docker exec redis-master redis-cli CLIENT LIST

# Identify client connection ID
# Format: id=N addr=... fd=... cmd=...

# Kill specific client connection (simulate network drop)
# Replace <client-id> with actual ID from above
docker exec redis-master redis-cli CLIENT KILL ID <client-id>

# Verify: reconnect happens automatically if using persistent client
# Check connected clients count
docker exec redis-master redis-cli CLIENT LIST | wc -l
```

### 1.3. Force Failover (SENTINEL Manual)

```bash
# Check current master
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster

# Initiate manual failover (simulate Sentinel election)
docker exec sentinel-1 redis-cli -p 26379 SENTINEL failover mymaster

# Observe: replica gets promoted
sleep 3
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster

# Check which instance is now master
docker exec redis-master redis-cli INFO replication | grep role
docker exec redis-replica redis-cli INFO replication | grep role

# Verify data still accessible
docker exec redis-master redis-cli GET test:key
```

### 1.4. Observe Replica Lag Under Load

```bash
# Terminal 1: Generate heavy write load
docker exec redis-master redis-cli DEBUG LOADDUMP /dev/null &
# Alternative: use redis-benchmark
docker exec redis-master redis-benchmark -t SET -n 50000 -r 100000 &

# Terminal 2: Monitor replica lag
while true; do
  echo "=== $(date '+%H:%M:%S') ==="
  docker exec redis-replica redis-cli INFO replication | grep -E 'lag|offset'
  sleep 1
done

# Stop benchmark
pkill -f "redis-benchmark"

# Observe: lag increases during heavy write, decreases after
```

### 1.5. Check Sentinel Events Pub/Sub

```bash
# Subscribe to Sentinel events (run in background)
docker exec sentinel-1 redis-cli -p 26379 PSUBSCRIBE '*'

# In another terminal, trigger failover
docker exec sentinel-1 redis-cli -p 26379 SENTINEL failover mymaster

# Observe Pub/Sub messages:
# +sdown master mymaster <ip:port> <state>
# +odown master mymaster <ip:port> <state>
# +new-addr master mymaster <new-ip:port>
# +switch-master mymaster <old-ip:port> <old-port> <new-ip:port> <new-port>
```

### 1.6. Cleanup Warm-up Data

```bash
docker exec redis-master redis-cli DEL test:key test:counter
```

---

## 2. Hands-on Lab: Chaos Testing Pipeline (60-70 phút)

**Scenario**: Go service đọc/ghi product catalog từ Redis. Implement retry + jitter + circuit breaker. Chạy load test (vegeta), kill master, observe error rate + p99 latency + recovery time.

### 2.1. Project Setup

```bash
mkdir -p day21/src
cd day21

# Initialize Go module
go mod init day21-chaos

# Install dependencies
go get github.com/redis/go-redis/v9@latest
go get github.com/mahadevbilagi/redis/redis@latest
go get github.com/tsenart/vegeta@latest
```

### 2.2. Docker Compose with Toxiproxy

```yaml
# docker-compose.yml (updated with toxiproxy)
version: "3.8"
services:
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    ports: ["6379:6379"]
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-replica:
    image: redis:7.2-alpine
    container_name: redis-replica
    ports: ["6380:6379"]
    command: >
      redis-server
      --replicaof redis-master 6379
      --appendonly yes
      --appendfsync everysec
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    ports: ["26379:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-1
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
      --sentinel failover-timeout mymaster 18000
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    ports: ["26380:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-2
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
    depends_on:
      redis-master:
        condition: service_healthy

  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    ports: ["26381:26379"]
    command: >
      redis-sentinel
      --sentinel announce-ip sentinel-3
      --sentinel announce-port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 3000
    depends_on:
      redis-master:
        condition: service_healthy

  toxiproxy:
    image: shopify/toxiproxy:latest
    container_name: toxiproxy
    ports: ["8474:8474", "16379:6379"]
```

### 2.3. Starter Code

```go
// src/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	_ "net/http/pprof"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

// --- Configuration ---
const (
	redisAddr       = "localhost:6379"
	loadTestDur     = 30 * time.Second
	loadTestRate    = 100 // requests per second
	targetEndpoint  = "http://localhost:8080/api/products/"
	numKeys         = 1000
)

// --- Metrics ---
var (
	totalRequests   int64
	errorCount     int64
	successCount   int64
	timeoutCount   int64
	latencies       []time.Duration
	latenciesMu     sync.Mutex
	circuitOpen    int64 // 1 = open, 0 = closed
)

// --- Circuit Breaker ---
type CircuitBreaker struct {
	failures         int64
	threshold        int64
	resetTimeout     time.Duration
	lastFailureTime  time.Time
	mu               sync.Mutex
	state            string // "CLOSED", "OPEN", "HALF_OPEN"
}

func NewCircuitBreaker(threshold int64, resetTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		threshold:   threshold,
		resetTimeout: resetTimeout,
		state:      "CLOSED",
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	atomic.AddInt64(&cb.failures, 1)
	cb.lastFailureTime = time.Now()

	if atomic.LoadInt64(&cb.failures) >= cb.threshold {
		if cb.state != "OPEN" {
			cb.state = "OPEN"
			log.Printf("[CircuitBreaker] OPEN — too many failures")
		}
	}
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	atomic.StoreInt64(&cb.failures, 0)
	if cb.state == "HALF_OPEN" {
		cb.state = "CLOSED"
		log.Printf("[CircuitBreaker] CLOSED — recovered")
	} else if cb.state == "CLOSED" {
		f := atomic.LoadInt64(&cb.failures)
		if f > 0 {
			atomic.StoreInt64(&cb.failures, f-1)
		}
	}
}

func (cb *CircuitBreaker) IsOpen() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if cb.state == "OPEN" {
		if time.Since(cb.lastFailureTime) > cb.resetTimeout {
			cb.state = "HALF_OPEN"
			log.Printf("[CircuitBreaker] HALF_OPEN — testing recovery")
			return false
		}
		return true
	}
	return false
}

func (cb *CircuitBreaker) GetState() string {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	return cb.state
}

// --- Full Jitter Backoff ---
func backoffWithJitter(attempt int) time.Duration {
	base := 100 * time.Millisecond
	maxDelay := 10 * time.Second

	exp := base * time.Duration(1<<uint(attempt))
	jitter := time.Duration(rand.Int63n(int64(exp)))
	if jitter > maxDelay {
		jitter = maxDelay
	}
	return jitter
}

// --- Redis Client with Sentinel ---
func newRedisClient() *redis.Client {
	return redis.NewFailoverClient(&redis.FailoverOptions{
		MasterName:    "mymaster",
		SentinelAddrs:  []string{"localhost:26379", "localhost:26380", "localhost:26381"},
		ReadTimeout:    5 * time.Second,
		WriteTimeout:   5 * time.Second,
		DialTimeout:    5 * time.Second,
		PoolSize:      50,
		MinIdleConns:  10,
		PoolTimeout:   10 * time.Second,
		RouteByLatency: true, // Prefer faster instance
	})
}

// --- Retry Loop with Jitter ---
func doWithRetry(ctx context.Context, rdb *redis.Client, key string, cb *CircuitBreaker) (string, error) {
	const maxRetries = 3

	for attempt := 0; attempt < maxRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return "", err
		}

		if cb.IsOpen() {
			return "", fmt.Errorf("circuit breaker open")
		}

		start := time.Now()
		val, err := rdb.Get(ctx, key).Result()
		latency := time.Since(start)

		latenciesMu.Lock()
		latencies = append(latencies, latency)
		latenciesMu.Unlock()

		if err == nil {
			cb.RecordSuccess()
			return val, nil
		}

		if err == redis.Nil {
			cb.RecordSuccess()
			return "", nil
		}

		log.Printf("[Attempt %d] Redis error for %s: %v (latency: %v)", attempt, key, err, latency)

		if attempt < maxRetries-1 {
			delay := backoffWithJitter(attempt)
			log.Printf("[Retry] Waiting %v before retry %d", delay, attempt+1)
			select {
			case <-time.After(delay):
			case <-ctx.Done():
				return "", ctx.Err()
			}
		}

		cb.RecordFailure()
	}

	return "", fmt.Errorf("max retries exceeded for key %s", key)
}

// --- Seed Data ---
func seedData(rdb *redis.Client) {
	ctx := context.Background()
	log.Printf("Seeding %d product keys...", numKeys)

	for i := 0; i < numKeys; i++ {
		key := fmt.Sprintf("product:%06d", i)
		value := map[string]interface{}{
			"id":    i,
			"name":  fmt.Sprintf("Product %d", i),
			"price": 1000 + rand.Intn(9000),
			"stock": rand.Intn(100),
		}
		data, _ := json.Marshal(value)
		if err := rdb.Set(ctx, key, string(data), 0).Err(); err != nil {
			log.Printf("Seed error for key %s: %v", key, err)
		}
	}
	log.Printf("Seeding complete")
}

// --- HTTP Handler ---
func handleGetProduct(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	rdb := newRedisClient()
	cb := NewCircuitBreaker(5, 30*time.Second)

	productID := r.URL.Path[len("/api/products/"):]
	key := fmt.Sprintf("product:%s", productID)

	start := time.Now()
	val, err := doWithRetry(ctx, rdb, key, cb)
	latency := time.Since(start)

	atomic.AddInt64(&totalRequests, 1)

	if err != nil {
		atomic.AddInt64(&errorCount, 1)
		if latency > 4*time.Second {
			atomic.AddInt64(&timeoutCount, 1)
		}
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]string{
			"error":       err.Error(),
			"circuit":     cb.GetState(),
			"latency_ms":  fmt.Sprintf("%d", latency.Milliseconds()),
		})
		return
	}

	atomic.AddInt64(&successCount, 1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(val))
}

// --- Metrics Handler ---
func handleMetrics(w http.ResponseWriter, r *http.Request) {
	latenciesMu.Lock()
	defer latenciesMu.Unlock()

	var p50, p95, p99 time.Duration = 0, 0, 0
	if len(latencies) > 0 {
		sorted := make([]time.Duration, len(latencies))
		copy(sorted, latencies)
		// Simple sort (inefficient for large N but fine for demo)
		for i := 0; i < len(sorted)-1; i++ {
			for j := i + 1; j < len(sorted); j++ {
				if sorted[j] < sorted[i] {
					sorted[i], sorted[j] = sorted[j], sorted[i]
				}
			}
		}
		n := len(sorted)
		p50 = sorted[n*50/100]
		p95 = sorted[n*95/100]
		p99 = sorted[n*99/100]
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"total_requests": atomic.LoadInt64(&totalRequests),
		"success_count": atomic.LoadInt64(&successCount),
		"error_count":   atomic.LoadInt64(&errorCount),
		"timeout_count": atomic.LoadInt64(&timeoutCount),
		"error_rate_pct": func() float64 {
			t := atomic.LoadInt64(&totalRequests)
			if t == 0 {
				return 0
			}
			return float64(atomic.LoadInt64(&errorCount)*100) / float64(t)
		}(),
		"latency_p50_ms": p50.Milliseconds(),
		"latency_p95_ms": p95.Milliseconds(),
		"latency_p99_ms": p99.Milliseconds(),
	})
}

// --- Load Test ---
func runLoadTest(target string, duration time.Duration, rate int) {
	log.Printf("Starting load test: %s, duration=%v, rate=%d/s", target, duration, rate)

	args := []string{
		"attack",
		"-rate=" + fmt.Sprintf("%d", rate),
		"-duration=" + duration.String(),
		"-targets=" + target,
		"-output=" + "results.bin",
	}

	cmd := exec.Command("vegeta", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		log.Printf("Vegeta error: %v", err)
	}
}

// Print results
func printResults() {
	cmd := exec.Command("vegeta", "report", "-type=json", "results.bin")
	cmd.Stdout = os.Stdout
	cmd.Run()
}
```

**HINT**: Cần thêm `import "os/exec"` ở trên. Thêm vào sau dòng `import`.

### 2.4. Running the Lab

**Terminal 1 — Setup + Start Server:**
```bash
docker-compose up -d
sleep 8  # Wait for Sentinel to elect master

# Seed data
go run src/main.go -seed
# Expected: "Seeding 1000 product keys..."

# Start HTTP server
go run src/main.go -server
# Server listening on :8080
```

**Terminal 2 — Load Test (before chaos):**
```bash
# Baseline: Run load test for 30 seconds
vegeta attack -rate=50 -duration=30s \
  -targets=<(echo "GET http://localhost:8080/api/products/000001") \
  -output=baseline.bin

vegeta report -type=json baseline.bin
# Expected: error rate ~0%, p99 < 50ms
```

**Terminal 3 — Kill Master (CHAOS):**
```bash
# While load test is running, kill master
docker kill redis-master

# Observe in Terminal 1:
# - Error count increases
# - Circuit breaker state changes
# - Latency spikes

# Wait for Sentinel to elect new master (Sentinel: down-after=3000ms, failover-timeout=18000ms)
# Expected recovery: 5-15 seconds

# Verify new master
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
docker exec redis-replica redis-cli INFO replication | grep role
```

**Terminal 4 — Load Test (during/after chaos):**
```bash
# Run during chaos
vegeta attack -rate=50 -duration=60s \
  -targets=<(echo "GET http://localhost:8080/api/products/000001") \
  -output=chaos.bin

# Get metrics
curl http://localhost:8080/metrics | jq .
```

### 2.5. Expected Output

**During Failover:**
```
[Attempt 0] Redis error for product:000001: connection refused (latency: 2ms)
[Retry] Waiting 127ms before retry 1
[Attempt 1] Redis error for product:000001: connection refused (latency: 1ms)
[Retry] Waiting 203ms before retry 2
[Attempt 2] Redis error for product:000001: max retries exceeded
[CircuitBreaker] OPEN — too many failures
Error rate: 30-50% during failover window
```

**After Recovery:**
```
[CircuitBreaker] HALF_OPEN — testing recovery
[Attempt 0] Redis error for product:000001: connection refused (latency: 1ms)
[CircuitBreaker] OPEN
[CircuitBreaker] HALF_OPEN — testing recovery
[CircuitBreaker] CLOSED — recovered
Success rate back to 100% within 10-20 seconds of master election
```

**Metrics comparison:**
```
| Metric          | Baseline | During Chaos | After Recovery |
|-----------------|----------|-------------|----------------|
| Error rate      | 0%       | 30-50%      | 0%             |
| p50 latency     | 2ms      | 50-200ms    | 2ms            |
| p99 latency     | 15ms     | 5000ms      | 20ms           |
| Recovery time   | N/A      | 5-15s       | N/A            |
```

### 2.6. Verification

```bash
# Check Sentinel status
docker exec sentinel-1 redis-cli -p 26379 SENTINEL master mymaster
# Verify: flags should not contain "s_down" or "o_down"

# Check replica sync
docker exec sentinel-1 redis-cli -p 26379 SENTINEL slaves mymaster

# Check data integrity (no data loss expected with everysec fsync)
docker exec redis-replica redis-cli DBSIZE
docker exec redis-master redis-cli DBSIZE
# Should be similar (some lag is normal)

# Check circuit breaker state via metrics endpoint
curl http://localhost:8080/metrics | jq .error_rate_pct
```

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Network Partition Simulation (3 Phases)

**Objective**: Simulate 3-phase network partition using Toxiproxy, tune timeout/retry, measure impact.

**Setup**: App connects through Toxiproxy (localhost:16379 → localhost:6379).

```bash
# Terminal 1: Create Toxiproxy proxy for Redis
toxiproxy-cli create redis --listen localhost:16379 --upstream localhost:6379

# Verify: app connecting through toxiproxy still works
curl http://localhost:8080/api/products/000001
# Should work normally
```

**Phase A — Connectivity Loss (10s)**:
```bash
# Add 100% timeout toxic (full partition)
toxiproxy-cli toxic add redis --toxicName partition \
  --type timeout --attribute timeout=1

# Observe: all requests fail immediately (connection refused)
# Duration: 10 seconds
# Expected: circuit breaker opens after 5 failures
```

**Phase B — Slow Link (30s)**:
```bash
# Remove partition
toxiproxy-cli toxic remove redis --toxicName partition

# Add 500ms latency toxic
toxiproxy-cli toxic add redis --toxicName latency \
  --type latency --attribute latency=500 --attribute jitter=50

# Observe: requests succeed but latency increases
# But: if readTimeout < 500ms + processing, many false timeouts
# Duration: 30 seconds
```

**Phase C — Restore**:
```bash
# Remove latency
toxiproxy-cli toxic remove redis --toxicName latency

# Observe: latency returns to baseline
# Measure recovery time (time until 100% success rate)
```

**Tasks**:
1. Tune `readTimeout` in your Go code so that Phase B does NOT cause mass timeouts
2. Tune retry strategy so Phase A recovery is fast
3. Record metrics for each phase (error rate, p99 latency)
4. Document: what timeout value prevents false failures in 500ms latency scenario?

### 3.2. Write Postmortem

Using the template in `document.md`, write a postmortem for the chaos test you just ran. Fill in:

- Timeline: when did failover start, when was it detected, when did it recover
- 5 Whys: why did the request fail?
- Metrics: error rate, p99 latency, recovery time
- Action items: what would you change in production based on this lab?

**Deliverable**: A filled postmortem in `postmortem.md`.

### 3.3. Tune Timeout for Different Scenarios

Given these scenarios, recommend the correct timeout values:

| Scenario | Infrastructure | Expected Failover Time | Recommended Timeout |
|---|---|---|---|
| Self-hosted Sentinel (fast network) | 3 VMs, same datacenter | 3-5s | ? |
| Self-hosted Sentinel (cross-AZ) | 3 VMs, different AZ | 10-20s | ? |
| AWS ElastiCache | Multi-AZ managed | 15-45s | ? |
| Redis Cluster | 6 nodes, 3 AZ | 10-30s | ? |
| Network partition (Sentinel split) | 3 Sentinel, 2-2 split | 30-60s | ? |

**Task**: For each scenario, also specify:
- `maxRetriesPerRequest` (1 or 2?)
- Retry strategy (jitter formula)
- Circuit breaker threshold (how many failures before opening?)
- Whether to use read from replica during failover

---

## 4. Reflection Questions (Open-ended)

1. **Retry budget**: Bạn có 1 triệu requests/giờ, error budget = 0.1% (1000 errors). Mỗi failover gây ra 2% error rate trong 30 giây. Bạn có thể chịu đựng bao nhiêu failover mỗi ngày trước khi vượt budget? Điều này có nghĩa gì cho việc thiết kế retry strategy?

2. **Khi nào fail-fast hơn retry?**: Với payment idempotency key, bạn KHÔNG bao giờ retry tự động. Nhưng với API response cache (stale-ok), bạn retry với jitter. Giải thích: tại sao cùng là Redis failure nhưng retry policy lại khác nhau?

3. **DNS TTL decision**: DNS TTL = 15s có nghĩa client refresh mỗi 15 giây → overhead DNS resolution. DNS TTL = 3600s có nghĩa client cached lâu → stale endpoint. Đề xuất TTL phù hợp cho: (a) Redis master endpoint, (b) Redis Cluster seed nodes, (c) read replica endpoint. Tại sao khác nhau?

4. **Circuit breaker vs Retry**: Cả hai đều xử lý failures. Khi nào dùng circuit breaker thay vì retry? Khi nào dùng cả hai? Liệu có scenario nào mà dùng cả hai gây ra vấn đề không?

5. **Graceful degradation vs hard failure**: Một số team chọn "fail-closed" (reject requests khi Redis down), số khác chọn "fail-open" (serve stale/default). Đánh giá trade-off cho: (a) rate limiting service, (b) payment processing, (c) user session, (d) product catalog. Có use case nào mà fail-open nguy hiểm hơn fail-closed không?

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 DEBUG SLEEP behavior**:
```
DEBUG SLEEP N: Pauses Redis main thread for N seconds
- All clients blocked during this time
- Data intact after recovery (persistence: AOF/RDB)
- Use for: simulating slow Redis (NOT crash)
- For crash simulation: docker kill or pkill -9 redis-server
```

**1.3 Manual failover**:
```bash
# Check before: master should be redis-master
# After failover: replica promoted, redis-master may be down or demoted
# Note: docker-compose restart may be needed to recreate original master
```

---

### Lab Solutions

**TODO 1: Timeout tuning for 500ms latency scenario**

Phase B (500ms latency) causes false timeouts if readTimeout < 500ms + processing time.

```go
// Recommended: readTimeout = 3 × slow_latency + p99_processing_time
// For 500ms slow link + 50ms processing + 100ms GC variance:
// readTimeout = 3 × 500ms + 150ms = 1650ms (round up to 2s)
// But also: timeout must > failover time
// Therefore: readTimeout = max(2s, 15s) = 15s for ElastiCache

// For this lab (local Sentinel, 3-5s failover):
ReadTimeout:  10 * time.Second  // 10s > 3× expected latency
WriteTimeout: 10 * time.Second
```

**TODO 2: Circuit breaker thresholds**

```go
// For load test with rate=50/s (1 request every 20ms):
// Threshold: 5 failures in 30s = 5 failures / (50 req/s × 30s) = 0.3%
// This trips circuit early → too aggressive

// Better: 20 failures in 10s = 20 failures / 500 total = 4%
// Still trips fast but not on 1-2 transient errors

cb := NewCircuitBreaker(
    threshold:    20,          // Trip after 20 failures
    resetTimeout: 30 * time.Second, // Wait 30s before trying again
)
```

**TODO 3: Phase-by-phase metrics interpretation**

| Phase | Error Type | Root Cause | Mitigation |
|---|---|---|---|
| A: Partition | All fail (connection refused) | TCP-level failure | Jitter prevents storm |
| B: 500ms latency | False timeouts if timeout too short | readTimeout < network latency | Tune readTimeout ≥ 2s |
| C: Recovery | Sporadic errors | Stale endpoints reconnecting | Subscribe to +switch-master |

---

### Challenge Solutions

**3.1 Timeout Recommendations Table**:

| Scenario | Infrastructure | Failover Time | Timeout | Max Retries | Circuit Threshold |
|---|---|---|---|---|---|
| Self-hosted, same DC | 3 VMs | 3-5s | 15s | 2 | 10 in 10s |
| Self-hosted, cross-AZ | 3 VMs, diff AZ | 10-20s | 30s | 1 | 5 in 10s |
| AWS ElastiCache | Multi-AZ managed | 15-45s | 60s | 1 | 10 in 30s |
| Redis Cluster | 6 nodes, 3 AZ | 10-30s | 45s | 1 | 5 in 15s |
| Network partition | 2-2 Sentinel split | 30-60s | 90s | 1 | 3 in 30s |

**Key insight**: **Timeout must be > 3× failover time** (not 1×, not 2×). Rule of thumb: never configure timeout < 10s for any Redis HA setup.

**3.3 Reflection Answers**:

**Q1 — Error budget math**:
```
Error budget: 1000 errors/hour
Per failover (30s, 2% error rate):
  - Requests in 30s: 1M / 3600 × 30 = ~8,333 requests
  - Errors during failover: 8,333 × 2% = ~167 errors
  - Failovers allowed: 1000 / 167 ≈ 6 per day
→ With proper retry (reducing error rate to 0.5%):
  - Errors per failover: 8,333 × 0.5% = ~42 errors
  - Failovers allowed: 1000 / 42 ≈ 24 per day
→ 4× improvement in failover tolerance
```

**Q2 — Why retry differs by use case**:
```
Payment idempotency: NEVER retry automatically
  → Same request → double payment
  → Client decides when to retry (after user confirmation)
  → Timeout: 30s, fail immediately, log for manual review

API cache (stale-ok): Retry with jitter
  → Same request → same cached response (idempotent GET)
  → Serve stale is acceptable
  → Timeout: 2-5s, 2 retries with jitter
```

**Q3 — DNS TTL recommendations**:
```
Redis master endpoint: TTL = 15s
  → Changes on every failover (may be daily)
  → Short TTL ensures fast recovery

Redis Cluster seed nodes: TTL = 60s
  → Rarely change (node additions/removals are rare)
  → Longer TTL reduces DNS query overhead

Read replica endpoint: TTL = 5s (or use service discovery)
  → Can change on failover, promotion
  → But: replica reads are best-effort, brief staleness OK
  → Shorter TTL than master (failover is less critical)
```

---

### Key Takeaways

1. **Timeout > 3× failover time** is the most critical setting — everything else is secondary.
2. **Jitter prevents retry storms** — never use fixed delay retry in production with 100+ clients.
3. **Circuit breaker protects the system** — but tune thresholds before production, not after incident.
4. **Subscribe to Sentinel events** — polling for master IP = 1 hour of failures after failover.
5. **Test chaos in staging** — the first failover in production is not the time to discover your timeout is too short.
6. **DNS TTL matters** — 3600s TTL = 1 hour of failures. Use 15s or subscribe to events.
7. **Graceful degradation is a feature** — serve stale cache > serve error. But design for it before you need it.
