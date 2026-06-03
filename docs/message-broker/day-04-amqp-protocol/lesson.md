# Day 4: AMQP Protocol — Exchange, Queue, Binding, Routing

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu rõ** AMQP 0-9-1 protocol và tại sao RabbitMQ chọn mô hình "smart broker, dumb consumer"
2. **Nắm vững** 4 thành phần cốt lõi: Exchange, Queue, Binding, Routing Key — và cách chúng phối hợp
3. **Phân biệt** Connection vs Channel và tại sao channel multiplexing quan trọng cho performance
4. **Hiểu** consumer acknowledgment model (ack/nack/reject) và hậu quả khi dùng sai
5. **Thực hành** setup RabbitMQ với Docker, publish/consume messages bằng Go

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 1-3 (hiểu messaging fundamentals, queue vs pub/sub vs stream)
- Hiểu TCP connection basics
- Biết Docker và Docker Compose
- Go cơ bản

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- AMQP protocol overview và RabbitMQ architecture
- Exchange, Queue, Binding, Routing Key — 4 building blocks
- Connection vs Channel — multiplexing
- Queue properties: durable, exclusive, auto-delete
- Consumer acknowledgment: auto-ack vs manual ack
- Hands-on: RabbitMQ setup + publish/consume với Go

### 🟡 Should Learn (nếu còn thời gian)
- Virtual hosts (vhosts) — multi-tenancy
- Message properties chi tiết (headers, priority, expiration, content-type)
- Prefetch count cơ bản (deep dive ở Day 9)

### 🟢 Optional Deep Dive
- AMQP 0-9-1 frame format (method frame, header frame, body frame)
- AMQP 1.0 vs 0-9-1 — tại sao RabbitMQ vẫn dùng 0-9-1
- RabbitMQ plugin architecture

---

## 4. Lý thuyết (Theory)

### 4.1 Tại sao RabbitMQ? — Từ NATS sang "Smart Broker"

#### WHY — Vấn đề NATS core không giải quyết được

Ở Day 1-3, bạn đã thấy NATS core cực kỳ nhanh nhưng có giới hạn:
- **Không có routing phức tạp**: NATS dùng subject matching đơn giản (wildcards). Nếu bạn cần route message dựa trên nội dung, header, hoặc logic phức tạp → NATS không đủ
- **Không có built-in retry/DLQ**: Message lỗi ở NATS core bị mất (JetStream có nhưng đơn giản hơn RabbitMQ)
- **Không có priority queue**: Tất cả messages được xử lý bình đẳng

RabbitMQ giải quyết bằng triết lý **"Smart Broker, Dumb Consumer"**:
- Broker (RabbitMQ) chịu trách nhiệm routing, retry, dead-lettering, priority
- Consumer chỉ cần connect, nhận message, ack/nack
- Giống bưu điện thông minh: bạn gửi thư kèm địa chỉ, bưu điện tự phân loại và chuyển đến đúng nơi

#### WHAT — RabbitMQ là gì?

RabbitMQ là message broker implement AMQP 0-9-1 protocol (Advanced Message Queuing Protocol). Nó hoạt động như một trung gian thông minh giữa producers và consumers.

```
Producer                    RabbitMQ                         Consumer
   │                          │                                │
   │── publish message ──────>│                                │
   │   (routing key +         │── route theo binding ──>│Queue│ │
   │    exchange name)        │                        │█████│──> consume
   │                          │                        │█████│ │
   │                          │                                │
```

**So sánh nhanh với NATS:**

| Tiêu chí | NATS Core | RabbitMQ |
|----------|-----------|----------|
| **Triết lý** | Simple, fast | Feature-rich, flexible |
| **Routing** | Subject matching | Exchange + Binding rules |
| **Persistence** | Không (JetStream có) | Có (durable queues) |
| **Delivery** | At-most-once | At-least-once (với ack) |
| **Retry/DLQ** | Không built-in | Built-in DLX, TTL |
| **Protocol** | Text-based, custom | AMQP 0-9-1 (binary) |
| **Throughput** | ~10M msg/s | ~50K msg/s per node |
| **Latency** | ~100μs | ~1ms |
| **Best for** | Service mesh, IoT | Task queues, routing phức tạp |

---

### 4.2 AMQP 0-9-1 Protocol — Bức tranh tổng thể

#### WHY — Tại sao cần protocol chuẩn?

Trước AMQP, mỗi message broker dùng protocol riêng → vendor lock-in. AMQP ra đời để chuẩn hóa cách applications giao tiếp qua message broker, giống HTTP chuẩn hóa web communication.

#### WHAT — AMQP Model

AMQP 0-9-1 định nghĩa một mô hình messaging với 4 thành phần chính:

```
┌─────────────────────────────────────────────────────────────────┐
│                        RabbitMQ Broker                          │
│                                                                 │
│  Publisher ──publish──> [Exchange] ──binding──> [Queue] ──> Consumer
│                            │                     │              │
│                            │    routing key       │              │
│                            │    + binding key      │              │
│                            │    = match?           │              │
│                            └─────────────────────┘              │
│                                                                 │
│  Exchange types: direct, fanout, topic, headers                 │
└─────────────────────────────────────────────────────────────────┘
```

**Flow chi tiết:**

1. **Publisher** gửi message đến **Exchange** (KHÔNG gửi trực tiếp vào Queue)
2. **Exchange** nhận message, dựa vào **routing key** và **binding rules** để quyết định route đến Queue nào
3. **Queue** lưu trữ message cho đến khi RabbitMQ deliver cho Consumer
4. **Consumer** đăng ký bằng `basic.consume`; RabbitMQ **push** message xuống consumer theo giới hạn prefetch, consumer xử lý xong gửi **acknowledgment**

**Analogy — Bưu điện:**
- **Exchange** = Trung tâm phân loại thư
- **Queue** = Hộp thư người nhận
- **Binding** = Quy tắc phân loại (thư gửi đến quận X → hộp thư X)
- **Routing key** = Mã bưu chính trên thư
- **Publisher** = Người gửi thư
- **Consumer** = Người nhận thư

---

### 4.3 Exchange — Trung tâm phân loại

#### WHAT

Exchange là entry point cho mọi message vào RabbitMQ. Publisher KHÔNG BAO GIỜ gửi trực tiếp vào Queue — luôn gửi qua Exchange.

Exchange nhận message và dựa vào **type** + **binding rules** để route:

| Exchange Type | Routing Logic | Use Case |
|--------------|--------------|----------|
| **direct** | Exact match routing key = binding key | Task distribution theo loại |
| **fanout** | Broadcast tất cả — ignore routing key | Event notification, cache invalidation |
| **topic** | Pattern matching (*.logs, audit.#) | Log routing, event filtering linh hoạt |
| **headers** | Match dựa trên message headers | Routing phức tạp theo metadata |

_(Chi tiết từng exchange type sẽ ở Day 5)_

#### Default Exchange

RabbitMQ có một **default exchange** (nameless, type direct) đặc biệt:
- Tên rỗng: `""`
- Mọi queue tự động binding vào default exchange với binding key = tên queue
- Cho phép publish trực tiếp vào queue bằng routing key = tên queue

```
Publisher ──publish(exchange="", routing_key="task_queue")──> [Default Exchange]
                                                                    │
                                                        auto-bind: routing_key = queue_name
                                                                    │
                                                              [task_queue]
```

Đây là lý do nhiều tutorial đơn giản "gửi thẳng vào queue" — thực ra đang dùng default exchange.

---

### 4.4 Queue — Nơi lưu trữ Messages

#### WHAT

Queue là buffer lưu trữ messages theo FIFO (First In, First Out). Messages nằm trong queue cho đến khi RabbitMQ deliver cho consumer và consumer ack.

**FIFO nuance:** FIFO rõ nhất khi có 1 queue, 1 consumer, manual ack tuần tự, không priority, không requeue. Khi có nhiều consumers, `prefetch > 1`, priority queue, TTL, redelivery hoặc `nack(requeue=true)`, thứ tự xử lý thực tế có thể lệch so với thứ tự publish. Vì vậy chỉ dựa vào RabbitMQ FIFO cho task queue đơn giản; nếu cần ordering per entity, thiết kế routing key/queue theo entity hoặc dùng stream/log phù hợp hơn.

#### Queue Properties quan trọng

```go
// Khi declare queue, bạn phải quyết định các properties này:
ch.QueueDeclare(
    "task_queue",  // name
    true,          // durable: queue survive broker restart?
    false,         // autoDelete: xóa queue khi không còn consumer?
    false,         // exclusive: chỉ connection này dùng, xóa khi disconnect?
    false,         // noWait
    nil,           // arguments (TTL, max-length, DLX, v.v.)
)
```

| Property | Giá trị | Ý nghĩa | Khi nào dùng |
|----------|---------|---------|-------------|
| **durable** | `true` | Queue tồn tại sau khi RabbitMQ restart | Production — hầu hết mọi lúc |
| **durable** | `false` | Queue bị xóa khi broker restart | Test, temporary queues |
| **autoDelete** | `true` | Queue tự xóa khi consumer cuối cùng disconnect | Reply queues, temporary |
| **exclusive** | `true` | Chỉ 1 connection dùng, tự xóa khi disconnect | Private reply queue |
| **exclusive** | `false` | Nhiều connections có thể consume | Shared work queue |

**Production rule:**
- Work queues: `durable=true, autoDelete=false, exclusive=false`
- Reply queues (RPC): `durable=false, autoDelete=true, exclusive=true`
- Temporary/debug: `durable=false, autoDelete=true`

#### Queue vs NATS subject

| Tiêu chí | RabbitMQ Queue | NATS Subject |
|----------|---------------|-------------|
| **Lưu trữ** | Có — messages nằm trong queue | Không — fire-and-forget |
| **Competing consumers** | Built-in — round-robin | Cần queue groups |
| **Declare trước** | Có — phải declare queue | Không — subscribe là đủ |
| **Properties** | Rich (durable, TTL, max-length) | Không có |
| **Backpressure** | Queue đầy → block/reject | Slow consumer → drop messages |

---

### 4.5 Binding — Kết nối Exchange và Queue

#### WHAT

Binding là **rule** nối Exchange với Queue, kèm theo **binding key** (routing criteria).

```
[Exchange: orders] ──binding(key="order.created")──> [Queue: new_orders]
                   ──binding(key="order.shipped")──> [Queue: shipping]
                   ──binding(key="order.*")────────> [Queue: order_audit]
```

Một Exchange có thể bind đến nhiều Queues (fan-out). Một Queue có thể nhận bindings từ nhiều Exchanges.

#### Routing Key vs Binding Key

- **Routing key**: Publisher đặt khi publish message (giống địa chỉ trên thư)
- **Binding key**: Đặt khi tạo binding (giống quy tắc phân loại ở bưu điện)
- Exchange so sánh routing key với binding key → match thì route vào queue

```
Publisher publish(exchange="orders", routing_key="order.created", body=...)

Exchange "orders" kiểm tra bindings:
  - binding key "order.created" → Queue "new_orders" ✅ MATCH → route
  - binding key "order.shipped" → Queue "shipping" ❌ NO MATCH
  - binding key "order.*"       → Queue "order_audit" ✅ MATCH → route
```

---

### 4.6 Connection vs Channel — Multiplexing

#### WHY — Tại sao cần Channel?

Mở TCP connection tốn kém:
- TCP handshake: 3-way (~1.5 RTT)
- TLS handshake: thêm ~2 RTT
- AMQP handshake: authentication + tuning
- Memory: mỗi connection ~100KB ở broker side

Nếu mỗi goroutine/thread mở connection riêng → hàng nghìn connections → broker quá tải.

#### WHAT — Channel Multiplexing

**Connection**: 1 TCP connection thực sự đến RabbitMQ broker
**Channel**: Lightweight virtual connection **bên trong** 1 TCP connection

```
Application Process
┌──────────────────────────────────────┐
│  [Connection] ─── 1 TCP connection ──────── RabbitMQ
│      │                                        │
│      ├── [Channel 1] ── publish orders ──────>│
│      ├── [Channel 2] ── consume tasks ──────>│
│      ├── [Channel 3] ── publish logs ────────>│
│      └── [Channel 4] ── RPC replies ────────>│
│                                               │
│  1 Connection, N Channels = hiệu quả         │
└──────────────────────────────────────┘
```

#### HOW — AMQP Multiplexing Protocol

Mỗi AMQP frame có **channel number** → broker biết frame thuộc channel nào trên cùng TCP connection.

```
TCP Connection (1 socket):
┌──────────────────────────────────────────────┐
│ [Ch1: Publish] [Ch2: Consume] [Ch1: Publish] │  ← interleaved frames
│ [Ch3: Declare] [Ch2: Ack]    [Ch1: Publish] │
└──────────────────────────────────────────────┘
```

#### Best Practices cho Connection/Channel

| Quy tắc | Lý do |
|---------|-------|
| **1 Connection per application** (hoặc per process) | Giảm TCP overhead, dễ quản lý |
| **1 Channel per thread/goroutine** | Channels KHÔNG thread-safe |
| **Không share Channel giữa threads** | Race condition, undefined behavior |
| **Đóng Channel khi xong** | Tránh resource leak |
| **Connection pool cho high-throughput** | 2-5 connections, mỗi connection nhiều channels |

**Anti-pattern:**
```
❌ 1 Connection per message (mở/đóng liên tục)
❌ 1 Channel shared giữa nhiều goroutines
❌ 1000 Connections từ 1 application
```

**Production pattern:**
```
✅ 1-5 Connections per application
✅ 1 Channel per goroutine (publish hoặc consume)
✅ Separate connection cho publish vs consume (tránh backpressure ảnh hưởng)
```

---

### 4.7 Consumer Acknowledgment Model

#### WHY — Tại sao cần Ack?

Khi RabbitMQ deliver message cho consumer, có 2 câu hỏi:
1. Consumer đã **nhận** được message chưa? (network level)
2. Consumer đã **xử lý xong** message chưa? (application level)

Nếu broker xóa message ngay sau khi gửi → consumer crash giữa chừng → message mất vĩnh viễn.
Nếu broker giữ message mãi → queue đầy, memory cạn.

Acknowledgment cho phép consumer **báo cho broker** khi nào đã xử lý xong.

#### WHAT — 3 Chế độ Acknowledgment

**1. Auto-Ack (autoAck=true) — Fire and forget**
```
Broker ──deliver message──> Consumer
        (broker xóa ngay)   (có thể crash trước khi xử lý)
```
- Broker xóa message **ngay khi gửi** đến consumer
- Nhanh nhất nhưng **KHÔNG AN TOÀN** — message mất nếu consumer crash
- Dùng cho: logs, metrics, data không quan trọng

**2. Manual Ack (autoAck=false) — Recommended cho production**
```
Broker ──deliver message──> Consumer
        (giữ message)       │
                             ├── xử lý xong
                             └── ack ──> Broker (giờ mới xóa message)
```
- Consumer phải gọi `Ack()` sau khi xử lý xong
- Broker giữ message cho đến khi nhận ack
- Consumer crash → message **requeue** (gửi lại cho consumer khác)

**3. Nack/Reject — Từ chối message**
```
Consumer nhận message → xử lý lỗi → nack(requeue=true)  → message quay lại queue
                                   → nack(requeue=false) → message bị discard hoặc đến DLX
                                   → reject              → giống nack nhưng chỉ 1 message
```

| Action | Hành vi | Khi nào dùng |
|--------|---------|-------------|
| **ack** | Xóa message khỏi queue | Xử lý thành công |
| **nack(requeue=true)** | Đưa message lại queue, gần vị trí cũ nếu có thể | Lỗi tạm thời (DB timeout, network blip) |
| **nack(requeue=false)** | Discard hoặc route đến DLX | Lỗi vĩnh viễn (bad data, parse error) |
| **reject** | Giống nack nhưng chỉ cho 1 message | Legacy — nack linh hoạt hơn |

#### Prefetch Count — Kiểm soát tốc độ delivery

RabbitMQ consumer mặc định là **push-based**: khi app gọi `basic.consume`, broker chủ động gửi deliveries xuống client. `prefetch` là cơ chế flow control ở phía consumer, giới hạn số message đã deliver nhưng chưa ack. API `basic.get` mới là kiểu pull/poll từng message và thường không nên dùng cho hot path production.

```go
// Chỉ gửi tối đa 10 messages cho consumer này trước khi nhận ack
ch.Qos(10, 0, false)
```

- **Prefetch = 1**: Consumer chỉ nhận 1 message, xử lý xong ack rồi mới nhận tiếp → fair dispatch nhưng chậm
- **Prefetch = 10-50**: Balance giữa throughput và fair dispatch → **recommended**
- **Prefetch = 0 (unlimited)**: Broker gửi hết → fast nhưng có thể OOM consumer

```
Prefetch = 1 (fair, chậm):
Queue: [msg5][msg4][msg3][msg2][msg1]
Consumer A: [msg1] ← xử lý xong, ack, nhận msg3
Consumer B: [msg2] ← đang xử lý

Prefetch = unlimited (fast, nguy hiểm):
Queue: []  ← trống!
Consumer A: [msg1][msg2][msg3][msg4][msg5] ← nhận hết, OOM risk
Consumer B: [] ← không nhận gì
```

---

### 4.8 Message Properties

Mỗi AMQP message có **body** (payload) và **properties** (metadata):

```go
amqp.Publishing{
    ContentType:  "application/json",      // MIME type
    DeliveryMode: amqp.Persistent,         // 1=transient, 2=persistent (ghi disk)
    Priority:     0,                       // 0-9 (cần priority queue)
    CorrelationId: "req-123",              // Correlation ID cho RPC/tracing
    ReplyTo:      "amq.rabbitmq.reply-to", // Reply queue cho RPC
    MessageId:    "msg-uuid-456",          // Unique message ID (idempotency)
    Timestamp:    time.Now(),              // Thời điểm publish
    Expiration:   "60000",                 // TTL tính bằng ms (string!)
    Headers: amqp.Table{                   // Custom headers
        "x-retry-count": 0,
        "x-source":      "order-service",
    },
    Body: payload,
}
```

**Properties quan trọng nhất:**
- `DeliveryMode: Persistent` — message ghi vào disk, survive broker restart. **BẮT BUỘC** cho production data
- `ContentType` — giúp consumer biết cách deserialize
- `MessageId` — dùng cho idempotent consumer (Day 7)
- `CorrelationId` — distributed tracing

**Lưu ý:** `DeliveryMode: Persistent` + `durable queue` = message survive restart. Thiếu 1 trong 2 → vẫn mất message khi restart.

**Quan trọng:** durable queue + persistent message chỉ nói rằng broker có thể lưu message bền vững **sau khi broker đã nhận và chấp nhận publish**. Publisher vẫn cần **publisher confirms** để biết RabbitMQ đã nhận responsibility cho message. Nếu publish bị mất giữa network/client/broker mà không chờ confirm, producer có thể tưởng đã gửi thành công trong khi broker chưa lưu.

---

## 5. Trade-off Analysis

### RabbitMQ AMQP Model vs NATS Subject Model

| Tiêu chí | RabbitMQ (AMQP) | NATS |
|----------|----------------|------|
| **Routing flexibility** | Rất cao — 4 exchange types, binding rules | Thấp — subject wildcards only |
| **Setup complexity** | Cao — phải declare exchange, queue, binding | Thấp — subscribe subject là xong |
| **Message durability** | Có — persistent messages + durable queues | Không (core) / Có (JetStream) |
| **Consumer model** | Push-based với prefetch; `basic.get` là polling API | Push-based |
| **Ack model** | Rich — ack/nack/reject + requeue | Đơn giản (JetStream) |
| **Throughput** | ~30-50K msg/s per queue | ~10M msg/s |
| **Latency** | ~1-5ms | ~100μs |
| **Learning curve** | Dốc hơn — nhiều concepts | Thoải mái — ít concepts |
| **Khi nào chọn** | Routing phức tạp, task queues, retry | Simple pub/sub, low latency |

### Auto-Ack vs Manual Ack

| Tiêu chí | Auto-Ack | Manual Ack |
|----------|----------|------------|
| **Throughput** | Cao hơn (~2-5x) | Thấp hơn |
| **Safety** | Message có thể mất | Message an toàn |
| **Complexity** | Đơn giản | Phải handle ack/nack |
| **Memory** | Broker nhẹ (xóa ngay) | Broker giữ message (unacked) |
| **Use case** | Logs, metrics, non-critical | Orders, payments, critical data |
| **Production** | ❌ Hiếm khi dùng | ✅ Mặc định nên dùng |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Luôn dùng manual ack cho production data**
   ```go
   // ✅ Manual ack — consumer kiểm soát khi nào message bị xóa
   msgs, _ := ch.Consume(queue, "", false, false, false, false, nil)
   //                              ↑ autoAck=false
   for msg := range msgs {
       if err := process(msg); err != nil {
           msg.Nack(false, true) // requeue=true → retry
       } else {
           msg.Ack(false)
       }
   }
   ```

2. **Separate connections cho publish và consume**
   - Publish connection bị flow control → không ảnh hưởng consume
   - Consume connection bị backpressure → không ảnh hưởng publish

3. **Luôn declare queue/exchange là durable trong production, và chờ publisher confirms**
   ```go
   // ✅ Durable queue + persistent message + publisher confirm = reliable publish boundary
   ch.QueueDeclare("orders", true, false, false, false, nil)
   ch.Confirm(false)
   ch.Publish("", "orders", false, false, amqp.Publishing{
       DeliveryMode: amqp.Persistent,
       Body:         payload,
   })
   ```
   - `durable` + `persistent` bảo vệ phía broker sau khi message được nhận.
   - Publisher confirm bảo vệ phía producer: app biết broker đã accept hoặc nack publish.

4. **Set prefetch count hợp lý**
   - `prefetch=1` cho tasks nặng (video processing)
   - `prefetch=10-50` cho tasks trung bình (API calls)
   - `prefetch=100+` cho tasks nhẹ (log processing)

5. **Đặt tên queue có ý nghĩa**
   ```
   ✅ order-service.process-payments
   ✅ notification.send-email
   ❌ queue1
   ❌ q
   ```

### Common Pitfalls

1. **Pitfall: Forget to ack → memory leak**
   - Consumer nhận message nhưng không ack → message vẫn "unacked" trong bộ nhớ broker
   - Queue dần đầy → broker OOM
   - Fix: Luôn ack/nack trong mọi code path (kể cả error path)
   ```go
   // ❌ Nếu process() panic → message không bao giờ ack
   process(msg)
   msg.Ack(false)
   
   // ✅ Dùng defer hoặc đảm bảo mọi path có ack/nack
   func handleMsg(msg amqp.Delivery) {
       defer func() {
           if r := recover(); r != nil {
               msg.Nack(false, true)
           }
       }()
       if err := process(msg); err != nil {
           msg.Nack(false, true)
           return
       }
       msg.Ack(false)
   }
   ```

2. **Pitfall: nack(requeue=true) infinite loop**
   - Message lỗi → nack requeue → nhận lại → lỗi lại → nack requeue → vòng lặp vô hạn
   - Fix: Đếm retry count trong header, sau N lần → nack(requeue=false) để đến DLX (Day 7)

3. **Pitfall: Declare queue với properties khác nhau**
   - Queue "orders" đã declare `durable=true`, service khác declare `durable=false` → **ERROR**
   - RabbitMQ không cho thay đổi properties của queue đã tồn tại
   - Fix: Thống nhất queue declaration across services, dùng IaC (Terraform, Ansible)

4. **Pitfall: Quá nhiều connections**
   - Mỗi microservice instance mở 100 connections → 50 instances = 5000 connections
   - RabbitMQ default `max_connections = infinity` nhưng performance giảm >10K
   - Fix: 1-2 connections per process, dùng channels

5. **Pitfall: Publish vào queue name thay vì exchange**
   - Nghĩ RabbitMQ giống Redis LPUSH (publish thẳng vào queue)
   - Thực tế: phải publish vào exchange, exchange route đến queue
   - Default exchange (`""`) che giấu điều này → khi cần routing phức tạp sẽ bối rối

---

## 7. Performance Considerations

### Benchmark Numbers (Order of Magnitude)

| Metric | Giá trị | Điều kiện |
|--------|---------|-----------|
| Throughput (1 queue) | ~30,000-50,000 msg/s | Persistent, 1KB message, manual ack |
| Throughput (auto-ack) | ~100,000+ msg/s | Non-persistent, small messages |
| Throughput (quorum queue) | ~20,000-30,000 msg/s | 3-node cluster |
| Latency (publish → consume) | ~1-5ms | Local, persistent |
| Latency (non-persistent) | ~0.5ms | Local |
| Max connections | ~100,000 | Tuned Erlang VM |
| Max channels per connection | ~65,535 | AMQP protocol limit |
| Max queues | ~50,000 | Trước khi management UI chậm |
| Memory per connection | ~100KB | Erlang process overhead |
| Memory per queue | ~30KB + messages | Empty queue overhead |

### Key Metrics cần Monitor

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| **Queue depth** | < 1000 | 1000-10000 | > 10000 |
| **Unacked messages** | < prefetch * consumers | Tăng dần | Bằng prefetch limit |
| **Consumer utilization** | > 90% | 50-90% | < 50% |
| **Publish rate** | Ổn định | Spike đột ngột | Drop → 0 |
| **Memory usage** | < 60% watermark | 60-80% | > 80% (flow control) |
| **Disk usage** | < 50% | 50-80% | > 80% (alarm) |

### Connection vs Channel — Performance Impact

```
Scenario: 100 concurrent publish operations

❌ 100 TCP connections:
   Memory: 100 x 100KB = 10MB
   TCP overhead: 100 sockets
   TLS overhead: 100 TLS sessions
   
✅ 1 connection + 100 channels:
   Memory: 100KB + 100 x ~5KB = 600KB
   TCP overhead: 1 socket
   TLS overhead: 1 TLS session
```

---

## 8. Hands-on Lab

### 8.1 Setup RabbitMQ với Docker

Tạo thư mục project:
```bash
mkdir -p day-04-amqp-protocol/lab && cd day-04-amqp-protocol/lab
```

Tạo file `docker-compose.yml`:

```yaml
version: "3.8"
services:
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    container_name: rabbitmq
    ports:
      - "5672:5672"     # AMQP protocol
      - "15672:15672"   # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin123
      RABBITMQ_DEFAULT_VHOST: /
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  rabbitmq-data:
```

Khởi động:
```bash
docker compose up -d

# Đợi RabbitMQ ready
docker compose logs -f rabbitmq
# Tìm dòng: "Server startup complete"

# Mở Management UI
# http://localhost:15672
# Login: admin / admin123
```

### 8.2 Khám phá Management UI

Trước khi code, hãy khám phá RabbitMQ Management UI tại `http://localhost:15672`:

1. **Overview**: Tổng quan messages rate, connections, channels
2. **Connections**: Xem TCP connections
3. **Channels**: Xem channels trên mỗi connection
4. **Exchanges**: Các exchanges đã declare (thấy 7 default exchanges)
5. **Queues**: Các queues đã declare

Chú ý 7 default exchanges:
```
(AMQP default)   — type: direct  — default exchange, routing key = queue name
amq.direct        — type: direct
amq.fanout        — type: fanout
amq.headers       — type: headers
amq.match         — type: headers
amq.rabbitmq.trace— type: topic   — internal tracing
amq.topic         — type: topic
```

### 8.3 Lab 1: Simple Publish/Consume với Go

Tạo Go project:
```bash
go mod init rabbitmq-lab
go get github.com/rabbitmq/amqp091-go
```

**File `producer.go`:**
```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Product   string    `json:"product"`
	Quantity  int       `json:"quantity"`
	Total     float64   `json:"total"`
	CreatedAt time.Time `json:"created_at"`
}

func main() {
	// 1. Tạo Connection (1 TCP connection)
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}
	defer conn.Close()
	log.Println("Connected to RabbitMQ")

	// 2. Tạo Channel (virtual connection trên cùng TCP)
	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("Failed to open channel: %v", err)
	}
	defer ch.Close()

	// 3. Declare Queue — idempotent, tạo nếu chưa có
	queueName := "orders.process"
	q, err := ch.QueueDeclare(
		queueName,
		true,  // durable: survive broker restart
		false, // autoDelete
		false, // exclusive
		false, // noWait
		nil,   // arguments
	)
	if err != nil {
		log.Fatalf("Failed to declare queue: %v", err)
	}
	log.Printf("Queue declared: %s (messages: %d, consumers: %d)",
		q.Name, q.Messages, q.Consumers)

	// 4. Bật publisher confirms để producer biết broker đã accept message
	if err := ch.Confirm(false); err != nil {
		log.Fatalf("Failed to enable publisher confirms: %v", err)
	}
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, 1))

	// 5. Publish messages
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	for i := 1; i <= 10; i++ {
		order := OrderEvent{
			OrderID:   fmt.Sprintf("ORD-%03d", i),
			Product:   "laptop",
			Quantity:  i,
			Total:     float64(i) * 999.99,
			CreatedAt: time.Now(),
		}

		body, _ := json.Marshal(order)

		err := ch.PublishWithContext(ctx,
			"",        // exchange: default exchange
			queueName, // routing key: queue name (vì dùng default exchange)
			false,     // mandatory: return message nếu không route được
			false,     // immediate: deprecated in RabbitMQ 3.x
			amqp.Publishing{
				DeliveryMode: amqp.Persistent, // message ghi disk
				ContentType:  "application/json",
				MessageId:    fmt.Sprintf("msg-%s-%d", order.OrderID, time.Now().UnixNano()),
				Timestamp:    time.Now(),
				Body:         body,
			},
		)
		if err != nil {
			log.Printf("Failed to publish %s: %v", order.OrderID, err)
			continue
		}

		select {
		case confirm := <-confirms:
			if !confirm.Ack {
				log.Printf("Broker nack for %s — producer should retry with idempotency key", order.OrderID)
				continue
			}
		case <-ctx.Done():
			log.Printf("Timed out waiting publisher confirm for %s", order.OrderID)
			continue
		}

		log.Printf("Published and confirmed: %s (total: $%.2f)", order.OrderID, order.Total)
		time.Sleep(200 * time.Millisecond)
	}

	log.Println("All orders published")
}
```

**File `consumer.go`:**
```go
package main

import (
	"encoding/json"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Product   string    `json:"product"`
	Quantity  int       `json:"quantity"`
	Total     float64   `json:"total"`
	CreatedAt time.Time `json:"created_at"`
}

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("Failed to open channel: %v", err)
	}
	defer ch.Close()

	queueName := "orders.process"
	_, err = ch.QueueDeclare(queueName, true, false, false, false, nil)
	if err != nil {
		log.Fatalf("Failed to declare queue: %v", err)
	}

	// Prefetch: chỉ gửi 5 messages chưa ack cho consumer này
	err = ch.Qos(5, 0, false)
	if err != nil {
		log.Fatalf("Failed to set QoS: %v", err)
	}

	// Consume với manual ack
	msgs, err := ch.Consume(
		queueName,
		"order-processor-1", // consumer tag — identify consumer trong management UI
		false,               // autoAck=false → manual ack
		false,               // exclusive
		false,               // noLocal
		false,               // noWait
		nil,                 // arguments
	)
	if err != nil {
		log.Fatalf("Failed to register consumer: %v", err)
	}

	log.Printf("Consumer started on queue: %s (prefetch: 5)", queueName)

	// Graceful shutdown
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var order OrderEvent
			if err := json.Unmarshal(msg.Body, &order); err != nil {
				log.Printf("Parse error (rejecting): %v", err)
				// Bad data → reject, không requeue (gửi DLX nếu có)
				msg.Nack(false, false)
				continue
			}

			// Simulate processing
			log.Printf("Processing: %s — %d x %s ($%.2f)",
				order.OrderID, order.Quantity, order.Product, order.Total)
			time.Sleep(500 * time.Millisecond)

			// Simulate occasional failure: order 5 fail lần đầu, retry đúng 1 lần rồi reject.
			// Day 7 sẽ thay phần này bằng retry/DLX có đếm attempt rõ ràng.
			if order.OrderID == "ORD-005" {
				if !msg.Redelivered {
					log.Printf("FAILED: %s — simulated transient error, requeuing once", order.OrderID)
					msg.Nack(false, true) // requeue=true → thử lại một lần
				} else {
					log.Printf("FAILED AGAIN: %s — reject to avoid infinite requeue loop", order.OrderID)
					msg.Nack(false, false) // discard hoặc route đến DLX nếu đã cấu hình
				}
				continue
			}

			// Success → ack
			msg.Ack(false) // multiple=false → chỉ ack message này
			log.Printf("DONE: %s ✓", order.OrderID)
		}
	}()

	<-sig
	log.Println("Shutting down consumer...")
}
```

**Chạy:**
```bash
# Terminal 1 — consumer
go run consumer.go

# Terminal 2 — producer
go run producer.go
```

**Quan sát trên Management UI:**
- Tab **Connections**: thấy 2 connections (producer + consumer)
- Tab **Channels**: thấy 2 channels
- Tab **Queues** → queue `orders.process`:
  - **Ready**: messages chờ delivery
  - **Unacked**: messages đã deliver nhưng chưa ack
  - **Total**: Ready + Unacked
- Chú ý ORD-005 được requeue đúng 1 lần rồi reject để tránh infinite loop. Day 7 sẽ thay bằng DLX/retry queue có attempt counter rõ ràng.

### 8.4 Lab 2: Competing Consumers — Load Balancing

Chạy **2 consumers** đồng thời:

```bash
# Terminal 1 — Consumer A
go run consumer.go
# (sửa consumer tag thành "order-processor-2" nếu muốn phân biệt trên UI)

# Terminal 2 — Consumer B
go run consumer.go

# Terminal 3 — Producer (publish 20 messages)
go run producer.go
```

**Quan sát:**
- 20 messages được phân đều giữa Consumer A và B (round-robin)
- Mỗi message chỉ 1 consumer nhận (competing consumers — giống NATS queue groups)
- `prefetch=5` đảm bảo fair dispatch: consumer chậm không bị "ngập" messages

### 8.5 Lab 3: Connection và Channel — Quan sát trên UI

**File `connection_demo.go`:**
```go
package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	// 1 Connection
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	// Mở 5 channels trên cùng 1 connection
	for i := 1; i <= 5; i++ {
		ch, err := conn.Channel()
		if err != nil {
			log.Fatal(err)
		}

		queueName := fmt.Sprintf("demo-queue-%d", i)
		ch.QueueDeclare(queueName, false, true, false, false, nil)
		log.Printf("Channel %d → Queue: %s", i, queueName)

		_ = ch // giữ channel open
	}

	log.Println("Check Management UI: 1 connection, 5 channels")
	log.Println("http://localhost:15672/#/connections")

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
}
```

```bash
go run connection_demo.go
# Mở http://localhost:15672/#/connections
# Thấy: 1 connection với 5 channels
# Click vào connection → thấy chi tiết 5 channels
```

### 8.6 Lab 4: Monitoring cơ bản qua HTTP API

RabbitMQ Management plugin cung cấp HTTP API:

```bash
# Liệt kê queues
curl -s -u admin:admin123 http://localhost:15672/api/queues | jq '.[].name'

# Chi tiết 1 queue
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F/orders.process | jq '{
  name: .name,
  messages: .messages,
  messages_ready: .messages_ready,
  messages_unacknowledged: .messages_unacknowledged,
  consumers: .consumers,
  message_stats: .message_stats
}'

# Liệt kê connections
curl -s -u admin:admin123 http://localhost:15672/api/connections | jq '.[].name'

# Liệt kê exchanges
curl -s -u admin:admin123 http://localhost:15672/api/exchanges/%2F | jq '.[].name'

# Health check
curl -s -u admin:admin123 http://localhost:15672/api/healthchecks/node | jq .
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Tại sao RabbitMQ bắt buộc publish qua Exchange thay vì trực tiếp vào Queue?** Lợi ích kiến trúc này mang lại là gì? Default exchange có thực sự "gửi thẳng vào queue" không?

   *Hint: Nghĩ về separation of concerns — publisher không nên biết message đến queue nào.*

2. **Connection và Channel khác nhau thế nào? Tại sao không mở 1 Connection cho mỗi operation?** Cho scenario: ứng dụng Go có 50 goroutines cần publish messages — bạn thiết kế Connection/Channel thế nào?

   *Hint: Nghĩ về TCP overhead vs AMQP multiplexing. Channel có thread-safe không?*

3. **So sánh auto-ack và manual ack.** Khi nào auto-ack an toàn? Giải thích vì sao nack(requeue=true) có thể gây infinite loop và cách khắc phục.

   *Hint: Nghĩ về retry count trong message headers.*

4. **Queue declare là idempotent — nghĩa là gì?** Chuyện gì xảy ra nếu 2 services declare cùng queue nhưng properties khác nhau (VD: service A declare durable=true, service B declare durable=false)?

   *Hint: Đây là common pitfall trong microservices. Ai nên "own" queue declaration?*

5. **Bạn có 3 services: OrderService (publish orders), PaymentService (xử lý thanh toán), InventoryService (trừ kho).** Khi order mới tạo, PaymentService cần nhận để thanh toán (competing consumers — chỉ 1 instance xử lý), nhưng InventoryService cũng cần nhận ĐỘC LẬP. Thiết kế exchange/queue/binding nào phù hợp?

   *Hint: Nghĩ về exchange type + nhiều queues. So sánh với NATS queue groups.*

6. **Design question:** `DeliveryMode: Persistent` + `durable: true` + publisher confirms tạo reliability boundary nào? Nếu thiếu publisher confirms, failure nào vẫn có thể làm producer hiểu nhầm là publish thành công? Trade-off performance là gì?

   *Hint: Persistent write = disk I/O; confirm = broker ack cho producer, không liên quan consumer ack.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [AMQP 0-9-1 Model Explained](https://www.rabbitmq.com/tutorials/amqp-concepts.html)
- [RabbitMQ Go Client (amqp091-go)](https://github.com/rabbitmq/amqp091-go)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)

### Architecture & Design
- [RabbitMQ vs Kafka](https://www.cloudamqp.com/blog/when-to-use-rabbitmq-or-apache-kafka.html) — CloudAMQP
- [Connections and Channels](https://www.rabbitmq.com/connections.html)
- [Consumer Acknowledgements](https://www.rabbitmq.com/confirms.html)

### Videos
- [RabbitMQ in 100 Seconds — Fireship](https://www.youtube.com/watch?v=NQ3fZtyXji0)
- [RabbitMQ Crash Course — Hussein Nasser](https://www.youtube.com/watch?v=Cie5v59mrTg)
- [AMQP Protocol Deep Dive — RabbitMQ Summit](https://www.youtube.com/watch?v=FzqjtU2x6YA)
