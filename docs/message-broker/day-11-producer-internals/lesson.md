# Day 11: Kafka Producer Internals — Batching, Compression, Acks, Idempotent Producer

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** kiến trúc bên trong của Kafka Producer — từ `send()` đến lúc record đến broker
2. **Nắm vững** batching mechanism — `batch.size`, `linger.ms`, buffer memory và cách chúng ảnh hưởng throughput/latency
3. **Phân tích được** trade-off của `acks` (0, 1, all) — durability vs performance
4. **Hiểu** idempotent producer — tại sao cần, cách hoạt động, giới hạn
5. **Thực hành** tuning producer với các workload khác nhau (low-latency vs high-throughput)

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10 (Kafka fundamentals: topic, partition, offset, broker, replication)
- Hiểu partition key và ordering guarantee từ Day 10
- Hiểu sequential I/O, page cache, zero-copy concepts
- Docker Compose cluster từ Day 10 đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Producer architecture: RecordAccumulator, Sender thread, batching pipeline
- `batch.size`, `linger.ms`, `buffer.memory` — tuning cho throughput vs latency
- `acks` (0, 1, all) — trade-off analysis chi tiết
- Compression types (none, gzip, snappy, lz4, zstd) — khi nào dùng gì
- Partitioner strategies: round-robin, sticky, key-based (murmur2 hash)
- Hands-on: benchmark throughput với các config khác nhau

### 🟡 Should Learn (nếu còn thời gian)
- Idempotent producer (`enable.idempotence=true`) — dedup retry nội bộ của producer trong phạm vi partition/session, không phải exactly-once end-to-end
- `max.in.flight.requests.per.connection` và ordering guarantee
- Custom partitioner implementation

### 🟢 Optional Deep Dive
- Producer interceptors
- Kafka producer source code walkthrough (Java)
- Transactional producer (sẽ cover sâu hơn ở Day 15)

---

## 4. Lý thuyết (Theory)

### 4.1 Producer Architecture — Bên trong send() có gì?

#### WHY — Tại sao cần hiểu producer internals?

Khác với RabbitMQ (gửi 1 message → broker xác nhận → xong), Kafka producer có architecture phức tạp hơn nhiều bên trong. Hiểu internals giúp bạn:
- **Tuning đúng cách** thay vì trial-and-error
- **Debug production issues** (ví dụ: tại sao latency spike? tại sao message bị duplicate?)
- **Chọn config phù hợp** cho từng workload

#### HOW — Producer Pipeline

```
Application Thread                    Sender Thread (background)
      │                                       │
      ▼                                       │
  send(record)                                │
      │                                       │
      ▼                                       │
  Serializer                                  │
  (key + value → bytes)                       │
      │                                       │
      ▼                                       │
  Partitioner                                 │
  (chọn partition)                            │
      │                                       │
      ▼                                       │
  ┌─────────────────────┐                     │
  │  RecordAccumulator  │                     │
  │  ┌───────────────┐  │                     │
  │  │ Partition 0   │  │    drain batches    │
  │  │ [batch1]      │──┼────────────────────►│
  │  │ [batch2]      │  │                     │
  │  ├───────────────┤  │                     ▼
  │  │ Partition 1   │  │              NetworkClient
  │  │ [batch1]      │──┼─────────────►  (send to broker)
  │  ├───────────────┤  │                     │
  │  │ Partition 2   │  │                     ▼
  │  │ [batch1]      │──┼──────────►   Broker Response
  │  └───────────────┘  │              (acks/errors)
  │                     │                     │
  │  buffer.memory      │                     ▼
  │  (default 32MB)     │              Callback/Future
  └─────────────────────┘              (notify application)
```

**Luồng chi tiết:**

1. **Application thread** gọi `send(record)` — non-blocking, return `Future`
2. **Serializer** chuyển key và value thành bytes
3. **Partitioner** quyết định record đi vào partition nào
4. **RecordAccumulator** buffer record vào batch tương ứng với partition
5. **Sender thread** (background, riêng biệt) kiểm tra batches:
   - Batch đầy (`batch.size`) → gửi ngay
   - Hoặc đợi timeout (`linger.ms`) → gửi batch chưa đầy
6. **NetworkClient** gửi batch đến broker leader của partition đó
7. **Broker** xử lý, replicate (nếu `acks=all`), trả response
8. **Callback** được gọi — success hoặc error

**Insight quan trọng**: Application thread và Sender thread hoạt động **độc lập**. `send()` chỉ bỏ record vào buffer → return ngay. Actual network I/O xảy ra ở background thread.

### 4.2 Batching — Trái tim của Producer Performance

#### WHY — Batch thay vì gửi từng message

```
Không batching (1 message = 1 request):
  Application: send(m1)  send(m2)  send(m3)  send(m4)
  Network:     [m1]───►  [m2]───►  [m3]───►  [m4]───►
  Broker:      write1    write2    write3    write4
  
  = 4 network round trips + 4 disk writes
  Throughput: ~1000-5000 msg/s (network latency bound)

Batching (nhiều messages = 1 request):
  Application: send(m1) send(m2) send(m3) send(m4)
                 ↓        ↓       ↓        ↓
  Buffer:      [m1, m2, m3, m4] ← accumulate
  Network:     [batch]──────────────────────►
  Broker:      write_batch (1 sequential write)
  
  = 1 network round trip + 1 disk write
  Throughput: ~100,000-500,000 msg/s
```

#### `batch.size` — Kích thước batch tối đa (bytes)

```properties
batch.size=16384   # 16KB (mặc định)
```

- Khi buffer cho 1 partition đạt `batch.size` bytes → Sender gửi batch ngay
- **KHÔNG phải** số messages, mà là **bytes**
- Tăng `batch.size` → batch lớn hơn → ít requests hơn → throughput cao hơn
- Nhưng: tốn memory hơn, latency có thể tăng (đợi batch đầy)

```
batch.size = 16KB:
  100-byte messages → ~160 messages/batch
  1KB messages → ~16 messages/batch
  
batch.size = 64KB:
  100-byte messages → ~640 messages/batch
  → Throughput tăng ~4x nếu có đủ messages
```

#### `linger.ms` — Đợi bao lâu trước khi gửi batch chưa đầy

```properties
linger.ms=0    # Mặc định (Kafka < 4.0): gửi ngay khi có message
linger.ms=5    # Mặc định (Kafka >= 4.0): đợi 5ms
```

```
linger.ms = 0 (không đợi):
  t=0ms:  send(m1) → batch=[m1] → gửi ngay! (batch chỉ có 1 msg)
  t=1ms:  send(m2) → batch=[m2] → gửi ngay!
  → Latency thấp nhất, nhưng batch luôn nhỏ
  
linger.ms = 5 (đợi 5ms):
  t=0ms:  send(m1) → batch=[m1]           ← chờ...
  t=1ms:  send(m2) → batch=[m1,m2]        ← chờ...
  t=3ms:  send(m3) → batch=[m1,m2,m3]     ← chờ...
  t=5ms:  timeout! → gửi batch=[m1,m2,m3] ← batch 3 msgs!
  → +5ms latency, nhưng throughput tốt hơn nhiều

linger.ms = 50 (đợi lâu hơn):
  → Batch lớn hơn, throughput cao nhất
  → Nhưng thêm 50ms latency cho MỌI message
```

**Rule of thumb:**
- `linger.ms=0`: low-latency critical (trading, real-time alerts)
- `linger.ms=5-20`: balanced (hầu hết use cases)
- `linger.ms=50-100`: high-throughput batch processing (log aggregation, analytics)

#### `buffer.memory` — Tổng memory cho tất cả batches

```properties
buffer.memory=33554432   # 32MB (mặc định)
```

- Tổng memory mà producer dùng để buffer **tất cả partitions**
- Khi buffer đầy → `send()` **BLOCK** (chờ Sender giải phóng space)
- Block timeout = `max.block.ms` (mặc định 60s) → nếu vẫn đầy → throw exception

```
buffer.memory = 32MB, ghi vào 10 partitions:
  Mỗi partition có ~3.2MB buffer space
  Nếu producer ghi nhanh hơn network gửi → buffer đầy → backpressure!
  
  Giải pháp:
  1. Tăng buffer.memory (64MB, 128MB)
  2. Tăng batch.size + linger.ms (batch lớn hơn, gửi hiệu quả hơn)
  3. Tăng throughput phía broker/network
```

#### Batching Interaction Diagram

```
                    batch.size = 16KB
                    linger.ms = 10ms
                        │
  send(r1) ─────► ┌────▼────────────────┐
  send(r2) ─────► │  Batch buffer       │
  send(r3) ─────► │  [r1][r2][r3]       │
                  │  current: 3KB       │
                  │                     │
                  │  Trigger gửi khi:   │
                  │  1. size >= 16KB    │─── batch đầy → gửi NGAY
                  │  2. time >= 10ms    │─── timeout → gửi batch hiện tại
                  │  3. flush() called  │─── explicit flush
                  └─────────────────────┘
```

### 4.3 Compression — Nhỏ hơn = Nhanh hơn

#### WHY — Compress ở producer

```
Không compression:
  Producer ──[100KB raw]──► Network ──[100KB]──► Broker ──[100KB]──► Disk
  
Có compression (zstd, ~80% ratio):
  Producer ──[20KB compressed]──► Network ──[20KB]──► Broker ──[20KB]──► Disk
                                                                         ↓
  Consumer ◄──[20KB compressed]──────────────────────────────────────── Disk
  Consumer decompress → 100KB

  Network bandwidth giảm 80%!
  Disk usage giảm 80%!
  CPU trade-off: producer compress + consumer decompress
```

**Quan trọng**: Compression xảy ra ở **batch level**, không phải per-message. Batch càng lớn → compression ratio càng tốt.

#### Compression Types So Sánh

| Algorithm | Compression Ratio | Compress Speed | Decompress Speed | CPU Usage | Best For |
|-----------|------------------|----------------|-------------------|-----------|----------|
| **none** | 1:1 | N/A | N/A | Lowest | CPU-constrained |
| **gzip** | Cao (~85%) | Chậm | Trung bình | Cao | Bandwidth-constrained, batch jobs |
| **snappy** | Trung bình (~60%) | Rất nhanh | Rất nhanh | Thấp | Balanced (deprecated dần) |
| **lz4** | Trung bình (~65%) | Rất nhanh | Rất nhanh | Thấp | **Recommended default** |
| **zstd** | Rất cao (~90%) | Nhanh | Nhanh | Trung bình | **Best overall** (Kafka >= 2.1) |

**Recommendation**: Dùng **lz4** cho low-latency workloads, **zstd** cho bandwidth/storage optimization.

```properties
compression.type=lz4    # Recommended cho hầu hết cases
# hoặc
compression.type=zstd   # Best ratio, chấp nhận thêm chút CPU
```

### 4.4 Acks — Durability vs Latency Trade-off

#### WHY — Producer cần "xác nhận" từ broker

Khi producer gửi batch, nó cần biết: "Broker đã nhận được chưa?" Mức độ "nhận được" = `acks` config.

#### `acks=0` — Fire and Forget

```
Producer ──[batch]──► Broker (leader)
   ↓
 return (không đợi)

Timeline:
  t=0ms:  send batch
  t=0ms:  return success (không biết broker nhận chưa!)
  
  Nếu broker crash TRƯỚC khi ghi disk → DATA LOST
  Nếu network drop → DATA LOST
  Producer KHÔNG BIẾT!
```

- **Throughput**: Cao nhất (không đợi)
- **Latency**: Thấp nhất (~0ms)
- **Durability**: **KHÔNG có** — message có thể mất mà producer không biết
- **Use case**: Metrics, logs không critical, nơi mất vài message chấp nhận được

#### `acks=1` — Leader Acknowledged

```
Producer ──[batch]──► Broker (leader)
                         │
                         ▼
                      Write to log
                         │
                         ▼
Producer ◄──[ack]──── Return success
                         │
                   (background replication)
                         ├──► Follower 1
                         └──► Follower 2

Timeline:
  t=0ms:   send batch
  t=2-5ms: leader writes to page cache → ack
  t=5-50ms: followers replicate (async, KHÔNG đợi)
  
  Nếu leader crash SAU ack nhưng TRƯỚC replicate → DATA LOST
```

- **Throughput**: Cao
- **Latency**: Thấp (~2-5ms)
- **Durability**: Trung bình — mất nếu leader crash trước replication
- **Use case**: Hầu hết production use cases chấp nhận rare data loss

#### `acks=all` (hoặc `acks=-1`) — Current ISR Acknowledged

```
Producer ──[batch]──► Broker (leader)
                         │
                         ▼
                      Write to log
                         │
                         ├──► Follower 1 trong ISR: replicate + ack ✓
                         ├──► Follower 2 trong ISR: replicate + ack ✓
                         │
                         ▼ (tất cả replica đang nằm trong ISR đã ack)
Producer ◄──[ack]──── Return success

Timeline:
  t=0ms:    send batch
  t=2-5ms:  leader writes
  t=5-20ms: followers replicate
  t=15-30ms: current ISR ack → producer nhận ack
  
  Data safe nếu ít nhất một replica đã ack còn sống để được elect làm leader.
  min.insync.replicas KHÔNG quyết định producer đợi bao nhiêu ack;
  nó chỉ quyết định ISR size tối thiểu để broker được phép nhận write.
```

- **Throughput**: Thấp nhất (đợi replication)
- **Latency**: Cao nhất (~15-30ms)
- **Durability**: **Cao nhất trong các mức ack** — nhưng vẫn phụ thuộc `replication.factor`, `min.insync.replicas`, trạng thái ISR, và `unclean.leader.election.enable=false`
- **Use case**: Financial transactions, critical events, payment processing

#### Acks Decision Matrix

```
┌─────────────────────────────────────────────────┐
│           Choosing acks level                    │
│                                                  │
│  "Mất vài message OK không?"                    │
│      │                                           │
│      ├── Có → acks=0 (metrics, logs)            │
│      │                                           │
│      └── Không                                   │
│           │                                      │
│           ├── "Rare loss chấp nhận?"            │
│           │    │                                 │
│           │    ├── Có → acks=1 (default tốt)    │
│           │    │                                 │
│           │    └── Không → acks=all             │
│           │              + min.insync.replicas=2│
│           │              (financial, critical)  │
│           │                                      │
└─────────────────────────────────────────────────┘
```

**Production recommendation**: `acks=all` + `min.insync.replicas=2` + `replication.factor=3`

```
Ví dụ: replication.factor=3, min.insync.replicas=2, acks=all
  
  3 brokers: Leader, Follower1, Follower2
  
  Scenario 1: Tất cả healthy, ISR = [Leader, F1, F2]
    Leader ghi → F1 ack → F2 ack → tất cả current ISR ack → ack producer ✓
    min.insync=2 chỉ là ngưỡng cho phép write, không phải số ack cần đợi.
    
  Scenario 2: F2 chết
    ISR = [Leader, F1] → vẫn đủ min.insync=2
    Leader ghi → F1 ack → current ISR ack đủ → hoạt động bình thường ✓
    
  Scenario 3: F1 VÀ F2 chết
    ISR = [Leader] → chỉ 1 ISR < min.insync=2
    → Producer nhận ERROR: NotEnoughReplicasException
    → Data KHÔNG bị mất, nhưng producer không ghi được
    → Trade-off: availability giảm để đảm bảo durability
```

### 4.5 Partitioner Strategies — Record đi vào partition nào?

#### Default Behavior

```
Partitioner logic:
  if key != null:
    partition = murmur2(key) % num_partitions    ← deterministic!
  else:
    partition = sticky_partition()                ← batch-aware round-robin
```

#### Strategy Comparison

**1. Key-based (murmur2 hash) — Mặc định khi có key**

```
murmur2("order-001") % 3 = 1 → Partition 1
murmur2("order-002") % 3 = 0 → Partition 0  
murmur2("order-001") % 3 = 1 → Partition 1  (LUÔN cùng partition!)

✅ Ordering guarantee per key
❌ Hot partition nếu key skewed (80% traffic có cùng key prefix)
```

**2. Round-Robin — Phân bổ đều (Kafka cũ, khi key=null)**

```
msg1 → Partition 0
msg2 → Partition 1  
msg3 → Partition 2
msg4 → Partition 0
...

✅ Phân bổ đều
❌ Batch nhỏ (mỗi message có thể vào partition khác → batch bị split)
❌ Không ordering
```

**3. Sticky Partitioner — Mặc định khi key=null (Kafka >= 2.4)**

```
Batch 1: msg1, msg2, msg3 → tất cả vào Partition 0 (stick!)
Batch 2: msg4, msg5, msg6 → tất cả vào Partition 1 (switch khi batch đầy)
Batch 3: msg7, msg8, msg9 → tất cả vào Partition 2

✅ Batch lớn hơn → throughput tốt hơn (~50% improvement)
✅ Phân bổ đều qua thời gian
❌ Không ordering (nhưng key=null thì không cần ordering)
```

**4. Custom Partitioner**

```go
// Ví dụ: route theo region
type RegionPartitioner struct{}

func (p *RegionPartitioner) Balance(msg kafka.Message, partitions ...int) int {
    key := string(msg.Key)
    switch {
    case strings.HasPrefix(key, "us-"):
        return partitions[0]
    case strings.HasPrefix(key, "eu-"):
        return partitions[1]
    case strings.HasPrefix(key, "ap-"):
        return partitions[2]
    default:
        return partitions[0]
    }
}
```

### 4.6 Idempotent Producer — Exactly-Once cho Single Partition

#### WHY — Duplicate Problem

```
Scenario KHÔNG có idempotent producer:

  Producer ──[batch]──► Broker (leader)
                           │
                           ▼
                        Write OK!
                           │
                           ▼
  Producer ◄──[ack]──── (NHƯNG ack bị LOST do network!)
       │
       ▼
  "Hmm, không nhận ack → retry!"
       │
  Producer ──[batch]──► Broker (leader)
                           │
                           ▼
                        Write AGAIN! → DUPLICATE!
```

Đây là vấn đề classic: **at-least-once delivery** có thể tạo duplicates khi retry.

#### HOW — Idempotent Producer hoạt động

```properties
enable.idempotence=true   # Apache Kafka Java client >= 3.0: mặc định true khi config tương thích
```

Version scope: default này nói về **Apache Kafka Java producer**. Một số client khác hoặc version cũ hơn có thể không bật idempotence mặc định, nên production config nên set tường minh `enable.idempotence=true`, `acks=all`, `retries>0`, và giữ `max.in.flight.requests.per.connection<=5`.

```
Idempotent Producer assigns:
  - Producer ID (PID): unique ID per producer instance
  - Sequence Number: tăng dần per <PID, Topic, Partition>

Producer ──[PID=5, Seq=0, batch]──► Broker
                                       │
                                       ▼
                                    Write + save (PID=5, Seq=0)
                                       │
Producer ◄──[ack LOST]────────────── ack
       │
  Producer ──[PID=5, Seq=0, batch]──► Broker  (RETRY, cùng PID+Seq!)
                                       │
                                       ▼
                                    "PID=5, Seq=0 đã có!"
                                    → SKIP write (idempotent!)
                                       │
Producer ◄──[ack]──────────────────── ack (duplicate detected, not written)
```

**Giới hạn quan trọng:**
- Idempotent producer chỉ guarantee **per partition** — KHÔNG guarantee cross-partition
- `max.in.flight.requests.per.connection` tối đa = 5 (với idempotence)
- PID thay đổi khi producer restart → không protect cross-session duplicates
- Để exactly-once cross-partition → cần **transactional producer** (Day 15)

#### `max.in.flight.requests.per.connection` và Ordering

```
max.in.flight = 1 (an toàn nhất, chậm nhất):
  [batch1] ──► broker
       ◄── ack
  [batch2] ──► broker
       ◄── ack
  → Ordering LUÔN đảm bảo, nhưng throughput thấp

max.in.flight = 5 (mặc định):
  [batch1] ──►
  [batch2] ──►     (5 requests song song)
  [batch3] ──►
  [batch4] ──►
  [batch5] ──►
  
  KHÔNG có idempotence:
    batch1 FAIL → retry batch1
    batch2 SUCCESS
    → Order trên disk: batch2, batch1 → SAI THỨ TỰ!
    
  CÓ idempotence:
    Broker dùng sequence number để sắp xếp đúng
    → Order trên disk: batch1, batch2 → ĐÚNG THỨ TỰ!
```

**Takeaway**: Với `enable.idempotence=true` + `max.in.flight.requests.per.connection <= 5`, ordering được đảm bảo ngay cả khi có retry.

### 4.7 Error Handling & Retries

```properties
retries=2147483647          # Mặc định (Kafka >= 2.1): retry vô hạn
retry.backoff.ms=100        # Đợi 100ms giữa các retries
delivery.timeout.ms=120000  # Tổng time cho delivery (2 phút)
```

```
Error handling flow:

  send() → batch
           │
           ▼
     Sender gửi batch
           │
           ├── Success → callback(null, metadata)
           │
           ├── Retriable error (NetworkException, NotLeaderForPartition)
           │   → retry sau retry.backoff.ms
           │   → nếu quá delivery.timeout.ms → callback(error, null)
           │
           └── Non-retriable error (SerializationException, RecordTooLarge)
               → callback(error, null) ngay lập tức, KHÔNG retry
```

---

## 5. Trade-off Analysis

### Throughput vs Latency Tuning Profiles

| Config | Low Latency | Balanced | High Throughput |
|--------|------------|----------|-----------------|
| `acks` | 1 | all | all |
| `linger.ms` | 0 | 5-10 | 50-200 |
| `batch.size` | 16KB | 32KB | 128KB-512KB |
| `compression` | none/lz4 | lz4 | zstd |
| `buffer.memory` | 32MB | 64MB | 128MB+ |
| Throughput | ~10K msg/s | ~100K msg/s | ~500K+ msg/s |
| Latency (p99) | ~2-5ms | ~10-20ms | ~50-200ms |
| Use case | Trading, alerts | General events | Log aggregation |

### Compression Trade-off Matrix

| Scenario | Recommended | Reasoning |
|----------|-------------|-----------|
| Network bandwidth limited | zstd | Best compression ratio |
| CPU limited | none hoặc lz4 | Minimal CPU overhead |
| Mixed workload | lz4 | Good balance ratio/speed |
| Batch processing, không care latency | gzip hoặc zstd | Maximum compression |
| Message size rất nhỏ (<100 bytes) | none | Compression overhead > savings |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Luôn bật idempotent producer**: `enable.idempotence=true`. Với Apache Kafka Java client >= 3.0, idempotence mặc định bật khi config không xung đột; với client khác hoặc version cũ, hãy set tường minh. Cost gần bằng 0 nhưng protect duplicate khi retry nội bộ.

2. **Dùng `acks=all` cho production**: Kết hợp với `min.insync.replicas=2` và `replication.factor=3`. Throughput giảm ~10-20% so với `acks=1` — chấp nhận được.

3. **Batch size tuning**: Monitor metric `record-queue-time-avg`. Nếu > 100ms → batch quá lớn hoặc linger quá cao. Nếu gần 0ms → batch quá nhỏ, tăng linger.

4. **Compression mặc định**: Dùng `lz4` cho hầu hết cases. Chỉ đổi sang `zstd` nếu cần optimize storage/bandwidth.

5. **Set delivery.timeout.ms hợp lý**: Phải lớn hơn `linger.ms + request.timeout.ms`. Giá trị quá nhỏ → message dropped khi transient failure.

6. **Always handle send() errors**: Dùng callback hoặc check Future, KHÔNG fire-and-forget (trừ khi acks=0).

### Common Pitfalls

1. **❌ linger.ms=0 rồi thắc mắc throughput thấp**: Mỗi message = 1 request. Set ít nhất 5ms.

2. **❌ Tăng batch.size quá mức mà không tăng linger.ms**: Batch size lớn nhưng linger=0 → batch luôn nhỏ vì gửi ngay.

3. **❌ buffer.memory quá nhỏ khi producer nhanh hơn broker**: `send()` sẽ BLOCK. Application thread bị stuck → cascade failure.

4. **❌ Không monitor producer metrics**: Metrics quan trọng: `record-send-rate`, `record-error-rate`, `request-latency-avg`, `batch-size-avg`, `buffer-available-bytes`.

5. **❌ Key có cardinality thấp**: Ví dụ key = "type" chỉ có 3 values → 3 partitions còn lại trống → hot partition.

6. **❌ Tắt idempotence + max.in.flight > 1**: Ordering bị phá vỡ khi retry. Đây là bug ngầm rất khó phát hiện.

---

## 7. Performance Considerations

### Producer Metrics Quan Trọng

| Metric (JMX) | Ý nghĩa | Target |
|------|---------|--------|
| `record-send-rate` | Messages/sec gửi thành công | Stable, match expected |
| `record-error-rate` | Messages/sec bị error | ~0 |
| `request-latency-avg` | Avg time per request (ms) | < 50ms |
| `batch-size-avg` | Avg batch size (bytes) | Gần batch.size config |
| `record-queue-time-avg` | Time record ở buffer (ms) | < linger.ms × 2 |
| `buffer-available-bytes` | Buffer memory còn trống | > 20% tổng |
| `records-per-request-avg` | Avg records per batch | Càng cao càng tốt |
| `compression-rate-avg` | Compression ratio | < 0.5 = tốt |

### Tuning Checklist

```
1. Baseline benchmark → measure current throughput/latency
2. Tăng batch.size (32KB → 64KB → 128KB) → observe throughput
3. Tăng linger.ms (0 → 5 → 20 → 50) → observe batch fullness + latency
4. Enable compression (lz4 → zstd) → observe network + disk
5. Tăng buffer.memory nếu buffer-available-bytes thấp
6. Monitor: throughput tăng nhưng latency vẫn chấp nhận? → done!
```

---

## 8. Hands-on Lab

### 8.1 Setup (tiếp tục từ Day 10)

```bash
# Đảm bảo Kafka cluster đang chạy
docker compose ps

# Tạo topics cho lab
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic producer-bench --partitions 6 --replication-factor 3

docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic producer-acks-test --partitions 3 --replication-factor 3
```

### 8.2 Benchmark Tool — So sánh configs

Lab Go dưới đây là **demo tương đối** để thấy xu hướng batching/compression. Nó không chứng minh đầy đủ producer internals vì `kafka-go` không expose toàn bộ metric của Java producer như `batch-size-avg`, `record-queue-time-avg`, `request-latency-avg`. Khi cần benchmark nghiêm túc, chạy thêm official tool:

```bash
docker exec kafka-1 kafka-producer-perf-test.sh \
  --topic producer-bench \
  --num-records 100000 \
  --record-size 512 \
  --throughput -1 \
  --producer-props bootstrap.servers=localhost:9094 acks=all linger.ms=10 batch.size=65536 compression.type=lz4
```

```bash
mkdir -p day-11-lab && cd day-11-lab
go mod init day11-producer-internals
go get github.com/segmentio/kafka-go
```

**Benchmark code** (`benchmark.go`):

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"sync/atomic"
	"time"

	"github.com/segmentio/kafka-go"
)

type BenchConfig struct {
	Name         string
	BatchSize    int
	BatchTimeout time.Duration
	RequiredAcks kafka.RequiredAcks
	Compression  kafka.Compression
	MessageCount int
}

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Product   string    `json:"product"`
	Amount    float64   `json:"amount"`
	Timestamp time.Time `json:"timestamp"`
}

func runBenchmark(cfg BenchConfig) {
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "producer-bench",
		Balancer:     &kafka.LeastBytes{},
		BatchSize:    cfg.BatchSize,
		BatchTimeout: cfg.BatchTimeout,
		RequiredAcks: cfg.RequiredAcks,
		Compression:  cfg.Compression,
		Async:        false,
	}
	defer writer.Close()

	var totalBytes int64
	var errorCount int64

	start := time.Now()

	for i := 0; i < cfg.MessageCount; i++ {
		event := OrderEvent{
			OrderID:   fmt.Sprintf("order-%06d", i),
			Product:   "laptop-pro-max-ultra",
			Amount:    999.99,
			Timestamp: time.Now(),
		}
		value, _ := json.Marshal(event)

		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(event.OrderID),
			Value: value,
		})
		if err != nil {
			atomic.AddInt64(&errorCount, 1)
			continue
		}
		atomic.AddInt64(&totalBytes, int64(len(value)))
	}

	elapsed := time.Since(start)
	msgPerSec := float64(cfg.MessageCount) / elapsed.Seconds()
	mbPerSec := float64(totalBytes) / elapsed.Seconds() / 1024 / 1024

	fmt.Printf("\n=== %s ===\n", cfg.Name)
	fmt.Printf("Messages:    %d (errors: %d)\n", cfg.MessageCount, errorCount)
	fmt.Printf("Duration:    %v\n", elapsed.Round(time.Millisecond))
	fmt.Printf("Throughput:  %.0f msg/s\n", msgPerSec)
	fmt.Printf("Bandwidth:   %.2f MB/s\n", mbPerSec)
	fmt.Printf("Avg Latency: %.2f ms/msg\n", elapsed.Seconds()/float64(cfg.MessageCount)*1000)
}

func main() {
	messageCount := 10000

	configs := []BenchConfig{
		{
			Name:         "1) No batching (linger=0, batch=1KB)",
			BatchSize:    1024,
			BatchTimeout: 0,
			RequiredAcks: kafka.RequireAll,
			MessageCount: messageCount,
		},
		{
			Name:         "2) Small batch (linger=5ms, batch=16KB)",
			BatchSize:    16384,
			BatchTimeout: 5 * time.Millisecond,
			RequiredAcks: kafka.RequireAll,
			MessageCount: messageCount,
		},
		{
			Name:         "3) Large batch (linger=50ms, batch=64KB)",
			BatchSize:    65536,
			BatchTimeout: 50 * time.Millisecond,
			RequiredAcks: kafka.RequireAll,
			MessageCount: messageCount,
		},
		{
			Name:         "4) Large batch + LZ4 compression",
			BatchSize:    65536,
			BatchTimeout: 50 * time.Millisecond,
			RequiredAcks: kafka.RequireAll,
			Compression:  kafka.Lz4,
			MessageCount: messageCount,
		},
		{
			Name:         "5) Large batch + acks=1 (no replication wait)",
			BatchSize:    65536,
			BatchTimeout: 50 * time.Millisecond,
			RequiredAcks: kafka.RequireOne,
			Compression:  kafka.Lz4,
			MessageCount: messageCount,
		},
		{
			Name:         "6) Fire-and-forget (acks=0)",
			BatchSize:    65536,
			BatchTimeout: 50 * time.Millisecond,
			RequiredAcks: kafka.RequireNone,
			Compression:  kafka.Lz4,
			MessageCount: messageCount,
		},
	}

	fmt.Println("Starting Producer Benchmark...")
	fmt.Println("Each test sends", messageCount, "messages")

	for _, cfg := range configs {
		runBenchmark(cfg)
		time.Sleep(2 * time.Second) // cool down
	}
}
```

```bash
go run benchmark.go
```

**Kết quả mong đợi** (approximate, phụ thuộc hardware):
```
=== 1) No batching ===
Throughput:  ~500-2000 msg/s      ← chậm nhất

=== 2) Small batch ===
Throughput:  ~5000-15000 msg/s    ← 5-10x improvement

=== 3) Large batch ===
Throughput:  ~15000-30000 msg/s   ← thêm 2-3x

=== 4) + LZ4 compression ===
Throughput:  ~20000-40000 msg/s   ← network savings

=== 5) acks=1 ===
Throughput:  ~30000-50000 msg/s   ← no replication wait

=== 6) acks=0 ===
Throughput:  ~50000-100000 msg/s  ← fastest
```

### 8.3 Acks Durability Test — Chứng minh data loss

```go
// acks_durability_demo.go — Test durability với acks=0 vs acks=all
// Không đặt tên file là *_test.go nếu muốn chạy bằng `go run`.
package main

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"time"

	"github.com/segmentio/kafka-go"
)

func countMessages(topic, groupID string) int {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:9092"},
		Topic:    topic,
		GroupID:  groupID,
		MaxWait:  2 * time.Second,
	})
	defer reader.Close()

	count := 0
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	for {
		_, err := reader.ReadMessage(ctx)
		if err != nil {
			break
		}
		count++
	}
	return count
}

func main() {
	topic := "producer-acks-test"

	// Test 1: acks=all — gửi messages, kill broker, check
	fmt.Println("=== Test: acks=all ===")
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        topic,
		Balancer:     &kafka.RoundRobin{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 1 * time.Millisecond,
	}

	sent := 0
	for i := 0; i < 100; i++ {
		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(fmt.Sprintf("key-%d", i)),
			Value: []byte(fmt.Sprintf("acks-all-msg-%d", i)),
		})
		if err != nil {
			fmt.Printf("Send error at msg %d: %v\n", i, err)

			// Kill 1 broker giữa chừng
			if i == 50 {
				fmt.Println("Killing kafka-3...")
				exec.Command("docker", "stop", "kafka-3").Run()
				time.Sleep(5 * time.Second)
			}
			continue
		}
		sent++
	}
	writer.Close()
	fmt.Printf("Sent with acks=all: %d/100\n", sent)

	// Restart broker
	exec.Command("docker", "start", "kafka-3").Run()
	time.Sleep(10 * time.Second)

	received := countMessages(topic, "acks-test-consumer")
	fmt.Printf("Received: %d messages (expected: %d)\n", received, sent)
	fmt.Printf("Data loss: %d messages\n\n", sent-received)
}
```

### 8.4 Key-based Partitioning Demo

```go
// partitioner_demo.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "partition-key-demo"

	conn, err := kafka.Dial("tcp", "localhost:9092")
	if err != nil {
		log.Fatal(err)
	}
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     4,
		ReplicationFactor: 3,
	})
	conn.Close()

	writer := &kafka.Writer{
		Addr:     kafka.TCP("localhost:9092"),
		Topic:    topic,
		Balancer: &kafka.Hash{},
	}
	defer writer.Close()

	events := []struct{ key, value string }{
		{"user-alice", "login"},
		{"user-bob", "login"},
		{"user-alice", "browse"},
		{"user-charlie", "login"},
		{"user-alice", "purchase"},
		{"user-bob", "browse"},
		{"user-alice", "logout"},
		{"user-bob", "purchase"},
		{"user-charlie", "browse"},
		{"user-charlie", "purchase"},
	}

	for _, e := range events {
		writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(e.key),
			Value: []byte(e.value),
		})
	}

	fmt.Println("Messages sent. Reading back by partition...")

	for p := 0; p < 4; p++ {
		reader := kafka.NewReader(kafka.ReaderConfig{
			Brokers:   []string{"localhost:9092"},
			Topic:     topic,
			Partition: p,
			MinBytes:  1,
			MaxBytes:  10e6,
		})
		reader.SetOffset(kafka.FirstOffset)

		fmt.Printf("\n--- Partition %d ---\n", p)
		for {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			msg, err := reader.ReadMessage(ctx)
			cancel()
			if err != nil {
				break
			}
			fmt.Printf("  key=%s value=%s (offset=%d)\n",
				string(msg.Key), string(msg.Value), msg.Offset)
		}
		reader.Close()
	}

	fmt.Println("\n→ Quan sát: tất cả events của cùng 1 user nằm trong cùng partition!")
}
```

### 8.5 Idempotent Producer Simulation

```go
// idempotent_demo.go — Simulate network failure + retry
package main

import (
	"context"
	"fmt"
	"time"

	"github.com/segmentio/kafka-go"
)

func main() {
	topic := "idempotent-test"

	conn, _ := kafka.Dial("tcp", "localhost:9092")
	conn.CreateTopics(kafka.TopicConfig{
		Topic:             topic,
		NumPartitions:     1,
		ReplicationFactor: 3,
	})
	conn.Close()

	// Producer gửi cùng message "3 lần" (simulate retry)
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 1 * time.Millisecond,
	}

	for attempt := 1; attempt <= 3; attempt++ {
		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte("order-001"),
			Value: []byte(fmt.Sprintf("payment-processed (attempt %d)", attempt)),
		})
		if err != nil {
			fmt.Printf("Attempt %d failed: %v\n", attempt, err)
		} else {
			fmt.Printf("Attempt %d: sent successfully\n", attempt)
		}
	}
	writer.Close()

	// Đọc lại — quan sát có bao nhiêu messages
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:   []string{"localhost:9092"},
		Topic:     topic,
		Partition: 0,
		MinBytes:  1,
		MaxBytes:  10e6,
	})
	reader.SetOffset(kafka.FirstOffset)

	fmt.Println("\n--- Messages on topic ---")
	count := 0
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		msg, err := reader.ReadMessage(ctx)
		cancel()
		if err != nil {
			break
		}
		count++
		fmt.Printf("[%d] key=%s value=%s\n", count, string(msg.Key), string(msg.Value))
	}
	reader.Close()

	fmt.Printf("\nTotal messages: %d\n", count)
	fmt.Println("→ Kafka-go gửi 3 lần riêng biệt → 3 messages (vì đây là 3 send() calls khác nhau)")
	fmt.Println("→ Idempotent producer chỉ dedup khi CÙNG batch bị retry bởi producer internals")
	fmt.Println("→ Application-level dedup cần inbox pattern (Day 15)")
}
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **`send()` có blocking không?** Giải thích luồng từ `send()` qua RecordAccumulator đến Sender thread. Khi nào `send()` BỊ block? (Hint: buffer.memory)

2. **Bạn có 1 topic 6 partitions, producer linger.ms=50ms, batch.size=64KB. Tại sao throughput vẫn thấp?** Debug như thế nào? (Hint: message rate, buffer fullness, acks)

3. **Giải thích tại sao `acks=all` + `min.insync.replicas=2` an toàn hơn `acks=1`?** Cho scenario cụ thể khi data bị mất với acks=1 nhưng safe với acks=all. (Hint: leader crash)

4. **Sticky partitioner (key=null) tốt hơn round-robin thế nào?** Vẽ diagram so sánh batching behavior. (Hint: batch size)

5. **Idempotent producer giải quyết duplicate ở mức nào?** Nó KHÔNG giải quyết duplicate ở mức nào? Cần gì thêm? (Hint: per-partition, PID reset, cross-partition)

6. **Bạn cần gửi 500K messages/second với acks=all. Thiết kế producer config thế nào?** (Hint: batching, compression, multiple producer instances, partition count)

7. **Compression ở batch level vs message level — tại sao batch level tốt hơn?** (Hint: dictionary, similar data patterns)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Producer Configuration](https://kafka.apache.org/documentation/#producerconfigs) — tất cả producer configs
- [Kafka Design: The Producer](https://kafka.apache.org/documentation/#design_producer)
- [KIP-480: Sticky Partitioner](https://cwiki.apache.org/confluence/display/KAFKA/KIP-480%3A+Sticky+Partitioner)
- [KIP-679: Producer Will Enable Strongest Delivery Guarantee by Default](https://cwiki.apache.org/confluence/display/KAFKA/KIP-679)

### Blog Posts Chất Lượng
- [Kafka Producer Internals](https://www.conduktor.io/kafka/kafka-producer-batching/) — Conduktor
- [Optimizing Kafka Producers](https://strimzi.io/blog/2020/10/15/producer-tuning/) — Strimzi
- [Idempotent Producer Explained](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) — Confluent

### Videos
- [Inside the Kafka Producer](https://www.youtube.com/watch?v=bNrRfNkrJME) — Kafka Summit
- [Producer Performance Tuning](https://www.youtube.com/watch?v=jY02MBprByU) — Confluent
