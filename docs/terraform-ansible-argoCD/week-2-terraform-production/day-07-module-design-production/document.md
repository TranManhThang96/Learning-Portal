# Day 7: Module Design for Production - Reference Document

**Dung de tham khao nhanh trong va sau khi hoc. Khong phai tai lieu hoc chinh.**

---

## 1. Module Design Patterns Reference

### Pattern 1: Opinionated Internal Wrapper

Dung khi team muon enforce company standards ma van tan dung community module.

```hcl
# modules/vpc-internal/main.tf
# Wrapper around terraform-aws-modules/vpc/aws with company standards enforced

module "vpc_community" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # ===========================================================
  # ENFORCED - Caller khong the override (khong expose bien nay)
  # ===========================================================
  enable_flow_log                      = true
  flow_log_cloudwatch_log_group_name   = "/aws/vpc/${var.project_name}-${var.environment}"
  flow_log_traffic_type                = "ALL"
  flow_log_cloudwatch_log_group_retention_in_days = local.log_retention_by_env[var.environment]

  # Default SG hardening (khong cho phep gi)
  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []

  # Tagging bat buoc theo company standard
  tags = local.enforced_tags

  # ===========================================================
  # CONFIGURABLE - Caller co the set qua input variable
  # ===========================================================
  name            = "${var.project_name}-${var.environment}"
  cidr            = var.vpc_cidr
  azs             = var.availability_zones
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway = var.nat_gateway_config.enabled
  single_nat_gateway = var.nat_gateway_config.single_az
}

locals {
  # Opinionated: prod phai retain log lau hon
  log_retention_by_env = {
    dev     = 7
    staging = 30
    prod    = 90
  }

  # Company-mandated tags - khong the override
  enforced_tags = {
    ManagedBy     = "terraform"
    CostCenter    = var.cost_center
    SecurityLevel = var.environment == "prod" ? "high" : "standard"
    Compliance    = "required"
  }
}
```

### Pattern 2: Module Composition voi Data Passing

```hcl
# environments/prod/main.tf

module "vpc" {
  source       = "../../modules/vpc-production"
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  # ... other inputs
}

module "security_groups" {
  source       = "../../modules/security-groups"
  project_name = var.project_name
  environment  = var.environment

  # Output cua vpc module -> input cua security_groups module
  vpc_id   = module.vpc.vpc_id
  vpc_cidr = module.vpc.vpc_cidr
}

module "eks" {
  source       = "../../modules/eks"
  project_name = var.project_name
  environment  = var.environment

  # Composition: output tu nhieu module
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.subnet_ids.private
  cluster_sg_id      = module.security_groups.eks_cluster_sg_id
  worker_sg_id       = module.security_groups.eks_worker_sg_id
}
```

### Pattern 3: Conditional Resource Creation

```hcl
# Co 3 cach tao conditional resource trong Terraform

# Cach 1: count = 0 hoac 1 (don gian nhat)
resource "aws_nat_gateway" "main" {
  count = var.enable_nat ? 1 : 0
  # ...
}
# Truy cap: aws_nat_gateway.main[0].id (phai check count truoc)

# Cach 2: for_each voi empty map/set
resource "aws_flow_log" "main" {
  for_each = var.flow_logs_enabled ? toset(["main"]) : toset([])
  # ...
}
# Truy cap: aws_flow_log.main["main"].id

# Cach 3: count voi complex condition
locals {
  nat_count = var.enable_nat ? (var.single_az ? 1 : length(var.azs)) : 0
}
resource "aws_nat_gateway" "main" {
  count = local.nat_count
  # ...
}
```

**Uu tien:** `for_each` tot hon `count` khi resource co the bi xoa giua cac phan tu (tranh "index shift" problem). `count` OK khi tap resource la homogeneous va stt quan trong.

### Pattern 4: Dynamic Block

```hcl
# Dung khi so luong block phu thuoc vao input
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  # Them route chi khi NAT dang bat
  dynamic "route" {
    for_each = var.enable_nat ? [aws_nat_gateway.main[0].id] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = route.value
    }
  }

  # Co the co nhieu dynamic block
  dynamic "route" {
    for_each = var.additional_routes
    content {
      cidr_block                = route.value.cidr
      vpc_peering_connection_id = route.value.peering_id
    }
  }
}
```

### Pattern 5: Cross-Variable Validation

```hcl
# Terraform khong co built-in cross-variable validation (cho den v1.9 co precondition)
# Cach dung hieu qua nhat: tobool() trong local

locals {
  # Neu condition fail -> tobool("error message") -> Terraform throw error
  _validate_nat_needs_public_subnet = (
    var.enable_nat && length(var.public_subnet_cidrs) == 0
    ? tobool("NAT Gateway yeu cau it nhat 1 public subnet. Truyen public_subnet_cidrs khi enable_nat = true.")
    : true
  )

  _validate_subnet_az_count = (
    length(var.public_subnet_cidrs) != length(var.azs)
    ? tobool("So luong public_subnet_cidrs phai bang so luong availability_zones. Got: ${length(var.public_subnet_cidrs)} cidrs vs ${length(var.azs)} AZs")
    : true
  )
}
```

Tf 1.9+ ho tro `check` block va `precondition` trong resource, nhung tobool pattern van hoat dong tren Tf 1.4+.

---

## 2. Interface Design Checklist

Su dung checklist nay truoc khi "release" module cho team dung.

### Input Variables Checklist

```
[ ] Moi variable co description day du (it nhat 1 cau giai thich tai sao can variable nay)
[ ] Moi variable co type constraint (khong dung "type = any")
[ ] Variable optional co default gia tri co y nghia (khong de default = null tru khi can thiet)
[ ] Variable bat buoc (khong co default) duoc ghi ro trong description la "REQUIRED"
[ ] Validation rule cho:
    - String: format, allowed values (bang contains()), length limit
    - Number: min/max range
    - List: length constraint, element format
    - Object: required vs optional keys
[ ] Cross-variable validation cho cac rang buoc phuc tap
[ ] Khong co variable nao expose internal implementation detail
    (vi du: khong co "aws_vpc_resource_name" = variable)
[ ] Variable name ro rang, khong the nham lan voi module khac khi dung composition
    ("vpc_cidr" thay vi "cidr", "eks_version" thay vi "version")
[ ] Sensitive variable duoc danh dau "sensitive = true"
```

### Output Values Checklist

```
[ ] Moi output co description giai thich:
    - Gia tri la gi
    - Khi nao/tai sao consumer can su dung
    - Format/type cua gia tri
[ ] Output name la stable identifier, khong depend vao internal resource name
    (vpc_id tot hon, aws_vpc_main_id xau)
[ ] Chi output nhung gi consumer thuc su can
    (khong output tat ca resource attribute)
[ ] Sensitive output duoc danh dau "sensitive = true"
[ ] Output duoc nhom logic (primary / optional / metadata)
[ ] Structured output cho related values
    (subnet_ids.public/private thay vi flat public_subnet_ids + private_subnet_ids)
[ ] Consistent naming convention voi cac module khac
```

### Module Interface Review Questions

Truoc khi commit module va cho team dung, tra loi cac cau hoi nay:

1. Neu toi rename resource ben trong tu "main" sang "primary", co output nao bi break khong?
2. Neu toi them 1 AZ moi, output format co thay doi theo cach unexpected khong?
3. Neu consumer chi biet ten module (khong biet source code), ho biet exactly infra gi duoc tao ra khong?
4. Neu security team doc list output, ho co the biet sensitive thong tin bi expose khong?
5. Calller co the reuse module nay cho 3 environment khac nhau chi bang cach doi input khong?

---

## 3. Module Boundary Decision Matrix

Dung matrix nay khi phan van "nen tach module nay ra khong?"

### Axis 1: Lifecycle Similarity

| Score | Mo ta |
|-------|-------|
| 5 | Tat ca resource duoc tao/xoa/update voi cung ly do |
| 3 | Mostly cung lifecycle, co 1-2 resource update doc lap |
| 1 | Resource thuong duoc update rieng le voi cac ly do khac nhau |

### Axis 2: Team Ownership

| Score | Mo ta |
|-------|-------|
| 5 | Mot team duy nhat own tat ca resource |
| 3 | Mostly mot team, nhung doi khi team khac can access |
| 1 | Nhieu team co need update cac resource khac nhau |

### Axis 3: Blast Radius

| Score | Mo ta |
|-------|-------|
| 5 | Tac dong cua moi change duoc can toan bo nhom resource |
| 3 | Mot so resource co the bi anh huong ngoai y muon |
| 1 | Change 1 resource co the trigger recreate resource khac |

### Axis 4: Reusability

| Score | Mo ta |
|-------|-------|
| 5 | Group luon di cung nhau, khong co value khi tach |
| 3 | Doi khi chi can mot phan |
| 1 | Thuong xuyen chi can mot phan cua group |

### Ra quyet dinh

```
Tinh tong score (4 axes):

16-20: Gop vao 1 module. Chung co lifecycle tight, cung owner, rui ro tach la cao.
11-15: Co the gop nhung xem xet tach neu team grow hoac complexity tang.
6-10:  Nen tach. Co du dau hieu la 2 concern khac nhau.
4-5:   Phai tach. Chung khong nen cung module.
```

### Vi du thuc te ap dung matrix

| Resource group | Lifecycle | Ownership | Blast Radius | Reuse | Total | Decision |
|---------------|-----------|-----------|--------------|-------|-------|----------|
| VPC + IGW + Subnet | 5 | 5 | 5 | 5 | 20 | Gop |
| Subnet + Route Table | 4 | 5 | 4 | 4 | 17 | Gop |
| VPC + NAT Gateway | 3 | 4 | 3 | 2 | 12 | Xem xet tach (vi optional, costly) |
| VPC + Security Group | 2 | 2 | 2 | 1 | 7 | Nen tach |
| VPC + EKS | 1 | 1 | 1 | 1 | 4 | Phai tach |

---

## 4. Versioning Strategy Comparison Table

### Strategy Overview

| Strategy | Source Syntax | Lock Type | Reproducible | Complexity |
|----------|--------------|-----------|--------------|------------|
| Local path | `./modules/vpc` | None (always latest) | No | Thap nhat |
| Git branch | `git::...?ref=main` | Branch (moving) | No | Thap |
| Git tag | `git::...?ref=v1.2.0` | Tag (immutable) | Yes | Trung binh |
| Git commit | `git::...?ref=a1b2c3d` | Commit (immutable) | Yes | Cao |
| Private Registry | `myorg.com/vpc/aws` + `version` | Semantic version | Yes (khi pin) | Cao nhat |

### Semantic Version Constraints

| Constraint | Cho phep | Vi du |
|-----------|----------|-------|
| `= 1.2.3` | Exact version 1.2.3 only | Prod: khong bao gio surprise |
| `!= 1.2.3` | Tat ca tru 1.2.3 | Block known broken version |
| `> 1.2.3` | Greater than | It dung |
| `>= 1.2.3` | 1.2.3 tro len | Flexible lower bound |
| `< 2.0.0` | Truoc 2.0.0 | Block major version |
| `~> 1.2` | >= 1.2.0, < 1.3.0 (patch only) | Conservative |
| `~> 1.0` | >= 1.0.0, < 2.0.0 (minor+patch OK) | Common cho dev |
| `>= 1.0, < 2.0` | Tuong duong `~> 1.0` nhung explicit | Ro rang hon |

### Versioning per Environment Recommendation

```hcl
# environments/dev/main.tf
module "vpc" {
  source  = "git::https://github.com/myorg/tf-modules.git//vpc?ref=main"
  # Dev luon dung latest - phat hien breaking change som
}

# environments/staging/main.tf
module "vpc" {
  source  = "git::https://github.com/myorg/tf-modules.git//vpc?ref=v2.1"
  # Staging pin minor version - test truoc khi len prod
}

# environments/prod/main.tf
module "vpc" {
  source  = "git::https://github.com/myorg/tf-modules.git//vpc?ref=v2.1.3"
  # Prod pin exact version - khong bao gio surprise
}
```

### Module Release Lifecycle

```
Draft -> v0.1.0-alpha -> v0.1.0-beta -> v0.1.0 -> v0.1.1 -> v0.2.0 -> v1.0.0
                                          |          |          |          |
                                       Dev test   Bug fix   New feat   Stable API
                                                  (patch)   (minor)   (major)

Quy tac:
  PATCH (0.1.0 -> 0.1.1): Bug fix, khong thay doi interface
  MINOR (0.1.0 -> 0.2.0): New feature, backward compatible
  MAJOR (0.x.0 -> 1.0.0): Breaking change trong interface (input/output)

Breaking change vi du:
  - Them required variable (khong co default)
  - Xoa output hoac doi ten output
  - Doi type cua variable (string -> object)
  - Doi behavior cua feature hien co
```

### CHANGELOG Template cho Module

```markdown
# CHANGELOG - vpc-production module

## [Unreleased]

## [0.2.0] - 2024-01-15

### Added
- `subnet_details` output voi AZ information
- `vpc_metadata` output cho debugging

### Changed
- `subnet_ids` output da duoc restructure tu `list(string)` sang `object({public, private})`
  BREAKING CHANGE: Update consumer code truoc khi upgrade
  Migration guide: `module.vpc.private_subnet_ids` -> `module.vpc.subnet_ids.private`

### Fixed
- Route table association khi single_az = false va nat_count > 1

## [0.1.0] - 2024-01-01

### Added
- Initial release
- VPC, subnets, IGW, NAT Gateway, route tables
- VPC Flow Logs (optional, default off)
- Default SG hardening
```

---

## 5. Common Anti-Patterns va Cach Fix

### Anti-pattern 1: God Module

```
Symptom:
  - Module co > 15 required inputs
  - Module co > 50 resource
  - terraform plan mat > 2 phut
  - "Toi so sua module vi khong biet se anh huong gi"

Fix:
  1. List tat ca resource trong module
  2. Group theo lifecycle (xem Section 3.1 cua lesson.md)
  3. Tach thanh 2-3 module con
  4. Wire chung qua composition
```

### Anti-pattern 2: Leaky Abstraction

```
Symptom:
  - Output ten nhu: aws_vpc_main_id, aws_subnet_public_0_id
  - Output la toan bo resource object: value = aws_vpc.main
  - Consumer code dung: module.vpc.aws_vpc.main.enable_dns_hostnames

Fix:
  - Rename output bo internal resource name
  - Chi output attribute cu the can thiet
  - Consumer chi biet vpc_id, khong biet ten resource internal
```

### Anti-pattern 3: Magic Environment Behavior

```
Symptom:
  variable "environment" { ... }
  
  resource "aws_db_instance" "main" {
    instance_class    = var.environment == "prod" ? "db.r5.2xlarge" : "db.t3.micro"
    multi_az          = var.environment == "prod" ? true : false
    deletion_protection = var.environment == "prod" ? true : false
    # 10 dong if/else dua tren environment
  }

Problem:
  - Caller truyen "prod" va khong biet chinh xac instance se la gi
  - Qua nhieu logic an phia sau 1 variable
  - Kho test vi phai test tat ca environment permutation

Fix:
  - Expose explicit variable cho tung concern
    multi_az = var.multi_az (default: false)
    instance_class = var.db_instance_class (default: "db.t3.micro")
  - Caller (root module) quyet dinh gia tri theo environment
  - Module co the van giu environment variable cho naming, nhung khong dung no de quyet dinh sizing
```

### Anti-pattern 4: Missing Version Constraint

```hcl
# BAD: Khong co version constraint trong module
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Khong co version constraint
    }
  }
}

# Problem: khi AWS provider release breaking version, module bi break
# Fix: Luon co constraint, it nhat la major version bound

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0, < 6.0.0"  # Chap nhan patch + minor, block major
    }
  }
}
```

### Anti-pattern 5: Provider Configuration trong Module

```hcl
# BAD: Dung provider block trong child module
# modules/vpc/main.tf
provider "aws" {
  region = "ap-southeast-1"  # Hardcode region -> module khong reusable
}

# GOOD: Provider duoc cau hinh o root module, module nhan qua provider meta-argument
# modules/vpc/main.tf: khong co provider block

# root module: main.tf
provider "aws" {
  region = var.aws_region  # Configurable
}

module "vpc" {
  source = "./modules/vpc"
  # Provider duoc ke thua tu root module tu dong
}

# Truong hop multi-region:
provider "aws" {
  alias  = "singapore"
  region = "ap-southeast-1"
}

provider "aws" {
  alias  = "tokyo"
  region = "ap-northeast-1"
}

module "vpc_sg" {
  source   = "./modules/vpc"
  providers = { aws = aws.singapore }
}

module "vpc_tokyo" {
  source    = "./modules/vpc"
  providers = { aws = aws.tokyo }
}
```

---

## 6. Security Checklist cho Production Module

```
VPC Security Basics:
[ ] Default Security Group duoc hardened (khong co inbound/outbound rule)
[ ] VPC Flow Logs bat (it nhat cho staging va prod)
[ ] Khong co resource nao trong default SG
[ ] Public subnet chi chua load balancer, bastion host - khong phai application server
[ ] Private subnet cho tat ca application va database workload

Output Security:
[ ] Khong output secret, password, private key
[ ] Output sensitive duoc danh dau "sensitive = true"
[ ] Caller khong the access output cua module khac theo path lan trau
    (module.other_module.some_output -> chi qua wiring explicit)

IAM cho Flow Logs:
[ ] IAM Role dung least-privilege (chi permission can thiet cho CloudWatch Logs)
[ ] Role name khong trung voi role khac (dung name_prefix)
[ ] Policy inline (khong dung managed policy tru khi co ly do dac biet)

Tagging cho Security:
[ ] Tat ca resource co tag "Environment" de phan biet prod/non-prod
[ ] Tat ca resource co tag "ManagedBy = terraform" de biet nguon goc
[ ] Khong expose internal system information trong tag (version, config detail)
```
