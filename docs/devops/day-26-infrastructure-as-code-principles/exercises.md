# Day 26: Exercises — Infrastructure as Code Principles

## Exercise 1: Easy — IaC Concepts & Terminology

### Context

Bạn vừa gia nhập một team đang chuyển từ manual infrastructure management sang Infrastructure as Code. Team lead yêu cầu bạn chứng minh hiểu biết về IaC concepts trước khi bắt đầu viết Terraform.

### Yêu cầu

1. Phân loại các hành động sau thành **Declarative** hoặc **Imperative**:
   - `kubectl apply -f deployment.yaml`
   - `aws ec2 run-instances --image-id ami-xxx`
   - `terraform apply`
   - `docker run -d nginx`
   - `helm install my-app ./chart`
   - `ansible-playbook setup.yml`
   - `bash deploy.sh`

2. Cho mỗi scenario sau, xác định vấn đề IaC:
   - Engineer A tạo security group trên console, Engineer B modify cùng security group bằng Terraform
   - Team chạy `terraform apply` 2 lần liên tiếp, lần 2 tạo thêm resources
   - State file bị xóa, `terraform plan` hiển thị tạo lại toàn bộ resources

3. Viết `.gitignore` cho một Terraform project, giải thích vì sao mỗi entry cần ignore.

### Expected Outcome

- Phân loại chính xác 7 hành động.
- Xác định đúng vấn đề: drift, non-idempotency, state loss.
- `.gitignore` bao gồm: `*.tfstate`, `*.tfstate.backup`, `.terraform/`, `*.tfvars` (chứa secrets).

### Hint

- Declarative = mô tả trạng thái cuối cùng, tool tự tính bước thực hiện.
- Imperative = mô tả từng bước cụ thể.
- State file chứa sensitive data — không bao giờ commit vào Git.

### Acceptance Criteria

- [ ] Phân loại đúng ít nhất 6/7 hành động
- [ ] Giải thích đúng 3 vấn đề IaC
- [ ] `.gitignore` đầy đủ và có giải thích

### Bonus Challenge

Viết thêm 3 scenarios drift có thể xảy ra trong production và cách phát hiện + xử lý mỗi scenario.

<details>
<summary>Solution</summary>

**1. Phân loại:**

| Hành động | Type | Giải thích |
|-----------|------|-----------|
| `kubectl apply -f deployment.yaml` | Declarative | Mô tả desired state, K8s tự reconcile |
| `aws ec2 run-instances` | Imperative | Lệnh trực tiếp tạo instance |
| `terraform apply` | Declarative | Apply desired state từ HCL |
| `docker run -d nginx` | Imperative | Lệnh trực tiếp chạy container |
| `helm install my-app ./chart` | Declarative | Template → manifest → K8s apply |
| `ansible-playbook setup.yml` | Declarative* | Declarative intent, imperative execution |
| `bash deploy.sh` | Imperative | Script chạy từng bước |

*Ansible là hybrid — playbook declarative, nhưng execution là imperative (SSH + run commands).

**2. Vấn đề IaC:**

- **Drift**: Console change + Terraform manage cùng resource → next plan sẽ revert console change hoặc conflict.
- **Non-idempotency**: Terraform PHẢI idempotent — nếu lần 2 tạo thêm resources, đó là bug trong code (ví dụ: dùng `count` sai, hoặc random name).
- **State loss**: State bị xóa → Terraform nghĩ không có resource nào → plan tạo lại tất cả → duplicate resources hoặc error (resource exists).

**3. .gitignore:**

```gitignore
# State files - chứa secrets (passwords, keys, IPs)
*.tfstate
*.tfstate.*

# Terraform directory - cached plugins, modules
.terraform/

# Lock file cho provider versions (CÓ THỂ commit - optional)
# .terraform.lock.hcl

# Variable files có thể chứa secrets
*.tfvars
*.tfvars.json

# Override files
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Plan output files
*.tfplan

# Crash log
crash.log
crash.*.log
```

</details>

---

## Exercise 2: Medium — Thiết kế IaC Workflow cho Team

### Context

Bạn là DevOps engineer tại một SaaS company có 20 engineers. Hiện tại infrastructure được quản lý bằng mix of console clicks và bash scripts. CTO yêu cầu bạn thiết kế IaC workflow hoàn chỉnh.

### Yêu cầu

1. **Thiết kế Git branching strategy** cho IaC repository:
   - Branch naming convention
   - PR process
   - Review requirements
   - Merge strategy

2. **Thiết kế CI/CD pipeline** cho IaC:
   - Vẽ pipeline stages (dùng ASCII art hoặc mermaid)
   - Mô tả mỗi stage làm gì
   - Xác định quality gates
   - Xác định approval process

3. **Thiết kế state management strategy**:
   - State backend lưu ở đâu
   - State locking mechanism
   - State split strategy (bao nhiêu state files, tách theo gì)
   - Backup strategy cho state

4. **Viết IaC PR template** mà team sẽ dùng cho mọi infrastructure change.

### Expected Outcome

- Git strategy document hoàn chỉnh.
- Pipeline diagram với ít nhất 5 stages.
- State strategy document.
- PR template markdown file.

### Hint

- Pipeline: lint → validate → plan → policy check → apply.
- State split: theo environment + theo blast radius.
- PR template cần: description, plan output, blast radius, rollback plan, checklist.

### Acceptance Criteria

- [ ] Git strategy cover branching, review, merge
- [ ] Pipeline có ít nhất: lint, validate, plan, policy, apply
- [ ] State strategy có backend, locking, split, backup
- [ ] PR template có ít nhất 5 sections
- [ ] Workflow phù hợp team 20 người

### Bonus Challenge

Thêm **drift detection** vào workflow: scheduled job phát hiện drift và tạo alert/issue tự động.

<details>
<summary>Solution</summary>

**1. Git Branching Strategy:**

```
main (protected)
  └── feature/infra-xxx (short-lived)

Rules:
- main = production state, always deployable
- Feature branches từ main, merge back to main
- Branch naming: {type}/infra-{ticket}-{short-description}
  - feat/infra-123-add-redis-cluster
  - fix/infra-456-sg-port-update
  - chore/infra-789-upgrade-k8s
- PRs require: 1 approval from infra team + plan review
- Squash merge to keep history clean
- Delete branch after merge
```

**2. CI/CD Pipeline:**

```
┌────────┐   ┌──────────┐   ┌────────┐   ┌──────────┐   ┌─────────┐   ┌────────┐
│  Lint  │──>│ Validate │──>│  Plan  │──>│  Policy  │──>│ Approve │──>│ Apply  │
│        │   │          │   │        │   │  Check   │   │ (human) │   │        │
└────────┘   └──────────┘   └────────┘   └──────────┘   └─────────┘   └────────┘
   │              │              │             │              │            │
 tflint       terraform      terraform     OPA/Sentinel   PR review   terraform
 fmt check    validate       plan          cost estimate  + plan OK    apply
                                                                         │
                                                                    ┌────┴────┐
                                                                    │ Verify  │
                                                                    │ (smoke) │
                                                                    └─────────┘

Triggers:
- PR opened/updated → Lint + Validate + Plan + Policy (auto)
- PR merged to main → Apply (after human approve plan)
- Schedule (weekly) → Drift detection
```

**3. State Management:**

```
Backend: AWS S3 + DynamoDB (locking)

State split:
├── networking/        # 1 state - ít thay đổi
│   ├── dev.tfstate
│   ├── staging.tfstate
│   └── prod.tfstate
├── kubernetes/        # 1 state - thay đổi monthly
│   └── prod.tfstate
├── database/          # 1 state - critical, ít thay đổi
│   └── prod.tfstate
└── application/       # 1 state - thay đổi thường xuyên
    ├── dev.tfstate
    ├── staging.tfstate
    └── prod.tfstate

Backup:
- S3 versioning enabled (30 days retention)
- Cross-region replication cho prod state
- Weekly state snapshot to separate bucket
```

**4. PR Template:**

```markdown
## Infrastructure Change Request

### Description
<!-- Mô tả ngắn gọn thay đổi -->

### Motivation
<!-- Vì sao cần thay đổi này -->

### Plan Output
<!-- Paste terraform plan output -->
```
terraform plan
# Plan: X to add, Y to change, Z to destroy
```

### Blast Radius
- [ ] Networking changes
- [ ] Database changes  
- [ ] Compute changes
- [ ] Application changes
- Environment(s) affected: [ ] dev [ ] staging [ ] prod

### Rollback Plan
<!-- Nếu apply fail hoặc gây issue, rollback thế nào -->

### Checklist
- [ ] Plan reviewed — no unexpected destroys
- [ ] No hardcoded secrets
- [ ] Tags/labels present
- [ ] Security groups minimal
- [ ] Cost impact assessed
- [ ] Downtime impact: None / Brief / Extended
- [ ] Backup verified (if database change)
```

</details>

---

## Exercise 3: Hard — Production IaC Migration Plan

### Context

Bạn được thuê làm DevOps consultant cho một company đang chạy production infrastructure hoàn toàn bằng console clicks (ClickOps). Hệ thống gồm:

- 3 VPCs (dev, staging, prod)
- 2 EKS clusters (staging, prod)
- 5 RDS instances
- 10+ S3 buckets
- 20+ security groups
- IAM roles/policies
- Route 53 DNS records
- CloudFront distributions

Team: 30 engineers, 3 DevOps engineers. Budget: vừa phải.

### Yêu cầu

1. **Viết migration plan** từ ClickOps sang IaC:
   - Phase breakdown (ít nhất 4 phases)
   - Timeline cho mỗi phase
   - Risk assessment cho mỗi phase
   - Rollback plan cho mỗi phase
   - Success metrics

2. **Thiết kế repository structure** cho IaC:
   - Directory layout
   - Module strategy
   - Environment strategy
   - State split strategy

3. **Viết import strategy**:
   - Priority order (import resource nào trước)
   - Verification process sau khi import
   - Handling resources không thể import

4. **Thiết kế governance framework**:
   - Who can plan/apply
   - Review process
   - Emergency change process
   - Drift handling policy
   - Training plan cho team

### Expected Outcome

- Migration plan document (4+ phases, timeline, risks).
- Repository structure diagram.
- Import strategy với priority matrix.
- Governance document.

### Hint

- Import order: read-only resources trước (VPC, subnets), stateful resources (database) cẩn thận nhất.
- Phase 1 nên là non-critical environment (dev) để team học.
- Không import tất cả 1 lần — incremental migration an toàn hơn.

### Acceptance Criteria

- [ ] Migration plan có ít nhất 4 phases với timeline
- [ ] Mỗi phase có risk assessment và rollback plan
- [ ] Repository structure hợp lý, scalable
- [ ] Import strategy có priority matrix
- [ ] Governance cover: access, review, emergency, drift
- [ ] Plan phù hợp team 3 DevOps + 30 engineers

### Bonus Challenge

Viết workflow import mẫu cho 3 resource types (VPC, security group, RDS). Ưu tiên **configuration-driven import** bằng `import` block để review trong PR/CI; chỉ dùng `terraform import <resource_address> <resource_id>` cho break-glass hoặc migration thủ công có kiểm soát.

<details>
<summary>Solution</summary>

**1. Migration Plan:**

```markdown
# ClickOps to IaC Migration Plan

## Phase 1: Foundation (Week 1-2)
- Set up IaC repository + CI/CD pipeline
- Configure remote state backend (S3 + DynamoDB)
- Install tools, configure access
- Import DEV VPC + subnets (low risk, learning)
- Risk: LOW — dev environment only
- Rollback: Delete state, continue manual
- Metrics: Team can run plan/apply on dev VPC

## Phase 2: Dev Environment (Week 3-5)
- Import remaining dev resources (EKS, S3, SGs)
- Write modules for networking, compute, storage
- Establish PR review process
- Risk: MEDIUM — some resources may need recreation
- Rollback: Remove from state, continue manual
- Metrics: 100% dev infra in IaC, no drift for 1 week

## Phase 3: Staging (Week 6-8)
- Apply modules to staging (reuse dev modules)
- Import staging EKS, RDS, S3
- Validate HA, backup configs via IaC
- Risk: MEDIUM-HIGH — staging may serve QA/demo
- Rollback: Remove from state, document manual config
- Metrics: staging matches dev in IaC coverage

## Phase 4: Production (Week 9-12)
- Import prod VPC, networking (READ-ONLY first)
- Import prod EKS, RDS (CRITICAL — extra review)
- Import DNS, CDN, IAM
- Enable drift detection
- Risk: HIGH — production impact possible
- Rollback: terraform state rm, manual management
- Metrics: 100% prod in IaC, weekly drift check clean

## Phase 5: Optimization (Week 13-16)
- Consolidate modules, add tests
- Implement policy-as-code (OPA/Sentinel)
- Training workshops for all engineers
- Document runbooks
- Risk: LOW — improvement, not migration
- Metrics: DORA metrics improved, 0 console changes
```

**2. Repository Structure:**

```
infra-platform/
├── modules/
│   ├── networking/          # VPC, subnets, NAT, SG
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── README.md
│   ├── kubernetes/          # EKS cluster, node groups
│   ├── database/            # RDS instances
│   ├── storage/             # S3 buckets
│   ├── dns/                 # Route 53
│   ├── cdn/                 # CloudFront
│   └── iam/                 # IAM roles, policies
├── environments/
│   ├── dev/
│   │   ├── networking/      # State: dev-networking
│   │   ├── kubernetes/      # State: dev-kubernetes
│   │   └── application/     # State: dev-application
│   ├── staging/
│   │   ├── networking/
│   │   ├── kubernetes/
│   │   ├── database/
│   │   └── application/
│   └── prod/
│       ├── networking/      # State: prod-networking
│       ├── kubernetes/      # State: prod-kubernetes
│       ├── database/        # State: prod-database (separate!)
│       ├── application/     # State: prod-application
│       └── global/          # State: prod-global (DNS, CDN, IAM)
├── policies/                # OPA/Sentinel rules
├── scripts/                 # Import scripts, helpers
├── .github/workflows/       # CI/CD
└── README.md
```

**3. Import Priority Matrix:**

| Priority | Resource Type | Risk | Reason |
|----------|--------------|------|--------|
| 1 | VPC, Subnets | LOW | Read-heavy, rarely changed |
| 2 | Security Groups | LOW-MED | Rules may need cleanup |
| 3 | S3 Buckets | LOW | Stateless config |
| 4 | IAM Roles | MEDIUM | Policy accuracy critical |
| 5 | EKS Cluster | MEDIUM | Complex, many attributes |
| 6 | Route 53 | MEDIUM | DNS changes = outage risk |
| 7 | CloudFront | MEDIUM | Cache invalidation concern |
| 8 | RDS Instances | HIGH | Data at risk, import carefully |

**4. Configuration-driven import workflow:**

```hcl
# imports.tf
import {
  to = module.networking.aws_vpc.main
  id = "vpc-0123456789abcdef0"
}

import {
  to = module.networking.aws_security_group.web
  id = "sg-0123456789abcdef0"
}

import {
  to = module.database.aws_db_instance.main
  id = "prod-db-01"
}
```

```bash
terraform init
terraform plan -generate-config-out=generated-import.tf
# Review generated-import.tf, move clean HCL vào module tương ứng.
terraform plan -out=reviewed-import.tfplan
terraform apply reviewed-import.tfplan
terraform plan -detailed-exitcode
```

**5. Script verify cho traditional import (fallback thủ công):**

```bash
#!/bin/bash
# import-and-verify.sh

RESOURCE_TYPE=$1
RESOURCE_ID=$2
TF_ADDRESS=$3

echo "=== Importing $RESOURCE_TYPE: $RESOURCE_ID ==="

# Step 1: Import
terraform import "$TF_ADDRESS" "$RESOURCE_ID"

# Step 2: Plan (should show no changes)
terraform plan -detailed-exitcode
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Import clean — no changes needed"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "⚠️  Import has drift — review plan output"
    echo "Fix HCL to match actual state, then re-run"
else
    echo "❌ Import failed"
    exit 1
fi
```

**4. Governance Framework:**

```markdown
# IaC Governance

## Access Control
- Plan: Any engineer (read-only)
- Apply DEV: DevOps team (auto after PR merge)  
- Apply STAGING: DevOps team (manual approve)
- Apply PROD: Senior DevOps + Team Lead (2 approvals)

## Review Process
- All changes via PR (no direct apply)
- 1 reviewer for dev, 2 for staging/prod
- Plan output posted as PR comment (auto by CI)
- Security review for IAM/SG/NetworkPolicy changes

## Emergency Process
- On-call DevOps can apply without PR
- Must create retroactive PR within 24h
- Incident channel notification required
- Post-incident: convert manual fix to IaC

## Drift Policy
- Weekly drift check (CI scheduled job)
- Drift = P2 ticket, fix within 1 sprint
- Repeated drift on same resource = investigate root cause
- Console access audit monthly
```

</details>

