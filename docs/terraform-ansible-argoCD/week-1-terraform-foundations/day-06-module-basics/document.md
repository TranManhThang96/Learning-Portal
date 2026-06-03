# Day 6 - Reference Document: Terraform Module Basics

---

## 1. Module Structure Reference

### Cau truc file tieu chuan cho mot child module

```
modules/
  <ten-module>/
    main.tf          # Resource definitions (bat buoc)
    variables.tf     # Input variable declarations (bat buoc)
    outputs.tf       # Output value declarations (bat buoc khi co consumer)
    versions.tf      # required_version va required_providers (khuyen nghi)
    README.md        # Interface documentation (khuyen nghi khi share)
```

**Khong dat trong module:**
- `backend.tf` - Module khong quan ly state
- `terraform.tfvars` - Khong co y nghia trong module
- Provider configuration block - Provider thuoc root module

### Cau truc toan bo project su dung module

```
my-project/
  root/                         # Entry point, chay terraform o day
    main.tf                     # Goi child modules, data sources
    variables.tf                # Root-level variables
    outputs.tf                  # Root-level outputs (thuong la re-export tu modules)
    backend.tf                  # Backend config (S3, GCS, etc.)
    terraform.tfvars            # Gia tri bien cho environment nay
    versions.tf                 # required_version va required_providers
  modules/
    vpc/                        # Child module: networking layer
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    security-groups/            # Child module: security layer
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    eks/                        # Child module: compute layer
      main.tf
      variables.tf
      outputs.tf
      versions.tf
```

---

## 2. Module Block Syntax - Day du

```hcl
module "<ten_module>" {
  # BẮT BUỘC: Noi Terraform tim module source
  source = "./modules/vpc"

  # OPTIONAL: Version constraint (chi cho Registry va Git sources)
  version = "~> 5.0"

  # INPUT VARIABLES: Truyen gia tri vao module
  variable_name_1 = "value"
  variable_name_2 = var.some_var
  variable_name_3 = local.some_local

  # PROVIDER OVERRIDE (hiem khi can)
  # Dung khi module can dung provider khac voi default
  providers = {
    aws = aws.us-east-1
  }

  # DEPENDENCY (hiem khi can, thuong Terraform tu detect)
  depends_on = [module.other_module]
}
```

### Truy cap module output

```hcl
module.<ten_module>.<output_name>

# Vi du:
module.vpc.vpc_id
module.vpc.private_subnet_ids
module.security_groups.eks_sg_id
```

---

## 3. Input Variable Patterns

### Pattern 1 - Basic variable voi validation

```hcl
variable "environment" {
  description = "Ten environment. Anh huong den naming, tagging, va mot so config."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phai la mot trong: dev, staging, prod."
  }
}
```

### Pattern 2 - Variable voi default (optional khi goi module)

```hcl
variable "enable_nat_gateway" {
  description = "Bat NAT Gateway. Chi phi ~$32/thang/AZ."
  type        = bool
  default     = false
}
```

### Pattern 3 - Complex type: list

```hcl
variable "availability_zones" {
  description = "Danh sach AZ de deploy subnets"
  type        = list(string)
  # Khong co default = bat buoc khi goi module
}
```

### Pattern 4 - Complex type: map/object

```hcl
variable "tags" {
  description = "Map tag bo sung, se duoc merge voi common tags"
  type        = map(string)
  default     = {}
}

# Object voi ty rang ke nghia
variable "nat_gateway_config" {
  description = "Cau hinh NAT Gateway"
  type = object({
    enabled = bool
    single  = bool   # true = one per region, false = one per AZ
  })
  default = {
    enabled = false
    single  = true
  }
}
```

### Pattern 5 - CIDR validation

```hcl
variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR (vi du: 10.0.0.0/16)."
  }
}
```

### Pattern 6 - Regex validation

```hcl
variable "project_name" {
  description = "Ten project, dung lam prefix cho tat ca resource"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name phai tư 2-20 ky tu, chi chua lowercase, so, va hyphen."
  }
}
```

---

## 4. Output Value Patterns

### Pattern 1 - Basic output

```hcl
output "vpc_id" {
  description = "ID cua VPC duoc tao ra boi module nay"
  value       = aws_vpc.main.id
}
```

### Pattern 2 - Output list/tuple

```hcl
output "private_subnet_ids" {
  description = "Danh sach ID cua cac private subnet, theo thu tu AZ"
  value       = aws_subnet.private[*].id
}

# Voi for expression
output "subnet_id_by_az" {
  description = "Map tu AZ sang subnet ID"
  value = {
    for subnet in aws_subnet.private :
    subnet.availability_zone => subnet.id
  }
}
```

### Pattern 3 - Sensitive output

```hcl
output "db_password" {
  description = "Database password (sensitive)"
  value       = random_password.db.result
  sensitive   = true  # Khong hien thi trong terminal, van co trong state
}
```

### Pattern 4 - Conditional output

```hcl
output "nat_gateway_ips" {
  description = "Public IPs cua NAT Gateways (empty list neu disable)"
  value       = aws_eip.nat[*].public_ip
  # Neu khong co NAT Gateway (count = 0), tra ve empty list []
}
```

### Pattern 5 - Re-export tu submodule (module composition)

```hcl
# Trong mot "wrapper" module, re-export output tu child module
output "vpc_id" {
  description = "VPC ID (re-exported tu networking module)"
  value       = module.networking.vpc_id
}
```

---

## 5. Module Sources - Quick Reference

| Source type          | Syntax                                                           | Khi nao dung                            |
|----------------------|------------------------------------------------------------------|-----------------------------------------|
| Local path           | `"./modules/vpc"`                                               | Mono-repo, development                  |
| Local path (up)      | `"../shared-modules/vpc"`                                       | Shared modules trong cung repo          |
| Terraform Registry   | `"terraform-aws-modules/vpc/aws"`                               | Community/official modules              |
| GitHub (public)      | `"github.com/org/repo//module-path?ref=v1.0.0"`                 | Public GitHub repo                      |
| GitHub (private)     | `"git::https://github.com/org/repo.git//path?ref=v1.0.0"`      | Private GitHub, SSH key configured      |
| S3                   | `"s3::https://s3.amazonaws.com/bucket/module.zip"`             | Private enterprise module registry      |
| GCS                  | `"gcs::https://storage.googleapis.com/bucket/module.zip"`      | Private enterprise module registry      |

**Luu y `//` trong Git URL:** Double slash phan cach repository root va sub-directory cua module. `github.com/org/repo//vpc` = thu muc `vpc` trong repo `org/repo`.

---

## 6. Module Versioning - Best Practices

### Version constraint syntax

| Constraint    | Y nghia                                              | Vi du ap dung                         |
|---------------|------------------------------------------------------|---------------------------------------|
| `= 5.5.2`     | Exact version, khong co gi khac                      | Production, audit requirement         |
| `~> 5.5`      | >= 5.5.0, < 5.6.0 (patch only)                      | Staging, nhan security patches        |
| `~> 5.0`      | >= 5.0.0, < 6.0.0 (minor OK, no major)              | Dev environment                       |
| `>= 5.0`      | Bat ky version tu 5.0 tro len                        | Learning only, khong production       |
| `>= 5.0, < 6` | Range cu the                                         | Khi muon explicit ve upper bound      |

### Versioning strategy theo environment

```hcl
# modules/vpc/version.tf (trong separate module repo)
# Sau khi release, tag: git tag -a v2.3.1 -m "Add Flow Logs support"

# Root module cho dev environment
module "vpc" {
  source  = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.3.1"
  # hoac local path trong mono-repo (khong can version)
}

# Root module cho staging
module "vpc" {
  source  = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.3.1"
  # staging va prod dung cung version sau khi test xong
}

# Root module cho prod
module "vpc" {
  source  = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.3.1"
  # production luon dung exact version
}
```

### Semantic Versioning cho module

Theo SemVer (`MAJOR.MINOR.PATCH`):
- **PATCH** (2.3.0 -> 2.3.1): Bug fix, khong thay doi interface. `~> 2.3` se nhan.
- **MINOR** (2.3.x -> 2.4.0): Them feature moi, backward compatible. `~> 2.0` se nhan.
- **MAJOR** (2.x -> 3.0.0): Breaking changes. Phai update consumer thu cong.

Breaking changes trong module:
- Doi ten/xoa input variable (khong co default)
- Doi ten/xoa output value
- Thay doi kieu cua variable
- Thay doi resource address (se trigger destroy + recreate)

---

## 7. Module Registry Usage Guide

### Tim kiem module tren registry.terraform.io

```
URL: registry.terraform.io
Tim theo: provider (aws, gcp, azure) + functionality (vpc, eks, rds)

Module ID format: <namespace>/<module-name>/<provider>
Vi du: terraform-aws-modules/vpc/aws
       terraform-aws-modules/eks/aws
       cloudposse/label/null
```

### Dung module tu Registry

```hcl
module "vpc" {
  # Format: namespace/name/provider
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # Mac dinh la required inputs + mot so optional
  name = "my-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Environment = "dev"
    Terraform   = "true"
  }
}
```

### Sau khi them Registry module, bat buoc chay:

```bash
terraform init
# Terraform se download module xuong .terraform/modules/
```

### Wrapper pattern - Wrap Registry module

Dung khi muon enforce company standards tren top cua Registry module:

```hcl
# modules/vpc/main.tf (local module)
module "vpc_upstream" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # Cac argument bat buoc tu caller
  name = "${var.project_name}-${var.environment}-vpc"
  cidr = var.vpc_cidr
  azs  = var.availability_zones

  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  # Company standard: enforce di cung module, caller khong override duoc
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Common tags luon duoc apply
  tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# Re-export nhung output can thiet
output "vpc_id" {
  value = module.vpc_upstream.vpc_id
}
```

---

## 8. locals trong Module - Pattern Reference

```hcl
locals {
  # Naming convention tap trung
  name_prefix = "${var.project_name}-${var.environment}"

  # Tag merge pattern
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.tags  # Caller co the add them tags
  )

  # Conditional count
  nat_count = var.enable_nat_gateway ? (
    var.single_nat_gateway ? 1 : length(var.availability_zones)
  ) : 0

  # Derived value tu input
  # Do NOT recompute logic nhieu noi - dat vao local
  private_subnet_count = length(var.private_subnet_cidrs)
}
```

---

## 9. terraform state list - Module trong State

Sau khi apply project co module, state structure:

```bash
terraform state list

# Output vi du:
data.aws_availability_zones.available          # Root module data source
module.vpc.aws_vpc.main                        # Resource trong vpc module
module.vpc.aws_internet_gateway.main
module.vpc.aws_subnet.public[0]
module.vpc.aws_subnet.public[1]
module.vpc.aws_subnet.private[0]
module.vpc.aws_subnet.private[1]
module.vpc.aws_route_table.public
module.vpc.aws_route_table_association.public[0]
module.vpc.aws_route_table_association.public[1]

# Nested module (module goi module)
module.eks.module.node_groups.aws_autoscaling_group.workers[0]
```

**Cac lenh state huu ich voi module:**

```bash
# Xem state cua mot module cu the
terraform state show module.vpc.aws_vpc.main

# Xoa resource khoi state (khong destroy)
terraform state rm module.vpc.aws_subnet.private[0]

# Move resource giua modules (khi refactor)
terraform state mv module.vpc.aws_vpc.main module.networking.aws_vpc.main

# Import resource vao module
terraform import module.vpc.aws_vpc.main vpc-0abc123def
```

---

## 10. module-specific Terraform commands

```bash
# Init (BẮT BUỘC sau khi them module moi hoac thay doi source)
terraform init

# Init va upgrade module versions
terraform init -upgrade

# Plan chi mot module cu the
terraform plan -target=module.vpc

# Apply chi mot module (dung can than - co the tao dependency issues)
terraform apply -target=module.vpc

# Destroy chi mot module
terraform destroy -target=module.vpc

# Xem output cu the cua module (qua root output)
terraform output vpc_id
terraform output -json private_subnet_ids

# Graph dependency goi duoc module relationships
terraform graph | dot -Tpng > graph.png
```

---

## 11. Common Terraform Module Patterns

### Pattern: Environment selection qua variable

```hcl
# Thay vi viet code khac nhau cho moi environment,
# truyen environment vao module va module tu xu ly

module "vpc" {
  source = "./modules/vpc"

  environment = var.environment

  # Module noi se dung var.environment de quyet dinh:
  # - Size cua instance
  # - So luong AZ
  # - Bat/tat NAT Gateway
  # - Tags khac nhau
}
```

### Pattern: Feature flags

```hcl
module "vpc" {
  source = "./modules/vpc"

  # Feature flags ro rang hon la conditional logic phuc tap trong module
  enable_nat_gateway  = var.environment == "prod"
  enable_flow_logs    = true
  enable_vpn_gateway  = false
}
```

### Pattern: Data-driven configuration

```hcl
# variables.tf
variable "vpc_config" {
  type = object({
    cidr                 = string
    enable_nat_gateway   = bool
    private_subnet_cidrs = list(string)
    public_subnet_cidrs  = list(string)
  })
}

# terraform.tfvars
vpc_config = {
  cidr               = "10.0.0.0/16"
  enable_nat_gateway = true
  private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]
}
```

### Pattern: Module cho moi environment trong cung workspace

```hcl
# Khong khuyen nghi cho prod - nen dung separate state
# Nhung huu ich cho dev/test environment nhanh

locals {
  environments = {
    dev = {
      cidr               = "10.10.0.0/16"
      enable_nat_gateway = false
    }
    staging = {
      cidr               = "10.11.0.0/16"
      enable_nat_gateway = true
    }
  }
}

module "vpc" {
  for_each = local.environments
  source   = "./modules/vpc"

  environment        = each.key
  vpc_cidr           = each.value.cidr
  enable_nat_gateway = each.value.enable_nat_gateway
  # ...
}
```

---

## 12. Module interface documentation template

Du kien gan them trong `modules/vpc/README.md` hoac viet comment trong `variables.tf`:

```markdown
## Module: vpc

Tao VPC co ban voi public va private subnets.

### Usage

```hcl
module "vpc" {
  source = "./modules/vpc"

  project_name         = "myapp"
  environment          = "prod"
  vpc_cidr             = "10.0.0.0/16"
  availability_zones   = ["ap-southeast-1a", "ap-southeast-1b"]
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]
  enable_nat_gateway   = true
  single_nat_gateway   = false  # One per AZ for HA
}
```

### Inputs

| Name | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| project_name | string | - | Yes | Ten project |
| environment | string | - | Yes | dev/staging/prod |
| vpc_cidr | string | - | Yes | CIDR block cho VPC |
| availability_zones | list(string) | - | Yes | Danh sach AZ |
| public_subnet_cidrs | list(string) | - | Yes | CIDRs cho public subnets |
| private_subnet_cidrs | list(string) | - | Yes | CIDRs cho private subnets |
| enable_nat_gateway | bool | false | No | Bat NAT Gateway |
| single_nat_gateway | bool | true | No | Chi tao 1 NAT Gateway |
| tags | map(string) | {} | No | Tags bo sung |

### Outputs

| Name | Description |
|------|-------------|
| vpc_id | ID cua VPC |
| public_subnet_ids | List ID public subnets |
| private_subnet_ids | List ID private subnets |
| nat_gateway_ids | List ID NAT Gateways |
```
