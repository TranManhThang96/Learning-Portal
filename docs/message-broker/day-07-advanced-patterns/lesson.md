# Day 7: Advanced Patterns — DLX, TTL, Priority Queue, Delayed Messages, RPC, Retry Strategy

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** Dead Letter Exchange (DLX) — cơ chế xử lý messages thất bại trong RabbitMQ
2. **Nắm vững** retry strategy: immediate retry, delayed retry, exponential backoff với DLX + TTL
3. **Biết cách** detect và quarantine poison messages để tránh infinite redelivery loop
4. **Hiểu** RPC pattern qua RabbitMQ — request-reply với correlation ID
5. **Thực hành** implement retry pipeline end-to-end với Go: retry → DLQ → monitoring

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 4 (AMQP model, connection/channel, consumer ack/nack)
- Đã hoàn thành Day 5 (exchange types, topic routing)
- Đã hoàn thành Day 6 (publisher confirms, quorum queues, consumer ack deep dive)
- Hiểu nack(requeue=false) sẽ discard hoặc route đến DLX
- RabbitMQ đang chạy trên Docker từ Day 4

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Dead Letter Exchange (DLX) — tại sao cần, cách setup, flow chi tiết
- TTL (Time-To-Live) — per-queue và per-message
- Retry strategy với DLX + TTL — delayed retry, exponential backoff
- Poison message handling — detect, quarantine, alert
- Hands-on: retry pipeline hoàn chỉnh

### 🟡 Should Learn (nếu còn thời gian)
- Priority queues — khi nào dùng, limitations
- Overflow behavior (`drop-head`, `reject-publish`) và tác động đến DLX
- RPC pattern — request-reply với correlation ID, reply-to queue (đọc sâu/lab phụ)
- Delayed Message Exchange plugin (đọc sâu/lab phụ vì phụ thuộc plugin)

### 🟢 Optional Deep Dive
- Saga pattern basics — choreography vs orchestration qua RabbitMQ
- Complex retry topologies (multi-level retry)
- Message scheduling patterns

---

## 4. Lý thuyết (Theory)

### 4.1 Dead Letter Exchange (DLX) — Xử lý Messages Thất Bại

#### WHY — Tại sao cần DLX?

Từ Day 4 lab, bạn đã thấy vấn đề: message `ORD-005` bị nack(requeue=true) → requeue → nhận lại → nack → requeue → **vòng lặp vô hạn**.

3 cách message có thể "chết":
1. **Consumer reject** — `nack(requeue=false)` hoặc `reject(requeue=false)`
2. **TTL expired** — message quá hạn thời gian sống
3. **Queue full** — queue đạt `x-max-length`, message mới push message cũ ra

Không có DLX → messages chết **biến mất vĩnh viễn**. Mất data, không thể debug, không thể retry.

```
Không có DLX:
  Consumer ──nack(requeue=false)──> Message BIẾN MẤT 💀

Có DLX:
  Consumer ──nack(requeue=false)──> [Dead Letter Exchange] ──> [Dead Letter Queue]
                                                                     │
                                                          Monitor, debug, replay
```

#### WHAT — Dead Letter Exchange là gì?

DLX là một **exchange bình thường** (direct, fanout, topic — bất kỳ type nào), được chỉ định là "nơi chuyển tiếp" cho messages bị reject/expire/overflow từ một queue.

Khi message bị dead-lettered:
1. Message được **remove** khỏi queue gốc
2. Message được **publish** vào DLX với routing key gốc (hoặc routing key override)
3. DLX route message vào Dead Letter Queue (DLQ) theo binding rules thông thường
4. Headers đặc biệt được thêm vào message: `x-death` (chứa lịch sử dead-letter)

```
┌──────────────────────────────────────────────────────────────┐
│                    Normal Flow                                │
│                                                               │
│  Publisher ──> [Exchange] ──> [Queue: orders.process]          │
│                                       │                       │
│                                  Consumer                     │
│                                  ├── ack → ✅ done            │
│                                  ├── nack(requeue=true) → 🔁  │
│                                  └── nack(requeue=false) ──┐  │
│                                                            │  │
│                    Dead Letter Flow                        │  │
│                                                            ▼  │
│                              [DLX: orders.dlx] ──> [DLQ: orders.dead-letter]
│                                                         │     │
│                                                    Monitor    │
│                                                    Debug      │
│                                                    Replay     │
└──────────────────────────────────────────────────────────────┘
```

#### HOW — Setup DLX

```go
// 1. Declare DLX (exchange bình thường)
ch.ExchangeDeclare("orders.dlx", "fanout", true, false, false, false, nil)

// 2. Declare DLQ (queue bình thường)
ch.QueueDeclare("orders.dead-letter", true, false, false, false, nil)
ch.QueueBind("orders.dead-letter", "", "orders.dlx", false, nil)

// 3. Declare main queue VỚI DLX argument
ch.QueueDeclare("orders.process", true, false, false, false, amqp.Table{
    "x-dead-letter-exchange":    "orders.dlx",        // DLX name
    "x-dead-letter-routing-key": "orders.dead-letter", // Optional: override routing key
})
```

**x-death header** — Lịch sử dead-lettering:

Khi message đến DLQ, RabbitMQ tự thêm header `x-death`:
```json
{
  "x-death": [{
    "count": 1,
    "exchange": "",
    "queue": "orders.process",
    "reason": "rejected",
    "routing-keys": ["orders.process"],
    "time": "2024-01-15T10:30:00Z"
  }]
}
```

Reasons có thể là:
- `rejected` — consumer nack/reject với requeue=false
- `expired` — message TTL hết
- `maxlen` — queue overflow (x-max-length)
- `delivery-limit` — quorum queue delivery limit (x-delivery-limit)

---

### 4.2 TTL (Time-To-Live) — Thời gian sống của Message

#### WHY — Tại sao cần TTL?

Messages không nên nằm mãi trong queue:
- Order confirmation notification sau 24h → vô nghĩa, nên bỏ
- Payment processing request sau 30 phút → nên timeout, thông báo user
- Retry message → nên có thời gian chờ trước khi thử lại (delayed retry)

#### WHAT — 2 Loại TTL

**1. Per-Queue TTL — Tất cả messages trong queue có cùng TTL**

```go
ch.QueueDeclare("notifications", true, false, false, false, amqp.Table{
    "x-message-ttl": 86400000, // 24 giờ = 86,400,000 ms
    "x-dead-letter-exchange": "notifications.dlx",
})
```

- Mọi message đến queue này tự expire sau 24 giờ
- Hiệu quả hơn per-message TTL (broker optimize cho cùng TTL)
- Message ở **đầu queue** expire trước (FIFO order)

**2. Per-Message TTL — Mỗi message có TTL riêng**

```go
ch.PublishWithContext(ctx, exchange, routingKey, false, false,
    amqp.Publishing{
        Expiration: "60000", // 60 giây (string, đơn vị ms!)
        Body:       payload,
    },
)
```

- Mỗi message có thể có TTL khác nhau
- **Gotcha:** RabbitMQ chỉ check TTL ở **đầu queue**. Message expired ở giữa queue KHÔNG bị remove cho đến khi nó đến đầu queue hoặc được deliver
- Dùng cho: delayed retry với exponential backoff (mỗi retry TTL khác nhau)

#### Trade-off: Per-Queue TTL vs Per-Message TTL

| Tiêu chí | Per-Queue TTL | Per-Message TTL |
|----------|---------------|-----------------|
| **Granularity** | Tất cả messages cùng TTL | Mỗi message TTL khác | 
| **Performance** | Tốt hơn — broker optimize | Kém hơn — check mỗi message |
| **Expire accuracy** | Chính xác — FIFO order | Không chính xác — chỉ check đầu queue |
| **Use case** | Notification timeout, session expire | Delayed retry, exponential backoff |
| **Setup** | Queue argument | Message property |

**Recommendation:** Dùng per-queue TTL khi tất cả messages cùng timeout. Dùng per-message TTL khi cần flexibility (retry với backoff khác nhau).

---

### 4.3 Retry Strategy — Xử lý Lỗi Tái sử dụng

#### WHY — nack(requeue=true) không phải retry strategy

```
❌ Naive retry: nack(requeue=true)
  Message lỗi → requeue → nhận lại NGAY LẬP TỨC → lỗi lại → requeue → ...
  
  Vấn đề:
  1. Infinite loop nếu lỗi permanent
  2. CPU 100% xử lý cùng 1 message
  3. Block messages khác trong queue
  4. Retry ngay → downstream service vẫn đang lỗi
```

#### WHAT — Retry Strategy Levels

```
Level 0: No retry (fire-and-forget)
  ├── Message lỗi → nack(requeue=false) → mất
  └── Use case: logs, metrics

Level 1: Immediate retry (nack requeue)
  ├── Message lỗi → nack(requeue=true) → retry ngay
  ├── Giới hạn bằng delivery count  
  └── Use case: transient errors (DB connection đứt 1 giây)

Level 2: Delayed retry (DLX + TTL)
  ├── Message lỗi → publish vào retry queue (TTL=30s) → expire → DLX → main queue
  ├── Đợi trước khi retry → downstream service có thời gian recover
  └── Use case: external API timeout, rate limiting

Level 3: Exponential backoff (multiple retry queues)
  ├── Retry 1: 5s delay → Retry 2: 30s delay → Retry 3: 300s delay → DLQ
  ├── Tăng delay mỗi lần retry → tránh thundering herd
  └── Use case: payment gateway, 3rd party API calls

Level 4: DLQ + manual replay
  ├── Sau max retries → message vào DLQ
  ├── Human/automated review → fix root cause → replay từ DLQ
  └── Use case: financial transactions, critical business events
```

#### HOW — Delayed Retry với DLX + TTL

**Pattern: Main Queue → Retry Queue (TTL) → DLX → Main Queue**

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
Publisher ──> [Exchange] ──> [Queue: orders.process]            │
                                     │                         │
                                Consumer                       │
                                ├── ack → ✅                    │
                                └── error → publish to retry ──┘
                                              │
                              [Queue: orders.retry.30s]
                              (x-message-ttl: 30000)
                              (x-dead-letter-exchange → orders.exchange)
                                              │
                                         TTL expires
                                              │
                                    ──> [orders.exchange] ──> [orders.process]
                                              (retry!)
```

**Exponential Backoff — Multiple Retry Queues:**

```
orders.process → lỗi → orders.retry.5s   (TTL=5s)   → retry 1
                      → orders.retry.30s  (TTL=30s)  → retry 2
                      → orders.retry.300s (TTL=300s) → retry 3
                      → orders.dead-letter            → DLQ (max retries reached)

Mỗi retry queue:
  - x-message-ttl: delay tương ứng
  - x-dead-letter-exchange: orders.exchange (route lại main queue)
  - x-dead-letter-routing-key: orders.process
```

#### Flow chi tiết:

```
Retry attempt tracking bằng header x-retry-count:

Message arrives at consumer:
  1. Check header x-retry-count (default 0)
  2. Nếu x-retry-count >= MAX_RETRIES → nack(requeue=false) → DLQ
  3. Nếu error transient:
     a. Tăng x-retry-count
     b. Tính delay = backoff(x-retry-count)
     c. Publish message vào retry queue có TTL = delay
     d. Ack message gốc (đã chuyển sang retry queue)
  4. Nếu error permanent (parse error, validation) → nack(requeue=false) → DLQ
```

---

### 4.4 Poison Message Handling — Detect và Quarantine

#### WHY — Poison messages phá hủy hệ thống

Poison message là message mà consumer **không bao giờ** xử lý được:
- Malformed JSON/protobuf
- Schema mismatch (field thiếu hoặc sai type)
- Business logic impossible (order ID không tồn tại, amount âm)
- Size quá lớn → OOM khi deserialize

```
Poison message không có handling:
  Message arrive → crash consumer → restart → nhận lại → crash → restart → ...
  
  Hậu quả:
  - Consumer restart loop → downtime
  - Messages khác bị block
  - Alert fatigue từ monitoring
  - Toàn bộ pipeline bị stuck
```

#### WHAT — Poison Message Strategy

```
Message arrives at consumer:
  │
  ├── Deserialize OK?
  │     NO → PERMANENT ERROR → nack(requeue=false) → DLQ
  │     YES ↓
  │
  ├── Business validation OK?
  │     NO → PERMANENT ERROR → nack(requeue=false) → DLQ  
  │     YES ↓
  │
  ├── Process OK?
  │     YES → ack ✅
  │     NO ↓
  │
  ├── Error transient? (timeout, connection refused, rate limit)
  │     YES → Retry (exponential backoff)
  │     NO → PERMANENT ERROR → nack(requeue=false) → DLQ
  │
  └── Max retries reached?
        YES → nack(requeue=false) → DLQ
        NO → Retry next level
```

#### HOW — Quorum Queue x-delivery-limit

Quorum queues (Day 6) có built-in delivery limit tracking:

```go
ch.QueueDeclare("orders.process", true, false, false, false, amqp.Table{
    "x-queue-type":              "quorum",
    "x-delivery-limit":          5,               // Max 5 deliveries
    "x-dead-letter-exchange":    "orders.dlx",    // OK as queue arg, nhưng policy dễ vận hành hơn
})
```

Sau 5 lần delivery (bao gồm nack requeue), quorum queue tự động route message đến DLX. Không cần code retry logic ở consumer.

**Production policy cho quorum DLX at-least-once:**

```bash
rabbitmqctl set_policy qq-dlx "^orders\." \
  '{"dead-letter-exchange":"orders.dlx","dead-letter-strategy":"at-least-once","overflow":"reject-publish","delivery-limit":5}' \
  --apply-to quorum_queues
```

`dead-letter-strategy=at-least-once` nên được quản bằng policy để đổi được mà không redeclare queue. Điều kiện quan trọng: dùng `overflow=reject-publish`; nếu để default `drop-head`, quorum queue sẽ rơi về at-most-once dead-lettering.

**Overflow behavior và DLX:**

| Overflow | Khi queue đầy | Publisher thấy gì | DLX impact |
|----------|---------------|-------------------|------------|
| `drop-head` | Xóa message cũ ở đầu queue để nhận message mới | Publish có thể vẫn thành công | Message bị drop/dead-letter theo kiểu at-most-once; không phù hợp nếu DLX phải chắc chắn |
| `reject-publish` | Từ chối publish mới khi vượt limit | Publish bị nack/return tùy confirm/mandatory | Bắt buộc cho quorum at-least-once DLX; queue có thể overshoot nhẹ vì in-flight publishes |

**Classic queue vs Quorum queue — Retry handling:**

| Feature | Classic Queue | Quorum Queue |
|---------|-------------|-------------|
| **Delivery count tracking** | Phải tự implement (header) | Built-in (x-delivery-count) |
| **Auto dead-letter sau N retries** | Không — phải tự check | Có — x-delivery-limit |
| **DLX strategy** | at-most-once | at-least-once (configurable) |
| **Recommendation** | Cần code retry logic | Dùng x-delivery-limit cho đơn giản |

---

### 4.5 Priority Queue (Should Learn)

#### WHY — Khi nào cần Priority?

Hệ thống xử lý orders: VIP customers cần xử lý trước regular customers. Nếu queue đang có 1000 orders, VIP order mới nên "chen hàng" lên trước.

#### WHAT — Priority Queue Setup

```go
ch.QueueDeclare("orders.priority", true, false, false, false, amqp.Table{
    "x-max-priority": 10, // Priority range: 0-10 (0 = lowest)
})

// Publish high-priority message
ch.PublishWithContext(ctx, "", "orders.priority", false, false,
    amqp.Publishing{
        Priority: 8, // High priority
        Body:     vipOrderPayload,
    },
)

// Publish normal-priority message
ch.PublishWithContext(ctx, "", "orders.priority", false, false,
    amqp.Publishing{
        Priority: 1, // Low priority
        Body:     normalOrderPayload,
    },
)
```

#### Trade-offs và Limitations

| Tiêu chí | Priority Queue | Separate Queues |
|----------|---------------|-----------------|
| **Simplicity** | 1 queue, priority header | N queues (vip_orders, normal_orders) |
| **Ordering** | Approximate — không strict FIFO | Strict within each queue |
| **Performance** | Overhead ~15-20% (heap sort) | Không overhead |
| **Quorum queue support** | ❌ Không hỗ trợ | ✅ Mỗi queue có thể quorum |
| **Consumer control** | 1 consumer pool | Separate consumer pools, tunable |
| **Recommendation** | Chỉ khi cần >3 priority levels | **Production preferred** |

**Production recommendation:** Dùng **separate queues** thay vì priority queues cho hầu hết use cases. Lý do:
- Priority queues chỉ classic (không quorum)
- Performance overhead
- Khó predict behavior khi queue đầy
- Separate queues cho nhiều control hơn (scale consumers riêng)

---

### 4.6 RPC Pattern — Request-Reply qua RabbitMQ (Deep Dive / Exercise)

#### WHY — Khi nào dùng RPC qua message broker?

Đôi khi bạn cần **synchronous-like** behavior qua async messaging:
- Backend cần kết quả tính toán từ worker (PDF generation → return file URL)
- Service A cần data từ Service B nhưng communication phải qua RabbitMQ (security, decoupling)

#### WHAT — RPC Flow

```
Client                                          Server
  │                                                │
  │── publish request ──> [Exchange] ──> [rpc_queue] ──> Server receives
  │   (correlation_id: "req-123",                     │
  │    reply_to: "amq.rabbitmq.reply-to")            │
  │                                                   │── process request
  │                                                   │
  │<── response ──── [Default Exchange] ──────────────│   
  │   (correlation_id: "req-123")          publish to reply_to queue
  │
  │── match correlation_id → got response!
```

**Cơ chế:**
1. Client tạo **exclusive, auto-delete** reply queue (hoặc dùng Direct Reply-to)
2. Client publish request với `reply_to` = reply queue name, `correlation_id` = unique ID
3. Server consume request, xử lý, publish response đến `reply_to` queue với cùng `correlation_id`
4. Client consume reply queue, match `correlation_id` → nhận response

#### Trade-off: RPC qua RabbitMQ vs Direct HTTP/gRPC

| Tiêu chí | RPC qua RabbitMQ | Direct HTTP/gRPC |
|----------|-----------------|-----------------|
| **Latency** | ~5-20ms (qua broker) | ~1-5ms (direct) |
| **Decoupling** | Cao — client/server chỉ biết queue | Thấp — client biết server address |
| **Load balancing** | Built-in (competing consumers) | Cần service discovery + LB |
| **Reliability** | Message persist, retry | Connection phải active |
| **Timeout handling** | Phức tạp (TTL + correlation tracking) | Đơn giản (context timeout) |
| **Recommendation** | Khi đã có RabbitMQ, cần decouple | Mặc định cho sync calls |

**Production recommendation:** Tránh RPC qua RabbitMQ trừ khi có lý do cụ thể. HTTP/gRPC đơn giản và nhanh hơn cho synchronous requests. RabbitMQ shine cho **asynchronous** patterns.

---

### 4.7 Delayed Message Exchange Plugin (Deep Dive / Exercise)

#### WHY — Tại sao cần Delayed Exchange?

Retry pattern với TTL queues hoạt động nhưng phức tạp: cần tạo nhiều retry queues cho mỗi delay level. Delayed Message Exchange plugin cho phép **delay trực tiếp** tại exchange level.

#### WHAT

```
Publisher ──publish(x-delay: 30000)──> [Delayed Exchange]
                                            │
                                       Wait 30 seconds...
                                            │
                                       [Queue] ──> Consumer
```

#### HOW — Enable Plugin

```bash
# Enable plugin trong Docker
docker exec rabbitmq rabbitmq-plugins enable rabbitmq_delayed_message_exchange
```

```go
// Declare delayed exchange
ch.ExchangeDeclare("orders.delayed", "x-delayed-message", true, false, false, false,
    amqp.Table{
        "x-delayed-type": "direct", // Underlying exchange type
    },
)

// Publish with delay
ch.PublishWithContext(ctx, "orders.delayed", "orders.retry", false, false,
    amqp.Publishing{
        Headers: amqp.Table{
            "x-delay": 30000, // 30 giây delay
        },
        Body: payload,
    },
)
```

**Limitations:**
- Plugin không shipped default — phải install riêng
- Delayed messages lưu trong Mnesia (disk-based) — không replicate tốt với clustering
- Performance: ~10,000 delayed msg/s (thấp hơn normal exchange)
- Không recommend cho high-throughput retry — dùng TTL queues thay

---

## 5. Trade-off Analysis

### Retry Strategy Decision Matrix

| Strategy | Delay | Complexity | Throughput | Use Case |
|----------|-------|-----------|------------|----------|
| **nack(requeue=true)** | 0 ms | Rất thấp | Cao | Transient error, retry ngay (1-2 lần) |
| **Single retry queue (TTL)** | Cố định | Thấp | Cao | Fixed delay retry |
| **Multi-level retry (TTL)** | Exponential | Trung bình | Cao | Production retry with backoff |
| **Delayed Exchange plugin** | Arbitrary | Thấp | Trung bình | Flexible delay, low volume |
| **Quorum x-delivery-limit** | 0 ms (requeue) | Rất thấp | Cao | Simple max retry count |

### Error Type → Action Matrix

| Error Type | Examples | Action | Retry? |
|-----------|---------|--------|--------|
| **Parse error** | Invalid JSON, wrong encoding | nack(requeue=false) → DLQ | ❌ Never retry |
| **Validation error** | Missing field, invalid amount | nack(requeue=false) → DLQ | ❌ Never retry |
| **Transient error** | DB timeout, connection reset | Delayed retry (backoff) | ✅ Max 3-5 times |
| **Rate limit** | 429 Too Many Requests | Delayed retry (longer delay) | ✅ With increasing delay |
| **Downstream unavailable** | Service B down | Delayed retry (long backoff) | ✅ Max 5-10 times |
| **Unknown error** | Unexpected exception | Delayed retry (1-2 times) → DLQ | ✅ Limited |

### DLQ Processing Strategies

```
DLQ messages — cần xử lý, không phải để mãi:

Strategy 1: Manual Review (recommended cho critical data)
  - Alert team khi DLQ depth > 0
  - Human review → fix root cause → replay messages
  - Dùng cho: payments, orders

Strategy 2: Automated Replay (cho high-volume non-critical)
  - Scheduled job đọc DLQ → retry sau N giờ
  - Nếu vẫn fail → alert
  - Dùng cho: notifications, analytics events

Strategy 3: Discard with Logging (cho disposable data)
  - Consumer trên DLQ: log message details → discard
  - Metrics: đếm discarded messages per-type
  - Dùng cho: metrics, telemetry
```

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Mọi production queue nên có DLX**
   ```go
   // ✅ Template cho production queue
   ch.QueueDeclare("service.action", true, false, false, false, amqp.Table{
       "x-dead-letter-exchange":    "service.dlx",
       "x-dead-letter-routing-key": "service.action.dead",
   })
   ```

2. **Phân loại errors trước khi quyết định retry**
   ```go
   func handleMessage(msg amqp.Delivery) {
       err := process(msg)
       if err == nil {
           msg.Ack(false)
           return
       }
       
       if isPermanentError(err) {
           // Parse errors, validation errors → DLQ ngay
           msg.Nack(false, false)
           return
       }
       
       // Transient errors → retry với delay
       retryWithBackoff(msg, err)
   }
   
   func isPermanentError(err error) bool {
       // Errors KHÔNG BAO GIỜ tự khỏi
       var parseErr *json.SyntaxError
       var validErr *ValidationError
       return errors.As(err, &parseErr) || errors.As(err, &validErr)
   }
   ```

3. **Luôn set max retry count**
   - Không có max → infinite retry (chậm hơn infinite loop nhưng vẫn waste resources)
   - Recommendation: 3-5 lần cho API calls, 5-10 cho infrastructure issues

4. **Monitor DLQ depth — KHÔNG BAO GIỜ để DLQ tích lũy mà không alert**
   ```
   Alert rules:
   - DLQ depth > 0 → Warning (investigate)
   - DLQ depth > 100 → Critical (systematic issue)
   - DLQ growth rate > 10/min → Critical (something broken)
   ```

5. **Dùng MessageId cho idempotent retry**
   ```go
   // Publisher set unique MessageId
   amqp.Publishing{
       MessageId: uuid.New().String(),
       Body:      payload,
   }
   
   // Consumer deduplicate bằng MessageId
   // Dùng Redis SET hoặc DB unique constraint
   if isProcessed(msg.MessageId) {
       msg.Ack(false) // Already processed, skip
       return
   }
   ```

6. **Log đầy đủ khi dead-letter**
   ```go
   if isMaxRetry(msg) {
       log.Printf("MAX_RETRY_REACHED: message_id=%s, queue=%s, retries=%d, last_error=%v",
           msg.MessageId, msg.RoutingKey, getRetryCount(msg), lastErr)
       msg.Nack(false, false) // → DLQ
   }
   ```

### Common Pitfalls

1. **Pitfall: nack(requeue=true) cho tất cả errors**
   ```
   ❌ Any error → nack(requeue=true) → infinite loop cho permanent errors
   
   ✅ Classify: transient → delayed retry (max N times)
                permanent → nack(requeue=false) → DLQ
   ```

2. **Pitfall: TTL per-message ordering surprise**
   ```
   Queue: [msg1 TTL=60s] [msg2 TTL=5s] [msg3 TTL=60s]
   
   ❌ Expected: msg2 expire trước (TTL ngắn hơn)
   ✅ Actual: msg1 ở đầu queue, msg2 expire nhưng CHƯA bị remove 
             cho đến khi msg1 được consume hoặc expire
   
   Fix: Dùng per-queue TTL (cùng TTL) hoặc separate queue per TTL level
   ```

3. **Pitfall: DLQ không có consumer**
   ```
   ❌ Setup DLX/DLQ nhưng không ai consume DLQ
      → DLQ tích lũy messages mãi → disk full → broker crash
   
   ✅ Luôn có:
      - Consumer trên DLQ (log, alert, forward)
      - TTL trên DLQ (auto-expire sau 30 ngày)
      - Monitor DLQ depth
   ```

4. **Pitfall: Retry gây thundering herd**
   ```
   1000 messages fail cùng lúc → tất cả retry sau 30s → 1000 messages hit service cùng lúc
   
   Fix: Add jitter vào delay
   delay = baseDelay * 2^attempt + random(0, baseDelay)
   ```

5. **Pitfall: Ack message gốc trước khi publish retry thành công**
   ```go
   // ❌ Ack trước, publish retry sau → nếu publish fail = message mất
   msg.Ack(false)
   ch.PublishWithContext(ctx, retryExchange, ...) // Nếu fail ở đây?
   
   // ✅ Publish retry trước (với confirm), rồi mới ack message gốc
   err := ch.PublishWithContext(ctx, retryExchange, ...)
   if err != nil {
       msg.Nack(false, true) // Requeue — giữ message an toàn
       return
   }
   msg.Ack(false) // Giờ mới ack
   ```

---

## 7. Performance Considerations

### Retry Queue Performance Impact

```
Benchmark: 1KB messages, single node

Normal flow (no retry):        ~45,000 msg/s
With DLX configured:           ~44,000 msg/s  (-2% — DLX setup overhead minimal)
Actual dead-lettering:         ~20,000 msg/s  (message copy + route lại)
Delayed retry (TTL queue):     ~15,000 msg/s  (TTL check + dead-letter + reroute)
Delayed Exchange plugin:       ~10,000 msg/s  (Mnesia disk-based scheduling)
```

### DLQ Sizing

| Scenario | DLQ Growth Rate | Action |
|----------|----------------|--------|
| Healthy system | 0-5 msg/day | Normal — review weekly |
| Intermittent issues | 10-100 msg/day | Monitor — check error types |
| Systematic failure | >100 msg/hour | **Alert — fix root cause ngay** |
| Downstream outage | All messages → DLQ | **Critical — stop consuming, fix downstream** |

### Memory Impact của Retry Queues

```
Retry topology: main + 3 retry + 1 DLQ = 5 queues per service

10 microservices × 5 queues = 50 queues
Memory overhead: 50 × ~30KB (empty queue) = ~1.5MB (negligible)

Nhưng: Retry queues đầy messages khi có incident:
  1000 messages × 3 retry queues × 1KB = ~3MB (vẫn nhỏ)
  1M messages × 3 retry queues × 1KB = ~3GB (cần SSD, monitor disk)
```

### Key Metrics cho Retry Monitoring

| Metric | Ý nghĩa | Alert |
|--------|---------|-------|
| `retry_queue_depth` | Messages đang chờ retry | > 1000 → investigate |
| `dlq_depth` | Messages failed permanently | > 0 → warning |
| `dlq_growth_rate` | Tốc độ DLQ tăng | > 10/min → critical |
| `retry_success_rate` | % messages retry thành công | < 50% → retry không hiệu quả |
| `avg_retry_count` | Trung bình bao nhiêu retry trước khi thành công | > 3 → downstream unhealthy |

---

## 8. Hands-on Lab

### 8.1 Setup

```bash
# Đảm bảo RabbitMQ đang chạy từ Day 4
docker compose up -d

# Tạo thư mục lab
mkdir -p day-07-advanced-patterns/lab && cd day-07-advanced-patterns/lab
go mod init advanced-patterns-lab
go get github.com/rabbitmq/amqp091-go
go get github.com/google/uuid
```

### 8.2 Lab 1: DLX + TTL — Retry Pipeline

**File `retry_pipeline.go`:**
```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/google/uuid"
	amqp "github.com/rabbitmq/amqp091-go"
)

const (
	mainExchange  = "orders"
	mainQueue     = "orders.process"
	retryExchange = "orders.retry"
	dlxExchange   = "orders.dlx"
	dlqQueue      = "orders.dead-letter"
	maxRetries    = 3
)

var retryDelays = []int{5000, 15000, 60000} // 5s, 15s, 60s

type Order struct {
	OrderID string  `json:"order_id"`
	UserID  string  `json:"user_id"`
	Amount  float64 `json:"amount"`
	Item    string  `json:"item"`
}

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	mode := "demo"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	switch mode {
	case "setup":
		setupTopology(conn)
	case "publish":
		publishOrders(conn)
	case "consume":
		consumeOrders(conn)
	case "dlq":
		consumeDLQ(conn)
	default:
		setupTopology(conn)
		go consumeDLQ(conn)
		go consumeOrders(conn)
		time.Sleep(500 * time.Millisecond)
		publishOrders(conn)
		time.Sleep(90 * time.Second) // Wait for retries to complete
	}
}

func setupTopology(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	// Main exchange và queue
	ch.ExchangeDeclare(mainExchange, "direct", true, false, false, false, nil)

	// DLX — nơi nhận messages hết retry
	ch.ExchangeDeclare(dlxExchange, "fanout", true, false, false, false, nil)
	ch.QueueDeclare(dlqQueue, true, false, false, false, amqp.Table{
		"x-message-ttl": int64(30 * 24 * 60 * 60 * 1000), // DLQ TTL: 30 ngày; int32 sẽ overflow
	})
	ch.QueueBind(dlqQueue, "", dlxExchange, false, nil)

	// Main queue — messages bị nack(requeue=false) đến DLX
	ch.QueueDeclare(mainQueue, true, false, false, false, amqp.Table{
		"x-dead-letter-exchange": dlxExchange,
	})
	ch.QueueBind(mainQueue, "order.process", mainExchange, false, nil)

	// Retry exchange — nhận retry messages, route lại main queue
	ch.ExchangeDeclare(retryExchange, "direct", true, false, false, false, nil)

	// Tạo retry queues với TTL tăng dần
	for i, delay := range retryDelays {
		retryQueue := fmt.Sprintf("orders.retry.%d", i+1)
		ch.QueueDeclare(retryQueue, true, false, false, false, amqp.Table{
			"x-message-ttl":             int64(delay),
			"x-dead-letter-exchange":    mainExchange,
			"x-dead-letter-routing-key": "order.process",
		})
		ch.QueueBind(retryQueue, fmt.Sprintf("retry.%d", i+1), retryExchange, false, nil)
		log.Printf("Retry queue created: %s (TTL: %dms)", retryQueue, delay)
	}

	log.Println("Topology setup complete!")
	log.Println("Flow: orders.process → retry.1 (5s) → retry.2 (15s) → retry.3 (60s) → DLQ")
}

func publishOrders(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Confirm(false)
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 10))
	ctx := context.Background()

	orders := []Order{
		{"ORD-001", "user-1", 99.99, "laptop"},       // Success
		{"ORD-002", "user-2", 49.99, "headphones"},    // Transient error → retry → success
		{"ORD-003", "user-3", -10.00, "invalid"},      // Permanent error → DLQ immediately
		{"ORD-004", "user-4", 199.99, "always-fails"}, // Always fails → exhaust retries → DLQ
		{"ORD-005", "user-5", 29.99, "mouse"},         // Success
	}

	for _, order := range orders {
		body, _ := json.Marshal(order)
		err := ch.PublishWithContext(ctx, mainExchange, "order.process", false, false,
			amqp.Publishing{
				DeliveryMode:  amqp.Persistent,
				ContentType:   "application/json",
				MessageId:     uuid.New().String(),
				CorrelationId: order.OrderID,
				Timestamp:     time.Now(),
				Body:          body,
			},
		)
		if err != nil {
			log.Printf("Publish failed: %s — %v", order.OrderID, err)
			continue
		}

		confirmed := <-confirms
		if confirmed.Ack {
			log.Printf("PUBLISHED: %s ($%.2f, item=%s)", order.OrderID, order.Amount, order.Item)
		}
	}
}

func consumeOrders(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	// Separate channel cho retry publish
	retryCh, _ := conn.Channel()
	defer retryCh.Close()
	retryCh.Confirm(false)
	retryConfirms := retryCh.NotifyPublish(make(chan amqp.Confirmation, 10))

	ch.Qos(5, 0, false)
	msgs, _ := ch.Consume(mainQueue, "order-processor", false, false, false, false, nil)

	log.Printf("Order processor started (queue: %s, max_retries: %d)", mainQueue, maxRetries)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var order Order
			if err := json.Unmarshal(msg.Body, &order); err != nil {
				log.Printf("PERMANENT_ERROR: bad JSON — sending to DLQ: %v", err)
				msg.Nack(false, false) // → DLQ
				continue
			}

			retryCount := getRetryCount(msg)
			log.Printf("PROCESSING: %s (attempt %d/%d, amount=$%.2f)",
				order.OrderID, retryCount+1, maxRetries+1, order.Amount)

			// Permanent error: invalid data → DLQ immediately
			if order.Amount <= 0 {
				log.Printf("PERMANENT_ERROR: %s — invalid amount $%.2f → DLQ",
					order.OrderID, order.Amount)
				msg.Nack(false, false) // → DLQ
				continue
			}

			// Simulate processing
			err := processOrder(order, retryCount)
			if err == nil {
				msg.Ack(false)
				log.Printf("SUCCESS: %s processed", order.OrderID)
				continue
			}

			// Transient error — retry with backoff
			if retryCount >= maxRetries {
				log.Printf("MAX_RETRY_REACHED: %s — %d retries exhausted → DLQ",
					order.OrderID, maxRetries)
				msg.Nack(false, false) // → DLQ
				continue
			}

			// Publish to retry queue
			nextRetry := retryCount + 1
			retryRoutingKey := fmt.Sprintf("retry.%d", nextRetry)

			retryHeaders := copyHeaders(msg.Headers)
			retryHeaders["x-retry-count"] = int32(nextRetry)
			retryHeaders["x-original-exchange"] = mainExchange
			retryHeaders["x-original-routing-key"] = msg.RoutingKey
			retryHeaders["x-last-error"] = err.Error()

			pubErr := retryCh.PublishWithContext(context.Background(),
				retryExchange, retryRoutingKey, false, false,
				amqp.Publishing{
					DeliveryMode:  amqp.Persistent,
					ContentType:   msg.ContentType,
					MessageId:     msg.MessageId,
					CorrelationId: msg.CorrelationId,
					Timestamp:     time.Now(),
					Headers:       retryHeaders,
					Body:          msg.Body,
				},
			)
			if pubErr != nil {
				log.Printf("RETRY_PUBLISH_FAILED: %s — requeue original message", order.OrderID)
				msg.Nack(false, true) // Requeue — giữ message an toàn
				continue
			}

			retryConfirm := <-retryConfirms
			if !retryConfirm.Ack {
				log.Printf("RETRY_NACKED: %s — requeue original message", order.OrderID)
				msg.Nack(false, true)
				continue
			}

			delay := retryDelays[nextRetry-1]
			log.Printf("RETRY_SCHEDULED: %s → retry %d (delay=%dms, error=%v)",
				order.OrderID, nextRetry, delay, err)
			msg.Ack(false) // Ack original — đã chuyển sang retry queue
		}
	}()

	<-sig
}

func consumeDLQ(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	ch.Qos(1, 0, false)
	msgs, _ := ch.Consume(dlqQueue, "dlq-processor", false, false, false, false, nil)

	log.Printf("DLQ processor started (queue: %s)", dlqQueue)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var order Order
			json.Unmarshal(msg.Body, &order)

			retryCount := getRetryCount(msg)
			lastError := ""
			if le, ok := msg.Headers["x-last-error"]; ok {
				lastError = le.(string)
			}

			log.Printf("DLQ_RECEIVED: order=%s, retries=%d, last_error=%s, message_id=%s",
				order.OrderID, retryCount, lastError, msg.MessageId)

			// Production: alert team, store for review, expose replay API
			msg.Ack(false)
		}
	}()

	<-sig
}

func processOrder(order Order, retryCount int) error {
	time.Sleep(200 * time.Millisecond) // Simulate processing time

	// ORD-002: fails first 2 times, succeeds on 3rd
	if order.Item == "headphones" && retryCount < 2 {
		return fmt.Errorf("payment gateway timeout (transient)")
	}

	// ORD-004: always fails
	if order.Item == "always-fails" {
		return fmt.Errorf("inventory service unavailable (transient)")
	}

	return nil
}

func getRetryCount(msg amqp.Delivery) int {
	if rc, ok := msg.Headers["x-retry-count"]; ok {
		switch v := rc.(type) {
		case int32:
			return int(v)
		case int64:
			return int(v)
		case int:
			return v
		}
	}
	return 0
}

func copyHeaders(src amqp.Table) amqp.Table {
	dst := amqp.Table{}
	for k, v := range src {
		dst[k] = v
	}
	return dst
}

// Unused but included as reference for jitter-based backoff
func calcBackoffWithJitter(attempt int, baseMs int) int {
	delay := baseMs * (1 << attempt) // Exponential: baseMs * 2^attempt
	jitter := rand.Intn(baseMs)      // Random jitter: 0 to baseMs
	return delay + jitter
}

// Unused helper to parse string expiration to int
func parseExpiration(exp string) int {
	val, _ := strconv.Atoi(exp)
	return val
}
```

```bash
# All-in-one demo
go run retry_pipeline.go

# Hoặc riêng:
go run retry_pipeline.go setup
go run retry_pipeline.go dlq       # Terminal 1
go run retry_pipeline.go consume   # Terminal 2
go run retry_pipeline.go publish   # Terminal 3
```

**Expected output:**

```
Topology setup complete!
Flow: orders.process → retry.1 (5s) → retry.2 (15s) → retry.3 (60s) → DLQ

DLQ processor started (queue: orders.dead-letter)
Order processor started (queue: orders.process, max_retries: 3)

PUBLISHED: ORD-001 ($99.99, item=laptop)
PROCESSING: ORD-001 (attempt 1/4, amount=$99.99)
SUCCESS: ORD-001 processed

PUBLISHED: ORD-002 ($49.99, item=headphones)
PROCESSING: ORD-002 (attempt 1/4, amount=$49.99)
RETRY_SCHEDULED: ORD-002 → retry 1 (delay=5000ms, error=payment gateway timeout)
  ... 5 seconds later ...
PROCESSING: ORD-002 (attempt 2/4, amount=$49.99)
RETRY_SCHEDULED: ORD-002 → retry 2 (delay=15000ms, error=payment gateway timeout)
  ... 15 seconds later ...
PROCESSING: ORD-002 (attempt 3/4, amount=$49.99)
SUCCESS: ORD-002 processed

PUBLISHED: ORD-003 ($-10.00, item=invalid)
PROCESSING: ORD-003 (attempt 1/4, amount=$-10.00)
PERMANENT_ERROR: ORD-003 — invalid amount $-10.00 → DLQ
DLQ_RECEIVED: order=ORD-003, retries=0, last_error=, message_id=...

PUBLISHED: ORD-004 ($199.99, item=always-fails)
PROCESSING: ORD-004 (attempt 1/4, amount=$199.99)
RETRY_SCHEDULED: ORD-004 → retry 1 (delay=5000ms)
  ... retries 2, 3 ...
MAX_RETRY_REACHED: ORD-004 — 3 retries exhausted → DLQ
DLQ_RECEIVED: order=ORD-004, retries=3, last_error=inventory service unavailable

PUBLISHED: ORD-005 ($29.99, item=mouse)
PROCESSING: ORD-005 (attempt 1/4, amount=$29.99)
SUCCESS: ORD-005 processed
```

### 8.3 Lab 2: RPC Pattern (Should Learn)

**File `rpc_demo.go`:**
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

	"github.com/google/uuid"
	amqp "github.com/rabbitmq/amqp091-go"
)

type CalcRequest struct {
	Operation string  `json:"operation"`
	A         float64 `json:"a"`
	B         float64 `json:"b"`
}

type CalcResponse struct {
	Result float64 `json:"result"`
	Error  string  `json:"error,omitempty"`
}

func main() {
	conn, _ := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	defer conn.Close()

	mode := "server"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	switch mode {
	case "server":
		rpcServer(conn)
	case "client":
		rpcClient(conn)
	default:
		go rpcServer(conn)
		time.Sleep(500 * time.Millisecond)
		rpcClient(conn)
	}
}

func rpcServer(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	rpcQueue := "rpc.calculator"
	ch.QueueDeclare(rpcQueue, true, false, false, false, nil)
	ch.Qos(1, 0, false)

	msgs, _ := ch.Consume(rpcQueue, "calc-server", false, false, false, false, nil)
	log.Printf("RPC Server started (queue: %s)", rpcQueue)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var req CalcRequest
			json.Unmarshal(msg.Body, &req)

			log.Printf("RPC_REQUEST: %s — %.2f %s %.2f (correlation: %s)",
				msg.CorrelationId, req.A, req.Operation, req.B)

			resp := calculate(req)
			respBody, _ := json.Marshal(resp)

			// Publish response đến reply-to queue
			ch.PublishWithContext(context.Background(),
				"",          // Default exchange
				msg.ReplyTo, // Reply queue từ client
				false, false,
				amqp.Publishing{
					ContentType:   "application/json",
					CorrelationId: msg.CorrelationId, // Giữ nguyên correlation ID
					Body:          respBody,
				},
			)

			msg.Ack(false)
			log.Printf("RPC_RESPONSE: %s — result=%.2f", msg.CorrelationId, resp.Result)
		}
	}()

	<-sig
}

func rpcClient(conn *amqp.Connection) {
	ch, _ := conn.Channel()
	defer ch.Close()

	// Declare exclusive reply queue — auto-delete khi disconnect
	replyQueue, _ := ch.QueueDeclare("", false, true, true, false, nil)
	replies, _ := ch.Consume(replyQueue.Name, "", true, true, false, false, nil)

	ctx := context.Background()
	requests := []CalcRequest{
		{"add", 10, 20},
		{"multiply", 7, 6},
		{"divide", 100, 3},
		{"divide", 42, 0}, // Error case
	}

	// Track pending requests
	pending := make(map[string]chan CalcResponse)

	// Consume replies in background
	go func() {
		for msg := range replies {
			if ch, ok := pending[msg.CorrelationId]; ok {
				var resp CalcResponse
				json.Unmarshal(msg.Body, &resp)
				ch <- resp
			}
		}
	}()

	for _, req := range requests {
		corrID := uuid.New().String()[:8]
		respCh := make(chan CalcResponse, 1)
		pending[corrID] = respCh

		body, _ := json.Marshal(req)
		ch.PublishWithContext(ctx, "", "rpc.calculator", false, false,
			amqp.Publishing{
				ContentType:   "application/json",
				CorrelationId: corrID,
				ReplyTo:       replyQueue.Name,
				Expiration:    "10000", // 10s timeout
				Body:          body,
			},
		)

		log.Printf("RPC_CALL: %s — %.0f %s %.0f", corrID, req.A, req.Operation, req.B)

		// Wait for response with timeout
		select {
		case resp := <-respCh:
			if resp.Error != "" {
				log.Printf("RPC_ERROR: %s — %s", corrID, resp.Error)
			} else {
				log.Printf("RPC_RESULT: %s — %.4f", corrID, resp.Result)
			}
		case <-time.After(10 * time.Second):
			log.Printf("RPC_TIMEOUT: %s", corrID)
		}
	}
}

func calculate(req CalcRequest) CalcResponse {
	time.Sleep(100 * time.Millisecond) // Simulate work

	switch req.Operation {
	case "add":
		return CalcResponse{Result: req.A + req.B}
	case "subtract":
		return CalcResponse{Result: req.A - req.B}
	case "multiply":
		return CalcResponse{Result: req.A * req.B}
	case "divide":
		if req.B == 0 {
			return CalcResponse{Error: "division by zero"}
		}
		return CalcResponse{Result: req.A / req.B}
	default:
		return CalcResponse{Error: fmt.Sprintf("unknown operation: %s", req.Operation)}
	}
}
```

```bash
# All-in-one
go run rpc_demo.go

# Hoặc riêng:
go run rpc_demo.go server  # Terminal 1
go run rpc_demo.go client  # Terminal 2
```

### 8.4 Lab 3: Monitoring Retry & DLQ

```bash
# Kiểm tra retry queues
for q in orders.retry.1 orders.retry.2 orders.retry.3; do
  echo "=== $q ==="
  curl -s -u admin:admin123 "http://localhost:15672/api/queues/%2F/$q" | jq '{
    name: .name,
    messages: .messages,
    message_ttl: .arguments."x-message-ttl",
    dlx: .arguments."x-dead-letter-exchange"
  }'
done

# Kiểm tra DLQ depth
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/orders.dead-letter | jq '{
  name: .name,
  messages: .messages,
  messages_ready: .messages_ready,
  consumers: .consumers
}'

# Xem messages trong DLQ (peek without consume)
curl -s -u admin:admin123 \
  -H "content-type:application/json" \
  -d '{"count":5,"ackmode":"ack_requeue_true","encoding":"auto"}' \
  http://localhost:15672/api/queues/%2F/orders.dead-letter/get | jq '.[].payload' 
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Message bị dead-letter trong 3 trường hợp nào?** Giải thích từng trường hợp và khi nào chúng xảy ra trong production.

   *Hint: nack(requeue=false), TTL expired, queue overflow (x-max-length). Nghĩ về scenario cho từng case.*

2. **So sánh retry bằng nack(requeue=true) với retry bằng DLX + TTL queue.** Tại sao approach thứ 2 tốt hơn? Có trường hợp nào nack(requeue=true) vẫn phù hợp?

   *Hint: Delay giữa retries, thundering herd, classified errors. nack(requeue=true) OK cho 1-2 immediate retries cho very transient errors.*

3. **Per-message TTL có ordering surprise gì?** Giải thích tại sao message có TTL=5s không expire trước message có TTL=60s nếu msg TTL=60s ở đầu queue.

   *Hint: RabbitMQ chỉ check TTL ở đầu queue (head). Design decision vì check mọi message quá tốn.*

4. **Design question:** Bạn có payment processing service. Khi payment gateway timeout:
   - Retry bao nhiêu lần? Delay mỗi lần?
   - Sau max retries → hành động gì?
   - Làm sao tránh duplicate payment?
   
   *Hint: 3-5 retries, exponential backoff (5s→30s→300s), DLQ + alert + manual review. Idempotency key từ MessageId hoặc payment reference.*

5. **Tại sao PHẢI publish retry message thành công TRƯỚC KHI ack message gốc?** Nếu làm ngược lại (ack trước, publish retry sau) → vấn đề gì xảy ra?

   *Hint: Ack = broker xóa message. Nếu publish retry fail sau ack → message mất vĩnh viễn, không ở main queue, không ở retry queue.*

6. **Poison message khác transient error thế nào?** Cho 3 ví dụ mỗi loại. Tại sao poison message KHÔNG BAO GIỜ nên retry?

   *Hint: Poison = data issue (sẽ luôn fail). Transient = infrastructure issue (sẽ tự khỏi). Retry poison = waste resources.*

7. **RPC qua RabbitMQ vs gRPC direct: khi nào dùng cái nào?** Cho scenario cụ thể cho mỗi approach.

   *Hint: RPC qua broker khi cần decouple, load balance, message persistence. gRPC cho low-latency sync calls.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Dead Letter Exchanges](https://www.rabbitmq.com/dlx.html)
- [TTL (Time-To-Live)](https://www.rabbitmq.com/ttl.html)
- [Priority Queue Support](https://www.rabbitmq.com/priority.html)
- [Direct Reply-to (RPC)](https://www.rabbitmq.com/direct-reply-to.html)
- [Delayed Message Exchange Plugin](https://github.com/rabbitmq/rabbitmq-delayed-message-exchange)

### Architecture & Design
- [RabbitMQ Retry Pattern — CloudAMQP](https://www.cloudamqp.com/blog/when-and-how-to-use-the-rabbitmq-dead-letter-exchange.html)
- [Poison Message Handling — Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/patterns/messaging/InvalidMessageChannel.html)
- [Reliable Microservices with RabbitMQ](https://blog.rabbitmq.com/posts/2022/12/rabbitmq-retry-pitfalls/)

### Deep Dive
- [Exponential Backoff and Jitter — AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [RabbitMQ in Depth — Gavin M. Roy](https://www.manning.com/books/rabbitmq-in-depth) (Chapter 6-7)

### Videos
- [Dead Letter Exchanges Explained — CloudAMQP](https://www.youtube.com/watch?v=B5iFT-MkP6Y)
- [Error Handling in Event-Driven Systems — GOTO Conference](https://www.youtube.com/watch?v=A780gk2g-T8)
