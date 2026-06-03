# Day 35 — Disaster Recovery, Final Demo, Runbook & Retrospective

> **Ngày cuối cùng — Capstone Production-Grade**
> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Hoàn thành Day 28-34 (full platform từ network đến CI/CD)
> **Output:** Runbook hoàn chỉnh + DR checklist + Final demo script + Retrospective document + Cleanup toàn bộ resource

---

## 1. Mục tiêu ngày học

- Mô phỏng được 6 disaster scenario phổ biến nhất trong hệ microservices GitOps-based (mất cluster, mất ArgoCD, sai secret, deployment lỗi, Terraform state lỗi, rollback app)
- Phân biệt được RTO (Recovery Time Objective) và RPO (Recovery Point Objective) — hai chỉ số quyết định DR strategy
- Xây dựng được DR matrix cho từng component (cluster, data, ArgoCD, secrets, app) với action plan cụ thể
- Viết được runbook có checkpoint rõ ràng, có rollback step, có verification sau mỗi bước
- Thực hiện final demo end-to-end: từ zero đến full platform restored
- Đánh giá được cái gì production-ready, cái gì chỉ là simulation, và next steps cụ thể
- Cleanup toàn bộ resource (Mode B) — bắt buộc sau ngày cuối

---

## 2. Bối cảnh thực tế

### Chuyện thật: Không có DR plan thì incident trở thành disaster

Week 5 xây dựng platform hoàn chỉnh suốt 7 ngày. Không có DR plan, toàn bộ effort đó nằm ở một sợi chỉ:

```
Ngày thường:
  Dev quên xóa --debug flag → secrets log ra CloudWatch → AWS breach → cluster delete
  Terraform state lock → người khác force unlock → state corruption → 3 ngày restore
  ArgoCD app misconfigured → cascade delete resource → 2 tiếng downtime không có rollback plan

Đêm hoặc cuối tuần:
  Kubernetes node fail → không có PDB → pod không reschedule → 4 tiếng incident
  RDS fail → không backup tested → restore từ backup 8 tiếng → RTO missed
  ArgoCD crash → không có backup → phải manually recreate 50+ Application
```

### Tại sao ngày cuối là DR, không phải thêm feature

Một platform không có DR plan là một platform chưa hoàn thành. DR không phải "nice to have" — nó là criteria cuối cùng để answer câu hỏi: *"Nếu đêm nay mất hết, mất bao lâu để restore?"*

Team có DR plan và tested runbook:
- RTO: 30 phút (ArgoCD re-bootstrap từ Git, cluster từ Terraform state backup)
- RPO: 15 phút (PostgreSQL backup 15 phút/lần, Redis RDB)

Team không có DR plan:
- RTO: undefined — thường 4-24 giờ
- RPO: undefined — dữ liệu mất hoàn toàn hoặc phải manual recovery

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 RTO và RPO — hai chỉ số quyết định DR strategy

**RTO (Recovery Time Objective):** Thời gian tối đa cho phép để restore service từ lúc incident xảy ra. Ví dụ: RTO = 1 giờ nghĩa là service phải back online trong 1 giờ.

**RPO (Recovery Point Objective):** Lượng dữ liệu tối đa cho phép mất — tính bằng thời gian. Ví dụ: RPO = 15 phút nghĩa là chấp nhận mất tối đa 15 phút dữ liệu gần nhất.

```
Timeline của một incident:

t=0 (incident xảy ra) ──── RPO boundary ──── t=now (restore hoàn tất) ──── RTO boundary
     │                              │                    │
     │  Data trước RPO: CÓ          │  Data trước RTO:   │
     │  Data sau RPO: MẤT           │  Service: UP       │
     └──────────────────────────────┴────────────────────┘
                                    ↑
                              Đây là thời gian cần phải restore
```

### 3.2 DR Matrix cho Capstone Platform

| Component | Failure Mode | RTO Target | RPO Target | Recovery Action |
|-----------|-------------|------------|------------|-----------------|
| **Cluster (EKS/kind)** | Node fail / AZ fail / Cluster delete | 15-30 phút | 0 (stateless app) | Terraform apply (recreate) hoặc kind restore |
| **ArgoCD** | Crash / Pod delete / Namespace delete | 10-15 phút | 0 (config as code) | Bootstrap từ Git + ESO restore |
| **ArgoCD Config** | Application resource xóa nhầm | 5 phút | 0 | ArgoCD export/import hoặc Git revert |
| **Secrets** | Secret sai / rotate fail / ESO down | 5-10 phút | 0 | Update AWS Secrets Manager / ESO sync |
| **Deployment lỗi** | Bad image tag / bad config / cascade fail | 3-5 phút | 0 | ArgoCD rollback (1 click) |
| **Terraform State** | Lock / corruption / nhầm delete | 30-60 phút | Varies | State backup restore + re-apply |
| **Application data** | DB lỗi / disk full / data corruption | 30-60 phút | 15 phút | RDS automated backup restore + point-in-time |
| **CI/CD Pipeline** | GitHub Actions fail / credential expire | 10-15 phút | 0 | Recreate OIDC role / re-run workflow |

### 3.3 Backup Hierarchy

```
Backup Layers (từ low-level đến high-level):

Layer 1: Kubernetes persistent data
  └── PVC snapshot (nếu có EBS CSI driver)
  └── Database dump (pg_dump, redis-cli SAVE)

Layer 2: Application config
  └── ArgoCD export (argocd admin export)
  └── Kubernetes resource manifests (kubectl get all -o yaml)
  └── Helm values (Git repo, luôn có)

Layer 3: Platform config
  └── Terraform state backup (S3 versioning)
  └── ESO SecretStore / ClusterSecretStore YAML
  └── Ingress / Certificate config

Layer 4: Infrastructure
  └── VPC / Network config (Terraform state)
  └── RDS automated backup (AWS managed, 1-35 ngày retention)
  └── ElastiCache backup (daily automatic snapshot)
```

### 3.4 Disaster Scenarios chi tiết

#### Scenario 1: Mất Cluster (Cluster Deleted / AZ Failure)

**Triệu chứng nhận biết:**
```
# kubectl không kết nối được
The connection to the server <endpoint> was refused

# AWS Console: EKS cluster bị xóa hoặc không accessible
# hoặc: tất cả node báo NotReady cùng lúc
```

**Root cause phổ biến:**
- Terraform destroy nhầm môi trường (staging vs production)
- AWS account bị compromise
- Human error (xóa cluster thay vì xóa namespace)
- AZ outage nghiêm trọng

**Recovery procedure:**
1. Verify cluster không tồn tại: `aws eks describe-cluster --name capstone-dev`
2. Nếu là Terraform-managed: `cd capstone-infra/terraform/envs/prod && terraform apply`
3. Nếu là kind local: `kind create cluster --config kind-config.yaml`
4. Recreate IAM OIDC provider cho IRSA
5. Recreate IRSA roles (ESO, ALB Controller, cluster-autoscaler)
6. ArgoCD bootstrap: `kubectl apply -f bootstrap/root-app.yaml`
7. ArgoCD tự sync toàn bộ app từ Git → thời gian: 5-10 phút

**Prevention:**
- `prevent_destroy = true` trong Terraform lifecycle cho production cluster
- IAM policy hạn chế delete cluster
- Terraform state locking nghiêm ngặt
- Backup ArgoCD config trước mỗi major change

#### Scenario 2: Mất ArgoCD (ArgoCD Deleted / CrashLoopBackOff)

**Triệu chứng nhận biết:**
```
# ArgoCD API server không respond
argocd login argocd.example.com --grpc-web
  FATA[0000] rpc error: code = Unavailable desc = connection refused

# ArgoCD pod trong crash loop
kubectl get pods -n argocd
  argocd-server-xxx   CrashLoopBackOff
  argocd-repo-server-xxx   CrashLoopBackOff
```

**Root cause phổ biền:**
- Namespace argocd bị xóa nhầm
- Storage PVC bị delete
- Update configmap gây crash
- Helm chart upgrade lỗi

**Recovery procedure:**
1. Kiểm tra ArgoCD namespace: `kubectl get ns argocd`
2. Nếu namespace mất: tạo lại + apply manifests
3. Restore credentials từ backup (admin password từ Secret hoặc SSO config)
4. Verify ArgoCD cluster credentials: `argocd cluster list`
5. ArgoCD tự reconcile các Application sau khi back online
6. Nếu Application out-of-sync sau restore: `argocd app sync --all`

**Prevention:**
- ArgoCD nên nằm trong separate dedicated namespace, không nằm trong app's sync scope
- Backup ArgoCD config: `argocd admin export > argocd-backup-$(date +%Y%m%d).yaml`
- Quản lý ArgoCD qua Git (App of Apps pattern) — ngày 21 đã làm

#### Scenario 3: Sai Secret (Secret Misconfiguration / Rotation Failure)

**Triệu chứng nhận biết:**
```
# Pod không start được, lỗi secret missing
Events:
  Warning  Failed     5s (x3 over 15s)  kubelet  Error: secret "db-password" not found

# Application liên tục restart, lỗi auth
# Frontend: 500 Internal Server Error - authentication failed
# Worker: psycopg2.OperationalError: password authentication failed
```

**Root cause phổ biến:**
- ESO SyncPolicy = Never (quên apply)
- AWS Secrets Manager secret bị xóa
- Secret rotation không sync across replicas
- ESO CRD SecretStore reference sai region/account

**Recovery procedure:**
1. Identify pod đang fail: `kubectl get pods -A | grep -v Running`
2. Check ESO status: `kubectl get externalsecret -A`
3. Verify secret tồn tại trong AWS Secrets Manager / vault
4. Force ESO sync: `kubectl annotate externalsecret <name> force-sync=$(date +%s)`
5. Restart pod: `kubectl rollout restart deployment api-service -n apps`
6. Verify secret đúng: `kubectl get secret db-password -n apps -o yaml`

**Prevention:**
- Luôn dùng ESO với `refreshInterval: 1h` hoặc `force-sync` annotation
- Alert khi ESO SecretStore ở degraded state
- Test secret rotation trước khi apply production
- Backup secret reference trong Git (encrypted với SOPS)

#### Scenario 4: Deployment Lỗi (Bad Deployment / Cascade Failure)

**Triệu chứng nhận biết:**
```
# ArgoCD Application out-of-sync với health error
argocd app get api-service
  Status:  OutOfSync  Health: Degraded

# Service không respond
curl api-service.internal/health
  HTTP 503 Service Unavailable

# ReplicaSet không ready
kubectl get rs -n apps
  NAME                DESIRED   CURRENT   READY
  api-service-v2      3         3         0    ← 0 ready
```

**Root cause phổ biến:**
- Image tag không tồn tại (nhầm `v1.2.3` thay vì `v1.2.2`)
- Resource limit quá thấp (OOMKilled)
- Readiness probe fail
- Breaking database migration

**Recovery procedure:**
1. Xem diff: `argocd app diff api-service`
2. Identify problematic resource: `kubectl describe deployment api-service -n apps`
3. Rollback ngay: `argocd app rollback api-service`
4. Hoặc sync về revision cũ: `argocd app sync api-service --revision PREV_REVISION`
5. Verify health: `argocd app get api-service`
6. Nếu là breaking migration: chạy rollback migration script

**Prevention:**
- ArgoCD auto-sync nên có `outOfSync` policy nhưng KHÔNG auto-prune khi chưa test
- Health check always on
- Pre-production staging test mandatory trước promotion
- Argo Rollouts cho canary deployment (Day 26 đã làm)

#### Scenario 5: Terraform State Lỗi (State Lock / Corruption / Accidental Delete)

**Triệu chứng nhận biết:**
```
# State lock
Error: Error acquiring the state lock
  Lock ID: <lock-id>
  Locked by: <another process>

# State drift nặng
terraform plan
  ~ update aws_eks_cluster.main
  ~ update aws_db_instance.main
  # 47 to destroy, 89 to add, 234 to change  ← DRIFT NẶNG

# State file mất
Error: Unable to locate state file
  Either the file "terraform.tfstate" has been deleted
  or the S3 bucket is inaccessible
```

**Root cause phổ biến:**
- `terraform apply` bị interrupt (ctrl+C, network fail)
- Lock timeout quá ngắn
- Nhầm workspace (production vs staging)
- S3 bucket bị delete hoặc IAM issue

**Recovery procedure:**
1. Thử unlock trước: `terraform force-unlock <LOCK_ID>`
2. Check S3 bucket tồn tại và accessible: `aws s3 ls s3://capstone-tf-state/`
3. Nếu state file mất: restore từ S3 versioning `aws s3api get-object-version`
4. Nếu state corrupt: `terraform state push` với backup file
5. Refresh state: `terraform refresh`
6. Re-apply plan để sync: `terraform plan` → `terraform apply`

**Prevention:**
- S3 bucket versioning BẬT (automatic backup mỗi state write)
- DynamoDB lock với timeout đủ lớn
- `terraform state pull` thủ công trước mỗi major apply
- Gitignore terraform.tfstate, terraform.tfstate.backup
- Backup script chạy định kỳ: `aws s3 cp s3://bucket/terraform.tfstate ./backups/`

#### Scenario 6: Rollback Application

**Triệu chứng nhận biết:**
```
# Vừa promote app lên production
# Health check fail → user báo lỗi
# Cần rollback ngay

argocd app get api-service
  SyncStatus:   Synced
  Health:       Degraded
  Revision:     v2.1.0  ← version mới có vấn đề
```

**Recovery procedure (3 cách):**

**Cách 1 — ArgoCD rollback (recommended):**
```bash
# Xem lịch sử sync
argocd app history api-service

# Rollback về revision cũ
argocd app rollback api-service

# Hoặc sync với revision cụ thể
argocd app sync api-service --revision <PREV_REVISION>
```

**Cách 2 — Git revert (permanent rollback):**
```bash
# Revert git commit
git revert HEAD
git push

# ArgoCD tự sync → app rollback tự động
```

**Cách 3 — Argo Rollouts canary rollback (nếu dùng Rollouts):**
```bash
# Abort active rollout
kubectl argo rollouts abort api-service

# Full rollback
kubectl argo rollouts undo api-service
```

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 DR Strategy: Active-Active vs Active-Passive vs Backup-Restore

| Criteria | Active-Active | Active-Passive | Backup-Restore |
|----------|--------------|----------------|----------------|
| RTO | ~0 (instant failover) | 5-15 phút | 30 phút - 4 giờ |
| RPO | ~0 (sync replication) | 0-5 phút | 15 phút - 24 giờ |
| Cost | 2× infrastructure | 1.5× infrastructure | 1× (chỉ backup) |
| Complexity | Cao nhất | Trung bình | Thấp nhất |
| Phù hợp | Tier-1 service, finance | Production thường | Dev/staging, non-critical |
| Capstone mode | Mode B multi-region (expensive) | Mode B single-region (recommended) | Mode A kind (simulation) |

**Capstone reality check:**
- Mode A (kind): Chỉ simulation được DR. RTO/RPO không phản ánh production vì kind cluster restore = `kind create cluster` (~5 phút). Đây là learning exercise, không phải production DR.
- Mode B (AWS): Thực sự gần production. EKS restore = Terraform apply (~15-30 phút), RDS point-in-time ~10-15 phút, ArgoCD bootstrap ~5-10 phút. RTO thực tế ~30-45 phút.

### 4.2 ArgoCD Backup: Velero vs ArgoCD Admin Export vs Git-based

| Method | What it backs up | Speed | Restore complexity | Automation |
|--------|----------------|-------|-------------------|------------|
| **Velero** | Full cluster state (包括 PersistentVolume) | Chậm (full snapshot) | Phức tạp (must match cluster version) | Scheduled backup |
| **ArgoCD Admin Export** | ArgoCD config, Application, Repo credentials | Nhanh (< 1 phút) | Dễ (kubectl apply -f backup.yaml) | Scriptable |
| **Git-based (App of Apps)** | Application manifests (không có credentials) | Tức thì (pull from Git) | Dễ nhất (ArgoCD tự reconcile) | Native GitOps |
| **ArgoCD Backup Operator** | Incremental backup of all ArgoCD resources | Trung bình | Trung bình | CRD-based |

**Recommendation:**
- Backup ArgoCD config hàng ngày: `argocd admin export | gzip > argocd-backup-$(date +%Y%m%d).yaml.gz`
- Store backup trong S3 với lifecycle: `30 ngày retention`
- ArgoCD Application luôn Git-managed → không cần Velero cho Application layer
- Velero chỉ cần nếu có PersistentVolume với data quan trọng

### 4.3 Terraform State Safety Strategy

**Critical principle: State file là source of truth. Backup trước khi apply bất kỳ thay đổi lớn nào.**

```
State Safety Checklist:

□ S3 bucket versioning BẬT (automatic historical versions)
□ DynamoDB lock table TỒN TẠI trước khi apply
□ Backup local state trước apply:
    aws s3 cp s3://bucket/terraform.tfstate ./backups/terraform.tfstate.$(date +%Y%m%d%H%M%S)
□ Never run terraform destroy trên production mà không có backup
□ Never disable state locking
□ Never modify state file thủ công (dùng terraform state commands)
□ Pipeline: terraform plan trong PR → terraform apply sau khi approve
□ State file không bao giờ commit vào Git
```

### 4.4 DR Testing: GameDay vs Simulation

| Type | Frequency | Scope | Real incident risk | Cost |
|------|-----------|-------|--------------------|------|
| **Tabletop exercise** | Monthly | Review runbook, không execute | 0 | ~2h engineer time |
| **GameDay simulation** | Quarterly | Thực sự delete/restore components | Low (isolated env) | ~4h + infra cost |
| **Chaos injection (LitmusChaos)** | CI/CD | Automated failure injection | Low | Tooling time |
| **Real DR drill** | Yearly | Full failover, real RTO/RPO measurement | High (có downtime thật) | Maximum |

**Capstone exercise hôm nay = Tabletop + GameDay hybrid:**
- Thực sự xóa và restore một số component (ArgoCD app, deployment)
- Mô phỏng bằng lời các scenario khác (cluster loss, state corruption)
- Measure thời gian restore để verify RTO target

### 4.5 Common Pitfalls và cách tránh

**Pitfall 1: Backup nhưng không test restore**
- Symptom: Backup tồn tại nhưng restore fail vì format cũ, missing dependencies
- Fix: Test restore quarterly bằng isolated environment

**Pitfall 2: ArgoCD không có namespace riêng**
- Symptom: ArgoCD bị cascade delete khi app team xóa namespace
- Fix: ArgoCD namespace `argocd` phải nằm ngoài app's sync scope, có `prune=false` cho infra resources

**Pitfall 3: Terraform state không có versioning**
- Symptom: Apply nhầm → state corrupt → không có backup để restore
- Fix: Bật S3 versioning + DynamoDB lock + backup script

**Pitfall 4: Database backup nhưng không test restore**
- Symptom: Backup "thành công" nhưng restore fail vì missing WAL file
- Fix: Monthly restore test đến isolated database

**Pitfall 5: Rollback plan không có cho breaking migration**
- Symptom: Migration chạy, deployment thành công, nhưng data corruption sau đó
- Fix: Migration rollback script phải đi kèm migration forward script

### 4.6 Cost implications của DR trong Capstone

```
DR component costs (Mode B):

1. S3 terraform state bucket:  ~$0.50/tháng (backup storage)
2. S3 ArgoCD backup bucket:    ~$0.50/tháng (backup storage)
3. RDS automated backup:      Included in RDS price ($0-30/tháng tùy instance)
4. ElastiCache backup:         Included in ElastiCache price
5. Velero (optional):         ~$10-20/tháng (EBS snapshot storage)
---
Total DR infrastructure:       ~$11-21/tháng (LOW cost, HIGH value)

Không có DR: 1 incident có thể gây 4-24h downtime
  = 4-24h developer time × $100-200/h = $400-4800 cost
  vs $11-21/tháng DR backup = $132-252/năm
  → ROI rõ ràng: DR backup cost <<< 1 incident cost
```

---

## 5. Hands-on Lab — 60 phút

### Lab Overview

```
Lab sequence:
  Part 1 (10 phút):  Backup ArgoCD config hiện tại
  Part 2 (10 phút):  Simulate ArgoCD app delete + restore bằng Git
  Part 3 (15 phút):  Simulate bad deployment + ArgoCD rollback
  Part 4 (10 phút):  Simulate Terraform state backup/restore (local state simulation)
  Part 5 (5 phút):   Export DR runbook + final demo checklist
  Part 6 (10 phút):  Full cleanup (Mode B destroy / Mode A kind delete)
```

### Prerequisites

```bash
# Verify đang ở capstone workspace
cd ~/capstone
ls -la

# Kiểm tra cluster accessible
kubectl cluster-info
argocd cluster list

# Kiểm tra ArgoCD logged in
argocd version --short

# Kiểm tra GitOps repos accessible
git remote -v
```

### Cảnh báo chi phí (Mode B)

```
⚠️  Mode B: Lab này chỉ THỰC SỰ simulate disaster. Không xóa production resources.

Nếu đang dùng Mode B:
- KHÔNG chạy terraform destroy trong lab
- Backup thay vì delete production state
- Chỉ xóa ArgoCD Application (Application ≠ underlying resources)
- Cleanup ở cuối lab = terraform destroy bắt buộc

Ước tính chi phí nếu quên cleanup:
- EKS: $73/ngày × 7 ngày = $511 (nếu quên destroy 1 tuần)
- RDS: $13-30/ngày × 7 = $91-210
```

---

### Part 1: Backup ArgoCD Config (10 phút)

**Bước 1.1 — Tạo backup directory**

```bash
mkdir -p ~/capstone/backups/$(date +%Y%m%d)
BACKUP_DIR=~/capstone/backups/$(date +%Y%m%d)
echo "Backup directory: $BACKUP_DIR"
```

**Bước 1.2 — Export ArgoCD full config**

```bash
# Export tất cả ArgoCD resources (Applications, AppProject, Repository credentials)
argocd admin export -o ${BACKUP_DIR}/argocd-backup-full.yaml

# Verify backup file tạo thành công
ls -lh ${BACKUP_DIR}/argocd-backup-full.yaml
wc -l ${BACKUP_DIR}/argocd-backup-full.yaml
```

**Expected output:**
```
-rw-r--r-- 1 user staff  12K  May 15 14:30  argocd-backup-full.yaml
# File phải chứa: Application, AppProject, Repository, Cluster, Secret (encrypted)
```

**Bước 1.3 — Backup ArgoCD repo credentials riêng**

```bash
# Lấy danh sách repo credentials
argocd repo list --output json | jq '.' > ${BACKUP_DIR}/argocd-repos.json

# Backup cluster secret (để add cluster lại nếu cần)
kubectl get secret argocd-cluster -n argocd -o yaml > ${BACKUP_DIR}/argocd-cluster-secret.yaml

cat ${BACKUP_DIR}/argocd-repos.json | jq '.[].url'
```

**Expected output:**
```
"https://github.com/your-org/capstone-platform"
"https://github.com/your-org/capstone-apps"
```

**Bước 1.4 — Backup Terraform state metadata (không phải state file)**

```bash
# Chỉ đọc, không sửa state
cd ~/capstone/capstone-infra/terraform/envs/dev

# List state resources (xem có gì trong state)
terraform state list | head -20

# Backup current state version
terraform state pull > ${BACKUP_DIR}/terraform-state-backup-$(date +%Y%m%d).tfstate

ls -lh ${BACKUP_DIR}/terraform-state-backup-*.tfstate
```

**Bước 1.5 — Backup Kubernetes resources manifests (GitOps-based)**

```bash
# GitOps-based platform: Application manifests đã nằm trong Git
# Chỉ cần verify Git có latest commit
cd ~/capstone/capstone-platform

git log --oneline -5
echo "---"
# Verify tất cả app manifests tồn tại trong Git
ls apps/infra/*/Chart.yaml 2>/dev/null || ls apps/infra/*/kustomization.yaml
echo "---"
# Current commit = backup version
git rev-parse HEAD > ${BACKUP_DIR}/git-head-commit.txt
echo "Git HEAD: $(cat ${BACKUP_DIR}/git-head-commit.txt)"
```

---

### Part 2: Simulate ArgoCD App Delete + Restore (10 phút)

**Bước 2.1 — Verify target Application đang healthy**

```bash
# Chọn một app để simulate (không phải root app)
argocd app list

# Kiểm tra trạng thái
argocd app get api-service --output json | jq '{sync,health,revision}'
```

**Expected output:**
```
{
  "sync": {
    "status": "Synced"
  },
  "health": {
    "status": "Healthy"
  },
  "revision": "v1.2.3"
}
```

**Bước 2.2 — Ghi lại trạng thái trước khi delete**

```bash
# Capture all app resources trước khi xóa
argocd app resources api-service -o wide > ${BACKUP_DIR}/api-service-resources-before.txt

# Ghi lại manifest
kubectl get deployment api-service -n apps -o yaml > ${BACKUP_DIR}/api-service-deployment-before.yaml

echo "Pre-delete snapshot saved to ${BACKUP_DIR}/"
cat ${BACKUP_DIR}/api-service-resources-before.txt
```

**Bước 2.3 — Simulate ArgoCD App delete (chỉ xóa Application CR, không xóa cluster resources)**

```bash
# Xóa ArgoCD Application resource
# KHÔNG dùng --cascade (sẽ xóa cả underlying resources)
argocd app delete api-service

# Verify Application đã xóa
argocd app list | grep api-service
# Expected: (empty) — Application đã xóa
```

**Bước 2.4 — Verify cluster resources vẫn còn (ArgoCD không xóa underlying khi chỉ delete App)**

```bash
# Cluster resources vẫn running
kubectl get deployment api-service -n apps
kubectl get pods -n apps -l app=api-service

echo "→ Cluster resources vẫn Healthy: $(kubectl get deployment api-service -n apps -o jsonpath='{.status.readyReplicas}')/$(kubectl get deployment api-service -n apps -o jsonpath='{.spec.replicas}') replicas"
```

**Expected output:**
```
NAME           READY   UP-TO-DATE   AVAILABLE
api-service    2/2     2            2
→ Cluster resources vẫn Healthy: 2/2 replicas
```

**Bước 2.5 — Restore Application từ Git (cách nhanh nhất)**

```bash
# Tạo lại Application bằng cách sync từ Git
# ArgoCD sẽ detect application mới từ App of Apps hoặc tạo thủ công

# Nếu dùng App of Apps: ArgoCD sẽ tự recreate sau vài phút
# Nếu tạo thủ công:
cat <<'EOF' | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_ORG/capstone-apps
    targetRevision: HEAD
    path: apps/api-service/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: apps
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF
```

**Bước 2.6 — Verify restore thành công**

```bash
# Watch ArgoCD sync
argocd app wait api-service --timeout 120

argocd app get api-service
```

**Expected output:**
```
Name:               api-service
Sync Status:        Synced
Health Status:      Healthy
```

**Bước 2.7 — Measure recovery time**

```bash
# Ghi lại thời gian restore
echo "Recovery completed at: $(date)"
echo "DR Matrix check: ArgoCD App restore = 5 phút (target: 5 phút) ✓"
```

---

### Part 3: Simulate Bad Deployment + ArgoCD Rollback (15 phút)

**Bước 3.1 — Tạo "bad" commit trong apps repo để simulate deployment lỗi**

```bash
cd ~/capstone/capstone-apps

# Check git status
git status

# Backup current working state
git add -A
git commit -m "chore: backup before DR simulation" || true
git push

echo "Current HEAD: $(git rev-parse HEAD)"
```

**Bước 3.2 — Simulate bad deployment bằng cách update image tag sai**

```bash
# Tạo bad commit: image tag không tồn tại
# Chỉnh sửa values file: đổi image tag thành non-existent version

# Cách an toàn: tạo override không push lên main
cat <<'EOF' > apps/api-service/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: apps
resources:
  - ../../base
images:
  - name: ghcr.io/YOUR_ORG/api-service
    newTag: DOES-NOT-EXIST-99.99.99  # ← Bad tag
EOF

# Apply bad config locally (override Git state, không commit)
kubectl kustomize apps/api-service/overlays/dev | kubectl apply -f -
echo "→ Applied bad configuration (tag DOES-NOT-EXIST-99.99.99)"
```

**Bước 3.3 — Observe failure**

```bash
# Watch pod fail
kubectl get pods -n apps -l app=api-service -w

# Sau ~30 giây, pod sẽ fail với ImagePullBackOff
# Ctrl+C để thoát watch
```

**Expected error (sau 30 giây):**
```
NAME                        READY   STATUS            RESTARTS   AGE
api-service-xxx            0/1     ImagePullBackOff  0          45s
api-service-old-xxx        2/2     Running           0          10m
```

**Bước 3.4 — ArgoCD rollback**

```bash
# Xem sync history
argocd app history api-service

# Rollback về revision trước (revision có tag hợp lệ)
argocd app rollback api-service

# Hoặc sync về revision cũ cụ thể
# argocd app sync api-service --revision <good-revision>
```

**Expected output:**
```
History ID  Revision  Deploy Date           Source
3           v2.1.0    2026-05-15 14:35      main@sha1:abc123  ← bad
2           v1.2.3    2026-05-15 13:00      main@sha1:def456  ← good
1           v1.2.2    2026-05-15 10:00      main@sha1:ghi789

Rollback to '2' initiated.
```

**Bước 3.5 — Verify rollback thành công**

```bash
argocd app wait api-service --timeout 120
argocd app get api-service | grep -E "Sync|Health|Revision"

# Verify pod healthy
kubectl get pods -n apps -l app=api-service
```

**Expected output:**
```
Name:               api-service
Sync Status:        Synced  Health:      Healthy
Revision:           v1.2.3  ← Đã rollback về version cũ
```

**Bước 3.6 — Cleanup kustomization override**

```bash
# Xóa kustomization.yaml override tạm thời
# (vì nó ghi đè Git state)
rm apps/api-service/overlays/dev/kustomization.yaml

# ArgoCD sẽ revert về Git state (đúng)
argocd app sync api-service
argocd app get api-service | grep -E "Sync|Health|Revision"
```

---

### Part 4: Terraform State Backup/Restore Simulation (10 phút)

**Bước 4.1 — Tạo test resource để simulate state manipulation**

```bash
cd ~/capstone/capstone-infra/terraform/envs/dev

# Tạo test resource (local file — không ảnh hưởng cloud)
cat <<'EOF' > test_state_resource.tf
resource "local_file" "dr_test" {
  content  = "DR simulation file - can be deleted"
  filename = "dr-test-file.txt"
}
EOF

terraform init
terraform apply -auto-approve

# Verify state chứa resource mới
terraform state list | grep dr_test
```

**Expected output:**
```
local_file.dr_test
```

**Bước 4.2 — Simulate state corruption và restore**

```bash
# Backup current state
BACKUP_FILE=${BACKUP_DIR}/terraform-state-pre-dr-test.tfstate
terraform state pull > $BACKUP_FILE
echo "State backed up to: $BACKUP_FILE"

# Simulate corruption: xóa resource khỏi state
terraform state rm local_file.dr_test

# Verify state không còn resource (nhưng file vẫn tồn tại trong thực tế)
terraform state list | grep dr_test
# Expected: (empty)

ls dr-test-file.txt
# Expected: file still exists ( orphaned in reality, tracked only in state)
```

**Bước 4.3 — Restore state**

```bash
# Restore từ backup
terraform state push $BACKUP_FILE

# Verify resource đã back trong state
terraform state list | grep dr_test
# Expected: local_file.dr_test
```

**Bước 4.4 — Cleanup test resource**

```bash
# Destroy test resource
terraform destroy -auto-approve
rm -f test_state_resource.tf dr-test-file.txt

# Verify state sạch
terraform state list | grep dr_test
# Expected: (empty)
```

**Expected output:**
```
State restored successfully from backup
Resource local_file.dr_test restored to state
local_file.dr_test: Refreshing state... [id=xxx]
Destroy complete! Resources: 1 destroyed.
```

---

### Part 5: Export DR Runbook + Final Demo Checklist (5 phút)

**Bước 5.1 — Tạo final demo checklist**

```bash
cat <<'EOF' > ~/capstone/docs/final-demo-checklist.md
# Final Demo Checklist

## Pre-demo (5 phút trước khi demo)

- [ ] Cluster accessible: `kubectl cluster-info`
- [ ] ArgoCD healthy: `argocd version`
- [ ] Tất cả Application synced: `argocd app list | grep -v Synced`
- [ ] Tất cả pod Running: `kubectl get pods -A | grep -v Running`
- [ ] ArgoCD backup mới nhất tồn tại: `ls -lh backups/$(date +%Y%m%d)/`
- [ ] Terraform state healthy: `cd infra && terraform state list | head`
- [ ] Git repos clean: `git status` (working tree clean)

## Demo Sequence (10 phút)

### 1. ArgoCD GitOps Flow (2 phút)
```bash
# Show current deployment
argocd app list
argocd app get api-service

# Show app resources
argocd app resources api-service
```

### 2. Self-Heal Demonstration (3 phút)
```bash
# Delete a resource directly (not via Git)
kubectl delete deployment api-service -n apps

# ArgoCD tự recreate (nếu auto-sync = true)
kubectl get pods -n apps -l app=api-service -w
# Pod recreate trong ~30 giây
```

### 3. Rollback Demonstration (3 phút)
```bash
# Show sync history
argocd app history api-service

# Trigger rollback
argocd app rollback api-service
argocd app get api-service
```

### 4. Backup Verification (2 phút)
```bash
# Show ArgoCD backup
ls -lh backups/$(date +%Y%m%d)/argocd-backup-full.yaml

# Show Terraform state backup
ls -lh backups/$(date +%Y%m%d)/terraform-state-*.tfstate

# Show Git HEAD (Application manifests)
git -C capstone-platform log --oneline -3
```

## Post-demo Cleanup (bắt buộc)

- [ ] Mode B: `cd capstone-infra/terraform/envs/dev && terraform destroy -auto-approve`
- [ ] Mode B: Verify no EKS/RDS/ElastiCache resources remain
- [ ] Mode A: `kind delete cluster --name capstone`
- [ ] Remove backup files: `rm -rf ~/capstone/backups/`
EOF

echo "Final demo checklist created: ~/capstone/docs/final-demo-checklist.md"
cat ~/capstone/docs/final-demo-checklist.md
```

---

### Part 6: Full Cleanup (10 phút)

**⚠️ CLEANUP BẮT BUỘC — KHÔNG BỎ QUA**

#### Mode A Cleanup

```bash
# 1. Xóa kind cluster
kind get clusters
kind delete cluster --name capstone || kind delete cluster

# 2. Verify cluster đã xóa
kind get clusters
# Expected: (empty hoặc lỗi "no clusters found")

# 3. Xóa local backup directory
rm -rf ~/capstone/backups/

# 4. Verify cleanup hoàn tất
docker ps | grep -E "kind|argocd" || echo "Docker containers clean"
echo "✓ Mode A cleanup hoàn tất"
```

#### Mode B Cleanup (BẮT BUỘC)

```bash
# 1. Verify infrastructure đang chạy
cd ~/capstone/capstone-infra/terraform/envs/dev
aws ec2 describe-vpcs --filters Name=tag:Project,Values=capstone --output table

# 2. Terraform destroy — DURATION: ~10-15 phút
terraform destroy -auto-approve

# 3. Verify destroy thành công
terraform show | head -5
# Expected: "No state" hoặc empty

# 4. Verify no AWS resources remain
aws ec2 describe-vpcs --filters Name=tag:Project,Values=capstone --output json | jq '.Vpcs | length'
# Expected: 0

# 5. Xóa S3 state bucket backup (nếu muốn clean hết)
aws s3 ls | grep capstone
# Nếu có: aws s3 rb s3://capstone-tf-state-xxx --force

# 6. Xóa local backup
rm -rf ~/capstone/backups/

# 7. AWS Budget verification
echo "Kiểm tra AWS Budget Console để verify không có unexpected charge"
echo "Recommended: https://console.aws.amazon.com/billing/home#/budgets"

echo "✓ Mode B cleanup hoàn tất — KHÔNG QUÊN CHECK AWS BUDGET"
```

---

## 6. Kiểm tra hiểu bài

**Câu 1: Giải thích DR concept**

RTO (Recovery Time Objective) và RPO (Recovery Point Objective) khác nhau như thế nào? Trong capstone platform này, RPO của database nên đặt bao nhiêu, và tại sao?

**Câu 2: Chọn DR strategy**

Một startup có 3 developer, budget $50/tháng, chạy trên AWS Mode B single-AZ. Họ nên chọn DR strategy nào cho cluster (EKS)? Và cho database (RDS)? Giải thích trade-offs.

**Câu 3: Debug incident**

Dev team báo: "ArgoCD không sync được app, tất cả application ở OutOfSync." Bạn sẽ debug như thế nào? Liệt kê 5 bước đầu tiên để diagnose.

**Câu 4: Rollback decision**

Sau khi promote v2.3.0 lên production, 2% user báo lỗi checkout. ArgoCD hiện synced ở v2.3.0. Bạn sẽ:
- Chọn ArgoCD rollback hay Git revert?
- Rollback về revision nào?
- Cần notify ai trước khi rollback?
- Sau khi rollback, có cần tạo incident report không?

**Câu 5: Terraform state emergency**

Sau khi chạy `terraform apply` trên production, state lock không release được. Lock ID đã mất. Bạn cần apply một thay đổi urgent. Bạn sẽ làm gì?

---

## 7. Tóm tắt cuối ngày

### 3-5 ý quan trọng nhất

1. **DR không phải backup — DR là ability to recover.** Backup chỉ là một phần. Runbook + tested procedures + verified RTO/RPO mới là DR plan hoàn chỉnh.

2. **GitOps là DR strategy tốt nhất cho Application layer.** Vì application manifests luôn nằm trong Git, restore ArgoCD Application = `kubectl apply -f <git-manifest>` + ArgoCD tự reconcile. Không cần Velero cho stateless app.

3. **Terraform state là điểm thất bại duy nhất của infrastructure layer.** State file = infrastructure source of truth. S3 versioning + DynamoDB lock + backup script = minimum viable DR cho infrastructure.

4. **Rollback phải nhanh hơn debug.** Khi incident xảy ra, rollback ngay bằng ArgoCD rollback (3 phút) — rồi debug sau. Không bao giờ debug trên production đang broken.

5. **DR plan chỉ có giá trị khi được test.** Runbook không test = không đáng tin. GameDay simulation hàng quý là cách duy trất confidence duy nhất.

### Output đã tạo ra

Sau ngày này, bạn có:
- ArgoCD backup: `backups/YYYYMMDD/argocd-backup-full.yaml`
- Terraform state backup: `backups/YYYYMMDD/terraform-state-backup-*.tfstate`
- DR Runbook: `docs/runbook.md` (document.md)
- DR Checklist + Matrix: trong document.md
- Final Demo Checklist: `docs/final-demo-checklist.md`
- Incident simulation exercises: `exercises.md`
- Full platform cleanup (Mode A hoặc Mode B)

### Kiến thức chuẩn bị cho công việc thực tế

Ngày cuối này tổng hợp toàn bộ 35 ngày. Kiến thức đã có:
- Terraform: module design, multi-env, state strategy, CI/CD, OIDC (Day 1-12)
- Ansible: playbook, role, vault, integration với Terraform (Day 13-16)
- ArgoCD: Application, AppProject, ApplicationSet, sync waves, secrets, RBAC, Rollouts, observability (Day 17-27)
- Production platform: end-to-end GitOps, CI/CD, DR, observability, cost control (Day 28-35)

---

## 8. Tham khảo thêm

- [ArgoCD Disaster Recovery](https://argo-cd.readthedocs.io/en/stable/operator-manual/disaster_recovery/)
- [ArgoCD Admin Export/Import](https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-admin-export/)
- [Velero Backup & Restore Kubernetes](https://velero.io/docs/latest/)
- [Terraform State Management](https://developer.hashicorp.com/terraform/language/state)
- [AWS RDS Backup and Restore](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- [RTO vs RPO — AWS Backup](https://docs.aws.amazon.com/aws-backup/latest/devguide/application-layer.html)
- [SRE Workbook — Postmortem Culture](https://sre.google/workbook/postmortem/)
