# Day 29: Observability, Security & Troubleshooting — Reference Document

---

## 1. Command Cheat Sheet

### INFO Commands

| Command | Mô tả |
|---|---|
| `INFO [section]` | Full metrics. Sections: server, clients, memory, persistence, stats, replication, cpu, commandstats, latency, sentinel, cluster, keyspace |
| `INFO memory` | Memory usage: used_memory, mem_fragmentation_ratio, mem_rss, eviction metrics |
| `INFO stats` | Operations count: keyspace_hits, keyspace_misses, total_commands_processed, rejected_connections |
| `INFO replication` | Role, replica status, offsets, lag |
| `INFO clients` | connected_clients, blocked_clients, tracking_clients, maxinputbuffer, maxoutputbuffer |
| `INFO commandstats` | Per-command latency: calls, usec, usec_per_call |
| `INFO persistence` | RDB/AOF status: loading, aof_rewrite_in_progress, rdb_bgsave_in_progress |
| `INFO server` | Version, uptime, process_id, os |

### Monitoring Commands

| Command | Mô tả |
|---|---|
| `SLOWLOG GET [N]` | Get N slowest commands. Each entry: time, args, duration (μs) |
| `SLOWLOG LEN` | Current slowlog size |
| `SLOWLOG RESET` | Clear slowlog |
| `LATENCY DOCTOR` | Analyze latency issues and give recommendations |
| `LATENCY HISTORY <event>` | Latency samples for specific event |
| `LATENCY RESET <event>` | Reset latency data for event |
| `LATENCY GRAPH <event>` | ASCII graph of latency samples |
| `MEMORY DOCTOR` | Memory diagnosis with recommendations |
| `MEMORY STATS` | Detailed memory breakdown by category (Redis 4.4+) |
| `MEMORY USAGE <key>` | Memory used by specific key |
| `DEBUG SLEEP <seconds>` | Simulate latency (for testing) |
| `DEBUG COMMAND <getkeys>` | Inspect command without executing |
| `CLIENT LIST` | All connected clients with details |
| `CLIENT KILL <addr>` | Kill specific client |
| `CLIENT PAUSE <timeout>` | Pause all clients for timeout ms |

### ACL Commands

| Command | Syntax | Mô tả |
|---|---|---|
| `ACL SETUSER` | `ACL SETUSER name [rules...]` | Create/modify user |
| `ACL GETUSER` | `ACL GETUSER name` | Get user details |
| `ACL LIST` | `ACL LIST` | List all users |
| `ACL DELUSER` | `ACL DELUSER name` | Delete user |
| `ACL SAVE` | `ACL SAVE` | Save ACL to config |
| `ACL LOAD` | `ACL LOAD` | Load ACL from config |
| `AUTH` | `AUTH user password` | Authenticate |

### TLS / Security Commands

| Command | Mô tả |
|---|---|
| `CONFIG GET` | Read config at runtime |
| `CONFIG SET` | Write config at runtime |
| `CLIENT ENCODING` | Set client encoding |

---

## 2. Key INFO Fields Reference

### INFO memory

```
used_memory:247387648           # bytes (247 MB)
used_memory_human:235.94M
used_memory_rss:349057024        # RSS in bytes (includes fragmentation)
used_memory_rss_human:332.86M
used_memory_peak:312387648
used_memory_peak_human:297.94M
used_memory_peak_perc:79.21%
used_memory_overhead:2000000
used_memory_startup:1000000
used_memory_dataset:245387648
used_memory_scripts:0
used_memory_vm:0
maxmemory:536870912             # maxmemory bytes (512 MB)
maxmemory_human:512.00M
maxmemory_policy:allkeys-lru
mem_fragmentation_ratio:1.41     # >1.5 = warning, >2.0 = critical
mem_not_counted_for_evict:0
mem_replication_backlog:1048576
mem_clients_slave:0
mem_clients_normal:1000000
mem_aof_buffer:0
mem_allocator:jemalloc-5.3.0
active_defrag_running:0
lazyfree_pending_objects:0
lazyfree_pending_objects_volatile:0
```

### INFO stats (cache metrics)

```
total_commands_processed:1234567
instantaneous_ops_per_sec:5432
total_net_input_bytes:98765432
total_net_output_bytes:123456789
instantaneous_input_kbps:12.34
instantaneous_output_kbps:56.78
rejected_connections:0          # CRITICAL: should be 0
keyspace_hits:1000000           # Cache hit count
keyspace_misses:100000          # Cache miss count
keyspace_hitrate:90.91%         # hit_rate
expired_keys:50000              # Keys expired by active expiration
evicted_keys:100                # Keys evicted due to maxmemory
```

### INFO clients

```
connected_clients:150
authed_clients:148
blocked_clients:2               # > 0 = something is blocking
tracking_clients:0
clients_in_timeout_table:0
clients_longest_output_list:2048
clients_biggest_input_buf:1024
```

### INFO commandstats (example)

```
cmdstat_get:calls=1000000,usec=500000,usec_per_call=0.50,rejected_call=0,failed_call=0
cmdstat_set:calls=500000,usec=2500000,usec_per_call=5.00,rejected_call=0,failed_call=0
cmdstat_keys:calls=10,usec=8000000,usec_per_call=800000.00,rejected_call=0,failed_call=0
cmdstat_scan:calls=1000,usec=50000,usec_per_call=50.00,rejected_call=0,failed_call=0
```

### Replication INFO (on replica)

```
role:slave
master_host:10.0.1.10
master_port:6379
master_link_status:up
master_sync_in_progress:0
slave_repl_offset:1234567
slave_priority:100
slave_read_only:1
replica_announced:1
connected_slaves:0
master_repl_offset:1234567
second_repl_offset:1200000
repl_backlog_active:1
repl_backlog_size:104857600
repl_backlog_histlen:1523
repl_backlog_first_size:8204
```

---

## 3. Configuration Reference

### redis.conf — Monitoring & Security

```txt
# ── Logging ──────────────────────────────────────────────────
loglevel notice
logfile /var/log/redis/redis.log

# ── Slowlog ─────────────────────────────────────────────────
slowlog-log-slower-than 10000   # microseconds (10ms). 0 = disable.
slowlog-max-len 128             # max entries in slowlog

# ── Clients ─────────────────────────────────────────────────
maxclients 10000
timeout 30                      # disconnect idle clients after N seconds
tcp-keepalive 300               # TCP keepalive for detecting dead clients

# ── Memory ───────────────────────────────────────────────────
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# ── Memory Overhead ─────────────────────────────────────────
# Client output buffer limits
client-output-buffer-limit normal 32mb 8mb 60   # normal clients
client-output-buffer-limit replica 128mb 64mb 60 # replica connections
client-output-buffer-limit pubsub 32mb 8mb 60    # pub/sub subscribers

# ── ACL ─────────────────────────────────────────────────────
# Named users (Redis 6+)
user default on nopass ~* +@read +ping -@dangerous
# Admin user (manual use only)
user admin on >admin_hash ~* +@all -@dangerous

# ── Command Renaming ────────────────────────────────────────
rename-command FLUSHDB "FLUSHDB_prod_a1b2c3d4"
rename-command FLUSHALL "FLUSHALL_prod_e5f6g7h8"
rename-command KEYS ""
rename-command DEBUG ""
rename-command SHUTDOWN ""
rename-command CONFIG "CONFIG_prod_m3n4o5p6"

# ── Network ─────────────────────────────────────────────────
bind 10.0.1.10 127.0.0.1        # internal IP + localhost only
protected-mode yes               # only if bind includes 0.0.0.0
port 6379

# ── TLS (enable for cross-AZ / external) ──────────────────
# tls-port 6380
# tls-cert-file /etc/redis/tls/redis.crt
# tls-key-file /etc/redis/tls/redis.key
# tls-ca-cert-file /etc/redis/tls/ca.crt
# tls-cert-verify-clients required
# tls-protocols TLSv1.2 TLSv1.3
# tls-replication yes          # for replica connections
```

### redis_exporter Configuration

```yaml
# prometheus redis_exporter deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis-exporter
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: redis-exporter
          image: oliver006/redis_exporter:v1.61.0
          args:
            - --redis.addr=redis://redis-master:6379
            - --redis.password=$(REDIS_PASSWORD)
            - --web.listen-address=:9121
            - --check-keys=cache:*,session:*
            - --scrape-timeout=5s
            - --debug=false
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: password
          ports:
            - name: metrics
              containerPort: 9121
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
```

---

## 4. Docker Compose — Production Monitoring Stack

```yaml
# docker-compose.monitoring.yml
version: "3.8"

services:
  # ── Redis Master ──────────────────────────────────────────
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
      --requirepass redispass123
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --maxmemory-samples 5
      --slowlog-log-slower-than 10000
      --slowlog-max-len 128
      --enable-debug-command yes
      --maxclients 10000
      --timeout 30
      --tcp-keepalive 300
      --client-output-buffer-limit normal 32mb 8mb 60
      --loglevel notice
      --logfile /data/redis.log
      --save 900 1
      --save 300 10
      --save 60 10000
      --appendonly yes
      --appendfsync everysec
    volumes:
      - redis-master-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redispass123", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - redis-net

  # ── Redis Replica ─────────────────────────────────────────
  redis-replica:
    image: redis:7.2-alpine
    container_name: redis-replica
    hostname: redis-replica
    ports:
      - "6380:6379"
    command: >
      redis-server
      --bind 0.0.0.0
      --protected-mode no
      --requirepass redispass123
      --replicaof redis-master 6379
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --replica-read-only yes
      --slowlog-log-slower-than 10000
      --slowlog-max-len 128
      --maxclients 10000
      --timeout 30
    volumes:
      - redis-replica-data:/data
    depends_on:
      redis-master:
        condition: service_healthy
    networks:
      - redis-net

  # ── Redis Exporter ────────────────────────────────────────
  redis-exporter:
    image: oliver006/redis_exporter:v1.61.0
    container_name: redis-exporter
    ports:
      - "9121:9121"
    environment:
      REDIS_ADDR: "redis://redis-master:6379"
      REDIS_PASSWORD: "redispass123"
    depends_on:
      redis-master:
        condition: service_healthy
    networks:
      - redis-net
    restart: unless-stopped

  # ── Prometheus ────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./alert_rules.yml:/etc/prometheus/alert_rules.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=90d'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    networks:
      - redis-net
    restart: unless-stopped

  # ── Grafana ───────────────────────────────────────────────
  grafana:
    image: grafana/grafana:10.2.2
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin123
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    networks:
      - redis-net
    restart: unless-stopped

volumes:
  redis-master-data:
  redis-replica-data:
  prometheus-data:
  grafana-data:

networks:
  redis-net:
    driver: bridge
```

---

## 5. Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: "redis"
    static_configs:
      - targets:
          - "redis-exporter:9121"
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        regex: "([^:]+):\\d+"
        replacement: "${1}"
```

### Prometheus Alert Rules

```yaml
# alert_rules.yml
groups:
  - name: redis_alerts
    rules:
      # ── Memory ─────────────────────────────────────────────
      - alert: RedisHighMemoryWarning
        expr: (redis_memory_used_bytes / redis_memory_max_bytes) > 0.75
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory above 75%"
          description: "{{ $labels.instance }} memory is {{ $value | humanizePercentage }}"

      - alert: RedisHighMemoryCritical
        expr: (redis_memory_used_bytes / redis_memory_max_bytes) > 0.90
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Redis memory above 90%"
          description: "{{ $labels.instance }} is {{ $value | humanizePercentage }} — eviction imminent"

      # ── Eviction ──────────────────────────────────────────
      - alert: RedisEvictionActive
        expr: rate(redis_evicted_keys_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Redis eviction rate elevated"
          description: "{{ $labels.instance }} evictions: {{ $value | humanize }} keys/sec"

      - alert: RedisEvictionCritical
        expr: rate(redis_evicted_keys_total[1m]) > 100
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis eviction rate critical"
          description: "{{ $labels.instance }} evictions: {{ $value | humanize }} keys/sec — SLA breach"

      # ── Replication ───────────────────────────────────────
      - alert: RedisReplicationLagWarning
        expr: redis_replication_lag_seconds > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Redis replication lag above 1 second"
          description: "{{ $labels.instance }} is {{ $value }}s behind master"

      - alert: RedisReplicationLagCritical
        expr: redis_replication_lag_seconds > 5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis replication lag exceeds 5 seconds"
          description: "{{ $labels.instance }} is {{ $value }}s behind master — potential data inconsistency"

      # ── Latency ───────────────────────────────────────────
      # redis_exporter exposes aggregate commandstats, not true percentiles.
      # Use client-side/application histogram buckets for p95/p99 alerts.
      - alert: RedisLatencyP99Warning
        expr: histogram_quantile(0.99, sum(rate(redis_client_command_duration_seconds_bucket[5m])) by (le, instance, cmd)) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis p99 latency above 50ms"
          description: "{{ $labels.instance }} p99 latency is {{ $value }}s for command {{ $labels.cmd }}"

      - alert: RedisLatencyP99Critical
        expr: histogram_quantile(0.99, sum(rate(redis_client_command_duration_seconds_bucket[5m])) by (le, instance)) > 0.2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Redis overall p99 latency above 200ms"
          description: "{{ $labels.instance }} overall p99 is {{ $value }}s — user experience degraded"

      # ── Slowlog ───────────────────────────────────────────
      - alert: RedisSlowlogGrowing
        expr: increase(redis_slowlog_length[5m]) > 20
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Redis slowlog growing"
          description: "{{ $labels.instance }} had {{ $value }} new slowlog entries in 5 minutes"

      # ── Connections ───────────────────────────────────────
      - alert: RedisHighConnectionCount
        expr: redis_connected_clients / redis_max_clients > 0.80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis connection count above 80%"
          description: "{{ $labels.instance }} has {{ $value | humanizePercentage }} of max clients"

      - alert: RedisConnectionRejected
        expr: rate(redis_rejected_connections_total[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Redis is rejecting connections"
          description: "{{ $labels.instance }} rejected {{ $value | humanize }} connections/sec — maxclients reached"

      - alert: RedisBlockedClients
        expr: redis_blocked_clients > 0
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Redis has blocked clients"
          description: "{{ $labels.instance }} has {{ $value }} blocked clients"

      # ── Fragmentation ──────────────────────────────────────
      - alert: RedisHighFragmentation
        expr: redis_mem_fragmentation_ratio > 1.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory fragmentation above 1.5"
          description: "{{ $labels.instance }} fragmentation: {{ $value }}. Consider restart."

      # ── Hit Rate ──────────────────────────────────────────
      - alert: RedisLowHitRate
        expr: (redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)) < 0.80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis cache hit rate below 80%"
          description: "{{ $labels.instance }} hit rate: {{ $value | humanizePercentage }}"
```

---

## 6. Grafana Dashboard Snippets

### Dashboard Datasource Config

```yaml
# grafana/datasources/datasource.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

### Dashboard Config

```yaml
# grafana/dashboards/dashboard.yml
apiVersion: 1

providers:
  - name: "Redis Dashboards"
    folder: "Redis"
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

### Key Panels (PromQL queries)

```txt
# Memory Usage Panel
redis_memory_used_bytes / redis_memory_max_bytes

# Hit Rate Gauge
sum(rate(redis_keyspace_hits_total[5m])) /
(sum(rate(redis_keyspace_hits_total[5m])) + sum(rate(redis_keyspace_misses_total[5m])))

# Operations Per Second
sum(rate(redis_commands_processed_total[1m]))

# Connected Clients
redis_connected_clients

# Replication Lag (seconds)
redis_replication_lag_seconds

# p99 Latency by Command Type
histogram_quantile(0.99,
  sum(rate(redis_client_command_duration_seconds_bucket[5m])) by (le, cmd)
)

# Eviction Rate
rate(redis_evicted_keys_total[5m])

# Slowlog Entries
redis_slowlog_length
```

---

## 7. Redis ACL Patterns

### Pattern 1: Minimal Read-Only User

```txt
# Monitoring agent: can only read stats, no key access
ACL SETUSER monitoring on >mon_hash ~* +ping +info +dbsize +memory|stats +memory|doctor +slowlog|get +command +client|list +config|get -@dangerous -@write -FLUSH* -KEYS -DEBUG
```

### Pattern 2: Application User

```txt
# App server: read/write on specific key patterns, no dangerous commands
ACL SETUSER app on >app_hash ~app:* ~session:* ~cache:* ~rate:* +@read +@write +@transaction +@scripting -FLUSH* -KEYS -DEBUG -CONFIG -SHUTDOWN -BGSAVE -BGREWRITEAOF -SAVE -SYNC -PSYNC -REPLICAOF -WAIT
```

### Pattern 3: Analytics User

```txt
# Analytics: read-only, can scan large datasets
ACL SETUSER analytics on >analytics_hash ~analytics:* ~metrics:* +@read +scan +dbsize +memory|usage +slowlog|get +command +client|list -KEYS -DEBUG -FLUSH* -CONFIG -SHUTDOWN
```

### Pattern 4: Backup User

```txt
# Backup service: full read, no writes, can trigger BGSAVE
ACL SETUSER backup on >backup_hash ~* +@read +save +bgsave +lastsave +sync +role +info -@write -FLUSH* -KEYS -DEBUG -CONFIG -SHUTDOWN -slaveof -replicaof
```

### View and Manage ACL

```bash
# List all users
redis-cli ACL LIST

# Show specific user rules
redis-cli ACL GET monitoring

# Delete user
redis-cli ACL DELUSER old_user

# Test user permissions
redis-cli -u redis://monitoring:mon_hash@localhost:6379 PING
redis-cli -u redis://monitoring:mon_hash@localhost:6379 GET cache:key  # Should error

# Save ACL rules to config file
redis-cli ACL SAVE

# Generate secure random password
openssl rand -hex 32
```

---

## 8. Security Checklist

### Pre-Deployment Checklist

```
[ ] ACL configured — no default user with full access
[ ] Network isolation — Redis bound to internal IPs only
[ ] protected-mode — enabled if bind includes 0.0.0.0
[ ] Dangerous commands renamed or disabled:
      FLUSHDB, FLUSHALL, KEYS, DEBUG, SHUTDOWN, CONFIG
[ ] requirepass OR ACL password set (Redis 6+: use ACL, not requirepass alone)
[ ] maxmemory set — prevent unbounded memory growth
[ ] maxmemory-policy set — know what happens when memory is full
[ ] slowlog-log-slower-than set — 10000 (10ms) for production
[ ] slowlog-max-len set — 128 or higher
[ ] client-output-buffer-limits configured
[ ] TLS configured (if cross-AZ or cloud)
[ ] maxclients set — reasonable limit for instance size
[ ] Client timeout set — timeout 30 (idle client disconnect)
[ ] Connection monitoring enabled (rejected_connections metric)
[ ] Metrics exported (redis_exporter + Prometheus)
[ ] Alert thresholds configured
[ ] Backup strategy documented (BGSAVE / redis-cli --rdb)
[ ] Logs written to file (not just stdout in Docker)
[ ] No DEBUG command accessible to application users
[ ] Sentinel/Cluster auth configured (if applicable)
```

### ACL Security Checklist

```
[ ] Default user disabled or restricted
[ ] Named users for each application/service
[ ] Key patterns scoped per user (e.g., app:user1:* only)
[ ] No user has +@dangerous permission
[ ] No user can use FLUSH* without explicit rename
[ ] KEYS command disabled or renamed
[ ] Admin user separate from application users
[ ] Passwords stored securely (secret manager, not in code)
[ ] Password rotation policy defined
[ ] Monitoring user has minimal permissions
[ ] ACL rules saved to config file
[ ] ACL tested after each change
```

---

## 9. Troubleshooting Quick Reference

### High Memory

```bash
# Step 1: Diagnose
redis-cli -a $PASS INFO memory | grep -E "used_memory|maxmemory|mem_fragmentation|evicted"

# Step 2: Memory doctor
redis-cli -a $PASS MEMORY DOCTOR

# Step 3: Find big keys
redis-cli -a $PASS --bigkeys

# Step 4: Check memory by category
redis-cli -a $PASS MEMORY STATS

# Step 5: Check specific key size
redis-cli -a $PASS MEMORY USAGE key:your:key

# If fragmentation:
#   < 1.5: OK
#   1.5 - 2.0: warning → plan restart during low traffic
#   > 2.0: critical → restart now
```

### High Latency

```bash
# Step 1: Quick check
redis-cli -a $PASS --latency

# Step 2: Histogram
redis-cli -a $PASS --latency-history

# Step 3: Slowlog
redis-cli -a $PASS SLOWLOG GET 20

# Step 4: Command stats
redis-cli -a $PASS INFO commandstats | grep -v "^#" | sort -t= -k3 -rn | head -20

# Step 5: Big keys
redis-cli -a $PASS --bigkeys

# Step 6: Check for fork
redis-cli -a $PASS INFO persistence | grep -E "fork|rdb|aof"
```

### Connection Issues

```bash
# Step 1: Current connections
redis-cli -a $PASS INFO clients

# Step 2: List all clients
redis-cli -a $PASS CLIENT LIST

# Step 3: Find idle connections
redis-cli -a $PASS CLIENT LIST | grep "idle=[0-9]" | head -10

# Step 4: Find blocked clients
redis-cli -a $PASS CLIENT LIST | grep "cmd=B"

# Step 5: Kill idle connections older than 5 minutes
redis-cli -a $PASS CLIENT KILL TYPE normal IDLE-TIME 300

# Step 6: Check rejected connections
redis-cli -a $PASS INFO stats | grep rejected
```

### Replication Lag

```bash
# Step 1: On master
redis-cli -a $PASS INFO replication

# Step 2: On replica
redis-cli -a $PASS INFO replication | grep -E "master_link|repl_offset|lag"

# Step 3: Monitor continuously
watch 'redis-cli -a $PASS INFO replication | grep -E "master_link|repl_offset|lag"'

# Step 4: Check replica command latency
redis-cli -a $PASS INFO commandstats | sort -t= -k3 -rn | head -10
```

---

## 10. Links & References

### Official Redis Documentation

- [Redis Security](https://redis.io/docs/management/security/)
- [Redis ACL](https://redis.io/docs/management/security/acl/)
- [Redis TLS](https://redis.io/docs/management/security/encryption/)
- [Redis SENSITIVE Commands](https://redis.io/docs/management/security/encryption/)
- [Redis Slowlog](https://redis.io/commands/slowlog/)
- [Redis LATENCY DOCTOR](https://redis.io/commands/latency-doctor/)
- [Redis MEMORY DOCTOR](https://redis.io/commands/memory-doctor/)
- [Redis Command Remapping](https://redis.io/docs/management/security/encryption/)

### Monitoring Tools

- [redis_exporter (Prometheus)](https://github.com/oliver006/redis_exporter)
- [Grafana Redis Dashboard #11835](https://grafana.com/grafana/dashboards/11835)
- [Grafana Redis Dashboard #14091](https://grafana.com/grafana/dashboards/14091)
- [Redis Prometheus Exporter Metrics](https://github.com/oliver006/redis_exporter#available-metrics)
- [Prometheus Alerting](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)

### ELK Integration

- [Filebeat Redis Module](https://www.elastic.co/guide/en/beats/filebeat/current/filebeat-module-redis.html)
- [Redis slowlog as JSON](https://github.com/redis/redis/issues/7967)
- [Elasticsearch Redis Input Plugin](https://www.elastic.co/guide/en/logstash/current/plugins-inputs-redis.html)

### Engineering Articles

- [How GitHub's Engineering Team Uses Redis](https://github.blog/category/engineering/open-source/infrastructure/)
- [Discord — Using Redis at Scale](https://discord.com/blog/)
- [Uber — Redis Connection Handling](https://www.uber.com/)
- [Netflix — Redis Latency Monitoring](https://netflix.com/)
- [Shopify — Redis in Production](https://shopify.engineering/)

### Books

- *Redis in Action* — Josiah Carlson (Manning)
- *Designing Data-Intensive Applications* — Martin Kleppmann, Chapter 3 & 5
- *Redis Deep Dive* — Suyog Gupta, pap40

### Benchmark & Tools

- [redis-benchmark](https://redis.io/docs/management/optimization/redis-benchmark/)
- [memtier_benchmark](https://github.com/RedisLabs/memtier_benchmark)
- [redis-cli --latency](https://redis.io/docs/management/optimization/redis-cli/)
- [redis-faina (command analysis)](https://github.com/facebookarchive/redis-faina)
