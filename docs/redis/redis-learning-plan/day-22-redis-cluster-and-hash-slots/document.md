# Day 22: Redis Cluster & Hash Slots — Reference Document

---

## 1. CLUSTER Commands Cheat Sheet

### Cluster Management Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER INFO` | `CLUSTER INFO` | Trạng thái cluster: state, slots assigned, nodes, epochs |
| `CLUSTER NODES` | `CLUSTER NODES` | Danh sách tất cả node: ID, addr, flags, slots, connected |
| `CLUSTER SLOTS` | `CLUSTER SLOTS` | Slot ranges và node owner: `[[slot, slot, [node-ip:port,uid], ...]]` |
| `CLUSTER SHARDS` | `CLUSTER SHARDS` | Shard-level view: mỗi shard gồm master + replicas |
| `CLUSTER MEET` | `CLUSTER MEET ip port` | Join 1 node vào cluster (thường tự động khi init) |
| `CLUSTER FORGET` | `CLUSTER FORGET node-id` | Remove node khỏi cluster (60s timeout để avoid re-add tự động) |
| `CLUSTER RESET` | `CLUSTER RESET [HARD\|SOFT]` | Reset node về standalone (hard = xóa config, soft = keep) |
| `CLUSTER ADDSLOTS` | `CLUSTER ADDSLOTS slot [slot ...]` | Assign slots cho current master (dùng khi init) |
| `CLUSTER DELSLOTS` | `CLUSTER DELSLOTS slot [slot ...]` | Remove slots khỏi current node |
| `CLUSTER REPLICATE` | `CLUSTER REPLICATE node-id` | Make current node replica of specified master |
| `CLUSTER SETSLOT` | `CLUSTER SETSLOT slot IMPORTING\|MIGRATING\|NODE` | Manual slot state management (resharding) |

### Key Routing & Slot Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER KEYSLOT` | `CLUSTER KEYSLOT key` | Tính slot number cho key: `CRC16(key) mod 16384` |
| `CLUSTER COUNTKEYSINSLOT` | `CLUSTER COUNTKEYSINSLOT slot` | Số keys trong slot (trên node hiện tại) |
| `CLUSTER GETKEYSINSLOT` | `CLUSTER GETKEYSINSLOT slot count` | Lấy up to `count` keys trong slot |

### Node Info Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER SLAVES` | `CLUSTER SLAVES node-id` | List replicas của 1 master |
| `CLUSTER MYID` | `CLUSTER MYID` | Return node ID của current node |
| `CLUSTER SAVECONFIG` | `CLUSTER SAVECONFIG` | Force save nodes.conf (checkpoint) |

### Failover Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER FAILOVER` | `CLUSTER FAILOVER [FORCE\|TAKEOVER]` | Manual failover: replica → master |
| `CLUSTER FAILOVER FORCE` | `CLUSTER FAILOVER FORCE` | Force replica promote (bỏ qua master coordination) |
| `CLUSTER FAILOVER TAKEOVER` | `CLUSTER FAILOVER TAKEOVER` | Emergency takeover (bỏ qua quorum, dùng khi majority loss) |

---

## 2. Configuration Reference

### Cluster-Specific Config

```txt
# Bật cluster mode — required để node hoạt động trong cluster
cluster-enabled yes

# File lưu cluster state (nodes.conf auto-generated)
# KHÔNG edit thủ công
cluster-config-file nodes.conf

# Thời gian node không respond trước khi mark unreachable
# Default: 15000ms — too short = false positive, too long = slow detection
cluster-node-timeout 15000

# Slot coverage requirement
# yes (default): tất cả slots phải covered, else cluster reject writes
# no: cho phép reads/writes khi 1 số slot uncovered (partial cluster)
cluster-require-full-coverage no

# Replica validity: replica bị mark invalid nếu PING > N × node-timeout không respond
# 0 = replica không bao giờ bị mark invalid (replica luôn valid)
# > 0 = graceful degradation
cluster-replica-validity-factor 10

# Cho phép reads khi master unreachable
# no (default): reads rejected khi cluster degraded
# yes: reads từ replicas kể cả khi majority masters down
cluster-allow-reads-when-down no

# Replica election priority (trong cluster, khác với replica-priority trong Sentinel)
# Tăng priority = replica được ưu tiên promote hơn
# Default: 1
cluster-replica-priority 100

# Migration barrier: master chỉ migrate slot khi có >= N replicas healthy
# Default: 1 (OK)
cluster-migration-barrier 1
```

### Slot Calculation Formula

```bash
# CRC16(hash_key) mod 16384
# CRC16 polynomial: x^16 + x^12 + x^5 + 1
# Result: 0-16383 (14 low bits used)

# Với hash tag {tag}:
# CRC16 chỉ tính trên phần "tag" bên trong cặp {} hợp lệ đầu tiên.
# Nếu tag rỗng hoặc không có cặp {} hợp lệ, Redis dùng toàn bộ key.

# Ví dụ:
redis-cli CLUSTER KEYSLOT "user:123:profile"
# → CRC16("user:123:profile") mod 16384 = e.g., 4219

redis-cli CLUSTER KEYSLOT "user:{tenant-42}:profile"
# → CRC16("tenant-42") mod 16384 = slot của tenant-42
# → all keys với tenant-42 cùng slot
```

---

## 3. Docker Compose — Production-Grade 6-Node Cluster

```yaml
# docker-compose.cluster.yml
version: "3.8"
services:
  # ── Shard 1: master + replica ──────────────────────────────────────────
  redis-node-1:
    image: redis:7.2-alpine
    container_name: redis-node-1
    ports:
      - "7001:6379"
      - "17001:16379"   # cluster bus = client port + 10000
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node1-data:/data
    networks:
      - redis-cluster-net

  redis-node-2:
    image: redis:7.2-alpine
    container_name: redis-node-2
    ports:
      - "7002:6379"
      - "17002:16379"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node2-data:/data
    networks:
      - redis-cluster-net

  # ── Shard 2: master + replica ──────────────────────────────────────────
  redis-node-3:
    image: redis:7.2-alpine
    container_name: redis-node-3
    ports:
      - "7003:6379"
      - "17003:16379"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node3-data:/data
    networks:
      - redis-cluster-net

  redis-node-4:
    image: redis:7.2-alpine
    container_name: redis-node-4
    ports:
      - "7004:6379"
      - "17004:16379"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node4-data:/data
    networks:
      - redis-cluster-net

  # ── Shard 3: master + replica ──────────────────────────────────────────
  redis-node-5:
    image: redis:7.2-alpine
    container_name: redis-node-5
    ports:
      - "7005:6379"
      - "17005:16379"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node5-data:/data
    networks:
      - redis-cluster-net

  redis-node-6:
    image: redis:7.2-alpine
    container_name: redis-node-6
    ports:
      - "7006:6379"
      - "17006:16379"
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file /data/nodes.conf
      --cluster-node-timeout 15000
      --cluster-require-full-coverage no
      --cluster-allow-reads-when-down yes
      --appendonly yes
      --appendfsync everysec
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - node6-data:/data
    networks:
      - redis-cluster-net

networks:
  redis-cluster-net:
    driver: bridge

volumes:
  node1-data:
  node2-data:
  node3-data:
  node4-data:
  node5-data:
  node6-data:
```

### Cluster Init Script

```bash
# Bước 1: Start containers
docker compose -f docker-compose.cluster.yml up -d

# Bước 2: Wait for all nodes to be ready
sleep 10

# Bước 3: Create cluster
# redis-cli --cluster create <node1> <node2> ... <node6>
# --cluster-replicas 1 = 1 replica per master (3 master + 3 replica = 6 nodes)

redis-cli --cluster create \
  127.0.0.1:7001 \
  127.0.0.1:7002 \
  127.0.0.1:7003 \
  127.0.0.1:7004 \
  127.0.0.1:7005 \
  127.0.0.1:7006 \
  --cluster-replicas 1

# Bước 4: Verify
redis-cli -p 7001 CLUSTER INFO
# Expected:
# cluster_state:ok
# cluster_slots_assigned:16384
# cluster_slots_ok:16384
# cluster_nodes:6

# Bước 5: Check slot distribution
redis-cli -p 7001 CLUSTER SLOTS
# Expected: 3 ranges (5461, 5461, 5462 slots each)

# Cleanup cluster
# redis-cli --cluster del-node 127.0.0.1:7001 <node-id>
```

---

## 4. TypeScript Code Snippets (ioredis Cluster)

```typescript
// cluster-client.ts
import Redis from "ioredis";

const clusterNodes = [
  { host: "127.0.0.1", port: 7001 },
  { host: "127.0.0.1", port: 7002 },
  { host: "127.0.0.1", port: 7003 },
];

export const cluster = new Redis.Cluster(clusterNodes, {
  // Slot map refresh
  redisOptions: {
    maxRetriesPerRequest: 3,
    retryStrategy: (times) => Math.min(times * 100, 3000),
    connectTimeout: 10000,
  },

  // How often to refresh slot map (ms)
  // Default: 60000 (1 minute)
  slotRefreshInterval: 60_000,

  // Enable/disable automatic MOVED handling
  // Default: true (should be true in production)
  enableReadyCheck: true,

  // Scale reads to replicas
  // 'master' | 'slave' | 'random' | 'all'
  readOnly: false,

  // Cluster-specific options
  clusterRetryStrategy: (times) => {
    if (times > 10) return null; // Stop retrying
    return Math.min(times * 200, 2000);
  },
});

cluster.on("error", (err) => {
  console.error("Cluster error:", err.message);
});

cluster.on("MOVED", (err) => {
  // ioredis handles MOVED automatically by default
  // This event fires for logging purposes
  console.log(`MOVED redirect: ${err.message}`);
});
```

```typescript
// key-operations.ts
import { cluster } from "./cluster";

// ── Single key operations (always safe) ──────────────────────────────────
async function singleKeyOps() {
  // Direct routing by key hash — ioredis resolves slot automatically
  await cluster.set("user:123", JSON.stringify({ name: "Thang", role: "admin" }));
  const user = await cluster.get("user:123");

  // TTL
  await cluster.setex("session:abc", 3600, "data");

  // Hash
  await cluster.hset("product:P-001", "name", "Laptop", "price", "15000000");
  const product = await cluster.hgetall("product:P-001");

  // Sorted set (for leaderboard)
  await cluster.zadd("leaderboard:game-1", 1500, "player:thang");
  await cluster.zadd("leaderboard:game-1", 2000, "player:minh");
  const top3 = await cluster.zrevrange("leaderboard:game-1", 0, 2, "WITHSCORES");
  // top3 = ["player:minh", "2000", "player:thang", "1500"]
}

// ── Hash tag operations ─────────────────────────────────────────────────
async function hashTagOps() {
  // Hash tag: {tenant-id} — all session keys of same tenant in same slot
  const tenantId = "tenant-42";
  const userId = "user-001";

  // Keys with same hash tag → same slot
  await cluster.set(`session:{${tenantId}}:${userId}`, JSON.stringify({ token: "abc" }));
  await cluster.set(`cart:{${tenantId}}:${userId}`, JSON.stringify({ items: [] }));
  await cluster.set(`pref:{${tenantId}}:${userId}`, JSON.stringify({ theme: "dark" }));

  // Multi-key same-slot: MGET works because {tenant-42} → same slot
  // ✓ This is safe
  const session = await cluster.get(`session:{${tenantId}}:${userId}`);
  const cart = await cluster.get(`cart:{${tenantId}}:${userId}`);

  // ✗ WRONG: Different hash tags → different slots
  // const results = await cluster.mget(
  //   `session:{tenant-42}:u1`,
  //   `session:{tenant-99}:u1`
  // );
  // → CROSSSLOT error

  // Pipeline per tenant (all keys same slot)
  const pipe = cluster.pipeline();
  pipe.get(`session:{${tenantId}}:${userId}`);
  pipe.get(`cart:{${tenantId}}:${userId}`);
  pipe.hgetall(`profile:{${tenantId}}:${userId}`);
  const pipeResults = await pipe.exec();
}

// ── Cross-slot scatter-gather ──────────────────────────────────────────
async function crossSlotScatterGather() {
  // Redis Cluster không execute một command MGET nếu keys khác slot.
  // Cách portable: tự group keys theo slot/node rồi pipeline GET hoặc MGET
  // cho từng same-slot group.

  const keys = Array.from({ length: 100 }, (_, i) => `product:${i}:info`);

  const grouped = new Map<number, string[]>();
  for (const key of keys) {
    const slot = (await cluster.cluster("keyslot", key)) as number;
    const bucket = grouped.get(slot) ?? [];
    bucket.push(key);
    grouped.set(slot, bucket);
  }

  const pairs = await Promise.all(
    Array.from(grouped.values()).map(async (sameSlotKeys) => {
      const values =
        sameSlotKeys.length === 1
          ? [await cluster.get(sameSlotKeys[0])]
          : await cluster.mget(...sameSlotKeys);
      return sameSlotKeys.map((key, i) => [key, values[i]] as const);
    }),
  );

  const byKey = new Map(pairs.flat());
  const results = keys.map((key) => byKey.get(key) ?? null);
  // Latency: max(RTT to slowest node) — not sum

  // For high-performance: manual pipeline per node
  // 1. Get slot map
  const slotMap = await cluster.cluster("slots");
  // 2. Group keys by node
  // 3. Pipeline per node (faster, less overhead)
}

// ── Compute slot number ─────────────────────────────────────────────────
async function slotComputation() {
  // CLUSTER KEYSLOT: compute slot from key
  const slot = await cluster.cluster("keyslot", "user:{tenant-42}:profile");
  console.log(`Key maps to slot: ${slot}`);
  // slot: 0-16383

  // Compute locally (for planning)
  // redis-cli: CLUSTER KEYSLOT "key"
}

// ── Observe cluster state ───────────────────────────────────────────────
async function clusterDiagnostics() {
  const info = await cluster.cluster("info");
  console.log("State:", info.cluster_state); // ok / fail
  console.log("Slots:", info.cluster_slots_assigned);
  console.log("Nodes:", info.cluster_known_nodes);

  const nodes = await cluster.cluster("nodes");
  console.log(nodes);

  const slots = await cluster.cluster("slots");
  // [[slot_start, slot_end, [node, uid], ...], ...]
}
```

```typescript
// cluster-aware-session.ts
// Session store với hash tag để multi-key operation

interface Session {
  userId: string;
  tenantId: string;
  token: string;
  createdAt: number;
}

export class ClusterSessionStore {
  constructor(private cluster: Redis.Cluster) {}

  // Hash tag pattern: session:{tenantId}:{userId}
  private sessionKey(tenantId: string, userId: string) {
    return `session:{${tenantId}}:${userId}`;
  }

  // All tenant's session-related keys share same hash tag
  // → Can use MGET, pipeline for same-tenant operations

  async setSession(tenantId: string, userId: string, data: Session, ttl: number) {
    const key = this.sessionKey(tenantId, userId);
    await this.cluster.setex(key, ttl, JSON.stringify(data));
  }

  async getSession(tenantId: string, userId: string): Promise<Session | null> {
    const key = this.sessionKey(tenantId, userId);
    const raw = await this.cluster.get(key);
    return raw ? JSON.parse(raw) : null;
  }

  // Multi-key for same tenant (same slot ✓)
  async getMultipleSessions(tenantId: string, userIds: string[]) {
    const keys = userIds.map((uid) => this.sessionKey(tenantId, uid));
    // Safe because all keys have same hash tag → same slot
    const results = await this.cluster.mget(...keys);
    return results.map((r) => (r ? JSON.parse(r) : null));
  }

  async deleteSession(tenantId: string, userId: string) {
    const key = this.sessionKey(tenantId, userId);
    await this.cluster.del(key);
  }
}
```

---

## 5. Go Code Snippets (go-redis/v9 ClusterClient)

```go
// cluster-client.go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

func newClusterClient() *redis.ClusterClient {
    return redis.NewClusterClient(&redis.ClusterOptions{
        Addrs: []string{
            "127.0.0.1:7001",
            "127.0.0.1:7002",
            "127.0.0.1:7003",
        },
        // MOVED handling: automatic by default
        // Client routes to correct node using slot map

        MaxRedirects: 3, // Max MOVED redirects before error

        // Connection pool per node
        PoolSize: 100, // connections per node

        // Timeouts
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,
        ConnectTimeout: 5 * time.Second,

        // Replica read (optional)
        // RouteReadsToReplicas: true,

        // Cluster-specific
        RouteByLatency:  false,
        RouteRandomly:   false,
    })
}
```

```go
// key-operations.go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

func clusterOperations(ctx context.Context, client *redis.ClusterClient) {
    // ── Single key operations ─────────────────────────────────────────
    err := client.Set(ctx, "user:123", `{"name":"Thang","role":"admin"}`, time.Hour).Err()
    if err != nil {
        log.Fatalf("SET error: %v", err)
    }

    val, err := client.Get(ctx, "user:123").Result()
    if err == redis.Nil {
        fmt.Println("Key not found")
    } else if err != nil {
        log.Fatalf("GET error: %v", err)
    } else {
        fmt.Printf("Got: %s\n", val)
    }

    // ── Hash tag operations ───────────────────────────────────────────
    tenantID := "tenant-42"
    userID := "user-001"

    // All keys với same hash tag → same slot
    sessionKey := fmt.Sprintf("session:{%s}:%s", tenantID, userID)
    cartKey := fmt.Sprintf("cart:{%s}:%s", tenantID, userID)

    pipe := client.Pipeline()
    pipe.Set(ctx, sessionKey, `{"token":"abc123"}`, time.Hour)
    pipe.Set(ctx, cartKey, `{"items":["P-001","P-002"]}`, time.Hour)
    _, err = pipe.Exec(ctx)
    if err != nil {
        log.Fatalf("Pipeline error: %v", err)
    }

    // MGET safe vì cùng hash tag → cùng slot
    results, err := client.MGet(ctx, sessionKey, cartKey).Result()
    if err != nil {
        log.Fatalf("MGET error: %v", err)
    }
    fmt.Printf("MGET results: %v\n", results)

    // ── Cross-slot scatter-gather ─────────────────────────────────────
    keys := make([]string, 100)
    for i := 0; i < 100; i++ {
        keys[i] = fmt.Sprintf("product:%d:info", i)
    }

    // go-redis tự động split MGET by slot và pipeline
    // Latency = max(RTT to slowest node) chứ không phải sum
    values, err := client.MGet(ctx, keys...).Result()
    if err != nil {
        log.Fatalf("MGET cross-slot error: %v", err)
    }
    fmt.Printf("Got %d results\n", len(values))

    // ── Sorted set (leaderboard) ──────────────────────────────────────
    leaderboardKey := "leaderboard:game-1"
    pipe = client.Pipeline()
    pipe.ZAdd(ctx, leaderboardKey, redis.Z{Score: 1500, Member: "player:thang"})
    pipe.ZAdd(ctx, leaderboardKey, redis.Z{Score: 2000, Member: "player:minh"})
    pipe.ZAdd(ctx, leaderboardKey, redis.Z{Score: 1800, Member: "player:lan"})
    _, _ = pipe.Exec(ctx)

    // Top 3
    top3, err := client.ZRevRangeWithScores(ctx, leaderboardKey, 0, 2).Result()
    if err != nil {
        log.Fatalf("ZREVRANGE error: %v", err)
    }
    for i, z := range top3 {
        fmt.Printf("Rank %d: %s = %.0f\n", i+1, z.Member, z.Score)
    }

    // ── Slot computation ──────────────────────────────────────────────
    slot := client.Slot(ctx, sessionKey)
    fmt.Printf("Key %s maps to slot: %d\n", sessionKey, slot)
}
```

```go
// cluster-session-store.go
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
)

type Session struct {
    UserID    string `json:"user_id"`
    TenantID  string `json:"tenant_id"`
    Token     string `json:"token"`
    CreatedAt int64  `json:"created_at"`
}

type ClusterSessionStore struct {
    client *redis.ClusterClient
}

func NewClusterSessionStore(client *redis.ClusterClient) *ClusterSessionStore {
    return &ClusterSessionStore{client: client}
}

func (s *ClusterSessionStore) sessionKey(tenantID, userID string) string {
    return fmt.Sprintf("session:{%s}:%s", tenantID, userID)
}

func (s *ClusterSessionStore) SetSession(ctx context.Context,
    tenantID, userID string, ttl time.Duration) error {

    key := s.sessionKey(tenantID, userID)
    session := Session{
        UserID:    userID,
        TenantID:  tenantID,
        Token:     fmt.Sprintf("tok_%s_%d", userID, time.Now().Unix()),
        CreatedAt: time.Now().Unix(),
    }
    data, err := json.Marshal(session)
    if err != nil {
        return err
    }
    return s.client.Set(ctx, key, data, ttl).Err()
}

func (s *ClusterSessionStore) GetSession(ctx context.Context,
    tenantID, userID string) (*Session, error) {

    key := s.sessionKey(tenantID, userID)
    data, err := s.client.Get(ctx, key).Bytes()
    if err != nil {
        return nil, err
    }
    var session Session
    if err := json.Unmarshal(data, &session); err != nil {
        return nil, err
    }
    return &session, nil
}

func (s *ClusterSessionStore) GetMultipleSessions(ctx context.Context,
    tenantID string, userIDs []string) (map[string]*Session, error) {

    // All keys have same hash tag → same slot → MGET safe
    keys := make([]string, len(userIDs))
    for i, uid := range userIDs {
        keys[i] = s.sessionKey(tenantID, uid)
    }

    results, err := s.client.MGet(ctx, keys...).Result()
    if err != nil {
        return nil, err
    }

    sessions := make(map[string]*Session, len(userIDs))
    for i, r := range results {
        if r == nil {
            continue // key not found
        }
        data, ok := r.(string)
        if !ok {
            continue
        }
        var session Session
        if err := json.Unmarshal([]byte(data), &session); err != nil {
            continue
        }
        sessions[userIDs[i]] = &session
    }
    return sessions, nil
}
```

---

## 6. Hash Tag Pattern Examples

### Đúng và Sai

```bash
# ✅ ĐÚNG: Hash tag có cardinality cao
session:{user-id}:profile    → each user = 1 slot (or shared with few users)
session:{user-id}:cart      → same slot as session:{user-id}:profile

# ✅ ĐÚNG: Hash tag cho multi-key locality cần thiết
order:{order-id}:items      → all items of same order same slot
order:{order-id}:payment    → same slot

# ✅ ĐÚNG: Sub-sharding để tránh hot slot
session:{tenant-id}:{shard}:{user-id}
  shard = CRC16(user-id) % 4
  → 4 slots per tenant → no hot slot

# ❌ SAI: Hash tag có cardinality thấp → hot slot
session:{region}:{user-id}     → region chỉ có 3 giá trị (vn, us, eu)
                                 → chỉ 3 slots, 1 slot có thể = 80% traffic

# ❌ SAI: Hash tag không cần thiết
cache:{page}:{id}             → nếu không cần MGET cùng page
                                 → không cần hash tag, để random distribution

# ❌ SAI: Empty hash tag (no tag)
cache::{id}                   → {} là empty tag
                                 → sử dụng full key → không có hash tag

# ❌ SAI: Multiple {} pairs — chỉ first pair được dùng
cache:{tenant}:{user}:data    → hash tag = {tenant}
                                 → {user} không ảnh hưởng slot
```

### Hash Tag Decision Flowchart

```
Bạn cần multi-key operation (MGET, pipeline, transaction)?
  │
  ├─ NO → Không dùng hash tag → random distribution → even slots
  │
  └─ YES → Bạn có N keys cùng entity/group cần gộp?
      │
      ├─ YES → Dùng hash tag với entity/group ID
      │        Ví dụ: order:{order-id}:{field}
      │        ⚠️ WARNING: entity ID phải có cardinality CAO
      │                   (>100 unique values để even distribution)
      │
      └─ NO → Xem xét lại key design
               Hoặc: dùng scatter-gather thay vì hash tag
               Hoặc: application-level merge
```

### Hot Slot Risk Assessment

```bash
# Calculate slot distribution của hash tag pattern
# Test với 1000 random keys

python3 -c "
import hashlib
def crc16(key):
    # Simplified CRC16 approximation using Python hash
    # Real Redis: CRC16(key) mod 16384
    h = 0
    for c in key:
        h = (h * 33 + ord(c)) & 0xFFFF
    return h % 16384

# Test hash tag với tenant ID (low cardinality)
tenants = ['region-vn', 'region-us', 'region-eu']
for t in tenants:
    for u in range(1000):
        key = f'session:{{{t}}}:user-{u}'
        slot = crc16(key)
        print(f'{t}: slot {slot}')
" | awk '{print $2}' | sort -n | uniq -c | sort -rn | head -5
```

---

## 7. Links & References

### Official Documentation

- [Redis Cluster Specification](https://redis.io/docs/management/scaling/) — official Redis docs
- [Redis Cluster Tutorial](https://redis.io/docs/management/optimization/cluster-tutorial/) — step-by-step guide
- [Redis Cluster Commands](https://redis.io/commands/?group=cluster) — full command reference
- [CLUSTER KEYSLOT](https://redis.io/commands/cluster-keyslot/) — slot computation
- [CLUSTER INFO](https://redis.io/commands/cluster-info/) — cluster state
- [Redis Cluster Tutorial — Slot Migration](https://redis.io/docs/management/scaling/#redistributing-slots) — resharding how-to

### Configuration Reference

- [`cluster-enabled`](https://redis.io/docs/management/replication/#replication-configuration) — cluster mode config
- [`cluster-node-timeout`](https://redis.io/docs/management/scaling/#cluster-configuration) — failure detection tuning
- [`cluster-require-full-coverage`](https://redis.io/docs/management/scaling/#cluster-availability) — partial cluster config
- [`cluster-allow-reads-when-down`](https://redis.io/docs/management/scaling/#reading-writes-when-a-master-is-unavailable) — degraded reads

### ioredis & go-redis

- [ioredis Cluster](https://github.com/redis/ioredis/blob/main/README.md#cluster) — TypeScript cluster client
- [ioredis Cluster options](https://github.com/redis/ioredis/blob/main/README.md#cluster-options) — all options
- [go-redis ClusterClient](https://redis.uptrace.dev/guide/go-redis-cluster.html) — Go cluster client
- [go-redis v9 Cluster](https://pkg.go.dev/github.com/redis/go-redis/v9#ClusterClient) — API reference

### Hash Tag Specification

- [Redis Cluster Key Hash Tags](https://redis.io/docs/reference/cluster-spec/#key-hash-tags) — official spec
- [CRC16 algorithm in Redis source](https://github.com/redis/redis/blob/unstable/src/cluster.c) — `slot.c`, `cluster.c`

### Architecture & Blog Posts

- [antirez blog: Redis Cluster spec](http://antirez.com/news/98) — original design rationale
- [Redis Cluster gossip protocol internals](https://redis.io/docs/reference/cluster-spec/#gossip) — failure detection
- [Shopify: Scaling Redis at Shopify](https://shopify.engineering/) — production case study
- [Twitter Engineering Blog](https://blog.twitter.com/engineering/) — timeline sharding case study
- [AWS ElastiCache Redis Cluster](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/WhatIs.html) — managed cluster
- [Redis Labs: Cluster benchmarks](https://redis.com/blog/) — performance data

### Tools

- [`redis-cli --cluster create`](https://redis.io/docs/management/scaling/#creating-a-cluster) — cluster creation
- [`redis-cli --cluster check`](https://redis.io/docs/management/scaling/#cluster-health-checks) — cluster health check
- [`redis-cli --cluster reshard`](https://redis.io/docs/management/scaling/#resharding-cluster-nodes) — online resharding
- [`redis-cli --cluster add-node`](https://redis.io/docs/management/scaling/#adding-a-node) — add node to cluster
- [`redis-cli --cluster del-node`](https://redis.io/docs/management/scaling/#removing-a-node) — remove node
- [Redis-cluster Visualizer](https://github.com/RedisInsight/RedisClusterRC) — cluster visualization
