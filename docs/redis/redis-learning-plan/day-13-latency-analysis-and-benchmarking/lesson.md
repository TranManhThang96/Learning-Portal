# Day 13: Latency Analysis & Benchmarking

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân loại được 5 nguồn gốc latency (intrinsic, network, slow command, fork, persistence) và đo lường bằng `redis-cli --intrinsic-latency` và `LATENCY DOCTOR`.
- Cấu hình `SLOWLOG` với threshold phù hợp production, đọc và phân tích kết quả bằng script tự động.
- Chạy `redis-benchmark` và `memtier_benchmark` với các flags phù hợp để đo p50/p95/p99/p99.9 latency theo từng payload size.
- So sánh synthetic benchmark vs real workload, average vs percentile, local vs network — biết khi nào mỗi loại cho kết quả đáng tin.
- Viết benchmark report production-ready với số liệu reproducible.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: p99 Tăng Từ 200ms Lên 2s Sau Khi Bật AOF Rewrite

Một team benchmark Redis trước khi deploy: p99 = 200ms — OK. Sau khi enable AOF `appendfsync everysec`, p99 tăng lên 2s vài phút sau mỗi giờ. Không ai hiểu tại sao — vì synthetic benchmark `redis-benchmark` chạy trên localhost với payload nhỏ (16 bytes). Real workload: 10KB payload, 10K ops/sec, `BGREWRITEAOF` chạy mỗi giờ trigger AOF rewrite, disk I/O contention → latency spike không thấy trong benchmark.

**Lesson**: Synthetic benchmark không phản ánh production workload. Phải benchmark với realistic payload và duration.

### Incident 2: Bỏ Qua SLOWLOG -> Slow Command Kill Cluster

Một service có 500K keys trong một Sorted Set. Developer chạy `ZRANGEBYSCORE` với range lớn (0, +inf) mà không có `LIMIT`. Command mất 800ms — đủ nhanh để không ai nhận ra trong dev. Nhưng khi 50 instances cùng chạy → 50 slow commands/giây → Redis single-threaded bị blocking → tất cả commands queue lại → p99 tăng từ 5ms lên 500ms → cluster quá tải.

**Root cause**: Không có `SLOWLOG` monitoring, không có `slowlog-log-slower-than` threshold hợp lý.

### Incident 3: Benchmark Localhost Rồi Deploy WAN -> SLA Miss 40%

Một team đo throughput = 150K ops/sec trên localhost. Deploy lên production (Redis ở datacenter khác, RTT = 15ms) → real throughput chỉ = 5K ops/sec. Root cause: benchmark không tính network latency. Mỗi command mất 15ms × 2 (request + response) = 30ms RTT → 1000ms / 30ms = ~33 ops/sec per connection. Với 50 connections → ~1.6K ops/sec theoretical max.

**Lesson**: Benchmark trên localhost không có giá trị production nếu Redis thực sự ở WAN.

**Bottom line**: Latency analysis và benchmarking là kỹ năng phân biệt senior engineer với junior — vì sai lầm ở đây dẫn đến capacity misplanning, SLA miss, và production outage mà không ai thấy trước.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model, event loop, I/O multiplexing (Day 1)
- TCP handshake, RTT, TLS basics (Day 12)
- Pipeline và batch (Day 11)
- AOF, RDB, fork, COW (Day 6, Day 7)
- Connection pool size và timeout (Day 12)
- Các data structures và Big O operations (Day 2, Day 3)

---

## 4. Lý thuyết chi tiết

### 4.1. Nguồn Gốc Latency

Latency của một Redis command = tổng của nhiều thành phần:

```txt
Total Latency = T_network + T_intrinsic + T_command + TPersistence + T_fork

Trong đó:
  T_network    = RTT (Round Trip Time) + network switch/router delay
  T_intrinsic  = OS kernel + Redis event loop overhead
  T_command    = actual command processing time (O(1) vs O(N))
  T_persistence = fsync (AOF) hoặc disk I/O (RDB save)
  T_fork        = COW fork overhead (RDB snapshot, AOF rewrite)
```

#### T_intrinsic Latency

Đây là overhead cố định của Redis event loop — không thể loại bỏ.

```txt
Intrinsic latency components:
  - epoll/kqueue/IOCP system call overhead: ~0.05-0.1ms
  - Redis event loop dispatch: ~0.01-0.05ms per command
  - Timer wheel processing: ~0.01ms
  - Memory allocation (jemalloc): ~0.01-0.1ms

Total intrinsic (measured by redis-cli --intrinsic-latency):
  - No TLS:      ~0.05-0.15ms per command
  - With TLS:    ~0.1-0.3ms per command
  - Under CPU contention: can spike to 1-5ms
```

**Measure intrinsic latency**:
```bash
# Measure intrinsic latency (no network, local Redis)
redis-cli --intrinsic-latency 120

# Sample output:
# Max latency base: 0.54 microseconds
# 120 seconds total, 1234567 operations sampled
```

**Khi nào intrinsic latency tăng**:
- CPU contention: other processes on same host consuming CPU
- Hypervisor/noise from co-located VMs
- Transparent huge pages (THP) — **disable THP on Redis hosts**
- GC pause (if using Redis with Java client side, not Redis itself)

#### T_network Latency

```txt
RTT (Round Trip Time):
  - Loopback (localhost):     ~0.05ms
  - LAN (same datacenter):    ~0.5-1ms
  - WAN (cross-datacenter):   ~5-30ms
  - Internet (cloud regions): ~50-150ms

Network latency components:
  - TCP handshake (if new connection): +1 RTT
  - TLS handshake: +1-2 RTT
  - Command request: 1 RTT minimum
  - Command response: included in same RTT

Effective throughput per connection:
  RTT = 1ms  →  ~1000 ops/sec per connection (pipelining helps)
  RTT = 10ms →  ~100 ops/sec per connection
  RTT = 100ms→  ~10 ops/sec per connection
```

#### T_command Latency (Slow Command)

Đây là nguồn latency lớn nhất thường gặp trong production.

```txt
Command latency by complexity:

O(1)  commands: GET, SET, SETEX, INCR, HGET, SADD, SISMEMBER
        → 0.05-0.2ms (LAN)
        → dominant factor = network

O(log N) commands: ZADD, ZRANGEBYSCORE, ZRANK
        → 0.1-0.5ms for N=10K
        → 1-5ms for N=1M

O(N) commands: KEYS, SMEMBERS, LRANGE, HGETALL, ZRANGE without LIMIT
        → N = number of elements accessed
        → 1ms for N=1K, 100ms for N=100K, seconds for N=1M

O(N+M) commands: SUNION, SINTER, ZUNIONSTORE
        → proportional to total elements across all sets

O(M×log N) commands: ZINTERSTORE with M sorted sets
        → intersection of multiple sorted sets
```

**Dangerous commands** (never run in production without LIMIT):
```bash
KEYS *                    # O(N) — scans entire keyspace
KEYS user:*               # O(N) — same, no index
SMEMBERS huge_set         # O(N) — returns all members
LRANGE huge_list 0 -1      # O(N) — returns all elements
HGETALL huge_hash          # O(N) — returns all fields
ZRANGE huge_zset 0 -1      # O(log N + N) — no LIMIT = all elements
SUNIONSTORE set1 set2 ...  # O(N) — proportional to total elements
FLUSHDB / FLUSHALL         # O(N) — deletes all keys, blocks event loop
```

#### T_fork Latency

Fork latency xảy ra khi Redis tạo child process (RDB snapshot hoặc AOF rewrite).

```txt
Fork process:
  Parent process (Redis) calls fork()
    → Creates child process with copy of parent address space
    → Linux: uses copy-on-write (COW)
    → Parent memory is NOT duplicated, only copied when written

Fork latency factors:
  - Redis memory size: fork_time ∝ used_memory
    used_memory = 1GB  → fork ~10-50ms
    used_memory = 10GB → fork ~100-500ms
    used_memory = 50GB → fork ~500ms-2s
  - CPU speed: faster CPU = faster fork
  - THP (transparent huge pages): ENABLE → fork 2-5× slower
  - VM environment: co-locate with other VMs → variable

What happens during fork:
  t=0:    fork() called
  t=~50ms: fork completes (COW page tables created)
  t=~50ms: child starts running BGSAVE command
  t=ongoing: COW pages copied as parent writes to memory
```

**KPI: fork per second (INFO stats)**:
```txt
# INFO stats | grep -E "latest_fork_usec|total_forks"
latest_fork_usec: 543210   # microseconds = 543ms
total_forks: 1234
```

#### T_persistence Latency

```txt
fsync policies:

appendfsync no:
  - OS decides when to sync to disk
  - Lowest latency (0ms added to write)
  - Highest data loss risk (up to 30s of writes)
  - Use when: Redis as cache, can lose all data on crash

appendfsync everysec:
  - Sync once per second (async)
  - Adds ~0-1ms average latency (one sync per second)
  - p99 latency spike: ~1 second (when sync happens)
  - Data loss: up to 1 second of writes
  - RECOMMENDED for most production workloads

appendfsync always:
  - Sync after every write (blocking)
  - Adds 5-20ms latency per write (depends on disk speed)
  - Data loss: only if OS crashes
  - Use when: financial-grade durability needed

Disk I/O contention:
  - AOF rewrite: reads entire AOF file, rewrites compacted version
  - Heavy AOF write + disk-slow → latency spike
  - Solution: use SSD, separate disk from data volume
```

### 4.2. Latency Distribution

Average latency không phản ánh user experience. Latency distribution mới là thứ cần optimize.

```txt
Latency distribution of 1M operations (p99 = 100ms):

p50   =   1ms  (50% of requests < 1ms)
p75   =   5ms  (25% of requests between 1-5ms)
p90   =  20ms  (10% of requests between 5-20ms)
p95   =  50ms  (5% of requests between 20-50ms)
p99   = 100ms  (1% of requests between 50-100ms)
p99.9 = 500ms  (0.1% of requests > 100ms)

Distribution shape:
  Normal (Gaussian):
    Most requests fast, tail is short
    Average ≈ p50

  Bimodal (common in Redis issues):
    Peak 1: fast requests (95%) → p50 = 1ms
    Peak 2: slow requests (5%) → p95 = 50ms
    Average skewed by slow tail

  Heavy tail (worst case):
    Most requests fast
    Small % very slow (1-10 seconds)
    Average OK, but user experience terrible
```

```txt
ASCII: Why average is misleading

Scenario: 100 operations
  99 operations: 1ms each
  1 operation:   100ms

Average = (99×1 + 100) / 100 = 1.99ms  ← looks OK
p99     = 100ms                         ← user experience is BAD

p50 vs Average:
  If distribution is skewed (heavy tail):
    Average > p50 (common)
  If distribution is normal:
    Average ≈ p50

Always report p50, p95, p99, max — never just average.
```

### 4.3. SLOWLOG

`SLOWLOG` ghi lại tất cả commands vượt quá threshold — công cụ quan trọng nhất để debug slow command.

#### Configuration

```bash
# Threshold: log commands slower than N microseconds
# Default: 10000 (10ms) — TOO LOOSE for most production
# Recommended: 1000 (1ms) for low-latency apps, 5000 (5ms) for standard
slowlog-log-slower-than 1000

# Max entries in slowlog (keep last N commands)
# Default: 128 — TOO SMALL for production
# Recommended: 1000-10000 depending on traffic
slowlog-max-len 1000

# Config in redis.conf:
slowlog-log-slower-than 1000
slowlog-max-len 10000
```

#### Commands

```bash
# Get all slowlog entries
SLOWLOG GET

# Get last N entries (e.g., last 10)
SLOWLOG GET 10

# Get slowlog entries with length (without fetching all)
SLOWLOG LEN

# Reset slowlog (clears all entries)
SLOWLOG RESET

# Note: SLOWLOG is stored in memory (ring buffer), not persisted
```

#### SLOWLOG Entry Format

```txt
1) 1) (integer) id           # Unique entry ID (increments)
   2) (integer) timestamp     # Unix timestamp when command started
   3) (integer) duration      # Execution time in microseconds
   4) 1) "ZRANGEBYSCORE"     # Command + arguments
      2) "leaderboard:global"
      3) "0"
      4) "+inf"
      5) "LIMIT"
      6) "0"
      7) "10000"              # ← DANGER: no LIMIT → O(N)
   5) (integer) client_ip     # Client IP (integer in older Redis)
   6) (string)  client_name   # CLIENT SETNAME value
```

#### Example: Identifying Problematic Commands

```bash
# Run workload that generates slow commands
redis-cli SLOWLOG RESET

# Simulate slow command
redis-cli ZRANGEBYSCORE leaderboard 0 +inf

# Check slowlog
redis-cli SLOWLOG GET

# Analyze duration distribution
redis-cli SLOWLOG GET | awk '{print $3}' | sort -n | awk '
  BEGIN { total=0; count=0 }
  { total+=$1; count++ }
  END {
    avg=total/count/1000;
    print "Avg: " avg "ms, Count: " count
  }'
```

#### SLOWLOG Storage Consideration

```txt
SLOWLOG is stored in memory (linked list):
  - Each entry: ~200-500 bytes depending on command length
  - slowlog-max-len 10000 → ~2-5MB memory overhead
  - Ring buffer: old entries dropped when full

SLOWLOG is NOT persisted to AOF/RDB:
  - Lost after Redis restart
  - For persistence: poll SLOWLOG periodically and write to external store
  - Or use Redis audit log (Redis 6.2+ with module/ACL)

Monitoring strategy:
  - Poll SLOWLOG LEN every 30 seconds
  - Alert if slowlog length > 0 (means threshold was exceeded)
  - Aggregate SLOWLOG GET results to Prometheus/Grafana
```

### 4.4. LATENCY Commands (Redis 7+)

`LATENCY` family commands cung cấp introspection về latency events.

#### LATENCY DOCTOR

```bash
LATENCY DOCTOR

# Sample output:
Dave, I have observed latency spikes in your Redis instance.
Your Redis version 7.2 has a configured slowlog-log-slower-than threshold
of 1000 microseconds.

I have detected 45 latency spikes in the last 2 hours, most recent 60 seconds ago.
The latest latency event was 127 milliseconds.

I have found 4 distinct latency events in this Redis instance:

1. Command:  (command execution) - 3 events, avg 95ms
   Description: Slow commands detected by SLOWLOG.
   This is **expected** if you have slow commands (see SLOWLOG GET).
   Latency is usually caused by slow commands (see SLOWLOG GET).

2. Command: fork (fork time) - 1 event, 543ms
   Description: Fork time of 543ms indicates slow disk or high memory usage.
   Check disk speed with 'hdparm -t /dev/sda' and memory usage.

3. Command: rdb-unlink-temp-file (temp file unlink) - 1 event, 42ms
   Description: Time needed to unlink temporary RDB file.
   May indicate high memory pressure or slow disk I/O.

4. Command: fast-command (non-commands) - 40 events, avg 0.8ms
   Description: Non-command time such as TTL and key eviction.
   This is **expected** under memory pressure or key expiration.
```

#### LATENCY HISTORY

```bash
LATENCY HISTORY fork

# Sample output:
1) 1) (integer) 1700000000     # Unix timestamp
   2) (integer) 543210         # Latency in microseconds

2) 1) (integer) 1699990000
   2) (integer) 432100
```

#### LATENCY LATEST

```bash
LATENCY LATEST

# Sample output:
1) 1) "command"              # Event name
   2) (integer) 1700000600   # Unix timestamp
   3) (integer) 127000       # Latency in microseconds (127ms)
   4) (integer) 45           # Number of samples for this event
   5) 1) "ZRANGEBYSCORE"
      2) "leaderboard:global"
      3) "0"
      4) "+inf"
```

#### LATENCY RESET

```bash
# Reset history for a specific event
LATENCY RESET fork

# Reset all events
LATENCY RESET

# Reset events with minimum count
LATENCY RESET command 10  # Reset if >= 10 events recorded
```

#### LATENCY GRAPH (Redis 7.2+)

```bash
LATENCY GRAPH command

# ASCII graph of latency over time
command - latencies in microseconds, 60 seconds window
This Redis instance was started at: 2024-01-01 00:00:00.000000

0.3s -\
0.3s -|\
0.3s -| |\
0.3s -| | |
0.3s -| | |\
0.3s -| | | |\
0.3s -| | | | |  127ms spike at 59s ago
0.3s -| | | | |  |
0.3s -| | | | |  |
0.3s -| | | | |  |
0.3s -|_________|  |_____________________________
0s    10s   20s   30s   40s   50s   60s   70s
```

### 4.5. redis-cli Latency Tools

#### redis-cli --latency

Measure round-trip latency by sending PING commands.

```bash
# Measure latency continuously (1 sample per second)
redis-cli --latency

# Sample output:
min: 0, max: 1, avg: 0.12 (3821 samples)

# With history (show latency per sample)
redis-cli --latency-history

# Sample output (30-second intervals):
$0 127.0.0.1:6379 (redis-cli 7.2.0)
$1 127.0.0.1:6379 (redis-cli 7.2.0)
latency is 0.12ms
latency is 0.15ms
...
```

#### redis-cli --latency-dist

```bash
# Show latency distribution histogram (requires Redis 7+)
redis-cli --latency-dist

# ASCII histogram output showing latency buckets
```

#### redis-cli --intrinsic-latency

```bash
# Measure intrinsic (server-side) latency without network
# Run for 120 seconds to get accurate baseline
redis-cli --intrinsic-latency 120

# Sample output:
Max latency base: 0.54 microseconds
This instance is a good candidate for benchmarking.
120 seconds total, 234567 operations sampled.

# Interpretation:
# - 0.54 microseconds = 0.00054ms intrinsic overhead per command
# - This is the baseline — any extra latency = network + command + contention
```

#### redis-cli --scan-and-sort (for big key detection)

```bash
# Measure latency of SCAN + SORT operations (pattern-based)
redis-cli --scan-and-sort
```

### 4.6. redis-benchmark

`redis-benchmark` là tool built-in để measure throughput và latency.

#### Syntax

```bash
redis-benchmark [OPTIONS]

Key options:
  -h <hostname>      Server hostname (default: 127.0.0.1)
  -p <port>          Server port (default: 6379)
  -a <password>      Password
  -c <clients>       Number of parallel connections (default: 50)
  -n <requests>      Total number of requests (default: 100000)
  -d <size>          Data size of SET/GET value in bytes (default: 3)
  -r <range>         Use random keys for SET/GET (random suffix)
  -P <num流水线>      Pipeline N commands (default: 1 = no pipeline)
  -t <commands>      Run only specific commands (comma-separated)
  --cluster         Enable cluster mode
  --threads <n>      Use multiple threads (Redis 6+)
  -q                 Quiet output (shows only ops/sec and latency)
  --csv             Output in CSV format
  -l                 Loop (run benchmark forever)
  --dbnum <db>       Database number
  --pipe-timeout <n> Timeout for --pipe in seconds
```

#### Common Usage Patterns

```bash
# Basic GET benchmark (default: 50 clients, 100K requests, 3 bytes)
redis-benchmark

# GET with realistic payload (1KB value)
redis-benchmark -t get -d 1024 -n 100000 -c 50

# Mixed workload (80% GET, 20% SET)
redis-benchmark -t get,set -r 100000 -n 1000000 -c 100

# Pipeline benchmark (batch 16 commands per RTT)
redis-benchmark -t get -P 16 -n 100000 -c 50

# Measure p50/p95/p99 latency
redis-benchmark -t get -n 10000 -c 10 --latency

# Benchmark specific commands only
redis-benchmark -t set,get,lpush,lrange -n 10000 -c 20

# Random keys (avoid hot key)
redis-benchmark -t get -r 1000000 -n 100000

# Run for 60 seconds continuously
redis-benchmark -t get -c 50 -d 256 -D 60

# CSV output for automation
redis-benchmark -t get,set -n 10000 --csv > benchmark.csv
```

#### Understanding redis-benchmark Output

```txt
# Sample output:
redis-benchmark -t get -n 100000 -c 50 -d 256

# ===== GET =====
# 100000 requests completed in 1.23 seconds
# 50 parallel clients
# 3 bytes payload
# ++++ Keep-Alive used, probably.

# Summary:
#   throughput summary: 81300.82 requests per second
#   latency summary (microseconds):
#         50.000%   0.063000 ms
#         75.000%   0.078000 ms
#         90.000%   0.094000 ms
#         99.000%   0.156000 ms
#         99.900%   0.516000 ms
#         99.990%   1.232000 ms
#         99.999%   2.847000 ms
```

#### redis-benchmark Limitations

```txt
redis-benchmark weaknesses:
  1. Single-threaded (unless --threads used in Redis 6+)
  2. Same value repeated for all GETs (hot key simulation)
  3. No command distribution modeling (all requests = same command)
  4. Localhost only (can't easily benchmark WAN latency)
  5. No percentile beyond p99.999
  6. Fixed request rate (not realistic burst traffic)

When to use:
  - Baseline comparison between Redis versions
  - Smoke test after config changes
  - Quick sanity check

When NOT to use:
  - Production capacity planning (use memtier_benchmark)
  - Realistic workload simulation (use real traffic replay)
  - WAN latency measurement (use real clients)
```

### 4.7. memtier_benchmark

`memtier_benchmark` (by Redis Labs, part of RedisGears) là tool benchmark production-grade.

#### Installation

```bash
# Ubuntu/Debian
apt-get install memtier-benchmark

# From source (RedisLabs/memtier_benchmark on GitHub)
git clone https://github.com/RedisLabs/memtier_benchmark.git
cd memtier_benchmark
./configure && make

# Docker
docker run --rm redislabs/memtier_benchmark:latest --help
```

#### Key Options

```bash
memtier_benchmark [options]

Connection & load:
  -s, --server=<addr>          Server address (default: localhost)
  -p, --port=<port>            Server port (default: 6379)
  -a, --auth-password=<pwd>    Password
  -c, --clients=<n>            Concurrent clients (default: 50)
  -t, --threads=<n>            Worker threads (default: 4)
  -P, --pipeline=<n>           Pipeline depth (default: 1)

Workload:
  -n, --requests=<n>           Requests per client (default: 10000)
  -d, --data-size=<bytes>      Value size (default: 32)
  -R, --random-data             Use random data (key suffix + random value)
  --key-pattern=<pattern>      Key pattern (e.g., "S:R" = SET:GET ratio)
  --ratio=<N:M>                SET:GET ratio (e.g., --ratio=1:10 = 10% writes)
  --lookaside-ratio=<N:M>      Ratio for key lookaside pattern

Output:
  -q, --quiet                  Quiet mode
  --show-config                Show config before running
  --print <masks>              Print latency per operation type
  --json-out-file=<file>       JSON output
  --csv-out-file=<file>        CSV output
  --latency-resolution=<ms>    Latency histogram resolution (default: 1ms)

Cluster:
  --cluster-mode               Enable Redis Cluster mode
  --use-cluster-slots-verification  Verify cluster slot mapping
```

#### Common Usage Patterns

```bash
# Basic GET benchmark
memtier_benchmark -s localhost -p 6379 -t 4 -c 50 -n 100000

# Mixed workload: 10% writes, 90% reads, 1KB values
memtier_benchmark \
  -s localhost \
  -t 4 -c 100 \
  --ratio=1:9 \
  -d 1024 \
  -n 100000

# Random keys (avoid hot key)
memtier_benchmark \
  -s localhost \
  -R \
  --key-pattern=R:R \
  -t 4 -c 50

# Measure latency histogram (p50/p95/p99/p99.9)
memtier_benchmark \
  -s localhost \
  -t 4 -c 50 \
  --latency-resolution=0.1 \
  -n 50000 \
  --print-full-latency

# Pipeline benchmark (batch 16)
memtier_benchmark \
  -s localhost \
  -P 16 \
  -t 4 -c 50

# JSON output for Prometheus/Grafana integration
memtier_benchmark \
  -s localhost \
  -t 4 -c 50 \
  --json-out-file=/tmp/benchmark.json \
  -n 100000

# Benchmark over network (WAN simulation)
memtier_benchmark \
  -s redis.prod.example.com \
  -p 6379 \
  -t 4 -c 20 \
  -d 512 \
  -n 100000
```

#### memtier_benchmark vs redis-benchmark

| Aspect | redis-benchmark | memtier_benchmark |
|---|---|---|
| Multi-threading | Basic (--threads in Redis 6+) | Full multi-thread support |
| Latency distribution | p50-p99.999 | Full histogram (p50-p99.9+) |
| Pipeline support | Yes | Yes |
| Cluster mode | Yes (--cluster) | Yes (--cluster-mode) |
| Random keys | Yes (-r) | Yes (-R) |
| SET:GET ratio | No | Yes (--ratio) |
| Realistic workload | No (single command) | Yes (mixed workload) |
| Installation | Built into Redis | Separate install |
| JSON/CSV output | Yes (--csv) | Yes |
| Auth support | Yes (-a) | Yes |
| Connection distribution | Uniform | Configurable |

---

## 5. Trade-off Analysis

### 5.1. Synthetic Benchmark vs Real Workload Benchmark

| Aspect | Synthetic (redis-benchmark) | Real Workload (memtier + production traffic) |
|---|---|---|
| Repeatability | High (same conditions every run) | Variable (real traffic patterns change) |
| Setup complexity | Low (built-in tool) | High (need traffic capture/replay) |
| Production accuracy | Low (single command, uniform) | High (mirrors actual patterns) |
| Use when | Quick baseline, version comparison | Capacity planning, SLA validation |
| Risk | False confidence (looks great, fails in prod) | Hard to reproduce exactly |
| Cost | Free, fast | Requires production traffic analysis |

**Recommendation**: Start with synthetic for baseline. Validate with realistic workload before major capacity decisions.

### 5.2. Average Latency vs Percentile Latency

| Aspect | Average Only | Percentile (p95/p99/p99.9) |
|---|---|---|
| Easy to understand | Yes | p50/p95 OK, p99.9 harder |
| Captures user experience | No (skewed by outliers) | Yes (tail = worst users) |
| Good for SLO | No | Yes (p99 is standard SLO) |
| Requires | Sum/count | Sorted histogram |
| Misleading when | Distribution is bimodal | N/A |
| Recommendation | Supplement only | Primary metric for SLA |

**Recommendation**: Always report p50, p95, p99. Average is useless alone for latency.

### 5.3. Throughput Max vs Stable Latency

| Aspect | Optimize Throughput (max ops/sec) | Optimize Stable Latency |
|---|---|---|
| Goal | Push Redis to limit | Keep latency predictable |
| Config | Large pipelining, many connections | Smaller batches, conservative pool |
| Latency at limit | High variance, spikes | Low, consistent |
| SLA fit | Not suitable for low-latency SLO | Ideal for SLA-bound services |
| Use when | Batch jobs, background processing | User-facing APIs, real-time |
| Risk | p99 can be 10× average | May underutilize Redis |

**Example**: With pipelining 50:
- Throughput: 200K ops/sec
- p99 latency: 25ms (batching adds queueing)
- Without pipeline (batch 1):
- Throughput: 50K ops/sec
- p99 latency: 1ms (immediate response)

### 5.4. Local Benchmark vs Network Benchmark

| Aspect | Localhost (localhost) | Network (real network) |
|---|---|---|
| RTT | ~0.05ms | 0.5-150ms |
| Throughput ceiling | Very high (no network limit) | Network bandwidth limited |
| Latency ceiling | Unrealistic low | Realistic |
| Use when | Redis server performance only | Real deployment validation |
| Valid for prod? | Only if prod is also localhost | Yes |
| Key risk | Overestimate throughput 10-100× | N/A |

**Rule**: Benchmark production topology. If Redis is remote, benchmark remotely.

---

## 6. Best Solution & Best Practices

### 6.1. SLOWLOG Configuration

```bash
# redis.conf

# Low-latency service (<10ms p99 SLA):
slowlog-log-slower-than 500   # 0.5ms — catch anything over half-millisecond

# Standard service (<50ms p99 SLA):
slowlog-log-slower-than 5000  # 5ms — catch slow commands

# Background monitoring / analytics:
slowlog-log-slower-than 10000 # 10ms — only significant slow commands

# Max entries: keep enough history to spot patterns
slowlog-max-len 10000

# Alerting: poll SLOWLOG LEN periodically
# If slowlog_len > 0 → alert
# If slowlog_len growing → trend alert
```

### 6.2. Latency Monitoring Stack

```txt
Production latency monitoring:

Layer 1: SLOWLOG (command-level)
  - Catches: slow commands, fork, eviction, expiration
  - Polling: every 30 seconds
  - Storage: external (Prometheus/Grafana) via SLOWLOG GET parsing

Layer 2: LATENCY DOCTOR (weekly check)
  - Use: redis-cli LATENCY DOCTOR
  - Frequency: weekly or when investigating issues
  - Stored: incident management system

Layer 3: Application-level latency
  - P50/P95/P99 from client library
  - Stored: Prometheus histogram
  - Alert: p99 > threshold

Layer 4: Redis INFO stats
  - instantaneous_ops_per_second
  - hit_rate
  - evicted_keys
  - keyspace_hits_misses
  - total_commands_processed
```

### 6.3. Benchmarking Checklist

```bash
# Before running benchmark:

# 1. Redis config check
redis-cli INFO | grep -E "redis_version|os|used_memory_human|maxmemory"

# 2. Clear slowlog
redis-cli SLOWLOG RESET

# 3. Flush test data (if needed)
redis-cli FLUSHALL

# 4. Warm up (populate data)
redis-cli --scan | head -10000 | xargs -r redis-cli DEL

# 5. Run benchmark with realistic parameters
memtier_benchmark \
  -s localhost \
  -t 4 \
  -c 100 \
  -d 1024 \
  -R \
  --ratio=1:9 \
  --json-out-file=/tmp/bench.json

# 6. Check slowlog after benchmark
redis-cli SLOWLOG LEN
redis-cli SLOWLOG GET 10

# 7. Compare p50/p95/p99 against SLO
```

### Anti-patterns

1. **Benchmark localhost, deploy WAN**: Different topology → different results.
2. **Use GET-only benchmark for write-heavy workload**: Real workload = mixed read/write.
3. **Set payload size too small**: Default redis-benchmark = 3 bytes. Real values = 100B-10KB.
4. **Ignore warm-up**: Cold Redis data may fit CPU cache → unrealistic fast.
5. **One-shot benchmark**: Run for 10 seconds. Real traffic has bursts, sustained load.
6. **No pagination of slowlog**: Fetching all slowlog entries on high-traffic Redis = slow.
7. **Setting slowlog-log-slower-than = 0**: Logs everything → performance impact.
8. **Benchmark on shared infrastructure**: Co-located VMs = noisy neighbor → variable results.

---

## 7. Performance Considerations

### 7.1. Slow Command Latency by Operation

```txt
Operation complexity vs latency (approximate, LAN, Redis 7.2):

O(1) operations (constant time):
  GET/SET/DEL/EXISTS/INCR/DECR:       0.05-0.2ms
  HSET/HGET/HSETNX:                   0.05-0.3ms
  SADD/SISMEMBER/SREM:                 0.05-0.3ms
  SETBIT/GETBIT:                       0.05-0.2ms

O(log N) operations (logarithmic):
  ZADD/ZRANK/ZSCORE (N=10K):         0.1-0.5ms
  ZADD/ZRANK/ZSCORE (N=1M):          0.5-2ms
  ZRANGEBYSCORE with LIMIT (N=1M):   1-5ms

O(N) operations (linear):
  SMEMBERS (N=1K):                   0.5-2ms
  SMEMBERS (N=100K):                 50-200ms
  LRANGE 0 -1 (N=10K):               5-20ms
  HGETALL (N=100 fields):            1-5ms
  HGETALL (N=10K fields):            100-500ms

O(N+M) operations:
  SUNION (2 sets, 50K+50K elements):  20-100ms
  SINTER (2 sets, 10K each):          5-20ms
  ZUNIONSTORE (3 sorted sets):        10-50ms
```

### 7.2. Pipeline Size vs Latency

```txt
Pipeline depth vs effective throughput and latency:

Depth 1 (no pipeline):
  1 command per RTT
  RTT = 1ms → 1000 ops/sec per connection
  Latency per command: 1ms (p50)

Depth 10:
  10 commands per RTT
  10× throughput
  Latency: first command = 1ms, last = 10ms
  Effective latency per command: ~5.5ms average (1+10)/2

Depth 50:
  50 commands per RTT
  Latency: first = 1ms, last = 50ms
  Average latency per command: ~25ms

Depth 100:
  100 commands per RTT
  Average latency: ~50ms
  Risk: if any command fails, entire pipeline fails

Trade-off:
  - High throughput: large pipeline
  - Low latency: small pipeline
  - Sweet spot: pipeline 10-50 depending on RTT
  - For RTT=1ms: pipeline 50 → 50K ops/sec
  - For RTT=10ms: pipeline 10 → 1K ops/sec
```

### 7.3. P95/P99 Impact of Slow Commands

```txt
Scenario: Normal commands = 1ms, but 1% of commands are slow (100ms)

Without slow commands:
  p95 = 1ms
  p99 = 1.5ms
  Average = 1ms

With 1% slow commands (100ms):
  p95 = 1ms (still below slow command threshold)
  p99 = 100ms (the slow command enters p99)
  p99.9 = 100ms (only 0.1% exceed 100ms)
  Average = (0.99×1 + 0.01×100) = 1.99ms (looks OK!)

With 5% slow commands (100ms):
  p95 = 100ms (slow commands dominate p95)
  p99 = 100ms
  Average = (0.95×1 + 0.05×100) = 5.95ms

Lesson: Even 1% slow commands can dominate p99.
SLOWLOG threshold should be set to catch anything above p95.
```

### 7.4. Fork Latency vs Memory Size

```txt
Fork latency (approximate, modern hardware):

used_memory = 1GB   → fork = 10-50ms
used_memory = 5GB   → fork = 50-200ms
used_memory = 10GB  → fork = 100-500ms
used_memory = 50GB  → fork = 500ms-2s
used_memory = 100GB → fork = 1-4s (with THP disabled)

Impact:
  - RDB snapshot: fork + COW during save
  - AOF rewrite: fork (for bgrewriteaof child process)
  - Fork blocks parent: NO (fork is async after creation)
  - But: COW pages during fork can cause latency if memory writes are heavy

Mitigation:
  - Disable transparent huge pages (THP): echo never > /sys/kernel/mm/transparent_hugepage/enabled
  - Use faster disk (NVMe SSD) for AOF
  - Separate AOF disk from data disk
  - Use COW-friendly data patterns (read-heavy, low write during snapshot)
```

---

## 8. Production Failure Modes

### 8.1. Silent Slow Command Accumulation

**Nguyên nhân**: Slow commands xuất hiện không đều đặn (peak hour), không bị noticed cho đến khi p99 tăng đột ngột.

**Dấu hiệu**:
- `SLOWLOG LEN` tăng dần trong giờ cao điểm
- Application logs có spike latency không giải thích được
- `LATENCY DOCTOR` report command event với frequency cao

**Debug**:
```bash
# Check slowlog in real-time (watch)
watch 'redis-cli SLOWLOG GET 10 | grep -E "duration|command"'

# Check slowlog entry details
redis-cli SLOWLOG GET 1 | python3 -c "
import sys, json
for entry in json.load(sys.stdin):
    print(f'Command: {entry[3]}')
    print(f'Duration: {entry[2]/1000:.2f}ms')
    print(f'Time: {entry[1]}')
"

# Identify slow command pattern
redis-cli SLOWLOG GET 100 | awk '
  /ZRANGEBYSCORE|SMEMBERS|HGETALL|KEYS|LRANGE/ { count++ }
  END { print "Slow command count:", count }
'
```

**Phòng tránh**:
- Set `slowlog-log-slower-than` = p95 threshold (e.g., 5ms)
- Alert when `SLOWLOG LEN` > 0
- Monitor slow command by type (aggregate SLOWLOG entries)

### 8.2. Fork Latency Spike

**Nguyên nhân**: Redis RDB snapshot hoặc AOF rewrite trigger fork, memory lớn → fork chậm.

**Dấu hiệu**:
- Latency spike định kỳ (every hour if RDB saves)
- `INFO stats | grep latest_fork_usec` cao bất thường
- `LATENCY HISTORY fork` shows spikes

**Debug**:
```bash
# Check fork latency
redis-cli INFO stats | grep latest_fork

# Check fork history
redis-cli LATENCY HISTORY fork

# Check memory usage
redis-cli INFO memory | grep used_memory_human

# Check THP status
cat /sys/kernel/mm/transparent_hugepage/enabled

# Benchmark disk I/O
hdparm -t /dev/sda
```

**Fix**:
1. Disable THP: `echo never > /sys/kernel/mm/transparent_hugepage/enabled`
2. Reduce memory footprint hoặc shard
3. Move AOF/RDB to faster disk
4. Adjust RDB save schedule (less frequent snapshots)
5. Use slower but less frequent AOF rewrite

### 8.3. Latency Bimodal Distribution

**Nguyên nhân**: Two distinct populations: fast commands + slow commands. Average OK, but p95/p99 bad.

**Dấu hiệu**:
- p50 = 1ms, p95 = 100ms (huge gap = bimodal)
- `SLOWLOG` shows slow commands
- Latency histogram has two peaks

**Debug**:
```bash
# Check slowlog for command types
redis-cli SLOWLOG GET 100 | jq '.[3][]' | sort | uniq -c | sort -rn

# Run latency histogram
redis-cli --latency-dist

# Check with memtier_benchmark full histogram
memtier_benchmark --print-full-latency --json-out-file=/tmp/out.json
```

**Fix**:
1. Identify slow command pattern (which command is slow?)
2. Add LIMIT to commands (ZRANGE, LRANGE, SMEMBERS)
3. Replace KEYS with SCAN (if needed)
4. Shard big data structures
5. Use read replicas for slow read commands

### 8.4. AOF fsync Latency Spike

**Nguyên nhân**: `appendfsync everysec` sync định kỳ — latency spike khi sync xảy ra.

**Dấu hiệu**:
- Latency spike every 1 second
- Disk I/O high at sync time
- `INFO persistence | grep aof_last_sync_status`

**Debug**:
```bash
# Check AOF stats
redis-cli INFO persistence | grep -E "aof_|loading:"

# Check disk speed
hdparm -t /dev/sda

# Check if AOF and data on same disk
df -h /var/lib/redis

# Monitor AOF rewrite
redis-cli INFO persistence | grep -E "aof_rewrite|aof_last_write"
```

**Fix**:
1. Use SSD for AOF (not HDD)
2. Separate AOF disk from data disk
3. Consider `appendfsync no` if Redis is cache (data loss acceptable)
4. Use NVMe instead of SATA SSD

---

## 9. Real-world Examples

### Twitter/X — Latency Budgeting for Timeline Reads

Twitter dùng Redis cho timeline cache. Timeline read phải < 50ms end-to-end. Redis command budget = 5ms p99. Họ benchmark mỗi Redis command type với production data size, set `slowlog-log-slower-than` = 2ms. Any command exceeding 2ms = investigated immediately.

**Key learning**: SLO của application phải drive Redis threshold, không phải ngược lại.

### GitHub — Redis Latency Monitoring at Scale

GitHub chạy Redis với `slowlog-log-slower-than 1000` (1ms). Họ có automated alerting khi slowlog length > 100 trong 5 phút. Weekly LATENCY DOCTOR review. Từ incident review: 80% latency issues traceable to commands exceeding 5ms in slowlog.

**Key learning**: Low threshold = catch problems before they compound.

### Shopify — Benchmark-Driven Capacity Planning

Shopify benchmark Redis với real payload size (order data = 2-10KB JSON). Họ phát hiện: at 50K ops/sec with 10KB values, p99 = 20ms. But with 4KB values, p99 = 5ms. This drove their decision to compress Redis values > 5KB.

**Key learning**: Payload size significantly impacts latency. Benchmark with realistic data sizes.

### Uber — Multi-Region Latency Benchmarking

Uber benchmark Redis across regions. Found: Redis in Region A with client in Region B = p99 50ms. Within same region = p99 2ms. This drove their architecture: cache locally in each region, async sync across regions.

**Key learning**: Network topology matters more than Redis performance. Benchmark the actual network path.

---

## 10. Common Pitfalls

1. **Chỉ nhìn average latency**: Average 1ms掩盖了p99=500ms. Luôn report p50/p95/p99.

2. **Benchmark trên localhost rồi deploy WAN**: localhost RTT ~0.05ms vs WAN RTT ~15ms → 300× difference in throughput per connection.

3. **Dùng GET-only benchmark cho mixed workload**: Write-heavy workload (20% SET) has different latency characteristics than 100% GET.

4. **Benchmark với payload quá nhỏ**: Default redis-benchmark = 3 bytes. Real values = 100B-10KB. Payload size directly affects latency.

5. **Không warm up Redis trước benchmark**: Cold Redis with small dataset fits in CPU cache → unrealistically fast.

6. **slowlog-log-slower-than = 10000 (default) quá cao**: Many production systems have p99 = 5ms. Default 10ms misses most latency issues.

7. **Chạy benchmark trên shared infrastructure**: Co-located VMs cause noisy neighbor → variable results. Always use dedicated benchmarking hosts.

8. **Dùng redis-benchmark để capacity plan**: redis-benchmark không có multi-threading thực sự (trước Redis 6+), không mô phỏng realistic workload. Dùng memtier_benchmark.

9. **Không persist slowlog**: SLOWLOG reset on restart → lost evidence. Poll and store externally.

10. **One-shot benchmark**: 10 seconds không phản ánh production. Run at least 5-10 minutes to capture patterns.

---

## 11. Câu hỏi tự kiểm tra

### Câu 1

Bạn set `slowlog-log-slower-than 10000` (10ms). SLOWLOG không có entries nào. Nhưng application logs show p99 = 50ms. Giải thích? Làm sao verify?

<details>
<summary>Đáp án</summary>

```txt
Root cause: 10ms threshold = quá cao. p99 = 50ms means many commands are
between 10-50ms — above threshold, but not in slowlog.

Verification:
1. Lower threshold: slowlog-log-slower-than 1000 (1ms)
2. Run redis-cli SLOWLOG GET → should now have entries
3. Check which commands: redis-cli SLOWLOG GET | jq '.[3][]'
4. Check duration distribution: redis-cli --latency-dist

The commands between 10-50ms are NOT logged, but they ARE causing p99 = 50ms.

Solution: Set threshold = p95 target or lower.
If p99 SLA = 50ms, set slowlog-log-slower-than = 5000 (5ms) to catch
commands that might breach SLA.
```

</details>

### Câu 2

`redis-benchmark -t get -n 100000 -c 50` cho kết quả 80K ops/sec. Nhưng khi deploy lên production, real throughput chỉ 5K ops/sec. Phân tích nguyên nhân.

<details>
<summary>Đáp án</summary>

```txt
Possible causes (check in order):

1. Network topology:
   - Benchmark localhost (RTT ~0.05ms) → 80K ops/sec
   - Production: Redis remote (RTT ~15ms) → 1000ms/15ms/2 = ~33 ops/sec per connection
   - 50 connections × 33 = ~1.6K ops/sec theoretical max

2. Payload size:
   - Benchmark default: 3 bytes → fast network serialization
   - Production: 10KB values → 3000× more data
   - Network bandwidth becomes bottleneck

3. Mixed workload:
   - Benchmark: 100% GET (simple)
   - Production: 20% SET (write = slower due to AOF)

4. Pipeline:
   - Benchmark: no pipeline → 1 command/RTT
   - Production code: pipeline 10 → 10× throughput potential

Verification steps:
1. Run redis-cli --intrinsic-latency (confirm server baseline)
2. Run memtier_benchmark with -d 10240 (realistic payload)
3. Run from same network location as production
4. Check application code: does it pipeline?
```

</details>

### Câu 3

SLOWLOG show 1000 entries với command `ZRANGEBYSCORE leaderboard 0 +inf LIMIT 0 100`. Duration = 5000 microseconds (5ms). Nhưng p99 latency = 200ms. Giải thích?

<details>
<summary>Đáp án</summary>

```txt
SLOWLOG only logs commands EXCEEDING threshold (e.g., > 1ms or > 5ms).

The SLOWLOG entry shows duration = 5000μs = 5ms — this is the threshold value.
This means 5ms is the MINIMUM logged, not the maximum.

p99 = 200ms means some commands took much longer than 5ms.

Possible causes:
1. Some ZRANGEBYSCORE calls had large range (+inf = all elements)
   - Even with LIMIT, scanning the full range takes time
   - Some calls might be without LIMIT → O(N) = seconds

2. Key size variation:
   - Some leaderboard keys have 10K elements (5ms)
   - Some have 1M elements (200ms)

3. Other slow commands not in this SLOWLOG batch:
   - SUNIONSTORE, HGETALL on big keys
   - KEYS * (not this one but similar)

Investigation:
redis-cli SLOWLOG GET | grep -E "duration|command"
# Look for entries with duration >> 5000 (e.g., 100000+ = 100ms+)

Fix:
1. Ensure ALL ZRANGEBYSCORE have LIMIT
2. Check ZRANGEBYSCORE without LIMIT in application code
3. Set slowlog-log-slower-than = 1000 to catch 5ms commands
4. Profile with --latency-history to see time-series
```

</details>

### Câu 4

Bạn muốn benchmark Redis để xác định throughput tối đa cho capacity planning. Soạn benchmark plan: tool nào, flags nào, metrics nào?

<details>
<summary>Đáp án</summary>

```txt
Tool: memtier_benchmark (production-grade, multi-threaded)

Benchmark plan:

Phase 1: Baseline (single connection, no pipeline)
memtier_benchmark -s localhost -c 1 -t 1 -n 100000 -d 256
Goal: measure intrinsic latency per connection

Phase 2: Connection scaling
memtier_benchmark -s localhost -c 10,50,100,200 -t 4 -n 100000 -d 256
Goal: find connection count where throughput plateaus

Phase 3: Pipeline scaling
memtier_benchmark -s localhost -c 50 -t 4 -P 1,5,10,20,50 -n 100000 -d 256
Goal: find optimal pipeline depth

Phase 4: Realistic workload
memtier_benchmark -s localhost -c 50 -t 4 -P 10 \
  --ratio=1:9 -d 1024 -R --key-pattern=R:R -n 100000
Goal: mixed read/write with realistic data size

Phase 5: Latency validation
memtier_benchmark -s localhost -c 50 -t 4 \
  --print-full-latency --json-out-file=/tmp/bench.json

Metrics to collect:
- Throughput: ops/sec (aggregate and per-thread)
- Latency: p50, p95, p99, p99.9, max
- Latency per operation type (SET vs GET)
- Throughput vs connection count (find saturation point)
- Throughput vs pipeline depth

Run each phase 3 times, take median. Discard first run (cold cache).
```

</details>

### Câu 5

Một Redis instance có `used_memory = 50GB`. Bạn enable RDB snapshotting (`save 900 1`). Fork latency spike lên 2s. Giải thích và đề xuất giải pháp.

<details>
<summary>Đáp án</summary>

```txt
Fork latency = time to create child process with COW page tables.
With 50GB memory, fork must:
1. Duplicate page table entries for entire address space
2. Set up COW protection for all pages
3. This is CPU-bound and proportional to memory size

2s fork = expected for 50GB on commodity hardware.

Solutions (in order of impact):

1. Disable Transparent Huge Pages (immediate, free):
   echo never > /sys/kernel/mm/transparent_hugepage/enabled
   echo never > /sys/kernel/mm/transparent_hugepage/defrag
   Reduces fork time by 2-5× on large-memory systems

2. Reduce memory footprint (best long-term):
   - Shard to multiple Redis instances (3× 16GB instead of 1× 50GB)
   - Each shard fork time = ~500ms (manageable)
   - Total throughput preserved, fork latency reduced

3. Change RDB save strategy:
   - save "" (disable automatic RDB)
   - Use BGSAVE manually during low-traffic windows
   - Or: use AOF-only persistence (eliminates fork)

4. Use faster hardware:
   - NVMe SSD for AOF/RDB saves
   - More CPU cores (faster fork)
   - More RAM = faster COW page allocation

5. Consider Redis on Flash (Redis 7.2+):
   - Use Redis on Flash for warm data in memory, cold on NVMe
   - Reduces memory size → reduces fork time
```

</details>

### Câu 6

Bạn phát hiện latency bimodal distribution: p50 = 1ms, p95 = 100ms. Làm sao identify slow command population và fix?

<details>
<summary>Đáp án</summary>

```txt
Step 1: Lower SLOWLOG threshold to catch 5ms+ commands
redis-cli CONFIG SET slowlog-log-slower-than 5000
redis-cli SLOWLOG RESET

Step 2: Generate traffic that reproduces the issue
Run your production workload for a few minutes

Step 3: Analyze SLOWLOG
redis-cli SLOWLOG GET 100 | jq -r '.[] | "\(.[2]) \(.[3][0])"' | \
  awk '{print int($1/1000) "ms " $2}' | sort | uniq -c | sort -rn | head -20

Step 4: Identify pattern
- Are slow commands the same command type?
- Are they on specific keys (hot key)?
- Are they at specific times (peak hour)?

Step 5: Common fixes

If slow commands are ZRANGEBYSCORE/LRANGE without LIMIT:
  - Add LIMIT to all range queries
  - Audit codebase for +inf ranges

If slow commands are SMEMBERS on big sets:
  - Replace with SSCAN (cursor-based iteration)
  - Or: pre-compute subsets

If slow commands are HGETALL on big hashes:
  - Split into smaller hashes (bucket pattern)
  - Or: use pipeline with HSCAN

If slow commands are on hot keys (same key):
  - Shard the hot key
  - Add local cache
  - Use read replica

Step 6: Verify fix
Run benchmark with --latency-dist
Target: p95 < 10ms (improved from 100ms)
```

</details>

### Câu 7

Số liệu benchmark cho thấy throughput tăng tuyến tính với connection count từ 1 đến 200. Có vẻ không có bottleneck. Nhưng latency p99 tăng từ 2ms (50 connections) lên 20ms (200 connections). Giải thích?

<details>
<summary>Đáp án</summary>

```txt
Throughput scales linearly: 1 conn = 10K ops/sec, 200 conn = 2M ops/sec
Latency p99 increases: 2ms → 20ms

This is the expected behavior of Redis under high concurrency:

Redis single-threaded processes commands sequentially.
With 50 connections:
  - Each connection sends commands in sequence
  - 50 concurrent commands → average wait = ~1 command time
  - p99 = 50 × command_time = ~2ms

With 200 connections:
  - 200 concurrent commands
  - Average wait = 200 × command_time
  - p99 = 200 × command_time = ~20ms

The key insight:
  - Throughput ∝ connection count (as long as Redis has headroom)
  - Latency ∝ connection count (queueing delay)
  - Beyond a point, adding connections only increases latency

Optimal point:
  - Find connection count where throughput stops increasing
  - That connection count = optimal pool size
  - Beyond that: latency increases, throughput flat

In practice:
  - For 1ms commands: optimal = 50-100 connections
  - For 10ms commands: optimal = 10-20 connections
  - Rule: connections = target_concurrency × command_latency_ms / 1000

For the given scenario: 200 connections gives 10× throughput vs 50,
but p99 is 10× higher. Trade-off depends on SLA:
  - If SLA = 5ms: use 50 connections
  - If SLA = 50ms: 200 connections gives 10× more throughput
```

</details>
