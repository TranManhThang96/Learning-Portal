# Day 5: Remote Backend với S3 + DynamoDB

**Thời gian:** 2 giờ | **Level:** Intermediate | **Prerequisites:** Day 1-4

---

## Mục tiêu ngày học

Sau buổi học này, bạn có thể:

1. Giải thích tại sao local state không phù hợp cho môi trường team và liệt kê ít nhất 3 loại sự cố thực tế
2. Cấu hình S3 backend với DynamoDB locking cho một Terraform project từ đầu
3. Giải quyết bài toán bootstrap (tạo S3/DynamoDB trước khi Terraform có thể dùng chúng)
4. Migrate state từ local sang remote backend mà không mất dữ liệu
5. Thiết kế chiến lược backend isolation theo environment cho một microservices platform

---

## Bối cảnh thực tế

### Chuyện xảy ra khi team dùng local state

Bạn đang build một microservices platform. Team có 5 engineers. Mỗi người clone repo về và chạy `terraform apply` trên máy mình.

**Incident 1 - State conflict:**
Thứ Hai sáng. Engineer A và Engineer B cùng lúc chạy `terraform apply` để deploy một thay đổi nhỏ. Không có locking. Cả hai đều thành công trên máy mình. Nhưng infrastructure thực tế bị corrupt - một số resource bị duplicate, một số bị delete. RDS instance của staging environment xuống. Mất 3 tiếng để restore.

**Incident 2 - State loss:**
Engineer C format lại laptop. File `terraform.tfstate` trên máy mất. Team không biết Terraform đang quản lý những resource nào nữa. Chạy `terraform plan` ra toàn bộ resource bị mark là "will be created" - nhưng chúng đang chạy trên AWS. Nếu ai đó apply lúc này, toàn bộ infrastructure bị recreate. Downtime production.

**Incident 3 - Stale state:**
Engineer D apply trên máy mình và update state trên local. Engineer E không biết, apply lại từ một commit cũ hơn với state cũ. Kết quả: một số Security Group rules bị rollback, application không kết nối được database. Alert lúc 2 giờ sáng.

### Với microservices platform teams

Platform team thường quản lý:
- VPC, subnets, security groups (networking layer)
- EKS/GKE cluster (compute layer)
- RDS, ElastiCache (data layer)
- IAM roles, policies (security layer)
- S3 buckets, CloudFront (storage/CDN layer)

Mỗi layer có thể có nhiều engineer touch vào. Remote backend với locking là điều kiện bắt buộc, không phải optional.

---

## Kiến thức nền tảng - 30 phút

### 1. Remote Backend là gì và tại sao cần nó

Day 4 đã cover state fundamentals. Bạn biết state file lưu mapping giữa Terraform config và real infrastructure. Vấn đề: local state chỉ phù hợp cho một người làm việc một mình.

Remote backend giải quyết 3 vấn đề:

```
Local State (vấn đề)          Remote Backend (giải pháp)
─────────────────────         ─────────────────────────
File trên máy cá nhân    →    Centralized storage (S3, GCS, etc.)
Không có locking         →    Distributed lock (DynamoDB)
Không có audit trail     →    Versioning + access logs
```

Terraform hỗ trợ nhiều backend type. S3 + DynamoDB là combination phổ biến nhất cho AWS workloads và đây là những gì bạn sẽ dùng trong thực tế.

### 2. S3 Backend Configuration - Chi tiết

Đây là một S3 backend configuration đầy đủ, production-ready:

```hcl
# backend.tf
terraform {
  backend "s3" {
    # S3 bucket để lưu state file
    bucket = "my-company-terraform-state"
    key    = "platform/vpc/terraform.tfstate"
    region = "ap-southeast-1"

    # DynamoDB table để locking
    dynamodb_table = "terraform-state-lock"

    # Encryption at rest
    encrypt = true

    # Server-side encryption key (optional, dùng AWS managed key nếu bỏ)
    # kms_key_id = "arn:aws:kms:..."

    # Profile AWS (optional, dùng IAM role nếu chạy trên EC2/ECS)
    # profile = "my-aws-profile"

    # Workspace prefix (nếu dùng Terraform workspaces)
    # workspace_key_prefix = "workspaces"
  }
}
```

**Cấu trúc `key`:** Đây là path bên trong S3 bucket. Convention phổ biến:

```
{team}/{component}/{env}/terraform.tfstate

Ví dụ:
platform/networking/prod/terraform.tfstate
platform/networking/staging/terraform.tfstate
platform/eks-cluster/prod/terraform.tfstate
services/auth-service/prod/terraform.tfstate
```

### 3. DynamoDB Lock Table - Cơ chế hoạt động

DynamoDB được dùng để implement distributed locking. Table này chỉ cần một primary key:

```
Table name: terraform-state-lock
Primary key: LockID (String)
```

**Quy trình locking:**

```
Engineer A chạy terraform apply
         │
         ▼
Terraform ghi lock record vào DynamoDB
  LockID = "my-bucket/platform/vpc/terraform.tfstate"
  Info    = { Who: "engineer-a", When: "...", Operation: "apply" }
         │
         ▼
Engineer B cùng lúc chạy terraform apply
         │
         ▼
Terraform cố ghi lock record → DynamoDB từ chối
  (LockID đã tồn tại)
         │
         ▼
Engineer B nhận thông báo:
  "Error acquiring the state lock:
   Lock Info: ID=..., Path=..., Who=engineer-a@laptop..."
         │
         ▼
Engineer B phải chờ Engineer A xong
         │
Engineer A hoàn thành apply
         │
         ▼
Terraform xóa lock record khỏi DynamoDB
         │
         ▼
Engineer B có thể chạy bây giờ
```

**Lock bị stuck:** Nếu Terraform crash giữa chừng, lock có thể không được release. Dùng lệnh:

```bash
terraform force-unlock <LOCK_ID>
```

Lấy LOCK_ID từ error message. Dùng cẩn thận - chỉ dùng khi bạn chắc chắn không có operation nào đang chạy.

### 4. Bootstrap Problem - Bài toán con gà và quả trứng

Đây là vấn đề thú vị: bạn cần S3 bucket để lưu Terraform state, nhưng bạn dùng Terraform để tạo S3 bucket. Vậy lần đầu tiên bạn làm gì?

```
Vấn đề:
┌─────────────────┐         ┌─────────────────┐
│  Terraform cần  │         │   S3 bucket     │
│  S3 để lưu     │ ──────► │   cần được tạo  │
│  state          │         │   bởi Terraform │
└─────────────────┘         └─────────────────┘
         ▲                           │
         └───────────────────────────┘
                  Circular dependency!
```

**Giải pháp 1 - Manual tạo (đơn giản nhất):**

```bash
# Tạo S3 bucket
aws s3api create-bucket \
  --bucket my-company-terraform-state \
  --region ap-southeast-1 \
  --create-bucket-configuration LocationConstraint=ap-southeast-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket my-company-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket my-company-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket my-company-terraform-state \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Tạo DynamoDB table
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

**Giải pháp 2 - Separate bootstrap Terraform project:**

```
terraform-bootstrap/        ← Dùng local backend, chỉ chạy một lần
  main.tf                   ← Tạo S3 bucket + DynamoDB
  outputs.tf                ← Output bucket name, table name

platform/                   ← Dùng remote backend (S3 vừa tạo ở trên)
  backend.tf
  main.tf
  ...
```

Bootstrap project dùng local state (vì chưa có remote backend). Sau khi chạy xong, bạn có S3 và DynamoDB. Các project khác dùng remote backend trỏ vào S3 đó.

**Giải pháp 3 - CloudFormation / AWS CDK:**
Dùng CloudFormation để tạo S3 + DynamoDB. CloudFormation có state management riêng, không phụ thuộc Terraform.

### 5. Backend per Environment Strategy

Hai pattern phổ biến:

**Pattern A - Một bucket, nhiều key (key prefix isolation):**

```
Bucket: my-company-terraform-state
├── platform/networking/dev/terraform.tfstate
├── platform/networking/staging/terraform.tfstate
├── platform/networking/prod/terraform.tfstate
├── platform/eks/dev/terraform.tfstate
├── platform/eks/staging/terraform.tfstate
└── platform/eks/prod/terraform.tfstate
```

Ưu điểm: Đơn giản, ít bucket phải quản lý.
Nhược điểm: Một IAM policy lỗi có thể ảnh hưởng nhiều environment. Khó isolate permissions.

**Pattern B - Mỗi environment một bucket:**

```
my-company-tf-state-dev/
  platform/networking/terraform.tfstate
  platform/eks/terraform.tfstate

my-company-tf-state-staging/
  platform/networking/terraform.tfstate

my-company-tf-state-prod/
  platform/networking/terraform.tfstate
```

Ưu điểm: Isolation hoàn toàn. IAM policy rõ ràng theo environment. Engineer dev không touch được prod state.
Nhược điểm: Nhiều bucket hơn, phức tạp hơn ở bước setup.

**Best practice cho platform teams:** Dùng Pattern B. Production state cần được bảo vệ nghiêm ngặt. Separate bucket với separate IAM role là cách an toàn nhất.

### 6. State Backup và S3 Versioning

Enable S3 versioning cho state bucket là bắt buộc. Mỗi lần Terraform ghi state, S3 lưu một version mới. Bạn có thể rollback nếu state bị corrupt.

```
S3 Version history cho terraform.tfstate:
  v8 (latest) ← 2024-01-15 10:30:00 - sau apply thêm RDS
  v7          ← 2024-01-15 09:00:00 - sau apply thêm Security Group
  v6          ← 2024-01-14 15:00:00 - sau apply thêm subnet
  ...
```

Rollback state:
```bash
# List versions
aws s3api list-object-versions \
  --bucket my-company-terraform-state \
  --prefix platform/vpc/terraform.tfstate

# Download một version cụ thể
aws s3api get-object \
  --bucket my-company-terraform-state \
  --key platform/vpc/terraform.tfstate \
  --version-id <VERSION_ID> \
  terraform.tfstate.backup

# Nếu cần restore: upload version cũ lên làm version mới nhất
aws s3 cp terraform.tfstate.backup \
  s3://my-company-terraform-state/platform/vpc/terraform.tfstate
```

### 7. terraform init -migrate-state

Khi bạn thay đổi backend config (ví dụ từ local sang S3), chạy:

```bash
terraform init -migrate-state
```

Terraform sẽ:
1. Detect backend thay đổi
2. Hỏi bạn có muốn copy state sang backend mới không
3. Copy state file lên S3
4. Xóa local state (nếu bạn đồng ý)

```
Initializing the backend...
Do you want to copy existing state to the new backend?
  Pre-existing state was found while migrating the previous "local" backend to the
  newly configured "s3" backend. No existing state was found in the newly configured
  "s3" backend. Do you want to copy this state to the new backend?
  Enter a value: yes

Successfully configured the backend "s3"!
```

### 8. Remote Backend Architecture - ASCII Diagram

```
Developer Machine              AWS Cloud
─────────────────              ──────────────────────────────────────────

┌─────────────────┐            ┌──────────────────────────────────────┐
│                 │            │                                      │
│  terraform      │   read/    │  S3 Bucket                           │
│  plan/apply  ◄──┼───write───►│  "my-company-terraform-state"        │
│                 │   state    │                                      │
│                 │            │  platform/vpc/terraform.tfstate  v1  │
│                 │            │  platform/vpc/terraform.tfstate  v2  │
│                 │   lock/    │  platform/vpc/terraform.tfstate  v3  │
│                 ├───unlock──►│                                      │
│                 │            │  DynamoDB Table                      │
│                 │            │  "terraform-state-lock"              │
│                 │            │  LockID | Info                       │
└─────────────────┘            │  ───────|──────────────────────────  │
                               │  .../.. | Who: engineer-a, When: ... │
Developer Machine 2            │                                      │
─────────────────              └──────────────────────────────────────┘
┌─────────────────┐                        │
│                 │   try lock    DENIED ◄──┘
│  terraform      │─────────────►│
│  plan/apply     │              │ Error: state is locked by engineer-a
│  (blocked)      │              │ Lock Info: ...
│                 │              │ Run force-unlock if process crashed
└─────────────────┘

CI/CD Pipeline (GitHub Actions, Jenkins, etc.)
─────────────────────────────────────────────
┌─────────────────┐   IAM Role   ┌───────────┐
│  terraform      │─────────────►│  S3 +     │
│  plan/apply     │              │  DynamoDB │
│  (automation)   │              └───────────┘
└─────────────────┘
```

---

## Deep Dive & Trade-offs - 30 phút

### 1. So sánh Backend Options

| Backend         | Locking      | Versioning   | Cost         | Complexity | Phù hợp khi nào                            |
|-----------------|--------------|--------------|--------------|------------|---------------------------------------------|
| local           | Không        | Không        | Miễn phí     | Thấp       | Solo dev, learning, prototype               |
| S3 + DynamoDB   | Có (DynamoDB)| Có (S3)      | Thấp (~$1/mo)| Trung bình | AWS teams, production, tiêu chuẩn          |
| GCS             | Có (native)  | Có           | Tương đương  | Thấp hơn   | GCP teams (locking built-in, không cần extra service) |
| Azure Blob      | Có (native)  | Có           | Tương đương  | Thấp hơn   | Azure teams                                 |
| Terraform Cloud | Có (native)  | Có           | Free tier → $20/user/mo | Thấp | Cần UI, audit logs, policy enforcement |
| Consul          | Có           | Không mặc định| Vận hành Consul cluster| Cao | Onprem, HashiCorp stack enthusiasts |
| HTTP            | Optional     | Không         | Tuỳ backend  | Cao        | Custom backend, self-hosted solutions       |

**Takeaway cho AWS teams:** S3 + DynamoDB là gold standard. GCS đơn giản hơn một chút (locking built-in, không cần DynamoDB riêng) nhưng chỉ cho GCP.

### 2. S3 Backend Security

**Encryption:**
```hcl
backend "s3" {
  encrypt    = true        # Bắt buộc. Encrypt state at rest với AES-256
  kms_key_id = "arn:..."  # Optional. Dùng CMK thay vì AWS managed key
}
```

State file chứa sensitive data: database passwords, API keys, private IPs, certificate content. Encrypt là không thương lượng.

**Bucket Policy - Block public access hoàn toàn:**
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
    }
  ]
}
```

**IAM permissions tối thiểu:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::my-company-terraform-state",
        "arn:aws:s3:::my-company-terraform-state/platform/*"
      ]
    },
    {
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

Note: `DeleteObject` cần thiết khi Terraform xóa state (ít gặp). `ListBucket` cần để check state tồn tại hay chưa.

### 3. Bootstrap Strategies - Trade-offs

| Strategy            | Ưu điểm                                    | Nhược điểm                                         |
|---------------------|--------------------------------------------|----------------------------------------------------|
| Manual AWS CLI      | Đơn giản, nhanh, không phụ thuộc tool khác | Không reproducible bằng code, dễ quên bước nào    |
| Bootstrap TF project| Reproducible, kiểm soát config đầy đủ     | Phải maintain 2 project, người mới dễ nhầm lẫn   |
| CloudFormation      | Tự quản lý state riêng, stable             | Phải biết CloudFormation (thêm tool)               |
| Terraform Cloud     | Không cần bootstrap - TC quản lý state     | Chi phí, vendor lock-in                           |

**Recommendation:** Với team mới bắt đầu với Terraform, dùng manual AWS CLI để bootstrap. Document lại các lệnh. Sau khi team stable, consider moving to bootstrap TF project để repeatability.

### 4. State Isolation Patterns

**Anti-pattern - Một state file cho toàn bộ infrastructure:**
```
❌ Tất cả trong một:
   company/terraform.tfstate
   (VPC + EKS + RDS + IAM + tất cả services trong một file)
```

Vấn đề:
- Blast radius lớn. Lỗi nhỏ có thể affect toàn bộ infrastructure
- Plan/apply chậm vì phải refresh tất cả resource
- Team size tăng → conflict nhiều hơn
- Khó test thay đổi nhỏ

**Best practice - Isolate theo component và environment:**

```
Production:
  prod/networking/terraform.tfstate      (VPC, subnets, routes)
  prod/security/terraform.tfstate        (Security Groups, NACLs)
  prod/kubernetes/terraform.tfstate      (EKS cluster, node groups)
  prod/data/terraform.tfstate            (RDS, ElastiCache)
  prod/services/auth/terraform.tfstate   (Auth service infra)
  prod/services/api/terraform.tfstate    (API service infra)

Staging:
  staging/networking/terraform.tfstate
  staging/kubernetes/terraform.tfstate
  ...

Dev:
  dev/networking/terraform.tfstate
  dev/kubernetes/terraform.tfstate
  ...
```

Benefit: Một team làm việc trên `prod/services/auth` không ảnh hưởng team đang apply `prod/kubernetes`. Blast radius nhỏ. Apply nhanh hơn.

### 5. Cost Implications

**S3 + DynamoDB cho state management:**

```
S3 Storage:
  State file size thường: 1KB - 500KB per project
  1000 projects × 500KB = 500MB
  500MB × $0.023/GB = ~$0.01/month

S3 Requests:
  Mỗi plan/apply = ~5-10 API calls
  100 operations/day × 30 × $0.0004/1000 requests = ~$0.001/month

S3 Versioning:
  Giữ 10 versions × 500MB = 5GB
  $0.023/GB = ~$0.12/month

DynamoDB (PAY_PER_REQUEST):
  Lock/unlock = 2 write operations per apply
  100 applies/day × 30 × 2 × $0.00000125/write = ~$0.008/month

Tổng: < $1/month cho team nhỏ đến vừa
```

**So sánh với Terraform Cloud:**
- Free: 500 managed resources
- Plus: $20/user/month
- Business: Custom pricing

Với team 5 người: $100/month. S3 + DynamoDB rõ ràng rẻ hơn nhiều nếu bạn chấp nhận setup thêm một chút.

### 6. Common Pitfalls và Cách Fix

**Pitfall 1 - Wrong region:**
```hcl
# backend.tf
backend "s3" {
  bucket = "my-company-terraform-state"
  region = "us-east-1"  # ← Bucket ở ap-southeast-1 nhưng config sai region
}
```
Error: `NoSuchBucket`
Fix: Đảm bảo region trong backend config khớp với region của S3 bucket.

**Pitfall 2 - Missing DynamoDB table:**
```
Error: Failed to retrieve state lock info for the state: error retrieving
       state: dynamodb: ResourceNotFoundException: Requested resource not found
```
Fix: Tạo DynamoDB table với primary key `LockID` (type String) trước khi chạy `terraform init`.

**Pitfall 3 - Permission errors:**
```
Error: error configuring S3 Backend: error validating provider credentials:
       error calling sts:GetCallerIdentity: AccessDenied
```
Fix: Check AWS credentials đang active. Đảm bảo IAM policy đúng. Thử `aws sts get-caller-identity` để verify credentials.

**Pitfall 4 - State migration failure:**
State bị stuck ở giữa quá trình migrate. Kiểm tra:
```bash
# Check state ở local còn không
ls -la terraform.tfstate

# Check state đã lên S3 chưa
aws s3 ls s3://my-bucket/path/to/terraform.tfstate

# Re-run init nếu cần
terraform init -migrate-state -reconfigure
```

**Pitfall 5 - Bucket name conflict:**
S3 bucket name là global unique trên toàn bộ AWS. `my-terraform-state` đã bị người khác lấy rồi.
Fix: Dùng company name + account ID + region: `mycompany-123456789-ap-southeast-1-tf-state`.

**Pitfall 6 - State lock left behind:**
Terraform crash giữa chừng, lock không được cleanup.
```bash
# Xem thông tin lock trong error message
# Lấy LOCK_ID từ đó
terraform force-unlock <LOCK_ID>
```

---

## Hands-on Lab - 60 phút

### Cảnh báo chi phí

```
Các resource có thể phát sinh chi phí: S3 bucket, DynamoDB table
Ước tính chi phí: ~$0.50-1/month nếu giữ lại
Option miễn phí: Dùng LocalStack (hướng dẫn ở phần cuối lab)
Cleanup sau lab: terraform destroy + xóa S3 bucket thủ công
```

### Cấu trúc Lab

```
day-05-lab/
├── bootstrap/          # Bước 1: Tạo S3 + DynamoDB
│   ├── main.tf
│   ├── outputs.tf
│   └── variables.tf
├── app-infra/          # Bước 2: Project dùng remote backend
│   ├── backend.tf
│   ├── main.tf
│   ├── outputs.tf
│   └── variables.tf
└── localstack/         # Alternative: LocalStack setup
    └── docker-compose.yml
```

---

### Option A: Dùng real AWS (có phí nhỏ)

#### Bước 1 - Prerequisites

```bash
# Verify AWS CLI configured
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDA...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-user"
# }

# Verify Terraform installed
terraform version
# Terraform v1.6.x hoặc mới hơn
```

#### Bước 2 - Tạo Bootstrap project

Tạo thư mục và file:

```bash
mkdir -p ~/terraform-day5-lab/bootstrap
cd ~/terraform-day5-lab/bootstrap
```

File `bootstrap/variables.tf`:
```hcl
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Environment name for resource naming"
  type        = string
  default     = "learning"
}

variable "state_bucket_suffix" {
  description = "Unique suffix for S3 bucket name (use your AWS account ID or random string)"
  type        = string
  # Không có default - bắt buộc phải truyền vào để đảm bảo unique
}
```

File `bootstrap/main.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # NOTE: Bootstrap project dùng local backend
  # Đây là intentional - đây là project đặc biệt chỉ chạy một lần
}

provider "aws" {
  region = var.aws_region
}

locals {
  bucket_name = "terraform-state-${var.state_bucket_suffix}"
  table_name  = "terraform-state-lock"

  common_tags = {
    ManagedBy   = "terraform-bootstrap"
    Environment = var.environment
    Purpose     = "terraform-state-management"
  }
}

# S3 bucket để lưu Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = local.bucket_name

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }

  tags = local.common_tags
}

# Enable versioning - BẮT BUỘC, không negotiable
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block tất cả public access
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table cho state locking
resource "aws_dynamodb_table" "terraform_state_lock" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST" # Tiết kiệm chi phí cho low traffic
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = local.common_tags
}
```

File `bootstrap/outputs.tf`:
```hcl
output "state_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.terraform_state.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = aws_dynamodb_table.terraform_state_lock.id
}

output "backend_config_snippet" {
  description = "Copy this into your backend.tf files"
  value = <<-EOT
    terraform {
      backend "s3" {
        bucket         = "${aws_s3_bucket.terraform_state.id}"
        key            = "CHANGE_ME/terraform.tfstate"
        region         = "${var.aws_region}"
        dynamodb_table = "${aws_dynamodb_table.terraform_state_lock.id}"
        encrypt        = true
      }
    }
  EOT
}
```

Chạy bootstrap:
```bash
cd ~/terraform-day5-lab/bootstrap

terraform init

# Lấy AWS Account ID của bạn để dùng làm suffix
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"

terraform plan -var="state_bucket_suffix=${ACCOUNT_ID}"

# Review plan, sau đó apply
terraform apply -var="state_bucket_suffix=${ACCOUNT_ID}"
```

Expected output sau apply:
```
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:

backend_config_snippet = <<EOT
  terraform {
    backend "s3" {
      bucket         = "terraform-state-123456789012"
      key            = "CHANGE_ME/terraform.tfstate"
      region         = "ap-southeast-1"
      dynamodb_table = "terraform-state-lock"
      encrypt        = true
    }
  }
EOT

dynamodb_table_name = "terraform-state-lock"
state_bucket_name = "terraform-state-123456789012"
```

#### Bước 3 - Tạo App Infrastructure project với Remote Backend

```bash
mkdir -p ~/terraform-day5-lab/app-infra
cd ~/terraform-day5-lab/app-infra
```

File `app-infra/backend.tf`:
```hcl
terraform {
  backend "s3" {
    # THAY bucket name bằng output từ bước 2
    bucket         = "terraform-state-123456789012"
    key            = "day5-lab/app-infra/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

File `app-infra/variables.tf`:
```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "learning"
}
```

File `app-infra/main.tf`:
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

provider "aws" {
  region = var.aws_region
}

# Tạo một resource đơn giản để test - SSM Parameter (không có chi phí)
resource "aws_ssm_parameter" "demo" {
  name  = "/day5-lab/${var.environment}/demo-param"
  type  = "String"
  value = "hello-from-remote-backend"

  tags = {
    Environment = var.environment
    Lab         = "day5-remote-backend"
  }
}
```

File `app-infra/outputs.tf`:
```hcl
output "ssm_parameter_name" {
  description = "SSM Parameter name"
  value       = aws_ssm_parameter.demo.name
}

output "ssm_parameter_arn" {
  description = "SSM Parameter ARN"
  value       = aws_ssm_parameter.demo.arn
}
```

```bash
cd ~/terraform-day5-lab/app-infra

terraform init
```

Expected output của `terraform init`:
```
Initializing the backend...

Successfully configured the backend "s3"! Terraform will automatically
use this backend unless the backend configuration changes.

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...
- Installed hashicorp/aws v5.x.x (signed by HashiCorp)

Terraform has been successfully initialized!
```

```bash
terraform plan
terraform apply
```

Expected output:
```
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

Outputs:
ssm_parameter_arn = "arn:aws:ssm:ap-southeast-1:123456789012:parameter/day5-lab/learning/demo-param"
ssm_parameter_name = "/day5-lab/learning/demo-param"
```

Verify state đã lên S3:
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 ls s3://terraform-state-${ACCOUNT_ID}/day5-lab/app-infra/
```

Expected:
```
2024-01-15 10:30:00       2048 terraform.tfstate
```

#### Bước 4 - Test State Locking

Mở terminal thứ hai. Trong terminal 1:
```bash
cd ~/terraform-day5-lab/app-infra
# Dùng -lock-timeout=0 để giữ lock và fail ngay nếu có conflict
terraform apply -auto-approve
```

Trong terminal 2 (ngay lập tức):
```bash
cd ~/terraform-day5-lab/app-infra
terraform plan
```

Terminal 2 sẽ bị block với message:
```
Acquiring state lock. This may take a few moments...

Error: Error acquiring the state lock

Error message: ConditionalCheckFailedException: ...
Lock Info:
  ID:        abc123...
  Path:      terraform-state-.../day5-lab/app-infra/terraform.tfstate
  Operation: OperationTypeApply
  Who:       your-user@your-machine
  Version:   1.6.x
  Created:   2024-01-15 10:30:00 +0000 UTC
  Info:
```

Đây là locking hoạt động đúng. Terminal 2 không thể proceed cho đến khi Terminal 1 xong.

#### Bước 5 - Migrate từ Local sang Remote State

Tạo một project local trước:
```bash
mkdir -p ~/terraform-day5-lab/migration-demo
cd ~/terraform-day5-lab/migration-demo
```

File `migration-demo/main.tf` (không có backend block = dùng local):
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

provider "aws" {
  region = "ap-southeast-1"
}

resource "aws_ssm_parameter" "migration_demo" {
  name  = "/day5-lab/migration-demo"
  type  = "String"
  value = "this-started-with-local-state"
}
```

```bash
terraform init
terraform apply -auto-approve
# State được lưu ở ./terraform.tfstate (local)
ls -la terraform.tfstate  # Verify file tồn tại
```

Bây giờ migrate sang remote backend. Thêm `backend.tf`:

```hcl
# migration-demo/backend.tf (thêm file này)
terraform {
  backend "s3" {
    bucket         = "terraform-state-123456789012"  # Thay bằng bucket của bạn
    key            = "day5-lab/migration-demo/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

```bash
terraform init -migrate-state
```

Output sẽ hỏi:
```
Initializing the backend...
Do you want to copy existing state to the new backend?
  Pre-existing state was found while migrating the previous "local" backend to the
  newly configured "s3" backend. No existing state was found in the newly configured
  "s3" backend. Do you want to copy this state to the new backend?

  Enter a value: yes  ← Gõ yes

Successfully configured the backend "s3"! Terraform will automatically
use this backend unless the backend configuration changes.
```

Verify:
```bash
# Local state vẫn còn (Terraform không tự xóa)
ls -la terraform.tfstate

# State đã lên S3
aws s3 ls s3://terraform-state-123456789012/day5-lab/migration-demo/
```

Có thể xóa local state an toàn vì S3 đã có đầy đủ:
```bash
rm terraform.tfstate terraform.tfstate.backup
```

Test rằng Terraform vẫn hoạt động với remote state:
```bash
terraform plan
# Expected: No changes. Infrastructure is up-to-date.
```

#### Bước 6 - Cleanup

```bash
# Destroy app-infra
cd ~/terraform-day5-lab/app-infra
terraform destroy -auto-approve

# Destroy migration-demo
cd ~/terraform-day5-lab/migration-demo
terraform destroy -auto-approve

# Xóa S3 bucket (cần empty bucket trước)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="terraform-state-${ACCOUNT_ID}"

# Xóa tất cả versions (vì versioning enabled)
aws s3api delete-objects \
  --bucket $BUCKET \
  --delete "$(aws s3api list-object-versions \
    --bucket $BUCKET \
    --output=json \
    --query='{Objects: Versions[].{Key:Key,VersionId:VersionId}}')"

# Xóa delete markers nếu có
aws s3api delete-objects \
  --bucket $BUCKET \
  --delete "$(aws s3api list-object-versions \
    --bucket $BUCKET \
    --output=json \
    --query='{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}')" 2>/dev/null || true

# Xóa bucket
aws s3 rb s3://$BUCKET

# Xóa DynamoDB table
aws dynamodb delete-table --table-name terraform-state-lock --region ap-southeast-1

# Destroy bootstrap (lưu ý: có prevent_destroy, cần comment out trước)
# Cách đơn giản: xóa resource bằng tay (đã làm ở trên)
```

---

### Option B: LocalStack (Miễn phí, dùng cho học tập)

LocalStack emulate AWS services locally. Phù hợp cho learning mà không muốn tốn phí.

File `localstack/docker-compose.yml`:
```yaml
version: "3.8"
services:
  localstack:
    image: localstack/localstack:2026.05.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,dynamodb,sts,iam
      - DEBUG=0
      - DEFAULT_REGION=us-east-1
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
```

```bash
cd ~/terraform-day5-lab/localstack
docker-compose up -d

# Verify LocalStack running
curl http://localhost:4566/_localstack/health
```

Tạo resources trên LocalStack:
```bash
# Tạo S3 bucket
aws --endpoint-url=http://localhost:4566 s3api create-bucket \
  --bucket terraform-state-local \
  --region us-east-1

# Enable versioning
aws --endpoint-url=http://localhost:4566 s3api put-bucket-versioning \
  --bucket terraform-state-local \
  --versioning-configuration Status=Enabled

# Tạo DynamoDB table
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Backend config cho LocalStack:
```hcl
terraform {
  backend "s3" {
    bucket         = "terraform-state-local"
    key            = "day5-lab/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true

    # LocalStack-specific settings
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    force_path_style            = true

    endpoints {
      s3       = "http://localhost:4566"
      dynamodb = "http://localhost:4566"
    }
  }
}
```

Provider config cho LocalStack:
```hcl
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    ssm      = "http://localhost:4566"
  }
}
```

Cleanup LocalStack:
```bash
cd ~/terraform-day5-lab/localstack
docker-compose down -v
```

---

## Kiểm tra hiểu bài

1. **Tại sao local state không đủ cho team môi trường?** Liệt kê 3 vấn đề cụ thể và giải thích cơ chế gây ra mỗi vấn đề.

2. **Giải thích bootstrap problem trong Terraform remote backend.** Bạn sẽ chọn strategy nào cho một team 10 người mới bắt đầu dùng Terraform? Và tại sao?

3. **So sánh key prefix isolation vs. separate bucket per environment.** Khi nào bạn chọn từng cách? Với một platform team quản lý 3 environment (dev/staging/prod), bạn khuyến nghị gì?

4. **DynamoDB lock bị stuck sau khi Terraform process crash.** Bạn xác nhận không có operation nào đang chạy. Bạn làm gì tiếp theo? Lệnh cụ thể là gì?

5. **State file chứa loại thông tin gì khiến encryption trở nên bắt buộc?** Cho ví dụ với một RDS instance được quản lý bởi Terraform.

---

## Tóm tắt cuối ngày

### Key Points

- **Remote backend giải quyết 3 vấn đề:** State centralization, distributed locking, và audit trail
- **S3 + DynamoDB = gold standard cho AWS:** S3 lưu state với versioning, DynamoDB xử lý concurrent access control
- **Bootstrap problem có nhiều giải pháp:** Manual CLI đơn giản nhất để bắt đầu, bootstrap Terraform project tốt hơn cho long-term
- **Isolation strategy quan trọng:** Separate bucket per environment cho production workloads, key prefix cho small teams
- **State file là sensitive data:** Encryption at rest + HTTPS in transit là bắt buộc
- **Blast radius phụ thuộc vào state isolation:** Một state file per component, không gộp tất cả vào một
- **Migration là reversible:** `terraform init -migrate-state` và S3 versioning cho phép rollback

### Outputs của ngày học

Bạn đã làm được:
- Tạo S3 bucket và DynamoDB table cho Terraform state management
- Configure và sử dụng S3 backend trong một Terraform project thực
- Test state locking với concurrent operations
- Migrate project từ local state sang remote state
- Hiểu trade-offs giữa các backend options

### Chuẩn bị cho Day 6 - Module Basics

Day 6 sẽ cover Terraform Modules - cách tổ chức và tái sử dụng Terraform code. Trước khi học:

- Nghĩ về code reuse patterns bạn biết: npm packages, Go modules, Python packages. Module pattern trong Terraform tương tự về concept
- Xem lại code từ Day 3-4 và nghĩ: phần nào có thể được tái sử dụng cho nhiều environments?
- Một câu hỏi để suy nghĩ: Nếu bạn cần deploy cùng một set networking resources (VPC, subnets, security groups) cho 5 microservices, bạn sẽ tổ chức code như thế nào?

---

## Tham khảo thêm

- [Terraform S3 Backend Documentation](https://developer.hashicorp.com/terraform/language/backend/s3) - Official docs với đầy đủ config options
- [Terraform Backend Configuration](https://developer.hashicorp.com/terraform/language/backend) - Tổng quan về backend types
- [AWS S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html) - Cách versioning hoạt động
- [DynamoDB Conditional Writes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html#WorkingWithItems.ConditionalUpdate) - Cơ chế đằng sau locking
- [LocalStack Documentation](https://docs.localstack.cloud/getting-started/) - Setup và sử dụng LocalStack
- [Terraform State Locking](https://developer.hashicorp.com/terraform/language/state/locking) - Chi tiết về locking mechanism
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) - Cho IAM policy design
