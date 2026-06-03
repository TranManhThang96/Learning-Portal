# Course Review

## Executive Summary

Khóa học có nền tảng tốt: 25 bài đều có cấu trúc nhất quán theo learning plan, bao phủ đúng NATS, RabbitMQ, Kafka, production operations và capstone. Nội dung có nhiều WHY/WHAT/HOW, trade-off, pitfalls, performance notes, self-check questions và lab thực tế hơn mức tutorial cơ bản.

Điểm trung bình hiện tại khoảng **7.0/10**. Vấn đề lớn nhất không phải thiếu nội dung, mà là **quá nhiều nội dung trong một `lesson.md`**, **nhiều lab chưa runnable**, và **một số điểm kỹ thuật/version đã lệch với Kafka/RabbitMQ hiện hành**. Toàn bộ 25 thư mục hiện chỉ có `lesson.md`, không có `document.md` hoặc `exercises.md`, trong khi nhiều bài dài 50-72KB và 1,400-1,900 dòng. Điều này trái với mục tiêu học 2 giờ/ngày.

Các ưu tiên sửa trước khi tiếp tục mở rộng course:

1. Chuẩn hóa version target: Kafka KRaft, RabbitMQ 3.13/4.x, NATS server/client versions.
2. Sửa lỗi kỹ thuật High priority: Kafka KRaft/ZooKeeper inconsistency, RabbitMQ lazy/quorum details, Kafka delivery semantics, Schema Registry/CDC/Streams lab.
3. Tách file: giữ `lesson.md` cho Must Learn, đưa deep dive sang `document.md`, đưa lab mở rộng/challenges sang `exercises.md`.
4. Chạy lại và làm runnable từng lab: compose, `go.mod`, Gradle main class, `_test.go`, plugin dependencies, expected output, cleanup.
5. Làm lại Day 25 capstone thành scaffold chạy end-to-end hoặc giảm scope rõ ràng.

## Score Table

| Lesson | Title | Score | Main Issues | Priority |
|---|---|---:|---|---|
| 01 | Messaging Fundamentals + NATS Core Concepts | 8.0 | Dài cho ngày nền tảng; benchmark/latency thiếu điều kiện; lab thiếu correlation ID/log convention | Medium |
| 02 | NATS JetStream | 7.0 | Overclaim "exactly-once"; WorkQueue/MaxDeliver cần nuance; consumer lab có thể fail nếu stream chưa tồn tại | High |
| 03 | NATS Production | 7.0 | Quá tải; cluster/leaf routing giải thích quá rộng; JetStream permissions/TLS lab cần kiểm tra | High |
| 04 | AMQP Protocol | 7.0 | RabbitMQ consumer bị mô tả như pull-based; durable+persistent thiếu publisher confirms; lab có infinite requeue | High |
| 05 | Exchange Types | 7.0 | Sai so sánh NATS wildcard; quá dài; mục tiêu headers exchange nhưng lab không thực hành headers | High |
| 06 | Reliability | 8.0 | Dài; quorum TTL/feature matrix cần cập nhật; retry sau `QueueDeclare` lỗi có thể dùng channel đã đóng | Medium |
| 07 | Advanced Patterns | 7.5 | `int32(2592000000)` không compile; quorum DLX strategy nên dùng policy; quá nhiều pattern trong 1 bài | High |
| 08 | Clustering & HA | 7.2 | Publisher confirms chưa được đọc; partition handling không persistent; thiếu `pause_if_all_down`; network command brittle | High |
| 09 | Performance & Production | 6.8 | Lazy queues outdated; `go run load_test.go` không chạy; Prometheus metric path/prefix dễ sai; Alpine `bash` rủi ro | High |
| 10 | Kafka Fundamentals | 8.1 | Concept tốt; thiếu lệnh chạy Go app; vài claim Kafka/NATS quá tuyệt đối; metadata verify brittle | Medium |
| 11 | Producer Internals | 7.0 | Nhầm `acks=all` với `min.insync.replicas`; lab batching/idempotence chưa chứng minh claim; code lỗi trong lesson | High |
| 12 | Consumer Internals | 8.0 | Lý thuyết tốt; cần nuance heartbeat vs `max.poll.interval.ms`; lab assignment/rebalance chưa đo trực tiếp | Medium |
| 13 | Replication & ISR | 8.0 | Theory mạnh; unclean election lab chưa bật/chứng minh unclean election; `_test.go` không runnable bằng `go run` | Medium |
| 14 | ZooKeeper vs KRaft | 7.0 | Migration path đơn giản hóa; KRaft lab brittle; hardcode controller/path/cluster id | High |
| 15 | Delivery Semantics + Idempotency | 6.5 | Quá rộng; hứa Kafka transactions nhưng lab không có transaction/read_committed thực tế | High |
| 16 | Schema Management | 6.5 | Backward/forward bị đảo trong timeline; Docker listener có thể fail; Go Avro lab không compile/không khớp schema | High |
| 17 | Kafka Connect + CDC | 6.8 | ES connector không có trong image; replication slot conflict; CDC guarantee bị overclaim; outbox cleanup mô tả sai | High |
| 18 | Kafka Streams Basic | 7.0 | `EXACTLY_ONCE_V2` thiếu single-broker configs; Gradle main class không chạy đúng; handler không cấu hình; `groupBy` xếp sai | High |
| 19 | Kafka Streams Advanced | 7.2 | Grace/late events chưa nói theo stream-time; Interactive Queries thiếu REST/forwarding; "NO data loss" quá tuyệt đối | High |
| 20 | Performance Tuning | 7.3 | Benchmark single broker dễ suy diễn sai; durable test chưa production-durable; tuning advice quá tuyệt đối | Medium |
| 21 | Capacity Planning & Sizing | 7.0 | Thiếu compose; benchmark "per partition" nhưng topic 12 partitions; network sizing full-duplex dễ gây hiểu nhầm | High |
| 22 | Security & Multi-tenancy | 6.5 | ACL default cần kiểm chứng/sửa; lab dùng ZooKeeper, PLAINTEXT và `ANONYMOUS` superuser; thiếu KRaft security path | High |
| 23 | Production Operations + Observability | 6.0 | Alert queries không khớp JMX rules; thiếu node-exporter/dashboard; code chỉ correlation logging, chưa OpenTelemetry | High |
| 24 | Broker Comparison | 6.5 | Exactly-once bị oversell; benchmark không compile/không công bằng; matrix cần caveat mạnh | Medium |
| 25 | Capstone | 5.0 | Không runnable end-to-end; compose thiếu services; topic mapping lệch design; saga compensation/timeout chưa implement | High |

## Cross-Lesson Issues

1. **Scope 2 giờ chưa thực tế**

   Tất cả thư mục chỉ có `lesson.md`. Các bài RabbitMQ advanced, Kafka Streams, observability và capstone đã thành handbook hơn là lesson 2 giờ. Day 18, 19, 23, 25 đặc biệt quá tải. Cần áp dụng rule:

   - `lesson.md`: Must Learn + 1 primary lab.
   - `document.md`: internals, reference matrix, benchmark caveat, production runbook.
   - `exercises.md`: extra labs, troubleshooting, quiz, design drills.

2. **Runnability là rủi ro lớn nhất**

   Nhiều lab thiếu `docker-compose.yml`, `go.mod`, Gradle wrapper/main override, plugin install, expected output hoặc cleanup. Một số file tên `*_test.go` nhưng hướng dẫn `go run`, Go sẽ từ chối chạy. Một số Docker/Prometheus/JMX commands phụ thuộc môi trường hoặc metric names chưa được validate.

3. **Kafka KRaft/ZooKeeper không nhất quán**

   Day 10 và Day 14 dạy KRaft, nhưng Day 16-20, Day 22-23 quay lại `cp-zookeeper`/`KAFKA_ZOOKEEPER_CONNECT`. Theo Apache Kafka 4.x, ZooKeeper mode đã bị loại bỏ, nên labs phải chuyển sang KRaft hoặc ghi rõ lab đang dùng bridge/legacy Kafka 3.x và không đại diện cho Kafka 4.x production.

4. **Delivery semantics bị overclaim ở nhiều nơi**

   JetStream dedup window, Kafka idempotent producer, Kafka Streams EOS và broker-level confirms đều bị diễn đạt quá gần "exactly-once end-to-end". Course cần một wording xuyên suốt: exactly-once là phạm vi cụ thể của broker/client/framework; end-to-end vẫn cần idempotent consumer, dedup key, inbox/outbox, transaction boundary và xử lý external side effects.

5. **Benchmark/performance numbers thiếu điều kiện**

   Nhiều bảng throughput/latency dùng số tuyệt đối mà thiếu message size, batching, compression, replication factor, hardware, persistence mode và client concurrency. Cần chuyển số benchmark sang "order of magnitude" hoặc kèm assumptions rõ.

6. **Version matrix cần đặt ở README hoặc document chung**

   Nên có bảng version target: NATS server/client, RabbitMQ 3.13 vs 4.x, Kafka/Confluent image, Kafka Streams, Debezium, Schema Registry, Elasticsearch connector, Go/JDK/Gradle. Điều này giảm lỗi như lazy queue, classic mirrored queue, KRaft security, Schema Registry listeners và connector availability.

7. **Observability chưa nhất quán từ đầu khóa**

   Learning plan yêu cầu correlation ID, causation ID, trace context, structured logging và metrics tối thiểu. Hiện các lab đầu khóa thường chưa có correlation/log schema, còn Day 23 mới giới thiệu sâu. Nên thêm message headers/log convention tối thiểu từ Day 1/4/10.

8. **Failure drills thiếu acceptance criteria và cleanup**

   Nhiều bài có `docker stop`, network partition, poison message, producer failure, consumer lag, nhưng thiếu cách xác định leader/controller trước khi kill, expected output, restore steps, cleanup topic/group/queue và warning destructive.

9. **Client/library choice đôi khi lệch mục tiêu**

   Kafka idempotent producer và transactions được dạy sâu nhưng lab dùng `segmentio/kafka-go`, không thể hiện rõ idempotent producer/transactions như Java client hoặc `confluent-kafka-go`. Nếu giữ Go, phải chọn client phù hợp hoặc đổi mục tiêu lab.

10. **README chưa là entry point hoàn chỉnh**

   README có overview tốt nhưng link checklist không nhất quán: một số days có link, nhiều days chỉ là text. Nên link đủ 25 lessons và thêm trạng thái `Needs Review` hoặc `Runnable Verified`.

Technical reference checks used for high-risk points:

- Apache Kafka 4.0 upgrade notes: https://kafka.apache.org/40/getting-started/upgrade/
- Apache Kafka KRaft operations: https://kafka.apache.org/42/operations/kraft/
- Apache Kafka Streams processing guarantee: https://kafka.apache.org/42/streams/developer-guide/config-streams/
- Apache Kafka producer configs/idempotence: https://kafka.apache.org/40/configuration/producer-configs/
- RabbitMQ quorum queues: https://www.rabbitmq.com/docs/quorum-queues
- RabbitMQ classic queue mirroring deprecation/removal: https://www.rabbitmq.com/docs/3.13/ha
- NATS JetStream consumers: https://docs.nats.io/nats-concepts/jetstream/consumers

## Detailed Review

### Lesson 01 - Messaging Fundamentals + NATS Core Concepts

Score: **8.0/10**. Priority: **Medium**.

Strong foundation lesson with good framing of synchronous vs asynchronous communication, queue/pub-sub/stream, and NATS core. Main issue is density: Day 1 already includes NATS core, queue groups, request-reply, Go examples and monitoring.

Recommended fixes:

- Add assumptions beside all benchmark/latency numbers.
- Clarify why Docker enables `--js` on Day 1 if JetStream is not taught until Day 2.
- Add minimal correlation ID and structured logging convention.
- Move Go request-reply and optional monitoring to `exercises.md`.

### Lesson 02 - NATS JetStream

Score: **7.0/10**. Priority: **High**.

The JetStream mental model is useful, but delivery guarantees need sharper wording. `Nats-Msg-Id` provides duplicate suppression within a dedup window, not end-to-end exactly-once processing.

Recommended fixes:

- Replace "exactly-once" wording with "at-least-once + publisher dedup window".
- Explain WorkQueue retention constraints and consumer/filter overlap.
- Clarify that MaxDeliver stops redelivery/emits advisory; message retention depends on stream policy.
- Make consumer lab create/verify stream or require setup publisher first.
- Add exercise for poison message advisory to DLQ-like stream.

### Lesson 03 - NATS Production

Score: **7.0/10**. Priority: **High**.

Good production topics, but too many concepts for one 2-hour lesson: clustering, leaf nodes, auth, TLS, monitoring, Prometheus and HA lab.

Recommended fixes:

- Correct cluster/leaf explanation: NATS uses interest-based routing; avoid saying every message is routed to every node.
- Recheck JetStream API permissions: clients usually publish to `$JS.API.>` and subscribe to reply inboxes.
- Either add a small TLS lab or move TLS to Should/Optional.
- Create `document.md` for security, leaf/super-cluster, monitoring thresholds.
- Create `exercises.md` for HA drills and Prometheus/Grafana.

### Lesson 04 - AMQP Protocol

Score: **7.0/10**. Priority: **High**.

The AMQP concept explanation is strong, but one technical framing is dangerous: RabbitMQ `basic.consume` is push delivery with prefetch/credit-style flow control, not pull-based consumption. `basic.get` is the polling-style API.

Recommended fixes:

- Rewrite RabbitMQ consumer model as "push-based with consumer-side flow control via prefetch".
- State that durable queue + persistent message is not enough; publisher confirms are required for reliable publish acknowledgement.
- Add FIFO nuance for multiple consumers, prefetch, priority, redelivery and requeue.
- Avoid infinite `Nack(requeue=true)` in lab; add max attempts or stop after observation.
- Move AMQP frame/channel internals to `document.md`.

### Lesson 05 - Exchange Types

Score: **7.0/10**. Priority: **High**.

Direct/fanout/topic coverage is useful, but the comparison with NATS wildcard is wrong: NATS supports `*` in the middle, while `>` only appears at the end and is not identical to RabbitMQ `#`.

Recommended fixes:

- Correct RabbitMQ topic vs NATS wildcard comparison.
- Add a headers exchange mini lab or reduce headers from learning objective.
- Treat alternate exchange as one strategy, not mandatory for every production exchange.
- Add caveats to exchange performance numbers.
- Split full exchange matrix and cleanup/API drills into `document.md` and `exercises.md`.

### Lesson 06 - Reliability

Score: **8.0/10**. Priority: **Medium**.

Rich reliability lesson covering publisher confirms, ack/nack, durability and quorum queues. It needs version cleanup and scope reduction.

Recommended fixes:

- Update quorum queue feature matrix for current RabbitMQ behavior.
- Reopen AMQP channel after `QueueDeclare` failure before retrying with fallback queue arguments.
- Reinforce publisher confirms as the publish-side reliability boundary.
- Reduce overlap with Day 9 prefetch/performance.
- Move quorum/Raft internals and benchmark caveats to `document.md`.

### Lesson 07 - Advanced Patterns

Score: **7.5/10**. Priority: **High**.

The retry/DLX flow is practical, but the lesson contains compile and configuration risks.

Recommended fixes:

- Fix `int32(2592000000)` overflow for 30-day TTL.
- Teach quorum queue at-least-once dead-lettering via policy, not as a misleading queue argument.
- Explain overflow behavior (`drop-head`, `reject-publish`) and its effect on dead-lettering.
- Move RPC and delayed exchange plugin deeper into `document.md`.
- Add `exercises.md` for DLQ replay, jitter, error classification and idempotency key.

### Lesson 08 - Clustering & HA

Score: **7.2/10**. Priority: **High**.

Good 3-node clustering direction, but failure labs need to prove the guarantee they claim.

Recommended fixes:

- Read publisher confirms with `NotifyPublish` before saying failover publish succeeded.
- Configure partition handling in `rabbitmq.conf`, not transient `rabbitmqctl eval`.
- Add `pause_if_all_down` and clarify when it is appropriate.
- Resolve Compose network name dynamically instead of hardcoding.
- Identify quorum queue leader before stopping a node.
- Move federation/shovel details to `document.md`.

### Lesson 09 - Performance & Production

Score: **6.8/10**. Priority: **High**.

The lesson is useful but has several runnable/version issues.

Recommended fixes:

- Update lazy queue content: old `x-queue-mode=lazy` tuning is no longer a valid current lever in recent RabbitMQ versions.
- Rename `load_test.go` to a non-`*_test.go` file if it is meant for `go run`.
- Use `sh -c` for Alpine containers or switch image.
- Validate Prometheus metric names and `/metrics/detailed` prefixes.
- Avoid concurrent acking on one AMQP channel unless client library safety is proven.
- Split OS tuning, Streams vs Kafka and Grafana alert labs into separate files.

### Lesson 10 - Kafka Fundamentals

Score: **8.1/10**. Priority: **Medium**.

Good first Kafka lesson with distributed log, topic/partition/offset and KRaft lab. It needs a few precision edits and practical commands.

Recommended fixes:

- Say Kafka is not a classic queue, but consumer groups provide queue-like competing consumers.
- Nuance NATS core ordering instead of saying no guarantee broadly.
- Explain log compaction is not immediate and tombstone/delete retention matters.
- Add TLS/zero-copy caveat.
- Add explicit commands to run Go producer/consumer.
- Prefer practical cluster verification commands over hardcoded metadata snapshot paths.

### Lesson 11 - Producer Internals

Score: **7.0/10**. Priority: **High**.

This is a key Kafka lesson, but it has a correctness issue around `acks=all`.

Recommended fixes:

- Fix explanation: `acks=all` waits for current ISR acknowledgements; `min.insync.replicas` is the minimum ISR count required to accept writes.
- Make idempotence default statement consistent with target Kafka version.
- Do not include intentionally broken code in a copy-paste lesson unless clearly isolated as an exercise.
- Use official perf tools or a batch-aware client pattern to demonstrate batching.
- Consider Java or `confluent-kafka-go` for idempotent producer features.

### Lesson 12 - Consumer Internals

Score: **8.0/10**. Priority: **Medium**.

The consumer group, assignment, rebalance and offset content is generally solid.

Recommended fixes:

- Separate heartbeat/session timeout from `max.poll.interval.ms` behavior.
- Add static membership and commit-on-revoke practice.
- Use `kafka-consumer-groups.sh --describe --members --verbose` to show real assignment.
- Add PowerShell equivalents for environment-variable run commands.
- Move detailed assignment strategy comparison to `document.md`.

### Lesson 13 - Replication & ISR

Score: **8.0/10**. Priority: **Medium**.

Strong ISR/HW/LEO explanation. Failure demos need more rigor.

Recommended fixes:

- Qualify durability claims with `min.insync.replicas`, leader availability and unclean leader election settings.
- Rename runnable files away from `*_test.go` if using `go run`.
- For unclean election demo, explicitly enable it on a throwaway topic/cluster and verify truncation/data loss.
- Add restore/cleanup steps after broker failure simulations.
- Move high-watermark and replication protocol deep dive to `document.md`.

### Lesson 14 - ZooKeeper vs KRaft

Score: **7.0/10**. Priority: **High**.

Conceptual KRaft content is good, but migration and ops need current version scoping.

Recommended fixes:

- State clearly: Kafka 4.x supports KRaft only; ZooKeeper clusters must migrate before upgrading to 4.x.
- Replace simplified export/import migration with an accurate migration runbook or link to official docs.
- Detect active controller before failover test instead of assuming `kafka-1`.
- Avoid hardcoded metadata path and cluster id.
- Create `document.md` for ZK internals, Raft, migration and operational caveats.

### Lesson 15 - Delivery Semantics + Idempotency

Score: **6.5/10**. Priority: **High**.

The main message is right: exactly-once is an end-to-end design problem. The lab does not yet match the promised Kafka transactions scope.

Recommended fixes:

- Either add a real Kafka transaction lab (`InitTransactions`, transactional producer, send offsets to transaction, `read_committed`) or change the lab objective to idempotent consumer + outbox.
- Nuance transaction timeout/LSO behavior after producer crash before commit.
- Split Kafka transactions, inbox/outbox and performance into separate files.
- Add duplicate event and crash-recovery acceptance tests.

### Lesson 16 - Schema Management

Score: **6.5/10**. Priority: **High**.

Important topic, but the schema evolution section has a backward/forward confusion and the lab likely fails.

Recommended fixes:

- Correct backward compatibility wording and deployment timeline.
- Use dual Kafka listeners for host and container-to-container traffic.
- Align Avro schema versions with Go structs.
- Fix missing imports/API usage or simplify to one primary language path.
- Add contract testing exercise with compatibility check and sample deserialize.

### Lesson 17 - Kafka Connect + CDC

Score: **6.8/10**. Priority: **High**.

Good progression after Schema Registry, but the CDC lab has connector and guarantee issues.

Recommended fixes:

- Use an image containing Elasticsearch sink connector or install it explicitly.
- Set unique `slot.name` and `publication.name` for multiple Debezium connectors.
- Correct CDC guarantee to at-least-once; require idempotent sink.
- Add `REPLICA IDENTITY FULL` if demo needs full `before` image.
- Correct outbox cleanup: Debezium reads changes, it does not delete outbox rows.
- Add `/connector-plugins`, replication slot lag and connector restart checks.

### Lesson 18 - Kafka Streams Basic

Score: **7.0/10**. Priority: **High**.

Concept flow is good, but several lab details undermine runnable quality.

Recommended fixes:

- Move `groupBy`/`groupByKey` out of pure stateless operations; call them repartition/stateful boundaries.
- Add transaction state log configs for single-broker `EXACTLY_ONCE_V2`, or remove EOS from the basic lab.
- Wire Gradle `-PmainClass` into `build.gradle`.
- Actually configure `SafeDeserializationHandler`.
- Avoid mutating the same `Order` object in `mapValues`.
- Move TopologyTestDriver and failure scenario extras to `exercises.md`.

### Lesson 19 - Kafka Streams Advanced

Score: **7.2/10**. Priority: **High**.

Good coverage of stateful processing, but some semantics are oversimplified.

Recommended fixes:

- Explain grace/late events using stream-time, not wall clock.
- Clarify EOS scope: Kafka output, offsets and changelog/state restore; not arbitrary external side effects.
- Build real Interactive Queries with REST endpoint and metadata forwarding, or adjust objective.
- Fix `hourlyRevenue` naming if window is 5 minutes.
- Avoid "NO data loss" claims when lab uses RF=1.

### Lesson 20 - Performance Tuning

Score: **7.3/10**. Priority: **Medium**.

Useful performance methodology, but local benchmark results are too easy to misread as production truth.

Recommended fixes:

- Label single-broker benchmark as local demo only.
- Add optional 3-broker compose for replication/durability tests.
- Avoid absolute advice like "always lz4" or "never gzip"; make them defaults with exceptions.
- Update disk scheduler advice for modern Linux (`mq-deadline`/`none` depending on kernel/device).
- Add failure scenario: buffer full, max poll exceeded, ISR shrink with `acks=all`.

### Lesson 21 - Capacity Planning & Sizing

Score: **7.0/10**. Priority: **High**.

The formulas are useful, but lab setup and measurement need corrections.

Recommended fixes:

- Include or link the required `docker-compose.yml`.
- Use a 1-partition topic for per-partition benchmark and N-partition topic for scaling benchmark.
- Compare NIC inbound/outbound separately with headroom, or explicitly label aggregate math as conservative.
- Use peak throughput, consumer throughput and ordering groups in calculator.
- Fix `du -sh | awk` unit math.
- Add a capacity planning checklist.

### Lesson 22 - Security & Multi-tenancy

Score: **6.5/10**. Priority: **High**.

Security lesson has good topics, but defaults and lab mode need to be safer.

Recommended fixes:

- Recheck and correct `allow.everyone.if.no.acl.found` default/meaning; teach deny-by-default explicitly.
- Clarify SASL/PLAIN risk: without TLS it exposes credentials in transit; with TLS, storage/rotation are still concerns.
- Do not use `User:ANONYMOUS` as superuser unless clearly labeled lab-only and never exposed.
- Add a KRaft + `StandardAuthorizer` path instead of ZooKeeper-only security lab.
- Add verify checklist: anonymous denied, wrong ACL denied, TLS hostname validation, quota throttling metric.

### Lesson 23 - Production Operations + Observability

Score: **6.0/10**. Priority: **High**.

This is a critical production lesson, but metric and tracing implementations need validation.

Recommended fixes:

- Validate actual `/metrics` output and align Prometheus alert expressions with exporter rules.
- Add node-exporter if using `node_filesystem_*` alerts, or remove those alerts.
- Fix JMX percentile/request metric names.
- Detect hot partitions using partition-level offsets/log dirs/exporter metrics, not broker topic aggregate metrics.
- Rename "with Tracing" to correlation logging, or implement OpenTelemetry spans.
- Add `go.mod`, run commands, dashboard JSON and slow consumer group to produce real lag.

### Lesson 24 - Broker Comparison

Score: **6.5/10**. Priority: **Medium**.

Good synthesis day, but comparison tables and benchmark must be carefully caveated.

Recommended fixes:

- Remove/qualify exactly-once claims for NATS JetStream and Kafka.
- Distinguish RabbitMQ publisher confirms from AMQP transactions.
- Do not compare NATS subjects as if they were partitions.
- Fix benchmark compile issue and setup steps.
- Split benchmark profiles: non-persistent pub/sub, persistent publish-ack, end-to-end consume.
- Prefer official tools (`nats bench`, RabbitMQ PerfTest, Kafka perf tools) or label custom benchmark as demo.

### Lesson 25 - Capstone

Score: **5.0/10**. Priority: **High**.

The architecture idea is good, but the capstone does not currently meet runnable end-to-end expectations.

Recommended fixes:

- Provide actual service scaffold: `order-service`, `payment-service`, `inventory-service`, `notification-service`, Dockerfiles, `go.mod`, run commands and compose services.
- Fix topic model so domain events go to domain topics consistently.
- Use per-service outbox/inbox or include owner/locking semantics such as `FOR UPDATE SKIP LOCKED`.
- Do not commit Kafka offset after failed processing.
- Implement refund, inventory release, timeout job, DLQ path and duplicate-event tests.
- Fix inventory logic to use order items instead of hardcoded `PROD-001`.
- Remove invalid PostgreSQL `INDEX` inside `CREATE TABLE` examples.
- Add acceptance checklist: create order, payment fail, inventory fail, duplicate event, lag/alert, cleanup.

## Recommended Fix Plan

### Phase 0 - Freeze Versions and Course Contract

1. Add `VERSIONS.md` or a README section with exact versions for NATS, RabbitMQ, Kafka/Confluent images, Schema Registry, Debezium, Kafka Streams, Go, Java and Gradle.
2. Decide whether Kafka labs target Kafka 4.x KRaft only, or Kafka 3.x bridge mode. Prefer KRaft-only for new course content.
3. Define lab acceptance standard: setup command, expected output, failure command, observed symptom, cleanup command.

### Phase 1 - Fix High-Risk Technical Errors

1. Fix Kafka KRaft/ZooKeeper inconsistency in Day 16-20 and Day 22-23.
2. Fix delivery semantics wording across Day 2, 11, 15, 18, 19, 24 and 25.
3. Fix RabbitMQ version issues in Day 6-9: quorum TTL/priority/DLX, lazy queues, classic mirrored deprecation/removal.
4. Fix Schema Registry, Connect/CDC, Streams and Observability lab correctness before adding more content.

### Phase 2 - Split Files

1. Add `document.md` and `exercises.md` for Day 3-9, 11, 14-25.
2. Keep each `lesson.md` focused on 2-hour Must Learn plus one primary lab.
3. Move long matrices, benchmark notes, internals and runbooks to `document.md`.
4. Move optional labs, incident drills, quiz expansion and design exercises to `exercises.md`.

### Phase 3 - Make Labs Runnable

1. Run every code block path on a clean machine or container.
2. Add missing `go mod init`, `go get`, Gradle config, Dockerfiles, connector plugin installation and Compose services.
3. Rename runnable Go files away from `*_test.go`.
4. Validate Prometheus/JMX metric names from actual `/metrics` output.
5. Add PowerShell equivalents where commands use POSIX environment-variable syntax.

### Phase 4 - Rework Capstone

1. Either reduce Day 25 to design-only plus pseudocode, or provide a real runnable scaffold.
2. If runnable, build four services with clear domain topics, per-service outbox/inbox, idempotency, saga compensation and observability.
3. Add test script covering happy path, payment failure, inventory failure, duplicate message, retry/DLQ and timeout.

### Phase 5 - Final QA

1. Update README links for all 25 lessons.
2. Add review status/checklist per day.
3. Add source links for version-sensitive facts.
4. Re-score after fixes, targeting all High priority lessons at 8.0+.

## Final Checklist

- [ ] All 25 lessons keep required 10-section structure.
- [ ] Every lesson has a clear 2-hour Must Learn path.
- [ ] Lessons above 1,000 lines are split into `document.md` and/or `exercises.md`.
- [ ] Kafka labs use one consistent KRaft-based setup unless explicitly marked legacy.
- [ ] RabbitMQ content is version-scoped for 3.13/4.x differences.
- [ ] No lesson claims broker/client features provide exactly-once end-to-end without explaining scope and required application patterns.
- [ ] Every lab has setup, run, expected output, failure scenario and cleanup.
- [ ] All Go/Java/TypeScript code compiles or is clearly marked pseudocode.
- [ ] All Docker Compose examples have correct listeners for host and container-to-container access.
- [ ] Prometheus/Grafana alerts match actual exported metric names.
- [ ] README links to all 25 lesson files and optional documents/exercises.
- [ ] Day 25 capstone is either runnable end-to-end or explicitly scoped as design-only.
