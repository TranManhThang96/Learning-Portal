# Day 24: Cluster Operations & Resharding — Reference Document

---

## 1. Command Cheat Sheet

### redis-cli --cluster Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `create` | `redis-cli --cluster create <host:port> [host:port...]` | Tạo cluster mới. Phân chia 16384 slots đều cho các masters. |
| `add-node` | `redis-cli --cluster add-node <new-host:port> <existing-host:port> [--cluster-slave [--cluster-master-id <id>]]` | Thêm node mới. Mặc định là master. Dùng `--cluster-slave` để thêm replica. |
| `del-node` | `redis-cli --cluster del-node <host:port> <node-id>` | Xóa node khỏi cluster. Node phải không có slots. |
| `reshard` | `redis-cli --cluster reshard <host:port> [--cluster-from <source-id>] [--cluster-to <target-id>] [--cluster-slots <N>] [--cluster-yes]` | Di chuyển N slots từ source sang target. Dùng `--cluster-from` để chỉ định source cụ thể. |
| `rebalance` | `redis-cli --cluster rebalance <host:port> [--cluster-weight <node-id=N>] [--cluster-yes]` | Cân bằng slot distribution giữa các nodes. Dùng weight để điều chỉnh. |
| `check` | `redis-cli --cluster check <host:port>` | Kiểm tra cluster health: slots, node roles, connectivity. |
| `fix` | `redis-cli --cluster fix <host:port>` | Tự động fix cluster issues: orphaned slots, unreachable nodes. |
| `info` | `redis-cli --cluster info <host:port>` | Hiển thị cluster state: slots owned, node count, health. |
| `call` | `redis-cli --cluster call <host:port> <command>` | Gọi command trên tất cả nodes trong cluster. |
| `import` | `redis-cli --cluster import <source-host:port> <dest-host:port>` | Import keys từ standalone Redis sang cluster. |

### CLUSTER Subcommands

| Command | Syntax | Mô tả |
|---|---|---|
| `CLUSTER NODES` | `CLUSTER NODES` | Liệt kê tất cả nodes trong cluster với slot ownership, flags. |
| `CLUSTER SLOTS` | `CLUSTER SLOTS` | Trả về slot ranges và node info cho mỗi node. |
| `CLUSTER INFO` | `CLUSTER INFO` | Cluster state: state, size, slots assigned, failover, etc. |
| `CLUSTER SETSLOT` | `CLUSTER SETSLOT <slot> MIGRATING\|IMPORTING\|NODE <node-id>` | Gán trạng thái slot. Dùng trong resharding. |
| `CLUSTER COUNTKEYSINSLOT` | `CLUSTER COUNTKEYSINSLOT <slot>` | Đếm số keys trong slot (trên local node). |
| `CLUSTER GETKEYSINSLOT` | `CLUSTER GETKEYSINSLOT <slot> <count>` | Lấy danh sách keys trong slot (max count). |
| `CLUSTER KEYSLOT` | `CLUSTER KEYSLOT <key>` | Hash slot cho key (thuộc về slot nào). |
| `CLUSTER FAILOVER` | `CLUSTER FAILOVER [FORCE\|TAKEOVER]` | Manual replica promotion. |
| `CLUSTER MEET` | `CLUSTER MEET <ip> <port>` | Join node vào cluster. |
| `CLUSTER FORGET` | `CLUSTER FORGET <node-id>` | Xóa node khỏi cluster (sau khi đã down). |
| `CLUSTER REPLICAS` | `CLUSTER REPLICAS <master-id>` | Liệt kê replicas của master. |

### Cluster-Related Config

| Config | Default | Effect |
|---|---|---|
| `cluster-enabled` | `no` | Bật/tắt cluster mode. |
| `cluster-config-file` | `nodes.conf` | File lưu cluster topology (auto-generated). |
| `cluster-node-timeout` | `15000` (ms) | Thời gian node được coi là down. Quan trọng cho failover. |
| `cluster-replica-validity-factor` | `10` | Thời gian replica được coi là stale (timeout × factor). |
| `cluster-allow-replica-migration` | `yes` | Cho phép replica tự động migrate sang master khác. |
| `cluster-migration-barrier` | `1` | Số replica tối thiểu mỗi master giữ lại sau migration. |
| `cluster-require-full-coverage` | `yes` | Yêu cầu tất cả slots có master online để serve writes. |
| `cluster-preferred-endpoint-type` | `ip\|hostname\|client-port` | Endpoint type để advertise (AWS ElastiCache). |

---

## 2. Comparison Tables

### redis-cli --cluster add-node vs del-node

| Aspect | add-node | del-node |
|---|---|---|
| Slot ownership | New node: 0 slots (empty) | Must rebalance trước nếu node có slots |
| Role | Master (default) hoặc replica | Node phải reachable hoặc đã down |
| Rebalance needed | Yes — phải reshard sau khi add | Yes — slots phải được redistribute |
| Time complexity | O(1) join + O(N) migrate (N = slots) | O(N) rebalance + O(1) remove |
| Risk | Low — node join không affect existing nodes | Medium — rebalance có thể tạo latency spike |

### CLUSTER FAILOVER Modes

| Mode | Khi nào dùng | Data safety | Cluster impact |
|---|---|---|---|
| Automatic (default) | Master alive, replica promoted | Safe (đợi sync trước khi failover) | Minimal |
| `FORCE` | Master down, replica promoted | May lose data (không đợi sync) | Minimal |
| `TAKEOVER` | Majority partition, emergency | May lose data, may create split-brain | High (bypass quorum) |

### Cluster Backup Strategies

| Strategy | Pros | Cons |
|---|---|---|
| Per-master RDB BGSAVE | Consistent với point-in-time, simple | Must coordinate across all masters |
| Per-master AOF + Redis replication | Near-continuous backup | Complex setup |
| Redis Cluster sharding (Redis 7.2+) | Cluster-level backup command | Limited support |
| Application-level dual-write | Cross-cluster consistency | Application complexity |

---

## 3. Docker Compose Template — 6-Node Cluster

```yaml
# docker-compose.cluster.yml
version: "3.8"
services:
  redis-node-0:
    image: redis:7.2-alpine
    container_name: redis-node-0
    ports:
      - "7000:7000"
      - "17000:17000"  # Cluster bus port
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7000.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis-node-1:
    image: redis:7.2-alpine
    container_name: redis-node-1
    ports:
      - "7001:7000"
      - "17001:17000"
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7001.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis-node-2:
    image: redis:7.2-alpine
    container_name: redis-node-2
    ports:
      - "7002:7000"
      - "17002:17000"
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7002.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis-node-3:
    image: redis:7.2-alpine
    container_name: redis-node-3
    ports:
      - "7003:7000"
      - "17003:17000"
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7003.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis-node-4:
    image: redis:7.2-alpine
    container_name: redis-node-4
    ports:
      - "7004:7000"
      - "17004:17000"
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7004.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis-node-5:
    image: redis:7.2-alpine
    container_name: redis-node-5
    ports:
      - "7005:7000"
      - "17005:17000"
    command: >
      redis-server
      --port 7000
      --cluster-enabled yes
      --cluster-config-file nodes-7005.conf
      --cluster-node-timeout 15000
      --cluster-replica-validity-factor 10
      --cluster-require-full-coverage no
      --cluster-migration-barrier 1
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "7000", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
```

```bash
# Start all containers
docker compose -f docker-compose.cluster.yml up -d

# Wait for all containers to be healthy
sleep 10

# Create cluster: 3 masters (7000, 7001, 7002) + 3 replicas (7003, 7004, 7005)
# Chạy từ host để dùng các mapped ports 7000-7005.
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1 \
  --cluster-yes

# Verify cluster
redis-cli -p 7000 CLUSTER INFO
redis-cli -p 7000 CLUSTER NODES

# Cleanup
docker compose -f docker-compose.cluster.yml down -v
```

---

## 4. Code Snippets

### Bash Script — Reshard Từng Phase

```bash
#!/bin/bash
# cluster-reshard-manual.sh
# Manual resharding với kiểm soát từng bước

set -e

SOURCE_PORT="${1:?Usage: $0 <source-port> <target-port> <slot>}"
TARGET_PORT="${2:?Usage: $0 <source-port> <target-port> <slot>}"
SLOT="${3:?Usage: $0 <source-port> <target-port> <slot>}"
TIMEOUT_MS="${4:-10000}"

SOURCE_ID="$(redis-cli -p "$SOURCE_PORT" CLUSTER MYID)"
TARGET_ID="$(redis-cli -p "$TARGET_PORT" CLUSTER MYID)"

echo "=== Phase 1: Set MIGRATING on source ==="
redis-cli -p "$SOURCE_PORT" CLUSTER SETSLOT "$SLOT" MIGRATING "$TARGET_ID"

echo "=== Phase 2: Set IMPORTING on target ==="
redis-cli -p "$TARGET_PORT" CLUSTER SETSLOT "$SLOT" IMPORTING "$SOURCE_ID"

echo "=== Phase 3: Get keys in slot ==="
KEYS=$(redis-cli -p "$SOURCE_PORT" CLUSTER GETKEYSINSLOT "$SLOT" 10000)
KEY_COUNT=$(echo "$KEYS" | wc -l)
echo "Found $KEY_COUNT keys in slot $SLOT"

if [ "$KEY_COUNT" -eq 0 ]; then
  echo "No keys to migrate, skipping Phase 3"
else
  echo "=== Phase 3: Migrate keys ==="
  for key in $KEYS; do
    redis-cli -p "$SOURCE_PORT" MIGRATE 127.0.0.1 "$TARGET_PORT" "$key" 0 "$TIMEOUT_MS" REPLACE
    echo "  Migrated: $key"
  done
fi

echo "=== Phase 4: Set slot ownership ==="
for port in "$SOURCE_PORT" "$TARGET_PORT"; do
  redis-cli -p "$port" CLUSTER SETSLOT "$SLOT" NODE "$TARGET_ID"
done

echo "=== Phase 5: Verify ==="
sleep 2
redis-cli -p "$SOURCE_PORT" CLUSTER NODES | grep "$TARGET_ID"
redis-cli -p "$TARGET_PORT" CLUSTER NODES | grep "$TARGET_ID"

echo "=== Done ==="
```

### TypeScript — ioredis Cluster handle MOVED/ASK during Reshard

```typescript
// cluster-client.ts
import Redis from "ioredis";

const CLUSTER_PORTS = [7000, 7001, 7002, 7003, 7004, 7005];

// Build startup nodes
const startupNodes = CLUSTER_PORTS.map((port) => ({
  host: "127.0.0.1",
  port,
}));

const cluster = new Redis.Cluster(startupNodes, {
  // redisOptions for each node
  redisOptions: {
    maxRetriesPerRequest: 3,
    enableReadyCheck: true,
    connectTimeout: 10000,
  },

  // Handle MOVED automatically (critical!)
  // ioredis tự động update slot map khi nhận MOVED
  // ioredis cũng tự gửi ASKING khi nhận ASK redirect

  // Retry cluster connection on MOVED
  clusterRetryStrategy: (times) => {
    if (times > 10) return null; // Stop retrying
    return Math.min(times * 100, 3000);
  },

  // Refresh slot map định kỳ để giảm stale topology window
  slotsRefreshInterval: 60_000,
});

cluster.on("error", (err) => {
  console.error(`[CLUSTER ERROR] ${err.message}`);
});

// --- Helper: Measure latency during resharding ---
async function measureLatency(
  key: string,
  label: string
): Promise<{ latencyMs: number; result: string | null }> {
  const start = Date.now();
  try {
    const result = await cluster.get(key);
    return { latencyMs: Date.now() - start, result };
  } catch (err: any) {
    const latencyMs = Date.now() - start;
    // Handle MOVED/ASK redirect errors
    if (err.message.includes("MOVED")) {
      // ioredis đã tự redirect rồi, nhưng log để monitor
      console.log(`[MOVED during ${label}] ${err.message}`);
      return { latencyMs, result: null };
    }
    if (err.message.includes("ASK")) {
      console.log(`[ASK during ${label}] ${err.message}`);
      return { latencyMs, result: null };
    }
    throw err;
  }
}

// --- Helper: Monitor cluster state ---
async function monitorClusterState(): Promise<void> {
  const nodes = await cluster.nodes("master");
  console.log("\n=== Cluster State ===");
  for (const node of nodes) {
    const info = await node.info("cluster");
    const nodesInfo = await node.cluster("nodes");
    console.log(`Node ${node.options.port}: ${info}`);
    const slotCount = await node.cluster("slots");
    console.log(`  Slots: ${slotCount.length} slots owned`);
  }
}

// --- Benchmark: Measure p99 latency during resharding ---
async function benchmarkP99Latency(
  keys: string[],
  label: string
): Promise<{ p50: number; p95: number; p99: number; errorRate: number }> {
  const measurements: number[] = [];
  let errorCount = 0;

  await Promise.all(
    keys.map(async (key) => {
      try {
        const { latencyMs } = await measureLatency(key, label);
        measurements.push(latencyMs);
      } catch {
        errorCount++;
      }
    })
  );

  measurements.sort((a, b) => a - b);
  const n = measurements.length;
  return {
    p50: measurements[Math.floor(n * 0.5)] ?? 0,
    p95: measurements[Math.floor(n * 0.95)] ?? 0,
    p99: measurements[Math.floor(n * 0.99)] ?? 0,
    errorRate: errorCount / keys.length,
  };
}

// --- Helper: Verify slot ownership after reshard ---
async function verifySlotOwnership(
  expectedNodeId: string,
  slots: number[]
): Promise<{ match: boolean; mismatches: number[] }> {
  const mismatches: number[] = [];

  for (const slot of slots) {
    const slotInfo = await cluster.cluster("slots");
    const slotNode = slotInfo.find((range: any) =>
      (range as any[]).some(
        (node: any) =>
          node.id === expectedNodeId &&
          slot >= (range[0] ?? 0) &&
          slot <= (range[1] ?? 0)
      )
    );
    if (!slotNode) {
      mismatches.push(slot);
    }
  }

  return { match: mismatches.length === 0, mismatches };
}

export { cluster, measureLatency, monitorClusterState, benchmarkP99Latency, verifySlotOwnership };
```

### Go — Monitor Cluster Topology

```go
// cluster-monitor.go
package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

type ClusterNode struct {
	ID         string
	Addr       string
	Role       string // master, replica, myself
	Slots      []int
	Connected  bool
	ReplicaOf  string
}

type ClusterTopology struct {
	Nodes []ClusterNode
}

func parseClusterNodes(output string) []ClusterNode {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	nodes := make([]ClusterNode, 0, len(lines))

	for _, line := range lines {
		parts := strings.Fields(line)
		if len(parts) < 8 {
			continue
		}

		// Format: node-id ip:port@bus-port flags role master-id ping-sent pong-recv ...
		nodeID := parts[0]
		addr := parts[1]
		flags := strings.Split(parts[2], ",")

		var role, replicaOf string
		isMaster := true
		isMyself := false
		slots := []int{}

		for _, flag := range flags {
			switch flag {
			case "myself":
				isMyself = true
			case "master":
				role = "master"
				isMaster = true
			case "replica":
				role = "replica"
				isMaster = false
			case "handshake":
				continue
			}
			// Replica-of: @<master-id>
			if strings.HasPrefix(flag, "@") {
				replicaOf = flag[1:]
			}
			// Slot ranges: e.g., 0-5460
			if strings.Contains(flag, "-") || (len(parts) > 8 && isNumber(flag)) {
				// Parse slot ranges from remaining parts
			}
		}

		// Parse slots from line
		slotParts := strings.FieldsFunc(line, func(r rune) bool {
			return r == ' ' || r == '[' || r == ']' || r == '-'
		})

		for _, part := range slotParts {
			// Simple slot detection: numbers that look like slot numbers
			for _, s := range strings.Fields(part) {
				var num int
				if _, err := fmt.Sscanf(s, "%d", &num); err == nil && num >= 0 && num < 16384 {
					slots = append(slots, num)
				}
			}
		}

		nodes = append(nodes, ClusterNode{
			ID:        nodeID,
			Addr:      addr,
			Role:      role,
			Slots:     slots,
			Connected: !strings.Contains(parts[2], "disconnected"),
			ReplicaOf: replicaOf,
		})
	}
	return nodes
}

func isNumber(s string) bool {
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return len(s) > 0
}

func fetchClusterTopology(client *redis.Client) (*ClusterTopology, error) {
	ctx := context.Background()
	nodesOutput, err := client.ClusterNodes(ctx).Result()
	if err != nil {
		return nil, fmt.Errorf("CLUSTER NODES: %w", err)
	}

	infoOutput, err := client.ClusterInfo(ctx).Result()
	if err != nil {
		return nil, fmt.Errorf("CLUSTER INFO: %w", err)
	}

	nodes := parseClusterNodes(nodesOutput)

	fmt.Printf("=== Cluster Topology ===\n")
	fmt.Printf("Cluster state: %s\n", extractField(infoOutput, "cluster_state"))
	fmt.Printf("Slots assigned: %s\n", extractField(infoOutput, "cluster_slots_assigned"))
	fmt.Printf("Nodes: %d\n\n", len(nodes))

	for _, n := range nodes {
		slotRanges := summarizeSlots(n.Slots)
		fmt.Printf("  %s [%s] %s slots=%s\n",
			n.ID[:8], n.Role, n.Addr, slotRanges)
	}

	return &ClusterTopology{Nodes: nodes}, nil
}

func extractField(info, key string) string {
	for _, line := range strings.Split(info, "\n") {
		if strings.HasPrefix(line, key+":") {
			return strings.TrimSpace(strings.SplitN(line, ":", 2)[1])
		}
	}
	return "unknown"
}

func summarizeSlots(slots []int) string {
	if len(slots) == 0 {
		return "none"
	}
	return fmt.Sprintf("%d slots (range: %d-%d)", len(slots), slots[0], slots[len(slots)-1])
}

func monitorClusterTopology() {
	ports := []int{7000, 7001, 7002, 7003, 7004, 7005}

	for _, port := range ports {
		client := redis.NewClient(&redis.Options{
			Addr:         fmt.Sprintf("127.0.0.1:%d", port),
			DialTimeout:  5 * time.Second,
			ReadTimeout:  5 * time.Second,
			WriteTimeout: 5 * time.Second,
		})

		ctx := context.Background()
		if err := client.Ping(ctx).Err(); err != nil {
			log.Printf("Port %d: unreachable", port)
			client.Close()
			continue
		}

		topology, err := fetchClusterTopology(client)
		if err != nil {
			log.Printf("Port %d: %v", port, err)
		}

		// Check for migration states
		_nodes, _ := client.ClusterNodes(ctx).Result()
		if strings.Contains(_nodes, "MIGRATING") || strings.Contains(_nodes, "IMPORTING") {
			fmt.Printf("  ⚠️  Migration in progress detected on port %d\n", port)
		}

		// Verify slot count
		masterCount := 0
		for _, n := range topology.Nodes {
			if n.Role == "master" {
				masterCount++
			}
		}
		expectedSlots := masterCount * (16384 / masterCount)
		for _, n := range topology.Nodes {
			if n.Role == "master" && len(n.Slots) != expectedSlots/masterCount {
				fmt.Printf("  ⚠️  Node %s has %d slots (expected ~%d)\n",
					n.ID[:8], len(n.Slots), expectedSlots/masterCount)
			}
		}

		client.Close()
		break // Only need to query one node to get full topology
	}
}

func main() {
	fmt.Println("Starting cluster topology monitor...")
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		monitorClusterTopology()
		<-ticker.C
	}
}
```

---

## 5. Cluster Operation Runbook Checklist

### Pre-Operation Checklist

```
□ Cluster health check: redis-cli --cluster check
□ All nodes reachable: redis-cli -p <port> PING on all ports
□ No slots in MIGRATING/IMPORTING state: CLUSTER NODES | grep MIGRAT
□ Replication lag = 0: INFO replication | grep master_link_status
□ Memory headroom: INFO memory | grep used_memory_human
□ Backup completed: BGSAVE on all masters, RDB files copied
□ Slot distribution verified: CLUSTER NODES shows all 16384 slots covered
□ cluster-require-full-coverage reviewed: set to no if needed
□ cluster-node-timeout reviewed: set to 30s if doing heavy migration
□ Stakeholders notified: operation window announced
□ Rollback plan prepared: backup + procedure to revert
```

### During-Operation Checklist

```
□ Migration progress monitored: CLUSTER NODES | grep MIGRAT every 5 min
□ Latency monitored: redis-cli --latency-history on target node
□ MOVED/ASK count monitored: INFO errorstats | grep -E "MOVED|ASK" và client metrics
□ No errors in redis-cli output
□ If MOVED storm detected: pause operation, investigate
□ If slot stuck > 10 min: abort and investigate
□ Replication lag monitored: INFO replication on replicas
```

### Post-Operation Checklist

```
□ Cluster healthy: redis-cli --cluster check
□ All 16384 slots covered by masters: CLUSTER NODES | grep master
□ No MIGRATING/IMPORTING states: CLUSTER NODES | grep MIGRAT
□ Replication healthy: INFO replication | grep master_link_status = up
□ Load test passed: redis-benchmark or custom test
□ Latency p99 verified: within SLA
□ Slot distribution verified: CLUSTER NODES shows expected layout
□ Monitoring dashboards updated (if slot distribution changed)
□ Stakeholders notified: operation completed
□ Documentation updated: cluster topology diagram
```

---

## 6. Links & References

- [Redis Cluster Tutorial](https://redis.io/docs/management/clustering/) — Official tutorial
- [Redis Cluster Specification](https://redis.io/docs/reference/cluster-spec/) — Protocol, gossip, failover
- [Redis Cluster CLI (redis-cli)](https://redis.io/docs/management/clustering/#redis-cluster-cli) — `redis-cli --cluster` commands
- [CLUSTER SETSLOT](https://redis.io/commands/cluster-setslot/) — Slot migration commands
- [MIGRATE](https://redis.io/commands/migrate/) — Key migration command
- [Redis Cluster Failover](https://redis.io/docs/management/clustering/# failover) — Manual and automatic failover
- [Redis Cluster Configuration](https://redis.io/docs/management/clustering/#cluster-configuration) — All cluster configs
- [ioredis Cluster](https://github.com/redis/ioredis/blob/main/README.md#cluster) — TypeScript/Node.js cluster client
- [go-redis Cluster](https://redis.uptrace.dev/guide/go-redis-cluster.html) — Go cluster client
- [Twitter Redis Cluster at Scale](https://blog.twitter.com/engineering/) — Engineering blog
- [Shopify Redis Cluster Case Study](https://shopify.engineering/) — Capacity scaling at Shopify
- [AWS ElastiCache Redis Cluster](https://docs.aws.amazon.com/elasticache/) — Managed cluster operations
- [Redis Cluster Best Practices](https://redis.io/docs/management/clustering/#redis-cluster-best-practices) — Official best practices
- [Redis Cluster Security](https://redis.io/docs/management/security/cluster-security/) — TLS, authentication in cluster mode
