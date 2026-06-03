# Day 6: Terraform Module Basics

**Thoi gian:** 2 gio | **Level:** Intermediate | **Prerequisites:** Day 1-5

---

## Muc tieu ngay hoc

Sau buoi hoc nay, ban co the:

1. Giai thich tai sao module can thiet bang cach liet ke it nhat 3 van de xay ra khi khong co module trong mot codebase nhieu environment
2. Phan biet root module va child module, mo ta luong data di chuyen qua input variable va output value
3. Viet mot module VPC hoan chinh voi input/output ro rang, co the tai su dung cho nhieu environment
4. Su dung output cua mot module lam input cho module khac (module composition)
5. Doc va su dung module tu Terraform Registry voi version constraint dung chuan

---

## Boi canh thuc te

### Van de xay ra khi team khong dung module

Ban vua xong Day 5. Remote backend da duoc setup. Team co 6 engineers. Platform team quan ly networking cho 3 environment: dev, staging, prod. Moi environment can: VPC, public subnets, private subnets, Internet Gateway, NAT Gateway, route tables.

**Incident 1 - Copy-paste drift:**

Engineer A viet VPC cho dev. Engineer B copy code sang cho staging, sua mot so gia tri. Hai thang sau, security team yeu cau bat VPC Flow Logs tren tat ca environment. Engineer A update dev. Engineer B quen update staging. Ba thang sau, audit phat hien staging khong co Flow Logs. Phat tien. Report. Post-mortem.

Van de: Khong co single source of truth cho "cach tao VPC dung chuan". Moi environment la mot copy rieng, diverge theo thoi gian.

**Incident 2 - CIDR conflict trong microservices:**

Moi microservice team tu quan ly networking rieng. Team Auth viet VPC code rieng. Team Payment viet VPC code rieng. Sau 6 thang, platform team phat hien Auth VPC va Payment VPC co CIDR overlap - khong the peer duoc. Rework toan bo networking, downtime 4 tieng.

Van de: Khong co cach enforce cau truc networking chung. Moi team re-invent the wheel theo cach rieng.

**Incident 3 - Khong scale duoc:**

Startup grow nhanh. Tu 2 len 15 microservices trong 6 thang. Moi service can environment rieng. Co nghia la 15 * 3 = 45 VPC configurations. Copy-paste 45 lan. Mot thay doi nho (them tag, doi naming convention) phai update 45 cho.

Van de: Infrastructure code khong scale cung voi to chuc.

### Voi microservices platform

Platform team thuong la "internal infrastructure provider" cho cac service team. Module chinh la cach platform team:
- Enforce standards (naming, tagging, security baseline) mot lan, ap dung moi noi
- Expose interface don gian (input/output) cho service team dung ma khong can hieu internals
- Ship updates (security patches, compliance changes) den tat ca consumer bang cach bump version

Day la pattern giong nhu npm package trong Node.js ecosystem, hoac internal shared library trong Java/Go. Ban da lam viec voi concept nay, chi la trong terraform context.

---

## Kien thuc nen tang - 30 phut

### 1. Module la gi va tai sao can no?

Module trong Terraform la mot tap hop cac file `.tf` trong mot thu muc. Moi thu muc chua file `.tf` deu la mot module - ke ca cai ban da viet tu Day 1.

Diem quan trong: **ban da dung module tu ngay dau, chi la chua biet goi ten no.**

Thu muc `day-01-lab/` cua ban la mot module. No duoc goi la **root module** - la entry point ma Terraform chay khi ban goi `terraform apply`.

```
Analogy voi programming:

Terraform Module  =  Go Package / Python Module / npm Package
Root module       =  main() function / entry point
Child module      =  imported package / library
module input      =  function argument
module output     =  function return value
```

```
Cau truc don gian:

root-module/              <- Root module (ban chay terraform o day)
  main.tf                 <- Co the goi child modules
  variables.tf
  outputs.tf
  backend.tf

modules/                  <- Thu vien cac child module
  vpc/                    <- Child module: VPC
    main.tf
    variables.tf
    outputs.tf
  security-groups/        <- Child module: Security Groups
    main.tf
    variables.tf
    outputs.tf
```

### 2. Root module vs Child module

**Root module:**
- La thu muc noi ban chay `terraform init`, `terraform plan`, `terraform apply`
- Co the khong co, mot, hoac nhieu child module
- Quan ly state
- Nhan gia tri tu: `.tfvars` files, environment variables, `-var` flag, hoac default

**Child module:**
- Duoc goi boi root module (hoac module khac) bang `module` block
- Nhan input tu noi goi no (caller)
- Expose output de noi goi no co the su dung
- Khong co state rieng - state duoc quan ly boi root module
- Co the duoc goi nhieu lan voi input khac nhau

```hcl
# Root module goi child module
module "vpc_prod" {
  source = "./modules/vpc"        # Duong dan den child module

  # Input variables - truyen vao child module
  vpc_cidr     = "10.0.0.0/16"
  environment  = "prod"
  project_name = "myapp"
}

module "vpc_staging" {
  source = "./modules/vpc"        # Cung module source

  # Input khac nhau = infra khac nhau tu cung mot template
  vpc_cidr     = "10.1.0.0/16"
  environment  = "staging"
  project_name = "myapp"
}
```

### 3. Module Input/Output - Luong data

Input va output la interface cua module. Day la cach module giao tiep voi the gioi ben ngoai.

```
                  Child Module: modules/vpc/
                 ┌───────────────────────────────┐
Root Module      │                               │
                 │  variables.tf                 │
vpc_cidr ───────►│  (input variables)            │
environment ────►│                               │
project_name ───►│  main.tf                      │
                 │  (resource definitions)       │
                 │                               │
                 │  outputs.tf                   │
                 │  (output values)              │
                 │                               │
                 └───────────────────────────────┘
                          │
                          ▼ (return values)
                 vpc_id, subnet_ids, ...
```

**Input variables** trong child module hoat dong giong nhu function parameters:

```hcl
# modules/vpc/variables.tf
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR block. Vi du: 10.0.0.0/16"
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phai la mot trong: dev, staging, prod"
  }
}

variable "enable_nat_gateway" {
  description = "Bat NAT Gateway cho private subnets. Chi phi ~$32/thang/AZ"
  type        = bool
  default     = true  # Co default = optional khi goi module
}
```

**Output values** la nhung gi module expose ra cho caller:

```hcl
# modules/vpc/outputs.tf
output "vpc_id" {
  description = "ID of the created VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}
```

**Su dung output trong root module:**

```hcl
# Root module: main.tf
module "vpc" {
  source = "./modules/vpc"
  # ...
}

# Truy cap output cua module bang: module.<name>.<output_name>
resource "aws_eks_cluster" "main" {
  name = "my-cluster"

  vpc_config {
    subnet_ids = module.vpc.private_subnet_ids  # Dung output tu module
  }
}
```

### 4. Module Composition

Module composition la khi output cua module nay tro thanh input cua module khac. Day la cach xay dung infrastructure phuc tap tu cac building blocks nho.

```
modules/vpc/         modules/security-groups/    modules/eks/
    │                        │                        │
    │  vpc_id ──────────────►│  vpc_id                │
    │  subnet_ids ──────────►│  subnet_ids            │
    │                        │                        │
    │  vpc_id ────────────────────────────────────────►│  vpc_id
    │  private_subnet_ids ────────────────────────────►│  subnet_ids
    │                        │  sg_id ────────────────►│  cluster_sg_id
```

```hcl
# Root module: main.tf - module composition example
module "vpc" {
  source       = "./modules/vpc"
  vpc_cidr     = var.vpc_cidr
  environment  = var.environment
  project_name = var.project_name
}

module "security_groups" {
  source      = "./modules/security-groups"
  vpc_id      = module.vpc.vpc_id          # Output tu vpc module
  environment = var.environment
}

module "eks" {
  source            = "./modules/eks"
  vpc_id            = module.vpc.vpc_id               # Output tu vpc
  subnet_ids        = module.vpc.private_subnet_ids   # Output tu vpc
  cluster_sg_id     = module.security_groups.eks_sg_id # Output tu security_groups
  environment       = var.environment
}
```

Terraform tu dong resolve dependency order: VPC phai duoc tao truoc Security Groups va EKS vi chung phu thuoc vao output cua VPC.

### 5. Module Sources - Noi Terraform tim module

```hcl
# Local path (pho bien nhat trong development)
module "vpc" {
  source = "./modules/vpc"
}

# Terraform Registry (hashicorp official hoac community)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}

# GitHub (private hoac public repo)
module "vpc" {
  source = "github.com/myorg/terraform-modules//vpc?ref=v2.1.0"
}

# Git URL chung
module "vpc" {
  source = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.1.0"
}

# S3 bucket (private module registry cho enterprise)
module "vpc" {
  source = "s3::https://s3-ap-southeast-1.amazonaws.com/my-modules/vpc.zip"
}
```

**Terraform Registry format:** `<namespace>/<module-name>/<provider>`
- `terraform-aws-modules/vpc/aws` = namespace: terraform-aws-modules, module: vpc, provider: aws
- Tim kiem tai: registry.terraform.io

### 6. Module Versioning

Version constraint cho module Registry source hoat dong giong nhu Go module hay npm:

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"

  # ~> 5.0 = >= 5.0.0, < 6.0.0 (patch updates OK, minor/major khong)
  version = "~> 5.0"

  # ~> 5.1 = >= 5.1.0, < 5.2.0 (chi patch)
  version = "~> 5.1"

  # Exact version cho production (reproducible)
  version = "= 5.5.2"

  # Flexible cho development
  version = ">= 5.0, < 6.0"
}
```

**Rule of thumb cho versioning:**

| Context        | Constraint Strategy                              | Ly do                                        |
|----------------|--------------------------------------------------|----------------------------------------------|
| Production     | `= 5.5.2` (exact)                                | Reproducible, khong co surprise updates      |
| Staging        | `~> 5.5` (patch flexible)                       | Test patch updates truoc khi len prod        |
| Development    | `~> 5.0` (minor flexible)                       | Nhan bug fixes va small improvements         |
| Learning       | `>= 5.0` (open-ended, khong dung prod)          | Luon co latest, chap nhan breaking changes   |

Local path source (`./modules/vpc`) khong co version constraint - version duoc quan ly boi Git tag/branch cua repo.

### 7. Module Structure - Convention

Mot module chuan co cac file sau:

```
modules/vpc/
  main.tf          # Resources chinh
  variables.tf     # Input variables (co description, type, validation)
  outputs.tf       # Output values (co description)
  versions.tf      # required_providers va required_version
  README.md        # (Optional nhung nen co) Interface documentation
```

**Khong nen** dat trong module:
- `backend.tf` - Module khong co state rieng
- `provider configuration` - Provider duoc cau hinh o root module, khong phai trong module
- `terraform.tfvars` - Khong co y nghia trong module context

---

## Deep Dive & Trade-offs - 30 phut

### 1. Module granularity - To hay nho?

Day la quyet dinh kien truc quan trong nhat khi thiet ke module.

**Option A - Mega module (Coarse-grained):**

```
modules/
  networking/     # VPC + subnets + IGW + NAT + route tables + SGs + NACLs
```

Uu diem:
- Don gian cho nguoi dung (it variable hon, it module call hon)
- Dependency management don gian hon (it wiring)
- Nhanh hon de bat dau

Nhuoc diem:
- Blast radius lon - thay doi SG co the trigger recreation VPC
- Plan/apply cham vi nhieu resource
- Kho tai su dung tung phan rieng le
- Team khac nhau can update cac phan khac nhau, conflict nhieu hon

**Option B - Micro module (Fine-grained):**

```
modules/
  vpc/            # Chi VPC + CIDR config
  subnets/        # Chi subnets (public/private)
  nat-gateway/    # Chi NAT Gateway
  security-groups/
    eks-sg/
    rds-sg/
    bastion-sg/
```

Uu diem:
- Blast radius nho, each module doc lap
- Co the compose theo nhieu cach khac nhau
- De test rieng le
- Nhieu team co the work tren different module khong conflict

Nhuoc diem:
- Nhieu module call, nhieu wiring
- Nguoi dung module phai hieu nhieu hon
- Dependency management phuc tap hon

**Option C - Pragmatic module (Recommended):**

```
modules/
  vpc/            # VPC + subnets + IGW + route tables (tightly coupled)
  nat-gateway/    # NAT Gateway rieng (vi optional va co chi phi)
  security-groups/ # SG rieng (vi moi app co SG khac nhau)
```

Su dung ranh gioi tu nhien cua infrastructure: nhom nhung resource luon di cung nhau (VPC + subnets luon co nhau), tach nhung resource optional hoac co concern rieng (NAT Gateway optional, SG khac nhau per application).

**So sanh theo context:**

| Context     | Recommendation                    | Ly do                                               |
|-------------|-----------------------------------|-----------------------------------------------------|
| Ca nhan     | Mega module                       | Nhanh, don gian, chi mot nguoi dung                |
| Small team  | Pragmatic module                  | Balance giua simplicity va reusability             |
| Startup     | Pragmatic module                  | Khong over-engineer, scale khi can                 |
| Enterprise  | Fine-grained module               | Nhieu team, can clear ownership, blast radius nho  |
| Bank/Regulated | Fine-grained + strict versioning | Compliance, audit trail, change control rieng biet |

### 2. Local module vs Registry module

**Su dung local module khi:**
- Module specific voi to chuc/use case cua ban (naming conventions rieng, internal standards)
- Dang trong giai doan phat trien, chua stable
- Module can access internal resource (private endpoints)
- Khong muon expose logic ra ngoai

**Su dung Registry module khi:**
- Tan dung battle-tested implementation (terraform-aws-modules co hang nghin contributor va test)
- Tiet kiem thoi gian cho well-understood patterns (VPC networking la solved problem)
- Module khong co company-specific logic

**Trade-off quan trong:**

Registry module nhu `terraform-aws-modules/vpc/aws` rat feature-rich:
- Ho tro >30 input variable
- Edge cases duoc handle
- Tested boi community lon

Nhung:
- Updating version = can hieu breaking changes
- Dependency vao external source (khong co internet = khong init duoc)
- Gia `terraform plan` cham hon vi nhieu resource
- Kho debug vi code phuc tap

**Recommendation:** Dung Registry module cho standard patterns (VPC, EKS, RDS). Viet local module cho business logic va company-specific config. Wrap Registry module vao local module neu can add custom logic.

### 3. Module versioning strategies

**Pattern A - Git tag truc tiep:**
```hcl
source = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.1.0"
```
Uu diem: Fine-grained control, co the pick exact commit
Nhuoc diem: Dai dong, phai quan ly Git tag

**Pattern B - Terraform Registry rieng (Enterprise):**
Dung Terraform Cloud / HCP Terraform private registry. Module duoc publish nhu package, co version semantics.
Uu diem: Giong nhu public registry nhung private, co access control, co UI
Nhuoc diem: Vendor lock-in, chi phi

**Pattern C - Local path trong mono-repo:**
```hcl
source = "./modules/vpc"
```
Uu diem: Don gian, khong can version management, all-in-one repo
Nhuoc diem: Tat ca projects dung cung version (latest), kho rollback tung project rieng le

**Pattern D - Separate module repo + Git tag:**
Module trong repo rieng. Root module tham chieu bang `git::...?ref=vX.Y.Z`.
Uu diem: Module va consumer co vong doi doc lap
Nhuoc diem: Phai maintain 2 repo, CI/CD phuc tap hon

**Recommendation theo org size:**

| Org size | Recommendation                                          |
|----------|---------------------------------------------------------|
| 1-5 dev  | Local path trong mono-repo, don gian nhat              |
| 5-20 dev | Separate module repo + Git tag                          |
| 20+ dev  | Private Terraform Registry (HCP Terraform hoac Atlantis)|

### 4. Common Pitfalls

**Pitfall 1 - Provider trong child module:**
```hcl
# SAI - Khong dat provider configuration trong module
# modules/vpc/main.tf
provider "aws" {     # <-- Khong lam nay
  region = "ap-southeast-1"
}
```

Correct: Provider duoc cau hinh o root module. Neu can dung provider khac (multi-region), dung `provider` argument khi goi module.

**Pitfall 2 - Hardcode gia tri trong module:**
```hcl
# SAI - Hardcode tao ra module khong teo tai su dung
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"  # Hardcoded
  tags = {
    Name = "prod-vpc"          # Hardcoded environment
  }
}
```

Correct: Tat ca gia tri co the vary theo context deu phai la variable.

**Pitfall 3 - Expose qua nhieu output:**
Khong nen output moi attribute cua moi resource. Chi output nhung gi caller thuc su can. Qua nhieu output = leaky abstraction.

**Pitfall 4 - Module khong co description:**
```hcl
# SAI - Thieu description
variable "vpc_cidr" {
  type = string
}

# DUNG
variable "vpc_cidr" {
  description = "CIDR block for the VPC. Phai khong overlap voi other VPCs trong cung region."
  type        = string
}
```

**Pitfall 5 - Doi ten output khi co consumer:**
Doi ten output = breaking change cho tat ca consumer cua module. Neu phai doi, duy tri backward compatibility bang cach keep old output va add new output, sau do deprecate.

---

## Hands-on Lab - 60 phut

### Muc tieu lab

Ket qua Day 5: Ban co S3 backend va DynamoDB. Ket qua Day 6 lab: Ban co mot VPC module duoc tach biet khoi root module, root module goi module do va su dung output cua no.

Cau truc nay se duoc refactor trong Day 7 va reuse trong Day 8 (Multi-Environment).

### Cau truc lab

```
day-06-lab/
├── modules/
│   └── vpc/
│       ├── main.tf          # VPC, subnets, IGW, route tables
│       ├── variables.tf     # Input variables
│       ├── outputs.tf       # Output values
│       └── versions.tf      # Provider requirements
└── root/
    ├── main.tf              # Goi module vpc
    ├── variables.tf
    ├── outputs.tf
    ├── backend.tf           # S3 backend tu Day 5
    └── terraform.tfvars     # Gia tri cho learning environment
```

### Buoc 1 - Setup thu muc

```bash
mkdir -p ~/terraform-day6-lab/modules/vpc
mkdir -p ~/terraform-day6-lab/root

cd ~/terraform-day6-lab
```

### Buoc 2 - Viet VPC module

**File `modules/vpc/versions.tf`:**

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

**File `modules/vpc/variables.tf`:**

```hcl
variable "project_name" {
  description = "Ten project, dung de dat ten resource. Chi chua lowercase letters, numbers, hyphens."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name chi duoc chua lowercase letters, numbers, va hyphens."
  }
}

variable "environment" {
  description = "Ten environment (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phai la mot trong: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block cua VPC. Vi du: 10.0.0.0/16"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR block."
  }
}

variable "availability_zones" {
  description = "Danh sach Availability Zones se deploy subnets vao"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "Danh sach CIDR cho public subnets. So luong phai bang so AZ."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "Danh sach CIDR cho private subnets. So luong phai bang so AZ."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Bat NAT Gateway cho private subnets. NAT Gateway ton khoang $32/thang/AZ."
  type        = bool
  default     = false  # Default false de tiet kiem chi phi trong lab
}

variable "single_nat_gateway" {
  description = "Chi tao mot NAT Gateway thay vi mot per AZ. Tiet kiem chi phi nhung giam HA."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Map cac tag bo sung de apply len tat ca resource"
  type        = map(string)
  default     = {}
}
```

**File `modules/vpc/main.tf`:**

```hcl
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Merge common tags voi custom tags
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "vpc"
    },
    var.tags
  )

  # Neu enable_nat_gateway = false thi chi tao 0 NAT Gateway
  # Neu single_nat_gateway = true thi chi tao 1
  # Neu single_nat_gateway = false thi tao 1 per AZ
  nat_gateway_count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.availability_zones)) : 0
}

# VPC chinh
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# Public Subnets - co the reach internet truc tiep qua IGW
resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true  # Instance trong public subnet se co public IP

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Tier = "public"
  })
}

# Private Subnets - chi truyen qua NAT Gateway
resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Tier = "private"
  })
}

# Internet Gateway - cho phep public subnets reach internet
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# Elastic IP cho NAT Gateway
resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip-${count.index + 1}"
  })

  depends_on = [aws_internet_gateway.main]
}

# NAT Gateway - cho private subnets reach internet (outbound only)
resource "aws_nat_gateway" "main" {
  count = local.nat_gateway_count

  # NAT Gateway phai dat trong public subnet
  subnet_id     = aws_subnet.public[count.index].id
  allocation_id = aws_eip.nat[count.index].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-${count.index + 1}"
  })

  depends_on = [aws_internet_gateway.main]
}

# Route Table cho public subnets - route 0.0.0.0/0 qua IGW
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

# Associate public subnets voi public route table
resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Route Table cho private subnets - route 0.0.0.0/0 qua NAT Gateway
# Tao mot per NAT Gateway (hoac khong tao neu khong co NAT)
resource "aws_route_table" "private" {
  count  = local.nat_gateway_count > 0 ? length(var.private_subnet_cidrs) : 1
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = local.nat_gateway_count > 0 ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.main[0].id : aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt-${count.index + 1}"
  })
}

# Associate private subnets voi private route table
resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = local.nat_gateway_count > 0 ? aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id : aws_route_table.private[0].id
}
```

**File `modules/vpc/outputs.tf`:**

```hcl
output "vpc_id" {
  description = "ID cua VPC duoc tao"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block cua VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "Danh sach ID cua cac public subnet"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Danh sach ID cua cac private subnet"
  value       = aws_subnet.private[*].id
}

output "internet_gateway_id" {
  description = "ID cua Internet Gateway"
  value       = aws_internet_gateway.main.id
}

output "nat_gateway_ids" {
  description = "Danh sach ID cua NAT Gateways (empty neu enable_nat_gateway = false)"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = "Danh sach public IP cua NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

output "public_route_table_id" {
  description = "ID cua public route table"
  value       = aws_route_table.public.id
}

output "private_route_table_ids" {
  description = "Danh sach ID cua private route tables"
  value       = aws_route_table.private[*].id
}

# Convenience output - hay dung khi truyen vao EKS, ECS
output "all_subnet_ids" {
  description = "Danh sach tat ca subnet IDs (public + private)"
  value       = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
}
```

### Buoc 3 - Viet Root Module

**File `root/backend.tf`:**
```hcl
terraform {
  backend "s3" {
    # Thay bang gia tri tu Day 5 lab cua ban
    bucket         = "terraform-state-YOUR_ACCOUNT_ID"
    key            = "day6-lab/root/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

**File `root/versions.tf`:**
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

**File `root/variables.tf`:**
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

variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string
  default     = "10.10.0.0/16"
}
```

**File `root/main.tf`:**
```hcl
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

# Lay available AZs trong region
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  # Lay 2 AZ dau tien
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

# Goi child module vpc
module "vpc" {
  source = "../modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr

  availability_zones   = local.azs
  public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
  private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]

  enable_nat_gateway = false  # False de tiet kiem chi phi trong lab
  single_nat_gateway = true

  tags = {
    Lab = "day6-module-basics"
  }
}
```

**File `root/outputs.tf`:**
```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "availability_zones" {
  description = "AZs duoc su dung"
  value       = local.azs
}
```

**File `root/terraform.tfvars`:**
```hcl
aws_region   = "ap-southeast-1"
project_name = "myapp"
environment  = "dev"
vpc_cidr     = "10.10.0.0/16"
```

### Buoc 4 - Init va Plan

```bash
cd ~/terraform-day6-lab/root

terraform init
```

Expected output:
```
Initializing the backend...

Successfully configured the backend "s3"!

Initializing modules...
- vpc in ../modules/vpc

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...

Terraform has been successfully initialized!
```

Luu y dong: `Initializing modules... - vpc in ../modules/vpc`. Terraform tim thay va load child module.

```bash
terraform plan
```

Expected output (rut gon):
```
Terraform will perform the following actions:

  # module.vpc.aws_internet_gateway.main will be created
  + resource "aws_internet_gateway" "main" {
      + id     = (known after apply)
      + vpc_id = (known after apply)
      ...

  # module.vpc.aws_route_table.public will be created
  # module.vpc.aws_route_table_association.public[0] will be created
  # module.vpc.aws_route_table_association.public[1] will be created
  # module.vpc.aws_subnet.private[0] will be created
  # module.vpc.aws_subnet.private[1] will be created
  # module.vpc.aws_subnet.public[0] will be created
  # module.vpc.aws_subnet.public[1] will be created
  # module.vpc.aws_vpc.main will be created

Plan: 9 to add, 0 to change, 0 to destroy.
```

Luu y naming: tat ca resource co prefix `module.vpc.` - day la module path trong state.

### Buoc 5 - Apply

```bash
terraform apply
```

Confirm bang cach nhap `yes`. Expected output:
```
module.vpc.aws_vpc.main: Creating...
module.vpc.aws_vpc.main: Creation complete after 2s [id=vpc-0abc123...]
module.vpc.aws_internet_gateway.main: Creating...
module.vpc.aws_subnet.public[0]: Creating...
module.vpc.aws_subnet.public[1]: Creating...
module.vpc.aws_subnet.private[0]: Creating...
module.vpc.aws_subnet.private[1]: Creating...
...
Apply complete! Resources: 9 added, 0 changed, 0 destroyed.

Outputs:

availability_zones = [
  "ap-southeast-1a",
  "ap-southeast-1b",
]
private_subnet_ids = [
  "subnet-0abc...",
  "subnet-0def...",
]
public_subnet_ids = [
  "subnet-0ghi...",
  "subnet-0jkl...",
]
vpc_cidr = "10.10.0.0/16"
vpc_id = "vpc-0abc123..."
```

### Buoc 6 - Kiem tra module output trong state

```bash
# Xem output cu the
terraform output vpc_id
terraform output -json public_subnet_ids

# Xem state structure - chu y how module resources duoc to chuc
terraform state list
```

Expected `terraform state list`:
```
data.aws_availability_zones.available
module.vpc.aws_internet_gateway.main
module.vpc.aws_route_table.private[0]
module.vpc.aws_route_table.public
module.vpc.aws_route_table_association.private[0]
module.vpc.aws_route_table_association.private[1]
module.vpc.aws_route_table_association.public[0]
module.vpc.aws_route_table_association.public[1]
module.vpc.aws_subnet.private[0]
module.vpc.aws_subnet.private[1]
module.vpc.aws_subnet.public[0]
module.vpc.aws_subnet.public[1]
module.vpc.aws_vpc.main
```

Tat ca resource cua module deu nam duoi `module.vpc.` trong state.

### Buoc 7 - Goi module lan thu hai (module reuse)

Them vao `root/main.tf`:

```hcl
# Goi cung module voi config khac - tao them mot VPC "staging"
module "vpc_staging" {
  source = "../modules/vpc"

  project_name = var.project_name
  environment  = "staging"
  vpc_cidr     = "10.11.0.0/16"  # CIDR khac de tranh overlap

  availability_zones   = local.azs
  public_subnet_cidrs  = ["10.11.1.0/24", "10.11.2.0/24"]
  private_subnet_cidrs = ["10.11.11.0/24", "10.11.12.0/24"]

  enable_nat_gateway = false
  single_nat_gateway = true

  tags = {
    Lab = "day6-module-basics"
  }
}
```

Them vao `root/outputs.tf`:
```hcl
output "staging_vpc_id" {
  description = "Staging VPC ID"
  value       = module.vpc_staging.vpc_id
}
```

```bash
terraform plan
```

Expected: Plan chi them resource cho staging VPC, khong affect dev VPC da co:
```
Plan: 9 to add, 0 to change, 0 to destroy.
```

```bash
terraform apply
```

Gio ban co 2 VPC duoc tao tu cung mot module source, voi config khac nhau.

### Buoc 8 - Troubleshooting pho bien

**Loi 1: Module source khong tim thay**
```
Error: Module not installed
  on main.tf line 6, in module "vpc":
   6:   source = "../modules/vpc"

This module is not yet installed. Run "terraform init" to install all modules.
```
Fix: `terraform init` khi them module moi hoac thay doi source.

**Loi 2: Missing required variable**
```
Error: Missing required argument
  The argument "vpc_cidr" is required, but no definition was found.
```
Fix: Them variable vao module call. Kiem tra `variables.tf` cua module xem variable nao khong co default.

**Loi 3: Subnet CIDR count mismatch**
```
Error: Invalid value for variable
  private_subnet_cidrs: List must have same length as availability_zones.
```
Day la validation rule cua module. Fix: Dam bao so luong CIDR trong `public_subnet_cidrs` va `private_subnet_cidrs` bang so luong `availability_zones`.

**Loi 4: CIDR overlap**
```
Error: error creating subnet: InvalidSubnet.Conflict
```
Hai subnet co CIDR overlap trong cung VPC. Kiem tra lai cac CIDR block.

### Buoc 9 - Cleanup

```bash
cd ~/terraform-day6-lab/root

# Destroy tat ca resource
terraform destroy

# Xac nhan khi duoc hoi
# Expected: Destroy complete! Resources: 18 destroyed.
```

---

## Kiem tra hieu bai

1. **Khac biet giua root module va child module la gi?** Giai thich lien quan den state, provider configuration, va cach chay Terraform.

2. **Mot module VPC co output `vpc_id` va `subnet_ids`. Root module muon truyen `subnet_ids` vao mot module EKS.** Viet syntax cu the de truyen gia tri nay.

3. **Team ban co 3 engineer. Moi nguoi can deploy VPC vao environment rieng (dev1, dev2, dev3). Ban co 2 lua chon: copy code 3 lan hoac dung module.** Phân tich trade-off cu the cua tung approach, khong chi noi "module tot hon".

4. **Module `terraform-aws-modules/vpc/aws` o version 5.1.0. Ban dang dung constraint `~> 5.0`.** Khi version 5.2.0 ra, Terraform co tu dong upgrade khong? Khi 6.0.0 ra thi sao? Giai thich tai sao behavior nay la dung.

5. **Debug scenario:** `terraform plan` tra ve `No changes` nhung ban vua them resource vao module. Tai sao? Lam the nao de fix?

---

## Tom tat cuoi ngay

### Key points

- **Module = reusable infrastructure component:** Giong nhu function trong programming - co input, logic, output. Khong lam gi moi, chi organize code da biet cach viet
- **Root module goi child module, khong phai nguoc lai:** Data chay mot chieu: root truyen input vao, nhan output ve. Module khong biet ai dang dung no
- **State bao gom ca module path:** `module.vpc.aws_vpc.main` - day giup Terraform quan ly resource tung module doc lap, tranh conflict
- **Output cua module la interface contract:** Doi ten output = breaking change. Design interface can than truoc khi share cho nhieu team dung
- **Module versioning la infrastructure dependency management:** Giong nhu package.json hay go.mod, can quan ly version cua module dependency de co reproducible infra

### Outputs da tao ra

- Thu muc `modules/vpc/` voi day du `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`
- Root module goi vpc module voi 2 instance (dev va staging VPC)
- State tren S3 backend voi module path structure
- Module co the reuse de tao nhieu VPC voi cac config khac nhau

### Chuan bi cho Day 7 - Module Design for Production

Day 7 se refactor VPC module nay theo production standards:
- Them validation phuc tap hon (cross-variable validation)
- Handle multi-AZ NAT Gateway dung chuan
- Add VPC Flow Logs support
- Versioning strategy cho module trong team
- Testing voi Terratest
- Documentation-as-code voi terraform-docs

Truoc khi hoc: Nhin lai module ban vua viet. Nhung gi ban nghi co the lam tot hon? Nhung edge case nao chua duoc xu ly (vi du: AZ count = 1, enable_nat_gateway = true + single_nat_gateway = false thi sao)?

---

## Tham khao them

- [Terraform Modules Documentation](https://developer.hashicorp.com/terraform/language/modules) - Khai niem chinh thuc ve module
- [Terraform Registry](https://registry.terraform.io) - Tim kiem va xem public modules
- [terraform-aws-modules/vpc/aws](https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws) - Module VPC pho bien nhat, nen doc source code de hoc
- [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition) - Official guide ve module composition patterns
- [Module Sources](https://developer.hashicorp.com/terraform/language/modules/sources) - Tat ca loai source duoc ho tro
- [Publishing Modules](https://developer.hashicorp.com/terraform/registry/modules/publish) - Neu muon publish module len public registry
