# Day 47: Document — Database on Kubernetes vs Managed Database Reference

---

## 1. DB on Kubernetes vs Managed DB Decision Matrix

### Comprehensive Comparison

| Tiêu chí | DB on Kubernetes | Managed DB (RDS/Cloud SQL) | Serverless DB (Aurora/Neon) |
|----------|-----------------|---------------------------|---------------------------|
| **Setup time** | 1-2 ngày (operator + config) | 30 phút (console/terraform) | 10 phút |
| **Operational burden** | Cao (team maintain) | Thấp (provider maintain) | Rất thấp |
| **Cost (< 100GB)** | $50-200/month | $100-500/month | $20-200/month |
| **Cost (1TB+)** | $500-2000/month | $2000-8000/month | $3000-15000/month |
| **Customization** | Full control | Limited parameters | Very limited |
| **Performance tuning** | Kernel + storage + DB params | DB params only | Minimal |
| **Max performance** | Local NVMe: excellent | Network storage: good | Variable |
| **Auto failover** | Operator: 10-30s | Built-in: < 30s | Built-in: < 10s |
| **Backup** | Self-configure (WAL + base) | Built-in + PITR | Built-in + PITR |
| **Multi-cloud** | ✅ Portable | ❌ Vendor lock-in | ❌ Vendor lock-in |
| **Compliance** | Full data control | Provider region | Provider region |
| **Scaling (read)** | Manual replica config | 1-click read replica | Auto-scaling |
| **Scaling (write)** | Sharding (complex) | Vertical only | Some auto-scaling |
| **Connection pooling** | PgBouncer (self-manage) | RDS Proxy (extra cost) | Built-in |
| **Monitoring** | Self-setup (Prometheus) | CloudWatch/built-in | Built-in |
| **Version upgrade** | Operator rolling update | Maintenance window | Auto |
| **Team skill needed** | K8s + DBA + operator | Cloud + basic DBA | Minimal |
| **Risk level** | Medium-High | Low | Low |
| **Recovery expertise** | Team handles incidents | Provider handles | Provider handles |
| **Vendor lock-in** | None | Medium | High |

### Decision Flowchart

```
START: Chọn database hosting strategy
│
├── Q1: Team có DBA hoặc experienced DevOps?
│   ├── Không → Managed Database
│   └── Có → Tiếp Q2
│
├── Q2: Data > 1TB hoặc cost > $3K/month managed?
│   ├── Không → Managed Database (cost justified)
│   └── Có → Tiếp Q3
│
├── Q3: Compliance yêu cầu data locality control?
│   ├── Có → DB on Kubernetes (full control)
│   └── Không → Tiếp Q4
│
├── Q4: Multi-cloud hoặc no vendor lock-in required?
│   ├── Có → DB on Kubernetes
│   └── Không → Tiếp Q5
│
├── Q5: Database là critical (99.99%+ SLA)?
│   ├── Có → Managed Database (SLA guarantee)
│   └── Không → DB on Kubernetes (cost saving)
│
└── Default: Hybrid
    - Critical DBs → Managed
    - Non-critical DBs → Kubernetes
```

---

## 2. Operator Pattern Reference

### CloudNativePG (PostgreSQL)

```yaml
# Minimal production cluster
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-production
  namespace: database
spec:
  instances: 3
  imageName: ghcr.io/cloudnative-pg/postgresql:16.2
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "1GB"
      effective_cache_size: "3GB"
      work_mem: "16MB"
      maintenance_work_mem: "256MB"
      random_page_cost: "1.1"        # SSD
      effective_io_concurrency: "200" # SSD
      wal_buffers: "64MB"
      max_wal_size: "2GB"
      checkpoint_completion_target: "0.9"
      log_min_duration_statement: "500"
      log_statement: "ddl"
      
    pg_hba:
    - host all all 10.244.0.0/16 scram-sha-256
    - host all all 0.0.0.0/0 reject
  
  storage:
    storageClass: gp3-encrypted
    size: 100Gi
  
  walStorage:
    storageClass: gp3-encrypted
    size: 20Gi
  
  resources:
    requests:
      cpu: "2"
      memory: 4Gi
    limits:
      cpu: "4"
      memory: 8Gi
  
  affinity:
    enablePodAntiAffinity: true
    topologyKey: kubernetes.io/hostname
  
  backup:
    barmanObjectStore:
      destinationPath: s3://backups/pg-production
      s3Credentials:
        accessKeyId:
          name: s3-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-creds
          key: SECRET_ACCESS_KEY
      wal:
        compression: gzip
        maxParallel: 8
    retentionPolicy: "30d"
  
  monitoring:
    enablePodMonitor: true
    customQueriesConfigMap:
    - name: pg-custom-queries
      key: queries
  
  nodeMaintenanceWindow:
    inProgress: false
    reusePVC: true
```

### Percona Operator (MySQL)

```yaml
apiVersion: pxc.percona.com/v1
kind: PerconaXtraDBCluster
metadata:
  name: mysql-cluster
spec:
  crVersion: "1.14.0"
  secretsName: mysql-passwords
  
  pxc:
    size: 3
    image: percona/percona-xtradb-cluster:8.0.35
    resources:
      requests:
        memory: 2Gi
        cpu: "1"
    volumeSpec:
      persistentVolumeClaim:
        storageClassName: gp3
        resources:
          requests:
            storage: 100Gi
    affinity:
      antiAffinityTopologyKey: kubernetes.io/hostname
  
  haproxy:
    enabled: true
    size: 3
    resources:
      requests:
        memory: 256Mi
        cpu: 200m
  
  proxysql:
    enabled: false
  
  backup:
    image: percona/percona-xtradb-cluster-operator:1.14.0-pxc8.0-backup-pxb8.0.35
    storages:
      s3-backup:
        type: s3
        s3:
          bucket: mysql-backups
          credentialsSecret: s3-creds
    schedule:
    - name: daily-full
      schedule: "0 2 * * *"
      keep: 7
      storageName: s3-backup
```

### Vitess Operator (MySQL horizontal scaling)

```yaml
apiVersion: planetscale.com/v2
kind: VitessCluster
metadata:
  name: vitess-cluster
spec:
  images:
    vtctld: vitess/vtctld:18.0.0
    vtadmin: vitess/vtadmin:18.0.0
    vtgate: vitess/vtgate:18.0.0
    vttablet: vitess/vttablet:18.0.0
    vtbackup: vitess/vtbackup:18.0.0
    mysqld: vitess/mysqlserver:18.0.0
  
  cells:
  - name: zone1
    gateway:
      replicas: 2
      resources:
        requests:
          cpu: 500m
          memory: 512Mi
  
  keyspaces:
  - name: commerce
    turndownPolicy: Immediate
    partitionings:
    - equal:
        parts: 2
        shardTemplate:
          databaseInitScriptSecret:
            name: commerce-schema
            key: init.sql
          tabletPools:
          - cell: zone1
            type: replica
            replicas: 3
            vttablet:
              resources:
                requests:
                  cpu: 500m
                  memory: 1Gi
            mysqld:
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
              configOverrides: |
                innodb_buffer_pool_size = 1073741824
            dataVolumeClaimTemplate:
              storageClassName: gp3
              resources:
                requests:
                  storage: 50Gi
```

### Operator Comparison

| Feature | CloudNativePG | Percona (PXC) | CrunchyData PGO | Vitess |
|---------|--------------|---------------|-----------------|--------|
| **Database** | PostgreSQL | MySQL (PXC/PS) | PostgreSQL | MySQL |
| **Replication** | Streaming | Galera/Group | Streaming | Vitess |
| **Failover** | Auto (10-30s) | Auto (Galera) | Auto (Patroni) | Auto |
| **Backup** | Barman (S3) | xtrabackup (S3) | pgBackRest (S3) | vtbackup |
| **PITR** | ✅ | ✅ | ✅ | ❌ |
| **Connection pool** | PgBouncer | ProxySQL/HAProxy | PgBouncer | VTGate |
| **Monitoring** | Prometheus | PMM | pgMonitor | Vitess metrics |
| **Horizontal scale** | Read replicas | Galera multi-primary | Read replicas | Sharding |
| **Maturity** | Production-ready | Production-ready | Production-ready | YouTube-scale |
| **License** | Apache 2.0 | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| **CNCF** | Sandbox | - | - | Graduated |

---

## 3. Backup/Restore Strategy Checklist

### Backup Configuration

- [ ] **3-2-1 Rule**: 3 copies, 2 media types, 1 offsite
- [ ] **WAL archiving**: Continuous (RPO ~0)
- [ ] **Base backup schedule**: Daily (hoặc mỗi 6-12h cho large DBs)
- [ ] **Retention policy**: ≥ 30 ngày cho production
- [ ] **Backup encryption**: AES-256 at rest
- [ ] **Cross-region backup**: Backup ở region khác
- [ ] **Backup monitoring**: Alert khi backup fail hoặc quá cũ
- [ ] **Backup size tracking**: Monitor growth rate

### Restore Testing

- [ ] **Monthly restore test**: Restore to staging environment
- [ ] **PITR test**: Restore to specific timestamp
- [ ] **Full restore timing**: Đo RTO thực tế
- [ ] **Data integrity check**: Verify row counts, checksums
- [ ] **Application compatibility**: Test app kết nối restored DB
- [ ] **Document results**: RTO measured, issues found

### RPO/RTO Reference

| Backup Method | RPO | RTO | Cost |
|--------------|-----|-----|------|
| WAL archiving (continuous) | ~0 (giây) | 15-60 phút | Medium |
| Base backup hourly | 1 giờ | 30-120 phút | High (storage) |
| Base backup daily | 24 giờ | 30-120 phút | Low |
| Snapshot (EBS/PV) | Snapshot interval | 5-15 phút | Medium |
| Logical backup (pg_dump) | Dump interval | 1-4 giờ (large DB) | Low |

---

## 4. Storage Performance Benchmarking

### Quick Benchmark Commands

```bash
# PostgreSQL pgbench (built-in benchmark)
# Initialize
pgbench -i -s 100 -h localhost -U postgres testdb
# s=100 → ~1.5GB data

# Run benchmark (read-write)
pgbench -c 10 -j 2 -T 60 -h localhost -U postgres testdb
# c=clients, j=threads, T=duration

# Run benchmark (read-only)
pgbench -c 10 -j 2 -T 60 -S -h localhost -U postgres testdb

# FIO disk benchmark (inside pod)
kubectl exec -it <db-pod> -- bash
apt-get update && apt-get install -y fio

# Sequential write
fio --name=seqwrite --rw=write --bs=128k --size=1G \
    --numjobs=1 --runtime=30 --time_based --directory=/var/lib/postgresql/data

# Random read (database-like)
fio --name=randread --rw=randread --bs=8k --size=1G \
    --numjobs=4 --runtime=30 --time_based --directory=/var/lib/postgresql/data

# Random write (WAL-like)
fio --name=randwrite --rw=randwrite --bs=8k --size=1G \
    --numjobs=4 --runtime=30 --time_based --fsync=1 --directory=/var/lib/postgresql/data
```

### Storage Class Recommendations

```yaml
# AWS EBS gp3 (general purpose — staging/dev)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true

---
# AWS EBS io2 (high performance — production DB)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: io2-high-perf
provisioner: ebs.csi.aws.com
parameters:
  type: io2
  iops: "10000"
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true

---
# Local NVMe (highest performance — latency-critical)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-nvme
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Retain  # IMPORTANT: manual cleanup
```

---

## 5. Failover Testing Runbook

### Pre-test Checklist

- [ ] Backup current state
- [ ] Notify team about planned failover test
- [ ] Monitor dashboard open
- [ ] Application health check endpoint ready
- [ ] Replication lag = 0 before starting

### Test Procedure

```bash
# Step 1: Record current state
echo "=== Pre-failover State ==="
kubectl get pods -n database -l cnpg.io/cluster=<name> \
  -o custom-columns="NAME:.metadata.name,ROLE:.metadata.labels.role,STATUS:.status.phase"

kubectl exec <primary-pod> -n database -- psql -U postgres -c "
  SELECT pg_current_wal_lsn();
  SELECT client_addr, state, sent_lsn, replay_lsn FROM pg_stat_replication;
"

# Step 2: Start monitoring
START_TIME=$(date +%s)
echo "Failover started at: $(date)"

# Step 3: Kill primary
kubectl delete pod <primary-pod> -n database

# Step 4: Monitor promotion
watch -n 1 'kubectl get pods -n database -l cnpg.io/cluster=<name> \
  -o custom-columns="NAME:.metadata.name,ROLE:.metadata.labels.role,STATUS:.status.phase,READY:.status.conditions[?(@.type==\"Ready\")].status"'

# Step 5: Wait for new primary
while ! kubectl get pods -n database -l role=primary | grep -q Running; do
  sleep 1
done
END_TIME=$(date +%s)

echo "New primary ready. Failover time: $((END_TIME - START_TIME)) seconds"

# Step 6: Verify application connectivity
curl -s http://app-service/health | jq .database

# Step 7: Verify data integrity
kubectl exec <new-primary-pod> -n database -- psql -U postgres -d appdb -c "
  SELECT count(*) FROM <critical_table>;
"

# Step 8: Verify replication resumed
kubectl exec <new-primary-pod> -n database -- psql -U postgres -c "
  SELECT client_addr, state FROM pg_stat_replication;
"
```

### Post-test Report Template

```markdown
## Failover Test Report

**Date**: YYYY-MM-DD
**Cluster**: <cluster-name>
**Reason**: Planned failover test

### Results

| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| Failover time | Xs | < 30s | ✅/❌ |
| Data loss | 0 rows | 0 rows | ✅/❌ |
| App downtime | Xs | < 60s | ✅/❌ |
| Errors during failover | N | < 10 | ✅/❌ |
| Replication resumed | Xs | < 60s | ✅/❌ |

### Issues Found
1. ...

### Action Items
1. ...
```

---

## 6. PostgreSQL Monitoring Queries

### Health Checks

```sql
-- Connection usage
SELECT count(*) AS total_connections,
       count(*) FILTER (WHERE state = 'active') AS active,
       count(*) FILTER (WHERE state = 'idle') AS idle,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conn,
       round(count(*)::numeric / (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') * 100, 1) AS usage_pct
FROM pg_stat_activity;

-- Replication lag (run on primary)
SELECT client_addr, state,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) / 1024 / 1024 AS lag_mb
FROM pg_stat_replication;

-- Database size
SELECT datname,
       pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database
WHERE datname NOT IN ('template0', 'template1')
ORDER BY pg_database_size(datname) DESC;

-- Table sizes (top 10)
SELECT schemaname || '.' || tablename AS table,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
       pg_size_pretty(pg_relation_size(schemaname || '.' || tablename)) AS data_size,
       pg_size_pretty(pg_indexes_size(schemaname || '.' || tablename::regclass)) AS index_size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
LIMIT 10;

-- Slow queries (requires log_min_duration_statement)
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
  AND state = 'active';

-- Cache hit ratio (should be > 99%)
SELECT 'index' AS type,
       sum(idx_blks_hit) / nullif(sum(idx_blks_hit + idx_blks_read), 0) * 100 AS ratio
FROM pg_statio_user_indexes
UNION ALL
SELECT 'table',
       sum(heap_blks_hit) / nullif(sum(heap_blks_hit + heap_blks_read), 0) * 100
FROM pg_statio_user_tables;

-- Checkpoint stats
SELECT checkpoints_timed, checkpoints_req,
       pg_size_pretty(buffers_checkpoint * 8192) AS checkpoint_write,
       pg_size_pretty(buffers_backend * 8192) AS backend_write
FROM pg_stat_bgwriter;
```

### Prometheus Metrics (CloudNativePG exports)

```
# Key metrics to dashboard/alert
cnpg_collector_up                          # Collector health
cnpg_pg_replication_lag                    # Replication lag (alert > 10MB)
cnpg_pg_stat_activity_count               # Connection count
cnpg_backends_total                        # Total backends
cnpg_pg_database_size_bytes               # Database size
cnpg_pg_stat_bgwriter_checkpoints_timed   # Timed checkpoints
cnpg_pg_stat_bgwriter_checkpoints_req     # Requested checkpoints  
cnpg_pg_stat_user_tables_n_tup_ins        # Rows inserted
cnpg_pg_stat_user_tables_n_tup_upd        # Rows updated
cnpg_pg_stat_user_tables_n_tup_del        # Rows deleted
```

---

## 7. Production Readiness Checklist

### Infrastructure

- [ ] Dedicated nodes cho database (node affinity)
- [ ] Anti-affinity: mỗi DB instance trên node khác nhau
- [ ] High-IOPS StorageClass (io2 hoặc local NVMe)
- [ ] Separate WAL storage volume
- [ ] PodDisruptionBudget configured
- [ ] Resource requests = limits (Guaranteed QoS)

### Database Configuration

- [ ] Connection pooling (PgBouncer/ProxySQL)
- [ ] shared_buffers = 25% pod memory
- [ ] max_connections tuned (không quá cao)
- [ ] Statement logging cho slow queries
- [ ] pg_hba.conf restrictive

### Security

- [ ] NetworkPolicy isolate database namespace
- [ ] TLS cho client connections
- [ ] Encryption at rest (StorageClass)
- [ ] Secrets managed properly (External Secrets)
- [ ] Database users least privilege
- [ ] Audit logging enabled

### Backup & Recovery

- [ ] WAL archiving to object storage
- [ ] Scheduled base backups
- [ ] Cross-region/account backup copy
- [ ] Retention policy configured
- [ ] Monthly restore test documented
- [ ] PITR verified

### Monitoring & Alerting

- [ ] Replication lag alert (> 10MB)
- [ ] Connection usage alert (> 80%)
- [ ] Disk usage alert (> 80%)
- [ ] Backup age alert (> 25h)
- [ ] Cache hit ratio alert (< 99%)
- [ ] Failover events alert
- [ ] Dashboard: connections, replication, disk, queries

