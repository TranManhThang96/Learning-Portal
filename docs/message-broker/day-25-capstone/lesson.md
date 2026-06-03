# Day 25: Capstone Project — E-commerce Event-Driven System Design & Implementation

> Companion split: xem `document.md` để đào sâu architecture/runbook và `exercises.md` để làm acceptance drills riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Thiết kế** kiến trúc event-driven hoàn chỉnh cho hệ thống e-commerce: Order → Payment → Inventory → Notification
2. **Implement ở mức reference snippets** event catalog, schema design, naming convention, versioning strategy
3. **Xây dựng thiết kế** transactional outbox + idempotent consumer (inbox table) pattern
4. **Thực hành trên giấy và snippet** saga choreography: happy path, failure compensation, timeout handling
5. **Chuẩn bị** monitoring checklist: Prometheus metrics, consumer lag alerting + structured logging

## 2. Kiến thức nền (Prerequisites)

- **Tất cả** Day 1-24 — bài này tổng hợp mọi kiến thức đã học
- Cụ thể cần:
  - Kafka producer/consumer, consumer groups (Day 10-12)
  - Delivery semantics, idempotency (Day 15)
  - Schema design (Day 16)
  - Monitoring, observability, correlation ID (Day 23)
  - Trade-off analysis giữa 3 brokers (Day 24)
- Docker Compose, Go programming, PostgreSQL basics

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Architecture design — Mode A (Kafka-only, minimal production)
- Event catalog — tất cả events với schema
- Outbox + Inbox pattern implementation
- Saga choreography — happy path + payment failure compensation
- Go reference snippets cho 4 services; bài này không claim runnable end-to-end trong 2 giờ
- Correlation ID propagation + structured logging

### 🟡 Should Learn (nếu còn thời gian)
- Mode B (polyglot: Kafka + RabbitMQ + NATS)
- Dead letter topic consumer + manual replay
- Prometheus + Grafana monitoring setup
- Runbook cho common incidents

### 🟢 Optional Deep Dive
- Saga timeout handling (payment never responds)
- Schema evolution (v1 → v2 migration)
- Load testing + failure injection
- Full observability: OpenTelemetry traces + Grafana dashboards
- Production deployment checklist

---

## 4. Lý thuyết (Theory)

### 4.1 System Architecture — Mode A (Minimal Production Design)

#### WHY — Tại sao Kafka-only là đủ cho hầu hết teams?

```
MODE A vs MODE B:

  Mode A: "Kafka does everything"
  → 1 messaging system to operate
  → 1 monitoring setup
  → 1 team expertise needed
  → Trade-off: Kafka retry/DLQ không elegant bằng RabbitMQ DLX
  → RECOMMENDATION: Start here. 90% teams không cần Mode B.

  Mode B: "Right tool for right job"
  → Kafka (events) + RabbitMQ (tasks) + NATS (real-time)
  → Better fit per use case
  → 3x operational complexity
  → ONLY when: clear pain point with Mode A + team có resources
```

```
MODE A — ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  ┌──────────┐     REST API      ┌─────────────────┐            │
  │  │  Client   │ ───────────────► │  Order Service   │            │
  │  │  (HTTP)   │  POST /orders    │                  │            │
  │  └──────────┘                   │  ┌────────────┐  │            │
  │                                 │  │ PostgreSQL │  │            │
  │                                 │  │ ┌────────┐ │  │            │
  │                                 │  │ │ orders │ │  │            │
  │                                 │  │ │ outbox │ │  │            │
  │                                 │  │ └────────┘ │  │            │
  │                                 │  └────────────┘  │            │
  │                                 │       │          │            │
  │                                 │  Outbox Poller   │            │
  │                                 │  (reads outbox,  │            │
  │                                 │   publishes to   │            │
  │                                 │   Kafka)         │            │
  │                                 └───────┬──────────┘            │
  │                                         │                       │
  │                                         ▼                       │
  │                              ┌──────────────────┐               │
  │                              │   Kafka Topics    │               │
  │                              │                   │               │
  │                              │ • orders.created  │               │
  │                              │ • payments.done   │               │
  │                              │ • payments.failed │               │
  │                              │ • inventory.ok    │               │
  │                              │ • inventory.fail  │               │
  │                              │ • orders.completed│               │
  │                              │ • orders.cancelled│               │
  │                              │ • notifications   │               │
  │                              │ • *.dlq (dead     │               │
  │                              │   letter topics)  │               │
  │                              └──────┬───────────┘               │
  │                    ┌────────────────┼──────────────┐            │
  │                    ▼                ▼              ▼            │
  │  ┌─────────────────────┐ ┌─────────────────┐ ┌──────────────┐  │
  │  │  Payment Service    │ │Inventory Service│ │ Notification │  │
  │  │                     │ │                 │ │ Service      │  │
  │  │  ┌───────────────┐  │ │ ┌─────────────┐ │ │              │  │
  │  │  │ PostgreSQL    │  │ │ │ PostgreSQL  │ │ │ (sink only,  │  │
  │  │  │ ┌───────────┐ │  │ │ │ ┌─────────┐ │ │ │  no outbox)  │  │
  │  │  │ │ payments  │ │  │ │ │ │inventory│ │ │ │              │  │
  │  │  │ │ inbox     │ │  │ │ │ │ inbox   │ │ │ │  Logs email/ │  │
  │  │  │ │ outbox    │ │  │ │ │ │ outbox  │ │ │ │  SMS to      │  │
  │  │  │ └───────────┘ │  │ │ │ └─────────┘ │ │ │  stdout      │  │
  │  │  └───────────────┘  │ │ └─────────────┘ │ │              │  │
  │  └─────────────────────┘ └─────────────────┘ └──────────────┘  │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

### 4.2 Event Catalog — Naming Convention & Schema

```
EVENT NAMING CONVENTION:

  Pattern: {domain}.{entity}.{action}.{version}
  
  Examples:
  ┌─────────────────────────────────────────────────────────────┐
  │ Event Name                    │ Producer          │ Action  │
  ├───────────────────────────────┼───────────────────┼─────────┤
  │ order.order.created.v1        │ Order Service     │ Saga    │
  │ order.order.completed.v1      │ Order Service     │ start   │
  │ order.order.cancelled.v1      │ Order Service     │ Saga end│
  │                               │                   │         │
  │ payment.payment.completed.v1  │ Payment Service   │ Saga    │
  │ payment.payment.failed.v1     │ Payment Service   │ step    │
  │                               │                   │         │
  │ inventory.stock.reserved.v1   │ Inventory Service │ Saga    │
  │ inventory.stock.insufficient.v1│ Inventory Service│ step    │
  │ inventory.stock.released.v1   │ Inventory Service │ Compen- │
  │                               │                   │ sation  │
  │ notification.email.sent.v1    │ Notification Svc  │ Sink    │
  └─────────────────────────────────────────────────────────────┘

  Kafka Topic mapping:
  - Topic per event type: order.order.created.v1
  - OR topic per domain: order-events, payment-events
  
  RECOMMENDATION: Topic per domain (fewer topics, easier ops)
  → order-events (contains: created, completed, cancelled)
  → payment-events (contains: completed, failed, refund.requested, refund.completed)
  → inventory-events (contains: reserved, insufficient, released)
  → notification-events (contains: email.sent)
  → Use event type in message header for filtering
  → Không publish payment.completed vào inventory-events; Inventory Service subscribe payment-events và publish kết quả của chính nó vào inventory-events.
```

#### Event Envelope Schema

```
EVENT ENVELOPE — Standard structure cho MỌI event:

  {
    // === Metadata (system fields) ===
    "eventId":       "evt_01HQ...",      // Unique ID (ULID/UUID)
    "eventType":     "order.order.created.v1",
    "timestamp":     "2024-01-15T10:30:00.000Z",
    "correlationId": "req_abc123",       // Original request ID
    "causationId":   "evt_01HP...",      // Parent event ID
    "source":        "order-service",    // Producer service
    "version":       1,                  // Schema version
    
    // === Domain payload (business data) ===
    "data": {
      "orderId":    "ORD-20240115-001",
      "customerId": "CUST-789",
      "items": [
        {"productId": "PROD-001", "quantity": 2, "price": 29.99},
        {"productId": "PROD-005", "quantity": 1, "price": 49.99}
      ],
      "totalAmount": 109.97,
      "currency":    "USD"
    }
  }


ALL EVENT SCHEMAS:

  ┌─────────────────────────────────────────────────────────────┐
  │ order.order.created.v1                                      │
  │ data: { orderId, customerId, items[], totalAmount, currency}│
  │                                                             │
  │ payment.payment.completed.v1                                │
  │ data: { paymentId, orderId, amount, method, transactionRef, │
  │         items[] }                                            │
  │                                                             │
  │ payment.payment.failed.v1                                   │
  │ data: { paymentId, orderId, amount, reason, errorCode }     │
  │                                                             │
  │ inventory.stock.reserved.v1                                 │
  │ data: { reservationId, orderId, items[{productId, qty}] }   │
  │                                                             │
  │ inventory.stock.insufficient.v1                             │
  │ data: { orderId, items[{productId, requested, available}] } │
  │                                                             │
  │ inventory.stock.released.v1     (compensation)              │
  │ data: { reservationId, orderId, reason }                    │
  │                                                             │
  │ order.order.completed.v1                                    │
  │ data: { orderId, completedAt }                              │
  │                                                             │
  │ order.order.cancelled.v1        (compensation)              │
  │ data: { orderId, reason, cancelledAt }                      │
  │                                                             │
  │ notification.email.requested.v1                             │
  │ data: { recipientEmail, template, templateData }            │
  └─────────────────────────────────────────────────────────────┘
```

### 4.3 Saga Choreography — Flow Design

```
SAGA CHOREOGRAPHY — Happy Path:

  ┌──────────┐   order.order    ┌──────────┐  payment.payment  ┌──────────┐
  │  Order   │   .created.v1    │ Payment  │  .completed.v1    │Inventory │
  │ Service  │────────────────►│ Service  │───────────────────►│ Service  │
  │          │                  │          │                    │          │
  │ Create   │                  │ Charge   │                    │ Reserve  │
  │ order    │                  │ card     │                    │ stock    │
  │ (PENDING)│                  │          │                    │          │
  └──────────┘                  └──────────┘                    └────┬─────┘
       ▲                                                            │
       │                                                            │
       │   order.order          ┌──────────┐  inventory.stock       │
       │   .completed.v1        │  Notif   │  .reserved.v1          │
       │◄───────────────────────│ Service  │◄───────────────────────┘
       │                        │          │
       │ Update                 │ Send     │
       │ order                  │ email    │
       │ (COMPLETED)            │          │
       │                        └──────────┘
       │
       └── Update order status: PENDING → COMPLETED


SAGA CHOREOGRAPHY — Payment Failure:

  ┌──────────┐   order.order    ┌──────────┐
  │  Order   │   .created.v1    │ Payment  │
  │ Service  │────────────────►│ Service  │
  │          │                  │          │
  │ Create   │                  │ Charge   │
  │ order    │                  │ FAILS!   │
  │ (PENDING)│                  │          │
  └──────────┘                  └────┬─────┘
       ▲                             │
       │   payment.payment           │
       │   .failed.v1                │
       │◄────────────────────────────┘
       │
       │ COMPENSATE:
       │ Update order (CANCELLED)
       │ Publish order.order.cancelled.v1
       │
       └── Notification Service sends "order cancelled" email


SAGA CHOREOGRAPHY — Inventory Insufficient:

  Order ──created──► Payment ──completed──► Inventory
                                               │
                                          stock NOT enough!
                                               │
                                    inventory.stock.insufficient.v1
                                               │
       ┌───────────────────────────────────────┘
       ▼
  Order Service receives insufficient event:
  1. Publish payment.refund.requested.v1 (compensate payment)
  2. Update order status: CANCELLED
  3. Publish order.order.cancelled.v1
  
  Payment Service receives refund request:
  1. Process refund
  2. Publish payment.refund.completed.v1


SAGA TIMEOUT — Payment never responds:

  ┌──────────────────────────────────────────────────────────────┐
  │ Order Service creates order with:                            │
  │   status: PENDING                                            │
  │   created_at: now()                                          │
  │   timeout_at: now() + 15 minutes                             │
  │                                                              │
  │ Background job (cron / scheduler):                           │
  │   SELECT * FROM orders                                       │
  │   WHERE status = 'PENDING'                                   │
  │   AND timeout_at < now()                                     │
  │                                                              │
  │   For each timed-out order:                                  │
  │   1. Update status: CANCELLED (reason: timeout)              │
  │   2. Insert outbox: order.order.cancelled.v1                 │
  │   3. Log warning with correlationId                          │
  │                                                              │
  │ Important: Payment CÓ THỂ respond AFTER timeout             │
  │ → Order already cancelled → inbox table rejects duplicate    │
  │ → Payment service checks order status before processing      │
  └──────────────────────────────────────────────────────────────┘
```

### 4.4 Outbox & Inbox Pattern — Database Schema

```sql
-- === OUTBOX TABLE (mỗi service có 1) ===
-- Đảm bảo database write + event publish là atomic

CREATE TABLE outbox (
    id            BIGSERIAL PRIMARY KEY,
    event_id      VARCHAR(64) NOT NULL UNIQUE,
    event_type    VARCHAR(128) NOT NULL,
    owner_service VARCHAR(64) NOT NULL,      -- service owns this outbox row
    aggregate_id  VARCHAR(128) NOT NULL,    -- orderId, paymentId, etc.
    aggregate_type VARCHAR(64) NOT NULL,     -- "order", "payment", etc.
    payload       JSONB NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    causation_id  VARCHAR(64) NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    locked_at     TIMESTAMP,                -- poller lock marker
    published_at  TIMESTAMP                 -- NULL = not yet published
);

CREATE INDEX idx_outbox_unpublished
    ON outbox (owner_service, id)
    WHERE published_at IS NULL;

-- === INBOX TABLE (mỗi service có 1) ===
-- Đảm bảo idempotent consumer (process each event exactly once)

CREATE TABLE inbox (
    event_id      VARCHAR(64) PRIMARY KEY,  -- dedup key
    event_type    VARCHAR(128) NOT NULL,
    owner_service VARCHAR(64) NOT NULL,
    processed_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inbox_cleanup ON inbox (owner_service, processed_at);

-- Poller query production-safe:
-- SELECT * FROM outbox
-- WHERE owner_service = $1 AND published_at IS NULL
-- ORDER BY id
-- LIMIT 100
-- FOR UPDATE SKIP LOCKED;

-- === ORDERS TABLE ===
CREATE TABLE orders (
    id            VARCHAR(64) PRIMARY KEY,
    customer_id   VARCHAR(64) NOT NULL,
    items         JSONB NOT NULL,
    total_amount  DECIMAL(12,2) NOT NULL,
    currency      VARCHAR(3) NOT NULL DEFAULT 'USD',
    status        VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    -- PENDING → COMPLETED | CANCELLED
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    timeout_at    TIMESTAMP NOT NULL
);

-- === PAYMENTS TABLE ===
CREATE TABLE payments (
    id            VARCHAR(64) PRIMARY KEY,
    order_id      VARCHAR(64) NOT NULL,
    amount        DECIMAL(12,2) NOT NULL,
    method        VARCHAR(20) NOT NULL DEFAULT 'credit_card',
    status        VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    -- PENDING → COMPLETED | FAILED | REFUNDED
    transaction_ref VARCHAR(128),
    error_code    VARCHAR(20),
    error_reason  VARCHAR(256),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- === INVENTORY TABLE ===
CREATE TABLE inventory (
    product_id    VARCHAR(64) PRIMARY KEY,
    quantity      INTEGER NOT NULL DEFAULT 0,
    reserved      INTEGER NOT NULL DEFAULT 0,
    -- available = quantity - reserved
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE inventory_reservations (
    id            VARCHAR(64) PRIMARY KEY,
    order_id      VARCHAR(64) NOT NULL,
    product_id    VARCHAR(64) NOT NULL,
    quantity      INTEGER NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'RESERVED',
    -- RESERVED → CONFIRMED | RELEASED
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 4.5 Failure Handling Matrix

```
FAILURE HANDLING MATRIX:

  ┌──────────────────────────────────────────────────────────────────────┐
  │ Failure Point           │ Detection         │ Recovery              │
  ├─────────────────────────┼───────────────────┼───────────────────────┤
  │ Order creation fails    │ HTTP 500 to client│ Client retries        │
  │ (DB down)               │                   │ (idempotent API)      │
  │                         │                   │                       │
  │ Outbox poller crashes   │ No events published│ Restart poller.      │
  │                         │ Consumer lag = 0   │ Outbox has unpublished│
  │                         │ but orders PENDING │ events. Resume.       │
  │                         │                   │                       │
  │ Kafka unavailable       │ Outbox poller fails│ Poller retries with  │
  │                         │ to publish         │ backoff. Events queue │
  │                         │                   │ in outbox table.       │
  │                         │                   │                       │
  │ Payment service down    │ Consumer lag grows │ Kafka retains msgs.  │
  │                         │ Orders stay PENDING│ Service recovers →   │
  │                         │                   │ processes backlog.     │
  │                         │ Timeout triggers   │ Order cancelled after │
  │                         │ after 15 min       │ timeout.              │
  │                         │                   │                       │
  │ Payment gateway timeout │ Payment service    │ Retry 3x with backoff│
  │                         │ logs error         │ Then publish          │
  │                         │                   │ payment.failed        │
  │                         │                   │                       │
  │ Duplicate event         │ Inbox table check  │ Skip processing.     │
  │ (redelivery after crash)│ finds existing ID  │ Ack offset. Log.     │
  │                         │                   │                       │
  │ Poison message          │ Deserialization    │ Send to DLQ topic.   │
  │ (bad schema)            │ error              │ Alert. Manual review. │
  │                         │                   │                       │
  │ Inventory insufficient  │ Stock check fails  │ Publish insufficient.│
  │                         │                   │ Trigger compensation. │
  │                         │                   │                       │
  │ Consumer rebalance      │ Lag spikes, then   │ Cooperative sticky   │
  │                         │ recovers           │ assignor. Static     │
  │                         │                   │ membership.           │
  │                         │                   │                       │
  │ DB connection pool      │ Processing slows   │ Monitor pool metrics │
  │ exhausted               │ max.poll.interval  │ Tune pool size.      │
  │                         │ exceeded → rebalance│ Increase timeout.   │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### Mode A vs Mode B

| Tiêu chí | Mode A (Kafka only) | Mode B (Polyglot) |
|----------|--------------------|--------------------|
| Operational complexity | Thấp (1 system) | Cao (3 systems) |
| Team expertise | 1 broker to learn | 3 brokers to learn |
| Event backbone | Kafka ✓ | Kafka ✓ |
| Task queue | Kafka retry topics (OK) | RabbitMQ DLX (better) |
| Real-time push | Kafka consumer → WS (OK) | NATS → WS (better latency) |
| Monitoring | 1 stack | 3 stacks |
| Best for | 90% of teams | Teams với specific pain points |
| When to switch | When Kafka retry/DLQ becomes painful | Never start here |

### Outbox Polling vs CDC (Debezium)

| Tiêu chí | Outbox Polling | CDC (Debezium) |
|----------|---------------|----------------|
| Complexity | Thấp (simple SQL query) | Trung bình (Debezium + Connect) |
| Latency | 100ms-1s (polling interval) | ~100ms (near real-time) |
| DB load | Extra queries (polling) | Read WAL (minimal load) |
| Ordering | By outbox ID (guaranteed) | By WAL position (guaranteed) |
| Infrastructure | No extra (just code) | Kafka Connect + Debezium |
| Best for | Start here | High throughput, low latency needs |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. OUTBOX: Always write business data + outbox event in SAME transaction
   → BEGIN; INSERT INTO orders...; INSERT INTO outbox...; COMMIT;
   → NEVER publish to Kafka first, then write to DB (or vice versa)
   → Transaction guarantees both succeed or both fail

2. INBOX: Check BEFORE processing, not after
   → First: check inbox for event_id → if exists, skip
   → Then: process business logic
   → Then: insert into inbox + commit in SAME transaction
   → This gives idempotent at-least-once processing for your DB side effects.
   → It is not exactly-once end-to-end for external APIs like payment gateway/email.

3. CORRELATION ID: Generate at entry point, propagate everywhere
   → API Gateway generates correlationId for each HTTP request
   → Every Kafka message carries it in headers
   → Every log line includes it
   → Query: "show me everything for correlationId=req_abc" → full story

4. SAGA: Design compensation for EVERY step
   → If step N fails, compensate steps N-1, N-2, ..., 1
   → Compensation must be idempotent (can run multiple times safely)
   → Order: created → cancelled (compensation)
   → Payment: charged → refunded (compensation)
   → Inventory: reserved → released (compensation)

5. DLQ: Every consumer MUST have a DLQ strategy
   → Deserialization error → DLQ immediately (no retry will fix it)
   → Processing error → retry 3x → then DLQ
   → DLQ consumer: alert team, store for manual replay
   → NEVER silently drop messages

6. OFFSET COMMIT: Commit Kafka offset only after durable side effects
   → OK: DB transaction committed + outbox/inbox written → commit offset
   → NOT OK: handler returned error / DB rollback / outbox insert failed → do not commit
   → Bad payload: write DLQ record first, then commit original offset
```

### Common Pitfalls

```
❌ PITFALL 1: Publishing to Kafka outside of outbox
   Sai:  db.Save(order) → kafka.Publish(event) → nếu Kafka fail → data inconsistent
   Đúng: db.Transaction { save(order) + save(outbox) } → poller publishes

❌ PITFALL 2: Inbox check race condition
   Sai:  if !inbox.exists(eventId) { process(); inbox.save(eventId) }
         → 2 consumers process same event concurrently!
   Đúng: Use database UNIQUE constraint on event_id
         → Second INSERT fails → skip processing

❌ PITFALL 3: Compensation not idempotent
   Sai:  refund(orderId) → charge -$100 EVERY time called
   Đúng: refund is idempotent → check if already refunded → skip

❌ PITFALL 4: No timeout for saga
   Sai:  Order stays PENDING forever if Payment never responds
   Đúng: timeout_at = created_at + 15 min → background job cancels

❌ PITFALL 5: Logging without correlationId
   Sai:  log.Info("Payment processed") → WHICH order? WHICH request?
   Đúng: log.Info("Payment processed", "correlationId", cid, "orderId", oid)
```

---

## 7. Performance Considerations

```
PERFORMANCE TARGETS cho E-commerce Event-Driven System:

  ┌────────────────────────────────────────────────────────────┐
  │ Metric                    │ Target         │ Alert Threshold│
  ├───────────────────────────┼────────────────┼────────────────┤
  │ Order creation (API)      │ p99 < 200ms    │ > 500ms        │
  │ Event publish (outbox→KF) │ p99 < 500ms    │ > 2s           │
  │ Payment processing        │ p99 < 5s       │ > 15s          │
  │ End-to-end saga           │ p99 < 10s      │ > 30s          │
  │ Consumer lag (payment)    │ < 100 msgs     │ > 1000 msgs    │
  │ Consumer lag (notif)      │ < 1000 msgs    │ > 10000 msgs   │
  │ DLQ message count         │ 0              │ > 10           │
  │ Outbox unpublished age    │ < 1s           │ > 10s          │
  └────────────────────────────────────────────────────────────┘

  CAPACITY ESTIMATES (order of magnitude):
  
  100 orders/sec peak:
  → 100 msg/s to order-events
  → 100 msg/s to payment-events  
  → 100 msg/s to inventory-events
  → 100 msg/s to notification-events
  → Total: ~400 msg/s → 1 Kafka broker handles easily
  → 4 partitions per topic → enough for 4 consumer instances
  
  10,000 orders/sec peak (large e-commerce):
  → ~40,000 msg/s total
  → 3 Kafka brokers, 16+ partitions per topic
  → Connection pooling, batch processing critical
```

---

## 8. Hands-on Lab

> Phạm vi Day 25 trong 2 giờ là **runnable scaffold tối giản + reference implementation snippets**. Thư mục này hiện có scaffold thật: `docker-compose.yml`, `go.mod`, `shared/`, `order-service/`, `payment-service/`, `inventory-service/`, `notification-service/`, `init.sql` và `prometheus.yml`. Scaffold dùng Kafka KRaft single-broker cho lab local, PostgreSQL shared database, inbox/outbox tối thiểu và structured logs để quan sát correlation ID. Nó chưa phải production template đầy đủ; mục tiêu là chạy được flow end-to-end để review trade-off.

### 8.1 Docker Compose — Reference Infrastructure

```yaml
# docker-compose.yml
version: '3.8'

services:
  # === Kafka (KRaft mode) ===
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,EXTERNAL://localhost:9092
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:9093,EXTERNAL://0.0.0.0:9092
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:9093"
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_NUM_PARTITIONS: 4
      KAFKA_LOG_RETENTION_HOURS: 24
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    healthcheck:
      test: kafka-topics --bootstrap-server localhost:9092 --list || exit 1
      interval: 10s
      timeout: 5s
      retries: 5

  # === PostgreSQL (shared for simplicity, separate in production) ===
  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ecommerce
      POSTGRES_PASSWORD: ecommerce
      POSTGRES_DB: ecommerce
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: pg_isready -U ecommerce
      interval: 5s
      timeout: 3s
      retries: 5

  # === kafka-exporter (consumer lag metrics) ===
  kafka-exporter:
    image: danielqsj/kafka-exporter:latest
    depends_on:
      kafka:
        condition: service_healthy
    ports:
      - "9308:9308"
    command:
      - "--kafka.server=kafka:29092"
      - "--topic.filter=.*"
      - "--group.filter=.*"

  # === Prometheus ===
  prometheus:
    image: prom/prometheus:v2.48.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  # === Grafana ===
  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    depends_on:
      - prometheus
```

### 8.2 Database Initialization

```sql
-- init.sql — Database schema for all services

-- === ORDER SERVICE ===
CREATE TABLE orders (
    id            VARCHAR(64) PRIMARY KEY,
    customer_id   VARCHAR(64) NOT NULL,
    items         JSONB NOT NULL,
    total_amount  DECIMAL(12,2) NOT NULL,
    currency      VARCHAR(3) NOT NULL DEFAULT 'USD',
    status        VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    timeout_at    TIMESTAMP NOT NULL
);

-- === PAYMENT SERVICE ===
CREATE TABLE payments (
    id            VARCHAR(64) PRIMARY KEY,
    order_id      VARCHAR(64) NOT NULL,
    amount        DECIMAL(12,2) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    transaction_ref VARCHAR(128),
    error_reason  VARCHAR(256),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- === INVENTORY SERVICE ===
CREATE TABLE inventory (
    product_id    VARCHAR(64) PRIMARY KEY,
    quantity      INTEGER NOT NULL DEFAULT 0,
    reserved      INTEGER NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE inventory_reservations (
    id            VARCHAR(64) PRIMARY KEY,
    order_id      VARCHAR(64) NOT NULL,
    product_id    VARCHAR(64) NOT NULL,
    quantity      INTEGER NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'RESERVED',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- === SHARED: OUTBOX TABLE (each service has one) ===
CREATE TABLE outbox (
    id             BIGSERIAL PRIMARY KEY,
    event_id       VARCHAR(64) NOT NULL UNIQUE,
    event_type     VARCHAR(128) NOT NULL,
    owner_service  VARCHAR(64) NOT NULL,
    aggregate_id   VARCHAR(128) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    topic          VARCHAR(128) NOT NULL,
    payload        JSONB NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    causation_id   VARCHAR(64) NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    locked_at      TIMESTAMP,
    published_at   TIMESTAMP
);
CREATE INDEX idx_outbox_unpublished ON outbox (owner_service, id) WHERE published_at IS NULL;

-- === SHARED: INBOX TABLE (each service has one) ===
CREATE TABLE inbox (
    event_id      VARCHAR(64) PRIMARY KEY,
    event_type    VARCHAR(128) NOT NULL,
    owner_service VARCHAR(64) NOT NULL,
    processed_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_inbox_cleanup ON inbox (owner_service, processed_at);

-- === SEED DATA: Inventory ===
INSERT INTO inventory (product_id, quantity, reserved) VALUES
    ('PROD-001', 100, 0),
    ('PROD-002', 50, 0),
    ('PROD-003', 200, 0),
    ('PROD-004', 10, 0),
    ('PROD-005', 75, 0);
```

### 8.3 Prometheus Config

```yaml
# prometheus.yml
global:
  scrape_interval: 10s

scrape_configs:
  - job_name: "kafka-exporter"
    static_configs:
      - targets: ["kafka-exporter:9308"]
```

### 8.4 Go Implementation — Shared Types & Utilities

```go
// shared/event.go
package shared

import (
	"time"

	"github.com/google/uuid"
)

type Event struct {
	EventID       string      `json:"eventId"`
	EventType     string      `json:"eventType"`
	Timestamp     string      `json:"timestamp"`
	CorrelationID string      `json:"correlationId"`
	CausationID   string      `json:"causationId"`
	Source        string      `json:"source"`
	Version       int         `json:"version"`
	Data          interface{} `json:"data"`
}

func NewEvent(eventType, correlationID, causationID, source string, data interface{}) Event {
	return Event{
		EventID:       "evt_" + uuid.New().String()[:8],
		EventType:     eventType,
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
		CorrelationID: correlationID,
		CausationID:   causationID,
		Source:        source,
		Version:       1,
		Data:          data,
	}
}

// Domain event data types

type OrderCreatedData struct {
	OrderID    string      `json:"orderId"`
	CustomerID string      `json:"customerId"`
	Items      []OrderItem `json:"items"`
	TotalAmount float64    `json:"totalAmount"`
	Currency   string      `json:"currency"`
}

type OrderItem struct {
	ProductID string  `json:"productId"`
	Quantity  int     `json:"quantity"`
	Price     float64 `json:"price"`
}

type PaymentCompletedData struct {
	PaymentID      string  `json:"paymentId"`
	OrderID        string  `json:"orderId"`
	Amount         float64 `json:"amount"`
	TransactionRef string  `json:"transactionRef"`
	Items          []OrderItem `json:"items"`
}

type PaymentFailedData struct {
	PaymentID string `json:"paymentId"`
	OrderID   string `json:"orderId"`
	Reason    string `json:"reason"`
}

type StockReservedData struct {
	ReservationID string      `json:"reservationId"`
	OrderID       string      `json:"orderId"`
	Items         []OrderItem `json:"items"`
}

type StockInsufficientData struct {
	OrderID string              `json:"orderId"`
	Items   []InsufficientItem  `json:"items"`
}

type InsufficientItem struct {
	ProductID string `json:"productId"`
	Requested int    `json:"requested"`
	Available int    `json:"available"`
}
```

```go
// shared/outbox.go
package shared

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"github.com/segmentio/kafka-go"
)

type OutboxEntry struct {
	ID            int64
	EventID       string
	EventType     string
	OwnerService  string
	AggregateID   string
	AggregateType string
	Topic         string
	Payload       json.RawMessage
	CorrelationID string
	CausationID   string
}

// InsertOutbox adds an event to the outbox table within the given transaction
func InsertOutbox(ctx context.Context, tx *sql.Tx, ownerService, topic string, event Event, aggregateID, aggregateType string) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(ctx, `
		INSERT INTO outbox (event_id, event_type, owner_service, aggregate_id, aggregate_type, topic, payload, correlation_id, causation_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
		event.EventID, event.EventType, ownerService, aggregateID, aggregateType, topic, payload, event.CorrelationID, event.CausationID)

	return err
}

// CheckInbox returns true if the event has already been processed
func CheckInbox(ctx context.Context, tx *sql.Tx, eventID string) (bool, error) {
	var exists bool
	err := tx.QueryRowContext(ctx,
		"SELECT EXISTS(SELECT 1 FROM inbox WHERE event_id = $1)", eventID).Scan(&exists)
	return exists, err
}

// MarkInbox records that an event has been processed
func MarkInbox(ctx context.Context, tx *sql.Tx, eventID, eventType, ownerService string) error {
	_, err := tx.ExecContext(ctx,
		"INSERT INTO inbox (event_id, event_type, owner_service) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
		eventID, eventType, ownerService)
	return err
}

// OutboxPoller polls the outbox table and publishes events to Kafka
func OutboxPoller(ctx context.Context, db *sql.DB, writer *kafka.Writer, ownerService string, pollInterval time.Duration) {
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			publishOutbox(ctx, db, writer, ownerService)
		}
	}
}

func publishOutbox(ctx context.Context, db *sql.DB, writer *kafka.Writer, ownerService string) {
	rows, err := db.QueryContext(ctx,
		`SELECT id, event_id, event_type, topic, payload, correlation_id, causation_id
		 FROM outbox
		 WHERE owner_service = $1 AND published_at IS NULL
		 ORDER BY id LIMIT 100
		 FOR UPDATE SKIP LOCKED`, ownerService)
	if err != nil {
		slog.Error("Failed to query outbox", "error", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var entry OutboxEntry
		if err := rows.Scan(&entry.ID, &entry.EventID, &entry.EventType,
			&entry.Topic, &entry.Payload, &entry.CorrelationID, &entry.CausationID); err != nil {
			slog.Error("Failed to scan outbox row", "error", err)
			continue
		}

		msg := kafka.Message{
			Topic: entry.Topic,
			Key:   []byte(entry.EventID),
			Value: entry.Payload,
			Headers: []kafka.Header{
				{Key: "X-Correlation-ID", Value: []byte(entry.CorrelationID)},
				{Key: "X-Causation-ID", Value: []byte(entry.CausationID)},
				{Key: "X-Event-Type", Value: []byte(entry.EventType)},
			},
		}

		if err := writer.WriteMessages(ctx, msg); err != nil {
			slog.Error("Failed to publish outbox event",
				"eventId", entry.EventID,
				"topic", entry.Topic,
				"error", err,
			)
			continue
		}

		_, err := db.ExecContext(ctx,
			"UPDATE outbox SET published_at = NOW() WHERE id = $1", entry.ID)
		if err != nil {
			slog.Error("Failed to mark outbox published",
				"eventId", entry.EventID, "error", err)
		}

		slog.Info("Outbox event published",
			"eventId", entry.EventID,
			"eventType", entry.EventType,
			"topic", entry.Topic,
			"correlationId", entry.CorrelationID,
		)
	}
}
```

### 8.5 Order Service — REST API + Outbox

```go
// order-service/main.go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"

	"capstone/shared"
)

var db *sql.DB

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	var err error
	dsn := getEnv("DATABASE_URL", "postgres://ecommerce:ecommerce@localhost:5432/ecommerce?sslmode=disable")
	db, err = sql.Open("postgres", dsn)
	if err != nil {
		slog.Error("Failed to connect to database", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	// Kafka writer for outbox poller
	writer := &kafka.Writer{
		Addr:         kafka.TCP(getEnv("KAFKA_BROKER", "localhost:9092")),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
	defer writer.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start outbox poller
	go shared.OutboxPoller(ctx, db, writer, "order-service", 200*time.Millisecond)

	// Start saga event consumer (listens for payment/inventory events)
	go consumeSagaEvents(ctx)

	// HTTP API
	mux := http.NewServeMux()
	mux.HandleFunc("POST /orders", createOrderHandler)
	mux.HandleFunc("GET /orders/{id}", getOrderHandler)
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		w.Write([]byte(`{"status":"ok"}`))
	})

	server := &http.Server{Addr: ":8080", Handler: mux}

	go func() {
		slog.Info("Order Service started", "port", 8080)
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			slog.Error("HTTP server error", "error", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	slog.Info("Shutting down Order Service")
	cancel()
	server.Shutdown(context.Background())
}

type CreateOrderRequest struct {
	CustomerID string             `json:"customerId"`
	Items      []shared.OrderItem `json:"items"`
}

func createOrderHandler(w http.ResponseWriter, r *http.Request) {
	var req CreateOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}

	correlationID := r.Header.Get("X-Correlation-ID")
	if correlationID == "" {
		correlationID = "req_" + uuid.New().String()[:8]
	}

	orderID := "ORD-" + uuid.New().String()[:8]
	var totalAmount float64
	for _, item := range req.Items {
		totalAmount += item.Price * float64(item.Quantity)
	}

	itemsJSON, _ := json.Marshal(req.Items)

	// BEGIN TRANSACTION: save order + outbox event atomically
	tx, err := db.BeginTx(r.Context(), nil)
	if err != nil {
		slog.Error("Failed to begin transaction", "error", err, "correlationId", correlationID)
		http.Error(w, `{"error":"internal error"}`, http.StatusInternalServerError)
		return
	}
	defer tx.Rollback()

	timeoutAt := time.Now().Add(15 * time.Minute)

	_, err = tx.ExecContext(r.Context(),
		`INSERT INTO orders (id, customer_id, items, total_amount, currency, status, timeout_at)
		 VALUES ($1, $2, $3, $4, 'USD', 'PENDING', $5)`,
		orderID, req.CustomerID, itemsJSON, totalAmount, timeoutAt)
	if err != nil {
		slog.Error("Failed to insert order", "error", err, "correlationId", correlationID)
		http.Error(w, `{"error":"failed to create order"}`, http.StatusInternalServerError)
		return
	}

	event := shared.NewEvent(
		"order.order.created.v1",
		correlationID,
		correlationID,
		"order-service",
		shared.OrderCreatedData{
			OrderID:     orderID,
			CustomerID:  req.CustomerID,
			Items:       req.Items,
			TotalAmount: totalAmount,
			Currency:    "USD",
		},
	)

	if err := shared.InsertOutbox(r.Context(), tx, "order-service", "order-events", event, orderID, "order"); err != nil {
		slog.Error("Failed to insert outbox", "error", err, "correlationId", correlationID)
		http.Error(w, `{"error":"failed to create order"}`, http.StatusInternalServerError)
		return
	}

	if err := tx.Commit(); err != nil {
		slog.Error("Failed to commit transaction", "error", err, "correlationId", correlationID)
		http.Error(w, `{"error":"failed to create order"}`, http.StatusInternalServerError)
		return
	}

	slog.Info("Order created",
		"orderId", orderID,
		"customerId", req.CustomerID,
		"totalAmount", totalAmount,
		"correlationId", correlationID,
	)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"orderId":       orderID,
		"status":        "PENDING",
		"totalAmount":   totalAmount,
		"correlationId": correlationID,
	})
}

func getOrderHandler(w http.ResponseWriter, r *http.Request) {
	orderID := r.PathValue("id")

	var status, customerID string
	var totalAmount float64
	var createdAt time.Time
	err := db.QueryRowContext(r.Context(),
		"SELECT status, customer_id, total_amount, created_at FROM orders WHERE id = $1",
		orderID).Scan(&status, &customerID, &totalAmount, &createdAt)

	if err == sql.ErrNoRows {
		http.Error(w, `{"error":"order not found"}`, http.StatusNotFound)
		return
	}
	if err != nil {
		http.Error(w, `{"error":"internal error"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"orderId":    orderID,
		"customerId": customerID,
		"totalAmount": totalAmount,
		"status":     status,
		"createdAt":  createdAt,
	})
}

func consumeSagaEvents(ctx context.Context) {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{getEnv("KAFKA_BROKER", "localhost:9092")},
		GroupID: "order-service-saga",
		GroupTopics: []string{"payment-events", "inventory-events"},
		MinBytes: 1e3,
		MaxBytes: 10e6,
	})
	defer reader.Close()

	writer := &kafka.Writer{
		Addr:         kafka.TCP(getEnv("KAFKA_BROKER", "localhost:9092")),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
	}
	defer writer.Close()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			slog.Error("Failed to fetch saga event", "error", err)
			continue
		}

		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			slog.Error("Failed to unmarshal saga event", "error", err)
			reader.CommitMessages(ctx, msg)
			continue
		}

		switch event.EventType {
		case "inventory.stock.reserved.v1":
			handleStockReserved(ctx, event, writer)
		case "payment.payment.failed.v1":
			handlePaymentFailed(ctx, event)
		case "inventory.stock.insufficient.v1":
			handleStockInsufficient(ctx, event)
		}

		reader.CommitMessages(ctx, msg)
	}
}

func handleStockReserved(ctx context.Context, event shared.Event, writer *kafka.Writer) {
	dataBytes, _ := json.Marshal(event.Data)
	var data shared.StockReservedData
	json.Unmarshal(dataBytes, &data)

	tx, _ := db.BeginTx(ctx, nil)
	defer tx.Rollback()

	processed, _ := shared.CheckInbox(ctx, tx, event.EventID)
	if processed {
		return
	}

	tx.ExecContext(ctx,
		"UPDATE orders SET status = 'COMPLETED', updated_at = NOW() WHERE id = $1 AND status = 'PENDING'",
		data.OrderID)

	completedEvent := shared.NewEvent(
		"order.order.completed.v1",
		event.CorrelationID,
		event.EventID,
		"order-service",
		map[string]interface{}{"orderId": data.OrderID, "completedAt": time.Now().UTC()},
	)
	shared.InsertOutbox(ctx, tx, "order-service", "notification-events", completedEvent, data.OrderID, "order")
	shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "order-service")
	tx.Commit()

	slog.Info("Order completed",
		"orderId", data.OrderID,
		"correlationId", event.CorrelationID,
	)
}

func handlePaymentFailed(ctx context.Context, event shared.Event) {
	dataBytes, _ := json.Marshal(event.Data)
	var data shared.PaymentFailedData
	json.Unmarshal(dataBytes, &data)

	tx, _ := db.BeginTx(ctx, nil)
	defer tx.Rollback()

	processed, _ := shared.CheckInbox(ctx, tx, event.EventID)
	if processed {
		return
	}

	tx.ExecContext(ctx,
		"UPDATE orders SET status = 'CANCELLED', updated_at = NOW() WHERE id = $1 AND status = 'PENDING'",
		data.OrderID)

	cancelledEvent := shared.NewEvent(
		"order.order.cancelled.v1",
		event.CorrelationID,
		event.EventID,
		"order-service",
		map[string]interface{}{"orderId": data.OrderID, "reason": "payment_failed: " + data.Reason},
	)
	shared.InsertOutbox(ctx, tx, "order-service", "notification-events", cancelledEvent, data.OrderID, "order")
	shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "order-service")
	tx.Commit()

	slog.Info("Order cancelled due to payment failure",
		"orderId", data.OrderID,
		"reason", data.Reason,
		"correlationId", event.CorrelationID,
	)
}

func handleStockInsufficient(ctx context.Context, event shared.Event) {
	dataBytes, _ := json.Marshal(event.Data)
	var data shared.StockInsufficientData
	json.Unmarshal(dataBytes, &data)

	tx, _ := db.BeginTx(ctx, nil)
	defer tx.Rollback()

	processed, _ := shared.CheckInbox(ctx, tx, event.EventID)
	if processed {
		return
	}

	tx.ExecContext(ctx,
		"UPDATE orders SET status = 'CANCELLED', updated_at = NOW() WHERE id = $1",
		data.OrderID)

	cancelledEvent := shared.NewEvent(
		"order.order.cancelled.v1",
		event.CorrelationID,
		event.EventID,
		"order-service",
		map[string]interface{}{"orderId": data.OrderID, "reason": "insufficient_stock"},
	)
	shared.InsertOutbox(ctx, tx, "order-service", "notification-events", cancelledEvent, data.OrderID, "order")
	shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "order-service")
	tx.Commit()

	slog.Info("Order cancelled due to insufficient stock",
		"orderId", data.OrderID,
		"correlationId", event.CorrelationID,
	)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

### 8.6 Payment Service — Consumer + Producer with Inbox

```go
// payment-service/main.go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"

	"capstone/shared"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	dsn := getEnv("DATABASE_URL", "postgres://ecommerce:ecommerce@localhost:5432/ecommerce?sslmode=disable")
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		slog.Error("DB connection failed", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	broker := getEnv("KAFKA_BROKER", "localhost:9092")

	writer := &kafka.Writer{
		Addr:         kafka.TCP(broker),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
	defer writer.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{broker},
		GroupID:  "payment-service-group",
		Topic:    "order-events",
		MinBytes: 1e3,
		MaxBytes: 10e6,
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start outbox poller
	go shared.OutboxPoller(ctx, db, writer, "payment-service", 200*time.Millisecond)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		slog.Info("Shutting down Payment Service")
		cancel()
	}()

	slog.Info("Payment Service started", "broker", broker)

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			slog.Error("Fetch error", "error", err)
			continue
		}

		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			slog.Error("Unmarshal error", "error", err,
				"topic", msg.Topic, "partition", msg.Partition, "offset", msg.Offset)
			reader.CommitMessages(ctx, msg)
			continue
		}

		if event.EventType != "order.order.created.v1" {
			reader.CommitMessages(ctx, msg)
			continue
		}

		if err := processPayment(ctx, db, event); err != nil {
			slog.Error("Processing failed; offset not committed",
				"eventId", event.EventID,
				"correlationId", event.CorrelationID,
				"error", err,
			)
			continue
		}
		reader.CommitMessages(ctx, msg)
	}
}

func processPayment(ctx context.Context, db *sql.DB, event shared.Event) error {
	start := time.Now()

	dataBytes, _ := json.Marshal(event.Data)
	var orderData shared.OrderCreatedData
	json.Unmarshal(dataBytes, &orderData)

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		slog.Error("Begin TX failed", "error", err, "correlationId", event.CorrelationID)
		return err
	}
	defer tx.Rollback()

	// Idempotency check
	processed, _ := shared.CheckInbox(ctx, tx, event.EventID)
	if processed {
		slog.Info("Event already processed (idempotent skip)",
			"eventId", event.EventID,
			"correlationId", event.CorrelationID,
		)
		tx.Rollback()
		return nil
	}

	paymentID := "PAY-" + uuid.New().String()[:8]

	// Simulate payment processing (10% failure rate for demo)
	time.Sleep(time.Duration(50+rand.Intn(200)) * time.Millisecond)
	paymentSuccess := rand.Float64() > 0.1

	if paymentSuccess {
		txnRef := fmt.Sprintf("TXN-%d", time.Now().UnixNano())

		tx.ExecContext(ctx,
			`INSERT INTO payments (id, order_id, amount, status, transaction_ref)
			 VALUES ($1, $2, $3, 'COMPLETED', $4)`,
			paymentID, orderData.OrderID, orderData.TotalAmount, txnRef)

		completedEvent := shared.NewEvent(
			"payment.payment.completed.v1",
			event.CorrelationID,
			event.EventID,
			"payment-service",
			shared.PaymentCompletedData{
				PaymentID:      paymentID,
				OrderID:        orderData.OrderID,
				Amount:         orderData.TotalAmount,
				TransactionRef: txnRef,
				Items:          orderData.Items,
			},
		)
		shared.InsertOutbox(ctx, tx, "payment-service", "payment-events", completedEvent, paymentID, "payment")

		slog.Info("Payment completed",
			"paymentId", paymentID,
			"orderId", orderData.OrderID,
			"amount", orderData.TotalAmount,
			"correlationId", event.CorrelationID,
			"processingTimeMs", time.Since(start).Milliseconds(),
			"outcome", "success",
		)
	} else {
		reason := "insufficient_funds"

		tx.ExecContext(ctx,
			`INSERT INTO payments (id, order_id, amount, status, error_reason)
			 VALUES ($1, $2, $3, 'FAILED', $4)`,
			paymentID, orderData.OrderID, orderData.TotalAmount, reason)

		failedEvent := shared.NewEvent(
			"payment.payment.failed.v1",
			event.CorrelationID,
			event.EventID,
			"payment-service",
			shared.PaymentFailedData{
				PaymentID: paymentID,
				OrderID:   orderData.OrderID,
				Reason:    reason,
			},
		)
		shared.InsertOutbox(ctx, tx, "payment-service", "payment-events", failedEvent, paymentID, "payment")

		slog.Warn("Payment failed",
			"paymentId", paymentID,
			"orderId", orderData.OrderID,
			"reason", reason,
			"correlationId", event.CorrelationID,
			"processingTimeMs", time.Since(start).Milliseconds(),
			"outcome", "failure",
		)
	}

	shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "payment-service")
	if err := tx.Commit(); err != nil {
		return err
	}
	return nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

### 8.7 Inventory Service — Reserve/Release Stock

```go
// inventory-service/main.go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"

	"capstone/shared"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	dsn := getEnv("DATABASE_URL", "postgres://ecommerce:ecommerce@localhost:5432/ecommerce?sslmode=disable")
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		slog.Error("DB connection failed", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	broker := getEnv("KAFKA_BROKER", "localhost:9092")

	writer := &kafka.Writer{
		Addr:         kafka.TCP(broker),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
	defer writer.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     []string{broker},
		GroupID:     "inventory-service-group",
		Topic:       "payment-events",
		MinBytes:    1e3,
		MaxBytes:    10e6,
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go shared.OutboxPoller(ctx, db, writer, "inventory-service", 200*time.Millisecond)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigCh; cancel() }()

	slog.Info("Inventory Service started")

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			continue
		}

		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			reader.CommitMessages(ctx, msg)
			continue
		}

		if event.EventType == "payment.payment.completed.v1" {
			if err := reserveStock(ctx, db, event); err != nil {
				slog.Error("Reserve stock failed; offset not committed",
					"eventId", event.EventID,
					"correlationId", event.CorrelationID,
					"error", err,
				)
				continue
			}
		}

		reader.CommitMessages(ctx, msg)
	}
}

func reserveStock(ctx context.Context, db *sql.DB, event shared.Event) error {
	dataBytes, _ := json.Marshal(event.Data)
	var paymentData shared.PaymentCompletedData
	json.Unmarshal(dataBytes, &paymentData)

	tx, _ := db.BeginTx(ctx, nil)
	defer tx.Rollback()

	processed, _ := shared.CheckInbox(ctx, tx, event.EventID)
	if processed {
		return nil
	}

	// PaymentCompletedData carries order items so inventory does not hardcode a SKU.
	reservationID := "RES-" + uuid.New().String()[:8]
	if len(paymentData.Items) == 0 {
		return fmt.Errorf("payment completed event missing items")
	}
	item := paymentData.Items[0]
	productID := item.ProductID
	quantity := item.Quantity

	var available int
	err := tx.QueryRowContext(ctx,
		"SELECT quantity - reserved FROM inventory WHERE product_id = $1 FOR UPDATE",
		productID).Scan(&available)

	if err != nil || available < quantity {
		insufficientEvent := shared.NewEvent(
			"inventory.stock.insufficient.v1",
			event.CorrelationID,
			event.EventID,
			"inventory-service",
			shared.StockInsufficientData{
				OrderID: paymentData.OrderID,
				Items: []shared.InsufficientItem{
					{ProductID: productID, Requested: quantity, Available: available},
				},
			},
		)
		shared.InsertOutbox(ctx, tx, "inventory-service", "inventory-events", insufficientEvent, paymentData.OrderID, "inventory")
		shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "inventory-service")
		tx.Commit()

		slog.Warn("Insufficient stock",
			"orderId", paymentData.OrderID,
			"productId", productID,
			"requested", quantity,
			"available", available,
			"correlationId", event.CorrelationID,
		)
		return nil
	}

	tx.ExecContext(ctx,
		"UPDATE inventory SET reserved = reserved + $1, updated_at = NOW() WHERE product_id = $2",
		quantity, productID)

	tx.ExecContext(ctx,
		`INSERT INTO inventory_reservations (id, order_id, product_id, quantity, status)
		 VALUES ($1, $2, $3, $4, 'RESERVED')`,
		reservationID, paymentData.OrderID, productID, quantity)

	reservedEvent := shared.NewEvent(
		"inventory.stock.reserved.v1",
		event.CorrelationID,
		event.EventID,
		"inventory-service",
		shared.StockReservedData{
			ReservationID: reservationID,
			OrderID:       paymentData.OrderID,
			Items:         []shared.OrderItem{{ProductID: productID, Quantity: quantity}},
		},
	)
	shared.InsertOutbox(ctx, tx, "inventory-service", "inventory-events", reservedEvent, paymentData.OrderID, "inventory")
	shared.MarkInbox(ctx, tx, event.EventID, event.EventType, "inventory-service")
	if err := tx.Commit(); err != nil {
		return err
	}

	slog.Info("Stock reserved",
		"reservationId", reservationID,
		"orderId", paymentData.OrderID,
		"productId", productID,
		"quantity", quantity,
		"correlationId", event.CorrelationID,
	)
	return nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

### 8.8 Notification Service — Sink Consumer

```go
// notification-service/main.go
package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/segmentio/kafka-go"

	"capstone/shared"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	broker := getEnv("KAFKA_BROKER", "localhost:9092")

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{broker},
		GroupID:  "notification-service-group",
		Topic:    "notification-events",
		MinBytes: 1e3,
		MaxBytes: 10e6,
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigCh; cancel() }()

	slog.Info("Notification Service started")

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			continue
		}

		var event shared.Event
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			slog.Error("Failed to unmarshal", "error", err)
			reader.CommitMessages(ctx, msg)
			continue
		}

		correlationID := event.CorrelationID

		switch event.EventType {
		case "order.order.completed.v1":
			slog.Info("[EMAIL] Order completed notification sent",
				"eventType", event.EventType,
				"correlationId", correlationID,
				"template", "order_completed",
				"channel", "email",
			)
		case "order.order.cancelled.v1":
			slog.Info("[EMAIL] Order cancelled notification sent",
				"eventType", event.EventType,
				"correlationId", correlationID,
				"template", "order_cancelled",
				"channel", "email",
			)
		default:
			slog.Info("Unhandled notification event",
				"eventType", event.EventType,
				"correlationId", correlationID,
			)
		}

		reader.CommitMessages(ctx, msg)
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

### 8.9 Create Topics & Run

```bash
# Build và start infrastructure + 4 services
docker compose up -d

# Wait for Kafka, Postgres và service startup
sleep 15

# Topics được tạo bởi service kafka-init trong docker-compose.yml
docker compose ps
```

```bash
# === TEST: Happy Path ===
echo "--- Creating order (happy path) ---"
curl -s -X POST http://localhost:18080/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-happy-001" \
  -d '{
    "customerId": "CUST-789",
    "items": [
      {"productId": "PROD-001", "quantity": 1, "price": 29.99}
    ]
  }' | jq .

# Wait for saga to complete
sleep 3

# Check order status. Expected: CONFIRMED hoặc CANCELLED tùy payment/stock simulation.
ORDER_ID=$(curl -s -X POST http://localhost:18080/orders \
  -H "Content-Type: application/json" \
  -d '{"customerId":"CUST-789","items":[{"productId":"PROD-001","quantity":1,"price":9.99}]}' | jq -r '.orderId')
sleep 3
curl -s "http://localhost:18080/orders/${ORDER_ID}" | jq .

# Observe structured logs with eventType/correlationId.
docker compose logs -f order-service payment-service inventory-service notification-service
```

```bash
# === TEST: Duplicate Handling (Idempotency) ===
echo "--- Testing idempotency: produce same event twice ---"
# The inbox table prevents double processing
# Check payment-service logs for "Event already processed (idempotent skip)"
```

```bash
# === MONITORING ===
echo "Prometheus: http://localhost:9090"
echo "Grafana:    http://localhost:3000 (admin/admin)"
echo ""
echo "PromQL queries:"
echo "  Consumer lag: kafka_consumergroup_lag_sum"
echo "  By group:     kafka_consumergroup_lag_sum{consumergroup=~'.*service.*'}"
```

### 8.10 Mode B Overview — Polyglot Messaging (Reference Only)

```
MODE B — For reference, NOT implement in 2 hours:

  In Mode B, bạn sẽ thêm:

  ❶ RabbitMQ cho Notification Service:
     → Kafka consumer reads notification-events
     → Bridge: publishes to RabbitMQ queue "email-tasks"
     → RabbitMQ benefits: retry 3x, DLX, priority (high priority = password reset)
     → Notification worker consumes from RabbitMQ
  
  ❷ NATS cho Real-time Frontend Updates:
     → After order status changes
     → Publish to NATS subject "orders.{orderId}.status"
     → WebSocket gateway subscribes to orders.{orderId}.>
     → Browser receives real-time status updates

  ❸ Bridge Pattern:
     → Dedicated "bridge" service
     → Consumes from Kafka
     → Publishes to RabbitMQ / NATS
     → Single responsibility, easy to monitor

  Trade-off:
  → Better fit per use case
  → 3x operational burden
  → ONLY justified when: email retry with RabbitMQ DLX is critical
     AND real-time push with NATS latency is critical
  → Most teams: Mode A is sufficient
```

### 8.11 Acceptance Checklist

Day 25 hiện có **runnable scaffold tối giản + reference snippets**. Checklist dưới đây tách rõ phần đã có trong scaffold local và phần còn là production extension:

- [x] `docker compose up` dựng Kafka, PostgreSQL và đủ 4 services: `order-service`, `payment-service`, `inventory-service`, `notification-service`.
- [x] Topics đúng domain model: `order-events`, `payment-events`, `inventory-events`, `notification-events`; không publish event của domain này vào topic domain khác.
- [x] Happy path: create order → payment completed → inventory reserved → order confirmed → notification logged.
- [x] Duplicate event: cùng `event_id` được redeliver nhưng inbox unique constraint làm side effect chạy đúng một lần.
- [x] Inventory dùng `items[]` từ order/payment event, không hardcode SKU.
- [ ] Production extension: thêm các `*.dlq` topics và poison payload handling đầy đủ.
- [x] Payment failure: payment failed event → order cancelled → notification logged; inventory không reserve stock.
- [ ] Production extension: inventory failure → refund requested/completed → order cancelled.
- [ ] Production extension: order `PENDING` quá SLA được cancel bởi timeout job; late payment event trigger refund/ignore idempotently.
- [ ] Production extension: consumer error không commit offset; bad payload được ghi DLQ trước khi commit original offset.
- [ ] SQL hợp lệ PostgreSQL: index tạo bằng `CREATE INDEX`, không đặt `INDEX` inline trong `CREATE TABLE`.
- [ ] Observability: mọi log có `correlationId`, consumer lag query chạy được, DLQ count có alert threshold.

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Tại sao outbox pattern cần INSERT order và INSERT outbox trong CÙNG database transaction? Nếu tách thành 2 operations riêng biệt, failure scenario nào xảy ra?**
   - Hint: If order saved but outbox not → order created but event never published → downstream services never know. If outbox saved but order not → event published for non-existent order. BOTH are dangerous data inconsistencies.

2. **Consumer restart sau crash. Kafka redelivers message. Nếu KHÔNG có inbox table, hậu quả cụ thể trong hệ thống này?**
   - Hint: Payment charged TWICE for same order. Inventory reserved TWICE. Customer notified TWICE. Double-charge = customer complaint + refund process. Inbox table prevents ALL of these.

3. **Saga choreography (events) vs saga orchestration (central coordinator). Trade-off? Khi nào dùng orchestration thay vì choreography?**
   - Hint: Choreography: loosely coupled, no single point of failure, BUT hard to visualize full flow, hard to add new steps. Orchestration: centralized logic, easy to understand flow, BUT central coordinator = bottleneck + SPOF. Use orchestration when: many steps (>5), complex compensation, need visibility.

4. **Order timeout 15 phút. Payment service processes payment ở phút 16 (sau khi order đã cancelled). Hệ thống xử lý thế nào? Có data inconsistency không?**
   - Hint: Payment completed → publishes payment.completed → Inventory Service receives → tries to reserve stock → BUT Order Service already received timeout → order is CANCELLED. Inbox table: order-service might already have processed a "cancel" event. Need compensation: refund payment since order was cancelled.

5. **Correlation ID và causation ID khác nhau thế nào? Trong chain Order→Payment→Inventory→Notification, liệt kê correlationId và causationId cho mỗi event.**
   - Hint: correlationId = same for ALL events in chain (original request ID). causationId = eventId of the DIRECT parent. OrderCreated.causationId = requestId, PaymentCompleted.causationId = OrderCreated.eventId, StockReserved.causationId = PaymentCompleted.eventId.

6. **System đã chạy 6 tháng. Event schema cần thay đổi: thêm field "shippingAddress" vào OrderCreated. Cách nào để evolve schema mà không break existing consumers?**
   - Hint: Backward compatible change: new field as OPTIONAL. Existing consumers ignore unknown fields. New consumers use the field if present. Avro/Protobuf: schema registry enforces compatibility. JSON: consumers must handle missing fields gracefully. Version: order.order.created.v2.

7. **Consumer lag cho payment-service-group tăng đều 100 messages/minute. Producer rate stable. Kafka broker healthy. Nguyên nhân có thể và cách investigate?**
   - Hint: Consumer processing slower than produce rate. Check: Is payment gateway slow? DB connection pool exhausted? GC pauses? max.poll.records too high → processing timeout → rebalance? Check structured logs for processingTimeMs trend.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Transactional Outbox Pattern — Microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)
- [Saga Pattern — Microservices.io](https://microservices.io/patterns/data/saga.html)

### Blog Posts & Articles
- [Confluent — Event-Driven Microservices](https://www.confluent.io/blog/event-driven-microservices-with-kafka/)
- [Uber Engineering — Reliable Processing in a Streaming World](https://www.uber.com/blog/reliable-reprocessing/)
- [CloudEvents Specification](https://cloudevents.io/) — standard event envelope format
- [Chris Richardson — Saga Pattern](https://chrisrichardson.net/post/microservices/2019/07/09/developing-sagas-part-1.html)
- [Gunnar Morling — Outbox Pattern with Debezium](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/)

### Videos & Talks
- [Martin Kleppmann — Turning the Database Inside Out](https://www.youtube.com/watch?v=fU9hR3kiOK0)
- [Kafka Summit — Building Event-Driven Microservices](https://www.confluent.io/events/kafka-summit/)
- [GOTO Conference — Practical Event-Driven Microservices](https://www.youtube.com/results?search_query=event+driven+microservices+saga)

### Code References
- [segmentio/kafka-go](https://github.com/segmentio/kafka-go) — Go Kafka client
- [Debezium Outbox Event Router](https://debezium.io/documentation/reference/transformations/outbox-event-router.html)
- [eventuate-tram](https://github.com/eventuate-tram/eventuate-tram-core) — Saga orchestration framework (Java)
