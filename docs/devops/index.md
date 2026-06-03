# DevOps/SRE Production-Grade — 50 ngày từ senior dev đến platform engineer

Lộ trình dành cho Senior Software Engineer muốn nâng cấp lên DevOps/SRE/Platform Engineering. 50 ngày, mỗi ngày 2 giờ (40% lý thuyết — 60% thực hành), local-first với Docker, kind, kubectl, Helm, Terraform.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể triển khai và vận hành hệ thống production:

1. [Day 01: DevOps, SRE, Platform Engineering & DORA Metrics](./day-01-devops-sre-platform-engineering/lesson) — operating model, DORA metrics, error budget
2. [Day 02: Linux Advanced — Process, Signal, systemd](./day-02-linux-advanced-process-signal-systemd/lesson) — process model, graceful shutdown, file descriptors
3. [Day 08: Docker Internals — namespace, cgroup, OCI](./day-08-docker-internals-namespace-cgroup-oci/lesson) — container isolation, multi-stage build, image optimization
4. [Day 10: Kubernetes Architecture Deep Dive](./day-10-kubernetes-architecture-deep-dive/lesson) — control plane, reconciliation loop, kind cluster
5. [Day 11: Kubernetes Workload Resources](./day-11-kubernetes-workload-resources/lesson) — Deployment, StatefulSet, DaemonSet, Job
6. [Day 12: Kubernetes Networking Core](./day-12-kubernetes-networking-core/lesson) — Service types, kube-proxy, CoreDNS
7. [Day 18: Resource Requests/Limits, QoS](./day-18-resource-requests-limits-qos-rightsizing/lesson) — CPU throttling, OOMKilled, right-sizing
8. [Day 27: Terraform Fundamentals](./day-27-terraform-fundamentals/lesson) — HCL, init/plan/apply, state management
9. [Day 31: GitOps với ArgoCD & Flux](./day-31-gitops-argocd-flux/lesson) — Git as source of truth, pull-based deployment
10. [Day 38: Observability — Metrics, Logs, Traces](./day-38-observability-metrics-logs-traces/lesson) — three pillars, Golden Signals, structured logging

Sau 10 bài này bạn đã có thể deploy microservices lên Kubernetes, quản lý infrastructure bằng Terraform, GitOps, và biết cách quan sát/debug hệ thống production.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---:|---|
| Phase 1 — Foundation | Day 01-07 | DevOps mindset, Linux, Networking, Automation, Git | Linux production runbook + automation scripts |
| Phase 2 — Docker & Kubernetes Core | Day 08-17 | Container internals, K8s architecture, workloads, networking, storage, Helm/Kustomize | Microservice stack trên local K8s |
| Phase 3 — Kubernetes Production | Day 18-25 | Resources, autoscaling, RBAC, security, troubleshooting, upgrade, backup | Production-hardened K8s cluster |
| Phase 4 — IaC & GitOps | Day 26-31 | Terraform, Pulumi, Ansible, ArgoCD, Flux | Infrastructure as Code + GitOps workflow |
| Phase 5 — CI/CD & Release | Day 32-37 | Pipeline design, GitHub Actions, deployment strategies, progressive delivery, supply chain | CI/CD pipeline + artifact security |
| Phase 6 — Observability | Day 38-44 | Metrics, Prometheus, Grafana, logging, tracing, SLO, incident response | Full observability stack + runbooks |
| Phase 7 — Production & Capstone | Day 45-50 | DevSecOps, service mesh, DB on K8s, DR, cost optimization, capstone | Production platform design |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 1 | DevOps/SRE/Platform Engineering | Nền tảng tư duy operating model; không hiểu thì không biết team mình cần gì |
| Day 2 | Linux Advanced — Process, Signal | Container = Linux process + namespace; không hiểu process/signal thì không debug được pod termination |
| Day 3 | Linux Networking Fundamentals | Mọi distributed system communication đi qua network; connection timeout ≠ read timeout |
| Day 8 | Docker Internals | Container isolation, multi-stage build giảm image từ 1.1GB → 5-15MB; secret trong image layer không xóa được |
| Day 10 | Kubernetes Architecture | K8s = declarative system với reconciliation loops; API server là gateway duy nhất |
| Day 11 | K8s Workload Resources | Deployment cho stateless, StatefulSet cho stateful — dùng sai workload gây production incident |
| Day 12 | K8s Networking Core | Service = stable virtual IP + DNS; ndots:5 gây DNS storm |
| Day 18 | Resource Requests/Limits, QoS | CPU throttling là nguyên nhân #1 "service chậm không rõ lý do" |
| Day 27 | Terraform Fundamentals | IaC standard; init/plan/apply workflow, state file management |
| Day 31 | GitOps with ArgoCD/Flux | Git as single source of truth + pull-based deployment |
| Day 38 | Observability — Three Pillars | Metrics cho "what", traces cho "where", logs cho "why"; không có observability → MTTR tăng 5-10x |
| Day 39 | Prometheus & PromQL | Pull-based monitoring, PromQL queries, cardinality management |
| Day 43 | SLI/SLO/Error Budget | Burn rate alert giảm noise 80%, tăng signal; error budget cho phép fail có kiểm soát |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 4 | Linux Performance & Debug | USE method, flame graphs — kỹ năng debug production essential |
| Day 5 | Bash & Python Automation | Automation = DNA của DevOps; strict mode, idempotent scripts |
| Day 6 | Git Workflows & Release | Trunk-based development tương quan DORA metrics cao |
| Day 9 | Container Image Optimization | 75% images có HIGH/CRITICAL CVE; Alpine nhỏ nhưng musl DNS issues |
| Day 13 | Ingress & Gateway API | 1 Ingress = 1 entry point cho nhiều services (cost-effective) |
| Day 14 | ConfigMap, Secret Management | Secret chỉ là base64, KHÔNG phải encryption; cần External Secrets cho production |
| Day 19 | Autoscaling (HPA, VPA, KEDA) | Autoscaling giảm 75-85% cost so với over-provisioning |
| Day 20 | RBAC, Pod Security, NetworkPolicy | K8s mặc định MỞ — cần least privilege + NetworkPolicy default deny |
| Day 22 | K8s Troubleshooting | Debug distributed system methodology; mitigation trước, root cause sau |
| Day 26 | IaC Principles | Declarative vs imperative, desired state, drift detection |
| Day 28 | Terraform Advanced — Remote State, Modules | Local state → remote state khi có team; module = reusable package |
| Day 32 | CI/CD Design Patterns | Pipeline stages, quality gates, DORA metrics in practice |
| Day 33 | GitHub Actions Deep Dive | CI/CD tích hợp native GitHub; OIDC thay long-lived secrets |
| Day 35 | Deployment Strategies | Rolling, Blue-Green, Canary — database migration là thách thức lớn nhất |
| Day 40 | Grafana Dashboard & Alerting | SLO-based alerting giảm alert fatigue; mỗi alert PHẢI có runbook link |
| Day 41 | Logging Architecture (Loki vs ELK) | Loki chi phí thấp 10-20x so với ELK; structured logging + correlation ID |
| Day 44 | Incident Response & Postmortem | Blameless postmortem, 5 Whys, action items SMART |
| Day 49 | Cost Optimization & FinOps | 70% cloud spend bị lãng phí; right-sizing + Savings Plans = 30-50% savings |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---|
| Day 7 | Mini-project Linux + Networking | Làm để tổng hợp Phase 1, nhưng không blocking |
| Day 15 | Storage — PV, PVC, CSI | Khi cần stateful workload trên K8s |
| Day 16 | Helm vs Kustomize | Khi cần package/deploy nhiều services; startup dùng Kustomize, enterprise dùng Helm |
| Day 17 | Mini-project Microservice Stack | Capstone Phase 2 — làm sau khi hiểu K8s core |
| Day 21 | Admission Controller, OPA/Kyverno | Khi cần policy enforcement ở cấp cluster |
| Day 23 | K8s Upgrade, Backup & Maintenance | Khi vận hành production cluster thật |
| Day 24 | Production-ready K8s Checklist | Dùng để audit cluster trước go-live |
| Day 25 | Mini-project Harden K8s App | Capstone Phase 3 — hardening từ chạy được → production-ready |
| Day 29 | Pulumi vs Terraform vs CDK | Khi cần chọn IaC tool cho team — migration cost rất cao |
| Day 30 | Ansible Configuration Management | Khi cần node bootstrapping, bare-metal, security hardening |
| Day 34 | GitLab CI, Jenkins, CircleCI | Khi cần chọn CI/CD tool theo team context |
| Day 36 | Progressive Delivery (Argo Rollouts) | Khi canary thủ công không đủ; automated analysis + rollback |
| Day 37 | Artifact Registry & Supply Chain | `latest` tag = anti-pattern; Cosign sign + Kyverno verify |
| Day 42 | OpenTelemetry & Distributed Tracing | Khi cần trace request xuyên 5-10 services |
| Day 45 | DevSecOps (SAST/DAST/SCA) | Shift-left security; fix cost tăng 10x qua mỗi phase |
| Day 46 | Service Mesh & Zero-trust | Khi có > 10 services; Linkerd simple, Istio feature-rich |
| Day 47 | Database on K8s vs Managed | Startup dùng managed DB, enterprise self-host save 40-60% |
| Day 48 | Multi-region DR & RPO/RTO | HA ≠ DR; warm standby best ROI cho mid-size |
| Day 50 | Capstone Production Platform | Tổng hợp toàn bộ 49 ngày — làm cuối cùng |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---|
| Các file `document.md` | Cheat sheet, templates, reference | Tra cứu khi cần |
| Lab nâng cao trong `exercises.md` | Bài tập mở rộng | Làm sau khi hoàn thành core path |

## Cách học đề xuất

1. **Phase 1** (Day 01-07): Foundation — Linux, Networking, DevOps mindset. Học trước để có nền tảng vận hành.
2. **Phase 2** (Day 08-17): Docker & Kubernetes Core. Đây là 20% kiến thức tạo 80% giá trị — deploy microservices lên K8s.
3. **Phase 3** (Day 18-25): Kubernetes Production — chuyển từ "deploy được" → "deploy an toàn, debug được, bảo mật được".
4. **Phase 4** (Day 26-31): IaC & GitOps — quản lý infrastructure bằng code, GitOps workflow.
5. **Phase 5** (Day 32-37): CI/CD & Release Engineering — pipeline an toàn, progressive delivery.
6. **Phase 6** (Day 38-44): Observability & Reliability — đo, debug, alert bằng dữ liệu.
7. **Phase 7** (Day 45-50): Security, Cost, DR & Capstone.

Mỗi ngày học 2 giờ theo format:
- 20 phút: đọc concept
- 25 phút: deep dive / trade-offs
- 50 phút: hands-on thực hành
- 15 phút: debugging / checklist
- 10 phút: ghi chú

## Mini project — Production Platform Design (Capstone)

**Mô tả:** Thiết kế và xây dựng NextShop e-commerce platform hoàn chỉnh — từ architecture, K8s manifests, Terraform, CI/CD, observability, security, DR đến cost optimization.

**Stack:**
- Kubernetes (kind/EKS) + Istio/Linkerd service mesh
- PostgreSQL (CloudNativePG) + Redis + Kafka
- Terraform + ArgoCD + GitHub Actions
- Prometheus + Grafana + Loki + Tempo + OpenTelemetry

**Kiến thức áp dụng:**
- C4 architecture diagrams, ADR documentation
- Production-grade K8s YAML (resources, probes, PDB, HPA, NetworkPolicy, RBAC)
- Terraform modules (VPC, EKS, RDS, ElastiCache, MSK)
- GitHub Actions pipeline (test → scan → sign → deploy → verify)
- Canary deployment với Argo Rollouts + Prometheus analysis
- SLO-based alerting, incident runbooks, DR plan

**Tiêu chí hoàn thành:**
- C4 architecture diagrams (Context + Container + Component)
- K8s manifests cho 6-7 services production-grade
- Terraform modules + CI/CD pipeline + observability stack
- 5 incident runbooks + DR plan + cost breakdown

## Checklist học nhanh

- [ ] Tôi đã hiểu DevOps ≠ tool, SRE ≠ sysadmin, Platform Engineering ≠ internal tools
- [ ] Tôi đã học xong toàn bộ nhóm A (Foundation + Docker/K8s Core + IaC + Observability)
- [ ] Tôi đã deploy được microservice stack lên local Kubernetes
- [ ] Tôi đã cấu hình resource requests/limits, probes, và biết debug pod issues
- [ ] Tôi đã dùng Terraform để quản lý infrastructure + ArgoCD cho GitOps
- [ ] Tôi đã setup Prometheus/Grafana/Loki để quan sát hệ thống
- [ ] Tôi đã viết incident postmortem với 5 Whys và action items
- [ ] Tôi biết phần nào thuộc nhóm C/D để quay lại sau

## Flashcard / câu hỏi ôn tập gợi ý

1. DevOps khác SRE thế nào?
   - **Đáp án:** DevOps là culture/principles, SRE là implementation cụ thể với SLI/SLO/error budget.
   - **Liên quan:** Day 01

2. Container khác VM ở điểm cốt lõi nào?
   - **Đáp án:** Container = process + namespace (isolation) + cgroup (resource limit), chia sẻ kernel host. VM có kernel riêng, hardware-level isolation.
   - **Liên quan:** Day 08

3. Kubernetes reconciliation loop là gì?
   - **Đáp án:** Controller liên tục observe → diff desired vs actual state → act để đưa actual = desired.
   - **Liên quan:** Day 10

4. Khi nào dùng Deployment vs StatefulSet?
   - **Đáp án:** Deployment cho stateless workloads, StatefulSet cho stateful (stable network identity + per-replica storage).
   - **Liên quan:** Day 11

5. CPU request/limit khác nhau thế nào?
   - **Đáp án:** Request = guaranteed amount (scheduler dùng), Limit = maximum allowed. CPU compressible (throttle), memory incompressible (OOMKilled).
   - **Liên quan:** Day 18

6. Terraform plan vs apply khác nhau thế nào?
   - **Đáp án:** plan = preview changes (dry run), apply = execute changes. Plan không modify infrastructure.
   - **Liên quan:** Day 27

7. GitOps khác CI/CD truyền thống thế nào?
   - **Đáp án:** GitOps = Git as single source of truth + pull-based deployment (operator trong cluster kéo từ Git). CI/CD truyền thống push-based.
   - **Liên quan:** Day 31

8. Prometheus rate() vs irate() khác nhau thế nào?
   - **Đáp án:** rate() = average over window (smooth, cho dashboards), irate() = instant rate (responsive, cho alerts).
   - **Liên quan:** Day 39

9. SLA vs SLO vs SLI là gì?
   - **Đáp án:** SLA = business contract (penalties), SLO = internal target, SLI = measurement. Error budget = (1 - SLO) × time.
   - **Liên quan:** Day 43

10. Blameless postmortem khác blame culture thế nào?
    - **Đáp án:** Blameless tìm systemic cause (process/culture), không đổ lỗi cá nhân. Action items phải SMART.
    - **Liên quan:** Day 44

## Tài nguyên

- [README tổng quan khóa học](./README.md)
- [Phase 1: Foundation (Day 01-07)](./day-01-devops-sre-platform-engineering/lesson.md)
- [Phase 2: Docker & Kubernetes Core (Day 08-17)](./day-08-docker-internals-namespace-cgroup-oci/lesson.md)
- [Phase 6: Observability (Day 38-44)](./day-38-observability-metrics-logs-traces/lesson.md)
- [Capstone: Production Platform Design (Day 50)](./day-50-capstone-production-platform-design/lesson.md)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
