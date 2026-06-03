# Day 23: Production Operations + Observability — Monitoring, Tracing, Incident Response & Disaster Recovery

> Companion split: xem `document.md` để đào sâu observability/runbook và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** Kafka monitoring stack — JMX metrics, Prometheus exporter, Grafana dashboards và cách thiết kế alerting hiệu quả
2. **Nắm vững** consumer lag — tại sao là metric quan trọng nhất, cách đo, cách alert, và cách troubleshoot
3. **Thực hành** xử lý common incidents: rebalance storm, hot partition, under-replicated partitions, disk full
4. **Hiểu** distributed tracing qua Kafka — correlation ID, causation ID, OpenTelemetry integration, structured logging
5. **Biết** disaster recovery — MirrorMaker 2, cross-datacenter replication, failover/failback procedures

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-22 (Kafka fundamentals → security)
- Hiểu consumer group, partition assignment, rebalance protocol
- Hiểu replication, ISR, leader election
- Hiểu producer/consumer configuration (acks, batch.size, fetch config)
- Docker Compose Kafka cluster đang chạy
- Familiar với Prometheus query language (PromQL) cơ bản

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Kafka monitoring architecture — JMX → Prometheus → Grafana pipeline
- Key metrics: broker, producer, consumer, topic-level
- Consumer lag — definition, measurement, alerting, troubleshooting
- Common incidents — rebalance storm, hot partition, under-replicated partitions
- Distributed tracing — correlation ID, causation ID, Kafka headers
- Hands-on: Docker Compose monitoring stack + simulate incidents

### 🟡 Should Learn (nếu còn thời gian)
- OpenTelemetry integration với Kafka producer/consumer
- Structured logging best practices cho message-driven systems
- Runbook templates cho common incidents
- MirrorMaker 2 overview — active-passive replication

### 🟢 Optional Deep Dive
- MirrorMaker 2 active-active topology
- Cross-datacenter RPO/RTO analysis
- Custom JMX metrics cho application-specific monitoring
- Kafka Cruise Control — automated partition rebalancing
- Automated incident response với PagerDuty/OpsGenie integration

---

## 4. Lý thuyết (Theory)

### 4.1 Kafka Monitoring Architecture — JMX → Prometheus → Grafana

#### WHY — Tại sao Monitoring Kafka phức tạp?

```
KAFKA MONITORING CHALLENGES:

  Kafka = distributed system với nhiều components:
  
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  ❶ NHIỀU LAYERS cần monitor:                           │
  │     Broker (JVM, disk, network, replication)            │
  │     Topic (throughput, size, partition distribution)     │
  │     Producer (batch, buffer, errors, latency)           │
  │     Consumer (lag, poll rate, commit rate, rebalance)    │
  │     ZooKeeper/KRaft (session, leader election)          │
  │                                                         │
  │  ❷ METRICS RẤT NHIỀU:                                  │
  │     Kafka exposes 500+ JMX metrics per broker           │
  │     → Chọn SAI metrics = miss critical issues           │
  │     → Monitor QUÁ NHIỀU = noise, alert fatigue          │
  │                                                         │
  │  ❸ DISTRIBUTED STATE:                                   │
  │     Consumer lag = f(producer rate, consumer rate,       │
  │                      partition count, rebalance state)   │
  │     → Không phải 1 số đơn giản                         │
  │     → Cần correlate nhiều metrics                       │
  │                                                         │
  │  ❹ FAILURE MODES PHỨC TẠP:                             │
  │     Under-replicated → ISR shrink → potential data loss │
  │     Rebalance storm → all consumers stop → lag spikes   │
  │     Hot partition → 1 consumer overloaded               │
  │     → Cần detect TRƯỚC khi user thấy impact            │
  └─────────────────────────────────────────────────────────┘
```

#### WHAT — Monitoring Stack Overview

```
KAFKA MONITORING PIPELINE:

  ┌──────────┐    JMX     ┌────────────┐  scrape  ┌────────────┐  query  ┌──────────┐
  │  Kafka   │──────────►│ JMX        │────────►│ Prometheus │────────►│ Grafana  │
  │  Broker  │  (port    │ Exporter   │  /metrics│            │ PromQL │          │
  │  (JVM)   │   9999)   │ (port 7071)│         │ (port 9090)│        │(port 3000│
  └──────────┘           └────────────┘         └────────────┘        └──────────┘
                                                     │
  ┌──────────┐  kafka    ┌────────────┐  scrape     │
  │  Kafka   │  protocol │ kafka-     │─────────────┘
  │  Broker  │──────────►│ exporter   │  /metrics
  │          │  (9092)   │ (port 9308)│  (consumer lag,
  └──────────┘           └────────────┘   topic metrics)

  
  2 EXPORTERS cần dùng:

  ┌───────────────────────────────────────────────────────────┐
  │ Exporter        │ Nguồn data │ Metrics                     │
  ├─────────────────┼────────────┼─────────────────────────────┤
  │ JMX Exporter    │ JMX (JVM)  │ Broker internals: request   │
  │ (jmx_exporter)  │            │ rate, replication, network,  │
  │                 │            │ log flush, ISR, controller   │
  │                 │            │                              │
  │ kafka-exporter  │ Kafka API  │ Consumer lag, topic offsets, │
  │ (danielqsj)     │ (AdminClient)│ partition count, message   │
  │                 │            │ rate per topic               │
  └───────────────────────────────────────────────────────────┘

  WHY cần CẢ HAI?
  - JMX Exporter: broker-internal metrics (JVM, disk I/O, replication)
  - kafka-exporter: consumer-facing metrics (lag — metric quan trọng nhất!)
  - JMX Exporter KHÔNG có consumer lag (vì lag = consumer state, không phải broker JVM state)
```

#### HOW — Key Metrics to Monitor

```
TOP 15 KAFKA METRICS (sorted by priority):

  Caveat quan trọng:
  - Prometheus metric names phụ thuộc vào JMX Exporter rules.
  - Danh sách dưới đây dùng names khớp với config ở lab 8.2.
  - Luôn validate bằng: curl -s localhost:7071/metrics | grep '<metric_name>'
  - Nếu đổi rules hoặc exporter image, alert expressions phải đổi theo.

  ═══ CRITICAL (page on-call if abnormal) ═══

  ❶ kafka_consumergroup_lag
     Consumer lag = latest offset - committed offset
     → Lag tăng = consumer chậm hơn producer
     → Lag > threshold = data processing delay
     → Alert: lag > 10K messages sustained > 5 min
     → Source: kafka-exporter

  ❷ kafka_server_replicamanager_underreplicatedpartitions
     Số partitions có ISR < replication factor
     → 0 = healthy, > 0 = risk of data loss!
     → Alert: > 0 sustained > 2 min
     → Source: JMX Exporter

  ❸ kafka_controller_kafkacontroller_activecontrollercount
     Số active controller trong cluster
     → Must be EXACTLY 1
     → 0 = no controller = cluster unresponsive!
     → > 1 = split brain (should not happen with KRaft)
     → Alert: != 1
     → Source: JMX Exporter

  ❹ kafka_controller_kafkacontroller_offlinepartitionscount
     Partitions không có leader
     → 0 = healthy
     → > 0 = partitions UNAVAILABLE for produce/consume!
     → Alert: > 0
     → Source: JMX Exporter


  ═══ WARNING (investigate within 1 hour) ═══

  ❺ kafka_server_replicamanager_underminisrpartitioncount
     Partitions có ISR < min.insync.replicas
     → acks=all producers sẽ bị BLOCKED!
     → Alert: > 0 sustained > 5 min

  ❻ kafka_server_brokertopicmetrics_messagesinpersec_oneminuterate
     Throughput per broker (messages/sec)
     → Sudden drop = producer issue
     → Sudden spike = burst or loop
     → Alert: deviation > 50% from baseline

  ❼ kafka_network_requestmetrics_totaltimems{percentile="99thPercentile"}
     Request latency (Produce, Fetch, Metadata)
     → p99 > 100ms = investigate
     → p99 > 1s = critical
     → Alert: p99 > 500ms sustained > 5 min

  ❽ kafka_server_kafkarequesthandlerpool_requesthandleravgidlepercent
     Request handler thread utilization
     → < 30% idle = broker overloaded!
     → Alert: < 25% sustained > 5 min


  ═══ INFORMATIONAL (trending, capacity planning) ═══

  ❾ kafka_log_log_size (per topic-partition)
     Disk usage per partition
     → Trending up = check retention config
     → Alert: disk usage > 80%

  ❿ kafka_server_replicafetchermanager_maxlag
     Max replication lag (in messages)
     → High lag = follower falling behind
     → Alert: > 1000 sustained > 10 min

  ⓫ kafka_server_brokertopicmetrics_bytesinpersec_oneminuterate / bytesoutpersec_oneminuterate
     Network throughput per broker
     → Capacity planning metric
     → Alert: > 80% of NIC capacity

  ⓬ kafka_server_sessionexpirelistener_zookeeperexpirespersec (legacy ZooKeeper only)
     ZooKeeper session expirations
     → Kafka KRaft lab không có metric này; đừng alert metric legacy trên KRaft cluster
     → Alert: > 0 sustained

  ⓭ kafka_consumer_consumer_fetch_manager_records_lag_max
     Max lag across all partitions (client-side metric)
     → Alternative to kafka-exporter lag
     → Requires client instrumentation

  ⓮ kafka_server_group_coordinator_metrics_GroupCompletedRebalanceCount
     Rebalance completion rate
     → High rate = rebalance storm!
     → Alert: > 5 rebalances in 10 min

  ⓯ jvm_memory_bytes_used / jvm_gc_pause_seconds
     JVM heap và GC metrics
     → Long GC pauses → request timeouts
     → Alert: GC pause > 500ms, heap > 85%
```

### 4.2 Consumer Lag — Metric Quan Trọng Nhất

#### WHY — Tại sao Consumer Lag là "King of Kafka Metrics"?

```
CONSUMER LAG EXPLAINED:

  Time ──────────────────────────────────────────────►

  Producer writes:    [1] [2] [3] [4] [5] [6] [7] [8] [9] [10]
                                                          ▲
                                                     Latest Offset = 10

  Consumer reads:     [1] [2] [3] [4] [5] [6]
                                              ▲
                                         Committed Offset = 6

  LAG = Latest Offset - Committed Offset = 10 - 6 = 4 messages


  TẠI SAO LAG QUAN TRỌNG?

  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  Lag = 0:  Consumer đang real-time                          │
  │            → Data freshness: milliseconds                   │
  │                                                             │
  │  Lag = 100: Consumer chậm hơn producer 100 messages        │
  │            → Có thể bình thường (batch processing)          │
  │            → Hoặc consumer đang bị slow                     │
  │                                                             │
  │  Lag = 1M: Consumer bị stuck hoặc quá chậm                │
  │            → Users thấy stale data!                         │
  │            → Orders chưa được process!                      │
  │            → Notifications chưa gửi!                        │
  │                                                             │
  │  Lag tăng liên tục: Producer rate > Consumer rate           │
  │            → Sẽ ngày càng tệ hơn!                          │
  │            → Cần scale consumers hoặc optimize              │
  │                                                             │
  │  Lag đột ngột spike: Rebalance, restart, hoặc bug          │
  │            → Investigation cần ngay!                        │
  └─────────────────────────────────────────────────────────────┘


  LAG MEASUREMENT METHODS:

  ┌───────────────────────────────────────────────────────────┐
  │ Method              │ Cách hoạt động            │ Dùng khi│
  ├─────────────────────┼───────────────────────────┼─────────┤
  │ kafka-exporter      │ Poll broker offsets +     │ Standard│
  │                     │ consumer committed offsets│ setup   │
  │                     │ → calculate diff          │         │
  │                     │                           │         │
  │ Burrow (LinkedIn)   │ Evaluate lag TREND        │ Advanced│
  │                     │ → WARN if increasing      │ lag     │
  │                     │ → OK if stable            │ analysis│
  │                     │ → ERR if not committed    │         │
  │                     │                           │         │
  │ kafka-consumer-     │ CLI command               │ Debug   │
  │ groups --describe   │ → snapshot at a point     │ only    │
  │                     │                           │         │
  │ Client-side metrics │ JMX/Micrometer in app     │ Per-app │
  │ records-lag-max     │ → real-time lag reporting  │ monitor │
  └───────────────────────────────────────────────────────────┘
```

#### HOW — Lag Alerting Strategy

```
CONSUMER LAG ALERTING — Multi-level:

  ┌─────────────────────────────────────────────────────────────┐
  │ Level     │ Condition                    │ Action            │
  ├───────────┼──────────────────────────────┼───────────────────┤
  │ INFO      │ Lag > 1K for > 5 min         │ Log, dashboard    │
  │ WARNING   │ Lag > 10K for > 10 min       │ Slack notification│
  │ CRITICAL  │ Lag > 100K for > 15 min      │ PagerDuty page    │
  │ EMERGENCY │ Lag tăng liên tục > 30 min   │ Immediate action  │
  └─────────────────────────────────────────────────────────────┘

  ⚠️ Critical: thresholds PHẢI CUSTOMIZE theo workload!
  
  Online payment processing: lag > 100 = critical
  Daily batch analytics: lag > 1M = warning
  Log aggregation: lag > 10M = warning
  
  → Không có "one size fits all" threshold
  → Base on BUSINESS IMPACT, không phải technical number


  LAG TROUBLESHOOTING FLOWCHART:

  Lag increasing?
  │
  ├─ Consumer running? ──── No ──► Check pod/process status
  │                                 Restart consumer
  │
  ├─ Yes → Rebalancing? ──── Yes ──► Check rebalance storm (4.3)
  │
  ├─ No → Processing slow? ─── Yes ──► Profile consumer code
  │                                     Check DB connection pool
  │                                     Check external API latency
  │                                     Increase max.poll.records?
  │
  ├─ No → Producer burst? ──── Yes ──► Scale consumers
  │                                     Add partitions (carefully!)
  │
  ├─ No → Partition skew? ──── Yes ──► Check hot partition (4.3)
  │                                     Fix key distribution
  │
  └─ No → Network issue? ──── Yes ──► Check fetch.min.bytes
                                       Check consumer-broker latency
                                       Check bandwidth
```

### 4.3 Common Incidents — Detection & Mitigation

#### Incident 1: Rebalance Storm

```
REBALANCE STORM — Consumer Group liên tục rebalance:

  Normal rebalance lifecycle:
  Consumer join/leave → Rebalance → Partition reassign → Resume processing
  Duration: 5-30 seconds → acceptable

  REBALANCE STORM:
  Rebalance → some consumer slow → timeout → rebalance again → loop!

  Timeline:
  T=0:    Rebalance bắt đầu (partition revoked)
  T=0-30: All consumers STOP processing → lag increases
  T=30:   Reassignment done → consumers resume
  T=35:   Slow consumer misses poll → max.poll.interval.ms exceeded
  T=35:   Broker kicks slow consumer → trigger NEW rebalance!
  T=35-65: All consumers STOP again → lag doubles!
  → LOOP continues → consumers effectively DOWN


  CAUSES:
  ┌─────────────────────────────────────────────────────────────┐
  │ Cause                       │ Why it triggers rebalance     │
  ├─────────────────────────────┼───────────────────────────────┤
  │ Slow message processing     │ max.poll.interval.ms exceeded │
  │ Long GC pauses              │ session.timeout.ms exceeded   │
  │ Frequent deployments        │ Consumer leave/join rapid     │
  │ Too many partitions/consumer│ Rebalance takes too long      │
  │ Network instability         │ Heartbeat timeout             │
  │ Exception in processing     │ Consumer crash → restart      │
  └─────────────────────────────────────────────────────────────┘


  SOLUTIONS:

  ❶ Increase max.poll.interval.ms (default: 300s = 5 min)
     → If processing single batch > 5 min → increase
     → But: slower detection of dead consumers

  ❷ Decrease max.poll.records (default: 500)
     → Smaller batch = faster processing per poll
     → Trade-off: more poll round-trips

  ❸ Static Group Membership (Kafka 2.3+)
     group.instance.id=consumer-1  # unique per consumer instance
     session.timeout.ms=300000     # 5 min (can be longer)
     → Consumer restart does NOT trigger rebalance!
     → Broker waits session.timeout before reassigning
     → MUST: each instance unique ID + session timeout > restart time

  ❹ Cooperative Sticky Assignor (Kafka 2.4+)
     partition.assignment.strategy=
       org.apache.kafka.clients.consumer.CooperativeStickyAssignor
     → Incremental rebalance: chỉ reassign affected partitions
     → Other partitions CONTINUE processing during rebalance!
     → Reduces "stop the world" rebalance impact by ~80%

  ❺ RECOMMENDED PRODUCTION CONFIG:
     max.poll.interval.ms=600000       # 10 min
     max.poll.records=100              # smaller batches
     session.timeout.ms=45000          # 45 sec
     heartbeat.interval.ms=15000       # 15 sec (1/3 session timeout)
     group.instance.id=svc-${POD_NAME} # static membership
     partition.assignment.strategy=CooperativeStickyAssignor
```

#### Incident 2: Hot Partition

```
HOT PARTITION — 1 partition nhận traffic không tỷ lệ:

  Partition 0: ████████████████████████████████ 80% traffic
  Partition 1: ████ 5%
  Partition 2: ████ 5%
  Partition 3: ████████ 10%

  → Consumer P0 overloaded, others idle
  → Lag builds on P0, others fine
  → Throughput bottleneck = slowest partition


  CAUSES:
  ┌─────────────────────────────────────────────────────────────┐
  │ Cause                     │ Example                         │
  ├─────────────────────────────┼───────────────────────────────┤
  │ Skewed key distribution   │ 80% orders from 1 merchant      │
  │ Default partitioner + few │ key="null" → sticky batch →     │
  │   keys                    │ full batch goes to 1 partition   │
  │ Hash collision            │ Multiple keys hash to same part  │
  │ Time-based key            │ Minute-based key → 1 partition   │
  │                           │   per minute active              │
  └─────────────────────────────────────────────────────────────┘


  DETECTION:
  - kafka-exporter: rate(kafka_topic_partition_current_offset[5m]) by topic/partition
  - kafka-exporter: kafka_consumergroup_lag by consumergroup/topic/partition
  - Broker/log-dir tools: kafka-log-dirs --describe để so sánh size theo partition
  - JMX broker topic aggregate KHÔNG đủ: BrokerTopicMetrics không expose skew theo partition nếu rules không capture partition label

  
  SOLUTIONS:

  ❶ Better key design
     Sai:  key = "merchant_id" (1 merchant = 80% traffic)
     Đúng: key = "merchant_id:order_id" (distribute within merchant)
     Đúng: key = "order_id" (if ordering by merchant not needed)

  ❷ Add salt to key (if ordering within key not critical)
     key = original_key + "_" + (sequence % num_sub_partitions)
     → Spreads 1 hot key across N partitions
     → Trade-off: lose strict ordering on original key

  ❸ Custom partitioner
     class CustomPartitioner implements Partitioner {
       // Route hot merchants to dedicated partitions
       // Route others using default hash
     }

  ❹ Increase partition count (last resort)
     → More partitions = better distribution chance
     → But: cannot decrease later! Affects ordering!
     → First try fixing key distribution
```

#### Incident 3: Under-Replicated Partitions

```
UNDER-REPLICATED PARTITIONS (URP):

  Normal (RF=3, ISR=3):
  Partition 0: Leader=B1, Followers=[B2✓, B3✓]  ISR=[B1,B2,B3] ✓

  Under-replicated (RF=3, ISR=2):
  Partition 0: Leader=B1, Followers=[B2✓, B3✗]  ISR=[B1,B2]    ⚠️
                                         ▲
                                    B3 fell behind!

  IMPACT:
  - ISR shrink → nếu leader dies → fewer replicas to elect from
  - If ISR < min.insync.replicas → producers with acks=all BLOCKED!
  - Extended URP → risk data loss if more brokers fail


  CAUSES:
  ┌─────────────────────────────────────────────────────────────┐
  │ Cause                     │ How to detect                   │
  ├───────────────────────────┼─────────────────────────────────┤
  │ Slow broker (CPU/memory)  │ High request latency on broker  │
  │ Disk I/O saturation       │ iostat shows high await time    │
  │ Network issues            │ Replication fetch latency high  │
  │ GC pauses (JVM)           │ jvm_gc_pause_seconds > 500ms   │
  │ Unbalanced partition load │ Some brokers have more leaders  │
  │ Broker down               │ Broker not in cluster metadata  │
  └─────────────────────────────────────────────────────────────┘


  REMEDIATION:
  1. Check which brokers have URP:
     kafka-topics --describe --under-replicated-partitions
  
  2. Identify slow broker → check CPU, disk, GC, network
  
  3. If disk full → increase retention, add disk, move partitions
  
  4. If broker restarted → wait for catch-up (follower fetch)
     → Monitor replica.lag.time.max.ms (default 30s)
  
  5. If persistent → reassign partitions away from slow broker
     kafka-reassign-partitions --execute
  
  6. Leader rebalance (if leaders concentrated on few brokers):
     kafka-leader-election --all-topic-partitions
```

### 4.4 Distributed Tracing qua Kafka

#### WHY — Lost in the Event Maze

```
TRACING CHALLENGE trong Event-Driven Systems:

  Synchronous (HTTP/gRPC):
  User → API Gateway → Order Service → Payment Service → DB
  └─────────────── 1 request, 1 trace, easy ──────────────┘

  Asynchronous (Kafka):
  User → Order Service ──produce──► [Kafka Topic] ──consume──► Payment Service
                                                   ──consume──► Inventory Service
                                                   ──consume──► Notification Service

  Vấn đề:
  ❶ Message produce và consume là 2 processes KHÁC NHAU
  ❷ Consumer có thể process HÀNG GIỜ sau khi produce
  ❸ 1 event có thể trigger NHIỀU downstream events
  ❹ Khi lỗi xảy ra: "Event nào gây ra event này?" "Request nào từ user?"

  → Cần PROPAGATE trace context qua Kafka headers!
```

#### WHAT — Correlation ID, Causation ID, Trace Context

```
EVENT TRACING IDENTIFIERS:

  ┌──────────────────────────────────────────────────────────────┐
  │                    Event Envelope                            │
  │                                                              │
  │  eventId:       "evt_abc123"     ← unique ID cho event này  │
  │  correlationId: "req_xyz789"     ← ID của original request  │
  │  causationId:   "evt_def456"     ← ID của event cha (parent)│
  │  traceId:       "00-abcdef..."   ← W3C trace context        │
  │  spanId:        "1234abcd"       ← current span             │
  │  timestamp:     1704067200000    ← khi event được tạo       │
  │  source:        "order-service"  ← service tạo event        │
  │                                                              │
  │  payload: { ... domain data ... }                            │
  └──────────────────────────────────────────────────────────────┘


  CORRELATION vs CAUSATION:

  User places order (correlationId = req_001):

  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
  │ OrderCreated     │     │ PaymentProcessed│     │ NotificationSent│
  │                  │     │                  │     │                  │
  │ eventId: evt_1   │────►│ eventId: evt_2   │────►│ eventId: evt_3   │
  │ correlationId:   │     │ correlationId:   │     │ correlationId:   │
  │   req_001        │     │   req_001        │     │   req_001        │
  │ causationId:     │     │ causationId:     │     │ causationId:     │
  │   req_001        │     │   evt_1          │     │   evt_2          │
  │ source:          │     │ source:          │     │ source:          │
  │   order-service  │     │   payment-svc    │     │   notification   │
  └─────────────────┘     └─────────────────┘     └─────────────────┘

  correlationId: LUÔN GIỐNG NHAU trong cả chain
  → "Tất cả events này thuộc về request req_001"
  → Query: "cho tôi xem TẤT CẢ events của request req_001"

  causationId: event NÀO trực tiếp gây ra event này
  → evt_2 caused by evt_1 (OrderCreated → PaymentProcessed)
  → evt_3 caused by evt_2 (PaymentProcessed → NotificationSent)
  → Rebuild causal graph: req_001 → evt_1 → evt_2 → evt_3


  KAFKA HEADERS cho Trace Propagation:

  ProducerRecord headers:
  ┌────────────────────────────────────────────┐
  │ Header Key          │ Value                 │
  ├─────────────────────┼───────────────────────┤
  │ X-Correlation-ID    │ req_001               │
  │ X-Causation-ID      │ evt_1                 │
  │ traceparent         │ 00-{traceId}-{spanId} │
  │ tracestate          │ vendor-specific state  │
  │ X-Source-Service    │ order-service          │
  │ X-Event-Type        │ OrderCreated           │
  │ X-Event-Time        │ 2024-01-01T00:00:00Z  │
  └────────────────────────────────────────────┘

  → Headers travel WITH the message
  → Consumer extracts headers → continues trace
  → Zero modification to message payload!
```

#### HOW — OpenTelemetry Integration

```
OPENTELEMETRY + KAFKA:

  ┌──────────────┐        ┌──────────┐        ┌──────────────┐
  │  Producer    │        │  Kafka   │        │  Consumer    │
  │              │        │  Broker  │        │              │
  │ ┌──────────┐ │        │          │        │ ┌──────────┐ │
  │ │  Span:   │ │ inject │          │extract │ │  Span:   │ │
  │ │ produce  │─┼──────►│  headers ├──────►─┼─│ consume  │ │
  │ │          │ │ trace  │  carry   │ trace  │ │          │ │
  │ │ traceId  │ │ context│ context  │context │ │ traceId  │ │
  │ │ spanId A │ │        │          │        │ │ spanId B │ │
  │ └──────────┘ │        │          │        │ └──────────┘ │
  │      │       │        │          │        │      │       │
  │      ▼       │        │          │        │      ▼       │
  │ OTel SDK     │        │          │        │ OTel SDK     │
  │ → Exporter   │        │          │        │ → Exporter   │
  └──────┼───────┘        └──────────┘        └──────┼───────┘
         │                                          │
         ▼                                          ▼
  ┌──────────────────────────────────────────────────────────┐
  │                  Tracing Backend                          │
  │              (Jaeger / Zipkin / Tempo)                    │
  │                                                          │
  │  Trace: req_001                                          │
  │  ├─ Span A: order-service.produce (topic: orders)       │
  │  │   └─ Span B: payment-service.consume (topic: orders)  │
  │  │       └─ Span C: payment-service.produce (payments)   │
  │  │           └─ Span D: notif-service.consume (payments) │
  │  └─ Span E: inventory-service.consume (topic: orders)   │
  └──────────────────────────────────────────────────────────┘

  Implementation approaches:
  
  ❶ Auto-instrumentation (recommended):
     → OTel SDK intercept Kafka client calls
     → Automatic span creation + context propagation
     → Go: otelkafka-go, Java: opentelemetry-java-instrumentation
     → Minimal code changes

  ❷ Manual instrumentation:
     → Inject trace context into headers on produce
     → Extract trace context from headers on consume
     → Full control but more code
```

Lab note: code ở section 8.5-8.6 chỉ triển khai **correlation logging** bằng Kafka headers (`X-Correlation-ID`, `X-Causation-ID`). Nó chưa tạo OpenTelemetry span, chưa export trace qua collector, và không nên gọi là distributed tracing đầy đủ. Muốn có tracing thật cần propagate W3C `traceparent`/`tracestate`, tạo producer/consumer spans, và gửi về Jaeger/Tempo/OTel Collector.

### 4.5 Structured Logging cho Message-Driven Systems

```
STRUCTURED LOGGING BEST PRACTICES:

  ❌ UNSTRUCTURED (traditional):
  2024-01-01 10:00:00 INFO Processing order ORD-123
  2024-01-01 10:00:01 ERROR Payment failed for order ORD-123
  → Grep "ORD-123" → miss related events without orderId
  → Cannot correlate across services
  → Cannot filter by field

  ✅ STRUCTURED (JSON):
  {
    "timestamp": "2024-01-01T10:00:00.000Z",
    "level": "INFO",
    "service": "payment-service",
    "message": "Processing payment",
    "correlationId": "req_001",
    "causationId": "evt_abc",
    "eventType": "OrderCreated",
    "orderId": "ORD-123",
    "topic": "orders",
    "partition": 3,
    "offset": 12345,
    "consumerGroup": "payment-group",
    "processingTimeMs": 45,
    "traceId": "abcdef1234567890"
  }

  → Query: correlationId=req_001 → ALL events for this request
  → Filter: level=ERROR AND service=payment-service
  → Dashboard: avg(processingTimeMs) by eventType
  → Link: traceId → jump to Jaeger/Tempo trace


  MANDATORY LOG FIELDS cho Kafka consumers:

  ┌────────────────────────────────────────────────────────────┐
  │ Field             │ Why                                     │
  ├───────────────────┼─────────────────────────────────────────┤
  │ correlationId     │ Trace request across services           │
  │ causationId       │ Find parent event                       │
  │ eventType         │ Filter by event type                    │
  │ topic             │ Which topic was consumed                │
  │ partition         │ Which partition (debug hot partition)    │
  │ offset            │ Exact message position (replay ability) │
  │ consumerGroup     │ Which consumer group                    │
  │ processingTimeMs  │ Processing duration (performance)       │
  │ traceId           │ Link to distributed trace               │
  │ outcome           │ success/failure/retry/dlq               │
  └────────────────────────────────────────────────────────────┘
```

### 4.6 Disaster Recovery — MirrorMaker 2

```
MIRRORMAKER 2 (MM2) — Cross-Datacenter Replication:

  WHY?
  - Disaster recovery: DC down → failover to backup
  - Geo-replication: data close to users
  - Migration: move to new cluster
  - Aggregation: multiple clusters → central analytics


  TOPOLOGIES:

  ❶ ACTIVE-PASSIVE (DR):
  ┌──────────────┐     MM2        ┌──────────────┐
  │ DC-Primary   │──────────────►│ DC-Secondary  │
  │ (active)     │  replicate    │ (standby)     │
  │              │  topics +     │               │
  │ producers ✓  │  offsets +    │ producers ✗   │
  │ consumers ✓  │  configs      │ consumers ✗   │
  └──────────────┘               └──────────────┘
  
  Failover: redirect producers + consumers to DC-Secondary
  RPO: seconds to minutes (replication lag)
  RTO: minutes (DNS switch, consumer restart)
  
  ❷ ACTIVE-ACTIVE (multi-region):
  ┌──────────────┐     MM2        ┌──────────────┐
  │ DC-East      │◄──────────────►│ DC-West      │
  │              │  bidirectional │               │
  │ producers ✓  │  replication   │ producers ✓  │
  │ consumers ✓  │               │ consumers ✓  │
  └──────────────┘               └──────────────┘
  
  Topic naming: source cluster prefix
  DC-East topic "orders" → DC-West topic "dc-east.orders"
  → Prevents infinite replication loop
  
  Challenges:
  - Event deduplication (same order processed in both DCs)
  - Conflict resolution (concurrent writes)
  - Higher complexity


  MM2 KEY FEATURES vs MM1:
  ┌───────────────────────────────────────────────────────────┐
  │ Feature                │ MM1 (legacy)  │ MM2 (Kafka 2.4+)│
  ├────────────────────────┼───────────────┼──────────────────┤
  │ Based on               │ Consumer+     │ Kafka Connect    │
  │                        │ Producer      │ framework        │
  │ Offset translation     │ No            │ Yes (automatic)  │
  │ Consumer group sync    │ No            │ Yes              │
  │ Dynamic topic discovery│ No            │ Yes              │
  │ Exactly-once           │ No            │ Yes (with txn)   │
  │ Monitoring             │ Basic         │ Rich metrics     │
  │ Replication loop avoid │ Manual        │ Automatic        │
  └───────────────────────────────────────────────────────────┘


  RPO / RTO TARGETS:

  ┌──────────────────────────────────────────────────────────┐
  │ RPO (Recovery Point Objective):                          │
  │ "Bao nhiêu data có thể mất?"                            │
  │                                                          │
  │ MM2 replication lag typically: 100ms - 5s                │
  │ → RPO ≈ seconds (dữ liệu trong 5s cuối có thể mất)    │
  │ → Tunable via: sync.group.offsets.interval.seconds      │
  │                                                          │
  │ RTO (Recovery Time Objective):                           │
  │ "Bao lâu để phục hồi?"                                  │
  │                                                          │
  │ DNS failover: 30s - 5 min (depends on TTL)              │
  │ Consumer restart: 30s - 2 min                           │
  │ Offset translation: automatic với MM2                   │
  │ → RTO ≈ 2-10 minutes typically                          │
  └──────────────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### Monitoring Tool Selection

| Tiêu chí | JMX Exporter + Prometheus | Confluent Control Center | Datadog Kafka Integration |
|----------|--------------------------|------------------------|--------------------------|
| Cost | Free (open source) | Commercial (Confluent license) | SaaS pricing |
| Setup complexity | Trung bình (config JMX, exporters) | Thấp (bundled) | Thấp (agent install) |
| Consumer lag | Cần kafka-exporter riêng | Built-in | Built-in |
| Dashboards | Manual (Grafana) | Pre-built | Pre-built |
| Alerting | Prometheus Alertmanager | Built-in | Built-in |
| Custom metrics | Full control | Limited | Limited |
| Best for | Team đã có Prometheus stack | All-Confluent shop | Existing Datadog users |

### Consumer Lag Monitoring Tools

| Tiêu chí | kafka-exporter | Burrow (LinkedIn) | Client-side metrics |
|----------|---------------|-------------------|-------------------|
| Deployment | Sidecar/standalone | Standalone service | In-app |
| Lag calculation | Simple diff | Trend analysis (OK/WARN/ERR) | Real-time per consumer |
| Alert intelligence | Basic threshold | Smart (evaluates trend) | Custom logic |
| Overhead | Thấp | Trung bình | Rất thấp |
| Best for | Most setups | Large multi-team Kafka | Custom alerting needs |

### Rebalance Mitigation Strategies

| Strategy | Rebalance impact | Complexity | Trade-off |
|---------|-----------------|------------|-----------|
| Increase max.poll.interval.ms | Giảm rebalance frequency | Thấp | Slower dead consumer detection |
| Static group membership | Eliminate restart rebalances | Thấp | Need unique instance IDs |
| Cooperative sticky assignor | Incremental rebalance | Thấp | Minor assignment overhead |
| Reduce max.poll.records | Faster poll cycles | Thấp | More network round-trips |
| All combined | Best result | Trung bình | Recommended cho production |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. MONITORING: "Monitor before you need it"
   → Set up Prometheus + Grafana TRƯỚC khi go production
   → Pre-built dashboards: import Grafana dashboard ID 7589 (Kafka Overview)
   → Key alerts: consumer lag, URP, offline partitions, disk usage
   → Test alerting: simulate failure → verify alert fires

2. CONSUMER LAG: Context-aware thresholds
   → Payment processing: lag > 100 = CRITICAL
   → Analytics pipeline: lag > 100K = WARNING
   → Nên dùng Burrow cho lag TREND analysis thay vì static thresholds
   → Monitor lag RATE OF CHANGE, không chỉ absolute value

3. TRACING: Correlation ID from DAY 1
   → Mọi message PHẢI có correlationId trong header
   → Generate at API gateway level, propagate everywhere
   → Store in MDC (Mapped Diagnostic Context) hoặc Go context
   → Log correlationId trong MỌI log line

4. STRUCTURED LOGGING: JSON everywhere
   → topic, partition, offset, correlationId, processingTime
   → Ship to ELK/Loki → query across services
   → Dashboard: processing time by event type, error rate by topic

5. INCIDENT RESPONSE: Runbooks ready
   → Mỗi alert PHẢI có runbook link
   → Runbook = step-by-step investigation + remediation
   → Practice incident response: monthly disaster drill
```

### Common Pitfalls

```
❌ PITFALL 1: Chỉ monitor broker, quên consumer lag
   Sai:  "Broker CPU 30%, disk 50% → everything fine!"
   Đúng: Consumer lag 1M and increasing → users see stale data!
   → Broker healthy ≠ system healthy
   → Consumer lag là metric CỦA BUSINESS, không chỉ infra

❌ PITFALL 2: Alert on EVERY rebalance
   Sai:  Alert khi rebalance xảy ra → alert fatigue
   Đúng: Alert khi rebalance SỐ LẦN cao (>5 trong 10 min)
   → Single rebalance = normal (deployment, scaling)
   → Rebalance storm = problem → alert!

❌ PITFALL 3: No correlation ID → debug nightmare
   Sai:  "Payment failed" → WHICH order? WHICH user? WHERE?
   Đúng: correlationId=req_001 → search ALL services → full picture
   → Add correlationId TRƯỚC khi có incident
   → Retrofitting correlation = much harder

❌ PITFALL 4: Monitoring lag by consumer group, not per partition
   Sai:  Total lag = 100K → "average 25K per partition"
   Đúng: P0 = 99K, P1 = 500, P2 = 300, P3 = 200
   → P0 is hot partition! Total hides the problem
   → Always monitor PER PARTITION lag

❌ PITFALL 5: No DR plan → "we'll figure it out"
   Sai:  "If DC goes down, we'll manually failover"
   Đúng: Document failover procedure, practice quarterly
   → Under stress = mistakes
   → Documented + practiced = confident execution

❌ PITFALL 6: Missing offset commit monitoring
   Sai:  Consumer running, processing messages, but NOT committing offsets
   Đúng: Monitor commit rate → if drops to 0, consumer is stuck
   → Consumer may be processing but rebalance will RESTART from last commit!
```

---

## 7. Performance Considerations

### Monitoring Stack Performance Impact

```
MONITORING OVERHEAD:

  ┌────────────────────────────────────────────────────────────┐
  │ Component        │ CPU Impact │ Memory   │ Network         │
  ├──────────────────┼────────────┼──────────┼─────────────────┤
  │ JMX Exporter     │ 1-3%       │ 50-100MB │ ~1MB/scrape     │
  │ kafka-exporter   │ < 1%       │ 30-50MB  │ ~500KB/scrape   │
  │ Prometheus       │ 5-10%      │ 2-8GB    │ Depends on      │
  │ (scrape+storage) │ (its own)  │ (its own)│ target count    │
  │ Grafana          │ < 5%       │ 256MB    │ Query-dependent │
  └────────────────────────────────────────────────────────────┘

  PROMETHEUS SCRAPE TUNING:
  - scrape_interval: 15s (default) → good for most metrics
  - Consumer lag: scrape_interval: 10s (more frequent = faster detection)
  - JMX Exporter: scrape_interval: 30s (broker metrics change slowly)
  
  → Total monitoring overhead on Kafka broker: < 5% CPU, < 200MB RAM
  → Acceptable for the visibility gained


  KEY PERFORMANCE METRICS THRESHOLDS:

  ┌────────────────────────────────────────────────────────────┐
  │ Metric                      │ Healthy    │ Warning  │ Crit │
  ├─────────────────────────────┼────────────┼──────────┼──────┤
  │ Request handler idle %      │ > 50%      │ 25-50%   │ <25% │
  │ Network handler idle %      │ > 50%      │ 25-50%   │ <25% │
  │ Produce request p99         │ < 50ms     │ 50-200ms │ >200 │
  │ Fetch request p99           │ < 100ms    │ 100-500ms│ >500 │
  │ Under-replicated partitions │ 0          │ 1-5      │ >5   │
  │ ISR shrinks/sec             │ 0          │ > 0      │ >1/s │
  │ Disk usage %                │ < 60%      │ 60-80%   │ >80% │
  │ JVM GC pause p99            │ < 100ms    │ 100-500ms│ >500 │
  │ Consumer lag (depends!)     │ Stable     │ Growing  │ Spike│
  └────────────────────────────────────────────────────────────┘
```

---

## 8. Hands-on Lab

### 8.1 Setup — Monitoring Stack

```yaml
# docker-compose.yml — Kafka + Prometheus + Grafana + kafka-exporter
version: '3.8'

services:
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
      - "7071:7071"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092,EXTERNAL://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,EXTERNAL://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_NUM_PARTITIONS: 4
      KAFKA_LOG_RETENTION_HOURS: 24
      KAFKA_JMX_PORT: 9999
      KAFKA_JMX_HOSTNAME: kafka
      KAFKA_OPTS: "-javaagent:/opt/jmx-exporter/jmx_prometheus_javaagent.jar=7071:/opt/jmx-exporter/kafka-broker.yml"
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    volumes:
      - ./jmx-exporter:/opt/jmx-exporter

  kafka-exporter:
    image: danielqsj/kafka-exporter:latest
    depends_on:
      - kafka
    ports:
      - "9308:9308"
    command:
      - "--kafka.server=kafka:29092"
      - "--topic.filter=.*"
      - "--group.filter=.*"
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.7.0
    ports:
      - "9100:9100"
    command:
      - "--path.rootfs=/host"
    volumes:
      - "/:/host:ro,rslave"
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:v2.48.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alert-rules.yml:/etc/prometheus/alert-rules.yml
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=7d"

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_SECURITY_ADMIN_USER: admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  grafana-data:
```

### 8.2 JMX Exporter Configuration

```bash
# Create directories
mkdir -p jmx-exporter prometheus grafana/provisioning/datasources grafana/provisioning/dashboards
cp day-23-production-operations-observability/grafana-kafka-lag-dashboard.json \
  grafana/provisioning/dashboards/kafka-lag-dashboard.json
```

```yaml
# jmx-exporter/kafka-broker.yml
# JMX Exporter config for Kafka broker metrics
lowercaseOutputName: true
lowercaseOutputLabelNames: true

rules:
  # Broker topic meters. Attribute names such as OneMinuteRate/Count become label values.
  - pattern: kafka.server<type=BrokerTopicMetrics, name=(.+), topic=(.+)><>(Count|OneMinuteRate|FiveMinuteRate|MeanRate)
    name: kafka_server_brokertopicmetrics_$1_$3
    labels:
      topic: "$2"
    type: UNTYPED

  - pattern: kafka.server<type=BrokerTopicMetrics, name=(.+)><>(Count|OneMinuteRate|FiveMinuteRate|MeanRate)
    name: kafka_server_brokertopicmetrics_$1_$2
    type: UNTYPED

  # Request latency percentiles.
  - pattern: kafka.network<type=RequestMetrics, name=TotalTimeMs, request=(.+)><>(50thPercentile|75thPercentile|95thPercentile|98thPercentile|99thPercentile|999thPercentile)
    name: kafka_network_requestmetrics_totaltimems
    labels:
      request: "$1"
      percentile: "$2"
    type: GAUGE

  # Replica manager gauges used by alerts.
  - pattern: kafka.server<type=ReplicaManager, name=(UnderReplicatedPartitions|UnderMinIsrPartitionCount|PartitionCount)><>Value
    name: kafka_server_replicamanager_$1
    type: GAUGE

  # Controller gauges.
  - pattern: kafka.controller<type=KafkaController, name=(ActiveControllerCount|OfflinePartitionsCount)><>Value
    name: kafka_controller_kafkacontroller_$1
    type: GAUGE

  # Log metrics
  - pattern: kafka.log<type=Log, name=Size, topic=(.+), partition=(.+)><>Value
    name: kafka_log_log_size
    labels:
      topic: "$1"
      partition: "$2"
    type: GAUGE

  # Request handler pool
  - pattern: kafka.server<type=KafkaRequestHandlerPool, name=RequestHandlerAvgIdlePercent><>Value
    name: kafka_server_kafkarequesthandlerpool_requesthandleravgidlepercent
    type: GAUGE

  # Group coordinator rebalance count.
  - pattern: kafka.coordinator.group<type=GroupCoordinatorMetrics, name=GroupCompletedRebalanceCount><>Count
    name: kafka_coordinator_group_groupcompletedrebalancecount
    type: COUNTER

  # JVM metrics (built-in)
  - pattern: java.lang<type=Memory><HeapMemoryUsage>(\w+)
    name: jvm_memory_heap_$1
    type: GAUGE

  - pattern: java.lang<type=GarbageCollector, name=(.+)><>CollectionCount
    name: jvm_gc_collection_count
    labels:
      gc: "$1"
    type: COUNTER

  - pattern: java.lang<type=GarbageCollector, name=(.+)><>CollectionTime
    name: jvm_gc_collection_time_ms
    labels:
      gc: "$1"
    type: COUNTER
```

Download the JMX exporter agent:

```bash
# Download JMX Prometheus Java agent
curl -L -o jmx-exporter/jmx_prometheus_javaagent.jar \
  https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar
```

### 8.3 Prometheus Configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert-rules.yml"

scrape_configs:
  # Kafka broker JMX metrics
  - job_name: "kafka-broker"
    static_configs:
      - targets: ["kafka:7071"]
    scrape_interval: 15s

  # Kafka exporter (consumer lag, topic metrics)
  - job_name: "kafka-exporter"
    static_configs:
      - targets: ["kafka-exporter:9308"]
    scrape_interval: 10s

  # Host filesystem/CPU metrics for disk alerts.
  # Docker Desktop reports the Linux VM filesystem, not necessarily your physical host.
  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]
    scrape_interval: 15s

  # Prometheus self-monitoring
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
```

```yaml
# prometheus/alert-rules.yml
groups:
  - name: kafka-critical
    rules:
      # Consumer lag critical
      - alert: KafkaConsumerLagCritical
        expr: kafka_consumergroup_lag_sum > 100000
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "Consumer group {{ $labels.consumergroup }} lag > 100K"
          description: "Topic {{ $labels.topic }}, current lag: {{ $value }}"

      # Consumer lag increasing
      - alert: KafkaConsumerLagIncreasing
        expr: delta(kafka_consumergroup_lag_sum[10m]) > 50000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Consumer lag increasing for {{ $labels.consumergroup }}"
          description: "Lag increased by {{ $value }} in last 10 min"

      # Under-replicated partitions
      - alert: KafkaUnderReplicatedPartitions
        expr: kafka_server_replicamanager_underreplicatedpartitions > 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Under-replicated partitions detected"
          description: "{{ $value }} partitions under-replicated"

      # No active controller
      - alert: KafkaNoActiveController
        expr: kafka_controller_kafkacontroller_activecontrollercount != 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No active Kafka controller!"

      # Offline partitions
      - alert: KafkaOfflinePartitions
        expr: kafka_controller_kafkacontroller_offlinepartitionscount > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $value }} offline partitions!"

      # Disk usage
      - alert: KafkaDiskUsageHigh
        expr: (node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs"} - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"}) / node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs"} > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Disk usage > 80%"

  - name: kafka-warning
    rules:
      # Request handler saturation
      - alert: KafkaRequestHandlerSaturation
        expr: kafka_server_kafkarequesthandlerpool_requesthandleravgidlepercent < 0.25
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Request handler idle < 25%"

      # High produce latency
      - alert: KafkaHighProduceLatency
        expr: kafka_network_requestmetrics_totaltimems{request="Produce", percentile="99thPercentile"} > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Produce p99 latency > 500ms"

      # Frequent rebalances (rebalance storm)
      - alert: KafkaRebalanceStorm
        expr: increase(kafka_coordinator_group_groupcompletedrebalancecount[10m]) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Possible rebalance storm: >5 rebalances in 10 min"
```

### 8.4 Grafana Provisioning

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

```yaml
# grafana/provisioning/dashboards/dashboard.yml
apiVersion: 1
providers:
  - name: "kafka-dashboards"
    orgId: 1
    folder: "Kafka"
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: false
```

Dashboard JSON tối thiểu được cung cấp kèm bài tại `day-23-production-operations-observability/grafana-kafka-lag-dashboard.json`. Copy file này vào `grafana/provisioning/dashboards/kafka-lag-dashboard.json` sau khi tạo thư mục provisioning để Grafana tự load panel lag theo group/topic/partition, under-replicated partitions, offline partitions và log size theo partition.

### 8.5 Go Application — Producer with Correlation Logging

```go
// producer/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/segmentio/kafka-go"
)

type OrderEvent struct {
	EventID       string  `json:"eventId"`
	EventType     string  `json:"eventType"`
	CorrelationID string  `json:"correlationId"`
	CausationID   string  `json:"causationId"`
	Source        string  `json:"source"`
	Timestamp     string  `json:"timestamp"`
	OrderID       string  `json:"orderId"`
	CustomerID    string  `json:"customerId"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	broker := getEnv("KAFKA_BROKER", "localhost:9092")
	topic := getEnv("KAFKA_TOPIC", "orders")

	writer := &kafka.Writer{
		Addr:         kafka.TCP(broker),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		BatchSize:    100,
		BatchTimeout: 10 * time.Millisecond,
		RequiredAcks: kafka.RequireAll,
		Async:        false,
	}
	defer writer.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	customers := []string{"CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"}
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	slog.Info("Producer started", "broker", broker, "topic", topic)

	for {
		select {
		case <-sigCh:
			slog.Info("Shutting down producer")
			return
		case <-ticker.C:
			correlationID := uuid.New().String()
			eventID := uuid.New().String()
			orderID := fmt.Sprintf("ORD-%d", time.Now().UnixMilli())
			customerID := customers[rand.Intn(len(customers))]
			amount := float64(rand.Intn(10000)) / 100.0

			event := OrderEvent{
				EventID:       eventID,
				EventType:     "order.created.v1",
				CorrelationID: correlationID,
				CausationID:   correlationID,
				Source:        "order-service",
				Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
				OrderID:       orderID,
				CustomerID:    customerID,
				Amount:        amount,
				Currency:      "USD",
			}

			value, _ := json.Marshal(event)

			msg := kafka.Message{
				Key:   []byte(customerID),
				Value: value,
				Headers: []kafka.Header{
					{Key: "X-Correlation-ID", Value: []byte(correlationID)},
					{Key: "X-Causation-ID", Value: []byte(correlationID)},
					{Key: "X-Event-Type", Value: []byte("order.created.v1")},
					{Key: "X-Source-Service", Value: []byte("order-service")},
				},
			}

			start := time.Now()
			err := writer.WriteMessages(ctx, msg)
			produceLatency := time.Since(start)

			if err != nil {
				slog.Error("Failed to produce message",
					"correlationId", correlationID,
					"orderId", orderID,
					"error", err.Error(),
				)
				continue
			}

			slog.Info("Message produced",
				"correlationId", correlationID,
				"orderId", orderID,
				"customerId", customerID,
				"amount", amount,
				"topic", topic,
				"produceLatencyMs", produceLatency.Milliseconds(),
			)
		}
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

### 8.6 Go Application — Consumer with Correlation Logging & Structured Logging

```go
// consumer/main.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/segmentio/kafka-go"
)

type OrderEvent struct {
	EventID       string  `json:"eventId"`
	EventType     string  `json:"eventType"`
	CorrelationID string  `json:"correlationId"`
	CausationID   string  `json:"causationId"`
	Source        string  `json:"source"`
	Timestamp     string  `json:"timestamp"`
	OrderID       string  `json:"orderId"`
	CustomerID    string  `json:"customerId"`
	Amount        float64 `json:"amount"`
	Currency      string  `json:"currency"`
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	broker := getEnv("KAFKA_BROKER", "localhost:9092")
	topic := getEnv("KAFKA_TOPIC", "orders")
	groupID := getEnv("KAFKA_GROUP", "payment-service-group")
	instanceID := getEnv("KAFKA_INSTANCE_ID", "payment-1")

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{broker},
		Topic:          topic,
		GroupID:        groupID,
		MinBytes:       1e3,
		MaxBytes:       10e6,
		MaxWait:        500 * time.Millisecond,
		CommitInterval: time.Second,
		// Static membership to avoid rebalance on restart
		GroupBalancers: []kafka.GroupBalancer{
			kafka.RangeGroupBalancer{},
		},
	})
	defer reader.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	slog.Info("Consumer started",
		"broker", broker,
		"topic", topic,
		"groupId", groupID,
		"instanceId", instanceID,
	)

	go func() {
		<-sigCh
		slog.Info("Shutting down consumer gracefully")
		cancel()
	}()

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			slog.Error("Failed to fetch message", "error", err.Error())
			continue
		}

		start := time.Now()

		correlationID := extractHeader(msg.Headers, "X-Correlation-ID")
		causationID := extractHeader(msg.Headers, "X-Causation-ID")
		eventType := extractHeader(msg.Headers, "X-Event-Type")

		var event OrderEvent
		if err := json.Unmarshal(msg.Value, &event); err != nil {
			slog.Error("Failed to deserialize message",
				"correlationId", correlationID,
				"topic", msg.Topic,
				"partition", msg.Partition,
				"offset", msg.Offset,
				"error", err.Error(),
				"outcome", "dlq",
			)
			// Commit to avoid reprocessing bad message
			reader.CommitMessages(ctx, msg)
			continue
		}

		// Simulate processing (payment validation)
		processingErr := processPayment(event)
		processingTime := time.Since(start)

		if processingErr != nil {
			slog.Error("Payment processing failed",
				"correlationId", correlationID,
				"causationId", causationID,
				"eventType", eventType,
				"orderId", event.OrderID,
				"customerId", event.CustomerID,
				"amount", event.Amount,
				"topic", msg.Topic,
				"partition", msg.Partition,
				"offset", msg.Offset,
				"processingTimeMs", processingTime.Milliseconds(),
				"outcome", "failure",
				"error", processingErr.Error(),
			)
		} else {
			slog.Info("Payment processed successfully",
				"correlationId", correlationID,
				"causationId", causationID,
				"eventType", eventType,
				"orderId", event.OrderID,
				"customerId", event.CustomerID,
				"amount", event.Amount,
				"topic", msg.Topic,
				"partition", msg.Partition,
				"offset", msg.Offset,
				"processingTimeMs", processingTime.Milliseconds(),
				"outcome", "success",
			)
		}

		if err := reader.CommitMessages(ctx, msg); err != nil {
			slog.Error("Failed to commit offset",
				"correlationId", correlationID,
				"topic", msg.Topic,
				"partition", msg.Partition,
				"offset", msg.Offset,
				"error", err.Error(),
			)
		}
	}
}

func processPayment(event OrderEvent) error {
	// Simulate 10-100ms processing time
	time.Sleep(time.Duration(10+rand.Intn(90)) * time.Millisecond)

	// Simulate 5% failure rate
	if rand.Float64() < 0.05 {
		return fmt.Errorf("payment gateway timeout for order %s", event.OrderID)
	}
	return nil
}

func extractHeader(headers []kafka.Header, key string) string {
	for _, h := range headers {
		if h.Key == key {
			return string(h.Value)
		}
	}
	return ""
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

Run commands cho hai app demo:

```bash
mkdir -p producer consumer

cat > go.mod <<'EOF'
module kafka-observability-lab

go 1.21

require (
	github.com/google/uuid v1.6.0
	github.com/segmentio/kafka-go v0.4.47
)
EOF

go mod tidy
go run ./producer
KAFKA_GROUP=payment-service-group KAFKA_INSTANCE_ID=payment-1 go run ./consumer
```

### 8.7 Simulate Incidents

```bash
# Start the monitoring stack
docker compose up -d

# Wait for everything to start
sleep 15

# Create test topic
docker exec $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server localhost:9092 \
  --create --topic orders --partitions 4 --replication-factor 1

echo "=== Stack URLs ==="
echo "Kafka:      localhost:9092"
echo "Prometheus: http://localhost:9090"
echo "Grafana:    http://localhost:3000 (admin/admin)"
echo "kafka-exporter metrics: http://localhost:9308/metrics"
echo "JMX exporter metrics:   http://localhost:7071/metrics"
```

```bash
# === INCIDENT SIMULATION 1: Consumer Lag ===
# Produce 100K messages quickly
echo "--- Producing 100K messages to create consumer lag ---"
docker exec $(docker ps -q -f name=kafka) bash -c "
  seq 1 100000 | while read i; do
    echo '{\"orderId\":\"ORD-'\"'\$i'\"'\",\"amount\":99.99}'
  done | kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic orders \
    --property parse.key=false
"
echo "--- Check Prometheus: kafka_consumergroup_lag ---"
echo "    http://localhost:9090/graph?g0.expr=kafka_consumergroup_lag_sum"
```

```bash
# === INCIDENT SIMULATION 2: Hot Partition ===
# Produce messages with same key → all go to 1 partition
echo "--- Creating hot partition (same key) ---"
docker exec $(docker ps -q -f name=kafka) bash -c "
  for i in \$(seq 1 10000); do
    echo 'HOT_KEY:{\"orderId\":\"ORD-'\$i'\",\"amount\":99.99}'
  done | kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic orders \
    --property parse.key=true \
    --property key.separator=:
"

# Check partition distribution
echo "--- Partition sizes (look for imbalance) ---"
docker exec $(docker ps -q -f name=kafka) \
  kafka-log-dirs --bootstrap-server localhost:9092 \
  --describe --topic-list orders | grep -oP '"partition":\d+,"size":\d+'
```

```bash
# === Verify Monitoring Stack ===

# Check Prometheus targets
echo "--- Prometheus targets ---"
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | head -30

# Check kafka-exporter metrics
echo "--- Consumer lag metrics ---"
curl -s http://localhost:9308/metrics | grep "kafka_consumergroup_lag"

# Check JMX metrics
echo "--- Broker metrics ---"
curl -s http://localhost:7071/metrics | grep "kafka_server_replicamanager" | head -10

# PromQL queries to try in Prometheus UI (http://localhost:9090):
echo ""
echo "=== PromQL Queries to Try ==="
echo "Consumer lag:           kafka_consumergroup_lag_sum"
echo "Messages in/sec:        rate(kafka_server_brokertopicmetrics_messagesinpersec[5m])"
echo "Under-replicated:       kafka_server_replicamanager_underreplicatedpartitions"
echo "Active controller:      kafka_controller_kafkacontroller_activecontrollercount"
echo "Request handler idle:   kafka_server_kafkarequesthandlerpool_requesthandleravgidlepercent"
echo "Log size by partition:  kafka_log_log_size"
```

### 8.8 Runbook Templates

```markdown
## Runbook: Consumer Lag Increasing

### Symptoms
- Alert: KafkaConsumerLagCritical fired
- Grafana: consumer lag trending up for group `{GROUP_NAME}`

### Investigation
1. Check consumer status:
   kafka-consumer-groups --bootstrap-server localhost:9092 \
     --describe --group {GROUP_NAME}
   → Look for: EMPTY state (no consumers), or high lag on specific partitions

2. Check consumer pod/process:
   kubectl get pods -l app={SERVICE_NAME}
   → Are pods running? OOMKilled? CrashLoopBackOff?

3. Check consumer logs:
   kubectl logs -l app={SERVICE_NAME} --tail=100 | grep -i error

4. Check if lag is on ALL partitions or specific ones:
   → ALL: consumer throughput issue or consumer down
   → SPECIFIC: hot partition or stuck consumer

5. Check producer rate (sudden spike?):
   rate(kafka_server_brokertopicmetrics_messagesinpersec{topic="{TOPIC}"}[5m])

### Remediation
- Consumer down → restart consumer pods
- Processing slow → check downstream dependencies (DB, API)
- Producer spike → scale consumers (add pods)
- Hot partition → investigate key distribution
- Rebalance loop → check max.poll.interval.ms, add static membership

### Escalation
- If lag > 1M and increasing after 30 min → page on-call lead
- If consumer group EMPTY and restart fails → page platform team
```

```markdown
## Runbook: Under-Replicated Partitions

### Symptoms
- Alert: KafkaUnderReplicatedPartitions > 0
- Risk: potential data loss if more brokers fail

### Investigation
1. Identify affected partitions:
   kafka-topics --bootstrap-server localhost:9092 \
     --describe --under-replicated-partitions

2. Identify slow broker:
   → Which broker is NOT in ISR for these partitions?

3. Check slow broker health:
   - CPU: top / kubectl top pod
   - Disk I/O: iostat -x 1
   - GC pauses: JMX jvm_gc_pause_seconds
   - Network: check replication fetch latency

4. Check disk usage on affected broker:
   df -h /var/lib/kafka/data

### Remediation
- GC pauses → tune JVM (reduce heap if > 8GB, use G1GC)
- Disk I/O saturated → move partitions to other brokers
- Network issue → check inter-broker connectivity
- Broker down → wait for recovery, partitions will catch up
- Disk full → increase retention config, add disk, move partitions

### Escalation
- If URP > 30 min → page on-call
- If min.insync.replicas not met → producers blocked → CRITICAL
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Consumer lag = 50K messages, nhưng stable (không tăng). Đây có phải vấn đề không? Khi nào 50K lag là acceptable, khi nào là critical?**
   - Hint: phụ thuộc vào use case. Payment processing: critical. Daily analytics batch: acceptable. Quan trọng là lag STABLE hay INCREASING.

2. **Cluster có 3 brokers, 1 broker có under-replicated partitions > 0 trong 10 phút. Producers vẫn chạy bình thường. Nguy hiểm ở đâu?**
   - Hint: Suy nghĩ về min.insync.replicas và acks=all. Nếu THÊM 1 broker nữa fail → ISR < min.insync → producers bị BLOCKED hoặc data loss nếu unclean leader election enabled.

3. **Team deploy consumer mới, sau đó thấy lag spike rồi giảm dần. Nguyên nhân và cách tránh?**
   - Hint: deploy = consumer restart = rebalance = stop processing = lag tăng. Static group membership (group.instance.id) + cooperative sticky assignor → giảm rebalance impact.

4. **Bạn dùng correlationId trong Kafka headers. Consumer A gửi event trigger Consumer B, B gửi event trigger Consumer C. Làm sao trace toàn bộ chain từ A → B → C?**
   - Hint: correlationId giữ nguyên qua cả chain. causationId = eventId của event trước. Search tất cả logs by correlationId → rebuild the causal graph.

5. **Grafana dashboard shows producer throughput đột ngột giảm 80%. Consumer lag không tăng. Kafka broker metrics bình thường. Vấn đề ở đâu?**
   - Hint: Nếu consumer lag không tăng → producers ngừng gửi (application issue, not Kafka). Check producer application logs, upstream service health.

6. **MirrorMaker 2 active-passive setup. Primary DC down. Bạn cần failover. Liệt kê các bước và rủi ro.**
   - Hint: RPO = replication lag (vài giây data loss possible). Steps: redirect producers, restart consumers on secondary with translated offsets, monitor lag. Risk: events in-flight chưa replicate → duplicate or lost.

7. **kafka-exporter metrics cho thấy consumer group lag = 0 trên TẤT CẢ partitions. Nhưng users báo không nhận được notifications. Debug thế nào?**
   - Hint: Lag = 0 nghĩa là consumer committed offsets = latest. Nhưng committed offset ≠ processed successfully. Consumer có thể commit trước khi xử lý xong (auto-commit) hoặc processing logic bị bug. Check structured logs → outcome field.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Monitoring](https://kafka.apache.org/documentation/#monitoring)
- [Kafka Operations](https://kafka.apache.org/documentation/#operations)
- [MirrorMaker 2 (KIP-382)](https://kafka.apache.org/documentation/#georeplication)
- [Consumer Group Protocol](https://kafka.apache.org/documentation/#consumerconfigs)

### Blog Posts & Articles
- [Confluent — Monitoring Kafka](https://docs.confluent.io/platform/current/kafka/monitoring.html)
- [LinkedIn — Burrow: Kafka Consumer Lag Checking](https://engineering.linkedin.com/apache-kafka/burrow-kafka-consumer-monitoring-reinvented)
- [Uber — Distributed Tracing with Kafka](https://www.uber.com/blog/distributed-tracing/)
- [Datadog — Key Kafka Metrics to Monitor](https://www.datadoghq.com/blog/monitoring-kafka-performance-metrics/)
- [Confluent — MirrorMaker 2 Guide](https://docs.confluent.io/platform/current/multi-dc-deployments/replicator/index.html)

### Videos & Talks
- [Kafka Summit — Monitoring Kafka Like a Pro](https://www.confluent.io/events/kafka-summit/)
- [Confluent Developer — Kafka Operations](https://developer.confluent.io/courses/)
- [GOTO Conference — Observability for Event-Driven Systems](https://www.youtube.com/results?search_query=kafka+observability+opentelemetry)

### Tools
- [JMX Exporter](https://github.com/prometheus/jmx_exporter)
- [kafka-exporter](https://github.com/danielqsj/kafka_exporter)
- [Burrow](https://github.com/linkedin/Burrow)
- [OpenTelemetry Kafka Instrumentation](https://opentelemetry.io/docs/instrumentation/)
