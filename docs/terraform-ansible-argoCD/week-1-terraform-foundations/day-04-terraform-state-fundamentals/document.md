# Day 4 - Document: Terraform State Reference

> Cheat sheet và reference guide cho Terraform State. Dùng song song khi lab và khi làm việc thực tế.

---

## 1. terraform state Commands Cheat Sheet

### Read-only commands (an toàn, không thay đổi state)

```bash
# List tất cả resources trong state
terraform state list

# List resources trong một module cụ thể
terraform state list module.vpc

# List resources của một type cụ thể (dùng grep)
terraform state list | grep aws_instance

# Xem chi tiết một resource
terraform state show <resource_address>
terraform state show aws_instance.web
terraform state show module.vpc.aws_subnet.public[0]

# Pull state từ remote về (in ra stdout)
terraform state pull

# Pull và save vào file
terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate

# Xem serial và lineage của state
terraform state pull | jq '{serial: .serial, lineage: .lineage}'

# List tất cả resource types đang dùng
terraform state pull | jq '[.resources[].type] | unique | sort'
```

### Write commands (LUÔN backup state trước)

```bash
# Rename/move resource trong state
terraform state mv <source> <destination>

# Examples:
terraform state mv aws_instance.web aws_instance.app
terraform state mv aws_instance.web module.app.aws_instance.web
terraform state mv module.old.aws_s3_bucket.data module.new.aws_s3_bucket.data

# Move resource với for_each (dùng quotes để escape brackets)
terraform state mv 'aws_instance.web["us-east-1"]' 'aws_instance.web["us-west-2"]'

# Xóa resource khỏi state (resource vẫn tồn tại trên infrastructure)
terraform state rm <resource_address>
terraform state rm aws_instance.legacy
terraform state rm module.old_vpc

# Push local state lên remote (CHỈ DÙNG KHI RECOVERY)
terraform state push <file>
terraform state push backup.tfstate
terraform state push -force backup.tfstate  # bypass serial check, cực kỳ nguy hiểm
```

### Import commands

```bash
# Bring existing resource vào Terraform management
terraform import <resource_address> <resource_id>

# Examples:
terraform import aws_instance.web i-0abc123def456789
terraform import aws_s3_bucket.data my-bucket-name
terraform import docker_container.nginx <container_id>
terraform import 'aws_instance.web["app1"]' i-0abc123def456789  # for_each
```

### Plan & Apply commands liên quan đến state

```bash
# Plan chỉ refresh state, không apply changes
terraform plan -refresh-only

# Apply refresh-only (cập nhật state theo real world, không thay đổi infrastructure)
terraform apply -refresh-only

# Apply không refresh state từ real world (faster, riskier)
terraform apply -refresh=false

# Target specific resource (hữu ích khi troubleshoot)
terraform apply -target=aws_instance.web
terraform apply -target=module.vpc

# Force unlock bị stuck lock
terraform force-unlock <lock_id>
```

### Workspace commands

```bash
# List workspaces
terraform workspace list

# Show current workspace
terraform workspace show

# Create workspace mới
terraform workspace new <name>
terraform workspace new staging

# Switch workspace
terraform workspace select <name>
terraform workspace select production

# Delete workspace (XÓA CẢ STATE!)
terraform workspace delete <name>
# WARNING: Chỉ delete khi workspace đã empty (đã destroy tất cả resources)
```

---

## 2. State File Field Reference

```
terraform.tfstate
├── version          : Integer - State format version (hiện tại là 4)
├── terraform_version: String  - Terraform version tạo state này
├── serial           : Integer - Tăng sau mỗi state mutation; dùng để detect conflicts
├── lineage          : UUID    - Gắn với state file từ khi init; phòng tránh mix state files
├── outputs          : Object  - output values từ configuration
│   └── <name>
│       ├── value    : Any     - Giá trị thực tế
│       ├── type     : String  - Terraform type (string, number, bool, list, map, ...)
│       └── sensitive: Bool    - Nếu true, value được redact khi print
└── resources        : Array   - Tất cả managed resources
    └── [resource]
        ├── mode     : String  - "managed" hoặc "data"
        ├── type     : String  - Resource type (aws_instance, docker_container, ...)
        ├── name     : String  - Resource name từ code
        ├── provider : String  - Provider address đầy đủ
        ├── module   : String  - Module path (nếu trong module)
        └── instances: Array
            └── [instance]
                ├── schema_version    : Integer - Provider schema version
                ├── index_key         : String/Int - Key khi dùng count/for_each
                ├── attributes        : Object  - TẤT CẢ attributes, kể cả computed
                ├── sensitive_attributes: Array - Paths đến sensitive values
                ├── private           : Base64  - Internal provider data
                └── dependencies      : Array   - Resource addresses phụ thuộc vào
```

---

## 3. State Troubleshooting Guide

### Problem: "Error acquiring the state lock"

```
Error: Error acquiring the state lock
  Lock Info:
    ID:        abc123-...
    Path:      s3://my-bucket/terraform.tfstate
    Operation: OperationTypeApply
    Who:       user@hostname
    Version:   1.x.x
    Created:   2024-01-01 10:00:00
    Info:
```

**Nguyên nhân:**
- Terraform apply đang chạy trên máy khác / pipeline khác.
- Apply bị interrupt (mất kết nối, Ctrl+C) mà không release lock.

**Giải quyết:**
```bash
# Bước 1: Verify không ai đang apply thật sự
# Hỏi team, kiểm tra CI/CD pipeline

# Bước 2: Nếu chắc chắn lock bị stuck, force unlock
terraform force-unlock abc123-...

# Bước 3: Verify state còn nguyên trước khi tiếp tục
terraform plan
```

---

### Problem: State corrupt / "Invalid JSON"

**Dấu hiệu:**
```
Error: Failed to load state: state snapshot was created by Terraform
       vX.Y.Z, which is newer than current v1.x.x
```
hoặc:
```
Error: Failed to load state: invalid character 'x' looking for beginning of value
```

**Giải quyết:**
```bash
# Option 1: Restore từ S3 versioning (remote backend)
# Vào S3 console, tìm version trước của state file, restore

# Option 2: Restore từ backup local
terraform state push terraform.tfstate.backup

# Option 3: Nếu có manual backup
terraform state push backup-20240101-120000.tfstate

# Option 4: Merge từ partial state (advanced)
# Cần đọc hiểu state JSON format và merge thủ công
```

---

### Problem: "Resource already exists" khi apply

```
Error: Error creating Instance: InvalidInstanceID.AlreadyExists
```

**Nguyên nhân:** Resource đã tồn tại trên infrastructure nhưng không có trong state.

**Giải quyết:**
```bash
# Import resource vào state
terraform import aws_instance.web i-0abc123def456789

# Verify
terraform state show aws_instance.web

# Plan để check không có unexpected changes
terraform plan
```

---

### Problem: "Resource not found" khi state mv

```
Error: Instance not found in state
```

**Giải quyết:**
```bash
# Verify resource address đúng
terraform state list | grep <name>

# Dùng đúng address (case-sensitive)
terraform state mv docker_container.Web docker_container.web
# Không phải "Web", phải là "web" (exact match với code)

# Với for_each, cần quote
terraform state list | grep instance
# aws_instance.web["app1"]
terraform state mv 'aws_instance.web["app1"]' 'aws_instance.app["app1"]'
```

---

### Problem: State drift sau auto-scaling

**Nguyên nhân:** AWS Auto Scaling Group thay đổi số lượng instance, Terraform không biết.

**Giải quyết:**
```bash
# Refresh state để reflect real world
terraform apply -refresh-only

# Hoặc dùng lifecycle ignore_changes trong code:
resource "aws_autoscaling_group" "app" {
  ...
  lifecycle {
    ignore_changes = [desired_capacity]
  }
}
```

---

### Problem: `terraform plan` luôn show changes dù không đổi gì

**Nguyên nhân phổ biến:**
1. Provider version update → thay đổi default values.
2. Sensitive value comparison issue.
3. Ordering của lists/sets khác nhau giữa state và API response.

**Debug:**
```bash
# Xem chi tiết thay đổi
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan | jq '.resource_changes[] | select(.change.actions != ["no-op"])'

# Check provider version
cat .terraform.lock.hcl

# Thử upgrade provider
terraform init -upgrade
terraform plan
```

---

### Problem: Workspace nhầm (apply vào sai environment)

**Prevention:**
```bash
# Luôn check workspace trước khi apply
terraform workspace show

# Thêm vào CI/CD script:
CURRENT_WS=$(terraform workspace show)
EXPECTED_WS=${ENVIRONMENT:-"default"}
if [ "$CURRENT_WS" != "$EXPECTED_WS" ]; then
  echo "ERROR: Wrong workspace! Expected $EXPECTED_WS, got $CURRENT_WS"
  exit 1
fi
```

**Recovery nếu apply nhầm workspace:**
```bash
# 1. Tìm resources đã bị tạo nhầm
terraform state list

# 2. Destroy resources trong workspace nhầm
terraform destroy -target=<resource> -target=<resource>

# 3. Switch về workspace đúng
terraform workspace select <correct_workspace>

# 4. Apply để recreate nếu cần
terraform apply
```

---

## 4. State Security Checklist

### Before project setup

- [ ] `.gitignore` đã block `*.tfstate`, `*.tfstate.backup`, `.terraform/`
- [ ] Remote backend đã được config với encryption at rest
- [ ] IAM/RBAC cho state storage đã được restrict (least privilege)
- [ ] S3 bucket versioning đã enabled (cho AWS backend)
- [ ] S3 bucket block public access đã enabled
- [ ] DynamoDB table cho locking đã tạo (AWS)
- [ ] Audit logging enabled (CloudTrail cho S3 access)

### Ongoing operations

- [ ] Không share state file qua email/Slack/chat
- [ ] State access audit log được review định kỳ
- [ ] Rotate secrets nếu state bị expose
- [ ] Periodic backup của state file ra ngoài primary storage
- [ ] Pre-commit hook chặn commit state files:

```bash
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -q '\.tfstate'; then
  echo "ERROR: Attempting to commit .tfstate file!"
  echo "Remove it from staging: git reset HEAD <file>"
  exit 1
fi
```

### State access control (AWS example)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowTerraformStateRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-terraform-state",
        "arn:aws:s3:::my-terraform-state/*"
      ]
    },
    {
      "Sid": "AllowTerraformStateWrite",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-terraform-state/prod/*",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalTag/Team": "platform"
        }
      }
    },
    {
      "Sid": "AllowStateLocking",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-lock"
    }
  ]
}
```

### Sensitive values - Best practices

```hcl
# BAD: Hard-code secret trong code
resource "aws_db_instance" "db" {
  password = "SuperSecret123!"
}

# BAD: Dùng variable nhưng không mark sensitive
variable "db_password" {}

# BETTER: Mark variable là sensitive (ẩn khỏi logs nhưng vẫn trong state)
variable "db_password" {
  type      = string
  sensitive = true
}

# BEST: Lấy từ secrets manager, không pass qua Terraform variables
data "aws_secretsmanager_secret_version" "db" {
  secret_id = "/prod/myapp/db-password"
}

resource "aws_db_instance" "db" {
  password = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)["password"]
}
# State vẫn chứa password, nhưng secret rotation không cần thay đổi Terraform code
```

---

## 5. State File Locations

| Backend | Default location | Lock mechanism |
|---------|-----------------|----------------|
| local | `./terraform.tfstate` | Không có |
| s3 | `s3://<bucket>/<key>` | DynamoDB |
| gcs | `gs://<bucket>/<prefix>/default.tfstate` | GCS Object locking |
| azurerm | Azure Blob Storage | Azure Blob lease |
| http | Custom HTTP endpoint | Custom |
| terraform cloud | Terraform Cloud servers | Built-in |
| consul | Consul KV | Consul session |
| kubernetes | Kubernetes secret | Kubernetes lease |

### State filename pattern với workspaces

```
# S3 backend
s3://bucket/path/to/terraform.tfstate           # default workspace
s3://bucket/path/to/env:/staging/terraform.tfstate  # staging workspace
s3://bucket/path/to/env:/prod/terraform.tfstate      # prod workspace

# Local backend
./terraform.tfstate                              # default workspace
./terraform.tfstate.d/staging/terraform.tfstate  # staging workspace
./terraform.tfstate.d/prod/terraform.tfstate     # prod workspace
```

---

## 6. Quick Reference: State vs Code vs Real World

```
┌───────────────┬──────────────────────────────────────────────┐
│   Situation   │   Command                                    │
├───────────────┼──────────────────────────────────────────────┤
│ Code ≠ State  │ terraform plan (xem diff)                    │
│ (desired ≠    │ terraform apply (apply changes)              │
│  tracked)     │                                              │
├───────────────┼──────────────────────────────────────────────┤
│ State ≠ Real  │ terraform plan -refresh-only (detect drift)  │
│ World (drift) │ terraform apply -refresh-only (accept drift) │
│               │ terraform apply (revert drift)               │
├───────────────┼──────────────────────────────────────────────┤
│ Real World ∉  │ terraform import (bring vào state)           │
│ State (orphan)│                                              │
├───────────────┼──────────────────────────────────────────────┤
│ State ∉ Code  │ terraform state rm (xóa khỏi state)          │
│ (removed from │ hoặc add lại vào code                        │
│  tracking)    │                                              │
└───────────────┴──────────────────────────────────────────────┘
```
