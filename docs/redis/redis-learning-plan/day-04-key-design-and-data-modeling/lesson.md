# Day 4: Key Design & Redis Data Modeling

---

## 1. Mục tiêu bài học

- Thiết kế key naming convention nhất quán, production-ready, có namespace và version
- Chọn TTL strategy phù hợp (fixed, dynamic, sliding) và triển khai jitter để tránh stampede
- Quản lý key cardinality: phân biệt bounded vs unbounded, tránh bùng nổ memory
- Thiết kế tenant-aware keyspace cho multi-tenant SaaS, multi-region
- Sử dụng hash tag chính xác cho Redis Cluster multi-key operation
- Tránh 5 failure mode phổ biến: OOM từ unbounded key, stampede từ fixed TTL đồng loạt, Cluster MULTI/EXEC fail từ thiếu hash tag, thread blocking từ DEL big key, key conflict cross-service

---

## 2. Vì sao cần học chủ đề này

### Shopify incident: key namespace conflict

Shopify gốc thiết kế cache key là `product:{id}` — không có service prefix. Khi mở rộng microservices, service A ghi `product:1001` (price), service B ghi `product:1001` (inventory). Kết quả: inventory overwrite price cache, dashboard hiển thị giá sai. Fix: rename toàn bộ key thành `{shop_id}:product:{id}:price` và `{shop_id}:product:{id}:inventory`. Downtime 40 phút, ảnh hưởng hàng nghìn merchant.

**Bài học**: Key không có namespace là vấn đề "khi nào" chứ không phải "nếu".

### GitHub incident: cardinality bùng nổ

GitHub lưu trữ notification key dạng `notifications:{user_id}:{url_hash}`. Dev muốn expire notification cũ, dùng `SCAN notifications:*` rồi DEL. Scan trả về hàng triệu key — cluster CPU spike 100%, API latency p99 tăng từ 50ms lên 8s trong 12 phút. Root cause: URL trong key tạo cardinality không giới hạn, mỗi unique URL = 1 key mới.

**Bài học**: Raw URL, email, phone trong key là guaranteed OOM path.

### Twitter incident: namespace versioning để rollback nhanh

Twitter cache timeline dạng `timeline:{user_id}`. Khi deploy thay đổi serialization format, họ cần invalidate toàn bộ timeline cache (hàng tỷ key) — không thể làm đồng loạt. Giải pháp: dùng namespace version `v2:timeline:{user_id}`, deploy ghi vào `v3:timeline:{user_id}` đọc từ `v3`. Rollback: switch về `v2` là O(1). Không cần DEL.

**Bài học**: Version trong key, không phải trong value, quyết định tốc độ rollback.

---

## 3. Kiến thức nền tảng (Day 1-3)

| Khái niệm | Cần nhớ |
|-----------|---------|
| Redis single-threaded | Mọi command là atomic, nhưng DEL/HGETALL trên big key block event loop |
| String, Hash, List, Set, Sorted Set | Chọn data structure trước khi thiết kế key |
| Encoding internals (Day 5 sẽ sâu) | Hash nhỏ dùng listpack trong Redis 7, lớn chuyển hashtable — ảnh hưởng memory |
| TTL command | EXPIRE, PEXPIRE, TTL, PTTL, EXPIREAT, PEXPIREAT, PERSIST |

---

## 4. Lý thuyết chi tiết

### 4.1 Key Naming Convention

#### Format chuẩn

```txt
{env}:{service}:{entity}:{id}:{field?}
```

**Ví dụ e-commerce:**

```txt
prod:order-service:order:88421:meta
prod:catalog-service:product:10044:price
prod:cart-service:cart:992:items
staging:user-service:session:a3f8b2
```

#### Nguyên tắc delimiter

- Dùng `:` làm delimiter chính — dễ SCAN, dễ parse
- Không dùng `/`, `.`, `|`, space trong key
- Không dùng UUID v4 nguyên dạng trong key — quá dài, khó debug

#### Key length và memory impact

Redis lưu **toàn bộ key name trong RAM** — cả master và mọi replica.

| Key length | 10M keys overhead | 100M keys overhead |
|-----------|-----------------|------------------|
| 20 bytes  | 200 MB          | 2 GB             |
| 64 bytes  | 640 MB          | 6.4 GB           |
| 128 bytes | 1.28 GB         | 12.8 GB          |

Key dài nhất khuyến nghị: **64 bytes** (bao gồm prefix đầy đủ). Nếu vượt, encode hash thay vì raw value.

**Bad:**
```txt
https://example.com/api/v2/users/profile?session=abc123&ref=email-campaign-winter-sale-2024
```

**Good:**
```txt
user:session:{sha256("https://example.com/api/v2/users/profile?session=abc123&ref=...")}
# → user:session:a3f8b2c1d4e5...
# → max 32 bytes thay vì 200 bytes
```

#### Tên hợp lệ

- Key chỉ chứa byte value 0–255 (ASCII)
- Không chứa newline `\n`, carriage return `\r`
- Max length: **512 MB** (nhưng thực tế key >1KB là anti-pattern)

---

### 4.2 TTL Strategy

#### 4.2.1 Fixed TTL

```bash
SET prod:catalog:product:10044:price 299000 EX 3600
```

- **Ưu điểm**: Predictable, dễ estimate memory, dễ debug
- **Nhược điểm**: Stampede khi nhiều key cùng hết hạn đồng loạt → DB overload đồng thời
- **Dùng khi**: Data ít thay đổi, traffic đều, downstream DB chịu được burst

#### 4.2.2 Dynamic TTL với Jitter

```go
func jitterTTL(base, jitterPct int) time.Duration {
    jitter := float64(base) * jitterPct * (rand.Float64()*2 - 1) // ±jitterPct
    return time.Duration(float64(base) + jitter) * time.Second
}
// base=3600, jitterPct=0.15 → [3060s, 4140s]
```

- **Ưu điểm**: Trải đều expiration, giảm stampede
- **Nhược điểm**: Less predictable memory ceiling
- **Jitter recommended**: ±10-20% của base TTL

#### 4.2.3 Sliding TTL (Touch on access)

```bash
# Mỗi lần đọc → reset TTL (session model)
GET session:user:99231
EXPIRE session:user:99231 1800   # reset về 30 phút
```

- **Ưu điểm**: Active user giữ session sống, inactive user tự expire
- **Nhược điểm**: Tăng write operation mỗi read; nếu dùng replica read thì phải touch trên master
- **Dùng khi**: User session, active connection, rate limit sliding window

#### TTL Stampede Diagram

```txt
Without jitter (fixed TTL at t=0):
Redis:  [key1 expires] [key2 expires] [key3 expires] [ALL AT t=3600]
DB:     ═══════════════ SPIKE ═══════════════

With jitter (±20%):
Redis:  [key1 expires t=3060] [key2 expires t=3720] [key3 expires t=3540]
DB:     ══ SPIKE (small) ══ SPIKE (small) ══ SPIKE (small)
```

#### 4.2.4 TTL for different use cases

| Use case | TTL base | Jitter | Strategy |
|----------|----------|--------|----------|
| Product catalog cache | 1-24h | ±15% | Fixed with jitter |
| User session | 30m | None | Sliding (touch on access) |
| API rate limit counter | 60s | None | Fixed, reset window |
| Featured products leaderboard | 5m | ±5% | Fixed with jitter |
| Inventory stock | 30s | None | Fixed, invalidate on write |

---

### 4.3 Key Cardinality Management

#### Bounded vs Unbounded

**Bounded key** — số lượng key có thể predict được:

```txt
user:100:profile       (1 key per user)
user:100:cart          (1 key per user)
product:200:price      (1 key per product)
```

**Unbounded key** — số lượng key tăng không giới hạn theo user action:

```txt
user:100:notifications:{notif_id}     # Nếu user có 10K notifications → 10K keys
order:88421:events:{event_id}         # Nếu order có 1M events → unbounded
```

#### Hậu quả của unbounded key

1. **Memory không predict được**: 100K users × 500 notifications = 50M keys → OOM
2. **SCAN chậm**: SCAN trên pattern `user:*:notifications:*` quét toàn bộ keyspace
3. **KEYS hoặc DEL khó**: Không thể delete 50M keys cùng lúc
4. **Replication lag**: Nhiều key write nhỏ → nhiều replication command

#### Giải pháp cho unbounded key

**Pattern A: Aggregate vào Hash/Set**

```txt
# Bad: unbounded individual keys
user:100:notifications:abc123
user:100:notifications:def456

# Good: bounded Hash với sliding window
HSET user:100:notifications "abc123" "{...}" "def456" "{...}"
EXPIRE user:100:notifications 86400   # Keep 24h only
```

**Pattern B: Dùng Sorted Set với timestamp score**

```txt
ZADD user:100:events {timestamp} "{event_json}"
# Giữ 30 ngày
ZREMRANGEBYSCORE user:100:events 0 {now - 30*86400}
```

**Pattern C: Date-bucket keys + SCAN/UNLINK cleanup**

TTL không cho biết "key đã cũ hơn 7 ngày" nếu key vẫn còn sống; `TTL` chỉ là thời gian còn lại. Muốn cleanup chính xác, encode ngày vào key hoặc dùng Sorted Set score.

```bash
# Good: bounded by date bucket, cleanup được theo ngày
LPUSH user:100:events:2026-05-21 "{event_json}"
EXPIRE user:100:events:2026-05-21 604800

# Cleanup ngày cũ theo batch, không dùng KEYS
redis-cli --scan --pattern "user:*:events:2026-05-14" |
  xargs -r -n 500 redis-cli UNLINK
```

---

### 4.4 Key Lifecycle

```txt
┌──────────────────────────────────────────────────────────────┐
│  CREATED          ACTIVE          EXPIRING         DELETED  │
│     │                │                │                │     │
│  SET/HSET/       READ/WRITE      TTL=0 or        DEL/    │
│  EXPIRE          on key           lazy free       UNLINK  │
│     │                │                │                │     │
│  [t=0]     ────► [t=T]    ────► [t=T+Δ]   ────► [t=T+Δ+ε]  │
│              active           pending delete      memory   │
│              window           (lazy free)        reclaimed │
└──────────────────────────────────────────────────────────────┘
```

- **Lazy expiration**: Redis không xóa key ngay khi hết TTL. Key bị đọc → Redis thấy TTL=0 → xóa → return nil. Nếu không ai đọc, key tồn tại đến khi active expiration chạy (sample 20 keys/second).
- **UNLINK**: Mark key là deleted trong hashtable, free memory asynchronously. An toàn trên event loop.
- **DEL**: Synchronous, O(N) với N = số field (Hash/List/Set). Block event loop.

---

### 4.5 Namespace Design & Versioning

#### Namespace pattern

```txt
{env}:{service}:{entity}:{id}:{field}

# Layer 1: Environment (prod, staging, dev)
# Layer 2: Service (order, catalog, cart, user)
# Layer 3: Entity (product, order, session)
# Layer 4: ID (numeric, UUID prefix, entity ID)
# Layer 5: Field (optional, metadata, price, inventory)
```

#### Versioned namespace

Thay đổi format dữ liệu hoặc serialization → bump version trong key prefix:

```txt
v1:user:profile:9921        # JSON serialization
v2:user:profile:9921        # Protobuf serialization

v3:timeline:user:9921        # Changed from list to stream
```

**Rollback strategy**:

```go
// Read: try latest version first, fallback
profile, err := getProfile(ctx, "v3", userID)
if err == ErrNotFound {
    profile, err = getProfile(ctx, "v2", userID)  // fallback
}

// Write: always write latest version
setProfile(ctx, "v3", userID, profile)
```

**Mass invalidation**: Bump version prefix → tất cả key cũ tự expire theo TTL hoặc DEL bằng SCAN + UNLINK. Không cần invalidate từng key.

---

### 4.6 Tenant-Aware Key Design (Multi-tenant SaaS)

```txt
# Pattern: tenant-first (đảm bảo tenant isolation)
{tenant_id}:{service}:{entity}:{id}:{field}

prod:shop_abc123:catalog:product:10044:price
prod:shop_abc123:order:88421:meta
prod:shop_xyz789:catalog:product:20088:price

# Cluster-aware: tenant_id trở thành hash tag
{shop_abc123}:catalog:product:10044:price
{shop_abc123}:order:88421:meta
{shop_xyz789}:catalog:product:20088:price
```

**Lợi ích tenant-first**:

1. Dễ delete toàn bộ tenant data: `SCAN MATCH {tenant_id}:*` → UNLINK
2. Tenant isolation trên Redis Cluster (hash tag)
3. Quota per tenant dễ track (INFO MEMORY per key pattern)
4. Tenant migration (move sang cluster khác) dễ hơn

---

### 4.7 Hash Tags cho Redis Cluster

Redis Cluster chia 16384 hash slot = `CRC16(key) % 16384`. Muốn MULTI/EXEC hoặc Lua access nhiều key cùng lúc → tất cả key phải cùng slot.

**Hash tag**: Phần trong key nằm giữa `{` và `}` được dùng để compute slot thay vì toàn bộ key.

```txt
# Không có hash tag → 3 key có thể ở 3 slot khác nhau
order:88421:meta       → slot = CRC16("order:88421:meta") % 16384
order:88421:items      → slot = CRC16("order:88421:items") % 16384
order:88421:shipping   → slot = CRC16("order:88421:shipping") % 16384
# MULTI/EXEC fail vì cross-slot

# Có hash tag → cùng slot
order:{88421}:meta     → CRC16("88421") % 16384
order:{88421}:items    → CRC16("88421") % 16384
order:{88421}:shipping → CRC16("88421") % 16384
# MULTI/EXEC OK
```

**Hash tag anti-pattern — hot slot**:

```txt
# User 1 là customer VIP, tạo 1000 orders
order:{user_1}:meta    # 1000 keys → HOT SLOT

# 9999 users tạo 1 order mỗi
order:{user_2}:meta    # 1 key
...
order:{user_10000}:meta  # 1 key each

# user_1 chiếm 1 slot với 1000 keys, tất cả trỏ vào 1 shard → hot slot
```

**Giải pháp**: Hash tag phải có cardinality đủ cao và đều. Nếu dùng `{user_id}` với skewed distribution → dùng `{tenant_id}` thay thế (thường đều hơn).

---

### 4.8 Redis-First Data Modeling

**Tư duy ngược**: Không design data model giống database rồi map sang Redis. Thay vào đó, nghĩ theo access pattern.

```txt
Access Pattern Analysis:

1. Đọc gì?
   - Single entity? → GET/HSET
   - Nhiều entity? → MGET/MSCAN
   - Sorted list? → ZRANGEBYSCORE

2. Theo key gì?
   - Theo user_id? → user:{id}:*
   - Theo entity_id? → product:{id}:*
   - Theo time range? → events:{timestamp}:*

3. Write pattern?
   - Append only? → List/Stream
   - Overwrite? → String/Hash
   - Atomic? → Lua/Transaction

4. Expiration?
   - All keys same TTL? → EXPIRE sau SET
   - Sliding? → EXPIRE on every access
   - Never? → Primary store
```

---

### 4.9 E-commerce Keyspace Tree (ASCII)

```txt
redis:keyspace:ecommerce
│
├── prod:order-service
│   ├── order:{order_id}:meta        (Hash, TTL=30d)
│   ├── order:{order_id}:items       (Hash, TTL=30d)
│   └── order:{order_id}:status      (String, TTL=30d)
│
├── prod:catalog-service
│   ├── product:{product_id}:price   (String, TTL=1h, jitter±15%)
│   ├── product:{product_id}:stock   (Hash, TTL=30s)
│   ├── category:{cat_id}:products  (Sorted Set, no TTL)
│   └── featured:products            (Sorted Set, TTL=5m)
│
├── prod:cart-service
│   ├── cart:{user_id}:items        (Hash, TTL=7d, sliding)
│   └── cart:{user_id}:meta          (Hash, TTL=7d)
│
├── prod:user-service
│   ├── session:{token}:data        (Hash, TTL=30m, sliding)
│   ├── user:{user_id}:profile      (Hash, TTL=1h)
│   └── user:{user_id}:rate-limit   (String, TTL=60s)
│
└── prod:inventory-service
    ├── stock:{product_id}:qty      (String, TTL=30s)
    └── lock:product:{product_id}   (String NX PX 30s)
```

---

## 5. Trade-off Analysis

### Trade-off 1: Coarse-grained key vs Fine-grained key

| Tiêu chí | Coarse-grained | Fine-grained |
|----------|---------------|-------------|
| **Mô tả** | `user:9921` (1 Hash chứa tất cả) | `user:9921:name`, `user:9921:email`, ... |
| **Read single field** | HGET → lấy 1 field nhưng load cả Hash | GET → O(1), optimal |
| **Read all fields** | HGETALL → 1 round-trip | MGET → N round-trip (hoặc pipeline) |
| **Memory** | Key name overhead thấp | Key name overhead cao |
| **TTL granularity** | 1 TTL chung | Mỗi key có TTL riêng |
| **Atomicity** | HGETALL atomic | Multi-key không atomic (trừ Cluster hash tag) |
| **Use case** | Entity đọc full, ít update field | Entity đọc field riêng lẻ, TTL khác nhau |
| **Dùng khi** | Profile, settings | Session field, rate limit counter |

### Trade-off 2: One big Hash vs Many small keys

| Tiêu chí | One big Hash | Many small keys |
|----------|-------------|----------------|
| **MGET/MSET** | Field-level | Full key-level |
| **Memory** | Hashtable overhead khi >512 fields | Key metadata overhead cho mỗi key |
| **Encoding** | Chuyển listpack→hashtable khi vượt threshold | String luôn raw/ int |
| **TTL** | Single TTL hoặc lua script per-field | Mỗi key EXPIRE riêng |
| **Big key risk** | Có (Hash >10K fields) | Không |
| **SCAN** | HSCAN (iterator) | SCAN (iterator) |
| **Use case** | User profile, product catalog | Rate limit, session fields |
| **Dùng khi** | Access full object >80% | Access partial fields >50% |

### Trade-off 3: Fixed TTL vs Dynamic TTL

| Tiêu chí | Fixed TTL | Dynamic TTL (jitter) |
|----------|-----------|---------------------|
| **Stampede** | Cao — cùng expiration time | Thấp — randomized |
| **Predictability** | High | Medium |
| **Memory ceiling** | Tính được | ±jitter range |
| **Downstream DB load** | Spike đồng loạt | Distributed |
| **Use case** | Rate limit window, batch job | Cached data reads |
| **Dùng khi** | Traffic đều, downstream chịu được spike | Any read-heavy cache |
| **Jitter size** | N/A | ±10-20% recommended |

### Trade-off 4: DEL key vs EXPIRE key

| Tiêu chí | DEL | EXPIRE |
|----------|-----|--------|
| **Timing** | Synchronous, immediate | Background, lazy hoặc periodic |
| **CPU impact** | O(N) blocking — risky trên event loop | Negligible |
| **Memory reclaim** | Immediate (sau lazy free) | On next access hoặc active expiration |
| **Atomicity** | Irreversible | Có thể PERSIST để undo |
| **Use case** | Chủ động xóa dữ liệu; tenant migration; schema change | Automatic expiration; session; cache |
| **Big key DEL** | Nguy hiểm — block event loop | Không block — key tự xóa |
| **Dùng khi** | Key nhỏ (<1K fields), cần immediate cleanup | Hầu hết cache use case; big key |

### Trade-off 5: Cache invalidation by key vs by namespace version

| Tiêu chí | Per-key invalidation | Namespace version bump |
|----------|---------------------|----------------------|
| **Granularity** | Single key | Toàn bộ service data |
| **Implementation** | DELETE trên mỗi write | Bump version prefix, DEL toàn bộ vN:* |
| **Speed** | O(1) per key | O(keys scanned) |
| **Consistency** | Precise — chỉ xóa key cần xóa | Coarse — xóa cả key không thay đổi |
| **Rollback speed** | Phải DELETE key cũ | Switch version prefix = instant |
| **Use case** | Write-through cache; update-by-key | Schema change; serialization format change; mass invalidation |
| **Dùng khi** | Thay đổi 1 record | Thay đổi toàn bộ service |

---

## 6. Best Solution & Best Practices

### Recommended Key Naming Convention

```txt
{env}:{service}:{entity}:{id}:{field?}

# Examples:
prod:order-service:order:88421:meta
prod:catalog-service:product:10044:price
prod:user-service:session:a3f8b2c1:data
staging:rate-limit:api:{client_id}:count
```

### TTL Best Practices

1. **Luôn đặt TTL** — không có TTL = memory leak tiềm tàng
2. **Luôn có jitter** cho read-heavy cache: `TTL = base * (1 + uniform(-jitter, +jitter))`
3. **Sliding TTL** cho session: `EXPIRE` sau mỗi `GET`/`SET`
4. **Fixed TTL không jitter** cho rate limit, batch windows
5. **TTL alignment**: align TTL với business cycle (hourly, daily, weekly)

### Hash Tag Best Practices

1. **Chỉ dùng khi cần multi-key operation** (MULTI/EXEC, Lua, pipeline với atomic)
2. **Hash tag phải có cardinality cao và đều**: `{order_id}`, `{user_id}`, `{tenant_id}`
3. **Không dùng hash tag cố định**: `order:{123}` mọi key → hot slot
4. **Đặt hash tag ở vị trí có cardinality cao nhất**

### Versioning Best Practices

1. **Version trong key prefix**, không phải trong value
2. **Dùng integer version**: `v1`, `v2`, `v3` (dễ so sánh hơn string)
3. **Support dual-read**: đọc version mới trước, fallback version cũ
4. **Single version active tại một thời điểm**: không đọc từ 2 version cùng lúc

### Anti-patterns cần tránh

| Anti-pattern | Vấn đề | Giải pháp |
|-------------|--------|-----------|
| Raw URL/email/phone trong key | Cardinality unbounded → OOM | Hash URL/email trước khi làm key |
| Không có TTL | Memory leak | Luôn EXPIRE khi SET cache |
| DEL big Hash/List/Set | Block event loop 5+ giây | UNLINK thay vì DEL |
| KEYS * trên prod | O(N) scan → event loop block | SCAN với COUNT limit |
| Hash tag với low cardinality | Hot slot → 1 shard quá tải | Thiết kế hash tag có cardinality cao |
| Lưu PII raw trong key | Compliance violation (GDPR, etc.) | Hash/anonymize trước khi dùng làm key |
| Inconsistent namespace giữa services | Key conflict, khó track | Enforce convention qua code review, linter |
| Version trong value thay vì key | Không thể invalidate by namespace | Move version vào key prefix |
| Không distinguish env (prod/staging) | Staging ghi đè prod | Always prefix `{env}:` |

---

## 7. Performance Considerations

### Key Length Impact

Redis lưu key name dưới dạng `sds` (Simple Dynamic String). Mỗi key có overhead:

- Key metadata (hashtable entry): **~56 bytes** overhead
- SDS string: **key length + 1 null byte**
- Delimiter `:` không tốn thêm overhead, chỉ là bytes trong string

```txt
# 100M keys × avg 50 bytes key name = 5GB key name storage (ngoài data)
# vs 100M keys × avg 20 bytes = 2GB
```

**Recommendation**: Giữ key name ≤ 64 bytes.

### DEL vs UNLINK Performance

```txt
DEL big_hash (1M fields):
  - O(N) = O(1M)
  - Blocking: 5-15 giây event loop
  - Replication: replicate DELETE command

UNLINK big_hash (1M fields):
  - O(1) = return immediately
  - Async free: background thread free memory
  - Replication: replicate UNLINK command (khác DEL)
```

`UNLINK` luôn an toàn. Nếu key < `lazyfree-lazy-user-del` threshold (default: empty threshold = always async via UNLINK, sync via DEL), dùng UNLINK.

### SCAN vs KEYS

```txt
KEYS pattern:
  - O(N) to scan entire keyspace
  - Returns all results in one blocking call
  - BLOCKS event loop for entire duration
  - N = total keys in instance (not just matching pattern)

SCAN cursor [MATCH pattern] [COUNT count] [TYPE type]:
  - O(1) per call
  - Returns ~count keys per call
  - Non-blocking (yield to event loop between chunks)
  - Cursor-based: iterate until cursor returns 0
  - COUNT is hint, not guarantee
```

**Production rule**: Dùng SCAN trong loop. COUNT = 100–1000 tùy key size.

### TTL Stampede p95/p99 Impact

```txt
Scenario: 100K cached items, TTL=3600s, no jitter
- All expire at t=3600
- At t=3600: 100K cache miss → 100K DB queries
- DB latency p99 = 50ms → queue time = 5000 seconds
- Effective p99 cache latency = 5 seconds

Scenario: same 100K items, TTL=3600±20% jitter
- Expire spread over t=[2880, 4320]
- Peak expiration rate: ~8K keys/minute
- DB queries spread: manageable
- p99 latency: ~50-100ms
```

### Hash Tag Hot Slot Impact

```txt
Cluster 6 nodes (3 shards × 2 replicas)
Hash tag = "{user_id}" với skewed distribution

- Normal: ~5461 slots/node
- Hot slot user_1: all 1000 order keys cùng slot 8500
- Node chứa slot 8500: CPU 80%, latency p99 spike 500ms
- Other nodes: idle

Benchmark without hot slot:
  - p50: 2ms, p95: 8ms, p99: 15ms

Benchmark with hot slot (10% traffic to hot slot):
  - p50: 2ms, p95: 12ms, p99: 500ms
```

---

## 8. Production Failure Modes

### FM1: Unbounded Key Growth → OOM

**Nguyên nhân**: Key chứa user-generated content (URL, notification ID, event ID) không giới hạn.
**Dấu hiệu**: `INFO memory` used_memory tăng đều, không giảm dù có TTL; `INFO keyspace` key count tăng liên tục.
**Debug**: `SCAN 0 COUNT 100` → phân tích pattern key name; `MEMORY USAGE key`, `OBJECT ENCODING key` kiểm tra footprint. `DEBUG OBJECT` chỉ dùng trên dev/staging vì có thể bị disable trên managed Redis.
**Phòng ngừa**: Review key design trước khi deploy; set memory limit (`maxmemory`); alert trên key count growth rate.

### FM2: Cache Stampede (Fixed TTL Synchronized Expiration)

**Nguyên nhân**: Nhiều key cùng TTL, hết hạn đồng thời → tất cả request hit DB cùng lúc.
**Dấu hiệu**: Periodic latency spike theo chu kỳ TTL; DB CPU spike đồng thời; downstream service timeout.
**Debug**: So sánh `INFO stats` `expired_keys` counter với timestamp của latency spike.
**Phòng ngừa**: TTL jitter ±10-20%; probabilistic early expiration (stale-while-revalidate).

### FM3: Cluster MULTI/EXEC Fail (Cross-Slot Keys)

**Nguyên nhân**: MULTI/EXEC hoặc Lua gọi nhiều key không cùng hash slot.
**Dấu hiệu**: `CROSSSLOT` error trong response; transaction fail không rõ lý do; intermittent failure.
**Debug**: `CLUSTER KEYSLOT key` kiểm tra slot của từng key; verify hash tag có mặt và đúng.
**Phòng ngừa**: Thiết kế hash tag ngay từ đầu; unit test kiểm tra slot; dùng single-key operation thay vì multi-key transaction khi có thể.

### FM4: DEL Big Key Blocking Event Loop

**Nguyên nhân**: DEL Hash/List/Set với hàng trăm nghìn elements chạy trên event loop.
**Dấu hiệu**: Redis latency spike đột ngột, connected clients timeout, replica lag spike.
**Debug**: `SLOWLOG GET 10` → DEL command xuất hiện với microseconds cao; `DEBUG SLEEP 5` để test.
**Phòng ngừa**: Luôn dùng UNLINK thay vì DEL; set `lazyfree-lazy-user-del yes`; break big collection thành chunks.

### FM5: Service A Overwrites Service B Keys (Missing Namespace)

**Nguyên nhân**: 2 service dùng chung pattern key không có service prefix.
**Dấu hiệu**: Data corruption không rõ nguyên nhân; inconsistency giữa service response và database; intermittent bug.
**Debug**: So sánh `SCAN` pattern của từng service; kiểm tra key prefix trong code.
**Phòng ngừa**: Enforce naming convention qua code review; key naming linter; shared key registry.

---

## 9. Real-world Examples

### Shopify: Namespace per shop_id

Shopify dùng Redis làm cache chính cho hàng triệu merchant. Key design:

```txt
shop:{shop_id}:product:{product_id}:cache
shop:{shop_id}:order:{order_id}:meta
shop:{shop_id}:inventory:{product_id}:qty
```

- `shop_id` đóng vai trò namespace + tenant isolation + hash tag (Cluster)
- Mỗi shop có isolated keyspace riêng
- `shop:{shop_id}:*` SCAN → delete toàn bộ data khi shop bị suspend

### Uber: Hash tag `{trip_id}` cho trip state

Uber cần MULTI/EXEC để update trip state atomic (location, status, fare):

```txt
trip:{trip_id}:location    # {trip_id} là hash tag
trip:{trip_id}:status
trip:{trip_id}:fare
trip:{trip_id}:driver-location
```

- `{trip_id}` đảm bảo tất cả key cùng slot → atomic transaction
- trip_id có cardinality rất cao (hàng triệu trips/day) → distribution đều
- Không dùng `{driver_id}` vì driver có thể có hundreds active trips (skewed)

### Twitter: Versioned namespace cho timeline cache

Twitter timeline cache (2012-2018 architecture):

```txt
v2:timeline:home:{user_id}
v2:timeline:user:{user_id}
v2:timeline:mentions:{user_id}
```

- Khi thay đổi ranking algorithm: viết vào `v3:timeline:*`, đọc `v3`
- Rollback: switch về `v2` → 0 DEL, 0 latency spike
- Version bump là instant (just change prefix)
- Toàn bộ v2 cache tự expire theo TTL

### GitHub: TTL jitter cho session cache

GitHub dùng Redis làm session store cho hàng triệu developer:

```txt
github:session:{session_token}
```

- TTL = 30 phút + uniform(-6, +6) phút jitter
- Sliding TTL: `EXPIRE` sau mỗi request
- Session token là opaque UUID, không chứa PII
- Max 1 session per user, bounded key count

---

## 10. Common Pitfalls

| Pitfall | Tại sao xảy ra | Hậu quả | Fix |
|---------|---------------|---------|-----|
| Dùng `KEYS *` trên prod | Dev quen dùng trong dev, quên performance | Event loop block, latency spike | Luôn dùng SCAN |
| Không có TTL → memory leak | Cache-aside implement sai | OOM, eviction không kiểm soát | Luôn EXPIRE khi SET |
| DEL big key → block | Lập trình viên quen `DEL` | Event loop blocked 5+ giây | Dùng UNLINK |
| Hash tag với cardinality thấp | Dùng `{tenant}` khi 1 tenant >50% traffic | Hot slot → 1 shard quá tải | Chọn hash tag có cardinality đều |
| Lưu PII raw trong key | Tiện debug | GDPR violation, data breach risk | Hash/anonymize PII |
| Inconsistent namespace | Mỗi team tự đặt tên | Key conflict, khó maintain | Shared key registry, linter |
| Version trong value | Thiết kế sai ban đầu | Không thể namespace invalidation | Refactor: version vào key prefix |
| Không test hash tag trên Cluster | Thiết kế local, deploy lên Cluster | CROSSSLOT error production | CI test: verify all related keys same slot |

---

## 11. Câu hỏi tự kiểm tra

**Câu 1.** Bạn có 2 service: order-service và payment-service. Cả 2 đều cache order data. Order-service dùng key `order:{id}:data`, payment-service cũng dùng `order:{id}:data`. Sau 6 tháng, bạn phát hiện payment cache data bị overwrite bởi order cache data (format khác nhau). Phân tích root cause và đề xuất fix.

<details>
<summary>Đáp án</summary>

**Root cause**: Thiếu service namespace. Cả 2 service dùng chung key pattern không phân biệt được service nào ghi.

**Fix**:
```txt
# Trước
order:{order_id}:data        # Conflict!

# Sau
order-service:order:{order_id}:data
payment-service:order:{order_id}:data
```
</details>

---

**Câu 2.** Bạn thiết kế notification system: `notif:{user_id}:{notification_id}`. Mỗi user có thể nhận hàng nghìn notification. Sau 1 tháng, Redis báo OOM. Phân tích và đề xuất redesign.

<details>
<summary>Đáp án</summary>

**Root cause**: `{notification_id}` tạo unbounded cardinality. Số notification không giới hạn → số key không giới hạn.

**Redesign options**:
1. **Dùng Hash**: `HSET notif:{user_id} {notif_id} {payload}` → bounded key count per user. Add TTL trên hash.
2. **Dùng Sorted Set**: `ZADD notif:{user_id} {timestamp} {payload}` → tự động prune bằng `ZREMRANGEBYSCORE`.
3. **Dùng List với LPUSH/LTRIM**: Keep last N notifications.

**Recommendation**: Sorted Set với timestamp score, TTL = 30 days, nightly `ZREMRANGEBYSCORE` để trim.
</details>

---

**Câu 3.** Bạn cần MULTI/EXEC update 3 key cùng order: `order:88421:meta`, `order:88421:items`, `order:88421:shipping`. Chạy trên Redis Cluster 6 nodes. MULTI/EXEC fail. Tại sao và fix như thế nào?

<details>
<summary>Đáp án</summary>

**Tại sao**: 3 key không có hash tag → Redis compute slot cho toàn key → 3 key có thể nằm trên 3 slot khác nhau → CROSSSLOT error.

**Fix**: Thêm hash tag vào order ID:
```txt
order:{88421}:meta
order:{88421}:items
order:{88421}:shipping
# CRC16("88421") % 16384 = slot_id → tất cả cùng slot
```

**Lưu ý**: Hash tag phải có cardinality cao. Nếu dùng `{order_status}` làm hash tag (chỉ có vài giá trị: pending/paid/cancelled) → hot slot.
</details>

---

**Câu 4.** So sánh DEL và UNLINK. Khi nào dùng DEL thay vì UNLINK?

<details>
<summary>Đáp án</summary>

| Scenario | Command |
|----------|---------|
| Key nhỏ (< 100 elements) | UNLINK hoặc DEL đều OK |
| Key lớn (Hash/List > 10K elements) | **UNLINK bắt buộc** |
| Cần synchronous (đảm bảo xóa ngay trước khi tiếp tục) | DEL (nhưng block event loop) |
| Redis config `lazyfree-lazy-user-del no` | DEL đồng bộ, UNLINK async |
| Replication environment | Cả 2 đều replicate command |

**Khi dùng DEL**: Khi cần đảm bảo key không tồn tại trước khi thực hiện bước tiếp theo trong cùng operation, và key nhỏ. Trong mọi trường hợp khác: UNLINK.
</details>

---

**Câu 5.** Bạn cần invalidate toàn bộ 50 triệu product cache khi thay đổi pricing algorithm. Mỗi key có format `prod:catalog:product:{id}:price`. Bạn sẽ làm thế nào để invalidation nhanh nhất mà không gây latency spike?

<details>
<summary>Đáp án</summary>

**Phương án 1 — Versioned namespace (recommended)**:
```txt
# Trước: prod:catalog:product:{id}:price
# Sau:  prod:v2:catalog:product:{id}:price
```
- Bump version prefix → instant switch, 0 DEL
- 50 triệu key cũ tự expire theo TTL hoặc scan + UNLINK background
- Rollback: switch về v1 → instant

**Phương án 2 — SCAN + UNLINK chunked**:
```lua
-- Chạy background, 1000 key mỗi lần, không block
local cursor = 0
repeat
    cursor = redis.call('SCAN', cursor, 'MATCH', 'prod:catalog:product:*:price', 'COUNT', 1000)
    -- UNLINK batch trong background thread
until cursor == '0'
```

**Không bao giờ dùng**: `KEYS prod:catalog:product:*` (block event loop 50M keys).
</details>

---

**Câu 6.** TTL jitter cụ thể hoạt động như thế nào? Tính TTL với base=3600s, jitter=15%.

<details>
<summary>Đáp án</summary>

```go
func jitterTTL(base int, jitterPct float64) int {
    // ±jitterPct của base
    jitter := int(float64(base) * jitterPct * (rand.Float64()*2 - 1))
    return base + jitter
}
// base=3600, jitter=0.15
// jitter ∈ [-540, +540]
// TTL ∈ [3060, 4140] seconds
```

**Effect**:
- 1000 keys với base=3600, no jitter: all expire tại t=3600
- 1000 keys với base=3600, jitter=±15%: expire spread trong 18 phút
- Peak expiration rate: giảm từ 1000 keys trong cùng một thời điểm → ~100 keys/phút

**Formula**: `TTL = base × (1 + random.uniform(-jitter, +jitter))`
</details>

---

**Câu 7.** Bạn có multi-tenant SaaS với 10K tenants, mỗi tenant có 100K products. Thiết kế key cho product cache sao cho:
- Tenant isolation (mỗi tenant có thể bị xóa independent)
- Hash tag đúng để MULTI/EXEC atomic
- Key không chứa PII
- TTL 1h với jitter

<details>
<summary>Đáp án</summary>

```txt
# Key format
{env}:catalog:{tenant_id}:product:{product_id}:price
# Ví dụ:
prod:catalog:tenant_a1b2c3:product:10044:price

# Hash tag: dùng {tenant_id}
order:{tenant_id}:product:{product_id}     # MULTI/EXEC atomic
inventory:{tenant_id}:product:{product_id} # MULTI/EXEC atomic

# TTL
base_ttl = 3600  # 1h
jitter = ±15%    # [3060s, 4140s]
```

**Design decisions**:
1. `{tenant_id}` là hash tag → cùng slot per tenant
2. `{tenant_id}` không phải PII (dùng internal ID, không phải tenant name/email)
3. `tenant_id` thường đều distribution → không hot slot
4. Xóa tenant: `SCAN MATCH {tenant_id}:* COUNT 1000` → UNLINK
5. Số key tối đa: 10K tenants × 100K products = 1B keys → **KHÔNG dùng per-product key**! Nên dùng Hash: `catalog:{tenant_id}:products` (Hash với 100K fields) hoặc cache page-based
</details>
