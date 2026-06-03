# Day 47: Bài tập — Database on Kubernetes vs Managed Database

---

## Bài 1: Easy — Deploy CloudNativePG và Test Basic Operations

### Context

Bạn là DevOps engineer được giao nhiệm vụ evaluate CloudNativePG cho staging environment. Team muốn biết liệu có thể chạy PostgreSQL trên Kubernetes thay vì dùng RDS (đang tốn $800/tháng cho staging).

### Yêu cầu

1. Tạo kind cluster với 3 worker nodes
2. Cài CloudNativePG operator
3. Deploy PostgreSQL cluster 3 instances (1 primary + 2 replicas)
4. Tạo database, table, insert data
5. Verify read từ replica hoạt động
6. Test failover: kill primary pod, verify tự động promote replica
7. Verify data intact sau failover

### Expected Outcome

- PostgreSQL cluster 3 instances healthy
- Data write qua `-rw` service, read qua `-ro` service
- Failover hoàn thành trong < 60 giây
- Data không bị mất sau failover

### Hint

- `kubectl get cluster -n database` để xem cluster status
- `kubectl get pods -l role=primary -n database` để xem primary
- Sau khi delete primary pod, watch events: `kubectl get pods -n database -w`

### Acceptance Criteria

- [ ] CloudNativePG operator running
- [ ] 3 PostgreSQL pods running (1 primary, 2 replicas)
- [ ] Data inserted via `-rw` service thành công
- [ ] Data read via `-ro` service thành công
- [ ] Primary pod deleted → new primary promoted < 60s
- [ ] Data intact sau failover

### Bonus Challenge

- Đo thời gian failover chính xác (từ delete pod đến new primary ready)
- So sánh resource usage: 3 PostgreSQL pods tốn bao nhiêu CPU/memory

---

## Bài 2: Medium — Backup/Restore Strategy và Monitoring

### Context

Team đã quyết định dùng CloudNativePG cho staging. Trước khi production, cần implement backup strategy và monitoring. Manager yêu cầu RPO < 5 phút và RTO < 15 phút.

### Yêu cầu

1. Deploy PostgreSQL cluster với backup configuration (MinIO làm S3-compatible storage)
2. Configure:
   - WAL archiving (continuous backup)
   - Scheduled base backup (daily)
   - Retention policy (7 ngày)
3. Insert test data (1000 rows)
4. Trigger manual backup
5. Simulate data loss: `DROP TABLE`
6. Restore từ backup (PITR đến thời điểm trước DROP)
7. Verify data restored đúng
8. Setup monitoring:
   - Replication lag metric
   - Connection count
   - Backup status

### Expected Outcome

- Backup tự động hoạt động
- PITR restore thành công — data recovered
- Monitoring dashboard/queries cho PostgreSQL metrics

### Hint

- Deploy MinIO trước: `helm install minio minio/minio`
- CloudNativePG backup config: `spec.backup.barmanObjectStore`
- Restore: tạo Cluster mới với `spec.bootstrap.recovery`
- PostgreSQL metrics: `pg_stat_replication`, `pg_stat_activity`

### Acceptance Criteria

- [ ] MinIO running, accessible
- [ ] WAL archiving configured và active
- [ ] Manual backup completed successfully
- [ ] Data (1000 rows) inserted và verified
- [ ] DROP TABLE simulated
- [ ] PITR restore to pre-DROP timestamp
- [ ] Restored data verified (1000 rows intact)
- [ ] 3 monitoring queries working (replication lag, connections, backup age)

### Bonus Challenge

- Tạo restore test automation script (monthly restore verification)
- Calculate actual RPO/RTO từ test results

---

## Bài 3: Hard — Decision Matrix và Production-ready Database Architecture

### Context

Bạn là Senior DevOps Engineer tại một e-commerce platform. CTO yêu cầu thiết kế database architecture cho platform mới với yêu cầu:

- 5 microservices, mỗi service cần PostgreSQL riêng
- Total data: ~500GB, growing 50GB/year
- Peak traffic: 5K TPS writes, 20K TPS reads
- SLA: 99.95% availability
- Compliance: data phải ở region cụ thể
- Budget: optimize cost nhưng không compromise reliability
- Team: 3 DevOps engineers, không có dedicated DBA

### Yêu cầu

1. **Decision Matrix**: Tạo chi tiết decision matrix so sánh:
   - CloudNativePG on EKS
   - Amazon RDS PostgreSQL
   - Amazon Aurora PostgreSQL
   - Hybrid (critical DBs on RDS, non-critical on K8s)
   
   Tiêu chí: cost, operations effort, performance, reliability, compliance, migration risk

2. **Architecture Design**: Cho phương án được chọn, thiết kế:
   - Database topology per service (primary/replica count)
   - Storage strategy (StorageClass, IOPS)
   - Backup strategy (RPO/RTO per database)
   - Connection pooling architecture
   - Monitoring và alerting
   - DR plan

3. **Implementation Skeleton**: Deploy ít nhất 2 databases trên kind:
   - Service A: critical (high availability, strict backup)
   - Service B: non-critical (single instance, basic backup)
   - Connection pooling (PgBouncer)
   - NetworkPolicy isolation

4. **Cost Analysis**: So sánh monthly cost cho 3 options

### Expected Outcome

- Decision matrix document với clear recommendation
- Architecture diagram (mermaid)
- Working 2-database setup trên kind
- Cost comparison spreadsheet/table
- Production readiness checklist

### Hint

- AWS RDS pricing: check `aws.amazon.com/rds/pricing`
- CloudNativePG trên EKS: compute cost + EBS cost
- PgBouncer: `spec.pgbouncer` trong CloudNativePG
- Priority: critical service = Guaranteed QoS, non-critical = Burstable

### Acceptance Criteria

- [ ] Decision matrix hoàn chỉnh (≥ 8 tiêu chí, 4 options)
- [ ] Clear recommendation với justification
- [ ] Architecture diagram cho recommended option
- [ ] 2 PostgreSQL clusters deployed (critical + non-critical)
- [ ] NetworkPolicy isolate database namespace
- [ ] PgBouncer configured cho critical database
- [ ] Cost comparison table (monthly estimates)
- [ ] Production readiness checklist (≥ 15 items)

### Bonus Challenge

- Implement Prometheus monitoring cho cả 2 databases
- Design blue-green database migration strategy
- Create runbook cho top 5 database incidents

---

## Solutions

<details>
<summary>Solution Bài 1: Deploy CloudNativePG</summary>

```bash
# Cluster
cat <<EOF | kind create cluster --name db-easy --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
EOF

# Install operator
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.1.yaml

kubectl wait --for=condition=Available deployment/cnpg-controller-manager \
  -n cnpg-system --timeout=120s

# Deploy cluster
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: database
---
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-easy
  namespace: database
spec:
  instances: 3
  postgresql:
    parameters:
      max_connections: "100"
      shared_buffers: "128MB"
  bootstrap:
    initdb:
      database: testdb
      owner: testuser
  storage:
    size: 2Gi
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
EOF

kubectl wait --for=condition=Ready cluster/pg-easy -n database --timeout=300s

# Verify
kubectl get pods -n database -l cnpg.io/cluster=pg-easy

# Get password
export PGPASSWORD=$(kubectl get secret pg-easy-app -n database \
  -o jsonpath='{.data.password}' | base64 -d)

# Write test
kubectl port-forward svc/pg-easy-rw -n database 5432:5432 &
sleep 2
psql -h localhost -U testuser -d testdb -c "
  CREATE TABLE test (id SERIAL, data TEXT);
  INSERT INTO test (data) SELECT 'row-' || g FROM generate_series(1,100) g;
  SELECT count(*) FROM test;
"

# Read from replica
kubectl port-forward svc/pg-easy-ro -n database 5433:5432 &
sleep 2
psql -h localhost -p 5433 -U testuser -d testdb -c "SELECT count(*) FROM test;"

# Failover test
echo "=== Failover Test ==="
PRIMARY=$(kubectl get pods -n database -l role=primary -o name)
echo "Current primary: $PRIMARY"
START=$(date +%s)

kubectl delete $PRIMARY -n database

echo "Waiting for new primary..."
sleep 5
while ! kubectl get pods -n database -l role=primary 2>/dev/null | grep Running; do
  sleep 2
done

END=$(date +%s)
echo "Failover completed in $((END - START)) seconds"

# Verify data
psql -h localhost -U testuser -d testdb -c "SELECT count(*) FROM test;"
# Expected: 100

# Cleanup
kill %1 %2 2>/dev/null
kubectl delete namespace database
kind delete cluster --name db-easy
```

</details>

<details>
<summary>Solution Bài 2: Backup/Restore Strategy</summary>

```bash
kind create cluster --name db-medium

# Install CNPG operator
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.1.yaml
kubectl wait --for=condition=Available deployment/cnpg-controller-manager \
  -n cnpg-system --timeout=120s

kubectl create namespace database

# Deploy MinIO for S3-compatible backup
cat <<'EOF' | kubectl apply -n database -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
      - name: minio
        image: minio/minio:latest
        args: ["server", "/data", "--console-address", ":9001"]
        env:
        - name: MINIO_ROOT_USER
          value: minioadmin
        - name: MINIO_ROOT_PASSWORD
          value: minioadmin123
        ports:
        - containerPort: 9000
        - containerPort: 9001
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
      volumes:
      - name: data
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: minio
spec:
  selector:
    app: minio
  ports:
  - name: api
    port: 9000
  - name: console
    port: 9001
EOF

kubectl wait --for=condition=Available deployment/minio -n database --timeout=120s

# Create MinIO bucket
kubectl exec -n database deploy/minio -- \
  mc alias set local http://localhost:9000 minioadmin minioadmin123
kubectl exec -n database deploy/minio -- \
  mc mb local/pg-backups

# Create S3 credentials secret
cat <<'EOF' | kubectl apply -n database -f -
apiVersion: v1
kind: Secret
metadata:
  name: s3-creds
type: Opaque
stringData:
  ACCESS_KEY_ID: minioadmin
  SECRET_ACCESS_KEY: minioadmin123
EOF

# Deploy PostgreSQL with backup
cat <<'EOF' | kubectl apply -n database -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-backup
spec:
  instances: 3
  postgresql:
    parameters:
      max_connections: "100"
      shared_buffers: "128MB"
  bootstrap:
    initdb:
      database: appdb
      owner: appuser
  storage:
    size: 2Gi
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi
  backup:
    barmanObjectStore:
      destinationPath: s3://pg-backups/pg-backup
      endpointURL: http://minio:9000
      s3Credentials:
        accessKeyId:
          name: s3-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-creds
          key: SECRET_ACCESS_KEY
    retentionPolicy: "7d"
EOF

kubectl wait --for=condition=Ready cluster/pg-backup -n database --timeout=300s

# Insert 1000 rows
export PGPASSWORD=$(kubectl get secret pg-backup-app -n database \
  -o jsonpath='{.data.password}' | base64 -d)
kubectl port-forward svc/pg-backup-rw -n database 5432:5432 &
sleep 2

psql -h localhost -U appuser -d appdb -c "
  CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer TEXT,
    amount DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
  );
  INSERT INTO orders (customer, amount)
  SELECT 'customer-' || g, (random() * 1000)::decimal(10,2)
  FROM generate_series(1,1000) g;
  SELECT count(*) FROM orders;
"

# Record timestamp before DROP
RESTORE_POINT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Restore target: $RESTORE_POINT"
sleep 5

# Trigger manual backup
cat <<'EOF' | kubectl apply -n database -f -
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: manual-backup
spec:
  method: barmanObjectStore
  cluster:
    name: pg-backup
EOF

# Wait for backup
kubectl wait --for=condition=Completed backup/manual-backup -n database --timeout=300s

# Simulate disaster (DROP TABLE after backup)
sleep 5
psql -h localhost -U appuser -d appdb -c "DROP TABLE orders;"
psql -h localhost -U appuser -d appdb -c "SELECT count(*) FROM orders;"
# Expected: ERROR - table does not exist

# Restore via PITR
cat <<EOF | kubectl apply -n database -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-restored
  namespace: database
spec:
  instances: 1
  storage:
    size: 2Gi
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
  bootstrap:
    recovery:
      source: pg-backup
      recoveryTarget:
        targetTime: "$RESTORE_POINT"
  externalClusters:
  - name: pg-backup
    barmanObjectStore:
      destinationPath: s3://pg-backups/pg-backup
      endpointURL: http://minio:9000
      s3Credentials:
        accessKeyId:
          name: s3-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-creds
          key: SECRET_ACCESS_KEY
EOF

kubectl wait --for=condition=Ready cluster/pg-restored -n database --timeout=300s

# Verify restored data
kubectl port-forward svc/pg-restored-rw -n database 5434:5432 &
sleep 2
export PGPASSWORD=$(kubectl get secret pg-restored-app -n database \
  -o jsonpath='{.data.password}' | base64 -d)
psql -h localhost -p 5434 -U appuser -d appdb -c "SELECT count(*) FROM orders;"
# Expected: 1000

# Monitoring queries
psql -h localhost -U appuser -d appdb -c "
  -- Replication lag
  SELECT client_addr, state, 
         pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replication_lag_bytes
  FROM pg_stat_replication;
  
  -- Connection count
  SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
"

# Cleanup
kill %1 %2 2>/dev/null
kubectl delete namespace database
kind delete cluster --name db-medium
```

</details>

<details>
<summary>Solution Bài 3: Decision Matrix và Architecture (Outline)</summary>

### Decision Matrix

| Tiêu chí (Weight) | CloudNativePG on EKS | RDS PostgreSQL | Aurora PostgreSQL | Hybrid |
|---|---|---|---|---|
| **Cost/month** (20%) | ~$1,200 | ~$2,800 | ~$3,500 | ~$2,000 |
| **Operations effort** (20%) | Cao (team chạy) | Thấp (AWS managed) | Rất thấp | Trung bình |
| **Performance** (15%) | Tốt (tunable) | Tốt | Rất tốt (Aurora) | Tốt |
| **Reliability** (15%) | Operator-dependent | 99.95% SLA | 99.99% SLA | Mixed |
| **Compliance** (10%) | Full control | AWS region | AWS region | Flexible |
| **Migration risk** (10%) | Thấp (standard PG) | Thấp | Medium (Aurora) | Thấp |
| **Team expertise** (10%) | Cần K8s + DB skills | Cần AWS skills | Cần AWS skills | Both |
| **Score** | 72/100 | 78/100 | 75/100 | **80/100** |

### Recommendation: Hybrid

```
Critical databases (user, payment, order):
→ RDS PostgreSQL Multi-AZ
  - 99.95% SLA guarantee
  - Automated backup/PITR
  - Team không phải lo operations
  - Cost justified by business criticality

Non-critical databases (analytics, config, temp):
→ CloudNativePG on EKS
  - Tiết kiệm ~60% vs RDS
  - Team practice K8s DB operations
  - Acceptable risk cho non-critical data
  - Migration path to K8s khi team mature
```

### Architecture Diagram

```mermaid
graph TB
    subgraph "EKS Cluster"
        subgraph "Application Namespace"
            API[API Gateway]
            USER_SVC[User Service]
            PAY_SVC[Payment Service]
            ANALYTICS[Analytics Service]
            CONFIG_SVC[Config Service]
        end
        
        subgraph "Database Namespace (K8s)"
            subgraph "CloudNativePG"
                AN_PG[Analytics DB<br/>1 primary + 1 replica]
                CF_PG[Config DB<br/>1 instance]
            end
            PGBOUNCER[PgBouncer]
        end
    end
    
    subgraph "AWS Managed"
        subgraph "RDS Multi-AZ"
            USER_RDS[User DB<br/>db.r6g.large]
            PAY_RDS[Payment DB<br/>db.r6g.large]
        end
    end
    
    USER_SVC --> USER_RDS
    PAY_SVC --> PAY_RDS
    ANALYTICS --> PGBOUNCER --> AN_PG
    CONFIG_SVC --> CF_PG
```

### Cost Comparison

```
Option A: All RDS
- 5 × db.r6g.large Multi-AZ = 5 × $560 = $2,800/month
- Storage: 500GB × $0.115 = $57.50
- Backup: $50
- Total: ~$2,907/month

Option B: All CloudNativePG on EKS
- 5 clusters × 3 instances × m5.large spot = ~$600/month (compute)
- 15 × 100GB gp3 = $120/month (storage)
- S3 backup = $30/month
- Total: ~$750/month (but higher ops cost)

Option C: Hybrid (recommended)
- 2 × RDS Multi-AZ (critical) = $1,120
- 3 × CloudNativePG (non-critical) = ~$300
- Storage + backup = ~$100
- Total: ~$1,520/month
- Savings vs all-RDS: 48%
```

</details>

