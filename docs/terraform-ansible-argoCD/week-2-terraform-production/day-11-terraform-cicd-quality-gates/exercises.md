# Day 11: Exercises & Challenges — Terraform CI/CD, OIDC, Quality Gates

---

## Bài tập 1: Multi-environment Workflow (Intermediate)

### Bối cảnh

Công ty bạn có 3 environments: `dev`, `staging`, `production`. Hiện tại chỉ có 1 workflow file deploy lên `dev` bằng manual apply từ laptop. Nhiệm vụ: thiết kế và implement workflow CI/CD hoàn chỉnh cho cả 3 environments.

### Yêu cầu

1. **Cấu trúc Terraform**: Tổ chức code theo pattern `environments/<env>/` với shared modules.
2. **Workflow rules**:
   - `dev`: Auto-apply khi push vào `develop` branch, không cần approval.
   - `staging`: Plan khi push vào `staging` branch, apply cần 1 reviewer.
   - `production`: Plan khi push vào `main`, apply cần 2 reviewers và chỉ trong giờ hành chính (không enforce bằng code, nhưng document policy).
3. **OIDC**: Mỗi environment có IAM role riêng biệt với permissions khác nhau.
4. **State isolation**: Mỗi environment có state file riêng trong S3.

### Hướng dẫn

**Bước 1**: Tạo cấu trúc thư mục:

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── production/
│       ├── main.tf
│       ├── variables.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── modules/
    ├── networking/
    └── compute/
```

**Bước 2**: Tạo 3 GitHub Environments với required reviewers:

```
dev:          0 required reviewers
staging:      1 required reviewer
production:   2 required reviewers
```

**Bước 3**: Implement workflow với matrix hoặc reusable workflow:

```yaml
# Approach A: Matrix (không recommended vì environments có config khác nhau)
strategy:
  matrix:
    environment: [dev, staging, production]

# Approach B: Reusable workflow (recommended)
# .github/workflows/terraform-deploy.yml (reusable)
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      working_directory:
        required: true
        type: string
      role_arn:
        required: true
        type: string
```

**Bước 4**: Implement main workflow file gọi reusable workflow:

```yaml
# .github/workflows/deploy-dev.yml
on:
  push:
    branches: [develop]
    paths: ['terraform/environments/dev/**']

jobs:
  deploy:
    uses: ./.github/workflows/terraform-deploy.yml
    with:
      environment: dev
      working_directory: terraform/environments/dev
      role_arn: arn:aws:iam::ACCOUNT:role/terraform-dev-apply-role
    permissions:
      id-token: write
      contents: read
```

### Câu hỏi để suy ngẫm

- Tại sao không dùng 1 workflow file với if-conditions thay vì 3 file riêng?
- Nếu `staging` và `production` dùng chung codebase nhưng khác variable values, bạn manage tfvars như thế nào trong CI? (Hint: không commit sensitive tfvars lên git)
- Làm thế nào để prevent developer accidentally merge production changes khi họ thực ra muốn deploy staging?

---

## Bài tập 2: Security Hardening — Tighten OIDC Trust Policy (Intermediate)

### Bối cảnh

Team bạn nhận được security audit finding: OIDC role hiện tại có condition `"repo:org/repo:*"` — quá rộng. Attacker có thể tạo một workflow trong cùng repo để escalate privileges bằng cách assume apply role.

### Yêu cầu

Implement OIDC trust policy theo nguyên tắc least privilege nhất có thể:

1. **Plan role**: Chỉ được assume từ PR workflows (không phải từ push to main).
2. **Apply role**: Chỉ được assume từ push to `main` branch và chỉ khi workflow file là `.github/workflows/terraform.yml` (không phải workflow file khác).
3. **Production apply role**: Thêm thêm điều kiện: phải được trigger từ GitHub Environment `production`.

### Solution hướng dẫn

```hcl
# Plan role: chỉ pull_request events
Condition = {
  StringEquals = {
    "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
  }
  StringLike = {
    # pull_request events có sub dạng: repo:org/repo:pull_request
    "token.actions.githubusercontent.com:sub" = "repo:org/repo:pull_request"
  }
}

# Apply role: chỉ main branch, chỉ workflow cụ thể
Condition = {
  StringEquals = {
    "token.actions.githubusercontent.com:aud"    = "sts.amazonaws.com"
    "token.actions.githubusercontent.com:sub"    = "repo:org/repo:ref:refs/heads/main"
    # job_workflow_ref restrict đến workflow file cụ thể
    "token.actions.githubusercontent.com:job_workflow_ref" = "org/repo/.github/workflows/terraform.yml@refs/heads/main"
  }
}

# Production apply role: thêm environment condition
Condition = {
  StringEquals = {
    "token.actions.githubusercontent.com:aud"         = "sts.amazonaws.com"
    "token.actions.githubusercontent.com:environment" = "production"
    "token.actions.githubusercontent.com:sub"         = "repo:org/repo:environment:production"
  }
}
```

### Điểm nâng cao

- Implement tất cả điều kiện trên dưới dạng Terraform module với variables.
- Viết unit test (dùng `terraform test` hoặc manual) để verify policy logic.
- Document tất cả conditions trong `README` hoặc comment trong code.

---

## Bài tập 3: Custom Quality Gate — Module Compliance Checker (Advanced)

### Bối cảnh

Team platform muốn enforce rằng tất cả Terraform modules trong internal registry phải:
1. Có `required_version` constraint với `>=` và upper bound: `>= 1.5.0, < 2.0.0`
2. Tất cả variables phải có `description` và `type`
3. Tất cả outputs phải có `description`
4. Module phải có file `README.md` hoặc `README.tf` (documentation)
5. Không được có hardcoded AWS account IDs (phải dùng `data "aws_caller_identity"`)

### Yêu cầu

Viết một shell script `scripts/module-compliance-check.sh` chạy các checks trên, tích hợp vào GitHub Actions workflow.

### Solution framework

```bash
#!/usr/bin/env bash
set -euo pipefail

# scripts/module-compliance-check.sh

MODULES_DIR="${1:-./modules}"
ERRORS=0
WARNINGS=0

log_error() {
  echo "ERROR: $1" >&2
  ERRORS=$((ERRORS + 1))
}

log_warn() {
  echo "WARN: $1"
  WARNINGS=$((WARNINGS + 1))
}

log_ok() {
  echo "OK: $1"
}

# Check 1: required_version phải có cả lower và upper bound
check_version_constraints() {
  local module_dir="$1"
  local tf_files
  tf_files=$(find "$module_dir" -name "*.tf" -maxdepth 1)

  local has_required_version=false
  local has_upper_bound=false

  for f in $tf_files; do
    if grep -q 'required_version' "$f"; then
      has_required_version=true
      # Kiểm tra có upper bound (< hoặc ~>)
      if grep -E 'required_version.*[<~>]' "$f" | grep -q '[<]'; then
        has_upper_bound=true
      fi
    fi
  done

  if ! $has_required_version; then
    log_error "[$module_dir] Missing required_version constraint"
  elif ! $has_upper_bound; then
    log_warn "[$module_dir] required_version has no upper bound (e.g., '< 2.0.0')"
  else
    log_ok "[$module_dir] required_version OK"
  fi
}

# Check 2: Variables phải có description và type
check_variables() {
  local module_dir="$1"
  local vars_file="$module_dir/variables.tf"

  if [[ ! -f "$vars_file" ]]; then
    log_warn "[$module_dir] No variables.tf found"
    return
  fi

  # Dùng python để parse HCL (đơn giản hơn dùng terraform)
  # Hoặc dùng regex đơn giản
  local var_blocks
  var_blocks=$(grep -c '^variable "' "$vars_file" 2>/dev/null || echo 0)
  local desc_count
  desc_count=$(grep -c 'description\s*=' "$vars_file" 2>/dev/null || echo 0)
  local type_count
  type_count=$(grep -c 'type\s*=' "$vars_file" 2>/dev/null || echo 0)

  if [[ "$desc_count" -lt "$var_blocks" ]]; then
    log_error "[$module_dir] Some variables missing description ($desc_count/$var_blocks have it)"
  else
    log_ok "[$module_dir] All variables have description"
  fi

  if [[ "$type_count" -lt "$var_blocks" ]]; then
    log_error "[$module_dir] Some variables missing type ($type_count/$var_blocks have it)"
  else
    log_ok "[$module_dir] All variables have type"
  fi
}

# Check 3: Không có hardcoded account IDs (12-digit numbers)
check_no_hardcoded_account_ids() {
  local module_dir="$1"
  local found
  # Tìm 12-digit numbers trong ARNs (pattern: arn:aws:...:123456789012:...)
  found=$(grep -rE 'arn:aws:[^:]+:[^:]*:[0-9]{12}:' "$module_dir" --include="*.tf" 2>/dev/null || true)

  if [[ -n "$found" ]]; then
    log_error "[$module_dir] Hardcoded AWS account ID found:"
    echo "$found"
  else
    log_ok "[$module_dir] No hardcoded account IDs"
  fi
}

# Check 4: Module có documentation
check_documentation() {
  local module_dir="$1"
  if [[ -f "$module_dir/README.md" ]] || [[ -f "$module_dir/README.tf" ]]; then
    log_ok "[$module_dir] Documentation found"
  else
    log_error "[$module_dir] Missing README.md or README.tf"
  fi
}

# Main: iterate qua tất cả modules
echo "=== Module Compliance Check ==="
echo "Scanning: $MODULES_DIR"
echo ""

for module_dir in "$MODULES_DIR"/*/; do
  if [[ -d "$module_dir" ]]; then
    echo "--- Checking module: $module_dir ---"
    check_version_constraints "$module_dir"
    check_variables "$module_dir"
    check_no_hardcoded_account_ids "$module_dir"
    check_documentation "$module_dir"
    echo ""
  fi
done

echo "=== Summary ==="
echo "Errors: $ERRORS"
echo "Warnings: $WARNINGS"

if [[ "$ERRORS" -gt 0 ]]; then
  echo "FAILED: $ERRORS compliance errors found"
  exit 1
else
  echo "PASSED: All compliance checks passed"
  exit 0
fi
```

Tích hợp vào workflow:

```yaml
- name: Module Compliance Check
  run: |
    chmod +x scripts/module-compliance-check.sh
    ./scripts/module-compliance-check.sh ./modules
```

---

## Bài tập 4: Drift Detection Cơ bản trong CI (Intermediate-Advanced)

### Bối cảnh

Infrastructure drift xảy ra khi ai đó modify resources trực tiếp trên AWS Console mà không qua Terraform. Bạn muốn phát hiện drift sớm (không chờ đến lần apply tiếp theo).

### Yêu cầu

Tạo một GitHub Actions workflow chạy **theo schedule** (mỗi ngày 1 lần hoặc mỗi 6 giờ) để:
1. Chạy `terraform plan` trên tất cả environments.
2. Nếu plan output cho thấy có changes (exit code 2) mà **không có PR nào đang open**, nghĩa là drift đã xảy ra.
3. Tạo GitHub Issue tự động với detail về drift.

### Workflow skeleton

```yaml
name: Drift Detection

on:
  schedule:
    - cron: '0 */6 * * *'  # Mỗi 6 giờ
  workflow_dispatch:          # Cho phép trigger thủ công

permissions:
  id-token: write
  contents: read
  issues: write  # Để tạo issue

jobs:
  detect-drift:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, production]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.8.0
          terraform_wrapper: true

      - name: Configure AWS (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars[format('TERRAFORM_{0}_PLAN_ROLE_ARN', matrix.environment)] }}
          aws-region: ap-southeast-1

      - name: Terraform Init
        working-directory: terraform/environments/${{ matrix.environment }}
        run: terraform init

      - name: Check for Drift
        id: drift
        working-directory: terraform/environments/${{ matrix.environment }}
        run: |
          terraform plan -detailed-exitcode -var-file="terraform.tfvars" 2>&1 | tee plan_output.txt
          EXIT_CODE=${PIPESTATUS[0]}

          if [[ "$EXIT_CODE" == "2" ]]; then
            echo "has_drift=true" >> $GITHUB_OUTPUT
          else
            echo "has_drift=false" >> $GITHUB_OUTPUT
          fi
        continue-on-error: true

      - name: Create Drift Issue
        if: steps.drift.outputs.has_drift == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const plan = fs.readFileSync(
              'terraform/environments/${{ matrix.environment }}/plan_output.txt',
              'utf8'
            );

            const title = `[Drift Detected] ${{ matrix.environment }} environment has infrastructure drift`;

            // Kiểm tra issue cùng title đã tồn tại chưa (tránh spam)
            const { data: issues } = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: 'terraform-drift',
            });

            const existing = issues.find(i => i.title === title);
            if (existing) {
              // Update comment với plan mới nhất
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: existing.number,
                body: `**Drift still detected** at ${new Date().toISOString()}\n\n\`\`\`\n${plan.substring(0, 60000)}\n\`\`\``,
              });
            } else {
              await github.rest.issues.create({
                owner: context.repo.owner,
                repo: context.repo.repo,
                title,
                labels: ['terraform-drift', '${{ matrix.environment }}'],
                body: `## Infrastructure Drift Detected

            **Environment:** ${{ matrix.environment }}
            **Detected at:** ${new Date().toISOString()}

            Terraform plan shows changes that were NOT made through Terraform.
            This usually means someone manually modified resources on the AWS Console.

            ### Plan Output

            \`\`\`
            ${plan.substring(0, 60000)}
            \`\`\`

            ## Action Required

            1. Identify who made the change and why
            2. Either: import the change into Terraform state, OR revert the manual change
            3. Close this issue when drift is resolved`,
              });
            }
```

### Câu hỏi mở rộng

- Làm thế nào phân biệt "legitimate drift" (ví dụ: auto-scaling tạo/xóa instances) vs. "unauthorized drift" (ví dụ: ai đó thay đổi security group)?
- Schedule drift detection như thế nào nếu cost là concern (mỗi plan call đều tốn thời gian và có thể lock state)?

---

## Bài tập 5: Tối ưu hóa Pipeline Speed (Advanced)

### Bối cảnh

Workflow hiện tại mất 8-10 phút mỗi lần chạy. Developer phàn nàn vì họ phải đợi quá lâu để biết PR của họ có lỗi không. Nhiệm vụ: tối ưu xuống dưới 3 phút cho quality gates.

### Bottlenecks thường gặp

1. `terraform init` download providers (~2-3 phút nếu không có cache)
2. `tflint --init` download plugins (~30s)
3. `checkov` cài dependencies (~1 phút)
4. `trivy` download DB (~30s)

### Yêu cầu

Implement caching strategy cho tất cả các tools trên.

### Solution

```yaml
# Cache provider downloads
- name: Cache Terraform Providers
  uses: actions/cache@v4
  with:
    path: |
      ~/.terraform.d/plugin-cache
      ${{ env.WORKING_DIR }}/.terraform
    key: terraform-${{ runner.os }}-${{ hashFiles('**/.terraform.lock.hcl') }}
    restore-keys: |
      terraform-${{ runner.os }}-

# Config terraform để dùng plugin cache
- name: Configure Terraform Plugin Cache
  run: |
    mkdir -p ~/.terraform.d/plugin-cache
    cat >> ~/.terraformrc << EOF
    plugin_cache_dir = "$HOME/.terraform.d/plugin-cache"
    EOF

# Cache tflint plugins
- name: Cache TFLint Plugins
  uses: actions/cache@v4
  with:
    path: ~/.tflint.d/plugins
    key: tflint-${{ runner.os }}-${{ hashFiles('.tflint.hcl') }}

# Cache trivy DB
- name: Cache Trivy DB
  uses: actions/cache@v4
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ github.run_id }}
    restore-keys: |
      trivy-db-

# Parallelize quality gates
quality-gates:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    # Chạy fmt và validate trước (nhanh, không cần internet)
    - name: Setup Terraform
      uses: hashicorp/setup-terraform@v3
      with:
        terraform_version: 1.8.0

    - name: Fmt Check
      run: terraform fmt -check -recursive

    - name: Init (no backend)
      run: terraform init -backend=false
      working-directory: ${{ env.WORKING_DIR }}

    - name: Validate
      run: terraform validate
      working-directory: ${{ env.WORKING_DIR }}

    # Chạy tflint, trivy, checkov song song
    - name: Run Security Tools in Parallel
      run: |
        # Background tất cả, capture exit codes
        tflint --recursive &
        TFLINT_PID=$!

        trivy config --severity HIGH,CRITICAL --exit-code 1 . &
        TRIVY_PID=$!

        checkov -d . --framework terraform --quiet &
        CHECKOV_PID=$!

        # Wait và check exit codes
        wait $TFLINT_PID
        TFLINT_EXIT=$?

        wait $TRIVY_PID
        TRIVY_EXIT=$?

        wait $CHECKOV_PID
        CHECKOV_EXIT=$?

        # Fail nếu bất kỳ tool nào fail
        if [[ "$TFLINT_EXIT" != "0" ]] || [[ "$TRIVY_EXIT" != "0" ]] || [[ "$CHECKOV_EXIT" != "0" ]]; then
          echo "Quality gate failed: tflint=$TFLINT_EXIT, trivy=$TRIVY_EXIT, checkov=$CHECKOV_EXIT"
          exit 1
        fi
```

### Đo lường kết quả

Sau khi optimize, ghi lại:

| Step | Before | After |
|---|---|---|
| terraform init | ? phút | ? phút |
| tflint | ? giây | ? giây |
| trivy config | ? giây | ? giây |
| checkov | ? phút | ? giây |
| Total | ? phút | ? phút |

---

## Challenge tổng hợp: Production-Ready Pipeline

Kết hợp tất cả các bài tập trên để tạo một complete Terraform CI/CD pipeline cho một microservices platform với:

- 3 AWS accounts (dev account, staging account, production account) — cross-account deployment
- 5 Terraform modules (networking, EKS cluster, RDS, ElastiCache, monitoring)
- GitHub Actions OIDC với role chaining (hub account assume role into spoke accounts)
- Automatic drift detection chạy mỗi 6 giờ
- Module compliance checks
- Infracost (cost estimation) trong PR comment bên cạnh plan output
- OPA policy gates (sẽ học trong Day 12)

Đây là bài tập thiết kế — không cần implement toàn bộ, nhưng cần produce:
1. Diagram ASCII của toàn bộ workflow
2. IAM role structure cho cross-account OIDC
3. GitHub Actions workflow files (có thể dùng placeholder cho phần chưa học)
4. Decision log: tại sao chọn mỗi approach

Bài tập này không có "đáp án đúng duy nhất" — mục đích là practice architecting và documenting trade-offs.
