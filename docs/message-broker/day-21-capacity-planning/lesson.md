# Day 21: Capacity Planning & Sizing — Partition, Retention, Network, Disk, Replication

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** cách tính số partitions phù hợp — công thức, constraints, và trade-off khi quá ít/quá nhiều partitions
2. **Nắm vững** retention sizing — tính toán disk requirement dựa trên throughput, retention period, replication factor
3. **Thực hành** network bandwidth planning — replication traffic, producer/consumer traffic, cross-DC considerations
4. **Biết** disk throughput estimation — sequential vs random I/O, SSD vs HDD selection criteria
5. **Áp dụng** rule of thumb cho different workloads — event streaming, log aggregation, CDC, real-time analytics

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-13 (Kafka fundamentals, producer/consumer internals, replication, ISR)
- Đã hoàn thành Day 20 (Performance tuning — hiểu bottleneck model)
- Hiểu partition, replication factor, ISR, consumer groups
- Hiểu cơ bản về storage, networking concepts

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Partition count calculation — throughput-based, consumer-based, ordering requirements
- Retention sizing — disk formula, compacted topics, tiered storage overview
- Network bandwidth — replication overhead, producer/consumer math
- Hands-on: capacity planning worksheet cho real scenarios

### 🟡 Should Learn (nếu còn thời gian)
- Disk throughput analysis — IOPS calculation, SSD vs HDD
- Broker count estimation — CPU, memory, disk, network balanced
- Growth planning — scaling strategy, partition expansion caveats
- Cost estimation — cloud vs on-premise, per-broker cost model

### 🟢 Optional Deep Dive
- Multi-datacenter capacity planning (MirrorMaker 2 overhead)
- Tiered storage economics (hot/warm/cold)
- Kafka on Kubernetes resource requests/limits
- Capacity planning automation tools

---

## 4. Lý thuyết (Theory)

### 4.1 Partition Count — Bao nhiêu Partitions là đủ?

#### WHY — Tại sao số partition quan trọng?

```
PARTITION = ĐƠN VỊ CƠ BẢN của:
  - Parallelism: mỗi partition = 1 consumer thread max
  - Ordering: messages cùng key → cùng partition → ordered
  - Storage: mỗi partition = 1 thư mục trên disk
  - Replication: mỗi partition replicate independently
  - Recovery: mỗi partition = 1 đơn vị recovery khi broker crash

  QUÁ ÍT partitions:
  ┌───────────────────────────────────────────────────┐
  │ Topic "orders" — 2 partitions                      │
  │                                                   │
  │ Consumer Group (8 consumers):                     │
  │ Consumer 1 ← Partition 0  (overloaded!)           │
  │ Consumer 2 ← Partition 1  (overloaded!)           │
  │ Consumer 3 ← IDLE                                 │
  │ Consumer 4 ← IDLE                                 │
  │ Consumer 5 ← IDLE (wasted!)                       │
  │ Consumer 6 ← IDLE                                 │
  │ Consumer 7 ← IDLE                                 │
  │ Consumer 8 ← IDLE                                 │
  │                                                   │
  │ → 6 consumers idle → money wasted!                │
  │ → Cannot scale beyond 2x throughput               │
  └───────────────────────────────────────────────────┘

  QUÁ NHIỀU partitions:
  ┌───────────────────────────────────────────────────┐
  │ Topic "orders" — 10,000 partitions                 │
  │                                                   │
  │ Problems:                                         │
  │ ✗ Metadata overhead: broker track 10K partitions  │
  │ ✗ File descriptors: 10K × 2 files = 20K fds      │
  │ ✗ Recovery time: leader election cho 10K partitions│
  │   → có thể mất PHÚT thay vì giây                 │
  │ ✗ Memory: producer batch buffer × 10K partitions  │
  │ ✗ Rebalance time: consumer group assign 10K       │
  │   partitions → slow rebalance                    │
  │ ✗ End-to-end latency tăng (more batches, smaller) │
  └───────────────────────────────────────────────────┘
```

#### HOW — Công thức tính Partition Count

```
APPROACH 1: THROUGHPUT-BASED (most common)

  Partitions = max(T/Pp, T/Cp)

  Trong đó:
  - T  = target throughput (MB/s hoặc records/s)
  - Pp = throughput per partition for PRODUCER
  - Cp = throughput per partition for CONSUMER

  Ví dụ:
  - Target: 100 MB/s throughput
  - Producer: 1 partition sustains ~10 MB/s (with compression)
  - Consumer: 1 partition sustains ~20 MB/s (faster, zero-copy)
  
  Partitions = max(100/10, 100/20) = max(10, 5) = 10
  
  Nhưng plan for growth → 10 × 2 = 20 partitions
  
  ⚠️ Đây là MINIMUM. Thêm buffer cho growth.


APPROACH 2: CONSUMER-BASED

  Partitions ≥ max consumers cần trong tương lai

  Ví dụ: 
  - Hiện tại 4 consumer instances
  - Dự kiến scale lên 16 instances trong 2 năm
  - → Ít nhất 16 partitions

  ⚠️ Không thể GIẢM partitions! Chỉ có thể tăng.
  → Plan cho 2-3 năm growth


APPROACH 3: ORDERING-BASED

  Nếu cần ordering → partitions = số "ordering groups"
  
  Ví dụ: Order processing, key = customerId
  - 10,000 active customers
  - Cần ordering per customer → không cần 10K partitions
  - Kafka hash(key) % num_partitions → distribute customers
  - 50-100 partitions đủ cho ordering + parallelism


COMBINED FORMULA:

  P = max(
    ceil(target_throughput / per_partition_throughput),
    max_consumer_instances,
    min_partitions_for_ordering
  )
  
  Then: round UP to next "nice" number (6, 8, 12, 16, 24, 32, ...)
  → Chia đều cho brokers (P % num_brokers = 0 → ideal)


PER-PARTITION THROUGHPUT ESTIMATES:

  ┌──────────────────────────────────────────────────────┐
  │ Workload                │ Producer/partition │ Consumer/partition │
  ├─────────────────────────┼────────────────────┼───────────────────┤
  │ Small msgs (< 1KB)      │ 5-10 MB/s          │ 15-25 MB/s        │
  │ Medium msgs (1-10KB)    │ 10-30 MB/s         │ 25-50 MB/s        │
  │ Large msgs (10-100KB)   │ 20-50 MB/s         │ 40-80 MB/s        │
  │ With compression (lz4)  │ 1.5-2x above       │ same (decompress) │
  └──────────────────────────────────────────────────────┘

  Factors affecting per-partition throughput:
  - Message size (larger = higher MB/s, lower records/s)
  - Compression (higher throughput MB/s, more CPU)
  - acks setting (acks=all slower than acks=1)
  - Replication factor (more replicas = more I/O)
  - Disk type (SSD >> HDD for writes)
```

#### Rules of Thumb cho Partition Count

```
RULES OF THUMB:

  ┌──────────────────────────────────────────────────────────┐
  │ Workload            │ Partitions │ Reasoning              │
  ├──────────────────────┼────────────┼────────────────────────┤
  │ Low throughput       │ 6-12       │ Enough parallelism,    │
  │ (< 10 MB/s)         │            │ room to grow           │
  │                      │            │                        │
  │ Medium throughput    │ 12-32      │ Balance parallelism    │
  │ (10-100 MB/s)       │            │ vs overhead            │
  │                      │            │                        │
  │ High throughput      │ 32-128     │ Near-linear scaling    │
  │ (100+ MB/s)         │            │ with consumers         │
  │                      │            │                        │
  │ Compacted topic      │ 6-24       │ Compaction overhead    │
  │ (lookup tables)     │            │ increases with P       │
  │                      │            │                        │
  │ Log aggregation      │ 24-96      │ Many producers,        │
  │                      │            │ high throughput        │
  └──────────────────────┴────────────┴────────────────────────┘

  CLUSTER-WIDE LIMITS:
  - Tổng partitions per broker: < 4,000 (recommended)
  - Tổng partitions per cluster: < 200,000 (KRaft)
  - Tổng partitions per cluster: < 100,000 (ZooKeeper)
  
  Ví dụ: 6 brokers × 4,000 = max 24,000 partitions per cluster

  ⚠️ KHÔNG THỂ GIẢM partition count sau khi tạo!
  → Tăng partitions → messages với CÙNG key có thể đi partition KHÁC
  → Key ordering bị phá vỡ cho existing keys!
  → Plan ahead, nhưng đừng over-provision quá mức
```

### 4.2 Retention Sizing — Bao nhiêu Disk?

#### WHY — Disk là chi phí lớn nhất

```
KAFKA DISK USAGE = f(throughput, retention, replication)

  FORMULA:

  Disk per broker = (daily_data × retention_days × replication_factor) / num_brokers
  
  Trong đó:
  daily_data = avg_msg_size × msgs_per_day × (1 / compression_ratio)
  
  
  VÍ DỤ THỰC TẾ:

  Scenario: E-commerce event platform
  - Messages: 10,000 msg/s average, 50,000 msg/s peak
  - Message size: 500 bytes average
  - Compression: lz4 (ratio ~2x)
  - Retention: 7 days  
  - Replication factor: 3
  - Brokers: 6

  Calculation:
  ┌──────────────────────────────────────────────────────┐
  │ Daily data (uncompressed):                            │
  │   10,000 msg/s × 500 bytes × 86,400 s/day           │
  │   = 432 GB/day (uncompressed)                        │
  │                                                      │
  │ Daily data (with lz4 ~2x):                           │
  │   432 GB / 2 = 216 GB/day (compressed)               │
  │                                                      │
  │ Total data (7 days retention):                       │
  │   216 GB × 7 = 1,512 GB = ~1.5 TB                   │
  │                                                      │
  │ With replication (RF=3):                              │
  │   1,512 GB × 3 = 4,536 GB = ~4.5 TB total           │
  │                                                      │
  │ Per broker (6 brokers):                               │
  │   4,536 GB / 6 = 756 GB per broker                   │
  │                                                      │
  │ Add 30% buffer for overhead (indexes, logs, etc.):   │
  │   756 GB × 1.3 = ~983 GB ≈ 1 TB per broker          │
  │                                                      │
  │ RESULT: 6 brokers × 1 TB disk each                   │
  └──────────────────────────────────────────────────────┘
```

#### Compacted Topics — Khác biệt sizing

```
COMPACTED TOPICS (cleanup.policy=compact):

  Retention KHÔNG dựa trên time/size → dựa trên KEYS
  
  Disk usage = num_unique_keys × avg_value_size
  
  Ví dụ: User profiles (compacted)
  - 1 triệu users
  - Avg profile size: 2KB
  - Disk = 1M × 2KB = 2GB (bất kể retention period!)
  
  Nhưng TRƯỚC compaction, data tích tụ:
  - Compaction chạy periodically (không real-time)
  - Có thể có 3-5x data trước khi compact
  - Budget: unique_keys × value_size × 3-5x
  
  Tham số ảnh hưởng:
  - min.cleanable.dirty.ratio = 0.5 (default)
    → Compact khi ≥50% data là dirty (chưa compact)
    → Giảm → compact thường xuyên hơn → ít disk, nhiều CPU
  - log.cleaner.min.compaction.lag.ms = 0
    → Min time trước khi message eligible cho compaction
    → Set > 0 để giữ recent duplicates (debug, audit)


TIERED STORAGE (Kafka 3.6+ — KIP-405):

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  Hot data (recent):  Broker local disk (SSD)            │
  │  ├─ Last 24h of data                                    │
  │  ├─ Fast access for real-time consumers                 │
  │  └─ local.retention.ms = 86400000 (24h)                 │
  │                                                         │
  │  Cold data (older):  Object storage (S3, GCS, HDFS)     │
  │  ├─ Historical data (7 days, 30 days, forever)          │
  │  ├─ 10-50x cheaper per GB                               │
  │  └─ Higher latency for catch-up consumers               │
  │                                                         │
  │  Impact on capacity planning:                           │
  │  - Broker disk: chỉ cần cho hot data (24-48h)          │
  │  - Object storage: cheap, virtually unlimited           │
  │  - Cost reduction: 50-80% cho long-retention topics     │
  └─────────────────────────────────────────────────────────┘
```

### 4.3 Network Bandwidth — Replication + Client Traffic

#### WHY — Network thường là bottleneck đầu tiên

```
NETWORK TRAFFIC COMPONENTS:

  ┌─────────────────────────────────────────────────────────┐
  │                     Kafka Broker                         │
  │                                                         │
  │  INBOUND:                                               │
  │  ├─ Producer writes:        W MB/s                      │
  │  ├─ Follower fetch:         W × (RF-1) MB/s            │
  │  │  (other brokers replicating FROM this broker)        │
  │  └─ Total IN = W × RF                                  │
  │                                                         │
  │  OUTBOUND:                                              │
  │  ├─ Consumer reads:         R MB/s (per consumer group) │
  │  ├─ Leader → follower:      W × (RF-1) MB/s            │
  │  │  (this broker replicating TO other brokers)          │
  │  └─ Total OUT = R × num_consumer_groups + W × (RF-1)   │
  │                                                         │
  └─────────────────────────────────────────────────────────┘


FORMULA:

  Per broker network (assuming evenly distributed). Tính INBOUND và OUTBOUND riêng vì NIC là full-duplex; cộng hai chiều chỉ là cách conservative để nhìn tổng traffic, không phải capacity một chiều của NIC:

  Inbound per broker  = (producer_throughput / num_brokers) × RF
  Outbound per broker = (producer_throughput / num_brokers) × (RF - 1)
                      + Σ (consumer_group_throughput / num_brokers)


VÍ DỤ:

  - Producer throughput: 100 MB/s total
  - Replication factor: 3
  - Consumer groups: 3 (mỗi group đọc toàn bộ data)
  - Brokers: 6

  Per broker INBOUND:
    (100 / 6) × 3 = 50 MB/s
    ├── 16.7 MB/s from producers
    └── 33.3 MB/s from follower replication (other brokers fetching)

  Per broker OUTBOUND:
    (100 / 6) × (3 - 1) + 3 × (100 / 6)
    = 33.3 + 50 = 83.3 MB/s
    ├── 33.3 MB/s replication to followers
    └── 50 MB/s to 3 consumer groups (16.7 × 3)

  Directional bandwidth:
    INBOUND  = 50 MB/s   ≈ 0.40 Gbps
    OUTBOUND = 83.3 MB/s ≈ 0.67 Gbps
    Aggregate = 133.3 MB/s ≈ 1.1 Gbps (conservative reporting only)
  
  → NIC 1 Gbps có thể chạy sát ngưỡng OUTBOUND, nhưng headroom < 70% rất mỏng
  → Rule production: max(IN, OUT) / 0.70 + protocol overhead
  → Với workload này nên chọn 10 Gbps NIC thay vì rely vào 1 Gbps


NETWORK BANDWIDTH RECOMMENDATIONS:

  ┌────────────────────────────────────────────────────────┐
  │ Total cluster throughput │ NIC per broker              │
  ├──────────────────────────┼─────────────────────────────┤
  │ < 50 MB/s                │ 1 Gbps (sufficient)         │
  │ 50-200 MB/s              │ 10 Gbps (recommended)       │
  │ 200-500 MB/s             │ 10 Gbps (bonded or 25G)     │
  │ > 500 MB/s               │ 25 Gbps+                    │
  └────────────────────────────────────────────────────────┘
  
  ⚠️ Compression giảm network significantly!
  LZ4 ~2x → effective network throughput × 2
```

### 4.4 Disk Throughput — SSD vs HDD

```
DISK SELECTION:

  ┌───────────────────────────────────────────────────────────┐
  │                   HDD vs SSD cho Kafka                     │
  │                                                           │
  │  Kafka writes = SEQUENTIAL → HDD có thể chấp nhận        │
  │  Kafka reads  = SEQUENTIAL (tailing) → page cache serves  │
  │                                                           │
  │  NHƯNG có scenarios cần random I/O:                       │
  │  1. Consumer catch-up (đọc historical data not in cache)  │
  │  2. Compaction (read old segments, write new)             │
  │  3. State store recovery (Kafka Streams RocksDB)          │
  │  4. Multiple consumers đọc different offsets              │
  │                                                           │
  │  | Tiêu chí         | HDD            | SSD (SATA)      | SSD (NVMe)       |
  │  |-----------------|----------------|-----------------|-----------------|
  │  | Sequential write | 100-200 MB/s   | 400-500 MB/s    | 1-3 GB/s        |
  │  | Sequential read  | 100-200 MB/s   | 400-500 MB/s    | 2-6 GB/s        |
  │  | Random IOPS      | 100-200        | 50K-100K        | 200K-1M         |
  │  | Cost per TB      | $25-50         | $100-200        | $150-400        |
  │  | Latency (avg)    | ~5-10ms        | ~0.1-0.5ms      | ~0.01-0.1ms     |
  │  | Best for         | Log storage    | Mixed workload  | Low latency     |
  │  |                  | Archival       | Most production | High throughput  |
  └───────────────────────────────────────────────────────────┘

RECOMMENDATION:
  - HDD: OK cho log aggregation, archival, cost-sensitive nhưng only tailing consumers
  - SSD (SATA): RECOMMENDED cho hầu hết production → balanced cost/performance
  - SSD (NVMe): cho latency-critical, high-throughput → financial, real-time analytics

DISK THROUGHPUT FORMULA:

  Required disk write throughput per broker:
  = (producer_throughput / num_brokers) × replication_factor
  
  Ví dụ: 100 MB/s total, 6 brokers, RF=3
  = (100 / 6) × 3 = 50 MB/s per broker
  
  → HDD (200 MB/s sequential): 25% utilization ✓
  → SSD (500 MB/s): 10% utilization ✓ ✓
  
  Nhưng thêm compaction, consumer reads, replication:
  → Total I/O có thể 2-3x write throughput
  → 50 MB/s × 3 = 150 MB/s → HDD 75% (risky!)
  → SSD preferred
```

### 4.5 Broker Count — Bao nhiêu Brokers?

```
BROKER COUNT FORMULA:

  Brokers = max(
    ceil(total_disk / disk_per_broker),
    ceil(total_network / network_per_broker),
    ceil(total_partitions / partitions_per_broker),
    min_for_replication_factor               # RF=3 → ≥ 3 brokers
  )


VÍ DỤ TỔNG HỢP:

  Requirements:
  - Throughput: 200 MB/s sustained (400 MB/s peak)
  - Message size: 1KB average
  - Retention: 14 days
  - Replication: 3
  - Consumer groups: 5
  - Latency: p99 < 50ms

  Step 1: Disk sizing
  Daily data = 200 MB/s × 86,400s = 17.28 TB/day (uncompressed)
  With lz4 (~2x): 8.64 TB/day
  14 days × 3 RF = 8.64 × 14 × 3 = 362.9 TB
  Per broker (8 brokers): 45.4 TB per broker
  → Mỗi broker cần ~50 TB disk (with buffer)

  Step 2: Network sizing
  Producer inbound per broker: (200/8) × 3 = 75 MB/s
  Consumer outbound per broker: 5 × (200/8) = 125 MB/s
  Replication outbound: (200/8) × 2 = 50 MB/s
  Total: 75 + 125 + 50 = 250 MB/s = 2 Gbps → 10G NIC ✓

  Step 3: Partition count
  Partitions = 200 MB/s / 10 MB/s per partition = 20
  With growth buffer: 40-60 partitions → 60 / 8 brokers = ~8 per broker ✓

  Step 4: Memory
  Per broker: 6GB heap + page cache
  Active segments: ~50 partitions × 1GB = 50GB hot data
  Page cache 50GB → total RAM 64GB per broker

  RESULT:
  ┌────────────────────────────────────────────┐
  │ Cluster sizing:                             │
  │ - 8 brokers                                │
  │ - 64 GB RAM each                           │
  │ - 8 cores each                             │
  │ - 50 TB disk each (SSD recommended)        │
  │ - 10 Gbps NIC                              │
  │ - 60 partitions (with RF=3 = 180 replicas) │
  └────────────────────────────────────────────┘
```

### 4.6 Workload-Specific Rules of Thumb

```
WORKLOAD SIZING CHEAT SHEET:

  ┌──────────────────────────────────────────────────────────────┐
  │ Workload           │ Partition│ Retention │ RF │ Compression │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ Log aggregation    │ 24-96    │ 3-7 days  │ 2  │ zstd        │
  │ (high volume,      │          │           │    │ (best ratio)│
  │  loss-tolerant)    │          │           │    │             │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ Event streaming    │ 12-48    │ 7-30 days │ 3  │ lz4         │
  │ (orders, actions)  │          │           │    │             │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ CDC (Debezium)     │ match    │ 7 days +  │ 3  │ zstd        │
  │                    │ source   │ compact   │    │             │
  │                    │ tables   │           │    │             │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ Real-time analytics│ 12-32    │ 1-3 days  │ 2  │ lz4         │
  │ (metrics, dashbd)  │          │           │    │             │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ Event sourcing     │ 6-24     │ forever   │ 3  │ zstd        │
  │ (command log)      │          │ (compact) │    │             │
  ├────────────────────┼──────────┼───────────┼────┼─────────────┤
  │ IoT telemetry      │ 48-256   │ 1-7 days  │ 2  │ snappy/lz4  │
  │ (many devices)     │          │           │    │             │
  └──────────────────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### Partition Count Trade-offs

| Fewer Partitions | More Partitions |
|-----------------|-----------------|
| Ít metadata overhead | Nhiều metadata, tốn memory |
| Recovery nhanh (ít leader elections) | Recovery chậm |
| Ít file descriptors | Nhiều file descriptors |
| Limited parallelism | High parallelism |
| Rebalance nhanh | Rebalance chậm |
| Latency thấp (larger batches) | Latency có thể tăng (smaller batches) |

### Retention vs Disk Cost

| Retention | Disk Cost | Use Case | Alternative |
|-----------|-----------|----------|------------|
| 24h | Thấp | Metrics, logs | - |
| 7 days | Trung bình | Events, transactions | - |
| 30 days | Cao | Compliance, replay | Tiered storage |
| Forever | Rất cao | Event sourcing | Compact + tiered |

### Replication Factor

| RF=1 | RF=2 | RF=3 |
|------|------|------|
| Không fault-tolerant | Tolerate 1 failure | Tolerate 1 failure (quorum) |
| Disk × 1 | Disk × 2 | Disk × 3 |
| Network × 1 | Network × 2 | Network × 3 |
| Dev/test only | Ít dùng (odd better) | Production standard |
| - | - | min.insync.replicas=2 possible |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. PARTITION COUNT: start moderate, plan for 2-3 năm growth
   → 12-32 partitions cho hầu hết topics
   → Divisible by broker count (12 partitions / 3 brokers = 4 each)
   → KHÔNG THỂ GIẢM → conservative nhưng đủ

2. RETENTION: dùng CÙNG LÚC time-based VÀ size-based
   log.retention.hours = 168        # 7 days max
   log.retention.bytes = 107374182400  # 100GB max per partition
   → Whichever triggers FIRST → delete
   → Protect against spike (1 giờ traffic gấp 10x → disk full)

3. REPLICATION: RF=3 cho production, min.insync.replicas=2
   → Tolerate 1 broker failure cho writes
   → Tolerate 2 broker failures cho reads
   → Duy nhất exception: RF=2 cho non-critical logs (cost saving)

4. DISK: separate disks cho data vs OS/logs
   → log.dirs=/data1,/data2  (JBOD — multiple disks)
   → Kafka tự balance partitions across disks
   → Nếu 1 disk fail → chỉ mất partitions trên disk đó
   → RAID-10 KHÔNG cần (replication thay thế)

5. HEADROOM: plan 30-50% buffer cho:
   → Traffic spikes (holiday, events)
   → Broker failure (remaining brokers handle extra load)
   → Compaction overhead
   → Consumer catch-up reads

6. MONITORING capaciy metrics:
   → Disk: > 70% used → add disk hoặc giảm retention
   → Network: > 70% utilized → add brokers hoặc compression
   → CPU: > 80% sustained → add brokers
   → Partitions per broker: > 4000 → add brokers
```

### Common Pitfalls

```
❌ PITFALL 1: Tạo quá nhiều partitions "để safe"
   Sai:  1000 partitions cho topic 100 msg/s
   Đúng: 12 partitions (đủ cho 10x growth)
   Tại sao: metadata overhead, slow recovery, wasted resources

❌ PITFALL 2: Quên tính replication trong disk sizing
   Sai:  "100GB/day × 7 days = 700GB per cluster"
   Đúng: 700GB × RF=3 = 2.1TB per cluster, 700GB per broker (3 brokers)
   Tại sao: mỗi partition replicated RF lần trên DIFFERENT brokers

❌ PITFALL 3: Không plan cho broker failure
   3 brokers, RF=3 → 1 broker chết → 2 brokers còn lại chịu 1.5x load
   Nếu 2 brokers đã ở 80% capacity → 1 chết → 2 còn lại ở 120% → cascade fail!
   → Giữ utilization < 60-70% per broker

❌ PITFALL 4: Tăng partitions trên existing topic
   Sai:  kafka-topics --alter --partitions 24 (từ 12)
   Vấn đề: messages với cùng key hash đến PARTITION KHÁC
   → Ordering bị phá vỡ cho existing keys!
   → Consumers relying on key ordering → data inconsistency
   Đúng: Tạo topic mới → migrate data → cut over

❌ PITFALL 5: Retention quá dài không cần thiết
   "Set retention=30 days để safe" cho metrics topic
   → 500 MB/s × 30 days × RF=3 = 3.8 PB!
   → 99% data never read after 24h
   → Fix: retention=3 days + archive to object storage nếu cần

❌ PITFALL 6: Network sizing quên consumer groups
   "100 MB/s write, 3 replicas → 300 MB/s network"
   Nhưng có 5 consumer groups → thêm 500 MB/s read!
   Total = 300 + 500 = 800 MB/s → gần max 1Gbps NIC
```

---

## 7. Performance Considerations

### Capacity Planning Metrics to Monitor

```
CONTINUOUS CAPACITY MONITORING:

  Disk:
  - kafka.log:type=Log,name=Size     → bytes per topic/partition
  - disk_used_percent                  → per broker disk usage
  - Alert: > 70% → plan expansion     → > 85% → urgent

  Network:
  - kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec
  - kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec
  - Alert: > 70% NIC capacity

  Partitions:
  - kafka.server:type=ReplicaManager,name=PartitionCount
  - kafka.controller:type=KafkaController,name=ActiveControllerCount
  - Alert: > 4000 partitions per broker

  Replication:
  - kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions
  - kafka.server:type=ReplicaManager,name=IsrShrinksPerSec
  - Alert: UnderReplicated > 0 for > 5 minutes

  Growth tracking:
  - Weekly: plot disk usage trend → project full date
  - Monthly: review throughput growth → adjust capacity plan
  - Quarterly: re-evaluate partition count adequacy
```

---

## 8. Hands-on Lab

### 8.1 Capacity Planning Worksheet

```bash
#!/bin/bash
# capacity-calculator.sh — Kafka Capacity Planning Calculator

echo "=== Kafka Capacity Planning Calculator ==="
echo ""

# Input parameters
read -p "Average message size (bytes) [500]: " MSG_SIZE
MSG_SIZE=${MSG_SIZE:-500}

read -p "Messages per second (avg) [10000]: " MSG_PER_SEC
MSG_PER_SEC=${MSG_PER_SEC:-10000}

read -p "Peak multiplier (e.g., 3 for 3x) [3]: " PEAK_MULT
PEAK_MULT=${PEAK_MULT:-3}

read -p "Retention days [7]: " RETENTION_DAYS
RETENTION_DAYS=${RETENTION_DAYS:-7}

read -p "Replication factor [3]: " RF
RF=${RF:-3}

read -p "Number of consumer groups [3]: " NUM_CG
NUM_CG=${NUM_CG:-3}

read -p "Peak consumer groups that read full stream [3]: " PEAK_NUM_CG
PEAK_NUM_CG=${PEAK_NUM_CG:-$NUM_CG}

read -p "Compression ratio (2 for lz4) [2]: " COMP_RATIO
COMP_RATIO=${COMP_RATIO:-2}

read -p "Number of brokers [3]: " NUM_BROKERS
NUM_BROKERS=${NUM_BROKERS:-3}

read -p "Producer MB/s per partition from benchmark [10]: " PRODUCER_MB_PER_PARTITION
PRODUCER_MB_PER_PARTITION=${PRODUCER_MB_PER_PARTITION:-10}

read -p "Consumer MB/s per partition from benchmark [20]: " CONSUMER_MB_PER_PARTITION
CONSUMER_MB_PER_PARTITION=${CONSUMER_MB_PER_PARTITION:-20}

read -p "Max consumer instances in one consumer group [6]: " MAX_CONSUMERS
MAX_CONSUMERS=${MAX_CONSUMERS:-6}

read -p "Minimum ordering groups / key buckets [6]: " ORDERING_GROUPS
ORDERING_GROUPS=${ORDERING_GROUPS:-6}

echo ""
echo "=== RESULTS ==="
echo ""

# Calculations
AVG_THROUGHPUT_BYTES=$(echo "$MSG_PER_SEC * $MSG_SIZE" | bc)
AVG_THROUGHPUT_MB=$(echo "scale=2; $AVG_THROUGHPUT_BYTES / 1048576" | bc)
PEAK_THROUGHPUT_MB=$(echo "scale=2; $AVG_THROUGHPUT_MB * $PEAK_MULT" | bc)

echo "--- Throughput ---"
echo "Average throughput: ${AVG_THROUGHPUT_MB} MB/s (uncompressed)"
echo "Peak throughput: ${PEAK_THROUGHPUT_MB} MB/s (uncompressed)"

COMPRESSED_MB=$(echo "scale=2; $AVG_THROUGHPUT_MB / $COMP_RATIO" | bc)
PEAK_COMPRESSED_MB=$(echo "scale=2; $PEAK_THROUGHPUT_MB / $COMP_RATIO" | bc)
echo "Average throughput (compressed): ${COMPRESSED_MB} MB/s"
echo "Peak throughput (compressed): ${PEAK_COMPRESSED_MB} MB/s"

# Disk
DAILY_GB=$(echo "scale=2; $COMPRESSED_MB * 86400 / 1024" | bc)
TOTAL_GB=$(echo "scale=2; $DAILY_GB * $RETENTION_DAYS * $RF" | bc)
PER_BROKER_GB=$(echo "scale=2; $TOTAL_GB / $NUM_BROKERS * 1.3" | bc)

echo ""
echo "--- Disk ---"
echo "Daily data (compressed): ${DAILY_GB} GB/day"
echo "Total cluster data: ${TOTAL_GB} GB (${RETENTION_DAYS} days × RF=${RF})"
echo "Per broker (with 30% buffer): ${PER_BROKER_GB} GB"

# Network
INBOUND_PER_BROKER=$(echo "scale=2; $PEAK_COMPRESSED_MB / $NUM_BROKERS * $RF" | bc)
OUTBOUND_REPL=$(echo "scale=2; $PEAK_COMPRESSED_MB / $NUM_BROKERS * ($RF - 1)" | bc)
OUTBOUND_CONSUMERS=$(echo "scale=2; $PEAK_COMPRESSED_MB / $NUM_BROKERS * $PEAK_NUM_CG" | bc)
OUTBOUND_PER_BROKER=$(echo "scale=2; $OUTBOUND_REPL + $OUTBOUND_CONSUMERS" | bc)
INBOUND_GBPS=$(echo "scale=2; $INBOUND_PER_BROKER * 8 / 1024" | bc)
OUTBOUND_GBPS=$(echo "scale=2; $OUTBOUND_PER_BROKER * 8 / 1024" | bc)
MAX_DIRECTION_GBPS=$(awk -v in="$INBOUND_GBPS" -v out="$OUTBOUND_GBPS" 'BEGIN { print (in > out ? in : out) }')
REQUIRED_NIC_GBPS=$(echo "scale=2; $MAX_DIRECTION_GBPS / 0.70" | bc)

echo ""
echo "--- Network (per broker) ---"
echo "Inbound: ${INBOUND_PER_BROKER} MB/s = ${INBOUND_GBPS} Gbps (producers + replication)"
echo "Outbound replication: ${OUTBOUND_REPL} MB/s"
echo "Outbound consumers: ${OUTBOUND_CONSUMERS} MB/s (${PEAK_NUM_CG} groups)"
echo "Outbound total: ${OUTBOUND_PER_BROKER} MB/s = ${OUTBOUND_GBPS} Gbps"
echo "Required NIC one-way capacity with 30% headroom: ${REQUIRED_NIC_GBPS} Gbps"

# Partitions
ceil_div() {
  awk -v a="$1" -v b="$2" 'function ceil(x){return x == int(x) ? x : int(x)+1} BEGIN{print ceil(a/b)}'
}
PRODUCER_PARTITIONS=$(ceil_div "$PEAK_COMPRESSED_MB" "$PRODUCER_MB_PER_PARTITION")
CONSUMER_PARTITIONS=$(ceil_div "$PEAK_COMPRESSED_MB" "$CONSUMER_MB_PER_PARTITION")
PARTITIONS=$(printf "%s\n%s\n%s\n%s\n" "$PRODUCER_PARTITIONS" "$CONSUMER_PARTITIONS" "$MAX_CONSUMERS" "$ORDERING_GROUPS" | sort -nr | head -1)
if [ "$PARTITIONS" -lt 6 ]; then PARTITIONS=6; fi
# Round up to multiple of broker count
PARTITIONS=$(echo "($PARTITIONS + $NUM_BROKERS - 1) / $NUM_BROKERS * $NUM_BROKERS" | bc)

echo ""
echo "--- Partitions ---"
echo "Recommended partitions per topic: ${PARTITIONS}"
echo "  producer throughput need: ${PRODUCER_PARTITIONS}"
echo "  consumer throughput need: ${CONSUMER_PARTITIONS}"
echo "  max consumer instances: ${MAX_CONSUMERS}"
echo "  ordering groups floor: ${ORDERING_GROUPS}"
echo "Partitions per broker: $(echo "$PARTITIONS / $NUM_BROKERS" | bc)"

# Memory
PAGE_CACHE_GB=$(echo "scale=0; $PARTITIONS * 1 * 0.3" | bc) # 30% of active segments
TOTAL_RAM=$((PAGE_CACHE_GB + 8 + 6)) # page cache + OS + JVM heap

echo ""
echo "--- Memory (per broker) ---"
echo "Kafka JVM heap: 6 GB"
echo "OS + overhead: 8 GB"  
echo "Page cache (estimated): ${PAGE_CACHE_GB} GB"
echo "Total RAM recommended: ${TOTAL_RAM} GB (round up to nearest power of 2)"

# NIC recommendation
if (( $(echo "$REQUIRED_NIC_GBPS > 1.0" | bc -l) )); then
    echo ""
    echo "⚠️  NIC Recommendation: 10 Gbps (required one-way capacity ${REQUIRED_NIC_GBPS} Gbps)"
else
    echo ""
    echo "✓ NIC Recommendation: 1 Gbps sufficient"
fi

echo ""
echo "=== SUMMARY ==="
echo "Brokers: ${NUM_BROKERS}"
echo "RAM per broker: ${TOTAL_RAM} GB"
echo "Disk per broker: ${PER_BROKER_GB} GB"
echo "NIC: $(if (( $(echo "$REQUIRED_NIC_GBPS > 1.0" | bc -l) )); then echo '10 Gbps'; else echo '1 Gbps'; fi)"
echo "Partitions per topic: ${PARTITIONS}"
```

### 8.2 Verify Cluster Capacity with Benchmarks

```bash
# File day-21-capacity-planning/docker-compose.yml được cung cấp kèm bài.
# Nếu chỉ copy code block trong lesson, tạo file đó trước rồi chạy:
docker compose up -d

# Create separate topics: 1 partition để đo per-partition, N partitions để đo scale-out
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic capacity-per-partition \
    --partitions 1 \
    --replication-factor 1 \
    --config retention.ms=3600000

  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic capacity-scale \
    --partitions 12 \
    --replication-factor 1 \
    --config retention.ms=3600000
"

# Test 1: Find max producer throughput per partition
echo "=== Max throughput: 1 partition ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic capacity-per-partition \
  --num-records 500000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=5 \
    compression.type=lz4

# NOTE: record the MB/s from output → this is your Pp (per-partition producer throughput)

# Test 2: Verify scale-out with 12 partitions
echo "=== Scale-out producer throughput: 12 partitions ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic capacity-scale \
  --num-records 1000000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=5 \
    compression.type=lz4

# Test 3: Find max consumer throughput on the same N-partition topic
echo "=== Max consumer throughput: 12 partitions ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-consumer-perf-test \
  --topic capacity-scale \
  --bootstrap-server localhost:9092 \
  --messages 1000000

# Test 4: Verify disk usage in bytes; do not sum human-readable du -sh output
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  echo '--- Disk usage per partition ---'
  du -sh /var/lib/kafka/data/capacity-*
  echo ''
  echo '--- Total topic size ---'
  du -sb /var/lib/kafka/data/capacity-* | awk '{sum += \$1} END {printf \"%.2f MiB total\\n\", sum/1024/1024}'
"

# Test 5: Topic describe for verification
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server localhost:9092 \
  --describe --topic capacity-per-partition

docker exec -it $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server localhost:9092 \
  --describe --topic capacity-scale
```

### 8.3 Capacity Planning Acceptance Checklist

Trước khi chốt sizing proposal, checklist tối thiểu:

- [ ] Có peak throughput riêng cho producer và consumer, không chỉ average.
- [ ] Per-partition throughput được đo bằng topic 1 partition; scale-out được đo bằng topic N partitions.
- [ ] Partition count lấy `max(producer_need, consumer_need, max_consumers, ordering_groups)` và round theo số broker.
- [ ] NIC tính INBOUND và OUTBOUND riêng với headroom tối thiểu 30%; aggregate chỉ dùng để báo cáo conservative.
- [ ] Disk sizing dùng bytes/MiB/GiB nhất quán; không cộng output human-readable từ `du -sh`.
- [ ] Retention tính trên compressed bytes, replication factor, growth buffer và operational free space.
- [ ] Có ghi rõ assumption: message size, compression, acks, RF, hardware, client concurrency.
- [ ] Có plan nếu cần tăng partitions: impact tới key ordering, consumer rollout và topic migration.

### 8.4 Scenario Exercise: E-commerce Platform Sizing

```
EXERCISE: Thiết kế capacity cho e-commerce platform

Requirements:
- 500 orders/second (average), 2000 orders/second (peak: Black Friday)
- Order message: ~2KB (JSON with items, addresses, etc.)
- Topics:
  1. orders (all orders)           — retention 30 days
  2. order-events (status changes) — retention 90 days
  3. inventory-updates             — retention 7 days, compacted
  4. user-activity (clickstream)   — retention 3 days
  5. notifications                 — retention 1 day

- Consumer groups per topic:
  orders: 4 (payment, inventory, shipping, analytics)
  order-events: 3 (audit, analytics, notification)
  inventory-updates: 2 (warehouse, dashboard)
  user-activity: 2 (analytics, recommendation engine)
  notifications: 1 (notification service)

- Replication: 3 for orders/events, 2 for others
- Compression: lz4 everywhere
- Availability: 99.95% (tolerate 1 broker failure)

YOUR TASK: Calculate:
1. Partition count per topic
2. Total disk requirement per broker
3. Network bandwidth per broker
4. Number of brokers
5. RAM per broker
6. Disk type recommendation (HDD/SSD)

SOLUTION HINTS:
- Average data rate:
  orders: 500/s × 2KB = 1 MB/s
  order-events: 500/s × 5 event types × 0.5KB = 1.25 MB/s
  inventory-updates: 100/s × 1KB = 0.1 MB/s
  user-activity: 5000/s × 0.5KB = 2.5 MB/s
  notifications: 500/s × 0.3KB = 0.15 MB/s
  Total: ~5 MB/s average, ~20 MB/s peak
  
  → This is a SMALL cluster! 3 brokers sufficient.
```

### 8.5 Partition Expansion Impact Test

```bash
# Demo: impact of adding partitions on key ordering

# Create topic with 4 partitions
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic partition-demo \
    --partitions 4 \
    --replication-factor 1
"

# Produce messages with fixed key to observe partition assignment
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  for i in \$(seq 1 5); do
    echo 'user-123:{\"event\":\"click_\$i\"}' | \
    kafka-console-producer \
      --bootstrap-server localhost:9092 \
      --topic partition-demo \
      --property parse.key=true \
      --property key.separator=:
  done
"

# Check which partition key 'user-123' goes to
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  echo '--- Before expansion ---'
  for p in 0 1 2 3; do
    count=\$(kafka-console-consumer \
      --bootstrap-server localhost:9092 \
      --topic partition-demo \
      --partition \$p \
      --from-beginning --timeout-ms 3000 2>/dev/null | wc -l)
    echo \"Partition \$p: \$count messages\"
  done
"

# Expand to 8 partitions
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --alter \
    --topic partition-demo \
    --partitions 8
  echo 'Expanded to 8 partitions'
"

# Produce SAME key again — may go to DIFFERENT partition!
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  for i in \$(seq 6 10); do
    echo 'user-123:{\"event\":\"click_\$i\"}' | \
    kafka-console-producer \
      --bootstrap-server localhost:9092 \
      --topic partition-demo \
      --property parse.key=true \
      --property key.separator=:
  done
"

# Check partition distribution after expansion
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  echo '--- After expansion ---'
  for p in 0 1 2 3 4 5 6 7; do
    count=\$(kafka-console-consumer \
      --bootstrap-server localhost:9092 \
      --topic partition-demo \
      --partition \$p \
      --from-beginning --timeout-ms 3000 2>/dev/null | wc -l)
    echo \"Partition \$p: \$count messages\"
  done
"

# OBSERVE: key 'user-123' may now be in 2 DIFFERENT partitions!
# → Ordering guarantee BROKEN for this key
# → This is why partition count should be planned upfront
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Topic có 12 partitions. Bạn cần scale consumer group từ 4 lên 20 instances. Tại sao chỉ 12 instances effective? Giải pháp?**
   - Hint: max parallelism = num_partitions. 8 consumers idle. Tạo topic mới với nhiều partitions hơn.

2. **Cluster 3 brokers, mỗi broker 2TB disk (SSD). Throughput 50MB/s, RF=3, lz4 compression (2x). Retention TỐI ĐA bao nhiêu ngày?**
   - Hint: daily data = 50MB/s ÷ 2(lz4) × 86400s = 2.16TB/day. With RF=3: 6.48TB/day. Total 6TB disk. 6TB / 6.48TB = ~0.9 days? Kiểm tra lại logic.

3. **Topic order-events có messages keyed bởi orderId. Sau 6 tháng production, traffic tăng gấp 3x và bạn cần thêm partitions (từ 12 lên 36). Rủi ro gì? Cách an toàn nhất?**
   - Hint: hash(orderId) % 12 ≠ hash(orderId) % 36. Create new topic và migrate.

4. **Broker A host 5000 partitions, Broker B host 1000 partitions. Broker A crash. Tại sao recovery chậm?**
   - Hint: 5000 leader elections cần thực hiện. Each election = metadata update + ISR check.

5. **Network NIC 1Gbps. Throughput 30MB/s, RF=3, 3 consumer groups. Đủ bandwidth không?**
   - Hint: Inbound = 30 × 3 = 90MB/s. Outbound = 30 × 2 (repl) + 30 × 3 (consumers) = 150MB/s. Total per broker (3 brokers) = (90+150)/3 = 80MB/s = 640Mbps. 64% of 1Gbps → borderline.

6. **Bạn cần event sourcing topic (retain forever). 10MB/s, RF=3. Sau 1 năm, bao nhiêu storage?**
   - Hint: 10MB/s ÷ 2(lz4) × 86400 × 365 × 3 = ?

7. **vm.swappiness=1, disk SSD NVMe, network 25Gbps. Throughput vẫn chỉ 200K msg/s. Bottleneck ở đâu?**
   - Hint: check producer config (linger, batch, compression), partition count, consumer count.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Operations — Hardware & OS](https://kafka.apache.org/documentation/#hwandos)
- [Kafka Operations — Production](https://kafka.apache.org/documentation/#ops)
- [Confluent — Sizing Calculator](https://eventsizer.io/)
- [Confluent — Running Kafka in Production](https://docs.confluent.io/platform/current/kafka/deployment.html)

### Blog Posts & Articles
- [Confluent — How to Choose Number of Topics/Partitions](https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/)
- [LinkedIn — Kafka at Scale: 7 Trillion Messages Per Day](https://engineering.linkedin.com/blog/2019/apache-kafka-at-scale)
- [Uber Engineering — Kafka Capacity Planning](https://www.uber.com/blog/kafka/)
- [CloudKarafka — Kafka Sizing Guide](https://www.cloudkarafka.com/blog/kafka-sizing-guide.html)
- [Confluent — Tiered Storage](https://docs.confluent.io/platform/current/kafka/tiered-storage.html)

### Videos & Talks
- [Kafka Summit — Sizing and Capacity Planning](https://www.confluent.io/events/kafka-summit/)
- [GOTO Conference — Running Kafka in Production](https://www.youtube.com/results?search_query=kafka+capacity+planning+production)
- [Confluent Developer — Cluster Sizing](https://developer.confluent.io/courses/)
