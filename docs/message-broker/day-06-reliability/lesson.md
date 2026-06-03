# Day 6: Reliability — Publisher Confirms, Consumer Ack, Quorum Queues

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu rõ** message lifecycle trong RabbitMQ và các điểm có thể mất message
2. **Nắm vững** publisher confirms — cơ chế đảm bảo broker đã nhận message
3. **Phân biệt** persistent messages vs durable queues và tại sao cần CẢ HAI
4. **Hiểu** quorum queues — giải pháp thay thế classic mirrored queues cho high availability
5. **Thực hành** implement reliable messaging pipeline end-to-end với Go

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 4 (AMQP model, connection/channel, consumer ack)
- Đã hoàn thành Day 5 (exchange types, routing)
- Hiểu cơ bản về distributed systems consensus (Raft — sẽ giải thích lại)
- RabbitMQ đang chạy trên Docker từ Day 4

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Message lifecycle và các failure points
- Publisher confirms (individual + batch + async)
- Persistent messages + durable queues = reliable storage
- Consumer ack/nack deep dive — redelivery, prefetch tuning
- Quorum queues — tại sao tốt hơn classic mirrored queues
- Hands-on: reliable publisher + consumer pipeline

### 🟡 Should Learn (nếu còn thời gian)
- Mandatory flag — detect unroutable messages
- Transaction (tx) — tại sao KHÔNG nên dùng
- Durability vs throughput benchmarks chi tiết

### 🟢 Optional Deep Dive
- Quorum queues internals — Raft consensus protocol
- Lazy queues vs default queues
- Memory and disk alarms — flow control mechanism

---

## 4. Lý thuyết (Theory)

### 4.1 Message Lifecycle — Đâu có thể mất Message?

#### WHY — Tại sao reliability phức tạp?

Một message đi qua nhiều bước. Ở MỖI bước đều có thể mất:

```
Publisher ──①──> [Exchange] ──②──> [Queue] ──③──> Consumer
   │                                 │              │
   ①  Network failure              ②  Broker crash  ③  Consumer crash
      Publisher crash                  Disk failure     Process killed
      Broker reject                    Memory full      Bug trong code
```

**3 failure points chính:**

| Point | Failure | Hậu quả | Giải pháp |
|-------|---------|---------|-----------|
| **① Publisher → Broker** | Network drop, broker reject | Message chưa bao giờ đến broker | **Publisher Confirms** |
| **② Broker storage** | Broker crash, disk failure | Message trong memory bị mất | **Persistent messages + Durable queues + Quorum queues** |
| **③ Broker → Consumer** | Consumer crash trước khi xử lý xong | Message bị mất hoặc duplicate | **Manual Ack + Idempotent consumer** |

**Mục tiêu:** Đảm bảo message **không bị mất** ở bất kỳ failure point nào. Trade-off: reliability tăng → throughput giảm.

---

### 4.2 Publisher Confirms — Đảm bảo Broker đã nhận Message

#### WHY — Publish fire-and-forget có vấn đề gì?

Mặc định khi bạn gọi `ch.Publish()`:
- Client library gửi AMQP frame qua TCP
- **KHÔNG có confirmation** từ broker rằng message đã được nhận và lưu
- Nếu broker crash NGAY lúc nhận → message mất mà publisher không biết

```
Publisher: "Tôi đã publish thành công!" (thực ra chỉ gửi vào TCP buffer)
Broker: *crash* (chưa kịp persist)
Message: *mất vĩnh viễn*
```

#### WHAT — Publisher Confirms là gì?

Publisher Confirms là cơ chế broker **gửi ack về publisher** sau khi đã xử lý message:

```
Publisher ──publish msg──> Broker
                           │
                           ├── Persistent? → ghi vào disk
                           ├── Route đến queue(s)
                           │
Broker ──confirm (ack)───> Publisher
         "Tôi đã nhận và xử lý message của bạn"
```

- **Ack**: Broker đã nhận, persist (nếu persistent), route thành công
- **Nack**: Broker từ chối (internal error, disk full)

**Boundary quan trọng:** publisher confirm chỉ là ranh giới **publisher → broker/queue**. Nó trả lời câu hỏi "broker đã nhận và chịu trách nhiệm cho message này chưa?", không trả lời "consumer đã xử lý xong chưa?". Reliability end-to-end vẫn cần consumer manual ack, idempotency và retry/DLX ở phía consume.

#### HOW — 3 Modes của Publisher Confirms

**Mode 1: Individual Confirm (đơn giản nhất, chậm nhất)**

```
Publish msg1 → wait ack1 → Publish msg2 → wait ack2 → ...
```

- Publish 1 message, đợi confirm rồi mới publish tiếp
- **Throughput**: ~200-500 msg/s (chậm vì RTT mỗi message)
- **Khi nào dùng**: Messages ít, mỗi message cực kỳ quan trọng (financial transactions)

**Mode 2: Batch Confirm (balance)**

```
Publish msg1, msg2, ..., msg100 → wait confirm cho cả batch
```

- Publish N messages, rồi đợi confirm cho cả batch
- **Throughput**: ~5,000-10,000 msg/s
- Nếu 1 message bị nack → phải resend CẢ batch
- **Khi nào dùng**: Batch processing, data pipeline

**Mode 3: Async Confirm (nhanh nhất, phức tạp nhất)**

```
Publish msg1 ──>
Publish msg2 ──>  (không đợi)
Publish msg3 ──>
                  <── ack msg1
Publish msg4 ──>
                  <── ack msg2, msg3
                  <── nack msg4 (resend only msg4)
```

- Publish liên tục, broker gửi ack/nack async qua callback
- **Throughput**: ~20,000-30,000 msg/s
- Publisher phải track outstanding confirms
- **Khi nào dùng**: High-throughput production systems

#### Trade-off so sánh

| Mode | Throughput | Latency | Complexity | Retry granularity |
|------|-----------|---------|------------|-------------------|
| **Individual** | ~200 msg/s | Cao (wait each) | Thấp | Per-message |
| **Batch** | ~5,000 msg/s | Trung bình | Trung bình | Per-batch (kém) |
| **Async** | ~20,000 msg/s | Thấp | Cao | Per-message |
| **No confirms** | ~50,000 msg/s | Thấp nhất | Không | Không |

**Recommendation:** Dùng **async confirms** cho production. Individual chỉ cho critical messages (payments). Batch cho batch jobs.

---

### 4.3 Persistent Messages + Durable Queues

#### WHY — Confirm không đủ nếu broker crash

Publisher confirms đảm bảo broker **đã nhận** message. Nhưng nếu message chỉ nằm trong **memory** → broker crash = mất.

Cần 2 thứ:
1. **Durable queue**: Queue definition survive broker restart
2. **Persistent message**: Message content ghi vào disk

```
❌ Durable queue + Transient message:
   Broker restart → Queue tồn tại nhưng messages bên trong MẤT

❌ Non-durable queue + Persistent message:
   Broker restart → Queue bị XÓA → messages cũng mất

✅ Durable queue + Persistent message:
   Broker restart → Queue tồn tại VÀ messages còn nguyên
```

#### HOW — Cơ chế persist

```
Publisher publish persistent message:
1. Broker nhận message
2. Broker ghi message vào disk (fsync)
3. Broker route đến durable queue
4. Broker gửi confirm cho publisher

Broker crash & restart:
1. Broker đọc queue definitions từ durable store
2. Broker đọc persistent messages từ disk
3. Queue phục hồi với messages
```

#### Trade-off: Durability vs Throughput

| Config | Throughput | Durability | Use Case |
|--------|-----------|------------|----------|
| Non-durable queue + transient msg | ~100,000 msg/s | ❌ Mất khi restart | Metrics, logs tạm |
| Durable queue + transient msg | ~80,000 msg/s | ⚠️ Queue tồn tại, messages mất | Queue định nghĩa quan trọng, data không |
| Durable queue + persistent msg | ~30,000-50,000 msg/s | ✅ Full recovery | **Production default** |
| Quorum queue + persistent msg | ~20,000-30,000 msg/s | ✅✅ Replicated | **Critical production data** |

**Persistent messages chậm hơn ~2-3x** vì disk I/O (fsync). Đây là trade-off cơ bản: **durability vs performance**.

#### Gotcha: Persistent ≠ 100% safe trên single node

Ngay cả với persistent messages, vẫn có window nhỏ khi message nằm trong OS page cache chưa kịp fsync → power failure = mất.

Giải pháp: **Quorum queues** (replicated across multiple nodes) — xem phần 4.5.

---

### 4.4 Consumer Acknowledgment Deep Dive

#### Recap từ Day 4

Consumer ack/nack kiểm soát khi nào broker xóa message khỏi queue:

```
Manual Ack flow:
Broker ──deliver msg──> Consumer (msg = "unacked" trong broker)
                         │
                         ├── process success → ack → Broker xóa msg
                         ├── process fail (tạm) → nack(requeue=true) → Broker requeue
                         └── process fail (vĩnh viễn) → nack(requeue=false) → Broker discard/DLX
```

#### Multiple Ack — Batch acknowledgment

```go
// Ack multiple=true: ack message này VÀ tất cả messages trước nó (delivery tag nhỏ hơn)
msg.Ack(true)  // ack msg 1, 2, 3, 4, 5 (nếu delivery tag = 5)

// Ack multiple=false: chỉ ack message này
msg.Ack(false) // chỉ ack msg 5
```

**Khi nào dùng multiple ack?**
- Batch processing: xử lý 100 messages rồi ack một lần → ít network roundtrips
- Trade-off: Nếu crash giữa chừng, tất cả messages chưa ack bị redelivery

Phần prefetch ở Day 6 chỉ dùng để hiểu reliability boundary của unacked messages. Tuning throughput, benchmark prefetch và worker pool sẽ học sâu ở Day 9 để tránh trộn reliability với performance tuning.

#### Redelivery Flag

Khi message bị requeue (nack requeue=true, hoặc consumer disconnect), message có field `Redelivered = true`:

```go
for msg := range msgs {
    if msg.Redelivered {
        log.Printf("REDELIVERED: %s (có thể đã xử lý rồi — cần idempotent!)", msg.MessageId)
    }
    // process...
}
```

**Lưu ý:** `Redelivered = true` KHÔNG có nghĩa message đã được xử lý thành công trước đó. Nó chỉ có nghĩa broker đã deliver message ít nhất 1 lần trước. Consumer phải tự đảm bảo idempotency.

#### Consumer Prefetch Tuning

Prefetch count ảnh hưởng trực tiếp đến throughput và fair dispatch:

```
Prefetch = 1:
  Consumer A: [processing msg1] → ack → [processing msg3] → ...
  Consumer B: [processing msg2] → ack → [processing msg4] → ...
  ✅ Fair dispatch — consumer chậm không bị overload
  ❌ Throughput thấp — idle time giữa ack và nhận message tiếp

Prefetch = 100:
  Consumer A: [msg1, msg2, ..., msg100] → process & ack → [msg201, ...]
  Consumer B: [msg101, ..., msg200] → process & ack → [msg301, ...]
  ✅ Throughput cao — pipeline đầy đủ messages  
  ❌ Unfair — consumer chậm giữ 100 messages, consumer nhanh idle

Prefetch = 10-30 (sweet spot):
  Balance giữa throughput và fair dispatch
```

| Task Type | Recommended Prefetch | Lý do |
|-----------|---------------------|-------|
| Heavy tasks (video encoding) | 1-5 | Tasks lâu, cần fair dispatch |
| Medium tasks (API calls, DB writes) | 10-30 | Balance |
| Light tasks (logging, metrics) | 50-100 | Tasks nhanh, maximize throughput |
| Unknown/mixed | 10 | Safe default |

---

### 4.5 Quorum Queues — The Modern Way

#### WHY — Classic Mirrored Queues có vấn đề gì?

RabbitMQ classic mirrored queues (ha-policy) có nhiều vấn đề nghiêm trọng:
- **Synchronization blocking**: Khi mirror sync, queue bị block → messages không thể publish/consume
- **Split-brain**: Network partition → 2 masters → data inconsistency
- **Performance**: Mirror overhead lớn, throughput giảm ~50%
- **Data loss edge cases**: Khi chuyển master, messages in-flight có thể mất
- **Deprecated**: RabbitMQ team chính thức deprecate classic mirrored queues từ v3.13

#### WHAT — Quorum Queues

Quorum queues dùng **Raft consensus protocol** để replicate messages across cluster nodes. Raft đảm bảo:
- **Consensus**: Majority (quorum) nodes phải đồng ý trước khi commit
- **Leader election**: Tự động bầu leader mới khi leader crash
- **Consistent replication**: Không split-brain

```
3-Node RabbitMQ Cluster:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Node 1  │    │  Node 2  │    │  Node 3  │
│ ┌──────┐ │    │ ┌──────┐ │    │ ┌──────┐ │
│ │Leader│ │◄──►│ │Follow│ │◄──►│ │Follow│ │
│ │Queue │ │    │ │Queue │ │    │ │Queue │ │
│ └──────┘ │    │ └──────┘ │    │ └──────┘ │
└──────────┘    └──────────┘    └──────────┘

Publish flow (Raft):
1. Publisher → Leader (Node 1)
2. Leader ghi message vào local log
3. Leader replicate đến Followers (Node 2, 3)
4. Quorum (2/3 nodes) ack → message "committed"
5. Leader confirm cho Publisher

Node 1 crash:
- Node 2 và 3 bầu leader mới (Raft election)
- Client auto-reconnect đến node mới
- Không mất message đã committed
```

#### HOW — Declare Quorum Queue

```go
// Declare quorum queue — chỉ cần thêm argument
args := amqp.Table{
    "x-queue-type": "quorum",
}
ch.QueueDeclare(
    "orders.reliable",  // name
    true,               // durable — quorum queues LUÔN durable
    false,              // autoDelete — quorum queues KHÔNG hỗ trợ autoDelete
    false,              // exclusive — quorum queues KHÔNG hỗ trợ exclusive
    false,              // noWait
    args,
)
```

**Constraints của quorum queue:**
- **Luôn durable** — không thể tạo non-durable quorum queue
- **Không exclusive** — thiết kế cho shared access
- **Không autoDelete** — thiết kế cho persistence
- **Messages luôn persistent** — transient messages tự động thành persistent
- **Hỗ trợ message TTL và queue TTL** — nhưng TTL làm tăng overhead per-message; dùng có chủ đích
- **Hỗ trợ priority trong RabbitMQ hiện hành** — vẫn cần benchmark trước khi dùng rộng; separate queues thường dễ kiểm soát hơn
- **Hỗ trợ DLX** — at-most-once là default; at-least-once DLX cần policy phù hợp (Day 7)

#### Classic Queue vs Quorum Queue

| Tiêu chí | Classic Queue | Quorum Queue |
|----------|-------------|-------------|
| **Replication** | Mirrored (deprecated) hoặc single | Raft consensus |
| **Durability** | Optional | Always durable |
| **Split-brain** | Có thể xảy ra | Không (Raft) |
| **Throughput** | ~50,000 msg/s | ~20,000-30,000 msg/s |
| **Latency** | ~1ms | ~2-5ms (replication overhead) |
| **Data safety** | Weaker (async mirror) | Strong (quorum commit) |
| **Priority queues** | ✅ Hỗ trợ | ✅ Hỗ trợ, nhưng cần benchmark |
| **Message TTL** | ✅ Hỗ trợ | ✅ Hỗ trợ, có thêm overhead |
| **Lazy queues** | Legacy/ignored ở bản mới | Không áp dụng; quorum disk-first |
| **Non-durable** | ✅ Hỗ trợ | ❌ Không |
| **Memory usage** | Cao hơn (RAM-first) | Thấp hơn (disk-first) |
| **Production recommendation** | Legacy workloads | **Mặc định cho mọi use case mới** |

**Production recommendation:** Dùng quorum queues cho tất cả production queues mới. Classic queues chỉ cho:
- Temporary/exclusive queues (RPC reply queues)
- Non-critical data (logs, metrics) khi cần throughput tối đa

---

### 4.6 Mandatory Flag — Detect Unroutable Messages (Should Learn)

#### WHAT

Khi publish message mà **không có queue nào match** binding → message bị silent drop. Mandatory flag buộc broker **return message** về publisher nếu không route được.

```go
ch.PublishWithContext(ctx,
    "orders",           // exchange
    "unknown.routing",  // routing key — không match binding nào
    true,               // mandatory=true → return nếu unroutable
    false,
    amqp.Publishing{Body: payload},
)

// Handle returned messages
ch.NotifyReturn(make(chan amqp.Return, 10))
```

```
Publisher ──publish(mandatory=true, routing_key="unknown")──> Exchange
                                                                 │
                                                          No binding matches!
                                                                 │
Publisher <──return(reply_code=312, "NO_ROUTE")───────────────────┘
```

**Khi nào dùng?**
- Development/staging: detect routing bugs sớm
- Production critical paths: đảm bảo message luôn đến queue
- Alternative: dùng alternate exchange (Day 5) — đơn giản hơn

---

### 4.7 Transactions (tx) — Tại sao KHÔNG nên dùng (Should Learn)

#### WHAT

AMQP hỗ trợ transactions: `tx.Select()` → `publish...` → `tx.Commit()`. Broker đảm bảo tất cả operations trong transaction hoặc thành công hoàn toàn, hoặc rollback.

#### WHY NOT

```
Throughput comparison:
  Without confirms:  ~50,000 msg/s
  Publisher confirms: ~20,000-30,000 msg/s
  Transactions:       ~2,000-5,000 msg/s  ← 10-25x chậm hơn!
```

Transactions chậm vì:
- Broker phải fsync **synchronous** cho mỗi commit
- Không thể pipeline/batch
- Block channel cho đến khi commit complete

**Publisher confirms đạt reliability tương đương với performance tốt hơn rất nhiều.** Transactions trong RabbitMQ là legacy feature — không nên dùng cho code mới.

---

## 5. Trade-off Analysis

### Reliability Spectrum

```
Least Reliable                                          Most Reliable
     │                                                        │
     ▼                                                        ▼
Fire-and-forget → Persistent msg → Publisher confirms → Quorum queues
  ~100K msg/s     ~50K msg/s       ~20-30K msg/s        ~20K msg/s

  No ack            Durable queue    Async confirms       Raft consensus
  No persist         + disk write    + persistent msg     + replicated
  No confirm                        + durable queue      + manual ack
```

### Reliability Level cho từng Use Case

| Use Case | Cần gì? | Throughput | Config |
|----------|---------|-----------|--------|
| **Metrics/Logs** | Mất vài message OK | ~100K msg/s | Auto-ack, non-durable, no confirms |
| **Notifications** | Mất ít acceptable | ~50K msg/s | Persistent, durable, no confirms |
| **Order processing** | Không được mất | ~20-30K msg/s | Persistent, durable, async confirms, manual ack |
| **Financial transactions** | Tuyệt đối không mất | ~15-20K msg/s | Quorum queue, individual confirms, manual ack, idempotent consumer |

### End-to-End Reliable Pipeline

Đảm bảo **không mất message** ở bất kỳ điểm nào:

```
Publisher:
  ✅ Publisher confirms (async)
  ✅ Persistent messages (DeliveryMode: 2)
  ✅ Retry logic khi nack
  ✅ Connection recovery

Broker:
  ✅ Durable exchange
  ✅ Quorum queue (replicated)
  ✅ Alternate exchange cho unroutable messages

Consumer:
  ✅ Manual ack (autoAck=false)
  ✅ Nack + requeue cho transient errors
  ✅ Nack + no-requeue cho permanent errors → DLX
  ✅ Prefetch tuning
  ✅ Idempotent processing (MessageId deduplication)
```

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Luôn dùng async publisher confirms cho production**
   - Individual confirms chỉ cho financial/critical path
   - Batch confirms cho batch jobs
   - Track outstanding confirms bằng map/channel

2. **Durable queue + persistent message = default cho mọi production queue**
   ```go
   // ✅ Production default
   ch.QueueDeclare("orders", true, false, false, false, amqp.Table{
       "x-queue-type": "quorum",
   })
   ch.PublishWithContext(ctx, exchange, key, false, false, amqp.Publishing{
       DeliveryMode: amqp.Persistent,
       Body:         payload,
   })
   ```

3. **Quorum queues cho mọi queue mới trong cluster**
   - Nếu chạy single node development → classic queue OK
   - Nếu chạy cluster (staging/production) → quorum queue mặc định

4. **Implement connection recovery**
   - Network failures WILL happen
   - `amqp091-go` không auto-reconnect — phải tự implement
   - Dùng exponential backoff khi reconnect

5. **Separate connections cho publish và consume**
   - Flow control trên publish connection không block consume
   - Consume connection disconnect → requeue messages → không ảnh hưởng publish

6. **Prefetch count phải phù hợp với task duration**
   - Tasks 1s+ → prefetch 1-5
   - Tasks 100ms → prefetch 10-30
   - Tasks <10ms → prefetch 50-100

### Common Pitfalls

1. **Pitfall: Persistent message trên non-durable queue**
   ```
   ❌ Non-durable queue + persistent message
      → Broker restart = queue bị xóa = messages mất dù persistent
   
   ✅ Durable queue + persistent message
      → Broker restart = queue tồn tại + messages còn
   ```

2. **Pitfall: Publish confirms nhưng không handle nack**
   ```go
   // ❌ Bật confirms nhưng không listen nack
   ch.Confirm(false)
   ch.Publish(...)
   // Nếu broker nack → message mất silently
   
   // ✅ Handle cả ack và nack
   confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 100))
   go func() {
       for confirm := range confirms {
           if !confirm.Ack {
               log.Printf("Message %d NACKED — need to resend!", confirm.DeliveryTag)
           }
       }
   }()
   ```

3. **Pitfall: Consumer crash → infinite redelivery loop**
   - Message gây crash → redelivery → crash → redelivery → ...
   - Fix: Đếm redelivery (x-delivery-count header trong quorum queues), sau N lần → DLX (Day 7)
   - Quorum queues tự động track delivery count

4. **Pitfall: Quorum queue cho temporary/reply queues**
   ```
   ❌ Quorum queue cho RPC reply queue
      → Quorum queue không hỗ trợ exclusive + autoDelete
      → Overhead replication cho temporary data
   
   ✅ Classic queue cho RPC reply queues
      → Exclusive, autoDelete, non-durable — đúng semantics
   ```

5. **Pitfall: Không có connection recovery**
   ```go
   // ❌ Connect 1 lần, crash khi disconnect
   conn, _ := amqp.Dial(url)
   // ... 3 giờ sau, network blip, connection đứt
   // ch.Publish() → error, application crash
   
   // ✅ Reconnect loop (xem Lab phần 8.4)
   ```

---

## 7. Performance Considerations

### Benchmark: Reliability vs Throughput

```
Test: 1KB messages, single node, 1 publisher, 1 consumer

╔═══════════════════════════════════════════════════════════╗
║ Configuration                        │ Throughput (msg/s) ║
╠═══════════════════════════════════════════════════════════╣
║ Auto-ack, non-persistent, no confirms│ ~100,000           ║
║ Manual-ack, non-persistent, no confirms│ ~65,000          ║
║ Manual-ack, persistent, no confirms  │ ~45,000            ║
║ Manual-ack, persistent, async confirms│ ~28,000           ║
║ Manual-ack, persistent, individual confirms│ ~500         ║
║ Manual-ack, quorum queue, async confirms│ ~22,000         ║
║ Transaction (tx.Commit)              │ ~3,000             ║
╚═══════════════════════════════════════════════════════════╝
```

### Quorum Queue Cluster Sizing

| Cluster Size | Quorum | Tolerate Failures | Throughput Impact | Recommendation |
|-------------|--------|------------------|-------------------|----------------|
| 3 nodes | 2 | 1 node down | Baseline | **Development/staging** |
| 5 nodes | 3 | 2 nodes down | -15% vs 3-node | **Production** |
| 7 nodes | 4 | 3 nodes down | -25% vs 3-node | Overkill cho hầu hết |

**Rule of thumb:** 3 nodes cho hầu hết production. 5 nodes cho mission-critical. Luôn dùng **odd number** (3, 5, 7) để Raft quorum hoạt động tốt.

### Disk I/O — Bottleneck chính của Persistence

```
Persistent message workload:
  Message arrive → write to WAL (Write-Ahead Log) → fsync

Disk type matters:
  HDD: ~200 IOPS → ~200 persistent msg/s đồng bộ
  SSD: ~50,000 IOPS → ~50,000 persistent msg/s đồng bộ
  NVMe: ~500,000 IOPS → I/O không còn là bottleneck
```

**Production tip:** Luôn dùng SSD/NVMe cho RabbitMQ data directory. HDD + persistent messages = performance rất kém.

### Key Metrics cho Reliability Monitoring

| Metric | Ý nghĩa | Alert threshold |
|--------|---------|-----------------|
| `messages_unacknowledged` | Messages delivered nhưng chưa ack | > prefetch × consumers (consumer stuck) |
| `messages_ready` | Messages chờ trong queue | Trending up (consumer lag) |
| `confirm_rate` | Publisher confirms/s | Drop đột ngột (broker overload) |
| `disk_free` | Disk space còn lại | < 2× min_free_disk_limit |
| `mem_used` | Memory usage | > 80% watermark |
| `queue_leader_changes` (quorum) | Số lần leader thay đổi | > 0 (node instability) |

---

## 8. Hands-on Lab

### 8.1 Setup

```bash
# Đảm bảo RabbitMQ đang chạy từ Day 4
docker compose up -d

# Tạo thư mục lab
mkdir -p day-06-reliability/lab && cd day-06-reliability/lab
go mod init reliability-lab
go get github.com/rabbitmq/amqp091-go
```

### 8.2 Lab 1: Publisher Confirms — 3 Modes

**File `publisher_confirms.go`:**
```go
package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	// Setup queue
	setupCh, _ := conn.Channel()
	setupCh.QueueDeclare("confirm-test", true, false, false, false, nil)
	setupCh.Close()

	messageCount := 100

	// Mode 1: Individual confirms
	log.Println("\n=== Mode 1: Individual Confirms ===")
	individualConfirms(conn, messageCount)

	// Mode 2: Batch confirms
	log.Println("\n=== Mode 2: Batch Confirms ===")
	batchConfirms(conn, messageCount)

	// Mode 3: Async confirms
	log.Println("\n=== Mode 3: Async Confirms ===")
	asyncConfirms(conn, messageCount)
}

func individualConfirms(conn *amqp.Connection, count int) {
	ch, _ := conn.Channel()
	defer ch.Close()

	// Bật confirm mode trên channel
	ch.Confirm(false)
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 1))

	start := time.Now()
	ctx := context.Background()

	for i := 0; i < count; i++ {
		body := fmt.Sprintf(`{"id": %d, "mode": "individual"}`, i)
		ch.PublishWithContext(ctx, "", "confirm-test", false, false,
			amqp.Publishing{DeliveryMode: amqp.Persistent, Body: []byte(body)},
		)

		// Đợi confirm cho TỪNG message
		confirmed := <-confirms
		if !confirmed.Ack {
			log.Printf("Message %d NACKED!", confirmed.DeliveryTag)
		}
	}

	elapsed := time.Since(start)
	log.Printf("Individual: %d messages in %v (%.0f msg/s)",
		count, elapsed, float64(count)/elapsed.Seconds())
}

func batchConfirms(conn *amqp.Connection, count int) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Confirm(false)
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, count))

	batchSize := 20
	start := time.Now()
	ctx := context.Background()

	for i := 0; i < count; i++ {
		body := fmt.Sprintf(`{"id": %d, "mode": "batch"}`, i)
		ch.PublishWithContext(ctx, "", "confirm-test", false, false,
			amqp.Publishing{DeliveryMode: amqp.Persistent, Body: []byte(body)},
		)

		// Đợi confirm sau mỗi batch
		if (i+1)%batchSize == 0 {
			for j := 0; j < batchSize; j++ {
				confirmed := <-confirms
				if !confirmed.Ack {
					log.Printf("Batch message NACKED: tag=%d", confirmed.DeliveryTag)
				}
			}
		}
	}

	// Drain remaining confirms
	remaining := count % batchSize
	for i := 0; i < remaining; i++ {
		<-confirms
	}

	elapsed := time.Since(start)
	log.Printf("Batch(%d): %d messages in %v (%.0f msg/s)",
		batchSize, count, elapsed, float64(count)/elapsed.Seconds())
}

func asyncConfirms(conn *amqp.Connection, count int) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Confirm(false)
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, count))

	start := time.Now()
	ctx := context.Background()

	// Track unconfirmed messages
	var mu sync.Mutex
	unconfirmed := make(map[uint64]bool)
	var nackCount int

	// Async handler — process confirms in background
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		confirmed := 0
		for confirm := range confirms {
			mu.Lock()
			delete(unconfirmed, confirm.DeliveryTag)
			mu.Unlock()

			if !confirm.Ack {
				nackCount++
				log.Printf("NACK: delivery tag %d — would resend in production", confirm.DeliveryTag)
			}
			confirmed++
			if confirmed >= count {
				return
			}
		}
	}()

	// Publish all messages without waiting for individual confirms
	for i := 0; i < count; i++ {
		body := fmt.Sprintf(`{"id": %d, "mode": "async"}`, i)

		mu.Lock()
		unconfirmed[uint64(i+1)] = true
		mu.Unlock()

		ch.PublishWithContext(ctx, "", "confirm-test", false, false,
			amqp.Publishing{DeliveryMode: amqp.Persistent, Body: []byte(body)},
		)
	}

	// Wait for all confirms
	wg.Wait()

	elapsed := time.Since(start)
	log.Printf("Async: %d messages in %v (%.0f msg/s), nacks: %d",
		count, elapsed, float64(count)/elapsed.Seconds(), nackCount)
}
```

```bash
go run publisher_confirms.go
```

**Expected output (throughput comparison):**
```
=== Mode 1: Individual Confirms ===
Individual: 100 messages in 1.2s (83 msg/s)

=== Mode 2: Batch Confirms ===
Batch(20): 100 messages in 180ms (555 msg/s)

=== Mode 3: Async Confirms ===
Async: 100 messages in 45ms (2222 msg/s)
```

### 8.3 Lab 2: Quorum Queue — Reliability Demo

**File `quorum_demo.go`:**
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

	amqp "github.com/rabbitmq/amqp091-go"
)

type Payment struct {
	PaymentID string  `json:"payment_id"`
	OrderID   string  `json:"order_id"`
	Amount    float64 `json:"amount"`
	Currency  string  `json:"currency"`
}

func main() {
	mode := "demo"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	switch mode {
	case "setup":
		setupQuorumQueue(conn)
	case "publish":
		publishReliable(conn)
	case "consume":
		consumeReliable(conn)
	default:
		setupQuorumQueue(conn)
		go consumeReliable(conn)
		time.Sleep(500 * time.Millisecond)
		publishReliable(conn)
		time.Sleep(3 * time.Second)
	}
}

func setupQuorumQueue(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	exchangeName := "payments"
	queueName := "payments.process"

	// Durable exchange
	ch.ExchangeDeclare(exchangeName, "direct", true, false, false, false, nil)

	// Quorum queue — chỉ thêm x-queue-type argument
	_, err := ch.QueueDeclare(
		queueName,
		true,  // durable — bắt buộc cho quorum queue
		false, // autoDelete — không hỗ trợ cho quorum queue
		false, // exclusive — không hỗ trợ cho quorum queue
		false,
		amqp.Table{
			"x-queue-type":           "quorum",
			"x-delivery-limit":       5,     // Max redelivery trước khi đến DLX
			"x-quorum-initial-group-size": 3, // Số replicas (cần cluster 3+ nodes)
		},
	)
	if err != nil {
		// QueueDeclare failure closes the AMQP channel. Open a new channel before retrying.
		ch.Close()
		ch, err = conn.Channel()
		if err != nil {
			log.Fatal(err)
		}

		log.Printf("Retry without x-quorum-initial-group-size after declare error: %v", err)
		if _, err = ch.QueueDeclare(queueName, true, false, false, false,
			amqp.Table{
				"x-queue-type":     "quorum",
				"x-delivery-limit": 5,
			},
		); err != nil {
			log.Fatal(err)
		}
	}

	ch.QueueBind(queueName, "payment.process", exchangeName, false, nil)
	log.Printf("Quorum queue '%s' created and bound to '%s'", queueName, exchangeName)
}

func publishReliable(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	// Bật publisher confirms
	ch.Confirm(false)
	confirmCh := ch.NotifyPublish(make(chan amqp.Confirmation, 10))

	ctx := context.Background()

	payments := []Payment{
		{"PAY-001", "ORD-001", 999.99, "USD"},
		{"PAY-002", "ORD-002", 49.99, "USD"},
		{"PAY-003", "ORD-003", 1499.99, "USD"},
		{"PAY-004", "ORD-004", 0, "USD"}, // Amount 0 → sẽ bị reject bởi consumer
		{"PAY-005", "ORD-005", 299.99, "USD"},
	}

	for _, p := range payments {
		body, _ := json.Marshal(p)

		err := ch.PublishWithContext(ctx,
			"payments",         // exchange
			"payment.process",  // routing key
			false, false,
			amqp.Publishing{
				DeliveryMode:  amqp.Persistent,
				ContentType:   "application/json",
				MessageId:     p.PaymentID, // Unique ID cho idempotency
				CorrelationId: p.OrderID,   // Correlation cho tracing
				Timestamp:     time.Now(),
				Body:          body,
			},
		)
		if err != nil {
			log.Printf("Publish failed for %s: %v", p.PaymentID, err)
			continue
		}

		// Wait for individual confirm (critical path — payment!)
		confirmed := <-confirmCh
		if confirmed.Ack {
			log.Printf("CONFIRMED: %s ($%.2f) — broker acknowledged", p.PaymentID, p.Amount)
		} else {
			log.Printf("NACKED: %s — broker rejected, MUST retry!", p.PaymentID)
		}
	}
}

func consumeReliable(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	queueName := "payments.process"

	// Prefetch 1 cho payment processing — mỗi payment process cẩn thận
	ch.Qos(1, 0, false)

	msgs, err := ch.Consume(queueName, "payment-processor", false, false, false, false, nil)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("Payment processor started (queue: %s, prefetch: 1)", queueName)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var payment Payment
			if err := json.Unmarshal(msg.Body, &payment); err != nil {
				log.Printf("REJECT: bad message format — %v", err)
				msg.Nack(false, false)
				continue
			}

			// Check delivery count (quorum queue feature)
			deliveryCount := int64(0)
			if dc, ok := msg.Headers["x-delivery-count"]; ok {
				switch v := dc.(type) {
				case int64:
					deliveryCount = v
				case int32:
					deliveryCount = int64(v)
				}
			}

			if deliveryCount > 0 {
				log.Printf("REDELIVERY #%d: %s (was delivered before)", deliveryCount, payment.PaymentID)
			}

			// Business validation
			if payment.Amount <= 0 {
				log.Printf("REJECT: %s — invalid amount $%.2f (permanent error, no requeue)",
					payment.PaymentID, payment.Amount)
				msg.Nack(false, false) // requeue=false → dead letter (nếu có DLX)
				continue
			}

			// Simulate processing
			log.Printf("Processing: %s — $%.2f %s (order: %s)",
				payment.PaymentID, payment.Amount, payment.Currency, payment.OrderID)
			time.Sleep(300 * time.Millisecond)

			// Simulate occasional transient failure
			if payment.PaymentID == "PAY-002" && deliveryCount == 0 {
				log.Printf("TRANSIENT FAIL: %s — payment gateway timeout, requeuing", payment.PaymentID)
				msg.Nack(false, true) // requeue=true → try again
				continue
			}

			msg.Ack(false)
			log.Printf("SUCCESS: %s — payment processed ✓", payment.PaymentID)
		}
	}()

	<-sig
	log.Println("Payment processor shutting down...")
}
```

```bash
# All-in-one demo
go run quorum_demo.go

# Hoặc riêng:
go run quorum_demo.go setup
go run quorum_demo.go consume  # Terminal 1
go run quorum_demo.go publish  # Terminal 2
```

**Expected output:**
```
Quorum queue 'payments.process' created and bound to 'payments'
Payment processor started (queue: payments.process, prefetch: 1)

CONFIRMED: PAY-001 ($999.99) — broker acknowledged
Processing: PAY-001 — $999.99 USD (order: ORD-001)
SUCCESS: PAY-001 — payment processed ✓

CONFIRMED: PAY-002 ($49.99) — broker acknowledged
Processing: PAY-002 — $49.99 USD (order: ORD-002)
TRANSIENT FAIL: PAY-002 — payment gateway timeout, requeuing
REDELIVERY #1: PAY-002 (was delivered before)
Processing: PAY-002 — $49.99 USD (order: ORD-002)
SUCCESS: PAY-002 — payment processed ✓

CONFIRMED: PAY-003 ($1499.99) — broker acknowledged
Processing: PAY-003 — $1499.99 USD (order: ORD-003)
SUCCESS: PAY-003 — payment processed ✓

CONFIRMED: PAY-004 ($0.00) — broker acknowledged
REJECT: PAY-004 — invalid amount $0.00 (permanent error, no requeue)

CONFIRMED: PAY-005 ($299.99) — broker acknowledged
Processing: PAY-005 — $299.99 USD (order: ORD-005)
SUCCESS: PAY-005 — payment processed ✓
```

### 8.4 Lab 3: Connection Recovery

**File `connection_recovery.go`:**
```go
package main

import (
	"context"
	"fmt"
	"log"
	"math"
	"os"
	"os/signal"
	"syscall"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

type RabbitMQClient struct {
	conn    *amqp.Connection
	channel *amqp.Channel
	url     string
}

func NewRabbitMQClient(url string) *RabbitMQClient {
	client := &RabbitMQClient{url: url}
	client.connect()
	return client
}

func (c *RabbitMQClient) connect() {
	var err error
	maxRetries := 10

	for attempt := 1; attempt <= maxRetries; attempt++ {
		c.conn, err = amqp.Dial(c.url)
		if err == nil {
			c.channel, err = c.conn.Channel()
			if err == nil {
				log.Printf("Connected to RabbitMQ (attempt %d)", attempt)
				c.monitorConnection()
				return
			}
		}

		// Exponential backoff: 1s, 2s, 4s, 8s, ... capped at 30s
		backoff := time.Duration(math.Min(math.Pow(2, float64(attempt-1)), 30)) * time.Second
		log.Printf("Connection attempt %d failed: %v. Retrying in %v...", attempt, err, backoff)
		time.Sleep(backoff)
	}

	log.Fatalf("Failed to connect after %d attempts", maxRetries)
}

func (c *RabbitMQClient) monitorConnection() {
	// RabbitMQ gửi close notification khi connection bị đứt
	closeCh := make(chan *amqp.Error, 1)
	c.conn.NotifyClose(closeCh)

	go func() {
		amqpErr := <-closeCh
		if amqpErr != nil {
			log.Printf("Connection lost: %v. Reconnecting...", amqpErr)
			c.connect()
		}
	}()
}

func (c *RabbitMQClient) Publish(exchange, routingKey string, body []byte) error {
	if c.channel == nil {
		return fmt.Errorf("channel not available")
	}
	return c.channel.PublishWithContext(
		context.Background(),
		exchange, routingKey, false, false,
		amqp.Publishing{
			DeliveryMode: amqp.Persistent,
			ContentType:  "application/json",
			Body:         body,
		},
	)
}

func (c *RabbitMQClient) Close() {
	if c.channel != nil {
		c.channel.Close()
	}
	if c.conn != nil {
		c.conn.Close()
	}
}

func main() {
	client := NewRabbitMQClient("amqp://admin:admin123@localhost:5672/")
	defer client.Close()

	// Declare queue
	client.channel.QueueDeclare("recovery-test", true, false, false, false, nil)

	// Publish periodically
	go func() {
		for i := 1; ; i++ {
			body := fmt.Sprintf(`{"msg": %d, "time": "%s"}`, i, time.Now().Format(time.RFC3339))
			err := client.Publish("", "recovery-test", []byte(body))
			if err != nil {
				log.Printf("Publish failed: %v (will retry after reconnect)", err)
			} else {
				log.Printf("Published message %d", i)
			}
			time.Sleep(2 * time.Second)
		}
	}()

	log.Println("Publishing every 2s. Try: docker compose restart rabbitmq")

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
}
```

```bash
go run connection_recovery.go

# Trong terminal khác — restart RabbitMQ để test recovery:
docker compose restart rabbitmq

# Quan sát: client tự reconnect sau vài giây
```

### 8.5 Lab 4: Queue Type Comparison

Kiểm tra sự khác biệt giữa classic và quorum queue trên Management UI:

```bash
# Tạo cả 2 loại queue để so sánh
curl -s -u admin:admin123 -X PUT \
  -H "content-type: application/json" \
  -d '{"auto_delete":false,"durable":true,"arguments":{}}' \
  http://localhost:15672/api/queues/%2F/test.classic

curl -s -u admin:admin123 -X PUT \
  -H "content-type: application/json" \
  -d '{"auto_delete":false,"durable":true,"arguments":{"x-queue-type":"quorum"}}' \
  http://localhost:15672/api/queues/%2F/test.quorum

# So sánh thông tin queue
echo "=== Classic Queue ==="
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/test.classic | \
  jq '{name, type, durable, arguments}'

echo "=== Quorum Queue ==="
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/test.quorum | \
  jq '{name, type, durable, arguments}'
```

Mở Management UI → Queues tab:
- Classic queue: type = "classic"
- Quorum queue: type = "quorum", thấy thêm thông tin Raft leader/followers

### 8.6 Lab 5: Quan sát Reliability Metrics

```bash
# Queue depth và unacked messages
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/payments.process | jq '{
  messages_ready: .messages_ready,
  messages_unacknowledged: .messages_unacknowledged,
  messages_total: .messages,
  consumers: .consumers,
  consumer_utilisation: .consumer_utilisation,
  type: .type
}'

# Overview — message rates
curl -s -u admin:admin123 http://localhost:15672/api/overview | jq '{
  publish_rate: .message_stats.publish_details.rate,
  deliver_rate: .message_stats.deliver_get_details.rate,
  ack_rate: .message_stats.ack_details.rate,
  confirm_rate: .message_stats.confirm_details.rate
}'

# Node health — memory & disk
curl -s -u admin:admin123 http://localhost:15672/api/nodes | jq '.[0] | {
  name,
  mem_used_mb: (.mem_used / 1048576 | floor),
  mem_limit_mb: (.mem_limit / 1048576 | floor),
  disk_free_mb: (.disk_free / 1048576 | floor),
  disk_free_limit_mb: (.disk_free_limit / 1048576 | floor),
  running: .running
}'
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Giải thích tại sao `Persistent message` + `Durable queue` vẫn chưa đủ để đảm bảo message không mất.** Có scenario nào persistent message vẫn mất trên single node? Quorum queue giải quyết vấn đề này thế nào?

   *Hint: Nghĩ về OS page cache và khoảng thời gian giữa write và fsync. Power failure trong window này → dữ liệu trong page cache chưa flush xuống disk bị mất.*

2. **So sánh 3 modes publisher confirms (individual, batch, async) về throughput, latency, và retry granularity.** Cho financial payment system xử lý $1M/ngày, bạn chọn mode nào và tại sao?

   *Hint: Financial → individual confirms (mỗi payment phải được confirm). Nhưng nếu volume lớn (>10K payments/s), async confirms + per-message tracking có thể là trade-off tốt hơn.*

3. **Consumer prefetch count ảnh hưởng thế nào đến throughput và fairness?** Cho scenario: 5 consumers, mỗi task mất 2 giây, queue có 1000 messages. Prefetch=1 vs prefetch=100 — throughput tổng và fairness khác nhau thế nào?

   *Hint: Prefetch=1 → 5 messages đang xử lý cùng lúc, fair. Prefetch=100 → consumer đầu tiên "grab" 100 messages, bất công nếu task duration không đều.*

4. **Quorum queues dùng Raft consensus. Giải thích bằng lời đơn giản: khi publisher gửi 1 message vào quorum queue (3 nodes), flow nào xảy ra trước khi publisher nhận confirm?**

   *Hint: Leader ghi local → replicate đến followers → 2/3 nodes ack (quorum) → leader confirm cho publisher.*

5. **Tại sao RabbitMQ team deprecate classic mirrored queues và khuyến cáo quorum queues?** Cho 3 vấn đề chính của mirrored queues.

   *Hint: Sync blocking, split-brain, data loss edge cases.*

6. **Design question:** Thiết kế reliable messaging pipeline cho e-commerce order processing. Messages KHÔNG ĐƯỢC mất. Throughput cần ~5,000 msg/s. Chi tiết:
   - Publisher: dùng confirms mode nào?
   - Queue: classic hay quorum?
   - Consumer: auto-ack hay manual-ack? Prefetch bao nhiêu?
   - Failure handling: message xử lý lỗi thì sao?

   *Hint: Async confirms, quorum queue, manual ack, prefetch 10-20, nack + DLX cho permanent errors.*

7. **Benchmark question:** Bạn đo throughput được 28,000 msg/s với persistent messages + async confirms. Yêu cầu tăng lên 60,000 msg/s mà vẫn reliable. Có những options nào?

   *Hint: Horizontal scaling (thêm queues + sharding), non-persistent cho non-critical subset, faster disk (NVMe), tune batch sizes.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Publisher Confirms](https://www.rabbitmq.com/confirms.html#publisher-confirms)
- [Consumer Acknowledgements](https://www.rabbitmq.com/confirms.html#consumer-acknowledgements)
- [Quorum Queues](https://www.rabbitmq.com/quorum-queues.html)
- [Persistence Configuration](https://www.rabbitmq.com/persistence-conf.html)
- [Reliability Guide](https://www.rabbitmq.com/reliability.html)

### Architecture & Design
- [RabbitMQ Reliability — CloudAMQP](https://www.cloudamqp.com/blog/part2-rabbitmq-best-practice.html)
- [Quorum Queues — What, Why, How — RabbitMQ Blog](https://blog.rabbitmq.com/posts/2020/04/quorum-queues-and-why-they-matter/)
- [Classic vs Quorum Queues — Benchmarks](https://blog.rabbitmq.com/posts/2022/05/rabbitmq-3.10-performance-improvements/)

### Deep Dive
- [Raft Consensus Algorithm — Visualization](https://raft.github.io/)
- [RabbitMQ Internals — How Quorum Queues Work](https://www.youtube.com/watch?v=3P5yVpvvA5A)
- [RabbitMQ Performance Tuning — Pivotal](https://tanzu.vmware.com/developer/blog/rabbitmq-performance-tuning/)

### Videos
- [RabbitMQ Quorum Queues Deep Dive — RabbitMQ Summit 2019](https://www.youtube.com/watch?v=kR5YwvR-qKc)
- [Reliable Messaging with RabbitMQ — GOTO Conference](https://www.youtube.com/watch?v=XjuiZM7JzPw)
