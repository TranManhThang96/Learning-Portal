# Day 1: Redis Architecture & Production Use Cases - Reference Document

---

## 1. Redis CLI Cheat Sheet

### Kết nối và kiểm tra cơ bản

```bash
# Kết nối tới Redis
redis-cli

# Kết nối với host và port cụ thể
redis-cli -h 127.0.0.1 -p 6379

# Ping để kiểm tra kết nối
redis-cli PING
# Expected: PONG

# Kiểm tra server info
redis-cli INFO server
redis-cli INFO memory
redis-cli INFO stats
redis-cli INFO replication

# Lấy tất cả config
redis-cli CONFIG GET *
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy
redis-cli CONFIG GET timeout
redis-cli CONFIG GET tcp-keepalive

# Thay đổi config runtime (không lưu lại sau restart)
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Monitoring và Debug

```bash
# Monitor tất cả commands real-time (chỉ dùng khi debug)
redis-cli MONITOR

# Kiểm tra slow commands
redis-cli SLOWLOG GET 10
redis-cli SLOWLOG LEN
redis-cli SLOWLOG RESET

# Kiểm tra command statistics
redis-cli INFO commandstats

# Chẩn đoán memory
redis-cli MEMORY DOCTOR

# Đo memory usage của một key
redis-cli MEMORY USAGE user:123

# Đo object encoding
redis-cli OBJECT ENCODING user:123

# Latency check
redis-cli --latency
redis-cli --latency-history
redis-cli --latency-dist

# Big keys (không block, dùng SCAN)
redis-cli --bigkeys
redis-cli --hotkeys
redis-cli --memkeys

# Chẩn đoán fragmentation
redis-cli INFO memory | grep -E "mem_fragmentation_ratio|used_memory_human|maxmemory_human"
```

### Cấu trúc dữ liệu cơ bản

```bash
# String
SET key value
SET key value EX 3600        # với TTL 3600 giây
SET key value NX             # chỉ set nếu key chưa tồn tại
GET key
DEL key
EXISTS key

# Hash
HSET user:123 name "Alice" email "alice@example.com"
HGET user:123 name
HGETALL user:123
HINCRBY user:123 login_count 1
HDEL user:123 email

# List
LPUSH queue:jobs '{"job":"email"}'
RPUSH queue:jobs '{"job":"sms"}'
LPOP queue:jobs
BRPOP queue:jobs 0            # blocking pop, timeout 0 = vô cực

# Set
SADD tags:article:1 redis golang
SMEMBERS tags:article:1
SISMEMBER tags:article:1 redis
SCARD tags:article:1

# Sorted Set
ZADD leaderboard 100 "alice"
ZADD leaderboard 200 "bob"
ZREVRANGE leaderboard 0 9 WITHSCORES
ZRANK leaderboard alice

# Counter
INCR pageviews:/home
INCRBY pageviews:/home 100
DECR pageviews:/home
```

---

## 2. Redis vs Memcached - Bảng so sánh chi tiết

| Tiêu chí | Redis 7.x | Memcached |
|---|---|---|
| **Version** | 7.2+ (current) | 1.6+ |
| **Protocol** | RESP3 (binary, compact) | ASCII + binary |
| **String encoding** | SDS, tự động encode (int, embstr, raw) | Raw bytes |
| **Max value size** | 512MB | 1MB |
| **Max key size** | 512MB | 250 bytes |
| **Data structures** | 10+ types (String, Hash, List, Set, ZSet, Bitmap, HLL, Geo, Stream, Module) | Chỉ String |
| **Atomic ops** | INCR, HINCRBY, SETNX, Lua, MULTI/EXEC | inc, dec |
| **Persistence** | RDB + AOF (tùy chọn) | Không có |
| **Replication** | Master-replica, async, PSYNC2 | Replica (doc-only) |
| **High Availability** | Sentinel, Cluster | Không có native HA |
| **Eviction policies** | 8 (noeviction, allkeys-lru, volatile-lru, allkeys-lfu, volatile-lfu, allkeys-random, volatile-random, volatile-ttl) | 4 (LRU, LFU, FIFO, TTL) |
| **Memory allocator** | jemalloc (default), libc, tcmalloc | slab allocator |
| **Thread model** | Single-threaded + I/O thread (Redis 6+) | Multi-threaded (slab reassignment) |
| **Pub/Sub** | Có (Channel, Pattern) | Có |
| **Lua scripting** | Có (EVAL, EVALSHA) | Không |
| **Transactions** | MULTI/EXEC + WATCH | Không |
| **Streams** | Có (Redis 5+) | Không |
| **Memory overhead/key** | ~49 bytes (dictEntry) + overhead | ~62 bytes (item + chunk overhead) |
| **Cache invalidation** | Via command, Lua, key expiration | Flush khi expire |
| **Hot reload config** | CONFIG SET (runtime) | Không |

**Lựa chọn:** Redis khi cần durability, HA, complex data structures. Memcached khi chỉ cần simple string cache, muốn multi-threaded performance, hoặc dvetail với Varnish/Nginx caching layer.

---

## 3. Docker Compose Template

### Redis 7.x Standalone (Production Starter)

```yaml
version: "3.8"

services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-primary
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --maxmemory-samples 10
      --timeout 300
      --tcp-keepalive 60
      --loglevel notice
      --appendonly yes
      --appendfsync everysec
      --auto-aof-rewrite-percentage 100
      --auto-aof-rewrite-min-size 64mb
      --save 900 1
      --save 300 10
      --save 60 10000
      --rdbchecksum yes
      --replica-read-only yes
      --maxclients 10000
      --protected-mode yes
    volumes:
      - redis-data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          memory: 768M
        reservations:
          memory: 512M
    restart: unless-stopped
    ulimits:
      nofile:
        soft: 65536
        hard: 65536

volumes:
  redis-data:
    driver: local

networks:
  default:
    name: redis-network
```

### Redis 7.x Standalone - Development (Không Persistence)

```yaml
version: "3.8"

services:
  redis-dev:
    image: redis:7.2-alpine
    container_name: redis-dev
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --save "" --appendonly no
    # Debug: tất cả data mất khi restart
    # Chỉ dùng cho local development
    restart: "no"
```

---

## 4. Redis Config Snippet - Production Starter

```txt
# ============ MEMORY ============
maxmemory 2gb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# ============ NETWORK ============
timeout 300
tcp-keepalive 60
tcp-backlog 511
maxclients 10000
protected-mode yes

# ============ PERSISTENCE ============
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-load-truncated yes
aof-use-rdb-preamble yes

# RDB snapshots (backup)
save 900 1
save 300 10
save 60 10000
rdbchecksum yes
rdbcompression yes

# ============ REPLICATION ============
replica-read-only yes
repl-diskless-sync no
repl-diskless-sync-delay 5
repl-timeout 60
repl-backlog-size 10mb
repl-backlog-ttl 3600
min-slaves-to-write 1
min-slaves-max-lag 10

# ============ SECURITY ============
# requirepass yourStrongPasswordHere
# rename-command FLUSHDB ""
# rename-command FLUSHALL ""
# rename-command KEYS ""
# rename-command DEBUG ""

# ============ LOGGING ============
loglevel notice
logfile ""

# ============ MEMORY MANAGEMENT ============
active-defrag.enabled yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10
active-defrag-threshold-upper 100
active-defrag-cycle-min 25
active-defrag-cycle-max 75

# ============ LAZY FREE ============
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
replica-lazy-flush yes

# ============ CLIENTS ============
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60
```

---

## 5. TypeScript Code Snippet - Redis Client với ioredis

### 5.1 Redis Client Wrapper với Connection Pooling, Retry, Timeout

```typescript
// src/redis/client.ts
import Redis from "ioredis";

const REDIS_HOST = process.env.REDIS_HOST ?? "127.0.0.1";
const REDIS_PORT = parseInt(process.env.REDIS_PORT ?? "6379", 10);
const REDIS_PASSWORD = process.env.REDIS_PASSWORD;
const MAX_RETRIES = 3;
const CONNECT_TIMEOUT_MS = 5000;
const COMMAND_TIMEOUT_MS = 3000;

class RedisClient {
  private client: Redis;
  private isReady = false;

  constructor() {
    this.client = new Redis({
      host: REDIS_HOST,
      port: REDIS_PORT,
      password: REDIS_PASSWORD,
      db: 0,
      retryStrategy: (times) => {
        if (times > MAX_RETRIES) {
          console.error(`[Redis] Max retries (${MAX_RETRIES}) reached. Giving up.`);
          return null; // stop retrying
        }
        const delay = Math.min(times * 200, 2000);
        console.warn(`[Redis] Retry #${times} in ${delay}ms...`);
        return delay;
      },
      connectTimeout: CONNECT_TIMEOUT_MS,
      commandTimeout: COMMAND_TIMEOUT_MS,
      maxRetriesPerRequest: 3,
      enableReadyCheck: true,
      lazyConnect: false,
      keepAlive: 30000,
      enableOfflineQueue: true,
    });

    this.client.on("connect", () => console.log("[Redis] Connecting..."));
    this.client.on("ready", () => {
      this.isReady = true;
      console.log("[Redis] Ready.");
    });
    this.client.on("error", (err) => {
      console.error(`[Redis] Error: ${err.message}`);
      this.isReady = false;
    });
    this.client.on("close", () => {
      console.warn("[Redis] Connection closed.");
      this.isReady = false;
    });
    this.client.on("reconnecting", () => {
      console.warn("[Redis] Reconnecting...");
    });
  }

  getClient(): Redis {
    return this.client;
  }

  isConnected(): boolean {
    return this.isReady && this.client.status === "ready";
  }

  // ---- Convenience methods ----

  async ping(): Promise<string> {
    return this.client.ping();
  }

  async get(key: string): Promise<string | null> {
    return this.client.get(key);
  }

  async set(key: string, value: string, ttlSeconds?: number): Promise<"OK"> {
    if (ttlSeconds !== undefined) {
      return this.client.set(key, value, "EX", ttlSeconds);
    }
    return this.client.set(key, value);
  }

  async setNX(key: string, value: string, ttlSeconds: number): Promise<boolean> {
    const result = await this.client.set(key, value, "EX", ttlSeconds, "NX");
    return result === "OK";
  }

  async incr(key: string): Promise<number> {
    return this.client.incr(key);
  }

  async hset(key: string, field: string, value: string): Promise<number> {
    return this.client.hset(key, field, value);
  }

  async hget(key: string, field: string): Promise<string | null> {
    return this.client.hget(key, field);
  }

  async hgetall(key: string): Promise<Record<string, string>> {
    return this.client.hgetall(key) as Promise<Record<string, string>>;
  }

  // ---- Pipeline ----
  pipeline(): ReturnType<Redis["pipeline"]> {
    return this.client.pipeline();
  }

  async close(): Promise<void> {
    await this.client.quit();
    this.isReady = false;
    console.log("[Redis] Disconnected.");
  }
}

// Singleton
const redisClient = new RedisClient();
export default redisClient;
export { Redis };
```

### 5.2 RTT Measurement Utility

```typescript
// src/redis/benchmark.ts
import redisClient from "./client";

async function measureRTT(): Promise<void> {
  const client = redisClient.getClient();
  const iterations = 1000;

  // Warm up
  await client.set("warmup", "1");
  await client.get("warmup");
  await client.del("warmup");

  // Measure GET RTT
  const getTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    await client.get(`bench:get:${i}`);
    const end = performance.now();
    getTimes.push(end - start);
  }

  // Measure SET RTT
  const setTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    await client.set(`bench:set:${i}`, "value");
    const end = performance.now();
    setTimes.push(end - start);
  }

  // Measure Pipeline (10 commands)
  const pipelineTimes: number[] = [];
  for (let i = 0; i < iterations; i++) {
    const start = performance.now();
    const pipe = client.pipeline();
    for (let j = 0; j < 10; j++) {
      pipe.get(`bench:pipe:${j}`);
    }
    await pipe.exec();
    const end = performance.now();
    pipelineTimes.push(end - start);
  }

  function percentile(arr: number[], p: number): number {
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[idx];
  }

  function avg(arr: number[]): number {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }

  console.log("=== RTT Benchmark Results ===");
  console.log(`GET  - avg: ${avg(getTimes).toFixed(3)}ms, p50: ${percentile(getTimes, 50).toFixed(3)}ms, p95: ${percentile(getTimes, 95).toFixed(3)}ms, p99: ${percentile(getTimes, 99).toFixed(3)}ms`);
  console.log(`SET  - avg: ${avg(setTimes).toFixed(3)}ms, p50: ${percentile(setTimes, 50).toFixed(3)}ms, p95: ${percentile(setTimes, 95).toFixed(3)}ms, p99: ${percentile(setTimes, 99).toFixed(3)}ms`);
  console.log(`Pipe - avg: ${avg(pipelineTimes).toFixed(3)}ms, p50: ${percentile(pipelineTimes, 50).toFixed(3)}ms, p95: ${percentile(pipelineTimes, 95).toFixed(3)}ms, p99: ${percentile(pipelineTimes, 99).toFixed(3)}ms`);
  console.log(`Pipeline (10 ops): throughput = ${(10000 / avg(pipelineTimes)).toFixed(0)} ops/sec`);
}

async function main() {
  await redisClient.ping(); // đợi connection sẵn sàng trước khi benchmark
  await measureRTT();
  await redisClient.close();
}

main().catch(console.error);
```

### 5.3 Cache-Aside Pattern

```typescript
// src/services/productCache.ts
import redisClient from "./client";

interface Product {
  id: string;
  name: string;
  price: number;
}

// Simulated database
const fakeDB: Record<string, Product> = {
  "1": { id: "1", name: "Laptop", price: 1000 },
  "2": { id: "2", name: "Mouse", price: 50 },
};

const CACHE_TTL_SECONDS = 300; // 5 minutes

export async function getProduct(id: string): Promise<Product | null> {
  const cacheKey = `product:${id}`;

  // 1. Check cache first
  const cached = await redisClient.get(cacheKey);
  if (cached !== null) {
    console.log(`[Cache HIT] ${cacheKey}`);
    return JSON.parse(cached) as Product;
  }

  console.log(`[Cache MISS] ${cacheKey}`);

  // 2. Fetch from database
  const product = fakeDB[id] ?? null;
  if (product === null) {
    return null;
  }

  // 3. Store in cache with TTL
  await redisClient.set(cacheKey, JSON.stringify(product), CACHE_TTL_SECONDS);

  return product;
}

export async function invalidateProductCache(id: string): Promise<void> {
  const cacheKey = `product:${id}`;
  await redisClient.getClient().del(cacheKey);
  console.log(`[Cache INVALIDATED] ${cacheKey}`);
}
```

### 5.4 package.json dependencies

```json
{
  "name": "redis-day1-lab",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "start:dev": "ts-node src/redis/client.ts",
    "benchmark": "ts-node src/redis/benchmark.ts"
  },
  "dependencies": {
    "ioredis": "^5.3.2"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  }
}
```

### 5.5 tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

---

## 6. Links

### Official Documentation
- Redis Documentation: https://redis.io/docs/
- Redis CLI Documentation: https://redis.io/docs/manual/cli/
- Redis Configuration: https://redis.io/docs/management/config/
- Redis Persistence: https://redis.io/docs/management/persistence/
- Redis Replication: https://redis.io/docs/management/replication/
- Redis Security: https://redis.io/docs/management/security/

### Redis Internals
- Redis Source Code: https://github.com/redis/redis
- Redis Internals Series (antirez blog): http://oldblog.antirez.com/
- Redis-conf: http://antirez.com/latest/redis-conf/
- How Redis implements data structures: https://redis.io/docs/reference/internals/

### Performance & Benchmarking
- redis-benchmark: https://redis.io/docs/management/optimization/benchmarks/
- redis-cli --latency: https://redis.io/docs/management/optimization/latency/
- memtier_benchmark: https://github.com/RedisLabs/memtier_benchmark
- Latency Fundamentals: https://www.brendangregg.com/blog/2020-01-01/learning-latkency-fundamentals.html

### Books & Papers
- "Redis in Action" by Josiah L. Carlson (Manning, 2013)
- "The Little Redis Book" by Karl Seguin (free): https://github.com/karlseguin/the-little-redis-book
- "Redis: The Definitive Guide" by Jay A. Kreibich (O'Reilly, 2015)

### Blog Posts & Case Studies
- "Why Redis is eating the world" - https://www.doximity.com/articles/why-redis-is-eating-the-world
- Twitter Timeline Architecture: https://www.infoq.com/presentations/Twitter-Timeline-Scalability
- GitHub Redis Session Store: https://github.blog/2023-03-13-how-github-reduced-memory-and-improved-performance-with-redis/
- Stack Overflow Cache Architecture: https://nickcraver.com/blog/2020/02/17/stack-overflow-how-we-do-app-caching/

### Tools
- Redis Docker Image: https://hub.docker.com/_/redis
- RedisInsight (GUI): https://redis.com/redis-enterprise/redis-insight/
- Redis Commits Explorer: https://github.com/redis/redis/commits
- Redis Slack Community: https://redis.com/community

---

## 7. Redis Architecture - Quick Reference Card

```
+------------------------------------------+
|          CLIENT (Any Language)           |
|  ioredis / node-redis / go-redis / etc  |
+--------+-------------------+-------------+
         |  TCP/RESP3         |  TCP/RESP3
         v                    v
+----------------+    +------------------+
| Redis Server   |    | Redis Sentinel   |
| (event loop)   |    | (HA management)  |
| single-thread  |    +------------------+
+----------------+
|  +-----------+ |
|  |aeEventLoop| |  I/O Multiplexing
|  | epoll/    | |  (non-blocking)
|  | kqueue    | |
|  +-----------+ |
|  +-----------+ |
|  | Command   | |  O(1) - SET/GET/INCR
|  | Processor | |  O(log N) - ZADD
|  +-----------+ |  O(N) - KEYS* (avoid!)
|  +-----------+ |
|  | Data      | |  SDS / Listpack /
|  | Structures| |  Quicklist / Skiplist
|  +-----------+ |
+--------+--------+
         |
    +----+----+
    | jemalloc |
    | (memory) |
    +----------+
         |
    +----+----+
    | RDB/AOF  |  Persistence
    +----------+
```

**Event Loop Flow:**
```
socket readable -> read data -> parse command -> execute -> write response -> socket writable
       |                  |             |
   epoll/kqueue      RESP parser    O(1) dict lookup
   (non-blocking)    (fast)        + data structure ops
```
