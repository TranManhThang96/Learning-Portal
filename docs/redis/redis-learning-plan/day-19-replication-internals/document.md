# Day 19: Replication Internals — Reference Document

---

## 1. Command Cheat Sheet

### Replication Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `REPLICAOF` | `REPLICAOF host port` | Configure instance là replica của master. `REPLICAOF NO ONE` = promote thành master. |
| `REPLICAOF NO ONE` | `REPLICAOF NO ONE` | Dừng replication, instance trở thành standalone master. |
| `PSYNC` | `PSYNC <replid> <offset>` | Partial sync: tiếp tục từ offset. `PSYNC ? -1` = full sync. |
| `SYNC` | `SYNC` | Legacy (Redis 2.8 trước PSYNC). Luôn full sync. |
| `WAIT` | `WAIT numreplicas timeout` | Đợi acknowledgment từ N replicas trong timeout ms. |
| `REPLCONF` | `REPLCONF <option> <value>` | Replication configuration handshake: `listening-port`, `ip-address`, `ack <offset>`. |
| `CONFIG GET replica-read-only` | `CONFIG GET replica-read-only` | Kiểm tra replica có reject writes hay không. |
| `CONFIG SET replica-read-only no` | `CONFIG SET replica-read-only no` | Cho phép write trực tiếp trên replica để lab/debug; không dùng production. |
| `ROLE` | `ROLE` | Trả về role của instance: master, slave, sentinel. |

### Info Commands

| Command | Mô tả |
|---|---|
| `INFO replication` | Full replication status: role, master/replica details, offsets, lag |
| `INFO commandstats` | Command latency breakdown (useful to find slow commands causing replication delay) |
| `INFO memory` | Memory usage: used_memory, mem_fragmentation_ratio, etc. |
| `INFO server` | Server info: version, uptime, process_id |

### Key INFO Replication Fields

```bash
# Trên master:
redis-cli INFO replication | grep -E "^role|^connected_slaves|^master_"
role:master
connected_slaves:3
slave0:ip=10.0.1.20,port=6380,state=online,offset=1234567,lag=0
slave1:ip=10.0.1.21,port=6381,state=online,offset=1234567,lag=0
slave2:ip=10.0.1.22,port=6382,state=connect,offset=1234500,lag=67

# Trên replica:
redis-cli INFO replication | grep -E "^role|^master_|^slave_"
role:slave
master_host:10.0.0.10
master_port:6379
master_link_status:up
master_repl_offset:1234567
second_repl_offset:1200000
repl_backlog_active:1
repl_backlog_size:104857600
repl_backlog_histlen:1523
repl_backlog_first_size:8204
slave_repl_offset:1234567
```

### Client Management on Replica

| Command | Syntax | Mô tả |
|---|---|---|
| `CLIENT NO-EVICT` | `CLIENT NOEVICT ON\|OFF` | Cho phép client không bị evict khi replica đến maxmemory. Dùng cho replica của replica. |
| `CLIENT LIST` | `CLIENT LIST` | Liệt kê tất cả connected clients + role (type=normal, replica, pubsub). |
| `CLIENT KILL` | `CLIENT KILL ip:port` | Kill specific client connection. |
| `CLIENT PAUSE` | `CLIENT PAUSE timeout [WRITE\|ALL]` | Pause tất cả clients trong timeout ms. |

---

## 2. Configuration Reference

### Core Replication Config

```txt
# redis.conf — Master

# Replication
replicaof 127.0.0.1 6379          # (chỉ trên replica) master host:port

# Backlog
repl-backlog-size 104857600       # 100 MB — production minimum
repl-backlog-ttl 3600             # seconds to keep backlog after last replica disconnect

# Disk / Diskless sync
repl-diskless-sync yes             # stream RDB qua socket, không qua disk
repl-diskless-sync-delay 5         # seconds to wait for more replicas before starting sync

# Timeout
repl-timeout 60                   # seconds — replication timeout (sento master/replica)
repl-ping-replica-period 10        # seconds — PING interval from master to replicas

# ACK & Write concern
min-replicas-to-write 1            # reject writes if fewer than N healthy replicas are available
min-replicas-max-lag 5             # seconds — only replicas with lag <= this value are counted

# Buffer
repl-backlog-size 104857600        # 100MB backlog buffer

# Performance
repl-disable-tcp-nodelay no       # no = enable TCP_NODELAY (lower latency, more packets)
                                  # yes = disable (higher latency, less bandwidth)
```

```txt
# redis.conf — Replica

# Read-only mode (default: yes)
replica-read-only yes              # reject writes on replica

# Sync from master
replicaof 10.0.0.10 6379         # master host:port

# Replica performance
repl-diskless-sync yes
repl-diskless-sync-delay 5

# Timeout
repl-timeout 60
repl-ping-replica-period 10

# Memory management on replica
maxmemory 2gb                     # set less than master if replica has less RAM
maxmemory-policy allkeys-lru       # on replica: may need eviction
```

### `repl-disable-tcp-nodelay` Explained

```
TCP_NODELAY off (repl-disable-tcp-nodelay yes):
  - Buffer small commands → send in larger batches
  - Reduces network packets by ~80%
  - Adds latency: commands wait in buffer before sending
  - Best for: high write throughput, lag-tolerant

TCP_NODELAY on (repl-disable-tcp-nodelay no) [DEFAULT]:
  - Send commands immediately (no buffering)
  - More network packets
  - Lower latency
  - Best for: low-latency replication, small commands
```

### `min-replicas-to-write` Behavior

```txt
# Master rejects writes if:
#   healthy_replicas_with_lag_le_min_replicas_max_lag < min-replicas-to-write

# Example: require at least 1 replica within 5 seconds
min-replicas-to-write 1
min-replicas-max-lag 5
```

```
Timeline:
  T=0:   1 replica connected, lag=1s   → writes ACCEPTED
  T=6:   replica lag=6s (exceeds 5s)    → writes REJECTED ("N replica lag too high")
  T=8:   replica catches up, lag=0s     → writes ACCEPTED again

Use with WAIT for write acknowledgment:
  SET key value
  WAIT 1 5000  → blocks until 1 replica ack within 5s
```

---

## 3. Docker Compose Template — Production Grade

### docker-compose.replication.yml

```yaml
version: "3.8"

services:
  # ── Master ──────────────────────────────────────────────
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    hostname: redis-master
    ports:
      - "6379:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-diskless-sync-delay 5
      --repl-backlog-size 104857600
      --repl-backlog-ttl 3600
      --repl-timeout 60
      --repl-ping-replica-period 10
      --repl-disable-tcp-nodelay no
      --min-replicas-to-write 1
      --min-replicas-max-lag 5
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
      --save 900 1
      --save 300 10
      --save 60 10000
      --loglevel notice
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    volumes:
      - redis-master-data:/data
    networks:
      - redis-net
    deploy:
      resources:
        limits:
          memory: 768M
        reservations:
          memory: 512M

  # ── Replica 1 ───────────────────────────────────────────
  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    hostname: redis-replica-1
    ports:
      - "6380:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replicaof redis-master 6379
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-diskless-sync-delay 5
      --repl-backlog-size 104857600
      --repl-timeout 60
      --repl-disable-tcp-nodelay no
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
      --loglevel notice
    healthcheck:
      test: ["CMD", "redis-cli", "-h", "redis-master", "-p", "6379", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - redis-replica-1-data:/data
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 768M

  # ── Replica 2 ───────────────────────────────────────────
  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    hostname: redis-replica-2
    ports:
      - "6381:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --replicaof redis-master 6379
      --replica-read-only yes
      --repl-diskless-sync yes
      --repl-diskless-sync-delay 5
      --repl-backlog-size 104857600
      --repl-timeout 60
      --repl-disable-tcp-nodelay no
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
      --loglevel notice
    healthcheck:
      test: ["CMD", "redis-cli", "-h", "redis-master", "-p", "6379", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - redis-replica-2-data:/data
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 768M

volumes:
  redis-master-data:
  redis-replica-1-data:
  redis-replica-2-data:

networks:
  redis-net:
    driver: bridge
```

### Start and Verify

```bash
# Start
docker compose -f docker-compose.replication.yml up -d

# Wait for replication to establish
sleep 5

# Verify master has 2 connected replicas
redis-cli -h localhost -p 6379 INFO replication
# Expected: connected_slaves:2

# Verify replica status
redis-cli -h localhost -p 6380 INFO replication | grep master_link_status
# Expected: master_link_status:up

# Test replication
redis-cli -h localhost -p 6379 SET test:key "hello"
redis-cli -h localhost -p 6380 GET test:key   # Should return "hello"
redis-cli -h localhost -p 6381 GET test:key   # Should return "hello"

# Check replication offsets
redis-cli -h localhost -p 6379 INFO replication | grep master_repl_offset
redis-cli -h localhost -p 6380 INFO replication | grep "master_repl_offset\|slave_repl_offset"

# Cleanup
docker compose -f docker-compose.replication.yml down -v
```

---

## 4. Go Code Snippets

### Setup: Master + Replica Clients

```go
// setup.go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	masterHost = "localhost"
	masterPort = "6379"
	replica1Host = "localhost"
	replica1Port = "6380"
	replica2Host = "localhost"
	replica2Port = "6381"
)

func newClient(addr string) *redis.Client {
	return redis.NewClient(&redis.Options{
		Addr:         addr,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     50,
		MinIdleConns: 5,
		// Read-only for replica connections
	})
}

var (
	masterClient = newClient(masterHost + ":" + masterPort)
	replica1Client = newClient(replica1Host + ":" + replica1Port)
	replica2Client = newClient(replica2Host + ":" + replica2Port)
)

// ReadWriteClient: generic client with both master and replica
type ReadWriteClient struct {
	master   *redis.Client
	replicas []*redis.Client
}

func NewReadWriteClient(master *redis.Client, replicas ...*redis.Client) *ReadWriteClient {
	return &ReadWriteClient{
		master:   master,
		replicas: replicas,
	}
}

func (c *ReadWriteClient) Write(ctx context.Context, key, value string) error {
	return c.master.Set(ctx, key, value, 0).Err()
}

func (c *ReadWriteClient) ReadFromReplica(ctx context.Context, key string) (string, error) {
	// Round-robin across replicas
	for _, r := range c.replicas {
		val, err := r.Get(ctx, key).Result()
		if err == nil {
			return val, nil
		}
		// If error is not redis.Nil, log but continue
		if err != redis.Nil {
			log.Printf("Replica read error: %v", err)
		}
	}
	// Fallback to master
	return c.master.Get(ctx, key).Result()
}

func (c *ReadWriteClient) Master() *redis.Client {
	return c.master
}

func (c *ReadWriteClient) Replicas() []*redis.Client {
	return c.replicas
}

func verifyReplicationUp(ctx context.Context) error {
	info, err := masterClient.Info(ctx, "replication").Result()
	if err != nil {
		return fmt.Errorf("failed to get master info: %w", err)
	}
	log.Printf("Master INFO replication:\n%s", info)

	for i, r := range []*redis.Client{replica1Client, replica2Client} {
		info, err := r.Info(ctx, "replication").Result()
		if err != nil {
			return fmt.Errorf("failed to get replica-%d info: %w", i+1, err)
		}
		log.Printf("Replica-%d INFO replication:\n%s", i+1, info)
	}
	return nil
}
```

### Measure Replica Lag

```go
// replica_lag.go
package main

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

type ReplicationStatus struct {
	MasterReplOffset  int64
	ReplicaReplOffset int64
	LagBytes          int64
	LagSeconds        float64
}

func getMasterOffset(ctx context.Context, master *redis.Client) (int64, error) {
	info, err := master.Info(ctx, "replication").Result()
	if err != nil {
		return 0, err
	}
	for _, line := range strings.Split(info, "\n") {
		if strings.HasPrefix(line, "master_repl_offset:") {
			return strconv.ParseInt(strings.TrimPrefix(line, "master_repl_offset:"), 10, 64)
		}
	}
	return 0, fmt.Errorf("master_repl_offset not found")
}

func getReplicaOffset(ctx context.Context, replica *redis.Client) (int64, error) {
	info, err := replica.Info(ctx, "replication").Result()
	if err != nil {
		return 0, err
	}
	for _, line := range strings.Split(info, "\n") {
		if strings.HasPrefix(line, "slave_repl_offset:") {
			return strconv.ParseInt(strings.TrimPrefix(line, "slave_repl_offset:"), 10, 64)
		}
	}
	return 0, fmt.Errorf("slave_repl_offset not found")
}

func MeasureReplicaLag(ctx context.Context, master, replica *redis.Client) (*ReplicationStatus, error) {
	masterOffset, err := getMasterOffset(ctx, master)
	if err != nil {
		return nil, fmt.Errorf("master offset: %w", err)
	}
	replicaOffset, err := getReplicaOffset(ctx, replica)
	if err != nil {
		return nil, fmt.Errorf("replica offset: %w", err)
	}

	// Estimate lag in seconds using write rate approximation
	// In production: track actual write throughput from master
	avgCmdSize := 500 // bytes per command (estimate)
	estimatedWriteRate := 10000 // commands/sec (estimate)
	lagSeconds := float64(masterOffset-replicaOffset) * avgCmdSize / float64(estimatedWriteRate)

	return &ReplicationStatus{
		MasterReplOffset:  masterOffset,
		ReplicaReplOffset: replicaOffset,
		LagBytes:          masterOffset - replicaOffset,
		LagSeconds:        lagSeconds,
	}, nil
}

// MonitorLagLoop: continuously monitor replica lag
func MonitorLagLoop(ctx context.Context, master, replica *redis.Client, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			status, err := MeasureReplicaLag(ctx, master, replica)
			if err != nil {
				fmt.Printf("[ERROR] %v\n", err)
				continue
			}
			fmt.Printf("[LAG] master_offset=%d replica_offset=%d lag_bytes=%d estimated_lag=%.3fs\n",
				status.MasterReplOffset, status.ReplicaReplOffset, status.LagBytes, status.LagSeconds)

			// Alert threshold
			if status.LagSeconds > 1.0 {
				fmt.Printf("[ALERT] Replica lag exceeded 1 second: %.3fs\n", status.LagSeconds)
			}
		}
	}
}
```

### Write with WAIT + Read with Fallback

```go
// read_write.go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	WaitReplicas    = 1
	WaitTimeoutMs   = 5000
	StaleThresholdS = 0.5
)

// WriteWithWait writes to master and waits for replica acknowledgment
func WriteWithWait(ctx context.Context, master *redis.Client, key, value string) error {
	pipe := master.Pipeline()
	setCmd := pipe.Set(ctx, key, value, 0)
	// Execute SET first
	if err := pipe.Exec(ctx); err != nil && !errors.Is(err, redis.Nil) {
		return fmt.Errorf("SET failed: %w", err)
	}
	_ = setCmd

	// Now WAIT for acknowledgment
	acked, err := master.Wait(ctx, WaitReplicas, int64(WaitTimeoutMs)).Result()
	if err != nil {
		return fmt.Errorf("WAIT failed: %w", err)
	}
	if acked < WaitReplicas {
		log.Printf("[WARN] Only %d/%d replicas acked within %dms", acked, WaitReplicas, WaitTimeoutMs)
	}
	return nil
}

// ReadWithFallback: read from replica, fallback to master if stale or error
func ReadWithFallback(ctx context.Context, replicas []*redis.Client, master *redis.Client, key string) (string, error) {
	// Try each replica
	for _, r := range replicas {
		val, err := r.Get(ctx, key).Result()
		if err == nil {
			// Check lag
			lagBytes, lagOk := getReplicaLagBytes(ctx, r)
			if lagOk && float64(lagBytes)/10000 > StaleThresholdS {
				// Too stale, try next replica or master
				log.Printf("[WARN] Replica too stale (%.3fs), trying master", float64(lagBytes)/10000)
				continue
			}
			return val, nil
		}
		if errors.Is(err, redis.Nil) {
			return "", err
		}
		log.Printf("[WARN] Replica read error: %v", err)
	}

	// Fallback to master
	val, err := master.Get(ctx, key).Result()
	if err != nil {
		return "", fmt.Errorf("master read failed: %w", err)
	}
	return val, nil
}

func getReplicaLagBytes(ctx context.Context, replica *redis.Client) (int64, bool) {
	info, err := replica.Info(ctx, "replication").Result()
	if err != nil {
		return 0, false
	}
	for _, line := range splitLines(info) {
		if hasPrefix(line, "slave_repl_offset:") {
			replicaOffset, _ := parseInt(strings.TrimPrefix(line, "slave_repl_offset:"))
			// Need master offset to compute lag
			return replicaOffset, true // simplified
		}
	}
	return 0, false
}

func splitLines(s string) []string { return strings.Split(s, "\n") }
func hasPrefix(s, prefix string) bool { return strings.HasPrefix(s, prefix) }
func parseInt(s string) (int64, error) { var i int64; return i, nil }
```

---

## 5. TypeScript Code Snippets (ioredis)

### Replica-Aware Client with Sticky Routing

```typescript
// redis-replica-client.ts
import Redis from "ioredis";

interface ReplicaEndpoint {
  host: string;
  port: number;
}

class ReplicaAwareClient {
  private master: Redis;
  private replicas: Redis[];
  private replicaIndex = 0;
  private stickyMap = new Map<string, Redis>(); // sessionId → replica

  constructor(
    masterConfig: { host: string; port: number },
    replicaConfigs: ReplicaEndpoint[]
  ) {
    this.master = new Redis({
      host: masterConfig.host,
      port: masterConfig.port,
      maxRetriesPerRequest: 3,
      retryStrategy: (t) => Math.min(t * 100, 3000),
      enableReadyCheck: true,
      connectTimeout: 10000,
    });

    this.replicas = replicaConfigs.map((cfg) => {
      const client = new Redis({
        host: cfg.host,
        port: cfg.port,
        maxRetriesPerRequest: 3,
        retryStrategy: (t) => Math.min(t * 100, 3000),
        enableReadyCheck: true,
        // In Redis Cluster, clients may use READONLY for replica reads.
        // In standalone/Sentinel replication, `replica-read-only` is server config.
        readonlyMode: "on",
      });

      client.on("error", (err) =>
        console.error(`Replica ${cfg.host}:${cfg.port} error:`, err)
      );
      return client;
    });

    this.master.on("error", (err) =>
      console.error("Master error:", err)
    );
  }

  // Write — always to master
  async write(key: string, value: string): Promise<void> {
    await this.master.set(key, value);
  }

  // Write with replication acknowledgment
  async writeAndWait(
    key: string,
    value: string,
    replicas: number = 1,
    timeoutMs: number = 5000
  ): Promise<number> {
    await this.master.set(key, value);
    return this.master.wait(replicas, timeoutMs);
  }

  // Read from replica with sticky routing (monotonic reads)
  async readFromReplica(
    key: string,
    sessionId: string
  ): Promise<string | null> {
    let replica: Redis;

    if (this.stickyMap.has(sessionId)) {
      replica = this.stickyMap.get(sessionId)!;
    } else {
      // Round-robin to pick a replica
      replica = this.replicas[this.replicaIndex % this.replicas.length];
      this.replicaIndex++;
      this.stickyMap.set(sessionId, replica);
    }

    try {
      return await replica.get(key);
    } catch (err) {
      console.error("Replica read error, falling back to master:", err);
      // Remove from sticky map so next request gets a fresh replica
      this.stickyMap.delete(sessionId);
      return this.master.get(key);
    }
  }

  // Read from master (for write-your-reads consistency)
  async readFromMaster(key: string): Promise<string | null> {
    return this.master.get(key);
  }

  // Read with automatic routing based on data type
  async read(
    key: string,
    options: { sessionId?: string; readFromMaster?: boolean } = {}
  ): Promise<string | null> {
    if (options.readFromMaster) {
      return this.readFromMaster(key);
    }
    if (options.sessionId) {
      return this.readFromReplica(key, options.sessionId);
    }
    // Default: read from master (safe default)
    return this.readFromMaster(key);
  }

  // Monitor replica lag
  async getReplicaLag(replica: Redis): Promise<number> {
    const info = await replica.info("replication");
    const masterOffset = parseInt(
      (info as string)
        .split("\n")
        .find((l) => l.startsWith("master_repl_offset:"))
        ?.split(":")[1] ?? "0"
    );
    const slaveOffset = parseInt(
      (info as string)
        .split("\n")
        .find((l) => l.startsWith("slave_repl_offset:"))
        ?.split(":")[1] ?? "0"
    );
    return masterOffset - slaveOffset;
  }

  async close(): Promise<void> {
    await this.master.quit();
    await Promise.all(this.replicas.map((r) => r.quit()));
  }
}

// Usage
async function main() {
  const client = new ReplicaAwareClient(
    { host: "localhost", port: 6379 },
    [
      { host: "localhost", port: 6380 },
      { host: "localhost", port: 6381 },
    ]
  );

  // Write with replication acknowledgment
  await client.writeAndWait("user:100:profile", JSON.stringify({ name: "Alice" }), 1, 5000);

  // Read user's own profile (write-your-reads) — from master
  const myProfile = await client.readFromMaster("user:100:profile");

  // Read other users' profiles (stale OK) — from replica with sticky routing
  const otherProfile = await client.readFromReplica("user:200:profile", "session-abc");

  // Read with auto-routing
  const data = await client.read("user:100:profile", { readFromMaster: true });

  await client.close();
}
```

---

## 6. Redis Source Reference

### Key Source Files

```
src/replication.c     — Core replication logic
  - syncWithMaster()       : PSYNC/SYNC handshake với master
  - replicationFeedReplicas(): Master gửi commands đến replicas
  - replconfCommand()       : Xử lý REPLCONF commands
  - replicaTryPartialResync(): PSYNC2 partial sync logic
  - createMasterClient()    : Tạo client object cho master connection

src/server.h         — Replication structs
  - struct redisServer.repl_backlog       : Replication backlog buffer
  - struct redisServer.replid, replid2    : Replication IDs
  - struct client.flags & CLIENT_SLAVE      : Client role flags
  - struct serverState.repl_script_cache   : Script cache on replicas

src/networking.c     — Client connections
  - addReplyReplicationOffset(): Gửi repl offset cho replicas
  - freeClient()              : Cleanup khi replica disconnects

src/rdb.c           — RDB persistence (used by full sync)
  - rdbSaveRio()              : Tạo RDB file (disk mode)
  - rdbSaveToSocket()         : Stream RDB directly to socket (diskless mode)
  - rdbLoadRio()              : Load RDB vào replica

src/server.c         — Server main loop
  - call()                     : Gọi command + gọi replicationFeedReplicas()
```

### Key Data Structures

```c
// Replication backlog (src/server.h)
typedef struct replicationBacklog {
    char *replbuf;          // Circular buffer — holds command bytes
    long long replbuf_size; // Buffer size (repl-backlog-size)
    long long reploffset;   // Current master_repl_offset
    long long histlen;      // Number of bytes currently in backlog
    long long offset;       // First byte offset in circular buffer
} replicationBacklog;

// Each replica tracked in server.slaves list
typedef struct client {
    // ...
    long long reploffset;   // slave_repl_offset
    char replid[CONFIG_RUN_ID_SIZE+1]; // master's replid
    uint64_t flags;
} client;
```

---

## 7. Links & References

### Official Redis Documentation

- [Replication documentation](https://redis.io/docs/management/replication/)
- [REPLICAOF command](https://redis.io/commands/replicaof/)
- [PSYNC command](https://redis.io/commands/psync/)
- [WAIT command](https://redis.io/commands/wait/)
- [CONFIG SET command](https://redis.io/commands/config-set/)
- [Redis replication.conf reference](https://redis.io/docs/management/replication/#configuration)
- [Redis replication internals (antirez blog)](http://antirez.com) — Posts from Salvatore Sanfilippo on PSYNC2 design

### Source Code

- [Redis GitHub — src/replication.c](https://github.com/redis/redis/blob/unstable/src/replication.c)
- [Redis GitHub — src/server.h (replication structs)](https://github.com/redis/redis/blob/unstable/src/server.h)

### Blog Posts & Engineering Articles

- [GitHub Engineering — Redis at GitHub](https://github.blog/category/engineering/open-source/infrastructure/)
- [How Discord Stores Trillions of Messages](https://discord.com/blog/) — relevant for replication strategy at scale
- [antirez — Redis 4.0 PSYNC2 improvements](http://antirez.com) — original design rationale for PSYNC2
- [Shopify — Zero-Downtime Redis Failover](https://shopify.engineering/) — real production lessons
- [Stack Overflow — "It's Always DNS" incident](https://stackoverflow.blog/) — DNS failover with Redis

### Monitoring & Observability

- [redis_exporter — Prometheus metrics](https://github.com/oliver006/redis_exporter)
- [Grafana Redis Dashboard #11835](https://grafana.com/grafana/dashboards/11835)
- [Redis replication lag metrics in INFO](https://redis.io/docs/management/replication/#monitoring)

### Books

- *Designing Data-Intensive Applications* — Martin Kleppmann, Chapter 5 (Replication)
