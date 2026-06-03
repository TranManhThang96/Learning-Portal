# Day 1: Messaging Fundamentals + NATS Core Concepts

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu rõ** sự khác biệt giữa synchronous và asynchronous communication, và khi nào nên dùng cái nào
2. **Phân biệt** được 3 messaging models: Queue, Pub/Sub, Stream — kèm trade-off của từng loại
3. **Hiểu** kiến trúc cơ bản của NATS: subject, publish, subscribe, wildcards, request-reply
4. **Thực hành** được NATS pub/sub và request-reply bằng Go hoặc TypeScript với Docker
5. **So sánh** được NATS với HTTP/gRPC ở mức high-level để chọn đúng tool

## 2. Kiến thức nền (Prerequisites)

- Hiểu HTTP request/response model
- Biết cơ bản về microservices architecture
- Có kinh nghiệm với Docker và Docker Compose
- Biết Go hoặc TypeScript cơ bản

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Synchronous vs Asynchronous communication
- Queue vs Pub/Sub vs Stream — 3 messaging models
- NATS core: subject, publish, subscribe, wildcards
- Request-reply pattern
- Hands-on: NATS pub/sub + request-reply với Docker

### 🟡 Should Learn (nếu còn thời gian)
- Subject naming conventions & best practices
- Queue groups (load balancing consumers)
- So sánh NATS core vs HTTP/gRPC chi tiết

### 🟢 Optional Deep Dive
- NATS protocol internals (text-based protocol)
- NATS architecture: zero-dependency, single binary
- History của NATS và design philosophy

---

## 4. Lý thuyết (Theory)

### 4.1 Synchronous vs Asynchronous Communication

#### WHY — Tại sao cần phân biệt?

Trong monolith, các module gọi nhau trực tiếp qua function call — đơn giản, nhanh, dễ debug. Nhưng khi chuyển sang microservices, mỗi service là một process riêng biệt, giao tiếp qua network. Lúc này bạn phải chọn: **gọi trực tiếp (sync)** hay **gửi message rồi quên (async)**?

Chọn sai → hệ thống fragile, cascading failures, bottleneck. Chọn đúng → resilient, scalable, loosely coupled.

#### WHAT — Định nghĩa

**Synchronous communication** (HTTP, gRPC):
- Caller **chờ** response trước khi tiếp tục
- Giống gọi điện thoại: phải có người nghe mới nói chuyện được
- Coupling chặt: caller phải biết address của callee

```
Service A ---HTTP POST /orders---> Service B
           <---200 OK + data------
           (A blocked cho đến khi B trả lời)
```

**Asynchronous communication** (Message Broker):
- Caller **gửi message rồi tiếp tục** làm việc khác
- Giống gửi email: gửi xong là quên, người nhận xử lý khi nào tùy họ
- Coupling lỏng: caller không cần biết ai sẽ xử lý message

```
Service A ---publish msg---> [Message Broker] ---deliver---> Service B
           (A tiếp tục ngay,                    (B xử lý khi sẵn sàng)
            không cần chờ)
```

#### HOW — Khi nào dùng cái nào?

| Tiêu chí | Synchronous (HTTP/gRPC) | Asynchronous (Message Broker) |
|----------|------------------------|------------------------------|
| **Khi cần response ngay** | ✅ User đang chờ kết quả | ❌ Không phù hợp |
| **Khi cần fire-and-forget** | ❌ Waste connection | ✅ Gửi xong quên |
| **Coupling** | Chặt — phải biết URL | Lỏng — chỉ biết topic/subject |
| **Failure handling** | Cascading failure | Isolated — broker buffer messages |
| **Scaling** | Load balancer phức tạp | Thêm consumer tự nhiên |
| **Debugging** | Dễ — trace request | Khó hơn — cần correlation ID |
| **Latency** | Thấp (~1-10ms nội bộ) | Cao hơn (~5-50ms qua broker) |

**Giả định cho các số latency/throughput trong bài:** các con số bên dưới là order of magnitude để so sánh mental model, không phải SLA. Chúng giả định message nhỏ, local network hoặc cùng region, không TLS, không persistence, client đủ concurrency và broker không bị disk/network bottleneck. Khi bật persistence, replication, TLS, cross-region hoặc payload lớn, số thực tế có thể khác nhiều.

**Production rule of thumb:**
- **Dùng sync** khi: user đang chờ (API gateway → service), cần data ngay để tiếp tục xử lý, read operations
- **Dùng async** khi: downstream processing (send email, update analytics), cross-domain communication, event notification, background jobs

**Ví dụ thực tế — E-commerce checkout:**
```
User click "Đặt hàng"
  → [SYNC] API Gateway → Order Service: tạo order, trả order_id cho user
  → [ASYNC] Order Service publish event "order.created"
      → Payment Service: xử lý thanh toán
      → Inventory Service: trừ kho
      → Notification Service: gửi email xác nhận
      → Analytics Service: ghi log analytics
```

User chỉ cần chờ order_id (sync). Các bước sau không cần user chờ (async).

---

### 4.2 Ba Messaging Models: Queue, Pub/Sub, Stream

#### WHY — Tại sao có nhiều model?

Mỗi use case cần message được xử lý **khác nhau**:
- Có khi bạn muốn **chỉ 1 worker** xử lý mỗi task (job queue)
- Có khi bạn muốn **tất cả subscribers** đều nhận (broadcast notification)
- Có khi bạn muốn **replay lại** messages từ quá khứ (event sourcing, audit)

Không có model nào "tốt nhất" — chỉ có model **phù hợp nhất** cho use case cụ thể.

#### WHAT — 3 Models chi tiết

**1. Queue (Point-to-Point / Competing Consumers)**

```
Producer → [Queue: ████████] → Consumer 1 (nhận msg A)
                              → Consumer 2 (nhận msg B)
                              → Consumer 3 (nhận msg C)
```

- Mỗi message chỉ được **1 consumer** xử lý (competing consumers)
- Message bị xóa khỏi queue sau khi được consumed
- **Analogy**: Hàng đợi ở ngân hàng — mỗi khách chỉ được 1 nhân viên phục vụ
- **Use case**: Task distribution, background jobs, work queue

**2. Pub/Sub (Publish/Subscribe)**

```
Publisher → [Topic/Subject] → Subscriber 1 (nhận copy)
                             → Subscriber 2 (nhận copy)
                             → Subscriber 3 (nhận copy)
```

- Mỗi message được **tất cả subscribers** nhận (fan-out)
- Message thường không được lưu trữ (fire-and-forget)
- **Analogy**: Đài radio — tất cả người nghe đều nhận cùng nội dung
- **Use case**: Event notification, real-time updates, cache invalidation

**3. Stream (Distributed Log)**

```
Producer → [Log: msg1|msg2|msg3|msg4|msg5] → Consumer A (đọc từ offset 1)
                                            → Consumer B (đọc từ offset 3)
                                            → Consumer C (đọc từ offset 1, replay)
```

- Messages được **lưu trữ vĩnh viễn** (hoặc theo retention policy)
- Consumer đọc bằng **offset/position** — có thể replay
- Nhiều consumer groups đọc **độc lập** từ cùng stream
- **Analogy**: Cuốn sổ ghi chép — ai cũng có thể mở đọc lại từ trang bất kỳ
- **Use case**: Event sourcing, audit log, CDC, analytics pipeline

#### Trade-off Analysis

| Tiêu chí | Queue | Pub/Sub | Stream |
|----------|-------|---------|--------|
| **Message ownership** | 1 consumer | Tất cả subscribers | Tất cả consumer groups |
| **Ordering** | FIFO trong queue | Không đảm bảo | Per-partition ordering |
| **Replay** | ❌ Không | ❌ Không | ✅ Có |
| **Retention** | Xóa sau consume | Không lưu | Lưu theo policy |
| **Fan-out** | ❌ Competing | ✅ Broadcast | ✅ Consumer groups |
| **Throughput** | Trung bình (~10K/s) | Cao (~100K/s) | Rất cao (~1M/s) |
| **Complexity** | Thấp | Thấp | Cao |
| **Broker** | RabbitMQ | NATS, RabbitMQ | Kafka, NATS JetStream |

---

### 4.3 Broker vs Distributed Log

#### WHY — Tại sao phải phân biệt?

Khi nghe "message broker", nhiều người nghĩ tất cả đều giống nhau. Thực tế có 2 triết lý thiết kế hoàn toàn khác:

**Smart broker, dumb consumer** (RabbitMQ, NATS core):
- Broker quyết định routing, delivery, retry
- Consumer chỉ cần connect và nhận message
- Broker track trạng thái của từng message

**Dumb broker, smart consumer** (Kafka):
- Broker chỉ lưu trữ và serve data (append-only log)
- Consumer tự quản lý offset, tự quyết định đọc từ đâu
- Broker không track ai đã đọc gì

```
RabbitMQ (Smart Broker):
┌─────────────────────────────┐
│  Broker quyết định:         │
│  - Route msg đến đâu?       │
│  - Ai đã ack?               │
│  - Retry bao nhiêu lần?     │
│  - Dead letter khi nào?     │
└─────────────────────────────┘

Kafka (Distributed Log):
┌─────────────────────────────┐
│  Broker chỉ:                │
│  - Append msg vào log       │
│  - Serve msg theo offset    │
│  Consumer tự:               │
│  - Track offset             │
│  - Quyết định replay        │
│  - Handle failures          │
└─────────────────────────────┘
```

| Tiêu chí | Smart Broker (RabbitMQ) | Distributed Log (Kafka) |
|----------|------------------------|------------------------|
| **Routing logic** | Broker (exchanges, bindings) | Client (partitioner) |
| **Message tracking** | Broker tracks per-message | Consumer tracks offset |
| **Replay** | Không (msg bị xóa sau ack) | Có (log immutable) |
| **Throughput** | ~50K msg/s per node | ~1M msg/s per node |
| **Latency** | ~1ms | ~5ms |
| **Storage** | RAM + disk (tạm thời) | Disk only (lâu dài) |
| **Best for** | Task queues, routing phức tạp | Event streaming, audit, CDC |

---

### 4.4 NATS — Core concepts

#### WHY — Tại sao NATS?

NATS được thiết kế với triết lý **simplicity first**:
- Single binary, zero dependencies, ~15MB
- Startup trong milliseconds
- Protocol đơn giản (text-based, giống HTTP)
- Latency cực thấp trong điều kiện tối ưu (~100μs local, payload nhỏ, no persistence)
- Có sẵn pub/sub, queue groups, request-reply

**Khi nào chọn NATS?**
- Cần messaging đơn giản, nhanh, ít overhead
- Microservices communication (service mesh nhẹ)
- IoT với hàng triệu connections
- Request-reply thay thế HTTP nội bộ

#### WHAT — Kiến trúc NATS

```
┌──────────────────────────────────────────────┐
│                 NATS Server                   │
│                                              │
│   Subjects: orders.created                   │
│             orders.*.shipped                 │
│             payments.>                       │
│                                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│   │ Client A│  │ Client B│  │ Client C│    │
│   │Publisher │  │Subscriber│ │Subscriber│   │
│   └─────────┘  └─────────┘  └─────────┘    │
└──────────────────────────────────────────────┘
```

**Subject**: Địa chỉ định danh cho message (giống topic). NATS dùng string với dấu `.` phân cách hierarchy.

```
orders.created          → cụ thể: order mới tạo
orders.us.created       → cụ thể theo region
orders.*.created        → wildcard 1 level: orders.us.created, orders.eu.created
orders.>                → wildcard nhiều level: orders.us.created, orders.eu.shipped.tracking
```

**Wildcard rules:**
- `*` matches **1 token** (1 level): `orders.*` matches `orders.created` nhưng KHÔNG match `orders.us.created`
- `>` matches **1 hoặc nhiều tokens** (phải ở cuối): `orders.>` matches `orders.created`, `orders.us.created`, `orders.eu.shipped`

#### HOW — Publish/Subscribe flow

```
1. Client B subscribe("orders.created")
2. Client C subscribe("orders.created")
3. Client A publish("orders.created", data)
4. NATS server nhận msg, tìm tất cả subscribers match subject
5. Server gửi copy đến cả Client B và Client C
6. Cả B và C nhận message (fan-out)
```

Đặc điểm quan trọng:
- **At-most-once delivery** (NATS core): nếu subscriber offline, message bị mất
- **Fire-and-forget**: publisher không biết có ai nhận hay không
- **No persistence**: message không được lưu trữ (cần JetStream cho persistence — Day 2)

---

### 4.5 Queue Groups — Load Balancing

#### WHY

Pub/sub mặc định fan-out: tất cả subscribers nhận message. Nhưng khi bạn muốn **distribute work** (mỗi message chỉ 1 worker xử lý), bạn cần Queue Groups.

#### WHAT

```
Publisher → [NATS] → Queue Group "workers"
                        ├─ Worker 1 (nhận msg A)
                        ├─ Worker 2 (nhận msg B)  ← round-robin
                        └─ Worker 3 (nhận msg C)
                   → Subscriber D (nhận TẤT CẢ messages — không trong queue group)
```

- Subscribers cùng queue group → chỉ 1 subscriber nhận mỗi message (competing consumers)
- Subscribers khác queue group hoặc không có group → nhận tất cả (fan-out bình thường)
- Có thể kết hợp queue groups + regular subscribers trên cùng subject

---

### 4.6 Request-Reply Pattern

#### WHY

Đôi khi bạn cần async communication nhưng vẫn muốn **nhận response** — giống HTTP nhưng qua message broker. NATS hỗ trợ native request-reply.

#### HOW

```
1. Client A tạo unique inbox subject: _INBOX.abc123
2. Client A subscribe("_INBOX.abc123") — chờ response
3. Client A publish("orders.get", data, reply="_INBOX.abc123")
4. Client B (subscriber của "orders.get") nhận msg + reply subject
5. Client B publish("_INBOX.abc123", response_data)
6. Client A nhận response trên inbox subject
```

```
Client A                    NATS                    Client B
   |                         |                         |
   |-- publish "orders.get" -|-> deliver to Client B --|
   |   reply="_INBOX.xyz"    |                         |
   |                         |                         |
   |                         |<- publish "_INBOX.xyz" -|
   |<-- deliver response ----|                         |
```

**So sánh với HTTP:**

| Tiêu chí | HTTP | NATS Request-Reply |
|----------|------|-------------------|
| Discovery | URL/DNS cố định | Subject-based (bất kỳ ai subscribe đều handle được) |
| Load balancing | Cần LB riêng (nginx, envoy) | Queue groups — built-in |
| Timeout | TCP timeout | Configurable per-request |
| Coupling | URL coupling | Subject coupling (lỏng hơn) |
| Multi-response | ❌ 1 request = 1 response | ✅ Có thể nhận nhiều responses (scatter-gather) |

---

## 5. Trade-off Analysis tổng hợp

### NATS Core — Khi nào dùng, khi nào KHÔNG

| ✅ Dùng khi | ❌ KHÔNG dùng khi |
|------------|------------------|
| Cần messaging đơn giản, nhanh | Cần guaranteed delivery (dùng JetStream hoặc Kafka) |
| Service-to-service communication | Cần message persistence / replay |
| Request-reply thay HTTP nội bộ | Cần routing phức tạp (dùng RabbitMQ) |
| IoT / edge computing (nhẹ) | Cần event sourcing / audit log (dùng Kafka) |
| Real-time notifications | Cần strict ordering hoặc exactly-once end-to-end |

### Messaging Model chọn thế nào?

```
Bạn cần gì?
│
├─ "Mỗi task chỉ 1 worker xử lý" → Queue (RabbitMQ, NATS Queue Group)
│
├─ "Tất cả services đều cần biết" → Pub/Sub (NATS, RabbitMQ fanout)
│
├─ "Cần replay, audit, nhiều consumer groups" → Stream (Kafka, NATS JetStream)
│
└─ "Cần response cho request qua broker" → Request-Reply (NATS native, RabbitMQ RPC)
```

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Subject naming convention**: Dùng hierarchy rõ ràng
   ```
   ✅ orders.us.created
   ✅ payments.processed
   ✅ notifications.email.sent
   
   ❌ order_created (không hierarchy)
   ❌ Orders.Created (tránh uppercase — NATS case-sensitive)
   ❌ orders (quá chung chung)
   ```

2. **Dùng correlation ID và structured logs ngay từ Day 1**
   - Mỗi message nên có `correlation_id` để nối log giữa producer và consumer.
   - Nếu message sinh ra từ message khác, thêm `causation_id` = `message_id` của message nguồn.
   - Log tối thiểu theo schema nhất quán:
   ```json
   {
     "ts": "2026-05-07T10:15:30Z",
     "level": "info",
     "service": "order-service",
     "subject": "orders.created",
     "message_id": "msg-01H...",
     "correlation_id": "corr-01H...",
     "causation_id": "cmd-01H...",
     "event": "message_published"
   }
   ```
   - Với NATS core, header là nơi tự nhiên để truyền `correlation_id`; với CLI lab có thể để trong JSON payload cho dễ quan sát.

3. **Luôn set timeout cho request-reply**: Không set → client treo vô hạn nếu không có responder

4. **Dùng queue groups khi scale horizontally**: Tránh duplicate processing

5. **Đừng dùng NATS core cho critical data**: NATS core là at-most-once — message có thể mất. Dùng JetStream (Day 2) cho durable delivery + ack, và vẫn thiết kế idempotent consumer

### Common Pitfalls

1. **Pitfall: Nghĩ pub/sub = guaranteed delivery**
   - NATS core KHÔNG lưu message. Subscriber offline = message mất
   - Fix: Dùng JetStream cho persistence

2. **Pitfall: Wildcard `>` bắt quá nhiều**
   - `>` ở cuối match mọi thứ phía sau → subscribe quá rộng
   - Fix: Cụ thể hóa subject, dùng `*` thay `>` khi có thể

3. **Pitfall: Subject quá flat**
   - `orderCreated`, `orderShipped` → không tận dụng được wildcards
   - Fix: `orders.created`, `orders.shipped` → subscribe `orders.*` hoặc `orders.>`

---

## 7. Performance Considerations

### Benchmark numbers (order of magnitude)

Các số này chỉ dùng để so sánh bậc lớn. Benchmark thực tế phải ghi rõ message size, persistence on/off, TLS, số clients, batching, CPU, NIC, disk và số broker nodes.

| Metric | NATS Core | So sánh |
|--------|-----------|---------|
| Throughput | ~10-15 triệu msg/s (small messages) | Nhanh hơn Kafka cho small msg |
| Latency | ~100μs (local), ~500μs (cross-DC) | Thấp hơn RabbitMQ và Kafka |
| Connections | ~1 triệu concurrent | Hơn RabbitMQ (~100K) |
| Message size | Tối ưu cho <1KB | Kafka tối ưu cho >1KB batching |
| Memory footprint | ~20MB server | RabbitMQ ~100MB+, Kafka ~1GB+ |

### Key metrics cần monitor

- **Connections**: Số client connections
- **Messages in/out**: Throughput rate
- **Bytes in/out**: Bandwidth usage
- **Slow consumers**: Consumers không kịp xử lý
- **Subscription count**: Số active subscriptions

### Khi nào NATS core KHÔNG đủ nhanh?

- Message size lớn (>1MB) → cân nhắc object store hoặc chia nhỏ
- Cần persistence → throughput giảm khi bật JetStream
- Cross-region latency → leaf nodes và super-cluster (Day 3)

---

## 8. Hands-on Lab

### 8.1 Setup NATS với Docker

Tạo file `docker-compose.yml`:

```yaml
version: "3.8"
services:
  nats:
    image: nats:2.10-alpine
    ports:
      - "4222:4222"   # Client connections
      - "8222:8222"   # HTTP monitoring
      - "6222:6222"   # Cluster routing
    command: ["--http_port", "8222", "--js"]  # Bật sẵn JetStream để Day 2 dùng lại volume/lab; Day 1 vẫn chỉ học NATS core
    volumes:
      - nats-data:/data

volumes:
  nats-data:
```

Khởi động:
```bash
docker compose up -d
# Verify
docker compose logs nats
# Kiểm tra monitoring endpoint
curl http://localhost:8222/varz
```

Cài NATS CLI (tool chính thức để test):
```bash
# macOS
brew install nats-io/nats-tools/nats

# Linux/Windows — download binary
# https://github.com/nats-io/natscli/releases

# Verify
nats --version
```

### 8.2 Lab 1: Pub/Sub cơ bản với NATS CLI

Mở 3 terminal:

**Terminal 1 — Subscriber 1:**
```bash
nats sub "orders.>"
```

**Terminal 2 — Subscriber 2:**
```bash
nats sub "orders.created"
```

**Terminal 3 — Publisher:**
```bash
# Gửi message
nats pub "orders.created" '{"orderId": "123", "item": "laptop", "qty": 1}'
nats pub "orders.shipped" '{"orderId": "123", "carrier": "fedex"}'
nats pub "orders.us.created" '{"orderId": "456", "region": "us"}'
```

**Quan sát:**
- Terminal 1 (`orders.>`) nhận TẤT CẢ 3 messages
- Terminal 2 (`orders.created`) chỉ nhận message đầu tiên
- Wildcard `>` match mọi thứ, `orders.created` chỉ exact match

### 8.3 Lab 2: Queue Groups

**Terminal 1 — Worker 1:**
```bash
nats sub "tasks.process" --queue workers
```

**Terminal 2 — Worker 2:**
```bash
nats sub "tasks.process" --queue workers
```

**Terminal 3 — Publisher:**
```bash
for i in $(seq 1 10); do
  nats pub "tasks.process" "task-$i"
done
```

**Quan sát:**
- 10 messages được phân đều giữa Worker 1 và Worker 2
- Mỗi message chỉ 1 worker nhận (competing consumers)
- Thêm `--queue workers` biến subscriber thành queue group member

### 8.4 Lab 3: Request-Reply với NATS CLI

Từ đây trở đi là phần nên làm nếu còn thời gian trong buổi Day 1. Must Learn của ngày này là pub/sub, queue group và convention log/correlation; request-reply Go và monitoring có thể làm sau mà không ảnh hưởng Day 2.

**Terminal 1 — Responder (service):**
```bash
nats reply "greet.hello" "Xin chào, {{.Msg}}!"
```

**Terminal 2 — Requester:**
```bash
nats request "greet.hello" "NATS User"
```

**Output:**
```
Published 9 bytes to "greet.hello"
Received with rtt 1.234ms
Xin chào, NATS User!
```

### 8.5 Lab 4: Pub/Sub với Go

Tạo project Go:
```bash
mkdir -p nats-lab && cd nats-lab
go mod init nats-lab
go get github.com/nats-io/nats.go
```

**File `publisher.go`:**
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

func logMessage(event, subject, messageID, correlationID string) {
	log.Printf("event=%s subject=%s message_id=%s correlation_id=%s",
		event, subject, messageID, correlationID)
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	for i := 1; i <= 5; i++ {
		order := OrderEvent{
			OrderID:   fmt.Sprintf("ORD-%03d", i),
			Item:      "laptop",
			Quantity:  i,
			CreatedAt: time.Now(),
		}

		data, _ := json.Marshal(order)
		messageID := fmt.Sprintf("msg-%s", order.OrderID)
		correlationID := fmt.Sprintf("corr-%s", order.OrderID)

		// Publish lên subject "orders.created" với headers để trace xuyên service.
		msg := nats.NewMsg("orders.created")
		msg.Data = data
		msg.Header.Set("Nats-Msg-Id", messageID)
		msg.Header.Set("Correlation-Id", correlationID)
		msg.Header.Set("Causation-Id", "checkout-command")

		err := nc.PublishMsg(msg)
		if err != nil {
			log.Printf("Publish error: %v", err)
			continue
		}

		logMessage("message_published", "orders.created", messageID, correlationID)
		time.Sleep(500 * time.Millisecond)
	}

	// Flush đảm bảo tất cả messages đã gửi đến server
	nc.Flush()
	log.Println("All orders published")
}
```

**File `subscriber.go`:**
```go
package main

import (
	"encoding/json"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/nats-io/nats.go"
)

type OrderEvent struct {
	OrderID   string `json:"order_id"`
	Item      string `json:"item"`
	Quantity  int    `json:"quantity"`
	CreatedAt string `json:"created_at"`
}

func logMessage(event, subject, orderID, messageID, correlationID, causationID string) {
	log.Printf("event=%s subject=%s order_id=%s message_id=%s correlation_id=%s causation_id=%s",
		event, subject, orderID, messageID, correlationID, causationID)
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	// Subscribe tất cả events trong domain "orders"
	sub, err := nc.Subscribe("orders.>", func(msg *nats.Msg) {
		var order OrderEvent
		if err := json.Unmarshal(msg.Data, &order); err != nil {
			log.Printf("Unmarshal error: %v", err)
			return
		}

		logMessage(
			"message_consumed",
			msg.Subject,
			order.OrderID,
			msg.Header.Get("Nats-Msg-Id"),
			msg.Header.Get("Correlation-Id"),
			msg.Header.Get("Causation-Id"),
		)
	})
	if err != nil {
		log.Fatal(err)
	}
	defer sub.Unsubscribe()

	log.Println("Subscriber listening on 'orders.>'...")

	// Graceful shutdown
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	log.Println("Shutting down subscriber")
}
```

**Chạy:**
```bash
# Terminal 1 — chạy subscriber trước
go run subscriber.go

# Terminal 2 — chạy publisher
go run publisher.go
```

### 8.6 Lab 5: Request-Reply với Go

**File `service.go`:**
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/nats-io/nats.go"
)

type PriceRequest struct {
	Item string `json:"item"`
}

type PriceResponse struct {
	Item  string  `json:"item"`
	Price float64 `json:"price"`
	Unit  string  `json:"unit"`
}

var priceDB = map[string]float64{
	"laptop": 999.99,
	"phone":  699.99,
	"tablet": 449.99,
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	// Subscribe và auto-reply qua msg.Reply
	sub, err := nc.Subscribe("pricing.lookup", func(msg *nats.Msg) {
		var req PriceRequest
		if err := json.Unmarshal(msg.Data, &req); err != nil {
			log.Printf("Bad request: %v", err)
			return
		}

		price, ok := priceDB[req.Item]
		if !ok {
			// Trả error response thay vì không trả gì — caller cần biết item không tồn tại
			nc.Publish(msg.Reply, []byte(`{"error":"item not found"}`))
			return
		}

		resp := PriceResponse{Item: req.Item, Price: price, Unit: "USD"}
		data, _ := json.Marshal(resp)
		nc.Publish(msg.Reply, data)

		log.Printf("Replied price for %s: $%.2f", req.Item, price)
	})
	if err != nil {
		log.Fatal(err)
	}
	defer sub.Unsubscribe()

	log.Println("Pricing service ready on 'pricing.lookup'")

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig

	fmt.Println("Pricing service stopped")
}
```

**File `client.go`:**
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/nats-io/nats.go"
)

type PriceRequest struct {
	Item string `json:"item"`
}

type PriceResponse struct {
	Item  string  `json:"item"`
	Price float64 `json:"price"`
	Unit  string  `json:"unit"`
	Error string  `json:"error,omitempty"`
}

func main() {
	nc, err := nats.Connect(nats.DefaultURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Close()

	items := []string{"laptop", "phone", "unknown_item"}

	for _, item := range items {
		req := PriceRequest{Item: item}
		data, _ := json.Marshal(req)

		// Request với timeout 2 giây — nếu không có service nào reply, sẽ timeout
		msg, err := nc.Request("pricing.lookup", data, 2*time.Second)
		if err != nil {
			log.Printf("Request for %s failed: %v", item, err)
			continue
		}

		var resp PriceResponse
		json.Unmarshal(msg.Data, &resp)

		if resp.Error != "" {
			fmt.Printf("❌ %s: %s\n", item, resp.Error)
		} else {
			fmt.Printf("✅ %s: $%.2f %s\n", resp.Item, resp.Price, resp.Unit)
		}
	}
}
```

**Chạy:**
```bash
# Terminal 1 — pricing service
go run service.go

# Terminal 2 — client
go run client.go
```

**Output expected:**
```
✅ laptop: $999.99 USD
✅ phone: $699.99 USD
❌ unknown_item: item not found
```

### 8.7 Lab 6: Monitoring cơ bản

```bash
# Server health
curl -s http://localhost:8222/varz | jq '.server_id, .mem, .connections'

# Connections info
curl -s http://localhost:8222/connz | jq '.connections[] | {name, ip, subscriptions}'

# Subscriptions detail
curl -s http://localhost:8222/subsz?subs=1 | jq .

# Routes (clustering — sẽ dùng Day 3)
curl -s http://localhost:8222/routez | jq .
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Khi nào bạn chọn async communication thay vì sync?** Cho 2 ví dụ cụ thể trong hệ thống e-commerce nơi async là lựa chọn đúng, và giải thích tại sao sync sẽ gây vấn đề ở đó.

2. **Queue model và Pub/Sub model khác nhau cốt lõi ở điểm nào?** Nếu bạn có 3 instances của notification service và dùng pub/sub thông thường, điều gì sẽ xảy ra khi có 1 event "order.created"? Làm sao fix?

3. **Tại sao NATS core được gọi là "at-most-once delivery"?** Điều này có nghĩa gì trong production? Cho scenario cụ thể khi việc mất message là chấp nhận được và khi nào thì không.

4. **Giải thích sự khác biệt giữa wildcard `*` và `>` trong NATS.** Cho subject hierarchy `orders.{region}.{action}`, viết subscription pattern để: (a) nhận tất cả orders từ region "us", (b) nhận tất cả actions trên tất cả regions.

5. **Request-reply trong NATS hoạt động thế nào "under the hood"?** Tại sao nó tốt hơn HTTP cho internal service communication trong một số trường hợp? Khi nào HTTP vẫn là lựa chọn tốt hơn?

6. **Design question**: Bạn đang xây dựng hệ thống notification cho app. Có 3 loại notification: email, SMS, push. Mỗi loại có service riêng. Khi user đặt hàng, cả 3 loại notification đều cần gửi. Bạn sẽ thiết kế subject hierarchy và subscription model như thế nào với NATS? Queue groups có vai trò gì ở đây?

   *Hint: Nghĩ về việc kết hợp pub/sub (fan-out đến các loại notification) với queue groups (scale mỗi loại horizontally).*

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [NATS Documentation](https://docs.nats.io/)
- [NATS Go Client](https://github.com/nats-io/nats.go)
- [NATS CLI](https://github.com/nats-io/natscli)

### Architecture & Design
- [NATS Architecture](https://docs.nats.io/nats-concepts/overview)
- [Subject-Based Messaging](https://docs.nats.io/nats-concepts/subjects)
- [Queue Groups](https://docs.nats.io/nats-concepts/core-nats/queue)
- [Request-Reply](https://docs.nats.io/nats-concepts/core-nats/reqreply)

### Comparison & Decision Making
- [Choosing between messaging systems](https://docs.nats.io/compare) — NATS official comparison
- [Martin Kleppmann — Designing Data-Intensive Applications](https://dataintensive.net/) — Chapter 11: Stream Processing

### Videos
- [NATS: A Cloud Native Messaging System — KubeCon](https://www.youtube.com/watch?v=t_USu3FwYgA)
- [Derek Collison — NATS Deep Dive](https://www.youtube.com/watch?v=RfE3mM6VD3E)
