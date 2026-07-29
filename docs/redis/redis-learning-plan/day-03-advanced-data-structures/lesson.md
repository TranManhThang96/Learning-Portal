# Day 3: Advanced Data Structures

## 1. Mục tiêu bài học

- Phân biệt được Bitmap, HyperLogLog, Geospatial, Bloom Filter — biết khi nào dùng cái nào thay vì dùng Set/String
- Tính toán memory footprint chính xác: 1B unique users lưu bằng Set vs Bitmap vs HyperLogLog chênh nhau 4-5 orders of magnitude
- Implement DAU tracker, unique visitor counter, geo proximity search bằng TypeScript + ioredis
- Đọc được false positive rate, error rate, latency profile của từng data structure để đưa ra production decision đúng
- Tránh các anti-pattern phổ biến: dùng HyperLogLog cho exact count, dùng Bitmap cho sparse user ID, dùng GEORADIUS thay vì GEOSEARCH

---

## 2. Vì sao cần học chủ đề này

### Bối cảnh thực tế

Twitter (2013) gặp vấn đề: họ cần track 500M+ users xem ai đã interact với tweet nào mỗi ngày. Dùng Set — mỗi user_id 8 bytes × 500M users = 4GB per tweet. Không khả thi.

Giải pháp: Bitmap. Với user_id là auto-increment integer (dense), dùng 1 bit per user. 500M bits = ~60MB per day, giảm 98% memory. BITCOUNT O(N) nhưng N là số bytes chứ không phải số bits — nên thực tế rất nhanh.

Uber gặp vấn đề: driver location update 5 giây/lần, 2 triệu drivers. GEOSEARCH với radius 5km trả về kết quả trong <5ms — dùng sorted set backed by geohash 52-bit. Nếu dùng PostGIS, mỗi query PostgreSQL mất 50-200ms ở scale này, không đủ real-time cho matching.

Medium gặp vấn đề: "bạn đã đọc bài này chưa?" với 50 triệu users × hàng triệu articles. Lưu full history = quá lớn. Dùng Bloom Filter — mỗi user một filter nhỏ, false positive rate <1%, memory chỉ ~10KB per user thay vì MB.

**Nếu dùng sai structure:**
- Dùng Set đếm unique visitors: 1 triệu unique = ~64MB RAM. HyperLogLog chỉ ~12KB, chênh 5000x.
- Dùng Bitmap cho user_id UUID (sparse): 1 triệu UUID sparse = Bitmap ~125MB. Set chỉ ~50MB.
- Dùng HyperLogLog cho payment counter: bạn sẽ báo "xấp xỉ 1,234,567" thay vì exact — không ai chấp nhận.

---

## 3. Kiến thức nền cần có

Từ Day 2, cần nắm vững:

- **String**: SET, GET, INCR, INCRBY — Redis String dùng SDS (Simple Dynamic String), overhead ~23 bytes/key
- **Set**: SADD, SISMEMBER, SMEMBERS, SCARD, SUNION/SINTER — backed by intset (khi <512 elements, all integers) hoặc hashtable
- **Sorted Set**: ZADD, ZRANGE, ZRANK — backed by skiplist + hashtable
- **Hash**: HSET, HGET, HINCRBY — phù hợp cho object cache, không phải cho counting
- **Memory overhead**: key name (~23 bytes min) + value overhead + pointer overhead

Key insight: Bitmap, HyperLogLog, Geospatial **đều backed by String** (raw bytes) hoặc **Sorted Set** (Geospatial). Chúng không phải data type riêng — chúng là cách interpret bit-level/score-level data.

---

## 4. Nội dung lý thuyết từ cơ bản đến chi tiết

### 4.1 Bitmap

#### Cơ chế

Bitmap là String được interpret như một mảng bit. Mỗi bit có index = offset.

```
Key: user:active:20260519
Value: [bit0][bit1][bit2]...[bitN]

User 123 login ngày hôm nay → SETBIT user:active:20260519 123 1
→ User 123 đang active → bit ở offset 123 = 1
```

**Memory tính như thế nào:**
- 1 bit = 1 bit storage
- Redis tối thiểu 1 byte per key overhead + actual string bytes
- 1 triệu bits = 125KB string data
- Overhead key + encoding = thêm ~50 bytes

**Offset là gì:** offset chính là user_id. Nếu user_id dense (1, 2, 3, 4, ..., 1M) thì memory hiệu quả. Nếu sparse (UUID với giá trị max = 2^64) thì Redis phải allocate đủ bytes cho offset đó — tốn memory khủng khiếp.

**Commands:**

```txt
SETBIT key offset value    # O(1), offset 0-based
GETBIT key offset         # O(1)
BITCOUNT key [start end]  # O(N) bytes, N = số bytes chứa bits
BITOP AND destkey key1 key2  # O(N) bytes, merge nhiều bitmap
BITPOS key bit [start] [end] # Tìm vị trí bit đầu tiên = 0 hoặc 1
```

**BITCOUNT internals:** Redis scan toàn bộ string theo byte, dùng SIMD instructions (nếu CPU hỗ trợ) để count bits nhanh. O(N) với N = byte length, không phải bit length. Với 1 triệu users (125KB), BITCOUNT mất ~0.1ms.

**BITOP để compute MAU/WAU:**
```txt
# MAU = OR 30 ngày liên tiếp
BITOP OR mau:active user:active:20260501 user:active:20260502 ... user:active:20260530
BITCOUNT mau:active
```

#### Analogy

Hãy tưởng tượng một khách sạn 10 tầng, mỗi tầng 100 phòng. Bitmap như bảng đèn LED: phòng nào có khách thì đèn sáng. BITCOUNT = đếm số đèn sáng. BITOP OR = hợp nhất bảng đèn nhiều ngày để xem có bao nhiêu phòng từng có khách trong tháng.

---

### 4.2 HyperLogLog

#### Cơ chế

HyperLogLog (HLL) là thuật toán probabilistic cardinality estimation. Nó **đếm số lượng unique elements** mà **không lưu từng element**.

**Fixed memory: ~12KB** bất kể cardinality (1K hay 1B elements). Error rate ~0.81%.

**Thuật toán cơ bản:**
1. Hash mỗi element bằng 64-bit hash
2. Đếm số leading zeros trong hash
3. Dùng maximum số leading zeros để estimate cardinality: `2^max_leading_zeros`

**Lý do lỗi 0.81%:** HLL dùng 2^14 = 16384 registers (registers = buckets). Mỗi register lưu 6 bits (max leading zeros = 63). Memory = 16384 × 6 bits = 12KB.

```txt
PFADD key element [element ...]   # O(1) amortized
PFCOUNT key [key ...]             # O(N) với N = số keys, merge trước khi count
PFMERGE destkey sourcekey [sourcekey ...]  # Merge nhiều HLL
```

**PF = Pi Fonseca**, tên hai nhà phát minh ra thuật toán này (2007).

**Khi nào PFCOUNT chậm:** Nếu merge nhiều keys cùng lúc (PFCOUNT key1 key2 key3...), Redis phải merge registers trước. 3-5 keys thì <1ms. 100 keys thì ~10-50ms. Design key structure để tránh merge quá nhiều.

**Điều quan trọng:**
- Không thể đếm exact
- Không thể remove element (HLL không có reverse operation)
- PFCOUNT trả về approximate — error rate cố định 0.81%
- Dùng PFADD nhiều lần cùng element trong cùng HLL chỉ count 1 lần (idempotent về mặt estimation)

---

### 4.3 Geospatial

#### Cơ chế

Redis Geospatial backed by Sorted Set. Mỗi member có score = geohash của (longitude, latitude).

**Geohash 52-bit precision:**
- Encode longitude (-180 to 180) và latitude (-90 to 90) thành 52-bit integer
- Accuracy: ~0.59cm ở equator — đủ cho mọi use case thực tế
- Score trong sorted set là geohash integer

```txt
GEOADD key longitude latitude member [longitude latitude member ...]  # O(log N)
GEOSEARCH key FROMLONLAT longitude latitude BYRADIUS radius unit     # O(N + log M)
GEOSEARCH key BYBOX width height unit                                 # O(N + log M)
GEODIST key member1 member2 [unit]                                    # O(log N)
GEOPOS key member [member ...]                                       # O(log N)
GEORADIUS key ...                            # DEPRECATED từ Redis 6.2
```

**GEOSEARCH thay GEORADIUS:**
- GEORADIUS bị deprecate từ Redis 6.2
- GEOSEARCH hỗ trợ cả BYRADIUS (circular) và BYBOX (rectangular)
- Cú pháp GEOSEARCH linh hoạt hơn nhưng cần thời gian adapt

**Radius vs Box:**
- BYRADIUS: tìm trong hình tròn, dùng khi cần khoảng cách đường bộ
- BYBOX: tìm trong hình chữ nhật, nhanh hơn 2-3x khi chỉ cần approximate

**BYRADIUS complexity O(N + log M):**
- N = tất cả members trong key
- M = members trong bounding box (pre-filter bằng geohash)
- Với 1000 drivers và radius 5km: N=1000, M ~50 → rất nhanh
- Với radius lớn (100km+): M tăng, có thể scan toàn bộ members

**Đơn vị distance:** m (meters), km, mi (miles), ft (feet)

---

### 4.4 Streams Overview

Streams là topic-queue hybrid. Chi tiết Day 18, ở đây chỉ overview:

```txt
XADD stream-name * field value [field value ...]   # Append, auto-generated ID
XLEN stream-name                                    # Length
XREAD COUNT 10 STREAMS stream-name $               # Read mới nhất (blocking optional)
XREADGROUP GROUP g1 c1 COUNT 10 STREAMS stream-name >  # Consumer group
XACK stream-name group id                          # Acknowledge
```

**Key characteristics:**
- Append-only log, tự động trim
- ID-based ordering (timestamp + sequence)
- Consumer group cho load balancing
- Backed by radix tree (memory efficient cho range query)
- Không nhầm với Pub/Sub — Streams có persistence và replayability

---

### 4.5 Bloom Filter (RedisBloom Module)

#### Cơ chế

Bloom Filter là probabilistic data structure kiểm tra **"element này có trong set không"**.

**Tính chất:**
- **False positive possible**: báo "có" nhưng thực tế không có
- **False negative impossible**: nếu báo "không" thì chắc chắn không có
- Không thể remove element (chỉ set thêm bit, không clear được bit đã set)

**Cấu trúc:**
- Mảng m bits, khởi tạo = 0
- K hash functions, mỗi hash trả về index trong [0, m)
- ADD: set bit tại K positions
- EXISTS: check tất cả K bits — nếu bất kỳ bit nào = 0 → chắc chắn không có

**Memory vs False Positive Rate:**

| m bits/item | k hash | False Positive Rate | Memory per 1M items |
|-------------|--------|----------------------|----------------------|
| 10 | 7 | 1.25% | ~1.25 MB |
| 13 | 9 | 0.25% | ~1.6 MB |
| 16 | 11 | 0.005% | ~2 MB |

**Cuckoo Filter** (module riêng, không phải Bloom Filter):
- Hỗ trợ remove
- Thay bit array bằng fingerprint table
- Memory ~1.2x Bloom nhưng supports deletion

**RedisBloom commands:**
```txt
BF.ADD key item           # O(K), K = số hash functions
BF.EXISTS key item       # O(K)
BF.MADD key item [item]  # Batch add
BF.INSERT key ERROR 0.001 CAPACITY 100000 ITEMS key1 key2  # Create with config
BF.INFO key              # Size, capacity, false positive rate
```

**Use case chuẩn:** Cache anti-penetration. Thay vì query database để kiểm tra "product có tồn tại không" mỗi lần cache miss, dùng Bloom Filter trước. Nếu BF báo không có → skip DB hoàn toàn.

---

### 4.6 Count-Min Sketch (CMS)

**Use case:** Frequency estimation — "element X xuất hiện bao nhiêu lần?"

```txt
CMS.INCRBY key item increment [item increment ...]   # O(w) với w = width
CMS.QUERY key item                                    # Estimated count
CMS.MERGE destkey numkeys key [key ...] [WEIGHTS w...]  # Merge
```

**Cơ chế:** 2D array [d rows][w columns], mỗi row có hash function khác nhau. Count = minimum của tất cả rows tại position.

**Trade-off:**
- Luôn overestimate (count thực = min của tất cả rows)
- Không underestimate (nếu min = X, thực tế ≥ X)
- Memory cố định: d × w bits

**Use case:** Top-K frequent items, rate limiting per user/IP, query frequency tracking.

---

### 4.7 Top-K

```txt
TOPK.ADD key item [item ...]     # O(K log W)
TOPK.QUERY key item               # 1 nếu có trong top-K, 0 nếu không
TOPK.LIST key                    # Full top-K list
TOPK.INFO key                    # K, width, depth
```

**Use case:** Real-time trending topics, top-N most sold products, top-K API endpoints by request count.

**So sánh với CMS:**
- CMS: "element X xuất hiện bao nhiêu lần?"
- Top-K: "Những element nào là top-K?"

---

## 5. Trade-off Analysis

### 5.1 Bitmap vs Set cho user activity tracking

| Tiêu chí | Bitmap | Set |
|----------|--------|-----|
| Memory (dense user ID) | ~0.125 bytes/user (1 bit) | ~50-100 bytes/user |
| Memory (sparse user ID) | **Cực kỳ tệ** — tỷ bits nếu max ID = UUID | ~50-100 bytes/user |
| Query DAU | BITCOUNT O(N bytes) — rất nhanh | SCARD O(1) — nhanh |
| Query MAU | BITOP OR + BITCOUNT — O(N×30 bytes) | SUNION 30 keys — O(N×30) nhưng nặng |
| Storage user list | Không lấy được danh sách users | SMEMBERS — được |
| Implementation complexity | Cần convert user_id → offset | Trực tiếp |
| Sharding support | Hash tag cần thiết nếu dùng Cluster | Hash tag cần thiết |

**Khi nào dùng Bitmap:** User ID dense (auto-increment, sequential), cần BITCOUNT/BITOP analysis, cardinality > 100K, activity tracking (DAU/MAU/WAU), feature flags.

**Khi nào dùng Set:** User ID sparse, cần lấy danh sách members, cardinality < 10K, membership testing với exact result.

---

### 5.2 HyperLogLog vs Exact Count

| Tiêu chí | HyperLogLog | Exact (Set/Hash) |
|----------|-------------|-----------------|
| Memory | ~12KB cố định | ~50-100 bytes per unique |
| Accuracy | ~0.81% error | 100% exact |
| Add element | O(1) amortized | O(1) amortized |
| Remove element | **Không supported** | O(1) |
| Count | PFCOUNT O(N keys merge) | SCARD O(1) |
| Scale 1B unique | ~12KB | ~64-100GB |
| Use case phù hợp | Unique visitors, API calls, DAU estimates | Payment count, inventory, user IDs |

**Khi nào dùng HyperLogLog:** Unique visitor counter, DAU estimate (chấp nhận ±0.81%), API call counting, any metric cần scale cardinality nhưng không cần exact.

**Khi nào dùng exact:** Payment processed, items sold, inventory count, anything business-critical cần exact number.

---

### 5.3 Geospatial Redis vs PostGIS

| Tiêu chí | Redis GEOSEARCH | PostGIS ST_DWithin |
|----------|-----------------|-------------------|
| Query latency (1000 rows) | <5ms | 50-200ms |
| Query latency (1M rows) | <50ms với index | 200-2000ms |
| Update frequency | Rất cao (real-time) | Thấp đến trung bình |
| Spatial operations | Chỉ distance + bounds | Đầy đủ: intersection, buffer, etc. |
| Data type | Point only | Point, Line, Polygon, Raster |
| Join với other tables | Không | Có |
| Persistence | Volatile (có thể AOF/RDB) | Persistent |
| Setup complexity | Thấp | Cao |

**Khi dùng Redis Geospatial:** Real-time proximity search (driver-rider, store-customer), high-frequency location updates, latency-sensitive use cases, không cần complex spatial operations.

**Khi dùng PostGIS:** Complex spatial queries, spatial joins, historical trajectory data, audit requirements, data needs persistence beyond Redis.

---

### 5.4 Bloom Filter vs Database Existence Check

| Tiêu chí | Bloom Filter | Database EXISTS query |
|----------|-------------|-----------------------|
| Latency | O(K) ~<1ms | O(log n) ~5-50ms |
| DB load | Zero (khi BF = not found) | Full query mỗi lần |
| False positive | Config được (0.1%-1%) | Zero |
| Memory | Config được | Zero (dùng DB memory) |
| Data freshness | Phải sync với DB | Always fresh |
| Remove support | Không (Bloom), Có (Cuckoo) | Có |
| Scalability | Hàng triệu items, <10MB | DB-dependent |

**Khi dùng Bloom Filter:** Cache anti-penetration, "đã đọc" feature, duplicate detection trong ingestion pipeline, existence check trước expensive operation.

**Khi dùng Database EXISTS:** Accuracy bắt buộc, data thay đổi liên tục, không có Bloom module, audit/compliance yêu cầu exact result.

---

## 6. Best Solution & Best Practices

### 6.1 Production Recommendations

**Scenario 1: DAU tracker cho app có 5 triệu MAU**
→ **Bitmap** với key pattern `dau:YYYYMMDD`
- SETBIT dau:20260519 1234567 1 → user_id 1234567 active hôm nay
- BITCOUNT dau:20260519 → DAU hôm nay
- BITOP OR mau:dau dau:20260501 ... dau:20260519 → BITCOUNT → MAU
- Memory: 5M bits = 625KB per day, 19MB cho 30 days

**Scenario 2: Unique visitors cho 1000 product pages**
→ **HyperLogLog** với key pattern `uv:product:{product_id}`
- PFADD uv:product:123 ip_or_user_hash → mỗi visit
- PFCOUNT uv:product:123 → unique visitors estimate
- PFCOUNT uv:product:123 uv:product:124 → union count 2 pages
- Memory: ~12KB per product × 1000 = 12MB total

**Scenario 3: Tìm driver trong bán kính 5km**
→ **Geospatial** với key `drivers:location`
- GEOADD drivers:location longitude latitude driver_id → mỗi driver update vị trí
- GEOSEARCH drivers:location FROMLONLAT 106.7 10.8 BYRADIUS 5 km WITHDIST ASC COUNT 20
- 2M drivers, 1000 drivers trong radius → <10ms với Redis 7

**Scenario 4: Chặn cache penetration cho product lookup**
→ **Bloom Filter** + cache-aside
```
product_exists_bf = Bloom Filter key = "product:exists"
cache_key = "product:12345"

# Before cache lookup
if BF.EXISTS(product_exists_bf, "12345") == 0:
    return "not found"  # Chắc chắn không tồn tại, skip DB
else:
    # Có thể false positive, vẫn check DB
    result = GET cache_key
    if not result:
        result = DB.get("12345")
        if result:
            SET cache_key result TTL 300
    return result
```

**Scenario 5: Top selling products real-time dashboard**
→ **Top-K** với CMS backup
- TOPK.ADD sales:topk product_id (mỗi sale event)
- TOPK.LIST sales:topk → top 10 products
- CMS.QUERY sales:cms product_id → frequency nếu cần exact count cho top items

---

### 6.2 Anti-patterns

**1. Dùng HyperLogLog cho exact counter**
```txt
# SAI: Marketing sẽ ghét bạn khi họ thấy "xấp xỉ 1.2M orders"
PFADD orders:2026-05 company_id  # Sai

# ĐÚNG: Dùng String với INCR
INCR orders:2026-05  # Exact count
```

**2. Dùng Bitmap cho sparse user ID**
```txt
# SAI: UUID max = 2^64, Redis phải allocate 2EB bitmap
SETBIT user:activity UUID_value 1  # TỆ

# ĐÚNG: Dùng Set hoặc Hash
SADD user:activity:{uuid} 1  # Hoặc HSET
```

**3. Dùng GEORADIUS thay vì GEOSEARCH**
```txt
# SAI: GEORADIUS deprecated từ Redis 6.2
GEORADIUS drivers 106.7 10.8 5 km ASC

# ĐÚNG: Dùng GEOSEARCH
GEOSEARCH drivers FROMLONLAT 106.7 10.8 BYRADIUS 5 km ASC
```

**4. Không rebuild Bloom Filter khi false positive rate tăng**
- Bloom Filter sau khi insert nhiều items, các bit dần fill up → false positive rate tăng
- Giải pháp: Set TTL trên Bloom key hoặc rebuild định kỳ với bigger capacity

**5. Quên rằng RedisBloom cần module riêng**
- Standard Redis không có Bloom Filter
- Cần Redis Stack (redis/redis-stack:latest) hoặc load RedisBloom module riêng
- Command BF.ADD sẽ error "unknown command" nếu không có module

---

## 7. Performance Considerations

### 7.1 Big O Summary

| Data Structure | SETBIT | GETBIT | BITCOUNT | PFADD | PFCOUNT | GEOADD | GEOSEARCH |
|----------------|--------|--------|----------|-------|---------|--------|-----------|
| Time | O(1) | O(1) | O(N bytes) | O(1)* | O(N merge) | O(log N) | O(N + log M) |
| Memory | 1 bit | 1 bit | N/A | ~12KB | N/A | ~50 bytes | N/A |
| Note | Fixed | Fixed | N = byte length | Amortized | N = keys | Per member | N = all members |

*Nếu HLL not initialized: O(1), nếu đã có: O(1) amortized vì PFADD thường update 1 register

### 7.2 Số liệu benchmark thực tế

**Bitmap operations (1 triệu users = 125KB string):**
```
SETBIT dau:20260519 999999 1   # ~0.01ms
BITCOUNT dau:20260519            # ~0.5ms (125KB byte scan)
BITOP OR mau dau:d01 ... dau:d30 # ~2ms (3.75MB OR operation)
BITCOUNT mau                     # ~2ms
```

**HyperLogLog (1B elements):**
```
PFADD uv:page1 item1 item2 ...   # ~0.05ms
PFCOUNT uv:page1                 # ~0.1ms
PFCOUNT uv:page1 uv:page2 uv:page3  # ~5ms (3-way merge)
```

**Geospatial (1M drivers, 100 trong radius 10km):**
```
GEOADD drivers:location 106.7 10.8 driver:001  # ~0.05ms
GEOSEARCH drivers FROMLONLAT 106.7 10.8 BYRADIUS 10 km COUNT 20
  # ~5-15ms (取决于 driver density trong bounding box)
```

**Bloom Filter (1 triệu items, 0.8% FPR):**
```
BF.ADD products:bloom item_id   # ~0.05ms
BF.EXISTS products:bloom item_id # ~0.05ms
```

### 7.3 Impact lên p95/p99

- **BITCOUNT trên string lớn (100MB+):** Có thể mất 50-200ms → ảnh hưởng p99. Giải pháp: dùng BITCOUNT với start/end byte range thay vì full key.
- **PFCOUNT nhiều keys:** 10 keys merge → ~20ms. 100 keys merge → ~100ms+ → spike p99.
- **GEOSEARCH radius lớn (100km+):** Scan toàn bộ geohash bucket → 50-500ms. Giải pháp: dùng smaller radius hoặc partition bằng geohash grid.
- **BF.EXISTS false positive:** Nếu BF fill >80% capacity → FPR tăng đột ngột. p99 latency không đổi nhưng accuracy giảm.

---

## 8. Production Failure Modes

### 8.1 Sparse User ID với Bitmap

**Vấn đề:** User ID là UUID (2^64 range), user_id max = 10 triệu nhưng sparse
```
UUID = "550e8400-e29b-41d4-a716-446655440000"
→ Converted to integer offset = huge
→ Redis allocate bitmap size = huge number / 8 bytes
→ 1 triệu sparse UUIDs = 125MB bitmap
→ Set: 1 triệu × 50 bytes = 50MB
→ Bitmap CHẬM hơn Set về memory
```

**Dấu hiệu:** `MEMORY USAGE bitmap:key` trả về số lớn bất thường
**Debug:** `BITCOUNT` đo tốc độ, `OBJECT ENCODING` kiểm tra bitmap string encoding
**Fix:** Dùng Set hoặc Hash thay vì Bitmap

### 8.2 HLL Over-merge

**Vấn đề:** PFCOUNT key1 key2 ... key100 → merge 100 HLLs mỗi lần query
- Mỗi HLL merge mất O(registers) = 16384 operations
- 100 keys × 16384 = 1.6M operations/query
- p99 spike lên 100-200ms

**Dấu hiệu:** PFCOUNT latency cao bất thường, spike khi dashboard load
**Fix:** Thiết kế key structure hợp lý. Thay vì 100 HLL keys, dùng 1 key với PFADD, hoặc pre-merge vào daily/weekly keys

### 8.3 GEOSEARCH với radius lớn

**Vấn đề:** GEOSEARCH với radius 100km+ trong city đông đúc → scan hàng nghìn geohash buckets
```
Ho Chi Minh City radius 100km → ~5000 drivers trong kết quả
→ Time: 50-200ms
→ Block event loop của Redis thread
```

**Dấu hiệu:** Redis latency spike khi geo query chạy, `SLOWLOG` có GEOSEARCH entries
**Fix:** Partition key bằng geohash grid level (ví dụ: geohash precision 6 = ~1.2km × 0.6km cells), query cell chính + 8 neighbors

### 8.4 Bloom Filter Configuration sai

**Vấn đề 1:** FPR quá thấp (0.001%) → memory cần lớn gấp 10 lần
```
1 triệu items, FPR=0.001%: m=19M bits = 2.4MB
1 triệu items, FPR=1%:      m=9.6M bits = 1.2MB
```

**Vấn đề 2:** Không SETEX/TTL cho Bloom key → fill up không bao giờ reset
```
→ FPR tăng theo thời gian (nếu max capacity gốc = 100K items nhưng insert 1M)
→ Từ 1% FPR → 99% FPR (almost always positive)
→ Bloom filter trở nên useless
```

**Dấu hiệu:** DB queries không giảm dù đã dùng Bloom Filter
**Fix:** Cấu hình capacity đủ cho expected N (nên reserve 2-3x), set TTL hoặc rebuild định kỳ

### 8.5 RedisBloom Module không load

**Vấn đề:** Code dùng BF.ADD nhưng Redis không có RedisBloom module → "ERR unknown command"
**Dấu hiệu:** Redis error log có "unknown command" cho BF.*
**Fix:**
```bash
# Kiểm tra module
redis-cli MODULE LIST

# Hoặc dùng Redis Stack
docker run -d -p 6379:6379 redis/redis-stack:latest
```

---

## 9. Real-world Examples

### 9.1 Twitter: Bitmap cho user feature flags

Twitter dùng Bitmap để track 500M+ users × features. Mỗi user = 1 bit per feature.
- Key pattern: `feature:{feature_id}:users`
- Active users = BITCOUNT
- User 123 có feature? → GETBIT
- Memory: 500M bits = 62.5MB per feature × 100 features = 6.25GB (vẫn OK)

Nguồn: RedisConf 2019, "Redis at Twitter" talks

### 9.2 Reddit: HyperLogLog cho subreddit unique visitors

Reddit dùng HLL để count unique visitors per subreddit per day:
- Key: `subreddit:{id}:uv:daily:{YYYYMMDD}`
- 10K+ subreddits, mỗi cái có HLL ~12KB
- Total memory: ~120MB cho full day tracking
- PFCOUNT để query UV mỗi khi render subreddit page

Nguồn: Reddit engineering blog

### 9.3 Uber/Lyft: Geospatial cho driver-rider matching

Uber dùng Redis-like system (không chính xác Redis nhưng concept tương tự) để:
- Driver gửi location update mỗi 3-5 giây
- Rider request → tìm drivers trong 5km radius
- Scoring bằng ETA + driver rating
- Return top N drivers trong <100ms

Với Redis GEOSEARCH: 2M drivers, 100-500 drivers in radius → <10ms p99

### 9.4 Medium: Bloom Filter cho "đã đọc"

Medium dùng Bloom Filter per user để trả lời "bạn đã đọc bài này chưa?"
- Mỗi user có 1 Bloom Filter ~5-10KB (estimated 100K articles read)
- Khi scroll feed: BF.EXISTS trước khi hiển thị "đã đọc" badge
- False positive rate ~0.1% → badge hiện nhầm một vài lần (acceptable)

### 9.5 Spotify: HyperLogLog cho unique listeners

Spotify dùng HLL để track unique listeners per playlist, per artist:
- Playlist có 10 triệu plays từ 5 triệu unique users
- Exact count với Set: 5M × 50 bytes = 250MB per playlist
- HLL: 12KB per playlist
- Dùng cho "unique listeners" metric trên artist dashboard

Nguồn: Spotify engineering blog, "Redis at Spotify"

---

## 10. Common Pitfalls

### 10.1 HyperLogLog không reverse được
```txt
PFADD uv:daily:20260519 user:001
# Không có PFREMOVE hoặc PFDELETE element
# Muốn xóa user:001 → phải recreate entire HLL (không khả thi)
```
→ Thiết kế key lifecycle hợp lý: dùng daily HLL keys, tạo key mới mỗi ngày, xóa key cũ sau 90 ngày

### 10.2 Bitmap với user ID 64-bit sparse
```
# user_id max = 18 quintillion (UUID với max value)
# Bitmap phải allocate đủ bytes cho offset đó
# 18 quintillion bits = 2EB (exabytes) → OOM
```
→ Luôn kiểm tra user ID distribution trước khi chọn Bitmap. Nếu sparse, dùng Set hoặc Hash

### 10.3 GEORADIUS deprecated nhưng code cũ vẫn dùng
- Code viết năm 2020 dùng GEORADIUS → vẫn work nhưng sẽ có deprecation warning
- GEOSEARCH có cú pháp khác, cần migrate
- `GEORADIUS key long lat r unit [GEOSEARCH]` flag → auto-convert

### 10.4 Bloom Filter không thể remove
- Insert-only design: false positive rate tăng khi fill rate > 50%
- Cần rebuild filter khi FPR vượt threshold
- Cân nhắc Cuckoo Filter nếu cần remove

### 10.5 Quên RedisBloom module
```bash
# Standard Redis: BF.ADD sẽ fail
redis-cli BF.ADD myfilter item
# (error) ERR unknown command `BF.ADD`

# Phải dùng Redis Stack
docker run -d -p 6379:6379 redis/redis-stack:latest
```
→ Docker Compose phải specify `redis/redis-stack:latest`, không phải `redis:latest`

### 10.6 PFCOUNT nhiều keys gây latency spike
```txt
# Dashboard query: union UV của 30 ngày
PFCOUNT uv:d01 uv:d02 ... uv:d30
# Nếu mỗi ngày là separate key → merge 30 HLLs
# 30-way merge = ~30ms → spike p99
```
→ Pre-merge vào weekly/monthly keys, hoặc dùng daily BITOP approach

---

## 11. Câu hỏi tự kiểm tra

**Câu 1:**
Bạn cần track 2 triệu daily active users. User ID là auto-increment integer (1-2M). Bạn dùng Bitmap hay Set? Tính memory cho cả hai và đưa ra con số cụ thể.

**Câu 2:**
Bạn dùng HyperLogLog để đếm unique visitors cho website. Một ngày có 1 triệu unique visitors. Hôm nay bạn nhận được PFCOUNT = 1,005,000. Con số này có bình thường không?

**Câu 3:**
GEORADIUS và GEOSEARCH khác nhau như thế nào? Tại sao bạn nên migrate từ GEORADIUS sang GEOSEARCH?

**Câu 4:**
Bạn dùng Bloom Filter để chặn cache penetration cho product lookup. Khi nào Bloom Filter báo "có tồn tại" nhưng thực tế product không tồn tại trong database?

**Câu 5:**
Bạn có 1000 product pages, mỗi page cần unique visitor count. Bạn thiết kế key như thế nào để PFCOUNT không spike p99?

**Câu 6:**
So sánh memory khi lưu 1 tỷ unique users bằng: (a) Set, (b) Bitmap (dense), (c) HyperLogLog. Đưa ra con số cụ thể.

**Câu 7:**
Khi nào bạn chọn Redis Geospatial thay vì PostGIS? Nêu 3 tiêu chí quyết định.

---

## Đáp án

**Câu 1:** Dùng **Bitmap** vì user ID dense. Bitmap: 2M bits = 250KB/ngày, khoảng 7.5MB cho 30 ngày MAU. Set: 2M × khoảng 50 bytes = khoảng 100MB/ngày. Bitmap tiết kiệm khoảng 400 lần memory và `BITCOUNT` trên 250KB thường rất nhanh.

**Câu 2:** Có, bình thường. HyperLogLog có error rate khoảng 0.81%; với 1,000,000 users, biên sai số kỳ vọng khoảng ±8,100. Kết quả 1,005,000 nằm trong range đó. Nếu business cần exact count, dùng Set hoặc database `COUNT(DISTINCT)`.

**Câu 3:** `GEORADIUS` chỉ query theo radius và đã deprecated từ Redis 6.2. `GEOSEARCH` hỗ trợ `BYRADIUS`, `BYBOX`, cú pháp rõ hơn và là hướng dùng mới. Migration: `GEORADIUS key lon lat r unit` thành `GEOSEARCH key FROMLONLAT lon lat BYRADIUS r unit`, giữ lại các options như `WITHDIST`, `WITHCOORD`, `ASC`, `COUNT`.

**Câu 4:** Đó là **false positive**. Các hash functions của item mới có thể trỏ vào các bit đã được set bởi item khác, nên Bloom Filter báo có dù database không có record. Bloom Filter không có false negative nếu filter được build đúng; nếu `BF.EXISTS` trả 0 thì có thể chặn DB lookup.

**Câu 5:** Không query `PFCOUNT` trên 1000 HLL keys trong request path vì merge nhiều HLL sẽ làm p99 spike. Thiết kế theo daily/pre-aggregated keys như `uv:product:{id}:daily:{yyyyMMdd}`, cache kết quả PFCOUNT TTL ngắn 10-30 giây, hoặc pre-merge background vào weekly/monthly/global keys. Tránh merge quá 10-20 HLLs trong một call nóng.

**Câu 6:** Set: khoảng 50-64GB cho 1B string members. Bitmap dense với `max_id = 1B`: 1B bits = 125MB. HyperLogLog: khoảng 12KB fixed. Bitmap chỉ hợp lý với ID dense; HyperLogLog tiết kiệm nhất nhưng chỉ cho estimate.

**Câu 7:** Chọn Redis Geospatial khi cần latency <10ms, update location tần suất cao, và bài toán chỉ cần point-distance/radius/box query. Chọn PostGIS khi cần spatial joins, polygon/line/buffer, audit trail, transactional persistence, hoặc query địa lý phức tạp hơn.
