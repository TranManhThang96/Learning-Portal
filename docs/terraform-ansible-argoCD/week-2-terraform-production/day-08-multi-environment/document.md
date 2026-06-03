# Day 8 - Reference Document: Multi-Environment Strategy

---

## 1. Multi-Environment Strategy Comparison Matrix

### Isolation approaches

| Tieu chi | Folder-based | Workspace | Hybrid |
|---|---|---|---|
| **State isolation** | Hoan toan rieng biet | Rieng biet (cung backend, khac key) | Rieng biet |
| **Code isolation** | Moi env co file rieng | Cung code, khac workspace | Tuy theo layer |
| **Risk khi apply sai** | Thap (sai folder = thay ngay) | Cao (quen switch workspace) | Thap |
| **Config per env** | Ro rang, moi env co tfvars rieng | Embed trong code via `terraform.workspace` | Ro rang |
| **IAM credentials** | Co the giong hoac khac nhau | Thuong giong nhau | Linh hoat |
| **CI/CD complexity** | Don gian (cd vao folder) | Trung binh (phai `workspace select`) | Trung binh |
| **Code duplication** | Trung binh (main.tf tuong tu) | Thap (1 main.tf) | Thap |
| **Visibility** | Cao | Thap | Cao |
| **Terragrunt benefit** | Cao (giam duplicate) | Thap | Cao |
| **Khi nao nen dung** | Long-lived envs (dev/staging/prod) | Ephemeral envs (PR, feature test) | Ca hai |

### Repo structure approaches

| Tieu chi | Mono-repo | Multi-repo | Poly-repo |
|---|---|---|---|
| **Dinh nghia** | Modules + envs trong 1 repo | Modules trong repo rieng, env trong repo khac | Moi service/team co repo rieng |
| **Atomic changes** | Co (1 commit, 1 PR) | Khong (2 PRs minimum) | Khong |
| **Module versioning** | Khong can (always latest) | Can (git tag) | Can (git tag/registry) |
| **Permission control** | Kho (ai cung co the touch prod) | Ro rang (2 repo, 2 team) | Ro rang |
| **CI/CD complexity** | Thap | Trung binh | Cao |
| **Onboarding** | De (1 clone) | Trung binh | Kho |
| **Scale** | Kem (repo lon theo thoi gian) | Tot | Tot |
| **Discovery** | De (grep toan bo) | Kho hon | Kho |
| **Best for** | Solo, small team | Medium team | Enterprise |

---

## 2. Folder Structure Templates

### Template A - Small team (2-5 engineers, <= 3 environments)

```
myapp-infra/                      <- 1 Git repo (mono-repo)
  .gitignore
  .terraform-version               <- Pin Terraform version (tfenv)
  README.md
  common.tfvars                    <- Shared: project_name, aws_region, tags
  modules/
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
  environments/
    dev/
      main.tf
      variables.tf
      outputs.tf
      backend.tf
      terraform.tfvars             <- Dev-specific: CIDRs, instance sizes
      versions.tf
    staging/
      main.tf
      variables.tf
      outputs.tf
      backend.tf
      terraform.tfvars
      versions.tf
    prod/
      main.tf
      variables.tf
      outputs.tf
      backend.tf
      terraform.tfvars
      versions.tf
```

**Backend key convention cho Template A:**
```hcl
# dev/backend.tf
key = "myapp/environments/dev/terraform.tfstate"

# staging/backend.tf
key = "myapp/environments/staging/terraform.tfstate"

# prod/backend.tf
key = "myapp/environments/prod/terraform.tfstate"
```

**Cach chay:**
```bash
cd environments/dev && terraform init && terraform plan -var-file="../../common.tfvars"
cd environments/staging && terraform init && terraform plan -var-file="../../common.tfvars"
```

---

### Template B - Medium team (5-15 engineers, multi-service)

```
platform-infra/                    <- Mono-repo cho toan bo platform
  .gitignore
  .terraform-version
  common/
    variables.tf                   <- Shared variable declarations
    common.tfvars                  <- Shared values
    tags.tf                        <- Standard tag locals (dung nhu module)
  modules/
    vpc/
    rds/
    eks/
    elasticache/
    s3-private/
  services/
    service-a/
      environments/
        dev/
          main.tf
          backend.tf
          terraform.tfvars
          versions.tf
        staging/
          main.tf
          backend.tf
          terraform.tfvars
          versions.tf
        prod/
          main.tf
          backend.tf
          terraform.tfvars
          versions.tf
    service-b/
      environments/
        dev/
        staging/
        prod/
  platform/                        <- Shared platform infra (EKS cluster, shared RDS, etc.)
    environments/
      dev/
      staging/
      prod/
```

**Backend key convention cho Template B:**
```hcl
# services/service-a/environments/dev/backend.tf
key = "services/service-a/environments/dev/terraform.tfstate"

# platform/environments/prod/backend.tf
key = "platform/environments/prod/terraform.tfstate"
```

---

### Template C - Enterprise (20+ engineers, multi-account AWS)

```
terraform-modules/                 <- Repo 1: Module library (platform team owns)
  vpc/
    main.tf
    variables.tf
    outputs.tf
    versions.tf
    CHANGELOG.md
    README.md                      <- terraform-docs generated
  rds/
  eks/
  # Versioning: git tag v2.1.0 sau moi release

myapp-platform-infra/              <- Repo 2: Platform-level infra
  environments/
    dev/
      main.tf                      <- source = "git::...//vpc?ref=v2.1.0"
      backend.tf
      terraform.tfvars
    staging/
    prod/

myapp-service-a-infra/             <- Repo 3: Service A infra
  environments/
    dev/
    staging/
    prod/

myapp-service-b-infra/             <- Repo 4: Service B infra
  environments/
    ...
```

**Reference module tu separate repo (Template C):**
```hcl
# environments/prod/main.tf
module "vpc" {
  source = "git::https://github.com/myorg/terraform-modules.git//vpc?ref=v2.1.0"

  # Input variables
  project_name = var.project_name
  environment  = "prod"
  vpc_cidr     = "10.0.0.0/16"
  # ...
}
```

---

## 3. tfvars Layering Patterns

### Pattern 1 - Basic 2-layer (common + environment)

```
project/
  common.tfvars          <- Layer 1: shared defaults
  environments/
    dev/
      terraform.tfvars   <- Layer 2: dev overrides
    staging/
      terraform.tfvars   <- Layer 2: staging overrides
    prod/
      terraform.tfvars   <- Layer 2: prod overrides
```

**common.tfvars:**
```hcl
project_name = "myapp"
aws_region   = "ap-southeast-1"

tags = {
  ManagedBy  = "terraform"
  Owner      = "platform-team"
  CostCenter = "engineering"
}
```

**environments/prod/terraform.tfvars:**
```hcl
# Chi override nhung gi khac common
environment        = "prod"
vpc_cidr           = "10.0.0.0/16"
enable_nat_gateway = true
single_nat_gateway = false  # Per-AZ NAT cho HA
instance_type      = "t3.large"
```

**Apply command:**
```bash
cd environments/prod
terraform plan \
  -var-file="../../common.tfvars" \
  -var-file="terraform.tfvars"
```

---

### Pattern 2 - 3-layer (global + region + environment)

Huu ich khi deploy multi-region.

```
project/
  global.tfvars              <- Layer 1: global config
  regions/
    ap-southeast-1.tfvars    <- Layer 2: region-specific
    us-east-1.tfvars
  environments/
    ap-southeast-1/
      dev/
        terraform.tfvars     <- Layer 3: env-specific
      prod/
        terraform.tfvars
    us-east-1/
      prod/
        terraform.tfvars
```

**global.tfvars:**
```hcl
project_name = "myapp"
tags = {
  ManagedBy = "terraform"
}
```

**regions/ap-southeast-1.tfvars:**
```hcl
aws_region = "ap-southeast-1"
availability_zones = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
```

**environments/ap-southeast-1/prod/terraform.tfvars:**
```hcl
environment = "prod"
vpc_cidr    = "10.0.0.0/16"
```

**Apply command:**
```bash
cd environments/ap-southeast-1/prod
terraform plan \
  -var-file="../../../global.tfvars" \
  -var-file="../../../regions/ap-southeast-1.tfvars" \
  -var-file="terraform.tfvars"
```

---

### Pattern 3 - tfvars vs environment variables

Terraform nhan variable values theo thu tu uu tien (sau ghi de truoc):

```
1. Default values trong variable block (thap nhat)
2. terraform.tfvars (auto-loaded)
3. *.auto.tfvars (auto-loaded, theo alphabetical order)
4. -var-file flag (theo thu tu tren command line)
5. -var flag
6. TF_VAR_<name> environment variables
7. Interactive prompt (cao nhat, neu khong co gi khac)
```

**Pattern dung environment variables cho sensitive values:**
```bash
# Khong luu credential trong tfvars file (vao git = bao mat issue)
export TF_VAR_db_password="$(aws secretsmanager get-secret-value --secret-id prod/db-password --query SecretString --output text)"

terraform apply -var-file="terraform.tfvars"
# db_password duoc set tu env var, khong xuat hien trong tfvars file
```

**Pattern dung trong CI/CD:**
```yaml
# GitHub Actions workflow
- name: Terraform Apply
  env:
    TF_VAR_db_password: ${{ secrets.PROD_DB_PASSWORD }}
    AWS_ACCESS_KEY_ID: ${{ secrets.PROD_AWS_KEY }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.PROD_AWS_SECRET }}
  run: |
    cd environments/prod
    terraform init
    terraform apply -var-file="../../common.tfvars" -auto-approve
```

---

### Pattern 4 - auto.tfvars cho auto-loading multi-file

Neu khong muon truyen `-var-file` flag, dung `.auto.tfvars` extension:

```
environments/prod/
  terraform.tfvars         <- duoc auto-load
  common.auto.tfvars       <- duoc auto-load (alphabetical: common truoc)
  tags.auto.tfvars         <- duoc auto-load (alphabetical: sau common)
```

**Alphabetical load order:**
```
common.auto.tfvars   <- load truoc
tags.auto.tfvars     <- load sau (override neu co conflict)
terraform.tfvars     <- load sau cung (uu tien cao nhat trong auto-load)
```

**Luu y:** Neu dung `-var-file` flag bat ky, files duoc chi dinh qua flag co uu tien cao hon `.auto.tfvars`. Giu nhat quan: hoac chi dung auto-load, hoac chi dung explicit `-var-file`. Tron lan gay nham lan.

---

## 4. Terragrunt Quick Reference

### Khi nao xem xet Terragrunt

- Tren 5 environment hoac tren 10 module configurations
- Backend configuration blatantly duplicate (chi khac `key`)
- Can dep dependency giua modules trong cung environment mot cach type-safe
- Multi-account AWS setup phuc tap

### Cau truc Terragrunt project

```
myapp-infra/
  terragrunt.hcl             <- Root config: remote_state, generate blocks
  common_vars.yaml           <- Shared variables (YAML hay HCL deu duoc)
  environments/
    dev/
      env_vars.yaml          <- Dev-specific variables
      vpc/
        terragrunt.hcl       <- Include root + point to vpc module + inputs
      rds/
        terragrunt.hcl
    staging/
      env_vars.yaml
      vpc/
        terragrunt.hcl
      rds/
        terragrunt.hcl
    prod/
      env_vars.yaml
      vpc/
        terragrunt.hcl
      rds/
        terragrunt.hcl
  modules/
    vpc/
    rds/
```

### Root terragrunt.hcl

```hcl
# myapp-infra/terragrunt.hcl

locals {
  # Doc common vars
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))

  # Doc environment-specific vars (tim env_vars.yaml trong thu muc cha gan nhat)
  env_vars = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

# Tu dong generate backend.tf cho moi module
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "${local.common_vars.project_name}-terraform-state-${local.common_vars.aws_account_id}"
    # path_relative_to_include() tra ve relative path tu root -> environments/dev/vpc
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.common_vars.aws_region
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

# Tu dong generate versions.tf
generate "versions" {
  path      = "versions.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
EOF
}
```

### Module-level terragrunt.hcl

```hcl
# environments/staging/vpc/terragrunt.hcl

# Include tat ca config tu root terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

locals {
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
}

terraform {
  # Point toi module source
  source = "../../../modules/vpc"
}

# Inputs tuong duong voi variables trong terraform.tfvars
inputs = {
  project_name = local.common_vars.project_name
  environment  = local.env_vars.environment
  aws_region   = local.common_vars.aws_region

  vpc_cidr             = local.env_vars.vpc_cidr
  availability_zones   = local.env_vars.availability_zones
  public_subnet_cidrs  = local.env_vars.public_subnet_cidrs
  private_subnet_cidrs = local.env_vars.private_subnet_cidrs
  enable_nat_gateway   = local.env_vars.enable_nat_gateway
  single_nat_gateway   = local.env_vars.single_nat_gateway

  tags = local.common_vars.tags
}
```

### Dep dependency giua modules (Terragrunt killer feature)

```hcl
# environments/staging/rds/terragrunt.hcl

include "root" {
  path = find_in_parent_folders()
}

# Khai bao dependency vao VPC module (tuong tu context cung environment)
dependency "vpc" {
  config_path = "../vpc"

  # Khi chay plan ma vpc chua apply, dung mock outputs
  mock_outputs = {
    vpc_id             = "vpc-00000000000000000"
    private_subnet_ids = ["subnet-00000000000000000", "subnet-00000000000000001"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

terraform {
  source = "../../../modules/rds"
}

inputs = {
  # Lay output tu vpc dependency
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnet_ids

  # RDS-specific inputs
  db_name       = "myapp"
  instance_class = "db.t3.medium"
}
```

### Terragrunt CLI cac lenh quan trong

```bash
# Init tat ca module trong thu muc hien tai va sub-directories
terragrunt run-all init

# Plan tat ca modules, ton trong dependency order
terragrunt run-all plan

# Apply tat ca modules theo dung dependency order
terragrunt run-all apply

# Apply chi module hien tai (khong recursive)
terragrunt apply

# Destroy theo thu tu nguoc
terragrunt run-all destroy

# Xem dependency graph
terragrunt graph-dependencies

# Validate HCL files
terragrunt hclfmt --terragrunt-check
```

---

## 5. CIDR Allocation Planning

Thiet ke CIDR plan truoc khi bat dau. Khi da deploy, re-CIDR rat kho (phai destroy va recreate VPC).

### Conventional allocation scheme

```
10.0.0.0/8      <- Private range (RFC 1918), lon nhat
  10.0.0.0/16   <- Production VPC
  10.1.0.0/16   <- Staging VPC
  10.2.0.0/16   <- Dev VPC

  # Hoac theo service:
  10.10.0.0/16  <- Service A prod
  10.11.0.0/16  <- Service A staging
  10.12.0.0/16  <- Service A dev
  10.20.0.0/16  <- Service B prod
  10.21.0.0/16  <- Service B staging

172.16.0.0/12   <- Private range khac, it pho bien hon
192.168.0.0/16  <- Nho nhat trong 3 private ranges
```

### Subnet allocation trong VPC /16

```
VPC: 10.0.0.0/16 (65536 IPs)
  Public subnets (Internet-reachable):
    AZ-a: 10.0.0.0/24   (251 usable IPs, AWS reserve 5)
    AZ-b: 10.0.1.0/24
    AZ-c: 10.0.2.0/24

  Private subnets (Application tier):
    AZ-a: 10.0.16.0/20  (4091 usable IPs - lon hon vi workloads o day)
    AZ-b: 10.0.32.0/20
    AZ-c: 10.0.48.0/20

  Database subnets (Restricted access):
    AZ-a: 10.0.128.0/24
    AZ-b: 10.0.129.0/24
    AZ-c: 10.0.130.0/24
```

**Nguyen tac:**
- Public subnets: /24 (251 IPs) - du cho load balancers, NAT Gateways, bastion
- Private subnets: /20 (4091 IPs) - workloads scale ra day, can nhieu IP
- Database subnets: /24 - it instance hon, khong can nhieu IP
- Giua cac tier: khoang trong de co the expand sau nay

---

## 6. State Key Naming Conventions

Nhat quan trong naming la dieu kien de CI/CD va audit hoat dong duoc.

### Convention A - Theo environment va service

```
<account_alias>/<service>/<environment>/terraform.tfstate

# Vi du:
mycompany-prod/platform/networking/terraform.tfstate
mycompany-prod/service-a/compute/terraform.tfstate
mycompany-dev/platform/networking/terraform.tfstate
mycompany-dev/service-a/compute/terraform.tfstate
```

### Convention B - Theo environment truoc (pho bien hon)

```
<environment>/<service>/<module>/terraform.tfstate

# Vi du:
prod/platform/vpc/terraform.tfstate
prod/platform/eks/terraform.tfstate
prod/service-a/rds/terraform.tfstate
staging/platform/vpc/terraform.tfstate
dev/service-a/rds/terraform.tfstate
```

### Convention C - Theo folder path (Terragrunt default)

```
# path_relative_to_include() trong Terragrunt tu dong tao:
environments/dev/vpc/terraform.tfstate
environments/staging/vpc/terraform.tfstate
environments/prod/vpc/terraform.tfstate
environments/prod/rds/terraform.tfstate
```

**Khuyen nghi:** Dung Convention B hoac C. Environment o dau de de filter trong S3 (`aws s3 ls s3://bucket/prod/`).

---

## 7. Environment Promotion Workflow

Quy trinh chuan de "promote" change tu dev len prod:

```
Developer branch -> PR -> dev apply -> staging apply -> prod apply
```

### Workflow chi tiet

```
1. Developer viet code tren feature branch
   git checkout -b feature/add-vpc-flow-logs

2. Test tren dev (apply to dev environment)
   cd environments/dev
   terraform plan -var-file="../../common.tfvars"
   terraform apply -var-file="../../common.tfvars"
   # Verify tren AWS console

3. Tao PR, peer review, merge vao main

4. CI/CD tu dong apply len staging
   cd environments/staging
   terraform plan -var-file="../../common.tfvars"  # Review plan output
   # Co manual approval step truoc khi apply
   terraform apply -var-file="../../common.tfvars"
   # Chay integration tests

5. After staging sign-off, approve prod apply
   cd environments/prod
   terraform plan -var-file="../../common.tfvars"  # Final review
   # Approval tu senior engineer / SRE
   terraform apply -var-file="../../common.tfvars"
```

### Dieu kien de promote

| Tu | Den | Dieu kien |
|---|---|---|
| feature branch | dev | CI tests pass, code review |
| dev | staging | `terraform plan` clean (no unexpected diffs), functional test pass |
| staging | prod | Staging soak time (>24h), load test pass, SRE approval |

---

## 8. Quick Reference - Multi-environment Commands

### Folder-based workflow

```bash
# Dev
cd environments/dev
terraform init
terraform plan -var-file="../../common.tfvars" -var-file="terraform.tfvars" -out=dev.tfplan
terraform show dev.tfplan          # Review plan
terraform apply dev.tfplan

# Staging
cd environments/staging
terraform init
terraform plan -var-file="../../common.tfvars" -var-file="terraform.tfvars" -out=staging.tfplan
terraform apply staging.tfplan

# Prod
cd environments/prod
terraform init
terraform plan -var-file="../../common.tfvars" -var-file="terraform.tfvars" -out=prod.tfplan
terraform apply prod.tfplan        # Sau khi review va approve plan

# Check state
terraform state list
terraform output -json
terraform output environment_summary
```

### Workspace workflow (ephemeral environments)

```bash
# Tao va switch sang workspace moi
terraform workspace new pr-123
terraform workspace select pr-123
terraform workspace show           # Confirm dang o dung workspace

# Apply voi workspace-specific values
terraform plan -var="environment=pr-123"
terraform apply -var="environment=pr-123"

# Cleanup sau khi PR merge
terraform destroy -var="environment=pr-123"
terraform workspace select default
terraform workspace delete pr-123

# List tat ca workspaces
terraform workspace list
```

### Compare environments (diff two plans)

```bash
# Tao plan file cho ca hai environments
cd environments/dev
terraform plan -var-file="../../common.tfvars" -out=dev.plan -no-color 2>&1 | tee dev-plan.txt

cd environments/staging
terraform plan -var-file="../../common.tfvars" -out=staging.plan -no-color 2>&1 | tee staging-plan.txt

# So sanh
diff dev-plan.txt staging-plan.txt
```
