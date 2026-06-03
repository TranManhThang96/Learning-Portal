# Day 20 — Tài liệu tham khảo: Repo Template Library & Reference

> Bổ sung cho `lesson.md` — phần này là reference library để copy-paste khi thiết kế thực tế.

---

## 1. Repo Template Library

### Template 1: Solo Developer / Side Project (Monorepo)

Phù hợp: 1 người, muốn đơn giản, không cần RBAC phức tạp.

```
acme-gitops/                     # 1 repo duy nhất
├── terraform/                   # Infrastructure (Terraform)
│   ├── modules/
│   └── live/{dev,staging,prod}/
├── platform/                    # Platform addons
│   ├── ingress-nginx/
│   └── cert-manager/
├── apps/                        # Application manifests
│   ├── api/
│   │   ├── base/
│   │   └── overlays/{dev,staging,prod}/
│   └── worker/
├── argocd/                      # ArgoCD applications
│   └── applications/
└── README.md
```

```yaml
# argocd/applications/api-prod.yaml
# Tất cả app trỏ vào cùng 1 repo, path khác nhau
spec:
  source:
    repoURL: https://github.com/acme/acme-gitops.git
    path: apps/api/overlays/prod
    targetRevision: main
```

**Khi nào nâng cấp lên Template 2:** Khi bắt đầu có 2+ người trong team.

---

### Template 2: Small Team (Monorepo infra+platform + per-service polyrepo)

Phù hợp: 5–15 người, 2–4 service, cần ownership rõ hơn.

```
acme/
├── acme-infra-platform/          # Monorepo: Terraform + cluster addons
│   ├── terraform/
│   │   ├── modules/
│   │   └── live/{dev,staging,prod}/
│   ├── platform/
│   │   ├── argocd/
│   │   └── helm/
│   ├── .github/workflows/       # Cùng CI cho cả 2
│   └── CODEOWNERS
│
├── acme-api/                    # Polyrepo per service
├── acme-worker/                 # Mỗi team 1 repo
└── acme-frontend/
```

**Đặc điểm:**
- CI chỉ trigger khi file trong path tương ứng thay đổi
- Platform team review `acme-infra-platform`, app team tự quản repo riêng
- Promotion: mỗi service repo có overlay riêng

---

### Template 3: Enterprise (3 repo + per-service repos)

Phù hợp: 15–50 người, compliance nghiêm ngặt, nhiều team.

```
acme/
├── acme-infra/                  # Terraform-only repo
├── acme-platform/               # Platform addons-only repo
├── acme-shared-config/          # Tooling config, CI templates, policy
│   ├── .github/
│   │   └── workflows/
│   │       ├── terraform-plan.yml
│   │       ├── kustomize-build.yml
│   │       └── conftest.yml
│   └── policies/
│       └── opa/
├── acme-api/                    # Mỗi service 1 repo riêng
│   ├── services/api/
│   │   ├── base/
│   │   └── overlays/{dev,staging,prod}/
│   ├── argocd/                  # ArgoCD Application cũng trong repo
│   └── .github/
│       └── workflows/
└── acme-worker/
    └── ...
```

**Đặc điểm:**
- `acme-shared-config` chứa reusable CI template (workflow template)
- Mỗi service repo dùng workflow template từ shared-config
- Tooling consistency được enforce qua shared templates
- Enforcement: `push` block nếu không dùng shared workflows

```yaml
# acme-shared-config/.github/workflows/_template-kustomize.yml
# Dùng làm reusable workflow
name: Kustomize Build
on:
  workflow_call:
    inputs:
      service_path:
        required: true
        type: string
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: kustomize build ${{ inputs.service_path }}/overlays/dev
```

```yaml
# acme-api/.github/workflows/main.yml
# Gọi reusable workflow
on: [push, pull_request]
jobs:
  kustomize:
    uses: acme/acme-shared-config/.github/workflows/_template-kustomize.yml@main
    with:
      service_path: services/api
```

---

### Template 4: Bank / Regulated Industry

Phù hợp: Bank, insurance, healthcare — cần audit trail đầy đủ, signed commits, sync window, mandatory review.

```
acme-regulated/
├── acme-infra/                   # Terraform
│   ├── .github/
│   │   └── workflows/
│   │       └── terraform.yml    # 4-eye review enforced
│   ├── .github/CODEOWNERS
│   └── .github/branch-protection.yml
│
├── acme-platform/                # Platform
│   ├── .github/
│   │   └── workflows/
│   │       └── platform.yml     # 4-eye review enforced
│   └── .github/CODEOWNERS
│
├── acme-apps/                    # Application
│   ├── .github/
│   │   └── workflows/
│   │       ├── dev.yml          # 1-eye (dev)
│   │       └── prod.yml         # 2-eye (prod)
│   └── .github/CODEOWNERS
│
└── acme-policy-config/          # Enforcement config
    └── policies/                 # OPA policies (required)
```

**Additional requirements:**
- **Signed commits:** `--gpg-sign` hoặc `--local-user-signingkey`
- **Sync window:** ArgoCD sync chỉ trong maintenance window
- **Audit log export:** GitHub audit log → SIEM integration
- **Branch protection:** 4-eye (2 người khác approve) + signed commit requirement
- **Secrets:** External Secrets Operator, Vault integration
- **Immutable tags:** Không dùng `latest`, dùng digest hoặc semver

---

## 2. Ownership Matrix mẫu (10x10 Grid)

Team structure mẫu cho 1 organization 50 người:

| Resource / Team | SRE (3) | Platform (4) | API Team (8) | Worker Team (5) | Frontend Team (6) | Security (2) | DBA (2) | Dev Leads (3) | Management (2) | Externel Audit |
|----------------|---------|-------------|-------------|----------------|-----------------|-------------|--------|--------------|---------------|----------------|
| `infra-repo/terraform/` | **OW** | R | - | - | - | - | R | R | I | - |
| `infra-repo/live/prod/` | **OW** | - | - | - | - | R | R | A | I | - |
| `infra-repo/live/dev/` | **OW** | R | - | - | - | - | - | R | I | - |
| `platform-repo/argocd/bootstrap/` | A | **OW** | - | - | - | R | - | I | - | - |
| `platform-repo/argocd/projects/` | A | **OW** | R | R | R | R | - | R | - | - |
| `platform-repo/platform-services/` | A | **OW** | - | - | - | R | - | R | - | - |
| `apps-repo/services/api/` | A | A | **OW** | - | - | R | R | R | I | - |
| `apps-repo/services/worker/` | A | A | - | **OW** | - | R | R | R | I | - |
| `apps-repo/services/frontend/` | A | A | - | - | **OW** | R | - | R | I | - |
| `apps-repo/overlays/prod/` | A | A | R | R | R | R | - | **OW** | I | R |

Legend:
- **OW** = Owner (full write + admin)
- R = Review required (phải approve PR)
- A = Approve (chỉ approve, không write trực tiếp)
- I = Informed (được notify, không cần approve)
- `-` = Không liên quan

---

## 3. README Template chi tiết

### Template A: infra-repo README

```markdown
# <PROJECT>-infra

## Mục đích

Chứa Terraform code quản [infrastructure components]. Repo này là **source of truth** cho infrastructure.

## Owner

| Trường | Giá trị |
|--------|---------|
| Team | @<team-name> |
| Slack | #<channel> |
| On-call | PagerDuty: <service> |
| On-call schedule | Rotation: 1 week each |

## Cấu trúc

```
modules/                    # Terraform modules (reusable)
  <module-name>/
    main.tf
    variables.tf
    outputs.tf
live/                       # Environment-specific
  <env>/                    # dev / staging / prod
    main.tf
    variables.tf
    backend.tf
.github/workflows/          # CI/CD
```

## Thêm thay đổi

1. **Tạo branch:** `git checkout -b feat/<description>`
2. **Sửa file:** Terraform code
3. **Commit:** `git commit -m "feat: <description>"`
4. **Push:** `git push origin feat/<description>`
5. **Tạo PR:** CI sẽ chạy terraform plan tự động
6. **Review:** Chờ approval từ CODEOWNERS
7. **Merge:** Squash merge vào `main`

## Environment

| Env | Region | Account | Terraform backend |
|-----|--------|---------|-----------------|
| dev | us-east-1 | 111111111111 | S3 (local state dev bucket) |
| staging | us-east-1 | 222222222222 | S3 (staging bucket) |
| prod | us-east-1 | 333333333333 | S3 (prod bucket, DynamoDB lock) |

## CI/CD Pipeline

| Trigger | Action |
|---------|--------|
| PR opened | terraform fmt + validate + plan |
| PR merged to main | terraform apply (auto) |
| Push to `modules/` | Retest all env plan |

## Review rule

| Environment | Required approvers |
|-------------|-------------------|
| dev | 1 (SRE team) |
| staging | 1 (SRE team) |
| prod | 2 (SRE lead + DBA/Platform) |

## Rollback

```bash
# KHÔNG chạy terraform apply rollback trực tiếp
# Luôn dùng git revert:
git revert <bad-commit-sha>
git push

# Verify: ArgoCD hoặc terraform plan sẽ show diff
```

## Contacts

- Primary: <name> (<email>)
- Backup: <name> (<email>)
```

### Template B: platform-repo README

```markdown
# <PROJECT>-platform

## Mục đích

Chứa cluster-level configuration — ArgoCD bootstrap, platform addons, policies. Repo này là **source of truth** cho platform.

## Owner

| Trường | Giá trị |
|--------|---------|
| Team | @platform-team |
| Slack | #team-platform |
| On-call | PagerDuty: <service> |

## Cấu trúc

```
argocd/                     # ArgoCD configuration
  bootstrap/               # Root App of Apps
  projects/                # AppProject definitions
  applications/             # Platform Application definitions
platform-services/          # Helm values (upstream charts)
policies/                   # OPA / Kyverno policies
```

## Thêm platform addon

1. Thêm Helm values vào `platform-services/<addon>/values.yaml`
2. Tạo ArgoCD Application trong `argocd/applications/<addon>.yaml`
3. PR → Platform team review → merge → ArgoCD sync

## ArgoCD sync policy

| Environment | Automated sync | Sync window |
|-------------|---------------|------------|
| dev | Yes (prune + selfHeal) | Always |
| staging | Yes (prune, no selfHeal) | Always |
| prod | Manual (click Sync) | Maintenance: 22:00–06:00 UTC |

## Application list

| Application | Namespace | Chart | Purpose |
|-------------|-----------|-------|---------|
| ingress-nginx | ingress-nginx | ingress-nginx/ingress-nginx | HTTP routing |
| cert-manager | cert-manager | jetstack/cert-manager | TLS certificates |
| external-secrets | external-secrets | external-secrets/external-secrets | Secret management |
| prometheus-stack | monitoring | prometheus-community/kube-prometheus-stack | Monitoring |
| loki | loki | grafana/loki | Log aggregation |

## Promotion / Rollback

- **Promotion:** PR thay đổi Helm values hoặc ArgoCD Application spec
- **Rollback:** `git revert` → ArgoCD detect → sync

## Contacts

- Primary: <name> (<email>)
- Backup: <name> (<email>)
```

### Template C: apps-repo README

```markdown
# <PROJECT>-apps

## Mục đích

Chứa Kubernetes manifests cho tất cả application microservices. **Source of truth** cho application deployment.

## Owner

| Trường | Giá trị |
|--------|---------|
| Global | @dev-leads |
| Per-service | Xem CODEOWNERS |

## Cấu trúc

```
services/                   # Mỗi service 1 sub-tree
  <service-name>/
    base/                   # Base manifests
    overlays/               # Per-env overrides
      dev/
      staging/
      prod/
argocd/                     # ArgoCD Application definitions
  projects/                # Per-team AppProject
  applications/            # Application per service/env
```

## Service catalog

| Service | Team | Repo/Path | Description |
|---------|------|-----------|-------------|
| api-service | @api-team | services/api-service/ | REST API |
| worker-service | @worker-team | services/worker-service/ | Background jobs |
| frontend-service | @frontend-team | services/frontend-service/ | Web UI |

## Promotion flow

```
CI build → acme/<service>:vX.Y.Z
    ↓
Image Updater tạo PR → overlays/dev/
    ↓
Auto-merge → ArgoCD dev sync
    ↓
Promotion PR → overlays/staging/
    ↓
1-eye review + merge → ArgoCD staging sync
    ↓
Promotion PR → overlays/prod/
    ↓
2-eye (team lead + SRE) + merge → ArgoCD prod sync
```

## Thêm service mới

1. `services/<new-service>/base/` — manifests
2. `services/<new-service>/overlays/{dev,staging,prod}/` — overlays
3. `argocd/applications/<new-service>-{dev,staging,prod}.yaml` — ArgoCD app
4. PR → team review → merge → ArgoCD tự tạo app

## Rollback

```bash
git log services/<service>/overlays/prod/
git revert <bad-sha>
git push
# ArgoCD detect → sync về version trước
```

## CI checks

| Check | Tool | Trigger |
|-------|------|---------|
| Kustomize build | kustomize | Every PR |
| Schema validation | kubeval / kubeconform | Every PR |
| Security scan | Trivy / kubesec | Every PR |
| Policy check | conftest | Every PR |

## Contacts

| Service | Team | Primary | Backup |
|---------|------|---------|--------|
| api-service | @api-team | <name> | <name> |
| worker-service | @worker-team | <name> | <name> |
```

---

## 4. CODEOWNERS Pattern Reference

### Basic pattern

```
# comment
/path/to/thing @owner1 @owner2
```

### Pattern cho multi-team organization

```
# ============================================
# INFRA REPO
# ============================================
# Global: SRE owns all infrastructure
* @acme/sre

# Production: leads required
live/prod/ @acme/sre-leads
live/prod/** @acme/sre-leads

# Staging: standard SRE review
live/staging/ @acme/sre

# Dev: SRE review
live/dev/ @acme/sre

# Database module: DBA required
modules/database/ @acme/sre @acme/dba
/modules/rds/ @acme/sre @acme/dba
/modules/elasticache/ @acme/sre @acme/dba

# Networking: SRE + Network
/modules/network/ @acme/sre @acme/network

# ============================================
# PLATFORM REPO
# ============================================
# Global: Platform team
* @acme/platform

# Security-sensitive
argocd/projects/ @acme/platform @acme/security
policies/ @acme/platform @acme/security

# Prod ArgoCD apps
argocd/applications/prod-*.yaml @acme/platform @acme/sre-leads

# ============================================
# APPS REPO
# ============================================
# Global: Dev leads
* @acme/dev-leads

# Per-service ownership
/services/api/ @acme/api-team
/services/worker/ @acme/worker-team
/services/frontend/ @acme/frontend-team

# Prod overlays: SRE leads required
/services/*/overlays/prod/ @acme/dev-leads @acme/sre-leads

# Security-critical services
/services/payment/ @acme/payment-team @acme/security
/services/auth/ @acme/auth-team @acme/security
/services/*/overlays/prod/ @acme/payment-team @acme/security @acme/sre-leads

# Shared base (changes affect all teams)
services/base/ @acme/dev-leads @acme/platform
```

---

## 5. Branch Protection Settings

### GitHub UI fields (Settings → Branches → Add rule)

```
Branch name pattern: main
☑ Require a pull request before merging
   Required number of approvals before merging: [2]       ← 4-eye cho prod infra
☑ Dismiss stale reviews when new commits are pushed
☑ Require review from Code Owners                      ← CODEOWNERS enforcement
☑ Require status checks to pass before merging
   Status checks:
     - terraform-plan (required)
     - terraform-fmt (required)
     - terraform-validate (required)
☑ Require branches to be up to date before merging
☑ Do not allow bypassing the above settings
☑ Include administrators
☑ Lock branch (prevent force-push)
☑ Require signed commits                               ← Bank/regulated
☑ Require conversation resolution before merging
```

### GitHub Actions Branch Protection (via API / ruleset YAML)

```yaml
# .github/rulesets/infra-repo.yml (GitHub Enterprise)
name: infra-repo main protection
rules:
  required_status_checks:
    strict: true
    checks:
      - context: terraform-plan
        type: required
      - context: terraform-fmt
        type: required
  required_reviewers:
    - 2  # 4-eye: author + 2 reviewer
  dismissal_rules:
    dismiss_stale_reviews: true
    require_code_owner_reviews: true
  restrictions:
    blocks_force_push: true
    require_signed_commits: true  # bank/regulated
  ruleset_type: advanced
```

---

## 6. Promotion Flow Diagrams

### Flow A: ArgoCD Image Updater (auto-promotion)

```
CI build: acme/api:v1.2.0
         │
         ▼
Container Registry (ghcr.io / ECR)
         │
         ▼
ArgoCD Image Updater
  - Polls registry every 5 phút
  - Detect new digest
  - Update argocd/applications/api-service-dev.yaml
    spec.source.helm.parameters:
      - name: image.tag
        value: v1.2.0
  - Push to Git (service account credential)
         │
         ▼
ArgoCD dev Application: OutOfSync
         │
         ▼
ArgoCD auto-sync (selfHeal: true)
         │
         ▼
Dev cluster: api-service v1.2.0 ✓
         │
         ▼
Manual promotion PR: staging overlay
  → Review → Merge
         │
         ▼
ArgoCD staging sync ✓
```

### Flow B: Renovate Bot (dependency update)

```
Renovate Bot (schedule: hourly)
  │
  ├── Detect: acme/api-service v1.2.0 published to registry
  │
  ▼
Create PR: apps-repo
  overlays/dev/kustomization.yaml
  - newTag: v1.2.0
  Branch: renovate/api-service-image
         │
         ▼
CI: kustomize build + validate ✓
         │
         ▼
Auto-merge (if: satisfies auto-merge rules)
         │
         ▼
ArgoCD dev sync ✓
         │
         ▼
Manual promote.yml workflow:
  → PR: staging
  → PR: prod (require SRE approval)
```

### Flow C: ApplicationSet Generator (multi-cluster)

```
ApplicationSet Generator (Git generator)
  │
  ├── Cluster selector: environment=prod
  ├── Clusters: us-east, eu-west, ap-south
  │
  ▼
Generate Application per cluster:
  api-service-us-east
  api-service-eu-west
  api-service-ap-south
         │
         ▼
Each Application points to:
  repoURL: apps-repo
  path: services/api-service/overlays/prod
  targetRevision: main
         │
         ▼
ArgoCD sync to ALL 3 clusters simultaneously ✓
```

---

## 7. Rollback Runbook (3 Scenarios)

### Scenario 1: Bad image tag deployed to prod

**Symptom:** API service returning 500 after deploying v1.2.0 to prod.

**Timeline:**
- T (0): Image bump PR merged → ArgoCD sync → prod v1.2.0
- T (5 min): PagerDuty alert — 50% error rate
- T (7 min): On-call confirms: v1.2.0 is the cause

**Runbook:**

```bash
# Step 1: Identify bad commit
argocd app history api-service-prod
# OUTPUT:
# ID  DATE                           REVISION  STATUS
# 42  2026-05-14 10:05:00 +0000 UTC  abc1234f  Synced ← BAD
# 41  2026-05-14 09:00:00 +0000 UTC  9f8e7d6c  Synced ← GOOD

# Step 2: Git rollback (PROD: luôn qua Git)
cd apps-repo
git revert abc1234f --no-edit
git push

# Step 3: Wait for ArgoCD sync (hoặc manual sync)
argocd app sync api-service-prod

# Step 4: Verify
argocd app get api-service-prod
# Expected: Synced, Healthy

# Step 5: Post-incident
# - Update image bump policy: require staging test 1h trước prod
# - Document trong incident report
```

**Prevention:**
- Require minimum 4h soak time trên staging trước prod promotion
- Auto-rollback nếu error rate > 5% trong 5 phút

---

### Scenario 2: Bad Helm values config deployed

**Symptom:** ingress-nginx không start sau khi update values.

**Runbook:**

```bash
# Step 1: Identify
argocd app get ingress-nginx
# Expected: Degraded/Unhealthy

argocd app history ingress-nginx
# Find the bad revision

# Step 2: Git revert
cd platform-repo
git revert <bad-sha> --no-edit
git push

# Step 3: Verify
argocd app sync ingress-nginx
argocd app get ingress-nginx
# Expected: Healthy
```

---

### Scenario 3: Prune disaster (ArgoCD deleted resources không nên xóa)

**Symptom:** ArgoCD `prune: true` xóa ConfigMap quan trọng khi sync.

**Emergency runbook:**

```bash
# Step 1: STOP ArgoCD auto-sync immediately
argocd app set ingress-nginx --sync-policy manual
argocd app set ingress-nginx --automated-sync-enabled=false

# Step 2: Restore từ backup
# Option A: Recreate manually (if backup unavailable)
kubectl apply -f backup/ingress-nginx-configmap.yaml

# Option B: Restore from Git history
kubectl get configmap ingress-nginx-config -o yaml > /tmp/backup.yaml
# Sau đó chỉnh sửa backup này

# Step 3: Fix ArgoCD Application spec để exclude resource khỏi prune
# Thêm vào Application spec:
spec:
  ignoreDifferences:
    - group: ""
      kind: ConfigMap
      name: ingress-nginx-config
      jsonPointers:
        - /data

# Step 4: Re-enable sync
argocd app set ingress-nginx --sync-policy automated
argocd app sync ingress-nginx

# Step 5: Post-incident
# - Fix spec.syncPolicy (thêm ignoreDifferences)
# - Review tất cả prune:true policies
# - Backup resource trước khi apply
```

---

## 8. CI/CD Job Catalog

### Per-repo CI pipeline

#### infra-repo CI

| Job | Trigger | Action | Fail means |
|-----|---------|--------|------------|
| terraform-fmt | push PR | `terraform fmt -check` | Formatting issue |
| terraform-validate | push PR | `terraform validate` | Syntax error |
| terraform-plan-dev | push PR | `terraform plan -var-file=dev.tfvars` | Breaking change dev |
| terraform-plan-staging | push PR | `terraform plan -var-file=staging.tfvars` | Breaking change staging |
| terraform-plan-prod | push PR | `terraform plan -var-file=prod.tfvars` | Breaking change prod |
| terraform-apply | merge main | `terraform apply` | Manual intervention |
| tfsec | schedule | Security scan | Report only |

#### platform-repo CI

| Job | Trigger | Action | Fail means |
|-----|---------|--------|------------|
| conftest | push PR | OPA policy eval | Policy violation |
| kustomize-build | push PR | `kustomize build` | Invalid YAML |
| helm-lint | push PR | `helm lint` | Invalid values |
| validate-all | push PR | Validate all platform-services | Broken dependency |
| security-scan | push PR | Trivy image scan | Critical CVE |
| promotion-check | manual | Verify sync status | Promotion blocked |

#### apps-repo CI

| Job | Trigger | Action | Fail means |
|-----|---------|--------|------------|
| kustomize-build | push PR | `kustomize build` per overlay | Invalid manifest |
| kubeval | push PR | Schema validation | Invalid K8s schema |
| conftest | push PR | Policy check (no latest tag) | Policy violation |
| trivy-scan | push PR | Image vulnerability scan | Critical CVE |
| lint-all-overlays | push PR | Validate all overlays | Broken overlay |
| integration-test | promotion PR | Smoke test on target env | Deployment blocked |
| e2e-test | post-sync | Run tests on deployed app | Rollback triggered |

---

## 9. Anti-patterns Checklist (15 bullets)

```markdown
## Repository Structure Anti-patterns

- [ ] Helm chart + source code trong cùng repo GitOps
      → Tách: source repo (build) vs GitOps repo (deploy)
- [ ] Secrets/hardcoded credentials trong manifest
      → Dùng External Secrets Operator + Vault
- [ ] Dùng `latest` tag thay vì immutable tag
      → Luôn dùng digest hoặc semver (vX.Y.Z)
- [ ] Quên CODEOWNERS → ai cũng approve được
      → Bắt buộc CODEOWNERS review trên branch protection
- [ ] Promotion bằng tay (edit file trên GitHub UI)
      → Luôn qua PR để có audit trail
- [ ] Dùng argocd app sync làm promotion
      → Chỉ thay đổi cluster, không thay đổi Git
- [ ] Dùng git reset --hard
      → Mất history, drift Git vs cluster
- [ ] ArgoCD dùng personal PAT
      → Dùng machine user + deploy key
- [ ] App team sửa được infra/platform repo
      → Repo-level RBAC + branch protection
- [ ] CRD/ClusterRole trong apps-repo
      → Chỉ namespace-scope trong apps-repo
- [ ] Admin bypass branch protection
      → Disable admin bypass hoàn toàn
- [ ] ArgoCD auto-sync prod 24/7 không có sync window
      → Set sync window: maintenance only
- [ ] Merge squash làm mất commit history
      → Dùng merge commit cho infra/prod overlay
- [ ] Hardcode namespace trong manifest
      → Dùng kustomize namespaces hoặc Helm values
- [ ] Không có health check trong ArgoCD Application
      → ArgoCD không biết app healthy hay không
```

---

## 10. ArgoCD Credential Security Reference

### Anti-pattern: Personal Access Token (PAT)

```yaml
# SAI - KHÔNG LÀM
# Using personal PAT in ArgoCD repo credential
# Problem: Token belongs to a person
# When person leaves: credential expired → all apps drift
data:
  config: |
    - url: https://github.com/acme/
      auth: |
        username: john.doe
        password: ghp_xxxxxxxxxxxxx  # John's PAT
```

### Best practice: Machine User + Deploy Key

```bash
# Step 1: Tạo machine user account
# GitHub → Settings → Developer settings → Personal access tokens → Fine-grained PAT
# Permissions:
#   - Contents: Read-only (cho apps-repo)
#   - Contents: Read-write (cho platform-repo, infra-repo)

# Step 2: Register credential trong ArgoCD
argocd repo add https://github.com/acme/apps-repo \
  --username acme-bot \
  --password $ARGOCD_APPS_REPO_TOKEN

argocd repo add https://github.com/acme/platform-repo \
  --username acme-bot \
  --password $ARGOCD_PLATFORM_REPO_TOKEN

# Step 3: Verify
argocd repo list
# OUTPUT:
# TYPE  NAME  REPO                                      INSECURE  PROJECT
# git   apps  https://github.com/acme/apps-repo          OCI       default
# git   platform https://github.com/acme/platform-repo   OCI       default
```

### Best practice: GitHub App (Enterprise)

```bash
# Tốt nhất cho enterprise: GitHub App authentication
# Không cần quản lý token, revoke qua GitHub UI

argocd repo add https://github.com/acme \
  --github-app-id 123456 \
  --github-app-installation-id 987654321 \
  --key-file ./acme-argo-app.private-key.pem
```
