# Day 20: Sentinel & High Availability — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript (ioredis Sentinel support)
**Redis**: 7.2+

---

## 0. Setup

```bash
# Copy docker-compose.sentinel.yml from document.md
# Or create it:
cat > docker-compose.sentinel.yml << 'EOF'
# (paste content from document.md section 3)
version: "3.8"
services:
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    ports: ["6379:6379"]
    command: redis-server --requirepass redis_secret_pass --appendonly yes --replica-read-only yes --min-replicas-to-write 2 --min-replicas-max-lag 10
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    ports: ["6380:6379"]
    command: redis-server --requirepass redis_secret_pass --masterauth redis_secret_pass --replicaof redis-master 6379 --replica-priority 100 --replica-read-only yes --appendonly yes
    depends_on: [redis-master]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    ports: ["6381:6379"]
    command: redis-server --requirepass redis_secret_pass --masterauth redis_secret_pass --replicaof redis-master 6379 --replica-priority 50 --replica-read-only yes --appendonly yes
    depends_on: [redis-master]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    ports: ["26379:26379"]
    command: redis-sentinel --port 26379 --sentinel monitor mymaster redis-master 6379 2 --sentinel down-after-milliseconds mymaster 5000 --sentinel failover-timeout mymaster 180000 --sentinel parallel-syncs mymaster 1 --sentinel auth-pass mymaster redis_secret_pass
    depends_on: [redis-master]
  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    ports: ["26380:26379"]
    command: redis-sentinel --port 26379 --sentinel monitor mymaster redis-master 6379 2 --sentinel down-after-milliseconds mymaster 5000 --sentinel failover-timeout mymaster 180000 --sentinel parallel-syncs mymaster 1 --sentinel auth-pass mymaster redis_secret_pass
    depends_on: [redis-master]
  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    ports: ["26381:26379"]
    command: redis-sentinel --port 26379 --sentinel monitor mymaster redis-master 6379 2 --sentinel down-after-milliseconds mymaster 5000 --sentinel failover-timeout mymaster 180000 --sentinel parallel-syncs mymaster 1 --sentinel auth-pass mymaster redis_secret_pass
    depends_on: [redis-master]
EOF

docker compose -f docker-compose.sentinel.yml up -d
docker compose -f docker-compose.sentinel.yml ps
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Verify Sentinel Quorum

```bash
# Check Sentinel quorum status
docker exec sentinel-1 redis-cli -p 26379 SENTINEL ckquorum mymaster
# Expected: mymaster: 3 usable Sentinels (quorum=2, 3/3 usable)

# If you see: "mymaster: 2 usable Sentinels" → one Sentinel is down
# If you see: "mymaster: NOQUORUM" → < 2 usable → no failover possible!

# List all masters (should show 1 master, online)
docker exec sentinel-1 redis-cli -p 26379 SENTINEL masters
```

**Question**: Tại sao output nói "3 usable Sentinels" nhưng quorum=2? Ý nghĩa của "3 usable" và "quorum=2"?

### 1.2. Get Master Address — Client Discovery

```bash
# Get current master address (this is what clients call via SENTINEL get-master-addr-by-name)
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
# Expected: ["127.0.0.1","6379"] or ["redis-master","6379"]

# Master detailed info
docker exec sentinel-1 redis-cli -p 26379 SENTINEL master mymaster
# Key fields:
#   flags: master,online
#   num-slaves: 2
#   num-other-sentinels: 2
#   quorum: 2
#   failover-state: none
```

### 1.3. List Replicas

```bash
# List all replicas of master
docker exec sentinel-1 redis-cli -p 26379 SENTINEL replicas mymaster

# Expected output (each replica shows):
#   ip: 172.x.x.x
#   port: 6379
#   flags: slave
#   priority: 100 (or 50)
#   link-status: connected

# Count replicas
docker exec sentinel-1 redis-cli -p 26379 SENTINEL replicas mymaster | grep -c "slave"
```

### 1.4. Check Replication Status

```bash
# On master: replication info
docker exec redis-master redis-cli -a redis_secret_pass INFO replication | grep -E "role|connected_slaves|master_link_status"

# Expected:
#   role:master
#   connected_slaves:2
#   master_link_status:up

# On replica-1: check it's replicating from master
docker exec redis-replica-1 redis-cli -a redis_secret_pass INFO replication | grep -E "role|master_host|master_link_status|slave_priority"

# Expected:
#   role:slave
#   master_host:redis-master
#   master_link_status:up
#   slave_priority:100
```

### 1.5. Simulate Manual Failover

```bash
# Trigger manual failover (useful for maintenance)
docker exec sentinel-1 redis-cli -p 26379 SENTINEL failover mymaster

# Watch what happens:
docker exec sentinel-1 redis-cli -p 26379 SENTINEL master mymaster
# After failover:
#   - flags may show "s_down,o_down,failover-in-progress"
#   - Then new master takes over

# Check after failover completes (wait ~15s)
sleep 15
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

**Note**: Sau manual failover, kiểm tra xem `redis-replica-1` (priority cao) được promote hay `redis-replica-2`. Replica với `replica-priority 100` sẽ được ưu tiên.

### 1.6. Verify Write Durability with min-replicas-to-write

```bash
# min-replicas-to-write=2: writes require 2 replicas acknowledged
# Write a key on master
docker exec redis-master redis-cli -a redis_secret_pass SET test:warmup "hello"

# Read from replica (should be replicated)
docker exec redis-replica-1 redis-cli -a redis_secret_pass GET test:warmup
# Expected: hello

# Now stop replica-1 to see min-replicas-to-write blocking
docker stop redis-replica-1

# Try to write (should fail or block)
docker exec redis-master redis-cli -a redis_secret_pass SET test:blocked "blocked"
# With min-replicas-to-write=2: ERROR (not enough replicas)

# Restore
docker start redis-replica-1
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

---

## 2. Hands-on Lab: Sentinel-Aware TypeScript Application (60-70 phút)

**Scenario**: Bạn viết một microservice quản lý user sessions với Redis Sentinel. Microservice phải:
- Kết nối qua Sentinel (không hardcoded IP)
- Subscribe `+switch-master` để tự động reconnect sau failover
- Đo failover time (kill master → measure time đến +switch-master event)
- Test write/read với session operations

### 2.1. Project Setup

```bash
mkdir -p day20-sentinel && cd day20-sentinel
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

```yaml
# docker-compose.yml (reference from warmup, use same compose file)
# Run: docker compose -f ../docker-compose.sentinel.yml up -d
```

### 2.2. Starter Code

```typescript
// src/config.ts
export const CONFIG = {
  sentinels: [
    { host: "localhost", port: 26379 },
    { host: "localhost", port: 26380 },
    { host: "localhost", port: 26381 },
  ],
  masterName: "mymaster",
  redisPassword: "redis_secret_pass",
  // Session settings
  sessionPrefix: "session:",
  sessionTtlMs: 30 * 24 * 60 * 60 * 1000, // 30 days
};
```

```typescript
// src/sentinel-client.ts
import Redis from "ioredis";

// ─── TODO 1: Create Sentinel-aware Redis client ──────────────────────────
// HINT: Use ioredis with sentinels option
// - sentinels: array of {host, port}
// - name: masterName (mymaster)
// - password: redisPassword
// - sentinelRetryStrategy: (times) => Math.min(times * 100, 3000)
// - sentinelOn: (sentinel: Redis) => { sentinel.subscribe('+switch-master') }
// - role: 'master'

export function createSentinelClient(): Redis {
  throw new Error("TODO: Create ioredis client with Sentinel support");
}

// ─── TODO 2: Monitor +switch-master event ────────────────────────────────
// HINT: ioredis fires 'sentinel' event when master changes
// Attach handler that logs:
//   - Old master info (if available)
//   - New master info (ioredis reconnects automatically)
//   - Time since last event

export function setupSentinelEvents(client: Redis): void {
  // Your code here: attach event handlers
  throw new Error("TODO: Setup sentinel event handlers");
}

// ─── TODO 3: Verify connection ─────────────────────────────────────────────
// HINT: Call client.ping() to verify connection works
export async function verifyConnection(client: Redis): Promise<void> {
  throw new Error("TODO: Verify Redis connection");
}
```

```typescript
// src/session-store.ts
import Redis from "ioredis";
import { CONFIG } from "./config";

// ─── TODO 4: Session CRUD operations ──────────────────────────────────────

export interface SessionData {
  userId: string;
  email: string;
  createdAt: number;
  lastActive: number;
}

// Set a session
// HINT: Use SET with PX for ms TTL
export async function setSession(
  client: Redis,
  sessionId: string,
  data: SessionData
): Promise<void> {
  throw new Error("TODO: Implement setSession");
}

// Get a session
// HINT: GET + JSON.parse
export async function getSession(
  client: Redis,
  sessionId: string
): Promise<SessionData | null> {
  throw new Error("TODO: Implement getSession");
}

// Update lastActive timestamp
// HINT: GET + JSON.parse + JSON.stringify + SET
export async function touchSession(
  client: Redis,
  sessionId: string
): Promise<void> {
  throw new Error("TODO: Implement touchSession");
}
```

```typescript
// src/failover-tester.ts
import Redis from "ioredis";

// ─── TODO 5: Measure failover time ───────────────────────────────────────
// This script simulates:
//   1. Write data to Redis
//   2. Kill master container
//   3. Wait for +switch-master event
//   4. Write data to new master
//   5. Report failover time

export async function measureFailoverTime(
  client: Redis,
  masterContainerName: string = "redis-master"
): Promise<number> {
  // HINT 1: Record start time (Date.now())
  // HINT 2: Attach one-time 'sentinel' event handler for +switch-master
  //         (use once() pattern — remove handler after first call)
  // HINT 3: Spawn shell to kill master: docker stop redis-master
  // HINT 4: Wait for 'sentinel' event → record end time
  // HINT 5: Failover time = end - start (ms)
  // HINT 6: Log the failover time
  throw new Error("TODO: Implement measureFailoverTime");
}

// ─── TODO 6: Verify data integrity after failover ──────────────────────────
// HINT: After failover, write test key and verify it's on new master
// Check redis-cli INFO replication on new master
export async function verifyDataIntegrity(
  client: Redis,
  testKey: string = "failover:test"
): Promise<{ passed: boolean; newMaster: string }> {
  throw new Error("TODO: Implement verifyDataIntegrity");
}
```

```typescript
// src/index.ts
import { createSentinelClient, setupSentinelEvents, verifyConnection } from "./sentinel-client";
import { setSession, getSession, touchSession } from "./session-store";
import { measureFailoverTime, verifyDataIntegrity } from "./failover-tester";
import { CONFIG } from "./config";

async function main() {
  console.log("=== Redis Sentinel Client Demo ===\n");

  // Step 1: Create client
  const client = createSentinelClient();
  console.log("[1/5] Client created");

  // Step 2: Setup sentinel events
  setupSentinelEvents(client);
  console.log("[2/5] Sentinel events attached");

  // Step 3: Verify connection
  await verifyConnection(client);
  console.log("[3/5] Connection verified");

  // Step 4: Session CRUD demo
  const testSessionId = "sess_" + Date.now();
  const testSession = {
    userId: "user_001",
    email: "demo@example.com",
    createdAt: Date.now(),
    lastActive: Date.now(),
  };

  await setSession(client, testSessionId, testSession);
  console.log(`[4/5] Session created: ${testSessionId}`);

  const retrieved = await getSession(client, testSessionId);
  if (retrieved && retrieved.userId === testSession.userId) {
    console.log("[4/5] Session retrieved OK:", retrieved.email);
  } else {
    console.error("[4/5] Session mismatch!");
  }

  // Step 5: Failover test (comment out if you don't want to kill master)
  if (process.argv.includes("--test-failover")) {
    console.log("\n[5/5] Starting failover test (killing master in 3s)...");
    await new Promise((r) => setTimeout(r, 3000));

    const failoverTime = await measureFailoverTime(client);
    console.log(`[5/5] FAILOVER TIME: ${failoverTime}ms`);

    const integrity = await verifyDataIntegrity(client);
    console.log(`[5/5] Data integrity: ${integrity.passed ? "PASSED" : "FAILED"}`);
    console.log(`     New master: ${integrity.newMaster}`);
  }

  console.log("\nDone. Press Ctrl+C to exit.");
}

main().catch(console.error);
```

### 2.3. Running the Lab

**Terminal 1 — Setup & Demo**:
```bash
cd day20-sentinel
# Make sure Sentinel is running
docker compose -f ../docker-compose.sentinel.yml up -d
sleep 10

# Run demo (without failover test)
npx ts-node src/index.ts
```

**Terminal 1 — Failover Test** (optional, after basic demo):
```bash
npx ts-node src/index.ts --test-failover
```

### 2.4. Expected Output

**Basic demo (without --test-failover)**:
```
=== Redis Sentinel Client Demo ===

[1/5] Client created
Connecting to Sentinel at localhost:26379...
[2/5] Sentinel events attached
[Sentinel] Subscribed to +switch-master
[3/5] Connection verified
[4/5] Session created: sess_1700000000000
[4/5] Session retrieved OK: demo@example.com
[5/5] Skipped (use --test-failover to enable)

Done. Press Ctrl+C to exit.
```

**Failover test (--test-failover)**:
```
[5/5] Starting failover test (killing master in 3s)...
[Sentinel] +switch-master event received!
[Sentinel] Master changed to redis-replica-1
[5/5] FAILOVER TIME: 18432ms
[5/5] Data integrity: PASSED
     New master: redis-replica-1
```

### 2.5. Verification

```bash
# After failover: check new master
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
# Should show: redis-replica-1's IP (not redis-master)

# Check replica configuration
docker exec redis-master redis-cli -a redis_secret_pass INFO replication | grep role
# Should show: role:slave (old master is now replica)

# Restart old master to restore original topology
docker start redis-master
sleep 10
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Design Multi-AZ Sentinel Topology

**Scenario**: Thiết kế Sentinel infrastructure cho hệ thống e-commerce với yêu cầu:
- 3 availability zones: us-east-1a, us-east-1b, us-west-2a
- Redis master ở us-east-1a, replicas ở us-east-1b và us-west-2a
- SLA: 99.9% uptime, failover < 30s
- Write ops: 50K/sec peak

**Tasks**:

A) **Sentinel placement**: Đặt Sentinel ở đâu? Bao nhiêu nodes?
   - Cần đảm bảo: 1 Sentinel cùng AZ với master
   - Cần đảm bảo: majority AZ không bị single point of failure
   - Cần đảm bảo: network latency giữa Sentinels < 50ms

B) **Quorum calculation**:
   - Nếu 1 AZ (us-east-1a) bị partition: quorum đủ chưa? Failover xảy ra?
   - Nếu 2 AZs (us-east-1a + us-east-1b) bị partition: quorum đủ?
   - Đề xuất quorum tối ưu

C) **Configuration parameters**:
   - down-after-milliseconds = ? (justify)
   - min-replicas-to-write = ? (justify)
   - parallel-syncs = ? (justify)
   - replica-priority trên từng replica?

D) **Split-brain risk analysis**:
   - Scenario: us-east-1a bị partition khỏi internet (không phải internal network)
   - us-east-1b + us-west-2a: Sentinels ở 2 AZ này có quorum?
   - us-east-1a: master + Sentinel ở AZ này → phản ứng gì?
   - Writes ở us-east-1a: có bị blocked không?
   - Mitigation nào để giảm split-brain risk?

### 3.2. Failover Runbook Design

Viết failover runbook cho incident sau:

```
Incident: SENTINEL ckquorum mymaster trả về "NOQUORUM"
- sentinel-1: DOWN
- sentinel-2: ONLINE
- sentinel-3: ONLINE
- master: UNKNOWN
- Replicas: UNKNOWN
```

**Questions**:
1. Bước đầu tiên là gì? Tại sao không restart master ngay?
2. Làm thế nào để xác định master còn sống hay không?
3. Nếu sentinel-1 crashed: restore hay tiếp tục với 2 Sentinels?
4. Emergency khi chỉ còn 2 Sentinels: khi nào nên restore Sentinel trước, khi nào cần manual failover có kiểm soát?
5. Khi nào cần manual failover thay vì đợi Sentinel auto-failover?

### 3.3. Split-Brain Analysis

Giải thích và phân tích:

```
Configuration:
  - 3 Sentinels, quorum = 1
  - Network topology: 3 different VMs in same datacenter
  - min-replicas-to-write = 0

Scenario: "Split-horizon" — us-west-2a network switch bị lỗi,
tách us-west-2a khỏi us-east-1a và us-east-1b

Zone A (majority, 2 Sentinels): Sentinel-1(us-east-1a), Sentinel-2(us-east-1b)
  - Master reachable
  - Writes accepted

Zone B (minority, 1 Sentinel): Sentinel-3(us-west-2a)
  - Master NOT reachable (network partition)
  - Sentinel-3 có thể mark ODOWN nếu quorum=1, nhưng không lấy được majority authorization một mình
  - Không được assume Sentinel-3 tự promote replica; split-brain write thường đến từ old master còn accept writes ở partition khác

Questions:
1. Điều gì xảy ra với writes ở Zone A và Zone B?
2. min-replicas-to-write = 0 ảnh hưởng gì?
3. Khi network hồi phục, làm thế nào để reconcile data?
4. Quorum đúng để giảm false ODOWN trong scenario này?
5. Redis server `min-replicas-to-write` phải đặt thế nào để old master bị cô lập không accept writes?
```

---

## 4. Reflection Questions (Open-ended)

1. Bạn đang design Redis infrastructure cho một payment gateway. Data loss = financial loss. Bạn chọn Sentinel với `min-replicas-to-write=2` hay dùng Redis Cluster? Tại sao? Cần thêm gì ngoài Redis để đảm bảo durability?

2. Team của bạn có 3 engineers. Ops capacity hạn chế. Hệ thống có 20K ops/sec, memory 16GB. Bạn chọn Sentinel hay Cluster? Lập luận với số liệu cụ thể.

3. Khi nào bạn chấp nhận data loss khi failover xảy ra? Trong scenario nào thì data loss là acceptable? Trong scenario nào thì không bao giờ được chấp nhận? Lấy ví dụ từ e-commerce và financial system.

4. Automatic failover có luôn luôn tốt hơn manual failover không? Khi nào bạn muốn vô hiệu hóa automatic failover và trigger manual thay thế? (Gợi ý: rolling deployment, major version upgrade, schema migration.)

5. Bạn phát hiện ra rằng replica lag trong production thường xuyên đạt 15-20 giây vào peak hours. `min-replicas-max-lag` đang đặt = 10. Điều gì sẽ xảy ra với writes? Bạn sẽ làm gì?

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 Quorum output**:
```
"3 usable Sentinels" = 3 Sentinels đang online và respond
"quorum=2" = cần 2 Sentinels đồng ý SDOWN để declare ODOWN
→ 3 usable > quorum=2 → failover CAN happen
→ Nếu 1 Sentinel down → 2 usable → quorum=2 → still OK
→ Nếu 2 Sentinels down → 1 usable → NOQUORUM → no failover possible
```

**1.5 Manual failover**:
```
redis-cli -p 26379 SENTINEL failover mymaster
→ Một Sentinel lấy majority authorization trong current epoch và thực hiện failover
→ Promotes replica có highest priority (replica-priority=100)
→ redis-replica-1 được promote (priority=100 > priority=50)
```

---

### Lab Solutions

**TODO 1: createSentinelClient**
```typescript
import Redis from "ioredis";
import { CONFIG } from "./config";

export function createSentinelClient(): Redis {
  const client = new Redis({
    sentinels: CONFIG.sentinels,
    name: CONFIG.masterName,
    password: CONFIG.redisPassword,
    role: "master",
    sentinelRetryStrategy: (times: number) => {
      console.log(`[Sentinel] Retry attempt ${times}`);
      return Math.min(times * 100, 3000);
    },
    retryStrategy: (times: number) => {
      console.log(`[Redis] Retry attempt ${times}`);
      return Math.min(times * 200, 5000);
    },
    maxRetriesPerRequest: 3,
    enableReadyCheck: true,
    lazyConnect: false,
  });
  return client;
}
```

**TODO 2: setupSentinelEvents**
```typescript
import Redis from "ioredis";

export function setupSentinelEvents(client: Redis): void {
  client.on("sentinel", (err: Error | null) => {
    if (err) {
      console.error("[Sentinel] Sentinel error:", err.message);
      return;
    }
    // ioredis auto-reconnects after +switch-master
    console.log("[Sentinel] +switch-master event received — ioredis reconnecting...");
  });

  client.on("error", (err) => {
    console.error("[Sentinel] Redis error:", err.message);
  });

  client.on("close", () => {
    console.warn("[Sentinel] Connection closed");
  });

  client.on("reconnecting", () => {
    console.log("[Sentinel] Reconnecting...");
  });

  client.on("ready", () => {
    console.log("[Sentinel] Client ready");
  });

  // Subscribe to additional channels if needed
  const sentinelConn = new Redis({
    host: "localhost",
    port: 26379,
  });
  sentinelConn.subscribe(
    "+switch-master",
    "+odown",
    "-odown",
    "+sdown",
    "+failover-state-retry",
    "+min-slave-replica-limit",
    (err) => {
      if (err) console.error("[Sentinel] Subscribe error:", err.message);
    }
  );
  sentinelConn.on("message", (channel, message) => {
    const ts = new Date().toISOString();
    console.log(`[${ts}] [Sentinel Pub/Sub] ${channel}: ${message}`);
  });
}
```

**TODO 3: verifyConnection**
```typescript
import Redis from "ioredis";

export async function verifyConnection(client: Redis): Promise<void> {
  try {
    const pong = await client.ping();
    if (pong !== "PONG") throw new Error(`Unexpected PING response: ${pong}`);
    console.log("[Sentinel] PING/PONG OK");
  } catch (err) {
    console.error("[Sentinel] Connection verification failed:", err);
    throw err;
  }
}
```

**TODO 4: Session operations**
```typescript
import Redis from "ioredis";
import { CONFIG } from "./config";

export async function setSession(
  client: Redis,
  sessionId: string,
  data: SessionData
): Promise<void> {
  const key = `${CONFIG.sessionPrefix}${sessionId}`;
  const payload = JSON.stringify(data);
  await client.set(key, payload, "PX", CONFIG.sessionTtlMs);
}

export async function getSession(
  client: Redis,
  sessionId: string
): Promise<SessionData | null> {
  const key = `${CONFIG.sessionPrefix}${sessionId}`;
  const raw = await client.get(key);
  if (!raw) return null;
  return JSON.parse(raw) as SessionData;
}

export async function touchSession(
  client: Redis,
  sessionId: string
): Promise<void> {
  const existing = await getSession(client, sessionId);
  if (!existing) throw new Error(`Session ${sessionId} not found`);
  existing.lastActive = Date.now();
  await setSession(client, sessionId, existing);
}
```

**TODO 5: measureFailoverTime**
```typescript
import Redis from "ioredis";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export async function measureFailoverTime(
  client: Redis,
  masterContainerName: string = "redis-master"
): Promise<number> {
  return new Promise((resolve, reject) => {
    const start = Date.now();

    // One-time handler for sentinel event (auto-removes after first call)
    const handler = () => {
      const elapsed = Date.now() - start;
      client.removeListener("sentinel", handler);
      resolve(elapsed);
    };

    client.on("sentinel", handler);

    // Kill master after short delay (allow handler to register)
    setTimeout(async () => {
      try {
        console.log(`[Test] Killing ${masterContainerName}...`);
        await execAsync(`docker stop ${masterContainerName}`);
        console.log("[Test] Master killed, waiting for failover...");
      } catch (err) {
        reject(err);
      }
    }, 1000);
  });
}
```

**TODO 6: verifyDataIntegrity**
```typescript
import Redis from "ioredis";

export async function verifyDataIntegrity(
  client: Redis,
  testKey: string = "failover:test"
): Promise<{ passed: boolean; newMaster: string }> {
  // Write test key
  await client.set(testKey, Date.now().toString());

  // Verify it's readable (proves we have a working master)
  const value = await client.get(testKey);
  const passed = value !== null;

  // Get master address
  const sentinel = new Redis({ host: "localhost", port: 26379 });
  const [ip, port] = await sentinel.sentinel("get-master-addr-by-name", "mymaster") as [string, string];
  await sentinel.quit();

  return { passed, newMaster: `${ip}:${port}` };
}
```

---

### Challenge Solutions

**3.1.B Quorum Calculation**:

```
Recommended: 5 Sentinels (spread: 2+2+1)
  - AZ us-east-1a: Sentinel-1 + Sentinel-2
  - AZ us-east-1b: Sentinel-3 + Sentinel-4
  - AZ us-west-2a: Sentinel-5
  - Quorum: 3 (majority of 5)

Analysis:
  us-east-1a partition (2 Sentinels down):
    → 3 remaining (us-east-1b: 2, us-west-2a: 1) = quorum=3
    → Failover STILL POSSIBLE ✓

  us-east-1a + us-east-1b partition (4 Sentinels down):
    → 1 remaining (us-west-2a: 1) = NOQUORUM
    → No failover → system unavailable → ACCEPTABLE (cross-region disaster)

us-east-1a + us-west-2a partition (3 Sentinels down):
    → 2 remaining (us-east-1b: 2) = NOQUORUM
    → No failover → system unavailable → ACCEPTABLE

Conclusion: 5 Sentinels spread 2-2-1 across AZs = optimal balance
```

**3.2.A Emergency runbook steps**:

```
Step 1: KHÔNG restart master ngay
  - Lý do: nếu master còn chạy (chỉ Sentinel-1 down), restart master
    có thể gây ra THÊM disruption (master restart → replicas resync)
  - Thay vào đó: xác định master status TRƯỚC

Step 2: Kiểm tra master còn sống không
  - redis-cli -p 6379 PING (direct to master IP — discover via sentinel)
  - docker exec sentinel-2 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
  - Nếu master UP: chỉ cần restore Sentinel-1
  - Nếu master DOWN: failover sẽ tự xảy ra (Sentinel-2 + Sentinel-3 đủ quorum)

Step 3: Restore Sentinel-1
  - docker start sentinel-1 (hoặc restart process)
  - Verify: redis-cli -p 26379 SENTINEL ckquorum mymaster → OK

Step 4: Emergency với 2 Sentinels
  - Ưu tiên restore Sentinel thứ 3 hoặc start replacement Sentinel trên host khác
  - Nếu master down và business cần recover ngay: manual failover có kiểm soát sau khi xác nhận old master stopped/isolated
  - Tránh hạ quorum xuống 1 trừ khi đã cô lập old master và có kế hoạch revert ngay

Step 5: Manual failover thay vì auto
  - Khi: đang upgrade Redis version, cần kiểm soát thời điểm failover
  - docker exec sentinel-1 SENTINEL failover mymaster
  - Chỉ định replica nào được promote
```

---

### Key Takeaways

1. **Sentinel không phải Redis process** — chạy độc lập, giao tiếp qua TCP port 26379.
2. **Quorum = majority** — 3 node → quorum=2, 5 node → quorum=3. KHÔNG dùng quorum=1 hoặc quorum=3 trên 3 nodes.
3. **Client không bao giờ hardcode master IP** — dùng `SENTINEL get-master-addr-by-name` hoặc Sentinel-aware client library.
4. **ioredis tự động handle `+switch-master`** — chỉ cần subscribe sentinel event để log. go-redis FailoverClient cũng tự động.
5. **Failover time = down-after + ODOWN + election + promotion + client reconnect** — thường 15-30 giây.
6. **`min-replicas-to-write` là trade-off consistency vs availability** — đặt = 0 cho cache, = 2 cho primary store.
7. **2 Sentinel = anti-pattern** — không đủ quorum khi 1 fail.
8. **Luôn spread Sentinels across AZs** — không co-locate với Redis trên cùng host.
9. **Monitor Sentinel health** — không chỉ monitor Redis. Sentinel process die = no failover.
10. **Test failover thường xuyên** — chaos engineering là cách duy nhất để xác nhận failover works.
