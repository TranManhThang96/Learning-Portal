# Day 26: Cache Stampede & Thundering Herd — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: TypeScript
**Redis**: 7.2+ standalone

---

## 0. Setup

```bash
# Start Redis
docker run -d --name redis-stampede \
  -p 6379:6379 \
  redis:7.2-alpine \
  redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

# Verify
redis-cli ping
# Expected: PONG

# Create project directory
mkdir -p day26 && cd day26
npm init -y
npm install ioredis typescript ts-node @types/node
npx tsc --init
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "strict": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "esModuleInterop": true
  },
  "include": ["src/**/*"]
}
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Cache Miss Storm — Simulate and Observe

**Setup**: Seed 1 cache key với TTL = 10 giây. Sau 10 giây, gửi 50 concurrent GET requests. Observe backend call pattern.

```bash
# Step 1: Set cache key với short TTL
redis-cli SET stampede:product:100 '{"id":100,"price":99.99}' EX 10
# Expected: OK

# Step 2: Verify TTL
redis-cli TTL stampede:product:100
# Expected: 10 (or 9, 8, depending on timing)

# Step 3: Wait for expiry
echo "Waiting for TTL expiry..."
sleep 12

# Step 4: Check cache expired
redis-cli GET stampede:product:100
# Expected: (nil)

# Step 5: Monitor Redis command stats
redis-cli INFO stats | grep -E "cmdstat_get|cmdstat_set"

# Step 6: With a script, fire 50 concurrent GETs and observe
# (script below in 1.2)
```

### 1.2. Measure Cache Miss Latency Spike

```typescript
// src/warmup-latency.ts
import Redis from "ioredis";

async function warmupLatencyTest() {
  const redis = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });
  const KEY = "stampede:product:100";

  // Reset
  await redis.del(KEY);

  // Set with TTL = 5 seconds
  await redis.set(KEY, JSON.stringify({ id: 100, price: 99.99 }), "EX", 5);
  console.log(`Cache set, TTL = 5s. Waiting...`);

  // Wait for expiry
  await new Promise((r) => setTimeout(r, 6000));

  // Measure latency of cache miss vs hit
  console.log("\n--- Cache MISS (after expiry) ---");
  const missTimes: number[] = [];
  for (let i = 0; i < 20; i++) {
    const start = Date.now();
    const val = await redis.get(KEY);
    missTimes.push(Date.now() - start);
    // Simulate backend by re-populating cache
    if (val === null) {
      await redis.set(KEY, JSON.stringify({ id: 100, price: 99.99 }), "EX", 5);
    }
  }
  missTimes.sort((a, b) => a - b);
  console.log(`  p50: ${missTimes[Math.floor(missTimes.length * 0.5)]}ms`);
  console.log(`  p99: ${missTimes[Math.floor(missTimes.length * 0.99)]}ms`);

  console.log("\n--- Cache HIT (fresh) ---");
  const hitTimes: number[] = [];
  for (let i = 0; i < 20; i++) {
    const start = Date.now();
    await redis.get(KEY);
    hitTimes.push(Date.now() - start);
  }
  hitTimes.sort((a, b) => a - b);
  console.log(`  p50: ${hitTimes[Math.floor(hitTimes.length * 0.5)]}ms`);
  console.log(`  p99: ${hitTimes[Math.floor(hitTimes.length * 0.99)]}ms`);

  // Observe INFO stats
  const stats = await redis.info("stats");
  const getMatch = stats.match(/cmdstat_get:calls=(\d+)/);
  const setMatch = stats.match(/cmdstat_set:calls=(\d+)/);
  console.log(`\nRedis stats — GET calls: ${getMatch?.[1]}, SET calls: ${setMatch?.[1]}`);

  await redis.quit();
}

warmupLatencyTest().catch(console.error);
```

```bash
npx ts-node src/warmup-latency.ts

# Expected output:
# Cache MISS: p50 ~0.3ms, p99 ~1ms (Redis itself is fast)
# Cache HIT:  p50 ~0.2ms, p99 ~0.5ms
# Note: In this isolated test, latency is low because no backend is called.
# Real stampede = cache miss + backend call simultaneously by many requests.
```

### 1.3. Verify Lock Behavior

```bash
# Acquire lock (NX = only if not exists)
redis-cli SET lock:product:100 "1" NX EX 5
# Expected: OK

# Try to acquire same lock again (should fail)
redis-cli SET lock:product:100 "1" NX EX 5
# Expected: (nil)

# Check TTL on lock
redis-cli TTL lock:product:100
# Expected: 5 (or 4, 3, ...)

# Release lock (unsafe — should use Lua)
redis-cli DEL lock:product:100
# Expected: 1

# Verify released
redis-cli SET lock:product:100 "1" NX EX 5
# Expected: OK
```

### 1.4. Test Lua Safe Lock Release

```bash
# Start a lock
redis-cli SET lock:product:100 "token-abc" NX EX 10

# Unsafe release (may delete lock held by another process)
redis-cli DEL lock:product:100

# Correct approach: Lua script (atomic check-and-delete)
redis-cli EVAL \
  "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end" \
  1 lock:product:100 "token-abc"
# Expected: 1 (deleted)

# Try again (lock already released)
redis-cli EVAL \
  "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end" \
  1 lock:product:100 "token-abc"
# Expected: 0 (lock not held by this token)
```

### 1.5. Jittered TTL Demo

```bash
# Set 10 keys with jittered TTLs (±20%)
for i in $(seq 1 10); do
  BASE=60
  JITTER=$(( (RANDOM % 48) - 24 ))  # -24 to +24
  TTL=$((BASE + JITTER))
  redis-cli SET "stampede:jitter:$i" "value-$i" EX $TTL
  echo "Key $i: TTL = $TTL seconds"
done

# Check that expiry times differ
for i in $(seq 1 10); do
  TTL=$(redis-cli TTL "stampede:jitter:$i")
  echo "Key $i: remaining TTL = $TTL seconds"
done

# Expected: TTLs vary from ~36 to ~84 seconds
# Not all expire at the same time
```

---

## 2. Hands-on Lab (60-70 phút)

**Scenario**: API service cache product details. Backend latency = 500ms (simulated). 500 concurrent requests hit same cache key. Without protection: 500 backend calls simultaneously. Your goal: implement all 3 strategies and measure p95/p99 latency.

### 2.1. Project Setup

```bash
cd day26
mkdir -p src
```

```bash
# package.json additions
npm install ioredis typescript ts-node @types/node
```

### 2.2. Implement Cache Client

```typescript
// src/cache-client.ts
import Redis from "ioredis";

export interface CacheOptions {
  lockTTL?: number;    // ms
  lockWait?: number;   // ms
  lockRetry?: number;  // ms
  softTTL?: number;    // ms
  hardTTL?: number;    // ms
  beta?: number;       // 0-1
}

interface CacheEntry<T> {
  value: T;
  storedAt: number;
  expiresAt: number;
  hardExpiresAt: number;
}

interface EarlyEntry<T> {
  value: T;
  lastRefreshAt: number;
  softTTL: number;
  hardTTL: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const SAFE_UNLOCK_SCRIPT = `
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
`;

// ─── Strategy 1: Mutex Lock ────────────────────────────────────────────────

export async function getWithMutex<T>(
  redis: Redis,
  key: string,
  fetcher: () => Promise<T>,
  options: Required<CacheOptions>
): Promise<T> {
  const lockKey = `lock:${key}`;
  const token = `${Date.now()}-${Math.random()}`;
  const { lockTTL, lockWait, lockRetry } = options;

  const acquired = await redis.set(lockKey, token, "PX", lockTTL, "NX");

  if (acquired === "OK") {
    try {
      const value = await fetcher();
      await redis.set(key, JSON.stringify(value), "EX", Math.floor(options.hardTTL / 1000));
      return value;
    } finally {
      await redis.eval(SAFE_UNLOCK_SCRIPT, 1, lockKey, token);
    }
  }

  // Wait for lock holder to populate cache
  const start = Date.now();
  let delay = lockRetry;

  while (Date.now() - start < lockWait) {
    await sleep(delay + Math.random() * 10);
    const cached = await redis.get(key);
    if (cached !== null) return JSON.parse(cached) as T;
    delay = Math.min(delay * 1.5, 2000);
  }

  return fetcher();
}

// ─── Strategy 2: Stale-While-Revalidate ──────────────────────────────────

async function storeSWREntry<T>(
  redis: Redis,
  key: string,
  value: T,
  softTTL: number,
  hardTTL: number
): Promise<void> {
  const now = Date.now();
  const entry: CacheEntry<T> = {
    value,
    storedAt: now,
    expiresAt: now + softTTL,
    hardExpiresAt: now + hardTTL,
  };
  await redis.set(key, JSON.stringify(entry), "EX", Math.floor(hardTTL / 1000));
}

export async function getWithSWR<T>(
  redis: Redis,
  key: string,
  fetcher: () => Promise<T>,
  options: Required<CacheOptions>
): Promise<T> {
  const { softTTL, hardTTL } = options;
  const now = Date.now();

  const raw = await redis.get(key);

  if (raw === null) {
    const value = await fetcher();
    await storeSWREntry(redis, key, value, softTTL, hardTTL);
    return value;
  }

  const entry: CacheEntry<T> = JSON.parse(raw);

  if (now < entry.expiresAt) return entry.value;

  if (now < entry.hardExpiresAt) {
    const refreshKey = `swr:${key}`;
    const acquired = await redis.set(refreshKey, "1", "NX", "EX", 30);
    if (acquired === "OK") {
      fetcher()
        .then((value) => storeSWREntry(redis, key, value, softTTL, hardTTL))
        .catch((err) => console.error(`SWR refresh failed: ${err.message}`));
    }
    return entry.value;
  }

  const value = await fetcher();
  await storeSWREntry(redis, key, value, softTTL, hardTTL);
  return value;
}

// ─── Strategy 3: Probabilistic Early Expiration ───────────────────────────

function shouldEarlyRefresh<T>(entry: EarlyEntry<T>, beta: number): boolean {
  const now = Date.now();
  const age = now - entry.lastRefreshAt;
  const ttlRatio = age / entry.hardTTL;
  const p = Math.max(0, Math.min(1, beta * ttlRatio));
  return Math.random() < p;
}

async function storeProbEntry<T>(
  redis: Redis,
  key: string,
  value: T,
  softTTL: number,
  hardTTL: number
): Promise<void> {
  const entry: EarlyEntry<T> = {
    value,
    lastRefreshAt: Date.now(),
    softTTL,
    hardTTL,
  };
  await redis.set(key, JSON.stringify(entry), "PX", hardTTL);
}

export async function getWithProbabilistic<T>(
  redis: Redis,
  key: string,
  fetcher: () => Promise<T>,
  options: Required<CacheOptions>
): Promise<T> {
  const raw = await redis.get(key);
  const { softTTL, hardTTL, beta } = options;

  if (raw === null) {
    const value = await fetcher();
    await storeProbEntry(redis, key, value, softTTL, hardTTL);
    return value;
  }

  const entry: EarlyEntry<T> = JSON.parse(raw);
  const now = Date.now();

  if (now >= entry.lastRefreshAt + entry.hardTTL) {
    const value = await fetcher();
    await storeProbEntry(redis, key, value, softTTL, hardTTL);
    return value;
  }

  if (shouldEarlyRefresh(entry, beta)) {
    const value = await fetcher();
    await storeProbEntry(redis, key, value, softTTL, hardTTL);
    return value;
  }

  return entry.value;
}

// ─── Benchmark ─────────────────────────────────────────────────────────────

export async function runBenchmark(
  redis: Redis,
  strategy: "mutex" | "swr" | "probabilistic",
  key: string,
  fetcher: () => Promise<string>,
  options: Required<CacheOptions>
): Promise<{ p50: number; p95: number; p99: number; errors: number; staleCount: number }> {
  const measurements: number[] = [];
  let errors = 0;
  let staleCount = 0;
  const CONCURRENT = 500;

  const promises = Array.from({ length: CONCURRENT }, async () => {
    const start = Date.now();
    try {
      let result: string;
      switch (strategy) {
        case "mutex":
          result = await getWithMutex(redis, key, fetcher, options);
          break;
        case "swr":
          result = await getWithSWR(redis, key, fetcher, options);
          staleCount++;
          break;
        case "probabilistic":
          result = await getWithProbabilistic(redis, key, fetcher, options);
          break;
      }
      measurements.push(Date.now() - start);
    } catch (e) {
      errors++;
    }
  });

  await Promise.all(promises);

  measurements.sort((a, b) => a - b);
  const n = measurements.length;
  return {
    p50: measurements[Math.floor(n * 0.5)] ?? 0,
    p95: measurements[Math.floor(n * 0.95)] ?? 0,
    p99: measurements[Math.floor(n * 0.99)] ?? 0,
    errors,
    staleCount,
  };
}
```

### 2.3. Stampede Lab

```typescript
// src/stampede-lab.ts
import Redis from "ioredis";
import { runBenchmark, CacheOptions } from "./cache-client";

async function main() {
  const redis = new Redis({
    host: "127.0.0.1",
    port: 6379,
    maxRetriesPerRequest: 3,
    enableReadyCheck: true,
  });

  // Verify Redis connection
  const pong = await redis.ping();
  console.log(`Redis connected: ${pong}`);

  // Configuration
  const KEY = "stampede:lab:product:999";
  const BACKEND_LATENCY_MS = 500; // Simulated slow backend

  const options: Required<CacheOptions> = {
    lockTTL: 2000,     // 2s — backend p95 × 4
    lockWait: 10000,   // 10s
    lockRetry: 50,     // 50ms
    softTTL: 10000,    // 10s
    hardTTL: 60000,    // 60s
    beta: 0.3,         // 30% aggressiveness
  };

  // Simulated slow backend (ML inference, external API call)
  const slowFetcher = async (): Promise<string> => {
    await new Promise((resolve) => setTimeout(resolve, BACKEND_LATENCY_MS));
    return JSON.stringify({
      id: 999,
      price: 299.99,
      name: `Product ${999}`,
      updatedAt: Date.now(),
    });
  };

  // ── Phase 1: Baseline (no protection) ─────────────────────────────────
  console.log("\n=== Phase 1: Baseline — No Protection ===");
  await redis.del(KEY);
  // First request populates cache
  await slowFetcher();
  // Expire cache
  await redis.set(KEY, "EXPIRED", "EX", 1);
  await new Promise((r) => setTimeout(r, 2000));

  const baselineStart = Date.now();
  let baselineErrors = 0;
  const BASELINE_CONCURRENT = 500;
  const baselinePromises = Array.from({ length: BASELINE_CONCURRENT }, async () => {
    const start = Date.now();
    try {
      const val = await redis.get(KEY);
      if (val === null || val === "EXPIRED") {
        await slowFetcher(); // All 500 requests hit backend
      }
    } catch {
      baselineErrors++;
    }
  });
  await Promise.all(baselinePromises);
  const baselineTotal = Date.now() - baselineStart;
  console.log(`  ${BASELINE_CONCURRENT} concurrent requests: ${baselineTotal}ms total`);
  console.log(`  Backend calls: ${BASELINE_CONCURRENT} (all hit simultaneously)`);
  console.log(`  Result: SEVERE STAMPEDE — backend overloaded`);

  // ── Phase 2: Mutex Lock ─────────────────────────────────────────────────
  console.log("\n=== Phase 2: Mutex Lock ===");
  await redis.del(KEY);
  await redis.del(`lock:${KEY}`);

  const mutexResult = await runBenchmark(redis, "mutex", KEY, slowFetcher, options);
  console.log(`  p50: ${mutexResult.p50}ms, p95: ${mutexResult.p95}ms, p99: ${mutexResult.p99}ms`);
  console.log(`  Errors: ${mutexResult.errors}`);
  console.log(`  Expected backend calls: ~1-2 (lock serialized requests)`);

  // ── Phase 3: Stale-While-Revalidate ───────────────────────────────────
  console.log("\n=== Phase 3: Stale-While-Revalidate ===");
  await redis.del(KEY);

  // Pre-populate with SWR entry (soft expired immediately for demo)
  await redis.set(
    KEY,
    JSON.stringify({
      value: JSON.stringify({ id: 999, price: 299.99 }),
      storedAt: Date.now() - 20000,
      expiresAt: Date.now() - 10000, // soft expired 10s ago
      hardExpiresAt: Date.now() + 40000, // hard expires in 40s
    }),
    "EX",
    60
  );

  const swrResult = await runBenchmark(redis, "swr", KEY, slowFetcher, options);
  console.log(`  p50: ${swrResult.p50}ms, p95: ${swrResult.p95}ms, p99: ${swrResult.p99}ms`);
  console.log(`  Errors: ${swrResult.errors}`);
  console.log(`  Stale serves: ${swrResult.staleCount}`);
  console.log(`  Expected backend calls: 1 (background refresh), rest served stale`);

  // ── Phase 4: Probabilistic Early Expiration ────────────────────────────
  console.log("\n=== Phase 4: Probabilistic Early Expiration (β=0.3) ===");
  await redis.del(KEY);

  // Pre-populate an entry that is near hard expiry. Probabilistic early
  // expiration smooths refresh for existing hot entries; it does not protect
  // a completely cold cache miss by itself.
  await redis.set(
    KEY,
    JSON.stringify({
      value: JSON.stringify({ id: 999, price: 299.99, name: "Product 999" }),
      lastRefreshAt: Date.now() - 55_000,
      softTTL: options.softTTL,
      hardTTL: options.hardTTL,
    }),
    "PX",
    options.hardTTL
  );

  const probResult = await runBenchmark(redis, "probabilistic", KEY, slowFetcher, options);
  console.log(`  p50: ${probResult.p50}ms, p95: ${probResult.p95}ms, p99: ${probResult.p99}ms`);
  console.log(`  Errors: ${probResult.errors}`);
  console.log(`  Expected backend calls: spread over TTL window, peak < ${BASELINE_CONCURRENT}`);

  // ── Phase 5: Jittered TTL Demo ─────────────────────────────────────────
  console.log("\n=== Phase 5: Jittered TTL Effect ===");
  const oldJitterKeys = await redis.keys("stampede:jitter:*");
  if (oldJitterKeys.length > 0) {
    await redis.del(...oldJitterKeys);
  }
  const BASE = 60;
  const JITTER_PCT = 0.2;
  for (let i = 0; i < 10; i++) {
    const jitter = (Math.random() * 2 - 1) * BASE * JITTER_PCT;
    const ttl = Math.floor(BASE + jitter);
    await redis.set(`stampede:jitter:${i}`, `value-${i}`, "EX", ttl);
  }
  console.log("  10 keys set with TTL 48-72s (base 60s, ±20% jitter)");
  console.log("  Expiry spread: 24-second window instead of synchronized");
  console.log("  Without jitter: all 10 expire at T=60s → potential 10× spike");
  console.log("  With jitter: spread over T=48-72s → peak reduced ~4×");

  // ── Summary ────────────────────────────────────────────────────────────
  console.log("\n=== Summary ===");
  console.log("| Strategy             | p50  | p95   | p99   | Backend Calls |");
  console.log("|---------------------|------|-------|-------|---------------|");
  console.log(`| Baseline (none)      | ${baselineTotal}ms | -     | -     | 500           |`);
  console.log(`| Mutex Lock          | ${mutexResult.p50}ms | ${mutexResult.p95}ms | ${mutexResult.p99}ms | 1-2           |`);
  console.log(`| SWR                 | ${swrResult.p50}ms | ${swrResult.p95}ms | ${swrResult.p99}ms | 1             |`);
  console.log(`| Probabilistic (β=0.3)| ${probResult.p50}ms | ${probResult.p95}ms | ${probResult.p99}ms | ~140           |`);

  await redis.quit();
  console.log("\nLab complete!");
}

main().catch(console.error);
```

```bash
npx ts-node src/stampede-lab.ts

# Expected output (approximate):
# Redis connected: PONG
#
# === Phase 1: Baseline — No Protection ===
#   500 concurrent requests: 502ms total
#   Backend calls: 500 (all hit simultaneously)
#   Result: SEVERE STAMPEDE — backend overloaded
#
# === Phase 2: Mutex Lock ===
#   p50: 501ms, p95: 520ms, p99: 550ms
#   Errors: 0
#   Expected backend calls: ~1-2 (lock serialized requests)
#
# === Phase 3: Stale-While-Revalidate ===
#   p50: 0ms, p95: 1ms, p99: 2ms
#   Errors: 0
#   Stale serves: 500
#   Expected backend calls: 1 (background refresh), rest served stale
#
# === Phase 4: Probabilistic Early Expiration (β=0.3) ===
#   p50: 0ms, p95: 2ms, p99: 500ms
#   Errors: 0
#   Expected backend calls: ~140 (probabilistic refreshes near hard expiry)
```

### 2.4. Verification

```bash
# After lab, verify:
# 1. Redis keys exist
redis-cli KEYS "stampede:*"

# 2. Lock keys cleaned up
redis-cli KEYS "lock:*"
# Expected: empty (locks auto-expire)

# 3. Check Redis memory usage
redis-cli INFO memory | grep used_memory_human
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge 1: Lock TTL Mismatch — Diagnose và Fix

**Setup**: Backend p95 = 2000ms. Lock TTL được set = 1000ms (wrong). Run stampede simulation. Observe multiple refreshers. Fix by increasing lock TTL.

```typescript
// src/challenge-lock-ttl.ts
// Part A: Demonstrate lock TTL too short → multiple refreshers
// Part B: Fix and verify

async function challengeLockTTL() {
  const redis = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });

  const KEY = "challenge:product:1";
  const BACKEND_LATENCY_MS = 2000; // 2000ms backend

  // WRONG: lock TTL = 1000ms < backend p95 = 2000ms
  const WRONG_LOCK_TTL = 1000;  // ms — TOO SHORT
  const CORRECT_LOCK_TTL = 8000; // ms — p95 × 4

  const slowFetcher = async (): Promise<string> => {
    await new Promise((r) => setTimeout(r, BACKEND_LATENCY_MS));
    return JSON.stringify({ id: 1, price: 49.99 });
  };

  // Count how many times backend is called
  let backendCallCount = 0;
  const instrumentedFetcher = async (): Promise<string> => {
    backendCallCount++;
    return slowFetcher();
  };

  // Part A: Wrong TTL
  console.log("\n=== Part A: Lock TTL = 1000ms (too short) ===");
  backendCallCount = 0;
  await redis.del(KEY);
  await redis.del(`lock:${KEY}`);

  const startA = Date.now();
  await Promise.all(
    Array.from({ length: 100 }, async () => {
      const lockKey = `lock:${KEY}`;
      const token = `${Date.now()}-${Math.random()}`;

      // Try lock
      const acquired = await redis.set(lockKey, token, "PX", WRONG_LOCK_TTL, "NX");
      if (acquired === "OK") {
        try {
          await instrumentedFetcher();
          await redis.set(KEY, "done", "EX", 60);
        } finally {
          await redis.eval(
            `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`,
            1, lockKey, token
          );
        }
      } else {
        // Wait and retry
        await new Promise((r) => setTimeout(r, 200));
        const val = await redis.get(KEY);
        if (!val) await instrumentedFetcher();
      }
    })
  );

  console.log(`  Backend calls: ${backendCallCount}`);
  console.log(`  Duration: ${Date.now() - startA}ms`);
  console.log(`  Expected: >1 backend call (lock expired mid-refresh)`);

  // Part B: Correct TTL
  console.log("\n=== Part B: Lock TTL = 8000ms (correct) ===");
  backendCallCount = 0;
  await redis.del(KEY);
  await redis.del(`lock:${KEY}`);

  const startB = Date.now();
  await Promise.all(
    Array.from({ length: 100 }, async () => {
      const lockKey = `lock:${KEY}`;
      const token = `${Date.now()}-${Math.random()}`;

      const acquired = await redis.set(lockKey, token, "PX", CORRECT_LOCK_TTL, "NX");
      if (acquired === "OK") {
        try {
          await instrumentedFetcher();
          await redis.set(KEY, "done", "EX", 60);
        } finally {
          await redis.eval(
            `if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end`,
            1, lockKey, token
          );
        }
      } else {
        await new Promise((r) => setTimeout(r, 200));
        const val = await redis.get(KEY);
        if (!val) await instrumentedFetcher();
      }
    })
  );

  console.log(`  Backend calls: ${backendCallCount}`);
  console.log(`  Duration: ${Date.now() - startB}ms`);
  console.log(`  Expected: 1 backend call (lock held long enough)`);

  await redis.quit();
}

challengeLockTTL().catch(console.error);
```

**Tasks**:
- Run Part A, observe backend call count > 1
- Calculate correct lock TTL: `backend_p95 × 4 = 2000 × 4 = 8000ms`
- Run Part B, verify backend call count = 1
- Write reflection: why did lock expiry during refresh cause multiple refreshers?

### Challenge 2: Multi-Service Distributed Stampede

**Scenario**: 3 microservices (Order, Payment, Notification) cùng cache `user:12345:profile`. Without distributed coalescing, each service sees stampede internally. Design and implement cross-service coalescing.

```typescript
// src/challenge-distributed-coalescing.ts
// Simulate: 3 services, each with 100 concurrent requests for same user profile

async function challengeDistributedCoalescing() {
  const redis = new Redis({ host: "127.0.0.1", port: 6379, maxRetriesPerRequest: 3 });

  const KEY = "user:12345:profile";
  const BACKEND_LATENCY_MS = 500;

  let backendCallCount = 0;
  const slowFetcher = async (): Promise<string> => {
    backendCallCount++;
    await new Promise((r) => setTimeout(r, BACKEND_LATENCY_MS));
    return JSON.stringify({ id: 12345, name: "John Doe" });
  };

  // ── Local coalescing only ──────────────────────────────────────────────
  console.log("\n=== Local Coalescing Only ===");
  backendCallCount = 0;
  await redis.del(KEY);

  // Simulate 3 services × 100 concurrent requests = 300 total
  const serviceCount = 3;
  const requestsPerService = 100;
  const localInFlight = new Map<number, Promise<string>>();

  await Promise.all(
    Array.from({ length: serviceCount * requestsPerService }, async (_, i) => {
      const serviceId = Math.floor(i / requestsPerService);
      const cached = await redis.get(KEY);
      if (cached === null) {
        let promise = localInFlight.get(serviceId);
        if (!promise) {
          promise = slowFetcher().then(async (value) => {
            await redis.set(KEY, value, "EX", 60);
            return value;
          });
          localInFlight.set(serviceId, promise);
        }
        await promise;
      }
    })
  );

  console.log(`  Total requests: ${serviceCount * requestsPerService}`);
  console.log(`  Backend calls: ${backendCallCount}`);
  console.log(`  Expected: 3 (1 per service)`);
  console.log(`  Problem: backend overloaded 3×`);

  // ── With distributed coalescing ──────────────────────────────────────────
  console.log("\n=== With Distributed Coalescing (Redis SET NX) ===");
  backendCallCount = 0;
  await redis.del(KEY);
  await redis.del(`coalesce:${KEY}`);

  const COALESCE_TTL = 10000; // ms

  await Promise.all(
    Array.from({ length: serviceCount * requestsPerService }, async (_, i) => {
      const serviceId = Math.floor(i / requestsPerService);
      const coalesceKey = `coalesce:${KEY}`;

      // Try to become coordinator
      const isCoordinator = await redis.set(coalesceKey, `${serviceId}`, "NX", "PX", COALESCE_TTL);

      if (isCoordinator === "OK") {
        // Coordinator: fetch and store
        await slowFetcher();
        await redis.set(KEY, "cached", "EX", 60);
        await redis.set(`${coalesceKey}:done`, "1", "EX", 60);
      } else {
        // Wait for coordinator to finish
        const start = Date.now();
        while (Date.now() - start < COALESCE_TTL) {
          const done = await redis.get(`${coalesceKey}:done`);
          if (done === "1") break;
          const cached = await redis.get(KEY);
          if (cached !== null) break;
          await new Promise((r) => setTimeout(r, 20));
        }
      }
    })
  );

  console.log(`  Total requests: ${serviceCount * requestsPerService}`);
  console.log(`  Backend calls: ${backendCallCount}`);
  console.log(`  Expected: 1 (distributed coalescing across services)`);

  await redis.quit();
}

challengeDistributedCoalescing().catch(console.error);
```

**Tasks**:
- Run both scenarios
- Verify distributed coalescing reduces backend calls from 3 to 1
- Explain: why does local coalescing fail across services?

---

## 4. Reflection Questions (Open-ended)

1. **TTL Selection Trade-off**: Bạn cache product price với TTL = 300s. Nhưng price có thể thay đổi mỗi 30 giây (flash sale). Stale-while-revalidate với SOFT_TTL = 10s, HARD_TTL = 60s. Khách hàng thấy giá sai trong bao lâu? TTL-based cache có phải là tool đúng cho use case này không? Đề xuất alternative.

2. **Algorithm Choice**: Hệ thống của bạn chịu 100K requests/giây cho 1 hot key. Backend p95 = 100ms. Bạn chọn strategy nào? Tại sao không chọn các strategy khác? Nếu backend p95 = 3000ms (ML inference), lựa chọn của bạn có thay đổi không?

3. **Lock vs SWR for Write-Heavy Data**: Bạn cache inventory count — dữ liệu thay đổi liên tục mỗi 5-10 giây. Cache stampede protection nào phù hợp? Tại sao write-through cache không phải luôn là câu trả lời?

4. **Probabilistic β Tuning**: Bạn set β = 0.1 và thấy backend vẫn bị stampede. Bạn tăng β lên 0.9. Trade-off là gì? Làm thế nào để find sweet spot mà không gây stampede trong production?

5. **Multi-layer Cache Stampede**: Bạn có local in-memory cache (L1) và Redis cache (L2). Hot key hết hạn ở L1 trước L2. Thundering herd xảy ra ở layer nào? Thiết kế multi-layer stampede protection như thế nào?

---

## 5. Solution Guide

> **WARNING: Spoiler** — Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.1 Cache miss storm expected**:
```
Cache set: OK, TTL = 10s
After 12s wait: GET returns (nil) — cache expired
Without backend simulation, Redis responds fast (~0.2ms)
Real stampede = cache miss + backend call simultaneously
```

**1.2 Latency difference**:
```
Cache miss: Redis returns nil fast (~0.3ms)
Cache hit:  Redis returns value fast (~0.2ms)
The difference is minimal in isolation
The problem emerges when backend is involved:
  500 cache misses → 500 backend calls → backend overwhelmed
```

**1.3 Lock NX behavior**:
```
First SET NX: OK (lock acquired)
Second SET NX: (nil) (already held)
TTL check: returns remaining TTL
DEL: removes lock immediately
```

**1.4 Lua safe unlock**:
```
Correct: Lua ensures only lock owner (matching token) can delete
Unsafe: DEL removes lock even if held by another process
Risk of unsafe DEL: another process acquires lock between check and delete
→ race condition → two processes think they own the lock
```

**1.5 Jittered TTL expected output**:
```
Keys with base=60s, ±20% jitter:
  TTLs: ~48, ~52, ~55, ~58, ~62, ~65, ~68, ~72, ~54, ~60 seconds
  Spread: ~24 seconds (from 48 to 72)
  Without jitter: all at exactly 60s → synchronized expiry
```

---

### Lab Solutions

**Phase 1 Baseline**:
```
500 concurrent requests, no protection
All 500 hit backend simultaneously
Duration ≈ BACKEND_LATENCY = 500ms (parallel)
Backend load: 500 simultaneous calls
This is the stampede — exactly what we want to prevent
```

**Phase 2 Mutex Lock**:
```
p50 ≈ 500ms (first request must wait for backend)
p95 ≈ 520ms (slight overhead from lock polling)
p99 ≈ 550ms (last poller)
Backend calls: 1-2 (if lock TTL too short, could be more)
Mutex works best when backend is slower than polling overhead
```

**Phase 3 SWR**:
```
p50 ≈ 0ms (served stale immediately)
p95 ≈ 1ms (cache read)
p99 ≈ 2ms (cache read)
Backend calls: 1 (background refresh)
Stale serves: 500 (all requests served stale, then 1 refresh)
Trade-off: all requests served stale data for up to 10 seconds
Best when: staleness is acceptable; latency is critical
```

**Phase 4 Probabilistic**:
```
p50 ≈ 0ms (most requests don't trigger refresh)
p95 ≈ 2ms (most don't trigger, some do)
p99 ≈ 500ms (the requests that hit backend)
Backend calls: ~150 (β=0.3, spread over 60s window)
Peak at TTL expiry: 25% of 500 = 125 calls (vs 500 without)
Best when: staleness unacceptable; need some smoothing
```

**Phase 5 Jitter**:
```
Without jitter (base=60): 10 keys expire at T=60 → potential 10× spike
With 20% jitter: TTL range 48-72s → 24s spread → peak reduced ~4×
Formula: spread = 2 × base × jitter_percent
```

---

### Challenge Solutions

**Challenge 1: Lock TTL**:
```
Wrong TTL = 1000ms < backend_p95 = 2000ms
Timeline:
  T=0:   Request #1 acquires lock, starts backend (2000ms)
  T=1000: Lock expires (TTL=1000ms)
  T=1000: Request #2 acquires lock (lock not held!)
  T=1000: Request #2 starts SECOND backend call
  T=2000: Request #1 finishes, sets cache, releases lock
  T=2000: Request #2 finishes, sets cache (overwrites), releases lock
Result: 2 backend calls (one from each process that acquired lock)

Fix: lock_ttl ≥ backend_p95 × 4 = 8000ms
Why ×4: p95 = 2000ms, but tail latency (p99 = 3000ms) still possible
        Lock must survive p99 to guarantee single refresher
```

**Challenge 2: Distributed Coalescing**:
```
Without distributed coalescing:
  Service 1: 100 requests coalesced to 1 call
  Service 2: 100 requests coalesced to 1 call
  Service 3: 100 requests coalesced to 1 call
  Total: 3 backend calls
  Problem: still 3× backend load

With distributed coalescing (Redis SET NX):
  First request across ALL services: acquires coalesce key
  Coordinator: 1 backend call
  All other requests: wait for done signal
  Total: 1 backend call (regardless of service count)
  Redis acts as coordination layer across service boundaries

Why local coalescing fails: Promise.all within a process only coalesces
goroutines in that process. Other pods have separate Node.js event loops.
Redis-based coalescing is required for cross-service coordination.
```

---

### Key Takeaways

1. **Cache stampede = timing problem, not load problem**: 500 requests/500ms = manageable. 500 requests hitting backend simultaneously = overload. The fix is temporal distribution, not capacity increase.
2. **Mutex lock is simple but has TTL sensitivity**: lock_ttl must be ≥ backend_p99 × 2 minimum. Too short → multiple refreshers. Too long → slow recovery if lock holder crashes.
3. **Stale-while-revalidate trades consistency for latency**: serves stale data (up to soft TTL) immediately while refreshing. Best for latency-critical paths where mild staleness is acceptable.
4. **Probabilistic early expiration is parameter-sensitive**: β too low = insufficient smoothing, β too high = excessive backend load. Load test with production-like traffic patterns to tune.
5. **Jitter is the simplest protection**: adding ±20% TTL jitter alone can reduce peak load by 4×. Works best as a baseline, combined with other strategies.
6. **Local coalescing is insufficient for distributed systems**: each service instance/pod needs Redis-level coordination. Local coalescing reduces intra-instance burst; Redis SET NX reduces inter-instance burst.
7. **Always measure backend p95 before choosing lock TTL**: lock_ttl is a function of backend latency, not an arbitrary number. "Use 5 seconds" is wrong; "use backend_p95 × 4" is correct.
