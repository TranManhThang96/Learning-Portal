# Day 12: Kafka Consumer Internals — Consumer Group, Partition Assignment, Rebalance, Offset Management

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** Consumer Group — tại sao là abstraction quan trọng nhất của Kafka consumer
2. **Nắm vững** các partition assignment strategies: range, round-robin, sticky, cooperative sticky
3. **Phân tích được** rebalance protocol — tại sao rebalance đáng sợ và cách giảm thiểu impact
4. **Hiểu rõ** offset management — auto commit vs manual commit và trade-off at-least-once vs at-most-once
5. **Thực hành** xây dựng consumer group, quan sát rebalance, xử lý backpressure

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10 (topic, partition, offset, broker) và Day 11 (producer internals)
- Hiểu partition key routing và ordering guarantee
- Hiểu `acks` và delivery semantics từ Day 11
- Docker Compose Kafka cluster đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Consumer Group concept — tại sao cần, cách hoạt động
- Partition assignment: 1 partition → 1 consumer per group (rule quan trọng nhất)
- Offset management: auto commit vs manual commit, at-least-once vs at-most-once
- Rebalance basics: khi nào trigger, stop-the-world impact
- `max.poll.records`, `max.poll.interval.ms`, `session.timeout.ms`
- Hands-on: multiple consumers, observe rebalance, manual offset commit

### 🟡 Should Learn (nếu còn thời gian)
- Assignment strategies: range, round-robin, sticky, cooperative sticky
- Cooperative rebalance (incremental) — tại sao tốt hơn eager
- Consumer lag monitoring và alerting
- Backpressure handling patterns

### 🟢 Optional Deep Dive
- Consumer group protocol (JoinGroup, SyncGroup, Heartbeat, LeaveGroup)
- Static group membership (`group.instance.id`)
- Custom offset storage (ngoài `__consumer_offsets`)

---

## 4. Lý thuyết (Theory)

### 4.1 Consumer Group — Abstraction Quan Trọng Nhất

#### WHY — Tại sao cần Consumer Group?

Hãy tưởng tượng topic "orders" có 100K messages/second. Một consumer xử lý được 10K msg/s. Bạn cần 10 consumers. Nhưng:
- Làm sao chia partitions cho 10 consumers?
- Khi 1 consumer chết, ai xử lý phần của nó?
- Khi thêm consumer mới, chia lại như thế nào?

**Consumer Group** giải quyết tất cả vấn đề trên.

#### WHAT — Consumer Group là gì?

Consumer Group là **một nhóm consumers** chia sẻ cùng `group.id`. Kafka **tự động phân chia** partitions cho các consumers trong group.

**Rule vàng**: Mỗi partition chỉ được gán cho **ĐÚNG 1 consumer** trong 1 group tại bất kỳ thời điểm nào.

```
Topic "orders": 6 partitions (P0-P5)

Consumer Group "order-service" (3 consumers):
  ┌──────────────────────────────────────────┐
  │  Consumer A: [P0] [P1]                   │
  │  Consumer B: [P2] [P3]                   │
  │  Consumer C: [P4] [P5]                   │
  └──────────────────────────────────────────┘
  → Mỗi consumer xử lý 2 partitions
  → Load chia đều

Consumer Group "analytics" (2 consumers):
  ┌──────────────────────────────────────────┐
  │  Consumer X: [P0] [P1] [P2]              │
  │  Consumer Y: [P3] [P4] [P5]              │
  └──────────────────────────────────────────┘
  → CÙNG data, nhóm khác, phân chia riêng
  → 2 groups đọc TOÀN BỘ messages ĐỘC LẬP
```

**So sánh với RabbitMQ:**

```
RabbitMQ competing consumers:
  Queue ──► Consumer A (nhận msg1, msg3, msg5...)
       └──► Consumer B (nhận msg2, msg4, msg6...)
  → Message bị XÓA sau khi 1 consumer xử lý
  → Không thể có 2 nhóm consumers đều đọc TẤT CẢ messages

Kafka consumer groups:
  Topic ──► Group "service" → Consumer A (P0,P1), Consumer B (P2,P3)
       └──► Group "analytics" → Consumer X (P0,P1,P2,P3)
  → Cả 2 groups đọc TẤT CẢ messages
  → Messages KHÔNG bị xóa
```

#### Scaling Rules

```
6 partitions, thay đổi số consumers:

1 consumer:   C1 ← [P0][P1][P2][P3][P4][P5]     ← xử lý hết
2 consumers:  C1 ← [P0][P1][P2], C2 ← [P3][P4][P5]
3 consumers:  C1 ← [P0][P1], C2 ← [P2][P3], C3 ← [P4][P5]
6 consumers:  C1 ← [P0], C2 ← [P1], ..., C6 ← [P5]   ← max parallel
8 consumers:  C1-C6 mỗi cái 1 partition, C7 và C8 ← IDLE! ⚠️

→ Max effective consumers = số partitions
→ Consumers thừa sẽ IDLE (lãng phí resources)
→ Đây là lý do partition count rất quan trọng khi thiết kế
```

### 4.2 Partition Assignment Strategies

#### WHY — Cần nhiều strategies?

Cách chia partitions cho consumers ảnh hưởng đến:
- **Load balance**: partitions chia đều hay không?
- **Rebalance impact**: khi consumer join/leave, bao nhiêu partitions phải di chuyển?
- **Locality**: consumer có thể "nhớ" state khi giữ nguyên partition?

#### 1. Range Assignor (mặc định cũ)

```
Topics: T1(P0,P1,P2), T2(P0,P1,P2)
Consumers: C0, C1

Range per topic:
  T1: C0 ← [P0,P1], C1 ← [P2]
  T2: C0 ← [P0,P1], C1 ← [P2]

Kết quả:
  C0: T1-P0, T1-P1, T2-P0, T2-P1  (4 partitions)
  C1: T1-P2, T2-P2                  (2 partitions)

→ KHÔNG đều! C0 bị overloaded
→ Vấn đề tệ hơn với nhiều topics
```

- **Ưu điểm**: Co-partitioning — cùng partition number của các topics gán cho cùng consumer (hữu ích cho joins)
- **Nhược điểm**: Không đều khi partitions không chia hết cho consumers

#### 2. Round-Robin Assignor

```
Topics: T1(P0,P1,P2), T2(P0,P1,P2)
Consumers: C0, C1

Round-robin across ALL partitions:
  T1-P0 → C0
  T1-P1 → C1
  T1-P2 → C0
  T2-P0 → C1
  T2-P1 → C0
  T2-P2 → C1

Kết quả:
  C0: T1-P0, T1-P2, T2-P1  (3 partitions)
  C1: T1-P1, T2-P0, T2-P2  (3 partitions)

→ Đều! Nhưng khi rebalance → gần như TẤT CẢ partitions di chuyển
```

- **Ưu điểm**: Phân bổ đều hơn Range
- **Nhược điểm**: Rebalance cost cao — nhiều partitions bị reassign

#### 3. Sticky Assignor

```
Trước khi C2 join (C0, C1 đang active):
  C0: [P0][P1][P2]
  C1: [P3][P4][P5]

SAU khi C2 join — Round-Robin sẽ:
  C0: [P0][P3]     ← P1,P2 bị lấy mất, P3 mới nhận
  C1: [P1][P4]     ← P3,P5 bị lấy, P1 mới nhận  
  C2: [P2][P5]     ← 6 partition movements!

SAU khi C2 join — Sticky sẽ:
  C0: [P0][P1]     ← giữ P0,P1, chỉ mất P2
  C1: [P3][P4]     ← giữ P3,P4, chỉ mất P5
  C2: [P2][P5]     ← chỉ 2 partition movements!

→ Sticky giảm partition movement khi rebalance
→ Consumer giữ lại partition cũ → state cache vẫn valid
```

- **Ưu điểm**: Ít partition movement → rebalance nhanh hơn, ít data re-processing
- **Nhược điểm**: Vẫn là "eager" rebalance — TẤT CẢ consumers DỪNG xử lý trong rebalance

#### 4. Cooperative Sticky Assignor (Recommended)

```
Eager rebalance (Range, Round-Robin, Sticky):
  ┌─────────┐  ┌──────────────┐  ┌─────────┐
  │ Normal  │→ │ STOP-THE-WORLD│→ │ Normal  │
  │ C0:[P0,P1]│ │ ALL consumers │  │ C0:[P0] │
  │ C1:[P2,P3]│ │ STOP, revoke │  │ C1:[P2] │
  │         │  │ ALL partitions│  │ C2:[P1,P3]│
  └─────────┘  └──────────────┘  └─────────┘
                 ↑ processing gap! ↑

Cooperative (incremental) rebalance:
  ┌──────────┐  ┌─────────────┐  ┌───────────┐
  │ Normal   │→ │ ONLY P1,P3  │→ │ Normal    │
  │ C0:[P0,P1]│ │ revoked from│  │ C0:[P0]   │
  │ C1:[P2,P3]│ │ C0,C1       │  │ C1:[P2]   │
  │          │  │ P0,P2 keep  │  │ C2:[P1,P3]│
  │          │  │ processing! │  │           │
  └──────────┘  └─────────────┘  └───────────┘
                  ↑ chỉ P1,P3 bị pause
                  ↑ P0,P2 vẫn chạy!
```

- **Ưu điểm**: Không stop-the-world — chỉ revoke partitions cần di chuyển, còn lại tiếp tục
- **Nhược điểm**: Có thể cần 2 rebalance rounds (revoke + assign)
- **Recommendation**: Dùng **CooperativeSticky** cho production (Kafka >= 2.4)

```properties
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

#### Assignment Strategy Comparison

| Strategy | Load Balance | Rebalance Cost | Stop-the-world | Co-partition |
|----------|-------------|----------------|----------------|-------------|
| Range | Kém | Thấp | Có | Có |
| RoundRobin | Tốt | Cao | Có | Không |
| Sticky | Tốt | Thấp | Có | Không |
| CooperativeSticky | Tốt | Rất thấp | **Không** | Không |

### 4.3 Rebalance Protocol — "Dreaded Rebalance"

#### WHY — Rebalance là vấn đề lớn nhất của Kafka consumers

Rebalance = quá trình Kafka **redistribute** partitions cho consumers. Trong thời gian rebalance (eager mode), **TẤT CẢ consumers DỪNG xử lý**.

#### Khi nào rebalance xảy ra?

```
Trigger rebalance:
  1. Consumer join group      → C3 start → rebalance
  2. Consumer leave group     → C2 crash → rebalance
  3. Consumer bị coi là dead  → heartbeat timeout → rebalance
  4. Topic partition thay đổi → add partitions → rebalance
  5. Consumer subscribe thay đổi → thay đổi topic list → rebalance
```

#### Rebalance Protocol Chi Tiết (Eager mode)

```
                Group Coordinator (Broker)
                         │
  C0 ──[JoinGroup]──────►│
  C1 ──[JoinGroup]──────►│
  C2 ──[JoinGroup]──────►│    ← Phase 1: tất cả consumers join
                         │
                         │ Chọn C0 làm Group Leader
                         │
  C0 ◄──[JoinResponse]──│    (C0 nhận danh sách members)
  C1 ◄──[JoinResponse]──│    (assignment: {})
  C2 ◄──[JoinResponse]──│
                         │
  C0: tính partition assignment (strategy)
                         │
  C0 ──[SyncGroup]──────►│    (gửi assignment cho tất cả)
  C1 ──[SyncGroup]──────►│    ← Phase 2: sync
  C2 ──[SyncGroup]──────►│
                         │
  C0 ◄──[SyncResponse]──│    C0: [P0,P1]
  C1 ◄──[SyncResponse]──│    C1: [P2,P3]
  C2 ◄──[SyncResponse]──│    C2: [P4,P5]
                         │
  C0, C1, C2: start consuming + heartbeat
                         │
  C0 ──[Heartbeat]──────►│    (mỗi heartbeat.interval.ms)
  C1 ──[Heartbeat]──────►│
  C2 ──[Heartbeat]──────►│
```

#### Rebalance Impact và Mitigation

```
Production impact khi rebalance:
  
  Timeline (eager rebalance, 6 consumers):
  ────────┬──────────────────────┬───────────
  Normal  │     REBALANCE        │  Normal
  100K    │     0 msg/s          │  100K
  msg/s   │     (30s-120s!)      │  msg/s
          │                      │
          └──────────────────────┘
          ↑ Consumer lag tăng vọt!
          ↑ Downstream delay!
          ↑ Possible timeout cascade!
```

**Mitigation strategies:**

| Strategy | Cách làm | Impact |
|----------|---------|--------|
| Cooperative rebalance | `CooperativeStickyAssignor` | Giảm ~90% downtime |
| Static membership | Set `group.instance.id` | Tránh rebalance khi consumer restart ngắn |
| Tăng session timeout | `session.timeout.ms=30000` | Ít false-positive consumer death |
| Tune heartbeat | `heartbeat.interval.ms=3000` | Phát hiện dead consumer nhanh hơn |
| Handling time | `max.poll.interval.ms` đủ lớn | Tránh rebalance do slow processing |

**Commit-on-revoke practice**: Khi partition bị revoke trong rebalance, consumer nên commit offset cuối cùng đã xử lý cho partition đó trước khi trả partition về group. Với Java/librdkafka, đây là `ConsumerRebalanceListener`/rebalance callback:

```java
consumer.subscribe(List.of("orders"), new ConsumerRebalanceListener() {
  public void onPartitionsRevoked(Collection<TopicPartition> partitions) {
    // Commit offset đã xử lý xong cho các partition sắp bị revoke.
    consumer.commitSync(currentOffsetsFor(partitions));
  }

  public void onPartitionsAssigned(Collection<TopicPartition> partitions) {
    // Load state, resume từ committed offset.
  }
});
```

`kafka-go` lab bên dưới dùng để quan sát rebalance và lag; nếu cần demo commit-on-revoke/static membership đúng production, ưu tiên Java client hoặc librdkafka vì chúng expose rebalance callback rõ hơn.

### 4.4 Offset Management — At-Least-Once vs At-Most-Once

#### WHY — Offset commit quyết định delivery semantics

Offset commit = "tôi đã xử lý xong messages đến offset X". Kafka lưu committed offsets trong internal topic `__consumer_offsets`.

```
Partition 0: [m0] [m1] [m2] [m3] [m4] [m5]
                           ↑         ↑
                    committed      current position
                    offset=3       (đang xử lý m4, m5)
                    
Nếu consumer crash:
  Restart → đọc lại từ committed offset (3)
  → m3, m4, m5 được xử lý LẠI (duplicates nếu m3,m4 đã xử lý)
```

#### Auto Commit — Simple nhưng nguy hiểm

```properties
enable.auto.commit=true            # Mặc định
auto.commit.interval.ms=5000       # Commit mỗi 5s
```

```
Auto commit timeline:

  t=0s:   poll() → nhận [m0,m1,m2,m3,m4]
  t=1s:   xử lý m0 ✓
  t=2s:   xử lý m1 ✓
  t=3s:   xử lý m2 ✓
  t=4s:   CRASH! 💥
  t=5s:   (auto commit sẽ commit ở đây — nhưng đã crash!)
  
  Restart: offset vẫn = 0 → xử lý LẠI m0,m1,m2 → DUPLICATES!
  
  Hoặc ngược lại:
  t=0s:   poll() → nhận [m0,m1,m2,m3,m4]
  t=1s:   xử lý m0 ✓
  t=5s:   AUTO COMMIT offset=5 (commit TẤT CẢ nhận được!)
  t=6s:   xử lý m1 ✓
  t=7s:   CRASH! 💥
  
  Restart: offset = 5 → SKIP m2,m3,m4 → DATA LOSS!
```

#### Manual Commit — Chính xác hơn

**Synchronous commit** — commit từng message:

```go
for {
    msg, err := reader.FetchMessage(ctx)
    if err != nil {
        break
    }
    
    // 1. Xử lý message
    processMessage(msg)
    
    // 2. Commit SAU khi xử lý xong → at-least-once
    err = reader.CommitMessages(ctx, msg)
    if err != nil {
        log.Printf("commit failed: %v", err)
    }
}
```

```
Manual commit (at-least-once):

  FetchMessage(m0) → process m0 ✓ → commit offset=1 ✓
  FetchMessage(m1) → process m1 ✓ → commit offset=2 ✓
  FetchMessage(m2) → process m2 ✓ → CRASH! 💥 (commit chưa kịp)
  
  Restart → offset = 2 → xử lý LẠI m2 → duplicate m2
  → Nhưng KHÔNG mất data!
  → Cần idempotent consumer để handle duplicate (Day 15)
```

**Commit at-most-once** — commit TRƯỚC khi xử lý:

```go
for {
    msg, err := reader.FetchMessage(ctx)
    if err != nil {
        break
    }
    
    // 1. Commit TRƯỚC → at-most-once
    reader.CommitMessages(ctx, msg)
    
    // 2. Rồi mới xử lý
    processMessage(msg) // nếu crash ở đây → message mất
}
```

#### Offset Commit Strategies

| Strategy | Delivery Semantic | Throughput | Use Case |
|----------|------------------|-----------|----------|
| Auto commit | Cả 2 đều có thể xảy ra | Cao | Non-critical, logs |
| Commit per message | At-least-once | Thấp | Financial, important events |
| Commit per batch | At-least-once (batch granularity) | Trung bình | **Recommended default** |
| Commit trước xử lý | At-most-once | Cao | Metrics mà mất 1 vài OK |
| Async commit | At-least-once (eventual) | Cao | High-throughput, chấp nhận larger duplicate window |

**Production recommendation**: **Commit per batch** + **idempotent consumer** (Day 15)

```go
// Commit per batch — balance giữa throughput và safety
batchSize := 100
var batch []kafka.Message

for {
    msg, err := reader.FetchMessage(ctx)
    if err != nil {
        break
    }
    
    processMessage(msg)
    batch = append(batch, msg)
    
    if len(batch) >= batchSize {
        // Commit offset cao nhất trong batch
        reader.CommitMessages(ctx, batch[len(batch)-1])
        batch = batch[:0]
    }
}
```

### 4.5 Consumer Configuration Quan Trọng

#### `max.poll.records` — Số records tối đa per poll

```properties
max.poll.records=500    # Mặc định
```

```
poll() trả về tối đa 500 records
→ Consumer xử lý 500 records
→ Rồi poll() tiếp

Nếu xử lý 500 records mất 10 phút nhưng max.poll.interval.ms=5 phút:
→ Consumer bị kick khỏi group → REBALANCE!
```

#### `max.poll.interval.ms` — Thời gian tối đa giữa 2 lần poll

```properties
max.poll.interval.ms=300000    # 5 phút (mặc định)
```

```
poll()
  │
  ▼
  Processing... (phải xong và poll() lại trước 5 phút)
  │
  ▼
poll()    ← nếu quá 5 phút → client bị coi là không progress → rebalance

Common mistake:
  max.poll.records=10000 + slow processing (10ms/record)
  = 100 seconds processing time
  < max.poll.interval.ms = 300s → OK
  
  Nhưng nếu processing spike to 50ms/record:
  = 500 seconds > 300s → REBALANCE! 💥
```

Nuance quan trọng:
- `max.poll.interval.ms` đo **application progress**: consumer phải gọi `poll()` lại trong khoảng này. Heartbeat thread có thể vẫn còn gửi heartbeat trong lúc processing, nhưng group coordinator vẫn trigger rebalance nếu consumer không poll lại đủ lâu.
- `session.timeout.ms` đo **membership liveness**: nếu coordinator không nhận heartbeat trong khoảng này thì member bị coi là dead.
- Với **dynamic membership**, vượt `max.poll.interval.ms` thường dẫn tới LeaveGroup/rebalance sớm. Với **static membership** (`group.instance.id`), partition có thể được giữ đến khi `session.timeout.ms` hết hạn, giúp restart ngắn không tạo rebalance ngay.

#### `session.timeout.ms` và `heartbeat.interval.ms`

```properties
session.timeout.ms=45000       # Consumer bị coi là dead sau 45s không heartbeat
heartbeat.interval.ms=3000     # Gửi heartbeat mỗi 3s
```

```
Consumer ──[heartbeat]──► Coordinator
  3s later
Consumer ──[heartbeat]──► Coordinator
  3s later
Consumer ──[heartbeat]──► Coordinator
  ...
  
Nếu GC pause 50s:   (> session.timeout = 45s)
  → Coordinator: "Consumer dead!" → REBALANCE
  → GC xong, consumer quay lại → "hả, tôi bị kick?"

Rule of thumb:
  session.timeout.ms >= 3 × heartbeat.interval.ms
  Thường: session=45s, heartbeat=3s (= 15 missed heartbeats trước khi dead)
```

Static membership config mẫu:

```properties
group.instance.id=order-processor-pod-0  # stable ID per instance/pod
session.timeout.ms=45000
heartbeat.interval.ms=3000
max.poll.interval.ms=300000
```

### 4.6 Backpressure — Consumer chậm hơn Producer

#### WHY — Backpressure trong Kafka

```
Producer: 100K msg/s ──► Topic ──► Consumer: 10K msg/s

Gap: 90K msg/s không được xử lý
→ Consumer lag TĂNG liên tục
→ Lag = (latest offset) - (consumer committed offset)
→ Lag = 90K × 60s = 5.4M messages sau 1 phút
→ Lag = 90K × 3600s = 324M messages sau 1 giờ!
```

#### Kafka Backpressure Model vs RabbitMQ

```
RabbitMQ: ACTIVE backpressure
  → Broker ngừng nhận messages từ producer khi queue đầy
  → Credit-based flow control
  → Producer bị SLOW DOWN

Kafka: PASSIVE backpressure
  → Broker LUÔN nhận messages (append to log)
  → Consumer lag TĂNG
  → Kafka KHÔNG tự động slow down producer
  → Application phải tự xử lý
```

#### Giải pháp Backpressure

```
1. Scale consumers (thêm consumers + thêm partitions):
   Consumer group: C1, C2 → C1, C2, C3, C4
   Throughput: 20K → 40K msg/s

2. Optimize processing:
   Parallel processing within consumer (thread pool)
   Batch processing (xử lý batch thay vì từng message)

3. Auto-scaling:
   Monitor consumer lag
   → lag > threshold → scale up consumers
   → lag ≈ 0 → scale down

4. Tiered processing:
   Important messages → fast path
   Non-critical → slow path / batch later
```

---

## 5. Trade-off Analysis

### Consumer Group Size vs Partition Count

| Consumer Count vs Partitions | Kết quả | Recommendation |
|------------------------------|---------|----------------|
| Consumers < Partitions | Một số consumers xử lý nhiều partitions | OK cho bình thường |
| Consumers = Partitions | Mỗi consumer 1 partition — max parallelism | **Ideal** |
| Consumers > Partitions | Consumers thừa bị IDLE | **Lãng phí** |

### Auto Commit vs Manual Commit

| Tiêu chí | Auto Commit | Manual (sync) | Manual (async) |
|----------|-------------|---------------|----------------|
| Simplicity | ✅ Đơn giản | Phức tạp | Trung bình |
| Data safety | ❌ Có thể mất/duplicate | ✅ At-least-once | ✅ At-least-once |
| Throughput | Cao | Thấp nhất | Cao |
| Latency impact | Không | Có (commit mỗi message) | Không đáng kể |
| Duplicate window | ~auto.commit.interval | ~1 message | ~commit interval |
| Use case | Logs, metrics | Payments, orders | High-volume events |

### Rebalance Strategy

| Tiêu chí | Eager (default cũ) | Cooperative (recommended) |
|-----------|-------------------|--------------------------|
| Processing gap | **Toàn bộ** consumers dừng | Chỉ affected partitions |
| Rebalance time | Nhanh hơn (1 round) | Có thể 2 rounds |
| Complexity | Đơn giản | Phức tạp hơn |
| Production safety | ❌ Risky cho high-throughput | ✅ Safe |
| Kafka version | Tất cả | >= 2.4 |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Dùng CooperativeStickyAssignor**: Tránh stop-the-world rebalance. Set `partition.assignment.strategy=CooperativeStickyAssignor`.

2. **Manual commit per batch**: Balance giữa throughput và safety. Commit mỗi 100-500 messages hoặc mỗi 5-10 giây.

3. **Set `max.poll.records` phù hợp với processing time**: `max.poll.records × avg_processing_time < max.poll.interval.ms × 0.8` (có buffer 20%).

4. **Monitor consumer lag**: Alert khi lag > threshold (ví dụ: > 10K messages hoặc > 5 phút). Dùng `kafka-consumer-groups.sh --describe` hoặc Kafka UI.

5. **Graceful shutdown**: Consumer gọi `Close()` → trigger LeaveGroup → rebalance nhanh hơn (so với đợi session timeout).

6. **Static group membership**: Cho environments với frequent restarts (container orchestration), set `group.instance.id` stable theo instance/pod. Đừng generate random ID mỗi lần start, nếu không sẽ mất lợi ích static membership.

### Common Pitfalls

1. **❌ Auto commit + slow processing**: Commit offset trước khi xử lý xong → restart → skip messages → data loss.

2. **❌ `max.poll.interval.ms` quá nhỏ**: Processing chậm 1 chút → consumer bị kick → rebalance → processing chậm thêm → rebalance storm! Vòng lặp chết.

3. **❌ Quá nhiều consumers so với partitions**: Consumers thừa bị IDLE, lãng phí resources. Check: `num_consumers <= num_partitions`.

4. **❌ Xử lý message lâu hơn `max.poll.interval.ms`**: Heartbeat/session timeout và poll interval là hai cơ chế khác nhau. Client hiện đại có thể vẫn heartbeat trong lúc xử lý, nhưng nếu không `poll()` lại đúng hạn thì vẫn bị coi là không progress và gây rebalance.

5. **❌ Không handle rebalance callbacks**: Khi partition bị revoke, cần commit offset hiện tại cho partition đó trước khi revoke. Nếu không → duplicate processing sau rebalance.

6. **❌ Quên monitor consumer lag**: Consumer chạy "bình thường" nhưng lag tăng 10M messages → phát hiện khi đã quá muộn → data quá cũ.

---

## 7. Performance Considerations

### Consumer Metrics Quan Trọng

| Metric | Ý nghĩa | Alert Threshold |
|--------|---------|----------------|
| `consumer_lag` | Offset chênh lệch giữa latest và committed | > 10K hoặc > 5 phút |
| `records-consumed-rate` | Messages consumed/sec | Giảm đột ngột |
| `fetch-latency-avg` | Avg fetch request latency (ms) | > 500ms |
| `poll-idle-ratio-avg` | % time consumer idle (đợi messages) | < 20% = overloaded |
| `commit-latency-avg` | Avg commit request latency | > 100ms |
| `rebalance-total` | Số lần rebalance | Tăng đột ngột |
| `rebalance-latency-avg` | Avg thời gian rebalance (ms) | > 30s |

### Consumer Tuning Checklist

```
Processing throughput thấp?
├── Check consumer lag → tăng?
│   ├── Có → tăng consumers (max = num_partitions)
│   ├── Processing slow → optimize logic, batch DB writes
│   └── Network slow → fetch.min.bytes, fetch.max.wait.ms
│
├── Rebalance liên tục?
│   ├── max.poll.interval.ms quá nhỏ → tăng lên
│   ├── session.timeout.ms quá nhỏ → tăng lên
│   ├── GC pauses → tune JVM (nếu dùng Java client)
│   └── Dùng CooperativeStickyAssignor
│
└── Commit overhead cao?
    ├── Commit mỗi message → commit per batch
    ├── Async commit thay vì sync
    └── Tăng auto.commit.interval.ms
```

### Consumer Benchmark Numbers

```
Single consumer (modern hardware):
├── Simple processing: 100K-500K msg/s
├── With JSON parse: 50K-200K msg/s  
├── With DB write: 5K-20K msg/s (DB is bottleneck)
├── With HTTP call: 500-2K msg/s (network latency bound)
└── Fetch throughput: up to 300 MB/s (zero-copy)

Rule of thumb cho capacity planning:
  Required throughput / per-consumer throughput = min consumers
  + 50% buffer for spikes = recommended consumers
  consumers <= partitions
```

---

## 8. Hands-on Lab

### 8.1 Setup

```bash
# Tiếp từ Day 10 cluster
# Tạo topic cho lab
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic consumer-lab --partitions 6 --replication-factor 3

mkdir -p day-12-lab && cd day-12-lab
go mod init day12-consumer-internals
go get github.com/segmentio/kafka-go
```

### 8.2 Consumer Group và Rebalance Observation

**Producer** (`producer.go`) — liên tục gửi messages:

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

type Event struct {
	ID        int       `json:"id"`
	UserID    string    `json:"user_id"`
	Action    string    `json:"action"`
	Timestamp time.Time `json:"timestamp"`
}

func main() {
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "consumer-lab",
		Balancer:     &kafka.Hash{},
		BatchTimeout: 10 * time.Millisecond,
		RequiredAcks: kafka.RequireAll,
	}
	defer writer.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	users := []string{"user-alice", "user-bob", "user-charlie", "user-diana", "user-eve"}
	actions := []string{"login", "view", "click", "purchase", "logout"}

	id := 0
	ticker := time.NewTicker(100 * time.Millisecond) // 10 msg/s
	defer ticker.Stop()

	fmt.Println("Producer started. Sending 10 msg/s. Ctrl+C to stop.")

	for {
		select {
		case <-ctx.Done():
			fmt.Println("Producer stopped.")
			return
		case <-ticker.C:
			event := Event{
				ID:        id,
				UserID:    users[id%len(users)],
				Action:    actions[id%len(actions)],
				Timestamp: time.Now(),
			}
			value, _ := json.Marshal(event)

			err := writer.WriteMessages(ctx, kafka.Message{
				Key:   []byte(event.UserID),
				Value: value,
			})
			if err != nil {
				if ctx.Err() != nil {
					return
				}
				log.Printf("Send error: %v", err)
				continue
			}

			if id%50 == 0 {
				fmt.Printf("Sent %d messages\n", id)
			}
			id++
		}
	}
}
```

**Consumer** (`consumer.go`) — chạy nhiều instances:

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

type Event struct {
	ID        int    `json:"id"`
	UserID    string `json:"user_id"`
	Action    string `json:"action"`
	Timestamp string `json:"timestamp"`
}

func main() {
	consumerID := os.Getenv("CONSUMER_ID")
	if consumerID == "" {
		consumerID = fmt.Sprintf("consumer-%d", time.Now().UnixNano()%1000)
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{"localhost:9092"},
		Topic:          "consumer-lab",
		GroupID:        "order-processors", // CÙNG group → shared partitions
		MaxBytes:       10e6,
		CommitInterval: time.Second, // async commit mỗi giây
		StartOffset:    kafka.LastOffset,
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; fmt.Printf("\n[%s] Shutting down...\n", consumerID); cancel() }()

	var msgCount int64
	partitionMap := make(map[int]int64)

	fmt.Printf("[%s] Consumer started. Waiting for messages...\n", consumerID)

	// Stats printer
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				total := atomic.LoadInt64(&msgCount)
				fmt.Printf("[%s] Total processed: %d | Partitions: %v\n",
					consumerID, total, partitionMap)
			}
		}
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				break
			}
			log.Printf("[%s] Fetch error: %v", consumerID, err)
			continue
		}

		var event Event
		json.Unmarshal(msg.Value, &event)

		atomic.AddInt64(&msgCount, 1)
		partitionMap[msg.Partition]++

		// Simulate processing time (50ms)
		time.Sleep(50 * time.Millisecond)

		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("[%s] Commit error: %v", consumerID, err)
		}
	}

	total := atomic.LoadInt64(&msgCount)
	fmt.Printf("[%s] Stopped. Total processed: %d\n", consumerID, total)
}
```

**Chạy lab:**

```bash
# Terminal 1: Producer
go run producer.go

# Terminal 2: Consumer 1
CONSUMER_ID=C1 go run consumer.go

# PowerShell:
# $env:CONSUMER_ID="C1"; go run consumer.go

# Quan sát C1 nhận TẤT CẢ 6 partitions

# Terminal 3: Consumer 2 (rebalance!)
CONSUMER_ID=C2 go run consumer.go

# PowerShell:
# $env:CONSUMER_ID="C2"; go run consumer.go

# Quan sát: partitions được chia 2 → mỗi consumer 3 partitions

# Terminal 4: Consumer 3
CONSUMER_ID=C3 go run consumer.go

# PowerShell:
# $env:CONSUMER_ID="C3"; go run consumer.go

# Quan sát: mỗi consumer 2 partitions

# Kill Consumer 2 (Ctrl+C) → rebalance, C1 và C3 chia lại
```

### 8.3 Manual Offset Commit — At-Least-Once Demo

```go
// manual_commit_demo.go — Chứng minh at-least-once semantics
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "commit-demo"

	// Tạo topic
	conn, _ := kafka.Dial("tcp", "localhost:9092")
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     1,
		ReplicationFactor: 3,
	})
	conn.Close()

	// Gửi 10 messages
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        topic,
		RequiredAcks: kafka.RequireAll,
	}
	for i := 0; i < 10; i++ {
		writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(fmt.Sprintf("key-%d", i)),
			Value: []byte(fmt.Sprintf("message-%d", i)),
		})
	}
	writer.Close()
	fmt.Println("Sent 10 messages")

	// Consumer: commit mỗi 3 messages, "crash" sau message 7
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{"localhost:9092"},
		Topic:   topic,
		GroupID: "commit-demo-group",
	})

	ctx, cancel := context.WithCancel(context.Background())
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	batchSize := 3
	var batch []kafka.Message
	processedCount := 0
	simulateCrash := true

	fmt.Println("\n=== First run (will 'crash' after message-7) ===")
	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			break
		}

		fmt.Printf("Processing: %s (partition=%d, offset=%d)\n",
			string(msg.Value), msg.Partition, msg.Offset)
		batch = append(batch, msg)
		processedCount++

		if len(batch) >= batchSize {
			// Commit batch
			err := reader.CommitMessages(ctx, batch[len(batch)-1])
			if err != nil {
				log.Printf("Commit failed: %v", err)
			} else {
				fmt.Printf(">>> Committed offset %d\n", batch[len(batch)-1].Offset+1)
			}
			batch = batch[:0]
		}

		// Simulate crash after processing message-7
		if simulateCrash && processedCount >= 8 {
			fmt.Println("\n💥 Simulated crash! (uncommitted: message-6, message-7)")
			reader.Close()
			break
		}
	}

	if !simulateCrash {
		return
	}

	// "Restart" consumer — sẽ replay uncommitted messages
	time.Sleep(2 * time.Second)
	fmt.Println("\n=== Restart (replaying from last committed offset) ===")

	reader2 := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{"localhost:9092"},
		Topic:   topic,
		GroupID: "commit-demo-group",
	})
	defer reader2.Close()

	for i := 0; i < 10; i++ {
		ctx2, cancel2 := context.WithTimeout(context.Background(), 3*time.Second)
		msg, err := reader2.FetchMessage(ctx2)
		cancel2()
		if err != nil {
			fmt.Println("No more messages")
			break
		}
		fmt.Printf("Re-processing: %s (partition=%d, offset=%d)\n",
			string(msg.Value), msg.Partition, msg.Offset)
		reader2.CommitMessages(context.Background(), msg)
	}

	fmt.Println("\n→ Quan sát: message-6 và message-7 được xử lý LẠI!")
	fmt.Println("→ Đây là at-least-once semantics")
	fmt.Println("→ Cần idempotent consumer (inbox pattern) để handle duplicates")
}
```

### 8.4 Consumer Lag Monitoring

```bash
# Xem consumer group details
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --describe --group order-processors

# Xem member và assignment thật sau mỗi lần start/stop consumer
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --describe --group order-processors --members --verbose

# PowerShell multiline tương đương:
# docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 `
#   --describe --group order-processors --members --verbose

# Output ví dụ:
# GROUP            TOPIC        PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# order-processors consumer-lab 0          150             200             50
# order-processors consumer-lab 1          145             198             53
# order-processors consumer-lab 2          160             205             45
# ...

# List tất cả consumer groups
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 --list

# Reset offset (test replay)
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --group order-processors --topic consumer-lab --reset-offsets --to-earliest --execute

# Kafka UI: http://localhost:8080 → Consumer Groups
```

### 8.5 Backpressure Simulation

```go
// backpressure_demo.go — Simulate slow consumer
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "backpressure-demo"

	conn, _ := kafka.Dial("tcp", "localhost:9092")
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     3,
		ReplicationFactor: 3,
	})
	conn.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	// Fast producer: 100 msg/s
	go func() {
		writer := &kafka.Writer{
			Addr:         kafka.TCP("localhost:9092"),
			Topic:        topic,
			Balancer:     &kafka.RoundRobin{},
			BatchTimeout: 10 * time.Millisecond,
		}
		defer writer.Close()

		var produced int64
		for {
			select {
			case <-ctx.Done():
				return
			default:
				writer.WriteMessages(ctx, kafka.Message{
					Value: []byte(fmt.Sprintf("msg-%d", produced)),
				})
				atomic.AddInt64(&produced, 1)
				time.Sleep(10 * time.Millisecond) // 100 msg/s
			}
		}
	}()

	// Slow consumer: 10 msg/s (processing takes 100ms)
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:9092"},
		Topic:    topic,
		GroupID:  "slow-consumer",
		MaxBytes: 10e6,
	})
	defer reader.Close()

	var consumed int64
	start := time.Now()

	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				c := atomic.LoadInt64(&consumed)
				elapsed := time.Since(start).Seconds()
				rate := float64(c) / elapsed
				fmt.Printf("Consumed: %d | Rate: %.0f msg/s | Expected lag: ~%.0f msgs\n",
					c, rate, (100-rate)*elapsed)
			}
		}
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				break
			}
			log.Printf("Fetch error: %v", err)
			continue
		}

		// Slow processing — 100ms per message = 10 msg/s
		time.Sleep(100 * time.Millisecond)
		atomic.AddInt64(&consumed, 1)

		reader.CommitMessages(ctx, msg)

		_ = msg // prevent unused warning
	}
}
```

```bash
go run backpressure_demo.go

# Quan sát: lag tăng liên tục ~90 msg/s
# Sau 1 phút: lag ≈ 5400 messages
# Giải pháp: thêm consumers hoặc optimize processing
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Bạn có topic 8 partitions, consumer group 5 consumers. Partition assignment trông như thế nào?** Nếu 1 consumer chết, điều gì xảy ra? (Hint: range vs round-robin vs sticky)

2. **Giải thích sự khác biệt giữa `session.timeout.ms` và `max.poll.interval.ms`.** Cho scenario mà mỗi cái trigger rebalance. (Hint: heartbeat thread vs poll thread)

3. **Tại sao "commit before process" là at-most-once còn "process then commit" là at-least-once?** Vẽ timeline crash scenario cho mỗi case. (Hint: crash point)

4. **Cooperative rebalance (incremental) tốt hơn eager rebalance như thế nào?** Trong scenario nào cooperative KHÔNG giúp được? (Hint: tất cả partitions đều phải di chuyển)

5. **Consumer lag tăng liên tục. Bạn sẽ debug và fix thế nào?** Liệt kê 5 bước từ detect đến resolve. (Hint: identify bottleneck → scale → optimize → alert)

6. **Tại sao max consumers = partition count?** Nếu cần nhiều parallelism hơn partition count hiện tại, bạn làm gì? Trade-off là gì? (Hint: tăng partitions, in-consumer parallelism)

7. **Static group membership (`group.instance.id`) giúp gì trong Kubernetes?** Khi nào nó KHÔNG giúp? (Hint: rolling restart vs scaling)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Consumer Configuration](https://kafka.apache.org/documentation/#consumerconfigs)
- [Kafka Consumer Group Protocol](https://kafka.apache.org/documentation/#protocol_consumer)
- [KIP-429: Cooperative Rebalancing](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol)
- [KIP-345: Static Group Membership](https://cwiki.apache.org/confluence/display/KAFKA/KIP-345%3A+Introduce+static+membership+protocol+to+reduce+consumer+rebalances)

### Blog Posts Chất Lượng
- [Apache Kafka Rebalance Protocol](https://www.confluent.io/blog/cooperative-rebalancing-in-kafka-streams-consumer-ksqldb/) — Confluent
- [Everything You Need to Know About Kafka Consumer Lag](https://www.conduktor.io/kafka/kafka-consumer-group-and-consumer-offsets/) — Conduktor
- [Kafka Consumer Tuning](https://strimzi.io/blog/2021/01/07/consumer-tuning/) — Strimzi

### Videos
- [The Kafka Consumer: Internals and Advanced Configurations](https://www.youtube.com/watch?v=pGZ1zckbLR4) — Confluent
- [Incremental Cooperative Rebalancing: Support and Policies](https://www.youtube.com/watch?v=MFHqGKkfqp8) — Kafka Summit
- [Understanding Consumer Lag](https://www.youtube.com/watch?v=1vLMuWsfMcA) — Conduktor
