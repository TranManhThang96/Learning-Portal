# Day 17: Kafka Connect + CDC — Source & Sink Connectors, Debezium, Transactional Outbox

> Companion split: xem `document.md` để đào sâu CDC/outbox operations và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** Kafka Connect architecture — tại sao cần framework riêng thay vì viết producer/consumer thủ công
2. **Nắm vững** Source vs Sink connectors — standalone vs distributed mode, configuration, error handling
3. **Thực hành** Debezium CDC — capture database changes real-time, hiểu CDC internals (WAL/binlog)
4. **Áp dụng** Single Message Transforms (SMT) — transform data on-the-fly không cần code
5. **Triển khai** Transactional Outbox Pattern với Debezium — giải quyết dual-write problem

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-15 (Kafka fundamentals, producer/consumer, transactions)
- Đã hoàn thành Day 16 (Schema Registry, Avro — Connect dùng schema cho data)
- Hiểu database basics: SQL, transactions, WAL (Write-Ahead Log)
- Hiểu microservices communication patterns
- Docker Compose Kafka cluster + Schema Registry đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Kafka Connect architecture — Workers, Tasks, Converters, Transforms
- Source vs Sink connectors — khi nào dùng gì
- Debezium CDC fundamentals — WAL-based change capture, event format
- Standalone vs Distributed mode — trade-offs
- Hands-on: Debezium PostgreSQL CDC → Kafka → Elasticsearch sink

### 🟡 Should Learn (nếu còn thời gian)
- Single Message Transforms (SMT) — routing, filtering, field manipulation
- Transactional Outbox Pattern với Debezium
- Dead Letter Queue trong Connect
- Connector monitoring và error handling

### 🟢 Optional Deep Dive
- Custom connector development
- Debezium embedded engine (library mode)
- Schema evolution trong CDC pipeline
- MirrorMaker 2 (Kafka→Kafka replication dùng Connect)

---

## 4. Lý thuyết (Theory)

### 4.1 Tại sao cần Kafka Connect?

#### WHY — Vấn đề Data Integration

Trong microservices, data nằm rải rác ở nhiều systems: PostgreSQL, MySQL, MongoDB, Elasticsearch, S3, Redis, etc. Bạn cần **sync data** giữa các systems.

```
VẤN ĐỀ KHI VIẾT CUSTOM CODE:

  ┌──────────┐     custom producer      ┌──────────┐
  │PostgreSQL│────────────────────────►│  Kafka   │
  └──────────┘                          └──────────┘
                                              │
  Phải tự handle:                             │ custom consumer
  ✗ Connection management                     │
  ✗ Error handling + retry                    ▼
  ✗ Offset tracking (đã đọc đến đâu?)  ┌──────────┐
  ✗ Schema conversion                   │  Elastic │
  ✗ Parallelism / scaling               └──────────┘
  ✗ Monitoring
  ✗ Exactly-once end-to-end (Connect/CDC thường là at-least-once; sink phải idempotent)
  ✗ Dead letter queue
  
  → Mỗi integration = 500-2000 dòng boilerplate code
  → 10 integrations = 10x maintenance burden
  → Mỗi team viết khác nhau, quality không đồng đều


KAFKA CONNECT GIẢI QUYẾT:

  ┌──────────┐     Source Connector      ┌──────────┐     Sink Connector      ┌──────────┐
  │PostgreSQL│────────────────────────►│  Kafka   │────────────────────────►│  Elastic │
  └──────────┘    (Debezium)            └──────────┘    (ES Sink)           └──────────┘
  
  Kafka Connect cung cấp SẴN:
  ✓ Scalable framework (distributed workers)
  ✓ Fault tolerance (task redistribution)
  ✓ Offset management (tự track progress)
  ✓ Schema integration (Schema Registry)
  ✓ REST API quản lý (deploy, pause, resume, delete)
  ✓ Dead letter queue
  ✓ Monitoring (JMX metrics)
  ✓ 100+ connectors có sẵn (community + Confluent)
  ✓ Delivery thực tế: at-least-once; duplicate có thể xảy ra sau restart/retry
  
  → Config JSON thay vì code
  → 0 custom code cho standard integrations
  → Sink production phải idempotent: upsert theo primary key, dedup key, hoặc transactional sink riêng
```

#### WHAT — Kafka Connect Architecture

```
KAFKA CONNECT CLUSTER:

  ┌─────────────────────────────────────────────────┐
  │              Connect Cluster                     │
  │                                                  │
  │  ┌─────────────┐  ┌─────────────┐              │
  │  │  Worker 1    │  │  Worker 2    │              │
  │  │             │  │             │              │
  │  │ ┌─────────┐ │  │ ┌─────────┐ │              │
  │  │ │Connector│ │  │ │Connector│ │              │
  │  │ │  Config  │ │  │ │  Config  │ │              │
  │  │ └────┬────┘ │  │ └────┬────┘ │              │
  │  │      │      │  │      │      │              │
  │  │ ┌────▼────┐ │  │ ┌────▼────┐ │              │
  │  │ │ Task 0  │ │  │ │ Task 1  │ │              │
  │  │ │ Task 1  │ │  │ │ Task 2  │ │              │
  │  │ └─────────┘ │  │ └─────────┘ │              │
  │  └─────────────┘  └─────────────┘              │
  │         │                │                      │
  │         └───────┬────────┘                      │
  │                 │                                │
  │    ┌────────────▼────────────┐                  │
  │    │   Internal Topics       │                  │
  │    │ connect-configs         │ ← connector configs  │
  │    │ connect-offsets          │ ← source offsets     │
  │    │ connect-status           │ ← connector status   │
  │    └─────────────────────────┘                  │
  └─────────────────────────────────────────────────┘

  Terminology:
  ┌──────────────────────────────────────────────────┐
  │ Worker     = JVM process chạy Connect framework   │
  │ Connector  = Java class + config cho 1 integration│
  │ Task       = Unit of parallelism trong connector   │
  │ Converter  = Serialize/deserialize data format     │
  │ Transform  = SMT — modify record on-the-fly       │
  └──────────────────────────────────────────────────┘
```

#### HOW — Data Flow Chi Tiết

```
SOURCE CONNECTOR FLOW:

  ┌────────┐                ┌──────────────────────────┐
  │External│   poll()       │     Connect Worker        │
  │System  │◄──────────────│                            │
  │(DB/API)│                │  ┌──────┐  ┌─────────┐   │
  │        │   records      │  │Source│  │Converter│   │
  │        │───────────────►│  │Task  │─►│(Avro/   │   │
  └────────┘                │  │      │  │JSON/    │   │
                            │  └──────┘  │Protobuf)│   │
                            │            └────┬────┘   │
                            │                 │         │
                            │            ┌────▼────┐   │
                            │            │  SMT    │   │ ← Optional transforms
                            │            │(filter, │   │
                            │            │ route)  │   │
                            │            └────┬────┘   │
                            └─────────────────┼────────┘
                                              │
                                              ▼
                                        ┌──────────┐
                                        │  Kafka   │
                                        │  Topic   │
                                        └──────────┘


SINK CONNECTOR FLOW:

                                        ┌──────────┐
                                        │  Kafka   │
                                        │  Topic   │
                                        └────┬─────┘
                                              │
                            ┌─────────────────┼────────┐
                            │     Connect Worker       │
                            │            ┌────▼────┐   │
                            │            │  SMT    │   │
                            │            └────┬────┘   │
                            │            ┌────▼────┐   │
                            │            │Converter│   │
                            │            └────┬────┘   │
                            │  ┌──────┐  ┌────▼────┐   │
                            │  │ Sink │◄─┤  put()  │   │
                            │  │ Task │  └─────────┘   │
                            │  └──┬───┘                │
                            └─────┼────────────────────┘
                                  │
                                  ▼
                            ┌──────────┐
                            │External  │
                            │System    │
                            │(ES/S3)   │
                            └──────────┘
```

### 4.2 Standalone vs Distributed Mode

```
STANDALONE MODE:
  ┌───────────────────────────────┐
  │      Single Worker Process     │
  │                                │
  │  ┌───────────┐ ┌───────────┐  │
  │  │Connector A│ │Connector B│  │
  │  │  Task 0   │ │  Task 0   │  │
  │  └───────────┘ └───────────┘  │
  │                                │
  │  Offsets: local file           │
  │  Config: property file         │
  └───────────────────────────────┘
  
  Khi nào dùng:
  ✅ Development / testing
  ✅ Edge processing (IoT devices)
  ✅ Single-node deployment đơn giản
  
  Hạn chế:
  ❌ Không fault tolerant (worker die = data stop)
  ❌ Không scale horizontally
  ❌ Offset lưu local file → mất khi disk fail


DISTRIBUTED MODE:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │   Worker 1    │  │   Worker 2    │  │   Worker 3    │
  │              │  │              │  │              │
  │ Connector A  │  │ Connector A  │  │ Connector B  │
  │   Task 0     │  │   Task 1     │  │   Task 0     │
  │   Task 2     │  │   Task 3     │  │   Task 1     │
  └──────────────┘  └──────────────┘  └──────────────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
              ┌───────────▼───────────┐
              │   Kafka Internal Topics│
              │  (configs, offsets,    │
              │   status)             │
              └───────────────────────┘
  
  Khi nào dùng:
  ✅ Production — LUÔN dùng distributed
  ✅ Cần fault tolerance (task auto-redistribute)
  ✅ Cần scale (thêm workers khi load tăng)
  ✅ Nhiều connectors cùng quản lý
  
  Behavior khi worker fail:
  Worker 2 die → Task 1 và Task 3 redistribute
  sang Worker 1 và Worker 3 (rebalance giống consumer group)
```

### 4.3 Change Data Capture (CDC) với Debezium

#### WHY — Dual-Write Problem

```
VẤN ĐỀ DUAL-WRITE:

  Microservice cần: 1) update DB  2) publish event
  
  Approach 1: Write DB first, then publish event
  ┌────────┐    ┌──────┐    ┌───────┐
  │Service │──►│  DB  │──►│ Kafka │   ← Step 2 fail?
  └────────┘    └──────┘    └───────┘      DB updated, event LOST!

  Approach 2: Publish event first, then write DB
  ┌────────┐    ┌───────┐    ┌──────┐
  │Service │──►│ Kafka │──►│  DB  │   ← Step 2 fail?
  └────────┘    └───────┘    └──────┘      Event published, DB NOT updated!

  Approach 3: 2PC (Two-Phase Commit)
  → Phức tạp, chậm, không scale, hầu hết message brokers KHÔNG support

  VẤN ĐỀ CỐT LÕI:
  Bạn KHÔNG THỂ atomically write vào 2 systems khác nhau
  (DB và Kafka) mà không có coordinator protocol.


GIẢI PHÁP: CDC — Database làm single source of truth

  ┌────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐
  │Service │──►│   DB     │──►│Debezium  │──►│ Kafka │
  │        │    │ (single  │    │(reads    │    │       │
  │        │    │  write)  │    │ WAL/     │    │       │
  │        │    │          │    │ binlog)  │    │       │
  └────────┘    └──────────┘    └──────────┘    └───────┘

  ✓ Service CHỈ write vào DB (single write, ACID guaranteed)
  ✓ Debezium đọc transaction log → publish changes to Kafka
  ✓ Không mất event (WAL/binlog là durable)
  ✓ Không duplicate (LSN/binlog position tracking)
  ✓ Real-time (~ms latency)
```

#### WHAT — CDC Internals

```
HOW CDC WORKS (PostgreSQL example):

  ┌──────────────────────────┐
  │      PostgreSQL           │
  │                          │
  │  ┌─────────┐             │
  │  │  Table   │             │
  │  │ orders   │             │
  │  └────┬────┘             │
  │       │ INSERT/UPDATE/    │
  │       │ DELETE            │
  │       ▼                   │
  │  ┌─────────────┐         │
  │  │ WAL (Write- │         │ ← EVERY change logged sequentially
  │  │ Ahead Log)  │         │    trước khi apply vào data files
  │  │             │         │
  │  │ LSN: 0/1A3  │         │ ← Log Sequence Number = position
  │  │ LSN: 0/1A4  │         │
  │  │ LSN: 0/1A5  │         │
  │  └──────┬──────┘         │
  │         │                │
  │  ┌──────▼──────┐         │
  │  │ Replication │         │ ← Logical replication slot
  │  │ Slot        │         │    giữ WAL entries cho Debezium
  │  │ name=...    │         │    ví dụ: orders_cdc_slot
  │  │             │         │    slot name phải unique per connector
  │  └──────┬──────┘         │
  └─────────┼────────────────┘
            │
            │ Logical Replication Protocol
            │ (streaming WAL changes)
            ▼
  ┌──────────────────┐
  │    Debezium       │
  │                  │
  │ 1. Connect to    │
  │    replication    │
  │    slot           │
  │ 2. Read WAL       │
  │    changes        │
  │ 3. Convert to     │
  │    Kafka events   │
  │ 4. Track LSN      │
  │    (offset)       │
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │   Kafka Topic     │
  │ "dbserver.public. │
  │  orders"          │
  │                  │
  │ Key: {id: 123}   │
  │ Value: {          │
  │   before: {...},  │ ← row state TRƯỚC change
  │   after: {...},   │ ← row state SAU change
  │   source: {       │
  │     lsn: "0/1A5", │
  │     txId: 567,    │
  │     ts_ms: ...    │
  │   },              │
  │   op: "u"         │ ← c=create, u=update, d=delete, r=read(snapshot)
  │ }                 │
  └──────────────────┘


CDC vs POLLING:
  ┌──────────────────────────────────────────────────────┐
  │                                                      │
  │  Polling (query DB every N seconds):                 │
  │  - SELECT * FROM orders WHERE updated_at > ?         │
  │  - Latency: seconds → minutes                       │
  │  - DELETE detection: impossible (row gone!)          │
  │  - DB load: high (repeated full scans)               │
  │  - Ordering: no guarantee                            │
  │                                                      │
  │  CDC (read transaction log):                         │
  │  - Stream từ WAL/binlog                              │
  │  - Latency: milliseconds                             │
  │  - DELETE detection: ✅ (logged in WAL)              │
  │  - DB load: minimal (replication stream)             │
  │  - Ordering: guaranteed (LSN order)                  │
  │                                                      │
  └──────────────────────────────────────────────────────┘
```

#### Debezium Event Format

```json
// Topic: dbserver1.public.orders
// Key:
{
  "schema": {...},
  "payload": {
    "id": 1001
  }
}

// Value:
{
  "schema": {...},
  "payload": {
    "before": null,
    "after": {
      "id": 1001,
      "customer_id": "cust-456",
      "amount": 99.99,
      "status": "CREATED",
      "created_at": 1704067200000
    },
    "source": {
      "version": "2.4.0.Final",
      "connector": "postgresql",
      "name": "dbserver1",
      "ts_ms": 1704067200000,
      "snapshot": "false",
      "db": "orderdb",
      "schema": "public",
      "table": "orders",
      "txId": 567,
      "lsn": 33227720,
      "xmin": null
    },
    "op": "c",
    "ts_ms": 1704067200123,
    "transaction": null
  }
}
```

### 4.4 Single Message Transforms (SMT)

#### WHY — Transform data mà không cần viết code

```
USE CASE:

  Source: PostgreSQL "users" table
  ┌──────────────────────────────────┐
  │ id │ name    │ email           │ ssn        │
  │ 1  │ Alice   │ alice@mail.com │ 123-45-6789│
  └──────────────────────────────────┘

  Vấn đề:
  - "ssn" là PII → KHÔNG được đưa vào Kafka
  - Table prefix "public." → muốn bỏ
  - "created_at" microseconds → muốn đổi sang epoch millis
  - Muốn thêm field "source_system": "order-db"

  KHÔNG CẦN viết custom connector!
  → Dùng SMT chain:

  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐
  │ Source   │──►│ MaskField│──►│ RegexRouter│──►│TimestampConverter│──►│ Kafka │
  │ Record   │    │(ssn→****)│   │(remove    │    │(μs→ms)   │    │       │
  │          │    │          │    │ prefix)   │    │          │    │       │
  └─────────┘    └──────────┘    └──────────┘    └──────────┘    └───────┘
```

#### Common SMTs

```
BUILT-IN SMTs:

1. RegexRouter — thay đổi target topic name
   "transforms": "route",
   "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
   "transforms.route.regex": "dbserver1\\.public\\.(.*)",
   "transforms.route.replacement": "cdc.$1"
   // dbserver1.public.orders → cdc.orders

2. ExtractField — lấy 1 field từ struct
   "transforms": "extractKey",
   "transforms.extractKey.type": "org.apache.kafka.connect.transforms.ExtractField$Key",
   "transforms.extractKey.field": "id"
   // Key: {"id": 123} → Key: 123

3. MaskField — mask sensitive data
   "transforms.mask.type": "org.apache.kafka.connect.transforms.MaskField$Value",
   "transforms.mask.fields": "ssn,credit_card",
   "transforms.mask.replacement": "****"

4. Filter (Debezium) — filter events
   "transforms.filter.type": "io.debezium.transforms.Filter",
   "transforms.filter.language": "jsr223.groovy",
   "transforms.filter.condition": "value.op == 'd'"
   // Drop DELETE events

5. InsertField — thêm field
   "transforms.addSource.type": "org.apache.kafka.connect.transforms.InsertField$Value",
   "transforms.addSource.static.field": "source_system",
   "transforms.addSource.static.value": "order-db"

6. Outbox Event Router (Debezium) — transactional outbox
   (chi tiết ở phần 4.5)
```

### 4.5 Transactional Outbox Pattern với Debezium

#### WHY — Giải quyết Dual-Write Problem triệt để

```
OUTBOX PATTERN FLOW:

  ┌─────────────────────────────────────────────────────┐
  │                  OrderService                        │
  │                                                     │
  │  BEGIN TRANSACTION                                   │
  │    INSERT INTO orders (id, ...) VALUES (...);        │
  │    INSERT INTO outbox (                              │
  │      id, aggregate_type, aggregate_id,              │
  │      event_type, payload                            │
  │    ) VALUES (...);                                   │
  │  COMMIT;                                            │
  │                                                     │
  │  → Cả hai writes trong 1 DB transaction             │
  │  → ACID guarantee: cả 2 thành công hoặc cả 2 fail  │
  └──────────────────────┬──────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    PostgreSQL DB     │
              │                     │
              │  ┌───────────────┐  │
              │  │ orders table  │  │
              │  └───────────────┘  │
              │  ┌───────────────┐  │
              │  │ outbox table  │  │ ← Debezium watches this table
              │  └───────┬───────┘  │
              │          │ WAL      │
              └──────────┼──────────┘
                         │
              ┌──────────▼──────────┐
              │     Debezium         │
              │  + Outbox Event      │
              │    Router SMT        │
              │                     │
              │  Reads outbox table  │
              │  changes from WAL    │
              │  Routes to proper    │
              │  Kafka topic         │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │     Kafka Topics     │
              │                     │
              │ order.events         │ ← routed by aggregate_type
              │ payment.events       │
              └──────────────────────┘


OUTBOX TABLE DESIGN:

  CREATE TABLE outbox (
      id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      aggregate_type  VARCHAR(255) NOT NULL,   -- "Order", "Payment"
      aggregate_id    VARCHAR(255) NOT NULL,   -- order ID (partition key)
      event_type      VARCHAR(255) NOT NULL,   -- "OrderCreated"
      payload         JSONB NOT NULL,          -- event data
      created_at      TIMESTAMP DEFAULT NOW(),
      
      -- Debezium đọc thay đổi từ WAL/logical replication, KHÔNG tự delete row.
      -- Application hoặc cleanup job xóa sau khi event đã đủ tuổi/đã được sink xử lý.
  );

  -- Index cho Debezium CDC performance
  CREATE INDEX idx_outbox_created_at ON outbox(created_at);
```

---

## 5. Trade-off Analysis

### Kafka Connect vs Custom Producer/Consumer

| Tiêu chí | Kafka Connect | Custom Code |
|----------|---------------|-------------|
| Development time | Phút (config JSON) | Ngày-tuần |
| Maintenance | Confluent/community maintains | Team maintains |
| Flexibility | Limited to connector features | Unlimited |
| Error handling | Built-in DLQ, retry | Must implement |
| Monitoring | Built-in JMX metrics | Must implement |
| Performance | Optimized, battle-tested | Variable |
| Learning curve | Connect concepts | Language-specific |
| **Recommendation** | **Standard integrations** | Complex business logic only |

### CDC vs Event-Driven (Application-Level Events)

| Tiêu chí | CDC (Debezium) | Application Events |
|----------|---------------|-------------------|
| Coupling | DB schema = event schema | Event schema independent |
| Completeness | ALL changes captured | Only instrumented paths |
| Latency | ~ms (WAL streaming) | ~ms (in-app publish) |
| Semantic richness | Low (CRUD operations) | High (business events) |
| Schema evolution | Tied to DB migration | Independent versioning |
| Legacy systems | ✅ No code changes needed | ❌ Must modify code |
| DB dependency | Specific DB features (WAL) | None |
| **Best for** | **Data sync, audit, legacy** | **Business events, CQRS** |

### Outbox Pattern: Debezium vs Polling Publisher

| Tiêu chí | Debezium Outbox | Polling Publisher |
|----------|----------------|-------------------|
| Latency | ~ms | Seconds (poll interval) |
| DB load | Minimal (WAL stream) | Higher (repeated queries) |
| Ordering | Guaranteed (WAL order) | Best-effort |
| Complexity | Debezium setup required | Simple cron/scheduler |
| Infrastructure | Kafka Connect cluster | Application code only |
| DELETE detection | ✅ | ❌ (polled row gone) |
| **Recommendation** | **Production at scale** | Prototype or simple cases |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. Distributed mode cho production — LUÔN
   → Standalone mode chỉ cho dev/testing
   → Minimum 2 workers cho fault tolerance

2. Converter configuration nhất quán
   → key.converter = org.apache.kafka.connect.storage.StringConverter
   → value.converter = io.confluent.connect.avro.AvroConverter
   → value.converter.schema.registry.url = http://schema-registry:8081
   → KHÔNG mix JSON và Avro trong cùng pipeline

3. Dead Letter Queue cho sink connectors
   → errors.tolerance = all
   → errors.deadletterqueue.topic.name = dlq-{connector-name}
   → errors.deadletterqueue.context.headers.enable = true
   → Monitor DLQ topic → alert khi có messages

4. tasks.max tuning
   → Source: = số tables hoặc partitions cần capture
   → Sink: ≤ số partitions của input topic (mỗi partition ≤ 1 task)
   → Quá nhiều tasks = overhead, quá ít = bottleneck

5. Debezium snapshot mode
   → initial: snapshot + streaming (default, dùng lần đầu)
   → schema_only: chỉ schema, streaming từ current position
   → never: chỉ streaming (phải có data trong topic rồi)
   → always: re-snapshot mỗi lần restart (nguy hiểm!)

6. WAL retention cho Debezium
   → PostgreSQL: wal_level = logical
   → Set max_replication_slots ≥ số Debezium connectors
   → Monitor replication lag: nếu Debezium chậm → WAL tích tụ → disk full!
```

### Common Pitfalls

```
❌ PITFALL 1: Debezium replication slot không cleanup
   Vấn đề: Debezium crash → replication slot giữ WAL → disk full
   Giải pháp: Monitor pg_replication_slots, alert khi WAL retention > threshold
   Query: SELECT slot_name, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) 
          AS lag_bytes FROM pg_replication_slots;

❌ PITFALL 2: Initial snapshot quá lớn
   Vấn đề: Table 100M rows → snapshot mất giờ, lock table, OOM
   Giải pháp: 
     - snapshot.mode = schema_only (skip data, chỉ stream từ now)
     - Hoặc: snapshot.fetch.size = 10000 (batch size nhỏ hơn)
     - Hoặc: signal-based incremental snapshot (Debezium 1.6+)

❌ PITFALL 3: CDC event = DB schema (tight coupling)
   Vấn đề: DB column rename → CDC event field rename → consumer break
   Giải pháp: 
     - Dùng SMT để transform CDC events thành stable format
     - Hoặc: Outbox pattern (event schema independent từ DB schema)

❌ PITFALL 4: Không chạy idempotent sink
   Vấn đề: Debezium resend after failure → duplicate in target
   Giải pháp: Elasticsearch sink dùng document ID = record key (upsert)
              JDBC sink dùng insert.mode = upsert

❌ PITFALL 5: Converter mismatch
   Vấn đề: Source dùng AvroConverter, Sink expect JsonConverter → deserialize fail
   Giải pháp: Dùng CÙNG converter cho source và sink
              Hoặc: dùng Schema Registry cho cả hai

❌ PITFALL 6: tasks.max > số partitions
   Vấn đề: Sink connector tasks.max = 10, topic chỉ có 3 partitions
   Kết quả: 7 tasks idle, waste resources
   Giải pháp: tasks.max ≤ số partitions
```

---

## 7. Performance Considerations

### Debezium CDC Performance

```
Throughput benchmarks (single Debezium connector):
  PostgreSQL WAL → Kafka:
  - Simple table (5 columns):    ~30,000 events/s
  - Complex table (20 columns):  ~10,000 events/s
  - With SMT transforms:         ~8,000 events/s
  
  MySQL binlog → Kafka:
  - Simple table:                ~25,000 events/s
  - Complex table:               ~8,000 events/s

Bottlenecks:
  1. Serialization: Avro ~2x faster than JSON for CDC events
  2. Snapshot phase: sequential reads, limited by DB I/O
  3. Network: WAL streaming bandwidth (usually not bottleneck)
  4. SMT chain: each transform adds ~10-50μs per record

Tuning:
  - max.batch.size = 2048 (default, increase for throughput)
  - poll.interval.ms = 500 (decrease for lower latency, increase for less CPU)
  - max.queue.size = 8192 (internal buffer, increase if producer faster than Kafka writes)
  - snapshot.fetch.size = 10240 (rows per snapshot batch)
```

### Connect Worker Tuning

```
Key configurations:
  - offset.flush.interval.ms = 60000 (default, decrease for more frequent commits)
  - offset.flush.timeout.ms = 5000
  - consumer.max.poll.records = 500 (sink connector batching)
  - producer.batch.size = 131072 (source connector produce batching)
  - producer.linger.ms = 10

Monitoring metrics (JMX):
  - kafka.connect:type=connector-task-metrics
    - source-record-poll-rate         → records/s from source
    - source-record-write-rate        → records/s to Kafka
    - sink-record-read-rate           → records/s from Kafka
    - sink-record-send-rate           → records/s to target
    - offset-commit-success-count     → successful offset commits
  
  - kafka.connect:type=connect-worker-metrics
    - connector-count                 → active connectors
    - task-count                      → active tasks
    - connector-startup-failure-total → failed connector starts

Alert thresholds:
  - source-record-poll-rate < 100 (sudden drop = source system issue)
  - sink DLQ message count > 0 (failures in sink)
  - rebalance-count frequent (worker instability)
```

---

## 8. Hands-on Lab

### 8.1 Setup — Full CDC Pipeline

Lab chính dùng `debezium/connect:2.4` để có sẵn PostgreSQL connector và Debezium Outbox Event Router. Image này **không bundle** Confluent Elasticsearch Sink Connector; bước 8.5 là optional và chỉ chạy khi bạn dùng image Connect đã cài plugin đó. Luôn verify plugin bằng `/connector-plugins` trước khi register connector.

```yaml
# docker-compose.yml
version: '3.8'
services:
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092,PLAINTEXT_HOST://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"

  schema-registry:
    image: confluentinc/cp-schema-registry:7.5.0
    depends_on:
      - kafka
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:29092

  connect:
    image: debezium/connect:2.4
    depends_on:
      - kafka
      - schema-registry
      - postgres
    ports:
      - "8083:8083"
    environment:
      BOOTSTRAP_SERVERS: kafka:29092
      GROUP_ID: connect-cluster
      CONFIG_STORAGE_TOPIC: connect-configs
      OFFSET_STORAGE_TOPIC: connect-offsets
      STATUS_STORAGE_TOPIC: connect-status
      CONFIG_STORAGE_REPLICATION_FACTOR: 1
      OFFSET_STORAGE_REPLICATION_FACTOR: 1
      STATUS_STORAGE_REPLICATION_FACTOR: 1
      KEY_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      VALUE_CONVERTER: org.apache.kafka.connect.json.JsonConverter
      KEY_CONVERTER_SCHEMAS_ENABLE: "false"
      VALUE_CONVERTER_SCHEMAS_ENABLE: "false"

  postgres:
    image: debezium/postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: orderdb
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

  elasticsearch:
    image: elasticsearch:8.10.2
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"

  kibana:
    image: kibana:8.10.2
    depends_on:
      - elasticsearch
    ports:
      - "5601:5601"
    environment:
      ELASTICSEARCH_HOSTS: http://elasticsearch:9200
```

### 8.2 Database Setup

```sql
-- init.sql
-- PostgreSQL với WAL logical replication cho Debezium

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Orders table
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    customer_id     VARCHAR(50) NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    currency        VARCHAR(3) DEFAULT 'USD',
    status          VARCHAR(20) DEFAULT 'CREATED',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Cần nếu demo muốn UPDATE/DELETE có đầy đủ "before" image.
-- Nếu không bật, PostgreSQL chỉ log key cũ; Debezium không thể dựng full before state.
ALTER TABLE orders REPLICA IDENTITY FULL;

-- Outbox table cho Transactional Outbox Pattern
CREATE TABLE outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(255) NOT NULL,
    aggregate_id    VARCHAR(255) NOT NULL,
    event_type      VARCHAR(255) NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Trigger tự update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Seed data
INSERT INTO orders (customer_id, amount, currency, status) VALUES
('cust-001', 99.99, 'USD', 'CREATED'),
('cust-002', 149.50, 'EUR', 'CREATED'),
('cust-003', 2500000, 'VND', 'CREATED');
```

```bash
# Start all services
docker compose up -d

# Wait for services to be healthy
sleep 30

# Verify Connect is running
curl http://localhost:8083/connectors
# []

# Verify connector/plugin availability trước khi register connector
curl http://localhost:8083/connector-plugins | python3 -m json.tool
# Cần thấy: io.debezium.connector.postgresql.PostgresConnector
# Nếu muốn chạy bước 8.5, cần thêm: io.confluent.connect.elasticsearch.ElasticsearchSinkConnector

# Verify PostgreSQL
docker exec -it $(docker ps -q -f name=postgres) psql -U postgres -d orderdb -c "SELECT * FROM orders;"

# Verify Elasticsearch
curl http://localhost:9200
```

### 8.3 Deploy Debezium PostgreSQL Source Connector

```bash
# Register Debezium PostgreSQL connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "orders-source",
    "config": {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "database.hostname": "postgres",
        "database.port": "5432",
        "database.user": "postgres",
        "database.password": "postgres",
        "database.dbname": "orderdb",
        "topic.prefix": "dbserver1",
        "table.include.list": "public.orders",
        "plugin.name": "pgoutput",
        "slot.name": "orders_cdc_slot",
        "publication.name": "orders_cdc_pub",
        "publication.autocreate.mode": "filtered",
        
        "snapshot.mode": "initial",
        
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": false,
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter.schemas.enable": false,
        
        "transforms": "route,extractId",
        "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
        "transforms.route.regex": "dbserver1\\.public\\.(.*)",
        "transforms.route.replacement": "cdc.$1",
        
        "transforms.extractId.type": "org.apache.kafka.connect.transforms.ExtractField$Key",
        "transforms.extractId.field": "id"
    }
}'

# Check connector status
curl http://localhost:8083/connectors/orders-source/status | python3 -m json.tool

# Check replication slot lag — quan trọng hơn "connector RUNNING" khi đánh giá CDC có kẹt không
docker exec -it $(docker ps -q -f name=postgres) \
  psql -U postgres -d orderdb -c \
  "SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes FROM pg_replication_slots;"
```

### 8.4 Verify CDC Events

```bash
# Consume CDC events từ Kafka (topic name transformed by RegexRouter)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic cdc.orders \
  --from-beginning \
  --max-messages 3

# Expected output (3 seed records from initial snapshot):
# {"before":null,"after":{"id":1,"customer_id":"cust-001","amount":99.99,...},"op":"r",...}
# "op":"r" = read (snapshot)

# Now INSERT a new order
docker exec -it $(docker ps -q -f name=postgres) \
  psql -U postgres -d orderdb -c \
  "INSERT INTO orders (customer_id, amount, status) VALUES ('cust-004', 75.00, 'CREATED');"

# Check CDC event for the INSERT (op: "c" = create)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic cdc.orders \
  --from-beginning \
  --max-messages 4

# UPDATE an order
docker exec -it $(docker ps -q -f name=postgres) \
  psql -U postgres -d orderdb -c \
  "UPDATE orders SET status = 'PAID', amount = 199.99 WHERE customer_id = 'cust-001';"

# CDC event will have op: "u" with both "before" and "after" states

# DELETE an order
docker exec -it $(docker ps -q -f name=postgres) \
  psql -U postgres -d orderdb -c \
  "DELETE FROM orders WHERE customer_id = 'cust-003';"

# CDC events: op: "d" (delete) + tombstone (null value for compacted topics)
```

### 8.5 Optional — Deploy Elasticsearch Sink Connector

```bash
# Chỉ chạy nếu /connector-plugins có:
# io.confluent.connect.elasticsearch.ElasticsearchSinkConnector
# debezium/connect:2.4 mặc định không có plugin này.

# Register Elasticsearch sink connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "orders-es-sink",
    "config": {
        "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
        "topics": "cdc.orders",
        "connection.url": "http://elasticsearch:9200",
        "type.name": "_doc",
        "key.ignore": false,
        "schema.ignore": true,
        
        "behavior.on.null.values": "DELETE",
        
        "transforms": "extractAfter",
        "transforms.extractAfter.type": "org.apache.kafka.connect.transforms.ExtractField$Value",
        "transforms.extractAfter.field": "after",
        
        "errors.tolerance": "all",
        "errors.deadletterqueue.topic.name": "dlq-orders-es-sink",
        "errors.deadletterqueue.context.headers.enable": true,
        
        "write.method": "UPSERT",
        "key.converter": "org.apache.kafka.connect.storage.StringConverter"
    }
}'

# Verify connector
curl http://localhost:8083/connectors/orders-es-sink/status | python3 -m json.tool

# Check data in Elasticsearch
curl http://localhost:9200/cdc.orders/_search?pretty
```

### 8.6 Transactional Outbox Pattern Lab

```go
// outbox-writer.go — Order service viết vào orders + outbox trong 1 transaction
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
)

type OrderCreatedEvent struct {
	OrderId    int       `json:"orderId"`
	CustomerId string    `json:"customerId"`
	Amount     float64   `json:"amount"`
	Currency   string    `json:"currency"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"createdAt"`
}

func createOrderWithOutbox(db *sql.DB, customerId string, amount float64) error {
	tx, err := db.BeginTx(context.Background(), &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// Step 1: Insert order
	var orderId int
	var createdAt time.Time
	err = tx.QueryRow(
		`INSERT INTO orders (customer_id, amount, currency, status) 
		 VALUES ($1, $2, 'USD', 'CREATED') 
		 RETURNING id, created_at`,
		customerId, amount,
	).Scan(&orderId, &createdAt)
	if err != nil {
		return fmt.Errorf("insert order: %w", err)
	}

	// Step 2: Insert outbox event (SAME transaction)
	event := OrderCreatedEvent{
		OrderId:    orderId,
		CustomerId: customerId,
		Amount:     amount,
		Currency:   "USD",
		Status:     "CREATED",
		CreatedAt:  createdAt,
	}
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}

	_, err = tx.Exec(
		`INSERT INTO outbox (id, aggregate_type, aggregate_id, event_type, payload) 
		 VALUES ($1, $2, $3, $4, $5)`,
		uuid.New().String(),
		"Order",
		fmt.Sprintf("%d", orderId),
		"OrderCreated",
		payload,
	)
	if err != nil {
		return fmt.Errorf("insert outbox: %w", err)
	}

	// COMMIT — cả order và outbox event atomically
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit: %w", err)
	}

	fmt.Printf("Order %d created with outbox event\n", orderId)
	return nil
}

func main() {
	db, err := sql.Open("postgres",
		"host=localhost port=5432 user=postgres password=postgres dbname=orderdb sslmode=disable")
	if err != nil {
		panic(err)
	}
	defer db.Close()

	for i := 0; i < 5; i++ {
		customerId := fmt.Sprintf("cust-%03d", 100+i)
		amount := 50.0 + float64(i)*25.0
		if err := createOrderWithOutbox(db, customerId, amount); err != nil {
			fmt.Printf("Error: %v\n", err)
		}
		time.Sleep(500 * time.Millisecond)
	}
}
```

```bash
# Deploy Debezium Outbox connector
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "outbox-connector",
    "config": {
        "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
        "database.hostname": "postgres",
        "database.port": "5432",
        "database.user": "postgres",
        "database.password": "postgres",
        "database.dbname": "orderdb",
        "topic.prefix": "outbox",
        "table.include.list": "public.outbox",
        "plugin.name": "pgoutput",
        "slot.name": "outbox_cdc_slot",
        "publication.name": "outbox_cdc_pub",
        "publication.autocreate.mode": "filtered",
        
        "tombstones.on.delete": false,
        "snapshot.mode": "never",
        
        "transforms": "outbox",
        "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
        "transforms.outbox.table.field.event.id": "id",
        "transforms.outbox.table.field.event.key": "aggregate_id",
        "transforms.outbox.table.field.event.type": "event_type",
        "transforms.outbox.table.field.event.payload": "payload",
        "transforms.outbox.route.by.field": "aggregate_type",
        "transforms.outbox.route.topic.replacement": "${routedByValue}.events",
        
        "key.converter": "org.apache.kafka.connect.storage.StringConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter.schemas.enable": false
    }
}'

# Run the Go outbox writer
go run outbox-writer.go

# Consume from the routed topic
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic Order.events \
  --from-beginning

# Expected: OrderCreated events routed to "Order.events" topic
# Key: aggregate_id (order ID)
# Value: outbox payload (OrderCreatedEvent JSON)
```

### 8.7 Monitoring Connect Cluster

```bash
# List all connectors
curl http://localhost:8083/connectors | python3 -m json.tool

# Check connector status
curl http://localhost:8083/connectors/orders-source/status | python3 -m json.tool

# Pause connector
curl -X PUT http://localhost:8083/connectors/orders-source/pause

# Resume connector
curl -X PUT http://localhost:8083/connectors/orders-source/resume

# Restart failed task
curl -X POST http://localhost:8083/connectors/orders-source/tasks/0/restart

# Delete connector
# curl -X DELETE http://localhost:8083/connectors/orders-source

# Check topics created
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server kafka:29092 --list

# Cleanup outbox rows cũ phải là application/ops job riêng.
# Debezium đọc WAL; nó KHÔNG xóa row trong outbox table.
# Chỉ xóa sau khi connector đã streaming ổn và record đủ tuổi để tránh phá snapshot/replay vận hành.
docker exec -it $(docker ps -q -f name=postgres) \
  psql -U postgres -d orderdb -c \
  "DELETE FROM outbox WHERE created_at < NOW() - INTERVAL '7 days';"

# Check DLQ for errors
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic dlq-orders-es-sink \
  --from-beginning \
  --max-messages 10
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Giải thích sự khác nhau giữa CDC và application-level events. Khi nào bạn chọn CDC, khi nào chọn application events? Có thể dùng cả hai không?**
   - Hint: nghĩ về legacy systems vs greenfield, data sync vs business events.

2. **Debezium connector crash và restart sau 1 giờ. Trong 1 giờ đó, database có 10,000 changes. Debezium có miss changes không? Giải thích cơ chế.**
   - Hint: WAL retention, replication slot, LSN tracking.

3. **Outbox table sẽ ngày càng lớn nếu không cleanup. Bạn sẽ cleanup như thế nào mà không ảnh hưởng Debezium?**
   - Hint: Debezium đọc từ WAL, không phải từ table. Nhưng snapshot mode thì sao?

4. **Tại sao Debezium + Outbox Pattern tốt hơn "service tự publish event sau khi commit DB"?**
   - Hint: nghĩ về crash window giữa DB commit và Kafka publish.

5. **tasks.max = 5 cho một Debezium PostgreSQL connector capture 1 table. Có vấn đề gì?**
   - Hint: Debezium PostgreSQL dùng 1 replication slot per connector. Parallelism hoạt động thế nào?

6. **Bạn cần mask PII fields (email, phone) trong CDC events trước khi đưa vào Kafka. Bạn sẽ dùng approach nào?**
   - Hint: SMT MaskField vs custom SMT vs application-level filter.

7. **Elasticsearch sink connector bị lỗi với 1 message format sai. Bạn muốn skip message đó và tiếp tục xử lý. Cấu hình như thế nào?**
   - Hint: errors.tolerance, dead letter queue.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Connect Documentation](https://kafka.apache.org/documentation/#connect)
- [Debezium Documentation](https://debezium.io/documentation/)
- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/connectors/postgresql.html)
- [Confluent Elasticsearch Sink Connector](https://docs.confluent.io/kafka-connectors/elasticsearch/current/overview.html)

### Blog Posts & Articles
- [Debezium — Outbox Event Router](https://debezium.io/documentation/reference/transformations/outbox-event-router.html)
- [Confluent — Kafka Connect Deep Dive](https://www.confluent.io/blog/kafka-connect-deep-dive-error-handling-dead-letter-queues/)
- [Gunnar Morling — Reliable Microservices Data Exchange With the Outbox Pattern](https://debezium.io/blog/2019/02/19/reliable-microservices-data-exchange-with-the-outbox-pattern/)
- [Chris Richardson — Pattern: Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html)

### Videos & Talks
- [Kafka Summit — Change Data Capture with Debezium](https://www.confluent.io/events/kafka-summit/)
- [Gunnar Morling — Practical Change Data Streaming Use Cases with Apache Kafka & Debezium](https://www.youtube.com/results?search_query=debezium+gunnar+morling)
