# Day 7: AOF Rewrite & Durability Trade-off — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: TypeScript (ioredis + tsx)
**Docker images**: redis:7-alpine

---

## 1. Warm-up Exercises (15–20 phút)

### 1.1. Enable AOF and Check Status

```bash
redis-cli CONFIG SET appendonly yes
redis-cli CONFIG SET appendfsync everysec
redis-cli INFO persistence | grep -E "^aof_|^rdb_changes|^latest_fork"
```

**Expected output** (fresh instance):

```
aof_enabled:1
aof_rewrite_in_progress:0
aof_rewrite_scheduled:0
aof_last_rewrite_time_sec:-1
aof_current_rewrite_time_sec:0
aof_last_bgrewrite_status:lasted 0 seconds, start:0, performed 0 of 0 BBSEC
aof_delayed_fsync:0
aof_pending_bio_fsync:0
aof_last_load_duration_ms:0
aof_enabled:1
rdb_changes_since_last_save:0
latest_fork_usec:0
```

### 1.2. Test fsync Policy Commands

```bash
# Test: CONFIG SET appendfsync always
redis-cli CONFIG SET appendfsync always
redis-cli CONFIG GET appendfsync

# Test: CONFIG SET appendfsync everysec
redis-cli CONFIG SET appendfsync everysec
redis-cli CONFIG GET appendfsync

# Test: CONFIG SET appendfsync no
redis-cli CONFIG SET appendfsync no
redis-cli CONFIG GET appendfsync

# Reset to default
redis-cli CONFIG SET appendfsync everysec
```

**Expected output**:

```
1) "appendfsync"
2) "always"

1) "appendfsync"
2) "everysec"

1) "appendfsync"
2) "no"
```

### 1.3. Get AOF Rewrite Config

```bash
redis-cli CONFIG GET auto-aof-rewrite-percentage
redis-cli CONFIG GET auto-aof-rewrite-min-size
redis-cli CONFIG GET aof-use-rdb-preamble
redis-cli CONFIG GET no-appendfsync-on-rewrite
redis-cli CONFIG GET aof-incremental-fsync
```

**Expected output** (Redis 7 defaults):

```
1) "auto-aof-rewrite-percentage"
2) "100"

1) "auto-aof-rewrite-min-size"
2) "64mb"

1) "aof-use-rdb-preamble"
2) "yes"

1) "no-appendfsync-on-rewrite"
2) "no"

1) "aof-incremental-fsync"
2) "yes"
```

### 1.4. Measure fsync Policy Latency Impact with redis-cli

```bash
# Reset latency baseline (appendfsync no)
redis-cli CONFIG SET appendfsync no
redis-cli CONFIG SET appendonly yes
redis-cli FLUSHALL

# Write 1000 keys and measure time with appendfsync no
time redis-cli -c -p 6379 <<'EOF'
1000
SET warmup:x "value"
EOF

# Repeat with everysec
redis-cli CONFIG SET appendfsync everysec
time (for i in $(seq 1 1000); do redis-cli SET warmup:y:$i "value"); done

# Repeat with always
redis-cli CONFIG SET appendfsync always
time (for i in $(seq 1 100); do redis-cli SET warmup:z:$i "value"); done
```

**Expected** (approximate, hardware-dependent):

```
appendfsync no:     ~0.5-1s for 1000 commands
appendfsync everysec: ~1-2s for 1000 commands (periodic fsync overhead)
appendfsync always: ~5-15s for 100 commands (10-50x slower per command)
```

### 1.5. Trigger BGREWRITEAOF and Monitor Progress

```bash
# First, write enough data to make rewrite observable
for i in $(seq 1 5000); do redis-cli SET "warmup:key:$i" "value-$i"; done

# Check AOF file size before rewrite
redis-cli INFO persistence | grep aof_base_size
redis-cli INFO persistence | grep aof_incremental

# Trigger BGREWRITEAOF
redis-cli BGREWRITEAOF

# Poll until done
while true; do
  STATUS=$(redis-cli INFO persistence | grep aof_rewrite_in_progress | cut -d: -f2 | tr -d '\r')
  if [ "$STATUS" = "0" ]; then
    echo "BGREWRITEAOF complete"
    break
  fi
  DURATION=$(redis-cli INFO persistence | grep aof_current_rewrite_time_sec | cut -d: -f2 | tr -d '\r')
  echo "Rewrite in progress... ${DURATION}s elapsed"
  sleep 2
done

# Check result
redis-cli INFO persistence | grep aof_last_bgrewrite_status
redis-cli INFO persistence | grep aof_last_rewrite_time_sec
redis-cli INFO persistence | grep latest_fork_usec
```

**Expected output**:

```
Background append only file rewriting started
Rewrite in progress... 1s elapsed
Rewrite in progress... 2s elapsed
BGREWRITEAOF complete
aof_last_bgrewrite_status:ok
aof_last_rewrite_time_sec:2-5   (varies by data size)
latest_fork_usec:100-500μs     (small dataset)
```

---

## 2. Hands-on Lab (60–70 phút)

### Setup: TypeScript Project with ioredis

**File**: `package.json`

```json
{
  "name": "day7-aof-lab",
  "type": "module",
  "scripts": {
    "benchmark": "tsx src/benchmark-fsync.ts",
    "monitor": "tsx src/monitor-rewrite.ts",
    "check-aof": "tsx src/check-aof-size.ts"
  },
  "dependencies": {
    "ioredis": "^5.3.2"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "tsx": "^4.7.0",
    "typescript": "^5.3.3"
  }
}
```

**File**: `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "esModuleInterop": true,
    "strict": true,
    "outDir": "dist"
  },
  "include": ["src"]
}
```

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis-aof:
    image: redis:7-alpine
    container_name: redis-aof-day7
    command: >
      redis-server
      --save ""
      --appendonly yes
      --appendfsync everysec
      --aof-use-rdb-preamble yes
      --aof-load-truncated yes
      --auto-aof-rewrite-percentage 100
      --auto-aof-rewrite-min-size 64mb
      --aof-incremental-fsync yes
      --loglevel notice
    volumes:
      - aof-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  aof-data:
```

Start environment:

```bash
docker compose up -d
npm install
```

### Step 1: Write 50K Keys to Create Observable AOF File (5–10 phút)

**File**: `src/setup-data.ts`

```typescript
import Redis from 'ioredis';

async function main() {
  const redis = new Redis({ host: 'localhost', port: 6379, maxRetriesPerRequest: null });

  // Wait for Redis
  await redis.ping();
  console.log('Connected to Redis');

  // Enable AOF
  await redis.config('SET', 'appendonly', 'yes');
  await redis.config('SET', 'appendfsync', 'everysec');
  console.log('AOF enabled: everysec');

  // Write 50K keys using pipeline (efficient)
  const TOTAL_KEYS = 50_000;
  const BATCH = 1000;
  const value = 'x'.repeat(200); // ~200 bytes per value

  console.log(`Writing ${TOTAL_KEYS} keys...`);
  const start = Date.now();

  for (let batch = 0; batch < TOTAL_KEYS / BATCH; batch++) {
    const pipe = redis.pipeline();
    for (let i = 0; i < BATCH; i++) {
      const keyNum = batch * BATCH + i;
      pipe.set(`lab:key:${String(keyNum).padStart(8, '0')}`, `${value}`);
    }
    await pipe.exec();
    if (batch % 10 === 0) {
      process.stdout.write(`  ${batch * BATCH}/${TOTAL_KEYS} keys written\r`);
    }
  }

  const elapsed = (Date.now() - start) / 1000;
  console.log(`\nDone: ${TOTAL_KEYS} keys in ${elapsed.toFixed(1)}s`);

  // Check AOF file size
  const info = await redis.info('memory');
  const lines = info.split('\n');
  const usedMem = lines.find(l => l.startsWith('used_memory_human:'))?.split(':')[1] ?? 'N/A';
  console.log(`Memory used: ${usedMem}`);

  redis.disconnect();
}

main().catch(err => { console.error(err); process.exit(1); });
```

**Run**:

```bash
npx tsx src/setup-data.ts
```

**Expected output** (approximate):

```
Connected to Redis
AOF enabled: everysec
Writing 50000 keys...
  10000/50000 keys written
  ...
Done: 50000 keys in 3-8s
Memory used: ~15-20MB
```

### Step 2: Trigger BGREWRITEAOF và Observe Fork Latency (10–15 phút)

**File**: `src/monitor-rewrite.ts`

```typescript
import Redis from 'ioredis';

interface PersistenceInfo {
  aofRewriteInProgress: boolean;
  aofRewriteScheduled: boolean;
  aofCurrentRewriteTimeSec: number;
  aofLastRewriteTimeSec: number;
  aofLastBgrewriteStatus: string;
  aofDelayedFsync: number;
  latestForkUsec: number;
  aofLastWriteStatus: string;
  aofEnabled: boolean;
}

function parseInfo(text: string): PersistenceInfo {
  const p: PersistenceInfo = {
    aofRewriteInProgress: false,
    aofRewriteScheduled: false,
    aofCurrentRewriteTimeSec: 0,
    aofLastRewriteTimeSec: 0,
    aofLastBgrewriteStatus: '',
    aofDelayedFsync: 0,
    latestForkUsec: 0,
    aofLastWriteStatus: '',
    aofEnabled: false,
  };

  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const colon = trimmed.indexOf(':');
    if (colon === -1) continue;
    const key = trimmed.slice(0, colon).trim();
    const val = trimmed.slice(colon + 1).trim();

    switch (key) {
      case 'aof_enabled':             p.aofEnabled = val === '1'; break;
      case 'aof_rewrite_in_progress':  p.aofRewriteInProgress = val === '1'; break;
      case 'aof_rewrite_scheduled':    p.aofRewriteScheduled = val === '1'; break;
      case 'aof_current_rewrite_time_sec': p.aofCurrentRewriteTimeSec = parseInt(val) || 0; break;
      case 'aof_last_rewrite_time_sec':    p.aofLastRewriteTimeSec = parseInt(val) || 0; break;
      case 'aof_last_bgrewrite_status': p.aofLastBgrewriteStatus = val; break;
      case 'aof_delayed_fsync':        p.aofDelayedFsync = parseInt(val) || 0; break;
      case 'latest_fork_usec':         p.latestForkUsec = parseInt(val) || 0; break;
      case 'aof_last_write_status':    p.aofLastWriteStatus = val; break;
    }
  }
  return p;
}

async function getInfo(redis: Redis): Promise<PersistenceInfo> {
  return parseInfo(await redis.info('persistence'));
}

async function main() {
  const redis = new Redis({ host: 'localhost', port: 6379, maxRetriesPerRequest: null });

  await redis.ping();
  console.log('Connected. Triggering BGREWRITEAOF...\n');

  // Trigger rewrite
  const result = await redis.bgrewriteaof();
  console.log('BGREWRITEAOF started:', result);

  const beforeInfo = await getInfo(redis);
  console.log(`Fork triggered | latest_fork_usec: ${beforeInfo.latestForkUsec}μs (${(beforeInfo.latestForkUsec / 1000).toFixed(1)}ms)\n`);

  // Monitor while rewrite runs
  let lastElapsed = 0;
  process.stdout.write('Monitoring rewrite:\n');
  while (true) {
    const info = await getInfo(redis);

    if (!info.aofRewriteInProgress) {
      console.log('\nRewrite complete!');
      console.log(`  aof_last_bgrewrite_status: ${info.aofLastBgrewriteStatus}`);
      console.log(`  aof_last_rewrite_time_sec: ${info.aofLastRewriteTimeSec}s`);
      console.log(`  latest_fork_usec: ${info.latestForkUsec}μs (${(info.latestForkUsec / 1000).toFixed(1)}ms)`);
      console.log(`  aof_delayed_fsync: ${info.aofDelayedFsync}`);
      console.log(`  aof_last_write_status: ${info.aofLastWriteStatus}`);
      break;
    }

    if (info.aofCurrentRewriteTimeSec !== lastElapsed) {
      lastElapsed = info.aofCurrentRewriteTimeSec;
      console.log(`  t=${lastElapsed}s | fork: ${info.latestForkUsec}μs | delayed_fsync: ${info.aofDelayedFsync}`);
    }

    await new Promise(resolve => setTimeout(resolve, 250));
  }

  redis.disconnect();
}

main().catch(err => { console.error(err); process.exit(1); });
```

**Run**:

```bash
npx tsx src/monitor-rewrite.ts
```

**Expected output** (small dataset):

```
Connected. Triggering BGREWRITEAOF...
BGREWRITEAOF started: Background append only file rewriting started

Fork triggered | latest_fork_usec: 150μs (0.2ms)

Monitoring rewrite:
  t=1s | fork: 150μs | delayed_fsync: 0
  t=2s | fork: 150μs | delayed_fsync: 0

Rewrite complete!
  aof_last_bgrewrite_status: ok
  aof_last_rewrite_time_sec: 2s
  latest_fork_usec: 150μs (0.2ms)
  aof_delayed_fsync: 0
  aof_last_write_status: ok
```

### Step 3: Benchmark Write Latency Across fsync Policies (20–25 phút)

**File**: `src/benchmark-fsync.ts`

```typescript
import Redis from 'ioredis';
import * as fs from 'fs';

interface LatencyResult {
  policy: string;
  p50: number;
  p95: number;
  p99: number;
  opsPerSec: number;
  totalMs: number;
}

function percentile(sorted: number[], p: number): number {
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

function computePercentiles(lats: number[]): { p50: number; p95: number; p99: number } {
  const sorted = [...lats].sort((a, b) => a - b);
  return {
    p50: parseFloat(percentile(sorted, 50).toFixed(3)),
    p95: parseFloat(percentile(sorted, 95).toFixed(3)),
    p99: parseFloat(percentile(sorted, 99).toFixed(3)),
  };
}

async function benchmarkPolicy(
  redis: Redis,
  policy: string,
  commandCount = 10_000,
): Promise<LatencyResult> {
  await redis.config('SET', 'appendfsync', policy);
  await new Promise(r => setTimeout(r, 500)); // Let config settle

  const lats: number[] = [];
  const value = 'x'.repeat(1024); // 1KB

  // Warm up
  for (let i = 0; i < 100; i++) {
    await redis.set(`warmup:${i}`, value);
  }

  // Measure
  for (let i = 0; i < commandCount; i++) {
    const key = `bench:${policy}:${i}`;
    const t0 = process.hrtime.bigint();
    await redis.set(key, value);
    const ns = Number(process.hrtime.bigint() - t0);
    lats.push(ns / 1_000_000); // ms
  }

  // Throughput via pipeline
  const pipeStart = process.hrtime.bigint();
  const pipe = redis.pipeline();
  for (let i = 0; i < commandCount; i++) {
    pipe.set(`pipe:${policy}:${i}`, value);
  }
  await pipe.exec();
  const pipeMs = Number(process.hrtime.bigint() - pipeStart) / 1_000_000;
  const opsPerSec = Math.round((commandCount * 1000) / pipeMs);

  const { p50, p95, p99 } = computePercentiles(lats);

  return { policy, p50, p95, p99, opsPerSec, totalMs: pipeMs };
}

async function main() {
  const redis = new Redis({
    host: 'localhost',
    port: 6379,
    maxRetriesPerRequest: 3,
    connectTimeout: 10_000,
  });

  await redis.ping();
  await redis.config('SET', 'appendonly', 'yes');

  console.log('=== AOF fsync Policy Benchmark ===\n');
  console.log(`Commands per policy: 10,000 SET (1KB value)\n`);

  const policies = ['no', 'everysec', 'always'];
  const results: LatencyResult[] = [];

  for (const policy of policies) {
    console.log(`Benchmarking appendfsync ${policy}...`);
    const result = await benchmarkPolicy(redis, policy);
    results.push(result);
    console.log(`  p50: ${result.p50}ms | p95: ${result.p95}ms | p99: ${result.p99}ms | throughput: ${result.opsPerSec} ops/sec`);
    console.log(`  (pipeline ${result.totalMs.toFixed(1)}ms for 10K commands)\n`);

    // Let fsync settle before next benchmark
    await new Promise(r => setTimeout(r, 3000));
  }

  // Write results to CSV
  const csvHeader = 'policy,p50_ms,p95_ms,p99_ms,ops_per_sec\n';
  const csvRows = results
    .map(r => `${r.policy},${r.p50},${r.p95},${r.p99},${r.opsPerSec}`)
    .join('\n');
  fs.writeFileSync('benchmark-fsync-results.csv', csvHeader + csvRows);
  console.log('Results written to benchmark-fsync-results.csv\n');

  // Summary table
  console.log('=== Summary Table ===');
  console.table(results);

  // Restore default
  await redis.config('SET', 'appendfsync', 'everysec');
  redis.disconnect();
}

main().catch(err => { console.error(err); process.exit(1); });
```

**Run**:

```bash
npx tsx src/benchmark-fsync.ts
```

**Expected output** (NVMe SSD, hardware-dependent):

```
=== AOF fsync Policy Benchmark ===

Commands per policy: 10,000 SET (1KB value)

Benchmarking appendfsync no...
  p50: 0.15ms | p95: 0.8ms | p99: 1.5ms | throughput: 145000 ops/sec
  (pipeline 68.9ms for 10K commands)

Benchmarking appendfsync everysec...
  p50: 0.18ms | p95: 2.1ms | p99: 4.8ms | throughput: 118000 ops/sec
  (pipeline 84.7ms for 10K commands)

Benchmarking appendfsync always...
  p50: 2.3ms | p95: 8.5ms | p99: 18.2ms | throughput: 35000 ops/sec
  (pipeline 285.7ms for 10K commands)

Results written to benchmark-fsync-results.csv
```

### Step 4: Observe Latency Spike During BGREWRITEAOF (10–15 phút)

**File**: `src/rewrite-latency-spike.ts`

```typescript
import Redis from 'ioredis';

async function main() {
  const redis = new Redis({
    host: 'localhost',
    port: 6379,
    maxRetriesPerRequest: 3,
    enableOfflineQueue: false,
  });

  await redis.ping();
  await redis.config('SET', 'appendonly', 'yes');
  await redis.config('SET', 'appendfsync', 'everysec');

  console.log('=== Latency Spike During BGREWRITEAOF ===\n');

  // Baseline: measure p50/p95 without rewrite
  const baseline: number[] = [];
  const value = 'x'.repeat(500);

  console.log('Collecting baseline (no rewrite)...');
  for (let i = 0; i < 1000; i++) {
    const t0 = process.hrtime.bigint();
    await redis.set(`base:${i}`, value);
    baseline.push(Number(process.hrtime.bigint() - t0) / 1_000_000);
  }
  baseline.sort((a, b) => a - b);
  console.log(`  Baseline p50: ${baseline[500].toFixed(3)}ms | p95: ${baseline[950].toFixed(3)}ms | p99: ${baseline[990].toFixed(3)}ms\n`);

  // Trigger BGREWRITEAOF in background
  console.log('Triggering BGREWRITEAOF (background)...');
  await redis.bgrewriteaof();

  // Measure latency while rewrite is running
  const duringRewrite: number[] = [];
  console.log('Measuring latency DURING rewrite...');
  let samples = 0;
  const MAX_SAMPLES = 2000;

  while (samples < MAX_SAMPLES) {
    const t0 = process.hrtime.bigint();
    await redis.set(`during:${samples}`, value);
    duringRewrite.push(Number(process.hrtime.bigint() - t0) / 1_000_000);
    samples++;
  }

  duringRewrite.sort((a, b) => a - b);
  console.log(`\nDuring Rewrite p50: ${duringRewrite[1000].toFixed(3)}ms | p95: ${duringRewrite[1900].toFixed(3)}ms | p99: ${duringRewrite[1990].toFixed(3)}ms`);

  const baselineP95 = baseline[950];
  const duringP95 = duringRewrite[1900];
  const spike = duringP95 / baselineP95;
  console.log(`\nLatency spike ratio (p95): ${spike.toFixed(2)}x`);
  console.log(`(Baseline p95: ${baselineP95.toFixed(3)}ms → During rewrite p95: ${duringP95.toFixed(3)}ms)`);

  // Wait for rewrite to complete
  let count = 0;
  while (count < 60) {
    const info = await redis.info('persistence');
    if (!info.includes('aof_rewrite_in_progress:1')) {
      console.log('\nRewrite complete!');
      break;
    }
    await new Promise(r => setTimeout(r, 500));
    count++;
  }

  redis.disconnect();
}

main().catch(err => { console.error(err); process.exit(1); });
```

**Run**:

```bash
npx tsx src/rewrite-latency-spike.ts
```

**Expected output** (approximate):

```
=== Latency Spike During BGREWRITEAOF ===

Collecting baseline (no rewrite)...
  Baseline p50: 0.18ms | p95: 0.8ms | p99: 1.5ms

Triggering BGREWRITEAOF (background)...
Measuring latency DURING rewrite...

During Rewrite p50: 0.22ms | p95: 1.8ms | p99: 5.2ms

Latency spike ratio (p95): 2.25x
(Baseline p95: 0.800ms → During rewrite p95: 1.800ms)

Rewrite complete!
```

---

## 3. Challenge Exercise (30–40 phút)

### Scenario A: Real-time Analytics Cache (100K ops/sec, accept 5-minute data loss)

**Context**: Bạn thiết kế Redis cho real-time analytics dashboard cache. Dataset: 50GB. Traffic: 100K ops/sec (95% reads, 5% writes). Cold start: có cache warmer chạy từ PostgreSQL. Data loss acceptable: 5 phút. Write latency requirement: < 5ms p99.

**Task**: Đề xuất persistence config hoàn chỉnh. Trả lời:

1. Nên dùng `appendfsync` nào? Tại sao?
2. Nên dùng RDB, AOF, hybrid, hay không persistence?
3. Tính COW overhead khi BGSAVE chạy trên 50GB dataset
4. Đề xuất `auto-aof-rewrite-percentage` và `auto-aof-rewrite-min-size` nếu dùng AOF
5. Đề xuất monitoring metrics và alert thresholds
6. Benchmark thực tế: trigger BGSAVE và đo `latest_fork_usec`

**Hint**: Với 50GB dataset, fork time ~500ms-2s. COW = write_rate × avg_write_size × rewrite_duration. Tính memory headroom cần thiết.

---

### Scenario B: E-commerce Session Store (10M sessions, 1s data loss max)

**Context**: Bạn thiết kế Redis cho e-commerce session store. Dataset: 10GB. Sessions: 10 triệu active sessions. Mỗi session có shopping cart (user-generated state). SLA: restart < 30 giây. Acceptable data loss: 1 giây. Write rate: 5K/sec.

**Task**:

1. Đề xuất config: fsync policy, RDB save interval, AOF rewrite knobs
2. Tính toán restart time cho hybrid config
3. Simulate crash: `docker kill --signal=9 redis-aof-day7`, restart, đo `aof_last_load_duration_ms`
4. Tính worst-case data loss nếu crash ngay trước khi fsync chạy
5. Tính disk space cần thiết (RDB + AOF)

**Docker commands for simulation**:

```bash
# Write session data first
docker exec redis-aof-day7 redis-cli DBSIZE

# Crash simulation
docker kill --signal=9 redis-aof-day7

# Check what was written to AOF
docker run --rm -v aof-data:/data redis:7-alpine ls -la /data/appendonlydir/

# Restart
docker compose up -d
sleep 3

# Check load time
docker exec redis-aof-day7 redis-cli INFO persistence | grep aof_last_load_duration
docker exec redis-aof-day7 redis-cli DBSIZE
```

---

### Scenario C: Payment Idempotency Store (5K ops/sec, near-zero data loss)

**Context**: Bạn thiết kế Redis cho payment API idempotency key storage. Dataset: 5GB. Ops: 5K/sec, mỗi operation là SET idempotency_token. Không acceptable data loss cho token. Redis không phải primary store (PostgreSQL có idempotency_token unique constraint).

**Task**:

1. Đề xuất config với justification từng tham số
2. Explain tại sao `appendfsync always` không đủ để gọi Redis là "durable store"
3. Đề xuất layered durability architecture (Redis + PostgreSQL)
4. Tính throughput impact của `appendfsync always` trên NVMe SSD vs SATA SSD
5. Tính memory overhead của BGREWRITEAOF trên 5GB dataset
6. Viết monitoring runbook cho `aof_delayed_fsync`

---

## 4. Reflection Questions

### Question 1: Tại sao `appendfsync always` không đồng nghĩa với "zero data loss"?

Trả lời ngắn: Liệt kê tất cả layers mà data có thể bị mất ngay cả khi Redis gọi `fsync()` sau mỗi write.

### Question 2: AOF rewrite frequency — aggressive hay conservative?

Khi nào nên rewrite thường xuyên (percentage thấp)? Khi nào nên rewrite ít (percentage cao)? Trade-off cụ thể là gì?

### Question 3: Multi-Part AOF (Redis 7+) thay đổi cách vận hành như thế nào?

Điều gì cần thay đổi trong Docker/Kubernetes config khi dùng Redis 7+? Tại sao?

### Question 4: Layered durability — khi nào và tại sao?

Khi nào bạn cần Redis + PostgreSQL cho idempotency? Khi nào Redis + replication là đủ? Khi nào Redis-only là acceptable?

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1** — `aof_enabled:1` sau khi enable. `aof_rewrite_in_progress:0` = no rewrite running.

**1.2** — `CONFIG SET appendfsync always` có thể làm Redis log cảnh báo nếu fsync quá chậm. Luôn reset về `everysec` sau test.

**1.3** — Redis 7 default: `aof-use-rdb-preamble yes`, `aof-incremental-fsync yes`, `auto-aof-rewrite-percentage 100`, `auto-aof-rewrite-min-size 64mb`.

**1.4** — `appendfsync always` chậm hơn `no` khoảng 10-50x per command. Đây là lý do chỉ dùng `always` khi cần thiết.

**1.5** — `BGREWRITEAOF` là non-blocking, fork child process. `aof_rewrite_in_progress` = 0 khi hoàn thành. Check `aof_last_bgrewrite_status` = "ok".

### Challenge Solutions

**Scenario A (Analytics Cache)**:

```txt
save "300 1"           # RDB snapshot mỗi 5 phút (acceptable: 5 phút data loss)
appendonly no           # Không cần AOF (write latency requirement <5ms p99)
                        # 100K ops/sec write rate → AOF overhead không acceptable
maxmemory 55gb
maxmemory-policy allkeys-lru
```

Justification:
- 100K ops/sec + 1KB avg = ~100MB/s write rate → AOF overhead rất lớn
- `appendfsync always`: p99 ~50ms+ → violate <5ms requirement
- `appendfsync everysec`: ~2-5ms p99 → acceptable
- RDB only = acceptable vì 5 phút loss OK và cache warmer có sẵn

COW calculation:
- 50GB dataset → fork ~500ms-2s
- COW = write_rate × avg_size × rewrite_duration
- = 100K/sec × 200B × 300s = 6GB COW peak
- Memory needed: 50GB + 6GB = 56GB → use 64GB instance

Monitoring:
- `rdb_changes_since_last_save` > 5_000_000 → alert
- `latest_fork_usec` > 2_000_000 → alert
- Disk usage < 20% remaining → alert

**Scenario B (Session Store)**:

```txt
save 300 1 60 10000    # Snapshot: every 5 min OR 10K changes in 1 min
appendonly yes
appendfsync everysec   # ~1s loss acceptable
aof-use-rdb-preamble yes
aof-load-truncated yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Restart time calculation (10GB dataset):
# RDB load: 10GB / 500MB/s NVMe = ~20s
# AOF tail replay: worst case ~1s (everysec, max 1s commands)
# Total: ~21-25s < 30s SLA ✓

# Disk space:
# RDB: ~10GB (binary)
# AOF: ~15-30GB (RESP verbosity, depends on write rate)
# Total: ~25-40GB
```

Crash simulation result:
- `aof_last_load_duration_ms`: thường < 500ms cho small dataset
- Key count sau crash: gần như 100% (mất ~1s = ~5K keys)
- `aof_delayed_fsync` > 0 = disk không kịp → upgrade disk

**Scenario C (Idempotency Store)**:

```txt
save 900 1             # RDB backup 15 phút
appendonly yes
appendfsync always     # ONLY trên dedicated NVMe với PLP
aof-use-rdb-preamble yes
aof-load-truncated yes
auto-aof-rewrite-percentage 200
auto-aof-rewrite-min-size 256mb

# HARD TRUTH: appendfsync always != zero data loss
# Gap: kernel page cache flush, disk controller cache, disk firmware bug
# Fix: PostgreSQL unique constraint = true idempotency guarantee

# Throughput on always:
# NVMe: 5K ops/sec (required) vs 100K ops/sec capacity → OK ✓
# SATA SSD: p99 ~50ms → 5K ops/sec → 250s delay → timeout → cascade
# → ONLY use always on NVMe
```

Layered durability architecture:
```
Payment Request (idempotency_token)
  ├─→ Redis SETNX idempotency_token "processing" (fast path)
  │    └─→ appendfsync always (NVMe)
  │
  └─→ PostgreSQL INSERT idempotency_token (unique constraint) (durable path)
       └─→ WAL + fsync = true durability

On crash during processing:
  Redis: token may be lost (if NVMe fails) → PostgreSQL prevents double-charge
  Redis: token survives → normal recovery

Result: no double-charge, even if Redis loses data
```

Memory overhead BGREWRITEAOF on 5GB:
- Fork: ~100-300ms
- COW: 5K/sec × 200B × 10s (rewrite) = 10MB
- Rewrite buffer: ~5MB (5s × 5K × 200B)
- Child process: ~5GB (reads via pipe)
- Peak: ~10GB (parent + child temporarily)
- Recommendation: use 10GB+ instance with 50% headroom

Monitoring runbook for `aof_delayed_fsync`:
```
# aof_delayed_fsync > 0 in any 5-minute window = disk can't keep up
# Immediate actions:
#   1. Check disk I/O: iostat -x 1
#   2. Check if BGSAVE/AOF rewrite running simultaneously
#   3. Move AOF to dedicated disk
#   4. Escalate if sustained > 10
```

### Reflection Solutions

**Q1**: `fsync()` đảm bảo data flush từ kernel page cache đến disk controller cache. Nhưng:
- Disk controller cache (DRAM) mất data trên power loss (nếu không có BBU/PLP)
- Rare disk firmware bugs có thể corrupt data
- Kernel bug có thể cause data loss even with fsync
- Redis crash sau `write()` nhưng trước `fsync()` = data loss

**Q2**: Aggressive rewrite (percentage=50) khi dataset lớn (50GB+) và disk fast (NVMe). Conservative (percentage=200) khi fork overhead cao hoặc disk chậm. Luôn set `auto-aof-rewrite-min-size` phù hợp.

**Q3**: Redis 7+ dùng `appendonlydir/` directory thay vì single file. Docker volume mount phải mount `/data` directory, không mount file cụ thể. `appendfilename` bị ignore khi `appenddirname` set.

**Q4**: Redis + PostgreSQL khi: idempotency token, financial data, permanent records. Redis + replication khi: session store, job queue (acceptable ~1s loss). Redis-only khi: pure cache, rate limiter, ephemeral data.
