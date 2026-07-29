# Day 29: Observability, Security & Troubleshooting — Exercises

**Thời lượng**: ~2 giờ
**Ngôn ngữ**: Go (luân phiên với Day 28)
**Redis**: 7.2+

---

## 0. Setup

```bash
# Verify Docker and docker-compose
docker --version
docker compose version

# Create working directory
mkdir -p day29-observability && cd day29-observability

# Copy docker-compose from document.md
# Start the full stack (Redis + Exporter + Prometheus + Grafana)
docker compose up -d

# Wait for services to be ready
sleep 10

# Verify Redis is up
redis-cli -h localhost -p 6379 -a redispass123 PING
# Expected: PONG

# Verify Redis Exporter is up
curl -s http://localhost:9121/metrics | head -20
# Expected: Prometheus format metrics

# Verify Prometheus is up
curl -s http://localhost:9090/-/healthy
# Expected: Prometheus is Healthy.

# Verify Grafana is up
curl -s http://localhost:3000/api/health
# Expected: {"database":"ok"}

# Access Grafana: http://localhost:3000
# Default: admin / admin123
```

---

## 1. Warm-up Exercises (15-20 phút)

### 1.1. Exploring INFO Sections

```bash
# Explore all INFO sections
redis-cli -h localhost -p 6379 -a redispass123 INFO server
redis-cli -h localhost -p 6379 -a redispass123 INFO memory
redis-cli -h localhost -p 6379 -a redispass123 INFO clients
redis-cli -h localhost -p 6379 -a redispass123 INFO stats
redis-cli -h localhost -p 6379 -a redispass123 INFO replication
redis-cli -h localhost -p 6379 -a redispass123 INFO commandstats

# Calculate hit rate from INFO stats
redis-cli -h localhost -p 6379 -a redispass123 INFO stats | grep keyspace
# Expected:
# keyspace_hits:XXX
# keyspace_misses:XXX
# Formula: hit_rate = hits / (hits + misses) * 100
```

### 1.2. SLOWLOG — Capturing and Analyzing Slow Commands

```bash
# Set slowlog threshold to 1ms (1000 microseconds) for testing
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET slowlog-log-slower-than 1000

# Generate some data
for i in $(seq 1 100); do
  redis-cli -h localhost -p 6379 -a redispass123 SET "warm:key:$i" "value$i"
done

# Run a slow command (DEBUG SLEEP simulates latency)
redis-cli -h localhost -p 6379 -a redispass123 DEBUG SLEEP 0.5
# Expected: OK (after 500ms)

# Check slowlog
redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG GET 10
# Expected output:
#  1) (integer) 1           ← entry ID
#     (integer) 1716200000   ← unix timestamp
#     (integer) 500123       ← duration in microseconds (500ms)
#     2) "DEBUG" "SLEEP" "0.5"
#     (integer) 0             ← client IP
#     (integer) 0             ← client name

# Count slowlog entries
redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG LEN
# Expected: 1 (or more if KEYS commands triggered)

# Reset slowlog
redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG RESET
redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG LEN
# Expected: 0

# Restore to production value (10ms = 10000 microseconds)
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET slowlog-log-slower-than 10000
```

### 1.3. MEMORY Commands

```bash
# Fill some data
redis-cli -h localhost -p 6379 -a redispass123 SET "mem:test:string" "hello-world"

# Check memory usage for specific key
redis-cli -h localhost -p 6379 -a redispass123 MEMORY USAGE "mem:test:string"
# Expected: ~80-120 bytes (includes key overhead + value)

# Create a hash and check its memory
redis-cli -h localhost -p 6379 -a redispass123 HSET "mem:test:hash" field1 value1 field2 value2
redis-cli -h localhost -p 6379 -a redispass123 MEMORY USAGE "mem:test:hash"
# Expected: hash memory footprint

# Run MEMORY DOCTOR
redis-cli -h localhost -p 6379 -a redispass123 MEMORY DOCTOR
# Expected: Detailed memory advice
```

### 1.4. CLIENT LIST — Identifying Connections

```bash
# List all clients
redis-cli -h localhost -p 6379 -a redispass123 CLIENT LIST
# Expected: each client on its own line, fields separated by spaces
# Fields: id,addr,port,fd,laddr,pgid,age,idle,flags,db,sub,multi,cmd,lib

# Count connected clients
redis-cli -h localhost -p 6379 -a redispass123 CLIENT LIST | wc -l
# Expected: varies (includes replicas, redis-cli sessions)

# Check replica connection
redis-cli -h localhost -p 6379 -a redispass123 CLIENT LIST | grep "replica"
# Expected: shows replica connection with flags=Sl

# Check blocked clients
redis-cli -h localhost -p 6379 -a redispass123 INFO clients | grep blocked
# Expected: blocked_clients:0 (or > 0 if something is blocking)
```

### 1.5. ACL — Creating and Testing Users

```bash
# Create a read-only user
redis-cli -h localhost -p 6379 -a redispass123 ACL SETUSER readonlyuser on >readonly123 ~* resetcommands +@read
# Expected: OK

# Create a read-write user for specific keys
redis-cli -h localhost -p 6379 -a redispass123 ACL SETUSER appuser on >apppass123 ~app:* +@read +@write -@dangerous -FLUSH* -KEYS -DEBUG
# Expected: OK

# List all users
redis-cli -h localhost -p 6379 -a redispass123 ACL LIST
# Expected: list of users with their rules

# Test readonlyuser permissions
redis-cli -h localhost -p 6379 -a readonly123 --user readonlyuser GET "warm:key:1"
# Expected: value1 (read works)

redis-cli -h localhost -p 6379 -a readonly123 --user readonlyuser SET "warm:key:1" "newvalue"
# Expected: NOPERM (write not allowed)

# Test appuser permissions
redis-cli -h localhost -p 6379 -a apppass123 --user appuser SET "app:test" "hello"
# Expected: OK

redis-cli -h localhost -p 6379 -a apppass123 --user appuser GET "app:test"
# Expected: hello

redis-cli -h localhost -p 6379 -a apppass123 --user appuser FLUSHDB
# Expected: NOPERM (FLUSHDB not allowed)

# Cleanup
redis-cli -h localhost -p 6379 -a redispass123 ACL DELUSER readonlyuser appuser
```

### 1.6. Prometheus Metrics via redis_exporter

```bash
# Query redis_exporter metrics directly
curl -s http://localhost:9121/metrics | grep "^redis_" | head -30
# Expected: redis_memory_used_bytes, redis_connected_clients, redis_commands_processed_total, etc.

# Query specific metrics
curl -s http://localhost:9121/metrics | grep "redis_memory_used_bytes"
curl -s http://localhost:9121/metrics | grep "redis_connected_clients"
curl -s http://localhost:9121/metrics | grep "redis_keyspace"

# Verify in Prometheus
curl -s "http://localhost:9090/api/v1/query?query=redis_memory_used_bytes"
# Expected: JSON with metrics

# Cleanup warm-up keys
redis-cli -h localhost -p 6379 -a redispass123 KEYS "warm:*" | xargs -r redis-cli -h localhost -p 6379 -a redispass123 DEL
redis-cli -h localhost -p 6379 -a redispass123 DEL "mem:test:string" "mem:test:hash" "app:test"
```

---

## 2. Hands-on Lab: Observability Stack + Troubleshooting Simulation (60-70 phút)

**Scenario**: Bạn vừa join team vận hành Redis production. Hệ thống có vấn đề nhưng chưa rõ nguyên nhân. Bạn cần:
1. Navigate Grafana dashboard và identify anomalies
2. Setup alert rules
3. Simulate high latency scenario
4. Simulate memory pressure
5. Write a troubleshooting runbook

### 2.1. Load Test Data

```bash
# Generate realistic dataset (1000 keys)
for i in $(seq 1 1000); do
  redis-cli -h localhost -p 6379 -a redispass123 SET "product:$i" "Product-$i-data"
done

# Generate some session data
for i in $(seq 1 500); do
  redis-cli -h localhost -p 6379 -a redispass123 HSET "session:$i" user_id "$i" status "active" last_seen "$(date +%s)"
done

# Verify
redis-cli -h localhost -p 6379 -a redispass123 DBSIZE
# Expected: (integer) 1500 (or close)
```

### 2.2. Access and Explore Grafana

```bash
# Grafana is available at http://localhost:3000
# Login: admin / admin123

# Import Redis dashboard:
# 1. Click "+" → Import
# 2. Enter dashboard ID: 11835
# 3. Select Prometheus datasource
# 4. Click Import

# Or use the pre-built dashboard via datasource provisioning
# Already provisioned in docker-compose.yml
```

### 2.3. Simulate High Latency Scenario

**Goal**: Simulate slow command causing p99 latency spike. Observe how Grafana and Prometheus capture this.

```bash
# Terminal 1: Monitor SLOWLOG continuously
watch 'redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG GET 5'

# Terminal 2: Generate load
for i in $(seq 1 50); do
  redis-cli -h localhost -p 6379 -a redispass123 GET "product:$((RANDOM % 1000 + 1))"
done

# Terminal 3: Simulate slow commands
# Set slowlog threshold very low for demonstration
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET slowlog-log-slower-than 1000

# Simulate 500ms latency
redis-cli -h localhost -p 6379 -a redispass123 DEBUG SLEEP 0.5
redis-cli -h localhost -p 6379 -a redispass123 DEBUG SLEEP 0.3
redis-cli -h localhost -p 6379 -a redispass123 DEBUG SLEEP 0.7

# Restore threshold
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET slowlog-log-slower-than 10000

# Check slowlog now
redis-cli -h localhost -p 6379 -a redispass123 SLOWLOG GET 10
```

**Observation points**:
- SLOWLOG entries show exact command, duration, timestamp
- `SLOWLOG` và `LATENCY DOCTOR` capture latency spike; p95/p99 dashboard cần client-side histogram metric, vì `redis_exporter` chỉ expose aggregate commandstats.
- Grafana dashboard shows latency spike
- Which commands caused the spike?

### 2.4. Simulate Memory Pressure

```bash
# Step 1: Check current memory
redis-cli -h localhost -p 6379 -a redispass123 INFO memory | grep -E "used_memory|maxmemory|evicted"

# Step 2: Set maxmemory to a small value
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxmemory 50mb
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxmemory-policy allkeys-lru

# Step 3: Check eviction
redis-cli -h localhost -p 6379 -a redispass123 INFO memory | grep evicted
# Expected: evicted_keys:0

# Step 4: Write more data than fits in 50MB
# This should trigger eviction
for i in $(seq 1 10000); do
  redis-cli -h localhost -p 6379 -a redispass123 SET "evict:test:$i" "$(head -c 5000 /dev/urandom | base64)"
done

# Step 5: Check eviction count
redis-cli -h localhost -p 6379 -a redispass123 INFO memory | grep -E "evicted_keys|maxmemory"
# Expected: evicted_keys increased significantly

# Step 6: Check which keys were evicted (SLOWLOG won't show this)
redis-cli -h localhost -p 6379 -a redispass123 GET "product:500"  # May be gone
redis-cli -h localhost -p 6379 -a redispass123 DBSIZE

# Restore to 256MB
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxmemory 256mb
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxmemory-policy allkeys-lru

# Step 7: Clear test data
redis-cli -h localhost -p 6379 -a redispass123 KEYS "evict:*" | xargs -r redis-cli -h localhost -p 6379 -a redispass123 DEL
redis-cli -h localhost -p 6379 -a redispass123 KEYS "product:*" | xargs -r redis-cli -h localhost -p 6379 -a redispass123 DEL
redis-cli -h localhost -p 6379 -a redispass123 KEYS "session:*" | xargs -r redis-cli -h localhost -p 6379 -a redispass123 DEL
```

### 2.5. Simulate Connection Explosion

```bash
# Check current connections
redis-cli -h localhost -p 6379 -a redispass123 INFO clients
# Expected: connected_clients: 2-3 (redis-cli + replica)

# Set maxclients to a very low value for demonstration
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxclients 20

# Open many connections from multiple processes
# (This simulates what happens when maxclients is reached)
for i in $(seq 1 15); do
  redis-cli -h localhost -p 6379 -a redispass123 PING &
done
wait

# Check rejected connections
redis-cli -h localhost -p 6379 -a redispass123 INFO stats | grep rejected
# Expected: rejected_connections:0 if within limit, > 0 if exceeded

# Restore
redis-cli -h localhost -p 6379 -a redispass123 CONFIG SET maxclients 10000

# Kill all hanging connections
redis-cli -h localhost -p 6379 -a redispass123 CLIENT KILL TYPE normal IDLE-TIME 60
```

### 2.6. Write a Troubleshooting Runbook

**Create a runbook file** `runbook.md`:

```markdown
# Redis Production Troubleshooting Runbook

## Incident: High Latency Spike

### Symptoms
- p99 latency > 200ms
- SLOWLOG filling with commands > 10ms
- User complaints: "site is slow"

### Step 1: Identify the Scope
- [ ] Check if latency affects all commands or specific commands
- [ ] Check if latency is on master or replicas
- [ ] Check if latency is consistent or intermittent

### Step 2: Check SLOWLOG
```bash
redis-cli -a $PASS SLOWLOG GET 20
```
- [ ] Identify slow command type
- [ ] Note duration and frequency
- [ ] Identify client IP causing slow commands

### Step 3: Check Command Stats
```bash
redis-cli -a $PASS INFO commandstats | sort -t= -k3 -rn | head -20
```
- [ ] Identify highest usec_per_call commands
- [ ] Check for O(N) commands: KEYS, SMEMBERS, HGETALL, LRANGE

### Step 4: Check System Resources
- [ ] CPU: is Redis using 100% CPU?
- [ ] Memory: is Redis swapping?
- [ ] Disk: is AOF/RDB causing I/O wait?
```bash
top -p $(pgrep redis-server)
dmesg | grep -i oom
dmesg | grep -i swap
```

### Step 5: Check for Big Keys
```bash
redis-cli -a $PASS --bigkeys
redis-cli -a $PASS DEBUG OBJECT ENCODING <big-key>
```

### Step 6: Mitigation
- [ ] If KEYS/SLOW command: kill client via `CLIENT KILL ADDR <ip>`
- [ ] If big key: plan key split during next maintenance window
- [ ] If fork overhead: schedule RDB/AOF during low traffic
- [ ] If memory: consider scaling or eviction policy review

### Step 7: Post-Incident
- [ ] Document slow command type and frequency
- [ ] Add alert rule for this command type
- [ ] Schedule fix (code change, key redesign, or config change)
- [ ] Update runbook if new failure mode discovered

## Incident: Memory Pressure / Eviction

### Symptoms
- evicted_keys counter increasing
- used_memory approaching maxmemory
- Users losing cached data

### Step 1: Assess Severity
```bash
redis-cli -a $PASS INFO memory | grep -E "used_memory|maxmemory|evicted"
```
- [ ] evicted_keys rate: < 100/min = warning, > 100/min = critical
- [ ] used_memory / maxmemory: > 80% = warning, > 90% = critical

### Step 2: Find Keys Without TTL
```bash
redis-cli -a $PASS --scan | head -1000 | while read key; do
  ttl=$(redis-cli -a $PASS TTL "$key")
  if [ "$ttl" -eq -1 ]; then
    echo "NO TTL: $key"
  fi
done
```

### Step 3: Find Large Keys
```bash
redis-cli -a $PASS --bigkeys
redis-cli -a $PASS MEMORY STATS
```

### Step 4: Mitigation
- [ ] Increase maxmemory (if hardware available)
- [ ] Change eviction policy if inappropriate
- [ ] Add TTL to keys (application fix)
- [ ] Scale horizontally (add cluster nodes)

### Step 5: Post-Incident
- [ ] Audit all keys for TTL coverage
- [ ] Set maxmemory with headroom (80% of available RAM)
- [ ] Add eviction rate alert
```

---

## 3. Challenge Exercise (30-40 phút)

### Challenge: Design a Production Monitoring & Alerting System

**Scenario**: E-commerce platform cần thiết kế monitoring system cho Redis cluster gồm:
- 1 master + 2 replicas
- Dataset: 50GB
- Peak ops/sec: 80,000
- SLA: p99 latency < 100ms, uptime > 99.9%

**Tasks**:

A) **Design alert thresholds** (with rationale):

| Metric | Warning Threshold | Critical Threshold | Rationale |
|---|---|---|---|
| Memory usage | ? | ? | ... |
| p99 latency | ? | ? | ... |
| Replication lag | ? | ? | ... |
| Evicted keys rate | ? | ? | ... |
| Connected clients | ? | ? | ... |
| Slowlog entries | ? | ? | ... |
| Fragmentation ratio | ? | ? | ... |

B) **Write 3 Prometheus alert rules** in YAML:
   - Memory above 85%
   - p99 latency above 100ms
   - Replication lag above 5 seconds
   Each rule must include: alert name, expr, for duration, labels, annotations.

C) **Design ACL for 3 users**:
   - `app_user`: read/write on `app:*` keys, no dangerous commands
   - `analytics_user`: read-only on `analytics:*` and `product:*` keys
   - `monitoring_user`: info-only, no key access

D) **Design incident response** cho scenario: Bạn nhận alert "RedisReplicationLagCritical". Mô tả step-by-step response flow, từ alert nhận đến resolution.

---

## 4. Reflection Questions (Open-ended)

1. **Monitoring overhead**: Bạn có 100 Redis instances. Mỗi instance có redis_exporter. Tính toán: Prometheus storage cần bao nhiêu cho 90 ngày retention? redis_exporter overhead trên 100 instances là bao nhiêu? Khi nào monitoring overhead trở thành bottleneck?

2. **TLS vs Latency**: Ứng dụng của bạn có p99 latency budget = 50ms. Redis ops local network latency = 0.5ms. Nếu enable TLS với overhead +1ms per operation, p99 latency sẽ tăng bao nhiêu? Bạn có nên dùng TLS không? Tại sao?

3. **ACL complexity vs security**: Bạn có 50 microservices, mỗi service cần quyền trên Redis. Bạn sẽ design ACL như thế nào? Mỗi service một user hay chia nhóm? Trade-off giữa fine-grained ACL và operational complexity là gì?

4. **Alert fatigue**: Team của bạn có 200 alerts/ngày. 95% là false positives hoặc non-actionable. Làm thế nào để giảm alert noise mà vẫn không miss critical incidents? Nêu ít nhất 3 concrete strategies.

5. **Security vs convenience**: Redis của bạn có `rename-command KEYS ""` (disabled). Developer phàn nàn rằng họ cần KEYS để debug trong staging. Bạn sẽ giải quyết conflict này như thế nào? Trade-off giữa security và developer productivity là gì?

---

## 5. Solution Guide

> **WARNING: Spoiler** - Đọc sau khi đã thử giải quyết bài tập.

---

### Warm-up Solutions

**1.2 SLOWLOG**:
```
SLOWLOG GET 10 output interpretation:
  - [0] = entry ID (sequential)
  - [1] = unix timestamp (seconds)
  - [2] = duration in microseconds (500123 = 500.123ms)
  - [3] = command + arguments
  - [4] = client IP (or 0)
  - [5] = client name (or 0)
```

**1.5 ACL permissions**:
```
ACL pattern breakdown:
  on              → user is enabled
  >password       → password is required
  ~pattern        → key pattern this user can access
  +@category     → allow command category
  -@category      → deny command category
  +command        → allow specific command
  -command        → deny specific command

Key points:
  - -@all first, then + only needed
  - Pattern matching: ~* = all keys, ~app:* = only app:*
  - Categories: @read, @write, @admin, @dangerous, @slow
```

---

### Challenge Solutions

**A) Alert Thresholds**:

| Metric | Warning | Critical | Rationale |
|---|---|---|---|
| Memory usage | > 75% | > 90% | 75% = 15% headroom for investigation; 90% = eviction imminent |
| p99 latency | > 50ms | > 100ms | 50ms = SLA budget - local ops (50ms); 100ms = SLA breach |
| Replication lag | > 1s | > 5s | 1s = early warning; 5s = user-visible stale data |
| Evicted keys rate | > 10/min | > 100/min | 10/min = starting to pressure; 100/min = users losing data |
| Connected clients | > 70% | > 90% | 70% = investigate; 90% = near maxclients |
| Slowlog entries | > 20/5min | > 100/5min | 20 = some commands slow; 100 = systematic issue |
| Fragmentation ratio | > 1.5 | > 2.0 | 1.5 = warning to plan restart; 2.0 = critical restart now |

**B) Prometheus Alert Rules**:

```yaml
# Memory alert
- alert: RedisMemoryCritical
  expr: (redis_memory_used_bytes / redis_memory_max_bytes) > 0.90
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Redis memory above 90%"
    description: "{{ $labels.instance }} is at {{ $value | humanizePercentage }}. Eviction imminent."

# p99 latency alert
- alert: RedisLatencyP99Critical
  expr: histogram_quantile(0.99,
    sum(rate(redis_client_command_duration_seconds_bucket[5m])) by (le, instance)
  ) > 0.1
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Redis p99 latency exceeds 100ms"
    description: "{{ $labels.instance }} p99 latency is {{ $value }}s"

# Replication lag alert
- alert: RedisReplicationLagCritical
  expr: redis_replication_lag_seconds > 5
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Redis replication lag exceeds 5 seconds"
    description: "{{ $labels.instance }} is {{ $value }}s behind master"
```

**C) ACL Design**:

```txt
# App user: read/write on app:*, session:*, rate:*
ACL SETUSER app_user on >app_user_hash \
  ~app:* ~session:* ~rate:* \
  +@read +@write \
  -@dangerous \
  -FLUSH* -KEYS -DEBUG -CONFIG -SHUTDOWN -SAVE -BGSAVE -BGREWRITEAOF

# Analytics user: read-only on analytics:*, product:*
ACL SETUSER analytics_user on >analytics_hash \
  ~analytics:* ~product:* \
  +@read +scan +dbsize +memory|usage +slowlog|get +command \
  -KEYS -DEBUG -FLUSH* -CONFIG -SHUTDOWN

# Monitoring user: info only, no key access
ACL SETUSER monitoring_user on >monitor_hash \
  ~* \
  +ping +info +dbsize +memory|stats +slowlog|get +command +config|get +client|list \
  -@write -@dangerous -FLUSH* -KEYS -DEBUG -SHUTDOWN -SAVE
```

**D) Incident Response Flow** (Replication Lag Alert):

```
1. Alert fires: "RedisReplicationLagCritical" on PagerDuty/Slack
2. Acknowledge alert within 5 minutes (SLA response time)
3. Immediate assessment (5 min):
   - Check which replica is lagging: INFO replication
   - Check replica health: CPU, memory, disk I/O
   - Check network between master and replica
4. Short-term mitigation (15 min):
   - If network issue: escalate to network team
   - If replica CPU/disk bound: restart replica (kill + restart container)
   - If big command causing lag: identify via commandstats
5. Communication (ongoing):
   - Update status page if user-visible impact
   - Notify team lead of progress
6. Resolution:
   - Lag recovered to < 1s
   - Confirm replica is healthy: INFO replication → lag = 0
   - Close incident in PagerDuty
7. Post-incident (within 24h):
   - Write postmortem
   - Identify root cause
   - Implement prevention (e.g., separate network, increase backlog)
   - Update runbook
```

---

### Key Takeaways

1. **Monitoring is not optional in production**: The cost of an undetected incident far exceeds the cost of monitoring infrastructure.
2. **Percentiles over averages**: p95/p99 latency reveals user-visible issues that average latency hides.
3. **ACL is essential**: Named users with least-privilege permissions should be mandatory, not optional.
4. **Alert without runbook = noise**: Every alert must have actionable steps, escalation path, and expected resolution time.
5. **Disable KEYS, rename FLUSH***: These commands can take down Redis. `KEYS` blocks the entire server; `FLUSHDB` destroys data.
6. **Test your monitoring**: Simulate failures (slow commands, memory pressure, connection exhaustion) to verify your alerts and dashboards work before an actual incident.
