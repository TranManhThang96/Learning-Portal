# Day 1: Redis Architecture & Production Use Cases - Exercises

**Thời gian:** ~2 giờ
**Công cụ:** redis-cli, Docker Compose, TypeScript + ioredis
**Prerequisites:** Docker Desktop, Node.js 18+, TypeScript

---

## 1. Warm-up Exercises (15-20 phút)

### Mục tiêu
Làm quen với redis-cli, hiểu các command cơ bản, kiểm tra server status.

### 1.1 Kết nối và kiểm tra

```bash
# Kết nối tới Redis (đang chạy trên port 6379)
redis-cli

# Kiểm tra kết nối
PING
# Expected: PONG

# Thoát khỏi redis-cli
QUIT
```

### 1.2 String operations

```bash
# Set một key
SET server:01 '{"name":"api-gateway","region":"us-east"}'
# Expected: OK

# Get key
GET server:01
# Expected: {"name":"api-gateway","region":"us-east"}

# Set với TTL (5 phút)
SET cache:page:home '{"title":"Home"}' EX 300
# Expected: OK

# Kiểm tra TTL
TTL cache:page:home
# Expected: (integer) < 300 (số giây còn lại)

# Check xem key có tồn tại không
EXISTS server:01
# Expected: (integer) 1

# Set nếu key chưa tồn tại (NX)
SETNX lock:process:001 "thang"
# Expected: (integer) 1 (đã set thành công)

# Thử setnx khi key đã tồn tại
SETNX lock:process:001 "an"
# Expected: (integer) 0 (không set vì đã tồn tại)

# Xóa key
DEL lock:process:001
# Expected: (integer) 1
```

### 1.3 Server Info

```bash
# Xem server info
INFO server
# Chú ý: redis_version, os, arch_bits, tcp_port, uptime_in_seconds

# Xem memory info
INFO memory
# Chú ý: used_memory_human, maxmemory_human, maxmemory_policy, mem_fragmentation_ratio

# Xem chỉ số latency
INFO stats
# Chú ý: total_connections_received, total_commands_processed, instantaneous_ops_per_sec

# Xem chỉ số replication (nếu có)
INFO replication
# Expected (nếu không có replica): role:master, connected_slaves:0

# Xem 5 slow commands gần nhất
SLOWLOG GET 5
# Expected: (empty list) hoặc một số entries
```

### 1.4 Config của Redis

```bash
# Lấy giá trị maxmemory hiện tại
CONFIG GET maxmemory
# Expected: 1) "maxmemory" 2) "0" hoặc một số bytes (vd "536870912" = 512MB)

# Lấy giá trị eviction policy
CONFIG GET maxmemory-policy
# Expected: 1) "maxmemory-policy" 2) "noeviction" hoặc "allkeys-lru"

# Lấy giá trị timeout
CONFIG GET timeout
# Expected: 1) "timeout" 2) "300"

# Lấy giá trị tcp-keepalive
CONFIG GET tcp-keepalive
# Expected: 1) "tcp-keepalive" 2) "60"
```

---

## 2. Hands-on Lab (60-70 phút)

### Mục tiêu
Setup Redis với Docker Compose, kết nối từ TypeScript, thực hiện các thao tác cơ bản, đo RTT.

### 2.1 Setup Redis với Docker Compose

**Bước 1:** Tạo file `docker-compose.yml` trong thư mục làm việc

```yaml
version: "3.8"

services:
  redis:
    image: redis:7.2-alpine
    container_name: redis-lab
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --maxmemory-samples 10
      --timeout 300
      --tcp-keepalive 60
      --loglevel notice
      --save ""           # Tắt RDB save (chỉ dùng cho lab)
      --appendonly yes
      --appendfsync everysec
      --protected-mode no
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: "no"         # Để debug, restart thủ công khi cần

volumes:
  redis-data:
```

**Bước 2:** Khởi động Redis

```bash
docker compose up -d redis
# Expected: Container redis-lab được tạo và chạy

# Kiểm tra container đang chạy
docker ps | grep redis-lab

# Kiểm tra health
docker exec redis-lab redis-cli PING
# Expected: PONG

# Xem logs
docker compose logs redis --tail 20
```

**Bước 3:** Xác nhận kết nối từ host machine

```bash
redis-cli PING
# Expected: PONG

redis-cli INFO server | grep redis_version
# Expected: redis_version:7.2.*
```

**Hint:** Nếu redis-cli không kết nối được (ERR TCP connection), kiểm lại port mapping: `docker port redis-lab`

---

### 2.2 TypeScript Project Setup

**Bước 1:** Tạo project

```bash
mkdir -p redis-lab/src/redis
cd redis-lab
npm init -y
npm install ioredis
npm install -D typescript @types/node ts-node
npx tsc --init --target ES2020 --module commonjs --strict --outDir ./dist
```

**Bước 2:** Tạo file `src/redis/client.ts`

Copy nội dung từ document.md, phần 5.1 vào file này.

**Bước 3:** Chạy client để kiểm tra kết nối

```bash
# Thêm vào package.json:
# "scripts": { "dev": "ts-node src/redis/client.ts" }

# Chạy
npm run dev
# Expected: [Redis] Connecting... -> [Redis] Ready.
# Sau 5 giây: [Redis] Disconnected.
```

**Hint:** Nếu gặp lỗi "Connection refused", kiểm lại Docker Compose port mapping. Thử `redis-cli -p 6379 PING` trước.

---

### 2.3 Exercise: Basic Redis Operations

**Yêu cầu:** Viết chương trình TypeScript thực hiện các thao tác sau:

1. SET key `user:session:thang` với value JSON (name, email, role), TTL 3600 giây
2. GET key đó, parse JSON
3. INCR counter `pageviews:/home`
4. HSET user profile `user:profile:thang` với các field: name, email, plan
5. HGETALL user profile
6. INCR pageview counter 100 lần (dùng vòng lặp nhanh)
7. Xóa tất cả keys tạo ở bước trên

**Starter code:**

```typescript
// src/redis/exercise.ts
import redisClient from "./client";

async function exercise(): Promise<void> {
  const client = redisClient.getClient();

  console.log("=== Exercise: Basic Redis Operations ===\n");

  // 1. SET user session (string với TTL)
  const sessionKey = "user:session:thang";
  const sessionData = JSON.stringify({ name: "thang", email: "thang@example.com", role: "admin" });
  const setResult = await client.set(sessionKey, sessionData, "EX", 3600);
  console.log(`1. SET session: ${setResult}`);

  // 2. GET session
  const sessionRaw = await client.get(sessionKey);
  const session = JSON.parse(sessionRaw!);
  console.log(`2. GET session: name=${session.name}, email=${session.email}`);

  // 3. INCR counter
  await client.set("pageviews:/home", "0");
  const newCount = await client.incr("pageviews:/home");
  console.log(`3. INCR pageviews: ${newCount}`);

  // 4. HSET user profile
  const profileKey = "user:profile:thang";
  await client.hset(profileKey, "name", "thang");
  await client.hset(profileKey, "email", "thang@example.com");
  await client.hset(profileKey, "plan", "pro");
  console.log(`4. HSET profile: OK`);

  // 5. HGETALL profile
  const profile = await client.hgetall(profileKey);
  console.log(`5. HGETALL profile: ${JSON.stringify(profile)}`);

  // 6. INCR 100 lần
  await client.set("pageviews:/home", "0");
  for (let i = 0; i < 100; i++) {
    await client.incr("pageviews:/home");
  }
  const finalCount = await client.get("pageviews:/home");
  console.log(`6. INCR 100x: final count = ${finalCount}`);

  // 7. Cleanup
  await client.del(sessionKey);
  await client.del("pageviews:/home");
  await client.del(profileKey);
  console.log(`7. DEL all keys: OK`);

  console.log("\n=== Exercise Complete ===");
}

async function main(): Promise<void> {
  await new Promise((r) => setTimeout(r, 1000)); // wait for connection
  await exercise();
  await redisClient.close();
}

main().catch(console.error);
```

**Expected output:**

```
=== Exercise: Basic Redis Operations ===

1. SET session: OK
2. GET session: name=thang, email=thang@example.com
3. INCR pageviews: 1
4. HSET profile: OK
5. HGETALL profile: {"name":"thang","email":"thang@example.com","plan":"pro"}
6. INCR 100x: final count = 100
7. DEL all keys: OK

=== Exercise Complete ===
```

**Step-by-step hint:**
1. Kiểm tra kết nối: `redis-cli PING`
2. Kiểm tra Docker port: `docker port redis-lab`
3. Nếu lỗi timeout, tăng `commandTimeout` trong client.ts
4. Nếu lỗi `redisClient` chưa ready, thêm `await new Promise(r => setTimeout(r, 2000))` trước khi gọi exercise()

---

### 2.4 Exercise: RTT Measurement (Pipeline)

**Yêu cầu:** Đo RTT (Round Trip Time) của các thao tác Redis:

- 100 lần GET (không pipeline)
- 100 lần SET (không pipeline)
- 100 lần pipeline 10 commands (MGET 10 keys)
- Tính p50, p95, p99

**Starter code:**

```typescript
// src/redis/rttBenchmark.ts
import redisClient from "./client";

function percentile(values: number[], p: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

async function rttBenchmark(): Promise<void> {
  const client = redisClient.getClient();
  const N = 100;
  const PIPELINE_SIZE = 10;

  // Setup: tạo 100 keys trước
  const keys: string[] = [];
  for (let i = 0; i < N * PIPELINE_SIZE; i++) {
    await client.set(`bench:${i}`, `value-${i}`);
  }

  // Benchmark: GET (không pipeline)
  const getTimes: number[] = [];
  for (let i = 0; i < N; i++) {
    const start = performance.now();
    await client.get(`bench:${i}`);
    getTimes.push(performance.now() - start);
  }

  // Benchmark: SET (không pipeline)
  const setTimes: number[] = [];
  for (let i = 0; i < N; i++) {
    const start = performance.now();
    await client.set(`bench:write:${i}`, `value-${i}`);
    setTimes.push(performance.now() - start);
  }

  // Benchmark: Pipeline (MGET 10 keys)
  const pipeTimes: number[] = [];
  for (let i = 0; i < N; i++) {
    const start = performance.now();
    const pipe = client.pipeline();
    for (let j = 0; j < PIPELINE_SIZE; j++) {
      pipe.mget(`bench:${i * PIPELINE_SIZE + j}`);
    }
    await pipe.exec();
    pipeTimes.push(performance.now() - start);
  }

  console.log("=== RTT Benchmark (ms) ===");
  console.log(`GET (x1):      avg=${(getTimes.reduce((a, b) => a + b) / N).toFixed(3)}, p50=${percentile(getTimes, 50).toFixed(3)}, p95=${percentile(getTimes, 95).toFixed(3)}, p99=${percentile(getTimes, 99).toFixed(3)}`);
  console.log(`SET (x1):      avg=${(setTimes.reduce((a, b) => a + b) / N).toFixed(3)}, p50=${percentile(setTimes, 50).toFixed(3)}, p95=${percentile(setTimes, 95).toFixed(3)}, p99=${percentile(setTimes, 99).toFixed(3)}`);
  console.log(`PIPELINE (x${PIPELINE_SIZE}): avg=${(pipeTimes.reduce((a, b) => a + b) / N).toFixed(3)}, p50=${percentile(pipeTimes, 50).toFixed(3)}, p95=${percentile(pipeTimes, 95).toFixed(3)}, p99=${percentile(pipeTimes, 99).toFixed(3)}`);
  console.log(`Throughput (pipeline): ${(N * PIPELINE_SIZE / (pipeTimes.reduce((a, b) => a + b) / N) / 1000).toFixed(0)} ops/sec`);
}

async function main(): Promise<void> {
  await new Promise((r) => setTimeout(r, 1000));
  await rttBenchmark();
  await redisClient.close();
}

main().catch(console.error);
```

**Expected output (local, Docker Desktop):**

```
=== RTT Benchmark (ms) ===
GET (x1):      avg=0.234, p50=0.200, p95=0.380, p99=0.610
SET (x1):      avg=0.241, p50=0.210, p95=0.390, p99=0.650
PIPELINE (x10): avg=0.280, p50=0.250, p95=0.440, p99=0.720
Throughput (pipeline): ~35700 ops/sec
```

**Ghi chú:** So sánh kết quả với không có Docker (chạy redis-server trực tiếp). Latency thường cao hơn 2-5x khi chạy qua Docker container.

---

## 3. Challenge Exercise (30-40 phút)

### Mục tiêu
Sử dụng `redis-benchmark` để benchmark Redis, phân tích kết quả, hiểu cách Redis scale.

### 3.1 Benchmark với redis-benchmark

**Bước 1:** Kiểm tra redis-benchmark có sẵn

```bash
which redis-benchmark
# Hoặc
docker exec redis-lab redis-benchmark --version
```

**Bước 2:** Chạy benchmark cơ bản (100K requests)

```bash
redis-benchmark -h 127.0.0.1 -p 6379 -n 100000 -c 50 -t get,set
```

- `-n 100000`: 100,000 requests tổng cộng
- `-c 50`: 50 concurrent connections
- `-t get,set`: chỉ test GET và SET

**Expected output:**

```
====== SET ======
  100000 requests completed in X seconds
  50 parallel clients
  50 bytes payload
  Latency percentiles (usec): 50th=200, 99th=500, 99.9th=1200

====== GET ======
  100000 requests completed in X seconds
  50 parallel clients
  Latency percentiles (usec): 50th=180, 99th=450, 99.9th=1100
```

**Bước 3:** Benchmark với nhiều payload size

```bash
# Small payload (50 bytes)
redis-benchmark -h 127.0.0.1 -p 6379 -n 50000 -c 50 -d 50 -t set

# Medium payload (1KB)
redis-benchmark -h 127.0.0.1 -p 6379 -n 50000 -c 50 -d 1024 -t set

# Large payload (10KB)
redis-benchmark -h 127.0.0.1 -p 6379 -n 50000 -c 50 -d 10240 -t set

# Very large payload (100KB)
redis-benchmark -h 127.0.0.1 -p 6379 -n 10000 -c 50 -d 102400 -t set
```

**Ghi nhận kết quả:** Latency p99 thay đổi như thế nào khi payload tăng?

**Bước 4:** Benchmark với nhiều concurrency

```bash
# 1 concurrent connection
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 1 -t get,set

# 10 concurrent
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 10 -t get,set

# 50 concurrent
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 50 -t get,set

# 200 concurrent
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 200 -t get,set
```

**Phân tích:** ops/sec thay đổi như thế nào khi concurrency tăng? Tại sao?

**Bước 5:** Benchmark pipeline

```bash
# Không pipeline (1 command per round trip)
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 50 -t get

# Pipeline 10 commands
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 50 -P 10 -t get

# Pipeline 50 commands
redis-benchmark -h 127.0.0.1 -p 6379 -n 20000 -c 50 -P 50 -t get
```

**Ghi nhận:** ops/sec tăng bao nhiêu lần khi tăng pipeline size?

### 3.2 Phân tích kết quả và viết report

**Yêu cầu:** Viết một report ngắn (trong terminal output) phân tích:

1. Qua `redis-benchmark`, tính **ops/sec** của Redis trên máy của bạn cho SET và GET (payload 50 bytes, 50 concurrent connections)
2. Khi payload tăng từ 50 bytes lên 10KB, latency p99 tăng bao nhiêu %? Giải thích tại sao.
3. Khi concurrency tăng từ 1 lên 200, ops/sec thay đổi như thế nào? Giải thích.
4. Nếu pipeline 10 commands thay vì 1 command/request, throughput tăng bao nhiêu lần?
5. Đưa ra kết luận: Redis có phù hợp để làm cache cho hệ thống cần 50,000 reads/sec không? Tại sao?

**Reference numbers (để compare):**

| Scenario | Expected ops/sec (approximate) |
|---|---|
| GET (1 conn, local) | ~30,000-80,000 |
| GET (50 conn, local) | ~100,000-300,000 |
| GET + pipeline 10 (50 conn) | ~500,000-1,000,000 |
| SET (50 conn) | ~80,000-200,000 |

---

## 4. Reflection Questions (10-15 phút)

**Trả lời những câu hỏi sau trong nhóm hoặc blog:**

**Câu 1: Decision Framework**
Một startup xây dựng e-commerce platform (100K daily active users, 1K products). Họ muốn cache product detail page (read-heavy, 95% reads, 5% writes). Bạn sẽ recommend:
- Dùng Redis làm gì? (cache, session, counter, lock, queue, ...)
- Eviction policy nào? Tại sao?
- TTL bao nhiêu là hợp lý?
- Nếu Redis bị down, hệ thống sẽ như thế nào? Có cách nào mitigate?

**Câu 2: Multi-instance Cache**
Một social network có 50 API servers. Hiện tại, mỗi server cache user profile trong local memory (Go map). Gặp vấn đề:
- User thay đổi profile, nhưng 49 server kia còn thấy profile cũ
- Memory usage = 50 x (số profiles cached) = rất lớn
Bạn sẽ thiết kế lại như thế nào với Redis? Nếu giải pháp có trade-off gì?

**Câu 3: Trade-off Analysis**
Một fintech company cần lưu transaction records (100K transactions/day). Hỏi:
- Nếu dùng Redis làm primary store (không có database), gặp risk gì?
- Nếu dùng Redis làm cache (database là primary), tại sao cần cache invalidation strategy?
- Nếu Redis mất điện 30 phút (không có persistence), gặp gì?

**Câu 4: Scalability Thinking**
Nếu 1 triệu users, mỗi user có 1 session (5KB), cần lưu 7 days. Tính:
- Tổng memory cần thiết?
- Nếu dùng local in-memory cache thay vì Redis, tổng memory là bao nhiêu?
- Nếu Redis single node không đủ dùng (maxmemory 32GB), giải pháp là gì?

**Câu 5: Anti-pattern Recognition**
Những developer này đang làm gì sai? Giải thích tại sao và đề xuất cách khắc phục:
- "Tôi dùng `KEYS order:*` trong cron job để cleanup old orders"
- "Tôi lưu toàn bộ product catalog (500MB) trong một String key"
- "Tôi không đặt TTL vì tôi muốn giữ data mãi mãi"
- "Tôi dùng Redis để lưu chat messages (1 triệu messages/day)"

---

## 5. Solution Guide

> **WARNING - SPOILER:** Phần này chứa đáp án và giải thích chi tiết. Đọc sau khi đã làm bài tập.

---

### 5.1 Warm-up - Đáp án

**1.1 PING:**
- `PONG` = Redis trả lời thành công. Nếu lỗi `Could not connect to Redis`, kiểm lại Docker: `docker ps | grep redis`.

**1.2 String operations:**
- `SETNX` trả về `1` khi key chưa tồn tại (set thành công), trả về `0` khi key đã tồn tại (không set).
- TTL trả về `-1` nếu key không có TTL, `-2` nếu key không tồn tại.

**1.3 INFO:**
- `used_memory` < `maxmemory` -> OK. Nếu `used_memory` ~ `maxmemory` -> sắp đầy.
- `maxmemory: 0` -> Redis sử dụng unbounded memory (nguy hiểm).

**1.4 CONFIG:**
- `maxmemory: 0` có nghĩa là không có giới hạn. Đặt giá trị = 70-80% RAM.

---

### 5.2 Docker - Giải thích lỗi thường gặp

**Lỗi "Could not connect to Redis at 127.0.0.1:6379":**
- Kiểm tra container: `docker ps -a | grep redis`
- Nếu container không chạy: `docker compose up -d`
- Nếu container đã chạy nhưng port không accessible: kiểm tra `docker port redis-lab`

**Lỗi "Command timeout":**
- Redis đang bị blocked bởi blocking command. Restart container: `docker restart redis-lab`
- Hoặc kiểm tra slowlog: `docker exec redis-lab redis-cli SLOWLOG GET 10`

---

### 5.3 TypeScript - Giải thích lỗi thường gặp

**Lỗi "Connection refused":**
- Do Redis chưa ready khi client connect. Thêm `await new Promise(r => setTimeout(r, 2000))` trước khi gọi exercise.
- Hoặc kiểm tra `redisClient.isConnected()` trước khi thực hiện thao tác.

**Lỗi "UnhandledPromiseRejection":**
- Do `client.ping()` hoặc operation thất bại nhưng không có try/catch. Thêm error handling.

---

### 5.4 Challenge - Phân tích chỉ tiêu

**1. Ops/sec thực tế (tham khảo):**

| Hardware | GET ops/sec | SET ops/sec |
|---|---|---|
| MacBook M1, Docker Desktop | ~80,000-150,000 | ~60,000-100,000 |
| Linux, bare metal | ~200,000-500,000 | ~150,000-400,000 |

**2. Payload size impact:**
- 50 bytes -> p99 ~300-500 us
- 10KB -> p99 ~800-2000 us (tăng 3-5x)
- Lý do: network throughput, memory allocation lớn hơn, RESP protocol parsing nhiều hơn
- 100KB -> p99 ~5000-15000 us (tăng 10-30x)
- Lý do: memory allocator overhead cho allocation > slab size, potential disk I/O nếu ddos

**3. Concurrency impact:**
- 1 -> 50 concurrent: ops/sec tăng ~30-50x (Redis single-threaded nhưng I/O multiplexing cho phép handle nhiều connection)
- 50 -> 200 concurrent: ops/sec tăng thêm ~20-50% (đã hit single-threaded ceiling)
- Lý do: Redis single-threaded, CPU bound, không thể scale beyond ~1M ops/sec trên 1 core

**4. Pipeline impact:**
- Không pipeline: 1 RTT per command
- Pipeline 10: 10 commands / 1 RTT -> throughput x ~8-10x
- Packet loss và network latency làm giảm ưu thế của pipeline ở đoạn công lớn

**5. Kết luận:**
- Redis có thể handle 50,000 reads/sec với 1 node (standalone). Như vậy, 1 node là đủ cho 100K DAU.
- Nhưng cần monitor: hit rate, eviction rate, replica lag.
- Nếu cần 500K+ reads/sec, cần Redis Cluster hoặc đọc từ replica.

---

### 5.5 Reflection - Đáp án viết tắt

**Câu 1: E-commerce Cache**
- Dùng Redis làm API response cache (cache-aside pattern)
- Eviction: `volatile-lru` (chỉ evict key có TTL) hoặc `allkeys-lru` (nếu cache hoàn toàn)
- TTL: 5-30 phút cho product detail, có thể ngắn hơn nếu product thay đổi nhiều
- Redis down: fallback sang database (nhưng có latency cao hơn). Hoặc: local cache L1 làm fallback.
- Mitigation: Redis Sentinel để automatic failover, replica để redundancy

**Câu 2: Multi-instance Cache**
- Chuyển sang Redis centralized cache: mỗi server đọc từ Redis thay vì local map
- Trade-off: +network round-trip (0.5-2ms), -memory usage giảm 50x (1 copy thay vì 50 copy)
- Có thể thêm local cache L1 (in-memory) làm LRU cache nhỏ (5 phút) trước Redis
- Implement: cache-aside với local L1 + Redis L2

**Câu 3: Fintech Transaction**
- Redis làm primary store: **KHÔNG NÊN**. Risk: mất data khi restart, OOM, hardware failure.
- Nếu Redis down 30 phút (không persistence): mất toàn bộ 30 phút transactions, không thể recover.
- Redis làm cache: cần invalidation khi database update (xóa key, giảm TTL, hoặc event-driven)
- Khuyến nghị: PostgreSQL làm primary store + Redis làm cache.

**Câu 4: Memory Calculation**
- Redis: 1 triệu x 5KB = 5GB (chi tiêu tốn ~6-7GB với overhead)
- Local cache (50 servers): 50 x 5GB = 250GB (nếu 1 triệu users trên tất cả)
- Redis single node 32GB không đủ -> Redis Cluster (sharding) hoặc tăng node size
- Tính toán: 1 triệu x 5KB = 5GB, nhân 1.3 overhead = ~6.5GB. Còn dư nếu 1 node 32GB.

**Câu 5: Anti-pattern Fixes**

| Anti-pattern | Tại sao sai | Fix |
|---|---|---|
| `KEYS order:*` trong cron | O(N), trễ 10+ giây, block all commands | Dùng `SCAN 0 MATCH order:* COUNT 1000`, hoặc lưu list key trong Set |
| 500MB String key | Big key: replicate lag, memory fragmentation, chunking rất lâu | Tách thành nhiều key nhỏ (Hash/List), hoặc stream |
| Không có TTL | Memory growth vô hạn, eviction gấp duty, không predict | Đặt TTL = 1.5x thời gian use case (ví dụ: session 2x timeout) |
| Redis cho chat messages | Redis không phải message queue mạnh, mất message khi restart, không consumer group | Dùng Kafka, RabbitMQ, hoặc Redis Streams |

---

## Cleanup

```bash
# Dừng và xóa container
docker compose down

# Xóa volume (mất toàn bộ data)
docker compose down -v
```

**Total time:** ~2 giờ (15 phút warm-up + 60 phút lab + 30 phút challenge + 15 phút reflection)
