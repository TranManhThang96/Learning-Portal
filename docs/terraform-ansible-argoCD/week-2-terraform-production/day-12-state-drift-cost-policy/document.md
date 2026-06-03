# Day 12: Cheat Sheet & Reference - State Strategy, Drift, Cost, Policy

---

## 1. State Layout Quick Reference

### Decision Tree: Chọn state strategy nào?

```
Bắt đầu
  │
  ├─► Solo dev / PoC?
  │     └─► Monolithic state (1 file per env). Đủ rồi.
  │
  ├─► Small team (2-5), 1 env?
  │     └─► 1 state per env. Dùng workspace nếu env giống nhau nhiều.
  │
  ├─► Medium team (5-20), multi-env, microservices?
  │     └─► Per-env + Per-domain (foundation / data / apps)
  │
  └─► Large team, nhiều domain teams, bank/regulated?
        └─► Per-service state + Terragrunt + automated DriftBot
```

### Chuẩn state layout cho microservices platform

```
s3://company-tf-state-{account_id}/
│
├── global/                    # IAM roles, Route53 zones, CloudTrail
│   └── terraform.tfstate
│
├── {env}/                     # env = dev | staging | production
│   ├── foundation/            # VPC, subnets, NAT GW, VPN
│   │   └── terraform.tfstate
│   ├── data/                  # RDS, ElastiCache, S3 buckets, MSK
│   │   └── terraform.tfstate
│   ├── compute/               # EKS cluster, node groups, ECR
│   │   └── terraform.tfstate
│   └── apps/                  # ALB, Route53 records, security groups
│       └── terraform.tfstate
│
└── [Mỗi state có DynamoDB lock riêng hoặc dùng chung table]
```

### Dependency order (phải apply theo thứ tự)

```
global → foundation → data → compute → apps
   └──────────────────────────────────────►
                  direction of dependency
```

---

## 2. Backend Configuration Snippets

### S3 Backend (Production Standard)

```hcl
terraform {
  backend "s3" {
    bucket         = "company-tf-state-123456789"
    key            = "production/foundation/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
    # Role cho cross-account state access
    role_arn       = "arn:aws:iam::ACCOUNT_ID:role/TerraformStateRole"
  }
}
```

### Partial backend config (recommened cho multi-env)

```hcl
# main.tf - chỉ khai báo type
terraform {
  backend "s3" {}
}
```

```hcl
# backend-prod.hcl - config file riêng
bucket         = "company-tf-state-123456789"
key            = "production/foundation/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-locks"
encrypt        = true
```

```bash
# Init với config file
terraform init -backend-config=backend-prod.hcl
```

### Remote State Data Source

```hcl
# Đọc output từ state khác
data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket = "company-tf-state-123456789"
    key    = "production/foundation/terraform.tfstate"
    region = "us-east-1"
  }
}

# Dùng output
resource "aws_eks_cluster" "main" {
  vpc_config {
    subnet_ids = data.terraform_remote_state.foundation.outputs.private_subnet_ids
  }
}
```

---

## 3. Drift Detection Commands

```bash
# Check drift (đọc từ cloud, không thay đổi gì)
terraform plan -refresh-only

# Nếu muốn áp drift ngược (xóa manual change):
terraform plan -refresh-only -out=drift.tfplan
terraform apply drift.tfplan  # ⚠️ Careful: reverts manual changes

# Force unlock nếu state bị locked
terraform force-unlock LOCK_ID

# Xem ai đang lock state
terraform state list         # liệt kê resources trong state
terraform state show ADDR    # xem chi tiết 1 resource trong state
terraform state pull         # dump raw state JSON

# Import resource vào state (sau khi tạo manual)
terraform import aws_security_group.web sg-0abc123def456

# Remove resource khỏi state mà không destroy
terraform state rm aws_security_group.web
```

### Drift detection exit codes

| Exit Code | Meaning |
|-----------|---------|
| `0` | No changes, no drift |
| `1` | Error |
| `2` | Changes detected (drift or pending apply) |

```bash
# Script detect drift dựa trên exit code
terraform plan -refresh-only -detailed-exitcode
case $? in
  0) echo "Clean" ;;
  1) echo "Error" ;;
  2) echo "DRIFT DETECTED" ;;
esac
```

---

## 4. Infracost Commands

```bash
# Cài đặt
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Authenticate (lấy API key free)
infracost auth login

# Estimate từ Terraform directory
infracost breakdown --path ./terraform/production

# Estimate từ plan JSON (tốt hơn cho CI - không cần cloud credentials)
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > plan.json
infracost breakdown --path plan.json

# Output formats
infracost breakdown --path plan.json --format table    # human readable
infracost breakdown --path plan.json --format json     # for scripting
infracost breakdown --path plan.json --format html     # HTML report

# So sánh với baseline
infracost breakdown --path plan.json --format json --out-file base.json
# ... sau khi thay đổi code ...
infracost diff --path plan-new.json --compare-to base.json

# Tích hợp với GitHub PR (tự động comment)
infracost comment github \
  --path plan.json \
  --repo $GITHUB_REPOSITORY \
  --pull-request $PR_NUMBER \
  --github-token $GITHUB_TOKEN
```

### Infracost trong GitHub Actions

```yaml
- name: Setup Infracost
  uses: infracost/actions/setup@v3
  with:
    api-key: ${{ secrets.INFRACOST_API_KEY }}

- name: Generate Terraform plan JSON
  run: |
    terraform plan -out=tfplan.binary
    terraform show -json tfplan.binary > plan.json

- name: Post Infracost comment
  uses: infracost/actions/comment@v3
  with:
    path: plan.json
    behavior: update   # update existing comment instead of posting new ones
```

---

## 5. OPA/Conftest Reference

### Rego policy structure

```rego
package my.policy.name    # namespace

import future.keywords.in  # optional: modern Rego keywords

# Constants / helpers
required_tags := {"Environment", "Owner", "CostCenter"}

# DENY rules - violations that block
deny[msg] {
  # conditions
  msg := "Human-readable error message"
}

# WARN rules - warnings that don't block
warn[msg] {
  # conditions
  msg := "Advisory message"
}
```

### Terraform plan JSON structure (để viết Rego)

```json
{
  "resource_changes": [
    {
      "address": "aws_s3_bucket.my_bucket",
      "type": "aws_s3_bucket",
      "change": {
        "actions": ["create"],     // create | update | delete | no-op
        "before": null,            // null nếu create
        "after": {
          "bucket": "my-bucket",
          "tags": {
            "Environment": "prod"
          }
        }
      }
    }
  ]
}
```

### Conftest commands

```bash
# Validate plan với policies
conftest test plan.json --policy ./policies/

# Validate với specific namespace
conftest test plan.json \
  --policy ./policies/ \
  --namespace terraform.aws.security

# Validate nhiều files
conftest test plan1.json plan2.json --policy ./policies/

# Run unit tests cho policies
conftest verify --policy ./policies/

# Output formats
conftest test plan.json --policy ./policies/ --output json   # JSON output
conftest test plan.json --policy ./policies/ --output tap    # TAP format
```

### Rego policy examples

```rego
# Enforce required tags
deny[msg] {
  resource := input.resource_changes[_]
  resource.change.actions[_] == "create"
  startswith(resource.type, "aws_")

  required_tag := required_tags[_]
  not resource.change.after.tags[required_tag]

  msg := sprintf("Missing tag '%s' on %s", [required_tag, resource.address])
}

# No public RDS
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_db_instance"
  resource.change.actions[_] == "create"
  resource.change.after.publicly_accessible == true

  msg := sprintf("RDS '%s' must not be publicly accessible", [resource.address])
}

# Instance type restriction per environment
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_instance"
  resource.change.actions[_] == "create"

  env := resource.change.after.tags["Environment"]
  env == "dev"

  allowed_types := {"t3.micro", "t3.small", "t3.medium"}
  instance_type := resource.change.after.instance_type
  not allowed_types[instance_type]

  msg := sprintf(
    "Dev environment only allows t3.micro/small/medium. Got: %s on %s",
    [instance_type, resource.address]
  )
}
```

---

## 6. Sentinel Overview (HashiCorp Terraform Cloud)

### Sentinel policy trong Terraform Cloud

```python
# sentinel.hcl - khai báo policies
policy "require-tags" {
  source            = "./policies/require-tags.sentinel"
  enforcement_level = "hard-mandatory"  # hard-mandatory | soft-mandatory | advisory
}

policy "restrict-instance-types" {
  source            = "./policies/restrict-instance-types.sentinel"
  enforcement_level = "soft-mandatory"
}
```

```python
# policies/require-tags.sentinel
import "tfplan/v2" as tfplan

# Required tags
required_tags = ["Environment", "Owner"]

# Lấy tất cả resources
all_resources = filter tfplan.resource_changes as addr, rc {
  rc.mode is "managed" and
  (rc.change.actions contains "create" or rc.change.actions contains "update")
}

# Check tags
violations = filter all_resources as addr, rc {
  all required_tags as tag {
    not (rc.change.after.tags[tag] else false)
  }
}

main = rule {
  length(violations) is 0
}
```

### Enforcement levels

| Level | Behavior |
|-------|----------|
| `advisory` | Warn only, không block apply |
| `soft-mandatory` | Block apply, nhưng user có thể override |
| `hard-mandatory` | Block apply, không thể override |

---

## 7. Comparison Tables

### State Split Approaches

| Approach | Blast Radius | Plan Speed | Team Isolation | Complexity |
|----------|-------------|------------|----------------|------------|
| Monolithic | Toàn infra | Chậm (tất cả refresh) | Không | Thấp |
| Per-env | Per env | Trung bình | Không (same team) | Thấp |
| Per-env + Domain | Per domain | Nhanh | Có | Trung bình |
| Per-service | Per service | Rất nhanh | Có | Cao |

### Remote State vs SSM vs Hardcode

| Method | Maintainability | Type Safety | Cross-team | Non-TF Consumers |
|--------|----------------|------------|------------|-----------------|
| Hardcode | Thấp | N/A | Không | Không |
| Remote State | Trung bình | Cao | Khó | Không |
| SSM Parameter | Cao | Không (string) | Dễ | Có |
| Consul/Vault | Cao | Có | Dễ | Có |

### Policy Enforcement Tools

| Tool | Language | Integration | Cost | Learning Curve |
|------|----------|-------------|------|---------------|
| OPA + Conftest | Rego | CI/CD, pre-commit | Free | Cao |
| Sentinel | Sentinel DSL | Native TFC/TFE | TFC/TFE plan | Trung bình |
| Checkov | Python | CI/CD | Free | Thấp |
| tfsec | Go rules | CI/CD | Free | Thấp |
| OPA Gatekeeper | Rego | Kubernetes | Free | Cao |

---

## 8. Common State Operations

### Move resource giữa states (khi refactor)

```bash
# Step 1: Export resource từ source state
terraform state pull > source-state-backup.json

# Step 2: Remove resource khỏi source state (không destroy)
terraform state rm aws_vpc.main

# Step 3: Trong target state directory, import resource
terraform import aws_vpc.main vpc-0abc123def456789

# Hoặc dùng `terraform state mv` cho cùng state file
terraform state mv \
  module.old_name.aws_vpc.main \
  module.new_name.aws_vpc.main
```

### Rename resource trong state

```bash
# Rename mà không destroy/recreate
terraform state mv \
  aws_security_group.web_sg \
  aws_security_group.web
```

### Xem state hiện tại

```bash
terraform state list                          # List all resources
terraform state show aws_vpc.main             # Show specific resource
terraform state pull | jq '.resources[]'      # Raw JSON
```

---

## 9. CI/CD Integration Checklist

```
PR Opened
    │
    ├── terraform fmt -check ────────────────── fail if formatting off
    ├── terraform validate ───────────────────── fail if syntax error
    ├── terraform plan ───────────────────────── generate plan
    │
    ├── conftest test plan.json ──────────────── fail if policy violation
    │
    ├── infracost diff ───────────────────────── post cost comment
    │   (vs main branch baseline)
    │
    └── human review required ─────────────────►
                                                │
PR Merged to Main                               │
    │                                           │
    ├── terraform plan (again) ◄────────────────┘
    ├── manual approval (prod) ──────────────── required for production
    └── terraform apply ────────────────────── deploy

Scheduled (Daily)
    └── terraform plan -refresh-only ────────── drift detection
        └── if exit 2: alert Slack + create ticket
```

---

## 10. Troubleshooting Quick Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `Error acquiring the state lock` | Another process locked state | Wait or `terraform force-unlock LOCK_ID` |
| `Failed to read remote state` | Wrong backend config or permissions | Check bucket/key/IAM policy |
| `output not found` | Remote state output renamed/deleted | Check outputs.tf in source state |
| `Provider configuration not present` | Missing provider in remote state consumer | Add provider block in consumer |
| `Cannot import non-existent remote object` | Resource doesn't exist in cloud | Create resource first or check IDs |
| Conftest: `no policies found` | Wrong policy path or no `.rego` files | Check `--policy` path |
| Infracost: `No valid Terraform files found` | Wrong path or no plan.json | Pass `--path plan.json` with plan JSON |
