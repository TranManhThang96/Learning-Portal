# Day 15: Transactions, WATCH & Atomicity

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Phân biệt được atomic single command (INCR, SETNX) vs MULTI/EXEC vs Lua scripting — biết chính xác khi nào dùng cái nào.
- Implement được optimistic locking bằng WATCH để giải quyết race condition trên multi-key mà không gây contention cao.
- Tránh được 4 transaction failure modes phổ biến: no-rollback, runtime error bị bỏ qua, syntax error cancel cả transaction, read-your-write không tồn tại trong queued commands.
- Phân tích được retry storm scenario khi WATCH trên hot key và đề xuất switch sang Lua hoặc atomic single command.
- So sánh được Redis atomicity model với database ACID transaction — hiểu khi nào trade-off hợp lý.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Team tin Redis có rollback — mất 5K USD inventory

Một e-commerce team dùng MULTI/EXEC để reserve inventory:

```txt
MULTI
  GET inventory:sku123          -- current: 10
  DECR inventory:sku123          -- want: 9
  SADD reserved:user42 sku123
EXEC
```

Sau khi DECR thành công (còn 9), một microservice khác call `HSET order:9999 qty 2` — lỗi syntax (HSET trên String key). Toàn bộ transaction bị cancel, inventory vẫn là 10 nhưng order đã được tạo. User nhận confirmation email nhưng inventory không trừ. Kết quả: oversell 5K USD inventory.

Root cause: Team assumption rằng Redis transaction có rollback như database transaction. **Redis transaction KHÔNG có rollback.** Syntax error trong queue cancel toàn bộ; runtime error thì các command khác vẫn chạy nhưng không có undo.

### Incident 2: WATCH retry loop vô hạn trên hot key — latency p99 tăng 50x

Một rate limiter dùng WATCH + MULTI/EXEC:

```txt
WATCH ratelimit:user42
current = GET ratelimit:user42
if current < 100:
  MULTI
    INCR ratelimit:user42
  EXEC
```

Hot key này được watch bởi 500 concurrent requests. Mỗi WATCH thành công rồi 499 request khác modify → EXEC trả nil → retry. Retry không có exponential backoff, không có max attempts. 500 goroutines retry đồng thời → retry storm → Redis CPU spike → latency p99 tăng từ 2ms lên 100ms.

Root cause: WATCH trên hot key với contention cao tạo ra retry storm. Giải pháp đúng: dùng INCR (atomic single command) hoặc Lua script.

### Incident 3: DECR thay cho WATCH+SET — tiết kiệm 95% latency

Trước khi biết atomic single command, một dev viết:

```txt
WATCH counter
val = GET counter
MULTI
  SET counter (val + 1)
EXEC
```

Với 10K ops/sec, latency p99 = 15ms, throughput = 200 ops/sec. Sau khi refactor:

```txt
INCR counter
```

Latency p99 = 0.3ms, throughput = 50K ops/sec trên cùng hardware.

**Bottom line**: Sai lầm phổ biến nhất của senior developer với Redis transactions: dùng WATCH khi không cần, dùng transaction khi atomic single command đủ, và tin rằng Redis có rollback khi thực tế không có.

---

## 3. Kiến thức nền cần có

- Redis single-threaded model, event loop (Day 1)
- Pipelining, command batching, RTT cost (Day 11)
- Connection pool, client retry, exponential backoff (Day 12)
- Key design, TTL (Day 4)

---

## 4. Lý thuyết chi tiết

### 4.1. First Principles: Tại sao Redis Single Command là Atomic miễn phí

Redis chạy trên một event loop đơn luồng. Mọi command được xử lý tuần tự, không có context switch trong quá trình xử lý command.

```txt
Timeline của Redis server:

Thread: [ Event Loop ]
  |
  |--- Command GET foo arrives
  |    -> Acquire lock (implicit via event loop)
  |    -> Read key "foo" from memory
  |    -> Serialize response
  |    -> Release lock
  |    [ atomic: no other command runs during this window ]
  |
  |--- Command SET bar 123 arrives
  |    -> ...

No preemption possible: một command đang chạy thì toàn bộ Redis đợi.
```

**Điều này có nghĩa**: Bất kỳ single command nào cũng atomic miễn phí. `INCR`, `SETNX`, `HSETNX`, `SADD`, `LPUSH` — không cần transaction, không cần lock, không cần WATCH.

Ngược lại, khi bạn cần **nhiều hơn một command** atomic với nhau, bạn cần can thiệp thủ công. Đó là lúc MULTI/EXEC hoặc Lua xuất hiện.

### 4.2. MULTI/EXEC Internals

#### Command Flow

```txt
Client                          Redis Server
  |                                   |
  |--- MULTI ------------------------>|
  |    (server returns: +OK)          |
  |    (server state: multi mode)     |
  |                                   |
  |--- GET foo ---------------------->|
  |    (queued, not executed)         |
  |--- INCR counter ----------------->|
  |    (queued, not executed)         |
  |--- SET bar 42 ------------------->|
  |    (queued, not executed)        |
  |                                   |
  |--- EXEC ------------------------->|
  |    [Server executes all queued]   |
  |                                   |
  |<---- 3-element array response ----|
  |    [value1, integer2, +OK]       |
  |                                   |

Timeline inside Redis during EXEC:
  for each queued command:
      execute()
  return all results as array
```

**Cơ chế quan trọng**: Commands được **queue** trong Redis server (không phải buffer ở client). Khi EXEC được gọi, Redis execute toàn bộ queue **serially** trong event loop. Đây là lý do MULTI/EXEC đảm bảo serialized execution mà không cần lock.

#### DISCARD

```txt
Client                          Redis Server
  |                                   |
  |--- MULTI ------------------------>|
  |--- GET foo ----------------------->|
  |--- INCR bar --------------------->|
  |                                   |
  |--- DISCARD ---------------------->|
  |    (queue cleared)                |
  |    (state: back to normal)        |
  |                                   |
  |--- GET foo ----------------------->|  <- normal command
```

DISCARD chỉ có tác dụng khi gọi **trước** EXEC. Sau EXEC, transaction đã kết thúc, DISCARD không có hiệu lực.

#### WATCH: Optimistic Locking

WATCH đăng ký một "dirty flag" trên specified keys. Nếu bất kỳ key nào bị modify (bởi client khác hoặc cùng connection) **giữa WATCH và EXEC**, EXEC sẽ return `nil` (null array) — báo hiệu transaction aborted.

```txt
┌─────────────────────────────────────────────────────────────┐
│                  WATCH + MULTI/EXEC Flow                    │
│                                                             │
│  Connection A                       Connection B            │
│      |                                  |                   │
│  WATCH key1,key2                       |                   │
│      |                                  |                   │
│  [WATCHED] keys registered              |                   │
│      |                                  |                   │
│  GET key1 (local) = 10                  |                   │
│      |                                  |                   │
│      |          [ key1 is modified ]    |                   │
│      |          SET key1 99              |                   │
│      |                                  |                   │
│  MULTI                                  |                   │
│  INCR key1                              |                   │
│  EXEC                                   |                   │
│      |                                  |                   │
│  [nil returned - conflict detected]     |                   │
│  A's transaction aborted                 |                   │
│                                                             │
│  Redis internal:                                            │
│    - WATCH stores watched-keys set                          │
│    - Each key modification sets a "dirty" flag              │
│    - EXEC checks dirty flags before running queue           │
│    - If dirty: return nil (not an error!)                   │
│    - If clean: execute queue, return results               │
└─────────────────────────────────────────────────────────────┘
```

#### WATCH Semantics chi tiết

- WATCH chỉ có hiệu lực cho **một transaction duy nhất**. Sau EXEC (thành công hoặc nil), tất cả watched keys được unwatched tự động.
- Nếu EXEC trả nil (conflict), connection vẫn ở trạng thái bình thường — không có "broken state".
- WATCH có thể đặt trên nhiều keys khác nhau bằng `WATCH key1 key2 key3`.
- `UNWATCH` hủy tất cả watched keys mà không cần EXEC.

```txt
WATCH flow chi tiết:
  WATCH key1
  local_val1 = GET key1
  local_val2 = GET key2
  ... ( tính toán local )
  MULTI
  SET key1 new_val1
  SET key2 new_val2
  EXEC
    -> If key1 or key2 modified since WATCH: return nil
    -> Else: execute atomically, return results
```

### 4.3. WATCH vs DB SERIALIZABLE Isolation

| Aspect | Redis WATCH | DB SERIALIZABLE |
|---|---|---|
| Mechanism | Optimistic (detect conflict) | Pessimistic (prevent conflict) |
| Blocking | Non-blocking, return nil on conflict | Block other transactions |
| Retry | Application must retry manually | Automatic |
| Overhead | Low when contention low | High when contention high |
| Conflict detection | At EXEC time only | Continuously |
| Correctness guarantee | Depends on retry logic | Strong (by preventing conflicts) |

WATCH không phải là "Serializable" như database. WATCH chỉ detect conflict tại thời điểm EXEC. Nếu 2 transactions cùng đọc giá trị X, cả hai đều tính toán, cả hai WATCH cùng key — một trong hai sẽ bị abort tại EXEC. Đây là optimistic concurrency control (OCC), không phải pessimistic locking.

### 4.4. Atomic Single Command vs MULTI/EXEC vs Lua

```txt
Atomic Single Command:
  INCR counter
  -> 1 RTT, atomic, no queue overhead
  -> Use for: simple increment, set-if-not-exists

MULTI/EXEC:
  MULTI
  GET key1
  INCR key2
  EXEC
  -> 2 RTT minimum (MULTI + EXEC), queue on server
  -> Use for: multiple commands, same-connection atomicity

WATCH + MULTI/EXEC:
  WATCH key1
  GET key1
  MULTI
  SET key1 newval
  EXEC
  -> 3+ RTT, optimistic, retry on conflict
  -> Use for: check-then-act on shared keys

Lua Script:
  EVAL "return redis.call('INCR', KEYS[1])" 1 counter
  -> 1 RTT, fully atomic, complex logic
  -> Use for: multi-key atomic with branching logic
```

### 4.5. Transaction Limitations (Chi tiết)

#### Không có Rollback

Đây là misconception phổ biến và nguy hiểm nhất.

```txt
MULTI
  SET balance:user42 1000
  DECRBY balance:user42 500   -- executes, balance = 500
  HSET order:9999 item "X"    -- ERROR: wrong type (order:9999 is String)
EXEC

-- Result:
-- balance:user42 = 500 (DECRBY đã chạy, không undo!)
-- order:9999 không được SET
-- Không có error trả về ở vị trí command thứ 3
-- Chỉ có queued command error được report trong EXEC response
```

Trong EXEC response array, mỗi command trả về kết quả riêng. Nếu command thứ 3 lỗi, response sẽ là:

```txt
[OK, 500, error_object, ...]
```

Response vẫn là array (không phải error thrown), nên code phải check từng element.

#### Runtime Error trong EXEC

```txt
MULTI
  SET count 10
  LPUSH list_key "value"   -- list_key is String, LPUSH fails at runtime
  INCR count
EXEC

-- count bị SET = "10" (string)
-- LPUSH fails: WRONGTYPE
-- INCR count executes: count = 11 (INCR convert "10" -> 11)

-- EXEC returns: [OK, error, 11]
-- Application must iterate response array to detect errors
```

Command lỗi runtime không cancel các command còn lại. Đây là design decision của Redis: "best effort" execution.

#### Syntax Error trong Queue

```txt
MULTI
  SET key value
  NONEXISTENT_CMD param        -- syntax error
  INCR counter
EXEC

-- Result: entire transaction cancelled
-- Response: null (no array returned)
-- Server logs: (error) ERR commands out of number range
```

Syntax error (command không tồn tại, sai số parameter) xảy ra tại thời điểm queue. Khi Redis thấy syntax error, nó cancel toàn bộ transaction. Đây là behavior khác hoàn toàn với runtime error.

#### No Read-Your-Write trong Same Transaction

```txt
MULTI
  SET mykey 42
  GET mykey           -- this queues GET, does NOT return 42 to client
EXEC
-- Response: [OK, 42]

Client sees:          -- nothing in between MULTI and EXEC
-- After EXEC: full response array [OK, 42]
```

Trong queued mode, client không nhận response ngay lập tức. `GET mykey` sau `SET mykey` trong cùng transaction sẽ trả về giá trị mới (42) trong EXEC response, nhưng client không thể dùng giá trị này để quyết định thêm command nào vào queue.

### 4.6. Cluster Limitation: WATCH Cross-Slot

```txt
Redis Cluster:
  Key "user:42:balance"  -> slot 1234  (node A)
  Key "user:42:orders"  -> slot 5678  (node B)

WATCH user:42:balance user:42:orders
  -> ERROR: CROSSSLOT Keys in request
```

WATCH chỉ hoạt động khi tất cả watched keys nằm trên **cùng một hash slot**. Trong Cluster, điều này yêu cầu tất cả keys phải có cùng hash tag (dùng `{}` trong key):

```txt
Key "user:{42}:balance" -> hash tag = "42"
Key "user:{42}:orders"  -> hash tag = "42"
-> Same slot -> WATCH works
```

Đây là limitation quan trọng khi design data model cho Cluster.

---

## 5. Trade-off Analysis

### WATCH vs Lua Script

| Criteria | WATCH + MULTI/EXEC | Lua Script |
|---|---|---|
| Atomicity | Serialized execution (server-side) | Fully atomic (single event-loop step) |
| Retry logic | Manual by application | Automatic |
| Contention behavior | Retry storm possible on hot keys | No retry; execute or fail |
| Logic complexity | Supports branching in application | Supports branching inside script |
| Read-your-write | No (queued commands don't return) | Yes (script sees own writes) |
| Latency | 2-4 RTTs | 1 RTT |
| Hot key impact | Severe (retry storm) | Minimal (single execution) |
| Cluster support | Only same-slot keys | Only same-slot keys |
| Error handling | Per-command error in response array | Script return value / error |
| Best for | Low contention, simple read-check-write | High contention or complex logic |

### Transaction vs Pipeline

| Criteria | MULTI/EXEC Transaction | Pipeline |
|---|---|---|
| Atomicity | Yes (serialized) | No (individual commands) |
| RTT reduction | Yes (batches commands) | Yes (batches commands) |
| Rollback | No | No |
| Conditional logic | At application layer | At application layer |
| Retry behavior | Must retry on WATCH conflict | Safe to retry any command |
| Correctness guarantee | Depends on WATCH usage | None (application responsibility) |
| Use when | Need serialized execution | Need throughput, not atomicity |

### Atomic Single Command vs Application-Level Lock

| Criteria | Atomic Single Command | Application-Level Lock |
|---|---|---|
| Example | INCR, SETNX | SET NX + PX + token |
| Complexity | Trivial | Medium (token management) |
| Blocking | None (optimistic) | Yes (pessimistic) |
| Latency | ~0.1-0.3ms | ~1-5ms |
| Throughput | Very high | Lower (lock contention) |
| Rollback | N/A | N/A |
| Distributed | Yes (Redis is single-threaded) | Yes (with Redlock or similar) |
| Best for | Counters, idempotency keys | Complex multi-step critical sections |

### Redis Atomicity vs DB ACID Transaction

| Criteria | Redis (WATCH/Lua) | DB ACID Transaction |
|---|---|---|
| Atomicity | Single command or script | Full atomicity |
| Consistency | Eventual (no foreign key, no schema) | Strong (constraints, triggers) |
| Isolation | None for single commands; OCC for WATCH | Full isolation levels (READ COMMITTED to SERIALIZABLE) |
| Durability | Optional (AOF/RDB) | Required (redo log, commit) |
| Rollback | No | Yes |
| Roll-forward on failure | No | Yes (redo log) |
| Read-your-write | Yes (in Lua); No (in WATCH) | Yes (by default) |
| Nested transactions | No | Yes (savepoints) |
| Recovery | Application-level | Automatic (DB engine) |
| Correctness guarantee | Application responsibility | DB engine responsibility |
| Best for | Idempotent ops, counters, simple CAS | Financial transactions, inventory with constraints |

---

## 6. Best Solution & Best Practices

### Decision Tree

```txt
Bạn cần atomicity?
  |
  Yes -> Chỉ một command?          -> Dùng atomic single command
  |       (INCR, SETNX, HSETNX, SADD, GETDEL, etc.)
  |
  |    -> Nhiều commands?
  |         |
  |         Cần conditional logic?
  |           (if stock > 0 then reserve)
  |           |
  |           Yes -> Contention cao?
  |                    (> 10% retry rate hoặc hot key)
  |                    |
  |                    Yes -> Dùng Lua script
  |                    |
  |                    No  -> WATCH + MULTI/EXEC với retry có backoff
  |
  |         Chỉ cần serialized execution?
  |         (không cần conditional)
  |           -> MULTI/EXEC (không cần WATCH)
  |
  No -> Pipeline (batching for throughput)
```

### Priority: Atomic Single Commands First

Luôn ưu tiên atomic single command trước. Nếu không đủ, mới xem xét WATCH hoặc Lua.

**Những command atomic single command cần nhớ**:

```txt
INCR / INCRBY / INCRBYFLOAT     -- atomic increment
DECR / DECRBY                    -- atomic decrement
SETNX / SET key value NX         -- set if not exists
HSETNX / ZSETNX / SSETNX         -- set field/member if not exists
SADD                            -- add to set (idempotent-like)
GETDEL                          -- atomic get-and-delete
GETEX                           -- atomic get with expire
LPUSH / RPUSH (single element)  -- atomic push
```

### WATCH Best Practices

```go
// ✅ Đúng: retry có limit và backoff
func reserveWithWatch(ctx context.Context, rdb *redis.Client, userID, sku string) error {
    const maxRetries = 5
    for i := 0; i < maxRetries; i++ {
        // Backoff: 1ms, 2ms, 4ms, 8ms, 16ms
        if i > 0 {
            time.Sleep(time.Duration(1<<uint(i)) * time.Millisecond)
        }

        err := rdb.Watch(ctx, func(tx *redis.Tx) error {
            stock, err := tx.Get(ctx, "inventory:"+sku).Int()
            if err != nil && err != redis.Nil {
                return err
            }
            if stock <= 0 {
                return errors.New("out of stock")
            }

            _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
                pipe.Decr(ctx, "inventory:"+sku)
                pipe.SAdd(ctx, "reserved:"+userID, sku)
                return nil
            })
            return err
        }, "inventory:"+sku)

        if err == nil {
            return nil // success
        }
        if err == redis.TxFailedErr {
            continue // retry
        }
        return err // real error
    }
    return errors.New("max retries exceeded")
}
```

### Lua Script Best Practices

```lua
-- ✅ Atomic inventory reservation (returns 1=success, 0=out-of-stock, -1=error)
local stock = redis.call('GET', KEYS[1])
if stock == false then
    return -1
end
stock = tonumber(stock)
if stock <= 0 then
    return 0
end
redis.call('DECR', KEYS[1])
redis.call('SADD', KEYS[2], ARGV[1])
return 1
```

### Anti-Patterns

1. **WATCH trong long transaction**: WATCH chỉ sống qua EXEC. Nếu tính toán local mất 500ms, watched key có thể bị stale.
2. **Retry không có max attempts**: Retry vô hạn trên hot key = retry storm.
3. **WATCH trên cross-slot keys**: Sẽ lỗi ở Cluster.
4. **Tin Redis có rollback**: Không có. Phải handle error hoặc design để không cần rollback.
5. **Dùng WATCH khi không cần**: Nếu chỉ cần serialized execution (không conditional), dùng MULTI/EXEC không cần WATCH.
6. **Queue response không check**: Khi EXEC trả array, phải iterate để check error ở từng command.

---

## 7. Performance Considerations

### Latency Numbers

| Operation | Typical Latency | Notes |
|---|---|---|
| INCR (atomic single) | 0.05-0.3ms | p50=0.08ms, p99=0.3ms (LAN) |
| MULTI/EXEC (2 commands) | 0.2-0.6ms | Overhead queue + exec barrier |
| WATCH + GET + EXEC | 0.3-1ms | 2-3 RTTs |
| WATCH conflict + retry | 0.5-2ms/attempt | Adds per-retry overhead |
| Lua script (simple) | 0.1-0.5ms | 1 RTT, ~10-50μs script execution |
| Lua script (complex) | 0.5-5ms | Depends on Lua logic complexity |

### WATCH Retry Storm Impact

```txt
Hot key contention analysis:

Scenario: 100 concurrent requests, all WATCH same key
Request arrival: uniform over 1 second

Without retry backoff:
  Round 1: 100 WATCH -> 1 success, 99 conflict -> retry
  Round 2: 99 WATCH -> 1 success, 98 conflict -> retry
  Round 3: 98 WATCH -> ...
  Total attempts: ~5000 (sum 100..1 = 4950)
  Redis load: 50x normal

With exponential backoff (1ms, 2ms, 4ms...):
  Round 1: 100 WATCH -> 1 success, 99 wait 1ms -> retry
  Round 2: 99 WATCH -> 1 success, 98 wait 2ms -> retry
  Total time: ~7 rounds * 4ms = ~28ms
  Redis load: ~5x normal
  p99 latency: ~28ms (last retry batch)

Conclusion:
  - No backoff on hot key: p99 can reach 100-500ms
  - With backoff: p99 typically < 50ms
  - Switch to Lua when retry rate > 20%
```

### MULTI/EXEC Overhead

```txt
Single INCR:     0.08ms (p99)
MULTI+INCR+EXEC: 0.15ms (p99)  -- 87% overhead vs single

Batch of 10 commands with pipeline:  0.5ms
Batch of 10 commands with MULTI/EXEC: 0.8ms  -- 60% overhead

MULTI/EXEC is slower than pipeline because:
  1. Server must maintain per-connection queue state
  2. EXEC barrier adds ~0.05ms overhead
  3. All commands still serialized (like pipeline)
```

### Cluster WATCH Failure

```txt
Cross-slot WATCH:
  Response: (error) ERR WATCH against multiple keys in cluster is not allowed
  Application crashes if not handling this error
  -> Always check CLUSTER KEYSLOT before WATCH in Cluster mode
```

---

## 8. Production Failure Modes

### Failure Mode 1: WATCH Retry Storm

**Dấu hiệu nhận biết**:
- Redis CPU tăng đột ngột mà không có traffic spike thực sự
- Latency p99 tăng 10-100x trong khi p50 không đổi
- `INFO commandstats` cho thấy WATCH/EXEC spike
- Application logs có nhiều "transaction conflict" messages

**Nguyên nhân**:
- WATCH trên hot key với retry không có backoff
- Nhiều concurrent requests cùng watch

**Debug**:
```bash
redis-cli --latency-history  # check latency spikes
redis-cli INFO commandstats | grep -i watch
redis-cli CLIENT LIST | grep addr  # check connection count
```

**Fix**:
- Switch sang Lua script cho hot key
- Thêm exponential backoff vào retry logic
- Giới hạn max retries (5-10)
- Consider atomic single command (INCR) thay vì WATCH

### Failure Mode 2: EXEC Return Nil Không Được Handle

**Dấu hiệu nhận biết**:
- Application tiếp tục xử lý như thể transaction thành công
- Data inconsistency xuất hiện sau vài giờ
- Không có error logs

**Nguyên nhân**:
```go
// ❌ Bug: không check nil response
rdb.Watch(ctx, func(tx *redis.Tx) error {
    val, _ := tx.Get(ctx, "key").Int()  // val = 0 if nil
    tx.Pipelined(ctx, func(pipe redis.Pipeliner) error {
        pipe.Set(ctx, "key", val+1, 0)
        return nil
    })
    return nil
})
// nil response from EXEC = val = 0, application continues as success
```

**Debug**:
- Code review transaction handlers
- Add assertion that EXEC result is not nil

**Fix**:
```go
// ✅ Đúng: handle nil explicitly
err := rdb.Watch(ctx, func(tx *redis.Tx) error {
    val, err := tx.Get(ctx, "key").Int()
    if err != nil {
        return err
    }
    _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
        pipe.Set(ctx, "key", val+1, 0)
        return nil
    })
    return err
}, "key")

if err == redis.TxFailedErr {
    return fmt.Errorf("transaction conflict after retries")
}
if err != nil {
    return fmt.Errorf("redis error: %w", err)
}
```

### Failure Mode 3: Runtime Error Bị Bỏ Qua

**Dấu hiệu nhận biết**:
- Một phần của transaction chạy, phần khác không
- Data trong inconsistent state
- Không có clear error message

**Nguyên nhân**: Code không iterate EXEC response array.

**Fix**:
```go
// ✅ Always check each element in EXEC response
results, err := tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
    pipe.Set(ctx, "key1", "value1", 0)
    pipe.Incr(ctx, "key2")
    return nil
})
if err != nil {
    return err
}
for i, result := range results {
    if err, ok := result.(redis.Error); ok {
        return fmt.Errorf("command %d failed: %w", i, err)
    }
}
```

### Failure Mode 4: Cluster CROSSSLOT WATCH

**Dấu hiệu nhận biết**:
- Error log: `ERR WATCH against multiple keys in cluster is not allowed`
- Application crash hoặc silent failure
- Chỉ xảy ra sau khi Cluster resharding hoặc key redistribution

**Debug**:
```bash
redis-cli CLUSTER KEYSLOT user:42:balance
redis-cli CLUSTER KEYSLOT user:42:orders
# Nếu khác slot -> CROSSSLOT error sẽ xảy ra
```

**Fix**:
- Dùng hash tag trong key design: `user:{42}:balance`, `user:{42}:orders`
- Hoặc tách thành 2 transactions riêng (nếu acceptable)
- Hoặc switch sang Lua với hash tag tương tự

---

## 9. Real-world Examples

### Shopify: Inventory Reservation

Shopify dùng Redis cho inventory counting tại scale hàng triệu SKUs. Trước đây, họ dùng WATCH cho stock reservation, nhưng gặp retry storm vào Black Friday. Giải pháp: chuyển sang Lua script với atomic DECR + conditional check, giảm retry rate từ 30% xuống <1%.

Tham khảo: Shopify's engineering blog về "Buying at Scale" — họ công khai discuss việc chuyển từ WATCH sang Lua vì contention issues.

### Stripe: Idempotency Keys

Stripe dùng Redis `SETNX` cho idempotency keys — đây là atomic single command, không cần transaction. Mỗi payment request có idempotency key, Stripe dùng `SET key EX 86400 NX` để guarantee rằng chỉ một request được process dù client retry. Đây là pattern dùng atomic single command thay vì transaction.

### GitHub: Rate Limiter

GitHub dùng Redis cho rate limiting across distributed runners. Pattern: atomic `INCR` với `EXPIRE` (2 commands không atomic giữa chúng — nhưng acceptable vì race on expire không critical). Họ không dùng WATCH vì INCR đã đủ atomic và không có conditional logic phức tạp.

### Incident từ Internet: Distributed Lock Bug

Một team implement distributed lock bằng WATCH:

```txt
WATCH lock:resource123
existing = GET lock:resource123
if existing == nil:
  MULTI
    SET lock:resource123 token NX PX 30000
  EXEC
```

Race condition: giữa GET và SET, client khác có thể acquire lock. WATCH sẽ detect conflict, nhưng nếu retry logic không tốt → deadlock.

Sai lầm: dùng WATCH để implement lock trong khi đã có `SET key value NX PX` — atomic single command, không cần WATCH.

---

## 10. Common Pitfalls

1. **Tin Redis transaction có rollback**: Không có. Phải design để không cần rollback hoặc implement application-level compensation.

2. **Không retry khi WATCH conflict**: WATCH trả nil = transaction bị abort. Application phải retry có backoff, không phải treat như success.

3. **WATCH trên cross-slot keys trong Cluster**: Sẽ fail với CROSSSLOT error. Luôn dùng hash tag.

4. **Không check queued command errors**: EXEC trả array. Phải iterate để detect runtime errors ở từng command.

5. **Dùng WATCH khi atomic single command đủ**: INCR thay vì WATCH+GET+SET = 95% latency reduction.

6. **Dùng WATCH trên hot key**: Retry storm là vấn đề thực tế. Switch sang Lua khi retry rate > 20%.

7. **Queued commands không có read-your-write**: `GET` sau `SET` trong queue trả về giá trị mới, nhưng client không thể use giá trị đó để quyết định command tiếp theo trong cùng transaction.

8. **WATCH trong long-lived connection bị stale**: WATCH chỉ sống qua EXEC. Tính toán local quá lâu → watched keys đã bị modify nhiều lần.

9. **Không handle EXEC return nil khi tất cả watched keys bị modify**: Nhầm lẫn nil với empty array `[]`. WATCH conflict trả nil (null), không phải `[]`.

10. **Syntax error cancel cả transaction**: `NONEXISTENT_CMD` trong queue → toàn bộ transaction bị cancel. Không phải chỉ command đó fail.

---

## 11. Câu hỏi tự kiểm tra

### Câu 1
Bạn cần implement một rate limiter: cho phép user gọi API tối đa 100 lần mỗi phút. User ID là key. Approach nào tốt nhất?

A. WATCH + MULTI/EXEC
B. Lua script
C. SETNX với EXPIRE
D. INCR + EXPIRE (2 commands)

Đáp án: D. `INCR` là atomic single command. `INCR rate:{user} 1` + `EXPIRE rate:{user} 60` — race giữa INCR và EXPIRE không gây vấn đề vì nếu EXPIRE fail, key tự cleanup qua maxmemory eviction. Watch không cần thiết. Lua script được nếu cần guarantee rằng EXPIRE chỉ set khi INCR thành công, nhưng overhead không đáng.

### Câu 2
MULTI/EXEC trả về array `[OK, error{WRONGTYPE}, 42]`. Điều gì xảy ra?

A. Transaction bị cancel hoàn toàn
B. Chỉ command bị lỗi không chạy, các command khác vẫn chạy
C. Tất cả command được chạy, response chứa error object
D. Redis server crash

Đáp án: C. Runtime error (WRONGTYPE) xảy ra trong quá trình EXEC. Command thứ 2 lỗi, nhưng command 1 và 3 vẫn chạy. Đây là "best effort" behavior. Application phải iterate response array để check từng element.

### Câu 3
Trong Cluster, bạn WATCH 2 keys nằm trên 2 hash slots khác nhau. Điều gì xảy ra?

A. WATCH chỉ watch key đầu tiên
B. WATCH succeed, EXEC có thể fail nếu một key thay đổi
C. CROSSSLOT error tại thời điểm WATCH
D. WATCH succeed, nhưng không detect conflict

Đáp án: C. Trong Cluster, WATCH nhiều keys ở các slots khác nhau trả về CROSSSLOT error. WATCH chỉ hoạt động cross-slot khi dùng hash tag `{}` để force cùng slot.

### Câu 4
Tại sao `INCR` an toàn hơn `WATCH + GET + SET` cho counter?

A. INCR dùng ít memory hơn
B. INCR là single command, không có race window giữa GET và SET
C. WATCH không hoạt động trên counters
D. INCR có built-in retry

Đáp án: B. `WATCH + GET + SET` có race window: sau GET, trước SET, client khác có thể modify. INCR là atomic single command, không có race window, latency thấp hơn 10-50x.

### Câu 5
Bạn dùng WATCH để reserve inventory. Retry không có backoff. System có 200 concurrent users cùng reserve 1 item cuối cùng. Điều gì xảy ra?

A. Tất cả 200 requests đều thành công (inventory oversold)
B. Tất cả 200 requests đều fail
C. Retry storm: ~10,000 attempts, latency p99 tăng 50x, CPU spike
D. Redis tự động switch sang Lua

Đáp án: C. Không có backoff, mỗi conflict trigger immediate retry. 200 initial attempts → ~199 conflicts → immediate retry → ~198 conflicts → ... Total attempts = ~20,000 (sum 200..1). Latency p99 có thể tăng 50-100x do contention. Giải pháp: exponential backoff hoặc switch sang Lua.

### Câu 6
Trong Lua script, tại sao read-your-write được đảm bảo mà trong WATCH transaction thì không?

A. Lua script chạy trong event loop, không có context switch
B. WATCH không hỗ trợ GET sau SET trong cùng transaction
C. Lua script dùng lock
D. WATCH chạy trên replica

Đáp án: A. Lua script execute trong Redis event loop như một single atomic unit. `redis.call('SET', ...) ` trước `redis.call('GET', ...)` trong cùng script → GET thấy giá trị vừa SET. WATCH transaction queue commands, không execute, nên client không nhận response cho đến EXEC.

### Câu 7
Khi nào nên chọn Lua script thay vì WATCH?

A. Khi cần rollback khi có lỗi
B. Khi contention cao (> 20% retry rate) HOẶC cần branching logic phức tạp
C. Khi chỉ cần serialized execution không có conditional
D. Khi muốn phân tách read và write

Đáp án: B. Lua script là atomic single unit, không retry (execute hoặc fail ngay). WATCH có retry mechanism nhưng retry storm là vấn đề khi contention cao. Lua phù hợp khi: (1) contention cao, (2) cần branching logic phức tạp mà application layer không handle được, (3) cần read-your-write. MULTI/EXEC (không WATCH) khi chỉ cần serialized execution.
