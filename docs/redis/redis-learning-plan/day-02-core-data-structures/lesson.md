# Day 2: Core Data Structures

## 1. Mục tiêu bài học

- Phân biệt được String, List, Hash, Set, Sorted Set về use case, Big O và memory footprint
- Chọn đúng data structure cho từng scenario production thực tế
- Tránh được các anti-pattern phổ biến: `SMEMBERS` big set, `LRANGE 0 -1`, `HGETALL` big hash
- Hiểu encoding internals (listpack, quicklist, skiplist, intset) để predict performance và memory
- Đo được memory usage thực tế giữa Hash vs nhiều String keys

---

## 2. Vì sao cần học chủ đề này

### Instagram feed latency spike (2013)

Instagram dùng List làm feed storage. Khi user có 1000+ photos, `LRANGE user:feed 0 -1` trả về 1000 entry, mỗi entry là JSON string ~200 bytes, tổng response ~200KB. Event loop bị block ~8ms cho mỗi request. Với 5000 req/sec, CPU saturation xảy ra không phải do computation mà do single-threaded bị block bởi response serialization.

**Root cause**: Dùng List (queue-style access) cho use case cần random access + pagination.

### Twitter timeline benchmark (Sorted Set vs Database)

- Database query timeline: `SELECT * FROM tweets ORDER BY created_at DESC LIMIT 20` → **200ms p95**
- Redis Sorted Set `ZREVRANGE timeline:user:123 0 19 WITHSCORES` → **0.5ms p95**, 400x nhanh hơn
- Dùng Sorted Set đúng cách, Twitter timeline scale được 300K+ TPS trên 1 node Redis

**Kết luận**: Chọn sai data structure → latency spike có thể nhân 400x. Với hệ thống 100K ops/sec, đây là sự khác biệt giữa 1 node và 10 node.

---

## 3. Kiến thức nền cần có

- Redis là single-threaded event loop
- I/O multiplexing, non-blocking I/O
- Tất cả command đều atomic vì chạy trên single thread
- `INCR` atomic nhưng không phải transaction nếu cần read-modify-write
- Key là binary-safe string, không có schema
- TTL nằm ở key-level, không có per-field TTL

---

## 4. Nội dung lý thuyết từ cơ bản đến chi tiết

### 4.1 String — SDS (Simple Dynamic String)

Redis **không dùng** C char* cho String. Dùng **SDS** (Simple Dynamic String):

```
struct __attribute__((__packed__)) sdshdr64 {
    uint64_t len;      // độ dài string
    uint64_t alloc;    // allocated size
    unsigned char flags;
    char buf[];
}
```

**Tại sao SDS?**

- `strlen`: O(1) qua `len` field, không cần scan
- `APPEND`: O(1) amortized, không cần realloc nếu còn space
- `INCR`/`INCRBY`: O(1), không parse-to-int rồi serialize lại mỗi lần (cóemboxing)
- Binary-safe: `buf[]` chứa raw bytes, không phải null-terminated string

**Commands quan trọng:**

| Command | Syntax | Complexity | Mô tả |
|---------|--------|------------|-------|
| `SET` | `SET key value [NX|XX] [EX seconds|PX ms]` | O(1) | Set string, optionally NX (not exist) hoặc XX (must exist), với TTL |
| `GET` | `GET key` | O(1) | Get string |
| `MGET` | `MGET key [key ...]` | O(N) | Get N keys song song, dùng pipeline |
| `MSET` | `MSET key value [key value ...]` | O(N) | Set N keys |
| `SETRANGE` | `SETRANGE key offset value` | O(1)* | Ghi tại offset, mở rộng string nếu cần |
| `GETRANGE` | `GETRANGE key start end` | O(N) | Substring, N = end-start |
| `APPEND` | `APPEND key value` | O(1) amortized | Nối thêm, tối ưu khi append nhiều lần |
| `INCR`/`INCRBY` | `INCR key`, `INCRBY key delta` | O(1) | Atomic increment, 64-bit signed integer |
| `INCRBYFLOAT` | `INCRBYFLOAT key delta` | O(1) | Atomic float increment |
| `STRLEN` | `STRLEN key` | O(1) | Độ dài string |
| `SETNX` | `SETNX key value` | O(1) | Set if not exists (atomic) |

**Use cases production:**
- Session token: `SET session:abc123 "{...}" EX 3600`
- Counter: page view, rate limit counter
- Cached serialized JSON: `SET product:456 '{"id":456,"name":"..."}'`
- Distributed lock (đơn giản): `SET lock:order:123 uuid NX EX 10`

**Misconception phổ biến**: String value limit là 512MB nhưng thực tế Redis khuyến nghị < 10KB cho cache use case. String > 10KB nên dùng `COMPRESS` ở application layer hoặc chunking.

---

### 4.2 List — Quicklist (Redis 7)

Redis 7 trở lên dùng **quicklist** làm default encoding cho List.

```
quicklist = doubly linked list of ziplists
ziplist = contiguous memory array, compressed
```

**Tại sao quicklist?**

- ziplist compact hơn linked list vì không có pointer overhead
- doubly linked list cho phép O(1) LPUSH/RPUSH ở cả 2 đầu
- ziplist có threshold: nếu list > `list-max-ziplist-size` entries → tự split thành nhiều ziplist node
- Kết quả: **O(1) push/pop ở 2 đầu** + **memory efficient** cho small list

**Encoding thresholds (Redis 7.x):**

| Condition | Encoding |
|-----------|----------|
| list entries < `list-max-ziplist-size` (default 8KB per entry) | ziplist |
| entries vượt threshold hoặc value > 64B | quicklist (linked list of ziplists) |
| list > `list-pack-entries-max-ziplist-size` | listpack |

**Commands quan trọng:**

| Command | Syntax | Complexity | Mô tả |
|---------|--------|------------|-------|
| `LPUSH` | `LPUSH key value [value ...]` | O(1)* | Push vào head |
| `RPUSH` | `RPUSH key value [value ...]` | O(1)* | Push vào tail |
| `LPOP` | `LPOP key [count]` | O(1)* | Pop từ head |
| `RPOP` | `RPOP key [count]` | O(1)* | Pop từ tail |
| `LPUSHX` | `LPUSHX key value` | O(1) | Push chỉ khi key tồn tại |
| `RPUSHX` | `RPUSHX key value` | O(1) | Push chỉ khi key tồn tại |
| `LLEN` | `LLEN key` | O(1) | Số lượng entries |
| `LRANGE` | `LRANGE key start stop` | O(S+M) | S = start offset, M = số elements lấy ra |
| `LINDEX` | `LINDEX key index` | O(N) | Random access by index — KHÔNG dùng cho production |
| `LINSERT` | `LINSERT key BEFORE\|AFTER pivot value` | O(N) | Insert giá trị |
| `LSET` | `LSET key index value` | O(N) | Set giá trị tại index |
| `LTRIM` | `LTRIM key start stop` | O(N) | Trim list, giữ elements trong range |
| `BLPOP` | `BLPOP key [key ...] timeout` | O(1) | Blocking pop từ head |
| `BRPOP` | `BRPOP key [key ...] timeout` | O(1) | Blocking pop từ tail |

`*` = amortized

**Use cases production:**
- Activity stream đơn giản: `LPUSH user:feed:{id} {post_json}` + `LTRIM` giữ 1000 items
- Task queue đơn giản: `LPUSH` jobs, `BRPOP` workers
- Recent history: `LPUSH` viewed items, `LTRIM` giữ 50 items

**Cảnh báo về LRANGE:**
```
LRANGE key 0 -1
```
Nếu list có 1M entries, Redis phải traverse tất cả ziplist nodes, tạo response chứa toàn bộ 1M elements (~500MB). Thread bị block cho toàn bộ serialization time. **Luôn dùng pagination** với `LRANGE key 0 99` thay vì `LRANGE key 0 -1`.

---

### 4.3 Hash — listpack vs hashtable

Hash là container cho multiple field-value pairs trong 1 key.

**Encoding:**

| Condition | Encoding | Threshold |
|-----------|----------|-----------|
| Hash có ≤ `hash-max-listpack-entries` (default 512) fields, mỗi value < `hash-max-listpack-value` (default 128B) | listpack | 512 fields, 128B/value |
| Vượt threshold | hashtable | > 512 fields hoặc value > 128B |

**listpack**: contiguous memory, mỗi entry: `[-][encoded-length][field][encoded-length][value]`. Entry đầu tiên lưu total byte count → delete phải recode toàn bộ.

**hashtable**: standard hash table, separate chaining, mỗi entry có pointer overhead.

**Commands quan trọng:**

| Command | Syntax | Complexity | Mô tả |
|---------|--------|------------|-------|
| `HSET` | `HSET key field value [field value ...]` | O(1) per field | Set field(s) |
| `HGET` | `HGET key field` | O(1) | Get 1 field |
| `HMGET` | `HMGET key field [field ...]` | O(N) | Get N fields |
| `HGETALL` | `HGETALL key` | O(N) | Get ALL fields — cảnh báo với big hash |
| `HSETNX` | `HSETNX key field value` | O(1) | Set if field not exists |
| `HINCRBY` | `HINCRBY key field delta` | O(1) | Atomic increment field |
| `HINCRBYFLOAT` | `HINCRBYFLOAT key field delta` | O(1) | Atomic float increment |
| `HEXISTS` | `HEXISTS key field` | O(1) | Check field exists |
| `HDEL` | `HDEL key field [field ...]` | O(1) per field | Delete field(s) |
| `HLEN` | `HLEN key` | O(1) | Số fields |
| `HSTRLEN` | `HSTRLEN key field` | O(1) | String length của field |
| `HSCAN` | `HSCAN key cursor [MATCH pattern] [COUNT n]` | O(1) per iteration | Iterator — dùng thay HGETALL cho big hash |
| `HRANDFIELD` | `HRANDFIELD key [count [WITHVALUES]]` | O(N) | Random field(s) — Redis 6.2+ |

**Use cases production:**
- User profile cache: `HSET user:123 name "An" email "an@example.com" age 28`
- Object cache: product, session, configuration
- Counter per entity: `HINCRBY stats:product:456 views 1`

**Khi nào dùng Hash thay vì String?**

- Object có ≥ 2 fields mà thường access together → Hash tốt hơn
- Object có fields được update riêng lẻ → Hash tốt hơn (không cần GET+SET full JSON)
- Object chỉ có 1 field hoặc rarely accessed → String JSON cũng được

---

### 4.4 Set — intset vs hashtable

Set lưu **unique, unordered** elements.

**Encoding:**

| Condition | Encoding | Threshold |
|-----------|----------|-----------|
| Tất cả elements là integer và ≤ 512 elements | intset | ≤ 512 integer elements |
| Vượt threshold hoặc có string elements | hashtable | > 512 elements hoặc non-integer |

**intset**: sorted array of integers trong contiguous memory. Binary search → O(log N) cho `SISMEMBER`. Memory cực kỳ efficient (6 bytes/int vs hashtable ~72 bytes/entry overhead).

**Commands quan trọng:**

| Command | Syntax | Complexity | Mô tả |
|---------|--------|------------|-------|
| `SADD` | `SADD key member [member ...]` | O(1) per member | Add members (ignore duplicates) |
| `SREM` | `SREM key member [member ...]` | O(1) per member | Remove members |
| `SISMEMBER` | `SISMEMBER key member` | O(1) | Check membership |
| `SMISMEMBER` | `SMISMEMBER key member [member ...]` | O(N) | Check N memberships |
| `SCARD` | `SCARD key` | O(1) | Số lượng members |
| `SMEMBERS` | `SMEMBERS key` | O(N) | Get ALL members — KHÔNG dùng với big set |
| `SSCAN` | `SSCAN key cursor [MATCH pattern] [COUNT n]` | O(1) per iteration | Iterator thay vì SMEMBERS |
| `SINTER` | `SINTER key [key ...]` | O(N*M) | Intersection — cảnh báo với big sets |
| `SINTERCARD` | `SINTERCARD key [key ...] limit` | O(N*M) | Intersection count với limit |
| `SUNION` | `SUNION key [key ...]` | O(N) | Union |
| `SDIFF` | `SDIFF key [key ...]` | O(N) | Set difference |
| `SRANDMEMBER` | `SRANDMEMBER key [count]` | O(N) | Random members, count > 0 → may repeat |
| `SPOP` | `SPOP key [count]` | O(1) per pop | Remove and return random member |

**SINTER complexity phân tích:**
- 2 sets: 100K + 200K elements → O(100K) (small set scan)
- 2 sets: 10M + 10M elements → O(10M * avg chain length) → **có thể mất vài giây**
- Nếu cần intersection với Set lớn → dùng `SINTERCARD key1 key2 100` để limit computation

**Use cases production:**
- Tag system: `SADD product:tags:electronics iphone samsung headphones`
- Unique visitor tracking: `SADD page:views:2026-05-19 {visitor_id}`
- Follower/following IDs: `SADD user:123:following {user_id}`
- Distributed dedup: `SISMEMBER job:processed {job_id}`

---

### 4.5 Sorted Set — skiplist + hashtable

Sorted Set (ZSET) là cấu trúc phức tạp nhất trong 5 data structures cơ bản.

**Internals: Dual data structure**

```
ZSET = skiplist(score ordered) + hashtable(member → score)
```

```
Level 1 (skiplist node):
┌─────────────────────────────────┐
│  member: "alice"                │
│  score: 1500                    │
│  ↓ next: [bob(1200), carol(1800)]
│  ↓ down: [alice_level0]         │
└─────────────────────────────────┘

Hashtable (O(1) lookup):
"alice" → 1500
"bob"   → 1200
"carol" → 1800
```

**Tại sao dual structure?**

- **skiplist**: ZRANGE, ZRANGEBYSCORE, ZRANK — O(log N + M)
- **hashtable**: ZSCORE lookup bằng member → O(1)
- Nếu chỉ dùng skiplist, `ZSCORE` sẽ là O(N) → không production-ready

**Encoding:**

| Condition | Encoding | Threshold |
|-----------|----------|-----------|
| ≤ 128 items, mỗi member < 64B | listpack-zset | 128 items, 64B member |
| > threshold | skiplist + hashtable | > 128 items |

**Commands quan trọng:**

| Command | Syntax | Complexity | Mô tả |
|---------|--------|------------|-------|
| `ZADD` | `ZADD key score member [score member ...]` | O(log N) per member | Add/update member với score |
| `ZINCRBY` | `ZINCRBY key delta member` | O(log N) | Atomic increment score |
| `ZSCORE` | `ZSCORE key member` | O(1) | Get score của member |
| `ZRANK` | `ZRANK key member` | O(log N) | 0-indexed rank (ascending) |
| `ZREVRANK` | `ZREVRANK key member` | O(log N) | 0-indexed rank (descending) |
| `ZRANGE` | `ZRANGE key min max [BYSCORE\|BYLEX] [REV] [LIMIT offset count] [WITHSCORES]` | O(log N + M) | Range query |
| `ZREVRANGE` | `ZREVRANGE key start stop [WITHSCORES]` | O(log N + M) | Descending range |
| `ZRANGEBYSCORE` | `ZRANGEBYSCORE key min max [WITHSCORES] [LIMIT o c]` | O(log N + M) | Score range query |
| `ZREVRANGEBYSCORE` | `ZREVRANGEBYSCORE key max min [WITHSCORES] [LIMIT o c]` | O(log N + M) | Descending score range |
| `ZCOUNT` | `ZCOUNT key min max` | O(log N) | Count trong score range |
| `ZCARD` | `ZCARD key` | O(1) | Số lượng members |
| `ZMPOP` | `ZMPOP numkeys key [key ...] MIN\|MAX [COUNT n]` | O(log N) per member | Pop from multiple sorted sets |
| `BZMPOP` | `BZMPOP timeout numkeys key [...] MIN\|MAX [COUNT n]` | O(log N) per member | Blocking ZMPOP |
| `ZMSCORE` | `ZMSCORE key member [member ...]` | O(1) per member | Get multiple scores |
| `ZDIFF` | `ZDIFF numkeys key [key ...] [WITHSCORES]` | O(N log N) | Set difference |
| `ZINTER` | `ZINTER numkeys key [key ...] [WEIGHTS w] [AGGREGATE SUM\|MIN\|MAX]` | O(N*K log K) | Intersection |

**Use cases production:**
- Leaderboard: `ZADD leaderboard:global 1500 "alice"`, `ZREVRANGE leaderboard:global 0 9 WITHSCORES`
- Time-series indexed: `ZADD metrics:cpu:2026-05-19 12.5 "10:30"`, query `ZRANGEBYSCORE` theo time range
- Priority queue: `ZADD queue:high 3 "job:abc"`, `ZPOPMIN queue:high`
- Rate limiting per user: `ZADD ratelimit:user:123 {timestamp_ms} {unique_id}`, `ZREMRANGEBYSCORE` old entries

**Cảnh báo ZADD với cùng score:**
Nếu 2 members có cùng score, Redis sort by **lexicographical order** (binary compare of strings). Không phải random hay insertion order. Điều này quan trọng khi dùng ZSET cho deduplication hoặc tie-breaking.

**ZSET vs database index:**
- Database: B-tree, O(log N) for range, O(log N) for point query
- ZSET skiplist: O(log N) for range, O(log N) for rank
- ZSET hashtable: O(1) for score lookup by member
- Redis ZSET: không có durability, không có ACID, scale horizontally khó hơn

---

### 4.6 Big O Summary Table

```
Legend: N = number of elements in data structure
        M = number of elements returned by operation
        K = number of sets being intersected (ZINTER)
```

| Operation | String | List | Hash | Set | Sorted Set |
|-----------|--------|------|------|-----|------------|
| Read single | O(1) | O(1)* | O(1) | - | O(1)** |
| Read all | O(N) | O(N) | O(N) | O(N) | O(N log N) |
| Add | O(1) | O(1)* | O(1) | O(1) | O(log N) |
| Add many | O(N) | O(N) | O(N) | O(N) | O(N log N) |
| Delete | O(1) | O(1)* | O(1) | O(1) | O(log N) |
| Membership | - | - | - | O(1) | O(log N) |
| Range | - | O(S+M)*** | - | - | O(log N + M) |
| Random access | - | O(N) | - | - | - |
| Intersection | - | - | - | O(N*K) | O(N*K log K) |
| Cardinality | - | O(1) | O(1) | O(1) | O(1) |

`*` = head/tail operation; `**` = ZSCORE only; `***` = S = start offset

---

## 5. Trade-off Analysis

### 5.1 String vs Hash

| Tiêu chí | String (JSON) | Hash |
|----------|---------------|------|
| Memory (object 5 fields) | ~250B + key overhead × 6 | ~120B + key overhead × 1 |
| Read 1 field | O(N) parse full JSON | O(1) |
| Read all fields | O(N) | O(N) |
| Update 1 field | O(N) full serialize | O(1) |
| Update all fields | O(N) | O(N) |
| TTL | key-level | key-level |
| Key cardinality | N keys | 1 key |
| Pipeline batching | Multiple MGET | HMSET / HMGET |
| Serialization | Cần JSON encode/decode | Không cần |

**Khi nào String (JSON)?**
- Object > 100 fields và rarely partially accessed
- Cần gửi entire object qua network cho frontend
- Object được cached ở nhiều places với full snapshot
- Dùng `MSET`/`MGET` pattern với consistent JSON schema

**Khi nào Hash?**
- Object ≤ 100 fields, partial access common
- Individual fields được update độc lập
- Cần `HINCRBY` atomic counter per field
- Memory efficiency quan trọng

**Khi nào KHÔNG dùng cả hai?**
- Object rất lớn (> 100KB) → cần chunking hoặc CDN/file storage
- Cần per-field TTL → không có trong Redis cơ bản → phải dùng separate keys

---

### 5.2 List vs Stream

| Tiêu chí | List | Stream |
|----------|------|--------|
| Entry ID | User-specified | Auto-generated (timestamp+sequence) |
| Consumer groups | Không | Có (XREADGROUP, XACK) |
| Pending entries | Không | Có (XPENDING) |
| Claiming messages | Không | Có (XCLAIM) |
| Blocking read multiple keys | Có (BLPOP) | Có (XREAD BLOCK) |
| Range query | O(S+M) | O(log N + M) |
| Trimming | LTRIM manual | XTRIM automatic |
| Consumer fail tolerance | Low | High |
| Persistence | Full RDB/AOF | Full RDB/AOF |
| Max entries | Unbounded | Unbounded (trim) |

**Khi nào List?**
- Message queue đơn giản, single consumer, không cần acknowledgment
- Activity stream với capped size: `LPUSH` + `LTRIM 0 999`
- Temporary job queue: `LPUSH` jobs, `BRPOP` worker

**Khi nào KHÔNG dùng List làm queue?**
- Production job queue → dùng **Stream**
- Multiple consumers → List không hỗ trợ consumer groups
- Cần message acknowledgment → BRPOP không có ACK
- Cần retry failed message → không có pending mechanism
- Cần dead letter queue → không có trong List

---

### 5.3 Set vs Sorted Set

| Tiêu chí | Set | Sorted Set |
|----------|-----|------------|
| Membership check | O(1) | O(log N) |
| Add | O(1) | O(log N) |
| Intersection | O(N*K) | O(N*K log K) |
| Get random member | O(1) | O(log N) |
| Ordered by | Không | Score |
| Rank by score | Không | O(log N) |
| Score-based range | Không | O(log N + M) |
| Memory (int elements) | intset (very compact) | ~2x Set |

**Khi nào Set?**
- Tag system: `SISMEMBER` O(1) rất nhanh
- Unique tracking: daily visitors, job dedup
- Relationship: user follows, permissions
- Intersection for recommendation: `SINTER tag:iphone tag:wireless`

**Khi nào Sorted Set?**
- Leaderboard: ranked by score
- Time-series với index: sorted by timestamp
- Priority queue: sorted by priority score
- Range queries: top 10, bottom 10, by score range

**Khi nào Sorted Set thay vì Set?**
- Cần biết rank của member → `ZRANK`
- Cần top-N hoặc bottom-N → `ZREVRANGE`
- Cần query theo score range → `ZRANGEBYSCORE`
- Cần sort theo 2 criteria → composite score (e.g., `score = upvotes * 1000000 + recency_ts`)

---

### 5.4 Sorted Set vs Database Index

| Tiêu chí | Sorted Set | Database Index |
|----------|------------|-----------------|
| Lookup by member | O(1) (hashtable) | O(log N) B-tree |
| Range query | O(log N + M) | O(log N + M) |
| Rank query | O(log N) | O(log N) |
| Update score | O(log N) | O(log N) |
| Persistence | Optional (RDB/AOF) | Always durable |
| ACID | Không | Có |
| Concurrent writes | High throughput | MVCC overhead |
| Full-text search | Không | Có |
| Horizontal scale | Cluster (hash slot) | Sharding |
| Hot key risk | High (single key) | Medium (index partitioning) |
| Data size | Memory bound | Disk bound |
| p95 latency | ~0.3ms | ~5-50ms |

**Khi nào Sorted Set?**
- Leaderboard, real-time rankings → 100-1000x nhanh hơn DB
- Rate limiting windows → sorted by timestamp
- Time-series indexing → sorted by time
- Caching index data → Redis là cache, DB là source of truth

**Khi nào Database Index?**
- Cần durability đảm bảo (financial data, audit log)
- Cần ACID transactions跨 keys
- Cần complex queries (JOIN, subquery, full-text)
- Cần backup/restore tự động
- Dữ liệu lớn hơn memory

**Best practice**: Sorted Set là **index cache** phía trước database. Database là source of truth, Sorted Set được rebuild khi cache miss.

---

## 6. Best Solution & Best Practices

### Hash cho object cache nhỏ (< 100 fields)

```txt
# Profile cache - tốt
HSET user:123 name "An" email "an@example.com" avatar "/avatars/123.jpg" status "active"
HGET user:123 email
HINCRBY user:123 login_count 1

# Anti-pattern - dùng String cho object nhỏ
SET user:123 '{"name":"An","email":"an@example.com"}'
# Khi cần email → GET + JSON.parse → O(N)
```

**Điều kiện áp dụng**: Object có ≤ 100 fields, fields được access độc lập, không cần gửi full object thường xuyên.

### Sorted Set cho leaderboard

```txt
# Leaderboard production pattern
ZADD leaderboard:global 0 "alice"  # Initialize
ZINCRBY leaderboard:global 50 "alice"  # Score update
ZINCRBY leaderboard:global 30 "bob"
ZREVRANK leaderboard:global "alice"    # Alice's rank
ZREVRANGE leaderboard:global 0 9 WITHSCORES  # Top 10
```

**Điều kiện áp dụng**: Ranking theo numeric score, cần top-N queries, cần real-time rank updates.

### Set cho tag/membership/dedup

```txt
# Tag system
SADD product:456:tags electronics wireless noise-canceling
SISMEMBER product:456:tags wireless  # O(1) membership check

# Multi-tag intersection - find products matching all tags
SINTER tag:electronics tag:wireless tag:noise-canceling

# Cart deduplication (Shopify pattern)
SISMEMBER cart:user:123:products "SKU-999"
```

**Điều kiện áp dụng**: Unique membership, O(1) membership test, set operations (union, intersection, difference).

### List cho queue đơn giản

```txt
# Simple FIFO queue - OK cho non-critical async jobs
LPUSH queue:jobs '{"job_id":"abc","type":"email","payload":{}}'
BRPOP queue:jobs 0  # Block until job available
```

**Anti-pattern**: Dùng List cho production job queue. Dùng **Stream** nếu cần:
- Multiple consumers
- Message acknowledgment
- Retry failed jobs
- Consumer groups

### Anti-patterns cần tránh

```txt
# ANTI-PATTERN 1: KEYS command - O(N), blocks entire Redis
KEYS user:*  # NEVER in production

# ANTI-PATTERN 2: SMEMBERS với big set - O(N), blocks thread
SMEMBERS tag:electronics  # 10K elements → ~10ms block

# ANTI-PATTERN 3: LRANGE 0 -1 với big list
LRANGE user:feed:123 0 -1  # 100K entries → blocks event loop

# ANTI-PATTERN 4: HGETALL trên big hash
HGETALL product:all_catalog  # 100K fields → blocks event loop

# ANTI-PATTERN 5: SINTER với huge sets - O(N*M)
SINTER tag:a tag:b tag:c  # 3 sets × 5M elements = potential seconds block

# ANTI-PATTERN 6: LRANGE với negative count
LRANGE queue:jobs -100 -1  # Negative indexing buộc full traverse
```

---

## 7. Performance Considerations

### 7.1 Latency Distribution

| Operation | p50 | p95 | p99 | Notes |
|-----------|-----|-----|-----|-------|
| GET/SET | 0.05ms | 0.15ms | 0.3ms | O(1) |
| INCR | 0.06ms | 0.18ms | 0.4ms | O(1), atomic |
| HGET | 0.06ms | 0.18ms | 0.4ms | O(1) |
| HGETALL (100 fields) | 0.08ms | 0.25ms | 0.5ms | O(N) |
| ZADD | 0.08ms | 0.25ms | 0.5ms | O(log N) |
| ZRANGE 0 9 | 0.1ms | 0.3ms | 0.6ms | O(log N + M) |
| ZRANK | 0.1ms | 0.3ms | 0.6ms | O(log N) |
| SISMEMBER | 0.05ms | 0.15ms | 0.3ms | O(1) |
| SINTER (2×10K) | 0.5ms | 2ms | 5ms | O(N) |
| SINTER (2×5M) | 200ms | 800ms | 2000ms | O(N) |

### 7.2 ZRANGE O(log N + M) — M lớn nguy hiểm

```txt
ZADD leaderboard:global 0 player{1} ... player{1000000}
ZRANGE leaderboard:global 0 99 WITHSCORES       → O(log 1M + 100) ≈ O(20) = rất nhanh
ZRANGE leaderboard:global 0 999999 WITHSCORES   → O(log 1M + 1M) ≈ O(1M) = NGUY HIỂM
```

**p95 spike**: Khi M tăng từ 100 → 1M, latency tăng từ ~0.3ms → ~500ms. Đây là lý do luôn dùng `LIMIT offset count` với count nhỏ.

### 7.3 SINTER với Set lớn — O(N×M)

```txt
Set A = 5M members (all users)
Set B = 5M members (active users today)
SINTER A B
```

- Redis scan smaller set (A), lookup mỗi element trong larger set (B)
- Mỗi lookup hashtable là O(1) nhưng 5M lookups = 5M operations
- **Time**: ~5M × 0.05µs = 250ms trên local, ~2-5s qua network
- **Solution**: `SUNIONSTORE` để pre-compute, hoặc `SINTERCARD` nếu chỉ cần count

### 7.4 Memory Overhead

| Data Structure | Overhead per Entry |
|----------------|--------------------|
| String | 2-8B (SDS header) |
| Hash (listpack) | 3-6B per field + 2B per value length encoding |
| Hash (hashtable) | ~72B per entry (pointer overhead) |
| Set (intset) | 4-8B per integer |
| Set (hashtable) | ~72B per entry |
| Sorted Set (skiplist) | ~56B per member |

**Quy tắc**: Listpack/intset tối ưu memory nhưng chuyển đổi encoding khi vượt threshold → **spike latency**.

---

## 8. Production Failure Modes

### 8.1 Big Hash — Encoding chuyển từ listpack → hashtable

**Scenario**: Hash `user:profile:123` có 500 fields → vẫn là listpack. Thêm field thứ 513 → Redis chuyển toàn bộ sang hashtable.

**Impact**:
- `HGET` O(1) vẫn vậy nhưng memory tăng đột ngột (từ ~2KB → ~40KB)
- Nếu nhiều Hash cùng chuyển cùng lúc → `MEMORY USAGE` tăng 10-20x
- Không có alert mặc định → production incident

**Dấu hiệu**:
```bash
redis-cli OBJECT ENCODING user:profile:123
# listpack → hashtable
redis-cli DEBUG OBJECT-ENCODING user:profile:123
# hashtable
```

**Phòng tránh**: Monitor encoding change, giữ Hash < 512 fields, dùng `OBJECT FREQ` để track hot big hashes.

### 8.2 SMEMBERS với big set

**Scenario**: `SMEMBERS session:active` → 2M session tokens → response 500MB.

**Impact**:
- Single request chiếm 500MB RAM cho response buffer
- Event loop blocked 500ms+
- Tất cả other requests phải chờ
- Memory spike trên Redis server

**Phòng tránh**: Dùng `SSCAN` thay vì `SMEMBERS`, hoặc store set size in counter và `SRANDMEMBER` với count limit.

### 8.3 LRANGE 0 -1 trên list lớn

**Scenario**: `LRANGE user:feed:123 0 -1` → 50K posts × 500B = 25MB response.

**Impact**: Tương tự SMEMBERS, nhưng đặc biệt nguy hiểm vì:
- `LRANGE` phải traverse qua tất cả ziplist nodes
- Mỗi node phải decompress để build response
- CPU spike trên Redis server (không phải memory)

**Phòng tránh**: Luôn dùng `LRANGE key 0 99` thay vì `LRANGE key 0 -1`. Nếu cần pagination → use cursor-based pagination với offset.

### 8.4 ZRANGE 0 -1 trả về cả triệu elements

**Scenario**: Leaderboard không có `LIMIT` → `ZRANGE leaderboard:global 0 -1 WITHSCORES` → 1M members × (member + score) = 200MB response.

**Impact**: Same pattern — event loop blocked, memory pressure, network saturation.

**Phòng tránh**:
```txt
# Đúng
ZRANGE leaderboard:global 0 9 WITHSCORES

# Đúng - paginate
ZRANGE leaderboard:global 0 99 WITHSCORES
ZRANGE leaderboard:global 100 199 WITHSCORES

# Sai
ZRANGE leaderboard:global 0 -1 WITHSCORES
```

---

## 9. Real-world Examples

### Twitter/X — Sorted Set cho timeline
Twitter dùng Sorted Set để maintain user timeline với score = timestamp (Unix milliseconds).
```
ZADD timeline:123 1747696000000 "tweet:abc"
ZADD timeline:123 1747696100000 "tweet:def"
ZREVRANGE timeline:123 0 49 WITHSCORES  # Latest 50 tweets
```
Dùng `ZREMRANGEBYSCORE` để trim timeline về 800 tweets max, giữ memory bounded.

### GitHub — Hash cho session storage
GitHub lưu session data trong Hash với fields cho từng attribute:
```
HSET session:a3f8b2 user_id 12345 plan "pro" exp 1747696000
HINCRBY session:a3f8b2 page_views 1
HGET session:a3f8b2 plan
```
Lý do: Session cần partial update (page_views++), Hash O(1) per field update.

### Stack Overflow — Sorted Set cho reputation leaderboard
Stack Overflow dùng Sorted Set cho global và per-tag leaderboards:
```
ZADD user:reputation 15000 "user:alice"
ZREVRANGE user:reputation 0 9 WITHSCORES  # Top 10
```
Query này phục vụ public leaderboard page với latency < 1ms thay vì database query 50-200ms.

### Shopify — Set cho cart product IDs
Shopify dùng Set để lưu product IDs trong cart:
```
SISMEMBER cart:user:123:products "SKU-999"  # O(1) check if in cart
SADD cart:user:123:products "SKU-999"       # Add to cart
SREM cart:user:123:products "SKU-999"      # Remove from cart
SCARD cart:user:123:products               # Cart item count
```
O(1) membership check cực kỳ quan trọng cho cart operations với high throughput.

---

## 10. Common Pitfalls

### Pitfall 1: Dùng String khi nên dùng Hash

```go
// Sai - String với JSON
val, _ := rdb.Get(ctx, "product:456").Result()
product := parseJSON(val) // Parse toàn bộ JSON
fmt.Println(product.Name)

// Đúng - Hash
name, _ := rdb.HGet(ctx, "product:456", "name").Result() // O(1)
```

**Hậu quả**: Khi chỉ cần 1 field từ object 20 fields → parse 20KB JSON chỉ để lấy 1 field. Memory và CPU wasted, latency tăng.

### Pitfall 2: Dùng List làm queue thay vì Stream

```go
// ANTI-PATTERN: List làm job queue
for {
    result, _ := rdb.BRPop(ctx, 5*time.Second, "jobs:queue").Result()
    process(result)
    // Nếu process fail → job lost vĩnh viễn
    // Nếu worker crash → không có retry
    // Nếu cần 3 workers → race condition trên BRPOP
}
```

**Đúng**: Dùng Stream với consumer groups.

### Pitfall 3: ZADD với cùng score — alphabet sort không như mong đợi

```txt
ZADD test 100 "apple" 100 "Banana" 100 "cherry"
ZRANGE test 0 -1
# Output: ["Banana", "apple", "cherry"]
# B (ASCII 66) < a (ASCII 97) < c (ASCII 99)
```

**Hậu quả**: Nếu muốn "apple" đứng trước "Banana" → phải dùng different scores hoặc dùng lexicographical ordering với ZADD + INCR strategy.

**Fix**: `ZADD test (score) member` (sử dụng exclusive score) hoặc composite score `ZADD test 100.0001 "apple"`.

### Pitfall 4: HGETALL trên big hash

```go
// ANTI-PATTERN: Lấy tất cả fields cho 1 field cần thiết
allFields, _ := rdb.HGetAll(ctx, "big:object:123").Result()
value := allFields["needed_field"]

// Đúng: Chỉ get field cần thiết
value, _ := rdb.HGet(ctx, "big:object:123", "needed_field").Result()
```

### Pitfall 5: Quên rằng Set là unordered

```go
// ANTI-PATTERN: Mong đợi deterministic order từ Set
members, _ := rdb.SMembers(ctx, "tag:electronics").Result()
// members[0] không phải "first added" — Set是无序的
// Output thay đổi giữa các lần gọi

// Đúng: Dùng Sorted Set nếu cần order
```

### Pitfall 6: Dùng intset limit quá mức

512 element limit cho intset là hardcoded trong Redis source. Nếu Set có đúng 513 integers → chuyển sang hashtable, memory tăng ~10x.

---

## 11. Câu hỏi tự kiểm tra

**Q1.** Bạn cần cache user profile có 15 fields. User thường xuyên chỉ cần 2-3 fields (name, avatar, status). Data structure nào phù hợp nhất?

**Q2.** Hệ thống rate limiting cần đếm requests trong sliding window 1 phút. Mỗi user có thể có 1000 requests/phút. Dùng Sorted Set với score = timestamp. Explain cách trim old entries và check current count.

**Q3.** `SINTER tag:iphone tag:wireless` trả về 50K results. Số lượng members trong mỗi set là 5M. Latency p95 là bao nhiêu? Làm sao giảm?

**Q4.** Bạn có Hash `product:catalog` với 200K fields (product_id → product_metadata JSON). `HGETALL` mất 2 giây. Giải thích nguyên nhân và đề xuất 3 cách fix.

**Q5.** Trường hợp nào dùng `SUNION` vs `SINTER`? Có trade-off gì khi dùng `SUNIONSTORE`?

**Q6.** Sorted Set encoding threshold là 128 items cho listpack. Nếu ZSET có 127 items, memory usage là bao nhiêu? Sau khi add thêm 1 item (128 total), memory thay đổi thế nào?

**Q7.** Shopify dùng Set cho cart. Làm sao implement "show cart item count" mà không gọi `SCARD` mỗi request? (Hint: đọc Shoppify engineering blog)

---

## Đáp án

**A1.** Hash. Vì:
- 15 fields ≤ 100 fields → encoding listpack (efficient)
- Partial access → `HGET` O(1) vs `GET` + JSON.parse O(N)
- Individual field update → `HINCRBY` atomic
- String JSON: GET + parse full 15-field JSON chỉ để lấy 1 field → O(N) parse overhead

**A2.** Sliding window rate limiting với Sorted Set:
```txt
# 1. Add request với timestamp là score và unique ID là member
ZADD ratelimit:user:123 {timestamp_ms} {uuid}

# 2. Remove entries older than 60 seconds
ZREMRANGEBYSCORE ratelimit:user:123 -inf {now_ms - 60000}

# 3. Count entries trong window
ZCARD ratelimit:user:123

# 4. Auto-expire key sau 2 minutes (safety net)
EXPIRE ratelimit:user:123 120
```
Lưu ý: `ZREMRANGEBYSCORE` + `ZCARD` = 2 commands. Có thể wrap trong Lua script để atomic.

**A3.** SINTER 2 sets × 5M elements:
- Redis scan smaller set (假设 tag:iphone = 5M)
- Mỗi element lookup trong tag:wireless hashtable = O(1)
- 5M × 0.05µs ≈ 250ms (local), ~1-2s (network)
- p95: có thể 500ms-2s với network overhead

**Giảm latency:**
1. Dùng `SINTERCARD tag:iphone tag:wireless 1000 LIMIT 1000` — stop sau 1000 kết quả
2. Precompute intersection với `SINTERSTORE` chạy background
3. Dùng pipeline: `SISMEMBER` batch thay vì SINTER nếu chỉ cần check 1 user

**A4.** Nguyên nhân: `HGETALL` là O(N) với N = 200K fields. Redis phải:
1. Iterate qua tất cả 200K entries
2. Serialize toàn bộ thành response (200K × ~200B = 40MB)
3. Network transfer 40MB

**3 cách fix:**
1. **Dùng `HSCAN`**: Iterator, không block, chunk processing
```txt
HSCAN product:catalog 0 MATCH product:* COUNT 1000
```
2. **Tách Hash lớn thành nhiều Hash nhỏ**: Key per product thay vì 1 big hash
3. **Dùng pipeline với `HMGET`**: Chỉ get fields cần thiết
```go
fields := []string{"name", "price", "stock"}
rdb.HMGet(ctx, "product:catalog", fields...)
```

**A5.**
- `SUNION`: Lấy tất cả unique members từ N sets → union = members in any set
- `SINTER`: Lấy members có mặt trong ALL N sets → intersection = common members

Trade-offs khi dùng `SUNIONSTORE`:
- `SUNIONSTORE dest key1 key2 ...` — chạy trên Redis server (không phải client)
- Destination key tồn tại → bị overwrite
- Nếu N sets × M elements → O(N×M) memory và time cho destination
- Dùng khi: intersection được query thường xuyên (precompute)
- Không dùng khi: sets thay đổi liên tục (maintenance overhead cao)

**A6.** Với 127 items < 128 threshold:
- Encoding: listpack-zset
- Memory: ~127 × (member_size + 3-6B overhead) ≈ very compact

Với 128 items = threshold:
- Redis chuyển sang skiplist + hashtable
- Memory tăng ~2-3x đột ngột (hashtable overhead ~72B/entry)
- Đây là "invisible spike" — không có warning

**A7.** Cách Shopify làm:
1. Lưu cart count trong **String key** (separate key):
```
SET cart:user:123:count 5
INCR cart:user:123:count   # Khi add
DECR cart:user:123:count   # Khi remove
```
2. Hoặc dùng `SCARD` một lần rồi **cache in-process** (application-level counter):
```go
var cartCount int64
// On add to cart: cartCount++
// On page load: if cartCount == 0 { cartCount = rdb.SCard(...).Val() }
// Return cartCount without Redis call
```
3. Optimistic update: update count ngay, dùng `DECR` nếu SCARD mismatch (eventual consistency).

**Nguyên tắc**: Redis call có latency ~0.1-0.5ms. Với high-frequency operation như "show cart count trên mọi page", gọi Redis mỗi request là overkill. Cache at application layer, update Redis asynchronously.
