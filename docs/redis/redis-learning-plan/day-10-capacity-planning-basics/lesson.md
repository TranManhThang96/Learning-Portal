# Day 10: Capacity Planning Basics

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Estimate memory consumption cho Redis dataset production: per-record overhead, Redis metadata, encoding factor, fragmentation — tính ra con số GB chính xác chứ không phải "feel estimate".
- Calculate throughput capacity (ops/sec) dựa trên payload size, command complexity, pipeline factor, network bandwidth ceiling — biết con số tối đa thực tế chứ không phải benchmark number.
- Design capacity plan bao gồm headroom (30-40%), failover scenarios, replica overhead, disk sizing, connection memory, replication bandwidth — tất cả trong một worksheet.
- Evaluate trade-offs giữa scale-up vs scale-out, 1 large node vs multiple shards, 1 replica vs 2 replicas — đưa ra quyết định dựa trên số liệu cụ thể.

---

## 2. Vì sao cần học chủ đề này

### Incident thực tế: Failover không tính headroom — cascading failure

Một team đã size Redis master cho **100K ops/sec**. Master có 2 replicas. Mọi thứ hoạt động tốt cho đến khi master crash lúc 9h sáng. Sentinel promote replica 1 thành master. **Nhưng promote không tính rằng replica 1 đang đọc 50% traffic qua read replica route.** Khi replica 1 promote:
- Nó phải gánh **100K ops/sec write** (trước đây là master xử lý)
- **Cộng thêm 50K ops/sec read** (vì read replica route vẫn chỉ vào đó)
- Total: **150K ops/sec** — 50% trên capacity

Replica 1 bắt đầu timeout, latency tăng, Sentinel detect lại là master down, promote replica 2. Replication lag 30s trong khi replica lag catch-up. Trong 30 giây đó, backend database overload. Hệ thống mất 45 phút để phục hồi.

**Root cause**: Capacity plan không tính **failover headroom** — không ai hỏi "replica promoted phải gánh bao nhiêu ops/sec?".

### Incident thực tế: Quên connection memory — OOM ngay khi restart

Một hệ thống Redis cache trên AWS ElastiCache `cache.r6g.2xlarge` (64GB). Khi đo `INFO memory`, used_memory = 58GB. Instance có 64GB. Memory headroom = 6GB. Mọi thứ ổn.

Rồi traffic tăng đột biến. Backend service restart tất cả pods. Mỗi pod tạo connection pool mới. **50,000 connections đổ vào Redis cùng lúc.**

Connection memory calculation:
- `maxmemory` không phải hard cap cho toàn bộ RSS của process; client buffers và overhead ngoài dataset vẫn cần headroom
- 50,000 connections × ~17KB/connection (Redis 7) = **850 MB connection overhead**
- 58GB + 850MB = 58.85GB → **vượt 64GB → OOM kill**

Redis bị kill. Pods restart. Connection storm lại. Loop. Mất 20 phút.

**Root cause**: Capacity plan không include **connection memory overhead**. `INFO clients` và `CLIENT LIST` không tự động alert connection memory.

### Incident thực tế: Cluster sizing — usable memory khác advertised memory

Team thiết kế Redis Cluster: 6 nodes × 32GB = 192GB total cluster memory. Dataset: 100M cached objects × 1KB = 100GB. Họ nghĩ 192GB cho 100GB dataset → dư 92GB headroom.

Nhưng họ quên:
- Replication factor = 1 (1 replica per master) → mỗi master shard chỉ có 1 replica
- Usable memory = 50% cluster (replica nodes không serve data, chỉ replicate) → **96GB usable**
- Replication backlog: 1GB × 6 shards = 6GB
- Dataset actually 120GB sau vài tháng → **OOM trên 3 shards**

**Root cause**: Cluster capacity planning phải account **replication factor**, không phải sum total cluster memory.

---

**Bottom line**: Capacity planning là bài toán số học. Nếu bạn không tính từng byte, từng ops, từng connection — bạn sẽ gặp incident khi hệ thống scale.

---

## 3. Kiến thức nền cần có

- **Day 5**: Encoding internals, per-record memory overhead, `MEMORY USAGE`, `OBJECT ENCODING`
- **Day 6**: RDB/AOF file size, COW overhead trong BGSAVE
- **Day 8**: `maxmemory`, eviction policies, dataset vs `maxmemory` ratio
- **Day 9**: Memory fragmentation, jemalloc size classes
- **Day 13**: Latency, throughput benchmark (sẽ học sâu hơn)
- **Day 19**: Replication internals, replica lag, replication backlog

---

## 4. Lý thuyết chi tiết

### 4.1. Memory Estimation

#### Per-record Memory Formula

```
total_memory =
    N × (key_len + sds_header + value_bytes + value_encoding_overhead)
    + N × redis_object_overhead
    + N × hashtable_overhead_if_applicable
    + instance_overhead
    + fragmentation
```

**Chi tiết từng component**:

| Component | Size | Notes |
|-----------|------|-------|
| `key_name` | 3–63 bytes (SDS) | +1 byte sdshdr8 (≤256B key) |
| `redisObject` | 16 bytes | 4+4+24 bits + 8B ptr |
| `robj.lru` | 3 bytes (in robj) | part of 16B struct |
| `hashtable dictEntry` | ~24 bytes/key | only if encoding = hashtable |
| `quicklist listpack node` | ~56 bytes/node | list overhead if List |
| `skiplist node` | ~32 + SDS + levels | only if ZSet > 128 entries |
| `intset header` | 4 bytes | fixed per intset |
| `jemalloc overhead` | variable | round up to size class (8,16,32,48,64...) |

**Quick estimation formula (String key-value, raw encoding)**:

```
bytes_per_record =
    key_len + 3                          // key SDS header
    + 16                                 // robj
    + value_len + 3                      // value SDS header
    + 5                                  // jemalloc overhead estimate
    ≈ key_len + value_len + 27 bytes
```

**Real example**:

```
Key: "product:SKU12345"  → 18 bytes
Value: '{"name":"iPhone","price":999}'  → 35 bytes
Per-record: 18 + 35 + 27 = 80 bytes
Dataset: 10M records
Total: 10M × 80 = 800MB (logical)
RSS (with fragmentation): ~900MB–1.1GB
```

#### Sampling-based Memory Estimation

`MEMORY USAGE key SAMPLES 100` cho statistical sampling:

```bash
# SCAN to get a random sample
redis-cli --scan --pattern 'cache:*' | head -1000 | while read key; do
  redis-cli MEMORY USAGE "$key" SAMPLES 100
done
```

**Statistical confidence formula**:

```
estimate = (sample_avg_bytes / sample_size) × total_keys
error_margin = 1.96 × (sample_stddev / sqrt(sample_size)) × total_keys
confidence_interval = estimate ± error_margin
```

**Minimum sample size** cho 95% confidence, ±10% error:
- Population: 1M keys → minimum sample: 96 keys
- Population: 100M keys → minimum sample: 96 keys (same for given error tolerance)
- Nếu `sample_stddev` cao (highly variable key sizes) → tăng sample size lên 500-1000

#### Expiry Overhead

TTL không tăng per-key memory đáng kể. Tuy nhiên:
- `EXPIREAT` lưu Unix timestamp trong metadata → negligible
- Active expiration scan: Redis scan `active-expire-effort` keys/tick (default 8) → CPU overhead không phải memory
- Expiry overhead trong `maxmemory` calculations: negligible (<1%)

#### Dataset Growth Rate

```
memory_growth_rate = (memory_today - memory_30d_ago) / 30 days

projected_memory_6mo = memory_today + (memory_growth_rate × 180 days)
projected_memory_12mo = memory_today + (memory_growth_rate × 365 days)
```

**Critical**: Instance size phải cover projected_memory_12mo + headroom. Nếu growth rate = 2GB/tháng, dataset 30GB hôm nay → 54GB trong 12 tháng → cần instance ≥ 64GB với headroom.

---

### 4.2. Throughput Estimation

#### Ops/sec Baseline (local benchmark)

```
Benchmark local (loopback, no network):
  String GET/SET:    200K–500K ops/sec per core
  Pipeline batch:   1M–5M ops/sec per core

Benchmark over network (1Gbps NIC, 0.1ms RTT):
  String GET/SET:    100K–300K ops/sec per connection
  p99 latency:      0.3–0.8ms per command
```

#### Payload Size Impact on Throughput

| Payload (bytes) | GET ops/sec (local) | GET ops/sec (network) | Bandwidth |
|-----------------|--------------------|-----------------------|-----------|
| 100 B | 450K | 200K | 20 MB/s |
| 1 KB | 400K | 150K | 150 MB/s |
| 10 KB | 300K | 80K | 800 MB/s |
| 100 KB | 80K | 20K | 2 GB/s (1Gbps NIC saturated) |
| 1 MB | 8K | 2K | 2 GB/s |

**Key insight**: Payload size ảnh hưởng throughput theo 2 cách:
1. **Serialization/deserialization CPU** tăng với payload
2. **Network bandwidth ceiling** — với payload lớn, 1Gbps NIC bị saturated ở ~10K ops/sec

#### Command Complexity Factor

| Command Type | Example | Big O | ops/sec factor vs O(1) |
|---|---|---|---|
| O(1) | GET, SET, HGET, SADD | 1 | 1.0× |
| O(1) + COW | SET with BGSAVE | 1 + COW | 0.8–0.95× (BGSAVE running) |
| O(log N) | ZADD, ZRANGEBYSCORE | log N | 0.7–0.9× |
| O(N) | HGETALL, LRANGE, SMEMBERS | N | 0.1–0.5× (N = result count) |
| O(N log N) | SORT | N log N | 0.05–0.2× |
| O(N^2) | ZUNIONSTORE large sets | N² | 0.01× (avoid!) |

**Real example**:
- 80K GET/sec + 20K HGETALL(50 fields)/sec
- Factor: 80K × 1.0 + 20K × 0.3 = 86K effective ops/sec
- Single-threaded limit ≈ 150K ops/sec → utilization = 57%

#### Pipeline Factor

```
ops/sec_with_pipeline = ops/sec_single × pipeline_size × network_efficiency_factor

network_efficiency_factor:
  - 1K RTT latency, 100 commands/pipeline → ~0.85
  - 1ms RTT, 500 commands/pipeline → ~0.95
  - 5ms RTT, 100 commands/pipeline → ~0.70
```

**Example**:
- Single GET: 150μs latency → 6,667 ops/sec per connection
- Pipeline 100 commands: 10ms RTT → 10,000 ops/sec per connection (50% improvement)
- 10 connections: 100,000 ops/sec total

#### Network Bandwidth Ceiling

```
bandwidth_ceiling_ops/sec = NIC_speed / avg_payload_size

Example:
  NIC: 1 Gbps = 125 MB/s
  Payload: 1 KB avg
  Ceiling: 125 MB/s / 1 KB = 125,000 ops/sec (single connection, bidirectional)

  NIC: 10 Gbps = 1.25 GB/s
  Payload: 1 KB avg
  Ceiling: 1.25 GB/s / 1 KB = 1,250,000 ops/sec
```

**Multi-connection scaling**: N connections không linear với bandwidth vì mỗi connection overhead (~17KB buffer/side). VD: 100 connections × 100KB payload = 10MB/RTT → 1Gbps NIC chỉ handle ~125 ops/sec × 100 = 12,500 effective ops/sec.

---

### 4.3. Connection Count Estimation

#### Connection Memory Cost (Redis 7)

```
Per connection memory:
  - Input buffer:  max 10MB (client-querybuf-limit, default 1MB)
  - Output buffer: max 10MB
  - Client struct: ~17 KB (name, addr, LRU, flags, db, ip, port, subscriptions)
  - RESP3 + pub/sub: additional ~2-5 KB per subscriber

Average per connection: ~17–50 KB depending on configuration
Conservative estimate: 17 KB/connection
```

**Real calculation**:
```
50,000 connections × 17 KB = 850 MB
100,000 connections × 17 KB = 1.7 GB
```

**Important**: `maxmemory` không phải hard cap cho toàn bộ RSS của process. Client buffers, replication/AOF buffers, allocator fragmentation và OS overhead có thể làm process memory cao hơn dataset memory dùng cho eviction. OOM từ connection storm thường là "process OOM" chứ không phải eviction theo `maxmemory`.

#### Connection Pool Sizing

```
total_connections = threads_per_instance × connections_per_thread × instances_per_service

Example (Go service, 8 pods × 10 goroutines each):
  goroutines/pod: 10
  connections/goroutine: 1 (shared connection pool)
  pools/pod: 10
  total: 8 × 10 = 80 connections per service pod
  × 20 service pods = 1,600 connections total
```

**Rule**: Mỗi goroutine/thread nên có dedicated connection hoặc share qua channel-based pool. Không share connection giữa goroutines đồng thời.

#### maxclients Configuration

```bash
# Check current maxclients
redis-cli CONFIG GET maxclients
# Default: 10000 (may vary by OS)

# Linux: max open files / 3 (stdin/stdout/stderr = 3)
ulimit -n 65536
# → maxclients = 21845

# redis.conf
maxclients 20000
```

**Connection exhaustion symptoms**:
- `redis-cli INFO clients` → `rejected_connections` counter tăng
- Client errors: "Connection refused" hoặc timeout khi connect
- `CLIENT LIST` → rất nhiều connections ở `age=0` (just connected, immediately rejected)

---

### 4.4. Headroom — The 30-40% Rule

#### Why Headroom is Non-negotiable

**BGSAVE COW overhead**:
```
Dataset: 30GB
BGSAVE duration: 60s
Write rate during BGSAVE: 200K ops/sec
Avg write size: 100 bytes/op
Pages written: 200K × 100 × 60s = 1.2GB
→ COW pages needed: 1.2GB / 4KB page = 300K pages
→ Peak memory: 30GB + 1.2GB = 31.2GB
→ Headroom needed: 1.2GB = 4% of 30GB (but...)
```

**Burst traffic**:
```
Normal: 80K ops/sec
Peak:   200K ops/sec (viral content, flash sale)
Burst factor: 2.5×
→ Plan for 200K ops/sec sustained for 30 minutes
→ Buffer connections, CPU, memory for 2.5× baseline
```

**Replication lag during catch-up**:
```
Replica behind 30s → replicate backlog = 30s × ops/sec
At 100K ops/sec → 3M ops in backlog
Backlog memory: ~300MB–1GB (depends on avg command size)
→ Headroom needed on replica before it can serve traffic
```

#### Headroom Budget Breakdown

```
Memory headroom:
  30% for dataset growth (monthly growth rate × 3)
  + 20% for COW during BGSAVE (worst-case write rate)
  + 10% for fragmentation (jemalloc + internal)
  + connection memory (17KB × expected_connections)
  = ~50-60% total headroom over dataset size

Ops/sec headroom:
  30% for traffic spikes (p95 → p99, viral events)
  + 20% for command mix shift (more HGETALL, less GET)
  + failover capacity (replica → master promotion)
  = ~40-50% headroom over baseline ops/sec

CPU headroom:
  Redis single-threaded → 1 core at 100% = hard ceiling
  Target: 70% CPU utilization max
  Headroom: 30% for BGSAVE fork impact, AOF fsync, slow commands
```

**Rule of thumb**:

| Resource | Safe threshold | Headroom |
|----------|---------------|----------|
| Memory | ≤ 70% of instance | 30% minimum |
| Ops/sec | ≤ 60% of benchmark | 40% minimum |
| CPU (single core) | ≤ 70% | 30% |
| Connections | ≤ 70% of maxclients | 30% |
| Disk (AOF/RDB) | ≤ 60% of disk | 40% |

---

### 4.5. Failover Capacity Planning

#### Single Replica Topology

```
Normal state:
  Master:  100K ops/sec (write) + 0 read
  Replica: 50K ops/sec read

After master crash, replica promoted:
  New master: 100K ops/sec (write) + 50K ops/sec (read) = 150K ops/sec
  → 50% OVER CAPACITY
  → Latency spike, timeouts, cascading failure
```

**Failover capacity formula**:
```
capacity_needed_after_failover =
    master_ops/sec
    + replica_read_ops/sec
    + (master_ops/sec × failover_read_penalty)
    # penalty = fraction of read traffic redirected to new master during failover

With 80/20 read/write split:
  Master: 80K reads + 20K writes = 100K total
  After failover: replica must handle 80K + 20K = 100K (if reads stay on replica)
  But if reads redirect to new master: 80K + 20K + 20K = 120K = 20% OVER CAPACITY
```

#### Two Replica Topology

```
Normal: 1 master + 2 replicas
  Master:  100K ops/sec write
  Replica1: 50K ops/sec read
  Replica2: 30K ops/sec read (different service)

After master crash, replica1 promoted:
  Replica1: 100K writes + 50K reads = 150K
  Replica2: 30K reads (still serving)
  Cluster total: 180K ops/sec (replicas can scale reads)

Recovery time:
  - Replica2 needs to replicate from new master
  - Replication lag: 30K ops/sec backlog × lag_seconds
  - During lag: replica2 serves stale reads (acceptable for read replicas)
```

**Trade-off: 1 replica vs 2 replicas**

| Config | Write capacity after failover | Read capacity after failover | Cost |
|--------|------------------------------|------------------------------|------|
| 1 replica | 100% (overloaded) | 0 (both read routes fail) | $X |
| 2 replicas | 100% | 30-50% (replica2 still up) | $2X |
| 3 replicas | 100% | 50-70% (2 replicas still up) | $3X |

---

### 4.6. Replica Memory Overhead

#### Replication Backlog

```
backlog_size (bytes) = replication_backlog × 1024 × 1024

Default: 1MB
→ At 100K ops/sec, avg command 100 bytes: 1MB / 100B = 10,000 commands backlog
→ Lag tolerance: 10,000 / 100,000 = 0.1 seconds!

Must size backlog = expected_max_lag_seconds × ops/sec × avg_command_bytes

Example:
  Max acceptable lag: 30 seconds
  Ops/sec: 100K
  Avg command: 200 bytes
  Required backlog: 30 × 100,000 × 200 = 600 MB
```

#### COW on Replica (BGSAVE)

Replica chạy BGSAVE bằng `child_copies_data = yes` (Redis 7+):
```
Replica memory during BGSAVE:
  Base: 30GB (dataset)
  + COW pages from replica's writes during BGSAVE
  + Parent child link: COW for master traffic replicated through replica

Writes on replica during BGSAVE (slave-save = yes by default):
  If replica has any writes (via MASTERCLIENT ...):
  → COW pages = write_rate × avg_write × BGSAVE_duration
  → Same COW formula as master
```

#### Output Buffer on Replica

```
Output buffer per replica = command_response_size × buffer_depth

Default: 1MB client-querybuf-limit for input
Output buffer: 10MB (max for master → replica stream)

At 100K ops/sec replication stream, avg response 50 bytes:
  Throughput: 5 MB/s replication bandwidth
  Buffer capacity: 10MB → 2 seconds lag tolerance
```

---

### 4.7. Persistence Disk Sizing

#### RDB File Size

```
RDB_size ≈ dataset_logical_size × compression_factor × fragmentation_padding

compression_factor: 0.5–0.7 (RDB is binary, already compressed)
fragmentation_padding: 1.1–1.3 (allocator overhead in dump)

Example:
  Dataset: 50GB logical
  RDB size: 50GB × 0.6 compression × 1.2 padding = ~36GB
```

**Important**: RDB size ≈ dataset compressed, không phải dataset × 1. Redis dùng binary format với its own serialization, không phải text.

#### AOF File Size

```
AOF_size ≈ dataset_size × AOF_overhead_multiplier × (1 - rewrite_progress)

AOF_overhead_multiplier: 3–10× (RESP verbosity: SET "key" "value" = ~20 bytes vs 2 bytes actual)
rewrite_progress: fraction of AOF already rewritten (0 = never, 1 = just rewrote)

Example (no rewrite yet):
  Dataset: 50GB
  AOF: 50GB × 5 (avg) = 250GB

Example (after AOF rewrite):
  Dataset: 50GB
  AOF after rewrite: 50GB × 0.7 (base) + 1GB (incremental) = ~36GB
```

**MP-AOF directory** (Redis 7+):
```
appendonlydir/
├── appendonly.1.0000000000000001.aof   (base: ~50GB)
├── appendonly.1.0000000000001234.aof   (incremental: ~500MB)
└── appendonly.manifest
Total directory: ~51-60GB (vs single AOF 250GB+)
```

#### Disk Sizing Formula

```
required_disk_gb =
    RDB_size × num_backups_to_keep
    + AOF_current_size × 1.5  (rewrite headroom)
    + MP-AOF incremental files × 2
    + 20% filesystem overhead
    + operating_system_swap if applicable

Example:
  RDB: 36GB × 2 backups = 72GB
  AOF: 250GB × 1.5 = 375GB
  OS overhead: 20% × (72 + 375) = 89GB
  Total: ~536GB
```

---

### 4.8. Network Bandwidth

#### Bandwidth Breakdown

```
total_bandwidth =
    client_traffic
    + replication_traffic
    + monitor_traffic
    + pubsub_traffic

client_traffic = ops/sec × (request_payload + response_payload)
replication_traffic = ops/sec × write_fraction × replication_factor × avg_command_size
```

**Real example**:
```
Workload: 100K ops/sec, 80/20 read/write
  Read:  80K GET × (20B request + 1KB response) = 80K × 1.02KB = 81.6 MB/s
  Write: 20K SET × (50B request + 30B response) = 20K × 80B = 1.6 MB/s
  Total client: ~83 MB/s = 664 Mbps

Replication (1 replica):
  Write traffic replicated: 20K SET × 50B = 1 MB/s
  Total: 665 Mbps → 1Gbps NIC: 67% utilized, acceptable

Replication (3 replicas):
  1 MB/s × 3 = 3 MB/s
  Total: 667 Mbps → still OK

At 10Gbps NIC:
  667 Mbps = 6.7% utilized → comfortable
```

#### 1Gbps vs 10Gbps NIC Decision

| Metric | 1 Gbps NIC | 10 Gbps NIC |
|--------|-----------|-------------|
| Effective throughput (bidirectional) | ~800 Mbps usable | ~8 Gbps usable |
| Max ops/sec (1KB payload) | ~100K ops/sec | ~1M ops/sec |
| Max ops/sec (100B payload) | ~800K ops/sec | ~8M ops/sec |
| Cost delta | baseline | +$50-200/month (cloud) |
| Break-even | N/A | ~50K ops/sec sustained |

**Decision**: Nếu ops/sec > 50K sustained và payload > 500B → 10Gbps NIC worth it. Nếu burst only → có thể dùng 1Gbps với burst credit.

---

### 4.9. Cluster Capacity Calculation

```
total_cluster_capacity =
    num_shards × capacity_per_shard

capacity_per_shard (single master):
  Memory: (instance_size / 2)  ← 50% for replica
  Ops/sec: benchmark_ops/sec × 0.6 (headroom)

Example: 6-node cluster, 32GB instances, 150K ops/sec benchmark
  Shards: 3 masters + 3 replicas
  Memory/shard: 32GB / 2 = 16GB usable
  Ops/sec/shard: 150K × 0.6 = 90K ops/sec
  Total cluster: 3 × 16GB = 48GB memory, 270K ops/sec
```

**Hash slot distribution**:
```
16384 slots / num_masters = slots per master
Each master handles ~5469 slots (with 3 masters)
→ Even distribution assumes uniform key access pattern
→ Hot slots: measure with redis-cli --bigkeys or CLUSTER KEYSLOT
```

**Key insight**: Cluster capacity = nửa tổng cluster memory (vì replica không serve data). Không nhầm lẫn "6 nodes × 32GB = 192GB" khi thực tế chỉ có 96GB usable.

---

### 4.10. T-Shirt Sizing Framework

#### Small Tier

| Metric | Value |
|--------|-------|
| Ops/sec | < 10K |
| Memory | < 10 GB |
| Dataset | < 5M keys |
| Use case | Single service, dev/staging, small microservice |
| Topology | Standalone + 1 replica |
| Instance | 2 vCPU, 8GB RAM |
| Cost/month (cloud) | $30–80 |

#### Medium Tier

| Metric | Value |
|--------|-------|
| Ops/sec | 10K – 100K |
| Memory | 10 – 100 GB |
| Dataset | 5M – 50M keys |
| Use case | Multiple services, primary cache, session store |
| Topology | Sentinel (3 nodes) + 1-2 replicas |
| Instance | 4-8 vCPU, 32-64GB RAM |
| Cost/month (cloud) | $150–600 |

#### Large Tier

| Metric | Value |
|--------|-------|
| Ops/sec | 100K – 1M+ |
| Memory | 100GB – 1TB+ |
| Dataset | 50M – 500M+ keys |
| Use case | Multi-tenant, high-throughput API cache, real-time analytics |
| Topology | Redis Cluster (6+ nodes) + Sentinel |
| Instance | 16-64 vCPU, 128-512GB RAM |
| Cost/month (cloud) | $1,000–10,000+ |

---

## 5. Trade-off Analysis

### Trade-off 1: Scale Up vs Scale Out

| Criteria | Scale Up (vertical) | Scale Out (horizontal/Cluster) |
|----------|---------------------|-------------------------------|
| Ops/sec limit | 150K–300K per instance | Unlimited (shards scale linearly) |
| Memory limit | 1 instance maxmemory | Unlimited (add shards) |
| Setup complexity | Low | High (resharding, hash tags) |
| Operations | Simple | Need cluster-aware tooling |
| Blast radius | Full instance down | Single shard down |
| Cost efficiency | Good < 50K ops/sec | Good > 100K ops/sec |
| Multi-key operations | All supported | Limited to same slot |
| Latency | Lower (no redirection) | MOVED/ASK overhead (0.5-2ms) |

**Khi nào scale up**: Ops/sec < 100K, memory < 100GB, multi-key operations needed, operational simplicity priority.

**Khi nào scale out**: Ops/sec > 100K, memory > 100GB, high availability critical, hot key risk, cost optimization at scale.

### Trade-off 2: One Large Node vs Multiple Shards

| Criteria | One Large Node (64GB+) | Multiple Shards (8GB × 8) |
|----------|------------------------|---------------------------|
| Operational simplicity | High | Medium |
| Blast radius | Full dataset loss | 12.5% dataset loss |
| Memory efficiency | No overhead | 1 extra node for replica |
| Key distribution | Automatic | Need hash tag design |
| Hot key isolation | Impossible | Can put hot keys on separate shard |
| Scaling granularity | All or nothing | Shard-by-shard |
| Cost | 1 × 64GB = $400/mo | 2 × 8GB masters + 2 replicas = $200/mo |

**Khi nào one large node**: Hot key không thể split, multi-key operations critical, operational team small.

**Khi nào multiple shards**: Hot key exists, cost optimization, blast radius concern, scale predictability.

### Trade-off 3: Memory Headroom 30% vs 50%

| Criteria | 30% Headroom | 50% Headroom |
|----------|-------------|-------------|
| Cost | Lower (smaller instance) | Higher (bigger instance) |
| Safety margin | Tight for BGSAVE COW | Comfortable for growth + spikes |
| Risk of OOM | Higher (especially COW) | Lower |
| Growth runway | 2–3 months | 6–12 months |
| When to use | Stable, predictable growth | High growth rate, viral traffic risk |

**Recommendation**: 30% headroom cho memory có growth rate < 2GB/tháng. 50% headroom cho growth rate > 5GB/tháng hoặc COW-heavy workloads.

### Trade-off 4: Replica Count 1 vs 2 vs 3

| Criteria | 1 Replica | 2 Replicas | 3 Replicas |
|----------|-----------|-----------|-----------|
| HA after master crash | Failover but overloaded | Can serve partial read | Full HA with read capacity |
| Read capacity after failover | 0% | 30–50% | 50–70% |
| Cost | $X | $2X | $3X |
| Replication bandwidth | 1× | 2× | 3× |
| Quorum safety | Low (1 of 2) | Medium (2 of 3) | High (3 of 4 with Sentinel) |
| Best for | Non-critical read replicas | Standard production | Financial/health-critical |

### Trade-off 5: Synchronous Benchmark vs Production Traffic Estimation

| Criteria | Benchmark (redis-benchmark) | Production Estimation |
|----------|----------------------------|------------------------|
| Payload | Fixed, uniform | Variable, realistic |
| Command mix | Single command | Real mix (GET, HGET, ZRANGE...) |
| Network | Local loopback or clean network | Production network (jitter, concurrent apps) |
| Number | Peak ops/sec achievable | Sustainable ops/sec with headroom |
| Multi-tenancy | No | Yes (shared host/NIC) |
| Result | Ceiling | Target |

**Rule**: Luôn dùng **benchmark ceiling × 0.5–0.6 = production target**. VD: benchmark = 200K ops/sec → plan for 100-120K ops/sec.

---

## 6. Best Solution & Best Practices

### T-Shirt Sizing Quick Reference

```
Small (< 10K ops/sec, < 10GB):
  → Standalone + 1 replica
  → 8GB instance, maxmemory 7GB
  → 30% headroom

Medium (10-100K ops/sec, 10-100GB):
  → Sentinel (3 nodes) + 1 replica
  → 32-64GB instance, maxmemory 50-60% of RAM
  → 40% headroom

Large (> 100K ops/sec, 100GB+):
  → Redis Cluster (6+ nodes) + Sentinel
  → 128-256GB instances
  → 40-50% headroom
```

### Headroom Checklist

```
Before going live, verify:
  [ ] Memory: current_used + 30% headroom ≤ maxmemory
  [ ] Memory: projected_6mo + 50% headroom ≤ maxmemory
  [ ] Ops/sec: baseline + 40% headroom ≤ benchmark × 0.6
  [ ] Ops/sec: failover scenario ≤ benchmark × 0.6
  [ ] Connections: expected + 30% headroom ≤ maxclients
  [ ] Connection memory: connections × 17KB ≤ available_system_memory
  [ ] Disk: RDB + AOF × 1.5 ≤ disk_size × 0.6
  [ ] Network: peak_bandwidth ≤ NIC_speed × 0.7
  [ ] Replication backlog: backlog_size ≥ max_lag_seconds × ops/sec × avg_cmd_bytes
```

### Anti-patterns

| Anti-pattern | Vấn đề | Fix |
|---|---|---|
| Size for today, no growth | OOM trong 3 tháng | Always project 12-month growth |
| Plan for benchmark number | Production không bao giờ đạt benchmark | Use 50-60% of benchmark |
| Ignore COW overhead | OOM khi BGSAVE chạy | Add 20-30% memory headroom |
| Ignore connection memory | Process OOM from connections | Count 17KB × max_connections |
| Single replica without failover plan | Replica promoted = overloaded | Size replica cho full master load |
| Plan for usable memory, not total | Cluster sizing error | Usable = total / replication_factor |
| Ignore replication backlog | Lag spike = data loss | Size backlog = lag_seconds × ops/sec |

---

## 7. Performance Considerations

### Ops/sec by Payload Size (realistic production numbers)

| Payload | Local (loopback) | 1 Gbps NIC | 10 Gbps NIC |
|---------|-----------------|-----------|------------|
| 100 B | 400K–500K | 150K–200K | 800K–1M |
| 1 KB | 350K–450K | 100K–150K | 500K–700K |
| 10 KB | 250K–350K | 50K–80K | 200K–300K |
| 100 KB | 50K–80K | 8K–15K | 40K–70K |
| 1 MB | 5K–8K | 1K–2K | 5K–10K |

**p95/p99 latency by ops/sec load**:

| Ops/sec Load | p50 GET | p95 GET | p99 GET |
|-------------|---------|---------|---------|
| 30% of capacity | 0.1ms | 0.2ms | 0.3ms |
| 60% of capacity | 0.2ms | 0.4ms | 0.7ms |
| 80% of capacity | 0.3ms | 0.8ms | 1.5ms |
| 95% of capacity | 0.5ms | 2ms | 10ms+ |

---

## 8. Production Failure Modes

### Failure Mode 1: Memory Underestimation — OOM at Peak

**Trigger**: Estimate dùng `MEMORY USAGE × key_count` nhưng không account jemalloc rounding, fragmentation, connection memory, COW overhead.

**Impact**: OOM → Redis killed → cold start → cache stampede → cascade failure.

**Dấu hiệu**: `redis-cli INFO memory` → `used_memory` gần `maxmemory`. `dmesg | grep -i oom` → Redis killed.

**Phòng tránh**: Size instance = estimated × 1.5 (headroom). Monitor `used_memory / maxmemory` ratio. Alert khi > 70%.

### Failure Mode 2: Connection Exhaustion — "Too many open connections"

**Trigger**: Connection pool không bounded, goroutine leak, connection không close, `maxclients` reached.

**Impact**: New connections rejected → application errors → users see errors.

**Dấu hiệu**: `INFO clients` → rejected_connections counter tăng. `CLIENT LIST | wc -l` → near maxclients.

**Phòng tránh**: Set `timeout` (client idle timeout, default 0 = never). Set `maxclients` based on `ulimit -n / 3`. Monitor `rejected_connections`.

### Failure Mode 3: Failover Overload — Replica Can't Handle Full Load

**Trigger**: Master crash, replica promoted, replica không sized cho full master load.

**Impact**: Latency spike → timeouts → Sentinel promote another → cascade.

**Dấu hiệu**: `INFO stats` → instantaneous_ops_per_sec spike. Latency monitor → p99 > 100ms.

**Phòng tránh**: Size replica cho full master load + 20% headroom. Test failover scenario trong chaos lab (Day 21).

### Failure Mode 4: COW Spike — OOM During BGSAVE

**Trigger**: High write rate during BGSAVE → COW pages allocate → peak memory > instance.

**Impact**: OOM → Redis killed → data loss + downtime.

**Dấu hiệu**: `INFO persistence` → `latest_fork_usec` cao. `INFO memory` → `mem_fragmentation_ratio` > 1.5.

**Phòng tránh**: Size instance = dataset × 1.3 (COW buffer). `vm.overcommit_memory = 1`. Monitor fork duration.

### Failure Mode 5: Disk Full — AOF/RDB Can't Write

**Trigger**: AOF file grow > disk size (VD: AOF = 3× dataset, no rewrite, disk 2× dataset).

**Impact**: Redis can't write persistence → disk full → Redis stop accepting writes or crash.

**Dấu hiệu**: `redis-cli INFO persistence` → `aof_last_write_status: err`. Log: "Cannot open or create append-only file".

**Phòng tránh**: Size disk = AOF × 2 + RDB × 2. Monitor disk usage. Set `stop-writes-on-bgsave-error` (default yes).

---

## 9. Real-world Examples

### Twitter — Redis Cache Sizing for Timelines

Twitter dùng Redis cho timeline cache với dataset ~2TB trên nhiều nodes. Sizing:
- Per-node: 96GB RAM
- Usable per node: ~72GB (25% headroom + replica overhead)
- Total nodes: ~30 (22TB physical, ~14TB usable + replication)
- Ops/sec per node: ~200K (local) → ~120K production (with headroom)
- Cluster total: ~2.4M ops/sec

**Lesson**: Twitter sizing cho hot path timeline cache cực kỳ conservative với headroom. Họ monitor keyspace growth weekly và scale nodes 2-3 tháng trước khi hit capacity.

### Slack — Redis for Real-time Presence

Slack dùng Redis cho user presence (online/offline). Dataset: ~10M users × ~20 bytes = ~200MB. Nhưng họ dùng **multiple Redis instances** cho isolation và blast radius:
- Presence: 1 master + 1 replica (small, 4GB instance)
- Session tokens: 1 master + 2 replicas (medium, 16GB instance)
- Rate limiting: dedicated instance per tenant (micro-sharding)

**Lesson**: Không phải mọi thứ cần cluster. Micro-sharding (dedicated small instances) đơn giản hơn và có better blast radius isolation.

### Shopify — Redis Cluster for Inventory

Shopify dùng Redis Cluster cho inventory reservation. Sizing:
- Peak: 500K ops/sec (flash sale)
- Dataset: 50GB
- Shards: 8 masters × 32GB = 256GB total (128GB usable)
- Each shard: 16GB dataset + 16GB replica
- Headroom: 30% per shard

**Lesson**: Shopify dùng T-shirt sizing "large" và micro-shards (8GB per shard) để có fine-grained scaling. Khi một flash sale cần scale, họ thêm shards thay vì resize nodes.

### Discord — Redis Pub/Sub Sizing

Discord dùng Redis Pub/Sub cho real-time message fanout. Capacity planning khác cache:
- **Pub/Sub không persistent**: memory = active channels × subscribers × overhead
- **Fanout = ops/sec × fanout_degree**: 10K messages/sec × 100 avg subscribers = 1M publish operations/sec
- **Connection cost**: 5M concurrent users × 1 connection each = 85GB connection memory!

**Lesson**: Pub/Sub sizing rất khác cache sizing — phải count subscribers và fanout degree, không phải dataset size.

---

## 10. Common Pitfalls

1. **Size cho dataset, quên headroom**: 30GB dataset → allocate 32GB instance → 2GB headroom → COW = 2GB → OOM.

2. **Dùng benchmark number làm capacity**: Benchmark 200K ops/sec → plan 200K ops/sec → production 150K ops/sec → overload.

3. **Quên connection memory**: 50K connections × 17KB = 850MB connection overhead ngoài dataset budget, vẫn cần RAM headroom dù `maxmemory` chưa chạm.

4. **Quên replication backlog**: backlog = 1MB default → lag > 0.1s → replication broken khi lag > backlog.

5. **Cluster sizing dùng total memory**: 6 nodes × 32GB = 192GB cluster, nhưng usable = 96GB (vì replica).

6. **Không tính AOF rewrite disk space**: AOF size = 3-10× dataset. Disk phải có 2× AOF size free cho rewrite.

7. **Size cho ops/sec, quên payload size**: 1K payload × 100K ops/sec = 100MB/s bandwidth → 1Gbps NIC saturated.

8. **Failover không có headroom**: Replica size = master load → promote → overloaded → cascade.

9. **Không project growth**: Size cho hôm nay → 3 tháng sau OOM → emergency resize.

10. **Quên pub/sub connection overhead**: Pub/Sub subscriber = extra connection với dedicated buffer. 1M subscribers = significant overhead.

---

## 11. Câu hỏi tự kiểm tra

**Câu 1**: Bạn có 50M cached objects, avg 512 bytes/object. Estimate memory cần thiết. Nếu dùng `maxmemory-policy allkeys-lru`, bạn cần bao nhiêu headroom?

**Câu 2**: Redis benchmark show 200K ops/sec với 100B payload trên loopback. Production estimate ops/sec là bao nhiêu? Nếu payload tăng lên 1KB, estimate thay đổi thế nào?

**Câu 3**: Bạn thiết kế hệ thống 100K ops/sec, 80/20 read/write. Master crash → replica promoted. Replica cần handle bao nhiêu ops/sec? Nếu dùng 1 replica, failover plan cần gì?

**Câu 4**: Cluster 6 nodes × 32GB. Replication factor = 1. Dataset hiện tại 80GB. Usable memory là bao nhiêu? Nếu thêm 2 replicas (replication factor = 2), usable memory là bao nhiêu?

**Câu 5**: Bạn có 80,000 connections đồng thời. Connection memory overhead là bao nhiêu? Nếu instance = 64GB và dataset = 58GB, hệ thống có OOM không? Tại sao?

**Câu 6**: Redis Cluster 4 shards × 32GB instances. Dataset = 80GB. AOF bật (no rewrite trong 6 tháng). Disk cần bao nhiêu?

**Câu 7**: Explain sự khác biệt giữa "scale up" và "scale out" trong Redis. Khi nào nên chọn Cluster thay vì Sentinel + bigger instance?

---

### Đáp án

**Câu 1**:
```
Logical dataset: 50M × 512B = 25.6 GB
Per-key overhead: ~27 bytes × 50M = 1.35 GB
Total logical: ~27 GB
Jemalloc fragmentation: × 1.1 = 29.7 GB
COW headroom (BGSAVE): +20% = 35.6 GB
Growth headroom (3 months × 2GB/mo): +6 GB
Total needed: ~42 GB
Instance recommendation: 64 GB (42/64 = 66% utilization)
```

**Câu 2**:
```
Benchmark ceiling: 200K ops/sec
Production target: 200K × 0.6 = 120K ops/sec
→ This is the sustainable ops/sec target (not burst)

With 100B payload:
  Bandwidth: 120K × 100B = 12 MB/s bidirectional
  → 1Gbps NIC: 6% utilized, OK

With 1KB payload:
  Bandwidth: 120K × 1KB = 120 MB/s bidirectional
  → 1Gbps NIC: 96% utilized, TIGHT
  → Need 10Gbps NIC or reduce ops/sec target to 80K

Production ops/sec estimate (1KB payload): ~80-100K ops/sec
```

**Câu 3**:
```
Normal: Master 20K writes + 80K reads = 100K total
  Reads served by: 1 replica (80K) + master (0)
After failover (replica promoted, reads redirect to new master):
  New master: 20K writes + 80K reads = 100K ops/sec
  → Replica was sized for 20K writes + 0 reads = 20K capacity
  → 100K / 20K = 5× OVER CAPACITY

Failover plan:
  1. Size replica for 100K ops/sec (not 20K)
  2. Keep read traffic on replica route (don't redirect to new master immediately)
  3. OR use 2 replicas: replica1 = 100K write capacity, replica2 = 80K read capacity
  4. Monitor failover scenarios in chaos lab (Day 21)
```

**Câu 4**:
```
Replication factor 1 (1 master + 1 replica per shard):
  3 master shards: 3 × 32GB = 96GB total physical per side
  Usable memory: 3 × 32GB = 96GB (replicas don't serve data)
  Note: total cluster = 6 × 32GB = 192GB physical
  Usable fraction: 96/192 = 50%

Replication factor 2 (1 master + 2 replicas per shard):
  2 master shards: 2 × 32GB = 64GB
  Usable memory: 64GB
  Total physical: 6 × 32GB = 192GB
  Usable fraction: 64/192 = 33%

Dataset 80GB / 96GB usable = 83% utilization — tight!
Recommendation: 4 master shards × 32GB = 128GB usable
  → 80GB / 128GB = 62.5% utilization (good headroom)
```

**Câu 5**:
```
Connection memory: 80,000 × 17KB = 1,360 MB = 1.36 GB

Dataset: 58GB
Connection overhead: 1.36GB
Total: 59.36GB / 64GB = 92.7% utilized

BUT: maxmemory is not a hard cap for process RSS!
Redis used_memory (controlled by maxmemory): 58GB
System-level memory: 58GB + 1.36GB = 59.36GB < 64GB

So: No process OOM from connections in this case.
However: At 90,000 connections → 1.53GB overhead → 59.53GB → still OK
At 100,000 connections → 1.7GB overhead → 59.7GB → still OK
At 150,000 connections → 2.55GB → 60.55GB → 94.6% — TIGHT

Critical insight: maxmemory = 58GB, connections at 150K → process RSS can approach 60.55GB
→ If instance has OS overhead (500MB) + Redis binary (50MB) = 61GB → near limit
→ If swap enabled: may trigger OOM despite maxmemory not reached
```

**Câu 6**:
```
Dataset: 80GB
RDB size: 80GB × 0.6 × 1.2 = ~58GB

AOF (no rewrite in 6 months):
  Write volume: 6 months × 30 days × 24h × 3600s × ops/sec × avg_cmd_bytes
  If 50K ops/sec × 100B avg: 6mo = 6 × 30 × 24 × 3600 × 50,000 × 100B
    = 6 × 30 × 24 × 3600 × 5 MB = 78 TB!!!

Even with AOF rewrite monthly:
  AOF after rewrite: 80GB × 0.7 = 56GB
  + incremental 1 month: 50K × 100B × 30 days × 24h × 3600s = 130GB
  → AOF current size: ~186GB

Disk needed:
  RDB (2 backups): 58GB × 2 = 116GB
  AOF (with headroom): 186GB × 1.5 = 279GB
  OS overhead: 20% × 395GB = 79GB
  Total: ~474GB → recommend 500GB NVMe SSD

Key insight: AOF without regular rewrite = disk space bomb!
Recommendation: AOF rewrite every 1-2 hours for write-heavy workloads.
```

**Câu 7**:
- **Scale up**: Tăng instance size (VD: 8GB → 64GB). Đơn giản, không thay đổi application. Giới hạn: ~100-150K ops/sec, ~100GB memory per instance. Multi-key operations OK.
- **Scale out (Cluster)**: Thêm nodes, chia dataset qua shards. Phức tạp hơn (hash tags, resharding). Không giới hạn. Multi-key ops bị giới hạn same-slot. Blast radius nhỏ hơn.

**Chọn Cluster khi**: ops/sec > 100K, memory > 100GB, hot key risk, cost optimization at scale, HA critical.
**Chọn Sentinel + bigger instance khi**: ops/sec < 100K, memory < 100GB, multi-key operations needed, operational team size small.
