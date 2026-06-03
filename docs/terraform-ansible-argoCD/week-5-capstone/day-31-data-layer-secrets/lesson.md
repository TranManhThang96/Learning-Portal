# Day 31 — Data Layer: PostgreSQL, Redis, Secrets

> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Day 30 (kind/EKS cluster + IAM roles + ECR repos)
> **Output:** PostgreSQL + Redis deployed + secrets in ESO/ASM + connection string management

---

## 1. Mục tiêu ngày học

- Phân biệt PostgreSQL via Helm (in-cluster) vs RDS managed database — trade-offs về operation, cost, backup, HA
- Phân biệt Redis via Helm (in-cluster) vs ElastiCache managed cache — trade-offs về cluster mode, persistence, scaling
- Thiết kế backup strategy: automated snapshot (RDS), WAL archiving, Point-in-time Recovery, cross-region backup
- Quản lý secret: Kubernetes Secret thường vs External Secrets Operator vs AWS Secrets Manager — biết khi nào dùng cái nào
- Quản lý connection string lifecycle: generation, rotation, injection vào pod qua environment variable hoặc volume mount
- Thực hành: Mode A deploy PostgreSQL + Redis bằng Helm bitnami; Mode B deploy RDS + ElastiCache bằng Terraform; cả 2 mode đều dùng ESO để inject secrets

---

## 2. Bối cảnh thực tế

### Chuyện thật mà production team hay gặp

**Pain point 1: Secret trong Git**

```
git commit -m "fix config"
  → git push
  → 30 phút sau: "DB_PASSWORD was exposed in public repo"
  → Rotate password → Update all environments → 2 giờ mất
```

Team chưa dùng ESO: hoặc hardcode secret trong ConfigMap (rất phổ biến), hoặc dùng Kubernetes Secret nhưng không bao giờ rotate. Kubernetes Secret là base64-encoded, không encrypted at rest theo mặc định (phải enable encryption at rest).

**Pain point 2: Connection string không rotation**

```
Setup: 2023-01-01
  → DB password never rotated
  → 2024-06: compliance audit → fail
  → Manual rotation → 5 environment update → 3 ngày
  → Root cause: không có automated secret rotation
```

**Pain point 3: PostgreSQL local trong Kubernetes không scale được**

```
Helm install postgresql trong kind cluster
  → 1 pod, 1 PVC
  → Replication: không có (bitnami/postgresql single replica)
  → Backup: phải tự viết script
  → Connection limit: 100 (default)
  → Khi workload tăng: pod OOM → crash
```

**Pain point 4: Backup không test restore**

```
Nightly backup chạy 365 ngày
  → Ngày 366: cần restore
  → Backup corrupted: không ai phát hiện
  → 4 giờ debug → kết luận: backup script có bug từ ngày 1
```

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 PostgreSQL: Helm vs RDS

```
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL Deployment Options                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Option A: Helm bitnami/postgresql (in-cluster)                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  kind/EKS Node                                            │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  postgresql-0  (StatefulSet)                       │  │   │
│  │  │  PVC: 8Gi gp3                                       │  │   │
│  │  │  Primary: accepts writes + reads                    │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │  Backup: pg_dump cron job (do you implement?)           │   │
│  │  HA: ❌ (single replica by default)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Option B: AWS RDS PostgreSQL (managed)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │   │
│  │  │  Primary DB  │───▶│  Standby DB  │    │  Read Replica │  │   │
│  │  │  (AZ-1)     │ SYNC │  (AZ-2)     │    │  (AZ-3)     │  │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │   │
│  │  Automated backup: daily snapshot + WAL archiving       │   │
│  │  Point-in-time recovery: up to last 35 days             │   │
│  │  HA: ✅ Multi-AZ automatic failover                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**PostgreSQL Helm chart (bitnami/postgresql):**

```yaml
# values.yaml (fragment)
architecture: replication  # standalone | replication
auth:
  username: capstone_user
  database: capstone_db
  password: ""           # generate automatically
  existingSecret: ""     # hoặc dùng secretRef
primary:
  persistence:
    size: 10Gi
    storageClass: gp3
  resources:
    requests: { cpu: "250m", memory: "512Mi" }
    limits:   { cpu: "1", memory: "1Gi" }
  podAnnotations:
    # IRSA annotation nếu dùng AWS (đọc secret từ ASM)
replica:
  replicaCount: 1       # read replica
  persistence:
    size: 10Gi
```

**RDS PostgreSQL (Terraform):**

```hcl
# terraform/modules/rds/main.tf (fragment)
resource "aws_db_subnet_group" "main" {
  name       = "capstone-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "capstone-db-subnet" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "capstone-${var.env}-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.instance_class  # db.t3.medium

  # Multi-AZ
  multi_az               = var.env == "prod" ? true : false
  db_name                = replace(var.env, "-", "_")
  username               = "capstone_admin"
  password               = random_password.db_password.result
  manage_master_user_password = true  # AWS quản lý password

  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]

  # Storage
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type         = "gp3"
  storage_encrypted    = true

  # Backup (tự động)
  backup_retention_period = var.env == "prod" ? 30 : 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"

  # Public access? KHÔNG — always private
  publicly_accessible = false

  # Performance insights
  monitoring_interval = 60
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Environment = var.env
    Project     = "capstone"
  }
}

resource "random_password" "db_password" {
  length  = 32
  special = true
}
```

---

### 3.2 Redis: Helm vs ElastiCache

```
┌─────────────────────────────────────────────────────────────────┐
│                 Redis Deployment Options                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Option A: Helm bitnami/redis (in-cluster)                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  redis-master-0  (StatefulSet)                          │   │
│  │  redis-replica-0 (Deployment, read-only)                │   │
│  │  ConfigMap: maxmemory-policy=allkeys-lru                │   │
│  │  PVC: 5Gi ( persistence enabled = true)                │   │
│  │  Password: auto-generated in Secret                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Option B: AWS ElastiCache Redis                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ┌─────────────┐    ┌─────────────┐                     │   │
│  │  │  Primary    │───▶│  Read Replica │ (automatic)      │   │
│  │  │  (cluster)   │    │  (1-5 nodes) │                   │   │
│  │  └─────────────┘    └─────────────┘                     │   │
│  │  Cluster mode: disabled (simple) hoặc enabled (cluster) │   │
│  │  Automatic failover: ✅ (cluster mode)                  │   │
│  │  At-rest encryption: ✅ (AWS-managed KMS)               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Redis Helm chart (bitnami/redis):**

```yaml
# values.yaml (fragment)
architecture: replication  # standalone | replication
auth:
  enabled:  true
  password: ""   # auto-generate
replica:
  replicaCount: 1
  persistence:
    enabled: true
    size: 5Gi
master:
  persistence:
    enabled: true
    size: 5Gi
  resources:
    requests: { cpu: "100m", memory: "256Mi" }
    limits:   { cpu: "250m", memory: "512Mi" }
commonConfiguration: |
  maxmemory-policy allkeys-lru
  timeout 300
```

**ElastiCache Redis (Terraform):**

```hcl
# terraform/modules/elasticache/main.tf (fragment)
resource "aws_elasticache_subnet_group" "main" {
  name       = "capstone-redis-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticacheReplicationGroup" "redis" {
  identifier              = "capstone-${var.env}-redis"
  engine                  = "redis"
  engine_version          = "7.1"

  # Cluster configuration
  node_type            = var.node_type    # cache.t3.medium
  number_cache_clusters = var.env == "prod" ? 2 : 1

  # Network
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids    = [var.security_group_id]

  # Backup & persistence
  automatic_failover_enabled = var.env == "prod" ? true : false
  multi_az_enabled          = var.env == "prod" ? true : false
  snapshot_retention_limit  = var.env == "prod" ? 7 : 1
  snapshot_window           = "03:00-05:00"
  maintenance_window        = "mon:05:00-mon:06:00"

  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false  # enable if TLS needed
  auth_token_enabled        = false  # enable for Redis AUTH

  # Performance
  parameters {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = {
    Environment = var.env
    Project     = "capstone"
  }
}
```

---

### 3.3 Backup Strategy

```
Backup Strategy Decision Tree
│
├─ Mode A: Helm PostgreSQL (local)
│   ├─ Automated: WAL shipping to S3 (WAL-G, pgBackRest)
│   ├─ Daily: pg_dump to PVC snapshot
│   ├─ Point-in-time: WAL replay
│   └─ Challenge: backup có thể nằm trên cùng PVC với data
│
└─ Mode B: RDS PostgreSQL
    ├─ Automated: Daily snapshot + WAL (always on)
    ├─ Point-in-time: any time in last 35 days
    ├─ Cross-region: manual snapshot copy hoặc automated rule
    └─ Test restore: TẠO snapshot → restore to new instance → verify
```

**RDS Backup Details:**

| Config | Dev | Staging | Prod |
|--------|-----|---------|------|
| Backup retention | 1 day | 7 days | 30 days |
| PITR (Point-in-time) | No | Yes (7 days) | Yes (35 days) |
| Multi-AZ | No | No | Yes |
| Cross-region backup | Manual | Manual | Automated rule |
| Tested restore | No | Quarterly | Monthly |

**pgBackRest (Local PostgreSQL Backup):**

```yaml
# Kubernetes CronJob for pgBackRest backup
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: data
spec:
  schedule: "0 3 * * *"  # Daily 3 AM
  successfulJobsHistoryLimit: 7
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: pg-backrest
            image: postgres:15
            env:
            - name: PGBACKREST_STANZA
              value: "db"
            - name: PGBACKREST_DB_PATH
              value: "/var/lib/postgresql/data"
            - name: PGBACKREST_REPO_TYPE
              value: "s3"
            - name: PGBACKREST_REPO_S3_BUCKET
              value: "capstone-backups"
            - name: PGBACKREST_REPO_S3_REGION
              value: "us-east-1"
            command:
            - pgbackrest
            - backup
            - --stanza=db
            - --type=full
          restartPolicy: OnFailure
```

---

### 3.4 Secret Storage Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│           Secret Storage Decision Spectrum                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Pattern 1: Kubernetes Secret (base, NOT encrypted by default) │
│  ─────────────────────────────────────────────────────────────  │
│  ✅ Simpler                                                    │
│  ❌ Not encrypted at rest (need encryption config)            │
│  ❌ No rotation automation                                     │
│  ❌ No audit log                                               │
│  Context: dev environment, demo, quick prototype              │
│                                                                  │
│  Pattern 2: ESO + AWS Secrets Manager (AWS-native)              │
│  ─────────────────────────────────────────────────────────────  │
│  ✅ Encrypted at rest (KMS)                                     │
│  ✅ Automatic rotation via Lambda (optional)                   │
│  ✅ Audit log via CloudTrail                                    │
│  ✅ IRSA access (no long-lived key)                             │
│  ❌ AWS-specific                                                │
│  Context: AWS production workloads                              │
│                                                                  │
│  Pattern 3: ESO + HashiCorp Vault (multi-cloud)                 │
│  ─────────────────────────────────────────────────────────────  │
│  ✅ Cloud-agnostic                                              │
│  ✅ Dynamic secret (generate DB cred per pod)                   │
│  ✅ PKI secret engine                                           │
│  ❌ Complex setup (Vault cluster, unseal)                      │
│  Context: Multi-cloud, regulated environment (bank, healthcare) │
│                                                                  │
│  Pattern 4: Sealed Secrets (GitOps-native, no external server)  │
│  ─────────────────────────────────────────────────────────────  │
│  ✅ No external server needed                                   │
│  ✅ Encrypted in Git (Sealed Secrets controller decrypts)     │
│  ❌ No automatic rotation                                       │
│  ❌ Controller holds decryption key (single point of failure) │
│  Context: GitOps-first team, small scale, no Vault/ASM budget   │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.5 Connection String Management

Connection string là sự kết hợp của: host + port + database + username + password + ssl_mode

```
PostgreSQL connection string format:
  postgresql://user:password@host:5432/dbname?sslmode=require

Redis connection string format:
  redis://default:password@host:6379/0

Connection string lifecycle:
  Generate (random password)
    → Store in secret store (ASM, Vault, Kubernetes Secret)
      → ESO sync to Kubernetes Secret (ESO creates actual Secret in cluster)
        → Mounted as env var hoặc volume vào pod
          → App đọc env var
            → Rotate (optional): update secret store → ESO re-sync → pod restart
```

**Connection string injection via ESO:**

```yaml
# ExternalSecret: khai báo desired state (NOT actual secret)
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: api-service-db-secret
  namespace: api-service-prod
spec:
  refreshInterval: 1h  # ESO check mỗi giờ
  secretStoreRef:
    name: aws-secrets-manager  # ClusterSecretStore (Day 32 setup)
    kind: ClusterSecretStore
  target:
    name: api-service-db-secret  # Kubernetes Secret name được tạo
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        # Connection string cho PostgreSQL
        DATABASE_URL: "{{ .postgres_url }}"
        # Key trong ASM: capstone/prod/api-service/database
        REDIS_URL: "redis://:${REDIS_PASSWORD}@{{ .redis_host }}:6379/0"
  data:
  - secretKey: postgres_url
    remoteRef:
      key: capstone/prod/api-service/database
      property: url
  - secretKey: redis_host
    remoteRef:
      key: capstone/prod/api-service/redis
      property: host
  - secretKey: REDIS_PASSWORD
    remoteRef:
      key: capstone/prod/api-service/redis
      property: password
```

**ESO LocalSecretStore (Mode A — no AWS):**

```yaml
# ClusterSecretStore for local mode
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: local-secret-store
spec:
  provider:
    kubernetes:
      server:
        caProvider:
          type: ConfigMap
          name: kube-root-ca.crt
          key: ca.crt
      # ESO sẽ đọc Secret từ namespace=secret-root
      auth:
        cert:
          clientCertSecretRef:
            name: eso-cert
            key: tls.crt
          clientKeySecretRef:
            name: eso-cert
            key: tls.key
```

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 PostgreSQL: Production Decision Matrix

| Tiêu chí | Helm bitnami (local) | RDS Single-AZ | RDS Multi-AZ |
|---|---|---|---|
| Setup time | 5 phút | 10 phút | 15 phút |
| Cost | $0 (k8s resources) | ~$25-70/tháng | ~$50-140/tháng |
| HA / Failover | ❌ Manual | ❌ | ✅ Auto (60-120s) |
| Automated backup | ❌ (phải tự setup) | ✅ (daily snapshot) | ✅ (same) |
| Point-in-time recovery | ❌ (WAL phải tự config) | ✅ (35 days) | ✅ (same) |
| Read replica | Phức tạp (Stolon, Patroni) | ✅ 1 click | ✅ (Multi-AZ includes standby) |
| Performance tuning | Full control | Limited (DB instance class) | Same |
| Encryption at rest | Tùy storage class | ✅ (AES-256) | ✅ |
| Compliance (SOC2/HIPAA) | Tự audit | ✅ (AWS managed compliance) | ✅ |
| Operation burden | Cao (backup, HA, upgrade) | Thấp | Thấp |
| Use case | Dev/test, learning | Dev/staging, small prod | Production |

### 4.2 Redis: Cluster Mode vs Simple (Single Node)

| Tiêu chí | Simple (no cluster) | Cluster Mode |
|---|---|---|
| Max memory per node | 1 shard = all data | N shard = data partitioned |
| Sharding | ❌ | ✅ (slot-based, 16384 slots) |
| Read scaling | ✅ (read replicas) | ✅ (replicas per shard) |
| Write scaling | ❌ (single primary) | ✅ (primary per shard) |
| Failover | Automatic (replicas) | Automatic per shard |
| Use case | < 350GB, single-region | > 350GB, high write throughput |
| Complexity | Low | Medium |
| Capstone choice | ✅ Dev/staging | Production at scale |

**Recommendation capstone:**
- Mode A dev: Simple Redis (1 primary + 1 replica via Helm)
- Mode B dev: ElastiCache Simple (1 node)
- Mode B prod-like: ElastiCache Cluster (2 shards × 2 replicas)

### 4.3 Secret Storage: Best Solution Per Context

| Context | Recommended | Reason |
|---|---|---|
| Solo learner, local | Kubernetes Secret + manual rotation | Không có external deps |
| Startup MVP, AWS | ESO + AWS Secrets Manager | Tích hợp tốt, dễ setup, OIDC/IRSA |
| Enterprise SME | ESO + AWS Secrets Manager + Lambda rotation | Compliance, audit, rotation |
| Multi-cloud (AWS + GCP) | ESO + HashiCorp Vault | Cloud-agnostic, dynamic secrets |
| Bank / regulated | ESO + HashiCorp Vault + KMIP | FIPS 140-2, HSM support |
| GitOps purist (no external server) | Sealed Secrets | Encrypted in Git, no server needed |
| 100% open source | ESO + External Secrets (ESO Server) | Vendor-neutral, vibrant community |

### 4.4 Connection String: Env Var vs Volume Mount

| Phương pháp | Ưu điểm | Nhược điểm | Use case |
|---|---|---|---|
| Env var | Dễ đọc: `os.Getenv("DATABASE_URL")` | Pod restart mới nhận giá trị mới; có thể leak qua `kubectl describe pod` | Default cho stateless app |
| Volume mount (subPath) | Không trigger pod restart khi secret thay đổi | Mounted file không auto-reload; subPath bypasses K8s secret update | App có file-based config |
| Volume mount (projected) | Auto-update khi ESO sync (K8s 1.19+); không subPath issue | App phải watch file change | Hot-reload requirement |
| TTL-based (Vault) | Dynamic credential per pod, tự rotate | Phức tạp hơn | Bank, compliance-heavy |

**Best practice:**
- Dùng env var cho `DATABASE_URL`, `REDIS_URL` — app restart là acceptable trade-off
- Dùng Kubernetes native secret (được ESO sync) — không dùng raw ASM value trực tiếp trong pod
- `ESO refreshInterval: 1h` — không cần sync real-time (connection string không thay đổi thường xuyên)

### 4.5 Backup Architecture Comparison

```
Local PostgreSQL (Helm):
  ┌──────────────┐    pgBackRest     ┌────────────────┐
  │ postgresql-0  │ ─── WAL ────────▶│  S3 Bucket     │
  │  (primary)    │ ─── full ────────▶│  (capstone-    │
  │               │                   │   backups)      │
  └──────────────┘                   └────────────────┘
  CronJob: pgbackrest backup --type=full (daily)
  CronJob: pgbackrest backup (WAL continuous)

RDS PostgreSQL:
  ┌──────────────┐   Automated   ┌────────────────┐
  │  RDS Primary  │ ──snapshot──▶│  Snapshots     │───cross-region──▶ DR S3
  │  (Multi-AZ)  │              │  retention:30d │
  └──────────────┘              └────────────────┘
  PITR: WAL archived continuously → restore any point
```

### 4.6 Cost Breakdown — Data Layer

```
Mode A (local, $0):
  PostgreSQL Helm: uses node resources (~$0)
  Redis Helm: uses node resources (~$0)
  S3 bucket (backup): $0.023/GB/month (nghĩa là $0 nếu <1GB)
  Total: $0

Mode B (AWS, us-east-1):
  RDS PostgreSQL:
    Single-AZ db.t3.medium: $0.0416/hr × 730 = $30.37/mo
    Multi-AZ db.t3.medium:  $0.0832/hr × 730 = $60.74/mo
    Storage 50GB gp3:       $0.08/GB/mo = $4/mo
    Automated backup (50GB): $0.095/GB/mo = $4.75/mo
  ElastiCache Redis:
    Simple cache.t3.medium: $0.0416/hr × 730 = $30.37/mo
    Cluster mode 2 shards:  $0.0416 × 2 × 730 = $60.74/mo
  Secrets Manager:
    5 secrets: $0.40/secret/mo = $2/mo
  ───────────────────────────────────────────────
  Mode B dev (Single-AZ + Simple): ~$71/mo
  Mode B prod (Multi-AZ + Cluster): ~$127/mo
```

### 4.7 Security Baseline — Data Layer

| Rule | Must | Should |
|------|------|--------|
| PostgreSQL password | Generated randomly, not default | Rotated quarterly |
| RDS public access | ❌ Không bao giờ | N/A |
| RDS security group | Chỉ allow from EKS nodes (port 5432) | N/A |
| Redis auth | ✅ Enable AUTH token | TLS in-transit |
| ElastiCache SG | Chỉ allow from EKS nodes (port 6379) | N/A |
| ESO ClusterSecretStore | ✅ Trỏ đúng secret store | N/A |
| Kubernetes Secret | Được tạo bởi ESO, không commit vào Git | Encrypted at rest via K8s encryption config |
| Connection string | Không hardcode trong manifest | LoadBalancer thay vì NodePort cho DB |

### 4.8 Common Pitfalls

| Pitfall | Hậu quả | Fix |
|---|---|---|
| PostgreSQL password trong Helm values plain text | Secret leak | Dùng `existingSecret` + ESO hoặc `generate` |
| RDS `publicly_accessible = true` | Database exposed internet | Set `false`, dùng bastion hoặc Session Manager |
| Redis không có AUTH | Ai cũng connect được | `auth.enabled = true` |
| Backup chưa từng test restore | Backup corrupted không biết | Restore test hàng tháng |
| ESO ClusterSecretStore sai namespace | Pod không nhận secret | `kind: ClusterSecretStore` not `SecretStore` |
| Connection string dùng IP thay vì hostname | Không fail over khi failover xảy ra | Luôn dùng endpoint (RDS cluster endpoint) |
| Kubernetes Secret không ESO-managed | Giá trị stale | Dùng ExternalSecret, không tạo Secret thủ công |

---

## 5. Hands-on Lab — 60 phút

### Pre-requisites

**Mode A ($0):**
- kind cluster chạy từ Day 30 (`kind get clusters | grep capstone`)
- kubectl context đúng: `kubectl config current-context`
- Helm 3 installed: `helm version`

**Mode B (phát sinh ~$71-127/tháng):**
- Day 29 VPC outputs: `vpc_id`, `private_subnet_ids`
- Day 30 EKS cluster đang chạy
- Day 30 ECR repos: `capstone/api`, `capstone/worker`, `capstone/frontend`
- Day 30 IRSA role cho ESO đã tạo: `capstone-dev-external-secrets`
- Terraform backend S3 đã cấu hình

---

### Mode A — PostgreSQL + Redis via Helm + ESO Local (Free)

> **Context:** kind cluster local, không có AWS. Dùng Helm bitnami deploy PostgreSQL + Redis. Dùng ESO với Kubernetes Secret store (no external backend) để demo secret sync pattern.

**Step 1: Tạo namespace cho data layer**

```bash
kubectl create namespace data --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace external-secrets --dry-run=client -o yaml | kubectl apply -f -

# Verify
kubectl get namespaces | grep -E "data|external-secrets"
```

**Step 2: Thêm bitnami Helm repo**

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Expected output:
# Update Complete. Happy Helming!
```

**Step 3: Deploy PostgreSQL bằng Helm**

```bash
# Generate password và lưu vào Kubernetes Secret (trước khi dùng ESO)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
kubectl create secret generic postgres-credentials \
  --namespace=data \
  --from-literal=password="$POSTGRES_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

# Install PostgreSQL
helm install postgres bitnami/postgresql \
  --namespace data \
  --set architecture=replication \
  --set auth.username=capstone_user \
  --set auth.database=capstone_db \
  --set auth.existingSecret=postgres-credentials \
  --set primary.persistence.size=5Gi \
  --set primary.persistence.storageClass=standard \
  --set primary.resources.requests.cpu=100m \
  --set primary.resources.requests.memory=256Mi \
  --set primary.resources.limits.cpu=500m \
  --set primary.resources.limits.memory=512Mi \
  --set replica.replicaCount=1 \
  --wait --timeout=5m

# Expected output:
# NAME: postgres
# LAST DEPLOYED: ...
# NAMESPACE: data
# STATUS: deployed
```

**Step 4: Deploy Redis bằng Helm**

```bash
# Generate Redis password
REDIS_PASSWORD=$(openssl rand -base64 24)
kubectl create secret generic redis-credentials \
  --namespace=data \
  --from-literal=password="$REDIS_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

# Install Redis
helm install redis bitnami/redis \
  --namespace data \
  --set architecture=replication \
  --set auth.enabled=true \
  --set auth.existingSecret=redis-credentials \
  --set master.persistence.size=2Gi \
  --set master.resources.requests.cpu=50m \
  --set master.resources.requests.memory=128Mi \
  --set replica.replicaCount=1 \
  --set replica.persistence.size=2Gi \
  --wait --timeout=5m

# Expected: "STATUS: deployed"
```

**Step 5: Verify PostgreSQL + Redis đang chạy**

```bash
kubectl get pods -n data -o wide

# Expected:
# NAME                  READY   STATUS    RESTARTS   AGE
# postgres-primary-0    1/1     Running   0          3m
# postgres-replica-0    1/1     Running   0          2m
# redis-master-0        1/1     Running   0          2m
# redis-replica-0       1/1     Running   0          1m

# Test PostgreSQL connection
kubectl run pg-test --rm -it --namespace=data \
  --image=bitnami/postgresql:15 \
  --restart=Never \
  -- psql -h postgres-primary.data.svc.cluster.local \
    -U capstone_user \
    -d capstone_db \
    -c "SELECT version();"

# Expected: PostgreSQL 15.x on...
```

**Step 6: Lấy connection string và chuẩn bị value cho ESO**

```bash
# Lấy PostgreSQL host
POSTGRES_HOST=$(kubectl get svc postgres-primary -n data \
  -o jsonpath='{.spec.clusterIP}')
echo "PostgreSQL host: $POSTGRES_HOST"

# Build connection string
DATABASE_URL="postgresql://capstone_user:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/capstone_db"
echo "DATABASE_URL prepared for ExternalSecret target"
```

Không in full connection string ra terminal trong workflow thật vì nó chứa password. Lab này giữ value trong shell variable để tạo fake local secret store ở bước sau.

**Step 7: Cài External Secrets Operator trước khi apply `ExternalSecret`**

`ExternalSecret`, `SecretStore` và `ClusterSecretStore` là CRD. Nếu apply manifest trước khi ESO cài CRD, Kubernetes sẽ trả lỗi `no matches for kind "ExternalSecret"`.

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --set installCRDs=true \
  --wait --timeout=5m

kubectl wait --for=condition=Established \
  crd/externalsecrets.external-secrets.io \
  --timeout=60s

kubectl get pods -n external-secrets
# Expected: external-secrets-xxxx Running
```

**Step 8: Tạo local `ClusterSecretStore` + `ExternalSecret`**

Mode A dùng fake provider để mô phỏng secret backend local. Fake provider chỉ phục vụ lab/test, không dùng cho production.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: local-secret-store
spec:
  provider:
    fake:
      data:
      - key: /capstone/local/api-service/database-url
        value: "${DATABASE_URL}"
      - key: /capstone/local/api-service/redis-password
        value: "${REDIS_PASSWORD}"
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: api-service-db-secret
  namespace: data
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: local-secret-store
    kind: ClusterSecretStore
  target:
    name: api-service-db-secret
    creationPolicy: Owner
  data:
  - secretKey: DATABASE_URL
    remoteRef:
      key: /capstone/local/api-service/database-url
  - secretKey: REDIS_PASSWORD
    remoteRef:
      key: /capstone/local/api-service/redis-password
EOF

kubectl wait externalsecret/api-service-db-secret \
  -n data \
  --for=condition=Ready \
  --timeout=60s

kubectl get secret api-service-db-secret -n data
# Expected: api-service-db-secret exists, type Opaque
```

**Step 9: Deploy test pod đọc connection string**

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: db-connectivity-test
  namespace: data
spec:
  replicas: 1
  selector:
    matchLabels:
      app: db-test
  template:
    metadata:
      labels:
        app: db-test
    spec:
      containers:
      - name: test
        image: bitnami/postgresql:15
        command: ["sh", "-c", "echo 'DATABASE_URL: $DATABASE_URL' && sleep 3600"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: api-service-db-secret
              key: DATABASE_URL
        resources:
          requests: { cpu: "50m", memory: "64Mi" }
          limits:   { cpu: "100m", memory: "128Mi" }
EOF

# Verify env var được mount
kubectl exec deploy/db-connectivity-test -n data -- sh -c 'echo $DATABASE_URL' | head -c 50
# Expected: postgresql://capstone_user:...@10.x.x.x:5432/capstone_db
```

**Mode A cleanup:**

```bash
helm uninstall postgres --namespace data
helm uninstall redis --namespace data
helm uninstall external-secrets --namespace external-secrets
kubectl delete namespace data external-secrets
```

---

### Mode B — RDS PostgreSQL + ElastiCache + ESO + AWS Secrets Manager (Có Cost)

> **WARNING:** Mode B tạo RDS + ElastiCache trong AWS. Chi phí ước tính ~$71-127/tháng. Cleanup bắt buộc sau lab.

**Step 1: Tạo Terraform module structure cho data layer**

```bash
mkdir -p terraform/modules/rds terraform/modules/elasticache terraform/modules/secrets
```

**File: `terraform/modules/rds/main.tf`**

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-${var.env}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = {
    Project     = var.project
    Environment = var.env
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project}-${var.env}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_security_group_id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.project
    Environment = var.env
  }
}

# RDS PostgreSQL instance
resource "aws_db_instance" "postgres" {
  identifier     = "${var.project}-${var.env}-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.instance_class

  # Authentication
  db_name                = replace(var.env, "-", "_")
  username               = "capstone_admin"
  manage_master_user_password = true  # AWS quản lý password

  # Network — NEVER public
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible   = false

  # Storage
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_id  # optional, uses default if null

  # Backup strategy — production-grade
  backup_retention_period = var.backup_retention_period
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  delete_az_backups      = false

  # Monitoring
  monitoring_interval = 60
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  # Multi-AZ: production only
  multi_az = var.env == "prod" ? true : false

  # Performance insights
  performance_insights_enabled = var.env == "prod"
  performance_insights_retention_period = var.env == "prod" ? 7 : 1

  # Deletion protection
  deletion_protection = var.env == "prod" ? true : false

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
  }
}

# Store password in AWS Secrets Manager
resource "aws_secretsmanager_secret" "postgres" {
  name        = "${var.project}/${var.env}/postgres"
  description = "PostgreSQL admin credentials for ${var.project} ${var.env}"

  recovery_window_in_days = 7  # 7-30 days

  tags = {
    Project     = var.project
    Environment = var.env
  }
}

resource "aws_secretsmanager_secret_version" "postgres" {
  secret_id = aws_secretsmanager_secret.postgres.id

  secret_string = jsonencode({
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    username = aws_db_instance.postgres.master_username
    password = aws_db_instance.postgres.master_user_password  # AWS-managed
    database = aws_db_instance.postgres.db_name
    url      = "postgresql://${aws_db_instance.postgres.master_username}:${aws_db_instance.postgres.master_user_password}@${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}/${aws_db_instance.postgres.db_name}"
  })
}
```

**File: `terraform/modules/rds/variables.tf`**

```hcl
variable "project"          { type = string }
variable "env"             { type = string }
variable "vpc_id"          { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "eks_security_group_id" { type = string }
variable "instance_class"  { type = string  default = "db.t3.medium" }
variable "allocated_storage" { type = number default = 20 }
variable "max_allocated_storage" { type = number default = 100 }
variable "backup_retention_period" { type = number default = 7 }
variable "kms_key_id"      { type = string  default = null }
```

**File: `terraform/modules/rds/outputs.tf`**

```hcl
output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint"
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "rds_secret_arn" {
  description = "Secrets Manager ARN for RDS credentials"
  value       = aws_secretsmanager_secret.postgres.arn
}

output "rds_security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "rds_identifier" {
  description = "RDS instance identifier"
  value       = aws_db_instance.postgres.identifier
}
```

**File: `terraform/modules/elasticache/main.tf`**

```hcl
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project}-${var.env}-redis-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name        = "${var.project}-${var.env}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.eks_security_group_id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project     = var.project
    Environment = var.env
  }
}

resource "aws_elasticache_replication_group" "redis" {
  identifier              = "${var.project}-${var.env}-redis"
  engine                  = "redis"
  engine_version          = "7.1"
  node_type               = var.node_type

  number_cache_clusters   = var.env == "prod" ? 2 : 1

  # Network
  subnet_group_name       = aws_elasticache_subnet_group.main.name
  security_group_ids      = [aws_security_group.redis.id]
  port                    = 6379

  # Backup
  automatic_failover_enabled = var.env == "prod" ? true : false
  multi_az_enabled          = var.env == "prod" ? true : false
  snapshot_retention_limit  = var.env == "prod" ? 7 : 1
  snapshot_window           = "03:00-05:00"
  maintenance_window        = "sun:05:00-sun:06:00"

  # Security
  at_rest_encryption_enabled = true
  auth_token_enabled        = var.env == "prod" ? true : false
  transit_encryption_mode  = var.env == "prod" ? "required" : "preferred"

  # Parameters
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
  }
}

# Store Redis connection info in Secrets Manager
resource "aws_secretsmanager_secret" "redis" {
  name        = "${var.project}/${var.env}/redis"
  description = "Redis connection info for ${var.project} ${var.env}"

  recovery_window_in_days = 7

  tags = {
    Project     = var.project
    Environment = var.env
  }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id

  secret_string = jsonencode({
    host     = aws_elasticache_replication_group.redis.primary_endpoint_address
    port     = aws_elasticache_replication_group.redis.port
    password = var.env == "prod" ? aws_elasticache_replication_group.redis.auth_token : ""
    url      = "redis://${var.env == "prod" ? ":" : ""}${var.env == "prod" ? aws_elasticache_replication_group.redis.auth_token : ""}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  })
}
```

**File: `terraform/modules/elasticache/variables.tf`**

```hcl
variable "project"            { type = string }
variable "env"                { type = string }
variable "vpc_id"             { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "eks_security_group_id" { type = string }
variable "node_type"          { type = string default = "cache.t3.medium" }
```

**File: `terraform/modules/elasticache/outputs.tf`**

```hcl
output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "ElastiCache Redis reader endpoint"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_secret_arn" {
  description = "Secrets Manager ARN for Redis credentials"
  value       = aws_secretsmanager_secret.redis.arn
}
```

**Step 2: Wire trong environment root module**

```hcl
# terraform/environments/dev/main.tf (append to existing Day 30 file)
# Data Layer — Day 31

data "terraform_remote_state" "eks" {
  backend = "s3"
  config {
    bucket = "capstone-terraform-state"
    key    = "eks/eks.tfstate"
    region = "us-east-1"
  }
}

module "rds" {
  source = "../../modules/rds"

  project               = "capstone"
  env                   = "dev"
  vpc_id                = data.terraform_remote_state.network.outputs.vpc_id
  private_subnet_ids    = data.terraform_remote_state.network.outputs.private_subnet_ids
  eks_security_group_id = data.terraform_remote_state.eks.outputs.eks_cluster_sg_id
  instance_class        = "db.t3.small"    # dev: smaller instance
  backup_retention_period = 1             # dev: 1 day
}

module "elasticache" {
  source = "../../modules/elasticache"

  project               = "capstone"
  env                   = "dev"
  vpc_id                = data.terraform_remote_state.network.outputs.vpc_id
  private_subnet_ids    = data.terraform_remote_state.network.outputs.private_subnet_ids
  eks_security_group_id = data.terraform_remote_state.eks.outputs.eks_cluster_sg_id
  node_type             = "cache.t3.small"  # dev: smaller instance
}

# Output để ESO đọc (ClusterSecretStore sẽ dùng IRSA)
output "rds_endpoint" {
  value     = module.rds.rds_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.elasticache.redis_endpoint
  sensitive = true
}

output "rds_secret_arn" {
  value = module.rds.rds_secret_arn
}

output "redis_secret_arn" {
  value = module.elasticache.redis_secret_arn
}
```

**Step 3: Plan + Apply**

```bash
cd terraform/environments/dev

# Plan — xem những gì sẽ tạo
terraform plan -out=plan.tfplan

# Expected plan output:
# + aws_db_instance.postgres
# + aws_db_subnet_group.main
# + aws_security_group.rds
# + aws_secretsmanager_secret.postgres
# + aws_elasticache_replication_group.redis
# + aws_elasticache_subnet_group.main
# + aws_security_group.redis
# + aws_secretsmanager_secret.redis

# Apply — WARNING: phát sinh chi phí ~$71/tháng (dev, Single-AZ)
terraform apply -auto-approve plan.tfplan

# Apply sẽ mất 10-15 phút (RDS + ElastiCache creation)
# Lấy outputs
terraform output -json
```

**Step 4: Xác nhận RDS endpoint**

```bash
# Get RDS endpoint
RDS_HOST=$(terraform output -raw rds_endpoint)
echo "RDS endpoint: $RDS_HOST"

# Verify bằng AWS CLI
aws rds describe-db-instances \
  --db-instance-identifier capstone-capstone-dev-postgres \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text

# Verify security group: chỉ allow từ EKS
aws ec2 describe-security-groups \
  --group-ids $(aws rds describe-db-instances \
    --db-instance-identifier capstone-capstone-dev-postgres \
    --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' \
    --output text) \
  --query 'SecurityGroups[0].IpPermissions'
```

**Step 5: ESO — tạo ClusterSecretStore + ExternalSecret**

```bash
# Tạo ClusterSecretStore dùng IRSA từ Day 30
cat <<'EOF' | kubectl apply -f -
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
EOF

# Tạo ExternalSecret cho API service
cat <<'EOF' | kubectl apply -f -
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: api-service-db-secret
  namespace: api-service-prod
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-service-db-secret
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        DATABASE_URL: "{{ .url }}"
        DB_HOST: "{{ .host }}"
        DB_PORT: "{{ .port }}"
        DB_NAME: "{{ .database }}"
        DB_USER: "{{ .username }}"
  data:
  - secretKey: url
    remoteRef:
      key: capstone/dev/postgres
      property: url
  - secretKey: host
    remoteRef:
      key: capstone/dev/postgres
      property: host
  - secretKey: port
    remoteRef:
      key: capstone/dev/postgres
      property: port
  - secretKey: database
    remoteRef:
      key: capstone/dev/postgres
      property: database
  - secretKey: username
    remoteRef:
      key: capstone/dev/postgres
      property: username
EOF

# Verify ESO sync
kubectl get externalsecret -n api-service-prod
# Expected: SYNCED = True

# Verify Kubernetes Secret được tạo
kubectl get secret api-service-db-secret -n api-service-prod -o yaml
# Note: các key sẽ hiển thị base64 encoded
```

**Step 6: Test connectivity (optional)**

```bash
# Deploy test pod với ESO-managed secret
kubectl run db-test --rm -it --namespace api-service-prod \
  --image=postgres:15 \
  --restart=Never \
  --overrides='
{
  "spec": {
    "serviceAccountName": "external-secrets",
    "containers": [{
      "name": "test",
      "image": "postgres:15",
      "command": ["psql"],
      "args": ["$(DATABASE_URL)", "-c", "SELECT 1;"],
      "env": [{
        "name": "DATABASE_URL",
        "valueFrom": {
          "secretKeyRef": {
            "name": "api-service-db-secret",
            "key": "DATABASE_URL"
          }
        }
      }]
    }]
  }
}' 2>/dev/null || echo "Pod ran (psql exited)"
```

**Step 7: CLEANUP — Bắt buộc**

```bash
cd terraform/environments/dev

# Tắt deletion_protection (nếu có) trước khi destroy
# Dev: deletion_protection = false nên không cần

# Destroy data layer
terraform destroy -auto-approve

# Verify resources đã xóa
aws rds describe-db-instances --query 'DBInstances[?DBInstanceIdentifier!=`null`]' | grep DBInstanceIdentifier || echo "RDS deleted"

aws elasticache describe-replication-groups \
  --query 'ReplicationGroups[?ReplicationGroupId!=`null`]' | grep ReplicationGroupId || echo "Redis deleted"

# Xóa secrets từ Secrets Manager (nếu còn)
aws secretsmanager list-secrets --filter Key=name,Values=capstone | \
  --query 'SecretList[].ARN' --output text | \
  xargs -I{} aws secretsmanager delete-secret --secret-id {} --force-delete-recovery-window --region us-east-1

echo "Cleanup complete. Cost after cleanup: $0"
```

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Khi nào dùng RDS thay vì Helm PostgreSQL? Nếu budget bạn là $0 cho dev environment, bạn chọn gì?

> **Trả lời:** RDS khi cần: automated backup + PITR, Multi-AZ HA, managed compliance, zero operational overhead cho backup/upgrade. Helm khi: budget $0, learning/debugging, không cần production-grade HA. Dev $0 → Helm bitnami/postgresql trong kind cluster.

**Câu 2:** ElastiCache Redis Cluster Mode khác gì Simple Mode? Trade-off là gì?

> **Trả lời:** Cluster Mode sharding data qua nhiều node (16384 slots), hỗ trợ write scaling khi data > 350GB. Simple Mode: 1 primary + replicas, không sharding, đơn giản hơn. Trade-off: Cluster Mode phức tạp hơn (client phải support cluster mode), nhưng scale write throughput. Capstone dev/staging → Simple; prod large-scale → Cluster.

**Câu 3:** Debug: ESO sync thành công (ExternalSecret SYNCED=True) nhưng pod không thấy env var. Liệt kê 5 nguyên nhân.

> **Trả lời:** (1) Secret được tạo ở namespace khác (ESO tạo trong namespace của ExternalSecret, không phải nơi pod chạy). (2) ServiceAccount pod không có quyền đọc Secret (`kubectl get rolebinding`). (3) `spec.target.name` không match env var reference. (4) Pod đang chạy pod cũ (trước khi Secret được tạo) — cần restart pod. (5) `template.data` key không match `data.secretKey` — ESO không overwrite.

**Câu 4:** Backup strategy nào production-grade cho PostgreSQL? Mô tả RPO (Recovery Point Objective) và RTO (Recovery Point Objective) của mỗi approach.

> **Trả lời:** (1) RDS automated backup: RPO = 1 day, RTO = minutes (point-in-time restore). (2) RDS automated backup + WAL continuous archiving: RPO = near-zero (5 min lag), RTO = ~15-30 min. (3) pgBackRest to S3 (local): RPO = WAL-based (5 min), RTO = ~30-60 min (restore from S3). (4) Cross-region DR: RPO = 24h (snapshot replication), RTO = hours. Production target: RPO < 5 min, RTO < 30 min.

**Câu 5:** Thiết kế secret storage cho 3 scenario: (a) solo learner, (b) startup 10 dev trên AWS, (c) enterprise bank trên multi-cloud. Chọn solution và giải thích trade-off.

> **Trả lời:** (a) Solo: Kubernetes Secret (manual) → đơn giản, $0, không cần ESO. (b) Startup: ESO + AWS Secrets Manager → tích hợp IAM/IRSA, OIDC, audit CloudTrail, dễ setup, chi phí $0.40/secret. (c) Bank: ESO + HashiCorp Vault → multi-cloud, dynamic secret per pod, HSM support, PKI engine, FIPS 140-2, nhưng phức tạp (Vault HA, unseal, rotation).

---

## 7. Tóm tắt cuối ngày

**3-5 ý chính:**

1. PostgreSQL: Helm bitnami cho dev local (free, đủ dùng); RDS cho production (managed backup, Multi-AZ, PITR). Không bao giờ dùng public RDS trong bài lab.

2. Redis: Helm bitnami replication (1 primary + 1 replica) cho dev; ElastiCache Simple cho staging, Cluster cho production scale. Luôn bật AUTH token.

3. Backup: RDS tự động snapshot + WAL; local Helm cần tự setup pgBackRest/S3. **Backup không test restore = backup không đáng tin.**

4. Secret storage: ESO (External Secrets Operator) là cầu nối giữa secret store (ASM, Vault, local) và Kubernetes Secret. Pod KHÔNG bao giờ đọc trực tiếp từ ASM — luôn qua ESO tạo Kubernetes Secret.

5. Connection string: dùng Kubernetes Secret (được ESO sync) → mount as env var vào pod. Endpoint luôn dùng DNS hostname, không IP (vì RDS failover thay đổi IP).

**Output sau Day 31:**

| File | Mode A (kind) | Mode B (AWS) |
|---|---|---|
| PostgreSQL | `helm install postgres` (bitnami) | `module.rds` (Terraform) |
| Redis | `helm install redis` (bitnami) | `module.elasticache` (Terraform) |
| Secrets | `postgres-credentials` + `redis-credentials` K8s Secret | `capstone/dev/postgres` + `capstone/dev/redis` (ASM) |
| ExternalSecret | ✅ `api-service-db-secret` (ESO manifest) | ✅ `api-service-db-secret` (ASM-backed) |
| ClusterSecretStore | ✅ `local-secret-store` (reference) | ✅ `aws-secrets-manager` (IRSA) |
| Connection string | ✅ `DATABASE_URL` as env var in pod | ✅ `DATABASE_URL` as env var via ESO |
| Day 32 ready | PostgreSQL + Redis running | RDS + ElastiCache + ASM + ESO synced |

**Chuẩn bị Day 32 (Platform Bootstrap Layer):**
- Cài ArgoCD bằng Helm hoặc ArgoCD operator
- Bootstrap platform apps qua App of Apps / ApplicationSet
- Cài External Secrets Operator (ESO) cluster-wide
- Cài Ingress Controller / AWS LB Controller
- Cài Cert Manager + ClusterIssuer

---

## 8. Tham khảo thêm

- [bitnami/postgresql Helm chart](https://artifacthub.io/packages/helm/bitnami/postgresql)
- [bitnami/redis Helm chart](https://artifacthub.io/packages/helm/bitnami/redis)
- [terraform-aws-modules/rds/aws](https://registry.terraform.io/modules/terraform-aws-modules/rds/aws/latest)
- [terraform-aws-modules/elasticache/aws](https://registry.terraform.io/modules/terraform-aws-modules/elasticache/aws/latest)
- [External Secrets Operator — Getting Started](https://external-secrets.io/latest/introduction/getting-started/)
- [External Secrets Operator — Fake Provider](https://external-secrets.io/latest/provider/fake/)
- [AWS Secrets Manager — Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [RDS PostgreSQL — Backup and Restore](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.BackupRestore.html)
- [ElastiCache Redis — Cluster Mode](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/ClusterMode.html)
- [pgBackRest — PostgreSQL Backup](https://pgbackrest.org/)
- [Kubernetes External Secrets — ASM Integration](https://external-secrets.io/latest/provider/aws-secrets-manager/)
