# Day 24: So sánh 3 Brokers Toàn Diện — Decision Matrix, Use Case Analysis & Polyglot Messaging

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** sự khác biệt kiến trúc giữa NATS, RabbitMQ, và Kafka — philosophy, trade-off, sweet spot của từng tool
2. **Nắm vững** decision matrix — chọn đúng broker cho đúng use case dựa trên tiêu chí cụ thể (throughput, ordering, replay, routing, latency)
3. **Thực hành** benchmark so sánh 3 brokers trên cùng workload — đo throughput, latency, resource usage
4. **Hiểu** khi nào KHÔNG dùng message broker, khi nào cần combine nhiều brokers (polyglot messaging)
5. **Biết** migration paths — khi nào nên chuyển đổi, cách migrate an toàn giữa các hệ thống

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 1-3 (NATS fundamentals, JetStream, production)
- Đã hoàn thành Day 4-9 (RabbitMQ: AMQP, exchanges, reliability, clustering)
- Đã hoàn thành Day 10-23 (Kafka: fundamentals → production operations)
- Hiểu core concepts: pub/sub, queue, stream, consumer group, replication, persistence
- Docker Compose để chạy cả 3 brokers

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Architecture philosophy comparison — 3 approaches khác nhau
- Feature comparison table — comprehensive side-by-side
- Decision matrix theo use case — event sourcing, task queue, log aggregation, request-reply, IoT, microservices
- Khi nào KHÔNG dùng message broker
- Hands-on: benchmark 3 brokers trên cùng workload

### 🟡 Should Learn (nếu còn thời gian)
- Polyglot messaging — combine nhiều brokers trong 1 hệ thống
- Migration paths — RabbitMQ → Kafka, strategies và pitfalls
- Real-world architecture examples — Uber, LinkedIn, Wealthsimple

### 🟢 Optional Deep Dive
- Cost analysis — TCO (Total Cost of Ownership) comparison
- Cloud-managed offerings — Amazon MSK, CloudAMQP, Synadia Cloud, Confluent Cloud
- Emerging alternatives — Pulsar, Redpanda, Memphis, NATS vs Kafka head-to-head in 2024+
- Build decision framework template cho team của bạn

---

## 4. Lý thuyết (Theory)

### 4.1 Architecture Philosophy — Ba trường phái tư duy

#### WHY — Tại sao có 3 tools khác nhau cho "cùng 1 vấn đề"?

```
BA PHILOSOPHY KHÁC NHAU:

  Chúng KHÔNG giải quyết cùng 1 vấn đề.
  Mỗi tool sinh ra từ một NHU CẦU khác nhau:


  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  NATS — "Simplicity is the ultimate sophistication"         │
  │  ├─ Sinh ra ở Apcera (2010), cloud-native messaging        │
  │  ├─ Philosophy: simple, fast, lightweight                   │
  │  ├─ Core: fire-and-forget pub/sub (at-most-once by default)│
  │  ├─ JetStream (2021): persistence, ack/replay, dedup window│
  │  ├─ Design: dumb broker, smart client                      │
  │  ├─ Sweet spot: cloud-native, low latency, IoT, edge       │
  │  └─ Analogy: "UDP cho messaging" (core NATS)               │
  │              "TCP cho messaging" (JetStream)                │
  │                                                             │
  │  RabbitMQ — "Smart broker, flexible routing"                │
  │  ├─ Sinh ra ở Pivotal/VMware (2007), AMQP protocol         │
  │  ├─ Philosophy: broker is smart, consumers are simple       │
  │  ├─ Core: message queuing với routing engine mạnh           │
  │  ├─ Design: exchange → binding → queue routing              │
  │  ├─ Sweet spot: task distribution, complex routing, RPC     │
  │  └─ Analogy: "Post office" — smart routing, guaranteed     │
  │              delivery, receiver mailbox                      │
  │                                                             │
  │  Kafka — "Distributed commit log for everything"            │
  │  ├─ Sinh ra ở LinkedIn (2011), distributed systems needs    │
  │  ├─ Philosophy: immutable log, consumers pull at own pace   │
  │  ├─ Core: append-only log, partitioned, replicated          │
  │  ├─ Design: dumb broker (storage), smart consumer (offset)  │
  │  ├─ Sweet spot: event streaming, log aggregation, CDC, ETL  │
  │  └─ Analogy: "Transaction log (WAL) as a service"          │
  │              Như database WAL nhưng cho inter-service comms  │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘
```

#### WHAT — Fundamental Architecture Differences

```
MESSAGE MODEL COMPARISON:

  ═══ NATS (Core) — Fire and Forget ═══
  
  Producer ──publish──► Subject: "orders.created"
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Subscriber1  Subscriber2  Subscriber3
              (all receive same message)
  
  → Message KHÔNG persist (core NATS)
  → Subscriber offline → MISS message
  → Ultra-low latency: ~200μs
  → Queue groups: load balance across subscribers
  
  
  ═══ NATS JetStream — Persistent Streaming ═══
  
  Producer ──publish──► Stream: "ORDERS"
                         [msg1][msg2][msg3][msg4]
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Consumer1    Consumer2   Consumer3
              (pull at own pace, ack, replay)
  
  → Messages PERSISTED in stream
  → Consumers can replay from any point
  → Consumer groups (durable consumers)
  → Closer to Kafka model but simpler API


  ═══ RabbitMQ — Exchange + Queue Routing ═══
  
  Producer ──publish──► Exchange ──routing──► Queue1 ──► Consumer1
                         (type:    key       Queue2 ──► Consumer2
                          topic)   match     Queue3 ──► Consumer3
  
  → Message ROUTED by broker (exchange logic)
  → Message consumed → REMOVED from queue
  → Consumer xử lý xong → ack → broker delete
  → NO replay after consumption (trừ khi dùng RabbitMQ Streams)
  → Rich routing: direct, fanout, topic, headers
  
  
  ═══ Kafka — Distributed Commit Log ═══
  
  Producer ──append──► Topic: "orders" (partition 0)
                         [offset 0][offset 1][offset 2][offset 3]
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              ConsumerA    ConsumerB   ConsumerC
              (offset=3)   (offset=1)  (offset=3)
              (real-time)  (catching up)(real-time)
  
  → Messages PERSIST theo retention policy (days/weeks/forever)
  → Multiple consumer groups đọc CÙNG data ở different pace
  → Consumer quản lý OWN offset → replay bất kỳ lúc nào
  → Broker KHÔNG biết consumer đã xử lý hay chưa


  KEY INSIGHT: Message Ownership

  ┌───────────────────────────────────────────────────────────┐
  │                   WHO OWNS THE MESSAGE?                    │
  │                                                           │
  │  NATS Core:  Nobody (fire and forget)                     │
  │  NATS JS:    Stream (server manages lifecycle)            │
  │  RabbitMQ:   Queue → Consumer (consumed = deleted)        │
  │  Kafka:      Log (retained regardless of consumption)     │
  │                                                           │
  │  → Kafka: message vẫn CÒN sau khi consume                │
  │  → RabbitMQ: message BỊ XÓA sau khi ack                  │
  │  → NATS core: message KHÔNG BAO GIỜ lưu                  │
  │  → NATS JS: message lưu theo retention policy             │
  └───────────────────────────────────────────────────────────┘
```

### 4.2 Feature Comparison — Comprehensive Side-by-Side

```
COMPREHENSIVE FEATURE COMPARISON:

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Feature              │ NATS (+ JetStream) │ RabbitMQ          │ Kafka    │
  ├──────────────────────┼────────────────────┼───────────────────┼──────────┤
  │ Protocol             │ NATS protocol      │ AMQP 0.9.1        │ Custom   │
  │                      │ (text-based)       │ (binary)          │ (binary) │
  │                      │                    │ + MQTT, STOMP     │          │
  │                      │                    │                   │          │
  │ Message model        │ Pub/Sub + Queue    │ Queue + Exchange  │ Commit   │
  │                      │ + Stream (JS)      │ routing           │ Log      │
  │                      │                    │                   │          │
  │ Persistence          │ Optional (JS)      │ Yes (persistent   │ Yes      │
  │                      │ Memory or File     │ queues)           │ (always) │
  │                      │                    │                   │          │
  │ Message replay       │ Yes (JetStream)    │ No (consumed =    │ Yes      │
  │                      │                    │ deleted) *        │ (offset) │
  │                      │                    │                   │          │
  │ Ordering             │ Per-stream/consumer│ Per-queue (single │ Per-     │
  │                      │                    │ consumer)         │partition │
  │                      │                    │                   │          │
  │ Consumer groups      │ Queue Groups /     │ Multiple consumers│ Consumer │
  │                      │ Durable Consumers  │ per queue         │ Groups   │
  │                      │                    │                   │          │
  │ Routing              │ Subject hierarchy  │ Exchange types    │ Topic +  │
  │                      │ + wildcards        │ (direct, topic,   │ partition│
  │                      │ (orders.>)         │ fanout, headers)  │ key      │
  │                      │                    │                   │          │
  │ Request-Reply        │ Built-in ✓         │ RPC pattern       │ Not      │
  │                      │ (first-class)      │ (manual setup)    │ built-in │
  │                      │                    │                   │          │
  │ Dead Letter          │ No (manual)        │ DLX ✓ (built-in) │ DLT      │
  │                      │                    │                   │ (manual) │
  │                      │                    │                   │          │
  │ Priority Queue       │ No                 │ Yes ✓             │ No       │
  │                      │                    │                   │          │
  │ Delayed Messages     │ No                 │ Yes (plugin/TTL)  │ No       │
  │                      │                    │                   │          │
  │ Transactions         │ No                 │ Publisher confirms│ Yes ✓    │
  │                      │                    │ ≠ AMQP TX mode    │ scoped to│
  │                      │                    │                   │ Kafka log│
  │                      │                    │                   │          │
  │ Stream Processing    │ No                 │ No                │ Kafka    │
  │                      │                    │                   │ Streams ✓│
  │                      │                    │                   │          │
  │ Schema Registry      │ No                 │ No (3rd party)    │ Yes ✓    │
  │                      │                    │                   │(Confluent│
  │                      │                    │                   │          │
  │ Connect Framework    │ No                 │ Shovel/Federation │ Kafka    │
  │                      │                    │                   │Connect ✓ │
  │                      │                    │                   │          │
  │ Replication          │ JetStream R=N      │ Quorum Queues     │ ISR ✓    │
  │                      │ (RAFT consensus)   │ (RAFT-based)      │ (leader/ │
  │                      │                    │                   │ follower)│
  │                      │                    │                   │          │
  │ Multi-tenancy        │ Accounts ✓         │ Virtual hosts     │ ACLs +   │
  │                      │                    │ (vhosts) ✓        │ quotas   │
  │                      │                    │                   │          │
  │ WebSocket support    │ Yes (built-in)     │ Yes (plugin)      │ No       │
  │                      │                    │                   │ (proxy)  │
  │                      │                    │                   │          │
  │ Binary size          │ ~20MB              │ ~100MB (Erlang)   │ ~100MB   │
  │                      │ (single binary)    │ (+ Erlang VM)     │ (+ JVM)  │
  │                      │                    │                   │          │
  │ Language             │ Go                 │ Erlang            │ Java/    │
  │                      │                    │                   │ Scala    │
  └──────────────────────────────────────────────────────────────────────────┘

  * RabbitMQ Streams (3.9+) supports replay but limited ecosystem
```

### 4.3 Performance Comparison

```
PERFORMANCE BENCHMARKS (approximate, single node, 1KB messages):

  ┌──────────────────────────────────────────────────────────────────┐
  │ Metric                │ NATS Core   │ RabbitMQ    │ Kafka        │
  ├───────────────────────┼─────────────┼─────────────┼──────────────┤
  │ Throughput (msg/sec)  │             │             │              │
  │   Publish (1 pub)     │ 10-15M      │ 20-50K      │ 200K-1M      │
  │   Publish (batched)   │ N/A (no     │ N/A         │ 1-2M         │
  │                       │  batching)  │             │ (with batch) │
  │                       │             │             │              │
  │ Throughput (MB/sec)   │             │             │              │
  │   Single partition    │ N/A         │ 20-50 MB/s  │ 100-200 MB/s │
  │   Multi-partition     │ N/A         │ N/A         │ 500MB-1GB/s  │
  │                       │             │             │              │
  │ Latency (p50/p99)     │             │             │              │
  │   Publish             │ 100-500μs   │ 1-5ms       │ 2-10ms       │
  │   End-to-end          │ 200μs-1ms   │ 2-10ms      │ 5-30ms       │
  │   (pub to sub)        │             │             │ (with batch) │
  │                       │             │             │              │
  │ Memory footprint      │ 10-50MB     │ 200MB-2GB   │ 1-8GB (heap) │
  │                       │             │ (Erlang VM) │ + page cache │
  │                       │             │             │              │
  │ Disk usage            │ 0 (core)    │ Proportional│ High         │
  │                       │ Low (JS)    │ to queue    │ (retention)  │
  │                       │             │ depth       │              │
  │                       │             │             │              │
  │ Max partition-like    │ Subjects are│ ~10K queues │ ~4K          │
  │ units/node            │ not         │ practical   │ partitions   │
  │                       │ partitions  │             │              │
  │                       │             │             │              │
  │ Horizontal scalability│ Cluster +   │ Cluster     │ Partition-   │
  │                       │ Leaf Nodes  │ (limited)   │ based ✓✓     │
  │                       │             │             │              │
  │ Resource efficiency   │ ✓✓✓ (Go,   │ ✓ (Erlang   │ ✓✓ (JVM,    │
  │                       │  small)     │  overhead)  │  page cache) │
  └──────────────────────────────────────────────────────────────────┘

  ⚠️ CẢNH BÁO: Benchmark numbers luôn phụ thuộc vào:
  - Hardware (CPU, disk type, memory, network)
  - Configuration (replication, acks, batch size, persistence)
  - Message size (1KB vs 100KB vs 1MB)
  - Workload pattern (sustained vs burst)
  
  → Luôn BENCHMARK trên hardware và workload CỦA BẠN!
  → Số trên chỉ là order of magnitude reference


NATS JetStream vs Kafka Performance (with persistence):

  ┌──────────────────────────────────────────────────────────────┐
  │ Metric              │ NATS JetStream    │ Kafka              │
  ├──────────────────────┼───────────────────┼────────────────────┤
  │ Throughput (1KB msg) │ 100K-500K msg/s   │ 200K-1M msg/s      │
  │ Latency p99          │ 1-5ms             │ 5-30ms (batched)   │
  │ Latency p99 (no bat) │ 1-5ms             │ 2-10ms             │
  │ Replication overhead │ ~40% (RAFT)       │ ~30% (ISR)         │
  │ Operational comfort  │ Đơn giản hơn      │ Phức tạp hơn       │
  │ Ecosystem            │ Growing           │ Mature ✓✓          │
  │ Stream processing    │ Không có          │ Kafka Streams ✓    │
  └──────────────────────────────────────────────────────────────┘
```

### 4.4 Decision Matrix — Chọn Broker theo Use Case

```
DECISION MATRIX:

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Use Case              │ Best Choice    │ Why                     │ Alt  │
  ├───────────────────────┼────────────────┼─────────────────────────┼──────┤
  │ Event Sourcing        │ Kafka ✓✓       │ Immutable log, replay,  │ NATS │
  │                       │                │ retention forever       │ JS   │
  │                       │                │                         │      │
  │ Task Queue / Work     │ RabbitMQ ✓✓    │ Ack/nack, priority,     │ NATS │
  │ Distribution          │                │ DLX, per-message routing│ QG   │
  │                       │                │                         │      │
  │ Log Aggregation       │ Kafka ✓✓       │ High throughput,        │      │
  │                       │                │ retention, compression  │      │
  │                       │                │                         │      │
  │ Real-time Analytics   │ Kafka ✓✓       │ Kafka Streams, ksqlDB,  │      │
  │ / Stream Processing   │                │ Kafka-scoped EOS,       │      │
  │                       │                │ windowing               │      │
  │                       │                │                         │      │
  │ Request-Reply / RPC   │ NATS ✓✓        │ Built-in request-reply, │ Rmq  │
  │                       │                │ ultra-low latency       │ RPC  │
  │                       │                │                         │      │
  │ IoT / Edge Computing  │ NATS ✓✓        │ Tiny binary, leaf nodes,│      │
  │                       │                │ low resource, WebSocket │      │
  │                       │                │                         │      │
  │ Microservices Events  │ Kafka ✓        │ IF need replay, audit   │ NATS │
  │ (Event-Driven)        │ hoặc NATS JS   │ NATS JS IF simpler ops  │ JS   │
  │                       │                │                         │      │
  │ Microservices Commands│ RabbitMQ ✓     │ Task routing, retry,    │ NATS │
  │ (Task Distribution)   │ hoặc NATS QG   │ DLX, priority           │ QG   │
  │                       │                │                         │      │
  │ Notification Fanout   │ NATS ✓✓        │ Simple pub/sub,         │ Rmq  │
  │                       │ hoặc RabbitMQ  │ ultra-fast fanout       │fanout│
  │                       │                │                         │      │
  │ CDC (Change Data      │ Kafka ✓✓       │ Debezium + Connect,     │      │
  │ Capture)              │                │ transactions + schema   │      │
  │                       │                │                         │      │
  │ Data Pipeline / ETL   │ Kafka ✓✓       │ Connect framework,      │      │
  │                       │                │ transactional consume/  │      │
  │                       │                │ produce + replay        │      │
  │                       │                │                         │      │
  │ Chat / Real-time Push │ NATS ✓✓        │ WebSocket, fast,        │ Rmq  │
  │                       │                │ subject wildcard        │ WS   │
  │                       │                │                         │      │
  │ Delayed / Scheduled   │ RabbitMQ ✓✓    │ TTL + DLX, delayed      │      │
  │ Messages              │                │ message plugin          │      │
  │                       │                │                         │      │
  │ Workflow Orchestration│ RabbitMQ ✓     │ Priority, routing,      │      │
  │ (Saga Orchestrator)   │                │ reply-to pattern        │      │
  └──────────────────────────────────────────────────────────────────────────┘


  SIMPLIFIED DECISION TREE:

  Bạn cần gì?
  │
  ├─ "Replay messages / Event sourcing / CDC" ──────► Kafka
  │
  ├─ "Stream processing (windowing, joins)" ────────► Kafka
  │
  ├─ "Complex routing / Priority / DLX / Retry" ───► RabbitMQ
  │
  ├─ "Ultra-low latency / Request-reply" ──────────► NATS
  │
  ├─ "Lightweight / IoT / Edge" ───────────────────► NATS
  │
  ├─ "Simple pub/sub, don't need replay" ──────────► NATS
  │
  ├─ "Simple task queue, ack/nack" ────────────────► RabbitMQ
  │   (hoặc NATS JetStream nếu muốn đơn giản hơn)
  │
  └─ "High throughput log aggregation" ────────────► Kafka
```

### 4.5 Khi Nào KHÔNG Dùng Message Broker

```
WHEN NOT TO USE A MESSAGE BROKER:

  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  ❶ Simple Request-Response với Immediate Feedback           │
  │     User click "Submit Order" → cần response NGAY           │
  │     → Dùng HTTP/gRPC call trực tiếp                        │
  │     → Broker adds latency + complexity cho KHÔNG lợi ích    │
  │                                                             │
  │  ❷ Ít Services, Ít Communication Patterns                  │
  │     2-3 services, mỗi service gọi 1-2 service khác         │
  │     → HTTP/gRPC đủ dùng, không cần broker overhead          │
  │     → Broker shines khi có NHIỀU services + NHIỀU patterns  │
  │                                                             │
  │  ❸ Strong Consistency Required (mọi thứ phải sync)         │
  │     Chuyển tiền: debit + credit PHẢI cùng transaction       │
  │     → Distributed transaction (2PC) hoặc database TX        │
  │     → Async messaging = eventual consistency (có thể ko đủ) │
  │                                                             │
  │  ❹ Simple CRUD Application                                 │
  │     Basic blog, simple admin panel, internal tool            │
  │     → Direct DB calls, no events needed                     │
  │     → Adding Kafka = over-engineering                       │
  │                                                             │
  │  ❺ Team Quá Nhỏ hoặc Không Có Expertise                   │
  │     3 devs, chưa ai dùng Kafka bao giờ                     │
  │     → Learning curve + ops burden > benefit                 │
  │     → Start simple, add broker khi THẬT SỰ CẦN             │
  └─────────────────────────────────────────────────────────────┘


  ANTI-PATTERNS — SAI cách dùng broker:

  ❌ Kafka as Database
     Sai:  "Kafka giữ data forever → dùng như database"
     Tại sao sai: No indexing, no random access, no update/delete
     Đúng: Kafka = transport + short-term buffer, DB = source of truth

  ❌ RabbitMQ for Event Sourcing
     Sai:  "Dùng RabbitMQ lưu event history"
     Tại sao sai: Consumed = deleted. No replay. No multiple consumers.
     Đúng: Kafka for event sourcing, RabbitMQ for task distribution

  ❌ Kafka for Request-Reply
     Sai:  "Dùng Kafka cho synchronous request-reply"
     Tại sao sai: High latency (batching), complex correlation
     Đúng: NATS hoặc HTTP/gRPC for request-reply

  ❌ Message Broker cho EVERY Inter-Service Communication
     Sai:  "Tất cả service-to-service calls qua Kafka"
     Tại sao sai: Some calls need immediate response (auth check, config fetch)
     Đúng: Async events via broker, sync queries via HTTP/gRPC
     → "Events through broker, queries through API"
```

### 4.6 Polyglot Messaging — Combine Nhiều Brokers

```
POLYGLOT MESSAGING — Khi 1 broker không đủ:

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  Real-world hệ thống thường có MULTIPLE messaging needs:        │
  │                                                                  │
  │  ❶ Event backbone (ordering, replay, audit)     → Kafka         │
  │  ❷ Task queue (retry, DLX, priority, routing)   → RabbitMQ      │
  │  ❸ Real-time push (WebSocket, low latency)      → NATS          │
  │                                                                  │
  │  Polyglot architecture:                                          │
  │                                                                  │
  │  ┌─────────┐    Kafka     ┌─────────┐    Kafka    ┌──────────┐ │
  │  │ Order   ├──(events)───►│ Payment ├──(events)──►│Inventory │ │
  │  │ Service │              │ Service │              │ Service  │ │
  │  └────┬────┘              └─────────┘              └──────────┘ │
  │       │                                                         │
  │       │ RabbitMQ (task)    ┌──────────┐                         │
  │       ├──(email task)────►│ Email    │                          │
  │       │  retry=3, DLX     │ Worker   │                          │
  │       │                   └──────────┘                          │
  │       │                                                         │
  │       │ NATS (real-time)  ┌──────────┐                         │
  │       └──(status push)───►│ WebSocket│──► Browser              │
  │          sub: orders.>    │ Gateway  │                          │
  │                           └──────────┘                          │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘


  REAL-WORLD EXAMPLES:

  Uber:
  - Kafka: ride events, surge pricing data, logging
  - Custom (Cherami/later Kafka): task queue for notifications
  - gRPC: synchronous service calls

  LinkedIn (nơi sinh ra Kafka):
  - Kafka: activity stream, metrics, CDC, Kafka Streams
  - Espresso (custom DB): synchronous queries
  - Not using RabbitMQ or NATS — all-in on Kafka

  Wealthsimple:
  - Kafka: event backbone, financial events
  - RabbitMQ: async task processing (reports, exports)
  - Direct Redis pub/sub: real-time portfolio updates


  TRADE-OFFS OF POLYGLOT MESSAGING:

  ┌───────────────────────────────────────────────────────────────┐
  │ Benefit                    │ Cost                             │
  ├────────────────────────────┼──────────────────────────────────┤
  │ Best tool for each job     │ 3x operational complexity        │
  │ Optimized performance per  │ 3x monitoring setup              │
  │   use case                 │ 3x security config               │
  │ Natural separation of      │ Team needs expertise in ALL 3    │
  │   concerns                 │ Data consistency across brokers  │
  │ Independent scaling per    │ Bridge/sync between brokers      │
  │   workload type            │   adds failure points            │
  └───────────────────────────────────────────────────────────────┘

  RECOMMENDATION:
  → Start với 1 broker (usually Kafka for events, or RabbitMQ for tasks)
  → Add 2nd broker ONLY khi clear pain point emerged
  → Document WHY each broker is used
  → Small team (< 10 devs)? Stick to 1 broker. Complexity kills.
```

### 4.7 Migration Paths

```
MIGRATION: RabbitMQ → Kafka (most common migration):

  WHY migrate?
  - Outgrown single-node RabbitMQ
  - Need message replay (audit, reprocessing)
  - Need stream processing (Kafka Streams)
  - Consumer can't keep up → need multiple consumer groups
  - Need CDC (Debezium + Kafka Connect)


  STRATEGY: Dual-Write / Bridge Pattern

  Phase 1: Parallel publishing
  ┌──────────┐    ┌───────────┐    ┌──────────┐
  │ Producer │───►│ RabbitMQ  │───►│ Consumer │  (existing)
  │          │    └───────────┘    │  (old)   │
  │          │    ┌───────────┐    └──────────┘
  │          │───►│  Kafka    │                   (new, shadow)
  │          │    └───────────┘
  └──────────┘

  Phase 2: Consumer migration (one by one)
  ┌──────────┐    ┌───────────┐
  │ Producer │───►│ RabbitMQ  │    (still publishing to both)
  │          │    └───────────┘
  │          │    ┌───────────┐    ┌──────────┐
  │          │───►│  Kafka    │───►│ Consumer │  (migrated!)
  │          │    └───────────┘    │  (new)   │
  └──────────┘                    └──────────┘

  Phase 3: Remove RabbitMQ
  ┌──────────┐    ┌───────────┐    ┌──────────┐
  │ Producer │───►│  Kafka    │───►│ Consumer │  (all migrated)
  └──────────┘    └───────────┘    └──────────┘


  PITFALLS khi migrate:
  ❌ Big bang migration → too risky
  ✓ Gradual, service by service
  
  ❌ Assume same semantics
  ✓ RabbitMQ ack/nack ≠ Kafka offset commit (different model!)
  
  ❌ Keep same architecture
  ✓ Redesign consumer groups, partitioning strategy
  
  ❌ Ignore ordering changes
  ✓ RabbitMQ: per-queue ordering. Kafka: per-partition ordering (different!)
```

---

## 5. Trade-off Analysis

### Operations & Cost Comparison

| Tiêu chí | NATS | RabbitMQ | Kafka |
|----------|------|----------|-------|
| Setup complexity | Rất thấp (single binary) | Thấp (Erlang package) | Cao (JVM + ZK/KRaft) |
| Ops complexity | Thấp | Trung bình | Cao |
| Learning curve | 1-2 ngày | 3-5 ngày | 2-4 tuần |
| Min resources | 64MB RAM, 1 CPU | 512MB RAM, 1 CPU | 2GB RAM, 2 CPU |
| Production resources | 1-4GB RAM | 4-8GB RAM | 8-32GB RAM + disk |
| Cluster min nodes | 3 (RAFT) | 3 (quorum) | 3 brokers + 3 KRaft |
| Team expertise needed | Go developer | Any backend dev | Dedicated Kafka team |
| Cloud managed options | Synadia Cloud | CloudAMQP, Amazon MQ | Confluent, Amazon MSK |
| Community & ecosystem | Growing | Mature | Very mature |

### Delivery Guarantee Comparison

| Guarantee | NATS Core | NATS JetStream | RabbitMQ | Kafka |
|-----------|----------|----------------|----------|-------|
| At-most-once | Default ✓ | Configurable | Configurable | Configurable |
| At-least-once | No | Yes ✓ | Yes ✓ | Yes ✓ |
| Exactly-once end-to-end | No | No; cần idempotent consumer | No; app-level only | No; Kafka transactions không cover external side effects |
| Idempotent producer | No | Dedup window bằng message ID | Publisher confirms không dedup | Yes ✓ trong phạm vi producer/session |
| Transactional | No | No | AMQP TX mode có nhưng chậm; publisher confirms chỉ là publish ack | Yes ✓ cho read-process-write Kafka topics |

Rule: nếu requirement ghi "exactly-once", hãy hỏi "exactly-once ở boundary nào?". Broker/client chỉ giải quyết một phần; payment API, database write, email/SMS vẫn cần idempotency key, inbox/outbox và compensation.

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. PICK BASED ON USE CASE, NOT HYPE
   → "Everyone uses Kafka" ≠ "We should use Kafka"
   → Simple task queue? RabbitMQ vẫn tốt hơn Kafka.
   → Low latency pub/sub? NATS vẫn tốt hơn Kafka.
   → Kafka shines for: replay, streaming, CDC, audit log

2. START WITH ONE BROKER
   → Add complexity CHỈ khi pain point rõ ràng
   → Small team + Kafka + RabbitMQ + NATS = operational nightmare
   → Kafka CAN do task queue (though not optimal)
   → RabbitMQ CAN do pub/sub (though not optimal)

3. EVALUATE WITH REAL WORKLOAD
   → Benchmark numbers online ≠ your workload
   → Message size, throughput, latency requirement, ordering needs
   → Run POC với realistic data pattern

4. CONSIDER TEAM EXPERTISE
   → Tool your team KNOWS > "best" tool your team doesn't know
   → Kafka expertise expensive → factor into decision
   → NATS lowest learning curve → fastest time to production

5. CONSIDER OPERATIONAL COST
   → Kafka: ZooKeeper/KRaft + brokers + monitoring + Schema Registry
   → RabbitMQ: cluster + monitoring
   → NATS: cluster (simplest ops)
   → Managed services reduce ops but increase $ cost
```

### Common Pitfalls

```
❌ PITFALL 1: Chọn Kafka cho MỌI thứ
   "Kafka is the best, use it for everything"
   → Kafka for request-reply = over-engineering + high latency
   → Kafka for simple task queue = over-engineering
   → Right tool for right job!

❌ PITFALL 2: Ignore operational complexity
   "Kafka throughput tốt nhất, chọn Kafka"
   → Nhưng team 3 người, không ai biết ops Kafka
   → 2AM on-call, Kafka cluster unhealthy, ai fix?
   → Factor ops cost vào decision

❌ PITFALL 3: Benchmark sai cách
   "NATS xử lý 15M msg/s, Kafka chỉ 1M msg/s"
   → NATS core = no persistence. So sánh apple vs orange.
   → So sánh NATS JetStream vs Kafka (cùng persistence) → gap nhỏ hơn nhiều
   → Benchmark with SAME guarantees (persistence, replication, acks)

❌ PITFALL 4: Migrate vì "mới hơn = tốt hơn"
   "RabbitMQ cũ rồi, migrate sang Kafka"
   → RabbitMQ vẫn evolving (quorum queues, streams)
   → Migrate khi có PAIN POINT cụ thể, không phải vì trend
   → Migration cost (time, risk, learning) có thể > benefit

❌ PITFALL 5: Quên data model khác nhau
   "Chuyển từ RabbitMQ sang Kafka, đổi client library là xong"
   → RabbitMQ: message consumed = deleted. Kafka: message retained.
   → RabbitMQ: broker routes. Kafka: consumer reads.
   → Cần REDESIGN consumer pattern, không chỉ swap library.
```

---

## 7. Performance Considerations

### Benchmark Methodology

```
FAIR BENCHMARK CHECKLIST:

  Khi compare brokers, PHẢI đảm bảo:

  ┌─────────────────────────────────────────────────────────────┐
  │ Parameter          │ PHẢI GIỐNG nhau giữa các brokers       │
  ├────────────────────┼─────────────────────────────────────────┤
  │ Message size       │ 1KB (standard) hoặc match your payload │
  │ Persistence        │ All ON hoặc all OFF                    │
  │ Replication factor │ 3 (all brokers)                        │
  │ Delivery guarantee │ at-least-once (all brokers)            │
  │ Ack mode           │ Wait for persistence acknowledge       │
  │ Hardware           │ Same machine/VM specs                  │
  │ Network            │ Same network setup                     │
  │ Batching           │ Compare with and without batching      │
  │ Compression        │ Same codec or all off                  │
  │ Message count      │ Same number of messages                │
  │ Concurrency        │ Same number of producers/consumers     │
  └─────────────────────────────────────────────────────────────┘

  UNFAIR COMPARISONS (common!):
  ❌ NATS core (no persistence) vs Kafka (persistence ON)
  ❌ RabbitMQ (ack=manual) vs Kafka (acks=0)
  ❌ Batched Kafka vs non-batched RabbitMQ

  Split benchmark thành 3 profile, không trộn kết quả:
  1. Non-persistent pub/sub: NATS Core vs RabbitMQ transient vs Kafka acks=0 (demo latency only)
  2. Persistent publish-ack: JetStream file ack vs RabbitMQ persistent+confirm vs Kafka acks=all
  3. End-to-end consume: publish + consume + ack/commit, cùng concurrency và payload

  Lab dưới đây là custom demo để học API và methodology. Khi cần số liệu quyết định production,
  ưu tiên official tools: nats bench, RabbitMQ PerfTest, kafka-producer-perf-test/kafka-consumer-perf-test.
```

---

## 8. Hands-on Lab

### 8.1 Setup — All 3 Brokers

```yaml
# docker-compose.yml — NATS + RabbitMQ + Kafka for side-by-side benchmark
version: '3.8'

services:
  # NATS with JetStream
  nats:
    image: nats:2.10-alpine
    ports:
      - "4222:4222"
      - "8222:8222"
    command: ["-js", "-m", "8222"]

  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3.13-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin

  # Kafka (KRaft mode — no ZooKeeper)
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
      KAFKA_LOG_RETENTION_HOURS: 1
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
```

```bash
# Start all 3 brokers
docker compose up -d

# Verify all running
echo "NATS:     $(curl -s http://localhost:8222/varz | grep -o '"server_id":"[^"]*"' | head -1)"
echo "RabbitMQ: $(curl -s -u admin:admin http://localhost:15672/api/overview | grep -o '"rabbitmq_version":"[^"]*"')"
docker exec $(docker ps -q -f name=kafka) kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null && echo "Kafka: OK" || echo "Kafka: waiting..."
```

### 8.2 Go Benchmark — 3 Brokers Side-by-Side

```go
// benchmark/main.go
package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"sync/atomic"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/segmentio/kafka-go"
)

const (
	messageCount = 100000
	messageSize  = 1024 // 1KB payload
)

type BenchResult struct {
	Broker     string
	Mode       string
	MsgCount   int
	Duration   time.Duration
	MsgPerSec  float64
	MBPerSec   float64
	AvgLatency time.Duration
}

func main() {
	payload := make([]byte, messageSize)
	for i := range payload {
		payload[i] = 'A'
	}

	fmt.Println("=== Message Broker Benchmark ===")
	fmt.Printf("Messages: %d, Size: %d bytes\n\n", messageCount, messageSize)

	results := []BenchResult{}

	// Benchmark NATS Core (no persistence)
	if r, err := benchmarkNATSCore(payload); err == nil {
		results = append(results, r)
	} else {
		log.Printf("NATS Core error: %v", err)
	}

	// Benchmark NATS JetStream (with persistence)
	if r, err := benchmarkNATSJetStream(payload); err == nil {
		results = append(results, r)
	} else {
		log.Printf("NATS JetStream error: %v", err)
	}

	// Benchmark RabbitMQ (persistent messages)
	if r, err := benchmarkRabbitMQ(payload); err == nil {
		results = append(results, r)
	} else {
		log.Printf("RabbitMQ error: %v", err)
	}

	// Benchmark Kafka (with acks=all)
	if r, err := benchmarkKafka(payload); err == nil {
		results = append(results, r)
	} else {
		log.Printf("Kafka error: %v", err)
	}

	// Print results
	fmt.Println("\n=== RESULTS ===")
	fmt.Printf("%-20s %-15s %10s %12s %10s\n", "Broker", "Mode", "Msg/sec", "MB/sec", "Avg Lat")
	fmt.Println("─────────────────────────────────────────────────────────────────")
	for _, r := range results {
		fmt.Printf("%-20s %-15s %10.0f %10.2f %12s\n",
			r.Broker, r.Mode, r.MsgPerSec, r.MBPerSec, r.AvgLatency)
	}
}

func benchmarkNATSCore(payload []byte) (BenchResult, error) {
	nc, err := nats.Connect("nats://localhost:4222")
	if err != nil {
		return BenchResult{}, err
	}
	defer nc.Close()

	var wg sync.WaitGroup
	var received int64
	wg.Add(1)

	if _, err := nc.Subscribe("bench.nats.core", func(m *nats.Msg) {
		if atomic.AddInt64(&received, 1) >= int64(messageCount) {
			wg.Done()
		}
	}); err != nil {
		return BenchResult{}, err
	}
	if err := nc.Flush(); err != nil {
		return BenchResult{}, err
	}

	start := time.Now()
	for i := 0; i < messageCount; i++ {
		nc.Publish("bench.nats.core", payload)
	}
	nc.Flush()
	wg.Wait()
	duration := time.Since(start)

	result := BenchResult{
		Broker:    "NATS",
		Mode:      "Core (no persist)",
		MsgCount:  messageCount,
		Duration:  duration,
		MsgPerSec: float64(messageCount) / duration.Seconds(),
		MBPerSec:  float64(messageCount*messageSize) / duration.Seconds() / 1024 / 1024,
		AvgLatency: duration / time.Duration(messageCount),
	}
	fmt.Printf("NATS Core: %d msgs in %v (%.0f msg/s)\n", messageCount, duration, result.MsgPerSec)
	return result, nil
}

func benchmarkNATSJetStream(payload []byte) (BenchResult, error) {
	nc, err := nats.Connect("nats://localhost:4222")
	if err != nil {
		return BenchResult{}, err
	}
	defer nc.Close()

	js, err := jetstream.New(nc)
	if err != nil {
		return BenchResult{}, err
	}

	ctx := context.Background()
	// Create or update stream
	js.CreateOrUpdateStream(ctx, jetstream.StreamConfig{
		Name:     "BENCH",
		Subjects: []string{"bench.nats.js"},
		Storage:  jetstream.FileStorage,
	})

	start := time.Now()
	for i := 0; i < messageCount; i++ {
		_, err := js.Publish(ctx, "bench.nats.js", payload)
		if err != nil {
			return BenchResult{}, fmt.Errorf("publish %d: %w", i, err)
		}
	}
	duration := time.Since(start)

	result := BenchResult{
		Broker:    "NATS",
		Mode:      "JetStream (file)",
		MsgCount:  messageCount,
		Duration:  duration,
		MsgPerSec: float64(messageCount) / duration.Seconds(),
		MBPerSec:  float64(messageCount*messageSize) / duration.Seconds() / 1024 / 1024,
		AvgLatency: duration / time.Duration(messageCount),
	}
	fmt.Printf("NATS JetStream: %d msgs in %v (%.0f msg/s)\n", messageCount, duration, result.MsgPerSec)

	// Cleanup
	js.DeleteStream(ctx, "BENCH")
	return result, nil
}

func benchmarkRabbitMQ(payload []byte) (BenchResult, error) {
	conn, err := amqp.Dial("amqp://admin:admin@localhost:5672/")
	if err != nil {
		return BenchResult{}, err
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		return BenchResult{}, err
	}
	defer ch.Close()

	q, err := ch.QueueDeclare("bench-queue", true, false, false, false, nil)
	if err != nil {
		return BenchResult{}, err
	}

	// Enable publisher confirms for fair comparison
	if err := ch.Confirm(false); err != nil {
		return BenchResult{}, err
	}
	confirms := ch.NotifyPublish(make(chan amqp.Confirmation, messageCount))

	ctx := context.Background()
	start := time.Now()

	for i := 0; i < messageCount; i++ {
		err := ch.PublishWithContext(ctx, "", q.Name, false, false, amqp.Publishing{
			ContentType:  "application/octet-stream",
			Body:         payload,
			DeliveryMode: amqp.Persistent,
		})
		if err != nil {
			return BenchResult{}, err
		}
	}

	// Wait for all confirms
	for i := 0; i < messageCount; i++ {
		confirm := <-confirms
		if !confirm.Ack {
			return BenchResult{}, fmt.Errorf("rabbitmq publish not confirmed at delivery tag %d", confirm.DeliveryTag)
		}
	}
	duration := time.Since(start)

	result := BenchResult{
		Broker:    "RabbitMQ",
		Mode:      "Persistent+Confirm",
		MsgCount:  messageCount,
		Duration:  duration,
		MsgPerSec: float64(messageCount) / duration.Seconds(),
		MBPerSec:  float64(messageCount*messageSize) / duration.Seconds() / 1024 / 1024,
		AvgLatency: duration / time.Duration(messageCount),
	}
	fmt.Printf("RabbitMQ: %d msgs in %v (%.0f msg/s)\n", messageCount, duration, result.MsgPerSec)

	// Cleanup
	ch.QueueDelete(q.Name, false, false, false)
	return result, nil
}

func benchmarkKafka(payload []byte) (BenchResult, error) {
	// Create topic first
	conn, err := kafka.Dial("tcp", "localhost:9092")
	if err != nil {
		return BenchResult{}, err
	}
	if err := conn.CreateTopics(kafka.TopicConfig{
		Topic:             "bench-topic",
		NumPartitions:     4,
		ReplicationFactor: 1,
	}); err != nil {
		conn.Close()
		return BenchResult{}, err
	}
	conn.Close()

	time.Sleep(2 * time.Second)

	writer := &kafka.Writer{
		Addr:         kafka.TCP("localhost:9092"),
		Topic:        "bench-topic",
		Balancer:     &kafka.RoundRobin{},
		BatchSize:    100,
		BatchTimeout: 5 * time.Millisecond,
		RequiredAcks: kafka.RequireAll,
		Async:        false,
	}
	defer writer.Close()

	ctx := context.Background()
	start := time.Now()

	// Send in batches for fair Kafka usage
	batchSize := 100
	for i := 0; i < messageCount; i += batchSize {
		end := i + batchSize
		if end > messageCount {
			end = messageCount
		}
		msgs := make([]kafka.Message, 0, end-i)
		for j := i; j < end; j++ {
			msgs = append(msgs, kafka.Message{
				Key:   []byte(fmt.Sprintf("key-%d", j%100)),
				Value: payload,
			})
		}
		err := writer.WriteMessages(ctx, msgs...)
		if err != nil {
			return BenchResult{}, fmt.Errorf("batch write at %d: %w", i, err)
		}
	}
	duration := time.Since(start)

	result := BenchResult{
		Broker:    "Kafka",
		Mode:      "Batched, acks=all",
		MsgCount:  messageCount,
		Duration:  duration,
		MsgPerSec: float64(messageCount) / duration.Seconds(),
		MBPerSec:  float64(messageCount*messageSize) / duration.Seconds() / 1024 / 1024,
		AvgLatency: duration / time.Duration(messageCount),
	}
	fmt.Printf("Kafka: %d msgs in %v (%.0f msg/s)\n", messageCount, duration, result.MsgPerSec)

	// Cleanup
	conn2, _ := kafka.Dial("tcp", "localhost:9092")
	if conn2 != nil {
		conn2.DeleteTopics("bench-topic")
		conn2.Close()
	}
	return result, nil
}
```

```bash
# Setup benchmark module
mkdir -p benchmark

# Save the Go code above as benchmark/main.go, then create go.mod:
cat <<'EOF' > benchmark/go.mod
module benchmark

go 1.21

require (
	github.com/nats-io/nats.go v1.31.0
	github.com/rabbitmq/amqp091-go v1.9.0
	github.com/segmentio/kafka-go v0.4.47
)
EOF

# Run benchmark
cd benchmark
go mod tidy
go run main.go
```

### 8.3 Decision Framework Worksheet

```markdown
## Broker Decision Worksheet — Fill in for YOUR project

### 1. Requirements Checklist

| Requirement                        | Needed? | Priority |
|------------------------------------|---------|----------|
| Message replay / reprocessing      | Y/N     | H/M/L    |
| Strict ordering                    | Y/N     | H/M/L    |
| Complex routing (header/topic)     | Y/N     | H/M/L    |
| Priority queue                     | Y/N     | H/M/L    |
| Delayed/scheduled messages         | Y/N     | H/M/L    |
| Request-reply pattern              | Y/N     | H/M/L    |
| Stream processing (windowing etc.) | Y/N     | H/M/L    |
| Exactly-once boundary rõ ràng      | Y/N     | H/M/L    |
| Dead letter queue                  | Y/N     | H/M/L    |
| Schema evolution                   | Y/N     | H/M/L    |
| CDC (Change Data Capture)          | Y/N     | H/M/L    |
| Multi-datacenter replication       | Y/N     | H/M/L    |
| WebSocket / browser push           | Y/N     | H/M/L    |
| Ultra-low latency (< 1ms)          | Y/N     | H/M/L    |

### 2. Constraints

| Constraint                         | Value                |
|------------------------------------|----------------------|
| Max messages/sec (peak)            | ______               |
| Max message size                   | ______               |
| Retention requirement              | ______               |
| Team Kafka experience (1-5)        | ______               |
| Team RabbitMQ experience (1-5)     | ______               |
| Team NATS experience (1-5)         | ______               |
| Budget for managed service         | ______               |
| Team size (who will operate)       | ______               |
| Available infrastructure           | ______               |

### 3. Score Matrix (rate 1-5)

| Criteria       | Weight | NATS | RabbitMQ | Kafka | NATS*W | Rmq*W | Kafka*W |
|---------------|--------|------|----------|-------|--------|-------|---------|
| Meets features| 5      |      |          |       |        |       |         |
| Performance   | 3      |      |          |       |        |       |         |
| Ops simplicity| 4      |      |          |       |        |       |         |
| Team expertise| 4      |      |          |       |        |       |         |
| Ecosystem     | 2      |      |          |       |        |       |         |
| Cost          | 3      |      |          |       |        |       |         |
| **TOTAL**     |        |      |          |       |        |       |         |

### 4. Decision
Chosen: ________________
Rationale: ________________
Review date: ________________ (revisit after 6 months)
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Một startup 5 người cần task queue để gửi email. 1000 emails/day. Họ nên chọn gì: Kafka, RabbitMQ, hay NATS? Giải thích.**
   - Hint: Throughput thấp, cần retry/DLX, team nhỏ. Over-engineering vs simplicity. NATS queue group hoặc RabbitMQ là đủ. Kafka = overkill.

2. **Hệ thống e-commerce cần REPLAY toàn bộ orders từ 30 ngày trước để rebuild search index. NATS JetStream hay Kafka? Trade-off?**
   - Hint: Kafka designed for long retention + replay. NATS JS CAN do it nhưng ecosystem tooling (Connect, Schema Registry) ít hơn. Volume lớn → Kafka. Volume nhỏ → NATS JS đơn giản hơn.

3. **RabbitMQ benchmark cho thấy 50K msg/s. Kafka cho 1M msg/s. Có nên migrate sang Kafka không? Những yếu tố nào cần cân nhắc ngoài throughput?**
   - Hint: 50K msg/s có ĐỦ cho workload không? Nếu đủ → không cần migrate. Cân nhắc: ops cost, learning curve, migration risk, ordering semantics khác, team expertise.

4. **Team quyết định dùng cả Kafka (events) + RabbitMQ (tasks) + NATS (real-time). Team có 4 backend devs. Bạn nghĩ sao?**
   - Hint: 4 devs operate 3 messaging systems = spreading too thin. 3x monitoring, 3x alerting, 3x expertise needed. Recommend: 1 broker first, add khi clear pain point.

5. **So sánh consumer model: RabbitMQ consumer ack/nack vs Kafka consumer offset commit. Implications cho error handling?**
   - Hint: RabbitMQ nack → message redelivered tới CÙNG queue. Kafka: skip offset → phải implement retry topic riêng. RabbitMQ built-in retry. Kafka cần manual retry/DLT pattern. Different mental model!

6. **Bạn đang migrate từ RabbitMQ sang Kafka. Production có 20 consumers. Strategy nào để migrate zero-downtime?**
   - Hint: Dual-write pattern. Producer publish to BOTH. Migrate consumers ONE BY ONE. Verify each. Remove RabbitMQ last. Risk: ordering changes (per-queue → per-partition), dedup during transition.

7. **Kafka anti-pattern: "dùng Kafka làm database". Tại sao sai? Khi nào Kafka CÓ THỂ thay thế 1 phần database (event sourcing)?**
   - Hint: No random access, no indexing, no update, no delete. Nhưng: Kafka compacted topics = materialized view of latest state per key. Event sourcing: log IS the source of truth. Vẫn cần query database cho reads.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [NATS Documentation](https://docs.nats.io/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [NATS vs Kafka Comparison (Synadia)](https://docs.nats.io/nats-concepts/overview/compare-nats)

### Blog Posts & Articles
- [Confluent — Kafka vs RabbitMQ vs ActiveMQ](https://www.confluent.io/blog/kafka-fastest-messaging-system/)
- [CloudAMQP — When to use RabbitMQ vs Kafka](https://www.cloudamqp.com/blog/when-to-use-rabbitmq-or-apache-kafka.html)
- [Uber Engineering — Building Reliable Reprocessing and Dead Letter Queues](https://www.uber.com/blog/reliable-reprocessing/)
- [LinkedIn Engineering — Kafka Ecosystem at LinkedIn](https://engineering.linkedin.com/blog/topic/kafka)
- [Wealthsimple Engineering — Event-Driven Architecture](https://medium.com/wealthsimple)

### Videos & Talks
- [Kafka Summit — Kafka vs Pulsar vs RabbitMQ](https://www.confluent.io/events/kafka-summit/)
- [GOTO Conference — Choosing the Right Message Broker](https://www.youtube.com/results?search_query=choosing+message+broker)
- [Martin Kleppmann — Turning the database inside out](https://www.youtube.com/watch?v=fU9hR3kiOK0)
- [Tim Berglund — Apache Kafka Explained](https://www.youtube.com/results?search_query=tim+berglund+kafka)

### Benchmark Tools
- [kafka-producer-perf-test / kafka-consumer-perf-test](https://kafka.apache.org/documentation/#basic_ops_perf)
- [NATS bench tool](https://docs.nats.io/running-a-nats-service/nats_admin/benchmarking)
- [RabbitMQ PerfTest](https://rabbitmq.github.io/rabbitmq-perf-test/stable/htmlsingle/)
