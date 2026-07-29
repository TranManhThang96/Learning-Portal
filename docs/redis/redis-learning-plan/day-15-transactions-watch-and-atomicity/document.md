# Day 15: Transactions, WATCH & Atomicity — Reference Document

---

## 1. Command Cheat Sheet

### Transaction Commands

```txt
MULTI
  -- Mark start of transaction. Subsequent commands are queued, not executed.
  -- Returns: +OK

EXEC
  -- Execute all queued commands atomically (serialized in event loop).
  -- Returns: Array of results, or null if WATCH conflict detected.
  -- If any command had syntax error: null (entire transaction cancelled).
  -- If runtime error in command: array with error objects at that position.

DISCARD
  -- Discard all queued commands, exit transaction mode.
  -- Returns: +OK
  -- Only valid before EXEC. After EXEC, has no effect.

WATCH key [key ...]
  -- Mark keys for optimistic locking.
  -- If any watched key is modified between WATCH and EXEC, EXEC returns null.
  -- WATCH is cleared after EXEC (success or null).
  -- Returns: +OK

UNWATCH
  -- Cancel all watched keys for current connection.
  -- Returns: +OK
  -- No need to call if EXEC was already called.
```

### Quick Reference

| Command | RTTs | Atomic | Retry | Rollback |
|---|---|---|---|---|
| Single command (INCR, SETNX) | 1 | Yes (free) | N/A | N/A |
| MULTI/EXEC | 2 | Yes (serialized) | N/A | No |
| WATCH + MULTI/EXEC | 3+ | Yes (serialized + OCC) | Manual | No |
| Lua EVAL | 1 | Yes (full) | N/A | No |
| Pipeline | 1 | No | Safe | No |

---

## 2. Atomic Single Commands

Dùng những command này trước khi nghĩ đến transaction. Đây là cách nhanh nhất và đơn giản nhất để đạt atomicity.

```txt
-- Counter (O(1))
INCR key                    -- atomic increment by 1
INCRBY key 5                -- atomic increment by N
INCRBYFLOAT key 0.5         -- atomic increment by float
DECR key                    -- atomic decrement by 1
DECRBY key 3                -- atomic decrement by N

-- Set-if-not-exists (O(1))
SETNX key value             -- SET if Not eXists; returns 1 if set, 0 if exists
SET key value NX            -- same as SETNX, NX option
SET key value NX PX 30000   -- SET NX with milliseconds expiration

-- Hash field (O(1) per field)
HSETNX key field value      -- HSET if Not eXists; returns 1 if set, 0 if field exists
ZSETNX is not a command; use Lua for conditional sorted set insert

-- Set (O(1) per element)
SADD key member             -- add member; returns 1 if added, 0 if existed (idempotent-like)
SREM key member             -- remove member; returns 1 if removed, 0 if didn't exist

-- String atomic operations
GETDEL key                  -- atomic GET and DELETE; returns value, nil if key missing
GETEX key [EX seconds|PX ms|EXAT timestamp|PXAT ms]  -- GET and set expire in one command

-- List (O(1) per element)
LPUSH key value             -- atomic push to left
RPUSH key value             -- atomic push to right
LPOP key                    -- atomic pop from left
RPOP key                    -- atomic pop from right
```

### Khi nào dùng cái nào

```txt
-- Counter: dùng INCR
INCR pageviews:2024-05-19

-- Idempotency key: dùng SETNX
SETNX idempotency:payment-abc123 "processing" EX 86400

-- Rate limit: dùng INCR + EXPIRE
-- (2 commands nhưng race không critical)
INCR ratelimit:user42
EXPIRE ratelimit:user42 60

-- Lock: dùng SET NX PX
SET lock:resource123 token-uuid PX 30000
```

---

## 3. Code Snippets

### Go — go-redis TxPipeline & Watch

```go
package main

import (
    "context"
    "errors"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

// Watch with retry and exponential backoff
func reserveInventoryWatch(ctx context.Context, rdb *redis.Client, sku, userID string) error {
    const maxRetries = 5

    for attempt := 0; attempt < maxRetries; attempt++ {
        // Exponential backoff: 1ms, 2ms, 4ms, 8ms, 16ms
        if attempt > 0 {
            time.Sleep(time.Duration(1<<uint(attempt)) * time.Millisecond)
        }

        err := rdb.Watch(ctx, func(tx *redis.Tx) error {
            // Read current stock
            stockKey := "inventory:" + sku
            stock, err := tx.Get(ctx, stockKey).Int()
            if err != nil && !errors.Is(err, redis.Nil) {
                return fmt.Errorf("get stock: %w", err)
            }

            if stock <= 0 {
                return errors.New("out of stock")
            }

            // Execute transaction: decrement stock + reserve for user
            reservedKey := "reserved:" + userID
            _, err = tx.TxPipelined(ctx, func(pipe redis.Pipeliner) error {
                pipe.Decr(ctx, stockKey)
                pipe.SAdd(ctx, reservedKey, sku)
                return nil
            })
            return err
        }, "inventory:"+sku) // watched key

        if err == nil {
            return nil // success
        }
        if errors.Is(err, redis.TxFailedErr) {
            // Conflict detected, retry
            continue
        }
        return err // real error
    }
    return errors.New("reservation failed: max retries exceeded")
}

// Simple MULTI/EXEC without WATCH (serialized execution only)
func batchSet(ctx context.Context, rdb *redis.Client, pairs map[string]string) error {
    tx := rdb.TxPipeline()
    for k, v := range pairs {
        tx.Set(ctx, k, v, 0)
    }
    _, err := tx.Exec(ctx)
    return err
}
```

### Go — Lua Script for Inventory

```go
package main

import (
    "context"
    "fmt"

    "github.com/redis/go-redis/v9"
)

var reserveInventoryScript = redis.NewScript(`
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
`)

func reserveInventoryLua(ctx context.Context, rdb *redis.Client, sku, userID string) (int, error) {
    stockKey := "inventory:" + sku
    reservedKey := "reserved:" + userID

    result, err := reserveInventoryScript.Run(ctx, rdb,
        []string{stockKey, reservedKey},
        userID,
    ).Int(ctx)

    if err != nil {
        return -2, fmt.Errorf("lua script error: %w", err)
    }
    return result, nil
    // result: 1=success, 0=out of stock, -1=key not found, -2=error
}
```

### TypeScript — ioredis multi/exec

```typescript
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });

// Watch with retry
async function reserveInventoryWatch(
  redis: Redis,
  sku: string,
  userId: string,
  maxRetries = 5
): Promise<void> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (attempt > 0) {
      // Exponential backoff: 1ms, 2ms, 4ms, 8ms, 16ms
      await new Promise(r => setTimeout(r, 1 << attempt));
    }

    const stockKey = `inventory:${sku}`;
    const reservedKey = `reserved:${userId}`;

    await redis.watch(stockKey);

    try {
      const stock = await redis.get(stockKey);
      if (stock === null || parseInt(stock, 10) <= 0) {
        await redis.unwatch();
        throw new Error('out of stock');
      }

      const multi = redis.multi();
      multi.decr(stockKey);
      multi.sadd(reservedKey, sku);

      const results = await multi.exec();

      // results is null if WATCH conflict detected
      if (results === null) {
        continue; // retry
      }

      // Check for errors in individual commands
      for (const [err, value] of results) {
        if (err) throw new Error(`command failed: ${err.message}`);
      }

      return; // success
    } finally {
      // unwatch if still watching (not in transaction)
      await redis.unwatch();
    }
  }
  throw new Error('reservation failed: max retries exceeded');
}

// Simple MULTI/EXEC (no WATCH)
async function batchSet(redis: Redis, pairs: Record<string, string>): Promise<void> {
  const multi = redis.multi();
  for (const [k, v] of Object.entries(pairs)) {
    multi.set(k, v);
  }
  await multi.exec();
}
```

### TypeScript — node-redis

```typescript
import { createClient } from 'redis';

const client = createClient();

await client.connect();

// MULTI returns a ChainCommander (fluent API)
const multi = client.multi();
multi.set('key1', 'value1');
multi.incr('counter');
const results = await multi.execAsBulk();
// results: [{value: 'OK'}, {value: 42}]

// WATCH in node-redis: use transaction with condition
// Note: node-redis v4 does not have built-in Watch support like ioredis.
// Use Lua script instead for atomic CAS operations.
```

---

## 4. Lua Script So Sánh với WATCH Approach

### WATCH Approach (Application-level CAS)

```lua
-- Pseudo-code, not real Redis Lua
WATCH inventory:sku123
current = GET inventory:sku123
if tonumber(current) > 0 then
  MULTI
  DECR inventory:sku123
  SADD reserved:user42 sku123
  EXEC
  -- May return nil if conflict, must retry
end
```

### Lua Approach (Server-side CAS)

```lua
local stock = redis.call('GET', KEYS[1])
if stock == false then
    return redis.error_reply('KEY_NOT_FOUND')
end
stock = tonumber(stock)
if stock <= 0 then
    return 0  -- out of stock
end
redis.call('DECR', KEYS[1])
redis.call('SADD', KEYS[2], ARGV[1])
return 1  -- success
```

### So sánh

| Aspect | WATCH Approach | Lua Approach |
|---|---|---|
| RTTs | 3+ (WATCH + GET + MULTI + EXEC) | 1 |
| Retry | Application handles | No retry needed (atomic) |
| Hot key contention | Retry storm possible | No contention (single execution) |
| Branching logic | In application | In Lua script |
| Read-your-write | No | Yes |
| Complexity | More code, more failure modes | Single script |
| Cluster | Same-slot only | Same-slot only |
| Debugging | Easier (breakpoints in app) | Harder (Redis Lua debugger) |

---

## 5. Production Checklist

### Trước khi deploy transaction code

- [ ] Không dùng WATCH khi atomic single command đủ (INCR, SETNX, SADD)
- [ ] Retry logic có exponential backoff và max attempts
- [ ] EXEC response được iterate để check per-command errors
- [ ] WATCH conflict (`nil` response) được handle đúng (retry, không treat như success)
- [ ] Không tin Redis có rollback — design compensation logic nếu cần
- [ ] Cluster: tất cả keys trong WATCH cùng hash slot (dùng hash tag `{}`)
- [ ] Queued commands không depend trên giá trị return từ command trước đó trong cùng queue
- [ ] Syntax error (sai command) trong queue cancel cả transaction — handle bằng error recovery
- [ ] Test với concurrent load để phát hiện retry storm

---

## 6. Links & References

### Official Redis Documentation
- https://redis.io/docs/manual/transactions/ — Transactions documentation
- https://redis.io/docs/manual/transactions/#watch-command — WATCH command reference
- https://redis.io/docs/interact/programmability/ — Lua scripting

### Blog & Articles
- antirez (Salvatore Sanfilippo), "Redis persistence internals" — explains single-threaded atomicity
- "Redis transactions are not what you think" — clarifies no-rollback behavior
- Shopify Engineering Blog — "Buying at Scale" (discusses inventory Lua vs WATCH)
- Stripe Engineering Blog — idempotency keys pattern (SETNX)

### Redis Source (for curious engineers)
- `src/server.c` — `multiCommand`, `execCommand`, `discardCommand`
- `src/multi.c` — transaction state machine
- `src/db.c` — `watchForKey` (dirty flag mechanism)
- `src/eval.c` — Lua scripting internals

### Commands Reference

```txt
-- Quick test in redis-cli
MULTI
GET mykey
INCR mykey
EXEC   -- returns [value_before, value_after]

-- Syntax error cancels transaction
MULTI
SET a 1
FOO bar
EXEC   -- returns null

-- Runtime error doesn't cancel others
SET strkey "hello"
MULTI
SET numkey 42
INCR strkey   -- WRONGTYPE error here
INCR numkey   -- still executes
EXEC   -- returns [OK, error, 43]
```
