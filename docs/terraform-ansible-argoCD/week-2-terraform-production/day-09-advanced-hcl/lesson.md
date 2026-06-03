# Day 9: Advanced HCL - for_each, count, dynamic blocks

**Thoi gian:** 2 gio | **Level:** Intermediate-Advanced | **Phase:** 2 - Terraform Production, Day 3
**Prerequisites:** Day 6 (VPC Module), Day 7 (Module Design), Day 8 (Multi-Environment)

---

## 1. Muc tieu ngay hoc

Sau buoi hoc nay, ban co the:

1. Phan biet `count` va `for_each` ve mechanism, trade-off, va khi nao dung cai nao - khong chi theo "best practice" ma theo context cu the
2. Viet `for_each` voi ca ba kieu input: `map`, `set(string)`, va `list` da duoc chuyen doi - va giai thich tai sao `list` khong direct-support
3. Su dung `dynamic` block de generate nested config linh hoat, thay the viec viet lap nhieu block voi nguy co drift
4. Ap dung `for` expression, `merge`, `lookup`, `try`, `can` de transform va validate data tuong tu nhu functional programming trong Go/TypeScript
5. Thuc hien refactor tu `count` sang `for_each` dung chuan: hieu van de index-shift, tranh unintended resource recreation, va su dung `moved` block (preview cho Day 10)

---

## 2. Boi canh thuc te

### Van de xay ra khi hard-code nhieu resource

Ban dang ky tiep module VPC tu Day 6. Module do dung `count` de tao public/private subnets:

```hcl
resource "aws_subnet" "public" {
  count             = length(var.public_subnet_cidrs)
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  # ...
}
```

Day la cach hop ly cho subnets - chung dong nhat, chi khac CIDR va AZ. Nhung khi ban mo rong sang security group rules, ban gap van de khac.

**Incident thuc te - Security Group drift:**

Team ban co 4 microservice: `api`, `worker`, `scheduler`, `admin`. Moi service can security group rule cho phep access vao port rieng. Engineer A viet:

```hcl
resource "aws_security_group_rule" "api_ingress" {
  type        = "ingress"
  from_port   = 8080
  to_port     = 8080
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/8"]
  security_group_id = aws_security_group.app.id
}

resource "aws_security_group_rule" "worker_ingress" {
  type        = "ingress"
  from_port   = 8081
  to_port     = 8081
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/8"]
  security_group_id = aws_security_group.app.id
}

# ... lap tiep cho scheduler, admin
```

Sau 3 thang:
- Service moi them vao = copy-paste them 1 block, de quen
- Thay doi `cidr_blocks` = phai update 4 cho, Engineer B update 3, bo sot 1
- Sort lai thu tu block = Terraform thay doi khong? Hay yen?

**Van de voi `count` khi danh sach thay doi:**

```hcl
# Ngay 1: 3 services
variable "services" {
  default = ["api", "worker", "scheduler"]
}

resource "aws_security_group_rule" "ingress" {
  count = length(var.services)
  # services[0] = api     -> index 0
  # services[1] = worker  -> index 1
  # services[2] = scheduler -> index 2
}
```

```hcl
# Ngay 30: Xoa "worker" o giua danh sach
variable "services" {
  default = ["api", "scheduler"]  # Bo "worker"
}

# Terraform plan:
# services[0] = api         -> index 0 (OK, khong thay doi)
# services[1] = scheduler   -> index 1 (THAY DOI - truoc la "worker")
# Ket qua: DESTROY "worker" rule, UPDATE "scheduler" rule (rename)
# Thuc te: Terraform se destroy va recreate "scheduler" rule
# Trong prod: co the gay outage neu SG rule bi xoa trong luc traffic dang di qua
```

Day la **index-shift problem** cua `count`. `for_each` giai quyet van de nay bang cach dung stable key thay vi index.

### Scaling infrastructure config

Khi platform team quan ly networking cho 10 tenant, moi tenant can:
- 3-5 subnets (tuy theo region va AZ)
- Security group voi 5-15 rules (tuy theo service topology)
- Network ACL entries

Hard-code = khong the. `count` = gap index-shift van de. `for_each` + `dynamic` = cach dung production.

---

## 3. Kien thuc nen tang - 30 phut

### 3.1 count - Mechanism va gioi han

`count` la meta-argument tao nhieu instance cua resource/module bang so nguyen. Terraform track chung bang numeric index: `resource_type.name[0]`, `resource_type.name[1]`, ...

```hcl
resource "aws_subnet" "public" {
  count      = 3
  cidr_block = var.cidrs[count.index]  # count.index: 0, 1, 2
  # ...
}
```

**Khi nao dung `count`:**
- Tat ca instance dong nhat, chi khac nhau o index (rate limiter, replica)
- So luong instance dua tren dieu kien boolean: `count = var.enable_feature ? 1 : 0`
- Resource don gian, khong co unique identity quan trong

**Khi KHONG dung `count`:**
- Resource co identity rieng biet (moi cai co ten, role, config rieng)
- Danh sach co the thay doi o giua (them/xoa phan tu giua list)
- Ban muon reference resource theo ten co nghia thay vi so

```hcl
# OK voi count: conditional resource
resource "aws_nat_gateway" "main" {
  count         = var.enable_nat ? 1 : 0
  subnet_id     = aws_subnet.public[0].id
  allocation_id = aws_eip.nat[0].id
}

# OK voi count: dong nhat replicas
resource "aws_instance" "worker" {
  count         = var.worker_count
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.small"
  tags = {
    Name = "worker-${count.index}"
  }
}
```

### 3.2 for_each - Mechanism va su dung

`for_each` la meta-argument tao nhieu instance tu `map` hoac `set(string)`. Terraform track chung bang key: `resource_type.name["key"]`.

```
Analogy voi programming:

count   ≈ for (int i = 0; i < n; i++)    // index-based, fragile khi xen/xoa
for_each ≈ map.forEach((key, value) => {}) // key-based, stable
```

**for_each voi map:**

```hcl
# Map: key = ten subnet, value = object chua config
variable "subnets" {
  type = map(object({
    cidr              = string
    availability_zone = string
    public            = bool
  }))
  default = {
    "public-a" = {
      cidr              = "10.0.1.0/24"
      availability_zone = "ap-southeast-1a"
      public            = true
    }
    "public-b" = {
      cidr              = "10.0.2.0/24"
      availability_zone = "ap-southeast-1b"
      public            = true
    }
    "private-a" = {
      cidr              = "10.0.11.0/24"
      availability_zone = "ap-southeast-1a"
      public            = false
    }
  }
}

resource "aws_subnet" "this" {
  for_each = var.subnets          # for_each nhan map

  cidr_block              = each.value.cidr
  availability_zone       = each.value.availability_zone
  map_public_ip_on_launch = each.value.public
  vpc_id                  = aws_vpc.main.id

  tags = {
    Name = "${var.project}-${each.key}"  # each.key = "public-a", "public-b", "private-a"
  }
}

# State se co:
# aws_subnet.this["public-a"]
# aws_subnet.this["public-b"]
# aws_subnet.this["private-a"]
# Xoa "public-b" khoi map: chi destroy aws_subnet.this["public-b"], khong affect cac subnet khac
```

**for_each voi set(string):**

```hcl
# Set: chi co key, khong co value rieng (each.key == each.value)
variable "allowed_principals" {
  type    = set(string)
  default = ["arn:aws:iam::123456789:role/DevRole", "arn:aws:iam::123456789:role/AdminRole"]
}

resource "aws_iam_role_policy_attachment" "this" {
  for_each = var.allowed_principals

  principal  = each.key    # each.key == each.value khi dung set
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}
```

**for_each voi list - can chuyen doi:**

`for_each` KHONG nhan `list(string)` truc tiep vi list co the co duplicate va order-dependent. Can chuyen sang `set` hoac `map` truoc:

```hcl
variable "service_names" {
  type    = list(string)
  default = ["api", "worker", "scheduler"]
}

locals {
  # Chuyen list sang set - mat order, can unique values
  service_set = toset(var.service_names)

  # Hoac chuyen sang map voi index lam key (neu can giu order)
  service_map = { for idx, name in var.service_names : name => idx }
}

resource "aws_security_group" "services" {
  for_each = local.service_set

  name   = "${var.project}-${each.key}-sg"
  vpc_id = var.vpc_id
}
```

### 3.3 for expression - Transform collections

`for` expression la cach viet functional transformation cho list va map, tuong tu `map()`, `filter()`, `reduce()` trong JavaScript/Python.

```hcl
# Syntax co ban:
# [for item in collection : transform_expression]          # => list
# {for item in collection : key_expr => value_expr}        # => map
# [for item in collection : transform if condition]        # => list co filter

locals {
  # List transformation: lay tat ca subnet ID tu for_each resource
  public_subnet_ids = [
    for k, v in aws_subnet.this : v.id
    if var.subnets[k].public == true
  ]

  # Map transformation: doi ten service thanh uppercase
  service_labels = {
    for service, config in var.services :
    service => upper(config.name)
  }

  # Flatten nested structure
  all_sg_rules = flatten([
    for service, rules in var.service_sg_rules : [
      for rule in rules : {
        service   = service
        port      = rule.port
        protocol  = rule.protocol
        cidr      = rule.cidr
      }
    ]
  ])
}
```

**for expression voi complex types:**

```hcl
variable "environments" {
  type = map(object({
    instance_type = string
    min_size      = number
    max_size      = number
  }))
  default = {
    dev = {
      instance_type = "t3.small"
      min_size      = 1
      max_size      = 3
    }
    prod = {
      instance_type = "t3.large"
      min_size      = 3
      max_size      = 10
    }
  }
}

locals {
  # Chi lay env co max_size >= 5
  large_environments = {
    for env, config in var.environments :
    env => config
    if config.max_size >= 5
  }

  # Tao flat map: env_name => instance_type
  instance_types = {
    for env, config in var.environments :
    env => config.instance_type
  }
}
```

### 3.4 dynamic blocks - Generate nested config

`dynamic` block cho phep generate nhieu nested block tu collection, thay vi viet tung block mot. Day la cach xu ly cac block nhu `ingress`, `egress`, `tag`, `volume` khi so luong block bi quyet dinh boi data.

```hcl
# Khong co dynamic: phai viet tung ingress rule mot
resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
}
```

```hcl
# Voi dynamic: drive tu data
locals {
  ingress_rules = [
    { port = 80,   protocol = "tcp", cidr = "0.0.0.0/0" },
    { port = 443,  protocol = "tcp", cidr = "0.0.0.0/0" },
    { port = 8080, protocol = "tcp", cidr = "10.0.0.0/8" },
  ]
}

resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = var.vpc_id

  dynamic "ingress" {          # "ingress" = ten cua nested block type
    for_each = local.ingress_rules
    content {                  # "content" chua noi dung cua block
      from_port   = ingress.value.port      # ingress = label dat cho iterator
      to_port     = ingress.value.port
      protocol    = ingress.value.protocol
      cidr_blocks = [ingress.value.cidr]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

**Anatomy cua dynamic block:**

```
dynamic "<block_type>" {
    ^--- Ten cua block type (ingress, egress, tag, volume, ...)

  for_each = <collection>
              ^--- Map hoac list/set de iterate

  content {
    <attribute> = <iterator_label>.value.<field>
                   ^--- "iterator_label" = ten cua block type (default)
                        Hoac custom label bang: iterator { label = "rule" }
  }
}
```

**Dynamic block voi custom iterator label:**

```hcl
dynamic "ingress" {
  for_each = var.ingress_rules
  iterator = rule                # Custom label, thay vi dung "ingress"
  content {
    from_port   = rule.value.port
    to_port     = rule.value.port
    protocol    = rule.value.protocol
    cidr_blocks = rule.value.cidr_blocks
  }
}
```

### 3.5 Complex types - object, map, list, set

**object: fixed schema**

```hcl
# Object co schema co dinh - phu hop cho config co cau truc ro rang
variable "vpc_config" {
  type = object({
    cidr              = string
    enable_dns        = bool
    nat_gateway_count = number
    tags              = map(string)  # nested complex type
  })
}

# Object voi optional fields (Terraform 1.3+)
variable "subnet_config" {
  type = object({
    cidr = string
    az   = string
    # Optional field co default value
    public = optional(bool, true)
    tags   = optional(map(string), {})
  })
}
```

**map: key-value dong nhat**

```hcl
# Map: tat ca value co cung type - phu hop cho lookup tables
variable "ami_by_region" {
  type = map(string)
  default = {
    "ap-southeast-1" = "ami-12345678"
    "ap-northeast-1" = "ami-87654321"
    "us-east-1"      = "ami-abcdef01"
  }
}

# map(object): pho bien nhat trong production
variable "services" {
  type = map(object({
    port          = number
    health_check  = string
    min_replicas  = number
  }))
}
```

**list vs set:**

```hcl
# list: ordered, allows duplicates, index-accessible
variable "availability_zones" {
  type    = list(string)
  default = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
}
# var.availability_zones[0] = "ap-southeast-1a"  // OK

# set: unordered, unique, no index
variable "allowed_actions" {
  type    = set(string)
  default = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
}
# set khong co index - chi dung trong for_each hoac contains()

# Chuyen doi:
locals {
  az_set   = toset(var.availability_zones)     # list -> set (mat order, bo duplicate)
  az_list  = tolist(var.allowed_actions)       # set -> list (co the dung index)
}
```

### 3.6 Built-in functions: merge, lookup, try, can

**merge - Gop map:**

```hcl
locals {
  # merge nhan nhieu map, key sau override key truoc
  final_tags = merge(
    { Project = var.project, ManagedBy = "terraform" },  # base tags
    var.environment_tags,                                  # env-specific tags
    { Name = "${var.project}-${var.environment}" }         # resource-specific tag (uu tien cao nhat)
  )
}
```

**lookup - Tim gia tri trong map:**

```hcl
locals {
  # lookup(map, key, default)
  # Neu key ton tai: tra ve value
  # Neu key khong ton tai: tra ve default (khong throw error)
  instance_type = lookup(var.instance_types_by_env, var.environment, "t3.micro")

  # KHAC voi map index: var.instance_types_by_env[var.environment]
  # Map index se throw error neu key khong ton tai
  # lookup thi return default
}
```

**try - Xu ly expression co the fail:**

```hcl
locals {
  # try(expression1, expression2, ...)
  # Thu lan luot, tra ve ket qua cua expression dau tien khong throw error
  # Huu ich khi access optional nested attribute

  # Truong hop: var.config co the co hoac khong co field "advanced"
  log_level = try(var.config.advanced.log_level, "info")
  # Neu var.config.advanced.log_level ton tai -> dung no
  # Neu throw error (vi advanced khong ton tai) -> dung "info"

  # Thu nested optional:
  alarm_email = try(var.monitoring.alerts.email, var.default_email, "ops@company.com")
}
```

**can - Kiem tra expression co hop le:**

```hcl
# can(expression) tra ve true/false
# Thuong dung trong validation block

variable "vpc_cidr" {
  type = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR notation. Vi du: 10.0.0.0/16"
  }
}

variable "tags" {
  type = map(string)

  validation {
    # Kiem tra xem "Environment" key co ton tai va co valid value
    condition     = can(regex("^(dev|staging|prod)$", var.tags["Environment"]))
    error_message = "tags phai co key 'Environment' voi value la dev, staging, hoac prod."
  }
}
```

**So sanh `try` va `can`:**

```
try(expr, fallback) -> gia tri
  Dung khi: ban muon gia tri thay the neu expression fail
  Vi du: try(var.config.timeout, 30)

can(expr) -> bool
  Dung khi: validation, kiem tra truoc khi dung
  Vi du: can(cidrnetmask(var.cidr)) trong validation block
```

---

## 4. Deep Dive va Trade-offs - 30 phut

### 4.1 count vs for_each - Bang so sanh day du

| Tieu chi | count | for_each |
|----------|-------|----------|
| Track resources boi | Numeric index (0, 1, 2) | String key ("name-a", "name-b") |
| Input type | number | map hoac set(string) |
| Xoa phan tu giua | INDEX SHIFT - may resources bi destroy/recreate | Stable - chi xoa resource voi key do |
| Access trong resource | `count.index` (so) | `each.key`, `each.value` |
| Reference tu ngoai | `resource.name[0]` | `resource.name["key"]` |
| Use case pho bien | Replicas dong nhat, boolean toggle | Named resources co config rieng |
| Terraform state key | `module.vpc.aws_subnet.public[0]` | `module.vpc.aws_subnet.this["public-a"]` |

**Index shift demo - tai sao nguy hiem:**

```
# Before:
services = ["api", "worker", "admin"]
State:
  aws_sg_rule.this[0] -> api (port 8080)
  aws_sg_rule.this[1] -> worker (port 8081)
  aws_sg_rule.this[2] -> admin (port 8082)

# After xoa "worker":
services = ["api", "admin"]
Terraform plan:
  aws_sg_rule.this[0] -> UNCHANGED (api)
  aws_sg_rule.this[1] -> MODIFY (was worker:8081, now admin:8082) <- Thuc te: destroy + create
  aws_sg_rule.this[2] -> DESTROY (orphaned)

# Ket qua: admin rule bi destroy va recreate - security gap trong luc apply!
```

```
# for_each khong co van de nay:
services = {
  "api"    = { port = 8080 }
  "worker" = { port = 8081 }
  "admin"  = { port = 8082 }
}
State:
  aws_sg_rule.this["api"]    -> api (port 8080)
  aws_sg_rule.this["worker"] -> worker (port 8081)
  aws_sg_rule.this["admin"]  -> admin (port 8082)

# After xoa "worker":
services = {
  "api"   = { port = 8080 }
  "admin" = { port = 8082 }
}
Plan:
  aws_sg_rule.this["api"]    -> UNCHANGED
  aws_sg_rule.this["worker"] -> DESTROY (chi no)
  aws_sg_rule.this["admin"]  -> UNCHANGED
# An toan - chi destroy dung resource can xoa
```

### 4.2 Khi nao dung dynamic block vs explicit blocks

**Dung explicit blocks khi:**
- So luong block co dinh, khong bao gio thay doi theo data
- Logic block qua phuc tap de represent trong loop
- Moi block co dieu kien khac nhau (khong dong nhat)
- Readability quan trong hon flexibility

```hcl
# Explicit: OK khi egress luc nao cung co dung 1 rule nay
resource "aws_security_group" "app" {
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
}
```

**Dung dynamic blocks khi:**
- So luong block bi quyet dinh boi variable/input
- Cac block dong nhat ve structure, chi khac nhau o values
- Ban muon driven by data (danh sach rules tu variable)
- DRY principle - tranh viet lai cung pattern nhieu lan

```hcl
# Dynamic: khi ingress rules den tu variable
resource "aws_security_group" "app" {
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

**Trade-off:**
- Dynamic block lam plan output kho doc hon (block biet bao nhieu rule se duoc tao)
- Dynamic block co the che giau complexity - nguoi doc phai theo jump sang definition cua collection
- Explicit block: self-documenting, ro rang nhung verbose va cung nhac

### 4.3 Complex type design patterns

**Pattern 1 - Map of objects (pho bien nhat):**

```hcl
# Phu hop khi: moi item co config rieng, can reference theo ten
variable "subnets" {
  type = map(object({
    cidr              = string
    availability_zone = string
    public            = bool
    nat_gateway       = optional(bool, false)
  }))
}
```

**Pattern 2 - List of objects (khi order quan trong):**

```hcl
# Phu hop khi: thu tu matters, hoac can dung count.index cho tuong quan
variable "route_table_entries" {
  type = list(object({
    destination_cidr = string
    gateway_id       = string
    description      = string
  }))
}
```

**Pattern 3 - Nested map (khi co hierarchy):**

```hcl
# Phu hop khi: co tree structure
variable "service_sg_rules" {
  type = map(object({
    ingress = list(object({
      port     = number
      protocol = string
      cidrs    = list(string)
    }))
    egress = list(object({
      port     = number
      protocol = string
      cidrs    = list(string)
    }))
  }))
}
```

**Chon type bang flat tuple <service, rule>:**

```hcl
# Khi can for_each tren tat ca rules cua tat ca services
locals {
  # Flatten map cua rules thanh list cua {service, rule} pairs
  all_sg_rules = merge([
    for service, config in var.service_sg_rules : {
      for idx, rule in config.ingress :
      "${service}-ingress-${idx}" => merge(rule, { service = service, direction = "ingress" })
    }
  ]...)
  # ... = unpack list of maps thanh arguments cho merge()
}

resource "aws_security_group_rule" "this" {
  for_each = local.all_sg_rules
  # ...
}
```

### 4.4 The count-to-for_each migration problem

Day la van de thuong gap khi refactor legacy code. Neu ban da deploy resources voi `count` va muon chuyen sang `for_each`, Terraform se thay tat ca resources bi destroy va recreate (vi state key thay doi tu `[0]` sang `["key"]`).

**Buoc 1 - Xac dinh van de:**

```bash
# Truoc khi refactor, kiem tra state keys hien tai
terraform state list | grep aws_subnet
# Output:
# module.vpc.aws_subnet.public[0]
# module.vpc.aws_subnet.public[1]
```

**Buoc 2 - Nhin vao plan truoc khi apply:**

```bash
terraform plan
# Se thay:
# - module.vpc.aws_subnet.public[0] will be DESTROYED
# - module.vpc.aws_subnet.public[1] will be DESTROYED
# - module.vpc.aws_subnet.this["public-a"] will be CREATED
# - module.vpc.aws_subnet.this["public-b"] will be CREATED
# KHONG BPAI: destroy truoc, create sau = downtime
```

**Buoc 3 - Dung `terraform state mv` (manual, risky):**

```bash
terraform state mv \
  'module.vpc.aws_subnet.public[0]' \
  'module.vpc.aws_subnet.this["public-a"]'

terraform state mv \
  'module.vpc.aws_subnet.public[1]' \
  'module.vpc.aws_subnet.this["public-b"]'
```

**Buoc 4 (Terraform >= 1.1) - Dung `moved` block (an toan hon):**

```hcl
# Them vao configuration file (se hoc ky hon o Day 10)
moved {
  from = aws_subnet.public[0]
  to   = aws_subnet.this["public-a"]
}

moved {
  from = aws_subnet.public[1]
  to   = aws_subnet.this["public-b"]
}
```

`moved` block la declarative, an toan hon `state mv` vi no duoc version-controlled va review duoc. Day 10 se di sau hon vao `moved`, `import`, va `lifecycle`.

### 4.5 Best practices

| Context | Recommendation | Ly do |
|---------|----------------|-------|
| Boolean toggle resource | `count = var.enable ? 1 : 0` | Don gian, ro rang intent |
| Identical replicas | `count = var.replica_count` | Chap nhan index, dong nhat |
| Named resources | `for_each = var.services` (map) | Key stable, ref by name |
| SG rules | `for_each` voi flat map | Rules co the them/xoa bat ky luc nao |
| Subnets trong module | `for_each` voi map(object) | Moi subnet co identity rieng |
| Conditional nested block | `dynamic` voi `for_each = condition ? [1] : []` | Toggle nested block |

**Anti-pattern can tranh:**

```hcl
# TRANG - Dung index de dat ten unique
resource "aws_subnet" "public" {
  count = 3
  tags = {
    Name = "subnet-${count.index}"  # Ten vo nghia
  }
}

# DUNG - Key co nghia
resource "aws_subnet" "this" {
  for_each = {
    "public-1a"  = { cidr = "10.0.1.0/24", az = "ap-southeast-1a" }
    "public-1b"  = { cidr = "10.0.2.0/24", az = "ap-southeast-1b" }
    "private-1a" = { cidr = "10.0.11.0/24", az = "ap-southeast-1a" }
  }
  tags = {
    Name = "${var.project}-${each.key}"  # Ten co nghia, stable
  }
}
```

### 4.6 Common pitfalls

**Pitfall 1 - for_each voi list truc tiep:**
```hcl
# SAI: for_each khong nhan list
resource "aws_security_group" "this" {
  for_each = ["api", "worker"]  # Error: for_each phai la map hoac set
}

# DUNG:
resource "aws_security_group" "this" {
  for_each = toset(["api", "worker"])  # Chuyen sang set
}
```

**Pitfall 2 - each.value khi dung set:**
```hcl
# Voi set(string): each.key == each.value (ca hai deu la string value)
resource "aws_security_group" "this" {
  for_each = toset(["api", "worker"])
  name     = each.value  # OK: "api", "worker"
  # Khong co each.value.something - vi each.value la string, khong phai object
}
```

**Pitfall 3 - dynamic block voi empty collection:**
```hcl
# Neu var.ingress_rules la empty list [], dynamic se khong tao block nao
# Day la behavior mong muon - khong phai bug

dynamic "ingress" {
  for_each = var.ingress_rules  # [] -> 0 ingress blocks
  content { ... }
}
```

**Pitfall 4 - Nested for_each trong module:**
```hcl
# Module khong the dung for_each ben trong no de goi child module
# Nhung root module co the goi module voi for_each:
module "subnet" {
  for_each = var.subnet_configs
  source   = "./modules/subnet"
  cidr     = each.value.cidr
}
```

**Pitfall 5 - Thay doi key trong for_each:**
```hcl
# NGUY HIEM: Doi ten key = destroy + recreate resource do
# Truoc: for_each = { "public-1a" = ... }
# Sau:   for_each = { "pub-1a" = ... }   <- "public-1a" bi destroy, "pub-1a" duoc create
# Trong prod: can dung "moved" block de rename key an toan
```

---

## 5. Hands-on Lab - 60 phut

### Muc tieu lab

Ket thuc lab nay, ban co module VPC su dung `for_each` cho subnets, security group voi `dynamic` blocks cho rules, va da thuc hien refactor tu `count` sang `for_each` an toan (demo voi `moved` block).

### Cau truc lab

```
day-09-lab/
├── modules/
│   └── vpc-advanced/
│       ├── main.tf          # Subnets voi for_each, SG voi dynamic
│       ├── variables.tf     # Complex type variables
│       ├── outputs.tf
│       └── versions.tf
├── main.tf                  # Root module goi vpc-advanced
├── variables.tf
├── outputs.tf
├── terraform.tfvars
└── versions.tf
```

---

### Part 1: Tao nhieu subnet bang for_each (15 phut)

**`modules/vpc-advanced/versions.tf`:**

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

**`modules/vpc-advanced/variables.tf`:**

```hcl
variable "project_name" {
  description = "Ten project, dung trong naming convention"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name chi duoc chua lowercase letters, numbers, hyphens."
  }
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phai la: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR. Vi du: 10.0.0.0/16"
  }
}

# Map of objects - day la core pattern cua Day 9
variable "subnets" {
  description = <<-EOT
    Map cua subnet configurations. Key la ten subnet (dung lam resource identifier).
    Value la object chua CIDR, AZ, va loai subnet.
    Vi du:
    {
      "public-1a" = { cidr = "10.0.1.0/24", az = "ap-southeast-1a", public = true }
      "private-1a" = { cidr = "10.0.11.0/24", az = "ap-southeast-1a", public = false }
    }
  EOT
  type = map(object({
    cidr   = string
    az     = string
    public = bool
  }))

  validation {
    condition = alltrue([
      for k, v in var.subnets : can(cidrnetmask(v.cidr))
    ])
    error_message = "Tat ca subnet cidr phai la valid CIDR notation."
  }
}

variable "ingress_rules" {
  description = "Danh sach ingress security group rules"
  type = list(object({
    description = string
    port        = number
    protocol    = string
    cidr_blocks = list(string)
  }))
  default = []
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
```

**`modules/vpc-advanced/main.tf`:**

```hcl
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags
  )

  # Tach public subnets tu map de build route table associations
  public_subnet_keys = [
    for k, v in var.subnets : k
    if v.public == true
  ]

  private_subnet_keys = [
    for k, v in var.subnets : k
    if v.public == false
  ]
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# Subnets - dung for_each voi map(object)
# State key se la: aws_subnet.this["public-1a"], aws_subnet.this["private-1a"], ...
resource "aws_subnet" "this" {
  for_each = var.subnets

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = each.value.public

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-${each.key}"
    Tier = each.value.public ? "public" : "private"
  })
}

# Route table cho public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
  })
}

# Associate tat ca public subnets voi public route table
# for_each tren local.public_subnet_keys (list cua subnet keys)
resource "aws_route_table_association" "public" {
  for_each = toset(local.public_subnet_keys)

  subnet_id      = aws_subnet.this[each.key].id
  route_table_id = aws_route_table.public.id
}

# Route table cho private subnets (khong co internet route)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt"
  })
}

# Associate tat ca private subnets
resource "aws_route_table_association" "private" {
  for_each = toset(local.private_subnet_keys)

  subnet_id      = aws_subnet.this[each.key].id
  route_table_id = aws_route_table.private.id
}

# Security Group voi dynamic ingress rules
resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app-sg"
  description = "Application security group for ${local.name_prefix}"
  vpc_id      = aws_vpc.main.id

  # Dynamic ingress rules - driven by var.ingress_rules
  dynamic "ingress" {
    for_each = var.ingress_rules
    iterator = rule                        # Custom iterator label cho readability

    content {
      description = rule.value.description
      from_port   = rule.value.port
      to_port     = rule.value.port
      protocol    = rule.value.protocol
      cidr_blocks = rule.value.cidr_blocks
    }
  }

  # Egress luon allow all - explicit block (khong doi)
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-app-sg"
  })

  lifecycle {
    # Neu SG rules duoc quan ly ben ngoai Terraform (Console, SDK), ignore changes
    # Thao luan: nen hay khong nen? -> Xem section trade-off o document.md
    create_before_destroy = true
  }
}
```

**`modules/vpc-advanced/outputs.tf`:**

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.main.cidr_block
}

# Output map: key = subnet name, value = subnet ID
# Cho phep caller reference: module.vpc.subnet_ids["public-1a"]
output "subnet_ids" {
  description = "Map cua subnet name -> subnet ID"
  value       = { for k, v in aws_subnet.this : k => v.id }
}

# Tien ich: chi public subnet IDs
output "public_subnet_ids" {
  description = "List cua public subnet IDs"
  value = [
    for k, v in aws_subnet.this : v.id
    if var.subnets[k].public == true
  ]
}

# Tien ich: chi private subnet IDs
output "private_subnet_ids" {
  description = "List cua private subnet IDs"
  value = [
    for k, v in aws_subnet.this : v.id
    if var.subnets[k].public == false
  ]
}

output "security_group_id" {
  description = "App security group ID"
  value       = aws_security_group.app.id
}

output "internet_gateway_id" {
  description = "Internet Gateway ID"
  value       = aws_internet_gateway.main.id
}
```

---

### Part 2: Root module voi complex config (10 phut)

**`versions.tf`:**

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

**`variables.tf`:**

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Ten project"
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "dev"
}
```

**`main.tf`:**

```hcl
module "vpc" {
  source = "./modules/vpc-advanced"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = "10.10.0.0/16"

  # for_each subnets: map voi 4 subnet, 2 public + 2 private
  subnets = {
    "public-1a" = {
      cidr   = "10.10.1.0/24"
      az     = "${var.aws_region}a"
      public = true
    }
    "public-1b" = {
      cidr   = "10.10.2.0/24"
      az     = "${var.aws_region}b"
      public = true
    }
    "private-1a" = {
      cidr   = "10.10.11.0/24"
      az     = "${var.aws_region}a"
      public = false
    }
    "private-1b" = {
      cidr   = "10.10.12.0/24"
      az     = "${var.aws_region}b"
      public = false
    }
  }

  # ingress_rules duoc driven by list -> dynamic block
  ingress_rules = [
    {
      description = "HTTP from internal"
      port        = 80
      protocol    = "tcp"
      cidr_blocks = ["10.0.0.0/8"]
    },
    {
      description = "HTTPS from public"
      port        = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    },
    {
      description = "App port from internal"
      port        = 8080
      protocol    = "tcp"
      cidr_blocks = ["10.10.0.0/16"]
    },
  ]

  tags = {
    Lab = "day-09-advanced-hcl"
  }
}
```

**`outputs.tf`:**

```hcl
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "all_subnet_ids" {
  description = "Map cua tat ca subnet IDs"
  value       = module.vpc.subnet_ids
}

output "public_subnet_ids" {
  value = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "security_group_id" {
  value = module.vpc.security_group_id
}
```

**`terraform.tfvars`:**

```hcl
aws_region   = "ap-southeast-1"
project_name = "myapp"
environment  = "dev"
```

---

### Part 3: Chay lab va quan sat output (10 phut)

```bash
cd ~/terraform-day9-lab

terraform init
```

Expected output quan trong:
```
Initializing modules...
- vpc in ./modules/vpc-advanced
```

```bash
terraform plan
```

Quan sat trong plan output:
- Resource dung `for_each` se co key thay vi index: `aws_subnet.this["public-1a"]`
- 3 `ingress` blocks duoc generate tu `dynamic` block

Expected plan (rut gon):
```
Terraform will perform the following actions:

  # module.vpc.aws_subnet.this["private-1a"] will be created
  # module.vpc.aws_subnet.this["private-1b"] will be created
  # module.vpc.aws_subnet.this["public-1a"] will be created
  # module.vpc.aws_subnet.this["public-1b"] will be created
  # module.vpc.aws_security_group.app will be created
    + ingress {
        + description      = "HTTP from internal"
        + from_port        = 80
        + to_port          = 80
        ...
      }
    + ingress {
        + description      = "HTTPS from public"
        + from_port        = 443
        ...
      }
    + ingress {
        + description      = "App port from internal"
        + from_port        = 8080
        ...
      }

Plan: 10 to add, 0 to change, 0 to destroy.
```

```bash
terraform apply
```

```bash
# Xem state structure - chu y keys
terraform state list | grep subnet
# module.vpc.aws_subnet.this["private-1a"]
# module.vpc.aws_subnet.this["private-1b"]
# module.vpc.aws_subnet.this["public-1a"]
# module.vpc.aws_subnet.this["public-1b"]

# Xem output map
terraform output all_subnet_ids
# {
#   "private-1a" = "subnet-0abc..."
#   "private-1b" = "subnet-0def..."
#   "public-1a"  = "subnet-0ghi..."
#   "public-1b"  = "subnet-0jkl..."
# }
```

---

### Part 4: Demo index-shift pitfall va for_each solution (15 phut)

**Part 4a - Tao resources voi count de demo)**

Them vao `main.tf` (sau module block):

```hcl
# Demo: Tao security group rules voi count (cach cu)
variable "demo_services_count" {
  type    = list(string)
  default = ["api", "worker", "admin"]
}

resource "aws_security_group" "demo_count" {
  name        = "${var.project_name}-${var.environment}-demo-count-sg"
  description = "Demo: using count"
  vpc_id      = module.vpc.vpc_id

  tags = {
    Name    = "${var.project_name}-demo-count"
    Purpose = "count-demo"
  }
}

resource "aws_security_group_rule" "demo_count" {
  count = length(var.demo_services_count)

  type              = "ingress"
  from_port         = 8080 + count.index
  to_port           = 8080 + count.index
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/8"]
  security_group_id = aws_security_group.demo_count.id
  description       = "Rule for ${var.demo_services_count[count.index]}"
}
```

Apply:
```bash
terraform apply -auto-approve

# Kiem tra state
terraform state list | grep demo_count
# aws_security_group_rule.demo_count[0]  <- api
# aws_security_group_rule.demo_count[1]  <- worker
# aws_security_group_rule.demo_count[2]  <- admin
```

**Part 4b - Simulate index shift (xoa "worker" o giua):**

```hcl
variable "demo_services_count" {
  type    = list(string)
  default = ["api", "admin"]  # Xoa "worker"
}
```

```bash
terraform plan

# Quan sat output:
# aws_security_group_rule.demo_count[1] will be updated in-place  <- THAY DOI! (was worker, now admin)
# aws_security_group_rule.demo_count[2] will be destroyed         <- admin cu bi xoa
```

Day chinh xac la van de: "admin" rule co index 2 bi destroy va index 1 bi modify. Trong production, day tao security gap.

**Part 4c - Refactor sang for_each:**

```hcl
# Thay the demo_services_count va aws_security_group_rule.demo_count bang:
variable "demo_services_foreach" {
  type = map(object({
    port = number
  }))
  default = {
    "api"    = { port = 8080 }
    "worker" = { port = 8081 }
    "admin"  = { port = 8082 }
  }
}

resource "aws_security_group_rule" "demo_foreach" {
  for_each = var.demo_services_foreach

  type              = "ingress"
  from_port         = each.value.port
  to_port           = each.value.port
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/8"]
  security_group_id = aws_security_group.demo_count.id
  description       = "Rule for ${each.key}"
}
```

Xoa "worker" khoi map:
```hcl
variable "demo_services_foreach" {
  type = map(object({
    port = number
  }))
  default = {
    "api"   = { port = 8080 }
    "admin" = { port = 8082 }
  }
}
```

```bash
terraform plan
# aws_security_group_rule.demo_foreach["worker"] will be destroyed  <- chi "worker" bi xoa
# aws_security_group_rule.demo_foreach["api"]   -> unchanged
# aws_security_group_rule.demo_foreach["admin"] -> unchanged
# An toan!
```

---

### Troubleshooting pho bien

**Loi 1: for_each voi list:**
```
Error: Invalid for_each argument
The given value is not suitable for use in for_each. The type is list of string,
and for_each requires a map or set.
```
Fix: `for_each = toset(your_list)` hoac chuyen sang `map`.

**Loi 2: Duplicate key trong map:**
```
Error: Duplicate key
Two items produced the key "api" in this 'for' expression.
```
Fix: Ensure tat ca key la unique. Neu tu list, dung `distinct()` truoc.

**Loi 3: each.value.field khong ton tai:**
```
Error: Unsupported attribute
An object with no attributes is not suitable.
```
Fix: Kiem tra lai type definition trong variable. Dung `try(each.value.field, default_value)` cho optional fields.

**Loi 4: Unknown value trong for_each:**
```
Error: Invalid for_each argument
The "for_each" value depends on resource attributes that cannot be determined
until apply.
```
Fix: `for_each` value phai biet truoc khi apply. Tranh dung computed resource attribute (nhu ID moi tao) lam for_each key. Dung static keys thay vi dynamic IDs.

---

### Cleanup

```bash
cd ~/terraform-day9-lab

terraform destroy
# Confirm: yes

# Expected: Destroy complete! Resources: X destroyed.
```

---

## 6. Kiem tra hieu bai

1. **Giai thich tai sao `for_each` khong nhan `list(string)` truc tiep.** Cach fix la gi va khi nao dung `toset()` vs tao map thu cong?

2. **Ban co resource dung `count = 4`. Plan hien tai: `[0]=api, [1]=worker, [2]=scheduler, [3]=admin`. Team quyet dinh xoa `worker`.** Mo ta chinh xac dieu gi se xay ra khi ban xoa `worker` khoi list va chay `terraform plan`. Tai sao day la van de va lam sao tranh?

3. **Phan biet khi nao dung `dynamic` block vs `for_each` tren resource.** Cho vi du cu the cua tung truong hop va giai thich tai sao khong the hoan doi nhau.

4. **`try(var.config.advanced.timeout, 30)` vs `lookup(var.config, "timeout", 30)` - hai cach nay co tuong duong nhau khong?** Giai thich su khac nhau ve input type va truong hop dung.

5. **Debug scenario:** Team chuyen subnet tu `count` sang `for_each`. Sau khi sua code, `terraform plan` bao se destroy 2 subnet hien co va tao 2 subnet moi. Subnet nay dang duoc dung boi EC2 instances. Ban xu ly nhu the nao de tranh downtime?

---

## 7. Tom tat cuoi ngay

### Key points

- **`count` dung index, `for_each` dung key:** Day la su khac biet co ban. Index thay doi khi danh sach thay doi, key khong thay doi. Production code nen dung `for_each` cho tat ca resource co identity rieng
- **`for_each` can map hoac set, khong nhan list:** Chuyen list sang `toset()` neu khong quan tam order, hoac tao map voi meaningful key
- **Dynamic block = for_each cho nested blocks:** Khi so luong nested config bi quyet dinh boi data (ingress rules, tags, volumes), dung `dynamic` thay vi viet tung block
- **`for` expression la functional transform:** Tuong tu `map()`, `filter()` trong Go/TS. Dung de transform collection truoc khi truyen vao `for_each` hoac output
- **`merge`, `lookup`, `try`, `can` la utility functions:** `merge` gop map (last wins), `lookup` safe access voi default, `try` handle optional nested access, `can` validate expression trong validation block
- **Migration count->for_each can trigger destroy+recreate:** Dung `moved` block (Terraform >= 1.1) hoac `terraform state mv` de doi ten state key ma khong tao lai resource

### Ket qua da tao ra

- Module `vpc-advanced` voi `for_each` cho subnets (map of objects) va `dynamic` block cho security group rules
- Root module su dung complex map config cho subnets
- Demo ro rang van de index-shift khi dung `count` va cach for_each giai quyet

### Chuan bi cho Day 10 - Lifecycle, Import, Moved Blocks

Day 10 se di sau vao:
- `lifecycle` meta-arguments: `create_before_destroy`, `prevent_destroy`, `ignore_changes`, `replace_triggered_by`
- `terraform import`: mang existing resource vao Terraform management
- `moved` block: rename/move resources trong state ma khong destroy
- `removed` block: xoa resource khoi state ma khong destroy thuc te

Day 10 se giup ban xu ly van de count-to-for_each migration du phong hon. `moved` block la cong cu chinh - ban da thay no duoc preview o Day 9 Part 4. Truoc buoi hoc, nhin lai state sau lab hom nay va nghi ve nhung resource nao co the can duoc rename/move trong tuong lai.

---

## 8. Tham khao them

- [for_each Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each) - Official docs
- [count Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/count) - Official docs
- [dynamic Blocks](https://developer.hashicorp.com/terraform/language/expressions/dynamic-blocks) - Official docs
- [for Expressions](https://developer.hashicorp.com/terraform/language/expressions/for) - Official docs
- [Type Constraints](https://developer.hashicorp.com/terraform/language/expressions/type-constraints) - object, map, list, set
- [Built-in Functions](https://developer.hashicorp.com/terraform/language/functions) - merge, lookup, try, can va toan bo function list
- [moved Block](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring) - Preview cho Day 10
- [Custom Conditions](https://developer.hashicorp.com/terraform/language/expressions/custom-conditions) - can() trong validation
