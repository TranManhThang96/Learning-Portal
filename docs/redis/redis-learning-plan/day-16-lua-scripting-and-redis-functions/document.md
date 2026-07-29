# Day 16: Lua Scripting & Redis Functions — Reference Document

---

## 1. EVAL/EVALSHA/SCRIPT Commands Cheat Sheet

```bash
# ============ EVAL / EVALSHA ============

# EVAL: chạy script ngay, gửi script body mỗi lần
# Syntax: EVAL script numkeys [key ...] [arg ...]
EVAL "return redis.call('GET', KEYS[1])" 1 mykey
EVAL "return redis.call('MGET', unpack(KEYS))" 2 key1 key2

# EVALSHA: chạy script bằng SHA1 hash (cache hit)
# Phải SCRIPT LOAD trước
EVALSHA "8c360ce72a98e2a24f6b4c25d3e3c6c5c7f0e1a2" 1 mykey

# ============ SCRIPT MANAGEMENT ============

# Load script vào cache, trả về SHA1
SCRIPT LOAD "return redis.call('GET', KEYS[1])"
# => "sha1hash123..."

# Kiểm tra script có trong cache không (trả về array)
SCRIPT EXISTS "sha1hash1" "sha1hash2"
# => [1, 0]  (1 = tồn tại, 0 = không)

# Xóa toàn bộ script cache (thường dùng khi upgrade)
SCRIPT FLUSH
# => OK

# Kill script đang chạy (chỉ work nếu script CHƯA gọi write command)
SCRIPT KILL
# => OK

# Debug script (local)
SCRIPT DEBUG YES  # non-blocking
SCRIPT DEBUG NO   # blocking (sync)
```

---

## 2. Redis Functions Commands Cheat Sheet (Redis 7+)

```bash
# ============ FUNCTION LOAD ============

# Load function library từ source string
# Syntax: FUNCTION LOAD lua-source
# Library format: #!lua name=libname@vN [flags]\nfunctions...

FUNCTION LOAD "#!lua name=ratelimit_v1\n\
local fn = function(keys, args)\n\
  local limit = tonumber(args[1])\n\
  local current = redis.call('GET', keys[1]) or '0'\n\
  current = tonumber(current)\n\
  if current >= limit then\n\
    return 0\n\
  end\n\
  redis.call('INCR', keys[1])\n\
  return 1\n\
end\n\
redis.register_function('rate_limit', fn)"

# ============ FCALL / FCALL_RO ============

# FCALL: gọi function (cần quyền write)
FCALL ratelimit_v1 1 ratelimit:user:123 100

# FCALL_RO: gọi function read-only (an toàn trên replica)
FCALL_RO ratelimit_v1 1 ratelimit:user:123

# ============ FUNCTION LIST ============

# List tất cả functions
FUNCTION LIST

# List với pattern
FUNCTION LIST LIBS name=ratelimit*

# List chi tiết
FUNCTION LIST WITHCODE

# ============ FUNCTION STATS ============

# Xem stats của functions đang chạy
FUNCTION STATS
# => {functions: [{name, description, flags, links}]}

# ============ FUNCTION DUMP / RESTORE ============

# Dump tất cả functions (binary blob)
FUNCTION DUMP
# => <binary blob>

# Restore từ dump
# (không có direct RESTORE từ blob, dùng FUNCTION LOAD lại)

# Restore từ library backup
FUNCTION DELETE ratelimit_v1
FUNCTION LOAD "..."  -- load lại từ backup

# ============ FUNCTION DELETE ============

# Xóa library
FUNCTION DELETE ratelimit_v1
# => OK
```

---

## 3. Lua Scripting Cheat Sheet

```lua
-- ============ KEYS[] và ARGV[] ============
-- KEYS[n]: key thứ n (1-indexed trong Lua)
-- ARGV[n]: argument thứ n

local key = KEYS[1]
local quantity = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

-- ============ redis.call vs redis.pcall ============
-- redis.call: propagate error, dừng script
local val = redis.call('GET', key)
-- val = nil nếu key không tồn tại

-- redis.pcall: catch error, script tiếp tục
local ok, err = redis.pcall('GET', key)
if not ok then
    return 'ERROR: ' .. err
end

-- ============ Return types ============
return 'string'
return 123
return nil
return {1, 2, 3}       -- array -> Redis array
return {err = 'msg'}   -- error table

-- ============ Common patterns ============
-- INCR with TTL
local function incr_with_ttl(key, ttl)
    local count = redis.call('INCR', key)
    if count == 1 then
        redis.call('EXPIRE', key, ttl)
    end
    return count
end

-- Conditional DECR (không âm)
local function safe_decr(key, amount)
    local current = tonumber(redis.call('GET', key) or 0)
    if current < amount then
        return {err = 'INSUFFICIENT_STOCK'}
    end
    local new_val = redis.call('DECRBY', key, amount)
    return {ok = 1, remaining = new_val}
end

-- Safe unlock (Lua equivalent of SET NX PX)
local function safe_unlock(lock_key, token)
    if redis.call('GET', lock_key) == token then
        return redis.call('DEL', lock_key)
    end
    return 0
end

-- ============ Unpacking KEYS[] for multi-key ============
-- MGET với KEYS[]
local values = redis.call('MGET', unpack(KEYS))
return values

-- ============ Replication note ============
-- Redis 7+ replicate effects của write script theo command stream.
-- Không cần redis.replicate_commands() cho script thông thường.
```

---

## 4. Lua Snippets Ready-to-Use

### 4.1. Sliding Window Rate Limiter

```lua
-- KEYS[1] = rate limit key (e.g., ratelimit:user:123)
-- ARGV[1] = window size in seconds
-- ARGV[2] = max requests in window
-- ARGV[3] = current timestamp (seconds)
-- Returns: 1 = allowed, 0 = rate limited

local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local window_start = now - window

-- Remove old entries outside window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count requests in window
local current = redis.call('ZCARD', key)

if current < limit then
    redis.call('ZADD', key, now, ARGV[4] or tostring(now))
    redis.call('EXPIRE', key, window + 1)
    return {1, current + 1, limit}
end

return {0, current, limit}
```

### 4.2. Inventory Reservation

```lua
-- KEYS[1] = inventory key (e.g., inventory:SKU001)
-- ARGV[1] = quantity to reserve
-- ARGV[2] = order ID (for audit log)
-- Returns: {ok, remaining} or {err, message}

local inv_key = KEYS[1]
local qty = tonumber(ARGV[1])
local order_id = ARGV[2]

local stock = redis.call('GET', inv_key)
if not stock then
    return {err = 'ITEM_NOT_FOUND'}
end

stock = tonumber(stock)
if stock < qty then
    return {err = 'INSUFFICIENT_STOCK', available = stock, requested = qty}
end

local new_stock = redis.call('DECRBY', inv_key, qty)

-- Log reservation for audit
redis.call('HSET', 'reservations', order_id, qty .. ':' .. new_stock)

return {ok = 1, remaining = new_stock, reserved = qty}
```

### 4.3. Safe Unlock (Distributed Lock)

```lua
-- KEYS[1] = lock key
-- ARGV[1] = lock token (should match value set by SET NX PX)
-- Returns: 1 = unlocked, 0 = not owner (do not delete)

local lock_key = KEYS[1]
local token = ARGV[1]

-- Lua equivalent of: if GET == token then DEL
if redis.call('GET', lock_key) == token then
    return redis.call('DEL', lock_key)
end

return 0
```

### 4.4. Increment with TTL

```lua
-- KEYS[1] = counter key
-- ARGV[1] = TTL in seconds
-- Returns: new count

local key = KEYS[1]
local ttl = tonumber(ARGV[1])

local count = redis.call('INCR', key)

if count == 1 then
    redis.call('EXPIRE', key, ttl)
end

return count
```

### 4.5. Idempotency Key Check-and-Set

```lua
-- KEYS[1] = idempotency key (e.g., idem:payment:abc123)
-- ARGV[1] = operation status: "processing" | "done"
-- ARGV[2] = result (if done)
-- Returns: {new, value} or {existing, value}

local key = KEYS[1]
local status = ARGV[1]
local result = ARGV[2]

local existing = redis.call('GET', key)
if existing then
    return {existing = 1, value = existing}
end

redis.call('SET', key, status, 'EX', 3600)
return {new = 1, value = status}
```

---

## 5. Code Snippets

### 5.1. TypeScript — ioredis defineCommand

```typescript
// src/lib/redis-rate-limiter.ts
import Redis from 'ioredis';

const redis = new Redis({ host: 'localhost', port: 6379 });

// Định nghĩa Lua command như native command
redis.defineCommand('rateLimit', {
  numberOfKeys: 1,
  lua: `
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local current = redis.call('ZCARD', key)
if current < limit then
  redis.call('ZADD', key, now, ARGV[4] or tostring(now))
  redis.call('EXPIRE', key, window + 1)
  return {1, current + 1, limit}
end
return {0, current, limit}
  `,
});

// Type-safe wrapper
async function rateLimit(
  key: string,
  windowSeconds: number,
  maxRequests: number
): Promise<{ allowed: number; current: number; limit: number }> {
  const now = Math.floor(Date.now() / 1000);
  const result = await (redis as any).rateLimit(
    key, windowSeconds, maxRequests, now
  ) as [number, number, number];
  return {
    allowed: result[0],
    current: result[1],
    limit: result[2],
  };
}

// SCRIPT LOAD on startup (production pattern)
async function initScripts() {
  const scriptSha = await redis.script('LOAD', `
    local key = KEYS[1]
    local window = tonumber(ARGV[1])
    local limit = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local window_start = now - window
    redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
    local current = redis.call('ZCARD', key)
    if current < limit then
      redis.call('ZADD', key, now, ARGV[4] or tostring(now))
      redis.call('EXPIRE', key, window + 1)
      return {1, current + 1, limit}
    end
    return {0, current, limit}
  `);
  return scriptSha;
}

// EVALSHA with NOSCRIPT fallback
async function rateLimitEvalsha(
  sha: string,
  key: string,
  window: number,
  limit: number
): Promise<[number, number, number]> {
  const now = Math.floor(Date.now() / 1000);
  try {
    return await redis.evalsha(sha, 1, key, window, limit, now) as [number, number, number];
  } catch (err: any) {
    if (err.message.includes('NOSCRIPT')) {
      const newSha = await initScripts();
      return await redis.evalsha(newSha, 1, key, window, limit, now) as [number, number, number];
    }
    throw err;
  }
}

export { rateLimit, rateLimitEvalsha, initScripts };
```

### 5.2. Go — go-redis Eval/EvalSha + Auto SCRIPT LOAD

```go
// internal/ratelimiter/ratelimiter.go
package ratelimiter

import (
	"context"
	"fmt"
	"math/rand"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	slidingWindowScript = `
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local current = redis.call('ZCARD', key)
if current < limit then
  redis.call('ZADD', key, now, ARGV[4] or tostring(now))
  redis.call('EXPIRE', key, window + 1)
  return {1, current + 1, limit}
end
return {0, current, limit}
`
)

// LuaScript wraps script + SHA1 cache
type LuaScript struct {
	script redis.Script
	sha    string
	loaded bool
}

// NewLuaScript creates and pre-loads script into Redis
func NewLuaScript(ctx context.Context, rdb *redis.Client, scriptBody string) (*LuaScript, error) {
	ls := &LuaScript{
		script: redis.NewScript(scriptBody),
	}

	// SCRIPT LOAD on init
	sha, err := rdb.ScriptLoad(ctx, scriptBody).Result()
	if err != nil {
		return nil, fmt.Errorf("SCRIPT LOAD: %w", err)
	}
	ls.sha = sha
	ls.loaded = true

	return ls, nil
}

// Run executes EVALSHA with NOSCRIPT fallback
func (ls *LuaScript) Run(ctx context.Context, rdb *redis.Client, keys []string, args ...interface{}) *redis.Cmd {
	// Try EVALSHA first (cache hit)
	result, err := rdb.EvalSha(ctx, ls.sha, keys, args...).Result()
	if err == nil {
		return redis.NewCmd(ctx, result)
	}

	// Fallback: check if NOSCRIPT
	if redis.IsNil(err) || (err != nil && err.Error() == "NOSCRIPT No matching script") {
		// Re-load script
		sha, reloadErr := rdb.ScriptLoad(ctx, ls.script.Hash()).Result()
		if reloadErr != nil {
			return redis.NewCmd(ctx, nil, reloadErr)
		}
		ls.sha = sha
		// Retry EVALSHA
		return rdb.EvalSha(ctx, ls.sha, keys, args...)
	}

	return redis.NewCmd(ctx, nil, err)
}

// RateLimiter wraps sliding window rate limiter
type RateLimiter struct {
	script *LuaScript
	rdb    *redis.Client
}

// NewRateLimiter initializes rate limiter with script pre-load
func NewRateLimiter(ctx context.Context, rdb *redis.Client) (*RateLimiter, error) {
	script, err := NewLuaScript(ctx, rdb, slidingWindowScript)
	if err != nil {
		return nil, err
	}
	return &RateLimiter{script: script, rdb: rdb}, nil
}

// RateLimitResult holds rate limit decision
type RateLimitResult struct {
	Allowed  bool
	Current  int64
	Limit    int64
}

// RateLimit executes sliding window rate limit check
func (rl *RateLimiter) RateLimit(ctx context.Context, key string, windowSec, limit int) (*RateLimitResult, error) {
	now := time.Now().Unix()

	result, err := rl.script.Run(ctx, rl.rdb, []string{key}, windowSec, limit, now).Result()
	if err != nil {
		return nil, fmt.Errorf("script run: %w", err)
	}

	arr, ok := result.([]interface{})
	if !ok || len(arr) < 3 {
		return nil, fmt.Errorf("unexpected result: %v", result)
	}

	allowed := arr[0].(int64) == 1
	current, _ := arr[1].(int64)
	limitVal, _ := arr[2].(int64)

	return &RateLimitResult{
		Allowed: allowed,
		Current: current,
		Limit:   limitVal,
	}, nil
}

// Helper: random token generator for distributed lock
func RandomToken() string {
	b := make([]byte, 16)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}
```

### 5.3. Redis Function Library Snippet

```lua
-- inventory_lib.lua
-- Load bằng: FUNCTION LOAD "$(cat inventory_lib.lua)"

#!lua name=inventory_lib@v2
flags={}

-- Reserve inventory atomically
local function reserve(keys, args)
    local inv_key = keys[1]
    local qty = tonumber(args[1])
    local order_id = args[2]

    local stock = redis.call('GET', inv_key)
    if not stock then
        return redis.error_reply('ITEM_NOT_FOUND')
    end

    stock = tonumber(stock)
    if stock < qty then
        return {'err', 'INSUFFICIENT_STOCK', stock}
    end

    local new_stock = redis.call('DECRBY', inv_key, qty)
    redis.call('HSET', 'orders:reservations', order_id, qty .. ':' .. new_stock)

    return {'ok', new_stock}
end

-- Release inventory (refund)
local function release(keys, args)
    local inv_key = keys[1]
    local qty = tonumber(args[1])
    local order_id = args[2]

    redis.call('INCRBY', inv_key, qty)
    redis.call('HDEL', 'orders:reservations', order_id)

    return {'ok', 'RELEASED'}
end

-- Check stock level
local function check(keys, args)
    local inv_key = keys[1]
    local stock = redis.call('GET', inv_key)
    return stock and tonumber(stock) or 0
end

redis.register_function{
    function_name = 'reserve',
    callback = reserve
}

redis.register_function{
    function_name = 'release',
    callback = release
}

redis.register_function{
    function_name = 'check',
    callback = check,
    flags = {'no-writes'}
}
```

---

## 6. Bảng So Sánh Lua vs Functions vs MULTI/EXEC vs Application Loop

| Tiêu chí | Lua EVALSHA | Redis Functions | MULTI/EXEC | Application Loop |
|---|---|---|---|---|
| Atomicity | 100% atomic | 100% atomic | Optimistic lock (WATCH) | Không atomic |
| Round-trip | 1 RTT (sau SCRIPT LOAD) | 1 RTT | N RTT (mỗi command) | N RTT |
| Blocking | Block main thread | Block main thread | Không block | Không block |
| Replicate | Command-by-command | Library persisted | Từng command | N/A |
| Versioning | Không | Có (libname@vN) | Không | Không |
| Rollback | Khó | Dễ (RESTORE) | Tự động (DISCARD) | N/A |
| Error handling | redis.pcall | redis.pcall trong callback | Có (DISCARD) | Try-catch |
| Cross-slot | Không (Cluster) | Không (Cluster) | Không (Cluster) | Có (nhiều call) |
| Persistence | Không (in-memory cache) | Có (RDB/AOF) | Có (commands) | N/A |
| External call | Không | Không | Có | Có |
| Read from replica | Không (always master) | FCALL_RO (replica OK) | Không (always master) | Có |
| Retry on conflict | Phải code thủ công | Phải code thủ công | Tự động (WATCH retry) | Phải code |
| Script management | Manual | Declarative | N/A | N/A |

---

## 7. Production Checklist

```bash
# Pre-deploy checklist cho Lua script
[ ] SCRIPT LOAD trên từng Redis process mà client có thể gọi EVALSHA
[ ] Benchmark script với production max data size
[ ] Set lua-time-limit = 3x p99 execution time
[ ] Monitor script execution time (log SHA1 + duration)
[ ] Script deterministic (chỉ dùng KEYS[], không TIME/RANDOM)
[ ] Handle NOSCRIPT error với EVAL fallback
[ ] Test trên Cluster (CROSSSLOT không xảy ra)
[ ] Không generate dynamic script body; mọi biến runtime đi qua KEYS[]/ARGV[]

# Pre-deploy checklist cho Redis Functions
[ ] FUNCTION DUMP (backup trước)
[ ] FUNCTION LOAD với version trong tên (libname@v2)
[ ] FCALL trên 1 node test trước
[ ] Monitor 15 phút sau khi switch
[ ] FUNCTION DELETE version cũ sau khi stable
```

---

## 8. Links & Resources

- [Redis Lua Scripting Documentation](https://redis.io/docs/interact/programmability/lua-api/)
- [Redis Functions (Libraries)](https://redis.io/docs/interact/programmability/functions/)
- [Redis EVALSHA Documentation](https://redis.io/commands/evalsha/)
- [Redis Script Commands](https://redis.io/commands/?group=scripting)
- [Redis Functions Commands](https://redis.io/commands/?group=function)
- [antirez blog — Redis scripting](http://oldblog.antirez.com/post/redis-and-lua)
- [Redis internals — Lua VM](https://github.com/redis/redis/tree/unstable/src/modules/gendoc.lua)
- [Redis Lua replication design doc](https://github.com/redis/redis/blob/unstable/src/scripting.md)
