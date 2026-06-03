# Day 20: Kafka Performance Tuning — Producer, Consumer, Broker & OS-Level Optimization

> Companion split: xem `document.md` để đào sâu benchmark methodology và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** performance model của Kafka — tại sao Kafka nhanh (sequential I/O, zero-copy, page cache, batching) và bottleneck ở đâu
2. **Nắm vững** producer tuning: batch.size, linger.ms, compression, buffer.memory, acks — trade-off giữa throughput, latency, durability
3. **Thực hành** consumer tuning: fetch.min.bytes, fetch.max.wait.ms, max.poll.records, max.poll.interval.ms — tối ưu cho high-throughput và low-latency
4. **Hiểu** broker tuning: num.network.threads, num.io.threads, log.segment.bytes, log.retention — cấu hình cho production workload
5. **Biết** OS-level tuning: page cache, file descriptors, disk I/O scheduler, network buffer — foundational performance

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-13 (Kafka fundamentals, producer/consumer internals, replication)
- Hiểu partition, replication factor, ISR, acks
- Hiểu producer batching, consumer polling model
- Docker Compose Kafka cluster đang chạy
- Familiar với Linux performance tools (top, iostat, vmstat)

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Kafka performance model — tại sao nhanh, bottleneck phổ biến
- Producer tuning — batch.size, linger.ms, compression, acks, buffer.memory
- Consumer tuning — fetch config, poll config, commit strategy
- Broker tuning — thread pools, log segments, replication tuning
- Hands-on: benchmark với kafka-producer-perf-test & kafka-consumer-perf-test

### 🟡 Should Learn (nếu còn thời gian)
- OS-level tuning — page cache, file descriptors, disk scheduler
- JVM tuning cho Kafka broker — heap size, GC settings
- Network tuning — socket buffers, TCP settings
- Monitoring performance metrics với JMX

### 🟢 Optional Deep Dive
- End-to-end latency analysis — profiling từng hop
- Compression algorithm comparison (LZ4 vs Snappy vs Zstd vs GZIP)
- Tiered storage performance impact
- Multi-datacenter replication performance (MirrorMaker 2)

---

## 4. Lý thuyết (Theory)

### 4.1 Performance Model — Tại sao Kafka nhanh?

#### WHY — Hiểu internals để biết tối ưu ở đâu

```
KAFKA PERFORMANCE FOUNDATIONS:

  1. SEQUENTIAL I/O (thay vì random I/O):
  ┌──────────────────────────────────────────────────────┐
  │  HDD Random I/O:   ~100 IOPS    = ~100 msg/s        │
  │  HDD Sequential:   ~100 MB/s    = ~200K msg/s       │
  │  SSD Random I/O:   ~50K IOPS    = ~50K msg/s        │
  │  SSD Sequential:   ~500 MB/s    = ~1M msg/s         │
  │                                                      │
  │  Kafka writes = append-only log = SEQUENTIAL         │
  │  → HDD sequential > SSD random!                      │
  │  → Đây là lý do Kafka có thể dùng HDD mà vẫn nhanh │
  └──────────────────────────────────────────────────────┘

  2. PAGE CACHE (OS-level caching):
  ┌──────────────────────────────────────────────────────┐
  │  Producer write:                                      │
  │  App → Kafka Broker JVM → OS Page Cache → Disk       │
  │                                                      │
  │  Consumer read (tailing — real-time consuming):      │
  │  Disk ✗ → OS Page Cache ✓ → Kafka Broker → Consumer │
  │                                                      │
  │  Real-time consumer đọc data VỪA được write          │
  │  → Data CÒN trong page cache → KHÔNG cần đọc disk!  │
  │  → Consumer throughput ≈ network speed, không phải   │
  │    disk speed                                        │
  │                                                      │
  │  KEY INSIGHT:                                        │
  │  Kafka broker heap nhỏ (6-8GB) vì DATA không ở heap  │
  │  Data ở PAGE CACHE (RAM do OS quản lý)               │
  │  → Heap lớn = GC pause lớn = latency spike!         │
  └──────────────────────────────────────────────────────┘

  3. ZERO-COPY (sendfile syscall):
  ┌──────────────────────────────────────────────────────┐
  │  Traditional copy:                                    │
  │  Disk → Kernel Buffer → User Buffer → Socket Buffer  │
  │  = 4 copies + 2 context switches                     │
  │                                                      │
  │  Zero-copy (sendfile):                               │
  │  Disk → Kernel Buffer → Socket Buffer                │
  │  = 2 copies + 0 context switches                     │
  │                                                      │
  │  Kafka consumer fetch = sendfile()                   │
  │  → CPU usage giảm ~50%                               │
  │  → Throughput tăng ~2-3x cho consumer-heavy workload │
  └──────────────────────────────────────────────────────┘

  4. BATCHING (producer + broker + consumer):
  ┌──────────────────────────────────────────────────────┐
  │  Without batching:                                    │
  │  100K messages × 1 network round-trip each           │
  │  = 100K round-trips × 0.5ms = 50 seconds!           │
  │                                                      │
  │  With batching (batch.size = 1000):                  │
  │  100 batches × 1 round-trip each                     │
  │  = 100 round-trips × 0.5ms = 50ms!                  │
  │                                                      │
  │  → 1000x faster!                                     │
  │  → Amortize network overhead across many messages    │
  └──────────────────────────────────────────────────────┘

  5. COMPRESSION (batch-level):
  ┌──────────────────────────────────────────────────────┐
  │  Compress TOÀN BỘ batch, không phải từng message     │
  │  → Compression ratio tốt hơn (similar messages)     │
  │  → Less network I/O                                  │
  │  → Less disk I/O                                     │
  │  → CPU trade-off: compress/decompress time           │
  │                                                      │
  │  Compression ratio (JSON data, typical):             │
  │  - None:   1.0x (baseline)                           │
  │  - Snappy: ~2x  (fast, moderate ratio)               │
  │  - LZ4:    ~2x  (fastest, moderate ratio)            │
  │  - Zstd:   ~3x  (best ratio, good speed)             │
  │  - GZIP:   ~3x  (best ratio, SLOW!)                  │
  └──────────────────────────────────────────────────────┘
```

#### Bottleneck Identification

```
PERFORMANCE BOTTLENECKS — Debug Flow:

  Throughput thấp?
  ┌──────────────┐
  │ Check CPU    │──► CPU > 80%? → compression, serialization
  │              │                  Giải pháp: đổi compression alg
  └──────┬───────┘                  hoặc tắt compression
         │ No
  ┌──────▼───────┐
  │ Check Disk   │──► Disk I/O > 80%? → log writes, compaction
  │ (iostat)     │                  Giải pháp: SSD, nhiều disks,
  └──────┬───────┘                  tune log.segment.bytes
         │ No
  ┌──────▼───────┐
  │ Check Network│──► Network > 80%? → replication, fetch
  │ (iftop/nload)│                  Giải pháp: compression, tune
  └──────┬───────┘                  replication factor
         │ No
  ┌──────▼───────┐
  │ Check JVM    │──► GC pauses > 200ms? → heap quá lớn
  │ (GC logs)    │                  Giải pháp: giảm heap,
  └──────┬───────┘                  dùng G1GC
         │ No
  ┌──────▼───────┐
  │ Check Config │──► Producer batch quá nhỏ?
  │              │    Consumer fetch quá nhỏ?
  │              │    Broker threads quá ít?
  └──────────────┘


  Latency cao?
  ┌────────────────────────────────────────────────────────┐
  │  End-to-end latency = Σ (mỗi hop):                    │
  │                                                       │
  │  Producer:                                            │
  │    ├─ Serialization:     ~0.1ms                       │
  │    ├─ Compression:       ~0.5-5ms (depends on alg)    │
  │    ├─ Batching wait:     0 - linger.ms                │
  │    ├─ Network to broker: ~0.5-2ms (same DC)           │
  │    └─ Ack wait:          ~1-10ms (acks=all)           │
  │                                                       │
  │  Broker:                                              │
  │    ├─ Write to page cache: ~0.01ms                    │
  │    ├─ Replication:        ~1-5ms (ISR followers)      │
  │    └─ Fsync (if enabled): ~5-50ms (AVOID!)            │
  │                                                       │
  │  Consumer:                                            │
  │    ├─ Fetch wait:         0 - fetch.max.wait.ms       │
  │    ├─ Network from broker: ~0.5-2ms                   │
  │    ├─ Deserialization:    ~0.1ms                       │
  │    └─ Processing:         application-dependent       │
  │                                                       │
  │  TYPICAL end-to-end (same DC, acks=all):              │
  │    5-50ms (well-tuned)                                │
  │    100-500ms (default config)                         │
  └────────────────────────────────────────────────────────┘
```

### 4.2 Producer Tuning

#### Core Parameters

```
PRODUCER CONFIGURATION MAP:

  ┌─────────────────────────────────────────────────────────┐
  │                     Producer                             │
  │                                                         │
  │  Record ──► Serializer ──► Partitioner ──► Accumulator  │
  │                                           (per partition │
  │                                            batch buffer) │
  │                                               │         │
  │                              batch.size ──────┤         │
  │                              linger.ms ───────┤         │
  │                              buffer.memory ───┘         │
  │                                               │         │
  │                              Compression ─────┤         │
  │                                               │         │
  │                                          ┌────▼────┐    │
  │                                          │ Sender  │    │
  │                                          │ Thread  │    │
  │                                          └────┬────┘    │
  │                                               │         │
  │            max.in.flight.requests ────────────┤         │
  │            acks ──────────────────────────────┤         │
  │            retries ───────────────────────────┤         │
  │            request.timeout.ms ────────────────┘         │
  │                                               │         │
  │                                          ┌────▼────┐    │
  │                                          │ Broker  │    │
  │                                          └─────────┘    │
  └─────────────────────────────────────────────────────────┘
```

```
1. batch.size (default: 16384 = 16KB)
   
   Kích thước batch buffer PER PARTITION
   
   Quá nhỏ (< 16KB):
   → Nhiều requests nhỏ → network overhead lớn
   → Throughput thấp
   
   Quá lớn (> 1MB):  
   → RAM usage tăng: batch.size × num_partitions
   → Latency tăng (chờ batch đầy)
   
   Recommendation:
   - High throughput: 65536-131072 (64KB-128KB)
   - Low latency: 16384 (default, send khi có 16KB)
   - Bulk load: 262144-524288 (256KB-512KB)

   ⚠️ batch.size là UPPER BOUND, NOT minimum
   → Batch gửi khi đầy HOẶC khi hết linger.ms


2. linger.ms (default: 0)
   
   Thời gian CHỜ thêm records trước khi gửi batch
   
   linger.ms = 0 (default):
   → Gửi ngay khi có record → latency thấp nhất
   → Nhưng batch thường chỉ có 1 record → throughput thấp
   
   linger.ms = 5-10:
   → Chờ thêm 5-10ms để accumulate records
   → Batch lớn hơn → throughput tăng đáng kể
   → Latency thêm 5-10ms (acceptable cho hầu hết use cases)
   
   linger.ms = 100-200:
   → Batch rất lớn → throughput cao nhất
   → Latency thêm 100-200ms (chỉ cho bulk/batch processing)
   
   Recommendation:
   - Low latency: 0-5ms
   - Balanced: 5-20ms (recommended default)
   - Max throughput: 50-200ms

   KEY INSIGHT:
   batch.size + linger.ms hoạt động cùng nhau:
   → Batch gửi khi: batch.size ĐẦY hoặc linger.ms HẾT
   → Whichever comes first


3. compression.type (default: none)
   
   | Algorithm | Compress Ratio | Compress Speed | Decompress Speed | CPU Usage |
   |-----------|---------------|----------------|------------------|-----------|
   | none      | 1.0x          | -              | -                | Thấp nhất |
   | snappy    | ~2.0x         | ~250 MB/s      | ~500 MB/s        | Thấp      |
   | lz4       | ~2.1x         | ~400 MB/s      | ~800 MB/s        | Thấp nhất |
   | zstd      | ~2.8x         | ~100 MB/s      | ~400 MB/s        | Trung bình|
   | gzip      | ~2.8x         | ~30 MB/s       | ~200 MB/s        | Cao       |
   
   Recommendation:
   - Default khởi đầu tốt cho nhiều workload: lz4 (speed/ratio cân bằng)
   - Network constrained hoặc storage cost cao: zstd (ratio tốt hơn, CPU cao hơn)
   - Legacy systems: snappy (widely supported)
   - GZIP: không dùng làm default; chỉ cân nhắc khi bandwidth/storage là bottleneck chính và CPU còn dư
   
   ⚠️ Compression ở BATCH level, không phải message level
   → Batch lớn hơn → compress ratio TỐT hơn (similar messages)
   → Tăng batch.size/linger.ms khi enable compression


4. acks (default: all, Kafka 3.0+)
   
   | acks | Durability | Throughput | Latency |
   |------|-----------|------------|---------|
   | 0    | Thấp nhất (fire-and-forget) | Cao nhất | Thấp nhất |
   | 1    | Leader only | Cao | Thấp |
   | all  | All ISR replicas | Thấp nhất | Cao nhất |
   
   acks=0: Producer KHÔNG chờ ack
   → Có thể mất data nếu broker crash
   → Use case: metrics, logs không critical

   acks=1: Chờ leader write
   → Mất data nếu leader crash trước replicate
   → Use case: balanced durability/performance

   acks=all: Chờ tất cả replicas đang ở trong ISR ack
   → Giảm rủi ro mất data khi kết hợp replication.factor ≥ 3, min.insync.replicas ≥ 2 và unclean leader election disabled
   → Use case: financial, orders, critical events
   
   ⚠️ acks=all + min.insync.replicas=1 vẫn có thể accept write khi ISR chỉ còn leader.
   → Với topic critical, set min.insync.replicas ≥ 2 và xử lý producer error khi ISR shrink


5. buffer.memory (default: 33554432 = 32MB)
   
   Total memory cho TẤT CẢ batch buffers
   
   Khi buffer đầy → producer.send() BLOCK
   → max.block.ms (default 60s) trước khi throw exception
   
   Recommendation:
   - Default 32MB đủ cho hầu hết
   - High throughput: 64-128MB
   - Nhiều partitions (>100): 128-256MB
   
   Formula: buffer.memory >= batch.size × num_active_partitions × 2


6. max.in.flight.requests.per.connection (default: 5)
   
   Số requests chưa được ack có thể gửi đồng thời per connection
   
   Vấn đề: > 1 → có thể OUT OF ORDER khi retry!
   Request 1 fail → retry → meanwhile Request 2 success
   → Message order: [2, 1] thay vì [1, 2]
   
   enable.idempotence = true (default Kafka 3.0+):
   → Safe với max.in.flight = 5 (Kafka handle ordering)
   → Kafka tự reorder nếu retry
   
   Recommendation:
   - enable.idempotence=true + max.in.flight=5 (default, recommended)
   - Nếu ordering CRITICAL và idempotence off: max.in.flight=1
```

### 4.3 Consumer Tuning

```
CONSUMER PERFORMANCE PARAMETERS:

  ┌─────────────────────────────────────────────────────────┐
  │                     Consumer                             │
  │                                                         │
  │  ┌──────────────┐                                       │
  │  │ Broker       │                                       │
  │  │              │◄── fetch.min.bytes (min data per fetch)│
  │  │  fetch data  │◄── fetch.max.wait.ms (max wait time)  │
  │  │              │◄── fetch.max.bytes (max data per fetch)│
  │  │              │◄── max.partition.fetch.bytes           │
  │  └──────┬───────┘                                       │
  │         │                                               │
  │  ┌──────▼───────┐                                       │
  │  │ Internal     │                                       │
  │  │ Buffer       │                                       │
  │  └──────┬───────┘                                       │
  │         │                                               │
  │  ┌──────▼───────┐                                       │
  │  │ poll()       │◄── max.poll.records (records per poll) │
  │  │              │◄── max.poll.interval.ms (timeout)     │
  │  └──────┬───────┘                                       │
  │         │                                               │
  │  ┌──────▼───────┐                                       │
  │  │ Process      │                                       │
  │  │ + Commit     │◄── enable.auto.commit                 │
  │  │              │◄── auto.commit.interval.ms            │
  │  └──────────────┘                                       │
  └─────────────────────────────────────────────────────────┘


1. fetch.min.bytes (default: 1)
   
   Broker trả về KHI CÓ ít nhất X bytes data
   
   fetch.min.bytes = 1 (default):
   → Trả về ngay khi có data → low latency
   → Nhưng có thể trả về rất ít data → nhiều fetch requests
   
   fetch.min.bytes = 10000 (10KB):
   → Chờ accumulate 10KB → ít fetch requests → throughput↑
   → Latency↑ (chờ data accumulate)
   
   Kết hợp với fetch.max.wait.ms:
   → Trả về khi: fetch.min.bytes ĐẠT hoặc fetch.max.wait.ms HẾT


2. fetch.max.wait.ms (default: 500)
   
   Max time broker chờ khi chưa đủ fetch.min.bytes
   
   fetch.max.wait.ms = 100:
   → Trả về sau 100ms dù chưa đủ fetch.min.bytes
   → Low latency, có thể fetch ít data
   
   fetch.max.wait.ms = 1000:
   → Chờ lâu hơn → batch lớn hơn → throughput↑
   → Latency↑ lên đến 1 giây


3. max.poll.records (default: 500)
   
   Số records TỐI ĐA trả về per poll() call
   
   max.poll.records = 100:
   → Process ít records mỗi lần → commit thường xuyên hơn
   → Ít data loss khi crash → nhưng throughput↓
   
   max.poll.records = 1000-5000:
   → Batch lớn → throughput↑
   → Nhưng nếu processing chậm → vượt max.poll.interval.ms
     → REBALANCE!
   
   ⚠️ CRITICAL RULE:
   processing_time(max.poll.records) < max.poll.interval.ms
   
   Ví dụ: processing mỗi record 10ms, max.poll.records=500
   → 500 × 10ms = 5000ms = 5s processing time
   → max.poll.interval.ms phải > 5s (default 300s → OK)


4. max.poll.interval.ms (default: 300000 = 5 phút)
   
   Max time giữa 2 poll() calls trước khi consumer bị coi là dead
   → Heartbeat riêng (background thread) giữ session alive
   → Nhưng nếu processing quá lâu → không poll() kịp → REBALANCE
   
   Recommendation:
   - Default 5 phút: OK cho hầu hết workloads
   - Heavy processing: tăng lên 10-15 phút
   - ĐỪNG set quá cao: delay detect dead consumers
   
   Thay vì tăng max.poll.interval.ms:
   → Giảm max.poll.records → xử lý nhanh hơn per poll
   → Hoặc offload processing sang thread pool


5. session.timeout.ms (default: 45000) + heartbeat.interval.ms (default: 3000)
   
   session.timeout.ms = thời gian broker chờ heartbeat
   heartbeat.interval.ms = tần suất gửi heartbeat
   
   Rule: heartbeat.interval.ms ≤ session.timeout.ms / 3
   
   Recommendation:
   - session.timeout.ms = 10000-30000 (10-30s)
   - heartbeat.interval.ms = session.timeout.ms / 3
   - Detect dead consumers nhanh hơn → rebalance nhanh hơn
```

### 4.4 Broker Tuning

```
BROKER CONFIGURATION:

1. Thread Pools:

  ┌──────────────────────────────────────────────────────────┐
  │                      Kafka Broker                         │
  │                                                          │
  │  ┌─────────────────────┐                                 │
  │  │  Network Threads     │  num.network.threads = 3       │
  │  │  (Acceptor + I/O)    │  → Handle network requests     │
  │  │                     │  → Parse requests               │
  │  │  Thread 1 ─────┐    │  → Send responses               │
  │  │  Thread 2 ─────┤    │                                 │
  │  │  Thread 3 ─────┤    │  Rule: 1 per 2GB/s throughput   │
  │  └────────────────┤────┘  Typical: 3-8 threads           │
  │                   │                                      │
  │            Request Queue                                 │
  │            queued.max.requests = 500                      │
  │                   │                                      │
  │  ┌────────────────▼────┐                                 │
  │  │  I/O Threads         │  num.io.threads = 8            │
  │  │  (Request Handler)   │  → Read/write to disk          │
  │  │                     │  → Fetch from page cache        │
  │  │  Thread 1-8         │  → Process produce/fetch        │
  │  │                     │                                 │
  │  │  Rule: ≥ #disks     │  Typical: 8-16 threads          │
  │  └─────────────────────┘                                 │
  │                                                          │
  │  ┌─────────────────────┐                                 │
  │  │  Background Threads  │                                 │
  │  │                     │                                 │
  │  │  Log Cleaner:       │  log.cleaner.threads = 1        │
  │  │  (compaction)       │  → 1 per 100GB log data         │
  │  │                     │                                 │
  │  │  Replication:       │  num.replica.fetchers = 1       │
  │  │  (follower fetch)   │  → 1 per 1000 partitions leader │
  │  └─────────────────────┘                                 │
  └──────────────────────────────────────────────────────────┘


2. Log Segment Configuration:

  log.segment.bytes = 1073741824 (1GB default)
  → Kích thước 1 segment file trước khi roll new segment
  → Nhỏ quá → nhiều files → fd usage tăng, metadata overhead
  → Lớn quá → retention/compaction granularity thô
  → Recommendation: 1GB (default OK cho hầu hết)

  log.segment.ms = 168 hours (7 days default)
  → Max time trước khi roll segment (dù chưa đầy)
  → Đảm bảo retention hoạt động đúng cho low-throughput topics

  log.retention.hours = 168 (7 days default)
  → Giữ data bao lâu trước khi delete
  → Tùy use case: 24h (metrics), 7 ngày (events), forever (changelog)

  log.retention.bytes = -1 (unlimited)
  → Max bytes per partition trước khi delete old segments
  → Set khi cần limit disk usage per partition


3. Replication Tuning:

  replica.fetch.max.bytes = 1048576 (1MB)
  → Max data follower fetch per request
  → Tăng cho high-throughput → replication lag giảm
  
  replica.fetch.wait.max.ms = 500
  → Max time follower chờ data từ leader
  → Giảm → replication latency giảm, nhưng nhiều empty fetches
  
  num.replica.fetchers = 1
  → Threads per broker để replicate từ leaders
  → Tăng nếu replication lag do single-threaded bottleneck
  → Rule: 1 per 1000 partitions leader trên broker này

  replica.lag.time.max.ms = 30000 (30s)
  → Max time follower có thể lag trước khi bị remove khỏi ISR
  → Giảm → detect slow followers nhanh hơn → nhưng ISR flapping risk
  → Production: 10000-30000 (10-30s)


4. Memory & Buffer:

  socket.send.buffer.bytes = 102400 (100KB)
  socket.receive.buffer.bytes = 102400 (100KB)
  → OS TCP socket buffers
  → Cross-DC or high throughput: 1-4MB
  
  message.max.bytes = 1048588 (~1MB)
  → Max message size (including header)
  → Cần sync với producer max.request.size
  → Và consumer max.partition.fetch.bytes
```

### 4.5 OS-Level Tuning

```
OS TUNING FOR KAFKA:

1. PAGE CACHE — CỰC KỲ QUAN TRỌNG

  Kafka performance phụ thuộc CHÍNH vào page cache
  
  Rule of thumb:
  → Page cache ≥ tổng active segments (segments đang write + read)
  → Ví dụ: 100 partitions × 1GB segment = 100GB hot data
  →        Nhưng real-time consumers chỉ cần last few GB
  →        30-50% RAM cho page cache là tốt
  
  Server 64GB RAM:
  - Kafka heap: 6GB
  - OS + other: 8GB  
  - Page cache: 50GB  ← MOST RAM FOR PAGE CACHE
  
  ⚠️ KHÔNG tăng Kafka heap để "caching"!
  Kafka heap chỉ cho object metadata, NOT data
  Data caching = OS page cache (tự động)


2. FILE DESCRIPTORS

  # Check current limit
  ulimit -n  # default: 1024 (QUÁ THẤP!)
  
  # Kafka cần fd cho:
  # - Mỗi log segment: 2 fds (log + index)
  # - Mỗi network connection: 1 fd
  # - Misc: ~100 fds
  
  # Formula:
  # min_fds = (num_partitions × segments_per_partition × 2)
  #         + max_connections + 100
  
  # Ví dụ: 1000 partitions × 10 segments × 2 = 20,000 fds
  
  # Set in /etc/security/limits.conf:
  kafka  soft  nofile  100000
  kafka  hard  nofile  100000


3. DISK I/O SCHEDULER

  # Kafka = sequential writes; scheduler đúng phụ thuộc kernel + device
  
  # Check current scheduler:
  cat /sys/block/sda/queue/scheduler
  
  # Modern Linux examples:
  echo "mq-deadline" > /sys/block/sda/queue/scheduler  # many SSD/HDD setups
  echo "none" > /sys/block/nvme0n1/queue/scheduler     # common for NVMe with good controller
  
  # Tại sao: 
  # old cfq/deadline/noop advice không còn đúng cho mọi kernel.
  # benchmark trên đúng instance type và quan sát await/util/iowait trước khi đổi.


4. NETWORK TUNING

  # /etc/sysctl.conf
  
  # Increase socket buffer sizes
  net.core.wmem_default = 131072
  net.core.rmem_default = 131072
  net.core.wmem_max = 2097152    # 2MB
  net.core.rmem_max = 2097152    # 2MB
  
  # TCP buffer auto-tuning
  net.ipv4.tcp_wmem = 4096 65536 2097152
  net.ipv4.tcp_rmem = 4096 65536 2097152
  
  # Max connections
  net.core.somaxconn = 32768
  net.core.netdev_max_backlog = 32768


5. VIRTUAL MEMORY

  # Reduce swappiness (Kafka should NOT swap)
  vm.swappiness = 1  # 0 could trigger OOM killer
  
  # Dirty page ratio
  vm.dirty_background_ratio = 5   # start flushing at 5%
  vm.dirty_ratio = 60             # force flush at 60%
  # Lower background_ratio → more frequent smaller flushes
  # → Smoother I/O, less latency spikes
```

---

## 5. Trade-off Analysis

### Producer Configuration Profiles

| Profile | batch.size | linger.ms | compression | acks | Use Case |
|---------|-----------|-----------|-------------|------|----------|
| Low Latency | 16384 | 0-5 | none/lz4 | 1/all | Real-time events, user actions; chọn theo durability |
| Balanced | 65536 | 10-20 | lz4 | all | Điểm bắt đầu cho nhiều workload, không phải luật tuyệt đối |
| High Throughput | 131072 | 50-100 | zstd | all | Log aggregation, CDC, bulk load |
| Fire & Forget | 65536 | 5 | snappy | 0 | Metrics, telemetry, non-critical |

### Consumer Configuration Profiles

| Profile | fetch.min.bytes | fetch.max.wait.ms | max.poll.records | Use Case |
|---------|----------------|-------------------|-----------------|----------|
| Low Latency | 1 | 100 | 100 | Real-time alerting |
| Balanced | 1024 | 500 | 500 | Most workloads |
| High Throughput | 50000 | 1000 | 2000 | Log processing, analytics |
| Batch Process | 100000 | 2000 | 5000 | Batch aggregation, ETL |

### Compression Algorithm Selection

| Tiêu chí | LZ4 | Snappy | Zstd | GZIP |
|----------|-----|--------|------|------|
| Compress speed | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| Decompress speed | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Ratio | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| CPU usage | Thấp | Thấp | Trung bình | Cao |
| Best for | Good starting default | Legacy compat | Network limited | Rare, CPU-costly cases |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. START WITH DEFAULTS, MEASURE, THEN TUNE
   → Đừng premature optimize
   → Benchmark baseline → identify bottleneck → tune targeted
   → Change 1 parameter at a time → measure impact

2. Producer: thử `linger.ms=5` + `compression=lz4` như baseline tuning đầu tiên
   → Thường tăng throughput rõ rệt với latency tăng nhỏ, nhưng phải đo theo SLA
   → Nếu payload đã compressed, CPU nóng, hoặc latency cực thấp là mục tiêu chính, kết quả có thể ngược lại
   → Zstd/GZIP chỉ hợp lý khi network/storage mới là bottleneck chính

3. Consumer: max.poll.records phải match processing capacity
   → processing_time_per_record × max.poll.records < max.poll.interval.ms
   → Nếu process chậm → ưu tiên giảm max.poll.records/tách worker; chỉ tăng max.poll.interval.ms khi có lý do rõ và đã hiểu rebalance delay

4. Broker: RAM dành cho page cache, KHÔNG phải JVM heap
   → Server 64GB: Kafka heap 6GB, còn lại cho OS + page cache
   → Heap quá lớn → GC pauses → latency spikes

5. Monitor TRƯỚC khi tune
   → CPU, disk, network, GC → identify bottleneck đúng
   → Tune sai chỗ → worse than trước

6. Compression end-to-end (producer compress, broker keep, consumer decompress)
   → Set compression.type trên PRODUCER, KHÔNG phải broker
   → Broker config compression.type chỉ nên để "producer" (keep as-is)
```

### Common Pitfalls

```
❌ PITFALL 1: Kafka heap quá lớn
   Sai:  KAFKA_HEAP_OPTS="-Xmx32g -Xms32g" (toàn bộ RAM cho JVM)
   Đúng: KAFKA_HEAP_OPTS="-Xmx6g -Xms6g" (6GB đủ cho hầu hết)
   Tại sao: Kafka DATA không ở heap (ở page cache)
            Heap lớn → GC pause dài → latency spike 500ms+

❌ PITFALL 2: linger.ms=0 + no compression (default cũ)
   → Mỗi record gửi 1 request → network overhead khổng lồ
   → Fix thường dùng để thử: linger.ms=5, compression.type=lz4; verify lại p99 latency

❌ PITFALL 3: max.poll.records quá cao + processing chậm
   → 5000 records × 50ms/record = 250 seconds
   → max.poll.interval.ms = 300s → gần timeout → REBALANCE risk
   → Fix: giảm max.poll.records, hoặc async processing

❌ PITFALL 4: acks=all nhưng min.insync.replicas=1
   → Nếu ISR shrink chỉ còn leader, broker vẫn accept write; leader/disk failure vẫn mất data
   → Fix: topic critical dùng RF>=3, min.insync.replicas=2, producer phải handle NotEnoughReplicas

❌ PITFALL 5: Swappiness cao (default 60)
   → Kafka pages bị swap out → page fault → latency spike
   → Fix: vm.swappiness=1

❌ PITFALL 6: File descriptor limit quá thấp
   → ulimit -n = 1024 → Kafka crash với "Too many open files"
   → Fix: ulimit -n 100000

❌ PITFALL 7: Tune nhiều parameters cùng lúc
   → Không biết parameter nào giúp, parameter nào hại
   → Fix: thay 1 cái, benchmark, rồi mới thay cái tiếp
```

---

## 7. Performance Considerations

### Benchmark Numbers (Reference, không phải cam kết production)

```
REFERENCE BENCHMARKS (3 brokers, 6 cores, 32GB RAM each, SSD):
  Chỉ dùng để hiểu order-of-magnitude và trade-off. Con số thật phụ thuộc record size,
  key distribution, client concurrency, replication factor, disk, network, TLS, quota,
  compaction, retention và workload của broker.

  PRODUCER:
  ┌────────────────────────────────────────────────────────┐
  │ Config                          │ Throughput  │ Latency │
  │                                 │ (records/s) │ (p99)   │
  ├─────────────────────────────────┼────────────┼─────────┤
  │ Default (linger=0, no compress) │ 50K        │ 5ms     │
  │ linger=5, lz4                   │ 200K       │ 12ms    │
  │ linger=50, zstd, batch=128KB    │ 500K       │ 80ms    │
  │ acks=0, lz4                     │ 800K       │ 1ms     │
  │ acks=all, lz4, 3 replicas      │ 150K       │ 15ms    │
  └─────────────────────────────────┴────────────┴─────────┘
  
  Record size: 500 bytes, 1 topic, 12 partitions

  CONSUMER:
  ┌────────────────────────────────────────────────────────┐
  │ Config                          │ Throughput  │ Latency │
  │                                 │ (records/s) │ (p99)   │
  ├─────────────────────────────────┼────────────┼─────────┤
  │ Default                         │ 100K       │ 50ms    │
  │ fetch.min=50KB, max.wait=1s     │ 300K       │ 200ms   │
  │ max.poll.records=2000           │ 250K       │ 100ms   │
  │ 4 consumers, 12 partitions      │ 800K       │ 50ms    │
  └─────────────────────────────────┴────────────┴─────────┘

  KEY TAKEAWAYS:
  - Producer default có thể chưa tối ưu cho throughput, nhưng là baseline để đo
  - linger + compression thường đổi latency lấy throughput; mức đổi phải đo trên workload thật
  - acks=all giảm throughput tùy ISR, replication, network và min.insync.replicas
  - Consumer throughput có thể cao hơn hoặc thấp hơn producer tùy processing logic
  - Scale consumer bị chặn bởi partitions, hot key và bottleneck downstream
```

### Kafka Performance Testing Tools

```
BUILT-IN TOOLS:

  # Producer performance test
  kafka-producer-perf-test \
    --topic perf-test \
    --num-records 1000000 \
    --record-size 500 \
    --throughput -1 \        # unlimited
    --producer-props \
      bootstrap.servers=localhost:9092 \
      acks=all \
      linger.ms=5 \
      batch.size=65536 \
      compression.type=lz4

  # Consumer performance test
  kafka-consumer-perf-test \
    --topic perf-test \
    --bootstrap-server localhost:9092 \
    --messages 1000000 \
    --threads 1

  # End-to-end latency test
  kafka-e2e-latency \
    --broker-list localhost:9092 \
    --topic perf-test \
    --num-messages 10000 \
    --producer-props acks=all \
    --consumer-props group.id=perf-test
```

---

## 8. Hands-on Lab

### 8.1 Setup — Local Benchmark Environment

Đây là **single-broker local benchmark** để quan sát relative impact của config. Không suy diễn thành production capacity và không dùng để kết luận durability. Test durability thật cần tối thiểu 3 brokers, topic RF=3, `min.insync.replicas=2`, rồi chủ động làm ISR shrink/failover.

```yaml
# docker-compose.yml
version: '3.8'
services:
  kafka1:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092,PLAINTEXT_HOST://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka1:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_NUM_PARTITIONS: 12
      KAFKA_LOG_RETENTION_HOURS: 1
      KAFKA_LOG_SEGMENT_BYTES: 107374182
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
      # Tuning parameters to observe
      KAFKA_NUM_NETWORK_THREADS: 3
      KAFKA_NUM_IO_THREADS: 8
      KAFKA_SOCKET_SEND_BUFFER_BYTES: 102400
      KAFKA_SOCKET_RECEIVE_BUFFER_BYTES: 102400
      KAFKA_SOCKET_REQUEST_MAX_BYTES: 104857600
```

```bash
docker compose up -d

# Create test topics
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create --topic perf-test-1p --partitions 1 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic perf-test-4p --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create --topic perf-test-12p --partitions 12 --replication-factor 1
"
```

### 8.2 Benchmark 1: Producer Tuning Impact

```bash
# Baseline: default config (linger=0, no compression)
echo "=== Test 1: Default Config ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1

# Test 2: linger.ms=5
echo "=== Test 2: linger.ms=5 ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=5

# Test 3: linger.ms=5 + lz4 compression
echo "=== Test 3: linger.ms=5 + lz4 ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=5 \
    compression.type=lz4

# Test 4: linger.ms=50 + zstd + batch=128KB
echo "=== Test 4: High Throughput Config ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=50 \
    batch.size=131072 \
    compression.type=zstd

# Test 5: acks=all trên RF=1 (ack-mode impact, KHÔNG phải production durability)
echo "=== Test 5: acks=all on single broker ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=all \
    linger.ms=5 \
    compression.type=lz4

# Compare results:
# Record columns: records/sec, MB/sec, avg latency, max latency, p50, p95, p99
```

### 8.3 Benchmark 2: Consumer Tuning

```bash
# First: produce 500K messages for consumer testing
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-producer-perf-test \
  --topic perf-test-12p \
  --num-records 500000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=localhost:9092 \
    acks=1 \
    linger.ms=5 \
    compression.type=lz4

# Consumer Test 1: Default
echo "=== Consumer Test 1: Default ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-consumer-perf-test \
  --topic perf-test-12p \
  --bootstrap-server localhost:9092 \
  --messages 500000 \
  --group test-consumer-1

# Consumer Test 2: Larger fetch
echo "=== Consumer Test 2: Larger Fetch ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-consumer-perf-test \
  --topic perf-test-12p \
  --bootstrap-server localhost:9092 \
  --messages 500000 \
  --group test-consumer-2 \
  --fetch-size 1048576

# Consumer Test 3: Multiple threads  
echo "=== Consumer Test 3: Multi-threaded ==="
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-consumer-perf-test \
  --topic perf-test-12p \
  --bootstrap-server localhost:9092 \
  --messages 500000 \
  --group test-consumer-3 \
  --threads 4
```

### 8.4 Benchmark 3: Partition Count Impact

```bash
# Test with 1, 4, 12 partitions (keeping total records same)

for partitions in 1 4 12; do
  echo "=== Partitions: $partitions ==="
  docker exec -it $(docker ps -q -f name=kafka) \
    kafka-producer-perf-test \
    --topic perf-test-${partitions}p \
    --num-records 100000 \
    --record-size 500 \
    --throughput -1 \
    --producer-props \
      bootstrap.servers=localhost:9092 \
      acks=1 \
      linger.ms=5 \
      compression.type=lz4
done

# Expected pattern:
# 1 partition:  limited by single partition throughput
# 4 partitions: ~3-4x improvement
# 12 partitions: ~8-10x improvement (diminishing returns)
```

### 8.5 Java Producer Benchmark (Programmatic)

```java
// src/main/java/com/example/perf/ProducerBenchmark.java
package com.example.perf;

import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.serialization.StringSerializer;

import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicLong;

public class ProducerBenchmark {

    record BenchmarkConfig(String name, int lingerMs, int batchSize, 
                           String compression, String acks) {}

    public static void main(String[] args) throws Exception {
        String topic = "perf-test-12p";
        int numRecords = 100_000;
        int recordSize = 500;

        List<BenchmarkConfig> configs = List.of(
            new BenchmarkConfig("Default", 0, 16384, "none", "1"),
            new BenchmarkConfig("Linger5", 5, 16384, "none", "1"),
            new BenchmarkConfig("Linger5+LZ4", 5, 65536, "lz4", "1"),
            new BenchmarkConfig("HighThroughput", 50, 131072, "zstd", "1"),
            new BenchmarkConfig("Durable", 5, 65536, "lz4", "all")
        );

        String payload = "x".repeat(recordSize);

        System.out.printf("%-20s %12s %12s %12s %12s%n",
            "Config", "Records/s", "MB/s", "Avg(ms)", "P99(ms)");
        System.out.println("─".repeat(80));

        for (BenchmarkConfig config : configs) {
            Properties props = new Properties();
            props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
            props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
            props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
            props.put(ProducerConfig.LINGER_MS_CONFIG, config.lingerMs);
            props.put(ProducerConfig.BATCH_SIZE_CONFIG, config.batchSize);
            props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, config.compression);
            props.put(ProducerConfig.ACKS_CONFIG, config.acks);
            props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "all".equals(config.acks));

            AtomicLong totalLatency = new AtomicLong(0);
            List<Long> latencies = Collections.synchronizedList(new ArrayList<>());
            CountDownLatch latch = new CountDownLatch(numRecords);

            long startTime = System.currentTimeMillis();

            try (Producer<String, String> producer = new KafkaProducer<>(props)) {
                for (int i = 0; i < numRecords; i++) {
                    long sendStart = System.currentTimeMillis();
                    producer.send(
                        new ProducerRecord<>(topic, "key-" + (i % 1000), payload),
                        (metadata, exception) -> {
                            long latency = System.currentTimeMillis() - sendStart;
                            totalLatency.addAndGet(latency);
                            latencies.add(latency);
                            latch.countDown();
                        });
                }
                producer.flush();
                latch.await();
            }

            long elapsed = System.currentTimeMillis() - startTime;
            double recordsPerSec = numRecords * 1000.0 / elapsed;
            double mbPerSec = recordsPerSec * recordSize / (1024.0 * 1024.0);
            double avgLatency = totalLatency.get() / (double) numRecords;

            Collections.sort(latencies);
            long p99 = latencies.get((int)(latencies.size() * 0.99));

            System.out.printf("%-20s %,12.0f %12.1f %12.1f %12d%n",
                config.name, recordsPerSec, mbPerSec, avgLatency, p99);

            Thread.sleep(2000); // cooldown between tests
        }
    }
}
```

### 8.6 Run Benchmarks

```bash
# Option 1: CLI benchmarks (quick, inside Docker)
# Run each Test section above one by one

# Option 2: Java benchmark (more accurate, from host)
cd kafka-streams-lab
./gradlew run -PmainClass=com.example.perf.ProducerBenchmark

# Expected output (numbers vary by hardware):
# Config               Records/s         MB/s      Avg(ms)      P99(ms)
# ────────────────────────────────────────────────────────────────────────
# Default                  25,000          11.9          3.2           15
# Linger5                  85,000          40.5          1.1            8
# Linger5+LZ4             120,000          57.2          0.8            5
# HighThroughput          180,000          85.8          2.5           25
# Durable                  60,000          28.6          5.1           22
```

### 8.7 Monitor During Benchmark

```bash
# Terminal mới: monitor Kafka broker metrics

# CPU & Memory
docker stats $(docker ps -q -f name=kafka)

# Disk I/O (inside container)
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  # Check log segment sizes
  du -sh /var/lib/kafka/data/perf-test-12p-*
  echo '---'
  # List segments
  ls -la /var/lib/kafka/data/perf-test-12p-0/
"

# Topic describe (check partition count, ISR)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-topics --bootstrap-server localhost:9092 \
  --describe --topic perf-test-12p

# Consumer group lag
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --group test-consumer-1
```

### 8.8 Failure Drills — Khi tuning chạm giới hạn

```bash
# Drill 1: Producer buffer full
# Mục tiêu: thấy producer bị block/timeout khi broker chậm hoặc throughput vượt khả năng gửi.
# Cách làm an toàn trong lab: giảm buffer.memory và max.block.ms trong Java benchmark:
#   buffer.memory=1048576
#   max.block.ms=1000
# Expected: TimeoutException/BufferExhausted; fix bằng backpressure, giảm throughput, tăng buffer có kiểm soát.

# Drill 2: Consumer vượt max.poll.interval.ms
# Tăng processing delay trong consumer giả lập để:
#   processing_time_per_record * max.poll.records > max.poll.interval.ms
# Expected: consumer bị remove khỏi group, rebalance; fix bằng giảm max.poll.records hoặc tách xử lý async có pause/resume.

# Drill 3: ISR shrink với acks=all
# Single-broker lab không chứng minh durability. Với optional 3-broker topic:
#   replication-factor=3, min.insync.replicas=2, producer acks=all
# Stop 2 brokers để ISR còn 1.
# Expected: producer fail với NotEnoughReplicas/NotEnoughReplicasAfterAppend thay vì silently accept write.
```

### 8.9 Optional — 3-Broker Compose cho durability benchmark

Single-broker lab phía trên chỉ đo relative throughput/latency. Dùng compose này khi muốn benchmark `acks=all`, RF=3, `min.insync.replicas=2` và failure drill ISR shrink.

```yaml
# docker-compose-3-brokers.yml
version: '3.8'
services:
  kafka1:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:29093,2@kafka2:29093,3@kafka3:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092,PLAINTEXT_HOST://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka1:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
      KAFKA_MIN_INSYNC_REPLICAS: 2
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"

  kafka2:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 2
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:29093,2@kafka2:29093,3@kafka3:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka2:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
      KAFKA_MIN_INSYNC_REPLICAS: 2
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"

  kafka3:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_NODE_ID: 3
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:29093,2@kafka2:29093,3@kafka3:29093"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENERS: CONTROLLER://0.0.0.0:29093,PLAINTEXT://0.0.0.0:29092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka3:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
      KAFKA_MIN_INSYNC_REPLICAS: 2
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
```

```bash
docker compose -f docker-compose-3-brokers.yml up -d

docker exec -it $(docker ps -q -f name=kafka1) \
  kafka-topics --bootstrap-server kafka1:29092 \
  --create --topic perf-durable \
  --partitions 12 --replication-factor 3 \
  --config min.insync.replicas=2

docker exec -it $(docker ps -q -f name=kafka1) \
  kafka-producer-perf-test \
  --topic perf-durable \
  --num-records 100000 \
  --record-size 500 \
  --throughput -1 \
  --producer-props \
    bootstrap.servers=kafka1:29092 \
    acks=all \
    linger.ms=5 \
    compression.type=lz4

# Failure drill: stop two brokers, then rerun producer test.
docker stop $(docker ps -q -f name=kafka2)
docker stop $(docker ps -q -f name=kafka3)
# Expected: producer fails because ISR < min.insync.replicas.
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **Producer có linger.ms=0, batch.size=16KB. Mỗi record 200 bytes. Trung bình batch chứa bao nhiêu records? Tại sao throughput thấp?**
   - Hint: linger.ms=0 → gửi ngay khi có record → batch chỉ có 1 record.

2. **Server 32GB RAM chạy Kafka broker. Bạn set KAFKA_HEAP_OPTS="-Xmx24g". Tại sao performance LẠI GIẢM?**
   - Hint: 32GB - 24GB (heap) = 8GB cho OS + page cache. Kafka data ở page cache, không ở heap.

3. **Consumer xử lý mỗi record mất 20ms. max.poll.records=1000, max.poll.interval.ms=300000. Có vấn đề gì?**
   - Hint: 1000 × 20ms = 20,000ms = 20s < 300s → OK. Nhưng nếu processing tăng lên 50ms?

4. **Compression type=gzip cho producer. Throughput giảm so với không compress. Tại sao? Bạn sẽ thử LZ4/Zstd/none theo tiêu chí nào?**
   - Hint: GZIP CPU-intensive; chọn theo CPU headroom, network bottleneck, record size và p99 latency.

5. **Broker có num.network.threads=3, num.io.threads=8. Traffic tăng 3x → request queue đầy. Tăng parameter nào?**
   - Hint: network threads handle connections, I/O threads handle disk. Check bottleneck ở đâu.

6. **acks=all, 3 replicas, min.insync.replicas=2. 1 broker chết. Producer có gửi được không?**
   - Hint: ISR còn 2 = min.insync.replicas → OK. Nếu 2 brokers chết → ISR=1 < min.insync → Producer fail.

7. **vm.swappiness=60 (default). Kafka đang process 100K msg/s. Đột nhiên latency spike 500ms. Nguyên nhân?**
   - Hint: OS swap Kafka pages to disk → page fault → disk read (random!) → latency spike.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Producer Configs](https://kafka.apache.org/documentation/#producerconfigs)
- [Kafka Consumer Configs](https://kafka.apache.org/documentation/#consumerconfigs)
- [Kafka Broker Configs](https://kafka.apache.org/documentation/#brokerconfigs)
- [Kafka Operations — Production](https://kafka.apache.org/documentation/#operations)

### Blog Posts & Articles
- [Confluent — Optimizing Kafka Producers](https://www.confluent.io/blog/configure-kafka-to-minimize-latency/)
- [Confluent — Kafka Performance Tuning](https://docs.confluent.io/platform/current/kafka/post-deployment.html)
- [LinkedIn — Kafka at Scale](https://engineering.linkedin.com/kafka/benchmarking-apache-kafka-2-million-writes-second-three-cheap-machines)
- [Uber — Kafka Performance at Scale](https://www.uber.com/blog/kafka/)
- [CloudKarafka — Kafka Performance](https://www.cloudkarafka.com/blog/part1-kafka-for-beginners-what-is-apache-kafka.html)

### Videos & Talks
- [Kafka Summit — Performance Tuning](https://www.confluent.io/events/kafka-summit/)
- [GOTO — Apache Kafka and the Rise of the Streaming Platform](https://www.youtube.com/results?search_query=kafka+performance+tuning)
- [Confluent Developer — Producer Performance](https://developer.confluent.io/courses/)
