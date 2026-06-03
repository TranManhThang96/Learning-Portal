# Day 2: NATS JetStream — Persistence & Streaming

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu** tại sao NATS core không đủ cho production và JetStream giải quyết vấn đề gì
2. **Phân biệt** được Stream và Consumer trong JetStream — cách chúng tách biệt storage và consumption
3. **Cấu hình** được retention policies, limits, và delivery semantics phù hợp từng use case
4. **Thực hành** tạo stream, push/pull consumers, acknowledgment, và replay với Docker
5. **Hiểu** backpressure cơ bản — khi producer nhanh hơn consumer thì chuyện gì xảy ra

## 2. Kiến thức nền (Prerequisites)

- Day 1: NATS core concepts (subject, pub/sub, queue groups, request-reply)
- Hiểu at-most-once vs at-least-once delivery (Day 1 đã giới thiệu)
- Docker Compose đang chạy NATS server với `--js` flag (Day 1 setup)

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- JetStream là gì và giải quyết vấn đề gì so với NATS core
- Stream: tạo, cấu hình, retention policies
- Consumer: push vs pull, durable vs ephemeral
- Acknowledgment: Ack, Nak, InProgress, Term
- Hands-on: tạo stream + consumer + publish/consume messages

### 🟡 Should Learn (nếu còn thời gian)
- Replay policies (instant, original)
- Delivery policies (all, last, new, by start time, by sequence)
- Publisher deduplication với `Nats-Msg-Id` (không phải exactly-once end-to-end)
- Backpressure và flow control

### 🟢 Optional Deep Dive
- JetStream internals: Raft consensus cho replication
- Key-Value Store và Object Store trên JetStream
- Mirror và Source streams
- JetStream vs Kafka Streams comparison

---

## 4. Lý thuyết (Theory)

### 4.1 Từ NATS Core đến JetStream — WHY?

#### Vấn đề của NATS Core

Day 1 đã thấy: NATS core là **at-most-once** — message gửi xong là quên. Nếu subscriber offline, message biến mất vĩnh viễn.

Trong production, điều này gây ra các vấn đề nghiêm trọng:

```
Scenario: Payment Service restart 30 giây
┌────────────┐     ┌──────┐     ┌────────────────┐
│ Order Svc  │────>│ NATS │────>│ Payment Svc ❌  │ (đang restart)
│ publish 50 │     │      │     │ OFFLINE 30s     │
│ order msgs │     │      │     │                 │
└────────────┘     └──────┘     └────────────────┘
                     ↓
              50 messages MẤT HOÀN TOÀN
              Payment không xử lý order nào
              → Mất tiền, khách hàng phàn nàn
```

**Bạn cần:**
- ✅ Message persistence — message được lưu trữ, không mất khi consumer offline
- ✅ At-least-once delivery — đảm bảo message được xử lý ít nhất 1 lần
- ✅ Replay — consumer mới có thể đọc lại history
- ✅ Acknowledgment — biết chắc consumer đã xử lý xong

#### JetStream giải quyết thế nào?

JetStream là **persistence layer** built-in của NATS, thêm vào trên NATS core:

```
NATS Core (fire-and-forget)
    │
    ▼
JetStream (persistence + streaming)
    ├── Streams: lưu trữ messages trên disk
    ├── Consumers: track ai đã đọc đến đâu (giống consumer group trong Kafka)
    ├── Acknowledgment: confirm message đã xử lý
    └── Replay: đọc lại messages từ quá khứ
```

**Analogy:**
- NATS core = đài radio phát sóng trực tiếp — bỏ lỡ thì mất
- JetStream = podcast — ghi lại, nghe lại bất cứ lúc nào, biết bạn nghe đến đâu

---

### 4.2 Stream — Nơi lưu trữ Messages

#### WHAT — Stream là gì?

Stream là **message store** — nơi messages được lưu trữ trên disk theo thứ tự. Mỗi message trong stream có một **sequence number** tăng dần (giống offset trong Kafka).

```
Stream "ORDERS"
┌────┬────┬────┬────┬────┬────┬────┐
│ 1  │ 2  │ 3  │ 4  │ 5  │ 6  │ 7  │  ← sequence numbers
│msg1│msg2│msg3│msg4│msg5│msg6│msg7│  ← messages
└────┴────┴────┴────┴────┴────┴────┘
         ↑                      ↑
     First seq              Last seq

Subjects captured: orders.created, orders.shipped, orders.>
```

**Đặc điểm quan trọng:**
- 1 stream có thể capture **nhiều subjects** (ví dụ: `orders.>` capture tất cả subjects bắt đầu bằng `orders.`)
- Messages được ghi theo thứ tự nhận — **append-only log** (giống Kafka)
- Stream KHÔNG xóa message khi consumer đọc — message tồn tại theo retention policy

#### HOW — Retention Policies

Stream cần biết **khi nào xóa messages cũ**. Có 3 policies:

**1. Limits-based (mặc định)**
```
Xóa messages cũ nhất khi vượt giới hạn:
- MaxMessages: tối đa bao nhiêu messages
- MaxBytes: tối đa bao nhiêu bytes
- MaxAge: messages cũ hơn X thời gian bị xóa
```

**2. Interest-based**
```
Xóa message khi TẤT CẢ consumers đã ack
- Giống queue truyền thống — message xóa sau khi xử lý xong
- Phải có ít nhất 1 consumer được định nghĩa
```

**3. WorkQueue**
```
Xóa message ngay khi BẤT KỲ consumer nào ack
- Mỗi message chỉ được xử lý bởi 1 consumer
- Giống competing consumers / work queue pattern
```

**Nuance quan trọng:** `WorkQueue` chỉ cho phép **một consumer cho mỗi subject filter không overlap** trên cùng stream. Ví dụ stream capture `orders.>` thì không nên tạo đồng thời consumer filter `orders.created` và `orders.*` nếu chúng có thể match cùng message. Nếu cần nhiều services độc lập cùng nhận `orders.created`, dùng `Limits` hoặc `Interest` retention thay vì `WorkQueue`.

#### Trade-off Analysis — Retention Policies

| Policy | Khi nào dùng | Ưu điểm | Nhược điểm |
|--------|-------------|----------|------------|
| **Limits** | Event sourcing, audit log, replay | Flexible, replay bất kỳ lúc nào | Tốn disk, cần quản lý limits |
| **Interest** | Multi-consumer processing pipeline | Tự dọn dẹp sau khi tất cả xử lý xong | Phải define consumer trước |
| **WorkQueue** | Task distribution, job queue | Simple, auto-cleanup | Chỉ 1 consumer xử lý mỗi message |

#### Stream Configuration quan trọng

```
Stream "ORDERS":
  subjects: ["orders.>"]           # Capture tất cả subjects bắt đầu bằng "orders."
  retention: limits                 # Xóa theo limits
  max_msgs: 1_000_000             # Tối đa 1 triệu messages
  max_bytes: 1GB                   # Tối đa 1GB storage
  max_age: 7d                      # Messages cũ hơn 7 ngày bị xóa
  storage: file                    # Lưu trên disk (hoặc "memory" cho tốc độ)
  replicas: 3                      # Replicate sang 3 nodes (clustering — Day 3)
  max_msg_size: 1MB                # Giới hạn size mỗi message
  discard: old                     # Khi đầy, xóa messages cũ nhất (hoặc "new" = reject mới)
```

---

### 4.3 Consumer — Theo dõi ai đọc đến đâu

#### WHAT — Consumer là gì?

Consumer là **view** trên stream — nó track vị trí đọc (sequence number) của một nhóm subscribers. Giống **consumer group** trong Kafka.

```
Stream "ORDERS": [msg1][msg2][msg3][msg4][msg5][msg6][msg7]
                                    ↑              ↑
Consumer "payment-svc":          seq 4           (đang xử lý)
Consumer "notification-svc":                    seq 6 (đã xử lý đến đây)
Consumer "analytics-svc":   seq 1 (mới bắt đầu, đọc từ đầu)
```

- Mỗi consumer track **độc lập** — không ảnh hưởng lẫn nhau
- Nhiều instances của cùng 1 consumer → **load balancing** (giống queue groups)
- Consumer có thể bắt đầu đọc từ đầu, từ cuối, hoặc từ timestamp/sequence cụ thể

#### Push vs Pull Consumer

**Push Consumer:**
- Server **chủ động đẩy** messages đến client
- Client chỉ cần subscribe và chờ
- Đơn giản nhưng khó kiểm soát flow rate

```
Stream ──push──> Consumer ──deliver──> Client
                                       (client nhận liên tục)
```

**Pull Consumer:**
- Client chủ động **kéo** messages khi sẵn sàng
- Client kiểm soát batch size và tốc độ
- Tốt hơn cho backpressure — client chỉ pull khi xử lý xong batch trước

```
Stream <──pull── Consumer <──fetch── Client
                                     (client quyết định khi nào lấy)
```

#### Trade-off: Push vs Pull

| Tiêu chí | Push Consumer | Pull Consumer |
|----------|--------------|---------------|
| **Simplicity** | Đơn giản — subscribe và nhận | Phức tạp hơn — phải gọi Fetch |
| **Backpressure** | Khó — server cứ push | Tốt — client kiểm soát tốc độ |
| **Latency** | Thấp — nhận ngay khi có msg | Cao hơn — polling interval |
| **Batch processing** | Khó — từng message một | Dễ — fetch N messages cùng lúc |
| **Horizontal scaling** | Tự động distribute | Tự động distribute |
| **Sử dụng khi** | Real-time, low latency | Batch processing, backpressure |

**Production recommendation:** Ưu tiên **Pull Consumer** cho hầu hết use cases vì kiểm soát backpressure tốt hơn. Dùng Push Consumer chỉ khi cần ultra-low latency.

#### Durable vs Ephemeral Consumer

**Durable Consumer:**
- Có tên (durable name) — server lưu trạng thái giữa các lần connect
- Reconnect → tiếp tục từ vị trí cũ
- Dùng cho production workloads

**Ephemeral Consumer:**
- Không có tên — mất khi disconnect
- Reconnect → bắt đầu lại từ đầu (hoặc theo deliver policy)
- Dùng cho monitoring, debugging, ad-hoc queries

---

### 4.4 Acknowledgment — Đảm bảo message được xử lý

#### WHY — Tại sao cần Ack?

Không có ack, server không biết consumer đã xử lý message chưa. Nếu consumer crash giữa chừng, message bị mất.

#### WHAT — Các loại Ack

```
Consumer nhận message → Xử lý → Gửi Ack/Nak
```

| Ack Type | Ý nghĩa | Server phản ứng |
|----------|---------|-----------------|
| **Ack** | "Đã xử lý xong" | Đánh dấu delivered, không gửi lại |
| **Nak** | "Xử lý thất bại, gửi lại" | Re-deliver message (có delay) |
| **InProgress** | "Đang xử lý, cần thêm thời gian" | Reset ack wait timer |
| **Term** | "Message lỗi, không thể xử lý, dừng retry" | Đánh dấu terminated, không gửi lại |

**Ack Wait**: Server chờ ack trong khoảng thời gian X (mặc định 30s). Nếu hết thời gian, tự động re-deliver.

```
Consumer nhận msg → bắt đầu xử lý
    │
    ├─ Xử lý thành công → Ack ✅
    │
    ├─ Xử lý thất bại (tạm thời) → Nak → server re-deliver
    │
    ├─ Cần xử lý lâu (>30s) → InProgress → reset timer → xử lý tiếp → Ack
    │
    └─ Message invalid/poison → Term → dừng retry, log alert
```

#### Max Deliveries & Dead Letter

Khi 1 message liên tục bị Nak hoặc timeout:
- `max_deliver: 5` → sau 5 lần deliver mà không ack, consumer dừng redelivery message đó và phát advisory event.
- Message **không tự biến mất thành DLQ**. Với `Limits` retention, message vẫn nằm trong stream cho đến khi retention/limits xóa hoặc bạn xử lý thủ công. Với `WorkQueue`, message đã chạm `MaxDeliver` vẫn cần operator/app quyết định delete, term hoặc route sang nơi khác.
- Kết hợp với **advisory subjects** để route poison messages đến DLQ-like stream hoặc alerting pipeline.

---

### 4.5 Delivery Policies — Bắt đầu đọc từ đâu?

Khi tạo consumer mới, bạn chọn bắt đầu đọc từ đâu:

| Policy | Mô tả | Use case |
|--------|-------|----------|
| **DeliverAll** | Từ message đầu tiên trong stream | Event sourcing, rebuild state |
| **DeliverLast** | Chỉ message cuối cùng | Current state, config updates |
| **DeliverLastPerSubject** | Message cuối cùng per subject | State per entity |
| **DeliverNew** | Chỉ messages mới từ lúc tạo consumer | Real-time processing |
| **DeliverByStartSequence** | Từ sequence number cụ thể | Resume từ checkpoint |
| **DeliverByStartTime** | Từ timestamp cụ thể | Replay sau incident |

---

### 4.6 Backpressure — Khi Producer nhanh hơn Consumer

#### WHY — Vấn đề gì xảy ra?

```
Producer: 10,000 msg/s ──> Stream ──> Consumer: 1,000 msg/s
                            │
                            ▼
                   Messages tích tụ trong stream
                   Disk usage tăng liên tục
                   Consumer lag tăng
                   Cuối cùng: OOM hoặc disk full
```

#### HOW — JetStream xử lý backpressure

1. **Stream limits**: `max_msgs`, `max_bytes`, `max_age` → khi đầy:
   - `discard: old` → xóa messages cũ nhất (mất data)
   - `discard: new` → reject messages mới (producer nhận error)

2. **Pull Consumer**: Consumer tự kiểm soát tốc độ pull → tự nhiên backpressure

3. **Flow Control** (push consumer): Server pause delivery khi consumer chậm, resume khi consumer bắt kịp

4. **Max Ack Pending**: Giới hạn số messages chưa ack tại một thời điểm
   ```
   max_ack_pending: 1000  → server chỉ deliver tối đa 1000 msg chưa ack
   ```

**Best practice:** Dùng pull consumer + monitoring consumer lag. Alert khi lag vượt threshold.

---

### 4.7 Publisher Deduplication với `Nats-Msg-Id`

#### WHY

Publisher gửi message, network timeout, publisher retry → 2 messages giống nhau trong stream.

#### HOW

JetStream hỗ trợ **message deduplication** qua `Nats-Msg-Id` header:

```
Publish attempt 1: Nats-Msg-Id: "order-123" → Stored (seq 1)
Publish attempt 2: Nats-Msg-Id: "order-123" → Duplicate detected → Rejected
```

Server giữ **dedup window** (mặc định thường được cấu hình 2 phút trong lab) — trong cửa sổ này, messages cùng ID bị detect là duplicate.

**Không gọi đây là exactly-once end-to-end.** `Nats-Msg-Id` chỉ chống duplicate publish trong dedup window của stream. Consumer vẫn có thể xử lý lại message vì crash sau side effect nhưng trước `Ack()`. Production vẫn cần `message_id`, idempotent consumer, inbox/dedup table hoặc business key duy nhất.

---

## 5. Trade-off Analysis tổng hợp

### NATS Core vs JetStream

| Tiêu chí | NATS Core | JetStream |
|----------|-----------|-----------|
| **Delivery** | At-most-once | At-least-once + publisher dedup window |
| **Persistence** | ❌ Không | ✅ Disk/Memory |
| **Replay** | ❌ | ✅ Từ bất kỳ điểm nào |
| **Consumer tracking** | ❌ | ✅ Durable consumers |
| **Throughput** | ~10M msg/s | ~500K-1M msg/s |
| **Latency** | ~100μs | ~500μs-1ms |
| **Complexity** | Cực thấp | Trung bình |
| **Storage** | Không cần disk | Cần disk |

### JetStream vs Kafka (high-level)

| Tiêu chí | JetStream | Kafka |
|----------|-----------|-------|
| **Setup** | Zero-config, built-in NATS | Cần ZooKeeper/KRaft, config phức tạp |
| **Throughput** | ~500K-1M msg/s | ~1M+ msg/s (batching) |
| **Ecosystem** | Nhỏ | Rất lớn (Connect, Streams, Schema Registry) |
| **Operations** | Đơn giản | Phức tạp (rebalance, ISR, partition management) |
| **Best for** | Microservices, nhẹ, nhanh | Data pipeline, event sourcing, analytics at scale |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Luôn dùng Durable Consumer cho production workloads**
   - Ephemeral consumer mất state khi disconnect → mất vị trí đọc

2. **Ưu tiên Pull Consumer trừ khi cần ultra-low latency**
   - Pull cho phép client kiểm soát batch size và tốc độ xử lý

3. **Set `max_deliver` hợp lý (thường 3-5 lần)**
   - Quá ít → message bị bỏ quá sớm
   - Quá nhiều → poison message blocking pipeline
   - Chạm `max_deliver` chỉ dừng redelivery cho consumer đó và phát advisory; không tự tạo DLQ

4. **Dùng `Nats-Msg-Id` cho idempotent publishing**
   - Tránh duplicate messages khi publisher retry trong dedup window
   - Không thay thế idempotent consumer

5. **Monitor consumer lag**
   - Lag = last sequence in stream - last ack'd sequence by consumer
   - Alert khi lag tăng liên tục

### Common Pitfalls

1. **Pitfall: Không set `max_age` hoặc `max_bytes` cho stream**
   - Stream grow vô hạn → disk full → server crash
   - Fix: Luôn set limits phù hợp use case

2. **Pitfall: Dùng push consumer cho batch processing**
   - Server push liên tục, consumer không kịp → memory pressure
   - Fix: Pull consumer + fetch batch

3. **Pitfall: Ack trước khi xử lý xong**
   ```go
   // ❌ SAI — ack trước khi xử lý
   msg.Ack()
   processMessage(msg) // crash ở đây → message mất
   
   // ✅ ĐÚNG — ack SAU khi xử lý
   err := processMessage(msg)
   if err == nil {
       msg.Ack()
   } else {
       msg.Nak() // retry
   }
   ```

4. **Pitfall: Subject filter quá rộng cho stream**
   - `subjects: [">"]` capture TOÀN BỘ messages trong NATS → stream khổng lồ
   - Fix: Cụ thể hóa subjects cho mỗi stream

---

## 7. Performance Considerations

### Benchmark Numbers

Các số dưới đây là order of magnitude cho local/same-region lab: payload nhỏ, file storage trên disk nhanh, replicas=1 trừ khi ghi chú khác, client đủ concurrency. Bật replicas=3, TLS, disk chậm hoặc payload lớn sẽ làm throughput/latency thay đổi đáng kể.

| Metric | JetStream (file storage) | JetStream (memory) |
|--------|-------------------------|-------------------|
| **Publish throughput** | ~200K-500K msg/s | ~800K-1M msg/s |
| **E2E latency** | ~1-5ms | ~200μs-1ms |
| **Storage efficiency** | ~1.2x raw data | RAM giới hạn |
| **Replay throughput** | ~100K-300K msg/s | ~500K+ msg/s |

### Key Tuning Parameters

| Config | Mặc định | Recommend | Lý do |
|--------|---------|-----------|-------|
| `max_ack_pending` | 20,000 | 1,000-5,000 | Tránh memory pressure khi consumer chậm |
| `ack_wait` | 30s | 10-60s tùy processing time | Quá ngắn → re-deliver sớm, quá dài → block pipeline |
| `max_deliver` | -1 (unlimited) | 3-5 | Tránh poison message loop vô hạn |
| `replicas` | 1 | 3 | Durability, nhưng tăng latency |

### Metrics cần monitor

- **Stream msgs/bytes**: Tổng messages và storage usage
- **Consumer ack pending**: Số messages đã deliver nhưng chưa ack
- **Consumer num pending**: Số messages chưa deliver (lag)
- **Consumer redelivery count**: Số lần re-deliver (cao = processing errors)
- **Stream discard count**: Số messages bị reject khi stream đầy

---

## 8. Hands-on Lab

### 8.1 Setup (dùng lại Docker Compose từ Day 1)

Verify JetStream đã enabled:
```bash
# Kiểm tra JetStream status
nats account info

# Expected output bao gồm:
# JetStream: enabled
```

### 8.2 Lab 1: Tạo Stream và publish messages (NATS CLI)

```bash
# Tạo stream "ORDERS" capture subjects orders.>
nats stream add ORDERS \
  --subjects "orders.>" \
  --retention limits \
  --max-msgs 100000 \
  --max-bytes 100MB \
  --max-age 24h \
  --storage file \
  --replicas 1 \
  --discard old \
  --max-msg-size 1MB \
  --defaults

# Xem stream info
nats stream info ORDERS

# Publish một số messages
nats pub orders.created '{"order_id":"ORD-001","item":"laptop","qty":1}'
nats pub orders.created '{"order_id":"ORD-002","item":"phone","qty":2}'
nats pub orders.shipped '{"order_id":"ORD-001","carrier":"fedex"}'
nats pub orders.created '{"order_id":"ORD-003","item":"tablet","qty":1}'

# Kiểm tra stream state
nats stream info ORDERS
# Expect: Messages: 4, Bytes: ~400B

# Xem messages trong stream (peek, không consume)
nats stream view ORDERS
```

### 8.3 Lab 2: Pull Consumer với NATS CLI

```bash
# Tạo pull consumer "payment-processor"
nats consumer add ORDERS payment-processor \
  --pull \
  --deliver all \
  --ack explicit \
  --max-deliver 3 \
  --max-pending 100 \
  --filter "orders.created" \
  --defaults

# Xem consumer info
nats consumer info ORDERS payment-processor

# Fetch messages (pull 2 messages)
nats consumer next ORDERS payment-processor --count 2

# Fetch 1 message at a time
nats consumer next ORDERS payment-processor
```

### 8.4 Lab 3: Push Consumer với NATS CLI

```bash
# Tạo push consumer "notification-svc"
nats consumer add ORDERS notification-svc \
  --deliver all \
  --ack explicit \
  --max-deliver 5 \
  --deliver-to "deliver.notifications" \
  --defaults

# Subscribe để nhận pushed messages
nats sub "deliver.notifications"
```

Mở terminal khác và publish:
```bash
nats pub orders.created '{"order_id":"ORD-010","item":"monitor"}'
```

### 8.5 Lab 4: JetStream Pub/Sub với Go

**File `js_publisher.go`:**
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/nats-io/nats.go"
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Item      string    `json:"item"`
	Quantity  int       `json:"quantity"`
	CreatedAt time.Time `json:"created_at"`
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	js, err := nc.JetStream()
	if err != nil {
		log.Fatal(err)
	}

	// Tạo stream nếu chưa tồn tại
	_, err = js.AddStream(&nats.StreamConfig{
		Name:       "ORDERS",
		Subjects:   []string{"orders.>"},
		Retention:  nats.LimitsPolicy,
		MaxMsgs:    100_000,
		MaxBytes:   100 * 1024 * 1024, // 100MB
		MaxAge:     24 * time.Hour,
		Storage:    nats.FileStorage,
		Replicas:   1,
		Discard:    nats.DiscardOld,
		MaxMsgSize: 1024 * 1024, // 1MB
		// Deduplication window — reject duplicate Nats-Msg-Id trong 2 phút
		Duplicates: 2 * time.Minute,
	})
	if err != nil {
		log.Printf("Stream may already exist: %v", err)
	}

	for i := 1; i <= 10; i++ {
		order := OrderEvent{
			OrderID:   fmt.Sprintf("ORD-%03d", i),
			Item:      "laptop",
			Quantity:  i,
			CreatedAt: time.Now(),
		}
		data, _ := json.Marshal(order)

		// Publish với message ID để deduplication
		ack, err := js.Publish("orders.created", data,
			nats.MsgId(fmt.Sprintf("order-%s", order.OrderID)),
		)
		if err != nil {
			log.Printf("Publish error: %v", err)
			continue
		}

		log.Printf("Published %s → stream=%s seq=%d duplicate=%v",
			order.OrderID, ack.Stream, ack.Sequence, ack.Duplicate)
	}

	// Publish lại message đầu tiên — sẽ bị detect là duplicate
	order1 := OrderEvent{OrderID: "ORD-001", Item: "laptop", Quantity: 1, CreatedAt: time.Now()}
	data, _ := json.Marshal(order1)
	ack, err := js.Publish("orders.created", data,
		nats.MsgId("order-ORD-001"), // cùng Nats-Msg-Id
	)
	if err != nil {
		log.Printf("Duplicate publish error: %v", err)
	} else {
		log.Printf("Duplicate detected: %v (seq=%d)", ack.Duplicate, ack.Sequence)
	}
}
```

**File `js_consumer.go`:**
```go
package main

import (
	"encoding/json"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nats-io/nats.go"
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	Item      string    `json:"item"`
	Quantity  int       `json:"quantity"`
	CreatedAt time.Time `json:"created_at"`
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	js, err := nc.JetStream()
	if err != nil {
		log.Fatal(err)
	}

	if _, err := js.StreamInfo("ORDERS"); err != nil {
		_, err = js.AddStream(&nats.StreamConfig{
			Name:      "ORDERS",
			Subjects:  []string{"orders.>"},
			Retention: nats.LimitsPolicy,
			MaxMsgs:   100_000,
			MaxAge:    24 * time.Hour,
			Storage:   nats.FileStorage,
		})
		if err != nil {
			log.Fatalf("Failed to create ORDERS stream: %v", err)
		}
		log.Println("Created ORDERS stream because it did not exist")
	}

	// Tạo durable pull consumer
	sub, err := js.PullSubscribe(
		"orders.created",
		"payment-processor",
		nats.ManualAck(),
		nats.MaxDeliver(3),
		nats.AckWait(10*time.Second),
	)
	if err != nil {
		log.Fatal(err)
	}

	log.Println("Payment processor started — pulling messages...")

	go func() {
		for {
			// Pull batch 5 messages, chờ tối đa 5 giây
			msgs, err := sub.Fetch(5, nats.MaxWait(5*time.Second))
			if err != nil {
				if err == nats.ErrTimeout {
					continue // Không có message mới, poll lại
				}
				log.Printf("Fetch error: %v", err)
				continue
			}

			for _, msg := range msgs {
				var order OrderEvent
				if err := json.Unmarshal(msg.Data, &order); err != nil {
					log.Printf("Bad message, terminating: %v", err)
					msg.Term() // Poison message — dừng retry
					continue
				}

				// Giả lập processing có thể fail
				if rand.Float64() < 0.2 {
					log.Printf("❌ Failed to process %s — Nak for retry", order.OrderID)
					msg.Nak() // Yêu cầu re-deliver
					continue
				}

				// Xử lý thành công
				log.Printf("✅ Processed order %s: %d x %s", order.OrderID, order.Quantity, order.Item)

				// Ack SAU khi xử lý xong
				msg.Ack()
			}
		}
	}()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	log.Println("Payment processor shutting down")
}
```

**Chạy:**
```bash
# Terminal 1 — consumer (chạy trước)
go run js_consumer.go

# Terminal 2 — publisher
go run js_publisher.go
```

**Quan sát:**
- Publisher nhận ack với sequence number cho mỗi message
- Message cuối cùng (duplicate) bị detect `duplicate=true` vì cùng `Nats-Msg-Id` trong dedup window
- Consumer xử lý messages, ~20% fail và Nak → re-deliver
- Sau 3 lần deliver mà vẫn fail → consumer dừng redelivery message đó; kiểm tra advisory/stream state để quyết định DLQ hoặc delete thủ công

### 8.6 Lab 5: Replay và Delivery Policy

```bash
# Tạo consumer đọc từ đầu stream
nats consumer add ORDERS replay-all \
  --pull \
  --deliver all \
  --ack none \
  --defaults

# Fetch tất cả messages (replay)
nats consumer next ORDERS replay-all --count 100

# Tạo consumer chỉ nhận messages mới
nats consumer add ORDERS only-new \
  --pull \
  --deliver new \
  --ack explicit \
  --defaults

# Consumer này chỉ nhận messages publish SAU khi tạo consumer
nats consumer next ORDERS only-new --count 5
# → timeout vì chưa có message mới

# Publish message mới
nats pub orders.created '{"order_id":"NEW-001","item":"keyboard"}'

# Bây giờ consumer only-new sẽ nhận
nats consumer next ORDERS only-new --count 1
```

### 8.7 Lab 6: Monitor stream và consumer

```bash
# Stream metrics
nats stream report

# Consumer lag report
nats consumer report ORDERS

# Watch messages real-time (giống tail -f)
nats stream view ORDERS --last 5

# JetStream account info
nats account info
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Stream và Consumer khác nhau cốt lõi ở điểm nào?** Tại sao JetStream tách 2 concept này thay vì gộp chung (như queue truyền thống)?

   *Hint: Nghĩ về việc nhiều consumer groups đọc cùng stream — nếu gộp chung thì sao?*

2. **Giải thích 3 retention policies (Limits, Interest, WorkQueue).** Cho mỗi policy, đưa ra 1 use case cụ thể trong hệ thống e-commerce.

3. **Push vs Pull Consumer — khi nào chọn cái nào?** Giải thích trong context backpressure: nếu producer đang publish 10K msg/s nhưng consumer chỉ xử lý được 1K msg/s, pull consumer giải quyết vấn đề này thế nào? Push consumer thì sao?

4. **4 loại acknowledgment (Ack, Nak, InProgress, Term) — khi nào dùng từng loại?** Cho scenario: consumer nhận message xử lý order payment. Describe flow xử lý khi: (a) thành công, (b) payment gateway timeout, (c) message data invalid.

5. **Delivery Policy: DeliverAll vs DeliverNew vs DeliverByStartTime** — Scenario: Service A crash lúc 14:00 và restart lúc 14:05. Bạn muốn xử lý lại tất cả messages từ 14:00. Bạn chọn delivery policy nào? Tại sao không dùng DeliverAll?

6. **Publisher deduplication với `Nats-Msg-Id` hoạt động thế nào?** Nếu dedup window là 2 phút, và publisher retry sau 3 phút, điều gì xảy ra? Vì sao đây không phải exactly-once end-to-end?

   *Hint: Dedup ở publisher level khác dedup ở consumer level.*

7. **Design question:** Bạn có stream "ORDERS" với 3 consumers: payment-svc, inventory-svc, notification-svc. Payment xử lý xong mới được ship (inventory). Notification gửi ngay. Bạn thiết kế consumers và subjects thế nào? Dùng retention policy gì?

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [JetStream Model Deep Dive](https://docs.nats.io/nats-concepts/jetstream/streams)
- [Consumer Configuration](https://docs.nats.io/nats-concepts/jetstream/consumers)

### Architecture & Internals
- [JetStream Design (NATS GitHub)](https://github.com/nats-io/nats-architecture-and-design)
- [NATS JetStream Walkthrough](https://docs.nats.io/nats-concepts/jetstream/js_walkthrough)

### Best Practices
- [Synadia Blog — JetStream Best Practices](https://www.synadia.com/blog)
- [NATS By Example](https://natsbyexample.com/) — Interactive examples

### Videos
- [JetStream Deep Dive — NATS Community](https://www.youtube.com/watch?v=mc46cG7oyjI)
- [Building Resilient Systems with NATS JetStream](https://www.youtube.com/watch?v=Kc_WT4pU0GI)
