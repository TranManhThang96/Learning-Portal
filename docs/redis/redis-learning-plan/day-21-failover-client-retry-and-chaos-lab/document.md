# Day 21: Failover, Client Retry & Chaos Lab — Reference Document

---

## 1. Cheat Sheet: Chaos Testing Commands

### Pumba Commands

```bash
# Pull Pumba image
docker pull gaiaadm/pumba:1.5.0

# Kill Redis container (simulate hard crash)
docker kill redis-master

# Pause Redis container (simulate unresponsive, killable again)
docker pause redis-master
docker unpause redis-master

# Network latency 500ms + 50ms jitter
pumba netem --duration 60s --tc-image docker.io/library/alpine:3.18 \
  --interval 10s \
  redis-master \
  delay --time 500 --jitter 50

# Packet loss 10%
pumba netem --duration 30s --tc-image docker.io/library/alpine:3.18 \
  redis-master \
  loss --percent 10

# Packet corruption 5%
pumba netem --duration 30s --tc-image docker.io/library/alpine:3.18 \
  redis-master \
  corrupt --percent 5

# Bandwidth limit 100KB/s
pumba netem --duration 60s --tc-image docker.io/library/alpine:3.18 \
  redis-master \
  rate --rate 100k
```

### tc netem Commands (Manual, No Pumba)

```bash
# Check current network configuration on container eth0
docker exec redis-master tc qdisc show dev eth0

# Add 500ms latency
docker exec redis-master tc qdisc add dev eth0 root netem delay 500ms 50ms

# Change latency (when rule already exists)
docker exec redis-master tc qdisc change dev eth0 root netem delay 500ms 50ms

# Add 10% packet loss
docker exec redis-master tc qdisc change dev eth0 root netem loss 10%

# Full partition (100% drop — use with care)
docker exec redis-master tc qdisc add dev eth0 root netem loss 100%

# Remove all netem rules
docker exec redis-master tc qdisc del dev eth0 root

# Combination: latency + packet loss
docker exec redis-master tc qdisc change dev eth0 root netem delay 200ms 20ms loss 5%
```

### iptables DROP (Hard Partition)

```bash
# Block all traffic FROM Redis (client can't reach Redis)
docker exec redis-master iptables -I INPUT -j DROP

# Block all traffic TO Redis (Redis can't receive from clients)
docker exec redis-master iptables -I OUTPUT -j DROP

# Block Redis port specifically
docker exec redis-master iptables -A INPUT -p tcp --dport 6379 -j DROP

# Remove all iptables rules (restore)
docker exec redis-master iptables -F

# Restore specific rule
docker exec redis-master iptables -D INPUT -p tcp --dport 6379 -j DROP
```

### Toxiproxy Commands (Recommended for Programmatic)

```bash
# Install Toxiproxy server
docker run -d --name toxiproxy -p 8474:8474 -p 16379:6379 \
  shopify/toxiproxy:latest

# CLI create proxy (Redis behind toxiproxy)
toxiproxy-cli create redis --listen 127.0.0.1:16379 --upstream 127.0.0.1:6379

# Add toxic: latency
toxiproxy-cli toxic add redis --toxicName latency --type latency \
  --attribute latency=500 --attribute jitter=50

# Add toxic: packet loss (percent)
toxiproxy-cli toxic add redis --toxicName loss --type limit_data \
  --attribute limit_bytes=0

# Add toxic: slow close (simulate slow disk)
toxiproxy-cli toxic add redis --toxicName slowclose --type slow_close \
  --attribute delay=5000

# Remove toxic
toxiproxy-cli toxic remove redis --toxicName latency

# List all toxics
toxiproxy-cli toxic list redis
```

---

## 2. Config Templates

### TypeScript ioredis (Sentinel + Retry + Jitter)

```typescript
// redis-client.ts
import Redis from "ioredis";
import { EventEmitter } from "events";

// Circuit breaker state machine
type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

class CircuitBreaker extends EventEmitter {
  private state: CircuitState = "CLOSED";
  private failures = 0;
  private lastFailureTime = 0;
  private halfOpenProbes = 0;
  private readonly threshold: number;
  private readonly resetTimeout: number; // ms
  private readonly halfOpenRecoveryThreshold: number;

  constructor(
    threshold = 5,
    resetTimeout = 30000,
    halfOpenRecoveryThreshold = 2,
  ) {
    super();
    this.threshold = threshold;
    this.resetTimeout = resetTimeout;
    this.halfOpenRecoveryThreshold = halfOpenRecoveryThreshold;
  }

  recordFailure(): void {
    this.failures++;
    this.lastFailureTime = Date.now();
    if (this.state === "HALF_OPEN") {
      this.state = "OPEN";
      this.emit("open");
    } else if (this.failures >= this.threshold) {
      this.state = "OPEN";
      this.emit("open");
    }
  }

  recordSuccess(): void {
    if (this.state === "HALF_OPEN") {
      this.halfOpenProbes++;
      if (this.halfOpenProbes >= this.halfOpenRecoveryThreshold) {
        this.state = "CLOSED";
        this.failures = 0;
        this.halfOpenProbes = 0;
        this.emit("closed");
      }
    } else if (this.state === "CLOSED") {
      this.failures = Math.max(0, this.failures - 1);
    }
  }

  isOpen(): boolean {
    if (this.state === "OPEN") {
      if (Date.now() - this.lastFailureTime > this.resetTimeout) {
        this.state = "HALF_OPEN";
        this.halfOpenProbes = 0;
        this.emit("half_open");
        return false;
      }
      return true;
    }
    return false;
  }

  getState(): CircuitState {
    return this.state;
  }
}

// Full jitter backoff
function fullJitterBackoff(attempt: number, baseMs = 100): number {
  const cap = 30000;
  const exp = baseMs * Math.pow(2, attempt);
  const jitter = Math.floor(Math.random() * Math.min(exp, cap));
  return jitter;
}

// Redis client with Sentinel, retry, jitter, circuit breaker
export class RedisClient {
  private client: Redis;
  private readonly circuitBreaker: CircuitBreaker;
  private readonly maxRetries = 3;

  constructor() {
    this.circuitBreaker = new CircuitBreaker(
      /* threshold */ 5,
      /* resetTimeout */ 30_000,
      /* halfOpenRecovery */ 2,
    );

    this.client = new Redis({
      // Sentinel config
      sentinels: [
        { host: "localhost", port: 26379 },
        { host: "localhost", port: 26380 },
        { host: "localhost", port: 26381 },
      ],
      name: "mymaster",
      role: "master",

      // Timeout — MUST be > 3× failover time
      connectTimeout: 10_000,
      maxRetriesPerRequest: 1, // Only 1 retry to avoid doubling wait time

      // Retry with full jitter
      retryStrategy: (times: number) => {
        if (times > this.maxRetries) return null; // Stop retrying
        return fullJitterBackoff(times);
      },

      // Don't queue writes when disconnected
      enableOfflineQueue: false,
      enableReadyCheck: true,

      // Sentinel event subscription
      sentinelRetryStrategy: (times: number) => {
        return Math.min(times * 200, 2000);
      },
    });

    // Subscribe to Sentinel events
    this.client.on("sentinelSwitch", (masterName: string, newMasterAddr: string) => {
      console.log(`[Sentinel] Master "${masterName}" switched to ${newMasterAddr}`);
      // Force full reconnection to new master
      this.client.disconnect(false);
      this.client.connect();
    });

    this.client.on("error", (err) => {
      console.error("[Redis] Error:", err.message);
      this.circuitBreaker.recordFailure();
    });

    this.client.on("connect", () => {
      this.circuitBreaker.recordSuccess();
    });
  }

  async get(key: string): Promise<string | null> {
    if (this.circuitBreaker.isOpen()) {
      throw new Error("Circuit breaker OPEN");
    }
    try {
      return await this.client.get(key);
    } catch (err: any) {
      this.circuitBreaker.recordFailure();
      throw err;
    }
  }

  async set(key: string, value: string, ttlSeconds?: number): Promise<string> {
    if (this.circuitBreaker.isOpen()) {
      throw new Error("Circuit breaker OPEN");
    }
    try {
      if (ttlSeconds) {
        return await this.client.set(key, value, "EX", ttlSeconds);
      }
      return await this.client.set(key, value);
    } catch (err: any) {
      this.circuitBreaker.recordFailure();
      throw err;
    }
  }

  getCircuitState(): CircuitState {
    return this.circuitBreaker.getState();
  }
}
```

### Go go-redis (Sentinel + Retry + Backoff + Jitter)

```go
// redis_client.go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"net"
	"time"

	"github.com/redis/go-redis/v9"
)

// Full jitter backoff
func backoffWithJitter(attempt int) time.Duration {
	base := 100 * time.Millisecond
	maxDelay := 30 * time.Second

	exp := base * time.Duration(1<<uint(attempt))
	jitter := time.Duration(rand.Int63n(int64(exp)))

	if jitter > maxDelay {
		jitter = maxDelay
	}
	return jitter
}

// Retryable error check
func isRetryable(err error) bool {
	if err == nil {
		return false
	}
	// Connection errors, timeouts are retryable
	return true
}

// Execute with retry + jitter
func doWithRetry(ctx context.Context, rdb *redis.Client, op func() error) error {
	const maxRetries = 3

	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}

		lastErr = op()
		if lastErr == nil {
			return nil
		}

		if isRetryable(lastErr) {
			delay := backoffWithJitter(attempt)
			select {
			case <-time.After(delay):
				// Continue to next retry
			case <-ctx.Done():
				return ctx.Err()
			}
		} else {
			return lastErr
		}
	}
	return fmt.Errorf("max retries exceeded: %w", lastErr)
}

// Sentinel client setup
func newRedisClient() *redis.Client {
	rdb := redis.NewFailoverClient(&redis.FailoverOptions{
		MasterName:    "mymaster",
		SentinelAddrs: []string{"localhost:26379", "localhost:26380", "localhost:26381"},

		// Timeout — critical: must exceed failover time
		Dialer: func(ctx context.Context, network, addr string) (net.Conn, error) {
			network = "tcp"
			dialer := &net.Dialer{
				Timeout: 10 * time.Second,
			}
			return dialer.DialContext(ctx, network, addr)
		},

		// Read/write timeout
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,

		// Pool config
		PoolSize:     50,
		MinIdleConns: 10,
		PoolTimeout:  15 * time.Second,

		// Route reads to replica (stale-ok for cache)
		RouteByLatency: true,
	})

	return rdb
}

// Usage example
func main() {
	ctx := context.Background()
	rdb := newRedisClient()

	// GET with retry
	val, err := doWithRetry(ctx, rdb, func() error {
		return rdb.Get(ctx, "cache:user:123").Err()
	})
	if err != nil {
		fmt.Printf("Failed after retries: %v\n", err)
	} else {
		fmt.Printf("Got value: %s\n", val)
	}
}
```

---

## 3. Toxiproxy Script

```bash
#!/bin/bash
# chaos_redis.sh — Chaos testing script for Redis using Toxiproxy

TOXIPROXY_HOST="localhost:8474"
PROXY_NAME="redis"
PROXY_LISTEN="localhost:16379"
PROXY_UPSTREAM="localhost:6379"

# Check if toxiproxy is running
check_toxiproxy() {
  curl -s "http://${TOXIPROXY_HOST}/api/version" > /dev/null 2>&1
  return $?
}

# Create proxy
create_proxy() {
  echo "[Setup] Creating Toxiproxy proxy: ${PROXY_NAME}"
  curl -s -X POST "http://${TOXIPROXY_HOST}/api/proxies" \
    -d "name=${PROXY_NAME}&listen=${PROXY_LISTEN}&upstream=${PROXY_UPSTREAM}"
  echo ""
}

# Remove proxy
remove_proxy() {
  echo "[Cleanup] Removing Toxiproxy proxy: ${PROXY_NAME}"
  curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}"
  echo ""
}

# Add latency toxic
add_latency() {
  local latency_ms=$1
  local jitter_ms=$2
  echo "[Scenario] Adding ${latency_ms}ms latency (±${jitter_ms}ms)"
  curl -s -X POST "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"latency\",\"type\":\"latency\",\"toxicName\":\"latency\",\"attributes\":{\"latency\":${latency_ms},\"jitter\":${jitter_ms}}}"
  echo ""
}

# Toxiproxy OSS does not model percentage packet loss directly.
# For packet loss percentage use Pumba/tc netem above; this function creates a timeout toxic.
add_loss() {
  local percent=$1
  echo "[Scenario] Simulating loss-like behavior with timeout toxic (requested ${percent}% loss)"
  curl -s -X POST "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"loss\",\"type\":\"timeout\",\"toxicName\":\"loss\",\"attributes\":{\"timeout\":1000}}"
  echo ""
}

# Add bandwidth limit toxic
add_bandwidth() {
  local rate=$1
  echo "[Scenario] Setting bandwidth limit to ${rate} bytes/s"
  curl -s -X POST "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"bandwidth\",\"type\":\"bandwidth\",\"toxicName\":\"bandwidth\",\"attributes\":{\"rate\":${rate}}}"
  echo ""
}

# Remove all toxics
remove_all_toxics() {
  echo "[Cleanup] Removing all toxics"
  curl -s "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics" | \
    jq -r '.[] | .name' | while read name; do
      curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics/${name}"
    done
  echo ""
}

# Scenario runners
scenario_latency() {
  add_latency 500 50
  echo "[Hold] Running for $1 seconds..."
  sleep "$1"
  echo "[Restore] Removing latency..."
  curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics/latency" 2>/dev/null
}

scenario_loss() {
  add_loss 20
  echo "[Hold] Running for $1 seconds..."
  sleep "$1"
  echo "[Restore] Removing packet loss..."
  curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics/loss" 2>/dev/null
}

scenario_slow_connection() {
  add_bandwidth 1024
  echo "[Hold] Running for $1 seconds (1KB/s bandwidth)..."
  sleep "$1"
  echo "[Restore] Removing bandwidth limit..."
  curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics/bandwidth" 2>/dev/null
}

scenario_full_partition() {
  echo "[Scenario] Creating full partition (timeout)"
  curl -s -X POST "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics" \
    -H "Content-Type: application/json" \
    -d '{"name":"partition","type":"timeout","toxicName":"partition","attributes":{"timeout":1}}'
  echo ""
  echo "[Hold] Partition active for $1 seconds..."
  sleep "$1"
  echo "[Restore] Removing partition..."
  curl -s -X DELETE "http://${TOXIPROXY_HOST}/api/proxies/${PROXY_NAME}/toxics/partition" 2>/dev/null
}

# Main
if ! check_toxiproxy; then
  echo "[ERROR] Toxiproxy is not running. Start with:"
  echo "  docker run -d --name toxiproxy -p 8474:8474 -p 16379:6379 shopify/toxiproxy:latest"
  exit 1
fi

remove_proxy
create_proxy

# Run all scenarios
echo ""
echo "=== Scenario 1: Network Latency 500ms ==="
scenario_latency 15

echo ""
echo "=== Scenario 2: Packet Loss 20% ==="
scenario_loss 15

echo ""
echo "=== Scenario 3: Slow Connection (1KB/s) ==="
scenario_slow_connection 15

echo ""
echo "=== Scenario 4: Full Partition (10s) ==="
scenario_full_partition 10

echo ""
echo "=== Chaos testing complete ==="
remove_proxy
```

---

## 4. Postmortem Template

```markdown
# Postmortem: Redis Failover Incident

**Date**: YYYY-MM-DD HH:MM – HH:MM (UTC)
**Duration**: X minutes
**Severity**: P0 / P1 / P2 / P3
**Services affected**: [list]
**On-call**: [name]

---

## Summary

[1-2 sentences: What happened, impact, how it was resolved]

---

## Timeline (UTC)

| Time | Event |
|---|---|
| HH:MM | [Alert fired] [Root cause] |
| HH:MM | [Engineer notified] |
| HH:MM | [Investigation started] |
| HH:MM | [Mitigation applied] |
| HH:MM | [Service recovered] |
| HH:MM | [Postmortem started] |

---

## Root Cause Analysis (5 Whys)

**Why 1**: [What happened]
**Why 2**: [Why did that happen]
**Why 3**: [Why did that happen]
**Why 4**: [Why did that happen]
**Why 5**: [Why did that happen]

**Root Cause**: [Final root cause — specific and actionable]

---

## Impact

- **Error rate**: X% for Y minutes (baseline: Z%)
- **Affected requests**: ~X requests
- **User impact**: [specific user-visible impact]
- **Revenue impact**: [if applicable]
- **p99 latency**: Xms → Yms (peak during incident)

---

## Detection

- How was the incident detected?
- How long from incident start to detection?
- Alert threshold that triggered?

---

## Mitigation

| Action | Time to Apply | Effectiveness |
|---|---|---|
| [Action 1] | X min | High/Medium/Low |
| [Action 2] | X min | High/Medium/Low |

---

## Action Items

| Item | Owner | Priority | Due Date |
|---|---|---|---|
| [ ] [Action 1 — specific] | @name | P1 | YYYY-MM-DD |
| [ ] [Action 2 — specific] | @name | P2 | YYYY-MM-DD |
| [ ] [Action 3 — specific] | @name | P2 | YYYY-MM-DD |
| [ ] [Action 4 — specific] | @name | P3 | YYYY-MM-DD |

---

## Lessons Learned

**What went well**:
- [Point 1]
- [Point 2]

**What didn't go well**:
- [Point 1]
- [Point 2]

**What we'll do differently**:
- [Point 1]
- [Point 2]
```

---

## 5. Production Runbook Checklist

### Pre-Incident (Proactive)

- [ ] Sentinel quorum = 2 (for 3 Sentinel) or 3 (for 5 Sentinel)
- [ ] `min-replica-max-lag` set to ≥ 10 seconds
- [ ] `down-after-milliseconds` ≤ 3000ms
- [ ] `failover-timeout` ≥ 18000ms
- [ ] Client connectTimeout ≥ 10s (self-hosted) / ≥ 15s (managed)
- [ ] Client readTimeout ≥ 10s (self-hosted) / ≥ 15s (managed)
- [ ] Client retryStrategy has jitter (not fixed delay)
- [ ] Client subscribes to Sentinel Pub/Sub (+switch-master, +sdown, +reboot)
- [ ] Client `enableOfflineQueue: false` (writes fail fast when disconnected)
- [ ] DNS TTL ≤ 15s for Redis endpoints
- [ ] Circuit breaker configured per use case
- [ ] `appendfsync everysec` (NOT always) on all instances
- [ ] Replica monitoring: alert when lag > 5MB sustained > 30s
- [ ] Redis memory headroom: ≤ 70% used_memory at peak
- [ ] Chaos testing script reviewed and working

### During Incident (Reactive)

- [ ] Verify failover status: `SENTINEL get-master-addr-by-name <master-name>`
- [ ] Check replica lag: `redis-cli -h <replica-ip> INFO replication`
- [ ] Check Sentinel quorum: `redis-cli -h <sentinel-ip> SENTINEL get-master-addr-by-name <name>`
- [ ] If data loss suspected: `SENTINEL masters` → check `sentinelMaster->configEpoch`
- [ ] Notify on-call for P0/P1 within 5 minutes
- [ ] If circuit breaker not auto-tripping: manual circuit open
- [ ] If retry storm suspected: enable rate limiting on fallback path
- [ ] Monitor DB CPU during fallback (alert if > 80%)

### Post-Incident

- [ ] Verify all clients reconnected to new master
- [ ] Check `INFO replication` on new master: role, connected_slaves
- [ ] Run postmortem within 48 hours
- [ ] Update runbook with lessons learned
- [ ] Verify chaos test covers this scenario for next run
- [ ] Review action items from previous postmortems

---

## 6. Links & References

- [Redis Sentinel Documentation](https://redis.io/docs/management/sentinel/)
- [Redis Replication Documentation](https://redis.io/docs/management/replication/)
- [SRE Book — Chapter 4: Service Level Objectives](https://sre.google/sre-book/chapter/)
- [SRE Book — Chapter 13: The Truth Is in the Logs](https://sre.google/sre-book/chapter/)
- [Google SRE — Building Secure and Reliable Systems — Chapter 9: Handling Overload](https://sre.google/sre-book/building-secure-reliable-systems/)
- [Toxiproxy GitHub](https://github.com/Shopify/toxiproxy)
- [Pumba GitHub](https://github.com/alexei-led/pumba)
- [AWS ElastiCache Failover Behavior](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/AutoFailover.html)
- [Exponential backoff and jitter — AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Circuit Breaker pattern — Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- [chaos-mesh](https://chaos-mesh.org/) — Kubernetes-native chaos testing
- [go-redis Failover Client](https://redis.uptrace.dev/guide/go-redis.html#failover-support)
- [ioredis Sentinel](https://redis.io/docs/clients/redis-client-for-javascript/)
