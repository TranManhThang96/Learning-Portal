# Day 31 — Data Layer & Secrets: Exercises

---

## Challenge 1: PostgreSQL Point-in-Time Recovery Test

**Mục tiêu:** Test restore capability — backup không test restore = backup không đáng tin.

**Scenario:** Bạn có 1 bảng `orders` trong PostgreSQL. Sau khi backup, có người chạy `DELETE FROM orders WHERE id > 100` (xóa 50 records). Cần restore bảng `orders` về trạng thái trước khi xóa.

**Setup (Mode A — Helm PostgreSQL):**

```bash
# 1. Cài PostgreSQL (đã làm trong lab)
helm install postgres bitnami/postgresql -n data --wait

# 2. Tạo database + table + data
PGPASSWORD=$POSTGRES_PASSWORD psql -h postgres-primary.data.svc.cluster.local \
  -U capstone_user -d capstone_db <<'SQL'
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  product TEXT,
  quantity INT,
  created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO orders (product, quantity)
SELECT 'Product-' || i, (random() * 100)::int
FROM generate_series(1, 150) AS i;

SELECT count(*) as before_delete FROM orders;
-- Expected: 150
SQL

# 3. Ghi lại thời điểm hiện tại (làm backup point)
BACKUP_TIME=$(date -u +"%Y-%m-%d %H:%M:%S")
echo "Backup time: $BACKUP_TIME"

# 4. Simulate disaster: xóa records
PGPASSWORD=$POSTGRES_PASSWORD psql -h postgres-primary.data.svc.cluster.local \
  -U capstone_user -d capstone_db -c "DELETE FROM orders WHERE id > 100;"

PGPASSWORD=$POSTGRES_PASSWORD psql -h postgres-primary.data.svc.cluster.local \
  -U capstone_user -d capstone_db -c "SELECT count(*) as after_delete FROM orders;"
-- Expected: 100 (50 records bị mất)
```

**Yêu cầu:**
1. Dùng `pg_dump` tạo backup trước thời điểm xóa (từ backup PVC hoặc pgBackRest)
2. Restore bảng `orders` về trạng thái 150 records (không restore toàn bộ DB)
3. Verify: `SELECT count(*) FROM orders` = 150
4. Ghi lại: RPO thực tế = bao lâu? Có đạt mục tiêu RPO < 5 phút không?

**Output cần nộp:**
- File `challenge1/pitr-process.md` mô tả step-by-step
- File `challenge1/backup-command.sh` script backup
- File `challenge1/restore-command.sh` script restore chỉ bảng `orders`
- Bảng so sánh: RPO/RTO achieved vs target

**Hints:**
- `pg_dump` export to SQL file → có thể filter chỉ restore table cụ thể
- `pg_restore` với option `-t table_name` restore chỉ 1 table
- PVC của PostgreSQL: `kubectl get pvc -n data`

---

## Challenge 2: Redis Cluster Migration — Local to ElastiCache

**Mục tiêu:** Migrate data từ Redis local (Helm) sang ElastiCache Redis mà không downtime.

**Scenario:** Capstone dev environment đang chạy Redis Helm trong kind. Team muốn migrate lên ElastiCache (AWS) để production simulation. Ứng dụng đang dùng Redis cho session storage và job queue. Cần migrate data hiện có mà không mất session.

**Setup:**
```bash
# 1. Chạy Redis local (Helm, đã có từ lab)
helm install redis bitnami/redis -n data --wait

# 2. Ghi data mẫu vào Redis local
REDIS_PASSWORD=$(kubectl get secret redis-credentials -n data \
  -o jsonpath='{.data.password}' | base64 -d)
redis-cli -h redis-master.data.svc.cluster.local -p 6379 \
  -a "$REDIS_PASSWORD" <<'EOF'
SET session:user:001 '{"id":1,"name":"Alice","role":"admin"}'
SET session:user:002 '{"id":2,"name":"Bob","role":"developer"}'
SET session:user:003 '{"id":3,"name":"Charlie","role":"viewer"}'
SET queue:jobs '{"type":"email","to":"alice@example.com"}'
SET counter:pageview "100"
KEYS *
EOF

# 3. Deploy "API service" ghi liên tục vào Redis
# (simulate active session)
```

**Yêu cầu:**
1. Thiết kế migration plan không downtime cho production-like scenario
2. Tạo Redis Replication Group endpoint (`REDIS_HOST`) từ Terraform (ElastiCache)
3. Implement dual-write pattern: ghi vào cả Redis local VÀ ElastiCache trong transition period
4. Switch-over: cập nhật `REDIS_URL` secret → ESO sync → pod restart
5. Verify data đầy đủ ở ElastiCache (so sánh `KEYS *` ở 2 Redis)
6. Cleanup: gỡ Redis Helm sau khi migration hoàn tất

**Output cần nộp:**
- File `challenge2/migration-plan.md` với step-by-step process
- File `challenge2/dual-write-script.sh` script đọc local → ghi cả 2
- File `challenge2/switchover.sh` ESO manifest + verification
- Timeline: pre-migration → dual-write → switch-over → cleanup
- Risk assessment: điều gì có thể sai trong migration này?

**Hints:**
- Dual-write: thay vì app ghi vào 1 Redis, app ghi vào 2 Redis endpoints
- Dùng `redis-cli --pipe` hoặc Python script để migrate keys
- ESO refresh interval: 1h — nếu cần nhanh hơn, set `refreshInterval: 1m`
- Redis AUTH: ElastiCache production nên bật AUTH token

---

## Challenge 3: Design ESO Secret Rotation Strategy

**Mục tiêu:** Thiết kế automated secret rotation cho PostgreSQL và Redis mà không restart pod.

**Scenario:** Compliance team yêu cầu:
- Database password phải rotate 90 ngày
- Redis password phải rotate 90 ngày
- Rotation không được gây downtime cho API service
- Audit log phải capture mọi rotation event

**Yêu cầu:**
1. Vẽ architecture diagram cho rotation flow (bằng ASCII)
2. Thiết kế rotation cho PostgreSQL (AWS Secrets Manager + Lambda):
   - Lambda trigger: CloudWatch Event (scheduled)
   - Step: Generate new password → Update ASM → Update RDS → Verify → Delete old
   - Grace period: 24 giờ (old password vẫn work trong grace period)
3. Thiết kế rotation cho Redis:
   - ElastiCache native rotation không hỗ trợ AUTH token tự động
   - Phương án: manual rotation script hoặc Lambda + ElastiCache API
4. ESO integration: sau rotation, ESO tự động sync secret mới
5. App graceful reload: app phải detect password change mà không restart
   - Gợi ý: app đọc secret từ file (projected volume) thay vì env var
   - Hoặc: /health endpoint triggers secret reload
6. Audit: CloudTrail log mọi ASM secret update

**Output cần nộp:**
- File `challenge3/rotation-architecture.md` ASCII diagram
- File `challenge3/postgres-rotation-lambda.py` Lambda function (outline/pseudocode)
- File `challenge3/redis-rotation-lambda.py` Lambda function (outline/pseudocode)
- File `challenge3/graceful-reload-deployment.yaml` Kubernetes manifest
- File `challenge3/audit-check.sh` script verify rotation log in CloudTrail

**Hints:**
- ASM native rotation hỗ trợ MySQL và RDS PostgreSQL (built-in Lambda)
- For Redis AUTH token: dùng ElastiCache API `modify-replication-group` + Lambda
- Grace period: lưu 2 version password trong ASM, app đọc latest
- ESO `refreshInterval: 5m` đủ nhanh cho rotation

---

## Challenge 4: Debug — Pod Can't Connect to RDS (Connection Timeout)

**Mục tiêu:** Debug network connectivity issue từ EKS pod đến RDS.

**Given:** Pod `api-service-xxxxx` đang CrashLoopBackOff. Logs:

```
Error: could not connect to database
  FATAL: password authentication failed for user "capstone_admin"
```

Wait — đó là auth fail. Sau khi fix password, logs:

```
Error: could not connect to database
  could not connect to server: Connection timed out
    Is the server running on host "10.0.1.100" and accepting
    TCP/IP connections on port 5432?
FATAL: could not connect to database
```

**Yêu cầu:** Debug step-by-step, xác định root cause + fix.

**Debug checklist:**

1. **Layer 1: EKS → RDS Network path**
   - EKS node nằm trong VPC nào? RDS nằm trong VPC nào?
   - Kiểm tra: EKS nodes có security group cho phép egress đến RDS SG không?
   - Kiểm tra: RDS SG có ingress rule cho phép traffic từ EKS SG?

2. **Layer 2: DNS resolution**
   - Pod resolve được RDS endpoint không?
   - `kubectl exec api-service-xxxxx -- nslookup capstone-dev-postgres.xxxx.us-east-1.rds.amazonaws.com`

3. **Layer 3: Security group verification**
   - RDS SG: ingress port 5432, source = EKS SG?
   - EKS SG: egress port 5432 đến RDS SG?

4. **Layer 4: Nếu dùng VPC Endpoint (không NAT)**
   - VPC Endpoint cho RDS Interface Endpoint có tồn tại không?
   - Nếu không: pods phải đi qua NAT Gateway đến internet → đến RDS (inefficient)

5. **Layer 5: VPC peering / Transit Gateway**
   - Nếu EKS và RDS ở 2 VPC khác nhau: có VPC peering không?

**Output cần nộp:**
- File `challenge4/debug-flow.md` — 5 layer checklist + commands
- File `challenge4/root-cause-analysis.md` — root cause + fix applied
- File `challenge4/fixed-sg-terraform.tf` — correct security group rules
- Verification: pod connect được RDS sau fix

**Hints:**
- RDS `publicly_accessible = false` + private subnet → EKS phải cùng VPC
- Security group rule phải dùng security group ID, không phải CIDR
- DNS resolution: RDS endpoint always resolves to private IP (trong VPC)

---

## Challenge 5: Multi-Service Secrets Management

**Mục tiêu:** Thiết kế secrets structure cho 3 microservice + shared secrets.

**Scenario:** Capstone có 3 microservice:

| Service | DB | Cache | External API |
|---|---|---|---|
| `api-service` | PostgreSQL (users, orders) | Redis (session) | Stripe API key |
| `worker-service` | PostgreSQL (job results) | Redis (job queue) | SQS queue URL |
| `frontend-service` | None | Redis (rate limit) | None |

Mỗi service cần credentials khác nhau. Có shared secrets (PostgreSQL credentials) và per-service secrets.

**Yêu cầu:**

1. **Thiết kế ASM secret structure:**

```
capstone/
├── shared/
│   ├── postgres-main/     # Admin credentials, dùng bởi migrations
│   └── postgres-readonly/ # Dùng bởi read replica
├── api-service/
│   ├── database/         # App-level credentials (limited grants)
│   ├── redis/
│   └── stripe-api/
├── worker-service/
│   ├── database/
│   ├── redis/
│   └── sqs/
└── frontend-service/
    └── redis/
```

2. **ESO ExternalSecret manifests cho từng service**

3. **IAM least-privilege cho ESO IRSA role:**
   - Mỗi service chỉ đọc secret của mình, không đọc secret của service khác
   - Dùng resource-level policy trong ASM

4. **Kubernetes RBAC:**
   - Mỗi namespace có ESO ServiceAccount với annotation IRSA
   - ClusterSecretStore hoặc SecretStore (namespace-scoped)

5. **Database user separation:**
   - `capstone_api` user: chỉ truy cập `api_*` tables
   - `capstone_worker` user: chỉ truy cập `jobs_*` tables
   - `capstone_migration` user: full access, chỉ dùng cho migration job

**Output cần nộp:**
- File `challenge5/secret-structure.md` ASCII tree
- File `challenge5/asm-policies.tf` Terraform: ASM secret + resource policies
- File `challenge5/irsa-roles.tf` Terraform: separate IAM role per service
- File `challenge5/external-secrets/` directory: ESO manifests cho 3 services
- File `challenge5/db-users.sql` SQL: 3 database users + grants
- Security analysis: nếu `frontend-service` bị compromised, damage radius là gì?

---

## Challenge 6: Backup Automation for Local PostgreSQL

**Mục tiêu:** Tự động hóa backup cho PostgreSQL Helm (local) với pgBackRest + S3.

**Scenario:** Không có RDS, dùng Helm PostgreSQL trong kind. Cần:
- Automated full backup: hàng ngày lúc 3:00 AM
- Continuous WAL archiving: mỗi 5 phút
- Backup retention: giữ 7 backups
- Restore test: hàng tuần tự động
- Backup verification: email/Slack notification khi backup fail

**Yêu cầu:**
1. Cài pgBackRest repository container (sidecar hoặc init container)
2. Cấu hình pgBackRest backup sang S3 (LocalStack S3 cho dev)
3. Tạo Kubernetes CronJob cho backup hàng ngày
4. Tạo CronJob cho backup verification hàng tuần
5. Tạo AlertingRule cho Prometheus: backup failure → Slack notification
6. Test restore: tạo test PVC → restore backup → verify data

**Output cần nộp:**
- File `challenge6/pgbackrest-values.yaml` — Helm values cho pgBackRest sidecar
- File `challenge6/backup-cronjob.yaml` — Kubernetes CronJob (daily full backup)
- File `challenge6/wal-archive-cronjob.yaml` — Kubernetes CronJob (WAL archive every 5m)
- File `challenge6/verify-restore-cronjob.yaml` — Kubernetes CronJob (weekly restore test)
- File `challenge6/alert-rule.yaml` — Prometheus alerting rule
- File `challenge6/backup-runbook.md` — runbook: làm sao restore khi cần

**Hints:**
- pgBackRest có official Docker image: `quay.io/pgdata/pgbackrest`
- Kubernetes CronJob: `successfulJobsHistoryLimit: 7`, `failedJobsHistoryLimit: 3`
- LocalStack S3 endpoint: `http://localhost:4566` (hoặc service endpoint trong K8s)
- Backup verification: `pgbackrest info` để check backup status

---

## Challenge 7: Design Review — Secrets Management Architecture

**Mục tiêu:** Review và critique architecture hiện tại, đề xuất improvements.

**Given Architecture (current state):**

```
Developer → GitHub → ArgoCD → Kubernetes
                                    │
                            ┌───────┴───────┐
                       ┌────▼────┐   ┌───▼────┐
                       │ ESO     │   │ ESO    │
                       │ Local   │   │ ASM    │
                       │ (Mode A)│   │ (Mode B)│
                       └─────────┘   └───┬────┘
                                          │
                              ┌───────────▼────────┐
                              │  ASM Secret Store  │
                              │  capstone/prod/api │
                              │  (1 big secret)    │
                              └────────────────────┘
```

**Issues to identify:**

1. **Single secret, single point of failure**: 1 ASM secret chứa tất cả credentials
2. **No rotation**: password generated once, never rotated
3. **No per-service least-privilege**: 1 ESO IRSA role đọc tất cả secret
4. **Connection string hardcoded in ASM**: không tách rõ database vs application credentials
5. **No secret versioning**: không track ai đã thay đổi secret
6. **Mode A vs Mode B inconsistency**: 2 different ESO setup không có unified secret management

**Yêu cầu:**

1. **Critique architecture**: đánh giá 5 issues trên (severity, impact, likelihood)
2. **Propose improved architecture** với ASCII diagram:
   - ASM secret per service + per environment
   - ESO ClusterSecretStore có IAM resource policy giới hạn theo secret path
   - IRSA role per service với resource-level permission
   - Automated rotation với Lambda
   - Secret versioning + audit log
3. **Migration plan**: làm sao migrate từ current state sang improved state mà không downtime
4. **Cost impact**: so sánh cost hiện tại vs improved (ASM pricing theo số secret)
5. **Security assessment**: improved architecture pass được những compliance nào?

**Output cần nộp:**
- File `challenge7/critique.md` — 5 issues scored (severity + likelihood)
- File `challenge7/improved-architecture.md` — improved ASCII diagram + explanation
- File `challenge7/migration-plan.md` — zero-downtime migration steps
- File `challenge7/cost-comparison.md` — current vs improved cost breakdown
- File `challenge7/compliance-matrix.md` — SOC2/HIPAA/PCI-DSS checklist

---

## Bonus Challenge: Cross-Region DR Setup

**Mục tiêu:** Thiết lập DR infrastructure cho data layer, multi-region.

**Scenario:** Production chạy ở `us-east-1`. Cần DR ở `us-west-2`. RPO < 24h, RTO < 2h.

**Yêu cầu:**
1. **RDS Cross-Region Read Replica** (async replication):
   - Primary: `us-east-1`
   - Replica: `us-west-2`
   - Promotion: convert replica thành standalone DB khi primary down
2. **ElastiCache Global Datastore** (2021+ feature):
   - Primary: `us-east-1`
   - Secondary: `us-west-2`
   - Automatic async replication
3. **Secrets Manager replication**: manual cross-region secret copy
4. **DR runbook**: step-by-step khi primary region fail

**Output cần nộp:**
- File `bonus/dr-architecture.md` — ASCII diagram multi-region
- File `bonus/rds-replica.tf` — Terraform: cross-region RDS replica
- File `bonus/elasticache-global.tf` — Terraform: ElastiCache Global Datastore
- File `bonus/dr-runbook.md` — runbook: primary fail → DR failover

**Cost impact note:** Cross-region replication tốn chi phí data transfer: ~$0.02/GB (us-east-1 → us-west-2). Với 50GB DB, 7 ngày retention: ~$7/tuần.

---

## Submission Checklist

Mỗi challenge cần nộp:

- [ ] Source code (Terraform, Kubernetes YAML, SQL)
- [ ] Giải thích ngắn (3-5 dòng) tại sao chọn approach đó
- [ ] Security considerations cho solution
- [ ] Estimated cost impact (nếu có)
- [ ] Expected output sau khi apply/run

**Total: 7 challenges + 1 bonus. Mỗi challenge = 1 directory trong `exercises/day-31/`**
