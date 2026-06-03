# Day 2 - Reference Document: HCL Type System & Variable Best Practices

> Quick reference cheat sheet. Dùng khi code, không cần đọc từ đầu.

---

## HCL Type System Reference

### Primitive Types

| Type     | Example Values              | Notes |
|----------|-----------------------------|-------|
| `string` | `"hello"`, `"123"`, `""`   | UTF-8, always quoted |
| `number` | `42`, `3.14`, `-7`, `1e10` | Integer hoặc float |
| `bool`   | `true`, `false`             | Lowercase, unquoted |

### Collection Types

| Type          | Syntax                        | Ordered | Duplicates | Key type |
|---------------|-------------------------------|---------|------------|----------|
| `list(T)`     | `["a", "b", "c"]`            | Yes     | Yes        | Integer index |
| `set(T)`      | `["a", "b", "c"]`            | No      | No         | Value itself |
| `map(T)`      | `{ key = "val" }`            | No      | N/A        | String |
| `tuple([T…])` | `["str", 42, true]`          | Yes     | Yes        | Integer index (mixed types) |
| `object({…})` | `{ name = "x", port = 80 }` | N/A     | N/A        | Named (fixed schema) |

### Type Conversion Functions

```hcl
tostring(42)           # "42"
tonumber("42")         # 42
tobool("true")         # true
tolist(var.my_set)     # set → list (để dùng index)
toset(var.my_list)     # list → set (unique, unordered)
tomap({ a = "1" })     # object → map
```

### Type: any

```hcl
variable "flexible_input" {
  type = any  # Terraform infer type từ giá trị truyền vào
}
# Dùng ít nhất có thể - mất type safety
# Hợp lý khi viết generic utility modules
```

### Structural vs Collection Types

```
Collection types (list, map, set):
  - Tất cả elements cùng type
  - Độ dài thay đổi được
  - list(string), map(number), set(bool)

Structural types (object, tuple):
  - Elements có thể khác type
  - Schema cố định (fixed fields/length)
  - object({ name = string, port = number })
  - tuple([string, number, bool])
```

---

## Variable Declaration Reference

### Đầy đủ các arguments của variable block

```hcl
variable "<NAME>" {
  # Mô tả mục đích - LUÔN LUÔN viết
  description = "string"

  # Type constraint - LUÔN LUÔN khai báo
  type = <TYPE>

  # Default value - optional
  # Không có default = required variable
  default = <VALUE>

  # Ẩn trong terminal output và plan - cho secrets
  sensitive = true | false

  # Validation rules - có thể có nhiều block
  validation {
    condition     = <BOOL_EXPRESSION>
    error_message = "Clear error message for the user."
  }

  # Terraform 1.8+: ephemeral variables (không store vào state)
  # ephemeral = true
}
```

### Variable Attributes và Access

```hcl
# Trong expressions, access variable bằng:
var.<NAME>

# Ví dụ:
var.environment
var.database_config.port      # nested object attribute
var.availability_zones[0]     # list element by index
var.tags["Team"]              # map element by key
```

---

## Locals Reference

```hcl
locals {
  # Một locals block có thể có nhiều local values
  name_prefix = "${var.project}-${var.environment}"
  is_prod     = var.environment == "prod"

  # Locals có thể reference locals khác
  # (nhưng không được circular)
  full_name = "${local.name_prefix}-service"
}

# Access: local.<NAME> (không phải locals.<NAME>)
resource "example" "this" {
  name = local.full_name
}
```

---

## Output Reference

```hcl
output "<NAME>" {
  # Mô tả - LUÔN LUÔN viết
  description = "string"

  # Giá trị expose
  value = <EXPRESSION>

  # Ẩn trong terminal (nhưng vẫn có trong state)
  sensitive = true | false

  # Terraform 1.8+: ephemeral outputs
  # ephemeral = true

  # Dependencies (hiếm dùng, thường Terraform tự detect)
  depends_on = [resource.name]
}
```

### Output CLI Commands

```bash
terraform output                          # Tất cả outputs (non-sensitive)
terraform output <name>                   # Specific output
terraform output -raw <name>             # Plain string, no quotes (dùng trong scripts)
terraform output -json                    # JSON format tất cả outputs
terraform output -json <name>            # JSON format specific output
terraform output -json | jq '.api_url.value'  # Parse với jq
```

---

## tfvars Files Reference

### File types và precedence

```
Precedence (cao → thấp):
  1. terraform plan -var 'key=value'
  2. terraform plan -var-file=FILE
  3. *.auto.tfvars (alphabetical: a.auto.tfvars trước z.auto.tfvars)
  4. terraform.tfvars (auto-loaded)
  5. TF_VAR_<name> environment variable
  6. Default value trong variable block
```

### tfvars syntax

```hcl
# terraform.tfvars hoặc *.tfvars

# String
environment = "prod"

# Number
replica_count = 3

# Bool
enable_https = true

# List
availability_zones = ["us-east-1a", "us-east-1b"]

# Map
tags = {
  Team    = "platform"
  Project = "myapp"
}

# Object
database_config = {
  name     = "prod_db"
  port     = 5432
  replicas = 3
  ssl      = true
}
```

### Environment variables

```bash
# TF_VAR_<variable_name>
export TF_VAR_environment="prod"
export TF_VAR_db_password="secret123"    # Cho sensitive vars
export TF_VAR_replica_count="3"          # String, Terraform tự convert

# Unset khi xong
unset TF_VAR_db_password
```

---

## Validation Best Practices

### Validation patterns thường dùng

```hcl
# 1. Allowed values (enum)
validation {
  condition     = contains(["dev", "staging", "prod"], var.environment)
  error_message = "environment must be one of: dev, staging, prod."
}

# 2. Number range
validation {
  condition     = var.port >= 1024 && var.port <= 65535
  error_message = "port must be between 1024 and 65535 (unprivileged ports)."
}

# 3. String format (regex)
validation {
  condition     = can(regex("^[a-z][a-z0-9-]{2,30}[a-z0-9]$", var.app_name))
  error_message = "app_name must be 4-32 chars, lowercase, start with letter, hyphens allowed."
}

# 4. String không chứa pattern nguy hiểm
validation {
  condition     = !can(regex("--", var.app_name))
  error_message = "app_name must not contain consecutive hyphens."
}

# 5. List not empty
validation {
  condition     = length(var.availability_zones) > 0
  error_message = "At least one availability zone must be specified."
}

# 6. List length limit
validation {
  condition     = length(var.allowed_cidrs) <= 20
  error_message = "Maximum 20 allowed CIDRs supported."
}

# 7. Cross-field validation (trong object variable)
variable "scaling_config" {
  type = object({
    min_replicas = number
    max_replicas = number
  })
  validation {
    condition     = var.scaling_config.min_replicas <= var.scaling_config.max_replicas
    error_message = "min_replicas must be <= max_replicas."
  }
}

# 8. String with image tag (required)
validation {
  condition     = can(regex(".+:.+", var.docker_image))
  error_message = "docker_image must include a tag (e.g. nginx:1.25, not just nginx)."
}
```

### Validation helper functions

```hcl
# can(expr) - returns true nếu expression không throw error
# Dùng với regex(), tonumber(), etc.
can(regex("^[a-z]+$", var.name))   # true nếu match
can(tonumber(var.port_string))      # true nếu string là valid number

# contains(list, value)
contains(["a", "b", "c"], var.choice)

# length(collection)
length(var.items) >= 1

# startswith(str, prefix) - Terraform 1.3+
startswith(var.name, "app-")

# endswith(str, suffix) - Terraform 1.3+
endswith(var.bucket_name, "-data")
```

---

## Common Expressions Cheat Sheet

### String operations

```hcl
locals {
  # Interpolation
  name = "${var.project}-${var.environment}"

  # Upper/lower
  upper_env = upper(var.environment)   # "PROD"
  lower_tag = lower("MyApp")           # "myapp"

  # Replace
  slug = replace(var.display_name, " ", "-")

  # Split / Join
  parts = split("-", "api-service-v2")   # ["api", "service", "v2"]
  joined = join("-", ["api", "service"])  # "api-service"

  # Trim
  clean = trimspace("  hello  ")        # "hello"

  # Format (printf-style)
  version_tag = format("v%d.%d.%d", 1, 2, 3)  # "v1.2.3"
}
```

### Collection operations

```hcl
locals {
  # merge maps (later args win on conflict)
  all_tags = merge(var.common_tags, var.resource_tags)

  # Lookup with default
  instance_type = lookup(local.size_map, var.environment, "t3.micro")

  # Keys / Values
  tag_keys   = keys(var.tags)
  tag_values = values(var.tags)

  # For expression - list
  upper_zones = [for z in var.zones : upper(z)]

  # For expression - map
  tagged_items = { for k, v in var.items : k => "${v}-${var.environment}" }

  # Filter with for
  prod_items = [for item in var.items : item if item.env == "prod"]

  # Flatten nested lists
  all_ips = flatten([for subnet in var.subnets : subnet.ips])

  # Conditional expression
  replica_count = var.environment == "prod" ? 3 : 1

  # Coalesce (first non-null, non-empty)
  effective_name = coalesce(var.override_name, local.default_name)
}
```

### Null and optional

```hcl
variable "optional_setting" {
  type    = string
  default = null  # null = not set
}

locals {
  # Null check
  has_setting = var.optional_setting != null

  # Null-safe coalescence
  active_setting = var.optional_setting != null ? var.optional_setting : "default"

  # Terraform 1.3+: optional() trong object type
}

variable "service_config" {
  type = object({
    name    = string
    port    = optional(number, 80)   # optional với default 80
    enabled = optional(bool, true)   # optional với default true
  })
}
```

---

## Variable Organization Guidelines

### File structure per project size

**Minimal (hobby/POC):**
```
main.tf           # everything in one file is ok for <100 lines
```

**Standard:**
```
main.tf           # resources
variables.tf      # all variable blocks
outputs.tf        # all output blocks
locals.tf         # all locals blocks (nếu có nhiều)
versions.tf       # terraform {} và required_providers {}
```

**Module:**
```
modules/<name>/
├── main.tf
├── variables.tf  # module interface (input)
├── outputs.tf    # module interface (output)
├── locals.tf     # internal computation
└── README.md     # how to use this module
```

**Multi-environment:**
```
├── main.tf
├── variables.tf
├── outputs.tf
├── locals.tf
├── versions.tf
└── env/
    ├── dev.tfvars
    ├── staging.tfvars
    └── prod.tfvars
```

### Nhóm variables theo concern (trong variables.tf)

```hcl
# === REQUIRED: Must be provided ===
variable "app_name" { ... }
variable "environment" { ... }

# === NETWORKING ===
variable "vpc_id" { ... }
variable "subnet_ids" { ... }

# === COMPUTE ===
variable "instance_type" { ... }
variable "replica_count" { ... }

# === DATABASE ===
variable "db_instance_class" { ... }
variable "db_name" { ... }

# === FEATURE FLAGS ===
variable "enable_monitoring" { ... }
variable "enable_backups" { ... }

# === SECRETS (sensitive = true) ===
variable "db_password" { ... }
variable "api_key" { ... }
```

---

## Anti-patterns Reference

| Anti-pattern | Problem | Fix |
|---|---|---|
| No `description` | Ai dùng module phải đọc source code | Luôn viết description rõ ràng |
| No `type` | Late type errors, unclear interface | Luôn khai báo type |
| `type = string` cho số | Type mismatch errors từ provider | Dùng `type = number` |
| Hardcode `default = "prod"` | AI dùng prod values trong dev | Default về safe value (dev/false/0) |
| Variable cho mọi thứ | Module cực kỳ phức tạp để dùng | Dùng locals cho computed values |
| `sensitive = false` cho passwords | Secrets hiện trong logs | Set `sensitive = true` |
| Secrets trong tfvars (committed) | Security breach | Dùng TF_VAR_ env vars hoặc Vault |
| Circular locals | Terraform error, khó debug | Locals phải là DAG |
| Output không có `description` | Caller không biết dùng output để làm gì | Luôn viết description |
| `type = any` mọi nơi | Mất type safety | Chỉ dùng `any` cho generic utilities |
