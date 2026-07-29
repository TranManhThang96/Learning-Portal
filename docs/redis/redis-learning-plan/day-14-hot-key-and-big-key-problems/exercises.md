# Day 14: Hot Key & Big Key Problems — Exercises

**Thời gian**: ~2 giờ
**Ngôn ngữ**: TypeScript (ioredis)
**Docker image**: redis:7.2-alpine

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Tạo Big Key Workloads

**Mục tiêu**: Tạo các loại big key để test detection tools.

```bash
# Kết nối redis-cli
docker exec -it redis-hotkey-lab redis-cli

# 1. Big String (100KB)
SET big:string:100kb "x" PADDING_TO_100KB

# 2. Big Hash (>1000 fields)
redis-cli <<'EOF'
  HMSET big:hash:10k field001 value001 field002 value002
  -- Using loop to create 10000 fields
  EVAL "for i=1,10000 do redis.call('HSET', KEYS[1], 'field'..string.format('%06d', i), 'value'..i) end" 1 big:hash:10k
EOF

# 3. Big List (1M elements)
redis-cli <<'EOF'
  EVAL "for i=1,1000000 do redis.call('RPUSH', KEYS[1], 'item_'..i) end" 1 big:list:1m
EOF

# 4. Big Sorted Set (100K members)
redis-cli <<'EOF'
  EVAL "for i=1,100000 do redis.call('ZADD', KEYS[1], math.random()*10000, 'member_'..i) end" 1 big:zset:100k
EOF

# 5. Verify sizes
DBSIZE
MEMORY USAGE big:string:100kb
MEMORY USAGE big:hash:10k
LLEN big:list:1m
ZCARD big:zset:100k
```

**Expected output**:
```txt
(integer) 5
(integer) 102400
(integer) 2097152
(integer) 1000000
(integer) 100000
```

### 1.2. Tạo Hot Key Workload

```bash
# Config must have maxmemory-policy = allkeys-lfu
redis-cli CONFIG GET maxmemory-policy
# Should show: allkeys-lfu

# Tạo 1 key và access 100K lần (LFU counter sẽ cao)
SET hot:counter:global "0"

# Loop INCR 50K lần
redis-cli <<'EOF'
  for i=1,50000 do
    redis.call('INCR', 'hot:counter:global')
  end
EOF

# Verify LFU frequency
OBJECT FREQ hot:counter:global
# Expected: high number (>1000)

# Tạo 100 user keys (sharded pattern)
redis-cli <<'EOF'
  for i=1,100 do
    redis.call('INCR', 'hot:counter:user_'..i)
  end
EOF
```

### 1.3. Detect với --bigkeys, --hotkeys, --memkeys

```bash
# 1. Scan big keys (non-blocking, fast)
redis-cli --bigkeys
# Quan sát: big String, big Hash, big List, big Zset

# 2. Scan hot keys (requires LFU policy)
redis-cli --hotkeys
# Quan sát: hot:counter:global nên xuất hiện với freq cao

# 3. Accurate memory scan (slower)
redis-cli --memkeys
# So sánh với --bigkeys output

# 4. Kiểm tra OBJECT ENCODING
redis-cli OBJECT ENCODING big:list:1m
redis-cli OBJECT ENCODING big:zset:100k
redis-cli OBJECT ENCODING big:hash:10k
# Expected: quicklist, skiplist, hashtable (encoded differently at scale)
```

**Expected observation**: `--bigkeys` shows only the "biggest so far" in each type — it misses many medium-large keys. `--memkeys` gives more complete picture. `--hotkeys` shows hot:counter:global with freq ~255.

### 1.4. Test DEL vs UNLINK Blocking

```bash
# Tạo 1 big list
redis-cli <<'EOF'
  EVAL "for i=1,500000 do redis.call('RPUSH', KEYS[1], 'item_'..i) end" 1 test:biglist
EOF

# Watch Redis latency trong terminal khác:
# redis-cli --latency-history

# Test DEL (synchronous - observe blocking)
TIME
DEL test:biglist
TIME
# Quan sát: TIME trước và sau DEL cách nhau ~100-200ms

# Tạo lại
redis-cli <<'EOF'
  EVAL "for i=1,500000 do redis.call('RPUSH', KEYS[1], 'item_'..i) end" 1 test:biglist2
EOF

# Test UNLINK (async - no observable delay)
TIME
UNLINK test:biglist2
TIME
# Quan sát: TIME trước và sau UNLINK cách nhau ~0-1ms

# Cleanup
FLUSHDB
```

**Expected observation**: DEL blocks ~100-200ms. UNLINK returns immediately (~0ms). Check memory: `redis-cli INFO memory | grep used_memory_human` — after UNLINK, memory may still be high until background thread frees.

---

## 2. Hands-on Lab: Hot Key Splitter (60-70 phút)

### 2.1. Mục tiêu

Implement hot key splitter cho 1 flash sale counter. Benchmark trước và sau sharding.

### 2.2. Setup

```bash
# docker-compose.yml (đã có từ document.md)
# Start nếu chưa chạy
docker compose up -d

# Verify
docker exec -it redis-hotkey-lab redis-cli PING
# Expected: PONG
```

### 2.3. Baseline: Single Hot Key Benchmark

Tạo file `src/baseline.ts`:

```typescript
// src/baseline.ts
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379, maxRetriesPerRequest: 3 });
const redisReplica = new Redis({ host: 'localhost', port: 6380, maxRetriesPerRequest: 3 });

const COUNTER_KEY = 'flash_sale:counter:global';
const NUM_REQUESTS = 10_000;
const NUM_CLIENTS = 100; // concurrent clients

async function setup(): Promise<void> {
  await redis.unlink(COUNTER_KEY).catch(() => {});
  await redis.set(COUNTER_KEY, '0');
}

async function baselineIncrement(): Promise<{ durationMs: number; finalValue: string }> {
  await redis.set(COUNTER_KEY, '0');

  const start = Date.now();

  await Promise.all(
    Array.from({ length: NUM_CLIENTS }, async () => {
      for (let i = 0; i < NUM_REQUESTS / NUM_CLIENTS; i++) {
        await redis.incr(COUNTER_KEY);
      }
    })
  );

  const durationMs = Date.now() - start;
  const finalValue = await redis.get(COUNTER_KEY);
  return { durationMs, finalValue: finalValue ?? '0' };
}

async function baselineRead(): Promise<{ readDurationMs: number; opsPerSec: number }> {
  const start = Date.now();
  let reads = 0;

  await Promise.all(
    Array.from({ length: NUM_CLIENTS }, async () => {
      for (let i = 0; i < NUM_REQUESTS / NUM_CLIENTS; i++) {
        await redis.get(COUNTER_KEY);
        reads++;
      }
    })
  );

  const readDurationMs = Date.now() - start;
  const opsPerSec = Math.round((reads / readDurationMs) * 1000);
  return { readDurationMs, opsPerSec };
}

async function main() {
  console.log('=== Baseline Hot Key Benchmark ===\n');

  await setup();

  console.log(`Single key: ${COUNTER_KEY}`);
  console.log(`Requests: ${NUM_REQUESTS} (${NUM_CLIENTS} concurrent clients)\n`);

  // Read benchmark (hot read scenario)
  console.log('--- Read Benchmark (hot key GET) ---');
  await redis.set(COUNTER_KEY, '50000');
  const { readDurationMs, opsPerSec } = await baselineRead();
  console.log(`  Duration: ${readDurationMs}ms`);
  console.log(`  Throughput: ${opsPerSec} ops/sec`);
  console.log(`  Per-request latency avg: ${(readDurationMs / NUM_REQUESTS * 1000).toFixed(2)}us\n`);

  // Increment benchmark (hot write scenario)
  console.log('--- Write Benchmark (hot key INCR) ---');
  const { durationMs, finalValue } = await baselineIncrement();
  console.log(`  Duration: ${durationMs}ms`);
  console.log(`  Throughput: ${Math.round((NUM_REQUESTS / durationMs) * 1000)} ops/sec`);
  console.log(`  Final counter value: ${finalValue}`);
  console.log(`  Expected: ${NUM_REQUESTS}, Got: ${finalValue}\n`);

  // Observe: with 10K ops on 1 hot key, you should see high latency
  // p99 GET should be visible if we tracked percentiles

  await redis.quit();
  await redisReplica.quit();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
```

Chạy:
```bash
npx ts-node src/baseline.ts
```

### 2.4. Sharded Counter Implementation

Tạo file `src/sharded-counter.ts`:

```typescript
// src/sharded-counter.ts
import Redis from 'ioredis';

// TypeScript implementation - hot key splitter
export class ShardedCounter {
  private client: Redis;
  private numShards: number;

  constructor(client: Redis, numShards: number = 100) {
    this.client = client;
    this.numShards = numShards;
  }

  private hashString(s: string): number {
    let hash = 0;
    for (let i = 0; i < s.length; i++) {
      const char = s.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  }

  private shardKey(key: string, shardId: number): string {
    return `${key}:shard_${String(shardId).padStart(3, '0')}_${this.numShards}`;
  }

  private pickShard(member: string): number {
    return this.hashString(member) % this.numShards;
  }

  private allShardKeys(key: string): string[] {
    return Array.from({ length: this.numShards }, (_, i) => this.shardKey(key, i));
  }

  async incr(key: string, actorId: string, delta: number = 1): Promise<number> {
    // Deterministic sharding keeps writes for the same actor on one shard.
    // The shard value itself is a String counter, not a Sorted Set.
    const shardId = this.pickShard(actorId);
    const shardK = this.shardKey(key, shardId);
    return this.client.incrby(shardK, delta);
  }

  async getTotal(key: string): Promise<number> {
    const shardKeys = this.allShardKeys(key);
    const results = await this.client.mget(...shardKeys);
    return results.reduce((sum, v) => sum + (v ? parseInt(v, 10) : 0), 0);
  }

  async reset(key: string): Promise<void> {
    const shardKeys = this.allShardKeys(key);
    await this.client.unlink(...shardKeys);
  }
}

const redis = new Redis({ host: 'localhost', port: 6379, maxRetriesPerRequest: 3 });

async function main() {
  const NUM_REQUESTS = 10_000;
  const NUM_CLIENTS = 100;
  const NUM_SHARDS = 100;
  const COUNTER_KEY = 'flash_sale:counter:sharded';

  console.log('=== Sharded Counter Benchmark ===\n');
  console.log(`Shards: ${NUM_SHARDS}`);
  console.log(`Requests: ${NUM_REQUESTS} (${NUM_CLIENTS} concurrent)\n`);

  const counter = new ShardedCounter(redis, NUM_SHARDS);
  await counter.reset(COUNTER_KEY);

  // Increment benchmark
  console.log('--- Sharded Write Benchmark (INCR across 100 shards) ---');
  const startIncr = Date.now();

  await Promise.all(
    Array.from({ length: NUM_CLIENTS }, async () => {
      for (let i = 0; i < NUM_REQUESTS / NUM_CLIENTS; i++) {
        await counter.incr(COUNTER_KEY, `client:${Math.random().toString(36).slice(2)}`);
      }
    })
  );

  const incrDurationMs = Date.now() - startIncr;
  const totalFromRedis = await counter.getTotal(COUNTER_KEY);

  console.log(`  Duration: ${incrDurationMs}ms`);
  console.log(`  Throughput: ${Math.round((NUM_REQUESTS / incrDurationMs) * 1000)} ops/sec`);
  console.log(`  Expected: ${NUM_REQUESTS}, Got: ${totalFromRedis}\n`);

  // Aggregate read from all shards
  console.log('--- Sharded Read: Aggregate Total ---');
  const startRead = Date.now();
  const aggregateTotal = await counter.getTotal(COUNTER_KEY);
  const readDurationMs = Date.now() - startRead;

  console.log(`  Duration: ${readDurationMs}ms (includes 100 shard reads)`);
  console.log(`  Aggregate total: ${aggregateTotal}`);
  console.log(`  Consistency note: exact after all writes finish; during live writes, reads are point-in-time best effort across shards.`);
  console.log();

  // Reset using UNLINK
  console.log('--- Reset (UNLINK 100 shards) ---');
  const resetStart = Date.now();
  await counter.reset(COUNTER_KEY);
  const resetDurationMs = Date.now() - resetStart;
  console.log(`  Duration: ${resetDurationMs}ms (async UNLINK)\n`);

  await redis.quit();
  console.log('Benchmark complete.');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
```

Chạy:
```bash
npx ts-node src/sharded-counter.ts
```

### 2.5. So sánh Kết quả

Sau khi chạy cả baseline và sharded, điền vào bảng:

| Metric | Baseline (Single Key) | Sharded (100 Shards) | Improvement |
|---|---|---|---|
| Write throughput (ops/sec) | ? | ? | ?× |
| Write latency avg (ms) | ? | ? | ?× faster |
| Per-request latency p99 (ms) | ? (estimate) | ? (estimate) | ?× |
| Reset duration (ms) | ~250ms (DEL) | ?ms (UNLINK) | ?× |
| Read consistency | Perfect | Eventual (sum approximation) | — |

**Ghi chú quan trọng**: Nếu lab chạy trên một Redis standalone, sharding key không làm write throughput tăng tuyến tính vì mọi command vẫn đi qua một event loop. Key splitting thực sự giúp throughput khi shard được phân bố qua Redis Cluster/nhiều nodes; trên standalone nó chủ yếu giảm big key risk, giảm reset latency, và chuẩn bị data model để scale out.

### 2.6. Hints

1. **Sharding key**: Dùng FNV-1a hash hoặc CRC32 để distribute đều. Không dùng modulo đơn giản trên sequential IDs.
2. **Pipeline**: Khi đọc từ N shards, dùng `pipeline()` để giảm RTT từ N xuống 1.
3. **UNLINK**: Kiểm tra memory sau UNLINK: `redis-cli INFO memory | grep used_memory_human`. Memory vẫn cao ban đầu (background thread chưa free xong).
4. **Read aggregation**: Khi sum N shards, dùng `MGET` (1 RTT) thay vì N lần `GET` (N RTT).

---

## 3. Challenge Exercise (30-40 phút)

### 3.1. Refactor Leaderboard 1M Users

**Scenario**: Bạn có 1 leaderboard với 1 triệu users trong 1 Sorted Set (~100MB). System cần:

- Xem top 100 users (ZREVRANGE)
- Xem rank của 1 user (ZRANK)
- Reset leaderboard mỗi ngày (DEL)
- Write throughput: 50K ZINCRBY/sec

**Current Problem**: 1 Sorted Set 1M members = big key. DEL blocks ~300-500ms. ZREVRANGE on 1M sorted set = slow. Replication of 100MB key = lag.

### 3.2. Yêu cầu

**Part A: Design** (10 phút)

Thiết kế kiến trúc bucket-based leaderboard. Trả lời:

1. Số buckets tối ưu? Tại sao?
2. Làm thế nào để query top 100 global khi data nằm trong M buckets?
3. Làm thế nào để query ZRANK (user rank) trong bucket architecture?
4. Reset strategy: dùng UNLINK hay rename approach?
5. Trade-off của approach này so với single ZSET?

**Part B: Implement** (20 phút)

Implement kiến trúc bucket-based leaderboard trong TypeScript.

```typescript
// src/bucket-leaderboard.ts
// Starter: implement the following methods

class BucketLeaderboard {
  private redis: Redis;
  private numBuckets: number;

  constructor(redis: Redis, numBuckets: number) {}

  // ZINCRBY on a random bucket
  async zincrby(key: string, member: string, score: number): Promise<number> {}

  // Get top K from all buckets (merge-sort)
  async getTopK(key: string, k: number): Promise<Array<{ rank: number; member: string; score: number }>> {}

  // Get rank of a specific user (search in correct bucket)
  async getRank(key: string, member: string): Promise<number | null> {}

  // Safe reset (UNLINK all bucket keys)
  async reset(key: string): Promise<void> {}

  // Seed with N random members (for testing)
  async seed(key: string, numMembers: number, maxScore: number): Promise<void> {}
}
```

**Part C: Analysis** (10 phút)

Benchmark và phân tích:

1. So sánh write throughput: single ZSET vs bucket approach
2. Read latency top-100: single ZSET vs bucket approach (pipeline vs non-pipeline)
3. Memory overhead của bucket approach (M keys thay vì 1 key)
4. Recommendation: khi nào nên dùng bucket, khi nào single ZSET vẫn đủ?

### 3.3. Solution Hint

```txt
Bucket approach implementation outline:

numBuckets = 100
bucketId = hash(member) % numBuckets
bucketKey = leaderboard:daily:bucket_{bucketId}

ZINCRBY bucketKey score member
  // Fast: operates on 1 of 100 buckets, ~10K elements each

getTopK(100):
  pipeline = redis.pipeline()
  for bucketId in 0..99:
    pipeline.zrevrange(leaderboard:daily:bucket_{bucketId}, 0, 99, WITHSCORES)
  results = pipeline.exec()  // 1 RTT, 100 sub-commands in parallel

  // Merge all 100 × 100 = 10K results
  // Sort and take top 100
  // O(10K log 10K) = manageable

getRank(member):
  bucketId = hash(member) % numBuckets
  bucketKey = leaderboard:daily:bucket_{bucketId}
  return ZREVRANK bucketKey member  // Direct, O(log 10K)

reset():
  keys = [leaderboard:daily:bucket_0 ... leaderboard:daily:bucket_99]
  UNLINK keys  // ~1ms, all 100 keys freed async
```

---

## 4. Reflection Questions (5 phút)

1. **Trade-off quyết định**: Trong scenario nào thì key splitting (sharding) là over-engineering? Trong scenario nào thì không có lựa chọn nào khác ngoài sharding?

2. **Consistency vs Performance**: Khi bạn chấp nhận stale data từ replica read để giảm hot key pressure, làm thế nào để quantify acceptable staleness window cho business của bạn?

3. **Big key prevention**: Bạn sẽ thiết lập automated monitoring như thế nào để phát hiện big key trước khi chúng gây incident? Số lượng keys, size thresholds, hay access frequency quan trọng hơn?

4. **Migration complexity**: Khi phát hiện hot key trên production system đang chạy, migration sang sharded architecture có risk gì? Làm sao để rollback nếu sharding gây bug?

5. **Cost-benefit**: Để implement hot key detection + mitigation cho 1 production system, ước tính bao nhiêu engineer-days? ROI đo lường bằng gì?

---

## 5. Solution Guide

### 5.1. Warm-up Solutions

**1.3 Expected detection results**:
```txt
--bigkeys output (sampled):
  big string:    102.4KB (detected as biggest string)
  big list:      1M elements (detected as biggest list)
  big zset:      100K members (detected as biggest zset)
  big hash:      10K fields (detected as biggest hash)

--hotkeys output:
  hot:counter:global  freq:255 (or high number depending on access count)

Note: --bigkeys is sample-based. It may miss keys that are
"big but not biggest" in their type category.
```

**1.4 DEL vs UNLINK**:
- DEL on 500K List: expect ~50-100ms blocking on standard hardware
- UNLINK: returns immediately (~0.5ms)
- Check memory after UNLINK: still high initially (background thread freeing)
- After ~1-2 seconds: memory returns to normal

### 5.2. Sharded Counter Solution

**Full implementation**:

```typescript
// ShardedCounter class - already provided in exercises.md
// Key insight: each shard is a small String counter and aggregate reads use MGET.
// On one standalone Redis node this does NOT multiply throughput because the
// event loop is still single-threaded. The gain is data-model safety and readiness
// for Redis Cluster / client-side sharding where shards live on different nodes.

// Expected results comparison:
// Standalone Redis: write throughput may be similar to baseline; p99 may improve
// only if the old key had extra work around it (large values, read aggregation,
// Lua, replication pressure).
// Redis Cluster / multi-node sharding: throughput can scale with node count.

// Critical: Use pipeline for multi-shard reads
async getTotal(key: string): Promise<number> {
  const shardKeys = this.allShardKeys(key);
  // WRONG: const results = await Promise.all(shardKeys.map(k => redis.get(k)));
  // RIGHT: const results = await redis.mget(...shardKeys); // 1 RTT
  const results = await this.client.mget(...shardKeys);
  return results.reduce((sum, v) => sum + (v ? parseInt(v, 10) : 0), 0);
}
```

### 5.3. Bucket Leaderboard Solution

**Design answers**:

1. **Số buckets**: 100 buckets là sweet spot.
   - Mỗi bucket ~10K members (manageable for ZREVRANGE)
   - Top-100 per bucket × 100 buckets = 10K results to merge
   - O(10K log 10K) = ~170K operations, acceptable
   - Trade-off: nếu <10 buckets, mỗi bucket quá lớn. Nếu >1000 buckets, merge overhead lớn.

2. **Top-100 global**: Pipeline ZREVRANGE từ tất cả buckets (1 RTT), merge-sort 10K results, take top 100.

3. **ZRANK**: Hash member → bucket ID → ZREVRANK trên bucket đó. O(log bucket_size).

4. **Reset**: UNLINK tất cả bucket keys. ~1ms total. Hoặc rename approach: đổi tên sang garbage bucket + TTL.

5. **Trade-off**:
   | Aspect | Single ZSET | Bucket Approach |
   |---|---|---|
   | ZREVRANGE top-100 | ~1ms | ~1ms (pipeline) + merge |
   | ZRANK | ~log(1M) | ~log(10K) |
   | DEL/Reset | ~300-500ms | ~1ms (UNLINK) |
   | Memory | 1 key | 100 keys (slight overhead) |
   | Atomic operations on full set | Supported | NOT supported |

**When to use single ZSET**: Rank queries < 1000/sec, rare resets, no strict latency requirements.

**When to use bucket**: Write-heavy (>10K/sec), frequent resets, strict latency requirements, replication lag unacceptable.

### 5.4. Warning: Spoiler

**Nếu bạn tự implement trước khi xem solution**:

1. Cố gắng giải quyết merge-sort problem trước. Đây là phần phức tạp nhất.
2. Nhớ: 1 user chỉ xuất hiện trong 1 bucket. Merge không cần dedupe trừ khi hash collision (rất hiếm).
3. Pipeline không đảm bảo order. Phải track bucket index để merge đúng.

### 5.5. Bonus: Production Checklist

Sau bài tập, tạo checklist để validate production readiness:

```markdown
## Hot Key & Big Key Production Checklist

- [ ] Big key scan chạy định kỳ (weekly)
- [ ] Hot key detection enabled (maxmemory-policy = allkeys-lfu)
- [ ] Per-key metrics logged ở application layer
- [ ] DEL replaced by UNLINK trong tất cả code paths
- [ ] DEL/UNLINK reviewed trong scheduled jobs
- [ ] Big key size limits enforced trong data model review
- [ ] Read replica configured cho hot read paths
- [ ] Circuit breaker set up cho Redis latency spikes
- [ ] Alert: replication lag > 5 seconds
- [ ] Alert: memory fragmentation ratio > 1.5
- [ ] Alert: single key > 10MB detected
```
