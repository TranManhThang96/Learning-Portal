# Day 9: Performance Tuning & Production — Monitoring, Flow Control, RabbitMQ Streams

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Nắm vững** prefetch count tuning — cách chọn giá trị tối ưu cho từng workload
2. **Hiểu sâu** flow control và memory/disk alarms — RabbitMQ tự bảo vệ thế nào
3. **Biết cách** setup monitoring với Prometheus + Grafana cho production RabbitMQ
4. **Hiểu** classic queue storage hiện hành và vì sao lazy queue tuning đã lỗi thời
5. **So sánh** RabbitMQ Streams với Kafka — khi nào RabbitMQ đủ cho stream processing

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 4-8 (toàn bộ RabbitMQ fundamentals, reliability, clustering)
- Hiểu consumer ack/nack, prefetch cơ bản từ Day 4 và Day 6
- Hiểu quorum queues từ Day 6 và Day 8
- RabbitMQ cluster đang chạy (single node OK cho labs)

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Prefetch count tuning — theory + benchmarks thực tế
- Flow control — memory watermark, disk alarm, credit-based flow
- Lazy queues — khi nào dùng, impact on performance
- Production monitoring — Prometheus metrics, Grafana dashboards, alerting rules
- Hands-on: setup Prometheus + Grafana, load test, observe metrics

### 🟡 Should Learn (nếu còn thời gian)
- RabbitMQ Streams — stream queues, offset tracking, so sánh với Kafka
- OS-level tuning — file descriptors, TCP buffers, Erlang VM flags
- Queue depth alerting strategies

### 🟢 Optional Deep Dive
- RabbitMQ PerfTest tool — benchmark methodology
- Connection pooling patterns
- Erlang VM tuning (schedulers, memory allocators)

---

## 4. Lý thuyết (Theory)

### 4.1 Prefetch Count Tuning — Core Performance Lever

#### WHY — Prefetch ảnh hưởng performance nhiều hơn bạn nghĩ

Recap từ Day 4: prefetch count = số messages broker gửi cho consumer **trước khi nhận ack**. Đây là **single most impactful tuning parameter** cho consumer throughput.

```
Prefetch = 1 (quá thận trọng):
  Broker        Consumer
    │ ──msg1──>   │
    │             │── process (200ms)
    │   <──ack──  │
    │ ──msg2──>   │              ← 200ms idle waiting!
    │             │── process (200ms)
    │   <──ack──  │
  
  Throughput: 1 / (process_time + RTT) = 1 / 0.201s ≈ 5 msg/s per consumer
  Problem: Network RTT wasted between ack and next delivery

Prefetch = 20 (pipeline đầy):
  Broker        Consumer
    │ ──msg1──>   │── process msg1
    │ ──msg2──>   │   (msg2-20 buffered locally)
    │ ──msg3──>   │
    │  ...        │
    │ ──msg20──>  │
    │   <──ack1── │── process msg2
    │ ──msg21──>  │   (immediate, no wait!)
    │   <──ack2── │── process msg3
  
  Throughput: 1 / process_time = 1 / 0.2s = 5 msg/s per consumer
  BUT: No idle time! Messages already buffered locally
  Effective: ~4.9 msg/s (near theoretical max)
```

#### WHAT — Chọn Prefetch Count

**Formula đơn giản:**

```
optimal_prefetch ≈ consumer_throughput × network_RTT × 2

Ví dụ:
  Consumer xử lý 50 msg/s, RTT đến broker = 2ms
  prefetch = 50 × 0.002 × 2 = 0.2 → round up to 1 (minimum)
  
  → Với low-latency network (< 1ms), prefetch thấp OK
  → Với high-latency (cloud, cross-AZ), prefetch phải cao hơn

Thực tế: dùng bảng guideline dưới đây
```

**Guideline by workload:**

| Workload | Process Time | Recommended Prefetch | Lý do |
|----------|-------------|---------------------|-------|
| **CPU-heavy** (video encoding, ML inference) | 5-60s | 1-2 | Fair dispatch critical, task lâu |
| **I/O-heavy** (DB writes, API calls) | 100ms-2s | 5-20 | Balance throughput và fairness |
| **Light processing** (logging, metrics, transform) | 1-50ms | 50-200 | Throughput dominant, tasks nhanh |
| **Mixed workload** | Variable | 10-30 | Safe default |

#### HOW — Benchmark prefetch impact

```
Benchmark: 1KB messages, single consumer, 10ms process time per message

Prefetch | Throughput (msg/s) | Consumer Memory | Fairness
---------|-------------------|-----------------|----------
    1    |         85        |      Low        | Perfect
    5    |         95        |      Low        | Very good
   10    |         98        |      Low        | Good
   25    |         99        |      Medium     | Acceptable
   50    |        100        |      Medium     | Poor (if multi-consumer)
  100    |        100        |      High       | Poor
  250    |        100        |      Very High  | Very Poor
    0    |        100        |      DANGEROUS  | None (OOM risk!)

Observation:
- Prefetch 1→10: significant throughput improvement
- Prefetch 10→250: diminishing returns
- Sweet spot: 10-50 cho hầu hết workloads
- Prefetch 0 (unlimited): NEVER in production
```

**Prefetch và multi-consumer fairness:**

```
2 consumers, prefetch=100, queue có 200 messages:

Consumer A (fast, 1ms/msg):   gets messages 1-100, processes all in 100ms
Consumer B (slow, 100ms/msg): gets messages 101-200, processes all in 10s

Consumer A finishes → idle 9.9 seconds! → queue trống
Consumer B still working → 100 messages buffered locally

Prefetch=10:
Consumer A: gets 1-10, processes all in 10ms, gets 21-30, ...
Consumer B: gets 11-20, processes msg 11 (100ms), ...
→ Consumer A processes MORE messages (fair by speed, not count)
→ Much better utilization!
```

---

### 4.2 Flow Control — RabbitMQ Tự Bảo Vệ

#### WHY — Backpressure là cần thiết

Producer nhanh hơn consumer → queue tăng → memory tăng → broker crash. RabbitMQ có **multiple layers** of flow control để ngăn điều này.

#### WHAT — 3 Layers of Flow Control

```
Layer 1: Memory Watermark (Broker-level)
  ├── Default: 40% of system RAM
  ├── Trigger: RabbitMQ memory > watermark
  ├── Action: BLOCK tất cả publishers (connection blocked)
  ├── Consumer vẫn chạy → drain queues → memory giảm → unblock
  └── Config: vm_memory_high_watermark.relative = 0.4

Layer 2: Disk Alarm (Broker-level)
  ├── Default: 50MB free disk
  ├── Trigger: Free disk < alarm threshold
  ├── Action: BLOCK tất cả publishers + STOP persistence
  ├── Broker refuse mọi publish, kể cả non-persistent
  └── Config: disk_free_limit.absolute = 2GB

Layer 3: Credit-Based Flow (Connection/Channel-level)
  ├── Internal mechanism: mỗi process (connection, channel, queue) có "credits"
  ├── Khi process chậm (queue write slow) → hết credits
  ├── Upstream process bị block cho đến khi credits replenish
  ├── Fine-grained: chỉ block connections gửi đến queue đang chậm
  └── Transparent cho clients (ngoại trừ throughput giảm)
```

**Memory Watermark Flow:**

```
Memory usage timeline:

100% ┬──────────────────────────────────────
     │                              ← Broker crash (OOM kill)
 80% ┤                              
     │                   ← DANGER ZONE
 60% ┤
     │
 40% ┤──────── Watermark ─────────  ← Publishers BLOCKED 🚫
     │         /                \
 30% ┤        /   consumers      \  ← Publishers UNBLOCKED ✅
     │       /    drain queues    \
 20% ┤      /                      \
     │     /                        \
 10% ┤────/                          \────
     │
  0% ┴──────────────────────────────────────
     t=0     t=1     t=2     t=3     t=4
```

#### HOW — Configure Flow Control

```ini
# rabbitmq.conf

# Memory watermark: 40% of RAM (default)
vm_memory_high_watermark.relative = 0.4
# Hoặc absolute: 2GB
# vm_memory_high_watermark.absolute = 2GB

# Paging: khi memory đạt 50% of watermark → start paging messages to disk
vm_memory_high_watermark_paging_ratio = 0.5
# Ví dụ: 16GB RAM, watermark=40%=6.4GB, paging ratio=50%=3.2GB
# Memory > 3.2GB → start paging (proactive)
# Memory > 6.4GB → block publishers (reactive)

# Disk alarm: minimum 2GB free
disk_free_limit.absolute = 2GB
# Hoặc relative: 1.5x of RAM
# disk_free_limit.relative = 1.5
```

**Client-side: detect và handle blocked connections:**

```go
conn, _ := amqp.Dial(url)

// RabbitMQ gửi Connection.Blocked khi flow control active
blockings := conn.NotifyBlocked(make(chan amqp.Blocking, 1))

go func() {
    for b := range blockings {
        if b.Active {
            log.Printf("CONNECTION BLOCKED: %s — reduce publish rate!", b.Reason)
            // Actions: reduce publish rate, buffer locally, alert
        } else {
            log.Printf("CONNECTION UNBLOCKED — resume normal rate")
        }
    }
}()
```

#### Trade-off: Watermark Settings

| Setting | Producer Impact | Memory Safety | Recommendation |
|---------|---------------|---------------|----------------|
| **0.2 (20%)** | Blocked thường xuyên | Rất safe | Over-conservative |
| **0.4 (40%)** | Blocked khi load spike | Safe | **Production default** |
| **0.6 (60%)** | Hiếm khi blocked | Risky | High-throughput, monitor chặt |
| **0.8 (80%)** | Gần như không blocked | Dangerous | ❌ DON'T |

---

### 4.3 Classic Queue Storage và Lazy Queue Caveat

#### WHY — Vì sao nội dung này cần caveat version?

Trong RabbitMQ hiện hành, classic queue không còn dùng `x-queue-mode=lazy` như một tuning lever production. Lazy mode là cơ chế lịch sử; ở các bản mới setting này bị bỏ qua hoặc chỉ còn giá trị tham khảo. Classic queues hiện đã có hành vi ghi disk và giữ memory ổn định hơn trước. Vấn đề cần quản trị vẫn là:
- Queue có 10M messages × 1KB = 10GB RAM → expensive hoặc OOM
- Burst traffic → memory spike → flow control triggers → publishers blocked

Với workloads mới cần HA + data safety, ưu tiên quorum queues và giới hạn queue length/bytes bằng policy. Với classic queues legacy, kiểm tra version RabbitMQ trước khi tin vào bất kỳ setting lazy nào.

#### WHAT — Classic Queue vs Lazy Queue vs Quorum Queue

```
Classic Queue (current behavior):
  Message arrive → buffered briefly → written to disk; hot subset kept in memory
  Memory: bounded hơn các bản cũ
  Latency: low cho hot messages
  Risk: vẫn cần length/byte limits và consumer capacity

Quorum Queue (WAL-based):
  Message arrive → write to WAL (disk) → cache in memory (configurable limit)
  Memory: CONFIGURABLE (x-max-in-memory-length/bytes)
  Latency: MEDIUM (balanced)
  Safe: Built-in memory control
```

#### HOW — Không dùng lazy mode cho lab mới

```bash
# Thay vì set queue-mode=lazy, đặt limit và DLX rõ ràng cho queue lớn
rabbitmqctl set_policy archive-limits "^logs\." \
  '{"max-length-bytes":10737418240,"overflow":"reject-publish","dead-letter-exchange":"logs.dlx"}' \
  --apply-to queues
```

#### Trade-off: Queue Storage Modes

| Tiêu chí | Classic Queue hiện hành | Quorum Queue |
|----------|--------------------------|--------------|
| **Memory usage** | Ổn định hơn bản cũ, vẫn cần limits | Disk-first/WAL, predictable hơn |
| **Large queues** | Dùng limits + DLX; không dựa vào lazy mode | Phù hợp hơn nếu cần durability/HA |
| **HA** | Single queue replica; mirrored queues deprecated | ✅ Raft |
| **Recommendation** | Legacy hoặc queue không cần replication | **Production default** |

**Production recommendation:** Dùng **quorum queues** thay vì lazy queues cho production mới. Nếu vẫn vận hành classic queues legacy, kiểm tra chính xác version RabbitMQ và metric memory/disk trước khi áp dụng tài liệu cũ về `x-queue-mode=lazy`.

---

### 4.4 Production Monitoring — Prometheus + Grafana

#### WHY — Monitoring là bắt buộc cho Production

Không có monitoring → blind:
- Queue depth tăng mà không biết → consumer lag → stale data
- Memory approaching watermark → sudden block → publisher timeout
- Disk filling up → alarm → complete halt
- Consumer crash → unacked messages pile up → memory leak

#### WHAT — RabbitMQ Metrics Ecosystem

```
RabbitMQ ──metrics──> Prometheus ──query──> Grafana
    │                                        │
    ├── Built-in Prometheus endpoint         ├── Dashboards
    │   (/metrics, port 15692)               ├── Alerts
    └── Management API                       └── Notifications
        (/api/, port 15672)
```

**Key Metric Categories:**

```
1. Queue Metrics (per-queue):
   ├── rabbitmq_queue_messages_ready          — messages waiting for consumer
   ├── rabbitmq_queue_messages_unacked        — delivered but not ack'd
   ├── rabbitmq_queue_messages_total          — ready + unacked
   ├── rabbitmq_queue_messages_published_total— total publish rate
   ├── rabbitmq_queue_messages_delivered_total— total deliver rate
   ├── rabbitmq_queue_messages_acked_total    — total ack rate
   └── rabbitmq_queue_consumers              — consumer count

2. Node Metrics:
   ├── rabbitmq_process_resident_memory_bytes — memory usage
   ├── rabbitmq_disk_space_available_bytes    — free disk
   ├── rabbitmq_erlang_processes_used         — Erlang process count
   ├── rabbitmq_connections_opened_total      — connection count
   └── rabbitmq_channels_opened_total         — channel count

3. Cluster Metrics:
   ├── rabbitmq_cluster_node_count            — nodes in cluster
   ├── rabbitmq_raft_log_entries              — quorum queue Raft log
   └── rabbitmq_raft_term_total               — leader elections count
```

Metric names can differ by RabbitMQ version, plugin configuration and whether you scrape `/metrics` or `/metrics/detailed`. Treat the names below as common examples, then validate in your running lab with:

```bash
curl -s http://localhost:15692/metrics | grep '^rabbitmq_queue_' | head
curl -s 'http://localhost:15692/metrics/detailed?family=queue_metrics' | grep '^rabbitmq_detailed_queue_' | head
```

The detailed endpoint often uses `rabbitmq_detailed_*` series and supports family filters; dashboard JSON from the internet may assume a different prefix.

#### HOW — Alerting Rules

**Critical Alerts (page oncall):**

| Alert | Condition | Impact |
|-------|-----------|--------|
| **Node Down** | `rabbitmq_cluster_node_count < expected` | HA degraded |
| **Disk Alarm** | `rabbitmq_disk_space_available_bytes < 1GB` | Publishers blocked |
| **Memory > 80%** | `rabbitmq_process_resident_memory_bytes > 0.8 * total` | Flow control imminent |
| **Queue Consumers = 0** | `rabbitmq_queue_consumers == 0 AND messages > 0` | Messages piling up |
| **Network Partition** | `rabbitmq_cluster_partition_count > 0` | Split-brain risk |

**Warning Alerts (investigate):**

| Alert | Condition | Impact |
|-------|-----------|--------|
| **Consumer Lag** | `rate(messages_ready) > rate(messages_delivered) for 10m` | Growing backlog |
| **DLQ Depth > 0** | `messages_ready{queue="*.dead-letter"} > 0` | Failed messages |
| **Unacked Growing** | `messages_unacked > prefetch × consumers × 2` | Consumer stuck |
| **High Redelivery** | `rate(messages_redelivered) > 10/min` | Consumer issues |
| **Queue > 100K** | `messages_total > 100000` | Need capacity review |

**Prometheus Alert Rules Example:**

```yaml
groups:
  - name: rabbitmq
    rules:
      - alert: RabbitMQNodeDown
        expr: rabbitmq_identity_info == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "RabbitMQ node down"
          
      - alert: RabbitMQQueueBacklog
        expr: rabbitmq_queue_messages_ready > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Queue {{ $labels.queue }} has {{ $value }} messages backlog"
          
      - alert: RabbitMQDLQNotEmpty
        expr: rabbitmq_queue_messages_ready{queue=~".*dead-letter.*"} > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "DLQ {{ $labels.queue }} has {{ $value }} failed messages"
          
      - alert: RabbitMQMemoryHigh
        expr: rabbitmq_process_resident_memory_bytes / rabbitmq_resident_memory_limit_bytes > 0.8
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "RabbitMQ memory usage > 80%"
```

---

### 4.5 RabbitMQ Streams — Stream Queue Type (Should Learn)

#### WHY — Tại sao RabbitMQ thêm Streams?

RabbitMQ classic model: message **consumed = deleted** từ queue. Kafka model: message **retained** trong log, consumers track offset.

RabbitMQ Streams (từ v3.9) mang Kafka-like behavior vào RabbitMQ:
- Messages **retained** (không bị xóa sau consume)
- Multiple consumers đọc **cùng stream** với **offset riêng**
- **Replay** từ bất kỳ offset nào
- **Higher throughput** so với classic/quorum queues

#### WHAT — Stream Queue Type

```
Classic/Quorum Queue:
  Publisher ──> [Queue: msg1, msg2, msg3] ──> Consumer A (msg consumed, removed)
                                               Consumer B (gets remaining messages)

Stream Queue:
  Publisher ──> [Stream: msg1, msg2, msg3, msg4, msg5, ...]
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               Consumer A    Consumer B    Consumer C
               offset=1     offset=3      offset=1
               (reading      (reading      (replay from
                from start)   latest)       beginning)
  
  Messages NEVER deleted (until retention policy)
```

#### HOW — Declare và Use Stream Queue

```go
// Declare stream queue
ch.QueueDeclare("events.stream", true, false, false, false, amqp.Table{
    "x-queue-type":                   "stream",
    "x-max-length-bytes":             5368709120, // 5GB retention
    "x-max-age":                      "7D",       // 7 ngày retention
    "x-stream-max-segment-size-bytes": 536870912, // 500MB per segment
})

// Publish — giống classic queue
ch.PublishWithContext(ctx, "", "events.stream", false, false, amqp.Publishing{
    Body: payload,
})

// Consume — cần set offset
ch.Qos(100, 0, false)
msgs, _ := ch.Consume("events.stream", "my-consumer", false, false, false, false,
    amqp.Table{
        "x-stream-offset": "first",    // Từ đầu stream
        // "x-stream-offset": "last",   // Chỉ messages mới
        // "x-stream-offset": "next",   // Sau message cuối consumer này đọc
        // "x-stream-offset": int64(42), // Từ offset cụ thể
        // "x-stream-offset": time.Now().Add(-1*time.Hour), // 1 giờ trước
    },
)
```

#### RabbitMQ Streams vs Kafka

| Tiêu chí | RabbitMQ Streams | Apache Kafka |
|----------|-----------------|-------------|
| **Throughput** | ~500K-1M msg/s | ~1-2M msg/s per partition |
| **Retention** | By size / age | By size / age / compaction |
| **Consumer groups** | Single Active Consumer | Native consumer groups |
| **Partitioning** | Super streams (manual) | Native partitions |
| **Exactly-once** | Không | Kafka transaction/EOS trong phạm vi Kafka; external side effects vẫn cần idempotency |
| **Stream processing** | Không built-in | Kafka Streams, ksqlDB |
| **Schema Registry** | Không | Confluent Schema Registry |
| **Ecosystem** | RabbitMQ ecosystem | Kafka Connect, MirrorMaker |
| **Operations** | Simpler (Erlang) | Complex (JVM, ZK/KRaft) |
| **Learning curve** | Dễ nếu đã biết RabbitMQ | Dốc hơn |
| **Maturity** | Mới (v3.9, 2021) | Mature (2011) |

#### Khi nào dùng RabbitMQ Streams vs Kafka?

```
✅ Dùng RabbitMQ Streams khi:
  - Đã có RabbitMQ infrastructure
  - Cần replay/audit trail cho một số queues
  - Throughput requirement < 1M msg/s
  - Không cần stream processing (Kafka Streams, ksqlDB)
  - Team quen RabbitMQ, không muốn thêm Kafka

✅ Dùng Kafka khi:
  - Throughput > 1M msg/s
  - Cần native partitioning cho parallel processing
  - Cần consumer groups với auto-rebalancing
  - Cần stream processing (joins, aggregations, windowing)
  - Cần schema evolution (Schema Registry)
  - Event sourcing là core architecture pattern
  - CDC (Change Data Capture) use case
```

**Bottom line:** RabbitMQ Streams là "good enough" cho simple stream use cases khi đã có RabbitMQ. Kafka vẫn là king cho serious stream processing và high-throughput event streaming.

---

### 4.6 OS-Level Tuning (Should Learn)

#### Key OS Settings cho Production RabbitMQ

```bash
# 1. File Descriptors — RabbitMQ cần rất nhiều (1 per connection + channel + queue)
# Default: 1024 — KHÔNG ĐỦ cho production
# Recommended: 65536+

# /etc/security/limits.conf
rabbitmq soft nofile 65536
rabbitmq hard nofile 65536

# Verify:
rabbitmqctl eval 'file_handle_cache:info().'

# 2. TCP Tuning
# /etc/sysctl.conf
net.core.somaxconn = 4096          # Max socket backlog
net.ipv4.tcp_max_syn_backlog = 4096
net.core.rmem_max = 16777216       # 16MB receive buffer
net.core.wmem_max = 16777216       # 16MB send buffer
net.ipv4.tcp_keepalive_time = 60   # Detect dead connections faster

# 3. Transparent Huge Pages — DISABLE
# THP gây latency spikes do Erlang VM memory allocation patterns
echo never > /sys/kernel/mm/transparent_hugepage/enabled

# 4. Disk I/O Scheduler
# Quorum queues benefit from deadline/none scheduler
echo none > /sys/block/sda/queue/scheduler  # For NVMe/SSD
```

---

## 5. Trade-off Analysis

### RabbitMQ Performance Optimization Decision Tree

```
"My RabbitMQ is slow" → Where is the bottleneck?

1. Publisher slow?
   ├── Check: flow control active? (Connection.Blocked)
   │     YES → memory too high, consumers too slow
   │     NO ↓
   ├── Check: publisher confirms latency?
   │     HIGH → disk I/O bottleneck (SSD? quorum queue replication?)
   │     OK ↓
   └── Check: batch many small publishes?
         YES → batch + compress + reduce message count

2. Consumer slow?
   ├── Check: prefetch count?
   │     =1 → increase to 10-50
   │     OK ↓
   ├── Check: processing time per message?
   │     HIGH → optimize business logic, scale consumers
   │     OK ↓
   ├── Check: consumer ack latency?
   │     HIGH → ack before heavy post-processing
   │     OK ↓
   └── Check: consumer count vs queue count?
         1 consumer on queue with 100K messages → add consumers

3. Queue growing?
   ├── Consumer slower than publisher?
   │     YES → scale consumers, optimize processing
   │     NO ↓
   ├── Consumer down?
   │     YES → fix consumer, restart
   │     NO ↓
   └── Burst traffic?
         YES → quorum queue hoặc classic queue có max-length/max-length-bytes policy
               + autoscaling consumers
```

### Production Checklist — RabbitMQ

```
Infrastructure:
  ☐ Cluster: 3+ nodes (odd number)
  ☐ Partition handling: pause_minority
  ☐ Disk: SSD/NVMe cho data directory
  ☐ Memory: >= 4GB per node (8GB recommended)
  ☐ File descriptors: >= 65536
  ☐ Load balancer: HAProxy/Nginx in front

Queues:
  ☐ Quorum queues cho production data
  ☐ DLX configured cho mỗi queue
  ☐ TTL cho queues có retention requirement
  ☐ x-max-length hoặc x-max-length-bytes để prevent unbounded growth

Publishing:
  ☐ Publisher confirms (async)
  ☐ Persistent messages cho important data
  ☐ Connection recovery + exponential backoff
  ☐ Separate publish/consume connections

Consuming:
  ☐ Manual ack (autoAck=false)
  ☐ Prefetch tuned per workload
  ☐ Idempotent consumers (MessageId deduplication)
  ☐ Retry strategy (DLX + TTL hoặc x-delivery-limit)
  ☐ Graceful shutdown (finish processing before exit)

Monitoring:
  ☐ Prometheus + Grafana setup
  ☐ Queue depth alerts
  ☐ Memory/disk alerts
  ☐ Consumer lag alerts
  ☐ DLQ depth alerts
  ☐ Node down alerts
  ☐ Cluster partition alerts

Security:
  ☐ TLS cho client connections
  ☐ Strong passwords (không dùng guest/guest)
  ☐ Vhost isolation per tenant/environment
  ☐ User permissions (read/write/configure per vhost)
  ☐ Management UI restricted access
```

### Tổng kết Phase 2 — RabbitMQ vs NATS vs (upcoming) Kafka

| Tiêu chí | NATS Core | NATS JetStream | RabbitMQ |
|----------|-----------|----------------|----------|
| **Throughput** | ~10M msg/s | ~1M msg/s | ~50K msg/s (per queue) |
| **Latency** | ~100μs | ~500μs | ~1-5ms |
| **Persistence** | ❌ | ✅ Stream | ✅ Durable queues |
| **Routing** | Subject wildcards | Subject wildcards | Exchange types (rich) |
| **Retry/DLQ** | ❌ | Basic | ✅ Rich (DLX, TTL, retry queues) |
| **Priority** | ❌ | ❌ | ✅ Priority queues |
| **Message ordering** | Per-subject | Per-stream | Per-queue (FIFO) |
| **Consumer groups** | Queue groups | Consumers | Competing consumers |
| **Operations** | Simple (Go binary) | Medium | Medium (Erlang VM) |
| **Monitoring** | Basic | Medium | ✅ Rich (Management UI, Prometheus) |
| **Best for** | Low latency, simple pub/sub | Stream + persistence (simple) | Task queues, routing, reliability |
| **Not for** | Persistence, routing complex | High-volume streaming | Ultra-high throughput |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Start với prefetch=10, tune dựa trên metrics**
   ```go
   // ✅ Measure, don't guess
   ch.Qos(10, 0, false) // Start here
   
   // Monitor: consumer utilization metric
   // If < 80% → increase prefetch
   // If messages_unacked high → decrease prefetch
   ```

2. **Set memory watermark dựa trên workload**
   ```ini
   # Standard workload
   vm_memory_high_watermark.relative = 0.4
   
   # Many large queues (quorum/classic with limits)
   vm_memory_high_watermark.relative = 0.5
   vm_memory_high_watermark_paging_ratio = 0.5
   
   # Small VM (< 4GB RAM)
   vm_memory_high_watermark.absolute = 1GB
   ```

3. **Handle Connection.Blocked ở publisher**
   ```go
   blockings := conn.NotifyBlocked(make(chan amqp.Blocking, 1))
   go func() {
       for b := range blockings {
           if b.Active {
               // Buffer messages locally, reduce rate, alert
               log.Printf("FLOW CONTROL: %s", b.Reason)
           }
       }
   }()
   ```

4. **Disk alarm threshold = 2x expected queue size**
   ```ini
   # Nếu queues thường hold ~5GB messages under load
   disk_free_limit.absolute = 10GB
   
   # Rule of thumb: disk_free > 2 × max_queue_size_expected
   ```

5. **Prometheus metrics endpoint riêng port**
   ```ini
   # rabbitmq.conf — enable Prometheus plugin
   # rabbitmq-plugins enable rabbitmq_prometheus
   
   # Metrics at :15692/metrics (separate from management :15672)
   prometheus.return_per_object_metrics = true
   ```

### Common Pitfalls

1. **Pitfall: Prefetch = 0 (unlimited)**
   ```
   ❌ ch.Qos(0, 0, false) → unlimited prefetch
      1M messages in queue → ALL delivered to 1 consumer → OOM!
   
   ✅ Always set prefetch > 0 in production
   ```

2. **Pitfall: Ignoring flow control**
   ```
   ❌ Producer keeps publishing while Connection.Blocked
      → Messages buffered in TCP stack → timeout → error
      → No visibility into why publishes fail
   
   ✅ Listen Connection.Blocked, back off, alert
   ```

3. **Pitfall: Không monitor queue depth**
   ```
   Queue 500K messages → nobody notices
   Queue 5M messages → memory > watermark → flow control
   Queue 10M messages → disk full → alarm → COMPLETE HALT
   
   ✅ Alert at 10K messages (investigate)
   ✅ Alert at 100K messages (action required)
   ✅ Alert at 1M messages (critical — scale consumers NOW)
   ```

4. **Pitfall: Monitoring vhost "/" mà quên encode**
   ```bash
   # ❌ Wrong
   curl http://localhost:15672/api/queues///my-queue
   
   # ✅ Correct — "/" phải URL-encode thành "%2F"
   curl http://localhost:15672/api/queues/%2F/my-queue
   ```

5. **Pitfall: HDD cho persistent messages**
   ```
   HDD: ~200 IOPS → ~200 persistent msg/s per queue
   SSD: ~50K IOPS → ~50K persistent msg/s per queue
   NVMe: ~500K IOPS → disk không phải bottleneck
   
   ❌ "RabbitMQ slow" + HDD = disk bottleneck
   ✅ Luôn dùng SSD/NVMe cho production
   ```

---

## 7. Performance Considerations

### Benchmark Numbers — Complete Reference

```
Test conditions: 1KB messages, single node, SSD, 16GB RAM
Numbers are order-of-magnitude — your mileage will vary.

╔══════════════════════════════════════════════════════════════════╗
║ Scenario                                    │ Throughput (msg/s) ║
╠══════════════════════════════════════════════════════════════════╣
║ PUBLISHING                                  │                    ║
║ Non-persistent, no confirms                 │ ~100,000           ║
║ Persistent, no confirms                     │ ~50,000            ║
║ Persistent, async confirms                  │ ~30,000            ║
║ Persistent, individual confirms             │ ~500               ║
║ Persistent, transactions                    │ ~3,000             ║
╠══════════════════════════════════════════════════════════════════╣
║ QUEUE TYPE                                  │                    ║
║ Classic queue                               │ ~50,000            ║
║ Classic queue with large backlog            │ version-dependent  ║
║ Quorum queue (3 replicas)                   │ ~30,000            ║
║ Stream queue                                │ ~800,000           ║
╠══════════════════════════════════════════════════════════════════╣
║ CONSUMING                                   │                    ║
║ Auto-ack                                    │ ~100,000           ║
║ Manual ack, prefetch=1                      │ ~1,000             ║
║ Manual ack, prefetch=10                     │ ~8,000             ║
║ Manual ack, prefetch=50                     │ ~30,000            ║
║ Manual ack, prefetch=100                    │ ~40,000            ║
╠══════════════════════════════════════════════════════════════════╣
║ EXCHANGE TYPE OVERHEAD                      │                    ║
║ Direct exchange                             │ baseline           ║
║ Fanout exchange                             │ +5%                ║
║ Topic exchange                              │ -15-20%            ║
║ Headers exchange                            │ -25-30%            ║
╠══════════════════════════════════════════════════════════════════╣
║ CLUSTER (3-node)                            │                    ║
║ Classic queue (non-replicated)              │ ~45,000            ║
║ Quorum queue                                │ ~30,000            ║
║ Cross-node consume (proxy overhead)         │ ~25,000            ║
╚══════════════════════════════════════════════════════════════════╝
```

### Scaling Patterns

```
Vertical scaling (per node):
  - More RAM → larger queues before paging
  - Faster disk (SSD/NVMe) → higher persistent throughput
  - More CPU → more connections/channels concurrent
  - Limit: ~50K msg/s per queue (AMQP overhead)

Horizontal scaling (more nodes):
  - More nodes → more queues distributed across nodes
  - ⚠️ NOT automatic: must design queue distribution
  - Pattern: shard queues (orders.shard-1, orders.shard-2, ...)
  - Client-side routing: hash(order_id) % num_shards → shard queue

Queue sharding example:
  orders.shard-0 → Node 1 (leader)
  orders.shard-1 → Node 2 (leader)  
  orders.shard-2 → Node 3 (leader)
  
  Publisher: publish to orders.shard-{hash(key) % 3}
  Consumer: consume from all shards (3 consumer groups)
  Throughput: ~30K × 3 = ~90K msg/s total

Comparison with Kafka:
  Kafka: partitioning built-in, automatic consumer assignment
  RabbitMQ: manual sharding, client-side routing
  → This is WHY Kafka wins for high-throughput use cases
```

---

## 8. Hands-on Lab

### 8.1 Setup: Monitoring Stack

**File `docker-compose-monitoring.yml`:**
```yaml
version: "3.8"

services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
      - "15692:15692"  # Prometheus metrics endpoint
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
    command: >
      sh -c "rabbitmq-plugins enable --offline rabbitmq_prometheus && exec rabbitmq-server"
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    depends_on:
      rabbitmq:
        condition: service_healthy

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin123
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  rabbitmq-data:
  prometheus-data:
  grafana-data:
```

**File `prometheus.yml`:**
```yaml
global:
  scrape_interval: 10s
  evaluation_interval: 10s

scrape_configs:
  - job_name: "rabbitmq"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["rabbitmq:15692"]
    scrape_interval: 5s

  - job_name: "rabbitmq-detailed"
    metrics_path: "/metrics/detailed"
    params:
      family: ["queue_metrics", "queue_consumer_count"]
    static_configs:
      - targets: ["rabbitmq:15692"]
    scrape_interval: 5s
```

```bash
# Setup
mkdir -p day-09-performance-production/lab && cd day-09-performance-production/lab

# Tạo prometheus.yml (nội dung bên trên)
# Tạo docker-compose-monitoring.yml (nội dung bên trên)

docker compose -f docker-compose-monitoring.yml up -d

# Wait for stack
sleep 30

# Verify:
# RabbitMQ Management: http://localhost:15672 (admin/admin123)
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin123)

# Verify Prometheus scraping RabbitMQ
curl -s http://localhost:15692/metrics | head -20

# Setup Go project
go mod init performance-lab
go get github.com/rabbitmq/amqp091-go
```

### 8.2 Lab 1: Prefetch Tuning Benchmark

**File `prefetch_benchmark.go`:**
```go
package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

const (
	messageCount = 5000
	queueName    = "bench.prefetch"
)

func main() {
	conn, _ := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	defer conn.Close()

	prefetchValues := []int{1, 5, 10, 25, 50, 100, 250}

	fmt.Println("╔═══════════════════════════════════════════════════╗")
	fmt.Println("║ Prefetch Benchmark — 5000 messages, 1ms process  ║")
	fmt.Println("╠════════════╤════════════╤════════════╤═══════════╣")
	fmt.Println("║ Prefetch   │ Time       │ msg/s      │ vs pf=1   ║")
	fmt.Println("╠════════════╪════════════╪════════════╪═══════════╣")

	var baselineRate float64

	for _, pf := range prefetchValues {
		publishMessages(conn)
		elapsed, rate := consumeWithPrefetch(conn, pf)

		if pf == 1 {
			baselineRate = rate
		}

		speedup := rate / baselineRate
		fmt.Printf("║ %10d │ %8.2fs  │ %8.0f   │ %5.1fx    ║\n",
			pf, elapsed.Seconds(), rate, speedup)
	}

	fmt.Println("╚════════════╧════════════╧════════════╧═══════════╝")
}

func publishMessages(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.QueueDelete(queueName, false, false, false)
	ch.QueueDeclare(queueName, false, false, false, false, nil)

	ctx := context.Background()
	for i := 0; i < messageCount; i++ {
		ch.PublishWithContext(ctx, "", queueName, false, false,
			amqp.Publishing{Body: []byte(fmt.Sprintf("msg-%d", i))},
		)
	}
}

func consumeWithPrefetch(conn *amqp.Connection, prefetch int) (time.Duration, float64) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Qos(prefetch, 0, false)
	msgs, _ := ch.Consume(queueName, "", false, false, false, false, nil)

	var count int64
	var wg sync.WaitGroup
	wg.Add(1)

	start := time.Now()

	go func() {
		defer wg.Done()
		for msg := range msgs {
			time.Sleep(1 * time.Millisecond) // Simulate processing
			msg.Ack(false)
			if atomic.AddInt64(&count, 1) >= messageCount {
				return
			}
		}
	}()

	wg.Wait()
	elapsed := time.Since(start)
	rate := float64(messageCount) / elapsed.Seconds()
	return elapsed, rate
}
```

```bash
go run prefetch_benchmark.go
```

**Expected output (approximate):**
```
╔═══════════════════════════════════════════════════╗
║ Prefetch Benchmark — 5000 messages, 1ms process  ║
╠════════════╤════════════╤════════════╤═══════════╣
║ Prefetch   │ Time       │ msg/s      │ vs pf=1   ║
╠════════════╪════════════╪════════════╪═══════════╣
║          1 │    6.50s   │      769   │   1.0x    ║
║          5 │    5.80s   │      862   │   1.1x    ║
║         10 │    5.40s   │      926   │   1.2x    ║
║         25 │    5.20s   │      962   │   1.3x    ║
║         50 │    5.10s   │      980   │   1.3x    ║
║        100 │    5.08s   │      984   │   1.3x    ║
║        250 │    5.05s   │      990   │   1.3x    ║
╚════════════╧════════════╧════════════╧═══════════╝
```

### 8.3 Lab 2: Load Test with Monitoring

**File `load_runner.go`:**
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

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	mode := "all"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	conn, _ := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	defer conn.Close()

	switch mode {
	case "setup":
		setup(conn)
	case "produce":
		produce(conn)
	case "consume":
		consume(conn)
	default:
		setup(conn)
		go consume(conn)
		time.Sleep(time.Second)
		produce(conn)
	}
}

func setup(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.ExchangeDeclare("loadtest", "direct", true, false, false, false, nil)

	// DLX
	ch.ExchangeDeclare("loadtest.dlx", "fanout", true, false, false, false, nil)
	ch.QueueDeclare("loadtest.dead-letter", true, false, false, false, nil)
	ch.QueueBind("loadtest.dead-letter", "", "loadtest.dlx", false, nil)

	// Main queue — quorum for production-like behavior
	ch.QueueDeclare("loadtest.queue", true, false, false, false, amqp.Table{
		"x-queue-type":           "quorum",
		"x-delivery-limit":      3,
		"x-dead-letter-exchange": "loadtest.dlx",
	})
	ch.QueueBind("loadtest.queue", "test", "loadtest", false, nil)

	log.Println("Load test topology setup complete")
}

func produce(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Confirm(false)
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 1000))
	blockings := conn.NotifyBlocked(make(chan amqp.Blocking, 1))

	var blocked int32

	go func() {
		for b := range blockings {
			if b.Active {
				atomic.StoreInt32(&blocked, 1)
				log.Printf("FLOW CONTROL ACTIVE: %s", b.Reason)
			} else {
				atomic.StoreInt32(&blocked, 0)
				log.Println("FLOW CONTROL RELEASED")
			}
		}
	}()

	// Drain confirms in background
	var ackCount, nackCount int64
	go func() {
		for c := range confirms {
			if c.Ack {
				atomic.AddInt64(&ackCount, 1)
			} else {
				atomic.AddInt64(&nackCount, 1)
			}
		}
	}()

	ctx := context.Background()
	var totalSent int64
	rate := 1000 // messages per second target
	start := time.Now()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	log.Printf("Producing at ~%d msg/s. Watch Grafana at http://localhost:3000", rate)
	log.Println("Press Ctrl+C to stop")

	ticker := time.NewTicker(time.Second / time.Duration(rate))
	defer ticker.Stop()

	statsTicker := time.NewTicker(5 * time.Second)
	defer statsTicker.Stop()

	for {
		select {
		case <-sig:
			elapsed := time.Since(start)
			log.Printf("DONE: sent=%d, acked=%d, nacked=%d, duration=%v, rate=%.0f msg/s",
				totalSent, atomic.LoadInt64(&ackCount), atomic.LoadInt64(&nackCount),
				elapsed, float64(totalSent)/elapsed.Seconds())
			return

		case <-statsTicker.C:
			elapsed := time.Since(start)
			log.Printf("STATS: sent=%d, acked=%d, nacked=%d, blocked=%v, rate=%.0f msg/s",
				totalSent, atomic.LoadInt64(&ackCount), atomic.LoadInt64(&nackCount),
				atomic.LoadInt32(&blocked) == 1, float64(totalSent)/elapsed.Seconds())

		case <-ticker.C:
			if atomic.LoadInt32(&blocked) == 1 {
				continue // Don't publish while blocked
			}

			id := atomic.AddInt64(&totalSent, 1)
			body, _ := json.Marshal(map[string]interface{}{
				"id":        id,
				"timestamp": time.Now().UnixMilli(),
				"payload":   "load test message",
			})

			ch.PublishWithContext(ctx, "loadtest", "test", false, false,
				amqp.Publishing{
					DeliveryMode: amqp.Persistent,
					ContentType:  "application/json",
					MessageId:    fmt.Sprintf("lt-%d", id),
					Body:         body,
				},
			)
		}
	}
}

func consume(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Qos(25, 0, false) // Tuned prefetch
	msgs, _ := ch.Consume("loadtest.queue", "load-consumer", false, false, false, false, nil)

	var processed int64
	start := time.Now()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	log.Println("Consumer started (prefetch=25)")
	log.Println("Concurrency caution: amqp.Channel is not generally safe for concurrent Ack/Nack; this lab keeps all acknowledgements on one goroutine.")

	workers := 5
	type result struct {
		msg amqp.Delivery
		ok  bool
	}
	msgChan := make(chan amqp.Delivery, 100)
	results := make(chan result, 100)

	// Fan-out to workers
	for i := 0; i < workers; i++ {
		go func(workerID int) {
			for msg := range msgChan {
				time.Sleep(5 * time.Millisecond) // Simulate 5ms processing
				results <- result{msg: msg, ok: true}
			}
		}(i)
	}

	go func() {
		for msg := range msgs {
			msgChan <- msg
		}
		close(msgChan)
	}()

	go func() {
		for r := range results {
			if r.ok {
				r.msg.Ack(false)
				count := atomic.AddInt64(&processed, 1)
				if count%1000 == 0 {
					elapsed := time.Since(start)
					log.Printf("Processed %d messages (%.0f msg/s)", count, float64(count)/elapsed.Seconds())
				}
			} else {
				r.msg.Nack(false, true)
			}
		}
	}()

	<-sig
	close(msgChan)
	log.Printf("Consumer stopped. Total processed: %d", atomic.LoadInt64(&processed))
}
```

```bash
# Start load test
go run load_runner.go

# Observe in Grafana:
# 1. Import RabbitMQ dashboard: ID 10991 (RabbitMQ Overview)
# 2. Or browse Prometheus: http://localhost:9090
#    Query: rabbitmq_queue_messages_ready{queue="loadtest.queue"}
#    Query: rate(rabbitmq_queue_messages_published_total{queue="loadtest.queue"}[1m])
```

### 8.4 Lab 3: Prometheus Queries

```bash
# Verify Prometheus is scraping RabbitMQ
curl -s 'http://localhost:9090/api/v1/targets' | jq '.data.activeTargets[] | {
  job: .labels.job,
  health: .health,
  lastScrape: .lastScrape
}'

# Query queue depth
curl -s 'http://localhost:9090/api/v1/query?query=rabbitmq_queue_messages{queue="loadtest.queue"}' | jq '.data.result[0].value[1]'

# Query publish rate (per second)
curl -s 'http://localhost:9090/api/v1/query?query=rate(rabbitmq_queue_messages_published_total{queue="loadtest.queue"}[1m])' | jq '.data.result[0].value[1]'

# Query memory usage
curl -s 'http://localhost:9090/api/v1/query?query=rabbitmq_process_resident_memory_bytes' | jq '.data.result[0].value[1]'

# Useful Grafana dashboard queries:
# Queue depth: rabbitmq_queue_messages_ready
# Publish rate: rate(rabbitmq_queue_messages_published_total[1m])
# Consume rate: rate(rabbitmq_queue_messages_delivered_total[1m])
# Unacked: rabbitmq_queue_messages_unacked
# Memory: rabbitmq_process_resident_memory_bytes
# Disk free: rabbitmq_disk_space_available_bytes
# Connections: rabbitmq_connections
```

### 8.5 Lab 4: Grafana Dashboard Setup

```bash
# Grafana: http://localhost:3000 (admin/admin123)

# 1. Add Prometheus data source:
#    Configuration → Data Sources → Add → Prometheus
#    URL: http://prometheus:9090
#    Save & Test

# 2. Import RabbitMQ dashboard:
#    Dashboards → Import → Dashboard ID: 10991
#    Select Prometheus data source
#    Import

# 3. Hoặc tạo custom dashboard với panels:
#    Panel 1: Queue Depth
#      Query: rabbitmq_queue_messages{queue=~"loadtest.*"}
#    Panel 2: Message Rates
#      Query: rate(rabbitmq_queue_messages_published_total[1m])
#      Query: rate(rabbitmq_queue_messages_delivered_total[1m])
#    Panel 3: Memory Usage
#      Query: rabbitmq_process_resident_memory_bytes / 1024 / 1024  (MB)
#    Panel 4: Consumer Count
#      Query: rabbitmq_queue_consumers
```

### 8.6 Lab 5: Flow Control Test

```bash
# Giảm memory watermark tạm thời để trigger flow control
docker exec rabbitmq rabbitmqctl eval 'application:set_env(rabbit, vm_memory_high_watermark, 0.05).'

# Run producer — sẽ bị blocked nhanh
go run load_runner.go produce
# Observe: "FLOW CONTROL ACTIVE" message

# Reset watermark
docker exec rabbitmq rabbitmqctl eval 'application:set_env(rabbit, vm_memory_high_watermark, 0.4).'
# Observe: "FLOW CONTROL RELEASED"
```

### 8.7 Cleanup

```bash
docker compose -f docker-compose-monitoring.yml down -v
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Prefetch=1 vs prefetch=100 cho video encoding tasks (mỗi task 30 giây).** Bạn chọn bao nhiêu? Tại sao? Nếu có 10 consumers, throughput tổng khác nhau thế nào?

   *Hint: Tasks 30s → prefetch 1-2. Prefetch 100 = 1 consumer "grab" 100 videos, others idle. Fairness > throughput cho long tasks.*

2. **Giải thích 3 layers of flow control trong RabbitMQ.** Layer nào client có thể detect? Layer nào transparent?

   *Hint: Memory watermark (client detects Connection.Blocked), disk alarm (client detects), credit-based flow (transparent). Client chỉ thấy 2 layers đầu.*

3. **Classic queue storage vs quorum queues: khi nào dùng cái nào?** Có nên dựa vào lazy mode không?

   *Hint: Quorum queues dùng WAL/disk-first và HA. `x-queue-mode=lazy` là tuning lịch sử cho classic queues và không còn là lever đáng tin ở RabbitMQ hiện hành.*

4. **Design question:** Setup monitoring cho RabbitMQ production serving 5 microservices. Liệt kê:
   - 5 metrics quan trọng nhất cần monitor
   - Alert thresholds cho mỗi metric
   - Dashboard panels cần có

   *Hint: Queue depth, memory %, disk free, consumer count, DLQ depth. See alerting rules in section 4.4.*

5. **RabbitMQ Streams vs Kafka — khi nào RabbitMQ Streams đủ?** Cho 3 use cases nên dùng Streams và 3 use cases BẮT BUỘC dùng Kafka.

   *Hint: Streams cho simple replay, audit log, low-volume event sourcing. Kafka cho high-throughput streaming, CDC, stream processing (joins, windowing).*

6. **Benchmark question:** Consumer đang xử lý 500 msg/s nhưng cần 2000 msg/s. Liệt kê 4 cách tăng throughput, từ dễ đến khó.

   *Hint: (1) Increase prefetch, (2) Add more consumers, (3) Optimize process time, (4) Queue sharding across nodes.*

7. **Production checklist:** Bạn deploy RabbitMQ mới. Cho 5 settings PHẢI thay đổi so với default trước khi go-live.

   *Hint: Password (!= guest), file descriptors (>= 65536), disk alarm threshold (>= 2GB), memory watermark (tune), partition handling (pause_minority).*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [RabbitMQ Monitoring](https://www.rabbitmq.com/monitoring.html)
- [RabbitMQ Prometheus Plugin](https://www.rabbitmq.com/prometheus.html)
- [Memory and Disk Alarms](https://www.rabbitmq.com/alarms.html)
- [Flow Control](https://www.rabbitmq.com/flow-control.html)
- [Lazy Queues](https://www.rabbitmq.com/lazy-queues.html)
- [RabbitMQ Streams](https://www.rabbitmq.com/streams.html)

### Architecture & Design
- [RabbitMQ Best Practices — CloudAMQP (Performance)](https://www.cloudamqp.com/blog/part2-rabbitmq-best-practice.html)
- [RabbitMQ Performance Measurements — Pivotal](https://blog.rabbitmq.com/posts/2020/06/cluster-sizing-and-other-considerations/)
- [RabbitMQ vs Kafka — When to Use What](https://www.cloudamqp.com/blog/when-to-use-rabbitmq-or-apache-kafka.html)

### Production Operations
- [Production Checklist — RabbitMQ](https://www.rabbitmq.com/production-checklist.html)
- [RabbitMQ Grafana Dashboards](https://grafana.com/grafana/dashboards/10991)
- [RabbitMQ PerfTest — Benchmarking Tool](https://rabbitmq.github.io/rabbitmq-perf-test/stable/htmlsingle/)

### Deep Dive
- [RabbitMQ Streams — Architecture](https://blog.rabbitmq.com/posts/2021/07/rabbitmq-streams-overview/)
- [Erlang VM Tuning for RabbitMQ](https://www.rabbitmq.com/runtime.html)
- [RabbitMQ Sizing Calculator](https://rabbitmq.github.io/ra-sizing/)

### Videos
- [RabbitMQ Performance Tuning — RabbitMQ Summit](https://www.youtube.com/watch?v=K7k7ynNJvhY)
- [RabbitMQ Streams Deep Dive — RabbitMQ Summit 2021](https://www.youtube.com/watch?v=K-ReFhEH_UY)
- [Monitoring RabbitMQ with Prometheus — CloudAMQP](https://www.youtube.com/watch?v=3P5yVpvvA5A)
