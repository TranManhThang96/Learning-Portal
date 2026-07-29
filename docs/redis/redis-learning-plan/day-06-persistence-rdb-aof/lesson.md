# Day 6: Persistence RDB & AOF

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Giải thích được RDB snapshotting mechanism, AOF append-only log, hybrid persistence — khác nhau ở đâu, dùng khi nào.
- Phân tích data loss window cho mỗi persistence config và đo lường bằng `INFO persistence`.
- Chẩn đoán OOM kill do COW trong BGSAVE qua `latest_fork_usec` và `mem_fragmentation_ratio`.
- Đánh giá fork latency, restart time thực tế trên dataset 1GB/10GB/50GB để đưa ra persistence decision không dựa trên "best practice" suông.
- Thiết kế persistence config tối ưu cho 3 use case: pure cache, session store, idempotency store — có trade-off rõ ràng, không copy-paste default.

## 2. Vì sao cần học chủ đề này

### GitLab Incident 2017 — Khi 5/5 backup mechanism đều thất bại

Ngày 31/01/2017, GitLab mất 6 giờ data. Nguyên nhân: replication bị dừng từ trước đó, PostgreSQL replication slot đầy, NFS mount bị unmount, backup script chạy thủ công và đã thất bại, và LVM snapshot cũng không hoạt động. Hệ quả: engineer phải khôi phục từ replica 6 giờ trước, mất tất cả commit trong 6 giờ đó. Bài học: **persistence không chỉ là config, là backup strategy toàn hệ thống**.

### Twitter — RDB-only session store mất 5 phút data

Twitter dùng Redis làm session store cho user sessions. Default RDB config `save 3600 1` — nghĩa là nếu crash ngay trước khi BGSAVE chạy, mất tối đa 1 giờ sessions. 5 phút crash trong peak hour đồng nghĩa hàng triệu user logout đột ngột, queue login flood backend. Không ai đặt câu hỏi "data loss window của config hiện tại là bao nhiêu?".

### Senior dev disable persistence cho cache nhưng quên warm-up

Một pattern cực kỳ phổ biến: dev bật `save ""` (disable RDB) cho Redis cache vì "cache thì không cần durability". Khi pod bị restart, Redis start với empty state. Traffic đổ vào cold cache → cold start storm → backend database overload. Chỉ cần một cache warmer đơn giản là tránh được, nhưng không ai nghĩ tới vì "cache mà".

**Bottom line**: Persistence là nơi nhiều senior developer mắc sai lầm nhất — không phải thiếu kiến thức, mà vì họ đưa ra assumption mà không kiểm chứng.

## 3. Kiến thức nền cần có

- Redis là single-threaded, in-memory data store (Day 1)
- Redis data structures: String, Hash, List, Set, Sorted Set (Day 2)
- Key design và TTL strategy (Day 4)
- Redis object model, encoding internals (Day 5)
- Linux process model: fork(), parent/child process (OS fundamentals)
- Disk I/O: fsync, write-back vs write-through cache

## 4. Lý thuyết chi tiết

### 4.1. RDB Mechanism

**RDB** = Redis Database snapshot file. Là binary file chứa toàn bộ dataset tại thời điểm snapshot.

#### Save Policy

```txt
# Default (Redis 7)
save 3600 1    # snapshot khi >= 1 key thay đổi trong 3600s (1 giờ)
save 300 100   # Hoặc >= 100 keys thay đổi trong 300s (5 phút)
save 60 10000  # Hoặc >= 10000 keys thay đổi trong 60s
```

Nếu không muốn RDB: `save ""` (empty string — config key `save` accept multi directive, empty string disable).

#### SAVE vs BGSAVE

| Command | Blocking | Use case |
|---------|----------|----------|
| `SAVE` | Full blocking — Redis không serve request trong lúc write | Chỉ dùng emergency, không bao giờ prod |
| `BGSAVE` | Non-blocking — fork child process | Standard prod operation |

**BGSAVE flow**:

```
Redis Parent Process (serve traffic)
    |
    fork() ──────────────────────────────────────── Linux kernel
    | (shared page table, read-only initially)          |
    |                                                   | COW: pages written by parent
    | (child process)                                   | → kernel allocates new page
    |                                                   |   for that page (copy-on-write)
    v                                                   v
child: RDBWrite(dump.rdb)         parent: continue serving requests
    |                                                   |
    | atomic rename                                     |
    v                                                   |
dump.rdb written ─────────────────────────────────────┘
(overwrite old dump.rdb)
```

- Parent process tiếp tục serve traffic trong khi child dump data
- Child fork từ parent → copy-on-write page table
- Parent writes to memory → kernel COW, allocate new page → memory overhead tăng
- Child viết xong → atomic rename (đảm bảo dump.rdb luôn consistent)
- File location: `dir/dbfilename` (default `./dump.rdb`)

#### RDB File Format

Binary format, optimized cho:

- Compact: chỉ chứa data, không chứa command
- Fast load: `redis-server --loadmodule` load trực tiếp vào memory
- gzip-compressible: có thể compress thêm cho backup

Redis 7+ RDB format có thêm per-key metadata (LFU/LRU counters, TTL precision). Version 9 RDB format (Redis 7.2+) có thêm data type versioning.

**Lưu ý quan trọng**: RDB file là **point-in-time snapshot tại thời điểm fork()**, không phải tại thời điểm child viết xong. Các thay đổi trong parent sau khi fork() không xuất hiện trong snapshot.

### 4.2. AOF Mechanism

**AOF** = Append-Only File. Log mọi write command vào file, replay khi restart.

#### How it works

```
Client: SET user:1 "thang"
    |
    v
Redis: Execute command → update data in memory
    |
    v
Serialize: *3\r\n$3\r\nSET\r\n$7\r\nuser:1\r\n$5\r\nthang\r\n
    |
    v
Append to appendonly.aof  (via write(2))
    |
    v
fsync() ──────────────────────────────────── Disk (depending on policy)
```

**RESP serialization**: mỗi command được serialize theo Redis Serialization Protocol (RESP). Ví dụ: `SET key value` → `*3\r\n$3\r\nSET\r\n$key_len\r\nkey\r\n$val_len\r\nvalue\r\n`.

#### fsync Policy

| Policy | Behavior | Durability | Write Latency |
|--------|----------|------------|---------------|
| `appendfsync always` | fsync() sau mỗi write | Tối đa trong Redis, best-effort gần 0 sau ACK | Cao (disk sync per op) |
| `appendfsync everysec` (default) | fsync() mỗi giây | ~1s data loss | Thấp (p99 +1-3ms) |
| `appendfsync no` | OS quyết định flush | Không guarantee | Minimal (best-effort) |

Chi tiết fsync policy và latency impact → **Day 7 deep dive**.

#### AOF File (Redis 7+)

Redis 7+ split AOF thành multiple files trong `appendonlydir/`:

```
appendonlydir/
├── appendonly.1.0000000000000000.aof
├── appendonly.1.0000000000000123.aof
└── appendonly.manifest
```

- Base file: full snapshot tương tự RDB (Redis 7.2+ sử dụng AOF+RDB hybrid format)
- Incremental files: chỉ chứa commands sau base
- `appendonly.manifest`: tracking file, version control
- Khi load AOF: replay incremental files theo order

### 4.3. fork() + Copy-on-Write

#### Linux fork() mechanics

```
fork() returns twice:
  - In parent: returns child's PID
  - In child: returns 0

After fork():
  Parent and child share the same physical pages
  But page tables point to same read-only pages initially
  → "virtual" copy, not actual memory duplication
```

#### Copy-on-Write flow

```
1. fork() called
   → Child gets copy of parent's page table
   → All pages marked read-only in both processes

2. Parent writes to page P
   → CPU triggers page fault (protection violation)
   → Kernel allocates NEW physical page
   → Copies content of P to new page
   → Updates parent's page table to point to new page
   → Marks new page as writable
   → Continues parent execution

3. Child still uses original page P (now freed for child)
   → Separate copy maintained
```

**Memory overhead = number of pages written by parent during BGSAVE run**

#### Real-world COW calculation

```
Dataset: 30GB
BGSAVE duration: 60s
Write rate: 200K ops/sec
Average write size: 100 bytes/op
Pages written: 200K * 100 = 20GB of data written
Page size: 4KB → 20GB / 4KB = 5M pages COW

Worst case: if all writes hit unique pages
→ 5M * 4KB = 20GB additional memory needed
→ Peak memory: 30GB + 20GB = 50GB (if instance limit is 32GB → OOM)
```

**Key insight**: COW overhead = write_volume × page_alignment_factor. High write rate + large dataset = memory bomb.

### 4.4. Snapshot Consistency

RDB snapshot là **point-in-time của thời điểm fork()**, không phải thời điểm dump xong.

```
t=0ms:   fork() triggered
t=200ms: fork() completes, snapshot "view" frozen at t=0ms
t=200ms-60s: parent continues writing, COW pages allocated
t=60s:   child finishes writing dump.rdb
t=60s:   atomic rename dump.rdb
```

Các thay đổi từ t=0ms đến t=60s (trong parent) **không có trong snapshot**. Đây là snapshot consistency model chứ không phải strict consistency.

### 4.5. Crash Recovery

```
Redis startup:
  |
  v
Check appendonly.aof exists?
  ├── Yes → Load AOF (priority: AOF > RDB)
  │         ├── Redis 7+: parse base + incremental files
  │         └── Replay all commands in order
  │
  └── No → Check dump.rdb exists?
            ├── Yes → Load RDB (fast, binary)
            └── No  → Start with empty dataset
```

**Load order**: AOF > RDB khi cả hai bật. Lý do: AOF chứa nhiều data hơn (chứa commands sau snapshot cuối).

**Hybrid persistence (Redis 4.0+)**:

```
aof-use-rdb-preamble yes
```

Behavior: Khi AOF rewrite triggered (Day 7):

1. Redis fork()
2. Child viết RDB format snapshot (nhanh, compact) vào AOF file
3. Child tiếp tục append commands vào AOF tail (RESP format)
4. Parent ghi commands vào rewrite buffer
5. Parent append rewrite buffer vào AOF tail sau rewrite complete

Result: File bắt đầu bằng RDB binary snapshot + tiếp theo là AOF commands → **fast load (RDB) + durability (AOF tail)**.

**Restart time comparison** (realistic numbers):

| Dataset | RDB | AOF | Hybrid |
|---------|-----|-----|--------|
| 1GB | 5-10s | 30-60s | 5-15s |
| 10GB | 60-120s | 5-15min | 60-150s |
| 50GB | 5-20min | 30-90min | 5-30min |

## 5. Trade-off Analysis

### 5.1. RDB vs AOF

| Aspect | RDB | AOF |
|--------|-----|-----|
| File size | Compact (binary, data only) | Lớn (verbose RESP commands) |
| Restart speed | Nhanh (binary load) | Chậm (replay commands sequentially) |
| Data loss window | Theo save interval (phút) | 0s (always), ~1s (everysec), unbounded (no) |
| Write pattern | Burst I/O khi BGSAVE | Đều đặn, append-only |
| CPU impact | Spike khi BGSAVE (fork + I/O) | Đều (serialization + write + fsync) |
| AOF rewrite needed | No | Yes (file grows unbounded) — Day 7 |
| Corruption recovery | Reload từ last snapshot | Truncate corrupt tail + replay |
| Suitable for | Backup, disaster recovery, fast restart | High durability requirement |

### 5.2. Durability vs Write Latency

| fsync policy | Data loss max | p99 write latency | p99.9 write latency |
|-------------|---------------|-------------------|----------------------|
| `always` | 0 | ~1-10ms (disk fsync) | ~10-50ms |
| `everysec` | ~1s | ~1-3ms | ~5-10ms |
| `no` | unbounded | ~0.1ms | ~1ms |
| RDB only | save interval (default 1h) | ~0 (no per-write overhead) | ~0 |

**Lưu ý**: `always` trên SSD chậm có thể gây write backpressure, client timeout. Không bao giờ dùng `always` trên HDD.

### 5.3. Faster Restart vs Data Loss

```
                    Restart Speed
                         ^
                         |
                    fast |  * RDB 1GB
                         |   * Hybrid 10GB
                         |
                         |
                         |
                    slow |  * AOF 50GB
                         |   * AOF 10GB (replay)
                         |
                         +------------------------------->
                               Small ←————→ Large
                               Data Loss Window

Trade-off: RDB restart nhanh nhưng mất data tới save interval.
           AOF restart chậm (replay) nhưng data loss tối thiểu.
           Hybrid = fast load (RDB) + recent changes (AOF tail).
```

| Scenario | Persistence | Restart Time | Data Loss |
|----------|------------|--------------|-----------|
| Crash sau 5 phút | RDB `save 3600 1` | Fast (RDB load) | ~1 giờ (stale snapshot) |
| Crash sau 5 phút | AOF `everysec` | Slow (replay 5 phút commands) | ~1 giây |
| Crash sau 5 phút | Hybrid | Fast (RDB) + replay AOF tail | ~1 giây |

### 5.4. Cache-only Redis vs Durable Redis

| Aspect | Cache-only (persistence off) | Durable Redis |
|--------|------------------------------|---------------|
| Write throughput | Cao nhất (no persistence overhead) | Thấp hơn (AOF append) |
| Restart behavior | Empty dataset (cold start) | Data preserved |
| Data loss | 100% after crash | 0 - ~1 giờ (tùy config) |
| Cold start risk | Cao (storm on backend) | Không (warm restart) |
| Memory efficiency | Chỉ data | Data + persistence buffer |
| Disk I/O | 0 | RDB burst hoặc AOF ongoing |
| Use when | True ephemeral cache, can rebuild | Session, queue, idempotency, source of truth |
| Risk | Catastrophic data loss on any restart | Operational complexity (disk, config, monitoring) |

## 6. Best Solution & Best Practices

### Theo Scenario

#### Pure Cache (Redis làm caching layer, data có thể rebuild từ DB)

```txt
save ""                    # Disable RDB
appendonly no              # Disable AOF
# Accept: 100% data loss on restart
# Require: cache warmer to prevent cold start storm
```

**Khi nào đúng**: Rate limiter, CDN edge cache, computed result cache — data không tồn tại = miss, backend rebuild.

**Khi nào sai**: Session store, shopping cart, bất kỳ state nào user tạo ra mà không có backend store.

#### Session Store (user sessions, shopping carts — user-generated state)

```txt
save 3600 1 300 100 60 10000
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
# Accept: ~1s data loss
# Fast restart: RDB preamble → load snapshot quickly
# Recent changes: AOF tail → minimal data loss
```

**Tại sao hybrid**: Session 1 giờ trước vẫn có trong RDB snapshot. Session trong 1 giây cuối trong AOF tail. Restart time = RDB load (nhanh) + AOF tail replay (chỉ 1s commands = vài MB).

#### Idempotency Store / Job Queue (không accept data loss)

```txt
save 900 1                 # RDB backup 15 phút
appendonly yes
appendfsync always          # best-effort near-zero data loss after ACK
aof-use-rdb-preamble yes
# Caveat: Redis is NOT a durable data store (see pitfall #12)
# Require: external durability guarantee (PostgreSQL, Kafka)
```

**Caveat quan trọng**: `appendfsync always` không đảm bảo 100% durability như PostgreSQL. Redis vẫn có thể mất data trong edge case (kernel bug, disk firmware bug, power loss với capacitor-backed RAID). Nếu cần true durability, dùng Redis chỉ để coordinate, không phải store data cuối cùng.

#### API Response Cache (large dataset, tolerate 1h data loss)

```txt
save 3600 1
appendonly no
# + cache warmer: periodic prefetch hot keys into Redis
```

### Anti-patterns — Không bao giờ làm

1. **Disable cả RDB và AOF cho session/queue**: `save ""` + `appendonly no` = 100% data loss on any restart.
2. **AOF always trên HDD hoặc SSD chậm**: Write latency spike → client timeout → cascading failure.
3. **BGSAVE trên instance không đủ memory headroom**: COW spike → OOM → kernel kill Redis → data loss + downtime + repeat loop.
4. **AOF/RDB trên cùng disk với DB write-heavy**: I/O contention → slow fsync → slow writes → slow reads.
5. **Không đặt restart timeout trong orchestrator**: AOF replay 50GB = 5-30 phút. Kubernetes pod liveness check = kill → data loss giữa replay.
6. **Nghĩ RDB = durable**: RDB là snapshot, không phải WAL. `save 3600 1` = có thể mất 1 giờ data.

## 7. Performance Considerations

### 7.1. Fork Overhead

Fork latency tỉ lệ với **memory size** và **page table size** — không phải dataset size.

```
Fork time ≈ f(memory_size, page_table_size, CPU_speed)

Real numbers (approximate):
  4GB  dataset: fork ~50-100ms
  16GB dataset: fork ~200-400ms
  32GB dataset: fork ~400-800ms
  64GB dataset: fork ~800-2000ms
```

Fork là **blocking** ở kernel level — Redis parent process bị block cho tới khi fork() return. Child sau đó chạy non-blocking. Redis 7.2+ có `fork()` optimization (copy_file_range) giảm I/O overhead.

**Đo lường**: `INFO persistence` → `latest_fork_usec` (microseconds). Alert nếu > 1s.

### 7.2. COW Memory Overhead

```
Base memory: dataset_size + overhead
Peak memory: base + COW_pages_written_during_BGSAVE

COW calculation:
  COW_bytes = write_rate(ops/s) × avg_write_bytes × BGSAVE_duration
  COW_pages = COW_bytes / page_size (4KB)

Example:
  Write rate: 100K ops/sec
  Avg write: 100 bytes
  BGSAVE: 30s
  COW = 100K × 100 × 30 = 300MB → ~75K pages → ~300MB peak

Worst case (random writes, 100% unique pages):
  30GB dataset, 200K writes/sec, 60s BGSAVE
  → 200K × 100 × 60 = 1.2GB COW
  → Peak: 31.2GB (if instance limit 32GB → tight, dangerous)
```

**Rule of thumb**: Reserve 20-30% memory headroom trên instance dùng BGSAVE. VD: 64GB dataset → 80GB+ instance.

### 7.3. AOF Write Latency

```
everysec (default):
  Write path: command → buffer (in memory) → write(2) → return
  fsync: background thread, every second
  p99 overhead: +1-3ms to normal write latency

always:
  Write path: command → buffer → write(2) → fsync() → return
  p99 overhead: +1-10ms (depends on disk speed)
  p99.9 overhead: +10-50ms (spikes when disk queue full)

no:
  Write path: command → buffer → write(2) → return (OS flush later)
  p99 overhead: ~0ms (buffered)
  Risk: up to 30s data loss (OS write-back cache eviction)
```

### 7.4. Disk I/O Pattern

| Mode | I/O Pattern | Disk Utilization |
|------|-------------|-----------------|
| RDB BGSAVE | Sequential burst write | Spike (100% for duration) |
| AOF everysec | Small sequential appends + periodic fsync | Moderate, steady |
| AOF always | Small writes + immediate fsync | High, consistent |
| AOF no | Buffered appends | Minimal until OS flush |

**SSD recommendation**: AOF-friendly (append-only = sequential writes). AOF no trên SSD vẫn an toàn hơn HDD.

### 7.5. Restart Time Numbers

```
1GB dataset:
  RDB:      5-10s    (fast binary load)
  AOF:      30-60s   (replay ~1GB commands)
  Hybrid:   5-15s    (RDB load + AOF tail replay)

10GB dataset:
  RDB:      60-120s  (load 10GB into memory)
  AOF:      5-15min  (replay commands, can be 10x larger than RDB)
  Hybrid:   60-150s  (RDB 10GB + AOF tail replay)

50GB dataset:
  RDB:      5-20min
  AOF:      30-90min (command log much larger than data)
  Hybrid:   5-30min  (RDB fast load + minimal AOF tail)
```

**Key insight**: AOF restart time tăng phi tuyến tính với dataset size vì command log chứa metadata (key names, type info) lặp lại nhiều lần. 50GB AOF có thể là 200GB+ file → replay mất rất lâu.

## 8. Production Failure Modes

### 8.1. OOM Kill khi BGSAVE (COW Spike)

**Nguyên nhân gốc**: COW pages allocate memory ngoài Redis control → kernel OOM killer kill Redis process.

```
Timeline:
  Redis used_memory: 28GB
  Redis maxmemory: 32GB
  Headroom: 4GB

  BGSAVE starts:
    fork() → child allocated
    COW starts: parent writes → pages duplicated

    If write volume > 4GB during BGSAVE:
      used_memory → 32GB+
      kernel OOM killer triggered
      Redis killed → data loss + downtime

    COW spike formula:
      peak_memory ≈ used_memory + (write_rate × avg_write × BGSAVE_duration)
```

**Dấu hiệu nhận biết**:
- `INFO persistence` → `latest_fork_usec` tăng đột ngột (1s+)
- `INFO memory` → `mem_fragmentation_ratio` > 1.5 (COW pages fragmented)
- `dmesg | grep -i oom` → Redis process killed
- System log → `Out of memory: Kill process ...`

**Fix**:
1. `vm.overcommit_memory = 1` (allow memory overcommit, prevent OOM on COW)
2. Monitor `latest_fork_usec` — alert nếu > 1s
3. Reserve 20-30% memory headroom
4. Giảm write pressure trong khi BGSAVE chạy
5. Dùng replica cho BGSAVE (Redis 7.2+ có `BGSAVE Replication Offset`)

### 8.2. Slow Disk gây AOF Backpressure

**Nguyên nhân**: AOF write blocked bởi fsync() chậm → Redis write pipeline bị backpressure.

**Dấu hiệu**:
- `INFO persistence` → `aof_delayed_fsync` counter tăng
- `INFO persistence` → `aof_pending_bio_fsync` > 0 liên tục
- Client write latency tăng
- Redis log: `Asynchronous AOF fsync is taking too long`

**Fix**:
1. Di chuyển AOF sang dedicated disk/volume
2. Dùng faster disk (NVMe SSD thay vì SATA SSD)
3. Chuyển `appendfsync everysec` (thay vì `always`)
4. Monitor `aof_pending_bio_fsync` — alert khi > 0

### 8.3. RDB Stale Snapshot

**Nguyên nhân**: Default `save 3600 1` → nếu không có thay đổi key trong 1 giờ, không có snapshot nào được tạo. Crash = mất tối đa 1 giờ data.

**Fix**:
1. Tune `save` policy: `save 300 1` (5 phút thay vì 1 giờ)
2. Bật AOF `everysec` làm safety net
3. Monitor `rdb_changes_since_last_save` — alert khi > threshold

### 8.4. AOF Corruption

**Nguyên nhân**: Power loss hoặc kernel panic giữa write → AOF file bị truncate ở tail.

**Recovery**:
```bash
redis-check-aof --fix appendonly.aof
```

`--fix` sẽ:
1. Scan AOF file
2. Tìm last valid command
3. Truncate file từ đó
4. Warning: data sau điểm corrupt bị mất

**Config safety nets**:
```txt
aof-load-truncated yes    # Load what we can, skip corrupt tail
aof-use-rdb-preamble yes  # RDB base = safety layer
```

### 8.5. Restart Timeout (Orchestrator Kill)

**Nguyên nhân**: Kubernetes liveness probe hoặc orchestrator restart timeout không tính AOF replay time.

```
50GB AOF replay = 5-30 phút
Kubernetes default liveness timeout = 30s
→ Pod bị kill giữa replay → restart loop → data mất liên tục
```

**Fix**:
1. Set appropriate `initialDelaySeconds` cho liveness probe
2. Tính toán worst-case restart time trước khi set timeout
3. Dùng hybrid persistence để restart nhanh hơn
4. Pre-stop hook: đợi replay complete trước khi stop

### 8.6. Persistence Disabled + Auto-restart

**Nguyên nhân**: Dev tắt persistence cho "performance", nhưng không có cache warmer → crash = data loss hoàn toàn.

**Fix**: Checklist trước khi disable persistence:
- [ ] Có cache warmer chạy không?
- [ ] Backend DB có chịu được cold start query load?
- [ ] Có monitoring cho cache hit rate post-restart?
- [ ] Data loss acceptable cho use case này?

## 9. Real-world Examples

### GitLab (2017) — Persistence và Backup as a System

GitLab mất 6 giờ data vì **5/5 backup mechanism đều thất bại**. Postmortem public (gitlab.com/blog/2017/03/02/gitlab-incident-report-31-jan-2017/). Bài học: backup không chỉ là config Redis, mà là toàn bộ stack — replication, NFS, LVM, backup scripts, offsite copies.

**Action items từ incident**:
- Replication monitoring với alert khi lag > threshold
- Backup verification (test restore thường xuyên)
- Multiple backup strategy (not single point of failure)
- Runbook cho từng backup mechanism

### Stripe — Hybrid cho Source-of-Truth Use Cases

Stripe dùng Redis cho rate limiting và idempotency key storage. Họ chạy hybrid persistence: RDB hourly backup + AOF `everysec`. Redis không phải primary store — Stripe dùng PostgreSQL với unique constraints cho idempotency. Redis làm "fast path", PostgreSQL làm durable store.

**Architecture**:
```
Payment request → Redis check idempotency key
  ├── Found: return cached response
  └── Not found: process payment → write to PostgreSQL + Redis
                 (Redis TTL 24h, PostgreSQL permanent)
```

### Twitter — RDB-only cho Timeline Cache với Fallback

Twitter dùng Redis cho timeline cache. RDB-only với `save 300 1` (5 phút). Cache warmer: pre-populate hot timelines từ database vào Redis. Khi Redis restart, cold start → timeline load từ DB → database spike có thể xử lý được vì rate limited bởi cache miss rate.

**Trade-off được accept**: 5 phút timeline data loss = stale timeline, không phải data loss nghiêm trọng.

### Instagram — AOF everysec cho Counter Service

Instagram counter service (likes, comments, followers) chạy AOF `everysec` với aggressive snapshot scheduling (5 phút). Counters là user-generated state, mất 1 giây counter increments = acceptable, nhưng mất toàn bộ counter = không acceptable.

### GitHub Sidekiq — AOF everysec cho Job Queue

Sidekiq (Ruby background job processor) khuyến nghị AOF `everysec` cho job queue durability. Mỗi job queue là Redis list. Job được enqueue → AOF append. Nếu Redis crash, jobs trong AOF được replay → không mất jobs trong flight.

## 10. Common Pitfalls

1. **Disable persistence trên durable use case**: `save ""` + `appendonly no` cho session store = 100% data loss on restart. Luôn hỏi: "Nếu Redis restart ngay bây giờ, impact là gì?"

2. **Bật AOF nhưng để fsync `no` mà nghĩ là durable**: `appendfsync no` = OS decide when to flush = có thể mất tới 30 giây (hoặc nhiều hơn) data. Không durable.

3. **Không monitor `latest_fork_usec`**: BGSAVE block 2-5 giây mà không ai biết → latency spike không explained → customer complaint.

4. **Lưu AOF cùng disk với write-heavy database**: I/O contention → slow fsync → Redis write backpressure → cascading failure.

5. **Restart timeout không tính AOF replay**: Orchestrator kill pod giữa replay → restart loop → persistent data loss.

6. **Hiểu sai "RDB durable"**: RDB là snapshot, không phải WAL. Data giữa 2 snapshot bị mất.

7. **Nghĩ AOF rewrite tự động cleanup mọi thứ**: AOF rewrite là Day 7 content. Không trigger rewrite = AOF file grow unbounded → disk full → Redis stop writing → data loss.

8. **Backup strategy chỉ dựa vào persistence file**: `dump.rdb` và `appendonly.aof` trên cùng server = single point of failure. Cần offsite backup.

9. **Không test restore**: Có backup nhưng chưa bao giờ restore thử = không có backup.

10. **Nghĩ COW memory overhead là 0**: Với high write workload, COW có thể tăng memory 50-100% trong BGSAVE window.

11. **Dùng `SAVE` command trong prod**: Blocking = Redis unavailable = incident.

12. **Dùng Redis làm primary durable store cho financial data**: Redis không phải database. Nếu cần durable = dùng PostgreSQL, Kafka, hoặc Redis Module như RedisRocks với WAL.

## 11. Câu hỏi tự kiểm tra

### Câu 1
**Workload**: 200K write ops/sec, dataset 30GB, instance memory 64GB. BGSAVE chạy 60 giây. Tính COW memory overhead peak và rủi ro?

<details>
<summary>Đáp án</summary>

```
COW = write_rate × avg_write_size × BGSAVE_duration
    = 200K × 100 bytes × 60s
    = 1.2GB COW pages

Peak memory = 30GB + 1.2GB = 31.2GB
Instance: 64GB → headroom = 64 - 31.2 = 32.8GB

Rủi ro: LOW. 64GB instance cho 30GB dataset có 33GB headroom >> COW 1.2GB.

Nhưng nếu:
  - Dataset 45GB + COW 1.2GB = 46.2GB (tight, risky)
  - Dataset 60GB + COW 1.2GB = 61.2GB > 64GB → OOM risk!
```

</details>

### Câu 2
**Scenario**: Bạn phát hiện `latest_fork_usec` = 3.5s trên instance 64GB. Nguyên nhân có thể là gì? Bước đầu tiên để debug?

<details>
<summary>Đáp án</summary>

**Nguyên nhân có thể**:
- Dataset quá lớn cho instance size (fork time tỉ lệ với page table size, không phải dataset size)
- Disk I/O chậm (BGSAVE child write bị I/O bound)
- Memory pressure gây swap → page table traversal chậm
- THP (Transparent Huge Pages) gây fork() slowdown
- CPU contention từ process khác

**Bước đầu tiên**:
```bash
# Check current fork time
redis-cli INFO persistence | grep latest_fork_usec

# Check memory usage
redis-cli INFO memory

# Check disk I/O
iostat -x 1

# Check THP
cat /sys/kernel/mm/transparent_hugepage/enabled

# Check swap
free -h
```

Fix tạm thời: `vm.overcommit_memory=1` + disable THP.
Fix dài hạn: scale up instance hoặc giảm dataset size (sharding).

</details>

### Câu 3
**Cache-only Redis có nên bật persistence không? Trong điều kiện nào?**

<details>
<summary>Đáp án</summary>

**Nên bật khi**:
- Cache có **cache warmer** (pre-populate sau restart)
- Cold start storm gây **database overload** không acceptable
- Cache miss rate post-restart gây **SLO violation**
- Dùng Redis làm **distributed cache với sticky session**

**Không nên bật khi**:
- Cache rebuildable trong milliseconds (local cache fallback, fast DB query)
- Write throughput cực kỳ cao (persistence overhead không đáng)
- Cache size nhỏ (restart = millisecond rebuild)
- Dùng Redis chỉ cho **rate limiting token bucket** (stateless, rebuildable)

**Best practice**: Nếu bật, dùng `save 300 1` (RDB only) + cache warmer. Không cần AOF vì cache loss acceptable.

</details>

### Câu 4
**50GB Redis instance với AOF `everysec`. Restart time thực tế là bao nhiêu? Hybrid giúp được gì?**

<details>
<summary>Đáp án</summary>

**AOF only restart**: 30-90 phút
- 50GB dataset → AOF file 200-500GB (RESP verbose)
- Replay = sequential scan + command execution
- p99 có thể > 90 phút

**Hybrid restart**: 5-30 phút
- RDB preamble = 50GB binary snapshot (load ~5-20 phút)
- AOF tail = chỉ commands sau last RDB rewrite (thường vài phút commands)
- Total ≈ RDB load time + AOF tail replay

**Lưu ý**: Hybrid chỉ help nếu AOF rewrite được trigger thường xuyên (Day 7). Nếu AOF chưa bao giờ rewrite, hybrid = full AOF.

</details>

### Câu 5
**Tại sao `appendfsync always` không đảm bảo 100% durability như PostgreSQL?**

<details>
<summary>Đáp án</summary>

`appendfsync always` đảm bảo mỗi command được fsync() trước khi Redis return ACK cho client. Nhưng vẫn có gap:

1. **OS page cache**: write(2) → kernel buffer → fsync() flushes kernel buffer → disk write-back cache vẫn có thể lost trên power loss (với capacitor-backed RAID, rare)
2. **Disk firmware bug**: rare, nhưng có case documented
3. **Kernel bug**: Linux kernel có history của fsync() không working đúng trên certain hardware
4. **Redis bug**: rare crash during write path

PostgreSQL đạt true durability qua:
- Write-Ahead Log (WAL) + fsync after every transaction commit
- Double-write buffer
- Checksummed pages
- fsync() với O_DIRECT (bypass page cache)

**Bottom line**: Redis AOF là "best effort durability" cho high throughput. Nếu cần true durability, Redis phải được combine với external durable store (PostgreSQL, Kafka) hoặc dùng Redis Module như RedisRocks.

</details>

### Câu 6
**Khi nào nên dùng `BGREWRITEAOF` thay vì chỉ RDB?**

<details>
<summary>Đáp án</summary>

**Dùng `BGREWRITEAOF` khi**:
- AOF file đã grow rất lớn (vd: 50GB AOF cho 10GB dataset)
- AOF replay time quá chậm khi restart
- Muốn compact AOF thành binary snapshot + incremental commands (hybrid)

**Dùng RDB only (không AOF) khi**:
- Dataset < 10GB, restart time không critical
- Backup/DR là primary goal
- Không cần durability cao

**Dùng AOF only (không RDB) khi**:
- Durability requirement cao nhất trong Redis (`always` cho near-zero sau ACK; `everysec` chấp nhận mất khoảng 1 giây)
- Dataset lớn, RDB snapshot disk space là vấn đề

**Lưu ý**: Day 7 sẽ deep dive BGREWRITEAOF + AOF rewrite frequency + performance impact.

</details>

### Câu 7
**Bạn phát hiện `aof_delayed_fsync` counter tăng liên tục. Điều gì đang xảy ra và fix như thế nào?**

<details>
<summary>Đáp án</summary>

`aof_delayed_fsync` = số lần fsync() bị delayed vì fsync trước chưa complete.

**Điều đang xảy ra**:
- Disk I/O không theo kịp AOF write rate
- `appendfsync always` = mỗi write chờ fsync → queue buildup
- Latency spike → client timeout → write error → data loss potential

**Root cause thường gặp**:
1. AOF trên same disk với database write-heavy
2. SATA SSD thay vì NVMe
3. `appendfsync always` trên slow disk
4. RAID controller with write-back cache misconfigured

**Fix steps**:
```bash
# Immediate: change fsync policy
redis-cli CONFIG SET appendfsync everysec

# Move AOF to dedicated disk
redis-cli CONFIG SET dir /mnt/fast-nvme/redis
redis-cli CONFIG SET appenddirname appendonlydir

# Verify fix
redis-cli INFO persistence | grep aof_delayed_fsync
# Should stay at 0 after fix
```

**Long-term**:
- Dùng NVMe SSD cho AOF
- Monitor `aof_pending_bio_fsync` (ActiveDefrag INFO)
- Consider `aof-load-truncated yes` + RDB preamble as safety net

</details>
