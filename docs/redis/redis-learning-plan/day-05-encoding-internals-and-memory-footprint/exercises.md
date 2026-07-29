# Day 5: Encoding Internals & Memory Footprint — Exercises

**Thời lượng**: ~2 giờ
**Môi trường**: Docker Compose (Redis 7.2) + TypeScript + ioredis
**File khởi tạo**: Docker Compose provided in document.md

---

## 0. Setup

```bash
cd redis-learning-plan/day-05-encoding-internals-and-memory-footprint
docker compose up -d
redis-cli ping
# Expected: PONG
```

Kiểm tra Redis version:

```bash
redis-cli INFO server | grep redis_version
# Expected: redis_version:7.2.x
```

Kiểm tra encoding thresholds:

```bash
redis-cli CONFIG GET hash-max-listpack-entries
# Expected: 1) "hash-max-listpack-entries"  2) "128"
```

---

## 1. Warm-up Exercises (15–20 phút)

Thực hành với `redis-cli`. Mỗi command có expected output để verify.

### 1.1. OBJECT ENCODING — Inspect Various Data Types

```bash
# String encoding
SET string:short "hello"
SET string:number "42"
SET string:long "this-is-a-very-long-string-that-exceeds-44-bytes-for-embstr"

OBJECT ENCODING string:short
# Expected: "embstr"  (≤44 bytes, embedded in robj)

OBJECT ENCODING string:number
# Expected: "int"  (integer string)

OBJECT ENCODING string:long
# Expected: "raw"  (>44 bytes, separate SDS allocation)

# Hash encoding — small vs large
HSET hash:small field1 value1 field2 value2 field3 value3
OBJECT ENCODING hash:small
# Expected: "listpack"  (3 fields < 128, value < 64B)

# Hash with > 128 fields → hashtable
redis-cli -r 1 -c "EVAL \"for i=0,129 do redis.call('HSET', 'hash:large', 'field_'..i, 'value_'..i) end\" 0"
OBJECT ENCODING hash:large
# Expected: "hashtable"  (fields > 128)

# Set encoding
SADD set:intset 1 2 3 4 5 6
OBJECT ENCODING set:intset
# Expected: "intset"  (all integers, ≤ 512)

SADD set:hashtable "string_element" 999
OBJECT ENCODING set:hashtable
# Expected: "hashtable"  (contains string)

# Sorted Set encoding
ZADD zset:small 1 one 2 two 3 three
OBJECT ENCODING zset:small
# Expected: "listpack"  (≤ 128 entries, value < 64B)

ZADD zset:large 1 one 2 two 3 three 4 four 5 five 6 six 7 seven 8 eight 9 nine 10 ten 11 eleven 12 twelve 13 thirteen 14 fourteen 15 fifteen 16 sixteen 17 seventeen 18 eighteen 19 nineteen 20 twenty
# Add more to force skiplist
redis-cli -r 1 -c "EVAL \"for i=1,130 do redis.call('ZADD', 'zset:large', i, 'member_'..i) end\" 0"
OBJECT ENCODING zset:large
# Expected: "skiplist"  (entries > 128)

# List encoding (quicklist in Redis 7)
RPUSH list:test 1 2 3 4 5
OBJECT ENCODING list:test
# Expected: "quicklist"  (Redis 7+)
```

### 1.2. MEMORY USAGE — Measure Per-Key Memory

```bash
# Clean slate
FLUSHDB

# Small String vs Large String
SET small "x"
SET large "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

MEMORY USAGE small
# Expected: ~50-70 bytes (robj + embstr)

MEMORY USAGE large
# Expected: ~200+ bytes (robj + SDS header + 200 bytes data)

# Hash memory — listpack vs hashtable
HSET h:small f1 v1 f2 v2 f3 v3
HSET h:large f1 v1
# Add 129 fields to force hashtable
redis-cli -r 1 -c "EVAL \"for i=1,129 do redis.call('HSET', 'h:large', 'field_'..i, 'val_'..i) end\" 0"

MEMORY USAGE h:small
# Expected: ~200-400 bytes (listpack, 3 fields)

MEMORY USAGE h:large SAMPLES 0
# Expected: ~4000-8000 bytes (hashtable, 129 fields, ~24B/entry dictEntry)

# Compare: MEMORY USAGE with SAMPLES vs SAMPLES 0
MEMORY USAGE h:large SAMPLES 5
# Expected: lower than SAMPLES 0 (sampled estimate)

# MEMORY DOCTOR — diagnose instance memory
MEMORY DOCTOR
# Expected: Output advice on fragmentation, allocator issues, memory leaks
```

### 1.3. DEBUG OBJECT — Full Object Inspection

`DEBUG OBJECT` chỉ dùng trong lab/dev. Docker Compose ở phần lab bật `--enable-debug-command yes`; managed Redis production thường disable command này.

```bash
DEBUG OBJECT h:small
# Expected fields:
# encoding:listpack
# listpack_bytes: N
# listpack_entries: 3
# refcount: 1

DEBUG OBJECT string:number
# Expected:
# encoding:int
# refcount: 1

DEBUG OBJECT zset:large
# Expected:
# encoding:skiplist
# listpack_bytes: (not shown for skiplist)
# refcount: 1

# WARNING: DEBUG OBJECT is for development only. Do NOT run on production keys.
```

### 1.4. INFO Memory — Instance-Level Overview

```bash
INFO memory | grep -E "used_memory|used_memory_rss|mem_fragmentation|maxmemory"
# Expected:
# used_memory:NNNNNN
# used_memory_rss:MMMMMM   (RSS >= used_memory)
# mem_fragmentation_ratio:X.XX  (should be < 1.5)
# maxmemory:0  (or set value)
```

---

## 2. Hands-on Lab (60–70 phút)

**Mục tiêu**: Thực hành encoding flip, measure memory, so sánh data models.

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7.2
    container_name: redis-day5
    command: >
      redis-server
      --save ""
      --appendonly no
      --maxmemory 256mb
      --hash-max-listpack-entries 128
      --hash-max-listpack-value 64
      --enable-debug-command yes
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

### TypeScript Starter Code

```typescript
// exercises/src/day5.ts
import Redis from 'ioredis';

const redis = new Redis({
  host: 'localhost',
  port: 6379,
  lazyConnect: true,
  retryStrategy: (times) => {
    if (times > 3) return null;
    return Math.min(times * 200, 2000);
  },
});

async function setup() {
  await redis.connect();
  await redis.flushdb();
  console.log('Redis connected and flushed');
}

// ─── Helper ──────────────────────────────────────────────────────────────────

async function getEncoding(key: string): Promise<string> {
  return (await redis.call('OBJECT', 'ENCODING', key)) as string;
}

async function getMemory(key: string): Promise<number> {
  return (await redis.call('MEMORY', 'USAGE', key, 'SAMPLES', '0')) as number;
}

async function getInstanceMemory(): Promise<{ used: number; rss: number; frag: number }> {
  const info = (await redis.call('INFO', 'memory')) as string;
  const used = parseInt(info.match(/used_memory:(\d+)/)?.[1] ?? '0');
  const rss = parseInt(info.match(/used_memory_rss:(\d+)/)?.[1] ?? '0');
  const frag = parseFloat(info.match(/mem_fragmentation_ratio:([\d.]+)/)?.[1] ?? '0');
  return { used, rss, frag };
}

async function printEncodingAndMemory(key: string) {
  const enc = await getEncoding(key);
  const mem = await getMemory(key);
  console.log(`  ${key}: encoding=${enc}, memory=${mem} bytes`);
}

// ─── Step 1: Hash 100 fields → listpack ────────────────────────────────────

async function step1() {
  console.log('\n=== Step 1: Hash 100 fields (listpack) ===');
  const key = 'lab:hash:100';
  await redis.call('DEL', key);

  for (let i = 0; i < 100; i++) {
    await redis.call('HSET', key, `field_${i}`, `value_${i}`);
  }

  await printEncodingAndMemory(key);
  const enc = await getEncoding(key);
  if (enc !== 'listpack') {
    throw new Error(`Expected listpack, got ${enc}`);
  }
  console.log('  ✓ Encoding is listpack (100 fields < 128 threshold)');
}

// ─── Step 2: Add field 129 → hashtable flip ─────────────────────────────────

async function step2() {
  console.log('\n=== Step 2: Add field 129 → hashtable flip ===');
  const key = 'lab:hash:100';
  const encBefore = await getEncoding(key);
  const memBefore = await getMemory(key);

  // Add field 129 with value > 64B to guarantee flip
  const longValue = 'x'.repeat(65); // > 64 bytes threshold
  await redis.call('HSET', key, 'field_129', longValue);

  const encAfter = await getEncoding(key);
  const memAfter = await getMemory(key);

  console.log(`  Before: encoding=${encBefore}, memory=${memBefore} bytes`);
  console.log(`  After:  encoding=${encAfter}, memory=${memAfter} bytes`);
  console.log(`  Memory increase: ${memAfter - memBefore} bytes (${(memAfter / memBefore).toFixed(2)}x)`);

  if (encAfter !== 'hashtable') {
    throw new Error(`Expected hashtable after flip, got ${encAfter}`);
  }
  if (memAfter < memBefore) {
    throw new Error(`Memory should increase after flip`);
  }
  console.log('  ✓ Encoding flipped to hashtable, memory increased');
}

// ─── Step 3: Measure MEMORY USAGE before/after flip ─────────────────────────

async function step3() {
  console.log('\n=== Step 3: Compare memory usage of encoding modes ===');

  // Mode A: 100 hashes × 10 fields = listpack
  // Mode B: 100 hashes × 200 fields = hashtable

  const modeA: string[] = [];
  const modeB: string[] = [];

  const t0 = Date.now();
  for (let i = 0; i < 100; i++) {
    const key = `lab:mode_a:${i}`;
    const fields: string[] = [];
    for (let f = 0; f < 10; f++) {
      fields.push(`f${f}`, `v${f}`);
    }
    await redis.call('HSET', key, ...fields);
    modeA.push(key);
  }
  const t1 = Date.now();

  for (let i = 0; i < 100; i++) {
    const key = `lab:mode_b:${i}`;
    const fields: string[] = [];
    for (let f = 0; f < 200; f++) {
      fields.push(`f${f}`, `value_${f}_for_mode_b`);
    }
    await redis.call('HSET', key, ...fields);
    modeB.push(key);
  }
  const t2 = Date.now();

  // Sample memory
  const memA_sample = await getMemory(modeA[0]);
  const memB_sample = await getMemory(modeB[0]);

  const encA = await getEncoding(modeA[0]);
  const encB = await getEncoding(modeB[0]);

  console.log(`  Mode A (10 fields/hash, ${encA}): ~${memA_sample} bytes/hash`);
  console.log(`  Mode B (200 fields/hash, ${encB}): ~${memB_sample} bytes/hash`);
  console.log(`  Ratio: ${(memB_sample / memA_sample).toFixed(2)}x more memory per key`);
  console.log(`  Mode A write: ${t1 - t0}ms, Mode B write: ${t2 - t1}ms`);

  const instance = await getInstanceMemory();
  console.log(`  Instance memory: ${(instance.used / 1024 / 1024).toFixed(2)} MB, RSS: ${(instance.rss / 1024 / 1024).toFixed(2)} MB, frag: ${instance.frag.toFixed(2)}x`);
}

// ─── Step 4: String vs Hash data model comparison ────────────────────────────

async function step4() {
  console.log('\n=== Step 4: String keys vs Hash model comparison ===');
  await redis.flushdb();

  const N = 1000; // 1K users for quick test
  const fieldsPerUser = 5;

  // Approach A: Hash per user (listpack)
  const t0 = Date.now();
  for (let userId = 0; userId < N; userId++) {
    const fields: string[] = [];
    for (let f = 0; f < fieldsPerUser; f++) {
      fields.push(`field_${f}`, `value_${userId}_${f}`);
    }
    await redis.call('HSET', `hash:user:${userId}`, ...fields);
  }
  const tA = Date.now() - t0;

  const encA = await getEncoding('hash:user:0');
  const memA = await getMemory('hash:user:0');
  const totalA = memA * N;

  console.log(`  Hash model: encoding=${encA}, per-key=${memA} bytes, total(${N}×${fieldsPerUser}fields)=${(totalA / 1024 / 1024).toFixed(2)} MB`);
  console.log(`  Write time: ${tA}ms`);

  // Approach B: Individual String keys per field
  const t1 = Date.now();
  for (let userId = 0; userId < N; userId++) {
    for (let f = 0; f < fieldsPerUser; f++) {
      await redis.call('SET', `string:user:${userId}:field_${f}`, `value_${userId}_${f}`);
    }
  }
  const tB = Date.now() - t1;

  const memB = await getMemory('string:user:0:field_0');
  const totalB = memB * N * fieldsPerUser;

  console.log(`  String model: per-key=${memB} bytes, total(${N * fieldsPerUser}keys)=${(totalB / 1024 / 1024).toFixed(2)} MB`);
  console.log(`  Write time: ${tB}ms`);
  console.log(`  Memory diff: Hash is ${(totalB / totalA).toFixed(2)}x smaller than Strings`);
  console.log(`  Write speed: Hash ${((tB / tA) - 1) > 0 ? `${(tB / tA).toFixed(1)}x` : `${(tA / tB).toFixed(1)}x faster`} than Strings`);
}

// ─── Step 5: INFO memory — instance overview ─────────────────────────────────

async function step5() {
  console.log('\n=== Step 5: Full instance memory analysis ===');
  await redis.flushdb();

  // Create a variety of data types
  await redis.call('SET', 'test:string', 'hello world');
  await redis.call('HSET', 'test:hash', 'f1', 'v1', 'f2', 'v2');
  await redis.call('SADD', 'test:set', 'a', 'b', '1', '2');
  await redis.call('ZADD', 'test:zset', 1, 'one', 2, 'two');
  await redis.call('RPUSH', 'test:list', 'x', 'y', 'z');

  const instance = await getInstanceMemory();
  const info = (await redis.call('INFO', 'memory')) as string;

  const parse = (key: string) =>
    parseInt(info.match(new RegExp(`${key}:(\\d+)`))?.[1] ?? '0');

  console.log('\n  Redis Memory Breakdown:');
  console.log(`    used_memory:          ${(parse('used_memory') / 1024).toFixed(2)} KB`);
  console.log(`    used_memory_rss:      ${(parse('used_memory_rss') / 1024).toFixed(2)} KB`);
  console.log(`    mem_fragmentation:    ${instance.frag.toFixed(2)}x`);
  console.log(`    overhead.meta:        ${(parse('overhead.total') / 1024).toFixed(2)} KB`);
  console.log(`    keys.in.db:           ${(await redis.call('DBSIZE'))}`);

  const wasted = instance.rss - instance.used;
  console.log(`    Estimated waste:      ${(wasted / 1024).toFixed(2)} KB (RSS - used_memory)`);
}

// ─── Run all steps ───────────────────────────────────────────────────────────

async function main() {
  try {
    await setup();
    await step1();
    await step2();
    await step3();
    await step4();
    await step5();
    console.log('\n✅ All steps completed');
  } catch (err) {
    console.error('\n❌ Step failed:', err);
    process.exit(1);
  } finally {
    await redis.quit();
  }
}

main();
```

### Expected Output (approximate)

```txt
Redis connected and flushed

=== Step 1: Hash 100 fields (listpack) ===
  lab:hash:100: encoding=listpack, memory=XXX bytes
  ✓ Encoding is listpack (100 fields < 128 threshold)

=== Step 2: Add field 129 → hashtable flip ===
  Before: encoding=listpack, memory=XXX bytes
  After:  encoding=hashtable, memory=XXX bytes
  Memory increase: XXX bytes (X.XXx)
  ✓ Encoding flipped to hashtable, memory increased

=== Step 3: Compare memory usage of encoding modes ===
  Mode A (10 fields/hash, listpack): ~XXX bytes/hash
  Mode B (200 fields/hash, hashtable): ~XXX bytes/hash
  Ratio: X.XXx more memory per key

=== Step 4: String keys vs Hash model comparison ===
  Hash model: encoding=listpack, per-key=XXX bytes, total(...)=X.XX MB
  String model: per-key=XXX bytes, total(...)=X.XX MB
  Memory diff: Hash is X.XXx smaller than Strings

=== Step 5: Full instance memory analysis ===
  Redis Memory Breakdown:
    used_memory:          X.XX KB
    used_memory_rss:      X.XX KB
    mem_fragmentation:    X.XXx

✅ All steps completed
```

---

## 3. Challenge Exercise (30–40 phút)

### Challenge: Feature Flags Data Model — Memory + Latency Benchmark

**Scenario**: 10M users × 200 boolean feature flags. Yêu cầu:
- Toggle flag nhanh
- Read flag O(1)
- Memory hiệu quả
- Không hot key

**Đề xuất 3 approaches** và benchmark:

```typescript
// Challenge: src/challenge.ts
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379, lazyConnect: true });
const USER_SAMPLE = 10_000; // sample for benchmarking
const TOTAL_USERS = 10_000_000;
const FLAG_COUNT = 200;

async function setup() {
  await redis.connect();
  await redis.flushdb();
}

// ─── Approach A: String Keys ──────────────────────────────────────────────────
// Key: feature:{userId}:{flagId}, Value: "0" or "1"

async function approachA_init() {
  console.log('\n=== Approach A: String Keys ===');
  const sample = Math.min(USER_SAMPLE, 1000); // smaller for init speed
  for (let userId = 0; userId < sample; userId++) {
    for (let flagId = 0; flagId < FLAG_COUNT; flagId++) {
      await redis.call('SET', `feat_a:${userId}:${flagId}`, '0');
    }
  }
  console.log(`  Initialized ${sample * FLAG_COUNT} keys`);
}

async function approachA_benchmark() {
  // Read benchmark
  const sample = Math.min(USER_SAMPLE, 1000);
  const t0 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('GET', `feat_a:${i % sample}:${i % FLAG_COUNT}`);
  }
  const readLatency = (Date.now() - t0) / (sample * FLAG_COUNT);

  // Write (toggle) benchmark
  const t1 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('SET', `feat_a:${i % sample}:${i % FLAG_COUNT}`, '1');
  }
  const writeLatency = (Date.now() - t1) / (sample * FLAG_COUNT);

  // Memory estimate
  const memPerKey = await redis.call('MEMORY', 'USAGE', `feat_a:0:0`);
  const totalKeys = TOTAL_USERS * FLAG_COUNT;
  const estimatedMemory = (memPerKey as number) * totalKeys;

  console.log(`  Read latency:  ${(readLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Write latency: ${(writeLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Per-key memory: ${memPerKey} bytes`);
  console.log(`  Est. total (${(totalKeys / 1e9).toFixed(1)}B keys): ${(estimatedMemory / 1024 / 1024 / 1024).toFixed(1)} GB`);
}

// ─── Approach B: Hash Listpack ───────────────────────────────────────────────
// Key: user_flags:{userId}, Hash with 200 fields

async function approachB_init() {
  console.log('\n=== Approach B: Hash Listpack ===');
  const sample = Math.min(USER_SAMPLE, 1000);
  for (let userId = 0; userId < sample; userId++) {
    const fields: string[] = [];
    for (let flagId = 0; flagId < FLAG_COUNT; flagId++) {
      fields.push(`flag_${flagId}`, '0');
    }
    await redis.call('HSET', `feat_b:${userId}`, ...fields);
  }
  const enc = await redis.call('OBJECT', 'ENCODING', 'feat_b:0');
  console.log(`  Initialized ${sample} users, encoding=${enc}`);
}

async function approachB_benchmark() {
  const sample = Math.min(USER_SAMPLE, 1000);
  // Read: HGET user_flags:{userId} flag_{id}
  const t0 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('HGET', `feat_b:${i % sample}`, `flag_${i % FLAG_COUNT}`);
  }
  const readLatency = (Date.now() - t0) / (sample * FLAG_COUNT);

  // Write: HSET
  const t1 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('HSET', `feat_b:${i % sample}`, `flag_${i % FLAG_COUNT}`, '1');
  }
  const writeLatency = (Date.now() - t1) / (sample * FLAG_COUNT);

  const memPerUser = await redis.call('MEMORY', 'USAGE', `feat_b:0`, 'SAMPLES', '0');
  const estimatedMemory = (memPerUser as number) * TOTAL_USERS;

  console.log(`  Read latency:  ${(readLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Write latency: ${(writeLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Per-user memory: ${memPerUser} bytes`);
  console.log(`  Est. total (${TOTAL_USERS / 1e6}M users): ${(estimatedMemory / 1024 / 1024 / 1024).toFixed(1)} GB`);
}

// ─── Approach C: Bitmap ──────────────────────────────────────────────────────
// Key: flag:{flagId}, Bitmap with userId as bit position

async function approachC_init() {
  console.log('\n=== Approach C: Bitmap ===');
  const sample = Math.min(USER_SAMPLE, 1000);
  for (let flagId = 0; flagId < FLAG_COUNT; flagId++) {
    for (let userId = 0; userId < sample; userId++) {
      await redis.call('SETBIT', `feat_c:${flagId}`, userId, 0);
    }
  }
  console.log(`  Initialized ${FLAG_COUNT} bitmaps × ${sample} users`);
}

async function approachC_benchmark() {
  const sample = Math.min(USER_SAMPLE, 1000);
  // Read: GETBIT flag:{flagId} userId
  const t0 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('GETBIT', `feat_c:${i % FLAG_COUNT}`, i % sample);
  }
  const readLatency = (Date.now() - t0) / (sample * FLAG_COUNT);

  // Write: SETBIT
  const t1 = Date.now();
  for (let i = 0; i < sample * FLAG_COUNT; i++) {
    await redis.call('SETBIT', `feat_c:${i % FLAG_COUNT}`, i % sample, 1);
  }
  const writeLatency = (Date.now() - t1) / (sample * FLAG_COUNT);

  const memPerBitmap = await redis.call('MEMORY', 'USAGE', `feat_c:0`);
  const estimatedMemory = (memPerBitmap as number) * FLAG_COUNT;

  console.log(`  Read latency:  ${(readLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Write latency: ${(writeLatency * 1000).toFixed(3)} ms/op`);
  console.log(`  Per-flag memory: ${memPerBitmap} bytes`);
  console.log(`  Est. total (${FLAG_COUNT} flags): ${(estimatedMemory / 1024 / 1024).toFixed(1)} MB`);
}

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  try {
    await setup();

    await approachA_init();
    await approachA_benchmark();

    await redis.flushdb();
    await approachB_init();
    await approachB_benchmark();

    await redis.flushdb();
    await approachC_init();
    await approachC_benchmark();

    console.log('\n=== Recommendation ===');
    console.log('  Approach A (String):  Extreme memory — DO NOT use');
    console.log('  Approach B (Hash):     Balanced memory + operations — Best general choice');
    console.log('  Approach C (Bitmap):   Best memory for boolean-only, limited flexibility');

  } catch (err) {
    console.error('Error:', err);
  } finally {
    await redis.quit();
  }
}

main();
```

### Expected Analysis Output

```txt
=== Approach A: String Keys ===
  Read latency:  ~0.015 ms/op
  Write latency: ~0.025 ms/op
  Est. total (2.0B keys): ~120+ GB
  ⚠ DO NOT use for this scale

=== Approach B: Hash Listpack ===
  Read latency:  ~0.010 ms/op  (HGET O(N) listpack scan but N=200, fast)
  Write latency: ~0.015 ms/op
  Est. total (10M users): ~2-3 GB  ✓
  ✓ RECOMMENDED

=== Approach C: Bitmap ===
  Read latency:  ~0.012 ms/op
  Write latency: ~0.030 ms/op
  Est. total (200 flags): ~250 MB  ✓
  ✓ Good for boolean-only, O(1) per operation
  ⚠ Trade-off: cannot store non-boolean data
```

---

## 4. Reflection Questions

**Câu 1**: Khi nào việc tăng `hash-max-listpack-entries` có lợi và khi nào có hại? Trình bày 2 scenario cụ thể.

**Câu 2**: Trong production, bạn phát hiện `mem_fragmentation_ratio` = 2.5 và `used_memory_rss` cao hơn `maxmemory`. Nêu 3 bước action plan và giải thích priority của từng bước.

**Câu 3**: `MEMORY USAGE` trả về `nil` cho một key. Giải thích 3 possible causes và cách debug từng case.

**Câu 4**: Mô tả scenario mà việc encoding flip từ listpack → hashtable có thể gây cascading failure trong production ( không chỉ memory spike đơn thuần).

---

## 5. Solution Guide

> ⚠️ **SPOILER WARNING** — Đọc sau khi đã thử làm bài tự thân.

### Solution 1.1 — Warm-up: OBJECT ENCODING

```bash
# All expected outputs đã ghi trong phần 1.1
# Key insight: encoding thay đổi theo threshold
# "embstr" là embedded string (≤44 bytes) — stored trong robj struct, 1 allocation
# "raw" là separate SDS allocation (>44 bytes)
# "listpack" (Redis 7+) thay "ziplist" (Redis 6)
# "quicklist" (Redis 7+) thay "linkedlist" (Redis 6)
```

### Solution 1.2 — MEMORY USAGE

```bash
# MEMORY USAGE trả về nil nếu key không tồn tại
# SAMPLES 0 = full scan, accurate cho big listpack
# SAMPLES 5 = default, fast approximation
# MEMORY USAGE count cả robj + data + overhead
# Nó KHÔNG count key name overhead trong per-key usage
# (key name counted separately trong keyspace total)
```

### Solution 1.3 — DEBUG OBJECT

```bash
# Chỉ dùng trong development/test environment
# NEVER run on production (BLOCKING với big keys)
# Redis không có option SANITIZE-ENCODING cho DEBUG OBJECT.
# Dùng OBJECT ENCODING + MEMORY USAGE để inspect an toàn hơn.
# "refcount" > 1: object đang được shared (VD: interned strings)
```

### Solution 2 — Hands-on Lab

**Step 1**: 100 fields → listpack. Threshold = 128, 100 < 128 ✓

**Step 2**: Field 129 với value 65 bytes → hashtable flip vì BOTH conditions violated: fields > 128 AND value > 64B. Memory tăng ~3-5x. Lý do: listpack ~2 bytes/entry, hashtable ~24 bytes/entry dictEntry overhead.

**Step 3**: Mode A (10 fields) vs Mode B (200 fields) — hashtable overhead per entry ~24B regardless of value size. Nếu value < 64B → listpack (compact). Mode A: 10 × ~2 bytes = ~20 bytes/listpack overhead. Mode B: 200 × 24 bytes = ~4800 bytes dictEntry overhead.

**Step 4**: Hash vs String. Hash chia sẻ key metadata (1 key name SDS, 1 robj, 1 listpack). String model: 5 keys × 1 key name + 1 value + overhead = ~5x overhead. Hash tiết kiệm 4-5x memory trong trường hợp này. Tuy nhiên write speed Hash nhanh hơn vì 1 command vs 5 commands.

**Step 5**: Fragmentation ratio = used_memory_rss / used_memory. Jemalloc rounding, active defrag tuning, large key deletions để lại holes → fragmentation. Ratio > 1.5 = action needed. Ratio < 1.1 = OK.

### Solution 3 — Challenge

**Approach A (String)**: KHÔNG dùng. 10M × 200 = 2B keys → impossible. Even với 10K sample, memory > 100GB.

**Approach B (Hash)**: RECOMMENDED cho general case.
- Memory: 10M × 250 bytes (listpack) ≈ 2.5 GB
- Operations: HGET/HSET per flag
- Encoding: listpack với 200 fields — listpack vì 200 > 128? Không! Nếu mỗi value chỉ là "0" hoặc "1" (1 byte), thì 200 fields > 128 → hashtable. Nhưng hashtable overhead ~24B/field × 200 = 4.8KB/user × 10M = 48 GB → quá lớn.
- **Cải thiện**: Split thành 2 Hashes, mỗi Hash ≤ 128 fields: `feat:{userId}:1` (flags 0–127), `feat:{userId}:2` (flags 128–199). Mỗi Hash 128 fields → listpack (1 byte values). Total: 2 × 10M × ~300 bytes = 6 GB.
- Tốt hơn Approach A (100GB) và tốt hơn 1 big Hash hashtable (48GB).

**Approach C (Bitmap)**: RECOMMENDED cho boolean-only data.
- Memory: 200 bitmaps × 10M bits = 250 MB (constant, không tăng theo users)
- Operations: O(1) per GETBIT/SETBIT
- Limitation: chỉ lưu boolean. Không thể store metadata per flag per user.

**Final recommendation**: 
- Nếu flags là boolean → Approach C (Bitmap) — best memory, O(1) operations
- Nếu flags có thể là non-boolean (string values) → Approach B với 2 Hashes split ≤ 128 fields

### Solution Reflection Questions

**Câu 1**: 
- Có lợi: write-once profile, fields cố định ở 200–300, không update thường xuyên. Increase để tránh hashtable overhead cho hash ổn định.
- Có hại: write-heavy workload với frequent updates → O(N) update cost tăng tuyến tính với threshold. Latency p99 spike nguy hiểm.

**Câu 2**: 
1. **Immediate** (trong 5 phút): Check `INFO memory` + `MEMORY STATS`. Identify top memory consumers. Nếu OOM imminent → scale out hoặc add replica để giảm memory pressure tạm thời.
2. **Short-term** (trong 1 giờ): Bật `activedefrag yes` (nếu chưa bật). Defrag sẽ chạy incremental khi fragmentation_ratio > 1.1. Monitor progress.
3. **Root cause fix**: Analyze fragmentation source — large key deletions, key expiry pattern, or allocator tuning. Consider restart with `stop-writes-on-bgsave-error` + proper config.

**Câu 3**: MEMORY USAGE returns nil:
1. Key không tồn tại → `EXISTS key` = 0. Check spelling, TTL expiry race condition.
2. Key đang expired nhưng chưa cleanup → `OBJECT IDLETIME key` > 0 confirm tồn tại.
3. Key là stream type với 0 entries → `TYPE key` confirm.

**Câu 4**: Encoding flip → memory spike → near-maxmemory Redis → OOM eviction → application retries → write storm → replication lag → cascading timeouts across services. Tình huống: Hash với 128 fields ở maxmemory threshold. Một batch job thêm 1 field → hashtable flip → 3x memory → OOM → Redis evicts 100K unrelated keys → cache miss storm → DB overload → latency spike trên toàn bộ hệ thống. Defense: monitor encoding state + maintain 20% headroom dưới maxmemory.
