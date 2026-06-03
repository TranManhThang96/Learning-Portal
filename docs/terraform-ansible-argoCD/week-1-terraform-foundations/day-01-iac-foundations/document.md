# Day 1 — Cheat Sheet: IaC Comparison & Terraform CLI Reference

---

## IaC Tool Comparison

| Criteria | Terraform | Ansible | Pulumi | CloudFormation | CDK |
|---|---|---|---|---|---|
| **Primary use** | Infrastructure provisioning | Config management + provisioning | Infrastructure provisioning | AWS infrastructure | AWS infrastructure |
| **Approach** | Declarative | Imperative (tasks) / Declarative (desired state) | Declarative (real code) | Declarative | Declarative (real code) |
| **Language** | HCL | YAML + Jinja2 | Python / TypeScript / Go / C# | JSON / YAML | TypeScript / Python / Java |
| **State management** | Yes (file / remote) | No built-in state | Yes (Pulumi Cloud / self-hosted) | Managed by AWS | Managed by AWS |
| **Multi-cloud** | Yes (800+ providers) | Partial | Yes | No (AWS only) | No (AWS only) |
| **Mutable infra** | No (immutable mindset) | Yes | No | No | No |
| **Unit testing** | Limited (Terratest) | Molecule | Yes (native pytest/jest) | cfn-lint | Jest / pytest |
| **Drift detection** | Yes (`terraform plan`) | Limited | Yes | Yes (drift detection) | Limited |
| **Import existing** | `terraform import` | N/A | `pulumi import` | No | No |
| **Maturity** | Very high (2014) | Very high (2012) | Medium (2018) | High (2011) | Medium (2019) |
| **License** | BSL 1.1 (2023+) | GPL v3 | Apache 2.0 | Proprietary | Apache 2.0 |
| **Ecosystem** | Terraform Registry, Gruntwork | Ansible Galaxy | Pulumi Registry | CloudFormation Registry | Construct Hub |

### Khi nào chọn gì

```
Cần provision cloud infrastructure?
├── AWS only + team quen CloudFormation?  →  CloudFormation / CDK
├── Multi-cloud hoặc nhiều providers?     →  Terraform
└── Team prefer real programming language →  Pulumi

Cần configure servers / apps sau khi provision?
└── Ansible (Day 8-14 của khóa này)

Cần cả hai?
└── Terraform (provision) + Ansible (configure) — phổ biến nhất
```

---

## Terraform CLI — Full Command Reference

### Lifecycle Commands

```bash
# Khởi tạo working directory, download providers
terraform init

# Init với upgrade providers lên version mới nhất (theo constraints)
terraform init -upgrade

# Init với backend config từ file (không hard-code backend config)
terraform init -backend-config=backend.hcl

# Migrate state sang backend mới
terraform init -migrate-state
```

```bash
# Validate syntax và config (không call API)
terraform validate

# Format code theo canonical style (overwrites files)
terraform fmt

# Format recursive — format cả subdirectories
terraform fmt -recursive

# Chỉ check, không sửa (dùng trong CI)
terraform fmt -check
```

```bash
# Tạo execution plan (không thay đổi gì)
terraform plan

# Save plan ra file (để apply chính xác plan đã review)
terraform plan -out=tfplan

# Plan chỉ cho specific resources
terraform plan -target=docker_container.web

# Plan với variable override
terraform plan -var="environment=staging"

# Plan với variable file
terraform plan -var-file=staging.tfvars

# Plan destroy (xem sẽ xóa gì)
terraform plan -destroy
```

```bash
# Apply (sẽ hỏi confirm)
terraform apply

# Apply không hỏi confirm (dùng trong CI/CD)
terraform apply -auto-approve

# Apply từ saved plan file (không hỏi confirm)
terraform apply tfplan

# Apply chỉ specific resource
terraform apply -target=docker_container.web

# Apply với variable override
terraform apply -var="host_port=9090"
```

```bash
# Destroy tất cả resources
terraform destroy

# Destroy không hỏi confirm
terraform destroy -auto-approve

# Destroy chỉ specific resource
terraform destroy -target=docker_container.web
```

### Inspection Commands

```bash
# Hiện current state (human-readable)
terraform show

# Hiện saved plan file
terraform show tfplan

# Hiện outputs
terraform output

# Hiện specific output
terraform output access_url

# Output dạng JSON (dùng trong scripts)
terraform output -json
```

```bash
# List tất cả resources trong state
terraform state list

# Xem chi tiết một resource trong state
terraform state show docker_container.web

# Move resource trong state (rename hoặc refactor)
terraform state mv docker_container.web docker_container.nginx

# Remove resource khỏi state (nhưng không destroy)
terraform state rm docker_container.web

# Pull current remote state (print ra stdout)
terraform state pull

# Push local state lên remote
terraform state push terraform.tfstate
```

```bash
# Import existing resource vào state
terraform import docker_container.web <container_id>

# Graph dependency (output DOT format)
terraform graph | dot -Tsvg > graph.svg
```

### Workspace Commands

```bash
# List workspaces
terraform workspace list

# Tạo workspace mới
terraform workspace new staging

# Switch workspace
terraform workspace select staging

# Xem current workspace
terraform workspace show

# Xóa workspace (phải switch ra trước)
terraform workspace delete staging
```

### Debug Commands

```bash
# Verbose logging
TF_LOG=DEBUG terraform apply
TF_LOG=ERROR terraform apply    # Chỉ errors

# Log ra file
TF_LOG=DEBUG TF_LOG_PATH=terraform.log terraform apply

# Force unlock state (dùng cẩn thận)
terraform force-unlock <LOCK_ID>

# Taint resource (force recreate lần apply tiếp theo) — deprecated từ 1.0
# Dùng thay thế:
terraform apply -replace=docker_container.web
```

---

## Terraform File Conventions

```
project/
├── main.tf           # Resources chính
├── variables.tf      # Input variable declarations
├── outputs.tf        # Output value declarations
├── providers.tf      # Provider configs (tách riêng cho dễ manage)
├── versions.tf       # terraform {} block với required_version và required_providers
├── locals.tf         # Local values (computed values)
├── data.tf           # Data sources
├── terraform.tfvars  # Variable values (KHÔNG commit nếu chứa secrets)
├── .terraform.lock.hcl  # Provider lock file (NÊN commit)
└── .gitignore        # Phải có *.tfstate, .terraform/
```

### .gitignore bắt buộc

```gitignore
# State files — chứa sensitive data
*.tfstate
*.tfstate.backup
*.tfstate.d/

# Provider cache
.terraform/

# Plan files — có thể chứa sensitive values  
*.tfplan
tfplan

# Override files
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Crash logs
crash.log
crash.*.log

# Sensitive variable files
*.tfvars
*.tfvars.json
!example.tfvars    # Ngoại lệ: example không chứa secrets

# Terraform Cloud credentials
.terraformrc
terraform.rc
```

---

## HCL Syntax Reference

### Variable Types

```hcl
variable "name" {
  type        = string
  default     = "default-value"
  description = "Mô tả biến"

  validation {
    condition     = length(var.name) > 0
    error_message = "Name không được rỗng."
  }
}

variable "count_val" {
  type    = number
  default = 3
}

variable "enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {
    env  = "dev"
    team = "platform"
  }
}

variable "allowed_ports" {
  type    = list(number)
  default = [80, 443, 8080]
}

variable "server_config" {
  type = object({
    instance_type = string
    disk_size_gb  = number
    enable_backup = bool
  })
  default = {
    instance_type = "t3.micro"
    disk_size_gb  = 20
    enable_backup = false
  }
}
```

### Local Values

```hcl
locals {
  # Computed values — không phải input
  app_prefix    = "${var.app_name}-${var.environment}"
  common_tags   = {
    ManagedBy   = "terraform"
    Environment = var.environment
    App         = var.app_name
  }
  is_production = var.environment == "production"
}

# Sử dụng
resource "docker_container" "web" {
  name = "${local.app_prefix}-web"
  labels {
    label = "env"
    value = local.common_tags.Environment
  }
}
```

### Expressions

```hcl
# Conditional (ternary)
instance_type = var.environment == "production" ? "t3.large" : "t3.micro"

# String interpolation
name = "${var.app_name}-${var.environment}"

# For expression — transform list
upper_names = [for name in var.names : upper(name)]

# For expression — filter
prod_instances = [for inst in var.instances : inst if inst.env == "production"]

# For expression — map
name_map = {for name in var.names : name => upper(name)}

# Splat expression
all_ids = aws_instance.servers[*].id

# Dynamic block
dynamic "ingress" {
  for_each = var.allowed_ports
  content {
    from_port = ingress.value
    to_port   = ingress.value
    protocol  = "tcp"
  }
}
```

### Meta-arguments

```hcl
resource "docker_container" "web" {
  # count: tạo N instances
  count = 3
  name  = "web-${count.index}"

  # for_each: tạo từ map/set
  for_each = toset(["web", "api", "worker"])
  name     = each.value

  # depends_on: explicit dependency (khi implicit không đủ)
  depends_on = [docker_network.lab_network]

  # lifecycle: kiểm soát create/destroy behavior
  lifecycle {
    create_before_destroy = true    # Tạo mới trước khi xóa cũ
    prevent_destroy       = true    # Ngăn destroy
    ignore_changes        = [labels]  # Ignore thay đổi ở fields này
    replace_triggered_by  = [docker_image.nginx.id]  # Replace khi ref thay đổi
  }

  # provider: chỉ định provider cụ thể (multi-provider)
  provider = docker.remote
}
```

---

## State Backend Quick Reference

### Local (default — chỉ dùng để học)

```hcl
# Không cần config gì
```

### S3 + DynamoDB (AWS — recommended cho team)

```hcl
# versions.tf hoặc main.tf
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "services/my-service/production/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

Setup DynamoDB table:
```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

### GCS (Google Cloud)

```hcl
terraform {
  backend "gcs" {
    bucket = "company-terraform-state"
    prefix = "services/my-service/production"
  }
}
```

### Terraform Cloud (HCP Terraform)

```hcl
terraform {
  cloud {
    organization = "my-company"
    workspaces {
      name = "my-service-production"
    }
  }
}
```

---

## Common Error Messages & Fixes

| Error | Nguyên nhân | Fix |
|---|---|---|
| `Error: No valid credential sources found` | AWS credentials chưa config | `aws configure` hoặc set `AWS_ACCESS_KEY_ID` env var |
| `Error: Error acquiring the state lock` | Apply khác đang chạy hoặc bị crash | Kiểm tra, nếu chắc chắn an toàn: `terraform force-unlock <ID>` |
| `Error: Resource already exists` | Resource tồn tại nhưng không có trong state | `terraform import <resource_address> <resource_id>` |
| `Error: Unsupported argument` | Typo trong argument name hoặc provider version cũ | Check provider docs, update version |
| `Error: cycle` | Circular dependency giữa resources | Dùng `depends_on` để break cycle hoặc refactor |
| `Error: Backend configuration changed` | Backend config thay đổi | `terraform init -reconfigure` |
| `Error: Provider produced inconsistent result` | Provider bug hoặc API race condition | Retry, hoặc check provider version |

---

## Quick Symbols in Plan Output

```
+ create        Resource sẽ được tạo
- destroy       Resource sẽ bị xóa
~ update        Resource sẽ được update in-place
-/+ replace     Resource sẽ bị destroy và tạo lại
<= read         Data source sẽ được đọc
!               Sensitive value (ẩn trong output)
(known after apply)  Giá trị chỉ biết sau khi apply
```
