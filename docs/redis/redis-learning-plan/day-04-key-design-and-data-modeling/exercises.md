# Day 4: Key Design & Redis Data Modeling — Exercises

**Thời lượng**: ~2 giờ
**Môi trường**: Redis 7 (Docker), redis-cli, Go + go-redis/v9

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. TTL lifecycle commands

```bash
# 1. SET a key với TTL
SET prod:session:user:9921:data "active" EX 60

# 2. Kiểm tra TTL còn lại
TTL prod:session:user:9921:data
# Expected: ~60 (số giây còn lại, không âm)

# 3. Giảm TTL xuống 30 giây
EXPIRE prod:session:user:9921:data 30

# 4. Kiểm tra lại
TTL prod:session:user:9921:data
# Expected: ~30

# 5. Xóa TTL (PERSIST)
PERSIST prod:session:user:9921:data
TTL prod:session:user:9921:data
# Expected: -1 (không có TTL)

# 6. Expire key bằng timestamp trong quá khứ
SET expired:key "value"
EXPIREAT expired:key 1
# Key bị xóa ngay vì expire time đã ở quá khứ

# 7. Verify key không tồn tại
GET expired:key
# Expected: (nil)
```

### 1.2. SCAN vs KEYS performance

```bash
# Tạo 5000 keys để test
for i in {1..5000}; do
  redis-cli SET "warmup:key:$i" "value_$i"
done

# Dùng KEYS để quan sát trong DEV, không chạy trên prod
time redis-cli KEYS "warmup:key:*" > /tmp/warmup-keys.txt
# Observe: KEYS scan toàn bộ keyspace trong một command blocking

# Dùng SCAN (production-safe)
redis-cli SCAN 0 MATCH "warmup:key:*" COUNT 100
# Run nhiều lần cho đến khi cursor = 0
# Observe: mỗi call trả về ~100 keys, non-blocking

# So sánh output
redis-cli SCAN 0 MATCH "warmup:key:*" COUNT 1000
# COUNT là hint, có thể trả về nhiều hoặc ít hơn

# Cleanup
redis-cli --scan --pattern "warmup:key:*" | xargs -r -n 500 redis-cli UNLINK
```

### 1.3. OBJECT IDLETIME và DEBUG OBJECT

```bash
# Tạo key
SET "prod:cache:report:daily" "data_v1"

# Kiểm tra idle time
OBJECT IDLETIME prod:cache:report:daily
# Expected: số giây key không được accessed

# Đọc key để reset idle time
GET prod:cache:report:daily
OBJECT IDLETIME prod:cache:report:daily
# Expected: 0 hoặc 1

# Kiểm tra encoding của Hash nhỏ vs lớn
HSET "test:hash:small" f1 v1 f2 v2 f3 v3
for i in $(seq 1 600); do
  redis-cli HSET "test:hash:large" "f$i" "$i" > /dev/null
done

redis-cli OBJECT ENCODING "test:hash:small"
# Expected: listpack (Redis 7+)

redis-cli OBJECT ENCODING "test:hash:large"
# Expected: hashtable (large)

# Cleanup
redis-cli UNLINK "prod:cache:report:daily" "test:hash:small" "test:hash:large"
```

### 1.4. DEL vs UNLINK blocking simulation

```bash
# Tạo big Hash (10,000 fields)
redis-cli --pipe-timeout 30 <<EOF
HSET test:big:hash f1 v1
EOF
# Tạo 10K fields bằng script nhỏ
for i in $(seq 1 10000); do
  redis-cli HSET "test:big:hash" "field_$i" "value_$i"
done

# Đo thời gian DEL (sẽ block)
time redis-cli DEL test:big:hash

# Tạo lại để test UNLINK
for i in $(seq 1 10000); do
  redis-cli HSET "test:big:hash:2" "field_$i" "value_$i"
done

# Đo thời gian UNLINK (non-blocking)
time redis-cli UNLINK test:big:hash:2
# UNLINK return ngay lập tức, memory freed async
```

---

## 2. Hands-on Lab (60-70 phút)

### Mục tiêu

Implement production-grade Redis key management utilities trong Go.

### File cần tạo

```
D:\my-source\learning\redis\redis-learning-plan\day-04-key-design-and-data-modeling\lab\
├── go.mod
├── main.go
├── keybuilder.go
├── keybuilder_test.go
├── ttl.go
├── ttl_test.go
├── delete.go
└── delete_test.go
```

### 2.1. Setup

```bash
mkdir -p "D:/my-source/learning/redis/redis-learning-plan/day-04-key-design-and-data-modeling/lab"
cd "D:/my-source/learning/redis/redis-learning-plan/day-04-key-design-and-data-modeling/lab"

cat > go.mod <<'EOF'
module day4-lab

go 1.21

require github.com/redis/go-redis/v9 v9.4.0
EOF
```

### 2.2. Starter Code

**`keybuilder.go`**:

```go
package main

import (
    "fmt"
    "strings"
)

// KeyBuilder builds Redis keys following production convention:
// {env}:{service}:{version}:{entity}:{id}:{field?}
//
// Example:
//   kb := NewKeyBuilder("prod", "order-service", "v2")
//   kb.Key("order", "88421", "meta")
//   // => "prod:order-service:v2:order:88421:meta"
//
// Cluster-aware:
//   kb.ClusterKey("order", "88421", "meta")
//   // => "prod:order-service:{88421}:order:meta"
type KeyBuilder struct {
    env     string
    service string
    version string
}

// NewKeyBuilder creates a new KeyBuilder.
func NewKeyBuilder(env, service, version string) *KeyBuilder {
    return &KeyBuilder{env: env, service: service, version: version}
}

// WithVersion returns a new KeyBuilder with the specified version.
func (kb *KeyBuilder) WithVersion(v string) *KeyBuilder {
    return &KeyBuilder{env: kb.env, service: kb.service, version: v}
}

// Key builds a standard key path.
// Format: {env}:{service}:{version}:{entity}:{id}:{field?}
// Version is skipped if empty string.
func (kb *KeyBuilder) Key(entity string, id string, field string) string {
    // TODO: Implement
    // Hint: build []string, filter empty version, join with ":"
    return ""
}

// ClusterKey builds a Cluster-aware key with hash tag around id.
// Format: {env}:{service}:{id}:{entity}:{field}
// The {id} becomes the hash tag for Redis Cluster slot calculation.
func (kb *KeyBuilder) ClusterKey(entity string, id string, field string) string {
    // TODO: Implement
    // Hash tag format: {id} — only id is inside braces
    return ""
}

// KeyPrefix returns a pattern prefix for SCAN operations.
// Example: kb.KeyPrefix("order") => "prod:order-service:v2:order:*"
func (kb *KeyBuilder) KeyPrefix(entity string) string {
    // TODO: Implement
    return ""
}

// Env returns the environment.
func (kb *KeyBuilder) Env() string { return kb.env }

// Service returns the service name.
func (kb *KeyBuilder) Service() string { return kb.service }

// Version returns the current version.
func (kb *KeyBuilder) Version() string { return kb.version }
```

**`ttl.go`**:

```go
package main

import (
    "context"
    "math/rand"
    "time"

    "github.com/redis/go-redis/v9"
)

// SetWithJitterTTL sets a key with TTL randomized by ±jitterPct.
// jitterPct: 0.0 to 1.0 (e.g., 0.15 = ±15% of baseTTL)
//
// Example:
//   SetWithJitterTTL(ctx, rdb, "key", "val", time.Hour, 0.15)
//   // TTL could be anywhere from 3060s to 4140s
func SetWithJitterTTL(ctx context.Context, rdb *redis.Client, key, value string, baseTTL time.Duration, jitterPct float64) error {
    // TODO: Implement
    // 1. Calculate jitter: baseTTL * jitterPct * (rand.Float64()*2 - 1)
    // 2. TTL = baseTTL + jitter (ensure >= 0)
    // 3. rdb.Set with calculated TTL
    return nil
}

// TouchTTL resets TTL on a key (sliding TTL pattern for sessions).
// Returns true if key existed and TTL was set, false if key didn't exist.
func TouchTTL(ctx context.Context, rdb *redis.Client, key string, ttl time.Duration) (bool, error) {
    // TODO: Implement
    // Hint: use EXPIRE with SETEX pattern, or PEXPIREAT
    return false, nil
}

// ProbabilisticEarlyExpiration decides if a cache entry should be
// refreshed early to prevent thundering herd.
//
// probRefresh: probability of refresh when elapsed > baseTTL*(1-probThreshold)
// Returns true if caller should refresh the cache entry.
func ProbabilisticEarlyExpiration(baseTTL, elapsed time.Duration, refreshProb float64) bool {
    // TODO: Implement
    // If elapsed > baseTTL AND rand < refreshProb, return true
    return false
}
```

**`delete.go`**:

```go
package main

import (
    "context"
    "strings"

    "github.com/redis/go-redis/v9"
)

// SafeDelete deletes a key using UNLINK if it has more than elementThreshold fields/elements,
// otherwise uses DEL. Falls back to UNLINK on error.
//
// elementThreshold: minimum number of elements to trigger UNLINK
//   Hash: number of fields
//   List/Set/ZSet: number of elements
//   String: always DEL (no elements to count)
func SafeDelete(ctx context.Context, rdb *redis.Client, key string, elementThreshold int64) error {
    // TODO: Implement
    // 1. Get key type: TYPE key
    // 2. If string -> DEL
    // 3. If hash -> HLEN
    // 4. If list -> LLEN
    // 5. If set -> SCARD
    // 6. If zset -> ZCARD
    // 7. If count > threshold -> UNLINK, else DEL
    // 8. On error -> fallback UNLINK
    return nil
}

// DeleteByPattern deletes all keys matching pattern using SCAN + UNLINK.
// Returns total number of keys deleted.
// chunkSize: number of keys per SCAN batch (100-1000 recommended).
func DeleteByPattern(ctx context.Context, rdb *redis.Client, pattern string, chunkSize int64) (int64, error) {
    // TODO: Implement
    // 1. SCAN loop with cursor
    // 2. UNLINK each batch
    // 3. Count total deleted
    return 0, nil
}

// CountKeysByPattern counts keys matching pattern using SCAN.
func CountKeysByPattern(ctx context.Context, rdb *redis.Client, pattern string) (int64, error) {
    // TODO: Implement
    return 0, nil
}
```

### 2.3. Test File (`keybuilder_test.go`)

```go
package main

import "testing"

func TestKeyBuilder_Key(t *testing.T) {
    kb := NewKeyBuilder("prod", "order-service", "v2")

    tests := []struct {
        name    string
        kb      *KeyBuilder
        entity  string
        id      string
        field   string
        want    string
    }{
        {
            name:   "full key with all parts",
            kb:     NewKeyBuilder("prod", "order-service", "v2"),
            entity: "order", id: "88421", field: "meta",
            want:   "prod:order-service:v2:order:88421:meta",
        },
        {
            name:   "key without version",
            kb:     NewKeyBuilder("prod", "catalog-service", ""),
            entity: "product", id: "10044", field: "price",
            want:   "prod:catalog-service:product:10044:price",
        },
        {
            name:   "WithVersion override",
            kb:     NewKeyBuilder("prod", "user-service", "v1").WithVersion("v3"),
            entity: "session", id: "abc123", field: "data",
            want:   "prod:user-service:v3:session:abc123:data",
        },
        {
            name:   "field empty string",
            kb:     NewKeyBuilder("staging", "cache", "v1"),
            entity: "product", id: "200", field: "",
            want:   "staging:cache:v1:product:200",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := tt.kb.Key(tt.entity, tt.id, tt.field)
            if got != tt.want {
                t.Errorf("Key() = %q, want %q", got, tt.want)
            }
        })
    }
}

func TestKeyBuilder_ClusterKey(t *testing.T) {
    kb := NewKeyBuilder("prod", "order-service", "v2")

    got := kb.ClusterKey("order", "88421", "meta")
    want := "prod:order-service:{88421}:order:meta"
    if got != want {
        t.Errorf("ClusterKey() = %q, want %q", got, want)
    }

    // Verify hash tag is only around the ID
    kb2 := NewKeyBuilder("prod", "trip-service", "v1")
    got2 := kb2.ClusterKey("trip", "trip_abc123", "status")
    want2 := "prod:trip-service:{trip_abc123}:trip:status"
    if got2 != want2 {
        t.Errorf("ClusterKey() = %q, want %q", got2, want2)
    }
}
```

### 2.4. Hints (nếu cần)

**Hint 2.2 (keybuilder.go)**: Build slice `[]string{kb.env, kb.service}`, nếu version != "" thì append version, sau đó append entity/id/field (nếu != ""). Dùng `strings.Join(s, ":")`.

**Hint 2.3 (ttl.go)**:
- `SetWithJitterTTL`: `jitter := int64(float64(baseTTL) * jitterPct * (rand.Float64()*2 - 1))` → convert sang Duration
- `TouchTTL`: kiểm tra `rdb.Exists(ctx, key).Val() > 0` trước, rồi `rdb.Expire(ctx, key, ttl)`

**Hint 2.4 (delete.go)**:
- Dùng `rdb.Type(ctx, key).Val()` để lấy key type
- Dùng `rdb.Unlink(ctx, key).Err()` hoặc `rdb.Del(ctx, key).Err()`
- `CountKeysByPattern`: SCAN loop đếm keys

### 2.5. Expected Output

```bash
# Chạy tests
cd lab && go mod tidy && go test -v ./...

=== RUN   TestKeyBuilder_Key
--- PASS: TestKeyBuilder_Key (0.00s)
=== RUN   TestKeyBuilder_ClusterKey
--- PASS: TestKeyBuilder_ClusterKey (0.00s)

# Chạy integration test (cần Redis chạy)
go test -v -run=TestIntegration ./...

=== RUN   TestSetWithJitterTTL
--- PASS: TestSetWithJitterTTL (0.00s)
=== RUN   TestSafeDelete
--- PASS: TestSafeDelete (0.00s)
=== RUN   TestDeleteByPattern
--- PASS: TestDeleteByPattern (0.00s)
```

---

## 3. Challenge Exercise (30-40 phút)

### 3A. Key Design Review: bad-keyspace.txt

File `bad-keyspace.txt` chứa 10 key design sai phổ biến. Đọc, identify problem, đề xuất fix.

```txt
# bad-keyspace.txt — copy vào lab/

# Case 1: No namespace, no TTL
order_88421_meta = "{'status': 'paid'}"

# Case 2: Raw email in key (PII + cardinality explosion)
user_session:john.smith@company.com = "session_data"

# Case 3: Raw URL in key (unbounded cardinality)
cache:GET:https://api.example.com/v2/products?category=electronics&page=1&sort=price_asc = "{...}"

# Case 4: No TTL on cache
product:catalog:10044:price = "299000"

# Case 5: Hash tag trên low-cardinality field (hot slot)
session:{status}:{user_id}:data   # status = "active" hoặc "inactive" → chỉ 2 slot!

# Case 6: Version trong value thay vì key
user:profile:9921 = '{"name": "Ana", "profile_version": 2}'

# Case 7: DEL on big Hash (1M fields)
DEL big_analytics:events:2024

# Case 8: KEYS * trong production code
def get_all_user_keys():
    return redis.keys("user:*")

# Case 9: Unbounded key count - notification per notification_id
notification:{user_id}:{notification_id} = "{...}"

# Case 10: Cross-service key conflict
auth:token:{token}         # Auth service
payment:token:{token}      # Payment service — conflict nếu token format giống nhau
```

**Yêu cầu**: Với mỗi case, viết:
1. Tên vấn đề (Problem)
2. Hậu quả nếu deploy (Impact)
3. Key design đúng (Fixed Key Pattern)
4. Lệnh Redis để fix production data (Fix Command)

---

### 3B. Ride-hailing Keyspace Design

Thiết kế keyspace cho hệ thống ride-hailing với constraints:

```
Constraints:
- Scale: 100,000 trips/day
- Active drivers: 10,000 concurrent
- Regions: 3 (us-east, us-west, eu-central)
- Retention: 3-year (hot: 30 days in Redis, cold: PostgreSQL)
- Multi-region active: drivers may cross regions
- Redis Cluster: 6 nodes (3 shards × 2 replicas)
- Security: No PII in keys
- Operations: Must support instant tenant/driver data deletion
```

**Yêu cầu**:

1. **Key naming convention** (theo format đã học)
2. **TTL strategy** (base + jitter) cho từng key type
3. **Hash tag design** cho Cluster (justify: tại sao chọn field đó)
4. **Cardinality analysis**: max keys per type, bounded or unbounded?
5. **Unbounded key mitigation** (nếu có)
6. **Data retention plan**: hot→cold migration strategy
7. **Multi-region key isolation**: strategy để không conflict
8. **Redis Cluster slot distribution** analysis

**Deliverable**: Viết output thành document trong `ridehailing-keyspace.md`

---

## 4. Reflection Questions (5-10 phút)

### Câu hỏi 1
Khi nào bạn chọn **versioned namespace** thay vì **per-key invalidation**? Trình bày decision tree với 3 câu hỏi để quyết định.

### Câu hỏi 2
TTL fixed đồng loạt gây stampede. Tuy nhiên, có scenario nào mà **fixed TTL không jitter** lại là lựa chọn đúng? Giải thích với ví dụ cụ thể.

### Câu hỏi 3
Hash tag `order:{order_id}` là hash tag tốt cho trip data của Uber. Nhưng `order:{customer_id}` là hash tag tệ. Giải thích sự khác biệt và đưa ra guideline chọn hash tag field.

### Câu hỏi 4
Bạn có 2 options cho session storage:
- A: `session:{user_id}:{session_id}` (fine-grained, N keys per user)
- B: `session:{user_id}` (Hash, 1 key per user)

So sánh trade-off và đưa ra recommendation cho:
- 10K concurrent users, mỗi user 1-2 sessions
- 10K concurrent users, mỗi user 50+ sessions (VPN/multi-device)

### Câu hỏi 5
Redis Cluster có 16384 slot. Bạn có 1 tenant chiếm 40% traffic. Điều gì xảy ra và bạn giải quyết thế nào nếu không thể thay đổi hash tag (vì đã có production data)?

---

## 5. Solution Guide

> **⚠️ SPOILER WARNING**: Phần này chứa đáp án. Hãy hoàn thành bài tập trước khi đọc.

---

### Solution 3A: Key Design Review

**Case 1: No namespace, no TTL**
- Problem: Conflict với service khác, memory leak
- Fixed: `prod:order-service:order:{id}:meta`, TTL 30d
- Fix: `RENAME order_88421_meta prod:order-service:order:88421:meta` + EXPIRE

**Case 2: Raw email in key**
- Problem: PII violation (GDPR), cardinality = số user (bounded nhưng vẫn bad practice), email format có @ → không nên trong key
- Fixed: `session:user-service:session:{sha256(email)}:data` (anonymize)
- Fix: RENAME + scan-and-fix application code

**Case 3: Raw URL in key**
- Problem: Cardinality unbounded — mỗi unique URL query param = 1 key mới. OOM guaranteed.
- Fixed: `cache:api:get:{sha256(url_without_params)}:page:{n}` hoặc dùng request fingerprint
- Fix: UNLINK all keys matching pattern, rewrite code

**Case 4: No TTL on cache**
- Problem: Memory leak khi product không còn tồn tại
- Fixed: `SET prod:catalog:product:{id}:price {val} EX 3600`
- Fix: `EXPIRE prod:catalog:product:10044:price 3600`

**Case 5: Hash tag on low-cardinality field**
- Problem: Chỉ 2 unique hash tag values → tất cả "active" keys đổ vào 1 slot → hot slot
- Fixed: `{user_id}` làm hash tag → cardinality cao
- Impact: Phải RENAME key để thêm hash tag

**Case 6: Version in value**
- Problem: Không thể namespace invalidation, phải scan + check value mới invalidate
- Fixed: `v2:user:profile:{id}` — version trong key prefix
- Fix: Rewrite code, migration plan

**Case 7: DEL on big Hash**
- Problem: DEL O(N) với 1M fields → block event loop 5-15 giây
- Fixed: `UNLINK big_analytics:events:2024`
- Fix: `UNLINK big_analytics:events:2024` (immediate, async)

**Case 8: KEYS * in production**
- Problem: KEYS block event loop → latency spike toàn hệ thống
- Fixed: SCAN iterator
- Fix: Rewrite thành SCAN

**Case 9: Unbounded notification keys**
- Problem: Nếu 100K users × 10K notifs = 1B keys → OOM
- Fixed: `notif:{user_id}` (Hash) với 10K fields max, TTL 30d
- Fix: Migration script aggregate vào Hash, UNLINK old keys

**Case 10: Cross-service key conflict**
- Problem: Cùng token format → auth ghi đè payment
- Fixed: `auth:service:token:{token}` và `payment:service:token:{token}`
- Fix: RENAME toàn bộ keys, enforce service prefix

---

### Solution 3B: Ride-hailing Keyspace (Summary)

**Key convention**: `{env}:{service}:{version?}:{entity}:{id}:{field?}`

**TTL Strategy**:
| Entity | Base TTL | Jitter | Strategy |
|--------|----------|--------|----------|
| Driver location | 300s | ±10% | Fixed overwrite (GEO không cần TTL cứng) |
| Active trip | 24h | None | Fixed, sliding on event |
| Trip history | 30d | None | Fixed, nightly archive job |
| Surge zone | 30s | None | Fixed |
| Rate limit | 60s | None | Fixed window |

**Hash tag choice**:
- `{trip_id}` cho trip data → cardinality = 100K trips/day → đều
- `{driver_id}` cho driver data → cardinality = 10K drivers → đều
- KHÔNG `{region}` vì skewed (1 region có thể 80% traffic)

**Cardinality**:
- Driver location: bounded (10K drivers × 3 regions = 30K keys)
- Active trip: bounded (max 10K concurrent trips)
- Trip events: UNBOUNDED → mitigated bằng Sorted Set + TTL per trip

**Retention**:
- Nightly cron: `SCAN trip:recent:*` → check trip age → move to PostgreSQL → UNLINK
- Trip history > 30 days: không giữ trong Redis
- Audit log: Elasticsearch, không phải Redis

**Multi-region**:
- Key prefix: `{region}:driver:location:{driver_id}`
- Cross-region trips: `trip:{trip_id}:meta` không có region prefix (stateless trip ID)
- Global rate limit: key không có region → dùng Redis Cluster với hash tag `{client_id}`

---

### Solution 2: Go Implementation (keybuilder.go)

```go
func (kb *KeyBuilder) Key(entity, id, field string) string {
    parts := []string{kb.env, kb.service}
    if kb.version != "" {
        parts = append(parts, kb.version)
    }
    parts = append(parts, entity)
    parts = append(parts, id)
    if field != "" {
        parts = append(parts, field)
    }
    return strings.Join(parts, ":")
}

func (kb *KeyBuilder) ClusterKey(entity, id, field string) string {
    parts := []string{kb.env, kb.service, "{" + id + "}", entity}
    if field != "" {
        parts = append(parts, field)
    }
    return strings.Join(parts, ":")
}

func (kb *KeyBuilder) KeyPrefix(entity string) string {
    parts := []string{kb.env, kb.service}
    if kb.version != "" {
        parts = append(parts, kb.version)
    }
    parts = append(parts, entity)
    return strings.Join(parts, ":") + ":*"
}
```
