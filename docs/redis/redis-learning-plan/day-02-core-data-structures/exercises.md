# Day 2: Core Data Structures — Exercises

**Thời gian**: ~2 giờ
**Mục tiêu**: Nắm vững 5 core data structures, benchmark memory, implement production patterns

---

## 1. Warm-up Exercises (15-20 phút)

Thực hành bằng `redis-cli`. Mỗi command có expected output.

### 1.1 String Operations

```txt
redis-cli

SET product:001 '{"name":"iPhone 15","price":999}' EX 3600
GET product:001
APPEND product:001 '-plus'
GETRANGE product:001 0 9
STRLEN product:001
INCR order:counter
INCR order:counter
GET order:counter
```

**Expected output:**
```
OK
{"name":"iPhone 15","price":999}
{"name":"iPhone 15","price":999}-plus
{"name":"i
29
(integer) 1
(integer) 2
2
```

### 1.2 List Operations

```txt
RPUSH queue:jobs job:A job:B job:C
LPUSH queue:jobs job:START
LRANGE queue:jobs 0 -1
LLEN queue:jobs
LPOP queue:jobs
LRANGE queue:jobs 0 1
BLPOP queue:jobs 1   -- timeout 1s, queue sẽ empty
```

**Expected output:**
```
(integer) 3
(integer) 4
1) "job:START"
2) "job:A"
3) "job:B"
4) "job:C"
(integer) 4
"job:START"
1) "job:A"
2) "job:B"
(nil)   -- nil after 1s timeout
```

### 1.3 Hash Operations

```txt
HSET user:100 name "Alice" email "alice@example.com" followers 1500
HGET user:100 name
HMGET user:100 name followers
HINCRBY user:100 followers 10
HGETALL user:100
HEXISTS user:100 email
HSTRLEN user:100 name
```

**Expected output:**
```
(integer) 3
"Alice"
1) "Alice"
2) "1510"
1) "name"
2) "Alice"
3) "email"
4) "alice@example.com"
5) "followers"
6) "1510"
(integer) 1
(integer) 5
```

### 1.4 Set Operations

```txt
SADD product:tags:001 electronics wireless noise-canceling
SADD product:tags:002 electronics bluetooth headphones
SISMEMBER product:tags:001 wireless
SMEMBERS product:tags:001
SCARD product:tags:001
SINTER product:tags:001 product:tags:002
SUNION product:tags:001 product:tags:002
SDIFF product:tags:001 product:tags:002
```

**Expected output:**
```
(integer) 3
(integer) 1
1) "electronics"
2) "wireless"
3) "noise-canceling"
(integer) 3
1) "electronics"
1) "electronics"
2) "wireless"
3) "noise-canceling"
4) "bluetooth"
5) "headphones"
1) "wireless"
2) "noise-canceling"
```

### 1.5 Sorted Set Operations

```txt
ZADD leaderboard 1500 alice 1200 bob 1800 carol 1500 david
ZREVRANGE leaderboard 0 2 WITHSCORES
ZRANK leaderboard alice
ZREVRANK leaderboard alice
ZSCORE leaderboard carol
ZINCRBY leaderboard 100 alice
ZREVRANGE leaderboard 0 0 WITHSCORES
ZRANGEBYSCORE leaderboard 1500 1600 WITHSCORES
```

**Expected output:**
```
(integer) 4
1) "carol"
2) "1800"
3) "alice"
4) "1500"
5) "david"
6) "1500"
(integer) 2      -- alice rank 0-indexed: bob=0, carol=1, alice=2, david=3
(integer) 1       -- reversed: carol=0, alice=1, david=2, bob=3
"1800"
"1600"
1) "alice"
2) "1600"
1) "alice"
2) "1600"
3) "david"
4) "1500"
```

---

## 2. Hands-on Lab (60-70 phút)

### 2.1 Setup

**File:** `day-02/exercises/docker-compose.yml`

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    container_name: redis-day2
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  app:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - REDIS_ADDR=redis:6379
    volumes:
      - .:/app
```

**File:** `day-02/exercises/Dockerfile`

```docker
FROM golang:1.22-alpine
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
```

**File:** `day-02/exercises/go.mod`

```go
module day02-exercises

go 1.22

require github.com/redis/go-redis/v9 v9.5.1
```

---

### 2.2 Exercise 1: User Profile Cache với Hash

**File:** `day-02/exercises/ex1_user_profile/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
)

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis connection failed: %v", err)
	}
	fmt.Println("Connected to Redis")

	// TODO 1: Set user profile using Hash (HSET)
	// Fields: id, name, email, avatar_url, status, followers
	// Key: user:profile:{id}

	// TODO 2: Get user profile using HGETALL

	// TODO 3: Get single field "email" using HGET - O(1) operation

	// TODO 4: Increment followers by 1 using HINCRBY

	// TODO 5: Update status from "active" to "premium" using HSET

	// TODO 6: Check if field "phone" exists using HEXISTS

	// TODO 7: Get multiple fields (name, followers) using HMGET

	// TODO 8: Measure memory of this Hash using MEMORY USAGE

	// TODO 9: Add TTL of 1 hour using EXPIRE

	fmt.Println("\n--- Running all operations ---")
	runAll(ctx, rdb)
}

func runAll(ctx context.Context, rdb *redis.Client) {
	userID := int64(12345)
	key := fmt.Sprintf("user:profile:%d", userID)

	// Clean up
	rdb.Del(ctx, key)

	// TODO 1: HSET - set multiple fields
	pipe := rdb.Pipeline()
	pipe.HSet(ctx, key, "id", userID, "name", "Alice", "email", "alice@example.com",
		"avatar_url", "/avatars/12345.jpg", "status", "active", "followers", 1500)
	pipe.Expire(ctx, key, 1*time.Hour)
	_, err := pipe.Exec(ctx)
	if err != nil {
		log.Fatalf("HSET failed: %v", err)
	}
	fmt.Printf("TODO 1: HSET - OK, %d fields set\n", 6)

	// TODO 2: HGETALL - get all fields
	all, err := rdb.HGetAll(ctx, key).Result()
	if err != nil {
		log.Fatalf("HGETALL failed: %v", err)
	}
	fmt.Printf("TODO 2: HGETALL - %d fields retrieved\n", len(all))

	// TODO 3: HGET - single field O(1)
	email, err := rdb.HGet(ctx, key, "email").Result()
	if err != nil {
		log.Fatalf("HGET failed: %v", err)
	}
	fmt.Printf("TODO 3: HGET 'email' - %s\n", email)

	// TODO 4: HINCRBY - atomic increment
	newFollowers, err := rdb.HIncrBy(ctx, key, "followers", 1).Result()
	if err != nil {
		log.Fatalf("HINCRBY failed: %v", err)
	}
	fmt.Printf("TODO 4: HINCRBY followers -> %d\n", newFollowers)

	// TODO 5: HSET - update single field
	err = rdb.HSet(ctx, key, "status", "premium").Err()
	if err != nil {
		log.Fatalf("HSET update failed: %v", err)
	}
	fmt.Println("TODO 5: HSET status -> premium")

	// TODO 6: HEXISTS
	exists, _ := rdb.HExists(ctx, key, "phone").Result()
	fmt.Printf("TODO 6: HEXISTS 'phone' -> %v\n", exists)

	// TODO 7: HMGET
	fields, _ := rdb.HMGet(ctx, key, "name", "followers").Result()
	fmt.Printf("TODO 7: HMGET name,followers -> %v\n", fields)

	// TODO 8: MEMORY USAGE
	bytes, _ := rdb.MemoryUsage(ctx, key).Result()
	fmt.Printf("TODO 8: MEMORY USAGE -> %d bytes (~%.2f KB)\n", bytes, float64(bytes)/1024)

	// TODO 9: EXPIRE
	err = rdb.Expire(ctx, key, 1*time.Hour).Err()
	fmt.Printf("TODO 9: EXPIRE set to 1h\n")
}
```

**Expected output:**
```
Connected to Redis
TODO 1: HSET - OK, 6 fields set
TODO 2: HGETALL - 6 fields retrieved
TODO 3: HGET 'email' - alice@example.com
TODO 4: HINCRBY followers -> 1501
TODO 5: HSET status -> premium
TODO 6: HEXISTS 'phone' -> false
TODO 7: HMGET name,followers -> [Alice 1501]
TODO 8: MEMORY USAGE -> ~350 bytes
TODO 9: EXPIRE set to 1h
```

---

### 2.3 Exercise 2: Tag System với Set

**File:** `day-02/exercises/ex2_tag_system/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/redis/go-redis/v9"
)

// Tags structure:
// product:tags:{product_id} -> Set of tags
// tag:products:{tag_name}   -> Set of product IDs (inverted index)

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis connection failed: %v", err)
	}
	fmt.Println("Connected to Redis")

	// TODO 1: Add tags to product 456 (electronics, wireless, noise-canceling)
	// SADD product:tags:456

	// TODO 2: Add same tags to inverted index (tag:products:electronics, etc.)
	// SADD tag:products:{tag} 456

	// TODO 3: Check if product has tag "wireless" - O(1)
	// SISMEMBER

	// TODO 4: Add product 789 with overlapping tags (electronics, bluetooth)
	// Build inverted index for it

	// TODO 5: Find products matching ALL tags: electronics + wireless
	// SINTER tag:products:electronics tag:products:wireless

	// TODO 6: Count products per tag using SCARD - O(1)

	// TODO 7: Remove tag "noise-canceling" from product 456
	// SREM

	// TODO 8: Get all tags for product 456 (careful with large sets!)
	// SMEMBERS - chỉ OK cho small set

	runAll(ctx, rdb)
}

func toAny(values []string) []interface{} {
	result := make([]interface{}, len(values))
	for i, value := range values {
		result[i] = value
	}
	return result
}

func runAll(ctx context.Context, rdb *redis.Client) {
	// Setup products
	product1 := int64(456)
	product2 := int64(789)

	tags1 := []string{"electronics", "wireless", "noise-canceling"}
	tags2 := []string{"electronics", "bluetooth", "headphones"}

	// Clean up
	rdb.Del(ctx, fmt.Sprintf("product:tags:%d", product1))
	rdb.Del(ctx, fmt.Sprintf("product:tags:%d", product2))
	for _, tag := range tags1 {
		rdb.Del(ctx, fmt.Sprintf("tag:products:%s", tag))
	}
	for _, tag := range tags2 {
		rdb.Del(ctx, fmt.Sprintf("tag:products:%s", tag))
	}

	// TODO 1: Add tags to product
	key1 := fmt.Sprintf("product:tags:%d", product1)
	n, _ := rdb.SAdd(ctx, key1, toAny(tags1)...).Result()
	fmt.Printf("TODO 1: SADD product:tags:456 -> %d tags added\n", n)

	// TODO 2: Build inverted index
	for _, tag := range tags1 {
		tagKey := fmt.Sprintf("tag:products:%s", tag)
		rdb.SAdd(ctx, tagKey, product1)
	}
	for _, tag := range tags2 {
		tagKey := fmt.Sprintf("tag:products:%s", tag)
		rdb.SAdd(ctx, tagKey, product2)
	}
	fmt.Println("TODO 2: Inverted index built")

	// TODO 3: SISMEMBER - O(1) membership check
	isWireless, _ := rdb.SIsMember(ctx, key1, "wireless").Result()
	fmt.Printf("TODO 3: SISMEMBER product:456 has 'wireless' -> %v\n", isWireless)

	// TODO 4: Add product 789 tags
	key2 := fmt.Sprintf("product:tags:%d", product2)
	rdb.SAdd(ctx, key2, toAny(tags2)...)
	fmt.Printf("TODO 4: Product 789 tags added: %v\n", tags2)

	// TODO 5: SINTER - find products matching electronics + wireless
	electronicsProducts, _ := rdb.SInter(ctx,
		"tag:products:electronics",
		"tag:products:wireless",
	).Result()
	fmt.Printf("TODO 5: SINTER electronics∩wireless -> %v\n", electronicsProducts)

	// TODO 6: SCARD - O(1) count
	electronicsCount, _ := rdb.SCard(ctx, "tag:products:electronics").Result()
	fmt.Printf("TODO 6: SCARD tag:electronics -> %d products\n", electronicsCount)

	// TODO 7: SREM - remove tag
	removed, _ := rdb.SRem(ctx, key1, "noise-canceling").Result()
	fmt.Printf("TODO 7: SREM noise-canceling from product 456 -> %d removed\n", removed)

	// TODO 8: SMEMBERS - list all tags (OK vì small set)
	allTags, _ := rdb.SMembers(ctx, key1).Result()
	fmt.Printf("TODO 8: SMEMBERS product:456 -> %v\n", allTags)
}
```

**Expected output:**
```
Connected to Redis
TODO 1: SADD product:tags:456 -> 3 tags added
TODO 2: Inverted index built
TODO 3: SISMEMBER product:456 has 'wireless' -> true
TODO 4: Product 789 tags added: [electronics bluetooth headphones]
TODO 5: SINTER electronics∩wireless -> [456]
TODO 6: SCARD tag:electronics -> 2 products
TODO 7: SREM noise-canceling from product 456 -> 1 removed
TODO 8: SMEMBERS product:456 -> [electronics wireless]
```

`SMEMBERS` và `SINTER` không đảm bảo thứ tự; output thực tế có thể đảo vị trí member.

---

### 2.4 Exercise 3: Leaderboard với Sorted Set

**File:** `day-02/exercises/ex3_leaderboard/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
)

const leaderboardKey = "leaderboard:global"

type Player struct {
	ID    string
	Score float64
}

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis connection failed: %v", err)
	}
	fmt.Println("Connected to Redis")

	// TODO 1: Add initial scores using ZADD
	// alice: 1500, bob: 1200, carol: 1800, david: 1500, eve: 2000

	// TODO 2: Increment alice's score by 100 (she won a match!)
	// ZINCRBY

	// TODO 3: Get alice's rank (0-indexed from ZRANK, convert to 1-indexed)

	// TODO 4: Get top 3 players using ZREVRANGE WITHSCORES
	// ZREVRANGE leaderboard 0 2 WITHSCORES

	// TODO 5: Get alice's score using ZSCORE - O(1)

	// TODO 6: Get players ranked 2-4 using ZRANGE (ascending) with WITHSCORES

	// TODO 7: Get total players using ZCARD - O(1)

	// TODO 8: Simulate leaderboard update - alice gets 200 more points, eve loses 500
	// Pipeline 2 ZINCRBY + 1 ZREVRANGE

	// TODO 9: BONUS - Find your rank without knowing all players (simulate 1000 players)
	// Generate 1000 players, add random scores, then find rank of a specific player

	runAll(ctx, rdb)
}

func runAll(ctx context.Context, rdb *redis.Client) {
	// Clean up
	rdb.Del(ctx, leaderboardKey)
	rdb.Del(ctx, "leaderboard:large")

	// TODO 1: ZADD - add players
	players := []redis.Z{
		{Score: 1500, Member: "alice"},
		{Score: 1200, Member: "bob"},
		{Score: 1800, Member: "carol"},
		{Score: 1500, Member: "david"},
		{Score: 2000, Member: "eve"},
	}
	rdb.ZAdd(ctx, leaderboardKey, players...)
	fmt.Printf("TODO 1: ZADD 5 players -> OK\n")

	// TODO 2: ZINCRBY - increment score
	newScore, _ := rdb.ZIncrBy(ctx, leaderboardKey, 100, "alice").Result()
	fmt.Printf("TODO 2: ZINCRBY alice +100 -> score now %.0f\n", newScore)

	// TODO 3: ZRANK -> 1-indexed
	rank, _ := rdb.ZRank(ctx, leaderboardKey, "alice").Result()
	fmt.Printf("TODO 3: ZRANK alice -> position %d out of 5\n", rank+1)

	// TODO 4: ZREVRANGE - top 3 (descending by score)
	top3, _ := rdb.ZRevRangeWithScores(ctx, leaderboardKey, 0, 2).Result()
	fmt.Println("TODO 4: Top 3 players:")
	for i, z := range top3 {
		fmt.Printf("  #%d: %s (%.0f points)\n", i+1, z.Member, z.Score)
	}

	// TODO 5: ZSCORE - O(1)
	aliceScore, _ := rdb.ZScore(ctx, leaderboardKey, "alice").Result()
	fmt.Printf("TODO 5: ZSCORE alice -> %.0f\n", aliceScore)

	// TODO 6: ZRANGE 2-4
	players2to4, _ := rdb.ZRangeWithScores(ctx, leaderboardKey, 1, 3).Result()
	fmt.Println("TODO 6: Rank 2-4 (ascending):")
	for _, z := range players2to4 {
		fmt.Printf("  %s: %.0f\n", z.Member, z.Score)
	}

	// TODO 7: ZCARD
	count, _ := rdb.ZCard(ctx, leaderboardKey).Result()
	fmt.Printf("TODO 7: ZCARD -> %d players\n", count)

	// TODO 8: Pipeline - 2 updates + query
	pipe := rdb.Pipeline()
	pipe.ZIncrBy(ctx, leaderboardKey, 200, "alice")
	pipe.ZIncrBy(ctx, leaderboardKey, -500, "eve")
	topCmd := pipe.ZRevRangeWithScores(ctx, leaderboardKey, 0, 4)
	if _, err := pipe.Exec(ctx); err != nil {
		log.Fatalf("pipeline failed: %v", err)
	}
	newTop, _ := topCmd.Result()
	fmt.Println("TODO 8: After pipeline update - Top 5:")
	for i, z := range newTop {
		fmt.Printf("  #%d: %s (%.0f points)\n", i+1, z.Member, z.Score)
	}

	// TODO 9: Large leaderboard - 1000 players
	simulateLargeLeaderboard(ctx, rdb)
}

func simulateLargeLeaderboard(ctx context.Context, rdb *redis.Client) {
	fmt.Println("\n--- Bonus: 1000-player leaderboard ---")

	// Generate 1000 players with random scores
	players := make([]redis.Z, 1000)
	for i := 0; i < 1000; i++ {
		players[i] = redis.Z{
			Member: fmt.Sprintf("player:%04d", i),
			Score: float64(i * 10), // deterministic for testing
		}
	}
	rdb.ZAdd(ctx, "leaderboard:large", players...)

	// Find rank of player:499
	start := time.Now()
	rank, _ := rdb.ZRank(ctx, "leaderboard:large", "player:0499").Result()
	elapsed := time.Since(start)
	fmt.Printf("TODO 9a: ZRANK player:0499 -> rank %d (elapsed: %s)\n", rank+1, elapsed)

	// Get top 10
	start = time.Now()
	top10, _ := rdb.ZRevRangeWithScores(ctx, "leaderboard:large", 0, 9).Result()
	elapsed = time.Since(start)
	fmt.Printf("TODO 9b: ZREVRANGE 0-9 WITHSCORES -> top 10 (elapsed: %s)\n", elapsed)
	for i, z := range top10 {
		if i < 3 {
			fmt.Printf("  #%d: %s (%.0f)\n", i+1, z.Member, z.Score)
		}
	}
	fmt.Printf("  ... (%d total players)\n", len(top10))

	// Score range query: players with score 3000-5000
	start = time.Now()
	rangeResults, _ := rdb.ZRangeByScoreWithScores(ctx, "leaderboard:large",
		&redis.ZRangeBy{Min: "3000", Max: "5000"}).Result()
	elapsed = time.Since(start)
	fmt.Printf("TODO 9c: ZRANGEBYSCORE 3000-5000 -> %d players (elapsed: %s)\n",
		len(rangeResults), elapsed)
}
```

**Expected output:**
```
Connected to Redis
TODO 1: ZADD 5 players -> OK
TODO 2: ZINCRBY alice +100 -> score now 1600
TODO 3: ZRANK alice -> position 3 out of 5
TODO 4: Top 3 players:
  #1: eve (2000 points)
  #2: carol (1800 points)
  #3: alice (1600 points)
TODO 5: ZSCORE alice -> 1600
TODO 6: Rank 2-4 (ascending):
  bob: 1200
  david: 1500
  alice: 1600
TODO 7: ZCARD -> 5 players
TODO 8: After pipeline update - Top 5:
  #1: carol (1800 points)
  #2: alice (1800 points)
  #3: eve (1500 points)
  #4: david (1500 points)
  #5: bob (1200 points)
--- Bonus: 1000-player leaderboard ---
TODO 9a: ZRANK player:0499 -> rank 500 (elapsed: ~0.2ms)
TODO 9b: ZREVRANGE 0-9 WITHSCORES -> top 10 (elapsed: ~0.3ms)
TODO 9c: ZRANGEBYSCORE 3000-5000 -> ~200 players (elapsed: ~0.5ms)
```

---

## 3. Challenge Exercise (30-40 phút)

### Benchmark Memory Usage: Hash vs Multiple String Keys vs 1 Big Hash

**Mục tiêu**: Đo và so sánh memory usage của 3 chiến lược data modeling cho 1000 user profiles.

**File:** `day-02/exercises/challenge/main.go`

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/redis/go-redis/v9"
)

const totalUsers = 1000
const fieldsPerUser = 10

func main() {
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis connection failed: %v", err)
	}
	fmt.Println("Connected to Redis")
	fmt.Printf("Setup: %d users, %d fields each\n\n", totalUsers, fieldsPerUser)

	// Method 1: Multiple String keys (1 per field)
	method1(ctx, rdb)

	// Method 2: Hash per user (1 key, multiple fields)
	method2(ctx, rdb)

	// Method 3: 1 big Hash (all users) - ANTI-PATTERN
	method3(ctx, rdb)

	// Summary comparison
	printSummary(ctx, rdb)
}

func deleteByPattern(ctx context.Context, rdb *redis.Client, pattern string) {
	var keys []string
	iter := rdb.Scan(ctx, 0, pattern, 100).Iterator()
	for iter.Next(ctx) {
		keys = append(keys, iter.Val())
	}
	if len(keys) > 0 {
		rdb.Del(ctx, keys...)
	}
}

func method1(ctx context.Context, rdb *redis.Client) {
	fmt.Println("=== Method 1: Multiple String keys ===")

	prefix := "mem:str:user"
	deleteByPattern(ctx, rdb, prefix+":*")

	var keys []string
	// Generate keys
	for userID := 1; userID <= totalUsers; userID++ {
		for fieldID := 1; fieldID <= fieldsPerUser; fieldID++ {
			key := fmt.Sprintf("%s:%d:field%d", prefix, userID, fieldID)
			value := fmt.Sprintf("value_%d_%d", userID, fieldID)
			rdb.Set(ctx, key, value, 0)
			keys = append(keys, key)
		}
	}

	// Measure memory
	totalBytes := int64(0)
	for _, key := range keys {
		sz, _ := rdb.MemoryUsage(ctx, key).Result()
		totalBytes += sz
	}

	fmt.Printf("Method 1 complete: %d keys, total memory: %.2f KB\n",
		len(keys), float64(totalBytes)/1024)
	if len(keys) > 0 {
		sampleBytes, _ := rdb.MemoryUsage(ctx, keys[0]).Result()
		fmt.Printf("  (Sample: %s = %d bytes)\n", keys[0], sampleBytes)
	}
}

func method2(ctx context.Context, rdb *redis.Client) {
	fmt.Println("\n=== Method 2: Hash per user ===")

	prefix := "mem:hash:user"
	deleteByPattern(ctx, rdb, prefix+":*")
	keys := make([]string, 0, totalUsers)

	// Generate
	for userID := 1; userID <= totalUsers; userID++ {
		key := fmt.Sprintf("%s:%d", prefix, userID)
		keys = append(keys, key)
		args := make([]interface{}, 0, fieldsPerUser*2)
		for fieldID := 1; fieldID <= fieldsPerUser; fieldID++ {
			args = append(args, fmt.Sprintf("field%d", fieldID),
				fmt.Sprintf("value_%d_%d", userID, fieldID))
		}
		rdb.HSet(ctx, key, args...)
	}

	// Measure
	totalBytes := int64(0)
	for _, key := range keys {
		sz, _ := rdb.MemoryUsage(ctx, key).Result()
		totalBytes += sz
	}

	fmt.Printf("Method 2 complete: %d Hash keys, total memory: %.2f KB\n",
		len(keys), float64(totalBytes)/1024)
}

func method3(ctx context.Context, rdb *redis.Client) {
	fmt.Println("\n=== Method 3: 1 Big Hash (ALL users) ===")

	bigKey := "mem:big:allusers"
	rdb.Del(ctx, bigKey)

	// Add ALL users into 1 Hash
	args := make([]interface{}, 0, totalUsers*fieldsPerUser*2)
	for userID := 1; userID <= totalUsers; userID++ {
		for fieldID := 1; fieldID <= fieldsPerUser; fieldID++ {
			fieldName := fmt.Sprintf("user%d:field%d", userID, fieldID)
			fieldValue := fmt.Sprintf("value_%d_%d", userID, fieldID)
			args = append(args, fieldName, fieldValue)
		}
	}
	rdb.HSet(ctx, bigKey, args...)

	sz, _ := rdb.MemoryUsage(ctx, bigKey).Result()
	fmt.Printf("Method 3 complete: 1 big Hash, total memory: %.2f KB\n",
		float64(sz)/1024)
}

func printSummary(ctx context.Context, rdb *redis.Client) {
	fmt.Println("\n=== Summary ===")
	// Run the actual memory test and print comparison
	// (Implementation hint: use MEMORY STATS and INFO memory)

	// Get total memory used by our test keys
	patterns := []string{"mem:str:*", "mem:hash:*", "mem:big:*"}
	for _, pattern := range patterns {
		var totalBytes int64
		var keyCount int
		iter := rdb.Scan(ctx, 0, pattern, 100).Iterator()
		for iter.Next(ctx) {
			key := iter.Val()
			sz, _ := rdb.MemoryUsage(ctx, key).Result()
			totalBytes += sz
			keyCount++
		}
		fmt.Printf("Pattern %s: %d keys, %.2f KB\n",
			pattern, keyCount, float64(totalBytes)/1024)
	}
}
```

**Challenge questions:**

1. **Đo memory thực tế**: Chạy code, ghi lại memory cho mỗi method. Giải thích tại sao method 3 (1 big Hash) có memory thấp nhất nhưng vẫn là anti-pattern.

2. **Encoding inspection**: Chạy `OBJECT ENCODING` trên các keys từ mỗi method. Giải thích tại sao Hash dùng listpack trong khi String dùng SDS.

3. **Trade-off analysis**: Với 1 triệu users, method nào scale tốt nhất? Khi nào method 1 (String) lại tốt hơn?

4. **Performance**: Đo latency của `HGET` vs `GET` trong mỗi method cho 1 random field access. Giải thích kết quả.

5. **TTL strategy**: Nếu mỗi user profile có TTL 1 giờ, method nào quản lý TTL hiệu quả nhất?

---

## 4. Reflection Questions

**Q1.** Bạn đang thiết kế hệ thống e-commerce với 10 triệu products. Mỗi product có ~20 fields. Traffic: 50K reads/sec, 5K writes/sec. Đề xuất data modeling strategy. Khi nào dùng Hash? Khi nào dùng String JSON? Khi nào cần chunking?

**Q2.** Rate limiting cần: 1000 requests/phút/user. Dùng Sorted Set với sliding window. Nêu cách implement `ZREMRANGEBYSCORE` để trim old entries. Làm sao để giảm từ 2 commands (ZREMRANGEBYSCORE + ZCARD) xuống 1 command?

**Q3.** Leaderboard có 10 triệu players. Lúc peak, 5K score updates/second. Sorted Set ZADD là O(log N) = O(log 10M) ≈ 23 operations. Với 5K updates/sec → ~115K operations/sec. Đủ hay không? Khi nào cần sharding? Làm sao shard leaderboard?

**Q4.** Tag system với 1 triệu products, mỗi product có 5-20 tags. `SINTER` giữa 2 tags mỗi tag có 100K products → 100K lookups × O(1) = 100K operations. Với 1000 queries/sec → 100M operations/sec. Bằng cách nào Redis xử lý? Pre-computation hay lazy computation?

**Q5.** Bạn phát hiện Hash `session:*` có encoding chuyển từ listpack sang hashtable. Memory tăng 5x. Nguyên nhân và cách fix? Nếu không thể thay đổi application code, có cách nào giảm memory không?

---

## 5. Solution Guide

> ⚠️ **SPOILER WARNING**: Phần này chứa đáp án. Đọc sau khi đã thử làm bài.

---

### Exercise 1: User Profile Cache

**Key design**: `user:profile:{id}`

**Điểm quan trọng**:
- `HSET` với multiple fields = 1 round-trip, atomic
- `HGETALL` OK cho object nhỏ (< 100 fields, listpack encoding)
- `HGET` O(1) — chỉ nên dùng khi cần ≤ 3 fields. Nếu cần > 5 fields → `HGETALL` ít round-trips hơn `HMGET` nhiều lần
- `HINCRBY` atomic — không race condition khi multiple requests update cùng lúc
- `MEMORY USAGE` đo chính xác memory của 1 key + value (không tính key name)

**Expected memory**: ~350-500 bytes cho 6-field Hash (listpack encoding, mỗi value < 128B)

---

### Exercise 2: Tag System

**Key design**:
- `product:tags:{id}` — Set of tags per product
- `tag:products:{tag}` — Inverted index: Set of product IDs per tag

**Điểm quan trọng**:
- Inverted index cho `SINTER` query hiệu quả
- `SISMEMBER` O(1) — kiểm tra tag membership nhanh
- `SMEMBERS` chỉ OK cho small sets (< 1K elements). Production: dùng `SSCAN`
- `SINTER` với 2 sets × 100K elements → ~100K operations → có thể 50-200ms. Pre-compute với `SINTERSTORE` nếu query thường xuyên

**Bonus insight**: Dùng `SUNIONSTORE tag:popular:electronics_bluetooth tag:products:electronics tag:products:bluetooth` để pre-compute common intersection, chạy background job mỗi 5 phút.

---

### Exercise 3: Leaderboard

**Key design**: `leaderboard:global`

**Điểm quan trọng**:
- `ZINCRBY` atomic — dùng cho live score updates (games, competitions)
- `ZREVRANGE 0 9 WITHSCORES` → O(log N + 10) ≈ O(log N) — cực nhanh dù N = 10M
- Pipeline cho multiple operations → giảm RTT từ N × RTT × 2 → RTT × 2
- 1000-player benchmark: ZRANK ~0.2ms (O(log 1000) ≈ 10 steps), ZREVRANGE top-10 ~0.3ms

**Real-world note**: Production leaderboard cần pagination. Dùng cursor-based: `ZRANGE leaderboard {cursor} {cursor + 9} WITHSCORES`, cursor = last score.

---

### Challenge: Memory Comparison

**Expected results (approx, Redis 7.x)**:

```
Method 1 (1000 users × 10 String keys = 10,000 keys):
  Total: ~800,000 bytes (~781 KB)
  Per key: ~80 bytes (SDS overhead + value)

Method 2 (1000 Hash keys × 10 fields):
  Total: ~150,000 bytes (~147 KB) ← BEST
  Per key: ~150 bytes (listpack compact)

Method 3 (1 big Hash, 10,000 fields):
  Total: ~120,000 bytes (~117 KB) ← LOWEST memory
  Per key: ~120 bytes (but hashtable encoding)
```

**Tại sao Method 3 là anti-pattern**:
1. `HGETALL` → O(N) với N = 10,000 → trả về 10K fields = potential 1MB response
2. Single point of failure: 1 key crash → tất cả users affected
3. `HSCAN` cần iterate toàn bộ để tìm 1 user
4. TTL phải ở key-level → không thể expire 1 user riêng lẻ
5. Redis Cluster: 1 big key → hot key problem
6. Encoding chuyển sang hashtable khi > 512 fields → memory spike

**Khi nào Method 1 (String) tốt hơn**:
- Khi fields được access độc lập với high frequency → `MGET` batch
- Khi cần atomic read-modify-write cho entire object → `GET` + `SET` (không phải `HINCRBY`)
- Khi caching full JSON response cho external service

---

### Reflection Answers

**A1. E-commerce product cache (10M products)**:
- Dùng Hash per product: `HSET product:{id} name "..." price 999 ...`
- Hash size: ~20 fields → listpack encoding nếu values < 128B
- Hot products (top 10K): cache in-process (LRU) + Redis Hash
- Cold products: database, Redis là cache layer
- Writes: không cần write-through, dùng cache-aside + TTL 5 phút

**A2. Rate limiting optimization**:
```lua
-- Single Lua script thay thế 2 commands
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, window)
    return {1, limit - count - 1}  -- allowed, remaining
end
return {0, 0}  -- denied, no remaining
```
1 command thay vì 2 → giảm RTT và atomic.

**A3. Leaderboard sharding strategy**:
```go
// Shard by score range (range-based sharding)
func leaderboardShardKey(score float64) string {
    if score >= 10000 { return "leaderboard:shard:5" }  // top 1%
    if score >= 5000  { return "leaderboard:shard:4" }
    if score >= 1000 { return "leaderboard:shard:3" }
    if score >= 100  { return "leaderboard:shard:2" }
    return "leaderboard:shard:1"
}
```
Trade-off: Shard query phức tạp hơn, nhưng mỗi shard nhỏ hơn → ZADD/ZRANGE nhanh hơn.

**A4. SINTER operation internals**:
Redis không pre-compute. `SINTER` chạy lazy:
1. Identify smallest set
2. Iterate smallest set
3. `SISMEMBER` on each element against other sets
4. Collect matches

Với 2 sets × 100K elements: ~100K hashtable lookups → ~5-10ms. Nếu 1000 queries/sec → 5-10 seconds total CPU time. Solution: `SINTERSTORE` pre-compute, update via background job.

**A5. Fix Hash encoding bloat**:
Nguyên nhân: Hash vượt 512 fields hoặc value ≥ 128B → chuyển sang hashtable.

Cách fix mà không đổi application code:
1. Dùng `OBJECT ENCODING` để verify: `redis-cli OBJECT ENCODING session:abc123`
2. Giảm field count: tách 1 large Hash thành 2 smaller Hashes
3. Giảm value size: compress JSON strings > 128B
4. Nếu không fix được: dùng `maxmemory-policy volatile-lru` để evict tự động, giảm memory pressure
5. Dùng `MEMORY PURGE` để defrag sau khi delete fields
