# Chương trình học DevOps/SRE Production-Grade 50 ngày

## Thông tin chương trình

- **Đối tượng**: Senior Software Engineer muốn nâng cấp lên DevOps/SRE/Platform Engineering.
- **Thời gian**: 2 giờ/ngày × 50 ngày.
- **Tỷ lệ**: 40% lý thuyết — 60% thực hành.
- **Ngôn ngữ**: Tiếng Việt, thuật ngữ chuyên ngành giữ nguyên English.
- **Thực hành**: Local-first (Docker, kind, kubectl, Helm, Terraform).
- **Ngôn ngữ demo**: Golang / Node.js (TypeScript).

---

## Tiến độ

| Phase | Ngày | Trạng thái |
|-------|------|-----------|
| Phase 1: Foundation | Day 1-7 | ✅ Hoàn thành |
| Phase 2: Docker & Kubernetes Core | Day 8-17 | ✅ Hoàn thành |
| Phase 3: Kubernetes Production | Day 18-25 | ✅ Hoàn thành |
| Phase 4: IaC & GitOps | Day 26-31 | ✅ Hoàn thành |
| Phase 5: CI/CD & Release Engineering | Day 32-37 | ✅ Hoàn thành |
| Phase 6: Observability & Reliability | Day 38-44 | ✅ Hoàn thành |
| Phase 7: Security, Cost, DR & Capstone | Day 45-50 | ✅ Hoàn thành |

---

## Phase 1: Foundation — Linux, Networking, DevOps Mindset

Mục tiêu: xây nền tảng vận hành hệ thống, tránh học DevOps chỉ ở tầng tool.

### Day 1: DevOps, SRE, Platform Engineering & DORA Metrics ✅

📂 `day-01-devops-sre-platform-engineering/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-01-devops-sre-platform-engineering/lesson.md) | DevOps vs SRE vs Platform Engineering, DORA metrics, error budget, trade-offs theo team size |
| [exercises.md](day-01-devops-sre-platform-engineering/exercises.md) | Đo DORA metrics từ git, viết ADR chọn operating model, thiết kế DORA dashboard |
| [document.md](day-01-devops-sre-platform-engineering/document.md) | Comparison matrix, DORA benchmark table, maturity assessment template, ADR template |

**Kiến thức chính**: DevOps (culture) → SRE (implementation) → Platform Engineering (product). DORA metrics chứng minh speed và stability không phải trade-off.

---

### Day 2: Linux Advanced — Process, Signal, File Descriptor, systemd ✅

📂 `day-02-linux-advanced-process-signal-systemd/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-02-linux-advanced-process-signal-systemd/lesson.md) | Process model, PID/PPID, signals (SIGTERM/SIGKILL), file descriptors, /proc, systemd lifecycle, graceful shutdown |
| [exercises.md](day-02-linux-advanced-process-signal-systemd/exercises.md) | Quan sát process tree, viết graceful shutdown service (Go/Node.js), systemd production setup + debug |
| [document.md](day-02-linux-advanced-process-signal-systemd/document.md) | Signal reference, /proc filesystem guide, systemd unit file template, debug decision tree |

**Kiến thức chính**: Container = Linux process + namespace + cgroup. Không hiểu process/signal → không debug được Kubernetes pod termination.

---

### Day 3: Linux Networking Fundamentals ✅

📂 `day-03-linux-networking-fundamentals/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-03-linux-networking-fundamentals/lesson.md) | TCP/IP, DNS resolution, HTTP/1.1 vs HTTP/2 vs HTTP/3, load balancing algorithms, NAT, ephemeral ports |
| [exercises.md](day-03-linux-networking-fundamentals/exercises.md) | DNS debugging, TCP connection analysis, network failure simulation |
| [document.md](day-03-linux-networking-fundamentals/document.md) | ss/tcpdump/curl cheat sheet, TCP states diagram, network tuning reference, error messages guide |

**Kiến thức chính**: Mọi distributed system communication đi qua network. gRPC + L4 load balancing = uneven traffic. Connection timeout ≠ read timeout.

---

### Day 4: Linux Performance & Debugging Tools ✅

📂 `day-04-linux-performance-debugging-tools/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-04-linux-performance-debugging-tools/lesson.md) | USE method, RED method, CPU/Memory/Disk/Network bottleneck analysis, top/vmstat/iostat/strace/perf, flame graphs |
| [exercises.md](day-04-linux-performance-debugging-tools/exercises.md) | Baseline collection, bottleneck identification challenge, production debugging simulation |
| [document.md](day-04-linux-performance-debugging-tools/document.md) | USE method checklist, tool output reading guide, decision tree, performance numbers reference |

**Kiến thức chính**: USE cho infrastructure, RED cho services. Đo trước, optimize sau. "Service chậm" → systematic analysis, không restart random.

---

### Day 5: Bash & Python Automation for DevOps ✅

📂 `day-05-bash-python-automation-devops/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-05-bash-python-automation-devops/lesson.md) | Bash strict mode, exit codes, trap, idempotent scripts, Python automation, khi nào Bash vs Python |
| [exercises.md](day-05-bash-python-automation-devops/exercises.md) | Health check script, backup with rotation, API monitoring system (Python) |
| [document.md](day-05-bash-python-automation-devops/document.md) | Bash/Python script templates, string/array patterns, cron reference, ShellCheck guide |

**Kiến thức chính**: Automation = DNA của DevOps. Bash < 100 dòng, Python > 100 dòng. Mọi script production cần: strict mode, logging, cleanup trap, idempotency.

---

### Day 6: Git Workflows & Release Models ✅

📂 `day-06-git-workflows-release-models/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-06-git-workflows-release-models/lesson.md) | GitFlow, GitHub Flow, trunk-based development, monorepo vs polyrepo, versioning (SemVer, SHA, build number), hotfix flow |
| [exercises.md](day-06-git-workflows-release-models/exercises.md) | Git workflow basics, hotfix flow & versioning, workflow design cho tổ chức lớn |
| [document.md](day-06-git-workflows-release-models/document.md) | Workflow comparison matrix, release checklist templates, branch naming convention, decision framework |

**Kiến thức chính**: Trunk-based development tương quan DORA metrics cao. GitFlow cho scheduled release, GitHub Flow cho continuous deploy. Versioning strategy khác nhau theo artifact type.

---

### Day 7: Mini-project — Linux + Networking + Automation ✅

📂 `day-07-mini-project-linux-networking-automation/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-07-mini-project-linux-networking-automation/lesson.md) | Deploy HTTP service + systemd, health check script, failure simulation (crash, port conflict, DNS, slow response), runbook |
| [exercises.md](day-07-mini-project-linux-networking-automation/exercises.md) | Deploy & configure, failure simulation & debug, production runbook & auto-recovery |
| [document.md](day-07-mini-project-linux-networking-automation/document.md) | Linux/networking command cheat sheet, USE method checklist, troubleshooting decision tree, runbook template |

**Kiến thức chính**: Capstone Phase 1 — tổng hợp process management, networking debug, performance tools, bash automation vào một deliverable production-ready.

---

## Phase 2: Docker & Kubernetes Core

Mục tiêu: hiểu container và Kubernetes ở mức đủ chắc để triển khai microservices local và production-like.

### Day 8: Docker Internals — namespace, cgroup, OCI, Image Layers ✅

📂 `day-08-docker-internals-namespace-cgroup-oci/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-08-docker-internals-namespace-cgroup-oci/lesson.md) | Container vs VM, Linux namespace (PID/NET/MNT/UTS/IPC/USER), cgroup (CPU/memory limits), OCI runtime chain, image layers, copy-on-write, multi-stage build, build cache |
| [exercises.md](day-08-docker-internals-namespace-cgroup-oci/exercises.md) | Khám phá namespace & cgroup, tối ưu Dockerfile giảm 80% size, production-ready Dockerfile |
| [document.md](day-08-docker-internals-namespace-cgroup-oci/document.md) | Docker architecture diagram, namespace/cgroup reference, Dockerfile instruction best practices, multi-stage build patterns, .dockerignore template |

**Kiến thức chính**: Container = process + namespace + cgroup. Multi-stage build giảm image từ 1.1GB xuống 5-15MB. Build cache order: dependencies trước, code sau.

---

### Day 9: Container Image Optimization & Security ✅

📂 `day-09-container-image-optimization-security/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-09-container-image-optimization-security/lesson.md) | Root vs non-root, Alpine vs Distroless vs Scratch trade-offs, Trivy/Grype scanning, SBOM, supply chain risks, image signing (Cosign) |
| [exercises.md](day-09-container-image-optimization-security/exercises.md) | Scan image với Trivy, chuyển Dockerfile sang non-root, secure image pipeline hoàn chỉnh |
| [document.md](day-09-container-image-optimization-security/document.md) | Base image comparison matrix, Trivy command reference, CVE severity guide, non-root patterns per language, CI/CD security pipeline template |

**Kiến thức chính**: 75% images có HIGH/CRITICAL CVE. Secret trong image layer KHÔNG xóa được bằng `rm`. Alpine nhỏ nhưng musl DNS issues. Distroless an toàn nhưng không debug được.

---

### Day 10: Kubernetes Architecture Deep Dive ✅

📂 `day-10-kubernetes-architecture-deep-dive/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-10-kubernetes-architecture-deep-dive/lesson.md) | Control plane (API server, etcd, scheduler, controller manager), data plane (kubelet, kube-proxy, CRI), reconciliation loop, request flow YAML → running pod, object lifecycle |
| [exercises.md](day-10-kubernetes-architecture-deep-dive/exercises.md) | Tạo kind cluster & khám phá control plane, trace request flow & reconciliation, component failure simulation |
| [document.md](day-10-kubernetes-architecture-deep-dive/document.md) | K8s architecture diagram, component reference table, kubectl essential commands, kind/k3d quick reference, troubleshooting decision tree |

**Kiến thức chính**: K8s = declarative system với reconciliation loops. API server là gateway duy nhất. etcd là "bộ nhớ" — mất etcd = mất cluster. Controller pattern: observe → diff → act (giống background worker).

---

### Day 11: Kubernetes Workload Resources ✅

📂 `day-11-kubernetes-workload-resources/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-11-kubernetes-workload-resources/lesson.md) | Pod, ReplicaSet, Deployment, StatefulSet, DaemonSet, Job, CronJob, update strategy (RollingUpdate, Recreate), restart policy, decision matrix |
| [exercises.md](day-11-kubernetes-workload-resources/exercises.md) | Deploy & scale Deployment, Job pipeline & CronJob monitoring, production-ready StatefulSet với Redis |
| [document.md](day-11-kubernetes-workload-resources/document.md) | Workload resource cheat sheet, decision framework flowchart, update strategy comparison, production checklist |

**Kiến thức chính**: Deployment cho stateless, StatefulSet cho stateful (stable identity + storage), DaemonSet cho node agents, Job/CronJob cho batch tasks. Không bao giờ tạo Pod đơn lẻ trong production.

---

### Day 12: Kubernetes Networking Core ✅

📂 `day-12-kubernetes-networking-core/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-12-kubernetes-networking-core/lesson.md) | Pod networking model, CNI plugins, Service types (ClusterIP, NodePort, LoadBalancer, Headless), Endpoint/EndpointSlice, kube-proxy modes (iptables, IPVS, eBPF), CoreDNS |
| [exercises.md](day-12-kubernetes-networking-core/exercises.md) | Service discovery cơ bản, Service types & endpoint debugging, multi-service architecture với DNS debugging |
| [document.md](day-12-kubernetes-networking-core/document.md) | Service type comparison, DNS reference, debugging flowchart, kube-proxy mode comparison, externalTrafficPolicy guide |

**Kiến thức chính**: Mỗi pod có IP riêng, không cần NAT. Service = stable virtual IP + DNS. ClusterIP cho internal, NodePort cho dev, LoadBalancer cho cloud. ndots:5 gây DNS storm — dùng FQDN hoặc giảm ndots.

---

### Day 13: Ingress, Gateway API & Load Balancing ✅

📂 `day-13-ingress-gateway-api-load-balancing/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-13-ingress-gateway-api-load-balancing/lesson.md) | Ingress vs Ingress Controller, NGINX/Traefik, Gateway API (future), L4 vs L7 load balancing, path/host-based routing, TLS termination, AWS mapping (ALB, NLB, Route 53) |
| [exercises.md](day-13-ingress-gateway-api-load-balancing/exercises.md) | Path-based routing, host-based routing với TLS, production Ingress architecture design |
| [document.md](day-13-ingress-gateway-api-load-balancing/document.md) | Ingress vs Gateway API comparison, NGINX annotation cheat sheet, TLS checklist, AWS LB mapping, production checklist |

**Kiến thức chính**: 1 Ingress = 1 entry point cho nhiều services (cost-effective vs 1 LB per service). Gateway API là tương lai — role separation giữa infra team và app team. Luôn enable TLS trong production.

---

### Day 14: ConfigMap, Secret & External Secret Management ✅

📂 `day-14-configmap-secret-external-secret-management/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-14-configmap-secret-external-secret-management/lesson.md) | ConfigMap, Secret (base64 ≠ encryption), env var vs volume mount trade-offs, External Secrets, Vault, Sealed Secrets, SOPS, rotation strategy, encryption at rest |
| [exercises.md](day-14-configmap-secret-external-secret-management/exercises.md) | ConfigMap/Secret cơ bản, multi-environment secret strategy, production secret management architecture với RBAC |
| [document.md](day-14-configmap-secret-external-secret-management/document.md) | Secret management tools comparison matrix, inject patterns, production checklist, debugging commands |

**Kiến thức chính**: Secret chỉ là base64, KHÔNG phải encryption. Volume mount an toàn hơn env var (auto-update, file permissions). Production cần: encryption at rest + RBAC + audit + rotation strategy.

---

### Day 15: Storage — PV, PVC, StorageClass, CSI ✅

📂 `day-15-storage-pv-pvc-storageclass-csi/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-15-storage-pv-pvc-storageclass-csi/lesson.md) | Stateless vs stateful, PV/PVC binding, StorageClass dynamic provisioning, CSI drivers, access modes (RWO/ROX/RWX/RWOP), reclaim policy (Retain/Delete), backup/restore, vì sao stateful trên K8s khó |
| [exercises.md](day-15-storage-pv-pvc-storageclass-csi/exercises.md) | PVC & data persistence test, database deployment với backup/restore, production storage architecture design |
| [document.md](day-15-storage-pv-pvc-storageclass-csi/document.md) | Storage decision matrix, PV/PVC/SC quick reference, access modes table, AWS pricing reference, backup strategy checklist |

**Kiến thức chính**: PVC = request storage, PV = actual disk, StorageClass = auto-provision. Production dùng Retain policy (Delete = data mất vĩnh viễn). Hầu hết cases nên dùng managed database thay vì DB on K8s.

---

### Day 16: Helm vs Kustomize ✅

📂 `day-16-helm-vs-kustomize/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-16-helm-vs-kustomize/lesson.md) | Helm chart structure (values, templates, releases), Kustomize overlay (base, patches, transformers), Helm vs Kustomize trade-offs, khi nào kết hợp cả hai, templating vs patching approach |
| [exercises.md](day-16-helm-vs-kustomize/exercises.md) | Tạo Helm chart cơ bản, Kustomize multi-environment overlay, Helm + Kustomize hybrid workflow |
| [document.md](day-16-helm-vs-kustomize/document.md) | Helm/Kustomize command cheat sheet, comparison matrix, decision framework, best practices checklist, common template patterns |

**Kiến thức chính**: Helm = templating (npm cho K8s), Kustomize = patching (inheritance/override). Startup dùng Kustomize, enterprise dùng Helm + Kustomize. Third-party software luôn dùng Helm chart có sẵn.

---

### Day 17: Mini-project — Deploy Microservice Stack on Local Kubernetes ✅

📂 `day-17-mini-project-microservice-stack-local-k8s/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-17-mini-project-microservice-stack-local-k8s/lesson.md) | BookStore microservices (4 services): Frontend, API Gateway, Book Service, Redis. Ingress routing, ConfigMap/Secret, PVC, Kustomize overlay, health checks, step-by-step deployment guide |
| [exercises.md](day-17-mini-project-microservice-stack-local-k8s/exercises.md) | Deploy stack theo hướng dẫn, thêm monitoring + multi-env overlay, simulate failures & debug incidents |
| [document.md](day-17-mini-project-microservice-stack-local-k8s/document.md) | kubectl debug cheat sheet, resource relationship diagram, deployment checklist, common error resolution guide, verification script |

**Kiến thức chính**: Capstone Phase 2 — tổng hợp Docker, K8s workloads, networking, Ingress, ConfigMap/Secret, Storage, Helm/Kustomize vào một microservice stack production-like.

---

## Phase 3: Kubernetes Production

Mục tiêu: chuyển từ "deploy được" sang "deploy an toàn, scale được, debug được, bảo mật được".

### Day 18: Resource Requests/Limits, QoS, Right-sizing ✅

📂 `day-18-resource-requests-limits-qos-rightsizing/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-18-resource-requests-limits-qos-rightsizing/lesson.md) | CPU vs Memory (compressible vs incompressible), requests vs limits, QoS classes (Guaranteed/Burstable/BestEffort), CPU throttling (CFS), OOMKilled, LimitRange, ResourceQuota, right-sizing methodology |
| [exercises.md](day-18-resource-requests-limits-qos-rightsizing/exercises.md) | QoS classes observation, CPU throttling & OOMKilled debug, multi-team ResourceQuota management |
| [document.md](day-18-resource-requests-limits-qos-rightsizing/document.md) | Resource sizing reference per language, QoS decision matrix, right-sizing checklist, debug commands, production config templates |

**Kiến thức chính**: CPU throttling làm chậm (compressible), OOMKilled crash ngay (incompressible). Guaranteed QoS cho critical services, Burstable cho hầu hết workloads. Luôn set requests/limits — silent CPU throttling là nguyên nhân #1 của "service chậm không rõ lý do".

---

### Day 19: Autoscaling — HPA, VPA, Cluster Autoscaler, KEDA ✅

📂 `day-19-autoscaling-hpa-vpa-cluster-autoscaler-keda/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-19-autoscaling-hpa-vpa-cluster-autoscaler-keda/lesson.md) | HPA algorithm & behavior config, VPA modes, Cluster Autoscaler flow, KEDA event-driven scaling & scale-to-zero, load testing, khi nào autoscaling gây hại, warm-up/cold start |
| [exercises.md](day-19-autoscaling-hpa-vpa-cluster-autoscaler-keda/exercises.md) | HPA basic setup & load test, custom scaling policies & PDB, multi-tier autoscaling strategy design |
| [document.md](day-19-autoscaling-hpa-vpa-cluster-autoscaler-keda/document.md) | Autoscaler comparison matrix, HPA config cheat sheet, KEDA trigger reference, scaling decision flowchart, load testing guide, cost analysis |

**Kiến thức chính**: HPA cho stateless APIs (CPU/memory), KEDA cho event-driven workers (queue/cron, scale to zero). Autoscaling giảm 75-85% cost so với over-provisioning. Không autoscale databases. Scale up nhanh, scale down chậm.

---

### Day 20: RBAC, Pod Security Standards, NetworkPolicy ✅

📂 `day-20-rbac-pod-security-standards-networkpolicy/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-20-rbac-pod-security-standards-networkpolicy/lesson.md) | RBAC (ServiceAccount → Role → RoleBinding), Pod Security Standards (Privileged/Baseline/Restricted), NetworkPolicy (default deny, ingress/egress rules, namespace isolation), defense in depth, lateral movement prevention |
| [exercises.md](day-20-rbac-pod-security-standards-networkpolicy/exercises.md) | Least privilege ServiceAccount, Pod Security Standards + NetworkPolicy isolation, multi-tenant security architecture |
| [document.md](day-20-rbac-pod-security-standards-networkpolicy/document.md) | RBAC verbs/resources reference, Role templates, PSS comparison matrix, NetworkPolicy templates, kubectl auth cheat sheet, security audit checklist |

**Kiến thức chính**: K8s mặc định MỞ — mọi pod giao tiếp tự do, default SA có token. Production cần: RBAC least privilege + Pod Security baseline/restricted + NetworkPolicy default deny. Quên DNS egress rule = break mọi thứ.

---

### Day 21: Admission Controller, OPA/Gatekeeper, Kyverno ✅

📂 `day-21-admission-controller-opa-gatekeeper-kyverno/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-21-admission-controller-opa-gatekeeper-kyverno/lesson.md) | Admission controller flow (mutating vs validating), webhook architecture, Policy as Code, OPA/Gatekeeper (Rego + ConstraintTemplate), Kyverno (native YAML), use cases: block privileged, require labels/limits, trusted registries |
| [exercises.md](day-21-admission-controller-opa-gatekeeper-kyverno/exercises.md) | Deploy Kyverno + basic policies, Audit → Enforce workflow với multi-policy, Enterprise comparison Gatekeeper vs Kyverno |
| [document.md](day-21-admission-controller-opa-gatekeeper-kyverno/document.md) | Admission flow diagram, OPA vs Kyverno comparison matrix, Kyverno policy cheat sheet, Gatekeeper quick reference, production checklist, policy templates |

**Kiến thức chính**: Admission controller = middleware cho K8s API. Kyverno cho YAML-native (startup/mid-size), Gatekeeper cho multi-platform policy (enterprise). Luôn bắt đầu Audit mode, exclude kube-system, failurePolicy phù hợp.

---

### Day 22: Kubernetes Troubleshooting Methodology ✅

📂 `day-22-kubernetes-troubleshooting-methodology/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-22-kubernetes-troubleshooting-methodology/lesson.md) | Debug flow (symptom → scope → hypothesis → verification → mitigation → root cause), 7 debug cases (ImagePullBackOff, CrashLoopBackOff, OOMKilled, Pending, Stuck Terminating, DNS, Service routing), tools (describe/logs/exec/debug/ephemeral containers), 3 production case studies |
| [exercises.md](day-22-kubernetes-troubleshooting-methodology/exercises.md) | Debug 3 pod issues, Broken Cluster Challenge (5 bugs), Production incident simulation (6 bugs) + full postmortem |
| [document.md](day-22-kubernetes-troubleshooting-methodology/document.md) | Debug decision tree, kubectl troubleshooting cheat sheet, error messages reference, exit codes, incident note template, debugging checklist |

**Kiến thức chính**: Mitigation trước, root cause sau. Debug K8s = debug distributed system. 3 case studies: DNS storm (ndots:5), silent CPU throttling, stuck Terminating resource leak. Luôn viết incident note.

---

### Day 23: Kubernetes Upgrade, Backup & Node Maintenance ✅

📂 `day-23-kubernetes-upgrade-backup-node-maintenance/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-23-kubernetes-upgrade-backup-node-maintenance/lesson.md) | Version skew policy, upgrade order (etcd → API server → controllers → nodes), cordon/drain mechanics, PodDisruptionBudget, etcd backup/restore, Velero architecture, in-place vs blue-green upgrade |
| [exercises.md](day-23-kubernetes-upgrade-backup-node-maintenance/exercises.md) | Cordon/drain + PDB test, full upgrade simulation + etcd backup, DR exercise (backup → delete namespace → restore) |
| [document.md](day-23-kubernetes-upgrade-backup-node-maintenance/document.md) | Upgrade checklist (pre/during/post), version skew matrix, drain/cordon reference, PDB templates, Velero cheat sheet, backup runbook template |

**Kiến thức chính**: K8s upgrade giống database migration — tuần tự, không skip. PDB = rate limiter cho eviction. etcd backup = database backup — mất etcd = mất cluster. Backup mà không test restore = không có backup.

---

### Day 24: Production-ready Kubernetes Checklist ✅

📂 `day-24-production-ready-kubernetes-checklist/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-24-production-ready-kubernetes-checklist/lesson.md) | 8 checklist categories (cluster, workload, security, observability, backup, cost, release, runbook), maturity model (Level 0-5), defense in depth, audit Day 17 BookStore, gap analysis, incremental adoption strategy |
| [exercises.md](day-24-production-ready-kubernetes-checklist/exercises.md) | Audit single service, full stack audit + remediation plan, enterprise multi-tenant checklist design |
| [document.md](day-24-production-ready-kubernetes-checklist/document.md) | Complete production checklist (72 items, printable), maturity scoring template, gap analysis template, priority matrix, automated audit script, probe templates |

**Kiến thức chính**: Production-ready = reliability + security + observability + DR + cost. Startup focus Critical items trước, enterprise cần full checklist. 5 items hay thiếu nhất: readiness probe, PDB, NetworkPolicy, resource limits, non-root.

---

### Day 25: Mini-project — Harden, Scale & Debug Kubernetes App ✅

📂 `day-25-kubernetes-production-hardening-mini-project/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-25-kubernetes-production-hardening-mini-project/lesson.md) | Capstone Phase 3: harden BookStore từ "chạy được" → "production-ready". 7 tasks: resources, HPA, RBAC, NetworkPolicy, Kyverno, incident simulation, runbooks. Complete YAML, verification commands, before/after comparison |
| [exercises.md](day-25-kubernetes-production-hardening-mini-project/exercises.md) | Resource + HPA single service, full security hardening (RBAC + NetworkPolicy + Kyverno), production incident simulation (5 planted bugs) + postmortem |
| [document.md](day-25-kubernetes-production-hardening-mini-project/document.md) | Complete hardened BookStore YAML manifests, security checklist (filled), scaling test report template, 5 incident runbooks (OOMKilled, routing, ImagePull, Pending, CPU throttling), before/after comparison |

**Kiến thức chính**: Capstone Phase 3 — tổng hợp resources/QoS (Day 18), autoscaling (Day 19), RBAC/NetworkPolicy (Day 20), admission control (Day 21), troubleshooting (Day 22), upgrade/backup (Day 23), production checklist (Day 24). Score từ ~0% lên ~60%.

---

## Phase 4: Infrastructure as Code & GitOps

Mục tiêu: quản lý hạ tầng bằng code, kiểm soát drift, review thay đổi, triển khai qua GitOps.

### Day 26: Infrastructure as Code Principles ✅

📂 `day-26-infrastructure-as-code-principles/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-26-infrastructure-as-code-principles/lesson.md) | Declarative vs imperative, desired state, state management, drift, plan/apply lifecycle, idempotency, Git as source of truth, IaC review process |
| [exercises.md](day-26-infrastructure-as-code-principles/exercises.md) | IaC concepts & terminology, thiết kế IaC workflow cho team 20 engineers, production IaC migration plan từ ClickOps |
| [document.md](day-26-infrastructure-as-code-principles/document.md) | IaC tool landscape comparison, declarative vs imperative matrix, state management cheat sheet, PR review checklist, drift detection patterns, maturity model |

**Kiến thức chính**: IaC = reproducibility + version control + automation. Declarative (Terraform) vs Imperative (scripts). State file = "bộ nhớ" của IaC tool. Drift = ai đó sửa infra bằng tay → plan sẽ revert. Auto-approve là shortcut nguy hiểm nhất.

---

### Day 27: Terraform Fundamentals ✅

📂 `day-27-terraform-fundamentals/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-27-terraform-fundamentals/lesson.md) | Provider, resource, data source, variable, output, locals, module basics, HCL syntax, init/plan/apply/destroy workflow, dependency graph, state file internals |
| [exercises.md](day-27-terraform-fundamentals/exercises.md) | Terraform basics với local provider, Docker infrastructure (NGINX + Redis), multi-environment Docker stack với workspaces |
| [document.md](day-27-terraform-fundamentals/document.md) | Terraform CLI cheat sheet, HCL syntax reference, built-in functions, resource meta-arguments (count vs for_each), provider reference, .gitignore template, error messages guide |

**Kiến thức chính**: Terraform = declarative IaC với HCL. Provider = SDK, resource = object, state = database. init downloads providers, plan previews, apply executes. Docker provider cho cloud-free hands-on. for_each > count khi resources có identity.

---

### Day 28: Terraform Advanced — Remote State, Locking, Modules, Drift ✅

📂 `day-28-terraform-advanced-remote-state-modules-drift/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-28-terraform-advanced-remote-state-modules-drift/lesson.md) | Remote state (S3/GCS/TF Cloud), state locking (DynamoDB), module architecture & design, environment strategy (workspace vs directory), drift detection & handling, terraform import, state operations (mv/rm/import) |
| [exercises.md](day-28-terraform-advanced-remote-state-modules-drift/exercises.md) | Module basics (webserver/cache), drift detection & resolution (3 loại drift), multi-environment module architecture |
| [document.md](day-28-terraform-advanced-remote-state-modules-drift/document.md) | Module design patterns, state management cheat sheet, environment strategy comparison, anti-patterns reference, drift detection automation (GitHub Actions), import workflow |

**Kiến thức chính**: Local state → remote state khi có team. State locking ngăn concurrent modifications. Module = reusable package (function). Directory-based environments > workspaces cho production. Drift handling: detect → investigate → fix code hoặc revert. `state mv` cho refactor không downtime.

---

### Day 29: Pulumi vs Terraform vs CDK ✅

📂 `day-29-pulumi-vs-terraform-vs-cdk/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-29-pulumi-vs-terraform-vs-cdk/lesson.md) | Terraform (HCL, 3000+ providers, BSL), Pulumi (TS/Py/Go, encrypted secrets, Apache 2.0), CDK (AWS-only, L3 constructs, CloudFormation), DSL vs GPL trade-offs, same infrastructure 3 ways, decision framework theo company size |
| [exercises.md](day-29-pulumi-vs-terraform-vs-cdk/exercises.md) | IaC tool terminology mapping, decision matrix cho 3 teams trong organization, PoC comparison Terraform vs Pulumi |
| [document.md](day-29-pulumi-vs-terraform-vs-cdk/document.md) | Comprehensive feature comparison (20+ criteria), decision framework flowchart, code comparison (S3 bucket 4 ways), migration guide, vendor lock-in assessment, cost comparison, quick start commands |

**Kiến thức chính**: DSL (HCL) = safe, limited, easy to review. GPL (TS/Py) = powerful, flexible, risk of complexity. Terraform cho multi-cloud + largest hiring pool. Pulumi cho dev-heavy teams. CDK cho AWS-only deep integration. Chọn tool dựa trên team skill + requirements, không phải hype. Migration cost rất cao.

---

### Day 30: Ansible for Configuration Management ✅

📂 `day-30-ansible-configuration-management/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-30-ansible-configuration-management/lesson.md) | Configuration management vs provisioning, agentless architecture (SSH), inventory, playbook, role, task, handler, idempotency, Jinja2 templates, variable precedence, Ansible trong thế giới K8s/cloud-native |
| [exercises.md](day-30-ansible-configuration-management/exercises.md) | Playbook basics trên localhost, multi-role playbook với variables/templates/handlers, production Ansible project design |
| [document.md](day-30-ansible-configuration-management/document.md) | Ansible command cheat sheet, module quick reference (apt/file/copy/template/service/user), inventory patterns, role directory structure, Jinja2 template reference, variable precedence, CM tools comparison, ansible.cfg reference, troubleshooting decision tree |

**Kiến thức chính**: Provisioning (Terraform) tạo server, Configuration Management (Ansible) cấu hình server. Ansible = agentless (SSH), push model, YAML playbooks. Dùng modules thay vì shell/command để đảm bảo idempotency. Ansible vẫn relevant cho: node bootstrapping, bare-metal, network devices, legacy VMs, security hardening.

---

### Day 31: GitOps with ArgoCD & Flux ✅

📂 `day-31-gitops-argocd-flux/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-31-gitops-argocd-flux/lesson.md) | GitOps 4 principles, push vs pull deployment, ArgoCD architecture (API Server, Repo Server, Controller, Redis), Flux architecture (source/kustomize/helm/notification controllers), sync policy, drift reconciliation, secret handling (Sealed Secrets, External Secrets, SOPS), rollback strategies |
| [exercises.md](day-31-gitops-argocd-flux/exercises.md) | ArgoCD basics (deploy & observe), self-healing & drift detection (4 drift tests), production GitOps workflow design (repo structure, RBAC, promotion, monitoring) |
| [document.md](day-31-gitops-argocd-flux/document.md) | ArgoCD vs Flux comparison matrix, ArgoCD CLI cheat sheet, Flux CLI cheat sheet, GitOps production checklist, Application YAML templates, ApplicationSet, debugging decision tree, Phase 4 summary |

**Kiến thức chính**: GitOps = Git as single source of truth + pull-based deployment. ArgoCD cho UI + multi-cluster, Flux cho lightweight + Kubernetes-native. Self-heal chống drift. Secrets KHÔNG commit plaintext — dùng Sealed Secrets / External Secrets. Rollback = git revert (không ArgoCD rollback). Phase 4 checkpoint: Terraform quản lý infrastructure, GitOps quản lý workloads, Ansible quản lý configuration.

---

## Phase 5: CI/CD & Release Engineering

Mục tiêu: thiết kế pipeline an toàn, nhanh, có rollback và phù hợp team scale.

### Day 32: CI/CD Design Patterns ✅

📂 `day-32-cicd-design-patterns/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-32-cicd-design-patterns/lesson.md) | CI vs CD (Delivery vs Deployment), pipeline stages (lint/test/build/scan/package/deploy/verify), Pipeline as Code, quality gates, DORA metrics in practice, pipeline architecture patterns (linear, fan-out, matrix, multi-env), pipeline speed optimization, cost analysis |
| [exercises.md](day-32-cicd-design-patterns/exercises.md) | Pipeline stage walkthrough (Makefile), quality gate design cho e-commerce (scoring matrix, DORA dashboard), monorepo pipeline architecture (affected services detection, GitHub Actions matrix) |
| [document.md](day-32-cicd-design-patterns/document.md) | Pipeline stage reference, quality gate checklist templates (CI + CD), DORA metrics measurement guide, pipeline anti-patterns (15 patterns), pipeline templates (Go/Node/Python), CI/CD tool comparison, performance optimization checklist |

**Kiến thức chính**: CI = integration feedback loop (build + test), CD = deployment automation. Continuous Delivery (manual gate) vs Continuous Deployment (auto). Pipeline dưới 10 phút = developer productivity. Quality gates phải automatable, fast, actionable. DORA metrics chứng minh CI/CD tốt = cả speed lẫn stability.

---

### Day 33: GitHub Actions Deep Dive ✅

📂 `day-33-github-actions-deep-dive/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-33-github-actions-deep-dive/lesson.md) | GitHub Actions architecture (workflow/job/step/runner), event types, runner types, job dependencies & parallelism, matrix build, caching, reusable workflows, composite actions, environment protection, OIDC authentication, security threats (supply chain, credential theft, code injection) |
| [exercises.md](day-33-github-actions-deep-dive/exercises.md) | Basic CI workflow (lint/test/build), reusable workflow & matrix build (multi-service), security hardening (pinned SHA, OIDC, secret scanning, script injection prevention, Dependabot) |
| [document.md](day-33-github-actions-deep-dive/document.md) | Workflow syntax cheat sheet, context & expressions, common actions reference, caching patterns (Go/Node/Python/Docker), security hardening checklist, debugging reference, cost optimization tips |

**Kiến thức chính**: GitHub Actions = CI/CD tích hợp native GitHub. Pin actions bằng SHA (không tag) để chống supply chain attack. OIDC thay long-lived secrets cho cloud auth. Reusable workflows cho DRY across services. Script injection: dùng `env:` thay vì inline `$&#123;&#123; &#125;&#125;` trong `run:`. Concurrency control tránh parallel deploys.

---

### Day 34: GitLab CI, Jenkins, CircleCI Comparison ✅

📂 `day-34-gitlab-ci-jenkins-circleci-comparison/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-34-gitlab-ci-jenkins-circleci-comparison/lesson.md) | GitLab CI (all-in-one platform, Auto DevOps), Jenkins (open-source, 1800+ plugins, Groovy), CircleCI (Docker-first, Orbs, SSH debug), comprehensive comparison matrix (20+ tiêu chí), decision framework, cost analysis, migration considerations, production case study (Jenkins plugin hell) |
| [exercises.md](day-34-gitlab-ci-jenkins-circleci-comparison/exercises.md) | Pipeline syntax translation (Jenkinsfile → GitHub Actions → GitLab CI), CI/CD tool selection (scoring matrix, cost projection, risk assessment), multi-tool architecture design (hybrid Jenkins + GitHub Actions) |
| [document.md](day-34-gitlab-ci-jenkins-circleci-comparison/document.md) | Comprehensive feature comparison (core + CI/CD + security), same pipeline in 4 formats, cost calculator reference, decision framework flowchart, migration checklist (Jenkins → GHA, Any → GitLab), terminology mapping |

**Kiến thức chính**: Không có "best tool" — chỉ có "best fit". GitHub Actions cho GitHub-native + ecosystem. GitLab CI cho all-in-one + compliance (Ultimate). Jenkins cho max flexibility + no vendor lock-in (nhưng maintenance cao). CircleCI cho Docker-first + DX. Chọn dựa trên: team size, Git platform, budget, compliance, ops capacity.

---

### Day 35: Deployment Strategies — Rolling, Blue-Green, Canary, Feature Flag ✅

📂 `day-35-deployment-strategies-rolling-bluegreen-canary/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-35-deployment-strategies-rolling-bluegreen-canary/lesson.md) | 6 strategies (Recreate, Rolling, Blue-Green, Canary, Feature Flag, Dark Launch), Kubernetes rolling update (maxSurge/maxUnavailable), Blue-Green implementation (Service selector switch), Canary implementation (pod-based + Istio/Argo Rollouts preview), database migration compatibility (expand-contract pattern), health check integration, decision framework |
| [exercises.md](day-35-deployment-strategies-rolling-bluegreen-canary/exercises.md) | Rolling update mastery (maxSurge configs, timing comparison), Blue-Green implementation (Service selector switch, test endpoint), production strategy design (4 services, rollback plan, DB migration, health checks, deployment runbook, feature flag design) |
| [document.md](day-35-deployment-strategies-rolling-bluegreen-canary/document.md) | Strategy comparison matrix, kubectl rollout cheat sheet, Blue-Green patterns (Service/Ingress/DNS), Canary patterns (K8s/Argo Rollouts/Istio), database migration compatibility reference, health check templates (HTTP/gRPC/worker), deployment runbook template, feature flag best practices |

**Kiến thức chính**: Rolling Update cho hầu hết services (zero downtime, low cost). Blue-Green cho instant rollback (2x cost). Canary cho gradual validation (critical services). Feature Flag cho per-user control (code complexity). Database migration = thách thức lớn nhất — luôn dùng expand-contract pattern. Health checks phải accurate — bad readinessProbe = bad rollout.

---

### Day 36: Progressive Delivery with Argo Rollouts / Flagger ✅

📂 `day-36-progressive-delivery-argo-rollouts-flagger/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-36-progressive-delivery-argo-rollouts-flagger/lesson.md) | Progressive delivery = canary + automated analysis + automated decision. Argo Rollouts architecture (Rollout CRD, AnalysisTemplate, traffic routing), Flagger overview, metric-based promotion, automated rollback, Prometheus integration, failure modes |
| [exercises.md](day-36-progressive-delivery-argo-rollouts-flagger/exercises.md) | Basic canary rollout (Argo Rollouts setup), automated analysis với Prometheus (AnalysisTemplate), production-grade progressive delivery pipeline (6 steps, manual approval, business metrics, runbook) |

**Kiến thức chính**: Progressive delivery = canary thủ công nâng cấp thành automated. Argo Rollouts thay thế Deployment bằng Rollout CRD. AnalysisTemplate query Prometheus để quyết định promote/rollback. Metrics phải đo business outcome, không chỉ HTTP status. False positive (promote version lỗi) nguy hiểm hơn false negative (rollback version tốt).

---

### Day 37: Artifact Registry, Image Signing & Supply Chain Security ✅

📂 `day-37-artifact-registry-image-signing-supply-chain/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-37-artifact-registry-image-signing-supply-chain/lesson.md) | Artifact management, OCI registry, Harbor vs Nexus vs Artifactory vs cloud-native, image tag strategy (immutable tags, semver + git SHA), Cosign/Sigstore (keyless signing), SBOM (CycloneDX, Syft), SLSA framework (Level 0-4), supply chain attacks (SolarWinds, Codecov, ua-parser-js) |
| [exercises.md](day-37-artifact-registry-image-signing-supply-chain/exercises.md) | Image tag strategy + local registry, vulnerability scanning + SBOM pipeline (Trivy, CI gate), end-to-end supply chain security (Cosign signing, Kyverno admission policy, SLSA assessment) |

**Kiến thức chính**: `latest` tag = anti-pattern — dùng immutable tags (semver + git SHA). Supply chain attack là real (SolarWinds ảnh hưởng 18,000 customers). Cosign sign images, Kyverno verify trước khi deploy. SBOM = package-lock.json cho containers. SLSA framework đánh giá maturity. Sign mà không verify = vô nghĩa. Phase 5 checkpoint: Code → CI → Artifact (scan/sign/SBOM) → CD (progressive delivery).

---

## Phase 6: Observability & Reliability

Mục tiêu: biết đo, debug, alert và cải thiện reliability bằng dữ liệu.

### Day 38: Observability — Metrics, Logs, Traces ✅

📂 `day-38-observability-metrics-logs-traces/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-38-observability-metrics-logs-traces/lesson.md) | Monitoring vs observability, three pillars (metrics/logs/traces), Golden Signals (latency, traffic, errors, saturation), RED/USE methods, structured logging, cardinality, correlation flow (alert → metric → trace → log → root cause), observability architecture, data characteristics, cost management |
| [exercises.md](day-38-observability-metrics-logs-traces/exercises.md) | Golden Signals instrumentation (Go/Node.js), structured logging + trace_id correlation (2 services), full observability stack (Prometheus + Grafana + optional Loki, incident simulation) |

**Kiến thức chính**: Monitoring = "có hoạt động không?" (known unknowns). Observability = "vì sao hoạt động như vậy?" (unknown unknowns). Metrics cho "what", Traces cho "where", Logs cho "why". Cardinality = nguyên nhân #1 Prometheus OOM — KHÔNG dùng user_id/request_id làm metric labels. Structured logging + trace_id = correlate across services. Không có observability → MTTR tăng 5-10x.

---

### Day 39: Prometheus & PromQL ✅

📂 `day-39-prometheus-promql/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-39-prometheus-promql/lesson.md) | Prometheus architecture (pull model, TSDB, service discovery), data model (metric name, labels, timestamp, value), 4 metric types (Counter, Gauge, Histogram, Summary), PromQL (instant/range vectors, rate/irate/increase, histogram_quantile, aggregations), recording rules, alert rules, cardinality explosion, long-term storage (Thanos vs Mimir) |
| [exercises.md](day-39-prometheus-promql/exercises.md) | Setup Prometheus + basic PromQL (6 queries), recording rules + alert rules + histogram percentiles, multi-service monitoring + cardinality management (audit, relabel, scaling plan) |
| [document.md](day-39-prometheus-promql/document.md) | PromQL cheat sheet (functions, production queries cho RPS/error rate/latency/saturation), alert rule templates (service health + infrastructure), recording rules templates, API endpoints, cardinality debugging, common mistakes |

**Kiến thức chính**: Prometheus = pull-based, dimensional data model, PromQL. `rate()` cho dashboards (smooth), `irate()` cho alerts (responsive). Histogram > Summary (aggregatable). Cardinality explosion: thêm 1 high-cardinality label = multiply RAM usage. Recording rules = materialized views cho dashboard performance. Thanos cho multi-cluster global view, Mimir cho high-scale Grafana ecosystem.

---

### Day 40: Grafana Dashboard & Alerting ✅

📂 `day-40-grafana-dashboard-alerting/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-40-grafana-dashboard-alerting/lesson.md) | Dashboard design principles (purpose, hierarchy, glanceable, actionable, consistent), 3 dashboard levels (executive, service, debug), panel types, Grafana alerting architecture, alert states, Grafana vs Prometheus AlertManager, SLO-based alerting (burn rate), alert fatigue causes & solutions, dashboard as code |
| [exercises.md](day-40-grafana-dashboard-alerting/exercises.md) | RED metrics dashboard (6 panels, thresholds, JSON export), alert rules + notification (4 rules, contact points, silence), production-grade observability suite (3 dashboards, SLO burn rate alerts, alert hygiene, dashboard as code) |
| [document.md](day-40-grafana-dashboard-alerting/document.md) | Dashboard design checklist, alert rule templates (error rate, latency, service down, no traffic, SLO burn rate, disk prediction), runbook template, alert severity matrix, dashboard naming convention, Grafana provisioning reference |

**Kiến thức chính**: Dashboard = UI/UX cho infrastructure. 3 levels: Executive (glanceable), Service (RED metrics), Debug (detailed). Alert fatigue = quá nhiều alerts → ignore tất cả → miss real incidents. SLO-based alerting (burn rate) thay vì threshold-based → giảm noise 80%. Mỗi alert PHẢI có runbook link. Dashboard as code = export JSON + provisioning + git version control.

---

### Day 41: Logging Architecture — Loki vs ELK vs Splunk ✅

📂 `day-41-logging-architecture-loki-elk-splunk/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-41-logging-architecture-loki-elk-splunk/lesson.md) | Structured logging, log aggregation pipeline, Loki architecture (Distributor→Ingester→Object Store), ELK architecture (Elasticsearch/Logstash/Kibana), Splunk overview, LogQL queries, cost optimization, retention policy, sensitive data handling (PII redaction) |
| [exercises.md](day-41-logging-architecture-loki-elk-splunk/exercises.md) | Deploy Loki stack + LogQL queries, correlation ID propagation across 3 services, sensitive data redaction pipeline + multi-tier retention + cost optimization |
| [document.md](day-41-logging-architecture-loki-elk-splunk/document.md) | 14-column Loki vs ELK vs Splunk comparison matrix, LogQL/KQL/SPL quick reference, logging best practices checklist (30+ items), cost optimization cheat sheet, structured logging snippets (Go/Node/Python/Java) |

**Kiến thức chính**: Loki = index-free (chỉ index labels, grep content khi query) → chi phí thấp 10-20x so với ELK. ELK = full-text index → query mạnh nhưng tốn RAM/disk. Splunk = enterprise all-in-one nhưng đắt. Structured logging + correlation ID = debug across microservices. KHÔNG BAO GIỜ log passwords, JWT tokens, PII — dùng Promtail pipeline stages hoặc app-level redaction.

---

### Day 42: OpenTelemetry & Distributed Tracing ✅

📂 `day-42-opentelemetry-distributed-tracing/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-42-opentelemetry-distributed-tracing/lesson.md) | Trace, Span, Context Propagation (W3C TraceContext), sampling strategies (head-based, tail-based, probabilistic), OpenTelemetry Collector pipeline (receivers/processors/exporters), Jaeger vs Tempo comparison, trace correlation với logs/metrics qua Exemplars |
| [exercises.md](day-42-opentelemetry-distributed-tracing/exercises.md) | Instrument single Go service, tail-based sampling configuration, full "Three Pillars" integration (traces + logs + metrics correlation, Grafana drill-down) |
| [document.md](day-42-opentelemetry-distributed-tracing/document.md) | Go SDK quick reference, semantic convention attributes, Collector config template, Jaeger vs Tempo matrix, TraceQL reference, sampling decision flowchart, Docker Compose templates (minimal/standard/full), K8s Collector manifest |

**Kiến thức chính**: Distributed tracing = distributed stack trace across services. OpenTelemetry = vendor-neutral standard (thay thế Jaeger client, Zipkin). Context propagation qua W3C `traceparent` header — thiếu propagation = broken traces. Sampling giảm cost nhưng có thể miss rare errors → tail-based sampling giữ 100% errors. Jaeger cho đơn giản + tự host, Tempo cho scale + Grafana ecosystem.

---

### Day 43: SLI/SLO, Error Budget & Alert Fatigue ✅

📂 `day-43-sli-slo-error-budget-alert-fatigue/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-43-sli-slo-error-budget-alert-fatigue/lesson.md) | SLA vs SLO vs SLI, error budget calculation (8 SLO levels), burn rate concept + multi-window alerting (PAGE/TICKET/WARNING/INFO), alert fatigue root causes + solutions, toil definition + reduction strategy, error budget policy (4 tiers) |
| [exercises.md](day-43-sli-slo-error-budget-alert-fatigue/exercises.md) | Error budget calculation từ incident timeline, SLI design cho user-auth-api + burn rate alerts, alert system redesign (312 rules → 18 rules) + toil reduction ROI |
| [document.md](day-43-sli-slo-error-budget-alert-fatigue/document.md) | SLI/SLO templates cho 5 service types, error budget calculation worksheet, burn rate multi-window reference, PromQL snippets cho SLO monitoring, recording rules templates, alert fatigue reduction checklist, Grafana panel definitions, Sloth (SLO-as-code) reference |

**Kiến thức chính**: SLA = business contract (penalties), SLO = internal target, SLI = measurement. Error budget = cho phép fail có kiểm soát thay vì chasing 100%. Burn rate alert thay threshold-based → giảm noise 80%, tăng signal. 99.9% SLO = 43.8 phút downtime/tháng. Case study: team giảm MTTR 73% (87→23 phút) và pages 94% (50→3/tuần) khi chuyển sang SLO-based alerting.

---

### Day 44: Incident Response & Postmortem ✅

📂 `day-44-incident-response-postmortem/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-44-incident-response-postmortem/lesson.md) | Incident lifecycle (detect→triage→mitigate→resolve→postmortem), SEV1-4 definitions, roles (IC/Ops Lead/Comms Lead), mitigation strategies, blameless postmortem, 5 Whys technique, action items (SMART), 3 production case studies (AWS AZ outage, DB migration locking, cascading memory leak) |
| [exercises.md](day-44-incident-response-postmortem/exercises.md) | Severity classification + status page, blameless postmortem từ raw logs + 5 Whys, multi-team cascade incident (IC decision log, cross-team coordination) |
| [document.md](day-44-incident-response-postmortem/document.md) | 7 production-ready templates: severity definitions, incident response checklist, blameless postmortem template, communication templates (Slack/status page/email), 5 Whys worksheet, action items tracker, on-call handoff template |

**Kiến thức chính**: Mitigation trước, root cause sau — mục tiêu đầu tiên là giảm user impact. Blameless postmortem = tìm systemic cause, không đổ lỗi cá nhân. 5 Whys: đào sâu đến root cause thật (thường ở process/culture, không phải code). Action items phải SMART (Specific, Measurable, có Owner + Deadline). Phase 6 checkpoint: Metrics (Day 38-39) → Dashboard/Alert (Day 40) → Logs (Day 41) → Traces (Day 42) → SLO (Day 43) → Incident (Day 44).

---

## Phase 7: Security, Cost, DR & Advanced Production

Mục tiêu: hoàn thiện tư duy production-grade, biết đánh đổi giữa security, reliability, cost và complexity.

### Day 45: DevSecOps — SAST, DAST, SCA, Secret Scanning ✅

📂 `day-45-devsecops-sast-dast-sca-secret-scanning/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-45-devsecops-sast-dast-sca-secret-scanning/lesson.md) | Shift-left security, SAST (Semgrep/SonarQube/CodeQL), DAST (OWASP ZAP/Nuclei), SCA (Trivy/Snyk/Dependabot), Secret Scanning (GitLeaks/TruffleHog), Container Scanning, policy gates trong CI/CD, false positive management, 5 real-world breaches (SolarWinds, Log4Shell) |
| [exercises.md](day-45-devsecops-sast-dast-sca-secret-scanning/exercises.md) | Trivy scan 3 target types, full GitHub Actions security pipeline (4 parallel jobs + false positive suppression), enterprise security strategy (12-service fintech, custom Semgrep rules, Security Scorecard) |
| [document.md](day-45-devsecops-sast-dast-sca-secret-scanning/document.md) | SAST vs DAST vs SCA vs Secret Scan comparison matrix, tool comparison (open-source vs commercial), GitHub Actions security pipeline template, CVE decision framework, false positive triage checklist, OWASP Top 10 reference, maturity model (5 levels), recommended $0/month stack |

**Kiến thức chính**: Shift-left = tìm vulnerabilities sớm, fix rẻ hơn 100x so với production. SAST = scan source code (ESLint cho security), SCA = scan dependencies (package-lock.json), DAST = scan running app, Secret Scanning = tìm credentials leaked. Rule of 10: fix cost tăng 10x qua mỗi phase (dev→build→staging→prod). Open-source stack (Semgrep + Trivy + GitLeaks) = $0/tháng, đủ cho hầu hết teams.

---

### Day 46: Service Mesh & Zero-trust Overview ✅

📂 `day-46-service-mesh-zero-trust-overview/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-46-service-mesh-zero-trust-overview/lesson.md) | Service mesh là gì, sidecar pattern, mTLS, traffic management (retry/timeout/circuit breaker), Istio vs Linkerd vs Cilium, zero-trust networking, khi nào KHÔNG nên dùng mesh, 3 production case studies |
| [exercises.md](day-46-service-mesh-zero-trust-overview/exercises.md) | Cài Linkerd + mTLS observation, traffic management với ServiceProfiles, zero-trust architecture design cho FinTech SOC 2 compliance |
| [document.md](day-46-service-mesh-zero-trust-overview/document.md) | Service mesh comparison matrix (Istio/Linkerd/Cilium), mTLS config reference, traffic management patterns, zero-trust checklist, debugging decision tree, production checklist |

**Kiến thức chính**: Service mesh = infrastructure-level middleware cho service-to-service communication. Linkerd simple + low overhead (1-2ms p99, 10-20MB RAM), Istio feature-rich (3-5ms p99, 50-100MB RAM), Cilium eBPF-based (lowest overhead). Zero-trust = "never trust, always verify". KHÔNG dùng mesh cho < 10 services. Retry × upstream services = amplification → cần circuit breaker.

---

### Day 47: Database on Kubernetes vs Managed Database ✅

📂 `day-47-database-kubernetes-vs-managed/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-47-database-kubernetes-vs-managed/lesson.md) | Vì sao DB trên K8s khó (5 thách thức), Operator pattern, CloudNativePG architecture, Vitess (MySQL sharding), backup/restore, failover flow, managed DB trade-offs, 3 production case studies |
| [exercises.md](day-47-database-kubernetes-vs-managed/exercises.md) | Deploy CloudNativePG + failover test, backup/restore với MinIO + PITR, decision matrix CloudNativePG vs RDS vs Aurora + hybrid architecture |
| [document.md](day-47-database-kubernetes-vs-managed/document.md) | DB on K8s vs Managed DB matrix, Operator pattern reference (CloudNativePG/Percona/Vitess), backup/restore checklist, storage performance benchmarking, failover testing runbook, PostgreSQL monitoring queries, production readiness checklist |

**Kiến thức chính**: Stateful workloads khác fundamentally với stateless - cần storage, identity, ordering, network, data management. Operator = "automated DBA" với reconciliation loop. Startup dùng managed DB, enterprise có thể self-host để save 40-60% cost. CloudNativePG auto failover 10-30s. Backup mà không test restore = không có backup (GitLab case study).

---

### Day 48: Multi-region, Disaster Recovery, RPO/RTO ✅

📂 `day-48-multi-region-disaster-recovery-rpo-rto/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-48-multi-region-disaster-recovery-rpo-rto/lesson.md) | HA vs DR (khác biệt cốt lõi), RPO/RTO calculation, 4 DR patterns (Cold/Warm/Active-Passive/Active-Active), DNS failover, data consistency trade-offs, 3 production case studies (OVH fire, AWS outage, GitLab deletion) |
| [exercises.md](day-48-multi-region-disaster-recovery-rpo-rto/exercises.md) | RPO/RTO analysis per service, DR plan design cho e-commerce (warm standby), multi-region active-active với GDPR compliance + chaos testing |
| [document.md](day-48-multi-region-disaster-recovery-rpo-rto/document.md) | HA vs DR matrix, Active-Active vs Active-Passive reference, RPO/RTO calculation worksheet, DR testing runbook template, DNS failover patterns (Route 53/CloudFlare), restore procedure checklist, multi-region cost analysis, production DR checklist |

**Kiến thức chính**: HA ≠ DR (HA = same region AZ failure, DR = region failure). RPO = data loss tolerance, RTO = recovery time. 99.9% SLA = 43.8 phút/tháng downtime. Warm standby best ROI cho mid-size. Cross-region sync replication = latency penalty cho mỗi write. "Backup mà không test restore = không có backup". Test DR quarterly minimum.

---

### Day 49: Cost Optimization & FinOps ✅

📂 `day-49-cost-optimization-finops/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-49-cost-optimization-finops/lesson.md) | FinOps mindset + lifecycle, cloud cost structure, K8s cost allocation (3 methods), top 10 cost optimization techniques, pricing models (On-Demand/Reserved/Spot/Savings Plans), Kubecost architecture, observability cost explosion case study |
| [exercises.md](day-49-cost-optimization-finops/exercises.md) | Cost audit + 5 quick wins với estimated savings, cost allocation + right-sizing cho 4 teams, enterprise FinOps strategy 6-month plan (30% cost reduction) |
| [document.md](day-49-cost-optimization-finops/document.md) | FinOps maturity model (Crawl/Walk/Run), K8s cost allocation methods, Spot/Reserved/On-Demand decision matrix, cost optimization checklist (30+ items), Kubecost setup, cloud cost calculator templates, cost reporting dashboard design, anomaly detection |

**Kiến thức chính**: FinOps = engineering responsibility, không chỉ finance. 70% cloud spend bị lãng phí. Right-sizing + Savings Plans + Spot = 30-50% savings. Gartner: right-size alone = 20-40% savings. Cardinality explosion = nguyên nhân #1 observability cost blow up. Chưa đo = đừng optimize. Premature cost cutting compromise reliability.

---

### Day 50: Capstone Project — Production Platform Design ✅

📂 `day-50-capstone-production-platform-design/`

| File | Nội dung |
|------|---------|
| [lesson.md](day-50-capstone-production-platform-design/lesson.md) | Complete capstone: NextShop e-commerce platform design. 12 deliverables: C4 architecture, K8s YAML skeleton (order-service production-grade), Terraform modules, GitHub Actions pipeline, observability plan, deployment strategy (canary với Argo Rollouts), security plan (RBAC/NetworkPolicy/Kyverno), DR plan, cost breakdown ($4.8K/month → $2.8K optimized), 5 incident runbooks, scale 10x/budget 50%/team 100 analysis, 50-day program summary |
| [exercises.md](day-50-capstone-production-platform-design/exercises.md) | Single service production deployment (all production concerns), observability + security stack (Prometheus+Grafana+Loki+Tempo+Kyverno+External Secrets), complete capstone với all 12 deliverables |
| [document.md](day-50-capstone-production-platform-design/document.md) | Complete production platform checklist (all 50 days), ADR template, C4 model reference, 50-day knowledge map (Day 1-50 key takeaways), "What's Next" learning paths (Platform/SRE/Security/Cloud/Data Engineering), self-assessment checklist, continuous learning resources, practical tips for senior engineers, certificate of completion |

**Kiến thức chính**: Capstone integrate toàn bộ 49 ngày trước. Production platform = infrastructure + workloads + networking + security + observability + CI/CD + backup + cost management. Trade-offs everywhere: cost vs reliability, simplicity vs features, vendor lock-in vs operational burden. Document "why" behind each decision. 50 days chỉ là khởi đầu - production experience không thay thế được courses.

---

## Cấu trúc mỗi bài học

```
day-XX-topic-name/
├── lesson.md       # Bài học chính (11 sections chuẩn)
├── exercises.md    # Bài tập: Easy + Medium + Hard
└── document.md     # Cheat sheet, templates, reference
```

### Cấu trúc lesson.md

1. Mục tiêu bài học (đo lường được)
2. Bối cảnh & Động lực
3. Kiến thức nền tảng
4. Deep Dive (diagrams)
5. Trade-offs & Best Practices ⭐
6. Performance & Scalability ⭐
7. Security & Reliability
8. Hands-on Example (chạy được)
9. Common Pitfalls & Debugging
10. Kết nối bài trước & sau
11. Tài liệu tham khảo

### Thời lượng gợi ý mỗi ngày

| Hoạt động | Thời gian |
|-----------|-----------|
| Đọc concept | 20 phút |
| Deep dive / trade-offs | 25 phút |
| Hands-on thực hành | 50 phút |
| Debugging / checklist | 15 phút |
| Ghi chú / reflection | 10 phút |
| **Tổng** | **2 giờ** |

---

## Setup môi trường

```bash
# Kiểm tra tools cần thiết cho Phase 1
docker --version
kubectl version --client
git --version
python3 --version
go version          # optional
curl --version
```

Máy local khuyến nghị: 4+ cores, 16GB+ RAM, 80GB+ disk, Linux/macOS/WSL2.

