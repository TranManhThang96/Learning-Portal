# Day 11: Cheat Sheet & Reference — Terraform CI/CD, OIDC, Quality Gates

---

## Quick Reference: Quality Gate Commands

### terraform fmt

```bash
# Kiểm tra (dùng trong CI — exit 1 nếu không đúng format)
terraform fmt -check -recursive

# Tự động fix (dùng local)
terraform fmt -recursive

# Xem diff trước khi fix
terraform fmt -diff -recursive
```

### terraform validate

```bash
# Cần init trước (không cần backend)
terraform init -backend=false
terraform validate

# Validate với variables
terraform validate -var="environment=dev"
```

### tflint

```bash
# Init (download ruleset plugins)
tflint --init

# Chạy trên directory hiện tại
tflint

# Chạy recursive (tất cả modules)
tflint --recursive

# Output format cho CI
tflint --format compact      # compact
tflint --format json         # machine-readable
tflint --format checkstyle   # XML cho Jenkins

# Chỉ chạy rule cụ thể
tflint --enable-rule=terraform_required_version

# Skip rule cụ thể
tflint --disable-rule=terraform_naming_convention
```

### checkov

```bash
# Scan directory
checkov -d .

# Chỉ Terraform framework
checkov -d . --framework terraform

# Output formats
checkov -d . --output cli        # human-readable
checkov -d . --output json       # machine-readable
checkov -d . --output junitxml   # CI-friendly

# Skip specific checks
checkov -d . --skip-check CKV_AWS_18,CKV_AWS_20

# Soft fail (report nhưng không fail pipeline)
checkov -d . --soft-fail

# Chỉ HIGH severity trở lên
checkov -d . --check CKV_AWS_*  # không có built-in severity filter — dùng trivy thay thế
```

### trivy config

```bash
# Scan config files (Terraform, K8s, Docker)
trivy config .

# Chỉ fail với HIGH và CRITICAL
trivy config --severity HIGH,CRITICAL .

# Exit code 1 nếu có findings
trivy config --exit-code 1 --severity HIGH,CRITICAL .

# Output formats
trivy config --format table .       # default
trivy config --format json .        # machine-readable
trivy config --format sarif .       # upload vào GitHub Code Scanning

# Skip specific rules
trivy config --skip-files "modules/legacy/**" .
```

---

## OIDC Trust Policy Quick Reference

### Subject (`sub`) claim patterns

| Pattern | Ý nghĩa |
|---|---|
| `repo:org/repo:*` | Bất kỳ trigger nào trong repo |
| `repo:org/repo:ref:refs/heads/main` | Chỉ main branch |
| `repo:org/repo:ref:refs/heads/feature/*` | Tất cả feature branches |
| `repo:org/repo:pull_request` | Chỉ PR events |
| `repo:org/repo:environment:production` | Chỉ GitHub Environment "production" |
| `repo:org/repo:ref:refs/tags/*` | Chỉ tagged releases |

### GitHub OIDC Token Claims

| Claim | Ví dụ | Dùng để |
|---|---|---|
| `sub` | `repo:org/repo:ref:refs/heads/main` | Restrict theo repo/branch |
| `aud` | `sts.amazonaws.com` | Luôn dùng giá trị này với AWS |
| `iss` | `https://token.actions.githubusercontent.com` | OIDC issuer URL |
| `repository` | `org/repo` | Tên repo |
| `repository_owner` | `org` | Tên org |
| `workflow` | `Terraform CI/CD` | Tên workflow |
| `job_workflow_ref` | `org/repo/.github/workflows/terraform.yml@refs/heads/main` | Specific workflow file |
| `environment` | `production` | GitHub Environment name |

### AWS STS AssumeRoleWithWebIdentity — Điều kiện thường dùng

```json
{
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
      "token.actions.githubusercontent.com:sub": "repo:org/repo:ref:refs/heads/main"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:org/repo:*"
    }
  }
}
```

`StringEquals` dùng khi cần match chính xác (main branch, specific environment).
`StringLike` dùng khi cần wildcard (tất cả branches, tất cả tags).

---

## GitHub Actions: Terraform Workflow Patterns

### Permission block cần thiết

```yaml
permissions:
  id-token: write      # Bắt buộc để request OIDC token
  contents: read       # Để checkout code
  pull-requests: write # Để post plan comment vào PR
```

### Concurrency — Ngăn concurrent applies

```yaml
concurrency:
  group: terraform-${{ github.ref }}
  cancel-in-progress: false  # KHÔNG cancel Terraform apply đang chạy
```

### terraform_wrapper: true — Tại sao cần?

```yaml
- uses: hashicorp/setup-terraform@v3
  with:
    terraform_version: 1.8.0
    terraform_wrapper: true  # Wrap terraform binary để capture exit codes
```

Với `terraform_wrapper: true`, exit code của `terraform plan` được expose:
- `0`: Không có changes
- `1`: Lỗi
- `2`: Có changes (khi dùng `-detailed-exitcode`)

### Capture plan exit code

```yaml
- name: Terraform Plan
  id: plan
  run: |
    terraform plan -out=tfplan -detailed-exitcode 2>&1 | tee plan_output.txt
    echo "exitcode=${PIPESTATUS[0]}" >> $GITHUB_OUTPUT
  continue-on-error: true

- name: Check Plan
  if: steps.plan.outputs.exitcode == '1'
  run: exit 1
```

Dùng `PIPESTATUS[0]` thay vì `$?` vì `| tee` sẽ overwrite `$?` bằng exit code của `tee` (luôn là 0).

### Post plan to PR comment (với update existing comment)

```yaml
- uses: actions/github-script@v7
  if: github.event_name == 'pull_request'
  with:
    script: |
      const fs = require('fs');
      const plan = fs.readFileSync('plan_output.txt', 'utf8');

      const { data: comments } = await github.rest.issues.listComments({
        owner: context.repo.owner,
        repo: context.repo.repo,
        issue_number: context.issue.number,
      });

      const marker = '<!-- terraform-plan-comment -->';
      const body = `${marker}\n## Terraform Plan\n\`\`\`\n${plan}\n\`\`\``;

      const existing = comments.find(c => c.body.includes(marker));
      if (existing) {
        await github.rest.issues.updateComment({
          ...context.repo,
          comment_id: existing.id,
          body,
        });
      } else {
        await github.rest.issues.createComment({
          ...context.repo,
          issue_number: context.issue.number,
          body,
        });
      }
```

### Manual Approval Gate via GitHub Environment

```yaml
jobs:
  apply:
    environment: production   # Trigger approval gate
    needs: plan
    if: github.ref == 'refs/heads/main'
```

GitHub sẽ pause workflow và gửi notification cho required reviewers. Reviewer vào Actions UI và approve/reject.

### Upload/Download Plan Artifact

```yaml
# Upload (trong plan job)
- uses: actions/upload-artifact@v4
  with:
    name: tfplan-${{ github.run_id }}
    path: infra/tfplan
    retention-days: 1  # Xóa sau 1 ngày — plan không nên lưu lâu

# Download (trong apply job)
- uses: actions/download-artifact@v4
  with:
    name: tfplan-${{ github.run_id }}
    path: infra/
```

---

## .tflint.hcl — Config Reference

```hcl
config {
  # Format của output
  format = "compact"

  # Plugin directory (mặc định ~/.tflint.d/plugins)
  plugin_dir = "~/.tflint.d/plugins"

  # Call module recursively
  call_module_type = "local"  # "local", "all", "none"
}

# Plugin chính thức của HashiCorp cho AWS
plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

# Rules thường dùng
rule "terraform_required_version"      { enabled = true }
rule "terraform_required_providers"    { enabled = true }
rule "terraform_documented_variables"  { enabled = true }
rule "terraform_documented_outputs"    { enabled = true }
rule "terraform_naming_convention"     { enabled = true }
rule "terraform_deprecated_interpolation" { enabled = true }

# AWS-specific rules
rule "aws_instance_invalid_type"       { enabled = true }
rule "aws_instance_previous_type"      { enabled = true }
rule "aws_iam_policy_document_gov_friendly_arns" { enabled = false }
```

---

## checkov — Suppress False Positives

### Inline suppression trong Terraform code

```hcl
resource "aws_s3_bucket" "example" {
  bucket = "my-bucket"

  # checkov:skip=CKV_AWS_18:Bucket không cần access logging vì là internal-only
  # checkov:skip=CKV_AWS_52:MFA delete không cần cho dev environment
}
```

### File-level suppression `.checkov.yaml`

```yaml
skip-check:
  - CKV_AWS_18   # S3 access logging — không cần cho dev
  - CKV_AWS_52   # MFA delete — không cần cho non-production

# Hoặc suppress toàn bộ directory
skip-path:
  - modules/legacy/
```

---

## trivy — Suppress False Positives

### `.trivyignore` file

```
# Format: RULE_ID [expiry-date] [comment]
AVD-AWS-0086 exp:2024-06-01 S3 access logging không cần cho internal bucket
AVD-AWS-0132                 MFA delete không applicable cho dev env
```

### Inline suppression trong Terraform

```hcl
#trivy:ignore:AVD-AWS-0086
resource "aws_s3_bucket" "example" {
  bucket = "my-internal-bucket"
}
```

---

## Common Errors & Fixes

| Error | Nguyên nhân | Fix |
|---|---|---|
| `Error: error assuming role ... AccessDenied` | Trust policy sub condition không match | Kiểm tra `sub` claim trong workflow so với condition trong IAM role |
| `terraform fmt -check` failed | File không được format | Chạy `terraform fmt -recursive` local rồi commit |
| `terraform validate` failed: `Required plugins are not installed` | Chạy validate trước init | Thêm `terraform init -backend=false` trước validate |
| tflint: `Failed to initialize plugins` | Không có internet trong CI hoặc tflint cache miss | Thêm `actions/cache` cho `~/.tflint.d/plugins` |
| Plan: `Error acquiring the state lock` | Workflow khác đang hold lock | Kiểm tra DynamoDB table, force-unlock nếu lock stale |
| Apply artifact not found | Plan job không upload artifact vì exit code 0 | Artifact chỉ upload khi exit code 2 (có changes) |
| `PIPESTATUS` sai | Dùng `$?` sau pipe | Dùng `${PIPESTATUS[0]}` để lấy exit code của lệnh đầu tiên |

---

## IAM Role — Principle of Least Privilege Reference

### Plan role permissions (minimum)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::BUCKET-NAME",
        "arn:aws:s3:::BUCKET-NAME/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem", "dynamodb:PutItem",
        "dynamodb:DeleteItem", "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:*:ACCOUNT-ID:table/LOCK-TABLE-NAME"
    },
    {
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    }
  ]
}
```

Thêm các read-only actions cho resource types mà module của bạn quản lý (ví dụ: `ec2:Describe*`, `iam:Get*`).

### Apply role — Tránh AdministratorAccess trong production

Thay vì `AdministratorAccess`, sử dụng IAM Permission Boundary hoặc tạo custom policy chỉ chứa actions module cần. Một số tools hữu ích:

- [iamlive](https://github.com/iann0036/iamlive): Capture actual API calls và generate minimal policy
- [Terraform AWS Provider IAM docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs): Xem resource schema để biết API calls cần thiết

---

## Checklist trước khi merge PR có Terraform changes

- [ ] `terraform fmt -check -recursive` pass
- [ ] `terraform validate` pass
- [ ] `tflint --recursive` không có errors (warnings có thể chấp nhận tùy rule)
- [ ] `trivy config --severity HIGH,CRITICAL .` pass (hoặc mọi HIGH/CRITICAL đều có documented justification)
- [ ] `checkov -d .` pass (hoặc suppressions có comment giải thích)
- [ ] Plan output đã được review bởi ít nhất 1 người khác
- [ ] Không có unexpected destroys trong plan
- [ ] Không có sensitive data trong plan output (passwords, keys)
- [ ] State backend đã được configure đúng (đúng bucket, đúng key path)
- [ ] Với production: manual approval đã được bật trong GitHub Environment
