# Day 3: Advanced Data Structures — Reference Document

## 1. Command Cheat Sheet

### 1.1 Bitmap

```txt
SETBIT key offset value     -- O(1), offset 0-based, value = 0 or 1
GETBIT key offset           -- O(1)
BITCOUNT key [start end]    -- O(N) bytes, count bits = 1
BITOP AND|OR|XOR|NOT dest key [key ...]   -- O(N) bytes per key
BITPOS key bit [start] [end] [BYTE|BIT]   -- Index của bit đầu tiên = 0 hoặc 1
```

```txt
-- Daily active users
SETBIT dau:20260519 123456 1          -- Mark user 123456 active
BITCOUNT dau:20260519                 -- DAU = số users active
BITOP OR mau:dau dau:20260501 dau:20260502 ... dau:20260530
BITCOUNT mau:dau                       -- MAU = unique users 30 ngày
```

### 1.2 HyperLogLog

```txt
PFADD key element [element ...]       -- O(1) amortized
PFCOUNT key [key ...]                  -- O(N) với N = số keys cần merge
PFMERGE destkey sourcekey [sourcekey ...]  -- Merge vào destkey
```

```txt
PFADD uv:product:123 user:session1   -- Add visitor
PFCOUNT uv:product:123               -- Estimated unique visitors
PFCOUNT uv:product:123 uv:product:456 -- Union count 2 products
PFMERGE uv:weekly uv:d01 uv:d02 ... uv:d07
```

### 1.3 Geospatial

```txt
GEOADD key longitude latitude member [longitude latitude member ...]  -- O(log N)
GEOPOS key member [member ...]           -- O(log N), lấy (lon, lat)
GEODIST key member1 member2 [m|km|mi|ft]  -- O(log N)
GEOSEARCH key FROMLONLAT lo la BYRADIUS r unit [WITHDIST] [WITHCOORD] [ASC|DESC] [COUNT n]
GEOSEARCH key BYBOX width height unit [WITHDIST] [WITHCOORD] [ASC|DESC] [COUNT n]
```

```txt
GEOADD drivers:location 106.7 10.8 driver:001
GEOADD drivers:location 106.8 10.9 driver:002
GEOSEARCH drivers:location FROMLONLAT 106.7 10.8 BYRADIUS 5 km WITHDIST ASC COUNT 10
GEOSEARCH drivers:location BYBOX 10 10 km WITHDIST ASC
GEODIST drivers:location driver:001 driver:002 km
```

> **Lưu ý:** GEORADIUS deprecated từ Redis 6.2. Dùng GEOSEARCH.

### 1.4 Bloom Filter (RedisBloom Module)

```txt
BF.ADD key item                      -- O(K)
BF.EXISTS key item                  -- O(K)
BF.MADD key item [item ...]         -- O(K * n)
BF.INSERT key [ERROR rate] [CAPACITY n] [EXPANSION expansion] ITEMS key1 key2 ...
BF.INFO key                          -- Xem size, capacity, FPR
BF.SCANDUMP key iter                -- Export filter (for backup)
BF.LOADCHUNK key iter data          -- Import filter
```

```txt
BF.INSERT product:exists ERROR 0.001 CAPACITY 100000
BF.ADD product:exists "SKU-12345"
BF.EXISTS product:exists "SKU-12345"    -- 1 = có thể tồn tại, 0 = chắc chắn không
```

### 1.5 Count-Min Sketch (CMS)

```txt
CMS.INCRBY key item increment [item increment ...]   -- O(w)
CMS.QUERY key item                                    -- Estimated frequency
CMS.MERGE destkey numkeys key [key ...] [WEIGHTS w ...]
CMS.INFO key                                          -- Width, depth, total
```

```txt
CMS.INCRBY api:requests /api/products 1
CMS.QUERY api:requests /api/products     -- Số lần gọi ước tính
```

### 1.6 Top-K

```txt
TOPK.ADD key item [item ...]           -- O(K log W)
TOPK.QUERY key item                    -- 1 = in top-K, 0 = not
TOPK.LIST key [WITHCOUNT]              -- Full top-K list
TOPK.INFO key                          -- K, width, depth
TOPK.RESERVE key K [width depth]       -- Tạo key với K items
```

```txt
TOPK.RESERVE sales:topk 10
TOPK.ADD sales:topk product:001 product:002 product:001
TOPK.LIST sales:topk WITHCOUNT
```

### 1.7 Streams (Overview)

```txt
XADD stream-name * field value [field value ...]  -- Auto ID
XLEN stream-name                                   -- Count
XREAD [COUNT n] STREAMS stream-name [id|$]        -- Read stream
XREADGROUP GROUP g1 c1 [COUNT n] STREAMS stream-name >  -- Consumer group
XACK stream-name group id                         -- Acknowledge
```

> Chi tiết Streams Day 18.

---

## 2. Memory Comparison Table

### 2.1 Storing 1 Billion Unique Users

| Data Structure | Memory | Accuracy | Remove Support | Notes |
|---------------|--------|----------|----------------|-------|
| Set | 50-64 GB | 100% | Có | ~50 bytes/user (SDS + overhead) |
| Bitmap (dense, max_id=1B) | ~125 MB | 100% | Có (SETBIT 0) | Chỉ hiệu quả với user_id dense |
| HyperLogLog | ~12 KB | ~99.19% (0.81% error) | **Không** | Fixed size bất kể cardinality |
| Bloom Filter | ~10-20 MB | FPR configurable | **Không** | Không dùng cho counting |

### 2.2 Storing DAU per Day (5 Million Users)

| Storage Type | Memory/Key | 30-Day Total |
|-------------|------------|---------------|
| Set (SADD) | ~250 MB | 7.5 GB |
| Bitmap | ~625 KB | 19 MB |
| HyperLogLog | ~12 KB | ~360 KB |

### 2.3 Geospatial: Redis vs Alternatives

| Metric | Redis GEOSEARCH | PostGIS | MongoDB $geoNear |
|--------|-----------------|---------|-----------------|
| Query latency (1K rows) | <5ms | 50-200ms | 10-50ms |
| Update latency | O(log N) | O(log n) + WAL | O(log n) |
| Max points per key | ~1B (sorted set limit) | No practical limit | ~1B |
| Supported geometry | Point only | All types | Point/GeoJSON |
| Memory efficiency | O(N) | Index-dependent | O(N) |

---

## 3. Accuracy Comparison Table

### 3.1 HyperLogLog Error Rate

| Cardinality | Expected Error | Actual ± | Example |
|-------------|---------------|---------|---------|
| 1,000 | ±0.81% = ±8 | ±8 users | 1,008 vs 1,000 |
| 10,000 | ±0.81% = ±81 | ±81 users | 10,081 vs 10,000 |
| 1,000,000 | ±0.81% = ±8,100 | ±8,100 users | 1,008,100 vs 1,000,000 |
| 100,000,000 | ±0.81% = ±810,000 | ±810,000 users | 100,810,000 vs 100M |

**Conclusion:** Error rate cố định 0.81% nhưng absolute error tăng theo cardinality.

### 3.2 Bloom Filter: FPR vs Memory

| Expected Items | FPR | Memory | Recommended |
|---------------|-----|--------|------------|
| 100,000 | 1% | ~1.2 MB | Internal tools |
| 100,000 | 0.1% | ~1.8 MB | User-facing features |
| 100,000 | 0.01% | ~2.4 MB | Payment/financial |
| 1,000,000 | 1% | ~12 MB | |
| 1,000,000 | 0.1% | ~19 MB | |
| 10,000,000 | 1% | ~120 MB | |

Formula: m = -(n × ln(FPR)) / (ln(2)^2)
Optimal k = (m/n) × ln(2)

---

## 4. Docker Compose Template

```yaml
# docker-compose.yml
version: "3.9"

services:
  redis-stack:
    image: redis/redis-stack:latest
    container_name: redis-stack
    ports:
      - "6379:6379"      # Redis port
      - "8001:8001"      # RedisInsight (optional UI)
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  redis-data:
```

**Kiểm tra RedisBloom module:**
```bash
docker exec redis-stack redis-cli MODULE LIST
# Phải thấy: redisbloom
```

**Test nhanh:**
```bash
docker exec redis-stack redis-cli BF.ADD test:bloom item1
docker exec redis-stack redis-cli BF.EXISTS test:bloom item1
```

---

## 5. TypeScript Code Snippets (ioredis)

### 5.1 DAU Tracker với Bitmap

```typescript
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379 });

// Key pattern: dau:YYYYMMDD
function getDAUKey(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `dau:${y}${m}${d}`;
}

/**
 * Track user as active for today
 * @param userId - Auto-increment integer user ID (dense)
 */
async function trackActiveUser(userId: number): Promise<number> {
  const key = getDAUKey();
  return redis.setbit(key, userId, 1);
}

/**
 * Get DAU count for a specific date
 */
async function getDAU(date: Date = new Date()): Promise<number> {
  const key = getDAUKey(date);
  return redis.bitcount(key);
}

/**
 * Get MAU (Monthly Active Users) using BITOP OR
 * Combines 30 days of DAU bitmaps
 */
async function getMAU(year: number, month: number): Promise<number> {
  const daysInMonth = new Date(year, month, 0).getDate();
  const monthStr = String(month).padStart(2, "0");

  const keys = Array.from({ length: daysInMonth }, (_, i) => {
    const d = String(i + 1).padStart(2, "0");
    return `dau:${year}${monthStr}${d}`;
  });

  const destKey = `mau:${year}${monthStr}`;
  await redis.bitop("OR", destKey, ...keys);

  // Set TTL = 40 days để auto-cleanup
  await redis.expire(destKey, 40 * 86400);

  return redis.bitcount(destKey);
}

// Example usage
async function main() {
  // Track users
  await trackActiveUser(1);
  await trackActiveUser(100);
  await trackActiveUser(10000);

  const dau = await getDAU();
  console.log(`DAU today: ${dau}`); // 3

  const mau = await getMAU(2026, 5);
  console.log(`MAU May 2026: ${mau}`);
}

main().catch(console.error);
```

### 5.2 Unique Visitor Counter với HyperLogLog

```typescript
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379 });

/**
 * Track unique visitor for a page
 * @param pageId - Product/page identifier
 * @param visitorId - User ID or hashed IP
 */
async function trackUniqueVisitor(
  pageId: string,
  visitorId: string
): Promise<number> {
  const key = `uv:page:${pageId}`;
  return redis.pfadd(key, visitorId);
}

/**
 * Get estimated unique visitors for a page
 */
async function getUniqueVisitors(pageId: string): Promise<number> {
  return redis.pfcount(`uv:page:${pageId}`);
}

/**
 * Get union of unique visitors across multiple pages
 */
async function getUnionUniqueVisitors(
  pageIds: string[]
): Promise<number> {
  const keys = pageIds.map((id) => `uv:page:${id}`);
  return redis.pfcount(...keys);
}

/**
 * Daily UV tracking với auto-expiry
 */
async function trackDailyUV(
  pageId: string,
  visitorId: string
): Promise<number> {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  const key = `uv:${y}${m}${d}:page:${pageId}`;

  const result = await redis.pfadd(key, visitorId);
  await redis.expire(key, 8 * 86400); // 8 days TTL
  return result;
}

// Example usage
async function main() {
  const pageId = "product-12345";

  // Track visitors
  await trackUniqueVisitor(pageId, "user:001");
  await trackUniqueVisitor(pageId, "user:002");
  await trackUniqueVisitor(pageId, "user:001"); // Duplicate — ignored by PFADD

  const uv = await getUniqueVisitors(pageId);
  console.log(`UV for ${pageId}: ${uv}`); // 2

  // Cross-page union
  const union = await getUnionUniqueVisitors([
    "product-12345",
    "product-67890",
    "product-11111",
  ]);
  console.log(`Union UV across 3 pages: ${union}`);
}

main().catch(console.error);
```

### 5.3 Geo Nearby Drivers Search

```typescript
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379 });

const DRIVERS_KEY = "drivers:location";

interface DriverLocation {
  driverId: string;
  longitude: number;
  latitude: number;
}

/**
 * Update driver location
 */
async function updateDriverLocation(
  driverId: string,
  longitude: number,
  latitude: number
): Promise<number> {
  return redis.geoadd(DRIVERS_KEY, longitude, latitude, driverId);
}

/**
 * Search nearby drivers within radius
 */
async function findNearbyDrivers(
  longitude: number,
  latitude: number,
  radiusKm: number,
  limit = 20
): Promise<Array<{ driverId: string; distance: string }>> {
  const results = await redis.geosearch(
    DRIVERS_KEY,
    "FROMLONLAT",
    longitude,
    latitude,
    "BYRADIUS",
    radiusKm,
    "km",
    "WITHDIST",
    "ASC",
    "COUNT",
    limit
  );

  // results: [[driverId, distance], ...]
  return results.map((r) => ({
    driverId: r[0] as string,
    distance: r[1] as string,
  }));
}

/**
 * Search drivers in rectangular area (faster for known bounding box)
 */
async function findDriversInBox(
  centerLon: number,
  centerLat: number,
  widthKm: number,
  heightKm: number,
  limit = 50
): Promise<string[]> {
  const results = await redis.geosearch(
    DRIVERS_KEY,
    "FROMLONLAT",
    centerLon,
    centerLat,
    "BYBOX",
    widthKm,
    heightKm,
    "km",
    "ASC",
    "COUNT",
    limit
  );

  return results as string[];
}

/**
 * Get distance between two drivers
 */
async function getDriverDistance(
  driverId1: string,
  driverId2: string
): Promise<string | null> {
  return redis.geodist(DRIVERS_KEY, driverId1, driverId2, "km");
}

/**
 * Get driver position
 */
async function getDriverPosition(
  driverId: string
): Promise<[string, string] | null> {
  const result = await redis.geopos(DRIVERS_KEY, driverId);
  return result ? (result[0] as [string, string]) : null;
}

// Example usage
async function main() {
  // Seed drivers
  const drivers: DriverLocation[] = [
    { driverId: "driver:001", longitude: 106.7, latitude: 10.8 },
    { driverId: "driver:002", longitude: 106.71, latitude: 10.81 },
    { driverId: "driver:003", longitude: 106.72, latitude: 10.82 },
    { driverId: "driver:004", longitude: 107.0, latitude: 11.0 },
  ];

  for (const d of drivers) {
    await updateDriverLocation(d.driverId, d.longitude, d.latitude);
  }

  // Find nearby drivers
  const nearby = await findNearbyDrivers(106.7, 10.8, 5, 10);
  console.log("Nearby drivers within 5km:");
  nearby.forEach(({ driverId, distance }) => {
    console.log(`  ${driverId}: ${distance} km`);
  });

  // Distance between two drivers
  const dist = await getDriverDistance("driver:001", "driver:002");
  console.log(`Distance driver:001 → driver:002: ${dist} km`);
}

main().catch(console.error);
```

### 5.4 Bloom Filter với @redis/bloom

```bash
npm install @redis/bloom ioredis
```

```typescript
import Redis from "ioredis";
import { BloomNamespace } from "@redis/bloom";

const redis = new Redis({ host: "localhost", port: 6379 });
const bloom = redis.defineCommand("BF", {
  numberOfKeys: 1,
  lua: "",
}) as unknown as BloomNamespace;

// Alternative: dùng raw commands với ioredis
const redisRaw = new Redis({ host: "localhost", port: 6379 });

const BLOOM_KEY = "product:exists";
const EXPECTED_ITEMS = 100_000;
const FALSE_POSITIVE_RATE = 0.001; // 0.1%

/**
 * Initialize bloom filter với capacity và FPR
 */
async function initBloomFilter(): Promise<void> {
  await redisRaw.call(
    "BF.INSERT",
    BLOOM_KEY,
    "ERROR",
    FALSE_POSITIVE_RATE,
    "CAPACITY",
    EXPECTED_ITEMS
  );
  // Set TTL 30 days — rebuild định kỳ
  await redisRaw.expire(BLOOM_KEY, 30 * 86400);
}

/**
 * Add item to bloom filter
 */
async function addToBloomFilter(item: string): Promise<number> {
  return redisRaw.call("BF.ADD", BLOOM_KEY, item) as Promise<number>;
}

/**
 * Batch add items
 */
async function addManyToBloomFilter(items: string[]): Promise<number[]> {
  const args = [BLOOM_KEY, ...items];
  return redisRaw.call("BF.MADD", ...args) as Promise<number[]>;
}

/**
 * Check item existence
 * Returns: 1 = possibly exists (may be false positive), 0 = definitely not exists
 */
async function existsInBloomFilter(item: string): Promise<number> {
  return redisRaw.call("BF.EXISTS", BLOOM_KEY, item) as Promise<number>;
}

/**
 * Cache anti-penetration flow
 */
async function getProductWithBloomFilter(
  productId: string,
  getFromDB: (id: string) => Promise<string | null>
): Promise<string | null> {
  // 1. Check bloom filter
  const possiblyExists = await existsInBloomFilter(productId);

  if (possiblyExists === 0) {
    // Chắc chắn không tồn tại — skip DB hoàn toàn
    console.log(`Bloom filter: ${productId} not found (definite)`);
    return null;
  }

  // 2. Bloom báo có — có thể false positive, vẫn check DB
  console.log(`Bloom filter: ${productId} possibly exists (checking DB)`);
  const cached = await redisRaw.get(`product:${productId}`);
  if (cached) return cached;

  const fromDB = await getFromDB(productId);
  if (fromDB) {
    await redisRaw.setex(`product:${productId}`, 300, fromDB);
    // Add to bloom filter (nếu từ DB — chắc chắn tồn tại)
    await addToBloomFilter(productId);
  }

  return fromDB;
}

// Example usage
async function main() {
  await initBloomFilter();

  // Add products from DB
  const productIds = Array.from({ length: 1000 }, (_, i) => `SKU-${i}`);
  await addManyToBloomFilter(productIds);

  // Check
  const result1 = await existsInBloomFilter("SKU-500");
  const result2 = await existsInBloomFilter("SKU-NONEXISTENT");

  console.log(`SKU-500: ${result1 === 1 ? "possibly exists" : "not found"}`);
  console.log(
    `SKU-NONEXISTENT: ${result2 === 1 ? "possibly exists" : "not found"}`
  );
}

main().catch(console.error);
```

### 5.5 CMS (Count-Min Sketch) Example

```typescript
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379 });

const CMS_KEY = "api:frequency";

/**
 * Increment frequency counter for an item
 */
async function incrementCounter(
  item: string,
  increment = 1
): Promise<number[]> {
  return redis.call("CMS.INCRBY", CMS_KEY, item, increment) as Promise<number[]>;
}

/**
 * Get estimated frequency of an item
 */
async function getFrequency(item: string): Promise<number> {
  return redis.call("CMS.QUERY", CMS_KEY, item) as Promise<number>;
}

/**
 * Reserve CMS với parameters (width/depth = memory/accuracy trade-off)
 */
async function initCMS(
  width = 1000,
  depth = 5
): Promise<void> {
  await redis.call("CMS.INITBYDIM", CMS_KEY, width, depth);
}

/**
 * Find top-K frequent items via CMS (scan candidate list)
 */
async function getTopFrequentItems(
  candidates: string[],
  limit = 10
): Promise<Array<{ item: string; frequency: number }>> {
  const frequencies = await Promise.all(
    candidates.map(async (item) => {
      const freq = await getFrequency(item);
      return { item, frequency: freq };
    })
  );

  return frequencies
    .sort((a, b) => b.frequency - a.frequency)
    .slice(0, limit);
}

// Example usage
async function main() {
  await initCMS(1000, 5);

  // Track API calls
  const endpoints = ["/api/products", "/api/users", "/api/orders"];
  for (let i = 0; i < 100; i++) {
    await incrementCounter(endpoints[i % endpoints.length]);
  }

  for (const ep of endpoints) {
    const freq = await getFrequency(ep);
    console.log(`${ep}: ~${freq} calls`);
  }
}

main().catch(console.error);
```

---

## 6. Links & References

### Official Redis Documentation
- https://redis.io/docs/data-types/bitmaps/
- https://redis.io/docs/data-types/hyperloglogs/
- https://redis.io/docs/data-types/geospatial/
- https://redis.io/docs/data-types/streams/
- https://redis.io/docs/data-types/probabilistic/

### RedisBloom
- https://redis.io/docs/interact/search-and-query/advanced-concepts/bloom-filter/
- https://github.com/RedisBloom/RedisBloom

### Redis Commands Reference
- https://redis.io/commands/setbit
- https://redis.io/commands/bitcount
- https://redis.io/commands/pfadd
- https://redis.io/commands/pfcount
- https://redis.io/commands/geoadd
- https://redis.io/commands/geosearch

### Background Reading
- **"Redis HyperLogLog: A 12KB Algorithm"** — Salvatore Antirez (Redis creator)
  https://antirez.com/news/75
- **"What every programmer should know about floating point math"** — David Goldberg (cho understanding HLL error rate)
- **"Bloom Filter" — Wikipedia** (for mathematical foundation)
- **"Geohash: Wikipedia"** (for understanding geohash precision and bounding box)
