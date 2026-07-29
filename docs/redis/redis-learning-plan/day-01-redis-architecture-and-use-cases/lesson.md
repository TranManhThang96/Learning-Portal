# Day 1: Redis Architecture & Production Use Cases

---

## 1. Mục tiêu bài học

- Phân biệt được Redis là gì, Redis không phải là gì, và tại sao đó quan trọng trong production
- Hiểu kiến trúc single-threaded, event loop, I/O multiplexing của Redis và impact của nó lên performance
- Phân tích được trade-off giữa Redis as cache vs Redis as primary store, Redis vs Memcached, Redis vs database materialized view, Redis vs local in-memory cache
- Đánh giá được khi nào nên / không nên dùng Redis cho một bài toán cụ thể
- Setup và kết nối Redis trong môi trường Docker, verify được các chỉ số quan trọng bằng redis-cli

---

## 2. Vì sao cần học chủ đề này

Redis rất dễ bị sử dụng sai cách. Phần lớn các incident liên quan đến Redis đều xuất phát từ một trong những lý do:

- **Dùng Redis làm primary store** mà không cấu hình persistence đúng cách, dẫn đến mất dữ liệu khi restart. Case nổi tiếng: một số startup mất toàn bộ session data khi Redis container bị restart vì không có volume mount.
- **Không hiểu single-threaded model** dẫn đến sử dụng blocking command (KEYS *, SMEMBERS trên big set, GETALL trên big hash) làm treo toàn bộ server.
- **Không hiểu eviction policy** dẫn đến dữ liệu bị xóa khi chưa kịp sử dụng, hoặc client bị block khi Redis trả về error.

Ví dụ failure thật: năm 2013, một ứng dụng Twitter clone sử dụng Redis làm session store nhưng không cấu hình RDB snapshot. Khi server bị restart, 100% user bị logout. Nếu hiểu rõ kiến trúc Redis, họ sẽ biết rằng Redis mặc định chỉ lưu data trong memory và mất khi restart nếu không có persistence.

Một bài toán cache trending topic trên social network thất bại vì sử dụng KEYS * để tìm key. KEYS * trên 10 triệu key làm Redis trễ 30 giây, tất cả request bị timeout.

Bài học: Redis là công cụ cực kỳ mạnh nhưng chỉ mạnh khi bạn hiểu nó.

---

## 3. Kiến thức nền cần có

- HTTP request/response cycle và network overhead
- TCP/IP networking cơ bản
- Docker và Docker Compose
- Client-server architecture
- Khái niệm latency, throughput, ops/sec

---

## 4. Nội dung lý thuyết từ cơ bản đến chi tiết

### 4.1 Redis là gì - Redis không phải là gì

**Redis (REmote DIctionary Server)** là in-memory data structure server, đầu tiên được tạo bởi Salvatore Sanfilippo (antirez) năm 2009. Nó lưu trữ dữ liệu trong RAM và cung cấp các thao tác trên các cấu trúc dữ liệu như String, Hash, List, Set, Sorted Set, Bitmap, HyperLogLog, Stream.

**Redis là:**
- In-memory cache
- Session store
- Rate limiter
- Message broker (pub/sub, streams)
- Distributed lock provider
- Real-time leaderboard
- Counter và rate limiting

**Redis KHÔNG phải là:**
- Primary database cho transactional data (nếu không cấu hình persistence)
- Durable storage (nếu chỉ dùng memory, mất dữ liệu khi restart)
- Search engine (chỉ có pattern matching cơ bản với KEYS/SCAN)
- Relational database (không có SQL, không có join)
- Message queue mạnh (Redis Streams lại, nhưng Kafka/RabbitMQ tốt hơn cho durable queue)
- Wide-column store hay document store

### 4.2 Redis Architecture Overview

```
+------------------+       RESP (Redis Serialization Protocol)
|   Client App     | <----------------------------------->  Redis Server
|  (TypeScript/Go) |           TCP socket (non-blocking)
+------------------+
                            +----------------------------+
                            |    Event Loop (aeEventLoop)|
                            |    +---------------------+ |
                            |    |  I/O Multiplexing   | |
                            |    |  (epoll/kqueue/...) | |
                            |    +---------------------+ |
                            |    +---------------------+ |
                            |    |  Command Dispatcher | |
                            |    +---------------------+ |
                            |    +---------------------+ |
                            |    |   Command Handler   | |
                            |    |  (data structures) | |
                            |    +---------------------+ |
                            +----------------------------+
                            |         Memory            |
                            |   (jemalloc allocator)     |
                            +----------------------------+
                            |     Persistence Layer     |
                            |    (RDB + AOF writers)    |
                            +----------------------------+
```

### 4.3 Single-Threaded Model - Sự thật và hiểu lầm

**Sự thật:**
- Redis sử dụng một single thread để execute commands. Không phải vì nó không thể handle concurrency, mà vì nó CHỌN single thread vì:
  - Không có context switch overhead giữa threads
  - Không có lock contention khi truy cập data structures
  - Data structures trong Redis được implement đơn giản, thread-safe by design (vd: sds string, skiplist)
  - Memory allocator jemalloc được tune cho single-threaded access

**I/O Multiplexing (Event Loop):**

```
Client A --[SET foo bar]-->  TCP Buffer
Client B --[GET foo]------>  TCP Buffer
Client C --[HSET ...]----->  TCP Buffer
        |
        v
+------------------+
|  I/O Multiplexer |  <-- epoll (Linux) / kqueue (macOS/BSD) / select (Windows fallback)
|  (aeApiPoll)     |
+------------------+
        |
        v
+------------------+
| Command Queue    |  <-- ring buffer, non-blocking
+------------------+
        |
        v
+------------------+
|  Command         |  <-- xử lý trên single thread
|  Processor       |
+------------------+
        |
        v
+------------------+
| Response Buffer  |  <-- viết vào socket
+------------------+
```

**Điểm quan trọng:** các I/O operation là non-blocking. epoll/kqueue chỉ là cho socket events (có data đến, có data đi), còn xử lý command thực sự vẫn là lại single-threaded. Đây là lý do tại sao một blocking command (KEYS *, SORT, SMEMBERS trên 10 triệu members) có thể làm trễ toàn bộ Redis.

### 4.4 Tại sao Redis nhanh

**1. Memory access pattern:**
- Đọc từ RAM: ~100-300 ns (nanosecond)
- Đọc từ disk SSD: ~100-200 us (microsecond) = 1,000x chậm hơn
- Đọc từ disk HDD: ~10-20 ms (millisecond) = 100,000x chậm hơn
- Redis đọc từ RAM, thật đơn giản.

**2. CPU cache friendliness:**
- Redis data structures được thiết kế để fit trong L1/L2 cache khi có thể
- SDS (Simple Dynamic String) trong Redis 7 có overhead chỉ 0-3 bytes
- Không có complex pointer chasing như disk-based B-tree

**3. Network overhead tính toán:**
- RESP protocol đơn giản, parse nhanh
- Non-blocking I/O: server không blocking khi chờ data từ socket
- pipelining cho phép gửi nhiều command trong một round-trip

**4. So sánh với các giải pháp khác:**

| | Redis | Memcached | PostgreSQL (SSD) | Elasticsearch |
|---|---|---|---|---|
| Latency p50 | ~0.1-0.3 ms | ~0.1-0.3 ms | ~1-5 ms | ~5-20 ms |
| Latency p99 | ~0.5-2 ms | ~0.5-2 ms | ~10-50 ms | ~50-200 ms |
| ops/sec (single node) | 100K-1M | 100K-500K | 10K-50K | 1K-10K |
| Memory footprint/key | ~50-100 bytes | ~50-100 bytes | ~200-500 bytes | ~1KB-10KB |

### 4.5 Redis trong Microservices Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  API Gateway    │    │  Auth Service   │    │  Order Service  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         v                      v                      v
┌──────────────────────────────────────────────────────────────────┐
│                        Redis Cluster                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │ Cache Layer │  │Session Store│  │Rate Limiter │               │
│  │  (API resp) │  │  (JWT sess) │  │ (per user)  │               │
│  └─────────────┘  └─────────────┘  └─────────────┘               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  Pub/Sub    │  │Distributed  │  │Leaderboard/ │               │
│  │  (events)   │  │   Lock      │  │  Counter    │               │
│  └─────────────┘  └─────────────┘  └─────────────┘               │
└──────────────────────────────────────────────────────────────────┘
```

**Redis trong microservice thường được dùng cho:**

| Use case | Redis data structure | Lý do |
|---|---|---|
| API response cache | String (JSON) | latency thấp, giải phóng DB |
| User session | Hash / String | session expiry tự động, nhanh |
| Rate limiting | String + Lua | atomic counter, chính xác |
| Distributed lock | String (NX PX) | chi phí thấp, dễ setup |
| Real-time leaderboard | Sorted Set | O(log N) cập nhật/xếp hạng |
| Job queue | List / Stream | nhẹ, tích hợp Redis |
| Pub/Sub | Pub/Sub / Stream | real-time notification |
| Idempotency key | String (NX EX) | chặn duplicate request |

---

## 5. Trade-off Analysis

### 5.1 Redis as Cache vs Redis as Primary Store

| Tiêu chí | Redis as Cache | Redis as Primary Store |
|---|---|---|
| **Ưu điểm** | Performance tối đa, đơn giản, không cần quan tâm durability | Dữ liệu được persist, có thể thay thế DB cho một số use case |
| **Nhược điểm** | Mất dữ liệu khi restart (nếu không có persistence), cần invalidation strategy | Complexity cao hơn, cần cấu hình RDB/AOF, potential data loss nếu dùng AOF only |
| **Khi nào chọn** | Cache API response, temporary data, session (có backup), rate limit counter | Counters, leaderboard, config không có DB, distributed lock |
| **Khi nào KHÔNG chọn** | Transactional data, financial record, user-generated content | Khi bạn cần durability thật sự, khi bạn không có team có kinh nghiệm quản lý Redis |
| **Data loss** | Có thể mất toàn bộ data | RDB: mất data từ lúc snapshot gần nhất (1 phút - vài giờ). AOF everysec: mất ~1 giây. AOF always: mất 0 giây nhưng latency cao |
| **Operation overhead** | Thấp | Cao (backup, monitoring, eviction tuning) |

### 5.2 Redis vs Memcached

| Tiêu chí | Redis | Memcached |
|---|---|---|
| **Data structures** | String, Hash, List, Set, Sorted Set, Bitmap, HyperLogLog, Stream, Geospatial | Chỉ String |
| **Persistence** | Có RDB, AOF | Không có (pure in-memory, mất khi restart) |
| **Replication** | Có master-replica, Sentinel, Cluster | Có replica nhưng không có automatic failover |
| **Atomic operations** | Có (INCR, HINCRBY, SETNX, Lua scripts) | Giới hạn (chỉ incr/decr trên String) |
| **Eviction policy** | 8 loại (LRU, LFU, TTL-based, random) | 4 loại (LRU, LFU, FIFO, TTL) |
| **Memory efficiency** | Dict entry ~64 bytes, SDS overhead thấp | Chunk overhead ~40-50 bytes/key |
| **Multi-threaded** | Single-threaded (nhanh hơn cho small ops), có worker threads cho I/O | Multi-threaded (tốt hơn cho very high throughput trên multi-core) |
| **Network efficiency** | RESP protocol, pipelining | ASCII protocol, binary protocol |
| **Use case tốt nhất** | Complex data structures, pub/sub, streams, sorted operations | Simple key-value cache, dovetail với Nginx/Varnish |
| **Use case không nên** | Khi chỉ cần simple string cache và muốn multi-threaded performance | Khi cần complex data structures, durability, replication |
| **Latency p99** | ~0.5-2 ms | ~0.3-1 ms (đơn giản hơn, multi-threaded) |
| **Memory overcommit** | Có config maxmemory, eviction | Có config max |

### 5.3 Redis vs Database Materialized View

| Tiêu chí | Redis Cache | Database Materialized View |
|---|---|---|
| **Latency** | ~0.1-2 ms | ~5-50 ms (phụ thuộc query phức tạp) |
| **Consistency** | Cần invalidation strategy, có thể stale | Tự động sync với source table |
| **Storage cost** | RAM (đắt hơn), giới hạn bởi maxmemory | Disk (rẻ chỉ phí ~$0.1/GB) |
| **Flexibility** | Cache bất kỳ shape nào, bất kỳ query nào | Chỉ cho query được định nghĩa sẵn trong view |
| **Maintenance** | Cần manual invalidation, TTL, warming | Tự động refresh (scheduled hoặc on-commit) |
| **Complex aggregation** | Giới hạn (tính toán ở app layer) | Mạnh (SQL aggregation, window function) |
| **Use case** | Pre-computed expensive query, API response cache, hot data | Report aggregation, dashboard data, OLAP-like query |
| **Reliability** | Mất dữ liệu khi restart/eviction | Tồn tại trong DB, backup cùng DB |
| **Khi nào chọn Redis** | Data thay đổi nhiều, cần p99 latency thấp, read-heavy | Data thay đổi ít, cần exact result, disk storage rẻ |
| **Khi nào chọn Materialized View** | Cần exact data, không chấp nhận stale, query phức tạp | Cần durability, data nằm trong DB chính |

### 5.4 Redis vs Local In-Memory Cache (In-App Cache)

| Tiêu chí | Redis (Centralized) | Local In-Memory Cache |
|---|---|---|
| **Sharing** | Tất cả instances chia sẻ cùng data | Mỗi instance có copy riêng |
| **Consistency** | Tất cả instances nhìn cùng một giá trị | Có thể stale giữa instances |
| **Memory usage** | Tổng memory = size của Redis (không nhân bản) | Memory = size x số instance |
| **Invalidation** | Tất cả instances đều thấy impact của invalidation | Chỉ instance owner bị invalidation |
| **Latency** | ~0.5-2 ms (network round-trip) | ~0.01-0.05 ms (in-process) |
| **Scalability** | Dễ scale, Redis Cluster | Không scale, memory giới hạn mỗi instance |
| **Fault tolerance** | Redis down -> cache miss nhưng app vẫn chạy | Instance down -> same như Redis down |
| **Use case** | Shared state: session, rate limit counter, distributed lock | Per-instance cache: computed value, config, hot data |
| **Hybrid approach** | Local cache làm L1, Redis làm L2 | Dành cho latency cực kỳ nhạy cảm |
| **Khi nào chọn Redis** | Multi-instance deployment, cần distributed state | Single instance, cần p50 latency cực kỳ thấp |
| **Khi nào chọn Local** | Single instance, memory đủ, chỉ cần cache đơn giản |

---

## 6. Best Solution & Best Practices

### 6.1 Decision Framework

```
Bạn cần Redis?
|
+-- Bạn cần durable storage cho transactional data?
|   +-- Có: Không nên dùng Redis làm primary. Dùng PostgreSQL/MySQL.
|
+-- Bạn cần complex SQL query?
|   +-- Có: Không nên dùng Redis. Dùng Redis chỉ làm cache.
|
+-- Bạn cần chỉ là simple key-value cache?
|   +-- Có: Redis hoặc Memcached đều được. Chọn dựa vào:
|       - Cần complex data structures? -> Redis
|       - Cần multi-threaded performance, chỉ cần string? -> Memcached
|
+-- Bạn cần distributed state (lock, counter, session)?
|   +-- Có: Redis là lựa chọn tốt.
|
+-- Bạn cần real-time leaderboard, rate limit, pub/sub?
|   +-- Có: Redis là lựa chọn tốt.
```

### 6.2 Best Practices theo Scenario

| Scenario | Recommendation | Config |
|---|---|---|
| API response cache (stateless service) | Redis as cache, cache-aside pattern | `maxmemory` = 50-70% RAM, `maxmemory-policy allkeys-lru` |
| User session (web app, multi-server) | Redis as session store, có replica | `maxmemory-policy volatile-lru`, TTL = session timeout |
| Rate limiting | Redis as counter, sliding window | `maxmemory-policy noeviction`, Lua script cho atomic |
| Distributed lock | Redis SET NX PX | `maxmemory-policy noeviction`, always use token + Lua |
| Hot data cache (precomputed aggregation) | Redis as cache + local cache L1/L2 | Redis TTL ngắn + local cache |
| Real-time leaderboard | Redis Sorted Set | `maxmemory-policy allkeys-lru` or noeviction |

### 6.3 Anti-patterns cần tránh

1. **Dùng KEYS * trên production** - O(N) với N = số key, trễ treo server
2. **Dùng Redis làm primary store mà không cấu hình persistence** - Mất dữ liệu khi restart
3. **Không đặt maxmemory** - Redis sử dụng hết RAM rồi crash
4. **Dùng evict policy `noeviction` mà không có monitoring** - Client bị error khi memory đầy
5. **Lưu big key (>10MB)** - Replicate lag cao, memory fragmentation
6. **Không dùng TTL** - Key nằm mãi trong memory, không bao giờ được evict
7. **Dùng single Redis instance làm nhiều thứ** - Mix cache + session + lock + queue = failure domain lớn

---

## 7. Performance Considerations

### 7.1 Big O quan trọng

| Operation | Time Complexity | Ghi chú |
|---|---|---|
| SET / GET | O(1) | Không phụ thuộc số lượng key |
| INCR / DECR | O(1) | Atomic, tốt nhất cho counter |
| HSET / HGET | O(1) | Hash field-level operation |
| HGETALL | O(N) | N = số field trong hash, tránh hash lớn |
| SMEMBERS | O(N) | N = số member trong set, tránh set lớn |
| SORT | O(N log N) | Mỗi khi nào có thể, dùng Lua thay thế |
| ZADD / ZRANGE | O(log N) | N = số member trong sorted set |
| KEYS * | O(N) | Tuyệt đối không dùng trên production |
| SCAN | O(1) per iteration | Dùng SCAN thay KEYS * |

### 7.2 Latency Numbers

| Operation | p50 | p95 | p99 | Notes |
|---|---|---|---|---|
| GET / SET (local) | ~30 us | ~100 us | ~300 us | Không có network |
| GET / SET (network) | ~200 us | ~500 us | ~1-2 ms | Cùng datacenter |
| GET / SET (cross-region) | ~5-20 ms | ~30-50 ms | ~50-100 ms | Không dùng cross-region Redis |
| Pipeline 10 commands | ~200 us | ~600 us | ~1-2 ms | Tiết kiệm RTT |
| MGET 100 keys | ~200 us | ~600 us | ~1-2 ms | Tốt hơn 100 GET riêng lẻ |
| Lua script đơn giản | ~50 us | ~150 us | ~400 us | Atomic, giảm RTT |

### 7.3 Throughput

| Metric | Value | Notes |
|---|---|---|
| ops/sec (single node, local) | 100K - 500K | Phụ thuộc payload, hardware |
| ops/sec (redis-benchmark, -r 1M) | 300K - 1M | Synthetic benchmark |
| ops/sec (real world) | 50K - 200K | Có network, app overhead |
| Connection limit | 10K - 100K | Phụ thuộc maxclients config |
| Memory per key | ~50-200 bytes | Phụ thuộc data type, allocator |

### 7.4 p95/p99 Impact

- Một slow command (100ms) giữa 10,000 requests -> chỉ 0.01% traffic bị trễ, nhưng nếu nó là GET/PING, có thể lỗi timeout
- `SLOWLOG` với threshold 10ms: bất kỳ command nào > 10ms đều được ghi lại
- Latency spike trong Redis thường do: fork (BGSAVE), AOF rewrite, big key access, KEYS *, swap
- Monitor latency bằng: `redis-cli --latency-history`, `redis-cli --latency-dist`, `INFO commandstats`

---

## 8. Production Failure Modes

### 8.1 Redis Out of Memory (OOM)

**Nguyên nhân:**
- Không đặt `maxmemory`, Redis sử dụng hết RAM
- `maxmemory-policy noeviction` + memory đầy = client nhận error
- Big key chen nhanh, eviction không kịp

**Dấu hiệu:**
- `redis-cli INFO memory` -> `used_memory` ≈ `maxmemory`
- `evicted_keys` > 0 trong `INFO stats`
- Client trả về `OOM command not allowed when memory limit is reached`

**Debug:**
```bash
redis-cli INFO memory | grep -E "maxmemory|used_memory|evicted_keys|expired_keys"
redis-cli MEMORY DOCTOR
redis-cli --bigkeys
redis-cli --hotkeys
```

**Phòng ngừa:**
- Đặt `maxmemory` = 70-80% RAM, để headroom
- Chọn đúng `maxmemory-policy` (allkeys-lru cho cache, noeviction cho lock/counter)
- Monitor `evicted_keys` rate, alert khi > 0
- Đặt `maxmemory-samples` (mặc định 5, tăng lên 10 nếu có nhiều small keys)

### 8.2 Single-Threaded Blocking

**Nguyên nhân:**
- Blocking command trên big data: KEYS *, SORT, SMEMBERS, HGETALL, BLPOP (nếu không có data)
- Long-running Lua script
- Fork overhead during BGSAVE/AOF rewrite

**Dấu hiệu:**
- `redis-cli --latency-history` hiện latency spike bất thường
- `redis-cli INFO commandstats` hiện `calls` thấp nhưng `usec` cao
- Client timeout gặp rồi

**Debug:**
```bash
redis-cli SLOWLOG GET 10
redis-cli INFO commandstats
redis-cli CONFIG GET *slowlog*
```

### 8.3 Data Loss khi Restart

**Nguyên nhân:**
- Không cấu hình RDB/AOF, chỉ chạy Redis bình thường
- AOF `appendfsync no` + restart = mất data trong AOF buffer
- RDB `save` không chạy trước restart

**Dấu hiệu:**
- Session biến mất, cache miss rate = 100%, user bị logout
- Counter bị reset

**Phòng ngừa:**
- Dùng Redis 7+ với `appendonly yes` + `appendfsync everysec` (trade-off: mất ~1 giây data)
- Hoặc `appendfsync always` cho mission-critical (latency tăng thêm 1-2ms/write)
- Test restore từ AOF/RDB trước khi lên production

### 8.4 Connection Exhaustion

**Nguyên nhân:**
- Connection pool không close properly
- Client reconnect liên tục mà không success
- Too many clients (maxclients default ~10K)

**Dấu hiệu:**
- `redis-cli INFO clients` -> `connected_clients` cao bất thường
- `blocked_clients` > 0
- Client lỗi "Connection refused" hoặc timeout

---

## 9. Real-world Examples

### 9.1 Twitter/X - Timeline Cache

Twitter lưu timeline của user trong Redis (Sorted Set, key = `timeline:{user_id}`). Mỗi entry là tweet_id với score = timestamp. Khi user refresh timeline, Redis trả về top 800 tweet nhanh chóng, không cần query database. Khi có tweet mới, push vào sorted set của tất cả follower.

**Số lượng:** Hàng triệu key, mỗi key chứa ~800-2000 tweet IDs.

**Lý do dùng Redis:** Timeline là read-heavy (99%), latency phải thấp, data có TTL (chỉ cần tweet trong vòng 7 ngày).

**Trade-off đã phân tích:** Stale timeline khi user có follower mới, nhưng chấp nhận được.

### 9.2 GitHub - Session Store

GitHub sử dụng Redis làm session store cho hàng triệu developer. Session data (user info, permissions, preferences) được lưu trong Redis Hash.

**Số lượng:** 50+ triệu session, mỗi session ~1-5KB.

**Lý do dùng Redis:** GitHub có nhiều server, cần shared session state. Redis có TTL tích hợp, dễ invalidate khi user logout.

**Incident nổi tiếng:** Năm 2013, một maintenance window bị delay, session Redis chưa được save xuống disk, user bị logout. Sau đó GitHub cấu hình AOF + replica để đảm bảo durability.

### 9.3 Stack Overflow - Caching Layer

Stack Overflow cache kết quả question list, question detail, tag list, user profile trong Redis. Cache hit rate > 95%, giải phóng PostgreSQL 80% load.

**Số lượng:** ~50 triệu cached objects.

**Lý do dùng Redis:** Questions được đọc nhiều, viết ít. Redis giúp trả lời trong < 5ms thay vì 50-200ms từ database.

### 9.4 Shopify - Rate Limiting

Shopify dùng Redis cho rate limiting API trên toàn bộ platform. Dùng sliding window algorithm implement bằng Lua script.

**Số lượng:** 100K+ requests/sec lúc peak.

**Lý do dùng Redis:** Atomic operation của Redis (INCR, Lua) đảm bảo counter chính xác trong distributed environment. Sub-millisecond latency cho phép check rate limit mà không ảnh hưởng API latency.

### 9.5 Uber - Geospatial Query

Uber dùng Redis Geospatial (Sorted Set) để query nearby drivers. `GEORADIUS` trả về drivers trong bán kính 5km trong O(N+log(M)).

**Lý do dùng Redis:** Real-time location update, sub-10ms query time cho mobile app.

---

## 10. Common Pitfalls

### Pitfall 1: Dùng Redis làm Primary Store cho User Data

**Vấn đề:** Nếu Redis chỉ được cấu hình RDB và không có replica, restart sẽ mất toàn bộ user data.

**Giải pháp:** Nếu data cần durable, sử dụng PostgreSQL/MySQL. Redis chỉ làm cache. Nếu thật sự cần Redis làm store, cấu hình AOF `everysec` hoặc `always`, có replica.

### Pitfall 2: KEYS * trên Production

**Vấn đề:** `KEYS *` là O(N), trễ 30+ giây nếu có 10 triệu key. Tất cả command bị block.

**Giải pháp:** Dùng `SCAN` (iterative, non-blocking) hoặc `SSCAN/HSCAN/ZSCAN` cho set/hash/sorted set.

### Pitfall 3: Không cấu hình maxmemory

**Vấn đề:** Redis sử dụng hết RAM, OS kill Redis process (OOM killer) hoặc Redis crash.

**Giải pháp:**
```bash
# Đặt maxmemory = 70% RAM
redis-cli CONFIG SET maxmemory 3gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET maxmemory-samples 10
```

### Pitfall 4: Không có TTL trên Cache Key

**Vấn đề:** Cache key nằm mãi trong memory, không bao giờ được evict, memory tăng dần không kiểm soát.

**Giải pháp:** Luôn đặt TTL khi set cache:
```bash
SET cache:user:123 '{"name":"..."}' EX 3600  # 1 hour TTL
```

### Pitfall 5: Dùng Redis cho Transactional Data

**Vấn đề:** Redis không có ACID transaction như PostgreSQL. Nếu bạn cần rollback khi error, Redis không hỗ trợ.

**Giải pháp:** Chỉ dùng Redis cho denormalized data, counter, cache. Cho transactional data (order, payment), dùng database.

### Pitfall 6: Không monitor eviction

**Vấn đề:** `evicted_keys` tăng lên -> cache hit rate giảm -> database overload.

**Giải pháp:** Alert khi `evicted_keys` > 0. Nếu thường xuyên, tăng `maxmemory` hoặc tối ưu data model.

### Pitfall 7: Big Key (>10MB)

**Vấn đề:** Big key làm tăng `repl_backlog` size, chậm rehashing, khó evict.

**Giải pháp:** Chunk big data (dùng List/Sorted Set thay vì String lớn), monitor bằng `redis-cli --bigkeys`.

---

## 11. Câu hỏi tự kiểm tra

**Câu 1.** Một e-commerce platform cần cache product catalog (100K products, đọc 10K lần/phút, ghi 100 lần/phút). Bạn sẽ chọn giữa Redis và PostgreSQL materialized view? Tại sao? Nếu chọn Redis, cấu hình nào là hợp lý?

**Câu 2.** Một distributed system có 20 API server, cần rate limiting 100 req/min/user. Nếu dùng Redis làm counter, điều gì xảy ra khi Redis bị down? Có cách nào mitigate?

**Câu 3.** Bạn phát hiện `redis-cli INFO` hiện `evicted_keys: 15000` trong 1 phút. Đây có nghĩa gì? Bạn sẽ debug như thế nào? Nếu khắc phục?

**Câu 4.** Một developer sử dụng `KEYS order:*` để tìm tất cả order trong Redis. Tại sao đây là anti-pattern? Có thay thế nào tốt hơn?

**Câu 5.** Bạn có 10 triệu session user, mỗi session 2KB, cần lưu 7 ngày. Tính memory Redis cần thiết. Nếu dùng Redis as primary store (không có DB), cần cấu hình persistence nào để đảm bảo data không mất?

**Câu 6.** So sánh latency p50/p95/p99 giữa Redis GET (local), Redis GET (network cùng datacenter), và PostgreSQL SELECT (indexed row). Tại sao p99 lớn hơn p50 nhiều hơn trong database so với Redis?

**Câu 7.** Một social network muốn cache newsfeed cho 1 triệu user. Mỗi feed có 50 posts. Nếu lưu tất cả feed trong Redis, memory cần thiết là bao nhiêu? Có cách nào tối ưu hơn?

---

## Đáp án

**Câu 1:** Redis là lựa chọn tốt vì read-heavy (99%), cần p99 latency thấp. Cấu hình: `maxmemory-policy volatile-lru`, `maxmemory` = 70% RAM, TTL = 10-30 phút cho product, `maxmemory-samples 10`. Cần invalidation khi product được update (xóa key hoặc giảm TTL).

**Câu 2:** Redis down -> rate limit không hoạt động -> tất cả request đều pass (insecure). Mitigation: graceful degradation - cho phép 1 request/giây khi Redis down (circuit breaker), hoặc dùng local rate limit làm L1. Tốt hơn: dùng Sentinel để Redis tự động failover.

**Câu 3:** `evicted_keys: 15000` trong 1 phút = 250/giây, rất cao. Cache đang bị overload. Debug: `redis-cli INFO memory`, `redis-cli MEMORY DOCTOR`, `redis-cli --bigkeys`, `redis-cli --hotkeys`. Khắc phục: tăng `maxmemory`, xóa key lớn bằng `SCAN` + `UNLINK`, tối ưu data model (key nhỏ hơn), chọn `maxmemory-policy` phù hợp.

**Câu 4:** `KEYS order:*` là O(N) = O(10 triệu key). Trễ 10-30 giây trên production, block tất cả command. Thay thế: `SCAN 0 MATCH order:* COUNT 1000` (iterative, non-blocking), hoặc lưu danh sách order id trong Set: `SADD orders:list order:1 order:2 ...` để query nhanh hơn.

**Câu 5:** Memory = 10 triệu x 2KB = 20GB + overhead ~30% = ~26GB. Nên để `maxmemory` = 30GB. Persistence: AOF `appendfsync everysec` (mất ~1 giây data), hoặc AOF `appendfsync always` (mất 0 giây, latency +1-2ms/write). Có replica để backup.

**Câu 6:** Redis (local): p50 ~30us, p99 ~300us (gần như không có variance, O(1)). Redis (network): p50 ~200us, p99 ~2ms (network variance, kernel scheduling). PostgreSQL: p50 ~1ms, p99 ~50ms (disk I/O, lock contention, B-tree traversal). Database có nhiều moving parts hơn, variance lớn hơn.

**Câu 7:** Nếu lưu tất cả feed trong Redis: 1 triệu x 50 x (JSON ~500 bytes) = 25GB + overhead = ~30-35GB. Tối ưu: lưu chỉ top 20 posts trong feed (không phải 50), dùng Sorted Set thay String (chỉ lưu post_id, không lưu JSON), dùng pipeline để fetch post chi tiết từ Redis/String. Giảm 80% memory.
