# Day 24: Cluster Operations & Resharding — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript
**Redis**: 7.2+ với Cluster mode enabled

---

## 0. Setup

```bash
# Start 6-node Redis Cluster
docker compose -f docker-compose.cluster.yml up -d

# Wait for containers to be ready
sleep 15

# Create cluster: 3 masters + 3 replicas
# Chạy từ host để dùng mapped ports 7000-7005.
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1 \
  --cluster-yes

# Verify cluster is healthy
redis-cli -p 7000 CLUSTER INFO

# Verify all 16384 slots are covered
redis-cli -p 7000 CLUSTER NODES | grep master

# Expected output: cluster_state:ok, cluster_slots_assigned:16384
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Inspect Cluster Topology

```bash
# List all nodes in cluster
redis-cli -p 7000 CLUSTER NODES

# Get cluster info
redis-cli -p 7000 CLUSTER INFO

# Get slot information per node
redis-cli -p 7000 CLUSTER SLOTS

# Check which node owns slot 0, slot 5000, slot 10000
redis-cli -p 7000 CLUSTER KEYSLOT "user:1:profile"
redis-cli -p 7000 CLUSTER KEYSLOT "user:5000:profile"
redis-cli -p 7000 CLUSTER KEYSLOT "user:10000:profile"

# Questions:
# - Có bao nhiêu master nodes? Bao nhiêu replicas?
# - Mỗi master sở hữu bao nhiêu slots?
# - Slot ranges được phân bổ như thế nào?
```

### 1.2. Count Keys per Slot

```bash
# Insert test keys across different slots
for i in $(seq 1 100); do
  redis-cli -p 7000 SET "user:$i:profile" "value-$i"
done

# Count keys in different slots
# First find which slot a key belongs to
SLOT_1=$(redis-cli -p 7000 CLUSTER KEYSLOT "user:1:profile")
SLOT_50=$(redis-cli -p 7000 CLUSTER KEYSLOT "user:50:profile")
SLOT_100=$(redis-cli -p 7000 CLUSTER KEYSLOT "user:100:profile")

echo "Slot for user:1 = $SLOT_1"
echo "Slot for user:50 = $SLOT_50"
echo "Slot for user:100 = $SLOT_100"

# Count keys in each slot
redis-cli -p 7000 CLUSTER COUNTKEYSINSLOT $SLOT_1
redis-cli -p 7000 CLUSTER COUNTKEYSINSLOT $SLOT_50
redis-cli -p 7000 CLUSTER COUNTKEYSINSLOT $SLOT_100

# Get keys in a specific slot
redis-cli -p 7000 CLUSTER GETKEYSINSLOT $SLOT_1 10

# Questions:
# - Hash tag {} có ảnh hưởng đến slot assignment không?
# - Nếu dùng key pattern "user:{user_id}:profile", các keys cùng user_id có cùng slot không?
```

### 1.3. Test MOVED Redirect

```bash
# Get node info for slot 0
SLOT_1=$(redis-cli -p 7000 CLUSTER KEYSLOT "user:1:profile")
echo "Testing MOVED redirect for slot $SLOT_1"

# Connect to a random node and get a key
# Key belongs to slot $SLOT_1, which is on some node
redis-cli -p 7002 GET "user:1:profile"

# If MOVED: you should see "MOVED <slot> <ip:port>"
# If OK: you get the value directly (ioredis handles MOVED transparently)

# Try CLUSTER KEYSLOT on a node that doesn't own the slot
redis-cli -p 7002 CLUSTER KEYSLOT "user:1:profile"

# Check if MOVED response
# If MOVED: reconnect to correct node
```

### 1.4. Monitor Cluster State

```bash
# Monitor cluster state in real-time
watch -n 2 'redis-cli -p 7000 CLUSTER INFO'

# Check for any MIGRATING or IMPORTING slots
redis-cli -p 7000 CLUSTER NODES | grep -E "MIGRAT|IMPORT"

# Check replication status
for port in 7000 7001 7002; do
  echo "=== Port $port replication ==="
  redis-cli -p $port INFO replication | grep -E "role|master_link_status|master_repl_offset|connected_slaves"
done

# Check memory usage
for port in 7000 7001 7002; do
  echo "=== Port $port memory ==="
  redis-cli -p $port INFO memory | grep -E "used_memory_human|maxmemory_human"
done
```

### 1.5. Cleanup

```bash
# Clean up warm-up keys
redis-cli -p 7000 KEYS "user:*" | head -20
# Then delete
redis-cli -p 7000 FLUSHDB  # Only for test data!
```

---

## 2. Hands-on Lab (60-70 phút)

**Scenario**: E-commerce Redis Cluster 6 nodes (3 masters + 3 replicas), 100K keys. Add 7th node (master), reshard ~1700 slots, measure p99 latency during resharding, implement MOVED handling in TypeScript, then remove the node.

### 2.1. Project Setup

```bash
mkdir -p day24-cluster && cd day24-cluster
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
    "rootDir": "./src",
    "esModuleInterop": true
  },
  "include": ["src/**/*"]
}
```

### 2.2. Insert 100K Keys

```typescript
// src/seed-data.ts
import Redis from "ioredis";

const cluster = new Redis.Cluster([
  { host: "127.0.0.1", port: 7000 },
  { host: "127.0.0.1", port: 7001 },
  { host: "127.0.0.1", port: 7002 },
], {
  redisOptions: { maxRetriesPerRequest: 3 },
  slotsRefreshInterval: 60_000,
});

async function seedData(keyCount: number = 100_000): Promise<void> {
  console.log(`Seeding ${keyCount} keys...`);
  const pipelineBatch = 1000;
  let seeded = 0;

  for (let i = 0; i < keyCount; i += pipelineBatch) {
    const pipeline = cluster.pipeline();
    for (let j = 0; j < pipelineBatch && i + j < keyCount; j++) {
      const key = `product:${i + j}:detail`;
      const value = JSON.stringify({
        id: i + j,
        name: `Product ${i + j}`,
        price: Math.floor(Math.random() * 1_000_000),
        category: `cat_${(i + j) % 100}`,
      });
      pipeline.set(key, value);
    }

    await pipeline.exec();
    seeded += pipelineBatch;
    if (seeded % 10_000 === 0) {
      console.log(`  Seeded ${seeded}/${keyCount} keys`);
    }
  }

  // Cleanup
  await cluster.quit();
  console.log("Seeding complete!");
}

const count = parseInt(process.argv[2] || "100000", 10);
seedData(count).then(() => process.exit(0));
```

```bash
# Run seeder
npx ts-node src/seed-data.ts 100000

# Verify data
redis-cli -p 7000 DBSIZE
redis-cli -p 7001 DBSIZE
redis-cli -p 7002 DBSIZE
# Expected: total ~100K keys across 3 masters

# Verify slot distribution
redis-cli -p 7000 CLUSTER NODES | grep master | wc -l
```

### 2.3. Add 7th Node

```bash
# Start 7th Redis container (add to docker-compose.cluster.yml)
# For now, start manually
docker run -d --name redis-node-6 \
  -p 7006:7000 -p 17006:17000 \
  redis:7.2-alpine \
  redis-server --port 7000 \
  --cluster-enabled yes \
  --cluster-config-file nodes-7006.conf \
  --cluster-node-timeout 15000 \
  --appendonly yes \
  --maxmemory 256mb

# Wait for it to start
sleep 5

# Join cluster as master (no slots)
redis-cli --cluster add-node 127.0.0.1:7006 127.0.0.1:7000

# Verify: node joined but has 0 slots
redis-cli -p 7000 CLUSTER NODES | grep 7006

# Expected output: shows node-6 as master with no slots flags (no slots)
```

### 2.4. Implement Latency Monitor

```typescript
// src/cluster-client.ts
import Redis from "ioredis";

export const cluster = new Redis.Cluster([
  { host: "127.0.0.1", port: 7000 },
  { host: "127.0.0.1", port: 7001 },
  { host: "127.0.0.1", port: 7002 },
], {
  redisOptions: {
    maxRetriesPerRequest: 3,
    connectTimeout: 10_000,
  },
  slotsRefreshInterval: 60_000,
});
```

```typescript
// src/latency-monitor.ts
import { cluster } from "./cluster-client";

async function measureLatencyDuringReshard(
  durationMs: number = 60_000,
  sampleIntervalMs: number = 1000
): Promise<{ p50: number; p95: number; p99: number; errors: number }> {
  const measurements: number[] = [];
  let errorCount = 0;

  // Generate test keys
  const testKeys = Array.from(
    { length: 1000 },
    (_, i) => `product:${i * 100}:detail`
  );

  const endTime = Date.now() + durationMs;

  while (Date.now() < endTime) {
    const batch = testKeys.slice(0, 50);

    await Promise.all(
      batch.map(async (key) => {
        const start = Date.now();
        try {
          await cluster.get(key);
          measurements.push(Date.now() - start);
        } catch (err: any) {
          errorCount++;
          if (
            err.message.includes("MOVED") ||
            err.message.includes("ASK")
          ) {
            // Normal during migration — count as error but not crash
          } else {
            console.error(`Error for key ${key}: ${err.message}`);
          }
        }
      })
    );

    await new Promise((r) => setTimeout(r, sampleIntervalMs));
  }

  measurements.sort((a, b) => a - b);
  const n = measurements.length;
  return {
    p50: measurements[Math.floor(n * 0.5)] ?? 0,
    p95: measurements[Math.floor(n * 0.95)] ?? 0,
    p99: measurements[Math.floor(n * 0.99)] ?? 0,
    errors: errorCount,
  };
}

// Export for use in other files
export { measureLatencyDuringReshard };
```

### 2.5. Reshard và Measure

```typescript
// src/reshard-lab.ts
import { cluster } from "./cluster-client";
import { measureLatencyDuringReshard } from "./latency-monitor";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

async function getNodeId(port: number): Promise<string> {
  const { stdout } = await execAsync(
    `redis-cli -p ${port} CLUSTER NODES | grep myself`
  );
  return stdout.trim().split(" ")[0];
}

async function getSlotsForNode(port: number): Promise<number[]> {
  const { stdout } = await execAsync(
    `redis-cli -p ${port} CLUSTER NODES`
  );
  // Parse slot ranges from node line
  const lines = stdout.trim().split("\n");
  const nodeLine = lines.find(
    (l) => l.includes(`:7000@17000`) && l.includes("myself")
  );
  if (!nodeLine) throw new Error("Node not found");

  const parts = nodeLine.split(" ");
  // Slots are in format [slot1-start-slot1-end ...] or raw numbers
  const slots: number[] = [];
  for (const part of parts.slice(8)) {
    // Try to parse as number
    const num = parseInt(part.replace(/[\[\]]/g, ""), 10);
    if (!isNaN(num) && num >= 0 && num < 16384) {
      slots.push(num);
    }
  }
  return slots;
}

async function reshardWithMonitoring(
  sourcePort: number,
  targetPort: number,
  slotsToMove: number
): Promise<void> {
  console.log(`\n=== Starting Resharding ===`);
  console.log(`Source port: ${sourcePort}`);
  console.log(`Target port: ${targetPort}`);
  console.log(`Slots to move: ${slotsToMove}`);

  // Get node IDs
  const sourceId = await getNodeId(sourcePort);
  const targetId = await getNodeId(targetPort);
  console.log(`Source node ID: ${sourceId}`);
  console.log(`Target node ID: ${targetId}`);

  // Start latency monitoring in background
  console.log("Starting latency monitoring...");
  const latencyPromise = measureLatencyDuringReshard(120_000);

  // Run reshard
  console.log("Starting reshard...");
  const reshardCmd = [
    "redis-cli",
    "--cluster",
    "reshard",
    `127.0.0.1:${sourcePort}`,
    "--cluster-from",
    sourceId,
    "--cluster-to",
    targetId,
    "--cluster-slots",
    String(slotsToMove),
    "--cluster-yes",
  ].join(" ");

  try {
    await execAsync(reshardCmd, { timeout: 300_000 });
    console.log("Reshard completed!");
  } catch (err) {
    console.error("Reshard command error:", err);
  }

  // Get latency results
  console.log("\nWaiting for latency monitoring to complete...");
  const latencyResults = await latencyPromise;

  console.log("\n=== Latency During Resharding ===");
  console.log(`p50: ${latencyResults.p50}ms`);
  console.log(`p95: ${latencyResults.p95}ms`);
  console.log(`p99: ${latencyResults.p99}ms`);
  console.log(`Errors: ${latencyResults.errors}`);

  // Verify new slot distribution
  console.log("\n=== Post-Reshard Verification ===");
  await verifySlotDistribution();
}

async function verifySlotDistribution(): Promise<void> {
  console.log("Cluster nodes and slots:");

  for (const port of [7000, 7001, 7002, 7006]) {
    const slots = await getSlotsForNode(port);
    console.log(`  Port ${port}: ${slots.length} slots`);
  }
}

// Run if called directly
const sourcePort = parseInt(process.argv[2] || "7000", 10);
const targetPort = parseInt(process.argv[3] || "7006", 10);
const slots = parseInt(process.argv[4] || "546", 10);

reshardWithMonitoring(sourcePort, targetPort, slots)
  .then(() => {
    console.log("\nLab complete!");
    process.exit(0);
  })
  .catch((err) => {
    console.error("Error:", err);
    process.exit(1);
  });
```

### 2.6. Add Replica to New Node

```bash
# Add replica for new master (port 7006)
# Không dùng lại 7003 vì node đó đã là replica của cluster hiện tại.
docker run -d --name redis-node-7 \
  -p 7007:7000 -p 17007:17000 \
  redis:7.2-alpine \
  redis-server --port 7000 \
  --cluster-enabled yes \
  --cluster-config-file nodes-7007.conf \
  --cluster-node-timeout 15000 \
  --appendonly yes \
  --maxmemory 256mb

sleep 5

redis-cli --cluster add-node 127.0.0.1:7007 127.0.0.1:7000 \
  --cluster-slave \
  --cluster-master-id <node-6-id>

# Verify replica is attached to node-6
redis-cli -p 7000 CLUSTER NODES | grep 7007

# Check replication status
redis-cli -p 7007 INFO replication | grep master_link_status
```

### 2.7. Implement Client MOVED/ASK Handler

```typescript
// src/cluster-client.ts
// File này đã được tạo ở bước 2.4.
// Không tạo lại export vòng lặp kiểu `export { cluster } from "./cluster-client";`.
// Mục tiêu của bước này là thêm wrapper/demo để quan sát behavior khi có MOVED/ASK.
```

```typescript
// src/moved-handler.ts
// Manual MOVED/ASK handling — for learning purposes
// Note: ioredis handles MOVED automatically, this demonstrates the logic

import Redis from "ioredis";

interface SlotMap {
  [slot: number]: string; // slot -> node address
}

class ManualClusterClient {
  private nodes: Map<string, Redis> = new Map();
  private slotMap: SlotMap = {};
  public clusterClient: Redis.Cluster;

  constructor(port: number) {
    this.clusterClient = new Redis.Cluster(
      [{ host: "127.0.0.1", port }],
      {
        redisOptions: { maxRetriesPerRequest: 3 },
        clusterRetryStrategy: (times) => Math.min(times * 100, 3000),
      }
    );

    this.clusterClient.on("moved", (err) => {
      // ioredis auto-updates slot map, but log for monitoring
      console.log(`[MOVED] ${err.message}`);
    });

    this.clusterClient.on("asking", (err) => {
      console.log(`[ASKING] ${err.message}`);
    });

    this.clusterClient.on("error", (err) => {
      console.error(`[CLUSTER ERROR] ${err.message}`);
    });
  }

  async refreshSlotMap(): Promise<void> {
    // Force refresh cluster topology
    const slots = await this.clusterClient.cluster("slots");
    console.log(`Slot map refreshed: ${(slots as any[]).length} slot ranges`);
  }

  async get(key: string): Promise<string | null> {
    try {
      return await this.clusterClient.get(key);
    } catch (err: any) {
      // If ioredis auto-retry failed after MOVED handling, rethrow
      throw err;
    }
  }

  async close(): Promise<void> {
    await this.clusterClient.quit();
    for (const client of this.nodes.values()) {
      await client.quit();
    }
  }
}

// --- Demo: Track MOVED counts ---
async function demoMovedTracking(): Promise<void> {
  const client = new ManualClusterClient(7000);
  const MOVED_COUNT_KEY = "lab:moved-count";

  await client.clusterClient.set(MOVED_COUNT_KEY, "0");

  // Simulate 100 GET operations
  const keys = Array.from({ length: 100 }, (_, i) => `product:${i}:detail`);

  for (const key of keys) {
    try {
      await client.get(key);
    } catch {
      // Ignore errors for demo
    }
  }

  const count = await client.clusterClient.get(MOVED_COUNT_KEY);
  console.log(`Total MOVED redirects encountered: ${count}`);

  await client.close();
}
```

### 2.8. Remove Node

```bash
# Step 1: Rebalance — move slots from node-6 back to node-1
redis-cli --cluster rebalance 127.0.0.1:7000 \
  --cluster-weight 127.0.0.1:7006=0 \
  --cluster-yes

# Wait for rebalance to complete
sleep 10

# Step 2: Verify node-6 has 0 slots
redis-cli -p 7000 CLUSTER NODES | grep 7006

# Step 3: Delete replica first (if any)
# Find replica of node-6
redis-cli --cluster del-node 127.0.0.1:7000 <replica-node-id>

# Step 4: Delete master node
redis-cli --cluster del-node 127.0.0.1:7000 <node-6-id>

# Step 5: Verify cluster is healthy
redis-cli --cluster check 127.0.0.1:7000
```

### 2.9. Verification

```bash
# Verify cluster health
redis-cli -p 7000 CLUSTER INFO
# Expected: cluster_state:ok, cluster_slots_assigned:16384

# Verify all nodes connected
redis-cli -p 7000 CLUSTER NODES | grep -v disconnected | wc -l
# Expected: 6 nodes (3 masters + 3 replicas)

# Verify data integrity
redis-cli -p 7000 DBSIZE
redis-cli -p 7001 DBSIZE
redis-cli -p 7002 DBSIZE
# Total should be ~100K (some variation due to migration)

# Verify no stale keys (keys lost during migration)
TOTAL=$(for port in 7000 7001 7002; do redis-cli -p "$port" DBSIZE; done | awk '{sum+=$1}END{print sum}')
echo "Total keys across 3 masters: $TOTAL"
# Should be close to original 100K
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge 1: Simulate Shard Failure và Quan sát Replica Promote

**Setup**: 6-node cluster, 1 master (port 7000) + 1 replica (port 7003).

**Tasks**:

A) **Kill master and observe automatic failover**:
```bash
# Terminal 1: Monitor cluster
watch -n 1 'redis-cli -p 7000 CLUSTER INFO'

# Terminal 2: Kill master port 7000
docker kill redis-node-0

# Observe:
# - cluster_state changes from "ok" to "fail" temporarily
# - replica on port 7003 promotes to master
# - cluster_state returns to "ok"
```

B) **Measure failover time**:
```typescript
// src/failover-measure.ts
import Redis from "ioredis";

async function measureFailoverTime(): Promise<number> {
  const masterClient = new Redis({ host: "127.0.0.1", port: 7000 });
  const replicaClient = new Redis({ host: "127.0.0.1", port: 7003 });

  const start = Date.now();

  // Wait for replica to become master
  while (true) {
    const role = await replicaClient.info("replication");
    if (role.includes("role:master")) {
      return Date.now() - start;
    }
    await new Promise((r) => setTimeout(r, 100));
    if (Date.now() - start > 60000) throw new Error("Failover timeout");
  }
}

console.log(`Failover completed in ${await measureFailoverTime()}ms`);
```

C) **Bring original master back**:
```bash
# Restart original master
docker start redis-node-0

# Verify: original master rejoins as replica of new master
redis-cli -p 7003 INFO replication | grep connected_slaves

# Verify replication is re-established
redis-cli -p 7003 INFO replication | grep master_link_status
```

D) **Write operation runbook** for this scenario.

---

### Challenge 2: Design Operation Runbook cho Add-Node + Reshard Production

**Scenario**: Production Redis Cluster 1TB data, 10 masters + 10 replicas, 5M ops/sec.

**Tasks**:

A) **Risk Analysis**:
```
Write risk analysis for adding 2 new nodes to production cluster:
- Risk 1: Migration duration (estimate: keys/s, throughput)
- Risk 2: p99 latency spike during migration
- Risk 3: Client MOVED storm
- Risk 4: Data loss risk (network partition during migration)
- Risk 5: Operational complexity
```

B) **Operation Timeline**:
```
Design detailed operation timeline:
- Pre-checks (what to check, how long)
- Add nodes (how to add, what to verify)
- Rebalance (how many slots per batch, how to estimate duration)
- Post-checks (what metrics to verify)
- Rollback procedure
```

C) **Write complete runbook**:

```markdown
# Production Cluster Resharding Runbook

## Overview
- Cluster: 10 masters + 10 replicas, 1TB total data
- Operation: Add 2 new master nodes + reshard 5461 slots each
- Estimated duration: ?
- Risk level: HIGH

## Pre-checks (Day before)
- [ ] Backup: BGSAVE on all masters, verify RDB files
- [ ] Peak traffic hours: identify off-peak window
- [ ] Client MOVED handling: verify all clients handle MOVED correctly
- [ ] Memory headroom: ensure all nodes have >20% memory headroom
- [ ] Test in staging: run same resharding on staging cluster

## Pre-checks (Operation day)
- [ ] Notify stakeholders: operation window announced
- [ ] Verify backups: RDB files accessible
- [ ] Lock configuration: prevent automated resharding
- [ ] Cluster health: redis-cli --cluster check
- [ ] No migration in progress: CLUSTER NODES | grep MIGRAT

## Execution
- [ ] Add node 11 (master, empty)
- [ ] Verify node 11 joined cluster
- [ ] Add node 12 (master, empty)
- [ ] Verify node 12 joined cluster

- [ ] Reshard: move 5461 slots from node1 to node11
- [ ] Monitor: latency, MOVED count, replication lag
- [ ] If p99 > 100ms for > 5 min: PAUSE and investigate

- [ ] Reshard: move 5461 slots from node2 to node12
- [ ] Monitor: same metrics

## Post-checks
- [ ] redis-cli --cluster check: healthy
- [ ] All 16384 slots covered: verified
- [ ] No MIGRATING/IMPORTING: verified
- [ ] Replication lag = 0: verified
- [ ] Load test: p99 < SLA threshold

## Rollback
- [ ] If migration fails: rebalance back to original distribution
- [ ] If data integrity issue: restore from backup

## Sign-off
- [ ] Operations team sign-off
- [ ] Application team sign-off
- [ ] Post-incident review scheduled
```

---

### Challenge 3: Analyze MOVED Storm Risk

```typescript
// src/moved-storm-test.ts
// Simulate: 1000 clients, each with stale slot map, reshard happens

import Redis from "ioredis";

async function simulateMovedStorm(
  staleClientCount: number = 1000,
  requestsPerClient: number = 100
): Promise<{ totalErrors: number; stormDetected: boolean }> {
  // Create stale cluster clients (simulating outdated slot map)
  const staleClients = Array.from({ length: staleClientCount }, () =>
    new Redis({ host: "127.0.0.1", port: 7000, maxRetriesPerRequest: 1 })
  );

  let totalErrors = 0;
  const MOVED_THRESHOLD = staleClientCount * 10; // Storm if > 10× normal

  // Make requests (these will hit MOVED due to stale map)
  const startTime = Date.now();

  await Promise.all(
    staleClients.map(async (client) => {
      for (let i = 0; i < requestsPerClient; i++) {
        try {
          await client.get(`product:${i % 1000}:detail`);
        } catch (err: any) {
          totalErrors++;
        }
      }
    })
  );

  const duration = Date.now() - startTime;
  const stormDetected =
    totalErrors > MOVED_THRESHOLD &&
    duration < 10_000; // Many errors in short time

  await Promise.all(staleClients.map((c) => c.quit()));

  return { totalErrors, stormDetected };
}
```

---

## 4. Reflection Questions (Open-ended)

1. Bạn đang vận hành Redis Cluster production. Team muốn resharding trong maintenance window 4 tiếng. Trình bày trade-off giữa online resharding (zero downtime, rủi ro latency) vs maintenance window (downtime nhưng operation sạch hơn). Bạn chọn cách nào? Tại sao?

2. AWS ElastiCache cung cấp automatic resharding. Trade-off là gì khi dùng managed service cluster vs self-managed Redis Cluster? Khi nào nên dùng ElastiCache, khi nào nên self-manage?

3. Replica migration tự động trong Redis Cluster: `cluster-allow-replica-migration = yes` (default). Bạn nên keep default hay disable? Trình bày scenario cụ thể cho từng lựa chọn.

4. Hash tag `{}` cho phép multi-key operation nhưng có risk hot slot. Bạn thiết kế keyspace cho e-commerce. Products thuộc nhiều categories, users có shopping carts với nhiều products. Bạn dùng hash tag như thế nào để balance hot slot risk vs multi-key operation convenience?

5. `cluster-require-full-coverage` default là `yes`. Production của bạn có 99.9% uptime SLA. Bạn set `yes` hay `no`? Giải thích decision với scenario cụ thể.

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 Cluster topology**:
```
Expected: 3 masters + 3 replicas = 6 nodes
Each master: ~5461 slots (16384 / 3 = 5461.33, rounded)
```

**1.2 Key count per slot**:
```
Keys without hash tag {}: evenly distributed across slots
Keys with hash tag {user_id}: same slot for same user_id
Example: user:{100}:profile, user:{100}:cart, user:{100}:session → same slot
```

**1.3 MOVED redirect**:
```
When connected to wrong node: MOVED <slot> <ip:port>
ioredis auto-retries → you see value (not MOVED message)
Raw redis-cli shows MOVED: you must reconnect to correct node
```

---

### Lab Solutions

**2.4 Latency during resharding — expected results**:
```
Before reshard:  p50 ~1ms, p95 ~3ms, p99 ~5ms
During reshard: p50 ~2ms, p95 ~15ms, p99 ~50ms (target node busy)
After reshard:  p50 ~1ms, p95 ~3ms, p99 ~5ms (back to normal)

Error rate during reshard: should be < 1% (ASK/MOVED redirects)
If > 5%: check if MOVED storm happening
```

**2.5 Node removal — slot ownership check**:
```bash
# After rebalance, verify node-6 has 0 slots
redis-cli -p 7000 CLUSTER NODES | grep 7006
# Expected: node shows as master but no slot numbers in flags

# If slots still present, rebalance more
redis-cli --cluster rebalance 127.0.0.1:7000 \
  --cluster-weight 127.0.0.1:7006=0 \
  --cluster-yes
```

**2.6 Deleting node with slots**:
```
Error: "Node is not empty! Remove its slots first"
Fix: rebalance all slots away from the node before del-node
```

---

### Challenge Solutions

**Challenge 1: Failover time estimate**:
```
Expected failover time: 10-30 seconds
Steps:
  1. Master detection: cluster-node-timeout (15s default)
  2. Voting: few hundred ms
  3. Failover execution: ~1-2 seconds
  4. Gossip propagation: ~1 second

Total: ~17-20 seconds default
Can tune: cluster-node-timeout = 5s for faster failover (but more false positives)
```

**Challenge 2: Operation timeline estimation**:
```
1TB total, 5M ops/sec
Assume avg key size: 200 bytes
Keys per shard: 10 shards → 100GB per shard
Keys count: 1TB / 200B = 5 billion keys

Migration throughput: ~5K-10K keys/sec (single-threaded bottleneck)
Time to migrate 5461 slots (1/3 of cluster): ~500GB → ~2.5 billion keys
Duration: 2.5B keys / 5K keys/sec = 500,000 seconds ≈ 6 days ← TOO LONG

Solution: batch by chunking, migrate during off-peak
Actual production approach: add nodes, let natural key expiry + new writes
balance distribution over time, avoid forced reshard of entire slot ranges
```

**Challenge 3: MOVED storm detection**:
```typescript
// Storm detection: many MOVED in short time window
const STORM_WINDOW_MS = 5000;
const STORM_MOVED_THRESHOLD = 1000;

let movedCount = 0;
let windowStart = Date.now();

client.on("moved", () => {
  movedCount++;
  if (Date.now() - windowStart > STORM_WINDOW_MS) {
    movedCount = 0;
    windowStart = Date.now();
  }
  if (movedCount > STORM_MOVED_THRESHOLD) {
    console.error("MOVED STORM DETECTED!");
    // Mitigation: restart all clients in batches
  }
});
```

---

### Key Takeaways

1. **MOVED và ASK có semantic khác nhau**: MOVED = permanent redirect, ASK = temporary redirect during migration. Client phải handle cả hai, nhưng ioredis/go-redis đã handle auto.
2. **Resharding là online operation nhưng có cost**: p99 latency spike là normal, nhưng spike > 100ms sustained → có vấn đề.
3. **Luôn backup trước resharding**: BGSAVE on all masters, verify RDB files tồn tại.
4. **Slot stuck IMPORTING/MIGRATING**: xảy ra khi redis-cli bị interrupt. Fix = chạy `CLUSTER SETSLOT <slot> NODE <correct-node-id>` trên bất kỳ node nào.
5. **Replica migration**: default on, tự động balance replicas khi master removed. Có thể disable nếu muốn sticky replica.
6. **cluster-require-full-coverage = no**: recommended cho most production vì availability > perfect coverage.
7. **Monitor during migration**: MOVED/ASK count, latency p99, replication lag, IMPORTING/MIGRATING states.
