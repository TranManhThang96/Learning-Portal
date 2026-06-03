# Message Broker — NATS, RabbitMQ & Kafka trong 25 ngày

Khóa học 25 ngày dành cho Senior Developer muốn master 3 message brokers phổ biến nhất. Mỗi ngày học 2 giờ (lý thuyết + hands-on lab).

## Bắt đầu

- [Lộ trình tổng quan](./README.md)
- [Day 01: Messaging Fundamentals + NATS Basics](./day-01-messaging-fundamentals-and-nats-basics/lesson.md)

## Phân tích 80/20

~20% kiến thức mang lại ~80% hiệu quả. Ưu tiên: Messaging Fundamentals, Kafka (distributed log core), Producer/Consumer Internals, Reliability Patterns, NATS JetStream.

## Cách học khuyến nghị (theo 80/20)

### Nhóm A — Học ngay, bắt buộc
Day 1 (Messaging Fundamentals + NATS) → Day 4 (AMQP Protocol) → Day 10 (Kafka Fundamentals) → Day 11 (Producer Internals) → Day 12 (Consumer Internals) → Day 13 (Replication & ISR) → Day 15 (Delivery Semantics), Day 24 (Broker Comparison)

### Nhóm B — Học sớm
Day 2 (NATS JetStream) + Day 3 (NATS Production) + Day 5-6 (Exchange Types + Reliability) + Day 14 (ZooKeeper vs KRaft) + Day 16 (Schema Management) + Day 7 (Retry/DLX) + Day 20 (Performance Tuning)

### Nhóm C — Học sau khi có basic project
Day 17 (Kafka Connect + CDC) + Day 18-19 (Kafka Streams) + Day 21 (Capacity Planning) + Day 22 (Security & Multi-tenancy) + Day 23 (Production Operations) + Day 25 (Capstone)

### Nhóm D — Đọc lướt / tra cứu
Day 8 (Clustering HA) + Day 9 (Performance Production)

## Lộ trình 80/20 chi tiết

### Phase 1: Messaging Fundamentals + NATS (Days 1-3)

**Nhóm A:** Day 01 — Messaging Fundamentals + NATS Core. Kiến thức nền tảng bắt buộc: synchronous vs asynchronous, queue vs pub/sub vs stream, broker vs distributed log, NATS subject/wildcards. Làm nền cho toàn bộ khóa học.

**Nhóm B:** Day 02 — NATS JetStream. Persistence và streaming cho NATS. Quan trọng nhưng có thể học sau khi đã hiểu fundamentals.

**Nhóm C:** Day 03 — NATS Production. Clustering, security, monitoring. Học khi cần deploy NATS production.

### Phase 2: RabbitMQ (Days 4-9)

**Nhóm A:** Day 04 — AMQP Protocol. Exchange, Queue, Binding, Connection/Channel, Consumer Ack. Kiến thức nền cho RabbitMQ.

**Nhóm B:** Day 05 — Exchange Types + Day 06 — Reliability. Routing patterns và reliability patterns dùng thường xuyên.

**Nhóm C:** Day 07 — Advanced Patterns (DLX, TTL, Retry). Học sau khi đã làm basic project.

**Nhóm D:** Day 08 (Clustering HA) + Day 09 (Performance Production). Đọc lướt, tra cứu khi cần.

### Phase 3: Kafka (Days 10-23)

**Nhóm A:** Day 10 (Kafka Fundamentals) + Day 11 (Producer Internals) + Day 12 (Consumer Internals) + Day 13 (Replication & ISR) + Day 15 (Delivery Semantics & Idempotency). Core Kafka — distributed log, producer batching, consumer groups, replication, delivery guarantees.

**Nhóm B:** Day 14 (ZooKeeper vs KRaft) + Day 16 (Schema Management) + Day 20 (Performance Tuning). Học sớm để hiểu operations.

**Nhóm C:** Day 17 (Kafka Connect + CDC) + Day 18 (Kafka Streams basics) + Day 19 (Kafka Streams advanced) + Day 21 (Capacity Planning) + Day 22 (Security & Multi-tenancy) + Day 23 (Production Operations). Học sau khi làm basic project.

### Phase 4: Tổng hợp & Capstone (Days 24-25)

**Nhóm A:** Day 24 — So sánh 3 Brokers. Decision matrix, biết chọn đúng broker cho từng use case.

**Nhóm C:** Day 25 — Capstone. Học sau khi đã hoàn thành các phần còn lại.

## Mini project đề xuất

### Project 1: Event-Driven Order System
Xây dựng order processing với Kafka (event backbone) + RabbitMQ (task queue với retry/DLX) + NATS (real-time push). Áp dụng outbox pattern, idempotent consumer, saga choreography.

### Project 2: Log Aggregation Pipeline
Dùng Kafka Connect + Kafka Streams để ingest logs, filter, enrich và route đến Elasticsearch. Áp dụng schema management với Avro/Protobuf.

### Project 3: Chat Application với NATS
Xây dựng real-time chat với NATS pub/sub + JetStream cho message history. Áp dụng subject hierarchy, queue groups, leaf nodes.

## Checklist học nhanh

- [ ] Tôi đã hiểu sync vs async communication và 3 messaging models
- [ ] Tôi đã phân biệt được broker vs distributed log
- [ ] Tôi đã học xong nhóm A (Days 1, 4, 10, 11, 12, 13, 15, 24)
- [ ] Tôi đã làm được mini project đầu tiên
- [ ] Tôi đã hiểu delivery guarantees (at-most-once, at-least-once, exactly-once)
- [ ] Tôi đã biết khi nào chọn Kafka, RabbitMQ, hay NATS
