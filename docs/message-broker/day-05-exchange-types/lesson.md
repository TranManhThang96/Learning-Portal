# Day 5: Exchange Types — Direct, Fanout, Topic, Headers

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** cơ chế routing của 4 exchange types: direct, fanout, topic, headers
2. **Biết chọn** đúng exchange type cho từng use case trong microservices
3. **Thiết kế** được routing topology phức tạp bằng cách kết hợp exchanges và bindings
4. **Thực hành** implement từng exchange type với Go, quan sát routing behavior qua Management UI
5. **So sánh** exchange-based routing (RabbitMQ) với subject-based routing (NATS)

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 4 (hiểu Exchange, Queue, Binding, Routing Key, Connection/Channel)
- Đã có RabbitMQ chạy bằng Docker từ Day 4
- Biết Go cơ bản và `amqp091-go` library

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Direct exchange — exact routing key matching
- Fanout exchange — broadcast to all queues
- Topic exchange — pattern matching với `*` và `#`
- Hands-on: implement cả 3 exchange types với Go
- Decision matrix: chọn exchange type nào cho use case nào

### 🟡 Should Learn (nếu còn thời gian)
- Headers exchange — routing theo message headers
- Exchange-to-exchange binding
- Alternate exchange (unroutable messages)

### 🟢 Optional Deep Dive
- Consistent hash exchange (plugin)
- Custom exchange plugins
- Internal exchanges và tracing

---

## 4. Lý thuyết (Theory)

### 4.1 Direct Exchange — Exact Match Routing

#### WHY — Khi nào cần exact routing?

Bạn có nhiều loại tasks khác nhau, mỗi loại cần worker riêng biệt xử lý. Ví dụ:
- Email notifications → email worker
- SMS notifications → SMS worker
- Push notifications → push worker

Bạn muốn message đến **đúng queue** dựa trên **exact routing key match**.

#### WHAT — Cơ chế hoạt động

Direct exchange so sánh **routing key** của message với **binding key** của mỗi queue. **Exact match** → route vào queue.

```
Publisher ──publish(routing_key="email")──> [Direct Exchange: notifications]
                                                │
                                    ┌───────────┼───────────┐
                                    │           │           │
                              binding:email  binding:sms  binding:push
                                    │           │           │
                              [email_queue] [sms_queue] [push_queue]
                                    │           │           │
                              Email Worker  SMS Worker  Push Worker
```

Routing key `"email"` chỉ match binding key `"email"` → message chỉ đến `email_queue`.

#### HOW — Multiple bindings, same routing key

Một routing key có thể match **nhiều bindings** → message copy đến nhiều queues:

```
Publisher ──publish(routing_key="error")──> [Direct Exchange: logs]
                                                │
                                    ┌───────────┼───────────┐
                                    │           │           │
                              binding:error binding:error binding:info
                                    │           │           │
                              [file_queue] [alert_queue] [archive_queue]
                                    │           │
                                    ✅ MATCH    ✅ MATCH    ❌ NO MATCH
```

Routing key `"error"` match 2 bindings → message đi đến cả `file_queue` và `alert_queue`.

#### Khi nào dùng Direct Exchange?

| ✅ Dùng khi | ❌ KHÔNG dùng khi |
|------------|------------------|
| Route theo loại cụ thể (task type, severity) | Cần broadcast đến tất cả queues |
| Số lượng routing keys ít và biết trước | Routing keys động, không biết trước |
| Competing consumers cho từng loại task | Cần pattern matching linh hoạt |

---

### 4.2 Fanout Exchange — Broadcast

#### WHY — Khi nào cần broadcast?

Khi một event xảy ra và **nhiều services** cần biết, nhưng mỗi service xử lý **độc lập**. Ví dụ:
- Order created → PaymentService xử lý thanh toán, InventoryService trừ kho, NotificationService gửi email, AnalyticsService ghi log
- Cache invalidation → tất cả instances clear cache

Bạn muốn **tất cả queues** đều nhận message, bất kể routing key.

#### WHAT — Cơ chế hoạt động

Fanout exchange **IGNORE routing key** hoàn toàn. Mọi message đều được copy đến **tất cả queues** đã bind.

```
Publisher ──publish(routing_key="anything")──> [Fanout Exchange: order.events]
                                                        │
                                            ┌───────────┼───────────┐
                                            │           │           │
                                      (no binding key needed)       │
                                            │           │           │
                                      [payment_q]  [inventory_q]  [notification_q]
                                            │           │           │
                                      PaymentSvc   InventorySvc  NotificationSvc
```

Routing key `"anything"` (hoặc `""`) — không quan trọng, tất cả queues đều nhận.

#### Fanout vs NATS Pub/Sub

| Tiêu chí | RabbitMQ Fanout | NATS Subject |
|----------|----------------|-------------|
| **Mechanism** | Exchange → tất cả bound queues | Subject → tất cả subscribers |
| **Persistence** | Messages lưu trong queue | Fire-and-forget |
| **Offline consumers** | Queue giữ messages | Messages bị mất |
| **Setup** | Declare exchange + queue + binding | Subscribe subject |
| **Kết quả** | Giống nhau — fan-out | Giống nhau — fan-out |

**Key insight:** Fanout exchange + durable queues = tất cả consumers đều nhận message, kể cả khi offline tạm thời. NATS pub/sub mất message khi subscriber offline.

#### Khi nào dùng Fanout Exchange?

| ✅ Dùng khi | ❌ KHÔNG dùng khi |
|------------|------------------|
| Event notification đến nhiều services | Chỉ 1 service cần nhận |
| Cache invalidation broadcast | Cần filter theo loại event |
| Audit logging (tất cả events) | Chỉ cần subset of events |
| Real-time dashboard updates | High-throughput data pipeline (dùng Kafka) |

---

### 4.3 Topic Exchange — Pattern Matching Routing

#### WHY — Khi nào cần flexible routing?

Direct exchange quá rigid (exact match). Fanout quá broad (broadcast all). Bạn cần middle-ground: **route dựa trên pattern**.

Ví dụ — hệ thống logging:
- Service A muốn nhận tất cả errors: `*.error`
- Service B muốn nhận tất cả events từ order domain: `order.#`
- Service C muốn nhận chính xác order payments: `order.payment.success`

Topic exchange cho phép **wildcard matching** trên routing key.

#### WHAT — Cơ chế routing

Topic exchange dùng routing key dạng **dot-separated words** (giống NATS subjects). Binding key có 2 wildcards:

- `*` (star) — match **đúng 1 word**
- `#` (hash) — match **0 hoặc nhiều words**

```
Routing Key Pattern Examples:
  order.payment.success     — 3 words
  order.inventory.failed    — 3 words
  user.registration         — 2 words
  audit.order.payment.refund — 4 words

Binding Key Wildcards:
  order.*.*         → match: order.payment.success, order.inventory.failed
                     → NOT match: order.payment (chỉ 2 words)
  order.#           → match: order.payment.success, order.inventory.failed,
                              order.payment (bất kỳ số words nào sau "order.")
  *.payment.*       → match: order.payment.success, invoice.payment.failed
  #                 → match TẤT CẢ messages (giống fanout)
```

**Ví dụ phức tạp:**

```
Publisher ──publish(routing_key="order.payment.success")──> [Topic Exchange: events]
                                                                    │
                                                    ┌───────────────┼───────────────┐
                                                    │               │               │
                                              binding:          binding:         binding:
                                              order.#          *.payment.*      order.payment.success
                                                    │               │               │
                                              [order_all_q]   [payment_q]     [payment_ok_q]
                                                    │               │               │
                                              ✅ MATCH         ✅ MATCH        ✅ MATCH
                                              (# matches       (* matches      (exact match)
                                              "payment.        "order",
                                              success")        * matches
                                                               "success")
```

Routing key `"order.payment.success"` match tất cả 3 bindings → message đi đến 3 queues.

#### So sánh Wildcards: RabbitMQ Topic vs NATS

| Feature | RabbitMQ Topic | NATS |
|---------|---------------|------|
| **Separator** | `.` (dot) | `.` (dot) |
| **Single word wildcard** | `*` match đúng 1 word | `*` match đúng 1 token, có thể ở giữa subject |
| **Multi word wildcard** | `#` match 0 hoặc nhiều words | `>` match tail tokens và phải là token cuối |
| **Wildcard position** | `*` và `#` có thể dùng trong binding pattern | `*` có thể ở giữa; `>` chỉ ở cuối |
| **Examples** | `*.payment.*`, `order.#` | `*.payment.*`, `order.>` |
| **Khác biệt quan trọng** | `order.#` match cả `order` | `order.>` không match subject `order`, chỉ match `order.<tail>` |
| **Flexibility** | Linh hoạt hơn cho multi-token wildcard | Tương đương cho single-token wildcard, hạn chế hơn cho tail wildcard |

**Key insight:** Đừng nói NATS không hỗ trợ wildcard ở giữa: `time.*.east` là pattern hợp lệ. Khác biệt chính là RabbitMQ `#` match 0 hoặc nhiều words trong topic binding, còn NATS `>` chỉ dùng ở cuối subject và không match subject cha không có tail.

#### Khi nào dùng Topic Exchange?

| ✅ Dùng khi | ❌ KHÔNG dùng khi |
|------------|------------------|
| Routing phức tạp, có hierarchy | Chỉ cần exact match (dùng direct) |
| Consumer cần filter theo pattern | Cần broadcast all (dùng fanout) |
| Log routing theo severity + source | Routing key đơn giản, không có dots |
| Event-driven microservices | Ultra-high throughput (topic exchange chậm hơn direct ~15-20%) |

---

### 4.4 Headers Exchange — Routing theo Metadata

#### WHY — Khi nào routing key không đủ?

Đôi khi logic routing phụ thuộc vào **nhiều criteria** cùng lúc, mà 1 routing key string không thể biểu diễn được. Ví dụ:
- Route dựa trên format (json/xml) VÀ priority (high/low) VÀ region (us/eu)
- Routing logic không theo hierarchy → topic exchange không phù hợp

#### WHAT — Cơ chế hoạt động

Headers exchange **IGNORE routing key**. Thay vào đó, nó match dựa trên **message headers** với **binding arguments**.

```go
// Khi binding queue, đặt match criteria trong arguments:
ch.QueueBind(
    "high_priority_json",     // queue
    "",                       // routing key — ignored
    "headers_exchange",       // exchange
    false,
    amqp.Table{
        "x-match":  "all",    // "all" = AND (tất cả headers phải match)
                              // "any" = OR (chỉ cần 1 header match)
        "format":   "json",
        "priority": "high",
    },
)
```

```
Publisher publish message với headers:
  format=json, priority=high, region=us

Headers Exchange kiểm tra:
  Queue A (x-match=all, format=json, priority=high) → ✅ MATCH (cả 2 match)
  Queue B (x-match=all, format=xml, priority=high)  → ❌ (format không match)
  Queue C (x-match=any, format=json, region=eu)     → ✅ MATCH (format match, đủ 1)
```

#### Khi nào dùng Headers Exchange?

| ✅ Dùng khi | ❌ KHÔNG dùng khi |
|------------|------------------|
| Routing logic phức tạp, multi-criteria | Routing đơn giản (dùng direct hoặc topic) |
| Routing key không thể biểu diễn logic | Performance quan trọng (headers chậm nhất) |
| Cần AND/OR logic cho routing | Hầu hết mọi trường hợp — headers exchange hiếm dùng |

**Production reality:** Headers exchange hiếm khi dùng trong thực tế. Topic exchange kết hợp với well-designed routing key hierarchy cover 95%+ use cases. Headers exchange chậm hơn đáng kể vì phải parse headers mỗi message.

---

### 4.5 Exchange-to-Exchange Binding (Should Learn)

#### WHY

Trong hệ thống phức tạp, bạn có thể muốn **chain exchanges** — exchange A route đến exchange B, exchange B route đến queues. Điều này cho phép **hierarchical routing**.

```
Publisher ──> [Exchange: all.events (fanout)]
                      │
              ┌───────┼───────┐
              │               │
    [Exchange: order.events   [Exchange: user.events
     (topic)]                  (topic)]
        │                         │
  ┌─────┼─────┐             ┌────┼────┐
  │           │             │         │
[order_q]  [payment_q]  [signup_q] [login_q]
```

- `all.events` (fanout) → broadcast đến tất cả sub-exchanges
- `order.events` (topic) → route chi tiết theo order domain
- `user.events` (topic) → route chi tiết theo user domain

**Lợi ích:**
- Separation of concerns — mỗi domain có exchange riêng
- Publishers chỉ cần biết 1 exchange (top-level)
- Thêm domain mới không ảnh hưởng publishers

#### Anti-pattern: quá nhiều layers

```
❌ Exchange → Exchange → Exchange → Exchange → Queue
   (4 hops = latency cao, debug khó, topology phức tạp)

✅ Exchange → Exchange → Queue
   (2 hops max — đủ flexibility, dễ debug)
```

---

### 4.6 Alternate Exchange (Should Learn)

#### WHY

Khi message không match bất kỳ binding nào → message bị **silently dropped**. Trong production, bạn muốn bắt được unroutable messages để debug.

#### WHAT

Alternate exchange là fallback: nếu message không route được qua exchange chính → route đến alternate exchange.

```go
// Declare exchange với alternate exchange
args := amqp.Table{
    "alternate-exchange": "unrouted-exchange",
}
ch.ExchangeDeclare("orders", "direct", true, false, false, false, args)

// Declare alternate exchange (thường là fanout để bắt tất cả)
ch.ExchangeDeclare("unrouted-exchange", "fanout", true, false, false, false, nil)

// Queue bắt unroutable messages
ch.QueueDeclare("unrouted-messages", true, false, false, false, nil)
ch.QueueBind("unrouted-messages", "", "unrouted-exchange", false, nil)
```

```
Publisher ──publish(routing_key="unknown")──> [Exchange: orders (direct)]
                                                  │
                                          No binding matches!
                                                  │
                                          ┌───────▼────────┐
                                          │ Alternate:      │
                                          │ unrouted-exchange│
                                          │ (fanout)        │
                                          └───────┬────────┘
                                                  │
                                          [unrouted-messages queue]
                                          → Monitor + alert
```

**Best practice:** Dùng alternate exchange cho các exchange mà unroutable message cần audit, alert hoặc replay trong lúc migrate topology. Không phải mọi production exchange đều bắt buộc có alternate exchange; với fire-and-forget metrics/logs hoặc flow đã dùng `mandatory` + publisher returns, bạn có thể chọn strategy khác.

---

## 5. Trade-off Analysis

### Exchange Types Decision Matrix

| Tiêu chí | Direct | Fanout | Topic | Headers |
|----------|--------|--------|-------|---------|
| **Routing logic** | Exact match | Broadcast all | Pattern match | Header match |
| **Performance** | Nhanh nhất | Rất nhanh | Chậm hơn ~15-20% | Chậm nhất |
| **Flexibility** | Thấp | Không routing | Cao | Rất cao |
| **Complexity** | Thấp | Rất thấp | Trung bình | Cao |
| **Use case chính** | Task distribution | Event notification | Event filtering | Multi-criteria routing |
| **Prevalence** | Phổ biến | Phổ biến | Rất phổ biến | Hiếm |

### Routing Key Design — Hierarchy Best Practices

```
Format: {domain}.{entity}.{action}.{detail}

Ví dụ:
  order.payment.completed          — domain.entity.action
  order.payment.failed.timeout     — domain.entity.action.detail
  user.registration.completed      — domain.entity.action
  notification.email.sent          — domain.channel.action
  inventory.stock.updated.warehouse-us — domain.entity.action.detail
```

**Quy tắc:**
1. **Lowercase, dot-separated** — consistency
2. **Nouns trước, verbs sau** — `order.payment.completed` không phải `completed.payment.order`
3. **Specific → general** — dễ match bằng wildcards. `order.#` bắt tất cả order events
4. **Tối đa 4-5 levels** — quá sâu thì routing key quá dài, khó maintain
5. **Past tense cho events** — `order.created` (đã tạo), `payment.completed` (đã hoàn thành)

### Performance Impact của Exchange Types

```
Benchmark minh họa: 1 exchange, 10 bound queues, 1KB messages, persistent, single-node lab, no TLS, client đủ concurrency.

Direct:  ~45,000 msg/s  (baseline)
Fanout:  ~48,000 msg/s  (+7% — không cần match logic)
Topic:   ~38,000 msg/s  (-15% — pattern matching overhead)
Headers: ~32,000 msg/s  (-29% — header parsing overhead)
```

Các số trên chỉ là order of magnitude. Binding count, queue type, disk, publisher confirms, network, TLS và payload size có thể làm kết quả khác đáng kể.

**Recommendation:**
- Mặc định dùng **topic exchange** — flexibility/performance balance tốt nhất
- Dùng **direct** khi routing keys ít và cố định
- Dùng **fanout** khi cần pure broadcast
- **Tránh headers** trừ khi thực sự cần multi-criteria routing

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Mặc định dùng topic exchange cho event-driven microservices**
   - Topic exchange cover hầu hết use cases
   - Khi routing đơn giản: binding key exact match (giống direct)
   - Khi cần broadcast: binding key `#` (giống fanout)
   - Khi cần filter: `order.*`, `*.payment.#`

2. **Thiết kế routing key hierarchy trước khi code**
   ```
   ✅ Quy ước rõ ràng, document trong API spec:
   {domain}.{entity}.{action}
   order.payment.completed
   order.shipment.dispatched
   user.profile.updated
   
   ❌ Ad-hoc, mỗi team đặt khác nhau:
   orderPaymentDone
   SHIPMENT_SENT
   user-updated
   ```

3. **Dùng alternate exchange khi unroutable message cần được giữ lại**
   - Bắt unroutable messages → monitor → alert
   - Debug routing issues nhanh hơn
   - Nếu flow chấp nhận drop hoặc dùng `mandatory` + publisher return, alternate exchange là optional strategy

4. **Tách exchange theo domain/bounded context**
   ```
   ✅ order.events (topic) — tất cả order-related events
   ✅ user.events (topic)  — tất cả user-related events
   ✅ system.events (fanout) — system-wide broadcasts
   
   ❌ Một exchange "events" cho toàn bộ hệ thống
      → quá nhiều bindings, khó maintain
   ```

5. **Document binding topology**
   - Vẽ diagram exchange → queue → consumer
   - Lưu trong repo, update khi thay đổi
   - RabbitMQ Management UI export definitions: `GET /api/definitions`

### Common Pitfalls

1. **Pitfall: Topic exchange wildcard confusion**
   ```
   Routing key: "order.payment.success"
   
   ❌ binding key: "order.payment"     → KHÔNG match (2 words vs 3 words)
   ✅ binding key: "order.payment.*"   → match (3 words, * = "success")
   ✅ binding key: "order.#"           → match (# = "payment.success")
   ❌ binding key: "order.*.*.success" → KHÔNG match (4 words vs 3 words)
   ```
   **Fix:** Nhớ `*` match đúng 1 word, `#` match 0 hoặc nhiều. Đếm words cẩn thận.

2. **Pitfall: Fanout exchange + routing key = wasted effort**
   ```go
   // ❌ Routing key bị ignore hoàn toàn ở fanout exchange
   ch.PublishWithContext(ctx, "my-fanout", "some.routing.key", ...)
   //                                      ↑ Có vẻ quan trọng nhưng bị ignore
   
   // ✅ Dùng empty routing key, rõ ý đồ
   ch.PublishWithContext(ctx, "my-fanout", "", ...)
   ```

3. **Pitfall: Quá nhiều exchanges, quá ít bindings**
   ```
   ❌ 1 exchange per queue (thừa exchange, giống direct routing)
   ❌ 1 global exchange + complex routing keys (quá tải 1 exchange)
   
   ✅ 1 exchange per domain, multiple bindings per queue
   ```

4. **Pitfall: Routing key design không nhất quán**
   - Team A: `order.created`, Team B: `OrderCreated`, Team C: `created_order`
   - Fix: Quy ước routing key convention sớm, enforce bằng validation ở publisher

5. **Pitfall: Binding key `#` trên topic exchange ≈ fanout**
   - `#` match mọi routing key → queue nhận TẤT CẢ messages
   - Nếu thực sự cần broadcast → dùng fanout exchange (nhanh hơn)
   - `#` trên topic chỉ nên dùng cho audit/debug queue

---

## 7. Performance Considerations

### Exchange Type Performance

| Exchange Type | Routing Overhead | Memory | Throughput Impact |
|--------------|-----------------|--------|-------------------|
| **Fanout** | O(1) — no matching | Thấp nhất | Cao nhất |
| **Direct** | O(1) — hash lookup | Thấp | Rất cao |
| **Topic** | O(N) — trie traversal | Trung bình | -15-20% vs direct |
| **Headers** | O(N×M) — N headers × M bindings | Cao | -25-30% vs direct |

### Binding Count Impact

```
Direct exchange — binding count ít ảnh hưởng (hash lookup):
  10 bindings:   ~45,000 msg/s
  100 bindings:  ~44,500 msg/s
  1000 bindings: ~43,000 msg/s

Topic exchange — binding count ảnh hưởng nhiều hơn (trie traversal):
  10 bindings:   ~38,000 msg/s
  100 bindings:  ~35,000 msg/s
  1000 bindings: ~28,000 msg/s
```

**Rule of thumb:**
- < 100 bindings per exchange: performance không đáng lo
- 100-1000 bindings: cân nhắc tách exchange
- > 1000 bindings: tách exchange + review topology

### Monitoring Exchange Performance

```bash
# Exchange rates qua Management API
curl -s -u admin:admin123 \
  http://localhost:15672/api/exchanges/%2F/order.events | jq '{
    message_stats: .message_stats,
    publish_in: .message_stats.publish_in_details.rate,
    publish_out: .message_stats.publish_out_details.rate
  }'
```

Metrics cần theo dõi:
- **publish_in rate**: Messages đến exchange/s
- **publish_out rate**: Messages rời exchange/s (đến queues)
- **unroutable rate**: Messages không match binding nào (cần alternate exchange)
- **return rate**: Messages trả về publisher (mandatory flag)

---

## 8. Hands-on Lab

### 8.1 Setup (tái sử dụng Docker từ Day 4)

```bash
# Đảm bảo RabbitMQ đang chạy
docker compose up -d

# Tạo thư mục lab
mkdir -p day-05-exchange-types/lab && cd day-05-exchange-types/lab
go mod init exchange-lab
go get github.com/rabbitmq/amqp091-go
```

### 8.2 Lab 1: Direct Exchange — Notification Routing

**Scenario:** Hệ thống notification có 3 channels: email, SMS, push. Mỗi order event cần route đến đúng notification channel.

**File `direct_setup.go`:**
```go
package main

import (
	"log"

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatal(err)
	}
	defer ch.Close()

	exchangeName := "notifications"

	// Declare direct exchange
	err = ch.ExchangeDeclare(
		exchangeName,
		"direct", // type
		true,     // durable
		false,    // autoDelete
		false,    // internal
		false,    // noWait
		nil,
	)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("Exchange declared: %s (type: direct)", exchangeName)

	// Declare 3 queues cho 3 notification channels
	queues := []struct {
		name       string
		bindingKey string
	}{
		{"notification.email", "email"},
		{"notification.sms", "sms"},
		{"notification.push", "push"},
	}

	for _, q := range queues {
		_, err := ch.QueueDeclare(q.name, true, false, false, false, nil)
		if err != nil {
			log.Fatal(err)
		}

		err = ch.QueueBind(q.name, q.bindingKey, exchangeName, false, nil)
		if err != nil {
			log.Fatal(err)
		}

		log.Printf("Queue %s bound to %s with key '%s'", q.name, exchangeName, q.bindingKey)
	}

	log.Println("Direct exchange topology created. Check Management UI!")
}
```

**File `direct_publisher.go`:**
```go
package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

type Notification struct {
	UserID  string `json:"user_id"`
	Channel string `json:"channel"`
	Message string `json:"message"`
}

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatal(err)
	}
	defer ch.Close()

	ctx := context.Background()

	notifications := []Notification{
		{"user-001", "email", "Your order ORD-100 has been confirmed"},
		{"user-001", "sms", "Order ORD-100 confirmed. Track at example.com/track/100"},
		{"user-001", "push", "Order confirmed!"},
		{"user-002", "email", "Welcome to our platform!"},
		{"user-002", "push", "Complete your profile for 10% off"},
	}

	for _, notif := range notifications {
		body, _ := json.Marshal(notif)

		err := ch.PublishWithContext(ctx,
			"notifications", // exchange
			notif.Channel,   // routing key = notification channel
			false, false,
			amqp.Publishing{
				DeliveryMode: amqp.Persistent,
				ContentType:  "application/json",
				Body:         body,
			},
		)
		if err != nil {
			log.Printf("Publish failed: %v", err)
			continue
		}

		log.Printf("Sent [%s] to %s: %s", notif.Channel, notif.UserID, notif.Message)
	}
}
```

**File `direct_consumer.go`:**
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	amqp "github.com/rabbitmq/amqp091-go"
)

type Notification struct {
	UserID  string `json:"user_id"`
	Channel string `json:"channel"`
	Message string `json:"message"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go run direct_consumer.go <email|sms|push>")
		os.Exit(1)
	}
	channel := os.Args[1]
	queueName := "notification." + channel

	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	if err != nil {
		log.Fatal(err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatal(err)
	}
	defer ch.Close()

	ch.Qos(10, 0, false)

	msgs, err := ch.Consume(queueName, "", false, false, false, false, nil)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("[%s Worker] Waiting for notifications on queue: %s", channel, queueName)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			var notif Notification
			json.Unmarshal(msg.Body, &notif)

			log.Printf("[%s] Sending to %s: %s", channel, notif.UserID, notif.Message)
			msg.Ack(false)
		}
	}()

	<-sig
}
```

**Chạy:**
```bash
# Step 1: Setup topology
go run direct_setup.go

# Step 2: Start consumers (3 terminals)
go run direct_consumer.go email
go run direct_consumer.go sms
go run direct_consumer.go push

# Step 3: Publish
go run direct_publisher.go

# Quan sát: mỗi consumer chỉ nhận messages của channel mình
```

### 8.3 Lab 2: Fanout Exchange — Order Events Broadcast

**Scenario:** Khi order được tạo, nhiều services cần biết: PaymentService, InventoryService, NotificationService.

**File `fanout_demo.go`:**
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

type OrderCreatedEvent struct {
	OrderID string  `json:"order_id"`
	UserID  string  `json:"user_id"`
	Total   float64 `json:"total"`
}

func setupTopology(ch *amqp.Channel) {
	// Fanout exchange — broadcast to all bound queues
	ch.ExchangeDeclare("order.events", "fanout", true, false, false, false, nil)

	// Mỗi service có queue riêng
	services := []string{
		"payment.order-events",
		"inventory.order-events",
		"notification.order-events",
	}

	for _, q := range services {
		ch.QueueDeclare(q, true, false, false, false, nil)
		// Fanout: binding key ignored, dùng "" là đủ
		ch.QueueBind(q, "", "order.events", false, nil)
		log.Printf("Queue %s bound to order.events (fanout)", q)
	}
}

func publish(ch *amqp.Channel) {
	ctx := context.Background()

	for i := 1; i <= 5; i++ {
		event := OrderCreatedEvent{
			OrderID: fmt.Sprintf("ORD-%03d", i),
			UserID:  "user-001",
			Total:   float64(i) * 49.99,
		}
		body, _ := json.Marshal(event)

		ch.PublishWithContext(ctx,
			"order.events", // exchange
			"",             // routing key — ignored by fanout
			false, false,
			amqp.Publishing{
				DeliveryMode: amqp.Persistent,
				ContentType:  "application/json",
				Body:         body,
			},
		)
		log.Printf("Published: %s ($%.2f)", event.OrderID, event.Total)
	}
}

func consume(ch *amqp.Channel, queueName, serviceName string) {
	ch.Qos(10, 0, false)
	msgs, _ := ch.Consume(queueName, "", false, false, false, false, nil)

	for msg := range msgs {
		var event OrderCreatedEvent
		json.Unmarshal(msg.Body, &event)
		log.Printf("[%s] Processing order: %s ($%.2f)", serviceName, event.OrderID, event.Total)
		msg.Ack(false)
	}
}

func main() {
	conn, _ := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	defer conn.Close()

	ch, _ := conn.Channel()
	defer ch.Close()

	mode := "all"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	switch mode {
	case "setup":
		setupTopology(ch)
	case "publish":
		publish(ch)
	case "consume-payment":
		consume(ch, "payment.order-events", "PaymentService")
		return
	case "consume-inventory":
		consume(ch, "inventory.order-events", "InventoryService")
		return
	case "consume-notification":
		consume(ch, "notification.order-events", "NotificationService")
		return
	default:
		// All-in-one demo
		setupTopology(ch)

		// Start consumers in goroutines
		ch2, _ := conn.Channel()
		ch3, _ := conn.Channel()
		ch4, _ := conn.Channel()

		go consume(ch2, "payment.order-events", "PaymentService")
		go consume(ch3, "inventory.order-events", "InventoryService")
		go consume(ch4, "notification.order-events", "NotificationService")

		time.Sleep(500 * time.Millisecond)
		publish(ch)
		time.Sleep(2 * time.Second)
		return
	}

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
}
```

```bash
# All-in-one demo
go run fanout_demo.go

# Hoặc chạy riêng:
go run fanout_demo.go setup
go run fanout_demo.go consume-payment      # Terminal 1
go run fanout_demo.go consume-inventory    # Terminal 2
go run fanout_demo.go consume-notification # Terminal 3
go run fanout_demo.go publish              # Terminal 4
```

**Quan sát:** Mỗi message xuất hiện ở TẤT CẢ 3 consumers — fan-out broadcast.

### 8.4 Lab 3: Topic Exchange — Event Filtering System

**Scenario:** Hệ thống event-driven với routing key format `{domain}.{entity}.{action}`. Consumers cần filter linh hoạt.

**File `topic_demo.go`:**
```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

func main() {
	conn, _ := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	defer conn.Close()

	ch, _ := conn.Channel()
	defer ch.Close()

	exchangeName := "app.events"

	mode := "all"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}

	switch mode {
	case "setup":
		setup(ch, exchangeName)
	case "publish":
		publish(ch, exchangeName)
	case "consume":
		if len(os.Args) < 4 {
			fmt.Println("Usage: go run topic_demo.go consume <queue_name> <binding_key>")
			os.Exit(1)
		}
		consumeWithBinding(ch, exchangeName, os.Args[2], os.Args[3])
	default:
		allInOne(conn, ch, exchangeName)
	}
}

func setup(ch *amqp.Channel, exchange string) {
	ch.ExchangeDeclare(exchange, "topic", true, false, false, false, nil)

	bindings := []struct {
		queue      string
		bindingKey string
		desc       string
	}{
		// Queue nhận TẤT CẢ order events
		{"all-orders", "order.#", "All order domain events"},
		// Queue chỉ nhận payment events (bất kỳ domain nào)
		{"all-payments", "*.payment.*", "Payment events from any domain"},
		// Queue chỉ nhận success events
		{"success-events", "*.*.success", "All success events"},
		// Queue audit — nhận MỌI THỨ
		{"audit-log", "#", "All events for auditing"},
		// Queue chỉ nhận order payment specifically
		{"order-payment", "order.payment.*", "Order payment events only"},
	}

	for _, b := range bindings {
		ch.QueueDeclare(b.queue, true, false, false, false, nil)
		ch.QueueBind(b.queue, b.bindingKey, exchange, false, nil)
		log.Printf("Bound: %s ← [%s] %s (%s)", b.queue, b.bindingKey, exchange, b.desc)
	}
}

func publish(ch *amqp.Channel, exchange string) {
	ctx := context.Background()

	events := []struct {
		routingKey string
		body       string
	}{
		{"order.payment.success", "Order ORD-001 payment completed"},
		{"order.payment.failed", "Order ORD-002 payment declined"},
		{"order.shipment.dispatched", "Order ORD-001 shipped via FedEx"},
		{"order.refund.completed", "Order ORD-003 refund processed"},
		{"user.registration.success", "User USR-100 registered"},
		{"user.payment.success", "User USR-100 subscription payment"},
		{"inventory.stock.updated", "Product P-500 stock changed"},
	}

	for _, e := range events {
		ch.PublishWithContext(ctx, exchange, e.routingKey, false, false,
			amqp.Publishing{
				DeliveryMode: amqp.Persistent,
				ContentType:  "text/plain",
				Body:         []byte(e.body),
			},
		)
		log.Printf("Published [%s]: %s", e.routingKey, e.body)
	}
}

func consumeWithBinding(ch *amqp.Channel, exchange, queue, bindingKey string) {
	ch.ExchangeDeclare(exchange, "topic", true, false, false, false, nil)
	ch.QueueDeclare(queue, true, false, false, false, nil)
	ch.QueueBind(queue, bindingKey, exchange, false, nil)
	ch.Qos(10, 0, false)

	msgs, _ := ch.Consume(queue, "", false, false, false, false, nil)
	log.Printf("[%s] Waiting (binding: %s)...", queue, bindingKey)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		for msg := range msgs {
			log.Printf("[%s] ← [%s] %s", queue, msg.RoutingKey, string(msg.Body))
			msg.Ack(false)
		}
	}()
	<-sig
}

func allInOne(conn *amqp.Connection, ch *amqp.Channel, exchange string) {
	setup(ch, exchange)

	queues := []string{"all-orders", "all-payments", "success-events", "audit-log", "order-payment"}

	for _, q := range queues {
		qName := q
		consumeCh, _ := conn.Channel()
		consumeCh.Qos(10, 0, false)
		msgs, _ := consumeCh.Consume(qName, "", false, false, false, false, nil)

		go func() {
			for msg := range msgs {
				log.Printf("[%-15s] ← [%-30s] %s", qName, msg.RoutingKey, string(msg.Body))
				msg.Ack(false)
			}
		}()
	}

	time.Sleep(500 * time.Millisecond)
	log.Println("\n=== Publishing Events ===")
	publish(ch, exchange)

	time.Sleep(2 * time.Second)
	log.Println("\n=== Result Analysis ===")
	log.Println("all-orders:     received order.* events (order.#)")
	log.Println("all-payments:   received *.payment.* events from any domain")
	log.Println("success-events: received *.*.success events")
	log.Println("audit-log:      received ALL events (#)")
	log.Println("order-payment:  received only order.payment.* events")
}
```

```bash
# All-in-one demo
go run topic_demo.go

# Hoặc chạy multi-terminal
go run topic_demo.go setup
go run topic_demo.go consume all-orders "order.#"
go run topic_demo.go consume success-only "*.*.success"
go run topic_demo.go publish
```

**Kết quả expected:**

| Event | all-orders | all-payments | success-events | audit-log | order-payment |
|-------|:----------:|:------------:|:--------------:|:---------:|:-------------:|
| `order.payment.success` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `order.payment.failed` | ✅ | ✅ | ❌ | ✅ | ✅ |
| `order.shipment.dispatched` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `order.refund.completed` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `user.registration.success` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `user.payment.success` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `inventory.stock.updated` | ❌ | ❌ | ❌ | ✅ | ❌ |

### 8.5 Lab 4: Headers Exchange — Metadata Routing

**Scenario:** Fraud/Risk service muốn route theo metadata không nằm tự nhiên trong routing key: `tenant`, `region`, `risk`, `event_type`. Đây là lab nhỏ để thấy headers exchange hoạt động; trong production, chỉ dùng khi topic routing không biểu diễn được logic rõ ràng.

**File `headers_demo.go`:**
```go
package main

import (
	"context"
	"log"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
)

func failOnError(err error, msg string) {
	if err != nil {
		log.Fatalf("%s: %v", msg, err)
	}
}

func main() {
	conn, err := amqp.Dial("amqp://admin:admin123@localhost:5672/")
	failOnError(err, "connect RabbitMQ")
	defer conn.Close()

	ch, err := conn.Channel()
	failOnError(err, "open channel")
	defer ch.Close()

	exchange := "event.headers"
	err = ch.ExchangeDeclare(exchange, "headers", true, false, false, false, nil)
	failOnError(err, "declare headers exchange")

	bindings := []struct {
		queue string
		args  amqp.Table
	}{
		{
			queue: "vip-us-events",
			args: amqp.Table{
				"x-match": "all", // AND: tenant=vip AND region=us
				"tenant":  "vip",
				"region":  "us",
			},
		},
		{
			queue: "risk-or-failed-payments",
			args: amqp.Table{
				"x-match":    "any", // OR: risk=high OR event_type=payment.failed
				"risk":       "high",
				"event_type": "payment.failed",
			},
		},
	}

	for _, b := range bindings {
		_, err := ch.QueueDeclare(b.queue, true, false, false, false, nil)
		failOnError(err, "declare queue")
		_, _ = ch.QueuePurge(b.queue, false)
		err = ch.QueueBind(b.queue, "", exchange, false, b.args)
		failOnError(err, "bind queue")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	events := []struct {
		body    string
		headers amqp.Table
	}{
		{`{"id":"E1","kind":"vip-us-order"}`, amqp.Table{"tenant": "vip", "region": "us", "risk": "low", "event_type": "order.created"}},
		{`{"id":"E2","kind":"high-risk-order"}`, amqp.Table{"tenant": "standard", "region": "eu", "risk": "high", "event_type": "order.created"}},
		{`{"id":"E3","kind":"failed-payment"}`, amqp.Table{"tenant": "standard", "region": "us", "risk": "medium", "event_type": "payment.failed"}},
	}

	for _, event := range events {
		err := ch.PublishWithContext(ctx, exchange, "", false, false, amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Headers:      event.headers,
			Body:         []byte(event.body),
		})
		failOnError(err, "publish event")
	}

	for _, b := range bindings {
		for {
			msg, ok, err := ch.Get(b.queue, true)
			failOnError(err, "get message")
			if !ok {
				break
			}
			log.Printf("queue=%s headers=%v body=%s", b.queue, msg.Headers, string(msg.Body))
		}
	}
}
```

**Chạy:**
```bash
go run headers_demo.go
```

**Expected:**
- `vip-us-events` nhận `E1` vì match đủ `tenant=vip` và `region=us`.
- `risk-or-failed-payments` nhận `E2` vì `risk=high`, và `E3` vì `event_type=payment.failed`.
- Headers exchange ignore routing key; mọi quyết định route nằm ở binding arguments.

### 8.6 Lab 5: Quan sát Topology trên Management UI

Sau khi chạy labs, mở RabbitMQ Management UI:

1. **Exchanges tab** → click vào `app.events`:
   - Thấy type: `topic`
   - Thấy tất cả bindings với binding keys

2. **Queues tab** → click vào bất kỳ queue:
   - Thấy bindings (exchange + routing key)
   - Thấy message rates (incoming, deliver, ack)

3. **Export topology** cho documentation:
```bash
# Export toàn bộ RabbitMQ definitions (exchanges, queues, bindings, users, vhosts)
curl -s -u admin:admin123 http://localhost:15672/api/definitions | jq . > rabbitmq-topology.json

# Chỉ xem bindings
curl -s -u admin:admin123 http://localhost:15672/api/bindings/%2F | jq '.[] | {
  source: .source,
  destination: .destination,
  routing_key: .routing_key,
  destination_type: .destination_type
}'
```

### 8.7 Lab 6: Cleanup

```bash
# Xóa exchanges và queues tạo trong lab (optional — hoặc giữ cho Day 6)
curl -s -u admin:admin123 -X DELETE http://localhost:15672/api/exchanges/%2F/notifications
curl -s -u admin:admin123 -X DELETE http://localhost:15672/api/exchanges/%2F/order.events
curl -s -u admin:admin123 -X DELETE http://localhost:15672/api/exchanges/%2F/app.events
curl -s -u admin:admin123 -X DELETE http://localhost:15672/api/exchanges/%2F/event.headers

# Hoặc xóa tất cả queues
curl -s -u admin:admin123 http://localhost:15672/api/queues/%2F | \
  jq -r '.[].name' | while read q; do
    curl -s -u admin:admin123 -X DELETE "http://localhost:15672/api/queues/%2F/$q"
    echo "Deleted queue: $q"
  done
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Direct exchange với 2 queues cùng binding key sẽ hoạt động thế nào?** Message sẽ đi đến cả 2 hay chỉ 1? So sánh behavior này với fanout exchange.

   *Hint: Direct exchange + duplicate binding keys tạo ra fan-out behavior cho specific routing key.*

2. **Topic exchange: Routing key "order.payment.refund.completed" sẽ match những binding nào trong list sau?: (a) `order.#`, (b) `order.*`, (c) `order.payment.*`, (d) `*.*.refund.*`, (e) `#`**

   *Hint: Đếm số words (dots + 1) và apply wildcard rules.*

3. **Tại sao topic exchange chậm hơn direct exchange ~15-20%?** Giải thích cơ chế matching bên trong (trie data structure).

   *Hint: Direct dùng hash table (O(1)), topic dùng trie tree traversal (O(N)).*

4. **Design question:** Bạn có hệ thống e-commerce với 5 bounded contexts: Order, Payment, Inventory, Shipping, Notification. Thiết kế exchange topology:
   - Mỗi domain publish events riêng
   - NotificationService cần nhận events từ TẤT CẢ domains
   - PaymentService chỉ cần order.created events
   - InventoryService cần order.created và order.cancelled

   *Hint: Cân nhắc exchange-to-exchange binding hoặc topic exchange với binding patterns.*

5. **Alternate exchange giải quyết vấn đề gì?** Khi nào message bị unroutable? Đưa ra scenario cụ thể và cách debug.

   *Hint: Typo trong routing key, binding bị xóa, exchange declare lại với bindings khác.*

6. **So sánh routing flexibility giữa RabbitMQ topic exchange và NATS subject wildcards.** Cho ví dụ routing pattern mà RabbitMQ làm được nhưng NATS không, và ngược lại.

   *Hint: NATS `*` cũng dùng được ở giữa, ví dụ `time.*.east`. Khác biệt chính là RabbitMQ `#` match 0 hoặc nhiều words còn NATS `>` chỉ được ở cuối và không match subject cha.*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [RabbitMQ Exchange Types](https://www.rabbitmq.com/tutorials/amqp-concepts.html#exchanges)
- [Topic Exchange Tutorial](https://www.rabbitmq.com/tutorials/tutorial-five-go.html)
- [Exchange-to-Exchange Bindings](https://www.rabbitmq.com/e2e.html)
- [Alternate Exchanges](https://www.rabbitmq.com/ae.html)

### Architecture & Design
- [RabbitMQ Best Practices — CloudAMQP](https://www.cloudamqp.com/blog/part1-rabbitmq-best-practice.html)
- [RabbitMQ Routing Topologies](https://www.rabbitmq.com/tutorials/tutorial-four-go.html)
- [Event-driven architectures with RabbitMQ](https://www.rabbitmq.com/blog/2021/07/22/event-driven-architecture)

### Videos
- [RabbitMQ Exchange Types Explained — CloudAMQP](https://www.youtube.com/watch?v=o8eU5WiO8fw)
- [RabbitMQ in Microservices — GOTO Conference](https://www.youtube.com/watch?v=deG25y_r6OY)
