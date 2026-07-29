# Day 30: Capstone - Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript + Go (mixed capstone)
**Redis**: 7.2+ với Cluster mode enabled

---

## 0. Setup

```bash
# Clone the capstone project structure
mkdir -p day30-capstone && cd day30-capstone
mkdir -p src monitoring backups grafana-dashboards

# Create project
npm init -y
npm install ioredis pg kafkajs prom-client
npm install -D typescript ts-node @types/node

npx tsc --init

cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "strict": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
EOF

# Docker Compose (run from parent directory)
# docker compose -f docker-compose.capstone.yml up -d
# Wait 15s for cluster to form
```

```yaml
# docker-compose.capstone.yml (minimal 3-shard cluster)
version: "3.8"
services:
  redis-m1: &redis-base
    image: redis:7.2-alpine
    ports: ["7000:6379"]
    volumes: ["./redis-data/m1:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
    restart: unless-stopped
  redis-m2:
    image: redis:7.2-alpine
    ports: ["7003:6379"]
    volumes: ["./redis-data/m3:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
    restart: unless-stopped
  redis-m3:
    image: redis:7.2-alpine
    ports: ["7006:6379"]
    volumes: ["./redis-data/m5:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
    restart: unless-stopped
  redis-r1:
    image: redis:7.2-alpine
    ports: ["7001:6379"]
    volumes: ["./redis-data/r1:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
      --replicaof redis-m1 6379
    restart: unless-stopped
  redis-r2:
    image: redis:7.2-alpine
    ports: ["7004:6379"]
    volumes: ["./redis-data/r4:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
      --replicaof redis-m2 6379
    restart: unless-stopped
  redis-r3:
    image: redis:7.2-alpine
    ports: ["7007:6379"]
    volumes: ["./redis-data/r7:/data"]
    command: >
      redis-server --port 6379 --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 15000
      --appendonly yes --maxmemory 256mb
      --replicaof redis-m3 6379
    restart: unless-stopped
```

```bash
# Start containers
docker compose -f docker-compose.capstone.yml up -d
sleep 10

# Form cluster: 3 masters + 3 replicas
docker exec redis-m1 redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7003 127.0.0.1:7006 \
  127.0.0.1:7001 127.0.0.1:7004 127.0.0.1:7007 \
  --cluster-replicas 1 \
  --cluster-yes

# Verify cluster health
docker exec redis-m1 redis-cli -p 7000 CLUSTER INFO
# Expected: cluster_state:ok, cluster_slots_assigned:16384
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Inspect Your Cluster Topology

```bash
# List all nodes and their roles
redis-cli -p 7000 CLUSTER NODES

# Get cluster info
redis-cli -p 7000 CLUSTER INFO

# Count slots per master
echo "=== Slot distribution ==="
for port in 7000 7003 7006; do
  slots=$(redis-cli -p $port CLUSTER NODES | grep myself | grep -oP '\d+(?=\[)')
  echo "Port $port: $(echo $slots | wc -w) slots"
done

# Verify replication
echo "=== Replication status ==="
for port in 7000 7003 7006; do
  echo "--- Master port $port ---"
  redis-cli -p $port INFO replication | grep -E "role|connected_slaves"
done
```

### 1.2. Verify Key Distribution Quality

```bash
# Insert 1000 keys and check slot distribution
for i in $(seq 1 1000); do
  redis-cli -p 7000 SET "driver:profile:$i" "{\"id\":$i,\"name\":\"Driver $i\"}"
done

# Count keys per master (verify even distribution)
echo "=== Keys per master ==="
for port in 7000 7003 7006; do
  count=$(redis-cli -p $port DBSIZE)
  echo "Port $port: $count keys"
done

# Find which slot a hot key belongs to
SLOT=$(redis-cli -p 7000 CLUSTER KEYSLOT "driver:profile:1")
echo "Key driver:profile:1 belongs to slot: $SLOT"

# Count keys in that slot
redis-cli -p 7000 CLUSTER COUNTKEYSINSLOT $SLOT
```

### 1.3. Test Cache Pattern (Cache-Aside)

```bash
# Step 1: Set a driver profile (simulating DB write)
redis-cli -p 7000 SET "driver:profile:1001" '{"id":1001,"name":"Nguyen Van A","rating":4.8,"trips":1250}'

# Step 2: Read it back (cache hit)
redis-cli -p 7000 GET "driver:profile:1001"

# Step 3: Delete it (simulating cache invalidation)
redis-cli -p 7000 DEL "driver:profile:1001"

# Step 4: Read again (cache miss — would fall back to DB)
redis-cli -p 7000 GET "driver:profile:1001"
# Expected: nil

# Cleanup
redis-cli -p 7000 KEYS "driver:*" | head -5 | xargs -I {} redis-cli -p 7000 DEL {}
```

### 1.4. Test Distributed Lock

```bash
# Acquire lock on zone "zone_downtown_hcm"
LOCK_KEY="lock:match:zone_downtown_hcm"
TOKEN="worker-$(date +%s)"

redis-cli -p 7000 SET $LOCK_KEY $TOKEN NX EX 10
# Expected: OK (lock acquired)

# Try to acquire same lock (should fail)
redis-cli -p 7000 SET $LOCK_KEY "worker-2" NX EX 10
# Expected: nil (already held)

# Release lock (with token check — simulated)
redis-cli -p 7000 DEL $LOCK_KEY

# Verify released
redis-cli -p 7000 GET $LOCK_KEY
# Expected: nil
```

---

## 2. Hands-on Lab (60-70 phút)

**Scenario**: Bạn là Senior Backend Engineer tại FastRide. Thiết kế và implement phần core của hệ thống Redis: (A) Cluster client với retry và circuit breaker, (B) Cache-aside service cho driver profiles, (C) Rate limiter với Lua script, (D) Mermaid architecture diagram generator.

### 2.1. Part A: Cluster Client with Retry & Circuit Breaker

```typescript
// src/redis-cluster-client.ts
import Redis from "ioredis";

interface CircuitBreakerState {
  failures: number;
  lastFailure: number;
  state: "CLOSED" | "OPEN" | "HALF_OPEN";
}

class CircuitBreaker {
  private failures = 0;
  private lastFailure = 0;
  private state: "CLOSED" | "OPEN" | "HALF_OPEN" = "CLOSED";
  private readonly threshold: number;
  private readonly timeout: number; // ms before half-open

  constructor(threshold = 5, timeoutMs = 30000) {
    this.threshold = threshold;
    this.timeout = timeoutMs;
  }

  recordSuccess(): void {
    this.failures = 0;
    this.state = "CLOSED";
  }

  recordFailure(): void {
    this.failures++;
    this.lastFailure = Date.now();
    if (this.failures >= this.threshold) {
      this.state = "OPEN";
    }
  }

  canExecute(): boolean {
    if (this.state === "CLOSED") return true;
    if (this.state === "OPEN") {
      if (Date.now() - this.lastFailure > this.timeout) {
        this.state = "HALF_OPEN";
        return true;
      }
      return false;
    }
    return true; // HALF_OPEN
  }

  getState(): string {
    return this.state;
  }
}

const CLUSTER_NODES = [
  { host: "127.0.0.1", port: 7000 },
  { host: "127.0.0.1", port: 7003 },
  { host: "127.0.0.1", port: 7006 },
];

export class FastRideRedisCluster {
  private client: Redis;
  private circuitBreaker: CircuitBreaker;
  private readonly logger: (msg: string) => void;

  constructor(logger: (msg: string) => void = console.log) {
    this.logger = logger;
    this.circuitBreaker = new CircuitBreaker(5, 30000);

    this.client = new Redis.Cluster(CLUSTER_NODES, {
      redisOptions: {
        connectTimeout: 5000,
        maxRetriesPerRequest: 2,
        retryStrategy: (times) => {
          if (times > 3) return null;
          return Math.min(times * 200, 2000);
        },
        enableReadyCheck: true,
      },
      clusterRetryStrategy: (times) => {
        if (times > 10) return null;
        return Math.min(times * 500, 10000);
      },
      slotsRefreshTimeout: 10000,
      redirects: 8,
      scaleReads: "masters",
    });

    this.client.on("error", (err) => {
      this.logger(`[Redis Error] ${err.message}`);
      this.circuitBreaker.recordFailure();
    });

    this.client.on("reconnecting", () => {
      this.logger("[Redis] Reconnecting...");
    });

    this.client.on("ready", () => {
      this.logger("[Redis] Cluster ready");
    });
  }

  async get(key: string): Promise<string | null> {
    if (!this.circuitBreaker.canExecute()) {
      this.logger(`[CircuitBreaker] OPEN — skipping GET ${key}`);
      return null;
    }

    try {
      const result = await this.client.get(key);
      this.circuitBreaker.recordSuccess();
      return result;
    } catch (err: any) {
      this.circuitBreaker.recordFailure();
      this.logger(`[Redis GET Error] ${err.message}`);
      return null;
    }
  }

  async set(key: string, value: string, ttlSeconds?: number): Promise<boolean> {
    if (!this.circuitBreaker.canExecute()) {
      this.logger(`[CircuitBreaker] OPEN — skipping SET ${key}`);
      return false;
    }

    try {
      if (ttlSeconds) {
        await this.client.setex(key, ttlSeconds, value);
      } else {
        await this.client.set(key, value);
      }
      this.circuitBreaker.recordSuccess();
      return true;
    } catch (err: any) {
      this.circuitBreaker.recordFailure();
      this.logger(`[Redis SET Error] ${err.message}`);
      return false;
    }
  }

  async del(key: string): Promise<boolean> {
    try {
      await this.client.del(key);
      return true;
    } catch (err: any) {
      this.logger(`[Redis DEL Error] ${err.message}`);
      return false;
    }
  }

  getCircuitBreakerState(): string {
    return this.circuitBreaker.getState();
  }

  async close(): Promise<void> {
    await this.client.quit();
  }
}
```

### 2.2. Part B: Cache-Aside Driver Profile Service

```typescript
// src/driver-service.ts
import { FastRideRedisCluster } from "./redis-cluster-client";

interface DriverProfile {
  id: number;
  name: string;
  rating: number;
  trips: number;
  available: boolean;
  zone: string;
}

// Simulated database (in-memory for demo)
const mockDatabase: Map<number, DriverProfile> = new Map();
for (let i = 1; i <= 100; i++) {
  mockDatabase.set(i, {
    id: i,
    name: `Driver ${i}`,
    rating: 3.5 + Math.random() * 1.5,
    trips: Math.floor(Math.random() * 5000),
    available: Math.random() > 0.3,
    zone: ["downtown", "suburb", "airport", "shopping_mall"][i % 4],
  });
}

const DEFAULT_TTL = 3600; // 1 hour
const JITTER = 0.1; // ±10%

function jitterTTL(ttl: number): number {
  const jitter = Math.floor(ttl * JITTER * Math.random());
  return ttl + jitter;
}

export class DriverService {
  constructor(private redis: FastRideRedisCluster) {}

  private cacheKey(driverId: number): string {
    return `driver:profile:${driverId}`;
  }

  async getProfile(driverId: number): Promise<DriverProfile | null> {
    const key = this.cacheKey(driverId);

    // Step 1: Try cache
    const cached = await this.redis.get(key);
    if (cached) {
      console.log(`[Cache HIT] driver:${driverId}`);
      return JSON.parse(cached);
    }

    // Step 2: Cache miss → read from DB
    console.log(`[Cache MISS] driver:${driverId} → DB`);
    const profile = mockDatabase.get(driverId);
    if (!profile) return null;

    // Step 3: Warm cache with jitter TTL
    await this.redis.set(key, JSON.stringify(profile), jitterTTL(DEFAULT_TTL));
    console.log(`[Cache WARMED] driver:${driverId}, TTL=${jitterTTL(DEFAULT_TTL)}s`);

    return profile;
  }

  async updateProfile(
    driverId: number,
    updates: Partial<DriverProfile>
  ): Promise<void> {
    // Step 1: Update DB
    const existing = mockDatabase.get(driverId);
    if (!existing) throw new Error(`Driver ${driverId} not found`);

    const updated = { ...existing, ...updates };
    mockDatabase.set(driverId, updated);
    console.log(`[DB UPDATED] driver:${driverId}`);

    // Step 2: Invalidate cache (event-driven invalidation simulation)
    await this.redis.del(this.cacheKey(driverId));
    console.log(`[CACHE INVALIDATED] driver:${driverId}`);
  }

  async getNearbyDrivers(zone: string): Promise<DriverProfile[]> {
    // Simulate geo query — in production would use Redis GEO commands
    const allDrivers = Array.from(mockDatabase.values());
    return allDrivers.filter((d) => d.zone === zone && d.available);
  }

  async rateLimit(driverId: number, limit: number, window: number): Promise<boolean> {
    const key = `ratelimit:driver:${driverId}:${window}`;
    const current = await this.redis.get(key);

    if (!current) {
      await this.redis.set(key, "1", window);
      return true;
    }

    if (parseInt(current, 10) >= limit) {
      return false; // Rate limited
    }

    // Increment (simplified — in production use Lua script)
    await this.redis.client.incr(key);
    return true;
  }
}
```

### 2.3. Part C: Rate Limiter Lua Script Integration

```typescript
// src/rate-limiter.ts
import { FastRideRedisCluster } from "./redis-cluster-client";

// Load Lua script as string
const RATE_LIMIT_SCRIPT = `
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current requests
local current = redis.call('ZCARD', key)

if current < limit then
    redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
    redis.call('EXPIRE', key, window + 1)
    return {1, limit - current - 1, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = math.ceil(tonumber(oldest[2]) + window - now)
    end
    return {0, 0, retry_after}
end
`;

export async function rateLimit(
  redis: FastRideRedisCluster,
  identifier: string,
  limit: number,
  windowSeconds: number
): Promise<{ allowed: boolean; remaining: number; retryAfter: number }> {
  const key = `ratelimit:api:${identifier}`;
  const now = Math.floor(Date.now() / 1000);

  const result = await (redis as any).client.eval(
    RATE_LIMIT_SCRIPT,
    1,
    key,
    windowSeconds,
    limit,
    now
  ) as [number, number, number];

  return {
    allowed: result[0] === 1,
    remaining: result[1],
    retryAfter: result[2],
  };
}
```

### 2.4. Part D: Generate Mermaid Architecture Diagram

```typescript
// src/generate-diagram.ts
import * as fs from "fs";

const ARCHITECTURE_MERMAID = `---
title: FastRide Production Redis Architecture
---

## Architecture Diagram

\`\`\`mermaid
graph TD
    subgraph Client_Layer
        RIDER[Rider App]
        DRIVER[Driver App]
        OPS[Ops Dashboard]
    end

    subgraph API_Gateway
        GW[API Gateway]
        RL[Rate Limiter<br/>Lua Script]
    end

    subgraph FastRide_Services
        DS[Driver Service]
        RS[Rider Service]
        MS[Matching Service]
    end

    subgraph Kafka_Cluster
        KB[Kafka Broker]
        IC[Invalidation Consumer]
    end

    subgraph Redis_Cluster
        subgraph Shard1["Shard 1 (Slots 0-5460)"]
            M1[M1<br/>:7000]
            R1[R1<br/>:7001]
        end
        subgraph Shard2["Shard 2 (Slots 5461-10922)"]
            M2[M2<br/>:7003]
            R2[R2<br/>:7004]
        end
        subgraph Shard3["Shard 3 (Slots 10923-16383)"]
            M3[M3<br/>:7006]
            R3[R3<br/>:7007]
        end
    end

    subgraph PostgreSQL
        PG[(PostgreSQL<br/>Primary)]
    end

    subgraph Monitoring
        PROM[Prometheus]
        GRAF[Grafana]
        EXP[Redis Exporter]
    end

    RIDER --> GW
    DRIVER --> GW
    OPS --> GW

    GW --> RL
    RL -->|Rate Check| DS
    RL -->|Rate Check| RS

    DS -->|GET/SET| M1
    DS -->|GEO| M2
    RS -->|GET/SET| M1
    RS -->|ZADD| M3
    MS -->|LOCK| M1
    MS -->|GEO| M2

    DS -->|Write + Event| KB
    RS -->|Write + Event| KB
    MS -->|Event| KB

    KB -->|Consume| IC
    IC -->|DELETE| M1
    IC -->|DELETE| M3

    DS -->|Primary Store| PG
    RS -->|Primary Store| PG
    MS -->|Primary Store| PG

    M1 -->|Replication| R1
    M2 -->|Replication| R2
    M3 -->|Replication| R3

    EXP -->|Metrics| PROM -->|Query| GRAF
\`\`\`

## Key Design

| Key Pattern | Type | TTL | Purpose |
|---|---|---|---|
| driver:profile:{id} | Hash | 24h | Driver profile cache |
| rider:profile:{id} | Hash | 12h | Rider profile cache |
| session:rider:{id}:{token} | String | 30d | Rider session |
| ratelimit:api:{id}:{win} | Sorted Set | 60s | Rate limit counter |
| geo:driver:zone:{zone} | Geo | 5m | Driver locations |
| lock:match:{zone} | String NX | 10s | Matching mutex |
| leaderboard:driver:rating | Sorted Set | None | Driver leaderboard |
| idempotency:{request_id} | String | 24h | Request deduplication |

## Capacity Summary

| Metric | Value |
|---|---|
| Peak ops/sec | 100,000 |
| Shard count | 3 (6 nodes total) |
| Memory per node | 256 MB (demo) / 16 GB (production) |
| Target p99 latency | < 50 ms |
| Cache hit rate target | > 85% |
| Replication | Async, < 1s lag |
| Failover time | < 30s (automatic) |

## Failure Mode Summary

| Failure | Impact | Mitigation |
|---|---|---|
| Single master down | 20s write unavailability | Auto-failover to replica |
| Cache stampede | DB overload on TTL expiry | TTL jitter + mutex |
| Hot slot | p99 spike on one shard | Key design review |
| OOM | Write failures | maxmemory + allkeys-lru |
| Cluster partition | Writes blocked | cluster-require-full-coverage=no |
`;

fs.writeFileSync("ARCHITECTURE.md", ARCHITECTURE_MERMAID);
console.log("[Diagram] ARCHITECTURE.md generated");
```

### 2.5. Run the Lab

```bash
# Run all parts
npx ts-node src/redis-cluster-client.ts &
npx ts-node src/driver-service.ts &
npx ts-node src/generate-diagram.ts

# Expected output for driver-service:
# [Cache MISS] driver:42 → DB
# [Cache WARMED] driver:42, TTL=3623s
# [Cache HIT] driver:42
# [DB UPDATED] driver:42
# [CACHE INVALIDATED] driver:42
```

### 2.6. Verification

```bash
# Verify cluster is healthy
redis-cli -p 7000 CLUSTER INFO | grep cluster_state

# Verify data distribution
echo "=== Key count per master ==="
for port in 7000 7003 7006; do
  echo "Port $port: $(redis-cli -p $port DBSIZE) keys"
done

# Verify replication
echo "=== Replication lag ==="
redis-cli -p 7000 INFO replication | grep master_link_status
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge 1: Write Full Architecture Document (Deliverable)

Write a complete architecture document for **"FastMart" — E-commerce Platform** (scenario khác FastRide để đa dạng).

**Requirements**:

```
Context:
  - Platform: E-commerce (products, orders, users, inventory)
  - Scale: 150K ops/sec peak, 5M SKUs, 2M users
  - DB: PostgreSQL (primary), MySQL (order history)
  - Kafka: order events, inventory updates
  - Redis: product catalog cache, session, rate limiting,
    inventory lock, recommendation cache, search index

Deliverables:
  1. Redis topology (standalone / Sentinel / Cluster)
     → Justify with numbers

  2. Data modeling (≥10 key patterns)
     → Format: key pattern | type | TTL | shard key
     → Include hash tags if needed

  3. Caching consistency strategy
     → Cache-aside vs write-through
     → Invalidation approach (event-driven vs TTL)

  4. Persistence config
     → AOF fsync policy + RDB schedule
     → Justify with durability requirements

  5. Capacity planning worksheet (numeric)
     → Memory estimate for 5M SKUs × 2KB avg
     → Shard count for 150K ops/sec
     → Headroom analysis

  6. Failure mode analysis (≥5 scenarios)
     → Format: failure | detection | impact | mitigation

  7. Monitoring requirements
     → Key metrics + SLO thresholds
     → Alert rules (≥5)

  8. Security checklist
     → Minimum 8 items

  Output format: write to FASTMART-ARCHITECTURE.md
```

### Challenge 2: Design Capacity Planning Sheet

Create a capacity planning worksheet for **FastFood Delivery** platform:

```
Context:
  - 200K daily orders
  - 50K active delivery partners
  - 500 restaurants
  - Peak: 15K ops/sec (lunch 12:00-13:00)
  - Read/write: 70/30

Tasks:
  A) Calculate memory requirements:
     - Session data: 1MB per user per day peak
     - Order cache: 5KB per order × 10K concurrent
     - Restaurant menu: 50KB per restaurant × 500
     - Delivery tracking: 2KB per active delivery × 5K

  B) Calculate shard count:
     - Single Redis: 30K ops/sec max
     - Target: 2× headroom
     - Read replica capacity

  C) Calculate replication backlog:
     - Write ops × avg payload × max lag seconds
     - Recommended backlog size

  D) Calculate network bandwidth:
     - ops/sec × bytes × replication factor
     - Per-shard bandwidth

  E) Produce final recommendation:
     - Node count, memory per node, shard count
     - Cost estimate (AWS r6g.xlarge: ~$0.3/hr)
     - Monthly cost
```

### Challenge 3: Failure Mode Analysis & Runbook

Choose 3 failure scenarios from the list below and write detailed runbooks:

**Options**:
- A) Master failover during peak traffic
- B) Cache stampede after promotional event
- C) OOM on one shard
- D) MOVED storm after resharding
- E) Kafka consumer lag causing stale inventory data

**For each selected scenario, write**:

```markdown
# Runbook: [Scenario Name]

## Impact Assessment
- User-visible impact:
- Duration estimate:
- SLA breach risk:

## Detection
- Alert name:
- Monitoring query:
- Manual check command:

## Immediate Response (0-5 min)
Step-by-step commands and their expected outputs

## Root Cause Analysis
- Likely causes:
- Investigation commands:

## Resolution
- Step-by-step fix
- Verification commands:

## Post-Incident
- Follow-up actions:
- Prevention:
```

---

## 4. Reflection Questions (Open-ended)

1. **Architecture Decision**: Bạn đang thiết kế Redis cho startup có 50K ops/sec hiện tại nhưng dự báo tăng 10× trong 12 tháng. Bạn bắt đầu với Sentinel (đơn giản) hay Cluster ngay từ đầu? Trình bày trade-off giữa "simplicity now" và "scale later". Khi nào bạn sẽ migrate từ Sentinel sang Cluster mà không có downtime?

2. **Redis vs PostgreSQL**: FastMart có inventory count cho sản phẩm. Mỗi khi có order, inventory giảm 1. Bạn dùng Redis INCR để decrement (fast, in-memory) hay PostgreSQL UPDATE (durable, consistent)? Điều gì xảy ra khi Redis crash giữa chừng? Làm thế nào để đảm bảo không bị oversell?

3. **Cost vs Reliability**: Team muốn giảm chi phí bằng cách bỏ replicas (1 master per shard, 0 replica). Phân tích: RTO và RPO nếu 1 master fail? Chi phí downtime tính bằng revenue loss? So sánh cost của replica vs cost của downtime?

4. **Key Design**: Bạn thiết kế key cho e-commerce cart: `cart:{user_id}:{item_id}`. Cart có thể chứa 100+ items. Mỗi item là Hash. Đánh giá: TTL nên set bao lâu? Memory của 1 cart hash với 100 items? Big key risk? Alternative design?

5. **Consistency vs Latency**: Matching service cho ride-hailing cần chọn driver gần nhất. Bạn đọc driver location từ Redis GEO. Nếu driver vừa di chuyển, location stale 2-5 giây. Điều này ảnh hưởng thế nào đến matching quality? Trade-off giữa consistency (read from master) và freshness (real-time location)? Bạn chấp nhận bao nhiêu staleness?

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 Cluster topology expected results**:
```
cluster_state:ok
cluster_slots_assigned:16384
Expected: 3 masters, 3 replicas
Slots per master: 16384 / 3 ≈ 5461 slots each
```

**1.2 Key distribution**:
```
With 1000 keys and 3 masters:
  Expected: ~330-350 keys per master (some variation normal)
  If one master has >500 keys: check for hash tag collision
  Key "driver:profile:1" → slot calculated from full key
  → No hash tag → slot based on "driver:profile:1"
```

**1.3 Cache-aside pattern**:
```
Pattern: Check cache → miss → read DB → write cache → return
Cache miss returns nil → application falls back to DB
Delete invalidates → next read causes cache miss → fresh data
```

**1.4 Distributed lock**:
```
SET key token NX EX 10 = atomic lock acquisition
If already held → returns nil
DEL after validation (in production: Lua script with token check)
```

---

### Lab Solutions

**2.1 Circuit breaker behavior**:
```
CLOSED → normal operation
OPEN → after 5 consecutive failures, all requests bypass Redis
HALF_OPEN → after 30s, allows 1 request to test recovery
→ If success: CLOSED. If fail: OPEN again.
```

**2.2 Cache-aside with TTL jitter**:
```
TTL = 3600 × (1 + random(0, 0.1)) = 3600-3960 seconds
Jitter prevents: all keys expiring at same timestamp → stampede
```

**2.3 Rate limiter Lua script**:
```
Sliding window = Sorted Set with timestamp as score
ZREMRANGEBYSCORE = remove entries older than window
ZCARD = count current entries in window
ZADD = add new request with unique member
EXPIRE = TTL = window + 1 (safety margin)
```

**2.4 Diagram generation**:
```
File: ARCHITECTURE.md
Content: Mermaid graph + key design table + capacity summary + failure mode table
This is the actual deliverable for the capstone.
```

---

### Challenge Solutions

**Challenge 1: FastMart Architecture (reference answer)**:

```
Topology: Redis Cluster 8 masters × 2 replicas = 24 nodes
  150K ops/sec / 30K per shard = 5 shards min
  × 2 headroom = 8 shards
  2 replicas per shard → 24 nodes total

Key patterns (partial):
  product:catalog:{sku_id}          Hash  24h    sku_id
  product:price:{sku_id}            String 1h    sku_id
  cart:{user_id}:items              Hash  7d     {user_id} (hash tag)
  session:user:{user_id}:{token}    String 30d   full key
  inventory:stock:{sku_id}           String 30s   sku_id (TTL short for freshness)
  inventory:lock:{sku_id}:{order}   String 10s   NX lock
  ratelimit:api:{user_id}:{window}  String 60s   full key
  recommendation:{user_id}          String 4h    user_id
  order:cache:{order_id}            Hash  2h     order_id
  search:index:{category}           Hash  1h     category

Caching: Cache-aside + Kafka event invalidation
  Write: UPDATE PostgreSQL → publish Kafka event
  Invalidation: Kafka consumer → DELETE Redis key
  Fallback: TTL = 2× expected invalidation latency

Persistence: AOF everysec + RDB 15min
  Reason: inventory is cache (can lose 1s)
  Not: AOF always (write latency too high)

Capacity:
  Memory: 5M SKUs × 2KB = 10 GB (products)
          2M users × 500B = 1 GB (sessions)
          200K orders × 5KB = 1 GB (orders)
          Total ≈ 12 GB × 1.5 (headroom) = 18 GB
  → 8 shards × 16 GB nodes = 128 GB total (plenty)
```

**Challenge 2: FastFood Capacity Planning**:

```
Part A — Memory:
  Sessions: 2M users × 1KB × 0.1 (active) = 200 MB
  Order cache: 10K × 5KB = 50 MB
  Restaurant menus: 500 × 50KB = 25 MB
  Delivery tracking: 5K × 2KB = 10 MB
  Total working set: ~285 MB
  × 5× growth = 1.4 GB
  × 1.5 fragmentation = 2.1 GB
  → Per shard: 2.1 GB / 6 shards = 350 MB (demo needs bigger)
  → Production: 6 shards × 8 GB nodes = 48 GB usable

Part B — Shard count:
  Target: 15K ops/sec × 2 = 30K ops/sec (headroom)
  Single Redis: 30K ops/sec max
  Min shards: ceil(30K / 30K) = 1
  With headroom: 6 shards
  Total capacity: 6 × 30K = 180K ops/sec

Part C — Replication backlog:
  Write ops: 15K × 0.3 = 4.5K writes/sec
  Avg payload: 500 bytes
  Max lag: 5 seconds
  Required backlog: 4.5K × 500 × 5 = 11.25 MB
  → Recommended: 64 MB (for bursts)

Part D — Bandwidth:
  Ops: 15K/sec × 500 bytes = 7.5 MB/s = 60 Mbps
  Per shard: 60 Mbps / 6 = 10 Mbps
  × 1.5 replication = 15 Mbps per shard
  → 100 Mbps NIC sufficient

Part E — Recommendation:
  Nodes: 6 masters + 6 replicas = 12 nodes
  Memory: 8 GB per node
  Cost: AWS r6g.xlarge × 12 = $0.3 × 12 × 730h = $2,628/month
```

**Challenge 3: Runbook Sample (Cache Stampede)**:

```markdown
# Runbook: Cache Stampede After Promotional Event

Impact: DB overload, p99 spike to 30s, possible cascade failure
Duration: Until cache warmed or event ended
SLA breach: Yes, p99 > SLA

Detection:
  Alert: RedisHitRateLow (hit rate < 70%)
  Monitor: spike in keyspace_misses_total
  Manual: redis-cli INFO stats | grep keyspace

Immediate Response:
  1. redis-cli -p <port> INFO stats | grep evicted
     → If > 1000/sec: immediate TTL reduction
  2. redis-cli CONFIG SET maxmemory-policy volatile-lru
  3. Identify which keys expired simultaneously:
     SCAN pattern "product:campaign:*"
  4. Emergency cache warming:
     Read key → SET with new TTL (non-blocking)
  5. Enable circuit breaker on DB connection pool
```

---

### Key Takeaways

1. **Architecture là tổng hợp**: Không có module riêng lẻ — topology, key design, persistence, monitoring, security phải align với nhau.
2. **Capacity planning = art + science**: Estimate rồi validate bằng actual benchmark. Numbers phải có backup (sao chép từ Day 10).
3. **Cache invalidation là hardest part**: TTL-only dễ nhưng có stale window. Event-driven tốt nhưng complex. Hybrid approach là best practice.
4. **Circuit breaker là bắt buộc**: Redis unavailability không nên cascade thành DB overload.
5. **Monitoring phải có action**: Alert mà không có runbook = noise. Mỗi alert cần response procedure.
6. **Document = liability**: Architecture document không maintain = outdated = misleading. Build review cycle vào process.
7. **Practice = mastery**: Đọc 29 ngày theory chưa đủ. Phải build, benchmark, break, và fix thật sự.
