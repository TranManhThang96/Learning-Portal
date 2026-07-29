# Redis Production-Ready — 30 ngày từ Senior Backend đến Redis Expert

Lộ trình dành cho Senior Software Engineer muốn master Redis ở mức production: hiểu internals, trade-off, failure mode, vận hành thực tế và thiết kế architecture cho hệ thống 100K+ ops/sec. 30 ngày, mỗi ngày ~2 giờ thực hành, local-first với Docker Compose.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể áp dụng Redis vào production:

1. [Day 01: Redis Architecture & Production Use Cases](./redis-learning-plan/day-01-redis-architecture-and-use-cases/lesson) — single-threaded model, khi nào nên/không nên dùng Redis
2. [Day 02: Core Data Structures](./redis-learning-plan/day-02-core-data-structures/lesson) — String, Hash, List, Set, Sorted Set — Big O, trade-off
3. [Day 08: Memory Management & Eviction](./redis-learning-plan/day-08-memory-management-and-eviction/lesson) — maxmemory, eviction policies, LRU vs LFU
4. [Day 11: Pipelining & Batching](./redis-learning-plan/day-11-pipelining-and-batching/lesson) — giảm RTT, batch tối ưu
5. [Day 14: Hot Key & Big Key Problems](./redis-learning-plan/day-14-hot-key-and-big-key-problems/lesson) — detection, mitigation — lỗi production phổ biến nhất
6. [Day 15: Transactions, WATCH & Atomicity](./redis-learning-plan/day-15-transactions-watch-and-atomicity/lesson) — optimistic locking, race conditions
7. [Day 19: Replication Internals](./redis-learning-plan/day-19-replication-internals/lesson) — PSYNC, replication lag, consistency trade-off
8. [Day 22: Redis Cluster & Hash Slots](./redis-learning-plan/day-22-redis-cluster-and-hash-slots/lesson) — cluster architecture, 16384 hash slots
9. [Day 25: Caching Patterns & Consistency](./redis-learning-plan/day-25-caching-patterns-and-consistency/lesson) — cache-aside, read-through, write-through, stale data handling
10. [Day 28: Distributed Locking & Coordination](./redis-learning-plan/day-28-distributed-locking-and-coordination/lesson) — Redlock, fencing token, khi nào an toàn

Sau 10 bài này bạn đã có thể thiết kế Redis caching strategy, debug hot/big key, cấu hình eviction/persistence, và implement distributed lock an toàn cho production.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---|
| Phase 1 — Foundation & Data Structures | Day 01-05 | Architecture, core/advanced data structures, key design, encoding | Production use case checklist, data modeling cheat sheet |
| Phase 2 — Persistence & Memory | Day 06-10 | RDB/AOF, eviction, memory optimization, capacity planning | Persistence config, memory analysis, capacity worksheet |
| Phase 3 — Performance Engineering | Day 11-14 | Pipelining, connection pooling, latency analysis, hot/big key | Benchmark report, latency troubleshooting guide |
| Phase 4 — Atomicity & Messaging | Day 15-18 | Transactions, Lua scripting, Pub/Sub, Streams | Lua scripts, Streams consumer group, reliability patterns |
| Phase 5 — High Availability & Cluster | Day 19-24 | Replication, Sentinel, failover, Cluster, sharding | Sentinel/Cluster setup, failover runbook, sharding strategy |
| Phase 6 — Production Patterns | Day 25-28 | Caching patterns, cache stampede, rate limiting, distributed locking | Production pattern implementations, lock analysis |
| Phase 7 — Observability & Capstone | Day 29-30 | Monitoring, security, troubleshooting, capstone design | Grafana dashboard, security checklist, architecture doc |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 1 | Redis Architecture & Use Cases | Nền tảng tư duy; không hiểu single-threaded model → dùng blocking command treo server |
| Day 2 | Core Data Structures | 5 structures là atomic building blocks; Big O sai → latency spike |
| Day 4 | Key Design & Data Modeling | Thiết kế keyspace sai → không scale được, hot key, migration đau đớn |
| Day 6 | Persistence RDB & AOF | Không hiểu persistence → mất dữ liệu khi restart (incident #1 của Redis) |
| Day 8 | Memory Management & Eviction | Eviction policy sai → cache miss ồ ạt, DB bị storm |
| Day 11 | Pipelining & Batching | Không pipeline → RTT cost gấp N lần, throughput giảm 10-50x |
| Day 14 | Hot Key & Big Key | Lỗi production phổ biến nhất; không biết detect → downtime |
| Day 19 | Replication | Async replication → stale read; không hiểu PSYNC → replication broken |
| Day 22 | Redis Cluster | Scale vượt single node; hash slots, MOVED/ASK |
| Day 25 | Caching Patterns | Cache-aside là pattern #1; consistency model ảnh hưởng toàn bộ architecture |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 3 | Advanced Data Structures | Bitmap, HyperLogLog, Bloom filter giải quyết bài toán cụ thể với memory thấp |
| Day 5 | Encoding Internals | Hiểu memory footprint → thiết kế data model tiết kiệm 30-50% memory |
| Day 7 | AOF Rewrite & Durability | fsync policy ảnh hưởng latency, rewrite gây fork overhead |
| Day 12 | Connection Pooling | Pool sai → connection storm, reconnect thảm họa |
| Day 15 | Transactions & WATCH | Optimistic locking pattern quan trọng cho inventory, reservation |
| Day 18 | Redis Streams | Reliable message queue pattern; PEL, consumer group |
| Day 28 | Distributed Locking | Redlock criticism; biết khi nào an toàn, khi nào không |

### Nhóm C — Học sau khi đã làm được project cơ bản

| Bài | Chủ đề | Vì sao để học sau |
|---|---|---|
| Day 9 | Memory Optimization & Fragmentation | Active defrag, jemalloc tuning — chỉ cần khi có memory issue |
| Day 10 | Capacity Planning | Cần số liệu thực tế từ hệ thống đang chạy mới tính chính xác |
| Day 13 | Latency Analysis & Benchmarking | Cần baseline từ hệ thống thật; benchmark synthetic dễ误导 |
| Day 16 | Lua Scripting & Redis Functions | Atomic server-side logic; cần khi transaction không đủ |
| Day 20 | Sentinel & HA | Automation failover; cần khi có replica |
| Day 23 | Sharding Strategies | Client-side vs proxy vs cluster sharding |
| Day 24 | Cluster Operations | Resharding, add/remove node — operations production |
| Day 26 | Cache Stampede | Mitigation pattern nâng cao: mutex, probabilistic early expiration |
| Day 27 | Rate Limiting & Patterns | Fixed/sliding window, token bucket — implementation pattern |
| Day 29 | Observability & Security | Monitoring, ACL, TLS — ops work |

### Nhóm D — Đọc lướt / tra cứu khi cần

| Bài | Chủ đề | Vì sao chưa cần học kỹ |
|---|---|---|
| Day 17 | Pub/Sub | Fire-and-forget, ít dùng trong production; Streams là bản nâng cấp |
| Day 21 | Failover & Chaos Lab | Simulation nâng cao; cần khi đã có HA setup thật |
| Day 30 | Capstone | Tổng hợp toàn bộ kiến thức; nên làm sau khi đã học hết nhóm A+B |

## Lộ trình học đề xuất

### Giai đoạn 1 — Học để bắt đầu dùng Redis đúng (7 ngày)

Thời lượng: ~14 giờ

Nên học: Day 1 → Day 2 → Day 4 → Day 6 → Day 8 → Day 11 → Day 25

Mục tiêu:
- Setup Redis, hiểu architecture, dùng đúng data structure
- Thiết kế keyspace, TTL, eviction policy
- Cấu hình persistence tránh mất dữ liệu
- Implement cache-aside pattern

### Giai đoạn 2 — Học để vận hành và debug (7 ngày)

Thời lượng: ~14 giờ

Nên học: Day 3 → Day 5 → Day 7 → Day 12 → Day 14 → Day 15 → Day 19

Mục tiêu:
- Phát hiện và xử lý hot key, big key
- Connection pooling đúng cách
- Transaction và optimistic locking
- Hiểu replication và consistency trade-off

### Giai đoạn 3 — Học để scale và production (7 ngày)

Thời lượng: ~14 giờ

Nên học: Day 18 → Day 22 → Day 25 → Day 26 → Day 27 → Day 28 → Day 29

Mục tiêu:
- Scale với Redis Cluster
- Caching patterns nâng cao, cache stampede mitigation
- Distributed locking an toàn
- Monitoring, alerting, security

### Giai đoạn 4 — Chuyên sâu và Capstone (9 ngày)

Thời lượng: ~18 giờ

Nên học: Day 9 → Day 10 → Day 13 → Day 16 → Day 20 → Day 23 → Day 24 → Day 21 → Day 30

Mục tiêu:
- Memory optimization
- Capacity planning
- Benchmark và latency analysis
- Lua scripting
- Sentinel HA, failover
- Cluster operations
- Capstone architecture design

## Mini project nên làm để kiểm chứng kiến thức

### Project 1: E-commerce Cache Layer

Thiết kế caching layer cho e-commerce system với Redis:
- API response cache (cache-aside, TTL with jitter)
- Product inventory với optimistic locking (WATCH)
- Rate limiting cho public API (sliding window)
- Leaderboard cho top sản phẩm (Sorted Set)

Kiến thức áp dụng: Day 1-4, 8, 11, 15, 25, 27

### Project 2: Production Redis Operations

Setup và vận hành Redis production cluster:
- Master-replica với Sentinel (3 nodes)
- Monitoring với Prometheus + Grafana (redis_exporter)
- Chaos testing: kill master, measure failover time
- Capacity planning cho 50K ops/sec

Kiến thức áp dụng: Day 6-10, 13, 19-21, 29

### Project 3: Real-time Coordination Service

Xây dựng coordination service dùng Redis:
- Distributed lock cho job scheduler
- Reliable job queue với Redis Streams + consumer group
- Distributed rate limiting
- Idempotency key cho payment-like API

Kiến thức áp dụng: Day 14-16, 18, 26-28

## Checklist học nhanh

- [ ] Tôi đã hiểu Redis single-threaded model và impact lên performance
- [ ] Tôi đã biết khi nào nên / không nên dùng Redis
- [ ] Tôi đã thiết kế được keyspace với namespace, TTL, eviction policy
- [ ] Tôi đã cấu hình RDB/AOF persistence cho use case cụ thể
- [ ] Tôi đã implement cache-aside pattern an toàn
- [ ] Tôi đã biết detect và xử lý hot key, big key
- [ ] Tôi đã setup master-replica và hiểu replication lag
- [ ] Tôi đã implement distributed lock an toàn (biết Redlock criticism)
- [ ] Tôi đã thiết kế Redis Cluster với hash tags
- [ ] Tôi đã setup monitoring với Prometheus/Grafana

## Flashcard / câu hỏi ôn tập

1. **Câu hỏi**: Vì sao Redis single-threaded nhưng vẫn nhanh?
   - **Đáp án**: I/O multiplexing (epoll/kqueue), in-memory, CPU cache friendly data structures, không context switch overhead
   - **Liên quan**: Day 1

2. **Câu hỏi**: Khi nào dùng Hash thay vì String key riêng lẻ?
   - **Đáp án**: Khi cần group nhiều field liên quan, ít thay đổi field riêng lẻ, tiết kiệm memory (nhất là với encoding listpack)
   - **Liên quan**: Day 2, 5

3. **Câu hỏi**: Sự khác biệt giữa RDB và AOF?
   - **Đáp án**: RDB snapshot định kỳ, restore nhanh, mất dữ liệu theo interval. AOF ghi từng command, durable hơn (everysec), restore chậm hơn, file lớn hơn. Hybrid là best practice.
   - **Liên quan**: Day 6

4. **Câu hỏi**: Khi nào chọn allkeys-lru vs volatile-lfu?
   - **Đáp án**: allkeys-lru: cache thuần (không quan tâm key nào bị evict). volatile-lfu: khi có cả cache và persistent data, chỉ evict key có TTL, dùng LFU cho hot data ưu tiên.
   - **Liên quan**: Day 8

5. **Câu hỏi**: WATCH khác gì với lock?
   - **Đáp án**: WATCH là optimistic locking — không block, kiểm tra version khi EXEC, fail nếu có thay đổi. Lock là pessimistic — block người khác. WATCH phù hợp cho contention thấp, lock cho contention cao.
   - **Liên quan**: Day 15

6. **Câu hỏi**: Vì sao Redis Cluster cần tối thiểu 6 nodes?
   - **Đáp án**: 3 master + 3 replica. Mỗi master cần ít nhất 1 replica để HA. Lost quorum nếu mất master + replica cùng lúc.
   - **Liên quan**: Day 22

7. **Câu hỏi**: Khi nào Redis lock KHÔNG an toàn?
   - **Đáp án**: Khi có clock drift (Redlock), khi critical section chạy lâu hơn lock TTL, khi cần fencing token nhưng không implement. Dùng etcd/ZooKeeper cho distributed coordination nghiêm túc.
   - **Liên quan**: Day 28

8. **Câu hỏi**: Cache stampede là gì và mitigation?
   - **Đáp án**: Nhiều request đồng thời miss cache → cùng gọi DB → DB overload. Mitigation: mutex lock, probabilistic early expiration, stale-while-revalidate, jittered TTL.
   - **Liên quan**: Day 26

9. **Câu hỏi**: Redis Pub/Sub vs Streams khác nhau thế nào?
   - **Đáp án**: Pub/Sub: fire-and-forget, không persistence, mất message nếu không có subscriber. Streams: persisted, consumer group, PEL, XACK — giống Kafka hơn.
   - **Liên quan**: Day 17, 18

10. **Câu hỏi**: Hot key là gì và cách xử lý?
    - **Đáp án**: Một key bị request quá nhiều → CPU spike, network saturation. Cách xử lý: split key (shard by suffix), local cache (application), read replica, hoặc thay đổi data model.
    - **Liên quan**: Day 14

## Ghi chú cuối cùng

Redis là công cụ cực mạnh nhưng chỉ mạnh khi hiểu đúng. Luôn đặt câu hỏi "trade-off là gì?" trước mỗi quyết định. Không có best solution fits all. Nếu cần durable message queue, dùng Kafka. Nếu cần distributed coordination, dùng etcd. Nếu cần in-memory cache, Redis là lựa chọn số một — nhưng phải config đúng eviction, persistence, memory, và monitoring.
