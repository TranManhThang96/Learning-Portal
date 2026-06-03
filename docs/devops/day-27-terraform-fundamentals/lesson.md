# Day 27: Terraform Fundamentals

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. Giải thích được kiến trúc Terraform: **provider**, **resource**, **data source**, **state** và cách chúng tương tác.
2. Viết được Terraform configuration hoàn chỉnh với **variables**, **outputs**, **locals** và **module basics**.
3. Thực hiện được workflow **init → plan → apply → destroy** và hiểu mỗi bước làm gì bên dưới.
4. Quản lý được **state file** và **workspace** ở mức cơ bản: list, show, select, create, remove.
5. Debug được các lỗi Terraform phổ biến: provider init fail, state lock, dependency cycle.

---

## 2. Bối cảnh & Động lực

### Vì sao Terraform?

Day 26 bạn đã học IaC principles — declarative, state management, drift, idempotency. Hôm nay bạn sẽ apply những principles đó vào **Terraform**, tool IaC phổ biến nhất thế giới.

**Terraform trong ecosystem:**

```
IaC Principles (Day 26)
    │
    ├── Terraform ← BẠN ĐANG Ở ĐÂY
    │   ├── HCL (HashiCorp Configuration Language)
    │   ├── 3000+ providers (AWS, GCP, Azure, K8s, GitHub, ...)
    │   └── State-based reconciliation
    │
    ├── Pulumi (Day 29)
    │   └── General-purpose languages (TS, Python, Go)
    │
    └── AWS CDK (Day 29)
        └── AWS-specific, CloudFormation backend
```

### Vì sao developer cần biết Terraform?

- **Self-service infrastructure**: không cần đợi DevOps team tạo S3 bucket hay database.
- **Code review infrastructure**: review PR cho Terraform cần hiểu HCL.
- **Debug production issues**: hiểu infrastructure layer giúp debug nhanh hơn.
- **Career growth**: DevOps/Platform Engineer đều cần Terraform.

### Analogy cho developer

| Developer concept | Terraform equivalent |
|---|---|
| npm/pip/go mod | terraform init (download providers) |
| import library | provider configuration |
| Class/Object | resource block |
| Read-only query | data source |
| Constructor parameters | variables |
| Return values | outputs |
| Package/module | module |
| Database | state file |
| Dry run / lint | terraform plan |
| Deploy | terraform apply |
| Rollback | revert code + apply |

---

## 3. Kiến thức nền tảng

### HCL — HashiCorp Configuration Language

Terraform dùng **HCL** — một DSL (Domain Specific Language) thiết kế cho infrastructure configuration:

```hcl
# Block type "resource", provider "local", resource type "file"
resource "local_file" "hello" {
  filename = "/tmp/hello.txt"
  content  = "Hello, Terraform!"
}
```

**Cấu trúc HCL block:**

```
block_type "label_1" "label_2" {
  argument_1 = "value"
  argument_2 = 42

  nested_block {
    nested_arg = true
  }
}
```

### Terraform Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Terraform CLI                          │
│                                                           │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  │
│  │  init   │  │   plan   │  │  apply  │  │ destroy  │  │
│  └────┬────┘  └─────┬────┘  └────┬────┘  └─────┬────┘  │
│       │             │            │              │        │
│  ┌────┴─────────────┴────────────┴──────────────┴────┐  │
│  │                 Terraform Core                     │  │
│  │  • Parse HCL                                       │  │
│  │  • Build dependency graph                          │  │
│  │  • Diff desired vs actual state                    │  │
│  │  • Execute plan                                    │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                  │
│  ┌─────────────────────┴─────────────────────────────┐  │
│  │                  Providers                         │  │
│  │                                                     │  │
│  │  ┌─────┐  ┌─────┐  ┌───────┐  ┌────────┐         │  │
│  │  │ AWS │  │ GCP │  │ Azure │  │ Docker │  ...     │  │
│  │  └──┬──┘  └──┬──┘  └───┬───┘  └───┬────┘         │  │
│  └─────┼────────┼────────┼────────────┼──────────────┘  │
│        │        │        │            │                   │
└────────┼────────┼────────┼────────────┼──────────────────┘
         │        │        │            │
    ┌────┴───┐ ┌──┴──┐ ┌──┴───┐  ┌────┴─────┐
    │AWS API │ │GCP  │ │Azure │  │Docker    │
    │        │ │API  │ │API   │  │Engine    │
    └────────┘ └─────┘ └──────┘  └──────────┘
```

### Core Concepts

#### 1. Provider

Provider là plugin kết nối Terraform với API của cloud/service:

```hcl
# Provider = SDK/client library
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

provider "docker" {
  # host = "unix:///var/run/docker.sock"  # Linux
  # host = "npipe:////.//pipe//docker_engine"  # Windows
}
```

#### 2. Resource

Resource là infrastructure object mà Terraform quản lý:

```hcl
# resource "<provider>_<type>" "<local_name>" { ... }
resource "docker_image" "nginx" {
  name         = "nginx:alpine"
  keep_locally = false
}

resource "docker_container" "web" {
  image = docker_image.nginx.image_id
  name  = "web-server"
  
  ports {
    internal = 80
    external = 8080
  }
}
```

#### 3. Data Source

Data source đọc thông tin từ infrastructure hiện có (read-only):

```hcl
# Đọc thông tin — KHÔNG tạo/modify
data "local_file" "existing_config" {
  filename = "/etc/hostname"
}

output "hostname" {
  value = data.local_file.existing_config.content
}
```

#### 4. Variables

```hcl
# variables.tf
variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "container_count" {
  description = "Number of containers to create"
  type        = number
  default     = 1
}

variable "labels" {
  description = "Labels to apply"
  type        = map(string)
  default     = {}
}
```

#### 5. Output

```hcl
# outputs.tf
output "container_id" {
  description = "ID of the created container"
  value       = docker_container.web.id
}

output "container_ip" {
  description = "IP address of the container"
  value       = docker_container.web.network_data[0].ip_address
  sensitive   = true
}
```

#### 6. Locals

```hcl
locals {
  # Computed values, không cho user thay đổi
  project_name = "${var.project}-${var.environment}"
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = var.project
  }
}
```

---

## 4. Deep Dive

### Terraform Workflow chi tiết

```
┌─────────────────────────────────────────────────────────────┐
│                    terraform init                            │
│                                                              │
│  1. Parse terraform {} block                                 │
│  2. Download required providers to .terraform/               │
│  3. Initialize backend (state storage)                       │
│  4. Download referenced modules                              │
│  5. Create .terraform.lock.hcl (provider versions)           │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────────────┐
│                    terraform plan                             │
│                                                              │
│  1. Read current state (terraform.tfstate)                    │
│  2. Refresh: query providers for actual state                │
│  3. Parse all .tf files → build resource graph               │
│  4. Diff desired state vs actual state                        │
│  5. Generate execution plan:                                  │
│     + create (new resources)                                  │
│     ~ update in-place (modify existing)                       │
│     -/+ replace (destroy + create)                            │
│     - destroy (remove resources)                              │
│  6. Display plan for review                                   │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────────────┐
│                    terraform apply                            │
│                                                              │
│  1. Re-run plan (or use saved plan)                           │
│  2. Prompt for confirmation (unless -auto-approve)            │
│  3. Execute changes in dependency order:                      │
│     - Independent resources: PARALLEL                         │
│     - Dependent resources: SEQUENTIAL                         │
│  4. Update state file after each resource                     │
│  5. Display results                                           │
└──────────────────────────────────────────────────────────────┘
```

### Dependency Graph

Terraform tự động xây dựng **dependency graph** từ references:

```hcl
resource "docker_network" "app_net" {
  name = "app-network"
}

resource "docker_image" "app" {
  name = "nginx:alpine"
}

resource "docker_container" "app" {
  name  = "app"
  image = docker_image.app.image_id          # depends on docker_image.app

  networks_advanced {
    name = docker_network.app_net.name        # depends on docker_network.app_net
  }
}
```

```
Dependency Graph:
                    docker_container.app
                    /                    \
        docker_image.app          docker_network.app_net
        (parallel)                (parallel)
```

Terraform tạo `docker_image.app` và `docker_network.app_net` **song song**, rồi tạo `docker_container.app` sau khi cả hai hoàn thành.

### State File Internals

```json
{
  "version": 4,
  "terraform_version": "1.7.0",
  "resources": [
    {
      "mode": "managed",
      "type": "docker_container",
      "name": "web",
      "provider": "provider[\"registry.terraform.io/kreuzwerker/docker\"]",
      "instances": [
        {
          "attributes": {
            "id": "abc123def456",
            "name": "web-server",
            "image": "sha256:...",
            "ports": [
              {
                "internal": 80,
                "external": 8080
              }
            ]
          }
        }
      ]
    }
  ]
}
```

---

## 5. Trade-offs & Best Practices ⭐

### HCL vs General-Purpose Languages

| Aspect | HCL (Terraform) | General-Purpose (Pulumi/CDK) |
|--------|-----------------|------------------------------|
| Learning | Cần học DSL mới | Dùng ngôn ngữ quen |
| Type safety | Limited validation | Full type system |
| Testing | Terratest, plan check | Standard unit tests |
| IDE support | Good (TF extension) | Excellent (TypeScript/Python) |
| Abstraction | Module = function | Class, interface, generics |
| Debugging | Plan output analysis | Standard debugger |
| Governance | Sentinel/OPA policies | Code review + policies |
| Ecosystem | 3000+ providers | Same providers, fewer wrappers |
| Best for | Operations-focused teams | Developer-focused teams |

### File Organization Best Practices

```
# SMALL PROJECT (<20 resources)
project/
├── main.tf           # Resources
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── providers.tf      # Provider config
├── terraform.tfvars  # Variable values (DON'T commit secrets)
└── .gitignore

# MEDIUM PROJECT (20-100 resources)
project/
├── main.tf           # High-level composition
├── networking.tf     # VPC, subnets, SG
├── compute.tf        # EC2, EKS, ASG
├── database.tf       # RDS, ElastiCache
├── storage.tf        # S3, EFS
├── variables.tf
├── outputs.tf
├── providers.tf
├── versions.tf       # Required provider versions
└── locals.tf

# LARGE PROJECT (100+ resources) → Use modules (Day 28)
```

### Naming Conventions

```hcl
# Resource naming: snake_case, descriptive
resource "aws_instance" "web_server" { ... }     # ✅
resource "aws_instance" "server1" { ... }         # ❌ unclear
resource "aws_instance" "webServer" { ... }       # ❌ camelCase

# Variable naming: snake_case, có prefix khi cần
variable "vpc_cidr_block" { ... }                 # ✅
variable "cidr" { ... }                           # ❌ too vague

# Output naming: mô tả rõ resource + attribute
output "web_server_public_ip" { ... }             # ✅
output "ip" { ... }                               # ❌ ambiguous
```

### Version Constraint Best Practices

```hcl
terraform {
  required_version = ">= 1.5.0, < 2.0.0"   # Pin major, allow minor/patch
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"                     # >= 5.0, < 6.0
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = ">= 3.0.0, < 4.0.0"
    }
  }
}
```

| Constraint | Meaning | Use Case |
|-----------|---------|----------|
| `= 1.5.0` | Exact version | Breaking change risk, testing |
| `>= 1.5.0` | Minimum version | Loose, may break on major |
| `~> 1.5.0` | >= 1.5.0, < 1.6.0 | Allow patch updates only |
| `~> 1.5` | >= 1.5, < 2.0 | Allow minor + patch |
| `>= 1.5.0, < 2.0.0` | Range | Explicit control |

---

## 6. Performance & Scalability ⭐

### Plan/Apply Performance

| Factor | Impact | Optimization |
|--------|--------|-------------|
| Resource count | Plan time tăng linear | Split state |
| Provider API calls | Mỗi resource = 1+ API call | Parallelism config |
| State file size | Read/write latency | State split |
| Module downloads | Init time | Module caching |
| Provider downloads | Init time | Provider caching |

### Parallelism

```bash
# Default: 10 concurrent operations
terraform apply

# Increase parallelism (careful with API rate limits)
terraform apply -parallelism=20

# Decrease for debugging or rate-limit-sensitive providers
terraform apply -parallelism=1
```

### Target Specific Resources

```bash
# Chỉ dùng khi debugging hoặc recovery có kiểm soát
terraform plan -target=docker_container.web
terraform apply -target=docker_container.web

# Không dùng -target như cách tăng tốc thường ngày.
# Production nên split state và apply toàn bộ configuration để giữ dependency graph consistent.
```

### Refresh Performance

```bash
# Skip refresh khi biết state đúng (faster plan)
terraform plan -refresh=false

# ⚠️ Chỉ dùng khi chắc chắn không có drift
```

---

## 7. Security & Reliability Considerations

### Security Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Secrets trong .tf files | HIGH | Dùng variables, ENV, Vault |
| Secrets trong .tfvars | HIGH | Dùng ENV vars: `TF_VAR_password` |
| State chứa secrets | HIGH | Encrypt state, restrict access |
| Provider credentials quá rộng | HIGH | Least privilege IAM |
| .terraform/ chứa cached providers | LOW | .gitignore |

### Secret Management

```hcl
# ❌ NEVER hardcode secrets
resource "aws_db_instance" "main" {
  password = "super-secret-123"    # ❌ NEVER
}

# ✅ Use variables
variable "db_password" {
  type      = string
  sensitive = true
}

resource "aws_db_instance" "main" {
  password = var.db_password       # ✅
}

# Pass via environment variable
# export TF_VAR_db_password="super-secret-123"
# terraform apply
```

### Sensitive Outputs

```hcl
output "db_password" {
  value     = aws_db_instance.main.password
  sensitive = true  # Không hiển thị trong terminal output
}
```

### Lifecycle Protection

```hcl
resource "aws_db_instance" "prod" {
  # ... config ...

  lifecycle {
    prevent_destroy = true  # Terraform sẽ ERROR nếu plan chứa destroy
  }
}
```

---

## 8. Hands-on Example

### Project: Quản lý Docker containers bằng Terraform

Bài hands-on này sử dụng **Docker provider** — không cần cloud account.

**Prerequisites:**
- Terraform >= 1.5 installed
- Docker Desktop running

#### Bước 1: Tạo project

```bash
mkdir -p terraform-docker-demo && cd terraform-docker-demo
```

#### Bước 2: Viết configuration

**providers.tf**
```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

provider "docker" {}
```

**variables.tf**
```hcl
variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "app_port" {
  description = "External port for the web application"
  type        = number
  default     = 8080
}

variable "container_count" {
  description = "Number of web containers"
  type        = number
  default     = 1

  validation {
    condition     = var.container_count >= 1 && var.container_count <= 5
    error_message = "Container count must be between 1 and 5."
  }
}

variable "nginx_version" {
  description = "NGINX image version"
  type        = string
  default     = "alpine"
}
```

**locals.tf**
```hcl
locals {
  project_name = "tf-demo"
  full_name    = "${local.project_name}-${var.environment}"

  common_labels = {
    "managed-by"  = "terraform"
    "environment" = var.environment
    "project"     = local.project_name
  }

  nginx_config = <<-EOT
    server {
      listen 80;
      server_name localhost;
      
      location / {
        root /usr/share/nginx/html;
        index index.html;
      }
      
      location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
      }
    }
  EOT

  index_html = <<-EOT
    <!DOCTYPE html>
    <html>
    <head><title>Terraform Demo</title></head>
    <body>
      <h1>Hello from Terraform!</h1>
      <p>Environment: ${var.environment}</p>
      <p>Managed by: Terraform</p>
    </body>
    </html>
  EOT
}
```

**main.tf**
```hcl
# Network cho containers
resource "docker_network" "app" {
  name = "${local.full_name}-network"

  labels {
    label = "managed-by"
    value = "terraform"
  }
}

# Pull NGINX image
resource "docker_image" "nginx" {
  name         = "nginx:${var.nginx_version}"
  keep_locally = false
}

# Tạo config files trên host
resource "local_file" "nginx_config" {
  filename = "${path.module}/config/nginx.conf"
  content  = local.nginx_config
}

resource "local_file" "index_html" {
  filename = "${path.module}/config/index.html"
  content  = local.index_html
}

# Web containers
resource "docker_container" "web" {
  count = var.container_count

  name  = "${local.full_name}-web-${count.index}"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = var.app_port + count.index
  }

  networks_advanced {
    name = docker_network.app.name
  }

  upload {
    content = local.nginx_config
    file    = "/etc/nginx/conf.d/default.conf"
  }

  upload {
    content = local.index_html
    file    = "/usr/share/nginx/html/index.html"
  }

  labels {
    label = "managed-by"
    value = "terraform"
  }

  labels {
    label = "environment"
    value = var.environment
  }

  restart = "unless-stopped"

  healthcheck {
    test     = ["CMD", "curl", "-f", "http://localhost/health"]
    interval = "10s"
    timeout  = "5s"
    retries  = 3
  }

  must_run = true
}

# Data source: đọc thông tin container đã tạo
data "docker_network" "app_info" {
  name = docker_network.app.name

  depends_on = [docker_container.web]
}
```

**outputs.tf**
```hcl
output "container_names" {
  description = "Names of created containers"
  value       = docker_container.web[*].name
}

output "container_ports" {
  description = "External ports mapped to containers"
  value = [
    for c in docker_container.web : {
      name = c.name
      port = c.ports[0].external
      url  = "http://localhost:${c.ports[0].external}"
    }
  ]
}

output "network_name" {
  description = "Docker network name"
  value       = docker_network.app.name
}

output "access_urls" {
  description = "URLs to access the web containers"
  value       = [for i in range(var.container_count) : "http://localhost:${var.app_port + i}"]
}
```

#### Bước 3: Chạy Terraform

```bash
# 1. Initialize — download providers
terraform init

# Expected output:
# Initializing the backend...
# Initializing provider plugins...
# - Installing kreuzwerker/docker v3.x.x...
# - Installing hashicorp/local v2.x.x...
# Terraform has been successfully initialized!

# 2. Validate — check syntax
terraform validate

# Expected output:
# Success! The configuration is valid.

# 3. Plan — preview changes và lưu plan đã review
terraform plan -out=tf-demo.tfplan

# Expected output:
# Plan: 5 to add, 0 to change, 0 to destroy.
# (docker_network, docker_image, local_file x2, docker_container)

# 4. Apply — chạy đúng plan đã review
terraform apply tf-demo.tfplan

# Expected output:
# Apply complete! Resources: 5 added, 0 changed, 0 destroyed.
# container_names = ["tf-demo-dev-web-0"]
# access_urls = ["http://localhost:8080"]

# 5. Verify
curl http://localhost:8080
curl http://localhost:8080/health

# 6. Check state
terraform state list
# docker_container.web[0]
# docker_image.nginx
# docker_network.app
# local_file.index_html
# local_file.nginx_config

terraform state show docker_container.web[0]
```

#### Bước 4: Thử thay đổi

```bash
# Tăng container count
terraform plan -var="container_count=3" -out=scale-out.tfplan
terraform apply scale-out.tfplan

# Expected: 2 to add (2 containers mới)
# Verify:
curl http://localhost:8080   # container 0
curl http://localhost:8081   # container 1
curl http://localhost:8082   # container 2

# Đổi environment
terraform plan -var="environment=staging" -var="container_count=2" -out=staging.tfplan
terraform apply staging.tfplan

# Expected: containers renamed, network renamed
```

#### Bước 5: Khám phá state

```bash
# Xem toàn bộ state
terraform state list

# Xem chi tiết 1 resource
terraform state show docker_container.web[0]

# Xem dependency graph
terraform graph | dot -Tpng > graph.png
# Hoặc xem text
terraform graph
```

#### Bước 5.5: Khám phá workspace

Workspace tách state cùng một configuration. Nó hữu ích cho lab hoặc environments rất giống nhau; production thường ưu tiên directory/state riêng theo environment để giảm blast radius.

```bash
terraform workspace list
terraform workspace new dev
terraform workspace show
terraform plan -out=dev.tfplan
terraform apply dev.tfplan
terraform workspace select default
terraform workspace delete dev
```

#### Bước 6: Cleanup

```bash
# Destroy all resources
terraform destroy

# Type "yes" when prompted
# Expected output:
# Destroy complete! Resources: 5 destroyed.

# Verify
docker ps  # no tf-demo containers
docker network ls  # no tf-demo network

# Clean up local files
cd ..
rm -rf terraform-docker-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Quên `terraform init` sau khi thêm provider

```
Error: Failed to instantiate provider
"registry.terraform.io/kreuzwerker/docker"
```

**Fix:** `terraform init` mỗi khi thêm/đổi provider hoặc module.

### Pitfall 2: State lock — ai đó đang apply

```
Error: Error acquiring the state lock
Lock Info:
  ID:        12345-abcde
  Path:      terraform.tfstate
  Operation: OperationTypeApply
  Who:       dev@laptop
  Created:   2024-01-15 10:30:00
```

**Fix:**
```bash
# Kiểm tra ai đang hold lock
# Nếu process đã chết:
terraform force-unlock 12345-abcde

# ⚠️ CHỈ dùng khi chắc chắn không ai đang apply
```

### Pitfall 3: Dependency cycle

```
Error: Cycle: resource_a, resource_b

# Resource A depends on B, B depends on A
```

**Fix:** Review dependencies, thường do implicit reference. Dùng `depends_on` explicit hoặc tách resource.

### Pitfall 4: Resource replacement thay vì update

```
# terraform plan output:
# docker_container.web must be replaced
# -/+ resource "docker_container" "web" {
#     ~ name = "web-old" -> "web-new" (forces replacement)
```

Một số attributes khi thay đổi sẽ **force replacement** (destroy + create) thay vì update in-place. Luôn đọc plan cẩn thận.

### Pitfall 5: Count/index thay đổi

```hcl
# 3 containers: web[0], web[1], web[2]
# Giảm count từ 3 xuống 2:
# Terraform destroy web[2] ← OK

# Nhưng nếu xóa container ở giữa (index shift):
# web[0], web[1] còn lại, NHƯNG web[1] cũ giờ thành web[1] mới
# Data/state có thể shift sai
```

**Fix:** Dùng `for_each` thay vì `count` khi resources có identity riêng (Day 28).

### Production Case Study: Terraform Plan nói "0 changes" nhưng Infrastructure khác Code

#### Context
Mid-size SaaS company, team 20 engineers, dùng Terraform quản lý AWS infrastructure.

#### Symptom
`terraform plan` hiện "No changes" nhưng security group trên AWS có thêm rules không có trong code.

#### Investigation
1. `terraform plan` → "No changes. Your infrastructure matches the configuration."
2. AWS console → security group có port 3306 (MySQL) open từ 0.0.0.0/0 ← không có trong code!
3. Kiểm tra: security group managed bởi Terraform, nhưng rule được thêm bằng **AWS CLI bởi developer khác**.
4. Terraform chỉ quản lý rules **trong code** — rules thêm bên ngoài bị ignore (đối với `aws_security_group` resource).

#### Root Cause
- `aws_security_group` resource manage toàn bộ SG, NHƯNG `aws_security_group_rule` resource chỉ manage individual rules.
- Khi dùng `aws_security_group` với `ingress {}` inline, Terraform manage toàn bộ rules → sẽ detect drift.
- Khi dùng `aws_security_group_rule` riêng lẻ, Terraform chỉ biết rules trong code.
- Developer tạo rule bằng CLI → Terraform không biết → "No changes".

#### Long-term Fix
1. Migrate sang `aws_security_group_rule` resources cho tất cả rules.
2. Import manual rules vào Terraform state.
3. Thêm drift detection weekly.
4. Lock down IAM: chỉ Terraform role có quyền modify security groups.

#### Lesson Learned
- Hiểu rõ **resource boundary** — Terraform manage gì và không manage gì.
- Drift có thể "invisible" nếu resource type không track certain attributes.
- Kết hợp IaC với IAM restrictions để prevent manual changes.

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Day 26

- Day 26 dạy **principles**: declarative, state, drift, idempotency.
- Day 27 bạn đã **apply principles** vào Terraform — viết HCL, quản lý state, chạy plan/apply.

### Bài sau: Day 28 — Terraform Advanced

- Day 27 dùng **local state** — 1 người, 1 project.
- Day 28 sẽ học **remote state** (team collaboration), **modules** (code reuse), **drift detection**, **import**.
- Đây là bước chuyển từ "Terraform cho cá nhân" sang "Terraform cho team production".

### Liên hệ với Kubernetes (Phase 2-3)

- Terraform tạo infrastructure **bên dưới** Kubernetes: VPC, EKS cluster, node groups, load balancers.
- Helm/Kustomize (Day 16) quản lý **application layer** trên Kubernetes.
- Cả Terraform và Kubernetes đều dùng **declarative** + **reconciliation** pattern.

---

## 11. Tài liệu tham khảo

### Must-read

- [Terraform Documentation — Get Started](https://developer.hashicorp.com/terraform/tutorials/aws-get-started) — Official tutorial, excellent starting point.
- [Terraform Language Documentation](https://developer.hashicorp.com/terraform/language) — HCL syntax reference.
- [Docker Provider Documentation](https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs) — Provider dùng trong hands-on.

### Nice-to-have

- [Terraform Best Practices](https://www.terraform-best-practices.com/) — Community-maintained best practices guide.
- [HashiCorp Learn — Terraform](https://developer.hashicorp.com/terraform/tutorials) — Interactive tutorials.
- [Terraform Registry](https://registry.terraform.io/) — Browse 3000+ providers và modules.

### Deep-dive

- [Terraform: Up & Running — Yevgeniy Brikman](https://www.terraformupandrunning.com/) — Best practical book.
- [How Terraform Works — A Visual Intro](https://blog.gruntwork.io/an-introduction-to-terraform-f17df9c6d180) — Visual explanation.
- [Terraform Internals](https://developer.hashicorp.com/terraform/internals) — Graph, state, plugin protocol.

