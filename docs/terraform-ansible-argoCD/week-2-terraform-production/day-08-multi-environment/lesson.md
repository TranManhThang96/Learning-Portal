# Day 8: Multi-Environment Strategy

**Thoi gian:** 2 gio | **Level:** Intermediate | **Prerequisites:** Day 6-7 (VPC Module)

---

## Muc tieu ngay hoc

Sau buoi hoc nay, ban co the:

1. Thiet ke folder structure cho multi-environment Terraform project, giai thich ro ly do chon cau truc do thay vi cac alternative
2. Mo ta su khac biet giua folder-based isolation va workspace-based isolation, neu dung cho dung truong hop
3. Ap dung tfvars layering de quan ly config khac nhau giua dev, staging, production tu cung mot codebase
4. Tao 2 environment doc lap (dev va staging) dung chung VPC module tu Day 6-7, voi config rieng biet, state rieng biet
5. Phan tich trade-off cua workspace vs folder, mono-repo vs multi-repo, shared module vs duplicated code - va dua ra quyet dinh cho context cu the

---

## Boi canh thuc te

### Van de khi khong co multi-environment strategy

**Incident 1 - "Deploy len prod nham" (nguyen nhan so 1 sau human error):**

Startup co 4 developer. Terraform code luu trong mot thu muc duy nhat. Ca team dung chung `terraform.tfvars`. Mot buoi chieu, developer A muon test thay doi sizing cho dev. Ho sua `instance_type = "t3.medium"` thanh `"t3.xlarge"` trong tfvars, chay `terraform apply`. Khong ai nhan ra rang file `terraform.tfstate` dang tro vao production backend. Ket qua: production instances bi recreate, downtime 15 phut, rollback mat them 20 phut.

Van de goc re: Khong co ranh gioi vat ly giua environments. Khong co mechanism nao ngan mot mistake nho thanh production incident.

**Incident 2 - Config drift tich luy theo thoi gian:**

Team co dev va prod. Developer test feature tren dev, them mot security group rule. Feature len prod, nhung ai do quen copy security group change. Sau 3 thang, security audit phat hien 7 diem khac biet giua dev va prod config. Khong ai nho tai sao chung khac nhau. Fix mat 2 ngay de trace lai history.

Van de goc re: Khong co single source of truth. Khi dev va prod duoc quan ly rieng biet bang tay, drift la tat yeu theo thoi gian.

**Incident 3 - Staging khong phan anh dung prod:**

Team co staging rieng. Nhung staging dung CIDR `10.0.0.0/16`, prod dung `172.16.0.0/16`. Staging co 1 AZ, prod co 3 AZ. Staging khong co NAT Gateway, prod co. Mot microservice deploy len staging thanh cong. Len prod: loi networking vi config khac nhau qua lon. Staging tro nen gia tri vi no khong thuc su test production-like config.

Van de goc re: "Staging" ten thi goi la staging, nhung config thi khong giong prod. Dung cung module voi cung parameter structure, chi khac gia tri, la cach duy nhat dam bao staging phan anh prod.

### Dieu gi tao nen mot multi-environment strategy tot?

Ba thuoc tinh can co:

1. **Isolation:** Loi o dev khong the anh huong den prod. State files rieng biet. Credentials rieng biet neu co the.
2. **Consistency:** Cung module, cung logic. Chi config values la khac nhau. Khi ban fix bug trong module, fix do duoc apply cho tat ca environment.
3. **Traceability:** Nhin vao code co the biet environment nay dang co config gi. Khong phai doan, khong phai check AWS console.

---

## Kien thuc nen tang - 30 phut

### 1. Folder-based environment structure

Day la approach pho bien nhat va duoc khuyen nghi cho hau het team: moi environment la mot thu muc rieng, voi state rieng biet.

```
projects/myapp/
  modules/                        <- Shared modules (VPC, EKS, RDS...)
    vpc/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    rds/
      ...
  environments/                   <- Moi env la mot thu muc doc lap
    dev/
      main.tf                     <- Goi module voi dev config
      variables.tf
      outputs.tf
      backend.tf                  <- State key: environments/dev/terraform.tfstate
      terraform.tfvars            <- Dev-specific values
      versions.tf
    staging/
      main.tf                     <- Cung module, cung structure
      variables.tf
      outputs.tf
      backend.tf                  <- State key: environments/staging/terraform.tfstate
      terraform.tfvars            <- Staging-specific values
      versions.tf
    prod/
      main.tf
      variables.tf
      outputs.tf
      backend.tf                  <- State key: environments/prod/terraform.tfstate
      terraform.tfvars
      versions.tf
```

**Cach chay:**

```bash
# De lam viec voi dev
cd environments/dev
terraform init
terraform plan
terraform apply

# De lam viec voi staging
cd environments/staging
terraform init
terraform plan
terraform apply
```

Moi thu muc environments la mot Terraform root module doc lap. State hoan toan rieng biet. Minh bach tuyet doi: dung sai thu muc = sai env - ban biet ngay.

### 2. Terraform Workspace

Workspace la built-in feature cua Terraform de quan ly nhieu state files tu cung mot thu muc code.

```bash
# Liet ke tat ca workspaces (luon co "default")
terraform workspace list

# Tao workspace moi
terraform workspace new dev
terraform workspace new staging
terraform workspace new prod

# Switch sang workspace cu the
terraform workspace select prod

# Xem workspace dang dung
terraform workspace show
```

Moi workspace co state file rieng. Khi dung S3 backend, state duoc luu tai:
- `default`: `s3://bucket/key` (vi du `terraform.tfstate`)
- `dev`: `s3://bucket/env:/dev/key`
- `staging`: `s3://bucket/env:/staging/key`

Su dung workspace trong code:

```hcl
locals {
  # terraform.workspace tra ve ten workspace hien tai
  environment = terraform.workspace

  # Config khac nhau theo workspace
  vpc_cidr = {
    default = "10.10.0.0/16"
    dev     = "10.10.0.0/16"
    staging = "10.11.0.0/16"
    prod    = "10.0.0.0/16"
  }[terraform.workspace]

  # Boolean feature flag
  enable_nat_gateway = terraform.workspace == "prod" ? true : false
}

module "vpc" {
  source = "../../modules/vpc"

  vpc_cidr           = local.vpc_cidr
  enable_nat_gateway = local.enable_nat_gateway
  environment        = local.environment
  # ...
}
```

Workspace co mot van de lon: **khong co indicator ro rang ban dang o workspace nao khi dung CLI.** Chuyen sang prod roi quen switch lai la risk thuc te. Se noi ky o phan trade-off.

### 3. tfvars Layering

tfvars layering la ky thuat dung nhieu file `.tfvars` de to chuc config theo layer, tu chung nhat den rieng nhat. Day la cach tiep can duoc dung nhieu trong folder-based approach.

**Layer 1 - Common defaults (`common.tfvars`):**
```hcl
# Gia tri chung cho tat ca environment
project_name = "myapp"
aws_region   = "ap-southeast-1"

tags = {
  ManagedBy   = "terraform"
  Owner       = "platform-team"
  CostCenter  = "engineering"
}
```

**Layer 2 - Environment-specific (`dev.tfvars`, `staging.tfvars`, `prod.tfvars`):**
```hcl
# dev.tfvars
environment        = "dev"
vpc_cidr           = "10.10.0.0/16"
enable_nat_gateway = false
instance_type      = "t3.micro"

# Staging.tfvars
environment        = "staging"
vpc_cidr           = "10.11.0.0/16"
enable_nat_gateway = true
instance_type      = "t3.small"
```

**Apply voi nhieu tfvars file:**
```bash
# Gia tri tu cac file duoc merge theo thu tu, file sau ghi de file truoc
terraform plan \
  -var-file="../../common.tfvars" \
  -var-file="staging.tfvars"

terraform apply \
  -var-file="../../common.tfvars" \
  -var-file="staging.tfvars"
```

**Luu y quan trong:** Khi co conflict (cung key xuat hien trong ca hai file), file duoc truyen sau se thang. Day la behavior duoc document trong Terraform. Su dung dieu nay co y: common.tfvars dat defaults, environment tfvars override chi nhung gi khac nhau.

**Auto-loaded tfvars:** Terraform tu dong load `terraform.tfvars` va bat ky file nao match `*.auto.tfvars`. Day la ly do trong folder-based approach hay dat file `terraform.tfvars` truc tiep trong moi environment folder - no duoc load tu dong, khong can `-var-file` flag.

### 4. Terragrunt Overview

Terragrunt la mot thin wrapper around Terraform, viet bang Go, duoc phat trien boi Gruntwork. No khong phai la tool chinh thuc cua HashiCorp.

**Van de Terragrunt giai quyet:**

**Van de 1: Backend configuration duplication.** Trong folder-based approach voi 3 environments, ban co 3 file `backend.tf` voi noi dung gan giong nhau, chi khac `key`:

```hcl
# dev/backend.tf
terraform {
  backend "s3" {
    bucket         = "myapp-terraform-state"
    key            = "environments/dev/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

# staging/backend.tf - gan y het, chi khac key
terraform {
  backend "s3" {
    bucket         = "myapp-terraform-state"
    key            = "environments/staging/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

Voi 10 environments va 20 modules, day la 200 file backend.tf co noi dung gan giong nhau.

**Van de 2: Provider version duplication.** Tuong tu voi `versions.tf`.

**Van de 3: Kho dep dependency giua modules trong cung environment.** Neu EKS module can output tu VPC module trong cung environment, ban phai doc state cua VPC bang `terraform_remote_state` data source - verbose va fragile.

**Terragrunt giai quyet bang `terragrunt.hcl`:**

```hcl
# terragrunt.hcl o root cua project
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "myapp-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

```hcl
# environments/dev/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()  # Tim va ke thua root terragrunt.hcl
}

terraform {
  source = "../../../modules/vpc"
}

inputs = {
  project_name = "myapp"
  environment  = "dev"
  vpc_cidr     = "10.10.0.0/16"
  # ...
}
```

**Terragrunt co nen dung khong?** Khi va chi khi:
- Ban co 5+ environments HOAC 10+ modules
- Team da master vanilla Terraform truoc
- Bo sung complexity co the accept duoc

Dung ngay lap tuc se mat di co hoi hieu Terraform hoat dong nhu the nao. Ngay hom nay, hoc vanilla.

### 5. Folder structure diagram

```
myapp-infrastructure/           <- Git repository root
  modules/                      <- Shared module library
    vpc/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    rds/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
    eks/
      main.tf
      variables.tf
      outputs.tf
      versions.tf
  environments/
    dev/
      main.tf                   <- Goi modules/vpc, modules/rds voi dev config
      variables.tf
      outputs.tf
      backend.tf                <- key = "environments/dev/terraform.tfstate"
      terraform.tfvars          <- Dev values: vpc_cidr, instance sizes, etc.
      versions.tf
    staging/
      main.tf                   <- Y het dev/main.tf ve structure, khac ve values
      variables.tf
      outputs.tf
      backend.tf                <- key = "environments/staging/terraform.tfstate"
      terraform.tfvars          <- Staging values
      versions.tf
    prod/
      main.tf
      variables.tf
      outputs.tf
      backend.tf                <- key = "environments/prod/terraform.tfstate"
      terraform.tfvars          <- Prod values (reviewed, approved)
      versions.tf
  common.tfvars                 <- Shared values: project_name, tags, region
  .terraform-version            <- Pinned Terraform version (dung voi tfenv)
  .gitignore
```

---

## Deep Dive & Trade-offs - 30 phut

### 1. Workspace vs Folder - So sanh toan dien

| Tieu chi | Workspace | Folder-based |
|---|---|---|
| Isolation | Yeu: cung code, cung provider, chi khac state | Manh: rieng biet hoan toan, co the dung khac nhau |
| Risk of mistake | Cao: quen switch workspace la apply sai env | Thap: sai thu muc = biet ngay |
| Visibility | Thap: khong ro dang o workspace nao | Cao: thu muc la truong hop |
| Config per env | Kho: phai embed trong code bang `terraform.workspace` | De: moi env co file rieng |
| State separation | Co nhung cung backend config | Hoan toan tach biet |
| CI/CD integration | Phuc tap: phai goi `workspace select` truoc | Don gian: cd vao thu muc la xong |
| IAM per env | Kho: cung provider config = cung credentials | De: moi env co the dung IAM role khac |
| Code duplication | Thap: 1 `main.tf` cho tat ca | Trung binh: `main.tf` tuong tu o moi env |
| Terraform docs | Official ho tro ca hai | Official ho tro ca hai |

**Khi nao dung workspace:**
- Trong CI/CD khi moi Pull Request can tao mot ephemeral environment (PR #123 -> workspace `pr-123`)
- Demo/testing nhanh, khong phai long-term environment
- Khi tat ca environment thuc su co cung config, chi khac ten (hiem gap trong thuc te)

**Khi nao dung folder (khuyen nghi cho 90% truong hop):**
- Dev, staging, prod co config khac nhau (so AZ, instance size, NAT Gateway, etc.)
- Can audit trail ro rang: ai apply cai gi vao env nao
- Can IAM role khac nhau per environment
- Team co nhieu nguoi, can clear ownership

**Khi nao dung ca hai:** Dung folder-based cho long-lived environments (dev/staging/prod). Dung workspace trong moi environment folder de tao ephemeral environments cho testing.

### 2. Mono-repo vs Multi-repo

**Mono-repo:** Tat ca Terraform code - modules va environments - trong cung Git repository.

```
myapp-infra/            <- 1 Git repo
  modules/
    vpc/
    rds/
    eks/
  environments/
    dev/
    staging/
    prod/
```

Uu diem:
- Atomic change: sua module va update consumer trong cung commit/PR
- De search: `grep -r "vpc_cidr"` chay tren toan bo codebase
- Khong can quan ly version cho internal modules
- Onboarding nhanh: 1 repo, 1 clone

Nhuoc diem:
- Blast radius: merge sai vao main co the anh huong tat ca environment
- Kho phan quyen: developer nao cung co the thay doi production config
- Scale kem khi repo lon: CI/CD phai chay tat ca check du chi change 1 file
- Shared module update anh huong tat ca consumer ngay lap tuc (khong co versioning buffer)

**Multi-repo:** Module trong repo rieng, environment trong repo khac (hoac rieng biet theo service/team).

```
terraform-modules/      <- Repo 1: shared modules
  vpc/
  rds/
  eks/

myapp-infra/            <- Repo 2: myapp environments
  environments/
    dev/
    staging/
    prod/
  # Reference module bang: git::https://github.com/org/terraform-modules.git//vpc?ref=v2.1.0

service-b-infra/        <- Repo 3: service B environments
  environments/
    ...
```

Uu diem:
- Clear ownership: platform team own modules repo, app team own env repos
- Module versioning: consumer chon khi nao upgrade
- Phan quyen ro rang: chỉ platform team merge vao modules repo
- Module mat nhieu tien = env repos khong bi affect ngay

Nhuoc diem:
- 2 PRs cho 1 change (update module + update consumer)
- CI/CD phuc tap hon
- Kho debug: co the module repo dang o commit nao?

**Best solution theo context:**

| Context | Recommendation | Ly do |
|---|---|---|
| Ca nhan / solo | Mono-repo | Khong co overhead, don gian nhat |
| Small team (2-5) | Mono-repo | Communication cost thap, atomic changes |
| Startup | Mono-repo + ro cau truc | Move fast, refactor khi scale |
| Medium team (5-20) | Mono-repo hoac Multi-repo tuy team | Phu thuoc vao team topology |
| Enterprise | Multi-repo voi private registry | Clear ownership, governance, versioning |
| Bank/regulated | Multi-repo + Terraform Cloud | Full audit trail, change approval process, role separation |

### 3. Shared Module vs Duplicated Code

Day la trade-off co cung dynamics voi DRY (Don't Repeat Yourself) trong software.

**Shared module (DRY approach):**
```
modules/vpc/ <- 1 implementation
  main.tf
  variables.tf
  outputs.tf

environments/dev/main.tf  <- goi modules/vpc
environments/staging/main.tf  <- goi cung modules/vpc
environments/prod/main.tf  <- goi cung modules/vpc
```

Uu diem: Fix bug 1 lan + apply toi tat ca environments. Enforce standards (tagging, naming). Single source of truth.

Nhuoc diem: Change module anh huong tat ca consumers. Phai think forward ve interface. Kho ac-commodate edge case cua tung environment.

**Duplicated code (explicit approach):**
```
environments/dev/networking.tf   <- VPC code cho dev
environments/staging/networking.tf  <- Copy, co the da drift
environments/prod/networking.tf  <- Copy nua
```

Uu diem: Moi environment hoan toan doc lap. Co the customize thoai mai. Dung prod kha `terraform plan` ma khong lo anh huong dev.

Nhuoc diem: Update 3 noi. Drift theo thoi gian. Khi audit, kho biet ai la nguon goc.

**Loi khuyen thuc te:** Dung shared module nhung design interface cho flexible. Dung validation de enforce constraints. Neu 2 environment thuc su can config qua khac nhau, co le chung can 2 module khac nhau - day co the la dau hieu module granularity sai, khong phai dau hieu nen duplicate code.

**Nguyen tac quyet dinh:** Duplicate code khi su divergence la *co chu dich* va *lau dai*. Trong truong hop sai khac do bug hoac quen update, du nhieu dau hieu cho thay shared module la dung.

### 4. Terragrunt vs Vanilla Terraform - Quyet dinh cho tung context

| Scenario | Vanilla Terraform | Terragrunt |
|---|---|---|
| Hoc Terraform | Bat buoc dung vanilla | Khong dung - lam mo concept |
| 1-3 environments, 2-5 modules | Vanilla hoan toan du | Overkill |
| 3-5 environments, 5-10 modules | Vanilla voi folder-based | Co the xem xet |
| 5+ environments hoac 10+ modules | Bat dau cam thay pain | Terragrunt giai quyet dung van de nay |
| Multi-account AWS | Vanilla phuc tap | Terragrunt rat huu ich |

Trong khoa hoc nay: hoc vanilla truoc. Hieu root module, state, backend, module hoat dong nhu the nao. Sau khi hieu khi nao vanilla "dau", ban se biet chinh xac Terragrunt giai quyet van de gi.

### 5. Common Pitfalls trong Multi-Environment

**Pitfall 1 - Chia se state file:**
```hcl
# SAI: Ca dev va staging dung cung state
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "terraform.tfstate"  # Cung key!
    region = "ap-southeast-1"
  }
}
```
`terraform apply` tren staging se override state cua dev. Fix: moi environment mot key duy nhat.

**Pitfall 2 - Hardcode environment trong module:**
```hcl
# SAI: module tu quyet dinh no la "prod"
resource "aws_vpc" "main" {
  tags = {
    Environment = "prod"  # Hardcoded
  }
}
```
Module nay khong reusable cho dev hay staging. Fix: `environment` la input variable.

**Pitfall 3 - CIDR overlap giua environments:**
```hcl
# Ve sau nay co the can VPC peering hoac Transit Gateway
# Dev: 10.10.0.0/16 | Staging: 10.11.0.0/16 | Prod: 10.0.0.0/16
# Neu dat cung CIDR, khong the peer duoc
```
Thiet ke CIDR allocation plan ngay tu dau, ngan va ghi lai.

**Pitfall 4 - Khong pin Terraform version:**
```
# .terraform-version (dung voi tfenv)
1.9.5
```
Neu khong pin, developer A dung 1.8.x, developer B dung 1.9.x, CI/CD dung latest. State format co the khac. Fix: commit file `.terraform-version` hoac dung `.terraform.lock.hcl`.

**Pitfall 5 - Apply prod truc tiep tu laptop:**
Ngay ca khi code dung, nen apply thong qua CI/CD pipeline voi proper audit trail. Apply tu laptop = khong ai biet ban da apply gi, khi nao, voi credentials nao.

---

## Hands-on Lab - 60 phut

### Muc tieu lab

Lay VPC module tu Day 6-7. Tao 2 environment doc lap: `dev` va `staging`. Moi environment goi cung module nhung voi config khac nhau. State hoan toan rieng biet. So sanh `terraform plan` output giua hai environment.

### Cau truc lab

```
~/terraform-day8-lab/
  modules/
    vpc/
      main.tf          <- Copy tu Day 6-7, khong thay doi gi
      variables.tf
      outputs.tf
      versions.tf
  environments/
    dev/
      main.tf
      variables.tf
      outputs.tf
      backend.tf
      terraform.tfvars
      versions.tf
    staging/
      main.tf
      variables.tf
      outputs.tf
      backend.tf
      terraform.tfvars
      versions.tf
  common.tfvars        <- Shared values
```

### Buoc 1 - Setup thu muc va copy module

```bash
mkdir -p ~/terraform-day8-lab/modules/vpc
mkdir -p ~/terraform-day8-lab/environments/dev
mkdir -p ~/terraform-day8-lab/environments/staging

cd ~/terraform-day8-lab
```

Copy VPC module tu Day 6-7 vao `modules/vpc/`. Module nay da duoc test - khong thay doi gi trong module, chi thay doi cach goi.

### Buoc 2 - Viet file common.tfvars

**File `~/terraform-day8-lab/common.tfvars`:**

```hcl
# Values shared across all environments
# Specific environment values override these in environment-specific tfvars

project_name = "myapp"
aws_region   = "ap-southeast-1"

tags = {
  ManagedBy   = "terraform"
  Owner       = "platform-team"
  Repository  = "myapp-infrastructure"
  CostCenter  = "engineering"
}
```

### Buoc 3 - Dev environment

**File `environments/dev/versions.tf`:**

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

**File `environments/dev/backend.tf`:**

```hcl
terraform {
  backend "s3" {
    # Thay bang S3 bucket tu Day 5 cua ban
    bucket         = "terraform-state-YOUR_ACCOUNT_ID"
    key            = "myapp/environments/dev/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

**File `environments/dev/variables.tf`:**

```hcl
variable "project_name" {
  description = "Ten project, dung lam prefix cho resource names"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Ten environment"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string
}

variable "availability_zones" {
  description = "Danh sach AZ"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDRs cho public subnets"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDRs cho private subnets"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Bat NAT Gateway"
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "Dung single NAT Gateway thay vi per-AZ"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}
```

**File `environments/dev/main.tf`:**

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(var.tags, {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    })
  }
}

module "vpc" {
  # Path tu environments/dev/ len root, xuong modules/vpc/
  source = "../../modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr

  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs

  # Dev: khong co NAT Gateway -> tiet kiem chi phi
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway

  tags = var.tags
}
```

**File `environments/dev/outputs.tf`:**

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "VPC CIDR"
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

output "nat_gateway_ids" {
  description = "NAT Gateway IDs (empty neu disable)"
  value       = module.vpc.nat_gateway_ids
}

# Output de confirm dang o dung environment
output "environment_summary" {
  description = "Summary cua environment nay"
  value = {
    environment        = var.environment
    vpc_cidr           = var.vpc_cidr
    enable_nat_gateway = var.enable_nat_gateway
    nat_gateway_count  = length(module.vpc.nat_gateway_ids)
  }
}
```

**File `environments/dev/terraform.tfvars`:**

```hcl
# Dev environment - optimize cho cost, khong phai HA
environment = "dev"

vpc_cidr = "10.10.0.0/16"

# Dev dung 2 AZ - du de test multi-AZ behavior
availability_zones   = ["ap-southeast-1a", "ap-southeast-1b"]
public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]

# Khong co NAT Gateway -> private instances khong reach internet
# Chap nhan duoc cho dev, tiet kiem ~$32/thang
enable_nat_gateway = false
single_nat_gateway = true
```

### Buoc 4 - Staging environment

Staging su dung cung structure y het, nhung khac config. Day la diem co y nghia: khi nhin vao `staging/terraform.tfvars` vs `dev/terraform.tfvars`, ban thay ngay su khac biet.

**File `environments/staging/versions.tf`:** (y het dev)

**File `environments/staging/backend.tf`:**

```hcl
terraform {
  backend "s3" {
    bucket         = "terraform-state-YOUR_ACCOUNT_ID"
    key            = "myapp/environments/staging/terraform.tfstate"  # Key KHAC
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

**File `environments/staging/variables.tf`:** (y het dev)

**File `environments/staging/main.tf`:**

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(var.tags, {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    })
  }
}

module "vpc" {
  source = "../../modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr

  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs

  # Staging: co NAT Gateway -> simulate production behavior
  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = var.single_nat_gateway

  tags = var.tags
}
```

**File `environments/staging/outputs.tf`:** (y het dev)

**File `environments/staging/terraform.tfvars`:**

```hcl
# Staging environment - simulate production, test truoc khi len prod
environment = "staging"

# CIDR khac dev de tranh overlap khi can peering sau nay
vpc_cidr = "10.11.0.0/16"

# Staging dung 2 AZ giong prod (prod co the dung 3)
availability_zones   = ["ap-southeast-1a", "ap-southeast-1b"]
public_subnet_cidrs  = ["10.11.1.0/24", "10.11.2.0/24"]
private_subnet_cidrs = ["10.11.11.0/24", "10.11.12.0/24"]

# Co NAT Gateway giong prod -> private instances co the reach internet
# Single NAT -> tiet kiem chi phi, chap nhan it HA hon prod
enable_nat_gateway = true
single_nat_gateway = true
```

### Buoc 5 - Init va Plan dev environment

```bash
cd ~/terraform-day8-lab/environments/dev

terraform init
```

Expected output:
```
Initializing the backend...

Successfully configured the backend "s3"!

Initializing modules...
- vpc in ../../modules/vpc

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...

Terraform has been successfully initialized!
```

```bash
# Load common.tfvars + dev-specific tfvars
terraform plan \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
```

Expected output (rut gon):
```
Terraform will perform the following actions:

  # module.vpc.aws_internet_gateway.main will be created
  + resource "aws_internet_gateway" "main" {
      + tags = {
          + "Environment" = "dev"
          + "ManagedBy"   = "terraform"
          + "Name"        = "myapp-dev-igw"
          + "Project"     = "myapp"
        }
      ...
    }

  # module.vpc.aws_route_table.private[0] will be created
  # module.vpc.aws_route_table.public will be created
  # (route table khong co route 0.0.0.0/0 -> NAT vi disable_nat_gateway = false)
  # module.vpc.aws_route_table_association.private[0] will be created
  # module.vpc.aws_route_table_association.private[1] will be created
  # module.vpc.aws_route_table_association.public[0] will be created
  # module.vpc.aws_route_table_association.public[1] will be created
  # module.vpc.aws_subnet.private[0] will be created (10.10.11.0/24)
  # module.vpc.aws_subnet.private[1] will be created (10.10.12.0/24)
  # module.vpc.aws_subnet.public[0] will be created (10.10.1.0/24)
  # module.vpc.aws_subnet.public[1] will be created (10.10.2.0/24)
  # module.vpc.aws_vpc.main will be created (10.10.0.0/16)

Plan: 9 to add, 0 to change, 0 to destroy.
```

Luu y: **9 resources** - khong co EIP va NAT Gateway vi `enable_nat_gateway = false`.

### Buoc 6 - Init va Plan staging environment

```bash
cd ~/terraform-day8-lab/environments/staging

terraform init
```

```bash
terraform plan \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
```

Expected output (rut gon):
```
Terraform will perform the following actions:

  # module.vpc.aws_eip.nat[0] will be created   <- KHAC DEV
  + resource "aws_eip" "nat" {
      + tags = {
          + "Environment" = "staging"          <- staging, khong phai dev
          + "Name"        = "myapp-staging-nat-eip-1"
        }
      ...
    }

  # module.vpc.aws_nat_gateway.main[0] will be created   <- KHAC DEV
  + resource "aws_nat_gateway" "main" {
      + tags = {
          + "Name" = "myapp-staging-nat-1"
        }
      ...
    }

  # module.vpc.aws_route_table.private[0] will be created
  # (route 0.0.0.0/0 -> nat gateway duoc them, khac dev)
  # module.vpc.aws_subnet.private[0] will be created (10.11.11.0/24)  <- CIDR KHAC
  # module.vpc.aws_subnet.public[0] will be created (10.11.1.0/24)    <- CIDR KHAC
  # module.vpc.aws_vpc.main will be created (10.11.0.0/16)             <- CIDR KHAC

Plan: 11 to add, 0 to change, 0 to destroy.
```

Luu y: **11 resources** (9 + EIP + NAT Gateway) - staging co nat gateway, dev khong co.

### Buoc 7 - So sanh plan output - Phan tich su khac biet

Mo 2 terminal, chay plan o ca 2 va so sanh:

| Diem so sanh | Dev | Staging |
|---|---|---|
| Resource count | 9 | 11 |
| VPC CIDR | 10.10.0.0/16 | 10.11.0.0/16 |
| Subnet CIDRs | 10.10.x.0/24 | 10.11.x.0/24 |
| EIP | Khong co | 1 EIP |
| NAT Gateway | Khong co | 1 NAT Gateway |
| Private RT route | Khong co 0.0.0.0/0 | Co route -> NAT |
| Resource names | myapp-dev-* | myapp-staging-* |
| Environment tag | dev | staging |
| State location | .../dev/terraform.tfstate | .../staging/terraform.tfstate |

Day chinh xac la dieu muon thay: cung module, cung code, nhung output khac nhau do config khac nhau. Module hoat dong nhu mot function - dau vao khac, dau ra khac.

### Buoc 8 - Apply (tuy chon, can AWS credentials)

```bash
# Apply dev
cd ~/terraform-day8-lab/environments/dev
terraform apply \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"

# Apply staging (chi sau khi dev thanh cong)
cd ~/terraform-day8-lab/environments/staging
terraform apply \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
```

Xac nhan state doc lap:

```bash
# Check dev state
cd ~/terraform-day8-lab/environments/dev
terraform state list

# Expected:
# module.vpc.aws_internet_gateway.main
# module.vpc.aws_route_table.private[0]
# module.vpc.aws_route_table.public
# module.vpc.aws_route_table_association.private[0]
# module.vpc.aws_route_table_association.private[1]
# module.vpc.aws_route_table_association.public[0]
# module.vpc.aws_route_table_association.public[1]
# module.vpc.aws_subnet.private[0]
# module.vpc.aws_subnet.private[1]
# module.vpc.aws_subnet.public[0]
# module.vpc.aws_subnet.public[1]
# module.vpc.aws_vpc.main

# Check staging state (rieng biet)
cd ~/terraform-day8-lab/environments/staging
terraform state list

# Expected: tuong tu nhung co them:
# module.vpc.aws_eip.nat[0]
# module.vpc.aws_nat_gateway.main[0]
```

```bash
# Output cua moi environment
cd ~/terraform-day8-lab/environments/dev
terraform output environment_summary
# {
#   "enable_nat_gateway" = false
#   "environment" = "dev"
#   "nat_gateway_count" = 0
#   "vpc_cidr" = "10.10.0.0/16"
# }

cd ~/terraform-day8-lab/environments/staging
terraform output environment_summary
# {
#   "enable_nat_gateway" = true
#   "environment" = "staging"
#   "nat_gateway_count" = 1
#   "vpc_cidr" = "10.11.0.0/16"
# }
```

### Buoc 9 - Troubleshooting pho bien

**Loi 1: Backend key conflict**
```
Error: Error acquiring the state lock
```
Nguyen nhan: Dev va staging cung key tren S3. Kiem tra `backend.tf` cua hai environment - key phai khac nhau.

**Loi 2: Module source khong tim thay sau khi copy code**
```
Error: Module not installed
```
Fix: Chay `terraform init` trong moi environment folder. init phai chay trong cung thu muc voi `backend.tf`.

**Loi 3: Variable khong duoc set**
```
Error: No value for required variable
Do you have a terraform.tfvars file in this directory?
```
Khi dung `-var-file`, file `terraform.tfvars` khong duoc auto-load neu ban dung `-var-file` flag cho file khac. Giai phap: truyen ca hai: `-var-file="../../common.tfvars" -var-file="terraform.tfvars"`.

**Loi 4: CIDR overlap**
```
Error: error creating VPC: InvalidVpc.Conflict
```
Dev dung 10.10.0.0/16 va staging dung 10.11.0.0/16 nen khong overlap. Neu gap loi nay: kiem tra AWS console xem co VPC nao khac dang dung cung CIDR trong cung account.

**Loi 5: Apply sai environment**
Xac nhan dang o dung thu muc truoc khi apply:
```bash
pwd  # Xac nhan duong dan
cat terraform.tfvars  # Doc lai config
cat backend.tf  # Xac nhan state key
terraform workspace show  # Neu dung workspace
```

### Buoc 10 - Cleanup

```bash
# Destroy staging truoc
cd ~/terraform-day8-lab/environments/staging
terraform destroy \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
# Expected: Destroy complete! Resources: 11 destroyed.

# Destroy dev
cd ~/terraform-day8-lab/environments/dev
terraform destroy \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
# Expected: Destroy complete! Resources: 9 destroyed.
```

---

## Kiem tra hieu bai

1. **Trade-off question:** Team ban co 3 dev dung dev environment va 1 SRE quan ly staging/prod. Ban dang chon giua Terraform workspace va folder-based approach. Neu la Senior Engineer trong team, ban se chon gi va tai sao? Neu co ai trong team phan doi, ban se lap luan the nao?

2. **Debug scenario:** Developer chay `terraform apply` va tao VPC tren prod thay vi dev. State file bi overwrite. Phan tich nguyen nhan goc re (root cause), propose it nhat 2 thay doi ky thuat va 1 thay doi process de ngan cho lan sau.

3. **tfvars layering:** Ban co `common.tfvars` voi `tags = { ManagedBy = "terraform" }`. File `staging.tfvars` co `tags = { ManagedBy = "manual" }`. Khi apply voi `-var-file="common.tfvars" -var-file="staging.tfvars"`, gia tri cuoi cung cua `ManagedBy` la gi? Giai thich behavior nay.

4. **Module interface design:** Ban viet module VPC hom nay. Sau 6 thang, co requirement moi: prod can VPC Flow Logs, dev va staging khong can (chi phi). Co nhung cach nao de them feature nay ma **khong breaking existing callers**? Neu so sanh cach nao tot hon?

5. **Architecture decision:** Startup cua ban dang grow. Hien tai co dev va prod (staging chua co). Module VPC la local path trong mono-repo. Ban chuan bi hire them 5 engineer. Nhung thay doi nao ban nen lam truoc khi ho join?

---

## Tom tat cuoi ngay

### Key points

- **Folder-based isolation la default choice cho hau het team:** Moi environment la mot thu muc rieng, state rieng, backend rieng. Risk khi apply sai environment rat thap vi sai thu muc = thay ngay
- **Workspace huu ich cho ephemeral environments, khong phai long-lived:** Dung workspace cho PR environments, feature branches. Dung folder cho dev/staging/prod
- **tfvars layering tao separation giua shared defaults va environment-specific config:** `common.tfvars` cho shared values, `staging.tfvars` chi override nhung gi khac nhau
- **Cung module + khac config = cung behavior contract:** Day la gia tri thuc su cua module reuse trong multi-env context. Staging phan anh prod vi chung dung cung code path, chi khac dau vao
- **State isolation la non-negotiable:** Dev va prod khong duoc chia se state. Bao gio cung. Bat ke approach nao ban chon

### Outputs da tao ra

- Folder structure `environments/dev/` va `environments/staging/` voi state hoan toan rieng biet
- VPC module duoc reuse: `dev` co 9 resources, `staging` co 11 resources (co NAT Gateway)
- `common.tfvars` va environment-specific `terraform.tfvars` dem lai config ro rang, co cau truc
- Plan output so sanh giua 2 environment, hieu ro su khac biet va tai sao

### Chuan bi cho Day 9 - Advanced HCL

Day 9 se di sau hon vao HCL language features: `for_each` tren module, `dynamic` blocks, advanced locals, va conditionals. Cac kien truc nay se giup ban viet module linh hoat hon - thay vi phai tao 2 environment folder rieng biet, ban co the cau hinh chung tu mot `map`. Trade-off la gi khi lam vay se duoc phan tich cu the.

Truoc khi hoc: Nhin lai `environments/dev/main.tf` va `environments/staging/main.tf`. Chung giong nhau toi ~90%. Dieu gi co the duoc extract ra? Dieu gi khong the? Day la cau hoi dung logic de di vao Day 9.

---

## Tham khao them

- [Terraform Backend Configuration](https://developer.hashicorp.com/terraform/language/settings/backends/configuration) - Cach cau hinh backend cho moi environment
- [Terraform Workspaces](https://developer.hashicorp.com/terraform/language/state/workspaces) - Official docs ve workspace, bao gom khi nao nen dung
- [Terraform Variable Files](https://developer.hashicorp.com/terraform/language/values/variables#variable-definitions-tfvars-files) - tfvars file loading order va precedence
- [Terragrunt Documentation](https://terragrunt.gruntwork.io/docs/) - Khi ban ready de di xa hon vanilla Terraform
- [Gruntwork Blog - How to manage terraform state](https://blog.gruntwork.io/how-to-manage-terraform-state-28f5697e68bb) - Bai viet goc cua team Gruntwork, anh huong lon den community practices
- [Terraform Best Practices](https://www.terraform-best-practices.com) - Community-maintained guide, phan ve module structure rat huu ich
