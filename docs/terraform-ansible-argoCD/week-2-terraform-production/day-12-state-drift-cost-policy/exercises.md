# Day 12: Extended Exercises & Challenges

**Phase:** 2 - Terraform Production | **Day:** 12 (Final) | **Level:** Advanced

---

## Exercise 1: State Layout Design (Conceptual)

### Bài toán

Bạn join một startup fintech đang migrate từ monolithic infra sang microservices. Hiện tại họ có:

- 1 VPC với 3 subnets (public, private, database)
- 1 RDS PostgreSQL (shared cho tất cả services)
- 3 EC2 instances chạy monolith
- 1 ALB
- Tất cả trong 1 Terraform state file (200 resources)

Team plan:
- Tách thành 5 microservices: `user-service`, `payment-service`, `order-service`, `notification-service`, `api-gateway`
- Mỗi service có RDS riêng
- Dùng EKS thay EC2
- 3 environments: dev, staging, production
- 2 teams: Platform team (infra), Product team (apps)

### Yêu cầu

**Câu 1.1**: Vẽ ASCII diagram cho state layout mới. Phân chia state theo env và domain. Giải thích rõ:
- Mỗi state chứa gì
- Team nào quản lý state nào
- Dependency giữa các states

**Câu 1.2**: Thiết kế output contract giữa `foundation` state và `data` state. Liệt kê tối thiểu 5 outputs mà foundation phải export và giải thích tại sao.

**Câu 1.3**: Kể tên 3 rủi ro lớn nhất khi migrate từ monolithic state sang split states. Với mỗi rủi ro, đề xuất cách giảm thiểu.

**Câu 1.4**: Payment service có requirement: state của nó phải ở AWS account riêng (PCI-DSS compliance). Thiết kế backend configuration cho trường hợp này, bao gồm IAM roles cần thiết.

---

## Exercise 2: Remote State Data Source Implementation

### Bài toán

```hcl
# Đây là foundation/outputs.tf hiện tại
output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
output "database_subnet_ids" {
  value = aws_subnet.database[*].id
}
output "vpc_id" {
  value = aws_vpc.main.id
}
```

Platform team muốn refactor: rename `database_subnet_ids` thành `db_subnet_ids` để consistent với naming convention mới.

### Yêu cầu

**Câu 2.1**: Liệt kê tất cả files bạn cần kiểm tra trước khi rename. Viết bash command để tìm tất cả places đang dùng `database_subnet_ids`.

**Câu 2.2**: Viết migration plan để rename output mà không gây downtime. Include:
- Bước 1 đến N
- Thời gian giữa các bước
- Rollback plan nếu bước N fail

**Câu 2.3**: Thay vì remote state, đề xuất implement SSM Parameter Store làm interface layer. Viết đầy đủ Terraform code cho:
- Foundation layer: write VPC ID và subnet IDs vào SSM
- Apps layer: đọc từ SSM thay vì remote state data source

---

## Exercise 3: Drift Detection Automation

### Bài toán

Viết GitHub Actions workflow hoàn chỉnh cho drift detection với yêu cầu sau:

- Chạy daily lúc 7:00 AM UTC
- Check drift cho tất cả 3 environments: dev, staging, production
- Mỗi environment là một job riêng
- Nếu detect drift trong production: tạo GitHub Issue tự động với label `drift`, `production`, assign cho on-call team
- Nếu detect drift trong dev/staging: chỉ cần Slack notification
- Lưu drift report dưới dạng artifact

### Yêu cầu

**Câu 3.1**: Viết file `.github/workflows/drift-detection.yml` hoàn chỉnh theo yêu cầu trên.

**Câu 3.2**: Giải thích tại sao workflow dùng `terraform plan -refresh-only -detailed-exitcode` thay vì `terraform plan`. Sự khác biệt về behavior và khi nào cần dùng cái nào.

**Câu 3.3**: Team debate về auto-apply drift correction (khi detect drift, tự động apply để bring infra về state). Bạn là người có tiếng nói. Viết argument (2-3 đoạn) cho hoặc chống auto-apply, với lý do kỹ thuật cụ thể.

---

## Exercise 4: Infracost Cost Governance

### Bài toán

Viết một cost governance system với các rules sau:
- PR không được tăng cost > $500/month mà không có approval
- Tổng cost của dev environment không vượt quá $1,000/month
- Mọi PR phải có Infracost comment

### Yêu cầu

**Câu 4.1**: Viết bash script `cost-governance.sh` nhận input là `plan.json` và thực hiện:
- Generate Infracost breakdown
- Check nếu monthly increase > $500, exit với code khác 0 và print warning
- Print summary ra stdout

**Câu 4.2**: Câu lệnh Infracost nào dùng để so sánh cost giữa current branch và main branch? Viết đầy đủ command với tất cả flags cần thiết.

**Câu 4.3**: Infracost không thể estimate cost của tất cả resources. Liệt kê 3 loại resources phổ biến mà Infracost không estimate được và giải thích tại sao. Bạn xử lý gap này như thế nào?

---

## Exercise 5: Policy as Code với OPA/Conftest

### Bài toán

Viết đầy đủ policy suite cho một fintech company với các requirements sau:

**Security Requirements:**
- Không resource nào được tạo ở region ngoài `us-east-1` và `eu-west-1`
- RDS phải có `deletion_protection = true` trong production
- S3 bucket phải có versioning enabled
- EKS cluster phải dùng private endpoint (không public)

**Cost Requirements:**
- Dev environment: không dùng instance type có price tier > t3.large
- Production: chỉ được dùng instances trong danh sách được approved

**Compliance Requirements:**
- Tất cả resources phải có tags: `Environment`, `Owner`, `CostCenter`, `DataClassification`
- S3 buckets chứa customer data (tag `DataClassification=PII`) phải có encryption với customer-managed key (KMS)

### Yêu cầu

**Câu 5.1**: Viết Rego policy cho **Security Requirement 1** (region restriction). Include unit tests với ít nhất 2 test cases (pass và fail).

**Câu 5.2**: Viết Rego policy cho **Compliance Requirement 2** (PII bucket must use KMS). Đây là policy phức tạp nhất - cần check:
- Bucket có tag `DataClassification=PII` không
- Bucket có `server_side_encryption_configuration` không
- Encryption algorithm có phải `aws:kms` không

**Câu 5.3**: Viết `conftest.toml` hoặc `policy/` structure để organize tất cả policies theo namespaces (security, cost, compliance). Policies nào nên là `deny` (blocking) và policies nào nên là `warn` (advisory)?

**Câu 5.4**: Một developer argue rằng "Policy as Code adds too much friction to development". Họ đề xuất chỉ run policies weekly thay vì mỗi PR. Bạn phản hồi thế nào? (Trả lời bằng kỹ thuật arguments, không phải process/management arguments)

---

## Exercise 6: Tích hợp hoàn chỉnh - Mini Pipeline

### Bài toán

Viết một CI/CD pipeline hoàn chỉnh cho Terraform với tất cả gates từ Day 12:

```
Developer push code
    │
    ├── Stage 1: Validate & Format
    ├── Stage 2: Plan
    ├── Stage 3: Policy Check (Conftest)
    ├── Stage 4: Cost Check (Infracost)
    ├── Stage 5: Human Approval (production only)
    └── Stage 6: Apply
```

### Yêu cầu

**Câu 6.1**: Viết `.github/workflows/terraform-pipeline.yml` implement đầy đủ 6 stages trên. Yêu cầu:
- Stage 3 và 4 chạy song song (không phụ thuộc nhau)
- Stage 5 chỉ trigger khi branch là `main` VÀ changes affect production directory
- Stage 6 chỉ chạy sau khi Stage 5 approved

**Câu 6.2**: Trong workflow của bạn, plan JSON được generate ở Stage 2 và cần dùng ở Stage 3 và 4. Làm thế nào để chia sẻ artifact này giữa jobs? Viết relevant YAML snippets.

**Câu 6.3**: Nếu Stage 4 (Cost Check) fail, nên block merge hay chỉ warn? Justify your answer với ít nhất 2 scenarios cụ thể.

---

## Exercise 7: Challenge - Refactor Monolith State

### Advanced Challenge (45-60 phút)

Đây là tình huống thực tế: bạn được giao refactor một monolithic state 150 resources thành split state. Không được downtime. Không được destroy/recreate resources.

#### Monolith state structure hiện tại

```
# Một state chứa tất cả:
module "vpc"
module "rds_users"
module "rds_orders"
module "eks_cluster"
module "alb_external"
module "alb_internal"
module "route53"
module "acm_certs"
```

#### Target structure

```
foundation/  ──── VPC, subnets
data/        ──── RDS clusters
compute/     ──── EKS cluster
apps/        ──── ALBs, Route53, ACM
```

### Yêu cầu

**Câu 7.1**: Viết step-by-step runbook để migrate `module.vpc` từ monolith sang `foundation/` state mà không recreate VPC. Sử dụng `terraform state mv` và/hoặc `terraform state rm` + `terraform import`. Giải thích tại sao cần từng bước.

**Câu 7.2**: Sau khi move VPC sang foundation state, apps/ state cần dùng VPC ID. Bạn thiết kế interface layer như thế nào giữa foundation và apps? Viết code cho cả hai phía.

**Câu 7.3**: Trong quá trình migration, có một window ngắn mà resource tồn tại trong cả hai states. Điều này gây ra vấn đề gì? Cách xử lý?

**Câu 7.4**: Sau migration hoàn tất, viết smoke test script để verify rằng tất cả states consistent và không có resource nào bị duplicate hoặc thiếu.

---

## Gợi ý giải (không xem trước khi tự làm)

<details>
<summary>Gợi ý Exercise 2.3 - SSM Parameter Store Interface</summary>

```hcl
# foundation/ssm.tf
# Write outputs vào SSM để decoupling
resource "aws_ssm_parameter" "vpc_id" {
  name        = "/${var.environment}/foundation/vpc_id"
  type        = "String"
  value       = aws_vpc.main.id
  description = "VPC ID - managed by foundation Terraform"

  tags = {
    ManagedBy = "terraform"
    Layer     = "foundation"
  }
}

resource "aws_ssm_parameter" "private_subnet_ids" {
  name        = "/${var.environment}/foundation/private_subnet_ids"
  type        = "StringList"
  value       = join(",", aws_subnet.private[*].id)
  description = "Private subnet IDs - managed by foundation Terraform"
}
```

```hcl
# apps/main.tf
# Read từ SSM thay vì remote state
data "aws_ssm_parameter" "vpc_id" {
  name = "/${var.environment}/foundation/vpc_id"
}

data "aws_ssm_parameter" "private_subnet_ids" {
  name = "/${var.environment}/foundation/private_subnet_ids"
}

locals {
  vpc_id             = data.aws_ssm_parameter.vpc_id.value
  private_subnet_ids = split(",", data.aws_ssm_parameter.private_subnet_ids.value)
}
```

Ưu điểm: Apps không cần biết foundation backend config. Bất kỳ service nào (Lambda, EC2 user data, ECS task) cũng có thể đọc SSM. Thay đổi key name trong SSM dễ hơn thay đổi Terraform output vì không cần terraform state migration.

</details>

<details>
<summary>Gợi ý Exercise 5.1 - Region Restriction Policy</summary>

```rego
# policies/security/region_restriction.rego
package terraform.security.regions

import future.keywords.in

allowed_regions := {"us-east-1", "eu-west-1"}

deny[msg] {
  resource := input.resource_changes[_]
  resource.change.actions[_] in {"create", "update"}
  startswith(resource.type, "aws_")

  # Lấy region từ provider config
  # Trong tf plan JSON, region nằm trong provider_config
  provider := input.configuration.provider_config.aws
  region := provider.expressions.region.constant_value
  not allowed_regions[region]

  msg := sprintf(
    "Resource '%s' is in region '%s'. Only %v are allowed.",
    [resource.address, region, allowed_regions]
  )
}
```

```rego
# policies/security/region_restriction_test.rego
package terraform.security.regions

test_allowed_region_passes {
  count(deny) == 0 with input as {
    "configuration": {
      "provider_config": {
        "aws": {
          "expressions": {
            "region": {"constant_value": "us-east-1"}
          }
        }
      }
    },
    "resource_changes": []
  }
}

test_disallowed_region_fails {
  count(deny) == 1 with input as {
    "configuration": {
      "provider_config": {
        "aws": {
          "expressions": {
            "region": {"constant_value": "ap-southeast-1"}
          }
        }
      }
    },
    "resource_changes": [{
      "address": "aws_vpc.main",
      "type": "aws_vpc",
      "change": {
        "actions": ["create"],
        "after": {"cidr_block": "10.0.0.0/16"}
      }
    }]
  }
}
```

</details>

<details>
<summary>Gợi ý Exercise 7.1 - State Migration Runbook</summary>

```bash
#!/bin/bash
# migrate-vpc-to-foundation.sh
# Migrate VPC từ monolith state sang foundation state
# KHÔNG destroy, KHÔNG recreate resources

set -e

MONOLITH_DIR="./terraform/monolith"
FOUNDATION_DIR="./terraform/production/foundation"

echo "=== Step 1: Backup current states ==="
terraform -chdir="${MONOLITH_DIR}" state pull > /tmp/monolith-backup-$(date +%Y%m%d%H%M%S).json
echo "Backup created"

echo "=== Step 2: Get VPC resource IDs ==="
VPC_ID=$(terraform -chdir="${MONOLITH_DIR}" output -raw vpc_id)
SUBNET_IDS=$(terraform -chdir="${MONOLITH_DIR}" state show module.vpc.aws_subnet.private | grep '"id"' | awk '{print $3}' | tr -d '"')
echo "VPC: ${VPC_ID}"

echo "=== Step 3: Remove VPC resources from monolith state (WITHOUT destroying) ==="
terraform -chdir="${MONOLITH_DIR}" state rm module.vpc.aws_vpc.main
terraform -chdir="${MONOLITH_DIR}" state rm 'module.vpc.aws_subnet.private[0]'
terraform -chdir="${MONOLITH_DIR}" state rm 'module.vpc.aws_subnet.private[1]'
# Remove all VPC-related resources...
echo "Resources removed from monolith state"

echo "=== Step 4: Init foundation state ==="
terraform -chdir="${FOUNDATION_DIR}" init

echo "=== Step 5: Import resources into foundation state ==="
# Resources vẫn exist trên AWS - chỉ import reference vào new state
terraform -chdir="${FOUNDATION_DIR}" import aws_vpc.main "${VPC_ID}"
# Import subnets...
echo "Resources imported into foundation state"

echo "=== Step 6: Verify no changes ==="
terraform -chdir="${FOUNDATION_DIR}" plan
# Should show: No changes. Your infrastructure matches the configuration.

echo "=== Migration complete! ==="
echo "WARNING: Update monolith state to use remote_state data source for VPC references"
```

Key insight: Resource tồn tại trong cả 2 states trong window ngắn (giữa bước 3 và 5). Trong window này, nếu ai đó chạy `terraform apply` trên monolith → Terraform sẽ cố recreate VPC (vì đã rm khỏi state nhưng VPC vẫn tồn tại → conflict). Giải pháp: lock monolith state bằng cách tạo dummy lock file hoặc revoke IAM permissions tạm thời.

</details>

---

## Tự đánh giá

Sau khi hoàn thành các exercises, tự đánh giá theo rubric sau:

| Skill | Beginner | Intermediate | Advanced |
|-------|----------|-------------|----------|
| State layout design | Biết split per-env | Biết split per-domain | Thiết kế được cho enterprise với compliance requirements |
| Remote state | Copy-paste data source block | Biết trade-offs với SSM | Thiết kế được interface contract, migration plan |
| Drift detection | Chạy được `tf plan -refresh-only` | Viết được CI job | Thiết kế automated response system |
| Infracost | Chạy được basic commands | Tích hợp vào CI | Implement cost governance với thresholds và approvals |
| Policy as Code | Viết được basic deny rule | Viết được với unit tests | Thiết kế multi-layer policy enforcement |

**Target cho Day 12**: Intermediate cho tất cả, Advanced cho ít nhất 2 skills.
