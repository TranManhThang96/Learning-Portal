# Day 27: Document — Terraform Fundamentals Reference

## Terraform CLI Cheat Sheet

### Workflow Commands

| Command | Mục đích | Flags thường dùng |
|---------|----------|-------------------|
| `terraform init` | Download providers, init backend | `-upgrade` (update providers) |
| `terraform validate` | Check syntax, không gọi API | |
| `terraform plan` | Preview changes | `-out=plan.tfplan`, `-var="key=val"` |
| `terraform apply` | Execute changes | `plan.tfplan` để apply đúng saved plan đã review |
| `terraform destroy` | Delete all resources | `-auto-approve` chỉ dùng cho lab/automation đã có guardrail |
| `terraform fmt` | Format HCL files | `-check` (CI mode), `-recursive` |
| `terraform output` | Show outputs | `-json`, `-raw` |
| `terraform refresh` | Sync state with reality | (deprecated, use `apply -refresh-only`) |

### State Commands

| Command | Mục đích | Risk Level |
|---------|----------|------------|
| `terraform state list` | List resources in state | LOW |
| `terraform state show <addr>` | Show resource details | LOW |
| `terraform state pull` | Download remote state | LOW |
| `terraform state rm <addr>` | Remove resource from state | MEDIUM |
| `terraform state mv <from> <to>` | Rename/move resource | MEDIUM |
| `terraform import <addr> <id>` | Import thủ công existing resource; Day 28 sẽ dùng `import` block an toàn hơn cho CI/CD | MEDIUM |
| `terraform state push` | Upload state (recovery) | HIGH |
| `terraform force-unlock <id>` | Break state lock | HIGH |

### Workspace Commands

| Command | Mục đích |
|---------|----------|
| `terraform workspace list` | List workspaces |
| `terraform workspace new <name>` | Create workspace |
| `terraform workspace select <name>` | Switch workspace |
| `terraform workspace delete <name>` | Delete workspace |
| `terraform workspace show` | Current workspace |

### Debugging

```bash
# Enable debug logging
export TF_LOG=DEBUG
export TF_LOG_PATH=terraform.log
terraform plan

# Trace level (most verbose)
export TF_LOG=TRACE

# Disable
unset TF_LOG TF_LOG_PATH
```

---

## HCL Syntax Quick Reference

### Data Types

```hcl
# String
name = "hello"

# Number
count = 3
ratio = 1.5

# Boolean
enabled = true

# List
zones = ["us-east-1a", "us-east-1b"]

# Map
tags = {
  Environment = "prod"
  Team        = "platform"
}

# Object (typed map)
variable "config" {
  type = object({
    name    = string
    port    = number
    enabled = bool
  })
}

# Tuple
variable "mixed" {
  type = tuple([string, number, bool])
}

# Set (unique values)
variable "unique_ports" {
  type = set(number)
}
```

### String Interpolation & Templates

```hcl
# Simple interpolation
name = "app-${var.environment}"

# Conditional
size = var.environment == "prod" ? "large" : "small"

# Heredoc
content = <<-EOT
  line 1
  line 2 with ${var.name}
EOT

# Directive (loop in string)
config = <<-EOT
  %{for name in var.names}
  server ${name}
  %{endfor}
EOT

# Directive (conditional in string)
config = <<-EOT
  %{if var.debug}
  debug = true
  %{endif}
EOT
```

### Built-in Functions (Most Used)

| Category | Function | Example | Result |
|----------|----------|---------|--------|
| String | `upper("hello")` | | `"HELLO"` |
| String | `lower("HELLO")` | | `"hello"` |
| String | `replace("hello", "l", "r")` | | `"herro"` |
| String | `join(",", ["a","b"])` | | `"a,b"` |
| String | `split(",", "a,b")` | | `["a","b"]` |
| String | `trimspace(" hi ")` | | `"hi"` |
| String | `format("Hello %s", "world")` | | `"Hello world"` |
| Collection | `length(["a","b"])` | | `2` |
| Collection | `contains(["a","b"], "a")` | | `true` |
| Collection | `merge({a=1}, {b=2})` | | `{a=1, b=2}` |
| Collection | `keys({a=1, b=2})` | | `["a","b"]` |
| Collection | `values({a=1, b=2})` | | `[1, 2]` |
| Collection | `lookup({a=1}, "a", 0)` | | `1` |
| Collection | `flatten([[1,2],[3]])` | | `[1,2,3]` |
| Collection | `distinct([1,1,2])` | | `[1,2]` |
| Numeric | `max(1, 2, 3)` | | `3` |
| Numeric | `min(1, 2, 3)` | | `1` |
| Encoding | `jsonencode({a=1})` | | `"{\"a\":1}"` |
| Encoding | `jsondecode("{\"a\":1}")` | | `{a=1}` |
| Encoding | `base64encode("hello")` | | `"aGVsbG8="` |
| Encoding | `yamlencode({a=1})` | | YAML string |
| Filesystem | `file("path")` | Read file | Content string |
| Filesystem | `templatefile("t.tpl", {v=1})` | Render template | Rendered string |
| Filesystem | `fileexists("path")` | Check exists | `true`/`false` |
| Network | `cidrsubnet("10.0.0.0/16", 8, 1)` | | `"10.0.1.0/24"` |
| Type | `tostring(42)` | | `"42"` |
| Type | `tonumber("42")` | | `42` |
| Type | `tolist(toset([1,1]))` | | `[1]` |
| Hash | `md5("hello")` | | MD5 hash |
| Hash | `sha256("hello")` | | SHA256 hash |

### Expressions

```hcl
# For expression (list)
upper_names = [for n in var.names : upper(n)]

# For expression (map)
name_map = {for n in var.names : n => upper(n)}

# For expression with condition (filter)
prod_instances = [for i in var.instances : i if i.environment == "prod"]

# Splat expression
ids = aws_instance.web[*].id

# Dynamic block
dynamic "ingress" {
  for_each = var.ingress_rules
  content {
    from_port   = ingress.value.port
    to_port     = ingress.value.port
    protocol    = ingress.value.protocol
    cidr_blocks = ingress.value.cidrs
  }
}
```

---

## Resource Block Reference

### Meta-Arguments

```hcl
resource "type" "name" {
  # count — tạo N instances
  count = var.create ? 1 : 0

  # for_each — tạo instance per item
  for_each = toset(["a", "b", "c"])

  # depends_on — explicit dependency
  depends_on = [other_resource.name]

  # provider — specific provider instance
  provider = aws.west

  # lifecycle — control behavior
  lifecycle {
    create_before_destroy = true      # New trước, delete old sau
    prevent_destroy       = true      # Block destroy
    ignore_changes        = [tags]    # Ignore drift on specific attrs
    replace_triggered_by  = [null_resource.trigger]
  }

  # provisioner — run commands (LAST RESORT)
  provisioner "local-exec" {
    command = "echo 'Created'"
  }
}
```

### count vs for_each

| Feature | count | for_each |
|---------|-------|----------|
| Index | Numeric (0, 1, 2) | Key-based |
| Reference | `resource.name[0]` | `resource.name["key"]` |
| Remove middle item | Index shift → recreate | No shift |
| Best for | Simple N copies | Named instances |
| Delete specific | Risky (index shift) | Safe (by key) |

```hcl
# count — khi tất cả instances giống nhau
resource "docker_container" "web" {
  count = 3
  name  = "web-${count.index}"
}

# for_each — khi instances có identity
resource "docker_container" "service" {
  for_each = {
    api    = { port = 8080 }
    worker = { port = 8081 }
    admin  = { port = 8082 }
  }
  
  name = each.key
  # each.value.port
}
```

---

## Provider Reference

### Commonly Used Providers

| Provider | Source | Use Case |
|----------|-------|----------|
| `hashicorp/aws` | AWS cloud resources | EC2, S3, RDS, EKS |
| `hashicorp/google` | GCP resources | GCE, GCS, GKE |
| `hashicorp/azurerm` | Azure resources | VM, Blob, AKS |
| `hashicorp/kubernetes` | K8s resources | Deployments, Services |
| `hashicorp/helm` | Helm charts | Install charts via TF |
| `hashicorp/local` | Local files | Config file management |
| `hashicorp/null` | Null resource | Triggers, provisioners |
| `hashicorp/random` | Random values | Passwords, names |
| `hashicorp/tls` | TLS certs | Self-signed certs |
| `kreuzwerker/docker` | Docker resources | Containers, images |
| `integrations/github` | GitHub resources | Repos, teams, actions |
| `cloudflare/cloudflare` | Cloudflare | DNS, CDN, WAF |

### Provider Configuration Patterns

```hcl
# Single provider
provider "aws" {
  region = "us-east-1"
}

# Multiple provider instances (alias)
provider "aws" {
  alias  = "west"
  region = "us-west-2"
}

resource "aws_instance" "west_server" {
  provider = aws.west
  # ...
}

# Provider version pinning
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"     # >= 5.0.0, < 6.0.0
    }
  }
}
```

---

## .gitignore Template cho Terraform

```gitignore
# Local .terraform directories
**/.terraform/*

# .tfstate files
*.tfstate
*.tfstate.*

# Crash log files
crash.log
crash.*.log

# Exclude all .tfvars files, which are likely to contain sensitive data
*.tfvars
*.tfvars.json

# Ignore override files as they are usually used to override resources locally
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Ignore CLI configuration files
.terraformrc
terraform.rc

# Plan files
*.tfplan

# Lock file — SHOULD be committed for reproducible builds
# Do NOT add: .terraform.lock.hcl
```

---

## Terraform Error Messages Quick Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to instantiate provider` | Provider not initialized | `terraform init` |
| `Error acquiring the state lock` | Someone else is running apply | Wait or `force-unlock` |
| `Cycle detected` | Circular dependency | Remove circular refs |
| `Error: Unsupported attribute` | Wrong attribute name | Check provider docs |
| `Error: Missing required argument` | Required field missing | Add required field |
| `Error: Invalid value for variable` | Validation failed | Fix variable value |
| `Error: Resource already exists` | Resource exists outside TF | Import or rename |
| `Error: Provider configuration not present` | Missing provider block | Add provider config |
| `Error: Inconsistent dependency lock file` | Lockfile mismatch | `terraform init -upgrade` |
| `Error: Failed to load plugin schemas` | Provider version issue | `terraform init -upgrade` |

---

## Terraform Project Checklist

### New Project Setup

- [ ] `.gitignore` configured (state, tfvars, .terraform/)
- [ ] Provider versions pinned (`~> X.Y`)
- [ ] Terraform version pinned (`required_version`)
- [ ] `.terraform.lock.hcl` committed
- [ ] Variables have descriptions and types
- [ ] Variables have validation where appropriate
- [ ] Sensitive variables marked as `sensitive = true`
- [ ] Outputs defined for important values
- [ ] `terraform fmt` passes
- [ ] `terraform validate` passes

### Before Apply

- [ ] `terraform plan` reviewed carefully
- [ ] No unexpected destroy/replace actions
- [ ] State backend configured (if team project)
- [ ] Credentials not hardcoded
- [ ] Tags/labels consistent

