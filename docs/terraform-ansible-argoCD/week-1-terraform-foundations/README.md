# Week 1 - Terraform Foundations (Day 1-6)

## Tổng quan

Week 1 xây dựng nền tảng Terraform từ zero đến production-ready module design. Mỗi ngày 2 tiếng thực hành, thiết kế cho senior developer chuyển sang DevOps/Platform Engineering.

## Lộ trình học

| Ngày | Chủ đề | Thời lượng | Files |
|------|--------|------------|-------|
| Day 1 | IaC Foundations & Terraform Mental Model | 2h | lesson, document, exercises |
| Day 2 | HCL, Variables, Outputs, Locals | 2h | lesson, document, exercises |
| Day 3 | Providers, Resources, Data Sources, Dependency Graph | 2h | lesson, document, exercises |
| Day 4 | Terraform State Fundamentals | 2h | lesson, document, exercises |
| Day 5 | Remote Backend with S3 + DynamoDB | 2h | lesson, document, exercises |
| Day 6 | Terraform Module Basics | 2h | lesson, document, exercises |

## Chi tiết từng ngày

### Day 1 - IaC Foundations & Terraform Mental Model

**Mục tiêu:** Hiểu tại sao cần IaC, nắm Terraform workflow (init/plan/apply/destroy), phân biệt declarative vs imperative.

- **Kiến thức:** IaC rationale, Terraform core concepts (provider, resource, data source, state, dependency graph), so sánh với Bash/Ansible/Pulumi/CloudFormation
- **Lab:** Docker provider - tạo container, quan sát state file, chạy full lifecycle
- **Document:** IaC comparison cheat sheet, Terraform CLI reference
- **Exercises:** 5 bài tập tăng dần (thêm Redis container, `for_each`, `terraform import`, multi-container stack)

### Day 2 - HCL, Variables, Outputs, Locals

**Mục tiêu:** Thành thạo HCL syntax, type system, variable management, validation rules.

- **Kiến thức:** HCL syntax, input variables, output values, locals, type constraints, validation rules, sensitive values, naming conventions
- **Lab:** Docker provider - tạo module `app-service` với variables/outputs/locals, dev/prod tfvars
- **Document:** HCL type system reference, validation patterns, anti-patterns reference
- **Exercises:** Complex types, validation scenarios, output patterns, module interface design

### Day 3 - Providers, Resources, Data Sources, Dependency Graph

**Mục tiêu:** Hiểu provider configuration, resource lifecycle, data source, dependency management.

- **Kiến thức:** Provider config/alias, resource lifecycle (CRUD), data source vs resource, implicit/explicit dependency, `depends_on`, `terraform graph`
- **Lab:** Docker provider - 4-resource stack với dependencies, graph visualization, port change replacement demo
- **Document:** Version constraint reference, provider alias patterns, lifecycle meta-argument reference
- **Exercises:** 7 bài tập (provider audit, dependency graph, multi-region aliasing, circular dependency fix)

### Day 4 - Terraform State Fundamentals

**Mục tiêu:** Hiểu state file, drift detection, state locking, state commands, state security.

- **Kiến thức:** State purpose, JSON structure deep dive, drift taxonomy, locking mechanics, local vs remote state, sensitive data exposure
- **Lab:** Docker provider - inspect state, simulate drift via `docker rm`, detect/remediate drift, practice state mv/rm/pull/import
- **Document:** State commands cheat sheet, troubleshooting guide, security checklist, IAM policy template
- **Exercises:** 6 bài tập (state inspection, drift scenarios, refactoring, state recovery, security audit)

### Day 5 - Remote Backend with S3 + DynamoDB

**Mục tiêu:** Cấu hình remote backend, giải quyết bootstrap problem, state migration, multi-env backend.

- **Kiến thức:** Remote backend concept, S3 backend config, DynamoDB locking, bootstrap problem, backend per environment, state backup/versioning
- **Lab:** Hai paths - AWS thật hoặc LocalStack (free), tạo S3+DynamoDB, configure backend, test locking, migrate state
- **Document:** S3 backend security checklist, backend comparison matrix, migration checklist
- **Exercises:** Backend migration challenge, multi-environment setup, state locking simulation

### Day 6 - Terraform Module Basics

**Mục tiêu:** Hiểu module concept, tạo và sử dụng module, module composition, versioning.

- **Kiến thức:** Root module vs child module, module input/output, module composition, module registry, versioning strategy
- **Lab:** Tạo VPC module cơ bản, tách network module khỏi root module, dùng output từ module, tạo 2 instance (dev + staging) để demo reuse
- **Document:** Module structure reference, input/output patterns, registry usage guide, versioning best practices
- **Exercises:** 8 bài tập (cross-variable validation, multi-region module, 3-layer composition, state address debug, version upgrade, code review, registry investigation, for_each with module)

## Cấu trúc folder

```
week-1-terraform-foundations/
├── README.md
├── day-01-iac-foundations/
│   ├── lesson.md          # Bài học chính (2h)
│   ├── document.md        # Cheat sheet & reference
│   └── exercises.md       # Bài tập mở rộng
├── day-02-hcl-variables-outputs/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-03-providers-resources-data-sources/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-04-terraform-state-fundamentals/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-05-remote-backend/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
└── day-06-module-basics/
    ├── lesson.md
    ├── document.md
    └── exercises.md
```

## Cách sử dụng

1. Học theo thứ tự Day 1 → Day 5 (nội dung ngày sau build trên ngày trước)
2. Mỗi ngày bắt đầu bằng `lesson.md` - đọc theory 30 phút, deep dive 30 phút, lab 60 phút
3. Tra cứu nhanh trong `document.md` khi cần reference
4. Làm thêm `exercises.md` nếu muốn nâng cao

## Yêu cầu môi trường

- **Terraform** >= 1.5.0
- **Docker** (cho Docker provider - dùng xuyên suốt week 1, không cần cloud account)
- **LocalStack** (optional - thay thế AWS cho Day 5)
- **jq** (optional - phân tích state file)

## Chi phí cloud

- Day 1-4: **Miễn phí** (dùng Docker/local provider)
- Day 5: **Miễn phí** nếu dùng LocalStack, ~$0.5-1/tháng nếu dùng AWS thật (S3 + DynamoDB)

## Tiếp theo

**Day 6 - Terraform Module Basics** (Week 1 tiếp tục với Phase 1)
