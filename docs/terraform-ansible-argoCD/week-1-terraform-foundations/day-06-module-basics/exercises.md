# Day 6 - Extra Exercises: Terraform Module Basics

---

## Challenge 1: Module Validation Nang cao

**Context:** Ban la platform engineer. VPC module cua ban se duoc dung boi 10 service team khac nhau. Module can phat hien sai ngay tu `terraform plan`, khong phai sau khi infrastructure da duoc tao.

**Task:** Them validation rules vao `modules/vpc/variables.tf` de:

1. Dam bao `vpc_cidr` la private range (10.x, 172.16-31.x, 192.168.x)
2. Dam bao so luong `public_subnet_cidrs` bang so luong `availability_zones` (validation cross-variable hieu khi tu `variable` block, can dung `locals` va variable block tach biet)
3. Dam bao moi subnet CIDR nam trong `vpc_cidr`
4. Dam bao prefix cua subnet is /24 hoac nho hon (khong tao subnet /8 hay /16 - qua lon)

**Validation co the dung:**
```hcl
# Check private range
condition = can(regex("^(10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.)", var.vpc_cidr))

# Check subnet la /24 hoac nho hon
condition = tonumber(split("/", var.public_subnet_cidrs[0])[1]) >= 24
```

**Expected behavior:**
```bash
# Phai fail voi error ro rang:
terraform plan  # khi vpc_cidr = "8.8.0.0/16" (public range)
terraform plan  # khi public_subnet_cidrs co 3 phan tu nhung azs co 2
```

---

## Challenge 2: Multi-Region Module

**Context:** Cong ty ban expand sang Singapore va Tokyo. Platform team yeu cau: cung mot VPC module, deploy duoc sang nhieu region.

**Task:** Thay doi root module de deploy VPC vao 2 region AP:

1. Them 2 AWS provider instances: `aws.singapore` (ap-southeast-1) va `aws.tokyo` (ap-northeast-1)
2. Them variable `regions` la `map(object(...))` chua config per region
3. Goi module VPC 2 lan, moi lan voi provider khac nhau
4. Output tat ca VPC IDs tu ca 2 region

**Goi y - Provider alias:**
```hcl
# main.tf - root module
provider "aws" {
  alias  = "singapore"
  region = "ap-southeast-1"
}

provider "aws" {
  alias  = "tokyo"
  region = "ap-northeast-1"
}

module "vpc_singapore" {
  source = "./modules/vpc"

  providers = {
    aws = aws.singapore
  }
  # ... other variables
}
```

**Luu y:** Module `modules/vpc/main.tf` can khai bao provider requirement:
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
      configuration_aliases = [aws]  # Cho phep caller truyen provider
    }
  }
}
```

**Expected output:**
```
singapore_vpc_id = "vpc-0abc..."
tokyo_vpc_id     = "vpc-0def..."
```

---

## Challenge 3: Module Composition - Three Layers

**Context:** Platform team yeu cau mot stack day du gom: networking layer, security layer, va application layer. Moi layer la mot module rieng. Layer sau phu thuoc vao output cua layer truoc.

**Task:** Tao 3 module va ket noi chung:

**Module 1: `modules/vpc`** (da co tu lab chinh)

**Module 2: `modules/security-groups`**
- Input: `vpc_id`, `environment`, `project_name`, `allowed_ingress_cidrs`
- Tao: `aws_security_group` cho: bastion, application, database
- Output: `bastion_sg_id`, `app_sg_id`, `db_sg_id`

```hcl
# Goi y cho security-groups module
resource "aws_security_group" "app" {
  name        = "${var.project_name}-${var.environment}-app-sg"
  description = "Security group cho application tier"
  vpc_id      = var.vpc_id   # <-- Input tu module caller

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.bastion.id]  # Chi cho phep tu bastion
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-app-sg"
  }
}
```

**Module 3: `modules/ssm-params`** (no-cost, de test composition)
- Input: `environment`, `project_name`, `vpc_id`, `private_subnet_ids`, `app_sg_id`
- Tao: SSM parameters luu thong tin infrastructure (thay cho real application)
- Output: `parameter_arns`

**Root module** ket noi 3 module nay voi chain:
```
modules/vpc          modules/security-groups      modules/ssm-params
    │                        │                           │
    ├── vpc_id ─────────────►│                           │
    ├── private_subnet_ids ──────────────────────────────►│
    │                        ├── app_sg_id ──────────────►│
    └── vpc_id ───────────────────────────────────────────►│
```

---

## Challenge 4: Debug Scenario - State Address Conflict

**Context:** Ban nhan duoc ticket: "Sau khi refactor, tat ca subnet bi destroy va recreate. Downtime 20 phut."

**Setup (tao situation de debug):**

Step 1: Tao VPC voi module path nhu sau:
```hcl
# main.tf ban dau
module "networking" {
  source = "./modules/vpc"
  # ...
}
```

Step 2: Rename module (chi doi ten, khong doi logic):
```hcl
# main.tf sau khi refactor
module "vpc" {          # Doi tu "networking" sang "vpc"
  source = "./modules/vpc"
  # ...
}
```

Step 3: Chay `terraform plan` va doc output.

**Task:**

1. Giai thich tai sao Terraform muon destroy va recreate tat ca resource
2. Tim lenh Terraform de fix problem nay MA KHONG destroy va recreate bat ky resource nao
3. Viet script bash chay tat ca state mv commands can thiet (assume module co VPC, 2 public subnet, 2 private subnet, IGW, route tables)
4. Sau khi apply fix, `terraform plan` phai ra `No changes`

**Goi y:**
```bash
# terraform state mv tu address cu sang address moi
terraform state mv \
  module.networking.aws_vpc.main \
  module.vpc.aws_vpc.main
```

---

## Challenge 5: Module Version Upgrade

**Context:** Team ban dang dung `terraform-aws-modules/vpc/aws` version `4.0.0`. Security team yeu cau upgrade len `5.x` vi co security fix quan trong. Ban phai upgrade ma khong gay downtime.

**Task (simulation voi local module):**

1. Tao module `modules/vpc-v1` voi cau truc don gian:
   - Tao VPC voi CIDR
   - Output: `vpc_id`, `vpc_cidr`

2. Apply voi `module "vpc" { source = "./modules/vpc-v1" ... }`

3. Tao module `modules/vpc-v2` voi thay doi:
   - Them `enable_dns_hostnames = true` (non-breaking)
   - Doi ten output `vpc_cidr` thanh `cidr_block` (BREAKING)

4. Thu upgrade: thay source sang `./modules/vpc-v2`, chay plan

5. **Khong dung rename output trong module.** Thay vao do, implement backward compatibility:
   - Giu output `vpc_cidr` cu (mark la deprecated)
   - Them output `cidr_block` moi
   - Dung `planfile` de verify khong co destroy

**Ket qua mong doi:**
- `terraform plan` ra `1 to add, 1 to change, 0 to destroy` (chi them output moi, update resource co san)
- Ca `module.vpc.vpc_cidr` va `module.vpc.cidr_block` deu hoat dong

---

## Challenge 6: Design Review

**Scenario:** Junior teammate viet module VPC sau day. Ban duoc yeu cau review truoc khi merge vao main branch. Tim tat ca van de va giai thich tai sao moi van de la van de.

```hcl
# modules/vpc/main.tf - CODE CAN REVIEW

provider "aws" {
  region = "us-east-1"
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/8"

  tags = {
    Name = "production-vpc"
  }
}

resource "aws_subnet" "subnet1" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.0.0/24"
}

resource "aws_subnet" "subnet2" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}

output "vpc" {
  value = aws_vpc.main
}
```

```hcl
# modules/vpc/variables.tf
variable "region" {
  default = "us-east-1"
}
```

**Task:** Liet ke it nhat 8 van de, moi van de ghi ro:
- Van de la gi
- Tai sao no la van de (consequence la gi)
- Cach fix cu the

**Danh sach van de de check (truoc khi xem):**
1. Provider trong module
2. Hardcoded CIDR
3. Hardcoded region trong variable
4. Hardcoded environment-specific name
5. Qua rong CIDR /8
6. Thieu description tren variable
7. Output toan bo object thay vi fields cu the
8. Thieu tags chuan
9. Khong co `versions.tf`
10. Thieu `description` tren resource

---

## Challenge 7: Registry Module Investigation

**Context:** Truoc khi viet module tu dau, engineer gioi biet nen kiem tra xem da co module nao kha dung tren Registry.

**Task - Research va su dung Registry module:**

1. Vao `registry.terraform.io`, tim module `terraform-aws-modules/vpc/aws`

2. Doc documentation va tim hieu:
   - Module nay ho tro bao nhieu loai subnet? (public, private, database, elasticache, intra...)
   - Input variable nao de bat VPC Flow Logs?
   - Input variable nao cho EKS-specific subnet tagging (quan trong cho EKS cluster)?

3. Viet mot module call su dung `terraform-aws-modules/vpc/aws` voi:
   - Version constraint `~> 5.0`
   - Private va public subnets
   - EKS tags cho private subnets: `kubernetes.io/role/internal-elb = 1`
   - EKS tags cho public subnets: `kubernetes.io/role/elb = 1`
   - Single NAT Gateway
   - Version pinned sau khi test (doi sang exact version)

4. So sanh: Module nay co bao nhieu input variable so voi module ban tu viet? Comment ve trade-off.

**Expected code:**
```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.project_name}-${var.environment}"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway     = true
  single_nat_gateway     = true
  enable_dns_hostnames   = true

  # EKS-specific tags - can thiet de EKS biet dung subnet nao
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

---

## Challenge 8: for_each voi Module

**Context:** Cong ty co 5 team, moi team can mot VPC rieng trong dev environment. Viet code lap di lap lai 5 lan la anti-pattern.

**Task:** Dung `for_each` de tao nhieu module instance tu mot config map.

```hcl
# variables.tf
variable "team_vpcs" {
  description = "Map config VPC cho moi team"
  type = map(object({
    cidr                 = string
    public_subnet_cidrs  = list(string)
    private_subnet_cidrs = list(string)
  }))

  default = {
    auth-team = {
      cidr                 = "10.10.0.0/16"
      public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
      private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]
    }
    payment-team = {
      cidr                 = "10.11.0.0/16"
      public_subnet_cidrs  = ["10.11.1.0/24", "10.11.2.0/24"]
      private_subnet_cidrs = ["10.11.11.0/24", "10.11.12.0/24"]
    }
    notification-team = {
      cidr                 = "10.12.0.0/16"
      public_subnet_cidrs  = ["10.12.1.0/24", "10.12.2.0/24"]
      private_subnet_cidrs = ["10.12.11.0/24", "10.12.12.0/24"]
    }
  }
}
```

**Task:**

1. Viet `module "team_vpc"` su dung `for_each = var.team_vpcs`
2. Viet output `team_vpc_ids` la `map(string)` - key la team name, value la VPC ID
3. Viet output `all_vpc_cidrs` la `list(string)` - tat ca CIDR cua tat ca team

**Goi y:**
```hcl
# module voi for_each
module "team_vpc" {
  for_each = var.team_vpcs
  source   = "./modules/vpc"

  project_name         = each.key              # "auth-team", "payment-team", ...
  environment          = "dev"
  vpc_cidr             = each.value.cidr
  # ...
}

# Output: truy cap module voi for_each
output "team_vpc_ids" {
  value = {
    for team, mod in module.team_vpc :
    team => mod.vpc_id
  }
}
```

4. Chay `terraform state list` va giai thich format cua module address khi dung `for_each`.

**Expected state format:**
```
module.team_vpc["auth-team"].aws_vpc.main
module.team_vpc["payment-team"].aws_vpc.main
module.team_vpc["notification-team"].aws_vpc.main
```

---

## Loi giai va Huong dan su dung exercises

Cac challenge duoc sap xep theo do phuc tap tang dan. Khuyen nghi:

- **Challenge 1, 6, 7:** Lam sau khi hoan thanh lab chinh. Khong can tao real AWS resource.
- **Challenge 2, 3:** Lam trong ngay de consolidate kien thuc. Can AWS credentials.
- **Challenge 4, 5:** Lam truoc Day 7 - truc tiep lien quan den noi dung refactoring.
- **Challenge 8:** Lam truoc Day 8 (Multi-Environment) - `for_each` se duoc dung nhieu.

**Cac khoi niem quan trong can nam vung truoc Day 7:**
- Module address trong state (`module.<name>.<resource>`)
- `terraform state mv` de rename ma khong destroy
- Backward-compatible vs breaking output changes
- `for_each` voi module
