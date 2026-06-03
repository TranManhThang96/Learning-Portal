# Day 15: Delivery Semantics + Idempotency Patterns — Exactly-Once, Transactions, Idempotent Consumer

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** 3 delivery semantics (at-most-once, at-least-once, exactly-once) — tại sao exactly-once là end-to-end design chứ không chỉ là config
2. **Nắm vững phạm vi** Kafka Transactions — transactional producer, read-process-write pattern, `read_committed`, và giới hạn Kafka-to-Kafka
3. **Phân tích được** idempotent consumer patterns — inbox table, deduplication key, idempotency at application level
4. **Hiểu rõ** Transactional Outbox Pattern — đảm bảo database write và event publish không lệch nhau
5. **Thực hành** xây dựng idempotent consumer với inbox pattern và outbox pattern; Kafka transaction lab được scope là theory/optional vì Go client trong lab không expose API transaction đầy đủ

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 11 (idempotent producer — `enable.idempotence`, PID, sequence number)
- Đã hoàn thành Day 12 (consumer offset management — auto commit vs manual commit, at-least-once)
- Đã hoàn thành Day 13 (replication, ISR, `acks=all`, `min.insync.replicas`)
- Hiểu database transactions (ACID) từ backend development background
- Docker Compose Kafka cluster đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Delivery semantics tổng quan — tại sao exactly-once KHÔNG phải chỉ config một chỗ
- Exactly-once illusion: producer idempotence (Day 11 review) + consumer idempotence
- Idempotent consumer patterns: deduplication key, inbox table
- Kafka Transactions: transactional producer, `isolation.level`, read-process-write, transaction timeout/LSO
- Hands-on chính: inbox pattern với database và outbox pattern

### 🟡 Should Learn (nếu còn thời gian)
- Transactional Outbox Pattern — database + event publish consistency
- Exactly-once trong Kafka Streams (automatic với `processing.guarantee=exactly_once_v2`)
- Transaction coordinator internals
- Consumer `isolation.level=read_committed` vs `read_uncommitted`
- Optional transaction lab bằng Java client hoặc librdkafka nếu muốn chứng minh `read_committed`

### 🟢 Optional Deep Dive
- Two-phase commit trong Kafka transactions
- Transaction log (`__transaction_state` topic)
- Zombie fencing (epoch-based)
- Saga patterns với Kafka (choreography vs orchestration)

---

## 4. Lý thuyết (Theory)

### 4.1 Delivery Semantics — Bức tranh toàn cảnh

#### WHY — Tại sao delivery guarantee phức tạp?

Trong distributed systems, có 3 thứ có thể fail: **producer**, **broker**, **consumer**. Mỗi failure point tạo ra khả năng **mất** hoặc **duplicate** message.

```
End-to-end message flow:

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ Producer │───►│  Kafka   │───►│ Consumer │───►│ Database │
  │          │    │  Broker  │    │          │    │ / Service│
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       ↑               ↑               ↑               ↑
   Failure 1       Failure 2       Failure 3       Failure 4
   (send fail,     (broker crash,  (crash after    (DB fail
    retry →         replication    process but     after write)
    duplicate?)     fail)          before commit?)

  End-to-end "exactly-once effect" = failure không gây duplicate business effect
  hoặc data loss quan sát được ở business boundary.
  → Phải handle TẤT CẢ failure points, không chỉ bật 1 Kafka config.
```

#### 3 Delivery Semantics

```
AT-MOST-ONCE (≤ 1 lần):
  ┌──────────┐    ┌──────┐    ┌──────────┐
  │ Producer │──►│Broker │──►│ Consumer │
  │ send()   │    │      │    │ commit() │ ← commit TRƯỚC process
  │ no retry │    │      │    │ process()│ ← crash ở đây → message MẤT
  └──────────┘    └──────┘    └──────────┘

  Producer: acks=0 hoặc retries=0
  Consumer: commit offset TRƯỚC khi xử lý
  
  Kết quả: message có thể mất, nhưng KHÔNG BAO GIỜ duplicate
  Use case: Metrics, logs không critical
  

AT-LEAST-ONCE (≥ 1 lần):
  ┌──────────┐    ┌──────┐    ┌──────────┐
  │ Producer │──►│Broker │──►│ Consumer │
  │ send()   │    │      │    │ process()│ ← xử lý TRƯỚC
  │ retry ✓  │    │      │    │ commit() │ ← commit SAU → crash = re-process
  └──────────┘    └──────┘    └──────────┘

  Producer: acks=all, retries=MAX, enable.idempotence=true
  Consumer: process TRƯỚC, commit offset SAU
  
  Kết quả: message KHÔNG BAO GIỜ mất, nhưng có thể DUPLICATE
  Use case: Hầu hết production systems (kết hợp idempotent consumer)


EXACTLY-ONCE (= 1 lần):
  ┌──────────┐    ┌──────┐    ┌──────────┐    ┌──────────┐
  │ Producer │──►│Broker │──►│ Consumer │──►│ Database │
  │ idempotent│   │      │    │ dedup    │    │ idempotent│
  │ + txn     │   │      │    │ + inbox  │    │ writes   │
  └──────────┘    └──────┘    └──────────┘    └──────────┘

  = at-least-once + idempotent processing at EVERY stage
  
  Kết quả: business effect chỉ xảy ra 1 lần end-to-end dù message có thể được retry/re-read
  Use case: Financial transactions, payments, inventory updates
```

#### "Exactly-Once is a LIE" — Hay không?

```
Common misconception:
  "Tôi set exactly-once config, xong!"
  → SAI! Kafka exactly-once chỉ cover Kafka ↔ Kafka

Kafka covers:
  ┌──────────┐    ┌──────┐    ┌──────────┐
  │ Producer │──►│Kafka  │──►│ Consumer │
  │ (idempot)│    │(txn)  │    │ (txn)    │
  └──────────┘    └──────┘    └──────────┘
  └──────── Kafka "exactly-once" ─────────┘
  
Kafka DOES NOT cover:
  Source ──► Producer ──► Kafka ──► Consumer ──► Sink (DB, API)
  ↑                                               ↑
  External source                          External sink
  (HTTP, file, etc.)                      (DB, service, etc.)
  
  → Source retry → duplicate input
  → Sink idempotency? → consumer xử lý 2 lần, DB ghi 2 lần?

End-to-end effectively-once = end-to-end design:
  1. Idempotent producer (Kafka provides)
  2. Kafka transactions (Kafka provides)
  3. Idempotent consumer (YOU must implement)
  4. Idempotent sink (YOU must implement)
```

### 4.2 Kafka Idempotent Producer — Review từ Day 11

```
Idempotent producer (đã học Day 11):

  enable.idempotence=true
  
  Producer gán: PID (Producer ID) + Sequence Number per <topic, partition>
  
  Send attempt 1: [PID=5, Seq=10, data] → Broker ghi ✓
  ACK lost! Producer retry:
  Send attempt 2: [PID=5, Seq=10, data] → Broker: "Seq=10 đã có" → skip ✓
  
  → Duplicate ELIMINATED tại broker level
  → Chỉ protect SINGLE partition
  → PID reset khi producer restart → không protect cross-session

Giới hạn:
  ✅ Dedup retries trong cùng producer session
  ❌ KHÔNG dedup cross-partition (gửi cùng data đến 2 partitions)
  ❌ KHÔNG dedup cross-session (producer restart = PID mới)
  ❌ KHÔNG dedup application-level retries (app gọi send() 2 lần)
```

### 4.3 Kafka Transactions — Cross-Partition Exactly-Once

#### WHY — Khi nào cần Transactions?

```
Scenario: Read-Process-Write pattern

  Input Topic ──► Consumer ──► Process ──► Producer ──► Output Topic
                                                  ↓
                                           Commit offset

  Cần ATOMIC: {ghi output + commit input offset} phải xảy ra CÙNG LÚC
  Nếu crash GIỮA 2 bước → duplicate hoặc data loss

  KHÔNG có transaction:
    1. Consumer đọc message M từ input
    2. Process M → tạo output O
    3. Producer ghi O đến output topic → SUCCESS
    4. Consumer commit offset → CRASH! 💥
    
    Restart: offset chưa commit → đọc lại M → process lại → ghi O LẦN 2
    → DUPLICATE output!

  CÓ transaction:
    1. Begin transaction
    2. Consumer đọc message M
    3. Process M → tạo output O
    4. Producer ghi O đến output topic (TRONG transaction)
    5. Producer commit offset (TRONG transaction)
    6. Commit transaction → TẤT CẢ hoặc KHÔNG GÌ
    
    Crash trước commit → transaction ABORT → consumer đọc lại M
    → Process lại nhưng output O chưa "visible" → ĐÚNG 1 LẦN ✓
```

#### HOW — Transactional Producer hoạt động

```
Transactional Producer setup:

  transactional.id = "order-processor-1"   ← BẮT BUỘC, unique per instance
  enable.idempotence = true                ← tự động bật khi có transactional.id

Transaction flow:

  Producer                    Transaction Coordinator           Broker
     │                              │                              │
     │ InitTransactions()           │                              │
     │─────────────────────────────►│                              │
     │                              │ Assign PID, bump epoch       │
     │◄─────────────────────────────│ (zombie fencing!)            │
     │                              │                              │
     │ BeginTransaction()           │                              │
     │─────────────────────────────►│ Record: TXN_STARTED          │
     │                              │                              │
     │ Send(output-topic, data)     │                              │
     │──────────────────────────────┼─────────────────────────────►│
     │                              │ AddPartitions(output-topic)  │
     │                              │                              │
     │ SendOffsetsToTransaction()   │                              │
     │─────────────────────────────►│ Record offsets in txn        │
     │                              │                              │
     │ CommitTransaction()          │                              │
     │─────────────────────────────►│                              │
     │                              │ Write COMMIT marker          │
     │                              │──────────────────────────────►│
     │                              │ Commit offsets               │
     │◄─────────────────────────────│ Done!                        │
     │                              │                              │

  Nếu crash trước CommitTransaction():
    → Transaction Coordinator: ABORT transaction
    → Output records có ABORT marker → consumers (read_committed) SKIP chúng
    → Offsets KHÔNG commit → consumer đọc lại input
    → Exactly-once trong phạm vi Kafka read-process-write ✓
```

#### Consumer `isolation.level`

```properties
# Consumer đọc committed transactions only
isolation.level=read_committed    # CHỈ đọc messages đã committed

# Consumer đọc tất cả (kể cả uncommitted)
isolation.level=read_uncommitted  # Mặc định — đọc thấy transactional records trước khi commit
```

```
Producer transaction:
  [msg1(txn)] [msg2(txn)] [msg3(non-txn)] [COMMIT] [msg4(txn2)] [msg5(txn2)] [ABORT]

Consumer read_uncommitted:
  Đọc: msg1, msg2, msg3, msg4, msg5  ← TẤT CẢ (kể cả aborted txn2!)

Consumer read_committed:
  Đọc: msg1, msg2, msg3              ← CHỈ committed data
  msg4, msg5 bị SKIP (txn2 aborted)
```

Nuance về LSO và transaction timeout:
- `read_committed` không chỉ "ẩn aborted records"; nó chỉ đọc tới **Last Stable Offset (LSO)** của partition. Nếu có transaction đang pending, consumer `read_committed` có thể bị giữ lại ở trước transaction đó, kể cả khi phía sau đã có records non-transactional.
- Nếu producer crash trước `CommitTransaction()`, transaction coordinator sẽ abort khi producer bị fenced hoặc khi `transaction.timeout.ms` hết hạn. Trong khoảng chờ này, `read_committed` consumer có thể thấy lag tăng vì LSO chưa tiến.
- Chọn `transaction.timeout.ms` quá lớn làm crash recovery chậm; quá nhỏ làm transaction dài bị abort nhầm. Với stream processing, batch transaction vừa phải thay vì giữ transaction mở lâu.

#### Zombie Fencing — Tránh "zombie producer"

```
Vấn đề zombie:
  Producer-1 (transactional.id = "processor-1")
  → Network partition → Producer-1 bị coi là dead
  → Producer-2 start với CÙNG transactional.id = "processor-1"
  → Producer-1 reconnect → 2 producers cùng ID → CONFLICT!

Giải pháp: Epoch-based fencing

  Producer-1: transactional.id="proc-1", epoch=5
    → Bị isolate

  Producer-2: InitTransactions(transactional.id="proc-1")
    → Coordinator: bump epoch → epoch=6
    → Coordinator: abort any pending txn from epoch 5
    → Producer-2 active với epoch=6

  Producer-1 reconnect, send với epoch=5:
    → Broker: "epoch 5 < current epoch 6" → REJECT (ProducerFencedException)
    → Producer-1 = zombie, bị fence out ✓
```

### 4.4 Idempotent Consumer — Application-Level Deduplication

#### WHY — Kafka transactions chỉ cover Kafka-to-Kafka

```
Kafka transaction scope:
  Input Topic ──► Process ──► Output Topic    ← Kafka guarantees atomic output + offset commit
                                    │
                                    ▼
                              External DB      ← Kafka CANNOT guarantee!
                              API call         ← Kafka CANNOT guarantee!
                              Send email       ← Kafka CANNOT guarantee!

Khi consumer ghi vào DATABASE:
  1. Consumer đọc message (order.created, orderId=123)
  2. Consumer ghi vào DB: INSERT INTO orders (id, ...) VALUES (123, ...)
  3. Consumer commit offset
  4. CRASH! 💥 (offset chưa commit)
  5. Restart → đọc lại message → INSERT lại → DUPLICATE!

→ Consumer PHẢI tự handle deduplication khi ghi ra external system
```

#### Pattern 1: Natural Idempotency

```
Một số operations TỰ NHIÊN idempotent:

  UPSERT (INSERT ON CONFLICT UPDATE):
    INSERT INTO products (id, name, price) VALUES (123, 'Laptop', 999)
    ON CONFLICT (id) DO UPDATE SET name='Laptop', price=999;
    
    → Gọi 1 lần hay 10 lần kết quả GIỐNG NHAU ✓
    → Use case: state sync, CDC, configuration

  SET (overwrite):
    UPDATE users SET last_login = '2024-01-01' WHERE id = 456;
    
    → Idempotent vì SET same value ✓

  DELETE:
    DELETE FROM notifications WHERE id = 789;
    
    → Lần 2 delete → no rows affected → vẫn OK ✓

KHÔNG idempotent tự nhiên:
  INSERT INTO orders (...) VALUES (...);       ← duplicate insert!
  UPDATE accounts SET balance = balance + 100; ← multiple adds!
  counter++;                                   ← multiple increments!
```

#### Pattern 2: Deduplication Key

```
Mỗi message mang theo 1 unique ID (deduplication key):

  Message: {
    "id": "evt-abc-123",          ← deduplication key
    "type": "payment.processed",
    "orderId": "order-456",
    "amount": 100.00
  }

Consumer logic:
  function processMessage(msg):
    if (hasProcessed(msg.id)):     ← check processed?
      return SKIP                  ← đã xử lý rồi, bỏ qua
    
    executeBusinessLogic(msg)      ← xử lý
    markAsProcessed(msg.id)        ← đánh dấu đã xử lý
    commitOffset(msg)

Lưu trữ processed IDs:
  Option 1: In-memory Set (HashSet)
    Pro: Nhanh nhất
    Con: Mất khi restart → window of duplicates
    Con: Memory-bound nếu nhiều messages
    
  Option 2: Database table
    Pro: Persist qua restart
    Con: Thêm 1 DB query per message
    
  Option 3: Redis/Cache với TTL
    Pro: Nhanh, auto-cleanup
    Con: Thêm dependency
```

#### Pattern 3: Inbox Table (Recommended for Production)

```
Inbox Pattern — Dedup + Business Logic trong cùng 1 DB transaction:

  ┌──────────────────────────────────────────────────┐
  │ PostgreSQL Database                               │
  │                                                    │
  │ CREATE TABLE inbox (                               │
  │   message_id  VARCHAR(255) PRIMARY KEY,            │
  │   topic       VARCHAR(255) NOT NULL,               │
  │   payload     JSONB NOT NULL,                      │
  │   processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP │
  │ );                                                 │
  │                                                    │
  │ CREATE TABLE orders (                              │
  │   id          VARCHAR(255) PRIMARY KEY,            │
  │   status      VARCHAR(50),                         │
  │   amount      DECIMAL(10,2),                       │
  │   updated_at  TIMESTAMP                            │
  │ );                                                 │
  └──────────────────────────────────────────────────┘

  Consumer processing:
    BEGIN TRANSACTION;
    
    -- Step 1: Check inbox (idempotency check)
    INSERT INTO inbox (message_id, topic, payload)
    VALUES ('evt-abc-123', 'payments', '{"..."}')
    ON CONFLICT (message_id) DO NOTHING;
    
    -- Nếu insert thành công (message chưa xử lý):
    IF row_count > 0 THEN
      -- Step 2: Business logic
      UPDATE orders SET status = 'paid' WHERE id = 'order-456';
      UPDATE accounts SET balance = balance - 100 WHERE user_id = 'user-789';
    END IF;
    
    COMMIT;  -- Atomic: inbox insert + business logic

  → Message xử lý LẦN 1: inbox insert ✓ + business logic ✓
  → Message xử lý LẦN 2: inbox insert CONFLICT → SKIP business logic ✓
  → Effectively-once business effect! ✓
```

**Tại sao inbox table tốt hơn in-memory dedup?**

```
In-memory Set:
  Consumer crash → restart → Set rỗng
  → Window: messages processed trước crash nhưng offset chưa commit
  → Duplicate window = offset commit interval

Inbox table (DB):
  Consumer crash → restart → offset chưa commit → re-read message
  → Check inbox table: "message-123 đã có!" → SKIP
  → Không lặp business effect (giả sử DB transaction đã commit bền vững)

Trade-off:
  In-memory:   +++ Performance    --- Durability
  Inbox (DB):  --- 1 extra DB query +++ effectively-once business effect
  Redis:       ++ Performance      ++ Durability (depends on config)
```

### 4.5 Transactional Outbox Pattern — Database + Event Consistency

#### WHY — Dual Write Problem

```
Vấn đề: service cần CẢ ghi DB VÀ publish event

  function createOrder(order):
    db.insert(order)                    // Step 1: DB write
    kafka.send("order.created", order)  // Step 2: Event publish

  Failure scenarios:
    1. DB write ✓ → Kafka send ✗ → DB có data, event MẤT!
    2. DB write ✗ → Kafka send ✓ → Event published mà DB không có!
    3. DB write ✓ → service crash → Kafka send chưa thực hiện

  → KHÔNG THỂ atomic 2 hệ thống khác nhau (DB + Kafka) 
    mà không có distributed transaction!
```

#### HOW — Outbox Pattern

```
Thay vì ghi 2 hệ thống song song, ghi CHỈ vào DB:

  ┌─────────────────────────────────────────────┐
  │ PostgreSQL                                   │
  │                                               │
  │ CREATE TABLE outbox (                         │
  │   id            BIGSERIAL PRIMARY KEY,        │
  │   aggregate_type VARCHAR(255),                │
  │   aggregate_id   VARCHAR(255),                │
  │   event_type     VARCHAR(255),                │
  │   payload        JSONB,                       │
  │   created_at     TIMESTAMP DEFAULT NOW(),     │
  │   published      BOOLEAN DEFAULT FALSE        │
  │ );                                            │
  └───────────────┬─────────────────────────────┘
                  │
                  │ Polling hoặc CDC (Debezium)
                  ▼
  ┌─────────────────────────────────────────────┐
  │ Outbox Publisher                              │
  │ (separate process hoặc CDC connector)         │
  │                                               │
  │ SELECT * FROM outbox WHERE published = FALSE; │
  │ → Kafka.send(event)                           │
  │ → UPDATE outbox SET published = TRUE          │
  │                                               │
  │ Hoặc: Debezium CDC → tự động capture inserts  │
  │ → Route đến Kafka topic                       │
  └─────────────────────────────────────────────┘

Service code (simplified):
  function createOrder(order):
    BEGIN TRANSACTION;
      INSERT INTO orders (...) VALUES (...);
      INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
        VALUES ('order', order.id, 'order.created', to_json(order));
    COMMIT;
    // → ATOMIC! Cả order VÀ outbox event trong cùng 1 DB transaction
    // → Outbox publisher sẽ đọc và publish event đến Kafka
```

```
Outbox Pattern Flow:

  ┌──────────┐   ┌─────────────────┐   ┌──────────────┐   ┌──────────┐
  │ Service  │──►│   Database      │──►│ Outbox       │──►│  Kafka   │
  │          │   │ ┌────────────┐  │   │ Publisher    │   │          │
  │ create   │   │ │orders table│  │   │ (Debezium   │   │ topic:   │
  │ Order()  │   │ └────────────┘  │   │  or polling)│   │ orders   │
  │          │   │ ┌────────────┐  │   │             │   │          │
  │          │   │ │outbox table│  │   │             │   │          │
  │          │   │ └────────────┘  │   │             │   │          │
  └──────────┘   └─────────────────┘   └──────────────┘   └──────────┘
                 └─── 1 DB transaction ─┘
                 
  Guarantee:
  ✅ Order IN DB ↔ Event IN outbox (atomic via DB txn)
  ✅ Outbox publisher eventually sends to Kafka (at-least-once)
  ✅ Consumer inbox pattern handles duplicates
  = End-to-end effectively-once business effect
```

### 4.6 End-to-End Effectively-Once Design — Putting It All Together

```
Complete effectively-once architecture:

  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  Service A                                                   │
  │  ┌──────────────────────────────┐                            │
  │  │ DB Transaction:              │                            │
  │  │  INSERT INTO orders (...)    │                            │
  │  │  INSERT INTO outbox (...)    │ ← Outbox Pattern           │
  │  └──────────────────────────────┘                            │
  │           │                                                  │
  │           ▼                                                  │
  │  Outbox Publisher (Debezium CDC)                              │
  │           │                                                  │
  │           ▼                                                  │
  │  ┌──────────────────────────────┐                            │
  │  │ Kafka (idempotent producer)  │ ← Producer Idempotence     │
  │  │ Topic: order-events          │                            │
  │  └──────────────────────────────┘                            │
  │           │                                                  │
  │           ▼                                                  │
  │  Service B (Consumer)                                        │
  │  ┌──────────────────────────────┐                            │
  │  │ DB Transaction:              │                            │
  │  │  INSERT INTO inbox (msg_id)  │ ← Inbox Pattern            │
  │  │  ON CONFLICT DO NOTHING      │                            │
  │  │  IF inserted:                │                            │
  │  │    process business logic    │                            │
  │  │    INSERT INTO outbox (...)  │ ← Outbox for next event    │
  │  └──────────────────────────────┘                            │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘

  Guarantees at each stage:
  1. Service A → DB:      Atomic (DB transaction)
  2. DB → Kafka:          At-least-once (outbox publisher retries)  
  3. Kafka internal:      Idempotent retries / transaction scope nếu dùng Kafka transaction
  4. Kafka → Service B:   At-least-once (consumer retry on crash)
  5. Service B → DB:      Idempotent (inbox dedup)
  
  End-to-end effect: effectively-once business effect ✅
```

---

## 5. Trade-off Analysis

### Delivery Semantics Comparison

| Tiêu chí | At-Most-Once | At-Least-Once | Exactly-Once (Kafka) | Exactly-Once (E2E) |
|----------|-------------|--------------|---------------------|-------------------|
| Data loss | Có thể | Không | Không | Không |
| Duplicates | Không | Có thể | Không (Kafka scope) | Không |
| Throughput | Cao nhất | Cao | Trung bình (~20% penalty) | Thấp nhất |
| Latency | Thấp nhất | Thấp | Trung bình | Cao nhất |
| Complexity | Thấp | Thấp | Trung bình | **Cao** |
| Config | acks=0 | acks=all, retry | + transactions | + inbox/outbox |
| Use case | Metrics | Events, logs | Stream processing | Payments, orders |

### Idempotency Implementation Options

| Option | Throughput | Durability | Complexity | Use Case |
|--------|-----------|-----------|-----------|----------|
| No dedup (at-least-once) | ✅ Cao | N/A | Thấp | Idempotent operations (UPSERT) |
| In-memory Set | ✅ Cao | ❌ Mất khi restart | Thấp | Short-lived consumers, acceptable dup window |
| Redis dedup | ✅ Cao | ✅ (depending on config) | Trung bình | High throughput + dedup |
| **Inbox table (DB)** | ⚠️ Trung bình | ✅ Persist | Trung bình | **Production default** |
| Kafka Transactions | ⚠️ Trung bình | ✅ Kafka scope | Cao | Kafka-to-Kafka processing |

### Outbox Pattern: Polling vs CDC

| Tiêu chí | Polling | CDC (Debezium) |
|----------|---------|----------------|
| Latency | Polling interval (100ms-5s) | Near real-time (~ms) |
| Complexity | Đơn giản (cron job / goroutine) | Cần Debezium + Kafka Connect |
| Ordering | Dễ đảm bảo (ORDER BY id) | Đảm bảo tự nhiên (WAL order) |
| Load on DB | Poll query mỗi interval | Đọc WAL (minimal) |
| Infrastructure | Không cần thêm | Kafka Connect cluster |
| **Recommendation** | **Prototype, small scale** | **Production, large scale** |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

1. **Default: at-least-once + idempotent consumer**. Đây là sweet spot cho 90% production use cases. Kafka transactions chỉ cần cho Kafka-to-Kafka exactly-once.

2. **Inbox table là production pattern**: Kết hợp inbox check + business logic trong cùng 1 DB transaction. Cheap (1 extra INSERT) và reliable.

3. **Deduplication key design**: Dùng message ID có ý nghĩa business (`orderId-eventType-version`) thay vì random UUID. Giúp debug và trace.

4. **Inbox cleanup**: Inbox table tăng vô hạn. Schedule cleanup job xóa records cũ hơn retention window (ví dụ: 7 ngày). Consumer lag phải < cleanup window!

```sql
DELETE FROM inbox WHERE processed_at < NOW() - INTERVAL '7 days';
```

5. **Outbox pattern khi cần DB + Kafka consistency**: KHÔNG ghi trực tiếp cả DB và Kafka trong application code. Luôn dùng outbox.

6. **Kafka transactions cho Kafka-to-Kafka stream processing**: Nếu đang dùng Kafka Streams, set `processing.guarantee=exactly_once_v2` khi cần. Kafka Streams atomic output + offset + changelog trong Kafka, nhưng external DB/API side effects vẫn cần idempotency riêng.

### Common Pitfalls

1. **❌ Nghĩ `enable.idempotence=true` là exactly-once end-to-end**: Idempotent producer chỉ protect Kafka broker-level duplicates từ producer retries. Consumer side KHÔNG được protect.

2. **❌ Dual write (DB + Kafka trực tiếp)**: `db.insert()` then `kafka.send()` → crash giữa 2 calls → inconsistency. PHẢI dùng outbox pattern.

3. **❌ Inbox cleanup window < consumer lag**: Nếu inbox xóa records sau 1 giờ nhưng consumer lag 2 giờ → consumer re-process message → inbox không có record → DUPLICATE!

4. **❌ Dùng Kafka transaction cho external DB writes**: Kafka transactions chỉ cover Kafka topics. KHÔNG thể include DB write trong Kafka transaction.

5. **❌ Random UUID làm message ID**: Debug nightmare. Dùng deterministic ID: `{source}-{entity_id}-{event_type}-{version}` (ví dụ: `order-svc-order123-created-v1`).

6. **❌ In-memory dedup cho long-running consumers**: Memory leak nếu không cleanup. Consumer restart → dedup set rỗng → duplicate window equal to uncommitted offset range.

---

## 7. Performance Considerations

### Transaction Performance Impact

```
Throughput impact of Kafka transactions:
  Without transactions:  ~100,000 msg/s (producer)
  With transactions:     ~70,000-80,000 msg/s (~20-30% penalty)
  
  Tại sao chậm hơn?
  ├── InitTransactions(): 1 RPC to coordinator
  ├── BeginTransaction(): local
  ├── Add partitions: 1 RPC per new partition in txn
  ├── Send messages: same as non-txn
  ├── CommitTransaction(): 
  │   ├── Write PREPARE marker
  │   ├── Write COMMIT markers đến mọi partitions
  │   └── 2-3 RPCs
  └── Total overhead: ~5-10ms per transaction

Optimization:
  → Batch nhiều messages trong 1 transaction (giảm overhead/message)
  → 1 transaction per batch (100-1000 messages) thay vì per message
  → Transaction interval = linger.ms cho producer
```

### Inbox Pattern Performance

```
Inbox table performance:
  Per message:
    1 ALTER TABLE inbox (INSERT ON CONFLICT): ~0.5-1ms
    1 Business logic query: varies
    
  Throughput impact: 
    Without inbox: 10,000 msg/s (DB-bound)
    With inbox:    7,000-8,000 msg/s (~20-30% penalty from extra query)
    
  Optimization:
  1. Batch inbox checks:
     SELECT message_id FROM inbox WHERE message_id IN ('id1','id2',...,'id100');
     → 1 query per batch instead of per message
     
  2. Partitioned inbox table (by date):
     CREATE TABLE inbox_2024_01 PARTITION OF inbox FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
     → Fast cleanup (DROP PARTITION) instead of DELETE
     
  3. Index optimization:
     CREATE INDEX idx_inbox_message_id ON inbox (message_id);
     → Already PRIMARY KEY, but ensure btree for fast lookup
```

### Metrics Quan Trọng

| Metric | Ý nghĩa | Alert |
|--------|---------|-------|
| `inbox_duplicates_total` | Số messages bị dedup | Tăng đột ngột = potential issue |
| `inbox_table_size` | Số rows trong inbox | Growing unbounded = cleanup issue |
| `outbox_unpublished_count` | Outbox events chưa publish | > 0 sustained = publisher stuck |
| `outbox_publish_latency` | Thời gian từ insert đến publish | > 5s = latency concern |
| `txn_commit_latency` | Kafka transaction commit time | > 100ms |
| `consumer_processing_time` | Time per message including dedup | Increasing = potential bottleneck |

---

## 8. Hands-on Lab

Lab objective trong 2 giờ: chứng minh **duplicate suppression** và **crash recovery** bằng inbox table, sau đó demo outbox để tránh dual write. Lab này **không claim** đang chạy Kafka transactional producer; `kafka-go` không phải client phù hợp để dạy `InitTransactions`/`SendOffsetsToTransaction`. Nếu cần prove `read_committed`, dùng Java client hoặc librdkafka ở exercise riêng.

### 8.1 Setup

```bash
mkdir -p day-15-lab && cd day-15-lab
go mod init day15-delivery-semantics
go get github.com/segmentio/kafka-go
go get github.com/lib/pq

# Start PostgreSQL cho inbox/outbox patterns
# Thêm vào docker-compose.yml (hoặc chạy riêng):
```

```yaml
# docker-compose-postgres.yml
version: '3.8'
services:
  postgres:
    image: postgres:16
    container_name: postgres-lab
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: kafka_lab
      POSTGRES_PASSWORD: kafka_lab
      POSTGRES_DB: kafka_lab
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
docker compose -f docker-compose-postgres.yml up -d

# Setup database tables
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
CREATE TABLE IF NOT EXISTS inbox (
    message_id  VARCHAR(255) PRIMARY KEY,
    topic       VARCHAR(255) NOT NULL,
    partition_num INTEGER,
    offset_num  BIGINT,
    payload     JSONB,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id          VARCHAR(255) PRIMARY KEY,
    user_id     VARCHAR(255),
    product     VARCHAR(255),
    amount      DECIMAL(10,2),
    status      VARCHAR(50) DEFAULT 'created',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outbox (
    id              BIGSERIAL PRIMARY KEY,
    aggregate_type  VARCHAR(255) NOT NULL,
    aggregate_id    VARCHAR(255) NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published       BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_outbox_unpublished ON outbox (published, created_at) WHERE published = FALSE;
SQL

# Tạo Kafka topics
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic order-events --partitions 3 --replication-factor 3

docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --create --topic payment-events --partitions 3 --replication-factor 3
```

### 8.2 Idempotent Consumer với Inbox Pattern

```go
// inbox_consumer.go — Idempotent consumer using inbox table
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
	_ "github.com/lib/pq"
)

type OrderEvent struct {
	EventID   string  `json:"event_id"`
	OrderID   string  `json:"order_id"`
	UserID    string  `json:"user_id"`
	Product   string  `json:"product"`
	Amount    float64 `json:"amount"`
	EventType string  `json:"event_type"`
	Timestamp string  `json:"timestamp"`
}

func main() {
	db, err := sql.Open("postgres",
		"host=localhost port=5432 user=kafka_lab password=kafka_lab dbname=kafka_lab sslmode=disable")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  []string{"localhost:9092"},
		Topic:    "order-events",
		GroupID:  "order-processor-idempotent",
		MaxBytes: 10e6,
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	var processed, duplicates int64

	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				p := atomic.LoadInt64(&processed)
				d := atomic.LoadInt64(&duplicates)
				fmt.Printf("[Stats] Processed: %d | Duplicates skipped: %d\n", p, d)
			}
		}
	}()

	fmt.Println("Idempotent consumer started. Waiting for messages...")

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				break
			}
			log.Printf("Fetch error: %v", err)
			continue
		}

		var event OrderEvent
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			log.Printf("Unmarshal error: %v", err)
			reader.CommitMessages(ctx, msg)
			continue
		}

		isDuplicate, err := processWithInbox(db, event, msg)
		if err != nil {
			log.Printf("Process error: %v", err)
			continue
		}

		if isDuplicate {
			atomic.AddInt64(&duplicates, 1)
			fmt.Printf("[DUP] Skipped duplicate: %s\n", event.EventID)
		} else {
			atomic.AddInt64(&processed, 1)
			fmt.Printf("[NEW] Processed: %s (order=%s, type=%s)\n",
				event.EventID, event.OrderID, event.EventType)
		}

		if os.Getenv("CRASH_AFTER_DB_COMMIT") == "1" && !isDuplicate {
			fmt.Println("[CRASH TEST] DB transaction committed but Kafka offset not committed yet.")
			fmt.Println("[CRASH TEST] Restart consumer without env var; same event must be skipped by inbox.")
			os.Exit(2)
		}

		reader.CommitMessages(ctx, msg)
	}

	fmt.Printf("\nFinal: Processed=%d, Duplicates=%d\n",
		atomic.LoadInt64(&processed), atomic.LoadInt64(&duplicates))
}

func processWithInbox(db *sql.DB, event OrderEvent, msg kafka.Message) (bool, error) {
	tx, err := db.Begin()
	if err != nil {
		return false, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Step 1: Inbox check — INSERT ON CONFLICT DO NOTHING
	payload, _ := json.Marshal(event)
	result, err := tx.Exec(`
		INSERT INTO inbox (message_id, topic, partition_num, offset_num, payload)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (message_id) DO NOTHING`,
		event.EventID, msg.Topic, msg.Partition, msg.Offset, payload)
	if err != nil {
		return false, fmt.Errorf("inbox insert: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		return true, nil // DUPLICATE — skip business logic
	}

	// Step 2: Business logic (only if NOT duplicate)
	switch event.EventType {
	case "order.created":
		_, err = tx.Exec(`
			INSERT INTO orders (id, user_id, product, amount, status)
			VALUES ($1, $2, $3, $4, 'created')
			ON CONFLICT (id) DO NOTHING`,
			event.OrderID, event.UserID, event.Product, event.Amount)

	case "order.paid":
		_, err = tx.Exec(`
			UPDATE orders SET status = 'paid', updated_at = NOW()
			WHERE id = $1`,
			event.OrderID)

	case "order.shipped":
		_, err = tx.Exec(`
			UPDATE orders SET status = 'shipped', updated_at = NOW()
			WHERE id = $1`,
			event.OrderID)
	}

	if err != nil {
		return false, fmt.Errorf("business logic: %w", err)
	}

	return false, tx.Commit()
}
```

### 8.3 Producer — Gửi messages (có simulate duplicates)

```go
// producer_with_duplicates.go — Simulate duplicate messages
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
	EventID   string  `json:"event_id"`
	OrderID   string  `json:"order_id"`
	UserID    string  `json:"user_id"`
	Product   string  `json:"product"`
	Amount    float64 `json:"amount"`
	EventType string  `json:"event_type"`
	Timestamp string  `json:"timestamp"`
}

func main() {
	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "order-events",
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 1 * time.Millisecond,
	}
	defer writer.Close()

	events := []OrderEvent{
		{EventID: "evt-001", OrderID: "order-100", UserID: "user-alice", Product: "Laptop", Amount: 999.99, EventType: "order.created"},
		{EventID: "evt-002", OrderID: "order-101", UserID: "user-bob", Product: "Phone", Amount: 599.99, EventType: "order.created"},
		{EventID: "evt-003", OrderID: "order-100", UserID: "user-alice", Product: "Laptop", Amount: 999.99, EventType: "order.paid"},
		// DUPLICATE! Simulate retry
		{EventID: "evt-001", OrderID: "order-100", UserID: "user-alice", Product: "Laptop", Amount: 999.99, EventType: "order.created"},
		{EventID: "evt-003", OrderID: "order-100", UserID: "user-alice", Product: "Laptop", Amount: 999.99, EventType: "order.paid"},
		// New events
		{EventID: "evt-004", OrderID: "order-102", UserID: "user-charlie", Product: "Tablet", Amount: 399.99, EventType: "order.created"},
		{EventID: "evt-005", OrderID: "order-101", UserID: "user-bob", Product: "Phone", Amount: 599.99, EventType: "order.paid"},
		// More duplicates
		{EventID: "evt-004", OrderID: "order-102", UserID: "user-charlie", Product: "Tablet", Amount: 399.99, EventType: "order.created"},
		{EventID: "evt-006", OrderID: "order-100", UserID: "user-alice", Product: "Laptop", Amount: 999.99, EventType: "order.shipped"},
	}

	fmt.Printf("Sending %d messages (including intentional duplicates)...\n\n", len(events))

	for i, event := range events {
		event.Timestamp = time.Now().Format(time.RFC3339)
		value, _ := json.Marshal(event)

		err := writer.WriteMessages(context.Background(), kafka.Message{
			Key:   []byte(event.OrderID),
			Value: value,
		})
		if err != nil {
			log.Printf("Send error: %v", err)
			continue
		}

		isDup := ""
		for j := 0; j < i; j++ {
			if events[j].EventID == event.EventID {
				isDup = " ← DUPLICATE"
				break
			}
		}
		fmt.Printf("[%d] Sent: event=%s order=%s type=%s%s\n",
			i+1, event.EventID, event.OrderID, event.EventType, isDup)
	}

	fmt.Println("\n→ Run inbox_consumer.go and observe:")
	fmt.Println("  - Unique events processed: 6")
	fmt.Println("  - Duplicates skipped: 3")
	fmt.Println("  - Database will have exactly 3 orders with correct states")
}
```

### 8.4 Outbox Publisher

```go
// outbox_publisher.go — Poll outbox table and publish to Kafka
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
	_ "github.com/lib/pq"
)

func main() {
	db, err := sql.Open("postgres",
		"host=localhost port=5432 user=kafka_lab password=kafka_lab dbname=kafka_lab sslmode=disable")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
	defer writer.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sigChan; cancel() }()

	fmt.Println("Outbox publisher started. Polling every 500ms...")

	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	totalPublished := 0

	for {
		select {
		case <-ctx.Done():
			fmt.Printf("Publisher stopped. Total published: %d\n", totalPublished)
			return
		case <-ticker.C:
			count, err := publishBatch(ctx, db, writer)
			if err != nil {
				log.Printf("Publish error: %v", err)
				continue
			}
			if count > 0 {
				totalPublished += count
				fmt.Printf("Published %d outbox events (total: %d)\n", count, totalPublished)
			}
		}
	}
}

func publishBatch(ctx context.Context, db *sql.DB, writer *kafka.Writer) (int, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, aggregate_type, aggregate_id, event_type, payload
		FROM outbox
		WHERE published = FALSE
		ORDER BY id
		LIMIT 100`)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	type outboxRecord struct {
		id            int64
		aggregateType string
		aggregateID   string
		eventType     string
		payload       json.RawMessage
	}

	var records []outboxRecord
	for rows.Next() {
		var r outboxRecord
		if err := rows.Scan(&r.id, &r.aggregateType, &r.aggregateID, &r.eventType, &r.payload); err != nil {
			return 0, err
		}
		records = append(records, r)
	}

	if len(records) == 0 {
		return 0, nil
	}

	for _, r := range records {
		topic := fmt.Sprintf("%s-events", r.aggregateType)
		err := writer.WriteMessages(ctx, kafka.Message{
			Topic: topic,
			Key:   []byte(r.aggregateID),
			Value: r.payload,
			Headers: []kafka.Header{
				{Key: "event_type", Value: []byte(r.eventType)},
				{Key: "outbox_id", Value: []byte(fmt.Sprintf("%d", r.id))},
			},
		})
		if err != nil {
			return 0, fmt.Errorf("kafka send for outbox %d: %w", r.id, err)
		}

		_, err = db.ExecContext(ctx,
			"UPDATE outbox SET published = TRUE WHERE id = $1", r.id)
		if err != nil {
			return 0, fmt.Errorf("mark published %d: %w", r.id, err)
		}
	}

	return len(records), nil
}
```

### 8.5 Outbox Writer — Service ghi DB + outbox atomically

```go
// outbox_writer.go — Simulate service writing to DB + outbox in same transaction
package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"time"

	_ "github.com/lib/pq"
)

type OrderCommand struct {
	OrderID string  `json:"order_id"`
	UserID  string  `json:"user_id"`
	Product string  `json:"product"`
	Amount  float64 `json:"amount"`
}

func main() {
	db, err := sql.Open("postgres",
		"host=localhost port=5432 user=kafka_lab password=kafka_lab dbname=kafka_lab sslmode=disable")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	orders := []OrderCommand{
		{OrderID: "order-200", UserID: "user-diana", Product: "Monitor", Amount: 450.00},
		{OrderID: "order-201", UserID: "user-eve", Product: "Keyboard", Amount: 120.00},
		{OrderID: "order-202", UserID: "user-frank", Product: "Mouse", Amount: 60.00},
	}

	for _, order := range orders {
		if err := createOrderWithOutbox(db, order); err != nil {
			log.Printf("Failed to create order %s: %v", order.OrderID, err)
			continue
		}
		fmt.Printf("Created order %s + outbox event (atomic!) \n", order.OrderID)
	}

	// Verify
	var orderCount, outboxCount int
	db.QueryRow("SELECT COUNT(*) FROM orders WHERE id LIKE 'order-2%'").Scan(&orderCount)
	db.QueryRow("SELECT COUNT(*) FROM outbox WHERE published = FALSE").Scan(&outboxCount)

	fmt.Printf("\nOrders in DB: %d\n", orderCount)
	fmt.Printf("Unpublished outbox events: %d\n", outboxCount)
	fmt.Println("\n→ Run outbox_publisher.go to publish events to Kafka")
	fmt.Println("→ Then run inbox_consumer.go to consume with idempotency")
}

func createOrderWithOutbox(db *sql.DB, order OrderCommand) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Step 1: Insert order (business data)
	_, err = tx.Exec(`
		INSERT INTO orders (id, user_id, product, amount, status)
		VALUES ($1, $2, $3, $4, 'created')`,
		order.OrderID, order.UserID, order.Product, order.Amount)
	if err != nil {
		return fmt.Errorf("insert order: %w", err)
	}

	// Step 2: Insert outbox event (same transaction!)
	eventPayload := map[string]interface{}{
		"event_id":   fmt.Sprintf("evt-%s-%d", order.OrderID, time.Now().UnixNano()),
		"order_id":   order.OrderID,
		"user_id":    order.UserID,
		"product":    order.Product,
		"amount":     order.Amount,
		"event_type": "order.created",
		"timestamp":  time.Now().Format(time.RFC3339),
	}
	payload, _ := json.Marshal(eventPayload)

	_, err = tx.Exec(`
		INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
		VALUES ($1, $2, $3, $4)`,
		"order", order.OrderID, "order.created", payload)
	if err != nil {
		return fmt.Errorf("insert outbox: %w", err)
	}

	// ATOMIC COMMIT — cả order VÀ outbox event
	return tx.Commit()
}
```

### 8.6 Verify Lab Results

```bash
# Chạy lab theo thứ tự:

# 1. Producer gửi messages (có duplicates)
go run producer_with_duplicates.go

# 2. Consumer xử lý với inbox pattern
go run inbox_consumer.go
# → Quan sát: 6 processed, 3 duplicates skipped

# 3. Verify database
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
SELECT '=== Orders ===' as section;
SELECT id, user_id, product, amount, status FROM orders ORDER BY id;

SELECT '=== Inbox ===' as section;
SELECT message_id, topic, processed_at FROM inbox ORDER BY processed_at;

SELECT '=== Inbox Stats ===' as section;
SELECT COUNT(*) as total_inbox, COUNT(DISTINCT message_id) as unique_messages FROM inbox;
SQL

# 4. Outbox pattern demo
go run outbox_writer.go        # Insert orders + outbox events
go run outbox_publisher.go     # Publish outbox to Kafka

# 5. Inbox cleanup (maintenance)
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab -c \
  "SELECT COUNT(*) as inbox_size FROM inbox;"
```

### 8.7 Acceptance Tests — Duplicate và Crash Recovery

Chạy các acceptance này trước khi coi lab đạt mục tiêu. Mỗi test dùng database sạch để kết quả không bị lẫn từ lần chạy trước.

```bash
# Reset DB state
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
TRUNCATE TABLE inbox, orders, outbox RESTART IDENTITY;
SQL

# Đảm bảo consumer group không còn chạy trước khi delete/reset group
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --delete --group order-processor-idempotent 2>/dev/null || true
```

**Acceptance 1 — duplicate messages không tạo duplicate business effect**

```bash
go run producer_with_duplicates.go
go run inbox_consumer.go
# Dừng consumer bằng Ctrl+C sau khi thấy processed=6 và duplicates=3.

docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
SELECT COUNT(*) AS inbox_unique_events FROM inbox;           -- expected: 6
SELECT COUNT(*) AS order_rows FROM orders;                   -- expected: 3
SELECT id, COUNT(*) FROM orders GROUP BY id HAVING COUNT(*) > 1; -- expected: 0 rows
SQL
```

**Acceptance 2 — crash sau DB commit nhưng trước offset commit**

```bash
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
TRUNCATE TABLE inbox, orders, outbox RESTART IDENTITY;
SQL

docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --delete --group order-processor-idempotent 2>/dev/null || true

go run producer_with_duplicates.go

# Bash:
CRASH_AFTER_DB_COMMIT=1 go run inbox_consumer.go

# PowerShell:
# $env:CRASH_AFTER_DB_COMMIT="1"; go run inbox_consumer.go; Remove-Item Env:CRASH_AFTER_DB_COMMIT

# Restart bình thường. Event đã commit DB trước crash phải bị inbox skip, rồi consumer xử lý tiếp.
go run inbox_consumer.go

docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
SELECT COUNT(*) AS inbox_unique_events FROM inbox;           -- expected: 6
SELECT COUNT(*) AS order_rows FROM orders;                   -- expected: 3
SELECT id, COUNT(*) FROM orders GROUP BY id HAVING COUNT(*) > 1; -- expected: 0 rows
SQL
```

Cleanup sau acceptance:

```bash
docker exec -i postgres-lab psql -U kafka_lab -d kafka_lab <<'SQL'
TRUNCATE TABLE inbox, orders, outbox RESTART IDENTITY;
SQL
docker exec kafka-1 kafka-consumer-groups.sh --bootstrap-server localhost:9094 \
  --delete --group order-processor-idempotent 2>/dev/null || true
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --delete --topic payment-events --if-exists
docker exec kafka-1 kafka-topics.sh --bootstrap-server localhost:9094 \
  --delete --topic order-events --if-exists
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Giải thích tại sao "exactly-once" trong Kafka thực ra là "effectively-once".** Kafka transactions cover phần nào? Application phải handle phần nào? (Hint: Kafka scope vs external systems)

2. **Consumer đang dùng inbox table pattern. Inbox cleanup job chạy mỗi giờ, xóa records > 1 giờ. Consumer lag đột ngột tăng lên 2 giờ. Điều gì xảy ra?** Cách fix? (Hint: inbox record đã xóa + message re-process)

3. **So sánh 3 cách implement idempotent consumer: in-memory Set vs Redis vs Inbox table.** Khi nào chọn cái nào? Trade-off cụ thể. (Hint: durability, performance, complexity)

4. **Transactional Outbox Pattern: tại sao PHẢI ghi DB + outbox trong cùng 1 DB transaction?** Cho scenario failure khi KHÔNG dùng cùng transaction. (Hint: crash between two writes)

5. **Kafka Transactions: `transactional.id` phải unique per producer instance. Khi scale up 3 instances, bạn assign ID thế nào?** Khi scale down thì sao? (Hint: static assignment, partition affinity)

6. **`isolation.level=read_committed` vs `read_uncommitted` — consumer nào nên dùng cái nào?** Cho scenario cụ thể khi `read_uncommitted` gây vấn đề. (Hint: aborted transaction, phantom reads)

7. **Design end-to-end exactly-once cho flow: User clicks "Pay" → Payment Service → Kafka → Order Service → DB update.** Vẽ architecture với outbox, inbox, và idempotency tại mỗi stage. (Hint: combine outbox + inbox + dedup key)

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Transactions](https://kafka.apache.org/documentation/#semantics) — Official semantics docs
- [KIP-98: Exactly Once Delivery and Transactional Messaging](https://cwiki.apache.org/confluence/display/KAFKA/KIP-98+-+Exactly+Once+Delivery+and+Transactional+Messaging)
- [KIP-447: Producer Scalability for Exactly Once Semantics](https://cwiki.apache.org/confluence/display/KAFKA/KIP-447%3A+Producer+scalability+for+exactly+once+semantics)
- [Kafka Streams Exactly-Once](https://kafka.apache.org/documentation/streams/core-concepts#streams_processing_guarantee)

### Blog Posts Chất Lượng
- [Exactly-Once Semantics Are Possible: Here's How Kafka Does It](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) — Confluent (MUST READ)
- [Transactions in Apache Kafka](https://www.confluent.io/blog/transactions-apache-kafka/) — Confluent
- [Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html) — microservices.io
- [Idempotent Consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html) — microservices.io
- [The Outbox Pattern](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/) — Debezium

### Videos
- [Transactions in Apache Kafka](https://www.youtube.com/watch?v=5ZjhNTM1sgw) — Confluent
- [Exactly-Once Made Easy](https://www.youtube.com/watch?v=Vo_TXRCY3Xc) — Kafka Summit
- [The Outbox Pattern with Debezium](https://www.youtube.com/watch?v=_XY8GBnalJk) — Gunnar Morling
- [Idempotency and Exactly-Once in Distributed Systems](https://www.youtube.com/watch?v=IP-rGJKSZ3s) — Martin Kleppmann
