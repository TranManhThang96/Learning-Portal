# Day 18: Kafka Streams Cơ Bản — KStream, KTable, Stateless Operations, Topology

> Companion split: xem `document.md` để đào sâu topology/serde và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** tại sao cần stream processing library và Kafka Streams giải quyết vấn đề gì so với consumer thông thường
2. **Nắm vững** 2 abstraction cốt lõi: KStream (event stream) vs KTable (changelog/materialized view) — khi nào dùng gì
3. **Thực hành** stateless operations: filter, map, flatMap, branch, merge, selectKey; hiểu `groupBy` là boundary sang stateful processing
4. **Hiểu** Topology — cách Kafka Streams xây dựng và thực thi DAG processing
5. **So sánh** Kafka Streams vs Flink vs Spark Streaming — trade-off để chọn đúng tool

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-12 (Kafka fundamentals, producer/consumer internals, consumer groups)
- Đã hoàn thành Day 15 (delivery semantics, exactly-once, transactions)
- Đã hoàn thành Day 16 (Schema Registry, Avro serialization)
- Hiểu functional programming cơ bản (map, filter, reduce)
- Docker Compose Kafka cluster đang chạy

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Stream processing paradigm — tại sao consumer + business logic không đủ
- KStream vs KTable — duality, khi nào dùng gì
- Stateless operations — filter, map, flatMap, branch, merge, selectKey
- Repartition/stateful boundary — `groupByKey()`/`groupBy()` chỉ chuẩn bị cho aggregate/reduce/count ở Day 19
- Topology concept — Sub-topology, source/processor/sink nodes
- Hands-on: xây dựng order processing pipeline với stateless operations

### 🟡 Should Learn (nếu còn thời gian)
- Processor API (low-level) — khi DSL không đủ
- SerDes configuration — custom serializer/deserializer
- Error handling — deserialization errors, production exceptions
- Kafka Streams testing với TopologyTestDriver

### 🟢 Optional Deep Dive
- Internal threading model (StreamThread, StreamTask, StandbyTask)
- Partition assignment trong Kafka Streams
- Interactive Queries cơ bản (preview cho Day 19)
- Kafka Streams vs ksqlDB

---

## 4. Lý thuyết (Theory)

### 4.1 Tại sao cần Stream Processing?

#### WHY — Consumer thông thường không đủ

```
VẤN ĐỀ VỚI "CONSUMER + BUSINESS LOGIC":

  Scenario: Tính tổng doanh thu real-time theo category

  Approach 1: Simple consumer
  ┌──────────┐     ┌────────────────────────┐     ┌──────────┐
  │  Kafka   │────►│    Consumer App         │────►│   DB     │
  │  orders  │     │                        │     │ revenue  │
  └──────────┘     │ 1. Poll messages        │     └──────────┘
                   │ 2. Parse JSON           │
                   │ 3. Group by category    │
                   │ 4. Sum amounts          │
                   │ 5. Write to DB          │
                   │ 6. Commit offset        │
                   └────────────────────────┘
  
  Vấn đề:
  ✗ State management tự viết (in-memory map? DB? Redis?)
  ✗ Fault tolerance cho state (consumer crash → state mất?)
  ✗ Exactly-once tự handle (sum bị double sau restart?)
  ✗ Reprocessing logic (backfill từ đầu topic?)
  ✗ Scaling lo tự coordinate (multiple instances?)
  ✗ Time semantics (event time vs processing time?)
  ✗ Late arriving events?
  ✗ Windowing (tổng theo giờ, ngày)?
  
  → 2000+ dòng boilerplate trước khi viết 1 dòng business logic


KAFKA STREAMS GIẢI QUYẾT:

  ┌──────────┐     ┌────────────────────────┐     ┌──────────┐
  │  Kafka   │────►│   Kafka Streams App     │────►│  Kafka   │
  │  orders  │     │                        │     │ revenue  │
  └──────────┘     │ KStream<Order>          │     └──────────┘
                   │   .filter(paid)         │
                   │   .groupBy(category)    │
                   │   .reduce(sum)          │
                   │   .toStream()           │
                   │   .to("revenue")        │
                   └────────────────────────┘
  
  Kafka Streams cung cấp SẴN:
  ✓ State management (RocksDB local state store)
  ✓ Fault tolerance (state backed by changelog topic)
  ✓ Exactly-once processing trong phạm vi Kafka khi bật EOS đúng config
  ✓ Scaling = thêm instances (consumer group based)
  ✓ Event time processing + late event handling
  ✓ Windowing operations
  ✓ Interactive queries (query state từ ngoài)
  
  → Focus 100% vào BUSINESS LOGIC
```

#### WHAT — Kafka Streams là gì?

```
Kafka Streams = LIBRARY (không phải cluster/framework)

  ┌─────────────────────────────────────────────────────┐
  │                   So sánh kiến trúc                  │
  │                                                     │
  │  Flink/Spark:              Kafka Streams:           │
  │  ┌───────────────┐         ┌───────────────┐        │
  │  │  Your App     │         │  Your App     │        │
  │  │  (submit job) │         │  + Kafka      │        │
  │  └──────┬────────┘         │    Streams    │        │
  │         │                  │  (library)    │        │
  │  ┌──────▼────────┐         └───────────────┘        │
  │  │ Flink Cluster │                                  │
  │  │ (JobManager,  │         Không cần cluster!       │
  │  │  TaskManagers)│         Deploy như normal         │
  │  └───────────────┘         microservice             │
  │                                                     │
  │  Cần: Cluster riêng       Cần: chỉ Kafka cluster    │
  │  Ops: phức tạp            Ops: như mọi service      │
  │  Scale: cluster resize    Scale: thêm instances     │
  │  Deploy: job submission   Deploy: docker/k8s        │
  └─────────────────────────────────────────────────────┘

  KEY INSIGHT:
  Kafka Streams app = một Java/Kotlin application thông thường
  → Package thành JAR/Docker image
  → Deploy lên K8s như mọi microservice khác
  → Scale bằng cách tăng replicas
  → Không cần học thêm ops tooling
```

### 4.2 KStream vs KTable — Stream-Table Duality

#### WHY — Hai cách nhìn cùng 1 dữ liệu

Trong thế giới thực, data có 2 bản chất:
- **Events** (immutable facts): "User A đặt order #123 lúc 10:00"
- **State** (mutable current view): "Order #123 hiện tại status = PAID"

Kafka topic chứa events, nhưng đôi khi bạn cần state.

```
KSTREAM — Event Stream (immutable, append-only):

  Kafka Topic "orders":
  ┌──────┬────────────────────────────────┐
  │Offset│ Event                          │
  ├──────┼────────────────────────────────┤
  │  0   │ {orderId:1, action:CREATE, amt:100} │
  │  1   │ {orderId:2, action:CREATE, amt:200} │
  │  2   │ {orderId:1, action:UPDATE, amt:150} │ ← order 1 updated
  │  3   │ {orderId:1, action:CANCEL}          │ ← order 1 cancelled
  │  4   │ {orderId:3, action:CREATE, amt:300} │
  └──────┴────────────────────────────────┘

  KStream nhìn thấy: TẤT CẢ 5 records (mỗi record là 1 event)
  → Interpret mỗi record là FACT đã xảy ra
  → Dùng cho: logging, audit trail, event processing


KTABLE — Changelog / Materialized View (mutable, latest-per-key):

  Cùng topic, nhưng KTable nhìn thấy "latest state per key":

  ┌─────────┬──────────────────────────────┐
  │  Key    │ Latest Value                 │
  ├─────────┼──────────────────────────────┤
  │ order-1 │ {action:CANCEL}              │ ← chỉ giữ record cuối
  │ order-2 │ {action:CREATE, amt:200}     │
  │ order-3 │ {action:CREATE, amt:300}     │
  └─────────┴──────────────────────────────┘

  KTable nhìn thấy: 3 entries (latest per key)
  → Interpret mỗi record là UPDATE cho key đó
  → Dùng cho: current state, lookup tables, aggregation results


STREAM-TABLE DUALITY:
  
  Stream → Table:  aggregate/reduce stream thành table
                   (accumulate events → current state)
  
  Table → Stream:  mỗi change trong table = 1 event trong stream
                   (CDC chính là table → stream!)

  Analogy:
  ┌────────────────────────────────────────────────┐
  │ Bank account = TABLE (current balance: $500)   │
  │ Bank statement = STREAM (all transactions)     │
  │                                                │
  │ Statement → Balance:  sum(transactions)        │
  │ Balance → Statement:  log every change         │
  └────────────────────────────────────────────────┘
```

#### WHAT — KStream và KTable trong code

```java
// KStream: read topic as event stream
KStream<String, Order> orderStream = builder.stream("orders");
// Mỗi record là 1 event → process tất cả records

// KTable: read topic as changelog (latest per key)
KTable<String, UserProfile> userTable = builder.table("users");
// Mỗi record update state cho key đó → chỉ giữ latest

// GlobalKTable: KTable replicated trên TẤT CẢ instances
GlobalKTable<String, Product> productTable = builder.globalTable("products");
// Mọi instance có FULL data → dùng cho lookup/join nhỏ
```

```
KSTREAM vs KTABLE vs GLOBALKTABLE:

| Tiêu chí          | KStream           | KTable            | GlobalKTable       |
|-------------------|-------------------|--------------------|--------------------|
| Semantics         | Event stream      | Changelog          | Changelog          |
| Records processed | ALL records       | Latest per key     | Latest per key     |
| Partitioned       | Yes               | Yes                | NO (full copy)     |
| State store       | None (stateless)  | Local RocksDB      | Local RocksDB      |
| Scaling           | By partitions     | By partitions      | Every instance     |
| Memory usage      | Low               | Proportional to    | FULL dataset       |
|                   |                   | assigned partitions| on every instance! |
| Join capability   | Stream-Stream     | Stream-Table       | Stream-GlobalTable |
|                   | Stream-Table      | Table-Table        |                    |
| Use case          | Events, logs,     | User profiles,     | Small lookup data  |
|                   | transactions      | product catalog    | (countries, configs)|
|                   |                   | (partitioned)      | (< 1GB total)      |
```

### 4.3 Stateless Operations

```
STATELESS = Không cần nhớ gì từ records trước
          = Mỗi record xử lý independently
          = Không cần state store
          = Nhanh, đơn giản, dễ scale

Operation Overview:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  filter()     — giữ records thỏa điều kiện             │
│  filterNot()  — loại records thỏa điều kiện            │
│  map()        — transform key + value, 1→1             │
│  mapValues()  — transform value only (giữ key), 1→1    │
│  flatMap()    — transform 1 record → 0..N records      │
│  flatMapValues() — flatMap nhưng giữ key               │
│  selectKey()  — đổi key (trigger repartition!)         │
│  branch()     — split stream thành multiple streams    │
│  merge()      — combine multiple streams thành 1       │
│  peek()       — side-effect (logging) không đổi data   │
│  groupByKey() — boundary sang stateful aggregate/reduce   │
│  groupBy()    — boundary + thường trigger repartition     │
│  foreach()    — terminal operation, side-effect only   │
│  to()         — write to output topic                  │
│  through()    — write to topic rồi re-read (repartition)│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Chi tiết từng operation

```
filter() / filterNot():
  Input:  [A, B, C, D, E]
  filter(x -> x > C):  [D, E]
  
  KStream<String, Order> paidOrders = orders
      .filter((key, order) -> order.getStatus().equals("PAID"));

  ⚠️ filter KHÔNG thay đổi key → KHÔNG repartition


map() / mapValues():
  map():      transform CẢ key và value → có thể trigger repartition
  mapValues(): transform CHỈ value     → KHÔNG repartition (preferred!)
  
  // mapValues — preferred vì không repartition
  KStream<String, OrderSummary> summaries = orders
      .mapValues(order -> new OrderSummary(
          order.getId(),
          order.getAmount(),
          order.getCurrency()
      ));
  
  // map — đổi key → warning: triggers repartition!
  KStream<String, Order> rekeyed = orders
      .map((key, order) -> KeyValue.pair(
          order.getCustomerId(),  // new key
          order                   // same value
      ));

  ⚠️ RULE: Dùng mapValues() thay vì map() khi KHÔNG cần đổi key
     Tại sao: map() gây repartition (write to internal topic + re-read)
              = thêm latency + disk I/O + network


flatMap() / flatMapValues():
  1 input record → 0 hoặc nhiều output records
  
  // Split multi-item order thành individual item events
  KStream<String, OrderItem> items = orders
      .flatMapValues(order -> order.getItems());
  
  Input:  Order{items: [ItemA, ItemB, ItemC]}
  Output: [ItemA, ItemB, ItemC]  (3 records)


selectKey():
  Đổi key mà giữ nguyên value
  
  KStream<String, Order> byCustomer = orders
      .selectKey((key, order) -> order.getCustomerId());
  
  ⚠️ TRIGGERS REPARTITION — tương tự map(), data phải shuffle


branch() (KafkaStreams 2.8+: split()):
  Split 1 stream thành nhiều streams dựa trên conditions

  // Kafka Streams 2.8+ syntax
  Map<String, KStream<String, Order>> branches = orders
      .split(Named.as("order-"))
      .branch((key, order) -> order.getAmount() > 1000,
              Branched.as("high-value"))
      .branch((key, order) -> order.getAmount() > 100,
              Branched.as("medium-value"))
      .defaultBranch(Branched.as("low-value"));

  KStream<String, Order> highValue = branches.get("order-high-value");
  KStream<String, Order> mediumValue = branches.get("order-medium-value");
  KStream<String, Order> lowValue = branches.get("order-low-value");

  // Route to different topics
  highValue.to("orders-high-value");
  mediumValue.to("orders-medium-value");
  lowValue.to("orders-low-value");


merge():
  Combine multiple streams thành 1 stream
  
  KStream<String, Order> allOrders = highValue
      .merge(mediumValue)
      .merge(lowValue);
  
  ⚠️ merge KHÔNG guarantee ordering giữa các source streams


peek():
  Side-effect observation — KHÔNG thay đổi data
  
  KStream<String, Order> logged = orders
      .peek((key, order) -> 
          logger.info("Processing order: {} amount: {}", 
              key, order.getAmount()));


groupByKey() vs groupBy() — ranh giới sang stateful:
  groupByKey(): group theo EXISTING key — KHÔNG repartition
  groupBy():    group theo NEW key     — TRIGGERS repartition
  
  // groupByKey — preferred
  KGroupedStream<String, Order> grouped = orders
      .groupByKey();  // key đã là orderId
  
  // groupBy — repartition
  KGroupedStream<String, Order> byCategory = orders
      .groupBy((key, order) -> order.getCategory());
  
  ⚠️ groupByKey + groupBy không còn là stateless transform thuần túy.
     Chúng trả về KGroupedStream và thường đi kèm aggregate/reduce/count ở Day 19.
     Tư duy đúng: `selectKey()`/`map()` đổi key, còn `groupBy()` là điểm Kafka Streams cần repartition để chuẩn bị state store.
```

#### Repartition — Hiểu để avoid

```
REPARTITION — Kafka Streams internal behavior:

  Khi bạn thay đổi KEY (map, selectKey, groupBy),
  Kafka Streams phải REPARTITION data:

  Instance 1 (partitions 0,1)     Instance 2 (partitions 2,3)
  ┌─────────────────────┐        ┌─────────────────────┐
  │ Order{key=A, cat=X} │        │ Order{key=C, cat=X} │
  │ Order{key=B, cat=Y} │        │ Order{key=D, cat=Y} │
  └──────────┬──────────┘        └──────────┬──────────┘
             │ selectKey(category)           │
             ▼                               ▼
  ┌──────────────────────────────────────────────────────┐
  │         Internal Repartition Topic                    │
  │    app-id-KSTREAM-KEY-SELECT-0000000001-repartition  │
  │                                                      │
  │  Partition 0 (hash(X)): {A,cat=X}, {C,cat=X}        │
  │  Partition 1 (hash(Y)): {B,cat=Y}, {D,cat=Y}        │
  └──────────────────────────────────────────────────────┘
             │                               │
             ▼                               ▼
  Instance 1 (partition 0)       Instance 2 (partition 1)
  ┌─────────────────────┐       ┌─────────────────────┐
  │ cat=X: [A, C]       │       │ cat=Y: [B, D]       │
  └─────────────────────┘       └─────────────────────┘

  Cost of repartition:
  - Write to internal topic (disk + network)
  - Re-read from internal topic (disk + network)
  - Thêm latency (~50-200ms)
  - Thêm disk usage (internal topic retained)
  
  AVOID khi không cần thiết!
  → Dùng mapValues() thay vì map()
  → Khi bắt buộc aggregate, dùng groupByKey() nếu key hiện tại đã đúng
  → Design key đúng từ producer (partition by business key)
```

### 4.4 Topology — Execution Plan

#### WHAT — Topology là gì?

```
Topology = DAG (Directed Acyclic Graph) mô tả data flow

  Mỗi Kafka Streams application = 1 Topology
  Topology gồm các nodes:
    - Source Node:    đọc từ Kafka topic
    - Processor Node: xử lý data (filter, map, etc.)
    - Sink Node:      ghi vào Kafka topic

  Ví dụ topology:

  ┌─────────────────────────────────────────────────────┐
  │                    Topology                          │
  │                                                     │
  │  Source("orders")  Source("products")                │
  │       │                 │                            │
  │       ▼                 ▼                            │
  │  filter(paid)      table(products)                  │
  │       │                 │                            │
  │       ▼                 │                            │
  │  mapValues(summary)     │                            │
  │       │                 │                            │
  │       └────────┬────────┘                            │
  │                │                                     │
  │          join(order,product)                          │
  │                │                                     │
  │                ▼                                     │
  │          to("enriched-orders")                       │
  │                                                     │
  │  Sub-topologies:                                     │
  │  [0] orders → filter → mapValues → join → sink      │
  │  [1] products → table                               │
  └─────────────────────────────────────────────────────┘

  Sub-topology = unit of parallelism
  Mỗi sub-topology có thể scale independently
  Partitions quyết định parallelism trong mỗi sub-topology
```

#### HOW — Topology Execution

```
THREADING MODEL:

  ┌─────────────────────────────────────────────┐
  │          Kafka Streams Instance              │
  │                                             │
  │  num.stream.threads = 2                     │
  │                                             │
  │  ┌──────────────────────┐                   │
  │  │   StreamThread-1      │                   │
  │  │                      │                   │
  │  │  ┌────────────────┐  │                   │
  │  │  │ StreamTask P0   │  │ ← processes partition 0  │
  │  │  │ [source→filter │  │                   │
  │  │  │  →map→sink]    │  │                   │
  │  │  └────────────────┘  │                   │
  │  │  ┌────────────────┐  │                   │
  │  │  │ StreamTask P1   │  │ ← processes partition 1  │
  │  │  └────────────────┘  │                   │
  │  └──────────────────────┘                   │
  │                                             │
  │  ┌──────────────────────┐                   │
  │  │   StreamThread-2      │                   │
  │  │                      │                   │
  │  │  ┌────────────────┐  │                   │
  │  │  │ StreamTask P2   │  │ ← processes partition 2  │
  │  │  └────────────────┘  │                   │
  │  │  ┌────────────────┐  │                   │
  │  │  │ StreamTask P3   │  │ ← processes partition 3  │
  │  │  └────────────────┘  │                   │
  │  └──────────────────────┘                   │
  └─────────────────────────────────────────────┘

  Scaling rules:
  - Max parallelism = số partitions của input topic
  - num.stream.threads: threads TRONG 1 instance
  - Multiple instances: giống consumer group (partition rebalance)
  - Total tasks = num.stream.threads × num.instances
    nhưng effective parallelism ≤ num.partitions
```

### 4.5 Kafka Streams vs Flink vs Spark Streaming

```
| Tiêu chí              | Kafka Streams        | Apache Flink         | Spark Streaming      |
|------------------------|----------------------|----------------------|----------------------|
| Type                   | Library (embedded)   | Framework (cluster)  | Framework (cluster)  |
| Deployment             | Microservice/K8s     | Flink cluster        | Spark cluster        |
| Infrastructure         | Chỉ Kafka            | Flink + Kafka/other  | Spark + Kafka/other  |
| Learning curve         | Thấp (Java/Kotlin)   | Trung bình           | Trung bình-Cao       |
| Input sources          | CHỈ Kafka            | Kafka, Kinesis, files| Kafka, Kinesis, files|
| Exactly-once           | Supported bằng Kafka transactions | Supported tùy checkpoint/sink | Supported tùy checkpoint/sink |
| State management       | RocksDB local        | RocksDB managed      | In-memory/external   |
| Windowing              | ✅                    | ✅ (richer)           | ✅                    |
| Event time             | ✅                    | ✅ (best-in-class)    | ✅                    |
| Late events            | Basic (grace period)  | Advanced (side output)| Basic                |
| CEP (Complex Event)    | ❌                    | ✅ (FlinkCEP)         | ❌                    |
| Batch processing       | ❌                    | ✅ (unified)          | ✅ (native)           |
| SQL interface          | ksqlDB (separate)    | Flink SQL (built-in) | Spark SQL (built-in) |
| Scalability            | ~100K msg/s/instance | ~1M+ msg/s           | ~1M+ msg/s           |
| Ops complexity         | Thấp                 | Cao                  | Cao                  |
| Latency                | ~10-100ms            | ~1-10ms              | ~100ms-seconds       |
| Community              | Confluent ecosystem  | Rất lớn              | Rất lớn              |
```

```
CHỌN KAFKA STREAMS khi:
  ✅ Input và output đều là Kafka
  ✅ Đã có Kafka cluster, không muốn thêm infrastructure
  ✅ Team Java/Kotlin, muốn deploy như microservice
  ✅ Stateless hoặc stateful đơn giản (aggregation, join)
  ✅ Throughput vừa phải (~10K-100K msg/s per instance)
  ✅ Ops team nhỏ, không muốn quản lý thêm cluster

CHỌN FLINK khi:
  ✅ Cần complex event processing (CEP patterns)
  ✅ Cần event time processing phức tạp (out-of-order, side output)
  ✅ Input từ nhiều sources (không chỉ Kafka)
  ✅ Cần cả batch + streaming (unified)
  ✅ Throughput rất cao (>1M msg/s)
  ✅ Có team ops dedicated cho cluster

CHỌN SPARK STREAMING khi:
  ✅ Đã có Spark cluster cho batch processing
  ✅ Team quen Spark API (DataFrame, SQL)
  ✅ Use case thiên về analytics / ML pipeline
  ✅ Latency seconds acceptable (micro-batch)
  ❌ KHÔNG recommend cho low-latency event processing
```

---

## 5. Trade-off Analysis

### KStream vs KTable Selection

| Scenario | Chọn | Lý do |
|----------|------|-------|
| Process mọi order event | KStream | Mỗi event là 1 fact cần xử lý |
| Lookup user profile | KTable | Chỉ cần latest profile per userId |
| Audit log | KStream | Cần TẤT CẢ events, không chỉ latest |
| Product catalog | GlobalKTable | Data nhỏ, cần trên mọi instance |
| Running total | KStream → groupBy → aggregate | Stream thành table qua aggregation |
| Config/feature flags | GlobalKTable | Nhỏ, ít thay đổi, cần everywhere |

### Stateless vs Stateful Operations

| Tiêu chí | Stateless | Stateful (Day 19) |
|----------|-----------|-------------------|
| State store | Không cần | RocksDB local |
| Fault tolerance | Trivial | Changelog topic backup |
| Repartition | Chỉ khi đổi key | Thường cần (groupBy) |
| Performance | Rất nhanh | Chi phí I/O cho state |
| Complexity | Thấp | Trung bình-Cao |
| Examples | filter, map, flatMap | aggregate, join, window |
| Use case | Transform, route, enrich | Aggregation, correlation |

### Operations That Trigger Repartition

| Operation | Repartition? | Tại sao |
|-----------|-------------|---------|
| filter() | ❌ | Key không đổi |
| mapValues() | ❌ | Key không đổi |
| map() | ✅ | Key CÓ THỂ đổi |
| flatMap() | ✅ | Key CÓ THỂ đổi |
| flatMapValues() | ❌ | Key không đổi |
| selectKey() | ✅ | Key LUÔN đổi |
| groupByKey() | ❌ repartition, nhưng là stateful boundary | Group theo existing key để aggregate/reduce/count |
| groupBy() | ✅ và là stateful boundary | Group theo new key để aggregate/reduce/count |
| peek() | ❌ | Không đổi gì |
| branch/split() | ❌ | Chỉ route, không đổi key |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. application.id = unique, descriptive, KHÔNG thay đổi
   → Format: "{team}-{app}-{version}" (e.g., "payments-order-enrichment-v1")
   → Đổi application.id = reset toàn bộ state + offsets!
   → Internal topics có prefix: {application.id}-*

2. Dùng mapValues() thay vì map() khi không cần đổi key
   → Avoid repartition = avoid internal topic + network I/O
   → Rule: chỉ dùng map()/selectKey() khi THẬT SỰ cần đổi key; chỉ dùng groupBy() khi sắp aggregate/reduce/count

3. Specific SerDes cho từng stream/table
   StreamsBuilder builder = new StreamsBuilder();
   builder.stream("orders", 
       Consumed.with(Serdes.String(), orderSerde));
   → Avoid default serde issues, explicit is better than implicit

4. Error handling cho deserialization
   props.put(StreamsConfig.DEFAULT_DESERIALIZATION_EXCEPTION_HANDLER_CLASS_CONFIG,
       LogAndContinueExceptionHandler.class);
   → Production: LogAndContinue + alert + DLQ
   → KHÔNG dùng LogAndFail cho production (1 bad message stop toàn bộ app!)

5. Graceful shutdown
   Runtime.getRuntime().addShutdownHook(new Thread(streams::close));
   → streams.close(Duration.ofSeconds(30)) với timeout
   → Đảm bảo state flush + offset commit trước khi exit

6. num.stream.threads ≤ num.partitions / num.instances
   → Ví dụ: 12 partitions, 3 instances → max 4 threads/instance
   → Thừa threads = idle threads, waste resources
```

### Common Pitfalls

```
❌ PITFALL 1: Dùng map() khi chỉ cần transform value
   Sai:  stream.map((k, v) -> KeyValue.pair(k, transform(v)))
   Đúng: stream.mapValues(v -> transform(v))
   Tại sao: map() trigger repartition dù key KHÔNG đổi (Kafka Streams không biết)

❌ PITFALL 2: Đổi application.id trong production
   Sai:  Đổi từ "order-processor" → "order-processor-v2"
   Đúng: Giữ nguyên application.id, dùng version field nếu cần
   Tại sao: Internal topics ({app-id}-*-changelog, *-repartition) bị orphan
            Offsets reset → process lại từ đầu!

❌ PITFALL 3: Side effects trong map/filter (non-idempotent)
   Sai:  stream.mapValues(order -> { 
             httpClient.post("/api/process", order); // side effect!
             return order; 
         })
   Đúng: Side effects chỉ trong foreach() hoặc process() 
         (và phải idempotent!)
   Tại sao: Kafka Streams có thể retry/reprocess → side effect chạy lại

❌ PITFALL 4: GlobalKTable cho large dataset
   Sai:  builder.globalTable("user-events") // 100GB data
   Đúng: builder.table("user-events") // partitioned
   Tại sao: GlobalKTable replicate TOÀN BỘ data trên EVERY instance
            100GB × 10 instances = 1TB RAM/disk

❌ PITFALL 5: Không handle deserialization error
   Sai:  Default = LogAndFail → 1 poison message stop app
   Đúng: Custom handler → log + send to DLQ + continue
   Tại sao: Production data LUÔN có edge cases

❌ PITFALL 6: Quá nhiều operations → topology phức tạp
   Sai:  20 chained operations, 5 repartitions, debug nightmare
   Đúng: Break thành multiple applications, communicate qua topics
   Tại sao: Simpler topology = easier debug, monitoring, scaling
```

---

## 7. Performance Considerations

### Kafka Streams Performance Numbers

```
Benchmark (single instance, 4 cores, 16GB RAM):

  Stateless operations (filter + mapValues):
  - Input: 100K msg/s
  - Throughput: ~90K-95K msg/s (gần line rate Kafka consumer)
  - Latency (p99): ~5-20ms
  
  With repartition (selectKey + groupBy):
  - Input: 100K msg/s  
  - Throughput: ~40K-60K msg/s (internal topic I/O overhead)
  - Latency (p99): ~50-200ms
  
  Stateful (Day 19: aggregate, join):
  - Throughput: ~20K-50K msg/s (RocksDB I/O)
  - Latency (p99): ~100-500ms

Key performance parameters:
  - cache.max.bytes.buffering = 10485760 (10MB default)
    → Buffer records trước khi flush to state store
    → Tăng = throughput tăng, latency tăng
  
  - commit.interval.ms = 30000 (default)
    → Tần suất commit offset + flush state
    → Giảm = data loss window nhỏ hơn, throughput giảm
  
  - num.stream.threads = 1 (default)
    → Parallelism trong 1 JVM instance
    → Set ≤ num.partitions
  
  - buffered.records.per.partition = 1000 (default)
    → Max records buffered per partition trước khi processing
    → Tăng = batch lớn hơn, throughput cao hơn
```

### Monitoring Metrics

```
Essential JMX metrics:

  kafka.streams:type=stream-metrics
  - process-rate            → records processed/s
  - process-latency-avg     → avg processing time/record
  - poll-rate               → Kafka poll rate
  - commit-rate             → offset commit rate
  - task-created-rate       → task rebalance frequency
  
  kafka.streams:type=stream-task-metrics
  - process-latency-max     → worst-case processing time
  - active-process-ratio    → % time actually processing vs polling
  
  kafka.streams:type=stream-thread-metrics
  - thread-start-time       → thread uptime

  Consumer metrics (Kafka Streams uses consumer internally):
  - records-lag-max         → consumer lag (critical for alerting)
  - fetch-rate              → fetch request rate

Alert thresholds:
  - process-rate sudden drop > 50%   → processing issue
  - records-lag-max > 10000          → consumer falling behind
  - commit-rate = 0                  → commit failure (data loss risk)
  - task-created-rate spike          → rebalance storm
```

---

## 8. Hands-on Lab

### 8.1 Setup — Project Structure

```bash
# Project setup (Java + Gradle)
mkdir -p kafka-streams-lab/src/main/java/com/example
mkdir -p kafka-streams-lab/src/main/resources
cd kafka-streams-lab
```

```groovy
// build.gradle
plugins {
    id 'java'
    id 'application'
}

group = 'com.example'
version = '1.0.0'
sourceCompatibility = '17'

repositories {
    mavenCentral()
}

dependencies {
    implementation 'org.apache.kafka:kafka-streams:3.6.0'
    implementation 'org.apache.kafka:kafka-clients:3.6.0'
    implementation 'com.google.code.gson:gson:2.10.1'
    implementation 'org.slf4j:slf4j-simple:2.0.9'
    
    testImplementation 'org.apache.kafka:kafka-streams-test-utils:3.6.0'
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
}

application {
    // Cho phép chạy nhiều main class trong cùng lab:
    // ./gradlew run -PmainClass=com.example.OrderProducer
    mainClass = project.findProperty('mainClass') ?: 'com.example.OrderProcessingApp'
}

test {
    useJUnitPlatform()
}
```

```yaml
# docker-compose.yml (reuse KRaft baseline from Day 16, ensure Kafka running)
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
      KAFKA_NUM_PARTITIONS: 4
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
```

```bash
docker compose up -d

# Create input/output topics
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create --topic orders --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic orders-high-value --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic orders-standard --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic order-notifications --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic order-metrics --partitions 4 --replication-factor 1
"
```

### 8.2 Data Model

```java
// src/main/java/com/example/Order.java
package com.example;

public class Order {
    private String orderId;
    private String customerId;
    private String category;
    private double amount;
    private String currency;
    private String status;
    private long createdAt;
    private String region;

    public Order() {}

    public Order(String orderId, String customerId, String category,
                 double amount, String currency, String status,
                 long createdAt, String region) {
        this.orderId = orderId;
        this.customerId = customerId;
        this.category = category;
        this.amount = amount;
        this.currency = currency;
        this.status = status;
        this.createdAt = createdAt;
        this.region = region;
    }

    // Getters
    public String getOrderId() { return orderId; }
    public String getCustomerId() { return customerId; }
    public String getCategory() { return category; }
    public double getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public String getStatus() { return status; }
    public long getCreatedAt() { return createdAt; }
    public String getRegion() { return region; }

    // Setters
    public void setOrderId(String orderId) { this.orderId = orderId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }
    public void setCategory(String category) { this.category = category; }
    public void setAmount(double amount) { this.amount = amount; }
    public void setCurrency(String currency) { this.currency = currency; }
    public void setStatus(String status) { this.status = status; }
    public void setCreatedAt(long createdAt) { this.createdAt = createdAt; }
    public void setRegion(String region) { this.region = region; }

    @Override
    public String toString() {
        return String.format("Order{id=%s, customer=%s, category=%s, amount=%.2f %s, status=%s, region=%s}",
                orderId, customerId, category, amount, currency, status, region);
    }
}
```

```java
// src/main/java/com/example/OrderNotification.java
package com.example;

public class OrderNotification {
    private String orderId;
    private String customerId;
    private String type;
    private String message;
    private long timestamp;

    public OrderNotification() {}

    public OrderNotification(String orderId, String customerId,
                              String type, String message, long timestamp) {
        this.orderId = orderId;
        this.customerId = customerId;
        this.type = type;
        this.message = message;
        this.timestamp = timestamp;
    }

    public String getOrderId() { return orderId; }
    public String getCustomerId() { return customerId; }
    public String getType() { return type; }
    public String getMessage() { return message; }
    public long getTimestamp() { return timestamp; }

    @Override
    public String toString() {
        return String.format("Notification{order=%s, type=%s, msg=%s}", orderId, type, message);
    }
}
```

```java
// src/main/java/com/example/JsonSerde.java
package com.example;

import com.google.gson.Gson;
import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serializer;

import java.nio.charset.StandardCharsets;

public class JsonSerde<T> implements Serde<T> {
    private final Gson gson = new Gson();
    private final Class<T> clazz;

    public JsonSerde(Class<T> clazz) {
        this.clazz = clazz;
    }

    @Override
    public Serializer<T> serializer() {
        return (topic, data) -> {
            if (data == null) return null;
            return gson.toJson(data).getBytes(StandardCharsets.UTF_8);
        };
    }

    @Override
    public Deserializer<T> deserializer() {
        return (topic, data) -> {
            if (data == null) return null;
            return gson.fromJson(new String(data, StandardCharsets.UTF_8), clazz);
        };
    }
}
```

### 8.3 Order Processing Pipeline — Stateless Operations

```java
// src/main/java/com/example/OrderProcessingApp.java
package com.example;

import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.*;
import org.apache.kafka.streams.errors.StreamsUncaughtExceptionHandler;
import org.apache.kafka.streams.kstream.*;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CountDownLatch;

public class OrderProcessingApp {

    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "order-processing-v1");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        // Day 18 giữ lab basic ở at-least-once để chạy ổn trên single broker.
        // EXACTLY_ONCE_V2 cần transaction state log configs và sẽ học kỹ ở Day 19.
        props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.AT_LEAST_ONCE);
        props.put(StreamsConfig.DEFAULT_DESERIALIZATION_EXCEPTION_HANDLER_CLASS_CONFIG,
                SafeDeserializationHandler.class);
        // Commit interval
        props.put(StreamsConfig.COMMIT_INTERVAL_MS_CONFIG, 1000);
        // 2 threads for parallelism
        props.put(StreamsConfig.NUM_STREAM_THREADS_CONFIG, 2);

        Topology topology = buildTopology();

        // Print topology for debugging
        System.out.println("=== Topology Description ===");
        System.out.println(topology.describe());
        System.out.println("============================");

        KafkaStreams streams = new KafkaStreams(topology, props);

        // Graceful shutdown
        CountDownLatch latch = new CountDownLatch(1);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("Shutting down streams...");
            streams.close(Duration.ofSeconds(30));
            latch.countDown();
        }));

        // State listener
        streams.setStateListener((newState, oldState) -> {
            System.out.printf("State changed: %s → %s%n", oldState, newState);
        });

        // Uncaught exception handler
        streams.setUncaughtExceptionHandler(exception -> {
            System.err.printf("Uncaught exception: %s%n", exception.getMessage());
            return StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.REPLACE_THREAD;
        });

        try {
            streams.start();
            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    static Topology buildTopology() {
        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Order> orderSerde = new JsonSerde<>(Order.class);
        JsonSerde<OrderNotification> notifSerde = new JsonSerde<>(OrderNotification.class);

        // Source: read orders topic
        KStream<String, Order> orders = builder.stream(
                "orders",
                Consumed.with(Serdes.String(), orderSerde)
                        .withName("source-orders")
        );

        // 1. PEEK — logging (side-effect, không thay đổi data)
        KStream<String, Order> loggedOrders = orders
                .peek((key, order) -> System.out.printf(
                        "[RECEIVED] key=%s order=%s%n", key, order),
                        Named.as("peek-log-input"));

        // 2. FILTER — chỉ xử lý orders có status PAID
        KStream<String, Order> paidOrders = loggedOrders
                .filter((key, order) -> "PAID".equals(order.getStatus()),
                        Named.as("filter-paid-only"));

        // 3. BRANCH/SPLIT — phân loại theo amount
        Map<String, KStream<String, Order>> branches = paidOrders
                .split(Named.as("split-by-amount-"))
                .branch((key, order) -> order.getAmount() >= 1000,
                        Branched.as("high-value"))
                .defaultBranch(Branched.as("standard"));

        KStream<String, Order> highValueOrders = branches.get("split-by-amount-high-value");
        KStream<String, Order> standardOrders = branches.get("split-by-amount-standard");

        // 4. MAPVALUES — transform high-value orders (tag for special handling)
        KStream<String, Order> taggedHighValue = highValueOrders
                .mapValues(order -> new Order(
                        order.getOrderId(),
                        order.getCustomerId(),
                        "VIP-" + order.getCategory(),
                        order.getAmount(),
                        order.getCurrency(),
                        order.getStatus(),
                        order.getCreatedAt(),
                        order.getRegion()
                ), Named.as("mapValues-tag-vip"));

        // 5. Route to different output topics
        taggedHighValue.to("orders-high-value",
                Produced.with(Serdes.String(), orderSerde)
                        .withName("sink-high-value"));

        standardOrders.to("orders-standard",
                Produced.with(Serdes.String(), orderSerde)
                        .withName("sink-standard"));

        // 6. FLATMAPVALUES — tạo notifications cho mỗi order
        //    1 order → 2 notifications (customer + internal)
        KStream<String, OrderNotification> notifications = paidOrders
                .flatMapValues((key, order) -> {
                    List<OrderNotification> notifs = new ArrayList<>();
                    long now = Instant.now().toEpochMilli();

                    // Customer notification
                    notifs.add(new OrderNotification(
                            order.getOrderId(),
                            order.getCustomerId(),
                            "CUSTOMER",
                            String.format("Your order %s (%.2f %s) has been processed",
                                    order.getOrderId(), order.getAmount(), order.getCurrency()),
                            now
                    ));

                    // Internal notification for high-value orders
                    if (order.getAmount() >= 1000) {
                        notifs.add(new OrderNotification(
                                order.getOrderId(),
                                order.getCustomerId(),
                                "INTERNAL_ALERT",
                                String.format("High-value order %s: %.2f %s from %s",
                                        order.getOrderId(), order.getAmount(),
                                        order.getCurrency(), order.getRegion()),
                                now
                        ));
                    }

                    return notifs;
                }, Named.as("flatMapValues-notifications"));

        notifications.to("order-notifications",
                Produced.with(Serdes.String(), notifSerde)
                        .withName("sink-notifications"));

        // 7. MAPVALUES — create simple metrics (order count by category prep)
        KStream<String, String> metrics = paidOrders
                .mapValues(order -> String.format(
                        "{\"orderId\":\"%s\",\"category\":\"%s\",\"amount\":%.2f,\"region\":\"%s\",\"ts\":%d}",
                        order.getOrderId(), order.getCategory(),
                        order.getAmount(), order.getRegion(),
                        order.getCreatedAt()),
                        Named.as("mapValues-metrics"));

        metrics.to("order-metrics",
                Produced.with(Serdes.String(), Serdes.String())
                        .withName("sink-metrics"));

        // 8. MERGE — unified stream for monitoring
        KStream<String, Order> allProcessed = taggedHighValue.merge(standardOrders,
                Named.as("merge-all-processed"));

        allProcessed.peek((key, order) ->
                System.out.printf("[PROCESSED] key=%s order=%s%n", key, order),
                Named.as("peek-log-output"));

        return builder.build();
    }
}
```

### 8.4 Test Data Producer

```java
// src/main/java/com/example/OrderProducer.java
package com.example;

import com.google.gson.Gson;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

public class OrderProducer {
    private static final Gson gson = new Gson();
    private static final String[] CATEGORIES = {"Electronics", "Clothing", "Food", "Books", "Home"};
    private static final String[] STATUSES = {"CREATED", "PAID", "SHIPPED", "CANCELLED"};
    private static final String[] REGIONS = {"US-WEST", "US-EAST", "EU-WEST", "APAC"};
    private static final String[] CURRENCIES = {"USD", "EUR", "VND"};

    public static void main(String[] args) throws InterruptedException {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

        try (Producer<String, String> producer = new KafkaProducer<>(props)) {
            for (int i = 0; i < 20; i++) {
                ThreadLocalRandom rand = ThreadLocalRandom.current();
                String orderId = "ORD-" + UUID.randomUUID().toString().substring(0, 8);
                String customerId = "CUST-" + String.format("%03d", rand.nextInt(1, 50));

                Order order = new Order(
                        orderId,
                        customerId,
                        CATEGORIES[rand.nextInt(CATEGORIES.length)],
                        rand.nextDouble(10, 5000),
                        CURRENCIES[rand.nextInt(CURRENCIES.length)],
                        STATUSES[rand.nextInt(STATUSES.length)],
                        System.currentTimeMillis(),
                        REGIONS[rand.nextInt(REGIONS.length)]
                );

                String value = gson.toJson(order);
                ProducerRecord<String, String> record =
                        new ProducerRecord<>("orders", orderId, value);

                producer.send(record, (metadata, exception) -> {
                    if (exception != null) {
                        System.err.printf("Send failed: %s%n", exception.getMessage());
                    } else {
                        System.out.printf("Sent: %s → partition=%d offset=%d%n",
                                orderId, metadata.partition(), metadata.offset());
                    }
                });

                Thread.sleep(500);
            }
        }

        System.out.println("Producer finished. 20 orders sent.");
    }
}
```

### 8.5 Run và Verify

```bash
# Terminal 1: Start Kafka Streams app
cd kafka-streams-lab
./gradlew run

# Terminal 2: Produce test data
./gradlew run -PmainClass=com.example.OrderProducer

# Terminal 3: Consume high-value orders
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic orders-high-value \
  --from-beginning

# Terminal 4: Consume notifications
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-notifications \
  --from-beginning

# Terminal 5: Check metrics topic
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-metrics \
  --from-beginning
```

### 8.6 Unit Testing với TopologyTestDriver

```java
// src/test/java/com/example/OrderProcessingAppTest.java
package com.example;

import com.google.gson.Gson;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.streams.*;
import org.junit.jupiter.api.*;

import java.util.Properties;

import static org.junit.jupiter.api.Assertions.*;

class OrderProcessingAppTest {

    private TopologyTestDriver testDriver;
    private TestInputTopic<String, String> inputTopic;
    private TestOutputTopic<String, Order> highValueOutput;
    private TestOutputTopic<String, Order> standardOutput;
    private TestOutputTopic<String, OrderNotification> notificationsOutput;
    private final Gson gson = new Gson();

    @BeforeEach
    void setup() {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "test-order-processing");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "dummy:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);

        Topology topology = OrderProcessingApp.buildTopology();
        testDriver = new TopologyTestDriver(topology, props);

        inputTopic = testDriver.createInputTopic(
                "orders",
                new StringSerializer(),
                new StringSerializer());

        highValueOutput = testDriver.createOutputTopic(
                "orders-high-value",
                new StringDeserializer(),
                new JsonSerde<>(Order.class).deserializer());

        standardOutput = testDriver.createOutputTopic(
                "orders-standard",
                new StringDeserializer(),
                new JsonSerde<>(Order.class).deserializer());

        notificationsOutput = testDriver.createOutputTopic(
                "order-notifications",
                new StringDeserializer(),
                new JsonSerde<>(OrderNotification.class).deserializer());
    }

    @AfterEach
    void teardown() {
        testDriver.close();
    }

    @Test
    void shouldRouteHighValueOrdersToHighValueTopic() {
        Order order = new Order("ORD-001", "CUST-001", "Electronics",
                2500.00, "USD", "PAID", System.currentTimeMillis(), "US-WEST");
        inputTopic.pipeInput("ORD-001", gson.toJson(order));

        assertFalse(highValueOutput.isEmpty());
        KeyValue<String, Order> result = highValueOutput.readKeyValue();
        assertEquals("ORD-001", result.key);
        assertTrue(result.value.getCategory().startsWith("VIP-"));
    }

    @Test
    void shouldRouteStandardOrdersToStandardTopic() {
        Order order = new Order("ORD-002", "CUST-002", "Books",
                29.99, "USD", "PAID", System.currentTimeMillis(), "EU-WEST");
        inputTopic.pipeInput("ORD-002", gson.toJson(order));

        assertFalse(standardOutput.isEmpty());
        assertTrue(highValueOutput.isEmpty());
    }

    @Test
    void shouldFilterNonPaidOrders() {
        Order order = new Order("ORD-003", "CUST-003", "Food",
                50.00, "USD", "CREATED", System.currentTimeMillis(), "APAC");
        inputTopic.pipeInput("ORD-003", gson.toJson(order));

        assertTrue(highValueOutput.isEmpty());
        assertTrue(standardOutput.isEmpty());
        assertTrue(notificationsOutput.isEmpty());
    }

    @Test
    void shouldGenerateMultipleNotificationsForHighValueOrder() {
        Order order = new Order("ORD-004", "CUST-004", "Electronics",
                5000.00, "USD", "PAID", System.currentTimeMillis(), "US-EAST");
        inputTopic.pipeInput("ORD-004", gson.toJson(order));

        // High-value order → 2 notifications (customer + internal alert)
        var notifications = notificationsOutput.readValuesToList();
        assertEquals(2, notifications.size());
        assertEquals("CUSTOMER", notifications.get(0).getType());
        assertEquals("INTERNAL_ALERT", notifications.get(1).getType());
    }

    @Test
    void shouldGenerateSingleNotificationForStandardOrder() {
        Order order = new Order("ORD-005", "CUST-005", "Books",
                25.00, "USD", "PAID", System.currentTimeMillis(), "EU-WEST");
        inputTopic.pipeInput("ORD-005", gson.toJson(order));

        var notifications = notificationsOutput.readValuesToList();
        assertEquals(1, notifications.size());
        assertEquals("CUSTOMER", notifications.get(0).getType());
    }

    @Test
    void topologyDescriptionShouldBeReadable() {
        Topology topology = OrderProcessingApp.buildTopology();
        String description = topology.describe().toString();
        assertTrue(description.contains("source-orders"));
        assertTrue(description.contains("filter-paid-only"));
        assertTrue(description.contains("sink-high-value"));
        System.out.println(description);
    }
}
```

```bash
# Run tests
./gradlew test

# Expected:
# 6 tests passed
# TopologyTestDriver cho phép test TOÀN BỘ pipeline
# KHÔNG cần Kafka cluster running!
```

### 8.7 Failure Scenario — Deserialization Error Handling

```java
// src/main/java/com/example/SafeDeserializationHandler.java
package com.example;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.streams.errors.ErrorHandlerContext;
import org.apache.kafka.streams.errors.DeserializationExceptionHandler;

import java.util.Map;

public class SafeDeserializationHandler implements DeserializationExceptionHandler {

    @Override
    public DeserializationExceptionHandler.DeserializationHandlerResponse handle(
            ErrorHandlerContext context,
            ConsumerRecord<byte[], byte[]> record,
            Exception exception) {
        System.err.printf(
                "[DLQ] Deserialization failed — topic=%s partition=%d offset=%d error=%s%n",
                record.topic(), record.partition(), record.offset(),
                exception.getMessage());

        // In production: send to DLQ topic
        // dlqProducer.send(new ProducerRecord<>("dlq-orders", record.key(), record.value()));

        return DeserializationExceptionHandler.DeserializationHandlerResponse.CONTINUE;
    }

    @Override
    public void configure(Map<String, ?> configs) {}
}
```

```bash
# Send malformed message to test error handling
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic orders \
  --property "parse.key=true" \
  --property "key.separator=|"

# Type: BAD-KEY|{this is not valid json!!!}
# Observe: Streams app logs error, continues processing
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **KStream và KTable đọc từ cùng 1 topic. Nếu topic nhận 5 records với key "A" (values: 1, 2, 3, 4, 5), KStream xử lý bao nhiêu records và KTable "thấy" bao nhiêu records?**
   - Hint: KStream = event stream (all records), KTable = changelog (latest per key).

2. **Tại sao `mapValues()` được recommend hơn `map()` khi không cần đổi key? Giải thích cơ chế repartition.**
   - Hint: Kafka Streams không thể biết `map()` có thay đổi key hay không, nên assume worst case.

3. **Application A có `application.id = "order-processor"` và chạy 3 instances. Input topic có 12 partitions. Mỗi instance nên set `num.stream.threads` bao nhiêu? Nếu set quá nhiều thì sao?**
   - Hint: total tasks ≤ total partitions. 12 partitions / 3 instances = ?

4. **So sánh Kafka Streams và Flink. Trong scenario nào bạn PHẢI chọn Flink thay vì Kafka Streams?**
   - Hint: multi-source input, complex event processing, batch+streaming unified.

5. **Bạn đổi `application.id` từ "order-processor-v1" sang "order-processor-v2" trong production. Hậu quả là gì?**
   - Hint: internal topics (changelog, repartition), consumer group offsets.

6. **GlobalKTable replicate toàn bộ data trên tất cả instances. Khi nào việc này là vấn đề? Khi nào là advantage?**
   - Hint: memory/disk cost vs join flexibility (không cần co-partitioning).

7. **TopologyTestDriver test KHÔNG cần Kafka cluster. Đây là ưu điểm, nhưng có limitation gì so với integration test?**
   - Hint: timing, rebalancing, multi-instance behavior, real serialization/network.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Streams Documentation](https://kafka.apache.org/documentation/streams/)
- [Kafka Streams Developer Guide](https://docs.confluent.io/platform/current/streams/developer-guide/index.html)
- [Kafka Streams DSL](https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html)
- [Kafka Streams Architecture](https://docs.confluent.io/platform/current/streams/architecture.html)

### Blog Posts & Articles
- [Confluent — Kafka Streams 101](https://developer.confluent.io/courses/kafka-streams/get-started/)
- [Confluent — Event-Driven Microservices with Kafka Streams](https://www.confluent.io/blog/event-driven-microservices-with-kafka-streams/)
- [Martin Kleppmann — Turning the database inside-out](https://www.confluent.io/blog/turning-the-database-inside-out-with-apache-kafka/)
- [Confluent — Stream-Table Duality](https://www.confluent.io/blog/kafka-streams-tables-part-1-event-streaming/)

### Videos & Talks
- [Kafka Summit — Kafka Streams: What It Is and What It Isn't](https://www.confluent.io/events/kafka-summit/)
- [Tim Berglund — Kafka Streams Interactive Queries](https://www.youtube.com/results?search_query=kafka+streams+tim+berglund)
- [GOTO Conference — Designing Event-Driven Systems](https://www.youtube.com/results?search_query=kafka+streams+goto+conference)
