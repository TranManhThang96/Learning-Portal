# Day 28: Document — Terraform Advanced Reference

## Module Design Patterns

### Pattern 1: Simple Resource Module

```hcl
# modules/s3-bucket/
# Wrap 1 resource with opinionated defaults
modules/s3-bucket/
├── main.tf          # aws_s3_bucket + related resources
├── variables.tf     # bucket_name, environment, versioning
├── outputs.tf       # bucket_id, bucket_arn, bucket_domain
└── README.md
```

### Pattern 2: Composite Module

```hcl
# modules/vpc/
# Multiple related resources as a unit
modules/vpc/
├── main.tf          # VPC + subnets + NAT + route tables
├── security.tf      # Default security groups
├── variables.tf     # cidr, azs, enable_nat
├── outputs.tf       # vpc_id, subnet_ids, sg_ids
└── README.md
```

### Pattern 3: Stack Module

```hcl
# modules/web-stack/
# Composes other modules
module "networking" {
  source = "../networking"
  ...
}
module "compute" {
  source = "../compute"
  vpc_id = module.networking.vpc_id
  ...
}
module "database" {
  source = "../database"
  vpc_id = module.networking.vpc_id
  ...
}
```

### Module Interface Checklist

```markdown
✅ Good module interface:
- Variables with types, descriptions, defaults
- Validation rules for critical inputs
- Outputs for ALL values other modules might need
- README with usage example
- No hardcoded values
- Provider NOT configured in module (root module configures)

❌ Bad module interface:
- Variables without descriptions
- Missing outputs (forces users to use data sources)
- Provider block inside module
- Hardcoded regions, account IDs, etc.
```

---

## State Management Cheat Sheet

### State Commands Quick Reference

```bash
# List all resources
terraform state list

# Show specific resource
terraform state show module.web.docker_container.app[0]

# Move resource (refactor without destroy)
terraform state mv \
  docker_container.old_name \
  docker_container.new_name

# Move into module
terraform state mv \
  docker_container.web \
  module.webserver.docker_container.web

# Remove from state (stop managing, don't destroy)
terraform state rm docker_container.legacy

# Import existing resource manually (fallback)
terraform import docker_container.app <container_id>

# Backup state
terraform state pull > backup-$(date +%Y%m%d).tfstate

# Restore state (DANGEROUS)
terraform state push backup-20240115.tfstate
```

### State Migration Scenarios

| Scenario | Command | Risk |
|----------|---------|------|
| Rename resource | `state mv old new` | LOW |
| Move to module | `state mv res module.x.res` | LOW |
| Split state | `state mv` + new backend | MEDIUM |
| Merge states | Manual `state mv` per resource | HIGH |
| Recover corrupted | `state push` from backup | HIGH |
| Remove unmanaged | `state rm resource` | LOW |

### Remote Backend Configuration Examples

**AWS S3:**
```hcl
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "prod/networking/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

**GCP GCS:**
```hcl
terraform {
  backend "gcs" {
    bucket = "company-terraform-state"
    prefix = "prod/networking"
  }
}
```

**Terraform Cloud:**
```hcl
terraform {
  cloud {
    organization = "my-company"
    workspaces {
      name = "prod-networking"
    }
  }
}
```

---

## Environment Strategy Comparison

| Strategy | Structure | Isolation | Duplication | Best For |
|----------|-----------|-----------|-------------|----------|
| **Workspaces** | Same dir, different workspace | State only | None | Small teams, similar envs |
| **Directories** | Separate dirs, shared modules | Full (code + state) | Some tfvars | Production, different configs |
| **Branches** | Git branches per env | Full | High | NOT recommended |
| **Terragrunt** | DRY wrapper over directories | Full | Minimal | Large orgs, many envs |

### Directory-based Layout (Recommended)

```
infrastructure/
├── modules/               # Shared, versioned modules
│   ├── networking/
│   ├── kubernetes/
│   ├── database/
│   └── monitoring/
├── environments/
│   ├── dev/
│   │   ├── main.tf       # Uses modules with dev config
│   │   ├── backend.tf    # s3://state/dev/terraform.tfstate
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf       # Uses modules with staging config
│   │   ├── backend.tf    # s3://state/staging/terraform.tfstate
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf       # Uses modules with prod config
│       ├── backend.tf    # s3://state/prod/terraform.tfstate
│       └── terraform.tfvars
└── global/                # Shared resources (IAM, DNS)
    ├── main.tf
    └── backend.tf
```

---

## Terraform Anti-patterns Reference

### 1. Provider Inside Module

```hcl
# ❌ Anti-pattern
# modules/vpc/main.tf
provider "aws" {
  region = var.region    # Forces one provider instance per module
}

# ✅ Correct
# Root module configures provider
# Module inherits from root
```

### 2. Hardcoded Values

```hcl
# ❌ Anti-pattern
resource "aws_instance" "web" {
  ami           = "ami-12345678"     # Hardcoded AMI
  instance_type = "t3.medium"        # Hardcoded size
  subnet_id     = "subnet-abc123"    # Hardcoded subnet
}

# ✅ Correct
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id     = var.subnet_id
}
```

### 3. count for Named Resources

```hcl
# ❌ Anti-pattern — removing middle item shifts indices
resource "aws_instance" "web" {
  count = 3
  # web[0] = "api", web[1] = "admin", web[2] = "worker"
  # Delete web[1] → web[2] becomes web[1] → RECREATED
}

# ✅ Correct — for_each with stable keys
resource "aws_instance" "web" {
  for_each = toset(["api", "admin", "worker"])
  # Remove "admin" → only admin deleted, others unchanged
}
```

### 4. Giant Monolith State

```hcl
# ❌ 500 resources in one state
# Plan takes 10 min, blast radius = everything

# ✅ Split by:
# - Change frequency (networking vs apps)
# - Blast radius (database separate from app)
# - Team ownership (infra team vs app team)
```

### 5. Using -target in Production

```bash
# ❌ Regular use of -target
terraform apply -target=aws_instance.web

# This skips dependency checking and can leave state inconsistent
# Only use for: debugging, emergency fixes, initial PoC

# ✅ Always apply entire configuration in production
terraform apply
```

### 6. terraform taint (Deprecated)

```bash
# ❌ Deprecated
terraform taint aws_instance.web

# ✅ Use replace instead
terraform apply -replace=aws_instance.web
```

---

## Drift Detection Automation

### GitHub Actions Drift Check

```yaml
name: Terraform Drift Detection
on:
  schedule:
    - cron: '0 8 * * 1-5'  # Weekdays 8am
  workflow_dispatch: {}

jobs:
  drift-check:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, prod]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - name: Init
        working-directory: environments/${{ matrix.environment }}
        run: terraform init -input=false

      - name: Plan
        id: plan
        working-directory: environments/${{ matrix.environment }}
        run: |
          set +e
          terraform plan -detailed-exitcode -no-color -out=drift.plan 2>&1 | tee plan.txt
          echo "exitcode=$?" >> $GITHUB_OUTPUT
        continue-on-error: true

      - name: Alert on Drift
        if: steps.plan.outputs.exitcode == '2'
        run: |
          echo "::warning::Drift detected in ${{ matrix.environment }}"
          # Send Slack/email notification here
```

### Drift Report Template

```markdown
# Terraform Drift Report

**Date:** YYYY-MM-DD
**Environment:** prod
**Detected by:** Scheduled CI job

## Drifted Resources

| Resource | Attribute | Expected | Actual | Severity |
|----------|-----------|----------|--------|----------|
| aws_instance.web | instance_type | t3.medium | t3.xlarge | HIGH |
| aws_sg.web | ingress[1] | (none) | port 3306 open | CRITICAL |

## Investigation

- CloudTrail shows manual change by user X at timestamp Y
- Change was made to handle emergency traffic spike

## Recommended Action

- [ ] Update code to match reality (if change is permanent)
- [ ] Apply to revert (if change was temporary)
- [ ] Create follow-up ticket for proper IaC change

## Prevention

- [ ] Review IAM policies to restrict console access
- [ ] Add drift detection alert to Slack channel
```

---

## Terraform Import Reference

### Import Workflow

```hcl
# Step 1: Write HCL for the existing resource
resource "docker_container" "existing" {
  name  = "existing-container"
  image = "nginx:alpine"
  # ... other attributes
}

# Step 2: Add import block
import {
  to = docker_container.existing
  id = "<container_id>"
}
```

```bash
# Step 3: Plan — kiểm tra khác biệt; generate config khởi đầu nếu cần
terraform plan -generate-config-out=generated.tf

# Output shows what's different between code and reality

# Step 4: Update HCL to match reality
# Fix any attribute mismatches

# Step 5: Lưu plan đã review và apply đúng plan đó
terraform plan -out=import.tfplan
terraform apply import.tfplan

# Step 6: Commit
git add . && git commit -m "Import existing container into Terraform"
```

### Traditional Import Command

```bash
# Vẫn hợp lệ cho break-glass/migration thủ công, nhưng khó review trong CI/CD hơn
terraform import <resource_address> <resource_id>
terraform plan
```

Ưu tiên `import` block cho workflow team thông thường vì thao tác import được version cùng configuration.

