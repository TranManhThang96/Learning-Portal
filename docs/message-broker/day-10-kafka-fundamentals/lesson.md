# Day 10: Kafka Fundamentals — Distributed Commit Log, Tại sao Kafka nhanh?

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** triết lý distributed commit log — tại sao Kafka không phải "message queue" mà là "event streaming platform"
2. **Nắm vững** các khái niệm core: topic, partition, offset, broker, segment, retention
3. **Giải thích được** tại sao Kafka nhanh — sequential I/O, zero-copy, page cache, batching
4. **Phân biệt rõ** Kafka vs RabbitMQ/NATS ở architectural level (log vs queue)
5. **Thực hành** setup Kafka cluster với Docker, tạo topic, produce/consume messages đầu tiên

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 1-9 (messaging fundamentals, NATS, RabbitMQ)
- Hiểu queue vs pub/sub vs stream từ Day 1
- Hiểu delivery guarantees (at-most-once, at-least-once, exactly-once) từ Day 1 và Day 6
- Hiểu broker vs distributed log concept từ Day 1
- Docker và Docker Compose

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Distributed commit log philosophy — WHY Kafka
- Core concepts: topic, partition, offset, broker, segment
- Tại sao Kafka nhanh: sequential I/O, zero-copy, page cache
- Retention policies: time-based, size-based, compact
- Hands-on: setup Kafka + produce/consume messages bằng Go

### 🟡 Should Learn (nếu còn thời gian)
- Log compaction chi tiết
- Segment internals: index files, timeindex
- Kafka vs RabbitMQ/NATS architectural comparison table

### 🟢 Optional Deep Dive
- Kafka source code: Log.scala, LogSegment.scala
- sendfile() system call và zero-copy deep dive
- Page cache tuning trên Linux cho Kafka

---

## 4. Lý thuyết (Theory)

### 4.1 Distributed Commit Log — Triết lý cốt lõi của Kafka

#### WHY — Tại sao cần một "log" thay vì "queue"?

Hãy tưởng tượng 2 mô hình:

**Database transaction log (WAL — Write-Ahead Log):**
- Mọi thay đổi được ghi tuần tự vào log
- Log là nguồn sự thật duy nhất (source of truth)
- Có thể replay log để rebuild lại state bất kỳ lúc nào

**Traditional message queue / volatile pub-sub (RabbitMQ, NATS Core):**
- RabbitMQ queue: message được gửi đến queue, consumer ack xong thì message bị xóa
- NATS Core: pub/sub in-memory, không persistence/replay nếu không dùng JetStream
- Queue/pub-sub kiểu này là "ống nước" — nước chảy qua rồi mất

Kafka chọn triết lý **log**: messages (gọi là **records**) được ghi tuần tự vào log, **không bị xóa sau khi consume**. Consumer chỉ di chuyển "con trỏ" (offset) trên log.

```
Traditional Queue (RabbitMQ):
  [msg1] [msg2] [msg3] [msg4]
     ↑ consumer lấy msg1 → msg1 bị xóa khỏi queue
  
Distributed Log (Kafka):
  [rec0] [rec1] [rec2] [rec3] [rec4] [rec5] [rec6] ...
                   ↑                    ↑
              Consumer A            Consumer B
              (offset=2)            (offset=5)
  
  → Cả hai consumer đọc CÙNG log, ở VỊ TRÍ KHÁC NHAU
  → Records KHÔNG bị xóa sau khi đọc
  → Consumer C có thể join và đọc lại TỪ ĐẦU
```

**Insight quan trọng:** Trong Kafka, **data ownership thuộc về log, không thuộc về consumer**. Consumer chỉ là "reader" di chuyển bookmark trên log.

#### WHAT — Kafka là gì?

Kafka là một **distributed, partitioned, replicated commit log** implemented as a **distributed streaming platform**. Nó không phải classic message queue theo nghĩa "consume xong là xóa", nhưng **consumer groups** tạo được hành vi queue-like: nhiều consumer trong cùng group cạnh tranh xử lý partitions và mỗi record thường được xử lý bởi một member trong group.

Core identity của Kafka:
- **Distributed**: chạy trên cluster nhiều brokers
- **Partitioned**: mỗi topic chia thành nhiều partitions cho parallelism
- **Replicated**: mỗi partition có nhiều bản sao cho fault tolerance
- **Commit log**: append-only, immutable, ordered sequence of records

#### HOW — Kafka Architecture Overview

```
                    Kafka Cluster
┌─────────────────────────────────────────────┐
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Broker 0 │  │ Broker 1 │  │ Broker 2 │  │
│  │          │  │          │  │          │  │
│  │ P0(L)    │  │ P0(F)    │  │ P0(F)    │  │
│  │ P1(F)    │  │ P1(L)    │  │ P1(F)    │  │
│  │ P2(F)    │  │ P2(F)    │  │ P2(L)    │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                             │
│  L = Leader    F = Follower                 │
│  Topic "orders" có 3 partitions (P0,P1,P2)  │
│  Replication factor = 3                     │
└─────────────────────────────────────────────┘
        ↑                          ↑
   Producers                  Consumers
   (write to leaders)        (read from leaders/followers)
```

### 4.2 Core Concepts Chi Tiết

#### Topic

**Analogy**: Topic giống như một **table** trong database. Nó là category/feed name mà records được publish vào.

```
Topic "user-events":     Chứa tất cả events liên quan đến user
Topic "order-events":    Chứa tất cả events liên quan đến orders  
Topic "payment-events":  Chứa tất cả events liên quan đến payments
```

Naming convention phổ biến: `<domain>.<entity>.<action>` hoặc `<team>.<service>.<event>`
```
ecommerce.orders.created
ecommerce.orders.completed
payment.transactions.processed
user.profiles.updated
```

#### Partition — Đơn vị parallelism

**WHY cần partition?**

Nếu topic chỉ có 1 log duy nhất → chỉ 1 consumer đọc tại 1 thời điểm → bottleneck. Partition cho phép **parallel processing**.

```
Topic "orders" với 3 partitions:

Partition 0: [rec0] [rec3] [rec6] [rec9]  ...  → Consumer 0
Partition 1: [rec1] [rec4] [rec7] [rec10] ...  → Consumer 1  
Partition 2: [rec2] [rec5] [rec8] [rec11] ...  → Consumer 2

→ 3 consumers đọc song song, throughput x3!
```

**Đặc tính quan trọng của partition:**
- **Ordering guarantee**: Records trong CÙNG partition được đọc theo thứ tự ghi (FIFO)
- **Không có global ordering**: Records GIỮA các partitions KHÔNG có thứ tự đảm bảo
- **Partition là đơn vị replication**: mỗi partition có leader và followers
- **Partition là đơn vị parallelism**: max consumers trong 1 consumer group = số partitions

```
ORDERING GUARANTEE:

Partition 0: [A₁] [A₂] [A₃]     → Consumer đọc A₁ → A₂ → A₃ (đúng thứ tự ✓)
Partition 1: [B₁] [B₂] [B₃]     → Consumer đọc B₁ → B₂ → B₃ (đúng thứ tự ✓)

Nhưng GIỮA partition 0 và 1:
  A₁ có thể đọc trước hoặc sau B₁ — KHÔNG có đảm bảo!
```

**Per-key ordering**: Nếu cần ordering cho 1 entity, dùng message key. Cùng key → cùng partition.

```
Key = "order-123"  → hash("order-123") % 3 = 1 → Partition 1
Key = "order-456"  → hash("order-456") % 3 = 0 → Partition 0
Key = "order-123"  → hash("order-123") % 3 = 1 → Partition 1 (CÙNG partition!)

→ Mọi events của order-123 đều vào Partition 1 → đọc đúng thứ tự
```

#### Offset — Con trỏ đọc

**Analogy**: Offset giống **bookmark** trong sách. Mỗi record trong partition có một offset (số thứ tự) tăng dần, bắt đầu từ 0.

```
Partition 0:
  Offset:  0    1    2    3    4    5    6    7
  Data:  [rec] [rec] [rec] [rec] [rec] [rec] [rec] [rec]
                              ↑
                    Consumer đang ở offset 3
                    = đã đọc 0,1,2 — sẽ đọc 3 tiếp theo

Consumer commit offset = "tôi đã xử lý xong đến offset X"
```

**Offset management**:
- **Auto commit**: Consumer tự động commit offset theo interval (mặc định 5s) — đơn giản nhưng có thể mất/duplicate messages
- **Manual commit**: Consumer tự quyết định khi nào commit — chính xác hơn nhưng phức tạp hơn
- Offset được lưu trong internal topic `__consumer_offsets`

#### Broker — Kafka server

Mỗi broker là 1 Kafka server process. Cluster gồm nhiều brokers.

```
Broker responsibilities:
├── Nhận records từ producers, ghi vào partition log
├── Phục vụ consumers đọc records
├── Replicate partitions sang các brokers khác
├── Tham gia leader election cho partitions
└── Report metadata cho controller
```

Một broker có thể là **leader** cho một số partitions và **follower** cho các partitions khác. Mục tiêu: **phân tải đều** leaders across brokers.

#### Segment — Đơn vị storage trên disk

Mỗi partition không phải 1 file duy nhất mà chia thành nhiều **segments**:

```
Partition 0 trên disk:
  /kafka-logs/orders-0/
  ├── 00000000000000000000.log       ← segment 0 (offsets 0-999)
  ├── 00000000000000000000.index     ← sparse index cho segment 0
  ├── 00000000000000000000.timeindex ← time-based index
  ├── 00000000000000001000.log       ← segment 1 (offsets 1000-1999)
  ├── 00000000000000001000.index
  ├── 00000000000000001000.timeindex
  └── 00000000000000002000.log       ← active segment (đang ghi)
      
File name = base offset của segment
```

**Tại sao chia segments?**
- **Deletion hiệu quả**: xóa cả file thay vì xóa từng record
- **Compaction hiệu quả**: compact từng segment độc lập
- **Seek nhanh**: binary search trên index file để tìm offset

### 4.3 Tại sao Kafka nhanh? — 4 yếu tố chính

#### 1. Sequential I/O (Append-only writes)

```
Random I/O (Traditional DB):
  Disk head di chuyển liên tục giữa các vị trí
  ┌───────────────────────┐
  │  ↗  ↙  ↗    ↙  ↗     │  ← seek time ~10ms mỗi lần
  └───────────────────────┘
  Throughput: ~100-200 IOPS trên HDD

Sequential I/O (Kafka):
  Ghi liên tục tại cuối file
  ┌───────────────────────┐
  │  → → → → → → → →     │  ← không seek, ghi liên tục
  └───────────────────────┘
  Throughput: 100-600 MB/s trên HDD!
```

**Benchmark thực tế**: Sequential writes trên HDD nhanh hơn Random writes **6000x**. Sequential writes trên HDD thậm chí có thể **nhanh hơn random writes trên SSD**.

Kafka chỉ **append** vào cuối log file — không update, không delete records — nên tận dụng 100% sequential I/O.

#### 2. Page Cache (OS-level caching)

Kafka **không tự quản lý cache** trong JVM heap. Thay vào đó, nó dựa hoàn toàn vào **OS page cache**:

```
Traditional approach (tự cache trong application):
  Producer → App Memory (heap) → Flush to Disk → App Memory (heap) → Consumer
                ↑                                        ↑
           GC pressure!                          Double buffering!

Kafka approach (OS page cache):
  Producer → OS Page Cache → Disk (async)
                    ↓
                Consumer đọc trực tiếp từ page cache
                (nếu data còn "hot" → không chạm disk!)
```

**Tại sao page cache tốt hơn JVM heap?**
- Không bị GC (Garbage Collection) — no stop-the-world pauses
- OS tự quản lý eviction policy hiệu quả
- Surviving process restart — page cache vẫn còn ngay cả khi Kafka restart
- Tận dụng toàn bộ free RAM của machine

#### 3. Zero-Copy (sendfile system call)

```
KHÔNG có zero-copy (truyền thống):
  Disk → Kernel Buffer → User Buffer (App) → Socket Buffer → NIC
         copy 1           copy 2              copy 3
  = 4 context switches + 3 data copies

CÓ zero-copy (sendfile):
  Disk → Kernel Buffer ─────────────────────→ NIC
                    (direct transfer, no user space!)
  = 2 context switches + 0 CPU copies
```

Kafka dùng `sendfile()` system call (Java `FileChannel.transferTo()`) khi consumer đọc data → data đi thẳng từ disk/page cache đến network socket mà **không qua JVM**.

**Impact**: Giảm CPU usage ~60-70% khi serving consumers.

**Caveat:** Zero-copy không phải lúc nào cũng áp dụng trọn vẹn. TLS/SSL thường buộc data đi qua encryption layer nên giảm hoặc mất lợi ích zero-copy; compression, message format conversion, interceptors hoặc proxy cũng có thể làm data path quay lại user space. Vì vậy benchmark producer/consumer với TLS giống production trước khi dùng số throughput lý thuyết.

#### 4. Batching + Compression

```
Không batching:
  [msg1] → network → [msg2] → network → [msg3] → network
  3 network round trips
  3 disk writes
  
Batching:
  [msg1 + msg2 + msg3] → network (1 trip) → disk (1 write)
  + compression toàn batch: [gzip([msg1+msg2+msg3])]
  
  Compression ratios thực tế:
  ├── JSON data:  gzip ~75-85% reduction
  ├── JSON data:  snappy ~50-60% reduction  
  ├── JSON data:  lz4 ~55-65% reduction
  └── JSON data:  zstd ~75-90% reduction (best ratio)
```

### 4.4 Retention Policies — Kafka giữ data bao lâu?

Không giống queue (xóa sau khi consume), Kafka giữ data theo **policy**:

#### Time-based retention (mặc định)
```properties
# Giữ data 7 ngày (mặc định)
log.retention.hours=168

# Hoặc chính xác hơn
log.retention.ms=604800000
```

#### Size-based retention
```properties
# Giữ tối đa 50GB per partition
log.retention.bytes=53687091200
```

#### Log compaction
```properties
# Giữ record MỚI NHẤT cho mỗi key
log.cleanup.policy=compact
```

```
Log Compaction — giữ latest value per key:

TRƯỚC compaction:
  Key=A, Value=1  |  Key=B, Value=2  |  Key=A, Value=3  |  Key=B, Value=4  |  Key=A, Value=5

SAU compaction:
  Key=B, Value=4  |  Key=A, Value=5
  
  → Chỉ giữ record mới nhất cho mỗi key
  → Giống "snapshot" của state hiện tại
  → Use case: CDC (Change Data Capture), KTable materialization
```

Compaction là background process, **không immediate**. Trong một khoảng thời gian, consumer vẫn có thể đọc nhiều versions của cùng key cho đến khi cleaner chạy và segment đủ điều kiện compact. Xóa key trong compacted topic dùng tombstone record (`key` có `value=null`); tombstone cũng được giữ ít nhất theo `delete.retention.ms` để downstream có thời gian quan sát delete trước khi tombstone bị dọn.

| Policy | Use Case | Ưu điểm | Nhược điểm |
|--------|----------|---------|------------|
| Time-based | Event logs, audit trails | Predictable, dễ capacity plan | Có thể giữ data không cần thiết |
| Size-based | High-volume với disk giới hạn | Kiểm soát disk usage | Có thể mất data cũ khi volume spike |
| Compact | CDC, state snapshots, config | Giữ latest state mãi mãi | CPU-intensive, phức tạp hơn |
| Delete + Compact | Hybrid approach | Linh hoạt | Khó reason about |

---

## 5. Trade-off Analysis

### Kafka vs RabbitMQ vs NATS — Architectural Level

| Tiêu chí | Kafka | RabbitMQ | NATS Core |
|----------|-------|----------|-----------|
| **Mô hình** | Distributed commit log | Smart broker, dumb consumer | Simple pub/sub |
| **Data ownership** | Log giữ data, consumer chỉ đọc | Queue sở hữu, msg bị xóa sau consume | Không persistence (fire-and-forget) |
| **Replay** | ✅ Có — consumer seek đến bất kỳ offset | ❌ Không — đã consume là mất | ❌ Không (JetStream có) |
| **Ordering** | Per-partition ordering | Per-queue ordering | Per-publisher/per-connection subject order trong điều kiện ổn định; không có global ordering |
| **Throughput** | Rất cao (~1M+ msg/s/broker) | Trung bình (~50k msg/s) | Cao (~10M+ msg/s) |
| **Latency** | ~5-15ms (p99) | ~1-5ms | ~0.1-0.5ms |
| **Consumer coupling** | Loose — consumers độc lập | Tight — competing consumers | Loose |
| **Storage** | Disk (sequential log) | Memory + disk | Memory |
| **Complexity** | Cao | Trung bình | Thấp |

### Partition Count Trade-off

| Nhiều partitions | Ít partitions |
|-----------------|---------------|
| ✅ Throughput cao hơn (parallel) | ✅ Ít overhead metadata |
| ✅ Nhiều consumers hơn | ✅ Đảm bảo ordering dễ hơn |
| ❌ Nhiều file descriptors | ✅ Ít tài nguyên |
| ❌ Leader election chậm hơn | ❌ Throughput bị giới hạn |
| ❌ End-to-end latency cao hơn | ❌ Max consumers bị giới hạn |

**Rule of thumb**: Bắt đầu với `max(expected_throughput / partition_throughput, num_consumers)`. Typical: 3-12 partitions cho hầu hết use cases, 30-50 cho high-throughput topics.

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Partition key design là critical**: Dùng entity ID (order_id, user_id) làm key để đảm bảo ordering per entity. Tránh dùng key có cardinality quá thấp (ví dụ: country code → hot partition).

2. **Đừng tạo quá nhiều partitions**: Mỗi partition = overhead (memory, file handles, replication traffic). 50 partitions per topic là reasonable upper bound cho hầu hết cases.

3. **Retention phù hợp**: Không giữ data mãi mãi "just in case". Tính toán disk cost. 7 ngày là reasonable default, 30 ngày nếu cần replay.

4. **Topic naming convention**: Chọn 1 convention và tuân thủ. `<domain>.<entity>.<event>` (ví dụ: `order.payment.completed`).

### Common Pitfalls

1. **❌ Nghĩ Kafka là message queue**: Kafka KHÔNG xóa message sau khi consume. Nếu bạn cần queue semantics (1 message → 1 consumer xử lý → xóa), RabbitMQ phù hợp hơn.

2. **❌ Tăng partition count khi cần giảm**: Kafka cho phép tăng partitions nhưng **KHÔNG cho phép giảm**. Key-based routing sẽ bị BREAK khi tăng partitions vì hash thay đổi.

3. **❌ Single partition cho toàn bộ topic**: Throughput bị bottleneck tại 1 consumer. Trừ khi bạn cần strict global ordering.

4. **❌ Dùng Kafka cho request-reply**: Kafka latency ~5-15ms, overhead cao. Dùng gRPC/HTTP/NATS cho request-reply.

5. **❌ Quên configure retention**: Mặc định 7 ngày. Production với high volume → disk đầy nếu không plan.

---

## 7. Performance Considerations

### Metrics quan trọng

| Metric | Ý nghĩa | Alert threshold |
|--------|---------|----------------|
| `BytesInPerSec` | Data rate vào broker | Gần network bandwidth |
| `BytesOutPerSec` | Data rate ra broker | Gần network bandwidth |
| `MessagesInPerSec` | Message rate | Dựa trên capacity plan |
| `UnderReplicatedPartitions` | Partitions chưa đủ replicas | > 0 |
| `ActiveControllerCount` | Số controller active | != 1 |
| `RequestHandlerAvgIdlePercent` | CPU idle của request handlers | < 30% |

### Benchmark Numbers Thực Tế

```
Single broker (modern hardware, SSD):
├── Producer throughput:  200-500 MB/s (batched, compressed)
├── Consumer throughput:  300-600 MB/s (zero-copy)
├── Messages/sec:         500K-1M (small messages ~100 bytes)
└── Latency p99:          5-15ms (acks=1), 15-30ms (acks=all)

3-broker cluster (replication factor 3):
├── Aggregate throughput:  500-1500 MB/s
├── Messages/sec:          1-3M
└── Partitions:            tối đa ~4000 per broker (practical)
```

### Config Impact Lớn Nhất

```properties
# Producer side
batch.size=16384              # Batch size (bytes), tăng → throughput tăng
linger.ms=5                   # Wait time to fill batch, tăng → throughput tăng, latency tăng 
compression.type=lz4          # lz4 = fast compress, zstd = best ratio
acks=all                      # Durability vs latency trade-off

# Broker side  
num.partitions=3              # Default partitions per topic
log.retention.hours=168       # 7 days default
log.segment.bytes=1073741824  # 1GB per segment file
```

---

## 8. Hands-on Lab

### 8.1 Setup Kafka Cluster với Docker Compose

Tạo file `docker-compose.yml`:

```yaml
version: '3.8'

services:
  kafka-1:
    image: bitnami/kafka:3.7
    container_name: kafka-1
    ports:
      - "9092:9092"
    environment:
      # KRaft mode (không cần ZooKeeper)
      - KAFKA_CFG_NODE_ID=1
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9094,CONTROLLER://:9093,EXTERNAL://:9092
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka-1:9094,EXTERNAL://localhost:9092
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_INTER_BROKER_LISTENER_NAME=PLAINTEXT
      - KAFKA_KRAFT_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
      # Performance configs
      - KAFKA_CFG_NUM_PARTITIONS=3
      - KAFKA_CFG_DEFAULT_REPLICATION_FACTOR=3
      - KAFKA_CFG_LOG_RETENTION_HOURS=168
    volumes:
      - kafka1-data:/bitnami/kafka

  kafka-2:
    image: bitnami/kafka:3.7
    container_name: kafka-2
    ports:
      - "9093:9092"
    environment:
      - KAFKA_CFG_NODE_ID=2
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9094,CONTROLLER://:9093,EXTERNAL://:9092
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka-2:9094,EXTERNAL://localhost:9093
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_INTER_BROKER_LISTENER_NAME=PLAINTEXT
      - KAFKA_KRAFT_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
      - KAFKA_CFG_NUM_PARTITIONS=3
      - KAFKA_CFG_DEFAULT_REPLICATION_FACTOR=3
    volumes:
      - kafka2-data:/bitnami/kafka

  kafka-3:
    image: bitnami/kafka:3.7
    container_name: kafka-3
    ports:
      - "9094:9092"
    environment:
      - KAFKA_CFG_NODE_ID=3
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9094,CONTROLLER://:9093,EXTERNAL://:9092
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka-3:9094,EXTERNAL://localhost:9094
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_INTER_BROKER_LISTENER_NAME=PLAINTEXT
      - KAFKA_KRAFT_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk
      - KAFKA_CFG_NUM_PARTITIONS=3
      - KAFKA_CFG_DEFAULT_REPLICATION_FACTOR=3
    volumes:
      - kafka3-data:/bitnami/kafka

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    ports:
      - "8080:8080"
    environment:
      - KAFKA_CLUSTERS_0_NAME=local
      - KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=kafka-1:9094,kafka-2:9094,kafka-3:9094
    depends_on:
      - kafka-1
      - kafka-2
      - kafka-3

volumes:
  kafka1-data:
  kafka2-data:
  kafka3-data:
```

```bash
# Start cluster
docker compose up -d

# Verify cluster — đợi ~30s cho cluster ổn định
docker exec kafka-1 kafka-broker-api-versions.sh --bootstrap-server localhost:9094
docker exec kafka-1 kafka-metadata-quorum.sh --bootstrap-server localhost:9094 describe --status

# Tạo topic
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic orders \
  --partitions 3 \
  --replication-factor 3

# Describe topic — xem partition layout
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --describe --topic orders
```

### 8.2 First Producer/Consumer bằng CLI

```bash
# Terminal 1: Producer
docker exec -it kafka-1 kafka-console-producer.sh \
  --bootstrap-server localhost:9094 \
  --topic orders \
  --property "key.separator=:" \
  --property "parse.key=true"

# Gõ messages (format key:value):
# order-001:{"type":"created","amount":100}
# order-002:{"type":"created","amount":200}
# order-001:{"type":"paid","amount":100}

# Terminal 2: Consumer (from beginning)
docker exec -it kafka-1 kafka-console-consumer.sh \
  --bootstrap-server localhost:9094 \
  --topic orders \
  --from-beginning \
  --property "print.key=true" \
  --property "print.partition=true" \
  --property "print.offset=true"
```

### 8.3 Go Producer/Consumer Application

Tạo project Go:

```bash
mkdir -p day-10-lab && cd day-10-lab
go mod init day10-kafka-fundamentals
go get github.com/segmentio/kafka-go
```

**Producer** (`producer.go`):

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Type      string    `json:"type"`
	Amount    float64   `json:"amount"`
	Timestamp time.Time `json:"timestamp"`
}

func main() {
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "orders",
		Balancer:     &kafka.Hash{}, // hash key → cùng key luôn vào cùng partition
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		RequiredAcks: kafka.RequireAll, // acks=all cho durability
	}
	defer writer.Close()

	orders := []OrderEvent{
		{OrderID: "order-001", Type: "created", Amount: 150.00},
		{OrderID: "order-002", Type: "created", Amount: 299.99},
		{OrderID: "order-001", Type: "paid", Amount: 150.00},
		{OrderID: "order-003", Type: "created", Amount: 89.50},
		{OrderID: "order-002", Type: "paid", Amount: 299.99},
		{OrderID: "order-001", Type: "shipped", Amount: 150.00},
	}

	for _, order := range orders {
		order.Timestamp = time.Now()
		value, _ := json.Marshal(order)

		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(order.OrderID), // cùng order → cùng partition → ordering!
			Value: value,
		})
		if err != nil {
			log.Printf("Failed to write message: %v", err)
			continue
		}

		fmt.Printf("Produced: key=%s partition=auto type=%s\n", order.OrderID, order.Type)
		time.Sleep(500 * time.Millisecond)
	}

	fmt.Println("All messages produced!")
}
```

Chạy producer:

```bash
go run producer.go
```

**Consumer** (`consumer.go`):

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

	"github.com/segmentio/kafka-go"
)

type OrderEvent struct {
	OrderID   string  `json:"order_id"`
	Type      string  `json:"type"`
	Amount    float64 `json:"amount"`
	Timestamp string  `json:"timestamp"`
}

func main() {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:9092"},
		Topic:    "orders",
		GroupID:  "order-processor", // consumer group
		MaxBytes: 10e6,             // 10MB max per fetch
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		fmt.Println("\nShutting down consumer...")
		cancel()
	}()

	fmt.Println("Consumer started. Waiting for messages...")

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				break // context cancelled — graceful shutdown
			}
			log.Printf("Error fetching message: %v", err)
			continue
		}

		var event OrderEvent
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			log.Printf("Failed to unmarshal: %v", err)
			continue
		}

		fmt.Printf("[Partition %d | Offset %d] Order: %s, Type: %s, Amount: $%.2f\n",
			msg.Partition, msg.Offset, event.OrderID, event.Type, event.Amount)

		// Commit SAU KHI xử lý thành công — at-least-once semantics
		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("Failed to commit: %v", err)
		}
	}

	fmt.Println("Consumer stopped.")
}
```

Chạy consumer:

```bash
# Terminal 1
go run consumer.go

# Terminal 2: chạy lại producer để thấy consumer nhận messages
go run producer.go

# Optional: mở thêm consumer thứ hai cùng GroupID để quan sát queue-like consumer group assignment
go run consumer.go
```

### 8.4 Lab: Quan sát Partition Assignment và Ordering

```go
// partition_demo.go — demo per-key ordering
package main

import (
	"context"
	"fmt"
	"log"

	"github.com/segmentio/kafka-go"
)

func main() {
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "ordering-demo",
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
	}
	defer writer.Close()

	// Gửi events cho 3 orders — quan sát partition assignment
	events := []struct {
		key   string
		value string
	}{
		{"user-100", "login"},
		{"user-200", "login"},
		{"user-100", "view-product"},
		{"user-300", "login"},
		{"user-100", "add-to-cart"},
		{"user-200", "view-product"},
		{"user-100", "checkout"},
		{"user-200", "add-to-cart"},
	}

	for i, e := range events {
		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(e.key),
			Value: []byte(e.value),
		})
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("[%d] Sent key=%s value=%s\n", i, e.key, e.value)
	}

	// Đọc lại và kiểm tra ordering
	fmt.Println("\n--- Reading back (per partition order) ---")
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{"localhost:9092"},
		Topic:   "ordering-demo",
		GroupID: "ordering-checker",
	})
	defer reader.Close()

	for i := 0; i < len(events); i++ {
		msg, err := reader.ReadMessage(context.Background())
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("[Partition %d | Offset %d] key=%s value=%s\n",
			msg.Partition, msg.Offset, string(msg.Key), string(msg.Value))
	}
}
```

Chạy và quan sát:
```bash
# Tạo topic trước
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic ordering-demo --partitions 3 --replication-factor 3

go run partition_demo.go
```

**Kết quả mong đợi**: Tất cả events của `user-100` nằm trong cùng partition → đọc ra đúng thứ tự `login → view-product → add-to-cart → checkout`.

### 8.5 Lab: Replay Messages — Consumer đọc lại từ đầu

```bash
# Consumer group mới đọc từ đầu — chứng minh messages KHÔNG bị xóa
docker exec -it kafka-1 kafka-console-consumer.sh \
  --bootstrap-server localhost:9094 \
  --topic orders \
  --from-beginning \
  --group new-analytics-group

# Một consumer group khác cũng đọc được TẤT CẢ messages
docker exec -it kafka-1 kafka-console-consumer.sh \
  --bootstrap-server localhost:9094 \
  --topic orders \
  --from-beginning \
  --group audit-group
```

### 8.6 Kafka UI

Truy cập `http://localhost:8080` để xem:
- Cluster overview: brokers, controller
- Topic details: partitions, replication factor, configs
- Messages: browse messages theo partition, offset
- Consumer groups: lag, offsets

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Tại sao Kafka KHÔNG xóa messages sau khi consumer đọc?** Thiết kế này mang lại lợi ích gì và tạo ra thách thức gì? (Hint: nghĩ về multi-consumer, replay, disk management)

2. **Nếu bạn có topic "payments" với 6 partitions và consumer group có 8 consumers, điều gì xảy ra?** Nếu chỉ có 4 consumers thì sao? (Hint: partition assignment)

3. **Giải thích tại sao sequential I/O trên HDD có thể nhanh hơn random I/O trên SSD?** Kafka exploit điều này như thế nào? (Hint: disk seek time, OS read-ahead)

4. **Bạn cần đảm bảo tất cả events của cùng 1 user được xử lý theo thứ tự. Bạn sẽ design partition key như thế nào?** Nếu 1 user cực kỳ active tạo ra hot partition thì xử lý thế nào? (Hint: compound key)

5. **So sánh log compaction với time-based retention. Khi nào bạn chọn compaction?** Cho ví dụ cụ thể. (Hint: CDC, state materialization)

6. **Zero-copy transfer giúp Kafka như thế nào? Trong scenario nào zero-copy KHÔNG giúp được?** (Hint: encryption, compression at consumer)

7. **Một team đang dùng RabbitMQ cho event sourcing. Bạn sẽ nói gì với họ?** (Hint: replay, retention, consumer independence)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Design Documentation](https://kafka.apache.org/documentation/#design) — **MUST READ**, đặc biệt mục "Don't fear the filesystem!"
- [Kafka Configuration Reference](https://kafka.apache.org/documentation/#configuration)
- [KRaft (KIP-500)](https://cwiki.apache.org/confluence/display/KAFKA/KIP-500%3A+Replace+ZooKeeper+with+a+Self-Managed+Metadata+Quorum)

### Blog Posts Chất Lượng
- [The Log: What every software engineer should know about real-time data's unifying abstraction](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying) — Jay Kreps (creator Kafka)
- [How Kafka achieves high throughput](https://blog.bytebytego.com/p/why-is-kafka-fast) — ByteByteGo
- [Kafka vs RabbitMQ: Architecture, Performance, Use Cases](https://www.confluent.io/kafka-vs-rabbitmq/) — Confluent

### Videos
- [Kafka Internals: How Kafka Works Under the Hood](https://www.youtube.com/watch?v=d2l3_f4HKsM) — Confluent
- [The Log Abstraction](https://www.youtube.com/watch?v=I32hmY4diFY) — Martin Kleppmann
