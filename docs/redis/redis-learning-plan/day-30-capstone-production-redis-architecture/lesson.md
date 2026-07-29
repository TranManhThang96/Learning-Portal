# Day 30: Capstone - Production Redis Architecture

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Thiết kế được end-to-end Redis architecture cho hệ thống ride-hailing 100K+ ops/sec: topology, keyspace, persistence, failover, monitoring, security, backup, capacity planning — tất cả tích hợp thành một production blueprint hoàn chỉnh.
- Phân tích và justify được từng architectural decision: tại sao chọn Cluster thay vì Sentinel, tại sao Redis là cache chứ không phải primary store, tại sao dùng Kafka cho event-driven invalidation thay vì DB polling.
- Trình bày được 5 trade-off lớn ở cấp độ system design: Sentinel vs Cluster, cache vs source of truth, consistency vs latency, cost vs availability, operational complexity vs scalability.
- Phác thảo được failure mode analysis và runbook cho hệ thống production: chuẩn bị cho 10+ scenarios từ single-node failure đến full cluster partition.
- Đánh giá được production readiness của một architecture dựa trên checklist 50+ items phủ toàn bộ lifecycle: design, deployment, operation, disaster recovery.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Uber — Redis Cache Storm Khiến toàn bộ Booking Fail

Năm 2017, Uber vận hành hệ thống ride-hailing với Redis làm session store và API cache. Một deployment trigger mass cache invalidation — 500K keys bị xóa đồng thời. Hậu quả:

- 500K requests đánh thẳng vào PostgreSQL primary DB cùng lúc.
- Database connection pool exhausted.
- Booking API latency tăng từ 50ms lên 30 giây.
- Toàn bộ service degraded trong 45 phút.

Root cause: Cache invalidation không có backoff, không có circuit breaker, application không handle cache-miss gracefully. Bài học: **Redis cache failure không chỉ là Redis issue — đó là cascaded failure từ application design**.

### Incident 2: Grab (Southeast Asia Ride-hailing) — Redis Cluster Hot Slot Khiến Matching Fail

Grab xử lý hàng triệu ride requests mỗi ngày qua Redis Cluster. Một promotional event tạo ra surge traffic tập trung vào 1 hash slot chứa hot driver data. P99 latency spike từ 10ms lên 800ms. Matching service timeout liên tục. Drivers không nhận được ride assignments trong 20 phút.

Root cause: Key design dùng hash tag quá tập trung. `{driver_zone_central}` chứa 80% driver location updates. Bài học: **Hot slot trong Cluster không phải edge case — đó là guaranteed failure khi không thiết kế key distribution đúng**.

### Incident 3: Twitter/X — Redis Sentinel Misconfiguration, 2 Masters, Data Divergence

Một team dùng Redis Sentinel với 3 Sentinel nodes nhưng cấu hình sai quorum (đặt = 1). Khi network partition xảy ra, partition nhỏ hơn (1 node) trigger failover → tạo 2 master. Writes đi đến cả 2 masters. Khi network hồi phục, replication divergence cần 3 giờ manual resolution.

Bài học: **Sentinel quorum = 1 trên 3 nodes là lỗi cấu hình nghiêm trọng, không phải valid optimization. Misunderstanding về quorum là nguyên nhân phổ biến nhất của split-brain**.

### Bottom Line

Day 1-29 đã cover từng component riêng lẻ. Day 30 là bài test: bạn có thể kết hợp tất cả lại thành architecture coherent không? Production system không có luxury của "từng ngày học riêng" — tất cả xảy ra đồng thời, và một sai sót ở bất kỳ layer nào đều có thể gây ra toàn bộ system failure.

---

## 3. Kiến thức nền cần có

Day 30 capstone yêu cầu tổng hợp kiến thức từ toàn bộ chương trình. Bảng dưới đây liệt kê những knowledge dependency quan trọng nhất và nơi đã cover:

| Chủ đề | Ngày | Dependency level |
|---|---|---|
| Redis Cluster, hash slots, MOVED/ASK | Day 22-23 | Bắt buộc |
| Sentinel, quorum, failover | Day 20-21 | Bắt buộc |
| Replication internals, replica lag | Day 19 | Bắt buộc |
| Key design, TTL, hash tags | Day 4, Day 22 | Bắt buộc |
| Persistence: AOF + RDB | Day 6-7 | Bắt buộc |
| Eviction policy, memory management | Day 8-9 | Quan trọng |
| Capacity planning | Day 10 | Quan trọng |
| Caching patterns, cache-aside | Day 25-26 | Quan trọng |
| Rate limiting, leaderboard patterns | Day 27 | Quan trọng |
| Distributed lock, coordination | Day 28 | Quan trọng |
| Monitoring, alerting, Prometheus/Grafana | Day 29 | Quan trọng |
| Client retry, circuit breaker | Day 12, Day 21 | Quan trọng |
| Lua scripting | Day 16 | Hữu ích |

---

## 4. Nội dung lý thuyết chi tiết

### 4.1. Scenario: Ride-Hailing Platform "FastRide"

**Tổng quan hệ thống:**

- **Tên**: FastRide — nền tảng ride-hailing tại Việt Nam
- **Quy mô**: 100K+ ops/sec peak, 500K daily active drivers, 2M daily active riders
- **Database chính**: PostgreSQL (driver profiles, rider profiles, trip history, payments)
- **Event streaming**: Apache Kafka (trip events, driver location events, payment events)
- **Redis use cases**:
  - API response cache (driver profiles, rider profiles, fare estimates)
  - Session store (rider sessions, driver app sessions)
  - Rate limiting (API throttling per rider/driver/device)
  - Real-time counters (trip counts, surge multipliers)
  - Leaderboard (driver ratings, driver earnings)
  - Distributed coordination (mutex cho matching, idempotency keys)
  - Geospatial (nearby drivers lookup)
  - Pub/Sub (driver status broadcast, notification fanout)

### 4.2. Redis Topology — Chọn Cluster

**Quyết định: Redis Cluster 6 masters + 12 replicas = 18 nodes**

```
Số liệu nền tảng:
- Target: 100K ops/sec
- Read/Write ratio: 65% read / 35% write
- Peak burst: 200K ops/sec (surge pricing events)
- Average payload size: 500 bytes
- Max memory per node: 16 GB
- Expected hot data: ~50 GB (profiles, sessions, active trips)
- Total keys estimate: 20M keys

Tính toán:
- 100K ops/sec / 6 shards ≈ 16.7K ops/sec per shard
- Read operations: 65K/sec → phân bổ: 60% cache hit → 39K cache reads/sec
- Write operations: 35K/sec → distributed evenly
- Replication: async, max lag < 1s (acceptable cho cache use case)
```

**Chi tiết topology:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                 FastRide Redis Cluster — 18 Nodes                         │
│                                                                             │
│  Shard 1: M1(7000) ←→ R1(7001) ←→ R2(7002)                                │
│  Shard 2: M2(7003) ←→ R3(7004) ←→ R4(7005)                                │
│  Shard 3: M3(7006) ←→ R5(7007) ←→ R6(7008)                                │
│  Shard 4: M4(7009) ←→ R7(7010) ←→ R8(7011)                                │
│  Shard 5: M5(7012) ←→ R9(7013) ←→ R10(7014)                               │
│  Shard 6: M6(7015) ←→ R11(7016) ←→ R12(7017)                             │
│                                                                             │
│  Total: 6 masters + 12 replicas = 18 nodes                                │
│  2 replicas per master, spread across 3 AZs                               │
│  16384 slots / 6 masters ≈ 2730 slots per master                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Node spec khuyến nghị:**

```
Per node:
  - CPU: 4 vCPU (Redis single-threaded nhưng replication và fork tốn CPU)
  - Memory: 16 GB RAM (sử dụng 12 GB, 4 GB headroom)
  - Disk: 100 GB SSD (RDB + AOF)
  - Network: 10 Gbps

Cluster spec:
  - 6 masters × 16 GB = 96 GB total cluster memory
  - 12 replicas × 16 GB = 192 GB replica memory
  - Effective capacity: 96 GB (replicas không tăng write capacity)
  - Usable for data: 80 GB (20% headroom)
```

### 4.3. Data Modeling

**Bảng phân bổ data theo use case:**

| Use Case | Data Type | Key Pattern | TTL | Memory Estimate |
|---|---|---|---|---|
| Driver profile cache | Hash | `driver:{driver_id}:profile` | 24h | 10 GB |
| Rider profile cache | Hash | `rider:{rider_id}:profile` | 12h | 8 GB |
| Rider session | String (JSON) | `session:rider:{rider_id}:{token}` | 30d | 2 GB |
| Driver session | String (JSON) | `session:driver:{driver_id}:{token}` | 7d | 1 GB |
| Active trip | Hash | `trip:{trip_id}` | 2h | 500 MB |
| Rate limit counter | String | `ratelimit:{type}:{id}:{window}` | 60s | 50 MB |
| Driver location (geo) | Geo | `geo:drivers:zone:{zone_id}` | 5m | 2 GB |
| Driver leaderboard | Sorted Set | `leaderboard:drivers:rating` | None | 500 MB |
| Surge multiplier | String | `surge:{zone}:{hour_bucket}` | 30m | 50 MB |
| Matching lock | String (NX) | `lock:match:{zone}` | 10s | 1 MB |
| Idempotency key | String | `idempotency:{request_id}` | 24h | 100 MB |
| Driver availability | String | `driver:{driver_id}:available` | 5m | 100 MB |

**Key naming convention:**

```
Format: <namespace>:<entity>:<entity_id>:<sub_resource>:<version>

Quy tắc:
- namespace: tên service (driver, rider, trip, geo, ratelimit)
- entity: loại entity (profile, session, counter)
- entity_id: unique identifier
- sub_resource: optional, cho细分 data
- version: optional, cho backwards compatibility

Ví dụ:
  driver:profile:{driver_id}           → driver profile cache
  driver:session:{driver_id}:{token}  → driver session (hash tag: {driver_id})
  rider:profile:{rider_id}            → rider profile cache
  trip:active:{trip_id}                → active trip data
  ratelimit:api:{rider_id}:{window}    → API rate limit counter
  geo:driver:zone:{zone_id}            → geo index cho zone
  lock:match:{zone_id}                 → distributed lock cho matching
  leaderboard:driver:rating            → sorted set, all drivers
```

**Hash tag strategy:**

```
Hash tags được dùng khi CẦN multi-key operation trong cluster.
KHÔNG dùng hash tag khi không cần — để key distribution tự nhiên.

Cần hash tag (multi-driver transaction):
  Key pattern: driver:{zone_id}:active
  → Hash tag: {zone_id}
  → Tất cả drivers trong cùng zone cùng slot

Không cần hash tag (independent operations):
  driver:profile:{driver_id}    → Slot dựa trên "driver:profile:100"
  rider:session:{rider_id}:{token}  → Slot dựa trên full key
  leaderboard:driver:rating     → Single sorted set, dùng single node

⚠️ Anti-pattern: {driver_zone_central} hash tag cho toàn bộ drivers
  → 80% keys → 1 slot → hot slot → cluster overload
```

### 4.4. Caching Consistency Strategy

FastRide dùng **cache-aside + Kafka event-driven invalidation**:

```
Read path:
  1. Application reads from Redis cache.
  2. Cache miss → read from PostgreSQL.
  3. Write to Redis with TTL = 24h (driver profile) / 12h (rider profile).
  4. Return to client.

Write path (Cache invalidation):
  1. Application writes to PostgreSQL.
  2. Application publishes event to Kafka: "driver.profile.updated".
  3. Cache invalidation service (consumer) receives event.
  4. Service: DELETE driver:profile:{driver_id} from Redis.
  5. Next read: cache miss → fresh data from DB.

Cache warming (optional, cho critical paths):
  - Sau khi driver login: pre-warm profile cache từ DB.
  - Sau Kafka event: pre-warm nearby driver list.
```

**Event-driven invalidation vs TTL-only:**

```
TTL-only (stale-while-revalidate):
  ✅ Simple, no external dependency
  ✅ Works even when Kafka is down
  ❌ Stale data window = TTL duration (có thể 24h)
  ❌ Cache miss → DB hit → thundering herd nếu hot key expires

Event-driven invalidation:
  ✅ Data stale window = time between DB write + Kafka consume + Redis DELETE
  ✅ Typically < 1 second
  ✅ Cache miss → warm cache → consistent data
  ❌ Kafka là dependency — Kafka down → fallback về TTL-only
  ❌ Complexity: cần Kafka consumer + error handling

Hybrid approach (FastRide):
  - Primary: event-driven invalidation (latency < 1s)
  - Fallback: TTL-based expiration (safety net)
  - TTL = 2× expected invalidation latency (24h driver, 12h rider)
```

### 4.5. Persistence Configuration

```
Per master node (fastride-redis-master.conf):

  # Memory
  maxmemory 12gb
  maxmemory-policy allkeys-lru

  # Persistence
  appendonly yes
  appendfilename "appendonly.aof"
  appendfsync everysec
  aof-rewrite-internal-fsync everysec

  # RDB (backup + fork-based persistence)
  save 900 1
  save 300 10
  save 60 10000
  rdbcompression yes
  rdbchecksum yes

  # Replication
  repl-diskless-sync yes
  repl-diskless-sync-delay 5
  repl-backlog-size 64mb
  min-replicas-to-write 1
  min-replicas-max-lag 5

  # Cluster
  cluster-enabled yes
  cluster-config-file nodes.conf
  cluster-node-timeout 15000
  cluster-replica-validity-factor 10
  cluster-migration-barrier 1
  cluster-require-full-coverage no

  # Security
  protected-mode yes
  requirepass <from Vault>
  masterauth <from Vault>

  # Performance
  tcp-backlog 511
  timeout 10
  tcp-keepalive 300
  lua-time-limit 5000
  slowlog-log-slower-than 10000
```

**Persistence mode rationale:**

```
FastRide chọn: AOF everysec + RDB periodic

Lý do:
- Cache workload (driver profiles, sessions): mất data < 1s không catastrophic
- AOF everysec: write latency overhead thấp (1 fsync/sec)
- RDB periodic (15 min): backup snapshot cho disaster recovery
- repl-diskless-sync: faster replication, ít disk I/O

Không dùng:
- AOF always: write latency spike quá cao (every command = 1 fsync)
- AOF no: mất toàn bộ data nếu crash
- RDB only: mất tất cả writes trong 15 phút
```

### 4.6. Failover Strategy

```
Automatic Failover (Redis Cluster):
  Trigger: master không respond trong cluster-node-timeout (15s)
  Sequence:
    T+0s:    Master M1 unresponsive
    T+15s:   Replica R1 detects SDOWN → votes for failover
    T+15-16s: Quorum masters approve
    T+16-18s: R1 executes CLUSTER FAILOVER
    T+18s:    R1 promoted to master, gossip propagates
    T+18-20s: All clients redirect to R1 (MOVED)

  Total: ~20 seconds automatic failover

Manual Failover (Planned Maintenance):
  Before maintenance:
    1. Verify replica lag = 0
    2. CLUSTER FAILOVER FORCE on replica (graceful)
    3. Wait 30s for replication to settle
    4. Proceed with maintenance on old master

Post-failover:
  5. Verify new master has all slots
  6. Monitor replication from new master to remaining replicas
  7. Old master returns as replica automatically
```

### 4.7. Client Timeout & Retry Strategy (TypeScript)

```typescript
// src/redis-client.ts
import Redis from "ioredis";

const CLUSTER_NODES = [
  { host: "127.0.0.1", port: 7000 },
  { host: "127.0.0.1", port: 7003 },
  { host: "127.0.0.1", port: 7006 },
  { host: "127.0.0.1", port: 7009 },
  { host: "127.0.0.1", port: 7012 },
  { host: "127.0.0.1", port: 7015 },
];

export const cluster = new Redis.Cluster(CLUSTER_NODES, {
  redisOptions: {
    password: process.env.REDIS_PASSWORD,
    connectTimeout: 10000,
    maxRetriesPerRequest: 3,
    retryStrategy: (times: number) => {
      if (times > 10) return null; // Stop retry
      return Math.min(times * 200, 3000);
    },
    enableReadyCheck: true,
    enableOfflineQueue: true,
  },
  clusterRetryStrategy: (times: number) => {
    if (times > 20) return null;
    return Math.min(times * 1000, 30000);
  },
  slotsRefreshTimeout: 10000,
  slotsRefreshInterval: 1000,
  redirects: 16, // Max MOVED/ASK redirects before error
  scaleReads: "masters", // Read from masters for strong consistency
});

cluster.on("error", (err: Error) => {
  console.error(`[Redis Cluster Error] ${err.message}`);
});

cluster.on("reconnecting", () => {
  console.warn("[Redis] Reconnecting to cluster...");
});

// --- Connection pool per service ---
export function createClientPool(serviceName: string, size = 10): Redis[] {
  const pool: Redis[] = [];
  for (let i = 0; i < size; i++) {
    const node = CLUSTER_NODES[i % CLUSTER_NODES.length];
    const client = new Redis({
      host: node.host,
      port: node.port,
      password: process.env.REDIS_PASSWORD,
      connectTimeout: 5000,
      maxRetriesPerRequest: 3,
      retryStrategy: (times) => Math.min(times * 100, 1000),
    });
    pool.push(client);
  }
  return pool;
}
```

### 4.8. Monitoring Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    FastRide Redis Monitoring Dashboard                      │
│                                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│  │ OVERVIEW        │ │ MEMORY          │ │ LATENCY         │          │
│  │ cluster_state   │ │ used_memory     │ │ cmdstat_GET     │          │
│  │ connected_nodes │ │ mem_fragmentation│ │ cmdstat_SET     │          │
│  │ ops/sec (total) │ │ maxmemory_used  │ │ p50/p95/p99     │          │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│                                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│  │ REPLICATION     │ │ CACHE METRICS   │ │ CLUSTER HEALTH  │          │
│  │ master_offset   │ │ keyspace_hits   │ │ slots_assigned  │          │
│  │ replica_lag    │ │ keyspace_misses │ │ nodes_healthy   │          │
│  │ connected_slaves│ │ hit_rate        │ │ cluster_state   │          │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ PER-SHARD MEMORY & OPS (heatmap: 6 shards × memory/ops)         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ ALERT PANEL                                                    │    │
│  │ ⚠ cluster_state=fail | mem > 80% | replica_lag > 5s | p99 > 50ms│    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key metrics & thresholds:**

| Metric | Warning | Critical | Action |
|---|---|---|---|
| `cluster_state` | — | `fail` | Immediate incident |
| `used_memory_human` | > 12 GB (80%) | > 14 GB (93%) | Scale shard |
| `repl_backlog_histlen` | > 50 MB | approaching limit | Add replica |
| `cluster_node_timeout` | > 1 node unreachable | > 2 nodes unreachable | Investigate |
| `cmdstat_get_latency_p99` | > 20ms | > 50ms | Investigate slow command |
| `keyspace_hits / total` (hit rate) | < 85% | < 70% | Tune TTL/key design |
| `evicted_keys` | > 100/sec | > 1000/sec | Increase memory |
| `blocked_clients` | > 5 | > 20 | Investigate slow command |
| `connected_clients` | > 8000 | > 10000 | Check connection leak |

---

## 5. Trade-off Analysis

### 5.1. Sentinel vs Cluster

| Aspect | Sentinel | Cluster |
|---|---|---|
| **Horizontal scaling** | Không (single master) | Yes (multiple masters, sharding) |
| **Write throughput** | Single master limit (~150K ops/sec) | Sum of all shards |
| **100K+ ops/sec** | ⚠️ Borderline, cần vertical scale | ✅ Native support |
| **Hot key handling** | Single node → bottleneck | Spread across shards |
| **Data distribution** | Full replication to all replicas | Sharded, no cross-node transaction |
| **Multi-key operations** | Full support | Limited (same slot hoặc cross-slot error) |
| **Failover complexity** | Sentinel quorum (3 nodes) | Cluster gossip (per-shard) |
| **Operational complexity** | Lower | Higher |
| **FastRide verdict** | ❌ Không đủ cho 100K ops/sec | ✅ Cluster 6 shards |

**FastRide chọn Cluster vì**: 100K ops/sec vượt Sentinel single-master capacity, hot keys không thể scale bằng Sentinel, cluster cần sharding để phân bổ load.

### 5.2. Redis as Cache vs Source of Truth

| Aspect | Redis as Cache | Redis as Source of Truth |
|---|---|---|
| **Durability** | Loss acceptable (TTL-based) | Loss unacceptable |
| **Consistency** | Eventually consistent | Strongly consistent |
| **Persistence config** | Minimal (RDB backup only) | AOF always + RDB |
| **Failure impact** | Cache miss → DB fallback | Data unavailable → service down |
| **Use case fit** | API cache, sessions, counters | Distributed lock, idempotency |
| **FastRide verdict** | ✅ Profiles, sessions, counters | ✅ Locks, idempotency keys |

**FastRide principle**: Redis là **cache with persistence** cho data (profiles, trips), là **source of truth** cho coordination primitives (locks, idempotency). KHÔNG bao giờ dùng Redis làm primary store cho entity data.

### 5.3. Strong Consistency vs Low Latency

| Aspect | Strong Consistency | Low Latency |
|---|---|---|
| **Read path** | Read from master | Read from replica |
| **Replica lag** | Not tolerated | Tolerated (< 5s) |
| **Read latency** | Higher (master only) | Lower (replica spread) |
| **Consistency model** | Linearizable | Eventual |
| **Use case fit** | Payment, matching lock | Profile display, leaderboard |
| **FastRide verdict** | ✅ Distributed lock, idempotency | ✅ Profile cache, leaderboard |

**FastRide decision per use case:**

- Matching lock: `SET NX PX` + read from master only
- Driver profile read: read from nearest replica (stale < 5s acceptable)
- Leaderboard: read from master (snapshot, not critical)
- Idempotency: read from master (prevent double-spend)
- Rate limit: local read (eventual counter, not critical)

### 5.4. Cost vs Availability

| Aspect | Minimize Cost | Maximize Availability |
|---|---|---|
| **Node count** | 6 nodes (6 masters, 0 replica) | 18 nodes (6 masters + 12 replicas) |
| **Memory per node** | 8 GB | 16 GB |
| **Cross-AZ replicas** | Same AZ | Multi-AZ (3 AZs) |
| **Availability SLA** | 99% (8.7h downtime/month) | 99.99% (4.3min downtime/month) |
| **FastRide verdict** | ❌ Không accept single-replica risk | ✅ Multi-AZ 3 replicas |

**FastRide rationale**: Ride-hailing là business-critical. 4 phút downtime/tháng tốt hơn 8.7 giờ. Chi phí replica = insurance premium. 3 AZ deployment đảm bảo 1 AZ failure không gây outage.

### 5.5. Redis vs Kafka vs Database (Use Case Matrix)

| Use Case | Redis | Kafka | PostgreSQL | FastRide Chọn |
|---|---|---|---|---|
| API response cache | ✅ | ❌ | ❌ | Redis |
| Session store | ✅ | ❌ | ❌ | Redis |
| Rate limiting | ✅ | ❌ | ❌ | Redis |
| Leaderboard | ✅ | ❌ | ❌ | Redis |
| Real-time counters | ✅ | ❌ | ❌ | Redis |
| Distributed lock | ✅ | ❌ | ❌ | Redis |
| Geospatial lookup | ✅ | ❌ | ❌ | Redis |
| Event streaming | ❌ | ✅ | ❌ | Kafka |
| Event-driven cache invalidation | Consumer only | ✅ | ❌ | Kafka |
| Persistent trip record | ❌ | ✅ (temp) | ✅ (permanent) | PostgreSQL |
| Driver profile (permanent) | Cache | ❌ | ✅ | PostgreSQL |
| Payment ledger | ❌ | ❌ | ✅ | PostgreSQL |

**Nguyên tắc chọn:**

```
Chọn Redis khi:
  - Data có thể tái tạo từ primary DB (cache)
  - Cần sub-millisecond latency
  - Data là ephemeral (session, counter, lock)
  - Scale horizontally qua sharding

Chọn Kafka khi:
  - Data cần durable log (audit trail, event sourcing)
  - Multiple consumers cùng consume một event stream
  - Cần replay từ offset cũ
  - Event-driven coordination (cache invalidation, notifications)

Chọn PostgreSQL khi:
  - Data cần strong consistency
  - Data là source of truth (payments, trips)
  - Cần complex queries (JOIN, aggregation)
  - Data cần ACID transaction
  - Data cần long-term retention
```

---

## 6. Best Solution & Best Practices

### 6.1. Architecture Decision Record (ADR) — FastRide

```
ADR-001: Redis Cluster vs Sentinel
Status: APPROVED
Context: FastRide cần 100K+ ops/sec, multi-service, hot key protection
Decision: Redis Cluster 6 masters + 12 replicas, multi-AZ
Consequences:
  - Write throughput: linear scale theo shard count
  - Hot key: spread across 6 masters
  - Operational: cao hơn Sentinel, cần cluster-aware client
  - Cross-slot: không dùng multi-key operations trên keys khác shard

ADR-002: Redis as Cache vs Source of Truth
Status: APPROVED
Context: Driver profiles, trip data cần consistency nhưng không cần Redis làm store
Decision: Redis là cache với PostgreSQL là primary store
  - Cache invalidation via Kafka events
  - TTL fallback (24h driver, 12h rider)
  - Idempotency/lock: Redis là source of truth (short-lived)
Consequences:
  - Data loss acceptable: max 24h staleness
  - Cache stampede: mitigated via probabilistic early refresh
  - Kafka dependency: fallback TTL-only khi Kafka down

ADR-003: Persistence Strategy
Status: APPROVED
Context: Cache workload, acceptable data loss < 1s
Decision: AOF everysec + RDB periodic (15 min)
Consequences:
  - Write latency: +1-2ms overhead (fsync everysec)
  - Data loss: max 1s of writes
  - Recovery time: ~30s from AOF + RDB
```

### 6.2. Anti-patterns cần tránh

| Anti-pattern | Tại sao sai | Đúng |
|---|---|---|
| Dùng Redis làm primary store cho entity | Data loss khi Redis crash, không có backup chiến lược | PostgreSQL là primary, Redis là cache |
| Không có TTL trên session keys | Unbounded memory growth | TTL = 2× expected session lifetime |
| Dùng hash tag cho toàn bộ keyspace | Hot slot → cluster bottleneck | Chỉ dùng hash tag khi cần multi-key operation |
| `KEYS *` trong production | Blocking, scan entire dataset | `SCAN` với COUNT limit |
| Dùng replica read cho matching lock | Stale data → wrong lock acquisition | Read from master |
| Không set `maxmemory` | OOM → crash | maxmemory = 80% RAM, eviction policy = allkeys-lru |
| Dùng `FLUSHDB` trong production | Xóa toàn bộ data | `UNLINK` cho lazy delete |
| Dùng single Redis instance | Single point of failure | Cluster với replicas |

---

## 7. Performance Considerations

### 7.1. Capacity Planning Worksheet

```
FastRide Redis Capacity Planning

INPUTS:
  Peak ops/sec:          100,000
  Read ratio:            65%
  Write ratio:           35%
  Avg payload (bytes):   500
  Active drivers:        500,000
  Active riders:         2,000,000
  Active trips:          50,000

CALCULATIONS:
  Read ops/sec:          65,000
  Write ops/sec:         35,000
  Keys in cache:         ~20,000,000
  Avg key size:          200 bytes (hash fields)
  Avg value size:        300 bytes (JSON payload)
  Memory per key:        ~80 bytes overhead + value

MEMORY ESTIMATE:
  Driver profiles:       500K × 500B = 250 MB
  Rider profiles:        2M × 300B = 600 MB
  Sessions:              2.5M × 200B = 500 MB
  Active trips:          50K × 1KB = 50 MB
  Rate limit counters:   5M × 50B = 250 MB
  Driver locations:      500K × 100B = 50 MB
  Leaderboards:          1M × 100B = 100 MB
  Misc:                  ~200 MB
  ─────────────────────────────
  Total working set:     ~2.0 GB

  With 5× growth headroom: 10 GB
  With fragmentation (1.5×): 15 GB
  Recommended per-node: 16 GB RAM (12 GB used, 4 GB OS)

SHARD CALCULATIONS:
  Per shard: 15 GB / 6 shards ≈ 2.5 GB per shard (low!)
  Re-evaluate: 16 GB nodes cho future growth
  Shard ops capacity: 100K / 6 ≈ 16.7K ops/sec per shard
  Single Redis: ~30K-50K ops/sec → 6 shards = 180K-300K ops/sec total

  ✅ Safe for 100K steady load: 6 shards × 30K ops/sec = 180K ops/sec conservative capacity
  ⚠ 200K burst requires measured per-shard capacity > 34K ops/sec or adding a 7th master
```

### 7.2. Latency SLO

| Metric | SLO | p95 Target | p99 Target |
|---|---|---|---|
| GET (local shard) | < 5ms | < 2ms | < 5ms |
| MGET (same slot) | < 10ms | < 5ms | < 10ms |
| WRITE (master) | < 10ms | < 5ms | < 15ms |
| GEO query | < 20ms | < 10ms | < 30ms |
| ZADD/ZRANK (leaderboard) | < 15ms | < 8ms | < 20ms |
| Lua script (rate limit) | < 10ms | < 5ms | < 15ms |
| Cluster MOVED redirect | +5ms | +2ms | +8ms |
| Failover time | < 30s | < 25s | < 30s |

### 7.3. Network & Infrastructure Requirements

```
Per-node bandwidth estimate:
  100K ops/sec × 500 bytes avg = 50 MB/s = 400 Mbps peak
  Per shard: 400 Mbps / 6 ≈ 67 Mbps
  With replication: 67 Mbps × 1.5 (replication overhead) ≈ 101 Mbps
  → 10 Gbps NIC fully sufficient

Cross-AZ bandwidth:
  6 AZs × 2 replicas × 86 Mbps = 1 Gbps inter-AZ
  Use dedicated high-speed link for replication traffic
```

---

## 8. Production Failure Modes

### 8.1. Single Node Failure

```
Symptom: 1 Redis master/replica unreachable
Detection: cluster health alert, monitoring heartbeat
Impact: 
  - Master down: automatic failover (~20s), brief write latency spike
  - Replica down: reads continue from master, replication lag warning
Fix: Automatic (Cluster handles), manual verify after 60s
Prevention: 3 replicas per shard (1 same AZ, 2 cross-AZ)
```

### 8.2. Hot Slot (Hash Tag Collision)

```
Symptom: One shard có p99 latency 10× so với shards khác
Detection: per-shard latency monitoring, CLUSTER COUNTKEYSINSLOT
Cause: Hash tag collision → 1 slot chứa disproportionate keys
Fix:
  1. Identify hot slot: CLUSTER GETKEYSINSLOT <hot-slot> 100
  2. Analyze key pattern → find collision root cause
  3. Refactor key design (remove hash tag hoặc dùng sub-keys)
  4. Reshard: redistribute slots
Prevention: Key design review, per-slot monitoring dashboard
```

### 8.3. Cache Stampede (Thunder Herd on TTL Expiry)

```
Symptom: Periodic spike in DB load, Redis cache miss rate spike
Detection: keyspace_misses spike, DB CPU spike
Cause: Many keys expire at same TTL timestamp → simultaneous cache miss
Fix:
  1. Jitter TTL: TTL × (1 + random(0, 0.2))
  2. Lua script mutex: only 1 process refreshes cache
  3. Background refresh: refresh cache 80% through TTL
Prevention: TTL jitter on all cache keys, pre-warm critical keys
```

### 8.4. Cluster Partition (Split-Brain Risk)

```
Symptom: Cluster state = fail, writes rejected
Detection: cluster_state metric, sentinel alert
Cause: Network partition → minority nodes can't reach majority
Impact:
  - With cluster-require-full-coverage = no: writes to healthy slots continue
  - With cluster-require-full-coverage = yes: all writes fail
Fix:
  1. Verify network: check AWS/GCP network health
  2. Restore connectivity
  3. Verify: cluster_state = ok, no divergent data
Prevention: Multi-AZ spread, cluster-require-full-coverage = no
```

### 8.5. OOM (Out of Memory)

```
Symptom: Redis writes fail với OOM error, eviction rate spike
Detection: used_memory > maxmemory, evicted_keys spike
Cause:
  - Working set grew beyond maxmemory
  - Big key growth không được monitor
  - Memory fragmentation
Fix:
  1. Emergency: increase maxmemory (if headroom exists)
  2. Identify big keys: redis-cli --bigkeys
  3. Flush stale keys: SCAN + UNLINK
  4. Temporary: switch to volatile-lru if using allkeys-lru
Prevention: Memory headroom > 30%, big key monitoring, alert at 80%
```

### 8.6. Replication Lag Accumulation

```
Symptom: Read from replica returns stale data (lag > 5s)
Detection: INFO replication → master_repl_offset - slave0_repl_offset
Cause:
  - Master write burst exceeds replica network capacity
  - Slow replica (underpowered)
  - Network congestion cross-AZ
Fix:
  1. Throttle writes on master (circuit breaker)
  2. Check replica network: iperf3
  3. Upgrade replica if underpowered
Prevention: repl-backlog-size >= 64 MB, cross-AZ bandwidth >= 100 Mbps
```

### 8.7. Kafka Down (Cache Invalidation Stops)

```
Symptom: Cache keys không bị invalid khi DB updated
Detection: Event lag monitoring in Kafka consumer
Impact: Stale data cached up to TTL (24h)
Fix:
  1. Application: fallback to TTL-only invalidation
  2. Alert: Kafka consumer lag alert
  3. Restore Kafka: restart consumer group
Prevention: Kafka SLA 99.9%, TTL = 2× expected invalidation time
```

### 8.8. MOVED Storm Post-Resharding

```
Symptom: Error rate spike, MOVED response count spike after resharding
Detection: cmdstat_moved spike, error rate > 1%
Cause: Client slot map stale after resharding, retry → MOVED loop
Fix:
  1. Restart clients in batches (not all at once)
  2. Ioredis: client.cluster("CLUSTER SLOTS") to force refresh
Prevention: Cluster-aware client, test MOVED handling in CI
```

---

## 9. Real-world Examples

### Twitter Timeline Service — Redis at Scale

Twitter dùng Redis từ những ngày đầu với client-side sharding (trước Redis Cluster). Timeline service lưu trữ user timelines trong Redis với:
- Key: `timeline:{user_id}` (List, max 800 entries)
- Write path: khi user posts tweet → fanout đến all followers' timelines (Redis LPUSH)
- Read path: timeline read from Redis → served from cache

**Architecture lessons**:
- Twitter dùng Redis là **primary store** cho timelines (không phải cache) → phải chấp nhận durability risk.
- Sharding strategy: hash ring với virtual nodes để smooth distribution.
- MOVED storm xảy ra khi mở rộng shard count.

### Uber Michelangelo — Redis for Real-time Feature Store

Uber xây dựng Michelangelo platform với Redis cho real-time feature store:
- Drivers/riders features (location, ratings, surge) cached in Redis.
- Feature computation: Kafka streams → compute features → write to Redis.
- Model serving: read features from Redis → predict in < 10ms.

**Architecture lessons**:
- Redis là cache nhưng **latency SLA < 10ms** → phải có hot key strategy.
- Feature cache invalidation: Kafka consumer deletes stale features on new event.
- Memory estimation: features = 500M × 100 bytes = 50 GB → 4-node cluster.

### Shopify — Redis Session + Cart

Shopify dùng Redis Cluster 6 shards cho session và cart:
- Key: `session:{session_id}`, `cart:{shop_id}:{cart_id}`
- TTL: 30 days (session), unbounded (cart — deleted on checkout)
- Cache invalidation: explicit DELETE on order completion

**Architecture lessons**:
- Session: Redis là source of truth (short-lived, idempotent).
- Cart: Redis là cache (PostgreSQL is source, Redis for fast read).
- Cart invalidation: explicit DELETE trên order, không rely on TTL.

### Grab — Geospatial + Real-time Matching

Grab dùng Redis GEO commands cho nearby driver lookup:
- `GEOADD geo:drivers:zone:{zone}` để index driver locations.
- `GEORADIUS` để find drivers within 5km of rider.
- Update frequency: every 5 seconds per active driver.

**Architecture lessons**:
- GEO index: single Redis key per zone → hash tag cho per-zone operations.
- Hot zone (downtown): many drivers → single key with many members → O(log N) GEORADIUS.
- Mitigation: zone sharding (split large zones into sub-zones).

---

## 10. Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Dùng Redis làm primary store mà không backup chiến lược | Data loss khi Redis crash không recoverable | PostgreSQL là primary, Redis là cache |
| Không monitor memory fragmentation | Memory usage > 80% nhưng fragmentation ratio = 2.0 | `MEMORY DOCTOR`, enable active-defrag |
| Dùng hash tag không có analysis | Hot slot → cluster bottleneck | Analyze slot distribution trước khi deploy |
| TTL = 0 (no expiry) trên unbounded keys | Memory growth → OOM | TTL always, monitor key count growth |
| Dùng replica read cho critical write-path logic | Stale data → wrong decision | Read from master for consistency-critical paths |
| Retry Redis quá aggressive | Retry storm → Redis overload | Exponential backoff, circuit breaker |
| Không test failover | Failover fail khi cần nhất | Chaos test quarterly, simulate master kill |
| Misconfigure quorum Sentinel | Split-brain → 2 masters | Quorum = majority of (Sentinel + 1), min 3 |
| Dùng FLUSHDB trong production | Toàn bộ data mất | SCAN + UNLINK for selective delete |

---

## 11. Câu Hỏi Tự Kiểm Tra

### Câu 1: Topology Decision

Bạn thiết kế Redis cho hệ thống e-commerce 150K ops/sec peak, 80% reads. Propose topology: bao nhiêu shards, replicas, multi-AZ hay single-AZ, và tại sao không chọn Sentinel?

> **Đáp án**:
> - **Topology**: Redis Cluster, 8-10 masters × 2 replicas = 24-30 nodes.
> - **Shards**: 150K ops/sec / 30K ops/sec per shard ≈ 5 shards minimum. Chọn 8 shards để có 2× headroom.
> - **Replicas**: 2 per master (1 same AZ, 1 cross-AZ) → total 24 nodes.
> - **Multi-AZ**: Yes, spread across 3 AZs để protect against AZ failure.
> - **Không chọn Sentinel** vì: 150K ops/sec vượt single-master throughput (~150K max theoretical). Sentinel không support horizontal scaling → hot key bottleneck on single master. Cluster là lựa chọn duy nhất.

### Câu 2: Cache Invalidation Design

FastRide dùng Kafka để invalidate driver profile cache. Kafka consumer bị lag 30 giây. Driver cập nhật profile lúc T=0. Rider đọc driver profile lúc T=15 (Kafka lag 15s). Rider đọc driver profile lúc T=45 (Kafka đã consume). Mô tả data staleness ở mỗi thời điểm và đề xuất mitigation.

> **Đáp án**:
> - **T=0**: Driver write → PostgreSQL → Kafka event published. Redis: old data.
> - **T=15**: Rider reads → cache hit → **stale data** (profile chưa updated). Stale window: 15s.
> - **T=30**: Kafka event consumed → Redis cache deleted. Rider reads → cache miss → fresh data from PostgreSQL → **consistent**.
> - **Kafka lag 30s**: stale window = 30s.
> - **Mitigation**:
>   - Primary: Kafka consumer lag monitoring + alert (target: lag < 5s).
>   - Fallback: TTL-based expiry (driver profile TTL = 24h, quá dài → reduce to 4h).
>   - Hybrid: invalidate-on-read pattern: check Kafka timestamp in cache value, if stale → delete + re-fetch.
>   - Design: profile update không phải latency-critical → acceptable.

### Câu 3: Hot Slot Mitigation

Trong FastRide, `geo:drivers:zone:{zone_id}` chứa 200K driver locations cho zone "downtown_hcm". GEORADIUS queries bị latency spike. Phân tích nguyên nhân và đề xuất 3 cách fix.

> **Đáp án**:
> **Nguyên nhân**: Tất cả drivers trong zone "downtown_hcm" dùng cùng hash tag `{zone_id}` → cùng slot. 200K GEOADD/ZRADIUS → single node bottleneck.
>
> **3 cách fix**:
>
> **Cách 1: Zone splitting** (Recommended)
> - Split "downtown_hcm" thành sub-zones: "downtown_hcm_grid_1", "downtown_hcm_grid_2", ... (e.g., 1km×1km grid cells).
> - Rider query: xác định grid cell từ lat/lng → query correct geo key.
> - Benefit: distribute across multiple slots.
>
> **Cách 2: Multi-key read** (Read replicas + round-robin)
> - Read geo queries từ read replicas (eventual consistency OK for driver location).
> - Spread load across 3 replicas của shard chứa "downtown_hcm" slot.
>
> **Cách 3: Cache geo results** (Application-level)
> - Cache GEORADIUS results trong Redis với short TTL (5-10s).
> - Matching service: read from cache → less GEORADIUS commands.
> - Trade-off: slightly stale driver list, but acceptable for matching.

### Câu 4: Failover Impact on Rate Limiting

Redis Cluster master down trong 20 giây (failover). Tác động gì đến rate limiting? Làm thế nào để design rate limiting resilient với failover?

> **Đáp án**:
> **Impact khi master down**:
> - Rate limit counter trên master unavailable → reads return error hoặc stale.
> - Writes (increment) fail → rate limit không update → over-permitting (security risk).
> - Replica has stale counters (20s lag) → if reads from replica → under-permitting (UX degradation).
>
> **Resilient design**:
> - **Local rate limit** (token bucket in-memory): fast path, handles 99% of requests.
> - **Redis rate limit** (distributed): audit/limit per device across multiple instances.
> - **Graceful degradation**: if Redis unavailable → fall back to local rate limit (with reduced limit, e.g., 50% of normal).
> - **Sliding window**: use Redis Sorted Set with timestamp → safe to read from replica with age check.
> - **Circuit breaker**: if Redis error rate > 5% → open circuit → local rate limit only.

### Câu 5: Capacity Planning Error

Một team estimate: "50GB memory per node là đủ cho 100K ops/sec". Sau 1 tháng, Redis OOM. Phân tích 5 sai lầm phổ biến trong capacity planning và cách tránh.

> **Đáp án**:
> **5 sai lầm**:
>
> 1. **Không tính memory fragmentation**: jemalloc overhead + fragmentation → actual usable memory 30-50% less than physical. Fix: maxmemory = 70% physical RAM.
>
> 2. **Không tính per-key overhead**: key name + Redis object overhead (~50 bytes/key) + pointer overhead. 10M keys × 50B = 500 MB overhead.
>
> 3. **Không có growth headroom**: estimate cho current load, không cho future. Fix: plan for 3-6 months growth.
>
> 4. **Không tính replica memory**: replica requires same memory as master. 1 master + 1 replica = 2× memory usage.
>
> 5. **Không monitor actual usage**: dựa vào theoretical calculation thay vì actual metrics. Fix: use `INFO memory` và `MEMORY USAGE` command.
>
> **Correct approach**: Memory = (working_set × fragmentation × headroom) + replication_overhead. Example: 50GB working set × 1.5 fragmentation × 1.5 headroom × 2 (replication) = 225 GB → ~38 GB per node for 6-node cluster.

### Câu 6: Redis vs DB Choice

Thiết kế data storage cho "driver earnings leaderboard" (top 100 drivers by daily earnings). Các options: Redis Sorted Set, PostgreSQL with index, Kafka for real-time streaming. Đánh giá từng option.

> **Đáp án**:
> **Option 1: Redis Sorted Set**
> - Pros: O(log N) ZADD, O(log N + M) ZRANGE (top M), sub-ms latency, native ranking.
> - Cons: In-memory only (data loss risk), no complex filtering (per-day needs separate key), TTL management needed.
> - Best for: Real-time leaderboard, top-K queries, high-frequency updates.
>
> **Option 2: PostgreSQL with index**
> - Pros: Durable, complex queries, filter by date/zone/status, ACID.
> - Cons: Write-heavy (every trip completion → UPDATE), slower for top-K queries (needs covering index).
> - Best for: Historical analysis, audit trail, complex reports.
>
> **Option 3: Kafka for real-time aggregation**
> - Pros: Real-time stream processing, multiple consumers, replay capability.
> - Cons: Not a store, needs separate aggregation system (Flink/Spark), complex.
> - Best for: Real-time analytics pipeline, not real-time serving.
>
> **FastRide decision**: Redis Sorted Set for real-time leaderboard (read latency < 5ms), PostgreSQL as source of truth for earnings history, Kafka to sync Redis with DB (periodic dump every hour).

### Câu 7: Security Audit Failure

Sau security audit, team phát hiện: Redis không có password, ACL, TLS, và dùng `protected-mode no`. Đánh giá risk và đề xuất remediation plan.

> **Đáp án**:
> **Risk assessment**:
> - No password: anyone in network → full read/write access → data breach, data corruption.
> - No ACL: all applications dùng same credentials → no per-service access control.
> - No TLS: all traffic in plaintext → man-in-the-middle → credential/ data interception.
> - protected-mode no: Redis bind to 0.0.0.0 → exposed to internet if misconfigured.
>
> **Remediation plan (phased, zero-downtime)**:
>
> **Phase 1 (Immediate — 1 day)**:
> - Enable `protected-mode yes` (prevent accidental exposure).
> - Enable `bind 127.0.0.1` (Redis only accessible from within cluster network).
> - Network-level firewall: restrict port 7000-7017 to cluster nodes only.
>
> **Phase 2 (Short-term — 1 week)**:
> - Set `requirepass` via `CONFIG SET requirepass` (runtime) + update redis.conf (persistent).
> - Store password in Vault, inject via environment variable.
> - Test: verify without password → access denied.
>
> **Phase 3 (Medium-term — 1 month)**:
> - Enable Redis ACL: define user roles (app, monitoring, backup).
> - Example: `user app on >password ~* &* +@all`, `user monitor on >pass ~* &* +@read +@ping`.
> - `rename-command FLUSHDB ""` (disable dangerous commands for app user).
>
> **Phase 4 (Long-term — 3 months)**:
> - Enable TLS (certificate rotation plan needed).
> - All client connections must use TLS.
> - Redis Cluster: TLS for both client connections và cluster bus.
> - Audit: quarterly access review.
