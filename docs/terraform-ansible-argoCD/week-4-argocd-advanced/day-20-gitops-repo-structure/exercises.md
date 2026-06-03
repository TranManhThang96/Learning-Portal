# Day 20 — Exercises: GitOps Repository Structure

## Overview

6 challenges từ dễ đến khó, phản ánh các tình huống thực tế khi thiết kế và vận hành GitOps repository structure.

**Estimated time:** 90–120 phút (mỗi challenge 15–20 phút)
**Yêu cầu chung:** Hoàn thành lesson.md và document.md trước

---

## Challenge 1: Migration Plan — 1 repo lẫn lộn → 3 repo

### Bối cảnh

Team ACME đang dùng 1 monorepo `acme-gitops/` có cấu trúc:

```
acme-gitops/
├── terraform/          # Terraform infra (SRE dùng)
├── helm/               # Platform addons (Platform dùng)
├── services/           # Microservices (App team dùng)
├── argocd/             # ArgoCD apps (Platform dùng)
└── .github/workflows/  # Tất cả CI lẫn lộn
```

**Vấn đề hiện tại:**
- App team merge → trigger Terraform CI (không cần)
- SRE apply Terraform → conflict với app commit
- RBAC không phân tách được
- 1 nghìn commits, repo 800MB

### Nhiệm vụ

Thiết kế **migration plan** trong 1 sprint (2 tuần) để tách thành 3 repo mà **không downtime production**.

### Yêu cầu

1. **Viết RFC ngắn** (500-800 từ) bao gồm:
   - Phân tích risk: mỗi bước có risk gì?
   - Thứ tự migration: tại sao infra trước, apps sau?
   - Chiến lược rollback: nếu migration fail ở tuần 2, làm sao?
   - Cutover strategy: làm sao switch ArgoCD từ old repo sang new repo mà không mất sync?

2. **Tạo migration checklist** (checklist format, 15-20 items)

3. **Tính toán blast radius:**
   - Nếu platform-repo migration fail, blast radius là gì?
   - Nếu apps-repo migration fail, blast radius là gì?

### Output mong đợi

```
exercises/challenge-1/
├── RFC.md              # Migration plan
├── CHECKLIST.md         # Step-by-step checklist
└── BLAST_RADIUS.md      # Risk analysis
```

### Hướng dẫn

**Migration sequence:**
1. Tạo 3 repo mới (infra/platform/apps)
2. Clone từng folder vào repo tương ứng (preserve Git history: `git subtree split`)
3. Setup CI riêng cho từng repo
4. Test trên dev: ArgoCD point vào repo mới
5. Staging: 100% traffic qua repo mới
6. Prod: switch từng ArgoCD Application
7. Keep old repo read-only 30 ngày (rollback window)
8. Archive old repo

---

## Challenge 2: Team-of-Teams Ownership Design

### Bối cảnh

Tổ chức ACME có cấu trúc team phức tạp:

| Team | Members | Concern |
|------|---------|---------|
| SRE | 4 | Infrastructure (EKS, RDS, networking) |
| Platform | 5 | Cluster addons, ArgoCD |
| API Team | 8 | api-service, auth-service |
| Worker Team | 5 | worker-service, scheduler |
| Frontend Team | 6 | frontend-service |
| Security | 2 | Security policies, audit |
| DBA | 2 | Database configs |
| Dev Leads | 3 | Architecture, cross-cutting |

**Yêu cầu:**

1. **Viết CODEOWNERS đầy đủ** cho 3 repo (`infra-repo`, `platform-repo`, `apps-repo`) thể hiện:
   - SRE owns infra
   - Platform owns platform
   - Mỗi app team owns service của họ
   - Prod overlays require SRE lead approval
   - Security required review cho security-sensitive services (auth, payment)
   - DBA required review cho database-related changes

2. **Thiết kế AppProject mapping:**
   - Mỗi team có AppProject riêng
   - RBAC đủ: team chỉ deploy vào namespace của họ
   - Không team nào có quyền sửa cluster-level resource

3. **Vẽ ownership matrix** (ASCII table 8 team × 10 resource paths)

### Output mong đợi

```
exercises/challenge-2/
├── CODEOWNERS-infra      # infra-repo CODEOWNERS
├── CODEOWNERS-platform   # platform-repo CODEOWNERS
├── CODEOWNERS-apps       # apps-repo CODEOWNERS
├── APPPROJECTS/          # AppProject YAML files
│   ├── sre-project.yaml
│   ├── platform-project.yaml
│   ├── api-team-project.yaml
│   ├── worker-team-project.yaml
│   └── frontend-team-project.yaml
└── OWNERSHIP_MATRIX.md   # 8×10 table
```

### Constraints

- Security team phải approve mọi thay đổi trong `policies/`
- DBA phải approve thay đổi `infra-repo/modules/rds/`
- API team không có quyền sửa `services/worker-service/`
- SRE lead phải approve mọi thay đổi trong `*/overlays/prod/`
- Platform team không có quyền sửa `services/*`

---

## Challenge 3: Implement ArgoCD Image Updater

### Bối cảnh

Team muốn auto-promote image mới từ CI build vào ArgoCD dev environment mà không cần manual PR.

### Nhiệm vụ

**Option A (ArgoCD Image Updater):** Cấu hình ArgoCD Image Updater cho `api-service-dev` auto-update image tag từ container registry.

**Option B (Renovate Bot):** Cấu hình Renovate bot tự động tạo PR khi image tag mới được publish.

### Setup giả định

```yaml
# Container registry: ghcr.io/acme/api-service
# Image tags available: v0.1.0, v0.2.0, v0.2.1, v0.3.0-beta
# ArgoCD Application: api-service-dev
#   path: services/api-service/overlays/dev
#   targetRevision: main
```

### Yêu cầu Option A (ArgoCD Image Updater)

1. Cài ArgoCD Image Updater (Helm installation)
2. Cấu hình `argocd-image-updater-config` ConfigMap
3. Annotate `api-service-dev` Application để Image Updater track image
4. Viết script/action cho Image Updater dùng write-back method (Git vs Kubernetes)

```yaml
# Starter: Application annotation
metadata:
  annotations:
    argocd-image-updater.argoproj.io/image-list: api=ghcr.io/acme/api-service
    argocd-image-updater.argoproj.io/api.update-strategy: semver
    argocd-image-updater.argoproj.io/api.helm.image-tag-name: image.tag
    argocd-image-updater.argoproj.io/write-back-method: git
```

5. Tạo GitHub App hoặc deploy key cho Image Updater write vào apps-repo

### Yêu cầu Option B (Renovate Bot)

1. Cấu hình `renovate.json` cho apps-repo
2. Configure `customManagers` để match `newTag:` trong kustomization.yaml
3. Configure auto-merge rules cho dev overlay (auto-merge sau CI pass)
4. Configure require review cho staging/prod overlay

```json
// Starter renovate.json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "platform": "github",
  "repositories": ["acme/apps-repo"],
  "customManagers": [
    {
      "customType": "regex",
      "fileMatch": ["**/kustomization.yaml"],
      "matchStrings": [
        "newTag:\\s*'?{{semverCommitted}}'?\\s*"
      ],
      "datasourceTemplate": "docker"
    }
  ],
  "packageRules": [
    {
      "matchPaths": ["services/**/overlays/dev/**"],
      "autoMerge": true,
      "automergeType": "pr"
    }
  ]
}
```

### Output mong đợi

```
exercises/challenge-3/
├── argocd-image-updater/
│   ├── helm-values.yaml          # ArgoCD Image Updater Helm values
│   ├── configmap.yaml             # ConfigMap configuration
│   ├── application-patch.yaml    # Application annotation patch
│   └── git-credentials.sh         # Setup deploy key script
└── renovate/
    ├── renovate.json
    └── RENOVATE_README.md        # Giải thích config
```

### Bonus

Xử lý trường hợp: Image Updater/Renovate tạo PR nhưng image mới có security CVE (Critical) — viết policy để block auto-merge.

---

## Challenge 4: Promotion Incident — Recovery & Prevention

### Bối cảnh

Thứ 6, 17:30, junior dev đang deploy hotfix. Thay vì merge promotion PR staging → prod, dev merge **sai PR** — promotion PR chứa image `acme/api:v1.2.0-dev` (dev image, chưa tested).

Production nhận `v1.2.0-dev`, không có proper env var, 100% traffic returning 500.

### Timeline

```
17:32  Junior dev tạo PR #342: "api-service: promote dev → staging (v1.2.0-dev)"
17:35  DevOps lead review PR #342 → nhầm với PR #338 (staging → prod, v1.2.0)
17:36  PR #342 merged (v1.2.0-dev → prod)
17:37  ArgoCD prod sync
17:38  PagerDuty: 100% 5xx
17:40  On-call được alert
```

### Nhiệm vụ

**Part A: Recovery (trả lời bằng checklist)**

1. Immediate triage (0-5 min): Làm gì đầu tiên?
2. Rollback strategy: Rollback bằng cách nào, Git revert hay `argocd app rollback`?
3. Verify rollback: Làm sao verify cluster = Git sau rollback?
4. Incident declaration: Khi nào declare incident? Ai notify?

**Part B: Prevention (thiết kế safeguard mới)**

Thiết kế **4 safeguards** để ngăn nhầm lẫn tương tự:

1. **Label / Branch naming enforcement:** Làm sao prevent nhầm branch?
2. **CI gate:** Viết GitHub Action check để verify PR chỉ được merge vào đúng env?
3. **ArgoCD Application guard:** Làm sao ArgoCD detect và reject promotion sai?
4. **Process change:** Đề xuất process change (không phải tech change) để ngăn nhầm lẫn?

**Part C: Post-incident**

Viết template **post-incident report** (PIR) bao gồm:
- Timeline đầy đủ
- Root cause analysis (5-why format)
- 5 action items với owner và deadline

### Output mong đợi

```
exercises/challenge-4/
├── RECOVERY_CHECKLIST.md       # Part A
├── PREVENTION_DESIGN.md        # Part B
└── POST_INCIDENT_REPORT.md     # Part C (template)
```

### Hướng dẫn

**Part B — CI Gate (code mẫu):**

```yaml
# .github/workflows/validate-promotion.yml
name: Validate Promotion

on:
  pull_request:
    types: [opened, synchronize, reopened, labeled]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - name: Check PR labels
        run: |
          LABELS=$(gh pr view ${{ github.event.pull_request.number }} --json labels --jq '.labels[].name')
          echo "Labels: $LABELS"

          # Must have promotion label
          if ! echo "$LABELS" | grep -q "promotion"; then
            echo "ERROR: PR must have 'promotion' label"
            exit 1
          fi

          # Extract target env from path
          TARGET=$(echo "${{ github.event.pull_request.body }}" \
            | grep -oP '(?<=Target:\s)[\w-]+')

          # Prod promotions must have 2 approvers
          if [ "$TARGET" = "prod" ]; then
            APPROVALS=$(gh pr view ${{ github.event.pull_request.number }} \
              --json reviews --jq '[.reviews[] | select(.state=="APPROVED")] | length')
            if [ "$APPROVALS" -lt 2 ]; then
              echo "ERROR: Prod promotion requires 2 approvals"
              exit 1
            fi
          fi
```

---

## Challenge 5: Multi-Cluster GitOps Repo Design

### Bối cảnh

ACME mở rộng sang 3 regions:

| Cluster | Region | Environment | Node count |
|---------|--------|-------------|-----------|
| us-east-prod | us-east-1 | Production | 15 nodes |
| eu-west-prod | eu-west-1 | Production | 10 nodes |
| ap-south-prod | ap-south-1 | Production | 8 nodes |

**Yêu cầu:** Mỗi cluster đều chạy cùng application stack nhưng config khác nhau (replicas, resources, node selectors).

### Nhiệm vụ

1. **Thiết kế folder structure** cho apps-repo hỗ trợ multi-cluster:

   ```
   apps-repo/services/api-service/
   ???

   ??? folder structure để support:
   - us-east-prod: 10 replicas, m6i.xlarge, us-east-1 AZ
   - eu-west-prod: 6 replicas, m6i.large, eu-west-1 AZ
   - ap-south-prod: 4 replicas, m6i.large, ap-south-1a AZ
   ```

2. **Viết ApplicationSet** (Cluster generator hoặc Git generator) để deploy `api-service` lên cả 3 clusters từ 1 ApplicationSet definition

3. **Tính toán:** Khi promotion từ `main` → production, có 3 ArgoCD sync chạy đồng thời. Thiết kế **staged rollout** (us-east → eu-west → ap-south) dùng `sync-wave` hoặc Argo Rollouts

4. **Rollback strategy** khác cluster: Làm sao rollback chỉ us-east mà không ảnh hưởng eu-west/ap-south?

### Bonus

Thêm **environment separation**: team ở mỗi region có thể deploy hotfix riêng (regional deviation). Thiết kế mechanism để:
- Có base config chung
- Cho phép regional deviation
- Base promotion vẫn đi qua PR review
- Regional hotfix có thể nhanh hơn (2-eye thay vì 4-eye)

### Output mong đợi

```
exercises/challenge-5/
├── FOLDER_STRUCTURE.md           # ASCII tree
├── APPLICATION_SET/
│   ├── cluster-generator.yaml    # ApplicationSet using cluster selector
│   └── git-generator.yaml        # ApplicationSet using Git generator
├── ROLLOUT_STRATEGY/
│   ├── rollout.yaml               # Argo Rollouts progressive delivery
│   └── analysis-template.yaml     # Prometheus metrics analysis
└── REGIONAL_HOTFIX.md            # Hotfix mechanism design
```

---

## Challenge 6 (Advanced): Bank/Regulated — Full Design

### Bối cảnh

Bank ACME cần triển khai GitOps nhưng tuân thủ nghiêm ngặt:

**Regulatory requirements:**
- 4-eye review (2 người approve, không phải author) trên production
- Signed commits bắt buộc (GPG/SSH)
- Sync window: production ArgoCD chỉ sync trong maintenance window (22:00–06:00 UTC)
- Audit log export: mọi action phải được log, export được sang SIEM (Splunk/Sentinel)
- Disaster recovery: RTO < 15 phút, RPO < 5 phút
- Secrets rotation: Vault + External Secrets Operator

### Nhiệm vụ

**Part A: Repository structure + CI/CD**

1. Fork repo structure từ Template 4 trong document.md
2. Thiết kế **CI pipeline** cho mỗi repo với:
   - Signed commit verification (GPG)
   - Policy enforcement (OPA/conftest)
   - 4-eye approval enforcement (GitHub Enterprise required reviewers API)
   - Audit log emission (CloudEvents → webhook → SIEM)

3. Viết **Branch protection ruleset YAML** (GitHub Enterprise ruleset) cho:
   - `infra-repo/live/prod/`: 4-eye + signed commits + terraform plan pass
   - `platform-repo/argocd/applications/prod-*.yaml`: 4-eye + sync window check
   - `apps-repo/overlays/prod/`: 2-eye (app) + SRE lead + signed commit

**Part B: ArgoCD Sync Window + Security**

1. Cấu hình **Sync Window** cho production ArgoCD Applications:
   - Maintenance window: 22:00–06:00 UTC (8 giờ mỗi đêm)
   - Freeze window: 2 ngày trước month-end (không deploy)
   - Emergency override: có thể bypass nhưng cần 3-eye approval

```yaml
# Starter sync window configuration
spec:
  syncPolicy:
    syncOptions:
      - SyncOptionSyncWindow=true
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-prod
spec:
  # ... application spec
```

2. Thiết kế **Emergency bypass flow**: Khi production down vào 10:00 UTC, làm sao deploy hotfix khi sync window đóng?

**Part C: Disaster Recovery**

1. Thiết kế **Backup strategy** cho GitOps:
   - Git backup: tần suất, destination
   - Cluster state backup: Velero schedule
   - ArgoCD Application backup: cách restore nhanh
   - Secrets backup: Vault snapshot

2. Viết **Runbook DR** cho 2 scenario:
   - Scenario A: apps-repo bị mất (GitHub outage 24h)
   - Scenario B: Cluster us-east-prod bị mất hoàn toàn (fire)

**Part D: Security Checklist**

Viết security checklist cho team review (20 items) bao gồm:
- Secrets management
- RBAC/permissions
- Network policies
- Image security
- Compliance evidence

### Output mong đợi

```
exercises/challenge-6/
├── REPO_STRUCTURE.md              # ASCII tree
├── CI_CD/
│   ├── infra-pipeline.yml
│   ├── platform-pipeline.yml
│   └── apps-pipeline.yml
├── BRANCH_PROTECTION/
│   ├── prod-ruleset.yml
│   └── sync-check-workflow.yml
├── ARGOCD_SECURITY/
│   ├── sync-windows.yaml
│   └── emergency-bypass.md
├── DISASTER_RECOVERY/
│   ├── backup-strategy.md
│   ├── runbook-github-outage.md
│   └── runbook-cluster-loss.md
└── SECURITY_CHECKLIST.md          # 20-item checklist
```

---

## Bonus Challenges

### Challenge 7: GitOps Metrics Dashboard

Thiết kế ArgoCD dashboard (Grafana JSON) đo:

- Mean time to deploy (MTTD) per service
- Deployment frequency per day
- Failed deployments rate
- Time from PR merge to ArgoCD sync
- Sync delta (Git vs cluster drift detection)

### Challenge 8: Cost Optimization — Repo CI Analysis

Phân tích chi phí GitHub Actions giữa monorepo và polyrepo cho ACME (8 services, 10 team members, 50 deploys/day).

Tính toán:
- GitHub Actions minutes cho từng mô hình
- Cost estimation ($/month)
- Recommendation với justification

---

## Submission Guidelines

Mỗi challenge tạo folder riêng trong `exercises/`:
- Viết bằng Markdown
- Code snippets phải là production-quality (không có TODO)
- Include ASCII diagrams cho structural challenges
- Mỗi challenge có 1 file `SOLUTION.md` tóm tắt approach + decision made

---

## Expected Completion

| Challenge | Difficulty | Time | Key concept |
|-----------|-----------|------|------------|
| 1 | Medium | 20 min | Migration planning |
| 2 | Medium | 20 min | Ownership + RBAC |
| 3 | Medium-Hard | 25 min | Image automation |
| 4 | Medium | 20 min | Incident recovery |
| 5 | Hard | 25 min | Multi-cluster |
| 6 | Very Hard | 30 min | Enterprise compliance |
