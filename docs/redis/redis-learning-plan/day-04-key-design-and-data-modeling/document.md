# Day 4: Key Design & Redis Data Modeling — Reference Document

---

## 1. Key Naming Convention Cheat Sheet

### Good vs Bad Examples

| Pattern | Good | Bad | Lý do |
|---------|------|-----|-------|
| Có namespace | `prod:catalog:product:10044:price` | `product_10044_price` | Dùng `:` dễ SCAN, parse |
| Có env prefix | `prod:...`, `staging:...` | `user:9921:profile` | Tránh ghi đè cross-env |
| Có service prefix | `order-service:order:88421` | `order:88421` | Tránh conflict multi-service |
| Key length ≤ 64B | `user:profile:{id}` | `user:profile:{long_uuid_v4}` | Tiết kiệm RAM |
| Hash PII trước khi làm key | `user:session:{sha256(email)}` | `user:session:john@gmail.com` | GDPR/PII compliance |
| Hash tag Cluster-aware | `order:{88421}:meta` | `order:88421:meta` | MULTI/EXEC cross-slot |
| Version trong key prefix | `v2:user:profile:9921` | `user:profile:9921:version:2` | Namespace invalidation |
| TTL always set | `SET key val EX 3600` | `SET key val` | Tránh memory leak |

### Quick Reference

```txt
Format: {env}:{service}:{entity}:{id}:{field?}

Delimiter:    luôn dùng `:`
Max length:   64 bytes (khuyến nghị), 512 MB (max)
PII:          hash/anonymize trước khi dùng làm key
Version:      trong key prefix, không phải value
Hash tag:     {id} khi cần multi-key atomic trên Cluster
TTL:          luôn set, jitter ±10-20% cho read-heavy cache
Delete:       UNLINK thay vì DEL cho key >1K elements
```

---

## 2. Production Key Design Checklist

### Naming Convention

- [ ] Có `{env}` prefix (prod, staging, dev)?
- [ ] Có `{service}` prefix (order-service, catalog-service)?
- [ ] Dùng `:` làm delimiter, không dùng `_` hay `.`?
- [ ] Key length ≤ 64 bytes?
- [ ] Không chứa raw PII (email, phone, URL)?
- [ ] PII đã hash/anonymize trước khi làm key?

### TTL

- [ ] Mọi cache key đều có TTL?
- [ ] TTL phù hợp với data freshness requirement?
- [ ] Read-heavy cache có jitter ±10-20%?
- [ ] Session/active data dùng sliding TTL (EXPIRE on access)?
- [ ] TTL aligned với business cycle (hourly/daily/weekly)?

### Cardinality

- [ ] Key cardinality bounded? (predict được max key count)
- [ ] Không dùng raw URL, UUID v4, email trong key?
- [ ] Có strategy cho unbounded key (Hash, Sorted Set, List)?
- [ ] Periodic cleanup cho old keys?

### Redis Cluster

- [ ] Multi-key operation (MULTI/EXEC, Lua) có hash tag?
- [ ] Hash tag có cardinality đủ cao và đều?
- [ ] Hash tag không tạo hot slot?
- [ ] Đã test `CLUSTER KEYSLOT` cho các key liên quan?

### Versioning

- [ ] Schema/data format change có dùng version prefix?
- [ ] Version trong key prefix, không phải value?
- [ ] Dual-read (try new, fallback old) đã implement?
- [ ] Rollback strategy rõ ràng?

### Deletion

- [ ] Dùng UNLINK thay vì DEL cho key >1K elements?
- [ ] Có config `lazyfree-lazy-user-del yes`?
- [ ] Tenant/service deletion dùng SCAN + UNLINK chunked?
- [ ] Không dùng KEYS * trên prod?

### Multi-tenant

- [ ] Tenant isolation qua key prefix hoặc hash tag?
- [ ] Tenant migration strategy có?
- [ ] Tenant quota monitoring có?

### Operations

- [ ] SCAN dùng thay KEYS?
- [ ] Có keyspace monitoring (key count, memory per pattern)?
- [ ] Alert on key count growth rate?
- [ ] maxmemory policy đặt đúng?

---

## 3. E-commerce Keyspace Template

```txt
###############################################################################
# E-COMMERCE KEYSPACE TEMPLATE
# Environment: prod | staging | dev
###############################################################################

# ── Product Catalog ──────────────────────────────────────────────────────────
# Cache product data, TTL 1h ± 15% jitter
{cache}:catalog:product:{product_id}:price      # String, EX 3600±15%
{cache}:catalog:product:{product_id}:info        # Hash,  EX 3600±15%
{cache}:catalog:product:{product_id}:images     # List,  EX 7200±15%

# Featured/hero products (updated infrequently)
{cache}:catalog:featured:products                # Sorted Set (score=rank), EX 300±5%
{cache}:catalog:featured:categories              # Sorted Set, EX 900±10%

# Product search cache (page-based)
{cache}:catalog:search:{query_hash}:page:{n}    # String (JSON), EX 600±20%

# ── Inventory ───────────────────────────────────────────────────────────────
# Real-time stock (short TTL, invalidate on write)
{cache}:inventory:product:{product_id}:qty      # String, EX 30
{cache}:inventory:product:{product_id}:reserved # String, EX 60

# ── Shopping Cart ───────────────────────────────────────────────────────────
# Sliding TTL: expire on every write, reset TTL on read
{session}:cart:user:{user_id}:items             # Hash, EX 604800 (7d), touch on access
{session}:cart:user:{user_id}:meta              # Hash, EX 604800 (7d)

# Cart lock (distributed lock for concurrent modification)
{lock}:cart:user:{user_id}                      # String NX PX 5000

# ── Order ───────────────────────────────────────────────────────────────────
# Order state machine (Cluster-aware hash tag)
{order}:{order_id}:meta                         # Hash, TTL=30d
{order}:{order_id}:items                        # Hash, TTL=30d
{order}:{order_id}:status                       # String, TTL=30d
{order}:{order_id}:payment                      # Hash, TTL=30d
  # Hash tag: {order_id} ensures all keys same slot → MULTI/EXEC atomic

# Order confirmation token (short-lived)
{tmp}:order:confirm:{token}                    # String, EX 900 (15m)

# ── Session / Auth ──────────────────────────────────────────────────────────
# Sliding TTL session
{session}:user-service:session:{token}          # Hash, EX 1800, touch on access
{session}:user-service:user:{user_id}:sessions  # Set (active sessions), no TTL

# ── Rate Limiting ───────────────────────────────────────────────────────────
# Fixed window, no jitter
{limiter}:api:{client_id}:{window_timestamp}    # String INCR, EX 60
{limiter}:order-service:{user_id}:count          # String INCR, EX 60

# ── Leaderboard ──────────────────────────────────────────────────────────────
{cache}:leaderboard:sellers:global              # Sorted Set, EX 300±10%
{cache}:leaderboard:sellers:daily:{date}         # Sorted Set, EX 86400±10%

# ── Recently Viewed ──────────────────────────────────────────────────────────
{cache}:user:{user_id}:recently_viewed           # List (LPUSH, LTRIM 0 49), no TTL
```

---

## 4. Ride-hailing Keyspace Template

```txt
###############################################################################
# RIDE-HAILING KEYSPACE TEMPLATE
# Scale: 100K trips/day, 10K drivers, multi-region
###############################################################################

# ── Driver Location (Geospatial) ─────────────────────────────────────────────
# GEOADD driver:locations:{region} {lng} {lat} {driver_id}
{driver}:location:{region}:{driver_id}           # GEO, no TTL (update on move)
{driver}:location:hash:{driver_id}              # Hash: {lat, lng, updated_at}
                                                       # TTL=300, overwrite on each update

# ── Trip State (Cluster-aware, hash tag by trip_id) ─────────────────────────
{trip}:{trip_id}:meta                           # Hash, TTL=24h
{trip}:{trip_id}:location                       # Hash, TTL=24h
{trip}:{trip_id}:fare                           # Hash, TTL=24h
{trip}:{trip_id}:status                         # String, TTL=24h
  # Hash tag {trip_id}: all trip keys on same slot → MULTI/EXEC atomic

# ── Driver-Trip Assignment ──────────────────────────────────────────────────
{driver}:active_trip:{driver_id}                 # String (trip_id), EX 7200
{trip}:driver:{trip_id}                         # String (driver_id), EX 7200

# ── Surge Pricing Zone ───────────────────────────────────────────────────────
# Aggregate drivers/passengers per zone
{zone}:{zone_id}:drivers                        # Set (driver IDs), EX 60
{zone}:{zone_id}:requests                       # Set (request IDs), EX 60
{zone}:{zone_id}:surge_multiplier              # String (float), EX 30

# ── ETA Cache ────────────────────────────────────────────────────────────────
{route}:eta:{origin_hash}:{dest_hash}:{ts}     # String (JSON), EX 120±20%
                                                       # origin_hash = geohash(origin)

# ── Dispatch Queue ───────────────────────────────────────────────────────────
# Sorted Set: pending requests by pickup time
{queue}:dispatch:pending:{region}               # Sorted Set (score=created_at)
                                                       # Remove on assign

# ── Rate Limiting ────────────────────────────────────────────────────────────
{limiter}:rider:{user_id}:requests              # String INCR, EX 60
{limiter}:driver:{driver_id}:requests           # String INCR, EX 60
{limiter}:dispatch:{region}:requests            # String INCR, EX 60

# ── Multi-region: region prefix ──────────────────────────────────────────────
# Regions: us-east, us-west, eu-central, ap-south
{region}:driver:location:{driver_id}            # Hash, TTL=300

# ── Retention: 3-year compliance ────────────────────────────────────────────
# Trip history: Store in PostgreSQL, NOT Redis (too much data)
# Redis chỉ giữ recent trips (30 days hot), archive older
{trip}:recent:{trip_id}:meta                    # Hash, TTL=30d
# Cleanup: nightly job move Redis → cold storage → UNLINK
```

---

## 5. Go Code Snippets (`go-redis/v9`)

### 5.1 KeyBuilder with Namespace + Version

```go
// KeyBuilder builds Redis keys following production convention:
// {env}:{service}:{entity}:{id}:{field?}
type KeyBuilder struct {
    env     string
    service string
    version string // e.g., "v1", "v2"
}

func NewKeyBuilder(env, service, version string) *KeyBuilder {
    return &KeyBuilder{env: env, service: service, version: version}
}

func (kb *KeyBuilder) WithVersion(v string) *KeyBuilder {
    return &KeyBuilder{env: kb.env, service: kb.service, version: v}
}

// Format: {env}:{service}:{version}:{entity}:{id}:{field?}
func (kb *KeyBuilder) Key(entity string, id string, field string) string {
    parts := []string{kb.env, kb.service}
    if kb.version != "" {
        parts = append(parts, kb.version)
    }
    parts = append(parts, entity, id)
    if field != "" {
        parts = append(parts, field)
    }
    return strings.Join(parts, ":")
}

// Usage:
kb := NewKeyBuilder("prod", "catalog-service", "v2")
kb.Key("product", "10044", "price") // "prod:catalog-service:v2:product:10044:price"

// For Cluster-aware keys with hash tag:
func (kb *KeyBuilder) ClusterKey(entity string, id string, field string) string {
    // {id} as hash tag
    return fmt.Sprintf("%s:%s:{%s}:%s:%s", kb.env, kb.service, id, entity, field)
}

// Usage:
kb.ClusterKey("order", "88421", "meta") // "prod:order-service:{88421}:order:meta"
```

### 5.2 TTL with Jitter

```go
import (
    "math/rand"
    "time"
)

// SetWithJitterTTL sets a key with TTL jittered by ±jitterPct
// jitterPct: 0.0 to 1.0 (e.g., 0.15 = ±15%)
func SetWithJitterTTL(ctx context.Context, rdb *redis.Client, key, value string, baseTTL time.Duration, jitterPct float64) error {
    jitter := time.Duration(float64(baseTTL) * jitterPct * (rand.Float64()*2 - 1))
    ttl := baseTTL + jitter
    if ttl < 0 {
        ttl = baseTTL // floor at base
    }
    return rdb.Set(ctx, key, value, ttl).Err()
}

// SlidingTTL extends TTL on every access (for sessions)
func TouchTTL(ctx context.Context, rdb *redis.Client, key string, ttl time.Duration) error {
    return rdb.Expire(ctx, key, ttl).Err()
}

// ProbabilisticEarlyExpiration implements " probabilistic early expiration"
// from "Don't trust the biologists" (Facebook cache paper)
func MaybeEarlyExpire(baseTTL time.Duration, lastRefresh time.Time, probThreshold float64) bool {
    elapsed := time.Since(lastRefresh)
    expectedLife := float64(baseTTL)
    // If key has lasted longer than expected * (1 - probThreshold), consider refresh
    if rand.Float64() < probThreshold && float64(elapsed) > expectedLife*(1-probThreshold) {
        return true
    }
    return false
}

// Example usage:
SetWithJitterTTL(ctx, rdb, "prod:catalog:product:10044:price", "299000", time.Hour, 0.15)
// TTL will be in range [3060s, 4140s]
```

### 5.3 SafeDelete (UNLINK vs DEL)

```go
import (
    "context"
    "github.com/redis/go-redis/v9"
)

// IsBigKey estimates if a key is "big" by element count.
// It avoids DEBUG OBJECT because DEBUG is disabled on many production/managed Redis services.
func IsBigKey(ctx context.Context, rdb *redis.Client, key string, elementThreshold int64) (bool, error) {
    typ, err := rdb.Type(ctx, key).Result()
    if err != nil {
        return false, err
    }

    var n int64
    switch typ {
    case "none", "string":
        return false, nil
    case "hash":
        n, err = rdb.HLen(ctx, key).Result()
    case "list":
        n, err = rdb.LLen(ctx, key).Result()
    case "set":
        n, err = rdb.SCard(ctx, key).Result()
    case "zset":
        n, err = rdb.ZCard(ctx, key).Result()
    default:
        return true, nil
    }
    if err != nil {
        return true, err
    }
    return n > elementThreshold, nil
}

// SafeDelete deletes key using UNLINK if big, DEL if small
func SafeDelete(ctx context.Context, rdb *redis.Client, key string, elementThreshold int64) error {
    isBig, err := IsBigKey(ctx, rdb, key, elementThreshold)
    if err != nil {
        // Fallback to UNLINK if check fails (safer)
        return rdb.Unlink(ctx, key).Err()
    }
    if isBig {
        return rdb.Unlink(ctx, key).Err()
    }
    return rdb.Del(ctx, key).Err()
}

// DeletePattern deletes all keys matching pattern using SCAN + UNLINK
// chunkSize: number of keys to delete per iteration (100-1000 recommended)
func DeletePattern(ctx context.Context, rdb *redis.Client, pattern string, chunkSize int64) (int64, error) {
    var deleted int64
    var cursor uint64

    for {
        keys, nextCursor, err := rdb.Scan(ctx, cursor, pattern, chunkSize).Result()
        if err != nil {
            return deleted, err
        }

        if len(keys) > 0 {
            // Use Unlink (async) for all keys in this batch
            deleted += rdb.Unlink(ctx, keys...).Val()
        }

        cursor = nextCursor
        if cursor == 0 {
            break
        }
    }
    return deleted, nil
}
```

### 5.4 SCAN Iterator

```go
// ScanIterator scans all keys matching pattern using cursor-based iteration
// Non-blocking, safe for production
func ScanIterator(ctx context.Context, rdb *redis.Client, pattern string, count int64) ([]string, error) {
    var allKeys []string
    var cursor uint64

    for {
        keys, nextCursor, err := rdb.Scan(ctx, cursor, pattern, count).Result()
        if err != nil {
            return nil, err
        }
        allKeys = append(allKeys, keys...)
        cursor = nextCursor
        if cursor == 0 {
            break
        }
    }
    return allKeys, nil
}

// ScanKeysByPrefix streams keys matching prefix via callback (memory-efficient)
// Use for large keyspaces where loading all keys at once is too expensive
func ScanKeysByPrefix(ctx context.Context, rdb *redis.Client, prefix string, batchSize int64, fn func(keys []string) error) error {
    var cursor uint64
    pattern := prefix + "*"

    for {
        keys, nextCursor, err := rdb.Scan(ctx, cursor, pattern, batchSize).Result()
        if err != nil {
            return err
        }

        if len(keys) > 0 {
            if err := fn(keys); err != nil {
                return err
            }
        }

        cursor = nextCursor
        if cursor == 0 {
            break
        }
    }
    return nil
}

// Example: Count keys per namespace
func CountKeysByNamespace(ctx context.Context, rdb *redis.Client) (map[string]int64, error) {
    counts := make(map[string]int64)
    var cursor uint64

    for {
        keys, nextCursor, err := rdb.Scan(ctx, cursor, "*", 1000).Result()
        if err != nil {
            return nil, err
        }

        for _, key := range keys {
            // Extract namespace (first 3 segments: env:service:entity)
            parts := strings.Split(key, ":")
            if len(parts) >= 3 {
                ns := strings.Join(parts[:3], ":")
                counts[ns]++
            }
        }

        cursor = nextCursor
        if cursor == 0 {
            break
        }
    }
    return counts, nil
}
```

### 5.5 Versioned Namespace Helper

```go
// VersionedCache provides namespace versioning for mass invalidation
type VersionedCache struct {
    rdb     *redis.Client
    kb      *KeyBuilder
    current string // current version, e.g., "v3"
}

func NewVersionedCache(rdb *redis.Client, kb *KeyBuilder, version string) *VersionedCache {
    return &VersionedCache{rdb: rdb, kb: kb, current: version}
}

// ReadTryNewFallbackOld: try current version, fallback to previous versions
func (vc *VersionedCache) Get(ctx context.Context, entity, id, field string) (string, error) {
    // Try current version
    key := vc.keyWithVersion(entity, id, field, vc.current)
    val, err := vc.rdb.Get(ctx, key).Result()
    if err == nil {
        return val, nil
    }
    if err == redis.Nil {
        // Fallback: try v1, v2 if current is v3
        for _, v := range []string{"v2", "v1"} {
            if v == vc.current {
                continue
            }
            key := vc.keyWithVersion(entity, id, field, v)
            val, err := vc.rdb.Get(ctx, key).Result()
            if err == nil {
                return val, nil // found in older version
            }
        }
        return "", redis.Nil
    }
    return "", err
}

func (vc *VersionedCache) keyWithVersion(entity, id, field, version string) string {
    if version == "" {
        return strings.Join([]string{vc.kb.env, vc.kb.service, entity, id, field}, ":")
    }
    return strings.Join([]string{vc.kb.env, vc.kb.service, version, entity, id, field}, ":")
}

// InvalidateAll: bump version — no need to delete individual keys
func (vc *VersionedCache) InvalidateAll(ctx context.Context) error {
    newVersion := bumpVersion(vc.current)
    // Delete old version keys in background
    oldPattern := vc.keyPattern(vc.current)
    go func() {
        ctx := context.Background()
        deleted, err := DeletePattern(ctx, vc.rdb, oldPattern, 1000)
        if err != nil {
            log.Printf("failed to invalidate old version %s: %v, deleted %d", oldPattern, err, deleted)
        }
    }()
    vc.current = newVersion
    return nil
}

func (vc *VersionedCache) keyPattern(version string) string {
    return strings.Join([]string{vc.kb.env, vc.kb.service, version, "*"}, ":")
}

func bumpVersion(v string) string {
    if v == "" {
        return "v1"
    }
    // Simple vN increment
    if v[0] == 'v' {
        n := 0
        fmt.Sscanf(v[1:], "%d", &n)
        return fmt.Sprintf("v%d", n+1)
    }
    return v
}
```

---

## 6. Docker Compose Setup (Day 4 Exercises)

```yaml
version: "3.8"
services:
  redis:
    image: redis:7-alpine
    container_name: redis-day4
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --lazyfree-lazy-user-del yes
      --save ""
      --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  redis-cluster:
    image: redis:7-alpine
    container_name: redis-cluster-node
    ports:
      - "7380:7380"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-node-timeout 5000
      --maxmemory 128mb
      --lazyfree-lazy-user-del yes
      --save ""
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7380", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

---

## 7. Official Links

- Key patterns: https://redis.io/docs/manual/keyspace/
- Key expiry: https://redis.io/docs/manual/keyspace/#expire-options
- Redis Cluster / Hash tags: https://redis.io/docs/manual/scaling/#redis-cluster-data-sharding
- Hash tags spec: https://redis.io/docs/reference/cluster-spec/#hash-tags
- Redis Best Practices (antirez): https://redis.io/docs/manual/optimization/
- AWS ElastiCache best practices: https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractises.html
- Keyspace notifications (for TTL monitoring): https://redis.io/docs/manual/keyspace-notifications/
- OBJECT command: https://redis.io/commands/object/
