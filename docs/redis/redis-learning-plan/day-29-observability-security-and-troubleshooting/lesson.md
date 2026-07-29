# Day 29: Observability, Security & Troubleshooting

---

## 1. Mục tiêu bài học

Sau bài học, bạn sẽ:

- Monitor được tất cả metrics quan trọng của Redis: hit rate, miss rate, evicted keys, expired keys, memory usage, fragmentation ratio, connected clients, blocked clients, ops/sec, replication lag, command latency, p95/p99 latency bằng `redis_exporter` + Prometheus + Grafana.
- Configure được Redis ACL (user/password/permission), TLS, command renaming/disabling để bảo vệ Redis trong production.
- Troubleshoot được 8 failure mode phổ biến: high latency, high memory, high CPU, replication lag, failover issue, connection explosion, slow command, unexpected eviction.
- Phân tích được trade-off giữa monitoring overhead vs insight quality, alert sensitivity vs noise, TLS security vs latency overhead, expose Redis internally vs proxy/gateway, disable commands vs operational convenience.
- Viết được troubleshooting runbook có actionable steps, threshold cụ thể, và escalation path.

---

## 2. Vì sao cần học chủ đề này

### Incident 1: Không Có Monitoring — Silent Data Loss

Một startup chạy Redis làm session store cho 1 triệu users. Một ngày nọ, ops team phát hiện `evicted_keys` counter tăng vọt từ 0 lên 50,000 trong 30 phút. Root cause: developer deploy code mới, `maxmemory-policy` bị change từ `allkeys-lru` thành `noeviction`, Redis bắt đầu reject writes → users bị logged out hàng loạt. Không có monitoring → không ai biết cho đến khi user complaints flood in.

**Lesson**: Monitoring không phải là optional. Memory pressure, eviction, connection exhaustion có thể xảy ra bất cứ lúc nào — không có visibility = incident càng lớn.

### Incident 2: Redis Không Có ACL — Production Breach

Một team deploy Redis lên cloud với `protected-mode no` và không có password. Một security scan expose port 6379 publicly. Attacker kết nối, gõ `FLUSHALL` → toàn bộ cache gone → database overload → cascade failure. Estimated damage: 2 giờ downtime, 50,000 users affected.

**Lesson**: Redis mặc định không có authentication. Trong production, **ACL là bắt buộc**, không phải optional.

### Incident 3: High Latency Không Được Debug — Cascade Failure

Một e-commerce site chậm bất thường trong 20 phút. Operations team restart Redis nhiều lần nhưng không giải quyết được. Investigation sau đó: một developer chạy `KEYS *` trên production Redis có 10 triệu keys → single-threaded Redis blocked 8 giây → tất cả requests queue → timeout cascade.

**Lesson**: `KEYS` command là synchronous blocking command. Không có `SLOWLOG` monitoring = developer không biết mình gây ra incident.

### Incident 4: Netflix — Redis Latency Spike Causing Stream Interruption

Netflix gặp incident khi Redis latency spike lên 500ms+ do slow AOF rewrite. Vấn đề: không có command latency histogram monitoring → team không biết p99 latency đã tăng trước khi gây ra user-visible errors. Sau incident, team implement percentile-based latency monitoring và alert.

**Lesson**: Average latency là meaningless. p95/p99 latency là what matters for user experience. Phải monitor latency distribution, không chỉ average.

---

## 3. Kiến thức nền cần có

- **Day 8 Memory Management & Eviction**: `maxmemory`, eviction policies, lazy expiration — để hiểu eviction metrics
- **Day 9 Memory Optimization**: `mem_fragmentation_ratio`, `MEMORY DOCTOR`, jemalloc — để debug memory issues
- **Day 13 Latency Analysis**: `SLOWLOG`, `LATENCY DOCTOR`, `redis-cli --latency`, benchmark tools — để diagnose latency
- **Day 19 Replication**: `master_repl_offset`, `slave_repl_offset`, replica lag — để monitor replication health
- **Day 20 Sentinel & HA**: failover mechanism, `min-replicas-to-write` — để troubleshoot failover issues
- **Day 14 Hot Key & Big Key**: detection, impact on CPU/network/latency — để identify slow command causes

---

## 4. Lý thuyết chi tiết

### 4.1. Key Metrics — Tất Cả Những Gì Cần Monitor

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    Redis Metrics Hierarchy                                   │
│                                                                              │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐                 │
│  │   PERFORMANCE  │   │    MEMORY     │   │  AVAILABILITY  │                 │
│  ├────────────────┤   ├────────────────┤   ├────────────────┤                 │
│  │ ops/sec        │   │ used_memory    │   │ connected_clients│               │
│  │ command latency│   │ maxmemory      │   │ blocked_clients │               │
│  │ p95/p99 lat    │   │ mem_fragment   │   │ replication lag  │               │
│  │ slowlog count  │   │ evicted_keys   │   │ master_link_status│               │
│  └────────────────┘   └────────────────┘   └────────────────┘                 │
│                                                                              │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐                 │
│  │   CACHE        │   │   PERSISTENCE  │   │     CLIENTS    │                 │
│  ├────────────────┤   ├────────────────┤   ├────────────────┤                 │
│  │ keyspace_hits  │   │ aof_rewrite    │   │ total_connections│               │
│  │ keyspace_misses│   │ rdb_bgsave     │   │ rejected_connections│             │
│  │ hit_rate       │   │ last_fork_time │   │ client_biggest_input_buf│       │
│  │ expired_keys   │   │ fsync_rate     │   │ client_longest_output_list│     │
│  └────────────────┘   └────────────────┘   └────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Cache Metrics** (tính từ `INFO stats`):

```
hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses) × 100
```

- `keyspace_hits`: Số lần GET tìm thấy key
- `keyspace_misses`: Số lần GET không tìm thấy key
- `expired_keys`: Số keys đã expire (via active expiration, không phải lazy)

**Memory Metrics** (từ `INFO memory`):

```
used_memory_human: 2.3G
used_memory_peak_human: 3.1G
mem_fragmentation_ratio: 1.45
mem_aof_rewrite_in_progress: 0
mem_rss_human: 3.3G     ← actual RSS, includes fragmentation
```

**Fragmentation ratio interpretation**:
- `< 1.5`: healthy
- `1.5 - 2.0`: warning — consider restarting or enabling active defrag
- `> 2.0`: critical — restart immediately
- `< 1.0`: overcommitted — system is swapping

**Replication Metrics** (từ `INFO replication`):

```
connected_slaves: 3
slave0:ip=10.0.1.20,port=6380,state=online,offset=1234567,lag=0
slave1:ip=10.0.1.21,port=6381,state=online,offset=1234560,lag=7
# lag = bytes behind master
```

**Client Metrics** (từ `INFO clients`):

```
connected_clients: 1523
blocked_clients: 3
tracking_clients: 0
client_longest_output_list: 2048
client_biggest_input_buf: 1024
rejected_connections: 0   ← CRITICAL: should be 0
```

**Command Latency** (từ `INFO commandstats`):

```
cmdstat_get:calls=1000000,usec=500000,usec_per_call=0.50
cmdstat_set:calls=500000,usec=2500000,usec_per_call=5.00
cmdstat_keys:calls=10,usec=8000000,usec_per_call=800000.00  ← WARNING!
```

### 4.2. Prometheus + Grafana + Redis Exporter

**redis_exporter** là agent chạy song song với Redis, expose tất cả metrics qua `/metrics` endpoint theo Prometheus format.

```
┌──────────────┐       ┌─────────────────┐       ┌──────────────┐
│   Redis      │       │  redis_exporter │       │  Prometheus  │
│  (port 6379) │───────│  (port 9121)    │───────│  (scrape)    │
│              │ INFO  │                 │       │              │
│              │       │  /metrics        │       │              │
└──────────────┘       └─────────────────┘       └──────┬───────┘
                                                        │
                                               ┌────────▼────────┐
                                               │    Grafana     │
                                               │  (dashboard)   │
                                               └────────────────┘
```

**Key Prometheus metrics from redis_exporter**:

```
# Memory
redis_memory_used_bytes{instance="redis-master:6379"}
redis_memory_max_bytes{instance="redis-master:6379"}
redis_mem_fragmentation_ratio{instance="redis-master:6379"}

# Cache hit rate
redis_keyspace_hits_total{instance="redis-master:6379"}
redis_keyspace_misses_total{instance="redis-master:6379"}

# Eviction
redis_evicted_keys_total{instance="redis-master:6379"}
redis_expired_keys_total{instance="redis-master:6379"}

# Replication
redis_connected_slaves{instance="redis-master:6379"}
redis_replication_lag_seconds{instance="redis-master:6379"}

# Clients
redis_connected_clients{instance="redis-master:6379"}
redis_blocked_clients{instance="redis-master:6379"}
redis_rejected_connections_total{instance="redis-master:6379"}

# Command latency p95/p99
# redis_exporter chỉ có aggregate commandstats; p95/p99 cần client-side histogram.
redis_client_command_duration_seconds_sum{instance="api-1",cmd="get"}
redis_client_command_duration_seconds_bucket{instance="api-1",cmd="get",le="0.001"}
```

**Alert rule examples** (Prometheus alert rules):

```yaml
# RedisHighMemoryUsage
- alert: RedisHighMemoryUsage
  expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Redis memory usage above 85%"
    description: "{{ $labels.instance }} memory usage is {{ $value | humanizePercentage }}"

# RedisReplicationLag
- alert: RedisReplicationLag
  expr: redis_replication_lag_seconds > 5
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Redis replication lag exceeds 5 seconds"
    description: "{{ $labels.instance }} is {{ $value }}s behind master"

# RedisCommandLatencyP99
- alert: RedisCommandLatencyP99
  expr: histogram_quantile(0.99, sum(rate(redis_client_command_duration_seconds_bucket[5m])) by (le, instance, cmd)) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Redis p99 command latency above 100ms"
    description: "{{ $labels.instance }} p99 latency is {{ $value }}s for command {{ $labels.cmd }}"
```

### 4.3. ELK Integration — Log Aggregation

Redis logs chứa critical information: slow commands, connection events, replication events, memory warnings.

```
# redis.conf — configure log destination
loglevel notice
logfile /var/log/redis/redis.log
```

**Log → Filebeat → Elasticsearch flow**:

```
Redis (logfile) → Filebeat (sidecar) → Logstash → Elasticsearch
                                              ↓
                                    Kibana (visualize logs)
```

**Key log patterns to alert on**:

```
# Slow command (when command exceeds slowlog-log-slower-than)
12345:M 19 May 2025 14:23:45.123 # 10 commands completed in 15000.000000 microseconds
12345:M 19 May 2025 14:23:45.123 #    SLOWLOG: 'KEYS' with args 'user:*' (5000000 microseconds)

# Connection rejected (maxclients reached)
12345:M 19 May 2025 14:24:00.001 # WARNING: 100 clients connected, max clients is 100

# Out of memory (eviction)
12345:M 19 May 2025 14:25:00.000 # WARNING: 10000 keys evicted due to maxmemory limit

# Replication broken
12345:M 19 May 2025 14:26:00.000 # WARNING: replica 10.0.1.20:6380 has memory footprint larger than maxmemory

# Failover event
12345:M 19 May 2025 14:27:00.000 # +promoted-slave slave0:10.0.1.20:6380
```

**ELK JSON log format** (structured logging):

```json
{
  "@timestamp": "2025-05-19T14:23:45.123Z",
  "level": "WARNING",
  "message": "Slow command executed",
  "instance": "redis-master:6379",
  "command": "KEYS",
  "args": "user:*",
  "duration_us": 5000000,
  "pid": 12345
}
```

### 4.4. Redis ACL — User Management

ACL (Access Control List) từ Redis 6+ cho phép tạo named users với fine-grained permissions.

```txt
# View current ACL rules
ACL LIST

# Create user with password and permissions
ACL SETUSER alice on >secretpass ~cache:* -@all +get +set +del +exists

# ACL rule breakdown:
#   alice          → username
#   on             → user is enabled
#   >secretpass    → password is "secretpass"
#   ~cache:*       → can only access keys matching pattern cache:*
#   -@all          → deny all commands
#   +get +set ...  → allow specific commands
#   +@read         → allow all read commands (GET, HGET, LRANGE, etc.)
#   +@write        → allow all write commands (SET, DEL, HSET, etc.)
#   +@dangerous    → allow FLUSHDB, FLUSHALL, SHUTDOWN, CONFIG, etc. (BE CAREFUL)

# Read-only user for monitoring
ACL SETUSER monitoring on >monpass ~* +info +ping +type +dbsize +memory|stats +slowlog|get +command +client|list

# Admin user (full access but no CONFIG/SHUTDOWN for safety)
ACL SETUSER admin on >adminpass ~* +@all -@dangerous

# Superuser (full access)
ACL SETUSER superuser on >superpass ~* +@all

# Test user permissions
AUTH alice secretpass
GET cache:user:123    # OK
SET cache:user:123 {} # OK
FLUSHDB               # ERROR: NOPERM

# View user info
ACL GET alice

# Save ACL to config
ACL SAVE
```

**ACL categories**:

```
+@read       → GET, HGET, LRANGE, SMEMBERS, ZRANGE, etc.
+@write      → SET, HSET, LPUSH, SADD, ZADD, etc.
+@admin      → ADMIN commands
+@dangerous  → FLUSHDB, FLUSHALL, SHUTDOWN, DEBUG, MIGRATE, ROLE, SYNC, PSYNC
+@slow       → SINTER, SUNION, SDIFF, SORT (O(N) and O(N*log N))
+@pubsub      → PUBLISH, SUBSCRIBE, PSUBSCRIBE
+@transaction → MULTI, EXEC, DISCARD, WATCH
+@scripting   → EVAL, EVALSHA, FCALL
+@sortedset   → ZADD, ZRANGE, ZRANK, etc.
+@set         → SADD, SREM, SINTER, etc.
+@list        → LPUSH, RPUSH, LPOP, etc.
+@hash        → HSET, HGET, HGETALL, etc.
+@string      → GET, SET, INCR, DECR, etc.
```

### 4.5. TLS Configuration

TLS (Transport Layer Security) mã hóa traffic giữa Redis clients và server.

```txt
# redis.conf — TLS configuration

# Enable TLS
tls-port 6380
port 0                    # disable non-TLS port

# Certificates
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt

# TLS configurations
tls-cert-verify-clients optional   # required | optional | no
tls-protocols TLSv1.2 TLSv1.3

# For replica connections (Redis 6.2+)
tls-replication yes
```

**Docker Compose with TLS**:

```yaml
services:
  redis-tls:
    image: redis:7.2-alpine
    ports:
      - "6380:6380"
    volumes:
      - ./tls:/etc/redis/tls:ro
    command: >
      redis-server
      --tls-port 6380
      --port 0
      --tls-cert-file /etc/redis/tls/redis.crt
      --tls-key-file /etc/redis/tls/redis.key
      --tls-ca-cert-file /etc/redis/tls/ca.crt
      --tls-cert-verify-clients optional
      --tls-protocols TLSv1.2 TLSv1.3
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6380", "--tls", "--insecure", "ping"]
```

**Connection string with TLS** (Go):

```go
rdb := redis.NewClient(&redis.Options{
    Addr:     "localhost:6380",
    TLSConfig: &tls.Config{
        MinVersion: tls.VersionTLS12,
        // In production: Cert:     loadCert("/etc/redis/tls/client.crt"),
        //                KeyFile:  loadCert("/etc/redis/tls/client.key"),
        //                CaCert:   loadCert("/etc/redis/tls/ca.crt"),
        //                InsecureSkipVerify: false,  // NEVER true in production
    },
})
```

### 4.6. Command Renaming & Disabling Dangerous Commands

Redis cho phép rename commands trong `redis.conf`. Dùng để prevent accidental execution of dangerous commands hoặc prevent unauthorized access.

```txt
# redis.conf

# Rename dangerous commands
rename-command FLUSHDB "FLUSHDB_a1b2c3d4"
rename-command FLUSHALL "FLUSHALL_e5f6g7h8"
rename-command KEYS "KEYS_i9j0k1l2"
rename-command DEBUG ""
rename-command SHUTDOWN ""
rename-command CONFIG "CONFIG_m3n4o5p6"

# In case of emergency, you can still use original command via:
#   CONFIG SET / CONFIG GET
#   FLUSHDB via redis-cli --no--auth-warning -a password FLUSHDB_a1b2c3d4
```

**Command categories to consider renaming**:

| Command | Risk | Renamed As | Notes |
|---|---|---|---|
| `FLUSHDB` | Xóa tất cả keys trong current DB | `FLUSHDB_secure` | Rename, require ACL |
| `FLUSHALL` | Xóa tất cả keys tất cả DBs | `FLUSHALL_secure` | Highest risk |
| `KEYS` | Blocking, O(N), scan entire keyspace | `KEYS_slow` or `""` | Best to disable entirely |
| `DEBUG` | Exposes internals, can crash Redis | `""` (disable) | Never needed in production |
| `SHUTDOWN` | Stops Redis | `""` (disable) | Use systemctl/Supervisor |
| `CONFIG` | Change config at runtime | `CONFIG_safe` | Only if needed |
| `BGREWRITEAOF` | Disk I/O spike | keep | Can be useful |
| `BGSAVE` | Disk I/O, fork overhead | keep | Necessary for backups |
| `SLOWLOG` | No risk | keep | Essential for debugging |
| `CLIENT` | Can kill connections | keep | Admin tool |

**Security-first ACL + rename combo**:

```txt
# redis.conf
user default on nopass ~* +@read +ping +info +dbsize -@all

# Rename dangerous commands
rename-command FLUSHDB "FLUSHDB_prod_$(date +%s)"
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command DEBUG ""
rename-command SHUTDOWN ""

# Only admin user can use renamed commands
user admin on >admin_hash ~* resetchannels +@all -@dangerous
```

### 4.7. Network Isolation — Expose Redis Internally vs Proxy/Gateway

**Option A: Direct Internal Access** (simplest, highest risk):

```
┌──────────────┐
│   App        │───► Redis (10.0.1.10:6379)
│   Service    │     No password, same VPC
└──────────────┘
```
- Pros: Lowest latency, no proxy overhead
- Cons: Direct exposure, no rate limiting, no auth layer

**Option B: Redis AUTH + ACL** (recommended for internal):

```
┌──────────────┐
│   App        │───► Redis (ACL auth) ─── internal VPC only
│   Service    │     No TLS (internal network)
└──────────────┘
```
- Pros: Authentication, no TLS overhead, fine-grained permissions
- Cons: Still direct connection, no connection pooling

**Option C: Proxy/Gateway Layer** (most secure):

```
┌──────────────┐
│   App        │───► Proxy (Envoy/Twemproxy) ───► Redis Cluster
│   Service    │     Rate limiting, auth, circuit breaker
└──────────────┘
```
- Pros: Rate limiting, auth, circuit breaker, sharding
- Cons: Additional hop (1-3ms overhead), extra component to operate
- Tools: Twemproxy, Codis, Redis Cluster (built-in), Envoy Proxy, HAProxy

**Production recommendation**: Use Option B (ACL only) for internal services, Option C for multi-tenant or external-facing scenarios.

---

## 5. Trade-off Analysis

### Detailed Monitoring vs Overhead

| Aspect | Minimal Monitoring | Detailed Monitoring |
|---|---|---|
| **Metrics collected** | basic INFO output, polled every 60s | All counters, histograms, every 10s |
| **Overhead** | ~0ms (just INFO query) | redis_exporter ~2-5% CPU at 10K metrics |
| **Insight quality** | High-level, slow detection | Full visibility, early warning |
| **p99 latency detection** | Cannot detect | Histogram shows p95/p99 spikes |
| **Alert accuracy** | Low (average-based) | High (percentile-based) |
| **Use case** | Dev/test environment | Production with SLA |
| **Risk of over-monitoring** | Silent incidents | Metric query adds small load |

**Recommendation**: Production = detailed (redis_exporter + Prometheus). Dev = minimal (redis-cli INFO). Never skip monitoring entirely.

### Alert Sensitivity vs Noise

| Aspect | Too Sensitive | Too Loose |
|---|---|---|
| **Memory threshold** | > 70% = warning | > 95% = warning (eviction already happening) |
| **Replication lag** | > 1s = alert | > 60s = alert (minutes of stale data) |
| **p99 latency** | > 10ms = alert | > 500ms = alert (user impact already severe) |
| **Effect** | Alert fatigue → ignored | Incidents missed until critical |
| **Best practice** | Multi-level: warning at 70%, critical at 85% | Warning at 70%, critical at 85%, with 5m sustained |

**Multi-level alert template**:

```yaml
# Memory: warning → critical
- alert: RedisMemoryWarning
  expr: used_memory / maxmemory > 0.75
  for: 5m
  labels: { severity: warning }
- alert: RedisMemoryCritical
  expr: used_memory / maxmemory > 0.90
  for: 2m
  labels: { severity: critical }
```

### TLS Security vs Latency Overhead

| Aspect | Without TLS | With TLS |
|---|---|---|
| **Security** | None (plaintext) | Encrypted, authenticated |
| **Latency overhead** | 0ms | +1-3ms per connection (handshake) |
| **Throughput** | Maximum | -2-5% throughput (encryption CPU) |
| **Certificate management** | None | Required, rotation needed |
| **Internal network** | OK if VPC-isolated | Overkill (adds latency, complexity) |
| **External access / cloud** | Dangerous | Required |
| **Connection reuse** | N/A | TLS session resumption reduces handshake cost |

**Recommendation**:
- Internal VPC: No TLS (latency critical), use ACL + network isolation
- Cross-AZ / cloud: TLS (security critical), accept overhead
- TLS 1.3 with session resumption: reduces overhead to < 1ms

### Disable Commands vs Operational Convenience

| Command | Disable Risk | Enable Risk | Recommendation |
|---|---|---|---|
| `FLUSHDB`/`FLUSHALL` | Harder to clean up in emergency | Accidental data loss | Rename + ACL restrict |
| `KEYS` | Developers complain | Blocks Redis for seconds | Disable entirely, use SCAN |
| `DEBUG` | Can't debug internals | Can crash Redis | Disable |
| `SHUTDOWN` | Must use systemctl | Accidental shutdown | Disable |
| `CONFIG` | Runtime changes impossible | Security risk | Rename + admin-only |
| `BGREWRITEAOF` | No AOF optimization | Disk I/O spike | Keep, monitor |

**Best practice**: Rename all dangerous commands + use ACL to restrict. Keep commands accessible via privileged admin user.

### Expose Redis Internally vs Proxy/Gateway

| Aspect | Direct Access | Proxy Layer |
|---|---|---|
| **Latency** | 0-1ms | +1-3ms per request |
| **Auth** | ACL (named users) | ACL on proxy + Redis |
| **Rate limiting** | Not built-in | Built-in |
| **Circuit breaker** | Not built-in | Built-in |
| **Sharding** | Not built-in (unless Cluster) | Built-in |
| **Connection pooling** | Client-side | Proxy handles |
| **Operational complexity** | Low | High (proxy is another component) |
| **Multi-tenant** | ACL only (limited) | Full tenant isolation |
| **Best for** | Internal, low-latency, trusted network | External, multi-tenant, sharding |

---

## 6. Best Solution & Best Practices

### Production Monitoring Stack

```
┌─────────────────────────────────────────────────────────┐
│              Recommended Stack                            │
│                                                          │
│  Redis (7.2+)                                            │
│     │                                                     │
│     ├─ redis_exporter (sidecar or separate host)         │
│     │     scrape: 15s interval                           │
│     │                                                     │
│     └─ Prometheus                                        │
│           scrape_interval: 15s                           │
│           retention: 90 days                             │
│           recording rules for p95/p99                    │
│                                                          │
│     └─ Grafana                                            │
│           Dashboard: Redis Dashboard #11835               │
│           Alertmanager (PagerDuty/Slack)                 │
│                                                          │
│     └─ ELK Stack (optional, for logs)                   │
│           Filebeat → Logstash → Elasticsearch            │
│           slowlog events as structured logs              │
└─────────────────────────────────────────────────────────┘
```

### Alert Thresholds — Production Ready

| Metric | Warning | Critical | Sustained | Action |
|---|---|---|---|---|
| Memory usage | > 75% | > 90% | 5 min | Investigate, scale |
| Evicted keys | > 100/min | > 1000/min | 2 min | Review eviction policy, scale |
| Replication lag | > 1s | > 5s | 2 min | Check network, replica health |
| Connected clients | > 80% of `maxclients` | > 95% | 1 min | Review connection leaks |
| Blocked clients | > 0 | > 10 | Immediate | Investigate blocking commands |
| p99 latency | > 50ms | > 200ms | 5 min | Find slow commands |
| Slowlog entries | > 10/min | > 100/min | 2 min | Analyze with SLOWLOG |
| Fragmentation ratio | > 1.5 | > 2.0 | 10 min | Restart or defrag |
| Rejected connections | > 0 | > 10 | Immediate | Increase maxclients, check ACL |
| AOF rewrite | > 30s | > 60s | Immediate | Check disk I/O |

### Scenario-Based Recommendations

**Scenario 1: High-traffic Cache (100K ops/sec, 95% reads)**

```
Monitoring:
  - Hit rate: alert if < 95%
  - Memory: alert at 80% (scale before eviction)
  - p99 latency: alert at 50ms
Security:
  - ACL: app user with ~* +@read +@write -FLUSH* -KEYS
  - No TLS (internal VPC)
  - Command rename: KEYS → ""
  Expose: Direct ACL (no proxy needed)
```

**Scenario 2: Session Store (10K sessions/sec, 99.9% uptime SLA)**

```
Monitoring:
  - Connected clients: alert at 80% maxclients
  - Memory: alert at 75%
  - Replication lag: alert at 500ms
  - Blocked clients: alert at > 0
Security:
  - ACL: app user ~session:* +@read +@write -FLUSH* -KEYS
  - Network isolation: dedicated VPC, no public access
  - No TLS (internal network)
  - Command rename: FLUSHDB, FLUSHALL renamed
Expose: Direct ACL (latency critical)
```

**Scenario 3: Rate Limiting + Distributed Locking (multi-tenant SaaS)**

```
Monitoring:
  - All clients: alert at 60% (multi-tenant, be proactive)
  - Rejected connections: alert at > 0
  - Command latency: alert p99 > 10ms
Security:
  - Per-tenant ACL: tenant:{id}:* pattern
  - TLS: required (cross-service, cloud)
  - Command rename: all dangerous commands disabled
  - Proxy layer: rate limiting, tenant isolation
Expose: Proxy/gateway (multi-tenant isolation required)
```

### Anti-patterns

1. **Monitor average latency, ignore p99**: Average latency là misleading. Nếu p99 = 500ms nhưng average = 5ms, user experience vẫn terrible. Luôn monitor percentiles.
2. **Alert without runbook**: Alert mà không có clear action = noise. Mỗi alert phải có: threshold, root cause, mitigation steps.
3. **No TLS in cloud cross-AZ**: Cross-availability-zone traffic có thể be intercepted. Always use TLS for cross-AZ or cross-cloud communication.
4. **`protected-mode no` without ACL**: Redis exposed without password = security breach waiting to happen. At minimum, use `requirepass` + ACL.
5. **`KEYS` on production**: `KEYS` scans entire keyspace synchronously. On 10M keys → Redis blocked for 10+ seconds. Always use `SCAN` instead.
6. **`maxmemory-policy noeviction` without monitoring**: Writes fail silently when memory is full. Must have eviction monitoring if using noeviction.
7. **`CONFIG` enabled for all users**: `CONFIG` allows runtime changes that bypass your carefully designed deployment. Rename it.
8. **No slowlog threshold set**: If `slowlog-log-slower-than 0`, slowlog is disabled. Set to 10ms for production (capture commands > 10ms).

---

## 7. Performance Considerations

### Monitoring Overhead

```
redis_exporter overhead:
  - CPU: ~0.5-2% of a single core per Redis instance
  - Memory: ~20-50MB per exporter
  - Network: ~1-5MB/day of metrics (at 15s scrape interval)

Prometheus scrape cost:
  - 15s interval: 5760 scrapes/day per target
  - Per scrape: ~100KB (100 metrics, each ~1KB with labels)
  - Daily: ~576MB/day per target

Total infrastructure for 10 Redis instances:
  - redis_exporter: 10 × ~50MB = 500MB RAM
  - Prometheus: ~5-10GB RAM for 90-day retention
  - Network: ~5GB/day metrics

Conclusion: Monitoring overhead is negligible (< 1% of Redis resource cost).
```

### TLS Performance Impact

```
TLS 1.2 handshake cost:
  - Full handshake: ~2-3ms RTT (client → server → client)
  - Redis single-threaded: blocking during TLS handshake

TLS 1.3 improvement:
  - 1-RTT handshake (vs 2-RTT in TLS 1.2)
  - Session resumption: 0-RTT for resumed sessions
  - Expected overhead: 1-2ms instead of 2-3ms

Benchmark (Redis 7.2, TLS 1.3, local network):
  - Without TLS: 100K ops/sec, p99 = 0.8ms
  - With TLS:    95K ops/sec, p99 = 1.2ms
  - Overhead:    ~5% throughput, ~50% p99 latency increase

For high-throughput low-latency: TLS adds measurable but acceptable overhead.
For extreme latency requirements: avoid TLS, use network isolation instead.
```

### Command Latency Distribution

```
Command latency breakdown (p50 / p95 / p99):

GET on warm key:         p50=0.05ms  p95=0.1ms  p99=0.2ms
SET simple value:       p50=0.06ms  p95=0.15ms p99=0.3ms
HSET small hash:        p50=0.08ms  p95=0.2ms  p99=0.5ms
ZADD to sorted set:     p50=0.1ms   p95=0.3ms  p99=0.8ms
LRANGE 100 items:       p50=0.5ms   p95=1.5ms  p99=3.0ms
SMEMBERS (1K set):      p50=1.0ms   p95=5.0ms  p99=12ms
KEYS pattern (1M keys): p50=5000ms   p95=10000ms p99=15000ms ← NEVER use
SCAN 1M keys:           p50=0.1ms   p95=0.5ms  p99=1.0ms  ← use this instead

Big key impact:
  GET 1MB string:        p50=5ms     p95=15ms   p99=30ms
  LRANGE 100K list:     p50=50ms    p95=200ms  p99=500ms
  HGETALL big hash:      p50=30ms    p95=150ms  p99=400ms

Network overhead (remote client):
  Same AZ:  +0.1-0.3ms per RTT
  Cross AZ: +0.5-2.0ms per RTT
  Cross DC: +5-30ms per RTT (avoid for latency-critical)
```

---

## 8. Production Failure Modes

### 8.1. High Latency Spike

```
Symptom: p99 latency tăng từ 5ms lên 500ms+; slowlog có nhiều entries
Cause:
  - Slow command: KEYS, SMEMBERS, LRANGE on large keys
  - Big key: GET/SET on 10MB+ value
  - Fork: BGSAVE or AOF rewrite blocking (copy-on-write)
  - Swap: OS swapping due to memory overcommit
  - Network: NIC saturation, cross-AZ latency spike
  - AOF fsync: appendfsync always causing disk I/O bottleneck
Detection:
  - SLOWLOG GET 10 — xem commands > slowlog-log-slower-than threshold
  - redis-cli --latency-history — measure over time
  - redis-cli --bigkeys — find big keys
  - INFO commandstats — command-level latency
  - dmesg | grep -i swap — check for OOM/swap
Fix:
  1. Find slow command: SLOWLOG GET
  2. If KEYS/FLUSH*: identify culprit via CLIENT LIST + current_command
  3. If big key: SCAN + count items, assess size with MEMORY USAGE
  4. If fork: check last_fork_time in INFO persistence
  5. If AOF fsync: change appendfsync to everysec or no
  6. Scale horizontally if load-based
Prevention:
  - slowlog-log-slower-than: 10 (production)
  - Monitor p99 latency, not just average
  - Alert on slowlog count increase
  - Use SCAN instead of KEYS
  - Enforce max key size in application layer
```

### 8.2. High Memory / Memory Leak

```
Symptom: used_memory tăng liên tục, không giảm sau restarts
Cause:
  - Memory leak in application (keys never deleted)
  - Big keys accumulating (user-generated content)
  - Lua script returning large data without limits
  - `maxmemory` too small, constant eviction
  - Memory fragmentation (jemalloc fragmentation)
  - Process memory overhead: client buffers, AOF buffer, Lua memory
Detection:
  - MEMORY DOCTOR (Redis 4.4+): gives detailed diagnosis
  - MEMORY STATS: break down memory usage
  - MEMORY USAGE key: measure specific key size
  - redis-cli --bigkeys: find large keys
  - INFO memory → mem_fragmentation_ratio, mem_rss, used_memory_peak
Fix:
  1. MEMORY DOCTOR: get diagnosis
  2. Check fragmentation: if > 1.5 → restart Redis
  3. Find large keys: redis-cli --bigkeys (scan entire dataset)
  4. If memory leak: audit application code, add TTLs
  5. If fragmentation: restart Redis (only fix)
  6. If maxmemory too small: increase + scale cluster
Prevention:
  - Set TTL on all keys with natural expiration
  - Monitor used_memory_trend over hours/days
  - Alert at 75% maxmemory
  - Enforce max value size at application layer
```

### 8.3. High CPU on Redis

```
Symptom: CPU 100% on Redis process; commands queuing; latency spike
Cause:
  - Slow commands: O(N) or O(N*log N) commands on large datasets
  - Too many connections: context switching overhead
  - Lua scripts: long-running EVAL scripts blocking event loop
  - Background processes: AOF rewrite, RDB save, COW overhead
  - Big keys: large value serialization/deserialization
Detection:
  - INFO commandstats — identify high-call-volume or high-latency commands
  - SLOWLOG GET — find commands exceeding threshold
  - redis-cli --bigkeys — find large data structures
  - INFO stats → total_commands_processed rate
  - Check if CPU is user or system (top/htop)
Fix:
  1. Identify slow command: INFO commandstats
  2. If EVAL/EVALSHA: check script complexity, add timeout
  3. If LRANGE/SORT/SINTER: refactor to smaller operations
  4. If too many connections: use pipelining, reduce connection count
  5. If AOF/RDB: schedule during low traffic window
Prevention:
  - Avoid O(N) commands on large datasets
  - Use SCAN instead of KEYS/LLEN/SMEMBERS on large sets
  - Limit Lua script complexity with SCRIPT MAX-runtime
  - Monitor CPU per core, alert at 70%
```

### 8.4. Replication Lag Growing

```
Symptom: replica lag tăng, eventually exceeds SLA
Cause:
  - Slow replica: CPU/disk/network constrained
  - Big command: LPUSH with 100K items blocks stream
  - Network bandwidth saturation (replication + client traffic competing)
  - Replica restarts (cold cache)
  - Disk I/O bottleneck (disk-based persistence on replica)
Detection:
  - INFO replication → lag field (bytes)
  - redis_exporter → redis_replication_lag_seconds
  - Alert: replication_lag > 1s for 2 minutes
Fix:
  1. Check replica hardware: CPU, disk I/O, network throughput
  2. Check for big commands: INFO commandstats on replica
  3. If disk I/O: switch to repl-diskless-sync yes
  4. If network: separate replication network from client network
  5. If big command: split into smaller operations
  6. If backlog overflow: increase repl-backlog-size
Prevention:
  - Capacity test before production: peak write rate + measure lag
  - Monitor lag continuously, alert at 50% SLA threshold
  - Separate replication traffic from client traffic (VLAN/network)
```

### 8.5. Failover Issues

```
Symptom: Sentinel/Cluster failover xảy ra nhưng app không redirect đúng
Cause:
  - Client không dùng Sentinel/Cluster-aware client
  - DNS cache stale, clients point to old master
  - `min-replicas-to-write` causing writes to fail during failover
  - Split brain: multiple replicas think they're master
Detection:
  - Check Sentinel logs: +sdown, +odown, +switch-master events
  - Check Redis logs: +promoted-slave, +fix-slave-configuration
  - Check client logs: connection refused, MOVED errors
  - redis-cli -h master-ip INFO server → role field
Fix:
  1. Verify new master: redis-cli INFO replication → role:master
  2. Verify app clients: check they resolved new master address
  3. If DNS stale: reduce DNS TTL to < 30s
  4. If client not redirected: update client SDK, redeploy
  5. If min-replicas-to-write: temporarily set to 0 during failover
Prevention:
  - Use Sentinel/Cluster-aware client libraries
  - Short DNS TTL for Redis service discovery
  - Test failover regularly (chaos testing)
  - Monitor failover events, alert on any failover
```

### 8.6. Connection Explosion

```
Symptom: connected_clients = maxclients; new connections rejected; rejected_connections_total > 0
Cause:
  - Connection leak: clients open connections but don't close
  - Too many clients: connection pool misconfigured
  - Redis Cluster redirects: MOVED/ASK causing extra connections
  - PING timeout too long: slow clients hold connections
  - Slowloris attack: clients send partial requests slowly
Detection:
  - INFO clients → connected_clients, blocked_clients, rejected_connections
  - CLIENT LIST → identify clients by addr, cmd, idle time
  - Alert: connected_clients > 80% maxclients
Fix:
  1. Find idle/leaked connections: CLIENT LIST | grep "idle=[0-9]+"
  2. Kill leaked connections: CLIENT KILL ID <id>
  3. If maxclients too low: increase maxclients (in redis.conf)
  4. If connection pool issue: audit pool configuration
  5. Check client timeout: client-output-buffer-limit settings
Prevention:
  - Connection pooling on client side (mandatory)
  - Set reasonable client timeout: 10-30s
  - Monitor connection count trend
  - Set client-output-buffer-limit for pubsub/slave
```

### 8.7. Slow Command (KEYS, SMEMBERS, etc.)

```
Symptom: p99 latency spike, slowlog full of same command type
Cause:
  - Developer runs KEYS in production (O(N), blocking)
  - SMEMBERS on set with 1M members
  - LRANGE on list with 100K items
  - HGETALL on hash with 10K fields
Detection:
  - SLOWLOG GET → show commands exceeding threshold
  - INFO commandstats → high usec_per_call for specific command
  - CLIENT LIST → identify which client is running slow command
Fix:
  1. Find culprit: SLOWLOG GET + CLIENT LIST
  2. Kill if necessary: CLIENT KILL ADDRESS <ip>
  3. Identify slow command type
  4. Refactor:
     KEYS → SCAN + pattern matching in application
     SMEMBERS → SSCAN
     LRANGE → paginated with cursor
     HGETALL → HSCAN
Prevention:
  - slowlog-log-slower-than: 10 (capture > 10ms)
  - Alert on slowlog growth rate
  - Rename/disable KEYS in redis.conf
  - Code review: ban KEYS/SORT/SMEMBERS in production
```

### 8.8. Unexpected Key Eviction

```
Symptom: evicted_keys counter tăng; users lose cached data unexpectedly
Cause:
  - maxmemory too small for workload
  - maxmemory-policy changed (from allkeys-lru to allkeys-random)
  - TTL not set; keys live forever; fill up memory
  - Application creates keys without TTL; hits maxmemory
Detection:
  - INFO stats → evicted_keys_total
  - redis_exporter → redis_evicted_keys_total (rate per minute)
  - Alert: evicted_keys_rate > 100/min for 2 minutes
Fix:
  1. Check eviction policy: INFO memory → maxmemory_policy
  2. Check maxmemory: INFO memory → maxmemory
  3. Find keys without TTL: SCAN + TTL check
  4. If maxmemory too small: increase
  5. If TTL missing: audit application, add TTL
  6. If wrong policy: change based on use case
Prevention:
  - Monitor evicted_keys counter (not just memory usage)
  - Alert at first sign of eviction (eviction = degradation)
  - Set maxmemory with 10-20% headroom
  - Use volatile-* eviction policy if some keys should persist
  - Enforce TTL in application code
```

---

## 9. Real-world Examples

### GitHub — Redis Monitoring at Scale

GitHub chạy hàng trăm Redis instances với Prometheus + Grafana. Monitoring stack:
- redis_exporter scrape tất cả instances
- Recording rules cho p95/p99 latency per command type
- Evicted keys alert: notify team before users affected
- Key insight: average latency không phản ánh user experience — p99 là what matters

GitHub đã public blog về cách họ dùng Redis cho distributed locking và rate limiting, với monitoring dashboards cho mỗi use case.

### Twitter/X — Redis Latency Monitoring

Twitter/X monitor Redis command latency với sub-millisecond granularity. Key lesson: **p50 latency không quan trọng, p99/p99.9 mới là what causes user-visible degradation**.

Twitter dùng Redis cho timeline cache với strict latency budget: requests phải complete trong 10ms. Khi p99 vượt budget, team trigger automatic scaling.

### Shopify — Security Incident (No ACL)

Shopify incident: một developer accidentally expose Redis port publicly. Security team phát hiện trong 5 phút qua connection monitoring (rejected_connections counter spike từ external IPs). Lesson: **connection monitoring + ACL = defense in depth**.

Shopify giờ dùng ACL for all Redis access, even internal. Zero public exposure.

### Stack Overflow — Slowlog as Incident Detection

Stack Overflow (vận hành Stack Exchange network) dùng slowlog như primary debugging tool. Mỗi production incident đều bắt đầu với SLOWLOG analysis. Key lesson: **set slowlog-log-slower-than to a value that gives you ~10 slow commands per minute** — enough to detect issues, not so many to cause noise.

### Uber — Connection Pool Exhaustion

Uber gặp incident khi connection pool misconfiguration gây ra connection leak. Redis `connected_clients` tăng đến maxclients → writes rejected. Root cause: application không handle Redis connection errors properly → connections không returned to pool. Fix: connection pool with proper error handling + monitoring.

---

## 10. Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Monitor only average latency | p99 spike undetected until user complaints | Monitor histogram percentiles, not just averages |
| No eviction monitoring | silent data loss, users logged out | Alert on evicted_keys rate |
| TLS everywhere even internal | +2-3ms latency for no reason | TLS only for external/cross-AZ traffic |
| No ACL (or `requirepass` only) | Single password for all apps | Named users with fine-grained permissions |
| `KEYS` in production | Redis blocked 10s+ | Disable KEYS, use SCAN |
| Alert without runbook | Alert fatigue, ignored alerts | Every alert must have action steps |
| `CONFIG` accessible to app | Runtime misconfiguration possible | Rename CONFIG, restrict to admin |
| `maxmemory-policy noeviction` without monitoring | Writes silently fail when full | Monitor memory, alert before eviction |
| No TLS on cross-datacenter replication | Traffic can be intercepted | TLS replication for cross-DC |
| Slowlog disabled | Can't identify slow commands | Set slowlog-log-slower-than 10ms |
| Connection monitoring missing | Can't detect connection leak/explosion | Alert at 80% maxclients |
| Fragmentation ratio ignored | Memory appears full, but RSS much higher | Monitor fragmentation, restart at > 1.5 |

---

## 11. Câu hỏi tự kiểm tra

### Câu 1: Monitoring Threshold

Bạn có Redis với `maxmemory = 8GB`. SLA yêu cầu eviction rate < 100 keys/minute. Đặt alert thresholds cho memory usage và evicted keys. Giải thích tại sao dùng multi-level alerts.

> **Đáp án**:
>
> Memory usage thresholds:
> - Warning: > 70% (5.6GB) sustained 5 min — early warning
> - Critical: > 85% (6.8GB) sustained 2 min — action required
> - Eviction imminent: > 90% (7.2GB) sustained 1 min — emergency
>
> Evicted keys thresholds:
> - Warning: > 10 keys/min sustained 2 min — investigate
> - Critical: > 50 keys/min sustained 2 min — action required
> - SLA breach: > 100 keys/min — immediate response
>
> Multi-level alerts prevent both false positives (too sensitive) and missed incidents (too loose). Memory at 70% gives 30% headroom for investigation before hitting critical at 85%.

### Câu 2: TLS vs No TLS Decision

E-commerce platform trong AWS, 3-tier architecture (web → API → Redis in private VPC). Giải thích khi nào dùng TLS, khi nào không. Nêu latency impact cụ thể.

> **Đáp án**:
>
> **Internal Redis (same VPC)**: No TLS.
> - Redis và API cùng private VPC, không có external exposure
> - TLS handshake overhead: +1-3ms per connection
> - For 100K ops/sec: TLS adds ~5% throughput overhead, ~50% p99 latency increase
> - Mitigation: Use ACL + network security groups instead
>
> **Cross-AZ or cross-region**: TLS required.
> - Traffic traverses availability zone boundaries
> - Internal AWS traffic có thể be intercepted at network level
> - TLS 1.3 với session resumption: reduces handshake overhead
> - Accept +1-3ms overhead for security
>
> **External access**: TLS mandatory (non-negotiable).
> - No TLS = all traffic in plaintext
>
> Best practice: TLS for external/cross-AZ, ACL + network isolation for internal.

### Câu 3: ACL Design

Design ACL cho 3-tier application: app server (read/write), analytics service (read-only), monitoring agent (info only). Không ai được dùng FLUSH*, KEYS, hoặc DEBUG.

> **Đáp án**:
>
> ```txt
> # App server: full read/write but restricted
> ACL SETUSER app on >app_hash ~app:* +@read +@write -@dangerous -FLUSH* -KEYS -DEBUG -CONFIG
>
> # Analytics: read-only, can scan large datasets
> ACL SETUSER analytics on >analytics_hash ~analytics:* +@read +scan +slowlog|get +command +dbsize -FLUSH* -KEYS -DEBUG
>
> # Monitoring: minimal permissions (info + ping only)
> ACL SETUSER monitoring on >mon_hash ~* +ping +info +dbsize +memory|stats +slowlog|get +command +client|list +config|get -@dangerous -FLUSH* -KEYS -DEBUG
>
> # Admin (emergency use only)
> ACL SETUSER admin on >admin_hash ~* +@all -@dangerous
> ```
>
> Key principles:
> - Least privilege: each user only what it needs
> - Deny by default: -@all first, then + only needed commands
> - Dangerous commands: always restrict
> - Pattern: use key pattern matching (~) for multi-tenant isolation

### Câu 4: Slow Command Troubleshooting

`SLOWLOG GET 10` cho thấy 5 lệnh `SMEMBERS` mỗi lần chạy 2000-5000ms. Hệ thống có 50 triệu users, mỗi user có một SET chứa list of followed users (avg 500 users/set). Explaining root cause và solution.

> **Đáp án**:
>
> **Root cause**: `SMEMBERS` on a SET returns all members in O(N) time, where N = number of set members. With avg 500 members per set, each SMEMBERS = ~500 operations. At 50M keys with active users, some sets have 10K+ members → very slow.
>
> **Why it was slow**:
> - `SMEMBERS` has O(N) complexity where N = cardinality of set
> - Redis single-threaded: 5000ms SMEMBERS blocks ALL other commands for 5 seconds
> - Result: 5 slow SMEMBERS × 5s = 25 seconds of blocked processing
>
> **Solutions**:
> 1. **Use SSCAN instead of SMEMBERS**: paginated iteration, non-blocking
> 2. **Cache SMEMBERS result**: TTL short (30-60s), recompute on miss
> 3. **Denormalize**: store following list as a separate hash with TTL
> 4. **Redis 7+ Stream**: use consumer group if data grows indefinitely
> 5. **Code fix**: replace SMEMBERS with pagination + background refresh
>
> **Immediate fix**: Rename SMEMBERS (`rename-command SMEMBERS ""`) → force developers to use SSCAN. Alert team to fix code.

### Câu 5: Connection Explosion

`INFO clients` cho thấy `connected_clients = 9999` (maxclients = 10000). `rejected_connections = 1234`. Giải thích nguyên nhân và fix.

> **Đáp án**:
>
> **Causes**:
> 1. Connection leak: app opens connections but never closes (no connection pooling)
> 2. Client timeout too long: slow clients hold connections for minutes
> 3. Application bug: exceptions prevent connection return to pool
> 4. Too many app instances: each instance opens connections without pooling
> 5. Client output buffer full: server can't write → connection held open
>
> **Immediate fix**:
> ```bash
> # Find idle connections
> redis-cli CLIENT LIST | grep "idle=[0-9]" | head -20
> # Kill specific idle connections
> redis-cli CLIENT KILL ID <id>
> # Emergency: flush all idle connections (may disrupt app)
> redis-cli CLIENT KILL TYPE normal IDLE-TIME 300
> ```
>
> **Long-term fix**:
> 1. Implement connection pooling in application
> 2. Set client timeout: `timeout 30` (Redis side) + client-side timeout
> 3. Increase maxclients: `maxclients 20000` (but fix root cause first)
> 4. Set output buffer limits:
>    ```
>    client-output-buffer-limit normal 32mb 8mb 60
>    client-output-buffer-limit replica 128mb 64mb 60
>    client-output-buffer-limit pubsub 32mb 8mb 60
>    ```
> 5. Monitor: alert at 80% of maxclients

### Câu 6: Trade-off Analysis

So sánh detailed monitoring (redis_exporter + Prometheus + Grafana) vs minimal monitoring (redis-cli INFO cron job). Trong scenario nào mỗi approach phù hợp?

> **Đáp án**:
>
> | Aspect | Minimal (INFO cron) | Detailed (Full Stack) |
> |---|---|---|
> | Cost | Low (cron + shell script) | Higher (3+ components) |
> | Latency overhead | ~0ms | redis_exporter ~2-5% CPU |
> | Storage | None (just log) | Prometheus: 5-10GB for 90 days |
> | p99 latency detection | Not possible | Histogram buckets capture it |
> | Alerting | Threshold-based | Multi-dimensional, %ile-based |
> | Debug capability | Limited | Full observability |
>
> **Minimal appropriate**: Dev/test, single Redis instance, prototype.
>
> **Detailed required**: Production với SLA, multiple Redis instances, any system with user-facing SLAs.
>
> **Key insight**: Monitoring overhead (~2% CPU) là rất nhỏ so với cost của một incident không detected. Production = detailed monitoring, always.

### Câu 7: Security Hardening Runbook

Nêu 5 bước bảo mật đầu tiên để harden Redis production (theo thứ tự ưu tiên).

> **Đáp án**:
>
> **Bước 1 — ACL: Named users, no default access**:
> ```txt
> ACL SETUSER default off   # disable default user
> ACL SETUSER app on >hash ~app:* +@read +@write -@dangerous
> ```
>
> **Bước 2 — Network isolation: Bind only internal interface**:
> ```
> bind 10.0.1.10 127.0.0.1
> protected-mode yes
> ```
>
> **Bước 3 — Disable/rename dangerous commands**:
> ```txt
> rename-command FLUSHDB "FLUSHDB_secret123"
> rename-command FLUSHALL ""
> rename-command KEYS ""
> rename-command DEBUG ""
> rename-command SHUTDOWN ""
> ```
>
> **Bước 4 — TLS for cross-AZ/cross-cloud** (if applicable):
> ```
> tls-port 6380
> tls-cert-file /etc/redis/tls/server.crt
> tls-key-file /etc/redis/tls/server.key
> tls-cert-verify-clients required
> ```
>
> **Bước 5 — Connection limits + monitoring**:
> ```
> maxclients 10000
> client-output-buffer-limit normal 32mb 8mb 60
> slowlog-log-slower-than 10
> ```
>
> Priority: ACL → Network isolation → Command disable → TLS → Connection limits. Ngược lại: nếu không có ACL, attacker có thể bypass tất cả.
