# Day 11: Terraform CI/CD, OIDC, Quality Gates

**Thời gian:** 2 giờ | **Level:** Intermediate-Advanced | **Phase:** 2 - Terraform Production, Day 5

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Thiết kế và triển khai một GitHub Actions workflow hoàn chỉnh cho Terraform với các bước fmt, validate, lint, security scan, plan, và apply có manual approval.
- Cấu hình GitHub Actions OIDC để xác thực với AWS mà không cần long-lived credentials, loại bỏ hoàn toàn việc lưu `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` trong secrets.
- Sử dụng `tflint`, `trivy config`, và `checkov` như các quality gates bắt buộc trong CI pipeline, hiểu rõ mỗi tool kiểm tra cái gì.
- Phân biệt khi nào dùng PR-based workflow (plan-on-PR, apply-on-merge) vs. manual approval gate, và trade-off của từng cách.
- Debug các lỗi phổ biến trong Terraform CI: state lock, permission denied, plan drift, OIDC token failure.

---

## 2. Bối cảnh thực tế

### Vấn đề khi không có CI/CD cho Terraform

Bạn đang làm senior developer. Bạn quen với CI/CD cho application code: push code → test → build → deploy. Terraform cũng cần điều đó, nhưng hầu hết team bắt đầu với Terraform theo cách này:

```
Developer A: terraform apply   # từ laptop cá nhân
Developer B: terraform apply   # từ laptop khác, state cũ
Ops: terraform apply           # AWS key hardcode trong ~/.aws/credentials
```

Hệ quả trong thực tế:

- **"Worked on my machine"**: Developer A apply thành công, Developer B apply ra kết quả khác vì local module version khác nhau.
- **State drift**: Ai đó apply từ branch cũ, overwrite changes của người khác.
- **Leaked credentials**: AWS key được commit vào repo, hoặc expire giữa chừng khi pipeline đang chạy.
- **Không có audit trail**: 3 tháng sau không biết ai apply cái gì, khi nào, với state nào.
- **"Shadow infra"**: Ai đó tạo resource thủ công trên console, không qua Terraform, gây drift.

Trong một team 5 người, bạn sẽ gặp ít nhất 2 trong số này trong tháng đầu. Trong một startup 30 người, tất cả đều xảy ra.

### Terraform CI/CD giải quyết gì?

```
Pull Request → [fmt] → [validate] → [tflint] → [security scan] → [plan] → Review
Merge to main → [apply] → [với manual approval nếu production]
```

- **Consistency**: Mọi apply đều chạy từ cùng một môi trường (GitHub Actions runner), cùng Terraform version, cùng provider version.
- **Visibility**: Terraform plan output hiện ngay trong PR comment — reviewer thấy được "sẽ destroy 3 resources" trước khi approve.
- **Security**: Không ai có AWS key cá nhân. GitHub Actions dùng OIDC để lấy temporary credentials.
- **Audit**: Mọi apply đều có link đến PR, commit, và người trigger.

---

## 3. Kiến thức nền tảng (30 phút)

### 3.1 Tại sao cần quality gates?

Bạn đã làm việc với TypeScript strict mode, ESLint, Prettier. Đó là quality gates cho application code. Terraform cần equivalent:

| Application Code | Terraform Equivalent | Mục đích |
|---|---|---|
| Prettier | `terraform fmt` | Format nhất quán |
| TypeScript compiler | `terraform validate` | Syntax + schema check |
| ESLint | `tflint` | Logic errors, best practices |
| Snyk / Semgrep | `checkov` / `trivy config` | Security vulnerabilities |
| Jest / Pytest | Terraform test (Day 14) | Functional testing |

Từng tool kiểm tra ở một layer khác nhau. Chúng bổ sung, không thay thế nhau.

### 3.2 Từng tool làm gì?

#### `terraform fmt`

Chỉ format code. Không validate logic. Tương tự `gofmt` hoặc `prettier`.

```bash
terraform fmt -check -recursive  # exit code 1 nếu có file không đúng format
terraform fmt -recursive          # tự fix
```

Chạy `fmt -check` trong CI để pipeline fail nếu ai quên format. Đây là lỗi thường gặp nhất và cũng dễ fix nhất — không có lý do để bỏ qua.

#### `terraform validate`

Kiểm tra syntax và schema của Terraform configuration, nhưng **không chạm vào cloud**. Nó verify:
- HCL syntax hợp lệ
- Tất cả required attributes có mặt
- Resource type và attribute names đúng theo provider schema
- Variable references hợp lệ

```bash
terraform init -backend=false  # cần init trước, không cần backend
terraform validate
```

Nó **không** kiểm tra: giá trị runtime (ví dụ: AMI ID có tồn tại không), network connectivity, IAM permissions.

#### `tflint`

Linter cho Terraform. Giống ESLint nhưng hiểu Terraform semantics. Tìm:
- AWS-specific issues: sử dụng deprecated instance types, invalid region names
- Best practices: missing tags, missing variable descriptions
- Security lint: public S3 bucket, security group ingress từ 0.0.0.0/0

```bash
# Cài plugin cho AWS
tflint --init
tflint --recursive
```

File `.tflint.hcl`:
```hcl
plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}
```

#### `checkov`

Static analysis tool cho IaC security và compliance. Có hơn 1000 built-in policies theo CIS Benchmarks, HIPAA, PCI-DSS, SOC2. Kiểm tra:
- S3 bucket có bật versioning và encryption không
- Security group có ingress từ 0.0.0.0/0 không
- IAM role có quá nhiều wildcard permissions không
- RDS có múlti-AZ, encryption at rest không

```bash
checkov -d . --framework terraform
checkov -d . --framework terraform --output json  # machine-readable cho CI
```

#### `trivy config`

Tool của Aqua Security. Tương tự checkov nhưng nhẹ hơn, faster, và có thể scan nhiều loại file (Docker, K8s manifests, Terraform). Trong Terraform pipeline thường dùng song song hoặc thay thế checkov.

```bash
trivy config .
trivy config --severity HIGH,CRITICAL .  # chỉ fail với HIGH/CRITICAL
```

**Trade-off checkov vs trivy config:**
- `checkov`: nhiều rules hơn, output detail hơn, cần Python
- `trivy config`: nhanh hơn, single binary, integration tốt với container scanning pipeline

### 3.3 PR-based Workflow

Đây là pattern chuẩn trong production:

```
┌─────────────────────────────────────────────────────────┐
│                    Pull Request Flow                      │
│                                                           │
│  feature branch ──push──► PR opened/updated              │
│                                ↓                          │
│                         [CI Pipeline]                     │
│                    fmt → validate → tflint                │
│                         → security scan                   │
│                         → terraform plan                  │
│                              ↓                            │
│                    Plan output posted as PR comment        │
│                              ↓                            │
│                    Reviewer sees: "+ 3 to add, 0 to change│
│                    - 0 to destroy" → approves PR          │
│                              ↓                            │
│  main branch ◄──merge──── PR approved                    │
│                              ↓                            │
│                    [CD Pipeline on main]                  │
│                    terraform plan (confirm)               │
│                         → terraform apply                 │
│                    (với manual approval cho production)    │
└─────────────────────────────────────────────────────────┘
```

**Tại sao chạy plan 2 lần?** Vì giữa thời điểm PR được approve và merge vào main, có thể có thêm commits khác merge vào. Plan trên main đảm bảo bạn apply đúng state.

### 3.4 GitHub Actions OIDC — Không còn long-lived credentials

#### Vấn đề với static credentials

Cách cũ:
```yaml
env:
  AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
  AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Rủi ro:
- Key không expire → nếu leak, attacker có access lâu dài.
- Cần rotate thủ công → thường bị quên.
- Key được lưu trong GitHub Secrets — GitHub có thể bị compromise.
- Ai có access vào repo settings đều thấy key đang active (dù không thấy value).

#### OIDC là gì?

OIDC (OpenID Connect) cho phép GitHub Actions **chứng minh identity** với AWS thông qua JWT token, thay vì dùng static password.

Flow:
```
GitHub Actions Runner
        │
        ├── 1. Request OIDC token from GitHub
        │         (JWT signed by GitHub, contains: repo name, branch, workflow)
        │
        ├── 2. Gửi JWT token đến AWS STS AssumeRoleWithWebIdentity
        │
AWS STS ├── 3. Verify JWT với GitHub OIDC endpoint
        │         (https://token.actions.githubusercontent.com)
        │
        ├── 4. Check Trust Policy: repo này có được phép assume role này không?
        │
        └── 5. Trả về temporary credentials (15 phút mặc định)
                  AWS_ACCESS_KEY_ID (temp)
                  AWS_SECRET_ACCESS_KEY (temp)
                  AWS_SESSION_TOKEN
```

Temporary credentials tự expire sau 15-60 phút. Không cần lưu secret nào trong GitHub.

#### AWS IAM Trust Policy cho OIDC

```hcl
# Tạo OIDC Provider cho GitHub Actions
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # Thumbprint của GitHub OIDC endpoint
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "github-actions-oidc"
  }
}

# IAM Role được assume bởi GitHub Actions
resource "aws_iam_role" "github_actions_terraform" {
  name = "github-actions-terraform-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Chỉ cho phép repo cụ thể và branch cụ thể
            "token.actions.githubusercontent.com:sub" = "repo:your-org/your-repo:*"
          }
        }
      }
    ]
  })
}
```

**Condition `sub` quan trọng**. Nếu bỏ hoặc dùng wildcard quá rộng, bất kỳ repo nào trong org đều có thể assume role này. Restrict xuống branch nếu cần:

```
"repo:your-org/your-repo:ref:refs/heads/main"  # chỉ main branch
"repo:your-org/your-repo:environment:production" # chỉ environment cụ thể
```

---

## 4. Deep Dive & Trade-offs (30 phút)

### 4.1 So sánh các workflow patterns

#### Pattern A: Plan-on-PR, Apply-on-Merge (khuyến nghị cho dev/staging)

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
```

- PR trigger: chạy quality gates + plan, post comment
- Push to main trigger: chạy apply

**Pros:** Simple, ít complexity, phù hợp team nhỏ.
**Cons:** Không có gate giữa plan và apply — merge = apply tự động.

#### Pattern B: Manual Approval Gate (khuyến nghị cho production)

```yaml
jobs:
  plan:
    runs-on: ubuntu-latest
    outputs:
      plan_exit_code: ${{ steps.plan.outputs.exit_code }}

  apply:
    needs: plan
    environment: production  # <-- tạo manual approval requirement
    runs-on: ubuntu-latest
```

GitHub Environment với required reviewers: người trigger workflow phải chờ reviewer approve trước khi job `apply` chạy. Reviewer thấy plan output trước khi quyết định.

**Pros:** Explicit control, audit trail rõ ràng.
**Cons:** Cần setup GitHub Environment, thêm friction.

#### Pattern C: Atlantis (self-hosted bot)

Tool chuyên biệt cho Terraform workflow. Chạy plan/apply từ PR comments (`atlantis plan`, `atlantis apply`).

**Pros:** UX tốt hơn, built-in locking.
**Cons:** Phải tự host, thêm infrastructure để maintain. Không phù hợp nếu team chưa có platform team.

#### Comparison table theo context

| Context | Khuyến nghị | Lý do |
|---|---|---|
| Cá nhân / pet project | GitHub Actions pattern A | Đơn giản nhất |
| Startup (dev/staging) | GitHub Actions pattern A | Tốc độ > safety |
| Startup (production) | GitHub Actions pattern B | Cần gate |
| Team 10-50 người | GitHub Actions pattern B + OIDC | Balance tốt |
| Enterprise / Bank | Pattern B + Terraform Cloud / TFC | Audit, SSO, policy |
| Regulated (HIPAA, PCI) | Terraform Enterprise + OPA Policy | Compliance proof |

### 4.2 Khi nào dùng checkov vs trivy config?

| | checkov | trivy config |
|---|---|---|
| Số lượng rules | ~1500+ | ~800+ |
| Tốc độ | Chậm hơn (Python) | Nhanh hơn (Go binary) |
| Output detail | Rất chi tiết, có remediation link | Đủ dùng, concise |
| Framework support | Terraform, CFN, K8s, ARM, Docker | Terraform, K8s, Docker, Helm |
| Tích hợp container scan | Không | Có (cùng `trivy image`) |
| Suppress findings | `.checkov.yaml` | `.trivyignore` |

**Khuyến nghị:** Dùng `trivy config` nếu team đã dùng Trivy cho container scanning — one tool, consistent experience. Dùng `checkov` nếu cần nhiều rules hơn và compliance reporting (CIS report, HIPAA).

### 4.3 State lock và concurrency trong CI

**Vấn đề:** Hai workflow chạy đồng thời (ví dụ: 2 PR merge gần như cùng lúc). Cả hai đều cố apply → state lock contention.

**Giải pháp 1: GitHub Actions concurrency group**

```yaml
concurrency:
  group: terraform-${{ github.ref }}
  cancel-in-progress: false  # QUAN TRỌNG: không cancel apply đang chạy
```

`cancel-in-progress: false` với Terraform apply là bắt buộc. Nếu cancel giữa apply, state có thể bị corrupt hoặc resource ở trạng thái partial.

**Giải pháp 2: Terraform Cloud Remote State Locking**

Nếu dùng S3 backend với DynamoDB lock table, lock tự động xảy ra. Workflow thứ hai sẽ wait hoặc fail với error `Error locking state`. Nên handle error này và retry.

### 4.4 Security hardening cho Terraform CI

**Principle of Least Privilege cho OIDC role:**

```hcl
# Thay vì AdministratorAccess, grant chỉ quyền cần thiết
resource "aws_iam_role_policy" "terraform_minimal" {
  name = "terraform-minimal-policy"
  role = aws_iam_role.github_actions_terraform.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Đọc state từ S3
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::your-terraform-state-bucket/path/*"
      },
      # Lock DynamoDB
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = "arn:aws:dynamodb:*:*:table/terraform-state-lock"
      },
      # Các quyền Terraform cần để manage resources
      # ... (chỉ grant những gì module cần)
    ]
  })
}
```

**Plan-only role vs Apply role:**

Pattern tốt nhất: tạo 2 roles khác nhau.
- `github-actions-terraform-plan`: read-only permissions, assume được từ PR workflows.
- `github-actions-terraform-apply`: full permissions, assume được chỉ từ main branch hoặc environment-gated workflows.

```hcl
# Apply role chỉ cho phép main branch
Condition = {
  StringEquals = {
    "token.actions.githubusercontent.com:sub" = "repo:your-org/your-repo:ref:refs/heads/main"
  }
}
```

### 4.5 Common pitfalls

**Pitfall 1: Commit `terraform plan` output vào repo**

Một số team lưu plan output (file `.tfplan`) vào artifact. Điều này OK và nên làm — bạn apply chính xác plan đã review. Nhưng đừng commit `.tfplan` vào Git (chứa sensitive data).

```yaml
- name: Save plan
  run: terraform plan -out=tfplan
- uses: actions/upload-artifact@v4
  with:
    name: terraform-plan
    path: tfplan
    retention-days: 1  # Xóa sau 1 ngày
```

**Pitfall 2: `terraform validate` fails trong CI vì không có credentials**

`terraform validate` không cần credentials, nhưng cần `terraform init`. Nhiều providers require init trước khi validate. Dùng `terraform init -backend=false` để skip backend initialization.

```yaml
- run: terraform init -backend=false
- run: terraform validate
```

**Pitfall 3: tflint không tìm thấy provider plugin**

tflint cần download ruleset. Trong môi trường offline hoặc CI không có internet, sẽ fail. Giải pháp: cache tflint plugin.

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.tflint.d/plugins
    key: tflint-${{ hashFiles('.tflint.hcl') }}
```

---

## 5. Hands-on Lab (60 phút)

### Chuẩn bị

**Yêu cầu:**
- GitHub repository (public hoặc private)
- AWS account với quyền tạo IAM roles
- Terraform code từ Day 1-10 (hoặc tạo mới theo hướng dẫn)

**Cost warning:** Lab này không tạo expensive resources. Chi phí chính là DynamoDB (fractions of cent) và S3 (< $0.01/month cho state files nhỏ). OIDC infrastructure bản thân free. Tuy nhiên, khi workflow chạy terraform apply, resources được tạo sẽ phát sinh cost.

### Step 1: Chuẩn bị Terraform code cơ bản

Tạo structure sau trong repository:

```
.
├── .github/
│   └── workflows/
│       └── terraform.yml
├── .tflint.hcl
├── .trivyignore          (nếu cần suppress false positives)
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   └── backend.tf
└── modules/
    └── oidc/
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

Tạo `infra/providers.tf`:

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = var.environment
      Project     = "terraform-cicd-lab"
    }
  }
}
```

Tạo `infra/variables.tf`:

```hcl
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}
```

Tạo `infra/backend.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"   # Thay bằng bucket thực
    key            = "day-11-lab/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### Step 2: Tạo OIDC module

Tạo `modules/oidc/main.tf`:

```hcl
# OIDC Provider cho GitHub Actions
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # Thumbprint hiện tại của GitHub OIDC endpoint
  # Kiểm tra tại: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Name = "github-actions-oidc-provider"
  }
}

# IAM Role cho Plan (PR workflows) - read-only ish
resource "aws_iam_role" "github_actions_plan" {
  name        = "${var.name_prefix}-plan-role"
  description = "Role for GitHub Actions Terraform plan (PRs)"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Cho phép tất cả branches và PRs trong repo
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:*"
          }
        }
      }
    ]
  })

  tags = {
    Name    = "${var.name_prefix}-plan-role"
    Purpose = "terraform-plan"
  }
}

# IAM Role cho Apply (main branch only)
resource "aws_iam_role" "github_actions_apply" {
  name        = "${var.name_prefix}-apply-role"
  description = "Role for GitHub Actions Terraform apply (main branch only)"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            # Chỉ cho phép main branch
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  tags = {
    Name    = "${var.name_prefix}-apply-role"
    Purpose = "terraform-apply"
  }
}

# Policy cho Plan role: chỉ cần read state và quyền read AWS resources
resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.github_actions_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Thêm quyền write state cho plan role (plan cần lock state)
resource "aws_iam_role_policy" "plan_state_write" {
  name = "terraform-state-access"
  role = aws_iam_role.github_actions_plan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.state_bucket}",
          "arn:aws:s3:::${var.state_bucket}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:DescribeTable"
        ]
        Resource = "arn:aws:dynamodb:*:*:table/${var.lock_table}"
      }
    ]
  })
}

# Apply role: AdministratorAccess để apply bất kỳ resource nào
# Trong production thực tế, grant chỉ quyền cần thiết cho từng module
resource "aws_iam_role_policy_attachment" "apply_admin" {
  role       = aws_iam_role.github_actions_apply.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```

Tạo `modules/oidc/variables.tf`:

```hcl
variable "name_prefix" {
  description = "Prefix for IAM resource names"
  type        = string
}

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

variable "state_bucket" {
  description = "S3 bucket name for Terraform state"
  type        = string
}

variable "lock_table" {
  description = "DynamoDB table name for state locking"
  type        = string
}
```

Tạo `modules/oidc/outputs.tf`:

```hcl
output "plan_role_arn" {
  description = "ARN of the IAM role for Terraform plan"
  value       = aws_iam_role.github_actions_plan.arn
}

output "apply_role_arn" {
  description = "ARN of the IAM role for Terraform apply"
  value       = aws_iam_role.github_actions_apply.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider"
  value       = aws_iam_openid_connect_provider.github_actions.arn
}
```

### Step 3: Gọi OIDC module từ main config

Tạo `infra/main.tf`:

```hcl
module "github_oidc" {
  source = "../modules/oidc"

  name_prefix  = "terraform-cicd-lab"
  github_org   = var.github_org
  github_repo  = var.github_repo
  state_bucket = "your-terraform-state-bucket"  # Thay bằng bucket thực
  lock_table   = "terraform-state-lock"
}
```

Tạo `infra/outputs.tf`:

```hcl
output "plan_role_arn" {
  description = "Use this ARN in GitHub Actions for plan jobs"
  value       = module.github_oidc.plan_role_arn
}

output "apply_role_arn" {
  description = "Use this ARN in GitHub Actions for apply jobs"
  value       = module.github_oidc.apply_role_arn
}
```

### Step 4: Tạo tflint config

Tạo `.tflint.hcl` ở root:

```hcl
plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

# Bắt buộc khai báo required_version
rule "terraform_required_version" {
  enabled = true
}

# Bắt buộc khai báo required_providers
rule "terraform_required_providers" {
  enabled = true
}

# Cảnh báo nếu variable không có description
rule "terraform_documented_variables" {
  enabled = true
}

# Cảnh báo nếu output không có description
rule "terraform_documented_outputs" {
  enabled = true
}

# Cảnh báo deprecated interpolation syntax
rule "terraform_deprecated_interpolation" {
  enabled = true
}

# Kiểm tra naming convention
rule "terraform_naming_convention" {
  enabled = true

  resource {
    format = "snake_case"
  }

  variable {
    format = "snake_case"
  }
}
```

### Step 5: Tạo GitHub Actions workflow

Tạo `.github/workflows/terraform.yml`:

```yaml
name: Terraform CI/CD

on:
  pull_request:
    branches: [main]
    paths:
      - 'infra/**'
      - 'modules/**'
      - '.github/workflows/terraform.yml'
  push:
    branches: [main]
    paths:
      - 'infra/**'
      - 'modules/**'

# Ngăn chặn concurrent applies
concurrency:
  group: terraform-${{ github.ref }}
  cancel-in-progress: false

env:
  TF_VERSION: "1.8.0"
  WORKING_DIR: "./infra"

permissions:
  id-token: write    # Cần để request OIDC token
  contents: read
  pull-requests: write  # Cần để post comment lên PR

jobs:
  # ============================================================
  # Job 1: Quality Gates (chạy trên cả PR và push to main)
  # ============================================================
  quality-gates:
    name: Quality Gates
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      # terraform fmt: kiểm tra format, không sửa
      - name: Terraform Format Check
        run: terraform fmt -check -recursive
        working-directory: .

      # terraform init không cần backend cho validate
      - name: Terraform Init (no backend)
        run: terraform init -backend=false

      # terraform validate
      - name: Terraform Validate
        run: terraform validate

      # tflint
      - name: Setup TFLint
        uses: terraform-linters/setup-tflint@v4
        with:
          tflint_version: v0.51.0

      - name: Cache TFLint plugins
        uses: actions/cache@v4
        with:
          path: ~/.tflint.d/plugins
          key: tflint-${{ runner.os }}-${{ hashFiles('.tflint.hcl') }}

      - name: TFLint Init
        run: tflint --init
        working-directory: .

      - name: TFLint Run
        run: tflint --recursive --format compact
        working-directory: .

      # Trivy security scan
      - name: Trivy Config Scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: config
          scan-ref: .
          severity: HIGH,CRITICAL
          exit-code: 1  # Fail pipeline nếu có HIGH hoặc CRITICAL
          format: table

      # Checkov security scan (bổ sung cho trivy)
      - name: Checkov Scan
        uses: bridgecrewio/checkov-action@master
        with:
          directory: .
          framework: terraform
          output_format: cli
          soft_fail: false  # Fail pipeline nếu có violations
          skip_check: CKV_AWS_18  # Ví dụ: skip rule cụ thể nếu cần

  # ============================================================
  # Job 2: Terraform Plan (cho PR và main branch)
  # ============================================================
  terraform-plan:
    name: Terraform Plan
    runs-on: ubuntu-latest
    needs: quality-gates
    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    # Output để job apply biết có gì thay đổi không
    outputs:
      plan_exit_code: ${{ steps.plan.outputs.exitcode }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}
          terraform_wrapper: true  # Cần để capture exitcode

      # Authenticate với AWS qua OIDC
      - name: Configure AWS Credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/terraform-cicd-lab-plan-role
          aws-region: ap-southeast-1
          role-session-name: github-actions-plan-${{ github.run_id }}

      - name: Terraform Init
        run: |
          terraform init \
            -backend-config="bucket=your-terraform-state-bucket" \
            -backend-config="key=day-11-lab/terraform.tfstate" \
            -backend-config="region=ap-southeast-1"

      # Chạy plan, capture output
      - name: Terraform Plan
        id: plan
        run: |
          terraform plan \
            -var="environment=dev" \
            -var="github_org=${{ github.repository_owner }}" \
            -var="github_repo=${{ github.event.repository.name }}" \
            -out=tfplan \
            -detailed-exitcode 2>&1 | tee plan_output.txt
          echo "exitcode=${PIPESTATUS[0]}" >> $GITHUB_OUTPUT
        continue-on-error: true  # Xử lý exit codes khác nhau

      # Upload plan artifact để apply job dùng
      - name: Upload Plan
        uses: actions/upload-artifact@v4
        if: steps.plan.outputs.exitcode == '2'  # Chỉ upload nếu có changes
        with:
          name: terraform-plan-${{ github.run_id }}
          path: ${{ env.WORKING_DIR }}/tfplan
          retention-days: 1

      # Post plan output vào PR comment
      - name: Post Plan to PR
        uses: actions/github-script@v7
        if: github.event_name == 'pull_request'
        with:
          script: |
            const fs = require('fs');
            const planOutput = fs.readFileSync('${{ env.WORKING_DIR }}/plan_output.txt', 'utf8');
            const exitCode = '${{ steps.plan.outputs.exitcode }}';

            const status = exitCode === '0' ? '✅ No changes' :
                          exitCode === '2' ? '⚠️ Changes detected' :
                          '❌ Plan failed';

            const body = `## Terraform Plan - ${status}

            <details>
            <summary>Plan Output (click to expand)</summary>

            \`\`\`terraform
            ${planOutput.substring(0, 60000)}  // GitHub comment limit
            \`\`\`
            </details>

            *Triggered by: @${{ github.actor }} | Commit: ${{ github.sha }}*`;

            // Tìm và update comment cũ nếu có, tránh spam
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });

            const botComment = comments.find(comment =>
              comment.user.type === 'Bot' &&
              comment.body.includes('## Terraform Plan')
            );

            if (botComment) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: botComment.id,
                body: body,
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: body,
              });
            }

      # Fail job nếu plan thực sự bị lỗi (exit code 1)
      - name: Check Plan Result
        if: steps.plan.outputs.exitcode == '1'
        run: exit 1

  # ============================================================
  # Job 3: Terraform Apply (chỉ chạy khi merge vào main)
  # ============================================================
  terraform-apply:
    name: Terraform Apply
    runs-on: ubuntu-latest
    needs: terraform-plan
    # Chỉ chạy khi push to main VÀ có changes
    if: |
      github.event_name == 'push' &&
      github.ref == 'refs/heads/main' &&
      needs.terraform-plan.outputs.plan_exit_code == '2'

    # environment với required reviewers tạo manual approval gate
    environment: production

    defaults:
      run:
        working-directory: ${{ env.WORKING_DIR }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      # Apply role có nhiều quyền hơn plan role
      - name: Configure AWS Credentials (OIDC - Apply)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/terraform-cicd-lab-apply-role
          aws-region: ap-southeast-1
          role-session-name: github-actions-apply-${{ github.run_id }}

      - name: Terraform Init
        run: |
          terraform init \
            -backend-config="bucket=your-terraform-state-bucket" \
            -backend-config="key=day-11-lab/terraform.tfstate" \
            -backend-config="region=ap-southeast-1"

      # Download plan artifact từ plan job
      - name: Download Plan
        uses: actions/download-artifact@v4
        with:
          name: terraform-plan-${{ github.run_id }}
          path: ${{ env.WORKING_DIR }}

      # Apply chính xác plan đã được review
      - name: Terraform Apply
        run: terraform apply -auto-approve tfplan

      # Notify sau khi apply thành công
      - name: Apply Summary
        if: success()
        run: |
          echo "## Apply completed successfully" >> $GITHUB_STEP_SUMMARY
          echo "- **Triggered by:** ${{ github.actor }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Commit:** ${{ github.sha }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Time:** $(date -u)" >> $GITHUB_STEP_SUMMARY
```

### Step 6: Bootstrap — Apply OIDC infrastructure lần đầu

Lần đầu, chưa có OIDC role nên phải apply bằng local credentials:

```bash
cd infra

# Dùng local credentials (chỉ lần này)
export AWS_PROFILE=your-admin-profile

terraform init
terraform apply \
  -var="environment=dev" \
  -var="github_org=your-github-org" \
  -var="github_repo=your-repo-name"
```

Expected output:
```
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:
plan_role_arn = "arn:aws:iam::123456789012:role/terraform-cicd-lab-plan-role"
apply_role_arn = "arn:aws:iam::123456789012:role/terraform-cicd-lab-apply-role"
```

Lấy ARNs từ output và update vào workflow file (thay `123456789012` bằng account ID thực).

### Step 7: Cấu hình GitHub Environment

1. Vào repo GitHub → Settings → Environments → New environment → đặt tên `production`
2. Tick "Required reviewers", thêm tên của bạn hoặc team
3. Tick "Prevent self-review" nếu cần (reviewer không thể là người trigger)

### Step 8: Test workflow

```bash
# Tạo branch mới
git checkout -b feature/test-cicd

# Tạo một thay đổi nhỏ (thêm tag)
# Trong infra/main.tf, thêm một tag vào module

# Commit với format không đúng (để test fmt check)
# Thêm dòng có trailing whitespace

git add .
git commit -m "test: verify CI pipeline"
git push origin feature/test-cicd
```

Mở PR trên GitHub. Quan sát:

1. `quality-gates` job chạy → `terraform fmt` fail vì trailing whitespace
2. Fix format: `terraform fmt -recursive` → commit → push
3. Quality gates pass → plan job chạy
4. Plan output xuất hiện trong PR comment
5. Merge PR → apply job trigger → manual approval gate xuất hiện
6. Approve → apply chạy

### Step 9: Verify OIDC không dùng static credentials

Trong GitHub Actions run log, tìm step "Configure AWS Credentials":

```
Assuming role arn:aws:iam::123456789012:role/terraform-cicd-lab-plan-role
Role assummed, credentials will expire at: 2024-01-01T12:15:00Z
```

Không có `AWS_ACCESS_KEY_ID` hay `AWS_SECRET_ACCESS_KEY` trong secrets — đây là điều muốn thấy.

### Step 10: Cleanup

```bash
# Destroy OIDC resources khi xong lab
cd infra
terraform destroy \
  -var="environment=dev" \
  -var="github_org=your-github-org" \
  -var="github_repo=your-repo-name"
```

---

## 6. Kiểm tra hiểu bài

**Câu 1 — Khái niệm:**
Giải thích tại sao `terraform validate` không cần AWS credentials nhưng vẫn cần chạy `terraform init` trước. `terraform init -backend=false` khác gì `terraform init` thông thường?

**Câu 2 — Chọn approach:**
Team bạn có 3 môi trường: dev, staging, production. Dev cần deploy nhanh (nhiều lần/ngày), staging cần review nhưng không cần manual approval, production cần manual approval và audit log. Bạn sẽ thiết kế workflow thế nào? Dùng 1 hay 3 workflow files? 1 hay nhiều AWS OIDC roles?

**Câu 3 — Debug:**
Workflow của bạn fail với lỗi:
```
Error: error assuming role arn:aws:iam::123456789012:role/terraform-cicd-lab-plan-role
Status Code: 403, Code: AccessDenied
Message: Not authorized to perform sts:AssumeRoleWithWebIdentity
```
Liệt kê 3 nguyên nhân có thể gây lỗi này và cách kiểm tra từng nguyên nhân.

**Câu 4 — Trade-off:**
Tại sao không nên dùng `cancel-in-progress: true` trong concurrency group khi apply Terraform? Hậu quả nếu apply bị cancel giữa chừng là gì?

**Câu 5 — Security:**
Bạn review một PR và thấy team member đã thêm `soft_fail: true` vào bước checkov trong workflow, vì "checkov có quá nhiều false positives". Bạn sẽ phản hồi thế nào? Giải pháp tốt hơn là gì?

---

## 7. Tóm tắt cuối ngày

**3 điểm quan trọng nhất:**

1. **Quality gates là defense-in-depth**: `fmt` → `validate` → `tflint` → `checkov/trivy` kiểm tra ở các lớp khác nhau. Bỏ bất kỳ layer nào đều tạo blind spot. `fmt` ngăn style drift, `validate` ngăn syntax error, `tflint` ngăn logic errors, `checkov` ngăn security misconfig.

2. **OIDC loại bỏ toàn bộ static credential risk**: Không có secret nào tồn tại đủ lâu để bị leak. Trust được định nghĩa bằng IAM Trust Policy với condition chặt chẽ theo repo/branch. Plan role và apply role tách biệt theo principle of least privilege.

3. **Manual approval gate = explicit accountability**: Khi production thay đổi, phải có người review plan và chịu trách nhiệm approve. GitHub Environment với required reviewers tạo audit trail: ai approve, khi nào, với plan output nào. Không có "ai apply vào production lúc 3 giờ sáng mà không ai biết".

**Output của ngày hôm nay:**
- GitHub Actions workflow hoàn chỉnh với 3 jobs: quality-gates, plan, apply
- OIDC infrastructure (IAM OIDC provider + 2 roles: plan và apply)
- `.tflint.hcl` config với AWS ruleset
- PR comment tự động hiển thị terraform plan output
- Manual approval gate cho production environment

**Chuẩn bị cho Day 12:**
Day 12 sẽ cover State Strategy nâng cao (state migration, split state ra nhiều files), Drift Detection (phát hiện khi infrastructure bị thay đổi ngoài Terraform), Cost Control (Infracost trong CI), và Policy as Code (OPA / Sentinel). Workflow CI/CD từ Day 11 sẽ là foundation để thêm các bước này vào pipeline.

---

## 8. Tham khảo thêm

- [GitHub Actions OIDC - Official Docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
- [hashicorp/setup-terraform GitHub Action](https://github.com/hashicorp/setup-terraform)
- [tflint - GitHub](https://github.com/terraform-linters/tflint)
- [tflint-ruleset-aws](https://github.com/terraform-linters/tflint-ruleset-aws)
- [Checkov Documentation](https://www.checkov.io/1.Welcome/Quick%20Start.html)
- [Trivy Config Scanning](https://aquasecurity.github.io/trivy/latest/docs/scanner/misconfiguration/)
- [Terraform CI/CD Best Practices - HashiCorp](https://developer.hashicorp.com/terraform/tutorials/automation/github-actions)
- [GitHub Environments - Required Reviewers](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
