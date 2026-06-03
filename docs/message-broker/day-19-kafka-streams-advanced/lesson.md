# Day 19: Kafka Streams Nâng Cao — Stateful Operations, Windowing, Joins, Interactive Queries

> Companion split: xem `document.md` để đào sâu state store/windowing và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** stateful operations: aggregate, reduce, count — cách Kafka Streams quản lý state bằng RocksDB và changelog topics
2. **Nắm vững** windowing: tumbling, hopping, session, sliding — khi nào dùng loại nào và trade-off
3. **Thực hành** stream-stream joins, stream-table joins, table-table joins — co-partitioning requirement và cách xử lý
4. **Hiểu** Interactive Queries — query local state store và biết khi nào cần REST/metadata forwarding trong multi-instance deployment
5. **Nắm rõ** exactly-once processing trong phạm vi Kafka Streams — offsets, output topics, changelog/state store recovery, và giới hạn với external side effects

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 18 (KStream, KTable, stateless operations, topology)
- Hiểu rõ KStream vs KTable duality
- Hiểu repartition mechanism và khi nào nó xảy ra
- Docker Compose Kafka cluster đang chạy
- Java 17+ và Gradle project từ Day 18

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Stateful operations: aggregate, reduce, count — state store internals (RocksDB + changelog)
- Windowing: tumbling, hopping, session windows — syntax, semantics, grace period
- Joins: stream-stream, stream-table — co-partitioning requirement
- Hands-on: real-time revenue dashboard với windowed aggregation + stream-table join

### 🟡 Should Learn (nếu còn thời gian)
- Interactive Queries — ReadOnlyKeyValueStore, ReadOnlyWindowStore
- Table-table joins — foreign key joins (KIP-213)
- Suppression — suppress intermediate results trong windowed aggregation
- State store recovery — changelog replay, standby replicas

### 🟢 Optional Deep Dive
- Custom state store implementation
- Exactly-once processing internals (producer transactions + consumer read_committed)
- Punctuator — schedule periodic actions trong Processor API
- Out-of-order event handling strategies

---

## 4. Lý thuyết (Theory)

### 4.1 Stateful Operations — Tại sao cần State?

#### WHY — Stateless không đủ cho aggregation

```
VẤN ĐỀ:
  "Tính tổng doanh thu theo category trong 1 giờ qua"

  Stateless approach:
  ┌──────────┐     ┌──────────────────┐
  │  orders   │────►│ filter + map     │────► ???
  │  topic    │     │ (stateless)      │
  └──────────┘     └──────────────────┘
  
  Bạn nhận được order A = $100 (Electronics)
  Rồi order B = $200 (Electronics)
  
  Để tính SUM = $300, bạn PHẢI NHỚ order A khi xử lý order B
  → Cần STATE (bộ nhớ giữa các records)


KAFKA STREAMS STATEFUL SOLUTION:

  ┌──────────┐     ┌──────────────────────────┐     ┌──────────┐
  │  orders   │────►│ groupByKey()              │────►│  output  │
  │  topic    │     │   .windowedBy(1h)         │     │  topic   │
  └──────────┘     │   .aggregate(sum)          │     └──────────┘
                   │                            │
                   │  ┌──────────────────────┐  │
                   │  │ RocksDB State Store   │  │
                   │  │ ┌──────────┬────────┐ │  │
                   │  │ │ Key      │ Value  │ │  │
                   │  │ ├──────────┼────────┤ │  │
                   │  │ │ Elec/10h │ $300   │ │  │
                   │  │ │ Food/10h │ $150   │ │  │
                   │  │ │ Book/10h │ $50    │ │  │
                   │  │ └──────────┴────────┘ │  │
                   │  └──────────────────────┘  │
                   │         ↕ backup            │
                   │  ┌──────────────────────┐  │
                   │  │ Changelog Topic       │  │
                   │  │ (fault tolerance)     │  │
                   │  └──────────────────────┘  │
                   └──────────────────────────┘

  State Store = RocksDB (embedded key-value DB)
  - Trên local disk của instance
  - Backed by changelog topic (auto-created)
  - Crash → restart → replay changelog → state restored
```

#### WHAT — State Store Architecture

```
STATE STORE INTERNALS:

  ┌─────────────────────────────────────────────────────────┐
  │                  Kafka Streams Instance                   │
  │                                                         │
  │  ┌─────────────────────────────────┐                    │
  │  │        StreamTask (partition 0)  │                    │
  │  │                                 │                    │
  │  │  ┌───────────────────────────┐  │                    │
  │  │  │     RocksDB State Store    │  │                    │
  │  │  │                           │  │                    │
  │  │  │  In-memory cache          │  │                    │
  │  │  │  ┌─────────────────────┐  │  │                    │
  │  │  │  │ cache (10MB default) │  │  │                    │
  │  │  │  │ write-buffer         │  │  │                    │
  │  │  │  └────────┬────────────┘  │  │                    │
  │  │  │           │ flush         │  │                    │
  │  │  │  ┌────────▼────────────┐  │  │                    │
  │  │  │  │ RocksDB on disk     │  │  │                    │
  │  │  │  │ (SST files)         │  │  │                    │
  │  │  │  └────────┬────────────┘  │  │                    │
  │  │  │           │ write-ahead   │  │                    │
  │  │  └───────────┼───────────────┘  │                    │
  │  │              │                  │                    │
  │  └──────────────┼──────────────────┘                    │
  │                 │                                       │
  │                 ▼                                       │
  │  ┌──────────────────────────────────┐                   │
  │  │  Changelog Topic (Kafka)          │                   │
  │  │  {app-id}-{store-name}-changelog  │                   │
  │  │                                  │                   │
  │  │  Compacted topic                 │                   │
  │  │  key = state store key           │                   │
  │  │  value = state store value       │                   │
  │  │  Retention = forever (compacted) │                   │
  │  └──────────────────────────────────┘                   │
  └─────────────────────────────────────────────────────────┘

  RECOVERY FLOW (khi instance crash + restart):
  1. Instance mới start, được assign partition 0
  2. Tạo RocksDB store trống
  3. Replay toàn bộ changelog topic từ đầu
  4. State restored → bắt đầu processing
  
  STANDBY REPLICAS (giảm recovery time):
  - num.standby.replicas = 1
  - Instance khác giữ copy of state store
  - Crash → standby promote → near-instant recovery
  - Trade-off: thêm disk + network cho standby replication
```

#### HOW — Aggregate, Reduce, Count

```java
// 1. COUNT — đếm records per key
KTable<String, Long> orderCountByCategory = orders
    .groupBy((key, order) -> order.getCategory())  // repartition!
    .count(Materialized.as("order-count-store"));
// Internal: mỗi record đến → state[category] += 1

// 2. REDUCE — combine values (same type in, same type out)
KTable<String, Order> maxOrderByCategory = orders
    .groupBy((key, order) -> order.getCategory())
    .reduce(
        (aggValue, newValue) -> 
            aggValue.getAmount() >= newValue.getAmount() ? aggValue : newValue,
        Materialized.as("max-order-store")
    );
// Internal: mỗi record đến → state[category] = max(current, new)

// 3. AGGREGATE — flexible aggregation (different type out)
KTable<String, Double> revenueByCategory = orders
    .groupBy((key, order) -> order.getCategory())
    .aggregate(
        () -> 0.0,                    // initializer
        (key, order, totalRevenue) -> // aggregator
            totalRevenue + order.getAmount(),
        Materialized.<String, Double, KeyValueStore<Bytes, byte[]>>as(
            "revenue-store")
            .withKeySerde(Serdes.String())
            .withValueSerde(Serdes.Double())
    );
// Internal: mỗi record đến → state[category] += order.amount
```

```
AGGREGATE vs REDUCE vs COUNT:

| Operation  | Input Type | Output Type | Use Case                    |
|-----------|------------|-------------|------------------------------|
| count()   | V          | Long        | Đếm records per key          |
| reduce()  | V          | V (same)    | Min, max, latest per key     |
| aggregate()| V         | VR (any)    | Sum, avg, custom aggregation |

Rule of thumb:
- Chỉ cần đếm → count()
- Output type = input type → reduce()
- Output type khác input type → aggregate()
```

### 4.2 Windowing — Time-based Aggregation

#### WHY — Tại sao cần Windowing?

```
VẤN ĐỀ:
  "Tính doanh thu theo giờ" 
   → Nếu dùng aggregate() thông thường → tổng TẤT CẢ thời gian
   → Cần chia data theo TIME WINDOWS

  Timeline:
  09:00    09:15    09:30    09:45    10:00    10:15    10:30
  ──┼────────┼────────┼────────┼────────┼────────┼────────┼──
    │ $100   │ $200   │ $150   │        │ $300   │ $50    │
    │ $50    │        │ $100   │        │        │ $200   │
    │        │        │        │        │        │        │

  Window 09:00-10:00: $100 + $50 + $200 + $150 + $100 = $600
  Window 10:00-11:00: $300 + $50 + $200 = $550

  4 LOẠI WINDOWS trong Kafka Streams:
```

#### WHAT — 4 Window Types

```
1. TUMBLING WINDOW (fixed, non-overlapping):

  ┌──────────────┐┌──────────────┐┌──────────────┐
  │  Window 1     ││  Window 2     ││  Window 3     │
  │  09:00-10:00  ││  10:00-11:00  ││  11:00-12:00  │
  │  $600         ││  $550         ││  ...          │
  └──────────────┘└──────────────┘└──────────────┘
  
  - Size: cố định (ví dụ 1 giờ)
  - Overlap: KHÔNG
  - Mỗi event thuộc ĐÚNG 1 window
  - Use case: hourly/daily reports, billing periods

  TimeWindows.ofSizeWithNoGrace(Duration.ofHours(1))
  // hoặc
  TimeWindows.ofSizeAndGrace(Duration.ofHours(1), Duration.ofMinutes(5))


2. HOPPING WINDOW (fixed, overlapping):

  ┌──────────────────┐
  │  Window 1: 09:00-10:00  │
  └───────┬──────────────────┘
          ┌──────────────────┐
          │  Window 2: 09:30-10:30  │
          └───────┬──────────────────┘
                  ┌──────────────────┐
                  │  Window 3: 10:00-11:00  │
                  └──────────────────┘
  
  - Size: cố định (ví dụ 1 giờ)
  - Advance/Hop: interval nhỏ hơn size (ví dụ 30 phút)
  - Overlap: CÓ — mỗi event thuộc NHIỀU windows
  - Use case: moving average, sliding metrics

  TimeWindows.ofSizeAndGrace(Duration.ofHours(1), Duration.ofMinutes(5))
      .advanceBy(Duration.ofMinutes(30))


3. SESSION WINDOW (dynamic, gap-based):

  User A:
  ┌─────────┐        ┌──────────────────────────┐
  │ Session 1│        │ Session 2                 │
  │ 09:00    │  gap   │ 09:45  09:50  10:05      │
  │ 09:02    │ >30min │                           │
  └─────────┘        └──────────────────────────┘
  
  User B:
  ┌──────────────────────────────────────────┐
  │ Session 1 (liên tục, gap < 30min)         │
  │ 09:00  09:10  09:25  09:40  09:55        │
  └──────────────────────────────────────────┘
  
  - Size: DYNAMIC (phụ thuộc activity)
  - Inactivity gap: nếu không có event trong X phút → close session
  - Mỗi key có sessions riêng
  - Use case: user sessions, clickstream analysis

  SessionWindows.ofInactivityGapWithNoGrace(Duration.ofMinutes(30))


4. SLIDING WINDOW (fixed, continuous — chỉ cho joins):

  Dùng trong stream-stream joins:
  "Join order với payment nếu cả 2 xảy ra trong 10 phút"

  JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofMinutes(10))
```

#### HOW — Windowed Aggregation trong Code

```java
// Tumbling window: doanh thu theo giờ
KTable<Windowed<String>, Double> hourlyRevenue = orders
    .groupBy((key, order) -> order.getCategory())
    .windowedBy(TimeWindows.ofSizeAndGrace(
        Duration.ofHours(1),     // window size
        Duration.ofMinutes(5)))  // grace period for late events
    .aggregate(
        () -> 0.0,
        (key, order, total) -> total + order.getAmount(),
        Materialized.<String, Double, WindowStore<Bytes, byte[]>>as(
            "hourly-revenue-store")
            .withKeySerde(Serdes.String())
            .withValueSerde(Serdes.Double())
    );

// Output: Windowed<String> key chứa cả category + window time
hourlyRevenue
    .toStream()
    .map((windowedKey, revenue) -> KeyValue.pair(
        windowedKey.key() + "@" + windowedKey.window().startTime(),
        String.format("{\"category\":\"%s\",\"window_start\":%d,\"window_end\":%d,\"revenue\":%.2f}",
            windowedKey.key(),
            windowedKey.window().startTime().toEpochMilli(),
            windowedKey.window().endTime().toEpochMilli(),
            revenue)
    ))
    .to("hourly-revenue", 
        Produced.with(Serdes.String(), Serdes.String()));
```

```
GRACE PERIOD — Xử lý Late Events:

  Window 09:00-10:00, grace = 5 phút

  Timeline:
  09:00          10:00         10:05
  ──┼──────────────┼─────────────┼──
    │← window →    │← grace →   │
    │              │             │
    │  $100 ✓      │  $50 ✓     │ $30 ✗ (dropped!)
    │  accepted    │  late but   │ past grace period
    │              │  accepted   │

  - Grace period được tính theo **stream-time**, không phải wall clock.
  - Stream-time = timestamp lớn nhất Kafka Streams đã thấy trên task/partition.
  - Window đóng khi stream-time vượt `window_end + grace`.
  - Event có event_time nằm trong window và đến trước khi stream-time vượt ngưỡng → update aggregate.
  - Event đến sau khi stream-time vượt `window_end + grace` → DROPPED (hoặc forward to late-events topic).
  
  Trade-off:
  - Grace dài → ít mất data, nhưng emit results chậm hơn
  - Grace ngắn → results nhanh hơn, nhưng late events bị drop
  - Grace = 0 → close window ngay, KHÔNG chấp nhận late events
```

### 4.3 Joins — Correlating Streams

#### WHY — Tại sao cần Join?

```
SCENARIO: Enrich order với customer profile

  Kafka Topic "orders":         Kafka Topic "customers":
  ┌──────────────────────┐      ┌──────────────────────┐
  │ key: ORD-001          │      │ key: CUST-001        │
  │ customerId: CUST-001  │      │ name: "Alice"        │
  │ amount: 2500          │      │ tier: "Gold"         │
  │ category: Electronics │      │ region: "APAC"       │
  └──────────────────────┘      └──────────────────────┘
         │                              │
         └─────────── JOIN ─────────────┘
                      │
                      ▼
  ┌──────────────────────────────────────────┐
  │ key: ORD-001                              │
  │ customerName: "Alice"                     │
  │ customerTier: "Gold"                      │
  │ amount: 2500                              │
  │ category: Electronics                     │
  │ region: "APAC"                            │
  └──────────────────────────────────────────┘
```

#### WHAT — 3 Join Types

```
JOIN TYPES:

1. STREAM-TABLE JOIN (most common):
   KStream<K,V1> + KTable<K,V2> → KStream<K,VR>
   
   - LEFT JOIN hoặc INNER JOIN
   - Stream record arrives → lookup KTable for matching key
   - KTable đã được update trước → join lấy latest value
   - KHÔNG cần window (table luôn "current")
   - REQUIRE: co-partitioned (cùng số partitions, cùng key)
   
   Use case: enrich events with reference data

   KStream<String, EnrichedOrder> enriched = orders
       .join(
           customerTable,            // KTable
           (order, customer) ->      // joiner
               new EnrichedOrder(order, customer),
           Joined.with(Serdes.String(), orderSerde, customerSerde)
       );


2. STREAM-STREAM JOIN:
   KStream<K,V1> + KStream<K,V2> → KStream<K,VR>
   
   - INNER, LEFT, OUTER JOIN
   - REQUIRE: time window (2 events phải xảy ra trong X thời gian)
   - Cả 2 streams buffered trong state store
   - REQUIRE: co-partitioned
   
   Use case: correlate events (order + payment, click + purchase)

   KStream<String, OrderPayment> orderPayments = orders
       .join(
           payments,                              // other stream
           (order, payment) ->                     // joiner
               new OrderPayment(order, payment),
           JoinWindows.ofTimeDifferenceAndGrace(
               Duration.ofMinutes(10),             // join window
               Duration.ofMinutes(5)),             // grace period
           StreamJoined.with(Serdes.String(), orderSerde, paymentSerde)
       );


3. TABLE-TABLE JOIN:
   KTable<K,V1> + KTable<K,V2> → KTable<K,VR>
   
   - Result cập nhật KHI BẤT KỲ bên nào thay đổi
   - REQUIRE: co-partitioned (trừ foreign key join)
   
   Use case: materialized views combining 2 tables

   KTable<String, UserWithAddress> usersWithAddress = 
       userTable.join(
           addressTable,
           (user, address) -> new UserWithAddress(user, address)
       );
```

```
CO-PARTITIONING REQUIREMENT:

  Để join 2 streams/tables, CẢ 2 PHẢI:
  1. Cùng số partitions
  2. Cùng partitioning strategy (key)
  3. Producer gửi cùng key → cùng partition number

  ┌───────────────────────────────────────────────────┐
  │ ĐÚNG — Co-partitioned:                             │
  │                                                   │
  │  orders (4 partitions, key=customerId):           │
  │  P0: CUST-001, CUST-005    P1: CUST-002, CUST-006│
  │  P2: CUST-003              P3: CUST-004           │
  │                                                   │
  │  customers (4 partitions, key=customerId):        │
  │  P0: CUST-001, CUST-005    P1: CUST-002, CUST-006│
  │  P2: CUST-003              P3: CUST-004           │
  │                                                   │
  │  → Instance xử lý P0 có CẢ order VÀ customer     │
  │    cho CUST-001 → join locally!                   │
  └───────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────┐
  │ SAI — KHÔNG co-partitioned:                        │
  │                                                   │
  │  orders (4 partitions, key=orderId):              │
  │  P0: ORD-001              P1: ORD-002             │
  │                                                   │
  │  customers (3 partitions, key=customerId):        │
  │  P0: CUST-001             P1: CUST-002            │
  │                                                   │
  │  → Số partitions khác nhau!                       │
  │  → Key khác nhau (orderId vs customerId)!         │
  │  → Kafka Streams THROW TopologyException           │
  └───────────────────────────────────────────────────┘

  FIX: 
  - Dùng selectKey() + repartition để align keys
  - Hoặc dùng GlobalKTable (no co-partitioning needed, nhưng full copy)
```

### 4.4 Interactive Queries

#### WHY — Query State từ bên ngoài

```
PROBLEM:
  Kafka Streams app tính real-time revenue per category
  Frontend muốn hiển thị dashboard
  
  Without Interactive Queries:
  ┌─────────┐     ┌──────────┐     ┌──────┐     ┌──────────┐
  │ Streams  │────►│ Output   │────►│ DB   │────►│ Frontend │
  │ App      │     │ Topic    │     │      │     │ (poll DB)│
  └─────────┘     └──────────┘     └──────┘     └──────────┘
  
  → Thêm consumer để đọc output topic → write to DB → query DB
  → Thêm 2 hops, thêm infra (DB), thêm latency

  With Interactive Queries:
  ┌─────────────────────────────┐
  │        Streams App           │
  │                             │
  │  ┌────────────────────────┐ │     ┌──────────┐
  │  │  State Store (RocksDB)  │◄─────│ REST API │◄── Frontend
  │  │  revenue-store          │ │     │ (embedded)│
  │  └────────────────────────┘ │     └──────────┘
  └─────────────────────────────┘

  → Query STATE STORE trực tiếp trên instance đang giữ partition đó
  → Latency local thường thấp, nhưng query từ frontend cần REST endpoint + metadata forwarding
  → Lab hôm nay chỉ demo local query từ trong process; production service cần expose API riêng
```

#### HOW — Interactive Queries Code

```java
// Query local state store
ReadOnlyKeyValueStore<String, Double> revenueStore = 
    streams.store(
        StoreQueryParameters.fromNameAndType(
            "revenue-store",
            QueryableStoreTypes.keyValueStore()
        )
    );

// Get single key
Double electronicsRevenue = revenueStore.get("Electronics");

// Iterate all entries
try (KeyValueIterator<String, Double> iter = revenueStore.all()) {
    while (iter.hasNext()) {
        KeyValue<String, Double> entry = iter.next();
        System.out.printf("%s: $%.2f%n", entry.key, entry.value);
    }
}

// Windowed store query
ReadOnlyWindowStore<String, Double> windowStore =
    streams.store(
        StoreQueryParameters.fromNameAndType(
            "hourly-revenue-store",
            QueryableStoreTypes.windowStore()
        )
    );

// Query specific window range
Instant from = Instant.now().minus(Duration.ofHours(2));
Instant to = Instant.now();
try (WindowStoreIterator<Double> iter = 
        windowStore.fetch("Electronics", from, to)) {
    while (iter.hasNext()) {
        KeyValue<Long, Double> entry = iter.next();
        System.out.printf("Window %s: $%.2f%n",
            Instant.ofEpochMilli(entry.key), entry.value);
    }
}
```

```
INTERACTIVE QUERIES — MULTI-INSTANCE:

  Vấn đề: State store partitioned across instances
  
  Instance 1 (P0, P1):           Instance 2 (P2, P3):
  ┌───────────────────┐          ┌───────────────────┐
  │ revenue-store      │          │ revenue-store      │
  │ Electronics: $300  │          │ Books: $50         │
  │ Food: $150         │          │ Home: $200         │
  └───────────────────┘          └───────────────────┘

  Query "Books" → gửi đến Instance 1 → KHÔNG CÓ!
  
  Solution: Metadata API
  
  // Tìm instance nào hold key
  StreamsMetadata metadata = streams.queryMetadataForKey(
      "revenue-store",
      "Books",
      Serdes.String().serializer()
  );
  
  if (metadata.equals(StreamsMetadata.NOT_AVAILABLE)) {
      // store đang rebalancing
  } else {
      HostInfo host = metadata.hostInfo();
      if (isLocal(host)) {
          // query local store
      } else {
          // forward to remote instance via HTTP
          httpClient.get("http://" + host.host() + ":" + host.port() 
              + "/api/revenue/Books");
      }
  }
  
  config: application.server = "host:port"
  → Kafka Streams broadcast instance location qua consumer group
```

### 4.5 Exactly-Once Processing trong Kafka Streams

```
EXACTLY-ONCE trong Kafka Streams = TRANSACTIONS:

  Read-Process-Write pattern (atomic):
  
  ┌─────────────────────────────────────────────┐
  │              Kafka Transaction               │
  │                                             │
  │  1. Read input records (consumer)           │
  │  2. Process (update state store)            │
  │  3. Write output records (producer)         │
  │  4. Write changelog (state backup)          │
  │  5. Commit consumer offsets                 │
  │                                             │
  │  ALL or NOTHING — atomic!                   │
  └─────────────────────────────────────────────┘

  Config:
  props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, 
      StreamsConfig.EXACTLY_ONCE_V2);  // Kafka 2.6+
  
  // EXACTLY_ONCE_V2 (recommended):
  // - 1 transactional producer per StreamThread
  // - Ít overhead hơn v1
  // - Require broker version ≥ 2.5
  
  // EXACTLY_ONCE (v1, deprecated):
  // - 1 transactional producer per StreamTask
  // - Nhiều overhead hơn

  Scope quan trọng:
  - Bao phủ Kafka input offsets, Kafka output topics, changelog topics và state store restore.
  - KHÔNG làm external side effects exactly-once: HTTP call, email, database write ngoài Kafka vẫn cần idempotency key, inbox/outbox hoặc transaction riêng.
  - Với lab single broker/RF=1, EOS không bảo vệ khỏi mất data nếu broker disk mất.

  Trade-off:
  - Throughput giảm ~20-30% so với AT_LEAST_ONCE
  - Latency tăng ~50-100ms (transaction overhead)
  - Nhưng đảm bảo state store + output topic + offsets consistent
```

---

## 5. Trade-off Analysis

### Window Type Selection

| Tiêu chí | Tumbling | Hopping | Session |
|----------|---------|---------|---------|
| Window size | Fixed | Fixed | Dynamic |
| Overlap | Không | Có | Có thể |
| Records/window | 1 window per event | N windows per event | 1 session per key |
| State store size | Nhỏ nhất | Size × (size/advance) | Unpredictable |
| Memory | Thấp | Cao (nhiều overlapping windows) | Phụ thuộc gap |
| Use case | Reports, billing | Moving averages, alerts | User sessions |
| Complexity | Thấp | Trung bình | Cao (merge logic) |

### Join Type Selection

| Scenario | Join Type | Tại sao |
|----------|-----------|---------|
| Enrich order với customer profile | Stream-Table | Customer = slow-changing reference data |
| Correlate order + payment | Stream-Stream | 2 independent event streams, time-bounded |
| Combine user + address tables | Table-Table | 2 tables update independently |
| Enrich với small config data | Stream-GlobalKTable | Config nhỏ, cần trên mọi instance |
| Order + product từ khác key | Foreign Key Join | Key mismatch giữa 2 bên |

### State Store Configurations

| Config | Default | Ảnh hưởng |
|--------|---------|-----------|
| cache.max.bytes.buffering | 10MB | Tăng → batch lớn hơn → throughput↑ latency↑ |
| commit.interval.ms | 30000 | Giảm → commit/output flush thường hơn, duplicate/replay window nhỏ hơn → throughput↓ |
| num.standby.replicas | 0 | Tăng → recovery nhanh hơn → disk/network↑ |
| state.dir | /tmp/kafka-streams | Production: dùng dedicated SSD |
| rocksdb.config.setter | None | Tuning RocksDB cho workload cụ thể |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. Window + Grace Period cho mọi windowed aggregation
   → Grace period quá ngắn → mất late events
   → Grace period quá dài → emit results chậm
   → Rule of thumb: grace = 10-20% window size
   → Ví dụ: 1h window → 5-10 phút grace

2. Dùng Suppress để tránh intermediate results
   hourlyRevenue
       .suppress(Suppressed.untilWindowCloses(
           Suppressed.BufferConfig.unbounded()))
       .toStream()
       .to("final-hourly-revenue");
   → Chỉ emit FINAL result sau khi window đóng
   → Trade-off: latency tăng (chờ window close + grace)

3. Co-partitioning: đảm bảo TRƯỚC khi join
   → Check: kafka-topics --describe → num.partitions phải khớp
   → Key phải cùng type + cùng partitioner
   → Nếu không khớp → selectKey() + repartition TRƯỚC join

4. num.standby.replicas = 1 cho production
   → Recovery time: từ phút → giây
   → Cost: x2 state store disk, thêm changelog consumption

5. State store directory trên SSD
   state.dir = /data/kafka-streams  (SSD mount)
   → RocksDB performance phụ thuộc disk I/O
   → HDD → bottleneck cho stateful operations

6. Monitor state store size
   → RocksDB có thể grow lớn (especially windowed stores)
   → Set retention cho windowed stores
   → Alert khi disk usage > 80%
```

### Common Pitfalls

```
❌ PITFALL 1: Quên grace period → window đóng ngay → mất late events
   Sai:  TimeWindows.ofSizeWithNoGrace(Duration.ofHours(1))
   Đúng: TimeWindows.ofSizeAndGrace(Duration.ofHours(1), Duration.ofMinutes(5))

❌ PITFALL 2: Session window gap quá ngắn / quá dài
   Gap = 1 phút → quá nhiều sessions, không meaningful
   Gap = 24 giờ → 1 session khổng lồ, vô nghĩa
   → Phân tích user behavior để chọn gap phù hợp
   → Web apps: 30 phút (similar to Google Analytics)
   → Mobile apps: 5-15 phút

❌ PITFALL 3: Join mà quên co-partitioning
   orders topic: 6 partitions, key=orderId
   customers topic: 4 partitions, key=customerId
   orders.join(customers, ...) → TopologyException!
   
   Fix: tạo lại topics cùng partition count OR dùng GlobalKTable

❌ PITFALL 4: Stream-stream join window quá rộng
   JoinWindows.ofTimeDifferenceWithNoGrace(Duration.ofDays(7))
   → Buffer 7 ngày data trong state store → OOM!
   → Keep join window nhỏ nhất có thể (phút, không phải ngày)

❌ PITFALL 5: Interactive queries khi state = REBALANCING
   streams.store(...) → InvalidStateStoreException!
   → Always check: streams.state() == RUNNING trước khi query
   → Wrap trong try-catch, retry hoặc return 503

❌ PITFALL 6: Aggregate với stateful side effects
   .aggregate(() -> 0.0,
       (key, order, total) -> {
           db.update(key, total);  // SIDE EFFECT!
           return total + order.getAmount();
       })
   → Aggregate có thể replay → side effect chạy nhiều lần
   → Keep aggregator PURE (no I/O, no side effects)
```

---

## 7. Performance Considerations

### Stateful Operations Performance

```
Benchmark (single instance, 4 cores, 16GB RAM):

  Simple count/aggregate:
  - Throughput: 30K-50K msg/s
  - Latency (p99): ~50-200ms
  - State store: ~100MB per 1M unique keys

  Windowed aggregate (1h tumbling):
  - Throughput: 20K-40K msg/s
  - Latency (p99): ~100-500ms
  - State store: window_count × unique_keys × value_size

  Stream-table join:
  - Throughput: 40K-80K msg/s (table lookup = local RocksDB read)
  - Latency: ~10-50ms per join

  Stream-stream join (10min window):
  - Throughput: 15K-30K msg/s (2 state stores!)
  - Latency (p99): ~200-500ms
  - State store: 2 × window_size × event_rate × avg_size

KEY TUNING:

  cache.max.bytes.buffering = 10MB → 50MB
  → Larger cache → fewer writes to RocksDB
  → Throughput↑ 20-40%, latency↑ proportionally

  commit.interval.ms = 30000 → 100
  → More frequent commits → smaller replay/duplicate window
  → Throughput↓ 10-20% (more transaction overhead)

  RocksDB tuning:
  props.put(StreamsConfig.ROCKSDB_CONFIG_SETTER_CLASS_CONFIG,
      CustomRocksDBConfig.class);
  
  class CustomRocksDBConfig implements RocksDBConfigSetter {
      @Override
      public void setConfig(String storeName, Options options, 
                            Map<String, Object> configs) {
          // Block cache for reads
          BlockBasedTableConfig tableConfig = new BlockBasedTableConfig();
          tableConfig.setBlockCache(new LRUCache(64 * 1024 * 1024)); // 64MB
          tableConfig.setBlockSize(16 * 1024); // 16KB blocks
          options.setTableFormatConfig(tableConfig);
          
          // Write buffer
          options.setWriteBufferSize(16 * 1024 * 1024); // 16MB
          options.setMaxWriteBufferNumber(3);
          
          // Compaction
          options.setMaxBackgroundCompactions(4);
      }
  }
```

### Monitoring cho Stateful Processing

```
Critical metrics (thêm vào Day 18):

  State store metrics:
  - put-rate                    → write rate to state store
  - get-rate                    → read rate from state store
  - all-rate                    → range scan rate
  - flush-rate                  → RocksDB flush rate
  - restore-rate                → state restoration rate (after rebalance)
  - restore-remaining-records   → records left to restore

  Windowed processing:
  - expired-window-record-drop-rate  → records dropped (past grace)
  - late-record-drop-rate            → late records dropped

  Join metrics:
  - join-rate                   → successful joins/s
  - skipped-records-rate        → records that couldn't join

Alert thresholds:
  - restore-remaining-records > 1M    → long recovery, standby giúp
  - expired-window-record-drop-rate > 100/s → grace period quá ngắn
  - flush-rate spike                  → disk I/O bottleneck
  - put-latency-avg > 10ms           → RocksDB slow, kiểm tra disk
```

---

## 8. Hands-on Lab

### 8.1 Setup — Mở rộng Project từ Day 18

```yaml
# docker-compose.yml (KRaft baseline, mở rộng từ Day 18 setup)
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

# Create topics cho lab
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create --topic orders --partitions 4 --replication-factor 1 --if-not-exists
  kafka-topics --bootstrap-server localhost:9092 --create --topic payments --partitions 4 --replication-factor 1 --if-not-exists
  kafka-topics --bootstrap-server localhost:9092 --create --topic customers --partitions 4 --replication-factor 1 --config cleanup.policy=compact --if-not-exists
  kafka-topics --bootstrap-server localhost:9092 --create --topic hourly-revenue --partitions 4 --replication-factor 1 --if-not-exists
  kafka-topics --bootstrap-server localhost:9092 --create --topic enriched-orders --partitions 4 --replication-factor 1 --if-not-exists
  kafka-topics --bootstrap-server localhost:9092 --create --topic order-payment-matched --partitions 4 --replication-factor 1 --if-not-exists
"
```

### 8.2 Data Models

```java
// src/main/java/com/example/stateful/Customer.java
package com.example.stateful;

public class Customer {
    private String customerId;
    private String name;
    private String tier;   // Bronze, Silver, Gold, Platinum
    private String region;
    private String email;

    public Customer() {}

    public Customer(String customerId, String name, String tier, 
                    String region, String email) {
        this.customerId = customerId;
        this.name = name;
        this.tier = tier;
        this.region = region;
        this.email = email;
    }

    public String getCustomerId() { return customerId; }
    public String getName() { return name; }
    public String getTier() { return tier; }
    public String getRegion() { return region; }
    public String getEmail() { return email; }

    @Override
    public String toString() {
        return String.format("Customer{id=%s, name=%s, tier=%s, region=%s}",
                customerId, name, tier, region);
    }
}
```

```java
// src/main/java/com/example/stateful/Payment.java
package com.example.stateful;

public class Payment {
    private String paymentId;
    private String orderId;
    private double amount;
    private String method;
    private String status;
    private long paidAt;

    public Payment() {}

    public Payment(String paymentId, String orderId, double amount,
                   String method, String status, long paidAt) {
        this.paymentId = paymentId;
        this.orderId = orderId;
        this.amount = amount;
        this.method = method;
        this.status = status;
        this.paidAt = paidAt;
    }

    public String getPaymentId() { return paymentId; }
    public String getOrderId() { return orderId; }
    public double getAmount() { return amount; }
    public String getMethod() { return method; }
    public String getStatus() { return status; }
    public long getPaidAt() { return paidAt; }

    @Override
    public String toString() {
        return String.format("Payment{id=%s, orderId=%s, amount=%.2f, method=%s, status=%s}",
                paymentId, orderId, amount, method, status);
    }
}
```

```java
// src/main/java/com/example/stateful/EnrichedOrder.java
package com.example.stateful;

import com.example.Order;

public class EnrichedOrder {
    private String orderId;
    private String customerId;
    private String customerName;
    private String customerTier;
    private String category;
    private double amount;
    private String region;

    public EnrichedOrder() {}

    public EnrichedOrder(Order order, Customer customer) {
        this.orderId = order.getOrderId();
        this.customerId = order.getCustomerId();
        this.customerName = customer.getName();
        this.customerTier = customer.getTier();
        this.category = order.getCategory();
        this.amount = order.getAmount();
        this.region = customer.getRegion();
    }

    public String getOrderId() { return orderId; }
    public String getCustomerId() { return customerId; }
    public String getCustomerName() { return customerName; }
    public String getCustomerTier() { return customerTier; }
    public String getCategory() { return category; }
    public double getAmount() { return amount; }
    public String getRegion() { return region; }

    @Override
    public String toString() {
        return String.format("EnrichedOrder{id=%s, customer=%s(%s), category=%s, amount=%.2f}",
                orderId, customerName, customerTier, category, amount);
    }
}
```

```java
// src/main/java/com/example/stateful/OrderPaymentMatch.java
package com.example.stateful;

import com.example.Order;

public class OrderPaymentMatch {
    private String orderId;
    private double orderAmount;
    private double paymentAmount;
    private String paymentMethod;
    private boolean amountMatch;
    private long orderTime;
    private long paymentTime;
    private long latencyMs;

    public OrderPaymentMatch() {}

    public OrderPaymentMatch(Order order, Payment payment) {
        this.orderId = order.getOrderId();
        this.orderAmount = order.getAmount();
        this.paymentAmount = payment.getAmount();
        this.paymentMethod = payment.getMethod();
        this.amountMatch = Math.abs(order.getAmount() - payment.getAmount()) < 0.01;
        this.orderTime = order.getCreatedAt();
        this.paymentTime = payment.getPaidAt();
        this.latencyMs = payment.getPaidAt() - order.getCreatedAt();
    }

    public String getOrderId() { return orderId; }
    public boolean isAmountMatch() { return amountMatch; }
    public long getLatencyMs() { return latencyMs; }

    @Override
    public String toString() {
        return String.format(
            "OrderPaymentMatch{order=%s, orderAmt=%.2f, payAmt=%.2f, match=%b, latency=%dms}",
            orderId, orderAmount, paymentAmount, amountMatch, latencyMs);
    }
}
```

### 8.3 Stateful Processing App — Revenue + Join + Windowing

```java
// src/main/java/com/example/stateful/StatefulProcessingApp.java
package com.example.stateful;

import com.example.JsonSerde;
import com.example.Order;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.*;
import org.apache.kafka.streams.kstream.*;
import org.apache.kafka.streams.state.*;

import java.time.Duration;
import java.time.Instant;
import java.util.Properties;
import java.util.concurrent.CountDownLatch;

public class StatefulProcessingApp {

    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "stateful-processing-v1");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.EXACTLY_ONCE_V2);
        props.put(StreamsConfig.COMMIT_INTERVAL_MS_CONFIG, 1000);
        props.put(StreamsConfig.NUM_STREAM_THREADS_CONFIG, 2);
        // Interactive queries: expose instance endpoint
        props.put(StreamsConfig.APPLICATION_SERVER_CONFIG, "localhost:7070");
        // State store directory
        props.put(StreamsConfig.STATE_DIR_CONFIG, "/tmp/kafka-streams-stateful");
        // Standby replica for faster recovery
        props.put(StreamsConfig.NUM_STANDBY_REPLICAS_CONFIG, 0);

        Topology topology = buildTopology();
        System.out.println("=== Topology ===");
        System.out.println(topology.describe());

        KafkaStreams streams = new KafkaStreams(topology, props);

        CountDownLatch latch = new CountDownLatch(1);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            streams.close(Duration.ofSeconds(30));
            latch.countDown();
        }));

        streams.setStateListener((newState, oldState) ->
            System.out.printf("State: %s → %s%n", oldState, newState));

        streams.setUncaughtExceptionHandler(ex -> {
            System.err.printf("Uncaught: %s%n", ex.getMessage());
            return StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.REPLACE_THREAD;
        });

        try {
            streams.start();

            // Wait for RUNNING state before starting interactive queries
            while (streams.state() != KafkaStreams.State.RUNNING) {
                Thread.sleep(100);
            }
            System.out.println("Streams app RUNNING. Interactive queries available.");

            // Demo: periodically query state stores
            new Thread(() -> queryStateStores(streams), "query-thread").start();

            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    static Topology buildTopology() {
        StreamsBuilder builder = new StreamsBuilder();
        JsonSerde<Order> orderSerde = new JsonSerde<>(Order.class);
        JsonSerde<Customer> customerSerde = new JsonSerde<>(Customer.class);
        JsonSerde<Payment> paymentSerde = new JsonSerde<>(Payment.class);
        JsonSerde<EnrichedOrder> enrichedSerde = new JsonSerde<>(EnrichedOrder.class);
        JsonSerde<OrderPaymentMatch> matchSerde = new JsonSerde<>(OrderPaymentMatch.class);

        // === SOURCE STREAMS ===

        // Orders stream (key = orderId)
        KStream<String, Order> orders = builder.stream(
                "orders", Consumed.with(Serdes.String(), orderSerde));

        // Payments stream (key = orderId for co-partitioning)
        KStream<String, Payment> payments = builder.stream(
                "payments", Consumed.with(Serdes.String(), paymentSerde));

        // Customers table (key = customerId, compacted topic)
        KTable<String, Customer> customers = builder.table(
                "customers", Consumed.with(Serdes.String(), customerSerde),
                Materialized.as("customer-store"));

        // === 1. WINDOWED AGGREGATION: Hourly Revenue per Category ===

        KStream<String, Order> paidOrders = orders
                .filter((key, order) -> "PAID".equals(order.getStatus()));

        KTable<Windowed<String>, Double> hourlyRevenue = paidOrders
                .groupBy(
                    (key, order) -> order.getCategory(),
                    Grouped.with(Serdes.String(), orderSerde))
                .windowedBy(TimeWindows.ofSizeAndGrace(
                        Duration.ofHours(1),       // hourly windows
                        Duration.ofMinutes(5)))    // 5-min grace
                .aggregate(
                    () -> 0.0,
                    (category, order, totalRevenue) -> totalRevenue + order.getAmount(),
                    Materialized.<String, Double, WindowStore<Bytes, byte[]>>as(
                        "hourly-revenue-store")
                        .withKeySerde(Serdes.String())
                        .withValueSerde(Serdes.Double())
                );

        hourlyRevenue
                .toStream()
                .peek((windowedKey, revenue) ->
                    System.out.printf("[REVENUE] category=%s window=[%s-%s] total=$%.2f%n",
                        windowedKey.key(),
                        Instant.ofEpochMilli(windowedKey.window().startTime().toEpochMilli()),
                        Instant.ofEpochMilli(windowedKey.window().endTime().toEpochMilli()),
                        revenue))
                .map((windowedKey, revenue) -> KeyValue.pair(
                    windowedKey.key(),
                    String.format("{\"category\":\"%s\",\"window_start\":%d,\"window_end\":%d,\"revenue\":%.2f}",
                        windowedKey.key(),
                        windowedKey.window().startTime().toEpochMilli(),
                        windowedKey.window().endTime().toEpochMilli(),
                        revenue)))
                .to("hourly-revenue", Produced.with(Serdes.String(), Serdes.String()));

        // === 2. COUNT: Orders per Customer ===

        KTable<String, Long> ordersPerCustomer = paidOrders
                .groupBy(
                    (key, order) -> order.getCustomerId(),
                    Grouped.with(Serdes.String(), orderSerde))
                .count(Materialized.as("orders-per-customer-store"));

        ordersPerCustomer
                .toStream()
                .peek((customerId, count) ->
                    System.out.printf("[COUNT] customer=%s orders=%d%n", customerId, count))
                .mapValues(count -> count.toString())
                .to("orders-per-customer",
                    Produced.with(Serdes.String(), Serdes.String()));

        // === 3. STREAM-TABLE JOIN: Enrich orders with customer data ===

        // Re-key orders by customerId for join (triggers repartition)
        KStream<String, Order> ordersByCustomer = paidOrders
                .selectKey((key, order) -> order.getCustomerId());

        KStream<String, EnrichedOrder> enrichedOrders = ordersByCustomer
                .join(
                    customers,
                    (order, customer) -> new EnrichedOrder(order, customer),
                    Joined.with(Serdes.String(), orderSerde, customerSerde)
                );

        enrichedOrders
                .peek((key, enriched) ->
                    System.out.printf("[ENRICHED] %s%n", enriched))
                .selectKey((key, enriched) -> enriched.getOrderId())
                .to("enriched-orders",
                    Produced.with(Serdes.String(), enrichedSerde));

        // === 4. STREAM-STREAM JOIN: Match orders with payments ===

        KStream<String, OrderPaymentMatch> matched = orders
                .join(
                    payments,
                    (order, payment) -> new OrderPaymentMatch(order, payment),
                    JoinWindows.ofTimeDifferenceAndGrace(
                        Duration.ofMinutes(10),   // order and payment within 10 min
                        Duration.ofMinutes(2)),   // grace for late events
                    StreamJoined.with(Serdes.String(), orderSerde, paymentSerde)
                );

        matched
                .peek((key, match) ->
                    System.out.printf("[MATCHED] %s%n", match))
                .to("order-payment-matched",
                    Produced.with(Serdes.String(), matchSerde));

        return builder.build();
    }

    static void queryStateStores(KafkaStreams streams) {
        try {
            Thread.sleep(5000); // wait for some data

            // Query revenue store
            ReadOnlyWindowStore<String, Double> revenueStore =
                streams.store(StoreQueryParameters.fromNameAndType(
                    "hourly-revenue-store",
                    QueryableStoreTypes.windowStore()));

            System.out.println("\n=== Interactive Query: Revenue Store ===");
            Instant from = Instant.now().minus(Duration.ofHours(1));
            Instant to = Instant.now().plus(Duration.ofHours(1));
            try (var iter = revenueStore.fetchAll(from, to)) {
                while (iter.hasNext()) {
                    var kv = iter.next();
                    System.out.printf("  [%s] %s = $%.2f%n",
                        Instant.ofEpochMilli(kv.key.window().startTime().toEpochMilli()),
                        kv.key.key(), kv.value);
                }
            }

            // Query orders per customer
            ReadOnlyKeyValueStore<String, Long> countStore =
                streams.store(StoreQueryParameters.fromNameAndType(
                    "orders-per-customer-store",
                    QueryableStoreTypes.keyValueStore()));

            System.out.println("\n=== Interactive Query: Orders per Customer ===");
            try (var iter = countStore.all()) {
                while (iter.hasNext()) {
                    var kv = iter.next();
                    System.out.printf("  %s = %d orders%n", kv.key, kv.value);
                }
            }

        } catch (Exception e) {
            System.err.printf("Query failed: %s%n", e.getMessage());
        }
    }
}
```

### 8.4 Test Data Producers

```java
// src/main/java/com/example/stateful/TestDataProducer.java
package com.example.stateful;

import com.example.Order;
import com.google.gson.Gson;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

public class TestDataProducer {
    private static final Gson gson = new Gson();

    public static void main(String[] args) throws Exception {
        Properties props = new Properties();
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);

        try (Producer<String, String> producer = new KafkaProducer<>(props)) {

            // 1. Seed customers (KTable data)
            String[][] customers = {
                {"CUST-001", "Alice", "Gold", "US-WEST", "alice@example.com"},
                {"CUST-002", "Bob", "Silver", "EU-WEST", "bob@example.com"},
                {"CUST-003", "Charlie", "Platinum", "APAC", "charlie@example.com"},
                {"CUST-004", "Diana", "Bronze", "US-EAST", "diana@example.com"},
                {"CUST-005", "Eve", "Gold", "EU-WEST", "eve@example.com"},
            };

            System.out.println("--- Seeding Customers ---");
            for (String[] c : customers) {
                Customer customer = new Customer(c[0], c[1], c[2], c[3], c[4]);
                producer.send(new ProducerRecord<>("customers", c[0], gson.toJson(customer))).get();
                System.out.printf("Customer: %s (%s, %s)%n", c[0], c[1], c[2]);
            }
            producer.flush();
            Thread.sleep(2000); // Let KTable build

            // 2. Generate orders + payments
            String[] categories = {"Electronics", "Clothing", "Food", "Books", "Home"};
            String[] statuses = {"PAID", "PAID", "PAID", "CREATED"}; // 75% PAID
            String[] payMethods = {"CARD", "PAYPAL", "BANK_TRANSFER"};
            ThreadLocalRandom rand = ThreadLocalRandom.current();

            System.out.println("\n--- Generating Orders + Payments ---");
            for (int i = 0; i < 30; i++) {
                String orderId = "ORD-" + String.format("%04d", i + 1);
                String customerId = "CUST-" + String.format("%03d", rand.nextInt(1, 6));
                String status = statuses[rand.nextInt(statuses.length)];
                double amount = Math.round(rand.nextDouble(10, 3000) * 100.0) / 100.0;
                long now = System.currentTimeMillis();

                Order order = new Order(
                    orderId, customerId,
                    categories[rand.nextInt(categories.length)],
                    amount, "USD", status, now,
                    customers[rand.nextInt(customers.length)][3]);

                // Send order (key = orderId for stream-stream join)
                producer.send(new ProducerRecord<>("orders", orderId, gson.toJson(order)));
                System.out.printf("Order: %s customer=%s amount=$%.2f status=%s%n",
                    orderId, customerId, amount, status);

                // Send matching payment after short delay (simulate real flow)
                if ("PAID".equals(status)) {
                    Thread.sleep(rand.nextInt(100, 2000)); // 0.1-2s delay

                    Payment payment = new Payment(
                        "PAY-" + UUID.randomUUID().toString().substring(0, 8),
                        orderId, amount,
                        payMethods[rand.nextInt(payMethods.length)],
                        "COMPLETED",
                        System.currentTimeMillis());

                    producer.send(new ProducerRecord<>("payments", orderId, gson.toJson(payment)));
                    System.out.printf("  Payment: %s for %s method=%s%n",
                        payment.getPaymentId(), orderId, payment.getMethod());
                }

                Thread.sleep(rand.nextInt(200, 800));
            }
        }

        System.out.println("\nProducer finished. 30 orders + payments sent.");
    }
}
```

### 8.5 Run và Verify

```bash
# Terminal 1: Start stateful processing app
./gradlew run -PmainClass=com.example.stateful.StatefulProcessingApp

# Terminal 2: Send test data
./gradlew run -PmainClass=com.example.stateful.TestDataProducer

# Terminal 3: Consume enriched orders
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic enriched-orders \
  --from-beginning

# Terminal 4: Consume matched order-payments
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-payment-matched \
  --from-beginning

# Terminal 5: Check hourly revenue
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic hourly-revenue \
  --from-beginning

# Check internal topics created by Kafka Streams
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server localhost:9092 --list | grep stateful
# Expect:
#   stateful-processing-v1-hourly-revenue-store-changelog
#   stateful-processing-v1-orders-per-customer-store-changelog
#   stateful-processing-v1-KSTREAM-KEY-SELECT-...-repartition
```

### 8.6 Failure Scenario — State Recovery

```bash
# 1. Chạy app và produce data (đã làm ở trên)

# 2. Kill app đột ngột (simulate crash)
# Ctrl+C trong Terminal 1

# 3. Check state directory
ls -la /tmp/kafka-streams-stateful/stateful-processing-v1/

# 4. Delete local state (simulate data loss)
rm -rf /tmp/kafka-streams-stateful/stateful-processing-v1/

# 5. Restart app
./gradlew run -PmainClass=com.example.stateful.StatefulProcessingApp

# Observe:
# - App replays changelog topics to rebuild state stores
# - After restoration, interactive queries return same data
# - No state loss trong phạm vi Kafka nếu input/changelog topics còn nguyên
# - Lab đang RF=1: broker disk mất thì vẫn mất data; production dùng RF>=3 + min.insync.replicas>=2

# 6. Check restoration in logs:
# "State changed: REBALANCING → RUNNING"
# Restoration time depends on changelog size
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **RocksDB state store bị mất (disk failure). Kafka Streams recovery process hoạt động thế nào? Mất bao lâu nếu changelog topic có 10 triệu records?**
   - Hint: changelog topic replay, compacted topic, standby replicas.

2. **Tumbling window 1 giờ, grace period 5 phút. Event có event_time = 09:55 đến lúc 10:06 wall clock. Event này có được xử lý không?**
   - Hint: không đủ thông tin nếu chỉ biết wall clock. Cần biết stream-time của task đã vượt 10:05 hay chưa.

3. **Stream-stream join yêu cầu co-partitioning. Bạn có 2 topics: `orders` (key=orderId, 8 partitions) và `payments` (key=paymentId, 6 partitions). Làm sao để join?**
   - Hint: selectKey() + repartition, hoặc tạo lại topics.

4. **Session window với gap = 30 phút. User A có events lúc 09:00, 09:20, 09:55, 10:30. Có bao nhiêu sessions?**
   - Hint: 09:00→09:20 (gap=20 < 30 OK), 09:20→09:55 (gap=35 > 30 NEW SESSION), 09:55→10:30 (gap=35 > 30 NEW SESSION).

5. **Interactive Queries trên multi-instance deployment (3 instances). Client query key "Electronics" nhưng key này nằm trên instance 2. Làm sao forward request?**
   - Hint: StreamsMetadata API, application.server config.

6. **EXACTLY_ONCE_V2 giảm throughput ~20-30%. Trong scenario nào bạn chấp nhận AT_LEAST_ONCE thay vì EXACTLY_ONCE?**
   - Hint: idempotent downstream, throughput critical, aggregation mà double-count acceptable.

7. **Hopping window (size=1h, advance=10min) tạo bao nhiêu windows chứa 1 event? Ảnh hưởng đến state store size thế nào?**
   - Hint: 1h / 10min = 6 windows per event. State store size = 6× so với tumbling window.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Streams Developer Guide — Stateful Transformations](https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html#stateful-transformations)
- [Kafka Streams Architecture — State](https://docs.confluent.io/platform/current/streams/architecture.html#state)
- [Interactive Queries](https://kafka.apache.org/documentation/streams/developer-guide/interactive-queries.html)
- [Windowing](https://kafka.apache.org/documentation/streams/developer-guide/dsl-api.html#windowing)

### Blog Posts & Articles
- [Confluent — Kafka Streams Interactive Queries](https://www.confluent.io/blog/unifying-stream-processing-and-interactive-queries-in-apache-kafka/)
- [Confluent — Windowing in Kafka Streams](https://developer.confluent.io/courses/kafka-streams/windowing/)
- [Confluent — State Stores in Kafka Streams](https://docs.confluent.io/platform/current/streams/developer-guide/processor-api.html#state-stores)
- [Uber Engineering — Real-time Exactly-Once Event Processing](https://www.uber.com/blog/real-time-exactly-once-ad-event-processing/)

### Videos & Talks
- [Kafka Summit — Stateful Stream Processing with Kafka Streams](https://www.confluent.io/events/kafka-summit/)
- [Confluent Developer — Interactive Queries Tutorial](https://developer.confluent.io/courses/kafka-streams/hands-on-interactive-queries/)
- [GOTO Conference — Kafka Streams in Action](https://www.youtube.com/results?search_query=kafka+streams+stateful+processing)
