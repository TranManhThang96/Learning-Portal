# Day 47: Database on Kubernetes vs Managed Database

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích** được vì sao chạy database trên Kubernetes khó hơn stateless workloads và các thách thức cụ thể.
2. **Phân biệt** được Operator pattern và cách các database operators (CloudNativePG, Vitess, Percona) giải quyết vấn đề.
3. **Đánh giá** được khi nào nên chạy database trên Kubernetes vs dùng managed database service.
4. **Thiết kế** được backup/restore strategy và failover plan cho database trên Kubernetes.
5. **Tạo** được decision matrix giúp team chọn giải pháp database phù hợp theo context.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Mọi application cần database. Khi chuyển sang Kubernetes, câu hỏi lớn nhất luôn là:

> "Database có nên chạy trên Kubernetes không?"

Câu trả lời không phải "có" hoặc "không" — mà là **"tùy thuộc vào context"**.

### Hậu quả nếu quyết định sai

**Chạy DB trên K8s khi không nên**:
- Data loss do storage misconfiguration
- Downtime dài do thiếu automated failover
- Performance degradation do storage I/O bottleneck
- Team mất 60% thời gian vận hành database thay vì phát triển product

**Dùng managed DB khi không nên**:
- Vendor lock-in (khó migrate)
- Chi phí cao gấp 3-5x tự host cho large-scale workloads
- Thiếu control: không tune được kernel parameters, storage engine
- Latency cross-region khi managed DB ở region khác application

### Liên hệ với developer

Nếu bạn đã từng quản lý connection pool, configure read replicas, hoặc handle database failover trong application code — bạn đã biết database operations phức tạp thế nào. Operator pattern trên Kubernetes tự động hóa những việc này, giống một **experienced DBA viết thành code** chạy 24/7.

---

## 3. Kiến thức nền tảng

### Vì sao database trên Kubernetes khó?

Database là **stateful workload** — khác biệt cơ bản với stateless services:

```
Stateless (API server):          Stateful (Database):
┌──────────┐                     ┌──────────┐
│ Pod v1   │ ← kill & recreate   │ Pod v1   │ ← kill = DATA LOSS
│ No data  │    → No problem     │ 500GB    │    nếu không có PV
└──────────┘                     └──────────┘

Scale: tạo thêm pods            Scale: replication setup,
       identical copies                 shard routing, consensus
```

**5 thách thức chính**:

| # | Thách thức | Stateless | Stateful (DB) |
|---|-----------|-----------|---------------|
| 1 | **Storage** | Không cần | PV, PVC, StorageClass, I/O performance |
| 2 | **Identity** | Pods interchangeable | Mỗi node có role (primary/replica) |
| 3 | **Ordering** | Start/stop bất kỳ | Primary phải start trước replicas |
| 4 | **Network** | Service load balance | Stable hostname cho mỗi node |
| 5 | **Data** | Stateless, no backup | Backup, restore, PITR, encryption |

### Operator Pattern

**Analogy**: Operator giống một **DBA tự động** — nó biết:
- Cách deploy database cluster
- Cách thêm/xóa replicas
- Cách failover khi primary chết
- Cách backup theo schedule
- Cách restore từ backup
- Cách upgrade version

```mermaid
graph TB
    subgraph "Kubernetes"
        OP[Database Operator<br/>Controller]
        CR[Custom Resource<br/>PostgresCluster]
        
        subgraph "StatefulSet"
            P[Primary Pod<br/>+ PVC 100GB]
            R1[Replica 1<br/>+ PVC 100GB]
            R2[Replica 2<br/>+ PVC 100GB]
        end
        
        SVC_RW[Service RW<br/>→ Primary]
        SVC_RO[Service RO<br/>→ Replicas]
    end
    
    CR -->|watched by| OP
    OP -->|manages| P
    OP -->|manages| R1
    OP -->|manages| R2
    OP -->|creates| SVC_RW
    OP -->|creates| SVC_RO
    
    subgraph "Backup"
        S3[Object Storage<br/>S3/MinIO]
    end
    
    OP -->|backup WAL| S3
```

**Reconciliation loop** (giống Day 10 Kubernetes controllers):
```
1. Observe: đọc CR (desired state) và actual pods
2. Diff: primary chết? replica behind? backup outdated?
3. Act: promote replica, trigger backup, scale replicas
4. Repeat: liên tục, 24/7
```

### Managed Database là gì?

Cloud provider quản lý hoàn toàn database infrastructure:

| Dịch vụ | Provider | Database |
|---------|----------|----------|
| Amazon RDS/Aurora | AWS | PostgreSQL, MySQL, MariaDB |
| Cloud SQL | GCP | PostgreSQL, MySQL |
| Azure Database | Azure | PostgreSQL, MySQL |
| PlanetScale | Independent | MySQL (Vitess) |
| Neon | Independent | PostgreSQL (serverless) |
| Supabase | Independent | PostgreSQL |

**Managed = DBA-as-a-Service**: Provider lo backup, patching, failover, monitoring.

---

## 4. Deep Dive

### CloudNativePG Architecture

```mermaid
graph TB
    subgraph "CloudNativePG Operator"
        CTRL[CNPG Controller<br/>Reconciliation Loop]
    end
    
    subgraph "PostgreSQL Cluster"
        subgraph "Primary Instance"
            P_POD[Pod: pg-cluster-1]
            P_PG[PostgreSQL 16]
            P_PV[PVC: 100Gi<br/>gp3-io2]
        end
        
        subgraph "Replica 1"
            R1_POD[Pod: pg-cluster-2]
            R1_PG[PostgreSQL 16<br/>Streaming Replication]
            R1_PV[PVC: 100Gi]
        end
        
        subgraph "Replica 2"
            R2_POD[Pod: pg-cluster-3]
            R2_PG[PostgreSQL 16<br/>Streaming Replication]
            R2_PV[PVC: 100Gi]
        end
    end
    
    subgraph "Services"
        RW[Service: pg-cluster-rw<br/>Primary only]
        RO[Service: pg-cluster-ro<br/>Replicas only]
        R[Service: pg-cluster-r<br/>Any instance]
    end
    
    subgraph "Backup"
        BARMAN[Barman Cloud]
        S3[S3 / MinIO<br/>WAL Archive + Base Backup]
    end
    
    CTRL -->|manages| P_POD
    CTRL -->|manages| R1_POD
    CTRL -->|manages| R2_POD
    CTRL -->|creates| RW
    CTRL -->|creates| RO
    
    P_PG -->|streaming replication| R1_PG
    P_PG -->|streaming replication| R2_PG
    P_PG -->|WAL shipping| BARMAN
    BARMAN -->|archive| S3
```

**Key features**:
- **Automatic failover**: Primary chết → promote replica trong ~10-30 giây
- **WAL archiving**: Continuous backup to object storage
- **PITR**: Point-in-Time Recovery đến bất kỳ thời điểm nào
- **Rolling updates**: Upgrade PostgreSQL version không downtime
- **Connection pooling**: Built-in PgBouncer
- **Monitoring**: Prometheus metrics built-in

### Vitess Architecture (MySQL)

```mermaid
graph TB
    subgraph "Vitess Cluster"
        subgraph "VTGate Layer"
            VTG1[VTGate 1<br/>Query Router]
            VTG2[VTGate 2<br/>Query Router]
        end
        
        subgraph "Topology"
            TOPO[Topology Service<br/>etcd / ZooKeeper]
        end
        
        subgraph "Keyspace: users"
            subgraph "Shard -80"
                VTT1[VTTablet Primary]
                VTT1R[VTTablet Replica]
                M1[MySQL Primary]
                M1R[MySQL Replica]
            end
            subgraph "Shard 80-"
                VTT2[VTTablet Primary]
                VTT2R[VTTablet Replica]
                M2[MySQL Primary]
                M2R[MySQL Replica]
            end
        end
    end
    
    APP[Application]
    APP -->|MySQL protocol| VTG1
    APP -->|MySQL protocol| VTG2
    VTG1 --> VTT1
    VTG1 --> VTT2
    VTT1 --> M1
    VTT1R --> M1R
    VTT2 --> M2
    VTT2R --> M2R
    TOPO ---|cluster state| VTG1
    TOPO ---|cluster state| VTG2
```

**Key features**:
- **Horizontal sharding**: Scale MySQL vượt single-node limit
- **Online schema migration**: ALTER TABLE không lock
- **Query routing**: VTGate route query đến đúng shard
- **Backfill & resharding**: Move data giữa shards
- **YouTube-proven**: Chạy toàn bộ YouTube backend

### Storage Performance trên Kubernetes

```
Storage Stack:
┌─────────────────────────┐
│ Database Process        │ ← fsync, write-ahead log
├─────────────────────────┤
│ Filesystem (ext4/xfs)   │
├─────────────────────────┤
│ CSI Driver              │ ← overhead: API calls, attach/detach
├─────────────────────────┤
│ Network (nếu remote)    │ ← EBS, persistent disk = network storage
├─────────────────────────┤
│ Physical Disk           │ ← SSD, NVMe, HDD
└─────────────────────────┘
```

**Performance comparison**:

| Storage Type | IOPS | Latency | Cost | Use Case |
|-------------|------|---------|------|----------|
| Local NVMe | 500K+ | <0.1ms | Thấp | High-perf DB |
| EBS gp3 | 16K | 1-3ms | Trung bình | General purpose |
| EBS io2 | 64K | <1ms | Cao | Production DB |
| EFS/NFS | 10K | 3-10ms | Trung bình | Shared storage |
| Network PV (Ceph) | 20-50K | 1-5ms | Trung bình | On-premise |

**Vấn đề với network storage**: Database cần low-latency I/O, nhưng EBS/persistent disk là network storage → thêm 1-3ms latency cho mỗi disk operation.

### Failover Flow

```mermaid
sequenceDiagram
    participant App
    participant SvcRW as Service RW
    participant Primary
    participant Replica1
    participant Operator
    
    Note over Primary: Primary crashes!
    Primary->>Primary: Process dies
    
    Operator->>Operator: Detect primary unhealthy<br/>(health check fails)
    
    Note over Operator: Wait for confirmation<br/>(avoid false positive)
    
    Operator->>Replica1: Promote to primary<br/>pg_promote()
    Replica1->>Replica1: Accept writes
    
    Operator->>SvcRW: Update endpoints<br/>→ point to Replica1
    
    App->>SvcRW: Write query
    SvcRW->>Replica1: Forward to new primary
    Replica1->>App: Response OK
    
    Note over Operator: Total failover: 10-30s
```

---

## 5. Trade-offs & Best Practices ⭐

### Database on Kubernetes vs Managed Database

| Tiêu chí | DB on Kubernetes | Managed Database |
|----------|-----------------|------------------|
| **Setup complexity** | Cao (operator + storage + backup) | Thấp (click/terraform) |
| **Operational burden** | Team phải maintain | Provider maintain |
| **Cost (small)** | Thấp hơn | Cao hơn 2-3x |
| **Cost (large)** | Thấp hơn nhiều (40-60% saving) | Đắt (pay per resource) |
| **Customization** | Full control | Limited configuration |
| **Performance tuning** | Kernel, storage, pg config | Limited parameters |
| **Multi-cloud** | ✅ Portable | ❌ Vendor lock-in |
| **Backup/restore** | Tự configure | Built-in |
| **Auto failover** | Operator-dependent (10-30s) | Built-in (< 30s) |
| **Compliance** | Kiểm soát data locality | Depend on provider |
| **Risk** | Team expertise required | Provider outage risk |

### Decision Matrix theo Company Size

#### Startup (1-10 engineers, < 1TB data)

**Recommendation: Managed Database**

```
Lý do:
- Team nhỏ, không có DBA
- Focus vào product, không phải DB operations
- Chi phí managed DB < chi phí DevOps time
- Example: RDS PostgreSQL, Cloud SQL, PlanetScale
- Cost: $50-500/month
```

#### Mid-size (10-50 engineers, 1-10TB data)

**Recommendation: Managed Database, bắt đầu evaluate self-hosted**

```
Lý do:
- Có thể có 1-2 DevOps/SRE
- Managed DB cost bắt đầu đáng kể ($2K-10K/month)
- Evaluate CloudNativePG cho non-critical databases trước
- Migrate production DB sang self-hosted khi confident
```

#### Enterprise (50+ engineers, > 10TB data)

**Recommendation: Self-hosted hoặc hybrid**

```
Lý do:
- Có dedicated DBA/platform team
- Managed DB cost rất cao ($10K-100K+/month)
- CloudNativePG / Vitess / Percona operators
- Self-hosted tiết kiệm 40-60% cost
- Compliance requirements → data locality control
- Hybrid: critical DBs managed, others self-hosted
```

### Best Practices: Database on Kubernetes

```
✅ Dùng Operator (CloudNativePG, Percona, CrunchyData) — KHÔNG deploy DB manually
✅ Dedicated storage class cho databases (high IOPS, SSD)
✅ Node affinity: DB pods chạy trên dedicated nodes với local SSD
✅ Resource Guaranteed QoS: set requests = limits cho DB pods
✅ Backup automated: WAL archiving + scheduled base backups
✅ Test restore ĐỊNH KỲ (backup mà không test restore = không có backup)
✅ PodDisruptionBudget: minAvailable >= replicas - 1
✅ Monitoring: replication lag, connections, query performance, disk usage
✅ Network: dedicated NetworkPolicy cho database namespace

❌ KHÔNG dùng emptyDir cho database storage
❌ KHÔNG dùng Deployment cho database (dùng StatefulSet hoặc Operator)
❌ KHÔNG shared storage (RWX) cho database
❌ KHÔNG bỏ qua connection pooling (PgBouncer, ProxySQL)
❌ KHÔNG upgrade database version và application cùng lúc
```

### Anti-patterns

1. **"Mọi thứ trên K8s"**: Chạy production PostgreSQL trên K8s mà không có DBA experience → data loss risk
2. **Skip backup testing**: "Backup chạy mỗi ngày" nhưng chưa bao giờ test restore
3. **Dùng default storage**: gp2/standard StorageClass cho database → I/O throttling
4. **Ignore connection pooling**: 1000 pods connect trực tiếp đến DB → connection exhaustion
5. **Single replica**: Primary-only setup "vì staging" → primary chết = downtime

---

## 6. Performance & Scalability ⭐

### Storage Performance Impact

```
Benchmark: PostgreSQL pgbench
Hardware: 4 vCPU, 16GB RAM, 100GB storage

Storage Type          | TPS    | Latency (p99) | Notes
─────────────────────┼────────┼───────────────┼──────────────
Local NVMe            | 15,000 | 2ms           | Best performance
EBS io2 (10K IOPS)    | 8,500  | 5ms           | Good for production
EBS gp3 (3K IOPS)     | 3,200  | 15ms          | Acceptable for dev/staging
EBS gp2 (baseline)    | 1,500  | 30ms          | Avoid for production DB
Network PV (Ceph)     | 4,000  | 10ms          | Depends on network
```

### Connection Pooling

```
Vấn đề:
- PostgreSQL fork per connection → ~5MB RAM per connection
- 100 pods × 10 connections = 1000 connections → 5GB RAM chỉ cho connections
- Max connections ≠ performance → connection overhead

Giải pháp: PgBouncer
┌──────────┐     ┌───────────┐     ┌─────────────┐
│ 100 pods │ ──→ │ PgBouncer │ ──→ │ PostgreSQL  │
│ 1000 conn│     │ 50 conn   │     │ 50 active   │
└──────────┘     └───────────┘     └─────────────┘

CloudNativePG PgBouncer:
spec:
  instances: 3
  postgresql:
    parameters:
      max_connections: "200"
  pgbouncer:
    poolSize: 50
    defaultPoolMode: transaction
```

### Scaling Strategies

#### Read Scaling (thêm replicas)

```yaml
# CloudNativePG: tăng replicas
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-cluster
spec:
  instances: 5  # 1 primary + 4 replicas
  
  # Application dùng read service
  # pg-cluster-ro → load balance across replicas
```

#### Write Scaling (sharding)

```
Khi nào cần sharding:
- Single node write throughput không đủ (> 50K TPS)
- Data > 1TB và growing fast
- Multi-region write requirements

Tool cho sharding:
- Vitess (MySQL): horizontal sharding
- Citus (PostgreSQL): distributed PostgreSQL
- CockroachDB: distributed SQL (built-in sharding)
```

### Bottleneck Analysis

```
1. Disk I/O bottleneck
   Symptom: iowait cao, query chậm
   Debug: iostat -x 1, kubectl top pod
   Fix: upgrade StorageClass (gp3 → io2), move to local NVMe

2. Connection exhaustion
   Symptom: "too many clients" errors
   Debug: SELECT count(*) FROM pg_stat_activity
   Fix: PgBouncer, giảm max_connections per pod

3. Replication lag
   Symptom: read-after-write inconsistency
   Debug: SELECT pg_last_wal_receive_lsn() - pg_last_wal_replay_lsn()
   Fix: dedicated network, faster storage for replicas

4. Memory pressure
   Symptom: OOMKilled, swap, slow queries
   Debug: kubectl describe pod, pg_stat_bgwriter
   Fix: tune shared_buffers (25% RAM), work_mem, effective_cache_size
```

---

## 7. Security & Reliability Considerations

### Security

#### Encryption at Rest

```yaml
# CloudNativePG: encrypted storage
spec:
  storage:
    storageClass: encrypted-gp3  # StorageClass with encryption
    size: 100Gi
```

#### Encryption in Transit

```yaml
# CloudNativePG: TLS cho client connections
spec:
  postgresql:
    parameters:
      ssl: "on"
      ssl_min_protocol_version: "TLSv1.3"
  certificates:
    serverTLSSecret: pg-server-cert
    serverCASecret: pg-ca-cert
```

#### Access Control

```yaml
# CloudNativePG: pg_hba.conf
spec:
  postgresql:
    pg_hba:
    - host all all 10.244.0.0/16 scram-sha-256  # Pod network only
    - host all all 0.0.0.0/0 reject              # Deny external
```

#### NetworkPolicy cho Database

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-isolation
  namespace: database
spec:
  podSelector:
    matchLabels:
      app: postgresql
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          access-database: "true"
    ports:
    - port: 5432
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql  # Replication giữa các instances
    ports:
    - port: 5432
  - to:  # Backup to S3
    - ipBlock:
        cidr: 0.0.0.0/0
    ports:
    - port: 443
```

### Reliability

#### Backup Strategy (3-2-1 Rule)

```
3 copies: primary + replica + backup
2 media types: PV (disk) + Object Storage (S3)
1 offsite: backup ở region/account khác
```

```yaml
# CloudNativePG Backup
spec:
  backup:
    barmanObjectStore:
      destinationPath: s3://db-backups/pg-cluster
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
  
  # Scheduled backup
  scheduledBackups:
  - name: daily-backup
    schedule: "0 2 * * *"  # 2 AM daily
    backupOwnerReference: self
```

#### PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: pg-cluster-pdb
spec:
  minAvailable: 2  # Luôn có ít nhất 2 instances (1 primary + 1 replica)
  selector:
    matchLabels:
      cnpg.io/cluster: pg-cluster
```

---

## 8. Hands-on Example

### Deploy CloudNativePG trên kind

#### Bước 1: Tạo cluster

```bash
cat <<EOF | kind create cluster --name db-lab --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
EOF
```

#### Bước 2: Cài CloudNativePG Operator

```bash
# Install operator
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.1.yaml

# Wait for operator ready
kubectl wait --for=condition=Available deployment/cnpg-controller-manager \
  -n cnpg-system --timeout=120s

# Verify
kubectl get pods -n cnpg-system
```

**Expected output**:
```
NAME                                     READY   STATUS    RESTARTS   AGE
cnpg-controller-manager-xxx-yyy          1/1     Running   0          30s
```

#### Bước 3: Deploy PostgreSQL Cluster

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: database
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-demo
  namespace: database
spec:
  instances: 3
  
  postgresql:
    parameters:
      max_connections: "100"
      shared_buffers: "256MB"
      effective_cache_size: "512MB"
      log_statement: "ddl"
      log_min_duration_statement: "1000"
  
  bootstrap:
    initdb:
      database: appdb
      owner: appuser
  
  storage:
    size: 5Gi
  
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 500m
      memory: 1Gi
  
  monitoring:
    enablePodMonitor: false
EOF

# Wait for cluster ready
kubectl wait --for=condition=Ready cluster/pg-demo -n database --timeout=300s
```

#### Bước 4: Verify Cluster

```bash
# Check cluster status
kubectl get cluster pg-demo -n database

# Check pods (1 primary + 2 replicas)
kubectl get pods -n database -l cnpg.io/cluster=pg-demo

# Check services
kubectl get svc -n database

# Check which pod is primary
kubectl get pods -n database -l cnpg.io/cluster=pg-demo \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.role}{"\n"}{end}'
```

**Expected output**:
```
pg-demo-1    primary
pg-demo-2    replica
pg-demo-3    replica
```

#### Bước 5: Connect và test

```bash
# Get password
export PGPASSWORD=$(kubectl get secret pg-demo-app -n database \
  -o jsonpath='{.data.password}' | base64 -d)

# Connect via port-forward
kubectl port-forward svc/pg-demo-rw -n database 5432:5432 &

# Test write (to primary via -rw service)
psql -h localhost -U appuser -d appdb -c "
  CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
  );
  INSERT INTO products (name, price) VALUES 
    ('Widget A', 29.99),
    ('Widget B', 49.99),
    ('Widget C', 99.99);
  SELECT * FROM products;
"

# Test read (from replica via -ro service)
kubectl port-forward svc/pg-demo-ro -n database 5433:5432 &

psql -h localhost -p 5433 -U appuser -d appdb -c "SELECT * FROM products;"
```

#### Bước 6: Test Failover

```bash
# Identify primary
kubectl get pods -n database -l role=primary

# Delete primary pod (simulate crash)
kubectl delete pod pg-demo-1 -n database

# Watch failover
kubectl get pods -n database -w

# After ~30 seconds, check new primary
kubectl get pods -n database -l cnpg.io/cluster=pg-demo \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.role}{"\n"}{end}'
```

**Expected output** (after failover):
```
pg-demo-1    replica    (recreated, now replica)
pg-demo-2    primary    (promoted!)
pg-demo-3    replica
```

#### Bước 7: Verify data intact

```bash
# Connect to new primary
psql -h localhost -U appuser -d appdb -c "SELECT * FROM products;"
```

Data vẫn giữ nguyên — failover thành công!

#### Cleanup

```bash
kubectl delete namespace database
kubectl delete -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.1.yaml
kind delete cluster --name db-lab
```

---

## 9. Common Pitfalls & Debugging

### Lỗi thường gặp

| Lỗi | Triệu chứng | Nguyên nhân | Fix |
|------|-------------|-------------|-----|
| Pod Pending | Pod stuck Pending | PVC not bound, insufficient storage | Check StorageClass, PV availability |
| Replication lag | Read-after-write stale | Network slow, replica overloaded | Monitor `pg_stat_replication`, upgrade storage |
| Backup failure | No recent backup | S3 credentials expired, storage full | Check backup CronJob logs, credentials |
| Failover loop | Primary keeps changing | Network partition, split brain | Check cluster events, node connectivity |
| OOMKilled | Pod restarted | shared_buffers + work_mem > pod memory | Tune PostgreSQL memory params |
| Slow queries after failover | Performance drop | New primary was cold (no cache) | Pre-warm: `pg_prewarm` extension |

### Debug Flow

```bash
# 1. Check cluster status
kubectl get cluster <name> -n <ns> -o yaml | grep -A10 status

# 2. Check pod events
kubectl describe pod <pod> -n <ns>

# 3. Check PostgreSQL logs
kubectl logs <pod> -n <ns>

# 4. Check replication status
kubectl exec <primary-pod> -n <ns> -- psql -U postgres -c "
  SELECT client_addr, state, sent_lsn, write_lsn, replay_lsn, 
         sent_lsn - replay_lsn AS replication_lag
  FROM pg_stat_replication;
"

# 5. Check storage
kubectl get pvc -n <ns>
kubectl describe pvc <pvc> -n <ns>

# 6. Check operator logs
kubectl logs deploy/cnpg-controller-manager -n cnpg-system
```

### Production Case Study 1: EBS Volume Detach Storm

#### Context
E-commerce platform, PostgreSQL trên EKS, CloudNativePG, 3 instances, EBS gp3.

#### Symptom
- 2:30 AM: All 3 PostgreSQL pods restart đồng thời
- Application errors: "connection refused" kéo dài 5 phút
- After restart: data inconsistency (3 transactions lost)

#### Investigation
```bash
kubectl describe pod pg-cluster-1 -n database
# Events: "Multi-Attach error for volume"

kubectl get events -n database --sort-by='.lastTimestamp'
# Node maintenance → pods rescheduled → EBS volumes stuck in "detaching"
```

#### Root Cause
- AWS thực hiện node maintenance (reboot)
- 3 pods trên cùng 1 node (không có anti-affinity)
- EBS volumes cần 1-3 phút detach từ old node → attach to new node
- Trong thời gian đó: pods Pending, database down

#### Fix
```yaml
# 1. Anti-affinity: mỗi instance trên node khác nhau
spec:
  affinity:
    enablePodAntiAffinity: true
    topologyKey: kubernetes.io/hostname

# 2. PDB: luôn giữ ít nhất 2 instances
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: pg-cluster-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      cnpg.io/cluster: pg-cluster
```

### Production Case Study 2: Connection Pool Exhaustion

#### Context
SaaS platform, 50 microservices, PostgreSQL managed (RDS), r6g.xlarge.

#### Symptom
- Peak hours: random services reportor "too many clients" errors
- Database CPU chỉ 30% nhưng connections = 500 (max)
- Application timeout tăng từ 50ms lên 10s

#### Root Cause
- 50 services × default 10 connections = 500 connections
- PostgreSQL max_connections = 500
- Nhiều connections idle nhưng giữ slot
- Mỗi connection tốn ~5-10MB server RAM → 5GB chỉ cho connections

#### Fix
```
1. Deploy PgBouncer trước PostgreSQL
   - 500 app connections → PgBouncer → 50 DB connections
   - Mode: transaction (return connection after each transaction)
   
2. Giảm pool size per service
   - Core services: 5 connections
   - Background workers: 2 connections
   - Total: 50 services × 3 avg = 150 connections
   
3. Monitor
   - Grafana dashboard: active vs idle connections
   - Alert: connections > 80% max
```

### Production Case Study 3: Backup "Worked" But Restore Failed

#### Context
FinTech startup, PostgreSQL on K8s (CloudNativePG), daily backups to S3.

#### Symptom
- Accidental `DROP TABLE transactions` (senior dev ran migration on prod)
- Attempted restore from backup → FAILED
- Error: "could not find WAL segment" → PITR not possible

#### Root Cause
- WAL archiving was configured but S3 bucket had lifecycle policy: delete after 7 days
- Base backup was weekly → WAL files between backups were deleted
- PITR needs: base backup + ALL WAL files since that backup
- Gap in WAL → cannot replay to desired point

#### Fix
```yaml
# 1. S3 lifecycle: match retention policy
spec:
  backup:
    retentionPolicy: "30d"
    barmanObjectStore:
      # S3 bucket lifecycle: 60 days (2x retention for safety)

# 2. Regular restore tests
# CronJob/scheduled task: monthly restore test to staging
# Verify:
#   a) Base backup restores
#   b) PITR to specific timestamp works
#   c) Data integrity verified (row counts, checksums)

# 3. Pre-delete safety
# Prevent accidental drops:
# - Read-only user for most services
# - DDL only via migration pipeline
# - Enable statement_timeout for DDL
```

#### Lesson Learned
**"Backup mà không test restore = không có backup"** — phải test restore ít nhất monthly.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 46: Service Mesh & Zero-trust

- Service mesh mTLS ảnh hưởng database connections:
  - Database protocol (PostgreSQL wire protocol) qua sidecar proxy
  - Cần exclude database pods khỏi mesh hoặc configure đúng protocol
  - `config.linkerd.io/skip-outbound-ports: "5432"` nếu DB ngoài mesh
- Zero-trust + database: NetworkPolicy isolate database namespace (Day 20)

### Bài sau — Day 48: Multi-region, Disaster Recovery, RPO/RTO

- Database là critical nhất trong DR strategy
- RPO phụ thuộc trực tiếp vào backup strategy (WAL archiving → RPO ~0)
- RTO phụ thuộc vào restore speed (base backup size → restore time)
- Multi-region database replication → data consistency trade-offs
- Read replicas cross-region cho read-heavy workloads

### Kiến thức tái sử dụng

- **Storage** (Day 15): PV, PVC, StorageClass — nền tảng cho DB storage
- **StatefulSet** (Day 11): Stable identity cho database pods
- **Resource management** (Day 18): Guaranteed QoS cho database pods
- **Backup concept** (Day 23): Velero vs database-native backup
- **Observability** (Day 38-42): Database metrics, logs, query tracing

---

## 11. Tài liệu tham khảo

### Must-read
- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/) — official docs
- [Kubernetes Patterns: Stateful Service](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) — K8s stateful concepts
- [DoK (Data on Kubernetes) Community](https://dok.community/) — community resources

### Nice-to-have
- [Vitess.io](https://vitess.io/docs/) — MySQL horizontal scaling
- [Percona Operators](https://www.percona.com/software/percona-operators) — MySQL, MongoDB, PostgreSQL
- [CrunchyData PGO](https://access.crunchydata.com/documentation/postgres-operator/latest/) — alternative PostgreSQL operator

### Deep-dive
- **Book**: "Database Reliability Engineering" (Laine Campbell, Charity Majors)
- **Blog**: [Postgres on Kubernetes at GitLab](https://about.gitlab.com/blog/) — GitLab's journey
- **Talk**: [Running Databases on Kubernetes](https://www.youtube.com/results?search_query=running+databases+on+kubernetes+kubecon) — KubeCon talks
- [CloudNativePG vs CrunchyData PGO comparison](https://cloudnative-pg.io/documentation/current/operator_compared/) — operator comparison

