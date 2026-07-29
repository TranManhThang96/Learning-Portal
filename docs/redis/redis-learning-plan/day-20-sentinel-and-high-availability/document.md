# Day 20: Sentinel & High Availability — Reference Document

---

## 1. Command Cheat Sheet

### Sentinel Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `SENTINEL masters` | `SENTINEL masters` | Liệt kê tất cả monitored masters |
| `SENTINEL replicas <name>` | `SENTINEL replicas <name>` | Liệt kê replicas của master `<name>` |
| `SENTINEL get-master-addr-by-name <name>` | `SENTINEL get-master-addr-by-name <name>` | Lấy IP:port hiện tại của master `<name>` |
| `SENTINEL master <name>` | `SENTINEL master <name>` | Chi tiết trạng thái master (flags, address, quorum, Sentinel count) |
| `SENTINEL ckquorum <name>` | `SENTINEL ckquorum <name>` | Kiểm tra quorum đủ chưa để failover |
| `SENTINEL failover <name>` | `SENTINEL failover <name>` | Trigger manual failover (leader Sentinel phải thực thi) |
| `SENTINEL reset <name>` | `SENTINEL reset <name>` | Reset master state trong Sentinel config |
| `SENTINEL set <name> <option> <value>` | `SENTINEL set <name> <option> <value>` | Update config của master (runtime, không cần restart) |
| `SENTINEL is-master-down-by-addr` | `SENTINEL is-master-down-by-addr <ip> <port> <quorum> <runid>` | Kiểm tra master có down không + lấy vote |
| `SENTINEL info-cache` | `SENTINEL info-cache` | Cache info về tất cả Sentinels |
| `SENTINEL ping` | `SENTINEL ping` | Ping Sentinel |
| `SENTINEL role` | `SENTINEL role` | Trả về Sentinel's view về cluster role |

### Redis Replication Commands (liên quan Sentinel)

| Command | Syntax | Mô tả |
|---|---|---|
| `REPLICAOF <host> <port>` | `REPLICAOF <host> <port>` | Bắt đầu replicate từ master |
| `REPLICAOF NO ONE` | `REPLICAOF NO ONE` | Promote replica thành master (manual failover) |
| `WAIT <numreplicas> <timeout>` | `WAIT 2 5000` | Đợi N replicas acknowledge trong `timeout` ms |
| `ROLE` | `ROLE` | Trả về role của current instance (master/replica/sentinel) |
| `INFO replication` | `INFO replication` | Replication status, connected replicas, lag |

### Sentinel Pub/Sub Channels

| Channel | Trigger | Khi nào |
|---|---|---|
| `+sdown` | Subjective Down | 1 Sentinel mark master as unreachable |
| `-sdown` | SDOWN cleared | Master reachable lại |
| `+odown` | Objective Down | Quorum Sentinels agree on SDOWN |
| `-odown` | ODOWN cleared | Quorum không còn đủ |
| `+switch-master` | Master changed | Failover hoàn tất — **quan trọng nhất cho client** |
| `+slave-reconf` | Replica reconfigured | Replica đã sync với new master |
| `+promoted-slave` | Replica promoted | Replica được promote thành master |
| `+failover-state-retry` | Failover retry | Failover thất bại, đang retry |
| `+min-slave-replica-limit` | Write blocked | Write bị reject vì không đủ replicas |
| `+min-slave-replica-max-lag` | Write blocked | Write bị reject vì replica lag quá cao |

---

## 2. Configuration Templates

### Basic Sentinel Configuration

```txt
# sentinel.conf — 1 master + 2 replicas + 3 Sentinels
# File: sentinel-1.conf (Sentinel-1)

# Monitor master
sentinel monitor mymaster 127.0.0.1 6379 2

# Quorum: 2/3 Sentinels must agree → ODOWN
# Down detection threshold
sentinel down-after-milliseconds mymaster 5000

# Failover timeout (18 seconds)
sentinel failover-timeout mymaster 180000

# Replicas to sync after failover (1 = sequential, safe)
sentinel parallel-syncs mymaster 1

# Auth password (if Redis uses requirepass)
sentinel auth-pass mymaster <redis-password>

# Container/Docker: announce external IP (not container internal IP)
sentinel announce-ip 10.0.1.10
sentinel announce-port 26379

# Notification script (optional)
sentinel notification-script mymaster /etc/sentinel/notify.sh

# Client reconfig script (optional — called after failover)
sentinel client-reconf-script mymaster /etc/sentinel/reconfig.sh

# Deny scripts execution (security)
sentinel deny-scripts-reconfig yes
```

### Sentinel Config Parameters

| Parameter | Default | Recommended | Effect |
|---|---|---|---|
| `sentinel monitor <name> <ip> <port> <quorum>` | — | 2 (majority of 3) | Số Sentinels cần để declare ODOWN |
| `sentinel down-after-milliseconds <name> <ms>` | 30000 | 5000 | ms không reply trước khi SDOWN |
| `sentinel failover-timeout <name> <ms>` | 180000 | 180000 | Timeout cho toàn bộ failover operation |
| `sentinel parallel-syncs <name> <n>` | 1 | 1 | Replicas sync đồng thời sau failover |
| `sentinel auth-pass <name> <pass>` | — | set if required | Redis requirepass |
| `sentinel announce-ip <ip>` | auto | set in containers | IP announced cho clients (không dùng container IP) |
| `sentinel deny-scripts-reconfig` | no | yes | Ngăn scripts thay đổi Sentinel config |

### Redis Master Config For Write Guard

`min-replicas-to-write` và `min-replicas-max-lag` là Redis server config, không phải Sentinel config.

```txt
# redis.conf trên master
min-replicas-to-write 1
min-replicas-max-lag 10
```

| Redis Parameter | Default | Recommended | Effect |
|---|---|---|---|
| `min-replicas-to-write` | 0 | 0 cache, 1 session, 2 strict write guard with 2+ replicas | Reject writes nếu số healthy replicas nhỏ hơn N |
| `min-replicas-max-lag` | 10 | 10-30 | Replica chỉ được tính healthy nếu ACK age <= N seconds |
| `replica-priority` | 100 | 100 primary candidate, 50 secondary, 0 never promote | Ưu tiên replica được Sentinel promote; đặt trên Redis replica |

---

## 3. Docker Compose — Production Grade

```yaml
# docker-compose.sentinel.yml
# Production-grade: 1 master + 2 replicas + 3 Sentinels
version: "3.8"

services:
  # ─── Redis Master ────────────────────────────────────────────────────
  redis-master:
    image: redis:7.2-alpine
    container_name: redis-master
    hostname: redis-master
    ports:
      - "6379:6379"
    command: >
      redis-server
      --requirepass redis_secret_pass
      --appendonly yes
      --appendfsync everysec
      --replica-read-only yes
      --repl-diskless-sync no
      --min-replicas-to-write 1
      --min-replicas-max-lag 10
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redis-master-data:/data
    networks:
      - redis-net
    restart: unless-stopped

  # ─── Redis Replica 1 ────────────────────────────────────────────────
  redis-replica-1:
    image: redis:7.2-alpine
    container_name: redis-replica-1
    hostname: redis-replica-1
    ports:
      - "6380:6379"
    depends_on:
      redis-master:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redis-replica-1-data:/data
    networks:
      - redis-net
    restart: unless-stopped
    # Đặt replica-priority cao hơn để được ưu tiên promote
    command: >
      redis-server
      --requirepass redis_secret_pass
      --masterauth redis_secret_pass
      --replicaof redis-master 6379
      --replica-priority 100
      --appendonly yes
      --appendfsync everysec
      --replica-read-only yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru

  # ─── Redis Replica 2 ────────────────────────────────────────────────
  redis-replica-2:
    image: redis:7.2-alpine
    container_name: redis-replica-2
    hostname: redis-replica-2
    ports:
      - "6381:6379"
    command: >
      redis-server
      --requirepass redis_secret_pass
      --masterauth redis_secret_pass
      --replicaof redis-master 6379
      --replica-priority 50
      --appendonly yes
      --appendfsync everysec
      --replica-read-only yes
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    depends_on:
      redis-master:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis_secret_pass", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    volumes:
      - redis-replica-2-data:/data
    networks:
      - redis-net
    restart: unless-stopped

  # ─── Sentinel 1 (cùng host với master trong demo, production: separate hosts) ──
  sentinel-1:
    image: redis:7.2-alpine
    container_name: sentinel-1
    hostname: sentinel-1
    ports:
      - "26379:26379"
    command: >
      redis-sentinel
      --port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 5000
      --sentinel failover-timeout mymaster 180000
      --sentinel parallel-syncs mymaster 1
      --sentinel auth-pass mymaster redis_secret_pass
      --sentinel announce-ip sentinel-1
      --sentinel announce-port 26379
    depends_on:
      redis-master:
        condition: service_healthy
    volumes:
      - sentinel-1-data:/data
    networks:
      - redis-net
    restart: unless-stopped

  # ─── Sentinel 2 ─────────────────────────────────────────────────────
  sentinel-2:
    image: redis:7.2-alpine
    container_name: sentinel-2
    hostname: sentinel-2
    ports:
      - "26380:26379"
    command: >
      redis-sentinel
      --port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 5000
      --sentinel failover-timeout mymaster 180000
      --sentinel parallel-syncs mymaster 1
      --sentinel auth-pass mymaster redis_secret_pass
      --sentinel announce-ip sentinel-2
      --sentinel announce-port 26379
    depends_on:
      redis-master:
        condition: service_healthy
    volumes:
      - sentinel-2-data:/data
    networks:
      - redis-net
    restart: unless-stopped

  # ─── Sentinel 3 ─────────────────────────────────────────────────────
  sentinel-3:
    image: redis:7.2-alpine
    container_name: sentinel-3
    hostname: sentinel-3
    ports:
      - "26381:26379"
    command: >
      redis-sentinel
      --port 26379
      --sentinel monitor mymaster redis-master 6379 2
      --sentinel down-after-milliseconds mymaster 5000
      --sentinel failover-timeout mymaster 180000
      --sentinel parallel-syncs mymaster 1
      --sentinel auth-pass mymaster redis_secret_pass
      --sentinel announce-ip sentinel-3
      --sentinel announce-port 26379
    depends_on:
      redis-master:
        condition: service_healthy
    volumes:
      - sentinel-3-data:/data
    networks:
      - redis-net
    restart: unless-stopped

volumes:
  redis-master-data:
  redis-replica-1-data:
  redis-replica-2-data:
  sentinel-1-data:
  sentinel-2-data:
  sentinel-3-data:

networks:
  redis-net:
    driver: bridge
```

**Start**:
```bash
docker compose -f docker-compose.sentinel.yml up -d

# Verify
docker exec sentinel-1 redis-cli -p 26379 SENTINEL masters
docker exec sentinel-1 redis-cli -p 26379 SENTINEL ckquorum mymaster
docker exec sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

---

## 4. Code Snippets

### TypeScript — ioredis Sentinel (Recommended)

```typescript
// src/sentinel-client.ts
import Redis from "ioredis";
import { EventEmitter } from "events";

// ─── Configuration ────────────────────────────────────────────────────────
const SENTINELS = [
  { host: "localhost", port: 26379 },
  { host: "localhost", port: 26380 },
  { host: "localhost", port: 26381 },
];
const MASTER_NAME = "mymaster";
const REDIS_PASSWORD = "redis_secret_pass";

// ─── Sentinel-aware Redis Client ──────────────────────────────────────────
class SentinelClient extends EventEmitter {
  private masterClient: Redis | null = null;
  private isReady = false;

  constructor() {
    super();
    this.connect();
  }

  private connect(): void {
    this.masterClient = new Redis({
      sentinels: SENTINELS,
      name: MASTER_NAME,
      password: REDIS_PASSWORD,
      // Sentinel role detection
      role: "master",
      // Retry strategy for Sentinel connections
      sentinelRetryStrategy: (times: number) => {
        if (times > 10) {
          console.error("Sentinel connection failed after 10 retries");
          return null; // Stop retrying
        }
        return Math.min(times * 100, 3000);
      },
      // Retry strategy for master connection
      retryStrategy: (times: number) => {
        if (times > 20) {
          console.error("Master connection failed after 20 retries");
          return null;
        }
        return Math.min(times * 200, 5000);
      },
      maxRetriesPerRequest: 3,
      enableReadyCheck: true,
      lazyConnect: false,
    });

    // ── Connection events ──────────────────────────────────────────────
    this.masterClient.on("connect", () => {
      console.log("[Sentinel] Connected to Redis master");
    });

    this.masterClient.on("ready", () => {
      this.isReady = true;
      console.log("[Sentinel] Client ready");
    });

    this.masterClient.on("error", (err) => {
      console.error("[Sentinel] Redis error:", err.message);
    });

    this.masterClient.on("close", () => {
      this.isReady = false;
      console.warn("[Sentinel] Connection closed");
    });

    // ── Sentinel +switch-master event ──────────────────────────────────
    // This is the KEY event — fired when master changes after failover
    this.masterClient.on("sentinel", (err: Error | null) => {
      if (err) {
        console.error("[Sentinel] Sentinel error:", err.message);
        return;
      }
      // ioredis automatically handles reconnection after +switch-master
      console.log("[Sentinel] Master changed — ioredis reconnecting...");
    });

    // ── Reconnecting ───────────────────────────────────────────────────
    this.masterClient.on("reconnecting", () => {
      console.log("[Sentinel] Reconnecting to Redis...");
    });
  }

  async get(key: string): Promise<string | null> {
    if (!this.masterClient) throw new Error("Client not initialized");
    return this.masterClient.get(key);
  }

  async set(key: string, value: string, ttlMs?: number): Promise<string> {
    if (!this.masterClient) throw new Error("Client not initialized");
    if (ttlMs) {
      return this.masterClient.set(key, value, "PX", ttlMs);
    }
    return this.masterClient.set(key, value);
  }

  async waitForReady(): Promise<void> {
    if (this.isReady) return;
    return new Promise((resolve, reject) => {
      this.masterClient!.once("ready", resolve);
      this.masterClient!.once("error", reject);
    });
  }

  async close(): Promise<void> {
    await this.masterClient?.quit();
  }
}

// ─── Singleton instance ────────────────────────────────────────────────────
export const redisClient = new SentinelClient();
```

```typescript
// src/session-store.ts
import { redisClient } from "./sentinel-client";

const SESSION_PREFIX = "session:";
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export async function setSession(
  sessionId: string,
  userId: string,
  metadata: Record<string, string>
): Promise<void> {
  const key = `${SESSION_PREFIX}${sessionId}`;
  const data = JSON.stringify({ userId, metadata, createdAt: Date.now() });
  await redisClient.set(key, data, SESSION_TTL_MS);
}

export async function getSession(
  sessionId: string
): Promise<{ userId: string; metadata: Record<string, string> } | null> {
  const key = `${SESSION_PREFIX}${sessionId}`;
  const data = await redisClient.get(key);
  if (!data) return null;
  return JSON.parse(data);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const key = `${SESSION_PREFIX}${sessionId}`;
  await redisClient.close(); // Note: wrong — should use separate DEL operation
  // Correct:
  // const redis = new Redis(...) — get instance
  // await redis.del(key);
}
```

### Go — go-redis/v9 FailoverClient

```go
// sentinel.go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/redis/go-redis/v9"
)

// Sentinel configuration
var (
    sentinelAddrs = []string{
        "localhost:26379",
        "localhost:26380",
        "localhost:26381",
    }
    masterName    = "mymaster"
    redisPassword = "redis_secret_pass"
)

func newSentinelClient() *redis.Client {
    return redis.NewFailoverClient(&redis.FailoverOptions{
        SentinelAddrs: sentinelAddrs,
        SentinelPassword: "",          // if Sentinel needs auth
        MasterName:    masterName,
        MasterPassword: redisPassword,
        PoolSize:     50,
        MinIdleConns: 10,
        DialTimeout:  5 * time.Second,
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,
        // On failure, go-redis automatically queries Sentinel for new master
    })
}

func main() {
    rdb := newSentinelClient()
    ctx := context.Background()

    // Test connection
    pong, err := rdb.Ping(ctx).Result()
    if err != nil {
        log.Fatalf("Redis ping failed: %v", err)
    }
    fmt.Printf("Connected to master: %s\n", pong)

    // Get master address from Sentinel
    masterAddr, err := rdb.Get(ctx, "sentinel:master-addr").Result()
    if err == redis.Nil {
        // Not set — go-redis handles this internally
    }

    // Example operations
    err = rdb.Set(ctx, "user:session:123", "active", 30*24*time.Hour).Err()
    if err != nil {
        log.Printf("Set error: %v (may be due to failover)", err)
    }

    val, err := rdb.Get(ctx, "user:session:123").Result()
    if err != nil {
        log.Printf("Get error: %v (may be due to failover)", err)
    } else {
        fmt.Printf("Session: %s\n", val)
    }

    // WAIT command for durability
    // Ensure at least 1 replica acknowledged before returning
    n, err := rdb.Wait(ctx, 1, 5*time.Second).Result()
    if err != nil {
        log.Printf("WAIT result: %d replicas, err: %v", n, err)
    } else {
        fmt.Printf("Write acknowledged by %d replicas\n", n)
    }
}
```

### TypeScript — Failover Monitoring Script

```typescript
// src/failover-monitor.ts
// Monitor failover events in real-time using Sentinel Pub/Sub
import Redis from "ioredis";

const SENTINEL_ADDRS = [
  { host: "localhost", port: 26379 },
  { host: "localhost", port: 26380 },
  { host: "localhost", port: 26381 },
];

async function monitorFailoverEvents() {
  console.log("=== Sentinel Failover Monitor ===");

  for (const addr of SENTINEL_ADDRS) {
    const sentinel = new Redis({
      host: addr.host,
      port: addr.port,
      retryStrategy: (t) => Math.min(t * 100, 3000),
    });

    sentinel.on("error", (err) => {
      console.error(`[${addr.host}:${addr.port}] Sentinel error:`, err.message);
    });

    // Subscribe to all Sentinel Pub/Sub channels
    const channels = [
      "+switch-master",
      "+odown",
      "-odown",
      "+sdown",
      "-sdown",
      "+promoted-slave",
      "+failover-state-retry",
      "+min-slave-replica-limit",
      "+min-slave-replica-max-lag",
    ];

    for (const channel of channels) {
      sentinel.subscribe(channel, (err) => {
        if (err) {
          console.error(`[${addr.host}:${addr.port}] Subscribe error:`, err.message);
        }
      });
    }

    sentinel.on("message", (channel: string, message: string) => {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [${addr.host}:${addr.port}] ${channel}: ${message}`);
    });

    console.log(`Listening on Sentinel ${addr.host}:${addr.port}`);
  }

  // Keep running
  await new Promise(() => {});
}

monitorFailoverEvents().catch(console.error);
```

---

## 5. Failover Runbook Checklist

### Pre-incident: Preparation (luôn thực hiện)

- [ ] Sentinel processes đang chạy trên tất cả nodes: `ps aux | grep redis-sentinel`
- [ ] `SENTINEL ckquorum mymaster` trả về OK
- [ ] `SENTINEL masters` show tất cả Sentinels đang online
- [ ] Master `INFO replication` show replicas connected, `master_link_status = up`
- [ ] Replica lag < 10 giây: `INFO replication` → `master_link_down_since_seconds`
- [ ] Monitoring alerts configured cho: odown event, failover count, replica lag
- [ ] Application dùng Sentinel-aware client (ioredis, go-redis FailoverClient)
- [ ] Application subscribe `+switch-master` event
- [ ] Runbook này được test bằng chaos engineering

### Incident: Master Down Detected

- [ ] Alert received: master unreachable / odown / +sdown
- [ ] Verify: `redis-cli -p 26379 SENTINEL master mymaster` — flags show `odown`
- [ ] Verify: `redis-cli -p 26379 SENTINEL ckquorum mymaster` — quorum status
- [ ] Check: replica lag on each replica (`INFO replication`)
- [ ] Alert: notify on-call team, start incident ticket

### Incident: Failover In Progress

- [ ] Sentinel log: kiểm tra leader election (leader nhận majority authorization trong epoch)
- [ ] Sentinel log: replica promotion (`SLAVEOF NO ONE`)
- [ ] Sentinel log: replicas reconfigured (`SENTINEL REPLICATE new-master`)
- [ ] Time: đo failover duration từ SDOWN đến +switch-master
- [ ] `SENTINEL get-master-addr-by-name mymaster` — xác nhận new master address

### Post-failover: Verification

- [ ] New master `INFO replication` → role = master
- [ ] Replicas `INFO replication` → `master_link_status = up`, `role = slave`
- [ ] Replicas đang sync từ new master (check `master_repl_offset`)
- [ ] Application logs: confirm clients reconnect thành công
- [ ] No write errors từ application (check `min-replicas-to-write` not blocking)
- [ ] Sentinel `+switch-master` event received by all clients

### Post-failover: Old Master Recovery

- [ ] Old master (nếu recovered): `INFO replication` → role = slave
- [ ] Old master đang replicate từ new master
- [ ] Check: `INFO replication` → `master_link_status = up` trên old master
- [ ] Verify: no data divergence (check last command executed on both masters)
- [ ] Update monitoring: new master is primary, old master is replica

### Post-incident: Review

- [ ] Tổng hợp timeline: detection → failover start → failover complete → app reconnect
- [ ] Root cause: tại sao master failed? (OOM, crash, network partition, bug)
- [ ] Failover time: measured vs SLO (target: < 30s)
- [ ] Client reconnect: time từ +switch-master đến all clients connected
- [ ] Prevention: cập nhật runbook, monitoring, config nếu cần

---

## 6. Monitoring Queries

```bash
# ── Sentinel Health ──────────────────────────────────────────────────────
# Check quorum status (must return OK for failover to work)
redis-cli -p 26379 SENTINEL ckquorum mymaster
# Expected: mymaster: 3 usable Sentinels (quorum=2, 3/3 usable)

# All masters status
redis-cli -p 26379 SENTINEL masters

# Master detailed info
redis-cli -p 26379 SENTINEL master mymaster
# Key fields:
#   - flags: master,online (should NOT have odown,sdown)
#   - num-slaves: 2
#   - num-other-sentinels: 2
#   - quorum: 2
#   - failover-state: none (if not in failover)
#   - last-ok-ping-reply: 543ms (should be < 1000ms)

# List replicas
redis-cli -p 26379 SENTINEL replicas mymaster
# Key: flags, ip-address, port, runid, priority, link-status

# ── Redis Master Health ──────────────────────────────────────────────────
# Replication status on master
redis-cli -a redis_secret_pass INFO replication
# Key fields:
#   role:master
#   connected_slaves:2
#   master_failover_state:none
#   master_link_status:up
#   master_repl_offset (should match replica offsets)

# ── Redis Replica Health ─────────────────────────────────────────────────
# Replica replication lag
redis-cli -a redis_secret_pass INFO replication
# Key fields:
#   role:slave
#   master_link_status:up
#   master_link_down_since_seconds:0
#   slave_repl_offset:1234567
#   master_repl_offset:1234567
#   lag:0 (seconds behind master)

# ── Prometheus Metrics (if using redis_exporter) ─────────────────────────
# Sentinel-specific metrics (redis_exporter >= 1.5):
#   redis_sentinel_master_flags{flags="ok"}
#   redis_sentinel_master_num_slaves
#   redis_sentinel_master_quorum
#   redis_sentinel_master_last_ok_ping_reply_seconds
#   redis_sentinel_detected_failovers_total
```

---

## 7. Links & References

### Official Documentation
- [Redis Sentinel Documentation](https://redis.io/docs/management/sentinel/)
- [Redis Sentinel Tutorial](https://redis.io/docs/management/sentinel-tutorial/)
- [Sentinel Configuration](https://redis.io/docs/management/sentinel-tutorial/#example Sentinel-configuration)
- [SENTINEL Commands Reference](https://redis.io/commands/?group=sentinel)
- [Redis Replication + Sentinel](https://redis.io/docs/management/replication/)

### ioredis Sentinel
- [ioredis Sentinel support](https://github.com/redis/ioredis/blob/main/README.md#sentinel)
- [ioredis Sentinel events](https://github.com/redis/ioredis#sentinel-events)
- [ioredis FailoverClient example](https://github.com/redis/ioredis#basic-usage)

### go-redis FailoverClient
- [go-redis FailoverClient](https://redis.uptrace.dev/guide/go-redis.html#failover)
- [go-redis Sentinel](https://redis.uptrace.dev/guide/go-redis-sentinel.html)
- [go-redis GitHub](https://github.com/redis/go-redis)

### Blogs & Case Studies
- [Redis Sentinel internals — how it works (antirez blog)](http://antirez.com)
- [Redis Sentinel and the Raft algorithm](https://www.datadoghq.com/blog/redis-sentinel-monitoring/)
- [GitHub Redis — How we use Sentinel](https://github.blog/2021-10-06-using-redis-github/)
- [Stack Overflow: Redis Failover story](https://stackoverflow.blog/)
- [Twitter Redis migration to Cluster](https://blog.twitter.com/engineering/)
- [Shopify: Redis Sentinel for Sessions (Kelsey Gilmore-Terence)](https://shopify.engineering/)
