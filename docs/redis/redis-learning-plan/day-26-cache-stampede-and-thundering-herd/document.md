# Day 26: Cache Stampede & Thundering Herd — Reference Document

---

## 1. Command Cheat Sheet

### Lock-related Redis Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `SET key value NX PX ms` | `SET lock:product:123 "1" NX PX 5000` | Acquire distributed lock. Returns `OK` if acquired, `nil` if already held. |
| `SET key value EX sec NX` | `SET lock:product:123 "1" EX 5 NX` | Lock với expiry bằng second (alternative syntax). |
| `GET key` | `GET lock:product:123` | Check if lock exists (used in polling). |
| `DEL key` | `DEL lock:product:123` | Release lock (unsafe without Lua check). |
| `TTL key` | `TTL lock:product:123` | Check remaining lock TTL. |
| `EXPIRE key sec` | `EXPIRE lock:product:123 5` | Set lock expiry. |
| `EVAL script keys argc` | `EVAL "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end" 1 lock:product:123 "1"` | Safe lock release (atomic check-and-delete). |

### Cache Data Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `SET key value EX sec` | `SET cache:product:123 '{"price":99}' EX 300` | Set cache với TTL. |
| `GET key` | `GET cache:product:123` | Read cache. |
| `EXISTS key` | `EXISTS cache:product:123` | Check cache existence (useful for SWR). |
| `EXPIRE key sec` | `EXPIRE cache:product:123 300` | Update TTL. |
| `SETEX key sec value` | `SETEX cache:product:123 300 '{"price":99}'` | Set + expiry in one command. |
| `SETNX key value` | `SETNX cache:product:123 '{"price":99}'` | Set if not exists (used in coalescing). |

### Debug & Monitoring

| Command | Syntax | Mô tả |
|---|---|---|
| `INFO stats` | `INFO stats` | Xem `cmdstat_get`, `cmdstat_set` — detect stampede via miss rate spike. |
| `INFO commandstats` | `INFO commandstats` | Per-command stats — spike in command count = stampede. |
| `SLOWLOG GET 10` | `SLOWLOG GET 10` | Check for slow queries (backend overload indicator). |
| `CLIENT LIST` | `CLIENT LIST` | Check connected clients (connection storm). |
| `MONITOR` | `MONITOR` | Real-time command stream — detect burst pattern. |

---

## 2. Comparison Tables

### Strategy Comparison — All Approaches

| Aspect | Mutex Lock | Stale-While-Revalidate | Probabilistic Early Expiry | Jittered TTL | Request Coalescing |
|---|---|---|---|---|---|
| **Complexity** | Medium | Medium | Low-Medium | Trivial | Low-Medium |
| **Consistency** | Strong | Weak (stale serve) | Strong | Strong | Strong |
| **Backend load smoothing** | Yes (1 refresher) | Yes (1 refresher) | Yes (probabilistic) | Yes (spread expiry) | Yes (1 refresher) |
| **Latency impact** | Lock overhead | Stale serve possible | None | None | Promise chain |
| **Memory overhead** | 1 lock key per cache key | Metadata per entry | Metadata per entry | None | In-process map |
| **Failure risk** | Lock expiry mid-refresh | Stale data indefinitely | Ineffective if β too low | Limited spread if jitter too small | Cross-instance burst |
| **Implementation** | SET NX + Lua | Entry versioning | Probability function | Random offset on TTL | SET NX + polling |

### Lock TTL Sizing Guide

| Backend p95 | Recommended lock_ttl | Reasoning |
|---|---|---|
| 100ms | 500ms | p95 × 5 (safe margin) |
| 500ms | 2000ms | p95 × 4 |
| 1000ms | 4000ms | p95 × 4 |
| 3000ms | 12000ms | p95 × 4 (ML inference, etc.) |

### SWR TTL Sizing Guide

| Data freshness requirement | SOFT_TTL | HARD_TTL | SOFT/HARD ratio |
|---|---|---|---|
| Real-time (price, inventory) | 2-5s | 10-30s | 0.2-0.5 |
| Near real-time (feed, news) | 10-30s | 60-120s | 0.2-0.3 |
| Content (product detail, user profile) | 30-60s | 300-600s | 0.1-0.2 |
| Reference data (config, taxonomy) | 60-300s | 3600-7200s | 0.02-0.08 |

---

## 3. TypeScript — Complete Runable Code

### Main Cache Client with All Strategies

```typescript
// cache-client.ts
import Redis from "ioredis";

export interface CacheOptions {
  // Mutex lock settings
  lockTTL?: number;       // ms
  lockWait?: number;      // ms
  lockRetry?: number;     // ms

  // SWR settings
  softTTL?: number;       // ms
  hardTTL?: number;       // ms

  // Probabilistic settings
  beta?: number;          // 0-1, aggressiveness

  // Coalescing settings
  coalesceTTL?: number;   // ms
}

interface CacheEntry<T> {
  value: T;
  storedAt: number;
  expiresAt: number;    // soft expiry
  hardExpiresAt: number; // hard expiry
}

interface EarlyEntry<T> {
  value: T;
  lastRefreshAt: number;
  softTTL: number;
  hardTTL: number;
}

// ─── Mutex Lock ──────────────────────────────────────────────────────────────

export async function getWithMutex<T>(
  redis: Redis,
  key: string,
  fetcher: () => Promise<T>,
  options: Required<CacheOptions>
): Promise<T> {
  const lockKey = `lock:${key}`;
  const { lockTTL, lockWait, lockRetry } = options;

  const acquired = await redis.set(lockKey, '1', 'PX', lockTTL, 'NX');

  if (acquired === 'OK') {
    try {
      const value = await fetcher();
      await redis.set(key, JSON.stringify(value), 'EX', Math.floor(options.hardTTL! / 1000));
      return value;
    } finally {
      await redis.eval(
        `if redis.call("get", KEYS[1]) == ARGV[1] then
           return redis.call("del", KEYS[1])
         else return 0 end`,
        1, lockKey, '1'
      );
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

  // Timeout — fallback to direct fetch
  return fetcher();
}

// ─── Stale-While-Revalidate ─────────────────────────────────────────────────

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
    // Cache miss
    const value = await fetcher();
    await storeSWREntry(redis, key, value, softTTL, hardTTL);
    return value;
  }

  const entry: CacheEntry<T> = JSON.parse(raw);

  if (now < entry.expiresAt) {
    // Fresh
    return entry.value;
  }

  if (now < entry.hardExpiresAt) {
    // Soft expired: serve stale + background refresh
    const refreshKey = `swr:${key}`;
    const acquired = await redis.set(refreshKey, '1', 'NX', 'EX', 30);

    if (acquired === 'OK') {
      fetcher()
        .then((value) => storeSWREntry(redis, key, value, softTTL, hardTTL))
        .catch((err) => console.error(`SWR refresh failed for ${key}:`, err.message));
    }

    return entry.value;
  }

  // Hard expired
  const value = await fetcher();
  await storeSWREntry(redis, key, value, softTTL, hardTTL);
  return value;
}

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
  await redis.set(key, JSON.stringify(entry), 'EX', Math.floor(hardTTL / 1000));
}

// ─── Probabilistic Early Expiration ─────────────────────────────────────────

function shouldEarlyRefresh<T>(entry: EarlyEntry<T>, beta: number): boolean {
  const now = Date.now();
  const age = now - entry.lastRefreshAt;
  const ttlRatio = age / entry.hardTTL;
  const p = Math.max(0, Math.min(1, beta * ttlRatio));
  return Math.random() < p;
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
  await redis.set(key, JSON.stringify(entry), 'PX', hardTTL);
}

// ─── Jittered TTL Helper ─────────────────────────────────────────────────────

export function jitterTTL(baseTTLSec: number, jitterPercent: number = 0.1): number {
  const jitter = baseTTLSec * jitterPercent;
  const offset = (Math.random() * 2 - 1) * jitter;
  return Math.floor(baseTTLSec + offset);
}

// ─── Benchmark ───────────────────────────────────────────────────────────────

export async function benchmark(
  redis: Redis,
  strategy: 'mutex' | 'swr' | 'probabilistic',
  key: string,
  fetcher: () => Promise<string>,
  options: Required<CacheOptions>
): Promise<{ p50: number; p95: number; p99: number; errors: number }> {
  const measurements: number[] = [];
  let errors = 0;
  const ITERATIONS = 1000;
  const CONCURRENT = 100;

  // Simulate thundering herd: many concurrent requests for same key
  for (let batch = 0; batch < ITERATIONS / CONCURRENT; batch++) {
    const promises = Array.from({ length: CONCURRENT }, async () => {
      const start = Date.now();
      try {
        let result: string;
        switch (strategy) {
          case 'mutex':
            result = await getWithMutex(redis, key, fetcher, options);
            break;
          case 'swr':
            result = await getWithSWR(redis, key, fetcher, options);
            break;
          case 'probabilistic':
            result = await getWithProbabilistic(redis, key, fetcher, options);
            break;
        }
        measurements.push(Date.now() - start);
      } catch {
        errors++;
      }
    });

    // Wait a bit between batches to simulate real traffic
    if (batch < ITERATIONS / CONCURRENT - 1) {
      await sleep(10);
    }

    await Promise.all(promises);
  }

  measurements.sort((a, b) => a - b);
  const n = measurements.length;
  return {
    p50: measurements[Math.floor(n * 0.50)] ?? 0,
    p95: measurements[Math.floor(n * 0.95)] ?? 0,
    p99: measurements[Math.floor(n * 0.99)] ?? 0,
    errors,
  };
}

// ─── Utility ─────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

### Stampede Simulator

```typescript
// stampede-simulator.ts
// Simulates cache stampede: 1000 concurrent requests, same key,
// backend takes 500ms to respond. Measures latency distribution.

import Redis from "ioredis";
import { getWithMutex, getWithSWR, getWithProbabilistic, jitterTTL,
         benchmark, CacheOptions } from "./cache-client";

async function main() {
  const redis = new Redis({ host: '127.0.0.1', port: 6379, maxRetriesPerRequest: 3 });

  const KEY = 'stampede:test:product:123';
  const BACKEND_LATENCY_MS = 500; // Simulated slow backend
  const CONCURRENT_REQUESTS = 1000;

  // Simulated slow backend
  const slowFetcher = async (): Promise<string> => {
    await new Promise((resolve) => setTimeout(resolve, BACKEND_LATENCY_MS));
    return JSON.stringify({ id: 123, price: 99.99, updatedAt: Date.now() });
  };

  const baseOptions: Required<CacheOptions> = {
    lockTTL: 2000,
    lockWait: 10000,
    lockRetry: 50,
    softTTL: 10000,
    hardTTL: 60000,
    beta: 0.3,
    coalesceTTL: 5000,
  };

  // ── Baseline: No protection ─────────────────────────────────────────────
  console.log('\n=== Baseline: No protection (direct fetches) ===');
  await redis.del(KEY);

  const baselineStart = Date.now();
  await Promise.all(
    Array.from({ length: CONCURRENT_REQUESTS }, async (_, i) => {
      const start = Date.now();
      try {
        const cached = await redis.get(KEY);
        if (cached === null) {
          await slowFetcher(); // simulate backend
        }
        return Date.now() - start;
      } catch { return Date.now() - start; }
    })
  );
  const baselineTime = Date.now() - baselineStart;
  console.log(`${CONCURRENT_REQUESTS} concurrent requests: ${baselineTime}ms total`);
  console.log(`  Expected backend load: ${CONCURRENT_REQUESTS} simultaneous calls`);

  // ── Strategy 1: Mutex Lock ──────────────────────────────────────────────
  console.log('\n=== Strategy 1: Mutex Lock ===');
  await redis.del(KEY);

  const mutexResult = await benchmark(redis, 'mutex', KEY, slowFetcher, baseOptions);
  console.log(`  p50: ${mutexResult.p50}ms, p95: ${mutexResult.p95}ms, p99: ${mutexResult.p99}ms`);
  console.log(`  Errors: ${mutexResult.errors}`);
  console.log(`  Expected backend load: 1 call per lock TTL window`);

  // ── Strategy 2: Stale-While-Revalidate ─────────────────────────────────
  console.log('\n=== Strategy 2: Stale-While-Revalidate ===');
  await redis.del(KEY);

  const swrResult = await benchmark(redis, 'swr', KEY, slowFetcher, baseOptions);
  console.log(`  p50: ${swrResult.p50}ms, p95: ${swrResult.p95}ms, p99: ${swrResult.p99}ms`);
  console.log(`  Errors: ${swrResult.errors}`);
  console.log(`  Expected backend load: 1 call per soft TTL expiry`);

  // ── Strategy 3: Probabilistic Early Expiration ──────────────────────────
  console.log('\n=== Strategy 3: Probabilistic Early Expiration (β=0.3) ===');
  await redis.del(KEY);

  const probResult = await benchmark(redis, 'probabilistic', KEY, slowFetcher, baseOptions);
  console.log(`  p50: ${probResult.p50}ms, p95: ${probResult.p95}ms, p99: ${probResult.p99}ms`);
  console.log(`  Errors: ${probResult.errors}`);

  // ── Jitter Demo ─────────────────────────────────────────────────────────
  console.log('\n=== Jittered TTL Demo ===');
  console.log('  10 random TTLs with ±20% jitter:');
  for (let i = 0; i < 10; i++) {
    console.log(`    TTL ${i + 1}: ${jitterTTL(300, 0.2)}s`);
  }

  await redis.quit();
}

main().catch(console.error);
```

---

## 4. Go Implementation

### Mutex Lock + SWR in Go

```go
// stampede.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"
	"time"

	"github.com/redis/go-redis/v9"
)

// ─── Types ───────────────────────────────────────────────────────────────────

type CacheEntry[T any] struct {
	Value         T
	StoredAt      int64
	ExpiresAt     int64 // soft TTL
	HardExpiresAt int64 // hard TTL
}

type Options struct {
	LockTTL   time.Duration
	LockWait  time.Duration
	LockRetry time.Duration
	SoftTTL   time.Duration
	HardTTL   time.Duration
}

var defaultOptions = Options{
	LockTTL:   2 * time.Second,
	LockWait:  10 * time.Second,
	LockRetry: 50 * time.Millisecond,
	SoftTTL:   10 * time.Second,
	HardTTL:   60 * time.Second,
}

// ─── Mutex Lock ───────────────────────────────────────────────────────────────

// SafeReleaseLock uses Lua script for atomic check-and-delete
const safeReleaseLockScript = `
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
`

func getWithMutex[T any](
	ctx context.Context,
	rdb *redis.Client,
	key string,
	fetcher func() (T, error),
	opts Options,
) (T, error) {
	lockKey := fmt.Sprintf("lock:%s", key)
	token := fmt.Sprintf("%d", time.Now().UnixNano())

	// Try to acquire lock
	acquired, err := rdb.SetNX(ctx, lockKey, token, opts.LockTTL).Result()
	if err != nil {
		var zero T
		return zero, fmt.Errorf("lock acquire error: %w", err)
	}

	if acquired {
		defer func() {
			rdb.Eval(ctx, safeReleaseLockScript, []string{lockKey}, token)
		}()

		value, err := fetcher()
		if err != nil {
			var zero T
			return zero, err
		}

		// Store in cache
		data, _ := json.Marshal(value)
		rdb.Set(ctx, key, data, opts.HardTTL)
		return value, nil
	}

	// Lock not acquired — poll for cache
	start := time.Now()
	delay := opts.LockRetry

	for time.Since(start) < opts.LockWait {
		time.Sleep(delay + time.Duration(rand.Intn(20))*time.Millisecond)

		data, err := rdb.Get(ctx, key).Bytes()
		if err == nil {
			var value T
			json.Unmarshal(data, &value)
			return value, nil
		}

		// Try to grab lock in case holder crashed
		acquired2, _ := rdb.SetNX(ctx, lockKey, token, opts.LockTTL).Result()
		if acquired2 {
			defer func() {
				rdb.Eval(ctx, safeReleaseLockScript, []string{lockKey}, token)
			}()
			return fetcher()
		}

		delay = time.Duration(float64(delay) * 1.5)
		if delay > 2*time.Second {
			delay = 2 * time.Second
		}
	}

	// Timeout — fallback
	return fetcher()
}

// ─── Stale-While-Revalidate ───────────────────────────────────────────────────

func getWithSWR[T any](
	ctx context.Context,
	rdb *redis.Client,
	key string,
	fetcher func() (T, error),
	opts Options,
) (T, error) {
	data, err := rdb.Get(ctx, key).Bytes()
	now := time.Now()

	if err == redis.Nil {
		// Cache miss
		value, err := fetcher()
		if err != nil {
			var zero T
			return zero, err
		}
		storeSWREntry(ctx, rdb, key, value, opts)
		return value, nil
	}

	if err != nil {
		var zero T
		return zero, err
	}

	var entry CacheEntry[T]
	json.Unmarshal(data, &entry)

	if now.Before(time.UnixMilli(entry.ExpiresAt)) {
		// Fresh
		return entry.Value, nil
	}

	if now.Before(time.UnixMilli(entry.HardExpiresAt)) {
		// Soft expired — serve stale + background refresh
		refreshKey := fmt.Sprintf("swr:%s", key)
		acquired, _ := rdb.SetNX(ctx, refreshKey, "1", 30*time.Second).Result()
		if acquired {
			go func() {
				ctxBg := context.Background()
				value, err := fetcher()
				if err == nil {
					storeSWREntry(ctxBg, rdb, key, value, opts)
				}
			}()
		}
		return entry.Value, nil
	}

	// Hard expired
	value, err := fetcher()
	if err != nil {
		var zero T
		return zero, err
	}
	storeSWREntry(ctx, rdb, key, value, opts)
	return value, nil
}

func storeSWREntry[T any](
	ctx context.Context,
	rdb *redis.Client,
	key string,
	value T,
	opts Options,
) {
	now := time.Now()
	entry := CacheEntry[T]{
		Value:         value,
		StoredAt:      now.UnixMilli(),
		ExpiresAt:     now.Add(opts.SoftTTL).UnixMilli(),
		HardExpiresAt: now.Add(opts.HardTTL).UnixMilli(),
	}
	data, _ := json.Marshal(entry)
	rdb.Set(ctx, key, data, opts.HardTTL)
}

// ─── Utility ─────────────────────────────────────────────────────────────────

func jitterTTL(baseTTLSec int, jitterPercent float64) int {
	jitter := float64(baseTTLSec) * jitterPercent
	offset := (rand.Float64()*2 - 1) * jitter
	return int(float64(baseTTLSec) + offset)
}
```

---

## 5. Docker Compose — Redis + App

```yaml
# docker-compose.stampede.yml
version: "3.8"
services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-stampede
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save ""
      --appendonly no
      --loglevel warning
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile.stampede
    container_name: stampede-app
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    ports:
      - "8080:8080"
```

```docker
# Dockerfile.stampede
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install ioredis
COPY . .
CMD ["npx", "ts-node", "stampede-simulator.ts"]
```

---

## 6. Production Checklist

### Pre-deployment Checklist

```
□ Backend p95 latency measured (critical for lock TTL sizing)
□ Lock TTL = backend_p95 × 4 (minimum)
□ SWR: soft_ttl = 10-30% of hard_ttl
□ SWR: hard_ttl = backend_p99 × 2 (minimum)
□ Probabilistic β tuned: start at 0.3, adjust based on load test
□ Jitter: minimum ±10%, recommended ±20% for hot keys
□ Monitoring: stale serve rate metric configured
□ Monitoring: backend request rate per cache key
□ Alert: stale_rate > 5% sustained > 2 minutes
□ Alert: backend p95 > lock_ttl × 0.8
□ Lock release: Lua script verified (atomic check-and-delete)
□ Distributed coalescing: TTL > backend_p95 × 2
```

### Stampede-specific Metrics

```
□ Metric: stampede_lock_acquired_total (counter)
□ Metric: stampede_lock_contention_total (counter)
□ Metric: stampede_stale_serve_total (counter)
□ Metric: stampede_backend_requests_total (counter)
□ Metric: stampede_probabilistic_early_refresh_total (counter)
□ Dashboard: latency p50/p95/p99 by strategy
□ Dashboard: backend request rate heatmap
□ Dashboard: stale serve rate over time
□ Dashboard: lock contention rate
```

### Post-incident Checklist (if stampede detected)

```
□ Identify which cache key caused stampede
□ Check: TTL expiry synchronized? (check key creation timestamps)
□ Check: backend p95 latency spike? (stampede or slow backend?)
□ Check: eviction policy triggered? (maxmemory pressure?)
□ Fix: add jitter to TTL distribution
□ Fix: evaluate SWR for this key (acceptability of staleness)
□ Fix: increase lock TTL if too short
□ Fix: switch to coalescing if mutex overhead too high
□ Review: lock contention rate after fix
□ Review: stale serve rate within SLA
```

---

## 7. Links & References

- [RFC 5861: Stale-While-Revalidate](https://datatracker.ietf.org/doc/html/rfc5861) — HTTP Cache-Control extension, origin of the SWR pattern
- [Fritchie — Handoff-Locked Transactions (2010)](https://arxiv.org/abs/1011.1519) — Academic paper on using Redis SETNX for distributed coordination; early reference for request coalescing
- [Cloudflare Engineering Blog — Cache-Tag Hashing](https://blog.cloudflare.com/) — Probabilistic early expiration at CDN scale
- [Netflix Tech Blog — Hystrix Request Collapsing](https://netflixtechblog.com/) — Request coalescing and collapsing patterns
- [Discord Engineering Blog — Redis Migration](https://discord.com/engineering) — Real-world cache stampede case study
- [Shopify Engineering Blog — Caching at Shopify](https://shopify.engineering/) — SWR adoption for e-commerce
- [Redis SET NX PX](https://redis.io/commands/set/) — SET command with NX and PX options
- [Redis Lua Scripting](https://redis.io/docs/interactivelua/) — Atomic lock release with Lua
- [Go-redis Distributed Locks](https://redis.uptrace.dev/guide/distributed-locks.html) — go-redis lock patterns
- [ioredis Distributed Locks](https://github.com/redis/ioredis#distributed-locks) — ioredis lock patterns
