# Day 9: Memory Optimization & Fragmentation — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ code**: TypeScript (ioredis + snappy)
**Docker images**: redis:7-alpine, node:20-alpine
**Compression libs**: snappy (npm install snappy), zlib (built-in Node.js)

---

## 1. Warm-up Exercises (15–20 phút)

### 1.1. Baseline Memory Inspection

```bash
redis-cli INFO memory
```

Đọc và phân tích các fields sau:

```bash
# Fragmentation metrics
redis-cli INFO memory | grep -E "used_memory|used_memory_rss|mem_fragmentation|allocator"

# Peak memory
redis-cli INFO memory | grep used_memory_peak

# Dataset vs overhead breakdown
redis-cli INFO memory | grep -E "used_memory_dataset|used_memory_overhead"
```

**Expected output** (fresh Redis, ~0 keys):

```
used_memory:520896
used_memory_rss:3604480
mem_fragmentation_ratio:6.92
allocator_allocated:519952
allocator_active:3604480
```

**Interpretation**:
- `mem_fragmentation_ratio = 6.92` → rất cao vì RSS (3.6MB) / used_memory (520KB) = 6.92
- Lý do: fresh Redis có overhead từ jemalloc arenas (pre-allocated memory). Ratio sẽ giảm khi có data thực tế.

### 1.2. MEMORY DOCTOR

```bash
redis-cli MEMORY DOCTOR
```

**Expected output** (fresh instance):

```
Hi Sam, I'm Redis Memory Doctor!
--- ACTIVE DEFAG STRATEGY RECOMMENDATION ---
You have a lot of waste due to fragmentation.
Recommendation: Enable active defrag with:
  config set activedefrag yes
  config set active-defrag-threshold-lower 10
  ...
```

**Task**: Copy output. Đọc và highlight: defrag recommendation, fragmentation estimate, suggested config values.

### 1.3. Write Data và Measure Fragmentation Change

```bash
# Write 10K keys
redis-cli SET test:frag:1 "value-1"
redis-cli SET test:frag:2 "value-2"
# ... (10K keys total)

# Use pipeline
echo "Keys 1-10000" | redis-cli --pipe

# Check fragmentation again
redis-cli INFO memory | grep -E "used_memory_rss|used_memory|mem_fragmentation"
```

**Expected**: Ratio giảm đáng kể khi có data thực tế (3.6MB → ~1-2MB ratio).

### 1.4. MEMORY USAGE vs MEMORY STATS

```bash
# Set a sample key
redis-cli SET sample:key "hello-world-12345"

# MEMORY USAGE - per-key
redis-cli MEMORY USAGE sample:key

# MEMORY STATS - all keys aggregate
redis-cli MEMORY STATS

# OBJECT ENCODING
redis-cli OBJECT ENCODING sample:key

# DEBUG OBJECT (verbose)
redis-cli DEBUG OBJECT sample:key
```

**Expected**:
- `MEMORY USAGE` trả về ~48 bytes (string value 17B + SDS header + robj + jemalloc rounding)
- `OBJECT ENCODING` = "embstr" hoặc "raw"
- `DEBUG OBJECT` chứa: `encoding`, `refcount`, `lru`, `ldt`, `clen`, `overhead`

### 1.5. Test DEL vs UNLINK Behavior

```bash
# Create a large list (simulate big key)
redis-cli RPUSH biglist $(seq -s " item" 1 10000) > /dev/null

# Measure DEL time (blocking)
time redis-cli DEL biglist

# Recreate and test UNLINK (async)
redis-cli RPUSH biglist $(seq -s " item" 1 10000) > /dev/null
time redis-cli UNLINK biglist

# Check lazyfree queue
redis-cli INFO memory | grep lazyfree
```

**Expected**:
- `DEL`: blocking ~100-300ms cho 10K items list
- `UNLINK`: return ngay lập tức, memory freed async
- `lazyfree_pending_objects`: non-zero briefly after UNLINK

### 1.6. Active Defrag Toggle

```bash
# Check current defrag config
redis-cli CONFIG GET activedefrag
redis-cli CONFIG GET active-defrag-*

# Enable defrag (runtime)
redis-cli CONFIG SET activedefrag yes

# Verify
redis-cli CONFIG GET activedefrag

# Check if defrag is active
redis-cli INFO stats | grep -E "active|defrag"
```

---

## 2. Hands-on Lab (60–70 phút)

### Part A: Fragmentation Pattern — Induce và Defrag

**Thời gian**: 25-30 phút

#### Setup: Docker Compose

```yaml
# docker-compose.lab.yml
version: "3.9"

services:
  redis-lab:
    image: redis:7-alpine
    container_name: redis-lab
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --loglevel notice
    ports:
      - "6379:6379"
    volumes:
      - redis-lab-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  app:
    image: node:20-alpine
    container_name: redis-lab-app
    working_dir: /app
    volumes:
      - ./app:/app
    depends_on:
      redis-lab:
        condition: service_healthy
    command: ["sleep", "infinity"]

volumes:
  redis-lab-data:
```

Tạo `app/package.json` theo mẫu ở Part B trước khi chạy TypeScript, sau đó:

```bash
docker compose -f docker-compose.lab.yml up -d
docker exec -it redis-lab-app sh
npm install
npm run fragmentation
```

#### TypeScript Starter Code

```typescript
// app/part-a-fragmentation.ts
import Redis from 'ioredis';

const redis = new Redis({ host: 'redis-lab', port: 6379 });

async function getMemorySnapshot(): Promise<{
  usedMemory: number;
  usedMemoryRss: number;
  ratio: number;
}> {
  const info = await redis.info('memory');
  const usedMemory = Number(parseInfoField(info, 'used_memory'));
  const usedMemoryRss = Number(parseInfoField(info, 'used_memory_rss'));
  const ratio = parseFloat(parseInfoField(info, 'mem_fragmentation_ratio'));
  return { usedMemory, usedMemoryRss, ratio };
}

function parseInfoField(info: string, key: string): string {
  const line = info.split('\n').find(l => l.startsWith(`${key}:`));
  return line ? line.split(':')[1].trim() : '0';
}

async function printMemory(label: string): Promise<void> {
  const snap = await getMemorySnapshot();
  console.log(
    `[${label}] used_memory: ${(snap.usedMemory / 1024 / 1024).toFixed(2)}MB | ` +
    `RSS: ${(snap.usedMemoryRss / 1024 / 1024).toFixed(2)}MB | ` +
    `ratio: ${snap.ratio.toFixed(3)}`
  );
}

async function induceFragmentation(): Promise<void> {
  console.log('\n=== Step 1: Induce Fragmentation ===');
  console.log('Writing 50K keys with insert/delete pattern...');

  // Pattern: INSERT 50K, DELETE 25K, INSERT 25K → creates fragmentation.
  // Create a new pipeline for each batch; do not reuse a pipeline after exec().
  for (let i = 0; i < 50_000; i += 2000) {
    const pipeline = redis.pipeline();
    for (let j = i; j < Math.min(i + 2000, 50_000); j++) {
      pipeline.set(`frag:key:${j}`, `value-${j}`);
    }
    await pipeline.exec();
  }
  await printMemory('After insert 50K');

  // Delete 25K alternating keys
  for (let i = 0; i < 50_000; i += 4000) {
    const delPipeline = redis.pipeline();
    for (let j = i; j < Math.min(i + 4000, 50_000); j += 2) {
      delPipeline.del(`frag:key:${j}`);
    }
    await delPipeline.exec();
  }
  await printMemory('After delete 25K');

  // Insert 25K new keys
  for (let i = 0; i < 25_000; i += 2000) {
    const insertPipeline = redis.pipeline();
    for (let j = i; j < Math.min(i + 2000, 25_000); j++) {
      insertPipeline.set(`frag:new:${j}`, `new-value-${j}`);
    }
    await insertPipeline.exec();
  }
  await printMemory('After insert 25K new');
}

async function enableDefrag(): Promise<void> {
  console.log('\n=== Step 2: Enable Active Defrag ===');

  await redis.configSet('activedefrag', 'yes');
  await redis.configSet('active-defrag-threshold-lower', '100');
  await redis.configSet('active-defrag-ignore-bytes', '100mb');
  await redis.configSet('active-defrag-cycle-min', '10');
  await redis.configSet('active-defrag-cycle-max', '50');

  const defragStatus = await redis.configGet('activedefrag');
  console.log(`Active defrag enabled: ${defragStatus[1]}`);
}

async function monitorDefragProgress(): Promise<void> {
  console.log('\n=== Step 3: Monitor Defrag Progress ===');
  console.log('Monitoring fragmentation every 5 seconds for 60 seconds...');

  for (let i = 0; i < 12; i++) {
    const snap = await getMemorySnapshot();
    console.log(
      `  t+${(i * 5).toString().padStart(2)}s: ` +
      `ratio=${snap.ratio.toFixed(3)} | ` +
      `RSS=${(snap.usedMemoryRss / 1024 / 1024).toFixed(1)}MB | ` +
      `used=${(snap.usedMemory / 1024 / 1024).toFixed(1)}MB`
    );
    await new Promise(r => setTimeout(r, 5000));
  }

  const finalSnap = await getMemorySnapshot();
  console.log(
    `\n[Defrag Complete] Final ratio: ${finalSnap.ratio.toFixed(3)}`
  );
}

async function cleanup(): Promise<void> {
  console.log('\n=== Step 4: Cleanup ===');
  const keys = await redis.keys('frag:*');
  console.log(`Deleting ${keys.length} keys...`);

  const pipeline = redis.pipeline();
  for (const key of keys) {
    pipeline.unlink(key);
  }
  await pipeline.exec();
  await printMemory('After cleanup');
}

async function main() {
  try {
    await redis.ping();
    console.log('Connected to Redis');

    await printMemory('Baseline (empty)');
    await induceFragmentation();
    await enableDefrag();
    await monitorDefragProgress();
    await cleanup();

    console.log('\nLab complete!');
  } catch (err) {
    console.error('Error:', err);
  } finally {
    await redis.quit();
  }
}

main();
```

#### Expected Output

```
Connected to Redis
[Baseline (empty)] used_memory: 0.52MB | RSS: 3.50MB | ratio: 6.923

=== Step 1: Induce Fragmentation ===
Writing 50K keys with insert/delete pattern...
[After insert 50K] used_memory: 5.23MB | RSS: 7.82MB | ratio: 1.495
[After delete 25K] used_memory: 2.61MB | RSS: 8.10MB | ratio: 3.105
[After insert 25K new] used_memory: 5.28MB | RSS: 8.45MB | ratio: 1.600

=== Step 2: Enable Active Defrag ===
Active defrag enabled: yes

=== Step 3: Monitor Defrag Progress ===
  t+0s:  ratio=1.600 | RSS=8.45MB | used=5.28MB
  t+5s:  ratio=1.540 | RSS=8.30MB | used=5.39MB
  t+10s: ratio=1.490 | RSS=8.10MB | used=5.44MB
  t+15s: ratio=1.410 | RSS=7.88MB | used=5.59MB
  t+30s: ratio=1.210 | RSS=7.20MB | used=5.94MB
  t+45s: ratio=1.110 | RSS=6.80MB | used=6.12MB
  t+60s: ratio=1.080 | RSS=6.65MB | used=6.16MB

[Defrag Complete] Final ratio: 1.080
```

#### Hints

- Ratio cao sau delete pattern là do jemalloc không release pages back to OS immediately
- Active defrag thấy ratio > 1.10 và tồn tại > threshold → bắt đầu defrag
- defrag chạy incremental → ratio giảm từ từ, không phải instant

---

### Part B: Application-Layer Compression Benchmark

**Thời gian**: 35-40 phút

#### Shared Setup: package.json cho Part A và Part B

```json
{
  "name": "redis-compression-lab",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "fragmentation": "tsx part-a-fragmentation.ts",
    "compression": "tsx part-b-compression.ts"
  },
  "dependencies": {
    "ioredis": "^5.3.0",
    "snappy": "^7.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "tsx": "^4.7.0",
    "typescript": "^5.3.3"
  }
}
```

Run Part B:

```bash
docker exec -it redis-lab-app sh
npm install
npm run compression
```

#### TypeScript Starter Code

```typescript
// app/part-b-compression.ts
import Redis from 'ioredis';
import { compress, decompress } from 'snappy';
import { gzip, gunzip } from 'zlib';
import { promisify } from 'util';

const gzipAsync = promisify(gzip);
const gunzipAsync = promisify(gunzip);

const redis = new Redis({ host: 'redis-lab', port: 6379 });

// Generate realistic JSON payload sizes
function generatePayload(sizeKb: number): Record<string, unknown> {
  const targetBytes = sizeKb * 1024;
  const fields: Record<string, unknown> = { id: 1, ts: Date.now() };
  let currentBytes = JSON.stringify(fields).length;

  // Add fields until we hit target size
  let fieldCount = 0;
  while (currentBytes < targetBytes) {
    const value = `field_${fieldCount}_value_` + 'x'.repeat(Math.min(100, targetBytes - currentBytes));
    fields[`attr_${fieldCount}`] = value;
    currentBytes = JSON.stringify(fields).length;
    fieldCount++;
  }
  return fields;
}

async function encodeRaw(obj: Record<string, unknown>): Promise<{ raw: string; compressed?: never }> {
  return { raw: JSON.stringify(obj) };
}

async function encodeSnappy(obj: Record<string, unknown>): Promise<{ compressed: string }> {
  const json = JSON.stringify(obj);
  const compressed = compress(Buffer.from(json));
  return { compressed: compressed.toString('base64') };
}

async function encodeGzip(obj: Record<string, unknown>): Promise<{ compressed: string }> {
  const json = JSON.stringify(obj);
  const compressed = await gzipAsync(Buffer.from(json), { level: 1 });
  return { compressed: compressed.toString('base64') };
}

async function decodeSnappy(encoded: string): Promise<Record<string, unknown>> {
  const compressed = Buffer.from(encoded, 'base64');
  const json = decompress(compressed, { asBuffer: false }) as string;
  return JSON.parse(json);
}

async function decodeGzip(encoded: string): Promise<Record<string, unknown>> {
  const compressed = Buffer.from(encoded, 'base64');
  const json = await gunzipAsync(compressed);
  return JSON.parse(json.toString());
}

type EncodeFn = (obj: Record<string, unknown>) => Promise<{ raw?: string; compressed?: string }>;
type DecodeFn = (encoded: string) => Promise<Record<string, unknown>>;

interface BenchmarkResult {
  payloadSizeBytes: number;
  avgEncodeTimeUs: number;
  avgDecodeTimeUs: number;
  avgRedisMemoryBytes: number;
  compressionRatio: number;
}

async function benchmarkCompression(
  label: string,
  encodeFn: EncodeFn,
  decodeFn: DecodeFn,
  payload: Record<string, unknown>,
  iterations = 1000
): Promise<BenchmarkResult> {
  const payloadSizeBytes = Buffer.byteLength(JSON.stringify(payload), 'utf8');

  // Benchmark encode
  const encodeTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    await encodeFn(payload);
    encodeTimes.push((performance.now() - start) * 1000);
  }
  const avgEncodeTimeUs = encodeTimes.reduce((a, b) => a + b, 0) / encodeTimes.length;

  // Benchmark decode
  const encoded = await encodeFn(payload);
  const encodedValue = (encoded as { raw?: string; compressed?: string }).raw
    || (encoded as { raw?: string; compressed?: string }).compressed!;

  const decodeTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    await decodeFn(encodedValue);
    decodeTimes.push((performance.now() - start) * 1000);
  }
  const avgDecodeTimeUs = decodeTimes.reduce((a, b) => a + b, 0) / decodeTimes.length;

  // Measure Redis memory (write + MEMORY USAGE)
  const testKey = `bench:${label}:${payloadSizeBytes}`;
  await redis.set(testKey, encodedValue);

  const keys = await redis.keys(`bench:${label}:*`);
  let totalRedisMemory = 0;
  for (const key of keys) {
    const usage = await redis.memory('USAGE', key);
    totalRedisMemory += (usage as number);
  }

  await redis.del(...keys);

  const avgRedisMemoryBytes = totalRedisMemory / keys.length;
  const compressionRatio = payloadSizeBytes / avgRedisMemoryBytes;

  return {
    payloadSizeBytes,
    avgEncodeTimeUs,
    avgDecodeTimeUs,
    avgRedisMemoryBytes,
    compressionRatio,
  };
}

async function runBenchmarks(): Promise<void> {
  console.log('=== Compression Benchmark ===\n');

  const sizes = [1, 10, 100]; // KB
  const results: Array<{
    sizeKb: number;
    raw: BenchmarkResult | null;
    snappy: BenchmarkResult | null;
    gzip: BenchmarkResult | null;
  }> = [];

  for (const sizeKb of sizes) {
    console.log(`\n--- Payload: ${sizeKb}KB ---`);
    const payload = generatePayload(sizeKb);
    const jsonSize = Buffer.byteLength(JSON.stringify(payload), 'utf8');
    console.log(`Generated payload: ${(jsonSize / 1024).toFixed(1)}KB`);

    const rawResult = await benchmarkCompression('raw', encodeRaw as EncodeFn,
      async (v) => JSON.parse(v as string) as Record<string, unknown>,
      payload, 2000);
    console.log(`  RAW:       encode=${rawResult.avgEncodeTimeUs.toFixed(1)}μs | decode=${rawResult.avgDecodeTimeUs.toFixed(1)}μs | redis_mem=${(rawResult.avgRedisMemoryBytes/1024).toFixed(0)}KB | ratio=${rawResult.compressionRatio.toFixed(2)}x`);

    const snappyResult = await benchmarkCompression('snappy', encodeSnappy, decodeSnappy, payload, 2000);
    console.log(`  SNAPPY:    encode=${snappyResult.avgEncodeTimeUs.toFixed(1)}μs | decode=${snappyResult.avgDecodeTimeUs.toFixed(1)}μs | redis_mem=${(snappyResult.avgRedisMemoryBytes/1024).toFixed(0)}KB | ratio=${snappyResult.compressionRatio.toFixed(2)}x | savings=${((1-1/snappyResult.compressionRatio)*100).toFixed(0)}%`);

    const gzipResult = await benchmarkCompression('gzip', encodeGzip, decodeGzip, payload, 500);
    console.log(`  GZIP:      encode=${gzipResult.avgEncodeTimeUs.toFixed(1)}μs | decode=${gzipResult.avgDecodeTimeUs.toFixed(1)}μs | redis_mem=${(gzipResult.avgRedisMemoryBytes/1024).toFixed(0)}KB | ratio=${gzipResult.compressionRatio.toFixed(2)}x | savings=${((1-1/gzipResult.compressionRatio)*100).toFixed(0)}%`);

    results.push({ sizeKb, raw: rawResult, snappy: snappyResult, gzip: gzipResult });
  }

  // Summary table
  console.log('\n\n=== Summary ===');
  console.log('Payload | RAW mem | SNAPPY mem | SNAPPY savings | GZIP mem | GZIP savings');
  console.log('--------|----------|------------|---------------|----------|------------');
  for (const r of results) {
    const raw = ((r.raw?.avgRedisMemoryBytes ?? 0) / 1024).toFixed(0);
    const snp = ((r.snappy?.avgRedisMemoryBytes ?? 0) / 1024).toFixed(0);
    const snpSav = ((1 - 1 / (r.snappy?.compressionRatio ?? 1)) * 100).toFixed(0);
    const gz = ((r.gzip?.avgRedisMemoryBytes ?? 0) / 1024).toFixed(0);
    const gzSav = ((1 - 1 / (r.gzip?.compressionRatio ?? 1)) * 100).toFixed(0);
    console.log(`${r.sizeKb}KB    | ${raw.padStart(8)}KB | ${snp.padStart(10)}KB | ${snpSav.padStart(13)}% | ${gz.padStart(8)}KB | ${gzSav.padStart(11)}%`);
  }
}

async function main() {
  try {
    await redis.ping();
    console.log('Connected to Redis');

    await redis.configSet('maxmemory', '128mb');
    console.log('Set maxmemory=128mb for realistic constraint test\n');

    await runBenchmarks();

    console.log('\nLab complete!');
  } catch (err) {
    console.error('Error:', err);
  } finally {
    await redis.quit();
  }
}

main();
```

#### Expected Output (approximate)

```
--- Payload: 1KB ---
  RAW:       encode=2.1μs | decode=1.8μs | redis_mem=1.1KB | ratio=0.95x
  SNAPPY:    encode=8.3μs | decode=6.1μs | redis_mem=0.9KB | ratio=1.15x | savings=-15%
  GZIP:      encode=45.2μs | decode=12.3μs | redis_mem=0.7KB | ratio=1.49x | savings=33%

--- Payload: 10KB ---
  RAW:       encode=18.3μs | decode=16.1μs | redis_mem=10.2KB | ratio=0.98x
  SNAPPY:    encode=35.1μs | decode=22.4μs | redis_mem=5.8KB | ratio=1.76x | savings=43%
  GZIP:      encode=180.2μs | decode=35.1μs | redis_mem=4.2KB | ratio=2.43x | savings=59%

--- Payload: 100KB ---
  RAW:       encode=185.3μs | decode=172.1μs | redis_mem=100.5KB | ratio=0.99x
  SNAPPY:    encode=210.5μs | decode=95.3μs | redis_mem=55KB | ratio=1.83x | savings=45%
  GZIP:      encode=1200.1μs | decode=180.5μs | redis_mem=32KB | ratio=3.14x | savings=68%
```

**Key insight**: Compression chỉ hiệu quả khi payload > ~5KB. Với 1KB, compression overhead làm memory tăng thêm (do compressed data + base64 encoding).

#### Hints

- Snappy decode nhanh hơn gzip decode đáng kể
- Gzip compression ratio cao hơn nhưng encode overhead cũng cao hơn
- Base64 encoding tăng size ~33% so với raw binary → ảnh hưởng ratio

---

## 3. Challenge Exercise (30–40 phút)

### Dataset Optimization Plan: 10M User Profiles

**Scenario**: Hệ thống có 10 triệu user profiles, mỗi profile có 5 fields:

```
user_id (int, 8 bytes)
name (string, avg 30 bytes)
email (string, avg 40 bytes)
preferences (JSON object, avg 200 bytes)
last_login (timestamp, 10 bytes)
```

**Current state**: Dùng String keys: `profile:{userId}` → JSON string value.

**Questions**:

1. **Memory estimate hiện tại** (String keys + JSON): dùng jemalloc size class để tính.

2. **Đề xuất optimization plan** với 3 layers:
   - Layer 1: Encoding tuning (config change, 0 code change)
   - Layer 2: Data model change (Hash + serialization)
   - Layer 3: Compression (application-layer)

3. **Benchmark estimate**: So sánh memory + latency read/write cho mỗi approach.

4. **Recommendation**: Chọn 1 approach cuối cùng, kèm justification.

### Phân tích chi tiết

**Bước 1: Memory hiện tại (String keys + JSON)**

```
Key name: "profile:1234567" → SDS 16B + overhead
Value: JSON string ~288 bytes average
jemalloc: 288B → size class 320B

Per key:
  key SDS: ~22 bytes → 32B (size class)
  robj: 16 bytes
  value SDS: ~294 bytes → 320B (size class)
  jemalloc overhead: negligible (within class)

Total per key: ~368 bytes

10M keys: 10,000,000 × 368B = 3.68 GB logical
RSS với ratio 1.3: ~4.78 GB
```

**Bước 2: Layer 1 — Encoding tuning**

```txt
# Config change only
hash-max-listpack-entries 256
hash-max-listpack-value 256

# Data model: String → Hash
# Key: profile:{userId} (1 key per user)
# Value: Hash với 5 fields
# Encoding: listpack (5 fields < 128, nhưng check value size)

# Preferences field ~200 bytes > 64B default threshold
# → phải dùng hash-max-listpack-value 256
# → listpack vẫn được dùng (5 fields + values < 256B)

# Memory per Hash (listpack):
# listpack header: ~32 bytes
# 5 fields × (field_name_SDS + value_SDS) packed
# Average: ~350 bytes per hash

Total: 10M × 350B = 3.5 GB logical
Savings vs current: ~5%
```

**Bước 3: Layer 2 — Data model + split preferences**

```typescript
// Split preferences into separate Hash để fit listpack threshold
// profile:{userId}:core: Hash (name, email, last_login)
// profile:{userId}:prefs: String (JSON preferences)

Key 1: profile:123:core = Hash (3 fields: name, email, last_login)
  Memory: ~120 bytes (3 fields × ~35B avg)
Key 2: profile:123:prefs = String (JSON ~200B → 256B jemalloc)
  Memory: ~280 bytes

Total per user: ~400 bytes
10M users: 4 GB logical
Savings: NONE (actually slightly worse)
```

**Better approach**: Merge all fields into single Hash, use hash-max-listpack-value 256.

**Bước 4: Layer 3 — Compression**

```typescript
// Compress JSON preferences field
const prefs = { theme: 'dark', lang: 'vi', notifications: true };
const compressed = snappy.compress(JSON.stringify(prefs));
// 200B → ~80B (snappy ratio ~2.5x)
// Store as: profile:{userId}:prefs = <binary compressed>
// Problem: ioredis stores strings, binary must be base64 encoded
// 80B → 107B base64

// Memory: 200B → 107B = 46% reduction on preferences field
// Preferences ~200B of 288B total = 69% of payload
// Savings: 69% × 46% = 32% on total value size
// Total savings: ~32% × 368 bytes = ~118 bytes/key
// 10M × (368 - 118) = 2.5 GB logical
```

### Deliverable

Viết document (~500 words) trình bày:

1. Memory estimate hiện tại (có calculation)
2. 3-layer optimization plan (mỗi layer: memory savings, latency impact, complexity, risk)
3. Recommendation cuối cùng
4. Benchmark plan để verify (list command để chạy)

---

## 4. Reflection Questions

### Câu 1: Defrag — Khi nào bật, khi nào không?

Trong 3 scenario sau, bạn quyết định thế nào?

- Scenario A: 5K ops/sec, fragmentation ratio 1.6, peak hour từ 2-4 giờ sáng
- Scenario B: 50K ops/sec, fragmentation ratio 1.5, peak hour 9 giờ sáng - 6 giờ tối
- Scenario C: 200 ops/sec, fragmentation ratio 2.1, backup job chạy 2 giờ/lần

### Câu 2: Compression — Khi nào worth?

Bạn có 100GB dataset với values 1KB - 5KB (mixed). Compression potential:
- Values 1KB: ratio 1.2x (poor)
- Values 5KB: ratio 2.5x (good)
- Mix 50/50: weighted ratio ~1.85x

Compression overhead:
- Encode: +50μs per operation
- Decode: +30μs per operation
- CPU: +15% on application servers

Read pattern: 80% reads, 20% writes. QPS: 20K reads/sec.

**Question**: Compression có worth không? Tính toán latency impact trên p99.

### Câu 3: Key Design — Trade-off thực tế

Bạn có 2 thiết kế cho 10M user sessions:

- **Design A**: Hash per user (`session:{userId}`), 50 fields per session
- **Design B**: String key per field (`session:{userId}:field:{fieldName}`), 50 keys per user

Phân tích: memory, latency read/write, hot key risk, operational complexity.

---

## 5. Solution Guide

> **SPOILER WARNING**: Đọc sau khi đã thử làm bài tập.

### Warm-up Solutions

**1.1** — Baseline:
- Ratio 6.92 vì fresh Redis có jemalloc arena pre-allocated (~3.5MB RSS cho empty instance). used_memory chỉ 520KB → ratio cao bất normal.
- Ratio sẽ normalize khi data tăng.

**1.4** — `MEMORY USAGE sample:key`:
- String "hello-world-12345" = 17 bytes + SDS header 3 bytes + robj 16 bytes = 36 bytes → jemalloc round to 48 bytes.
- Output ~48 bytes (có thể ~64 bytes tùy allocator version).

**1.5** — DEL vs UNLINK:
- `DEL biglist`: blocking ~100-300ms cho list 10K items
- `UNLINK biglist`: return immediately, lazy free in background
- Production rule: always use UNLINK for keys > 1KB.

### Part A: Fragmentation Lab

**Key insight**: Insert/delete pattern tạo fragmentation vì:
1. jemalloc allocate pages cho new keys
2. Free không release pages về OS (arena retention)
3. New allocations reuse freed slots nhưng size class khác → fragmentation accumulates

**Defrag behavior**:
- Threshold 100 = ratio > 2.0
- Cycle min 10 = slow defrag (low CPU budget)
- Progress: ratio giảm từ từ (~0.1 per 15s với conservative settings)
- After 60s: ratio ~1.08-1.10 expected

**Expected observation**: Ratio giảm sau khi defrag enabled, nhưng không về 1.0 (some natural fragmentation always exists).

### Part B: Compression Lab

**Key findings**:

| Payload | Compression worth it? | Best choice | Savings |
|---------|----------------------|-------------|---------|
| 1KB | NO (overhead > savings) | RAW | 0% |
| 10KB | YES (43-59% savings) | snappy (speed) | 43% |
| 100KB | YES (45-68% savings) | gzip (ratio) | 68% |

**Decision framework**:
- Payload < 5KB: no compression (overhead > savings)
- Payload 5-50KB: snappy (fast, good ratio)
- Payload > 50KB: gzip or zstd (best ratio)

**Latency impact on reads**:
- snappy decode: ~22μs for 10KB → negligible for most apps
- gzip decode: ~35μs for 10KB → still acceptable
- If QPS = 20K and decode = 35μs → decode adds 700ms total per batch (parallel on modern CPU)

### Challenge Solutions

**Layer 1 (Encoding tuning)**: ~5% savings, minimal risk. Quick win nhưng không đủ.

**Layer 2 (Data model)**: ~10-15% savings, medium complexity. Hash split có thể worse nếu không split đúng cách.

**Layer 3 (Compression)**: ~30-40% savings, high complexity. Worth it cho large values.

**Recommendation**: Layer 1 + Layer 3 combined:
```txt
hash-max-listpack-entries 256
hash-max-listpack-value 256
```
+ Application-layer snappy compression for preferences field.

**Benchmark plan**:
```bash
# Baseline
redis-cli --scan | wc -l  # key count
redis-cli INFO memory | grep used_memory_rss
redis-cli --scan | head -1000 | xargs -I{} redis-cli MEMORY USAGE {} | awk '{s+=$1} END {print s/1000}'

# After optimization
redis-cli INFO memory | grep used_memory_rss  # should be 30-40% lower
redis-cli --latency-history  # measure latency
```

### Reflection Solutions

**Câu 1**:
- Scenario A (5K ops/sec, peak 2-4AM): **Bật defrag conservative** — low traffic, can tolerate slight CPU overhead
- Scenario B (50K ops/sec, peak 9AM-6PM): **Không bật defrag** — high traffic, latency sensitive. Thay vào đó: scheduled defrag 2-4AM
- Scenario C (200 ops/sec, backup job): **Bật defrag aggressive** — low traffic, backup job có maintenance window

**Câu 2**: Compression worth it nếu:
- Memory savings ~35% × 100GB = 35GB (significant)
- CPU overhead: +15% on app servers = acceptable nếu có headroom
- Latency: +30μs decode × 20K reads/sec = 600ms/second = negligible (parallel processing)
- Recommendation: Deploy với snappy, benchmark 1 tuần trước full rollout.

**Câu 3**: Design A vs B:
- Memory: Design A (Hash) = ~400 bytes/user. Design B (String keys) = 50 × ~60 bytes = 3000 bytes/user → 7.5x worse
- Latency read: Design A = 1 round trip (HGETALL). Design B = 50 round trips (hoặc 1 pipeline 50 commands)
- Hot key risk: Design A = 1 hot key per user. Design B = spread risk across 50 keys per user
- **Recommendation**: Design A (Hash) — significantly better memory, reasonable latency
