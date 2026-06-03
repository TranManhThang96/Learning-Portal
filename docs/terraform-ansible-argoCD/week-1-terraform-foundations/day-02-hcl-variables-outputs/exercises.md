# Day 2 - Exercises: HCL, Variables, Outputs, Locals

> **Level**: Intermediate to Advanced | **Estimated time**: 60-90 phút thêm ngoài lab chính

Các bài tập này build on top của lab chính. Hoàn thành lab trước khi làm exercises.

---

## Exercise 1: Complex Type Variables (20 phút)

**Mục tiêu**: Thành thạo `object`, `list(object)`, `map(object)`.

Tạo file `~/terraform-labs/day-02-ex1/variables.tf` với các variables sau:

### 1.1 Multi-service configuration

Khai báo variable `services` có type là `map(object(...))` để configure nhiều services cùng lúc:

```hcl
variable "services" {
  description = "Map of services to deploy. Key = service name."
  type = map(object({
    image         = string
    port          = number
    replicas      = number
    cpu_shares    = number
    memory_mb     = number
    health_check  = optional(object({
      path     = string
      interval = number  # seconds
    }), null)
    env_vars = optional(map(string), {})
  }))
}
```

Viết tfvars file với ít nhất 3 services:

```hcl
# ex1.tfvars - điền vào
services = {
  api = {
    image      = "nginx:1.25-alpine"
    port       = 80
    replicas   = 2
    cpu_shares = 512
    memory_mb  = 512
    health_check = {
      path     = "/health"
      interval = 30
    }
    env_vars = {
      LOG_LEVEL = "info"
    }
  }
  worker = {
    # ... bạn tự điền
  }
  scheduler = {
    # ... bạn tự điền
  }
}
```

### 1.2 Locals để transform services map

Viết `locals.tf` tính toán:

```hcl
locals {
  # 1. Tất cả service names (list of strings)
  service_names = ___

  # 2. Chỉ services có health check configured (filtered map)
  monitored_services = ___

  # 3. Tổng memory của tất cả services (số)
  total_memory_mb = ___

  # 4. Map từ service name sang endpoint URL format "http://localhost:{port}"
  service_urls = ___

  # 5. Services nào cần replicas > 1 (list of service names)
  scaled_services = ___
}
```

**Gợi ý expressions:**

```hcl
# Keys của map
keys(var.services)

# Filter map: for expression với if
{ for name, svc in var.services : name => svc if svc.replicas > 1 }

# Sum với for + sum... Terraform không có sum() built-in
# Dùng: [for svc in var.services : svc.memory_mb]
# Rồi dùng: sum([...])
```

<details>
<summary>Đáp án tham khảo</summary>

```hcl
locals {
  service_names = keys(var.services)

  monitored_services = {
    for name, svc in var.services : name => svc
    if svc.health_check != null
  }

  total_memory_mb = sum([for svc in var.services : svc.memory_mb])

  service_urls = {
    for name, svc in var.services : name => "http://localhost:${svc.port}"
  }

  scaled_services = [
    for name, svc in var.services : name
    if svc.replicas > 1
  ]
}
```
</details>

---

## Exercise 2: Validation Scenarios (20 phút)

**Mục tiêu**: Viết validation rules cho các trường hợp thực tế.

### 2.1 Validate CIDR block

```hcl
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string

  # Challenge: Validate rằng:
  # 1. Format hợp lệ: x.x.x.x/y
  # 2. Prefix length phải từ /8 đến /28
  # 3. Không dùng public IP ranges (không bắt đầu bằng 8. hoặc 1.)
  # Gợi ý: can(regex(...)), split()
  validation { ... }
}
```

<details>
<summary>Gợi ý</summary>

```hcl
validation {
  condition     = can(regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/\\d{1,2}$", var.vpc_cidr))
  error_message = "vpc_cidr must be a valid CIDR notation (e.g. 10.0.0.0/16)."
}

validation {
  condition = (
    tonumber(split("/", var.vpc_cidr)[1]) >= 8 &&
    tonumber(split("/", var.vpc_cidr)[1]) <= 28
  )
  error_message = "vpc_cidr prefix length must be between /8 and /28."
}

validation {
  condition     = !startswith(var.vpc_cidr, "8.") && !startswith(var.vpc_cidr, "1.")
  error_message = "Use private IP ranges (10.x, 172.x, 192.168.x)."
}
```
</details>

### 2.2 Validate semantic version

```hcl
variable "app_version" {
  description = "Application version in semver format (e.g. 1.2.3)"
  type        = string

  # Challenge: Validate semver format: MAJOR.MINOR.PATCH
  # Có thể có prefix "v" (v1.2.3 cũng ok)
  # Không chấp nhận: "latest", "1.2", "1.2.3.4"
  validation { ... }
}
```

<details>
<summary>Gợi ý</summary>

```hcl
validation {
  condition     = can(regex("^v?\\d+\\.\\d+\\.\\d+$", var.app_version))
  error_message = "app_version must be semver format (e.g. 1.2.3 or v1.2.3). Tags 'latest' or partial versions not allowed."
}
```
</details>

### 2.3 Validate cross-field consistency trong object

```hcl
variable "scaling_policy" {
  type = object({
    min_replicas     = number
    max_replicas     = number
    target_cpu_pct   = number  # 1-100
    scale_up_delay   = number  # seconds
    scale_down_delay = number  # seconds
  })

  # Challenge: Validate tất cả các constraints:
  # 1. min_replicas >= 1
  # 2. max_replicas >= min_replicas
  # 3. max_replicas <= 50
  # 4. target_cpu_pct between 10 and 90
  # 5. scale_down_delay >= scale_up_delay (cool down lâu hơn scale up)
  validation { ... }
  validation { ... }
  # ... thêm validations
}
```

---

## Exercise 3: Output Patterns (15 phút)

**Mục tiêu**: Hiểu các output patterns dùng trong thực tế.

### 3.1 Structured outputs cho CI/CD

Trong CI/CD pipeline, Jenkins/GitHub Actions thường cần read outputs. Viết outputs cho pattern sau:

```hcl
# main.tf tạo các resources sau (giả sử đã có):
# - docker_container.api (name, ports)
# - docker_container.worker (name, ports)
# - docker_image.api (id)

# outputs.tf - viết các outputs:

# 1. deployment_manifest: object chứa tất cả info CI/CD cần
#    { version, environment, services: { api: {...}, worker: {...} } }
output "deployment_manifest" {
  value = {
    # ... bạn tự viết
  }
}

# 2. health_check_urls: list các URLs cần test sau deploy
output "health_check_urls" {
  value = [
    # format: "http://localhost:{port}/health"
  ]
}

# 3. docker_commands: map các lệnh docker hữu ích
output "docker_commands" {
  value = {
    logs_api    = "docker logs -f api-${var.environment}"
    exec_api    = "docker exec -it api-${var.environment} sh"
    logs_worker = "docker logs -f worker-${var.environment}"
  }
}
```

### 3.2 Sensitive output handling

```hcl
# Scenario: Module tạo database container với credentials
# Viết outputs theo đúng sensitive/non-sensitive split

variable "db_user"     { type = string }
variable "db_password" { type = string; sensitive = true }
variable "db_name"     { type = string }

# Output 1: non-sensitive connection info (host, port, db name)
output "db_connection_info" { ... }

# Output 2: full connection string - PHẢI sensitive
output "db_connection_string" { ... }

# Output 3: env var format cho ứng dụng biết kết nối
# "DB_URL=postgresql://user:pass@host:port/db"
output "db_env_var" { ... }
```

Câu hỏi: Khi bạn chạy `terraform output db_connection_string`, thấy gì? Làm thế nào để xem giá trị thực?

<details>
<summary>Đáp án</summary>

```bash
# Outputs với sensitive = true hiện như sau:
terraform output db_connection_string
# (sensitive value, use `terraform output -raw db_connection_string` to access)

# Xem giá trị thực:
terraform output -raw db_connection_string
# postgresql://admin:secretpass@localhost:5432/mydb

# Hoặc JSON (vẫn hiện value trong JSON):
terraform output -json db_connection_string
```
</details>

---

## Exercise 4: Locals Pipeline (20 phút)

**Mục tiêu**: Build complex transformation pipelines với locals.

**Scenario**: Tạo Nginx configuration từ service definitions.

```hcl
# Đầu vào (variables)
variable "upstream_services" {
  type = map(object({
    host     = string
    port     = number
    weight   = number   # load balancing weight 1-100
    path     = string   # URL path prefix, e.g. "/api/v1"
    healthy  = bool
  }))
  default = {
    api_v1 = {
      host    = "10.0.1.10"
      port    = 8080
      weight  = 70
      path    = "/api/v1"
      healthy = true
    }
    api_v2 = {
      host    = "10.0.1.11"
      port    = 8080
      weight  = 30
      path    = "/api/v2"
      healthy = true
    }
    legacy = {
      host    = "10.0.1.5"
      port    = 8000
      weight  = 100
      path    = "/legacy"
      healthy = false  # unhealthy - không route traffic đến đây
    }
  }
}

# Challenge: Viết locals để compute:
locals {
  # 1. Chỉ healthy services
  healthy_services = ___

  # 2. Upstream entries format cho nginx.conf
  # ["server 10.0.1.10:8080 weight=70;", "server 10.0.1.11:8080 weight=30;"]
  nginx_upstream_entries = ___

  # 3. Location blocks format
  # { "/api/v1" = "proxy_pass http://10.0.1.10:8080;", ... }
  nginx_locations = ___

  # 4. Total weight của healthy services (cho validation)
  total_weight = ___

  # 5. Nginx upstream block (multi-line string)
  nginx_upstream_block = <<-EOT
    upstream backend {
      %{ for entry in local.nginx_upstream_entries ~}
      ${entry}
      %{ endfor ~}
    }
  EOT
}
```

<details>
<summary>Đáp án tham khảo</summary>

```hcl
locals {
  healthy_services = {
    for name, svc in var.upstream_services : name => svc
    if svc.healthy
  }

  nginx_upstream_entries = [
    for name, svc in local.healthy_services :
    "server ${svc.host}:${svc.port} weight=${svc.weight};"
  ]

  nginx_locations = {
    for name, svc in local.healthy_services :
    svc.path => "proxy_pass http://${svc.host}:${svc.port};"
  }

  total_weight = sum([
    for svc in local.healthy_services : svc.weight
  ])

  nginx_upstream_block = <<-EOT
    upstream backend {
      %{~ for entry in local.nginx_upstream_entries ~}
      ${entry}
      %{~ endfor ~}
    }
  EOT
}
```
</details>

---

## Exercise 5: Module Interface Design (30 phút)

**Mục tiêu**: Thiết kế clean module interface - quan trọng nhất trong Terraform.

**Scenario**: Bạn được yêu cầu tạo module `monitoring-stack` deploy Prometheus + Grafana. Senior dev khác sẽ dùng module của bạn.

### 5.1 Thiết kế variables.tf

Không nhìn gợi ý trước. Tự thiết kế variables cho module này. Sau đó so sánh:

**Câu hỏi cần trả lời trước khi code:**
1. Caller cần control những gì?
2. Module nên tự decide những gì (dùng locals)?
3. Gì nên có default và giá trị default hợp lý là gì?
4. Gì là required (không có default)?
5. Gì là sensitive?

**Gợi ý variables hợp lý:**

```hcl
# Required (no default)
variable "environment" { ... }      # dev/staging/prod
variable "app_name" { ... }         # tên app đang monitor

# Optional với sensible defaults
variable "prometheus_port" { ... }  # default 9090
variable "grafana_port" { ... }     # default 3000
variable "retention_days" { ... }   # default 15 (prod: 90)
variable "admin_password" {         # sensitive, no default = required
  sensitive = true
  ...
}

# Feature flags
variable "enable_alerting" { ... }  # default false (opt-in)
variable "slack_webhook_url" { ... } # required if enable_alerting = true
                                    # Challenge: làm thế nào validate conditional requirement?
```

### 5.2 Conditional validation challenge

```hcl
# Challenge: Validate rằng slack_webhook_url phải có giá trị
# nếu enable_alerting = true
# Nhưng có thể null nếu enable_alerting = false

variable "enable_alerting" {
  type    = bool
  default = false
}

variable "slack_webhook_url" {
  type    = string
  default = null
  # Làm thế nào validate: required when enable_alerting = true?
}
```

<details>
<summary>Gợi ý</summary>

```hcl
variable "slack_webhook_url" {
  type    = string
  default = null

  validation {
    condition = (
      !var.enable_alerting ||                          # alerting disabled = ok
      (var.enable_alerting && var.slack_webhook_url != null)  # alerting enabled = required
    )
    error_message = "slack_webhook_url is required when enable_alerting = true."
  }
}
```

Hoặc dùng precondition trong resource (Terraform 1.2+) để access cả hai variables.
</details>

### 5.3 Outputs design

Viết outputs cho `monitoring-stack` module mà caller (root module) sẽ cần:

```hcl
# outputs.tf cho monitoring-stack module
# Caller cần biết:
# - URLs để access Prometheus UI và Grafana UI
# - Container names (để debug với docker logs)
# - Grafana admin credentials (sensitive!)
# - Health check endpoints

output "prometheus_url" { ... }
output "grafana_url" { ... }
output "grafana_admin_user" { ... }
output "grafana_admin_password" { ... }  # sensitive!
output "container_names" { ... }         # { prometheus = "...", grafana = "..." }
output "health_endpoints" { ... }        # list of URLs to check
```

---

## Challenge: Refactor Anti-patterns (15 phút)

Refactor đoạn code sau - tìm và fix tất cả anti-patterns:

```hcl
# BROKEN CODE - có nhiều vấn đề, tìm và fix hết

variable "x" {
  default = "prod"
}

variable "password" {
  type = string
  default = "changeme123"
}

variable "config" {
  type = any
}

locals {
  a = "${local.b}-prefix"
  b = "${local.a}-server"
}

output "stuff" {
  value = var.password
}

output "url" {
  value = "http://app.internal:8080"
}
```

**Danh sách vấn đề cần tìm (8 vấn đề):**

1. Variable `x` - tên không rõ ràng
2. Variable `x` - không có `description`
3. Variable `x` - không có `type`
4. Variable `x` - default là `"prod"` (nguy hiểm)
5. Variable `password` - sensitive credential không có `sensitive = true`
6. Variable `password` - có default cho password (bao giờ cũng sai)
7. Variable `config` - `type = any` che giấu interface
8. Locals `a` và `b` - circular dependency
9. Output `stuff` - tên không rõ ràng
10. Output `stuff` - expose sensitive value mà không có `sensitive = true`
11. Output `url` - hardcode URL thay vì reference resource

<details>
<summary>Fixed version</summary>

```hcl
variable "environment" {
  description = "Deployment environment. Controls resource sizing and behavior."
  type        = string
  default     = "dev"  # safe default

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "db_password" {
  description = "Database master password. Provide via TF_VAR_db_password env var."
  type        = string
  sensitive   = true
  # No default for secrets
}

variable "app_config" {
  description = "Application configuration settings."
  type = object({
    name    = string
    version = string
    port    = number
  })
  # Specific type, not any
}

locals {
  # Fixed: no circular dependency
  name_prefix = "${var.environment}-server"
  full_name   = "${local.name_prefix}-${var.app_config.name}"
}

output "db_connection_string" {
  description = "Database connection string for the application."
  value       = "postgresql://app:${var.db_password}@db:5432/app"
  sensitive   = true  # Mark as sensitive
}

output "service_url" {
  description = "Application service URL."
  value       = "http://localhost:${docker_container.app.ports[0].external}"
  # References actual resource, not hardcode
}
```
</details>

---

## Self-Assessment Checklist

Sau khi hoàn thành tất cả exercises, check các items sau:

- [ ] Tôi có thể đọc complex HCL expressions mà không cần reference docs
- [ ] Tôi khai báo variables với `description`, `type`, và validation khi cần
- [ ] Tôi biết khi nào dùng `object` vs nhiều variables riêng lẻ
- [ ] Tôi biết `merge()` argument order ảnh hưởng gì đến kết quả
- [ ] Tôi có thể viết `for` expressions để filter và transform collections
- [ ] Tôi hiểu `sensitive = true` ẩn gì và không ẩn gì
- [ ] Tôi không có circular dependency trong locals
- [ ] Tôi có thể thiết kế clean module interface (variables + outputs)
- [ ] Tôi biết dùng `terraform output -raw` để lấy sensitive values trong scripts
- [ ] Tôi hiểu tfvars file precedence order
