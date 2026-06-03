# Day 28: Terraform Advanced — Remote State, Locking, Modules, Drift

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. Cấu hình được **remote state** với backend (S3, GCS, local simulation) và giải thích vì sao local state không phù hợp cho team.
2. Hiểu và áp dụng được **state locking** để ngăn concurrent modifications.
3. Thiết kế và refactor code thành **Terraform modules** tái sử dụng được.
4. Phát hiện và xử lý được **drift** khi infrastructure bị modify ngoài Terraform.
5. **Import** existing resources vào Terraform state và xử lý state conflicts.

---

## 2. Bối cảnh & Động lực

### Từ cá nhân đến team

Day 27 bạn học Terraform basics với **local state** — file `terraform.tfstate` nằm trên máy bạn. Điều này hoạt động khi một mình, nhưng khi có team:

```
Vấn đề với local state:

Engineer A: terraform apply     Engineer B: terraform apply
     │                                │
     ▼                                ▼
terraform.tfstate (máy A)    terraform.tfstate (máy B)
     │                                │
     └──── DIFFERENT STATE! ──────────┘
           → Conflicts, duplicate resources, data loss
```

**Remote state giải quyết:**

```
Engineer A: terraform apply     Engineer B: terraform apply
     │                                │
     ▼                                ▼
     └──────── S3 Bucket ─────────────┘
               terraform.tfstate (SINGLE SOURCE OF TRUTH)
               + DynamoDB Lock (prevent concurrent apply)
```

### Analogy cho developer

| Local state problem | Developer equivalent |
|---|---|
| 2 người edit cùng state | 2 người edit cùng file không có Git |
| State conflict | Merge conflict |
| State locking | Database row lock / mutex |
| Remote state | Shared Git repository |
| Module | npm package / Go module |
| Drift | Someone pushes to prod without PR |

---

## 3. Kiến thức nền tảng

### Remote State

Remote state lưu `terraform.tfstate` ở shared location thay vì local filesystem:

```hcl
# Backend configuration
terraform {
  backend "s3" {
    bucket         = "my-company-terraform-state"
    key            = "prod/networking/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

**Supported backends:**

| Backend | Locking | Encryption | Best For |
|---------|---------|-----------|----------|
| local | ❌ | ❌ | Solo dev, learning |
| S3 + DynamoDB | ✅ | ✅ (SSE-S3/KMS) | AWS teams |
| GCS | ✅ (built-in) | ✅ | GCP teams |
| Azure Blob | ✅ (blob lease) | ✅ | Azure teams |
| Terraform Cloud | ✅ | ✅ | Multi-cloud, enterprise |
| Consul | ✅ | ✅ | On-premise, HashiCorp stack |
| pg (PostgreSQL) | ✅ | ❌ (app-level) | Teams with existing PG |

### State Locking

State locking ngăn 2 người chạy `terraform apply` đồng thời:

```
Engineer A: terraform apply
  1. Acquire lock → SUCCESS
  2. Read state
  3. Plan + apply
  4. Write state
  5. Release lock

Engineer B: terraform apply (CÙNG LÚC)
  1. Acquire lock → BLOCKED (waiting...)
  ...đợi A xong...
  1. Acquire lock → SUCCESS
  2. Read state (đã updated bởi A)
  3. Plan + apply
  4. Write state
  5. Release lock
```

### Modules

Module là **reusable package** của Terraform code — giống function/class trong programming:

```
modules/
├── networking/
│   ├── main.tf        # Resources: VPC, subnets, SG
│   ├── variables.tf   # Input parameters
│   ├── outputs.tf     # Return values
│   └── README.md
├── database/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── kubernetes/
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

**Sử dụng module:**

```hcl
module "prod_network" {
  source = "./modules/networking"
  
  environment = "prod"
  vpc_cidr    = "10.0.0.0/16"
  azs         = ["us-east-1a", "us-east-1b"]
}

module "prod_db" {
  source = "./modules/database"
  
  environment = "prod"
  vpc_id      = module.prod_network.vpc_id       # Output từ module khác
  subnet_ids  = module.prod_network.private_subnet_ids
}
```

### Drift Detection

Drift xảy ra khi ai đó modify infrastructure ngoài Terraform:

```bash
# Terraform nghĩ instance_type = t3.medium (state)
# Thực tế trên AWS = t3.xlarge (ai đó resize bằng console)

terraform plan
# ~ aws_instance.web
#     instance_type: "t3.xlarge" => "t3.medium"
#     ↑ Terraform sẽ REVERT về giá trị trong code
```

### Import

Import đưa existing resource vào Terraform management. Cách cũ vẫn hợp lệ:

```bash
# Resource exists trên AWS NHƯNG không trong Terraform state
terraform import aws_instance.web i-0abc123def456

# Sau import: resource có trong state
# NHƯNG bạn phải viết HCL code tương ứng thủ công
```

Trong CI/CD, ưu tiên **configuration-driven import** vì `import` block nằm trong Git, review được trong PR, và pipeline có thể chạy `terraform plan`/`apply` nhất quán:

```hcl
resource "aws_instance" "web" {
  # HCL mô tả resource hiện hữu
}

import {
  to = aws_instance.web
  id = "i-0abc123def456"
}
```

---

## 4. Deep Dive

### Module Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Root Module                          │
│                     (environments/prod/)                 │
│                                                          │
│   module "network" {          module "database" {        │
│     source = "../../modules/    source = "../../modules/ │
│              networking"                 database"       │
│     vpc_cidr = "10.0.0.0/16"   vpc_id = module.network  │
│   }                                      .vpc_id        │
│                                }                         │
│                                                          │
│   ┌─────────────┐         ┌──────────────┐              │
│   │  Networking │────────>│   Database   │              │
│   │  Module     │ vpc_id  │   Module     │              │
│   │             │         │              │              │
│   │ Variables:  │         │ Variables:   │              │
│   │  - vpc_cidr │         │  - vpc_id    │              │
│   │  - azs      │         │  - engine   │              │
│   │             │         │              │              │
│   │ Outputs:    │         │ Outputs:     │              │
│   │  - vpc_id   │         │  - endpoint  │              │
│   │  - subnets  │         │  - port      │              │
│   └─────────────┘         └──────────────┘              │
└─────────────────────────────────────────────────────────┘
```

### Environment Strategy: Workspace vs Directory

**Option 1: Workspaces** (Day 27 đã dùng)

```
infrastructure/
├── main.tf
├── variables.tf
├── dev.tfvars
├── staging.tfvars
└── prod.tfvars

# terraform workspace select prod
# terraform apply -var-file=prod.tfvars
```

Ưu điểm: ít code duplication. Nhược điểm: cùng code cho tất cả env, khó customize per-env.

**Option 2: Directory-based** (recommended cho production)

```
infrastructure/
├── modules/
│   ├── networking/
│   └── database/
├── environments/
│   ├── dev/
│   │   ├── main.tf        # Dùng modules, dev-specific config
│   │   ├── terraform.tfvars
│   │   └── backend.tf     # State riêng cho dev
│   ├── staging/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf        # Có thể dùng resources dev không có
│       ├── terraform.tfvars
│       └── backend.tf     # State riêng cho prod
```

Ưu điểm: mỗi env có config riêng, state riêng, blast radius nhỏ. Nhược điểm: potential code duplication.

### State Layout Design

```
State Split theo 2 chiều: Environment × Layer

                    dev          staging        prod
                ┌──────────┬──────────────┬──────────────┐
  networking    │ dev/net   │ staging/net  │ prod/net     │ Ít change
                ├──────────┼──────────────┼──────────────┤
  kubernetes    │          │ staging/k8s  │ prod/k8s     │ Monthly
                ├──────────┼──────────────┼──────────────┤
  database      │          │ staging/db   │ prod/db      │ Critical
                ├──────────┼──────────────┼──────────────┤
  application   │ dev/app  │ staging/app  │ prod/app     │ Frequent
                └──────────┴──────────────┴──────────────┘

S3 keys:
  s3://terraform-state/dev/networking/terraform.tfstate
  s3://terraform-state/prod/database/terraform.tfstate
  s3://terraform-state/prod/application/terraform.tfstate
```

### Drift Handling Flowchart

```
terraform plan phát hiện drift
         │
         ├── Drift nhỏ (tag thay đổi, minor setting)
         │   └── Apply để revert về desired state
         │
         ├── Drift lớn (instance type, network config)
         │   ├── Hỏi team: drift này intentional?
         │   │   ├── CÓ → Update code để match reality
         │   │   └── KHÔNG → Apply để revert
         │   └── Investigate: ai thay đổi? (CloudTrail)
         │
         └── Drift critical (resource deleted, recreated)
             ├── State có thể inconsistent
             ├── terraform state rm + re-import
             └── Hoặc recreate resource
```

---

## 5. Trade-offs & Best Practices ⭐

### Workspace vs Directory-based Environments

| Criteria | Workspaces | Directory-based |
|----------|-----------|-----------------|
| Code duplication | Minimal | Some overlap |
| Per-env customization | Limited (same code) | Full flexibility |
| Risk isolation | Same code, different state | Different code + state |
| Blast radius | Code change affects all envs | Scoped to one env |
| Complexity | Simple | More files, more structure |
| Team size | Small (1-5) | Medium-Large (5+) |
| Recommended | Learning, small projects | Production |

### Module Granularity

```
# TOO FINE — 1 resource per module ❌
module "vpc" { ... }
module "subnet_a" { ... }
module "subnet_b" { ... }
module "security_group_web" { ... }
# → Quá nhiều modules, khó manage

# TOO COARSE — everything in 1 module ❌  
module "infrastructure" { ... }  # VPC + EKS + RDS + S3 + IAM
# → Module quá lớn, khó reuse

# JUST RIGHT — logical grouping ✅
module "networking" { ... }      # VPC + subnets + NAT + SGs
module "kubernetes" { ... }      # EKS + node groups
module "database" { ... }        # RDS + parameter groups
module "monitoring" { ... }      # CloudWatch + SNS + dashboards
```

### Module Design Best Practices

```hcl
# 1. Mỗi module có README
modules/networking/README.md

# 2. Variables có description + type + validation
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Must be a valid CIDR block."
  }
}

# 3. Outputs cho TẤT CẢ values module khác cần
output "vpc_id" {
  description = "ID of the created VPC"
  value       = aws_vpc.main.id
}

# 4. Không hardcode values — tất cả configurable qua variables
# 5. Dùng locals cho computed values
# 6. Semantic versioning nếu publish module
```

### Anti-patterns

| Anti-pattern | Vấn đề | Fix |
|---|---|---|
| Monolith state | Slow plan, large blast radius | Split by env + layer |
| Module nesting sâu | Hard to debug, slow init | Max 2 levels deep |
| Circular module deps | `terraform plan` fails | Redesign module boundaries |
| Hardcoded backend | Can't reuse across envs | Use `-backend-config` |
| `terraform state push` | State corruption risk | Only for recovery |
| Workspace for prod isolation | Insufficient isolation | Directory-based |
| Provider in module | Version conflicts | Provider in root only |

---

## 6. Performance & Scalability ⭐

### Large State Performance

| State size | Resources | Plan time | Optimization |
|-----------|-----------|-----------|-------------|
| Small | < 50 | < 10s | None needed |
| Medium | 50-200 | 10-60s | Consider split |
| Large | 200-500 | 1-5 min | Must split |
| Very Large | 500+ | 5-15 min | Split + -target |

### State Split Impact

```
BEFORE (monolith): 500 resources, plan = 8 minutes
AFTER (split by layer):
  networking:  50 resources, plan = 15s
  kubernetes: 100 resources, plan = 45s  
  database:    30 resources, plan = 10s
  application: 320 resources, plan = 3 min

Total plan time: 4 min (nhưng mỗi team chỉ chạy phần của mình)
```

### Module Performance

```bash
# Module download có thể chậm
# Cache modules locally:
export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"

# Registry modules vs local modules
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"  # Download từ registry
  version = "5.0.0"
}

module "vpc" {
  source = "../../modules/networking"  # Local, không download
}
```

---

## 7. Security & Reliability Considerations

### State File Security

```
State file chứa:
├── Resource IDs (EC2 instance IDs, ARNs)
├── Resource attributes (IP addresses, DNS names)  
├── Sensitive values:
│   ├── Database passwords
│   ├── API keys  
│   ├── TLS private keys
│   └── OAuth tokens
└── Connection strings

PHẢI:
✅ Encrypt state at rest (S3 SSE, KMS)
✅ Encrypt in transit (HTTPS)
✅ Restrict access (IAM policy)  
✅ Enable versioning (rollback)
✅ Enable logging (audit trail)
✅ State locking (prevent corruption)

KHÔNG ĐƯỢC:
❌ Commit state to Git
❌ Share state file qua email/Slack
❌ Store state trên shared drive không encrypt
```

### Module Security

```hcl
# Pin module versions — KHÔNG dùng "latest"
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.5.1"  # ✅ Pinned version

  # source = "terraform-aws-modules/vpc/aws"  # ❌ Latest = unpredictable
}

# Verify module source
# ✅ Official HashiCorp modules
# ✅ Well-known community modules (terraform-aws-modules)
# ⚠️  Random GitHub repos — review code first
# ❌ Unverified sources
```

### Import Security Considerations

```bash
# Import reads real infrastructure → state chứa real values
# Ví dụ: import RDS → state chứa master password

# Sau import, mark sensitive:
output "db_password" {
  value     = aws_db_instance.main.password
  sensitive = true
}

# Và restrict state access ngay lập tức
```

---

## 8. Hands-on Example

### Project: Refactor Terraform Code thành Modules + Simulate Drift

Bài này dùng Docker provider — không cần cloud account.

#### Bước 1: Tạo project structure

```bash
mkdir -p terraform-advanced-demo/{modules/{webserver,cache},environments/{dev,prod}}
cd terraform-advanced-demo
```

#### Bước 2: Tạo webserver module

**modules/webserver/main.tf**
```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

resource "docker_image" "nginx" {
  name         = "nginx:${var.nginx_version}"
  keep_locally = false
}

resource "docker_container" "web" {
  count = var.replicas

  name  = "${var.name_prefix}-web-${count.index}"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = var.base_port + count.index
  }

  networks_advanced {
    name = var.network_name
  }

  upload {
    content = <<-EOT
      server {
        listen 80;
        location / {
          return 200 "Service: ${var.name_prefix}\nInstance: ${count.index}\nEnvironment: ${var.environment}\n";
          add_header Content-Type text/plain;
        }
        location /health {
          access_log off;
          return 200 "healthy\n";
        }
      }
    EOT
    file = "/etc/nginx/conf.d/default.conf"
  }

  restart  = "unless-stopped"
  must_run = true

  labels {
    label = "managed-by"
    value = "terraform"
  }
  labels {
    label = "environment"
    value = var.environment
  }
  labels {
    label = "module"
    value = "webserver"
  }
}
```

**modules/webserver/variables.tf**
```hcl
variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "nginx_version" {
  description = "NGINX image tag"
  type        = string
  default     = "alpine"
}

variable "replicas" {
  description = "Number of web server instances"
  type        = number
  default     = 1

  validation {
    condition     = var.replicas >= 1 && var.replicas <= 10
    error_message = "Replicas must be between 1 and 10."
  }
}

variable "base_port" {
  description = "Starting external port"
  type        = number
}

variable "network_name" {
  description = "Docker network to join"
  type        = string
}
```

**modules/webserver/outputs.tf**
```hcl
output "container_names" {
  description = "Names of created containers"
  value       = docker_container.web[*].name
}

output "container_ids" {
  description = "IDs of created containers"
  value       = docker_container.web[*].id
}

output "urls" {
  description = "Access URLs"
  value       = [for i in range(var.replicas) : "http://localhost:${var.base_port + i}"]
}
```

#### Bước 3: Tạo cache module

**modules/cache/main.tf**
```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

resource "docker_image" "redis" {
  name         = "redis:${var.redis_version}"
  keep_locally = false
}

resource "docker_container" "redis" {
  name  = "${var.name_prefix}-redis"
  image = docker_image.redis.image_id

  command = ["redis-server", "--maxmemory", var.maxmemory, "--maxmemory-policy", "allkeys-lru"]

  ports {
    internal = 6379
    external = var.port
  }

  networks_advanced {
    name = var.network_name
  }

  healthcheck {
    test     = ["CMD", "redis-cli", "ping"]
    interval = "10s"
    timeout  = "5s"
    retries  = 3
  }

  restart  = "unless-stopped"
  must_run = true

  labels {
    label = "managed-by"
    value = "terraform"
  }
  labels {
    label = "environment"
    value = var.environment
  }
  labels {
    label = "module"
    value = "cache"
  }
}
```

**modules/cache/variables.tf**
```hcl
variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "redis_version" {
  description = "Redis image tag"
  type        = string
  default     = "7-alpine"
}

variable "maxmemory" {
  description = "Redis max memory"
  type        = string
  default     = "64mb"
}

variable "port" {
  description = "External port for Redis"
  type        = number
}

variable "network_name" {
  description = "Docker network to join"
  type        = string
}
```

**modules/cache/outputs.tf**
```hcl
output "container_name" {
  value = docker_container.redis.name
}

output "container_id" {
  value = docker_container.redis.id
}

output "endpoint" {
  value = "localhost:${var.port}"
}
```

#### Bước 4: Tạo dev environment

**environments/dev/main.tf**
```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

locals {
  environment = "dev"
  project     = "tf-advanced"
  name_prefix = "${local.project}-${local.environment}"
}

resource "docker_network" "main" {
  name = "${local.name_prefix}-network"
}

module "webserver" {
  source = "../../modules/webserver"

  name_prefix   = local.name_prefix
  environment   = local.environment
  replicas      = 1
  base_port     = 8080
  network_name  = docker_network.main.name
}

module "cache" {
  source = "../../modules/cache"

  name_prefix  = local.name_prefix
  environment  = local.environment
  maxmemory    = "32mb"
  port         = 6380
  network_name = docker_network.main.name
}

output "web_urls" {
  value = module.webserver.urls
}

output "redis_endpoint" {
  value = module.cache.endpoint
}

output "environment" {
  value = local.environment
}
```

#### Bước 5: Deploy và Test

```bash
cd environments/dev

# Initialize
terraform init

# Plan
terraform plan
# Expected: 5 to add (network, 2 images, 2 containers)

# Apply
terraform apply -auto-approve

# Verify
curl http://localhost:8080
# Service: tf-advanced-dev
# Instance: 0
# Environment: dev

# Check state
terraform state list
# docker_network.main
# module.cache.docker_container.redis
# module.cache.docker_image.redis
# module.webserver.docker_container.web[0]
# module.webserver.docker_image.nginx

# Show module output
terraform output
```

#### Bước 6: Simulate Drift

```bash
# Giả lập drift: ai đó rename container bằng CLI
docker rename tf-advanced-dev-web-0 tf-advanced-dev-web-MANUAL

# Kiểm tra drift
terraform plan
# Terraform sẽ phát hiện container không còn match state
# Plan sẽ đề xuất recreate/fix

# Fix drift
terraform apply -auto-approve
# Terraform sẽ restore container về đúng state
```

#### Bước 7: Thử import

```bash
# Tạo container bằng tay (ngoài Terraform)
docker run -d --name tf-advanced-dev-extra --network tf-advanced-dev-network nginx:alpine

# Container này không trong Terraform state
terraform state list  # không có "extra"

# Viết HCL cho resource mới (thêm vào main.tf):
cat >> main.tf << 'EOF'

resource "docker_container" "extra" {
  name     = "tf-advanced-dev-extra"
  image    = "nginx:alpine"
  must_run = true

  networks_advanced {
    name = docker_network.main.name
  }
}
EOF

# Import bằng configuration-driven import để review được trong Git
docker inspect tf-advanced-dev-extra --format '{{.ID}}'
# Output: abc123...

cat >> imports.tf << 'EOF'

import {
  to = docker_container.extra
  id = "<container_id_from_previous_command>"
}
EOF

# Verify
terraform plan -out=import-extra.tfplan
terraform apply import-extra.tfplan
terraform plan  # Nên hiển thị no changes sau khi HCL khớp thực tế
```

#### Cleanup

```bash
terraform destroy -auto-approve
docker rm -f tf-advanced-dev-extra 2>/dev/null
cd ../..
rm -rf terraform-advanced-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: State Lock Stuck

```
Error: Error acquiring the state lock
Lock Info:
  ID:        xxxxxxxx-xxxx-xxxx
  Operation: OperationTypeApply
  Who:       engineer@laptop
  Created:   2024-01-15 10:30:00
```

**Nguyên nhân:** Engineer apply bị crash, process bị kill, network disconnect.

**Fix:**
```bash
# Kiểm tra: có ai THỰC SỰ đang apply không?
# Nếu CHẮC CHẮN không:
terraform force-unlock xxxxxxxx-xxxx-xxxx

# ⚠️ KHÔNG force-unlock khi ai đó đang apply → state corruption
```

### Pitfall 2: Module Version Drift

```
# Team member A dùng module version 1.0
# Team member B update module lên 2.0 (breaking change)
# A chạy terraform apply → unexpected changes/errors
```

**Fix:** Pin module versions, dùng `.terraform.lock.hcl`, version constraints.

### Pitfall 3: State Move sau Refactor

```hcl
# TRƯỚC:
resource "docker_container" "web" { ... }

# SAU (refactor vào module):
module "webserver" {
  source = "./modules/webserver"
}

# terraform plan → DESTROY docker_container.web + CREATE module.webserver.docker_container.web
# → DOWNTIME!
```

**Fix:**
```bash
# Move resource trong state thay vì destroy+create
terraform state mv docker_container.web module.webserver.docker_container.web
# terraform plan → "No changes" ✅
```

### Pitfall 4: Circular Module Dependencies

```hcl
# Module A needs output from Module B
# Module B needs output from Module A
# → Error: Cycle detected

# Fix: redesign modules hoặc dùng data source
```

### Production Case Study: Terraform State Corruption

#### Context
E-commerce platform, 50 engineers, Terraform quản lý AWS infrastructure. Remote state trên S3 + DynamoDB locking.

#### Symptom
`terraform plan` fail với error "Error loading state: state snapshot was created by Terraform v1.7.0, which is newer than current v1.6.0".

#### Investigation
1. Engineer A upgrade Terraform lên 1.7.0 trên máy local.
2. A chạy `terraform apply` → state written với format 1.7.0.
3. CI/CD pipeline vẫn dùng 1.6.0 → không đọc được state mới.
4. Engineer B (1.6.0) cũng không thể plan/apply.

#### Root Cause
- Terraform state format forward-incompatible: version mới hơn ghi state, version cũ không đọc được.
- Không có `.terraform-version` hoặc `tfenv` enforce version consistency.

#### Mitigation
1. Upgrade tất cả CI/CD và machines lên 1.7.0.
2. Verify state readable.

#### Long-term Fix
1. Pin Terraform version: `required_version = "~> 1.7.0"`.
2. Dùng `tfenv` hoặc `asdf` cho version management.
3. CI/CD dùng chính xác cùng version.
4. Backup state trước mỗi upgrade → S3 versioning.

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Day 27

- Day 27 dùng **local state**, single project — học basics.
- Day 28 chuyển sang **remote state**, **modules** — team-ready.
- Concepts từ Day 27 (provider, resource, variable, output) vẫn dùng, chỉ thêm layer.

### Bài sau: Day 29 — Pulumi vs Terraform vs CDK

- Day 28 bạn đã master Terraform — biết limitations (HCL, state, modules).
- Day 29 sẽ so sánh với alternatives: Pulumi (TypeScript/Python), CDK (AWS-specific).
- Hiểu tradeoffs giúp chọn tool phù hợp cho từng team/project.

---

## 11. Tài liệu tham khảo

### Must-read

- [Terraform Module Documentation](https://developer.hashicorp.com/terraform/language/modules) — Official module guide.
- [Terraform State Documentation](https://developer.hashicorp.com/terraform/language/state) — State management deep dive.
- [Terraform Backend Configuration](https://developer.hashicorp.com/terraform/language/settings/backends) — Backend options.

### Nice-to-have

- [Terraform Module Registry](https://registry.terraform.io/browse/modules) — Community modules.
- [Terraform State Commands](https://developer.hashicorp.com/terraform/cli/commands/state) — State CLI reference.
- [Gruntwork — How to manage Terraform state](https://blog.gruntwork.io/how-to-manage-terraform-state-28f5697e68fa) — Practical state management.

### Deep-dive

- [Terraform: Up & Running — Chapter 3: State](https://www.terraformupandrunning.com/) — Best book chapter on state.
- [Terratest](https://terratest.gruntwork.io/) — Testing Terraform code.
- [How to Create Terraform Modules](https://developer.hashicorp.com/terraform/tutorials/modules) — Interactive tutorial.

