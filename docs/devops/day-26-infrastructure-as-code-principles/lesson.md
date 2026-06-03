# Day 26: Infrastructure as Code Principles

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. Phân biệt được **declarative** vs **imperative** approach và giải thích khi nào dùng cách nào.
2. Giải thích được **state management**, **desired state**, **drift detection** và vì sao chúng quan trọng trong production.
3. Thiết kế được **IaC workflow** hoàn chỉnh: từ code → review → plan → apply → verify.
4. Viết được pseudo-IaC cho một hệ thống gồm network, cluster, database, container registry.
5. Tạo được **IaC pull request review checklist** phù hợp cho team engineering.

---

## 2. Bối cảnh & Động lực

### Vì sao Infrastructure as Code quan trọng?

Bạn đã hoàn thành Phase 3 — biết cách deploy, scale, secure và debug Kubernetes workloads. Nhưng ai tạo ra cluster đó? Ai tạo network, database, load balancer, DNS records? Nếu câu trả lời là "click trên console" hoặc "chạy script một lần", thì bạn đang đối mặt với **infrastructure debt**.

**Vấn đề thực tế:**

```
Thứ 2: DevOps engineer tạo VPC trên AWS console
Thứ 3: Thêm security group, quên document
Thứ 4: Sửa route table, không ai biết
Thứ 5: Production incident — không ai nhớ config ban đầu
Thứ 6: Rebuild mất 8 giờ vì không có bản ghi
```

**IaC giải quyết:**

- **Reproducibility**: tái tạo toàn bộ infrastructure từ code.
- **Version control**: mọi thay đổi đều qua Git, có history, có reviewers.
- **Automation**: plan → apply tự động, giảm human error.
- **Documentation**: code chính là documentation — luôn up-to-date.
- **Collaboration**: nhiều người cùng làm việc trên infrastructure, không conflict.

### Liên hệ với developer

| Developer concept | IaC equivalent |
|---|---|
| Source code | Infrastructure definitions |
| Database migration | State management |
| Code review (PR) | Plan review |
| Unit test | Policy test, plan validation |
| Deployment pipeline | Apply pipeline |
| Rollback | `terraform plan` → revert commit → apply |

---

## 3. Kiến thức nền tảng

### Declarative vs Imperative

**Imperative** — bạn mô tả **từng bước** để đạt kết quả:

```bash
# Imperative: script tạo server
aws ec2 run-instances --image-id ami-xxx --instance-type t3.medium
aws ec2 create-tags --resources i-xxx --tags Key=Name,Value=web-server
aws ec2 create-security-group --group-name web-sg --description "Web SG"
aws ec2 authorize-security-group-ingress --group-name web-sg --protocol tcp --port 443
```

Vấn đề: chạy lần 2 → tạo thêm 1 server nữa. Không idempotent.

**Declarative** — bạn mô tả **trạng thái mong muốn**, tool tự tìm cách đạt được:

```hcl
# Declarative: Terraform
resource "aws_instance" "web" {
  ami           = "ami-xxx"
  instance_type = "t3.medium"
  tags = { Name = "web-server" }
}

resource "aws_security_group" "web" {
  name = "web-sg"
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Chạy lần 2 → không thay đổi gì. **Idempotent**.

### Analogy cho developer

```
Imperative = jQuery:   $("button").click(function() { ... })
Declarative = React:   <Button onClick={handleClick} />

Imperative = SQL DML:  INSERT INTO servers VALUES (...)
Declarative = Schema:  CREATE TABLE IF NOT EXISTS servers (...)
```

### Desired State & Reconciliation

IaC tools hoạt động theo pattern **desired state reconciliation** — giống hệt Kubernetes controller:

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Desired     │     │   IaC Tool   │     │   Actual     │
│ State       │────>│   (diff)     │────>│   State      │
│ (code)      │     │              │     │   (cloud)    │
└─────────────┘     └──────────────┘     └──────────────┘
                           │
                     ┌─────┴─────┐
                     │   Plan    │
                     │ (changes) │
                     └───────────┘
```

1. Tool đọc **desired state** từ code.
2. Tool đọc **actual state** từ cloud/infra.
3. Tool tính **diff** (plan).
4. User review plan.
5. Tool **apply** changes để actual state = desired state.

### State Management

**State file** là "bộ nhớ" của IaC tool — nó lưu mapping giữa resources trong code và resources thật trên cloud.

```
┌──────────────────────────────────────────────────┐
│                  State File                       │
│                                                   │
│  resource "aws_instance" "web"                    │
│    → maps to → i-0abc123def456 (EC2 instance)    │
│                                                   │
│  resource "aws_s3_bucket" "data"                  │
│    → maps to → my-app-data-bucket (S3)           │
│                                                   │
│  Contains: IDs, attributes, dependencies,         │
│            metadata, sensitive values              │
└──────────────────────────────────────────────────┘
```

**Vì sao state quan trọng:**

- Không có state → tool không biết resource nào đã tồn tại → tạo duplicate.
- State chứa **sensitive data** (passwords, keys) → phải bảo vệ.
- State bị corrupt → phải import lại từng resource.
- Nhiều người cùng modify state → **state locking** cần thiết.

### Drift

**Drift** xảy ra khi actual state khác desired state — ai đó sửa infrastructure bằng tay (click console, chạy CLI trực tiếp).

```
Code says:           instance_type = "t3.medium"
Cloud reality:       instance_type = "t3.xlarge"
                     ↑ ai đó resize bằng console
```

Drift nguy hiểm vì:

- Plan tiếp theo sẽ **revert** thay đổi thủ công → có thể gây outage.
- Hoặc mọi người ignore drift → code không còn reflect reality.
- Cả hai đều dẫn đến **mất niềm tin vào IaC**.

### Idempotency

**Idempotent** = chạy nhiều lần, kết quả giống nhau. Đây là property quan trọng nhất của IaC.

```bash
# Idempotent (declarative):
terraform apply    # Lần 1: tạo 3 resources
terraform apply    # Lần 2: "No changes needed" ✅

# NON-idempotent (imperative):
bash create.sh     # Lần 1: tạo 3 resources
bash create.sh     # Lần 2: tạo thêm 3 resources ❌
```

---

## 4. Deep Dive

### IaC Landscape

```
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure as Code                     │
│                                                               │
│  ┌───────────────────────┐  ┌───────────────────────────┐    │
│  │   PROVISIONING        │  │   CONFIGURATION MGMT      │    │
│  │   (Tạo infrastructure)│  │   (Config trên machines)  │    │
│  │                       │  │                           │    │
│  │  • Terraform          │  │  • Ansible                │    │
│  │  • Pulumi             │  │  • Chef                   │    │
│  │  • AWS CDK            │  │  • Puppet                 │    │
│  │  • Crossplane         │  │  • Salt                   │    │
│  └───────────────────────┘  └───────────────────────────┘    │
│                                                               │
│  ┌───────────────────────┐  ┌───────────────────────────┐    │
│  │   KUBERNETES CONFIG   │  │   GITOPS DELIVERY         │    │
│  │                       │  │                           │    │
│  │  • Helm               │  │  • ArgoCD                 │    │
│  │  • Kustomize          │  │  • Flux                   │    │
│  │  • Jsonnet            │  │  • Jenkins X              │    │
│  └───────────────────────┘  └───────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Plan/Apply Lifecycle chi tiết

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│  Write  │───>│  Review  │───>│   Plan   │───>│ Approve │───>│  Apply   │
│  Code   │    │   (PR)   │    │  (diff)  │    │ (human) │    │ (change) │
└─────────┘    └──────────┘    └──────────┘    └─────────┘    └──────────┘
     │              │               │               │              │
     │         Code review     Dry run          Manual          Execute
     │         + policy        preview          gate            changes
     │         checks                                              │
     │                                                             │
     │              ┌──────────┐                              ┌────┴────┐
     └──────────────│  Verify  │<─────────────────────────────│  Store  │
                    │  (test)  │                               │  State  │
                    └──────────┘                               └─────────┘
```

**Mỗi bước trong lifecycle:**

| Step | Mục đích | Tool/Process |
|------|----------|-------------|
| Write | Mô tả desired state | Editor + HCL/YAML |
| Review | Peer review thay đổi | GitHub PR + policy checks |
| Plan | Preview changes | `terraform plan` |
| Approve | Human verification | Manual approval gate |
| Apply | Execute changes | `terraform apply` |
| Store State | Lưu mapping | Remote state backend |
| Verify | Confirm success | Smoke test, health check |

### Git as Source of Truth

```
┌─────────────────────────────────────────────────┐
│                Git Repository                     │
│                                                   │
│  infrastructure/                                  │
│  ├── modules/                                     │
│  │   ├── networking/   # VPC, subnets, SG        │
│  │   ├── compute/      # EC2, ASG, LB            │
│  │   ├── database/     # RDS, ElastiCache        │
│  │   └── kubernetes/   # EKS, node groups        │
│  ├── environments/                                │
│  │   ├── dev/          # Dev config              │
│  │   ├── staging/      # Staging config          │
│  │   └── prod/         # Production config       │
│  ├── policies/         # OPA/Sentinel policies   │
│  └── README.md                                    │
│                                                   │
│  Every change:                                    │
│  1. Branch + commit                               │
│  2. PR + review                                   │
│  3. CI runs plan + policy check                   │
│  4. Merge = approved for apply                    │
│  5. CD runs apply                                 │
└─────────────────────────────────────────────────┘
```

### IaC Review Process

Code review cho IaC khác với application code review:

```
Application Code Review:        IaC Code Review:
┌────────────────────┐          ┌────────────────────────┐
│ Logic đúng?        │          │ Plan output hợp lý?    │
│ Tests pass?        │          │ Có destroy resource?   │
│ Performance?       │          │ Security groups OK?    │
│ Error handling?    │          │ Cost impact?           │
│ Code style?        │          │ Blast radius?          │
└────────────────────┘          │ Rollback plan?         │
                                │ Downtime required?     │
                                │ State migration?       │
                                └────────────────────────┘
```

---

## 5. Trade-offs & Best Practices ⭐

### Declarative vs Imperative

| Criteria | Declarative | Imperative |
|----------|------------|------------|
| Idempotency | Tự động | Phải tự implement |
| Learning curve | Cần học DSL mới | Dùng ngôn ngữ quen |
| Flexibility | Hạn chế bởi DSL | Không giới hạn |
| State mgmt | Tool quản lý | Tự quản lý |
| Debugging | Xem plan/state | Debug script |
| Parallelism | Tool tối ưu | Tự quản lý |
| Best for | Infrastructure provisioning | Complex orchestration |

### Khi nào viết IaC, khi nào dùng Console?

**Luôn dùng IaC:**
- Production infrastructure
- Shared resources (VPC, DNS, database)
- Security-sensitive resources (IAM, security groups)
- Resources cần reproduced (multi-env, DR)

**Có thể dùng Console:**
- Prototype/exploration ban đầu (rồi import vào IaC)
- One-time debugging tasks
- Personal sandbox (dev account riêng)

**Không bao giờ:**
- Modify production bằng console rồi "sync lại sau"
- Mix console + IaC cho cùng resource

### Best Practices theo Company Size

| Practice | Startup (5 eng) | Mid-size (30 eng) | Enterprise (200+ eng) |
|----------|-----------------|--------------------|-----------------------|
| State backend | S3/GCS | S3/GCS + locking | Terraform Cloud/Enterprise |
| Review process | 1 reviewer | 2 reviewers + plan check | Review + policy + cost gate |
| Module strategy | Inline, ít module | Shared modules repo | Versioned module registry |
| Environment | 2 (dev/prod) | 3 (dev/staging/prod) | N environments + sandbox |
| Drift detection | Manual monthly | Weekly CI job | Real-time monitoring |
| Policy | Manual review | Basic OPA/Sentinel | Full policy framework |

### Anti-patterns cần tránh

1. **ClickOps + IaC hybrid**: Một resource vừa quản lý bởi console vừa bởi IaC → drift liên tục.
2. **Monolith state**: Toàn bộ infrastructure trong 1 state file → plan chậm, blast radius lớn.
3. **No review for IaC**: Apply trực tiếp không qua PR → giống push to main without review.
4. **Ignoring plan output**: Auto-approve plan → `terraform destroy` by accident.
5. **State file in Git**: State chứa secrets → commit vào Git = leak credentials.
6. **Copy-paste environments**: Duplicate code cho dev/staging/prod → drift giữa environments.

---

## 6. Performance & Scalability ⭐

### Performance Implications

| Factor | Impact | Mitigation |
|--------|--------|------------|
| State file size | Plan chậm khi state lớn | Split state theo blast radius; chỉ dùng `-target` cho debugging/recovery có review |
| API rate limits | Cloud provider throttle | Parallelism config, retry |
| Network latency | Remote state access chậm | State caching, regional backend |
| Module count | Init chậm do download | Module caching, vendoring |
| Plan computation | CPU/memory intensive with large infra | Incremental planning |

### Scaling IaC

**Giai đoạn 1: Single team (1-10 resources)**
```
infrastructure/
└── main.tf          # Tất cả trong 1 file
```

**Giai đoạn 2: Growing team (10-50 resources)**
```
infrastructure/
├── networking.tf
├── compute.tf
├── database.tf
└── variables.tf
```

**Giai đoạn 3: Multiple teams (50-200 resources)**
```
infrastructure/
├── networking/      # Team Infra owns
├── compute/         # Team Platform owns
├── database/        # Team Data owns
└── modules/         # Shared modules
```

**Giai đoạn 4: Enterprise (200+ resources)**
```
infrastructure/
├── modules/         # Versioned, published to registry
├── platform/        # Platform team
├── team-a/          # Team A self-service
├── team-b/          # Team B self-service
├── policies/        # Security team
└── pipelines/       # CI/CD definitions
```

### Bottleneck thường gặp

1. **State locking contention**: Nhiều người apply cùng lúc → waiting for lock.
2. **Large plan time**: 500+ resources → plan mất 5-10 phút.
3. **API rate limiting**: Terraform gọi quá nhiều API calls → 429 errors.
4. **Module download**: Private module registry chậm → init timeout.

---

## 7. Security & Reliability Considerations

### Security Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| State chứa secrets | Credentials leak | Encrypt state at rest, strict access |
| Over-permissioned IaC role | Blast radius lớn | Least privilege IAM cho IaC |
| No PR review | Unauthorized changes | Branch protection + mandatory review |
| Hardcoded secrets trong code | Git history leak | Use variables, Vault, ENV vars |
| Shared credentials | No audit trail | Per-user credentials, OIDC |

### Reliability Patterns

**Blast radius control:**
```
# BAD: Một state quản lý tất cả
infrastructure/
└── main.tf    # VPC + EKS + RDS + S3 + IAM = 💥 blast radius lớn

# GOOD: Tách theo blast radius
infrastructure/
├── networking/    # Ít thay đổi, impact lớn
├── data/          # Database, ít thay đổi
├── compute/       # EKS, thay đổi TB
└── application/   # App resources, thay đổi thường xuyên
```

**Rollback strategy:**
- IaC rollback = revert commit + apply previous version.
- Nhưng: một số changes không thể rollback (database deletion, DNS propagation).
- Always check: "Nếu apply fail giữa chừng, state có consistent không?"

### State File Protection

```
# Minimum security cho state:
1. Encryption at rest (S3 SSE, GCS encryption)
2. Encryption in transit (HTTPS)
3. Access control (IAM policy, bucket policy)
4. Versioning (S3 versioning - rollback state)
5. Locking (DynamoDB, GCS locking)
6. Audit logging (CloudTrail, audit logs)
```

---

## 8. Hands-on Example

### Pseudo-IaC: Thiết kế infrastructure cho E-commerce Platform

Tạo file mô tả infrastructure bằng pseudo-IaC (giống Terraform syntax nhưng không cần cloud account).

#### Bước 1: Tạo project structure

```bash
mkdir -p iac-demo/{modules,environments/{dev,staging,prod}}
cd iac-demo
```

#### Bước 2: Viết pseudo-IaC cho hệ thống

**modules/networking/main.pseudo-tf**
```hcl
# Network layer - thay đổi ít, blast radius lớn
resource "cloud_vpc" "main" {
  name       = "${var.project}-${var.environment}-vpc"
  cidr_block = var.vpc_cidr

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Team        = "platform"
  }
}

resource "cloud_subnet" "private" {
  count      = length(var.availability_zones)
  vpc_id     = cloud_vpc.main.id
  cidr_block = cidrsubnet(var.vpc_cidr, 8, count.index)
  az         = var.availability_zones[count.index]
  type       = "private"
}

resource "cloud_subnet" "public" {
  count      = length(var.availability_zones)
  vpc_id     = cloud_vpc.main.id
  cidr_block = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  az         = var.availability_zones[count.index]
  type       = "public"
}

resource "cloud_nat_gateway" "main" {
  subnet_id = cloud_subnet.public[0].id
}
```

**modules/kubernetes/main.pseudo-tf**
```hcl
# Kubernetes cluster - thay đổi ít-trung bình
resource "cloud_kubernetes_cluster" "main" {
  name       = "${var.project}-${var.environment}"
  version    = var.k8s_version
  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  node_groups = {
    general = {
      instance_type = var.node_instance_type
      min_size      = var.node_min_count
      max_size      = var.node_max_count
      disk_size_gb  = 100
    }
  }

  addons = {
    coredns    = { enabled = true }
    kube_proxy = { enabled = true }
    cni        = { enabled = true }
  }

  logging = {
    api_server         = true
    controller_manager = true
    scheduler          = true
    audit              = true
  }
}
```

**modules/database/main.pseudo-tf**
```hcl
# Database layer - thay đổi ít, data critical
resource "cloud_database" "main" {
  engine         = "postgresql"
  engine_version = "15"
  instance_class = var.db_instance_class
  
  storage = {
    size_gb   = var.db_storage_size
    type      = "ssd"
    encrypted = true
  }

  high_availability = {
    enabled = var.environment == "prod" ? true : false
    standby_az = var.availability_zones[1]
  }

  backup = {
    enabled             = true
    retention_days      = var.environment == "prod" ? 30 : 7
    window              = "03:00-04:00"
    cross_region_backup = var.environment == "prod" ? true : false
  }

  networking = {
    vpc_id     = var.vpc_id
    subnet_ids = var.private_subnet_ids
    publicly_accessible = false
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    DataClass   = "sensitive"
  }
}
```

**modules/registry/main.pseudo-tf**
```hcl
# Container registry
resource "cloud_container_registry" "main" {
  name = "${var.project}-${var.environment}"
  
  image_scanning = {
    enabled  = true
    on_push  = true
  }

  lifecycle_policy = {
    untagged_expiry_days = 7
    keep_last_n_tagged   = 20
  }

  encryption = {
    enabled = true
  }

  replication = var.environment == "prod" ? {
    regions = var.replica_regions
  } : null
}
```

**environments/prod/main.pseudo-tf**
```hcl
# Production environment composition
module "networking" {
  source = "../../modules/networking"
  
  project            = "ecommerce"
  environment        = "prod"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["az-1", "az-2", "az-3"]
}

module "kubernetes" {
  source = "../../modules/kubernetes"
  
  project            = "ecommerce"
  environment        = "prod"
  k8s_version        = "1.29"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  node_instance_type = "m5.xlarge"
  node_min_count     = 3
  node_max_count     = 20
}

module "database" {
  source = "../../modules/database"
  
  environment        = "prod"
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  db_instance_class  = "db.r6g.xlarge"
  db_storage_size    = 500
  availability_zones = ["az-1", "az-2"]
}

module "registry" {
  source = "../../modules/registry"
  
  project         = "ecommerce"
  environment     = "prod"
  replica_regions = ["region-2"]
}
```

#### Bước 3: IaC Review Checklist

Tạo file `iac-review-checklist.md`:

```markdown
# IaC Pull Request Review Checklist

## 1. Correctness
- [ ] Plan output reviewed — no unexpected destroys
- [ ] Resource naming follows convention
- [ ] Tags/labels present (Environment, Team, ManagedBy)
- [ ] Dependencies correct (depends_on if needed)

## 2. Security
- [ ] No hardcoded secrets/credentials
- [ ] Encryption enabled (at rest + in transit)
- [ ] Network access restricted (no 0.0.0.0/0 for sensitive ports)
- [ ] IAM follows least privilege
- [ ] Security groups minimal

## 3. Reliability
- [ ] High availability configured for prod
- [ ] Backup enabled with appropriate retention
- [ ] Multi-AZ for critical resources
- [ ] Rollback plan documented

## 4. Cost
- [ ] Instance sizes appropriate for environment
- [ ] Dev/staging uses smaller resources than prod
- [ ] Auto-scaling configured (min/max reasonable)
- [ ] No forgotten resources (cleanup)

## 5. Operations
- [ ] Monitoring/alerting configured
- [ ] Logging enabled
- [ ] DNS/networking correct
- [ ] State impact understood (new state, moved, destroyed)

## 6. Blast Radius
- [ ] Changes scoped to minimum resources
- [ ] No cross-cutting changes (networking + database in same PR)
- [ ] Downtime impact assessed
- [ ] Rollback tested or documented
```

#### Expected output

```
iac-demo/
├── modules/
│   ├── networking/
│   │   └── main.pseudo-tf
│   ├── kubernetes/
│   │   └── main.pseudo-tf
│   ├── database/
│   │   └── main.pseudo-tf
│   └── registry/
│       └── main.pseudo-tf
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
│       └── main.pseudo-tf
└── iac-review-checklist.md
```

#### Verification

- Review modules: mỗi module độc lập, có variables rõ ràng.
- Review environments: prod có HA, backup cross-region, staging/dev giản lược hơn.
- Review checklist: áp dụng checklist lên chính pseudo-IaC vừa viết.

#### Cleanup

```bash
cd ..
rm -rf iac-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: State File trong Git

```
❌ git add terraform.tfstate
❌ git commit -m "add state"

# State chứa passwords, API keys, private IPs
# Git history KHÔNG XÓA được dễ dàng
```

**Fix**: Dùng remote state backend (S3, GCS, Terraform Cloud) + `.gitignore`.

### Pitfall 2: ClickOps sau khi đã có IaC

```
Timeline:
1. Terraform tạo security group: ingress port 443
2. Engineer thêm port 8080 bằng console (quên nói team)
3. Terraform plan: "Remove ingress rule port 8080"
4. Apply → service bị mất access → incident
```

**Fix**: Strict policy — no console changes cho managed resources. Drift detection weekly.

### Pitfall 3: No Plan Review

```
$ terraform apply -auto-approve    # ❌ NGUY HIỂM

# Plan có thể chứa:
# - aws_db_instance.main must be REPLACED (data loss!)
# - aws_vpc.main will be DESTROYED (toàn bộ network mất!)
```

**Fix**: Luôn review plan. CI chạy plan, human approve, CD chạy apply.

### Pitfall 4: Monolith State

```
# 1 state file quản lý:
# - VPC (thay đổi 1 lần/năm)
# - EKS cluster (thay đổi monthly)
# - App configs (thay đổi weekly)

# Vấn đề:
# - Plan mất 10 phút mỗi lần
# - Sửa app config → risk touch VPC
# - 1 người apply → block tất cả (state lock)
```

**Fix**: Split state theo blast radius và change frequency.

### Production Case Study: Terraform Destroy Incident

#### Context
Một fintech startup, 15 engineers, infrastructure quản lý bằng Terraform. Toàn bộ infrastructure trong 1 state file.

#### Symptom
Production database biến mất vào 3 giờ sáng. Tất cả services trả về 500.

#### Investigation
1. CloudTrail log: `DeleteDBInstance` called by `terraform-automation` role.
2. Git log: engineer commit thay đổi variable name cho database module.
3. Variable rename → Terraform interpret là destroy old + create new.
4. CI/CD pipeline có `auto-approve` cho nhánh `main`.

#### Root Cause
- Variable rename = resource replacement (destroy + create) trong Terraform.
- Pipeline auto-approve không có human gate.
- Backup có nhưng RTO = 4 giờ (restore from snapshot).

#### Mitigation
- Restore database từ latest snapshot (mất 2 giờ data).
- Manual data reconciliation cho 2 giờ missing transactions.

#### Long-term Fix
1. Remove `auto-approve` — plan luôn cần human approval.
2. Thêm `lifecycle { prevent_destroy = true }` cho critical resources.
3. Split state: database tách riêng khỏi application resources.
4. Thêm policy check: alert khi plan có `destroy` trên database/VPC.
5. Continuous backup với RPO = 5 phút (thay vì daily snapshot).

#### Lesson Learned
- `rename` trong IaC = `destroy + create`, không phải `rename`.
- Auto-approve là shortcut nguy hiểm nhất trong IaC.
- Critical resources cần `prevent_destroy` + separate state + backup.

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Phase 3 (Day 18-25)

- Phase 3 dạy bạn **vận hành Kubernetes**: resources, scaling, security, troubleshooting.
- Nhưng ai tạo ra cluster đó? Ai tạo VPC, load balancer, DNS? → **Phase 4 trả lời**.
- Kubernetes manifest (Day 16 Helm/Kustomize) là IaC cho application layer.
- Terraform/Pulumi là IaC cho infrastructure layer bên dưới.

### Bài sau: Day 27 — Terraform Fundamentals

- Day 26 học **principles** — tư duy, patterns, workflow.
- Day 27 sẽ apply principles vào **Terraform** — tool phổ biến nhất.
- Bạn sẽ viết HCL thật, chạy `terraform init/plan/apply` thật.

### Roadmap Phase 4

```
Day 26: IaC Principles     ← BẠN ĐANG Ở ĐÂY
Day 27: Terraform Fundamentals
Day 28: Terraform Advanced (remote state, modules, drift)
Day 29: Pulumi vs Terraform vs CDK
Day 30: Ansible for Configuration Management
Day 31: GitOps with ArgoCD & Flux
```

---

## 11. Tài liệu tham khảo

### Must-read

- [Terraform Documentation — What is Infrastructure as Code?](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/infrastructure-as-code) — Official intro từ HashiCorp.
- [Infrastructure as Code — Kief Morris (O'Reilly)](https://www.oreilly.com/library/view/infrastructure-as-code/9781098114664/) — Sách definitive về IaC patterns.
- [Google SRE Book — Chapter 8: Release Engineering](https://sre.google/sre-book/release-engineering/) — IaC trong context SRE.

### Nice-to-have

- [ThoughtWorks Technology Radar — IaC section](https://www.thoughtworks.com/radar) — Trends mới nhất.
- [Gruntwork Blog — Comprehensive Guide to Terraform](https://blog.gruntwork.io/a-comprehensive-guide-to-terraform-b3d32832baca) — Practical guide.
- [Spacelift Blog — IaC Best Practices](https://spacelift.io/blog/infrastructure-as-code-best-practices) — Production patterns.

### Deep-dive

- [Terraform: Up & Running — Yevgeniy Brikman](https://www.terraformupandrunning.com/) — Sách thực hành tốt nhất cho Terraform.
- [Pulumi Documentation — IaC Concepts](https://www.pulumi.com/docs/concepts/) — Alternative perspective từ Pulumi.
- [CNCF Landscape — Provisioning](https://landscape.cncf.io/guide#provisioning) — Toàn bộ IaC ecosystem.

