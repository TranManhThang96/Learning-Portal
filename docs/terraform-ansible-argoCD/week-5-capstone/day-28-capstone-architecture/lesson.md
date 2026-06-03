# Day 28 — Capstone Architecture, Repo Strategy, Cost Strategy

> **Capstone Production-Grade Phase — Mở đầu 8 ngày cuối**
> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Hoàn thành Day 1-27 (Terraform + Ansible + ArgoCD)
> **Output:** 3 repo skeleton + architecture diagram + ADR-0001 + cost estimate + security baseline + Makefile

---

## 1. Mục tiêu ngày học

- Thiết kế kiến trúc tổng thể cho hệ 3 microservice (api-service, worker-service, frontend-service) với data layer (PostgreSQL + Redis) và platform layer (ArgoCD + observability + CI/CD)
- Phân tách 3 repo (infra-repo / platform-repo / apps-repo) theo ownership boundary và blast radius, build trên nền tảng Day 20
- So sánh Mode A (Local/kind + free) vs Mode B (AWS/EKS + ~$X/tháng) — chọn default và explain khi nào switch
- Ước tính chi phí Mode B (NAT Gateway, EKS control plane, RDS, ElastiCache, ALB), trình bày cách giảm cost
- Viết ADR (Architecture Decision Record) đầu tiên cho platform — format chuẩn Markdown
- Setup security baseline checklist (IRSA, OIDC, least-privilege IAM, private RDS, ESO)
- Tạo Makefile shortcut cho các thao tác common (local-up, aws-plan, aws-destroy)

---

## 2. Bối cảnh thực tế

### Chuyện thật mà ai cũng gặp

Sau 27 ngày học từ Terraform cơ bản, Ansible playbook, đến ArgoCD GitOps nâng cao, học viên có đầy đủ "lego blocks" nhưng chưa bao giờ lắp chúng lại thành 1 platform hoàn chỉnh. 3 vấn đề thường gặp khi bắt đầu capstone:

**1. Không có blueprint trước — architecture by accident**

Team bắt đầu code ngay, rồi phát hiện:
- Terraform state quản cả cluster VÀ database trong 1 state file → apply sai → production down
- ArgoCD dùng chung 1 Application cho infra + app → app team trigger terraform plan 50 lần/ngày
- Không estimate cost trước → bill $800/tháng cho dev environment

**2. Không quyết định cost strategy từ đầu**

| Sai | Đúng |
|-----|------|
| Tạo EKS multi-AZ ngay từ đầu cho dev | Dev = kind/Spot, prod = EKS On-Demand |
| Dùng RDS Multi-AZ dev environment | Dev = Helm bitnami/postgresql local |
| NAT Gateway cho dev (không cần) | VPC Endpoint thay thế NAT cho internal traffic |

**3. Security baseline thiếu từ day 1**

```
Khởi tạo EKS
  → Dùng instance profile thay vì IRSA (long-lived credentials)
  → Tất cả pod có quyền full AWS account
  → Dev push AWS_ACCESS_KEY vào GitHub (public repo)
  → 48 giờ sau: $3,000 crypto mining bill
```

**Capstone ngày hôm nay:** Giải quyết cả 3 vấn đề trước khi viết dòng code nào cho Day 29-35. Không có architecture diagram, không có ADR, không có cost estimate — không bắt đầu Day 29.

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Capstone target: 3 microservices stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPSTONE STACK OVERVIEW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ api-service  │  │worker-service│  │frontend-svc  │          │
│  │  (Go/Node)   │  │  (Python)    │  │  (React)     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                     │
│                   ┌────────▼────────┐                           │
│                   │  Redis / Cache  │                           │
│                   │(ElastiCache/Local)│                         │
│                   └────────┬────────┘                           │
│                            │                                     │
│                   ┌────────▼────────┐                           │
│                   │ PostgreSQL     │                           │
│                   │ (RDS/Local)    │                           │
│                   └────────────────┘                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               GitOps Layer (ArgoCD)                     │   │
│  │   ApplicationSet → 3 services × 3 envs (dev/stg/prd)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            CI/CD Layer (GitHub Actions)                │   │
│  │   lint → test → build → scan → push → PR image-bump   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Observability (Prometheus/Grafana)           │   │
│  │   metrics + logs + alerts + dashboards                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Service responsibilities:**

| Service | Port | Role | External endpoint? |
|---------|------|------|--------------------|
| `api-service` | 8080 | REST API, business logic | Yes (via Ingress/ALB) |
| `worker-service` | 8081 | Background job queue consumer | No |
| `frontend-service` | 3000 | React SPA, proxies to api-service | Yes (via Ingress/ALB) |
| PostgreSQL | 5432 | Primary data store | No |
| Redis | 6379 | Session cache, job queue | No |

---

### 3.2 Mode A — Local/Low-cost ASCII diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    MODE A: LOCAL / KIND + FREE STACK                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        DEVELOPER MACHINE                          │  │
│  │                                                                  │  │
│  │   kind cluster (kubernetes.io/kind)                               │  │
│  │   ┌─────────────────────────────────────────────────────────┐   │  │
│  │   │  NAMESPACE: argocd                                       │   │  │
│  │   │    ArgoCD Server + Repo Server + Application Controller  │   │  │
│  │   ├─────────────────────────────────────────────────────────┤   │  │
│  │   │  NAMESPACE: ingress-nginx                                │   │  │
│  │   │    ingress-nginx-controller (NodePort 80/443)           │   │  │
│  │   ├─────────────────────────────────────────────────────────┤   │  │
│  │   │  NAMESPACE: cert-manager                                 │   │  │
│  │   │    cert-manager + ClusterIssuer (self-signed)           │   │  │
│  │   ├─────────────────────────────────────────────────────────┤   │  │
│  │   │  NAMESPACE: external-secrets                             │   │  │
│  │   │    ESO + LocalSecretStore (demo)                         │   │  │
│  │   ├─────────────────────────────────────────────────────────┤   │  │
│  │   │  NAMESPACE: monitoring                                  │   │  │
│  │   │    kube-prometheus-stack (Prometheus/Grafana)           │   │  │
│  │   ├─────────────────────────────────────────────────────────┤   │  │
│  │   │  NAMESPACE: api-service-prod                            │   │  │
│  │   │  NAMESPACE: worker-service-prod                         │   │  │
│  │   │  NAMESPACE: frontend-service-prod                       │   │  │
│  │   │    Deployment + Service + HPA + ConfigMap                │   │  │
│  │   └─────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Docker Compose (local, NOT inside kind)                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │  │
│  │  │ PostgreSQL   │  │    Redis     │  │ LocalStack (optional)  │  │  │
│  │  │  port 5432   │  │   port 6379  │  │  mock AWS S3/SQS/etc  │  │  │
│  │  └──────────────┘  └──────────────┘  └───────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  GitHub Container Registry (ghcr.io)                            │  │
│  │  Images: ghcr.io/<user>/api-service, worker, frontend           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  COST: $0/month (Docker Desktop license if needed, excluded)           │
│  SUITABLE FOR: learner, solo dev, team < 5 without budget            │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 Mode B — AWS Production-like ASCII diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    MODE B: AWS / EKS + PRODUCTION STACK                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         AWS REGION (eu-west-1 / us-east-1)          │ │
│  │                                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │                         VPC (10.0.0.0/16)                    │  │ │
│  │  │                                                              │  │ │
│  │  │  ┌─ PUBLIC SUBNETS (10.0.0.0/24, 10.0.1.0/24) ─────────────┐ │  │ │
│  │  │  │  NAT Gateway ($$)  │  Application Load Balancer (ALB)  │ │  │ │
│  │  │  │  EKS API endpoint  │  VPC Endpoint (S3, ECR, Secrets)  │ │  │ │
│  │  │  └──────────────────────────────────────────────────────┘ │  │ │
│  │  │                                                              │  │ │
│  │  │  ┌─ PRIVATE SUBNETS (10.0.16.0/24, 10.0.17.0/24) ──────────┐│  │ │
│  │  │  │  EKS Managed Node Group (t3.medium × 2, Spot 30%)      ││  │ │
│  │  │  │    ┌──────────────────────────────────────────────────┐ ││  │ │
│  │  │  │    │  PODS: api-service, worker, frontend            │ ││  │ │
│  │  │  │    │  PODS: ingress-nginx, cert-manager, ESO        │ ││  │ │
│  │  │  │    │  PODS: kube-prometheus-stack                    │ ││  │ │
│  │  │  │    │  IRSA: each SA → IAM role (no long-lived keys)  │ ││  │ │
│  │  │  │    └──────────────────────────────────────────────────┘ ││  │ │
│  │  │  └─────────────────────────────────────────────────────────┘│  │ │
│  │  │                                                              │  │ │
│  │  │  ┌─ PRIVATE SUBNETS DB (10.0.32.0/24, 10.0.33.0/24) ──────┐│  │ │
│  │  │  │  RDS PostgreSQL (db.t3.medium, Multi-AZ)               ││  │ │
│  │  │  │  ElastiCache Redis (cache.t3.medium, cluster mode)    ││  │ │
│  │  │  └────────────────────────────────────────────────────────┘│  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │     ECR      │  │  Route 53    │  │     ACM      │  │ Secrets Mgr │ │
│  │ Image registry│  │  DNS zones   │  │   TLS cert   │  │  ESO pull  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  GitHub Actions (external, NOT in AWS)                           │  │
│  │  OIDC: GitHub → AWS IAM (no long-lived AWS credentials)          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  COST: ~$180-350/month (see cost-estimate.md)                           │
│  SUITABLE FOR: production simulation, team with AWS budget               │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 3.4 Layered architecture (cả 2 mode dùng chung concept)

```
LAYER 1 ── NETWORK
  Local:  kind network (no NAT needed)
  AWS:    VPC / public-private subnets / route tables / security groups

LAYER 2 ── CLUSTER + IAM
  Local:  kind cluster (single node, docker driver)
  AWS:    EKS control plane + managed node group + IRSA

LAYER 3 ── DATA LAYER
  Local:  Docker Compose: PostgreSQL + Redis
  AWS:    RDS PostgreSQL (Multi-AZ) + ElastiCache Redis

LAYER 4 ── PLATFORM BOOTSTRAP
  Local:  ArgoCD + Ingress + Cert-Manager (self-signed) + ESO (local) + Prometheus
  AWS:    ArgoCD + AWS LB Controller + Cert-Manager (ACM) + ESO (ASM) + Prometheus

LAYER 5 ── APPS
  Local:  api-service + worker-service + frontend-service (Kustomize overlays)
  AWS:    Same, but image from ECR, secrets from ASM
```

---

### 3.5 3-repo strategy (build trên Day 20)

```
┌─────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY DIRECTION                        │
│                                                                 │
│  infra-repo  (Terraform)                                         │
│    provisions: VPC, EKS/kind, RDS, ElastiCache                  │
│    owned by: SRE/DevOps                                         │
│    │                                                           │
│    │ provisions cluster                                         │
│    ▼                                                           │
│  platform-repo  (Helm values + ArgoCD Applications)              │
│    manages: ingress-nginx, cert-manager, ESO, prometheus        │
│    owned by: Platform team                                      │
│    │                                                           │
│    │ sync cluster addons                                        │
│    ▼                                                           │
│  apps-repo  (Kubernetes manifests + Kustomize)                   │
│    manages: api-service, worker-service, frontend-service        │
│    owned by: App teams                                         │
│    │                                                           │
│    │ sync workloads                                             │
│    ▼                                                           │
│  [RUNNING CLUSTER]                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc quan trọng:**
- infra-repo KHÔNG bao giờ reference platform-repo hoặc apps-repo
- platform-repo và apps-repo KHÔNG tạo infrastructure (không gọi Terraform provider)
- Destroy order: apps → platform → infra (reverse of creation)
- **Day 28 chỉ tạo skeleton — chưa deploy gì cả**

---

### 3.6 Environment strategy

| Environment | ArgoCD Sync | Review | Promotion | Use case |
|-------------|-------------|--------|-----------|----------|
| `dev` | Auto-sync | None (author only) | Auto-merge on commit | Active development |
| `staging` | Auto-sync | 1 team member PR | PR review required | Pre-production validation |
| `prod-like` | Manual sync | 2 approvals + SRE lead | Manual approval + SRE 4-eye | Production simulation |

**Note:** Trong Capstone, "production-like" không phải production thật — là môi trường gần production nhất có thể dùng để test promotion flow. Tùy mode (A/B), environment này có thể là 1 kind cluster khác hoặc 1 EKS namespace riêng.

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 Cost strategy chi tiết

#### Mode A (Local)

| Component | Cost | Notes |
|-----------|------|-------|
| kind cluster | $0 | Kubernetes in Docker |
| PostgreSQL (Helm bitnami) | $0 | Runs as Deployment in kind |
| Redis (Helm bitnami) | $0 | Runs as Deployment in kind |
| GitHub Container Registry | $0 | Free for public repos |
| ArgoCD | $0 | OSS, runs in cluster |
| Prometheus/Grafana | $0 | kube-prometheus-stack Helm |
| **Total** | **$0** | Excludes Docker Desktop license |

**Hạn chế Mode A:**
- Không mô phỏng được AWS IAM (IRSA), RDS Multi-AZ, ElastiCache cluster mode
- Không test được VPC endpoint, ALB Controller, ACM
- Không có DR scenario thực sự (backup/restore PostgreSQL phải làm manual)

#### Mode B (AWS) — Cost estimate tháng 5/2026, eu-west-1

> Disclaimer: Ước tính, có thể thay đổi. Không bao gồm data transfer, CloudWatch, ECR storage.

| Service | Instance/Config | Cost/tháng | Notes |
|---------|----------------|------------|-------|
| EKS Control Plane | 1 cluster | $73.00 | Flat rate per cluster |
| EC2 Managed Node Group | t3.medium × 2 (On-Demand) | ~$45.00 | $0.0416/hr × 2 × 730h |
| EC2 Spot Node Group | t3.medium × 1 (30% mix) | ~$10.00 | ~70% savings vs OD |
| RDS PostgreSQL | db.t3.medium Multi-AZ | ~$70.00 | Multi-AZ = 2× single-AZ |
| RDS PostgreSQL Single-AZ (dev) | db.t3.small | ~$25.00 | Alternative cho dev |
| ElastiCache Redis | cache.t3.medium | ~$25.00 | Single-AZ; Multi-AZ ~$50 |
| NAT Gateway | 1 × AZ | ~$32.50 | $0.045/GB + $0.045/hr |
| Application Load Balancer | 1 × ALB | ~$16.50 | $0.0225/LCU + $16.50/mo |
| VPC Endpoint (S3) | 1 | $0.00 | Free |
| ECR storage | ~5 GB | ~$0.45 | $0.10/GB/month |
| ACM certificate | 1 | $0.00 | Free public certificates |
| Route 53 hosted zone | 1 | $0.50 | $0.50/hosted zone/month |
| Secrets Manager | 5 secrets | ~$1.35 | $0.40/secret/month |
| CloudWatch metrics | ~100 metrics | ~$3.00 | $0.30/metric/month |
| **Total (with Multi-AZ RDS)** | | **~$277/month** | Full production sim |
| **Total (Single-AZ, Spot mix)** | | **~$180/month** | Cost-optimized dev/staging |

**Cách giảm Mode B cost:**

```
Strategy 1: Thay NAT Gateway bằng VPC Endpoint
  Before: NAT Gateway ($32.50/mo) + Egress Internet
  After:  VPC Endpoint for S3/ECR ($0) + NAT Gateway chỉ cho worker node
  Saving: ~$25/mo

Strategy 2: Single-AZ cho non-prod
  RDS Multi-AZ → Single-AZ (dev/staging)
  Saving: ~$45/mo cho mỗi non-prod env

Strategy 3: Spot instance cho non-prod
  On-Demand t3.medium × 2 → Spot t3.medium × 1 (30% mix)
  Saving: ~$35/mo cho dev cluster

Strategy 4: t3.small cho dev environment
  t3.medium → t3.small (dev/staging only)
  Saving: ~$20/mo
```

---

### 4.2 Security baseline

**Nguyên tắc 1: IRSA thay long-lived credentials**

```hcl
# Sai: Pod dùng AWS access key trong env var
env:
  - name: AWS_ACCESS_KEY_ID
    value: "AKIAIOSFODNN7EXAMPLE"

# Đúng: Pod dùng IRSA (IAM Role gắn với ServiceAccount)
# EKS cluster có OIDC provider → Kubernetes ServiceAccount
# → mapped to IAM role (no manual credential rotation needed)
```

**Nguyên tắc 2: OIDC cho GitHub Actions (thay PAT long-lived)**

```yaml
# GitHub Actions: OIDC trust → temporary AWS credentials
# Không cần AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY trong secrets
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/GitHubActionsRole
    aws-region: eu-west-1
    audience: sts.amazonaws.com
```

**Nguyên tắc 3: RDS private subnet, không public internet**

```hcl
# RDS chỉ accessible từ EKS node qua security group
# Không có PubliclyAccessible = true
resource "aws_db_subnet_group" "main" {
  name       = "main"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}
```

**Nguyên tắc 4: ESO + External Secrets, không hardcode**

```yaml
# Kubernetes Secret: referenced as ExternalSecret
# Actual value: stored in AWS Secrets Manager
# Pod: chỉ thấy K8s Secret, không thấy ASM
apiVersion: external-secrets.io/v1
kind: ExternalSecret
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-service-secrets
  data:
    - secretKey: database-url
      remoteRef:
        key: prod/api-service/database
        property: url
```

---

### 4.3 Repo strategy: 3-repo vs monorepo cho Capstone

| Tiêu chí | Polyrepo 3 (default) | Monorepo |
|----------|---------------------|----------|
| Capstone learner (solo) | Phức tạp, cần quản 3 remote repo | Đơn giản hơn |
| Team 2-3 dev Capstone | Không cần thiết, overkill | OK |
| Simulate production | Polyrepo = production-grade | Monorepo = học được, không thực |
| Blast radius | Tách biệt: infra change không trigger app CI | 1 CI cho tất cả |
| Skill build | Polyrepo = đúng practice thực tế | Học cách nào cũng được |

**Capstone recommendation:**
- Học viên solo: dùng **3 folder** trong cùng 1 local repo (mô phỏng 3 repo), sau đó convert thành 3 remote repo nếu muốn
- Team Capstone: dùng **3 remote repo thật** (polyrepo production-grade)
- Giáo viên/demo: **hybrid** — 1 monorepo local cho nhanh, nhưng viết code tưởng tượng mình đang trong polyrepo

---

### 4.4 ADR — Architecture Decision Record

**ADR là gì?**

ADR là document ghi lại các architectural decision quan trọng, bao gồm:
- Tại sao ta quyết định theo hướng X thay vì Y
- Ai tham gia quyết định
- Hệ quả (tích cực và tiêu cực)

```
docs/adr/
├── 0001-mode-a-vs-b.md       ← Viết trong lab hôm nay
├── 0002-repo-split.md         ← Viết trong lab hôm nay
├── 0003-secrets-strategy.md   ← Viết trước Day 31
├── 0004-promotion-flow.md     ← Viết trước Day 33
└── 0005-disaster-recovery.md ← Viết trước Day 35
```

**ADR template chuẩn:**

```markdown
# ADR-XXXX: <Title>

## Status
Proposed | Accepted | Deprecated | Superseded

## Context
[Vấn đề cần giải quyết, ràng buộc, stakeholder]

## Decision
[Quyết định cụ thể ta đã chọn]

## Consequences

### Positive
- ...

### Negative
- ...

### Neutral
- ...
```

---

### 4.5 Capstone pitfalls — những lỗi hay gặp

| # | Pitfall | Hệ quả | Prevention |
|---|---------|--------|------------|
| 1 | Scope creep: muốn deploy 10 service thay vì 3 | Không kịp hoàn thành trong 8 ngày | Stick to 3 services specified in plan |
| 2 | Không cleanup AWS resources | Bill $200+ sau capstone | Chạy `make aws-destroy` ngay sau lab |
| 3 | Hardcode account ID / region | Không portable qua account khác | Dùng biến, không hardcode |
| 4 | Mix infra concerns trong apps-repo | App team có thể sửa Terraform | Repo boundary rõ ràng |
| 5 | Dùng `latest` tag | ArgoCD không detect image change | Immutable tag: `v1.2.3`, `sha-abc123` |
| 6 | Không backup Terraform state | State corruption = infrastructure loss | S3 backend + versioning |
| 7 | Dùng real credentials trong code | Secret leak | Chỉ dùng placeholder trong lab |
| 8 | Quên make destroy khi done | AWS resources chạy 24/7 | Makefile shortcut + cleanup reminder |

---

## 5. Hands-on Lab — 60 phút

**Thời gian:** 60 phút
**Mode:** Chọn A (Local) hoặc B (AWS) — lab hôm nay chỉ tạo skeleton + design docs, không tạo infrastructure

### Pre-requisites

```bash
# Kiểm tra pre-req trước khi bắt đầu
git --version        # Git required
gh --version         # Optional: GitHub CLI
docker --version     # Required for kind
kubectl version      # Required
kind version         # Optional (Mode A)
terraform --version  # Optional (Mode B)
aws --version        # Only if Mode B

# Nếu dùng GitHub: fork hoặc tạo 3 repo mới
gh auth login
gh repo create capstone-infra --public --clone
gh repo create capstone-platform --public --clone
gh repo create capstone-apps --public --clone
```

---

### Step 1: Tạo 3 repo skeleton (hoặc 3 folder)

```bash
# Option A: Clone GitHub repos
gh repo create <your-user>/capstone-infra --public --clone
gh repo create <your-user>/capstone-platform --public --clone
gh repo create <your-user>/capstone-apps --public --clone

cd capstone-infra

# Option B: Local folders (mô phỏng 3 repo)
mkdir -p capstone-infra capstone-platform capstone-apps
cd capstone-infra && git init
cd ../capstone-platform && git init
cd ../capstone-apps && git init
```

#### File: `capstone-infra/CODEOWNERS`

```
# SRE team owns all infrastructure
* @capstone/sre-team

# Production infrastructure: leads review
/live/prod/       @capstone/sre-leads
/live/staging/    @capstone/sre-team

# Dev: standard review
/live/dev/        @capstone/sre-team
```

#### File: `capstone-platform/CODEOWNERS`

```
# Platform team owns cluster addons
* @capstone/platform-team

# Security-sensitive paths
argocd/projects/  @capstone/platform-team @capstone/security
policies/         @capstone/platform-team @capstone/security

# Production ArgoCD applications
argocd/applications/prod-*.yaml  @capstone/platform-team @capstone/sre-leads
```

#### File: `capstone-apps/CODEOWNERS`

```
# App teams own their services
* @capstone/dev-leads

/services/api-service/           @capstone/api-team
/services/worker-service/        @capstone/worker-team
/services/frontend-service/      @capstone/frontend-team

# Production overlays: leads must approve
/services/*/overlays/prod/       @capstone/dev-leads @capstone/sre-leads
```

---

### Step 2: Tạo `docs/architecture.md` — architecture diagram + module breakdown

```bash
mkdir -p capstone-infra/docs/adr
mkdir -p capstone-platform/docs
mkdir -p capstone-apps/docs
```

**File: `capstone-infra/docs/architecture.md`** (copy diagram ASCII từ Section 3.2 hoặc 3.3 tùy mode)

```markdown
# Capstone Infrastructure Architecture

## Mode: [A: Local / B: AWS Production-like]

> Chọn 1 mode, comment out mode còn lại.

## Module Breakdown

### Mode A (Local)

| Module | Technology | Purpose |
|--------|------------|---------|
| `modules/kind-cluster` | kind + kubectl | Local Kubernetes cluster |
| `modules/postgres` | Helm bitnami/postgresql | PostgreSQL in-cluster |
| `modules/redis` | Helm bitnami/redis | Redis in-cluster |
| `modules/network` | kind network (no Terraform) | Network isolation |

### Mode B (AWS)

| Module | Technology | Purpose |
|--------|------------|---------|
| `modules/vpc` | AWS VPC | Network isolation |
| `modules/eks` | AWS EKS | Kubernetes control plane |
| `modules/rds` | AWS RDS PostgreSQL | Managed database |
| `modules/elasticache` | AWS ElastiCache Redis | Managed cache |
| `modules/irsa` | AWS IAM + OIDC | Pod-level IAM without keys |
| `modules/ecr` | AWS ECR | Container image registry |
| `modules/secrets` | AWS Secrets Manager | Secret storage for ESO |

## Environment Layout

```
live/
├── dev/          # Development (kind or t3.small single-AZ)
├── staging/      # Pre-production (kind or t3.medium single-AZ)
└── prod/         # Production simulation (EKS Multi-AZ or t3.medium × 2)
```

## Cost Summary

Xem: `docs/cost-estimate.md`
```

---

### Step 3: Viết ADR đầu tiên — `0001-mode-a-vs-b.md`

**File: `capstone-infra/docs/adr/0001-mode-a-vs-b.md`**

```markdown
# ADR-0001: Mode A (Local) là default cho Capstone

## Status
Accepted

## Context

Capstone (Day 28-35) cần hỗ trợ 2 loại learner:
1. Học viên không có AWS account / không muốn tốn tiền
2. Học viên muốn mô phỏng production thật với AWS services

Cần 1 architectural decision: nên default mode nào và khi nào switch.

## Decision

**Mode A (Local/kind + free stack) là default** cho Capstone.

Mode B (AWS/EKS) available như optional track.

### Lý do chọn Mode A:

1. **Barrier to entry thấp nhất** — không cần credit card, không cần AWS account
2. **Fast feedback loop** — tạo/destroy cluster trong 5 phút
3. **Learner tập trung vào GitOps** — không bị phân tâm bởi IAM policy debugging
4. **Week 5 vẫn cover AWS services** — trong phần platform bootstrap (Day 32) và observability (Day 34), học viên được giới thiệu AWS-specific components (IRSA, ALB Controller, ACM) dù ở Mode A

### Lý do giữ Mode B available:

1. **Production simulation** — team muốn thực hành AWS-native tooling
2. **Job interview preparation** — AWS EKS là yêu cầu phổ biến trong JD
3. **Cost optimization learning** — biết cách giảm $300 → $180/tháng

## Consequences

### Positive
- Mọi học viên đều có thể hoàn thành Capstone dù không có AWS
- Lab setup nhanh, không phụ thuộc external cloud provider
- Tập trung vào GitOps pattern (ArgoCD, Kustomize) thay vì AWS IAM policy

### Negative
- Học viên không trải nghiệm thực tế: IRSA, RDS Multi-AZ, ALB Controller, VPC endpoint
- Mode B phải được document chi tiết (cost estimate, cleanup) — tăng effort cho instructor

### Workaround cho Mode B gaps:
- Day 32 Platform Bootstrap: giới thiệu AWS-mode components qua code review
- Day 34 Observability: AWS CloudWatch metrics thay vì Prometheus (optional)
- Day 35 DR: simulate backup/restore bằng Velero plugin cho LocalStack
```

---

### Step 4: Viết `docs/cost-estimate.md` cho Mode B

**File: `capstone-infra/docs/cost-estimate.md`**

```markdown
# Cost Estimate — Mode B (AWS, eu-west-1)

> Disclaimer: Ước tính tháng 5/2026, eu-west-1. Giá có thể thay đổi.
> Always verify tại https://calculator.aws.amazon.com/

## Monthly Cost Summary

| Service | Configuration | Cost/tháng |
|---------|--------------|------------|
| EKS Control Plane | 1 cluster | $73.00 |
| EC2 Node Group (On-Demand) | t3.medium × 2 | $45.00 |
| EC2 Spot (30% mix) | t3.medium × 1 | $10.00 |
| RDS PostgreSQL Multi-AZ | db.t3.medium | $70.00 |
| ElastiCache Redis | cache.t3.medium | $25.00 |
| NAT Gateway | 1 × AZ | $32.50 |
| Application Load Balancer | 1 ALB | $16.50 |
| Secrets Manager | 5 secrets | $1.35 |
| Route 53 | 1 hosted zone | $0.50 |
| ECR storage | ~5 GB | $0.45 |
| CloudWatch | ~100 metrics | $3.00 |
| **Total (full)** | | **~$277/month** |

## Cost-Optimized Version (< $180/tháng)

| Change | Monthly Saving |
|--------|---------------|
| NAT Gateway → VPC Endpoint for S3/ECR | ~$25.00 |
| RDS Multi-AZ → Single-AZ (dev/staging) | ~$45.00 |
| On-Demand t3.medium → Spot 30% mix | ~$35.00 |
| t3.medium → t3.small (dev only) | ~$20.00 |
| **Total saving** | **~$125/month** |

## Cleanup Commands

```bash
# IMPORTANT: Chạy sau mỗi lab session

# Destroy all Terraform-managed resources
make aws-destroy

# Verify no resources left
aws ec2 describe-vpcs --region eu-west-1
aws rds describe-db-instances --region eu-west-1
aws eks list-clusters --region eu-west-1

# Manual cleanup (nếu Terraform state lost)
# Xóa ECR images
aws ecr list-images --repository-name capstone/api-service --region eu-west-1
aws ecr batch-delete-image \
  --repository-name capstone/api-service \
  --image-ids imageTag=v1.0.0 \
  --region eu-west-1

# Xóa S3 buckets (Terraform state backup)
aws s3 ls | grep capstone
aws s3 rb s3://capstone-tf-state --force

# Xóa CloudWatch logs
aws logs describe-log-groups --log-group-name-prefix /ecs/capstone

# Xóa Route53 hosted zone (nếu tạo mới)
aws route53 list-hosted-zones | grep capstone
aws route53 delete-hosted-zone --id ZXXXXXXXX
```

## Budget Alert Setup

```bash
# Tạo AWS Budget alert (Terraform)
resource "aws_budgets_budget" "monthly" {
  name         = "capstone-monthly"
  budget_type  = "COST"
  limit_amount = "200"
  limit_unit   = "USD"
  time_period_end = "2087-06-15_00:00"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator = "GREATER_THAN"
    threshold           = 80
    threshold_type      = "PERCENTAGE"
    notification_type   = "FORECASTED"
    subscriber_email_addresses = ["thangtm@example.com"]
  }
}
```
```

---

### Step 5: Viết `docs/security-baseline.md`

**File: `capstone-infra/docs/security-baseline.md`**

```markdown
# Security Baseline Checklist

## MUST (bắt buộc — không có exception)

### IAM & Credentials
- [ ] Sử dụng IRSA cho tất cả pod cần AWS access (thay vì access key trong env)
- [ ] EKS cluster có OIDC provider được configure (eksctl irsa setup hoặc Terraform)
- [ ] GitHub Actions dùng OIDC thay vì long-lived AWS credentials
- [ ] KHÔNG có AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY trong GitHub secrets (dùng IRSA/OIDC)
- [ ] IAM role có least-privilege: chỉ grant permission cần thiết, không `*:*`

### Secrets
- [ ] Không hardcode secret trong manifest, CI script, hoặc documentation
- [ ] Dùng ESO (External Secrets Operator) + AWS Secrets Manager (Mode B) hoặc ESO local provider (Mode A)
- [ ] Kubernetes Secret không commit vào Git (dùng ExternalSecret thay thế)
- [ ] Database password được generate tự động, không dùng default password

### Network
- [ ] RDS/ElastiCache trong private subnet, không có public IP
- [ ] Security group chỉ allow port cần thiết (PostgreSQL: 5432 từ EKS nodes)
- [ ] EKS API endpoint: private endpoint enabled, public endpoint disabled hoặc restricted
- [ ] ALB/Ingress chỉ expose app port ra internet (80/443), không expose database port

### Container Image
- [ ] Image tag là immutable (v1.2.3 hoặc digest, KHÔNG dùng `latest`)
- [ ] Image scanned trước khi push (Trivy, Grype)
- [ ] KHÔNG dùng image từ untrusted registry

### Terraform
- [ ] Terraform state lưu trong S3 với versioning enabled (không local state)
- [ ] S3 bucket có versioning, encryption (SSE-S3 hoặc SSE-KMS)
- [ ] Dữ liệu sensitive (password, key) không nằm trong state output (dùng `sensitive = true`)

## SHOULD (nên làm)

- [ ] ArgoCD admin password được rotate định kỳ (hoặc dùng SSO từ đầu)
- [ ] RBAC ArgoCD: không dùng role `admin` cho người dùng thường
- [ ] EKS node group có `enable_spot_termination_handler` nếu dùng Spot
- [ ] Kubernetes network policy để hạn chế pod-to-pod traffic
- [ ] Container resource requests/limits để tránh noisy-neighbor

## NICE-TO-HAVE

- [ ] Signed commits (GPG/Sigstore) cho production merges
- [ ] OPA/Gatekeeper policy để enforce: no privileged container, no hostPID
- [ ] Vault cho centralized secret management (thay vì ASM trực tiếp)
- [ ] AWS Security Hub / GuardDuty enable cho production
- [ ] VPC Flow Logs để audit network traffic
```

---

### Step 6: Tạo `Makefile` shortcuts

**File: `capstone-infra/Makefile`**

```makefile
# =====================================================================
# Capstone Infrastructure Makefile
# =====================================================================

.PHONY: help local-up local-down local-status aws-plan aws-apply aws-destroy

AWS_REGION := eu-west-1
TF_STATE_BUCKET := capstone-tf-state-$(shell date +%Y%m%d)

# ─── Mode A: Local kind ────────────────────────────────────────────

local-up:
	@echo "==> Creating kind cluster"
	kind get clusters | grep -q capstone && \
	  echo "Cluster already exists" || \
	  kind create cluster --name capstone
	@echo "==> Cluster created"
	kubectl get nodes

local-down:
	@echo "==> Deleting kind cluster"
	kind delete cluster --name capstone
	@echo "==> Cluster deleted"

local-status:
	kind get clusters
	kubectl get nodes
	@echo "==> ArgoCD status"
	@kubectl get pods -n argocd 2>/dev/null || \
	  echo "ArgoCD not installed. Run Day 32 bootstrap."

# ─── Mode B: AWS Terraform ─────────────────────────────────────────

aws-init:
	@echo "==> Initializing Terraform"
	cd live/dev && terraform init \
	  -backend-config="bucket=$(TF_STATE_BUCKET)" \
	  -backend-config="key=dev/terraform.tfstate" \
	  -backend-config="region=$(AWS_REGION)"
	cd live/staging && terraform init \
	  -backend-config="bucket=$(TF_STATE_BUCKET)" \
	  -backend-config="key=staging/terraform.tfstate" \
	  -backend-config="region=$(AWS_REGION)"

aws-plan:
	@echo "==> Running terraform plan for dev"
	cd live/dev && terraform plan -var="region=$(AWS_REGION)"
	@echo "==> Running terraform plan for staging"
	cd live/staging && terraform plan -var="region=$(AWS_REGION)"

aws-apply:
	@echo "==> Applying dev infrastructure"
	cd live/dev && terraform apply -var="region=$(AWS_REGION)" -auto-approve
	@echo "==> Dev infrastructure ready"
	@echo "NOTE: Apply staging/prod manually after review"

aws-destroy:
	@echo "==> DESTROYING all AWS resources (dev first)"
	cd live/dev && terraform destroy -var="region=$(AWS_REGION)" -auto-approve
	@echo "==> Dev resources destroyed"
	@echo "==> IMPORTANT: Manually destroy staging/prod:"
	@echo "   cd live/staging && terraform destroy"

aws-cost:
	@echo "Opening AWS Pricing Calculator..."
	@echo "https://calculator.aws.amazon.com/"
	@echo ""
	@echo "Quick estimate (eu-west-1, t3.medium, Multi-AZ RDS):"
	@echo "  EKS: \$73/mo | RDS: \$70/mo | Nodes: \$45/mo"
	@echo "  NAT: \$32/mo | ALB: \$16/mo | Redis: \$25/mo"
	@echo "  Total: ~\$277/mo (cost-optimized: ~\$180/mo)"

# ─── Common ───────────────────────────────────────────────────────

help:
	@echo "Capstone Infrastructure Makefile"
	@echo ""
	@echo "MODE A (Local):"
	@echo "  make local-up      - Create kind cluster"
	@echo "  make local-down    - Delete kind cluster"
	@echo "  make local-status  - Show cluster status"
	@echo ""
	@echo "MODE B (AWS):"
	@echo "  make aws-init      - Initialize Terraform backends"
	@echo "  make aws-plan      - Plan infrastructure changes"
	@echo "  make aws-apply     - Apply infrastructure (dev only)"
	@echo "  make aws-destroy   - Destroy all dev resources"
	@echo "  make aws-cost      - Show cost estimate"
	@echo ""
	@echo "NOTE: Day 28 lab = skeleton only. No cluster created today."
```

---

### Step 7: Tạo README cho từng repo

**File: `capstone-infra/README.md`**

```markdown
# capstone-infra

**Owner:** @capstone/sre-team
**Purpose:** Terraform code quản infrastructure cho Capstone platform.

## Mode Support

| Mode | Technology | Cost |
|------|-----------|------|
| A: Local | kind + Helm bitnami | $0 |
| B: AWS | EKS + RDS + ElastiCache | ~$180-277/tháng |

## Repository Structure

```
modules/           # Terraform modules (vpc, eks, rds, elasticache, irsa)
live/              # Environment-specific Terraform
  dev/
  staging/
  prod/
docs/
  adr/             # Architecture Decision Records
  architecture.md  # ASCII diagram + module breakdown
  cost-estimate.md # AWS cost estimate + cleanup
  security-baseline.md
```

## Quick Start

```bash
# Mode A
make local-up

# Mode B
make aws-plan
make aws-apply
make aws-destroy  # IMPORTANT: Run after lab!
```

## Key Decisions (ADRs)

- ADR-0001: Mode A là default, Mode B optional
- ADR-0002: 3-repo split (infra/platform/apps)
- ADR-0003: Secrets via ESO + AWS Secrets Manager
- ADR-0004: Promotion via Git PR, not `argocd app sync`
- ADR-0005: Disaster recovery strategy
```

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Team 5 dev muốn làm Capstone trong 8 ngày, budget $0. Chọn mode nào? Những components nào không thể test được?

> **Trả lời:** Mode A (Local/kind + free). Không test được: IRSA, RDS Multi-AZ, ElastiCache cluster mode, ALB Controller, ACM certificate, AWS Secrets Manager, VPC endpoint, NAT Gateway cost optimization, OIDC GitHub Actions. Những component đó vẫn được giới thiệu qua code review trong Day 32-34.

**Câu 2:** Vẽ dependency graph giữa 3 repo (infra → platform → apps). Tại sao infra không bao giờ phụ thuộc apps?

> **Trả lời:** infra provisions cluster + data layer. platform sync cluster addons (ArgoCD, ingress, ESO). apps deploy workloads. infra phụ thuộc apps → nếu app team refactor, infra phải thay đổi → SRE phải review app PR → không có ownership boundary → blast radius lớn.

**Câu 3:** Ngân sách startup 10 dev: $200/tháng cho dev/staging Capstone environment. Thiết kế cost-optimized Mode B với budget đó.

> **Trả lời:** (Xem exercises.md Challenge 1 — phần trả lời chi tiết.)

**Câu 4:** ADR cần những field nào? Viết 1 ADR ngắn (5-10 dòng) cho decision "dùng ArgoCD thay vì Flux".

> **Trả lời:** ADR = Status + Context + Decision + Consequences. 1 ví dụ:
> - Status: Accepted
> - Context: Team cần GitOps tool, đã biết ArgoCD từ Day 17-27
> - Decision: ArgoCD được dùng cho Capstone (thay vì Flux hoặc Fluent)
> - Consequences: Positive (đã có kiến thức, cộng đồng lớn, ApplicationSet mạnh); Negative (team chưa quen Flux nếu cần so sánh sau này)

**Câu 5:** Học viên quên chạy `make aws-destroy`, để EKS + RDS chạy 2 tuần. Ước tính bill?

> **Trả lời:** ~$277 × 2 tuần = ~$138 + thêm CloudWatch/data transfer. Trong 8 ngày Capstone: ~$277/4 = ~$70. Mitigation: luôn dùng budget alert + Terraform destroy ngay sau lab.

---

## 7. Tóm tắt cuối ngày

### Điều đã học

**Architecture & Mode:**
- Capstone target: 3 microservices (api-service, worker-service, frontend-service) + PostgreSQL + Redis + ArgoCD GitOps + CI/CD + Observability
- Mode A (Local/kind): $0, barrier thấp, tập trung GitOps pattern
- Mode B (AWS/EKS): ~$180-277/tháng, production simulation, cover AWS-native components
- Layered architecture: Network → Cluster+IAM → Data → Platform Bootstrap → Apps

**Repository Strategy:**
- 3-repo polyrepo: infra-repo (Terraform) → platform-repo (cluster addons) → apps-repo (workloads)
- Destroy order: apps → platform → infra (reverse of creation)
- Day 28 KHÔNG deploy gì — chỉ tạo skeleton + design docs

**Cost & Security:**
- Mode B cost: EKS $73 + RDS $70 + Nodes $45 + NAT $32 + ALB $16 + Redis $25 = ~$277/mo
- Cost optimization: VPC Endpoint thay NAT, Spot nodes, Single-AZ non-prod, t3.small dev
- Security: IRSA thay long-lived key, OIDC GitHub Actions, ESO + ASM, RDS private subnet, no `latest` tag

**ADR Practice:**
- ADR = Status + Context + Decision + Consequences
- 5 ADR cho Capstone: mode, repo split, secrets, promotion, DR

### Output của ngày hôm nay

```
week-5-capstone/day-28-capstone-architecture/
├── capstone-infra/                    (hoặc local folder)
│   ├── docs/
│   │   ├── architecture.md           ← ASCII diagram + module breakdown
│   │   ├── adr/
│   │   │   └── 0001-mode-a-vs-b.md   ← ADR-0001
│   │   ├── cost-estimate.md          ← Mode B cost table + cleanup
│   │   └── security-baseline.md      ← 20-bullet checklist
│   ├── Makefile                       ← make local-up/down/aws-plan/destroy
│   ├── CODEOWNERS
│   └── README.md
├── capstone-platform/                  (hoặc local folder)
│   └── CODEOWNERS
└── capstone-apps/                     (hoặc local folder)
    └── CODEOWNERS
```

### Chuẩn bị cho Day 29

Day 29 sẽ build **Network Layer** — tạo VPC design, public/private subnet, route table, NAT Gateway (Mode B) hoặc kind network (Mode A), security group. Học viên bắt đầu viết Terraform code thực tế đầu tiên của Capstone.

---

## 8. Tham khảo thêm

### Documentation
- [AWS EKS Pricing](https://aws.amazon.com/eks/pricing/)
- [AWS RDS Pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS ElastiCache Pricing](https://aws.amazon.com/elasticache/pricing/)
- [AWS EKS Best Practices — Security](https://aws.github.io/aws-eks-best-practices/)
- [kind Documentation](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [ADR GitHub topic — examples](https://github.com/joelparkerhenderson/architecture-decision-records)
- [Terraform AWS Provider — EKS](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster)

### Tools
- [AWS Pricing Calculator](https://calculator.aws.amazon.com/)
- [Grype — Container image vulnerability scanner](https://github.com/anchore/grype)
- [Trivy — Simple vulnerability scanner](https://aquasecurity.github.io/trivy/)
- [AWS Cost Explorer](https://aws.amazon.com/cost-management/aws-cost-explorer/)
- [kind — Kubernetes in Docker](https://kind.sigs.k8s.io/)
