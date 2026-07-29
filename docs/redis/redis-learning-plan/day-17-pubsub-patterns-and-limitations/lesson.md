# Day 17: Pub/Sub Patterns & Limitations

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân tích được Pub/Sub mechanics bên trong: PUBLISH iterate pubsub_channels dict, SUBSCRIBE chuyển connection sang subscribe-only mode, PSUBSCRIBE pattern matching CPU overhead.
- Đánh giá được trade-off giữa Redis Pub/Sub vs Streams vs Kafka vs NATS cho từng use case cụ thể.
- Triển khai notification fanout system, nhận biết message loss khi subscriber disconnect và biết cách khắc phục.
- Cấu hình `client-output-buffer-limit pubsub` để protect khỏi slow consumer overflow.
- Quyết định đúng khi nào dùng Pub/Sub (cache invalidation broadcast, ephemeral signal) và khi nào cần Streams/Kafka (financial event, audit log, cần replay).

---

## 2. Vì sao cần học chủ đề này

### Incident 1: WebSocket Notification Mất 30% Messages Khi Rolling Deploy

Team deploy 5 WebSocket subscriber instances mới. Trong lúc rolling restart, các subscriber cũ kill connection -> reconnect -> thời gian reconnect = 2-5 giây. Trong khoảng đó, 30% notification bị miss hoàn toàn vì **Redis Pub/Sub không persistence message**.

```
Timeline:
  T+0s:  Old subscriber disconnect
  T+0s:  Redis PUBLISH "order:created" -> KHÔNG ai nhận
  T+0.5s: New subscriber reconnecting...
  T+1.2s: PUBLISH "order:created" -> miss
  T+2.1s: PUBLISH "order:created" -> miss
  T+2.5s: New subscriber READY
  T+3.0s: PUBLISH "order:created" -> nhận được
Result: 3 messages lost trong 2.5s window
```

Không ai expect behavior này vì tên "Redis" gợi ý persistence.

### Incident 2: PSUBSCRIBE Regex 10K Patterns -> Redis CPU Spike 40%

Một developer dùng PSUBSCRIBE `*:*` pattern rất rộng. Hệ thống có 10,000 pattern subscriptions. Mỗi PUBLISH phải matching tất cả 10,000 regex pattern -> Redis CPU tăng 40% chỉ vì Pub/Sub overhead, không phải application logic.

```
PUBLISH "user:123:action" ->
  Iterate 10,000 PSUBSCRIBE patterns:
    "news:*"     -> no match
    "user:*"     -> match! -> send message
    "events:*"   -> no match
    ...
    [9,997 patterns more]
CPU overhead: O(N) với N = pattern count
```

### Incident 3: Redis Cluster PUBLISH -> 6x Bandwidth ở 6-Node Cluster

Một ứng dụng chạy trên Redis Cluster 6 node (3 master + 3 replica). Dùng global PUBLISH cho tất cả message. Redis Cluster broadcast PUBLISH tới **tất cả node** -> inter-node bandwidth = N × msg_size × publish_count.

```
Scenario:
  - 1 PUBLISH "cache:invalidate"
  - 6 nodes in cluster
  - 3 application instances (mỗi instance kết nối node khác nhau)

Redis 7+ sharded Pub/Sub (SPUBLISH):
  - Message chỉ gửi tới shard chứa slot của channel
  - Bandwidth = msg_size (1x)

Redis Cluster global PUBLISH:
  - Message broadcast tới 6 node
  - Bandwidth = 6 × msg_size (6x)

Real numbers: 100K publishes/day × 1KB × 6 = 600MB inter-node traffic/day
```

**Bottom line**: Pub/Sub là công cụ mạnh cho ephemeral signal, nhưng developer thường overestimate độ tin cậy của nó. Không ai đọc kỹ docs và nhận ra: **Pub/Sub là fire-and-forget, at-most-once delivery, không persistence, không replay, không consumer group.**

---

## 3. Kiến thức nền cần có

- Redis single-threaded model và event loop (Day 1): `PUBLISH` fanout và pattern matching chạy trên main thread; slow subscriber chủ yếu gây tăng output buffer, memory pressure và disconnect, không phải tự động "block toàn bộ event loop".
- Connection pooling (Day 12): subscribe connection KHÔNG share pool với command connection -> cần separate connection cho subscribe.
- Redis Cluster basics (Day 22): global PUBLISH broadcast toàn bộ cluster, Redis 7+ sharded Pub/Sub giải quyết bandwidth issue.

---

## 4. Lý thuyết chi tiết

### 4.1. First Principles: Ephemeral Message Bus

Redis Pub/Sub là một **ephemeral (ngắn hạn) in-memory message bus**. Không có persistence, không có disk write, không có acknowledgment.

```
Conceptual model:
  ┌─────────────────────────────────────────────────────────────┐
  │                      Redis Server                             │
  │                                                          │
  │  pubsub_channels: {                                       │
  │    "order:created": [conn1, conn2, conn3],              │
  │    "user:123:notify": [conn4],                          │
  │    "cache:invalidate": [conn1, conn5]                    │
  │  }                                                       │
  │                                                          │
  │  pubsub_patterns: [                                      │
  │    {pattern: "news:*", subscribers: [conn6]},           │
  │    {pattern: "user:*", subscribers: [conn7, conn8]}      │
  │  ]                                                       │
  └─────────────────────────────────────────────────────────────┘
        ^                ^                ^
        │                │                │
   SUBSCRIBE          PUBLISH          MESSAGE
   (read-only)    (write to dict)   (send to subs)
```

**Đặc điểm cốt lõi**:
- Publisher gửi message -> Redis lookup dictionary -> gửi message tới tất cả subscriber connection.
- Message không được lưu lại.
- Subscriber không nhận message -> message đó biến mất vĩnh viễn.
- Không có delivery guarantee, không có acknowledgment, không có retry.

### 4.2. SUBSCRIBE State Machine

Khi một connection gọi SUBSCRIBE, connection đó **chuyển sang subscribe-only mode**.

```
Connection states:

NORMAL MODE:
  - Read command -> execute -> return response
  - Full RESP protocol support
  - Can do GET, SET, HGET, etc.

SUBSCRIBE MODE (after SUBSCRIBE/PSUBSCRIBE):
  - Read command -> IGNORED (only subscribe/unsubscribe allowed)
  - Server pushes messages to this connection
  - Cannot execute regular commands (GET, SET, etc.)
  - Only accepts: SUBSCRIBE, PSUBSCRIBE, UNSUBSCRIBE, PUNSUBSCRIBE

RECONNECT:
  - SUBSCRIBE state NOT preserved across reconnect
  - Client phải re-subscribe manually
  - Trong thời gian reconnect -> MISS toàn bộ message
```

**Hệ quả quan trọng**:

```go
// SAI: Dùng cùng connection cho command + subscribe
conn := redisPool.Get()
conn.Set("key", "value")       // OK (trước khi subscribe)
conn.SUBSCRIBE("channel")     // Connection chuyển sang subscribe mode

// Kể từ đây, Set() sẽ không hoạt động trên connection này
conn.Get("key")                // FAIL: connection đang ở subscribe mode

// PHẢI dùng 2 connection riêng biệt
cmdConn := redisPool.Get()    // cho command
subConn := redisPool.Get()    // cho subscribe
```

### 4.3. PUBLISH Internals

```
PUBLISH "order:created" "payload"

Server-side execution:
  1. Lookup "order:created" in pubsub_channels dict: O(1)
  2. For each subscriber connection:
     - Check connection is alive
     - Write message to connection output buffer
     - If output buffer vượt hard/soft limit -> disconnect subscriber
  3. Return subscriber count (integer)
```

**PUBLISH latency**: tăng theo số subscriber trực tiếp của channel và số pattern subscription phải match. Slow subscriber làm `omem` tăng; khi vượt `client-output-buffer-limit pubsub`, Redis ngắt connection để bảo vệ server.

```
PUBLISH cost breakdown:
  - pubsub_channels lookup: O(1) [hashtable]
  - Per subscriber send: O(msg_size)

Fanout bandwidth:
  1 channel, 100 subscribers, 1KB message
  = 100 × 1KB = 100KB bandwidth per PUBLISH

  1 channel, 1000 subscribers, 1KB message
  = 1MB bandwidth per PUBLISH

  10 channels × 100 subscribers × 1KB
  = 1MB bandwidth per batch
```

### 4.4. PSUBSCRIBE: Pattern Matching Overhead

```
PSUBSCRIBE "news:*"
PSUBSCRIBE "user:*"
PSUBSCRIBE "events:2024:*"

PUBLISH "user:123:login" ->
  Match against ALL registered PSUBSCRIBE patterns:
    "news:*"       -> no match
    "user:*"       -> MATCH (regex "user:.*")
    "events:*"     -> no match
  -> Send message to "user:*" subscribers
```

**CPU overhead của PSUBSCRIBE**:

```
Pattern count | Regex matching per PUBLISH | CPU overhead
1             | 1 regex match              | ~0.01ms
100           | 100 regex matches           | ~1ms
1,000         | 1,000 regex matches         | ~10ms  (significant!)
10,000        | 10,000 regex matches        | ~100ms (BLOCKS Redis main thread!)
```

`CONFIG SET maxpattern` limit mặc định: 32,768 pattern. Nhưng đạt tới con số đó thì Redis đã bị CPU spike nặng.

**Best practice**: Không dùng PSUBSCRIBE khi có thể dùng nhiều specific SUBSCRIBE. Mỗi pattern subscription thay thế bằng 1-3 specific subscriptions nếu possible.

### 4.5. Sharded Pub/Sub (Redis 7+): SPUBLISH/SSUBSCRIBE

Redis 7.0 giới thiệu **Sharded Pub/Sub** giải quyết vấn đề bandwidth khi dùng Pub/Sub trong Redis Cluster.

```
Redis Cluster với global PUBLISH (before Redis 7):
  ┌──────────────────────────────────────────────────────────────┐
  │  Node1 ──PUBLISH──> broadcast ──> Node2 ──broadcast──> Node3│
  │    │                          │                               │
  │    └──> sub1                  └──> sub2                      │
  │                                                            │
  │  Message đi qua tất cả node trước khi đến subscriber        │
  │  Inter-node bandwidth: N × msg_size                        │
  └──────────────────────────────────────────────────────────────┘

Redis Cluster với SPUBLISH/SSUBSCRIBE (Redis 7+):
  ┌──────────────────────────────────────────────────────────────┐
  │  Channel "cache:invalidate" hashes to slot 1234            │
  │  Slot 1234 owned by Node2                                  │
  │                                                            │
  │  SPUBLISH "cache:invalidate" "key:abc"                      │
  │    -> Message chỉ gửi tới Node2 (shard chứa slot)           │
  │    -> SSUBSCRIBE subscriber ở Node2 nhận trực tiếp         │
  │    -> Không broadcast sang Node1, Node3                     │
  │                                                            │
  │  Inter-node bandwidth: 1 × msg_size (không phụ thuộc N)    │
  └──────────────────────────────────────────────────────────────┘
```

**So sánh global PUBLISH vs SPUBLISH trong Cluster**:

| Aspect | PUBLISH (global) | SPUBLISH (sharded) |
|---|---|---|
| Bandwidth | O(N) với N = node count | O(1) |
| Message routing | Broadcast all nodes | Direct to slot's node |
| Use case | Cross-cluster notification | Same-shard pub/sub |
| Redis version | All versions | Redis 7.0+ only |
| Subscriber groups | Subscriber bất kỳ node nào | Subscriber cùng shard |

### 4.6. ASCII Diagram: Pub/Sub Fanout vs Streams Consumer Group

```
┌─────────────────────────────────────────────────────────────────┐
│                    REDIS PUB/SUB FANOUT                         │
│                                                                 │
│   PUBLISH "channel"                                             │
│        │                                                        │
│        ├──────────────────────> Subscriber 1 (conn)            │
│        ├──────────────────────> Subscriber 2 (conn)            │
│        ├──────────────────────> Subscriber 3 (conn)            │
│        ├──────────────────────> Subscriber 4 (conn)            │
│        └──────────────────────> Subscriber 5 (conn)            │
│                                                                 │
│   at-most-once delivery (fire-and-forget)                      │
│   No persistence, No ACK, No replay                            │
│   Subscriber disconnect -> MISS message                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  REDIS STREAMS (Consumer Group)                  │
│                                                                 │
│   XADD "stream" ID payload                                      │
│        │                                                        │
│        v                                                        │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ Stream: [msg1, msg2, msg3, msg4, msg5, ...]              │  │
│   │ Consumer Group: "processors"                            │  │
│   │   Consumer A: [msg1, msg2] (pending)                    │  │
│   │   Consumer B: [msg3, msg4] (pending)                    │  │
│   │   Consumer C: [msg5] (pending)                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│        │                                                        │
│        v                                                        │
│   XACK -> Message removed from pending after success            │
│                                                                 │
│   at-least-once delivery (with ACK)                             │
│   Persistence: messages stay in stream until XACK/XTRIM         │
│   Replay: XREADGROUP GROUP g1 c1 BLOCK 0 STREAMS s $           │
│   Consumer disconnect -> pending messages -> OTHER consumer claim│
└─────────────────────────────────────────────────────────────────┘
```

### 4.7. Client-Output-Buffer Limit: Slow Consumer Protection

Redis bảo vệ server khỏi slow consumer bằng `client-output-buffer-limit`.

```
CONFIG SET client-output-buffer-limit pubsub 32mb 8mb 60

Syntax: client-output-buffer-limit <class> <hard_limit> <soft_limit> <soft_seconds>

pubsub class:
  - 32mb hard_limit:   hard cap - disconnect immediately
  - 8mb soft_limit:   soft cap - start counting
  - 60 soft_seconds:   grace period before disconnect

What happens:
  Subscriber nhận message chậm (network, process crash):
    1. Redis gửi message tới subscriber output buffer
    2. Buffer tăng > 8mb trong 60 giây -> Redis log warning
    3. Buffer đạt 32mb -> Redis DISCONNECT subscriber
    4. Subscriber miss toàn bộ message trong pending buffer
```

**Monitoring**: `CLIENT LIST` cho biết `omem` (output buffer memory usage) của từng client.

```
redis-cli CLIENT LIST | grep pubsub
id=5 addr=10.0.0.1:54321 name= sub=3 psub=1 msg_channel_len=1234567 obl=8388608 oll=0 omem=8388608

obl: output buffer length (bytes)
oll: output list length (pending messages)
omem: output memory (bytes) -> >32mb = disconnect
```

---

## 5. Trade-off Analysis

### Pub/Sub vs Streams vs Kafka vs NATS

| Dimension | Redis Pub/Sub | Redis Streams | Apache Kafka | NATS |
|---|---|---|---|---|
| **Delivery guarantee** | At-most-once | At-least-once (XACK) | At-least-once / Exactly-once | At-most-once / At-least-once |
| **Persistence** | None | In-memory + optional AOF | Disk (configurable retention) | Optional (JetStream) |
| **Replay capability** | No | Yes (XREADGROUP from last ACK) | Yes (offset-based) | Yes (JetStream) |
| **Consumer group** | No | Yes (XREADGROUP) | Yes (consumer group) | Yes (JetStream) |
| **Throughput** | Very high (in-memory) | High | Very high (disk-backed) | Very high |
| **Latency** | < 1ms | < 1ms | 5-20ms (disk) | < 1ms |
| **Message retention** | 0 seconds | Until XACK or XTRIM | Configurable (hours to infinite) | Configurable |
| **Cluster mode** | Broadcast (global) / Sharded (Redis 7+) | Hash-slot sharding | Native partitioning | Super Cluster |
| **Complexity** | Very simple | Simple | High (broker, partitions, ISR) | Low (JetStream optional) |
| **Failover** | None (message lost) | Pending message claim | Partition replication | JetStream replication |
| **Message ordering** | Per channel only | Per consumer group | Per partition | Per subject (JetStream) |
| **Operational overhead** | Very low | Low | High | Low |

### Khi nào chọn cái nào

```
Scenario: "Cache invalidation broadcast"
  -> Redis Pub/Sub ✓ (ephemeral, no replay needed, high fanout)
  -> Reason: Miss một invalidate = next read sẽ fetch từ DB
             No durability needed. Simplicity wins.

Scenario: "Financial transaction notification (audit log)"
  -> Redis Streams ✓ HOẶC Kafka ✓
  -> Reason: Miss một message = compliance violation.
             Cần replay, cần audit trail, cần ordering guarantee.

Scenario: "Real-time chat low-volume (<100 users/channel)"
  -> Redis Pub/Sub ✓
  -> Reason: Simplicity, low latency, ephemeral messages (history not critical)
             Khi user offline -> reconnect -> không cần đọc old messages

Scenario: "Real-time chat high-volume (>1000 users/channel)"
  -> NATS JetStream HOẶC Kafka ✓
  -> Reason: Cần message persistence, replay, consumer group
             Redis Pub/Sub fanout 1000 subscribers = 1MB/msg = bandwidth explosion

Scenario: "Microservice event-driven architecture"
  -> Kafka ✓ (enterprise) HOẶC NATS ✓ (lightweight)
  -> Reason: Event sourcing, audit trail, schema registry, exactly-once semantics
             Redis không đủ cho event sourcing architecture

Scenario: "Live dashboard update (biểu đồ thay đổi real-time)"
  -> Redis Pub/Sub ✓ (WebSocket gửi tiếp)
  -> Reason: Miss một update = biểu đồ hơi cũ
             Acceptable trade-off. Next update fix.
             Không cần replay 1 triệu update/giây.
```

---

## 6. Best Solution & Best Practices

### 6.1. Pub/Sub đúng cách

**Dùng Pub/Sub khi**:

```
✓ Cache invalidation broadcast
  - Microservice A update cache -> PUBLISH "cache:invalidate:user:123"
  - Microservice B, C, D SUBSCRIBE -> nhận notify, invalidate local cache
  - Miss = next DB read -> acceptable

✓ Ephemeral real-time signal (typing indicator, presence)
  - "User 456 đang typing..."
  - Miss = user không thấy typing indicator = acceptable
  - Không cần persistence

✓ Service discovery / topology change notification
  - "Node B online" -> các service cập nhật connection pool
  - Miss = retry discovery = acceptable

✓ Cross-service heartbeat / health signal
  - "Service X still alive" broadcast
  - Miss = timeout = acceptable (có fallback timer)

✓ Real-time low-volume notification (<1000 subscribers)
  - Trading platform: price alert cho 50 traders
  - Fanout = 50 × msg_size = acceptable
```

**Không dùng Pub/Sub khi**:

```
✗ Financial event / audit log
  - Cần replay, cần guarantee, cần compliance
  -> Dùng Streams hoặc Kafka

✗ Job queue / task distribution
  - Worker crash -> job phải retry
  -> Dùng Streams (XREADGROUP) hoặc Kafka

✗ High-volume fanout (>10K subscribers)
  - Bandwidth = 10K × msg_size
  - Message loss impact cao
  -> Dùng Kafka hoặc NATS

✗ Cần message ordering guarantee
  - Pub/Sub không đảm bảo ordering across channels
  -> Dùng Streams hoặc Kafka

✗ CQRS event sourcing
  - Cần replay toàn bộ event stream
  -> Dùng Kafka hoặc NATS JetStream
```

### 6.2. Anti-Patterns cần tránh

**Anti-pattern 1: Dùng Pub/Sub thay task queue**

```go
// SAI: Pub/Sub làm job queue
func processOrder(orderID string) {
    redis.PUBLISH("job:process-order", orderID)
}

// Subscriber xử lý
go func() {
    for msg := range pubsub.Channel() {
        processOrder(msg.Payload) // Worker crash -> job LOST
    }
}()

// Better: Dùng Redis Streams
func processOrder(orderID string) {
    redis.XADD("orders:stream", "*", "order_id", orderID)
}
```

**Anti-pattern 2: PSUBSCRIBE quá nhiều pattern**

```bash
# SAI: 10,000 pattern subscriptions
PSUBSCRIBE "*"
PSUBSCRIBE "*:*"
PSUBSCRIBE "events:*"

# Tốt hơn: Dùng specific subscriptions hoặc channel hierarchy
SUBSCRIBE "events:user:created"
SUBSCRIBE "events:user:deleted"
SUBSCRIBE "events:order:created"
# Hoặc dùng pattern có chọn lọc: chỉ 5-10 pattern tổng
```

**Anti-pattern 3: Subscribe + command trên cùng connection**

```go
// SAI: Cùng connection cho command và subscribe
conn := redisPool.Get()
conn.SUBSCRIBE("notifications")
// Từ đây, conn không thể execute command nào khác

// ĐÚNG: Separate connection cho subscribe
cmdConn := redisPool.Get()  // Regular commands
subConn := redisPool.Get()   // Subscribe only

go func() {
    for msg := range pubsub.Channel() {
        handleNotification(msg)
    }
}()
```

**Anti-pattern 4: Không monitor `pubsub_channels`**

```bash
# PHẢI monitor:
PUBSUB CHANNELS              # Tất cả active channels
PUBSUB NUMSUB <channel>      # Subscriber count của 1 channel
PUBSUB NUMPAT                # Pattern subscription count
INFO stats | grep pubsub      # publish/subscribe statistics
```

**Anti-pattern 5: Tin Pub/Sub có durability**

```go
// SAI assumption: "message sẽ được delivery"
redis.PUBLISH("critical:notification", "data")
// Gửi xong, subscriber đang restart
// Message đi tong. Không có retry. Không có persistence.

// ĐÚNG: Nếu cần durability -> dùng Streams
redis.XADD("critical:stream", "*", "data", "value")
// Message được lưu. Consumer có thể replay.
```

### 6.3. Architecture Pattern: Redis Pub/Sub + Streams Hybrid

Một pattern phổ biến: **Pub/Sub cho real-time, Streams cho persistence/replay**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Hybrid Architecture                           │
│                                                                 │
│  Publisher                                                      │
│    │                                                            │
│    ├──PUBLISH "notifications:urgent"──> Subscriber (real-time)│
│    │                                                            │
│    └──XADD "notifications:stream" ──────> Stream (persistence)│
│                                              │                  │
│                                              v                  │
│                                        Consumer Group           │
│                                        (replay on reconnect)    │
│                                                                 │
│  -> Real-time subscriber: nhận instant via Pub/Sub              │
│  -> Stream consumer: replay old messages khi reconnect          │
│  -> Delivery guarantee: at-least-once (Streams XACK)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Performance Considerations

### 7.1. Bandwidth Calculation

```
Single channel fanout bandwidth:
  msg_size × subscriber_count = bandwidth_per_publish

Example: Notification system
  - 3 publisher (notification service × 3 instances)
  - 5 subscriber type (email, SMS, push, in-app, webhook)
  - 50K users nhận notification
  - Message size: 500 bytes
  - Fanout: 3 × 50K × 500 bytes = 75MB/publish burst

Cluster inter-node bandwidth (global PUBLISH):
  bandwidth × node_count = inter_node_bandwidth

Example: 6-node cluster
  75MB × 6 = 450MB inter-node traffic per burst publish

Sharded Pub/Sub (Redis 7+) giải quyết:
  75MB × 1 = 75MB (chỉ shard chứa channel)
  Giảm 83% inter-node bandwidth
```

### 7.2. PSUBSCRIBE CPU Cost

```
Matching cost per PUBLISH:
  O(pattern_count) với mỗi pattern = 1 regex match

100 pattern subscriptions:
  Per PUBLISH: ~1ms CPU (negligible)

1,000 pattern subscriptions:
  Per PUBLISH: ~10ms CPU (significant - blocks Redis main thread)

10,000 pattern subscriptions:
  Per PUBLISH: ~100ms CPU (DISASTER - blocks ALL commands)

Redis 7.0: PSUBSCRIBE vẫn single-threaded, không cải thiện CPU cost
Redis 7.0: Chỉ SPUBLISH/SSUBSCRIBE là sharded, không giảm CPU overhead của PSUBSCRIBE
```

### 7.3. Slow Consumer Buffer Overflow

```
Config: client-output-buffer-limit pubsub 32mb 8mb 60

Slow consumer timeline:
  T+0:   Subscriber connected, healthy
  T+10:  Subscriber process GC pause 5 seconds
  T+10:  Redis output buffer fills 0 -> 5MB
  T+15:  Subscriber resumes, drains buffer to 0
  T+20:  Subscriber process GC pause 10 seconds
  T+20:  Redis output buffer fills 0 -> 8MB (soft limit)
  T+25:  Redis logs: "Client psub output buffer exceeded 8MB limit"
  T+30:  Subscriber still slow, buffer fills to 32MB (hard limit)
  T+30:  Redis DISCONNECTS subscriber
  T+30:  Subscriber reconnected but missed all messages in buffer
```

### 7.4. Memory Overhead

```
Per connection (subscribe mode):
  - Output buffer: 0-32MB (configurable)
  - Command buffer: ~1KB
  - Client struct: ~2KB

Per channel:
  - pubsub_channels dict entry: ~64 bytes
  - Subscriber list: N × pointer = N × 8 bytes

Per pattern subscription:
  - Pattern string: pattern length
  - Regex compiled state: ~1KB
  - Subscriber list: N × 8 bytes

Total memory for 1000 channels × 100 subscribers avg:
  - Channels: 1000 × 64 = 64KB
  - Subscriber lists: 1000 × 100 × 8 = 800KB
  - Output buffers: 1000 × ~1MB avg = 1GB (worst case)
```

### 7.5. Throughput Benchmark (estimated)

```
Hardware: 8-core CPU, 10Gbps NIC, Redis 7.2 single-threaded

PUBLISH (1 subscriber):
  Latency p50: 0.05ms, p99: 0.2ms
  Throughput: ~200K msg/sec

PUBLISH (100 subscribers):
  Latency p50: 0.5ms, p99: 2ms
  Throughput: ~50K msg/sec (bandwidth limited)

PUBLISH (1000 subscribers):
  Latency p50: 5ms, p99: 20ms
  Throughput: ~10K msg/sec

PUBLISH with 100 PSUBSCRIBE patterns:
  Additional CPU: +10% per PUBLISH

SPUBLISH (sharded, 1 shard target):
  Similar to PUBLISH but shard-local
  Cluster throughput: scales linearly with shard count
```

---

## 8. Production Failure Modes

### Failure Mode 1: Subscriber Slow Consumer -> Output Buffer Overflow

**Nguyên nhân**: Subscriber xử lý message chậm (GC pause, slow DB call, network latency).

**Dấu hiệu**:
```bash
# Log warning từ Redis
1845:M 01 Jan 12:00:00.123 # Client psub output buffer exceeded 8MB limit

# Kiểm tra
redis-cli CLIENT LIST | grep omem
```

**Cách debug**:
```bash
# 1. Kiểm tra subscriber count
PUBSUB NUMSUB <channel>

# 2. Kiểm tra output buffer
redis-cli CLIENT LIST | awk '{print $1, $NF}' | grep omem

# 3. Kiểm tra slow subscribers
redis-cli CLIENT KILL TYPE psub  # Kill tất cả pubsub client

# 4. Monitor real-time
redis-cli --latency-history
```

**Phòng tránh**:
```bash
# Cấu hình buffer limit
CONFIG SET client-output-buffer-limit pubsub 32mb 8mb 60

# Subscribe với bounded queue
# TypeScript/ioredis
const sub = redis.duplicate()
sub.setMaxListeners(100)
sub.on('message', (ch, msg) => {
  // Xử lý với timeout, crash nếu quá chậm
})
```

### Failure Mode 2: Reconnect Storm

**Nguyên nhân**: Redis restart hoặc network blip -> hàng tráng subscriber reconnect đồng thời -> PUBLISH backlog -> buffer overflow -> disconnect -> reconnect loop.

```
Redis restart:
  T+0:    Redis down
  T+0:    500 subscribers disconnect
  T+1:    Redis up
  T+1:    500 subscribers reconnect simultaneously
  T+1:    500 × SUBSCRIBE commands flood Redis
  T+1:    CPU spike
  T+1:    If any subscriber slow -> buffer overflow -> disconnect
  T+1:    Loop: reconnect -> disconnect -> reconnect
```

**Cách debug**:
```bash
# Monitor connected clients
redis-cli INFO clients
# Connected clients: 500 (normal)
# Connected clients: 0 -> reconnect storm starting

# Monitor reconnect rate
redis-cli CLIENT LIST | grep "cmd=subscribe" | wc -l
```

**Phòng tránh**:
```go
// Exponential backoff khi reconnect
backoff := 100 * time.Millisecond
maxBackoff := 30 * time.Second

for {
    conn, err := redis.Dial("tcp", addr)
    if err != nil {
        time.Sleep(backoff)
        backoff = min(backoff*2, maxBackoff)
        continue
    }
    break
}

// Jittered reconnect để tránh thundering herd
jitter := time.Duration(rand.Int63n(int64(backoff / 2)))
time.Sleep(backoff + jitter)
```

### Failure Mode 3: Message Loss Khi Network Partition

**Nguyên nhân**: Network partition -> subscriber không nhận message trong partition window -> message biến mất.

**Dấu hiệu**:
```bash
# Subscriber logs
[12:00:01] Received: msg_001
[12:00:02] Received: msg_002
[12:00:05] Received: msg_005  # Missed msg_003, msg_004

# Redis log
1845:M 01 Jan 12:00:03.456 - Client <IP> connection lost
```

**Cách debug**:
```bash
# PUBSUB NUMSUB để verify subscriber count
PUBSUB NUMSUB mychannel

# Monitor pubsub_channels count
redis-cli INFO stats | grep -E "pubsub"
# total_pubsub_messages: X
# pubsub_channels: Y
```

**Phòng tránh**: Không dùng Pub/Sub cho message cần guarantee. Dùng Streams với XACK.

### Failure Mode 4: Subscriber Reconnect Misses All Messages

**Nguyên nhân**: Subscriber disconnect -> reconnect -> phải re-subscribe -> tất cả message trong khoảng đó miss.

**Impact**: Tùy thuộc vào message type:
- Typing indicator: acceptable
- Cache invalidation: acceptable (next read sẽ fix)
- Order status notification: NOT acceptable

**Cách debug**:
```bash
# Subscribe/unsubscribe events (Redis 7+)
CONFIG SET notify-keyspace-events KEl
# Không có built-in event log cho message missed
# Phải implement application-level tracking
```

**Phòng tránh**:
```go
// Pattern: Hybrid Pub/Sub + Streams
// 1. PUBLISH real-time notification (for instant delivery)
redis.PUBLISH("order:status:"+orderID, status)

// 2. XADD vào stream (for replay)
redis.XADD("order:stream", "*", "order_id", orderID, "status", status)

// 3. Consumer: subscribe + XREADGROUP on reconnect
go func() {
    for msg := range pubsub.Channel() {
        processRealTime(msg)
    }
}()

go func() {
    // Replay pending messages trên reconnect
    for {
        streams, err := redis.XREADGROUP(
            "cg1", "consumer1",
            "streams", "order:stream",
            "0"  // Read all pending (unACKed)
        ).Result()
        // Xử lý pending messages
    }
}()
```

---

## 9. Real-world Examples

### Example 1: Discord Ephemeral Typing Indicator

Discord dùng Redis Pub/Sub cho **ephemeral signal**: typing indicator, presence (online/offline), cursor position trong collaborative editor.

```
Design:
  - Channel per guild: "guild:123:typing"
  - SUBSCRIBE guild:123:typing
  - PUBLISH "user:456 typing in channel:789"
  - Message TTL: 3 giây (client-side timeout)
  - Miss = user không thấy typing = acceptable

Why Pub/Sub:
  - Không cần replay
  - Không cần persistence
  - High fanout: 1M users × typing indicator = massive
  - Ephemeral: 3-second window chỉ cần real-time
```

### Example 2: Twitter/X Streams API (Historical Transition)

Twitter từng dùng Pub/Sub-like system cho real-time tweet delivery. Qua thời gian, chuyển sang **Kafka** vì:
- Scale: hàng tỷ tweets/day
- Replay: developer cần access old tweets
- Guarantee: không miss tweet notification
- Consumer group: nhiều consumer cho cùng stream

```
Old architecture (Pub/Sub):
  - Real-time tweet push
  - Fanout write (push to followers' streams)
  - Miss = lost opportunity to see tweet

New architecture (Kafka-backed):
  - Tweet as event in Kafka topic
  - Consumer group: search indexer, notification service, analytics
  - Replay: new consumer đọc old tweets
  - Exactly-once: no duplicate notification
```

### Example 3: GitLab Cache Invalidation Pub/Sub

GitLab dùng Redis Pub/Sub cho **multi-instance cache invalidation**.

```
Architecture:
  - 10 Unicorn workers (Puma workers)
  - Shared Redis cache
  - Cache invalidation: one worker updates data -> PUBLISH invalidate
  - Other workers SUBSCRIBE -> invalidate their local cache

Example flow:
  Worker1: UPDATE user SET name = "Bob" WHERE id = 123
  Worker1: PUBLISH "cache:invalidate:user:123"
  Worker2: SUBSCRIBE -> receives -> DEL "user:123:cache"
  Worker3: SUBSCRIBE -> receives -> DEL "user:123:cache"

Why Pub/Sub:
  - Miss = next read fetches from DB = fresh data = acceptable
  - Simplicity: no extra infrastructure
  - Low latency: instant invalidation across workers
  - GitLab: 3000+ GitLab installations, varied infrastructure
```

### Example 4: Uber Driver Location Updates (Not Pub/Sub)

Uber từng dùng Redis cho location tracking nhưng **không dùng Pub/Sub** cho driver location broadcast. Lý do:
- Location update cần **persistence**: để replay cho analytics, fraud detection
- Consumer group: nhiều service cần location data (dispatch, ETA, heatmap)
- Replay: new service onboarding cần historical location

```
Solution: Redis Streams hoặc Kafka
  - XADD "driver:location:stream" with coordinates
  - XREADGROUP consumer group cho dispatch service
  - XREADGROUP consumer group cho analytics service
  - Trimming: keep 24h window
```

---

## 10. Common Pitfalls

**Pitfall 1: Tin Pub/Sub có durability**

Đây là **sai lầm phổ biến nhất**. Developer thấy "Redis" -> nghĩ persistence. Nhưng Pub/Sub là fire-and-forget. Không có disk write, không có ACK, không có replay.

```
MISCONCEPTION:
  "PUBLISH xong -> message được lưu -> subscriber nhận sau cũng được"

REALITY:
  "PUBLISH xong -> message trong memory -> subscriber nhận ngay hoặc KHÔNG"
```

**Pitfall 2: Dùng Pub/Sub làm task queue**

```
// Phổ biến trong các bài hướng dẫn cũ
redis.PUBLISH("email:queue", emailPayload)
redis.PUBLISH("sms:queue", smsPayload)

// Problem:
// - Worker crash -> message lost
// - No retry
// - No dead letter queue
// - No at-least-once guarantee

// Right approach:
// - Redis Streams XADD + XREADGROUP
// - Kafka
// - RabbitMQ
// - NATS JetStream
```

**Pitfall 3: Mix command và subscribe trên cùng client**

```go
// SAI: ioredis/redis-py cho phép nhưng không nên
sub := redis.duplicate()
sub.SUBSCRIBE("channel")
// Từ đây, sub chỉ nhận message, không execute command

// Correct: luôn dùng separate connection
cmdConn := redisPool.Get()
subConn := redisPool.Get()
```

**Pitfall 4: Không monitor `pubsub_channels`**

```bash
# PHẢI có monitoring dashboard:
- PUBSUB CHANNELS (count over time)
- PUBSUB NUMSUB per channel
- PUBSUB NUMPAT (pattern count)
- redis-cli INFO stats | grep pubsub
- Alert khi: pattern count > 1000 (CPU risk)
```

**Pitfall 5: Đánh giá thấp fanout bandwidth**

```
// Tính trước bandwidth
msg_size = 1KB
subscribers = 5000
publishes_per_second = 100
bandwidth = 1KB × 5000 × 100 = 500MB/s = 4Gbps

// Trong 6-node cluster với global PUBLISH:
// bandwidth × 6 = 24Gbps inter-node (CRASHES network)

// Solution: Sharded Pub/Sub (SPUBLISH) hoặc fan-out-by-consumer
```

**Pitfall 6: Reconnect không re-subscribe**

```go
// SAI: Khi reconnect, không re-subscribe
sub, _ := redis.Subscribe("channel")
// Connection lost
sub, _ = redis.Subscribe("channel")  // OK đủ rồi? KHÔNG!
 // Missed messages trong reconnect window -> không recoverable

// Better: Hybrid với Streams replay
redis.XREADGROUP("cg1", "c1", "streams", "channel", "0")
// -> Đọc tất cả unACKed messages sau reconnect
```

**Pitfall 7: PSUBSCRIBE quá nhiều pattern không benchmark**

```bash
# Test CPU cost trước khi deploy
redis-cli --intrinsic-latency 100 --threads 4

# Monitor PSUBSCRIBE pattern count
redis-cli PUBSUB NUMPAT

# Alert threshold: > 500 patterns -> investigate
```

---

## 11. Câu hỏi tự kiểm tra

### Câu 1

**Bạn có hệ thống e-commerce với 50 microservice instances. Khi một instance update product cache, bạn cần tất cả 49 instance khác invalidate local cache của product đó. Chọn giải pháp nào?**

A. Redis Pub/Sub PUBLISH/SUBSCRIBE
B. Redis Streams XADD/XREADGROUP
C. Kafka topic với 50 consumer group
D. Database polling

<details>
<summary>Đáp án</summary>

**A. Redis Pub/Sub** là lựa chọn đúng.

Lý do:
- Cache invalidation là ephemeral signal: miss = next read từ DB = acceptable
- Không cần replay: invalidate rồi thì done, không cần đọc lại
- High fanout: 50 instances = 50 × msg_size = acceptable
- Low latency: instant invalidation across all instances
- Simplicity: không cần infrastructure phức tạp

Không chọn B/C vì over-engineering: Streams/Kafka cần XACK/replay = không cần cho cache invalidation. Không chọn D vì polling = waste resource.
</details>

---

### Câu 2

**Khi subscriber gọi SUBSCRIBE, điều gì xảy ra với connection đó?**

A. Connection vẫn execute được tất cả command bình thường
B. Connection chuyển sang subscribe-only mode, chỉ nhận message và subscribe/unsubscribe command
C. Connection bị kill và tạo connection mới
D. Connection tiếp tục execute command nhưng không nhận message

<details>
<summary>Đáp án</summary>

**B. Connection chuyển sang subscribe-only mode.**

Sau SUBSCRIBE:
- Connection chỉ nhận pushed message từ server
- Chỉ accept: SUBSCRIBE, PSUBSCRIBE, UNSUBSCRIBE, PUNSUBSCRIBE
- Regular commands (GET, SET, HGET, etc.) bị IGNORED hoặc ERROR

Hệ quả: **PHẢI dùng 2 connection riêng biệt** — một cho command, một cho subscribe.
</details>

---

### Câu 3

**Trong Redis Cluster 6 node (3 master + 3 replica), một service dùng PUBLISH cho cache invalidation. Bandwidth inter-node traffic là bao nhiêu so với SPUBLISH?**

A. Giống nhau
B. PUBLISH gấp 6 lần SPUBLISH
C. SPUBLISH gấp 6 lần PUBLISH
D. Không tính được vì phụ thuộc message size

<details>
<summary>Đáp án</summary>

**B. PUBLISH gấp 6 lần SPUBLISH.**

- Global PUBLISH trong Cluster: broadcast tới **tất cả 6 node** -> inter-node bandwidth = 6 × msg_size
- Sharded SPUBLISH: gửi trực tiếp tới **slot chứa channel** (1 node) -> inter-node bandwidth = 1 × msg_size
- Giảm 83% inter-node bandwidth với SPUBLISH

Lưu ý: SPUBLISH chỉ có từ Redis 7.0+.
</details>

---

### Câu 4

**Một developer dùng PSUBSCRIBE với 10,000 pattern. Mỗi khi có PUBLISH, điều gì xảy ra với Redis?**

A. Chỉ match patterns liên quan (optimized)
B. Match tất cả 10,000 patterns với mỗi PUBLISH
C. Không ảnh hưởng vì PSUBSCRIBE chạy async
D. Redis tự động limit pattern count

<details>
<summary>Đáp án</summary>

**B. Match tất cả 10,000 patterns với mỗi PUBLISH.**

- PSUBSCRIBE dùng regex matching cho **mỗi PUBLISH**
- O(N) với N = pattern count
- 10,000 patterns ≈ 100ms CPU overhead mỗi PUBLISH = **blocks Redis main thread**
- Đây là lý do mà 10,000 PSUBSCRIBE patterns = production incident

Solution: Giảm pattern count hoặc dùng specific SUBSCRIBE thay vì PSUBSCRIBE.
</details>

---

### Câu 5

**Bạn cần implement notification system cho trading platform. Nếu trader miss notification về giá cổ phiếu thay đổi, hậu quả là gì? Bạn nên dùng gì?**

A. Dùng Redis Pub/Sub vì latency thấp nhất
B. Dùng Redis Pub/Sub vì hệ thống trading cần real-time
C. Dùng Redis Streams vì cần at-least-once delivery guarantee
D. Dùng Redis Pub/Sub vì simple là tốt nhất

<details>
<summary>Đáp án</summary>

**C. Dùng Redis Streams vì cần at-least-once delivery guarantee.**

Lý do:
- Miss notification giá cổ phiếu = trader không kịp phản ứng = **financial loss**
- Redis Pub/Sub: at-most-once, fire-and-forget -> miss = lost vĩnh viễn
- Redis Streams: at-least-once với XACK -> nếu consumer crash, message được replay

Nguyên tắc: **Message có financial/business impact KHÔNG BAO GIỜ dùng Pub/Sub.**
</details>

---

### Câu 6

**Khi nào thì `client-output-buffer-limit pubsub` trigger disconnect?**

A. Khi subscriber gửi quá nhiều SUBSCRIBE command
B. Khi subscriber nhận message nhanh hơn xử lý, buffer đạt hard limit
C. Khi subscriber kết nối quá lâu
D. Chỉ khi Redis memory đầy

<details>
<summary>Đáp án</summary>

**B. Khi subscriber nhận message nhanh hơn xử lý, buffer đạt hard limit.**

- Soft limit (8mb): Redis bắt đầu count thời gian
- Soft seconds (60s): Nếu buffer > soft limit trong 60s -> warning log
- Hard limit (32mb): Redis disconnect subscriber NGAY LẬP TỨC

Đây là slow consumer protection: ngăn 1 slow subscriber chiếm toàn bộ Redis output buffer.
</details>

---

### Câu 7

**Sự khác biệt quan trọng nhất giữa Pub/Sub và Streams trong Redis là gì?**

A. Pub/Sub nhanh hơn Streams
B. Streams có persistence, Pub/Sub không
C. Pub/Sub dùng được trong Cluster, Streams không
D. Streams có consumer group, Pub/Sub không

<details>
<summary>Đáp án</summary>

**D. Streams có consumer group, Pub/Sub không.**

Nhưng câu trả lời đầy đủ cần cả B và D:
- **B (Persistence)**: Streams lưu message trong stream, đọc lại được. Pub/Sub không.
- **D (Consumer group)**: Streams hỗ trợ XREADGROUP với pending list, replay, claiming. Pub/Sub không.

Cả hai đều dùng được trong Redis Cluster (Streams dùng hash-slot, Pub/Sub dùng broadcast hoặc sharded).

Điểm khác biệt thực tế nhất trong production: **Pub/Sub = fire-and-forget, Streams = durable with replay**.
</details>
