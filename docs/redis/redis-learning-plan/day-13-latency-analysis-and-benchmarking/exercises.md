# Day 13: Latency Analysis & Benchmarking — Exercises

**Thời gian**: ~2 giờ
**Ngôn ngữ code**: Go (go-redis/v9 + hdrhistogram-go)
**Docker images**: redis:7.2

---

## 1. Warm-up Exercises (15-20 phút)

Mục đích: làm quen với các công cụ đo latency trực tiếp trên Redis.

### 1.1. Kiểm tra Intrinsic Latency

**Mục tiêu**: Đo overhead cố định của Redis event loop (không tính network).

```bash
# Chạy 60 giây để lấy mẫu đủ lớn
redis-cli --intrinsic-latency 60
```

**Expected output**:

```txt
Max latency base: 0.54 microseconds
This instance is a good candidate for benchmarking.
60 seconds total, 12345678 operations sampled.
```

**Điểm so sánh**:

| Kết quả | Đánh giá | Hành động |
|---|---|---|
| < 0.5 microseconds | Excellent | Sẵn sàng benchmark |
| 0.5 - 2 microseconds | Good | Bình thường |
| 2 - 10 microseconds | Degraded | Kiểm tra THP, CPU contention |
| > 10 microseconds | Critical | Không benchmark được — fix cấu hình trước |

### 1.2. Cấu hình và đọc SLOWLOG

**Bước 1**: Đặt threshold thấp để bắt được nhiều slow commands:

```bash
redis-cli CONFIG SET slowlog-log-slower-than 1000
redis-cli CONFIG SET slowlog-max-len 1000
redis-cli CONFIG GET slowlog-log-slower-than
redis-cli CONFIG GET slowlog-max-len
```

**Expected output**:

```txt
1) "slowlog-log-slower-than"
2) "1000"
1) "slowlog-max-len"
2) "1000"
```

**Bước 2**: Tạo slow commands với `DEBUG SLEEP`:

```bash
# Xóa slowlog cũ
redis-cli SLOWLOG RESET

# Chạy các commands chậm (5ms = 5000 microseconds)
redis-cli DEBUG SLEEP 0.005
redis-cli SET warmup:slow "value"
redis-cli GET warmup:slow

# Một số command O(N) nhỏ
redis-cli SADD warmup:set a b c d e f g h i j
redis-cli SMEMBERS warmup:set
```

**Bước 3**: Đọc slowlog:

```bash
redis-cli SLOWLOG GET
```

**Expected output** (dạng array):

```txt
 1) 1) (integer) 1
    2) (integer) 1700000000
    3) (integer) 5000
    4) 1) "DEBUG" "SLEEP" "0.005"
    5) (integer) 0
    6) ""
 2) 1) (integer) 2
    3) (integer) 1700000001
    3) (integer) 200
    4) 1) "SMEMBERS" "warmup:set"
```

Điểm chú ý:
- `duration` ở microseconds: `5000` = `5ms` (từ DEBUG SLEEP)
- `200` = `0.2ms` (từ SMEMBERS 10 members)
- `slowlog-log-slower-than = 1000` = `1ms` threshold
- DEBUG SLEEP = `5000` > `1000` → có trong slowlog
- SMEMBERS với 10 members = `200µs` = `0.2ms` → không qua `1000µs` → không có trong slowlog (nếu threshold = 1000)

**Bước 4**: So sánh với threshold khác:

```bash
# Đặt threshold thấp hơn (500 microseconds = 0.5ms)
redis-cli CONFIG SET slowlog-log-slower-than 500
redis-cli SLOWLOG RESET
redis-cli SMEMBERS warmup:set
redis-cli SLOWLOG GET
```

**Expected output**: Bây giờ SMEMBERS (200µs = 0.2ms) vẫn không qua threshold 500µs. Thử với LRANGE nhiều hơn:

```bash
redis-cli RPUSH warmup:list $(seq -s ' ' 1 1000)
redis-cli LRANGE warmup:list 0 -1
redis-cli SLOWLOG GET
```

Với 1000 phần tử, LRANGE sẽ mất ~1-5ms → xuất hiện trong slowlog.

### 1.3. LATENCY DOCTOR

**Bước 1**: Bật latency monitor:

```bash
redis-cli CONFIG SET latency-monitor-threshold 100
```

**Bước 2**: Kích hoạt một số sự kiện (fork, eviction):

```bash
# Tạo memory pressure để trigger eviction
redis-cli CONFIG SET maxmemory 10mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Ghi nhiều dữ liệu vượt maxmemory
for i in $(seq 1 10000); do
  redis-cli SET "key:$i" "value$(seq -s '' 1 100)"
done

# Kiểm tra eviction
redis-cli INFO stats | grep evicted_keys
```

**Bước 3**: Chạy LATENCY DOCTOR:

```bash
redis-cli LATENCY DOCTOR
```

**Expected output sections**:

```txt
Dave, I have observed latency spikes in your Redis instance.
...
I have found 3 distinct latency events in this Redis instance:

1. Command: (command execution) - N events, avg X ms
   Slow commands detected by SLOWLOG.

2. Command: eviction (eviction time) - N events, avg X ms
   Time needed to evict keys due to memory pressure.

3. Command: fast-command (non-commands) - N events, avg X ms
   Non-command time such as TTL and key eviction.
```

**Bước 4**: Kiểm tra LATENCY LATEST và LATENCY HISTORY:

```bash
redis-cli LATENCY LATEST
redis-cli LATENCY HISTORY eviction
```

**Điểm chú ý**: LATENCY chỉ ghi nhận các sự kiện vượt `latency-monitor-threshold` (tính bằng millisecond). SLOWLOG ghi nhận command vượt `slowlog-log-slower-than` (tính bằng microsecond). Hai công cụ bổ sung nhau, không thay thế.

### 1.4. redis-cli --latency và --latency-dist

**Bước 1**: Đặt lại maxmemory (tắt eviction để có kết quả ổn định):

```bash
redis-cli CONFIG SET maxmemory 0
redis-cli CONFIG SET maxmemory-policy noeviction
redis-cli CONFIG SET slowlog-log-slower-than 10000
redis-cli SLOWLOG RESET
```

**Bước 2**: Đo latency liên tục:

```bash
# Chạy 30 giây, Ctrl+C để dừng
redis-cli --latency
```

**Expected output** (dòng cập nhật):

```txt
latency: 0.12ms
latency: 0.11ms
latency: 0.13ms
...
```

**Bước 3**: Thử --latency-dist (nếu Redis 7+):

```bash
redis-cli --latency-dist
```

**Output**: ASCII histogram của latency distribution. Nhìn vào độ cao của từng bucket để hiểu latency distribution.

### 1.5. redis-benchmark nhanh

```bash
# Basic GET
redis-benchmark -t get -n 10000 -q

# GET với payload lớn hơn (1KB)
redis-benchmark -t get -d 1024 -n 10000 -q

# So sánh với pipeline
redis-benchmark -t get -P 1 -n 10000 -q
redis-benchmark -t get -P 10 -n 10000 -q
redis-benchmark -t get -P 50 -n 10000 -q
```

**Expected observation**:
- Pipeline tăng throughput nhưng tăng latency trung bình mỗi command.
- Tìm điểm tối ưu: pipeline quá lớn làm p99 tăng nhiều.

---

## 2. Hands-on Lab (60-70 phút)

### Setup: Docker Compose

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7.2
    container_name: redis-latency-lab
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --slowlog-log-slower-than 1000
      --slowlog-max-len 10000
      --latency-monitor-threshold 100
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
module latency-tool

go 1.21

require (
	github.com/HdrHistogram/hdrhistogram-go v1.1.2
	github.com/redis/go-redis/v9 v9.5.1
)
```

### Part A: Write Benchmark Tool (Go + HDR Histogram)

Viết tool `latency-tool` đo p50/p95/p99/p99.9 latency với các payload size khác nhau.

**File**: `cmd/benchmark/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/HdrHistogram/hdrhistogram-go"
	"github.com/redis/go-redis/v9"
)

// Payload sizes to test (bytes)
var payloadSizes = []int{64, 1024, 16384, 65536}

// BenchmarkConfig holds benchmark parameters.
type BenchmarkConfig struct {
	Host       string
	Port       int
	PoolSize   int
	NumWorkers int
	Duration   time.Duration
	PayloadSz  int
	RandKeys   bool
}

// BenchmarkResult holds results for one config.
type BenchmarkResult struct {
	PayloadSize int
	Workers     int
	OpsTotal    int64
	OpsPerSec   float64
	MinLatency  time.Duration
	P50         time.Duration
	P95         time.Duration
	P99         time.Duration
	P999        time.Duration // p99.9
	MaxLatency  time.Duration
	AvgLatency  time.Duration
}

func (r *BenchmarkResult) String() string {
	return fmt.Sprintf(
		"payload=%7dB | workers=%3d | ops=%10.0f/s | "+
			"p50=%7s p95=%7s p99=%7s p99.9=%7s max=%7s | "+
			"avg=%7s",
		r.PayloadSize, r.Workers, r.OpsPerSec,
		r.P50, r.P95, r.P99, r.P999, r.MaxLatency,
		r.AvgLatency,
	)
}

// generatePayload creates a random payload of the given size.
func generatePayload(size int) []byte {
	b := make([]byte, size)
	rand.Read(b)
	return b
}

// runBenchmark executes the benchmark with the given config.
func runBenchmark(ctx context.Context, cfg BenchmarkConfig) *BenchmarkResult {
	rdb := redis.NewClient(&redis.Options{
		Addr:        fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		PoolSize:    cfg.PoolSize,
		MinIdleConns: cfg.PoolSize / 4,
		ReadTimeout: 30 * time.Second,
	})
	defer rdb.Close()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Ping failed: %v", err)
	}

	// Pre-populate keys for random-key benchmark
	keyCount := 10000
	if cfg.RandKeys {
		log.Printf("Warming up: populating %d keys (%d bytes each)...", keyCount, cfg.PayloadSz)
		payload := generatePayload(cfg.PayloadSz)
		for i := 0; i < keyCount; i++ {
			key := fmt.Sprintf("bench:key:%06d", i)
			if err := rdb.Set(ctx, key, payload, 0).Err(); err != nil {
				log.Printf("SET warning: %v", err)
			}
		}
		log.Printf("Warmup done.")
	}

	// HDR histogram: record latencies in microseconds (max 1 second, 3 significant figures)
	hist := hdrhistogram.New(1, 1_000_000, 3) // 1us to 1s

	var (
		wg         sync.WaitGroup
		totalOps   int64
		latencyMu  sync.Mutex
		totalLatUs int64
		minLatUs   int64 = 1_000_000 // start high
	)

	start := time.Now()
	deadline := start.Add(cfg.Duration)

	worker := func(id int) {
		defer wg.Done()
		localOps := int64(0)
		localLatUs := int64(0)
		localMin := int64(1_000_000)

		payload := generatePayload(cfg.PayloadSz)

		for time.Now().Before(deadline) {
			key := fmt.Sprintf("bench:key:%06d", rand.Intn(keyCount))

			cmdStart := time.Now()
			err := rdb.Set(ctx, key, payload, 0).Err()
			latUs := time.Since(cmdStart).Microseconds()

			if err != nil {
				log.Printf("SET error: %v", err)
				continue
			}

			localOps++
			localLatUs += latUs
			if latUs < localMin {
				localMin = latUs
			}

			_ = hist.RecordValue(latUs)
		}

		atomic.AddInt64(&totalOps, localOps)
		latencyMu.Lock()
		totalLatUs += localLatUs
		if localMin < minLatUs {
			minLatUs = localMin
		}
		latencyMu.Unlock()
	}

	for i := 0; i < cfg.NumWorkers; i++ {
		wg.Add(1)
		go worker(i)
	}
	wg.Wait()

	elapsed := time.Since(start)
	opsPerSec := float64(totalOps) / elapsed.Seconds()

	return &BenchmarkResult{
		PayloadSize: cfg.PayloadSz,
		Workers:     cfg.NumWorkers,
		OpsTotal:    totalOps,
		OpsPerSec:   opsPerSec,
		MinLatency:  time.Duration(minLatUs) * time.Microsecond,
		P50:         time.Duration(hist.ValueAtQuantile(50)) * time.Microsecond,
		P95:         time.Duration(hist.ValueAtQuantile(95)) * time.Microsecond,
		P99:         time.Duration(hist.ValueAtQuantile(99)) * time.Microsecond,
		P999:        time.Duration(hist.ValueAtQuantile(99.9)) * time.Microsecond,
		MaxLatency:  time.Duration(hist.ValueAtQuantile(100)) * time.Microsecond,
		AvgLatency:  time.Duration(totalLatUs/totalOps) * time.Microsecond,
	}
}

func main() {
	ctx := context.Background()

	host := "localhost"
	port := 6379
	if h := os.Getenv("REDIS_HOST"); h != "" {
		host = h
	}

	workers := []int{1, 5, 10, 20}
	duration := 5 * time.Second

	fmt.Println("=== Latency Benchmark Tool ===")
	fmt.Printf("Host: %s:%d | Duration per test: %v\n", host, port, duration)
	fmt.Println()

	// Header
	fmt.Printf("%-90s\n", "CONFIG")
	fmt.Println("| payload=    64B | workers=  1 | ops/s=        N/A | p50=    N/A | p95=    N/A | p99=    N/A | p99.9=    N/A | max=    N/A | avg=    N/A |")
	fmt.Println("| payload=   1KB | workers=  1 | ops/s=        N/A | p50=    N/A | p95=    N/A | p99=    N/A | p99.9=    N/A | max=    N/A | avg=    N/A |")
	fmt.Println("| payload=  16KB | workers=  1 | ops/s=        N/A | p50=    N/A | p95=    N/A | p99=    N/A | p99.9=    N/A | max=    N/A | avg=    N/A |")
	fmt.Println("| payload=  64KB | workers=  1 | ops/s=        N/A | p50=    N/A | p95=    N/A | p99=    N/A | p99.9=    N/A | max=    N/A | avg=    N/A |")
	fmt.Println()

	for _, sz := range payloadSizes {
		for _, w := range workers {
			cfg := BenchmarkConfig{
				Host:       host,
				Port:       port,
				PoolSize:   w,
				NumWorkers: w,
				Duration:   duration,
				PayloadSz:  sz,
				RandKeys:   true,
			}
			result := runBenchmark(ctx, cfg)
			fmt.Printf("| %s\n", result.String())
		}
		fmt.Println()
	}

	fmt.Println("Done.")
}
```

> **Hint 1**: Nếu trên máy chạy chậm (laptop, VM), giảm `payloadSizes` xuống 3 mức (64B, 1KB, 16KB) và giảm `workers` xuống [1, 5, 10].
>
> **Hint 2**: Kết quả sẽ thay đổi nhiều theo hardware. Điểm quan trọng là **xu hướng**: payload lớn hơn → latency tăng như thế nào? Workers tăng → throughput tăng hay bão hòa?
>
> **Expected observations**:
> - Payload 64B → p99 ~0.2-1ms (LAN, localhost)
> - Payload 64KB → p99 có thể tăng 5-10× do network serialization
> - Workers 1 → 5 → 10: throughput tăng tuyến tính
> - Workers 10 → 20: throughput có thể bão hòa (Redis single-threaded)

### Part B: Parse SLOWLOG + LATENCY HISTORY Report

Viết script đọc SLOWLOG và LATENCY HISTORY, tạo report tổng hợp.

**File**: `cmd/report/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"sort"
	"time"

	"github.com/redis/go-redis/v9"
)

type SlowLogEntry struct {
	ID         int64
	Timestamp  int64
	DurationUs int64
	Command    []string
	ClientName string
}

type LatencyEvent struct {
	Event     string
	Timestamp int64
	LatencyUs int64
}

// fetchSlowLog retrieves slowlog entries via SLOWLOG GET.
func fetchSlowLog(ctx context.Context, rdb *redis.Client, limit int64) ([]SlowLogEntry, error) {
	raw, err := rdb.SlowLogGet(ctx, limit).Result()
	if err != nil {
		return nil, fmt.Errorf("SLOWLOG GET: %w", err)
	}

	var entries []SlowLogEntry
	for _, r := range raw {
		entries = append(entries, SlowLogEntry{
			ID:         r.ID,
			Timestamp:  r.StartedAt.Unix(),
			DurationUs: r.Duration.Microseconds(),
			Command:    r.Args,
			ClientName: r.ClientName,
		})
	}
	return entries, nil
}

// fetchLatencyLatest retrieves LATENCY LATEST.
func fetchLatencyLatest(ctx context.Context, rdb *redis.Client) ([]LatencyEvent, error) {
	raw, err := rdb.Do(ctx, "LATENCY", "LATEST").Result()
	if err != nil {
		return nil, fmt.Errorf("LATENCY LATEST: %w", err)
	}

	entries, _ := raw.([]interface{})
	var events []LatencyEvent
	for _, item := range entries {
		e, ok := item.([]interface{})
		if !ok || len(e) < 3 {
			continue
		}
		name, _ := e[0].(string)
		ts, _ := e[1].(int64)
		latUs, _ := e[2].(int64)
		events = append(events, LatencyEvent{Event: name, Timestamp: ts, LatencyUs: latUs})
	}
	return events, nil
}

// fetchLatencyHistory retrieves LATENCY HISTORY for a specific event.
func fetchLatencyHistory(ctx context.Context, rdb *redis.Client, event string) ([]LatencyEvent, error) {
	raw, err := rdb.Do(ctx, "LATENCY", "HISTORY", event).Result()
	if err != nil {
		return nil, fmt.Errorf("LATENCY HISTORY %s: %w", event, err)
	}

	entries, _ := raw.([]interface{})
	var events []LatencyEvent
	for _, item := range entries {
		e, ok := item.([]interface{})
		if !ok || len(e) < 2 {
			continue
		}
		ts, _ := e[0].(int64)
		latUs, _ := e[1].(int64)
		events = append(events, LatencyEvent{Event: event, Timestamp: ts, LatencyUs: latUs})
	}
	return events, nil
}

func percentile(sorted []int64, p float64) int64 {
	if len(sorted) == 0 {
		return 0
	}
	idx := int(float64(len(sorted)-1) * p / 100)
	if idx >= len(sorted) {
		idx = len(sorted) - 1
	}
	return sorted[idx]
}

func main() {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	defer rdb.Close()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Cannot connect to Redis: %v", err)
	}

	fmt.Println("=== Latency Analysis Report ===")
	fmt.Printf("Generated: %s\n\n", time.Now().Format(time.RFC3339))

	// --- SLOWLOG ---
	slowEntries, err := fetchSlowLog(ctx, rdb, 1000)
	if err != nil {
		log.Printf("SLOWLOG error: %v", err)
	} else {
		fmt.Printf("--- SLOWLOG (%d entries) ---\n", len(slowEntries))

		if len(slowEntries) > 0 {
			durations := make([]int64, len(slowEntries))
			cmdFreq := make(map[string]int)
			slowCmds := make([]SlowLogEntry, 0)

			for i, e := range slowEntries {
				durations[i] = e.DurationUs
				if len(e.Command) > 0 {
					cmdFreq[e.Command[0]]++
				}
				if e.DurationUs > 5000 { // > 5ms
					slowCmds = append(slowCmds, e)
				}
			}
			sort.Slice(durations, func(i, j int) bool { return durations[i] < durations[j] })

			fmt.Printf("  Duration stats:\n")
			fmt.Printf("    Min:   %7.3fms\n", float64(durations[0])/1000)
			fmt.Printf("    p50:   %7.3fms\n", float64(percentile(durations, 50))/1000)
			fmt.Printf("    p95:   %7.3fms\n", float64(percentile(durations, 95))/1000)
			fmt.Printf("    p99:   %7.3fms\n", float64(percentile(durations, 99))/1000)
			fmt.Printf("    Max:   %7.3fms\n", float64(durations[len(durations)-1])/1000)

			fmt.Printf("\n  Command frequency:\n")
			type pair struct{ cmd string; count int }
			var pairs []pair
			for cmd, cnt := range cmdFreq {
				pairs = append(pairs, pair{cmd, cnt})
			}
			sort.Slice(pairs, func(i, j int) bool { return pairs[i].count > pairs[j].count })
			for i, p := range pairs {
				if i >= 10 {
					break
				}
				fmt.Printf("    %-20s %d\n", p.cmd, p.count)
			}

			fmt.Printf("\n  Slow commands (> 5ms, top 10):\n")
			sort.Slice(slowCmds, func(i, j int) bool {
				return slowCmds[i].DurationUs > slowCmds[j].DurationUs
			})
			for i, e := range slowCmds {
				if i >= 10 {
					break
				}
				cmdStr := fmt.Sprintf("%v", e.Command)
				if len(cmdStr) > 60 {
					cmdStr = cmdStr[:60]
				}
				fmt.Printf("    %7.3fms | %s\n", float64(e.DurationUs)/1000, cmdStr)
			}
		} else {
			fmt.Println("  No slow commands recorded.")
		}
	}

	// --- LATENCY LATEST ---
	fmt.Println()
	events, err := fetchLatencyLatest(ctx, rdb)
	if err != nil {
		log.Printf("LATENCY LATEST error: %v", err)
	} else if len(events) > 0 {
		fmt.Println("--- LATENCY LATEST ---")
		for _, e := range events {
			ts := time.Unix(e.Timestamp, 0).Format("15:04:05")
			fmt.Printf("  %s | %-30s %8.3fms\n", ts, e.Event, float64(e.LatencyUs)/1000)
		}
	}

	// --- LATENCY HISTORY: fork ---
	fmt.Println()
	forkEvents, err := fetchLatencyHistory(ctx, rdb, "fork")
	if err != nil {
		log.Printf("LATENCY HISTORY fork: %v", err)
	} else {
		fmt.Println("--- LATENCY HISTORY: fork ---")
		if len(forkEvents) > 0 {
			for _, e := range forkEvents {
				ts := time.Unix(e.Timestamp, 0).Format("15:04:05")
				fmt.Printf("  %s | %8.3fms\n", ts, float64(e.LatencyUs)/1000)
			}
		} else {
			fmt.Println("  No fork events recorded.")
		}
	}

	fmt.Println()
}
```

---

## 3. Challenge Exercise (30-40 phút)

### Scenario: Daily p99 Spike From 5ms to 800ms at 09:00

**Context**:

```txt
Production Redis:
  - Redis 7.2, 1 primary + 2 replicas
  - used_memory: 8GB (maxmemory: 10GB)
  - RDB: save 900 1 (snapshot every 15 min if >= 1 key changed)
  - AOF: appendfsync everysec
  - maxmemory-policy: allkeys-lru
  - Slowlog threshold: 10000 (10ms — TOO LOOSE)

Symptoms:
  - p99 latency: 5ms (normal, 08:00-08:59)
  - p99 latency: 800ms (spike, 09:00-09:15, every day)
  - p99 returns to 5ms after 09:15
  - No traffic spike reported by application logs
  - Database team confirms no DB queries slow at 09:00
```

**Setup data giả lập** (chạy trước):

```bash
# Setup: Tạo dữ liệu
redis-cli CONFIG SET slowlog-log-slower-than 1000
redis-cli SLOWLOG RESET

# Tạo một số big keys (simulate production data)
redis-cli DEL leaderboard:global
for i in $(seq 1 50000); do
  redis-cli ZADD leaderboard:global $i "user:$i"
done
echo "Leaderboard created: $(redis-cli ZCARD leaderboard:global) members"

# Tạo một số keys để scan
redis-cli SET app:config:1 '{"rate":100,"timeout":5}'
redis-cli SET app:config:2 '{"rate":200,"timeout":10}'

# Tao cache data
for i in $(seq 1 1000); do
  redis-cli SET "cache:item:$i" "value$(seq -s '' 1 100)"
done
echo "Cache keys created: $(redis-cli DBSIZE)"

# Enable latency monitor
redis-cli CONFIG SET latency-monitor-threshold 100
```

**Yêu cầu**: Dùng các công cụ đã học để tìm root cause và đề xuất mitigation.

### 3a. Thu thập thông tin (tìm hiểu hiện trạng)

Chạy các command sau và ghi lại kết quả:

```bash
# 1. Kiểm tra slowlog hiện tại
redis-cli SLOWLOG GET 20

# 2. Kiểm tra các config liên quan
redis-cli CONFIG GET slowlog-log-slower-than
redis-cli CONFIG GET maxmemory-policy
redis-cli INFO stats | grep -E "total_forks|latest_fork_usec"
redis-cli INFO persistence | grep -E "rdb_|aof_"

# 3. Kiểm tra latency events
redis-cli LATENCY LATEST
redis-cli LATENCY DOCTOR

# 4. Kiểm tra big keys (nguy cơ O(N))
redis-cli DEBUG OBJECT ENCODING leaderboard:global
redis-cli ZCARD leaderboard:global

# 5. Kiểm tra commandstats
redis-cli INFO commandstats | grep -E "cmdstat_keys|cmdstat_zrange|cmdstat_slowlog"
```

**Phân tích**:
- `slowlog-log-slower-than = 10000` (10ms) → quá cao, bỏ sót nhiều slow commands
- `latest_fork_usec` cao → fork delay do memory size
- Leaderboard có 50K members → ZRANGEBYSCORE +inf +inf = O(N)

### 3b. Tìm root cause (gửi yêu cầu này)

Giả sử trong 1 cron job chạy lúc 09:00 có các command sau:

```bash
# Simulate cron job lúc 09:00 — MẪU, CHẠY TRONG TERMINAL 1
# (các command này sẽ tạo ra latency spike)

# WARNING: Chỉ chạy trong môi trường test
# Không bao giờ chạy các command này trong production!

# 1. KEYS * — scan toàn bộ keyspace (O(N))
echo "=== KEYS * (O(N) — nguy hiểm) ==="
redis-cli KEYS '*'

# 2. ZRANGE without LIMIT — lấy toàn bộ sorted set (O(N))
echo "=== ZRANGE without LIMIT (O(N)) ==="
redis-cli ZRANGE leaderboard:global 0 -1 | wc -l

# 3. BGSAVE kích hoạt RDB save
echo "=== Manual BGSAVE ==="
redis-cli BGSAVE

# 4. Monitor slowlog trong terminal 2
# redis-cli --latency-history
# Hoặc:
watch -n 1 'redis-cli SLOWLOG LEN'
```

Sau khi chạy, kiểm tra lại:

```bash
redis-cli SLOWLOG GET 10
redis-cli INFO commandstats | grep -E "cmdstat_keys|cmdstat_zrange"
redis-cli LATENCY LATEST
```

**Điểm chú ý**: KEYS * và ZRANGE không LIMIT đều là O(N) — chúng sẽ làm latency tăng với hệ số tuyến tính theo số phần tử.

### 3c. Phân tích root cause

Điền vào bảng phân tích:

| Thời gian | Hiện tượng | Nguyên nhân |
|---|---|---|
| 09:00 | KEYS * chạy | O(N) = 100K keys → 500ms+ |
| 09:01 | ZRANGE 0 -1 chạy | O(N) = 50K members → 200ms+ |
| 09:02 | BGSAVE chạy | Fork 8GB memory → 200ms+ |
| 09:03 | AOF rewrite bắt đầu | Disk I/O → latency tăng thêm |
| 09:05 | Traffic bình thường nhưng bị queue | Redis single-threaded bị blocking |

**Các root cause chính**:

1. **KEYS *** (hoặc SCAN nhưng không LIMIT) — O(N), block event loop
2. **ZRANGE không LIMIT** — trả về 50K phần tử, làm chậm Redis
3. **Fork cho RDB** — 8GB memory → ~200ms fork latency
4. **slowlog-log-slower-than = 10000** quá cao → không bắt được các command 5-10ms

### 3d. Đề xuất mitigation (lời giải)

Viết các bước fix cho từng root cause:

**Fix 1: Thay KEYS bằng SCAN**:

```bash
# Cũ: KEYS * (O(N), blocking)
redis-cli KEYS user:*

# Mới: SCAN (O(1) per call, non-blocking)
redis-cli --scan | head -100
# Hoặc dùng code:
# SCAN cursor MATCH pattern COUNT 100
```

**Fix 2: Thêm LIMIT cho ZRANGE**:

```bash
# Cũ: ZRANGE leaderboard 0 -1 (trả về tất cả)
# Mới: ZRANGE leaderboard 0 99 WITHSCORES (chỉ lấy 100 phần tử đầu)
# Hoặc: ZRANGEBYSCORE leaderboard -inf +inf LIMIT 0 100
```

**Fix 3: Giải phương trình fork latency**:

```bash
# Tăng interval giữa các RDB save
redis-cli CONFIG SET save "900 1 300 100 180 10"
# -> Chỉ save nếu có 10+ thay đổi trong 3 phút (thay vì 1 thay đổi trong 15 phút)

# Hoặc tắt RDB, chỉ dùng AOF
redis-cli CONFIG SET save ""
```

**Fix 4: Giảm slowlog threshold**:

```bash
# Cũ: slowlog-log-slower-than 10000 (10ms — bỏ sót)
# Mới: slowlog-log-slower-than 1000 (1ms — bắt được p95)
redis-cli CONFIG SET slowlog-log-slower-than 1000
```

**Fix 5: Chương trình cron job thực hiện cách 09:00**:

```bash
# Chạy lúc 02:00 (low traffic) thay vì 09:00
# Hoặc: disable during peak hours
```

---

## 4. Reflection Questions

### Question 1: Tại sao nên dùng synthetic benchmark (redis-benchmark) cho version comparison, nhưng không cho capacity planning?

Synthetic benchmark (redis-benchmark) có độ lặp lại cao, dễ chạy, không cần cấu hình phức tạp. Rất tốt để so sánh Redis version A vs B trên cùng một máy, cùng một workload. Nhưng nó không phản ánh production reality vì:

- Default payload = 3 bytes (không realistic)
- Chỉ một command type (GET hoặc SET), không phản ánh mixed workload
- Không có multi-threaded workers thật sự (trước Redis 6+)
- Không có percentile reporting đầy đủ (chỉ p99.999)
- Không thể mô phỏng phân phối traffic thật (chu kỳ, burst)

Capacity planning cần realistic workload: payload size that, read/write ratio that, multi-threaded, duration đủ dài. => memtier_benchmark hoặc custom tool.

**Reflection**: Nếu bạn cần xác định Redis version nao nhanh hơn — dùng redis-benchmark. Nếu bạn cần biết cần bao nhiêu Redis nodes cho production — dung memtier_benchmark với real workload.

### Question 2: Threshold slowlog-log-slower-than bao nhiêu là "hợp lý"? Có con số tuyệt đối không?

Không có con số tuyệt đối — threshold phụ thuộc vào SLO của ứng dụng:

| SLO p99 | Recommended threshold | Lý do |
|---|---|---|
| < 5ms | 500µs (0.5ms) | Bắt mọi thứ hơn p95 |
| 5-20ms | 1000µs (1ms) | Catch anything above p90 |
| 20-100ms | 5000µs (5ms) | Catch above p95 |
| > 100ms | 10000µs (10ms) | Chỉ bắt command chậm thực sự |

**Rule**: Threshold = SLO p99 / 10. Ví dụ: SLO p99 = 50ms → threshold = 5ms.

**Trade-off**: Threshold thấp = nhiều entries = nhiều memory (slowlog-max-len). Threshold cao = bỏ sót slow commands.

### Question 3: Benchmark local vs cross-region — khi nào thì sự khác biệt?

| Scenario | Localhost | Cross-region |
|---|---|---|
| RTT | ~0.05ms | 5-150ms |
| Quá tải? | Không bao giờ (quá nhanh) | Có (network là bottleneck) |
| Giá trị? | Chỉ khi prod cùng localhost | Khi prod là remote |
| Latency | Không thể dùng để ước tính production | Có thể dùng để ước tính production |

**Reflection**: Benchmark local lại rồi deploy cross-region = SLA miss 40-300% (trường hợp Uber, Twitter). Luôn benchmark với topology tương tự production.

### Question 4: Một số engineers cho rằng "p99 là đủ, không cần p99.9". Bạn đồng ý không?

Không đồng ý trong môi trường. p99 bỏ 1% requests. Với 1 triệu requests/ngay = 10,000 requests chậm. Nếu mỗi request chậm = 1s, 10,000 × 1s = 2.7 giờ user time lost/day.

Những trường hợp p99.9 quan trọng hơn:
- **Financial systems**: 0.1% = gap lớn trong revenue
- **Gaming**: 0.1% player bị lag = review tệ
- **API gateway**: 0.1% timeout = 100+ errors/phút với 100K RPS

**Reflection**: p99 đủ nếu distribution đều. Bimodal distribution (có cả fast và slow command) → p99 và p99.9 đều quan trọng để bắt tail.

### Question 5: Nếu intrinsic latency = 0.54µs nhưng p99 = 5ms — gap do đâu?

Gap do:
1. **Network** (nếu remote): 0.5-15ms RTT
2. **Slow commands**: O(N) commands trong slowlog
3. **Fork latency**: RDB/AOF rewrite
4. **Memory pressure**: eviction, swap
5. **CPU contention**: noisy neighbor trên cùng host
6. **Disk I/O**: AOF fsync

**Tính toán**: p99 = 5ms = 5000µs. Intrinsic = 0.5µs. Gap = ~10,000×. Neu network = 0.5ms, con 4.5ms con lai = slow commands + fork + contention.

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1 — Intrinsic latency**:
- Kết quả < 1µs = excellent. Nếu > 5µs → kiểm tra THP: `cat /sys/kernel/mm/transparent_hugepage/enabled`
- Nếu có "always" → disable THP trước khi benchmark.

**1.2 — SLOWLOG threshold**:
- Threshold = 1000 (1ms): DEBUG SLEEP 0.005 = 5000µs > 1000 → có trong slowlog
- Threshold = 500 (0.5ms): SMEMBERS với 10 members = 200µs < 500 → không có
- LRANGE 1000 phần tử = 1-5ms > 500 → có trong slowlog
- **Key insight**: Slowlog chỉ ghi command vừa vượt threshold, không phải tất cả commands chậm.

**1.3 — LATENCY vs SLOWLOG**:
- `slowlog-log-slower-than` = command-level, microseconds, mỗi command đều được log
- `latency-monitor-threshold` = event-level, milliseconds, chỉ những sự kiện đặc biệt (fork, eviction, disk)
- Hai công cụ bổ sung nhau.

**1.5 — redis-benchmark**:
- Pipeline tăng throughput nhưng tăng latency per command.
- Điểm tối ưu: pipeline 10-50 tùy thuộc RTT. RTT localhost ~0.05ms → pipeline 50 cho 50K ops/sec.

### Hands-on Lab Solutions

**Part A — HDR Histogram**:
- `hdrhistogram-go.New(1, 1_000_000, 3)`: ghi từ 1µs đến 1s, 3 chữ số nghĩa.
- `hist.RecordValue(latUs)`: ghi latency mỗi command.
- `hist.ValueAtQuantile(p)`: lay gia tri tai percentile.

**Expected benchmark results** (laptop, localhost):

| Payload | Workers | Ops/sec | p50 | p95 | p99 | p99.9 |
|---|---|---|---|---|---|---|
| 64B | 1 | ~8K | 0.1ms | 0.2ms | 0.3ms | 0.5ms |
| 64B | 5 | ~35K | 0.1ms | 0.3ms | 0.5ms | 1.0ms |
| 64B | 20 | ~60K | 0.2ms | 0.8ms | 1.5ms | 3.0ms |
| 1KB | 1 | ~7K | 0.1ms | 0.2ms | 0.4ms | 0.8ms |
| 1KB | 10 | ~40K | 0.2ms | 0.6ms | 1.2ms | 2.5ms |
| 16KB | 1 | ~3K | 0.3ms | 0.6ms | 1.0ms | 2.0ms |
| 16KB | 10 | ~20K | 0.5ms | 1.5ms | 3.0ms | 8.0ms |
| 64KB | 1 | ~1K | 0.8ms | 1.5ms | 3.0ms | 8.0ms |
| 64KB | 10 | ~8K | 1.2ms | 4.0ms | 10ms | 20ms |

**Key observations**:
1. Payload 64KB → p99 tăng 10-30× so với 64B (network serialization + memory allocation)
2. Workers 10 → 20: throughput có thể bão hòa (Redis single-threaded ~50-100K ops/sec localhost)
3. p99.9 cao hơn p99 nhiều → đảm bảo rằng 0.1% tail vẫn nằm trong SLO

**Part B — SLOWLOG + LATENCY report**:
- SLOWLOG chi ghi command vuot threshold → phân biệt slow commands
- LATENCY LATEST chi ghi su kien dac biet → phân biệt fork/eviction
- Kết hợp cả hai để có tầm nhìn đầy đủ về latency.

### Challenge Solutions

**Root cause của spike 09:00**:

```txt
1. KEYS * trong cron job:
   - O(N) = 100K keys → block event loop 500ms+
   - Redis single-threaded → tất cả commands queue

2. ZRANGE 0 -1 không LIMIT:
   - 50K members → trả về 50K strings → network saturation
   - O(log N + M) với M = 50000 → 10-50ms

3. BGSAVE chạy 09:00:
   - 8GB memory → fork ~200-500ms (Redis tạo nhiều COW)
   - Fork block? Không. Nhưng COW pages khi save có thể gây latency

4. slowlog-log-slower-than = 10000 (10ms):
   - Quá cao → không bắt được command 5-9ms
   - Gap giữa 10ms (threshold) và 800ms (p99) = slow commands trong khoảng đó
```

**Mitigation recommendations** (theo thứ tự ưu tiên):

| Priority | Fix | Impact |
|---|---|---|
| 1 | Thay KEYS * bằng SCAN | Loại bỏ 500ms spike |
| 2 | Thêm LIMIT cho ZRANGE | Loại bỏ 10-50ms spike |
| 3 | Giảm slowlog threshold = 1000 | Bắt được slow commands sớm hơn |
| 4 | Di chuyển cron job lúc 02:00 | Tránh peak hour |
| 5 | Giảm RDB frequency | Giảm fork spike |

**Thay thế nào thực hiện**:
- SCAN: `SCAN 0 MATCH user:* COUNT 100` → vòng lặp, non-blocking
- ZRANGE LIMIT: `ZRANGEBYSCORE leaderboard -inf +inf LIMIT 0 100` → chỉ 100 items
- Slowlog: `CONFIG SET slowlog-log-slower-than 1000` → bắt sớm hơn
- Cron schedule: cron `0 2 * * *` thay vì `0 9 * * *`

### Reflection Solutions

**Q1**: redis-benchmark = version comparison (repeatable, simple). memtier/custom = capacity planning (realistic, complex).

**Q2**: Không có con số tuyệt đối. Rule: threshold = SLO p99 / 10. Nếu SLO p99 = 50ms → threshold = 5ms.

**Q3**: Localhost RTT ~0.05ms vs WAN RTT ~15ms → 300× khác biệt trong throughput per connection. Benchmark đúng topology.

**Q4**: p99 đủ cho unimodal distribution nhưng không đủ cho bimodal. Bimodal = có hai populations (fast + slow commands) → p99.9 quan trọng để bắt tail thật sự.

**Q5**: p99 = 5ms, intrinsic = 0.5µs → gap 10,000×. Phân tích: network (0.5ms RTT) + slow commands (2-4ms) + fork/eviction = gap còn lại.
