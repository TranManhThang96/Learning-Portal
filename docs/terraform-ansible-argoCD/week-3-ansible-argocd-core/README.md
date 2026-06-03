# Week 3 - Ansible & ArgoCD Core (Day 13-19)

## Tổng quan

Week 3 chuyển từ Terraform sang hai công cụ còn lại trong bộ ba IaC production: Ansible cho configuration management và ArgoCD cho GitOps deployment. Phase 3 (Day 13-16) hoàn tất Ansible practical với pattern tích hợp Terraform + Ansible. Phase 4 (Day 17-19) bắt đầu ArgoCD & GitOps core, từ kiến trúc tới Application/AppProject/Sync Policy và rendering source bằng Helm/Kustomize. Mỗi ngày 2 tiếng thực hành.

## Lộ trình học

| Ngày | Chủ đề | Thời lượng | Files |
|------|--------|------------|-------|
| Day 13 | Ansible Mental Model & Idempotency | 2h | lesson, document, exercises |
| Day 14 | Variables, Facts, Conditionals, Loops, Handlers | 2h | lesson, document, exercises |
| Day 15 | Roles, Vault, Dynamic Inventory | 2h | lesson, document, exercises |
| Day 16 | Terraform + Ansible Integration | 2h | lesson, document, exercises |
| Day 17 | GitOps Principles & ArgoCD Architecture | 2h | lesson, document, exercises |
| Day 18 | Application, AppProject, Sync Policy | 2h | lesson, document, exercises |
| Day 19 | Helm, Kustomize, Overlays với ArgoCD | 2h | lesson, document, exercises |

## Chi tiết từng ngày

### Day 13 - Ansible Mental Model & Idempotency

**Mục tiêu:** Hiểu Ansible architecture, agentless model, idempotency, và positioning so với Terraform/Bash/cloud-init.

- **Kiến thức:** Ansible là gì và tại sao tồn tại song song với Terraform, agentless architecture (SSH-based), concept mapping từ Terraform/K8s sang Ansible (inventory = provider config, playbook = main.tf, module = resource type, role = Terraform module), idempotency deep dive
- **Lab:** Cài Ansible, tạo `ansible.cfg`, tạo local inventory, viết và chạy `hardening.yml` (7 sections, 20+ tasks demonstrating idempotency)
- **Document:** CLI quick-reference, Ansible → Terraform → K8s concept mapping table (12 concepts), module cheat sheet, inventory formats, idempotency decision tree, `ansible.cfg` annotated reference, architecture diagram
- **Exercises:** 6 bài tập tăng dần (inventory expansion, idempotency debugging, hardening extension, multi-play playbook, register & conditional, production-grade challenge) + self-assessment checklist

### Day 14 - Variables, Facts, Conditionals, Loops, Handlers

**Mục tiêu:** Thành thạo variable precedence, facts, conditionals, loops, handlers, Jinja2 templates, tags, check/diff mode.

- **Kiến thức:** Variable precedence (18 levels), facts gathering, conditionals (`when`), loops (`loop`, `with_items`), handlers và notify mechanism, Jinja2 templates, tags strategy, check mode và diff mode
- **Lab:** Nginx deployment playbook hoàn chỉnh với multi-environment inventory, 2 Jinja2 templates (`nginx.conf.j2`, `index.html.j2`), facts-based config, handlers, tags
- **Document:** Variable precedence table (18 levels), facts quick reference, conditionals syntax patterns, loops reference, handlers rules, Jinja2 complete filter reference, production patterns
- **Exercises:** 4 levels (basic variable/conditional/loop exercises, nginx/node_exporter deployment, PostgreSQL auto-tuning, HAProxy template + LAMP stack challenge)

### Day 15 - Roles, Vault, Dynamic Inventory

**Mục tiêu:** Tạo production-grade Ansible role, encrypt secrets bằng Vault, cấu hình dynamic inventory với AWS EC2.

- **Kiến thức:** Role directory structure (tasks, handlers, templates, files, vars, defaults, meta), Ansible Galaxy, Ansible Vault (file-level vs variable-level encryption), dynamic inventory (AWS EC2 plugin), secret management comparison
- **Lab:** Tạo role `node_exporter` hoàn chỉnh (production-grade, reuse-ready cho Day 16), vault setup với encrypted `group_vars/all/vault.yml`, AWS EC2 dynamic inventory config (có local fallback)
- **Document:** Role structure auto-loading rules, Galaxy CLI cheat sheet, Vault command reference, `aws_ec2.yml` full config, Node Exporter role variable table, production `ansible.cfg` template, reusable patterns, comparison tables
- **Exercises:** 7 bài tập + 4 challenges (nginx role, vault deep dive, Galaxy integration, Docker-simulated dynamic inventory, production role enhancement với TLS/Molecule, secret management comparison, end-to-end mini project)

### Day 16 - Terraform + Ansible Integration

**Mục tiêu:** Tích hợp Terraform với Ansible đúng cách qua decoupled pattern, dynamic inventory từ Terraform output, và phân biệt với cloud-init/Packer/SSM.

- **Kiến thức:** 3 patterns tích hợp (decoupled, provisioner anti-pattern, bake image), dynamic inventory generation từ `terraform output`, comparison giữa Ansible vs cloud-init vs user_data vs Packer vs SSM Run Command/State Manager
- **Lab:** Terraform tạo VPC + bastion EC2 (mode AWS) hoặc Docker container (mode local), generate dynamic inventory bằng `aws_ec2.yml` plugin filter theo tag, role `bastion-hardening` mới + reuse role `node_exporter` từ Day 15, end-to-end `terraform apply` → `ansible-playbook`
- **Document:** Decision tree ASCII flowchart cho tool selection, ADR template Terraform-Ansible integration, tag taxonomy chuẩn, bastion hardening checklist (CIS-style 20 items), 6 snippet (Terraform output → inventory bash/Python, aws_ec2.yml advanced, Packer HCL2, cloud-init, anti-pattern), cost optimization với SSM Session Manager
- **Exercises:** 6 challenges (static→dynamic inventory migration, Packer AMI build, multi-tier 3-tier infrastructure, debug 3 lỗi cài sẵn, race condition incident, hybrid Packer + Ansible + Terraform với full ADR)

### Day 17 - GitOps Principles & ArgoCD Architecture

**Mục tiêu:** Hiểu 4 nguyên tắc GitOps, kiến trúc ArgoCD và cài đặt ArgoCD trên kind để deploy app đầu tiên.

- **Kiến thức:** 4 nguyên tắc OpenGitOps (declarative, versioned, pulled, reconciled), desired vs actual state, reconciliation loop, pull vs push deployment, 5 core components ArgoCD (api-server, repo-server, application-controller, dex, redis) cùng applicationset-controller và notifications-controller, Application CRD preview
- **Lab:** Tạo kind cluster `argocd-day17`, cài ArgoCD v3.4.x pinned, login UI/CLI, deploy guestbook qua Application (CLI + YAML manifest), quan sát reconciliation, simulate drift bằng `kubectl scale`, inspect logs từng component
- **Document:** Component cheatsheet (port, RAM, scale strategy), ArgoCD vs Flux comparison matrix 30+ tiêu chí, reconciliation sequence diagram, 30+ argocd CLI command, Application CRD field reference, sync status × health status meanings, GitOps maturity model 4 levels
- **Exercises:** 6 challenges (multi-format deploy raw YAML/Helm/Kustomize, private repo PAT credential, drift + self-heal timing, debug stuck Progressing 5-step checklist, disaster recovery backup/restore, performance scale 50 synthetic apps + interval tuning)

### Day 18 - Application, AppProject, Sync Policy

**Mục tiêu:** Thiết kế Application + AppProject cho multi-tenant với sync policy và RBAC đúng theo môi trường.

- **Kiến thức:** Application CRD đầy đủ (source/destination/syncPolicy/syncOptions/retry/ignoreDifferences/finalizers), AppProject CRD (sourceRepos, destinations, roles, signatureKeys, syncWindows), 4 sync policy combinations (manual / automated / +selfHeal / +prune), sync status × health status (3×6 matrix), drift correction strategies
- **Lab:** Tạo AppProject `team-platform`, deploy Application `api-service` qua Git repo demo, simulate drift case 1 (modify replica) và case 2 (delete resource + prune), bật automated+selfHeal và quan sát behavior, test `ignoreDifferences` cho HPA replicas, AppProject RBAC test với account `dev-user`
- **Document:** Application CRD field reference (~40 fields), AppProject CRD field reference (~30 fields), sync policy decision matrix theo env và team size, sync options cheatsheet 15+ options, RBAC policy syntax (p, g rules), 3 AppProject template (per-env, per-team, bank/regulated), `ignoreDifferences` cookbook 6 patterns (HPA, managedFields, cert-manager…), annotation reference
- **Exercises:** 6 challenges (3 Application với 3 sync policy khác nhau, multi-team AppProject + RBAC, debug OutOfSync mãi do managedFields/creationTimestamp, prune incident + recovery runbook, zero-downtime project migration 5 apps, production sync windows weekend/lunch deny + validation)

### Day 19 - Helm, Kustomize, Overlays với ArgoCD

**Mục tiêu:** Hiểu cách ArgoCD render Helm/Kustomize server-side, thiết kế base/overlay cho multi-env, và combine Helm + Kustomize đúng cách.

- **Kiến thức:** ArgoCD render workflow (repo-server clone → `helm template` / `kustomize build` → controller apply), Application spec với `helm.*` và `kustomize.*` fields, multi-source Application (chart upstream + values team repo), base/overlay pattern Kustomize idiomatic, 3 patterns combine Helm + Kustomize (helmCharts trong base, multi-source clean, render-then-patch)
- **Lab:** Tạo Git repo `gitops-lab-day19/` dual structure (charts/ Helm + kustomize/ base+overlays), deploy `api-service` qua Helm và Kustomize song song, override resource requests/replicas/image theo env (dev 1 replica - staging 3 replica - prod 5 replica + PDB), bật `kustomize.buildOptions: --enable-helm` để combine pattern A, ApplicationSet sneak peek
- **Document:** Helm fields cheatsheet trong ArgoCD context (valueFiles, parameters, releaseName, version, passCredentials), Kustomize fields cheatsheet (images, namePrefix, replicas, commonLabels, JSON6902 patches), values precedence diagram (parameters > inline values > valueFiles), comparison matrix 20+ tiêu chí, 10 anti-patterns base/overlay, ConfigMap/Secret rotation patterns 4 cách, snippet library production (Deployment + probe + resources, HPA + PDB, helpers, multi-source), repo-server caching tips
- **Exercises:** 6 challenges (refactor 3 thư mục copy-paste sang Kustomize overlay, wrap cert-manager upstream chart qua multi-source, build production Helm chart với `_helpers.tpl` + values schema, debug `namePrefix` gây DNS resolution fail, combine Helm+Kustomize với nginx-ingress + `--enable-helm`, architecture design 8 service × 3 env enterprise)

## Cấu trúc folder

```
week-3-ansible-argocd-core/
├── README.md
├── day-13-ansible-mental-model/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-14-ansible-variables-handlers/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-15-ansible-roles-vault-inventory/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-16-terraform-ansible-integration/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-17-gitops-argocd-architecture/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-18-argocd-application-project-sync/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
└── day-19-helm-kustomize-argocd/
    ├── lesson.md
    ├── document.md
    └── exercises.md
```

## Cách sử dụng

1. Học theo thứ tự Day 13 → Day 19 (nội dung ngày sau build trên ngày trước)
2. Mỗi ngày bắt đầu bằng `lesson.md` - đọc theory 30 phút, deep dive 30 phút, lab 60 phút
3. Tra cứu nhanh trong `document.md` khi cần reference
4. Làm thêm `exercises.md` nếu muốn nâng cao

## Yêu cầu môi trường

- **Ansible** >= 2.14 (cài qua pip trên Linux/Mac/WSL)
- **Python** >= 3.9
- **Docker** (cho lab local Day 13-16, simulate managed nodes hoặc Docker provider Terraform)
- **WSL2** (nếu dùng Windows - Ansible không chạy native trên Windows)
- **AWS CLI** (optional - cho Day 15 dynamic inventory, Day 16 mode B)
- **Terraform** >= 1.6 (Day 16)
- **kind** >= 0.20 hoặc **minikube** (Day 17-19 ArgoCD)
- **kubectl** >= 1.28 (Day 17-19)
- **Helm** >= 3.13 (Day 19)
- **Kustomize** >= 5.x (Day 19)
- **argocd CLI** >= v3.4 (Day 17-19, hoặc một release còn supported)

## Chi phí cloud

- Day 13-15: **Miễn phí** (dùng local inventory, Docker containers)
- Day 15 dynamic inventory: **Miễn phí** nếu dùng local fallback, cần EC2 instances nếu dùng AWS thật
- Day 16: **Miễn phí** ở mode A (Docker), mode B AWS phát sinh ~$0-8/tháng (t3.micro free-tier 1 năm đầu)
- Day 17-19: **Miễn phí** hoàn toàn (chạy ArgoCD trên kind cluster local)

## Tính liên tục

- **Input:** Terraform knowledge từ Week 1-2 (module VPC, remote backend, multi-env, CI/CD OIDC, state strategy) được dùng làm bridge và reuse trong Day 16
- **Output:**
  - Role `node_exporter` từ Day 15 được reuse trong Day 16 (Terraform + Ansible Integration)
  - Role `bastion-hardening` Day 16 và Ansible patterns được áp dụng cho server hardening trong Capstone (Day 28-35)
  - kind cluster + ArgoCD installed Day 17 được kế thừa Day 18-19 (và Day 20+)
  - AppProject `team-platform` Day 18 được dùng làm bệ phóng cho App-of-Apps (Day 21) và ApplicationSet (Day 22)
  - Repo `gitops-lab-day19` với base/overlay + Helm chart pattern là tiền đề cho repo structure Day 20 và Capstone
- Day 13 basics → Day 14 variables/handlers → Day 15 roles/vault → Day 16 integration → Day 17 ArgoCD architecture → Day 18 Application/AppProject/SyncPolicy → Day 19 Helm/Kustomize render

## Tiếp theo

**Week 4 - ArgoCD Advanced** (Day 20-27):
- Day 20: GitOps Repo Structure (mono vs poly, infra/platform/apps repo)
- Day 21: App of Apps Pattern
- Day 22: ApplicationSet Basics
- Day 23: ApplicationSet Advanced (Matrix, Merge, Multi-Cluster)
- Day 24: Sync Waves, Hooks, Dependencies
- Day 25: Secrets Management, RBAC, SSO, Private Repo
- Day 26: Argo Rollouts, Progressive Delivery
- Day 27: ArgoCD Observability, Notifications, Backup & DR
