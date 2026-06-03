# Week 2 - Terraform Production (Day 7-12)

## Tổng quan

Week 2 nâng cấp kỹ năng Terraform từ foundations lên production-grade. Tập trung vào module design chuyên nghiệp, multi-environment strategy, advanced HCL patterns, và lifecycle management cho hệ thống thực tế. Mỗi ngày 2 tiếng thực hành.

## Lộ trình học

| Ngày | Chủ đề | Thời lượng | Files |
|------|--------|------------|-------|
| Day 7 | Module Design for Production | 2h | lesson, document, exercises |
| Day 8 | Multi-Environment Strategy | 2h | lesson, document, exercises |
| Day 9 | Advanced HCL: for_each, count, dynamic blocks | 2h | lesson, document, exercises |
| Day 10 | Lifecycle, Import, Moved Blocks, Refactor Không Downtime | 2h | lesson, document, exercises |
| Day 11 | Terraform CI/CD, OIDC, Quality Gates | 2h | lesson, document, exercises |
| Day 12 | State Strategy, Drift Detection, Cost Control, Policy as Code | 2h | lesson, document, exercises |

## Chi tiết từng ngày

### Day 7 - Module Design for Production

**Mục tiêu:** Thiết kế module boundary, interface design, opinionated vs flexible module, versioning strategy.

- **Kiến thức:** Module boundary (lifecycle alignment, blast radius), interface design (input/output rõ ràng), opinionated vs flexible spectrum, avoid over-abstraction
- **Lab:** Refactor VPC module từ Day 6 thành `vpc-production` với structured object inputs, cross-variable validation, concern-separated files, structured outputs, default SG hardening
- **Document:** 5 code patterns (opinionated wrapper, composition, conditional resource, dynamic block, cross-variable validation), input/output checklist, module boundary decision matrix, versioning comparison, security checklist
- **Exercises:** 6 bài tập (module boundary refactoring, breaking-change classification, debug scenarios, SG module design, migration rollout plan, testing strategy)

### Day 8 - Multi-Environment Strategy

**Mục tiêu:** Thiết kế multi-env structure, workspace vs folder, tfvars layering, Terragrunt overview.

- **Kiến thức:** Folder-based environment, Terraform workspace, tfvars layering với load order, Terragrunt overview với decision framework
- **Lab:** Tạo `environments/dev/` và `environments/staging/` dùng VPC module, config riêng (dev: no NAT, staging: có NAT), common.tfvars layering, so sánh plan output
- **Document:** Comparison matrix (isolation approaches), 3 folder structure templates (small/medium/enterprise), tfvars layering patterns, Terragrunt quick reference, CIDR allocation template
- **Exercises:** 5 bài tập (promotion pipeline script, workspace-to-folder migration, multi-account AWS strategy, consistency validation tool, architecture design cho 3 products x 4 envs x 2 regions)

### Day 9 - Advanced HCL: for_each, count, dynamic blocks

**Mục tiêu:** Thành thạo count, for_each, dynamic blocks, complex types, for expressions, built-in functions.

- **Kiến thức:** count vs for_each mechanism, for_each với map/set/list, dynamic blocks, complex types (object, map, list, set), for expressions, merge/lookup/try/can
- **Lab:** 4 phần - subnets với for_each map(object), root module với complex config, index-shift demo (count → delete → observe), refactor sang for_each với stability proof
- **Document:** ASCII decision flowchart (count vs for_each), 6 for_each patterns, 5 dynamic block patterns, for expression cheat sheet, built-in functions reference, migration guide, anti-patterns
- **Exercises:** 7 bài tập (multi-service SG, auto-calculate subnet CIDRs, full migration walkthrough, dynamic edge cases, advanced for expressions, try/can validation chains, complete VPC rewrite)

### Day 10 - Lifecycle, Import, Moved Blocks, Refactor Không Downtime

**Mục tiêu:** Sử dụng lifecycle rules, import existing resources, refactor không downtime bằng moved blocks.

- **Kiến thức:** lifecycle (prevent_destroy, ignore_changes, create_before_destroy), terraform import (CLI + import block 1.5+), moved block patterns, resource address system
- **Lab:** 4 phần dùng hashicorp/local provider (không cần cloud) - simulate import, test prevent_destroy, refactor vào module bằng moved blocks (verify 0 changes), import block workflow
- **Document:** lifecycle decision matrix (10 resource types), import syntax cho 14 AWS resource types, 5 moved block patterns, 15-step refactoring safety checklist, common error messages reference, Terraform version feature timeline
- **Exercises:** 5 bài tập (import 6 resources bằng import blocks, 3-module refactoring, production destroy incident recovery, for_each key migration, lifecycle tiered protection design) + grading rubric

### Day 11 - Terraform CI/CD, OIDC, Quality Gates

**Mục tiêu:** Thiết kế GitHub Actions workflow cho Terraform, cấu hình OIDC authentication, tích hợp quality gates.

- **Kiến thức:** PR-based workflow (plan-on-PR, apply-on-merge), OIDC flow với AWS (loại bỏ long-lived credentials), quality gate tools mapping (fmt → Prettier, validate → TypeScript compiler, tflint → ESLint, checkov/trivy → Snyk)
- **Lab:** Tạo GitHub Actions workflow hoàn chỉnh với 3 jobs (quality-gates → plan → apply + manual approval), OIDC module với plan role vs apply role, tflint/checkov/trivy config
- **Document:** Quick reference commands cho 5 tools, OIDC sub claim patterns, IAM Condition syntax, GitHub Actions production snippets, suppress false positives guide, common errors table, IAM minimal policies, pre-merge checklist
- **Exercises:** 5 bài tập + 1 challenge (multi-env workflow, OIDC trust tightening, custom compliance checker, scheduled drift detection, pipeline optimization, cross-account architecture design)

### Day 12 - State Strategy, Drift Detection, Cost Control, Policy as Code

**Mục tiêu:** Thiết kế state layout cho microservices, drift detection automation, cost control với Infracost, policy as code với OPA/Conftest.

- **Kiến thức:** State progression (monolithic → per-env → per-domain → per-service), `terraform_remote_state` data source, state coupling problem + SSM decoupling, drift detection với exit codes, Infracost workflow, OPA vs Conftest vs Sentinel
- **Lab:** 4 phần - state layout design, drift simulation/detection, Infracost cost estimation với diff comparison, Conftest/OPA policy writing với unit tests
- **Document:** State layout decision tree, production S3 backend config, drift detection commands, Infracost command reference, Rego policy structure guide, Sentinel examples, comparison tables, state operations reference, troubleshooting table
- **Exercises:** 7 bài tập (fintech state layout design, output rename migration, drift detection workflow, cost governance system, Rego policy suite, 6-stage CI/CD pipeline, 150-resource monolith migration)

## Cấu trúc folder

```
week-2-terraform-production/
├── README.md
├── day-07-module-design-production/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-08-multi-environment/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-09-advanced-hcl/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-10-import-refactor-lifecycle/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-11-terraform-cicd-quality-gates/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
└── day-12-state-drift-cost-policy/
    ├── lesson.md
    ├── document.md
    └── exercises.md
```

## Cách sử dụng

1. Học theo thứ tự Day 7 → Day 12 (nội dung ngày sau build trên ngày trước)
2. Mỗi ngày bắt đầu bằng `lesson.md` - đọc theory 30 phút, deep dive 30 phút, lab 60 phút
3. Tra cứu nhanh trong `document.md` khi cần reference
4. Làm thêm `exercises.md` nếu muốn nâng cao

## Yêu cầu môi trường

- **Terraform** >= 1.5.0
- **Docker** (cho Docker provider)
- **LocalStack** (optional - thay thế AWS)
- **jq** (optional - phân tích state file)

## Chi phí cloud

- Day 7-10: **Miễn phí** nếu dùng Docker/local provider hoặc LocalStack
- Day 11-12: Có thể cần AWS thật cho CI/CD OIDC và policy testing

## Tính liên tục

- **Input:** VPC module từ Day 6 (Week 1) được refactor và mở rộng xuyên suốt
- **Output:** Module patterns, multi-env structure, HCL patterns, lifecycle management được dùng lại trong Capstone (Day 28-35)
- Day 7 VPC module → Day 8 multi-env → Day 9 for_each refactor → Day 10 import/move

## Tiếp theo

**Week 3 - Ansible & ArgoCD Core** (Day 13-19)
