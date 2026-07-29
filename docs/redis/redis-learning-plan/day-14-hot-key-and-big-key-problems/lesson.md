# Day 14: Hot Key & Big Key Problems

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân biệt được hot key và big key — hai problem class khác nhau nhưng thường đi cùng nhau trong production.
- Sử dụng `redis-cli --hotkeys`, `--bigkeys`, `--memkeys`, `OBJECT FREQ`, `MEMORY USAGE`, `SCAN` để detect hot/big key trước khi chúng gây incident.
- Thiết kế data model phòng ngừa hot key (key splitting, local cache, request coalescing) và big key (chunking, UNLINK, data refactoring).
- Phân tích trade-off giữa các mitigation strategy: split vs read complexity, local cache vs consistency, replica read vs stale data, chunking vs operational overhead — và chọn đúng scenario.
- Tránh các anti-pattern phổ biến: DEL big key trong sync code path, KEYS * trên production, MGET với oversized values.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: DEL One Leaderboard Key -> Latency p99 từ 2ms lên 80s

Một team dùng Sorted Set 1.2 triệu members làm leaderboard. Key size ~220MB. Mỗi tuần reset leaderboard — dev gọi `DEL leaderboard:weekly`. DEL là command **synchronous**, O(N) với N = 1.2M elements. Redis event loop bị block ~250-400ms. Trong thời gian đó, tất cả 15K ops/sec đổ vào Redis đều xếp hàng. Latency p99 tăng từ 2ms lên 80s. 5 phút sau, Hystrix circuit breaker open → service unavailable → 2 giờ incident.

Sai lầm: gọi DEL trên big key mà không có mitigation.

### Incident 2: Hot Session Key Chiếm 40% CPU Redis

Một e-commerce flash sale có 200K concurrent users. Tất cả đều check session tại key `session:global:flash_sale` — một Hash 50KB. 200K req/sec đổ vào đúng 1 key duy nhất. Redis single-threaded xử lý tuần tự: mỗi HGET tốn ~0.05ms, nhưng với 200K req/sec, queue backlog = 200K × 0.05ms = 10 giây. CPU Redis single-core 100%. Latency p99 = 10 giây. Thực tế: latency tăng từ 1ms lên 8s.

Không ai phát hiện hot key cho đến khi load test.

### Incident 3: Big Key Replication -> Replica Lag 30 Phút

Một analytics system lưu daily aggregates vào Redis List với 10 triệu entries (key size ~800MB). Khi promotion replica, full sync phải transfer 800MB qua network. Replication backlog overflow → full sync lại → replica lag 30 phút. Trong thời gian đó, tất cả read replica traffic đổ vào master → master overload.

**Bottom line**: Hot key và big key là hai vấn đề "quiet killers" — không crash Redis ngay, nhưng tích lũy cho đến khi gây incident lớn. Không có monitoring per-key, bạn sẽ không biết mình đang có vấn đề cho đến khi quá muộn.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model, event loop (Day 1)
- Data structures: String, Hash, List, Set, Sorted Set — Big O operation (Day 2)
- Encoding internals: quicklist, listpack, hashtable, intset, skiplist (Day 5)
- Eviction policy: LRU, LFU, volatile vs allkeys (Day 8)
- Connection pooling và client behavior (Day 12)
- Đặc biệt: `maxmemory-policy` phải là `allkeys-lfu` hoặc `volatile-lfu` thì `--hotkeys` mới hoạt động

---

## 4. Lý thuyết chi tiết

### 4.1. Định nghĩa

**Hot key**: Key có tần suất truy cập cao bất thường so với phần còn lại của keyspace. Một cách định nghĩa thực tế: key chiếm >10% total ops/sec của một Redis instance.

**Big key**: Key có size/element count vượt ngưỡng cảnh báo:

| Type | Warning Threshold | Danger Threshold |
|---|---|---|
| String | >10KB | >100KB |
| Hash | >1,000 fields | >10,000 fields |
| List | >5,000 elements | >50,000 elements |
| Set | >5,000 members | >50,000 members |
| Sorted Set | >5,000 elements | >50,000 elements |
| Zset | >5,000 elements | >50,000 elements |

> Lưu ý: Đây là ngưỡng "reasonable" — trong thực tế, bất kỳ key nào gây operational pain đều là big key.

### 4.2. Tại sao Hot Key Đau ở Redis Single-Threaded

Redis xử lý commands tuần tự trên một event loop. Mỗi command phải chờ tất cả commands trước nó hoàn thành.

```txt
Hot key scenario - NO sharding:

  Time ->
  [req1: GET hot:counter  ] [req2: GET hot:counter] [req3: GET hot:counter] ...
  [========================= req1 done (0.05ms) =========================]
  [ req2 waits 0.05ms ][ req2 done (0.05ms) ]...
  [ req3 waits 0.10ms ]...

  200K req/sec × 0.05ms = 10,000ms queue backlog
  Latency p99 = 10 seconds

  CPU: single core 100%, other cores idle
  Network: saturated inbound on this Redis
```

**Core problem**: Hot key tạo ra serialization bottleneck. Tất cả clients竞争 một resource duy nhất (event loop). Với 1ms per operation, 10K ops/sec = queue backlog 10ms. Với 200K ops/sec vào cùng 1 key, backlog = 200ms. Với Redis event loop resolution ~0.05ms, đây là mức độ nghiêm trọng.

**Bandwidth saturation**: Giả sử hot key là String 50KB. 10K req/sec × 50KB = 500MB/s inbound bandwidth. Một 1Gbps NIC có throughput thực ~950Mbps sau overhead → saturation point. TCP buffer full → packet drop → retransmission → latency spike.

### 4.3. Tại sao Big Key Đau

Big key gây ra nhiều vấn đề khác nhau:

#### Blocking DEL — O(N) Synchronous Free

```txt
DEL <big_key>

Redis event loop:
  1. Mark key as deleted (immediate)
  2. Traverse internal data structure
  3. Free every element one by one
  4. Update metadata

Time complexity: O(N) where N = number of elements

Example:
  DEL sorted_set:leaderboard:2024  (1.2M members)
  = O(1,200,000)
  ≈ 250-400ms blocking

During blocking:
  - ALL other commands wait
  - Connection queues grow
  - Client timeouts fire
  - Circuit breakers open
  - Cascading failures begin
```

#### Memory Fragmentation

Big key thường được overwrite/update nhiều lần:

```txt
Key: session:user12345
  Initial write:  50KB String (jemalloc allocates 64KB chunk)
  Update 1:       55KB (jemalloc allocates 80KB chunk, old 64KB freed → hole)
  Update 2:       48KB (uses existing 80KB chunk, 32KB wasted)

Result:
  - Used memory: 55KB
  - Allocated memory: 80KB
  - Fragmentation ratio: 80/55 = 1.45 (>1.4 is concerning)
  - jemalloc can't easily merge holes
```

Active defragmentation có thể help, nhưng với big keys liên tục updated, defrag overhead lớn.

#### Network Packet Size

Một String 1MB tạo ra:

- TCP packet ~1500 bytes MTU → cần ~700 packets cho 1 value
- TCP congestion window ramp-up → bandwidth utilization thấp ban đầu
- Nếu packet bị loss → retransmit toàn bộ 1MB
- Client read buffer phải accumulate toàn bộ response trước khi xử lý

```txt
1MB value transfer over 1Gbps LAN:
  Theoretical time:  1MB / 125MB/s = 8ms
  Actual time:       ~15-20ms (TCP overhead, congestion control)
  With packet loss:  ~50-100ms (exponential backoff)
```

#### Replication Impact

Full sync phải transfer toàn bộ big key qua network:

```txt
Big key: 500MB Sorted Set

Full sync:
  1. Master forks background process
  2. COW copies all key data including the 500MB key
  3. RDB transfer to replica: 500MB / 100Mbps = 40 seconds
  4. Replica loads RDB: another 40 seconds
  5. Total replica lag: ~80 seconds minimum

Partial sync won't help if backlog overflows.
```

### 4.4. Internals: Lazyfree, UNLINK, and Big Object Overhead

**DEL (synchronous)**:
```txt
void delCommand(client *c) {
    deleteKey(c->db, c->argv[1]);
    // Deletes synchronously, O(N) for collections
}
```

**UNLINK (async, Redis 4.0+)**:
```txt
void unlinkCommand(client *c) {
    dbAsyncDelete(c->db, c->argv[1]);
    // Marks key as deleted immediately
    // Schedules actual memory free in bio.c background thread
}
```

```txt
DEL vs UNLINK timeline:

DEL:
  Time 0ms:    delCommand() starts
  Time 250ms:  1.2M elements freed
  Time 250ms:  Event loop unblocks ← BLOCKING HERE
  Time 251ms:  Next command executes

UNLINK:
  Time 0ms:    unlinkCommand() starts
  Time 1ms:    Key marked deleted, bg thread scheduled
  Time 1ms:    Event loop continues ← NO BLOCKING
  Time 250ms:  Background thread frees memory (off main loop)
```

**UNLINK threshold**: Redis chỉ dùng async free khi key có >64个小对象 (theo `lazyfree_lazy_server_del` config). Keys nhỏ vẫn free đồng bộ.

**LAZY EXPIRATION**: Khi key expired được accessed, Redis gọi `lazyfree` để free. Nếu có nhiều expired keys cùng lúc (ví dụ: TTL cluster expire event), đây là nguồn latency spike.

### 4.5. ASCII Diagram: Hot Key vs Distributed Load

```txt
PROBLEM: Hot key concentrated on single Redis shard

┌─────────────────────────────────────────────────────────────┐
│  Client Pool (200K concurrent users)                       │
│    ↓ 200K req/sec                                           │
│  ┌──────────────┐                                           │
│  │  Redis       │  hot_key:session (Hash, 50KB)             │
│  │  Single      │  [========================]               │
│  │  Thread      │  CPU: 100% single-core                    │
│  │  Event Loop  │  Queue: 10,000 pending commands            │
│  └──────────────┘  Latency p99: 8,000ms                     │
│      ↑                                                         │
│      │  ALL traffic                                          │
└─────────────────────────────────────────────────────────────┘

SOLUTION 1: Key Splitting (shard hot key)

┌──────────────────────────────────────────────────────────────┐
│  Client Pool (200K users)                                    │
│    ↓ hash(user_id) → pick shard                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Redis Shard1 │  │ Redis Shard2 │  │ Redis ShardN │       │
│  │ hot:session  │  │ hot:session  │  │ hot:session  │       │
│  │ :0000-:1999  │  │ :2000-:3999  │  │ :98000-:99999│       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│      ↓                   ↓                   ↓                │
│  40K req/sec        40K req/sec        40K req/sec           │
│  CPU: 20%           CPU: 20%           CPU: 20%             │
│  Latency p99: 5ms   Latency p99: 5ms  Latency p99: 5ms     │
└──────────────────────────────────────────────────────────────┘

SOLUTION 2: Local Cache + Request Coalescing

┌──────────────────────────────────────────────────────────────┐
│  App Instance                                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  In-process LRU cache (100 entries, TTL 5s)        │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │ Local cache hit → return immediately        │   │    │
│  │  │ Local cache miss → single-flight to Redis  │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Before: 200K req/sec → Redis                               │
│  After:  200K local hits (100 entries × 5s TTL = 500s coverage) │
│          + 200 req/sec coalesced → Redis (1% original)      │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Trade-off Analysis

### 5.1. Hot Key Mitigation Strategies

| Strategy | Ưu điểm | Nhược điểm | Nên dùng khi | Không nên dùng khi |
|---|---|---|---|---|
| **Key Splitting (sharding)** | Giảm pressure trên từng key; scale throughput khi shards nằm trên Redis Cluster/nhiều nodes | Read complexity tăng (phải aggregate N keys), không tăng tuyến tính trên một Redis standalone, operational overhead cao hơn | Hot key là counter, session, rate limit bucket có thể phân vùng và có path scale-out | Cần atomic operations trên toàn bộ data, cross-key transactions, hoặc chỉ có một standalone node và bottleneck là event loop |
| **Local Cache (L1)** | Latency thấp nhất (0ms network), giảm Redis load đáng kể | Consistency chậm (stale data up to TTL), memory overhead tại app layer, cache invalidation phức tạp | Read-heavy, có thể chịu stale, hot read paths | Write-heavy, strict consistency yêu cầu, multi-instance invalidation khó |
| **Request Coalescing (single-flight)** | Chống thundering herd, đơn giản implement | Không giảm total load, chỉ giảm concurrent requests | Cache miss spike (many requests cùng expired), background refresh | Write-heavy scenarios, đã có local cache |
| **Read Replica** | Giảm load master, đơn giản | Stale data (replication lag), thêm cost cho replica, lag tăng khi write spike | Read-heavy workloads, có thể chịu stale | Write-heavy, strict consistency yêu cầu, hot key trên write path |
| **Probabilistic Cache Refresh** | Không cần external invalidation, continuous refresh | Có stale data window, extra Redis reads, complex tuning | Read-heavy với acceptable staleness, cache warming | Strict consistency, write-heavy, latency-sensitive paths |

### 5.2. Big Key Mitigation Strategies

| Strategy | Ưu điểm | Nhược điểm | Nên dùng khi | Không nên dùng khi |
|---|---|---|---|---|
| **Data Chunking** | Giảm blocking time, parallel processing, network packet nhỏ | Operational complexity (scan N keys thay vì 1), cross-chunk queries khó, key count tăng | Big List, Hash với sequential access, sorted set với range queries | Random access patterns, key có cross-reference, atomic operations trên toàn bộ set |
| **UNLINK thay DEL** | Blocking ~1ms thay vì 250ms+, đơn giản thay đổi code | Memory tạm thời tăng (key space đã free nhưng memory chưa trả về OS), background thread overhead | Bất kỳ deletion trên collection >1K elements | String keys nhỏ (DEL đã đủ nhanh), memory pressure nghiêm trọng |
| **Lazy Expiration Tuning** | Giảm active expiration overhead, latency smooth hơn | Expired keys tồn tại lâu hơn trong memory (nhưng không accessible) | Phát hiện latency spike do mass expiration | Compliance/regulatory yêu cầu strict TTL |
| **Hash Subkeys** | Hot fields accessible nhanh, cold fields tách biệt | Extra keys, JOIN logic phức tạp hơn | Hot data và cold data trong cùng Hash, profile với rarely-accessed metadata | Flat data model, atomic operations cần trên toàn bộ object |

### 5.3. Key Splitting vs Read Complexity

```txt
No splitting (single key):
  GET counter:flash_sale
  → 1 Redis round-trip, 0.05ms

With splitting (N=10 shards):
  shard = hash(counter_key) % 10
  // For counter: need atomic increment
  INCR counter:flash_sale:shard_{shard}
  // For total: need to sum all shards
  MGET counter:flash_sale:shard_0 counter:flash_sale:shard_1 ... counter:flash_sale:shard_9
  // = 10 Redis round-trips (pipelined = 1 RTT)
  // BUT: pipelined MGET still processes 10 keys sequentially
  // Latency: pipelined MGET 10 keys × 0.05ms = 0.5ms

Trade-off:
  - Simple read: 0.05ms
  - Sharded read (pipelined): 0.5ms (10× slower on latency)
  - BUT: without sharding at 200K req/sec → p99 = 10,000ms
  - WITH sharding at 20K req/sec per shard → p99 = 5ms

  CONCLUSION: Throughput wins over per-request latency
```

---

## 6. Best Solution & Best Practices

### 6.1. Theo Scenario

**Scenario: E-commerce flash sale (hot counter)**

```txt
Problem: 200K users, 1 hot counter key

Best solution:
  1. Key splitting: counter:{product_id}:{shard_id} với N=100 shards
  2. Write: INCR counter:P12345:shard_{hash(user_id) % 100}
  3. Read: sum = 0; pipeline(MGET all shards) → sum / 100K (for rate display)
  4. Local cache: LRU cache 100 entries, TTL 2s (stale acceptable for rate display)
  5. Read replica: đọc tổng từ replica để giảm master load

Trade-off chấp nhận:
  - Read latency tăng (pipelined MGET)
  - Eventual consistency (replica lag)
  - Code complexity tăng
```

**Scenario: Leaderboard 1M users (big sorted set)**

```txt
Problem: ZSET 1.2M members, 100MB, thường xuyên DEL

Best solution:
  1. Chunking: 10 buckets × 120K members
     leaderboard:weekly:bucket_0 ... leaderboard:weekly:bucket_9
  2. Top-K read: scan all buckets, merge-sort, take top K
     (10 × ZREVRANGE bucket_0 K) pipelined → 1 RTT
  3. DELETE: UNLINK thay DEL, hoặc drop entire bucket approach
  4. Alternative: dùng separate smaller ZSETs với TTL auto-expiry

Trade-off chấp nhận:
  - Top-K cross-bucket phức tạp
  - Merging overhead
  - Bucket boundary skew (top K might be spread across buckets)
```

**Scenario: Session store (hot Hash)**

```txt
Problem: session:global hot key được access bởi 50K req/sec

Best solution:
  1. Key splitting: session:{user_id} — mỗi user có key riêng
     (session per user = 50K keys × 1KB = 50MB spread evenly)
  2. Local cache at API gateway: LRU 1000 entries, TTL 60s
  3. Read replica: đọc session từ replica

Trade-off chấp nhận:
  - Multiple keys thay vì 1 global key
  - Key explosion nếu không có TTL
  - Complex invalidation khi session update
```

### 6.2. Anti-patterns

- **Không bao giờ** gọi `KEYS *` trên production — scan production data với `SCAN`.
- **Không bao giờ** gọi `DEL` trên big key trong sync code path.
- **Không bao giờ** dùng `SMEMBERS` hoặc `LRANGE 0 -1` trên big collections.
- **Không bao giờ** `MGET` với nhiều big values cùng lúc mà không pipeline.
- **Không bao giờ** đánh giá hot key bằng "feel" — luôn dùng data.
- **Không bao giờ** ignore `--bigkeys` output trong health check.

---

## 7. Performance Considerations

### 7.1. Số liệu minh họa

```txt
DEL performance (synchronous):
  String 100KB:         ~0.1ms
  String 10MB:          ~8ms
  List 10K elements:    ~5ms
  List 1M elements:     ~250-400ms
  Sorted Set 1M members: ~300-500ms

UNLINK performance (async):
  Any size:             ~0.5-1ms (background free)
  Background thread:    Frees ~50-100MB/s depending on allocator

Network transfer:
  1MB String:           ~15-20ms over 1Gbps LAN
  100MB key:            ~1.5-2 seconds over 1Gbps LAN

Hot key serialization cost (1ms per operation):
  1K req/sec single key:   Queue backlog = 1ms (acceptable)
  10K req/sec single key:   Queue backlog = 10ms (warning)
  100K req/sec single key:  Queue backlog = 100ms (critical)
  200K req/sec single key:  Queue backlog = 200ms → timeouts

Replication full sync:
  500MB key:             ~40-80 seconds transfer
  1GB keyspace:         ~2-4 minutes transfer

Memory fragmentation from big keys:
  jemalloc overhead:    10-20% per chunk
  Update pattern:       30-50% waste from fragmentation
  Active defrag cost:   ~5-10% CPU overhead
```

### 7.2. Big O

| Operation | String | List | Hash | Set | Sorted Set |
|---|---|---|---|---|---|
| DEL | O(M) where M = value bytes | O(N) elements | O(N) fields | O(N) members | O(N) members |
| GET/SET | O(1) | - | - | - | - |
| HGET/HSET | - | - | O(1) avg | - | - |
| LRANGE | - | O(S+N) start+count | - | - | - |
| ZRANGE | - | - | - | - | O(log N + M) |
| MEMORY USAGE | O(1) | O(1)* | O(1)* | O(1)* | O(1)* |

> *MEMORY USAGE có thể trigger sampling internals nếu object lớn, nhưng command response time không tăng đáng kể.

---

## 8. Production Failure Modes

### 8.1. Hot Key Failures

**Failure: CPU single-core 100%, latency spike không rõ nguyên nhân**

```txt
Symptom:
  - Redis CPU 100% (single core), other cores idle
  - Latency p99 tăng đột ngột
  - ops/sec không tăng tương ứng với CPU

Diagnosis:
  1. redis-cli INFO stats | grep -E "instantaneous_ops|total_commands"
  2. redis-cli --hotkeys (nếu maxmemory-policy = allkeys-lfu)
  3. redis-cli MONITOR | head -100 (brief sample, not production-long)
  4. Client-side: log per-key hit rate

Root cause thường gặp:
  - Global counter không sharded
  - Session key tập trung vào 1 key
  - Cache warming miss spike
  - Rate limit bucket = 1 key cho toàn bộ system
```

### 8.2. Big Key Failures

**Failure: Latency spike cứ sau vài phút, kéo dài 200-400ms**

```txt
Symptom:
  - Periodic latency spike (thay vì random)
  - Spike duration tương đương với delete/update big operation
  - Memory usage giảm đột ngột sau spike

Diagnosis:
  1. redis-cli SLOWLOG GET 10
  2. redis-cli --bigkeys (premium scan)
  3. redis-cli KEYS "*" | xargs -I{} redis-cli MEMORY USAGE "{}" | sort -rn | head -20
  4. Check cron jobs / scheduled tasks that might delete/update big keys

Root cause thường gặp:
  - DEL called on big key trong request path
  - LRANGE 0 -1 on big List
  - UNPACK trên big Hash
  - Scheduled job reset big sorted set
```

**Failure: Replication lag tăng liên tục, replica không bao giờ catch up**

```txt
Symptom:
  - replica_log_space_in_bytes tăng liên tục
  - Master-replica lag > 30 seconds
  - Replica status: connected nhưng data behind

Diagnosis:
  1. redis-cli INFO replication (check master_repl_offset vs slave_repl_offset)
  2. Check big key list: redis-cli --bigkeys
  3. Monitor network throughput: iftop, nethogs
  4. Check disk I/O on replica (AOF rewrite?)

Root cause:
  - Big key full sync không ngừng
  - Replication backlog overflow → repeated full sync
  - Slow replica (CPU, disk I/O) không theo kịp master write rate
```

### 8.3. Combined Failure

**Failure: Hot key + big key = cascading failure**

```txt
Scenario:
  1. Hot key: session:global (50K req/sec, 50KB Hash)
  2. Big key: analytics:daily (500MB List, 10M entries)
  3. Background job: LRANGE analytics:daily 0 10000 (triggered every 5 minutes)
  4. LRANGE on 500MB List blocks event loop 100ms
  5. session requests queue: 50K × 0.05ms × queue_depth = backlog
  6. Latency p99: 0.05ms → 5,000ms
  7. Client timeouts fire → circuit breaker open
  8. Retry storm → Redis overload
```

---

## 9. Real-world Examples

### 9.1. Twitter/X — Trending Topics (Hot Key)

Twitter dùng Redis Sorted Set cho trending topics. Khi một sự kiện "Breaking News" xảy ra, hàng triệu users cùng refresh trending page. Nếu dùng 1 Sorted Set toàn cục: hot key. Giải pháp: sharding theo region/interest, mỗi shard là một Sorted Set riêng. Top-K trending = merge top-K từ M shards.

### 9.2. Instagram — Celebrity Follower Set (Big Key)

Instagram từng lưu follower list của celebrity accounts (10M+ followers) trong Redis Set. Một Set với 10 triệu members = big key. Problems: SMEMBERS = 10M entries, network transfer = 500MB+, replication lag. Solutions đã áp dụng: hybrid approach, paginated API ( SSCAN thay vì SMEMBERS), denormalized follower count, eventual consistency read replica.

### 9.3. Uber — Surge Zone Hot Key

Uber dùng Redis Hash để track surge multiplier theo zone. Zone "Manhattan Downtown" có thể có 50K drivers cùng check surge. Key `surge:zone:manhattan_downtown` = hot key. Solutions: per-driver cached zone data với local TTL, request coalescing khi cache miss, read replica for surge queries.

### 9.4. Alibaba/Tair — Hot Key Detection và Mitigation

Tair ( Alibaba Cloud Redis compatible) có built-in hot key detection và automatic sharding. Khi hot key phát hiện, tự động split thành N partitions. Public blog của Alibaba có chi tiết về hot key problem và cách họ handle trong production: hot key detection overhead < 1% CPU, automatic sharding transparent to application.

### 9.5. Shopify — Flash Sale Preparation

Shopify merchant chạy flash sale: 50K concurrent users, 1 product có 1000 units. Vấn đề: inventory counter = hot key. Giải pháp trước sale: pre-sharding counter thành 100 shards. During sale: INCR trên random shard. Inventory check: sum all shards. Kết quả: peak 80K INCR/sec, latency p99 < 10ms.

---

## 10. Common Pitfalls

### 10.1. Hot Key Pitfalls

**Pitfall 1: Không monitoring per-key access frequency**

```txt
Sai:
  // "Key design looks fine, let's ship"
  const sessionKey = `session:global:${eventId}`;  // HOT KEY

Đúng:
  // Pre-deployment analysis:
  // 1. Estimate access frequency per key
  // 2. If any key >10% ops/sec → shard
  // 3. Add per-key metrics in client
  const sessionKey = `session:${userId}`;  // Sharded by user
```

**Pitfall 2: Local cache không có invalidation strategy**

```txt
Sai:
  // "Local cache faster, let's cache everything"
  const cache = new LRU({ max: 10000, ttl: 300000 });  // 5 min TTL
  // 5 minutes stale data after user logout → security issue

Đúng:
  // Option 1: Short TTL
  const cache = new LRU({ max: 1000, ttl: 5000 });  // 5s TTL
  // Option 2: Invalidation on write
  cache.delete(`session:${userId}`);  // On logout/update
```

**Pitfall 3: Single-flight implement sai**

```txt
Sai:
  // Race condition in single-flight
  async getData(key) {
    if (cache.has(key)) return cache.get(key);
    const result = await redis.get(key);  // Multiple calls race here
    cache.set(key, result);
    return result;
  }

Đúng:
  const inflight = new Map();
  async function getData(key) {
    if (inflight.has(key)) return inflight.get(key).promise;
    const promise = redis.get(key).then(r => { cache.set(key, r); inflight.delete(key); return r; });
    inflight.set(key, { promise });
    return promise;
  }
```

### 10.2. Big Key Pitfalls

**Pitfall 4: DEL trong request path**

```txt
Sai:
  app.get('/reset-leaderboard', async (req, res) => {
    await redis.del('leaderboard:weekly');  // BLOCKS 300ms
    res.json({ ok: true });
  });

Đúng:
  app.get('/reset-leaderboard', async (req, res) => {
    // Schedule async delete
    await redis.unlink('leaderboard:weekly');  // ~1ms, non-blocking
    // Or better: rename + TTL
    await redis.rename('leaderboard:weekly', `leaderboard:weekly:old:${Date.now()}`);
    await redis.expire(`leaderboard:weekly:old:${Date.now()}`, 3600);
    res.json({ ok: true, message: 'reset scheduled' });
  });
```

**Pitfall 5: SCAN không count, KEYS * trên production**

```txt
Sai:
  // NEVER do this on production
  const keys = await redis.keys('*');  // Blocks, loads all keys into memory

Đúng:
  let cursor = '0';
  const bigKeys = [];
  do {
    const [nextCursor, batch] = await redis.scan(cursor, 'COUNT', 100, 'MATCH', '*');
    cursor = nextCursor;
    for (const key of batch) {
      const info = await redis.object('ENCODING', key);
      if (info === 'ziplist' || info === 'quicklist') {
        const len = await redis.lLen(key);
        if (len > 5000) bigKeys.push({ key, type: 'list', len });
      }
    }
  } while (cursor !== '0');
```

**Pitfall 6: Không có metric per-key**

```txt
Sai:
  // "Everything looks fine" (but you have no per-key visibility)
  // Redis INFO shows total ops/sec, not per-key

Đúng:
  // Client-side: log key access in histogram
  async function redisGet(key) {
    const start = process.hrtime.bigint();
    const result = await client.get(key);
    const ns = Number(process.hrtime.bigint() - start);
    metrics.histogram('redis.get.latency_ns', ns, { key_pattern: categorize(key) });
    metrics.increment('redis.get', { key_pattern: categorize(key) });
    return result;
  }

  // Redis-side: use OBJECT FREQ (requires LFU policy)
  CONFIG SET maxmemory-policy allkeys-lfu
  // Then: OBJECT FREQ hot:counter → access count since LFU init
```

---

## 11. Câu hỏi tự kiểm tra

### Câu 1

**Scenario**: Bạn phát hiện 1 Hash key `product:catalog` có 500,000 fields. Team muốn `HGETALL` để lấy toàn bộ product details. Bạn sẽ xử lý thế nào?

<details>
<summary>Đáp án</summary>

Không bao giờ dùng `HGETALL` trên 500K fields. Approach đúng:

1. **Analysis**: 500K fields = big key → ngưỡng danger.
2. **Chunking**: Tách thành multiple keys theo field category, ví dụ:
   - `product:catalog:base` (name, price, description)
   - `product:catalog:media` (images, videos)
   - `product:catalog:stats` (view_count, sold_count)
3. **Field grouping by access pattern**: hot fields (name, price, image) tách riêng, cold fields (description, long_text) tách riêng.
4. **Alternative**: Dùng JSON String với streaming parse, hoặc denormalize vào separate Redis keys.
5. **Nếu HGETALL bắt buộc**: Dùng ` HSCAN` với `COUNT` parameter để paginate, không blocking.

**Trade-off**: Data model refactoring cost vs operation risk. Nếu operation là one-time migration: acceptable. Nếu là frequent pattern: refactor.

</details>

### Câu 2

**Scenario**: 1 Sorted Set có 2 triệu members dùng làm leaderboard. Mỗi ngày phải reset. Team dùng `DEL` để reset. Incident: mỗi ngày lúc 00:00, latency tăng đến 800ms trong 5 phút. Phân tích và đề xuất solution.

<details>
<summary>Đáp án</summary>

**Root cause**: `DEL` trên ZSET 2M members = O(N) synchronous, tốn ~500ms blocking. Event loop blocked 500ms → all other commands wait → queue backlog → latency spike.

**Solution options**:

1. **UNLINK**: Thay `DEL` bằng `UNLINK` → blocking ~1ms. Memory tạm thời tăng (key đã "deleted" nhưng memory chưa freed). Acceptable nếu memory pressure không cao.

2. **Rename + TTL**: `RENAME leaderboard:daily leaderboard:daily:old:{timestamp}` + `EXPIRE` 1 giờ. Hoàn toàn non-blocking. Key tự động expire sau 1 giờ.

3. **Bucket approach**: Thay vì 1 big ZSET, dùng 10 smaller ZSETs (bucket_0 đến bucket_9). Mỗi bucket 200K members. Top-K = scan all buckets + merge-sort. Reset = drop all buckets (UNLINK N keys nhỏ thay vì 1 key lớn).

4. **Avoid reset**: Dùng ZADD với timestamp score, query bằng ZRANGEBYSCORE với date filter. Không cần delete.

**Recommendation**: Combine UNLINK + rename approach (fastest to implement, minimal code change).

</details>

### Câu 3

**Scenario**: E-commerce flash sale, 100,000 users cùng đọc thông tin sản phẩm từ key `product:flash:P12345` (Hash, 80KB). Latency p99 hiện tại 2s. Giải thích nguyên nhân và đề xuất giải pháp với trade-off.

<details>
<summary>Đáp án</summary>

**Root cause**: Hot key. 100K req/sec vào 1 key = serialization bottleneck. Với mỗi HGET tốn ~0.05ms: queue = 100K × 0.05ms = 5000ms = 5s theoretical backlog. Thực tế: client timeout (2s) fire trước.

**Solutions với trade-off**:

| Solution | Latency improvement | Trade-off |
|---|---|---|
| Key splitting (100 shards) | p99 ~5ms | Read = pipeline MGET 100 keys (1 RTT), code complexity |
| Local cache (LRU, TTL 5s) | p99 ~0.1ms (cache hit) | Stale data up to 5s, invalidation on write |
| Read replica | p99 ~2ms (reduced master load) | Stale data (replication lag), cost |
| CDN/static cache | p99 ~1ms | Stale, invalidation complex |

**Best approach**: Kết hợp local cache (L1) + key splitting (L2). Cache hit = local LRU return. Cache miss = pipeline MGET from sharded keys. Stale acceptable cho product info display.

</details>

### Câu 4

**Scenario**: Bạn phát hiện replica lag 5 phút trên read replica. Replica đang dùng cho reporting queries. Phân tích possible causes.

<details>
<summary>Đáp án</summary>

**Possible causes theo tần suất**:

1. **Big key full sync loop**: Master có big key (>500MB) → full sync → backlog overflow → full sync again. Check: `redis-cli INFO replication` xem `master_repl_offset` vs `slave_repl_offset` gap.

2. **Slow replica**: Replica CPU/Disk I/O bottleneck (AOF rewrite, COW fork). Check: `redis-cli INFO stats` trên replica, `INFO CPU`.

3. **Write spike on master**: Master write rate tăng đột ngột (batch job, ETL), replica không theo kịp. Check: `redis-cli INFO stats` → `total_commands_processed` rate.

4. **Network bottleneck**: Replication bandwidth saturation. Check: NIC throughput, replication buffer size (`repl-backlog-size`).

5. **Big key trong pipeline**: Một application gọi `MSET` với nhiều big values → single write operation lớn block replication. Check: slowlog trên master.

**Fix**: Nếu do big key: chunking big key, dùng UNLINK. Nếu do slow replica: vertical scale replica. Nếu do bandwidth: tăng `repl-backlog-size`, dùng compression (Redis 7.0+).

</details>

### Câu 5

**Scenario**: Bạn muốn detect hot keys trên production. Team gợi ý dùng `MONITOR`. Bạn phản đối. Tại sao và dùng gì thay thế?

<details>
<summary>Đáp án</summary>

**Tại sao KHÔNG dùng MONITOR**:

`MONITOR` output toàn bộ commands đến Redis, log vào buffer. Buffer overflow → commands dropped. Overhead: 30-50% CPU tăng trên Redis server. Trên production với 100K ops/sec: MONITOR output = 100K lines/second → Redis overload.

**Alternatives**:

| Tool | Pros | Cons |
|---|---|---|
| `redis-cli --hotkeys` | Built-in, easy | Cần `maxmemory-policy=allkeys-lfu/volatile-lfu`, sampling-based |
| `redis-cli --bigkeys` | Non-blocking scan | Không detect hot keys, chỉ big keys |
| `redis-cli --memkeys` | Accurate memory-based | Scan nặng, blocking risk |
| `OBJECT FREQ <key>` | Precise LFU count | Phải biết key name trước |
| Client-side metrics | Per-key visibility | Code change required |
| Redis Slowlog | Detect slow commands | Không measure frequency |
| Traffic sampling (proxy/sidecar) | Non-invasive | Extra infrastructure |

**Best practice**: Kết hợp `--bigkeys` (scheduled, weekly) + client-side per-key histogram + `OBJECT FREQ` cho suspected keys.

</details>

### Câu 6

**Scenario**: Một developer viết code: `const result = await redis.get('hot:global:counter'); await redis.del('hot:global:counter');`. Code chạy mỗi 5 giây. Giải thích vấn đề.

<details>
<summary>Đáp án</summary>

**Vấn đề 1**: `DEL` trên Hash/List/Set (nếu counter là collection) → O(N) blocking. Nếu `hot:global:counter` là String incrementing counter → `DEL` sau `GET` là race condition: giữa GET và DEL, another request có thể INCR → lost increment.

**Vấn đề 2**: Logic "GET rồi DEL" không phải atomic. Nếu cần atomic reset: dùng `GETDEL` (Redis 6.2+) hoặc Lua script.

**Vấn đề 3**: Nếu đây là hot key (được access mỗi 5s), và nằm trên main Redis: đây là anti-pattern reset-hot-key-in-loop. Nên dùng `RENAME` + `EXPIRE` thay vì `DEL`.

**Correct approach**:
```typescript
// Atomic reset với rename
const newKey = `counter:${Date.now()}:${randomId()}`;
await redis.rename('hot:global:counter', newKey);
await redis.expire(newKey, 3600); // TTL safety net

// Hoặc dùng GETDEL (Redis 6.2+)
const oldValue = await redis.getdel('hot:global:counter');
```

</details>

### Câu 7

**Scenario**: Bạn có 1 Hash `user:12345` với 50,000 fields. Bạn muốn lấy field thứ 1000 đến 1010. Command nào bạn dùng? Tại sao không dùng `HGETALL`?

<details>
<summary>Đáp án</summary>

**Command**: `HSCAN user:12345 0 MATCH * COUNT 1500` rồi skip fields 0-999, take 1000-1010. Hoặc dùng Lua script để `HSCAN` với cursor-based pagination.

**Tại sao KHÔNG dùng HGETALL**:

1. **Blocking**: `HGETALL` trên 50K fields = O(N) synchronous → block event loop ~50ms.
2. **Memory**: Response = 50K × (field_name + field_value) = ~5MB+ → network saturation, client buffer overflow.
3. **Parsing**: Client phải parse 5MB JSON/MessagePack → CPU spike.
4. **TTL**: Nếu key expired trong lúc HGETALL → empty result nhưng vẫn tốn resource.

**Better design**: Nếu bạn thường xuyên cần range access trên Hash, đây là data model problem. Refactor: dùng List thay vì Hash nếu sequential access, hoặc dùng multiple keys với deterministic naming.

</details>
