# Day 17: Pub/Sub Patterns & Limitations — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: Go (go-redis/v9)
**Docker images**: redis:7.2-alpine

> Day 17 luân phiên TypeScript (Day 16) → Go. Lab notification fanout system bằng Go.

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. SUBSCRIBE + PUBLISH — Two Terminals

**Terminal A** — subscriber:

```bash
redis-cli SUBSCRIBE news
```

**Terminal B** — publisher:

```bash
redis-cli PUBLISH news "Hello from publisher"
```

**Terminal A expected output**:

```
Reading messages... (press Ctrl+C to quit)
1) "subscribe"
2) "news"
3) (integer) 1
1) "message"
2) "news"
3) "Hello from publisher"
```

**Terminal B expected output**:

```
(integer) 1
```

Số `1` = 1 subscriber đã nhận message.

---

### 1.2. PSUBSCRIBE — Pattern Matching

**Terminal A** — pattern subscriber:

```bash
redis-cli PSUBSCRIBE "news.*" "events.*"
```

**Terminal B** — publish các channel khác nhau:

```bash
# Khớp news.*
redis-cli PUBLISH news.sports "Soccer match started"
redis-cli PUBLISH news.tech "New AI model released"

# Khớp events.*
redis-cli PUBLISH events.concert "Taylor Swift live"
redis-cli PUBLISH events.meetup "Go meetup tonight"

# Không khớp pattern nào
redis-cli PUBLISH weather.sunny "It is sunny"
redis-cli PUBLISH chat.general "Hello everyone"
```

**Terminal A expected output** (mỗi message format):

```
1) "pmessage"
2) "news.*"
3) "news.sports"
4) "Soccer match started"
```

`news.sports` và `news.tech` khớp `news.*`. `events.concert` và `events.meetup` khớp `events.*`. `weather.sunny` và `chat.general` không khớp → không hiển thị.

---

### 1.3. PUBSUB CHANNELS / NUMSUB / NUMPAT

```bash
# Liệt kê tất cả active channels
redis-cli PUBSUB CHANNELS

# Đếm subscriber count cho channel cụ thể
redis-cli PUBSUB NUMSUB news events.concert

# Đếm tổng pattern subscription count
redis-cli PUBSUB NUMPAT
```

**Expected output** (ví dụ):

```
1) "news"
2) "news.sports"
3) "news.tech"
4) "events.concert"
5) "events.meetup"
channel:news
(integer) 1
channel:events.concert
(integer) 1
(integer) 2
```

- `PUBSUB CHANNELS`: danh sách channel đang có subscriber
- `PUBSUB NUMSUB`: trả về cặp `channel N` cho mỗi channel
- `PUBSUB NUMPAT`: trả về tổng số pattern subscriptions đang active

> **Ghi chú**: NUMPAT là chỉ số quan trọng. Nếu > 1000 → CPU overhead đáng kể mỗi PUBLISH.

---

### 1.4. Sharded Pub/Sub — SPUBLISH / SSUBSCRIBE (Redis 7.0+)

> Standalone Redis 7.0+: SPUBLISH/SSUBSCRIBE hoạt động nhưng không khác gì PUBLISH/SUBSCRIBE (không có cluster sharding). Nếu có Redis Cluster 6+ node, bước này demo trực tiếp trong cluster.

**Terminal A** — shard subscriber:

```bash
redis-cli SSUBSCRIBE cache:invalidate
```

**Terminal B** — shard publisher:

```bash
redis-cli SPUBLISH cache:invalidate "user:123:profile"
```

**Terminal A expected output**:

```
1) "ssubscribe"
2) "cache:invalidate"
3) (integer) 1
1) "smessage"
2) "cache:invalidate"
3) "user:123:profile"
```

So sánh: `smessage` (sharded) vs `message` (classic). Cùng format, chỉ khác keyword.

**Kiểm tra shard channels**:

```bash
redis-cli PUBSUB SHARDCHANNELS
redis-cli PUBSUB SHARDNUMSUB cache:invalidate
```

---

### 1.5. Subscriber Disconnect — Message Loss Demo

**Bước 5a**: Terminal A subscribe:

```bash
redis-cli SUBSCRIBE critical:alerts
```

**Bước 5b**: Terminal B publish 3 messages:

```bash
redis-cli PUBLISH critical:alerts "msg-001-before-disconnect"
```

**Bước 5c**: Ctrl+C Terminal A (disconnect subscriber) — ngay lập tức:

**Bước 5d**: Terminal B publish trong khi subscriber DOWN:

```bash
redis-cli PUBLISH critical:alerts "msg-002-during-disconnect"
redis-cli PUBLISH critical:alerts "msg-003-during-disconnect"
```

**Bước 5e**: Terminal A reconnect:

```bash
redis-cli SUBSCRIBE critical:alerts
```

**Bước 5f**: Terminal B publish sau reconnect:

```bash
redis-cli PUBLISH critical:alerts "msg-004-after-reconnect"
```

**Expected**: Terminal A chỉ nhận `msg-001-before-disconnect` và `msg-004-after-reconnect`. `msg-002` và `msg-003` bị miss hoàn toàn — không recoverable.

**Expected output Terminal A**:

```
1) "subscribe"
2) "critical:alerts"
3) (integer) 1
1) "message"
2) "critical:alerts"
3) "msg-001-before-disconnect"
--- subscriber DOWN here, Ctrl+C ---
1) "subscribe"
2) "critical:alerts"
3) (integer) 1
1) "message"
2) "critical:alerts"
3) "msg-004-after-reconnect"
```

> **Key lesson**: `msg-002` và `msg-003` mất vĩnh viễn. Redis Pub/Sub không persistence. Đây là bằng chứng rõ ràng nhất: **Pub/Sub = fire-and-forget, at-most-once delivery**.

---

### 1.6. Slow Consumer Buffer Protection

```bash
# Kiểm tra cấu hình hiện tại
redis-cli CONFIG GET client-output-buffer-limit
```

**Expected output**:

```
1) "client-output-buffer-limit"
2) "normal 0 0 0 pubsub 32mb 8mb 60 slave 64mb 16mb 60 replica 64mb 16mb 60 0 0 0"
```

Format: `class hard_limit soft_limit soft_seconds`

> **Lưu ý**: Cấu hình mặc định `pubsub 32mb 8mb 60` — Redis sẽ disconnect subscriber nếu output buffer đạt 32MB (hard) hoặc vượt 8MB trong 60 giây (soft). Đây là slow consumer protection.

---

## 2. Hands-on Lab (60-70 phút)

### Scenario

Implement **notification fanout system**:

- 3 producer instances publish vào channel `notifications:{user_id}`
- 5 subscriber instances, mỗi subscriber lắng nghe pattern `notifications:*`
- Metrics: số message published, số message received per subscriber
- Phần A: chạy normal → verify hơi balance
- Phần B: kill 1 subscriber → publish thêm → measure message loss
- Phần C: chuyển sang Redis Streams + consumer group → verify zero loss

---

### Setup: Docker Compose

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-pubsub-lab
    ports:
      - "6379:6379"
    command: >
      redis-server
      --loglevel notice
      --client-output-buffer-limit pubsub 32mb 8mb 60
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  redis-pubsub-data:
```

---

### Go Module Setup

**File**: `go.mod`

```go
module redis-pubsub-lab

go 1.21

require github.com/redis/go-redis/v9 v9.5.1
```

---

### Starter Code

**File**: `cmd/lab/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
)

// Metrics tracks message counts per subscriber.
type Metrics struct {
	mu       sync.RWMutex
	received map[string]*atomic.Int64
}

func NewMetrics() *Metrics {
	return &Metrics{
		received: make(map[string]*atomic.Int64),
	}
}

func (m *Metrics) Register(id string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.received[id]; !ok {
		m.received[id] = new(atomic.Int64)
	}
}

func (m *Metrics) Inc(id string) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if counter, ok := m.received[id]; ok {
		counter.Add(1)
	}
}

func (m *Metrics) Get(id string) int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if counter, ok := m.received[id]; ok {
		return counter.Load()
	}
	return 0
}

func (m *Metrics) Snapshot() map[string]int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	snap := make(map[string]int64)
	for k, v := range m.received {
		snap[k] = v.Load()
	}
	return snap
}

var (
	totalPublished atomic.Int64
	totalLost     atomic.Int64
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	rdb := redis.NewClient(&redis.Options{
		Addr:    "localhost:6379",
		PoolSize: 50,
	})
	defer rdb.Close()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Cannot connect to Redis: %v", err)
	}
	fmt.Println("Connected to Redis OK")

	metrics := NewMetrics()

	// ───────────────────────────────────────────────
	// PART A: Normal run — verify balanced fanout
	// ───────────────────────────────────────────────
	fmt.Println("\n=== PART A: Normal Fanout (5 subscribers, 3 producers) ===")
	partA(ctx, rdb, metrics)
	printSnapshot("PART A", metrics)

	// ───────────────────────────────────────────────
	// PART B: Kill 1 subscriber — measure message loss
	// ───────────────────────────────────────────────
	fmt.Println("\n=== PART B: Subscriber Kill — Message Loss ===")
	partB(ctx, rdb, metrics)
	printSnapshot("PART B", metrics)

	// ───────────────────────────────────────────────
	// PART C: Redis Streams — verify zero loss
	// ───────────────────────────────────────────────
	fmt.Println("\n=== PART C: Redis Streams — Zero Loss ===")
	partC(ctx, rdb, metrics)
	printSnapshot("PART C", metrics)
}
```

---

### Step 1: Part A — Normal Fanout (5 subscribers, 3 producers)

Hoàn thiện hàm `partA`:

```go
// partA: 3 producers publish 100 msgs each; 5 subscribers receive via PSUBSCRIBE.
func partA(ctx context.Context, rdb *redis.Client, metrics *Metrics) {
	const (
		numProducers    = 3
		numSubscribers   = 5
		msgsPerProducer = 100
	)

	var wg sync.WaitGroup

	// --- Subscribers ---
	for i := 0; i < numSubscribers; i++ {
		wg.Add(1)
		subID := fmt.Sprintf("sub-A-%d", i)
		metrics.Register(subID)

		go func(id string) {
			defer wg.Done()

			// TẠO CONNECTION RIÊNG cho subscriber
			subConn := rdb.duplicate()
			defer subConn.Close()

			pubsub := subConn.PSubscribe(ctx, "notifications:*")
			defer pubsub.Close()

			_, err := pubsub.Receive(ctx)
			if err != nil {
				log.Printf("[%s] Subscribe error: %v", id, err)
				return
			}
			fmt.Printf("[%s] Subscribed to pattern 'notifications:*'\n", id)

			ch := pubsub.Channel()
			received := int64(0)

			for {
				select {
				case <-ctx.Done():
					return
				case msg, ok := <-ch:
					if !ok {
						return
					}
					metrics.Inc(id)
					received++
				}
			}
		}(subID)
	}

	// Đợi subscribers ready
	time.Sleep(500 * time.Millisecond)

	// --- Producers ---
	for p := 0; p < numProducers; p++ {
		wg.Add(1)
		prodID := fmt.Sprintf("prod-A-%d", p)

		go func(id string, instance int) {
			defer wg.Done()

			cmdConn := rdb
			for i := 0; i < msgsPerProducer; i++ {
				userID := (instance*msgsPerProducer + i) % 500
				channel := fmt.Sprintf("notifications:user:%d", userID)
				payload := fmt.Sprintf(`{"producer":"%s","user_id":%d,"seq":%d}`, id, userID, i)

				n, err := cmdConn.Publish(ctx, channel, payload).Result()
				if err != nil {
					log.Printf("[%s] Publish error: %v", id, err)
					continue
				}

				totalPublished.Add(1)
				_ = n // subscriber count, not used here

				time.Sleep(1 * time.Millisecond)
			}
			fmt.Printf("[%s] Published %d messages\n", id, msgsPerProducer)
		}(prodID, p)
	}

	// Đợi producers done
	wg.Wait()
	time.Sleep(1 * time.Second)
}
```

**Expected output Part A**:

```
Connected to Redis OK

=== PART A: Normal Fanout (5 subscribers, 3 producers) ===
[sub-A-0] Subscribed to pattern 'notifications:*'
[sub-A-1] Subscribed to pattern 'notifications:*'
[sub-A-2] Subscribed to pattern 'notifications:*'
[sub-A-3] Subscribed to pattern 'notifications:*'
[sub-A-4] Subscribed to pattern 'notifications:*'
[prod-A-0] Published 100 messages
[prod-A-1] Published 100 messages
[prod-A-2] Published 100 messages

PART A Snapshot:
  sub-A-0: ~60-65   (slight variation due to async timing)
  sub-A-1: ~60-65
  sub-A-2: ~60-65
  sub-A-3: ~60-65
  sub-A-4: ~60-65
  Total received: ~300-325   (may be slightly less than published due to timing)
  Total published: 300
```

> **Hint**: Tổng received có thể nhỏ hơn tổng published vì subscriber goroutine chưa kịp đọc hết trước khi `wg.Wait()` release. Đây là race condition bình thường trong async pub/sub.

---

### Step 2: Part B — Kill Subscriber Mid-flight → Measure Loss

Hoàn thiện hàm `partB`:

```go
// partB: 5 subscribers; kill sub-B-killer at msg 50; publish 200 more → measure loss.
func partB(ctx context.Context, rdb *redis.Client, metrics *Metrics) {
	const (
		numSubscribers  = 5
		killAtCount    = 50   // kill subscriber after receiving this many
		publishAfterKill = 200
	)

	var wg sync.WaitGroup
	var killMu sync.Mutex
	killTargets := make(map[string]bool)

	// --- Subscribers ---
	for i := 0; i < numSubscribers; i++ {
		wg.Add(1)
		subID := fmt.Sprintf("sub-B-%d", i)
		metrics.Register(subID)
		isKiller := (i == 0) // kill subscriber 0

		go func(id string, doKill bool) {
			defer wg.Done()

			subConn := rdb.duplicate()
			defer subConn.Close()

			pubsub := subConn.PSubscribe(ctx, "notifications:*")
			defer pubsub.Close()

			_, err := pubsub.Receive(ctx)
			if err != nil {
				log.Printf("[%s] Subscribe error: %v", id, err)
				return
			}
			fmt.Printf("[%s] Subscribed (kill=%v)\n", id, doKill)

			ch := pubsub.Channel()
			received := int64(0)

			for {
				select {
				case <-ctx.Done():
					return
				case msg, ok := <-ch:
					if !ok {
						return
					}
					metrics.Inc(id)
					received++

					// Kill subscriber after reaching threshold
					if doKill && received >= killAtCount {
						killMu.Lock()
						killTargets[id] = true
						killMu.Unlock()

						fmt.Printf("[%s] *** KILLED at msg %d ***\n", id, received)
						return
					}
				}
			}
		}(subID, isKiller)
	}

	// Đợi subscribers ready
	time.Sleep(500 * time.Millisecond)

	// --- Pre-kill publishes ---
	var preKillWg sync.WaitGroup
	preKillWg.Add(1)
	go func() {
		defer preKillWg.Done()
		cmdConn := rdb
		for i := 0; i < 100; i++ {
			channel := fmt.Sprintf("notifications:user:%d", i%50)
			payload := fmt.Sprintf(`{"phase":"pre-kill","user_id":%d}`, i)
			cmdConn.Publish(ctx, channel, payload)
			totalPublished.Add(1)
		}
		fmt.Println("[prod] Published 100 pre-kill messages")
	}()
	preKillWg.Wait()

	// Đợi kill subscriber chắc chắn đã chạm threshold
	time.Sleep(1 * time.Second)

	// Check kill status
	killMu.Lock()
	wasKilled := killTargets["sub-B-0"]
	killMu.Unlock()

	if wasKilled {
		fmt.Println("[lab] Confirmed: sub-B-0 killed. Publishing 200 more messages...")
	} else {
		fmt.Println("[lab] WARNING: sub-B-0 not killed yet, continuing...")
	}

	// --- Post-kill publishes (all lost for sub-B-0) ---
	var postKillWg sync.WaitGroup
	postKillWg.Add(1)
	go func() {
		defer postKillWg.Done()
		cmdConn := rdb
		for i := 0; i < publishAfterKill; i++ {
			channel := fmt.Sprintf("notifications:user:%d", i%50)
			payload := fmt.Sprintf(`{"phase":"post-kill","user_id":%d}`, i)
			cmdConn.Publish(ctx, channel, payload)
			totalPublished.Add(1)
		}
		fmt.Println("[prod] Published 200 post-kill messages")
	}()
	postKillWg.Wait()

	wg.Wait()
	time.Sleep(500 * time.Millisecond)

	// Calculate loss
	snap := metrics.Snapshot()
	subB0 := snap["sub-B-0"]
	subB1 := snap["sub-B-1"]

	// sub-B-0 should have received ~killAtCount before kill, then 0 post-kill
	// sub-B-1 (alive) should have received all ~300 messages
	fmt.Printf("\n[lab] PART B loss analysis:\n")
	fmt.Printf("  sub-B-0 (killed):  received ~%d (pre-kill only)\n", subB0)
	fmt.Printf("  sub-B-1 (alive):   received ~%d (all phases)\n", subB1)
	fmt.Printf("  Estimated loss for sub-B-0: ~%d messages\n", publishAfterKill)
	fmt.Printf("  Loss rate: %.0f%%\n", float64(publishAfterKill)/float64(100+publishAfterKill)*100)
}
```

**Expected output Part B**:

```
=== PART B: Subscriber Kill — Message Loss ===
[sub-B-0] Subscribed (kill=True)
[sub-B-1] Subscribed (kill=False)
[sub-B-2] Subscribed (kill=False)
[sub-B-3] Subscribed (kill=False)
[sub-B-4] Subscribed (kill=False)
[prod] Published 100 pre-kill messages
[sub-B-0] *** KILLED at msg 50 ***
[lab] Confirmed: sub-B-0 killed. Publishing 200 more messages...
[prod] Published 200 post-kill messages

[lab] PART B loss analysis:
  sub-B-0 (killed):  received ~50 (pre-kill only)
  sub-B-1 (alive):  received ~300 (all phases)
  Estimated loss for sub-B-0: ~200 messages
  Loss rate: 67%
```

> **Key observation**: sub-B-0 miss ~200 messages từ post-kill phase. Những message đó không được lưu ở đâu cả — vĩnh viễn mất. Đây là message loss trong Pub/Sub.

---

### Step 3: Part C — Redis Streams → Zero Loss

Hoàn thiện hàm `partC`:

```go
// partC: Streams + consumer group — verify zero loss even after reconnect.
func partC(ctx context.Context, rdb *redis.Client, metrics *Metrics) {
	const (
		streamKey   = "notifications:stream"
		groupName   = "notification-processors"
		consumerName = "consumer-C-0"
		msgsToSend  = 200
	)

	// Clean up from previous runs
	rdb.Del(ctx, streamKey)
	rdb.XGroupDestroy(ctx, streamKey, groupName, 0)

	// Create consumer group (starts from new messages)
	err := rdb.XGroupCreateMkStream(ctx, streamKey, groupName, "0").Err()
	if err != nil {
		log.Printf("[%s] XGroupCreate error (may already exist): %v", consumerName, err)
	}

	metrics.Register(consumerName)

	// --- Producer: XADD instead of PUBLISH ---
	go func() {
		cmdConn := rdb
		for i := 0; i < msgsToSend; i++ {
			payload := fmt.Sprintf(`{"seq":%d,"ts":"%s"}`, i, time.Now().Format(time.RFC3339))
			id, err := cmdConn.XAdd(ctx, &redis.XAddArgs{
				Stream: streamKey,
				ID:     "*",
				Values: map[string]interface{}{"data": payload},
			}).Result()
			if err != nil {
				log.Printf("[prod-streams] XADD error: %v", err)
				continue
			}
			totalPublished.Add(1)
			_ = id
		}
		fmt.Printf("[prod-streams] XADD %d messages\n", msgsToSend)
	}()

	// --- Consumer: XREADGROUP with blocking ---
	go func() {
		subConn := rdb.duplicate()
		defer subConn.Close()

		readCount := int64(0)

		for readCount < msgsToSend {
			// BLOCK 3 seconds waiting for new messages
			streams, err := subConn.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    groupName,
				Consumer: consumerName,
				Streams:  []string{streamKey, ">"},
				Count:    50,
				Block:    3 * time.Second,
			}).Result()

			if err != nil {
				if err == redis.Nil {
					// Timeout — no new messages
					continue
				}
				log.Printf("[%s] XREADGROUP error: %v", consumerName, err)
				continue
			}

			for _, stream := range streams {
				for _, msg := range stream.Messages {
					metrics.Inc(consumerName)
					readCount++

					// XACK after successful processing
					subConn.XAck(ctx, streamKey, groupName, msg.ID)
				}
			}
		}

		fmt.Printf("[%s] XREADGROUP received and ACKed %d messages\n", consumerName, readCount)
	}()

	time.Sleep(5 * time.Second)

	snap := metrics.Snapshot()
	received := snap[consumerName]

	fmt.Printf("\n[lab] PART C stream analysis:\n")
	fmt.Printf("  Stream messages sent: %d\n", msgsToSend)
	fmt.Printf("  Consumer received:   %d\n", received)
	fmt.Printf("  Messages ACKed:       %d\n", received)
	fmt.Printf("  Loss:                %d (should be 0)\n", msgsToSend-int(received))

	if received == int64(msgsToSend) {
		fmt.Println("  RESULT: ZERO LOSS ✓")
	} else {
		fmt.Printf("  RESULT: Loss detected (%.1f%%)\n",
			float64(msgsToSend-int(received))/float64(msgsToSend)*100)
	}
}
```

**Expected output Part C**:

```
=== PART C: Redis Streams — Zero Loss ===
[prod-streams] XADD 200 messages
[consumer-C-0] XREADGROUP received and ACKed 200 messages

[lab] PART C stream analysis:
  Stream messages sent: 200
  Consumer received:    200
  Messages ACKed:       200
  Loss:                 0 (should be 0)
  RESULT: ZERO LOSS ✓
```

> **Key insight**: Streams lưu message vào stream. Consumer đọc bằng XREADGROUP. Sau khi xử lý, XACK xác nhận. Nếu consumer crash trước XACK, message vẫn nằm trong pending list và được replay bởi consumer khác.

---

### Helper Function

Thêm vào cuối file:

```go
func printSnapshot(label string, metrics *Metrics) {
	snap := metrics.Snapshot()
	fmt.Printf("\n%s Snapshot:\n", label)
	for id, count := range snap {
		fmt.Printf("  %s: %d\n", id, count)
	}
	total := int64(0)
	for _, v := range snap {
		total += v
	}
	fmt.Printf("  Total received: %d\n", total)
	fmt.Printf("  Total published: %d\n", totalPublished.Load())
}
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge: Cache Invalidation System — 50 Instances × 100K Invalidations/s

**Scenario**:

```
50 microservice instances (Kubernetes pods)
  × 100K key invalidations per second total (2K/instances)
  × Cache key pattern: "product:{id}", "user:{id}", "order:{id}"

Bốn approaches để so sánh:

  A. Global Pub/Sub (PUBLISH/SUBSCRIBE)
  B. Sharded Pub/Sub (SPUBLISH/SSUBSCRIBE, Redis 7.0+)
  C. Redis Streams + Consumer Group
  D. Kafka (external broker)

Yêu cầu: phân tích bandwidth, latency, durability, operational complexity.
```

---

### 3a. Bandwidth & Latency Analysis

**Giả định**:

```
msg_size = 64 bytes (cache key invalidation payload)
instances = 50
total_invalidations/s = 100,000
avg_invalidations/instance = 2,000
fanout: mỗi invalidation cần gửi tới tất cả 50 instances
```

Điền vào bảng:

| Approach | Bandwidth (per invalidation) | Bandwidth (total/s) | Latency p50 | Latency p99 | Notes |
|---|---|---|---|---|---|
| A. Global Pub/Sub | 64B × 50 = 3.2KB | 320 MB/s | < 1ms | ~5ms | Broadcast all nodes |
| B. Sharded Pub/Sub | 64B × 1 = 64B | 6.4 MB/s | < 1ms | ~5ms | Direct to shard |
| C. Streams + CG | 64B × 1 = 64B | 6.4 MB/s | < 1ms | ~10ms | XADD overhead |
| D. Kafka | 64B × 3 replicas = 192B | 19.2 MB/s | 5-20ms | ~50ms | Disk-backed |

**Câu hỏi 1**: Global Pub/Sub bandwidth = 320 MB/s — tại sao con số này có thể là vấn đề trong 6-node cluster?

> **Hint**: 320 MB/s × 6 nodes = 1.92 GB/s inter-node traffic. 10Gbps NIC chỉ đủ cho 5 instances trước khi saturate.

---

### 3b. Durability & Reliability Analysis

Điền vào bảng:

| Aspect | A. Global Pub/Sub | B. Sharded Pub/Sub | C. Streams + CG | D. Kafka |
|---|---|---|---|---|
| Delivery guarantee | At-most-once | At-most-once | At-least-once | At-least-once / Exactly-once |
| Message persistence | None | None | In-memory (AOF) | Disk (configurable) |
| Replay capability | No | No | Yes | Yes |
| Consumer crash handling | Message lost | Message lost | Pending → replay | Pending → replay |
| Network blip (1s) | ~2K lost invalidations | ~2K lost invalidations | 0 lost (XACK deferred) | 0 lost |
| Infra complexity | Very low | Very low | Low | High |

**Câu hỏi 2**: Cache invalidation miss — impact thực sự là gì?

> **Hint**: Miss invalidation = instance vẫn dùng stale cache = next read serve stale data = acceptable vì DB read sẽ get fresh data. NOT a financial loss.

---

### 3c. Operational Complexity Analysis

| Aspect | A. Global Pub/Sub | B. Sharded Pub/Sub | C. Streams + CG | D. Kafka |
|---|---|---|---|---|
| Setup complexity | Trivial | Trivial | Simple | Complex (broker config) |
| Monitoring | PUBSUB NUMSUB | PUBSUB SHARDNUMSUB | XPENDING, XLEN | Kafka consumer lag |
| Scaling | Hard (fanout bottleneck) | Medium (shard per pattern) | Easy (add consumers) | Easy (partitions) |
| Team expertise | Low | Low | Medium | High |
| Infrastructure cost | Redis only | Redis only | Redis only | Kafka cluster + ZK |

---

### 3d. Recommended Architecture

**Đề xuất**: Sharded Pub/Sub + local L1 cache + short TTL

```
Architecture:

  Service Instance (×50)
       │
       ├── L1: Local in-memory cache (Go: sync.Map, 1000 entries, TTL 5s)
       │        │
       │        └── Cache miss → L2
       │
       └── L2: Redis Pub/Sub (SPUBLISH/SSUBSCRIBE)
                │
                └── Cache key invalidated → broadcast to all 50 instances
                                        → each instance DEL from L1

Design details:

  L1 cache config:
    - Max entries: 1000 per instance
    - TTL: 5 seconds (short — limits stale window)
    - Eviction: LRU

  Invalidation flow:
    1. Service A updates product:123
    2. Service A: SPUBLISH "cache:invalidate:product:123" "product:123"
    3. 49 instances SUBSCRIBE pattern "cache:invalidate:*"
    4. Each instance: DEL local key "product:123" from L1
    5. Next read: fetch from DB, repopulate L1

  L1 TTL = 5s → max stale window = 5s even if invalidation missed

Trade-off vs Streams:
  - Simpler: no XACK, no consumer group, no pending list
  - Acceptable loss: L1 TTL bounds stale window
  - No extra infrastructure: Redis only
  - Streams: more reliable but 10x operational complexity for this use case
```

**Câu hỏi 3**: Tại sao NOT dùng Kafka cho cache invalidation?

> **Hint**: Kafka cần separate cluster, ZK/KRaft, consumer group management, lag monitoring. Cache invalidation là ephemeral signal — miss = next DB read fix. Kafka over-engineering = wasted resources và operational burden.

---

### 3e. Final Recommendation Table

| Use case | Recommendation | Rationale |
|---|---|---|
| Cache invalidation broadcast (50-200 instances) | **B: Sharded Pub/Sub + L1 TTL** | Simplicity, acceptable loss (TTL bound), no extra infra |
| Financial notification (guaranteed delivery) | **C: Streams + CG hoặc D: Kafka** | At-least-once required, replay needed |
| Typing indicator (ephemeral, <100ms) | **A: Global Pub/Sub** | Ultra-low latency, miss = acceptable |
| Real-time dashboard (1000+ concurrent viewers) | **D: Kafka + WebSocket** | Persistence + fanout + replay |
| Service discovery / topology change | **A: Global Pub/Sub** | Ephemeral, miss = retry = acceptable |
| Audit log (compliance) | **D: Kafka** | Disk persistence, retention, exactly-once |

---

## 4. Reflection Questions

### Question 1: Khi nào Pub/Sub là lựa chọn đúng dù không durable?

Pub/Sub đúng khi message có **acceptable loss** — tức miss không gây ra hậu quả nghiêm trọng:

- Cache invalidation: miss = stale cache = next DB read fix
- Typing indicator: miss = indicator biến mất = acceptable
- Presence/heartbeat: miss = timeout = acceptable
- Real-time dashboard: miss = hơi cũ = acceptable

Nguyên tắc: **Nếu message loss gây financial loss, compliance violation, hoặc customer-visible bug → KHÔNG dùng Pub/Sub**.

### Question 2: PSUBSCRIBE với 10K pattern — bạn xử lý CPU overhead ra sao?

10K PSUBSCRIBE patterns là **production anti-pattern**:

- Mỗi PUBLISH phải match 10K regex patterns = ~100ms CPU = block Redis main thread
- Giải pháp từng bước:
  1. **Benchmark**: `redis-cli --intrinsic-latency 100` để confirm CPU overhead
  2. **Audit patterns**: 10K patterns thường là 10K specific wildcards thay vì 10K broad patterns
  3. **Convert to specific SUBSCRIBE**: mỗi pattern `user:*` thay bằng 10-50 specific subscriptions
  4. **Use channel hierarchy**: `events:user:created`, `events:user:deleted` thay vì `events:*`
  5. **Monitor NUMPAT**: alert khi > 500

> **Key rule**: PSUBSCRIBE nên dùng cho 5-50 patterns tổng, không phải 10K.

### Question 3: Trade-off giữa simplicity và reliability trong messaging?

Simplicity và reliability luôn có trade-off:

| | Simplicity wins | Reliability wins |
|---|---|---|
| **Architecture** | Pub/Sub (1 Redis command) | Kafka + Schema registry + Consumer group |
| **Ops** | 1 engineer hiểu | 3+ engineers với Kafka expertise |
| **Cost** | Redis only | Kafka cluster + monitoring + schema registry |
| **Failure mode** | Message loss | Consumer lag, partition rebalance |
| **Time to production** | 1 ngày | 2-4 tuần |

**Framework để quyết định**:

```
1. Đo impact của message loss:
   - Financial/compliance loss?  → Reliability wins
   - Miss = self-healing (DB read)? → Simplicity wins

2. Đo scale:
   - < 50 subscribers, < 10K msg/s?  → Pub/Sub OK
   - > 500 subscribers, > 100K msg/s? → Kafka/NATS needed

3. Đo team expertise:
   - Redis-only team? → Start with Pub/Sub/Streams
   - Kafka-experienced team? → Kafka for everything

4. Đo replay need:
   - Need replay for debugging/onboarding? → Streams or Kafka
   - No replay needed? → Pub/Sub OK
```

> **Bottom line**: Không có "best solution fits all". Chọn dựa trên impact of loss, scale, team expertise, và time-to-production.

### Question 4: Sharded Pub/Sub vs global PUBLISH — khi nào sự khác biệt thực sự quan trọng?

Sự khác biệt chỉ quan trọng trong **Redis Cluster**:

- **Standalone Redis**: SPUBLISH = PUBLISH (không có inter-node traffic) → không khác gì
- **Redis Cluster**: Global PUBLISH = broadcast toàn bộ cluster (6 node = 6× bandwidth). SPUBLISH = direct to shard (1× bandwidth).

Use case cần SPUBLISH:
- Cache invalidation trong 6+ node cluster với >50K invalidations/s
- High-frequency fanout trong cluster environment
- Bandwidth-critical multi-region deployment

Use case global PUBLISH vẫn OK:
- Single-node Redis hoặc Sentinel (không có cluster sharding)
- < 10K invalidations/s (bandwidth không phải bottleneck)
- Development/staging environment

### Question 5: Nếu bạn thiết kế lại Discord notification system từ đầu, bạn sẽ chọn gì?

Discord dùng Pub/Sub cho ephemeral signals (typing indicator, presence) — đúng. Nhưng nếu thiết kế lại:

```
Layer 1 (Real-time presence): Pub/Sub
  - Typing indicator, online/offline
  - Miss = acceptable (3-second window, client-side timeout)
  - Architecture: channel per guild, Pub/Sub với pattern per user

Layer 2 (Message delivery): Persistent queue
  - Actual chat messages
  - NOT Pub/Sub (message loss unacceptable)
  - Architecture: Redis Streams hoặc Kafka
  - Consumer group: fan-out to active user connections

Layer 3 (Delivery receipt): At-least-once
  - Read receipt, reaction
  - Need acknowledgment
  - Architecture: Redis Streams + XACK

Layer 4 (Offline sync): Disk-backed storage
  - User offline → messages stored
  - On reconnect → replay from stream
  - Architecture: Kafka hoặc PostgreSQL append-only log
```

**Key lesson**: Mỗi message type có reliability requirement khác nhau. Không dùng 1 giải pháp cho tất cả. Mix and match theo impact of loss.

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết và giải thích lý do. Đọc sau khi đã thử làm bài tập.

---

### Warm-up Solutions

**1.1-1.2**: SUBSCRIBE vs PSUBSCRIBE — điểm khác biệt:

- `SUBSCRIBE news` → nhận đúng channel `news`
- `PSUBSCRIBE "news.*"` → nhận `news.sports`, `news.tech`, `news.politics` (pattern matching)
- `SUBSCRIBE news.*` → ERROR (SUBSCRIBE không hỗ trợ pattern, chỉ PSUBSCRIBE)

**1.3**: `PUBSUB NUMPAT` là chỉ số CPU overhead indicator:
- < 100 patterns: negligible (< 0.01ms/PUBLISH)
- 100-1000 patterns: measurable (~1-10ms/PUBLISH)
- > 1000 patterns: significant risk → production alert needed

**1.5**: Message loss confirmation — 2 messages trong disconnect window bị miss hoàn toàn. Không có retry, không có recovery. Đây là bằng chứng rõ ràng: **Pub/Sub = at-most-once delivery**.

---

### Hands-on Lab Solutions

**Part A — Balanced fanout explanation**:

Mỗi PUBLISH gửi message tới 5 subscribers cùng lúc. Tổng received = 5 × 300 = 1500 "delivery events". Mỗi subscriber nhận ~60% messages vì:
- Messages được phân phối theo user ID (`notifications:user:N`)
- Mỗi subscriber nhận tất cả messages (pattern match), nhưng goroutine scheduling + channel buffer tạo variation
- Timing race giữa `wg.Wait()` và subscriber channel receive

**Part B — Message loss calculation**:

- sub-B-0 kill tại message ~50 (pre-kill phase)
- Post-kill: 200 messages được publish
- sub-B-0 miss toàn bộ 200 post-kill messages
- sub-B-1 (alive) nhận ~300 messages (all phases)
- Loss rate: 200/(50+200) = 80% trong post-kill window cho sub-B-0

Đây là **acceptable cho cache invalidation** (L1 TTL 5s bound stale window) nhưng **không acceptable cho financial notification**.

**Part C — Streams zero loss explanation**:

- `XADD` ghi message vào stream (persistent trong Redis memory/AOF)
- `XREADGROUP` đọc message từ stream, message không bị xóa cho đến `XACK`
- Nếu consumer crash giữa chừng (chưa XACK): message vẫn trong pending list
- Consumer reconnect cùng consumer name → đọc pending bằng `XREADGROUP ... STREAMS key 0` hoặc recover consumer khác bằng `XAUTOCLAIM`
- Zero loss = at-least-once delivery

**Key code path for reconnect replay**:

```go
// Read pending (unACKed) messages after reconnect
streams, _ := redis.XREADGROUP(ctx, "cg1", "c1",
    "streams", "notifications:stream", "0").Result()
// "0" = read pending entries owned by this consumer (not just new ">")
```

---

### Challenge Solutions

**3a — Bandwidth calculations**:

```
Global Pub/Sub (Redis Cluster):
  msg_size = 64 bytes
  fanout = 50 instances
  msgs/s = 100,000
  Bandwidth = 64B × 50 × 100,000 = 320,000,000 B/s = 320 MB/s

6-node cluster inter-node:
  320 MB/s × 6 = 1.92 GB/s
  10Gbps NIC = 1.25 GB/s max theoretical
  → 1.92 GB/s > 1.25 GB/s → NETWORK SATURATION

Sharded Pub/Sub:
  SPUBLISH gửi trực tiếp tới shard chứa slot của channel
  Bandwidth = 64B × 100,000 = 6.4 MB/s
  Inter-node: 6.4 MB/s × (1 shard hit) = ~6.4 MB/s (negligible)

Savings: 320 MB/s → 6.4 MB/s = 98% bandwidth reduction
```

**3b — Cache invalidation loss impact**:

```
Miss 1 invalidation:
  1 cache key vẫn có stale value
  Next read: Redis hit → serve stale data
  User thấy: product name cũ, avatar cũ
  Fix: wait 5s (L1 TTL) hoặc invalidate lại

Miss 100K invalidations (Redis down 1s):
  100K keys vẫn stale
  Impact: user thấy stale data trong 5s window
  Recovery: automatic (TTL expiration)

vs Financial notification miss:
  User không nhận được payment confirmation
  Impact: support ticket, customer anger, potential chargeback
  Recovery: MANUALLY resend notification
```

**3d — Architecture recommendation rationale**:

```
Sharded Pub/Sub + L1 TTL chosen vì:

1. Cache invalidation là ephemeral signal
   - Miss = self-healing (next DB read)
   - L1 TTL 5s = hard bound on stale window

2. Operational simplicity
   - Chỉ cần Redis
   - Không cần Kafka cluster, ZK, consumer group
   - Dev team đã có Redis expertise

3. Bandwidth efficiency
   - SPUBLISH: 6.4 MB/s (sharded)
   - Kafka: 19.2 MB/s (3 replicas) + broker overhead

4. Latency
   - Redis SPUBLISH: < 1ms p50
   - Kafka: 5-20ms p50 (disk write + replication)

5. Trade-off: Không có durability nhưng:
   - Invalidation gửi lại nếu cần (application-level)
   - L1 TTL bound stale window
   - Đủ cho cache invalidation use case
```

**Dùng Kafka/Streams thay vì Pub/Sub khi**:
- Message loss gây compliance violation (audit log)
- Message loss gây financial loss (payment notification)
- Cần replay cho debugging hoặc new consumer onboarding
- Consumer crash → job phải được retry tự động

---

### Reflection Solutions

**Q1 — Pub/Sub đúng khi**: Impact of loss = acceptable (self-healing, user not affected, next event fixes). Không bao giờ dùng Pub/Sub khi message loss = compliance violation, financial loss, hoặc customer-visible bug.

**Q2 — PSUBSCRIBE CPU overhead**: O(N) với N = pattern count. 10K patterns = ~100ms/PUBLISH = disaster. Fix: convert to specific SUBSCRIBE, use channel hierarchy, monitor NUMPAT, alert at > 500 patterns.

**Q3 — Simplicity vs reliability**: Không có câu trả lời đúng. Dùng framework 4 câu hỏi:
1. Impact of loss?
2. Scale?
3. Team expertise?
4. Replay needed?

**Q4 — SPUBLISH vs PUBLISH**: Chỉ khác trong Redis Cluster. Standalone: identical. Cluster: SPUBLISH = 1× bandwidth, PUBLISH = N× bandwidth. Important khi bandwidth-critical hoặc > 50K invalidations/s trong cluster.

**Q5 — Discord notification redesign**: Dùng hybrid:
- Layer 1 (presence/typing): Pub/Sub (ephemeral, miss OK)
- Layer 2 (messages): Streams hoặc Kafka (persistent, replay needed)
- Layer 3 (receipts): Streams + XACK (at-least-once)
- Layer 4 (offline): Disk-backed storage (Kafka hoặc append-only DB)

**Key lesson tổng quát**: Mỗi message type có reliability requirement khác nhau. Không dùng 1 giải pháp messaging cho tất cả. Thiết kế theo impact of loss của từng message type.
