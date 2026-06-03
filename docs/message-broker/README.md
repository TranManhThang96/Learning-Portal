# 🚀 Message Broker Learning Path — NATS, RabbitMQ & Kafka trong 25 ngày

## Tổng quan

Khóa học 25 ngày dành cho Senior Developer muốn master 3 message brokers phổ biến nhất: **NATS**, **RabbitMQ**, và **Kafka**. Mỗi ngày học 2 giờ (lý thuyết + hands-on lab), nội dung được chia thành 3 mức: Must Learn, Should Learn, và Optional Deep Dive.

## Yêu cầu

- Docker & Docker Compose
- Go 1.21+ hoặc Node.js 20+ (TypeScript)
- IDE: VS Code hoặc GoLand
- Terminal: bash/zsh

## Lộ trình

### 🟢 Phase 1: Messaging Fundamentals + NATS (Day 1-3)

| Ngày | Chủ đề | Trạng thái |
|------|--------|------------|
| [Day 1](./day-01-messaging-fundamentals-and-nats-basics/lesson.md) | Messaging Fundamentals + NATS Core Concepts | ⬜ |
| [Day 2](./day-02-nats-jetstream/lesson.md) | NATS JetStream — Persistence & Streaming | ⬜ |
| [Day 3](./day-03-nats-production/lesson.md) | NATS Production — Clustering, Security, Monitoring | ⬜ |

### 🟡 Phase 2: RabbitMQ (Day 4-9)

| Ngày | Chủ đề | Trạng thái |
|------|--------|------------|
| [Day 4](./day-04-amqp-protocol/lesson.md) | AMQP Protocol — Exchange, Queue, Binding, Routing | ⬜ |
| [Day 5](./day-05-exchange-types/lesson.md) | Exchange Types — Direct, Fanout, Topic, Headers | ⬜ |
| [Day 6](./day-06-reliability/lesson.md) | Reliability — Publisher Confirms, Quorum Queues | ⬜ |
| Day 7 | Advanced Patterns — DLX, TTL, Priority, Retry | ⬜ |
| Day 8 | Clustering & HA — Quorum Queues, Federation | ⬜ |
| Day 9 | Performance Tuning & Production Operations | ⬜ |

### 🔴 Phase 3: Kafka (Day 10-23)

| Ngày | Chủ đề | Trạng thái |
|------|--------|------------|
| Day 10 | Kafka Fundamentals — Distributed Commit Log | ⬜ |
| Day 11 | Producer Internals — Batching, Compression, Acks | ⬜ |
| Day 12 | Consumer Internals — Consumer Group, Rebalance | ⬜ |
| Day 13 | Replication & ISR — Leader/Follower, Durability | ⬜ |
| Day 14 | ZooKeeper vs KRaft — Metadata Management | ⬜ |
| Day 15 | Delivery Semantics + Idempotency Patterns | ⬜ |
| Day 16 | Schema Management — Schema Registry, Avro/Protobuf | ⬜ |
| Day 17 | Kafka Connect + CDC — Debezium, Outbox Pattern | ⬜ |
| Day 18 | Kafka Streams Cơ bản — KStream, KTable | ⬜ |
| Day 19 | Kafka Streams Nâng cao — Windowing, Joins, State | ⬜ |
| Day 20 | Performance Tuning — Producer, Consumer, Broker | ⬜ |
| Day 21 | Capacity Planning & Sizing | ⬜ |
| Day 22 | Security & Multi-tenancy | ⬜ |
| [Day 23](./day-23-production-operations-observability/lesson.md) | Production Operations + Observability | ⬜ |

### 🏆 Phase 4: Tổng hợp & Capstone (Day 24-25)

| Ngày | Chủ đề | Trạng thái |
|------|--------|------------|
| [Day 24](./day-24-broker-comparison/lesson.md) | So sánh 3 Brokers — Decision Matrix | ⬜ |
| [Day 25](./day-25-capstone/lesson.md) | Capstone Project — E-commerce Event-Driven System | ⬜ |

## Nguyên tắc học

- **Must Learn** 🔴: Bắt buộc hoàn thành trong 2 giờ
- **Should Learn** 🟡: Nên học nếu còn thời gian
- **Optional Deep Dive** 🟢: Đào sâu khi muốn nghiên cứu thêm

## Cấu trúc mỗi ngày

```
day-XX-topic/
├── lesson.md       # Bắt buộc — lý thuyết + hands-on lab
├── document.md     # Tùy chọn — tài liệu tham khảo sâu
└── exercises.md    # Tùy chọn — bài tập thực hành bổ sung
```
