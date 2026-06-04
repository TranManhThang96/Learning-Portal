# Day 20 — GitOps Repository Structure

> **GitOps không chỉ là ArgoCD. GitOps = Git là single source of truth cho cả infrastructure lẫn application.**
> Hôm nay ta thiết kế repository structure production-grade — nền tảng cho toàn bộ 15 ngày còn lại.

**Thời lượng:** 2 tiếng
**Prerequisite:** Hoàn thành Day 17–19 (ArgoCD architecture, Application, Helm/Kustomize)
**Output:** 3 repo skeleton + ArgoCD root-app + promotion/rollback workflow

---

## 1. Mục tiêu ngày học

- Phân biệt monorepo vs polyrepo và chọn approach phù hợp với team size và maturity
- Thiết kế tách 3 repo: `infra-repo` (Terraform), `platform-repo` (cluster-level), `apps-repo` (application-level GitOps)
- Áp dụng environment folder strategy: per-env folder vs per-env branch và đánh giá trade-off
- Triển khai promotion bằng Pull Request và rollback bằng Git revert có audit trail
- Viết README giải thích ownership và CODEOWNERS rõ ràng cho 3 repo

---

## 2. Bối cảnh thực tế

### Chuyện thật mà ai cũng gặp

Team ACME có 8 microservice chạy trên EKS, Terraform quản infrastructure, ArgoCD đã install. Mỗi service team tự push deployment vào 1 monorepo lớn `acme-infra-platform-apps/`:

```
acme-infra-platform-apps/
├── terraform/          # EKS, RDS, networking
├── helm-charts/        # ingress-nginx, prometheus
├── services/
│   ├── api/
│   ├── worker/
│   └── frontend/
└── argocd/
```

**Các vấn đề xuất hiện sau 3 tháng:**

| Vấn đề | Hệ quả |
|---------|--------|
| PR review chậm | Frontend dev review file Terraform (không hiểu) |
| Terraform apply sai trigger | Commit chỉnh Helm chart → trigger apply infra |
| Không RBAC được | 1 repo = 1 quyền → app team sửa được Terraform |
| Promotion = "copy file" | Dev merge file → staging → prod = copy tay |
| Rollback = sửa lại file | Mất history, không ai biết version trước là gì |
| Không audit trail | Không biết ai merge cái gì lúc nào |

**Tình huống cụ thể:** Tuần trước, một junior dev push commit sửa `image: nginx:latest` trong Helm chart lên branch `main`. Terraform plan chạy tự động, thấy diff → apply → production down 40 phút vì `latest` tag không deterministic.

### Sau Day 20

Sau ngày hôm nay, team sẽ có:

```
acme-org/
├── acme/infra-repo/         (SRE/DevOps — Terraform, EKS, RDS)
├── acme/platform-repo/      (Platform team — cluster addons)
└── acme/apps-repo/          (App teams — microservices GitOps)
```

- Rule rõ ràng: ai sửa được gì, ai phải review gì
- Promotion = PR, rollback = `git revert` — Git là source of truth
- CI độc lập: Terraform plan không chạy khi app team merge chart
- Audit trail đầy đủ: PR = promotion, revert = rollback
- **Chuẩn bị cho Day 21:** App-of-Apps pattern sẽ dùng chính skeleton này

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Tại sao tách repo?

Trước khi hỏi "làm thế nào", hãy hỏi "tại sao cần tách". Có 4 lý do thực sự:

#### 1. Ownership boundary

```
infra-repo     → SRE / DevOps team quản
platform-repo  → Platform team quản
apps-repo      → App team quản (mỗi team 1 sub-folder hoặc 1 repo)
```

Nếu 1 repo cho tất cả: app team có quyền write Terraform (nguy hiểm), SRE phải review PR Helm chart (lãng phí thời gian).

#### 2. Change frequency khác biệt

| Layer | Tần suất thay đổi | CI expectation |
|-------|-------------------|----------------|
| Infrastructure | ~1 lần/tuần | Slow, thorough, approve nhiều |
| Platform | ~3-5 lần/tuần | Medium, conftest, policy check |
| Application | ~10-50 lần/ngày | Fast, automated, pre-merge |

Chung 1 repo: mọi commit trigger cùng 1 CI pipeline → 50 lần merge app/ngày = 50 lần Terraform plan chạy không cần thiết.

#### 3. Blast radius

Khi merge 1 PR sửa Helm chart của service A, ta MUỐN:
- Deploy service A → **Có**
- Trigger Terraform plan/apply → **Không**
- Trigger deploy service B, C, D → **Không**

Tách repo → CI filter path → chỉ chạy pipeline liên quan.

#### 4. Compliance

| Môi trường | Review requirement |
|------------|--------------------|
| Bank/financial | 4-eye review (2 người approve) trên infra + prod |
| Healthcare | Audit log, signed commits |
| Startup | 1-eye review (author khác approve là đủ) |

Không thể enforce 4-eye trên app repo (thay đổi nhanh) VÀ infra repo (thay đổi chậm) nếu cùng 1 repo có cùng branch protection rule.

---

### 3.2 Mô hình 3-repo chi tiết

Đây là default recommendation cho team 10+ người:

```
acme-org/
│
├── infra-repo/                          # ★ SRE / DevOps owns
│   ├── modules/                         # Terraform modules reuse
│   │   ├── network/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── eks/
│   │   └── rds/
│   ├── live/                            # Environment-specific
│   │   ├── dev/
│   │   │   └── main.tf                 # module "eks" { source = "../../modules/eks" }
│   │   ├── staging/
│   │   └── prod/
│   ├── .github/
│   │   └── workflows/
│   │       ├── terraform-fmt.yml
│   │       ├── terraform-validate.yml
│   │       ├── terraform-plan.yml       # PR: plan only
│   │       └── terraform-apply.yml      # Merge to main: apply
│   ├── .gitignore
│   ├── CODEOWNERS
│   └── README.md
│
├── platform-repo/                       # ★ Platform team owns
│   ├── argocd/
│   │   ├── bootstrap/
│   │   │   └── root-app.yaml           # App of Apps entry point
│   │   ├── projects/
│   │   │   ├── platform-project.yaml
│   │   │   └── team-project.yaml
│   │   └── applications/
│   │       ├── ingress-nginx.yaml
│   │       ├── cert-manager.yaml
│   │       ├── external-secrets.yaml
│   │       ├── prometheus-stack.yaml
│   │       └── loki.yaml
│   ├── platform-services/               # Helm values (not charts)
│   │   ├── ingress-nginx/
│   │   │   └── values.yaml
│   │   ├── cert-manager/
│   │   │   └── values.yaml
│   │   └── external-secrets/
│   │       └── values.yaml
│   ├── policies/                        # OPA / Kyverno
│   │   ├── disallow-latest-tag.yaml
│   │   └── require-resources.yaml
│   ├── .github/
│   │   └── workflows/
│   │       ├── lint.yml                # conftest, kubesec
│   │       └── validate-apps.yml
│   ├── CODEOWNERS
│   └── README.md
│
└── apps-repo/                           # ★ App teams own per service
    ├── services/
    │   ├── api-service/
    │   │   ├── base/
    │   │   │   ├── deployment.yaml
    │   │   │   ├── service.yaml
    │   │   │   ├── hpa.yaml
    │   │   │   └── kustomization.yaml
    │   │   └── overlays/
    │   │       ├── dev/
    │   │       │   ├── kustomization.yaml
    │   │       │   └── replicas-patch.yaml
    │   │       ├── staging/
    │   │       │   ├── kustomization.yaml
    │   │       │   └── resources-patch.yaml
    │   │       └── prod/
    │   │           ├── kustomization.yaml
    │   │           └── resources-patch.yaml
    │   ├── worker-service/
    │   │   ├── base/
    │   │   └── overlays/{dev,staging,prod}/
    │   └── frontend-service/
    │       ├── base/
    │       └── overlays/{dev,staging,prod}/
    ├── argocd/
    │   ├── projects/
    │   │   └── api-team-project.yaml
    │   └── applications/
    │       ├── api-service-dev.yaml
    │       ├── api-service-staging.yaml
    │       └── api-service-prod.yaml
    │       # Hoặc dùng ApplicationSet (Day 22)
    ├── .github/
    │   └── workflows/
    │       ├── kustomize-build.yml     # validate overlays
    │       ├── image-bump.yml           # auto PR khi image mới
    │       └── promote.yml              # manual promotion PR
    ├── .github/
    │   └── CODEOWNERS
    └── README.md
```

#### Dependency graph

```
infra-repo
  │
  │ provisions
  ▼
┌─────────────────┐
│  EKS Cluster    │
│  (Control Plane)│
└────────┬────────┘
         │ ArgoCD sync
         ▼
┌─────────────────────────────────┐
│       platform-repo             │
│  (ingress-nginx, cert-manager,  │
│   prometheus, external-secrets) │
└────────┬────────────────────────┘
         │ ArgoCD sync
         ▼
┌─────────────────────────────────┐
│         apps-repo               │
│  (api-service, worker,          │
│   frontend per environment)     │
└─────────────────────────────────┘
```

**Nguyên tắc:** infra-repo không bao giờ phụ thuộc platform-repo hoặc apps-repo. platform-repo và apps-repo không tạo infrastructure (không gọi Terraform provider). Thứ tự destroy: apps → platform → infra.

---

### 3.3 Monorepo vs Polyrepo — Deep comparison

#### 3 cách tổ chức thực tế

**Cách A: Monorepo (1 repo, 3 thư mục)**

```
acme/
├── infra/
│   ├── modules/
│   └── live/{dev,staging,prod}/
├── platform/
│   ├── argocd/
│   └── helm/
└── apps/
    ├── api/
    └── worker/
```

| Pros | Cons |
|------|------|
| Atomic change (1 PR thay đổi cả infra + app) | CI duration dài (path filter không hoàn hảo) |
| Tooling đơn giản (1 .tool-versions, 1 pre-commit) | RBAC khó (GitHub Enterprise mới có path-based) |
| Clone 1 lần, grep toàn bộ | Repo nặng khi scale (500+ service) |
| Dependency refactor dễ | Blast radius lớn khi có incident |

**Cách B: Hybrid (2 repo)**

```
acme/
├── acme-gitops/           # infra + platform (monorepo 2 layer)
│   ├── terraform/
│   ├── platform/
│   └── argocd/
└── acme-services/          # Mỗi team 1 repo (polyrepo)
    ├── api-service/
    ├── worker-service/
    └── frontend-service/
```

| Pros | Cons |
|------|------|
| Ownership rõ hơn monorepo thuần | Cross-cutting change (app cần platform change) = multi-repo PR |
| CI phân chia tốt hơn | |

**Cách C: Polyrepo 3+ (recommend cho enterprise)**

```
acme-infra/       # Terraform only
acme-platform/    # Cluster addons + ArgoCD
acme-api/         # 1 service = 1 repo
acme-worker/
acme-frontend/
```

| Pros | Cons |
|------|------|
| Ownership hoàn toàn tách biệt | Cross-cutting change cần nhiều PR |
| CI nhanh nhất (chỉ trigger khi đổi repo đó) | Duplicated tooling (phải sync config) |
| RBAC tự nhiên (repo-level) | Dependency version skew (Helm chart version khác nhau) |
| Compliance dễ enforce | |

#### Decision matrix

| Team size | Maturity | Recommendation | Reasoning |
|-----------|----------|-----------------|-----------|
| Solo | N/A | Monorepo | 1 nơi clone, đơn giản |
| 2–5 dev | Startup | Monorepo | Tooling đơn giản, ownership ngầm |
| 5–15 dev | Growing | Hybrid: monorepo infra+platform + per-service apps | App team velocity cao, platform ổn định |
| 15–30 dev | Scale | Polyrepo 3 repo + team-based apps | Ownership rõ, compliance |
| 30+ dev | Enterprise | Polyrepo 3+ + per-service repos + signed commits | Compliance, audit, RBAC nghiêm ngặt |

**Ngày hôm nay dùng:** Polyrepo 3 repo (infra/platform/apps) vì nó là default cho production GitOps.

---

### 3.4 Environment Folder Strategy

Có 3 cách tổ chức environment trong GitOps:

#### Strategy A: Per-env Folder (RECOMMEND)

```
apps-repo/services/api-service/
├── base/
│   └── kustomization.yaml
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml      # image: acme/api:dev-abc123
    │   └── replicas-patch.yaml     # replicas: 1
    ├── staging/
    │   ├── kustomization.yaml      # image: acme/api:v1.2.3
    │   └── resources-patch.yaml    # replicas: 3
    └── prod/
        ├── kustomization.yaml      # image: acme/api:v1.2.2
        └── resources-patch.yaml    # replicas: 10, HPA enabled
```

```yaml
# overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: acme/api-service
    newTag: v1.2.3       # ← Promotion: đổi tag này
```

**ArgoCD Application point vào folder cụ thể:**

```yaml
# argocd/applications/api-service-staging.yaml
spec:
  source:
    repoURL: https://github.com/acme/apps-repo.git
    path: services/api-service/overlays/staging
    targetRevision: main   # ← Trunk-based: luôn main, chỉ đổi folder
```

| Pros | Cons |
|------|------|
| 1 branch (main) duy nhất | Vô tình có thể commit vào overlay sai env |
| Promotion = PR thay đổi image tag | Cần discipline (PR review) |
| Lịch sử Git gom trong 1 branch | |
| Dễ audit (1 PR = 1 promotion) | |

#### Strategy B: Per-env Branch (legacy, không recommend)

```
branches: dev / staging / main (prod)
```

| Pros | Cons |
|------|------|
| Isolation rõ ràng | Cherry-pick conflict khi merge lên prod |
| Dễ restrict prod branch | Audit bằng tag (không bằng PR) |
| | Prod branch protection mạnh nhưng dev/staging lỏng |
| | Multi-cluster phức tạp (mỗi cluster 1 branch?) |

#### Strategy C: Per-env Repo (extreme)

```
acme-apps-dev    # 1 repo = 1 env
acme-apps-staging
acme-apps-prod
```

| Pros | Cons |
|------|------|
| Blast radius nhỏ nhất | 3 lần tooling, 3 lần CI config |
| Không bao giờ nhầm env | Cross-env diff không thể làm |
| | |

**Best practice 2025:** Per-env folder + trunk-based (1 branch `main`). Dùng ArgoCD `path` filter để point vào overlay cụ thể.

---

### 3.5 Branch Strategy chi tiết

Với per-env folder, ta dùng **trunk-based development**:

```
main ──────────────────────────────────────────────────►
  │                                                      ▲
  │  PR #45: api-service/overlays/dev/kustomization.yaml  │
  │  image: acme/api:v1.3.0                              │
  │  Auto-merge sau CI pass                               │
  │                                                      │
  │  PR #46: api-service/overlays/staging/kustomization  │
  │  image: acme/api:v1.3.0                              │
  │  Manual review + approve                              │
  │                                                      │
  │  PR #47: api-service/overlays/prod/kustomization.yaml │
  │  image: acme/api:v1.3.0                              │
  │  SRE lead review + approve (4-eye)                   │
  │                                                      │
  │  PR #48: infra-repo/live/prod/main.tf                 │
  │  node_type: m6i.xlarge → m6i.2xlarge                  │
  │  4-eye review bắt buộc                               │
  │                                                      │
  │  PR #49: revert #45 (bug fix rolled back)            │
  │  image: acme/api:v1.2.9                              │
  │                                                      │
  └──────────────────────────────────────────────────────
```

**Nguyên tắc branch:**
- `main` duy nhất (không `develop`, `release`, `hotfix`)
- Feature branch cho tất cả thay đổi
- Squash merge để giữ history sạch
- Tag (vX.Y.Z) chỉ dùng cho audit, không dùng để deploy
- **KHÔNG BAO GIỜ commit trực tiếp lên main**

---

### 3.6 Promotion qua Pull Request

Promotion = thay đổi `image tag` hoặc `chart version` ở overlay của environment mục tiêu qua Pull Request.

#### Promotion flow toàn bộ

```
┌──────────────────────────────────────────────────────────────────────┐
│  CI BUILD (external)                                                 │
│  1. Developer push code → GitHub → CI build                         │
│  2. Docker build → push to registry: acme/api:v1.3.0                 │
│  3. CI update image tag in tracking file or commit                   │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AUTO IMAGE BUMP (Renovate / ArgoCD Image Updater / GitHub Action)    │
│  4. Bot detect image: acme/api:v1.3.0 is new                          │
│  5. Bot create PR: overlays/dev/kustomization.yaml                    │
│     newTag: v1.3.0                                                    │
│  6. CI validate → auto-merge                                         │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
         ArgoCD dev sync              Manual verify
                    │                         │
                    │  ▲                     │
                    │  │ PR tạo tự động      │
                    │  │ overlays/staging/    │
                    ▼  │ kustomization.yaml  │
               ArgoCD dev OK   │
                                  │
                                  ▼ Manual promotion PR
                         ┌───────────────┐
                         │ PR #N: staging│
                         │ image: v1.3.0 │
                         │ Team review   │
                         │ Approve + merge│
                         └───────┬───────┘
                                 │ ArgoCD staging sync
                                 ▼
                         ArgoCD staging OK
                                 │
                                 ▼ Manual promotion PR (SRE lead)
                         ┌───────────────┐
                         │ PR #N+1: prod │
                         │ image: v1.3.0 │
                         │ 4-eye approve │
                         │ Merge         │
                         └───────┬───────┘
                                 │ ArgoCD prod sync
                                 ▼
                          ArgoCD prod OK
```

#### Promotion = thay đổi file Git

**Điều quan trọng nhất về promotion:** Promotion KHÔNG phải là `argocd app sync`. Promotion là thay đổi Git manifest.

```bash
# Sai: promotion bằng tay → không có audit trail
argocd app sync api-service-prod  # ← Chỉ sync cluster, Git không đổi

# Đúng: promotion = PR → Git thay đổi → ArgoCD tự sync
# File: services/api-service/overlays/prod/kustomization.yaml
-   newTag: v1.2.9
+   newTag: v1.3.0
```

**Tại sao không dùng `argocd app sync` làm promotion?**
- `argocd app sync` chỉ thay đổi cluster, không thay đổi Git
- Next sync (auto hoặc manual) sẽ đưa cluster về version trong Git
- Drift xảy ra: cluster ≠ Git → mất single source of truth
- Không audit trail: không ai biết ai sync lúc nào

---

### 3.7 Rollback bằng Git Revert

Rollback = tạo commit mới revert thay đổi của commit xấu.

```bash
# Xem lịch sử
git log --oneline --follow services/api-service/overlays/prod/kustomization.yaml

# Rollback bằng revert
git revert abc1234f  # tạo commit mới: "Revert commit abc1234f"
git push

# ArgoCD detect Git change → tự sync
# Audit trail: PR + revert PR đều có, rõ ràng
```

**Nguyên tắc rollback:**

| Cách | Dùng khi | Không dùng khi |
|------|----------|----------------|
| `git revert <sha>` | Prod deployment có bug | N/A — luôn dùng cách này |
| `git reset --hard` | **KHÔNG BAO GIỜ** trên prod | Mất history, drift Git vs cluster |
| `argocd app rollback` | Dev/staging thử nhanh | Prod — chỉ rollback cluster, không Git |

**So sánh `git revert` vs `argocd app rollback`:**

```
git revert (PROD)
─────────────────────────────────────────────────────────
1. git revert abc1234f
2. git push
3. GitHub: PR được tạo (audit trail)
4. ArgoCD: detect change → sync
5. Cluster: về version trước
6. Git: ở version trước ✓ (source of truth = cluster)

argocd app rollback (PROD — AVOID)
─────────────────────────────────────────────────────────
1. argocd app rollback api-service-prod 42
2. Cluster: về revision 42 ✓
3. Git: vẫn ở bad commit ✗
4. Drift: next ArgoCD sync sẽ đưa cluster về bad version
5. Ai đó chạy ArgoCD sync = lại down
```

**Trường hợp đặc biệt:** Khi rollback phải nhanh (incident P1), ta làm:

```bash
# Bước 1: Emergency rollback (cluster)
argocd app rollback api-service-prod --revision <good-revision>

# Bước 2: Ghi lại vào Git NGAY trong 5 phút
git revert <bad-sha>
git push  # PR auto-merge hoặc được approve nhanh

# Bước 3: Verify Git = cluster
argocd app sync api-service-prod  # đưa cluster về đúng Git
```

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 Bảng so sánh chi tiết Monorepo vs Polyrepo

| Tiêu chí | Monorepo (1 repo) | Polyrepo (3+ repo) |
|----------|-------------------|-------------------|
| Atomic change | 1 PR thay đổi infra + app | Multi-repo PR cần đồng bộ |
| CI duration | Dài (filter path không hoàn hảo) | Ngắn (repo-level trigger) |
| Ownership | CODEOWNERS path-based (GH Enterprise) | Repo-level tự nhiên |
| RBAC | Path-based (cần GH Enterprise) | Repo-level (built-in) |
| Tooling consistency | Enforced tự nhiên | Cần sync tooling config |
| Disaster recovery | 1 repo restore | Nhiều repo restore |
| Search / cross-cutting | Grep 1 repo | Cần tool hoặc `git grep` nhiều repo |
| Build tool | Bazel / Nx / Turborepo | Per-repo Makefile |
| Scaling | Chậm khi >500 services | Tốt |
| Onboarding | Clone 1 repo | Clone nhiều repo |
| Dependency version | Dễ enforce | Khó (cần Renovate/Mrenovate) |

### 4.2 Trade-offs theo context cụ thể

| Context | Recommend | Lý do |
|---------|-----------|--------|
| Cá nhân học / side project | Monorepo | 1 nơi clone, đơn giản |
| Startup < 10 người | Monorepo cả 3 layer | Tooling đơn giản, velocity cao |
| Team 10–30 người | Hybrid: monorepo infra+platform + per-service apps | App team muốn độc lập |
| Team 30–100 người | Polyrepo 3 repo + team-based apps | Ownership rõ, CI nhanh |
| Enterprise 100+ người | Polyrepo strict + per-service + signed commits + branch protection nghiêm ngặt | Compliance, audit, security |
| Bank / financial regulated | Polyrepo + 4-eye review + signed commits + sync window + audit log export | Regulatory requirement |

### 4.3 Performance, Cost, Security

#### Performance

```
ArgoCD repo-server clone behavior:
──────────────────────────────────
Monorepo (1GB):
  First clone: ~30s
  Subsequent:  cached (OK)
  Path-based cache: ArgoCD 2.7+ support

Polyrepo (mỗi repo 50MB):
  Clone per repo: ~5s
  Total 3 repos: ~15s
  Cache per repo: independent ✓
```

**Solution cho monorepo lớn:** ArgoCD 2.7+ `execoras` cache + shallow clone (`--depth 1`) + path filter.

#### Cost (GitHub Actions)

```
Monorepo: mỗi commit trigger tất cả workflow
  → 50 commits/ngày × CI pipeline dài
  → ~5000 phút/tháng

Polyrepo: chỉ trigger workflow của repo bị đổi
  → 50 commits (app) × CI ngắn + 5 commits (infra) × CI dài
  → ~1500 phút/tháng
```

#### Security

| Vấn đề | Monorepo | Polyrepo |
|---------|----------|----------|
| Secrets trong repo | Dễ accidentally commit | Isolation tốt hơn |
| RBAC | Cần Enterprise | Built-in repo-level |
| Credential rotation | 1 repo credentials | Per-repo credentials |
| ArgoCD credential | 1 credential nhiều app | Repo riêng = credential riêng |
| Blast radius khi breach | Lớn (1 repo = tất cả) | Nhỏ |

**Best practice ArgoCD credential:**
```bash
# Tạo deploy key riêng cho mỗi repo
# KHÔNG dùng personal access token (PAT)
# Khi người tạo PAT nghỉ việc → repo không access được

# Tạo GitHub Machine User
# - 1 account không thuộc ai cụ thể
# - Read-only deploy key cho apps-repo
# - Read-write cho platform-repo (auto-merge)
```

### 4.4 Common Anti-patterns và cách tránh

| # | Anti-pattern | Hệ quả | Prevention |
|---|-------------|--------|------------|
| 1 | Helm chart + source code cùng repo | Image build trigger deploy cycle | Tách: source repo vs GitOps repo |
| 2 | Quên CODEOWNERS | Bất kỳ ai approve PR cũng được | Require CODEOWNERS review trên branch protection |
| 3 | Dùng `latest` tag | ArgoCD không detect change | Always use immutable tag (digest hoặc semver) |
| 4 | Promotion bằng `argocd app sync` | Drift Git vs cluster | Chỉ dùng PR promotion |
| 5 | Dùng `git reset --hard` | Mất history, drift | Chỉ dùng `git revert` |
| 6 | ArgoCD dùng PAT cá nhân | Bot fail khi người đó nghỉ | Machine user với deploy key |
| 7 | App team có quyền trong platform-repo | Có thể sửa cluster-level addons | Repo-level RBAC + branch protection |
| 8 | Cluster-scope resource (CRD, ClusterRole) trong apps-repo | App team vô tình ảnh hưởng cluster | Chỉ namespace-scope trong apps-repo |
| 9 | Admin bypass branch protection | Mất audit | Không admin bypass, dùng protected branch |
| 10 | Không có sync window | ArgoCD auto-sync prod 24/7 | Sync window chỉ trong maintenance window |
| 11 | Override image tag bằng `--prune=false` | Leftover resources sau rollback | Luôn dùng `prune: true` |
| 12 | Merge PR bằng squash và delete branch | Mất individual commit history | `merge commit` giữ history rõ hơn squash |
| 13 | Hardcode credentials trong ArgoCD Application | Credential expose | External secret (ExternalSecrets Operator) |
| 14 | Không có `spec.syncPolicy.automated` đánh dấu rõ | Không biết app auto-sync hay manual | Luôn khai báo rõ ràng trong spec |
| 15 | Quên `resource.healthcheacks` trong ArgoCD Application | ArgoCD luôn cho OutOfSync | Khia báo health check hoặc `healthLua` |

---

## 5. Hands-on Lab — 60 phút

### Trước khi bắt đầu

**Yêu cầu:**
- Kubernetes cluster (kind, minikube, hoặc EKS/GKE)
- ArgoCD installed (nếu chưa có — xem Day 17)
- kubectl configured
- GitHub account (hoặc dùng local bare repo)
- gh CLI (GitHub CLI) installed

**Lựa chọn mode:**

| Mode | Dùng khi | Setup |
|------|----------|-------|
| A: GitHub real | Muốn học thực tế nhất | Tạo 3 repo public |
| B: Local bare repo | Không muốn tạo GitHub repo | `git init --bare` per repo |

**Mode A (GitHub — RECOMMEND):**

```bash
# Tạo 3 repo trên GitHub
gh auth login
gh repo create acme/infra-repo --public --clone
gh repo create acme/platform-repo --public --clone
gh repo create acme/apps-repo --public --clone

# Hoặc trên GitHub UI: Settings → Repositories → New
```

**Mode B (Local — cho ai không muốn dùng GitHub):**

```bash
mkdir -p ~/gitops-lab
cd ~/gitops-lab

# Tạo bare repo
git init --bare infra-repo.git
git init --bare platform-repo.git
git init --bare apps-repo.git

# Clone working copies
git clone infra-repo.git infra-repo
git clone platform-repo.git platform-repo
git clone apps-repo.git apps-repo
```

---

### Step 1: Tạo skeleton infra-repo

```bash
cd infra-repo
```

#### File: `README.md`

```markdown
# infra-repo

**Purpose:** Terraform code quản infrastructure cho ACME production.

**Owner:** @acme/sre
**Slack:** #team-sre

## Mô tả

Repo này chứa toàn bộ infrastructure as code:
- Network (VPC, subnets, NAT gateway)
- EKS cluster (node groups, managed node groups)
- RDS (PostgreSQL, MySQL)
- S3, IAM, KMS

## Cấu trúc

```
modules/           # Terraform modules reuse được
  network/         # VPC, subnets, route tables
  eks/             # EKS cluster, node groups
  rds/             # Database modules
live/              # Environment-specific
  dev/             # Development environment
  staging/         # Staging environment
  prod/            # Production environment
```

## Thêm module mới

1. Tạo module trong `modules/<name>/`
2. Gọi trong `live/<env>/main.tf`
3. PR → SRE review → merge

## Promotion flow

Infra thay đổi → PR → terraform plan → SRE review → merge → auto apply

## Rollback

**KHÔNG dùng** `terraform apply` rollback.
Dùng `git revert` → PR → terraform apply lại version trước.

## CI Checks

- terraform fmt
- terraform validate
- terraform plan (trên mọi PR)
- terraform apply (chỉ khi merge vào main)

## Branch protection

- Branch: `main`
- Require: 2 PR approval (4-eye)
- Status check: terraform-plan phải pass
- No force push
- Admin bypass: disabled
```

#### File: `CODEOWNERS`

```
# Global: SRE team owns everything
* @acme/sre

# Database: DBA phải review
/modules/database/ @acme/sre @acme/dba
/live/*/rds/ @acme/sre @acme/dba

# Production changes: SRE leads review
/live/prod/ @acme/sre-leads

# Staging: SRE standard
/live/staging/ @acme/sre

# Dev: SRE standard
/live/dev/ @acme/sre
```

#### File: `modules/network/main.tf` (skeleton)

```hcl
# modules/network/main.tf
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-vpc"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 4, count.index)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.environment}-private-subnet-${count.index + 1}"
    Type = "private"
  }
}

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 4, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.environment}-public-subnet-${count.index + 1}"
    Type = "public"
  }
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
```

#### File: `live/dev/main.tf` (module call)

```hcl
# live/dev/main.tf
module "network" {
  source = "../../modules/network"

  environment      = "dev"
  cidr_block       = "10.1.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
}

# Module call cho EKS, RDS...
```

#### File: `.github/workflows/terraform-fmt.yml`

```yaml
name: Terraform Format

on:
  pull_request:
    paths:
      - '**.tf'
      - '**.tfvars'
  push:
    branches: [main]

jobs:
  fmt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - run: terraform fmt -check -recursive
```

#### File: `.github/workflows/terraform-plan.yml`

```yaml
name: Terraform Plan

on:
  pull_request:
    paths:
      - '**.tf'
      - '**.tfvars'
      - 'modules/**'

env:
  TF_VAR_environment: dev  # override trong job

jobs:
  plan:
    runs-on: ubuntu-latest
    # Terraform plan chỉ chạy khi file .tf thay đổi
    # Không chạy khi chỉ sửa apps/
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Terraform Init
        run: terraform init
        working-directory: live/dev

      - name: Terraform Validate
        run: terraform validate
        working-directory: live/dev

      - name: Terraform Plan
        run: terraform plan -no-color
        working-directory: live/dev
        env:
          TF_VAR_environment: dev
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

---

### Step 2: Tạo skeleton platform-repo

```bash
cd ../platform-repo
```

#### File: `README.md`

```markdown
# platform-repo

**Purpose:** Cluster-level platform as code — ArgoCD, ingress controller, monitoring, secrets management.

**Owner:** @acme/platform
**Slack:** #team-platform

## Mô tả

Repo này chứa configuration cho platform-level addons:
- ArgoCD itself (bootstrap, AppProject)
- Ingress controller (ingress-nginx)
- Certificate management (cert-manager)
- External secrets (ExternalSecrets Operator)
- Monitoring stack (Prometheus, Grafana)
- Log aggregation (Loki)
- Policy engines (OPA, Kyverno)

## Cấu trúc

```
argocd/
  bootstrap/       # Root Application (App of Apps)
  projects/        # AppProject definitions
  applications/    # Application definitions cho platform addons
platform-services/ # Helm values (upstream charts từ artifact hub)
policies/          # OPA / Kyverno policies
```

## Ai được phép sửa gì

| Path | Team | Review rule |
|------|------|-------------|
| argocd/bootstrap/ | @acme/platform | Platform lead review |
| argocd/projects/ | @acme/platform | Platform lead review |
| argocd/applications/ | @acme/platform | Platform lead review |
| platform-services/ | @acme/platform | Platform lead review |
| policies/ | @acme/platform @acme/security | Security + platform co-review |

## Thêm platform addon mới

1. Helm chart values vào `platform-services/<addon>/values.yaml`
2. ArgoCD Application vào `argocd/applications/<addon>.yaml`
3. PR → Platform review → merge → ArgoCD sync

## CI Checks

- conftest / OPA eval (policy check)
- kustomize build (validate overlay)
- kubeval / conftest (Kubernetes manifest lint)

## ArgoCD sync

- Tự động sync khi merge vào main (auto-sync enabled)
- Prod: sync window 22:00–06:00 UTC (maintenance only)
```

#### File: `CODEOWNERS`

```
# Global: platform team
* @acme/platform

# Security-sensitive
argocd/projects/ @acme/platform @acme/security
policies/ @acme/platform @acme/security

# Production ArgoCD applications
argocd/applications/prod-*.yaml @acme/platform @acme/sre-leads
```

#### File: `argocd/bootstrap/root-app.yaml` (App of Apps)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-platform
  namespace: argocd
  labels:
    app.kubernetes.io/name: root-platform
    app.kubernetes.io/part-of: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: argocd/applications
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

#### File: `argocd/projects/platform-project.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
  namespace: argocd
spec:
  description: Platform addons project
  sourceRepos:
    - https://github.com/acme/platform-repo.git
    - https://github.com/acme/infra-repo.git
  destinations:
    - server: https://kubernetes.default.svc
      namespace: ingress-nginx
    - server: https://kubernetes.default.svc
      namespace: cert-manager
    - server: https://kubernetes.default.svc
      namespace: monitoring
    - server: https://kubernetes.default.svc
      namespace: loki
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  namespaceResourceBlacklist:
    - group: ""
      kind: ResourceQuota
  roles:
    - name: platform-admin
      description: Platform team admin
      groups:
        - acme-platform
      policies:
        - p, proj:platform:platform-admin, applications, *, platform/*, allow
        - p, proj:platform:platform-admin, applications, action/sync, platform/*, allow
```

#### File: `argocd/applications/ingress-nginx.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/acme/platform-repo.git
    targetRevision: main
    path: platform-services/ingress-nginx
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

#### File: `platform-services/ingress-nginx/values.yaml`

```yaml
controller:
  replicaCount: 2

  service:
    type: LoadBalancer
    annotations:
      # AWS: External DNS annotation
      external-dns.alpha.kubernetes.io/hostname: "*.acme.internal"

  resources:
    requests:
      cpu: 100m
      memory: 90Mi
    limits:
      cpu: 500m
      memory: 256Mi

  admissionWebhooks:
    enabled: true

  metrics:
    enabled: true
    serviceMonitor:
      enabled: true
```

---

### Step 3: Tạo skeleton apps-repo

```bash
cd ../apps-repo
```

#### File: `README.md`

```markdown
# apps-repo

**Purpose:** Application-level GitOps — microservices deployment qua ArgoCD.

**Owner:** @acme/dev-leads (global), mỗi service có team sở hữu riêng
**Slack:** #team-dev

## Mô tả

Repo này chứa Kubernetes manifests cho tất cả application microservices:
- base/: Kubernetes manifests gốc (Deployment, Service, HPA, ConfigMap)
- overlays/: Environment-specific overrides (image tag, replicas, resources)

## Cấu trúc

~~~
services/                  # Mỗi service 1 sub-folder
  <service-name>/
    base/                  # Base manifests
      deployment.yaml
      service.yaml
      hpa.yaml
      kustomization.yaml
    overlays/              # Per-env overrides
      dev/
        kustomization.yaml
        replicas-patch.yaml
      staging/
        kustomization.yaml
        resources-patch.yaml
      prod/
        kustomization.yaml
        resources-patch.yaml
argocd/
  projects/                # Per-team AppProject
  applications/            # ArgoCD Application cho mỗi service/env
~~~

## Promotion flow

1. CI build image → push: `acme/<service>:v1.2.3`
2. ArgoCD Image Updater hoặc Renovate tạo PR → `overlays/dev/kustomization.yaml`
3. CI test → auto-merge → ArgoCD dev sync
4. Dev verified → promotion PR → staging → ArgoCD staging sync
5. Staging verified → promotion PR → prod → ArgoCD prod sync

## Rollback

`git revert <sha>` → ArgoCD detect → sync về version trước

**KHÔNG BAO GIỜ** dùng `argocd app rollback` trên prod.

## Thêm service mới

1. Tạo `services/<new-service>/base/` với manifests
2. Tạo `services/<new-service>/overlays/{dev,staging,prod}/`
3. Tạo `argocd/applications/<new-service>-{dev,staging,prod}.yaml`
4. Tạo PR → team review → merge

## CI Checks

- kustomize build (validate overlay)
- kubeval / kubesec (security scan)
- conftest (policy check: no latest tag, require resources)

## Branch protection

- Branch: `main`
- Require: 1 approval từ team member (app repo)
- Require: 2 approval từ SRE lead (prod overlay changes)
- Status checks: CI pipeline pass
- No force push
```

#### File: `CODEOWNERS`

```
# Global: dev leads own all
* @acme/dev-leads

# Per-service ownership
/services/api-service/ @acme/api-team
/services/worker-service/ @acme/worker-team
/services/frontend-service/ @acme/frontend-team

# Prod overlays: SRE leads must approve
/services/*/overlays/prod/ @acme/dev-leads @acme/sre-leads

# Security-sensitive services
/services/payment-service/ @acme/payment-team @acme/security
/services/auth-service/ @acme/auth-team @acme/security
```

#### File: `services/api-service/base/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app: api-service
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
        version: v1
    spec:
      containers:
        - name: api-service
          image: acme/api-service:dev-placeholder  # replaced by kustomize
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: api-service-secrets
                  key: database-url
            - name: LOG_LEVEL
              value: "info"
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

#### File: `services/api-service/base/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  labels:
    app: api-service
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8080
      protocol: TCP
      name: http
  selector:
    app: api-service
```

#### File: `services/api-service/base/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml

commonLabels:
  app.kubernetes.io/name: api-service
  app.kubernetes.io/part-of: acme-platform
```

#### File: `services/api-service/overlays/dev/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: acme/api-service
    newTag: v0.1.0-dev

patches:
  - path: replicas-patch.yaml
```

#### File: `services/api-service/overlays/dev/replicas-patch.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 1
```

#### File: `services/api-service/overlays/staging/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: acme/api-service
    newTag: v0.1.0

patches:
  - path: resources-patch.yaml
```

#### File: `services/api-service/overlays/staging/resources-patch.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: api-service
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 1Gi
```

#### File: `services/api-service/overlays/prod/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

images:
  - name: acme/api-service
    newTag: v0.0.9   # ← Promotion: thay đổi tag này qua PR

patches:
  - path: resources-patch.yaml
```

#### File: `services/api-service/overlays/prod/resources-patch.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 10
  template:
    spec:
      containers:
        - name: api-service
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 2Gi
```

#### File: `argocd/projects/api-team-project.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: api-team
  namespace: argocd
spec:
  description: API team applications
  sourceRepos:
    - https://github.com/acme/apps-repo.git
    - https://github.com/acme/platform-repo.git
  destinations:
    - server: https://kubernetes.default.svc
      namespace: api-service
    - server: https://kubernetes.default.svc
      namespace: api-service-staging
    - server: https://kubernetes.default.svc
      namespace: api-service-prod
  roles:
    - name: api-team-admin
      groups:
        - acme-api-team
      policies:
        - p, proj:api-team:api-team-admin, applications, *, api-team/*, allow
```

#### File: `argocd/applications/api-service-prod.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  labels:
    environment: prod
    team: api
spec:
  project: api-team
  source:
    repoURL: https://github.com/acme/apps-repo.git
    targetRevision: main
    path: services/api-service/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: api-service-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: false    # prod: manual sync để control
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
  revisionHistoryLimit: 10
```

---

### Step 4: GitHub Actions — Image Bump Workflow

#### File: `.github/workflows/image-bump.yml`

```yaml
name: Image Bump

on:
  schedule:
    # Check registry every 30 phút
    - cron: '*/30 * * * *'
  workflow_dispatch:
    inputs:
      service:
        description: 'Service name'
        required: true
        default: 'api-service'
      registry:
        description: 'Container registry'
        required: true
        default: 'ghcr.io/acme'

jobs:
  detect-and-bump:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get latest image tag
        id: image
        run: |
          LATEST=$(crane ls ${{ inputs.registry }}/${{ inputs.service }} \
            | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' \
            | sort --version-sort \
            | tail -n 1)
          echo "tag=$LATEST" >> $GITHUB_OUTPUT
          echo "Latest tag: $LATEST"

      - name: Read current dev tag
        run: |
          CURRENT=$(grep "newTag:" services/${{ inputs.service }}/overlays/dev/kustomization.yaml \
            | awk '{print $2}')
          echo "Current dev tag: $CURRENT"

      - name: Create bump PR if new tag available
        if: steps.image.outputs.tag != ''
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GH_PAT }}
          commit-message: "chore(${{ inputs.service }}): bump image to ${{ steps.image.outputs.tag }}"
          title: "chore(${{ inputs.service }}): bump to ${{ steps.image.outputs.tag }}"
          body: |
            ## Image Bump

            Detected new image: `${{ inputs.registry }}/${{ inputs.service }}:${{ steps.image.outputs.tag }}`

            **Service:** ${{ inputs.service }}
            **Registry:** ${{ inputs.registry }}

            ArgoCD will automatically sync after merge.
          branch: image-bump/${{ inputs.service }}-${{ steps.image.outputs.tag }}
          base: main
          labels: |
            auto-bump
            ${{ inputs.service }}
          reviewers: |
            ${{ github.actor }}
          draft: false
```

---

### Step 5: GitHub Actions — Promotion Workflow

#### File: `.github/workflows/promote.yml`

```yaml
name: Promotion

on:
  workflow_dispatch:
    inputs:
      service:
        description: 'Service to promote'
        required: true
        type: choice
        options:
          - api-service
          - worker-service
          - frontend-service
      source_env:
        description: 'Source environment'
        required: true
        type: choice
        options:
          - dev
          - staging
      target_env:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - staging
          - prod

jobs:
  promote:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract source image tag
        id: source
        run: |
          TAG=$(grep "newTag:" services/${{ inputs.service }}/overlays/${{ inputs.source_env }}/kustomization.yaml \
            | awk '{print $2}')
          echo "tag=$TAG" >> $GITHUB_OUTPUT
          echo "Source tag: $TAG"

      - name: Create promotion PR
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GH_PAT }}
          commit-message: "promote(${{ inputs.service }}): ${{ inputs.source_env }} → ${{ inputs.target_env }}"
          title: "promote(${{ inputs.service }}): ${{ inputs.source_env }} → ${{ inputs.target_env }} (v${{ steps.source.outputs.tag }})"
          body: |
            ## Promotion Request

            | Field | Value |
            |-------|-------|
            | Service | `${{ inputs.service }}` |
            | Source | `${{ inputs.source_env }}` |
            | Target | `${{ inputs.target_env }}` |
            | Image tag | `${{ steps.source.outputs.tag }}` |

            **Action required:**
            - Verify staging tests pass before merging
            - For prod: SRE lead approval required
          branch: promote/${{ inputs.service }}/${{ inputs.source_env }}-to-${{ inputs.target_env }}
          base: main
          labels: |
            promotion
            ${{ inputs.service }}
          reviewers: |
            ${{ github.actor }}
            ${{ inputs.target_env == 'prod' && 'acme/sre-leads' || '' }}
```

---

### Step 6: Cài ArgoCD root-app

```bash
# Apply root-app (trước đó đã tạo trong platform-repo)
argocd login --username admin --password $(kubectl get secret argocd-initial-admin-secret \
  -n argocd -o jsonpath='{.data.password}' | base64 -d)

# Nếu chưa có platform-repo, apply trực tiếp:
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_USER/platform-repo.git
    targetRevision: main
    path: argocd/applications
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

# Verify
argocd app list
# EXPECTED OUTPUT:
# NAME                    CLUSTER                         NAMESPACE  PROJECT  STATUS  HEALTH
# root-platform            https://kubernetes.default.svc  argocd     default  Synced  Healthy
```

---

### Step 7: Thực hiện 1 promotion thực tế

```bash
# 1. Clone apps-repo
git clone https://github.com/YOUR_USER/apps-repo.git
cd apps-repo

# 2. Tạo feature branch
git checkout -b chore/api-service-bump-v0.2.0

# 3. Sửa dev overlay — mô phỏng image bump
sed -i 's/newTag: v0.1.0-dev/newTag: v0.2.0-dev/' \
  services/api-service/overlays/dev/kustomization.yaml

# 4. Commit + push + PR
git add services/api-service/overlays/dev/
git commit -m "chore(api-service): bump dev image to v0.2.0-dev"
git push -u origin chore/api-service-bump-v0.2.0

gh pr create --title "chore(api-service): bump to v0.2.0-dev" \
  --body "Image bump from CI build" \
  --base main

# 5. Merge PR (approve + merge trên GitHub UI hoặc gh)
gh pr merge --squash --auto

# 6. ArgoCD tự sync
sleep 10
argocd app get api-service-dev

# 7. Promotion: dev → staging
gh workflow run promote.yml \
  -f service=api-service \
  -f source_env=dev \
  -f target_env=staging

# 8. Verify PR được tạo
gh pr list --label promotion

# 9. Merge promotion PR
gh pr merge --squash --auto
```

---

### Step 8: Rollback bằng git revert

```bash
# 1. Xem lịch sử production overlay
git log --oneline services/api-service/overlays/prod/

# OUTPUT ví dụ:
# abc1234f (HEAD -> main) promote(api-service): staging → prod (v0.2.0)
# 9f8e7d6c infra: update node type
# 1a2b3c4d promote(api-service): dev → staging (v0.2.0)
# ...

# 2. Rollback bằng git revert
git revert abc1234f --no-edit
git push

# 3. GitHub tạo revert PR tự động
gh pr list --label "automerge"

# 4. Merge revert PR
gh pr merge --squash --auto

# 5. Verify ArgoCD sync
argocd app get api-service-prod
# Expected: OutOfSync → Syncing → Synced (về v0.1.9)
```

**So sánh với argocd app rollback:**

```bash
# NGUY HIỂM trên prod: chỉ rollback cluster, không rollback Git
argocd app rollback api-service-prod

# Hệ quả:
# - Cluster: về version trước ✓
# - Git: vẫn ở bad version ✗
# - ArgoCD next sync: lại đưa cluster về bad version
```

---

### Step 9: Cleanup

```bash
# Xóa ArgoCD apps đã tạo trong lab
argocd app delete root-platform --cascade
argocd app delete api-service-dev --cascade
argocd app delete api-service-staging --cascade
argocd app delete api-service-prod --cascade

# Hoặc giữ lại nếu muốn dùng cho Day 21
# Skeleton repo tiếp tục được dùng trong Capstone Day 28-35

# Verify cleanup
argocd app list
# EXPECTED: (empty hoặc chỉ có system apps)
```

**Troubleshooting thường gặp:**

| Vấn đề | Nguyên nhân | Fix |
|--------|-------------|-----|
| ArgoCD không thấy file mới | `directory.recurse: true` missing | Thêm vào root-app spec |
| ArgoCD ứng dụng không hiển thị | Application kind = directory thay vì Application | Kiểm tra kind trong YAML |
| CODEOWNERS không enforce | Branch protection chưa require CODEOWNERS review | Bật trong GitHub → Settings → Branches |
| Image bump PR tạo vào main | Workflow checkout sai ref | `with: ref: ${{ github.ref }}` |
| ArgoCD vẫn OutOfSync sau merge | GitHub webhook chưa gửi | Verify webhook trong ArgoCD UI |
| Promotion PR conflict | Concurrent promotion | Rebase trước merge |

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Khi nào chọn monorepo? Khi nào polyrepo?

> **Trả lời:** Monorepo phù hợp khi team nhỏ (< 10 người), cần atomic change, và muốn tooling đơn giản. Polyrepo phù hợp khi team lớn hơn (15+), cần ownership rõ ràng, compliance nghiêm ngặt, hoặc CI/CD độc lập. Team 10-30 người thường dùng hybrid.

**Câu 2:** Tại sao per-env branch không còn là best practice?

> **Trả lời:** Per-env branch (dev/staging/main) gây cherry-pick conflict khi promotion, khó audit (dùng tag thay vì PR), và phức tạp khi mở rộng multi-cluster. Per-env folder + trunk-based giữ mọi thứ trong 1 branch, promotion = PR, rollback = revert.

**Câu 3:** Team có 1 repo lẫn lộn infra/platform/apps — thiết kế kế hoạch tách trong 1 sprint (2 tuần) không downtime.

> **Trả lời:**
> - Tuần 1: Tạo 3 repo mới (infra/platform/apps), migrate folder từng cái (infra trước, ít rủi ro nhất), setup CI riêng, test trên dev
> - Tuần 2: Switch ArgoCD Applications point sang repo mới (env-by-env: dev → staging → prod), verify mỗi stage, keep old repo read-only trong 1 tháng để rollback nếu cần
> - Key: ArgoCD Applications vẫn chỉ vào Git, chỉ đổi repo URL → không downtime

**Câu 4:** Promotion từ staging → prod: nên dùng `argocd app sync` hay PR? Tại sao?

> **Trả lời:** Luôn dùng PR. `argocd app sync` chỉ thay đổi cluster, không thay đổi Git → drift: cluster ≠ Git → ArgoCD next sync sẽ đưa cluster về version xấu. PR = Git thay đổi → ArgoCD tự sync → source of truth = Git. Rollback bằng `git revert` → Git + cluster cùng về version trước.

**Câu 5:** ArgoCD không pick up image mới dù bot đã PR + merge. Kiểm tra gì?

> **Debug checklist:**
> 1. ArgoCD Application `spec.source.path` có đúng point vào overlay folder?
> 2. `targetRevision` = `main` hay specific commit SHA? (dùng `main`)
> 3. Git webhook có gửi event về ArgoCD? (Settings → Webhooks)
> 4. ArgoCD repo credentials còn valid? (Robot account không bị expire)
> 5. Image tag trong `kustomization.yaml` có đúng format `newTag:` không?
> 6. ArgoCD sync policy có `automated` không? (nếu manual → phải click Sync)
> 7. `argocd app get <app> --watch` để xem real-time sync status
> 8. `argocd app revision history <app>` để xem Git revisions đã sync

---

## 7. Tóm tắt cuối ngày

### Điều đã học

**Repository Architecture:**
- 3-repo polyrepo (infra/platform/apps) là default cho production GitOps team
- Mỗi repo có 1 owner team và 1 concern rõ ràng
- infra-repo provisions cluster, platform-repo sync cluster addons, apps-repo sync microservices

**Environment Strategy:**
- Per-env folder (overlay/{dev,staging,prod}/) + trunk-based (1 branch `main`)
- KHÔNG dùng per-env branch (lỗi thời, gây cherry-pick conflict)
- ArgoCD Application `path` trỏ vào overlay folder cụ thể

**Promotion:**
- Promotion = thay đổi image tag trong Git qua Pull Request
- ArgoCD Image Updater hoặc Renovate tự động tạo promotion PR
- Review requirement tăng dần: dev (auto) → staging (1-eye) → prod (4-eye)
- KHÔNG BAO GIỜ dùng `argocd app sync` làm promotion

**Rollback:**
- `git revert <sha>` tạo commit mới revert bad commit
- ArgoCD detect Git change → tự sync về version trước
- Git + cluster luôn đồng bộ → single source of truth
- `argocd app rollback` chỉ dùng cho dev/staging, không dùng trên prod

**Compliance Baseline:**
- CODEOWNERS + branch protection = minimum viable compliance
- Repo-level RBAC tốt hơn path-based CODEOWNERS
- Machine user với deploy key thay vì personal PAT
- No admin bypass trên protected branches

### Output của ngày hôm nay

```
day-20/
├── infra-repo/           # Terraform skeleton
│   ├── modules/network/
│   ├── live/dev/
│   ├── .github/workflows/terraform-fmt.yml
│   ├── .github/workflows/terraform-plan.yml
│   ├── CODEOWNERS
│   └── README.md
├── platform-repo/        # Cluster addons skeleton
│   ├── argocd/bootstrap/root-app.yaml
│   ├── argocd/projects/platform-project.yaml
│   ├── argocd/applications/ingress-nginx.yaml
│   ├── platform-services/ingress-nginx/values.yaml
│   ├── CODEOWNERS
│   └── README.md
└── apps-repo/            # App GitOps skeleton
    ├── services/api-service/
    │   ├── base/{deployment,service,kustomization}.yaml
    │   └── overlays/{dev,staging,prod}/
    ├── argocd/projects/api-team-project.yaml
    ├── argocd/applications/api-service-prod.yaml
    ├── .github/workflows/image-bump.yml
    ├── .github/workflows/promote.yml
    ├── CODEOWNERS
    └── README.md
```

### Chuẩn bị cho Day 21

Day 21 sẽ học **App-of-Apps Pattern** — cách dùng 1 ArgoCD Application quản lý tất cả applications khác. Skeleton platform-repo (`argocd/bootstrap/root-app.yaml`) đã tạo sẵn là entry point cho pattern đó.

---

## 8. Tham khảo thêm

### Tài liệu chính thức

- [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
- [ArgoCD Declarative Setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [GitHub CODEOWNERS documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [GitHub Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

### Tooling

- [Renovate — Automated Dependency Updates](https://docs.renovatebot.com/)
- [ArgoCD Image Updater](https://argocd-image-updater.readthedocs.io/)
- [Kustomize — Kubernetes native config management](https://kubectl.docs.kubernetes.io/)
- [Turborepo — Monorepo build system](https://turbo.build/)

### Blogs & Case Studies

- [GitOps Repository Models — Codefresh](https://codefresh.io/docs/gitops-repos/)
- [Trunk-based Development — Atlassian](https://www.atlassian.com/continuous-delivery/continuous-deployment/trunk-based-development)
- [Monorepo vs Polyrepo — increment article](https://increment.com/software-architecture/one-or-many-repositories/)

### Security

- [OPA / Gatekeeper — Policy as Code](https://www.openpolicyagent.org/)
- [GitOps and Security — Weaveworks](https://www.weave.works/technologies/gitops/)
- [Sigstore — Keyless signing](https://sigstore.dev/)
