# Day 31 — Data Layer & Secrets: Reference Document

## 1. PostgreSQL Comparison Matrix

### Helm (bitnami/postgresql) vs RDS vs Aurora

| Tiêu chí | Helm bitnami | RDS PostgreSQL | Aurora PostgreSQL |
|---|---|---|---|
| Deployment | In-cluster (Deployment/StatefulSet) | AWS managed | AWS managed |
| Setup time | 5 phút | 10-15 phút | 15-20 phút |
| Cost | $0 (node resources) | $25-140/tháng | $50-200/tháng |
| HA / Failover | ❌ (manual, dùng Patroni/Stolon) | ✅ Multi-AZ auto (60-120s) | ✅ Multi-AZ auto (30s) |
| Automatic backup | ❌ (pgBackRest/WAL tự setup) | ✅ Daily snapshot + WAL | ✅ Continuous |
| Point-in-time recovery | ❌ (WAL phải tự config) | ✅ 35 days | ✅ |
| Read scaling | ❌ (Replication setup phức tạp) | ✅ Read replica 1-click | ✅ Auto-scaling read replicas |
| Encryption at rest | Tùy storage class (gp3 AES-256) | ✅ AES-256 | ✅ |
| Encryption in transit | Tùy TLS config | ✅ (force_ssl = 1) | ✅ |
| Max connections | 100 (default) | 500-5000 (theo instance class) | 5000+ |
| Maintenance | Tự quản lý (minor version, patches) | Maintenance window | Managed |
| Use case | Dev/test, learning | Staging, production small-medium | Production high-scale |
| Migration path | → RDS (export/import pg_dump) | ← Helm | Alternative |

---

## 2. Redis Comparison Matrix

| Tiêu chí | Helm bitnami | ElastiCache Simple | ElastiCache Cluster |
|---|---|---|---|
| Deployment | In-cluster (Deployment) | AWS managed | AWS managed |
| Cost | $0 (node resources) | $30-60/tháng | $60-120/tháng |
| HA / Failover | ❌ (phải tự setup Sentinel) | ✅ Auto-failover (1 replica) | ✅ Per-shard failover |
| Read scaling | ✅ (read replicas) | ✅ (1-5 replicas) | ✅ (replicas per shard) |
| Write scaling | ❌ (single primary) | ❌ | ✅ (N primaries, each shard) |
| Max data size | Node RAM limit | 350GB (cluster disabled) | 5.5TB (cluster enabled, 500GB/shard) |
| Cluster mode | ❌ (single shard) | ❌ | ✅ (slot-based sharding) |
| Auth token | ✅ (`auth.enabled = true`) | ✅ (`auth_token_enabled`) | ✅ |
| TLS in transit | Tùy config | ✅ optional | ✅ optional |
| Persistence | ✅ (RDB + AOF config) | ✅ (RDB snapshots) | ✅ |
| Use case | Dev/test, session cache | Small cache, session, queue | High-throughput production |
| Port | 6379 | 6379 | 6379 (cluster: 6379-6384) |

---

## 3. Backup Strategy Decision Guide

### 3.1 RPO/RTO Target

| Tier | RPO (max data loss) | RTO (recovery time) | Strategy |
|---|---|---|---|
| Production | < 5 phút | < 30 phút | Continuous WAL + Multi-AZ |
| Staging | < 1 giờ | < 1 giờ | Daily snapshot + WAL |
| Dev | < 1 ngày | < 4 giờ | Daily pg_dump |
| DR site | < 24 giờ | < 4 giờ | Cross-region snapshot copy |

### 3.2 PostgreSQL Backup Tools Comparison

| Tool | RPO | Setup | S3 Support | Encryption | PITR |
|---|---|---|---|---|---|
| `pg_dump` | Manual (hours) | Simple | Via script | ✅ | ❌ |
| `pgBackRest` | ~5 phút (WAL) | Medium | ✅ Native | ✅ | ✅ |
| Barman | ~5 phút | Complex | ✅ | ✅ | ✅ |
| WAL-E / WAL-G | ~5 phút | Medium | ✅ Native | ✅ | ✅ |
| RDS Automated | 1 day | None (managed) | N/A | ✅ | ✅ |
| RDS PITR | Near-zero | None | N/A | ✅ | ✅ |

### 3.3 Backup Verification Checklist

```bash
# 1. Verify backup ran
pgBackRest: cat /var/lib/pgbackrest/backup/backup.info
RDS: aws rds describe-db-snapshots --db-instance-identifier <id>

# 2. Test restore to new instance (PROD: quarterly; DEV: monthly)
# pgBackRest:
pgbackrest restore --stanza=db --type=time --target="2024-01-15 03:00:00"

# RDS:
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier capstone-restore-test \
  --snapshot-identifier rds:capstone-prod-2024-01-15 \
  --db-instance-class db.t3.medium

# 3. Verify data integrity
psql -h localhost -U capstone_user -d capstone_db -c "SELECT count(*) FROM your_table;"

# 4. Clean up test instance
# RDS:
aws rds delete-db-instance --db-instance-identifier capstone-restore-test \
  --skip-final-snapshot
```

---

## 4. AWS Secrets Manager Quick Reference

### 4.1 Secrets Manager vs Systems Manager Parameter Store

| Tiêu chí | Secrets Manager | Parameter Store (SSM) |
|---|---|---|
| Cost | $0.40/secret/month | $0.05/param/month (Standard) |
| Encryption | KMS (AES-256) | KMS (AES-256) |
| Automatic rotation | Lambda (native integration) | Lambda (custom) |
| Cross-region replication | ✅ (automatic) | ❌ |
| Resource policy | ✅ | ✅ |
| CloudTrail audit | ✅ | ✅ (for Write actions) |
| Cross-account | ✅ (resource policy) | ✅ ( Parameter Store API) |
| Automatic secret rotation | ✅ (MySQL, RDS, etc.) | ❌ |
| Max size | 10KB | 4KB (Standard), 8KB (Advanced) |
| Throughput | 1000 reads/sec | 1000 reads/sec (Standard) |
| ESO provider | ✅ (native) | ✅ |

### 4.2 ASM Secret Structure for Capstone

```
capstone/
├── dev/
│   ├── postgres/           # RDS dev credentials
│   │   url: postgresql://...@...:5432/capstone_dev
│   │   host: capstone-dev-postgres.xxxx.us-east-1.rds.amazonaws.com
│   │   port: "5432"
│   │   username: capstone_admin
│   │   database: capstone_dev
│   ├── redis/             # ElastiCache dev credentials
│   │   host: capstone-dev-redis.xxxx.cache.amazonaws.com
│   │   port: "6379"
│   │   password: ""
│   └── api-service/
│       database: { url, host, port }
│       redis: { host, port, password }
├── staging/
│   ├── postgres/
│   ├── redis/
│   └── api-service/
└── prod/
    ├── postgres/
    ├── redis/
    └── api-service/
```

### 4.3 ASM Secret ARN Pattern

```
arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:PROJECT/ENV/COMPONENT
```

```bash
# Create secret via AWS CLI
aws secretsmanager create-secret \
  --name "capstone/dev/api-service/database" \
  --secret-string '{"url":"postgresql://...","host":"..."}' \
  --region us-east-1

# Get secret value
aws secretsmanager get-secret-value \
  --secret-id "capstone/dev/api-service/database" \
  --region us-east-1 \
  --query SecretString --output text

# List all capstone secrets
aws secretsmanager list-secrets \
  --filter Key=name,Values=capstone \
  --region us-east-1
```

---

## 5. ESO Quick Reference

### 5.1 ESO Provider Matrix

| Provider | SecretStore kind | Auth | Rotation | Best for |
|---|---|---|---|---|
| AWS Secrets Manager | ClusterSecretStore / SecretStore | IRSA (IAM role) | Lambda | AWS workloads |
| GCP Secret Manager | ClusterSecretStore | Workload Identity | ✅ | GCP workloads |
| HashiCorp Vault | ClusterSecretStore | Kubernetes Auth / AppRole | ✅ | Multi-cloud |
| Azure Key Vault | ClusterSecretStore | Managed Identity | ✅ | Azure workloads |
| Kubernetes Secret | SecretStore | cert / token | ❌ | Local dev |
| YAML (inline) | N/A (static) | N/A | ❌ | Quick demo |

### 5.2 ESO ExternalSecret CRD Reference

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: my-secret
  namespace: my-namespace
spec:
  refreshInterval: 1h        # How often ESO re-fetches from secret store
  secretStoreRef:
    name: my-secret-store    # Name of ClusterSecretStore or SecretStore
    kind: ClusterSecretStore # or SecretStore (namespace-scoped)
  target:
    name: my-k8s-secret      # Kubernetes Secret name to create
    creationPolicy: Owner     # Owner = ESO creates; Merge = only update existing
    deletionPolicy: Retain    # Retain = keep on ExternalSecret delete
    template:                 # Optional: transform secret data
      type: Opaque
      data:
        MY_KEY: "{{ .remoteKey }}"   # Jinja2-like template
  data:                        # Map remote keys → K8s secret keys
  - secretKey: remoteKey       # Key in K8s Secret
    remoteRef:
      key: my/remote/secret   # Key in secret store
      property: my-property   # Property path in JSON (optional)
```

### 5.3 ClusterSecretStore (AWS ASM + IRSA)

```yaml
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
            name: external-secrets        # SA must exist in ESO namespace
            namespace: external-secrets   # Usually kube-system or external-secrets
```

### 5.4 ESO Installation Reference

```bash
# Helm installation
helm repo add external-secrets https://charts.external-secrets.io
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --set installCRDs=true \
  --set serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=$ESO_IRSA_ARN \
  --wait

# Or via Operator (if using Operator lifecycle)
# kubectl apply -f https://external-secrets.io/latest/install/

# Verify installation
kubectl get pods -n external-secrets
# external-secrets-xxxx-xxxxx   1/1   Running
```

---

## 6. Connection String Templates

### PostgreSQL Connection Strings

```bash
# Standard (libpq)
postgresql://user:password@host:5432/database

# With SSL
postgresql://user:password@host:5432/database?sslmode=require

# With application_name (useful for debugging)
postgresql://user:password@host:5432/database?application_name=api-service

# With connection pool parameters
postgresql://user:password@host:5432/database?sslmode=require&pool_max_conns=20
```

### Redis Connection Strings

```bash
# Standard
redis://password@host:6379/0

# With TLS
rediss://password@host:6379/0

# Cluster mode
redis-cluster://host1:6379,host2:6379,host3:6379/0

# Sentinel mode (for HA)
redis-sentinel://host:26379/service_name/0
```

### Connection String Injection in Deployment

```yaml
# Pattern 1: Environment variable (RECOMMENDED)
env:
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: api-service-db-secret
      key: DATABASE_URL

- name: REDIS_URL
  valueFrom:
    secretKeyRef:
      name: api-service-db-secret
      key: REDIS_URL

# Pattern 2: Volume mount (projected, K8s 1.19+)
volumes:
- name: secrets
  projected:
    sources:
    - secret:
        name: api-service-db-secret
        items:
        - key: DATABASE_URL
          path: database_url

# Pattern 3: Volume mount with TTL-based secret (Vault dynamic)
volumes:
- name: db-creds
  csi:
    driver: vault.csi.provider.com
    readOnly: true
    volumeAttributes:
      roleName: database
      vaultAddress: https://vault.internal:8200
      secrets: |
        - objectName: db-creds
          secretPath: database/creds/my-role
          secretKey: username
```

---

## 7. RDS Terraform Module Reference

### terraform-aws-modules/rds

```hcl
# Minimal required inputs
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "capstone-dev-postgres"

  engine               = "postgres"
  engine_version       = "15.4"
  family               = "postgres15"
  instance_class       = "db.t3.medium"

  db_name              = "capstone_db"
  username             = "capstone_admin"
  password             = random_password.db_password.result

  subnet_ids           = module.vpc.private_subnets
  vpc_security_group_ids = [module.rds_sg.security_group_id]

  multi_az               = false
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_encrypted      = true

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  deletion_protection     = false  # always false for dev
}
```

### Key Outputs

```hcl
output "rds_endpoint"       { value = module.rds.db_instance_address }
output "rds_port"          { value = module.rds.db_instance_port }
output "rds_arn"           { value = module.rds.db_instance_arn }
output "rds_name"          { value = module.rds.db_instance_name }
output "rds_password"      { value = random_password.db_password.result, sensitive = true }
```

---

## 8. ElastiCache Terraform Module Reference

```hcl
module "elasticache" {
  source  = "terraform-aws-modules/elasticache/aws"
  version = "~> 8.0"

  cluster_id           = "capstone-dev-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type           = "cache.t3.medium"

  number_cache_clusters = 1          # 2 for cluster mode

  port                = 6379
  subnet_group_name   = aws_elasticache_subnet_group.main.name
  security_group_ids   = [module.redis_sg.security_group_id]

  automatic_failover_enabled = false  # true for cluster mode
  multi_az_enabled          = false
  at_rest_encryption_enabled = true
  auth_token_enabled        = false  # true for production
  transit_encryption_mode   = "preferred"

  snapshot_retention_limit = 1
  snapshot_window          = "03:00-05:00"

  maintenance_window       = "sun:05:00-sun:06:00"

  # Parameter overrides
  parameter_group_name = aws_elasticache_parameter_group.redis.name
}
```

### Key Outputs

```hcl
output "redis_endpoint"         { value = module.elasticache.redis_endpoint }
output "redis_reader_endpoint"  { value = module.elasticache.redis_reader_endpoint }
output "redis_arn"             { value = module.elasticache.elasticache_replication_group_arn }
```

---

## 9. Security Checklist — Data Layer

### PostgreSQL / RDS

- [ ] `publicly_accessible = false` (never expose DB publicly)
- [ ] `password` generated randomly, not hardcoded in Terraform
- [ ] Security group: chỉ allow port 5432 từ EKS node SG
- [ ] `sslmode=require` trong connection string
- [ ] `random_password` với length >= 32, special characters
- [ ] Backup retention: dev >= 1, staging >= 7, prod >= 30
- [ ] Storage encrypted: `storage_encrypted = true`
- [ ] Log connections: `log_connections = 1` (prod)
- [ ] Connection limit: phù hợp với workload (RDS default: 100)
- [ ] Maintenance window: non-business hours

### Redis / ElastiCache

- [ ] `auth_token_enabled = true` (production)
- [ ] Security group: chỉ allow port 6379 từ EKS node SG
- [ ] `at_rest_encryption_enabled = true`
- [ ] `transit_encryption_mode = required` (production)
- [ ] `maxmemory-policy = allkeys-lru` (nếu cache)
- [ ] Snapshot retention: dev >= 1, prod >= 7
- [ ] Read replica cho production read-heavy workload

### Secrets Management

- [ ] Không hardcode password trong Git
- [ ] ESO ClusterSecretStore dùng IRSA, không access key
- [ ] Kubernetes Secret được tạo bởi ESO, không tạo thủ công
- [ ] `recovery_window_in_days = 7` trên ASM secret
- [ ] Connection string không chứa IP (dùng DNS hostname)
- [ ] App đọc secret từ Kubernetes Secret (env var hoặc volume), không đọc trực tiếp từ ASM/Vault

---

## 10. Cost Optimization Checklist

- [ ] Dev: dùng `db.t3.small` thay vì `db.t3.medium` (tiết kiệm ~50%)
- [ ] Dev: `backup_retention_period = 1` thay vì 7 (giảm snapshot storage)
- [ ] Staging: single-AZ (không Multi-AZ) — tiết kiệm 50% RDS cost
- [ ] Redis dev: `cache.t3.micro` hoặc `cache.t3.small`
- [ ] ElastiCache dev: 1 node (không replica) — tiết kiệm 50%
- [ ] Production: Spot instance cho EKS nodes (tiết kiệm 60-70%) — data layer không dùng Spot
- [ ] Storage: `gp3` thay vì `gp2` (10% cheaper, 4x throughput)
- [ ] Secrets Manager: xóa secret không dùng sau lab
- [ ] Dev cluster: shutdown khi không dùng (EKS không có auto-shutdown → dùng ASG scale to 0)

---

## 11. Common Errors & Fixes

### Error 1: RDS `connection refused` hoặc `timeout`

**Nguyên nhân:**
1. Security group không allow port 5432 từ EKS node
2. RDS chưa finished creating (takes 10-15 phút)
3. `publicly_accessible = false` và EKS node không trong same VPC
4. Wrong endpoint (dùng IP thay vì DNS)

**Fix:**
```bash
# Verify SG allows traffic
aws ec2 describe-security-groups \
  --group-ids sg-xxxx \
  --query 'SecurityGroups[0].IpPermissions'

# Verify RDS is available
aws rds describe-db-instances \
  --db-instance-identifier capstone-dev-postgres \
  --query 'DBInstances[0].DBInstanceStatus'
# Expected: "available"

# Get correct endpoint (always use this, not IP)
aws rds describe-db-instances \
  --db-instance-identifier capstone-dev-postgres \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text
```

### Error 2: ESO `ClusterSecretStore` not ready — `noJWTSigner`

**Nguyên nhân:**
1. IRSA annotation không đúng hoặc không tồn tại trên ESO ServiceAccount
2. ServiceAccount không cùng namespace với ESO pod
3. ESO pod không mount được JWT token

**Fix:**
```bash
# Verify ServiceAccount có đúng annotation
kubectl get sa external-secrets -n external-secrets \
  -o jsonpath='{.metadata.annotations}'
# Expected: eks.amazonaws.com/role-arn: arn:aws:iam::...:role/...

# Verify ESO pod có token mount
kubectl get pod -n external-secrets -l app.kubernetes.io/name=external-secrets \
  -o jsonpath='{.items[0].spec.serviceAccountName}'

# Verify IRSA role tồn tại
aws iam get-role --role-name capstone-dev-external-secrets
```

### Error 3: ESO sync creates Secret but pod can't read it

**Nguyên nhân:**
1. ExternalSecret ở namespace khác với pod
2. Kubernetes RBAC: pod's ServiceAccount không có quyền read Secret
3. Pod chạy trước khi Secret được tạo

**Fix:**
```bash
# Verify Secret tồn tại trong pod's namespace
kubectl get secret api-service-db-secret -n api-service-prod

# Verify ESO sync status
kubectl get externalsecret api-service-db-secret -n api-service-prod
# Expected: SecretStoreRef → Ready True, Synced True

# Restart pod (trigger secret reload)
kubectl rollout restart deployment api-service -n api-service-prod

# If RBAC issue: grant role to SA
kubectl create rolebinding api-service-read-secrets \
  --role=system:controller:job-controller \
  --serviceaccount=api-service-prod:api-service \
  -n api-service-prod
# Or just use default SA which has cluster-admin in dev
```

### Error 4: PostgreSQL Helm `CrashLoopBackOff` — `FDW`

**Nguyên nhân:**
1. PVC không thể bound (storage class không tồn tại)
2. Init container fail (wrong password reference)
3. Persistent volume không có đủ capacity

**Fix:**
```bash
kubectl describe pod postgres-primary-0 -n data | grep -A 5 "Warning"

# Check PVC status
kubectl get pvc -n data
# Expected: Bound

# Check storage class
kubectl get storageclass
# Use 'standard' for kind, 'gp3' for EKS

# Reinstall with correct storage class
helm upgrade postgres bitnami/postgresql \
  --namespace data \
  --set primary.persistence.storageClass=gp3 \
  --reuse-values
```

### Error 5: `random_password` creates new password on every apply

**Fix:**
```hcl
# Use manage_master_user_password = true (AWS-managed)
# Or store password in Secrets Manager and use data source
data "aws_secretsmanager_secret_version" "postgres" {
  secret_id = aws_secretsmanager_secret.postgres.id
}

# For Helm: use existingSecret
--set auth.existingSecret=postgres-credentials
# Create the secret manually first
kubectl create secret generic postgres-credentials \
  --from-literal=password=$(openssl rand -base64 32)
```

### Error 6: ElastiCache cluster stuck in "creating"

**Nguyên nhân:**
1. Không đủ subnet IPs
2. Security group không cho phép replication traffic
3. Cache subnet group không đúng

**Fix:**
```bash
# Check cluster status
aws elasticache describe-replication-groups \
  --replication-group-id capstone-dev-redis \
  --query 'ReplicationGroups[0].Status'

# Verify subnet group
aws elasticache describe-cache-subnet-groups \
  --cache-subnet-group-name capstone-dev-redis-subnet

# Check available IPs in subnets
aws ec2 describe-subnets \
  --subnet-ids $SUBNET_IDS \
  --query 'Subnets[].AvailableIpAddressCount'
# Need at least 2 IPs per node type (primary + replica)
```
