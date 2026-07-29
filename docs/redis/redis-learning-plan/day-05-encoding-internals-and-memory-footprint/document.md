# Day 5: Encoding Internals & Memory Footprint — Reference Document

## 1. Encoding Threshold Reference — Redis 7.x

### Default Thresholds

| Data Type     | Encoding 1        | Threshold 1                              | Encoding 2  | Threshold 2                         |
|---------------|-------------------|------------------------------------------|-------------|-------------------------------------|
| String        | raw               | value > 44 bytes (interned if ≤44)       | int         | value là integer fit 64-bit         |
| Hash          | listpack          | fields ≤ 128 **AND** value ≤ 64 bytes     | hashtable   | fields > 128 **OR** value > 64B     |
| List          | quicklist         | always (Redis 7+)                        | —           | —                                   |
| Set           | intset            | all integers **AND** size ≤ 512          | listpack    | strings + size ≤ 128 (Redis 7.2+)  |
| Set           | hashtable         | otherwise                                | —           | —                                   |
| Sorted Set    | listpack          | entries ≤ 128 **AND** value ≤ 64 bytes   | skiplist    | entries > 128 **OR** value > 64B   |

### Config Reference

```yaml
# Hash
hash-max-listpack-entries: 128    # max fields for listpack encoding
hash-max-listpack-value: 64        # max value bytes for listpack encoding

# List (Redis 7+: quicklist, node size controlled by listpack-size)
# -2 = 8KB per listpack node (default)
# -1 = 16KB per listpack node
# positive = max entries per listpack node
list-max-listpack-size: -2

# Set
set-max-intset-entries: 512        # max elements for intset encoding
set-max-listpack-entries: 128     # max entries for listpack set (Redis 7.2+)

# Sorted Set
zset-max-listpack-entries: 128     # max entries for listpack encoding
zset-max-listpack-value: 64        # max value bytes for listpack encoding
```

### Encoding Transition Rules

**Hash — encoding flip conditions**:
```txt
listpack → hashtable: fields > 128 OR value_bytes > 64
hashtable → listpack: fields ≤ 128 AND ALL values ≤ 64 (requires HSET DEL pattern to shrink, not automatic)
```

**Set — encoding flip conditions**:
```txt
intset → listpack: add string element (Redis 7.2+)
intset → hashtable: add string OR size > 512
listpack → hashtable: size > 128 (Redis 7.2+)
hashtable → intset: NOT possible (one-way transition)
```

**Sorted Set — encoding flip conditions**:
```txt
listpack → skiplist: entries > 128 OR value_bytes > 64
skiplist → listpack: NOT automatic (requires data shrink below threshold)
```

---

## 2. Memory Overhead Reference

### Per-Object Overhead

| Component                | Size (bytes)  | Notes                                   |
|--------------------------|---------------|----------------------------------------|
| robj struct              | 16            | type(4bit) + encoding(4bit) + lru(24bit) + refcount(32bit) + ptr(8B) |
| Key name SDS header      | 3–19          | sdshdr8(3) to sdshdr64(17) + null byte |
| Key name SDS buffer      | key_length    | variable                               |
| dictEntry (hashtable)    | 24            | key ptr + value ptr + next ptr          |
| SDS string value         | 3–17 + len    | header + actual data                    |
| robj pointer for value   | 8             | inside dictEntry value field            |

### Jemalloc Size Classes (typical, 64-bit)

| Requested size  | Size class  | Waste per allocation |
|-----------------|-------------|---------------------|
| 1–8 bytes       | 8           | up to 7 bytes       |
| 9–16 bytes      | 16          | up to 7 bytes       |
| 17–24 bytes     | 24          | up to 7 bytes       |
| 25–32 bytes     | 32          | up to 7 bytes       |
| 33–48 bytes     | 48          | up to 15 bytes      |
| 49–64 bytes     | 64          | up to 15 bytes      |
| 65–80 bytes     | 80          | up to 15 bytes      |
| 81–96 bytes     | 96          | up to 15 bytes      |
| 97–128 bytes    | 128         | up to 31 bytes      |
| 129–192 bytes   | 192         | up to 63 bytes      |
| 193–256 bytes   | 256         | up to 63 bytes      |
| 257–384 bytes   | 384         | up to 127 bytes     |
| 385–512 bytes   | 512         | up to 127 bytes     |
| 513–768 bytes   | 768         | up to 255 bytes     |
| 769–1024 bytes  | 1024        | up to 255 bytes     |

### Encoding-Specific Overhead

| Encoding    | Per-entry overhead | Breakdown                          |
|-------------|--------------------|-------------------------------------|
| intset      | 2 bytes            | 2B encoding + 2B length header     |
| intset      | 2/4/8 bytes/entry | depends on encoding (int16/32/64)   |
| listpack    | 1–5 bytes/entry   | encoding byte + length byte(s)      |
| hashtable   | 24 bytes/entry    | dictEntry (no embedded data)       |
| skiplist    | 32–64 bytes/node  | score(8B) + dictEntry(24B) + levels |
| SDS raw     | 3–17 bytes        | header                             |
| quicklist   | ~40 bytes/node    | listpack node pointer + metadata    |

### Memory Comparison: 1M User Objects × 10 Fields

| Model                              | Encoding      | Estimated Memory | Breakdown                            |
|------------------------------------|---------------|------------------|--------------------------------------|
| String keys (10M total keys)       | raw + SDS     | ~1.0–1.2 GB     | 10M × (16B robj + 20B key + 10B val) |
| Hash listpack (1M Hashs)           | listpack      | ~250–350 MB     | 1M × (16B robj + 20B key + 250B lp) |
| Hash hashtable (1M Hashs)          | hashtable     | ~550–700 MB     | 1M × (16B robj + 20B key + 500B dict) |
| 1 big Hash 10M fields              | hashtable     | ~800 MB+        | 10M fields × (24B dictEntry + SDS)  |
| JSON blob String per user          | raw           | ~600–800 MB     | 1M × (16B robj + 20B key + 600B val) |

---

## 3. Command Cheat Sheet

### Inspection Commands

```bash
# OBJECT ENCODING — xem encoding hiện tại của value
OBJECT ENCODING key
# Output examples:
# (nil)              → key không tồn tại
# "int"              → integer string
# "raw"              → raw SDS string > 44 bytes
# "embstr"           → embedded string ≤ 44 bytes (read-only, one allocation)
# "quicklist"        → list (Redis 7)
# "ziplist"          → list (Redis 6)
# "hashtable"        → hash / set / sorted set (large)
# "listpack"         → hash / set / sorted set (compact, Redis 7+)
# "skiplist"         → sorted set (large)
# "intset"           → set (all integers)

# OBJECT FREQUENCY — xem access frequency (LFU mode)
OBJECT FREQ key

# OBJECT IDLETIME — xem seconds từ lần access cuối
OBJECT IDLETIME key

# OBJECT REFCOUNT — xem reference count
OBJECT REFCOUNT key

# DEBUG OBJECT — full object details (DEV only, not production)
# Redis 7 disables DEBUG by default; start dev Redis with --enable-debug-command yes/local.
DEBUG OBJECT key
# Output fields:
# key: key name
# refcount: reference count
# encoding: current encoding
# serializedlength: serialized length
# lru_seconds: LRU timestamp
# lru_clock: server LRU clock
# pointer: raw memory address (DEBUG only)
# listpack_bytes: listpack specific (Redis 7+)
# listpack_entries: number of entries
# listpack_backwards_size: backwards traversal overhead

# MEMORY USAGE — accurate memory cho single key
MEMORY USAGE key [SAMPLES count]
# SAMPLES 0 = full scan (accurate nhưng chậm với big key)
# SAMPLES 5 = default (sample 5 entries, fast)

# MEMORY DOCTOR — diagnose memory issues
MEMORY DOCTOR
# Output: advice on fragmentation, allocator, memory leaks

# MEMORY STATS — allocator + Redis memory stats
MEMORY STATS
# Key fields:
# peak.allocated: peak memory allocated
# total.allocated: current total
# startup.allocated: Redis startup memory
# replication.backlog: replication backlog memory
# clients.slaves: replica client buffers
# clients.normal: normal client buffers
# aof.buffer: AOF rewrite buffer

# Production-safe alternative:
OBJECT ENCODING user:123
MEMORY USAGE user:123 SAMPLES 0
```

### Config Commands

```bash
# Xem threshold hiện tại
CONFIG GET hash-max-listpack-entries
CONFIG GET hash-max-listpack-value
CONFIG GET list-max-listpack-size
CONFIG GET set-max-intset-entries
CONFIG GET set-max-listpack-entries
CONFIG GET zset-max-listpack-entries
CONFIG GET zset-max-listpack-value

# Set threshold (runtime, not persisted)
CONFIG SET hash-max-listpack-entries 256
CONFIG SET hash-max-listpack-value 64

# Get all memory-related config
CONFIG GET *max-listpack*
CONFIG GET *max-intset*
```

### INFO Commands

```bash
# Memory section
INFO memory
# Key fields:
# used_memory: Redis internal memory allocator (jemalloc)
# used_memory_rss: Resident Set Size (physical memory)
# mem_fragmentation_ratio: used_memory_rss / used_memory (> 1.5 = problem)
# mem_fragmentation_bytes: absolute fragmentation bytes
# allocator_resident: allocator internal resident memory
# allocator_active: allocator active pages
# allocator_frag_ratio: allocator fragmentation
# allocator_frag_bytes: allocator fragmentation bytes
# allocator_rss_ratio: RSS / allocator active
# allocator_rss_bytes: RSS overhead
# maxmemory: maxmemory config
# maxmemory_policy: eviction policy
# maxmemory碎片: Chinese comment, ignore
# lazyfree_pending_objects: objects pending lazy free
```

### Scan Commands

```bash
# Scan keys without KEYS (safe in production)
SCAN 0 COUNT 1000
HSCAN hashkey 0 COUNT 100
SSCAN setkey 0 COUNT 100
ZSCAN zsetkey 0 COUNT 100

# OBJECT ENCODING for all keys matching pattern (use with SCAN, not KEYS)
redis-cli --scan | head -1000 | xargs -I {} redis-cli OBJECT ENCODING {}
```

---

## 4. TypeScript Code Reference — ioredis

### 4.1. Measure Memory Usage Across Data Models

```typescript
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379, lazyConnect: true });

async function memoryForKey(key: string): Promise<number> {
  const result = await redis.call('MEMORY', 'USAGE', key, 'SAMPLES', '0');
  return result as number;
}

async function memoryForPattern(pattern: string): Promise<Map<string, number>> {
  const results = new Map<string, number>();
  let cursor = '0';
  do {
    const [nextCursor, keys] = await redis.call('SCAN', cursor, 'MATCH', pattern, 'COUNT', 1000) as [string, string[]];
    cursor = nextCursor;
    for (const key of keys) {
      try {
        const bytes = await memoryForKey(key);
        results.set(key, bytes);
      } catch {
        // key may have expired
      }
    }
  } while (cursor !== '0');
  return results;
}

async function compareDataModels() {
  await redis.connect();
  await redis.flushdb();

  const N = 10_000;

  // Model A: 10000 Hashes (10 fields/hash, listpack)
  console.log('\n=== Model A: 10K Hashes (10 fields/hash) ===');
  const t0 = Date.now();
  for (let i = 0; i < N; i++) {
    const fields: string[] = [];
    for (let f = 0; f < 10; f++) {
      fields.push(`field${f}`, `value${f}_${i}`);
    }
    await redis.call('HSET', `model_a:user:${i}`, ...fields);
  }
  const t1 = Date.now();
  const memA = await redis.call('INFO', 'memory');
  const usedA = parseInt((memA as string).match(/used_memory:(\d+)/)?.[1] ?? '0');
  const encA = await redis.call('OBJECT', 'ENCODING', 'model_a:user:0');
  console.log(`Write time: ${t1 - t0}ms`);
  console.log(`Encoding: ${encA}`);
  console.log(`Total memory: ${(usedA / 1024 / 1024).toFixed(2)} MB`);

  // Model B: 100K String keys (1 string/key)
  await redis.flushdb();
  console.log('\n=== Model B: 100K String keys ===');
  const t2 = Date.now();
  for (let i = 0; i < N * 10; i++) {
    await redis.call('SET', `model_b:user:${Math.floor(i / 10)}:field${i % 10}`, `value${i}`);
  }
  const t3 = Date.now();
  const memB = await redis.call('INFO', 'memory');
  const usedB = parseInt((memB as string).match(/used_memory:(\d+)/)?.[1] ?? '0');
  console.log(`Write time: ${t3 - t2}ms`);
  console.log(`Total memory: ${(usedB / 1024 / 1024).toFixed(2)} MB`);

  await redis.quit();
}

compareDataModels().catch(console.error);
```

### 4.2. Encoding Flip Observer

```typescript
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });

type Encoding = 'listpack' | 'hashtable' | 'intset' | 'skiplist' | 'quicklist' | 'raw' | 'embstr' | 'int';

interface EncodingSnapshot {
  key: string;
  encoding: Encoding;
  memoryBytes: number;
  timestamp: number;
}

async function snapshotEncoding(key: string): Promise<EncodingSnapshot> {
  const [encoding, memoryBytes] = await Promise.all([
    redis.call('OBJECT', 'ENCODING', key),
    redis.call('MEMORY', 'USAGE', key, 'SAMPLES', '0'),
  ]);
  return {
    key,
    encoding: encoding as Encoding,
    memoryBytes: memoryBytes as number,
    timestamp: Date.now(),
  };
}

async function observeEncodingFlip(
  key: string,
  triggerFn: () => Promise<void>,
  thresholdFields: number
): Promise<EncodingSnapshot[]> {
  const snapshots: EncodingSnapshot[] = [];
  snapshots.push(await snapshotEncoding(key));

  console.log(`Initial encoding: ${snapshots[0].encoding} (${snapshots[0].memoryBytes} bytes)`);

  await triggerFn();
  const after = await snapshotEncoding(key);
  snapshots.push(after);

  const flipped = snapshots[0].encoding !== after.encoding;
  if (flipped) {
    console.log(`⚠ ENCODING FLIP: ${snapshots[0].encoding} → ${after.encoding}`);
    console.log(`Memory delta: ${(after.memoryBytes - snapshots[0].memoryBytes).toLocaleString()} bytes`);
    console.log(`Memory multiplier: ${(after.memoryBytes / snapshots[0].memoryBytes).toFixed(2)}x`);
  } else {
    console.log(`No encoding flip. Still: ${after.encoding}`);
  }

  return snapshots;
}

async function demoFlip() {
  await redis.connect();
  await redis.flushdb();

  const key = 'test:flip:demo';

  await observeEncodingFlip(
    key,
    async () => {
      // Add 128 fields (should stay listpack)
      for (let i = 0; i < 128; i++) {
        await redis.call('HSET', key, `field_${i}`, `value_${i}`);
      }
    },
    128
  );

  // Now add field 129 — should flip to hashtable
  await observeEncodingFlip(
    key,
    async () => {
      await redis.call('HSET', key, 'field_129', 'value_129_longer_than_64_bytes_payload_here');
    },
    128
  );

  await redis.quit();
}

demoFlip().catch(console.error);
```

### 4.3. Full Instance Memory Analysis

```typescript
import Redis from 'ioredis';

interface MemoryReport {
  usedMemory: number;
  usedMemoryRss: number;
  fragmentationRatio: number;
  maxmemory: number;
  evictionPolicy: string;
  totalKeys: number;
  peakMemory: number;
  allocatorFragRatio: number;
  allocatorRssRatio: number;
  overheadMeta: number;
}

async function getMemoryReport(): Promise<MemoryReport> {
  const info = await redis.call('INFO', 'memory');
  const infoStr = info as string;

  const parse = (key: string) =>
    parseInt(infoStr.match(new RegExp(`${key}:(\\d+)`))?.[1] ?? '0');

  const keyCount = await redis.call('DBSIZE');

  return {
    usedMemory: parse('used_memory'),
    usedMemoryRss: parse('used_memory_rss'),
    fragmentationRatio: parseFloat(infoStr.match(/mem_fragmentation_ratio:([\d.]+)/)?.[1] ?? '0'),
    maxmemory: parse('maxmemory'),
    evictionPolicy: infoStr.match(/maxmemory_policy:(\w+)/)?.[1] ?? 'none',
    totalKeys: keyCount as number,
    peakMemory: parse('allocator.allocated'),
    allocatorFragRatio: parseFloat(infoStr.match(/allocator.frag.ratio:([\d.]+)/)?.[1] ?? '1.0'),
    allocatorRssRatio: parseFloat(infoStr.match(/allocator.rss.ratio:([\d.]+)/)?.[1] ?? '1.0'),
    overheadMeta: parse('overhead.total'),
  };
}

async function printReport(report: MemoryReport) {
  console.log('\n=== Redis Memory Report ===');
  console.log(`Keys count:           ${report.totalKeys.toLocaleString()}`);
  console.log(`used_memory:          ${(report.usedMemory / 1024 / 1024).toFixed(2)} MB (allocator)`);
  console.log(`used_memory_rss:      ${(report.usedMemoryRss / 1024 / 1024).toFixed(2)} MB (RSS, physical)`);
  console.log(`Fragmentation ratio:  ${report.fragmentationRatio.toFixed(2)}x  ${report.fragmentationRatio > 1.5 ? '⚠ HIGH' : '✓ OK'}`);
  console.log(`maxmemory:            ${report.maxmemory > 0 ? `${(report.maxmemory / 1024 / 1024).toFixed(2)} MB` : 'unlimited'}`);
  console.log(`eviction_policy:      ${report.evictionPolicy}`);
  console.log(`allocator frag ratio: ${report.allocatorFragRatio.toFixed(2)}x`);
  console.log(`allocator RSS ratio:  ${report.allocatorRssRatio.toFixed(2)}x`);
  console.log(`overhead.meta:        ${(report.overheadMeta / 1024 / 1024).toFixed(2)} MB`);
  const wasted = report.usedMemoryRss - report.usedMemory;
  console.log(`Estimated waste:      ${(wasted / 1024 / 1024).toFixed(2)} MB (RSS - used_memory)`);
}

const redis = new Redis({ host: 'localhost', port: 6379 });
redis.connect().then(async () => {
  const report = await getMemoryReport();
  await printReport(report);
  await redis.quit();
}).catch(console.error);
```

---

## 5. Docker Compose — Redis 7 Standalone

```yaml
version: '3.8'
services:
  redis:
    image: redis:7.2
    container_name: redis-day5
    command: >
      redis-server
      --save ""
      --appendonly no
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --hash-max-listpack-entries 128
      --hash-max-listpack-value 64
      --list-max-listpack-size -2
      --set-max-intset-entries 512
      --zset-max-listpack-entries 128
      --zset-max-listpack-value 64
      --enable-debug-command yes
      --activerehashing yes
      --activedefrag yes
      --slowlog-log-slower-than 1000
      --slowlog-max-len 128
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    ulimits:
      nofile:
        soft: 65536
        hard: 65536

volumes:
  redis-data:
```

---

## 6. Links & References

### Official Documentation
- https://redis.io/docs/management/optimization/memory-optimization
- https://redis.io/docs/reference/internals/encoding
- https://redis.io/commands/object-encoding
- https://redis.io/commands/memory-usage
- https://redis.io/commands/debug-object
- https://redis.io/docs/reference/server-configuration

### Redis Source Code
- `src/object.c` — OBJECT ENCODING, MEMORY USAGE implementation
- `src/server.h` — robj struct definition, encoding constants
- `src/sds.h` — SDS implementation
- `src/listpack.c` — listpack implementation
- `src/ziplist.c` — ziplist (Redis 6 compatibility)
- `src/t_zset.c` — skiplist + ziplist/listpack switch
- `src/dict.c` — hashtable with incremental rehashing
- `src/quicklist.c` — quicklist (Redis 7+)
- `src/intset.c` — intset implementation

### Blog Posts & Engineering Articles
- antirez (Salvatore Sanfilippo), "Redis internals: SDS", blog.antirez.com
- antirez, "Optimizing Redis Memory Usage", oldblog.antirez.com
- "Redis Memory Optimization at Twitter" — Twitter Engineering Blog
- "Pinterest Redis Cache Footprint Optimization" — Pinterest Engineering Blog (2014)
- "Redis listpack" — Redis Labs blog introducing listpack in Redis 7
- "Understanding Redis Memory Fragmentation" — DataDog tech blog

### Books
- "Redis in Action" — Josiah L. Carlson (Manning)
- "The Redis Book" — Redis.io official documentation
