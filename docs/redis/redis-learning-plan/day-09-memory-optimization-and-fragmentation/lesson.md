# Day 9: Memory Optimization & Fragmentation

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân biệt được external fragmentation vs internal fragmentation, giải thích được `mem_fragmentation_ratio` semantics và khi nào ratio < 1 là dấu hiệu nghiêm trọng (swap).
- Tune `activedefrag`, `active-defrag-*-bytes` để defragment mà không gây latency spike p99 trong giờ peak, benchmark được defrag cost trước khi enable production.
- Đo lường object overhead (SDS header, robj, dictEntry, listpack header) bằng `MEMORY USAGE`, `MEMORY STATS`, `DEBUG OBJECT`, từ đó estimate total instance memory chính xác hơn.
- Đề xuất memory optimization plan cho dataset 10M records: encoding tuning + key namespace strategy + application-layer compression, kèm benchmark estimate.
- Tránh được 5 production failure modes: defrag gây latency spike, jemalloc fragmentation không monitor, big key DEL blocking, `mem_fragmentation_ratio < 1` (swap), compression CPU saturation.

---

## 2. Vì sao cần học chủ đề này

### Incident thực tế: "Why is Redis using more memory than I told it?"

Một team e-commerce có cluster Redis 32GB cho session store. Monitoring thấy `used_memory_rss` = 57GB — cao hơn gần 2x so với `used_memory` = 32GB. `mem_fragmentation_ratio` = 1.78. Engineer's câu hỏi đầu tiên: "Tại sao Redis dùng 57GB trong khi tôi chỉ lưu 32GB?"

Root cause: workload có pattern insert/delete xen kẽ với many small values — jemalloc arena bị fragmentation nặng. Key churn cao: 80K deletes + 80K inserts mỗi giờ, allocation pattern không reuse freed memory efficiently.

Họ scale cluster từ 32GB → 64GB. Memory pressure giảm nhưng vấn đề nằm ở data model: Hash dùng hashtable encoding thay vì listpack, overhead 24 bytes/field thay vì 1-2 bytes. Không ai từng check `OBJECT ENCODING`. Sau khi tune `hash-max-listpack-entries` + split big Hash keys, memory giảm 45%, fragmentation ratio về 1.12.

**Lesson**: Ratio 1.78 không phải "Redis memory leak" — đó là fragmentation + encoding issue + key churn.

### Incident thực tế: Active Defrag Gây p99 Latency Spike

Một startup bật `activedefrag yes` mà không benchmark. Defrag threshold mặc định (`active-defrag-threshold-lower 10`) kích hoạt khi fragmentation ratio > 1.10 và tồn tại > 10 seconds. Trong giờ peak (80K ops/sec), defrag process chạy aggressive — p99 latency tăng từ 5ms → 200ms. Client timeouts → cascade failure → 30 phút incident.

Fix: `active-defrag-cycle-min 10` (giảm CPU budget cho defrag), `active-defrag-threshold-lower 100` (chỉ defrag khi ratio > 2.0), `active-defrag-ignore-bytes 100mb` (bỏ qua fragmentation dưới 100MB).

**Lesson**: Active defrag là double-edged sword — tắt thì fragmentation tích tụ, bật mà không tune thì latency spike.

### Incident thực tế: Snappy Compression Giảm 60% Memory Nhưng Tăng CPU 25%

Team analytics dùng Redis làm time-series buffer, mỗi record ~10KB JSON. Memory gần max. Họ implement application-layer Snappy compression: JSON → snappy compress → Redis String. Memory giảm 60% (10KB → 4KB compressed). Nhưng decompression overhead cho mỗi read: +2ms p99. Với 50K reads/sec → decompression CPU tăng 25%. Vấn đề: họ không benchmark read path, chỉ benchmark write path.

Fix: Dùng Redis Module RedisJSON thay vì compressed JSON strings — native representation, không compression overhead. Hoặc chấp nhận 25% CPU increase nếu memory constraint nghiêm trọng hơn.

**Lesson**: Compression trade-off là CPU vs memory — phải benchmark cả read và write path.

---

## 3. Kiến thức nền cần có

- **Day 5**: Redis encoding internals — listpack vs hashtable, SDS header, robj struct, dictEntry overhead, encoding threshold tuning.
- **Day 8**: Memory management — `maxmemory`, eviction policies, lazy expiration, memory pressure.
- Linux process memory: RSS (Resident Set Size) vs VSZ (Virtual Size), page size, mmap, malloc/free.

**Đặc biệt, bạn cần nhớ**:

```
used_memory         = logical data size (tổng bytes của tất cả keys + overhead nội bộ)
used_memory_rss     = RSS = thực tế bytes OS allocate cho process (bao gồm fragmentation)
mem_fragmentation_ratio = used_memory_rss / used_memory
```

Ratio > 1.0 = có external fragmentation (normal). Ratio < 1.0 = **DANGEROUS** — process đang bị swapped out.

---

## 4. Lý thuyết chi tiết

### 4.1. Memory Fragmentation: External vs Internal

**Internal fragmentation**: allocator cấp block lớn hơn request. VD: request 37 bytes → jemalloc round up 48 bytes → 11 bytes wasted inside block.

**External fragmentation**: free memory tồn tại nhưng không contiguous. VD: process freed 3 blocks × 16 bytes, nhưng new request cần 32 bytes contiguous → dù có 48 bytes free tổng cộng nhưng không đủ 32 bytes liên tiếp → allocator phải request thêm pages từ OS.

```
External Fragmentation Example:

Before allocations:
[ PAGE 1: 4KB free ] [ PAGE 2: 4KB free ] [ PAGE 3: 4KB free ]

After: alloc 5KB, free 3KB, alloc 8KB
[ PAGE 1: 5KB used | 11KB free ] [ PAGE 2: 8KB used ] [ PAGE 3: 3KB used | 1KB free ]

Free memory: 12KB total (3 pages)
But largest contiguous: PAGE 1 has 11KB, PAGE 3 has only 1KB
→ If need 12KB contiguous → must request new page
```

**Redis fragmentation causes**:

1. **Mix of small/large allocations**: SDS small strings → size class 32/48/64/96 bytes. Large objects → multi-page allocations. Jemalloc phải maintain nhiều size classes → fragmented free lists.
2. **Key churn**: INSERT → DELETE pattern. Freed memory returned to allocator's free list, không release pages về OS (jemalloc không release arenas back to OS by default). Next allocation reuse from free list → ok. Nhưng nếu size class free list empty → new page → fragmentation.
3. **OS page table overhead**: mmap allocations (VD: AOF file, persistence buffers) → RSS count includes page tables. `used_memory_rss` cao hơn `used_memory` một phần do page table metadata.
4. **Copy-on-write**: fork() cho BGSAVE → parent pages COW → kernel allocate new pages → RSS tăng → fragmentation tăng مؤقتاً.

### 4.2. Jemalloc — Tại sao Redis dùng jemalloc

Redis compile với jemalloc thay vì glibc malloc (`ptmalloc`) hoặc tcmalloc vì:

| Criteria | glibc malloc (ptmalloc) | tcmalloc (gperftools) | jemalloc |
|----------|------------------------|-----------------------|----------|
| Fragmentation | Cao (ptmalloc2 không tối ưu multi-thread) | Thấp | Rất thấp |
| Multi-thread scalability | Poor (arena contention) | Tốt | Tốt (TLS arenas) |
| Memory release to OS | Chậm, often never | Yes | Yes (arena purging) |
| Memory overhead | Medium | High (metadata) | Low |
| Production verified | Yes (Redis chose jemalloc) | Some | Yes |

**jemalloc internals**:

```
┌─────────────────────────────────────────────────────────────┐
│                      PROCESS HEAP                            │
│                                                             │
│  Arena 0 (thread 0)    Arena 1 (thread 1)    Arena N       │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────┐ │
│  │ 32B run      │       │ 64B run      │       │ 128B run │ │
│  │ [slab][slab] │       │ [slab][slab] │       │ [slab]   │ │
│  └──────────────┘       └──────────────┘       └──────────┘ │
│       Page 0                 Page 1             Page N       │
└─────────────────────────────────────────────────────────────┘
```

**Size classes** (jemalloc 5.x):

```
Size classes: 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128,
              160, 192, 224, 256, 320, 384, 448, 512,
              640, 768, 896, 1024, 1280, 1536, 1792, 2048,
              2560, 3072, 3584, 4096 (4KB = 1 page)
```

**Key jemalloc concepts**:

- **Arena**: Mỗi thread được assign một arena (thay vì lock contention trên global heap). Thread-local allocations → no lock. Default: 4 arenas × CPU (Redis process ~8-16 arenas).
- **Size class**: Allocation được round up lên nearest size class. 37 bytes → 48 bytes. 100 bytes → 128 bytes.
- **Slab**: Một hoặc nhiều contiguous pages chứa multiple size-class objects. VD: 4KB page chứa 256 × 16B objects (16B size class).
- **Run**: Một slab đang active. Free slots tracked via bitmap.
- **Chunk**: 4MB (or larger) memory block allocated from OS via mmap. Chứa multiple runs.

**jemalloc vs glibc malloc memory behavior**:

```
glibc: malloc(37) → 37 bytes allocated → internal fragmentation 0
       but: arena lock contention under multi-thread → throughput drop

jemalloc: malloc(37) → round to 48B → internal fragmentation 11B
         but: thread-local arena → no lock → 3-5x better throughput
```

### 4.3. `mem_fragmentation_ratio` Semantics

```bash
INFO memory | grep -E "used_memory|used_memory_rss|mem_fragmentation"
```

Output mẫu:

```
used_memory:33554432                    # 32MB logical data
used_memory_rss:58720256                # 56MB RSS (OS allocated)
mem_fragmentation_ratio:1.75            # 1.75 = 75% overhead
allocator_allocated:33562600
allocator_active:58720256
allocator_resident:58720256
```

**Interpretation**:

| Ratio | Meaning | Action |
|-------|---------|--------|
| 1.00–1.20 | Healthy | Normal |
| 1.20–1.50 | Moderate fragmentation | Monitor, consider defrag if persistent |
| 1.50–1.80 | High fragmentation | Enable defrag, check key churn pattern |
| 1.80–2.50 | Severe fragmentation | Urgent action, defrag + data model review |
| > 2.50 | Critical | Cluster scale-up + fragmentation fix |
| < 1.00 | **DANGEROUS: SWAP** | Immediate: reduce maxmemory, scale up, check swap |

**`ratio < 1.0` = SWAP**: Nếu `used_memory_rss < used_memory` → process pages đã bị swapped out. Swap in/out → latency spike 10-100ms per operation. Đây là **emergency** — không phải "memory optimization" issue mà là **capacity issue**.

**Các field `allocator_*`**:

```
allocator_allocated: logical bytes allocated by jemalloc (≈ used_memory)
allocator_active: bytes in active runs (≈ used_memory_rss for jemalloc)
allocator_resident: bytes resident in RAM (includes arenas + metadata)
```

### 4.4. `INFO memory` — Full Field Reference

```bash
redis-cli INFO memory
```

| Field | Bytes | Description |
|-------|-------|-------------|
| `used_memory` | 33,554,432 | Logical data size (keys + overhead) |
| `used_memory_human` | 32M | Human-readable |
| `used_memory_rss` | 58,720,256 | RSS — physical pages allocated by OS |
| `used_memory_peak` | 58,720,256 | Peak `used_memory` ever |
| `used_memory_dataset` | 30,000,000 | Data only (exclude overhead) |
| `used_memory_overhead` | 3,554,432 | Internal Redis overhead (robj, dict, etc.) |
| `used_memory_startup` | 1,048,576 | Startup memory (Redis binary + structures) |
| `mem_fragmentation_ratio` | 1.75 | RSS / used_memory |
| `mem_fragmentation_bytes` | 25,165,824 | RSS - used_memory (fragmentation in bytes) |
| `mem_allocator` | jemalloc-5.3.0 | Allocator library |
| `allocator_frag_ratio` | 1.75 | Internal fragmentation ratio |
| `allocator_frag_bytes` | 25,165,824 | Internal fragmentation bytes |
| `allocator_rss_ratio` | 1.00 | rss / active |
| `allocator_rss_bytes` | 0 | RSS overhead beyond allocator |
| `mem_fragmentation_ratio` | 1.75 | RSS / logical |
| `mem_not_counted_for_evict` | 0 | Memory excluded from eviction calc |
| `mem_clients_slaves` | 0 | Replication memory (replica buffers) |
| `mem_clients_normal` | 1,000,000 | Normal client buffers |
| `mem_aof_buffer` | 0 | AOF buffer size |
| `lazyfree_pending_objects` | 0 | Objects pending async deletion |

### 4.5. `MEMORY DOCTOR` — Reading Output

```bash
redis-cli MEMORY DOCTOR
```

Output examples và interpretation:

```
Hi Sam, I'm Redis Memory Doctor!
--- ACTIVE DEFAG STRATEGY RECOMMENDATION ---
Active defrag is DISABLED. You have a lot of waste due to fragmentation.
Current fragmentation ratio is 1.89 (89% wasted memory, 4GB out of 6GB).
Recommendation: Enable active defrag with:
  config set activedefrag yes
  config set active-defrag-threshold-lower 10
  config set active-defrag-threshold-upper 75
  config set active-defrag-cycle-min 10
  config set active-defrag-cycle-max 75
  config set active-defrag-ignore-bytes 100mb
```

**Output reading guide**:

```
Fragmentation < 1.5         → Healthy, no action needed
Fragmentation 1.5–2.0        → Warning: enable defrag or reduce key churn
Fragmentation > 2.0         → Critical: defrag + review data model
Fragmentation > 3.0          → Emergency: scale up + defrag + data model review
Active defrag DISABLED       → MEMORY DOCTOR sẽ recommend enable
Active defrag ENABLED        → MEMORY DOCTOR sẽ validate config adequacy
```

### 4.6. Active Defragmentation

**How it works**:

Active defragmentation là background process chạy trong Redis main thread (splitting work across events). Nó không fork process — chạy incrementally.

```
Active Defrag Flow:

while (fragmentation_threshold_met AND time_budget_available):
    dictEntry = get_next_dictEntry_to_move()
    if dictEntry.is_fragmented():
        # Allocate new slot in target arena
        new_ptr = jemalloc_allocate(target_size)
        # Copy data
        memcpy(new_ptr, dictEntry.ptr, dictEntry.size)
        # Update dict pointer
        dictEntry.ptr = new_ptr
        # Free old slot
        jemalloc_deallocate(old_ptr)
        # Move cursor
        cursor += 1
    else:
        cursor += 1
```

**Config parameters**:

| Config | Default | Effect |
|--------|---------|--------|
| `activedefrag` | `no` | Enable/disable active defrag |
| `active-defrag-threshold-lower` | `10` | Start defrag when fragmentation > 1.10 for > 10s |
| `active-defrag-threshold-upper` | `75` | Defrag aggressively when fragmentation > 1.75 |
| `active-defrag-ignore-bytes` | `100mb` | Ignore fragmentation < 100MB (avoid defrag on small waste) |
| `active-defrag-cycle-min` | `10` | Min % CPU time for defrag (10% = defrag slower, less impact) |
| `active-defrag-cycle-max` | `75` | Max % CPU time for defrag (75% = aggressive) |

**CPU cost**:

```
CPU% for defrag = active-defrag-cycle-max value (at peak)
With active-defrag-cycle-max 75:
  - During aggressive defrag: up to 75% of 1 CPU core
  - For 8-core server: max 9.4% total CPU overhead

With active-defrag-cycle-min 10, active-defrag-cycle-max 50:
  - More conservative: max 50% of 1 core = 6.25% total CPU
  - Defrag takes longer but less latency impact
```

**Latency impact**: Active defrag chạy trong main event loop, split across multiple events → mỗi event có thể thêm 1-5ms overhead. Với aggressive settings (`cycle-max 75`) + high fragmentation (> 2.0) + high traffic (50K+ ops/sec) → p99 latency spike 10-50ms.

**Safe production config for high-traffic systems**:

```txt
activedefrag yes
active-defrag-threshold-lower 100      # Only start when ratio > 2.0 (not 1.10)
active-defrag-threshold-upper 50       # Less aggressive upper threshold
active-defrag-ignore-bytes 100mb       # Ignore < 100MB fragmentation
active-defrag-cycle-min 10            # Min CPU budget
active-defrag-cycle-max 50            # Max 50% of 1 core
```

### 4.7. Big Key Impact on Memory

**DEL blocking**: `DEL` command trên big aggregate key (Hash, List, Set, Sorted Set) là **O(N)** — Redis phải traverse toàn bộ data structure trước khi free. VD: DEL một Hash với 1M fields → blocking ~200-500ms.

```
Timeline when DEL big key (O(N) blocking):

t=0ms:    DEL session:big_hash received
t=200ms:  Dict scan completes (1M entries freed)
t=200ms:  Memory freed, return OK
→ During 200ms: Redis blocked, all other commands wait
→ p99 latency spike = 200ms
```

**Non-blocking alternative**: `ASYNC` modifier (Redis 6.2+):

```txt
UNLINK session:big_hash   # Same as DEL but async (immediately return)
# Redis frees memory in background
```

**Replication impact**: Big key trên master được replicate khi replica `SYNC`. Nếu master có big key 500MB → replica sync = 500MB network transfer + memory allocation → replica lag spike.

**Cluster single-shard pressure**: Trên Redis Cluster, một big key nằm trên 1 shard → shard đó có memory pressure cao hơn các shard khác → không scale horizontally.

### 4.8. Object Overhead — The Hidden Memory

Mỗi Redis key-value pair có overhead ngoài data payload:

```
Per-key overhead breakdown:

┌────────────────────────────────────────────────────┐
│ Key Name SDS (3-63 bytes)                         │
│   sdshdr8: 3 bytes header + key_length            │
│   Example: "user:12345:profile" = 19 chars → 22B   │
├────────────────────────────────────────────────────┤
│ robj struct (16 bytes)                             │
│   type(4bits) + encoding(4bits) + lru(24bits)    │
│   + refcount(32bits) + *ptr(64bits)              │
├────────────────────────────────────────────────────┤
│ Value object overhead                              │
│   String: SDS header + data                       │
│   Hash:  dict struct (2×hashtable) + entries     │
│         per-entry: dictEntry (24B) + key SDS + val│
│   List:  quicklist node (32B) + listpack         │
├────────────────────────────────────────────────────┤
│ dictEntry per key (24 bytes, hashtable overhead)   │
│   *key ptr + *val ptr + next ptr + bucket ref     │
├────────────────────────────────────────────────────┤
│ Jemalloc rounding (size class → nearest)           │
│   37B → 48B, 100B → 128B, 200B → 256B            │
└────────────────────────────────────────────────────┘
```

**Overhead comparison per key**:

| Data Type | Data Payload | Overhead (approx) | Total per key |
|-----------|-------------|-----------------|---------------|
| String | 10 bytes | ~22B (SDS) + 16B (robj) + rounding → 48B | ~60B |
| String | 100 bytes | ~100B + 16B + rounding → 128B | ~140B |
| Hash (10 fields) | ~200 bytes | ~24B dictEntry + 10×(24B+SDS) + 16B robj | ~500B |
| Hash (100 fields) | ~2KB | ~24B + 100×(24B+SDS) + 16B robj + hashtable | ~3KB |
| Set member | 10 bytes | ~24B dictEntry + 16B robj + SDS = 48B | ~60B |
| List item (quicklist) | 10 bytes | ~32B node + ~20B listpack entry | ~60B |

**Practical implication**: 10M String keys × 60 bytes/key = 600MB. Nhưng nếu dùng Hash với 10 fields/key → 10M Hash × 500 bytes = 5GB. Data model choice có huge memory impact.

### 4.9. Application-Layer Compression

Khi value > 1KB, application-layer compression có thể giảm memory đáng kể.

**Compression decision tree**:

```
Value size < 512 bytes?
  YES → No compression (overhead > savings)
  NO  → Compress

  Value size > 10KB?
    YES → Compression recommended (60-80% savings)
    NO  → Benchmark first (some cases compress poorly)

  Value compressibility?
    YES (JSON, text, logs) → High savings (60-80%)
    NO (already compressed, binary) → Low savings (10-20%)
```

**Encoding/decoding flow**:

```
Application:
  Write path:
    JSON.stringify(obj) → "{\"userId\":1,...}"
      ↓
    zlib.deflate() or snappy.compress() → compressed Buffer
      ↓
    redis.Set(key, compressed_buffer)
      ↓
    used_memory: 400 bytes (vs 4000 bytes raw)

  Read path:
    redis.Get(key) → compressed Buffer
      ↓
    decompress() → JSON string
      ↓
    JSON.parse() → obj
      ↓
    +2-5ms latency per read (decompression)
```

### 4.10. Redis 7+ Memory Improvements

**listpack thay ziplist (Redis 7)**:
- Day 5 đã cover: listpack fix cascade update bug và tối ưu memory hơn ziplist.
- Redis 7+ hash-max-listpack-entries default = 128 (Redis 6: 512).
- Hash value threshold: 64 bytes (listpack) vs hashtable.

**SDS optimizations (Redis 7.2+)**:
- SDS pre-allocation strategy tối ưu hơn, giảm reallocation frequency.
- SDS binary size header thay đổi: sdshdr5 không còn dùng cho keys.

**Memory reporting improvements**:
- `used_memory_dataset` — data bytes không kể overhead
- `used_memory_overhead` — Redis internal overhead
- `allocator_frag_ratio` / `allocator_frag_bytes` — chia nhỏ fragmentation metrics

**Lazy free for big keys (UNLINK)**:
- `UNLINK` = `DEL` async (6.2+)
- `FLUSHDB ASYNC`, `FLUSHDB SYNC` (4.0+)

---

## 5. Trade-off Analysis

### Trade-off 1: Optimize Memory vs Complexity

| Approach | Memory Savings | Complexity | Risk | Khi nào dùng |
|----------|---------------|------------|------|-------------|
| Encoding tuning (listpack) | 50-80% | Thấp | Low (config change) | Profile data, small values |
| Key design (coarse-grained) | 30-60% | Trung bình | Medium (scan complexity) | Related data accessed together |
| Application compression | 40-80% | Cao (encode/decode) | Medium (CPU overhead) | Large values, CPU not bottleneck |
| Memory-efficient data type | 60-90% | Cao (redisign model) | High (rewrite code) | When memory is critical |
| Vertical scale | 100% | Thấp | Low (cost) | When budget available |

### Trade-off 2: Compression vs CPU Cost

| Library | Compression Ratio | Compress Speed | Decompress Speed | CPU Overhead | Best For |
|--------|-----------------|----------------|-----------------|-------------|---------|
| None (raw) | 1.0x | 0 | 0 | 0 | Values < 512B, CPU-critical |
| gzip (zlib) | 3-8x | Slow (50-200MB/s) | Medium (100-300MB/s) | High | Cold storage, archival |
| snappy | 1.5-2x | Very fast (500MB/s+) | Very fast (500MB/s+) | Low | Hot data, latency-sensitive |
| zstd | 2-5x | Fast (200-400MB/s) | Very fast (600MB/s+) | Low-Medium | Best balance |
| lz4 | 1.8-2.5x | Fastest (800MB/s+) | Fastest (800MB/s+) | Very low | Ultra-low latency |

**Compression benchmark (10KB JSON payload)**:

```
Library   | Compressed | Ratio | Compress μs | Decompress μs | CPU% read
---------|-----------|-------|------------|---------------|----------
Raw       | 10,240B   | 1.0x  | 0          | 0             | 0%
gzip -1  | 1,200B    | 8.5x  | 150μs      | 50μs          | 15%
snappy   | 5,800B    | 1.8x  | 30μs       | 20μs          | 3%
zstd -3  | 2,100B    | 4.9x  | 60μs       | 15μs          | 6%
lz4      | 5,200B    | 2.0x  | 20μs       | 10μs          | 2%
```

**Decision**: snappy/lz4 cho latency-sensitive (read-heavy). zstd cho balance (compression ratio + speed). gzip chỉ cho cold storage.

### Trade-off 3: Active Defrag ON vs OFF

| Aspect | Defrag OFF | Defrag ON (conservative) | Defrag ON (aggressive) |
|--------|-----------|-------------------------|----------------------|
| Latency impact | 0% | +1-5ms p99 | +10-50ms p99 |
| CPU overhead | 0% | +2-6% total CPU | +5-15% total CPU |
| Fragmentation | Grows over time | Controlled | Minimized |
| Memory waste | Grows | Minimal | Minimal |
| Risk | OOM from frag | Minimal | Latency spike |
| Config | None | threshold-lower 100, cycle-max 50 | threshold-lower 10, cycle-max 75 |
| Recommended for | Low key churn, small instance | High-traffic prod | Low-traffic staging |

**Recommendation**: Bật defrag với conservative config (`threshold-lower 100`, `cycle-max 50`) cho production. Monitor latency trong 1 tuần trước khi tăng aggression.

### Trade-off 4: Bigger Redis Node vs Better Data Modeling

| Approach | Pros | Cons | Cost | Complexity |
|----------|------|------|------|------------|
| Vertical scale (bigger node) | Fast fix, no code change | Cost scales non-linearly, single point | $$$ | Low |
| Encoding tuning | Free, config only | Limited savings | $0 | Low |
| Data model redesign | 50-80% savings | Code rewrite required | Dev time | High |
| Compression | 40-80% savings | CPU overhead, code change | Dev time | Medium |
| Sharding | Scale horizontally | Operational complexity | $$$$ | High |

**Rule**: Luôn thử encoding tuning trước (miễn phí, không risk). Sau đó mới xem xét data model change hoặc vertical scale.

### Trade-off 5: Small Objects Many Keys vs Big Object Few Keys

| Aspect | Many Small Keys | Few Big Keys |
|--------|----------------|--------------|
| Key overhead | 1M × (24B dictEntry + 20B SDS) = 44MB | 1 × overhead = negligible |
| Command efficiency | Multiple round trips (MGET helps) | 1 round trip per object |
| Memory (1M records × 10 fields) | ~600-800MB (hashtable) | ~250-350MB (listpack Hash) |
| Hot key risk | Low (spread) | High (1 key = all data) |
| Atomicity | MULTI/EXEC for all fields | 1 command |
| Sharding (Cluster) | Natural distribution | Must use hash tags |
| Scan efficiency | KEYS pattern (EVIL) or SCAN | HSCAN cursor-based |

### Trade-off 6: listpack Threshold Cao vs Thấp

| Threshold | Memory | Lookup Speed | Update Speed | Best For |
|-----------|--------|-------------|-------------|---------|
| listpack entries: 128 (default) | Compact | O(N) but N small | O(N) small | General |
| listpack entries: 512 | Very compact | O(512) moderate | O(512) slower | Write-once |
| listpack entries: 10000 | Most compact | O(10000) slow | O(10000) very slow | DO NOT USE |
| listpack entries: 64 | Less compact | O(64) fast | O(64) fast | Write-heavy |

---

## 6. Best Solution & Best Practices

### The Memory Optimization Playbook

**Step 1: Baseline (trước khi optimize)**

```bash
# Baseline metrics
redis-cli INFO memory > baseline.txt
redis-cli MEMORY STATS > stats-baseline.txt
redis-cli MEMORY DOCTOR > doctor-baseline.txt

# Check fragmentation
redis-cli INFO memory | grep -E "mem_fragmentation|used_memory_rss|used_memory"
```

**Step 2: Encoding check**

```bash
# Sample encoding distribution
redis-cli --scan | head -1000 | xargs -I{} redis-cli OBJECT ENCODING {} | sort | uniq -c | sort -rn
```

**Step 3: Big key identification**

```bash
redis-cli --bigkeys        # Scan for biggest keys by type
redis-cli --memkeys        # Scan for biggest keys by memory
```

**Step 4: Optimize by priority**

```
Priority 1 (free, fast): Encoding tuning
  - hash-max-listpack-entries: 128 → 256 (if write-once)
  - set-max-intset-entries: 512 (default OK)
  - zset-max-listpack-entries: 128 (default OK)

Priority 2 (low effort): Key design
  - Merge multiple small strings into Hash
  - Use appropriate data structures

Priority 3 (medium effort): Application-layer compression
  - Compress values > 5KB with snappy/zstd
  - Add serialize/deserialize layer

Priority 4 (high effort): Data model redesign
  - Re-architect for memory efficiency
  - Consider Redis Modules (RedisJSON, RedisSearch)
```

### Production Config Template — Memory-Intensive Workload

```txt
# File: redis-memory-intensive.conf

# Memory
maxmemory 8gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Encoding
hash-max-listpack-entries 256
hash-max-listpack-value 64
zset-max-listpack-entries 128
set-max-intset-entries 512

# Active Defrag (conservative for high-traffic)
activedefrag yes
active-defrag-threshold-lower 100
active-defrag-threshold-upper 75
active-defrag-ignore-bytes 100mb
active-defrag-cycle-min 10
active-defrag-cycle-max 50

# Persistence (reduce memory overhead)
save 3600 1 300 100
appendonly yes
appendfsync everysec

# Client buffers
client-output-buffer-limit normal 256mb 64mb 60
client-output-buffer-limit replica 64mb 16mb 60

# Lazy free
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
replica-lazy-flush yes
```

### Anti-patterns

| Anti-pattern | Vấn đề | Fix |
|---|---|---|
| Bật defrag mà không tune threshold | Latency spike trong giờ peak | Conservative config: threshold-lower 100 |
| Monitoring only `used_memory`, not `used_memory_rss` | Không phát hiện fragmentation | Monitor both + ratio |
| Dùng DEL trên big key | Blocking 200-500ms | Dùng UNLINK |
| Compression không benchmark read path | CPU saturation on reads | Benchmark cả read + write |
| Tăng threshold quá cao | O(N) update latency spike | Benchmark trước |
| Vertical scale thay vì optimize | Chi phí cao, không fix root cause | Optimize data model trước |

---

## 7. Performance Considerations

### Memory Estimation Formula

```
Total Redis Memory ≈

  Σ(key_name_SDS_size + 16B robj)
+ Σ(value_overhead + value_payload)
+ Σ(dictEntry_overhead_if_hashtable)
+ Σ(encoding_struct_overhead)
+ allocator_metadata_overhead
+ instance_overhead
+ fragmentation_padding

More specifically:
  Total = used_memory_dataset
        + used_memory_overhead
        + (used_memory_rss - used_memory)  [fragmentation]
        + client_buffers
        + lua_heap
        + persistence_buffers
        + fragmentation_external
```

### Fragmentation Impact on Performance

```
Fragmentation ratio = 1.5:
  → 33% of RSS is wasted (ghost pages)
  → CPU cache miss rate increases (non-contiguous memory)
  → Performance impact: 5-15% slower operations

Fragmentation ratio = 2.0:
  → 50% of RSS is wasted
  → CPU cache miss rate significant
  → Performance impact: 15-30% slower operations

Fragmentation ratio = 2.5:
  → 60% of RSS is wasted
  → Memory pressure on OS level
  → Performance impact: 30-50% slower + OOM risk
```

### Latency Numbers (realistic production)

| Operation | Normal | With 1.5 frag | With 2.0 frag |
|-----------|--------|--------------|--------------|
| HSET small (listpack) | 0.05ms | 0.06ms | 0.07ms |
| HGETALL 100 fields | 0.3ms | 0.4ms | 0.5ms |
| SCAN 1000 keys | 1.0ms | 1.3ms | 1.8ms |
| DEL big Hash 1M fields | 200ms | 250ms | 300ms |
| BGSAVE fork (32GB) | 500ms | 600ms | 700ms |

---

## 8. Production Failure Modes

### Failure Mode 1: Fragmentation Không Monitor Gây OOM

**Trigger**: Key churn cao (insert/delete) → jemalloc fragmentation tích tụ → `used_memory_rss` tăng dần → đến maxmemory → OOM eviction.

**Dấu hiệu**:
```bash
# Fragmentation ratio tăng dần theo thời gian
redis-cli INFO memory | grep mem_fragmentation_ratio
# 1.2 → 1.4 → 1.6 → 1.8 → ...
```

**Debug**:
```bash
# Check fragmentation trend
watch -n 60 'redis-cli INFO memory | grep -E "mem_fragmentation|evicted_keys"'

# Check key churn
redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```

**Fix**: Enable active defrag + reduce key churn pattern.

### Failure Mode 2: Active Defrag Gây Latency Spike

**Trigger**: Defrag threshold mặc định kích hoạt trong peak hour → aggressive defrag → p99 spike.

**Dấu hiệu**: Latency spike đều đặn mỗi giờ (lúc defrag kích hoạt).

**Fix**:
```txt
active-defrag-threshold-lower 100    # Chỉ defrag khi ratio > 2.0
active-defrag-cycle-max 50           # Giảm aggression
active-defrag-ignore-bytes 100mb    # Bỏ qua small frag
```

### Failure Mode 3: `ratio < 1.0` — Swap

**Trigger**: `maxmemory` gần bằng RAM available → OS swap out Redis pages → `used_memory_rss < used_memory`.

**Dấu hiệu**:
```bash
free -h
# Swap used: 2GB, 5GB... (non-zero = swap active)

redis-cli INFO memory
# mem_fragmentation_ratio: 0.95  ← DANGER
```

**Fix**: Emergency scale up RAM, reduce `maxmemory`, add instance node.

### Failure Mode 4: Big Key DEL Blocking

**Trigger**: `DEL big_hash` trên production → Redis blocked 200-500ms.

**Dấu hiệu**: Periodic latency spike khi cleanup job chạy.

**Fix**: Dùng `UNLINK` thay vì `DEL`. Hoặc:
```txt
UNLINK session:old_key   # Non-blocking delete
# Redis frees memory in background
```

### Failure Mode 5: Compression CPU Saturation on Reads

**Trigger**: Application-layer compression với high read volume (50K reads/sec) → decompression CPU overhead 25% → CPU saturation.

**Dấu hiệu**: CPU% on application server tăng 20-30% khi traffic cao.

**Fix**: Benchmark trước. Nếu compression necessary: dùng lz4/snappy (fast decompression). Hoặc dùng Redis native compression (Redis 7+ có Stream compression support).

---

## 9. Real-world Examples

### Twitter — Fragmentation Management at Scale

Twitter Redis cluster với 100GB+ dataset, key churn pattern: timeline cache với 1 giờ TTL. 10 triệu key expires mỗi giờ → fragmentation cao.

**Solution**:
1. Active defrag enabled với conservative config
2. Timeline keys grouped in Hash → reduce key count
3. Monitoring: `mem_fragmentation_ratio` alert at 1.5

**Result**: Ratio maintained 1.1-1.3. No OOM events. Active defrag CPU overhead ~3%.

### Discord — Memory Optimization for Message Cache

Discord cần cache hàng tỷ messages. Raw JSON per message = 200-500 bytes. Với 10B messages → 2-5TB memory.

**Solution**:
1. Custom binary encoding: MessagePack thay vì JSON → 40% smaller
2. Group messages in Hash: `channel:{id}:messages` Hash với field = message_id
3. Sorted Set cho message ordering (score = timestamp)

**Result**: Memory reduction 60% (MessagePack + Hash grouping). Compression thêm 30% → total 75% reduction.

**Lesson**: Multiple optimization layers multiplicative.

### Shopify — Active Defrag Configuration for Production

Shopify Redis production với high churn → fragmentation ratio tăng 1.2 → 1.9 trong 3 tuần.

**Their approach**:
1. Không bật defrag mặc định (latency risk)
2. Scheduled defrag: maintenance window 2-4 AM → enable aggressive defrag
3. Monitoring: tự động disable defrag khi traffic > 10K ops/sec

**Lesson**: Defrag không phải always-on. Scheduled approach an toàn hơn cho high-traffic.

### Uber — Application-Layer Compression for Time-Series

Uber dùng Redis cho real-time metrics buffer. Mỗi metric: 50 data points × 8 bytes = 400 bytes.

**Solution**:
1. snappy compression: 400B → 180B
2. Batch writes: 1 write per second cho 1000 metrics = compression efficient
3. Read pattern: aggregated queries → decompress per query

**Result**: Memory reduction 55%. CPU overhead 8% for decompression. Acceptable trade-off.

---

## 10. Common Pitfalls

1. **Monitor only `used_memory`, not `used_memory_rss`**: Không thấy fragmentation. Ratio có thể = 2.0 nhưng `used_memory` vẫn dưới maxmemory.

2. **Bật active defrag mà không benchmark latency**: Defrag chạy trong main event loop → latency spike có thể không acceptable cho p99 SLA.

3. **Dùng `DEL` trên big key trong production**: Blocking operation. Luôn dùng `UNLINK`.

4. **Compression không benchmark read path**: Write benchmark show savings, nhưng read path decompression overhead gây latency spike.

5. **`mem_fragmentation_ratio < 1.0` không nhận ra là SWAP**: Đây là emergency, không phải fragmentation issue.

6. **Estimate memory = `MEMORY USAGE key` × key count**: Quên jemalloc size class rounding. 37B → 48B. Scale lên 10M keys → 110MB estimate vs 480MB actual.

7. **Tăng encoding threshold quá cao mà không benchmark write path**: `hash-max-listpack-entries: 10000` → O(N) update với N=10000 → latency spike.

8. **Nghĩ fragmentation ratio 1.8 = memory leak**: Không phải leak, đó là external fragmentation + encoding + key churn. Fix bằng defrag + data model optimization, không phải restart.

---

## 11. Câu hỏi tự kiểm tra

**Câu 1**: `INFO memory` cho thấy `used_memory: 10GB`, `used_memory_rss: 17GB`, `mem_fragmentation_ratio: 1.70`. Giải thích con số này. Bước đầu tiên để fix?

**Câu 2**: Production workload: 50K ops/sec, `mem_fragmentation_ratio` = 1.55. Bạn có bật `activedefrag yes` không? Nếu có, dùng config nào? Nếu không, tại sao?

**Câu 3**: Dataset: 10 triệu user profiles, mỗi profile 50 fields. Thiết kế data model để tối ưu memory, biết rằng mỗi field update thường xuyên. So sánh: String keys, Hash listpack, Hash hashtable.

**Câu 4**: Bạn phát hiện `mem_fragmentation_ratio = 0.92`. Điều gì đang xảy ra? Đây là fragmentation issue hay capacity issue? Fix như thế nào?

**Câu 5**: Bạn có 10GB dataset với values ~5KB mỗi value (JSON). Đề xuất compression strategy. Cần benchmark những gì trước khi deploy?

**Câu 6**: Explain sự khác biệt giữa `used_memory`, `used_memory_rss`, `allocator_allocated`, `allocator_active`. Khi nào chúng khác nhau nhiều nhất?

**Câu 7**: DEL vs UNLINK. Khi nào dùng cái nào? DEL có bao giờ được ưu tiên không?

---

### Đáp án

**Câu 1**: `mem_fragmentation_ratio = 1.70` nghĩa là RSS (17GB) cao hơn logical memory (10GB) 70%. Nguyên nhân: external fragmentation (jemalloc arenas + page allocation pattern) + potential COW from BGSAVE. Bước đầu: `MEMORY DOCTOR` → xem recommendation. Nếu ratio > 1.5: bật active defrag conservative + check key churn pattern.

**Câu 2**: Khuyến nghị **không bật defrag ngay trong peak hour** nếu chỉ ratio 1.55 và 50K ops/sec. Thay vào đó: (1) xem xét data model optimization (encoding tuning), (2) giảm key churn, (3) nếu defrag cần thiết: bật conservative ngoài peak (`threshold-lower 100`, `cycle-max 50`) + monitor latency trong 24h.

**Câu 3**:
- **String keys** (`profile:{userId}:{field}`): 10M × 50 keys = 500M keys → dictEntry overhead alone = 500M × 24B = 12GB → Impossible.
- **Hash listpack** (50 fields): 10M Hashs × 50 fields → 50 < 128 threshold → listpack. Memory: ~250 bytes/hash = 2.5GB. Update: O(N) với N=50 → acceptable.
- **Hash hashtable** (50 fields, value > 64B): 50 < 128 nhưng phải check value size. Nếu values > 64B → hashtable. Memory: ~600 bytes/hash = 6GB.
- **Recommendation**: Hash listpack với value split. VD: `profile:{id}:core` (20 fields, listpack) + `profile:{id}:extended` (30 fields, listpack).

**Câu 4**: `ratio = 0.92` = **SWAP**. `used_memory_rss < used_memory` → process pages đã bị swapped out. Đây là **capacity issue**, không phải fragmentation. Fix: (1) Emergency: scale up RAM, (2) Reduce `maxmemory`, (3) Add replica/shard để spread load, (4) Review memory leak (nếu `used_memory_peak` cũng cao → leak).

**Câu 5**:
- **Compression candidates**: snappy (fast, low CPU), zstd (best ratio + speed balance), lz4 (fastest)
- **Benchmark cần thiết**:
  1. Compress/decompress latency per operation (μs)
  2. Throughput with compression (ops/sec) vs without
  3. CPU% application server (not Redis — compression ở app layer)
  4. Memory reduction (compressed size / original size)
  5. Read path latency p50/p95/p99 với decompression
  6. Memory freed if compression deployed
- **Decision threshold**: Nếu p99 latency tăng < 5% và CPU tăng < 15% → deploy.

**Câu 6**:
- `used_memory`: Logical data bytes (tổng keys + overhead nội bộ Redis)
- `used_memory_rss`: RSS = pages in RAM × page size. Bao gồm fragmentation, page tables, COW pages.
- `allocator_allocated`: Bytes allocated by jemalloc (≈ used_memory)
- `allocator_active`: Bytes in jemalloc active runs (≈ used_memory_rss for jemalloc)
- Khác nhau nhiều nhất khi: (1) External fragmentation cao (RSS >> allocated), (2) COW pages từ BGSAVE (extra pages), (3) Page table overhead.

**Câu 7**:
- `UNLINK` = async delete: immediately return, Redis frees memory in background → **recommend for all big keys**
- `DEL` = synchronous blocking: traverses entire data structure → **chỉ dùng khi**: (1) Key size nhỏ (< 1KB), (2) Cần guaranteed delete completion trước khi proceed (VD: test, cleanup), (3) Redis version < 6.2 (không có UNLINK).
- Production rule: luôn dùng `UNLINK` trừ khi có lý do cụ thể dùng `DEL`.
