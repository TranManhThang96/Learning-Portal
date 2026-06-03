# Lộ trình học Kubernetes/K3s trong 45 ngày

Lộ trình này dành cho senior software engineer muốn hiểu Kubernetes ở mức đủ để thiết kế, deploy, debug và vận hành microservices thực tế. Trọng tâm không phải học thuộc YAML, mà là nắm được cách Kubernetes biến desired state thành runtime state, các trade-offs khi chọn workload/networking/storage/security pattern, và cách debug khi production có sự cố.

Mỗi ngày gồm 30-45 phút đọc `lesson.md` và khoảng 2 giờ thực hành trong `exercises.md`. Các file `document.md` đóng vai trò cheatsheet, sơ đồ hoặc bảng so sánh.

## Mục tiêu cuối cùng

Sau 45 ngày, học viên có thể:

- Thiết kế và triển khai microservices trên Kubernetes/K3s với `Deployment`, `Service`, `Ingress`, config, secret, probes, resources và autoscaling cơ bản.
- Phân biệt rõ Kubernetes upstream, K3s, local cluster tool và managed Kubernetes như EKS/GKE/AKS.
- Debug được lỗi thường gặp: `Pending`, `CrashLoopBackOff`, `ImagePullBackOff`, DNS, Service endpoint, resource pressure, rollout lỗi.
- Hiểu trade-offs khi chạy workload stateful như PostgreSQL, Redis, Kafka trên Kubernetes.
- Package app bằng Helm, đưa vào GitOps flow, và xây dựng checklist production readiness.

## Cấu trúc

```text
k8s-learning-journey-45-days/
├── README.md
├── day-01-kubernetes-mental-model-and-runtime-refresher/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── ...
├── day-28-kafka-on-kubernetes/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-29-logging/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-30-monitoring/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-31-distributed-tracing/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-32-kubernetes-debugging-toolkit/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-33-resource-debugging-and-failure-scenarios/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-34-rbac-k9s-lens-operations/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-35-pod-security-and-admission-control/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-36-helm-fundamentals/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-37-helm-chart-for-microservices/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-38-crd-and-operator-pattern/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-39-autoscaling/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-40-advanced-scheduling/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-41-cicd-gitops-with-argocd/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-42-backup-restore-disaster-recovery/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-43-managed-kubernetes-production-readiness/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-44-capstone-project-part-1/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── day-45-capstone-project-part-2/
│   ├── lesson.md
│   ├── document.md
│   └── exercises.md
├── phase-1-summary.md
├── phase-2-summary.md
├── phase-3-summary.md
├── phase-4-summary.md
├── phase-5-summary.md
└── phase-6-summary.md
```

## Prerequisites tổng

Hardware khuyến nghị:

- Laptop/desktop tối thiểu 4 CPU, 8 GB RAM; khuyến nghị 8 CPU, 16-32 GB RAM nếu chạy multi-node lab.
- Disk trống tối thiểu 30 GB.
- Network ổn định để pull container images.

Software cần có trong suốt lộ trình:

- Docker Desktop/Engine để chạy local lab mặc định bằng `k3d`.
- `kubectl`.
- `k3d` cho Day 1-3 và các lab cần reset nhanh.
- Linux VM, WSL2, hoặc máy Linux thật cho Day 4 khi cài K3s trực tiếp.
- `curl`, `jq`, `watch`, `openssl`.
- Tùy ngày: `helm`, `k9s`, `kind`, `argocd`, `velero`.

Kiến thức nền giả định:

- Đã biết Docker image/container ở mức dùng được.
- Đã quen với HTTP, DNS, reverse proxy, database, queue, observability và microservices.
- Đọc được YAML, logs và command-line output.

## Khuyến nghị môi trường lab

| Môi trường | Khi nên dùng | Điểm cần lưu ý |
|---|---|---|
| `k3d` single-node | Mặc định cho Day 1-3, học nhanh, reset dễ, chạy K3s trong Docker | Networking/storage là mô phỏng containerized, không giống hoàn toàn production |
| `k3d` multi-node | Học scheduling, node lifecycle, Service routing ở local | Cần nhiều RAM/CPU hơn single-node |
| K3s cài trực tiếp trên Linux VM | Day 4 trở đi khi cần hiểu `server`, `agent`, `systemd`, node token, kubeconfig thật | Tự quản lý OS, firewall, cleanup và dữ liệu local |
| Kind | CI, test manifest/controller, tạo/xóa cluster nhanh | Node là container Docker; networking và storage khác production |
| Minikube | Học local Kubernetes với nhiều driver/addon | Một số addon tiện cho học nhưng khác production |
| MicroK8s | Lab trên Ubuntu/snap, edge/small cluster | Cần hiểu addon nào được bật |
| Cloud VM chạy K3s | Lab gần thực tế hơn, chi phí thấp | Tự quản lý OS, firewall, backup |
| EKS/GKE/AKS | Học managed Kubernetes và production pattern | Cloud quản lý control plane, nhưng team vẫn chịu trách nhiệm workload, security, cost và observability |

## Bảng tra cứu 45 ngày

| Day | Topic | Key concepts | Exercises |
|---:|---|---|---|
| 1 | Kubernetes mental model, local lab bootstrap và container runtime refresher | `k3d`, `Pod`, desired state, reconciliation, `OCI`, `CRI`, `containerd` | Có |
| 2 | Kubernetes architecture overview | sơ đồ `control plane`/`worker node`, `kube-apiserver`, `etcd`, `scheduler`, `kubelet` | Có |
| 3 | K3s vs Kubernetes vs MicroK8s vs Minikube vs Kind | distro, local cluster, managed Kubernetes, packaged components | Có |
| 4 | Cài đặt K3s trực tiếp single-node và multi-node | K3s `server`/`agent`, kubeconfig, node join, uninstall/reset | Có |
| 5 | Control plane deep-dive | API server, etcd, scheduler, controller-manager | Có |
| 6 | Worker node deep-dive | kubelet, kube-proxy, runtime, node lifecycle | Có |
| 7 | kubectl mastery | contexts, output formats, jsonpath, events | Có |
| 8 | Pod lifecycle và multi-container patterns | init container, sidecar, probes | Có |
| 9 | ReplicaSet và Deployment | rolling update, rollback, rollout history | Có |
| 10 | StatefulSet | stable identity, ordered rollout, volume claim template | Có |
| 11 | DaemonSet | node agent, log agent, CNI/monitoring agent | Có |
| 12 | Job và CronJob | batch, retry, backoffLimit, concurrencyPolicy | Có |
| 13 | ConfigMap, Secret và secret management | External Secrets, Sealed Secrets, SOPS, Vault | Có |
| 14 | Namespace, labels, selectors, annotations | organization, ownership, filtering | Có |
| 15 | Service types | ClusterIP, NodePort, LoadBalancer, ExternalName, headless | Có |
| 16 | kube-proxy modes | iptables, IPVS, eBPF | Có |
| 17 | Ingress và Ingress controllers | NGINX, Traefik, HAProxy, TLS termination | Có |
| 18 | DNS trong Kubernetes | CoreDNS, service discovery, troubleshooting | Có |
| 19 | Network Policies | default deny, ingress/egress rules | Có |
| 20 | CNI deep-dive | Flannel, Calico, Cilium, overlay, routed, eBPF | Có |
| 21 | Service Mesh introduction | Istio, Linkerd, mTLS, traffic splitting | Có |
| 22 | Volumes | emptyDir, hostPath, projected volumes | Có |
| 23 | PersistentVolume và PersistentVolumeClaim | binding, reclaim policy, access mode | Có |
| 24 | StorageClass và dynamic provisioning | provisioner, default class, volume binding mode | Có |
| 25 | CSI drivers và troubleshooting | Longhorn, OpenEBS, Rook/Ceph, failure modes | Có |
| 26 | PostgreSQL on Kubernetes | operator overview, backup, production caveats | Có |
| 27 | Redis on Kubernetes | Sentinel, Cluster mode, persistence, failover | Có |
| 28 | Kafka on Kubernetes | Strimzi, broker identity, storage/network constraints | Có |
| 29 | Logging | EFK/ELK, Loki, stdout/stderr | Có |
| 30 | Monitoring | Prometheus, Grafana, RED/USE metrics | Có |
| 31 | Distributed tracing | OpenTelemetry, Jaeger, Tempo | Có |
| 32 | Kubernetes debugging toolkit | events, logs, endpoints, ephemeral containers | Có |
| 33 | Resource debugging | OOMKilled, CPU throttling, eviction, node pressure | Có |
| 34 | RBAC, k9s, Lens | Role, ClusterRole, ServiceAccount, operations | Có |
| 35 | Pod Security và admission control | PSS, admission controller, Gatekeeper, Kyverno | Có |
| 36 | Helm fundamentals | chart, template, values, helpers, dependencies | Có |
| 37 | Helm chart cho microservices | reusable chart, environment values | Có |
| 38 | CRD và Operator pattern | controller, finalizer, reconciliation | Có |
| 39 | Autoscaling | HPA, VPA, Cluster Autoscaler, KEDA | Có |
| 40 | Advanced scheduling | taints, tolerations, affinity, topology spread | Có |
| 41 | CI/CD và GitOps với ArgoCD | image promotion, Helm values, ApplicationSet | Có |
| 42 | Backup, restore, disaster recovery | Velero, etcd backup, restore drill | Có |
| 43 | Managed Kubernetes và production readiness | node pool, cloud LB/CSI, IAM, upgrade strategy | Có |
| 44 | Capstone Part 1 | API Gateway, microservices, Ingress, Helm | Có |
| 45 | Capstone Part 2 | Redis, Postgres, Kafka, monitoring, GitOps, backup | Có |

## Cách học hiệu quả

- Dùng `k3d` làm cluster mặc định cho Day 1-3. Khi đến Day 4 mới chuyển sang K3s cài trực tiếp trên Linux/VM để học vận hành node thật hơn.
- Mỗi ngày đọc `lesson.md` trước, ghi lại 3 câu hỏi còn mơ hồ, rồi làm `exercises.md`.
- Khi chạy lệnh, luôn so sánh actual state với desired state: YAML nói gì, API server nhận gì, controller làm gì, kubelet báo gì.
- Không bỏ qua phần inject lỗi. Kubernetes học nhanh nhất khi đọc `events`, `describe`, logs và endpoint state.
- Sau mỗi phase, tự tạo một incident nhỏ và debug theo checklist trước khi học tiếp.

## Roadmap sau 45 ngày

- Ôn CKA/CKAD nếu muốn chuẩn hóa kiến thức và luyện tốc độ CLI.
- Đi sâu production Kubernetes: multi-cluster, upgrade, backup, cost, security baseline.
- Học service mesh sâu hơn nếu hệ thống thật cần mTLS, traffic policy hoặc observability lớp L7.
- Viết controller/operator khi domain thật sự cần reconciliation riêng.
- Xây platform engineering workflow: golden path, template service, policy-as-code, developer portal.

## Tài liệu tham khảo chính

- Kubernetes Documentation: https://kubernetes.io/docs/
- Kubernetes Components: https://kubernetes.io/docs/concepts/overview/components/
- kubectl Reference: https://kubernetes.io/docs/reference/kubectl/
- K3s Documentation: https://docs.k3s.io/
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
- k3d Documentation: https://k3d.io/
- kind Documentation: https://kind.sigs.k8s.io/docs/
- Helm Documentation: https://helm.sh/docs/
- Argo CD Documentation: https://argo-cd.readthedocs.io/
- Velero Documentation: https://velero.io/docs/
