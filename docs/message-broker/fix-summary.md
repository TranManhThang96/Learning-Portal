# Fix Summary

Date: 2026-05-07

## Scope

Đã thực hiện theo `fix-review.md`: đọc learning plan, xử lý các issue trong `review.md` bằng 5 batch song song, mỗi batch chỉ sửa đúng 5 lesson trong phạm vi được giao.

## Files Changed

### Lesson 01-05

- `day-01-messaging-fundamentals-and-nats-basics/lesson.md`
- `day-02-nats-jetstream/lesson.md`
- `day-02-nats-jetstream/exercises.md`
- `day-03-nats-production/lesson.md`
- `day-04-amqp-protocol/lesson.md`
- `day-05-exchange-types/lesson.md`

Main fixes:

- Làm rõ benchmark assumptions, JetStream flag ở Day 1, correlation/causation/logging convention.
- Sửa JetStream dedup wording: không gọi là exactly-once end-to-end; thêm WorkQueue/MaxDeliver nuance và poison advisory exercise.
- Sửa NATS production routing theo interest-based routing, JetStream API permissions và scope TLS.
- Sửa RabbitMQ consume model là push-based với prefetch, thêm publisher confirms boundary, FIFO nuance và tránh infinite requeue.
- Sửa RabbitMQ topic vs NATS wildcard, thêm headers exchange mini lab và caveat alternate exchange/performance.

### Lesson 06-10

- `day-06-reliability/lesson.md`
- `day-07-advanced-patterns/lesson.md`
- `day-07-advanced-patterns/exercises.md`
- `day-08-clustering-ha/lesson.md`
- `day-09-performance-production/lesson.md`
- `day-10-kafka-fundamentals/lesson.md`

Main fixes:

- Cập nhật RabbitMQ quorum queue behavior hiện hành, publisher confirms boundary và retry sau `QueueDeclare` bằng channel mới.
- Sửa TTL overflow `int32(2592000000)`, chuyển quorum DLX at-least-once sang policy, thêm overflow behavior và exercises cho DLQ replay/idempotency.
- Sửa RabbitMQ HA lab: persistent partition handling, `pause_if_all_down`, `NotifyPublish`, dynamic network, identify quorum leader.
- Cập nhật lazy queue là tuning lịch sử, `sh -c` cho Alpine, đổi `load_test.go` instruction, caveat Prometheus metrics, tránh concurrent ack trên cùng channel.
- Sửa Kafka fundamentals wording về consumer groups, NATS ordering, compaction/tombstone, zero-copy/TLS và thêm run commands.

### Lesson 11-15

- `day-11-producer-internals/lesson.md`
- `day-12-consumer-internals/lesson.md`
- `day-13-replication-isr/lesson.md`
- `day-14-zookeeper-vs-kraft/lesson.md`
- `day-15-delivery-semantics-idempotency/lesson.md`

Main fixes:

- Sửa `acks=all` vs `min.insync.replicas`, idempotence default scope và batching demo.
- Tách heartbeat/session timeout khỏi `max.poll.interval.ms`, thêm static membership, commit-on-revoke và PowerShell equivalents.
- Thêm durability qualifiers, đổi runnable Go filename khỏi `*_test.go`, thêm unclean election demo có điều kiện và cleanup.
- Làm rõ Kafka 4.x KRaft-only, migration từ ZooKeeper là rolling bridge mode trong Kafka 3.x, detect active controller và tránh hardcoded metadata path/cluster id.
- Scope lại Day 15 lab thành idempotent consumer + outbox thay vì hứa transaction lab chưa có; thêm LSO/transaction timeout nuance và duplicate/crash acceptance tests.

### Lesson 16-20

- `day-16-schema-management/lesson.md`
- `day-17-kafka-connect-cdc/lesson.md`
- `day-18-kafka-streams-basics/lesson.md`
- `day-19-kafka-streams-advanced/lesson.md`
- `day-20-performance-tuning/lesson.md`

Main fixes:

- Thêm contract test cho compatibility check và sample deserialize; giữ đúng backward/forward compatibility và dual-listener guidance.
- Sửa CDC lab details: `pgcrypto`, replication slot lag check, outbox cleanup không do Debezium tự xóa.
- Cập nhật `SafeDeserializationHandler` theo API Kafka Streams hiện hành.
- Giữ/củng cố stream-time grace, EOS scope, Interactive Queries caveat và RF=1 caveat.
- Sửa listener single-broker, thêm optional 3-broker benchmark compose snippet và ISR shrink drill.

### Lesson 21-25

- `day-21-capacity-planning/lesson.md`
- `day-21-capacity-planning/docker-compose.yml`
- `day-22-security-multi-tenancy/lesson.md`
- `day-23-production-operations-observability/lesson.md`
- `day-23-production-operations-observability/grafana-kafka-lag-dashboard.json`
- `day-24-broker-comparison/lesson.md`
- `day-25-capstone/lesson.md`

Main fixes:

- Day 21 có compose, tách benchmark 1-partition vs N-partition, inbound/outbound NIC và acceptance checklist.
- Day 22 đã có deny-by-default ACL wording, SASL/PLAIN risk, không dùng `User:ANONYMOUS` superuser và KRaft `StandardAuthorizer` path.
- Day 23 thêm dashboard JSON tối thiểu, caveat metrics/JMX exporter rules, hot partition và tracing/correlation logging scope.
- Day 24 sửa exactly-once boundary, RabbitMQ confirms vs transaction, NATS subjects không phải partition, benchmark checks và profile split.
- Day 25 scope thành design-only/reference snippets thay vì overclaim runnable; sửa event schema, idempotent at-least-once, SQL index và acceptance checklist.

## Not Fully Fixed

- Fixed in follow-up: Day 16-20, 22-23 compose snippets đã được chuyển sang KRaft-only baseline; không còn `cp-zookeeper`, `KAFKA_ZOOKEEPER_CONNECT` hoặc depends-on ZooKeeper trong các ngày này.
- Fixed in follow-up: Các lesson dài Day 16-20, 22-23 và Day 25 đã có companion `document.md`/`exercises.md`, đồng thời `lesson.md` có link ở đầu file để tách phần deep-dive/lab drill khỏi bài chính.
- Fixed in follow-up: Day 25 đã có scaffold runnable thật với `docker-compose.yml`, `go.mod`, `shared/`, và 4 services: `order-service`, `payment-service`, `inventory-service`, `notification-service`.
- Partially fixed in follow-up: Đã compile/build/run scaffold Day 25 end-to-end. Chưa compile/run mọi code block trong toàn bộ markdown vì nhiều block vẫn là snippet rời, không có project/module tương ứng để build tự động mà không biến từng lesson thành repo con.

## Follow-up Verification 2026-05-07

- `rg` scan xác nhận Day 16-20, 22-23 không còn ZooKeeper compose config cũ: `cp-zookeeper`, `ZOOKEEPER_CLIENT_PORT`, `KAFKA_ZOOKEEPER_CONNECT`.
- `docker run --rm -v ${PWD}:/src -w /src golang:1.22-alpine go test ./...` trong `day-25-capstone` pass.
- `docker compose config --quiet` trong `day-25-capstone` pass.
- `docker compose build` trong `day-25-capstone` pass cho cả 4 services.
- End-to-end Day 25 verified bằng Docker network: create order → outbox publish `order.created.v1` → payment completed → inventory reserved → notification logs → order status `CONFIRMED`.
- `docker compose down` đã được chạy sau verification để không giữ container chạy nền.

## Verification

- Kiểm tra `git status --short` để xác nhận phạm vi thay đổi.
- Chạy keyword scan cho các rủi ro review chính: `exactly-once`, ZooKeeper/KRaft, lazy queue, `load_test.go`, `int32(2592000000)`, `ANONYMOUS`, `NO data loss`, `acks=all`, `min.insync.replicas`, ACL default.
- Sửa thêm các overclaim còn sót trong Day 08 và Day 09 sau keyword scan.
- Chạy `git diff --check` sau khi hoàn tất.

## Remaining Risk

- Một số Docker/Kafka/RabbitMQ commands phụ thuộc image version và listener name thực tế, cần chạy trên máy sạch để xác nhận end-to-end.
- Prometheus/JMX alert expressions vẫn nên validate bằng output `/metrics` thực tế.
- Các code block Go/Java trong markdown chưa được tách thành project riêng để compile tự động.
