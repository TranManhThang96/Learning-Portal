# Day 14: Hot Key & Big Key Problems — Reference Document

---

## 1. Cheat Sheet Commands

### 1.1. Hot Key Detection

```bash
# Requires: maxmemory-policy = allkeys-lfu OR volatile-lfu
redis-cli --hotkeys

# Sample output:
# -----------
# Hot keys in Redis with LFU eviction policy
# The following hot keys are monitored (top 5, 0 sampled 100 times)
# PSS will be displayed along with the hot key (if available)
#
# 1. counter:flash_sale    hits:45123055  freq:255.00  size:51200  encoding:hash
# 2. session:global        hits:12000332  freq:254.00  size:50000  encoding:hash
```

```bash
# Check LFU frequency of a specific key (requires LFU policy)
redis-cli OBJECT FREQ hot:counter
# Output: 15234 (access count since LFU initialization)
```

```bash
# Check current eviction policy
redis-cli CONFIG GET maxmemory-policy
# Output: 1) "maxmemory-policy" 2) "allkeys-lfu"
```

### 1.2. Big Key Detection

```bash
# Sample-based scan (fast, non-blocking, approximate)
redis-cli --bigkeys

# Sample output:
# -------- summary -------
# Sampled 123456 keys in the keyspace!
# Hot key biggest found  : type=string, size=10485760, so far=1234
# Hot key biggest found  : type=hash, size=100000, so far=1234
# Hot key biggest found  : type=list, size=5000000, so far=2345
# Hot key biggest found  : type=zset, size=200000, so far=3456
#
# Big key biggest found  : type=string, size=10485760 bytes, key=blob:data:2024
# Big key biggest found  : type=hash, size=100000 fields, key=user:profiles:all
# Big key biggest found  : type=list, size=5000000 elements, key=events:daily
```

```bash
# Accurate memory-based scan (slower, more precise)
redis-cli --memkeys

# Sample output:
# -------- summary -------
# 1. key=blob:data:2024        type=string   memory=10485760 bytes
# 2. key=user:profiles:all    type=hash      memory=2048576 bytes
# 3. key=events:daily         type=list      memory=5120000 bytes
```

```bash
# Memory usage of specific key
redis-cli MEMORY USAGE product:catalog
# Output: (integer) 5242880  (5MB)

# Object encoding info
redis-cli OBJECT ENCODING product:catalog
# Output: "ziplist" / "hashtable" / "quicklist" / "skiplist"
```

```bash
# DEBUG OBJECT (verbose info)
redis-cli DEBUG OBJECT KEY product:catalog
# Output: Value at:0x7f8a3c000000 refcount:1, encoding:hash, serializedlength:5242880, lru:12345678, lru_seconds_idle:3600
```

```bash
# Safe key scanning (non-blocking, production-safe)
redis-cli --scan --pattern '*:catalog:*' | head -100 | xargs -I{} redis-cli MEMORY USAGE {}

# HSCAN for big hash fields
redis-cli HSCAN product:catalog 0 COUNT 1000
# Returns: cursor + array of field/value pairs
```

### 1.3. DEL vs UNLINK

```bash
# UNLINK - async delete (Redis 4.0+)
redis-cli UNLINK leaderboard:weekly

# DEL - synchronous delete (blocking)
redis-cli DEL leaderboard:weekly

# GETDEL - atomic get + delete (Redis 6.2+)
redis-cli GETDEL counter:session:abc123
# Returns: old value AND deletes atomically
```

### 1.4. Key Rename + TTL (Non-blocking Reset)

```bash
# Safe reset pattern (non-blocking)
redis-cli RENAME leaderboard:weekly "leaderboard:weekly:backup:$(date +%s)"
redis-cli EXPIRE leaderboard:weekly:backup:1234567890 86400  # 1 day TTL

# Alternative: RENAME to garbage collection bucket
redis-cli RENAME leaderboard:weekly "gc:leaderboard:$(redis-cli TIME | awk '{print $1}')"
```

### 1.5. Slowlog for Big Key Impact

```bash
# View slow commands (look for DEL, LRANGE, HGETALL on big keys)
redis-cli SLOWLOG GET 20
# Returns: [command, args, duration_ms, timestamp]

# Enable slowlog for commands > 1ms
redis-cli CONFIG SET slowlog-log-slower-than 1000
redis-cli CONFIG SET slowlog-max-len 1000
```

---

## 2. Ngưỡng Cảnh Báo

### 2.1. Big Key Thresholds

| Type | Warning | Critical | Command gây blocking |
|---|---|---|---|
| String | >10KB | >100KB | GET (nếu value quá lớn network) |
| Hash | >1,000 fields | >10,000 fields | HGETALL, HDEL, HMSET |
| List | >5,000 elements | >50,000 elements | LRANGE 0 -1, DEL, LTRIM |
| Set | >5,000 members | >50,000 members | SMEMBERS, SUNION, SINTER |
| Sorted Set | >5,000 elements | >50,000 elements | ZRANGE 0 -1, DEL, ZREMRANGEBYRANK |
| Stream | >5,000 entries | >50,000 entries | XREAD BLOCK, XGROUP CREATE |

### 2.2. Hot Key Thresholds

| Metric | Warning | Critical |
|---|---|---|
| Ops/sec trên 1 key | >10% total ops/sec | >30% total ops/sec |
| Network bandwidth/key | >100Mbps | >500Mbps |
| Access frequency (LFU) | freq > 128 | freq > 200 |

### 2.3. Replication Impact Thresholds

| Metric | Warning | Critical |
|---|---|---|
| Replication lag | >5 seconds | >30 seconds |
| Replication backlog | >50% used | overflow |
| Full sync size | >500MB | >1GB |

---

## 3. Config Templates

### 3.1. Enable LFU for Hot Key Detection

```txt
# /etc/redis/redis.conf

# Enable LFU eviction for hot key monitoring
maxmemory-policy allkeys-lfu

# LFU configuration (optional tuning)
lfu-log-factor 10       # Higher = slower freq decay (default 10)
lfu-decay-time 1        # Minutes to decrement LFU counter (default 1)

# Lazyfree for async delete
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
lazyfree-lazy-user-del yes
```

### 3.2. Production Redis Config for Big Key Safety

```txt
# Disable dangerous commands on production
rename-command KEYS "KEYS_DISABLED_12345"
rename-command FLUSHDB "FLUSHDB_DISABLED_12345"
rename-command FLUSHALL "FLUSHALL_DISABLED_12345"

# Slowlog threshold
slowlog-log-slower-than 1000   # Log commands > 1ms
slowlog-max-len 1000

# Active defragmentation (help with big key fragmentation)
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10
active-defrag-threshold-upper 100
active-defrag-max-scan-fields 1000
```

### 3.3. Docker Compose for Hot/Big Key Lab

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-hotkey-lab
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lfu
      --lazyfree-lazy-eviction yes
      --lazyfree-lazy-expire yes
      --lazyfree-lazy-server-del yes
      --slowlog-log-slower-than 1000
      --slowlog-max-len 100
      --activedefrag yes
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis-replica:
    image: redis:7.2-alpine
    container_name: redis-hotkey-replica
    ports:
      - "6380:6379"
    command: >
      redis-server
      --replicaof redis 6379
      --maxmemory 256mb
      --lazyfree-lazy-server-del yes
    depends_on:
      redis:
        condition: service_healthy

  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: redis-commander
    environment:
      - REDIS_HOSTS=local:redis:6379
    ports:
      - "8081:8081"
    depends_on:
      - redis

volumes:
  redis-data:
```

---

## 4. Code Snippets

### 4.1. TypeScript: Scan and Classify Big Keys

```typescript
// big-key-scanner.ts
// Production-safe big key scanner using SCAN
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });
const BIG_KEY_THRESHOLDS = {
  string: 10 * 1024,           // 10KB
  list: 5_000,
  hash: 1_000,
  set: 5_000,
  zset: 5_000,
};

interface BigKeyReport {
  key: string;
  type: string;
  size: number;
  encoding: string;
  memoryBytes: number;
  severity: 'warning' | 'critical';
}

async function getKeyMeta(key: string): Promise<{
  type: string;
  encoding: string;
  memoryBytes: number;
  size: number;
} | null> {
  try {
    const [type, encoding, memoryBytes] = await Promise.all([
      redis.type(key),
      redis.object('ENCODING', key),
      redis.memory('USAGE', key).catch(() => 0),
    ]);

    let size = 0;
    switch (type) {
      case 'string':
        size = memoryBytes;
        break;
      case 'list':
        size = await redis.llen(key);
        break;
      case 'hash':
        size = await redis.hlen(key);
        break;
      case 'set':
        size = await redis.scard(key);
        break;
      case 'zset':
        size = await redis.zcard(key);
        break;
      default:
        size = memoryBytes;
    }

    return { type, encoding: encoding ?? 'unknown', memoryBytes, size };
  } catch {
    return null; // Key expired/deleted during scan
  }
}

async function scanAndClassifyBigKeys(
  pattern: string = '*',
  thresholdMultiplier: number = 1
): Promise<BigKeyReport[]> {
  const bigKeys: BigKeyReport[] = [];
  let cursor = '0';

  console.log(`Scanning keys matching: ${pattern}`);
  console.log('This is a production-safe operation (non-blocking SCAN)');

  let iterations = 0;
  const MAX_ITERATIONS = 10000;

  do {
    const [nextCursor, batch] = await redis.scan(
      cursor,
      'COUNT', 100,
      'MATCH', pattern
    );
    cursor = nextCursor;
    iterations++;

    const metas = await Promise.all(
      batch.map(key => getKeyMeta(key).then(meta => ({ key, meta })))
    );

    for (const { key, meta } of metas) {
      if (!meta) continue;

      const threshold = BIG_KEY_THRESHOLDS[meta.type as keyof typeof BIG_KEY_THRESHOLDS] ?? meta.memoryBytes;
      const scaledThreshold = threshold * thresholdMultiplier;

      if (meta.size > scaledThreshold || meta.memoryBytes > 1024 * 100) {
        const severity = meta.size > scaledThreshold * 10 ? 'critical' : 'warning';
        bigKeys.push({
          key,
          type: meta.type,
          size: meta.size,
          encoding: meta.encoding,
          memoryBytes: meta.memoryBytes,
          severity,
        });
      }
    }

    if (iterations % 100 === 0) {
      console.log(`Scanned ${iterations * 100} keys, found ${bigKeys.length} big keys...`);
    }

    if (iterations >= MAX_ITERATIONS) {
      console.warn('Max iterations reached, stopping scan');
      break;
    }
  } while (cursor !== '0');

  // Sort by memory usage descending
  bigKeys.sort((a, b) => b.memoryBytes - a.memoryBytes);

  console.log(`\nScan complete. Found ${bigKeys.length} big keys:`);
  for (const k of bigKeys.slice(0, 20)) {
    const sizeStr = k.memoryBytes > 1024 * 1024
      ? `${(k.memoryBytes / (1024 * 1024)).toFixed(1)}MB`
      : `${(k.memoryBytes / 1024).toFixed(1)}KB`;
    console.log(`  [${k.severity.toUpperCase()}] ${k.key}`);
    console.log(`    type=${k.type}, size=${k.size}, memory=${sizeStr}, encoding=${k.encoding}`);
  }

  return bigKeys;
}

// HSCAN for detailed hash field analysis
async function scanHashFields(
  key: string,
  callback: (field: string, value: string) => void
): Promise<void> {
  let cursor = '0';
  do {
    const [nextCursor, fields] = await redis.hscan(key, cursor, 'COUNT', 1000);
    cursor = nextCursor;
    for (let i = 0; i < fields.length; i += 2) {
      callback(fields[i], fields[i + 1]);
    }
  } while (cursor !== '0');
}

// Example usage
async function main() {
  try {
    // Scan all keys
    const reports = await scanAndClassifyBigKeys('*');

    // Check a specific suspected big key
    if (reports.length > 0) {
      const worst = reports[0];
      console.log(`\nWorst offender: ${worst.key}`);
      await scanHashFields(worst.key, (field, value) => {
        if (Number(value) > 1000000) {
          console.log(`  Hot field: ${field} = ${value}`);
        }
      });
    }

    await redis.quit();
  } catch (err) {
    console.error('Scanner error:', err);
    await redis.quit();
    process.exit(1);
  }
}

main();
```

### 4.2. TypeScript: Hot Key Detection with Client-Side Metrics

```typescript
// hot-key-metrics.ts
// Client-side per-key access frequency tracking
import Redis from 'ioredis';

interface KeyMetrics {
  hits: number;
  misses: number;
  latencies: number[];  // ns
  lastAccess: number;   // timestamp ms
}

export class HotKeyMonitor {
  private metrics = new Map<string, KeyMetrics>();
  private redis: Redis;
  private sampleRate: number;
  private maxSamples = 1000;

  constructor(redis: Redis, sampleRate = 1.0) {
    this.redis = redis;
    this.sampleRate = sampleRate;
  }

  private getOrCreate(key: string): KeyMetrics {
    if (!this.metrics.has(key)) {
      this.metrics.set(key, { hits: 0, misses: 0, latencies: [], lastAccess: 0 });
    }
    return this.metrics.get(key)!;
  }

  async get(key: string): Promise<string | null> {
    if (Math.random() > this.sampleRate) return this.redis.get(key);

    const start = process.hrtime.bigint();
    const result = await this.redis.get(key);
    const ns = Number(process.hrtime.bigint() - start);

    const m = this.getOrCreate(key);
    m.hits++;
    m.latencies.push(ns);
    m.lastAccess = Date.now();

    if (m.latencies.length > this.maxSamples) {
      m.latencies = m.latencies.slice(-this.maxSamples / 2);
    }

    return result;
  }

  getTopHotKeys(limit = 20): Array<{ key: string; hits: number; p99LatencyNs: number }> {
    return Array.from(this.metrics.entries())
      .map(([key, m]) => ({
        key,
        hits: m.hits,
        p99LatencyNs: this.percentile(m.latencies, 99),
      }))
      .sort((a, b) => b.hits - a.hits)
      .slice(0, limit);
  }

  private percentile(arr: number[], p: number): number {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, idx)];
  }
}
```

### 4.3. TypeScript: Hot Key Splitter (Key Sharding)

```typescript
// hot-key-splitter.ts
// Split a hot leaderboard into N Sorted Set shards.
import Redis from 'ioredis';

export interface ShardedLeaderboard {
  add(key: string, member: string, score: number, numShards?: number): Promise<number>;
  remove(key: string, member: string, numShards?: number): Promise<number>;
  getTopK(key: string, k: number, numShards?: number): Promise<Array<{ member: string; score: number }>>;
  getMemberCount(key: string, numShards?: number): Promise<number>;
  reset(key: string, numShards?: number): Promise<void>;
}

function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

export function createShardedLeaderboard(redis: Redis): ShardedLeaderboard {
  const NUM_SHARDS_DEFAULT = 100;

  function shardKey(key: string, shardId: number, numShards: number): string {
    return `${key}:shard_${String(shardId).padStart(3, '0')}_${numShards}`;
  }

  function pickShard(member: string, numShards: number): number {
    return hashString(member) % numShards;
  }

  async function getAllShardKeys(key: string, numShards: number): Promise<string[]> {
    return Array.from({ length: numShards }, (_, i) => shardKey(key, i, numShards));
  }

  return {
    async add(key: string, member: string, score: number, numShards = NUM_SHARDS_DEFAULT): Promise<number> {
      const shardId = pickShard(member, numShards);
      const shardK = shardKey(key, shardId, numShards);
      return redis.zadd(shardK, score, member);
    },

    async getMemberCount(key: string, numShards = NUM_SHARDS_DEFAULT): Promise<number> {
      const shardKeys = await getAllShardKeys(key, numShards);
      const pipeline = redis.pipeline();
      for (const shardK of shardKeys) {
        pipeline.zcard(shardK);
      }
      const results = await pipeline.exec();
      if (!results) return 0;
      return results.reduce((sum, [err, count]) => sum + (err ? 0 : Number(count || 0)), 0);
    },

    async remove(key: string, member: string, numShards = NUM_SHARDS_DEFAULT): Promise<number> {
      const shardId = pickShard(member, numShards);
      const shardK = shardKey(key, shardId, numShards);
      return redis.zrem(shardK, member);
    },

    async getTopK(key: string, k: number, numShards = NUM_SHARDS_DEFAULT): Promise<Array<{ member: string; score: number }>> {
      const shardKeys = await getAllShardKeys(key, numShards);

      // Pipeline: get top k from each shard
      const pipeline = redis.pipeline();
      for (const shardK of shardKeys) {
        pipeline.zrevrange(shardK, 0, k - 1, 'WITHSCORES');
      }
      const results = await pipeline.exec();

      if (!results) return [];

      // Merge and resort
      const all: Array<{ member: string; score: number }> = [];
      for (const [err, pairs] of results) {
        if (err || !pairs) continue;
        const arr = pairs as string[];
        for (let i = 0; i < arr.length; i += 2) {
          all.push({ member: arr[i], score: Number(arr[i + 1]) });
        }
      }

      // Sort and dedupe (same member might appear in multiple shards)
      const seen = new Set<string>();
      return all
        .filter(e => {
          if (seen.has(e.member)) return false;
          seen.add(e.member);
          return true;
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, k);
    },

    async reset(key: string, numShards = NUM_SHARDS_DEFAULT): Promise<void> {
      const shardKeys = await getAllShardKeys(key, numShards);
      await redis.unlink(...shardKeys);
    },
  };
}

// Usage example
async function demo() {
  const redis = new Redis({ host: 'localhost', port: 6379 });
  const leaderboard = createShardedLeaderboard(redis);

  // Simulate 100K increments spread across shards
  console.log('Adding 100K members to sharded leaderboard (100 shards)...');
  const start = Date.now();

  await Promise.all(
    Array.from({ length: 100_000 }, (_, i) =>
      leaderboard.add('leaderboard:daily', `user_${i}`, Math.random() * 1000)
    )
  );

  console.log(`Added in ${Date.now() - start}ms`);
  console.log('Member count:', await leaderboard.getMemberCount('leaderboard:daily'));

  // Get top 10
  const top10 = await leaderboard.getTopK('leaderboard:daily', 10);
  console.log('Top 10:', top10);

  // Reset (UNLINK - non-blocking)
  await leaderboard.reset('leaderboard:daily');
  console.log('Reset done (async UNLINK)');

  await redis.quit();
}

demo().catch(console.error);
```

### 4.4. Go: Hot Key Splitter

```go
// hot_key_splitter.go
package main

import (
	"context"
	"fmt"
	"hash/fnv"
	"sort"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

type ShardedCounter struct {
	client     *redis.Client
	numShards  int
	shardMu    []sync.RWMutex
}

func NewShardedCounter(client *redis.Client, numShards int) *ShardedCounter {
	return &ShardedCounter{
		client:    client,
		numShards: numShards,
		shardMu:   make([]sync.RWMutex, numShards),
	}
}

func (s *ShardedCounter) pickShard(member string) int {
	h := fnv.New32a()
	h.Write([]byte(member))
	return int(h.Sum32()) % s.numShards
}

func (s *ShardedCounter) shardKey(key string, shardID int) string {
	return fmt.Sprintf("%s:shard_%03d_%d", key, shardID, s.numShards)
}

// INCR a counter in a specific shard
func (s *ShardedCounter) Incr(ctx context.Context, key, member string, delta float64) (float64, error) {
	shardID := s.pickShard(member)
	shardK := s.shardKey(key, shardID)

	result, err := s.client.ZIncrBy(ctx, shardK, delta, member).Result()
	if err != nil {
		return 0, err
	}
	return result, nil
}

// Get total score of a member across all shards
func (s *ShardedCounter) GetTotal(ctx context.Context, key, member string) (float64, error) {
	var total float64
	for i := 0; i < s.numShards; i++ {
		shardK := s.shardKey(key, i)
		score, err := s.client.ZScore(ctx, shardK, member).Result()
		if err == redis.Nil {
			continue
		}
		if err != nil {
			return 0, err
		}
		total += score
	}
	return total, nil
}

// GetTopK from sharded sorted set using pipeline
func (s *ShardedCounter) GetTopK(ctx context.Context, key string, k int) ([]redis.Z, error) {
	pipe := s.client.Pipeline()

	cmds := make([]*redis.StringSliceCmd, s.numShards)
	for i := 0; i < s.numShards; i++ {
		cmds[i] = pipe.ZRevRangeWithScores(ctx, s.shardKey(key, i), 0, int64(k-1))
	}

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return nil, err
	}

	// Merge results
	all := make([]redis.Z, 0, s.numShards*k)
	seen := make(map[string]bool)

	for _, cmd := range cmds {
		members, err := cmd.Result()
		if err != nil {
			continue
		}
		for _, m := range members {
			if !seen[m.Member.(string)] {
				seen[m.Member.(string)] = true
				all = append(all, m)
			}
		}
	}

	sort.Slice(all, func(i, j int) bool {
		return all[i].Score > all[j].Score
	})

	if len(all) > k {
		all = all[:k]
	}
	return all, nil
}

// Reset using UNLINK (async, non-blocking)
func (s *ShardedCounter) Reset(ctx context.Context, key string) error {
	keys := make([]string, s.numShards)
	for i := 0; i < s.numShards; i++ {
		keys[i] = s.shardKey(key, i)
	}
	return s.client.Unlink(ctx, keys...).Err()
}

func main() {
	ctx := context.Background()
	client := redis.NewClient(&redis.Options{Addr: "localhost:6379"})

	counter := NewShardedCounter(client, 100)

	// Benchmark: 10K increments
	start := time.Now()
	var wg sync.WaitGroup

	for i := 0; i < 10_000; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			counter.Incr(ctx, "flash_sale", fmt.Sprintf("user_%d", id), 1)
		}(i)
	}
	wg.Wait()
	fmt.Printf("10K INCR: %v\n", time.Since(start))

	// Get top 10
	top, _ := counter.GetTopK(ctx, "flash_sale", 10)
	for i, z := range top {
		fmt.Printf("  #%d: %s = %.0f\n", i+1, z.Member, z.Score)
	}

	counter.Reset(ctx, "flash_sale")
}
```

---

## 5. Links & Resources

### 5.1. Official Redis Documentation

- Redis Keyspace Notifications: https://redis.io/docs/manual/keyspace-notifications/
- Redis Latency Problems: https://redis.io/docs/reference/latency/
- Redis Memory Optimization: https://redis.io/docs/management/optimization/memory-optimization/
- Redis Admin Guide: https://redis.io/docs/management/admin/

### 5.2. Redis Blog & Engineering

- antirez blog (Salvatore Sanfilippo): https://antirez.com/latest/ post
  - "Redis latency problems troubleshooting" — explains DEL blocking, big key internals
- Alibaba Tair Engineering Blog:
  - "Hot Key Detection and Auto-Sharding in Tair" — production hot key handling at Alibaba scale
- Redis Labs Blog:
  - "Debug Redis Memory Usage" — MEMORY USAGE deep dive
  - "Big Key and Hot Key Detection" — practical detection strategies

### 5.3. Tools

- `redis-cli --bigkeys` source: Redis source code `redis-cli.c` bigkeysCommand()
- `redis-cli --hotkeys` source: Redis source code `redis-cli.c` hotkeysCommand()
- Memtier Benchmark: https://github.com/RedisLabs/memtier_benchmark
- Redis Live (monitoring): https://github.com/pkulikov/redis-live

### 5.4. Academic / Production Reports

- "An Architecture for a High-Performance Web Cache" — early Redis design rationale
- "Redis in the Twitter Timeline" — social media Redis use case (available via Redis blog)
- "Amazon ElastiCache Best Practices" — hot key patterns in cloud Redis
