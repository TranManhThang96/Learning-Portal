# Day 16: Lua Scripting & Redis Functions

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân tích được cơ chế atomicity của Lua script trong Redis single-threaded, giải thích được tại sao script 100ms có thể làm p99 latency toàn cụm tăng từ 1ms lên 500ms+.
- Phân biệt được EVAL vs EVALSHA vs Redis Functions, biết khi nào dùng cái nào và tại sao EVAL thuần luôn là anti-pattern trong production.
- Viết được Lua script deterministic (chỉ truy cập key qua KEYS[]) chạy đúng trên Redis Cluster mà không gây MOVED/ASK redirection.
- Implement được rate limiter bằng Lua với latency < 500us thay vì 3 round-trip application-level, benchmark được throughput gain.
- Quản lý được script lifecycle: SCRIPT LOAD, EVALSHA với fallback, SCRIPT KILL khi script blocking quá lâu — không để incident thoát ra production.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Lua Loop 100ms -> P99 Toàn Cụm 500ms+

Một dev viết Lua script để atomic increment một counter có TTL. Script đơn giản, chạy 100ms vì trong loop có 1 triệu iterations (bug: dùng `for i=1, 1000000 do`). Script chạy trong main thread của Redis. Trong 100ms đó, tất cả 50.000 requests khác đang chờ. Kết quả: p99 latency tăng từ 1ms lên 600ms, p999 timeout, cascading retry storm. Nguyên nhân root: dev không biết `lua-time-limit` default = 5000ms, script đã block main thread suốt 100ms mà không bị kill.

**Misconception phổ biến**: "Lua script nhanh vì atomic". Thực tế: atomic miễn phí, nhưng blocking miễn phí thì KHÔNG.

### Incident 2: EVAL Thay Vì EVALSHA -> 50% Bandwidth Lãng Phí

Một hệ thống có 10 triệu calls/ngày tới Lua script. Dev dùng EVAL với script body gửi lên server mỗi lần. Script body = 500 bytes. Bandwidth lãng phí: 10M × 500B = 5GB bandwidth/ngày chỉ để gửi script text mà đáng lẽ chỉ cần gửi 20-byte SHA1 hash. Thêm vào đó, server phải parse script, compute SHA1 mỗi lần thay vì lookup cache.

**Misconception phổ biến**: "EVAL đơn giản, không cần SCRIPT LOAD trước". Production = EVALSHA + SCRIPT LOAD trên startup.

### Incident 3: Dynamic EVAL Làm Phình Script Cache

Team generate Lua script bằng string interpolation theo tenant rồi gọi `EVAL` trực tiếp trên hot path. Mỗi request tạo ra một script body khác nhau, Redis phải lưu vào script cache thay vì tái sử dụng SHA1. Trên Redis trước 7.4, cache này không tự thu gọn; trên Redis 7.4+ script chạy bằng `EVAL`/`EVAL_RO` có thể bị evict theo LRU khi quá nhiều script khác nhau. Kết quả thực tế: memory tăng khó giải thích, p99 tăng vì parse/compile liên tục, và sau restart toàn bộ `EVALSHA` bị `NOSCRIPT` nếu application không preload lại.

**Fix production**: script body phải stable, truyền dữ liệu qua `KEYS[]`/`ARGV[]`; preload bằng `SCRIPT LOAD` trên từng Redis process; luôn có `NOSCRIPT` fallback; nếu cần lifecycle/versioning qua restart và replication, dùng Redis Functions.

**Bottom line**: Lua scripting là con dao hai lưỡi — atomicity miễn phí nhưng nếu không hiểu blocking risk và script management, bạn sẽ gây incident lớn hơn không dùng Lua.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model, event loop (Day 1)
- Pipeline và RTT cost (Day 11) — hiểu tại sao 1 round-trip luôn tốt hơn N round-trip
- Connection pooling và latency (Day 12) — script overhead nằm ở đâu
- Transaction và WATCH (Day 15) — hiểu limitation của MULTI/EXEC để biết khi nào Lua thay thế
- Redis Cluster hash slots (Day 22) — KEYS[] phải cùng slot trên Cluster

---

## 4. Lý thuyết chi tiết

### 4.1. First Principles: Tại Sao Lua Atomic?

```
Redis single-threaded event loop:
  [Event Loop] ---> [Command Queue] ---> [Command Executor] ---> [Response]

  Mọi command chạy trong Command Executor, tuần tự, không preemptive.

  EVAL: Command "EVAL script keys[] args[]" đẩy vào queue
        -> Lua VM được khởi chạy trong Command Executor
        -> TẤT CẢ redis.call() chạy đồng bộ trong Lua VM
        -> Không command nào khác được xử lý trong lúc này
        -> Khi Lua VM trả về, event loop tiếp tục
```

**Kết luận**: Lua atomic miễn phí vì Redis không preemptive — không có context switch giữa các command. Nhưng đổi lại, **Lua block mọi thứ khác**. Script 1ms = 1ms không làm được gì khác.

### 4.2. Lua VM Trong Redis

```
Redis 6.x:  Lua 5.1 (vanilla, không JIT compilation)
Redis 7.x:  Lua 5.1 (vẫn là 5.1, không phải LuaJIT)
            Redis 7.4+ có script-cache eviction cho EVAL/EVAL_RO khi có quá nhiều script khác nhau

Điểm quan trọng:
- Lua 5.1 = interpreter, không JIT
- Mỗi redis.call() = context switch Lua VM <-> Redis C code
- Loop trong Lua không tối ưu bằng C code gốc
- redis.call() overhead: ~2-5 microseconds/call
```

```lua
-- Benchmark: 10,000 redis.call() trong Lua
-- Thực tế: ~20-50ms total (2-5us per call)
-- So với 10,000 lần gọi từ client: tiết kiệm 9,999 RTT
-- nhưng vẫn chạy trong main thread
```

### 4.3. EVAL/EVALSHA/SCRIPT Commands

```bash
# EVAL: gửi script body mỗi lần
EVAL "return redis.call('GET', KEYS[1])" 1 mykey
# => +OK / -ERR (syntax error nếu script lỗi)

# SCRIPT LOAD: load script vào cache, trả về SHA1
SCRIPT LOAD "return redis.call('GET', KEYS[1])"
# => "8c360ce72a98e2a24f6b4c25d3e3c6c5c7f0e1a2"

# EVALSHA: chạy script bằng SHA1 (cache hit)
EVALSHA "8c360ce72a98e2a24f6b4c25d3e3c6c5c7f0e1a2" 1 mykey
# => giá trị của mykey

# EVALSHA với script chưa load (cache miss)
EVALSHA "0000000000000000000000000000000000000000" 1 mykey
# => -NOSCRIPT No matching script. Use EVAL.

# => Client phải bắt NOSCRIPT, fallback về EVAL
# => Đây là pattern bắt buộc trong production code

# Kiểm tra script có tồn tại không (không tải về)
SCRIPT EXISTS "8c360ce72a98e2a24f6b4c25d3e3c6c5c7f0e1a2"
# => 1 (tồn tại) hoặc 0 (không tồn tại)

# Xóa toàn bộ script cache
SCRIPT FLUSH
# => OK (thường chỉ dùng khi upgrade major version)

# Kill script đang chạy (nếu chưa viết gì)
SCRIPT KILL
# => OK (chỉ work nếu script chưa gọi write command)
# => -BUSY Script wrote commands (SHUTDOWN NOSAVE là option cuối)
```

### 4.4. KEYS[] vs ARGV[] — Cluster Requirement

```lua
-- KEYS[]: danh sách key names (Redis dùng để route trên Cluster)
-- ARGV[]: arguments thông thường ( không ảnh hưởng routing)

-- ĐÚNG cho Cluster:
EVAL "return redis.call('GET', KEYS[1])" 1 user:123:profile
--                                    ^^ số lượng key = 1

-- SAI cho Cluster (không dùng KEYS[]):
EVAL "return redis.call('GET', 'user:123:profile')" 0
-- Redis không biết script truy cập key nào
-- => CROSSSLOT error trên Cluster

-- Nhiều key:
EVAL "return redis.call('MGET', unpack(KEYS))" 2 key1 key2
-- KEYS[1]=key1, KEYS[2]=key2
-- Tất cả key phải cùng hash slot (dùng hash tag {user}):
-- user:{123}:profile, user:{123}:session  => cùng slot vì {123}
-- user:123:profile, user:456:profile     => khác slot => CROSSSLOT
```

### 4.5. redis.call vs redis.pcall

```lua
-- redis.call: propagate error về client, dừng script
local val = redis.call('GET', 'missing-key')
-- Nếu key không tồn tại, script trả về nil, không error

-- redis.pcall: bắt error, script tiếp tục
local ok, err = redis.pcall('GET', 'missing-key')
if not ok then
    -- err là error message
    return 'error: ' .. err
end

-- Dùng redis.pcall khi:
-- 1. Muốn handle error trong script
-- 2. Muốn graceful fallback
-- 3. Muốn log error trước khi return
-- 4. Command có thể fail vì lý do không lường trước
```

### 4.6. EVAL Flow — Script Cache Diagram

```
Client                           Redis Server
  |                                    |
  |  EVAL "script..." 1 key            |
  |  --------------------------->     |
  |                                    |  [1] Check SHA1 in script cache
  |                                    |     HIT?  -> execute directly
  |                                    |     MISS? -> parse script, compute SHA1,
  |                                    |            store in cache, execute
  |  <script execution>                |
  |  <blocking all other commands>     |
  |                                    |
  |  +result                           |
  |  <-------------------------------  |
  |                                    |
  |  EVALSHA "sha1..." 1 key          |
  |  --------------------------->     |
  |                                    |  [2] SHA1 lookup in cache
  |                                    |     HIT?  -> execute
  |                                    |     MISS? -> return NOSCRIPT
  |                                    |
  |  -NOSCRIPT                         |
  |  <-------------------------------  |
  |                                    |
  |  EVAL "script..." 1 key  <-- fallback|
  |  --------------------------->     |
  |  +result                           |
  |  <-------------------------------  |
```

### 4.7. Deterministic Script Rules

```
Redis 5+: Scripts được replicate bằng command-by-command
(redis.conf: lua-cscript-replicate-commands = yes)

=> Script PHẢI deterministic:
  - Chỉ truy cập key qua KEYS[] (không hardcode key name)
  - Không gọi TIME (non-deterministic, thay đổi mỗi lần)
  - Không gọi RANDOMKEY, RANDOM (non-deterministic)
  - Không dùng math.random (non-deterministic)
  - Không gọi external service (Lua không hỗ trợ HTTP/gRPC)

Redis 7+ nới lỏng: cho phép một số non-deterministic command
(với trade-off trên replica có thể khác kết quả)
=> Vẫn NÊN giữ deterministic để consistency guarantee
```

### 4.8. Long-Running Script & lua-time-limit

```
lua-time-limit default = 5000ms (5 giây)

Script chạy quá lâu:
  Redis kiểm tra thời gian sau mỗi redis.call()
  Nếu vượt lua-time-limit:
    - Script được đánh dấu "interruptible"
    - Sau interruptible, chỉ cho phép:
        SCRIPT KILL (nếu script chưa write)
        SHUTDOWN NOSAVE (nếu script đã write)

Quan trọng: SCRIPT KILL KHÔNG work nếu script đã gọi write command
(vì write có thể đã thay đổi data)
```

### 4.9. Redis Functions (Redis 7+)

Redis Functions khác Lua script ad-hoc ở chỗ: được persist trong RDB/AOF, có name/version, replicate đến replica, có namespace.

```
# Load function library (từ source string)
FUNCTION LOAD "#!lua name=ratelimit_v1\nlocal fn = function(keys, args)\n..."

# Gọi function (không cần SCRIPT LOAD/EVALSHA mỗi lần)
FCALL ratelimit_v1 1 key arg1 arg2
FCALL_RO ratelimit_v1 1 key  -- read-only, an toàn trên replica

# List functions
FUNCTION LIST

# Statistics
FUNCTION STATS

# Dump để backup/deploy
FUNCTION DUMP

# Restore (sau FUNCTION DELETE)
FUNCTION RESTORE dumped_blob

# Delete
FUNCTION DELETE ratelimit_v1
```

**Redis Functions vs Lua Script Ad-hoc**:

| Tiêu chí | Lua Script (EVAL/EVALSHA) | Redis Functions |
|---|---|---|
| Persist trong RDB/AOF | Không (chỉ script text, không context) | Có (library được persist) |
| Versioning | Không | Có (library_name@v1, @v2) |
| Replicate đến replica | Lua text → replica | Library definition → replica |
| Pre-load | SCRIPT LOAD mỗi deploy | FUNCTION LOAD trên startup |
| Namespace | Không | Có (library:func) |
| rollback | Không | FUNCTION DELETE + RESTORE |

### 4.10. Redis Functions Structure

```
#!lua name=inventory_v2
-- Library comment
-- Version: 2.0

local function reserve(keys, args)
    local item_id = keys[1]
    local quantity = tonumber(args[1])
    local order_id = args[2]

    local current = redis.call('GET', keys[1])
    if not current then
        return {err = 'ITEM_NOT_FOUND'}
    end

    current = tonumber(current)
    if current < quantity then
        return {ok = 0, remaining = current}
    end

    redis.call('DECRBY', keys[1], quantity)
    redis.call('HSET', 'orders', order_id, quantity)

    return {ok = 1, remaining = current - quantity}
end

-- Register function
redis.register_function{
    function_name = 'reserve',
    callback = reserve,
    -- Không khai báo 'no-writes' vì function này có DECRBY/HSET.
    -- Dùng flags = {'no-writes'} chỉ cho function read-only.
}
```

### 4.11. Script Replication — Command-by-Command vs Script Text

```
Legacy (Redis < 5): Script được replicate dưới dạng Lua script text.
  Master: [EVAL script] -> Replica nhận [EVAL script] -> execute
  Problem: Replica có thể return kết quả khác master (TIME, RANDOM...)

Redis 5+: Redis mặc định replicate effects theo command stream
  Master: [EVAL script] -> Redis execute, track commands
  -> Replica nhận [GET key], [INCR key], ... (từng command riêng)
  -> Replica execute từng command riêng
```

```
Effect: Command-by-command replication đảm bảo:
  - Replica có thể return kết quả khác master (TIME() khác nhau)
  - Nhưng cuối cùng data state trên replica = master
  - Đây là acceptable trade-off cho script performance

Production rule:
  - Không cần gọi redis.replicate_commands() trên Redis 7+ cho script thông thường.
  - Vẫn giữ script deterministic để dễ debug, replay và tránh khác biệt giữa node.
  - Mọi key mà script truy cập phải được khai báo qua KEYS[] để Cluster route đúng.
```

### 4.12. Monitoring & Debugging Lua Scripts

```bash
# Xem script đang chạy
redis-cli CLIENT LIST | grep cmd=eval

# Xem blocked clients
redis-cli CLIENT LIST type=blocked

# Xem stats của script
redis-cli INFO stats | grep -E 'total_commands|evalsha'

# Xem slowlog (script > slowlog-threshold)
redis-cli SLOWLOG GET 10

# Monitor latency real-time
redis-cli --latency-history

# Xem lua-time-limit
redis-cli CONFIG GET lua-time-limit

# Thay đổi lua-time-limit (tạm thời, restart mất)
redis-cli CONFIG SET lua-time-limit 10000

# Kiểm tra script cache size
redis-cli INFO memory | grep lua
```

### 4.13. Versioning & Deployment Strategy

```
Strategy 1: Blue/Green với Redis Functions
  - Blue: load ratelimit@v1
  - Green: load ratelimit@v2
  - Switch traffic: update config
  - Monitor 15 phút
  - Delete ratelimit@v1

Strategy 2: Incremental Rollout với EVALSHA
  - Deploy code mới (dùng SHA1 mới)
  - SCRIPT LOAD SHA1 mới trên 10% node
  - Monitor error rate
  - Roll out 100% node
  - Không cần SCRIPT FLUSH vì cả v1 và v2 cùng tồn tại

Strategy 3: Canary với Script Parameter
  - Script nhận version parameter: ARGV[last]
  - Logic cũ chạy khi ARGV[last] = "v1"
  - Logic mới chạy khi ARGV[last] = "v2"
  - Switch version bằng config, không redeploy script

Điều không nên làm:
  - SCRIPT FLUSH trong peak hours (cache miss tất cả)
  - Deploy script không SCRIPT LOAD trước (NOSCRIPT on all calls)
  - Hardcode SHA1 trong code mà không có EVAL fallback
```

### 4.14. Script Cache Memory & Server-Side Behavior

```
Script cache là per-process (per Redis server instance):
  - 1 Redis process = 1 script cache
  - Script cache không share giữa các process
  - SCRIPT LOAD trên 1 connection = available cho TẤT CẢ connection
  - Script cache tồn tại trong memory của Redis process

Memory overhead:
  - SHA1 hash: 20 bytes
  - Script bytecode: 1-50KB (tùy script phức tạp)
  - Metadata: ~200 bytes
  - 10 scripts × 50KB = 500KB/server
  => Không đáng kể với Redis memory thông thường

Script cache không có TTL:
  - Cache tồn tại đến khi Redis restart hoặc SCRIPT FLUSH
  - Script vẫn trong cache dù không dùng
  - Đây là intentional: script có thể cần bất cứ lúc nào
```

---

## 5. Trade-off Analysis

| Scenario | Lua Script | MULTI/EXEC | Application Loop |
|---|---|---|---|
| Atomic conditional update | Atomic miễn phí, chạy trong main thread | WATCH: optimistic lock, retry on conflict | N round-trip, race condition |
| Rate limiting đơn giản | 1 round-trip, atomic | Phù hợp nếu logic đơn giản | N/A |
| Long-running business logic | Chặn tất cả command, nguy hiểm | Không block (WATCH không chặn) | N/A |
| Gọi external service | Không làm được | Làm được (multi-step) | Dễ dàng |
| Replication | Script replicated (legacy) hoặc command-by-command | Commands replicated | N/A |
| Cross-key atomic operation | Tất cả key phải cùng slot (Cluster) | CROSSSLOT error | N/A |
| Read-heavy, tolerate stale | N/A | N/A | Read from replica |
| Khi nào chọn | Khi cần atomicity + <=5ms execution | Khi logic đơn giản, có thể conflict | Khi không cần atomicity |

| Tiêu chí | Lua Script Ad-hoc (EVALSHA) | Redis Functions |
|---|---|---|
| Script management | Manual, phải SCRIPT LOAD mỗi deploy | Declarative, versioned |
| Rollback | Khó (phải reload script) | Dễ (FUNCTION DELETE + RESTORE) |
| Testing | Khó unit test | Dễ test (function riêng) |
| Persistence | Không persist trong RDB | Persist trong RDB/AOF |
| Startup time | SCRIPT LOAD trên mỗi Redis process/deploy | FUNCTION LOAD 1 lần khi deploy library |
| Cluster support | Cần all keys cùng slot | Tương tự |
| Khi nào chọn | Library nhỏ, ít thay đổi, legacy code | Library lớn, nhiều team, versioned deploy |

---

## 6. Best Solution & Best Practices

### Khi nào dùng Lua

- **Rate limiter**: atomic, không race condition, latency < 500us
- **Atomic conditional update**: DECR + check + rollback trong 1 script
- **Inventory reservation**: check + reserve + log trong 1 atomic unit
- **Distributed lock safe unlock**: SET NX PX + Lua verify token trước DEL
- **Idempotency check**: SET NX với unique key + Lua logic

### Khi nào KHÔNG dùng Lua

- **Business logic dài**: nên tách thành application-level với transaction
- **Gọi external service**: Lua không có HTTP client, không có network call
- **Heavy CPU computation**: parse JSON, hash large data → chạy ở application layer
- **Aggregation phức tạp**: SORT với custom compare, nên dùng application-level pipeline
- **Script > 5ms**: nếu script thường chạy > 5ms, cân nhắc lại thiết kế

### Anti-patterns

```lua
-- ANTI-PATTERN 1: redis.call trong loop lớn
for i = 1, 1000000 do
    redis.call('INCR', 'counter')
end
-- => 1 triệu redis.call(), block 1 triệu × 3us = 3 giây
-- FIX: dùng bulk command hoặc tách thành pipeline

-- ANTI-PATTERN 2: Hardcode key trong Lua (không qua KEYS[])
EVAL "return redis.call('GET', 'user:123:profile')" 0
-- => CROSSSLOT error trên Cluster, không deterministic

-- ANTI-PATTERN 3: Dùng EVAL thay vì EVALSHA trong hot path
-- => Gửi script body mỗi lần (500B × 10K ops = 5MB/giây bandwidth)

-- ANTI-PATTERN 4: Gọi TIME trong script
local now = redis.call('TIME')  -- non-deterministic, khác nhau trên replica
-- => Replica có thể trả về kết quả khác master

-- ANTI-PATTERN 5: Không handle NOSCRIPT fallback
-- => Khi script cache miss trên replica, crash không graceful
```

### Best Practices Deployment

```bash
# 1. Load script vào cache trên startup (không phải mỗi request)
SCRIPT LOAD "return redis.call('GET', KEYS[1])"
# => Lưu SHA1, dùng EVALSHA cho mọi call

# 2. Với Redis Functions: dùng versioning
FUNCTION LOAD "#!lua name=ratelimit@v2\n..."

# 3. Blue/green deploy Lua script:
#    - Node A: load v1
#    - Node B: load v2
#    - Switch traffic sang B
#    - Delete v1 trên A

# 4. Monitor lua-time-limit:
redis-cli CONFIG GET lua-time-limit
redis-cli CONFIG SET lua-time-limit 10000  # tăng nếu cần (nhưng cân nhắc risk)
```

---

## 7. Performance Considerations

### Số liệu thực tế

```
Baseline (no Lua, direct command):
  SET:     ~10-20 microseconds
  GET:     ~10-15 microseconds
  pipeline 10 commands: ~30-50 microseconds total

Lua script overhead:
  Script parse + SHA1 compute: ~100-500 microseconds (1 lần, khi SCRIPT LOAD)
  Script execution (simple GET): ~15-25 microseconds (tương đương GET thuần)
  redis.call() overhead: ~2-5 microseconds/call
  redis.pcall() overhead: ~3-6 microseconds/call (thêm error handling)

So sánh:
  3 round-trip (GET + DECR + EXPIRE):
    ~3 × 100us (LAN RTT) = 300us + processing time

  Lua script tương đương:
    ~1 × 100us (RTT) + ~50us (script overhead) = 150us
    => Tiết kiệm 50% latency

  10 round-trip → Lua:
    Tiết kiệm ~9 × 100us = ~900us

Limit:
  Lua script > 5ms: bắt đầu ảnh hưởng p99 latency của các request khác
  Lua script > 100ms: gây visible latency spike, có thể trigger timeout
  Lua script > 5000ms (lua-time-limit): bị interrupt, chỉ SCRIPT KILL
```

### Latency Impact on Cluster

```
Script execution time ảnh hưởng khác nhau trên standalone vs cluster:

Standalone:
  Script 5ms = 5ms tất cả clients phải đợi
  QPS = 1/5ms = 200 ops/sec max cho script

Redis Cluster:
  Script chạy trên node chứa hash slot của KEYS[1]
  Các node khác không bị ảnh hưởng
  QPS trên 1 shard = 1/5ms = 200 ops/sec
  Tổng QPS cluster = 200 × số shards

Multi-slot script (sai thiết kế):
  Script truy cập keys ở nhiều slot
  => CROSSSLOT error trên Cluster
  => Phải design lại: tách thành nhiều script hoặc dùng hash tag
```

### Memory Overhead

```
Script cache per Redis process:
  - SHA1 hash: 20 bytes
  - Compiled Lua bytecode: tùy script (simple GET ~1KB, complex script ~10KB)
  - Metadata: ~200 bytes

10 scripts × 10KB bytecode = ~100KB/server-side
=> Không đáng kể

Lua VM overhead khi script chạy:
  - Stack: ~8KB
  - Globals: ~4KB
  Total: ~12KB/script instance
=> Chỉ allocate khi script chạy, deallocate khi xong
```

---

## 8. Production Failure Modes

### Failure Mode 1: Script Timeout Blocking Cluster

**Dấu hiệu**: Redis CPU bình thường nhưng latency tăng đột ngột. `INFO stats` shows `instantaneous_ops_per_sec` giảm nhưng không về 0. `CLIENT LIST` shows nhiều client đang `cmd=eval`.

**Nguyên nhân**: Script chạy quá lâu vì bug (loop lớn) hoặc dữ liệu lớn bất thường.

**Debug**:
```bash
redis-cli INFO stats | grep -E "total_commands|blocked_clients"
redis-cli CLIENT LIST | grep cmd=eval
redis-cli SCRIPT KILL  # nếu script chưa write
redis-cli SHUTDOWN NOSAVE  # last resort nếu script đã write
```

**Phòng tránh**: Luôn benchmark script với dữ liệu max. Set `lua-time-limit` thấp nhất có thể. Monitor script execution time trong application.

### Failure Mode 2: EVALSHA NOSCRIPT Trên Replica Mới Sync

**Dấu hiệu**: Replica mới join cluster, requests tới replica bị `-NOSCRIPT`. Trên master vẫn work.

**Nguyên nhân**: `SCRIPT LOAD` nạp vào script cache của Redis process hiện tại, dùng chung cho mọi connection tới process đó, nhưng cache này không phải dữ liệu keyspace và không được đảm bảo tồn tại qua restart/full resync. Replica mới hoặc node mới có thể chưa có SHA đó.

**Debug**:
```bash
# Trên replica:
redis-cli SCRIPT EXISTS <sha1>
# => 0 (script chưa load)

# Trên master:
redis-cli SCRIPT LOAD "..."
# => SHA1 (re-load để replicate)
```

**Phòng tránh**: Khi dùng cluster-aware client, luôn SCRIPT LOAD trên mỗi node. Hoặc dùng Redis Functions vì library được replicate qua RDB.

### Failure Mode 3: lua-time-limit Quá Ngắn

**Dấu hiệu**: Thường xuyên gặp `BUSY` error khi chạy script hợp lệ. p95/p99 latency spike.

**Nguyên nhân**: Config `lua-time-limit` quá thấp (vd: 100ms) trong khi script cần 200ms.

**Phòng tránh**: Benchmark script với production data size. Set lua-time-limit = 3× p99 execution time của script. Monitor `lua-time-limit` events.

### Failure Mode 4: FUNCTION Conflict Version

**Dấu hiệu**: `FUNCTION LOAD` trả về `-WRONGTYPE Function already exists`. Deploy script mới fail.

**Nguyên nhân**: Load function với cùng tên nhưng code khác. Redis Functions không auto-overwrite.

**Phòng tránh**: FUNCTION DELETE trước khi load version mới. Hoặc dùng versioning: `ratelimit@v1`, `ratelimit@v2`.

---

## 9. Real-world Examples

### GitHub Rate Limiter (Lua)

GitHub dùng Redis Lua script cho rate limiting trên API. Script kiểm tra rate limit key trong Redis, atomic increment và TTL set. Điều đặc biệt: Lua script chạy trên shared Redis cluster, phải đảm bảo:
- Atomic: không có race condition giữa check và increment
- Fast: < 1ms vì chạy trên hot path (hàng triệu calls/ngày)
- Deterministic: chỉ dùng KEYS[], không TIME/RANDOM
- Hash tag: keys có dạng `ratelimit:{user_id}:search` để cùng slot

Implementation pattern:
```lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

redis.call('INCR', key)
redis.call('EXPIRE', key, window)

local current = redis.call('GET', key)
if tonumber(current) > limit then
    return {allowed = false, remaining = 0}
end
return {allowed = true, remaining = limit - current}
```

### Stripe Idempotency Key (Lua)

Stripe dùng Redis + Lua để check idempotency key trước khi xử lý payment. Logic:
1. `SET NX` idempotency key với TTL
2. Nếu SET thành công → process payment
3. Nếu SET fail → check existing result và return

Dùng Lua để atomic check-and-set trong 1 round-trip thay vì 2 (GET + SET) với race condition.

```lua
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local result_ttl = tonumber(ARGV[2])

local set = redis.call('SET', key, 'processing', 'NX', 'EX', ttl)
if not set then
    local existing = redis.call('GET', key)
    return {existing = true, status = existing}
end

-- Simulate payment processing
-- In real code: call payment service
redis.call('SET', key, 'done', 'EX', result_ttl)
return {existing = false, status = 'done'}
```

### Twitter/X Timeline Insert (Lua)

Twitter dùng Lua script để atomic insert tweet vào user timeline (Sorted Set với timestamp là score). Nếu timeline vượt max size → trim. Tất cả trong 1 atomic script:
```lua
local timeline_key = KEYS[1]
local tweet_id = ARGV[1]
local score = tonumber(ARGV[2])
local max_size = tonumber(ARGV[3])

redis.call('ZADD', timeline_key, score, tweet_id)
redis.call('ZREMRANGEBYRANK', timeline_key, 0, -max_size - 1)
return 'OK'
```
Đảm bảo không có duplicate tweet (ZADD không duplicate) và timeline không vượt quota. Đây là pattern rất phổ biến trong social media: fan-out write với bounded size.

### Uber Matching Engine — Geofence Check (Lua)

Uber dùng Lua script để atomic check nhiều geofence conditions cùng lúc. Thay vì 5 round-trips (GET geofence1, GET geofence2, ...), 1 Lua script check tất cả:

```lua
local geofence_keys = KEYS
local lat = tonumber(ARGV[1])
local lon = tonumber(ARGV[2])

local results = {}
for i, key in ipairs(geofence_keys) do
    local fence = redis.call('GET', key)
    if fence then
        -- Simplified: parse and check
        -- Real: parse JSON, check if lat/lon in polygon
        results[key] = 'inside'
    else
        results[key] = 'outside'
    end
end
return results
```

Pattern này: 5 keys × 1 script = 1 RTT thay vì 5 RTT. Với 100K requests/giây, tiết kiệm 400K RTT/giây.

### Shopify Inventory Atomic Reservation

Shopify dùng Lua script để atomic reserve inventory trong flash sale:
```lua
local stock = redis.call('GET', KEYS[1])
if tonumber(stock) >= tonumber(ARGV[1]) then
    redis.call('DECRBY', KEYS[1], ARGV[1])
    redis.call('HSET', 'reservations', ARGV[2], ARGV[1])
    return 1
end
return 0
```
Đảm bảo không oversell ngay cả khi 1000 requests/giây đổ vào. Nếu dùng WATCH, có thể retry 10-20 lần mỗi request → 10K retry/giây → overhead lớn. Lua atomic = 0 retry.

### Cloudflare Rate Limiting (Lua via Redis Modules)

Cloudflare dùng Redis (qua worker) để rate limit ở edge. Lua script chạy tại Redis edge node gần users. Pattern:
- Key = `cf:ratelimit:{ip}:{zone}`
- Lua script check limit với sliding window
- Result trả về Cloudflare edge → decide allow/block

Điểm đặc biệt: script phải cực nhanh (< 100us) vì chạy trên mỗi request đến edge.
- Deterministic: chỉ dùng KEYS[], không TIME

### Stripe Idempotency Key (Lua)

Stripe dùng Redis + Lua để check idempotency key trước khi xử lý payment. Logic:
1. `SET NX` idempotency key với TTL
2. Nếu SET thành công → process payment
3. Nếu SET fail → check existing result và return

Dùng Lua để atomic check-and-set trong 1 round-trip thay vì 2 (GET + SET) với race condition.

### Twitter/X Timeline Insert (Lua)

Twitter dùng Lua script để atomic insert tweet vào user timeline (Sorted Set với timestamp là score). Nếu timeline vượt max size → trim. Tất cả trong 1 atomic script:
```lua
redis.call('ZADD', KEYS[1], score, tweet_id)
redis.call('ZREMRANGEBYRANK', KEYS[1], 0, -max_size - 1)
return 'OK'
```
Đảm bảo không có duplicate tweet (ZADD không duplicate) và timeline không vượt quota.

### Shopify Inventory Atomic Reservation

Shopify dùng Lua script để atomic reserve inventory trong flash sale:
```lua
local stock = redis.call('GET', KEYS[1])
if tonumber(stock) >= tonumber(ARGV[1]) then
    redis.call('DECRBY', KEYS[1], ARGV[1])
    redis.call('HSET', 'reservations', ARGV[2], ARGV[1])
    return 1
end
return 0
```
Đảm bảo không oversell ngay cả khi 1000 requests/giây đổ vào.

---

## 10. Common Pitfalls

1. **EVAL thay vì EVALSHA + SCRIPT LOAD**: Gây lãng phí bandwidth, script không cache. Production code phải dùng EVALSHA.

2. **KEYS hardcode trong Lua**: `redis.call('GET', 'user:123')` trong script thay vì `redis.call('GET', KEYS[1])`. Trên Cluster, Redis không route đúng, gây CROSSSLOT.

3. **Gọi TIME trong Lua**: TIME không deterministic. Trên replica, kết quả khác master → data inconsistency khi replicate command-by-command.

4. **Không handle NOSCRIPT fallback**: Khi script cache miss, client crash hoặc return error. Phải catch NOSCRIPT và gọi EVAL.

5. **redis.call trong loop lớn**: Mỗi redis.call() block main thread. 10 triệu call = 30 giây blocking → Redis unavailable.

6. **lua-time-limit quá ngắn cho complex script**: Set 100ms nhưng script cần 200ms → thường xuyên gặp BUSY error.

7. **Deploy script không version**: Script cache không có lifecycle/versioning rõ ràng. Rollback phụ thuộc application config/SHA đang dùng, dễ lẫn v1/v2 giữa các service.

8. **SCRIPT KILL trên script đã write**: Không work, phải SHUTDOWN NOSAVE → data loss. Phải design script để không write khi có thể fail.

9. **Không test script với production data size**: Script chạy nhanh với test data 100 rows nhưng chậm với production 1 triệu rows → incident khi deploy.

10. **Dùng Lua thay cho aggregation**: Viết Lua script để parse JSON từ Redis, sort, filter → chạy trong main thread với CPU overhead cao. Nên đẩy aggregation về application layer.

---

## 11. Câu hỏi tự kiểm tra

**Câu 1**: Bạn viết Lua script rate limiter. Script chạy trong 8ms. Redis có `lua-time-limit = 5000ms`. Điều gì xảy ra?

- A) Script bị kill sau 5 giây
- B) Script chạy bình thường, không bị kill
- C) Script bị interruptible sau 5 giây, chỉ có SCRIPT KILL được phép
- D) Redis tự động chuyển script sang background thread

**Đáp án**: B. Script chạy 8ms < lua-time-limit (5000ms). Tuy nhiên, nếu script chạy 6 giây, Redis sẽ đánh dấu interruptible và chỉ cho phép SCRIPT KILL (nếu chưa write) hoặc SHUTDOWN NOSAVE (nếu đã write).

---

**Câu 2**: Trên Redis Cluster, bạn chạy:
```
EVAL "return redis.call('MGET', KEYS[1], KEYS[2])" 2 "user:100:profile" "order:200:detail"
```
Script fail với lỗi CROSSSLOT. Tại sao và fix thế nào?

**Đáp án**: `user:100:profile` và `order:200:detail` nằm ở 2 hash slot khác nhau (vì prefix khác nhau). Redis Cluster không cho phép multi-key operation trên các slot khác nhau. Fix: dùng hash tag `{user}:100:profile` và `{user}:100:order-detail` để cùng slot, hoặc tách thành 2 script call riêng.

---

**Câu 3**: Bạn dùng SCRIPT LOAD để preload script vào cache. Trên master chạy OK, nhưng 1 trong 3 replica mới sync báo NOSCRIPT. Giải thích và fix.

**Đáp án**: `SCRIPT LOAD` nạp script vào cache của một Redis process, không phải vào từng connection. Cache này không phải keyspace durable và có thể trống trên replica/node mới sau restart hoặc resync. Fix:
1. Preload script trên TẤT CẢ node mà client có thể gửi `EVALSHA` tới.
2. Luôn catch `NOSCRIPT` và fallback `EVAL`/`SCRIPT LOAD` rồi retry `EVALSHA`.
3. Tránh dynamic script body; truyền biến qua `ARGV[]`.
4. Dùng Redis Functions nếu cần library persist trong RDB/AOF và deploy theo version.

---

**Câu 4**: So sánh Lua script với MULTI/EXEC transaction cho inventory reservation atomic. Khi nào chọn cái nào?

**Đáp án**:
- MULTI/EXEC: Chọn khi logic đơn giản (2-3 commands), có thể chấp nhận retry on WATCH conflict, không cần conditional branching phức tạp. WATCH optimistic lock, không block các command khác.
- Lua script: Chọn khi cần atomic conditional logic (if stock < requested: return error else decrement), khi muốn 1 round-trip thay vì nhiều round-trip, khi không chấp nhận retry (inventory reservation không nên retry blindly). Lua block main thread nhưng đổi lại 100% atomic, không race condition.

---

**Câu 5**: Bạn phát hiện production incident: Lua script gây 500ms latency spike. Nêu 5 bước debug và 3 bước phòng tránh.

**Đáp án**:

Debug:
1. `redis-cli INFO stats | grep blocked_clients` — xem có client bị block
2. `redis-cli CLIENT LIST type=blocked` — xem client đang chờ command nào
3. `redis-cli SCRIPT KILL` — thử kill script đang chạy
4. Check application log — script nào đang chạy, SHA1 là gì
5. Review script code — tìm loop, redis.call() trong loop, hoặc slow command như SORT, SMEMBERS trên large set

Phòng tránh:
1. Benchmark script với max data size trước khi deploy
2. Set `lua-time-limit` phù hợp với p99 execution time
3. Monitor script execution time trong application (log thời gian execution)
4. Dùng `redis-cli --latency-history` để phát hiện latency spike sớm
5. Thiết kế script deterministic, không loop lớn, không redis.call() trong loop

---

**Câu 6**: Bạn cần deploy version mới của Redis Function lên production đang chạy. Các bước an toàn?

**Đáp án**:
1. FUNCTION DUMP trên current deployment (backup)
2. FUNCTION LOAD version mới với tên khác (vd: `ratelimit@v2`)
3. Test FCALL trên một node (not all)
4. Switch application config sang `ratelimit@v2`
5. Monitor 15 phút (latency, error rate)
6. Nếu OK: FUNCTION DELETE `ratelimit@v1`
7. Nếu fail: FUNCTION RESTORE backup, switch config về `@v1`

---

**Câu 7**: Tại sao Redis Functions được persist trong RDB/AOF nhưng Lua script EVAL thuần thì không? Đây là design decision hay bug?

**Đáp án**: Đây là design decision. Lua script EVAL gửi script body từ client mỗi lần → Redis server không biết đây là "function definition" hay "temporary script". Script chỉ tồn tại trong script cache (in-memory) và bị flush khi Redis restart hoặc SCRIPT FLUSH. Redis Functions được declare với metadata (name, version) và được load bằng FUNCTION LOAD → Redis biết đây là persistent function → lưu vào RDB/AOF. Đây là lý do chính để dùng Redis Functions trong production: script tồn tại qua restart và replica sync.
