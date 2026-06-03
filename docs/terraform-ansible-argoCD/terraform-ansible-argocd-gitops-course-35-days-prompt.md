# Prompt: Tạo khóa học Terraform + Ansible + ArgoCD + GitOps Production trong 35 ngày

## Context về học viên

Tôi là một **senior developer** với nền tảng sau:

- Đã thành thạo: TypeScript, PHP, Python, Java, Golang, Solidity, Rust, Move
- Đã có kinh nghiệm: system design, database optimization, microservices, API Gateway, RPC, caching, Redis, Kafka, ELK, monitoring
- **Đã biết Kubernetes cơ bản**:
  - Pod
  - Deployment
  - Service
  - ConfigMap
  - Secret
  - Ingress
  - Helm
  - Kustomize
  - kubectl
- Chưa có kinh nghiệm thực chiến với:
  - Terraform
  - Ansible
  - ArgoCD
  - GitOps workflow
  - Infrastructure CI/CD
  - Production-grade platform bootstrap

## Mục tiêu khóa học

Tạo lộ trình học **35 ngày**, mỗi ngày **2 tiếng thực hành**, giúp tôi đạt trình độ có thể:

- Thiết kế và vận hành infrastructure bằng Terraform ở mức production
- Quản lý Terraform state, module, multi-environment, CI/CD, security scan và cost control đúng cách
- Sử dụng Ansible đúng vai trò cho configuration management, server hardening và automation ngoài Kubernetes
- Thiết kế GitOps workflow hoàn chỉnh với ArgoCD cho hệ microservices
- Quản lý multi-env deployment, promotion strategy, rollback, secrets, RBAC, observability và disaster recovery
- Hiểu trade-offs giữa Terraform, Ansible, Helm, Kustomize, ArgoCD, GitHub Actions, cloud-init, Packer và các pattern liên quan
- Xây dựng được một capstone production-grade có thể chạy theo 2 mode:
  - **Local/Low-cost mode**
  - **AWS Production-like mode**

---

# Nguyên tắc thiết kế khóa học

## 1. Không học kiểu toy project

Ưu tiên ví dụ từ hệ thống microservices thực tế:

- API service
- Worker service
- PostgreSQL/RDS
- Redis/ElastiCache
- Ingress/API Gateway
- Observability stack
- CI/CD pipeline
- GitOps repo
- Secrets management
- Disaster recovery

Tránh ví dụ quá đơn giản kiểu `hello-world`, trừ khi dùng để giải thích concept ban đầu.

## 2. Mỗi ngày đúng 2 tiếng

Mỗi ngày phải chia rõ:

| Phần | Thời lượng |
|---|---:|
| Kiến thức nền tảng | 30 phút |
| Deep dive & trade-offs | 30 phút |
| Hands-on lab | 60 phút |

Nếu nội dung quá nhiều:

- Giữ phần cốt lõi trong `lesson.md`
- Đưa phần mở rộng vào `document.md`
- Đưa challenge thêm vào `exercises.md`

## 3. Ưu tiên production mindset

Mỗi chủ đề quan trọng phải làm rõ:

- Vì sao cần?
- Dùng khi nào?
- Không nên dùng khi nào?
- Trade-offs là gì?
- Best solution theo từng context là gì?
- Pitfalls phổ biến là gì?
- Performance/cost/security impact là gì?

## 4. Kiểm soát chi phí cloud

Luôn có ghi chú rõ:

- Phần nào có thể chạy local bằng `kind`, `minikube`, `Docker Compose`, `LocalStack`
- Phần nào cần AWS thật
- Dịch vụ AWS nào có thể phát sinh chi phí
- Cách cleanup resource
- Cách tránh chi phí cao như NAT Gateway, ALB, RDS, ElastiCache, EKS control plane

## 5. Ngôn ngữ

- Toàn bộ nội dung viết bằng **tiếng Việt**
- Chỉ giữ nguyên thuật ngữ chuyên ngành bằng tiếng Anh, ví dụ:
  - state
  - provider
  - resource
  - module
  - backend
  - workspace
  - playbook
  - role
  - inventory
  - idempotency
  - Application
  - ApplicationSet
  - sync wave
  - reconciliation
  - drift
  - declarative
  - imperative
  - manifest
  - overlay
  - promotion
  - rollback
  - policy as code
- Không dịch:
  - lệnh CLI
  - tên file
  - tên tool
  - code keyword
  - Kubernetes resource name

---

# Phân bổ khóa học 35 ngày

| Giai đoạn | Nội dung | Số ngày |
|---|---|---:|
| Phase 1 | Terraform foundations | Day 1-6 |
| Phase 2 | Terraform production | Day 7-12 |
| Phase 3 | Ansible practical | Day 13-16 |
| Phase 4 | ArgoCD & GitOps core | Day 17-22 |
| Phase 5 | ArgoCD advanced production | Day 23-27 |
| Phase 6 | Capstone production-grade | Day 28-35 |

---

# Chi tiết từng ngày

## Phase 1 - Terraform Foundations

### Day 1 - IaC Foundations & Terraform Mental Model

Nội dung chính:

- Vì sao cần Infrastructure as Code
- Declarative vs imperative
- Terraform workflow:
  - `init`
  - `plan`
  - `apply`
  - `destroy`
- Terraform core concepts:
  - provider
  - resource
  - data source
  - state
  - dependency graph
- So sánh Terraform với script Bash, Ansible, Pulumi, CloudFormation
- Lab:
  - Cài Terraform
  - Tạo resource đơn giản bằng local provider hoặc Docker provider
  - Quan sát state file
  - Chạy `plan`, `apply`, `destroy`

### Day 2 - HCL, Variables, Outputs, Locals

Nội dung chính:

- HCL syntax
- Input variables
- Output values
- Locals
- Type constraints
- Validation rules
- Sensitive values
- Naming convention
- Lab:
  - Tạo module nhỏ mô phỏng config cho service
  - Dùng variables, outputs, locals
  - Thêm validation rule

### Day 3 - Providers, Resources, Data Sources, Dependency Graph

Nội dung chính:

- Provider configuration
- Resource lifecycle
- Data source
- Explicit vs implicit dependency
- `depends_on`
- Terraform graph
- Provider version constraint
- Lab:
  - Dùng AWS provider hoặc LocalStack
  - Tạo VPC mock/local hoặc resource AWS đơn giản
  - Phân tích dependency graph

### Day 4 - Terraform State Fundamentals

Nội dung chính:

- Terraform state là gì?
- Vì sao Terraform cần state?
- State drift
- State locking
- Local state vs remote state
- Sensitive data trong state
- Lab:
  - Inspect state
  - Simulate drift
  - Chạy `terraform refresh`
  - Sửa drift bằng Terraform

### Day 5 - Remote Backend with S3 + DynamoDB

Nội dung chính:

- Remote backend
- S3 backend
- DynamoDB lock table
- Backend bootstrap problem
- Backend per environment
- State backup
- Lab:
  - Tạo S3 bucket và DynamoDB lock table
  - Cấu hình backend
  - Test state locking
  - Cleanup an toàn

### Day 6 - Terraform Module Basics

Nội dung chính:

- Vì sao cần module?
- Root module vs child module
- Module input/output
- Module composition
- Module registry
- Versioning module
- Lab:
  - Tạo module VPC cơ bản
  - Tách network module khỏi root module
  - Dùng output từ module

---

## Phase 2 - Terraform Production

### Day 7 - Module Design for Production

Nội dung chính:

- Module boundary
- Module interface design
- Opinionated module vs flexible module
- Versioning strategy
- Avoid over-abstraction
- Reusable module cho team
- Lab:
  - Refactor VPC module
  - Thêm subnet, route table, security group
  - Thiết kế input/output rõ ràng

### Day 8 - Multi-Environment Strategy

Nội dung chính:

- Dev/staging/production structure
- Folder-based environment
- Workspace
- tfvars layering
- Terragrunt overview
- Trade-offs:
  - workspace vs folder
  - mono repo vs multi repo
  - shared module vs duplicated code
- Lab:
  - Tạo 2 môi trường `dev` và `staging`
  - Dùng cùng module nhưng khác config
  - So sánh plan output

### Day 9 - Advanced HCL: for_each, count, dynamic blocks

Nội dung chính:

- `count`
- `for_each`
- `dynamic`
- Complex types:
  - object
  - map
  - list
  - set
- `for` expression
- `merge`, `lookup`, `try`, `can`
- Pitfalls khi đổi từ `count` sang `for_each`
- Lab:
  - Tạo nhiều subnet/security group rule bằng `for_each`
  - Refactor từ `count` sang `for_each`

### Day 10 - Lifecycle, Import, Moved Blocks, Refactor Không Downtime

Nội dung chính:

- `lifecycle`
  - `prevent_destroy`
  - `ignore_changes`
  - `create_before_destroy`
- `terraform import`
- `moved` block
- Refactor resource address
- Import resource có sẵn
- Lab:
  - Import resource có sẵn
  - Refactor resource vào module
  - Dùng `moved` block để tránh recreate

### Day 11 - Terraform CI/CD, OIDC, Quality Gates

Nội dung chính:

- Terraform trong CI/CD
- PR-based workflow
- `terraform fmt`
- `terraform validate`
- `tflint`
- `trivy config`
- `checkov`
- GitHub Actions OIDC
- Không dùng long-lived AWS key
- Manual approval trước production apply
- Lab:
  - Tạo GitHub Actions workflow
  - Chạy fmt/validate/tflint/security scan
  - Tạo plan trong Pull Request

### Day 12 - Terraform State Strategy, Drift Detection, Cost Control, Policy as Code

Nội dung chính:

- Split state strategy
- State per env
- State per domain/module
- Remote state data source
- State coupling problem
- Drift detection
- Infracost
- Policy as code:
  - OPA
  - Conftest
  - Sentinel overview
- Lab:
  - Thiết kế state layout cho microservices platform
  - Thêm Infracost hoặc cost estimation step
  - Viết policy rule đơn giản kiểm tra tag/resource

---

## Phase 3 - Ansible Practical

### Day 13 - Ansible Mental Model & Idempotency

Nội dung chính:

- Ansible là gì?
- Agentless architecture
- Control node vs managed node
- SSH-based automation
- Inventory
- Playbook
- Task
- Module
- Idempotency
- So sánh với Terraform, Bash, cloud-init
- Lab:
  - Cài Ansible
  - Tạo inventory local
  - Viết playbook hardening cơ bản

### Day 14 - Variables, Facts, Conditionals, Loops, Handlers

Nội dung chính:

- Variables precedence
- Facts
- Conditionals
- Loops
- Handlers
- Templates với Jinja2 cơ bản
- Tags
- Check mode
- Diff mode
- Lab:
  - Viết playbook cài nginx hoặc node_exporter
  - Dùng handler restart service
  - Dùng template config

### Day 15 - Roles, Vault, Dynamic Inventory

Nội dung chính:

- Role structure
- Ansible Galaxy
- Ansible Vault
- Dynamic inventory với AWS
- Secret handling
- Best practices cho role
- Lab:
  - Tạo role `node_exporter`
  - Dùng vault cho secret
  - Dùng dynamic inventory lấy EC2

### Day 16 - Terraform + Ansible Integration

Nội dung chính:

- Khi nào Terraform gọi Ansible?
- Khi nào không nên gọi Ansible từ Terraform?
- Dynamic inventory từ Terraform output
- So sánh:
  - Ansible
  - cloud-init
  - user_data
  - Packer
  - SSM
- Lab:
  - Terraform tạo EC2/bastion
  - Ansible hardening bastion
  - Xuất inventory từ Terraform output
  - Viết tài liệu trade-off cho team

---

## Phase 4 - ArgoCD & GitOps Core

### Day 17 - GitOps Principles & ArgoCD Architecture

Nội dung chính:

- GitOps là gì?
- Desired state vs actual state
- Reconciliation loop
- Pull-based deployment
- ArgoCD architecture:
  - API server
  - repo server
  - application controller
  - dex
  - redis
- So sánh ArgoCD với Flux
- Lab:
  - Cài ArgoCD trên kind/minikube
  - Login CLI/UI
  - Deploy app đơn giản

### Day 18 - Application, AppProject, Sync Policy

Nội dung chính:

- Application CRD
- AppProject
- Sync policy:
  - manual
  - automated
  - self-heal
  - prune
- Sync status
- Health status
- Drift correction
- Lab:
  - Deploy app bằng Application
  - Test drift bằng cách sửa trực tiếp resource
  - Quan sát ArgoCD self-heal

### Day 19 - Helm, Kustomize, Overlays with ArgoCD

Nội dung chính:

- Helm với ArgoCD
- Kustomize với ArgoCD
- Base/overlay pattern
- Helm values per env
- Combine Helm + Kustomize
- Trade-offs:
  - Helm-only
  - Kustomize-only
  - Helm + Kustomize
- Lab:
  - Deploy microservice bằng Helm
  - Tạo overlay dev/staging
  - Override resource requests/replicas theo env

### Day 20 - GitOps Repo Structure

Nội dung chính:

- Monorepo vs polyrepo
- infra-repo
- platform-repo
- apps-repo
- Environment folder strategy
- Branch strategy
- Promotion bằng Pull Request
- Rollback bằng Git revert
- Lab:
  - Thiết kế repo structure production
  - Tạo skeleton:
    - infra
    - platform
    - apps
  - Viết README giải thích ownership

### Day 21 - App of Apps Pattern

Nội dung chính:

- App of Apps là gì?
- Root Application
- Bootstrap ordering
- App dependency
- Pros/cons của App of Apps
- Khi nào không nên dùng
- Lab:
  - Tạo root app
  - Bootstrap nhiều app con
  - Test thêm/xóa app bằng Git

### Day 22 - ApplicationSet Basics

Nội dung chính:

- ApplicationSet controller
- Generators:
  - list
  - git
  - cluster
- Template
- Multi-env deployment
- App auto-discovery
- Lab:
  - Tạo ApplicationSet deploy 3 service vào 2 env
  - Thêm service mới bằng cách thêm folder
  - Quan sát auto-generate Application

---

## Phase 5 - ArgoCD Advanced Production

### Day 23 - ApplicationSet Advanced: Matrix, Merge, Multi-Cluster

Nội dung chính:

- Matrix generator
- Merge generator
- Cluster generator
- Multi-cluster GitOps
- Naming convention
- Scale issue khi có nhiều app/env/cluster
- Lab:
  - Deploy app matrix theo service x environment
  - Mô phỏng multi-cluster bằng nhiều namespace/context
  - Tối ưu naming và labels

### Day 24 - Sync Waves, Hooks, Dependencies

Nội dung chính:

- Sync waves
- Resource hooks:
  - PreSync
  - Sync
  - PostSync
  - SyncFail
- CRD ordering
- Database migration job
- Pitfalls với hook job
- Lab:
  - Deploy app có migration job
  - Dùng sync wave cho database secret trước app
  - Test failure scenario

### Day 25 - Secrets Management, RBAC, SSO, Private Repo

Nội dung chính:

- Kubernetes Secret thường
- Sealed Secrets
- External Secrets Operator
- SOPS + age/KMS
- AWS Secrets Manager
- HashiCorp Vault overview
- ArgoCD RBAC
- SSO overview
- Private repo credentials
- Best solution:
  - Small team
  - Startup
  - Enterprise
  - Bank/regulated environment
- Lab:
  - Cài External Secrets Operator
  - Dùng AWS Secrets Manager hoặc local secret store
  - Cấu hình ArgoCD repo credential
  - Viết RBAC policy mẫu

### Day 26 - Argo Rollouts, Progressive Delivery

Nội dung chính:

- Rolling update vs blue-green vs canary
- Argo Rollouts
- Analysis template
- Metrics-based promotion
- Rollback
- Trade-offs:
  - Kubernetes Deployment
  - Argo Rollouts
  - Service mesh rollout
- Lab:
  - Cài Argo Rollouts
  - Deploy canary rollout
  - Simulate bad version
  - Rollback

### Day 27 - ArgoCD Observability, Notifications, Backup & Disaster Recovery

Nội dung chính:

- Metrics của ArgoCD
- Prometheus scrape
- Grafana dashboard
- Notifications:
  - Slack
  - email
  - webhook
- Backup:
  - ArgoCD config
  - repo credentials
  - cluster secrets
- Disaster recovery strategy
- Lab:
  - Expose ArgoCD metrics
  - Cấu hình notification mock
  - Backup và restore ArgoCD app config

---

## Phase 6 - Capstone Production-Grade

## Capstone Overview

Capstone cần xây dựng một platform cho hệ microservices gồm:

- 3 microservices:
  - `api-service`
  - `worker-service`
  - `frontend-service`
- Database:
  - PostgreSQL hoặc RDS
- Cache:
  - Redis hoặc ElastiCache
- Container registry:
  - GitHub Container Registry hoặc ECR
- GitOps deployment:
  - ArgoCD
  - ApplicationSet
  - Helm/Kustomize
- Secrets:
  - External Secrets Operator
  - AWS Secrets Manager hoặc local secret store
- Observability:
  - Prometheus
  - Grafana
  - Loki hoặc logging stack tương đương
- CI/CD:
  - GitHub Actions
  - Build/test/push image
  - Update image tag bằng Pull Request
- Reliability:
  - Rollback
  - Disaster recovery
  - Runbook

Capstone phải hỗ trợ 2 mode.

### Mode A - Local/Low-cost

Dùng cho học viên muốn tránh chi phí cloud.

Gợi ý stack:

- kind hoặc minikube
- Docker Compose cho PostgreSQL/Redis nếu cần
- LocalStack nếu cần mock AWS
- GitHub Container Registry
- NGINX Ingress Controller
- self-signed certificate hoặc cert-manager local issuer
- External Secrets với local provider/mock
- Prometheus/Grafana local

### Mode B - AWS Production-like

Dùng khi muốn mô phỏng production thật.

Gợi ý stack:

- AWS VPC
- EKS
- ECR
- RDS PostgreSQL
- ElastiCache Redis
- IAM/IRSA
- ALB Controller
- Route53
- ACM
- AWS Secrets Manager
- CloudWatch integration nếu cần

Cần ghi rõ:

- Dịch vụ nào phát sinh chi phí
- Ước tính chi phí tương đối
- Cách cleanup
- Cách tránh NAT Gateway nếu không bắt buộc
- Cách dùng spot node group để giảm chi phí

---

### Day 28 - Capstone Architecture, Repo Strategy, Cost Strategy

Nội dung chính:

- Thiết kế kiến trúc tổng thể
- Phân tách repo:
  - `infra-repo`
  - `platform-repo`
  - `apps-repo`
- Local mode vs AWS mode
- Cost strategy
- Security baseline
- Environment strategy:
  - dev
  - staging
  - production-like
- Lab:
  - Tạo repo skeleton
  - Tạo architecture diagram ASCII
  - Viết ADR đầu tiên cho platform

### Day 29 - Infrastructure Network Layer

Nội dung chính:

- VPC design
- Public/private subnet
- Route table
- NAT Gateway trade-off
- Security group
- Network ACL overview
- DNS basics
- Lab:
  - Local mode: chuẩn bị kind network
  - AWS mode: tạo VPC module
  - Output network config cho layer sau

### Day 30 - Kubernetes & IAM Layer

Nội dung chính:

- EKS/kind cluster
- Node group
- Managed node group vs self-managed
- Spot instance trade-off
- IAM/IRSA
- ECR/GHCR
- Lab:
  - Local mode: tạo kind cluster
  - AWS mode: tạo EKS + node group + IRSA
  - Push image mẫu vào registry

### Day 31 - Data Layer: PostgreSQL, Redis, Secrets

Nội dung chính:

- PostgreSQL local vs RDS
- Redis local vs ElastiCache
- Backup strategy
- Secret storage
- Connection string management
- Lab:
  - Local mode: PostgreSQL/Redis bằng Helm hoặc Docker Compose
  - AWS mode: RDS + ElastiCache
  - Lưu secret vào local secret store hoặc AWS Secrets Manager

### Day 32 - Platform Bootstrap Layer

Nội dung chính:

- Bootstrap order
- ArgoCD
- External Secrets Operator
- Cert Manager
- Ingress Controller hoặc ALB Controller
- Prometheus stack
- Terraform `helm_release` vs ArgoCD bootstrap
- Trade-off:
  - Terraform quản lý Helm
  - ArgoCD quản lý Helm
  - Hybrid bootstrap
- Lab:
  - Cài ArgoCD
  - Bootstrap platform apps bằng App of Apps hoặc ApplicationSet
  - Cài External Secrets, Ingress, Cert Manager

### Day 33 - GitOps Apps Layer & Promotion Strategy

Nội dung chính:

- Apps repo structure
- Helm chart cho microservice
- Kustomize overlay cho env
- ApplicationSet auto-detect service
- Image tag strategy:
  - immutable tag
  - git sha
  - semver
  - latest không nên dùng cho production
- Promotion:
  - dev auto-sync
  - staging qua PR
  - production manual approval
- Rollback:
  - Git revert
  - sync previous revision
- Lab:
  - Deploy 3 microservices
  - Cấu hình dev/staging/prod-like
  - Thực hiện promotion dev → staging

### Day 34 - CI/CD, Observability, Reliability

Nội dung chính:

- GitHub Actions pipeline:
  - lint
  - test
  - build
  - scan image
  - push image
  - update GitOps repo bằng PR
- Observability:
  - Prometheus
  - Grafana
  - Loki/logging
  - alert rules
- Reliability:
  - readiness/liveness probe
  - resource requests/limits
  - HPA overview
  - PodDisruptionBudget
- Lab:
  - Tạo pipeline build/push image
  - Auto update image tag trong apps repo
  - Tạo dashboard cơ bản
  - Tạo alert rule mẫu

### Day 35 - Disaster Recovery, Final Demo, Runbook, Retrospective

Nội dung chính:

- Disaster scenarios:
  - mất cluster
  - mất ArgoCD
  - sai secret
  - deployment lỗi
  - Terraform state lỗi
  - rollback app
- Recovery checklist
- Runbook
- Final demo
- Retrospective:
  - cái gì production-ready
  - cái gì chỉ là simulation
  - next steps
- Lab:
  - Xóa app khỏi cluster và restore bằng ArgoCD
  - Simulate bad deployment và rollback
  - Export runbook
  - Cleanup toàn bộ resource

---

# Cấu trúc folder yêu cầu

Tạo cấu trúc folder như sau:

```text
terraform-ansible-argocd-gitops-course/
├── week-1-terraform-foundations/
│   ├── day-01-iac-foundations/
│   │   ├── lesson.md
│   │   ├── document.md
│   │   └── exercises.md
│   ├── day-02-hcl-variables-outputs/
│   ├── day-03-providers-resources-data-sources/
│   ├── day-04-terraform-state-fundamentals/
│   ├── day-05-remote-backend/
│   └── day-06-module-basics/
├── week-2-terraform-production/
│   ├── day-07-module-design-production/
│   ├── day-08-multi-environment/
│   ├── day-09-advanced-hcl/
│   ├── day-10-import-refactor-lifecycle/
│   ├── day-11-terraform-cicd-quality-gates/
│   └── day-12-state-drift-cost-policy/
├── week-3-ansible-argocd-core/
│   ├── day-13-ansible-mental-model/
│   ├── day-14-ansible-variables-handlers/
│   ├── day-15-ansible-roles-vault-inventory/
│   ├── day-16-terraform-ansible-integration/
│   ├── day-17-gitops-argocd-architecture/
│   ├── day-18-argocd-application-project-sync/
│   └── day-19-helm-kustomize-argocd/
├── week-4-argocd-advanced/
│   ├── day-20-gitops-repo-structure/
│   ├── day-21-app-of-apps/
│   ├── day-22-applicationset-basics/
│   ├── day-23-applicationset-advanced/
│   ├── day-24-sync-waves-hooks/
│   ├── day-25-secrets-rbac-sso/
│   ├── day-26-argo-rollouts/
│   └── day-27-argocd-observability-dr/
└── week-5-capstone/
    ├── day-28-capstone-architecture/
    ├── day-29-infra-network-layer/
    ├── day-30-kubernetes-iam-layer/
    ├── day-31-data-layer-secrets/
    ├── day-32-platform-bootstrap/
    ├── day-33-gitops-apps-promotion/
    ├── day-34-cicd-observability-reliability/
    └── day-35-disaster-recovery-demo/
```

---

# Yêu cầu nội dung cho mỗi ngày

## File bắt buộc: lesson.md

Mỗi `lesson.md` phải có đầy đủ các phần sau.

### 1. Mục tiêu ngày học

Gồm 3-5 bullet cụ thể, đo lường được.

Ví dụ:

```md
Sau ngày học này, bạn có thể:
- Giải thích được Terraform state dùng để làm gì
- Cấu hình được remote backend bằng S3 + DynamoDB
- Mô phỏng được state locking conflict
- Phân biệt được local state và remote state trong môi trường team
```

### 2. Bối cảnh thực tế

Giải thích:

- Vấn đề thực tế là gì?
- Nếu không dùng tool/pattern này thì team gặp lỗi gì?
- Vấn đề này thường xuất hiện trong hệ thống microservices như thế nào?

### 3. Kiến thức nền tảng - 30 phút

Yêu cầu:

- Giải thích từ cơ bản đến chi tiết
- Luôn trả lời câu hỏi “tại sao cần?” trước khi “làm thế nào?”
- Dùng analogy với programming, database, microservices hoặc Kubernetes khi phù hợp
- Có diagram ASCII hoặc mô tả visual nếu concept phức tạp
- Không giải thích quá dài các phần học viên đã biết như Git, Docker, Kubernetes cơ bản

### 4. Deep dive & Trade-offs - 30 phút

Yêu cầu:

- Phân tích ít nhất 2-3 cách tiếp cận
- So sánh bằng bảng nếu phù hợp
- Chỉ rõ best solution theo từng context:
  - cá nhân học tập
  - small team
  - startup
  - enterprise
  - bank/regulated environment
- Có phần:
  - performance implications
  - cost implications
  - security implications
  - operational complexity
- Có common pitfalls và cách tránh

### 5. Hands-on Lab - 60 phút

Yêu cầu:

- Step-by-step rõ ràng
- Code snippets đầy đủ
- Không để học viên phải đoán
- Có expected output ở các bước quan trọng
- Có troubleshooting cho lỗi phổ biến
- Có cleanup step nếu tạo resource cloud
- Nếu lab có cloud cost, phải cảnh báo rõ trước khi làm

### 6. Kiểm tra hiểu bài

Gồm 3-5 câu hỏi/bài tập ngắn.

Nên có các dạng:

- Giải thích concept
- Chọn approach tốt nhất cho một context
- Debug lỗi phổ biến
- Refactor config
- Nhận diện trade-off

### 7. Tóm tắt cuối ngày

Gồm:

- 3-5 ý quan trọng nhất
- Output đã tạo ra
- Kiến thức chuẩn bị cho ngày tiếp theo

### 8. Tham khảo thêm

Chỉ dùng link quan trọng:

- Official docs
- Blog kỹ thuật chất lượng cao
- Không spam quá nhiều link
- Ưu tiên tài liệu còn mới và có tính thực tế

---

# File optional: document.md

Tạo `document.md` khi cần:

- Cheat sheet
- Reference table
- Architecture diagram chi tiết
- Comparison matrix
- Best practices checklist
- ADR template
- Runbook template
- Security checklist
- Cost optimization checklist

Ví dụ:

```md
# Terraform State Strategy Cheat Sheet
# ArgoCD ApplicationSet Generator Comparison
# GitOps Promotion Strategy Reference
# AWS Cost Control Checklist
```

---

# File optional: exercises.md

Tạo `exercises.md` khi cần:

- Bài tập mở rộng
- Challenge ngoài lab chính
- Variation cho nhiều context
- Debug scenario
- Design review
- Production incident simulation

Ví dụ:

```md
# Exercises

## Challenge 1: Refactor module không downtime

## Challenge 2: Thiết kế state layout cho 5 team

## Challenge 3: Debug ArgoCD OutOfSync nhưng resource không thay đổi
```

---

# Style và tone

## Phong cách giải thích

Viết như một **senior engineer có kinh nghiệm DevOps/Platform Engineering đang mentor cho senior developer chuyển sang domain mới**.

Yêu cầu:

- Không patronizing
- Không giải thích quá sơ cấp ở phần học viên đã biết
- Rất chi tiết ở phần mới:
  - Terraform state
  - module design
  - remote backend
  - Ansible idempotency
  - ArgoCD reconciliation loop
  - ApplicationSet
  - GitOps promotion
  - secrets management
  - disaster recovery
- Câu văn ngắn gọn
- Kỹ thuật chính xác
- Có ví dụ thực tế

## Code quality

Code mẫu phải:

- Có cấu trúc production-like
- Có naming convention rõ
- Có comment khi cần
- Tránh hard-code secret
- Có version constraint
- Có provider constraint
- Có README/context nếu cần
- Có cleanup instruction

## Trade-off mindset

Không viết kiểu:

```md
Nên dùng External Secrets vì nó tốt.
```

Phải viết kiểu:

```md
Với hệ thống chạy trên AWS và đã dùng IAM/IRSA, External Secrets Operator + AWS Secrets Manager thường là lựa chọn tốt hơn Sealed Secrets vì secret gốc không nằm trong Git, rotation dễ hơn, audit tốt hơn. Đổi lại, hệ thống phụ thuộc vào AWS Secrets Manager và cần cấu hình IAM chính xác.
```

---

# Ràng buộc quan trọng

## 1. Tính liên tục

Ngày sau phải build trên output của ngày trước.

Ví dụ:

- Terraform module từ Day 6 được dùng lại trong Day 8
- State strategy từ Day 12 được áp dụng trong capstone
- Ansible role từ Day 15 được dùng lại ở Day 16
- ArgoCD Application từ Day 18 được refactor sang ApplicationSet ở Day 22
- Repo structure từ Day 20 dùng lại trong capstone Day 28-35

## 2. Không nhồi quá nhiều trong 1 ngày

Nếu một ngày có quá nhiều nội dung:

- Giữ core path trong `lesson.md`
- Đưa phần nâng cao sang `document.md`
- Đưa phần thực hành thêm sang `exercises.md`

## 3. Production-grade nhưng có kiểm soát

Capstone phải thực tế nhưng không được vượt quá khả năng học 2 tiếng/ngày.

Cần chia rõ:

- Must-have
- Should-have
- Nice-to-have

## 4. Cloud cost safety

Bất kỳ ngày nào dùng AWS thật phải có:

```md
## Cảnh báo chi phí

Các resource có thể phát sinh chi phí:
- ...
Ước tính chi phí:
- ...
Cách giảm chi phí:
- ...
Cleanup:
- ...
```

## 5. Security baseline

Bất kỳ lab production-like nào phải tránh:

- hard-code secret
- dùng AWS access key dài hạn nếu có thể dùng OIDC
- public database
- security group mở `0.0.0.0/0` không kiểm soát
- image tag `latest` cho production
- apply thẳng production không approval

## 6. Output rõ ràng

Mỗi ngày phải nói rõ học viên tạo được gì.

Ví dụ:

```md
## Output cuối ngày

Sau ngày này, bạn có:
- Một Terraform module VPC có thể reuse
- Một remote backend S3 + DynamoDB
- Một GitHub Actions workflow chạy fmt/validate/tflint
```

---

# Cách thực hiện khi generate khóa học

Hãy tạo từng ngày một cách tuần tự.

Với mỗi ngày:

1. Xác nhận sẽ tạo những file nào:
   - `lesson.md` bắt buộc
   - `document.md` nếu cần
   - `exercises.md` nếu cần
2. Tạo đầy đủ nội dung từng file
3. Đảm bảo nội dung phù hợp với 2 tiếng học
4. Không chuyển sang ngày tiếp theo cho đến khi tôi feedback
5. Sau mỗi ngày, hỏi tôi có muốn điều chỉnh gì trước khi tạo ngày tiếp theo không

Bắt đầu từ **Day 1 - IaC Foundations & Terraform Mental Model**.
