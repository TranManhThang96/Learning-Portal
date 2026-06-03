# Prompt: Tạo khóa học Terraform + Ansible + ArgoCD (1 tháng)

## Context về học viên

Tôi là một **senior developer** với nền tảng sau:
- Đã thành thạo: TypeScript, PHP, Python, Java, Golang, Solidity, Rust, Move
- Đã có kinh nghiệm: system design, database optimization, microservices (API Gateway, RPC, caching, Redis, Kafka, ELK, monitoring)
- **Đã biết Kubernetes cơ bản** (Pod, Deployment, Service, ConfigMap, Secret, Ingress, Helm, Kustomize, kubectl)
- Chưa có kinh nghiệm: Terraform, Ansible, ArgoCD, GitOps workflow

## Mục tiêu khóa học

Tạo lộ trình học **1 tháng (28 ngày)**, **mỗi ngày 2 tiếng thực hành**, giúp tôi đạt trình độ có thể:
- Thiết kế và vận hành infrastructure bằng Terraform ở mức production
- Sử dụng Ansible cho configuration management khi cần thiết
- Triển khai GitOps workflow hoàn chỉnh với ArgoCD cho hệ microservices
- Hiểu được trade-offs giữa các pattern và chọn được solution tối ưu

## Phân bổ thời gian (đã thống nhất)

| Tuần | Nội dung | Số ngày |
|------|----------|---------|
| 1 | Terraform (cơ bản → nâng cao + production topics) | Day 1-7 |
| 2 | Ansible (Day 8-12) + ArgoCD khởi động (Day 13-14) | Day 8-14 |
| 3 | ArgoCD nâng cao | Day 15-19 |
| 3-4 | Capstone project production-grade | Day 20-28 |

### Chi tiết từng ngày

**Tuần 1 - Terraform:**
- Day 1-2: IaC concepts, GitOps overview, HCL syntax, providers, resources, variables, outputs, locals, remote backend (S3 + DynamoDB). Lab: VPC + subnets + routing
- Day 3-4: Modules, module registry, multi-env structure (workspace vs Terragrunt), tfvars layering. Lab: Module hóa VPC + EKS + RDS, deploy 2 môi trường
- Day 5-6: for_each vs count, dynamic blocks, complex types, lifecycle rules, data sources, moved blocks, terraform import. Lab: Import resource có sẵn, refactor không downtime
- Day 7: State management nâng cao, secret handling, CI/CD (Atlantis, GitHub Actions với OIDC), drift detection, policy as code intro

**Tuần 2 - Ansible + ArgoCD khởi động:**
- Day 8-9: Agentless architecture, inventory (static + dynamic AWS), playbook, tasks, handlers, idempotency, variables precedence, facts, conditionals, loops. Lab: Harden EC2
- Day 10-11: Roles, Ansible Galaxy, Jinja2 templates, Ansible Vault, tags, check mode, diff mode. Lab: Role cài Prometheus node_exporter
- Day 12: Tích hợp Terraform ↔ Ansible (dynamic inventory), so sánh với cloud-init, user_data, Packer. Lab: Pipeline Terraform → Ansible
- Day 13-14: GitOps principles, cài ArgoCD (helm qua Terraform), Application CRD, project, sync strategies (manual, auto-sync, self-heal, prune). Lab: Deploy app + test drift correction

**Tuần 3 - ArgoCD nâng cao:**
- Day 15-16: App of Apps pattern, ApplicationSet (generators: list, cluster, git, matrix), sync waves & hooks. Lab: Deploy 5 microservices vào 3 môi trường
- Day 17: Monorepo vs polyrepo, Kustomize overlays, Helm + values per env, combine Helm + Kustomize. Lab: Refactor repo theo pattern production
- Day 18: Secrets management (Sealed Secrets, External Secrets Operator), RBAC, SSO, private repo credentials. Lab: External Secrets + AWS Secrets Manager
- Day 19: Argo Rollouts (canary, blue-green), notifications, metrics & monitoring ArgoCD, disaster recovery

**Tuần 3-4 - Capstone Project:**
- Day 20-21: Terraform infrastructure layer (VPC, EKS với managed + spot, RDS, ElastiCache, ECR, IAM/IRSA, Route53, ACM)
- Day 22: Bootstrap layer (ArgoCD, External Secrets, Cert Manager, ALB Controller, Prometheus stack qua helm_release/argocd_application)
- Day 23: Ansible layer (bastion hardening, backup scripts) hoặc skip nếu không cần
- Day 24-25: GitOps repo structure (infra-repo, platform-repo, apps-repo với base/overlays), ApplicationSet auto-detect
- Day 26: CI/CD pipeline (GitHub Actions: build → test → push ECR → update tag), PR preview environments
- Day 27: Observability (Grafana dashboards, alert rules, Loki logs), disaster scenario testing
- Day 28: Live demo, documentation, runbook, retrospective

## Yêu cầu output

### Cấu trúc folder

Tạo cấu trúc folder như sau:

```
terraform-ansible-argocd-course/
├── week-1-terraform/
│   ├── day-01-iac-foundations/
│   │   ├── lesson.md              (bắt buộc)
│   │   ├── document.md            (nếu cần tham khảo sâu)
│   │   └── exercises.md           (nếu cần bài tập bổ sung)
│   ├── day-02-terraform-basics/
│   ├── day-03-modules/
│   ├── day-04-multi-env/
│   ├── day-05-advanced-features/
│   ├── day-06-import-refactor/
│   └── day-07-production-topics/
├── week-2-ansible-argocd-start/
│   ├── day-08-ansible-basics/
│   ├── day-09-ansible-playbook/
│   ├── day-10-roles-templates/
│   ├── day-11-ansible-practical/
│   ├── day-12-terraform-ansible/
│   ├── day-13-argocd-gitops/
│   └── day-14-argocd-sync/
├── week-3-argocd-advanced/
│   ├── day-15-app-of-apps/
│   ├── day-16-applicationset/
│   ├── day-17-repo-structure/
│   ├── day-18-secrets-rbac/
│   └── day-19-rollouts-observability/
└── week-3-4-capstone/
    ├── day-20-infra-vpc-eks/
    ├── day-21-infra-data-layer/
    ├── day-22-bootstrap-layer/
    ├── day-23-ansible-bastion/
    ├── day-24-gitops-repo/
    ├── day-25-applicationset-config/
    ├── day-26-cicd-pipeline/
    ├── day-27-observability/
    └── day-28-demo-retrospective/
```

### Yêu cầu nội dung cho mỗi ngày

**lesson.md** (bắt buộc) phải có:

1. **Mục tiêu ngày học** - 3-5 bullet cụ thể, đo lường được
2. **Kiến thức nền tảng** (30 phút)
   - Giải thích khái niệm **từ cơ bản đến chi tiết**, giả định học viên chưa biết gì về tool đó
   - Luôn trả lời câu hỏi "tại sao cần?" trước khi vào "làm thế nào?"
   - Dùng analogy hoặc so sánh với thứ quen thuộc (vì học viên đã biết programming, database, microservices)
   - Minh họa bằng diagram ASCII hoặc mô tả visual khi cần
3. **Deep dive & Trade-offs** (30 phút)
   - Phân tích **trade-offs** của từng approach (ít nhất 2-3 cách tiếp cận)
   - Chỉ rõ **best solution** cho từng use case cụ thể (small team vs enterprise, startup vs bank...)
   - Đề cập **performance implications** khi relevant (ví dụ: Terraform plan time với state lớn, ArgoCD reconciliation performance với nhiều app)
   - Common pitfalls và cách tránh
4. **Hands-on Lab** (60 phút)
   - Step-by-step instructions chi tiết
   - Code snippets đầy đủ, không để học viên phải đoán
   - Expected output ở mỗi bước quan trọng
   - Troubleshooting cho lỗi phổ biến
5. **Kiểm tra hiểu bài** - 3-5 câu hỏi/bài tập ngắn để tự kiểm tra
6. **Tham khảo thêm** - Link đến official docs, blog posts chất lượng (chỉ link quan trọng, tránh spam link)

**document.md** (optional) - Tạo khi:
- Có khái niệm cần giải thích chi tiết hơn mà không phù hợp với flow của lesson
- Cần cheat sheet, reference table
- Có architecture diagram phức tạp cần mô tả kỹ
- Comparison matrix giữa nhiều tools/approaches

**exercises.md** (optional) - Tạo khi:
- Có bài tập mở rộng cho người muốn đào sâu
- Có challenge bổ sung ngoài lab chính
- Cần practice thêm với variation khác nhau

### Style và tone

- **Phong cách giải thích**: Như một senior engineer có kinh nghiệm đang mentor cho senior khác chuyển sang domain mới. Không patronizing, không quá basic ở những phần học viên đã biết (Git, Linux, Docker, K8s), nhưng rất chi tiết ở phần mới (Terraform state, Ansible idempotency, ArgoCD reconciliation loop).
- **Đề cao tư duy kỹ thuật**: Luôn phân tích **trade-offs**, chỉ ra **best solution** cho từng context, đánh giá **performance**. Tránh kiểu "nên dùng X" mà phải giải thích "trong context Y thì X tốt hơn Z vì..."
- **Ví dụ thực tế**: Ưu tiên ví dụ từ microservices architecture (vì học viên quen) thay vì ví dụ toy/hello-world
- **Code quality**: Code mẫu phải đạt chất lượng production, có comment khi cần, follow best practices của tool đó

## Yêu cầu ngôn ngữ

- Toàn bộ nội dung viết bằng **tiếng Việt**
- **CHỈ giữ nguyên các thuật ngữ chuyên ngành bằng tiếng Anh**, ví dụ: state, provider, resource, module, playbook, role, inventory, Application, ApplicationSet, sync wave, reconciliation, drift, idempotency, declarative, imperative, manifest, overlay, backend, workspace...
- Không dịch các lệnh CLI, tên tool, tên file, code keywords
- Câu văn ngắn gọn, kỹ thuật chính xác, tránh văn phong học thuật rườm rà

## Ràng buộc quan trọng

1. **Mỗi ngày đúng 2 tiếng** - phân bổ rõ: bao nhiêu phút lý thuyết, bao nhiêu phút thực hành. Nếu nội dung quá nhiều, chỉ giữ phần cốt lõi nhất, phần còn lại đưa sang document.md/exercises.md cho người muốn đào sâu.
2. **Tính liên tục** - Ngày N phải build trên kiến thức của ngày N-1, N-2... Lab của ngày sau có thể dùng output/infrastructure của ngày trước.
3. **Capstone thực sự production-grade** - Không phải demo toy. Sau 9 ngày capstone phải có một system deploy được microservices thật, có CI/CD, có observability, có disaster recovery.
4. **Tiết kiệm chi phí cloud** - Ưu tiên hướng dẫn dùng AWS Free Tier, LocalStack, kind/minikube khi có thể. Chỉ ra rõ phần nào bắt buộc phải dùng cloud thật và ước tính chi phí.
5. **Không giả định quá nhiều** - Học viên là senior dev nhưng mới với DevOps. Giải thích rõ các concept như VPC, subnet, IAM, DNS... lần đầu xuất hiện (không cần sâu, chỉ cần đủ để làm lab).

## Cách thực hiện

Hãy tạo từng ngày một cách tuần tự. Với mỗi ngày:
1. Xác nhận sẽ tạo những file nào (lesson.md bắt buộc, document.md và exercises.md optional)
2. Tạo đầy đủ nội dung từng file
3. Đảm bảo độ dài hợp lý cho 2 tiếng học: lesson.md khoảng 2000-4000 từ tiếng Việt, document.md và exercises.md tùy nhu cầu

Bắt đầu từ **Day 1** và hỏi tôi trước khi chuyển sang ngày tiếp theo để tôi có thể feedback điều chỉnh.