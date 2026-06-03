# Day 5 - Exercises: Remote Backend với S3 + DynamoDB

**Thời gian ước tính:** 90 phút tổng cộng  
**Prerequisites:** Hoàn thành lesson.md và hands-on lab

---

## Exercise 1 - Backend Migration Challenge (30 phút)

### Bối cảnh

Bạn join một team đang có một Terraform project quản lý một số AWS SSM Parameters. Project đang dùng local state và không ai biết state file đang ở đâu. Nhiệm vụ của bạn: migrate về remote backend một cách an toàn mà không làm gián đoạn infrastructure hiện có.

### Setup - Simulate "legacy project"

Tạo thư mục và file:

```bash
mkdir -p ~/terraform-exercises/ex1-migration
cd ~/terraform-exercises/ex1-migration
```

File `main.tf` (simulate legacy project với local state):
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Không có backend block = local state
}

provider "aws" {
  region = "ap-southeast-1"
}

# Simulate "existing infrastructure"
resource "aws_ssm_parameter" "app_config" {
  for_each = {
    "database_host" = "db.internal.company.com"
    "cache_host"    = "redis.internal.company.com"
    "api_version"   = "v2"
  }

  name  = "/legacy-app/config/${each.key}"
  type  = "String"
  value = each.value

  tags = {
    Environment = "exercise"
    ManagedBy   = "terraform"
  }
}

output "parameter_names" {
  value = [for p in aws_ssm_parameter.app_config : p.name]
}
```

```bash
terraform init
terraform apply -auto-approve
# State bây giờ ở ./terraform.tfstate (local)
```

### Nhiệm vụ

**Task 1.1 - Audit state hiện tại (5 phút)**

Trước khi làm bất cứ điều gì, audit state:
```bash
# Xem tất cả resource trong state
terraform state list

# Xem chi tiết một resource
terraform state show 'aws_ssm_parameter.app_config["database_host"]'

# Backup state file với timestamp
cp terraform.tfstate terraform.tfstate.pre-migration-backup-$(date +%Y%m%d-%H%M%S)
```

Câu hỏi: state file của bạn có những thông tin gì? Thông tin nào bạn thấy là sensitive?

**Task 1.2 - Chuẩn bị remote backend (10 phút)**

Nếu chưa có S3 bucket + DynamoDB từ lab chính, tạo bằng AWS CLI:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="terraform-state-exercise-${ACCOUNT_ID}"
REGION="ap-southeast-1"

# S3 bucket
aws s3api create-bucket \
  --bucket $BUCKET \
  --region $REGION \
  --create-bucket-configuration LocationConstraint=$REGION

aws s3api put-bucket-versioning \
  --bucket $BUCKET \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket $BUCKET \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket $BUCKET \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# DynamoDB
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION

echo "Bucket: $BUCKET"
```

**Task 1.3 - Thực hiện migration (10 phút)**

Tạo file `backend.tf` trong cùng thư mục (không sửa `main.tf`):

```hcl
# backend.tf - THÊM FILE NÀY
terraform {
  backend "s3" {
    bucket         = "terraform-state-exercise-ACCOUNT_ID"  # Thay thế
    key            = "exercises/ex1-migration/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

```bash
# Migration
terraform init -migrate-state
# Trả lời "yes" khi được hỏi

# Verify migration thành công
terraform plan
# Expected: "No changes. Infrastructure is up-to-date."

# Verify state ở S3
aws s3 ls s3://${BUCKET}/exercises/ex1-migration/
```

**Task 1.4 - Verify và cleanup local state (5 phút)**

```bash
# Sau khi verify terraform plan = no changes, xóa local state
rm terraform.tfstate terraform.tfstate.backup 2>/dev/null || true
# Giữ backup file đã tạo ở Task 1.1

# Test lại - phải vẫn hoạt động với remote state
terraform plan
terraform state list
```

### Tiêu chí hoàn thành

- [ ] `terraform state list` sau migration hiện đúng 3 SSM parameters
- [ ] `terraform plan` sau migration báo "No changes"
- [ ] State file tồn tại trên S3 tại đúng key path
- [ ] Local `terraform.tfstate` đã được xóa (chỉ giữ backup)
- [ ] Có thể giải thích: điều gì xảy ra với infrastructure trong suốt quá trình migration?

---

## Exercise 2 - Multi-Environment Backend Setup (35 phút)

### Bối cảnh

Bạn cần setup backend strategy cho một platform team quản lý 3 environments: dev, staging, prod. Mỗi environment cần isolation hoàn toàn. Bạn sẽ implement Pattern B (separate bucket per environment) từ lesson.

### Cấu trúc mục tiêu

```
~/terraform-exercises/ex2-multi-env/
├── bootstrap/
│   ├── main.tf          # Tạo S3 + DynamoDB cho cả 3 env
│   ├── variables.tf
│   └── outputs.tf
├── platform/
│   ├── dev/
│   │   ├── backend.tf
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── staging/
│   │   ├── backend.tf
│   │   ├── main.tf
│   │   └── variables.tf
│   └── prod/
│       ├── backend.tf
│       ├── main.tf
│       └── variables.tf
└── backend-configs/     # Partial backend configs (không commit sensitive data)
    ├── dev.hcl
    ├── staging.hcl
    └── prod.hcl
```

### Task 2.1 - Bootstrap cho Multi-Environment (15 phút)

```bash
mkdir -p ~/terraform-exercises/ex2-multi-env/bootstrap
cd ~/terraform-exercises/ex2-multi-env/bootstrap
```

File `bootstrap/variables.tf`:
```hcl
variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "account_id" {
  description = "AWS Account ID, dùng cho unique bucket naming"
  type        = string
}

variable "company_prefix" {
  description = "Company prefix cho naming convention"
  type        = string
  default     = "mycompany"
}

variable "environments" {
  description = "List of environments cần tạo backend resources cho"
  type        = list(string)
  default     = ["dev", "staging", "prod"]
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
  # Bootstrap dùng local backend - intentional
}

provider "aws" {
  region = var.aws_region
}

locals {
  # Tạo map: environment -> bucket name
  env_buckets = {
    for env in var.environments :
    env => "${var.company_prefix}-tf-state-${env}-${var.account_id}"
  }
}

# Tạo một S3 bucket cho mỗi environment
resource "aws_s3_bucket" "terraform_state" {
  for_each = local.env_buckets

  bucket = each.value

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Environment = each.key
    Purpose     = "terraform-state"
    ManagedBy   = "terraform-bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  for_each = aws_s3_bucket.terraform_state

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  for_each = aws_s3_bucket.terraform_state

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  for_each = aws_s3_bucket.terraform_state

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Một DynamoDB table dùng chung cho tất cả environments
# (LockID bao gồm bucket name nên sẽ không conflict)
resource "aws_dynamodb_table" "terraform_state_lock" {
  name         = "${var.company_prefix}-terraform-state-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Purpose   = "terraform-state-locking"
    ManagedBy = "terraform-bootstrap"
  }
}
```

File `bootstrap/outputs.tf`:
```hcl
output "state_buckets" {
  description = "Map of environment -> bucket name"
  value       = { for k, v in aws_s3_bucket.terraform_state : k => v.id }
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_state_lock.id
}

output "backend_config_files_content" {
  description = "Content cho backend config files (copy vào backend-configs/)"
  value = {
    for env, bucket in local.env_buckets :
    env => <<-EOT
      bucket         = "${bucket}"
      region         = "${var.aws_region}"
      dynamodb_table = "${aws_dynamodb_table.terraform_state_lock.id}"
      encrypt        = true
    EOT
  }
}
```

```bash
cd ~/terraform-exercises/ex2-multi-env/bootstrap
terraform init

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform apply -var="account_id=${ACCOUNT_ID}"

# Lưu outputs để dùng sau
terraform output -json > ../bootstrap-outputs.json
```

### Task 2.2 - Tạo Platform Infrastructure cho mỗi Environment (15 phút)

Tạo backend config files (không commit file này nếu chứa account info):

```bash
mkdir -p ~/terraform-exercises/ex2-multi-env/backend-configs

# Lấy bucket names từ output
DEV_BUCKET=$(terraform output -json state_buckets | jq -r '.dev')
STAGING_BUCKET=$(terraform output -json state_buckets | jq -r '.staging')
PROD_BUCKET=$(terraform output -json state_buckets | jq -r '.prod')
DYNAMO_TABLE=$(terraform output -raw dynamodb_table_name)
```

File `backend-configs/dev.hcl`:
```hcl
bucket         = "mycompany-tf-state-dev-ACCOUNT_ID"   # Thay bằng actual value
key            = "platform/network/terraform.tfstate"
region         = "ap-southeast-1"
dynamodb_table = "mycompany-terraform-state-lock"
encrypt        = true
```

Làm tương tự cho `staging.hcl` và `prod.hcl` với bucket name tương ứng.

Tạo platform code (dùng chung, thay đổi backend config theo env):

```bash
mkdir -p ~/terraform-exercises/ex2-multi-env/platform/{dev,staging,prod}
```

File `platform/dev/main.tf` (và tương tự cho staging, prod - thay environment value):
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Backend config được load từ file .hcl khi init
  backend "s3" {}
}

provider "aws" {
  region = "ap-southeast-1"
}

variable "environment" {
  type    = string
  default = "dev"   # staging/prod tương ứng
}

# Simulate platform config per environment
resource "aws_ssm_parameter" "platform_config" {
  name  = "/platform/${var.environment}/cluster-name"
  type  = "String"
  value = "eks-${var.environment}-cluster"

  tags = {
    Environment = var.environment
    Layer       = "platform"
  }
}

output "cluster_name" {
  value = aws_ssm_parameter.platform_config.value
}
```

```bash
# Init và apply cho từng environment
cd ~/terraform-exercises/ex2-multi-env/platform/dev
terraform init -backend-config=../../backend-configs/dev.hcl
terraform apply -auto-approve

cd ~/terraform-exercises/ex2-multi-env/platform/staging
terraform init -backend-config=../../backend-configs/staging.hcl
terraform apply -var="environment=staging" -auto-approve

cd ~/terraform-exercises/ex2-multi-env/platform/prod
terraform init -backend-config=../../backend-configs/prod.hcl
terraform apply -var="environment=prod" -auto-approve
```

### Task 2.3 - Verify Isolation (5 phút)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Verify mỗi environment có state file trong bucket riêng
echo "=== DEV bucket ==="
aws s3 ls s3://mycompany-tf-state-dev-${ACCOUNT_ID}/platform/network/ 2>/dev/null || echo "Không thể access"

echo "=== STAGING bucket ==="
aws s3 ls s3://mycompany-tf-state-staging-${ACCOUNT_ID}/platform/network/ 2>/dev/null || echo "Không thể access"

echo "=== PROD bucket ==="
aws s3 ls s3://mycompany-tf-state-prod-${ACCOUNT_ID}/platform/network/ 2>/dev/null || echo "Không thể access"
```

### Câu hỏi phân tích (không cần code)

1. Với cấu trúc này, nếu bạn muốn giới hạn CI/CD pipeline chỉ được apply vào staging và prod (không phải dev), bạn sẽ thiết kế IAM policy như thế nào?

2. Nếu team dev cần xem state của staging để debug một issue, nhưng không được phép modify, bạn cần thêm permission gì?

3. Tại sao trong bài này bạn dùng một DynamoDB table chung thay vì mỗi environment một table? Có trade-off gì không?

### Tiêu chí hoàn thành

- [ ] Mỗi environment có S3 bucket riêng với versioning + encryption
- [ ] State file của mỗi environment nằm đúng bucket
- [ ] `terraform plan` cho cả 3 environments đều báo "No changes"
- [ ] Có thể giải thích tại sao `-backend-config` flag được dùng thay vì hardcode trong file

---

## Exercise 3 - State Locking Simulation (25 phút)

### Bối cảnh

Bạn cần hiểu rõ behavior của state locking trong các tình huống thực tế: concurrent apply, lock timeout, và force-unlock. Bài này simulate các tình huống đó.

### Setup

```bash
mkdir -p ~/terraform-exercises/ex3-locking
cd ~/terraform-exercises/ex3-locking
```

File `main.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }

  backend "s3" {
    bucket         = "THAY_BUCKET_CUA_BAN"
    key            = "exercises/ex3-locking/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

provider "time" {}

variable "instance_count" {
  type    = number
  default = 1
}

# time_sleep dùng để tạo delay, cho phép simulate concurrent operations
resource "time_sleep" "wait" {
  create_duration = "10s"   # Apply mất 10 giây để hoàn thành
}

resource "aws_ssm_parameter" "locking_demo" {
  count = var.instance_count

  name  = "/locking-demo/param-${count.index}"
  type  = "String"
  value = "value-${count.index}"

  depends_on = [time_sleep.wait]

  tags = {
    Lab = "locking-simulation"
  }
}
```

```bash
terraform init
```

### Task 3.1 - Concurrent Apply Simulation (10 phút)

Cần 2 terminal, cùng thư mục:

**Terminal 1:**
```bash
cd ~/terraform-exercises/ex3-locking

echo "Terminal 1: Bắt đầu apply (sẽ mất ~15 giây)..."
time terraform apply -auto-approve
```

**Terminal 2 (ngay sau đó, trong vòng 3 giây):**
```bash
cd ~/terraform-exercises/ex3-locking

echo "Terminal 2: Cố apply cùng lúc..."
terraform apply -auto-approve -var="instance_count=2"
```

Quan sát:
- Terminal 2 sẽ bị block với "Acquiring state lock..."
- Sau khi Terminal 1 xong, Terminal 2 được phép chạy
- Note lock ID từ error message nếu terminal 2 timeout

Ghi lại:
```
Lock ID: ________________________
Who đang giữ lock: ________________________
Operation: ________________________
Thời điểm lock được tạo: ________________________
```

### Task 3.2 - Lock Timeout Configuration (5 phút)

Bạn có thể set timeout cho việc chờ acquire lock:

```bash
# Thử acquire lock với timeout 5 giây (sẽ fail nhanh hơn)
terraform apply -lock-timeout=5s -auto-approve
# Error ngay sau 5 giây nếu lock held bởi process khác

# Timeout 2 phút (mặc định là 0s = không chờ)
terraform apply -lock-timeout=2m -auto-approve

# Hoàn toàn skip locking (NGUY HIỂM - chỉ cho testing)
terraform apply -lock=false -auto-approve
```

Câu hỏi: Trong tình huống nào bạn có thể dùng `-lock=false`? Rủi ro là gì?

### Task 3.3 - Inspect và Force-Unlock (10 phút)

Simulate một locked state bằng cách hack DynamoDB trực tiếp:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATE_KEY="exercises/ex3-locking/terraform.tfstate"
BUCKET="terraform-state-exercise-${ACCOUNT_ID}"  # Hoặc bucket của bạn

# Xem lock table hiện tại có entries không
aws dynamodb scan \
  --table-name terraform-state-lock \
  --region ap-southeast-1 \
  --query 'Items[*]' \
  --output json
```

Sau khi chạy apply một lần, thử xem lock record trong DynamoDB:

```bash
# Apply để tạo lock (nhanh, không có time_sleep nếu đã apply)
# Hoặc dùng Terminal approach từ Task 3.1

# Trong khi Terminal 1 đang apply, ở Terminal 2:
aws dynamodb get-item \
  --table-name terraform-state-lock \
  --key '{"LockID": {"S": "BUCKET_NAME/exercises/ex3-locking/terraform.tfstate"}}' \
  --region ap-southeast-1
```

Simulate stuck lock (để test force-unlock):

```bash
# Thủ công ghi một lock record giả vào DynamoDB
aws dynamodb put-item \
  --table-name terraform-state-lock \
  --region ap-southeast-1 \
  --item '{
    "LockID": {"S": "BUCKET_NAME/exercises/ex3-locking/terraform.tfstate"},
    "Info": {"S": "{\"ID\":\"fake-lock-id-12345\",\"Operation\":\"OperationTypeApply\",\"Who\":\"simulate@crash\",\"Version\":\"1.6.0\",\"Created\":\"2024-01-01T00:00:00.000Z\"}"}
  }'

# Bây giờ thử plan - sẽ bị block
terraform plan
# Error: state is locked...

# Force unlock với fake lock ID
terraform force-unlock fake-lock-id-12345
# Trả lời "yes"

# Verify unlock
terraform plan
# Phải chạy được
```

### Task 3.4 - Phân tích: Khi nào dùng force-unlock?

Điền vào bảng phân tích sau (dựa trên understanding sau khi làm lab):

| Tình huống                                        | Có nên force-unlock không? | Lý do                        |
|--------------------------------------------------|----------------------------|------------------------------|
| Terraform plan/apply crash giữa chừng            | ?                          | ?                            |
| Engineer A đang apply, Engineer B muốn plan ngay | ?                          | ?                            |
| Lock timestamp cũ hơn 24h, không ai xác nhận chạy| ?                          | ?                            |
| CI/CD pipeline fail và không cleanup lock         | ?                          | ?                            |
| Lock held bởi laptop engineer (không respond)    | ?                          | ?                            |

### Cleanup Exercise 3

```bash
cd ~/terraform-exercises/ex3-locking
terraform destroy -auto-approve
```

---

## Cleanup Tổng Thể

```bash
# Exercise 1
cd ~/terraform-exercises/ex1-migration
terraform destroy -auto-approve

# Exercise 2
cd ~/terraform-exercises/ex2-multi-env/platform/dev
terraform destroy -auto-approve
cd ~/terraform-exercises/ex2-multi-env/platform/staging
terraform destroy -var="environment=staging" -auto-approve
cd ~/terraform-exercises/ex2-multi-env/platform/prod
terraform destroy -var="environment=prod" -auto-approve

# Xóa S3 buckets và DynamoDB (adjust theo tên thực tế của bạn)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

for BUCKET in \
  "terraform-state-exercise-${ACCOUNT_ID}" \
  "mycompany-tf-state-dev-${ACCOUNT_ID}" \
  "mycompany-tf-state-staging-${ACCOUNT_ID}" \
  "mycompany-tf-state-prod-${ACCOUNT_ID}"; do

  echo "Emptying bucket: $BUCKET"

  # Xóa tất cả versions
  aws s3api list-object-versions --bucket $BUCKET \
    --output json \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' 2>/dev/null | \
    xargs -I{} aws s3api delete-objects --bucket $BUCKET --delete '{}' 2>/dev/null || true

  # Xóa delete markers
  aws s3api list-object-versions --bucket $BUCKET \
    --output json \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' 2>/dev/null | \
    xargs -I{} aws s3api delete-objects --bucket $BUCKET --delete '{}' 2>/dev/null || true

  # Xóa bucket
  aws s3 rb s3://$BUCKET 2>/dev/null || echo "Bucket $BUCKET không tồn tại hoặc không thể xóa"
done

# Xóa DynamoDB tables
for TABLE in "terraform-state-lock" "mycompany-terraform-state-lock"; do
  aws dynamodb delete-table \
    --table-name $TABLE \
    --region ap-southeast-1 2>/dev/null || echo "Table $TABLE không tồn tại"
done

echo "Cleanup xong!"
```

---

## Bonus Challenge - Nếu còn thời gian

### Challenge A - State Inspection và Modification

Explore các lệnh quản lý state nâng cao:

```bash
# List tất cả resources trong state
terraform state list

# Move resource trong state (rename resource address mà không recreate)
terraform state mv \
  'aws_ssm_parameter.app_config["database_host"]' \
  'aws_ssm_parameter.app_config_renamed["database_host"]'

# Remove resource khỏi state (Terraform quên resource, nhưng resource vẫn tồn tại trên AWS)
# CẢNH BÁO: Chỉ làm trên exercise, không làm production mà không hiểu rõ
terraform state rm 'aws_ssm_parameter.app_config["api_version"]'

# Re-import resource bị remove
terraform import \
  'aws_ssm_parameter.app_config["api_version"]' \
  '/legacy-app/config/api_version'
```

### Challenge B - Backend Config với Environment Variables

Terraform hỗ trợ set backend config qua environment variables (prefix `TF_BACKEND_`):

```bash
# Thay vì file .hcl, dùng environment variables
export TF_BACKEND_bucket="terraform-state-exercise-${ACCOUNT_ID}"
export TF_BACKEND_key="exercises/challenge-b/terraform.tfstate"
export TF_BACKEND_region="ap-southeast-1"
export TF_BACKEND_dynamodb_table="terraform-state-lock"
export TF_BACKEND_encrypt="true"

terraform init
```

Câu hỏi: Cách này có ưu/nhược điểm gì so với `-backend-config=file.hcl`? Phù hợp nhất trong tình huống nào?

### Challenge C - State Versioning Recovery

Simulate và recover một corrupted state:

```bash
# 1. Apply thành công (state version 1 sẽ trên S3)
terraform apply -auto-approve

# 2. Check S3 versions
aws s3api list-object-versions \
  --bucket YOUR_BUCKET \
  --prefix exercises/ex1-migration/terraform.tfstate \
  --query 'Versions[*].{VersionId:VersionId,LastModified:LastModified}' \
  --output table

# 3. Download một version cũ và inspect
aws s3api get-object \
  --bucket YOUR_BUCKET \
  --key exercises/ex1-migration/terraform.tfstate \
  --version-id VERSION_ID_HERE \
  state-version-old.json

cat state-version-old.json | python -m json.tool | head -50

# 4. Nếu state bị corrupt, restore phiên bản cũ
aws s3 cp state-version-old.json \
  s3://YOUR_BUCKET/exercises/ex1-migration/terraform.tfstate
```

---

## Đáp án gợi ý - Câu hỏi phân tích

### Exercise 2 - Câu hỏi 3: Một DynamoDB table vs nhiều tables

**Một table chung:**
- LockID bao gồm bucket name + key path, nên không bao giờ conflict giữa các environments
- Đơn giản hơn: ít resource cần bootstrap
- Chi phí thấp hơn: PAY_PER_REQUEST, rất ít traffic

**Nhiều tables (một per env):**
- Isolation hoàn toàn: prod lock table không accessible từ dev role
- Audit rõ ràng hơn: DynamoDB logs per environment dễ filter
- Phù hợp hơn khi compliance yêu cầu strict isolation

**Khuyến nghị:** Một DynamoDB table là đủ cho hầu hết teams. Nếu compliance (SOC2, PCI-DSS) yêu cầu, tách ra.

### Exercise 3 - Task 3.2: Khi nào dùng `-lock=false`?

`-lock=false` chỉ nên dùng khi:
1. Chạy `terraform plan` (read-only, không modify state) trong CI để check nhanh
2. Testing/debugging trên môi trường isolated mà bạn chắc chắn không có concurrent access
3. KHÔNG BAO GIỜ dùng với `terraform apply` trong môi trường production

### Exercise 3 - Task 3.4: Force-unlock table

| Tình huống                                        | Force-unlock? | Lý do                                                               |
|--------------------------------------------------|---------------|---------------------------------------------------------------------|
| Terraform plan/apply crash giữa chừng            | Có            | Process đã dead, lock không còn được giữ bởi ai                   |
| Engineer A đang apply, Engineer B muốn plan ngay | Không         | Lock đang được giữ bởi active process                              |
| Lock timestamp cũ hơn 24h, không ai xác nhận    | Có (cẩn thận) | Verify qua Slack/call không có ai đang run trước khi force-unlock  |
| CI/CD pipeline fail và không cleanup lock         | Có            | Pipeline đã terminate, verify qua CI logs trước                   |
| Lock held bởi laptop engineer (không respond)    | Có (cẩn thận) | Verify engineer không đang apply offline trước                     |
