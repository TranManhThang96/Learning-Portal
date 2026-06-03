# Day 16: Schema Management — Schema Registry, Avro vs Protobuf vs JSON Schema, Schema Evolution

> Companion split: xem `document.md` để đào sâu schema governance và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** tại sao schema management là bắt buộc trong event-driven architecture — không có schema = ticking time bomb
2. **Nắm vững** Confluent Schema Registry — cách hoạt động, subject naming strategies, compatibility modes
3. **So sánh được** Avro vs Protobuf vs JSON Schema — trade-off thực tế về performance, tooling, developer experience
4. **Thực hành** schema evolution — backward, forward, full compatibility với real scenarios
5. **Áp dụng** contract testing giữa producer và consumer services

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-15 (Kafka fundamentals, producer/consumer internals, transactions)
- Hiểu serialization/deserialization cơ bản (JSON, binary formats)
- Biết khái niệm API versioning từ REST/gRPC development
- Docker Compose Kafka cluster đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Tại sao cần schema management — pain khi không có
- Schema Registry architecture — REST API, subject, version, compatibility
- Avro fundamentals — schema definition, serialization, GenericRecord vs SpecificRecord
- Schema evolution — backward, forward, full compatibility
- Hands-on: setup Schema Registry, produce/consume với Avro, test schema evolution

### 🟡 Should Learn (nếu còn thời gian)
- Protobuf với Schema Registry — khi nào chọn Protobuf thay Avro
- JSON Schema với Schema Registry
- Subject naming strategies (TopicNameStrategy, RecordNameStrategy, TopicRecordNameStrategy)
- Contract testing patterns giữa services

### 🟢 Optional Deep Dive
- Schema Registry HA deployment
- Custom serializer/deserializer
- Schema references (nested schemas, shared types)
- GitOps cho schema management (schema-as-code)

---

## 4. Lý thuyết (Theory)

### 4.1 Tại sao cần Schema Management?

#### WHY — Vấn đề "Schema Drift"

Kafka topic chỉ lưu bytes. Producer serialize data thành bytes, consumer deserialize bytes thành data. **Không có gì ngăn producer thay đổi format mà không nói cho consumer biết.**

```
VẤN ĐỀ THỰC TẾ:

Tuần 1: OrderService produce:
  {"orderId": "123", "amount": 100, "currency": "USD"}

Tuần 3: Dev mới rename field (breaking change):
  {"order_id": "123", "total_amount": 100, "currency": "USD"}

Tuần 4: PaymentService consumer CRASH!
  → NullPointerException: field "orderId" not found
  → 50,000 messages stuck trong topic
  → Incident P1 lúc 3 giờ sáng

Timeline sự cố:
  3:00 AM  — PagerDuty alert: consumer lag tăng vọt
  3:15 AM  — Oncall tìm ra consumer crash loop
  3:30 AM  — Git blame: field rename 2 ngày trước, KHÔNG ai review
  4:00 AM  — Hotfix: read cả 2 format → deploy
  5:00 AM  — Backlog 50k messages drain xong
  
  Tổng thiệt hại: 2 giờ downtime, $$$, trust giảm
```

#### WHAT — Schema Registry là gì?

Schema Registry là **centralized service** lưu trữ và quản lý schemas, đóng vai trò **contract enforcer** giữa producers và consumers.

```
KHÔNG CÓ Schema Registry:
  ┌──────────┐     raw bytes      ┌──────────┐
  │ Producer │───────────────────►│ Consumer │
  │          │  "trust me bro"    │          │
  └──────────┘                    └──────────┘
  → Producer đổi schema bất kỳ lúc nào
  → Consumer crash runtime
  → Phát hiện lỗi ở PRODUCTION


CÓ Schema Registry:
  ┌──────────┐                         ┌──────────┐
  │ Producer │                         │ Consumer │
  │          │                         │          │
  └────┬─────┘                         └────┬─────┘
       │ 1. Register/validate schema        │ 4. Fetch schema by ID
       │                                    │
       ▼                                    ▼
  ┌─────────────────────────────────────────────┐
  │            Schema Registry                   │
  │  ┌─────────────────────────────────────┐    │
  │  │ Subject: orders-value               │    │
  │  │ v1: {orderId, amount, currency}     │    │
  │  │ v2: {orderId, amount, currency,     │    │
  │  │      discount} ← backward compat   │    │
  │  └─────────────────────────────────────┘    │
  └─────────────────────────────────────────────┘
       │                                    │
       │ 2. Schema ID embedded in message   │
       ▼                                    │
  ┌──────────────────────────────────┐      │
  │         Kafka Broker             │──────┘
  │  [magic byte][schema_id][data]   │  3. Consumer reads message
  └──────────────────────────────────┘
  
  → Producer KHÔNG THỂ publish breaking change
  → Lỗi phát hiện ở BUILD TIME, không phải production
```

#### HOW — Wire Format

Khi dùng Schema Registry, mỗi Kafka message có format đặc biệt:

```
Kafka Message Value (wire format):

  Byte 0        Byte 1-4           Byte 5+
  ┌──────┐  ┌──────────────┐  ┌─────────────────┐
  │ 0x00 │  │  Schema ID   │  │  Avro/Protobuf  │
  │magic │  │  (4 bytes)   │  │  encoded data   │
  │ byte │  │  big-endian  │  │                 │
  └──────┘  └──────────────┘  └─────────────────┘

  Magic byte = 0 → message dùng Schema Registry
  Schema ID   → lookup schema từ Registry để deserialize
  Data        → binary data encoded theo schema

Flow chi tiết:
  Producer:
    1. Serialize object theo schema
    2. Register schema với Registry → nhận schema ID
    3. Prepend [0x00][schema_id] vào data
    4. Send to Kafka

  Consumer:
    1. Read message, extract schema ID từ byte 1-4
    2. Fetch schema từ Registry (cached locally)
    3. Deserialize data dùng schema
    4. Process message
```

### 4.2 Avro — Format mặc định của Kafka ecosystem

#### WHY — Tại sao Avro là lựa chọn phổ biến nhất cho Kafka?

Avro được thiết kế cho **data serialization trong distributed systems**, với 2 đặc điểm quan trọng:

1. **Schema embedded trong serialization**: reader và writer có thể dùng schema khác nhau → schema evolution
2. **Compact binary format**: không lưu field names trong data → message nhỏ hơn JSON 3-10x

#### WHAT — Avro Schema Definition

```json
// Schema cho Order event
{
  "type": "record",
  "name": "OrderCreated",
  "namespace": "com.example.events",
  "doc": "Event phát ra khi order được tạo thành công",
  "fields": [
    {
      "name": "orderId",
      "type": "string",
      "doc": "UUID unique cho mỗi order"
    },
    {
      "name": "userId",
      "type": "string"
    },
    {
      "name": "amount",
      "type": {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": 10,
        "scale": 2
      },
      "doc": "Tổng tiền, dùng decimal tránh floating-point errors"
    },
    {
      "name": "currency",
      "type": {
        "type": "enum",
        "name": "Currency",
        "symbols": ["USD", "EUR", "VND", "SGD"]
      }
    },
    {
      "name": "items",
      "type": {
        "type": "array",
        "items": {
          "type": "record",
          "name": "OrderItem",
          "fields": [
            {"name": "productId", "type": "string"},
            {"name": "quantity", "type": "int"},
            {"name": "price", "type": "double"}
          ]
        }
      }
    },
    {
      "name": "createdAt",
      "type": {
        "type": "long",
        "logicalType": "timestamp-millis"
      }
    },
    {
      "name": "metadata",
      "type": ["null", {"type": "map", "values": "string"}],
      "default": null,
      "doc": "Optional metadata — correlationId, traceId, etc."
    }
  ]
}
```

#### HOW — Avro Serialization Internals

```
JSON (human-readable, ~200 bytes):
{
  "orderId": "abc-123",
  "userId": "user-456",
  "amount": 99.99,
  "currency": "USD",
  "items": [...],
  "createdAt": 1704067200000
}

Avro Binary (compact, ~60 bytes):
  ┌─────────────────────────────────────────┐
  │ 0E 61 62 63 2D 31 32 33  │ orderId     │ ← length-prefixed string
  │ 10 75 73 65 72 2D 34 35  │ userId      │ ← no field name stored!
  │ 36                        │             │
  │ [decimal bytes]           │ amount      │
  │ 00                        │ currency=USD│ ← enum as index (0)
  │ [array data]              │ items       │
  │ [8 bytes long]            │ createdAt   │
  │ 00                        │ metadata    │ ← null union (index 0)
  └─────────────────────────────────────────┘

  Tại sao nhỏ hơn?
  - Không lưu field names (reader dùng schema để biết thứ tự)
  - Enum lưu bằng index (0, 1, 2) thay vì string
  - Integer dùng variable-length encoding (zigzag)
  - Không có delimiters (brackets, colons, commas)
```

### 4.3 Schema Evolution — Thay đổi schema an toàn

#### WHY — Tại sao schema evolution phức tạp?

Trong production, bạn KHÔNG THỂ:
- Stop tất cả consumers, deploy schema mới, rồi start lại → downtime
- Force tất cả teams upgrade cùng lúc → coordination nightmare

Bạn CẦN: producer và consumer ở nhiều version chạy song song, nhưng deployment order phải khớp với compatibility mode. Đây là điểm hay bị nhầm: **BACKWARD không có nghĩa là consumer cũ đọc được data mới**.

```
REAL-WORLD SCENARIO:

  Timeline deploy an toàn với BACKWARD compatibility:
  
  T0:  Producer v1 (schema v1) ──► Consumer v1 (schema v1)  ✅
  T1:  Deploy Consumer v2 (schema v2)
  T2:  Producer v1 (schema v1) ──► Consumer v2 (schema v2)  ← PHẢI WORK!
  T3:  Deploy Producer v2 (schema v2)
  T4:  Producer v2 (schema v2) ──► Consumer v2 (schema v2)  ✅

  Backward compatibility: reader schema mới đọc được writer schema cũ
  Forward compatibility:  reader schema cũ đọc được writer schema mới
  Full compatibility:     Cả hai hướng đều work

  Nếu bắt buộc deploy Producer v2 trước Consumer v2:
  - BACKWARD-only không đủ.
  - Cần FORWARD hoặc FULL compatibility, và change phải cho phép consumer cũ bỏ qua field mới.
```

#### WHAT — Compatibility Types

```
BACKWARD (default trong Confluent Schema Registry):
  "Consumer mới đọc được data cũ"
  
  Cho phép:
    ✅ Thêm field MỚI CÓ default value
    ✅ Xóa field KHÔNG CÓ default value
  
  Không cho phép:
    ❌ Thêm field mới KHÔNG CÓ default
    ❌ Xóa field CÓ default
    ❌ Rename field
    ❌ Thay đổi type
  
  Use case: Consumer upgrade trước, producer upgrade sau
  
  Ví dụ:
    Schema v1: {orderId, amount, currency}
    Schema v2: {orderId, amount, currency, discount (default=0)} ← OK
    Schema v2: {orderId, amount, currency, discount}             ← FAIL!


FORWARD:
  "Consumer cũ đọc được data mới"
  
  Cho phép:
    ✅ Thêm field mới KHÔNG CÓ default (consumer cũ ignore)
    ✅ Xóa field CÓ default value
  
  Không cho phép:
    ❌ Xóa field không có default
    ❌ Rename/change type
  
  Use case: Producer upgrade trước, consumer upgrade sau


FULL:
  "Cả consumer mới và cũ đều đọc được"
  
  Cho phép:
    ✅ Thêm field CÓ default value
    ✅ Xóa field CÓ default value
  
  Không cho phép:
    ❌ Thêm field KHÔNG CÓ default
    ❌ Xóa field KHÔNG CÓ default
    ❌ Rename/change type
  
  Use case: Recommended — an toàn nhất cho production


NONE:
  "Không check gì cả — YOLO"
  ❌ KHÔNG BAO GIỜ dùng trong production


TRANSITIVE variants (BACKWARD_TRANSITIVE, FORWARD_TRANSITIVE, FULL_TRANSITIVE):
  Check compatibility với TẤT CẢ versions trước đó, không chỉ version gần nhất.
  
  Non-transitive: v3 check với v2 ✓  (v1 không check)
  Transitive:     v3 check với v2 ✓ VÀ v1 ✓
  
  → Dùng TRANSITIVE khi consumers có thể đang chạy BẤT KỲ version nào
```

#### Decision Matrix cho Compatibility

| Tiêu chí | BACKWARD | FORWARD | FULL | NONE |
|----------|----------|---------|------|------|
| Default | ✅ (Confluent) | | | |
| Safe nhất | | | ✅ | |
| Deploy order | Consumer first | Producer first | Any order | Any |
| Thêm required field | ❌ | ✅ | ❌ | ✅ |
| Xóa field | Có điều kiện | Có điều kiện | Có default | ✅ |
| Production recommendation | Good | OK | **Best** | ❌ Never |

### 4.4 Avro vs Protobuf vs JSON Schema

#### So sánh tổng thể

| Tiêu chí | Avro | Protobuf | JSON Schema |
|----------|------|----------|-------------|
| **Origin** | Apache (Hadoop) | Google | IETF |
| **Encoding** | Binary | Binary | Text (JSON) |
| **Schema in data** | Không (separate) | Không (separate) | Trong data |
| **Message size** | Nhỏ (~60B) | Nhỏ nhất (~50B) | Lớn (~200B) |
| **Serialization speed** | Nhanh | Nhanh nhất | Chậm nhất |
| **Schema evolution** | Excellent | Excellent | Limited |
| **Kafka ecosystem** | **Native support** | Good support | Basic support |
| **Code generation** | Optional | Required | Optional |
| **Human readable** | Schema: Yes, Data: No | Schema: Yes, Data: No | Both: Yes |
| **Dynamic typing** | GenericRecord ✅ | Không | ✅ |
| **Learning curve** | Trung bình | Thấp | Thấp |
| **gRPC integration** | Không | **Native** | Không |

#### Khi nào dùng gì?

```
CHỌN AVRO khi:
  ✅ Kafka-first architecture
  ✅ Cần schema evolution mạnh
  ✅ Team data engineering/analytics (Spark, Flink, Hive đều support native)
  ✅ Cần dynamic schema (GenericRecord — không cần code gen)
  ✅ Confluent ecosystem (Schema Registry, Connect, ksqlDB)

CHỌN PROTOBUF khi:
  ✅ Đã dùng gRPC — reuse .proto files cho cả API và events
  ✅ Cần performance tối đa (nhỏ nhất, nhanh nhất)
  ✅ Polyglot environment (code gen cho 10+ languages)
  ✅ Team đã quen protobuf, không muốn học thêm Avro
  ✅ Nested messages phức tạp (protobuf syntax rõ ràng hơn)

CHỌN JSON SCHEMA khi:
  ✅ Prototype/MVP — cần debug dễ (đọc message bằng mắt)
  ✅ Team không quen binary formats
  ✅ External integration (webhook, REST API consumers)
  ✅ Schema validation cho existing JSON pipelines
  ❌ KHÔNG khuyến khích cho high-throughput production
```

### 4.5 Subject Naming Strategies

#### WHY — Tại sao naming quan trọng?

Subject trong Schema Registry quyết định **phạm vi compatibility check**. Naming sai → check sai phạm vi → breaking change lọt qua.

```
TOPICNAMESTRATEGY (default):
  Subject = "{topic}-key" và "{topic}-value"
  
  orders → "orders-key", "orders-value"
  
  ✅ Đơn giản, phù hợp 1 topic = 1 event type
  ❌ Không phù hợp nếu 1 topic chứa nhiều event types
  
  Ví dụ:
    Topic "orders" chỉ có OrderCreated events
    → Subject "orders-value" track schema evolution cho OrderCreated


RECORDNAMESTRATEGY:
  Subject = "{fully.qualified.record.name}"
  
  com.example.events.OrderCreated → "com.example.events.OrderCreated"
  
  ✅ 1 topic chứa nhiều event types (OrderCreated, OrderUpdated, OrderCancelled)
  ✅ Schema evolution per event type
  ❌ Phức tạp hơn, cần configure serializer


TOPICRECORDNAMESTRATEGY:
  Subject = "{topic}-{fully.qualified.record.name}"
  
  orders + OrderCreated → "orders-com.example.events.OrderCreated"
  
  ✅ Cùng event type trên nhiều topics có schema khác nhau
  ✅ Granular nhất
  ❌ Nhiều subjects → quản lý phức tạp
```

### 4.6 Contract Testing giữa Services

#### WHY — Schema Registry chưa đủ

Schema Registry check compatibility ở **schema level**, nhưng không check:
- Business logic changes (field "amount" đổi từ cents sang dollars)
- Semantic meaning (field "status" thêm giá trị mới mà consumer không handle)
- Required fields trong application logic (không phải schema level)

```
CONTRACT TESTING FLOW:

  ┌──────────────┐                    ┌──────────────┐
  │ OrderService │                    │PaymentService│
  │  (Producer)  │                    │  (Consumer)  │
  └──────┬───────┘                    └──────┬───────┘
         │                                    │
         │ 1. Define schema                   │ 2. Define expected format
         │    (producer contract)             │    (consumer contract)
         ▼                                    ▼
  ┌─────────────────────────────────────────────────┐
  │              CI/CD Pipeline                      │
  │                                                  │
  │  3. Producer tests:                              │
  │     - Serialize sample events                    │
  │     - Validate against producer schema           │
  │     - Register schema → check compatibility      │
  │                                                  │
  │  4. Consumer tests:                              │
  │     - Deserialize sample events                  │
  │     - Validate consumer can handle all fields    │
  │     - Test with MISSING optional fields          │
  │     - Test with EXTRA unknown fields             │
  │                                                  │
  │  5. Cross-service contract test:                 │
  │     - Producer sample → Consumer deserialization │
  │     - Verify no breaking changes                 │
  └─────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### Schema Registry: Centralized vs Decentralized

| Tiêu chí | Centralized (Schema Registry) | Decentralized (schema in code) |
|----------|-------------------------------|-------------------------------|
| Consistency | Guaranteed | Hope & pray |
| Breaking change detection | Automatic, build-time | Manual review only |
| Deployment coupling | Schema Registry must be available | No dependency |
| Developer friction | Phải register schema trước | Tự do thay đổi |
| Multi-language support | REST API cho mọi language | Per-language implementation |
| **Recommendation** | **Production: luôn dùng** | Chỉ cho prototype/hackathon |

### Avro vs Protobuf — Deep Comparison

| Tiêu chí | Avro | Protobuf |
|----------|------|----------|
| Kafka integration | **Native** (Confluent ecosystem) | Good (cần thêm config) |
| Schema in file | JSON (.avsc) | DSL (.proto) |
| Default values | Trong schema definition | Field defaults **luôn có** (zero value) |
| Union types | `["null", "string"]` | `oneof` |
| Code generation | Optional (GenericRecord) | **Required** |
| Schema readability | JSON → verbose | DSL → **concise, clear** |
| Backward compat rules | Schema Registry enforced | Proto3: tất cả fields optional by default |
| Tooling maturity | Kafka-focused | **Universal** (gRPC, mobile, embedded) |
| File size overhead | 3-10x smaller than JSON | **5-15x smaller** than JSON |
| Benchmark (ser/deser) | ~15μs / ~20μs | **~8μs / ~10μs** |

### Schema Evolution Strategy

| Scenario | Approach | Compatibility Mode |
|----------|----------|-------------------|
| Thêm optional analytics field | Add field with default | BACKWARD ✅ |
| Deprecate field dần | Mark deprecated, keep default, remove after all consumers migrate | FULL ✅ |
| Rename field | KHÔNG rename — thêm field mới, deprecate field cũ | FULL ✅ |
| Change field type (int→long) | Breaking — tạo topic mới hoặc thêm field mới | N/A (avoid) |
| Thêm required business field | Add with default, validate in application logic | BACKWARD ✅ |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. FULL_TRANSITIVE compatibility cho production
   → An toàn nhất, bất kỳ consumer version nào cũng đọc được
   → Set ở global level, override per-subject nếu cần

2. Schema-first development
   → Define schema TRƯỚC khi viết code
   → Review schema changes như review API changes (PR review)
   → Schema file trong git repo, CI/CD validate compatibility

3. Naming convention cho subjects
   → Format: {domain}.{entity}.{event}
   → Ví dụ: order.order.created, payment.payment.completed
   → KHÔNG dùng action verbs mơ hồ: "order.process", "user.update"

4. Default values cho MỌI field optional
   → Avro: {"name": "discount", "type": ["null", "double"], "default": null}
   → Luôn dùng union với null cho fields có thể không có

5. Logical types cho semantic meaning
   → timestamp-millis thay vì long
   → decimal thay vì double cho tiền tệ
   → uuid thay vì string (Avro 1.11.1+)

6. Envelope pattern cho events
   → Tách metadata (id, timestamp, source, correlationId) và payload
   → Consistent across tất cả events
```

### Common Pitfalls

```
❌ PITFALL 1: Rename field
   Sai:  v1: "orderId" → v2: "order_id"
   Đúng: v2: thêm "order_id" với default, deprecate "orderId"
   Tại sao: Rename = delete + add = breaking change

❌ PITFALL 2: Change type
   Sai:  "amount": "int" → "amount": "long"
   Đúng: Thêm "amountLong": "long", deprecate "amount"
   Tại sao: Binary encoding khác nhau, consumer crash

❌ PITFALL 3: Required field không có default
   Sai:  thêm {"name": "region", "type": "string"} (v2)
   Đúng: {"name": "region", "type": ["null", "string"], "default": null}
   Tại sao: Consumer v1 không biết field này, backward compat fail

❌ PITFALL 4: NONE compatibility mode
   Sai:  "Để NONE cho nhanh, sau set lại"
   Đúng: FULL_TRANSITIVE từ đầu
   Tại sao: Breaking changes đã register → không rollback được

❌ PITFALL 5: Không cache schema locally
   Sai:  Fetch schema từ Registry cho mỗi message
   Đúng: Client library tự cache (default behavior)
   Tại sao: 100k msg/s × HTTP call = Registry overload

❌ PITFALL 6: Shared schema cho nhiều event types
   Sai:  1 "OrderEvent" schema với field "eventType" + optional fields
   Đúng: Separate schemas: OrderCreated, OrderUpdated, OrderCancelled
   Tại sao: Shared schema evolve khó, optional field explosion
```

---

## 7. Performance Considerations

### Serialization/Deserialization Benchmark

```
Hardware: Intel i7, 16GB RAM, JVM 17
Message: Order event (10 fields, nested array)
Iterations: 1,000,000

| Format      | Ser Time  | Deser Time | Size (bytes) | Total/msg |
|-------------|-----------|------------|--------------|-----------|
| JSON        | ~45μs     | ~55μs      | ~250         | ~100μs    |
| JSON+gzip   | ~60μs     | ~70μs      | ~120         | ~130μs    |
| Avro        | ~15μs     | ~20μs      | ~80          | ~35μs     |
| Protobuf    | ~8μs      | ~10μs      | ~65          | ~18μs     |
| Avro+Snappy | ~18μs     | ~23μs      | ~70          | ~41μs     |

Nhận xét:
- Protobuf nhanh nhất (2x Avro, 5x JSON)
- Avro compact hơn JSON 3x, chậm hơn Protobuf chút
- JSON gzip: size giảm nhưng CPU tăng — trade-off
- Với Kafka throughput, sự khác biệt đáng kể ở scale lớn:
  100k msg/s × 35μs (Avro) = 3.5s CPU/s
  100k msg/s × 100μs (JSON) = 10s CPU/s → cần 3x cores
```

### Schema Registry Performance

```
Schema Registry metrics cần monitor:
  - schema_registry_registered_count    — tổng số schemas
  - schema_registry_api_latency         — REST API latency
  - schema_registry_cache_hit_ratio     — cache effectiveness

Bottlenecks thường gặp:
  1. Cold start: consumer lần đầu fetch schema → ~10ms
     Sau đó cache → ~0.01ms (có thể bỏ qua)
  
  2. Too many subjects: >10,000 subjects → Registry slow
     Giải pháp: archive old subjects, cleanup unused
  
  3. Schema Registry single point of failure:
     Giải pháp: multi-instance deployment, schemas stored in _schemas topic
     → Kafka cluster phải available thì Registry mới work

Performance tuning:
  - Client-side caching (default enabled): ~100KB RAM per schema ID
  - max.schemas.per.subject: limit evolution history (default 1000)
  - Schema validation: async nếu được, đừng block produce path
```

---

## 8. Hands-on Lab

### 8.1 Setup — Docker Compose với Schema Registry

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
      SCHEMA_REGISTRY_LISTENERS: http://0.0.0.0:8081
      # FULL_TRANSITIVE — production-grade compatibility
      SCHEMA_REGISTRY_SCHEMA_COMPATIBILITY_LEVEL: FULL_TRANSITIVE
```

```bash
# Start services
docker compose up -d

# Verify Schema Registry
curl http://localhost:8081/subjects
# Kết quả: [] (chưa có schema nào)

# Check config
curl http://localhost:8081/config
# {"compatibilityLevel":"FULL_TRANSITIVE"}
```

### 8.2 Schema Registry REST API — CRUD Operations

```bash
# 1. Register schema v1 cho subject "orders-value"
curl -X POST http://localhost:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}}]}"
  }'
# Kết quả: {"id":1}  ← Schema ID = 1

# 2. Lấy schema by ID
curl http://localhost:8081/schemas/ids/1

# 3. Lấy latest version của subject
curl http://localhost:8081/subjects/orders-value/versions/latest

# 4. List tất cả versions
curl http://localhost:8081/subjects/orders-value/versions
# [1]

# 5. Test compatibility TRƯỚC khi register
# Thử thêm field KHÔNG CÓ default (breaking change)
curl -X POST http://localhost:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}},{\"name\":\"region\",\"type\":\"string\"}]}"
  }'
# Kết quả: {"is_compatible":false}  ← BLOCKED! region không có default

# 6. Thêm field CÓ default (compatible change)
curl -X POST http://localhost:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}},{\"name\":\"discount\",\"type\":[\"null\",\"double\"],\"default\":null}]}"
  }'
# Kết quả: {"id":2}  ← Schema v2 registered!
```

### 8.3 Go Producer với Avro + Schema Registry

```bash
# Tạo project
mkdir -p kafka-schema-lab && cd kafka-schema-lab
go mod init kafka-schema-lab
go get github.com/confluentinc/confluent-kafka-go/v2/kafka
go get github.com/confluentinc/confluent-kafka-go/v2/schemaregistry
go get github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/avrov2
go get github.com/google/uuid
```

```go
// producer.go
package main

import (
	"fmt"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/avrov2"
	"github.com/google/uuid"
)

// OrderCreated — struct phải match schema "orders-value" đã register ở bước 8.2.
// Field tag dùng lowerCamelCase để khớp Avro field names; thêm field mới cần default/null trong schema.
type OrderCreated struct {
	OrderId   string   `avro:"orderId" json:"orderId"`
	UserId    string   `avro:"userId" json:"userId"`
	Amount    float64  `avro:"amount" json:"amount"`
	Currency  string   `avro:"currency" json:"currency"`
	CreatedAt int64    `avro:"createdAt" json:"createdAt"`
	Discount  *float64 `avro:"discount" json:"discount"`
}

func main() {
	topic := "orders"

	// Schema Registry client
	srClient, err := schemaregistry.NewClient(
		schemaregistry.NewConfig("http://localhost:8081"),
	)
	if err != nil {
		panic(fmt.Sprintf("Schema Registry connect failed: %v", err))
	}

	// Avro serializer — dùng schema đã register trong bước 8.2 thay vì tự suy diễn schema mới.
	// Cách này tránh drift giữa Go struct tags và contract trong Schema Registry.
	serConf := avrov2.NewSerializerConfig()
	serConf.AutoRegisterSchemas = false
	serConf.UseLatestVersion = true
	ser, err := avrov2.NewSerializer(
		srClient,
		serde.ValueSerde,
		serConf,
	)
	if err != nil {
		panic(fmt.Sprintf("Serializer create failed: %v", err))
	}
	ser.RegisterType("com.example.events.OrderCreated", OrderCreated{})

	// Kafka producer
	producer, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": "localhost:9092",
		"acks":              "all",
		"enable.idempotence": true,
	})
	if err != nil {
		panic(fmt.Sprintf("Producer create failed: %v", err))
	}
	defer producer.Close()

	// Delivery report handler
	go func() {
		for e := range producer.Events() {
			switch ev := e.(type) {
			case *kafka.Message:
				if ev.TopicPartition.Error != nil {
					fmt.Printf("FAILED delivery to %v: %v\n",
						ev.TopicPartition, ev.TopicPartition.Error)
				} else {
					fmt.Printf("Delivered to %v [partition %d] @ offset %v\n",
						*ev.TopicPartition.Topic,
						ev.TopicPartition.Partition,
						ev.TopicPartition.Offset)
				}
			}
		}
	}()

	// Produce 5 order events
	for i := 0; i < 5; i++ {
		discount := float64(i) * 5.0
		order := OrderCreated{
			OrderId:   uuid.New().String(),
			UserId:    fmt.Sprintf("user-%03d", i),
			Amount:    99.99 + float64(i)*10,
			Currency:  "USD",
			CreatedAt: time.Now().UnixMilli(),
			Discount:  &discount,
		}

		// Serialize với Avro + Schema Registry
		payload, err := ser.Serialize(topic, &order)
		if err != nil {
			fmt.Printf("Serialize failed: %v\n", err)
			continue
		}

		// Message header: correlationId cho tracing
		correlationId := uuid.New().String()
		err = producer.Produce(&kafka.Message{
			TopicPartition: kafka.TopicPartition{
				Topic:     &topic,
				Partition: kafka.PartitionAny,
			},
			Key:   []byte(order.OrderId),
			Value: payload,
			Headers: []kafka.Header{
				{Key: "correlationId", Value: []byte(correlationId)},
				{Key: "eventType", Value: []byte("OrderCreated")},
				{Key: "schemaVersion", Value: []byte("2")},
			},
		}, nil)
		if err != nil {
			fmt.Printf("Produce failed: %v\n", err)
		}

		fmt.Printf("Produced order %s (correlationId: %s)\n",
			order.OrderId, correlationId)
	}

	// Flush
	remaining := producer.Flush(10000)
	fmt.Printf("Flush completed. %d messages remaining.\n", remaining)
}
```

### 8.4 Go Consumer với Avro Deserialization

```go
// consumer.go
package main

import (
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde"
	"github.com/confluentinc/confluent-kafka-go/v2/schemaregistry/serde/avrov2"
)

type OrderCreated struct {
	OrderId   string   `avro:"orderId" json:"orderId"`
	UserId    string   `avro:"userId" json:"userId"`
	Amount    float64  `avro:"amount" json:"amount"`
	Currency  string   `avro:"currency" json:"currency"`
	CreatedAt int64    `avro:"createdAt" json:"createdAt"`
	Discount  *float64 `avro:"discount" json:"discount"`
}

func main() {
	// Schema Registry client
	srClient, err := schemaregistry.NewClient(
		schemaregistry.NewConfig("http://localhost:8081"),
	)
	if err != nil {
		panic(fmt.Sprintf("Schema Registry connect failed: %v", err))
	}

	// Avro deserializer
	deser, err := avrov2.NewDeserializer(
		srClient,
		serde.ValueSerde,
		avrov2.NewDeserializerConfig(),
	)
	if err != nil {
		panic(fmt.Sprintf("Deserializer create failed: %v", err))
	}

	// Register type mapping (Avro full name → Go struct).
	// Đây là Avro serde, không phải protobuf registry.
	deser.RegisterType("com.example.events.OrderCreated", OrderCreated{})

	// Kafka consumer
	consumer, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": "localhost:9092",
		"group.id":          "order-processor",
		"auto.offset.reset": "earliest",
		"enable.auto.commit": false,
	})
	if err != nil {
		panic(fmt.Sprintf("Consumer create failed: %v", err))
	}
	defer consumer.Close()

	consumer.SubscribeTopics([]string{"orders"}, nil)

	// Graceful shutdown
	sigchan := make(chan os.Signal, 1)
	signal.Notify(sigchan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Println("Consumer started. Waiting for messages...")

	run := true
	for run {
		select {
		case <-sigchan:
			fmt.Println("Shutting down...")
			run = false
		default:
			msg, err := consumer.ReadMessage(-1)
			if err != nil {
				fmt.Printf("Consumer error: %v\n", err)
				continue
			}

			// Extract correlation ID from headers
			var correlationId string
			for _, h := range msg.Headers {
				if h.Key == "correlationId" {
					correlationId = string(h.Value)
					break
				}
			}

			// Deserialize Avro message
			order := OrderCreated{}
			err = deser.DeserializeInto(*msg.TopicPartition.Topic, msg.Value, &order)
			if err != nil {
				fmt.Printf("[%s] Deserialize FAILED: %v\n", correlationId, err)
				continue
			}

			// Process order
			discountStr := "none"
			if order.Discount != nil {
				discountStr = fmt.Sprintf("%.2f", *order.Discount)
			}
			fmt.Printf("[%s] Order: %s | User: %s | Amount: %.2f %s | Discount: %s\n",
				correlationId, order.OrderId, order.UserId,
				order.Amount, order.Currency, discountStr)

			// Manual commit after successful processing
			_, err = consumer.CommitMessage(msg)
			if err != nil {
				fmt.Printf("[%s] Commit failed: %v\n", correlationId, err)
			}
		}
	}
}
```

### 8.5 Schema Evolution Lab — Backward Compatible Change

```bash
# Scenario: thêm field "region" vào OrderCreated v3

# Bước 1: Test compatibility TRƯỚC
curl -X POST http://localhost:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}},{\"name\":\"discount\",\"type\":[\"null\",\"double\"],\"default\":null},{\"name\":\"region\",\"type\":[\"null\",\"string\"],\"default\":null}]}"
  }'
# {"is_compatible":true} ← OK vì region có default null

# Bước 2: Register new version
curl -X POST http://localhost:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}},{\"name\":\"discount\",\"type\":[\"null\",\"double\"],\"default\":null},{\"name\":\"region\",\"type\":[\"null\",\"string\"],\"default\":null}]}"
  }'

# Bước 3: Verify versions
curl http://localhost:8081/subjects/orders-value/versions
# [1, 2, 3]

# Bước 4: Test BREAKING change (should fail)
curl -X POST http://localhost:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"order_id\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"}]}"
  }'
# {"is_compatible":false} ← BLOCKED! orderId renamed to order_id
```

### 8.6 Contract Test — compatibility + sample deserialize

Contract test tối thiểu trong CI nên làm 2 việc khác nhau:

- Schema compatibility: version mới có được Schema Registry accept không.
- Consumer contract: consumer hiện tại có deserialize và hiểu sample event producer mới phát ra không.

```bash
# 1. Producer PR: kiểm tra schema mới trước khi merge
curl -s -X POST http://localhost:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{
    "schema": "{\"type\":\"record\",\"name\":\"OrderCreated\",\"namespace\":\"com.example.events\",\"fields\":[{\"name\":\"orderId\",\"type\":\"string\"},{\"name\":\"userId\",\"type\":\"string\"},{\"name\":\"amount\",\"type\":\"double\"},{\"name\":\"currency\",\"type\":\"string\"},{\"name\":\"createdAt\",\"type\":{\"type\":\"long\",\"logicalType\":\"timestamp-millis\"}},{\"name\":\"discount\",\"type\":[\"null\",\"double\"],\"default\":null},{\"name\":\"region\",\"type\":[\"null\",\"string\"],\"default\":null}]}"
  }'
# CI pass khi response có: "is_compatible":true

# 2. Cross-service smoke: produce sample bằng producer mới
go run producer.go

# 3. Consumer hiện tại phải deserialize được sample và commit offset
go run consumer.go
# Expected log:
# [correlation-id] Order: ... | Amount: ... | Discount: ...
```

Nếu đổi semantic mà schema không bắt được, ví dụ `amount` từ dollars sang cents nhưng type vẫn `double`, compatibility vẫn pass. Vì vậy contract test cần assert business expectation trên sample event, không chỉ gọi REST API.

### 8.7 TypeScript Alternative — Producer với kafkajs + Avro

```typescript
// ts-producer.ts
import { Kafka } from 'kafkajs';
import { SchemaRegistry, SchemaType } from '@kafkajs/confluent-schema-registry';
import { v4 as uuidv4 } from 'uuid';

const kafka = new Kafka({
  clientId: 'order-service',
  brokers: ['localhost:9092'],
});

const registry = new SchemaRegistry({
  host: 'http://localhost:8081',
});

// Avro schema definition
const orderSchema = `
{
  "type": "record",
  "name": "OrderCreated",
  "namespace": "com.example.events",
  "fields": [
    {"name": "orderId", "type": "string"},
    {"name": "userId", "type": "string"},
    {"name": "amount", "type": "double"},
    {"name": "currency", "type": "string"},
    {"name": "createdAt", "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "discount", "type": ["null", "double"], "default": null},
    {"name": "region", "type": ["null", "string"], "default": null}
  ]
}`;

async function main() {
  // Register schema (idempotent — returns existing ID if schema already registered)
  const { id: schemaId } = await registry.register({
    type: SchemaType.AVRO,
    schema: orderSchema,
  }, {
    subject: 'orders-value',
  });
  console.log(`Schema registered with ID: ${schemaId}`);

  const producer = kafka.producer({
    idempotent: true,
  });
  await producer.connect();

  const orders = Array.from({ length: 5 }, (_, i) => ({
    orderId: uuidv4(),
    userId: `user-${String(i).padStart(3, '0')}`,
    amount: 99.99 + i * 10,
    currency: 'USD',
    createdAt: Date.now(),
    discount: i > 0 ? { double: i * 5.0 } : null, // Avro union format
    region: i % 2 === 0 ? { string: 'US-WEST' } : null,
  }));

  for (const order of orders) {
    const correlationId = uuidv4();

    // Encode with Avro schema
    const encodedValue = await registry.encode(schemaId, order);

    await producer.send({
      topic: 'orders',
      messages: [{
        key: order.orderId,
        value: encodedValue,
        headers: {
          correlationId,
          eventType: 'OrderCreated',
        },
      }],
    });

    console.log(`[${correlationId}] Produced order: ${order.orderId}`);
  }

  await producer.disconnect();
  console.log('Producer disconnected.');
}

main().catch(console.error);
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Nếu đang dùng BACKWARD compatibility, bạn deploy consumer v2 trước hay producer v2 trước? Giải thích tại sao thứ tự deploy quan trọng.**
   - Hint: "Backward" nghĩa là consumer mới đọc được data cũ. Vậy consumer upgrade trước có an toàn không?

2. **Team bạn muốn thêm field `paymentMethod` (bắt buộc, không có default) vào OrderCreated event. Với FULL compatibility, bạn sẽ handle thế nào?**
   - Hint: schema level vs application level validation là 2 việc khác nhau.

3. **Bạn có 1 topic "events" chứa OrderCreated, OrderUpdated, và OrderCancelled. TopicNameStrategy có vấn đề gì? Bạn sẽ chọn strategy nào?**
   - Hint: cùng subject → cùng compatibility check → schema cho OrderCreated và OrderCancelled phải compatible?

4. **Protobuf có ưu điểm gì mà Avro không có? Trong trường hợp nào bạn sẽ chọn Protobuf thay vì Avro cho Kafka?**
   - Hint: nghĩ về gRPC, code generation, và cross-platform support.

5. **Schema Registry down thì Kafka producer/consumer có tiếp tục hoạt động được không? Cần làm gì để giảm risk?**
   - Hint: phân biệt giữa schema registration (lần đầu) và schema lookup (cached).

6. **Giải thích tại sao TRANSITIVE variants quan trọng hơn non-transitive trong production environment có nhiều consumer versions?**
   - Hint: consumer team A chạy v1, team B chạy v3, team C chạy v5. Non-transitive chỉ check v5 vs v4.

7. **Contract testing khác gì so với schema compatibility check? Cho ví dụ breaking change mà Schema Registry KHÔNG bắt được.**
   - Hint: "amount" field đổi đơn vị từ cents sang dollars — schema vẫn "double", nhưng semantics thay đổi.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Confluent Schema Registry Documentation](https://docs.confluent.io/platform/current/schema-registry/index.html)
- [Apache Avro Specification](https://avro.apache.org/docs/current/specification/)
- [Protocol Buffers Language Guide](https://protobuf.dev/programming-guides/proto3/)
- [JSON Schema Specification](https://json-schema.org/specification)

### Blog Posts & Articles
- [Confluent — Schema Evolution and Compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
- [Confluent — Why Avro for Kafka Data](https://www.confluent.io/blog/avro-kafka-data/)
- [Martin Kleppmann — Schema evolution in Avro, Protocol Buffers and Thrift](https://martin.kleppmann.com/2012/12/05/schema-evolution-in-avro-protocol-buffers-thrift.html)

### Videos & Talks
- [Kafka Summit — Schema Registry: Past, Present, and Future](https://www.confluent.io/events/kafka-summit/)
- [GOTO Conference — Designing Events-First Microservices](https://www.youtube.com/results?search_query=goto+event+driven+schema+evolution)
