# Day 11: Pipelining & Batching

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Giải thích được cơ chế pipelining: client gửi N command mà không đợi reply, server queue response rồi flush một lần — và tại sao điều này loại bỏ N-1 RTT.
- Phân biệt được **batching** (MGET/MSET — single command, nhiều argument) với **pipelining** (nhiều command riêng biệt serialize), biết khi nào dùng cái nào.
- Phân tích được RTT cost thực tế: 100 GET không pipeline @ 1ms RTT = 100ms; có pipeline = 1-2ms — và tại sao network latency dominate.
- Thiết kế được batch size strategy tối ưu: tránh buffer overflow (server input buffer 1GB hard limit), tránh p99 latency spike (batch too large = memory pressure + RTT tăng), chọn đúng trade-off theo workload.
- Benchmark được pipelining thực tế bằng TypeScript + ioredis: record p50/p95/p99, so sánh throughput không pipeline vs pipeline ở batch size 10/100/1000.
- Tránh được 5 pitfall nghiêm trọng: buffer overflow, routing sai trên Cluster, ordered response assumption, error handling giữa pipeline, Lua atomicity vs pipeline atomicity.

---

## 2. Tại sao cần học chủ đề này

### Incident 1: 100K SET qua WAN — 1 giờ thành 30 giây

Một batch job chạy trên một dịch vụ distributed cần warm 100K cache entries lên Redis qua kết nối WAN (RTT 50ms). Dev gửi từng `SET` một — mỗi command chờ response trước khi gửi tiếp. Kết quả: **100K × 50ms = 5.000 giây = 83 phút**. Job chạy mất 1 giờ 20 phút.

Sau khi dùng pipeline batch size 1000: **100K SET / 1000 = 100 round-trip × 50ms = 5 giây**. Cả job chạy trong **dưới 30 giây**.

**Sai lầm gốc**: Giả định rằng mỗi command Redis nhanh (~μs) nên không cần batch. Dev quên rằng server xử lý μs nhưng network RTT có thể là ms — **network latency dominates, không phải server processing time**.

### Incident 2: Big Pipeline 1M commands — Server input buffer overflow, connection killed

Một dev muốn migrate 1 triệu records từ database vào Redis trong một pipeline lớn nhất có thể. Gửi 1M SET commands trong một pipeline buffer. Kết quả: **server input buffer vượt 1GB hard limit → Redis kill connection → migration thất bại sau 45 phút chạy**.

Sau đó dev chia thành batch 50K → chạy 20 lần → hoàn thành trong 10 phút.

**Sai lầm gốc**: Không có giới hạn batch size. Server `client-query-buffer-limit` mặc định là 1GB cho toàn bộ input buffer của một client. Pipeline 1M SET (mỗi SET ~100-200 bytes serialized) = 100-200MB raw command stream, nhưng RESP overhead + key names + value content dễ dàng vượt 1GB.

### Incident 3: Redis Cluster — nhầm pipeline với multi-key command

Một dev dùng `MGET user:1:profile user:2:profile user:3:profile` trong Redis Cluster. Mỗi key hash vào một slot khác nhau. `MGET` là multi-key command nên không hỗ trợ CROSSSLOT → **CROSSSLOT error**. Khi đổi sang pipeline `GET` từng key, họ vẫn phải dùng cluster-aware client để route từng command đúng node; nếu gửi toàn bộ pipeline vào một node thường sẽ nhận `MOVED`/`ASK` per-command hoặc routing sai ở client.

**Sai lầm gốc**: Pipeline không thay đổi semantics của command. `MGET` vẫn yêu cầu tất cả keys cùng slot. Pipeline chỉ tiết kiệm RTT; cluster-aware client vẫn phải split pipeline theo node.

**Bottom line**: Pipelining là kỹ thuật đơn giản nhưng có nhiều gotcha nghiêm trọng trong production — buffer overflow, Cluster limitations, error handling, memory pressure. Không hiểu kỹ sẽ gây incident thay vì cải thiện performance.

---

## 3. Kiến thức nền cần có

- Redis single-threaded, event loop, I/O multiplexing (Day 1)
- RTT (Round-Trip Time) — đã được định nghĩa trong Day 1: thời gian client gửi request đến server và nhận response về, phụ thuộc network distance và hops
- TCP/IP basics: connection establishment (3-way handshake), socket buffer
- RESP (Redis Serialization Protocol) — cách Redis serialize command và response
- Docker, TypeScript, Node.js async/await
- Các command: GET, SET, MGET, MSET, HMGET, HGETALL

---

## 4. Nội dung lý thuyết

### 4.1. RTT Cost — Tại sao network latency dominate

Redis server xử lý một command trong **microseconds**: `GET foo` mất ~30-100μs. Nhưng nếu client ở cùng datacenter (RTT ~0.2-0.5ms), tổng thời gian = server processing + network RTT = ~0.2-0.6ms. **Server chỉ chiếm ~20% tổng latency**.

Qua WAN (RTT 50ms): tổng thời gian = 50ms + 0.1ms = **~50.1ms**. Server chiếm **0.2%**.

```txt
Local (RTT 0.2ms):
  Client --[GET]--> Server (0.05ms) --[response]--> Client
  Total: 0.25ms  | Server: 0.05ms (20%) | Network: 0.2ms (80%)

WAN (RTT 50ms):
  Client --[GET]--> Server (0.05ms) --[response]--> Client
  Total: 50.05ms | Server: 0.05ms (0.1%)| Network: 50ms (99.9%)
```

**Conclusion**: Khi RTT tăng, network trở thành bottleneck tuyệt đối. Pipelining giải quyết vấn đề này bằng cách gửi nhiều commands trong một RTT thay vì N RTT.

### 4.2. Pipelining Mechanism — I/O Timeline

**Non-pipelined** (N commands, mỗi command chờ response):

```txt
Timeline (N=5, RTT=1ms):

t=0ms:    GET key:1  ──────────────────────────────────────────────────> [server]
          <─────────────────────────────── response @ t=1ms
t=1ms:    GET key:2  ──────────────────────────────────────────────────> [server]
          <─────────────────────────────── response @ t=2ms
t=2ms:    GET key:3  ──────────────────────────────────────────────────> [server]
          <─────────────────────────────── response @ t=3ms
t=3ms:    GET key:4  ──────────────────────────────────────────────────> [server]
          <─────────────────────────────── response @ t=4ms
t=4ms:    GET key:5  ──────────────────────────────────────────────────> [server]
          <─────────────────────────────── response @ t=5ms

Total: 5 RTT = 5ms.  Server idle 80% of time.
```

**Pipelined** (N commands trong 1 RTT):

```txt
Timeline (N=5, RTT=1ms):

t=0ms:    GET key:1 GET key:2 GET key:3 GET key:4 GET key:5 ───────> [server]
          (client gửi tất cả 5 commands không đợi response)
          <─────────────────────────────── 5 responses @ t=1ms (batched)

Total: 1 RTT = 1ms.  Server không idle.
```

**ASCII diagram tổng hợp**:

```txt
┌─────────────────────────────────────────────────────────────────────────┐
│                    NON-PIPELINED: N commands = N RTTs                   │
├─────────────────────────────────────────────────────────────────────────┤
│ Client  ──[CMD1]───────────────[CMD2]───────────────[CMD3]──>           │
│             │                    │                    │                │
│             v                    v                    v                │
│ Server  [proc]              [proc]                [proc]               │
│             │                    │                    │                │
│             v                    v                    v                │
│ Client  <──[R1]───────────────[R2]────────────────[R3]───             │
│                                                                         │
│ RTT:  ●──●──●──●──●  (5 round trips)                                   │
│ Time: 0ms 1ms 2ms 3ms 4ms 5ms                                          │
│                                                                         │
│ Server utilization: ~20% (idle between commands)                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      PIPELINED: N commands = 1 RTT                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Client  ──[CMD1 CMD2 CMD3 CMD4 CMD5]───────────────────────>           │
│                                                                         │
│             v                                                          │
│ Server  [proc 5 cmds sequentially]                                     │
│             |                                                          │
│             v                                                          │
│ Client  <──────────────────────────[R1 R2 R3 R4 R5]───                 │
│                                                                         │
│ RTT:  ●──────────────────────────────●  (1 round trip)                 │
│ Time: 0ms                                     1ms                       │
│                                                                         │
│ Server utilization: ~100% (continuous processing)                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3. Batching vs Pipelining — Hai khái niệm khác nhau

Đây là điểm hay bị nhầm lẫn nhất trong pipelining.

#### Batching = Single Command, Nhiều Arguments

Một số command Redis được thiết kế để nhận nhiều arguments cùng lúc:

| Command | Mô tả | Ví dụ |
|---------|--------|--------|
| `MGET key1 key2 ... keyN` | GET nhiều keys trong 1 command | `MGET user:1 user:2 user:3` |
| `MSET key1 val1 key2 val2 ...` | SET nhiều key-value trong 1 command | `MSET a 1 b 2 c 3` |
| `HMGET hash field1 field2 ...` | GET nhiều fields từ 1 hash | `HMGET user:1 name email` |
| `HGETALL hash` | GET tất cả field-value từ 1 hash | `HGETALL user:1` |
| `DEL key1 key2 ... keyN` | Xóa nhiều keys trong 1 command | `DEL session:1 session:2` |
| `SUNIONSTORE dest set1 set2 ...` | UNION nhiều sets vào dest | `SUNIONSTORE all tag:a tag:b` |

**Ưu điểm batching (MGET/MSET)**:
- Chỉ 1 RTT cho N keys
- Server xử lý trong 1 single-threaded execution
- Ít RESP serialization overhead nhất
- Không có command interleaving risk

**Nhược điểm**:
- Giới hạn bởi cùng key type (MGET chỉ String, HMGET chỉ Hash)
- Không hỗ trợ CROSSSLOT trên Cluster
- Server vẫn phải scan tất cả keys trong memory

#### Pipelining = Nhiều Commands Riêng Biệt, Serialize

Pipeline gửi N command riêng biệt trong một TCP write, server xử lý và trả response theo thứ tự:

```txt
Client gửi (1 TCP write):
  *3\r\n$3\r\nGET\r\n$5\r\nkey:1\r\n
  *3\r\n$3\r\nGET\r\n$5\r\nkey:2\r\n
  *3\r\n$3\r\nGET\r\n$5\r\nkey:3\r\n

Server trả (1 TCP read):
  $5\r\nvalue1\r\n
  $5\r\nvalue2\r\n
  $5\r\nvalue3\r\n
```

**Ưu điểm pipeline**:
- Áp dụng cho **bất kỳ command nào** (không giới hạn MGET/MSET)
- Giảm RTT từ N × RTT → 1 × RTT
- Commands không cần cùng key hoặc cùng type
- Server vẫn xử lý sequential, nhưng không có idle time giữa commands

**Nhược điểm**:
- Response không atomic — commands vẫn có thể interleaved với commands từ client khác
- Nếu command thứ 3 bị error, commands 4-N vẫn được execute
- Ordered response: client phải parse responses theo đúng thứ tự gửi

### 4.4. Server-Side Queue — Điều gì xảy ra khi command đến server

```txt
TCP Socket (client connection)
      │
      ▼
client-query-buffer  (input buffer, config: client-query-buffer-limit)
      │  ← command stream được đọc vào đây
      ▼
Command Parser ( RESP deserialization )
      │
      ▼
Server Command Queue (event loop ring buffer)
      │
      ▼
Single-threaded Command Processor
      │
      ▼
Output Buffer (client-output-buffer-limit)
      │
      ▼
TCP Socket (response gửi về client)
```

**client-query-buffer-limit** (default: 1GB hard limit):
- Kích thước tối đa của input buffer cho mỗi client connection
- Pipeline quá lớn → buffer vượt limit → **Redis kill connection**
- Config: `client-query-buffer-limit 1gb` (per client)

**client-output-buffer-limit** (default: normal=8MB/60s, replica=256MB/60s, pubsub=32MB/60s):
- Kích thước tối đa của output buffer trước khi Redis ngừng gửi cho client
- Nếu client đọc chậm (network congestion, client crash), output buffer grow → bị limit
- Config: `client-output-buffer-limit normal 8mb 60s 2mb 30s`

**proto-max-bulk-len** (default: 512MB):
- Kích thước tối đa của một single bulk string trong RESP protocol
- Một value 600MB → vượt proto-max-bulk-len → error

### 4.5. Batch Size Limit — Too Small vs Too Large

Batch size = số commands gửi trong một pipeline trước khi gọi `exec()`.

```txt
Batch size tối ưu phụ thuộc vào:
  - RTT: RTT càng lớn → batch size càng lớn có ích (ít RTT overhead)
  - Memory: server input buffer (1GB limit), client memory, output buffer
  - p99 latency budget: batch càng lớn → single exec() càng lâu → p99 spike
  - Error recovery: batch lớn → lỗi ở giữa → phải retry nhiều
```

**Too small (batch size = 1)**:
- Không khác gì non-pipeline
- RTT overhead chiếm 99% thời gian
- VD: 10K commands, batch=1, RTT=1ms → 10 giây

**Too large (batch size = 1M)**:
- Server input buffer overflow → connection killed
- Client memory pressure: pipeline buffer chứa 1M commands + responses
- p99 latency spike: exec() cho 1M commands có thể mất 1-10 giây
- Error recovery khó: lỗi ở command 500K → phải retry 500K commands
- VD: 1M SET commands × ~200 bytes each = ~200MB serialized → gần đụng 1GB limit

**Recommended batch sizes theo RTT**:

| RTT | Recommended batch size | Rationale |
|-----|----------------------|-----------|
| Local (0.1ms) | 50-500 | RTT cheap, small batches fine |
| Same DC (0.5ms) | 100-1,000 | Moderate RTT, 100x improvement |
| Cross-DC (5ms) | 500-5,000 | High RTT, maximize batch |
| WAN (50ms+) | 1,000-10,000 | Critical: minimize RTT count |
| Satellite (500ms+) | 10,000-50,000 | Extreme RTT, batch as large as possible |

**Memory calculation cho batch size**:

```txt
Batch size 1000, mỗi SET ~100 bytes serialized:
  Input buffer: 1000 × 100 bytes = ~100KB
  Output buffer: 1000 × ~50 bytes response = ~50KB
  Total per batch: ~150KB

Batch size 100,000:
  Input buffer: 100,000 × 100 = ~10MB
  → Still safe (1GB limit)

Batch size 10,000,000:
  Input buffer: 10M × 100 = ~1GB → AT LIMIT
  → Risk: 1 command dư thêm → overflow → killed
```

### 4.6. Pipeline vs MULTI/EXEC — Atomicity

| Aspect | Pipeline | MULTI/EXEC |
|--------|----------|------------|
| **Atomicity** | Không atomic — commands có thể interleaved | Atomic — tất cả commands execute together hoặc không |
| **RTT** | 1 RTT (batch) | 2 RTT (MULTI → N commands → EXEC) |
| **Error handling** | Error trả về riêng, commands sau vẫn execute | Nếu 1 command fail, tất cả discard |
| **WATCH support** | Không hỗ trợ WATCH | Hỗ trợ WATCH (optimistic lock) |
| **Cluster** | Pipeline theo node | MULTI/EXEC cũng phải cùng slot |
| **Use case** | Bulk read/write, no atomicity needed | Inventory, balance transfer, any ACID-like need |

**Ví dụ error in middle of pipeline**:

```txt
> PIPELINE
GET key:1
GET nonexistent-key
INCR counter:1    -- lỗi: key type wrong (not integer)
GET key:2
> EXEC
1) "value1"
2) (nil)
3) (error) ERR value is not an integer
4) "value2"
```

Redis vẫn trả về response cho tất cả 4 commands. Command 3 trả về error, nhưng commands 1, 2, 4 vẫn được execute. Client phải handle error riêng.

**MULTI/EXEC với WATCH**:

```txt
> WATCH balance:user:1
OK
> MULTI
> DECRBY balance:user:1 100
> INCRBY balance:user:2 100
> EXEC
1) (integer) 900
2) (integer) 1100
```

Nếu có client khác thay đổi `balance:user:1` giữa WATCH và EXEC → EXEC trả về `(nil)` (transaction aborted).

### 4.7. Pipeline vs Lua Script

| Aspect | Pipeline | Lua Script |
|--------|---------|-----------|
| **Atomicity** | Không atomic | Atomic (script execute đơn nhất) |
| **RTT** | N RTT → 1 RTT | 1 RTT (script body gửi 1 lần) |
| **Parallel I/O** | Yes (commands execute sequential, I/O parallel) | No (sequential execution, event loop blocked) |
| **Event loop blocking** | Không block | Có thể block event loop nếu script dài |
| **Network efficiency** | Good (N commands) | Excellent (1 command) |
| **Logic flexibility** | Limited to existing commands | Full Lua logic |
| **Use when** | Bulk read/write, no atomicity needed | Atomic + logic, short scripts |
| **Blocking risk** | Low | High if script > 5ms |

**Lua script làm blocking event loop**:

```lua
-- Bad: long-running script
local keys = redis.call('KEYS', 'user:*')  -- O(N), blocks event loop
for i, key in ipairs(keys) do
    redis.call('DEL', key)
end
return #keys
```

**Pipeline cho bulk operations**:

```go
// Tốt: dùng pipeline, không block event loop
pipe := rdb.Pipeline()
for i := 0; i < 1000; i++ {
    pipe.Del(ctx, fmt.Sprintf("user:%d", i))
}
pipe.Exec(ctx)
```

### 4.8. Pipeline vs MGET/MSET (Benchmark Numbers)

Với 100 keys, 1KB value, RTT 0.5ms:

```txt
Non-pipeline (100 GET riêng):
  100 × 0.5ms = 50ms total
  Throughput: 2,000 ops/sec

MGET (1 command, 100 keys):
  1 × 0.5ms = 0.5ms total
  Throughput: 100 ops in 0.5ms = 200,000 ops/sec
  (Redis xử lý MGET trong ~0.1ms, network 0.5ms)

Pipeline (100 GET trong 1 RTT):
  1 × 0.5ms = 0.5ms total
  Throughput: 100 ops in 0.5ms = 200,000 ops/sec
  (Redis xử lý 100 GETs trong ~1ms, nhưng network 0.5ms)
```

**MGET vs Pipeline**: MGET nhanh hơn chút vì:
1. Chỉ 1 command parse thay vì 100 command parses
2. Không có RESP overhead cho command headers
3. Redis optimize MGET bằng `lookupKeyRead()` loop

**Nhưng**: MGET chỉ hoạt động với String keys. Pipeline hoạt động với bất kỳ command nào.

### 4.9. Implementation Gotchas

#### Gotcha 1: Ordered Response

Pipeline trả response **theo đúng thứ tự commands được gửi**. Client phải parse responses theo index:

```typescript
const pipeline = redis.pipeline();
pipeline.get('key:1');
pipeline.get('key:2');
pipeline.get('key:3');
const results = await pipeline.exec();
// results[0] = ['error or null', 'value']
// results[1] = ['error or null', 'value']
// results[2] = ['error or null', 'value']
```

#### Gotcha 2: Error in Middle of Pipeline

Như đã nói ở 4.6: Redis execute tất cả commands, chỉ trả error riêng. Client phải handle:

```typescript
const results = await pipeline.exec();
for (const [err, value] of results) {
    if (err) {
        console.error('Command error:', err);
        // Handle error, không phải crash
    }
}
```

#### Gotcha 3: Pipeline trên Cluster — routing theo node

Pipeline không thay đổi Cluster routing. Multi-key commands như `MGET`, `MSET`, `DEL key1 key2` vẫn cần keys cùng slot. Pipeline gồm nhiều `GET` đơn-key có thể chạy trên nhiều slot, nhưng client phải tách theo node hoặc handle `MOVED`/`ASK` đúng cách:

```typescript
// Sai trên Cluster nếu dùng single-node Redis client:
// tất cả commands bị gửi tới một node, node đó có thể trả MOVED/ASK.
const pipeline = singleNodeRedis.pipeline();
pipeline.get('user:1'); // slot 100
pipeline.get('user:2'); // slot 250
pipeline.get('user:3'); // slot 400

// Đúng: dùng cluster-aware client; ioredis split pipeline theo node.
const cluster = new Redis.Cluster([{ host: '127.0.0.1', port: 7000 }]);
const pipe = cluster.pipeline();
pipe.get('user:1');
pipe.get('user:2');
pipe.get('user:3');
await pipe.exec();
```

#### Gotcha 4: Client Output Buffer Limit — Client Đọc Chậm

Nếu client không đọc responses kịp (network slow, client busy), output buffer tăng → bị limit → Redis ngừng gửi:

```bash
# Kiểm tra output buffer
redis-cli CLIENT LIST | grep obl
# obl = output buffer length
# oll = output list length (queued responses)
```

#### Gotcha 5: Pipeline vs Pub/Sub

Pipeline không hoạt động với Pub/Sub. SUBSCRIBE là blocking command — client phải đọc từ subscription socket riêng. Dùng `CLIENT REPLY ON/OFF` nếu muốn fire-and-forget trong pipeline (không đọc response).

---

## 5. Trade-off Analysis

### 5.1. Latency vs Throughput

| Aspect | Non-pipeline | Pipeline (batch size N) |
|--------|-------------|------------------------|
| Latency per operation | RTT × 1 | RTT / N (amortized) |
| p50 latency (100 ops, RTT=1ms) | 100ms | ~1ms |
| p99 latency (100 ops, RTT=1ms) | 100ms | ~1ms |
| Throughput | N / (N × RTT) = 1/RTT | N / RTT |
| Server CPU | Low (idle between ops) | High (continuous processing) |
| Best for | Interactive, real-time, N < 10 | Bulk operations, batch jobs |

### 5.2. Batch Size Lớn vs Memory Pressure

| Batch size | Memory (input+output) | p99 latency | Risk |
|-----------|----------------------|-------------|------|
| 10 | ~2KB | ~0.5ms | None |
| 100 | ~20KB | ~0.5ms | None |
| 1,000 | ~200KB | ~1ms | None |
| 10,000 | ~2MB | ~2-5ms | Low |
| 100,000 | ~20MB | ~10-30ms | Medium |
| 1,000,000 | ~200MB | ~100-500ms | High (buffer limit) |
| 10,000,000 | ~2GB | Timeout | Very High (overflow) |

### 5.3. Pipeline vs Lua Script

| Aspect | Pipeline | Lua Script |
|--------|---------|-----------|
| Atomicity | Không atomic | Atomic |
| Blocking event loop | Không | Có (nếu script dài) |
| RTT | 1 RTT | 1 RTT |
| Network overhead | N command headers | 1 script body |
| Logic capability | Fixed commands only | Full Lua logic |
| Error handling | Per-command | Fail on first error |
| Best when | Bulk read/write, hot data | Atomic operations with logic, short scripts |
| Risk | Non-atomic | Event loop blocking |

### 5.4. Pipeline vs MGET/MSET

| Aspect | MGET/MSET | Pipeline |
|--------|-----------|---------|
| RTT | 1 RTT | 1 RTT |
| Command overhead | 1 RESP header | N RESP headers |
| Server parse | 1 command | N commands |
| Key restriction | Same key type | Any command |
| Cluster routing | Same slot required | Cluster-aware client split theo node |
| Best when | Fetch many String keys | Mixed commands, non-String keys |
| Performance | Slightly faster | Slightly slower |

### 5.5. Pipeline Non-atomic vs MULTI/EXEC Atomic

| Aspect | Pipeline | MULTI/EXEC |
|--------|---------|-----------|
| Atomicity | Không | Có |
| RTT | 1 RTT | 2 RTT (MULTI + EXEC) |
| WATCH support | Không | Có |
| Error in middle | Execute, return error | Discard all |
| Cluster | Per-node pipeline | Per-node transaction |
| Use case | Bulk read/write, warmup | Financial ops, inventory |

### 5.6. Pipeline trên Cluster

| Aspect | Single pipeline | Pipeline per node |
|--------|----------------|-----------------|
| Cluster routing | MOVED/ASK nếu gửi sai node | Tách theo node, không routing sai |
| RTT | N commands / 1 RTT | N/M commands / 1 RTT (M = nodes) |
| Implementation | Đơn giản (nếu cùng slot) | Phức tạp (cần routing) |
| ioredis support | Tự động | Tự động (cluster mode) |
| Best when | Keys cùng slot | Keys phân tán nhiều slot |

---

## 6. Best Solution & Best Practices

### 6.1. Pipeline Best Practices

1. **Luôn đặt batch size cap**: Không bao giờ gửi pipeline > 100K commands. Đặt limit 10K-50K cho an toàn.
2. **Dùng MGET/MSET khi có thể**: Khi fetch nhiều String keys, MGET nhanh hơn pipeline GET.
3. **Xử lý error per-command**: Luôn check `err` trong mỗi response tuple.
4. **Dùng `pipeline.exec()` trong try/catch**: Nếu connection die, exec() sẽ throw.
5. **Đo p99 latency**: Batch size tối ưu không phải batch lớn nhất có thể — mà là batch cho p99 latency < SLO.
6. **Monitor server buffer**: `redis-cli CLIENT LIST | grep obl` + alert khi obl > 1MB.
7. **Cluster-aware routing**: Dùng ioredis cluster, nó tự động tách pipeline theo node.

### 6.2. Best Practice theo Scenario

| Scenario | Recommendation | Batch size |
|----------|--------------|------------|
| Cache warmer 100K records (LAN) | Pipeline SET | 1,000-5,000 |
| Cache warmer 100K records (WAN 50ms) | Pipeline SET | 5,000-10,000 |
| Real-time API: fetch 20 user profiles | MGET | 20 (single MGET) |
| Real-time API: fetch user + session + permissions | Pipeline GET × 3 | 3 |
| Background job: process 1M records | Pipeline + chunked | 10,000 per chunk |
| Rate limit check: 5 Redis calls per request | Pipeline GET × 5 | 5 |
| Session store: read 50 session fields | HMGET | 1 (HMGET 50 fields) |
| Complex atomic operation | Lua script | 1 (script atomic) |
| Pipeline trên Cluster | ioredis cluster auto-route | Per-node pipeline |

### 6.3. Anti-patterns

1. **Pipeline không giới hạn**: Gửi 1M commands trong 1 pipeline → input buffer overflow.
2. **Dùng pipeline thay MULTI/EXEC khi cần atomicity**: Inventory transfer cần MULTI/EXEC hoặc Lua.
3. **Dùng Lua khi pipeline đủ**: Đơn giản hóa được thì không cần Lua.
4. **Bỏ qua ordered response**: Parse responses theo index, không theo key name.
5. **Dùng pipeline trên Cluster mà không hiểu routing**: Multi-key khác slot → `CROSSSLOT`; pipeline đơn-key gửi sai node → `MOVED`/`ASK`.

---

## 7. Performance Considerations

### 7.1. Concrete Throughput Numbers

```txt
RTT = 1ms (same DC), commands = 100 GET, value = 100 bytes:

Non-pipeline:  100 × 1ms = 100ms   → 1,000 ops/sec
MGET:         1 × 1ms  = 1ms     → 100,000 ops/sec  (100× faster)
Pipeline-100: 1 × 1ms  = 1ms     → 100,000 ops/sec  (100× faster)
Pipeline-1000: 0.1×1ms = 0.1ms   → 1,000,000 ops/sec (1,000× faster)

RTT = 50ms (WAN), commands = 100 GET:

Non-pipeline:  100 × 50ms = 5,000ms  → 20 ops/sec
Pipeline-100: 1 × 50ms   = 50ms     → 2,000 ops/sec   (100× faster)
Pipeline-1000: 0.1×50ms  = 5ms      → 20,000 ops/sec  (1,000× faster)
```

### 7.2. Memory Overhead

```txt
Pipeline batch size N, mỗi command ~100 bytes serialized:

Client-side:
  Command buffer: N × 100 bytes
  Response buffer: N × ~50 bytes (simple OK/value)
  Total: N × 150 bytes

Server-side (per client):
  Input buffer: up to client-query-buffer-limit (default 1GB)
  Output buffer: up to client-output-buffer-limit (default 8MB)
  Server xử lý commands sequentially trong single thread

Memory safety:
  Batch size 10,000:  ~1.5MB/client
  Batch size 100,000: ~15MB/client
  Batch size 500,000: ~75MB/client  (safe)
  Batch size 10,000,000: ~1.5GB/client → overflow
```

### 7.3. p95/p99 Latency Impact

```txt
Batch size 1,000, RTT 1ms:
  p50: ~1ms  (amortized RTT)
  p95: ~1.5ms  (network jitter)
  p99: ~2ms    (server queue spike)

Batch size 100,000, RTT 1ms:
  p50: ~1ms  (amortized)
  p95: ~10ms  (large response parsing)
  p99: ~50ms  (garbage collection, OS scheduling)

Batch size 10,000, RTT 50ms (WAN):
  p50: ~50ms
  p95: ~52ms
  p99: ~60ms  (network variance)
  Latency budget còn lại: 50ms → có thể dùng batch 10K
```

### 7.4. Server Processing Time vs Network Time

```txt
Command: GET key (xử lý trong ~30μs = 0.03ms)

Local (RTT 0.2ms):
  Server: 0.03ms (15%)  |  Network: 0.2ms (85%)

Same DC (RTT 1ms):
  Server: 0.03ms (3%)   |  Network: 1ms (97%)

Cross-DC (RTT 10ms):
  Server: 0.03ms (0.3%) |  Network: 10ms (99.7%)

WAN (RTT 100ms):
  Server: 0.03ms (0.03%)|  Network: 100ms (99.97%)
```

---

## 8. Production Failure Modes

### 8.1. Server Input Buffer Overflow (Pipeline quá lớn)

**Nguyên nhân**: Pipeline gửi > 1GB serialized commands vào input buffer (default `client-query-buffer-limit 1gb`). Khi 1 command + overflow > limit → Redis kill connection.

**Dấu hiệu**:
- Client nhận error: `Connection closed` hoặc `Protocol error`
- Server log: `Client exceeded output buffer limit`
- `redis-cli CLIENT LIST` → client có `flags=N` (dead)

**Debug**:
```bash
# Kiểm tra client buffer status
redis-cli CLIENT LIST | awk -F'=' '{print $2}' | grep -E "addr|cmd|obl|oll"

# Kiểm tra server config
redis-cli CONFIG GET client-query-buffer-limit
redis-cli CONFIG GET client-output-buffer-limit
```

**Fix**:
1. Giảm batch size (max 50K-100K commands/pipeline)
2. Chunk large jobs thành nhiều pipeline nhỏ
3. Tăng `client-query-buffer-limit` nếu cần (VD: 4gb) — nhưng cần đảm bảo RAM đủ

### 8.2. Client Output Buffer Backpressure

**Nguyên nhân**: Client đọc responses chậm (network congestion, client busy, crash). Output buffer grow → đạt limit → Redis ngừng gửi.

**Dấu hiệu**:
- Client operations timeout dù server vẫn alive
- `redis-cli CLIENT LIST` → client có ` obl > 0`
- Server log: `Client paused because output buffer limits`

**Debug**:
```bash
redis-cli CLIENT LIST | head -3
# obl = output buffer length (bytes pending send)
# oll = output list length (number of pending replies)
```

**Fix**:
1. Client phải đọc responses nhanh — dùng streaming parser
2. Giảm pipeline batch size
3. Tăng `client-output-buffer-limit`
4. Kiểm tra network path (iperf, netstat)

### 8.3. Cluster Routing Sai Khi Pipeline

**Nguyên nhân**: Dùng single-node client để pipeline keys phân tán nhiều slot, hoặc dùng multi-key command với keys khác slot.

**Dấu hiệu**:
- `CROSSSLOT Keys in request don't hash to the same slot` cho multi-key command
- `MOVED` hoặc `ASK` replies cho pipeline đơn-key gửi sai node

**Fix**:
1. Dùng hash tag `{...}` trong key name để pins keys vào cùng slot
2. Dùng ioredis cluster (tự động tách pipeline theo node)
3. Tách pipeline theo node thủ công

### 8.4. Ordered Response Assumption Violation

**Nguyên nhân**: Client parse response không đúng index. Một pipeline với conditional logic (nếu key tồn tại thì GET, không thì SKIP) → response count thay đổi.

**Fix**: Luôn gửi cùng số commands, parse theo index, handle nil/error.

### 8.5. p99 Latency Spike từ Large Batch

**Nguyên nhân**: Batch quá lớn → exec() block lâu → tất cả request trong batch bị delay cùng lúc → p99 spike.

**Dấu hiệu**:
- p50 tốt (1ms) nhưng p99 cao (> 100ms)
- Benchmark cho thấy batch 100K chậm hơn batch 10K × 10

**Fix**: Benchmark với nhiều batch sizes, chọn batch size tối ưu cho p99 < SLO.

---

## 9. Real-world Examples

### 9.1. Twitter — Bulk Cache Warmup

Twitter dùng pipeline để warm cache sau khi Redis instance restart. 100 triệu user timeline entries được warm bằng pipeline batch size 10,000 qua internal network (RTT ~1ms). Total time: ~100 triệu / 10,000 × 1ms = 10,000ms = ~10 giây. Non-pipeline: 100 triệu × 1ms = 100,000 giây = ~27 giờ.

**Trade-off**: Batch size 10,000 → input buffer ~1.5MB/client → server vẫn healthy. Không pipeline: 100 triệu RTT → 27 giờ.

### 9.2. Shopify — Bulk Product Import

Shopify dùng pipeline để import 1 triệu sản phẩm từ database vào Redis cache. Dùng pipeline batch size 5,000, RTT ~0.5ms. Total: 1M / 5,000 × 0.5ms = 100ms. Non-pipeline: 500 giây.

**Trade-off**: Pipeline batch 5,000 → 200 round trips thay vì 1 triệu → 99.98% reduction in RTT overhead.

### 9.3. Discord — Message Cache Warmer

Discord warm cache với hàng tỷ messages. Dùng pipeline MSET (không phải generic pipeline) để batch 10,000 messages/request. Qua WAN (RTT ~20ms), 10,000 messages × 20ms = 200ms. Non-pipeline: 10,000 × 20ms = 200,000ms = 200 giây.

### 9.4. Stripe — Idempotency Key Check

Stripe dùng pipeline GET × 5 để check 5 idempotency keys trong 1 RTT thay vì 5 RTT. Với 100K API calls/giờ, RTT 1ms → 500 giây tiết kiệm/giờ. MGET cho 5 keys cùng tốc độ, nhưng idempotency keys có thể là nhiều loại → pipeline linh hoạt hơn.

---

## 10. Common Pitfalls

1. **Pipeline quá lớn gây buffer overflow**: Không đặt cap batch size → connection killed. Luôn đặt max batch size ≤ 100K.

2. **Dùng pipeline thay MULTI/EXEC cho atomic operation**: Inventory reservation cần atomic. Pipeline không đảm bảo — commands có thể interleaved. Dùng MULTI/EXEC + WATCH hoặc Lua script.

3. **Tưởng MGET thay thế được mọi batch operation**: MGET chỉ hoạt động với String keys. Hash fields cần HMGET. Pipeline hoạt động với mọi thứ.

4. **Bỏ qua error handling trong pipeline response**: `results[0]` có thể là `['error object', null]`. Không check error → silent data loss.

5. **Cluster routing bị hiểu sai**: `MGET` khác slot gây `CROSSSLOT`; pipeline `GET` đơn-key cần cluster-aware routing, không phải tất cả keys cùng slot.

6. **Dùng Lua khi pipeline đủ**: Lua block event loop. Pipelining đạt cùng RTT mà không block. Chỉ dùng Lua khi cần atomicity + logic.

7. **Không monitor output buffer**: `redis-cli CLIENT LIST` + `INFO clients` → alert khi output buffer > 1MB. Client đọc chậm → cascading failure.

8. **p99 latency spike không noticed**: Batch lớn → p99 tăng đột ngột → SLO breach. Luôn đo p99 khi benchmark, không chỉ p50.

---

## 11. Câu hỏi tự kiểm tra

**Câu 1.** Bạn cần warm 10 triệu cache entries (1KB/entry) qua WAN (RTT 50ms). Batch size tối ưu là bao nhiêu nếu client memory = 512MB và server `client-query-buffer-limit` = 1GB? Thời gian warm hoàn toàn là bao lâu?

<details>
<summary>Đáp án</summary>

```txt
Calculation:
  10M entries × 1KB = 10GB total data
  Mỗi SET command serialized: ~1,050 bytes (SET key value)
  Batch size N: N × 1,050 bytes input + N × ~5 bytes output ≈ N × 1,055 bytes

Client memory limit: 512MB
  Max batch = 512MB / 1,055 ≈ 500,000 commands/batch

Server input buffer limit: 1GB
  Max batch = 1GB / 1,055 ≈ 950,000 commands/batch

Safe batch size: ~100,000 (accounting for overhead, safety margin)

Total time:
  Non-pipeline: 10M × 50ms = 500,000,000ms = 138.8 hours
  Pipeline-100K: 10M / 100,000 × 50ms = 100 × 50ms = 5,000ms = 5 seconds
  Pipeline-10K: 10M / 10,000 × 50ms = 1,000 × 50ms = 50,000ms = 50 seconds
```

</details>

**Câu 2.** Khi nào nên dùng MGET thay vì pipeline GET × N? Tại sao?

<details>
<summary>Đáp án</summary>

Dùng MGET khi:
- Tất cả keys là String type (MGET chỉ hoạt động với String)
- Keys nằm trong cùng hash slot (Cluster requirement vẫn apply)
- Fetching > 10 keys cùng loại (MGET có ít RESP overhead hơn pipeline)

Pipeline GET × N khi:
- Keys có type khác nhau (String + Hash + List)
- Cần conditional logic (nếu key A tồn tại thì GET key B)
- Cần mix read và write commands trong cùng pipeline

MGET nhanh hơn chút vì: 1 RESP command header thay vì N headers. Nhưng với N < 100, difference không đáng kể (< 5%).

</details>

**Câu 3.** Một pipeline với 1,000 commands gặp error ở command thứ 500. Điều gì xảy ra với commands 501-1000? Code TypeScript xử lý như thế nào?

<details>
<summary>Đáp án</summary>

Redis execute tất cả 1,000 commands, chỉ trả error riêng cho command 500. Commands 1-499 và 501-1000 vẫn được execute và trả về response bình thường.

```typescript
const pipeline = redis.pipeline();
for (let i = 1; i <= 1000; i++) {
    pipeline.set(`key:${i}`, `value:${i}`);
}
const results = await pipeline.exec();

for (let i = 0; i < results.length; i++) {
    const [err, value] = results[i];
    if (err) {
        console.error(`Command ${i} failed:`, err);
        // Vẫn continue, không crash
    } else {
        // value is the actual response
    }
}
```

**Nếu cần atomicity**: dùng Lua script hoặc MULTI/EXEC.

</details>

**Câu 4.** Bạn chạy Redis Cluster với 3 node (mỗi node có 1 master + 1 replica). Bạn muốn pipeline 100 GET commands trong đó keys phân tán ngẫu nhiên trên 3 slot. Điều gì xảy ra? Làm sao để fix?

<details>
<summary>Đáp án</summary>

MGET trên nhiều slot → CROSSSLOT error. Pipeline GET × N trên nhiều slot **không phải multi-key command**, nhưng phải dùng cluster-aware client để split theo node. Nếu dùng single-node client, từng command có thể nhận `MOVED`/`ASK` và pipeline sẽ fail hoặc phải retry theo redirect.

**Fix options**:
1. **Dùng hash tag**: `user:{tenant}:profile` → `{tenant}` là hash tag → tất cả keys cùng slot nếu cùng tenant.
2. **Dùng ioredis cluster**: ioredis tự động tách pipeline theo node, gửi commands đến node đúng slot.
3. **Tách pipeline thủ công**: Lấy slot map từ `CLUSTER SLOTS`, group commands theo slot/node, gửi pipeline riêng cho mỗi node.

```typescript
// ioredis cluster mode tự động route đúng
const cluster = new Redis.Cluster([/* nodes */]);
const pipeline = cluster.pipeline();
for (const key of keys) {
    pipeline.get(key); // ioredis tự routing
}
const results = await pipeline.exec();
```

</details>

**Câu 5.** So sánh pipeline vs Lua script cho trường hợp: "atomic counter increment + check > threshold + reset nếu exceed". Pipeline có đủ không? Tại sao?

<details>
<summary>Đáp án</summary>

Pipeline **không đủ** vì:
1. Không atomic: giữa INCR và GET, client khác có thể INCR → race condition.
2. Không có logic: pipeline chỉ gửi commands, không có if/else.

Lua script **đủ** vì:
1. Atomic: script execute đơn nhất trong event loop, không interrupt.
2. Logic: có thể if/else, return early.

```lua
local current = redis.call('INCR', KEYS[1])
if current > tonumber(ARGV[1]) then
    redis.call('SET', KEYS[1], 0)
    return 0
end
return current
```

**Trade-off**: Lua block event loop → chỉ dùng cho short scripts (< 1ms). Nếu script phức tạp (loop qua nhiều keys), pipeline vẫn tốt hơn vì không block.

</details>

**Câu 6.** Batch size 100K commands → p99 latency spike lên 200ms. Bạn muốn giữ p99 < 50ms. Batch size tối ưu là bao nhiêu?

<details>
<summary>Đáp án</summary>

Không có công thức chính xác — phải benchmark thực tế. Nhưng có thể ước tính:

```txt
Observation: batch 100K → p99 = 200ms
Observation: batch 10K → p99 = ~20ms (assume, cần verify)

Rule of thumb: p99 tăng tuyến tính với batch size
  → p99 ≈ batch_size × constant

Batch 100K → p99 200ms
  → constant ≈ 200ms / 100,000 = 0.002ms/command

Target p99 < 50ms:
  → batch_size < 50ms / 0.002ms = 25,000 commands

Recommendation: benchmark 5K, 10K, 15K, 20K, 25K để tìm sweet spot.
Start với batch 10K → đo p99 → scale up/down.
```

</details>

**Câu 7.** Bạn phát hiện `redis-cli INFO clients` có `client_longest_output_list: 50MB`. Điều gì đang xảy ra?

<details>
<summary>Đáp án</summary>

`client_longest_output_list` = output buffer lớn nhất của bất kỳ client nào. 50MB → có client đọc responses chậm, output buffer tích tụ.

**Nguyên nhân có thể**:
1. Client network chậm (congestion, client ở xa)
2. Client crash nhưng không close connection (zombie connection)
3. Client đang xử lý responses quá chậm (single-threaded client, blocking I/O)

**Debug**:
```bash
# Tìm client có output buffer lớn
redis-cli CLIENT LIST | awk -F'|' '{print $1, $10, $11}' | sort -k3 -rn | head
# $10 = obl (output buffer length)
# $11 = oll (output list length)
```

**Fix**:
1. Tăng `client-output-buffer-limit`
2. Giảm pipeline batch size
3. Kiểm tra client network
4. Kill zombie connection: `redis-cli CLIENT KILL <id>`

</details>
