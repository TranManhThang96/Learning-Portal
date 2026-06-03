# Day 5 - Reference Document: Remote Backend với S3 + DynamoDB

---

## 1. S3 Backend - Đầy đủ Configuration Options

```hcl
terraform {
  backend "s3" {
    # ── BẮT BUỘC ────────────────────────────────────────────────────────────
    bucket = "my-company-terraform-state"        # Tên S3 bucket
    key    = "path/to/terraform.tfstate"         # Object key trong bucket
    region = "ap-southeast-1"                    # Region của bucket

    # ── STRONGLY RECOMMENDED ────────────────────────────────────────────────
    dynamodb_table = "terraform-state-lock"      # DynamoDB table cho locking
    encrypt        = true                        # Encrypt state at rest (AES-256)

    # ── AUTHENTICATION (chọn một trong các cách) ────────────────────────────
    # Cách 1: Dùng AWS profile (local dev)
    # profile = "my-aws-profile"

    # Cách 2: Dùng IAM role (CI/CD, EC2, ECS)
    # role_arn = "arn:aws:iam::123456789012:role/TerraformStateRole"

    # Cách 3: Dùng environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    # Không cần config gì thêm - Terraform tự detect

    # ── ENCRYPTION NÂNG CAO ─────────────────────────────────────────────────
    # Dùng KMS Customer Managed Key thay vì AWS managed
    # kms_key_id = "arn:aws:kms:ap-southeast-1:123456789012:key/abc-123"

    # ── WORKSPACE SUPPORT ───────────────────────────────────────────────────
    # Prefix cho Terraform workspaces (nếu dùng workspace feature)
    # workspace_key_prefix = "workspaces"
    # Key sẽ thành: workspaces/{workspace_name}/path/to/terraform.tfstate

    # ── ADVANCED / TROUBLESHOOTING ──────────────────────────────────────────
    # Tắt force path style (mặc định false cho AWS, true cho LocalStack)
    # force_path_style = false

    # Custom endpoint (cho LocalStack hoặc S3-compatible storage)
    # endpoints {
    #   s3       = "http://localhost:4566"
    #   dynamodb = "http://localhost:4566"
    # }

    # Skip validation (chỉ dùng cho testing / LocalStack)
    # skip_credentials_validation = true
    # skip_metadata_api_check     = true
    # skip_requesting_account_id  = true
  }
}
```

---

## 2. DynamoDB Lock Table - Specification

### Cấu trúc bắt buộc

```hcl
resource "aws_dynamodb_table" "terraform_state_lock" {
  name         = "terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"   # Không cần provisioned capacity cho low traffic

  # Bắt buộc: primary key phải là "LockID" kiểu String
  hash_key = "LockID"

  attribute {
    name = "LockID"
    type = "S"   # String
  }

  # Optional: Point-in-time recovery nếu cần audit trail đầy đủ
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Purpose   = "terraform-state-locking"
    ManagedBy = "terraform"
  }
}
```

### Lock Record Format

Khi Terraform giữ lock, DynamoDB record trông như sau:

```json
{
  "LockID": {
    "S": "my-company-terraform-state/platform/vpc/terraform.tfstate"
  },
  "Digest": {
    "S": "abc123..."
  },
  "Info": {
    "S": "{\"ID\":\"uuid-here\",\"Operation\":\"OperationTypeApply\",\"Info\":\"\",\"Who\":\"engineer@machine\",\"Version\":\"1.6.0\",\"Created\":\"2024-01-15T10:30:00.000Z\",\"Path\":\"my-company-terraform-state/...\"}"
  }
}
```

---

## 3. S3 Backend Security Checklist

Sử dụng checklist này trước khi dùng S3 bucket trong production:

### Bucket Configuration

- [ ] **Versioning enabled** - Bắt buộc để rollback state
  ```bash
  aws s3api get-bucket-versioning --bucket <bucket-name>
  # Expected: {"Status": "Enabled"}
  ```

- [ ] **Server-side encryption enabled** - AES-256 hoặc KMS
  ```bash
  aws s3api get-bucket-encryption --bucket <bucket-name>
  # Expected: SSEAlgorithm: AES256 hoặc aws:kms
  ```

- [ ] **Public access blocked hoàn toàn** - Cả 4 settings
  ```bash
  aws s3api get-public-access-block --bucket <bucket-name>
  # Expected: tất cả đều true
  ```

- [ ] **Bucket policy deny non-SSL** - Enforce HTTPS
  ```bash
  aws s3api get-bucket-policy --bucket <bucket-name>
  # Check: Có Statement với "aws:SecureTransport": "false" và Effect: Deny
  ```

- [ ] **Access logging enabled** (Production recommendation)
  ```bash
  aws s3api get-bucket-logging --bucket <bucket-name>
  ```

- [ ] **Lifecycle policy** để expire old versions (cost control)
  ```hcl
  resource "aws_s3_bucket_lifecycle_configuration" "state_lifecycle" {
    bucket = aws_s3_bucket.terraform_state.id

    rule {
      id     = "expire-old-state-versions"
      status = "Enabled"

      noncurrent_version_expiration {
        noncurrent_days = 90  # Giữ 90 ngày version history
      }
    }
  }
  ```

### IAM Permissions

- [ ] **Least privilege principle** - Chỉ cấp permissions cần thiết
- [ ] **Separate roles per environment** - Dev role không touch prod bucket
- [ ] **No wildcard Resource** trong IAM policy
- [ ] **CI/CD dùng IAM Role** thay vì long-lived access keys
- [ ] **MFA Delete** trên bucket production (ngăn xóa versions vô tình)

### IAM Policy Template (Minimum Required)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformStateAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-company-terraform-state/platform/*"
    },
    {
      "Sid": "TerraformStateListing",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketVersioning"
      ],
      "Resource": "arn:aws:s3:::my-company-terraform-state"
    },
    {
      "Sid": "TerraformStateLocking",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:ap-southeast-1:*:table/terraform-state-lock"
    }
  ]
}
```

### Bucket Policy Template (Enforce HTTPS + Deny Public)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonSSL",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::my-company-terraform-state",
        "arn:aws:s3:::my-company-terraform-state/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "AllowTerraformRole",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/TerraformStateRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::my-company-terraform-state",
        "arn:aws:s3:::my-company-terraform-state/*"
      ]
    }
  ]
}
```

---

## 4. Backend Options - Comparison Matrix

| Feature               | local        | S3+DynamoDB      | GCS              | Azure Blob       | Terraform Cloud  | Consul           |
|-----------------------|--------------|------------------|------------------|------------------|------------------|------------------|
| **State storage**     | Filesystem   | S3               | GCS              | Azure Blob       | HCP Terraform    | Consul KV        |
| **Locking**           | Không        | DynamoDB         | Native           | Native           | Native           | Native           |
| **Versioning**        | Không        | S3 Versioning    | GCS Versioning   | Blob Versioning  | Built-in         | Không mặc định  |
| **Encryption**        | Không        | SSE / KMS        | CMEK             | Azure Keys       | Built-in         | Tuỳ config       |
| **Setup complexity**  | Không cần    | Trung bình       | Thấp             | Thấp             | Thấp             | Cao              |
| **Cost**              | Miễn phí     | < $1/month       | < $1/month       | < $1/month       | Free / $20+/user | Consul cluster   |
| **Cloud provider**    | Any          | AWS              | GCP              | Azure            | Any              | Any              |
| **UI/Dashboard**      | Không        | S3 Console       | GCS Console      | Azure Portal     | Có               | Có               |
| **Policy enforcement**| Không        | IAM              | IAM              | Azure RBAC       | Sentinel         | ACL              |
| **Team features**     | Không        | Custom           | Custom           | Custom           | Built-in         | Custom           |
| **Audit logs**        | Không        | CloudTrail       | Cloud Audit      | Azure Monitor    | Built-in         | Custom           |
| **Phù hợp cho**       | Solo / learn | AWS teams        | GCP teams        | Azure teams      | Multi-cloud/SaaS | HashiCorp stack  |

### Decision Tree - Chọn Backend nào?

```
Bạn đang dùng cloud provider nào?
│
├── AWS → Dùng S3 + DynamoDB (gold standard)
│
├── GCP → Dùng GCS (locking built-in, không cần extra service)
│
├── Azure → Dùng Azure Blob Storage
│
├── Multi-cloud / không muốn tự manage → Terraform Cloud / HCP Terraform
│
└── On-premises / self-hosted → Consul hoặc HTTP backend
```

---

## 5. Key Naming Conventions

### Convention 1 - Flat structure (simple teams)

```
{environment}/{component}/terraform.tfstate

prod/vpc/terraform.tfstate
prod/eks/terraform.tfstate
prod/rds/terraform.tfstate
staging/vpc/terraform.tfstate
```

### Convention 2 - Hierarchical structure (large teams)

```
{team}/{environment}/{component}/terraform.tfstate

platform/prod/networking/terraform.tfstate
platform/prod/kubernetes/terraform.tfstate
platform/staging/networking/terraform.tfstate
services/auth/prod/terraform.tfstate
services/auth/staging/terraform.tfstate
services/payment/prod/terraform.tfstate
```

### Convention 3 - Account-scoped (multiple AWS accounts)

```
{account-alias}/{region}/{environment}/{component}/terraform.tfstate

production-account/ap-southeast-1/prod/networking/terraform.tfstate
staging-account/ap-southeast-1/staging/networking/terraform.tfstate
```

**Rule of thumb:** Key convention phải phản ánh cấu trúc tổ chức team và ownership của infrastructure.

---

## 6. terraform init Flags liên quan đến Backend

| Flag                      | Mô tả                                                                    | Khi nào dùng                                    |
|---------------------------|--------------------------------------------------------------------------|-------------------------------------------------|
| `terraform init`          | Initialize với backend config trong file                                 | Lần đầu, hoặc sau khi thêm provider mới        |
| `terraform init -migrate-state` | Migrate state từ backend cũ sang backend mới                      | Thay đổi backend type hoặc location            |
| `terraform init -reconfigure` | Reinitialize với config mới, bỏ qua migration prompt               | Reset backend config về trạng thái mới         |
| `terraform init -backend=false` | Skip backend initialization                                       | Chỉ install providers, không cần backend       |
| `terraform init -backend-config=file.hcl` | Load backend config từ file riêng (partial config)     | Tách backend config sensitive ra file riêng    |

### Partial Backend Configuration

Useful khi muốn giữ bucket name, region riêng khỏi code (ví dụ: để reuse cho nhiều environments):

File `backend.tf` (commit vào repo):
```hcl
terraform {
  backend "s3" {
    # Chỉ đặt non-sensitive, non-environment-specific config ở đây
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

File `prod.hcl` (không commit, hoặc per-environment):
```hcl
bucket = "my-company-terraform-state-prod"
key    = "platform/networking/terraform.tfstate"
region = "ap-southeast-1"
```

Run:
```bash
terraform init -backend-config=prod.hcl
```

---

## 7. State Migration Checklist

Trước khi migrate state từ local sang remote (hoặc từ remote backend A sang B):

- [ ] Backup state file hiện tại: `cp terraform.tfstate terraform.tfstate.$(date +%Y%m%d-%H%M%S).backup`
- [ ] Verify không có pending changes: `terraform plan` phải ra "No changes"
- [ ] Không có ai đang chạy `apply` cùng lúc
- [ ] Target backend đã được tạo và accessible (S3 bucket exists, DynamoDB table exists)
- [ ] IAM permissions đủ để write vào backend mới
- [ ] Test connection: `aws s3 ls s3://bucket-name/` phải thành công
- [ ] Run `terraform init -migrate-state`
- [ ] Verify sau migrate: `terraform plan` phải ra "No changes"
- [ ] Giữ backup local state ít nhất 24h trước khi xóa

---

## 8. Troubleshooting Quick Reference

| Error                                              | Nguyên nhân                                      | Fix                                                            |
|----------------------------------------------------|--------------------------------------------------|----------------------------------------------------------------|
| `NoSuchBucket`                                     | Bucket chưa tạo hoặc sai region                 | Tạo bucket / fix region trong backend config                  |
| `ResourceNotFoundException` (DynamoDB)             | DynamoDB table chưa tạo                         | Tạo table với hash_key "LockID" (String)                      |
| `AccessDenied` hoặc `AccessDeniedException`       | IAM permissions thiếu                           | Check và add permissions theo section 3 ở trên               |
| `Error acquiring the state lock`                   | Lock đang held bởi process khác                 | Chờ process kia xong, hoặc `force-unlock` nếu process crashed |
| `state data in S3 does not have the expected content` | State file bị corrupt hoặc sai format      | Restore version cũ từ S3 versioning                           |
| `Backend configuration changed`                    | Backend config thay đổi nhưng chưa chạy init   | `terraform init -reconfigure` hoặc `-migrate-state`          |
| `Failed to load state: AccessDenied`               | Không có quyền đọc state trong S3               | Check GetObject permission cho key path cụ thể               |
| `BucketAlreadyExists` khi tạo bucket              | Bucket name đã tồn tại (global namespace)       | Dùng tên unique hơn: thêm account-id hoặc random suffix      |
