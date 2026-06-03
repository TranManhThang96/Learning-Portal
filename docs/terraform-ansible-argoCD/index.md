# Terraform + Ansible + ArgoCD — 35 ngày từ zero đến GitOps production

Lộ trình dành cho Senior Developer đã biết Kubernetes cơ bản muốn mastering Infrastructure as Code với Terraform, configuration management với Ansible, và GitOps workflow với ArgoCD. 35 ngày, mỗi ngày 2 giờ (30' theory — 30' deep dive — 60' lab), local-first với Docker, kind, Terraform, Ansible, ArgoCD.

Khóa học được thiết kế với production mindset: tránh toy project, ưu tiên stack microservices thực tế (API service, worker, PostgreSQL, Redis, observability), và capstone hỗ trợ 2 mode (Local free / AWS production-like).

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể viết Terraform module, tự động hóa server bằng Ansible, và deploy GitOps với ArgoCD:

1. [Day 1: IaC Foundations & Terraform Mental Model](./week-1-terraform-foundations/day-01-iac-foundations/lesson) — provider, resource, state, init/plan/apply workflow
2. [Day 2: HCL, Variables, Outputs, Locals](./week-1-terraform-foundations/day-02-hcl-variables-outputs/lesson) — HCL syntax, variable management, validation
3. [Day 4: Terraform State Fundamentals](./week-1-terraform-foundations/day-04-terraform-state-fundamentals/lesson) — state là gì, drift, locking, local vs remote
4. [Day 5: Remote Backend with S3 + DynamoDB](./week-1-terraform-foundations/day-05-remote-backend/lesson) — remote state cho team, state locking
5. [Day 6: Terraform Module Basics](./week-1-terraform-foundations/day-06-module-basics/lesson) — module composition, reuse, versioning
6. [Day 8: Multi-Environment Strategy](./week-2-terraform-production/day-08-multi-environment/lesson) — dev/staging/prod, workspace vs folder
7. [Day 11: Terraform CI/CD, OIDC, Quality Gates](./week-2-terraform-production/day-11-terraform-cicd-quality-gates/lesson) — GitHub Actions, plan-on-PR, apply-on-merge
8. [Day 13: Ansible Mental Model & Idempotency](./week-3-ansible-argocd-core/day-13-ansible-mental-model/lesson) — agentless, inventory, idempotency
9. [Day 17: GitOps Principles & ArgoCD Architecture](./week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/lesson) — pull-based, reconciliation, ArgoCD install
10. [Day 18: Application, AppProject, Sync Policy](./week-3-ansible-argocd-core/day-18-argocd-application-project-sync/lesson) — Application CRD, sync strategies, self-heal
11. [Day 22: ApplicationSet Basics](./week-4-argocd-advanced/day-22-applicationset-basics/lesson) — multi-env deploy, git generator, template

Sau 11 bài này bạn đã có thể quản lý infrastructure bằng Terraform, tự động hóa config bằng Ansible, và deploy microservices với GitOps (ArgoCD) lên Kubernetes.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---|
| Phase 1 — Terraform Foundations | Day 1-6 | IaC, HCL, state, remote backend, module | Terraform module VPC có thể reuse |
| Phase 2 — Terraform Production | Day 7-12 | Module design, multi-env, advanced HCL, CI/CD, policy | Production-grade Terraform pipeline |
| Phase 3 — Ansible & ArgoCD Core | Day 13-19 | Ansible config management, ArgoCD GitOps core | Ansible roles + ArgoCD cluster |
| Phase 4 — ArgoCD Advanced | Day 20-27 | ApplicationSet, sync waves, secrets, rollouts, DR | Multi-env GitOps platform |
| Phase 5 — Capstone | Day 28-35 | End-to-end platform với 3 microservices | Production-grade platform (local/AWS) |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 1 | IaC Foundations & Terraform Mental Model | Nền tảng toàn bộ khóa học; không hiểu provider/resource/state thì không làm được Terraform |
| Day 2 | HCL, Variables, Outputs, Locals | HCL là ngôn ngữ chính; variable + output là interface module căn bản |
| Day 4 | Terraform State Fundamentals | State là core concept dễ gây lỗi nhất; drift + lock + sensitive data |
| Day 5 | Remote Backend S3 + DynamoDB | State sharing trong team; bootstrap problem; state migration |
| Day 6 | Terraform Module Basics | Module là đơn vị tái sử dụng; không biết module thì code Terraform như script |
| Day 8 | Multi-Environment Strategy | Dev/staging/prod là yêu cầu thực tế bắt buộc |
| Day 11 | Terraform CI/CD, OIDC | CI/CD Terraform + OIDC thay long-lived credential |
| Day 13 | Ansible Mental Model & Idempotency | Agentless architecture, idempotency — core concept Ansible |
| Day 17 | GitOps Principles & ArgoCD Architecture | Tư duy GitOps, pull-based, reconciliation loop |
| Day 18 | Application, AppProject, Sync Policy | Application CRD là resource chính của ArgoCD |
| Day 22 | ApplicationSet Basics | Multi-env deploy tự động; generator List/Git |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 3 | Providers, Resources, Data Sources | Dependency graph, data source pattern dùng thường xuyên |
| Day 7 | Module Design for Production | Module boundary, interface design, tránh over-abstraction |
| Day 9 | Advanced HCL: for_each, count, dynamic | for_each vs count là nguyên nhân #1 refactor đau đầu |
| Day 10 | Lifecycle, Import, Moved Blocks | Import resource có sẵn, refactor không downtime |
| Day 12 | State Strategy, Drift, Cost, Policy | Split state, drift detection, Infracost |
| Day 14 | Ansible Variables, Facts, Handlers | Variable precedence, facts, jinja2 template |
| Day 15 | Ansible Roles, Vault, Inventory | Role structure, Ansible Vault, dynamic inventory |
| Day 16 | Terraform + Ansible Integration | Khi nào dùng Ansible vs cloud-init vs Packer |
| Day 19 | Helm, Kustomize, Overlays với ArgoCD | Base/overlay pattern, Helm + Kustomize combine |
| Day 20 | GitOps Repo Structure | Monorepo vs polyrepo, 3-repo pattern |
| Day 21 | App of Apps Pattern | Bootstrap ordering, root Application |
| Day 25 | Secrets Management, RBAC, SSO | External Secrets Operator, ArgoCD RBAC |
| Day 26 | Argo Rollouts, Progressive Delivery | Canary deployment, AnalysisTemplate |
| Day 28 | Capstone Architecture & Strategy | Bắt đầu capstone — repo, cost, security baseline |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---|
| Day 23 | ApplicationSet Advanced (Matrix, Merge) | Khi cần multi-cluster hoặc matrix deployment phức tạp |
| Day 24 | Sync Waves, Hooks, Dependencies | Khi cần DB migration, dependency ordering |
| Day 27 | ArgoCD Observability, Notifications, DR | Khi vận hành ArgoCD production thật |
| Day 29-35 | Capstone chi tiết | Làm capstone sau khi đã học hết nhóm A+B |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---|
| Các file `document.md` | Cheat sheet, templates, reference | Tra cứu khi cần |
| `exercises.md` nâng cao | Bài tập mở rộng | Làm sau khi hoàn thành core path |
| Day 30 (mode B details) | AWS EKS, IRSA, Spot | Khi cần production trên AWS thật |

## Cách học đề xuất

1. **Phase 1** (Day 1-6): Terraform Foundations — provider/resource/state/module. Nắm vững 20% tạo 80% cho toàn bộ IaC.
2. **Phase 2** (Day 7-12): Terraform Production — multi-env, CI/CD, state strategy, cost control.
3. **Phase 3** (Day 13-19): Ansible + ArgoCD Core — từ Ansible basics đến GitOps với ArgoCD.
4. **Phase 4** (Day 20-27): ArgoCD Advanced — ApplicationSet, sync waves, secrets, rollouts, DR.
5. **Phase 5** (Day 28-35): Capstone — build production platform, chạy local free hoặc AWS.

Mỗi ngày học 2 giờ theo format:
- 30 phút: theory & concept
- 30 phút: deep dive & trade-offs
- 60 phút: hands-on lab

## Capstone — Production Platform

**Mô tả:** Xây dựng platform end-to-end cho 3 microservices (`api-service`, `worker-service`, `frontend-service`) + PostgreSQL + Redis + GitOps deploy + Observability + CI/CD + DR.

**Stack:**
- Terraform (VPC, EKS, RDS, ElastiCache, IAM)
- Ansible (bastion hardening, node_exporter)
- ArgoCD + ApplicationSet (GitOps deployment)
- GitHub Actions (CI/CD pipeline)
- Prometheus + Grafana + Loki (observability)
- External Secrets Operator (secrets management)

**2 mode:**
- Mode A (Local/Low-cost): kind + Docker Compose + LocalStack + GHCR — miễn phí
- Mode B (AWS Production-like): EKS + RDS + ElastiCache + ECR — ~$150-277/tháng

**Tiêu chí hoàn thành:**
- 3-repo structure (infra / platform / apps)
- Terraform modules cho network + cluster + data
- ApplicationSet deploy 3 services × 3 environments
- GitHub Actions pipeline + image scanning
- Prometheus + Grafana dashboard + alert rules
- DR runbook + rollback procedure

## Checklist học nhanh

- [ ] Tôi đã hiểu Terraform workflow: init → plan → apply → destroy
- [ ] Tôi đã biết phân biệt local state vs remote state (S3 + DynamoDB)
- [ ] Tôi đã viết được Terraform module có thể tái sử dụng
- [ ] Tôi đã cấu hình multi-environment (dev/staging/prod) với tfvars
- [ ] Tôi đã thiết lập CI/CD cho Terraform với GitHub Actions + OIDC
- [ ] Tôi đã viết Ansible playbook với handler, template, vault
- [ ] Tôi đã biết khi nào dùng Ansible vs cloud-init vs Packer vs SSM
- [ ] Tôi đã cài ArgoCD và deploy app đầu tiên
- [ ] Tôi đã dùng ApplicationSet để deploy multi-env
- [ ] Tôi đã cấu hình External Secrets Operator cho secret management
- [ ] Tôi đã hiểu GitOps promotion workflow (dev auto → staging PR → prod manual)
- [ ] Tôi đã hoàn thành capstone production platform

## Flashcard / câu hỏi ôn tập gợi ý

1. **Declarative vs Imperative khác nhau thế nào trong context IaC?**
   - **Đáp án:** Declarative = khai báo desired state (Terraform, Kubernetes), hệ thống tự tính diff và thực thi. Imperative = viết từng bước (Bash script, Ansible module có thể không idempotent nếu viết sai).
   - **Liên quan:** Day 1

2. **Terraform state dùng để làm gì? Vì sao không nên để local state trong team?**
   - **Đáp án:** State map resource khai báo ↔ resource thật trong cloud. Local state gây conflict khi nhiều người cùng apply; cần remote backend (S3) + state locking (DynamoDB).
   - **Liên quan:** Day 4-5

3. **for_each vs count — khi nào dùng cái nào?**
   - **Đáp án:** `for_each` với map/set → stable address (xóa phần tử giữa không ảnh hưởng phần khác). `count` với list → index-based, xóa phần tử giữa shift index gây recreate.
   - **Liên quan:** Day 9

4. **Workspace vs folder-based environment — trade-off là gì?**
   - **Đáp án:** Workspace đơn giản nhưng state chung 1 backend, dễ nhầm. Folder-based tách biệt state file per env, rõ ràng hơn, recommended cho production.
   - **Liên quan:** Day 8

5. **Ansible idempotency có nghĩa là gì?**
   - **Đáp án:** Chạy playbook N lần → kết quả giống nhau. Ansible module kiểm tra state hiện tại trước khi thực thi, chỉ change khi cần. Không idempotent = script Bash chạy 2 lần fail.
   - **Liên quan:** Day 13

6. **Khi nào dùng Ansible, khi nào dùng cloud-init/Packer/Terraform?**
   - **Đáp án:** cloud-init = first boot user_data, Packer = bake AMI cố định, Terraform = infra provisioning, Ansible = config management sau provision. Ansible phù hợp cho server hardening, app config, không phải để provision infra.
   - **Liên quan:** Day 16

7. **GitOps khác CI/CD truyền thống thế nào?**
   - **Đáp án:** GitOps = Git là single source of truth + pull-based (ArgoCD operator trong cluster kéo từ Git). CI/CD truyền thống push-based (Jenkins push deploy lên server).
   - **Liên quan:** Day 17

8. **ArgoCD ApplicationSet khác App of Apps thế nào?**
   - **Đáp án:** ApplicationSet = template + generator → tự động tạo Application theo data (list, git, cluster). App of Apps = root Application quản lý child Application YAML cố định. ApplicationSet cho multi-env/multi-service, App of Apps cho bootstrap ordering cố định.
   - **Liên quan:** Day 21-22

9. **External Secrets Operator (ESO) giải quyết vấn đề gì so với Kubernetes Secret thường?**
   - **Đáp án:** Kubernetes Secret chỉ base64, không encrypt, không Git-friendly. ESO sync secret từ external store (AWS Secrets Manager, Vault, etc.) vào Kubernetes Secret, cho phép GitOps workflow mà không lộ secret trong Git.
   - **Liên quan:** Day 25

10. **Khi nào dùng Argo Rollouts thay vì Kubernetes Deployment thường?**
    - **Đáp án:** Khi cần canary với traffic percent, analysis dựa trên metrics, auto-promote/rollback. Deployment + RollingUpdate chỉ step-wise, không thể analysis hay abort dựa trên metric.
    - **Liên quan:** Day 26

11. **Rollback trong GitOps — cách nào an toàn nhất?**
    - **Đáp án:** Git revert (không phải `git reset --hard`) + ArgoCD sync tự động. Không dùng `argocd app rollback` trên production vì không audit trail qua Git.
    - **Liên quan:** Day 20-33

12. **RPO và RTO khác nhau thế nào trong DR context?**
    - **Đáp án:** RPO = Recovery Point Objective (dữ liệu mất tối đa bao nhiêu? VD: 1h → backup mỗi giờ). RTO = Recovery Time Objective (khôi phục trong bao lâu? VD: 4h → cần runbook + automation).
    - **Liên quan:** Day 27-35

## Tài nguyên

- [Week 1: Terraform Foundations](./week-1-terraform-foundations/README.md)
- [Week 2: Terraform Production](./week-2-terraform-production/README.md)
- [Week 3: Ansible & ArgoCD Core](./week-3-ansible-argocd-core/README.md)
- [Week 4: ArgoCD Advanced](./week-4-argocd-advanced/README.md)
- [Week 5: Capstone Production-Grade](./week-5-capstone/README.md)
- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs)
- [Ansible Documentation](https://docs.ansible.com/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [External Secrets Operator](https://external-secrets.io/)
- [Argo Rollouts](https://argoproj.github.io/rollouts/)
