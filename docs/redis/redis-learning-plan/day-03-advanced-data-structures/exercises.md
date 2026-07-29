# Day 3: Advanced Data Structures — Exercises

**Thời gian:** ~2 giờ
**Yêu cầu:** Docker với `redis/redis-stack:latest`, Node.js 18+, TypeScript

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1 Bitmap Basic Operations

```bash
docker exec redis-stack redis-cli
```

```txt
-- Tạo bitmap với 3 users active
SETBIT user:active:20260519 1 1
SETBIT user:active:20260519 100 1
SETBIT user:active:20260519 1000 1

-- Check individual bit
GETBIT user:active:20260519 1     -- Expected: 1
GETBIT user:active:20260519 2     -- Expected: 0
GETBIT user:active:20260519 100   -- Expected: 1

-- Count DAU
BITCOUNT user:active:20260519    -- Expected: 3

-- Tìm vị trí bit đầu tiên = 1
BITPOS user:active:20260519 1    -- Expected: 1

-- Tạo ngày thứ 2
SETBIT user:active:20260520 1 1
SETBIT user:active:20260520 200 1
SETBIT user:active:20260520 1000 1

-- Compute MAU bằng BITOP OR
BITOP OR user:mau user:active:20260519 user:active:20260520
BITCOUNT user:mau                    -- Expected: 4 (users 1, 100, 200, 1000)

-- Cleanup
DEL user:active:20260519 user:active:20260520 user:mau
```

### 1.2 HyperLogLog Basic Operations

```txt
-- Thêm unique visitors
PFADD uv:page:home session:001
PFADD uv:page:home session:002
PFADD uv:page:home session:003
PFADD uv:page:home session:002    -- Duplicate, PFADD vẫn return 0

-- Đếm unique visitors
PFCOUNT uv:page:home              -- Expected: 3

-- Thêm page khác
PFADD uv:page:product session:002
PFADD uv:page:product session:003
PFADD uv:page:product session:004

-- Union count
PFCOUNT uv:page:home uv:page:product  -- Expected: ~4 (exact với dataset nhỏ)

-- Merge
PFMERGE uv:combined uv:page:home uv:page:product
PFCOUNT uv:combined              -- Same as union count

-- Cleanup
DEL uv:page:home uv:page:product uv:combined
```

### 1.3 Geospatial Basic Operations

```txt
-- Thêm locations
GEOADD restaurants:sg 106.7 10.8 "restaurant:001"
GEOADD restaurants:sg 106.71 10.81 "restaurant:002"
GEOADD restaurants:sg 106.72 10.82 "restaurant:003"
GEOADD restaurants:sg 107.0 11.0 "restaurant:004"

-- Lấy position
GEOPOS restaurants:sg restaurant:001   -- ["106.700000...", "10.800000..."]

-- Khoảng cách
GEODIST restaurants:sg restaurant:001 restaurant:002 km
-- Expected: ~0.017 km (17m)

-- Tìm nearby (dùng GEOSEARCH thay vì deprecated GEORADIUS)
GEOSEARCH restaurants:sg FROMLONLAT 106.7 10.8 BYRADIUS 10 km WITHDIST ASC COUNT 5
-- Expected: 3 restaurants gần nhất với khoảng cách

-- Tìm trong bounding box
GEOSEARCH restaurants:sg BYBOX 5 5 km ASC COUNT 5
-- Expected: 3 restaurants trong box

-- Cleanup
DEL restaurants:sg
```

### 1.4 Bloom Filter Basic (RedisBloom)

```bash
docker exec redis-stack redis-cli BF.INSERT products:bloom ERROR 0.01 CAPACITY 10000 ITEMS "SKU-001" "SKU-002" "SKU-003"
```

```txt
-- Check tồn tại
BF.EXISTS products:bloom SKU-001   -- Expected: 1 (tồn tại)
BF.EXISTS products:bloom SKU-999   -- Expected: 0 (không tồn tại)

-- Add thêm
BF.ADD products:bloom SKU-999

-- Batch add
BF.MADD products:bloom SKU-100 SKU-101

-- Info
BF.INFO products:bloom
-- Xem: Capacity, Size, Filters

-- Cleanup
DEL products:bloom
```

---

## 2. Hands-on Lab (60-70 phút)

### 2.1 Setup

```bash
mkdir -p day03-exercises/src
cd day03-exercises

# package.json
cat > package.json << 'EOF'
{
  "name": "day03-exercises",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node --loader ts-node/esm src/main.ts",
    "dev": "node --loader ts-node/esm src/main.ts"
  },
  "dependencies": {
    "ioredis": "^5.3.2"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
EOF

# tsconfig.json
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "esModuleInterop": true,
    "strict": true
  }
}
EOF

npm install
```

### 2.2 Starter Code

Tạo file `src/main.ts`:

```typescript
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379, lazyConnect: true });

async function setup() {
  await redis.connect();
  console.log("Connected to Redis");
}

function dateKey(prefix: string, date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${prefix}:${y}${m}${d}`;
}

// ============================================================
// LAB 1: DAU Tracker với Bitmap
// ============================================================

/**
 * Bài 1a: Implement hàm trackLogin(userId: number)
 * - Dùng key dau:YYYYMMDD
 * - SETBIT user bit = 1
 */
async function trackLogin(userId: number): Promise<number> {
  if (!Number.isInteger(userId) || userId < 0) {
    throw new Error("Bitmap chỉ phù hợp với userId integer không âm và tương đối dense");
  }
  return redis.setbit(dateKey("dau"), userId, 1);
}

/**
 * Bài 1b: Implement hàm getDAU(date?: Date): Promise<number>
 * - Dùng BITCOUNT
 */
async function getDAU(date?: Date): Promise<number> {
  return redis.bitcount(dateKey("dau", date ?? new Date()));
}

/**
 * Bài 1c: Implement hàm getMAU(year: number, month: number): Promise<number>
 * - Dùng BITOP OR để OR 30 ngày
 * - SETBIT expire = 48h
 */
async function getMAU(year: number, month: number): Promise<number> {
  const days = new Date(year, month, 0).getDate();
  const monthStr = String(month).padStart(2, "0");
  const keys = Array.from({ length: days }, (_, i) =>
    `dau:${year}${monthStr}${String(i + 1).padStart(2, "0")}`
  );
  const destKey = `mau:${year}${monthStr}`;
  await redis.bitop("OR", destKey, ...keys);
  await redis.expire(destKey, 48 * 3600);
  return redis.bitcount(destKey);
}

// ============================================================
// LAB 2: Unique Visitor với HyperLogLog
// ============================================================

/**
 * Bài 2a: Track visitor với PFADD
 */
async function trackVisitor(pageId: string, visitorId: string): Promise<number> {
  return redis.pfadd(`uv:page:${pageId}`, visitorId);
}

/**
 * Bài 2b: Get estimated UV
 */
async function getPageUV(pageId: string): Promise<number> {
  return redis.pfcount(`uv:page:${pageId}`);
}

/**
 * Bài 2c: Union UV across multiple pages
 */
async function getCrossPageUV(pageIds: string[]): Promise<number> {
  if (pageIds.length === 0) return 0;
  return redis.pfcount(...pageIds.map((id) => `uv:page:${id}`));
}

// ============================================================
// LAB 3: Geo Search - Nearby Drivers
// ============================================================

const DRIVERS_KEY = "drivers:active";

interface Driver {
  id: string;
  longitude: number;
  latitude: number;
}

/**
 * Bài 3a: Add driver location
 */
async function addDriver(driver: Driver): Promise<number> {
  return redis.geoadd(DRIVERS_KEY, driver.longitude, driver.latitude, driver.id);
}

/**
 * Bài 3b: Find nearby drivers với GEOSEARCH
 * Trả về mảng { driverId, distance } sắp xếp ASC
 */
async function findNearbyDrivers(
  longitude: number,
  latitude: number,
  radiusKm: number,
  limit = 10
): Promise<Array<{ driverId: string; distance: string }>> {
  const raw = (await redis.call(
    "GEOSEARCH",
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
  )) as Array<[string, string]>;

  return raw.map(([driverId, distance]) => ({ driverId, distance }));
}

// ============================================================
// LAB 4: Geo partitioning - Grid-based search
// ============================================================

/**
 * Bài 4: Partition city thành grid cells xấp xỉ 5km
 * Với mỗi cell, tạo key drivers:grid:{precision}:{lonCell}:{latCell}
 * Khi query: tính 9 cells xung quanh, search trong từng cell
 *
 * Production có thể thay bằng geohash library để cell chính xác hơn.
 */
async function addDriverToGrid(driver: Driver, precision = 5): Promise<void> {
  const cellSizeDeg = precision >= 5 ? 0.05 : 0.1;
  const lonCell = Math.floor(driver.longitude / cellSizeDeg);
  const latCell = Math.floor(driver.latitude / cellSizeDeg);
  const key = `drivers:grid:${precision}:${lonCell}:${latCell}`;
  await redis.geoadd(key, driver.longitude, driver.latitude, driver.id);
  await redis.expire(key, 3600);
}

// ============================================================
// LAB 5: Bloom Filter Cache Anti-Penetration
// ============================================================

const BF_KEY = "bf:products";

/**
 * Bài 5a: Initialize bloom filter
 * Capacity = 100,000 items, FPR = 0.001
 */
async function initBloomFilter(): Promise<void> {
  try {
    await redis.call("BF.RESERVE", BF_KEY, "0.001", "100000");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (!message.includes("item exists")) {
      throw new Error(`RedisBloom chưa sẵn sàng hoặc command BF.RESERVE lỗi: ${message}`);
    }
  }

  await redis.call("BF.ADD", BF_KEY, "SKU-REAL-001");
  await redis.call("BF.ADD", BF_KEY, "SKU-REAL-002");
}

/**
 * Bài 5b: Check before DB query
 * Returns: { source: "cache" | "bloom-filter-blocked" | "db", data: any }
 */
async function getProductWithBloom(
  productId: string,
  getFromDB: (id: string) => Promise<string | null>
): Promise<{ source: string; data: string | null }> {
  const exists = Number(await redis.call("BF.EXISTS", BF_KEY, productId));
  if (exists === 0) {
    return { source: "bloom-filter-blocked", data: null };
  }

  const cacheKey = `product:${productId}`;
  const cached = await redis.get(cacheKey);
  if (cached !== null) {
    return { source: "cache", data: cached };
  }

  const fromDB = await getFromDB(productId);
  if (fromDB !== null) {
    await redis.setex(cacheKey, 300, fromDB);
  }
  return { source: "db", data: fromDB };
}

// ============================================================
// Main test
// ============================================================

async function main() {
  await setup();
  const today = new Date();
  await redis.del(
    dateKey("dau", today),
    "uv:page:page:001",
    "uv:page:page:002",
    DRIVERS_KEY,
    BF_KEY,
    "product:SKU-REAL-001",
    "product:SKU-FAKE-999"
  );

  // === LAB 1: DAU ===
  console.log("\n--- LAB 1: DAU Tracker ---");
  await trackLogin(1);
  await trackLogin(100);
  await trackLogin(1); // duplicate
  await trackLogin(10000);
  const dau = await getDAU(today);
  console.log(`DAU today: ${dau}`); // Expected: 3

  // === LAB 2: HyperLogLog ===
  console.log("\n--- LAB 2: Unique Visitors ---");
  await trackVisitor("page:001", "user:001");
  await trackVisitor("page:001", "user:002");
  await trackVisitor("page:001", "user:001"); // duplicate
  const uv1 = await getPageUV("page:001");
  console.log(`UV page:001: ${uv1}`); // Expected: 2

  await trackVisitor("page:002", "user:002");
  await trackVisitor("page:002", "user:003");
  const crossUV = await getCrossPageUV(["page:001", "page:002"]);
  console.log(`Cross-page UV: ${crossUV}`); // Expected: 3

  // === LAB 3: Geo ===
  console.log("\n--- LAB 3: Nearby Drivers ---");
  const drivers = [
    { id: "d:001", longitude: 106.7, latitude: 10.8 },
    { id: "d:002", longitude: 106.71, latitude: 10.81 },
    { id: "d:003", longitude: 106.72, latitude: 10.82 },
    { id: "d:004", longitude: 107.5, latitude: 11.5 }, // Far away
  ];
  for (const d of drivers) await addDriver(d);

  const nearby = await findNearbyDrivers(106.7, 10.8, 10, 10);
  console.log("Nearby drivers (10km radius):");
  nearby.forEach(({ driverId, distance }) => {
    console.log(`  ${driverId}: ${distance} km`);
  });
  // Expected: d:001, d:002, d:003 (d:004 far away)

  // === LAB 5: Bloom Filter ===
  console.log("\n--- LAB 5: Bloom Filter ---");
  await initBloomFilter();
  const mockDB = async (id: string) => (id.startsWith("SKU-REAL-") ? `Product ${id}` : null);

  // SKU-REAL-001 should exist in DB
  const r1 = await getProductWithBloom("SKU-REAL-001", mockDB);
  console.log(`SKU-REAL-001: ${JSON.stringify(r1)}`);

  // SKU-FAKE-999 does not exist in DB and should be blocked by BF after first miss
  // (But BF only has SKUs we add — let's add some first)
  // BF.EXISTS returns 0 for unknown items that were never added
  const r2 = await getProductWithBloom("SKU-FAKE-999", mockDB);
  console.log(`SKU-FAKE-999: ${JSON.stringify(r2)}`);

  console.log("\nAll tests completed!");
  await redis.quit();
}

main().catch(console.error);
```

### 2.3 Hints từng bước

**LAB 1 (DAU Tracker):**

```typescript
// HINT 1: Lấy ngày
function getDateKey(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `dau:${y}${m}${d}`;
}

// HINT 2: trackLogin implementation
async function trackLogin(userId: number): Promise<number> {
  const key = getDateKey();
  return redis.setbit(key, userId, 1);
}

// HINT 3: getMAU implementation
async function getMAU(year: number, month: number): Promise<number> {
  const days = new Date(year, month, 0).getDate();
  const monthStr = String(month).padStart(2, "0");
  const keys = Array.from({ length: days }, (_, i) =>
    `dau:${year}${monthStr}${String(i + 1).padStart(2, "0")}`
  );
  const destKey = `mau:${year}${monthStr}`;
  await redis.bitop("OR", destKey, ...keys);
  await redis.expire(destKey, 48 * 3600);
  return redis.bitcount(destKey);
}
```

**LAB 2 (HyperLogLog):**

```typescript
// HINT: PFADD và PFCOUNT
async function trackVisitor(pageId: string, visitorId: string): Promise<number> {
  return redis.pfadd(`uv:page:${pageId}`, visitorId);
}

async function getPageUV(pageId: string): Promise<number> {
  return redis.pfcount(`uv:page:${pageId}`);
}

async function getCrossPageUV(pageIds: string[]): Promise<number> {
  const keys = pageIds.map((id) => `uv:page:${id}`);
  return redis.pfcount(...keys);
}
```

**LAB 3 (Geo):**

```typescript
// HINT: GEOSEARCH với options
async function findNearbyDrivers(
  longitude: number,
  latitude: number,
  radiusKm: number,
  limit = 10
): Promise<Array<{ driverId: string; distance: string }>> {
  const raw = await redis.geosearch(
    DRIVERS_KEY,
    "FROMLONLAT", longitude, latitude,
    "BYRADIUS", radiusKm, "km",
    "WITHDIST",
    "ASC",
    "COUNT", limit
  );
  return raw.map((item) => ({
    driverId: item[0] as string,
    distance: item[1] as string,
  }));
}
```

**LAB 5 (Bloom Filter):**

```typescript
// HINT: Dùng redis.call() cho custom commands
async function initBloomFilter(): Promise<void> {
  await (redis as any).call(
    "BF.RESERVE", BF_KEY,
    "0.001",
    "100000"
  );
  await (redis as any).call("BF.ADD", BF_KEY, "SKU-REAL-001");
  await (redis as any).call("BF.ADD", BF_KEY, "SKU-REAL-002");
}

async function bloomExists(productId: string): Promise<number> {
  return (redis as any).call("BF.EXISTS", BF_KEY, productId);
}

async function getProductWithBloom(
  productId: string,
  getFromDB: (id: string) => Promise<string | null>
): Promise<{ source: string; data: string | null }> {
  const exists = await bloomExists(productId);
  if (exists === 0) {
    return { source: "bloom-filter-blocked", data: null };
  }
  const cached = await redis.get(`product:${productId}`);
  if (cached) return { source: "cache", data: cached };
  const fromDB = await getFromDB(productId);
  if (fromDB) {
    await redis.setex(`product:${productId}`, 300, fromDB);
  }
  return { source: "db", data: fromDB };
}
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge: Compare Exact vs Approximate Counting — 1 Million Items

**Mục tiêu:** Đo memory và accuracy của Set vs HyperLogLog khi tracking 1 triệu unique items.

```typescript
// src/challenge.ts
import Redis from "ioredis";

const redis = new Redis({ host: "localhost", port: 6379, lazyConnect: true });

async function challenge() {
  await redis.connect();
  console.log("Connected to Redis");

  const SET_KEY = "challenge:set";
  const HLL_KEY = "challenge:hll";
  const NUM_ITEMS = 1_000_000;

  console.log(`\n=== CHALLENGE: ${NUM_ITEMS.toLocaleString()} unique items ===\n`);

  // Step 1: Insert 1M items into both Set and HLL
  console.log("Inserting items into Set...");
  const setStart = Date.now();
  let pipeline = redis.pipeline();

  for (let i = 1; i <= NUM_ITEMS; i++) {
    pipeline.sadd(SET_KEY, `item:${i}`);
    if (i % 50000 === 0) {
      await pipeline.exec();
      pipeline = redis.pipeline();
      process.stdout.write(`  Set progress: ${((i / NUM_ITEMS) * 100).toFixed(0)}%\r`);
    }
  }
  await pipeline.exec();
  const setInsertTime = Date.now() - setStart;
  console.log(`\n  Set insert time: ${setInsertTime}ms`);

  console.log("\nInserting items into HLL...");
  const hllStart = Date.now();
  let hllPipeline = redis.pipeline();
  for (let i = 1; i <= NUM_ITEMS; i++) {
    hllPipeline.pfadd(HLL_KEY, `item:${i}`);
    if (i % 50000 === 0) {
      await hllPipeline.exec();
      hllPipeline = redis.pipeline();
      process.stdout.write(`  HLL progress: ${((i / NUM_ITEMS) * 100).toFixed(0)}%\r`);
    }
  }
  await hllPipeline.exec();
  const hllInsertTime = Date.now() - hllStart;
  console.log(`\n  HLL insert time: ${hllInsertTime}ms`);

  // Step 2: Measure memory
  console.log("\n--- Memory Usage ---");
  const setMemory = Number(await redis.memory("USAGE", SET_KEY));
  const hllMemory = Number(await redis.memory("USAGE", HLL_KEY));
  console.log(`  Set:   ${(setMemory / 1024 / 1024).toFixed(2)} MB`);
  console.log(`  HLL:   ${(hllMemory / 1024).toFixed(2)} KB`);
  console.log(`  Ratio: ${(setMemory / hllMemory).toFixed(0)}x`);

  // Step 3: Count
  console.log("\n--- Count Results ---");
  const exactCount = await redis.scard(SET_KEY);
  const estimatedCount = await redis.pfcount(HLL_KEY);
  const error = Math.abs(estimatedCount - exactCount);
  const errorPct = ((error / exactCount) * 100).toFixed(4);

  console.log(`  Set exact count:    ${exactCount.toLocaleString()}`);
  console.log(`  HLL estimate:       ${estimatedCount.toLocaleString()}`);
  console.log(`  Absolute error:     ${error.toLocaleString()}`);
  console.log(`  Error rate:         ${errorPct}%`);
  console.log(`  Theoretical:       0.81%`);
  console.log(`  HLL acceptable:     ${parseFloat(errorPct) <= 1 ? "YES" : "NO"}`);

  // Step 4: Clean up
  await redis.del(SET_KEY, HLL_KEY);

  // Step 5: Analysis
  console.log("\n--- Decision Matrix ---");
  console.log("| Use Case                  | Recommended | Reason                    |");
  console.log("|---------------------------|-------------|---------------------------|");
  console.log("| Unique visitors (analytics) | HLL        | 0.8% error OK             |");
  console.log("| Payment count             | Set         | Exact required            |");
  console.log("| 100M+ items cardinality   | HLL         | 12KB vs 5GB               |");
  console.log("| Deduplication with removal | Set/Bloom  | HLL cannot remove        |");

  await redis.quit();
}

challenge().catch(console.error);
```

**Chạy:**
```bash
node --loader ts-node/esm src/challenge.ts
```

**Expected results:**
```
=== CHALLENGE: 1,000,000 unique items ===

Set insert time: ~30000-60000ms (tùy hardware)
HLL insert time: ~2000-5000ms

--- Memory Usage ---
Set:   ~55-70 MB
HLL:   ~12-15 KB
Ratio: ~4000-5000x

--- Count Results ---
Set exact count:    1,000,000
HLL estimate:       ~991,000 - 1,009,000
Error rate:         ~0.3-0.9%
HLL acceptable:    YES (within 0.81% theoretical)
```

**Phân tích:** HLL dùng ~5000x ít memory hơn Set với error rate < 1%. Tuy nhiên với business metric cần exact count → Set là lựa chọn duy nhất.

---

## 4. Reflection Questions (10-15 phút)

### Câu 1: Architectural Decision

Bạn đang thiết kế hệ thống analytics cho website có 10 triệu monthly visitors. Mỗi lượt view = (user_id, timestamp, page_url). Marketing team cần:

- **Metric A:** Unique visitors per page per day (accuracy ±5% acceptable)
- **Metric B:** Total views per page per day (exact)
- **Metric C:** "User đã view page này chưa?" — cho recommendation engine

Bạn sẽ thiết kế data storage cho từng metric như thế nào? Vẽ key design trên paper trước khi đọc tiếp.

<details>
<summary>Gợi ý</summary>

- **Metric A:** HyperLogLog → `PFADD uv:{date}:{page} {user_id}`; Memory ~12KB/page × 1000 pages = 12MB
- **Metric B:** String + INCRBY → `INCR views:{date}:{page}`; Exact count, INCR O(1)
- **Metric C:** Bitmap nếu user_id dense (auto-increment) → `SETBIT viewed:{user_id}:{date} {page_offset} 1`; Hoặc Bloom Filter per user nếu user_id sparse
</details>

### Câu 2: Trade-off Analysis

Một startup muốn implement "đã xem" feature cho video streaming platform với 2 triệu users, mỗi user xem 50-500 videos.

Họ đề xuất dùng Bloom Filter per user để track video đã xem. Phân tích xem đề xuất này có hợp lý không.

<details>
<summary>Gợi ý</summary>

Bloom Filter:
- 2M users × 500 videos × ~2 bits/item = 2M × 125KB = 250GB (nếu dùng Bitmap thuần túy)
- Bloom Filter giảm ~10x → 25GB per user (nếu FPR=1%)
- Problem: 25GB × 2M users = không khả thi

Alternative: Dùng Hash hoặc Set per user, với TTL = 90 ngày. 2M users × 500 videos × 20 bytes = 2TB. Vẫn lớn nhưng có thể partition theo user ID range.

Hoặc: Dùng Bloom Filter global cho top 100K videos, per-user chỉ lưu video IDs bằng Redis Set với TTL. User bấm "đã xem" không phải critical feature → acceptable false positive thấp có thể dùng Bloom.
</details>

### Câu 3: Operational

Bạn phát hiện PFCOUNT query trên dashboard chạy mất 500ms (p99), gây timeout cho API endpoint. Sau khi investigate, bạn thấy PFCOUNT đang merge 200 HyperLogLog keys.

Đưa ra 3 giải pháp với trade-off của từng giải pháp.

<details>
<summary>Gợi ý</summary>

1. **Cache PFCOUNT result** với TTL 30-60s → Giảm query frequency nhưng có stale data. Đơn giản, hiệu quả.

2. **Pre-aggregate vào daily/weekly keys** thay vì merge 200 keys mỗi query → `PFMERGE uv:week page:d01 ... page:d07` chạy background 1 lần/ngày. PFCOUNT chỉ query 1 key. Trade-off: không có real-time, chỉ có daily snapshot.

3. **Redesign key structure** — thay vì 1 key per page per day, dùng Redis Sorted Set với timestamp là score. Query by score range. Memory cao hơn nhưng query nhanh hơn.
</details>

### Câu 4: Geo Decision

Một ride-hailing startup quyết định dùng Redis Geospatial thay vì PostGIS cho matching driver-rider. Sau 6 tháng, họ gặp vấn đề:

- Driver location updates mỗi 3 giây → 100K updates/giây
- GEOSEARCH latency tăng dần theo số drivers
- Redis memory tăng liên tục không giảm

Phân tích root cause và đề xuất giải pháp.

<details>
<summary>Gợi ý</summary>

1. **Memory tăng:** GEOADD liên tục không có cleanup → sorted set grow vô hạn. Drivers offline không removed. Fix: Xóa driver khi offline, dùng ZREM sau khi driver không hoạt động > 5 phút.

2. **GEOSEARCH latency:** Radius quá lớn hoặc không partition. Fix: Dùng geohash precision partitioning, query cell + 8 neighbors.

3. **100K updates/sec:** GEOSEARCH read/write trên cùng key → contention. Fix: Shard theo geohash cell prefix, nhiều Redis keys nhỏ thay vì 1 key lớn.
</details>

### Câu 5: Failure Mode

Bạn deploy Bloom Filter với capacity 100K items. Sau 1 tháng, development team phát hiện DB query count không giảm — cache anti-penetration không hoạt động.

Liệt kê 5 possible root causes và cách verify/debug từng cái.

<details>
<summary>Gợi ý</summary>

1. **RedisBloom module không load** → `redis-cli MODULE LIST` check; `BF.ADD` sẽ error unknown command
2. **Bloom filter fill > capacity** → 100K capacity nhưng 500K items đã insert; `BF.INFO` xem actual size vs capacity
3. **Cache misses vẫn query DB** nhưng BF.EXISTS = 0 (đúng flow) → verify BF add rate vs miss rate
4. **FPR cao quá mức** → BF đã fill ~50%+ capacity → false positive rate tăng, không phân biệt được
5. **BF key bị evict** (nếu không set TTL hoặc key expired) → Redis eviction policy xóa BF key → rebuild từ đầu
</details>

---

## 5. Solution Guide

> **SPOILER WARNING** — Phần này chứa đáp án. Làm bài tập trước khi đọc.

---

### Exercise 1: Warm-up Solutions

Tất cả commands đã có expected output trong phần warm-up. Nếu kết quả khác:

- `BITCOUNT` = 0: Kiểm tra SETBIT đã chạy chưa
- `PFCOUNT` > actual: Đây là expected behavior — HLL có thể overestimate nhẹ
- `GEOSEARCH` empty: Kiểm tra longitude/latitude đúng format, dùng GEOPOS verify

---

### Exercise 2: Lab Solutions

**LAB 1 — Complete Implementation:**

```typescript
function getDateKey(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `dau:${y}${m}${d}`;
}

async function trackLogin(userId: number): Promise<number> {
  const key = getDateKey();
  return redis.setbit(key, userId, 1);
}

async function getDAU(date?: Date): Promise<number> {
  const key = getDateKey(date);
  return redis.bitcount(key);
}

async function getMAU(year: number, month: number): Promise<number> {
  const days = new Date(year, month, 0).getDate();
  const monthStr = String(month).padStart(2, "0");
  const keys = Array.from({ length: days }, (_, i) =>
    `dau:${year}${monthStr}${String(i + 1).padStart(2, "0")}`
  );
  const destKey = `mau:${year}${monthStr}`;
  await redis.bitop("OR", destKey, ...keys);
  await redis.expire(destKey, 48 * 3600);
  return redis.bitcount(destKey);
}
```

**LAB 2 — Complete Implementation:**

```typescript
async function trackVisitor(pageId: string, visitorId: string): Promise<number> {
  return redis.pfadd(`uv:page:${pageId}`, visitorId);
}

async function getPageUV(pageId: string): Promise<number> {
  return redis.pfcount(`uv:page:${pageId}`);
}

async function getCrossPageUV(pageIds: string[]): Promise<number> {
  const keys = pageIds.map((id) => `uv:page:${id}`);
  return redis.pfcount(...keys);
}
```

**LAB 3 — Complete Implementation:**

```typescript
async function addDriver(driver: Driver): Promise<number> {
  return redis.geoadd(DRIVERS_KEY, driver.longitude, driver.latitude, driver.id);
}

async function findNearbyDrivers(
  longitude: number,
  latitude: number,
  radiusKm: number,
  limit = 10
): Promise<Array<{ driverId: string; distance: string }>> {
  const raw = await redis.geosearch(
    DRIVERS_KEY,
    "FROMLONLAT", longitude, latitude,
    "BYRADIUS", radiusKm, "km",
    "WITHDIST",
    "ASC",
    "COUNT", limit
  );
  return raw.map((item) => ({
    driverId: item[0] as string,
    distance: item[1] as string,
  }));
}
```

**LAB 5 — Complete Implementation:**

```typescript
async function initBloomFilter(): Promise<void> {
  await (redis as any).call(
    "BF.RESERVE", BF_KEY,
    "0.001",
    "100000"
  );
  await (redis as any).call("BF.ADD", BF_KEY, "SKU-REAL-001");
  await (redis as any).call("BF.ADD", BF_KEY, "SKU-REAL-002");
  await redis.expire(BF_KEY, 30 * 86400); // TTL 30 days, rebuild định kỳ
}

async function bloomExists(productId: string): Promise<number> {
  return (redis as any).call("BF.EXISTS", BF_KEY, productId);
}

async function getProductWithBloom(
  productId: string,
  getFromDB: (id: string) => Promise<string | null>
): Promise<{ source: string; data: string | null }> {
  const exists = await bloomExists(productId);

  if (exists === 0) {
    // Bloom filter báo không tồn tại → skip DB hoàn toàn
    return { source: "bloom-filter-blocked", data: null };
  }

  // Bloom báo có → check cache
  const cached = await redis.get(`product:${productId}`);
  if (cached) return { source: "cache", data: cached };

  // Cache miss → get from DB
  const fromDB = await getFromDB(productId);
  if (fromDB) {
    await redis.setex(`product:${productId}`, 300, fromDB);
    await (redis as any).call("BF.ADD", BF_KEY, productId);
  }
  return { source: "db", data: fromDB };
}
```

---

### Challenge Solution

**Key findings:**

1. **Memory:** Set ~55-70MB, HLL ~12KB → ratio ~5000x
2. **Accuracy:** HLL error rate thực tế ~0.3-0.9% (luôn < 0.81% theoretical max với dataset nhỏ)
3. **Speed:** HLL insert ~5x nhanh hơn Set (PFADD O(1) vs SADD O(1) nhưng HLL operations nhẹ hơn)
4. **Remove:** Set support xóa, HLL không

**Decision framework:**

```
Nếu cần exact count + remove support        → Set
Nếu cần exact count, không cần remove         → Hash hoặc Sorted Set
Nếu chấp nhận ~0.81% error, scale lớn        → HyperLogLog
Nếu cần membership check + memory hiệu quả   → Bloom Filter
Nếu cần membership + remove support          → Cuckoo Filter (RedisBloom)
```

---

### Key Takeaways từ bài tập

1. **Bitmap chỉ hiệu quả với dense user ID.** Kiểm tra user ID distribution trước khi dùng.

2. **HLL error rate = 0.81% là worst-case.** Với cardinality ~1M, actual error thường < 0.5%.

3. **GEOSEARCH không deprecated** — chỉ GEORADIUS deprecated. Migrate code cũ.

4. **Bloom Filter cần capacity planning.** Insert > capacity → false positive rate tăng đột ngột.

5. **RedisBloom module không có trong standard Redis.** Phải dùng `redis/redis-stack:latest`.
