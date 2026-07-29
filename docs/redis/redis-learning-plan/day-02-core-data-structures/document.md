# Day 2: Core Data Structures — Reference Document

## 1. Command Cheat Sheet

### String Commands

| Command | Syntax | Time Complexity | Return |
|---------|--------|----------------|--------|
| `SET` | `SET key value [NX\|XX] [EX sec\|PX ms]` | O(1) | OK or nil |
| `GET` | `GET key` | O(1) | value or nil |
| `MGET` | `MGET key [key ...]` | O(N) | [values] |
| `MSET` | `MSET key v [key v ...]` | O(N) | OK |
| `MSETNX` | `MSETNX key v [key v ...]` | O(N) | 1 if all set |
| `SETNX` | `SETNX key value` | O(1) | 1 if set |
| `SETRANGE` | `SETRANGE key offset value` | O(1)* | new length |
| `GETRANGE` | `GETRANGE key start end` | O(N) | substring |
| `APPEND` | `APPEND key value` | O(1)* | new length |
| `INCR` | `INCR key` | O(1) | new value |
| `INCRBY` | `INCRBY key delta` | O(1) | new value |
| `INCRBYFLOAT` | `INCRBYFLOAT key delta` | O(1) | new value |
| `DECR` | `DECR key` | O(1) | new value |
| `STRLEN` | `STRLEN key` | O(1) | byte length |

### List Commands

| Command | Syntax | Time Complexity | Return |
|---------|--------|----------------|--------|
| `LPUSH` | `LPUSH key v [v ...]` | O(1)* | length |
| `RPUSH` | `RPUSH key v [v ...]` | O(1)* | length |
| `LPOP` | `LPOP key [count]` | O(1)* | element(s) |
| `RPOP` | `RPOP key [count]` | O(1)* | element(s) |
| `BLPOP` | `BLPOP key [key ...] timeout` | O(1) | element or nil |
| `BRPOP` | `BRPOP key [key ...] timeout` | O(1) | element or nil |
| `LRANGE` | `LRANGE key start stop` | O(S+M) | elements |
| `LINDEX` | `LINDEX key index` | O(N) | element |
| `LLEN` | `LLEN key` | O(1) | length |
| `LINSERT` | `LINSERT k BEFORE\|AFTER p v` | O(N) | length or -1 |
| `LSET` | `LSET key index value` | O(N) | OK |
| `LTRIM` | `LTRIM key start stop` | O(N) | OK |
| `RPOPLPUSH` | `RPOPLPUSH src dst` | O(1)* | element |

`*` amortized | `S` = start offset | `M` = number of elements

### Hash Commands

| Command | Syntax | Time Complexity | Return |
|---------|--------|----------------|--------|
| `HSET` | `HSET key field v [field v ...]` | O(1) per | N or 1 |
| `HGET` | `HGET key field` | O(1) | value or nil |
| `HMGET` | `HMGET key f [f ...]` | O(N) | [values] |
| `HGETALL` | `HGETALL key` | O(N) | [fields+values] |
| `HSETNX` | `HSETNX key field value` | O(1) | 1 if set |
| `HINCRBY` | `HINCRBY key field delta` | O(1) | new value |
| `HINCRBYFLOAT` | `HINCRBYFLOAT key f delta` | O(1) | new value |
| `HEXISTS` | `HEXISTS key field` | O(1) | 0 or 1 |
| `HDEL` | `HDEL key f [f ...]` | O(1) per | N removed |
| `HLEN` | `HLEN key` | O(1) | field count |
| `HSTRLEN` | `HSTRLEN key field` | O(1) | byte length |
| `HSCAN` | `HSCAN key cursor [MATCH p] [COUNT n]` | O(1)/iter | [cursor, fields] |
| `HRANDFIELD` | `HRANDFIELD k [count [WITHVALUES]]` | O(N) | field(s) |

### Set Commands

| Command | Syntax | Time Complexity | Return |
|---------|--------|----------------|--------|
| `SADD` | `SADD key m [m ...]` | O(1) per | N added |
| `SREM` | `SREM key m [m ...]` | O(1) per | N removed |
| `SISMEMBER` | `SISMEMBER key member` | O(1) | 0 or 1 |
| `SMISMEMBER` | `SMISMEMBER k m [m ...]` | O(N) | [0/1] |
| `SMEMBERS` | `SMEMBERS key` | O(N) | [members] |
| `SSCAN` | `SSCAN key cursor [MATCH p] [COUNT n]` | O(1)/iter | [cursor, members] |
| `SCARD` | `SCARD key` | O(1) | cardinality |
| `SINTER` | `SINTER key [key ...]` | O(N*K) | [members] |
| `SINTERCARD` | `SINTERCARD key [key ...] limit` | O(N*K) | count |
| `SUNION` | `SUNION key [key ...]` | O(N) | [members] |
| `SUNIONSTORE` | `SUNIONSTORE dest key [key ...]` | O(N) | cardinality |
| `SDIFF` | `SDIFF key [key ...]` | O(N) | [members] |
| `SRANDMEMBER` | `SRANDMEMBER key [count]` | O(N) | [members] |
| `SPOP` | `SPOP key [count]` | O(1) per | element(s) |

### Sorted Set Commands

| Command | Syntax | Time Complexity | Return |
|---------|--------|----------------|--------|
| `ZADD` | `ZADD key score m [score m ...]` | O(log N) per | N added |
| `ZINCRBY` | `ZINCRBY key delta member` | O(log N) | new score |
| `ZSCORE` | `ZSCORE key member` | O(1) | score or nil |
| `ZMSCORE` | `ZMSCORE k m [m ...]` | O(1) per | [scores] |
| `ZRANK` | `ZRANK key member` | O(log N) | rank or nil |
| `ZREVRANK` | `ZREVRANK key member` | O(log N) | rank or nil |
| `ZRANGE` | `ZRANGE key min max [BYSCORE\|BYLEX] [REV] [LIMIT o c] [WITHSCORES]` | O(log N + M) | [members(+scores)] |
| `ZREVRANGE` | `ZREVRANGE k start stop [WITHSCORES]` | O(log N + M) | [members(+scores)] |
| `ZRANGEBYSCORE` | `ZRANGEBYSCORE k min max [WITHSCORES] [LIMIT o c]` | O(log N + M) | [members(+scores)] |
| `ZREVRANGEBYSCORE` | `ZREVRANGEBYSCORE k max min [WITHSCORES] [LIMIT o c]` | O(log N + M) | [members(+scores)] |
| `ZCOUNT` | `ZCOUNT key min max` | O(log N) | count |
| `ZCARD` | `ZCARD key` | O(1) | cardinality |
| `ZDIFF` | `ZDIFF numkeys key [...] [WITHSCORES]` | O(N log N) | [members] |
| `ZDIFFSTORE` | `ZDIFFSTORE dest numkeys key [...]` | O(N log N) | count |
| `ZINTER` | `ZINTER numkeys k [...] [WEIGHTS w] [AGGREGATE SUM\|MIN\|MAX]` | O(N*K log K) | [members] |
| `ZINTERSTORE` | `ZINTERSTORE dest n k [...] [WEIGHTS w] [AGGREGATE SUM]` | O(N*K log K) | count |
| `ZUNION` | `ZUNION n k [...] [WEIGHTS w] [AGGREGATE SUM]` | O(N log N) | [members] |
| `ZMPOP` | `ZMPOP n k [...] MIN\|MAX [COUNT c]` | O(log N) per | [key, [members]] |
| `BZMPOP` | `BZMPOP timeout n k [...] MIN\|MAX [COUNT c]` | O(log N) per | [key, [members]] |
| `ZREMRANGEBYRANK` | `ZREMRANGEBYRANK key start stop` | O(log N + M) | removed count |
| `ZREMRANGEBYSCORE` | `ZREMRANGEBYSCORE key min max` | O(log N + M) | removed count |

---

## 2. Big O Complexity — Complete Reference

```
N = number of elements
M = number of elements returned
K = number of sets in operation
S = start offset in List LRANGE
```

### Time Complexity

| | String | List | Hash | Set | Sorted Set |
|---|---|---|---|---|---|
| Read single | O(1) | O(1)* | O(1) | — | O(1)** |
| Read multiple | O(N) | O(N) | O(N) | O(N) | O(N log N) |
| Range query | — | O(S+M) | — | — | O(log N + M) |
| Random access | — | O(N) | — | — | — |
| Add head | O(1) | O(1)* | O(1) | O(1) | O(log N) |
| Add tail | O(1) | O(1)* | — | — | — |
| Add (sorted) | — | — | — | — | O(log N) |
| Delete | O(1) | O(1)* | O(1) | O(1) | O(log N) |
| Membership | — | — | — | O(1) | O(log N) |
| Intersection | — | — | — | O(N*K) | O(N*K log K) |
| Union | — | — | — | O(N) | O(N log N) |
| Cardinality | — | O(1) | O(1) | O(1) | O(1) |

### Space Complexity

| | String | List | Hash | Set | Sorted Set |
|---|---|---|---|---|---|
| Per element | O(1) | O(1) | O(1) | O(1) | O(log N) |
| Overhead | SDS header (2-8B) | ziplist pointer | field+value + metadata | entry metadata | skiplist + hash entry |

---

## 3. Encoding Thresholds (Redis 7.x)

### Hash

| Encoding | Trigger | Undo trigger |
|----------|---------|--------------|
| listpack | ≤ 512 fields AND each value < 128B | > 512 fields OR value ≥ 128B |
| hashtable | > 512 fields OR any value ≥ 128B | Cannot auto-revert |

Config: `hash-max-listpack-entries` (default 512), `hash-max-listpack-value` (default 128)

### List

| Encoding | Trigger |
|----------|---------|
| quicklist (linked list of ziplists) | Default in Redis 7 |
| listpack | When `list-compress-depth` > 0 |
| linked list (plain) | Legacy, rarely used |

Config: `list-max-ziplist-size` (default 8KB per node), `list-compress-depth` (default 0)

### Set

| Encoding | Trigger | Undo trigger |
|----------|---------|--------------|
| intset | ≤ 512 entries AND all are integers | > 512 entries OR any non-integer |
| hashtable | > 512 entries OR any non-integer | Cannot auto-revert |

Config: `set-max-intset-entries` (default 512)

### Sorted Set

| Encoding | Trigger | Undo trigger |
|----------|---------|--------------|
| listpack-zset | ≤ 128 items AND each member < 64B | > 128 items OR member ≥ 64B |
| skiplist+hashtable | > 128 items OR member ≥ 64B | Cannot auto-revert |

Config: `zset-max-listpack-entries` (default 128), `zset-max-listpack-value` (default 64)

### Kiểm tra encoding

```txt
redis-cli OBJECT ENCODING <key>
redis-cli DEBUG OBJECT-ENCODING <key>
redis-cli OBJECT FREQ <key>        -- eviction frequency (LFU)
redis-cli MEMORY USAGE <key>        -- memory bytes
redis-cli MEMORY STATS <key>       -- detailed memory breakdown
```

---

## 4. Memory Comparison Snippet

```bash
# =========================================
# Memory: 1 Hash (100 fields) vs 100 String keys
# =========================================

# Setup: Hash with 100 fields
redis-cli DEL memtest:hash memtest:str
OK

# Add 100 fields to Hash
redis-cli HSET memtest:hash \
  f01 v01 f02 v02 f03 v03 f04 v04 f05 v05 \
  f06 v06 f07 v07 f08 v08 f09 v09 f10 v10 \
  f11 v11 f12 v12 f13 v13 f14 v14 f15 v15 \
  f16 v16 f17 v17 f18 v18 f19 v19 f20 v20 \
  f21 v21 f22 v22 f23 v23 f24 v24 f25 v25 \
  f26 v26 f27 v27 f28 v28 f29 v29 f30 v30 \
  f31 v31 f32 v32 f33 v33 f34 v34 f35 v35 \
  f36 v36 f37 v37 f38 v38 f39 v39 f40 v40 \
  f41 v41 f42 v42 f43 v43 f44 v44 f45 v45 \
  f46 v46 f47 v47 f48 v48 f49 v49 f50 v50 \
  f51 v51 f52 v52 f53 v53 f54 v54 f55 v55 \
  f56 v56 f57 v57 f58 v58 f59 v59 f60 v60 \
  f61 v61 f62 v62 f63 v63 f64 v64 f65 v65 \
  f66 v66 f67 v67 f68 v68 f69 v69 f70 v70 \
  f71 v71 f72 v72 f73 v73 f74 v74 f75 v75 \
  f76 v76 f77 v77 f78 v78 f79 v79 f80 v80 \
  f81 v81 f82 v82 f83 v83 f84 v84 f85 v85 \
  f86 v86 f87 v87 f88 v88 f89 v89 f90 v90 \
  f91 v91 f92 v92 f93 v93 f94 v94 f95 v95 \
  f96 v96 f97 v97 f98 v98 f99 v99 f100 v100

# Check encoding
redis-cli OBJECT ENCODING memtest:hash
# Expected: listpack (100 fields, each < 128B)

# Measure memory
redis-cli MEMORY USAGE memtest:hash
# Expected: ~2200 bytes (very compact)

# Setup: 100 String keys
redis-cli SET memtest:str:f01 v01
redis-cli SET memtest:str:f02 v02
... (repeat for 100 keys)

# Check memory per key
redis-cli MEMORY USAGE memtest:str:f01
# Expected: ~100 bytes per key (SDS overhead per key)

# Total: 100 String keys × ~100B = ~10,000 bytes
# vs Hash: ~2,200 bytes
# Hash saves ~78% memory
```

**Expected result:**

```
memtest:hash (listpack, 100 fields): ~2,200 bytes
100 String keys:                       ~10,000 bytes
Memory saving with Hash:               ~78%
```

**Nhưng**: Nếu Hash vượt 512 fields → hashtable → ~7,200 bytes → advantage giảm nhưng vẫn tốt hơn 100 String keys (~10,000 bytes).

---

## 5. Go Code Snippets (go-redis/v9)

### 5.1 User Profile Cache với Hash

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type UserProfile struct {
	ID        int64  `json:"id"`
	Name      string `json:"name"`
	Email     string `json:"email"`
	AvatarURL string `json:"avatar_url"`
	Status    string `json:"status"`
	Followers int64  `json:"followers"`
}

func userProfileKey(userID int64) string {
	return fmt.Sprintf("user:profile:%d", userID)
}

// SetUserProfile lưu profile vào Hash
func SetUserProfile(ctx context.Context, rdb *redis.Client, profile *UserProfile) error {
	key := userProfileKey(profile.ID)
	pipe := rdb.Pipeline()
	pipe.HSet(ctx, key,
		"id", profile.ID,
		"name", profile.Name,
		"email", profile.Email,
		"avatar_url", profile.AvatarURL,
		"status", profile.Status,
		"followers", profile.Followers,
	)
	pipe.Expire(ctx, key, 1*time.Hour) // TTL 1 giờ
	_, err := pipe.Exec(ctx)
	return err
}

// GetUserProfile lấy toàn bộ profile từ Hash
func GetUserProfile(ctx context.Context, rdb *redis.Client, userID int64) (*UserProfile, error) {
	key := userProfileKey(userID)
	result, err := rdb.HGetAll(ctx, key).Result()
	if err != nil {
		return nil, err
	}
	if len(result) == 0 {
		return nil, redis.Nil
	}
	profile := &UserProfile{}
	profile.ID, _ = fmt.Sscan(result["id"], &profile.ID)
	profile.Name = result["name"]
	profile.Email = result["email"]
	profile.AvatarURL = result["avatar_url"]
	profile.Status = result["status"]
	profile.Followers, _ = fmt.Sscan(result["followers"], &profile.Followers)
	return profile, nil
}

// GetUserField lấy 1 field cụ thể - O(1)
func GetUserName(ctx context.Context, rdb *redis.Client, userID int64) (string, error) {
	return rdb.HGet(ctx, userProfileKey(userID), "name").Result()
}

// IncrementFollowers atomic increment
func IncrementFollowers(ctx context.Context, rdb *redis.Client, userID int64) (int64, error) {
	return rdb.HIncrBy(ctx, userProfileKey(userID), "followers", 1).Result()
}

// UpdateProfilePartial chỉ update 1 field - không cần GET + SET full object
func UpdateUserStatus(ctx context.Context, rdb *redis.Client, userID int64, status string) error {
	return rdb.HSet(ctx, userProfileKey(userID), "status", status).Err()
}
```

### 5.2 Tag System với Set

```go
package main

import (
	"context"
	"fmt"

	"github.com/redis/go-redis/v9"
)

// AddTagsToProduct thêm tags cho product
func AddTagsToProduct(ctx context.Context, rdb *redis.Client, productID int64, tags []string) (int64, error) {
	key := fmt.Sprintf("product:tags:%d", productID)
	return rdb.SAdd(ctx, key, tags).Result()
}

// RemoveTagFromProduct xóa 1 tag
func RemoveTagFromProduct(ctx context.Context, rdb *redis.Client, productID int64, tag string) (int64, error) {
	key := fmt.Sprintf("product:tags:%d", productID)
	return rdb.SRem(ctx, key, tag).Result()
}

// HasTag kiểm tra product có tag không - O(1)
func HasTag(ctx context.Context, rdb *redis.Client, productID int64, tag string) (bool, error) {
	key := fmt.Sprintf("product:tags:%d", productID)
	return rdb.SIsMember(ctx, key, tag).Result()
}

// GetProductTags lấy tất cả tags - dùng SSCAN cho production
func GetProductTags(ctx context.Context, rdb *redis.Client, productID int64) ([]string, error) {
	key := fmt.Sprintf("product:tags:%d", productID)
	// Cảnh báo: SMEMBERS block thread với set lớn
	// Dùng SSCAN thay thế trong production
	return rdb.SMembers(ctx, key).Result()
}

// FindProductsByTags tìm products match ALL tags (intersection)
func FindProductsByTags(ctx context.Context, rdb *redis.Client, tags []string) ([]int64, error) {
	if len(tags) == 0 {
		return nil, nil
	}
	keys := make([]string, len(tags))
	for i, tag := range tags {
		keys[i] = fmt.Sprintf("tag:products:%s", tag)
	}
	result, err := rdb.SInter(ctx, keys...).Result()
	if err != nil {
		return nil, err
	}
	productIDs := make([]int64, 0, len(result))
	for _, r := range result {
		var id int64
		fmt.Sscanf(r, "%d", &id)
		productIDs = append(productIDs, id)
	}
	return productIDs, nil
}

// GetTagCount đếm số products có tag - O(1) với SCARD
func GetTagCount(ctx context.Context, rdb *redis.Client, tag string) (int64, error) {
	key := fmt.Sprintf("tag:products:%s", tag)
	return rdb.SCard(ctx, key).Result()
}
```

### 5.3 Leaderboard với Sorted Set

```go
package main

import (
	"context"
	"fmt"
	"strconv"

	"github.com/redis/go-redis/v9"
)

const leaderboardKey = "leaderboard:global"

// AddScore thêm/update score của player
func AddScore(ctx context.Context, rdb *redis.Client, playerID string, score float64) error {
	return rdb.ZAdd(ctx, leaderboardKey, redis.Z{
		Score:  score,
		Member: playerID,
	}).Err()
}

// IncrementScore atomic score increment - dùng cho live game
func IncrementScore(ctx context.Context, rdb *redis.Client, playerID string, delta float64) (float64, error) {
	return rdb.ZIncrBy(ctx, leaderboardKey, delta, playerID).Result()
}

// GetRank lấy rank của player (0-indexed, ascending)
func GetRank(ctx context.Context, rdb *redis.Client, playerID string) (int64, error) {
	rank, err := rdb.ZRank(ctx, leaderboardKey, playerID).Result()
	if err == redis.Nil {
		return -1, nil
	}
	return rank + 1, err // convert to 1-indexed
}

// GetTopN lấy top N players - dùng ZREVRANGE vì score descending
func GetTopN(ctx context.Context, rdb *redis.Client, n int64) ([]redis.Z, error) {
	return rdb.ZRevRangeWithScores(ctx, leaderboardKey, 0, n-1).Result()
}

// GetPlayerScore lấy score của player - O(1)
func GetPlayerScore(ctx context.Context, rdb *redis.Client, playerID string) (float64, error) {
	return rdb.ZScore(ctx, leaderboardKey, playerID).Result()
}

// GetPlayerRankAndScore lấy cả rank và score trong 1 round-trip
func GetPlayerRankAndScore(ctx context.Context, rdb *redis.Client, playerID string) (rank int64, score float64, err error) {
	pipe := rdb.Pipeline()
	rankCmd := pipe.ZRank(ctx, leaderboardKey, playerID)
	scoreCmd := pipe.ZScore(ctx, leaderboardKey, playerID)
	_, err = pipe.Exec(ctx)
	if rankCmd.Val() == 0 && scoreCmd.Val() == 0 && rankCmd.Err() == redis.Nil {
		return -1, 0, redis.Nil
	}
	if err != nil && rankCmd.Err() != nil {
		return -1, 0, err
	}
	return rankCmd.Val() + 1, scoreCmd.Val(), nil
}

// GetPlayersAroundMe lấy players xung quanh player (for matchmaking)
func GetPlayersAroundMe(ctx context.Context, rdb *redis.Client, playerID string, rangeSize int64) ([]redis.Z, error) {
	rank, err := rdb.ZRank(ctx, leaderboardKey, playerID).Result()
	if err != nil {
		return nil, err
	}
	start := rank - rangeSize
	if start < 0 {
		start = 0
	}
	end := rank + rangeSize
	return rdb.ZRevRangeWithScores(ctx, leaderboardKey, start, end).Result()
}

// TrimLeaderboard giữ chỉ top N - dùng cho bounded leaderboard
func TrimLeaderboard(ctx context.Context, rdb *redis.Client, keepTopN int64) (int64, error) {
	return rdb.ZRemRangeByRank(ctx, leaderboardKey, 0, -keepTopN-1).Result()
}

// GetRankingsByScoreRange lấy players trong score range
func GetRankingsByScoreRange(ctx context.Context, rdb *redis.Client, minScore, maxScore float64) ([]redis.Z, error) {
	return rdb.ZRevRangeByScoreWithScores(ctx, leaderboardKey, &redis.ZRangeBy{
		Min: strconv.FormatFloat(minScore, 'f', -1, 64),
		Max: strconv.FormatFloat(maxScore, 'f', -1, 64),
	}).Result()
}
```

---

## 6. Docker Compose Setup (Day 2)

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    container_name: redis-day2
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save ""          # Disable RDB for testing
      --appendonly no    # Disable AOF for testing
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

volumes:
  redis_data:
```

---

## 7. Links & References

- [Redis Data Types Tutorial](https://redis.io/docs/data-types/)
- [Redis Strings](https://redis.io/docs/data-types/strings/)
- [Redis Lists](https://redis.io/docs/data-types/lists/)
- [Redis Hashes](https://redis.io/docs/data-types/hashes/)
- [Redis Sets](https://redis.io/docs/data-types/sets/)
- [Redis Sorted Sets](https://redis.io/docs/data-types/sorted-sets/)
- antirez blog: ["On Redis Data Structures"](http://oldblog.antirez.com/post/redis-underlying-data-structures-1.html) (2010 — still relevant)
- antirez blog: ["Redis internals: SDS"](http://oldblog.antirez.com/post/redis-and-random-seeds.html)
- Redis source: [`t_list.c`](https://github.com/redis/redis/blob/unstable/src/t_list.c), [`t_hash.c`](https://github.com/redis/redis/blob/unstable/src/t_hash.c), [`t_set.c`](https://github.com/redis/redis/blob/unstable/src/t_set.c), [`t_zset.c`](https://github.com/redis/redis/blob/unstable/src/t_zset.c)
- Shopify Engineering: ["Stack Overflow: Redis in a Discrete Mathematics Course"](https://shopify.engineering/) (session cart pattern)
- Twitter Engineering: ["Using Redis at Twitter"](https://blog.twitter.com/engineering/) (timeline with Sorted Set)
