# Day 2 - HCL, Variables, Outputs, Locals

> **Thời gian**: 2 giờ | **Cấp độ**: Foundations | **Prerequisites**: Day 1 hoàn thành

---

## 1. Mục tiêu ngày học

Sau Day 2, bạn có thể:

- Đọc và viết HCL syntax thành thạo - hiểu blocks, arguments, expressions
- Khai báo input variables với type constraints và validation rules
- Sử dụng locals để tính toán giá trị trung gian, tránh lặp code
- Expose outputs để chia sẻ data giữa modules và workspaces
- Tổ chức variables theo môi trường bằng tfvars files
- Nhận diện và tránh các anti-patterns phổ biến (over-parameterization, type mismatch)

---

## 2. Bối cảnh thực tế

### Vấn đề: Hardcode trong infrastructure code

Bạn đã thấy pattern này trong application code:

```python
# BAD - hardcode trong app code
DB_HOST = "prod-db.internal:5432"
REPLICA_COUNT = 3
MEMORY_LIMIT = "2Gi"
```

Infrastructure code mắc lỗi tương tự, nhưng hậu quả nặng hơn nhiều.

**Tình huống thực tế** - một startup scale từ 1 lên 5 môi trường:

```
environments/
├── dev/
│   └── main.tf   # instance_type = "t3.micro", replicas = 1
├── staging/
│   └── main.tf   # instance_type = "t3.medium", replicas = 2  ← copy-paste từ dev
├── prod/
│   └── main.tf   # instance_type = "t3.large", replicas = 3
├── prod-eu/
│   └── main.tf   # instance_type = "t3.large", replicas = 3  ← copy-paste từ prod
└── prod-apac/
    └── main.tf   # instance_type = "t3.large", replicas = 3  ← lại copy-paste
```

Vấn đề khi team thêm `health_check_path`:
- Phải update 5 file
- Copy-paste sai ở `prod-apac`
- Incident lúc 2am

**Terraform giải quyết** bằng cách tách **what** (configuration logic) ra khỏi **where** (environment values):

```
modules/
└── app-service/        ← logic chỉ viết 1 lần
    ├── main.tf
    ├── variables.tf    ← interface: what can be customized
    ├── outputs.tf      ← interface: what is exposed
    └── locals.tf       ← internal: computed values

environments/
├── dev.tfvars          ← chỉ chứa values, không có logic
├── staging.tfvars
└── prod.tfvars
```

Đây là **separation of concerns** áp dụng cho infrastructure.

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 HCL Syntax Deep Dive

HCL (HashiCorp Configuration Language) không phải YAML, không phải JSON. Nó là declarative language có expression engine.

**Cấu trúc cơ bản:**

```hcl
# Block syntax
<BLOCK_TYPE> "<BLOCK_LABEL>" "<BLOCK_LABEL>" {
  # Arguments
  <IDENTIFIER> = <EXPRESSION>

  # Nested block
  <BLOCK_TYPE> {
    <IDENTIFIER> = <EXPRESSION>
  }
}
```

**Ví dụ thực tế:**

```hcl
# Block type: resource
# Labels: "docker_container", "web_server"
resource "docker_container" "web_server" {
  name  = "nginx-${var.environment}"   # expression với interpolation
  image = docker_image.nginx.image_id  # reference tới resource khác

  # Nested block
  ports {
    internal = 80
    external = var.port
  }
}
```

**String literals và expressions:**

```hcl
locals {
  # Heredoc - multi-line string
  startup_script = <<-EOT
    #!/bin/bash
    echo "Starting ${var.app_name}"
    export ENV=${var.environment}
  EOT

  # Template directives
  server_list = <<-EOT
    %{ for server in var.servers ~}
    server ${server};
    %{ endfor ~}
  EOT

  # Conditional expression
  replica_count = var.environment == "prod" ? 3 : 1

  # String interpolation
  full_name = "${var.project}-${var.environment}-${var.app_name}"
}
```

**Comments:**

```hcl
# Single-line comment (preferred)

// Also valid single-line

/*
  Multi-line comment
  Use sparingly - prefer self-documenting names
*/
```

**ASCII diagram - HCL block anatomy:**

```
resource "aws_instance" "web" {
│        │              │
│        │              └── Block label 2 (local name)
│        └── Block label 1 (resource type)
└── Block type

  ami           = "ami-0c55b159cbfafe1f0"
  │               │
  │               └── Expression (string literal)
  └── Argument name

  tags = {
    Name = "web-server"
  }
  └── Argument với map value
}
```

### 3.2 Input Variables

**Tại sao cần?**

Variables là **interface** của module/configuration. Ai đó sẽ dùng module của bạn mà không cần đọc implementation. Variables chính là API documentation sống động.

**Variable block cơ bản:**

```hcl
# variables.tf

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "replica_count" {
  description = "Number of application replicas"
  type        = number
  # Không có default = bắt buộc phải cung cấp
}

variable "enable_https" {
  description = "Enable HTTPS termination"
  type        = bool
  default     = true
}
```

**Thứ tự ưu tiên khi Terraform resolve variable values:**

```
1. -var flag (CLI)                     ← highest priority
2. -var-file flag (CLI)
3. *.auto.tfvars (alphabetical order)
4. terraform.tfvars
5. TF_VAR_<name> environment variables
6. default value in variable block     ← lowest priority
```

**Sensitive variables:**

```hcl
variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true  # Terraform sẽ không in ra terminal, plan, apply output
  # Nhưng VẪN stored in state - cần encrypt state
}
```

> **Lưu ý**: `sensitive = true` che giấu giá trị trong output nhưng không mã hóa nó trong state file. State file cần được bảo vệ riêng (S3 + encryption, Terraform Cloud, v.v.)

### 3.3 Type Constraints

**Tại sao cần?**

Terraform detect lỗi type mismatch trước khi tạo resource. Tốt hơn là nhận lỗi từ AWS API sau 30 giây.

**Primitive types:**

```
string  → "hello", "123", ""
number  → 42, 3.14, -7
bool    → true, false
```

**Collection types:**

```hcl
# list(type) - ordered, allow duplicates
variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# map(type) - key-value, string keys
variable "tags" {
  type    = map(string)
  default = {
    Team    = "platform"
    Project = "infra"
  }
}

# set(type) - unordered, unique values
variable "allowed_ips" {
  type    = set(string)
  default = ["10.0.0.1", "10.0.0.2"]
}
```

**Structural types:**

```hcl
# object - fixed schema, named attributes
variable "database_config" {
  type = object({
    name     = string
    port     = number
    replicas = number
    ssl      = bool
  })
  default = {
    name     = "app_db"
    port     = 5432
    replicas = 1
    ssl      = true
  }
}

# tuple - fixed-length list, mixed types
variable "server_spec" {
  type    = tuple([string, number, bool])
  default = ["t3.medium", 8, true]
  # Usage: var.server_spec[0] = "t3.medium"
  #        var.server_spec[1] = 8
}
```

**Type conversion:**

```hcl
# Terraform tự động convert khi an toàn
variable "port" {
  type = number
}
# Truyền "8080" (string) sẽ được convert sang 8080 (number) tự động

# Dùng tostring(), tonumber(), tolist(), toset(), tomap() để convert explicit
locals {
  port_string = tostring(var.port)         # number → string
  tags_list   = tolist(var.allowed_ips)    # set → list (để dùng index)
}
```

**ASCII diagram - Type hierarchy:**

```
any
 ├── string
 ├── number
 ├── bool
 ├── list(any)
 │    ├── list(string)
 │    ├── list(number)
 │    └── list(object({...}))
 ├── map(any)
 │    ├── map(string)
 │    └── map(object({...}))
 ├── set(any)
 ├── object({...})   ← structural, fixed schema
 └── tuple([...])    ← structural, fixed length
```

### 3.4 Validation Rules

**Tại sao cần?**

Fail fast. Tốt hơn là fail ở `terraform plan` sau 1 giây thay vì fail ở provider API sau 5 phút với error message khó đọc.

```hcl
variable "environment" {
  type        = string
  description = "Deployment environment"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod"
  }
}

variable "replica_count" {
  type        = number
  description = "Number of replicas"

  validation {
    condition     = var.replica_count >= 1 && var.replica_count <= 10
    error_message = "replica_count must be between 1 and 10"
  }
}

variable "app_name" {
  type        = string
  description = "Application name (used in DNS, labels)"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}[a-z0-9]$", var.app_name))
    error_message = "app_name must be lowercase, 4-32 chars, start with letter, only a-z0-9-"
  }

  validation {
    condition     = !can(regex("--", var.app_name))
    error_message = "app_name must not contain consecutive hyphens"
  }
}
```

**Multiple validations** - mỗi validation block check một điều kiện cụ thể. Error message rõ ràng hơn.

### 3.5 Output Values

**Tại sao cần?**

Outputs có 3 mục đích:
1. **Display**: Hiển thị thông tin sau `terraform apply` (URLs, IPs, connection strings)
2. **Module composition**: Truyền data từ module này sang module khác
3. **Remote state**: Chia sẻ data giữa các Terraform workspaces khác nhau

```hcl
# outputs.tf

output "service_endpoint" {
  description = "HTTP endpoint of the deployed service"
  value       = "http://${docker_container.app.ports[0].external}/"
}

output "container_id" {
  description = "Docker container ID"
  value       = docker_container.app.id
}

# Sensitive output - ẩn trong terminal nhưng accessible qua terraform output -raw
output "connection_string" {
  description = "Database connection string"
  value       = "postgresql://${var.db_user}:${var.db_password}@${docker_container.db.ports[0].external}/app"
  sensitive   = true
}

# Output một object phức tạp
output "service_info" {
  description = "Complete service information"
  value = {
    name     = docker_container.app.name
    endpoint = "http://localhost:${docker_container.app.ports[0].external}"
    image    = var.app_image
  }
}
```

**Dùng outputs trong compose:**

```hcl
# Root module dùng output từ child module
module "database" {
  source = "./modules/database"
  # ...
}

module "application" {
  source           = "./modules/application"
  db_host          = module.database.host        # ← dùng output của module khác
  db_port          = module.database.port
  db_password      = module.database.password
}
```

### 3.6 Locals

**Tại sao cần?**

Locals là **computed constants** - giá trị được tính toán một lần, dùng nhiều lần. Tránh lặp expression phức tạp. Đặt tên cho intermediate values.

```hcl
# locals.tf

locals {
  # Naming convention: project-env-component
  name_prefix = "${var.project}-${var.environment}"

  # Tags được merge giữa common tags và resource-specific tags
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Team        = var.team
  }

  # Computed values từ variables
  is_production = var.environment == "prod"

  # Conditional logic
  replica_count = local.is_production ? var.prod_replicas : 1

  # Resource sizing per environment
  instance_config = {
    dev = {
      cpu    = 0.25
      memory = 256
    }
    staging = {
      cpu    = 0.5
      memory = 512
    }
    prod = {
      cpu    = 1.0
      memory = 1024
    }
  }

  # Dùng lookup với current environment
  current_config = local.instance_config[var.environment]
}
```

**Dùng locals trong resources:**

```hcl
resource "docker_container" "app" {
  name  = "${local.name_prefix}-app"    # ← dùng local thay vì repeat expression
  image = var.app_image

  labels {
    label = "project"
    value = var.project
  }
  labels {
    label = "environment"
    value = var.environment
  }

  cpu_shares = local.current_config.cpu * 1024
  memory     = local.current_config.memory
}
```

### 3.7 Naming Conventions

**Terraform community conventions:**

```hcl
# Variables: snake_case
variable "instance_type" {}
variable "enable_monitoring" {}
variable "db_connection_string" {}

# Locals: snake_case
locals {
  name_prefix   = "..."
  common_tags   = {}
  is_production = true
}

# Outputs: snake_case, descriptive
output "service_url" {}
output "container_id" {}
output "database_host" {}

# Resources: snake_case, describe the role not the type
resource "docker_container" "web_server" {}  # ← "web_server" not "container_1"
resource "docker_container" "background_worker" {}

# Modules: snake_case, noun
module "database" {}
module "application_service" {}
module "load_balancer" {}
```

---

## 4. Deep Dive & Trade-offs - 30 phút

### 4.1 Variables vs Locals vs Data Sources

```
Câu hỏi: Giá trị này đến từ đâu?

Từ bên ngoài (caller/user)           → variable
Được tính toán từ values có sẵn      → local
Query từ external system/provider     → data source

Ví dụ:
- Tên environment (dev/prod)          → variable (caller biết)
- name prefix = project + env         → local (tính toán từ 2 variables)
- Latest AMI ID của Amazon Linux 2    → data source (query AWS API)
- DB password                         → variable (secret, từ vault hoặc CI)
- Tags map đầy đủ                     → local (computed từ nhiều variables)
- Existing VPC ID                     → data source (infrastructure hiện có)
```

### 4.2 Variable Organization Strategies

**Small project (1-2 người, 1 môi trường):**

```
project/
├── main.tf
├── variables.tf      # tất cả variables trong 1 file
├── outputs.tf
└── terraform.tfvars  # 1 file values
```

**Medium project (team, multiple environments):**

```
project/
├── main.tf
├── variables.tf
├── outputs.tf
├── locals.tf
├── env/
│   ├── dev.tfvars
│   ├── staging.tfvars
│   └── prod.tfvars
└── modules/
    └── app-service/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

**Enterprise (nhiều teams, nhiều regions):**

```
infrastructure/
├── modules/           # Shared, versioned modules
│   ├── networking/
│   ├── database/
│   └── app-service/
├── live/              # Environment-specific configs
│   ├── dev/
│   │   ├── us-east-1/
│   │   │   ├── main.tf
│   │   │   ├── backend.tf
│   │   │   └── prod.tfvars
│   │   └── eu-west-1/
│   └── prod/
│       ├── us-east-1/
│       └── eu-west-1/
└── global/            # Cross-environment resources (IAM, DNS zones)
```

### 4.3 tfvars Files Strategy

**terraform.tfvars** - auto-loaded, dùng cho defaults:

```hcl
# terraform.tfvars - auto-loaded
project = "myapp"
team    = "platform"
```

**Environment-specific files** - explicit load:

```bash
terraform plan -var-file="env/prod.tfvars"
terraform apply -var-file="env/prod.tfvars"
```

**Ví dụ tfvars files:**

```hcl
# env/dev.tfvars
environment    = "dev"
replica_count  = 1
instance_size  = "small"
enable_alerts  = false
allowed_cidrs  = ["10.0.0.0/8"]

# env/prod.tfvars
environment    = "prod"
replica_count  = 3
instance_size  = "large"
enable_alerts  = true
allowed_cidrs  = ["10.0.0.0/8", "172.16.0.0/12"]
```

**Git considerations:**

```gitignore
# .gitignore
*.tfvars           # Nếu chứa secrets
!env/dev.tfvars    # Nhưng commit non-sensitive dev values
terraform.tfvars   # Luôn ignore tfvars ở root (thường chứa secrets)

# Hoặc: commit tất cả tfvars nhưng không đặt secrets trong đó
# Secrets đến từ CI environment variables: TF_VAR_db_password
```

### 4.4 Validation vs Runtime Checks

```
Validation block:
  - Chạy ở: terraform plan/apply, trước khi tạo bất kỳ resource nào
  - Giới hạn: chỉ access var.x trong cùng variable block (không access locals, data sources)
  - Dùng cho: format checks, allowed values, range checks

Precondition/Postcondition (Terraform 1.2+):
  - Chạy ở: trong lifecycle của resource
  - Access: full access tới data sources, computed values
  - Dùng cho: business rules phức tạp hơn

Runtime errors từ provider:
  - Chậm nhất (sau khi API call)
  - Error message khó đọc hơn
  - Tránh bằng cách validate sớm
```

```hcl
resource "docker_container" "app" {
  # ...

  lifecycle {
    # Precondition: check trước khi tạo
    precondition {
      condition     = var.replica_count <= 5 || local.is_production
      error_message = "High replica count chỉ được phép ở production"
    }

    # Postcondition: check sau khi tạo
    postcondition {
      condition     = self.exit_code == null
      error_message = "Container exited unexpectedly"
    }
  }
}
```

### 4.5 Common Pitfalls

**Pitfall 1: Type mismatch**

```hcl
# BAD
variable "port" {
  type    = string  # ← sai type
  default = "8080"
}

resource "docker_container" "app" {
  ports {
    internal = var.port  # Docker provider expects number, gets string
    # Error: Inappropriate value for attribute "internal": a number is required.
  }
}

# GOOD
variable "port" {
  type    = number
  default = 8080
}
```

**Pitfall 2: Over-parameterization**

```hcl
# BAD - quá nhiều variables, module khó dùng
variable "container_name" {}
variable "container_image" {}
variable "container_cpu_shares" {}
variable "container_memory" {}
variable "container_restart_policy" {}
variable "container_network_mode" {}
variable "container_port_internal" {}
variable "container_port_external" {}
variable "container_env_var_1_name" {}
variable "container_env_var_1_value" {}
# 20+ variables cho 1 container...

# GOOD - group related config
variable "app_name" { type = string }
variable "app_image" { type = string }
variable "environment" { type = string }

# Locals compute the rest from environment + sensible defaults
locals {
  container_config = {
    dev = { cpu = 256, memory = 256 }
    prod = { cpu = 1024, memory = 1024 }
  }
}
```

**Pitfall 3: Circular dependency qua data**

```hcl
# BAD - circular dependency
locals {
  name    = "${local.prefix}-app"   # ← dùng local.prefix
  prefix  = "${local.name}-prefix"  # ← dùng local.name → circular!
}

# GOOD - dependency flow phải là DAG (directed acyclic graph)
locals {
  prefix = "${var.project}-${var.environment}"   # ← chỉ dùng variables
  name   = "${local.prefix}-app"                 # ← dùng local.prefix (đã defined)
}
```

**Pitfall 4: Sensitive data in non-sensitive output**

```hcl
# BAD
output "full_connection_string" {
  # "postgresql://user:PASSWORD@host/db" - password exposed in state và terminal
  value = "postgresql://${var.db_user}:${var.db_password}@${var.db_host}/app"
}

# GOOD - separate sensitive and non-sensitive
output "db_host" {
  value = var.db_host
}

output "connection_string" {
  value     = "postgresql://${var.db_user}:${var.db_password}@${var.db_host}/app"
  sensitive = true  # ẩn trong terminal, vẫn in state
}
```

### 4.6 Best Practices Per Context

| Aspect | Individual | Small Team | Startup | Enterprise |
|--------|------------|------------|---------|------------|
| Variables file | 1 file | Separate files by concern | Modules + tfvars | Strict module interfaces |
| Validation | Basic types | Type + range | Full validation | Validation + policy-as-code (OPA) |
| Sensitive vars | local tfvars | .env + CI secrets | Vault/Secret Manager | Secret Manager + rotation |
| Naming | Consistent snake_case | Team convention | Agreed convention | Enforced by linter (tflint) |
| Outputs | Info outputs | Module outputs | Documented | Versioned contracts |

---

## 5. Hands-on Lab - 60 phút

### Lab: Service Configuration Module với Docker Provider

**Mục tiêu lab**: Tạo module `app-service` simulate cấu hình cho một microservice. Dùng variables, locals, outputs, validation. Deploy thực với Docker provider (không cần cloud account).

**Prerequisites**: Docker Desktop chạy, Terraform đã cài (từ Day 1).

---

### Bước 1: Tạo project structure (5 phút)

```bash
mkdir -p ~/terraform-labs/day-02/modules/app-service
cd ~/terraform-labs/day-02
```

Cấu trúc sẽ là:

```
day-02/
├── main.tf           ← root module, gọi app-service module
├── variables.tf      ← root variables
├── outputs.tf        ← root outputs
├── locals.tf         ← root locals
├── versions.tf       ← provider + terraform version constraints
├── env/
│   ├── dev.tfvars
│   └── prod.tfvars
└── modules/
    └── app-service/
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        └── locals.tf
```

---

### Bước 2: Tạo module - app-service (20 phút)

**`modules/app-service/variables.tf`:**

```hcl
variable "app_name" {
  description = "Application name. Used in container name, labels, and DNS."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,28}[a-z0-9]$", var.app_name))
    error_message = "app_name must be 3-30 chars, lowercase, start with letter, only a-z0-9- allowed."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "app_image" {
  description = "Docker image with tag. Example: nginx:1.25-alpine."
  type        = string

  validation {
    condition     = can(regex(".+:.+", var.app_image))
    error_message = "app_image must include a tag (e.g. nginx:1.25-alpine, not just nginx)."
  }
}

variable "port" {
  description = "Container internal port."
  type        = number
  default     = 80

  validation {
    condition     = var.port >= 1 && var.port <= 65535
    error_message = "port must be between 1 and 65535."
  }
}

variable "external_port" {
  description = "Host port to map to container port. 0 = auto-assign."
  type        = number
  default     = 0

  validation {
    condition     = var.external_port >= 0 && var.external_port <= 65535
    error_message = "external_port must be between 0 and 65535."
  }
}

variable "environment_variables" {
  description = "Environment variables to inject into the container."
  type        = map(string)
  default     = {}
  # No sensitive = true here because map(string) doesn't support it at variable level
  # Pass secrets separately via separate sensitive variables
}

variable "resource_limits" {
  description = "CPU and memory limits for the container."
  type = object({
    cpu_shares = number # Relative CPU weight (1024 = 1 CPU equivalent)
    memory_mb  = number # Memory limit in MB
  })
  default = {
    cpu_shares = 256
    memory_mb  = 256
  }

  validation {
    condition     = var.resource_limits.cpu_shares >= 64 && var.resource_limits.cpu_shares <= 4096
    error_message = "cpu_shares must be between 64 and 4096."
  }

  validation {
    condition     = var.resource_limits.memory_mb >= 64 && var.resource_limits.memory_mb <= 8192
    error_message = "memory_mb must be between 64 and 8192."
  }
}

variable "labels" {
  description = "Additional Docker labels to apply to the container."
  type        = map(string)
  default     = {}
}

variable "restart_policy" {
  description = "Container restart policy."
  type        = string
  default     = "unless-stopped"

  validation {
    condition     = contains(["no", "always", "on-failure", "unless-stopped"], var.restart_policy)
    error_message = "restart_policy must be one of: no, always, on-failure, unless-stopped."
  }
}
```

**`modules/app-service/locals.tf`:**

```hcl
locals {
  # Container naming convention: {app_name}-{environment}
  container_name = "${var.app_name}-${var.environment}"

  # Merge caller-provided labels with mandatory platform labels
  # Caller labels can NOT override platform labels (platform always wins)
  merged_labels = merge(
    var.labels,  # caller-defined labels (lower priority)
    {            # platform mandatory labels (higher priority)
      "app.name"        = var.app_name
      "app.environment" = var.environment
      "managed-by"      = "terraform"
    }
  )

  # Determine if this is a production deployment
  is_production = var.environment == "prod"

  # Minimum replica suggestion (informational, Docker single container doesn't have replicas)
  # In real K8s modules this would control HPA minReplicas
  recommended_replicas = local.is_production ? 3 : 1

  # Resource config with environment-based overrides
  # If explicitly set to non-default, use that. Otherwise apply env defaults.
  effective_resources = {
    cpu_shares = var.resource_limits.cpu_shares
    memory_mb  = var.resource_limits.memory_mb
  }
}
```

**`modules/app-service/main.tf`:**

```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

# Pull the image (Terraform tracks this separately from the container)
resource "docker_image" "app" {
  name         = var.app_image
  keep_locally = true # Don't delete image when container is destroyed
}

resource "docker_container" "app" {
  name    = local.container_name
  image   = docker_image.app.image_id
  restart = var.restart_policy

  # Port mapping
  ports {
    internal = var.port
    external = var.external_port == 0 ? null : var.external_port
  }

  # CPU and memory limits
  cpu_shares = local.effective_resources.cpu_shares
  memory     = local.effective_resources.memory_mb

  # Environment variables
  dynamic "env" {
    for_each = var.environment_variables
    content {
      # Docker expects "KEY=VALUE" format
    }
  }

  # Actually, docker provider uses env as list of strings
  env = [for k, v in var.environment_variables : "${k}=${v}"]

  # Labels
  dynamic "labels" {
    for_each = local.merged_labels
    content {
      label = labels.key
      value = labels.value
    }
  }
}
```

**`modules/app-service/outputs.tf`:**

```hcl
output "container_id" {
  description = "Docker container ID."
  value       = docker_container.app.id
}

output "container_name" {
  description = "Container name (useful for docker exec, logs)."
  value       = docker_container.app.name
}

output "external_port" {
  description = "Host port the container is accessible on."
  value       = docker_container.app.ports[0].external
}

output "service_url" {
  description = "Service URL on localhost."
  value       = "http://localhost:${docker_container.app.ports[0].external}"
}

output "effective_labels" {
  description = "All labels applied to the container (merged)."
  value       = local.merged_labels
}

output "resource_config" {
  description = "Effective resource limits applied."
  value       = local.effective_resources
}

output "recommended_replicas" {
  description = "Recommended replica count for this environment (informational)."
  value       = local.recommended_replicas
}
```

---

### Bước 3: Tạo root module (10 phút)

**`versions.tf`:**

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

provider "docker" {
  # Docker Desktop on Mac/Linux: unix:///var/run/docker.sock (default, no config needed)
  # Docker Desktop on Windows: npipe:////./pipe/docker_engine
  # host = "npipe:////./pipe/docker_engine"  # ← uncomment nếu trên Windows
}
```

**`variables.tf`:**

```hcl
variable "project" {
  description = "Project name. Used in naming and tagging."
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "team" {
  description = "Team responsible for this deployment."
  type        = string
  default     = "platform"
}
```

**`locals.tf`:**

```hcl
locals {
  # Common tags applied to all resources
  common_labels = {
    project = var.project
    team    = var.team
  }

  # Environment-based sizing
  service_sizes = {
    dev = {
      cpu_shares = 256
      memory_mb  = 256
    }
    staging = {
      cpu_shares = 512
      memory_mb  = 512
    }
    prod = {
      cpu_shares = 1024
      memory_mb  = 1024
    }
  }

  current_size = local.service_sizes[var.environment]
}
```

**`main.tf`:**

```hcl
module "api_service" {
  source = "./modules/app-service"

  app_name    = "api"
  environment = var.environment
  app_image   = "nginx:1.25-alpine"
  port        = 80

  resource_limits = {
    cpu_shares = local.current_size.cpu_shares
    memory_mb  = local.current_size.memory_mb
  }

  environment_variables = {
    APP_ENV     = var.environment
    APP_VERSION = "1.0.0"
    LOG_LEVEL   = var.environment == "prod" ? "info" : "debug"
  }

  labels = local.common_labels

  restart_policy = var.environment == "prod" ? "always" : "unless-stopped"
}

module "worker_service" {
  source = "./modules/app-service"

  app_name    = "worker"
  environment = var.environment
  app_image   = "alpine:3.18"
  port        = 8080

  resource_limits = {
    cpu_shares = local.current_size.cpu_shares / 2  # Worker dùng ít resource hơn
    memory_mb  = local.current_size.memory_mb / 2
  }

  environment_variables = {
    APP_ENV   = var.environment
    QUEUE_URL = "redis://redis:6379"
  }

  labels = merge(local.common_labels, {
    "service-type" = "background-worker"
  })
}
```

**`outputs.tf`:**

```hcl
output "api_service_url" {
  description = "API service URL."
  value       = module.api_service.service_url
}

output "api_container_name" {
  description = "API container name (for docker commands)."
  value       = module.api_service.container_name
}

output "worker_container_name" {
  description = "Worker container name."
  value       = module.worker_service.container_name
}

output "environment_summary" {
  description = "Summary of deployed environment."
  value = {
    environment         = var.environment
    api_url             = module.api_service.service_url
    api_resources       = module.api_service.resource_config
    worker_resources    = module.worker_service.resource_config
    api_labels          = module.api_service.effective_labels
  }
}
```

**`env/dev.tfvars`:**

```hcl
project     = "myapp"
environment = "dev"
team        = "platform"
```

**`env/prod.tfvars`:**

```hcl
project     = "myapp"
environment = "prod"
team        = "platform"
```

---

### Bước 4: Chạy lab (15 phút)

**Khởi tạo Terraform:**

```bash
cd ~/terraform-labs/day-02
terraform init
```

Expected output:
```
Initializing the backend...
Initializing modules...
- api_service in modules/app-service
- worker_service in modules/app-service

Initializing provider plugins...
- Finding kreuzwerker/docker versions matching "~> 3.0"...
- Installing kreuzwerker/docker v3.x.x...

Terraform has been successfully initialized!
```

**Validate cấu hình:**

```bash
terraform validate
```

Expected: `Success! The configuration is valid.`

**Plan với dev environment:**

```bash
terraform plan -var-file="env/dev.tfvars"
```

Expected output (rút gọn):
```
Terraform will perform the following actions:

  # module.api_service.docker_container.app will be created
  + resource "docker_container" "app" {
      + cpu_shares = 256
      + image      = (known after apply)
      + memory     = 256
      + name       = "api-dev"
      + restart    = "unless-stopped"
      ...
    }

  # module.worker_service.docker_container.app will be created
  + resource "docker_container" "app" {
      + cpu_shares = 128
      + memory     = 128
      + name       = "worker-dev"
      ...
    }

Plan: 4 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + api_service_url       = (known after apply)
  + api_container_name    = "api-dev"
  + worker_container_name = "worker-dev"
```

**Apply:**

```bash
terraform apply -var-file="env/dev.tfvars"
# Type: yes
```

Expected output sau apply:
```
Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:

api_container_name    = "api-dev"
api_service_url       = "http://localhost:XXXXX"
worker_container_name = "worker-dev"
environment_summary   = {
  "api_labels" = {
    "app.environment" = "dev"
    "app.name"        = "api"
    "managed-by"      = "terraform"
    "project"         = "myapp"
    "team"            = "platform"
  }
  "api_resources" = {
    "cpu_shares" = 256
    "memory_mb"  = 256
  }
  ...
}
```

**Verify containers chạy:**

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

Expected:
```
NAMES         IMAGE                STATUS         PORTS
api-dev       nginx:1.25-alpine    Up X seconds   0.0.0.0:XXXXX->80/tcp
worker-dev    alpine:3.18          Up X seconds   0.0.0.0:XXXXX->8080/tcp
```

**Xem specific output:**

```bash
terraform output api_service_url
terraform output -json environment_summary
```

**Test validation - thử pass invalid value:**

```bash
terraform plan -var-file="env/dev.tfvars" -var='environment=production'
```

Expected error:
```
│ Error: Invalid value for variable
│
│   on variables.tf line X, in variable "environment":
│   X: variable "environment" {
│
│ environment must be one of: dev, staging, prod.
```

**So sánh dev vs prod plan:**

```bash
terraform plan -var-file="env/prod.tfvars"
```

Observe: `cpu_shares = 1024` thay vì `256`, `restart = "always"` thay vì `"unless-stopped"`.

**Cleanup:**

```bash
terraform destroy -var-file="env/dev.tfvars"
# Type: yes
```

---

### Bước 5: Troubleshooting thường gặp

**Lỗi: Docker provider không connect được**

```
Error: Error pinging Docker server: Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.24/ping"
```

Fix (Windows):

```hcl
# versions.tf
provider "docker" {
  host = "npipe:////./pipe/docker_engine"
}
```

Fix (Linux/Mac nếu socket khác):

```bash
export DOCKER_HOST=unix:///var/run/docker.sock
```

**Lỗi: Port đã bị dùng**

```
Error: Error response from daemon: driver failed programming external connectivity:
Bind for 0.0.0.0:80 failed: port is already allocated
```

Fix: Dùng `external_port = 0` để Docker auto-assign port, hoặc chọn port khác.

**Lỗi: Image pull failed**

```
Error: Error response from daemon: pull access denied
```

Fix: Kiểm tra image name và tag. Test manual với `docker pull nginx:1.25-alpine`.

**Lỗi: Type mismatch**

```
Error: Incorrect attribute value type
  The attribute "memory" expects a number value.
```

Fix: Kiểm tra variable type declarations. Dùng `number` không phải `string` cho numeric values.

---

## 6. Kiểm tra hiểu bài

**Câu 1**: Sự khác nhau giữa `variable`, `local`, và `output` về mục đích và flow data?

<details>
<summary>Gợi ý</summary>
Variable là input (từ ngoài vào), local là internal computed value (không expose), output là export (từ trong ra). Data flow: variable → local → output.
</details>

**Câu 2**: Validation block có thể access `module.something` hay `data.something` không? Tại sao?

<details>
<summary>Gợi ý</summary>
Không. Validation chạy trước khi Terraform resolve bất kỳ resource hay data source nào. Nó chỉ có thể access `var.x` trong cùng variable block.
</details>

**Câu 3**: Trong ví dụ `merge(var.labels, { "managed-by" = "terraform" })` vs `merge({ "managed-by" = "terraform" }, var.labels)` - kết quả khác nhau thế nào khi caller cũng set `"managed-by"`?

<details>
<summary>Gợi ý</summary>
merge() ưu tiên argument đứng sau khi có key conflict. Ví dụ đầu: platform label thắng (caller không override được). Ví dụ sau: caller label thắng (nguy hiểm - caller có thể override managed-by).
</details>

**Câu 4**: Tại sao nên set `sensitive = true` cho output chứa password, nhưng điều đó chưa đủ để bảo mật?

<details>
<summary>Gợi ý</summary>
sensitive = true ẩn value trong terminal output. Nhưng state file vẫn chứa plaintext. State file cần được bảo vệ độc lập (encryption, access control).
</details>

**Câu 5**: Khi nào dùng `object` type thay vì nhiều variables riêng lẻ?

<details>
<summary>Gợi ý</summary>
Dùng object khi các fields luôn phải di chuyển cùng nhau, có liên quan logic (database config: host + port + name). Dùng variables riêng lẻ khi từng field có thể được set độc lập bởi các team/context khác nhau.
</details>

---

## 7. Tóm tắt cuối ngày

### Key points

- **HCL** là declarative language với expression engine - không phải YAML hay JSON
- **Variables** = interface (API) của module/configuration. Luôn có `description` và `type`
- **Type constraints** giúp catch errors sớm ở `plan` thay vì provider API call
- **Validation blocks** cho phép custom business rules, fail fast với clear error messages
- **Locals** = computed constants, tránh repeat expressions, đặt tên cho intermediate values
- **Outputs** có 3 mục đích: display, module composition, remote state sharing
- **Sensitive values** cần `sensitive = true` để ẩn khỏi terminal, nhưng state vẫn cần encrypt
- **tfvars files** tách values (what) ra khỏi configuration logic (how)
- **merge()** argument order matters - argument sau override argument trước

### Module interface pattern (quan trọng nhất hôm nay):

```
variables.tf  ← INPUT interface (what callers must/can provide)
outputs.tf    ← OUTPUT interface (what callers can use)
locals.tf     ← INTERNAL computation (hidden from callers)
main.tf       ← IMPLEMENTATION (uses all above)
```

### Outputs của ngày hôm nay

Bạn đã tạo:
- `modules/app-service/` - reusable module với full interface
- Root configuration dùng module cho 2 services
- Validation rules cho tất cả critical inputs
- tfvars files cho dev/prod environments

### Prep cho Day 3: Providers, Resources, Data Sources

Day 3 sẽ đi sâu vào:
- Provider lifecycle và provider configuration
- Resource lifecycle (create, update, destroy, drift)
- Data sources - query existing infrastructure
- Resource dependencies: implicit vs explicit (`depends_on`)
- `for_each` và `count` để tạo nhiều resources

Đọc trước nếu có thể: [Terraform Provider Documentation](https://developer.hashicorp.com/terraform/language/providers)

---

## 8. Tham khảo thêm

- [HCL Language Specification](https://developer.hashicorp.com/terraform/language) - official Terraform docs
- [Input Variables](https://developer.hashicorp.com/terraform/language/values/variables) - full variable reference
- [Type Constraints](https://developer.hashicorp.com/terraform/language/expressions/type-constraints) - type system docs
- [Output Values](https://developer.hashicorp.com/terraform/language/values/outputs) - output reference
- [Local Values](https://developer.hashicorp.com/terraform/language/values/locals) - locals reference
- [Custom Validation Rules](https://developer.hashicorp.com/terraform/language/expressions/custom-conditions) - validation + precondition/postcondition
- [Docker Provider](https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs) - kreuzwerker/docker docs
