# Day 28 — Capstone Architecture, Repo Strategy, Cost Strategy
## Exercises & Challenges

> 5 challenges + 1 bonus challenge. Mỗi challenge có phần bài tập và phần hướng dẫn giải. Dành 15-30 phút mỗi challenge.

---

## Challenge 1: Cost-Optimized Mode B cho Startup 10 Dev

**Độ khó:** Medium
**Thời gian:** 20 phút
**Mục tiêu:** Thiết kế Mode B cho startup 10 dev, target < $200/tháng cho dev + staging environment.

### Bài tập

Startup của bạn có 10 dev cần dev + staging environment cho Capstone. Budget: < $200/tháng. Dev environment cần đủ để:
- Chạy 3 microservices (api, worker, frontend)
- Test CI/CD pipeline (GitHub Actions → ECR)
- Test promotion flow (dev → staging)
- Không cần production-grade availability

**Yêu cầu:**

1. Tính toán cost cho từng thay đổi sau và tổng hợp:
   - Dev: EKS + RDS Single-AZ + ElastiCache (thay vì Multi-AZ)
   - Dev: kind (local) thay vì EKS → bỏ EKS control plane + RDS dev
   - Staging: Spot node thay On-Demand (30% mix)
   - Network: VPC Endpoint for S3/ECR thay NAT Gateway (nếu tất cả AWS access qua VPC endpoint)

2. Thiết kế Terraform structure cho multi-environment (dev/staging) với shared module

3. Viết Terraform snippet `live/dev/main.tf` sử dụng Spot instances và single-AZ RDS

4. Đề xuất monitoring strategy tiết kiệm cho dev environment (dùng less expensive metrics hoặc disable non-critical dashboards)

5. Tính tổng cost cuối cùng — có dưới $200/tháng không?

### Hướng dẫn giải

**Step 1: Cost breakdown baseline (dev + staging)**

```
EKS Control Plane:     $73 × 2 envs   = $146
EC2 t3.medium × 2:    $45 × 2 envs   = $90
RDS Multi-AZ:          $70 × 2 envs   = $140
ElastiCache:           $25 × 2 envs   = $50
NAT Gateway:           $32 × 2 envs   = $64
ALB:                   $16 × 2 envs   = $32
Secrets Manager:      $1.35 × 2      = $2.70
---
Total:                                ~$525/month
```

**Step 2: Optimization**

| Thay đổi | Tiết kiệm/tháng |
|-----------|----------------|
| Dev: kind local thay EKS | -$73 (EKS) -$35 (nodes) -$32 (NAT) -$16 (ALB) -$25 (RDS) -$12 (Redis) = **-$193** |
| Staging: Spot 30% mix | -$13 (nodes) |
| Staging: Single-AZ RDS | -$35 (RDS) |
| Dev: Redis không có (dùng Docker Compose) | -$12 (Redis) |
| S3/ECR VPC Endpoint thay NAT | -$25 (NAT) |

**Step 3: Final cost**

```
Dev (kind local):
  kind cluster:          $0
  Docker Compose PG:     $0
  Docker Compose Redis:  $0
  GHCR:                  $0
  = $0

Staging (EKS):
  EKS Control Plane:     $73
  EC2 Spot × 1 + OD × 1: $28
  RDS Single-AZ:          $35
  VPC Endpoint (S3/ECR): $0
  ALB:                   $16
  Secrets Manager:       $1.35
  Route53 + ECR:         $0.50
  = ~$153/month  ✓ (dưới $200)

Total dev + staging:     ~$153/month  ✓
```

**Step 4: Terraform snippet**

```hcl
# live/staging/main.tf
module "network" {
  source = "../../modules/network"
  environment         = "staging"
  cidr_block          = "10.1.0.0/16"
  availability_zones  = ["eu-west-1a", "eu-west-1b"]
  enable_nat_gateway  = false  # dùng VPC Endpoint
}

module "eks" {
  source = "../../modules/eks"

  cluster_name    = "capstone-staging"
  environment     = "staging"
  vpc_id          = module.network.vpc_id
  subnet_ids      = module.network.private_subnet_ids

  node_groups = {
    mixed = {
      desired_capacity = 2
      max_capacity    = 4
      min_capacity    = 1

      instance_types = ["t3.medium"]
      spot_percentage = 30

      labels = {
        environment = "staging"
        capacity-type = "mixed"
      }
    }
  }
}

module "rds" {
  source = "../../modules/rds"

  environment     = "staging"
  db_instance    = "db.t3.small"  # single-AZ cho staging
  multi_az       = false
  allocated_storage = 50  # GB
  vpc_id         = module.network.vpc_id
  subnet_ids     = module.network.private_subnet_ids
}
```

**Kết luận:** $153/tháng cho dev (kind) + staging (EKS) ✓ Target < $200 đạt được.

---

## Challenge 2: Refactor 1-Repo Monorepo → 3 Polyrepo Migration Plan

**Độ khó:** Medium-High
**Thời gian:** 25 phút
**Mục tiêu:** Lên kế hoạch migrate 1 repo monorepo Capstone thành 3 repo production-grade trong 1 sprint (2 tuần) mà không downtime.

### Bài tập

Học viên đang có 1 repo monorepo cho Capstone:

```
capstone-monorepo/
├── terraform/           # VPC, EKS, RDS
├── platform/           # ArgoCD, Helm charts
├── apps/              # api-service, worker, frontend
└── argocd/            # Applications
```

Cần migrate sang 3-repo structure:
```
capstone-infra/       (terraform)
capstone-platform/    (platform)
capstone-apps/        (apps)
```

**Yêu cầu:**

1. Viết migration plan 2 tuần (10 working days) — chia theo tuần, mỗi ngày làm gì

2. Xác định:
   - Thứ tự migrate (infra trước hay platform trước? Tại sao?)
   - Làm sao giữ ArgoCD sync liên tục trong quá trình migrate?
   - Khi nào switch ArgoCD Application repo URL?

3. Viết migration script/commands cho ngày quan trọng nhất (ngày switch)

4. Rollback plan: nếu sau 1 tuần phát hiện vấn đề, làm sao quay lại monorepo nhanh nhất?

5. CI/CD migration: GitHub Actions workflows cần thay đổi gì?

### Hướng dẫn giải

**Step 1: Migration plan 2 tuần**

```
TUẦN 1 (Foundation)
─────────────────────
Day 1-2: Tạo 3 repo mới + folder structure + CODEOWNERS
         - git remote add origin <new-repo-url>
         - Copy terraform/ → capstone-infra/
         - Copy platform/ → capstone-platform/
         - Copy apps/ → capstone-apps/
         - Setup CI pipelines riêng cho từng repo

Day 3-4: Migrate infra (terraform/) trước — ít blast radius nhất
         - Verify: terraform plan + apply trên dev
         - Setup S3 backend riêng cho capstone-infra
         - ArgoCD: tạo Application mới point vào capstone-platform

Day 5:   Migrate platform (platform/)
         - ArgoCD: switch Application URL → capstone-platform
         - Verify: platform addons (ingress, ESO, prometheus) sync OK

TUẦN 2 (Cutover)
─────────────────────
Day 6-7: Migrate apps (apps/)
         - ArgoCD: switch Application URL → capstone-apps
         - Verify: 3 services deploy OK

Day 8-9: Cleanup
         - Update GitHub Actions workflows
         - Update README / documentation
         - Old repo: set to read-only, giữ 30 ngày

Day 10:  Validation
         - Full E2E test: code → CI → image → PR → sync → verify
         - DR test: xóa 1 service → ArgoCD re-sync
```

**Step 2: Thứ tự migrate**

```
THỨ TỰ ĐÚNG:
infra → platform → apps

Lý do:
1. infra không phụ thuộc platform/apps
2. platform không phụ thuộc apps
3. apps phụ thuộc platform (ArgoCD Application reference)

Nếu làm ngược (apps → platform → infra):
- Apps cần ArgoCD để deploy
- ArgoCD cần platform addons
- Platform addons cần cluster
- Circle dependency
```

**Step 3: Switch plan (Day 5-7)**

```bash
#!/bin/bash
# switch-argo-app-to-new-repo.sh

# Step 1: Verify new repo is healthy
argocd app get platform-addons
# EXPECTED: Synced, Healthy

# Step 2: Patch ArgoCD Application to point to new repo
kubectl patch application platform-addons \
  -n argocd \
  -p '{"spec": {"source": {"repoURL": "https://github.com/YOUR_USER/capstone-platform.git"}}}'

# Step 3: Verify ArgoCD sync
argocd app get platform-addons --watch

# Step 4: Verify no drift
argocd app diff platform-addons
# EXPECTED: (no diff)
```

**Step 4: Rollback plan**

```
Rollback strategy: git branch protection + blue-green switch

1. KHÔNG xóa old repo — set to read-only (Settings → Danger Zone)
2. Keep old repo alive 30 ngày
3. Nếu cần rollback:
   kubectl patch application platform-addons \
     -p '{"spec": {"source": {"repoURL": "https://github.com/YOUR_USER/capstone-monorepo.git"}}}'
   ArgoCD sync → revert về old repo
```

---

## Challenge 3: ADR cho Production 50 Microservices

**Độ khó:** Medium
**Thời gình:** 20 phút
**Mục tiêu:** Viết ADR cho production platform quy mô 50 microservices với nhiều team.

### Bài tập

Công ty của bạn có 50 microservice, 8 team, 200 dev. Cần viết ADR cho 4 decision points quan trọng:

1. **Managed K8s vs Self-managed**: EKS/GKE managed vs kops/self-hosted
2. **Database**: RDS Managed PostgreSQL vs Aurora Serverless vs self-managed on EC2
3. **Multi-region strategy**: Single-region vs Active-Active 2 region vs Active-Passive
4. **Deployment strategy**: ArgoCD ApplicationSet vs per-service ArgoCD Application

### Hướng dẫn giải

**ADR-001: Managed Kubernetes vs Self-managed**

```markdown
# ADR-001: AWS EKS Managed Kubernetes

## Status
Accepted — 2026-05-15

## Context
50 microservice, 8 team, 200 dev. Kubernetes cluster là nền tảng. Cần quyết định managed hay self-hosted.

## Decision
Dùng AWS EKS (managed Kubernetes).

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| EKS (managed) | Không quản control plane, tự động upgrade, H/A | $73/cluster/tháng, vendor lock-in |
| EKS Anywhere | Không vendor lock-in, run anywhere | Tự quản control plane, phức tạp hơn |
| kops | Full control, open source | Tự quản etcd, upgrade pain, SRE effort |
| Self-hosted (kubeadm) | Full control | 1 team FTE quản cluster, high operational burden |

## Consequences

### Positive
- SRE team tập trung vào application, không phải cluster operations
- Automated upgrade, patching, H/A control plane
- Native integration: IRSA, VPC CNI, EBS CSI, Fargate

### Negative
- Vendor lock-in với AWS
- $73/cluster/tháng × 3 envs = $219/tháng cluster cost
- AWS thay đổi behavior (VD: VPC CNI thay đổi) → phải adapt

### Neutral
- Cluster ngang size không phụ thuộc số service (1 cluster × 50 service vs 1 cluster × 5 service)
```

**ADR-002: RDS PostgreSQL vs Aurora Serverless**

```markdown
# ADR-002: RDS PostgreSQL cho structured data

## Status
Accepted — 2026-05-15

## Context
50 service × 8 team. Phần lớn dùng PostgreSQL. 2-3 service cần serverless data (variable workload, spiky traffic).

## Decision
Default: RDS PostgreSQL (managed, Multi-AZ)
Exception: Aurora Serverless v2 cho service có workload pattern unpredictable

## Consequences

### Positive
- RDS: predictable cost, well-understood, team familiarity
- Aurora Serverless: auto-scale, pay-per-use cho spiky workload

### Negative
- Aurora Serverless: phức tạp hơn, IAM integration khác, backup có chi phí
- Mỗi service 1 RDS instance: 50 service × $35-70/instance = $1,750-3,500/tháng
  → Consider: RDS Proxy + shared instance cho non-prod dev
```

**ADR-003: Single-region vs Multi-region**

```markdown
# ADR-003: Single-region eu-west-1, expand later

## Status
Accepted — 2026-05-15

## Context
50 service, 200 dev, primary market = EU. Compliance: GDPR. SLA: 99.9% (RTO 8h, RPO 24h).

## Decision
Single-region (eu-west-1) cho production. Multi-region expansion sau khi có >1 million active users.

## Consequences

### Positive
- Đơn giản: 1 VPC, 1 RDS, 1 EKS
- Cost thấp: không có cross-region data transfer, không có replication cost
- GDPR: data không rời EU

### Negative
- Single point of failure: AWS AZ failure → potential outage
- Mitigation: RDS Multi-AZ + EKS multi-AZ nodes
- RTO 8h: nếu entire region down → unacceptable for some services

### Neutral
- Expansion plan: read replica (Aurora) → active-passive → active-active
```

**ADR-004: ArgoCD ApplicationSet vs per-service Application**

```markdown
# ADR-004: ArgoCD ApplicationSet cho 50-service fleet

## Status
Accepted — 2026-05-15

## Context
50 service × 3-5 environments = 150-250 ArgoCD Application objects. Cần cách quản lý scale.

## Decision
Dùng ApplicationSet (Git Generator) làm primary, Application là exception cho special cases.

Default pattern:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: SERVICES
spec:
  generators:
    - git:
        repoURL: https://github.com/org/apps-repo.git
        directories:
          - path: services/*/overlays/*
  template:
    # render 1 Application per service/env
```

Special cases (dùng Application thay vì ApplicationSet):
- Service có non-standard promotion flow
- Service cần custom sync policy
- Service thuộc compliance-regulated team (cần riêng AppProject)

## Consequences

### Positive
- 1 ApplicationSet thay 50-250 Application file
- Thêm service mới = tạo folder, không cần tạo YAML
- Consistent naming, labeling, sync policy

### Negative
- ApplicationSet controller: additional operational component
- Debugging: ApplicationSet diff khó đọc hơn Application thường
- Generator explosion: 50 service × 5 envs = 250 App → render time
```

---

## Challenge 4: Security Baseline cho Regulated Environment (PCI/HIPAA)

**Độ khó:** Hard
**Thời gian:** 25 phút
**Mục tiêu:** Bổ sung security requirements cho regulated environment (PCI DSS Level 2 hoặc HIPAA) vào security baseline đã có.

### Bài tập

Bạn cần bổ sung security baseline cho Capstone simulation environment. Phiên bản thường (Challenge thường) đã có 20 bullet (MUST/SHOULD/NICE). Bây giờ cần cho regulated environment.

**Yêu cầu:**

1. Với PCI DSS Level 2, bổ sung thêm ít nhất 8 bullet mới (MUST) vào checklist

2. Với HIPAA, bổ sung thêm ít nhất 6 bullet mới (MUST) vào checklist

3. Cho mỗi framework, đề xuất 2 thay đổi kiến trúc thay vì chỉ thay đổi config

4. Vấn đề: ESO + AWS Secrets Manager cần tuân thủ PCI/HIPAA. Đề xuất solution:

   - PCI: Secret lưu trong ASM có encrypted at rest (mặc định). Nhưng IAM access cần được audit. Đề xuất: thêm CloudTrail logging + SCP.
   - HIPAA: PHI data không được lưu trong ASM (ASM không phải HIPAA-eligible theo mặc định). Đề xuất: dùng AWS RDS encrypted + AWS KMS, không dùng ASM cho PHI.

### Hướng dẫn giải

**PCI DSS Level 2 — Bổ sung checklist**

| # | Requirement | Implementation |
|---|-------------|---------------|
| PCI-1 | Firewall config | Security group deny-all default, explicit allow |
| PCI-2 | Default vendor creds | Change all default passwords (RDS, Redis, EKS node) |
| PCI-3 | Cardholder data encryption | PostgreSQL: `aws:rds.storage-encrypted = true` + KMS key |
| PCI-4 | Data in transit | TLS 1.2+ everywhere (ACM cert, PostgreSQL SSL) |
| PCI-7 | Need-to-know access | IRSA với exact ARN, không `*` trong IAM policy |
| PCI-8 | Multi-factor auth | ArgoCD SSO enforced, không password-based access |
| PCI-10 | Logging + monitoring | CloudTrail on, GuardDuty enabled, AWS Config |
| PCI-11 | Vulnerability scan | Trivy scan trong CI, không merge nếu HIGH/CITICAL |
| PCI-12 | Security policy | CODEOWNERS + branch protection + signed commits |
| AWS-1 | KMS key riêng | Tạo KMS key riêng cho capstone, không dùng default |
| AWS-2 | CloudTrail on | Enable CloudTrail trong tất cả region |
| AWS-3 | GuardDuty | Enable GuardDuty, không chỉ basic AWS account |

**HIPAA — Bổ sung checklist**

| # | Requirement | Implementation |
|---|-------------|---------------|
| HIPAA-164.308(a)(1) | Security officer | Assign security role, document in ADR |
| HIPAA-164.312(a)(1) | Access control | IRSA + SSO enforced, không shared credentials |
| HIPAA-164.312(b) | Audit controls | CloudTrail + VPC Flow Logs + RDS audit log |
| HIPAA-164.312(c)(1) | Integrity | S3 versioning + RDS backup có point-in-time recovery |
| HIPAA-164.312(e)(1) | Transmission security | TLS 1.2+ cho tất cả traffic, không HTTP plain |
| HIPAA-164.308(a)(7) | Contingency plan | RDS automated backup (daily), RTO < 4h |
| PHI-1 | PHI không trong ASM | PHI chỉ lưu trong RDS (encrypted) + KMS |
| PHI-2 | No PHI trong logs | Scrub PII từ application logs, không log patient ID |
| PHI-3 | Network segmentation | PHI service trong private subnet riêng, không public |

**Architecture changes:**

```
PCI/HIPAA Architecture Add-ons:

1. KMS Key riêng cho capstone
   resource "aws_kms_key" "capstone" {
     description             = "KMS key for Capstone encryption"
     deletion_window_in_days = 30
     enable_key_rotation     = true
     policy = jsonencode({
       Version = "2012-10-17"
       Statement = [
         {
           Sid    = "Enable IAM User Permissions"
           Effect = "Allow"
           Principal = {
             AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
           }
           Action = "kms:*"
           Resource = "*"
         },
         {
           Sid    = "Allow IRSA to use KMS"
           Effect = "Allow"
           Principal = {
             Federated = module.oidc.oidc_provider_arn
           }
           Action = ["kms:Decrypt", "kms:GenerateDataKey"]
           Resource = "*"
           Condition = {
             StringEquals = {
               "oidc.eks.eu-west-1.amazonaws.com:sub" = "system:serviceaccount:*:capstone-*"
             }
           }
         }
       ]
     })
   }

2. HIPAA: PHI subnet riêng (network segmentation)
   # PHI service (api-service) chạy trong subnet riêng
   # Worker + frontend chạy trong subnet thường
   # Security group: PHI subnet chỉ allow từ worker subnet
```

---

## Challenge 5: Capstone "Mode C" — Hybrid On-Prem Data Plane + Cloud Control Plane

**Độ khó:** Hard
**Thời gian:** 25 phút
**Mục tiêu:** Thiết kế và đánh giá feasibility của "Mode C" — hybrid architecture với data plane on-prem + control plane trên cloud.

### Bài tập

Một doanh nghiệp có datacenter on-prem (VMware) muốn làm Capstone nhưng không muốn migrate toàn bộ lên cloud. Họ muốn:

- **Control plane**: ArgoCD, CI/CD, Observability trên AWS (EKS managed, Prometheus managed)
- **Data plane**: PostgreSQL + Redis + microservices chạy trên VMware on-prem
- **Integration**: ArgoCD syncs từ AWS xuống on-prem cluster qua VPN

**Yêu cầu:**

1. Vẽ ASCII diagram cho Mode C architecture

2. Đánh giá feasibility (có thể làm không? Tại sao?)

3. Xác định 5 trade-off chính so với Mode B (full cloud)

4. Đề xuất 3 use case thực tế khi Mode C hợp lý

5. Viết Terraform snippet cho hybrid network (VPC ↔ On-Prem VPN connection)

### Hướng dẫn giải

**Step 1: ASCII Diagram Mode C**

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              MODE C: HYBRID ARCHITECTURE                         │
│                Control plane on AWS + Data plane on-prem VMware                  │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─── AWS EU-WEST-1 ──────────────────────────────────────────────────────┐   │
│  │                                                                         │   │
│  │  ┌─── VPC (10.0.0.0/16) ──────────────────────────────────────────┐   │   │
│  │  │                                                                  │   │   │
│  │  │  ┌─── SUBNET: control-plane (10.0.0.0/24) ──────────────────┐  │   │   │
│  │  │  │  EKS Control Plane (managed, $73/mo)                     │  │   │   │
│  │  │  │  ArgoCD Server + Repo Server                             │  │   │   │
│  │  │  │  Prometheus (managed by kube-prometheus-stack)           │  │   │   │
│  │  │  │  Grafana + Loki                                          │  │   │   │
│  │  │  │  GitHub Actions runners                                  │  │   │   │
│  │  │  │  ESO Operator (pulls ASM, pushes to on-prem via secret)  │  │   │   │
│  │  │  └──────────────────────────────────────────────────────────┘  │   │   │
│  │  │                                                                  │   │   │
│  │  │  ┌─── SUBNET: egress (10.0.1.0/24) ─────────────────────────┐  │   │   │
│  │  │  │  NAT Gateway ($32/mo)                                    │  │   │   │
│  │  │  │  Site-to-Site VPN: AWS → On-Prem Router (VyOS/OpenSwan) │  │   │   │
│  │  │  └──────────────────────────────────────────────────────────┘  │   │   │
│  │  │                                                                  │   │   │
│  │  │  AWS Services:                                                │   │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐    │   │   │
│  │  │  │    ECR   │ │ Secrets  │ │   ACM    │ │  Route 53   │    │   │   │
│  │  │  │          │ │ Manager  │ │          │ │             │    │   │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘    │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────────────────┘   │
│                                       │                                          │
│                          Site-to-Site VPN (IPSec)                               │
│                          On-prem CIDR: 192.168.1.0/24                           │
│                                       │                                          │
│  ┌─── ON-PREM DATACENTER ────────────────────────────────────────────────────┐   │
│  │                                                                         │   │
│  │  ┌─── VMWARE CLUSTER ───────────────────────────────────────────────┐  │   │
│  │  │                                                                     │  │   │
│  │  │  ┌─── vSphere Namespace: capstone ─────────────────────────────┐  │  │   │
│  │  │  │  ┌────────────────────────────────────────────────────────┐  │  │  │   │
│  │  │  │  │  kubeadm Kubernetes cluster (3 control + 3 worker)  │  │  │  │   │
│  │  │  │  │                                                             │  │  │  │   │
│  │  │  │  │  NAMESPACE: api-service                                   │  │  │  │   │
│  │  │  │  │  NAMESPACE: worker-service                                │  │  │  │   │
│  │  │  │  │  NAMESPACE: frontend-service                              │  │  │  │   │
│  │  │  │  │  NAMESPACE: ingress-nginx                                │  │  │  │   │
│  │  │  │  │  NAMESPACE: monitoring (node-exporter only)             │  │  │  │   │
│  │  │  │  └──────────────────────────────────────────────────────────┘  │  │  │   │
│  │  │  └─────────────────────────────────────────────────────────────▼──┘  │  │
│  │  │                                                                     │  │
│  │  │  ┌─── DATA LAYER (on-prem) ───────────────────────────────────────┐  │  │
│  │  │  │  PostgreSQL 16 (VM, 2 vCPU, 8GB RAM)                         │  │  │
│  │  │  │  Redis 7 Cluster (3 nodes, VM)                                │  │  │
│  │  │  │  Backup: NFS share → daily pg_dump → S3 via VPN             │  │  │
│  │  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │
│  │                                                                         │   │
│  └────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  COST: ~$110/mo (AWS) + ~$0 (on-prem existing hardware)                          │
│  VPN:   ~$35-50/mo (VPN gateway hoặc VyOS VM)                                    │
│  NOTE:  Feasible nếu có sẵn on-prem hardware, không phải trả tiền thêm           │
│                                                                                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Step 2: Feasibility Assessment**

```
FEASIBILITY: CÓ THỂ LÀM — với điều kiện:

✓ ArgoCD hỗ trợ multi-cluster từ 1 control plane: ArgoCD Hub → spoke on-prem
✓ Kubernetes cluster on-prem join được EKS Extended Support (EKE on-prem)
✓ VPN Site-to-Site kết nối AWS VPC ↔ on-prem network dễ setup
✓ ESO có thể pull từ ASM (AWS) và sync vào on-prem cluster
✓ GitHub Actions có thể build + push đến ECR (AWS), deploy đến on-prem

⚠️ PHỨC TẠP HƠN MODE B:
- Cần quản lý 2 Kubernetes cluster thay vì 1
- Network latency: ArgoCD poll/repo-sync qua VPN
- On-prem SPOF: VMware cluster không có Multi-AZ như AWS
- Operational overhead: 2 stack khác nhau cần kiến thức kép
```

**Step 3: 5 Trade-offs so với Mode B**

| Trade-off | Mode B (Full Cloud) | Mode C (Hybrid) |
|-----------|---------------------|-----------------|
| **Latency** | < 5ms (same AZ) | 20-100ms (VPN) — API calls từ pod → RDS/Redis chậm hơn |
| **Availability** | Multi-AZ, SLA 99.99% | On-prem SPOF, phụ thuộc VMware HA |
| **Cost** | ~$180-277/mo | ~$110 + on-prem hardware (nếu có sẵn) |
| **Operational complexity** | 1 platform (AWS) | 2 platform (AWS + VMware) |
| **Compliance** | AWS certifications (SOC2, PCI) | On-prem compliance tự manage |

**Step 4: 3 Use Cases thực tế cho Mode C**

```
1. Pharma/Healthcare: Data sovereignty requirement
   - PHI không được rời on-prem datacenter (GDPR, local law)
   - ArgoCD + CI/CD trên cloud để leverage managed services
   - Data plane on-prem để compliance

2. Legacy Migration Path
   - Đang migrate từ on-prem VMware → cloud
   - Mode C = intermediate step trong 12-18 tháng migration
   - Progressive: move control plane first (6 tháng) → move data plane after

3. Multi-cloud Strategy
   - AWS cho control plane (EKS, CI/CD)
   - Azure/GCP hoặc on-prem cho data plane
   - ArgoCD hub quản lý multi-cluster fleet
```

**Step 5: Terraform snippet — Hybrid VPN**

```hcl
# modules/network/hybrid-vpn.tf
resource "aws_vpn_connection" "onprem" {
  customer_gateway_id = aws_customer_gateway.onprem.id
  vpn_gateway_id      = aws_vpn_gateway.this.id
  type                = "ipsec.1"
  static_routes_only  = false  # dynamic routing via BGP

  tunnel1_pre_shared_key = var.vpn_tunnel1_psk  # rotate định kỳ
  tunnel2_pre_shared_key = var.vpn_tunnel2_psk

  tunnel1_inside_cidr = "169.254.0.1/30"  # VPN tunnel IP
  tunnel2_inside_cidr = "169.254.0.5/30"
}

resource "aws_customer_gateway" "onprem" {
  bgp_asn    = 65000  # On-prem router ASN
  ip_address = var.onprem_vpn_ip  # Public IP của on-prem router
  type       = "ipsec.1"

  tags = {
    Environment = "capstone"
    Type       = "customer-gateway"
  }
}

resource "aws_vpn_gateway" "this" {
  vpc_id = module.vpc.vpc_id
  type   = "vgw"

  tags = {
    Name = "capstone-vpn-gateway"
  }
}

resource "aws_vpn_gateway_route_propagation" "private_subnets" {
  vpn_gateway_id = aws_vpn_gateway.this.id
  subnet_ids     = module.vpc.private_subnet_ids
}
```

---

## Bonus Challenge: On-Call Runbook cho Capstone

**Độ khó:** Medium
**Thời gian:** 30 phút
**Mục tiêu:** Viết on-call runbook cho Capstone platform bao gồm alert → triage → mitigation → postmortem.

### Bài tập

Viết on-call runbook cho 4 scenarios:

1. **P1: ArgoCD application stuck in Syncing/Progressing > 10 phút**
2. **P2: All 3 microservices returning 5xx, database connection timeout**
3. **P2: Prometheus/Grafana không hiển thị metrics sau upgrade**
4. **P3: 1 service có elevated latency (P95 > 500ms nhưng < 2s)**

### Hướng dẫn giải (outline)

```markdown
# Capstone On-Call Runbook

## On-Call Escalation Matrix

| Severity | Response Time | Notification |
|----------|-------------|--------------|
| P1 (Outage) | 5 phút | PagerDuty → SMS + call |
| P2 (Degraded) | 15 phút | PagerDuty → push |
| P3 (Warning) | 1 giờ | Slack #alerts |

## Scenario 1: ArgoCD Application Stuck Syncing

### Symptoms
- ArgoCD UI: app = "Syncing" > 10 phút
- Slack: ArgoCD sync alert

### Triage
```bash
# 1. Check ArgoCD app events
argocd app events <app-name> -n argocd | grep -A 5 -B 5 "Warning"

# 2. Check application sync status
argocd app get <app-name> -n argocd

# 3. Check ArgoCD repo-server logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-repo-server --tail=50

# 4. Check application resources
argocd app resources <app-name> -n argocd
```

### Common Causes

| Cause | Indicator | Fix |
|-------|-----------|-----|
| Invalid YAML | Events: "Error parsing manifest" | Fix YAML, commit → PR |
| RBAC deny | Events: "User not allowed" | Check AppProject policy |
| Resource conflict | Events: "Already exists" | kubectl apply -–force |
| Network timeout | Repo server error | Check VPN/VPC endpoint |
| Image pull error | Pod: ImagePullBackOff | Check ECR permissions + IRSA |

### Mitigation
```bash
# Option 1: Retry sync
argocd app sync <app-name> --force

# Option 2: Rollback to last good revision
argocd app history <app-name> -n argocd
argocd app rollback <app-name> <revision>

# Option 3: Hard reset (nuclear option)
argocd app delete <app-name> --cascade
# ArgoCD App of Apps sẽ recreate
```

### Postmortem trigger
- Nếu P1: tạo postmortem trong 48 giờ
- Nếu P2: document in incident tracker

## Scenario 2: All Services 5xx — Database Timeout

### Symptoms
- PagerDuty: "api-service 5xx rate > 10%"
- Grafana: database connections = 0 hoặc maxed out

### Triage
```bash
# 1. Check database connectivity from pod
kubectl exec -it deploy/api-service -n api-service -- \
  psql "$DATABASE_URL" -c "SELECT 1"

# 2. Check RDS connection count
aws rds describe-db-connections \
  --db-instance-identifier capstone-db-prod \
  --region eu-west-1

# 3. Check database CPU/connections in Grafana
# Dashboard: RDS PostgreSQL → Metrics: db_client_connections

# 4. Check application logs
kubectl logs -l app=api-service -n api-service --tail=100 | grep "connection"
```

### Common Causes

| Cause | Indicator | Fix |
|-------|-----------|-----|
| RDS CPU > 90% | CloudWatch: CPUUtilization | Scale up or optimize query |
| Connection pool exhausted | App: "remaining connection slots" | Reduce app pool size or increase RDS `max_connections` |
| RDS restart/reboot | `describe-db-instances`: Status = rebooting | Wait 2-5 phút, Aurora ~30s |
| Network partition | Pod can't reach RDS | Check security group rules |
| Credentials expired | ESO sync failed → empty password | Run ESO sync: `kubectl annotate externalsecret <name> force-sync=$(date +%s)` |

### Mitigation
```bash
# Immediate: restart app pods (reset connection pool)
kubectl rollout restart deployment/api-service -n api-service
kubectl rollout restart deployment/worker-service -n worker-service
kubectl rollout restart deployment/frontend-service -n frontend-service

# Check ESO sync
kubectl get externalsecret -n api-service
kubectl describe externalsecret api-service-secrets -n api-service
```

## Scenario 3: Prometheus/Grafana No Metrics After Upgrade

### Triage
```bash
# 1. Check Prometheus targets
kubectl port-forward svc/prometheus-server 9090:9090 -n monitoring
# Open: http://localhost:9090/targets

# 2. Check service monitor
kubectl get servicemonitor -A
kubectl describe servicemonitor api-service -n monitoring

# 3. Check Prometheus operator logs
kubectl logs -n monitoring -l app=prometheus-operator --tail=50
```

### Common Causes
- RBAC: Prometheus ServiceAccount không có quyền scrape namespaces mới
- `serviceMonitorNamespace`: chỉ scrape trong 1 namespace
- Helm upgrade reset `values.yaml` → mất custom scrape config

## Scenario 4: Elevated Latency P95 > 500ms

### Triage
```bash
# 1. Check application traces
# (Grafana Tempo / Jaeger if installed)

# 2. Check HPA — is pod at max replicas?
kubectl get hpa -n api-service
kubectl top pods -n api-service

# 3. Check database query time
kubectl exec -it deploy/api-service -n api-service -- \
  psql "$DATABASE_URL" -c "SELECT * FROM pg_stat_activity;"

# 4. Check Redis hit rate
redis-cli -h $REDIS_HOST info stats | grep hit_rate
```

### Mitigation
```bash
# Scale up replicas
kubectl scale deployment api-service -n api-service --replicas=5

# Check slow query
# (application logs: "slow query" or DB query > 100ms)
```
```
