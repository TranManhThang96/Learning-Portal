# Day 7: AOF Rewrite & Durability Trade-off

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Trình bày chính xác AOF rewrite flow: BGREWRITEAOF, child fork, shadow process, rewrite buffer, atomic rename — và tại sao mỗi bước tồn tại.
- Phân tích sâu `appendfsync always` vs `everysec` vs `no`: syscall behavior, page cache interaction, kernel flush timing, và ảnh hưởng tới p50/p95/p99 write latency.
- Đo lường latency spike của AOF rewrite trên dataset lớn, đặc biệt qua `latest_fork_usec`, `aof_rewrite_in_progress`, `aof_last_rewrite_time_sec`.
- Đề xuất persistence config cho 3 use case: pure cache, session store, financial-like idempotency store — có số liệu cụ thể và trade-off rõ ràng.
- Xử lý AOF corruption bằng `redis-check-aof --fix` và hiểu rõ khi nào `--fix` an toàn, khi nào mất data.
- Giải thích Multi-Part AOF (Redis 7+): `appendonlydir/`, base.rdb, incr.aof, manifest — và tại sao đây là breaking change quan trọng.

## 2. Vì sao cần học chủ đề này

### Twitter/X — `appendfsync always` gây p99 spike 50ms+ khi disk I/O bận

Twitter từng chạy `appendfsync always` trên Redis session store vì đội infra nghĩ "always = safe nhất". Kết quả: trên ổ SSD gắn chung với PostgreSQL write-heavy, khi PostgreSQL flush buffer lên disk đồng thời Redis gọi `fsync()`, disk queue bị full. `fsync()` latency tăng từ ~1ms lên ~50-100ms. Client timeout ở 30ms → hàng nghìn request fail trong 5-10 phút mỗi ngày mà không ai hiểu tại sao. Root cause: `appendfsync always` không chỉ là "fsync sau mỗi write" — nó là synchronous blocking call trên shared disk. Bài học: **"maximum durability" không đồng nghĩa "maximum safety" khi disk là shared resource**.

### AOF rewrite buffer overflow — restart chậm từ 10 giây thành 10 phút

Một startup dùng Redis 5.x làm job queue (Sidekiq-style). AOF file tăng từ 500MB lên 8GB sau vài tuần mà không ai để ý. Khi pod restart, Redis 7 phải replay 8GB AOF commands. Không có cache warmer. Hệ quả: 10 phút toàn bộ job queue offline, 50K jobs bị miss. Root cause: `auto-aof-rewrite-percentage` mặc định = 100 (rewrite khi AOF grow 100% so với last rewrite), nhưng trên 500MB baseline, 100% growth = 1GB mới trigger. Họ cần `auto-aof-rewrite-percentage 100` + `auto-aof-rewrite-min-size 64mb` là chưa đủ. Bài học: **AOF rewrite không tự happen "optimally" — bạn phải tune, monitor và alert**.

### Discord — AOF corruption sau power loss

Discord dùng Redis cho message metadata cache. Power loss trên một region gây corruption ở AOF file tail — không phải truncate sạch mà là corrupt giữa file. `aof-load-truncated yes` không load được vì format đã broken. Kỹ sư phải dùng `redis-check-aof --fix` và mất ~30 phút để identify và fix. May mắn là họ có replica sync lại. Bài học: **AOF corruption là failure mode thực tế, không phải edge case lý thuyết**.

**Bottom line**: Day 6 đã dạy RDB/AOF mechanism. Day 7 dạy cách tinh chỉnh AOF rewrite, fsync policy, và trade-off giữa durability thực sự vs durability mong muốn trong production.

## 3. Kiến thức nền cần có

- Redis persistence mechanism: RDB snapshotting, AOF append-only log (Day 6)
- Linux fork() và copy-on-write (Day 6)
- fsync() syscall semantics: write-back cache, page cache, disk write-back cache
- Redis child process model: BGSAVE, BGREWRITEAOF đều fork từ parent
- `INFO persistence` fields: aof_rewrite_in_progress, latest_fork_usec, aof_delayed_fsync, aof_pending_bio_fsync
- Hybrid persistence: aof-use-rdb-preamble (Day 6)

## 4. Lý thuyết chi tiết

### 4.1. AOF Rewrite — Tại sao cần rewrite và hoạt động ra sao

**Tại sao AOF cần rewrite:**

```
AOF sau 1 tuần với 1 triệu commands SET user:1 → 50 bytes:
  Command 1:    *3\r\n$3\r\nSET\r\n$7\r\nuser:1\r\n$5\r\nalice\r\n  (~45 bytes)
  Command 2:    *3\r\n$3\r\nSET\r\n$7\r\nuser:1\r\n$3\r\nbob\r\n  (~43 bytes)
  ... × 1M commands = 45MB raw data → 500MB+ AOF file
```

AOF log mọi command dạng text (RESP protocol). Nếu user:1 được SET 1 triệu lần, AOF lưu 1 triệu dòng cho cùng 1 key. Rewrite compact AOF thành: chỉ ghi state cuối cùng của mỗi key → 500MB → 50KB.

**AOF rewrite flow (BGREWRITEAOF):**

```
┌──────────────────────────────────────────────────────────────────┐
│  Redis Parent Process                                             │
│  - Serves client requests                                         │
│  - Accumulates new commands in AOF buffer                         │
│  - Also appends to "rewrite buffer" (for child sync)             │
└─────────────────────────────┬────────────────────────────────────┘
                              │  fork()
                              │  (copy-on-write page table)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Redis Child Process (shadow AOF writer)                          │
│                                                                  │
│  Step 1: Read current dataset from parent via temp pipe          │
│          (parent serializes current keys → child receives them)   │
│                                                                  │
│  Step 2: Write full dataset to temp AOF file in RDB format      │
│          (if aof-use-rdb-preamble yes) or RESP format             │
│                                                                  │
│  Step 3: While writing, parent sends new commands via            │
│          "AOF rewrite buffer" to child                           │
│          (child appends these to temp file too)                   │
│                                                                  │
│  Step 4: Child finishes → signals parent                         │
│          Parent atomically renames temp file → appendonly.aof    │
│          (atomic rename = no corrupt intermediate state)          │
└──────────────────────────────────────────────────────────────────┘

Timeline:
t=0ms:      fork() starts
t=300ms:    fork() completes (for 10GB dataset ~300-800ms)
t=300ms:    child starts reading dataset and writing temp file
t=10s:      child completes writing ~10GB temp file
t=10s:      parent receives signal, does atomic rename
t=10s:      new AOF file live, old AOF deleted
t=10s-10.3s: rewrite done
```

**Key insight**: AOF rewrite là **fork + full dataset serialization**. Nó tốn tài nguyên giống như BGSAVE, nhưng thêm I/O overhead để viết temp file.

**Rewrite buffer (AOF rewrite buffer) là gì:**

Trong khi child process viết temp file, parent process tiếp tục nhận và xử lý commands từ clients. Các commands này được ghi vào một buffer đặc biệt gọi là **AOF rewrite buffer**:

```
Parent process receives new command: SET user:1 "charlie"
    │
    ├─→ Appends to main AOF file (normal behavior)
    │
    └─→ Also appends to "AOF rewrite buffer" (in-memory buffer)

Child process finishes writing base snapshot
    │
    └─→ Reads all commands from "AOF rewrite buffer"
        └─→ Appends them to temp AOF file
            (ensures new commands during rewrite are not lost)

Parent does atomic rename: temp file → appendonly.aof
```

**Rewrite buffer overflow — nguy hiểm thực sự:**

AOF rewrite buffer là **in-memory buffer** (giới hạn bởi `client-output-buffer-limit` và `aof-rewrite-incremental-fsync`). Nếu rewrite chạy chậm (disk I/O slow, dataset lớn) và write rate cực kỳ cao, buffer có thể đầy:

```
Rewrite buffer max size = (by default, controlled by output buffer limits)
If buffer overflows:
  → Child process killed by parent (OOM on rewrite buffer)
  → Rewrite fails: "Unrecoverable error: rewrite buffer overflow"
  → AOF file remains at old size → disk space issue persists
  → redis-check-aof detects inconsistency on next restart

Warning signs:
  - "Unrecoverable error in AOF rewrite: read-only AOF buffer passed"
  - Child exit code non-zero during BGREWRITEAOF
  - aof_last_bgrewrite_status = error
```

Fix: giảm write rate trong rewrite window, dùng dedicated fast disk, hoặc nâng `client-output-buffer-limit`.

### 4.2. fsync Policies — Internals từng cái

**fsync() là gì ( refresher):**

```
Application: write(2) → data to kernel page cache (RAM)
Kernel:       ... → later: disk controller writes to disk (async)
fsync():      forces kernel to flush page cache → disk NOW
              (blocks until disk confirms write)
```

**3 fsync policies chi tiết:**

```
┌─────────────────────────────────────────────────────────────────┐
│ appendfsync always                                               │
│                                                                  │
│ Client writes command                                             │
│   → Redis executes → writes to AOF buffer                       │
│   → write(2) to page cache (fast, in-RAM)                      │
│   → fsync() CALLED IMMEDIATELY → blocks until disk confirms     │
│   → returns OK to client                                         │
│                                                                  │
│ Timeline per write: ~0.1ms (write) + ~1-10ms (fsync) = ~1-10ms │
│ Disk behavior: synchronous write, one at a time                  │
│ Throughput drop: 100K ops/sec → 15-30K ops/sec on SATA SSD     │
│                  100K ops/sec → 60-80K ops/sec on NVMe         │
│                                                                  │
│ ⚠️ CRITICAL: fsync() blocks the Redis main thread              │
│    if disk is slow → ALL clients blocked → latency spike       │
│    Never use on shared disk with write-heavy DB                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ appendfsync everysec (DEFAULT)                                   │
│                                                                  │
│ Client writes command                                             │
│   → write(2) to page cache (fast) → return immediately         │
│                                                                  │
│ Background thread (every 1 second):                              │
│   → fsync() all accumulated AOF writes                          │
│   → if previous fsync still running → SKIP this cycle            │
│     (aof_delayed_fsync increments)                               │
│                                                                  │
│ Timeline: ~0.1ms per write (no blocking)                         │
│           + periodic 1-10ms fsync (background)                   │
│ p99 overhead: +1-3ms (background, does not block reads)         │
│ aof_delayed_fsync: increments when fsync backlog exists         │
│                                                                  │
│ Data loss window: up to 2 seconds (worst case: fsync skipped    │
│                   one cycle + crash before next cycle)          │
│                                                                  │
│ Trade-off acceptable for: session store, job queue, most cases   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ appendfsync no                                                   │
│                                                                  │
│ Client writes command                                             │
│   → write(2) to page cache → return immediately                │
│   → NO fsync() called by Redis                                   │
│                                                                  │
│ OS decides when to flush page cache to disk:                    │
│   - Typically: 30 seconds or when pressure on free memory       │
│   - Kernel daemon: pdflush / flush daemon                        │
│   - Heavily workload-dependent                                    │
│                                                                  │
│ Timeline: ~0.1ms per write (essentially no overhead)            │
│ Data loss window: up to 30+ seconds (OS-dependent)               │
│                                                                  │
│ ⚠️ CRITICAL: crash = up to 30s of commands lost               │
│ ⚠️ CRITICAL: power loss = data in page cache LOST               │
│   (page cache is DRAM, not persisted until disk write)           │
│                                                                  │
│ ONLY for: truly ephemeral cache, can rebuild from source          │
└─────────────────────────────────────────────────────────────────┘
```

**fsync vs page cache vs disk write-back cache:**

Đây là nơi nhiều senior developer hiểu sai nhất:

```
Layer 1: Redis process → write(2) → kernel page cache (RAM)
Layer 2: Kernel page cache → (async) → disk controller cache (DRAM on controller)
Layer 3: Disk controller cache → (async) → physical disk media (NAND/HDD platter)

fsync() guarantees: Layer 1 → Layer 2 (page cache flush)
                   Does NOT guarantee: Layer 2 → Layer 3

BBU (Battery-Backup Unit) on RAID controller:
  → Controller cache survives power loss
  → fsync() + BBU = true durability
  → fsync() without BBU = may lose data in controller cache on power loss

NVMe with power-loss protection (PLP):
  → capacitors reserve power to flush controller cache on power loss
  → fsync() + PLP = equivalent to BBU
```

**Linux kernel behavior:**

```bash
# How often does the kernel flush dirty pages to disk?
# Controlled by: /proc/sys/vm/dirty_writeback_centisecs (default: 500 = 5 seconds)
# /proc/sys/vm/dirty_expire_centisecs (default: 3000 = 30 seconds)
# Pages older than dirty_expire_centisecs are candidates for writeback

cat /proc/sys/vm/dirty_writeback_centisecs  # 500 (5 seconds)
cat /proc/sys/vm/dirty_expire_centisecs     # 3000 (30 seconds)
```

Với `appendfsync no`, Redis chỉ gọi `write(2)`. OS có thể mất tới `dirty_expire_centisecs` (mặc định 30 giây) trước khi flush page cache → disk. Trên workload nhẹ, OS có thể batch nhiều writes lại và flush cùng lúc (tốt cho throughput, xấu cho durability).

### 4.3. Disk I/O Contention — Shared Disk là Silent Killer

**Case study: AOF + PostgreSQL trên cùng SSD:**

```
Scenario:
  - NVMe SSD 3.5GB/s sequential write, 500K IOPS random write
  - PostgreSQL: 30K writes/sec (8KB pages)
  - Redis AOF: 50K writes/sec (200-byte commands)
  - Total: 80K writes/sec

Question: Is this SSD sufficient?

Calculation:
  - PostgreSQL: 30K × 8KB = 240MB/s
  - Redis AOF (everysec): 50K × 200B = 10MB/s
  - Combined: 250MB/s
  - NVMe rated: 500MB/s sequential
  - BUT: random writes at 80K IOPS (mixed PostgreSQL + Redis)
  - NVMe real-world random: ~300K IOPS
  → 80K/300K = 27% utilization → OK in normal condition

BUT: BGSAVE or BGREWRITEAOF runs:
  - BGSAVE: sequential write ~100-200MB/s (Redis dataset)
  - Redis AOF appends: 10MB/s random
  - PostgreSQL: 240MB/s mixed
  - Total: ~250MB/s, but mixed I/O pattern
  → Disk queue depth increases
  → fsync() latency increases from 1ms to 10-50ms
  → Redis everysec fsync (every 1s) takes longer
  → aof_delayed_fsync starts incrementing
  → Eventually: fsync takes > 1 second
  → "Asynchronous AOF fsync is taking too long" warning in Redis log
```

**Disk type comparison:**

| Disk Type | Sequential Write | Random Write | fsync latency (avg) | fsync latency (p99) | AOF always? |
|-----------|-----------------|--------------|----------------------|----------------------|-------------|
| HDD 7200RPM | 100-150 MB/s | ~100 IOPS | 10-20ms | 30-50ms | NO (never) |
| SATA SSD | 400-550 MB/s | ~50K IOPS | 1-3ms | 5-15ms | Risky |
| NVMe SSD | 2000-7000 MB/s | ~300K IOPS | 0.1-0.5ms | 1-3ms | Yes (if PLP) |
| NVMe + BBU RAID | 2000-5000 MB/s | ~200K IOPS | 0.1-0.3ms | 0.5-1ms | Yes |
| Network EBS gp3 | ~250 MB/s | ~15K IOPS | 1-5ms | 10-50ms | NO |
| Network EBS io2 | ~500 MB/s | ~50K IOPS | 0.5-2ms | 5-20ms | Risky |
| NFS/SMB share | 50-200 MB/s | ~1K IOPS | 5-50ms | 100-500ms | NO (never) |

**Recommendation:**
- AOF file trên **dedicated disk** (NVMe SSD riêng, không chia với DB)
- Nếu không có dedicated disk: dùng `appendfsync no` + replication làm durability backup
- Nếu dùng cloud: instance store (ephemeral NVMe) tốt hơn network-attached storage cho AOF

### 4.4. Fork Overhead trên Dataset Lớn

**BGREWRITEAOF fork tốn bao nhiêu:**

BGREWRITEAOF cũng fork() như BGSAVE. Fork time tỷ lệ với:
- Memory footprint (không phải dataset size trên disk)
- Page table entries (1 entry per 4KB page)
- Process's address space size

```
Memory footprint → Page table entries → Fork time

4GB  dataset (1M pages)   → fork ~50-150ms
16GB dataset (4M pages)   → fork ~200-400ms
32GB dataset (8M pages)   → fork ~400-800ms
64GB dataset (16M pages)  → fork ~800-2000ms
128GB dataset (32M pages)  → fork ~1500-4000ms

⚠️ On systems with THP enabled: fork time +30-200%
⚠️ On systems without overcommit: fork may fail if COW can't be satisfied
```

**latest_fork_usec thực sự measure cái gì:**

`INFO persistence` → `latest_fork_usec` = **thời gian fork() syscall mất bao lâu**, không phải thời gian rewrite hoàn thành.

```
fork() syscall = time to create child process + duplicate page table
                = O(process_address_space / copy_speed)
                NOT O(dataset_size)

Rewrite total time = fork() + dataset_serialization + atomic_rename
                   = latest_fork_usec + aof_last_rewrite_time_sec
                   = "how long until new AOF is live"
```

Alert threshold:
- < 1s: normal
- 1-2s: concerning — investigate disk I/O or THP
- > 2s: critical — OOM risk, THP issue, or dataset too large for instance

### 4.5. Multi-Part AOF (Redis 7+) — Breaking Change quan trọng

Redis 7+ thay đổi AOF format từ single file thành directory-based:

```
Redis 6: (single file)
  appendonly.aof         (~50GB) ← replay entire file on restart

Redis 7+: (multi-part)
  appendonlydir/
  ├── appendonly.1.0000000000000000.aof   (base: full snapshot in RDB format)
  ├── appendonly.1.0000000000001234.aof   (incremental: commands after base)
  ├── appendonly.1.0000000000005678.aof   (incremental: commands after last)
  ├── appendonly.2.0000000000009000.aof   (new base after rewrite)
  └── appendonly.manifest                 (metadata: file order, version)

Load order:
  1. Read manifest → determine file sequence
  2. Load base file (RDB format, fast binary load)
  3. Replay incremental files in order
  4. Total: base (fast) + incremental tail (slow but smaller per file)
```

**Tại sao Multi-Part AOF (MP-AOF):**

```
Single AOF problem:
  - 50GB file, need to append new commands
  - Rewrite = fork child → serialize full dataset → write 50GB temp file
  - Duration: 50GB / 100MB/s = ~500 seconds = 8+ minutes
  - During rewrite: disk I/O intensive, latency spike for all clients
  - Risk: if rewrite fails, no AOF (unless old file kept)

Multi-Part AOF solution:
  - Base file: RDB snapshot (compact, fast load)
  - Incremental files: small append-only files (e.g., 1GB each)
  - Rewrite = write new base from current state + start new incremental
  - Old incremental files kept until confirmed consumed
  - Faster rewrite: base only (RDB) not full AOF
  - Crash recovery: still works (manifest tracks order)
```

**Config liên quan:**

```txt
appendonly yes
appenddirname appendonlydir       # Redis 7+ default: appendonlydir/
appendfilename appendonly.aof    # Ignored when appenddirname is set

# Incremental file size (Redis 7+)
aof-incremental-fsync yes        # fsync after every 1MB of incremental writes
                                  # Reduces potential data loss on crash (was 32MB default)
```

**Load behavior:**

```
Redis 7+ startup:
  1. Check appendonlydir/ exists?
  2. Read appendonly.manifest
  3. Sort files by sequence number
  4. Load base.rdb (if exists, in RDB format)
  5. Replay each incr.aof in order
  6. Result: same end state as single AOF, but faster on restart

Docker volume mount warning:
  - If you mount a volume, make sure the whole directory is mounted
  - Not just appendonly.aof (which won't exist in Redis 7+ with MP-AOF)
  - Example: -v redis-data:/data (correct)
  - NOT: -v $(pwd)/appendonly.aof:/data/appendonly.aof (broken in Redis 7+)
```

## 5. Trade-off Analysis

### 5.1. appendfsync Policies — Durability vs Throughput vs Latency

| Aspect | `always` | `everysec` (default) | `no` |
|--------|----------|----------------------|------|
| Durability | Maximum (0 data loss in normal case) | ~1s data loss max | Unbounded (up to 30s+) |
| Write throughput | 15-30K ops/sec (SATA SSD) | 80-100K ops/sec | 100K+ ops/sec |
| Write latency (p50) | 1-5ms | 0.1-0.3ms | 0.1-0.2ms |
| Write latency (p95) | 5-15ms | 1-3ms | 0.5-1ms |
| Write latency (p99) | 15-50ms (spikes to 100ms) | 3-10ms | 2-5ms |
| CPU overhead | High (syscall per op) | Low (background fsync) | Minimal |
| Disk I/O pattern | Sync write per op | Batch fsync (1/sec) | OS decides |
| Suitable for | Financial, idempotency (rare) | Most production cases | Ephemeral cache only |
| Risk on shared disk | High (blocks when DB busy) | Low (background) | N/A |

**Real numbers — throughput drop on `appendfsync always`:**

```
Benchmark: redis-benchmark -t SET -n 1000000 -r 1000000 -c 50

Hardware: Intel i9-12900K, Samsung 980 Pro NVMe (7000 MB/s read, 5000 MB/s write)

appendfsync no:      ~150K-180K ops/sec
appendfsync everysec: ~120K-150K ops/sec  (slight overhead from fsync thread)
appendfsync always:   ~30K-60K ops/sec   (50-70% drop on SATA SSD)
                    ~80K-120K ops/sec   (NVMe with PLP)

⚠️ On SATA SSD (common in cloud):
   always: 100K ops/sec → ~30K ops/sec (70% drop)
   everysec: 100K ops/sec → ~90K ops/sec (10% drop)
   no: 100K ops/sec → ~98K ops/sec (2% drop)
```

### 5.2. AOF Rewrite Frequency

| Rewrite Frequency | Pros | Cons | When |
|-----------------|------|------|------|
| Aggressive (every few GB) | Fast restart, small AOF tail, less data loss on crash | High fork overhead, disk I/O spike, rewrite buffer overflow risk | Large datasets (50GB+), high write rate |
| Conservative (every 20-50GB) | Fewer fork() events, less CPU/disk overhead | Large AOF file, long restart time, more data loss on crash | Small-medium datasets, low write rate |
| Disabled (never) | No rewrite overhead | Unbounded file growth, potential disk full, very slow restart | **Never in production** |

**Rewrite timing and data loss:**

```
AOF file: 10GB (hasn't been rewritten in 1 week)
Crash at t=0
Restart at t=5s
  → Redis loads 10GB AOF
  → Takes 10-30 minutes to replay 10GB
  → All clients waiting during replay
  → Service unavailable for 10-30 minutes

With aggressive rewrite (every 1GB):
AOF file: always < 1.5GB (1GB base + 0.5GB tail)
Crash at t=0
Restart at t=5s
  → Redis loads 1GB base + replays 0.5GB tail
  → Takes 1-3 minutes
  → Data loss: ~1GB commands = ~1-5 minutes of writes
```

**auto-aof-rewrite-percentage and auto-aof-rewrite-min-size:**

```txt
# Default values:
auto-aof-rewrite-percentage 100   # rewrite when AOF is 2x last rewrite size
auto-aof-rewrite-min-size 64mb   # don't rewrite if AOF < 64MB

# Aggressive rewrite (high write rate dataset):
auto-aof-rewrite-percentage 50   # rewrite when AOF is 1.5x last size
auto-aof-rewrite-min-size 64mb

# Conservative rewrite (large dataset, expensive disk I/O):
auto-aof-rewrite-percentage 200  # rewrite when AOF is 3x last size
auto-aof-rewrite-min-size 256mb

# NEVER disable rewrite:
# auto-aof-rewrite-percentage 0   ← NEVER DO THIS IN PRODUCTION
```

### 5.3. Durability SLO vs Performance SLO

```
                    Performance SLO
                    (throughput, latency)
                           │
                    High   │   * appendfsync no
                           │     * No AOF at all
                           │
                           │
                           │
                    Low    │   * appendfsync always
                           │     (on slow disk)
                           │
                           └─────────────────────────────────→
                                  Low        Medium         High
                                         Durability SLO
```

| Use Case | Durability SLO | Performance SLO | Recommended Config |
|----------|---------------|-----------------|-------------------|
| Pure cache | 0% (ephemeral OK) | Max throughput | No AOF, RDB optional |
| Rate limiter | Low (can replay from source) | High | No AOF or everysec |
| Session store | ~1s loss acceptable | Medium | everysec + hybrid |
| Job queue (non-critical) | ~1s loss acceptable | Medium | everysec |
| Job queue (critical, Sidekiq Pro) | Near-zero | Medium | always (if fast disk) |
| Idempotency key | Near-zero | Medium | always + PostgreSQL backup |
| Distributed lock | Near-zero | Medium | always + fencing token |
| Financial transaction | Zero (true durability) | N/A | PostgreSQL primary, Redis coordination only |

**Reconciling Durability SLO vs Performance SLO:**

Câu hỏi đúng: "Durability requirement của tôi là gì, và tôi sẵn sàng trade-off bao nhiêu throughput để đạt được?"

```
Pattern 1: Redis durability = safety net (not primary)
  → everysec is almost always the right answer
  → Real durability: PostgreSQL/Kafka/Redis replication

Pattern 2: Redis durability = critical requirement
  → appendfsync always + dedicated NVMe + PLP
  → Monitor aof_delayed_fsync = 0 always
  → Alert if latest_fork_usec > 1s

Pattern 3: Performance critical, some data loss OK
  → appendfsync no + Redis replication as durability
  → Accept: up to 30s data loss on power loss
  → Use: ephemeral caches, feature flags, non-critical counters
```

## 6. Best Solution & Best Practices

### 6.1. Production Config theo 3 Use Case

#### Pure Cache (Redis là cache layer, data có thể rebuild từ DB)

```txt
# redis-pure-cache.conf
save ""                           # No RDB (cache rebuildable)
appendonly no                     # No AOF (durability not needed)
maxmemory-policy allkeys-lru      # LRU eviction when memory full
# Accept: 100% data loss on restart
# Require: cache warmer running post-restart
```

**Khi đúng**: Rate limiter, computed result cache, CDN edge cache, feature flag store.
**Khi sai**: Session store, shopping cart, bất kỳ state nào user tạo ra.

#### Session Store (user sessions, shopping carts — user-generated state, ~1s loss OK)

```txt
# redis-session-store.conf

# AOF: ~1s data loss, fast restart
appendonly yes
appendfsync everysec             # Max ~1s data loss
aof-use-rdb-preamble yes         # Fast load (RDB base) + AOF tail
aof-load-truncated yes           # Load what we can if corrupt

# RDB: baseline snapshot every 5 minutes
save 300 1 60 10000              # Snapshot if 1 change in 5min OR 10K changes in 1min

# Rewrite: aggressive to keep AOF small
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb   # Rewrite when AOF > 128MB

# Disk: DEDICATED SSD (not shared with DB)
dir /mnt/nvme-redis-sessions

# Restart time target must be validated on real hardware.
# For 10GB dataset on NVMe: RDB load often ~20-90s + AOF tail replay.
# If SLA is <30s: shard smaller, reduce dataset, or warm sessions from DB.
```

#### Financial-like Idempotency Store (no acceptable data loss)

```txt
# redis-idempotency.conf

# CRITICAL: Redis is NOT a true durable store.
# Always pair with PostgreSQL unique constraint for idempotency token.
# Redis = fast path coordination, PostgreSQL = source of truth.

# RDB: backup every 15 minutes
save 900 1

# AOF: maximum durability
appendonly yes
appendfsync always               # Lowest loss window, best effort, not absolute
aof-use-rdb-preamble yes         # Fast load
aof-load-truncated yes           # Safety net

# AOF rewrite: conservative (fork is expensive on large dataset)
auto-aof-rewrite-percentage 200
auto-aof-rewrite-min-size 256mb

# Disk: DEDICATED NVMe with power-loss protection
dir /mnt/nvme-redis-idempotency

# HARD LIMIT: appendfsync always requires NVMe SSD
# On SATA SSD: p99 write latency ~50ms+ → client timeout → cascade failure
# On NVMe + PLP: p99 write latency ~1-3ms → acceptable

# Monitoring non-negotiable:
# - aof_delayed_fsync MUST be 0 always
# - Alert if aof_delayed_fsync > 0
# - Alert if latest_fork_usec > 1000000 (1 second)
# - Alert if aof_last_bgrewrite_status = error
```

### 6.2. Anti-patterns bắt buộc tránh

1. **`appendfsync always` trên SATA SSD hoặc shared disk**: Write latency p99 ~50-100ms → client timeout cascade. Chỉ dùng `always` trên **dedicated NVMe với PLP**.

2. **AOF trên cùng disk với PostgreSQL/MySQL write-heavy**: fsync contention → `aof_delayed_fsync` tăng → latency spike → cascading failure.

3. **Không monitor `aof_delayed_fsync`**: Nếu counter tăng liên tục = disk không theo kịp AOF write rate → imminent failure.

4. **`auto-aof-rewrite-percentage 0`** (disable auto rewrite): AOF grow unbounded → disk full → Redis stop writing → data loss. **Never do this.**

5. **`no-appendfsync-on-rewrite yes`**: Giảm rewrite latency nhưng tăng potential data loss window khi crash during rewrite. Chỉ dùng nếu restart time là critical issue và 1-2s data loss during rewrite acceptable.

6. **Dùng Redis AOF làm single durability mechanism cho financial data**: `appendfsync always` ≠ PostgreSQL durability. Pair với PostgreSQL unique constraint.

7. **Không tính restart time khi set orchestrator timeout**: AOF replay time = dataset × replay speed. Với 50GB dataset: 10-30 phút. Liveness probe timeout phải > restart time.

8. **AOF file trên NFS/network storage**: fsync trên NFS có thể mất 100-500ms per call → `appendfsync always` impossible, `everysec` has high latency.

## 7. Performance Considerations

### 7.1. fsync Latency Breakdown

```
appendfsync everysec — typical latency per component:

write(2) to page cache:        ~10-50 μs   (memory operation)
kernel schedules fsync thread: ~100-500 μs (every 1 second)
fsync() syscall (background):  ~0.5-3 ms   (NVMe: 0.5ms, SATA SSD: 2ms)
  └── If disk busy:             ~5-50 ms    (queued behind DB writes)

Net effect on write latency:  ~0.1-0.3ms added (background, non-blocking)
p99 spike when fsync delayed: ~10-50ms (if aof_delayed_fsync > 0)
```

### 7.2. AOF Rewrite Latency Impact

```
Dataset: 10GB, Write rate: 100K ops/sec, Disk: NVMe 5000 MB/s

Rewrite phases and duration:
  fork() syscall:               ~300-800ms  (process address space)
  child reads dataset:           ~2-5s       (via temp pipe, serialized)
  child writes temp file:        ~2-4s       (10GB / 3GB/s NVMe write)
  rewrite buffer flush:          ~1-10s       (depends on write rate)
  atomic rename:                ~50-200ms   (metadata operation)

Total: ~6-20 seconds of elevated disk I/O

During rewrite:
  - Disk I/O: 10GB sequential write + AOF appends simultaneously
  - AOF rewrite buffer: accumulates new commands
  - Rewrite buffer risk: 100K ops/sec × 10s = 1M commands × 200B = 200MB buffer

Memory overhead during rewrite:
  - Parent: COW pages for writes during fork
  - Child: full dataset in memory (via pipe read)
  - Peak: ~2× dataset size temporarily (parent + child)
```

### 7.3. Big O Analysis

```
AOF file size growth: O(n) where n = number of write commands
  (each command stored verbatim, no compression)

AOF rewrite time: O(N) where N = dataset size
  (child must read/serialize all keys)

AOF restart replay time: O(C) where C = AOF file size in bytes
  (sequential scan + command replay, NOT efficient)

RDB load time: O(D) where D = dataset size in bytes
  (binary load, more efficient than AOF replay)

AOF tail replay (with RDB preamble): O(T) where T = AOF tail size
  (only replay recent commands after RDB snapshot)

→ Hybrid restart: O(D) + O(T), much faster than O(C) for large C
```

### 7.4. Memory Overhead của AOF Rewrite

```
BGREWRITEAOF memory overhead:

1. fork() COW: same as BGSAVE
   - COW = write_rate × avg_write_size × rewrite_duration
   - Example: 100K ops/sec × 100B × 10s = 100MB COW

2. Rewrite buffer: in-memory queue of new commands
   - Buffered until child consumes them
   - Max size = client output buffer limit (default 256MB hard, 64MB soft)
   - If overflow: child killed, rewrite fails

3. Child process: reads dataset from parent via pipe
   - Pipe buffer: ~1MB (kernel pipe buffer)
   - Child accumulates data in memory as it serializes
   - Child memory ≈ dataset size

Total peak memory during BGREWRITEAOF:
  parent_mem + COW + rewrite_buffer + child_mem
  ≈ dataset + COW + rewrite_buffer
  ≈ dataset + (write_rate × write_size × duration) + 64MB
```

## 8. Production Failure Modes

### 8.1. AOF Rewrite Buffer Overflow

**Nguyên nhân**: Write rate quá cao trong khi rewrite đang chạy → rewrite buffer đầy → child killed.

**Dấu hiệu nhận biết**:
```
redis.log: "Unrecoverable error in AOF rewrite: read only AOF buffer passed"
redis.log: "AOF rewrite: %d bytes needed, but the target buffer size is %d bytes"
INFO persistence → aof_last_bgrewrite_status = error
AOF file: still at old size (no compaction happened)
Disk usage: continues growing
```

**Timeline**:
```
t=0:    BGREWRITEAOF starts
t=1s:   Child writing temp file, parent buffering new commands in rewrite buffer
t=5s:   Rewrite buffer reaches soft limit (64MB)
t=8s:   Rewrite buffer reaches hard limit (256MB)
t=8.1s: Parent kills child, rewrite fails
t=8.1s: aof_last_bgrewrite_status = error
        AOF file: unchanged (still large)
```

**Fix**:
```bash
# Immediate: manual BGREWRITEAOF when load is low
redis-cli BGREWRITEAOF

# Tune rewrite buffer (via client output buffer):
redis-cli CONFIG SET client-output-buffer-limit "normal 256mb 64mb 60 slave 256mb 64mb 60 pubsub 32mb 8mb 60"

# Reduce write rate during rewrite window:
# - Use read replica for write-heavy workloads
# - Batch writes instead of individual commands
# - Monitor and alert on aof_last_bgrewrite_status
```

### 8.2. Disk Full vì AOF không Rewrite

**Nguyên nhân**: `auto-aof-rewrite-percentage` không trigger vì baseline quá nhỏ hoặc config sai.

**Dấu hiệu**:
```
redis.log: "MISCONF Redis is configured to save RDB snapshots, but is currently not able to persist on disk"
redis.log: "Can't open the append-only file: No space left on device"
```

**Fix**:
```bash
# Emergency: disable AOF temporarily
redis-cli CONFIG SET appendonly no

# OR: remove old AOF files manually (backup first)
cp /data/appendonlydir/appendonly.*.aof /backup/
# Then trigger manual rewrite
redis-cli BGREWRITEAOF

# Prevention:
redis-cli CONFIG GET auto-aof-rewrite-percentage  # Should be > 0
redis-cli CONFIG GET auto-aof-rewrite-min-size   # Should be reasonable (64mb-256mb)
```

### 8.3. AOF Corruption — Power Loss giữa Write

**Nguyên nhân**: Kernel write-back cache mất data trên power loss (không có BBU/PLP).

**Dấu hiệu**:
```
Redis log: "FATAL AOF mode is configured... but append only file is not writable"
redis-cli --rdb /dev/null  # Test: RDB load works
redis-cli --aof /data/appendonlydir/appendonly.*.aof  # Fails at corrupt point

$ redis-check-aof --fix /data/appendonlydir/appendonly.1.0000000000000000.aof
  AOF analyzed: size=10GB, ok=9.8GB, corruption=200MB at offset 9897632896
  Remove the 200MB tail? (y/N): y
```

**Recovery với `redis-check-aof --fix`:**
```bash
# Step 1: Stop Redis
redis-cli SHUTDOWN NOSAVE

# Step 2: Backup corrupted AOF
cp -r /data/appendonlydir /backup/appendonlydir-$(date +%Y%m%d%H%M%S)

# Step 3: Check and fix
redis-check-aof --fix /data/appendonlydir/appendonly.1.0000000000000000.aof

# Step 4: Verify after fix
redis-check-aof /data/appendonlydir/appendonly.1.0000000000000000.aof

# Step 5: Restart Redis
redis-server --appendonly yes --appenddirname appendonlydir
```

**Data loss estimation**: commands sau điểm corrupt bị mất. Nếu corrupt ở 200MB vào cuối file 10GB → mất ~2% commands (tùy write rate, có thể là vài phút data).

### 8.4. Fork OOM trên BGREWRITEAOF

**Nguyên nhân**: COW spike trong rewrite + parent write rate cao → memory đầy → OOM killer.

**Dấu hiệu**:
```
dmesg | grep -i redis
# Out of memory: Kill process 12345 (redis-server) score 900 or sacrifice child
# Killed process 12346 (redis-aof-rewrite) as a result

redis.log: Child exited with code 137 (SIGKILL = OOM)
INFO persistence → aof_last_bgrewrite_status = error
```

**Fix**:
```bash
# Immediate:
# 1. Scale up instance (more RAM)
# 2. Reduce write rate temporarily

# Prevention:
# 1. vm.overcommit_memory = 1
echo 1 > /proc/sys/vm/overcommit_memory

# 2. Monitor memory usage: used_memory_human, maxmemory_human
# 3. Reserve 20-30% headroom: if dataset = 20GB, use 32GB instance
# 4. Alert on latest_fork_usec > 1s

# Calculate COW risk:
# COW = write_rate × avg_write_size × rewrite_duration
# rewrite_duration = dataset_size / disk_write_speed
# If COW > available_memory → OOM risk
```

### 8.5. Multi-Part AOF — Docker Volume Misconfiguration

**Nguyên nhân**: Redis 7+ dùng `appendonlydir/` nhưng Dockerfile bind mount chỉ file cũ.

```yaml
# WRONG (Redis 7+):
volumes:
  - ./appendonly.aof:/data/appendonly.aof  # File doesn't exist in Redis 7+!

# RIGHT:
volumes:
  - redis-data:/data  # Mount whole /data directory
```

**Dấu hiệu**:
```
Redis log: "AOF was enabled but the append only file doesn't exist"
Redis log: "Opening append only file appendonlydir/appendonly.1.0000000000000000.aof: No such file or directory"
```

**Fix**: Mount entire `/data` directory, không chỉ file cụ thể.

## 9. Real-world Examples

### Twitter/X — AOF `everysec` cho Rate Limiting với Alert Thresholds

Twitter dùng Redis cho distributed rate limiting (token bucket). Config: AOF `everysec` + dedicated SSD. Alert thresholds:
- `aof_delayed_fsync` delta > 0 in 5 minutes → alert
- `latest_fork_usec` > 500000 (0.5s) → alert
- `aof_last_bgrewrite_status` = error → P1 alert

**Rationale**: Rate limiting state có thể rebuild từ logs, nhưng rebuild mất thời gian → allow some requests through without rate limit → cascade. Nên dùng `everysec` để có ~1s data loss max.

### Discord — Multi-Part AOF Migration

Discord chạy Redis 6 đến 2022, migrate lên Redis 7. AOF file lớn (hundreds of GB) + họ muốn dùng Multi-Part AOF. Challenge: migration phải không downtime.

**Migration approach**:
1. Upgrade Redis binary (6→7) on replica first
2. Replica starts with MP-AOF (new format)
3. Verify replica sync and data integrity
4. Failover replica → new master
5. Old master upgraded offline
6. Result: zero-downtime migration, MP-AOF active

**Lesson**: Redis 7 MP-AOF is backward-compatible (can read old single AOF), but new format requires full rewrite to take advantage of RDB base for fast restart.

### Shopify — Hybrid Persistence với `no-appendfsync-on-rewrite yes`

Shopify dùng Redis cho job queue (类似 Sidekiq). Họ tune `no-appendfsync-on-rewrite yes` để giảm AOF rewrite overhead:

```txt
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes    # Don't fsync during rewrite
aof-use-rdb-preamble yes
aof-load-truncated yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

**Trade-off they accept**: Nếu crash during rewrite, mất thêm ~5-10 giây commands (rewrite buffer không fsynced). Nhưng job queue job thường có retry logic → acceptable. Đổi lại: rewrite chạy nhanh hơn, ít latency spike.

### Instagram — AOF `everysec` cho Counters với Aggressive Rewrite

Instagram counter service (likes, comments, followers) chạy AOF `everysec` với aggressive rewrite schedule. Họ monitor:
- AOF file size < 2× dataset size
- Rewrite runs at 3AM (low traffic window)
- Alert if rewrite takes > 10 minutes

**Tuning**: `aof-rewrite-incremental-fsync yes` (Redis 7+) → fsync after every 1MB during rewrite → reduces potential data loss from 32MB to 1MB on crash during rewrite.

### Redis Source Code — `src/aof.c` Key Functions

Tham khảo trong source code:

```
src/aof.c:
  - rewriteAppendOnlyFile()      — child process: serialize dataset to temp AOF
  - feedAppendOnlyFile()          — parent: append command to AOF + rewrite buffer
  - aofRewriteBufferWrite()       — parent: flush rewrite buffer to child
  - aofLoadFromDisk()             — restart: load AOF/RDB on startup
  - aofCheckAndFixCorruption()    — redis-check-aof --fix logic

src/server.c:
  - server.aof_state             — AOF on/off/wait rewrite states
  - server.aof_selected_db        — current DB being rewritten
  - server.aofRewriteBuffSize     — rewrite buffer size tracking
  - appendFsync()                — fsync policy implementation

src/anet.c:
  - anetSynopsisAccepted()       — accept connection during AOF rewrite
  - checkBlockedClient()          — handle blocked clients during rewrite
```

## 10. Common Pitfalls

1. **Nghĩ `appendfsync always` = "no data loss"**: Sai. Vẫn có gap: kernel page cache flush, disk controller cache, rare disk firmware bugs. Nếu cần 100% durability → dùng PostgreSQL/Kafka.

2. **Tune `auto-aof-rewrite-percentage` mà không monitor AOF file size**: Nếu baseline = 10GB, percentage = 100 → rewrite chỉ trigger khi AOF = 20GB. Bạn có thể hết disk trước khi rewrite trigger.

3. **Không monitor `aof_delayed_fsync`**: Counter tăng = disk không theo kịp → imminent fsync backlog → eventual write latency spike → client timeout.

4. **Dùng `appendfsync no` mà nghĩ "data vẫn an toàn vì có AOF"**: OS có thể mất tới 30+ giây data trên power loss. "An toàn" là tương đối.

5. **Không test `redis-check-aof --fix` trước khi production cần**: `--fix` sẽ truncate file. Nếu corrupt ở giữa, data sau đó mất. Test trên backup trước.

6. **Redis 7+ mount chỉ file AOF**: `appendonlydir/` là directory, không phải file. Mounting sai config → Redis start với empty AOF → data loss.

7. **`no-appendfsync-on-rewrite yes` mà không hiểu data loss implication**: Rewrite buffer không được fsync → crash during rewrite = mất thêm từ vài giây đến vài phút commands.

8. **AOF rewrite trên instance không có memory headroom**: COW spike + rewrite buffer → OOM. Tính toán: peak memory = dataset + COW + buffer + overhead.

9. **Dùng `BGREWRITEAOF` trên instance đang under heavy write load**: Rewrite chậm → rewrite buffer đầy → rewrite fail. Chạy manual rewrite khi load thấp.

10. **Nghĩ AOF là backup strategy**: AOF trên cùng server = single point of failure. Cần offsite backup (S3), replica, và tested restore procedure.

## 11. Câu hỏi tự kiểm tra

### Câu 1
**System**: Redis 7+ với 50GB dataset, AOF `everysec`. `aof_delayed_fsync` counter tăng từ 0 lên 50 trong 10 phút. Nguyên nhân gốc là gì và fix như thế nào?

<details>
<summary>Đáp án</summary>

**Nguyên nhân**: Disk không theo kịp AOF fsync rate. `aof_delayed_fsync` = số lần fsync bị skip vì fsync trước chưa xong. 50 lần skip trong 10 phút = trung bình 5 lần skip/phút = fsync mất > 12 giây mỗi lần → disk I/O quá chậm.

**Root causes có thể**:
1. AOF trên shared disk với write-heavy DB
2. SATA SSD thay vì NVMe
3. BGSAVE hoặc BGREWRITEAOF đang chạy đồng thời
4. Disk firmware issue hoặc RAID controller misconfigured

**Fix steps**:
```bash
# Step 1: Check disk type and I/O
iostat -x 1  # Look at %util, avgqu-sz, await

# Step 2: Check if BGSAVE/AOF rewrite running
redis-cli INFO persistence | grep -E "bgsave_in_progress|rewrite_in_progress"

# Step 3: Immediate fix — move to dedicated disk
redis-cli CONFIG SET dir /mnt/dedicated-nvme/redis

# Step 4: If no dedicated disk available:
redis-cli CONFIG SET appendfsync no
# Risk: up to 30s data loss. Only acceptable for ephemeral cache.

# Step 5: Long-term fix
# - Migrate to NVMe SSD dedicated to Redis
# - Separate AOF disk from database disk
# - Monitor aof_delayed_fsync: should stay at 0
# - Alert if > 0 in any 5-minute window
```

</details>

### Câu 2
**System**: 32GB Redis instance, dataset 25GB, write rate 50K ops/sec. Bạn cần chạy BGREWRITEAOF. Tính COW memory overhead và rủi ro OOM?

<details>
<summary>Đáp án</summary>

```
Rewrite duration estimate:
  - 25GB dataset / 500MB/s NVMe write = ~50 seconds
  - COW = write_rate × avg_write_size × duration
  - COW = 50K × 100 bytes × 50s = 250MB

Peak memory:
  - Used: 25GB (dataset)
  - COW: 250MB
  - Rewrite buffer: ~50MB (5 seconds × 50K × 100B × 0.1 = 50MB)
  - Child process: ~25GB (reads dataset via pipe)
  - Total peak: ~50.3GB (parent + child temporarily)

Instance: 32GB
  → 32GB < 50.3GB → OOM RISK HIGH

Risk assessment:
  - fork() itself: overcommit_memory=1 → won't fail on fork
  - But: parent + child both using memory → OOM kill possible
  - If child killed (OOM): aof_last_bgrewrite_status = error
  - If parent killed (OOM): Redis dead → data loss + downtime

Fix:
  1. Scale instance to 64GB (32GB headroom)
  2. OR reduce write rate during rewrite (read replica for writes)
  3. OR use aof-rewrite-incremental-fsync yes (Redis 7+) to reduce memory spike
  4. OR split dataset (sharding) to reduce per-node size
```

</details>

### Câu 3
**Scenario**: Bạn chạy `redis-check-aof --fix` trên AOF file 50GB. Kết quả: "AOF analyzed: size=50GB, ok=49.5GB, corruption=500MB at offset 52,428,800,000. Remove the 500MB tail?" Bạn nên làm gì?

<details>
<summary>Đáp án</summary>

**Phân tích**:
- Corruption ở 49.5GB/50GB → chỉ 500MB cuối bị corrupt
- 500MB / AOF file size = 1% data loss
- Nếu write rate = 100K ops/sec × 200 bytes = 20MB/s
- 500MB ≈ 25 giây commands
- Data mất: ~25 giây writes gần nhất

**Decision tree**:
```
Is this a idempotency store or financial system?
  YES → STOP, do not --fix. Call Redis expert.
        - PostgreSQL may have idempotency record
        - 25 seconds of missing idempotency = potential double-charge risk
        - Manual reconciliation may be needed

Is this a session store or job queue?
  YES → --fix is probably OK.
        - Sessions: users can re-login (25s gap = minor inconvenience)
        - Job queue: jobs have retry logic (25s gap = some missed jobs)
        - But: ALWAYS backup first, test on staging

Is this a cache?
  YES → --fix or rebuild from DB (depending on what's easier)
```

**Safe procedure**:
```bash
# 1. Stop Redis
redis-cli SHUTDOWN NOSAVE

# 2. Backup everything
cp -r /data/appendonlydir /backup/appendonlydir-$(date +%Y%m%d%H%M%S)

# 3. Test --fix on backup copy first
redis-check-aof --fix /backup/appendonlydir/appendonly.1.0000000000000000.aof

# 4. Verify backup fix works
redis-check-aof /backup/appendonlydir/appendonly.1.0000000000000000.aof

# 5. Apply fix to production
redis-check-aof --fix /data/appendonlydir/appendonly.1.0000000000000000.aof

# 6. Restart Redis
redis-server --appendonly yes --appenddirname appendonlydir

# 7. Monitor: check data integrity, check for inconsistencies
redis-cli DBSIZE
redis-cli INFO persistence | grep aof_last_load_duration_ms
```

</details>

### Câu 4
**Scenario**: Bạn có 3 use case trên cùng 1 Redis instance:
1. Rate limiter (1M keys, write-heavy)
2. User session store (500K keys)
3. Distributed lock (10K keys, write-light)

Bạn cấu hình persistence như thế nào? Có nên dùng 1 hay 3 instance?

<details>
<summary>Đáp án</summary>

**Option A: 1 instance với separate DB/prefix**

```txt
# Problem: persistence config is GLOBAL, can't set per key-pattern
# → Rate limiter: want everysec (acceptable data loss)
# → Session: want everysec (acceptable data loss)
# → Lock: want always (but locks need to be short TTL anyway)
```

**Recommendation: 2 instances**

```yaml
# Instance 1: Rate limiter + Session (everysec, acceptable data loss)
redis-app:
  command: >
    redis-server
    --save "300 1"
    --appendonly yes
    --appendfsync everysec
    --aof-use-rdb-preamble yes
    --aof-load-truncated yes
  # Shared: rate limiter + session store
  # Data loss OK: both can rebuild

# Instance 2: Distributed lock (always + short TTL)
redis-lock:
  command: >
    redis-server
    --save "900 1"
    --appendonly yes
    --appendfsync always
    --aof-use-rdb-preamble yes
    --aof-load-truncated yes
    --dir /mnt/nvme-redis-lock
  # Dedicated NVMe SSD for always fsync
  # Short lock TTL (10-30s) = even if crash, locks auto-expire
  # Monitor: aof_delayed_fsync MUST be 0
```

**Rationale**:
- Rate limiter + session: cùng durability requirement (~1s loss OK), same disk profile → share instance
- Distributed lock: `appendfsync always` yêu cầu dedicated fast disk + low latency → separate instance
- Lock có TTL ngắn → crash = locks tự expire sau vài chục giây → impact limited

**Cost trade-off**:
- 1 instance: simpler ops, cheaper, but can't optimize persistence per use case
- 2 instances: +50% cost, +50% ops complexity, but proper durability per use case

</details>

### Câu 5
**Benchmark**: Bạn benchmark Redis với `redis-benchmark -t SET -n 100000 -c 50` trên 3 config:
- Config A: `appendfsync no` → 180K ops/sec
- Config B: `appendfsync everysec` → 140K ops/sec
- Config C: `appendfsync always` → 35K ops/sec

Giải thích sự khác biệt và đưa ra recommendation cho use case nào dùng config nào.

<details>
<summary>Đáp án</summary>

**Phân tích**:

```
Config A (no): ~180K ops/sec
  - write(2) → page cache (fast, non-blocking)
  - No fsync overhead
  - Throughput maxed at network/CPU limit
  - Data loss: up to 30s (OS write-back)
  - Best for: truly ephemeral cache, in-memory-only workloads

Config B (everysec): ~140K ops/sec
  - write(2) to page cache + periodic fsync thread
  - 22% overhead vs no fsync (140K vs 180K)
  - Acceptable for: session store, job queue, most production
  - Data loss: ~1s max
  - Recommendation: DEFAULT choice for most use cases

Config C (always): ~35K ops/sec
  - Every SET: write(2) + fsync() blocking
  - 81% throughput drop vs no fsync (35K vs 180K)
  - SATA SSD: ~35K ops/sec
  - NVMe + PLP: ~80-100K ops/sec (still 50% drop)
  - Only acceptable for: financial idempotency + dedicated NVMe
  - WARNING: never use on SATA SSD or shared disk

Real-world recommendation by workload:
  - 100K+ ops/sec API cache: everysec (140K sufficient) or no (180K)
  - 10K ops/sec session: everysec (sufficient headroom)
  - 1K ops/sec payment idempotency: always on NVMe (100K capacity >> 1K needed)
  - 500K ops/sec rate limiter: everysec or no (1s loss OK for rate limit)
```

</details>

### Câu 6
**Docker Compose**: Bạn deploy Redis 7+ với Docker Compose. Sau vài ngày, AOF file không tồn tại ở expected path. Debug như thế nào?

<details>
<summary>Đáp án</summary>

**Root cause thường gặp**: Redis 7+ dùng `appendonlydir/` directory thay vì single file `appendonly.aof`.

```bash
# Step 1: Check Redis log
docker exec <container> cat /var/log/redis/redis.log | grep -i aof
# Expected: "AOF file not found, but the append only mode is enabled"

# Step 2: Check what files exist in /data
docker exec <container> ls -la /data/
docker exec <container> ls -la /data/appendonlydir/

# Step 3: Verify AOF state
docker exec <container> redis-cli INFO persistence | grep aof

# Common misconfigs:
# WRONG volume mount (Redis 7+):
#   volumes:
#     - ./appendonly.aof:/data/appendonly.aof  # File doesn't exist!
# 
# CORRECT volume mount:
#   volumes:
#     - redis-data:/data  # Mount entire /data directory
#
# OR (bind mount specific directory):
#   volumes:
#     - ./redis-data:/data  # ./redis-data must contain appendonlydir/

# Step 4: If AOF was expected to exist but doesn't:
# Check if appendonly was enabled AFTER container start
# Redis config changes at runtime don't retroactively create AOF files

# Step 5: Fix
# Option A: Stop, backup data, recreate volume with correct mount
# Option B: CONFIG SET appendonly yes (triggers new AOF creation)
redis-cli CONFIG SET appendonly yes
# Warning: CONFIG SET appendonly yes while running may not preserve existing AOF state
```

**Prevention**: Docker Compose template phải mount `/data` directory, không phải file cụ thể.

</details>

### Câu 7
**Trade-off**: `appendfsync everysec` có data loss window = ~1 giây. Nhưng bạn cần 0 data loss cho idempotency key. Bạn có thể làm gì để đạt được durability cao hơn mà không cần `appendfsync always`?

<details>
<summary>Đáp án</summary>

**Strategy: Layered durability** (Redis is NOT single source of truth)

```
Layer 1: Redis AOF everysec (fast path, ~1s loss)
Layer 2: PostgreSQL unique constraint (durable, 0 loss)
Layer 3: Redis replication to replica (additional safety net)
Layer 4: Application-level idempotency retry

Implementation:
  1. Idempotency key written to Redis (SETNX with TTL)
     → Redis everysec: ~1s data loss risk
  2. Same idempotency key written to PostgreSQL
     → PostgreSQL: 0 data loss (WAL + fsync)
     → PostgreSQL unique constraint: prevents double-insert
  3. On read:
     → Check Redis first (fast path)
     → If Redis miss: check PostgreSQL (durable path)
     → If PostgreSQL found: repopulate Redis + return
```

**Why this works**:
- Redis crash → PostgreSQL has idempotency record → no double-charge
- PostgreSQL crash → rare, but if happens, Redis still has key
- Replica lag → < 1s, acceptable for idempotency

**Performance**:
- Write path: 2 writes (Redis + PostgreSQL) → latency +2-5ms
- Read path: Redis hit → fast; Redis miss → PostgreSQL check
- Cost: acceptable for idempotency (low volume, high value)

**This is how Stripe, Shopify, and similar companies handle financial idempotency**: Redis for speed, PostgreSQL/Kafka for durability. Never rely on Redis alone for true durability.
</details>
