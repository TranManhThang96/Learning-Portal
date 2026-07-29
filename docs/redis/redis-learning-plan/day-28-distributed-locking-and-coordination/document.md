# Day 28: Distributed Locking & Coordination — Reference Document

---

## 1. Command Reference

### Lock Acquisition & Release

```bash
# ============ ACQUISITION ============

# Safe lock acquisition (atomic: set + NX + TTL in one command)
SET lock:resource <token> NX PX 30000
# Returns: OK if acquired, nil if already held
# PX = milliseconds, EX = seconds

# Lua: safe lock acquisition with auto-extend check
EVAL "
  local existing = redis.call('GET', KEYS[1])
  if existing then
    return 0
  end
  redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
  return 1
" 1 lock:resource <token> <ttl_ms>

# Lua: acquire with TTL extension (for long operations)
EVAL "
  local current = redis.call('GET', KEYS[1])
  if current == false then
    redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
    return 1
  elseif current == ARGV[1] then
    redis.call('PEXPIRE', KEYS[1], ARGV[2])
    return 1
  end
  return 0
" 1 lock:resource <token> <ttl_ms>

# ============ SAFE UNLOCK ============

# WRONG (unsafe): removes any lock
DEL lock:resource

# RIGHT: Lua atomic check-and-delete
EVAL "
  if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
  else
    return 0
  end
" 1 lock:resource <token>
# Returns: 1 if deleted, 0 if not owner

# ============ LOCK EXTEND ============

# Extend TTL only if we still own the lock
EVAL "
  if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
  else
    return 0
  end
" 1 lock:resource <token> <new_ttl_ms>

# ============ LOCK QUERY ============

# Check if lock is held and by whom
GET lock:resource
# Returns: token if held, nil if not

# Check TTL
PTTL lock:resource
# Returns: remaining TTL in ms, -2 if key does not exist

# ============ REDLOCK (5 nodes) ============

# Acquire on single node (repeat for N nodes)
SET lock:resource <token> NX PX 10000

# Release on all nodes (can be parallel)
EVAL "..." 1 lock:resource <token>   # node 1
EVAL "..." 1 lock:resource <token>   # node 2
EVAL "..." 1 lock:resource <token>   # node 3

# Check lock on all nodes
redis-cli -h node1 -p 6379 GET lock:resource
redis-cli -h node2 -p 6379 GET lock:resource
redis-cli -h node3 -p 6379 GET lock:resource
```

---

## 2. Lua Script Library

```lua
-- safe_lock.lua
-- Helper: acquire lock (returns 1=acquired, 0=held)
local function acquire(key, token, ttl_ms)
  local existing = redis.call('GET', key)
  if existing then
    return 0
  end
  redis.call('SET', key, token, 'PX', ttl_ms)
  return 1
end

-- Helper: safe release (returns 1=released, 0=not owner)
local function safe_release(key, token)
  if redis.call('GET', key) == token then
    return redis.call('DEL', key)
  end
  return 0
end

-- Helper: safe extend (returns 1=extended, 0=not owner)
local function safe_extend(key, token, ttl_ms)
  if redis.call('GET', key) == token then
    redis.call('PEXPIRE', key, ttl_ms)
    return 1
  end
  return 0
end
```

```lua
-- atomic_inventory_reservation.lua
-- KEYS[1] = inventory key
-- KEYS[2] = lock key
-- ARGV[1] = lock token
-- ARGV[2] = quantity
-- ARGV[3] = TTL in ms
-- Returns: {ok, remaining} or {err, message}

local lock_key = KEYS[2]
local inv_key = KEYS[1]
local token = ARGV[1]
local qty = tonumber(ARGV[2])
local ttl_ms = tonumber(ARGV[3])

-- Try to acquire lock
local lock_acquired = 0
if redis.call('GET', lock_key) == false then
  redis.call('SET', lock_key, token, 'PX', ttl_ms)
  lock_acquired = 1
end

if lock_acquired == 0 then
  return {'err', 'LOCK_NOT_ACQUIRED'}
end

-- Check and reserve inventory
local stock = redis.call('GET', inv_key)
if stock == false then
  redis.call('DEL', lock_key)
  return {'err', 'ITEM_NOT_FOUND'}
end

stock = tonumber(stock)
if stock < qty then
  redis.call('DEL', lock_key)
  return {'err', 'INSUFFICIENT_STOCK', tostring(stock), tostring(qty)}
end

local new_stock = redis.call('DECRBY', inv_key, qty)

-- Release lock after critical section
redis.call('DEL', lock_key)

return {'ok', tostring(new_stock), tostring(qty)}
```

---

## 3. Go Code Snippets

### 3.1. Complete Distributed Lock Client

```go
// internal/distlock/distlock.go
package distlock

import (
    "context"
    crand "crypto/rand"
    "encoding/hex"
    "errors"
    "fmt"
    mrand "math/rand"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    defaultTTL         = 30 * time.Second
    defaultMaxRetries  = 3
    defaultRetryDelay  = 100 * time.Millisecond
    releaseScript      = `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
    `
    extendScript = `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("PEXPIRE", KEYS[1], ARGV[2])
        else
            return 0
        end
    `
)

var (
    ErrLockNotAcquired = errors.New("lock not acquired after retries")
    ErrNotLockOwner     = errors.New("not lock owner (token mismatch)")
)

// Lock wraps a distributed lock instance
type Lock struct {
    rdb   *redis.Client
    key   string
    token string
    ttl   time.Duration
}

// Config holds lock configuration
type Config struct {
    TTL         time.Duration
    MaxRetries  int
    RetryDelay  time.Duration
    RetryJitter time.Duration // random jitter to avoid thundering herd
}

func DefaultConfig() *Config {
    return &Config{
        TTL:         defaultTTL,
        MaxRetries:  defaultMaxRetries,
        RetryDelay:  defaultRetryDelay,
        RetryJitter: 50 * time.Millisecond,
    }
}

// generateToken creates a cryptographically random token
func generateToken() string {
    b := make([]byte, 16)
    crand.Read(b)
    return hex.EncodeToString(b)
}

// Acquire attempts to acquire the distributed lock with retry
func Acquire(ctx context.Context, rdb *redis.Client, key string, cfg *Config) (*Lock, error) {
    if cfg == nil {
        cfg = DefaultConfig()
    }

    token := generateToken()

    for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
        if attempt > 0 {
            backoff := cfg.RetryDelay * time.Duration(1<<uint(attempt-1))
            if cfg.RetryJitter > 0 {
                jitter := time.Duration(mrand.Int63n(int64(cfg.RetryJitter * 2)))
                backoff += jitter
            }

            select {
            case <-ctx.Done():
                return nil, ctx.Err()
            case <-time.After(backoff):
            }
        }

        acquired, err := rdb.SetNX(ctx, key, token, cfg.TTL).Result()
        if err != nil {
            return nil, fmt.Errorf("redis SetNX: %w", err)
        }

        if acquired {
            return &Lock{
                rdb:   rdb,
                key:   key,
                token: token,
                ttl:   cfg.TTL,
            }, nil
        }
    }

    return nil, ErrLockNotAcquired
}

// AcquireWithValue acquires lock and sets a custom value (not just token)
func AcquireWithValue(ctx context.Context, rdb *redis.Client, key string, value string, ttl time.Duration) (*Lock, error) {
    token := generateToken()
    fullValue := fmt.Sprintf("%s:%s", token, value)

    acquired, err := rdb.SetNX(ctx, key, fullValue, ttl).Result()
    if err != nil {
        return nil, fmt.Errorf("redis SetNX: %w", err)
    }

    if !acquired {
        return nil, ErrLockNotAcquired
    }

    return &Lock{rdb: rdb, key: key, token: token, ttl: ttl}, nil
}

// Release safely releases the lock (only if we still own it)
func (l *Lock) Release(ctx context.Context) error {
    result, err := l.rdb.Eval(ctx, releaseScript, []string{l.key}, l.token).Int64()
    if err != nil {
        return fmt.Errorf("redis Eval (release): %w", err)
    }
    if result == 0 {
        return ErrNotLockOwner // Lock expired or held by another client
    }
    return nil
}

// Extend extends the lock TTL (only if we still own it)
func (l *Lock) Extend(ctx context.Context, ttl time.Duration) error {
    result, err := l.rdb.Eval(ctx, extendScript, []string{l.key}, l.token, ttl.Milliseconds()).Int64()
    if err != nil {
        return fmt.Errorf("redis Eval (extend): %w", err)
    }
    if result == 0 {
        return ErrNotLockOwner // Lock expired or held by another client
    }
    l.ttl = ttl
    return nil
}

// GetToken returns the lock token (useful for debugging)
func (l *Lock) GetToken() string {
    return l.token
}

// IsOwned checks if we still own the lock
func (l *Lock) IsOwned(ctx context.Context) (bool, error) {
    currentToken, err := l.rdb.Get(ctx, l.key).Result()
    if err == redis.Nil {
        return false, nil
    }
    if err != nil {
        return false, err
    }
    return currentToken == l.token, nil
}
```

### 3.2. Redlock Implementation (5 nodes)

```go
// internal/distlock/redlock.go
package distlock

import (
    "context"
    "fmt"
    "strings"
    "time"

    "github.com/redis/go-redis/v9"
)

const (
    redlockQuorumScript = `
        local acquired = 0
        local drift_ms = tonumber(ARGV[1])
        local ttl_ms = tonumber(ARGV[2])
        local start_time = tonumber(ARGV[3])
        local key = KEYS[1]
        local token = ARGV[4]

        for i, node_key in ipairs(KEYS) do
            if i > 1 then  -- skip first key (already acquired)
                local ok = redis.call('SET', node_key, token, 'NX', 'PX', ARGV[2])
                if ok then
                    acquired = acquired + 1
                end
            end
        end

        -- Calculate if lock is valid
        local elapsed_ms = redis.call('TIME')[2]
        elapsed_ms = elapsed_ms - start_time
        local validity_ms = ttl_ms - elapsed_ms - drift_ms

        return {acquired, validity_ms}
    `
)

// RedlockNode represents a single Redis node in the Redlock setup
type RedlockNode struct {
    Addr string
    rdb   *redis.Client
}

// Redlock implements the Redlock algorithm across N Redis nodes
type Redlock struct {
    nodes  []*RedlockNode
    quorum int
}

// NewRedlock creates a Redlock manager with N Redis nodes
func NewRedlock(addrs []string) *Redlock {
    nodes := make([]*RedlockNode, len(addrs))
    for i, addr := range addrs {
        nodes[i] = &RedlockNode{
            Addr: addr,
            rdb:   redis.NewClient(&redis.Options{Addr: addr}),
        }
    }
    return &Redlock{
        nodes:  nodes,
        quorum: len(addrs)/2 + 1,
    }
}

// RedlockConfig holds Redlock configuration
type RedlockConfig struct {
    TTL              time.Duration
    RetryDelay       time.Duration
    RetryCount       int
    DriftFactor      float64 // typically 0.01 (1%)
}

// Acquire attempts to acquire the Redlock
func (r *Redlock) Acquire(ctx context.Context, key string, cfg *RedlockConfig) (*RedlockInstance, error) {
    if cfg == nil {
        cfg = &RedlockConfig{
            TTL:        10 * time.Second,
            RetryDelay: 50 * time.Millisecond,
            RetryCount: 3,
            DriftFactor: 0.01,
        }
    }

    token := generateToken()
    ttlMs := cfg.TTL.Milliseconds()
    driftMs := int64(float64(ttlMs) * cfg.DriftFactor)

    for attempt := 0; attempt <= cfg.RetryCount; attempt++ {
        if attempt > 0 {
            select {
            case <-ctx.Done():
                return nil, ctx.Err()
            case <-time.After(cfg.RetryDelay * time.Duration(1<<uint(attempt-1))):
            }
        }

        acquired := 0
        startTimeMs := time.Now().UnixMilli()
        var failedNodes []string

        // Try to acquire on all nodes
        for _, node := range r.nodes {
            acquiredNode, err := node.rdb.SetNX(ctx, key, token, cfg.TTL).Result()
            if err != nil {
                failedNodes = append(failedNodes, node.Addr+":"+err.Error())
                continue
            }
            if acquiredNode {
                acquired++
            }
        }

        // Check quorum
        if acquired >= r.quorum {
            elapsedMs := time.Now().UnixMilli() - startTimeMs
            validityMs := ttlMs - elapsedMs - driftMs

            if validityMs > 0 {
                return &RedlockInstance{
                    redlock: r,
                    key:     key,
                    token:   token,
                    ttl:     cfg.TTL,
                    validityMs: validityMs,
                    acquiredNodes: acquired,
                }, nil
            }
        }

        // Release any partial locks
        for _, node := range r.nodes {
            node.rdb.Eval(ctx, releaseScript, []string{key}, token)
        }
    }

    return nil, fmt.Errorf("redlock not acquired after %d attempts", cfg.RetryCount)
}

// Release releases the Redlock on all nodes
func (ri *RedlockInstance) Release(ctx context.Context) error {
    var errs []string
    for _, node := range ri.redlock.nodes {
        _, err := node.rdb.Eval(ctx, releaseScript, []string{ri.key}, ri.token).Int64()
        if err != nil {
            errs = append(errs, node.Addr+":"+err.Error())
        }
    }
    if len(errs) > 0 {
        return fmt.Errorf("release errors on nodes: %s", strings.Join(errs, "; "))
    }
    return nil
}

// RedlockInstance represents an acquired Redlock
type RedlockInstance struct {
    redlock       *Redlock
    key           string
    token         string
    ttl           time.Duration
    validityMs    int64
    acquiredNodes int
}
```

### 3.3. Fencing Token with Redis + PostgreSQL

```go
// internal/fencing/fencing.go
package fencing

import (
    "context"
    "fmt"
    "sync/atomic"
    "time"

    "github.com/jackc/pgx/v5"
    "github.com/redis/go-redis/v9"
)

// TokenStore combines Redis lock with DB sequence for fencing
type TokenStore struct {
    rdb  *redis.Client
    conn *pgx.Conn
}

type FencedOperation struct {
    Token   int64  // Fencing token (monotonic from DB)
    OwnerID string // Lock owner ID
}

// AcquireWithFencing acquires Redis lock AND gets a fencing token from DB
func (ts *TokenStore) AcquireWithFencing(ctx context.Context, resourceID, ownerID string, ttl time.Duration) (*FencedOperation, error) {
    // 1. Acquire Redis lock (from distlock package)
    lock, err := Acquire(ctx, ts.rdb, "lock:"+resourceID, &Config{TTL: ttl})
    if err != nil {
        return nil, fmt.Errorf("lock not acquired: %w", err)
    }

    // 2. Get fencing token from DB (sequence is linearizable)
    var token int64
    err = ts.conn.QueryRow(ctx,
        "SELECT nextval('fencing_tokens')").Scan(&token)
    if err != nil {
        lock.Release(ctx)
        return nil, fmt.Errorf("fencing token: %w", err)
    }

    return &FencedOperation{
        Token:   token,
        OwnerID: ownerID,
    }, nil
}

// ExecuteWithFencing runs operation with fencing token check
func (ts *TokenStore) ExecuteWithFencing(
    ctx context.Context,
    resourceID string,
    op FencedOp,
) error {
    // Get current max token from DB
    var maxToken int64
    err := ts.conn.QueryRow(ctx,
        "SELECT COALESCE(MAX(token), 0) FROM fenced_operations WHERE resource_id = $1",
        resourceID,
    ).Scan(&maxToken)
    if err != nil {
        return err
    }

    if op.Token <= maxToken {
        return fmt.Errorf("stale fencing token: op=%d, max=%d", op.Token, maxToken)
    }

    return op.Execute(ctx)
}

// FencedOp is an operation with a fencing token
type FencedOp struct {
    Token   int64
    OwnerID string
    Execute func(ctx context.Context) error
}
```

---

## 4. Redis Sentinel HA Configuration

```yaml
# docker-compose.yml
services:
  redis-master:
    image: redis:7.2
    ports:
      - "6379:6379"
    command: >
      redis-server
      --save ""
      --appendonly no
      --maxmemory 256mb
      --maxmemory-policy volatile-lru
    volumes:
      - redis-master-data:/data
    networks:
      - redis-net
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-replica-1:
    image: redis:7.2
    ports:
      - "6380:6379"
    command: >
      redis-server
      --save ""
      --appendonly no
      --replicaof redis-master 6379
      --maxmemory 256mb
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy

  redis-replica-2:
    image: redis:7.2
    ports:
      - "6381:6379"
    command: >
      redis-server
      --save ""
      --appendonly no
      --replicaof redis-master 6379
      --maxmemory 256mb
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy

volumes:
  redis-master-data:

networks:
  redis-net:
    driver: bridge
```

```go
// Go: Redis Sentinel client for HA lock service
import "github.com/redis/go-redis/v9"

func newSentinelClient() *redis.Client {
    return redis.NewFailoverClient(&redis.FailoverOptions{
        MasterName:    "mymaster",
        SentinelAddrs: []string{
            "sentinel-1:26379",
            "sentinel-2:26379",
            "sentinel-3:26379",
        },
        SentinelPassword: "sentinel_pass",
        Password:         "redis_pass",
        DB:               0,
    })
}
```

---

## 5. Benchmark Commands

```bash
# ============ Lock Acquisition Benchmark ============

# Single-threaded baseline (no contention)
redis-benchmark -t SET -n 100000 -r 1000000 -d 32 \
  --set 'EX' 10 'NX'

# Multi-threaded lock benchmark (simulate contention)
redis-benchmark -t SET -n 100000 -r 10000 -d 32 \
  --set 'EX' 10 'NX' \
  -c 50  # 50 concurrent clients

# Measure p95/p99 latency of lock acquisition
redis-cli --latency-distribution

# ============ Safe Unlock Benchmark ============

redis-cli EVAL "
  for i = 1, 100000 do
    redis.call('SET', 'lock:'..i, 'token', 'PX', 30000)
  end
  return 'OK'
" 0

redis-benchmark -r 100000 -n 50000 \
  --evalsha "<EVALSHA of safe_unlock_script>" \
  -c 20

# ============ Redlock Benchmark ============

# Measure quorum acquisition time
python3 << 'EOF'
import asyncio
import aioredis
import time

NODES = ['redis://node1:6379', 'redis://node2:6379', 'redis://node3:6379']
QUORUM = 3

async def try_acquire_all(key, token, ttl_ms):
    results = await asyncio.gather(
        *[aioredis.eval(node, script, 1, key, token, ttl_ms)
          for node in NODES],
        return_exceptions=True
    )
    return sum(1 for r in results if r == b'OK')

async def benchmark_redlock(n=1000):
    key = "bench:redlock"
    token = "token123"
    ttl_ms = 10000

    latencies = []
    for _ in range(n):
        start = time.perf_counter()
        acquired = await try_acquire_all(key, token, ttl_ms)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        # Release
        await asyncio.gather(
            *[aioredis.eval(node, "return redis.call('DEL', KEYS[1])", 1, key)
              for node in NODES],
            return_exceptions=True
        )

    latencies.sort()
    p50 = latencies[n//2]
    p99 = latencies[n*99//100]
    print(f"Redlock p50={p50:.2f}ms p99={p99:.2f}ms")

asyncio.run(benchmark_redlock())
EOF
```

---

## 6. Comparison Tables

### Lock Tool Comparison

| Tiêu chí | Redis Lock | ZooKeeper | etcd | Consul | DB Lock |
|---|---|---|---|---|---|
| Protocol | Single Redis | ZAB (Paxos-like) | Raft consensus | Raft consensus | MVCC + 2PL |
| Linearizable | No | Yes | Yes | Yes | Yes |
| Latency p99 | 0.5ms | 20ms | 15ms | 25ms | 30ms |
| Fencing token | No (manual) | Yes (seq number) | Yes (mod_rev) | Yes | Yes |
| Min nodes | 1 (3 for HA) | 3 | 3 | 3 | 1 (2 for HA) |
| Lock auto-cleanup | TTL-based | Ephemeral node | Lease | Session | COMMIT/ROLLBACK |
| Multi-resource | Multiple locks | Yes (chroot) | Txn | Yes | Yes (single xact) |
| Lock scope | Any resource | Any resource | Any resource | Any resource | DB only |
| Operational complexity | Low | High | High | High | Medium |
| Best for | Fast coordination, idempotent ops | Leader election, config | Service discovery, config | Service mesh | Financial transactions |

### TTL Selection Guide

| Operation Duration | Recommended TTL | Example |
|---|---|---|
| < 100ms | 500ms – 1s | Rate limit counter, simple cache |
| 100ms – 1s | 3s – 5s | Single DB query, API call |
| 1s – 10s | 15s – 30s | File processing, batch job |
| 10s – 30s | 45s – 90s | Complex computation |
| > 30s | Use queue instead | Never use lock |

---

## 7. Production Checklist

### Pre-deployment Checklist

```bash
# Lock implementation checklist
[ ] DEL never called directly on lock key — always Lua script
[ ] SET NX PX used (not SETNX + EXPIRE separately)
[ ] Token is cryptographically random (UUID v4, 16+ bytes)
[ ] TTL set with safety margin (TTL >= duration * 3)
[ ] Retry with exponential backoff + jitter implemented
[ ] Lock not acquired case handled (fallback/queue/error)
[ ] Context cancellation releases lock (defer Release)
[ ] Lock value logged (for debugging), never parse for business logic
[ ] Redlock only if multi-region HA genuinely required
[ ] Clock drift measured across Redis nodes (if using Redlock)
[ ] Fencing token implemented if correctness required (not just availability)
[ ] Tested: client crash mid-operation → lock expires correctly
[ ] Tested: lock holder slow → extension mechanism works
[ ] Lock key pattern consistent: lock:<resource_type>:<resource_id>
[ ] Lock metrics emitted: acquire_success, acquire_fail, release, extend
```

### Monitoring Checklist

```bash
# Metrics to monitor
[ ] lock_acquire_success_total (counter)
[ ] lock_acquire_fail_total (counter)
[ ] lock_acquire_latency_ms (histogram)
[ ] lock_hold_duration_ms (histogram)
[ ] lock_extend_attempts (counter)
[ ] lock_extend_fail_total (counter)
[ ] lock_expired_during_operation_total (counter)  # critical alert

# Alert rules
[ ] Alert if lock_acquire_fail_rate > 5% over 5 min
[ ] Alert if lock_hold_duration_p99 > TTL * 0.7
[ ] Alert if lock_expired_during_operation > 0
```

---

## 8. Links & Resources

- [Redis SET command](https://redis.io/commands/set/)
- [Redis Lua Scripting](https://redis.io/docs/interact/programmability/lua-api/)
- [Martin Kleppmann — How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
- [Redlock paper by Salvatore Sanfilippo](https://redis.io/topics/distlock)
- [ZooKeeper recipes — Lock](https://zookeeper.apache.org/doc/current/recipes.html#sc_recipes_Locks)
- [etcd Concurrency API](https://etcd.io/docs/v3.6/learning/api_grpc_gateway/)
- [Consul Locks](https://developer.hashicorp.com/consul/docs/dynamic-app-config/sessions)
- [Stripe engineering — Idempotency](https://stripe.com/blog/idempotency)
- [Amazon DynamoDB conditional writes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html#WorkingWithItems.ConditionalUpdate)
- [PingCAP — TiDB linearizability](https://docs.pingcap.com/tidb/stable/transaction-overview)
