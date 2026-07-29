# Day 8: Memory Management & Eviction

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân biệt được 4 khái niệm memory trong Redis: `used_memory`, `used_memory_rss`, `used_memory_dataset`, `maxmemory` — biết cái nào dùng để monitor eviction và cái nào dùng để plan capacity.
- Phân tích được cơ chế sample-based LRU và LFU trong Redis: tại sao không phải true LRU/LFU, `maxmemory-samples` ảnh hưởng thế nào đến accuracy vs CPU cost.
- So sánh được 8 eviction policies bằng bảng trade-off, chọn đúng policy cho 3 use case cụ thể: cache, session, leaderboard.
- Chẩn đoán được eviction incident: volatile-lru evict 0 keys, OOM write error với noeviction, LFU counter "stuck" — root cause và fix cụ thể.
- Thiết kế eviction config production cho API cache với Pareto workload: LRU vs LFU hit rate benchmark, `maxmemory-samples` tuning.

---

## 2. Vì sao cần học chủ đề này

### Incident thực tế 1: DevOps set `maxmemory` nhưng quên `maxmemory-policy` → OOM write error

Một team dùng Redis làm API response cache cho e-commerce. Họ set `maxmemory 10gb` vì instance có 16GB RAM. Không set eviction policy → default là `noeviction`. Khi Redis đầy (10GB), `SET` request tiếp theo trả về `OOM command not allowed when used memory > maxmemory`. Tất cả cache write fail → toàn bộ traffic hit database → database overload → cascade failure. Root cause: không ai check default eviction policy.

Sai lầm phổ biến: developer nghĩ `maxmemory` là "soft limit" hoặc tự động eviction, không biết `noeviction` là default.

### Incident thực tế 2: `volatile-lru` evict 0 keys vì không có key nào có TTL

Một startup dùng Redis làm session store. Họ set `maxmemory-policy volatile-lru` vì "chỉ evict session keys có TTL". Session keys thực tế không có TTL (hoặc TTL = 0 = vĩnh viễn). Khi Redis đầy, `volatile-lru` scan 0 keys → evict 0 keys → OOM → tất cả session write fail. Incident kéo dài 45 phút trước khi được phát hiện.

Sai lầm: `volatile-*` policies chỉ hoạt động trên keys có TTL set. Nếu tất cả keys không có TTL → không có gì để evict.

### Incident thực tế 3: LFU counter "stuck" — hit rate giảm sau vài ngày

Một CDN provider dùng Redis với `allkeys-lfu` cho cache. Sau 3 ngày, hit rate giảm từ 95% xuống 60%. Investigation: `lfu-log-factor` mặc định = 10. Với workload thực tế, counter chỉ tăng tối đa ~10 lần/giờ. Key được access 100 lần/giờ vẫn không được đẩy lên top của eviction list. LFU counter không reflect frequency thực tế → eviction policy evict "nhầm" keys.

Root cause: `lfu-log-factor` quá cao cho workload đó.

**Bottom line**: Eviction policy là nơi nhiều team "thiết kế đúng" nhưng vận hành sai. Không phải vì thiếu kiến thức, mà vì không test eviction behavior trước khi production.

---

## 3. Kiến thức nền cần có

- **Day 1**: Redis single-threaded, event loop, in-memory storage
- **Day 2**: String, Hash, List, Set, Sorted Set operations
- **Day 4**: Key naming, TTL strategy (`EXPIRE`, `TTL`)
- **Day 5**: Redis object model (`robj` struct với `lru` field 24 bits), memory overhead per key-value, encoding internals (listpack, hashtable)
- **Day 6**: Persistence không thay thế eviction — RDB/AOF là backup, không phải mechanism để giải phóng memory khi Redis đầy

**Lưu ý quan trọng**: Persistence (RDB/AOF) và Eviction là 2 mechanism hoàn toàn khác nhau:
- Persistence = backup data ra disk để khôi phục sau restart
- Eviction = xóa keys trong memory khi `used_memory > maxmemory`

Redis đầy → eviction xảy ra **trước khi** persistence mechanism chạy. Chúng không liên quan đến nhau.

---

## 4. Lý thuyết chi tiết

### 4.1. `maxmemory` — Semantics

`maxmemory` là hard limit cho `used_memory`. Khi `used_memory` vượt `maxmemory`, Redis trigger eviction loop.

**4 khái niệm memory cần phân biệt**:

| Metric | Ý nghĩa | Dùng khi nào |
|--------|---------|--------------|
| `used_memory` | Logical memory Redis allocated (allocator) | Monitor eviction trigger |
| `used_memory_rss` (RSS) | Physical memory OS gave Redis (includes fragmentation, jemalloc metadata) | Capacity planning, OOM risk |
| `used_memory_dataset` | Memory chỉ dành cho dataset (used_memory - overhead keys/ fragmentation) | Real dataset size |
| `maxmemory` | Config limit (byte count) | Sizing, eviction trigger threshold |

```
used_memory (logical) vs used_memory_rss (physical)

allocated by Redis     physical pages from OS
        │                    │
        ▼                    ▼
  ┌──────────┐          ┌──────────┐
  │ allocator│          │  memory  │
  │  512MB   │  ─────►  │  pages   │
  │ (logical)│          │  700MB   │  ← RSS = 700MB (fragmentation)
  └──────────┘          └──────────┘
  used_memory=512MB     mem_fragmentation_ratio=1.37
```

**Eviction trigger**: So sánh `used_memory` vs `maxmemory`. **Không phải** `used_memory_rss` vs `maxmemory`.

```bash
# Nếu maxmemory = 10GB:
#   used_memory = 10.1GB → TRIGGER eviction (used_memory > maxmemory)
#   used_memory_rss = 13GB → kernel OOM có thể kill Redis
```

**Khi nào trigger eviction**: Sau mỗi write command, Redis check `used_memory > maxmemory`. Nếu true → chạy eviction loop trước khi serve request tiếp theo. Eviction chạy trong cùng event loop → **blocking event loop cho tới khi đủ keys evicted**.

### 4.2. 8 Eviction Policies

```
Eviction Policies Tree:

Eviction
├── noeviction          → reject all writes, read OK
├── allkeys-lru         → LRU eviction trên ALL keys
├── volatile-lru        → LRU eviction trên keys CÓ TTL
├── allkeys-lfu         → LFU eviction trên ALL keys
├── volatile-lfu        → LFU eviction trên keys CÓ TTL
├── allkeys-random      → random eviction trên ALL keys
├── volatile-random     → random eviction trên keys CÓ TTL
└── volatile-ttl        → random eviction trên keys CÓ TTL, ưu tiên key có TTL nhỏ nhất
```

**Use case map**:

| Policy | Dataset | Best for |
|--------|---------|---------|
| `noeviction` | any | data store không chấp nhận mất data (idempotency, rate limit counter) |
| `allkeys-lru` | all keys | generic cache, hot data có recency pattern |
| `volatile-lru` | mixed (TTL + no-TTL) | session store (TTL sessions + persistent hot data) |
| `allkeys-lfu` | all keys | cache với frequency pattern rõ ràng (API response, CDN) |
| `volatile-lfu` | mixed | cache với TTL phần lớn, persistent data phần nhỏ |
| `allkeys-random` | all keys | sampling cache, load test, khi recency/frequency không quan trọng |
| `volatile-random` | mixed | backup eviction khi không có key nào có TTL |
| `volatile-ttl` | keys with TTL | temporary data store, priority cache entry |

### 4.3. Sample-based LRU — Implementation

Redis **không implement true LRU**. True LRU cần doubly-linked list cho O(1) move-to-head → memory overhead gấp đôi cho mỗi key. Thay vào đó, Redis dùng **approximated LRU** qua sampling.

**24-bit LRU clock**:

```
robj structure (from redisObject):
  unsigned lru:LRU_BITS;  // 24 bits → 16M possible values

LRU clock ticks every 1 second (server.unixtime / LRU_CLOCK_RESOLUTION)
max value = 2^24 - 1 = 16,777,215 (wraps around)
```

**Sample-based algorithm** (`src/evict.c`):

```c
// Simplified eviction loop pseudocode:
evictionLoop() {
    while (server.memory_over_limit) {
        // 1. Sample maxmemory-samples keys randomly
        for (int i = 0; i < server.maxmemory_samples; i++) {
            key = randomKey();
            sampleKeys[bestIdx] = key;  // track best candidate
        }

        // 2. Pick key with OLDEST LRU value (longest time since access)
        victim = findKeyWithOldestLRU(sampleKeys);

        // 3. Delete victim
        deleteKey(victim);
        freedBytes += estimateSize(victim);
    }
}
```

**Default sample size = 5**:

```
maxmemory-samples = 5 (default):

Dataset: 1M keys
Policy: allkeys-lru

Round 1: Sample 5 random keys → evict 1 (oldest)
Round 2: Sample 5 random keys → evict 1 (oldest)
...


Accuracy trade-off:
  samples = 3  → fast but may evict recently-used key
  samples = 10 → accurate but slower (CPU cost per eviction)
  samples = 50 → near-true LRU, but eviction loop takes longer
```

**ASCII diagram — Eviction Loop**:

```
┌──────────────────────────────────────────────────────┐
│  WRITE command arrives                               │
│    │                                                 │
│    ▼                                                 │
│  Check: used_memory > maxmemory?                    │
│    ├── No  → serve command normally                │
│    └── Yes → trigger eviction loop                 │
│              │                                      │
│              ▼                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │  while (used_memory > maxmemory):           │   │
│  │    samples = RANDOM_KEY(maxmemory_samples)   │   │
│  │    victim = KEY_WITH_OLDEST_LRU(samples)    │   │
│  │    DELETE(victim)                           │   │
│  │    freed += SIZE(victim)                    │   │
│  │    if (freed >= needed) break               │   │
│  └─────────────────────────────────────────────┘   │
│              │                                      │
│              ▼                                      │
│  Eviction complete → serve command                  │
└──────────────────────────────────────────────────────┘
```

**Gotcha về LRU accuracy**: Với `maxmemory-samples = 5` và 1M keys, accuracy rất thấp. Mỗi eviction chỉ check 5 keys trong 1M. Key được access 10 giây trước có thể không được sampled trong 100 eviction rounds → vẫn bị evict nhầm. Tăng samples lên 50 → accuracy tốt hơn nhưng eviction loop tốn nhiều CPU hơn.

### 4.4. TTL Behavior — Lazy Expiration vs Active Expiration

Redis dùng 2 cơ chế expire keys:

**Lazy expiration** (khi access key):

```
Client: GET user:session:123
    │
    ▼
Redis checks TTL of user:session:123
    │
    ├── TTL > 0    → return value (key chưa hết hạn)
    │
    └── TTL <= 0   → DELETE key immediately (lazy expiration)
                     → return nil (key not found)
```

**Active expiration** (background loop):

```
Every hz tick (default hz = 10 → every 100ms):
    │
    ▼
Redis samples up to 20 keys per database (REDBITS_EXPIRELOOKUPS_PER_CRON)
    │
    ▼
For each sampled key WITH TTL:
    │
    ├── TTL expired → DELETE key (via lazy expiration mechanism)
    │
    └── TTL not expired → no action
    │
    ▼
Move to next database (up to 16 DBs)
```

**Key insight về active expiration**:
- **Không bao giờ scan toàn bộ keyspace** — chỉ sample 20 keys/100ms/DB
- Với 1M keys có TTL → expire có thể mất **rất lâu** (1M / 20 per 100ms = 5,000 seconds = 83 phút)
- **Lazy expiration là primary expiration mechanism** — active expiration chỉ là "best effort" cleanup
- Nếu key có TTL nhưng không bao giờ được accessed → lazy expiration không bao giờ chạy → key tồn tại cho tới khi active expiration sample nó

**`hz` config impact**:

| `hz` value | Timer tick | Expire scan rate | CPU overhead |
|------------|-----------|-----------------|-------------|
| 1 | 1000ms | 20 keys/DB/s | Very low |
| 10 (default) | 100ms | 200 keys/DB/s | Low |
| 100 | 10ms | 2000 keys/DB/s | Moderate |
| 500 | 2ms | 10000 keys/DB/s | High — risk event loop blocking |

**`hz` quá cao có thể gây latency** vì mỗi timer tick chiếm event loop. Recommendation: `hz = 10` (default), tăng lên `hz = 100` chỉ khi có nhiều expired keys cần dọn dẹp.

### 4.5. LFU Implementation — Log Counter

Redis 4.0+ giới thiệu LFU eviction policy. Thay vì track recency, LFU track **frequency**.

**LFU counter = log counter (8-bit)**:

```
Counter value: 0–255 (8 bits)

LFU formula (from src/object.c):
  counter = counter + 1                     if rand() < prob
  counter = counter - 1                     if (decay needed and rand() < 0.01)

Where prob = 1.0 / pow(sliding_window, counter / lfu_log_factor)

Example (lfu-log-factor=10):
  counter=0  → prob = 1/1    ≈ 100% (access → counter increment nearly guaranteed)
  counter=5  → prob = 1/316  ≈ 0.3% (need ~316 accesses to maintain counter=5)
  counter=10 → prob = 1/100,000 ≈ 0.001% (very high frequency needed)
```

**`lfu-decay-time`**: Counter giảm theo thời gian. Default = 1 minute. Nghĩa là: nếu key không được access trong `lfu-decay-time` phút, counter giảm 1 đơn vị.

```
lfu-decay-time = 1 minute:

Key accessed at t=0 → counter=5
Key NOT accessed for 5 minutes → counter=0 (5 × 1-minute decay)
Key accessed at t=6min → counter becomes 1-5 (depending on probability)
```

**`lfu-log-factor` impact**:

| `lfu-log-factor` | Counter range (effective) | Best for |
|-----------------|-------------------------|---------|
| 1 | 0–255, fast saturation | Very high frequency keys (>1000 hits/hour) |
| 10 (default) | 0–50, moderate | General cache (10–100 hits/hour) |
| 100 | 0–15, slow growth | Low-frequency keys, keys that should stay longer |
| 1000 | 0–5, very slow | Almost never increment, keys should almost never be evicted |

**`OBJECT FREQ` — Inspect LFU counter**:

```txt
OBJECT FREQ user:123
```
Returns the current LFU counter value of a key. Useful for debugging LFU behavior and tuning `lfu-log-factor`.

**`OBJECT IDLETIME`** — How long since last access:

```txt
OBJECT IDLETIME user:123
```
Returns seconds since last access. Useful for debugging LRU behavior. **Warning**: accessing the key to check IDLETIME resets it to 0.

### 4.6. `volatile-*` — Gotcha khi không có TTL keys

**Critical gotcha**: `volatile-lru`, `volatile-lfu`, `volatile-random`, `volatile-ttl` chỉ hoạt động trên keys **có TTL set**. Nếu không có key nào có TTL → eviction loop chạy 0 iterations → `used_memory` vẫn > `maxmemory` → Redis tiếp tục reject writes (hoặc OOM error).

```
Scenario: Session store với all volatile-*

Keys in Redis:
  session:user1 → TTL=1800s  (SETEX session:user1 1800 ...)
  session:user2 → TTL=1600s
  user:profile:1 → NO TTL    ← NOT considered by volatile-lru
  config:app    → NO TTL

When Redis is full:
  volatile-lru → only evict session:user1 or session:user2
  allkeys-lru  → evict ANY key (including user:profile:1)

If ONLY non-TTL keys exist:
  volatile-lru → 0 keys evicted
  allkeys-lru  → evict oldest non-TTL key
```

**Production rule**: Nếu dùng `volatile-*`, luôn verify rằng keys bạn muốn evict thực sự có TTL. Dùng `redis-cli --scan` + `TTL` để audit keyspace.

### 4.7. `noeviction` — OOM Behavior

Khi `maxmemory-policy = noeviction` và `used_memory > maxmemory`:

```
SET new_key "value"
    │
    ▼
Redis: "OOM command not allowed when used memory > maxmemory"
    │
    ▼
Client receives: (error) OOM command not allowed when used memory > maxmemory
```

**Lệnh bị ảnh hưởng**: `SET`, `SETNX`, `APPEND`, `LPUSH`, `HSET`, `ZADD`, ... (tất cả commands thay đổi memory).

**Lệnh vẫn hoạt động**: `GET`, `SCAN`, `DBSIZE`, `INFO` (read-only commands).

**Use case đúng cho noeviction**: Data store mà không accept bất kỳ data loss nào (VD: idempotency key, rate limit counter, unique constraint). Nhưng phải monitor `used_memory` và scale trước khi đầy.

### 4.8. Redis OOM vs Kernel OOM — Phân biệt quan trọng

```
Redis maxmemory eviction loop:
  used_memory > maxmemory → Redis deletes keys
  → in-process memory management
  → application-level behavior
  → evicts data Redis knows about

Kernel OOM killer:
  RSS > available RAM → kernel kills process (SIGKILL)
  → Redis process killed
  → data loss (if no persistence)
  → Redis unavailable
  → no graceful degradation
```

**Memory pressure scenario**:

```
Dataset: 12GB, maxmemory: 12GB, Instance RAM: 16GB

Normal:   used_memory=10GB, RSS=13GB, fragmentation=1.3x

Under pressure:
  used_memory=11.9GB  → Redis eviction loop starts (maxmemory-policy=volatile-lru)
  evicted 0 keys (no TTL keys) → used_memory stays 11.9GB
  used_memory > maxmemory → write commands return OOM error

Worst case (fragmentation spike):
  jemalloc defrag → RSS jumps to 15.5GB
  Kernel OOM killer triggered
  Redis killed → total data loss if no persistence
```

**Monitor both**:
```bash
# Redis eviction (in-process)
redis-cli INFO memory | grep -E "used_memory|maxmemory|evicted_keys"

# Kernel OOM
dmesg | grep -i redis | grep -i "out of memory"
```

---

## 5. Trade-off Analysis

### 5.1. LRU vs LFU

| Criteria | LRU (allkeys-lru / volatile-lru) | LFU (allkeys-lfu / volatile-lfu) |
|----------|-----------------------------------|----------------------------------|
| Workload pattern | Recency (frequently recently-used keys) | Frequency (most frequently accessed keys) |
| Implementation | Sample-based (24-bit LRU clock) | Log counter (8-bit, probabilistic) |
| CPU cost | Low (sample + compare LRU values) | Low-medium (probability calculation per access) |
| Memory overhead | ~0 (uses existing lru field) | ~0 (uses existing lru field) |
| Hit rate accuracy | Good when recency = relevance | Good when frequency = relevance |
| Cold-start behavior | All new keys look fresh → evicted immediately | New keys start at counter=0 → evicted first |
| Best for | Temporal cache (user feed, recent items) | Stable hot set (CDN, API response, search results) |
| Worst for | Bursty traffic (all keys accessed once) | High-churn workload (all keys have similar frequency) |
| Counter "stuck" issue | No (LRU always updates on access) | Yes (LFU counter saturates; `lfu-log-factor` too high = slow growth) |

### 5.2. allkeys vs volatile

| Criteria | allkeys-* (LRU/LFU/RANDOM) | volatile-* (LRU/LFU/RANDOM/TTL) |
|----------|----------------------------|--------------------------------|
| Key pool | ALL keys in dataset | Only keys with TTL set |
| Eviction scope | Broadest (any key) | Narrow (only TTL keys) |
| Risk | May evict persistent data (data without TTL) | No keys to evict if no TTL → OOM despite policy |
| Use when | All data is cache-like (rebuildable) | Mix of persistent + temporary data |
| Best for | Pure cache | Session store with persistent hot data |
| Validation | Always has keys to evict | MUST verify keys have TTL before using |

### 5.3. noeviction vs eviction

| Criteria | noeviction | eviction (LRU/LFU/RANDOM) |
|----------|-----------|---------------------------|
| Write behavior | Reject with OOM error | Accept, evict as needed |
| Read behavior | Full read capability | Full read capability |
| Data safety | No data loss (unless kernel OOM) | Potential data loss (evicted keys gone) |
| Operational risk | Write failures during pressure | Silent data loss (no client error) |
| Use when | Source of truth, data store | Cache (data is rebuildable) |
| Requirement | Capacity monitoring + scale policy | Cache warmer for cold start |

### 5.4. Cache correctness vs availability

| Criteria | Strict cache correctness | Availability-first |
|----------|------------------------|-------------------|
| Behavior | Reject write if near maxmemory | Evict old data, accept write |
| Data freshness | Higher (evict based on age/frequency) | Lower (evict aggressively on pressure) |
| Write failure rate | 0% (reject) or 100% (OOM) | ~0% (eviction absorbs pressure) |
| User experience | Requests fail during pressure | Requests succeed, some stale/miss |
| Best for | Idempotency, counters, financial data | Generic cache, CDN, API response |

### 5.5. `maxmemory-samples` — Accuracy vs CPU

| Samples | Eviction accuracy | CPU cost per eviction round | p99 latency impact |
|---------|-----------------|----------------------------|--------------------|
| 3 | Low (~0.3% of dataset sampled) | Minimal | Negligible |
| 5 (default) | Low-medium | Low | Negligible |
| 10 | Medium | Low-medium | ~0.1ms |
| 20 | Medium-high | Medium | ~0.2ms |
| 50 | High (~5% of dataset) | Medium-high | ~0.5ms |
| 100 | Near-true LRU | High | ~1ms |

**Key insight**: Increasing samples from 5 to 50 improves accuracy significantly but adds per-eviction CPU overhead. The event loop is blocked during eviction — if eviction loop takes 10ms with samples=50, every write command during that period sees +10ms latency.

**Recommendation**:
- General cache: default 5 (sufficient)
- High-value cache (CDN, expensive computation): 10–20
- Extreme accuracy needed: 50 (benchmark p99 latency first)

---

## 6. Best Solution & Best Practices

### Theo Scenario

#### API Response Cache (80/20 Pareto workload — hot 20% keys = 80% traffic)

```txt
maxmemory 10gb
maxmemory-policy allkeys-lfu
maxmemory-samples 10
lfu-log-factor 10          # default — adjust based on hit rate
lfu-decay-time 5           # counter decay every 5 minutes (default 1)
```

**Tại sao allkeys-lfu**: Pareto workload → hot keys được access rất nhiều lần. LFU giữ hot keys lâu hơn LRU. LRU evict hot key mới access gần đây nhưng ít tần suất.

#### Session Store (user sessions, TTL = 30 phút)

```txt
maxmemory 8gb
maxmemory-policy volatile-lru
maxmemory-samples 5
```

**Tại sao volatile-lru**: Sessions có TTL = 30 phút. Eviction chỉ chọn trong session keys. Non-session data (rate limit counters, hot configs) không bị evict.

**Validation bắt buộc**: Kiểm tra tất cả session keys thực sự có TTL. Nếu developer dùng `SET` thay vì `SETEX` → `volatile-lru` = 0 evictions → OOM.

#### Idempotency Store (idempotency tokens, không chấp nhận mất data)

```txt
maxmemory 2gb
maxmemory-policy noeviction
# IMPORTANT: maxmemory is a safety net, not the primary protection
# Primary protection: capacity monitoring + scale trigger
```

**Tại sao noeviction**: Idempotency token mất = có thể double-charge. Tuy nhiên, `noeviction` không giải quyết kernel OOM. Cần monitor `used_memory` và scale khi > 80% maxmemory.

#### Leaderboard / Sorted Set Cache

```txt
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 5
```

**Tại sao allkeys-lru**: Leaderboard data không có TTL tự nhiên (sorted set update score liên tục). Dùng LRU vì user có xu hướng query top ranks thường xuyên (recency pattern).

#### Mixed Data (sessions + persistent cache)

```txt
maxmemory 12gb
maxmemory-policy allkeys-lru
maxmemory-samples 10
# VÀ: separate Redis instances
# Instance 1: volatile-lru for sessions (TTL keys)
# Instance 2: allkeys-lru for persistent cache
```

**Best practice**: Không mix volatile và allkeys trong cùng instance khi có thể. Dùng 2 Redis instances riêng.

### Anti-patterns

| Anti-pattern | Vấn đề | Fix |
|-------------|--------|-----|
| Dùng `noeviction` cho cache | Write fail khi Redis đầy → cascade failure | Dùng `allkeys-lru` hoặc `allkeys-lfu` |
| Dùng `volatile-lru` mà không verify TTL | 0 eviction khi Redis đầy | Audit keyspace: `redis-cli --scan \| head -1000 \| xargs redis-cli TTL` |
| Set `maxmemory` = 100% RAM | No headroom for COW, fragmentation | Set `maxmemory` = 70-80% of available RAM |
| Set `maxmemory-samples` = 100 mà không benchmark | Eviction loop blocking event loop 5-10ms | Benchmark p99 latency, increase gradually |
| Dùng `volatile-ttl` mà không hiểu behavior | Keys với TTL ngắn bị evict quá nhanh | Chỉ dùng khi TTL đã represent priority |
| Không monitor `evicted_keys` counter | Không biết eviction xảy ra | Alert khi `evicted_keys > 0` |

---

## 7. Performance Considerations

### 7.1. Eviction Loop Latency

**Blocking behavior**: Eviction loop chạy trong main event loop. **Event loop bị blocked** cho tới khi đủ keys evicted.

```
Normal write path:
  command → event loop → execute → response
           (~0.1–0.5ms per command)

Write during eviction:
  command → event loop → used_memory > maxmemory
           → eviction loop (samples + delete)
           → response
           (~0.1–5ms additional per command under pressure)
```

**Worst case**: 1000 keys cần evict, `maxmemory-samples = 50` → eviction loop samples 50 keys × 20 iterations = 1000 key checks → ~10-50ms blocking.

### 7.2. Per-write Eviction Overhead

```bash
# Scenario: Redis 95% full, eviction happening

p99 latency WITHOUT eviction:   ~0.5ms
p99 latency WITH eviction:       ~1-5ms
p99 latency SEVERE eviction:    ~10-50ms (eviction loop takes long)

# Key factor: how much memory over maxmemory?
```

**Rule**: Monitor `evicted_keys` rate. If > 1000/sec → eviction overhead is measurable in p99 latency.

### 7.3. `maxmemory-samples` CPU Cost

```go
// Cost breakdown per eviction round:
samples := 5   // default
for i := 0; i < samples; i++ {
    key := randKey()           // O(1) — dictGetRandomKey()
    checkLRU(key)              // O(1) — read lru field
}
bestKey := findOldest()        // O(samples) — linear scan
delete(bestKey)                // O(1) for string, O(N) for hash/list

Total: O(samples) = O(5) negligible per eviction round
```

**With 50 samples**: O(50) per eviction round. Still negligible per round, but noticeable if 1000 eviction rounds needed.

### 7.4. `hz` Impact on Expiration

```
hz = 10 (default):
  Timer fires every 100ms
  20 keys sampled per DB = 200 keys/second per DB
  With 1M keys → full scan in 5000 seconds = 83 minutes

hz = 100:
  Timer fires every 10ms
  2000 keys/second per DB
  Full scan: 500 seconds = 8.3 minutes

hz = 500:
  Timer fires every 2ms
  10000 keys/second per DB
  Full scan: 100 seconds = 1.6 minutes
  Risk: timer overhead vs actual benefit
```

**Recommendation**: Keep `hz = 10` unless you have evidence of expired keys accumulating. Monitor `expired_keys` counter in `INFO stats`.

### 7.5. Memory Overhead of Eviction Metadata

Redis **không store thêm metadata** cho eviction. LRU/LFU values reuse existing `lru` field (24 bits) trong `robj` struct. No additional memory overhead per key.

```
robj struct:
  type:4 + encoding:4 + lru:24 + refcount:32 + ptr:64 = 128 bits = 16 bytes
  lru field: shared between LRU and LFU modes (repurposed)
```

---

## 8. Production Failure Modes

### 8.1. OOM Write Error với `noeviction`

**Root cause**: Default eviction policy là `noeviction`. Dev set `maxmemory` nhưng không set policy → writes fail.

**Dấu hiệu**: Client logs có `OOM command not allowed when used memory > maxmemory`. Application cascading failures → database overload.

**Debug**:
```bash
redis-cli INFO memory | grep -E "used_memory|maxmemory|evicted_keys"
# used_memory: 10737418240 (10GB)
# maxmemory: 10737418240
# evicted_keys:0  ← KEY SIGN: 0 eviction + same numbers = noeviction

redis-cli CONFIG GET maxmemory-policy
# 1) "maxmemory-policy"
# 2) "noeviction"
```

**Fix**:
```bash
redis-cli CONFIG SET maxmemory-policy allkeys-lru
# Immediate: writes resume, eviction starts
# Long-term: design proper eviction policy for use case
```

### 8.2. `volatile-*` Evicts 0 Keys (No TTL Keys in Dataset)

**Root cause**: Policy set là `volatile-lru` nhưng không có key nào có TTL → eviction loop exits immediately, no keys evicted.

**Dấu hiệu**:
- `evicted_keys` = 0 despite `used_memory` > `maxmemory`
- Writes still failing (OOM error)
- `INFO keyspace` shows all keys with TTL = -1 (no TTL)

**Debug**:
```bash
# Check TTL distribution
redis-cli --scan | head -1000 | xargs -I{} redis-cli TTL {}

# Sample output:
# TTL user:profile:1: -1  ← NO TTL
# TTL session:abc: -1    ← NO TTL
# TTL session:xyz: 1523  ← HAS TTL
# If 99% are -1 → volatile-* policies useless
```

**Fix**:
1. If using session keys: verify `SETEX`/`SET ... EX` is used, not plain `SET`
2. If no TTL keys available: switch to `allkeys-lru` or `allkeys-lfu`
3. If mixed data: use 2 Redis instances

### 8.3. LFU Counter Saturation / "Stuck" Behavior

**Root cause**: `lfu-log-factor` default = 10. Với workload access key 50 lần/giờ, counter saturates rất chậm. Key được access 100 lần/giờ vẫn không vào top eviction candidates.

**Dấu hiệu**:
- LFU policy configured
- Hit rate thấp bất thường
- `OBJECT FREQ` trả về giá trị thấp (0–10) cho hot keys

```bash
# Inspect LFU counter distribution
redis-cli --scan | head -100 | xargs -I{} redis-cli OBJECT FREQ {}

# Typical output for Pareto cache:
# Hot key: freq=180
# Warm key: freq=45
# Cold key: freq=2

# If hot key shows freq=3 → lfu-log-factor too high
```

**Fix**:
```txt
# If counter saturates too slowly:
CONFIG SET lfu-log-factor 1   # faster counter growth

# If counter decays too fast (good keys evicted before cooling):
CONFIG SET lfu-decay-time 10  # 10 minutes per decay step (default 1)
```

**Tune process**:
1. Run with `lfu-log-factor=10` (default) for 24 hours
2. `OBJECT FREQ` on top 100 hot keys
3. If all hot keys have freq < 20 → lower `lfu-log-factor` to 1-5
4. If hot keys have freq > 200 → raise `lfu-log-factor` to 50+

### 8.4. Kernel OOM Kill (RSS Explosion)

**Root cause**: `used_memory_rss` (fragmentation) tăng cao → RSS gần RAM limit → kernel OOM killer kill Redis.

**Timeline**:
```
used_memory: 8GB (logical)
maxmemory: 8GB
RSS: 10.4GB (fragmentation = 1.3x)

jemalloc defrag activates → RSS jumps to 15GB
Kernel sees RSS > available RAM → SIGKILL Redis
```

**Dấu hiệu**:
- `dmesg | grep -i redis` → `Out of memory: Kill process`
- Redis process disappears (not graceful shutdown)
- Container/pod restart

**Fix**:
1. Set `maxmemory` = 70% of container RAM limit (not 100%)
2. Monitor `mem_fragmentation_ratio` → alert if > 1.5
3. Enable `activedefrag yes` (Day 9)
4. Set `maxmemory` slightly below point where defrag triggers

### 8.5. Eviction Loop Blocking Event Loop

**Root cause**: Eviction loop chạy synchronous trong event loop. Nếu cần evict nhiều keys → event loop blocked → all commands delayed.

**Dấu hiệu**:
- Periodic latency spikes (p99 >> p50)
- Spikes correlate with `evicted_keys` counter jumps
- `redis-cli --latency-history` shows spikes every few seconds

**Debug**:
```bash
# Check eviction rate
redis-cli INFO stats | grep evicted_keys

# Check latency
redis-cli --latency-history

# Output pattern:
# 1) 127.0.0.1:6379 seq:3 2s:0.42ms 5s:0.38ms 1m:0.35ms 5m:0.44ms
# 2) 127.0.0.1:6379 seq:4 2s:18.3ms 5s:0.41ms 1m:0.36ms 5m:0.40ms
#                           ^ spike! correlation: eviction burst
```

**Fix**:
1. Reduce memory pressure (more headroom below maxmemory)
2. Increase `maxmemory-samples` to improve accuracy (fewer eviction rounds)
3. Add more `maxmemory` (scale up)
4. Use `allkeys-random` as temporary measure (faster eviction loop, lower accuracy)

---

## 9. Real-world Examples

### Twitter — Timeline Cache với LRU

Twitter dùng Redis cho timeline cache. Ban đầu dùng `allkeys-lru` với `maxmemory-samples = 5`. Timeline access pattern là recency: user xem tweet mới nhất thường xuyên, tweet cũ ít khi xem.

**Config**:
```txt
maxmemory-policy allkeys-lru
maxmemory-samples 5
```

**Challenge**: Hot keys (celebrity tweets) được access rất nhiều, nhưng LRU vẫn evict chúng sau khi cold (không access 1-2 phút). Không ideal cho content có "eternal hot" keys.

**Solution**: Twitter dùng multiple Redis layers: L1 local cache (in-process) cho truly hot keys + L2 Redis cluster cho warm data.

### Netflix — EVCache (Evan-cache) với LFU

Netflix build EVCache (Evan Cache) trên Memcached/Redis-compatible layer. Cache pattern: 80/20 Pareto — 20% keys chiếm 80% traffic. LFU perfect cho pattern này.

**Why LFU over LRU**:
- Celebrity profiles, popular shows → accessed millions of times/day
- LFU counter đẩy these lên top of eviction list
- LRU would evict hot keys if not accessed for a few minutes (even if accessed millions of times before)

**Config**:
```txt
maxmemory-policy allkeys-lfu
lfu-log-factor 10           # balanced for high-frequency keys
lfu-decay-time 1            # 1-minute decay (default)
```

### antirez — "Random notes on improving the Redis LRU algorithm"

Salvatore Sanfilippo (antirez) viết blog về việc implement LRU trong Redis. Key insights:

1. **True LRU quá tốn memory**: doubly-linked list cho 1M keys = 16MB+ overhead
2. **Sample-based LRU đủ accurate**: 5 samples cho 1M keys → eviction decision "good enough" trong hầu hết cases
3. **maxmemory-samples = 5 là sweet spot**: Trade-off giữa accuracy và CPU cost
4. **LRU clock resolution**: 1 tick/second = max age resolution = 16M seconds ≈ 194 days

Source: `src/evict.c` — eviction algorithm được antirez viết và optimize qua nhiều Redis versions.

### Redis Source — `src/evict.c`

`src/evict.c` là core eviction implementation:

```c
// Key functions:
evictionPoolPopulate()  // Build candidate pool from random sampling
freeMemoryIfNeeded()     // Main eviction loop trigger
evictDictEntry()         // Evict single key
evictionPoolAdd()        // Add key to candidate pool

// Eviction pool (priority queue of worst candidates):
struct evictionPool {
    evictionPoolEntry[EVICTIONPOOLSIZE];  // EVICTIONPOOLSIZE = 16
    // Each entry: key name, idle time (or LFU counter)
    // Sorted by worst-first (oldest LRU or lowest LFU)
}
```

**`EVICTIONPOOLSIZE = 16`**: Redis maintain pool of 16 worst candidates (not just 5). `maxmemory-samples` = number of new candidates added per eviction round. Pool is a skiplist sorted by eviction score.

---

## 10. Common Pitfalls

### Pitfall 1: Quên rằng `noeviction` là default

Default `maxmemory-policy` = `noeviction`. Nếu chỉ set `maxmemory` mà không set policy → writes fail when Redis is full.

### Pitfall 2: Dùng `volatile-*` mà không audit keyspace

`volatile-lru` evict 0 keys nếu không có TTL keys. Luôn verify: `redis-cli --scan | head -1000 | xargs redis-cli TTL | grep -v "^-1$" | wc -l`.

### Pitfall 3: Set `maxmemory` = 100% RAM

Jemalloc fragmentation có thể push RSS lên 130-150% of `used_memory`. Nếu instance có 8GB RAM và `maxmemory = 8GB`, RSS có thể đạt 10-12GB → kernel OOM.

**Rule**: `maxmemory = 70-80% of available container RAM`.

### Pitfall 4: LFU counter không reflect real frequency

`lfu-log-factor` default = 10. Key cần access hàng nghìn lần mới reach high counter value. Với workload 50-100 accesses/giờ, counter barely grows → eviction still removes "hot" keys.

**Fix**: Tune `lfu-log-factor` down (1-5) hoặc dùng LRU.

### Pitfall 5: Không monitor `evicted_keys`

`evicted_keys > 0` nghĩa là Redis đang mất data. Nếu không monitor, không biết cache hit rate thực sự bao nhiêu.

### Pitfall 6: Hiểu sai LRU là "true LRU"

Redis LRU không evict least-recently-used key trong toàn bộ dataset. Nó chỉ sample `maxmemory-samples` keys và evict worst trong sample. Key có thể được accessed 1 second ago nhưng không được sampled → still evicted.

### Pitfall 7: Dùng eviction policy thay vì proper capacity planning

Eviction policy là **last resort**, không phải capacity planning strategy. Nếu Redis liên tục evict > 1000 keys/sec → cần scale up, không phải tune eviction policy.

### Pitfall 8: Confuse lazy expiration với eviction

`EXPIRE` xóa key khi TTL hết (lazy hoặc active). Eviction xóa key khi `used_memory > maxmemory`. Chúng là 2 independent mechanisms. Một key có TTL vẫn bị evict bởi `allkeys-lru` nếu Redis đầy.

---

## 11. Câu hỏi tự kiểm tra

### Câu 1
**Scenario**: Bạn set `maxmemory 10gb` và `maxmemory-policy volatile-lru`. Redis đầy, nhưng `evicted_keys = 0` sau 10 phút. Tất cả `SET` requests trả về OOM error. Nguyên nhân gốc là gì? Fix như thế nào?

<details>
<summary>Đáp án</summary>

**Root cause**: `volatile-lru` chỉ evict keys có TTL set. Nếu tất cả keys trong dataset không có TTL (hoặc TTL = 0 = vĩnh viễn), eviction loop scan 0 keys → 0 evicted.

**Debug step**:
```bash
redis-cli --scan | head -100 | xargs -I{} redis-cli TTL {}
# Output: mostly -1 (no TTL) → confirms root cause
```

**Fix options**:
1. Switch to `allkeys-lru` if all data is cache-like
2. If mixing persistent + TTL data: use 2 Redis instances
3. Verify application uses `SETEX`/`SET ... EX` for session keys

**Preventive**: Audit keyspace TTL distribution before setting `volatile-*` policies.

</details>

### Câu 2
**Scenario**: API response cache với Pareto workload. Bạn dùng `allkeys-lru` nhưng sau 1 tuần hit rate giảm từ 95% xuống 70%. Investigation thấy hot keys (access > 1000 lần/giờ) vẫn bị evict. Giải thích tại sao LRU fail trong case này và đề xuất fix.

<details>
<summary>Đáp án</summary>

**Tại sao LRU fail**: LRU chỉ quan tâm recency, không quan tâm frequency. Hot key được access 1000 lần/giờ nhưng nếu không được access trong 1-2 phút (ví dụ: off-peak hours, test environment), LRU coi nó là "old" và evict.

Pareto workload có "eternal hot" keys (celebrity profiles, top products) được access millions of times nhưng có thể có gaps trong access pattern → LRU evict nhầm.

**Fix**: Switch to `allkeys-lfu`:
```txt
CONFIG SET maxmemory-policy allkeys-lfu
CONFIG SET lfu-log-factor 10        # default, adjust if counter saturates too slowly
CONFIG SET lfu-decay-time 1         # 1 minute decay
```

**Expected**: Keys accessed 1000+ lần/giờ → LFU counter cao → evicted last. Keys accessed 1 lần → counter thấp → evicted first.

**Additional tuning**: Monitor `OBJECT FREQ` on hot keys. If freq < 20 after 24h → lower `lfu-log-factor`.

</details>

### Câu 3
**Scenario**: Production incident. Redis instance 16GB RAM, `maxmemory = 14gb`, `maxmemory-policy allkeys-lru`. Used memory = 14.1GB, fragmentation spike → RSS = 15.8GB → kernel OOM kill Redis. Giải thích chain of events và cách prevent.

<details>
<summary>Đáp án</summary>

**Chain of events**:
1. `used_memory = 14.1GB` → vượt `maxmemory = 14GB` → eviction loop starts
2. `volatile-lru` not configured → `allkeys-lru` starts evicting
3. While evicting: jemalloc defrag activates → RSS jumps from 14GB to 15.8GB
4. Fragmentation ratio = 15.8 / 14.1 = 1.12x (moderate)
5. Kernel sees total RSS 15.8GB on 16GB instance → no memory left
6. OOM killer invoked → SIGKILL Redis process

**Why eviction didn't help fast enough**:
- Eviction loop takes time to find + delete enough keys
- Fragmentation spike happened simultaneously
- Kernel OOM triggered faster than eviction could free memory

**Fix**:
1. **Immediate**: `maxmemory` = 70-75% of container RAM (not 87.5%)
   ```bash
   # For 16GB instance: maxmemory = 11-12GB
   CONFIG SET maxmemory 12gb
   ```
2. **Monitor fragmentation**: Alert when `mem_fragmentation_ratio > 1.5`
3. **Enable active defrag** (Day 9): `activedefrag yes`
4. **Long-term**: Right-size instance or add more RAM

**Rule**: `maxmemory` should leave headroom for fragmentation. 70% rule = safety margin for RSS > used_memory.

</details>

### Câu 4
**Scenario**: Bạn có Redis session store với 5 triệu sessions, mỗi session có TTL = 30 phút. Bạn set `maxmemory-policy volatile-lru`, `maxmemory 8gb`. Sau 1 tuần, Redis ở 7.5GB, eviction rate = 50 keys/sec. Bạn thêm 1 triệu sessions mới (traffic tăng 20%). Redis đầy trong 2 giờ, eviction tăng lên 5000 keys/sec. Tại sao eviction rate tăng 100x dù traffic chỉ tăng 20%?

<details>
<summary>Đáp án</summary>

**Root cause**: Session TTL = 30 phút. Với 5M sessions, average session lifetime = 30 phút. Churn rate = 5M / 30min = ~2,778 sessions/minute = ~46/second expire naturally (lazy + active expiration).

Khi thêm 1 triệu sessions: churn rate = 6M / 30min = ~3,333 sessions/minute = ~55/second.

Nhưng eviction tăng 100x → không phải do churn rate (chỉ tăng 20%).

**Real root cause**: 20% traffic increase → write rate increase → `used_memory` tăng nhanh hơn active expiration có thể clean. Redis đạt `maxmemory` → eviction loop activate. Eviction rate 5000/sec = Redis đang xóa ~5 triệu keys trong ~16 minutes = massive churn.

**Vấn đề design**: Session store có churn rate = full dataset / TTL. Với 6M sessions và 30 phút TTL, churn = 3,333 sessions/min ≈ 55/sec natural expiration. Nếu write rate > 55/sec → dataset grows → eviction needed.

**Fix options**:
1. Tăng `maxmemory` (scale up)
2. Giảm session TTL (faster natural expiration)
3. Chuyển sang `allkeys-lru` (evict bất kỳ key nào, không chỉ TTL keys)
4. Horizontal scaling: 2 Redis instances (session + persistent cache)

**Key insight**: Session TTL = 30 phút → max sustainable write rate ≈ dataset / TTL = 6M / 1800s = 3,333/sec. Nếu write rate > 3,333/sec → dataset grows → eviction required → cache instability.

</details>

### Câu 5
**Scenario**: CDN cache dùng `allkeys-lfu` với `lfu-log-factor 10`. Sau 1 tuần, hit rate = 85%. Bạn check `OBJECT FREQ` trên 10 hot keys và thấy counter values: 3, 5, 2, 8, 4, 1, 6, 3, 2, 7. Counter values rất thấp. Phân tích và fix.

<details>
<summary>Đáp án</summary>

**Phân tích**:
- Hot keys (CDN content accessed thousands of times) có counter chỉ 1-8
- `lfu-log-factor 10` → counter growth rất chậm
- Key cần access ~1000 lần để reach counter ~10 với factor=10
- CDN workload: hot keys accessed 10,000+ lần/giờ nhưng với Pareto = 80% accesses vào 20% keys

**LFU counter saturation formula**:
```
max_counter ≈ log_base(sliding_window) of (accesses_per_window)

With lfu-log-factor=10, sliding_window = hits_in_an_hour:
  Counter=10 requires ~100 accesses/hour (if hot)
  Counter=50 requires ~10,000 accesses/hour

CDN hot keys accessed 10,000+ times/hour → counter should be 50+
Actual: counter = 1-8 → something is wrong
```

**Possible issues**:
1. `lfu-decay-time` quá ngắn → counter decay quá nhanh (counter giảm 1 mỗi minute)
2. `lfu-log-factor` quá cao → counter growth quá chậm
3. Workload pattern: keys accessed burstily (1000 accesses trong 1 minute, rồi 0 trong 59 phút) → counter tăng rồi decay xuống

**Fix**:
```txt
CONFIG SET lfu-log-factor 1        # much faster counter growth
CONFIG SET lfu-decay-time 10       # slower decay (10 minutes)
```

**Verification**:
```bash
# Run for 24h, then check:
redis-cli --scan | head -100 | xargs -I{} redis-cli OBJECT FREQ {}
# Expected: hot keys should have freq > 50-100 after 24h
```

</details>

### Câu 6
**Bạn có 3 Redis instances, mỗi 8GB, dùng cho 3 mục đích khác nhau. Thiết kế eviction policy cho từng instance và giải thích trade-off.**

<details>
<summary>Đáp án</summary>

| Instance | Use Case | Policy | Giải thích |
|----------|----------|--------|-----------|
| Redis-A | API response cache (hot 20% keys = 80% traffic) | `allkeys-lfu` | Pareto pattern: frequency = relevance. LFU giữ hot keys. `lfu-log-factor=10`, `lfu-decay-time=5` |
| Redis-B | Session store (TTL=30 phút, user state) | `volatile-lru` | Sessions có TTL. Chỉ evict session keys. Non-session data (rate limit) không bị evict. **Verify: all session keys must have TTL** |
| Redis-C | Rate limit counter + idempotency tokens | `noeviction` | Counters không chấp nhận mất data. Monitor `used_memory` và scale khi > 80%. Pair với PostgreSQL unique constraint cho idempotency |

**Cross-concern**: Nếu 1 Redis instance bịOOM (Redis-B, volatile-lru, 0 eviction vì không có TTL) → session fail → user logout. **Mitigation**: monitor `evicted_keys` và `used_memory` trên mỗi instance riêng.

**Alternative architecture for Redis-B**: Dùng `allkeys-lru` thay vì `volatile-lru` nếu không guarantee được all keys có TTL. Session keys expire tự nhiên, LRU evict theo recency.

</details>

### Câu 7
**Explain sự khác biệt giữa Redis OOM (in-process eviction limit) và kernel OOM (OS-level kill). Khi nào cả 2 có thể xảy ra đồng thời?**

<details>
<summary>Đáp án</summary>

**Redis OOM (maxmemory)**:
- Redis internal check: `used_memory > maxmemory`
- Trigger eviction loop (synchronous, event loop blocked)
- Write commands return `OOM command not allowed` error
- Redis process still alive, serving reads
- Recovery: eviction or `CONFIG SET maxmemory` increase

**Kernel OOM (OOM killer)**:
- Linux kernel check: available RAM < threshold
- Kernel selects process with highest oom_score
- SIGKILL sent to Redis process
- Redis process dies immediately (no graceful shutdown)
- Data loss if no persistence
- Recovery: restart Redis (data loss if no persistence)

**When both can happen simultaneously**:
```
1. used_memory = 14GB, maxmemory = 14GB → Redis eviction loop starts
2. Fragmentation spike: RSS = 15.8GB (fragmentation ratio 1.13x)
3. Redis evicts keys → used_memory decreases slowly
4. While evicting: jemalloc defrag allocates new pages → RSS increases
5. RSS hits 16GB (total RAM) → kernel OOM triggers
6. Redis killed before eviction loop completes
```

**Prevention**:
- `maxmemory` = 70-75% of container RAM (not 90%+)
- Monitor `mem_fragmentation_ratio` → alert > 1.5
- Enable `activedefrag yes` (Day 9)
- Reserve 2-4GB system memory buffer

</details>
