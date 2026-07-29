# Day 19: Replication Internals — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: Go (luân phiên với Day 18 TypeScript)
**Redis**: 7.2+

---

## 0. Setup

```bash
# Verify Docker and docker-compose
docker --version
docker compose version

# Start 1 master + 2 replicas
cd day-19-replication-internals
docker compose up -d

# Verify all containers are up
docker compose ps

# Verify replication is established
redis-cli -h localhost -p 6379 INFO replication | grep connected_slaves
# Expected: connected_slaves:2

# Verify replica status
redis-cli -h localhost -p 6380 INFO replication | grep master_link_status
# Expected: master_link_status:up

# Verify replication lag
redis-cli -h localhost -p 6379 INFO replication | grep master_repl_offset
redis-cli -h localhost -p 6380 INFO replication | grep slave_repl_offset
# They should be equal or very close
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. REPLICAOF — Setup và Teardown

```bash
# Step 1: Kiểm tra role hiện tại (trên standalone redis)
redis-cli ROLE
# Expected: master

# Step 2: Promote một standalone Redis thành replica
# (Đã làm qua docker-compose, nhưng kiểm tra lại)
redis-cli -h localhost -p 6380 ROLE
# Expected: slave 127.0.0.1 6379

# Step 3: Disconnect replica (stop replication)
redis-cli -h localhost -p 6380 REPLICAOF NO ONE
redis-cli -h localhost -p 6380 ROLE
# Expected: master

# Step 4: Reconnect (khôi phục replication)
redis-cli -h localhost -p 6380 REPLICAOF localhost 6379
sleep 2
redis-cli -h localhost -p 6380 ROLE
# Expected: slave localhost 6379

# Step 5: Verify replication is restored
redis-cli -h localhost -p 6380 INFO replication | grep master_link_status
# Expected: master_link_status:up
```

### 1.2. INFO Replication — Đọc và Hiểu

```bash
# Master INFO
redis-cli -h localhost -p 6379 INFO replication

# Chú ý các fields sau:
# - role: master
# - connected_slaves: 2
# - master_repl_offset: <value>
# - repl_backlog_active: 1
# - repl_backlog_size: 104857600 (100MB)
# - repl_backlog_histlen: <bytes currently in use>
# - repl_backlog_first_size: <size of first chunk>

# Replica INFO
redis-cli -h localhost -p 6380 INFO replication

# Chú ý các fields sau:
# - role: slave
# - master_host: 127.0.0.1
# - master_port: 6379
# - master_link_status: up|down
# - slave_repl_offset: <replica's current offset>
# - master_repl_offset: <master's current offset>
# - master_last_io_seconds_ago: <seconds since last IO from master>
# - Offset lag bytes phải tự tính: master_repl_offset - slave_repl_offset

# Quan sát lag thay đổi khi write nhiều
# Terminal 1: Monitor
redis-cli -h localhost -p 6380 INFO replication | grep -E "master_repl_offset|slave_repl_offset|lag"

# Terminal 2: Write burst
for i in $(seq 1 100); do
  redis-cli -h localhost -p 6379 SET warm:key:$i "value$i"
done

# Terminal 1: Kiểm tra lại offset
redis-cli -h localhost -p 6380 INFO replication | grep -E "master_repl_offset|slave_repl_offset|lag"
```

**Questions**:
- `master_repl_offset - slave_repl_offset` = lag bytes. Convert sang giây (ước tính)?
- `repl_backlog_histlen` thay đổi thế nào sau write burst?

### 1.3. PSYNC — Observe Full Sync vs Partial Sync

```bash
# Bước 1: Quan sát partial sync (replica đang connected)
# Replica đã sync → partial sync nếu disconnect ngắn

# Bước 2: Simulate full sync
# Disconnect replica trong thời gian ngắn (repl-backlog-size đủ lớn)
redis-cli -h localhost -p 6380 DEBUG SLEEP 2
# Trong khi đó master nhận writes
redis-cli -h localhost -p 6379 SET test:psync "1"
redis-cli -h localhost -p 6379 SET test:psync "2"
redis-cli -h localhost -p 6379 SET test:psync "3"

# Check: replica vẫn có test:psync = "3" → partial sync worked
redis-cli -h localhost -p 6380 GET test:psync
# Expected: 3

# Bước 3: Force full sync bằng cách reset replica hoàn toàn
redis-cli -h localhost -p 6380 DEBUG OBJECT ENCODING nonexistent-key
# Không có gì đặc biệt — để trigger full sync:
#   - Disconnect replica lâu để backlog overflow (không làm trong lab)
#   - Hoặc reset replica hoàn toàn

# Verify giá trị
redis-cli -h localhost -p 6381 GET test:psync
# Expected: 3 (partial sync)
```

### 1.4. Replica Read-Only Config

```bash
# Trên replica: đọc được
redis-cli -h localhost -p 6380 GET test:psync
# Expected: 3

# Trên replica: thử write → phải bị reject
redis-cli -h localhost -p 6380 SET test:psync "cannot-write"
# Expected: READONLY You can't write against a read only replica

# Kiểm tra config reject writes trên replica
redis-cli -h localhost -p 6380 CONFIG GET replica-read-only
# Expected: replica-read-only yes

# Tắt replica-read-only để thấy rủi ro divergence (lab only, không dùng production)
redis-cli -h localhost -p 6380 CONFIG SET replica-read-only no
redis-cli -h localhost -p 6380 SET test:psync "written"
# Now it works locally, but tạo divergence cho đến khi replica resync
redis-cli -h localhost -p 6380 GET test:psync
# Expected: written

# Khôi phục replica (replication sẽ broken vì replica diverged)
redis-cli -h localhost -p 6380 CONFIG SET replica-read-only yes
redis-cli -h localhost -p 6380 REPLICAOF localhost 6379
sleep 2
redis-cli -h localhost -p 6380 GET test:psync
# Value reset về 3 từ master (replica reloads from master)
```

### 1.5. Cleanup

```bash
# Cleanup test keys
redis-cli -h localhost -p 6379 KEYS "warm:*" | xargs -r redis-cli -h localhost -p 6379 DEL
redis-cli -h localhost -p 6379 DEL test:psync test:key:1
```

---

## 2. Hands-on Lab: Replication Monitor & Load Testing (60-70 phút)

**Scenario**: E-commerce service cần read scaling qua replicas. Bạn cần:
1. Setup 1 master + 2 replicas (đã có qua docker-compose)
2. Đo replica lag thực tế khi write load tăng
3. Implement read-from-replica với stale detection và fallback
4. Simulate replica disconnect và observe partial vs full sync

### 2.1. Project Setup

```bash
mkdir -p day19-replication && cd day19-replication
go mod init day19-replication
go get github.com/redis/go-redis/v9
```

### 2.2. Docker Compose

```yaml
# docker-compose.yml
version: "3.8"
services:
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    ports:
      - "6379:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-diskless-sync-delay 5
      --repl-backlog-size 104857600
      --repl-backlog-ttl 3600
      --repl-timeout 60
      --repl-disable-tcp-nodelay no
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    ports:
      - "6380:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replicaof redis-master 6379
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-backlog-size 104857600
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    depends_on:
      redis-master:
        condition: service_healthy

  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    ports:
      - "6381:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replicaof redis-master 6379
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-backlog-size 104857600
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    depends_on:
      redis-master:
        condition: service_healthy
```

### 2.3. Starter Code

```go
// main.go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

// ─── Configuration ────────────────────────────────────────────
const (
	masterAddr   = "localhost:6379"
	replica1Addr = "localhost:6380"
	replica2Addr = "localhost:6381"
)

var (
	masterClient   *redis.Client
	replicaClients []*redis.Client
)

// ─── Setup ───────────────────────────────────────────────────
func setup() {
	masterClient = redis.NewClient(&redis.Options{
		Addr:         masterAddr,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     100,
		MinIdleConns: 10,
	})

	replicaClients = []*redis.Client{
		redis.NewClient(&redis.Options{
			Addr:         replica1Addr,
			DialTimeout:  5 * time.Second,
			ReadTimeout:  3 * time.Second,
			WriteTimeout: 3 * time.Second,
			PoolSize:     100,
			MinIdleConns: 10,
		}),
		redis.NewClient(&redis.Options{
			Addr:         replica2Addr,
			DialTimeout:  5 * time.Second,
			ReadTimeout:  3 * time.Second,
			WriteTimeout: 3 * time.Second,
			PoolSize:     100,
			MinIdleConns: 10,
		}),
	}
}

// ─── TODO 1: Measure Replica Lag ──────────────────────────────
// Implement hàm đo lag giữa master và replica
// Trả về: lag bytes, lag milliseconds (ước tính)
// Gợi ý: Đọc master_repl_offset và slave_repl_offset từ INFO replication
func measureLag(ctx context.Context, replica *redis.Client) (lagBytes int64, lagMs float64, err error) {
	// TODO: Implement this
	// 1. Get master_repl_offset từ master
	// 2. Get slave_repl_offset từ replica
	// 3. Tính lag bytes = master_offset - slave_offset
	// 4. Ước tính lag ms: giả sử write rate 10K ops/sec, avg 500 bytes/cmd
	//    lag_seconds = lag_bytes / (write_rate * avg_cmd_size)
	//    lag_ms = lag_seconds * 1000
	panic("TODO: Implement measureLag")
}

// ─── TODO 2: Write Load Generator ─────────────────────────────
// Viết hàm tạo write load lên master
// Tham số: count (số lượng writes), concurrency
// Trả về: thời gian thực hiện
func generateWriteLoad(ctx context.Context, count, concurrency int) (duration time.Duration, err error) {
	// TODO: Implement this
	// 1. Dùng goroutine + channel để write concurrently
	// 2. Mỗi write: SET key value (key = "load:{index}", value = random string)
	// 3. Ghi log: tổng writes, thời gian, writes/sec
	// 4. Trả về total duration
	panic("TODO: Implement generateWriteLoad")
}

// ─── TODO 3: Read from Replica with Sticky Routing ───────────
// Triển khai sticky routing: mỗi session luôn đọc từ cùng một replica
// Trả về giá trị và replica đã đọc
type ReadResult struct {
	Value  string
	Replica int
	LagMs  float64
}

func readWithStickyRouting(ctx context.Context, key, sessionID string) (*ReadResult, error) {
	// TODO: Implement this
	// 1. Hash sessionID để chọn replica (đảm bảo same session → same replica)
	// 2. Đo lag trước khi đọc
	// 3. Đọc từ replica đã chọn
	// 4. Trả về giá trị + replica index + lag
	panic("TODO: Implement readWithStickyRouting")
}

// ─── TODO 4: Simulate Replica Disconnect ─────────────────────
// Simulate replica disconnect trong N giây, sau đó reconnect
// Quan sát: partial sync hay full sync?
func simulateReplicaDisconnect(ctx context.Context, replicaIdx int, durationSec int) error {
	// TODO: Implement this
	// 1. Disconnect replica: REPLICAOF NO ONE
	// 2. Đợi durationSec giây
	// 3. Trong thời gian đó, write nhiều lên master (để test backlog)
	// 4. Reconnect: REPLICAOF masterAddr
	// 5. Kiểm tra: replica có data mới nhất không? Partial sync hay full sync?
	// 6. Ghi log kết quả
	panic("TODO: Implement simulateReplicaDisconnect")
}

// ─── TODO 5: Monitor Replication Continuously ─────────────────
// Chạy goroutine monitor replication lag
// Alert khi lag > threshold
func startLagMonitor(ctx context.Context, interval time.Duration, alertThresholdMs float64) {
	// TODO: Implement this
	// 1. Chạy vòng lặp với ticker
	// 2. Mỗi interval: đo lag tất cả replicas
	// 3. Log lag
	// 4. Nếu lag > alertThresholdMs: log ALERT
	// 5. Dùng context cancellation để stop
	panic("TODO: Implement startLagMonitor")
}

// ─── Experiments ──────────────────────────────────────────────
func experimentBasicLag() {
	ctx := context.Background()
	fmt.Println("\n=== Experiment 1: Basic Lag Measurement ===")

	for i, replica := range replicaClients {
		lagBytes, lagMs, err := measureLag(ctx, replica)
		if err != nil {
			log.Printf("Error measuring lag for replica-%d: %v", i+1, err)
			continue
		}
		fmt.Printf("Replica-%d: lag_bytes=%d lag_ms=%.2f\n", i+1, lagBytes, lagMs)
	}
}

func experimentWriteLoad() {
	ctx := context.Background()
	fmt.Println("\n=== Experiment 2: Write Load & Lag ===")

	// Clear test keys first
	for i := 0; i < 100; i++ {
		masterClient.Del(ctx, fmt.Sprintf("load:key:%d", i))
	}

	// Start lag monitor in background
	ctx, cancel := context.WithCancel(ctx)
	go startLagMonitor(ctx, 500*time.Millisecond, 100)

	// Generate write load
	count := 1000
	concurrency := 50
	duration, err := generateWriteLoad(ctx, count, concurrency)
	if err != nil {
		log.Printf("Write load error: %v", err)
	}
	fmt.Printf("Write load: %d writes in %v (%.0f writes/sec)\n",
		count, duration, float64(count)/duration.Seconds())

	// Wait and measure final lag
	time.Sleep(2 * time.Second)
	for i, replica := range replicaClients {
		lagBytes, lagMs, _ := measureLag(ctx, replica)
		fmt.Printf("After write: Replica-%d: lag_bytes=%d lag_ms=%.2f\n", i+1, lagBytes, lagMs)
	}

	cancel()
}

func experimentStickyRouting() {
	ctx := context.Background()
	fmt.Println("\n=== Experiment 3: Sticky Routing ===")

	// Seed some data
	for i := 1; i <= 10; i++ {
		masterClient.Set(ctx, fmt.Sprintf("product:%d", i), fmt.Sprintf("Product-%d", i), 0)
	}

	// Simulate 5 sessions reading the same key
	sessions := []string{"sess-001", "sess-002", "sess-003", "sess-004", "sess-005"}
	for _, sess := range sessions {
		for i := 1; i <= 5; i++ {
			result, err := readWithStickyRouting(ctx, fmt.Sprintf("product:%d", i), sess)
			if err != nil {
				log.Printf("Read error for %s: %v", sess, err)
				continue
			}
			fmt.Printf("Session %s (product:%d) -> Replica-%d (lag=%.2fms) value=%s\n",
				sess, i, result.Replica+1, result.LagMs, result.Value)
		}
	}
}

func experimentDisconnect() {
	ctx := context.Background()
	fmt.Println("\n=== Experiment 4: Replica Disconnect (5s) ===")
	fmt.Println("During disconnect, master will receive 100 writes")
	fmt.Println("After reconnect: check if partial sync was enough")

	err := simulateReplicaDisconnect(ctx, 0, 5)
	if err != nil {
		log.Printf("Disconnect simulation error: %v", err)
	}

	// Verify data
	val, _ := masterClient.Get(ctx, "disconnect:test").Result()
	replicaVal, _ := replicaClients[0].Get(ctx, "disconnect:test").Result()
	fmt.Printf("Master: disconnect:test = %s\n", val)
	fmt.Printf("Replica: disconnect:test = %s\n", replicaVal)
}

// ─── Helpers ─────────────────────────────────────────────────
func parseReplOffset(info string, field string) int64 {
	for _, line := range strings.Split(info, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, field+":") {
			val := strings.TrimPrefix(line, field+":")
			v, err := strconv.ParseInt(val, 10, 64)
			if err != nil {
				return 0
			}
			return v
		}
	}
	return 0
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run main.go <experiment>")
		fmt.Println("  experiment: 1=lag, 2=write-load, 3=sticky, 4=disconnect, all")
		os.Exit(1)
	}

	setup()
	ctx := context.Background()

	// Verify connectivity
	if err := masterClient.Ping(ctx).Err(); err != nil {
		log.Fatalf("Cannot connect to master: %v", err)
	}
	for i, r := range replicaClients {
		if err := r.Ping(ctx).Err(); err != nil {
			log.Fatalf("Cannot connect to replica-%d: %v", i+1, err)
		}
	}
	fmt.Println("All Redis connections verified OK")

	exp := os.Args[1]
	switch exp {
	case "1":
		experimentBasicLag()
	case "2":
		experimentWriteLoad()
	case "3":
		experimentStickyRouting()
	case "4":
		experimentDisconnect()
	case "all":
		experimentBasicLag()
		experimentWriteLoad()
		experimentStickyRouting()
		experimentDisconnect()
	default:
		fmt.Println("Unknown experiment:", exp)
	}

	// Cleanup
	masterClient.Close()
	for _, r := range replicaClients {
		r.Close()
	}
}
```

### 2.4. Running the Lab

```bash
# Start infrastructure
docker compose up -d
sleep 5

# Verify
redis-cli -h localhost -p 6379 PING
redis-cli -h localhost -p 6380 PING
redis-cli -h localhost -p 6381 PING

# Run experiments
go mod tidy
go run main.go 1    # Basic lag measurement
go run main.go 2    # Write load & lag
go run main.go 3    # Sticky routing
go run main.go 4    # Disconnect simulation
go run main.go all  # Run all
```

### 2.5. Expected Output

**Experiment 1 — Basic Lag**:
```
All Redis connections verified OK
=== Experiment 1: Basic Lag Measurement ===
Replica-1: lag_bytes=0 lag_ms=0.00
Replica-2: lag_bytes=0 lag_ms=0.00
```

**Experiment 2 — Write Load**:
```
=== Experiment 2: Write Load & Lag ===
[LAG] Replica-1: lag_bytes=0 lag_ms=0.00
[LAG] Replica-2: lag_bytes=0 lag_ms=0.00
Write load: 1000 writes in 1.234s (810 writes/sec)
[LAG] Replica-1: lag_bytes=5000 lag_ms=0.50  ← growing
[LAG] Replica-2: lag_bytes=5000 lag_ms=0.50
[LAG] Replica-1: lag_bytes=0 lag_ms=0.00  ← recovered
[LAG] Replica-2: lag_bytes=0 lag_ms=0.00
After write: Replica-1: lag_bytes=0 lag_ms=0.00
After write: Replica-2: lag_bytes=0 lag_ms=0.00
```

**Experiment 4 — Disconnect**:
```
=== Experiment 4: Replica Disconnect (5s) ===
Simulating 5s disconnect of Replica-1...
Master received 50 writes during disconnect
Replica-1 reconnecting...
[ALERT] Replica-1 lag exceeded 100ms: lag_bytes=25000 lag_ms=2.50
Replica-1 is back online
Master: disconnect:test = value-50
Replica: disconnect:test = value-50  ← partial sync worked!
```

### 2.6. Verification

```bash
# Verify replication is healthy
redis-cli -h localhost -p 6379 INFO replication | grep -E "connected_slaves|master_repl_offset"
# Should show: connected_slaves:2

# Verify no full syncs (check master logs)
docker logs redis-master 2>&1 | grep -i "fullsync\|full resync" | head -5
# Should be empty (or very few from initial sync)

# Check backlog usage
redis-cli -h localhost -p 6379 INFO replication | grep -E "repl_backlog"
# repl_backlog_active:1
# repl_backlog_size:104857600
# repl_backlog_histlen:1500  (should be small)
```

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Design Read Strategy for E-commerce Service with SLA

**Scenario**: E-commerce service với các loại data:

| Data Type | Read Volume | Write Volume | Stale Acceptable? | Read-your-Writes? |
|---|---|---|---|---|
| Product catalog (100K items) | 10K reads/sec | 100 writes/sec (price update) | < 30s | No |
| User sessions (1M sessions) | 50K reads/sec | 20K writes/sec (page views) | < 1s | Critical |
| Order status | 5K reads/sec | 5K writes/sec | < 500ms | Critical |
| Search index (Redis Search) | 20K reads/sec | 2K writes/sec | < 5s | No |
| Trending products | 30K reads/sec | 500 writes/sec | < 30s | No |

**Tasks**:

A) **Data classification**: Phân loại mỗi data type thành:
   - Read from master (RFM — Read-from-Master)
   - Read from replica (RFR — Read-from-Replica)
   - Explain why

B) **Architecture design**:
   - Cần bao nhiêu replicas để handle read volume?
   - Replication lag SLO cho mỗi loại data?
   - Backlog sizing calculation

C) **Fallback design**: Khi replica lag > SLO, application phải làm gì?
   - Implement code skeleton cho fallback logic
   - Nêu trade-off của mỗi fallback strategy

D) **Monotonic read guarantee**: Đảm bảo user không đọc được giá trị cũ sau giá trị mới (cùng session)

### 3.2. Backlog Sizing Challenge

Bạn có production Redis với:
- Dataset: 20GB
- Write rate: 30,000 commands/sec (peak), 5,000 commands/sec (average)
- Avg command size: 800 bytes
- SLA: replica lag < 2 seconds
- Network partition history: max 60 seconds (với 99.9% uptime)
- Compliance requirement: must not have full sync more than once per month

**Questions**:
1. Tính `repl-backlog-size` tối thiểu và khuyến nghị
2. Với backlog recommended, nếu partition 60s xảy ra, partial sync có đủ không?
3. Nếu avg command size tăng lên 2000 bytes (do big keys), backlog cần bao nhiêu?
4. Memory overhead của backlog trên master?

---

## 4. Reflection Questions (Open-ended)

1. **Backlog vs Memory**: Bạn có dataset 50GB và muốn set `repl-backlog-size = 1GB`. Đây là overhead 2% trên master. Tuy nhiên, nếu backlog full → full resync → tốn thêm network và disk. Bạn sẽ set bao nhiêu? Vì sao không set vô hạn?

2. **Read-from-Replica cho User Sessions**: User sessions cần read-your-writes. Nếu bạn vẫn muốn dùng replica để scale reads, bạn sẽ thiết kế như thế nào? Có options nào ngoài "read-from-master"?

3. **WAIT Command**: `WAIT` không đảm bảo durability (chỉ đảm bảo replication stream acknowledgment). Vậy `WAIT` hữu ích trong trường hợp nào? Trường hợp nào nó không đủ?

4. **Diskless vs Disk-based**: Khi nào bạn sẽ chọn disk-based replication thay vì diskless? Nêu ít nhất 2 scenarios cụ thể với trade-off.

5. **Chained Replication**: Tại sao chained replication (master → replica1 → replica2) là anti-pattern trong production? Nêu failure scenario cụ thể.

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.2 Lag Calculation**:
```bash
# Offset difference
master_offset=1234567
slave_offset=1234500
lag_bytes=$((master_offset - slave_offset))
# lag_bytes = 67

# Convert to seconds (estimate)
# Giả sử: 10K ops/sec × 500 bytes = 5MB/s
lag_seconds=$(echo "scale=3; $lag_bytes / 5000000" | bc)
# lag_seconds ≈ 0.000013s = 0.013ms

# Nếu lag_bytes > 0: replica đang behind master
```

**1.4 Replica Read-Only Behavior**:
```
`READONLY`/`READWRITE` là command cho Redis Cluster client, không phải control chính cho replica standalone.
- `replica-read-only yes`: default, replica reject writes.
- `CONFIG SET replica-read-only no`: cho phép writes cục bộ trên replica và có thể gây divergence.
- Sau lab phải set lại `replica-read-only yes` và resync bằng `REPLICAOF`.
```

---

### Lab Solutions

**TODO 1: measureLag**

```go
func measureLag(ctx context.Context, replica *redis.Client) (lagBytes int64, lagMs float64, err error) {
	// Get master offset
	masterInfo, err := masterClient.Info(ctx, "replication").Result()
	if err != nil {
		return 0, 0, fmt.Errorf("master info: %w", err)
	}
	masterOffset := parseReplOffset(masterInfo, "master_repl_offset")

	// Get replica offset
	replicaInfo, err := replica.Info(ctx, "replication").Result()
	if err != nil {
		return 0, 0, fmt.Errorf("replica info: %w", err)
	}
	replicaOffset := parseReplOffset(replicaInfo, "slave_repl_offset")

	lagBytes = masterOffset - replicaOffset
	if lagBytes < 0 {
		lagBytes = 0
	}

	// Estimate lag in ms
	// Giả sử: write rate 10K ops/sec, avg 500 bytes per command
	avgCmdSize := 500.0
	writeRate := 10000.0
	if lagBytes > 0 {
		lagMs = (float64(lagBytes) / (writeRate * avgCmdSize)) * 1000
	}
	return lagBytes, lagMs, nil
}
```

**TODO 2: generateWriteLoad**

```go
func generateWriteLoad(ctx context.Context, count, concurrency int) (duration time.Duration, err error) {
	var wg sync.WaitGroup
	sem := make(chan struct{}, concurrency)
	start := time.Now()

	type result struct {
		err error
	}
	results := make(chan result, count)

	for i := 0; i < count; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			key := fmt.Sprintf("load:key:%d", idx)
			value := fmt.Sprintf("value-%d-%d", idx, time.Now().UnixNano())
			err := masterClient.Set(ctx, key, value, 0).Err()
			results <- result{err: err}
		}(i)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	errCount := 0
	for r := range results {
		if r.err != nil {
			errCount++
		}
	}

	duration = time.Since(start)
	if errCount > 0 {
		log.Printf("[WARN] %d/%d writes failed", errCount, count)
	}
	return duration, nil
}
```

**TODO 3: readWithStickyRouting**

```go
func readWithStickyRouting(ctx context.Context, key, sessionID string) (*ReadResult, error) {
	// Hash sessionID để pick replica
	hash := 0
	for _, c := range sessionID {
		hash = hash*31 + int(c)
	}
	replicaIdx := hash % len(replicaClients)
	replica := replicaClients[replicaIdx]

	// Measure lag before read
	lagBytes, lagMs, _ := measureLag(ctx, replica)

	// Read
	val, err := replica.Get(ctx, key).Result()
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("replica read: %w", err)
	}

	return &ReadResult{
		Value:   val,
		Replica: replicaIdx,
		LagMs:   lagMs,
	}, nil
}
```

**TODO 4: simulateReplicaDisconnect**

```go
func simulateReplicaDisconnect(ctx context.Context, replicaIdx int, durationSec int) error {
	replica := replicaClients[replicaIdx]

	fmt.Printf("Simulating %ds disconnect of Replica-%d...\n", durationSec, replicaIdx+1)

	// Disconnect: REPLICAOF NO ONE
	if err := replica.ReplicaOf(ctx, "NO", "ONE").Err(); err != nil {
		return fmt.Errorf("REPLICAOF NO ONE: %w", err)
	}
	fmt.Println("Replica disconnected")

	// Write to master during disconnect
	writeCtx, cancel := context.WithTimeout(ctx, time.Duration(durationSec)*time.Second)
	defer cancel()

	go func() {
		count := 0
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-writeCtx.Done():
				fmt.Printf("Master received %d writes during disconnect\n", count)
				return
			case <-ticker.C:
				masterClient.Set(writeCtx, "disconnect:test", fmt.Sprintf("value-%d", count), 0)
				count++
			}
		}
	}()

	// Wait for duration
	time.Sleep(time.Duration(durationSec) * time.Second)

	// Reconnect
	fmt.Println("Replica reconnecting...")
	if err := replica.ReplicaOf(ctx, "localhost", "6379").Err(); err != nil {
		return fmt.Errorf("REPLICAOF localhost 6379: %w", err)
	}

	// Wait for sync
	time.Sleep(2 * time.Second)

	// Check final lag
	lagBytes, lagMs, _ := measureLag(ctx, replica)
	if lagMs > 100 {
		fmt.Printf("[ALERT] Replica-%d lag exceeded 100ms: lag_bytes=%d lag_ms=%.2f\n",
			replicaIdx+1, lagBytes, lagMs)
	}
	fmt.Println("Replica is back online")
	return nil
}
```

**TODO 5: startLagMonitor**

```go
func startLagMonitor(ctx context.Context, interval time.Duration, alertThresholdMs float64) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			for i, replica := range replicaClients {
				lagBytes, lagMs, err := measureLag(ctx, replica)
				if err != nil {
					log.Printf("Lag monitor error replica-%d: %v", i+1, err)
					continue
				}
				if lagMs > alertThresholdMs {
					fmt.Printf("[ALERT] Replica-%d lag exceeded %.2fms: lag_bytes=%d lag_ms=%.2f\n",
						i+1, alertThresholdMs, lagBytes, lagMs)
				} else {
					fmt.Printf("[LAG] Replica-%d: lag_bytes=%d lag_ms=%.2f\n",
						i+1, lagBytes, lagMs)
				}
			}
		}
	}
}
```

---

### Challenge Solutions

**3.1.A Data Classification**:

| Data Type | Strategy | Lý do |
|---|---|---|
| Product catalog | RFR (replica) | Stale < 30s OK, high read volume, write volume low |
| User sessions | RFM (master) | Read-your-writes critical, TTL short (1s lag ~ 1% stale) |
| Order status | RFM (master) | Read-your-writes critical, financial implication |
| Search index | RFR (replica) | Stale < 5s OK, Redis Search có thể đọc từ replica |
| Trending products | RFR (replica) | Stale < 30s OK, lag acceptable cho trending |

**3.2 Backlog Sizing**:

```
Part A: Minimum backlog
  Peak write rate: 30,000 cmd/s
  Max partition: 60 seconds
  Backlog = 30,000 × 60 × 800 = 1,440,000,000 bytes ≈ 1.4 GB (minimum)
  Recommended: × 1.5 safety = **2.1 GB**
  With 99.9% uptime (max partition 60s), 2GB covers it

Part B: With 60s partition
  30,000 cmd/s × 60s × 800B = 1.44 GB → partial sync works with 2GB backlog

Part C: With avg command size 2000 bytes
  30,000 × 60 × 2000 = 3.6 GB minimum
  Recommended: 5.4 GB

Part D: Memory overhead
  repl-backlog-size = 2GB
  Memory overhead: 2GB on master
  Total master memory ≈ 22GB (20GB dataset + 2GB backlog)
```

---

### Key Takeaways

1. **Always monitor replica lag**: Không có alert = silent inconsistency.
2. **Backlog size = write_rate × avg_command_size × partition_duration × safety_margin**: Minimum 100MB cho write thấp, nhưng write-heavy workloads thường cần 1GB+.
3. **Read-from-replica cho immutable/stale-OK data**: Product catalog, analytics, search. Read-from-master cho user-owned data, financial, rate limiting.
4. **Sticky routing**: Dùng session hash để route đến cùng replica → monotonic reads.
5. **Test disconnect/reconnect behavior**: Biết trước partial sync hay full sync xảy ra trong các scenario của bạn.
