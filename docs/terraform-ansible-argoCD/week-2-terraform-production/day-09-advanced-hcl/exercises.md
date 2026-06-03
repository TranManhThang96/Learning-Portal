# Exercises: Advanced HCL - Day 9

**Muc dich:** Bai tap nang cao cho Day 9. Lam sau khi hoan thanh lab chinh trong lesson.md. Moi bai tap co the lam doc lap.

---

## Exercise 1: Multi-service Security Group voi Complex for_each

**Muc tieu:** Viet module tao security group cho nhieu service, moi service co ingress/egress rules rieng, driven by map(object).

**Yeu cau:**

Tao file `ex1-multi-sg/main.tf` voi input sau:

```hcl
variable "service_security_groups" {
  type = map(object({
    description = string
    ingress_rules = list(object({
      description = string
      from_port   = number
      to_port     = number
      protocol    = string
      cidr_blocks = list(string)
    }))
    egress_allow_all = optional(bool, true)
    extra_egress_rules = optional(list(object({
      description = string
      from_port   = number
      to_port     = number
      protocol    = string
      cidr_blocks = list(string)
    })), [])
  }))
}
```

Tao resources:
1. `aws_security_group` cho moi key trong map (dung `for_each`)
2. Ingress rules bang `dynamic` block tren moi SG
3. Egress: neu `egress_allow_all = true` thi them 1 allow-all rule; neu false thi chi tao `extra_egress_rules`

**Test input:**

```hcl
service_security_groups = {
  "api" = {
    description = "API service security group"
    ingress_rules = [
      {
        description = "HTTP"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
      },
      {
        description = "HTTPS"
        from_port   = 443
        to_port     = 443
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
      }
    ]
    egress_allow_all = true
  }
  "database" = {
    description = "Database security group"
    ingress_rules = [
      {
        description = "PostgreSQL from API"
        from_port   = 5432
        to_port     = 5432
        protocol    = "tcp"
        cidr_blocks = ["10.0.0.0/8"]
      }
    ]
    egress_allow_all = false
    extra_egress_rules = [
      {
        description = "Replica sync"
        from_port   = 5432
        to_port     = 5432
        protocol    = "tcp"
        cidr_blocks = ["10.0.0.0/8"]
      }
    ]
  }
}
```

**Expected output:** Map cua security group IDs: `{ "api" = "sg-xxx", "database" = "sg-yyy" }`

**Hint:** Dung `dynamic "egress"` voi `for_each = var.service_security_groups[each.key].egress_allow_all ? [1] : []` cho allow-all rule. Cho extra egress rules, dung `dynamic "egress"` second instance voi `for_each = each.value.extra_egress_rules`.

---

## Exercise 2: Auto-calculate Subnet CIDRs

**Muc tieu:** Viet configuration tao subnets tu VPC CIDR tu dong, khong can hardcode tung CIDR sub, dung `cidrsubnet()` va `for` expression.

**Yeu cau:**

```hcl
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
}

variable "subnet_newbits" {
  type        = number
  default     = 8
  description = "Bits them vao VPC prefix. 10.0.0.0/16 + 8 bits = /24 subnets"
}
```

Yeu cau:
1. Tu dong tao `locals.public_subnet_map` la map(object) voi key = `"public-{az_suffix}"` va CIDRs duoc tinh bang `cidrsubnet(var.vpc_cidr, var.subnet_newbits, index)`
2. Tu dong tao `locals.private_subnet_map` tuong tu nhung voi netnum bat dau tu `length(var.availability_zones)` (tranh overlap)
3. Tao subnets bang `for_each`
4. Output map cua tat ca subnet CIDRs (key = subnet name, value = cidr)

**Expected behavior voi default values:**
```
vpc_cidr = "10.0.0.0/16", subnet_newbits = 8, 3 AZs

public_subnet_map:
  "public-1a" : { cidr = "10.0.0.0/24",  az = "ap-southeast-1a" }
  "public-1b" : { cidr = "10.0.1.0/24",  az = "ap-southeast-1b" }
  "public-1c" : { cidr = "10.0.2.0/24",  az = "ap-southeast-1c" }

private_subnet_map:
  "private-1a" : { cidr = "10.0.3.0/24",  az = "ap-southeast-1a" }
  "private-1b" : { cidr = "10.0.4.0/24",  az = "ap-southeast-1b" }
  "private-1c" : { cidr = "10.0.5.0/24",  az = "ap-southeast-1c" }
```

**Hint:** `az_suffix` = phan cuoi cua AZ name, vi du `"ap-southeast-1a"` -> `"1a"`. Dung `split("-", az)` va `reverse()` de lay suffix.

**Challenge nang cao:** Them validation dam bao so subnet se tao khong vuot qua capacity cua VPC. Voi `/16` + `8 bits` = 256 `/24` subnets toi da. Voi 3 AZs = 6 subnets, phai nho hon 256.

---

## Exercise 3: Refactoring Exercise - count to for_each

**Muc tieu:** Thuc hanh quy trinh migration thuc te, bao gom demo index-shift va fix bang `moved` block.

**Buoc 1 - Tao resources voi count:**

Tao `ex3-migration/initial.tf`:

```hcl
variable "environment_names" {
  type    = list(string)
  default = ["dev", "staging", "prod"]
}

resource "aws_iam_role" "deployer" {
  count = length(var.environment_names)

  name = "deployer-${var.environment_names[count.index]}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment_names[count.index]
    ManagedBy   = "terraform"
  }
}
```

Apply lan dau:
```bash
terraform apply
terraform state list
# aws_iam_role.deployer[0]  <- dev
# aws_iam_role.deployer[1]  <- staging
# aws_iam_role.deployer[2]  <- prod
```

**Buoc 2 - Demo index shift (chi plan, khong apply):**

Sua variable de xoa "staging":
```hcl
variable "environment_names" {
  type    = list(string)
  default = ["dev", "prod"]  # Xoa "staging"
}
```

```bash
terraform plan
```

Ghi lai va giai thich: bao nhieu resource bi modify/destroy/create? Tai sao "prod" role co the bi affect?

**Buoc 3 - Refactor sang for_each:**

- Revert variable ve `["dev", "staging", "prod"]`
- Chuyen sang `for_each = toset(var.environment_names)`
- Them `moved` blocks de tranh destroy/recreate:

```hcl
moved {
  from = aws_iam_role.deployer[0]
  to   = aws_iam_role.deployer["dev"]
}
moved {
  from = aws_iam_role.deployer[1]
  to   = aws_iam_role.deployer["staging"]
}
moved {
  from = aws_iam_role.deployer[2]
  to   = aws_iam_role.deployer["prod"]
}
```

**Buoc 4 - Verify:**
```bash
terraform plan
# Phai bao: 0 to add, 0 to change, 0 to destroy
# Chi show "moved" blocks duoc apply
```

**Buoc 5 - Xoa "staging" an toan:**
- Sau khi apply voi `moved` blocks
- Xoa "staging" khoi set
- Plan: chi `aws_iam_role.deployer["staging"]` bi destroy, khong affect "dev" va "prod"

---

## Exercise 4: Dynamic Block Edge Cases

**Muc tieu:** Master cac edge case cua `dynamic` block ma thuong gap trong production.

### Case 4a - Conditional nested dynamic block

Viet code tao `aws_autoscaling_group` voi `mixed_instances_policy` block chi xuat hien khi `var.use_mixed_instances = true`:

```hcl
variable "use_mixed_instances" {
  type    = bool
  default = false
}

variable "on_demand_percentage" {
  type    = number
  default = 50
}

variable "spot_instance_pools" {
  type    = number
  default = 2
}

resource "aws_autoscaling_group" "this" {
  name               = "my-asg"
  min_size           = 1
  max_size           = 10
  desired_capacity   = 2
  vpc_zone_identifier = var.subnet_ids

  # Chi tao mixed_instances_policy khi use_mixed_instances = true
  dynamic "mixed_instances_policy" {
    for_each = var.use_mixed_instances ? [1] : []
    content {
      instances_distribution {
        on_demand_percentage_above_base_capacity = var.on_demand_percentage
        spot_instance_pools                      = var.spot_instance_pools
      }

      launch_template {
        launch_template_specification {
          launch_template_id = aws_launch_template.this.id
        }
      }
    }
  }

  # Khi use_mixed_instances = false, dung launch_template truc tiep
  dynamic "launch_template" {
    for_each = var.use_mixed_instances ? [] : [1]
    content {
      id      = aws_launch_template.this.id
      version = "$Latest"
    }
  }
}
```

**Cau hoi:** Tai sao phai co ca hai dynamic blocks (`mixed_instances_policy` va `launch_template`)? Co the chuyen mot trong 2 sang explicit block khong? Giai thich.

### Case 4b - Dynamic block voi iterator co access to both key va value

```hcl
variable "route_table_entries" {
  type = map(object({
    destination_cidr = string
    target_type      = string  # "gateway" hoac "nat"
    target_id        = string
  }))
  default = {
    "internet-route" = {
      destination_cidr = "0.0.0.0/0"
      target_type      = "gateway"
      target_id        = "igw-12345"
    }
    "internal-route" = {
      destination_cidr = "10.1.0.0/16"
      target_type      = "nat"
      target_id        = "nat-67890"
    }
  }
}

resource "aws_route_table" "this" {
  vpc_id = var.vpc_id

  dynamic "route" {
    for_each = var.route_table_entries
    iterator = entry
    content {
      cidr_block     = entry.value.destination_cidr
      # Challenge: lam sao set dung attribute (gateway_id vs nat_gateway_id)
      # dua theo entry.value.target_type?
      # gateway_id     = ??? (chi set khi target_type == "gateway")
      # nat_gateway_id = ??? (chi set khi target_type == "nat")
    }
  }
}
```

**Challenge:** `aws_route_table`'s `route` block co hai attribute mutually exclusive: `gateway_id` va `nat_gateway_id`. Dung conditional expression trong `dynamic` block de set dung attribute. Viet `content` block hoan chinh.

**Hint:** `gateway_id = entry.value.target_type == "gateway" ? entry.value.target_id : null` - AWS provider se ignore `null` values.

---

## Exercise 5: for Expression Advanced Patterns

**Muc tieu:** Nang cao ky nang viet `for` expression de transform complex data structures.

### Case 5a - Invert map

```hcl
# Input:
variable "service_to_port" {
  type = map(number)
  default = {
    "api"       = 8080
    "worker"    = 8081
    "scheduler" = 8082
    "admin"     = 8083
  }
}

# Yeu cau: Tao local "port_to_service" = {8080 = "api", 8081 = "worker", ...}
# Chi dung for expression, khong dung loop/manual

locals {
  port_to_service = # Viet expression o day
}
```

**Ket qua mong doi:**
```
port_to_service = {
  8080 = "api"
  8081 = "worker"
  8082 = "scheduler"
  8083 = "admin"
}
```

### Case 5b - Group by attribute

```hcl
variable "instances" {
  type = list(object({
    name              = string
    availability_zone = string
    instance_type     = string
  }))
  default = [
    { name = "web-1", availability_zone = "ap-southeast-1a", instance_type = "t3.medium" },
    { name = "web-2", availability_zone = "ap-southeast-1b", instance_type = "t3.medium" },
    { name = "db-1",  availability_zone = "ap-southeast-1a", instance_type = "r5.large" },
    { name = "db-2",  availability_zone = "ap-southeast-1b", instance_type = "r5.large" },
    { name = "cache", availability_zone = "ap-southeast-1a", instance_type = "r5.xlarge" },
  ]
}

# Yeu cau: Group instances theo AZ
# instances_by_az = {
#   "ap-southeast-1a" = ["web-1", "db-1", "cache"]
#   "ap-southeast-1b" = ["web-2", "db-2"]
# }

locals {
  instances_by_az = # Viet expression o day
  # Hint: Can 2 pass - lay distinct AZs, sau do filter per AZ
}
```

### Case 5c - Flatten nested config thanh flat for_each map

```hcl
variable "application_tiers" {
  type = map(object({
    subnets = list(object({
      cidr_block = string
      az_index   = number
    }))
  }))
  default = {
    "public" = {
      subnets = [
        { cidr_block = "10.0.1.0/24", az_index = 0 },
        { cidr_block = "10.0.2.0/24", az_index = 1 }
      ]
    }
    "private" = {
      subnets = [
        { cidr_block = "10.0.11.0/24", az_index = 0 },
        { cidr_block = "10.0.12.0/24", az_index = 1 }
      ]
    }
    "database" = {
      subnets = [
        { cidr_block = "10.0.21.0/24", az_index = 0 }
      ]
    }
  }
}

# Yeu cau: Tao flat map de dung voi for_each tren aws_subnet
# Key format: "{tier}-{az_index}"
# Ket qua mong doi:
# {
#   "public-0"   = { cidr = "10.0.1.0/24",  az_index = 0, tier = "public"   }
#   "public-1"   = { cidr = "10.0.2.0/24",  az_index = 1, tier = "public"   }
#   "private-0"  = { cidr = "10.0.11.0/24", az_index = 0, tier = "private"  }
#   "private-1"  = { cidr = "10.0.12.0/24", az_index = 1, tier = "private"  }
#   "database-0" = { cidr = "10.0.21.0/24", az_index = 0, tier = "database" }
# }

locals {
  flat_subnets = # Viet expression o day
}

resource "aws_subnet" "this" {
  for_each = local.flat_subnets
  # each.key = "public-0", "private-1", ...
  # each.value.cidr, each.value.az_index, each.value.tier
}
```

---

## Exercise 6: try() va can() trong Production Validation

**Muc tieu:** Viet validation rules dong thoi va xu ly optional config an toan.

### Case 6a - Validation chain

Viet variable `database_config` voi cac validation:

```hcl
variable "database_config" {
  type = object({
    engine        = string          # "postgres", "mysql", "aurora-postgres", "aurora-mysql"
    version       = string          # Major version number
    instance_class = string         # "db.t3.medium", "db.r5.large", etc
    port          = optional(number, null)  # null = dung default port cua engine
    multi_az      = optional(bool, false)
    backup_retention_days = optional(number, 7)
  })

  # Validation 1: engine phai la supported value
  validation { ... }

  # Validation 2: version phai la number string (chi so)
  validation { ... }

  # Validation 3: backup_retention_days phai tu 1 den 35
  validation { ... }

  # Validation 4: Neu engine la "aurora-*", port mac dinh la 3306 hoac 5432
  # Validation nay kho hon vi can cross-field check
  # Hint: can(regex("^aurora-", var.database_config.engine)) cho ket qua bool
  validation { ... }
}
```

Them `locals` block xu ly `port` khi la `null`:

```hcl
locals {
  # Neu port = null, tinh default port dua theo engine
  default_ports = {
    "postgres"       = 5432
    "aurora-postgres" = 5432
    "mysql"          = 3306
    "aurora-mysql"   = 3306
  }

  effective_port = try(
    # Neu port duoc set explicitly, dung no
    var.database_config.port != null ? var.database_config.port : local.default_ports[var.database_config.engine],
    # Fallback neu engine khong co trong map
    5432
  )
}
```

### Case 6b - Optional nested config voi try()

```hcl
variable "monitoring_config" {
  description = "Optional monitoring configuration"
  type = object({
    enabled = bool
    # cac field sau chi co mat khi enabled = true
    cloudwatch = optional(object({
      log_group     = optional(string, "/aws/application")
      retention_days = optional(number, 30)
      alerts = optional(object({
        email     = string
        threshold = optional(number, 5)
      }))
    }))
    datadog = optional(object({
      api_key    = string
      tags       = optional(list(string), [])
    }))
  })
  default = { enabled = false }
}

locals {
  # Safe access vao optional nested fields
  log_group      = try(var.monitoring_config.cloudwatch.log_group, "/aws/application")
  alert_email    = try(var.monitoring_config.cloudwatch.alerts.email, null)
  alert_threshold = try(var.monitoring_config.cloudwatch.alerts.threshold, 5)
  datadog_tags   = try(var.monitoring_config.datadog.tags, [])

  # Kiem tra xem datadog co duoc enable
  datadog_enabled = can(var.monitoring_config.datadog.api_key) && var.monitoring_config.enabled
}
```

**Bai tap:** Viet them 3 `local` values su dung `try()` de safe-access:
1. `cloudwatch_retention`: Default 30 neu khong co
2. `has_alert_config`: bool, true neu `cloudwatch.alerts` ton tai
3. `effective_monitoring_tags`: Merge `datadog_tags` voi base tags, handle ca khi datadog khong duoc config

---

## Exercise 7: Complete VPC Module voi for_each Throughout

**Muc tieu:** Viet lai toan bo VPC module tu Day 6 dung for_each cho tat ca resource, thay vi count. Day la bai tap tong hop lon nhat.

**Yeu cau:**

Tao module voi input:

```hcl
variable "network_config" {
  type = object({
    vpc_cidr = string
    subnets = map(object({
      cidr   = string
      az     = string
      tier   = string  # "public", "private", "database"
    }))
    nat_gateway = optional(object({
      enabled = bool
      single  = optional(bool, true)  # true = 1 NAT, false = 1 per AZ
    }), { enabled = false })
  })
}
```

Resources can tao dung `for_each`:
1. `aws_subnet.this` cho moi subnet trong `network_config.subnets`
2. `aws_route_table` rieng per tier (`public`, `private`, `database`)
3. `aws_route_table_association` cho moi subnet (for_each tren map subnet)
4. `aws_nat_gateway` chi cho public subnets (neu nat_gateway.enabled = true)
5. `aws_eip` per NAT gateway (for_each tren subset cua public subnets)

**Outputs phai:** Map cua subnet IDs per tier:

```hcl
# Ket qua mong doi:
output "subnet_ids_by_tier" {
  value = {
    public   = [...list of public subnet IDs...]
    private  = [...list of private subnet IDs...]
    database = [...list of database subnet IDs...]
  }
}
```

**Constraints:**
- Neu `nat_gateway.single = true`: chi tao 1 NAT trong public subnet dau tien
- Neu `nat_gateway.single = false`: tao 1 NAT per unique AZ co public subnet
- Private route table co route den NAT gateway
- Database subnets: khong co route ra internet (isolated)

**Test voi config:**

```hcl
network_config = {
  vpc_cidr = "10.0.0.0/16"
  subnets = {
    "pub-1a"  = { cidr = "10.0.1.0/24",  az = "ap-southeast-1a", tier = "public" }
    "pub-1b"  = { cidr = "10.0.2.0/24",  az = "ap-southeast-1b", tier = "public" }
    "priv-1a" = { cidr = "10.0.11.0/24", az = "ap-southeast-1a", tier = "private" }
    "priv-1b" = { cidr = "10.0.12.0/24", az = "ap-southeast-1b", tier = "private" }
    "db-1a"   = { cidr = "10.0.21.0/24", az = "ap-southeast-1a", tier = "database" }
    "db-1b"   = { cidr = "10.0.22.0/24", az = "ap-southeast-1b", tier = "database" }
  }
  nat_gateway = {
    enabled = true
    single  = true
  }
}
```

**Expected state keys:**
```
aws_subnet.this["pub-1a"]
aws_subnet.this["pub-1b"]
aws_subnet.this["priv-1a"]
aws_subnet.this["priv-1b"]
aws_subnet.this["db-1a"]
aws_subnet.this["db-1b"]
aws_route_table.by_tier["public"]
aws_route_table.by_tier["private"]
aws_route_table.by_tier["database"]
aws_nat_gateway.this["pub-1a"]  # Chi 1 NAT (single = true)
```

---

## Giai Dap Goi Y

### Exercise 1 - Key insight

```hcl
# Hai dynamic "egress" blocks trong cung resource la hop le
# Block dau: conditional allow-all
dynamic "egress" {
  for_each = each.value.egress_allow_all ? [1] : []
  content {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Block thu hai: explicit rules
dynamic "egress" {
  for_each = each.value.extra_egress_rules
  iterator = rule
  content {
    from_port   = rule.value.from_port
    to_port     = rule.value.to_port
    protocol    = rule.value.protocol
    cidr_blocks = rule.value.cidr_blocks
    description = rule.value.description
  }
}
```

### Exercise 2 - az_suffix extraction

```hcl
locals {
  # "ap-southeast-1a" -> ["ap", "southeast", "1a"] -> last element = "1a"
  az_suffix = { for az in var.availability_zones : az => element(split("-", az), length(split("-", az)) - 1) }

  public_subnet_map = {
    for i, az in var.availability_zones :
    "public-${local.az_suffix[az]}" => {
      cidr   = cidrsubnet(var.vpc_cidr, var.subnet_newbits, i)
      az     = az
      public = true
    }
  }

  private_subnet_map = {
    for i, az in var.availability_zones :
    "private-${local.az_suffix[az]}" => {
      cidr   = cidrsubnet(var.vpc_cidr, var.subnet_newbits, length(var.availability_zones) + i)
      az     = az
      public = false
    }
  }
}
```

### Exercise 5a - Invert map

```hcl
locals {
  port_to_service = { for service, port in var.service_to_port : tostring(port) => service }
  # Note: map keys phai la string, nen can tostring(port)
}
```

### Exercise 5b - Group by AZ (approach)

```hcl
locals {
  distinct_azs = distinct([for i in var.instances : i.availability_zone])

  instances_by_az = {
    for az in local.distinct_azs :
    az => [
      for i in var.instances : i.name
      if i.availability_zone == az
    ]
  }
}
```

### Exercise 5c - Flatten nested config

```hcl
locals {
  flat_subnets = merge([
    for tier, config in var.application_tiers : {
      for subnet in config.subnets :
      "${tier}-${subnet.az_index}" => {
        cidr     = subnet.cidr_block
        az_index = subnet.az_index
        tier     = tier
      }
    }
  ]...)
}
```

### Exercise 4b - Conditional attribute trong dynamic route

```hcl
dynamic "route" {
  for_each = var.route_table_entries
  iterator = entry
  content {
    cidr_block     = entry.value.destination_cidr
    gateway_id     = entry.value.target_type == "gateway" ? entry.value.target_id : null
    nat_gateway_id = entry.value.target_type == "nat" ? entry.value.target_id : null
    # AWS provider bo qua null attribute - chi one duoc set
  }
}
```

---

## Checklist Hoan Thanh

- [ ] Exercise 1: Multi-service SG voi double dynamic egress hoat dong dung (allow-all + explicit rules tach biet)
- [ ] Exercise 2: Subnet CIDRs duoc tinh tu dong, khong hardcode, validation vuot qua
- [ ] Exercise 3: Migration cho thay `terraform plan` bao 0 change sau khi dung `moved` block
- [ ] Exercise 4a: ASG co `mixed_instances_policy` khi `use_mixed_instances = true`, khong co khi false
- [ ] Exercise 4b: Route table voi conditional gateway_id/nat_gateway_id hoat dong khong error
- [ ] Exercise 5: Ba for expressions cho ket qua chinh xac, co the verify bang `terraform console`
- [ ] Exercise 6: Validation bat loi input sai, `try()` xu ly optional field khong fail
- [ ] Exercise 7: Module tao dung resources, state keys dung format, `subnet_ids_by_tier` output chinh xac

---

## Ghi Chu Cho Day 10

Mot so patterm o Exercise 3 (moved block) se duoc hoc day du hon o Day 10:
- `moved` block voi module refactoring
- `removed` block de xoa resource khoi state ma khong destroy
- `import` block va `terraform import` command
- `lifecycle.replace_triggered_by` cho forced replacement

Exercise 7 (Complete VPC Module) la foundation cho Capstone Project - giu lai code sau khi hoan thanh.
