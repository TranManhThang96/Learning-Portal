# Day 23: Sharding Strategies & Key Distribution — Reference Document

---

## 1. Command Cheat Sheet

### Cluster Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER SLOTS` | `CLUSTER SLOTS` | Trả về danh sách slot ranges và node addresses |
| `CLUSTER KEYSLOT` | `CLUSTER KEYSLOT key` | Trả về slot number cho 1 key |
| `CLUSTER COUNTKEYSINSLOT` | `CLUSTER COUNTKEYSINSLOT slot` | Đếm số keys trong 1 slot |
| `CLUSTER GETKEYSINSLOT` | `CLUSTER GETKEYSINSLOT slot count` | Lấy danh sách keys trong 1 slot |
| `CLUSTER INFO` | `CLUSTER INFO` | Cluster state, slot distribution, node health |
| `CLUSTER NODES` | `CLUSTER NODES` | Chi tiết tất cả nodes trong cluster |
| `CLUSTER SLAVES` | `CLUSTER SLAVES node-id` | Liệt kê replicas của 1 master |
| `CLUSTER FAILOVER` | `CLUSTER FAILOVER [FORCE\|TAKEOVER]` | Trigger manual failover |
| `CLUSTER ADDSLOTS` | `CLUSTER ADDSLOTS slot [slot ...]` | Assign slots cho 1 node |
| `CLUSTER DELSLOTS` | `CLUSTER DELSLOTS slot [slot ...]` | Xóa slots khỏi 1 node |
| `CLUSTER SETSLOT` | `CLUSTER SETSLOT slot IMPORTING\|MIGRATING\|NODE\|STABLE` | Slot migration commands |
| `redis-cli --cluster add-node` | `redis-cli --cluster add-node new-host:port existing-host:port` | Thêm node vào cluster |
| `redis-cli --cluster del-node` | `redis-cli --cluster del-node host:port node-id` | Xóa node khỏi cluster |
| `CLUSTER RESHARD` | `redis-cli --cluster reshard host:port` | Interactive resharding |
| `CLUSTER REBALANCE` | `redis-cli --cluster rebalance host:port` | Auto rebalance slots |

### Key Distribution Analysis

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER KEYSLOT` | `CLUSTER KEYSLOT key` | Slot của key |
| `SCAN` | `SCAN cursor [MATCH pattern] [COUNT count]` | Scan keys, có thể filter pattern |
| `DBSIZE` | `DBSIZE` | Tổng số keys trong database |
| `INFO keyspace` | `INFO keyspace` | Key count, expiry stats |

### Redis-cli Cluster Flags

```bash
# Inspect cluster
redis-cli -c -p 7000 CLUSTER INFO
redis-cli -c -p 7000 CLUSTER SLOTS
redis-cli -c -p 7000 CLUSTER NODES

# Key distribution analysis
redis-cli -c -p 7000 CLUSTER KEYSLOT "user:123:profile"
redis-cli -c -p 7000 CLUSTER COUNTKEYSINSLOT 5000
redis-cli -c -p 7000 CLUSTER GETKEYSINSLOT 5000 100

# Hot key detection
redis-cli -p 7000 --hotkeys
redis-cli -p 7000 --bigkeys
redis-cli -p 7000 --memkeys

# Resharding
redis-cli --cluster reshard 127.0.0.1:7000 \
  --cluster-from <source-id> \
  --cluster-to <target-id> \
  --cluster-slots 1000 \
  --cluster-timeout 30000

# Auto rebalance
redis-cli --cluster rebalance 127.0.0.1:7000 \
  --cluster-timeout 30000 \
  --cluster-simulate

# Add node
redis-cli --cluster add-node 127.0.0.1:7007 127.0.0.1:7000 \
  --cluster-slave \
  --cluster-master-id <master-id>
```

---

## 2. Config Templates

### Twemproxy (nutcracker) YAML

```yaml
# nutcracker.yml
# Reference: https://github.com/twitter/twemproxy

alpha:
  listen: 0.0.0.0:6379
  hash: fnv1a_64
  distribution: ketama
  timeout: 100
  backlog: 1024
  client_connections: 0
  redis: true
  preconnect: true
  auto_eject_hosts: true
  server_retry_timeout: 2000
  server_failure_limit: 3
  servers:
    # format: host:port:weight
    - 172.16.1.1:6379:1
    - 172.16.1.2:6379:1
    - 172.16.16.3:6379:1

beta:
  listen: 0.0.0.0:6380
  hash: fnv1a_64
  distribution: ketama
  hash_tag: "{user}"
  timeout: 200
  redis: true
  servers:
    - 172.16.1.1:6380:1
    - 172.16.1.2:6380:1
```

### Envoy Redis Proxy

```yaml
# envoy-redis-proxy.yaml
static_resources:
  listeners:
    - name: redis_proxy
      address:
        socket_address:
          address: 0.0.0.0
          port_value: 6379
      filter_chains:
        - filters:
            - name: envoy.filters.network.redis_proxy
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.filters.network.redis_proxy.v3.RedisProxy
                stat_prefix: redis_proxy
                prefix_routes:
                  - cluster: redis_cluster
                    request_mirror_policy:
                      - cluster: redis_replica_cluster
                        runtime_fraction:
                          default_value: "0.01"
                settings:
                  op_timeout: 5s
                  enable_hashtag: true
                  enable_redirection: true

  clusters:
    - name: redis_cluster
      type: STRICT_DNS
      lb_policy: LEAST_REQUEST
      circuit_breakers:
        thresholds:
          - max_connections: 100
            max_pending_requests: 100
      hosts:
        - socket_address:
            address: redis-master
            port_value: 6379
    - name: redis_replica_cluster
      type: STRICT_DNS
      lb_policy: ROUND_ROBIN
      hosts:
        - socket_address:
            address: redis-replica
            port_value: 6379
```

### Codis Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CODIS COMPONENTS                          │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Codis Dashboard (Web)                  │   │
│  │  - Slot assignment management                             │   │
│  │  - Proxy state                                           │   │
│  │  - Migration progress                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                    │
│  ┌───────────────────────────▼───────────────────────────────┐   │
│  │              ZooKeeper / etcd                              │   │
│  │  - Persistent slot topology                               │   │
│  │  - Proxy registration                                     │   │
│  │  - HA coordination                                       │   │
│  └───────────────────────────┬───────────────────────────────┘   │
│                              │                                    │
│  ┌───────────────────────────▼───────────────────────────────┐   │
│  │                  Codis Proxy (N instances)                │   │
│  │  - Routes key → slot                                      │   │
│  │  - Connection pooling                                     │   │
│  │  - Migration coordination                                  │   │
│  └──────┬──────────────┬──────────────┬──────────────────────┘   │
│         │              │              │                            │
│  ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐                  │
│  │  Group 1   │ │  Group 2   │ │  Group N  │                  │
│  │ master     │ │  master   │ │  master   │                  │
│  │ + slave   │ │  + slave  │ │  + slave  │                  │
│  └───────────┘ └───────────┘ └───────────┘                  │
│                                                                   │
│  CODIS FEATURES:                                                  │
│  ✓ Online resharding (dashboard-triggered slot migration)       │
│  ✓ Automatic failover within group                               │
│  ✓ Multiple proxies for HA                                       │
│  ✓ Supports most Redis commands                                  │
│  ✗ Not compatible with Redis Cluster protocol                     │
│  ✗ No native TLS support                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Code Snippets

### 3.1. TypeScript — Consistent Hashing with `hashring`

```typescript
// src/sharding/consistent-hash.ts
import Redis from "ioredis";

// Install: npm install ioredis
// For consistent hash: npm install hashring
// import HashRing from "hashring";

interface ShardConfig {
  host: string;
  port: number;
  password?: string;
}

interface RedisClient {
  client: Redis;
  host: string;
  port: number;
}

/**
 * Client-side sharding router using consistent hashing.
 * Compatible with Redis Cluster protocol (16384 slots).
 */
export class ShardRouter {
  private shards: RedisClient[];
  private slotMap: Map<number, number>; // slot -> shard index
  private readonly SLOT_COUNT = 16384;

  constructor(shardConfigs: ShardConfig[]) {
    this.shards = shardConfigs.map((cfg) => ({
      client: new Redis({
        host: cfg.host,
        port: cfg.port,
        password: cfg.password,
        retryStrategy: (times) => Math.min(times * 50, 2000),
        maxRetriesPerRequest: 3,
      }),
      host: cfg.host,
      port: cfg.port,
    }));

    this.slotMap = new Map();
    this.rebuildSlotMap();
  }

  // CRC16 implementation (matches Redis Cluster's slot calculation)
  private crc16(key: string): number {
    let crc = 0;
    for (let i = 0; i < key.length; i++) {
      crc = ((crc << 8) ^ crc16Table[((crc >> 8) ^ key.charCodeAt(i)) & 0xff]) & 0xffff;
    }
    return crc % this.SLOT_COUNT;
  }

  // Extract hash tag if present
  private extractHashTag(key: string): string {
    const start = key.indexOf("{");
    const end = key.indexOf("}");
    if (start !== -1 && end !== -1 && end > start + 1) {
      return key.substring(start + 1, end);
    }
    return key;
  }

  private getSlot(key: string): number {
    const tag = this.extractHashTag(key);
    return this.crc16(tag);
  }

  private rebuildSlotMap(): void {
    this.slotMap.clear();
    const slotsPerShard = Math.floor(this.SLOT_COUNT / this.shards.length);

    for (let shardIdx = 0; shardIdx < this.shards.length; shardIdx++) {
      const startSlot = shardIdx * slotsPerShard;
      const endSlot =
        shardIdx === this.shards.length - 1
          ? this.SLOT_COUNT
          : startSlot + slotsPerShard;

      for (let slot = startSlot; slot < endSlot; slot++) {
        this.slotMap.set(slot, shardIdx);
      }
    }
  }

  getShard(key: string): RedisClient {
    const slot = this.getSlot(key);
    const shardIdx = this.slotMap.get(slot) ?? 0;
    return this.shards[shardIdx];
  }

  async get(key: string): Promise<string | null> {
    const shard = this.getShard(key);
    return shard.client.get(key);
  }

  async set(key: string, value: string, ttlMs?: number): Promise<"OK"> {
    const shard = this.getShard(key);
    if (ttlMs) {
      return shard.client.set(key, value, "PX", ttlMs);
    }
    return shard.client.set(key, value);
  }

  async mget(keys: string[]): Promise<(string | null)[]> {
    // Group keys by shard
    const shardKeys = new Map<number, string[]>();
    for (const key of keys) {
      const shard = this.getShard(key);
      const idx = this.shards.indexOf(shard);
      if (!shardKeys.has(idx)) shardKeys.set(idx, []);
      shardKeys.get(idx)!.push(key);
    }

    // Execute MGET on each shard in parallel
    const results = new Map<number, (string | null)[]>();
    const promises = Array.from(shardKeys.entries()).map(async ([idx, shardKeysList]) => {
      const vals = await this.shards[idx].client.mget(...shardKeysList);
      results.set(idx, vals as (string | null)[]);
    });

    await Promise.all(promises);

    // Merge results in original order
    const output: (string | null)[] = new Array(keys.length);
    for (let i = 0; i < keys.length; i++) {
      const shard = this.getShard(keys[i]);
      const idx = this.shards.indexOf(shard);
      const shardKeyList = shardKeys.get(idx)!;
      const localIdx = shardKeyList.indexOf(keys[i]);
      output[i] = results.get(idx)![localIdx];
    }
    return output;
  }

  async close(): Promise<void> {
    await Promise.all(this.shards.map((s) => s.client.quit()));
  }
}

// CRC16 lookup table (used by Redis)
const crc16Table: number[] = [];
for (let i = 0; i < 256; i++) {
  let c = i << 8;
  for (let j = 0; j < 8; j++) {
    c = c & 0x8000 ? ((c << 1) ^ 0x1021) : c << 1;
  }
  crc16Table.push(c);
}

// Usage
const router = new ShardRouter([
  { host: "redis-1", port: 6379 },
  { host: "redis-2", port: 6379 },
  { host: "redis-3", port: 6379 },
]);

router.get("user:123:profile").then(console.log);
router.set("user:123:profile", JSON.stringify({ name: "Alice" }), 86400000);
router.close();
```

### 3.2. Go — Jump Consistent Hash Implementation

```go
// jump_hash.go
package main

import (
    "fmt"
)

// JumpConsistentHash implements Google Jump Consistent Hash
// Paper: "A Fast, Minimal Memory, Consistent Hash Algorithm"
// https://arxiv.org/abs/1406.2294
//
// Properties:
// - O(log n) time complexity
// - No virtual nodes needed
// - Monotonic: adding nodes only moves keys that hash to new buckets
// - Memory: O(1) — just stores number of buckets

func JumpConsistentHash(key uint64, numBuckets int) int {
    if numBuckets <= 0 {
        return -1
    }

    var b int64 = -1
    var j int64 = 0

    for j < int64(numBuckets) {
        b = j
        key = key*2862933555777941757 + 1
        j = int64(float64(b+1) * (float64(uint64(1)<<31) / float64((key>>33)+1)))
    }

    return int(b)
}

// Demo: simulate uniform key distribution
func main() {
    const (
        numKeys    = 100_000
        numBuckets = 10
    )

    counts := make([]int, numBuckets)
    for i := 0; i < numKeys; i++ {
        bucket := JumpConsistentHash(uint64(i)*0x123456789ABCDEF, numBuckets)
        counts[bucket]++
    }

    fmt.Printf("Jump Consistent Hash — %d keys, %d buckets:\n", numKeys, numBuckets)
    expected := numKeys / numBuckets
    maxImbalance := 0
    for i, c := range counts {
        imbalance := abs(c-expected) * 100 / expected
        if imbalance > maxImbalance {
            maxImbalance = imbalance
        }
        barLen := c * 40 / expected
        bar := ""
        for j := 0; j < barLen; j++ {
            bar += "█"
        }
        fmt.Printf("  Shard %d: %6d keys (%+.2f%%) %s\n", i, c,
            float64(c-expected)/float64(expected)*100, bar)
    }
    fmt.Printf("\nMax imbalance: %d%%  (modulo-N would be catastrophic)\n", maxImbalance)

    // Show catastrophic failure of modulo-N
    fmt.Println("\nModulo-N resharding impact (add 1 node to 3-node cluster):")
    modCounts := make([]int, 4)
    for i := 0; i < numKeys; i++ {
        bucket := i % 4
        modCounts[bucket]++
    }
    for i, c := range modCounts {
        fmt.Printf("  Shard %d: %6d keys (%+.2f%%)\n", i, c,
            float64(c-expected)/float64(expected)*100)
    }
}

func abs(n int) int {
    if n < 0 {
        return -n
    }
    return n
}
```

### 3.3. Tenant-Based Shard Router (Go)

```go
// tenant_shard_router.go
package main

import (
    "fmt"
    "hash/fnv"
    "sync"
)

// TenantTier classifies tenants by their traffic profile
type TenantTier int

const (
    TierSmall TenantTier = iota // <1K ops/sec: shared cluster
    TierMedium                  // 1K-10K ops/sec: dedicated namespace
    TierLarge                   // >10K ops/sec: dedicated instance
)

// TenantInfo tracks per-tenant metadata
type TenantInfo struct {
    ID        string
    Tier      TenantTier
    ShardIdx  int    // for medium tenants: which shared shard
    RedisHost string // for large tenants: dedicated instance
}

// TenantShardRouter manages tiered sharding for multi-tenant SaaS
type TenantShardRouter struct {
    mu           sync.RWMutex
    smallTenants map[string]int        // tenantID -> smallShardIdx
    mediumShards []map[string]struct{}  // shared shards for medium tenants
    largeTenants map[string]*TenantInfo // dedicated per tenant

    // Config
    numSmallShards  int
    numMediumShards int
    mediumPerShard  int // max tenants per medium shard
}

func NewTenantShardRouter(numSmall, numMedium, mediumPerShard int) *TenantShardRouter {
    mediumShards := make([]map[string]struct{}, numMedium)
    for i := range mediumShards {
        mediumShards[i] = make(map[string]struct{})
    }
    return &TenantShardRouter{
        smallTenants:    make(map[string]int),
        mediumShards:    mediumShards,
        largeTenants:    make(map[string]*TenantInfo),
        numSmallShards:  numSmall,
        numMediumShards: numMedium,
        mediumPerShard:  mediumPerShard,
    }
}

func (r *TenantShardRouter) getShard(tier TenantTier, tenantID string) string {
    r.mu.RLock()
    defer r.mu.RUnlock()

    switch tier {
    case TierLarge:
        if t, ok := r.largeTenants[tenantID]; ok {
            return t.RedisHost
        }
    case TierMedium:
        if t, ok := r.largeTenants[tenantID]; ok {
            return fmt.Sprintf("redis-medium-%d", t.ShardIdx)
        }
    }
    // Small tenant: hash to small shard
    h := fnv.New32a()
    h.Write([]byte(tenantID))
    idx := int(h.Sum32()) % r.numSmallShards
    return fmt.Sprintf("redis-small-%d", idx)
}

func (r *TenantShardRouter) RegisterTenant(tenantID string, opsPerSec int) string {
    r.mu.Lock()
    defer r.mu.Unlock()

    if opsPerSec > 10_000 {
        // Large tenant: dedicated Redis
        r.largeTenants[tenantID] = &TenantInfo{
            ID:        tenantID,
            Tier:      TierLarge,
            RedisHost: fmt.Sprintf("redis-tenant-%s", tenantID),
        }
        return r.largeTenants[tenantID].RedisHost
    }

    if opsPerSec > 1_000 {
        // Medium tenant: shared medium shard
        // Find shard with fewest tenants
        bestIdx := 0
        minCount := len(r.mediumShards[0])
        for i, shard := range r.mediumShards {
            if len(shard) < minCount {
                minCount = len(shard)
                bestIdx = i
            }
        }
        r.mediumShards[bestIdx][tenantID] = struct{}{}
        r.largeTenants[tenantID] = &TenantInfo{
            ID:       tenantID,
            Tier:     TierMedium,
            ShardIdx: bestIdx,
        }
        return fmt.Sprintf("redis-medium-%d", bestIdx)
    }

    // Small tenant: shared small shard
    h := fnv.New32a()
    h.Write([]byte(tenantID))
    idx := int(h.Sum32()) % r.numSmallShards
    r.smallTenants[tenantID] = idx
    return fmt.Sprintf("redis-small-%d", idx)
}

func (r *TenantShardRouter) PromoteTenant(tenantID string, newOps int) string {
    // Remove from current tier, register at new tier
    r.mu.Lock()
    delete(r.smallTenants, tenantID)
    delete(r.largeTenants, tenantID)
    r.mu.Unlock()
    return r.RegisterTenant(tenantID, newOps)
}

// BuildKey creates tenant-scoped key
func BuildKey(tenantID, entityType, entityID string) string {
    return fmt.Sprintf("tenant:%s:%s:%s", tenantID, entityType, entityID)
}
```

---

## 4. Decision Matrix

### 4 Approach × 5 Dimensions

| Approach | Scalability | Latency | HA/DR | Ops Complexity | Best For |
|---|---|---|---|---|---|
| **Client-side sharding** | ★★★★☆ | ★★★★★ (zero overhead) | ★★☆☆☆ (manual) | ★★☆☆☆ | Multi-tenant isolation, custom routing |
| **Proxy-based (Twemproxy/Codis)** | ★★★★☆ | ★★★☆☆ (+0.2ms) | ★★★☆☆ (proxy HA) | ★☆☆☆☆ | Legacy migration, greenfield multi-app |
| **Redis Cluster** | ★★★★★ | ★★★★☆ (MOVED redirect) | ★★★★★ (built-in) | ★★★☆☆ | Greenfield, built-in HA needed |
| **Per-tenant Redis** | ★★☆☆☆ | ★★★★★ | ★★★★☆ | ★☆☆☆☆ | Enterprise SaaS, GDPR isolation |

### When to Choose Each Approach

| Scenario | Recommended | Why |
|---|---|---|
| <10K tenants, SMB | Shared Redis Cluster | Cost-effective, per-tenant hash namespace |
| >1K tenants, enterprise | Per-tenant Redis | Data isolation, compliance |
| Legacy app, minimal code change | Proxy-based | No app rewrite needed |
| Latency SLA <10ms p99 | Client-side | Zero proxy overhead |
| Need built-in HA | Redis Cluster | Automatic failover |
| Geographic sharding | Client-side or Proxy | Custom routing by region |
| Write-heavy, long retention | Per-tenant Redis + DB | Redis for hot, DB for cold |

---

## 5. Links & References

### Official Documentation

- [Redis Cluster Documentation](https://redis.io/docs/management/scaling/)
- [Redis Cluster Tutorial](https://redis.io/docs/management/optimization/cluster-tutorial/)
- [Redis CLUSTER KEYSLOT](https://redis.io/commands/cluster-keyslot/)
- [Redis CLUSTER SLOTS](https://redis.io/commands/cluster-slots/)
- [Redis CLUSTER COUNTKEYSINSLOT](https://redis.io/commands/cluster-countkeysinslot/)
- [Redis CLUSTER GETKEYSINSLOT](https://redis.io/commands/cluster-getkeysinslot/)
- [Redis CLUSTER SETSLOT](https://redis.io/commands/cluster-setslot/)
- [Redis-cli --cluster](https://redis.io/docs/management/optimization/cluster-admin/)

### Twemproxy / Proxy-Based

- [Twemproxy (GitHub)](https://github.com/twitter/twemproxy)
- [Twemproxy Configuration](https://github.com/twitter/twemproxy/blob/master/notes/s 配置.md)
- [Envoy Redis Proxy](https://www.envoyproxy.io/docs/envoy/v1.28/api-v3/extensions/filters/network/redis_proxy/v3/redis_proxy.proto)
- [Codis Documentation](https://github.com/CodisLabs/codis)

### Consistent Hashing Papers & Implementations

- [Google Jump Consistent Hash](https://arxiv.org/abs/1406.2294) — original paper by Lamping & Veach
- [Consistent Hashing and Random Trees](https://www.akamai.com/us/en/our-thinking/ipo-calico.jsp) — original Karger et al. paper
- [Memcached Ketama](https://github.com/RJ/ketama) — reference implementation
- [HashRing Python](https://pypi.org/project/hashring/) — Python hashring library

### Engineering Blog Posts

- [Twitter Engineering: Using Redis at Scale](https://blog.twitter.com/engineering/)
- [Discord Engineering: How Discord Stores Trillions of Messages](https://discord.com/blog/)
- [Pinterest Engineering: Sharding Pinterest](https://medium.com/@Pinterest_Engineering)
- [Shopify Engineering: Scaling Shopify's Infrastructure](https://shopify.engineering/)
- [Instagram Engineering: Scaling Infrastructure](https://instagram-engineering.com/)
- [Redis Labs: Redis Cluster vs Twemproxy](https://redis.io/blog/redis-cluster-vs-twemproxy-a-look-at-cluster-management/)
