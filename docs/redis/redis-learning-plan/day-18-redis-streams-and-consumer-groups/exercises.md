# Day 18: Redis Streams & Consumer Groups — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript (luân phiên với Day 17 Go)
**Redis**: 7.2+

---

## 0. Setup

```bash
# Terminal 1: Start Redis
docker run --rm -p 6379:6379 redis:7.2-alpine redis-server --maxmemory 256mb --appendonly yes

# Verify Redis is up
redis-cli ping
# Expected: PONG
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. XADD — Add Entries to Stream

```bash
# Add 5 entries to stream "warmup:orders"
redis-cli XADD warmup:orders MAXLEN ~1000 * order_id ORD001 amount 50000
redis-cli XADD warmup:orders MAXLEN ~1000 * order_id ORD002 amount 120000
redis-cli XADD warmup:orders MAXLEN ~1000 * order_id ORD003 amount 75000
redis-cli XADD warmup:orders MAXLEN ~1000 * order_id ORD004 amount 300000
redis-cli XADD warmup:orders MAXLEN ~1000 * order_id ORD005 amount 90000

# Check stream length
redis-cli XLEN warmup:orders
# Expected: 5

# Read all entries
redis-cli XRANGE warmup:orders - + COUNT 10
```

**Questions:**
- Entry ID format là gì? Có tăng monotonic không?
- `MAXLEN ~1000` vs `MAXLEN 1000` khác nhau gì ở output?

### 1.2. Consumer Group — Create and Read

```bash
# Create consumer group from beginning ($ = current end, use 0-0 for from start)
redis-cli XGROUP CREATE warmup:orders processors $ MKSTREAM

# Create a second consumer
redis-cli XGROUP CREATECONSUMER warmup:orders processors consumer-2

# Read new messages (nothing new since last-read is $)
redis-cli XREADGROUP GROUP processors consumer-1 BLOCK 1000 COUNT 10 STREAMS warmup:orders ">"

# Read pending messages already delivered to this consumer (not whole stream backfill)
redis-cli XREADGROUP GROUP processors consumer-1 BLOCK 1000 COUNT 10 STREAMS warmup:orders "0-0"

# Check consumer group info
redis-cli XINFO GROUPS warmup:orders
redis-cli XINFO CONSUMERS warmup:orders processors
```

**Expected output**: Consumer-1 nhận được 5 messages (OR001-ORD005).

### 1.3. XACK — Acknowledge và PEL

```bash
# Add 3 new entries (while group is already reading from $)
redis-cli XADD warmup:orders * order_id ORD006 amount 45000
redis-cli XADD warmup:orders * order_id ORD007 amount 80000
redis-cli XADD warmup:orders * order_id ORD008 amount 150000

# Read with consumer-2 (no ACK yet)
redis-cli XREADGROUP GROUP processors consumer-2 BLOCK 1000 COUNT 10 STREAMS warmup:orders ">"

# Check pending entries (PEL)
redis-cli XPENDING warmup:orders processors
# Expected: 3 entries (ORD006, ORD007, ORD008) — not yet ACKed

# Now ACK them (replace with actual IDs from previous output)
redis-cli XACK warmup:orders processors <ID-ORD006> <ID-ORD007> <ID-ORD008>

# Verify PEL is empty
redis-cli XPENDING warmup:orders processors
# Expected: (empty)
```

### 1.4. XAUTOCLAIM — Recover from Consumer Crash

```bash
# Simulate: consumer-1 crashed, 2 messages still in its PEL
# First, create a new entry and let consumer-1 "receive" it
redis-cli XADD warmup:orders * order_id ORD009 amount 200000
redis-cli XREADGROUP GROUP processors consumer-1 BLOCK 1000 COUNT 10 STREAMS warmup:orders ">"

# Check consumer-1's pending
redis-cli XPENDING warmup:orders processors consumer-1

# Simulate consumer-1 crash by NOT ACKing (message stays in PEL)
# Now consumer-2 tries to claim messages idle > 5 seconds
redis-cli XAUTOCLAIM warmup:orders processors consumer-2 5000 0-0 COUNT 10

# Expected: claims the message (ORD009) from consumer-1's PEL
# consumer-1 now loses that message from its PEL
# consumer-2 should process and XACK it
```

### 1.5. Trimming — Approximate vs Exact

```bash
# Create stream with approximate trim (fast)
redis-cli XADD warmup:trim-approx MAXLEN ~10 * data "value"
# Add 20 entries
for i in $(seq 1 20); do redis-cli XADD warmup:trim-approx MAXLEN ~10 * i $i; done

# Check length (should be around 10, not exactly 10)
redis-cli XLEN warmup:trim-approx

# Create stream with exact trim (slower)
redis-cli XADD warmup:trim-exact MAXLEN 10 * data "value"
for i in $(seq 1 20); do redis-cli XADD warmup:trim-exact MAXLEN 10 * i $i; done

# Check length (should be exactly 10)
redis-cli XLEN warmup:trim-exact
```

### 1.6. Cleanup

```bash
redis-cli XTRIM warmup:orders MAXLEN 0
redis-cli XTRIM warmup:trim-approx MAXLEN 0
redis-cli XTRIM warmup:trim-exact MAXLEN 0
```

---

## 2. Hands-on Lab: Order Processing Job Queue (60-70 phút)

**Scenario**: E-commerce order processing pipeline. Producer tạo orders (XADD), 3 consumers xử lý trong consumer group. Mỗi consumer có 20% chance crash giữa chừng (không XACK). XAUTOCLAIM recover. DLQ cho messages fail > 5 lần.

### 2.1. Project Setup

```bash
mkdir -p day18-streams && cd day18-streams
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
# docker-compose.yml
version: "3.8"
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

```bash
docker-compose up -d
docker-compose ps
```

### 2.2. Starter Code

```typescript
// src/config.ts
export const CONFIG = {
  redis: {
    host: "localhost",
    port: 6379,
  },
  stream: "lab:orders:stream",
  group: "lab:order-processors",
  dlqStream: "lab:orders:dlq",
  maxRetries: 5,
  retryHash: "lab:orders:retry-count",
  blockMs: 2000,
  count: 5,
  minIdleMs: 30_000, // 30 seconds — must be > 2× process time
};
```

```typescript
// src/redis.ts
import Redis from "ioredis";
import { CONFIG } from "./config";

export const redis = new Redis({
  host: CONFIG.redis.host,
  port: CONFIG.redis.port,
  maxRetriesPerRequest: 3,
  retryStrategy: (times) => Math.min(times * 100, 3000),
});

redis.on("error", (err) => console.error("Redis error:", err));
redis.on("connect", () => console.log("Connected to Redis"));

export async function initConsumerGroup(): Promise<void> {
  try {
    await redis.xgroup("CREATE", CONFIG.stream, CONFIG.group, "$", "MKSTREAM");
    console.log(`Created consumer group: ${CONFIG.group}`);
  } catch (err: any) {
    if (err.message.includes("BUSYGROUP")) {
      console.log(`Group ${CONFIG.group} already exists`);
    } else {
      throw err;
    }
  }
}

export function fieldsToObject(fields: string[]): Record<string, string> {
  const obj: Record<string, string> = {};
  for (let i = 0; i < fields.length; i += 2) {
    obj[fields[i]] = fields[i + 1];
  }
  return obj;
}
```

```typescript
// src/producer.ts
import { redis, initConsumerGroup } from "./redis";
import { CONFIG } from "./config";

async function seedOrders(count: number = 20): Promise<void> {
  await initConsumerGroup();

  console.log(`\n=== Seeding ${count} orders ===`);
  for (let i = 1; i <= count; i++) {
    const orderId = `ORD-${String(i).padStart(3, "0")}`;
    const amount = Math.floor(Math.random() * 500000) + 10000; // 10K-510K VND

    const id = await redis.xadd(
      CONFIG.stream,
      "MAXLEN",
      "~",
      "50000", // Approximate trim: max 50K entries
      "*",
      "order_id", orderId,
      "amount", String(amount),
      "status", "pending",
      "created_at", String(Date.now()),
    );
    console.log(`  [Producer] XADD ${orderId} -> ${id}`);
    await new Promise((r) => setTimeout(r, 50)); // Simulate time between orders
  }
  console.log(`\n=== Done seeding ${count} orders ===\n`);
}

const orderCount = parseInt(process.argv[2] || "20", 10);
seedOrders(orderCount).then(() => {
  setTimeout(() => process.exit(0), 1000);
});
```

```typescript
// src/consumer.ts
import { redis, initConsumerGroup, fieldsToObject } from "./redis";
import { CONFIG } from "./config";

// --- TODO 1: Implement processOrder ---
// Simulate order processing
// - Parse order data from fields
// - Simulate random processing time (100-800ms)
// - 20% chance of failure (simulate transient error)
// - Return: { success: boolean, message: string }
async function processOrder(
  orderId: string,
  _fields: string[],
): Promise<{ success: boolean; message: string }> {
  // HINT: Use Math.random() < 0.2 to simulate 20% failure rate
  // HINT: Use await new Promise(r => setTimeout(r, ms)) for delay
  // Your code here:
  throw new Error("TODO: Implement processOrder");
}

// --- TODO 2: Implement moveToDLQ ---
// Move entry to DLQ after max retries
async function moveToDLQ(entryId: string, fields: string[]): Promise<void> {
  // HINT: XADD to CONFIG.dlqStream with original-id, retry-count, and all fields
  // HINT: XACK original stream to remove from PEL
  // HINT: HDEL retry hash
  // Your code here:
  throw new Error("TODO: Implement moveToDLQ");
}

// --- TODO 3: Implement handleMessage ---
// Called for each message from XREADGROUP
async function handleMessage(
  entryId: string,
  fields: string[],
): Promise<void> {
  const data = fieldsToObject(fields);
  const orderId = data.order_id || entryId;

  // Increment retry count
  const retryCount = await redis.hincrby(CONFIG.retryHash, entryId, 1);

  if (retryCount > CONFIG.maxRetries) {
    console.log(`  [!] ${orderId} exceeded max retries (${retryCount}), moving to DLQ`);
    await moveToDLQ(entryId, fields);
    return;
  }

  try {
    const result = await processOrder(orderId, fields);
    if (result.success) {
      // Success: XACK
      await redis.xack(CONFIG.stream, CONFIG.group, entryId);
      console.log(`  [OK] ${orderId} processed successfully (retry #${retryCount})`);
      // Clean up retry hash
      await redis.hdel(CONFIG.retryHash, entryId);
    } else {
      // Transient failure: don't XACK — stays in PEL
      console.log(
        `  [RETRY ${retryCount}/${CONFIG.maxRetries}] ${orderId}: ${result.message}`,
      );
    }
  } catch (err) {
    console.error(`  [ERROR] ${orderId}:`, err);
    // Error: don't XACK — stays in PEL
  }
}

// --- TODO 4: Implement consume loop ---
async function consume(consumerName: string): Promise<void> {
  await initConsumerGroup();
  console.log(`\n=== Consumer "${consumerName}" started ===`);

  let processedCount = 0;
  let errorCount = 0;

  while (true) {
    try {
      // HINT: XREADGROUP with BLOCK, COUNT, and ">" for new messages only
      // Your code here:
      const result = null; // TODO: Replace with actual XREADGROUP call

      if (!result) {
        continue;
      }

      const [, messages] = result[0] as [string, [string, string[]][]];

      if (messages.length === 0) {
        continue;
      }

      console.log(`  [${consumerName}] Received ${messages.length} messages`);

      for (const [entryId, fields] of messages) {
        // HINT: Each message should be handled with a small delay
        // to simulate realistic processing
        await handleMessage(entryId, fields);
        processedCount++;
      }
    } catch (err) {
      errorCount++;
      console.error(`[${consumerName}] Error in consume loop:`, err);
      await new Promise((r) => setTimeout(r, 2000)); // Backoff on error
    }

    // Log stats every 10 processed
    if (processedCount % 10 === 0 && processedCount > 0) {
      console.log(
        `  [Stats] ${consumerName}: processed=${processedCount}, errors=${errorCount}`,
      );
    }
  }
}

// --- TODO 5: Implement autoClaimRecover ---
// Periodically claim messages from stalled consumers
async function autoClaimRecover(consumerName: string): Promise<void> {
  const intervalMs = CONFIG.minIdleMs / 2; // Run every half of min-idle-time

  setInterval(async () => {
    try {
      // HINT: XAUTOCLAIM with minIdleMs from CONFIG
      // Start from 0-0 to scan entire PEL
      // Your code here:
      const result = null; // TODO: Replace with actual XAUTOCLAIM call

      if (!result) return;

      const [, claimedIds, messages] = result as [string, string[], any[]];

      if (claimedIds.length > 0) {
        console.log(
          `  [${consumerName}] XAUTOCLAIM recovered ${claimedIds.length} messages`,
        );
        for (const [entryId, fields] of messages) {
          await handleMessage(entryId, fields);
        }
      }
    } catch (err) {
      console.error(`[${consumerName}] XAUTOCLAIM error:`, err);
    }
  }, intervalMs);
}

// Entry point
const consumerName = process.argv[2] || `consumer-${Date.now()}`;
consume(consumerName);
autoClaimRecover(consumerName);
```

### 2.3. Running the Lab

**Terminal 1 — Producer (seed orders):**
```bash
npx ts-node src/producer.ts 30
```

**Terminal 2, 3, 4 — 3 Consumers (mỗi terminal 1 consumer):**
```bash
# Terminal 2
npx ts-node src/consumer.ts worker-1

# Terminal 3
npx ts-node src/consumer.ts worker-2

# Terminal 4
npx ts-node src/consumer.ts worker-3
```

### 2.4. Expected Output

**Producer:**
```
=== Seeding 30 orders ===
  [Producer] XADD ORD-001 -> 1700000000000-0
  [Producer] XADD ORD-002 -> 1700000000000-1
  ...
=== Done seeding 30 orders ===
```

**Consumer (with crash simulation):**
```
=== Consumer "worker-1" started ===
  [worker-1] Received 5 messages
  [OK] ORD-001 processed successfully (retry #1)
  [RETRY 1/5] ORD-002: Simulated transient failure
  [OK] ORD-003 processed successfully (retry #1)
  ...
```

**After consumer crash simulation (kill one consumer, wait 30s):**
```
  [worker-2] XAUTOCLAIM recovered 3 messages
  [OK] ORD-007 processed successfully (retry #2)
```

**DLQ entries after 5 failures:**
```
redis-cli XLEN lab:orders:dlq
# Expected: count of permanently failed orders
redis-cli XRANGE lab:orders:dlq - + COUNT 5
```

### 2.5. Verification

```bash
# Check stream length (should stay under MAXLEN ~50000)
redis-cli XLEN lab:orders:stream

# Check all consumer groups
redis-cli XINFO GROUPS lab:orders:stream

# Check XPENDING — should be 0 or very low (no stuck messages)
redis-cli XPENDING lab:orders:stream lab:order-processors

# Check DLQ size
redis-cli XLEN lab:orders:dlq

# Check retry hash size (should be 0 after all processed)
redis-cli HLEN lab:orders:retry-count
```

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Design Event Pipeline — 50K Events/Second

**Scenario**: IoT telemetry platform. 50,000 sensors, mỗi sensor gửi 1 event/giây = **50K events/s**. Payload ~300 bytes/event. Yêu cầu:

1. **Retention**: 24 giờ (để reprocess incidents)
2. **Consumers**: Real-time dashboard (latency < 500ms), Analytics (batch, can lag 5 phút), Alert engine (latency < 1s)
3. **Failure recovery**: Consumer crash → redeliver trong 30 giây

**Tasks**:

A) **Memory calculation**:
   - 50K events/s × 3600s × 300 bytes = ? GB/giờ
   - 24 giờ = ? TB
   - Redis Streams (in-memory): feasible hay không? Với MAXLEN ~100K per stream?
   - Kafka (disk-based): ước tính disk cần thiết?

B) **Architecture decision**: Đề xuất kiến trúc sử dụng:
   - Redis Streams cho component nào? Tại sao?
   - Kafka cho component nào? Tại sao?
   - Có thể dùng hybrid không?

C) **Consumer group design**:
   - Dashboard consumer group: cần bao nhiêu consumers?
   - Analytics consumer group: batch size bao nhiêu?
   - Alert engine: priority consumer group hay shared?

D) **Production concerns**:
   - Monitoring: metric nào cần alert?
   - PEL size: alert threshold là bao nhiêu?
   - XTRIM strategy: approximate hay exact? MAXLEN bao nhiêu?

**Deliverable**: 1-2 trang architecture decision document.

### 3.2. Compare with Kafka in Specific Scenario

| Criteria | Redis Streams | Apache Kafka |
|---|---|---|
| Memory/disk cost (50K/s, 24h, 300B) | ? | ? |
| Consumer lag detection | ? | ? |
| Multi-DC replication | ? | ? |
| Operational complexity | ? | ? |
| Message retention | ? | ? |
| Consumer group rebalance | ? | ? |
| Schema evolution | ? | ? |

---

## 4. Reflection Questions (Open-ended)

1. Bạn đang build một payment gateway. Message không được process = financial loss. Bạn chọn Streams hay Kafka? Tại sao? Cần thêm gì để đảm bảo zero duplicate processing?

2. Team của bạn có 3 service cần đọc cùng event stream. Dùng 3 consumer groups hay 1 group với 3 consumers? Trade-off là gì?

3. Một developer trong team gợi ý dùng Redis Streams thay Kafka cho toàn bộ event sourcing. Bạn phản đối hay đồng ý? Lập luận với số liệu cụ thể.

4. Khi thiết kế DLQ, bạn nên lưu trữ failed message ở đâu? Trong Redis Stream (DLQ stream), trong database (retry table), hay external storage (S3)? Trade-off?

5. XAUTOCLAIM chạy mỗi 30 giây. min-idle-time = 30 giây. Giải thích race condition có thể xảy ra. Đề xuất giá trị min-idle-time tối ưu.

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 Entry ID format**:
```
Entry ID: 1700000000000-0 (milliseconds-sequence)
Auto-incrementing: 1700000000000-0, 1700000000000-1, 1700000000000-2, ...
MAXLEN ~1000 ≈ 1000 ± 5% (fast, heuristic-based)
MAXLEN 1000 = exactly 1000 (slower, scans all entries on trim)
```

**1.4 XAUTOCLAIM**:
```bash
# Claim messages idle > 5 seconds from any consumer
redis-cli XAUTOCLAIM warmup:orders processors consumer-2 5000 0-0 COUNT 10
# Returns: [next-start-id, [claimed-ids], [entry-contents]]
```

---

### Lab Solutions

**TODO 1: processOrder**
```typescript
async function processOrder(
  orderId: string,
  fields: string[],
): Promise<{ success: boolean; message: string }> {
  const processingTime = 100 + Math.floor(Math.random() * 700); // 100-800ms
  await new Promise((r) => setTimeout(r, processingTime));

  // 20% random failure — simulates transient error
  if (Math.random() < 0.2) {
    return { success: false, message: "Transient error (simulated)" };
  }

  return { success: true, message: "OK" };
}
```

**TODO 2: moveToDLQ**
```typescript
async function moveToDLQ(entryId: string, fields: string[]): Promise<void> {
  // Build DLQ entry with metadata
  const dlqArgs: string[] = [
    "original-id", entryId,
    "moved-at", String(Date.now()),
    "retry-count", String(CONFIG.maxRetries),
  ];
  // Append all original fields
  for (let i = 0; i < fields.length; i += 2) {
    dlqArgs.push(fields[i], fields[i + 1]);
  }
  await redis.xadd(CONFIG.dlqStream, "*", ...dlqArgs);

  // Remove from PEL by ACKing (entry will disappear from PEL)
  await redis.xack(CONFIG.stream, CONFIG.group, entryId);

  // Clean up retry counter
  await redis.hdel(CONFIG.retryHash, entryId);

  console.log(`  [DLQ] Moved ${entryId} to dead-letter stream`);
}
```

**TODO 3: handleMessage** (already provided in starter — key is try/catch + no XACK on failure)

**TODO 4: consume loop**
```typescript
async function consume(consumerName: string): Promise<void> {
  await initConsumerGroup();
  console.log(`\n=== Consumer "${consumerName}" started ===`);

  let processedCount = 0;

  while (true) {
    try {
      const result = await redis.xreadgroup(
        "GROUP", CONFIG.group, consumerName,
        "BLOCK", String(CONFIG.blockMs),
        "COUNT", String(CONFIG.count),
        "STREAMS", CONFIG.stream, ">",
      ) as any;

      if (!result || result.length === 0) continue;

      const [, messages] = result[0] as [string, [string, string[]][]];

      for (const [entryId, fields] of messages) {
        await handleMessage(entryId, fields);
        processedCount++;
      }
    } catch (err) {
      console.error(`[${consumerName}] Error:`, err);
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
}
```

**TODO 5: autoClaimRecover**
```typescript
async function autoClaimRecover(consumerName: string): Promise<void> {
  setInterval(async () => {
    try {
      const result = await redis.xautoclaim(
        CONFIG.stream, CONFIG.group, consumerName,
        String(CONFIG.minIdleMs),
        "0-0", // scan from beginning of PEL
        "COUNT", "100",
      ) as any;

      if (!result || result[1].length === 0) return;

      const [, claimedIds, messages] = result;

      console.log(
        `  [${consumerName}] XAUTOCLAIM recovered ${claimedIds.length} messages`,
      );
      for (const [entryId, fields] of messages) {
        await handleMessage(entryId, fields);
      }
    } catch (err) {
      console.error(`[${consumerName}] XAUTOCLAIM error:`, err);
    }
  }, CONFIG.minIdleMs / 2);
}
```

---

### Challenge Solutions

**3.1.A Memory calculation**:

```
50K events/s × 3600s × 300 bytes = 54 GB/giờ
24 giờ = 1,296 GB ≈ 1.3 TB

Redis Streams (in-memory):
  - 1.3 TB RAM >> budget của hầu hết deployment
  - Với MAXLEN ~100K: stream chỉ giữ 100K × 300B = 30 MB + 15 MB overhead
  - Nhưng: 24h retention KHÔNG đạt được với MAXLEN ~100K
  → Redis Streams: KHÔNG feasible cho use case này

Apache Kafka (disk-based):
  - 1.3 TB disk: rất cheap (~$50-100/month on cloud)
  - Kafka dùng sequential disk write: ~500 MB/s throughput
  - 50K × 300B/s = 15 MB/s → well within disk bandwidth
  → Kafka: feasible và recommended
```

**3.1.B Architecture recommendation**:

```
┌──────────────────────────────────────────────────────────────────┐
│                      Recommended Hybrid Architecture               │
│                                                                   │
│  Sensors (50K/s)                                                  │
│      │                                                           │
│      ▼                                                           │
│  Apache Kafka ─────────────────────────────────────────────────  │
│      │ (24h retention, disk, multi-DC)                          │
│      ├────────────────────┬─────────────────┬─────────────────   │
│      ▼                    ▼                 ▼                     │
│  Dashboard consumer   Analytics consumer  Alert engine          │
│  (real-time, low lag)  (batch, 5min lag)  (priority, <1s)      │
│                                                                   │
│  + Redis Streams (optional):                                     │
│    - Ingestion buffer từ edge devices đến Kafka                  │
│    - Hot path cho dashboard < 100ms                              │
│    - Redis dùng cho: caching, deduplication cache               │
└──────────────────────────────────────────────────────────────────┘
```

**3.1.D Production monitoring**:
```bash
# Alert thresholds for 50K/s pipeline:
# PEL size > 5000 sustained > 5 min: WARNING
# PEL size > 50000: CRITICAL
# Stream length growth rate > 200K/hour: ALERT (possible trim failure)
# XAUTOCLAIM claims > 100/min: WARNING (consumer lag)
# XAUTOCLAIM claims > 1000/min: CRITICAL (consumer group failure)
```

---

### Key Takeaways

1. **Streams là append-only log trong memory**: Không bao giờ dùng cho retention > vài giờ ở throughput cao.
2. **PEL ≠ message queue**: PEL là hệ thống tracking, không phải nơi lưu trữ message chờ xử lý.
3. **XACK = release khỏi PEL**: Không XACK → message tồn tại mãi trong PEL → memory leak.
4. **XAUTOCLAIM min-idle-time = 2× p99 process time**: Tránh race condition.
5. **Luôn luôn có DLQ**: Message fail > N lần → DLQ, không giữ trong PEL mãi mãi.
6. **Kafka thắng ở throughput cao và retention dài**: Redis Streams thắng ở simplicity và khi Redis đã có trong stack.
