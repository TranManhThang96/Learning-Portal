# Day 22: Redis Cluster & Hash Slots — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript (ioredis Cluster)
**Redis**: 7.2+

---

## 0. Setup

```bash
# Create working directory
mkdir -p day22-cluster && cd day22-cluster

# Copy docker-compose from document.md (6-node cluster)
# See: document.md Section 3 for full docker-compose.cluster.yml

# Start all 6 containers
docker compose -f docker-compose.cluster.yml up -d

# Wait for all containers to be healthy
sleep 15

# Verify all containers running
docker compose -f docker-compose.cluster.yml ps
# Expected: 6 containers, all "Up"

# Initialize cluster
redis-cli --cluster create \
  127.0.0.1:7001 \
  127.0.0.1:7002 \
  127.0.0.1:7003 \
  127.0.0.1:7004 \
  127.0.0.1:7005 \
  127.0.0.1:7006 \
  --cluster-replicas 1

# Verify cluster is healthy
redis-cli -p 7001 CLUSTER INFO | grep cluster_state
# Expected: cluster_state:ok
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Observe Cluster State

```bash
# Check cluster info
redis-cli -p 7001 CLUSTER INFO

# Expected fields to observe:
# cluster_state: ok
# cluster_slots_assigned: 16384
# cluster_slots_ok: 16384
# cluster_known_nodes: 6
# cluster_current_epoch: 6
# cluster_my_epoch: 0
# cluster_stats_messages_received: ...
```

**Questions:**
- `cluster_slots_assigned` = bao nhiêu? Tại sao?
- `cluster_current_epoch` nghĩa là gì?

### 1.2. Inspect Nodes

```bash
# List all nodes
redis-cli -p 7001 CLUSTER NODES

# Expected format:
# <node-id> <ip:port> <flags> <master-id> <ping-sent> <pong-recv> <epoch> <slots> <protocol> <conn> <label>
#
# Flags: master (m), replica (r), myself (myself), fail (fail), handshake (handshake)

# Interpret the output:
# - How many masters? Replicas?
# - Which node is yourself (port 7001)?
# - What slots are assigned to each master?
```

### 1.3. Slot Distribution

```bash
# Get detailed slot ranges
redis-cli -p 7001 CLUSTER SLOTS

# Expected: 3 slot ranges (one per master)
# [[slot_start, slot_end, [node_ip:port, node_id]], ...]
# Should be approximately 5461, 5462, 5461 slots

# Check which node owns a specific slot
redis-cli -p 7001 CLUSTER SLOTS | head -20
```

### 1.4. Compute Hash Slots

```bash
# Compute slot for various keys
redis-cli -p 7001 CLUSTER KEYSLOT "user:123"
redis-cli -p 7001 CLUSTER KEYSLOT "user:456"
redis-cli -p 7001 CLUSTER KEYSLOT "session:abc"
redis-cli -p 7001 CLUSTER KEYSLOT "session:def"

# Compute with hash tag
redis-cli -p 7001 CLUSTER KEYSLOT "product:{electronics}:P-001"
redis-cli -p 7001 CLUSTER KEYSLOT "product:{electronics}:P-002"
redis-cli -p 7001 CLUSTER KEYSLOT "product:{books}:P-001"
redis-cli -p 7001 CLUSTER KEYSLOT "product:{books}:P-002"

# Expected: electronics keys → same slot, books keys → same slot (different from electronics)

# Observe:
# - Keys without hash tag → random distribution across slots
# - Keys with same hash tag → same slot
```

### 1.5. Cross-Slot Error (MGET)

```bash
# Insert a key in slot 0
redis-cli -p 7001 SET test:key:1 "value1"

# Insert another key (different slot)
redis-cli -p 7001 SET test:key:2 "value2"

# Get their slots
redis-cli -p 7001 CLUSTER KEYSLOT "test:key:1"
redis-cli -p 7001 CLUSTER KEYSLOT "test:key:2"

# Try MGET across different slots
redis-cli -p 7001 MGET test:key:1 test:key:2
# Expected: CROSSSLOT Keys in request don't hash to the same slot

# Check which node serves each key
redis-cli -p 7001 CLUSTER KEYSLOT "test:key:1"
# Use CLUSTER SLOTS output to find which node
```

### 1.6. Same-Slot MGET (with Hash Tag)

```bash
# Insert keys with same hash tag
redis-cli -p 7001 SET "items:{cat-a}:1" "item1"
redis-cli -p 7001 SET "items:{cat-a}:2" "item2"
redis-cli -p 7001 SET "items:{cat-a}:3" "item3"

# Verify same slot
redis-cli -p 7001 CLUSTER KEYSLOT "items:{cat-a}:1"
redis-cli -p 7001 CLUSTER KEYSLOT "items:{cat-a}:2"
redis-cli -p 7001 CLUSTER KEYSLOT "items:{cat-a}:3"

# MGET same slot → should work
redis-cli -p 7001 MGET "items:{cat-a}:1" "items:{cat-a}:2" "items:{cat-a}:3"
# Expected: ["item1", "item2", "item3"]
```

### 1.7. Cleanup

```bash
redis-cli -p 7001 FLUSHDB
# Note: FLUSHDB chỉ flush node hiện tại
# Trong cluster, cần flush trên tất cả nodes
for port in 7001 7002 7003 7004 7005 7006; do
  redis-cli -p $port FLUSHDB
done
```

---

## 2. Hands-on Lab: Cluster Operations & Hash Tag Patterns (60-70 phút)

### 2.1. Project Setup

```bash
mkdir -p day22-lab && cd day22-lab
npm init -y
npm install ioredis typescript ts-node @types/node
npx tsc --init
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "strict": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

### 2.2. Cluster Client Setup

```typescript
// src/cluster-client.ts
import Redis from "ioredis";

export const CLUSTER_NODES = [
  { host: "127.0.0.1", port: 7001 },
  { host: "127.0.0.1", port: 7002 },
  { host: "127.0.0.1", port: 7003 },
];

export const cluster = new Redis.Cluster(CLUSTER_NODES, {
  redisOptions: {
    maxRetriesPerRequest: 3,
    retryStrategy: (times) => Math.min(times * 100, 3000),
    connectTimeout: 10000,
  },
  slotRefreshInterval: 60_000,
  enableReadyCheck: true,
});

cluster.on("error", (err) => console.error("Cluster error:", err.message));
cluster.on("connect", () => console.log("Cluster connected"));
```

### 2.3. Lab A: Slot Distribution Analysis (20 phút)

**Task**: Insert 100,000 keys (random + with hash tag), measure slot distribution.

```typescript
// src/lab-a-slot-distribution.ts
import { cluster } from "./cluster-client";

async function analyzeSlotDistribution() {
  console.log("=== Slot Distribution Analysis ===\n");

  // ── Part 1: Random keys (no hash tag) ───────────────────────────────
  console.log("Part 1: Random keys (no hash tag)");
  const slotCounts: Map<number, number> = new Map();
  const SAMPLE_SIZE = 10_000;

  const pipeline = cluster.pipeline();
  for (let i = 0; i < SAMPLE_SIZE; i++) {
    const key = `random:item:${i}:${Math.random().toString(36)}`;
    pipeline.set(key, `value-${i}`);
    pipeline.cluster("keyslot", key);
  }

  const results = await pipeline.exec();
  if (!results) throw new Error("Pipeline failed");

  for (let i = 0; i < SAMPLE_SIZE; i++) {
    const slotResult = results[i * 2 + 1];
    if (slotResult && !slotResult[0] && typeof slotResult[1] === "number") {
      const slot = slotResult[1] as number;
      slotCounts.set(slot, (slotCounts.get(slot) || 0) + 1);
    }
  }

  const slots = Array.from(slotCounts.keys()).sort((a, b) => a - b);
  console.log(`  Keys sampled: ${SAMPLE_SIZE}`);
  console.log(`  Unique slots used: ${slots.length} / 16384`);
  console.log(`  Avg keys/slot: ${(SAMPLE_SIZE / slots.length).toFixed(1)}`);

  const counts = Array.from(slotCounts.values()).sort((a, b) => a - b);
  const min = counts[0] ?? 0;
  const max = counts[counts.length - 1] ?? 0;
  const avg = counts.reduce((a, b) => a + b, 0) / counts.length;
  console.log(`  Min keys/slot: ${min}, Max: ${max}, Avg: ${avg.toFixed(1)}`);
  console.log(`  Distribution ratio (max/min): ${(max / Math.max(min, 1)).toFixed(2)}x`);

  // ── Part 2: Hash tag keys (low cardinality = hot slot risk) ─────────
  console.log("\nPart 2: Hash tag with LOW cardinality (HOT SLOT risk)");
  const categories = ["electronics", "books", "clothing", "food", "sports"]; // only 5 categories

  const hotPipeline = cluster.pipeline();
  for (let i = 0; i < 1000; i++) {
    const cat = categories[i % categories.length];
    const key = `product:{${cat}}:item-${i}`;
    hotPipeline.set(key, `value-${i}`);
    hotPipeline.cluster("keyslot", key);
  }

  const hotResults = await hotPipeline.exec();
  if (!hotResults) throw new Error("Hot pipeline failed");

  const hotSlotCounts: Map<number, number> = new Map();
  for (let i = 0; i < 1000; i++) {
    const slotResult = hotResults[i * 2 + 1];
    if (slotResult && !slotResult[0] && typeof slotResult[1] === "number") {
      const slot = slotResult[1] as number;
      hotSlotCounts.set(slot, (hotSlotCounts.get(slot) || 0) + 1);
    }
  }

  console.log(`  Keys: 1000, Categories: 5`);
  console.log(`  Unique slots: ${hotSlotCounts.size} (expected: 5 = 1 per category)`);
  console.log(
    `  Keys per slot: ${Array.from(hotSlotCounts.values())
      .map((n) => n.toString())
      .join(", ")}`,
  );
  console.log("  ⚠️  Only 5 slots used! → Hot slot risk if one category dominates traffic");

  // ── Part 3: Hash tag keys (high cardinality) ─────────────────────────
  console.log("\nPart 3: Hash tag with HIGH cardinality (good distribution)");
  const tenantPipeline = cluster.pipeline();
  const tenantCount = 1000;

  for (let i = 0; i < 1000; i++) {
    const key = `session:{tenant-${i}}:profile`;
    tenantPipeline.set(key, `profile-${i}`);
    tenantPipeline.cluster("keyslot", key);
  }

  const tenantResults = await tenantPipeline.exec();
  if (!tenantResults) throw new Error("Tenant pipeline failed");

  const tenantSlotCounts: Map<number, number> = new Map();
  for (let i = 0; i < 1000; i++) {
    const slotResult = tenantResults[i * 2 + 1];
    if (slotResult && !slotResult[0] && typeof slotResult[1] === "number") {
      const slot = slotResult[1] as number;
      tenantSlotCounts.set(slot, (tenantSlotCounts.get(slot) || 0) + 1);
    }
  }

  console.log(`  Keys: 1000, Tenants: 1000 (1:1 mapping)`);
  console.log(`  Unique slots: ${tenantSlotCounts.size}`);
  // Note: with 1000 tenants, ~1000 unique slots (distribution depends on CRC16 hash)
  console.log("  ✅ Good distribution (each tenant → different slot)");
}

analyzeSlotDistribution()
  .then(() => {
    console.log("\n✅ Lab A done");
    process.exit(0);
  })
  .catch((err) => {
    console.error("❌ Error:", err);
    process.exit(1);
  });
```

### 2.4. Lab B: MOVED Redirection Handling (20 phút)

**Task**: Observe MOVED redirect, test cluster-aware vs naive client behavior.

```typescript
// src/lab-b-moved-redirect.ts
import Redis from "ioredis";
import { CLUSTER_NODES } from "./cluster-client";

async function testMovedRedirect() {
  console.log("=== MOVED Redirection Test ===\n");

  // ── Part 1: Find which node serves which slot ────────────────────────
  console.log("Part 1: Finding slot ownership");
  const slotsInfo: Map<number, string> = new Map();
  const sampleKeys = [
    "test:moved:a",
    "test:moved:b",
    "test:moved:c",
    "user:123",
    "session:abc",
    "product:xyz",
  ];

  // Use any node to get slot info
  const discoverCluster = new Redis({ host: "127.0.0.1", port: 7001 });
  const slotsResult = (await discoverCluster.cluster("slots")) as any[];
  console.log(`  Found ${slotsResult.length} slot ranges (${slotsResult.length} masters)`);

  for (const [start, end, nodeInfo] of slotsResult) {
    const [hostPort, nodeId] = nodeInfo as [string, string];
    console.log(`  Slots ${start}-${end} → ${hostPort} (${nodeId.slice(0, 8)})`);
  }

  // ── Part 2: Direct connection vs Cluster-aware ─────────────────────────
  console.log("\nPart 2: Cluster-aware vs direct connection");

  const testKey = "user:profile:thangtm";
  const testValue = JSON.stringify({ name: "Thang", role: "senior" });

  // Cluster-aware: works from any node
  const clusterClient = new Redis.Cluster(CLUSTER_NODES, {
    redisOptions: { maxRetriesPerRequest: 3 },
  });

  await clusterClient.set(testKey, testValue);
  const result = await clusterClient.get(testKey);
  console.log(`  Cluster-aware SET/GET: ${result === testValue ? "✅ OK" : "❌ FAIL"}`);

  // Direct connection: only works if connected to correct node
  // First, find which node owns the slot
  const slot = (await clusterClient.cluster("keyslot", testKey)) as number;
  console.log(`  Key "${testKey}" → slot ${slot}`);

  // Find which node owns this slot
  const slots = (await discoverCluster.cluster("slots")) as any[];
  let correctNode: string | null = null;
  for (const [start, end, nodeInfo] of slots) {
    if (slot >= start && slot <= end) {
      correctNode = (nodeInfo as string[])[0];
      break;
    }
  }

  // Try connecting to wrong node
  const wrongNode = correctNode?.includes("7001") ? 7002 : 7001;
  const directClient = new Redis({
    host: "127.0.0.1",
    port: wrongNode,
    maxRetriesPerRequest: 1,
  });

  const directResult = await directClient.get(testKey);
  if (directResult === null) {
    console.log(
      `  Direct connection to wrong node (port ${wrongNode}): ❌ Key not found (expected)`,
    );
  }

  // Cluster-aware client handles MOVED automatically
  console.log(`  Cluster-aware client: ✅ Transparent MOVED handling`);

  // ── Part 3: Pipelining across slots ──────────────────────────────────
  console.log("\nPart 3: Pipelining across multiple slots");

  const pipe = clusterClient.pipeline();
  const keys = Array.from({ length: 20 }, (_, i) => `product:${i}:info`);
  keys.forEach((key) => pipe.set(key, `data-${key}`));

  const pipeResults = await pipe.exec();
  console.log(
    `  Pipeline SET 20 keys: ${pipeResults?.filter((r) => !r[0]).length}/20 ✅`,
  );

  // ── Part 4: Scatter-gather MGET ───────────────────────────────────────
  console.log("\nPart 4: Cross-slot MGET (automatic scatter-gather)");

  const getPipe = clusterClient.pipeline();
  keys.forEach((key) => getPipe.get(key));
  const getResults = await getPipe.exec();
  const successCount = getResults?.filter((r) => !r[0] && r[1]).length ?? 0;
  console.log(
    `  MGET 20 keys across slots: ${successCount}/20 keys retrieved ✅`,
  );
  console.log(
    "  Note: ioredis automatically split by slot, pipeline to each node, merge",
  );

  await clusterClient.quit();
  await discoverCluster.quit();
  await directClient.quit();
}

testMovedRedirect()
  .then(() => {
    console.log("\n✅ Lab B done");
    process.exit(0);
  })
  .catch((err) => {
    console.error("❌ Error:", err);
    process.exit(1);
  });
```

### 2.5. Lab C: Hash Tag Session Pattern (20 phút)

**Task**: Implement session store với hash tag pattern, measure p95 latency.

```typescript
// src/lab-c-session-hash-tag.ts
import Redis from "ioredis";
import { cluster } from "./cluster-client";

interface SessionData {
  userId: string;
  tenantId: string;
  token: string;
  lastActive: number;
}

class ClusterSessionStore {
  // Pattern: session:{tenantId}:{userId}
  // Hash tag = {tenantId} → all session data for same tenant in same slot

  private cluster: Redis.Cluster;

  constructor(cluster: Redis.Cluster) {
    this.cluster = cluster;
  }

  private sessionKey(tenantId: string, userId: string): string {
    return `session:{${tenantId}}:${userId}`;
  }

  async setSession(
    tenantId: string,
    userId: string,
    data: SessionData,
    ttl: number,
  ): Promise<void> {
    const key = this.sessionKey(tenantId, userId);
    await this.cluster.setex(key, ttl, JSON.stringify(data));
  }

  async getSession(tenantId: string, userId: string): Promise<SessionData | null> {
    const key = this.sessionKey(tenantId, userId);
    const raw = await this.cluster.get(key);
    return raw ? JSON.parse(raw) : null;
  }

  async deleteSession(tenantId: string, userId: string): Promise<void> {
    const key = this.sessionKey(tenantId, userId);
    await this.cluster.del(key);
  }

  // Multi-key: get all sessions for same tenant (same slot ✅)
  async getMultipleSessions(
    tenantId: string,
    userIds: string[],
  ): Promise<(SessionData | null)[]> {
    const keys = userIds.map((uid) => this.sessionKey(tenantId, uid));
    const results = await this.cluster.mget(...keys);
    return results.map((r) => (r ? JSON.parse(r) : null));
  }
}

async function measureLatency(
  fn: () => Promise<void>,
  iterations: number,
): Promise<{ p50: number; p95: number; p99: number; avg: number }> {
  const latencies: number[] = [];

  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    await fn();
    const end = performance.now();
    latencies.push(end - start);
  }

  latencies.sort((a, b) => a - b);
  const sum = latencies.reduce((a, b) => a + b, 0);
  return {
    p50: latencies[Math.floor(iterations * 0.5)],
    p95: latencies[Math.floor(iterations * 0.95)],
    p99: latencies[Math.floor(iterations * 0.99)],
    avg: sum / iterations,
  };
}

async function sessionLab() {
  console.log("=== Session Store with Hash Tags ===\n");

  const store = new ClusterSessionStore(cluster);

  // ── Part 1: Write 1000 sessions ────────────────────────────────────────
  console.log("Part 1: Write 1000 sessions (10 tenants × 100 users)");
  const tenants = Array.from({ length: 10 }, (_, i) => `tenant-${i}`);
  const userCount = 100;

  const writeStart = performance.now();
  for (const tenant of tenants) {
    for (let u = 0; u < userCount; u++) {
      const userId = `user-${u}`;
      await store.setSession(tenant, userId, {
        userId,
        tenantId: tenant,
        token: `tok_${tenant}_${u}`,
        lastActive: Date.now(),
      }, 3600);
    }
  }
  const writeEnd = performance.now();
  console.log(
    `  Wrote ${tenants.length * userCount} sessions in ${(writeEnd - writeStart).toFixed(0)}ms`,
  );

  // ── Part 2: Verify hash tag — same tenant same slot ───────────────────
  console.log("\nPart 2: Verify hash tag → same tenant = same slot");
  const slotPipe = cluster.pipeline();
  for (const tenant of tenants.slice(0, 3)) {
    slotPipe.cluster("keyslot", `session:{${tenant}}:user-0`);
  }
  const slotResults = await slotPipe.exec();
  if (slotResults) {
    const slots = slotResults.map((r) => (r[1] as number) ?? -1);
    const allSame = slots.every((s) => s === slots[0]);
    console.log(
      `  Slots for 3 different tenants: ${slots.join(", ")}`,
    );
    console.log(
      `  Same tenant same slot: ${allSame ? "✅ Yes" : "❌ No (each tenant = different slot)"}`,
    );
  }

  // ── Part 3: Multi-tenant MGET (same tenant) ────────────────────────────
  console.log("\nPart 3: MGET sessions within same tenant (same slot)");
  const tenant = tenants[0];
  const userIds = Array.from({ length: 20 }, (_, i) => `user-${i}`);

  const multiGetStats = await measureLatency(async () => {
    await store.getMultipleSessions(tenant, userIds);
  }, 100);

  console.log(
    `  MGET 20 sessions × 100 iterations:`,
  );
  console.log(
    `    Avg: ${multiGetStats.avg.toFixed(2)}ms, P50: ${multiGetStats.p50.toFixed(2)}ms`,
  );
  console.log(
    `    P95: ${multiGetStats.p95.toFixed(2)}ms, P99: ${multiGetStats.p99.toFixed(2)}ms`,
  );

  // ── Part 4: Single key latency ───────────────────────────────────────
  console.log("\nPart 4: Single key GET latency (baseline)");
  const singleKeyStats = await measureLatency(async () => {
    await store.getSession(tenant, "user-0");
  }, 1000);

  console.log(
    `  Single GET × 1000 iterations:`,
  );
  console.log(
    `    Avg: ${singleKeyStats.avg.toFixed(2)}ms, P50: ${singleKeyStats.p50.toFixed(2)}ms`,
  );
  console.log(
    `    P95: ${singleKeyStats.p95.toFixed(2)}ms, P99: ${singleKeyStats.p99.toFixed(2)}ms`,
  );

  // ── Part 5: Simulate hot tenant ──────────────────────────────────────
  console.log("\nPart 5: Hot tenant simulation (1 tenant = 80% traffic)");
  // In production: 1 tenant dominates → 1 slot = 80% load
  // This test: measure latency of single-tenant high-throughput
  const hotTenantStats = await measureLatency(async () => {
    // 20 keys same slot (all same tenant)
    await store.getMultipleSessions(tenant, userIds);
  }, 500);

  console.log(
    `  Hot tenant MGET 20 keys × 500 iterations:`,
  );
  console.log(
    `    Avg: ${hotTenantStats.avg.toFixed(2)}ms, P95: ${hotTenantStats.p95.toFixed(2)}ms`,
  );
  console.log(
    "  ⚠️  In real scenario: this slot would be CPU bottleneck",
  );
  console.log(
    "  ⚠️  Recommendation: sub-shard with {tenant}:{shard}",
  );
}

sessionLab()
  .then(() => {
    console.log("\n✅ Lab C done");
    process.exit(0);
  })
  .catch((err) => {
    console.error("❌ Error:", err);
    process.exit(1);
  });
```

### 2.6. Running the Labs

```bash
# Run all labs sequentially
npx ts-node src/lab-a-slot-distribution.ts
npx ts-node src/lab-b-moved-redirect.ts
npx ts-node src/lab-c-session-hash-tag.ts
```

### 2.7. Expected Output

**Lab A: Slot Distribution**
```
Part 1: Random keys
  Keys sampled: 10000
  Unique slots used: ~9500 / 16384
  Avg keys/slot: 1.05
  Distribution ratio: ~2-3x (very even)

Part 2: Hash tag LOW cardinality (5 categories)
  Keys: 1000, Categories: 5
  Unique slots: 5 (1 per category)
  Keys per slot: 200, 200, 200, 200, 200
  ⚠️  Only 5 slots used! → Hot slot risk

Part 3: Hash tag HIGH cardinality (1000 tenants)
  Keys: 1000, Tenants: 1000
  Unique slots: ~1000
  ✅ Good distribution
```

**Lab B: MOVED Redirect**
```
Part 1: Finding slot ownership
  Found 3 slot ranges (3 masters)
  Slots 0-5460 → 127.0.0.1:7001
  Slots 5461-10922 → 127.0.0.1:7002
  ...

Part 4: Cross-slot MGET
  MGET 20 keys across slots: 20/20 keys retrieved ✅
```

**Lab C: Session Hash Tag**
```
Part 3: MGET 20 sessions × 100 iterations:
    Avg: 2.3ms, P50: 1.8ms, P95: 4.1ms, P99: 6.2ms
Part 4: Single GET × 1000 iterations:
    Avg: 0.8ms, P50: 0.6ms, P95: 1.2ms, P99: 1.8ms
```

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Design Keyspace cho Multi-Tenant SaaS — Hash Tag Strategy

**Scenario**: Bạn thiết kế Redis Cluster cho multi-tenant SaaS platform:
- **50,000 tenants**, mỗi tenant có **100-10,000 users**
- Operations cần: MGET sessions (same tenant), ZADD leaderboard (per tenant)
- **Hot tenant risk**: top 5% tenants = 80% traffic

**Tasks**:

A) **Analyze hot slot risk**: Nếu dùng `session:{tenant}:{user}`, 1 tenant hot nhất có thể chiếm bao nhiêu % traffic? Điều gì xảy ra với node serve slot đó?

B) **Design sub-sharding pattern**:
   - Key: `session:{tenant}:{shard}:{user}` với shard = `hash(user_id) % N_shards`
   - Tính: N_shards = ? để hot tenant distribution safe (max 1 slot = 10% traffic)
   - Đề xuất formula cụ thể

C) **Implement và benchmark**:
   ```typescript
   // 1. Current pattern (hot slot risk)
   // session:{tenant}:{user}

   // 2. Sub-sharded pattern (mitigate hot slot)
   // session:{tenant}:{shard-%d}:{user}
   // shard = Math.abs(hash(tenant + user_id)) % N_shards

   // 3. Benchmark: tạo 10 tenants (1 hot tenant = 50% writes)
   // Đo p95 latency của hot tenant với mỗi pattern
   ```

D) **Latency comparison table**:

   | Pattern | Keys/slot (hot tenant) | P95 Latency | Hot Slot Risk |
   |---|---|---|---|
   | No hash tag | ~1000/16384 | ? | Low |
   | `{tenant}` (no shard) | ~5000 (1 tenant) | ? | HIGH |
   | `{tenant}:{shard-%d}` | ? | ? | Low |

E) **Production recommendation**: Đưa ra key design spec (namespace, hash tag, TTL) cho multi-tenant SaaS production-ready.

### 3.2. Trace MGET Cross-Slot Failure

**Scenario**: Code production hiện tại dùng MGET để batch load products:

```typescript
// current code — PROBLEM
async function getProducts(productIds: string[]): Promise<(Product | null)[]> {
  const keys = productIds.map((id) => `product:${id}`);
  return redis.mget(...keys); // CROSSSLOT error in cluster!
}
```

**Tasks**:

A) **Tại sao MGET fail**? Dùng `redis-cli CLUSTER KEYSLOT` để verify 3 random product keys → chúng khác slot không?

B) **Fix Option 1 — Application-level scatter-gather**:
   ```typescript
   // Redis Cluster không cho MGET cross-slot.
   // Group keys theo slot/node, gửi GET/MGET song song, rồi merge theo thứ tự ban đầu.
   const clusterClient = new Redis.Cluster(nodes);
   const slots = await Promise.all(
     keys.map(async (key) => [key, await clusterClient.cluster("keyslot", key)] as const),
   );
   // Exercise: build Map<slot, keys[]> và pipeline từng group.
   ```
   Đo latency của approach này với 100 keys. So sánh với single-node MGET và cùng-slot MGET.

C) **Fix Option 2 — Pipeline per slot**:
   ```typescript
   // Manual: group keys by slot, pipeline per node
   // Ưu điểm: kiểm soát được network, có thể retry per-node
   // Nhược điểm: code phức tạp hơn
   ```

D) **Fix Option 3 — Hash tag với key grouping**:
   ```typescript
   // Nếu cần MGET cùng category products
   // Key: product:{category}:{id}
   // Hash tag: {category} → all products in category same slot
   // Trade-off: hot category = hot slot
   ```

E) **Đề xuất**: Chọn option nào cho 3 scenarios:
   - Scenario A: Product catalog, 10K products, 100K reads/day, no hot product
   - Scenario B: User sessions, 1M users, 500K reads/day, 1 hot tenant = 30% traffic
   - Scenario C: Real-time inventory, 100K items, 1M reads/day, need < 5ms P99

---

## 4. Reflection Questions (Open-ended)

1. **Cluster vs Sentinel khi nào**: Bạn có hệ thống 30GB data, 80K ops/sec. Khi nào chọn Sentinel, khi nào chọn Cluster? Có use case nào dùng cả hai không?

2. **Hash tag risk**: Bạn phát hiện 1 slot có 10× traffic hơn bình thường. Bạn sẽ debug như thế nào? Fix trong production mà không downtime?

3. **Cross-region cluster**: Redis Cluster có nên dùng cho multi-region deployment không? Tại sao gossip protocol không hoạt động tốt cross-region?

4. **Cluster bus security**: Cluster bus port (6379+10000) mở cho internet. Rủi ro gì? Làm sao secure cluster bus communication?

5. **Slot migration cost**: Khi resharding, ASK redirect gây latency spike như thế nào? Có cách nào giảm thiểu impact trong production?

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Challenge 3.1.A: Hot Slot Risk Calculation

```
Pattern: session:{tenant}:{user}
- 50,000 tenants, top 5% = 2,500 tenants
- Hot tenant: 10,000 users × average activity
- Assuming uniform distribution: 
  - 1 slot = 16384 slots / 50000 tenants ≈ 0.3 slots per tenant
  - Actually: 1 tenant → 1 hash → 1 slot
  - Top 5% tenants → 2,500 unique slots

But with 10,000 users per hot tenant:
  - All users session:{hot-tenant}:{user-0...user-9999}
  - All map to same slot (same hash tag)
  - This slot receives 100% of hot tenant's traffic

If hot tenant = 30% of total traffic:
  → 1 slot = 30% of cluster traffic
  → Other 2,499 hot slots = 50% traffic (distributed)
  → Remaining 47,500 tenants ≈ 1 slot each = 20% traffic
  → Max slot load: 30% vs average 0.006%
  → Ratio: 30% / 0.006% = 5000× hot slot
  → Node would CPU overload instantly

Solution: Sub-sharding
  session:{tenant}:{shard-%d}:{user}
  shard = hash(user_id) % N

  Target: no slot gets > 10% of tenant's traffic
  For hot tenant with 10,000 users:
    N = 10,000 / (0.1 × avg_users_per_slot) 
    We want max 1,000 users per slot: N = 10,000 / 1,000 = 10 shards
  Formula: N_shards = ceil(max_users_per_tenant / target_users_per_slot)
```

### Challenge 3.2: Cross-Slot MGET Fix

```
Fix Option 1: Application-level scatter-gather
  - Latency: max(RTT_node1, RTT_node2, RTT_node3) + ~0.5ms overhead
  - 100 keys across 3 nodes, 1ms RTT each → ~1.5ms total
  - vs single-node MGET: 1ms
  - Overhead: group keys + merge result; acceptable for most cache read use cases

Fix Option 2: Pipeline per slot
  - Same latency as Option 1, but more control
  - Can retry per-node independently
  - Recommended for critical paths

Fix Option 3: Hash tag per category
  - Only if products naturally group by category
  - Risk: hot category = hot slot
  - For product catalog: acceptable if no single category dominates

Recommendation by scenario:
  A: Option 1 (application-level scatter-gather) — simple, sufficient
  B: Option 1 + sub-sharding (same approach)
  C: Option 1 + dedicated hot-instance (bypass cluster for hot keys)
```

---

### Key Takeaways

1. **16384 slots**: Chọn vì gossip bandwidth manageable (2KB per node per PING), đủ fine-grained distribution, không phải vì technical constraint.

2. **Hash tag**: Chỉ dùng khi multi-key operation thực sự cần thiết và cardinality của tag cao (>100 unique values). Low cardinality tag = hot slot = incident.

3. **MOVED vs ASK**: MOVED = permanent redirect (update slot map), ASK = transient redirect (don't update slot map, send ASKING first).

4. **ioredis/go-redis ClusterClient**: Tự động handle MOVED và ASK. Với cross-slot read batch, vẫn phải hiểu client/proxy có tách request giúp không; cách portable là tự group by slot/node rồi pipeline song song.

5. **cluster-require-full-coverage no**: Luôn set = no để cluster vẫn operate được khi 1 shard down.

6. **Slot distribution test**: Luôn test hash tag pattern trong staging trước production — kiểm tra xem slots có đều không.
