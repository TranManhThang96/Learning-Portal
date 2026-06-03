# Day 12: Terraform State Strategy, Drift Detection, Cost Control, Policy as Code

**Thời gian:** 2 giờ | **Level:** Advanced | **Phase:** 2 - Terraform Production, Day 6 (Final)

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Thiết kế **state layout** cho hệ thống microservices production với nhiều env, nhiều domain
- Hiểu và xử lý **state coupling problem** - vấn đề thường xuyên gây outage khi refactor infra
- Phát hiện và xử lý **infrastructure drift** bằng `terraform plan` + CI automation
- Tích hợp **Infracost** vào pipeline để kiểm soát chi phí trước khi apply
- Viết **Policy as Code** với OPA/Conftest để enforce governance rules trên Terraform plan

---

## 2. Bối cảnh thực tế

### Vấn đề không có state strategy

Bạn join một team startup đã deploy infra bằng Terraform 6 tháng. Mọi thứ nằm trong một file `main.tf` và một `terraform.tfstate` duy nhất. Hôm nay cần thêm một con RDS mới cho service mới. Bạn chạy `terraform plan` và thấy:

```
Plan: 1 to add, 47 to change, 0 to destroy.
```

47 resources thay đổi? Bạn chỉ thêm 1 RDS. Điều gì đang xảy ra?

**Đây là triệu chứng của monolithic state** - toàn bộ infra trong một state file, mọi thay đổi nhỏ đều trigger re-evaluation của toàn bộ hệ thống.

### Vấn đề drift trong thực tế

SRE team hotfix trực tiếp trên AWS Console lúc 3 giờ sáng để resolve outage - họ sửa security group, thêm một rule cho phép traffic. Terraform không biết điều này. Một tuần sau, ai đó chạy `terraform apply` và rule đó bị xóa. Production down.

### Vấn đề chi phí không kiểm soát

Developer thêm `instance_type = "m5.4xlarge"` vào module thay vì `m5.large` vì copy-paste. Không ai review. Infrastructure cost tăng $3,000/tháng. CFO phát hiện sau 2 tháng.

### Vấn đề compliance

Toàn bộ S3 bucket phải có encryption và tags `Environment`, `Owner`. Một developer mới tạo bucket không có encryption. Audit team phát hiện sau 3 tháng.

**Day 12 giải quyết tất cả các vấn đề trên.**

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 State Layout Strategy

#### Tại sao cần split state?

Nghĩ về state giống như **database transaction scope**. Nếu bạn đặt toàn bộ business logic vào một mega-transaction, bất kỳ lỗi nào cũng rollback tất cả. Monolithic state có vấn đề tương tự:

- **Blast radius lớn**: Lỗi trong một module có thể lock toàn bộ state
- **Plan time chậm**: Terraform phải refresh tất cả resources mỗi lần
- **Team conflict**: Nhiều team cùng edit state → lock contention
- **Security boundary**: Team A không nên có quyền xem state của Team B

#### Split theo Environment (Horizontal Split)

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   └── production/
│       ├── main.tf
│       └── terraform.tfvars
```

Mỗi environment có state riêng trong S3:
```
s3://company-terraform-state/
├── dev/terraform.tfstate
├── staging/terraform.tfstate
└── production/terraform.tfstate
```

**Ưu điểm**: Đơn giản, team nhỏ có thể adopt ngay  
**Nhược điểm**: Nếu environment phức tạp, state vẫn monolithic per-env

#### Split theo Domain/Module (Vertical Split)

```
terraform/
├── foundation/          # VPC, subnets, security groups
│   ├── main.tf
│   └── backend.tf
├── data/               # RDS, ElastiCache, S3
│   ├── main.tf
│   └── backend.tf
├── compute/            # EKS, EC2 Auto Scaling
│   ├── main.tf
│   └── backend.tf
└── apps/               # Application-level infra (ALB, Route53)
    ├── main.tf
    └── backend.tf
```

State layout trong S3:
```
s3://company-terraform-state/production/
├── foundation/terraform.tfstate
├── data/terraform.tfstate
├── compute/terraform.tfstate
└── apps/terraform.tfstate
```

**Ưu điểm**: Blast radius nhỏ, team có thể làm việc độc lập  
**Nhược điểm**: Cần coordinate khi có cross-domain dependency

#### Combined Strategy cho Microservices Platform

```
s3://company-terraform-state/
├── global/                          # IAM roles, Route53 hosted zones
│   └── terraform.tfstate
├── dev/
│   ├── foundation/terraform.tfstate # VPC, subnets
│   ├── data/terraform.tfstate       # RDS, Redis
│   └── apps/terraform.tfstate       # EKS, services
├── staging/
│   ├── foundation/terraform.tfstate
│   ├── data/terraform.tfstate
│   └── apps/terraform.tfstate
└── production/
    ├── foundation/terraform.tfstate
    ├── data/terraform.tfstate
    └── apps/terraform.tfstate
```

ASCII diagram:

```
┌─────────────────────────────────────────────────┐
│               Global State                       │
│           (IAM, DNS, shared)                     │
└───────────────────┬─────────────────────────────┘
                    │ remote_state reference
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │   dev   │ │staging  │ │  prod   │
   ├─────────┤ ├─────────┤ ├─────────┤
   │foundation│ │foundation│ │foundation│
   │  data   │ │  data   │ │  data   │
   │  apps   │ │  apps   │ │  apps   │
   └─────────┘ └─────────┘ └─────────┘
```

### 3.2 Remote State Data Source

#### Tại sao cần remote state data source?

Trong microservices, services cần biết về nhau. `apps` layer cần VPC ID từ `foundation` layer. Cách naive là hardcode VPC ID → brittle, không maintainable.

**Remote state data source** cho phép một state đọc output từ state khác mà không cần coupling code.

```hcl
# apps/main.tf - đọc VPC từ foundation state
data "terraform_remote_state" "foundation" {
  backend = "s3"
  config = {
    bucket = "company-terraform-state"
    key    = "production/foundation/terraform.tfstate"
    region = "us-east-1"
  }
}

# Sử dụng output từ foundation
resource "aws_eks_cluster" "main" {
  name     = "production-cluster"
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids = data.terraform_remote_state.foundation.outputs.private_subnet_ids
    # ↑ lấy từ foundation state, không hardcode
  }
}
```

Foundation state phải export outputs:
```hcl
# foundation/outputs.tf
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID for use by other state layers"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private subnet IDs"
}
```

#### State Coupling Problem

**Vấn đề**: Khi `apps` state đọc từ `foundation` state, nếu foundation thay đổi output name → apps state break.

Đây là **tight coupling giữa states** - giống coupling giữa microservices nhưng ở tầng infrastructure.

```
┌──────────────┐         ┌──────────────┐
│  foundation  │         │     apps     │
│   state      │◄────────│    state     │
│              │  reads  │              │
│ outputs:     │         │ needs:       │
│  vpc_id      │         │  vpc_id ✓    │
│  subnet_ids  │         │  subnet_ids ✓│
└──────────────┘         └──────────────┘

Nếu foundation rename "subnet_ids" → "private_subnets":
→ apps state lỗi ngay lập tức
→ apps deploy fail
→ Outage nếu không có rollback plan
```

**Giải pháp**:
1. **Output versioning**: Giữ old output name, thêm `deprecated = true` comment
2. **Contract testing**: CI kiểm tra output compatibility trước khi merge
3. **Interface layer**: Dùng SSM Parameter Store hoặc Consul làm registry thay vì direct state reference

```hcl
# Thay vì direct state reference, dùng SSM
data "aws_ssm_parameter" "vpc_id" {
  name = "/production/foundation/vpc_id"
}

# foundation viết vào SSM
resource "aws_ssm_parameter" "vpc_id" {
  name  = "/production/foundation/vpc_id"
  type  = "String"
  value = aws_vpc.main.id
}
```

### 3.3 Drift Detection

#### Drift là gì?

**Drift** = sự khác biệt giữa Terraform state và actual infrastructure.

Nguyên nhân:
- Manual change trên console (hotfix)
- Script chạy trực tiếp (AWS CLI, SDK)
- Cloud platform tự thay đổi (auto-scaling, managed service update)
- Import resource mà không update state

#### Phát hiện drift

```bash
# Refresh state từ actual infra, show diff
terraform refresh
terraform plan

# Hoặc trực tiếp
terraform plan -refresh-only
```

Output của `terraform plan -refresh-only`:
```
~ aws_security_group.web (refresh only)
    ~ ingress = [
        + {
            + cidr_blocks      = ["10.0.0.0/8"]
            + from_port        = 443
            + protocol         = "tcp"
            + to_port          = 443
          },
      ]

Plan: 0 to add, 0 to change, 0 to destroy.
Note: Objects have changed outside of Terraform
```

#### Automated Drift Detection

Chạy drift detection scheduled trong CI/CD:

```yaml
# .github/workflows/drift-detection.yml
name: Drift Detection

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC mỗi ngày

jobs:
  detect-drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init
        working-directory: terraform/production/apps

      - name: Detect Drift
        id: drift
        run: |
          OUTPUT=$(terraform plan -refresh-only -detailed-exitcode 2>&1) || EXIT_CODE=$?
          echo "$OUTPUT"
          if [ "${EXIT_CODE}" == "2" ]; then
            echo "DRIFT_DETECTED=true" >> $GITHUB_ENV
            echo "::warning::Infrastructure drift detected!"
          fi

      - name: Notify on Drift
        if: env.DRIFT_DETECTED == 'true'
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: 'infra-alerts'
          slack-message: ':warning: Infrastructure drift detected in production!'
```

### 3.4 Infracost - Cost Estimation

#### Tại sao cần cost estimation trong CI?

Giống như code review kiểm tra correctness, **cost review** kiểm tra budget impact. Infracost integrate vào PR để hiển thị cost diff.

```
┌─────────────────────────────────────────┐
│  Pull Request: Add RDS for user-service  │
├─────────────────────────────────────────┤
│  Infracost estimate:                     │
│                                          │
│  + aws_db_instance.users                 │
│      $245.61/month                       │
│                                          │
│  TOTAL CHANGE: +$245.61/month           │
│                                          │
│  [View full breakdown]                   │
└─────────────────────────────────────────┘
```

Developer thấy ngay impact trước khi merge.

#### Infracost hoạt động thế nào?

```bash
# Cài đặt
brew install infracost  # macOS
# hoặc
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Authenticate
infracost auth login

# Estimate cost cho một Terraform directory
infracost breakdown --path ./terraform/production/apps

# So sánh với baseline (detect cost changes)
infracost diff --path ./terraform/production/apps \
  --compare-to infracost-base.json
```

### 3.5 Policy as Code

#### Tại sao cần Policy as Code?

**Code review** có thể bỏ sót vi phạm policy. **Policy as Code** enforce rules tự động, không phụ thuộc vào human review.

Ví dụ policies phổ biến:
- Tất cả S3 bucket phải có encryption
- Không deploy instance type > m5.2xlarge ở dev
- Mọi resource phải có tag `Environment`, `Owner`, `CostCenter`
- RDS không được publicly accessible
- Security group không được open port 22 ra 0.0.0.0/0

#### OPA (Open Policy Agent)

OPA là policy engine general-purpose, dùng ngôn ngữ **Rego** để viết rules.

```
┌──────────────┐     JSON input      ┌──────────────┐
│  Terraform   │─────────────────────►│     OPA      │
│    Plan      │                     │  (Rego rules)│
│  (JSON)      │◄────────────────────│              │
└──────────────┘   allow/deny decision└──────────────┘
```

#### Conftest

**Conftest** là CLI wrapper cho OPA, tối ưu cho config validation:

```bash
# Cài đặt
brew install conftest

# Validate terraform plan
terraform show -json plan.tfplan > plan.json
conftest test plan.json --policy policies/
```

#### Sentinel (HashiCorp)

Sentinel là policy framework của HashiCorp, tích hợp native vào Terraform Cloud/Enterprise.

So sánh:

| Feature | OPA/Conftest | Sentinel |
|---------|-------------|----------|
| Language | Rego | Sentinel DSL |
| Integration | Manual, CI/CD | Native TFC/TFE |
| Learning curve | Steeper | Easier for TF users |
| Cost | Free | TFC/TFE required |
| Ecosystem | Broad | HashiCorp-specific |

Với team dùng Terraform Cloud → Sentinel. Với CI/CD tự build → OPA/Conftest.

---

## 4. Deep Dive & Trade-offs - 30 phút

### 4.1 State Split Strategies So sánh

| Strategy | Blast Radius | Team Independence | Complexity | Phù hợp |
|----------|-------------|-------------------|------------|---------|
| Monolithic | Toàn bộ infra | Thấp | Thấp | Solo dev, proof of concept |
| Per-env | Per environment | Trung bình | Thấp | Small team, simple infra |
| Per-env + Per-domain | Per domain | Cao | Trung bình | Medium team, microservices |
| Per-service | Per microservice | Rất cao | Cao | Large enterprise, platform team |

#### Recommendation theo context

**Cá nhân / Side project**: 1 state file per env là đủ. Đừng over-engineer.

**Small team (2-5 devs)**: Per-env split. Dùng workspace nếu env rất giống nhau.

**Startup (5-20 devs)**: Per-env + per-domain split. Foundation, data, apps layers.

**Enterprise / Bank**: Per-service state, full separation giữa domains. Có thể dùng Terragrunt để manage complexity.

### 4.2 Remote State Data Source vs SSM Parameter Store

| Aspect | Remote State | SSM Parameter |
|--------|-------------|---------------|
| Coupling | Tight (state format) | Loose (string values) |
| Type safety | Có (Terraform types) | Không (strings) |
| Access control | S3 bucket policy | IAM parameter path |
| Change tracking | S3 versioning | SSM versioning |
| Cross-team | Phức tạp | Dễ hơn |
| Non-Terraform consumers | Không | Có (bất kỳ service) |

**Recommendation**: Dùng remote state khi cùng team, cùng Terraform codebase. Dùng SSM khi cross-team hoặc non-Terraform consumers.

### 4.3 Drift Detection Strategies

| Approach | Frequency | Cost | Action |
|----------|-----------|------|--------|
| Manual `tf plan` | Ad-hoc | Thấp | Human review |
| Scheduled CI | Daily/Hourly | Trung bình | Alert + PR |
| Continuous (Atlantis) | On every change | Cao | Auto-apply or block |
| Drift detection tools (Driftctl) | Scheduled | Trung bình | Detailed report |

**Common Pitfall**: Auto-applying drift correction có thể reverting legitimate hotfixes. Luôn alert + human review cho production.

### 4.4 Policy as Code: Khi nào enforce ở đâu?

```
Developer writes code
        │
        ▼
  ┌─────────────┐
  │  Pre-commit │ ← Conftest local (fast feedback)
  │   hooks     │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  PR/CI      │ ← OPA + Conftest (blocking gate)
  │  pipeline   │   Infracost (cost review)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Terraform  │ ← Sentinel (if TFC/TFE)
  │  Cloud      │
  └─────────────┘
```

**Defense in depth**: Enforce ở nhiều layers, mỗi layer một loại check.

### 4.5 Common Pitfalls

#### Pitfall 1: State lock ở CI/CD

```
Error: Error locking state: Error acquiring the state lock
│ Lock Info:
│   ID: 12345678-...
│   Operation: OperationTypePlan
```

Xảy ra khi pipeline fail và không release lock. Fix:
```bash
terraform force-unlock <LOCK_ID>
```

Phòng ngừa: Dùng `-lock-timeout=10m`, implement lock cleanup trong CI.

#### Pitfall 2: Circular dependency giữa states

```
foundation state → reads from → apps state
apps state → reads from → foundation state
```

Không thể bootstrap được. Fix: Thiết kế dependency graph một chiều (DAG).

#### Pitfall 3: Sensitive data trong state

Terraform state lưu plaintext, kể cả sensitive values. Luôn:
- Enable S3 encryption
- Enable S3 versioning
- Restrict IAM access theo least privilege
- Không bao giờ commit state file vào git

#### Pitfall 4: Conftest false positives

Policy viết quá strict sẽ block legitimate changes. Test policies kỹ trước khi enforce:
```bash
conftest verify --policy policies/  # Test policies với test cases
```

---

## 5. Hands-on Lab - 60 phút

### Lab Overview

Bạn sẽ:
1. Thiết kế state layout cho microservices platform (20 phút)
2. Implement remote state data source (15 phút)
3. Setup Infracost cost estimation (10 phút)
4. Viết và test OPA policies với Conftest (15 phút)

**Prerequisites**: 
- AWS credentials configured (hoặc dùng LocalStack)
- Terraform >= 1.5.0 installed
- Git repository tạo sẵn

> **Cost Warning**: Lab này tạo S3 buckets cho state backend (< $1/month). Các resource khác chỉ tạo trong LocalStack hoặc sử dụng `terraform plan` không apply. Cleanup ở cuối lab.

---

### Part 1: Thiết kế State Layout cho Microservices Platform

#### Step 1.1: Tạo cấu trúc thư mục

```bash
mkdir -p ~/terraform-lab/platform/{global,dev,staging,production}
mkdir -p ~/terraform-lab/platform/{dev,staging,production}/{foundation,data,apps}

cd ~/terraform-lab
```

#### Step 1.2: Setup S3 backend buckets

Tạo file setup backend (chạy 1 lần, không quản lý bằng Terraform):

```bash
# bootstrap/create-backends.sh
#!/bin/bash
set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"
BUCKET_NAME="company-terraform-state-${ACCOUNT_ID}"

echo "Creating state bucket: ${BUCKET_NAME}"

aws s3api create-bucket \
  --bucket "${BUCKET_NAME}" \
  --region "${REGION}"

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Create DynamoDB for state locking
aws dynamodb create-table \
  --table-name terraform-state-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}"

echo "Backend setup complete!"
echo "Bucket: ${BUCKET_NAME}"
```

```bash
chmod +x ~/terraform-lab/bootstrap/create-backends.sh

# Nếu có AWS credentials thật:
# bash ~/terraform-lab/bootstrap/create-backends.sh

# Cho lab này, ta dùng local backend để tránh tạo AWS resources
```

#### Step 1.3: Foundation layer

```bash
cat > ~/terraform-lab/platform/dev/foundation/main.tf << 'EOF'
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Dùng local backend cho lab. Production dùng S3:
  # backend "s3" {
  #   bucket         = "company-terraform-state-${ACCOUNT_ID}"
  #   key            = "dev/foundation/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-locks"
  #   encrypt        = true
  # }
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
      Layer       = "foundation"
    }
  }
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "dev"
}

variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

# VPC (simplified for lab)
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.environment}-vpc"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.environment}-private-${count.index + 1}"
    Tier = "private"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}
EOF

cat > ~/terraform-lab/platform/dev/foundation/outputs.tf << 'EOF'
# IMPORTANT: Outputs đây được consume bởi các state layers khác
# Đừng rename/delete outputs mà không kiểm tra dependents

output "vpc_id" {
  description = "VPC ID - consumed by data and apps layers"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs - consumed by data and apps layers"
  value       = aws_subnet.private[*].id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.main.cidr_block
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}
EOF
```

#### Step 1.4: Apps layer sử dụng remote state

```bash
cat > ~/terraform-lab/platform/dev/apps/main.tf << 'EOF'
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Environment = "dev"
      ManagedBy   = "terraform"
      Layer       = "apps"
    }
  }
}

# Đọc output từ foundation state
data "terraform_remote_state" "foundation" {
  backend = "local"
  config = {
    path = "${path.module}/../foundation/terraform.tfstate"
  }
}

# Security Group cho web tier
resource "aws_security_group" "web" {
  name        = "dev-web-sg"
  description = "Security group for web tier"
  vpc_id      = data.terraform_remote_state.foundation.outputs.vpc_id
  # ↑ Lấy từ foundation state

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name  = "dev-web-sg"
    Owner = "platform-team"
  }
}

output "web_sg_id" {
  value = aws_security_group.web.id
}

output "foundation_vpc_id" {
  description = "VPC ID from foundation state (for verification)"
  value       = data.terraform_remote_state.foundation.outputs.vpc_id
}
EOF
```

#### Step 1.5: Initialize và plan

```bash
# Initialize foundation
cd ~/terraform-lab/platform/dev/foundation
terraform init
terraform plan -out=plan.tfplan

# Expected output:
# Plan: 3 to add, 0 to change, 0 to destroy.
# (VPC + 2 subnets)
```

> **Quan trọng**: Lab này dùng local backend. Trong production, thay bằng S3 backend với encryption và DynamoDB locking.

---

### Part 2: Implement Drift Detection

#### Step 2.1: Apply foundation resources

```bash
cd ~/terraform-lab/platform/dev/foundation
terraform apply -auto-approve

# Expected output:
# Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
```

#### Step 2.2: Simulate drift

```bash
# Giả sử ai đó thêm tag vào VPC ngoài Terraform
VPC_ID=$(terraform output -raw vpc_id)
aws ec2 create-tags \
  --resources "${VPC_ID}" \
  --tags Key=HotfixBy,Value=oncall-sre Key=HotfixDate,Value=2024-01-15

echo "Drift introduced: Added tags manually to VPC ${VPC_ID}"
```

#### Step 2.3: Detect drift

```bash
# Detect drift với refresh-only plan
terraform plan -refresh-only

# Expected output sẽ show diff:
# ~ aws_vpc.main
#     ~ tags = {
#         + "HotfixBy"   = "oncall-sre"
#         + "HotfixDate" = "2024-01-15"
#           ...
#       }
# Note: Objects have changed outside of Terraform
```

#### Step 2.4: Script drift detection

```bash
cat > ~/terraform-lab/scripts/detect-drift.sh << 'EOF'
#!/bin/bash
# detect-drift.sh - Check for infrastructure drift
set -e

TERRAFORM_DIR="${1:-./}"
EXIT_CODE=0

echo "=== Drift Detection ==="
echo "Directory: ${TERRAFORM_DIR}"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

cd "${TERRAFORM_DIR}"

# Run refresh-only plan, capture exit code
terraform plan -refresh-only -detailed-exitcode -out=/tmp/drift-plan.tfplan 2>&1
PLAN_EXIT="${?}"

case "${PLAN_EXIT}" in
  0)
    echo "✓ No drift detected. Infrastructure matches Terraform state."
    ;;
  1)
    echo "✗ Error running Terraform plan!"
    EXIT_CODE=1
    ;;
  2)
    echo "⚠ DRIFT DETECTED! Infrastructure differs from Terraform state."
    echo "Run 'terraform show /tmp/drift-plan.tfplan' to see details."
    echo ""
    echo "Options:"
    echo "  1. Apply drift back: terraform apply /tmp/drift-plan.tfplan"
    echo "  2. Import changes: Update Terraform code to match reality"
    EXIT_CODE=2
    ;;
esac

exit "${EXIT_CODE}"
EOF

chmod +x ~/terraform-lab/scripts/detect-drift.sh
bash ~/terraform-lab/scripts/detect-drift.sh ~/terraform-lab/platform/dev/foundation
```

---

### Part 3: Infracost Cost Estimation

#### Step 3.1: Cài đặt Infracost

```bash
# macOS
brew install infracost

# Linux
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Verify
infracost --version
# infracost v0.10.x
```

#### Step 3.2: Get API key

```bash
infracost auth login
# Mở browser, đăng ký tài khoản free
# API key được lưu vào ~/.config/infracost/credentials.yml
```

#### Step 3.3: Generate cost estimate

```bash
cd ~/terraform-lab/platform/dev/foundation

# Generate plan JSON
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > plan.json

# Run Infracost
infracost breakdown \
  --path plan.json \
  --format table

# Expected output:
# Name                                Monthly Qty  Unit   Monthly Cost
# aws_vpc.main
# └─ VPC                                          -            $0.00
#
# aws_subnet.private[0]
# └─ Subnet                                       -            $0.00
#
# OVERALL TOTAL                                               $0.00
# (VPC và subnets không tốn tiền, nhưng lab show workflow)
```

#### Step 3.4: So sánh cost trước và sau thay đổi

```bash
# Lưu baseline
infracost breakdown \
  --path plan.json \
  --format json \
  --out-file infracost-base.json

# Simulate thêm NAT Gateway (tốn tiền)
cat >> ~/terraform-lab/platform/dev/foundation/main.tf << 'EOF'

# NAT Gateway - expensive!
resource "aws_eip" "nat" {
  count  = 1
  domain = "vpc"
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_nat_gateway" "main" {
  count         = 1
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.private[0].id  # In real world, use public subnet

  depends_on = [aws_internet_gateway.main]
}
EOF

# Plan với thay đổi mới
terraform plan -out=tfplan-new.binary
terraform show -json tfplan-new.binary > plan-new.json

# Compare costs
infracost diff \
  --path plan-new.json \
  --compare-to infracost-base.json

# Expected output sẽ show NAT Gateway cost:
# + aws_nat_gateway.main[0]
#   + NAT gateway                        730  hours   $32.85
#   + Data processed                       -  GB           -
# Monthly cost change: +$32.85/month
# Yearly cost change:  +$394.20/year
```

#### Step 3.5: CI integration script

```bash
cat > ~/terraform-lab/scripts/cost-check.sh << 'EOF'
#!/bin/bash
# cost-check.sh - Check cost impact of Terraform changes
set -e

TERRAFORM_DIR="${1:-./}"
THRESHOLD="${2:-100}"  # Fail if monthly cost increase > $100

cd "${TERRAFORM_DIR}"

echo "=== Cost Impact Analysis ==="

# Generate new plan
terraform plan -out=/tmp/tfplan.binary -input=false
terraform show -json /tmp/tfplan.binary > /tmp/plan.json

# Check if baseline exists
if [ -f "infracost-base.json" ]; then
  # Compare with baseline
  DIFF_JSON=$(infracost diff \
    --path /tmp/plan.json \
    --compare-to infracost-base.json \
    --format json)

  MONTHLY_DIFF=$(echo "${DIFF_JSON}" | jq -r '.diffTotalMonthlyCost // "0"')
  
  echo "Monthly cost change: \$${MONTHLY_DIFF}"

  # Check threshold
  if (( $(echo "${MONTHLY_DIFF} > ${THRESHOLD}" | bc -l) )); then
    echo "ERROR: Cost increase \$${MONTHLY_DIFF}/month exceeds threshold \$${THRESHOLD}/month"
    echo "Please review and get budget approval before applying."
    exit 1
  fi
else
  echo "No baseline found. Generating initial estimate..."
  infracost breakdown --path /tmp/plan.json --format table
  infracost breakdown --path /tmp/plan.json --format json --out-file infracost-base.json
fi

echo "Cost check passed!"
EOF

chmod +x ~/terraform-lab/scripts/cost-check.sh
```

---

### Part 4: Policy as Code với OPA/Conftest

#### Step 4.1: Cài đặt Conftest

```bash
# macOS
brew install conftest

# Linux
VERSION=$(curl -s https://api.github.com/repos/open-policy-agent/conftest/releases/latest | jq -r .tag_name)
curl -Lo conftest.tar.gz "https://github.com/open-policy-agent/conftest/releases/download/${VERSION}/conftest_${VERSION#v}_Linux_x86_64.tar.gz"
tar xzf conftest.tar.gz
sudo mv conftest /usr/local/bin/

# Verify
conftest --version
```

#### Step 4.2: Tạo thư mục policies

```bash
mkdir -p ~/terraform-lab/policies
```

#### Step 4.3: Viết policy kiểm tra tags

```bash
cat > ~/terraform-lab/policies/required_tags.rego << 'EOF'
# required_tags.rego
# Enforce required tags trên tất cả AWS resources

package terraform.aws.tags

# Required tags mọi resource phải có
required_tags := {
  "Environment",
  "ManagedBy",
}

# Resources được exempt (managed services tự tạo tags)
exempt_resource_types := {
  "aws_iam_role_policy_attachment",
  "aws_iam_policy_attachment",
  "data.terraform_remote_state",
}

# Deny nếu resource không có required tags
deny[msg] {
  resource := input.resource_changes[_]
  
  # Chỉ check resources đang được create hoặc update
  resource.change.actions[_] == "create"
  
  # Không check exempt types
  not exempt_resource_types[resource.type]
  
  # Chỉ check AWS resources
  startswith(resource.type, "aws_")
  
  # Lấy tags sau khi apply
  tags := resource.change.after.tags

  # Tìm tag nào bị thiếu
  required_tag := required_tags[_]
  not tags[required_tag]

  msg := sprintf(
    "Resource '%s' (type: %s) is missing required tag '%s'",
    [resource.address, resource.type, required_tag]
  )
}
EOF
```

#### Step 4.4: Viết policy kiểm tra security group

```bash
cat > ~/terraform-lab/policies/security_group.rego << 'EOF'
# security_group.rego
# Enforce security group best practices

package terraform.aws.security

# Deny security group với SSH open to world
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group"
  resource.change.actions[_] == "create"

  ingress := resource.change.after.ingress[_]
  ingress.from_port <= 22
  ingress.to_port >= 22
  ingress.cidr_blocks[_] == "0.0.0.0/0"

  msg := sprintf(
    "SECURITY: Resource '%s' has SSH (port 22) open to 0.0.0.0/0. Use VPN or bastion host.",
    [resource.address]
  )
}

# Warn về port 3389 (RDP) open to world
warn[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group"
  resource.change.actions[_] == "create"

  ingress := resource.change.after.ingress[_]
  ingress.from_port <= 3389
  ingress.to_port >= 3389
  ingress.cidr_blocks[_] == "0.0.0.0/0"

  msg := sprintf(
    "WARNING: Resource '%s' has RDP (port 3389) open to 0.0.0.0/0",
    [resource.address]
  )
}
EOF
```

#### Step 4.5: Viết policy kiểm tra S3 encryption

```bash
cat > ~/terraform-lab/policies/s3_policy.rego << 'EOF'
# s3_policy.rego
# Enforce S3 security best practices

package terraform.aws.s3

# Deny S3 bucket không có server-side encryption
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  resource.change.actions[_] == "create"

  # Không có server_side_encryption_configuration
  not resource.change.after.server_side_encryption_configuration

  msg := sprintf(
    "S3 bucket '%s' must have server-side encryption enabled",
    [resource.address]
  )
}

# Deny S3 bucket không block public access
deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket_public_access_block"
  resource.change.actions[_] == "create"

  block_config := resource.change.after
  
  # Kiểm tra tất cả block đều true
  not (
    block_config.block_public_acls == true
    block_config.block_public_policy == true
    block_config.ignore_public_acls == true
    block_config.restrict_public_buckets == true
  )

  msg := sprintf(
    "S3 bucket public access block '%s' must have all options set to true",
    [resource.address]
  )
}
EOF
```

#### Step 4.6: Viết test cho policies

```bash
cat > ~/terraform-lab/policies/required_tags_test.rego << 'EOF'
# required_tags_test.rego
# Unit tests cho required_tags policy

package terraform.aws.tags

# Test: Resource có đủ tags → không bị deny
test_resource_with_all_tags {
  count(deny) == 0 with input as {
    "resource_changes": [{
      "address": "aws_vpc.main",
      "type": "aws_vpc",
      "change": {
        "actions": ["create"],
        "after": {
          "cidr_block": "10.0.0.0/16",
          "tags": {
            "Environment": "dev",
            "ManagedBy": "terraform"
          }
        }
      }
    }]
  }
}

# Test: Resource thiếu tag → phải bị deny
test_resource_missing_environment_tag {
  count(deny) == 1 with input as {
    "resource_changes": [{
      "address": "aws_vpc.bad",
      "type": "aws_vpc",
      "change": {
        "actions": ["create"],
        "after": {
          "cidr_block": "10.0.0.0/16",
          "tags": {
            "ManagedBy": "terraform"
            # Missing: Environment
          }
        }
      }
    }]
  }
}
EOF
```

#### Step 4.7: Generate plan và test policies

```bash
cd ~/terraform-lab/platform/dev/foundation

# Undo NAT gateway changes trước (revert file)
# Hoặc tạo fresh plan

terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > plan.json

# Run conftest với tất cả policies
conftest test plan.json \
  --policy ~/terraform-lab/policies/ \
  --all-namespaces

# Expected: có failures vì security group policy
```

#### Step 4.8: Test security group violation

```bash
# Tạo một plan với security group vi phạm
cat > /tmp/bad-sg-plan.json << 'EOF'
{
  "resource_changes": [
    {
      "address": "aws_security_group.bad",
      "type": "aws_security_group",
      "change": {
        "actions": ["create"],
        "after": {
          "name": "bad-sg",
          "ingress": [
            {
              "from_port": 22,
              "to_port": 22,
              "protocol": "tcp",
              "cidr_blocks": ["0.0.0.0/0"],
              "description": ""
            }
          ],
          "tags": {
            "Environment": "dev",
            "ManagedBy": "terraform"
          }
        }
      }
    }
  ]
}
EOF

# Test policy với plan xấu
conftest test /tmp/bad-sg-plan.json \
  --policy ~/terraform-lab/policies/ \
  --namespace terraform.aws.security

# Expected output:
# FAIL - /tmp/bad-sg-plan.json - terraform.aws.security - SECURITY: Resource 'aws_security_group.bad' has SSH (port 22) open to 0.0.0.0/0. Use VPN or bastion host.
# 1 test, 0 passed, 0 warnings, 1 failure, 0 exceptions
```

#### Step 4.9: Run policy unit tests

```bash
conftest verify \
  --policy ~/terraform-lab/policies/

# Expected:
# PASS - required_tags_test.rego - data.terraform.aws.tags.test_resource_with_all_tags
# PASS - required_tags_test.rego - data.terraform.aws.tags.test_resource_missing_environment_tag
# 2 tests, 2 passed, 0 warnings, 0 failures
```

#### Step 4.10: Integrate vào CI script

```bash
cat > ~/terraform-lab/scripts/policy-check.sh << 'EOF'
#!/bin/bash
# policy-check.sh - Run policy checks on Terraform plan
set -e

TERRAFORM_DIR="${1:-./}"
POLICY_DIR="${2:-~/terraform-lab/policies}"

cd "${TERRAFORM_DIR}"

echo "=== Policy Check ==="
echo "Policies: ${POLICY_DIR}"
echo ""

# Generate plan
terraform plan -out=/tmp/tfplan.binary -input=false
terraform show -json /tmp/tfplan.binary > /tmp/plan.json

# Run conftest
if conftest test /tmp/plan.json \
  --policy "${POLICY_DIR}" \
  --all-namespaces; then
  echo ""
  echo "✓ All policy checks passed!"
else
  echo ""
  echo "✗ Policy violations found. Fix issues before applying."
  exit 1
fi
EOF

chmod +x ~/terraform-lab/scripts/policy-check.sh
```

### Cleanup

```bash
# Destroy resources tạo trong lab
cd ~/terraform-lab/platform/dev/foundation
terraform destroy -auto-approve

# Remove lab files (optional)
# rm -rf ~/terraform-lab
```

---

## 6. Kiểm tra hiểu bài

**Câu 1**: Bạn có một Terraform monolith với 200 resources trong một state. Team bắt đầu complain về slow plan time (5 phút). Bạn sẽ refactor state layout như thế nào? Liệt kê các bước cụ thể và risk cần quản lý.

**Câu 2**: Một developer remove output `private_subnet_ids` từ foundation module mà không kiểm tra dependents. Apps layer đang dùng output này qua `remote_state`. Điều gì xảy ra? Làm thế nào để phòng ngừa tình huống này?

**Câu 3**: Team detect drift: SRE đã thêm một inbound rule vào security group lúc 2AM để fix incident. Hôm nay Terraform plan muốn xóa rule đó. Bạn sẽ xử lý thế nào? Có ba approaches, hãy so sánh trade-offs.

**Câu 4**: Viết Rego policy để enforce: không có RDS instance nào có `publicly_accessible = true`. Kèm theo một unit test case cho policy đó.

**Câu 5**: Team đang cân nhắc giữa OPA/Conftest và Sentinel để enforce Terraform policies. Team dùng Terraform Cloud. Bạn recommend cái nào và tại sao?

---

## 7. Tóm tắt cuối ngày

### 5 điểm quan trọng nhất

1. **State layout là kiến trúc quyết định**: Monolithic state = single point of failure. Split theo env + domain giảm blast radius và cho phép team làm việc độc lập.

2. **Remote state data source = loose coupling giữa layers**: Luôn version outputs, coi output contract như API contract. Breaking change trong output = breaking change cho consumer.

3. **Drift xảy ra liên tục trong production**: Scheduled drift detection (daily minimum) là bắt buộc. Auto-apply drift correction nguy hiểm - luôn human review cho production.

4. **Infracost trong PR = cost awareness sớm**: $3,000/month surprise có thể tránh được nếu developer thấy cost impact ngay trong PR comment.

5. **Policy as Code là defense in depth**: Code review không đủ. Conftest + OPA block misconfigurations trước khi reach production. Tests cho policies cũng quan trọng như tests cho application code.

### Output của ngày học

- State layout design cho microservices platform (foundation, data, apps layers)
- Remote state data source implementation với local backend
- Drift detection script với automated reporting
- Infracost integration cho cost estimation
- OPA/Conftest policies cho tags, security groups, S3 encryption
- Unit tests cho Rego policies

### Chuẩn bị cho Day 13 - Ansible Practical

Phase 3 bắt đầu với **Ansible**. Ngày mai bạn sẽ học:
- Ansible architecture: control node, managed nodes, inventory
- Playbooks, roles, handlers
- Ansible so với Terraform: khi nào dùng cái nào
- Tại sao cần Ansible khi đã có Terraform? (configuration management vs provisioning)

Chuẩn bị: Đảm bảo có ít nhất 2 VMs hoặc containers để test Ansible (một control node, một managed node).

---

## 8. Tham khảo thêm

### Official Documentation

- [Terraform Remote State](https://developer.hashicorp.com/terraform/language/state/remote-state-data) - Chính thức từ HashiCorp
- [Terraform Backend Configuration](https://developer.hashicorp.com/terraform/language/settings/backends/configuration) - Backend types và config
- [OPA Documentation](https://www.openpolicyagent.org/docs/latest/) - Open Policy Agent official docs
- [Conftest Documentation](https://www.conftest.dev/) - CLI tool for OPA
- [Infracost Documentation](https://www.infracost.io/docs/) - Cost estimation tool
- [Sentinel by HashiCorp](https://developer.hashicorp.com/sentinel) - Policy as Code for TFC/TFE

### Quality Tech Blogs

- [Terraform Best Practices](https://www.terraform-best-practices.com/) - Community-maintained best practices
- [How to manage Terraform state](https://blog.gruntwork.io/how-to-manage-terraform-state-28f5697e68bb) - Gruntwork blog, foundational
- [Testing Terraform with OPA](https://www.openpolicyagent.org/docs/latest/terraform/) - OPA guide cho Terraform

### Tools

- [Terragrunt](https://terragrunt.gruntwork.io/) - Wrapper giúp manage multiple state files
- [Driftctl](https://driftctl.com/) - Dedicated drift detection tool
- [Checkov](https://www.checkov.io/) - Static analysis cho Terraform (alternative/complement to OPA)
- [tfsec](https://aquasecurity.github.io/tfsec/) - Security scanner cho Terraform code
