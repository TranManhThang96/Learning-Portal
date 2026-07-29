# Day 11: Pipelining & Batching — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: TypeScript (ioredis)
**Docker images**: redis:7-alpine, node:20-alpine

---

## 1. Warm-up Exercises (15–20 phút)

### 1.1. redis-cli --pipe Mode

Gửi 100 `PING` commands qua `--pipe`:

```bash
# Method 1: raw RESP pipeline
for i in $(seq 1 100); do
    printf "*1\r\n\$4\r\nPING\r\n"
done | redis-cli --pipe-timeout 5

# Method 2: printf raw RESP ngắn (có thể thấy rõ RESP serialization)
printf "*1\r\n\$4\r\nPING\r\n*1\r\n\$4\r\nPING\r\n*1\r\n\$4\r\nPING\r\n" | redis-cli --pipe

# Method 3: xargs (sequential, non-pipeline)
seq 1 100 | xargs -I{} redis-cli PING
```

**Expected output** (method 1):
```txt
Warning: Using a password with '-a' or '--pass' option on the command line interface may not be safe.
100
100 commands sent.
```

**Expected output** (method 3 — sequential, chậm hơn):
```txt
PONG
PONG
... (100 lines)
```

So sánh thời gian method 1 vs method 3. Method 1 nhanh hơn bao nhiêu lần?

### 1.2. MGET vs N GET (Sequential)

```bash
# Setup: tạo 50 keys
for i in $(seq 1 50); do
    redis-cli SET "warmup:key:$i" "value-$i"
done

# Non-pipeline: 50 GET riêng lẻ
time (for i in $(seq 1 50); do redis-cli GET "warmup:key:$i" > /dev/null; done)

# MGET batch: 1 command với 50 keys
time redis-cli MGET warmup:key:1 warmup:key:2 warmup:key:3 warmup:key:4 warmup:key:5 warmup:key:6 warmup:key:7 warmup:key:8 warmup:key:9 warmup:key:10 warmup:key:11 warmup:key:12 warmup:key:13 warmup:key:14 warmup:key:15 warmup:key:16 warmup:key:17 warmup:key:18 warmup:key:19 warmup:key:20 warmup:key:21 warmup:key:22 warmup:key:23 warmup:key:24 warmup:key:25 warmup:key:26 warmup:key:27 warmup:key:28 warmup:key:29 warmup:key:30 warmup:key:31 warmup:key:32 warmup:key:33 warmup:key:34 warmup:key:35 warmup:key:36 warmup:key:37 warmup:key:38 warmup:key:39 warmup:key:40 warmup:key:41 warmup:key:42 warmup:key:43 warmup:key:44 warmup:key:45 warmup:key:46 warmup:key:47 warmup:key:48 warmup:key:49 warmup:key:50
```

**Expected**: MGET nhanh hơn ~50 lần (1 RTT thay vì 50 RTT).

### 1.3. Inspect INFO commandstats

Sau khi chạy các benchmark, kiểm tra command statistics:

```bash
redis-cli INFO commandstats | grep -E "cmdstat_get|cmdstat_mget|cmdstat_set|cmdstat_pipeline"
```

**Expected output** (sau benchmark):
```txt
cmdstat_get:calls=150,usec=450,usec_per_call=3.00
cmdstat_mget:calls=1,usec=15,usec_per_call=15.00
cmdstat_set:calls=50,usec=250,usec_per_call=5.00
```

Chú ý: `usec_per_call` của MGET cao hơn GET đơn lẻ (vì phải scan nhiều keys) nhưng **tổng thời gian** cho 50 keys = 15μs vs 50 × 3μs = 150μs.

### 1.4. Pipeline Raw RESP — Manual Construction

```bash
# Gửi 3 SET commands bằng raw RESP
# RESP format: *3\r\n$3\r\nSET\r\n$keylen\r\nkey\r\n$valuelen\r\nvalue\r\n

printf "*3\r\n\$3\r\nSET\r\n\$8\r\nraw:key1\r\n\$6\r\nvalue1\r\n*3\r\n\$3\r\nSET\r\n\$8\r\nraw:key2\r\n\$6\r\nvalue2\r\n*3\r\n\$3\r\nSET\r\n\$8\r\nraw:key3\r\n\$6\r\nvalue3\r\n" | redis-cli --pipe

# Verify
redis-cli MGET raw:key1 raw:key2 raw:key3
```

**Expected output**:
```txt
1) "value1"
2) "value2"
3) "value3"
```

---

## 2. Hands-on Lab (60–70 phút)

### Setup: Docker Compose

**File**: `docker-compose.yml`

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    container_name: redis-pipeline
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-wan:
    # Simulate WAN Redis: dùng tc (traffic control) để simulate RTT
    image: redis:7-alpine
    container_name: redis-wan
    ports:
      - "6380:6379"
    cap_add:
      - NET_ADMIN
    command: >
      sh -c "apk add --no-cache iproute2 >/dev/null &&
             tc qdisc add dev eth0 root netem delay 50ms &&
             redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru"
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

```bash
docker compose -f docker-compose.yml up -d
docker exec redis-pipeline redis-cli PING
docker exec redis-wan redis-cli PING
```

### TypeScript Project Setup

```bash
mkdir -p pipeline-lab && cd pipeline-lab
npm init -y
npm install ioredis typescript tsx @types/node
npx tsc --init --target ES2020 --module NodeNext --moduleResolution NodeNext --strict
```

**File**: `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

**File**: `src/setup.ts`

```typescript
import Redis from 'ioredis';

export const redisLAN = new Redis({
    host: 'localhost',
    port: 6379,
    lazyConnect: true,
    maxRetriesPerRequest: 3,
});

export const redisWAN = new Redis({
    host: 'localhost',
    port: 6380,
    lazyConnect: true,
    maxRetriesPerRequest: 3,
});

export async function connectClients() {
    await redisLAN.connect();
    await redisWAN.connect();
    console.log('Connected to Redis (LAN + WAN)');
}

export async function cleanup() {
    const keys = await redisLAN.keys('bench:*');
    if (keys.length > 0) {
        await redisLAN.del(...keys);
    }
    const wanKeys = await redisWAN.keys('bench:*');
    if (wanKeys.length > 0) {
        await redisWAN.del(...wanKeys);
    }
    await redisLAN.quit();
    await redisWAN.quit();
}
```

### Starter Code: Benchmark Pipeline

**File**: `src/benchmark.ts`

```typescript
import Redis from 'ioredis';
import { redisLAN, redisWAN, cleanup, connectClients } from './setup';

interface BenchmarkResult {
    totalOps: number;
    durationMs: number;
    opsPerSec: number;
    p50: number;
    p95: number;
    p99: number;
}

/**
 * Benchmark non-pipeline (sequential) GET operations.
 * Records per-operation latency for percentile calculation.
 */
async function benchmarkNonPipeline(
    redis: InstanceType<typeof Redis>,
    keyCount: number,
    prefix: string = 'bench'
): Promise<BenchmarkResult> {
    const latencies: number[] = [];

    const start = Date.now();
    for (let i = 0; i < keyCount; i++) {
        const t0 = Date.now();
        await redis.get(`${prefix}:key:${i}`);
        latencies.push(Date.now() - t0);
    }
    const durationMs = Date.now() - start;

    return {
        totalOps: keyCount,
        durationMs,
        opsPerSec: Math.round((keyCount / durationMs) * 1000),
        p50: percentile(latencies, 0.5),
        p95: percentile(latencies, 0.95),
        p99: percentile(latencies, 0.99),
    };
}

/**
 * Benchmark pipeline GET operations.
 * Measures total time and calculates theoretical ops/sec.
 */
export async function benchmarkPipeline(
    redis: InstanceType<typeof Redis>,
    keyCount: number,
    batchSize: number,
    prefix: string = 'bench'
): Promise<BenchmarkResult> {
    const start = Date.now();

    let totalOps = 0;
    let pipe = redis.pipeline();

    for (let i = 0; i < keyCount; i++) {
        pipe.get(`${prefix}:key:${i}`);

        if ((i + 1) % batchSize === 0) {
            await pipe.exec();
            totalOps += batchSize;
            pipe = redis.pipeline();
        }
    }

    // Flush remaining
    if ((keyCount % batchSize) !== 0) {
        const remainder = keyCount % batchSize;
        await pipe.exec();
        totalOps += remainder;
    } else {
        totalOps = keyCount;
    }

    const durationMs = Date.now() - start;

    return {
        totalOps,
        durationMs,
        opsPerSec: Math.round((totalOps / durationMs) * 1000),
        p50: 0, // pipeline không measure per-op latency
        p95: 0,
        p99: 0,
    };
}

/**
 * Benchmark pipeline SET operations với batch size.
 */
export async function benchmarkPipelineWrite(
    redis: InstanceType<typeof Redis>,
    keyCount: number,
    batchSize: number,
    prefix: string = 'bench'
): Promise<BenchmarkResult> {
    const start = Date.now();

    let totalOps = 0;
    let pipe = redis.pipeline();

    for (let i = 0; i < keyCount; i++) {
        pipe.set(`${prefix}:key:${i}`, `value-${i}`);

        if ((i + 1) % batchSize === 0) {
            await pipe.exec();
            totalOps += batchSize;
            pipe = redis.pipeline();
        }
    }

    if ((keyCount % batchSize) !== 0) {
        await pipe.exec();
        totalOps += keyCount % batchSize;
    } else {
        totalOps = keyCount;
    }

    const durationMs = Date.now() - start;

    return {
        totalOps,
        durationMs,
        opsPerSec: Math.round((totalOps / durationMs) * 1000),
        p50: 0,
        p95: 0,
        p99: 0,
    };
}

function percentile(arr: number[], p: number): number {
    const sorted = [...arr].sort((a, b) => a - b);
    const index = Math.ceil(p * sorted.length) - 1;
    return sorted[Math.max(0, index)];
}

function printResult(label: string, result: BenchmarkResult) {
    console.log(`\n${label}`);
    console.log(`  Ops: ${result.totalOps} | Time: ${result.durationMs}ms | Ops/sec: ${result.opsPerSec}`);
    if (result.p50 > 0) {
        console.log(`  Latency: p50=${result.p50}ms | p95=${result.p95}ms | p99=${result.p99}ms`);
    }
}

// ==================== LAB STEPS ====================

async function main() {
    await connectClients();

    const KEY_COUNT = 10_000;

    console.log(`\n=== LAB Day 11: Pipelining & Batching ===`);
    console.log(`Keys: ${KEY_COUNT} | Target: localhost:6379 (LAN) + :6380 (WAN 50ms)\n`);

    // Step 0: Setup data
    console.log('--- Step 0: Writing 10K SET keys (batch=1000) ---');
    await benchmarkPipelineWrite(redisLAN, KEY_COUNT, 1000, 'bench');
    await benchmarkPipelineWrite(redisWAN, 1000, 1000, 'bench');
    console.log('Setup complete.');

    // TODO: Implement Step 1-5 below

    await cleanup();
}

if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(async (err) => {
        console.error(err);
        await cleanup();
        process.exit(1);
    });
}
```

### Step 1: Benchmark Non-pipeline vs Pipeline (LAN)

Thêm vào `main()`:

```typescript
    // Step 1: Non-pipeline GET 10K
    console.log('\n--- Step 1: Non-pipeline GET 10K (LAN) ---');
    const nonPipeline = await benchmarkNonPipeline(redisLAN, KEY_COUNT, 'bench');
    printResult('Non-pipeline (10K sequential GET)', nonPipeline);

    // Step 2: Pipeline GET với batch size = 100
    console.log('\n--- Step 2: Pipeline GET batch=100 (LAN) ---');
    const pipeline100 = await benchmarkPipeline(redisLAN, KEY_COUNT, 100, 'bench');
    printResult('Pipeline batch=100', pipeline100);

    // Step 3: Pipeline GET với batch size = 1000
    console.log('\n--- Step 3: Pipeline GET batch=1000 (LAN) ---');
    const pipeline1000 = await benchmarkPipeline(redisLAN, KEY_COUNT, 1000, 'bench');
    printResult('Pipeline batch=1000', pipeline1000);
```

**Expected output** (LAN, approximate):

```txt
--- Step 1: Non-pipeline GET 10K (LAN) ---
Non-pipeline (10K sequential GET)
  Ops: 10000 | Time: ~5000ms | Ops/sec: ~2000
  Latency: p50=0ms | p95=8ms | p99=15ms

--- Step 2: Pipeline GET batch=100 (LAN) ---
Pipeline batch=100
  Ops: 10000 | Time: ~150ms | Ops/sec: ~66667
  Speedup: ~33x

--- Step 3: Pipeline GET batch=1000 (LAN) ---
Pipeline batch=1000
  Ops: 10000 | Time: ~80ms | Ops/sec: ~125000
  Speedup: ~62x
```

### Step 4: Benchmark Pipeline (WAN, 50ms RTT)

Thêm vào `main()`:

```typescript
    // Step 4: Non-pipeline GET 10K over WAN (50ms RTT)
    console.log('\n--- Step 4: Non-pipeline GET 10K (WAN 50ms RTT) ---');
    const nonPipelineWAN = await benchmarkNonPipeline(redisWAN, 1000, 'bench'); // use 1000 để test nhanh
    printResult('Non-pipeline (1000 sequential GET over WAN)', nonPipelineWAN);

    // Step 5: Pipeline GET over WAN
    console.log('\n--- Step 5: Pipeline GET batch=100 (WAN 50ms RTT) ---');
    const pipelineWAN100 = await benchmarkPipeline(redisWAN, 1000, 100, 'bench');
    printResult('Pipeline batch=100 (WAN)', pipelineWAN100);

    console.log('\n--- Step 6: Pipeline GET batch=1000 (WAN 50ms RTT) ---');
    const pipelineWAN1000 = await benchmarkPipeline(redisWAN, 1000, 1000, 'bench');
    printResult('Pipeline batch=1000 (WAN)', pipelineWAN1000);
```

**Expected output** (WAN, approximate):

```txt
--- Step 4: Non-pipeline (1000 sequential GET over WAN) ---
Non-pipeline (1000 sequential GET over WAN)
  Ops: 1000 | Time: ~50000ms | Ops/sec: ~20
  Latency: p50=50ms | p95=52ms | p99=55ms

--- Step 5: Pipeline batch=100 (WAN) ---
Pipeline batch=100
  Ops: 1000 | Time: ~500ms | Ops/sec: ~2000
  Speedup: 100x vs non-pipeline

--- Step 6: Pipeline batch=1000 (WAN) ---
Pipeline batch=1000
  Ops: 1000 | Time: ~50ms | Ops/sec: ~20000
  Speedup: 1000x vs non-pipeline
```

### Step 7: Batch Size vs Throughput Analysis

Thêm function mới vào `src/analysis.ts`:

```typescript
// File: src/analysis.ts
import { redisLAN, cleanup, connectClients } from './setup';
import { benchmarkPipeline } from './benchmark';

export async function batchSizeAnalysis() {
    const keyCount = 10_000;
    const batchSizes = [1, 10, 50, 100, 500, 1000, 2000, 5000, 10000];

    console.log('\n=== Batch Size Analysis (10K GET over LAN) ===');
    console.log('Batch Size | Time(ms) | Ops/sec | Throughput Gain vs batch=1');
    console.log('-----------+----------+---------+------------------------');

    // Write data
    let pipe = redisLAN.pipeline();
    for (let i = 0; i < keyCount; i++) {
        pipe.set(`bench:key:${i}`, `value-${i}`);
    }
    await pipe.exec();

    let baselineMs = 0;

    for (const batch of batchSizes) {
        const result = await benchmarkPipeline(redisLAN, keyCount, batch, 'bench');
        if (batch === 1) baselineMs = result.durationMs;

        const gain = baselineMs / result.durationMs;
        console.log(
            `${String(batch).padStart(10)} | ${String(result.durationMs).padStart(8)} | ` +
            `${String(result.opsPerSec).padStart(7)} | ${gain.toFixed(1)}x`
        );
    }

    await cleanup();
}

connectClients()
    .then(batchSizeAnalysis)
    .catch(async (err) => {
        console.error(err);
        await cleanup();
        process.exit(1);
    });
```

**Chạy**:

```bash
npx tsx src/analysis.ts
```

**Expected output**:

```txt
=== Batch Size Analysis (10K GET over LAN) ===
Batch Size | Time(ms) | Ops/sec | Throughput Gain vs batch=1
-----------+----------+---------+------------------------
         1 |     5000 |    2000 | 1.0x
        10 |      500 |   20000 | 10.0x
        50 |      105 |   95238 | 47.6x
       100 |       80 |  125000 | 62.5x
       500 |       30 |  333333 | 166.7x
      1000 |       25 |  400000 | 200.0x
      2000 |       23 |  434783 | 217.4x
      5000 |       22 |  454545 | 227.3x
     10000 |       21 |  476190 | 238.1x

Observation: Diminishing returns after batch=1000.
p99 latency sẽ spike nếu batch quá lớn (measure riêng nếu cần).
```

### Step 8: Error Handling trong Pipeline

Thêm function:

```typescript
// File: src/error-handling.ts
import { redisLAN, cleanup } from './setup';

export async function errorHandlingDemo() {
    // Setup: 1 key tồn tại, 1 key không phải integer
    await redisLAN.set('bench:counter', '0');
    await redisLAN.set('bench:string', 'hello');

    console.log('\n=== Pipeline Error Handling Demo ===');

    const pipe = redisLAN.pipeline();
    pipe.get('bench:counter');
    pipe.incr('bench:counter');    // OK: counter = 1
    pipe.incr('bench:string');     // ERROR: not integer
    pipe.incr('bench:counter');    // OK: counter = 2 (vẫn execute!)
    pipe.get('bench:counter');

    const results = await pipe.exec();

    console.log('Results:');
    for (let i = 0; i < results.length; i++) {
        const [err, value] = results[i] as [Error | null, any];
        const status = err ? `ERROR: ${err.message}` : `OK: ${value}`;
        console.log(`  [${i}] ${status}`);
    }

    console.log('\nObservation: Command #3 errored, but #4 and #5 still executed.');
    console.log('Redis pipeline KHÔNG rollback khi có error.');
    console.log('Counter =', await redisLAN.get('bench:counter'));
    // Counter = 2 (INCR executed twice, error không stop pipeline)
}
```

**Expected output**:

```txt
=== Pipeline Error Handling Demo ===
Results:
  [0] OK: 0
  [1] OK: 1
  [2] ERROR: ERR value is not an integer
  [3] OK: 2
  [4] OK: 2

Observation: Command #3 errored, but #4 and #5 still executed.
Redis pipeline KHÔNG rollback khi có error.
Counter = 2
```

---

## 3. Challenge Exercise (30–40 phút)

### Scenario: Cache Warmer cho 100 Triệu Records qua WAN

**Bài toán**:

Bạn cần warm cache với **100 triệu records** (key: 50 bytes, value: 1KB) từ database lên Redis qua kết nối WAN với **RTT = 50ms**.

**Constraints**:
- Client memory: 512MB available cho pipeline buffer
- Server `client-query-buffer-limit`: 1GB (default)
- Target p99 latency: < 100ms per batch exec
- Total time budget: < 1 giờ

**Yêu cầu**:

1. **Tính toán batch size tối ưu**:
   - Giải thích từng constraint và cách nó giới hạn batch size
   - Đề xuất batch size cụ thể với lý do

2. **Benchmark thực tế**:
   - Viết code đo p50/p95/p99 latency với các batch size: 1K, 5K, 10K, 20K, 50K, 100K
   - Dùng kết nối WAN (port 6380, RTT 50ms)
   - Vẽ bảng kết quả

3. **Đề xuất final config**:
   - Batch size tối ưu: ???
   - Tổng thời gian ước tính: ???
   - Throughput: ???

### Starter Code: `src/challenge.ts`

```typescript
// File: src/challenge.ts
import { redisWAN, cleanup, connectClients } from './setup';

interface BatchLatency {
    batchSize: number;
    p50: number;
    p95: number;
    p99: number;
    opsPerSec: number;
}

async function measureBatchLatency(batchSize: number, iterations = 100): Promise<BatchLatency> {
    const latencies: number[] = [];

    for (let iter = 0; iter < iterations; iter++) {
        const t0 = Date.now();
        const pipe = redisWAN.pipeline();
        for (let i = 0; i < batchSize; i++) {
            pipe.set(`challenge:key:${iter}:${i}`, `value-${iter}-${i}`);
        }
        await pipe.exec();
        latencies.push(Date.now() - t0);
    }

    const sorted = [...latencies].sort((a, b) => a - b);
    const p = (p: number) => sorted[Math.ceil(p * sorted.length) - 1];

    // ops/sec: batch_size / avg_latency
    const avgLatencyMs = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    const opsPerSec = Math.round((batchSize / avgLatencyMs) * 1000);

    return {
        batchSize,
        p50: p(0.5),
        p95: p(0.95),
        p99: p(0.99),
        opsPerSec,
    };
}

async function main() {
    await connectClients();

    console.log('\n=== Challenge: Optimal Batch Size for 100M Record Cache Warmer ===');
    console.log('Network: WAN RTT=50ms | Target p99 < 100ms\n');

    const batchSizes = [1000, 5000, 10000, 20000, 50000, 100000];

    console.log('Batch Size | p50(ms) | p95(ms) | p99(ms) | Ops/sec');
    console.log('-----------+---------+---------+---------+--------');

    for (const batch of batchSizes) {
        const result = await measureBatchLatency(batch, 50);
        const p99Ok = result.p99 < 100 ? '✓' : '✗';
        console.log(
            `${String(result.batchSize).padStart(10)} | ` +
            `${String(result.p50).padStart(7)} | ` +
            `${String(result.p95).padStart(7)} | ` +
            `${String(result.p99).padStart(7)} ${p99Ok} | ` +
            `${String(result.opsPerSec).padStart(6)}`
        );
    }

    // TODO: Calculate total time for 100M records with optimal batch
    // TODO: Print final recommendation

    await cleanup();
}

main().catch(console.error);
```

**Hint**:
- Batch size càng lớn → p99 latency càng cao (vì exec() block lâu hơn)
- Batch size quá nhỏ → RTT overhead chiếm nhiều
- Tìm "sweet spot" = batch size nhỏ nhất đạt p99 < 100ms

**Full Benchmark Output** (sau khi complete):

```txt
Batch Size | p50(ms) | p95(ms) | p99(ms) | Ops/sec
-----------+---------+---------+---------+--------
      1000 |      52 |      55 |      58 |   19230
      5000 |     255 |     270 |     285 |   19607
     10000 |     510 |     540 |     570 |   19607
     20000 |    1020 |    1080 |    1140 |   19607
     50000 |    2550 |    2700 |    2850 |   19607
    100000 |    5100 |    5400 |    5700 |   19607

Analysis:
  - p99 < 100ms: batch sizes 1000 only
  - Ops/sec constant (~19,607) = 1000 ops / 50ms RTT + server time
  - 100M records at 19,607 ops/sec = 5,100 seconds = 85 minutes
  - p99 < 100ms is the binding constraint → batch 1000 is optimal
  - Time budget < 1 giờ không đạt với 1 worker/connection
  - Cần ít nhất 2 workers độc lập, mỗi worker batch=1000, để đạt ~38K ops/sec và ~44 phút
```

---

## 4. Reflection Questions

### Câu 1: Tại sao pipeline không tăng ops/sec vô hạn khi tăng batch size?

Khi batch size tăng từ 1,000 → 10,000 → 100,000, tổng thời gian tăng tuyến tính (vì RTT = 50ms). Ops/sec = batch_size / (RTT + server_processing_time) → tiến về 1/RTT khi server_processing_time << RTT. Với RTT = 50ms, max ops/sec = 1/0.05 = 20 ops/ms = 20,000 ops/sec — bất kể batch size. Batch size lớn chỉ giảm fixed overhead.

### Câu 2: Khi nào MGET tốt hơn pipeline GET × N?

MGET tốt hơn khi: (1) tất cả keys là String, (2) batch > 10 keys, (3) cần performance tối đa. Pipeline GET × N linh hoạt hơn khi: (1) keys có type khác nhau, (2) cần conditional logic, (3) cần mix read + write trong 1 batch.

### Câu 3: Bạn phát hiện p99 latency cao bất thường khi dùng pipeline batch size 10,000. Nguyên nhân có thể là gì?

(1) p99 spike có thể do garbage collection trong Node.js — khi pipeline exec() tạo large array buffer, V8 GC pause → spike. (2) Server processing time tăng khi batch > 100,000 (command count đáng kể với single thread). (3) Client network jitter ở batch boundary. (4) Buffer allocation — large response array có thể trigger GC.

### Câu 4: Pipeline vs Lua — khi nào chọn Lua mặc dù pipeline nhanh hơn?

Chọn Lua khi cần atomicity + logic (ví dụ: atomic counter + threshold check + conditional reset trong 1 operation). Pipeline không atomic — có race condition giữa INCR và GET. Lua block event loop → chỉ dùng cho scripts < 5ms.

### Câu 5: Trên Redis Cluster, bạn muốn pipeline 1 triệu GET. Bạn sẽ thiết kế như thế nào?

1. Dùng ioredis cluster (tự động split pipeline theo node). 2. Hoặc dùng hash tag `{tenant}:` để pins keys vào cùng slot khi cần multi-key command. 3. Hoặc tách theo node thủ công: call `CLUSTER SLOTS` → group keys by slot/node → send pipeline per node. 4. Monitor `CROSSSLOT`, `MOVED`, `ASK` errors → nếu tăng, cần fix key design hoặc client routing.

---

## 5. Solution Guide

> **SPOILER WARNING**: Phần này chứa đáp án chi tiết. Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1** — `redis-cli --pipe` gửi tất cả PING trong 1 TCP write. Method 1 (pipe) nhanh hơn method 3 (sequential) khoảng 50-100 lần vì chỉ 1 RTT thay vì 100 RTT.

**1.2** — MGET 1 RTT vs 50 RTT riêng lẻ. MGET nhanh hơn ~50 lần. Với RTT 1ms, MGET ~1ms vs sequential ~50ms.

**1.3** — `usec_per_call` của MGET cho 50 keys = 15μs, GET × 50 = 150μs. MGET ~10 lần nhanh hơn về tổng thời gian.

**1.4** — Raw RESP: `*3\r\n` = array 3 elements, `$3\r\n` = bulk string 3 bytes, `SET\r\n` = command. Redis parse raw RESP → execute → return batch responses.

### Hands-on Lab Solutions

**Step 1-3 (LAN benchmark)**:

| Method | Time (10K GETs) | Ops/sec | Speedup |
|--------|-----------------|---------|---------|
| Non-pipeline | ~5,000ms | ~2,000 | 1x |
| Pipeline-100 | ~150ms | ~66,667 | 33x |
| Pipeline-1000 | ~80ms | ~125,000 | 62x |

Số liệu thực tế phụ thuộc hardware. Key insight: batch size tăng → throughput tăng theo, nhưng diminishing returns sau batch=1,000 (server CPU bắt đầu là bottleneck, không phải RTT).

**Step 4-6 (WAN benchmark)**:

| Method | Time (1K GETs) | Ops/sec | Speedup |
|--------|-----------------|---------|---------|
| Non-pipeline (WAN) | ~50,000ms | ~20 | 1x |
| Pipeline-100 (WAN) | ~500ms | ~2,000 | 100x |
| Pipeline-1000 (WAN) | ~50ms | ~20,000 | 1,000x |

**Key insight**: Trên WAN, pipelining cho **dramatic improvement**. Batch 1,000 đạt ~20,000 ops/sec ≈ 1,000 ops / (50ms + 1ms server) = throughput gần max theoretical (1/RTT = 20,000 ops/sec cho RTT=50ms).

**Step 7 (Batch size analysis)**:

Diminishing returns sau batch=1,000:
- Batch 1 → 5,000ms
- Batch 100 → 80ms (62.5x speedup)
- Batch 1,000 → 25ms (200x speedup)
- Batch 10,000 → 21ms (238x speedup)

Với batch > 1,000, server processing time bắt đầu dominate → throughput không tăng nhiều.

**Step 8 (Error handling)**:

Pipeline execute tất cả commands → error trả về riêng. Commands sau error vẫn execute. Counter = 2 (INCR executed 2 lần, dù có error ở command thứ 3).

→ Nếu cần atomicity: dùng MULTI/EXEC hoặc Lua script.

### Challenge Solutions

**Batch size calculation**:

```txt
Constraints:
  1. Client memory (512MB): N × 1,055 bytes < 512MB → N < 500,000
  2. Server input buffer (1GB): N × 1,055 bytes < 1GB → N < 1,000,000
  3. p99 < 100ms: batch × 50ms/RTT + server_time < 100ms
     → batch < 2,000 commands (if server_time ≈ 0)

Binding constraint: p99 < 100ms → batch size ≤ 1,000-2,000
```

**Actual benchmark**:
- Batch 1,000: p99 ~58ms ✓ → 19,230 ops/sec
- Batch 5,000: p99 ~285ms ✗ (exceed 100ms budget)

**Final recommendation**:
- Optimal batch size: **1,000**
- Throughput: ~19,000 ops/sec
- Total time for 100M records với 1 worker: 100,000,000 / 19,000 ≈ **5,263 seconds ≈ 87.7 minutes**
- Để đạt < 1 giờ mà vẫn giữ p99 < 100ms, chạy **2 workers/connections song song**, mỗi worker batch=1,000. Tổng throughput ~38K ops/sec → ~44 phút, nếu Redis CPU/NIC còn headroom.

**Alternative**: Nếu dùng pipeline write (SET) thay vì read, server processing time có thể cao hơn → giảm batch size.

### Reflection Solutions

**Câu 1**: Ops/sec tiến về 1/RTT khi batch tăng. Với RTT=50ms, max ops/sec = 20,000. Batch size tăng không thay đổi throughput khi server_time << RTT.

**Câu 2**: MGET khi > 10 String keys cùng loại. Pipeline khi mixed types hoặc cần conditional logic.

**Câu 3**: p99 spike → GC pause (V8), server command processing time tăng với batch size, network jitter, buffer allocation overhead.

**Câu 4**: Lua khi cần atomicity + logic (atomic counter + conditional). Pipeline không atomic → race condition.

**Câu 5**: ioredis cluster auto-splits pipeline theo node. Hoặc dùng hash tag để pin keys. Hoặc tách thủ công theo slot map.
