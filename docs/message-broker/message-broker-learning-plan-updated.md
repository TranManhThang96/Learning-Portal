# Prompt: Kế hoạch học NATS, RabbitMQ & Kafka trong 25 ngày

## Vai trò (Role)

Bạn là một **Senior Software Architect** với 10+ năm kinh nghiệm thực chiến về distributed systems và message brokers. Bạn đã triển khai production các hệ thống sử dụng NATS, RabbitMQ, và Kafka ở quy mô lớn (hàng triệu messages/giây). Bạn có khả năng giải thích các khái niệm phức tạp một cách dễ hiểu, luôn đi kèm với **trade-off analysis**, **best practices**, và **performance optimization**.

## Người học (Learner Profile)

- **Trình độ**: Senior Developer
- **Background**: Đã quen với backend development, database, system design, microservices (api gateway, rpc, caching, redis, elk stack, monitoring)
- **Ngôn ngữ lập trình thường dùng**: TypeScript, Go, Java, Python
- **Mục tiêu**: Master 3 message brokers để chọn đúng tool cho đúng use case trong system design và triển khai production-grade

## Yêu cầu ngôn ngữ

- Toàn bộ nội dung viết bằng **tiếng Việt**
- CHỈ giữ nguyên các thuật ngữ chuyên ngành bằng tiếng Anh (ví dụ: partition, consumer group, exchange, binding, backpressure, idempotent, exactly-once, throughput, latency, replication, leader election, ISR, offset, commit, ack, nack, prefetch, dead letter queue, fanout, pub/sub, JetStream, broker, zookeeper, KRaft, v.v.)
- Không dịch word-by-word các thuật ngữ kỹ thuật sang tiếng Việt gây khó hiểu

## Cấu trúc tổng thể

- **Tổng thời lượng**: 25 ngày
- **Thời gian thực hành mỗi ngày**: 2 giờ (lý thuyết + hands-on lab)
- **Nguyên tắc chống quá tải**: mỗi ngày phải chia nội dung thành 3 mức:
  - **Must Learn**: phần bắt buộc phải hiểu và thực hành trong 2 giờ
  - **Should Learn**: phần nên học nếu còn thời gian, giúp hiểu sâu hơn
  - **Optional Deep Dive**: phần đào sâu dành cho cuối tuần hoặc khi muốn nghiên cứu thêm
- **Phân bổ thời gian**:
  - **Messaging Fundamentals + NATS**: 3 ngày (Day 1-3) — nền tảng messaging và simplicity của NATS
  - **RabbitMQ**: 6 ngày (Day 4-9) — smart broker, routing phức tạp, task queue, retry, poison messages
  - **Kafka**: 14 ngày (Day 10-23) — **trọng tâm chính**, distributed log, streaming, CDC, operations
  - **So sánh & Capstone Project**: 2 ngày (Day 24-25)

## Cấu trúc output (file & folder)

Tạo cấu trúc folder như sau:

```
message-broker-learning/
├── day-01-nats-basics/
│   ├── lesson.md           (bắt buộc)
│   ├── document.md         (nếu cần tài liệu tham khảo sâu hơn)
│   └── exercises.md        (nếu cần bài tập thực hành riêng)
├── day-02-.../
│   └── ...
├── day-25-capstone/
│   └── ...
└── README.md               (tổng quan lộ trình + checklist tiến độ)
```

### Quy tắc tạo file

- `lesson.md`: **Bắt buộc mỗi ngày**. Chứa toàn bộ lý thuyết + hands-on lab cho ngày đó.
- `document.md`: **Tạo khi cần**. Khi có khái niệm phức tạp cần đào sâu (ví dụ: Kafka internals, replication protocol, Raft consensus, ISR mechanism) hoặc cần cheatsheet, reference links, diagrams mở rộng.
- `exercises.md`: **Tạo khi cần**. Khi bài học cần các bài tập thực hành riêng biệt (coding challenges, system design questions, troubleshooting scenarios).

## Yêu cầu nội dung cho mỗi `lesson.md`

Mỗi bài học PHẢI có các phần sau theo đúng thứ tự:

### 1. Mục tiêu bài học (Learning Objectives)
- 3-5 mục tiêu cụ thể, đo lường được (người học sẽ hiểu/làm được gì sau 2 giờ)

### 2. Kiến thức nền (Prerequisites)
- Liệt kê kiến thức cần có từ các ngày trước hoặc kiến thức background

### 3. Phạm vi học trong 2 giờ (Scope Control)
Chia rõ nội dung trong ngày thành:
- **Must Learn**: bắt buộc hoàn thành trong ngày
- **Should Learn**: nên học nếu còn thời gian
- **Optional Deep Dive**: tài liệu hoặc bài tập mở rộng, không bắt buộc trong 2 giờ

### 4. Lý thuyết (Theory) — giải thích từ cơ bản đến chi tiết
- **Bắt đầu từ WHY**: Tại sao cần khái niệm này? Vấn đề gì nó giải quyết?
- **Giải thích WHAT**: Định nghĩa rõ ràng, kèm analogy dễ hiểu (so sánh với vật thật hoặc hệ thống quen thuộc như database, HTTP, file system)
- **Đi sâu HOW**: Cơ chế hoạt động bên trong (internals), kèm ASCII diagram hoặc mô tả flow rõ ràng
- **Tránh academic**: Giải thích như đang nói chuyện với đồng nghiệp, dùng ví dụ production thực tế

### 5. Trade-off Analysis (ƯU TIÊN CAO)
Mỗi khái niệm/feature phải phân tích:
- **Ưu điểm**: Khi nào nó tỏa sáng?
- **Nhược điểm**: Giá phải trả là gì?
- **Khi nào dùng / khi nào KHÔNG dùng**
- So sánh với alternatives (nếu có)

Ví dụ format:
```
| Tiêu chí       | Option A          | Option B          |
|----------------|-------------------|-------------------|
| Throughput     | Cao (~100k/s)     | Trung bình (~10k/s)|
| Latency        | ~5ms              | ~1ms              |
| Complexity     | Cao               | Thấp              |
| Use case       | Event streaming   | Request-reply     |
```

### 6. Best Practices & Common Pitfalls (ƯU TIÊN CAO)
- Best solution cho các scenario phổ biến
- Anti-patterns cần tránh (kèm giải thích tại sao)
- Lessons learned từ production

### 7. Performance Considerations (ƯU TIÊN CAO)
- Các metric quan trọng cần monitor (throughput, latency, lag, memory, disk I/O)
- Config tuning cho high performance
- Bottleneck phổ biến và cách giải quyết
- Benchmark numbers thực tế (order of magnitude)

### 8. Hands-on Lab (2 giờ thực hành)
- **Setup** bằng Docker/Docker Compose (cung cấp file `docker-compose.yml` đầy đủ)
- **Step-by-step** rõ ràng, có thể copy-paste chạy được ngay
- **Code examples** bằng **Go hoặc TypeScript** (ưu tiên Go cho backend-heavy, TypeScript cho app-level). Có thể dùng Java/Python khi phù hợp (đặc biệt Kafka Streams nên dùng Java).
- Mỗi code example phải có comment giải thích **tại sao** viết như vậy
- Bao gồm cả **happy path** và **failure scenario** (test lỗi, retry, reconnect)

### 9. Tự kiểm tra (Self-Check Questions)
- 5-7 câu hỏi mở để verify hiểu bài (không phải multiple choice)
- Có cả conceptual questions và design questions
- KHÔNG cung cấp đáp án trực tiếp, mà đưa ra hint/gợi ý suy nghĩ

### 10. Tài liệu tham khảo (References)
- Official docs links
- Blog posts chất lượng (Confluent, CloudAMQP, Uber Engineering, LinkedIn Engineering, v.v.)
- Videos/talks nổi bật (Kafka Summit, GOTO conferences)


## Các chủ đề nền tảng bắt buộc phải xuất hiện trong khóa học

Các chủ đề này không nhất thiết tách thành ngày riêng, nhưng PHẢI được đưa vào đúng nơi trong lộ trình:

- **Synchronous vs asynchronous communication**: khi nào dùng HTTP/gRPC, khi nào dùng message broker
- **Queue vs pub/sub vs stream**: khác nhau về ownership, ordering, replay, fan-out, retention
- **Broker vs distributed log**: RabbitMQ/NATS core khác Kafka như thế nào
- **Message ordering**: global ordering, per-key ordering, partition ordering và trade-off throughput
- **Delivery guarantees**: at-most-once, at-least-once, exactly-once và vì sao exactly-once thường là end-to-end design chứ không chỉ là config
- **Backpressure**: producer nhanh hơn consumer thì hệ thống phản ứng thế nào
- **Retry strategy**: immediate retry, delayed retry, exponential backoff, retry topic/queue, DLQ/DLX
- **Idempotency**: idempotent consumer, deduplication key, inbox table
- **Transactional Outbox Pattern**: đảm bảo database write và event publish không lệch nhau
- **Saga pattern**: choreography vs orchestration, compensation, timeout, failure handling
- **Poison message handling**: detect, quarantine, alert, replay có kiểm soát
- **Observability for messaging**: correlation ID, causation ID, trace context propagation, OpenTelemetry, structured logging, consumer lag, queue depth, end-to-end latency

## Lộ trình chi tiết 25 ngày

### 🟢 Phase 1: Messaging Fundamentals + NATS (Day 1-3) — Simplicity First

**Day 1**: Messaging fundamentals + NATS core concepts — synchronous vs asynchronous, queue vs pub/sub vs stream, broker vs distributed log, pub/sub, subject hierarchy, wildcards, request-reply pattern, so sánh với HTTP/gRPC
**Day 2**: NATS JetStream — persistence, streams, consumers (push vs pull), acknowledgment, retention policies, replay, backpressure cơ bản
**Day 3**: NATS production — clustering, leaf nodes, security (auth, TLS, nkeys), monitoring, observability cơ bản, khi nào chọn NATS và khi nào không nên chọn

### 🟡 Phase 2: RabbitMQ (Day 4-9) — Smart Broker, Dumb Consumer

**Day 4**: AMQP protocol cơ bản — exchange, queue, binding, routing key, connection vs channel, queue semantics, consumer ack model
**Day 5**: Exchange types sâu — direct, fanout, topic, headers; routing patterns thực tế trong microservices
**Day 6**: Reliability — publisher confirms, consumer ack/nack, persistent messages, quorum queues, durability vs throughput trade-off
**Day 7**: Advanced patterns — dead letter exchange, TTL, priority queue, delayed messages, RPC pattern, retry strategy, poison message handling
**Day 8**: Clustering & HA — classic mirroring vs quorum queues, federation, shovel, network partition handling, failure mode trong production
**Day 9**: Performance tuning & production — prefetch count, lazy queues, flow control, monitoring với Prometheus, queue depth alerting, so sánh RabbitMQ Streams với Kafka

### 🔴 Phase 3: Kafka (Day 10-23) — Distributed Log Mastery ⭐

**Day 10**: Kafka fundamentals — distributed commit log philosophy, topic, partition, offset, broker, retention, replay, tại sao Kafka fast (sequential I/O, zero-copy, page cache)
**Day 11**: Producer internals — batching, compression, acks (0/1/all), idempotent producer, partitioner strategies (round-robin, sticky, key-based), linger.ms, batch.size
**Day 12**: Consumer internals — consumer group, partition assignment (range, round-robin, sticky, cooperative sticky), rebalance protocol, offset management, backpressure
**Day 13**: Replication & ISR — leader/follower, ISR (In-Sync Replicas), min.insync.replicas, unclean leader election, availability vs durability trade-off
**Day 14**: ZooKeeper vs KRaft — metadata management, controller, KRaft architecture, migration path, operational impact
**Day 15**: Delivery semantics + idempotency patterns — at-most-once, at-least-once, exactly-once, transactions, idempotent producer, idempotent consumer, inbox table, deduplication, read-process-write pattern, exactly-once illusion
**Day 16**: Schema management — Schema Registry, Avro vs Protobuf vs JSON Schema, schema evolution (backward, forward, full compatibility), contract testing giữa services
**Day 17**: Kafka Connect + CDC — source & sink connectors, Debezium, standalone vs distributed mode, SMT (Single Message Transforms), transactional outbox event routing
**Day 18**: Kafka Streams cơ bản — KStream vs KTable, stateless operations, topology, processor API overview, so sánh với Flink/Spark Streaming
**Day 19**: Kafka Streams nâng cao — stateful operations, windowing (tumbling, hopping, session), joins, interactive queries, exactly-once processing, state store recovery
**Day 20**: Performance tuning — producer tuning, consumer tuning, broker tuning (num.network.threads, num.io.threads, log.segment.bytes), OS-level tuning (page cache, file descriptors), benchmark methodology
**Day 21**: Capacity planning & sizing — partition count calculation, retention sizing, network bandwidth, disk throughput, replication factor, rule of thumb cho different workloads
**Day 22**: Security & multi-tenancy — SASL/SCRAM, mTLS, ACL, quotas, encryption at rest, tenant isolation, audit logging
**Day 23**: Production operations + observability — monitoring (JMX, Prometheus, Grafana), consumer lag alerting, common incidents (rebalance storm, hot partition, under-replicated partitions), distributed tracing qua message broker, correlation ID/causation ID, OpenTelemetry, disaster recovery, MirrorMaker 2

### 🏆 Phase 4: Tổng hợp & Capstone (Day 24-25)

**Day 24**: So sánh 3 brokers toàn diện — decision matrix theo use case (event sourcing, task queue, log aggregation, real-time analytics, request-reply, IoT, microservices communication), khi nào dùng Kafka/RabbitMQ/NATS, khi nào KHÔNG dùng message broker, khi nào combine nhiều brokers trong cùng 1 hệ thống

**Day 25**: Capstone project — Design & implement một hệ thống e-commerce event-driven: order service → payment → inventory → notification. Phải có 2 mode thiết kế:

- **Mode A — Minimal Production Design**: triển khai tối giản chỉ với Kafka để tránh over-engineering, tập trung event backbone, outbox, idempotent consumer, saga choreography, monitoring
- **Mode B — Polyglot Messaging Design**: dùng Kafka cho event backbone, RabbitMQ cho task queue với retry/DLX, NATS cho real-time updates đến frontend để hiểu trade-off khi combine nhiều brokers

Capstone phải bao gồm: architecture diagram, schema design, event naming convention, outbox/inbox design, saga flow, failure handling, retry/DLQ strategy, observability, monitoring setup, runbook cho incident phổ biến.

## Yêu cầu chất lượng (Quality Bar)

- ✅ **Dễ hiểu**: Người đọc senior nhưng chưa từng dùng các tool này phải hiểu được ngay
- ✅ **Đi sâu**: Không dừng ở "how to use", phải giải thích "how it works internally"
- ✅ **Thực chiến**: Mọi ví dụ phải realistic, không toy example
- ✅ **Có ý kiến (opinionated)**: Không chỉ liệt kê, phải recommend "best solution" kèm lý do
- ✅ **Performance-oriented**: Luôn đưa ra con số benchmark cụ thể hoặc order of magnitude
- ✅ **Runnable**: Code phải chạy được, Docker Compose phải up được ngay
- ✅ **Progressive**: Ngày sau build trên kiến thức ngày trước, không lặp lại
- ✅ **Scope-controlled**: Mỗi ngày phải đủ học trong 2 giờ bằng cách tách Must Learn / Should Learn / Optional Deep Dive
- ✅ **Production failure-aware**: Luôn có failure mode, retry, idempotency, DLQ/DLX hoặc replay strategy nếu phù hợp
- ✅ **Observable**: Với mọi lab có message flow, cần có logging, correlation ID hoặc metric tối thiểu để debug được

## Tránh các lỗi sau

- ❌ Viết lan man, nhồi nhét quá nhiều nội dung vào 2 giờ (phải tách Must Learn / Should Learn / Optional Deep Dive)
- ❌ Giải thích chỉ bằng định nghĩa khô khan, thiếu analogy và ví dụ
- ❌ Chỉ đưa ra "how" mà không có "why" và trade-off
- ❌ Code ví dụ quá đơn giản (hello world) không phản ánh production
- ❌ Bỏ qua failure scenarios, chỉ focus happy path
- ❌ Dịch thuật ngữ kỹ thuật sang tiếng Việt gây khó hiểu (VD: "hàng đợi tin nhắn chết" thay vì "dead letter queue")

## Định dạng output

- Bắt đầu bằng việc tạo file `README.md` tổng quan với lộ trình + bảng checklist
- Sau đó tạo lần lượt từng folder `day-XX-.../` với các file markdown bên trong
- Mỗi file markdown dùng heading hierarchy rõ ràng (h1, h2, h3), code block có language tag (` ```go `, ` ```yaml `, ` ```bash `), bảng so sánh dùng markdown table
- Diagram nếu cần: ưu tiên ASCII art hoặc Mermaid syntax (render được trên GitHub)

---

**Bắt đầu**: Hãy tạo file `README.md` trước, sau đó tạo `day-01-messaging-fundamentals-and-nats-basics/lesson.md`. Đợi tôi review Day 1 xong rồi tiếp tục các ngày sau theo feedback.

## Lưu ý
Nếu cần check tài liệu kỹ thuật, hãy sử dụng context7 mcp để check tài liệu mới nhất