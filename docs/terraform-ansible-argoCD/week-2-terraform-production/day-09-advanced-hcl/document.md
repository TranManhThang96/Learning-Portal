# Document: Advanced HCL Reference - Day 9

**Muc dich:** Tham khao nhanh cho for_each patterns, dynamic blocks, complex types, va built-in functions. Dung trong luc code, khong phai de doc tuyen tinh.

---

## 1. count vs for_each - Quick Decision Flowchart

```
Ban can tao nhieu instance cua cung mot resource?
            |
            v
So luong co the thay doi theo thoi gian?
    |                       |
   YES                      NO
    |                       |
    v                       v
Resources co        Dung count = N
unique identity?    (don gian hon)
(ten, role, config
 rieng biet)
    |           |
   YES          NO
    |           |
    v           v
Dung         count = length(list)
for_each     (chap nhan index)
(stable key)

Them:
- Boolean toggle resource?  -> count = var.enable ? 1 : 0
- Named resources?          -> for_each = map(...)
- Set cua strings?          -> for_each = toset(list)
- Has nested config?        -> for_each + dynamic block
```

---

## 2. for_each Patterns Reference

### Pattern A - for_each voi map(string)

```hcl
variable "bucket_names" {
  type    = map(string)
  default = {
    "logs"    = "my-app-logs"
    "backups" = "my-app-backups"
    "assets"  = "my-app-assets"
  }
}

resource "aws_s3_bucket" "this" {
  for_each = var.bucket_names

  bucket = each.value          # "my-app-logs", "my-app-backups", ...
  # each.key = "logs", "backups", "assets"
}

# Reference: aws_s3_bucket.this["logs"].id
```

### Pattern B - for_each voi map(object)

```hcl
variable "subnets" {
  type = map(object({
    cidr   = string
    az     = string
    public = bool
  }))
}

resource "aws_subnet" "this" {
  for_each = var.subnets

  cidr_block              = each.value.cidr    # Object field access
  availability_zone       = each.value.az
  map_public_ip_on_launch = each.value.public
  vpc_id                  = aws_vpc.main.id

  tags = { Name = each.key }    # each.key = "public-1a", "private-1b", ...
}

# Reference: aws_subnet.this["public-1a"].id
```

### Pattern C - for_each voi set(string)

```hcl
variable "environments" {
  type    = set(string)
  default = ["dev", "staging", "prod"]
}

resource "aws_iam_role" "deployer" {
  for_each = var.environments

  name = "deployer-${each.key}"    # each.key == each.value khi dung set
  # each.value cung = "dev", "staging", "prod" (giong each.key)
}
```

### Pattern D - for_each tu list (chuyen doi)

```hcl
variable "service_names" {
  type    = list(string)
  default = ["api", "worker", "scheduler"]
}

# Option 1: toset() - mat order, loai bo duplicates
resource "aws_security_group" "this" {
  for_each = toset(var.service_names)
  name     = "${each.key}-sg"
}

# Option 2: for expression -> map (giu them info)
locals {
  service_map = { for name in var.service_names : name => {
    port = lookup(var.service_ports, name, 8080)
  }}
}

resource "aws_security_group" "this" {
  for_each = local.service_map
  name     = "${each.key}-sg"
  # each.value.port = port number
}
```

### Pattern E - for_each voi complex flat map (flatten)

```hcl
# Input: nested structure
variable "service_rules" {
  type = map(list(number))
  default = {
    "api"    = [80, 443, 8080]
    "worker" = [8081, 9090]
    "admin"  = [8082]
  }
}

# Flatten thanh map voi composite key
locals {
  all_rules = merge([
    for service, ports in var.service_rules : {
      for port in ports :
      "${service}-${port}" => {    # Composite key: "api-80", "api-443", ...
        service = service
        port    = port
      }
    }
  ]...)    # ... = unpack list of maps
}

resource "aws_security_group_rule" "this" {
  for_each = local.all_rules

  type              = "ingress"
  from_port         = each.value.port
  to_port           = each.value.port
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/8"]
  security_group_id = aws_security_group.app.id
  description       = "Rule for ${each.value.service} port ${each.value.port}"
}
# State: aws_security_group_rule.this["api-80"], ["api-443"], ["worker-8081"], ...
```

### Pattern F - for_each tren module

```hcl
variable "environments" {
  type = map(object({
    vpc_cidr     = string
    subnet_count = number
  }))
}

module "vpc" {
  for_each = var.environments
  source   = "./modules/vpc"

  environment  = each.key
  vpc_cidr     = each.value.vpc_cidr
  subnet_count = each.value.subnet_count
}

# Reference: module.vpc["prod"].vpc_id
# Output map: { for env, v in module.vpc : env => v.vpc_id }
```

---

## 3. dynamic Block Patterns Reference

### Pattern A - Basic dynamic ingress

```hcl
variable "ingress_rules" {
  type = list(object({
    port     = number
    protocol = string
    cidrs    = list(string)
  }))
}

resource "aws_security_group" "this" {
  name   = "app-sg"
  vpc_id = var.vpc_id

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidrs
    }
  }
}
```

### Pattern B - Custom iterator label

```hcl
dynamic "ingress" {
  for_each = var.ingress_rules
  iterator = rule          # "rule" thay vi "ingress" (default)
  content {
    from_port   = rule.value.port     # rule.value, rule.key
    to_port     = rule.value.port
    protocol    = rule.value.protocol
    cidr_blocks = rule.value.cidrs
  }
}
```

### Pattern C - Conditional dynamic block

```hcl
# Them block chi khi dieu kien = true
resource "aws_cloudwatch_metric_alarm" "this" {
  alarm_name = "my-alarm"
  # ...

  # Chi them ok_actions khi co notification config
  dynamic "ok_actions" {
    for_each = var.notification_arn != null ? [var.notification_arn] : []
    content {
      # Content duoc generate 0 lan (empty list) hoac 1 lan
    }
  }
}

# Pattern: for_each = condition ? [sentinel_value] : []
# Sentinel value la bat ky gia tri nao (thuong la 1 hoac true hoac object)
# Muc dich: tao dung 1 block khi dieu kien true, 0 block khi false
```

### Pattern D - Nested dynamic blocks

```hcl
variable "load_balancer_listeners" {
  type = map(object({
    port     = number
    protocol = string
    rules = list(object({
      path_pattern = string
      target_group = string
      priority     = number
    }))
  }))
}

resource "aws_lb_listener" "this" {
  for_each = var.load_balancer_listeners

  load_balancer_arn = aws_lb.main.arn
  port              = each.value.port
  protocol          = each.value.protocol

  default_action {
    type = "forward"
  }
}

resource "aws_lb_listener_rule" "this" {
  # Flatten listeners + rules thanh flat map
  for_each = merge([
    for listener_name, listener in var.load_balancer_listeners : {
      for rule in listener.rules :
      "${listener_name}-${rule.priority}" => merge(rule, { listener = listener_name })
    }
  ]...)

  listener_arn = aws_lb_listener.this[each.value.listener].arn
  priority     = each.value.priority

  condition {
    path_pattern {
      values = [each.value.path_pattern]
    }
  }

  action {
    type             = "forward"
    target_group_arn = each.value.target_group
  }
}
```

### Pattern E - dynamic tags (AWS provider)

```hcl
variable "extra_tags" {
  type    = map(string)
  default = {}
}

resource "aws_instance" "this" {
  ami           = var.ami_id
  instance_type = var.instance_type

  # Dung dynamic cho tags block trong mot so resource types
  dynamic "tag" {
    for_each = merge(local.common_tags, var.extra_tags)
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true    # Cho AutoScaling group
    }
  }
}
```

---

## 4. for Expression Cheat Sheet

### List transformation

```hcl
locals {
  # [for item in list : transform(item)]
  upper_names = [for name in var.names : upper(name)]
  # ["api"] -> ["API"]

  # [for item in list : transform if condition]
  prod_services = [for s in var.services : s if s.env == "prod"]

  # [for idx, item in list : ...]  // idx = index
  indexed = [for i, name in var.names : "${i}-${name}"]
  # ["0-api", "1-worker", "2-admin"]
}
```

### Map transformation

```hcl
locals {
  # {for item in list : key_expr => value_expr}
  name_to_index = { for i, name in var.names : name => i }
  # {"api" = 0, "worker" = 1, "admin" = 2}

  # {for key, val in map : new_key => new_val}
  upper_map = { for k, v in var.service_configs : upper(k) => v }

  # {for key, val in map : key => val if condition}
  prod_configs = {
    for env, config in var.configs : env => config
    if config.replicas >= 3
  }
}
```

### Extract values from for_each resources

```hcl
# Lay tat ca IDs tu for_each resource
output "subnet_ids" {
  value = { for k, v in aws_subnet.this : k => v.id }
  # {"public-1a" = "subnet-abc", "private-1a" = "subnet-def"}
}

# Lay list cua IDs (bo keys)
output "public_subnet_id_list" {
  value = [
    for k, v in aws_subnet.this : v.id
    if var.subnets[k].public == true
  ]
  # ["subnet-abc", "subnet-def"]
}

# Lay values cua map
output "all_ids" {
  value = values({ for k, v in aws_subnet.this : k => v.id })
  # ["subnet-abc", "subnet-def", ...]  // values() tra ve list of values
}
```

### flatten() voi nested for

```hcl
locals {
  # flatten([[1,2], [3,4]]) = [1, 2, 3, 4]
  all_ports = flatten([
    for service, config in var.services :
    config.allowed_ports    # List of ports per service
  ])

  # flatten + for tao flat list of objects
  all_rules_list = flatten([
    for service, config in var.service_rules : [
      for rule in config.ingress : {
        service = service
        port    = rule.port
        cidr    = rule.cidr
      }
    ]
  ])
}
```

---

## 5. Built-in Functions Quick Reference

### merge()

```hcl
# merge(map1, map2, ...) - key conflict: LAST wins
locals {
  # Base tags + environment tags + resource-specific tag
  tags = merge(
    { Project = "myapp", ManagedBy = "terraform" },  # override boi step sau
    var.env_tags,                                      # override boi step sau
    { Name = "${var.project}-vpc" }                   # highest priority
  )

  # Merge list of maps (dung cho flatten patterns)
  combined = merge([
    for env in var.environments : { "${env}" = lookup(var.configs, env, {}) }
  ]...)    # ... = spread operator (unpack list)
}
```

### lookup()

```hcl
locals {
  # lookup(map, key, default)  - safe access, khong throw error
  instance_type = lookup(var.instance_types, var.environment, "t3.micro")

  # KHAC voi direct index:
  # var.instance_types[var.environment]   <- throw error neu key khong ton tai
  # lookup(var.instance_types, var.environment, "t3.micro")  <- return "t3.micro"

  # Dung cho multi-level config:
  db_port = lookup(
    lookup(var.db_configs, var.environment, {}),
    "port",
    5432
  )
}
```

### try()

```hcl
locals {
  # try(expr1, expr2, ...) - tra ve ket qua expr dau tien khong throw error
  # Dung cho optional nested attributes

  # Simple optional field
  log_level = try(var.config.log_level, "info")

  # Deep nested optional
  alarm_topic = try(
    var.monitoring.alerts.sns_topic_arn,
    var.default_sns_arn,
    null                    # fallback cuoi cung: null
  )

  # Optional field trong for_each object
  # Neu "timeout" co the khong ton tai trong tung config object
  service_timeouts = {
    for name, config in var.services :
    name => try(config.timeout, 30)    # Default 30 neu khong co timeout field
  }
}
```

### can()

```hcl
# can(expr) tra ve true/false - dung trong validation
variable "vpc_cidr" {
  type = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "Must be valid CIDR notation."
  }
}

variable "environment" {
  type = string

  validation {
    # can voi regex check
    condition     = can(regex("^(dev|staging|prod)$", var.environment))
    error_message = "Must be dev, staging, or prod."
  }
}

# can() vs try():
# can(x)     -> bool (co x tinh duoc khong?)
# try(x, y)  -> gia tri (neu x fail, dung y)
```

### Cac functions tien ich khac

```hcl
locals {
  # cidrsubnet(prefix, newbits, netnum) - tinh subnet CIDR
  # Hay dung khi auto-calculate subnet CIDRs tu VPC CIDR
  subnet_cidrs = [
    cidrsubnet("10.0.0.0/16", 8, 0),   # "10.0.0.0/24"
    cidrsubnet("10.0.0.0/16", 8, 1),   # "10.0.1.0/24"
    cidrsubnet("10.0.0.0/16", 8, 100), # "10.0.100.0/24"
  ]

  # cidrhost(prefix, hostnum) - tinh host IP trong subnet
  gateway_ip = cidrhost("10.0.1.0/24", 1)  # "10.0.1.1"

  # toset(), tolist(), tomap() - type conversion
  az_set  = toset(["ap-southeast-1a", "ap-southeast-1b"])  # list -> set
  az_list = tolist(toset(["b", "a", "b"]))                 # set -> list: ["a", "b"] (sorted, deduped)

  # contains(list|set, value)
  is_prod = contains(["prod", "production"], var.environment)

  # flatten(list_of_lists)
  all_cidrs = flatten([["10.0.1.0/24", "10.0.2.0/24"], ["10.0.11.0/24"]])
  # = ["10.0.1.0/24", "10.0.2.0/24", "10.0.11.0/24"]

  # distinct(list) - loai bo duplicates, giu order
  unique_azs = distinct(["a", "b", "a", "c"])  # ["a", "b", "c"]

  # keys(map), values(map)
  env_names = keys(var.environment_configs)    # ["dev", "prod", "staging"]
  env_cfgs  = values(var.environment_configs)  # [obj, obj, obj]

  # length(list|map|set|string)
  subnet_count = length(var.subnets)           # so luong subnet

  # slice(list, start, end)
  first_two_azs = slice(var.availability_zones, 0, 2)

  # concat(list1, list2)
  all_subnets = concat(var.public_subnets, var.private_subnets)

  # format(template, args...)
  bucket_name = format("%s-%s-%s", var.project, var.environment, var.region)

  # replace(string, old, new)
  slug = replace(lower(var.project_name), " ", "-")

  # templatefile(path, vars) - render template file
  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    environment = var.environment
    region      = data.aws_region.current.name
  })
}
```

---

## 6. Complex Types - Reference va Use Cases

### object vs map - Khi nao dung cai nao

```
object({...}):
  - Schema co dinh, biet truoc o compile time
  - Cac field co the co type khac nhau (string, number, bool, list, ...)
  - Dung cho: config group co cau truc ro rang
  - Vi du: database_config, vpc_config, service_spec

map(T):
  - Keys dong, biet luc run time
  - Tat ca values phai cung type T
  - Dung cho: lookup tables, named collections dong nhat
  - Vi du: ami_by_region, tags, service_ports

Ket hop: map(object({...})) pho bien nhat trong production
  - Keys la ten (dong, biet luc run time)
  - Values co schema (static, biet truoc)
  - Vi du: subnets, services, environments
```

### optional() trong object (Terraform >= 1.3)

```hcl
variable "subnet_config" {
  type = object({
    cidr = string          # Required field
    az   = string          # Required field
    # Optional fields - co default value neu khong truyen
    public             = optional(bool, true)          # Default: true
    nat_gateway        = optional(bool, false)         # Default: false
    tags               = optional(map(string), {})     # Default: empty map
    additional_cidrs   = optional(list(string), [])    # Default: empty list
  })
}

# Caller chi can truyen required fields:
module "subnet" {
  source = "./modules/subnet"
  subnet_config = {
    cidr = "10.0.1.0/24"
    az   = "ap-southeast-1a"
    # public = true (default)
    # nat_gateway = false (default)
  }
}
```

### Type examples cho common production patterns

```hcl
# Multi-environment config
variable "environments" {
  type = map(object({
    vpc_cidr      = string
    instance_type = string
    min_size      = number
    max_size      = number
    enabled       = optional(bool, true)
  }))
  default = {
    dev = {
      vpc_cidr      = "10.10.0.0/16"
      instance_type = "t3.small"
      min_size      = 1
      max_size      = 3
    }
    prod = {
      vpc_cidr      = "10.0.0.0/16"
      instance_type = "t3.large"
      min_size      = 3
      max_size      = 10
    }
  }
}

# Security group rules
variable "sg_rules" {
  type = list(object({
    description = string
    direction   = string           # "ingress" or "egress"
    port        = number
    protocol    = string
    cidr_blocks = list(string)
    priority    = optional(number, 100)
  }))
  default = []
}

# Service topology
variable "services" {
  type = map(object({
    image           = string
    port            = number
    health_check    = string
    min_replicas    = number
    max_replicas    = number
    cpu_request     = optional(string, "100m")
    memory_request  = optional(string, "128Mi")
    env_vars        = optional(map(string), {})
  }))
}
```

---

## 7. count vs for_each Migration Guide

### Kich ban: Co resources dung count, muon chuyen sang for_each

```
Buoc 1: Xac dinh hien trang
  terraform state list | grep resource_name
  # module.vpc.aws_subnet.public[0]
  # module.vpc.aws_subnet.public[1]
  # module.vpc.aws_subnet.public[2]

Buoc 2: Viet code moi dung for_each
  (xem vi du day du o lesson.md Part 4)

Buoc 3: Kiem tra plan - se thay destroy + create
  terraform plan
  # aws_subnet.public[0] will be destroyed
  # aws_subnet.public[1] will be destroyed
  # aws_subnet.this["public-1a"] will be created
  # ...

Buoc 4a (Terraform >= 1.1): Dung "moved" block trong code
  moved {
    from = aws_subnet.public[0]
    to   = aws_subnet.this["public-1a"]
  }
  moved {
    from = aws_subnet.public[1]
    to   = aws_subnet.this["public-1b"]
  }
  -> Plan se thay "moved" thay vi destroy+create

Buoc 4b (Alternative, ruc ro hon): terraform state mv
  terraform state mv 'module.vpc.aws_subnet.public[0]' 'module.vpc.aws_subnet.this["public-1a"]'
  terraform state mv 'module.vpc.aws_subnet.public[1]' 'module.vpc.aws_subnet.this["public-1b"]'

Buoc 5: Apply va verify khong co resource bi destroy
  terraform plan   # Nen bao: 0 to add, 0 to change, 0 to destroy (chi show "moved")
  terraform apply

Buoc 6: Sau khi apply thanh cong, xoa "moved" block
  (moved block chi can ton tai cho den khi tat ca user da apply)
```

### Common key mapping patterns

```
count[0]  ->  for_each["name-0"]   (giu index trong key)
count[0]  ->  for_each["public-1a"] (key co nghia hon)
count[0]  ->  for_each[var.list[0]] (dung gia tri tu list lam key)
```

---

## 8. State Key Reference

```
# Cau truc state key:

count:
  aws_subnet.public[0]
  module.vpc.aws_subnet.public[0]
  module.vpc["env1"].aws_subnet.public[0]  (module voi for_each)

for_each:
  aws_subnet.this["public-1a"]
  module.vpc.aws_subnet.this["public-1a"]
  module.environment["prod"].aws_subnet.this["public-1a"]

# Ghi chu: terraform state list de xem tat ca keys
# terraform state show 'module.vpc.aws_subnet.this["public-1a"]' de xem chi tiet
```

---

## 9. Anti-patterns va How to Fix

```hcl
# ANTI-PATTERN 1: count voi removable-middle list
variable "services" {
  default = ["api", "worker", "admin"]  # Neu xoa "worker" -> index shift
}
resource "aws_sg_rule" "this" {
  count = length(var.services)
}
# FIX: Dung for_each voi map

# ANTI-PATTERN 2: for_each voi computed keys
resource "aws_subnet" "this" {
  for_each = { for s in aws_security_group.services : s.name => s.id }
  # ERROR: for_each keys phai biet truoc (not computed from other resources)
}
# FIX: Dung static map thay vi computed values lam key

# ANTI-PATTERN 3: Dynamic key trong for_each
resource "aws_sg_rule" "this" {
  for_each = { for i, r in var.rules : "${i}-${uuid()}" => r }
  # ERROR: uuid() la non-deterministic -> key thay doi moi lan plan
}
# FIX: Keys phai deterministic (khong dung uuid, timestamp, random)

# ANTI-PATTERN 4: Qua nhieu dynamic blocks long nhau
resource "aws_something" "this" {
  dynamic "level1" {
    for_each = var.l1
    content {
      dynamic "level2" {
        for_each = level1.value.l2
        content {
          dynamic "level3" {  # <- Kho maintain, kho debug
            ...
          }
        }
      }
    }
  }
}
# FIX: Flatten structure truoc boi local, sau do dung 1 level of for_each
```

---

## 10. Terraform Functions - Full List (Day 9 relevant)

### Collection functions

| Function | Description | Example |
|----------|-------------|---------|
| `merge(map...)` | Gop maps, last wins | `merge({a=1}, {a=2, b=3})` = `{a=2, b=3}` |
| `lookup(map, key, default)` | Safe map access | `lookup(tags, "env", "dev")` |
| `keys(map)` | List of keys | `keys({a=1, b=2})` = `["a", "b"]` |
| `values(map)` | List of values | `values({a=1, b=2})` = `[1, 2]` |
| `flatten(list)` | Flatten nested lists | `flatten([[1,2],[3]])` = `[1,2,3]` |
| `distinct(list)` | Remove duplicates | `distinct([1,2,1])` = `[1,2]` |
| `concat(lists...)` | Merge lists | `concat([1,2],[3,4])` = `[1,2,3,4]` |
| `contains(list, val)` | Check membership | `contains(["a","b"], "a")` = `true` |
| `length(val)` | Count elements | `length(["a","b"])` = `2` |
| `slice(list, start, end)` | Sublist | `slice([0,1,2,3], 1, 3)` = `[1,2]` |
| `toset(list)` | Convert to set | `toset(["a","b","a"])` = `["a","b"]` |
| `tolist(set)` | Convert to list | Sorted, no duplicates |
| `tomap(obj)` | Object to map | All values same type |
| `zipmap(keys, vals)` | Merge parallel lists | `zipmap(["a","b"],[1,2])` = `{a=1,b=2}` |

### String functions

| Function | Description | Example |
|----------|-------------|---------|
| `format(tmpl, args...)` | String format | `format("%-10s", "hello")` |
| `replace(str, old, new)` | String replace | `replace("a-b", "-", "_")` = `"a_b"` |
| `split(sep, str)` | Split string | `split(",", "a,b")` = `["a","b"]` |
| `join(sep, list)` | Join list | `join(",", ["a","b"])` = `"a,b"` |
| `lower(str)` | Lowercase | `lower("HELLO")` = `"hello"` |
| `upper(str)` | Uppercase | `upper("hello")` = `"HELLO"` |
| `trimspace(str)` | Trim whitespace | `trimspace("  hi  ")` = `"hi"` |
| `regex(pattern, str)` | Regex match | Returns string |
| `regexall(pattern, str)` | All regex matches | Returns list |

### IP/Network functions

| Function | Description | Example |
|----------|-------------|---------|
| `cidrnetmask(cidr)` | Get netmask | `cidrnetmask("10.0.0.0/16")` = `"255.255.0.0"` |
| `cidrsubnet(prefix, bits, num)` | Calculate subnet | `cidrsubnet("10.0.0.0/16", 8, 1)` = `"10.0.1.0/24"` |
| `cidrhost(prefix, num)` | Get host IP | `cidrhost("10.0.1.0/24", 5)` = `"10.0.1.5"` |
| `cidrsubnets(prefix, bits...)` | Multiple subnets | Calculate series of subnets |

### Type/Encoding functions

| Function | Description |
|----------|-------------|
| `try(exprs...)` | Return first non-error expression |
| `can(expr)` | Test if expression is error-free |
| `tostring(val)` | Convert to string |
| `tonumber(val)` | Convert to number |
| `tobool(val)` | Convert to bool |
| `jsonencode(val)` | Encode as JSON |
| `jsondecode(str)` | Decode JSON string |
| `yamlencode(val)` | Encode as YAML |
| `yamldecode(str)` | Decode YAML string |
| `base64encode(str)` | Base64 encode |
| `base64decode(str)` | Base64 decode |

---

## 11. Expressions Quick Reference

### Conditional (ternary)

```hcl
local.is_prod ? 3 : 1                   # number
var.env == "prod" ? "large" : "small"   # string
var.enable_feature ? [1] : []           # for dynamic block toggle
```

### String interpolation

```hcl
"${var.project}-${var.environment}"         # Basic
"${var.project}-${upper(var.environment)}"  # With function
"prefix-${count.index + 1}"                 # With expression
"${path.module}/templates/script.sh"        # Path reference
```

### Path references

```hcl
path.module   # Thu muc chua module hien tai
path.root     # Thu muc cua root module
path.cwd      # Thu muc hien tai khi chay terraform

# Dung trong templatefile, file()
file("${path.module}/files/config.json")
templatefile("${path.module}/templates/user_data.sh", { ... })
```

### Heredoc strings

```hcl
locals {
  policy = <<-EOT
    {
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::${var.bucket_name}/*"
      }]
    }
  EOT

  # %{ if condition } ... %{ endif } - template directives
  user_data = <<-EOT
    #!/bin/bash
    %{ if var.environment == "prod" ~}
    systemctl enable monitoring-agent
    %{ endif ~}
    export APP_ENV=${var.environment}
  EOT
}
```
