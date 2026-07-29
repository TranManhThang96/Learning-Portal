# Redis Production-Ready trong 30 Ngày — Khóa học cho Senior Developer

> Chương trình huấn luyện chuyên sâu giúp Senior Backend Engineer master Redis ở mức production: hiểu internals, trade-off, failure mode, vận hành thực tế và thiết kế architecture cho hệ thống 100K+ ops/sec.

---

## 1. Tổng quan chương trình

- **Đối tượng**: Senior Software Engineer đã thành thạo TypeScript / Go / Java / Python / PHP và có nền tảng system design, microservices, database optimization.
- **Thời lượng**: 30 ngày, mỗi ngày khoảng 2 giờ thực hành (đọc lý thuyết → lab → challenge → reflection).
- **Triết lý**:
  - Không chỉ học command, mà phải hiểu **trade-off**, **internals**, **failure mode** và **operation thực tế**.
  - Tự thiết kế, triển khai, monitor, benchmark và troubleshoot Redis cho hệ thống lớn.
  - Luôn bám phong cách production-grade: số liệu cụ thể (p95/p99, ops/sec, bytes), bảng so sánh, scenario-based question, không "best fits all".
- **Mục tiêu sau khóa học**:
  - Thiết kế Redis architecture cho hệ thống 100K+ ops/sec.
  - Chọn đúng giữa standalone, Sentinel, Cluster, client-side / proxy-based sharding.
  - Thiết kế keyspace, TTL, eviction, persistence theo từng use case.
  - Debug latency spike, memory issue, big key, hot key, replication lag, failover incident.
  - Implement rate limiting, session store, leaderboard, idempotency key, distributed lock, cache-aside an toàn.
  - Setup monitoring, alerting, troubleshooting runbook và capacity planning.
  - Biết khi nào **không nên dùng Redis** và nên thay bằng Kafka / DB / Memcached / etcd / Consul.

---

## 2. Prerequisites

| Thành phần | Phiên bản khuyến nghị | Ghi chú |
|---|---|---|
| Docker | 24.x+ | Cần Docker Compose v2 |
| Docker Compose | v2.20+ | Cú pháp `docker compose` |
| Redis | 7.2+ | Một số bài cần Redis Stack (RedisBloom, RedisJSON) |
| Go | 1.22+ | Dùng `github.com/redis/go-redis/v9` |
| Node.js | 20 LTS+ | Dùng `ioredis` hoặc `@redis/client` |
| TypeScript | 5.x | Strict mode |
| `redis-cli` | 7.2+ | Khuyến nghị cài qua container hoặc package manager |
| `redis-benchmark` | 7.2+ | Bundled cùng Redis |
| `memtier_benchmark` | latest | Optional, dùng từ Day 13 |

**Kiến thức nền cần có:**

- Hiểu fundamentals về backend service, REST/RPC, database transaction.
- Quen với network basics: TCP, RTT, TLS, connection pooling.
- Có kinh nghiệm với ít nhất 1 database (PostgreSQL / MySQL / MongoDB).
- Quen với distributed systems concepts: consistency, replication, partitioning.
- Đã từng làm việc với observability stack (Prometheus, Grafana, ELK).

---

## 3. Hướng dẫn setup môi trường

### 3.1. Redis standalone (cho Phase 1–4)

```yaml
# docker-compose.standalone.yml
services:
  redis:
    image: redis:7.2
    container_name: redis-standalone
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
volumes:
  redis-data:
```

```bash
docker compose -f docker-compose.standalone.yml up -d
docker exec -it redis-standalone redis-cli PING
```

### 3.2. Redis Stack (cần cho Day 3, 16, 18 — bao gồm RedisBloom, Streams, RedisJSON)

```yaml
# docker-compose.stack.yml
services:
  redis-stack:
    image: redis/redis-stack:7.2.0-v6
    ports:
      - "6379:6379"
      - "8001:8001"   # RedisInsight UI
    volumes:
      - redis-stack-data:/data
volumes:
  redis-stack-data:
```

### 3.3. Redis master + replica (Day 19)

```yaml
# docker-compose.replica.yml
services:
  redis-master:
    image: redis:7.2
    ports: ["6379:6379"]
    command: redis-server --appendonly yes
  redis-replica-1:
    image: redis:7.2
    ports: ["6380:6379"]
    command: redis-server --replicaof redis-master 6379 --appendonly yes
    depends_on: [redis-master]
  redis-replica-2:
    image: redis:7.2
    ports: ["6381:6379"]
    command: redis-server --replicaof redis-master 6379 --appendonly yes
    depends_on: [redis-master]
```

### 3.4. Redis Sentinel (Day 20)

Yêu cầu tối thiểu 3 Sentinel node + 1 master + 2 replica. Compose template chi tiết sẽ được cung cấp tại `day-20-sentinel-and-high-availability/`.

### 3.5. Redis Cluster 6 nodes (Day 22–24)

```bash
# Quick setup bằng image redis với cluster create
docker run -d --name redis-cluster -p 7000-7005:7000-7005 \
  -e "IP=0.0.0.0" \
  grokzen/redis-cluster:7.2.0
```

Hoặc tự build cluster bằng 6 container Redis 7.2 + `redis-cli --cluster create` (template chi tiết tại `day-22-redis-cluster-and-hash-slots/`).

### 3.6. Redis exporter + Prometheus + Grafana (Day 29)

Stack monitoring full sẽ có template Compose ở `day-29-observability-security-and-troubleshooting/document.md`.

---

## 4. Lộ trình 30 ngày

### Phase 1 — Foundation, Data Structures & Data Modeling

- [x] [Day 1: Redis Architecture & Production Use Cases](./day-01-redis-architecture-and-use-cases/)
- [x] [Day 2: Core Data Structures](./day-02-core-data-structures/)
- [x] [Day 3: Advanced Data Structures](./day-03-advanced-data-structures/)
- [x] [Day 4: Key Design & Redis Data Modeling](./day-04-key-design-and-data-modeling/)
- [x] [Day 5: Encoding Internals & Memory Footprint](./day-05-encoding-internals-and-memory-footprint/)

### Phase 2 — Persistence, Memory & Capacity Planning

- [x] [Day 6: Persistence RDB & AOF](./day-06-persistence-rdb-aof/)
- [x] [Day 7: AOF Rewrite & Durability Trade-off](./day-07-aof-rewrite-and-durability-tradeoff/)
- [x] [Day 8: Memory Management & Eviction](./day-08-memory-management-and-eviction/)
- [x] [Day 9: Memory Optimization & Fragmentation](./day-09-memory-optimization-and-fragmentation/)
- [x] [Day 10: Capacity Planning Basics](./day-10-capacity-planning-basics/)

### Phase 3 — Performance Engineering

- [x] [Day 11: Pipelining & Batching](./day-11-pipelining-and-batching/)
- [x] [Day 12: Connection Pooling & Client Behavior](./day-12-connection-pooling-and-client-behavior/)
- [x] [Day 13: Latency Analysis & Benchmarking](./day-13-latency-analysis-and-benchmarking/)
- [x] [Day 14: Hot Key & Big Key Problems](./day-14-hot-key-and-big-key-problems/)

### Phase 4 — Atomicity, Scripting & Messaging

- [x] [Day 15: Transactions, WATCH & Atomicity](./day-15-transactions-watch-and-atomicity/)
- [x] [Day 16: Lua Scripting & Redis Functions](./day-16-lua-scripting-and-redis-functions/)
- [x] [Day 17: Pub/Sub Patterns & Limitations](./day-17-pubsub-patterns-and-limitations/)
- [x] [Day 18: Redis Streams & Consumer Groups](./day-18-redis-streams-and-consumer-groups/)

### Phase 5 — High Availability, Replication & Cluster

- [x] [Day 19: Replication Internals](./day-19-replication-internals/)
- [x] [Day 20: Sentinel & High Availability](./day-20-sentinel-and-high-availability/)
- [x] [Day 21: Failover, Client Retry & Chaos Lab](./day-21-failover-client-retry-and-chaos-lab/)
- [x] [Day 22: Redis Cluster & Hash Slots](./day-22-redis-cluster-and-hash-slots/)
- [x] [Day 23: Sharding Strategies & Key Distribution](./day-23-sharding-strategies-and-key-distribution/)
- [x] [Day 24: Cluster Operations & Resharding](./day-24-cluster-operations-and-resharding/)

### Phase 6 — Production Patterns

- [x] [Day 25: Caching Patterns & Consistency](./day-25-caching-patterns-and-consistency/)
- [x] [Day 26: Cache Stampede & Thundering Herd](./day-26-cache-stampede-and-thundering-herd/)
- [x] [Day 27: Rate Limiting, Session & Leaderboard Patterns](./day-27-rate-limiting-session-leaderboard-patterns/)
- [x] [Day 28: Distributed Locking & Coordination](./day-28-distributed-locking-and-coordination/)

### Phase 7 — Observability, Security, Troubleshooting & Capstone

- [x] [Day 29: Observability, Security & Troubleshooting](./day-29-observability-security-and-troubleshooting/)
- [x] [Day 30: Capstone — Production Redis Architecture](./day-30-capstone-production-redis-architecture/)

---

## 5. Cấu trúc file mỗi ngày

```txt
day-NN-topic/
├── lesson.md       # 11 sections: mục tiêu, motivation, kiến thức nền, lý thuyết,
│                   # trade-off, best practices, performance, failure modes,
│                   # real-world examples, common pitfalls, self-check questions
├── document.md     # cheat sheet, config templates, code snippets (TS/Go), links
└── exercises.md    # warm-up (15–20'), hands-on lab (60–70'), challenge (30–40'),
                    # reflection, solution guide
```

Phong cách viết:

- Tiếng Việt chuyên nghiệp, súc tích, đi thẳng vấn đề.
- Giữ nguyên thuật ngữ tiếng Anh chuyên ngành (caching, sharding, replication, latency, throughput, eviction, hot key, big key, fragmentation, failover, backpressure, circuit breaker…).
- Không dịch command Redis, tên data structure, tên module, tên tool.
- Code runnable, không pseudo-code.
- Ưu tiên bảng so sánh thay vì paragraph dài.
- Luôn nói trade-off, không "best fits all".
- Số liệu cụ thể (ops/sec, p95/p99 latency, bytes, MB).

---

## 6. Capstone expectation (Day 30)

Cuối khóa, học viên phải produce được **architecture document** hoàn chỉnh cho một hệ thống production giả lập (e-commerce / ride-hailing / food delivery, 100K+ ops/sec, multi-service), bao gồm:

- **Architecture diagram** (Mermaid): Redis topology, cách Redis tương tác với Application, DB chính, Kafka, các service.
- **Topology decision**: standalone vs Sentinel vs Cluster — lý do, số node, replica, shard strategy.
- **Key design spec**: namespace convention, TTL strategy, hash tag rules, versioning policy.
- **Capacity planning sheet**: memory estimate, throughput estimate, connection count, headroom, replica overhead, network bandwidth, disk sizing.
- **Persistence + eviction policy**: RDB / AOF / hybrid + eviction policy theo từng use case.
- **Monitoring dashboard spec**: metrics phải track, Grafana panel structure, alert rules.
- **Failure mode analysis**: top 5–10 failure scenario + mitigation.
- **Runbook**: failover, backup/restore, resharding, cache stampede recovery.
- **Production readiness checklist**: 20–30 items đảm bảo trước khi go-live.
- **Security**: ACL, TLS, network isolation, command renaming.

---

## 7. Tiêu chí chất lượng cuối khóa

Học viên phải có thể:

- [ ] Thiết kế Redis architecture cho hệ thống 100K+ ops/sec.
- [ ] Chọn đúng giữa standalone, Sentinel, Cluster, client-side sharding, proxy-based sharding.
- [ ] Thiết kế key naming, TTL strategy, eviction policy production-ready.
- [ ] Phân tích RDB vs AOF vs hybrid persistence theo use case cụ thể.
- [ ] Debug latency spike, memory issue, big key, hot key, replication lag, failover.
- [ ] Viết Lua scripts và Redis Functions an toàn (atomic, deterministic, không blocking).
- [ ] Implement rate limiting, session store, leaderboard, idempotency key, cache-aside, distributed lock.
- [ ] Hiểu khi nào nên / không nên dùng Redis Streams, Pub/Sub.
- [ ] Hiểu khi nào Redis lock an toàn, khi nào không (Redlock criticism, fencing token).
- [ ] Setup monitoring, alerting, troubleshooting runbook.
- [ ] Làm capacity planning cho Redis production.
- [ ] Phân tích failure modes và đề xuất mitigation.
- [ ] Biết khi nào nên thay Redis bằng Kafka, database, Memcached, etcd / ZooKeeper / Consul, hoặc application-level cache.

---

## 8. Resources bổ sung

### Docs chính thức

- [Redis Documentation](https://redis.io/docs/) — bắt buộc đọc kèm
- [Redis Commands Reference](https://redis.io/commands/) — tra cứu nhanh
- [Redis Source Code (GitHub)](https://github.com/redis/redis) — `src/server.c`, `src/dict.c`, `src/object.c`, `src/aof.c`, `src/rdb.c`
- [Redis University](https://university.redis.com/) — khoá miễn phí RU101/RU102/RU202

### Blog & paper kỹ thuật

- [antirez (Salvatore Sanfilippo) blog](http://antirez.com/) — tư duy thiết kế Redis từ tác giả gốc
- [Redis at Twitter Engineering](https://blog.twitter.com/engineering/) — case study scale lớn
- [How Discord Stores Trillions of Messages](https://discord.com/blog/) — cassandra, nhưng có insight về caching
- [Martin Kleppmann: How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — Redlock criticism (đọc trước Day 28)
- [antirez phản biện Kleppmann](http://antirez.com/news/101)
- *Designing Data-Intensive Applications* — Martin Kleppmann (chapter 5, 7, 9)

### Benchmark & tools

- `redis-benchmark` (bundled với Redis)
- [`memtier_benchmark`](https://github.com/RedisLabs/memtier_benchmark) — workload realistic hơn
- [`redis-cli --latency`](https://redis.io/docs/management/optimization/latency-monitor/) — intrinsic latency
- [RedisInsight](https://redis.io/insight/) — GUI debugging, SLOWLOG viewer

### Monitoring

- [redis_exporter (Prometheus)](https://github.com/oliver006/redis_exporter)
- [Grafana Redis Dashboard #11835](https://grafana.com/grafana/dashboards/11835)
- [Datadog Redis integration docs](https://docs.datadoghq.com/integrations/redisdb/)

### Module & ecosystem

- [RedisBloom](https://redis.io/docs/data-types/probabilistic/) — Bloom Filter, Cuckoo, CMS, Top-K
- [Redis Stack](https://redis.io/docs/about/about-stack/) — Redis core + RedisJSON + RediSearch + RedisBloom + RedisTimeSeries
- [RedisJSON](https://redis.io/docs/data-types/json/)
- [RediSearch](https://redis.io/docs/interact/search-and-query/)

---

## 9. Quy ước phong cách trong khóa học

- **Trade-off luôn được nêu rõ**: với mỗi quyết định kỹ thuật, luôn có context "nên / không nên dùng".
- **Failure mode-first**: đọc một concept luôn kèm "lỗi gì xảy ra trong production khi hiểu sai".
- **p95/p99 over average**: khi nói latency, luôn dùng percentile.
- **Senior-level tone**: không giải thích những thứ Senior đã biết (HTTP basics, JSON, OOP cơ bản…).
- **Real number**: throughput, memory, latency phải có số liệu cụ thể. Tránh "rất nhanh", "rất tốn", "khá lớn".
- **Code runnable**: không pseudo-code, không "..." để skip. Mỗi snippet phải copy-paste chạy được.
- **Bảng > paragraph**: bất cứ khi nào có ≥ 3 lựa chọn so sánh, dùng bảng.

---

## 10. Tiến độ hiện tại

| Phase | Day | Trạng thái |
|---|---|---|
| 1 | 1–5 | ✅ Hoàn thành |
| 2 | 6–10 | ✅ Hoàn thành |
| 3 | 11–14 | ✅ Hoàn thành |
| 4 | 15–18 | ✅ Hoàn thành |
| 5 | 19–24 | ✅ Hoàn thành |
| 6 | 25–28 | ✅ Hoàn thành |
| 7 | 29–30 | ✅ Hoàn thành |

> Đã hoàn tất Day 1–30 (toàn bộ 7 Phase). Tổng cộng 90 file (lesson + document + exercises × 30 ngày).
