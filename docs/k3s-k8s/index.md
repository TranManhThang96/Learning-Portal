# Kubernetes/K3s — 45 ngày từ senior dev đến production K8s operator

Lộ trình dành cho senior software engineer muốn hiểu Kubernetes ở mức đủ để thiết kế, deploy, debug và vận hành microservices thực tế. Trọng tâm không phải học thuộc YAML, mà là nắm được cách Kubernetes biến desired state thành runtime state, các trade-offs khi chọn workload/networking/storage/security pattern, và cách debug khi production có sự cố.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể deploy microservices lên Kubernetes:

1. [Day 01: Mental Model & Lab Bootstrap](./k8s-learning-journey-45-days/day-01-kubernetes-mental-model-and-runtime-refresher/lesson) — desired state, reconciliation, k3d, Pod cơ bản
2. [Day 09: ReplicaSet & Deployment](./k8s-learning-journey-45-days/day-09-replicaset-and-deployment/lesson) — stateless workload, rolling update, rollback
3. [Day 15: Service Types](./k8s-learning-journey-45-days/day-15-service-types/lesson) — ClusterIP, NodePort, LoadBalancer
4. [Day 17: Ingress & Ingress Controllers](./k8s-learning-journey-45-days/day-17-ingress-and-ingress-controllers/lesson) — HTTP routing, TLS termination
5. [Day 08: Pod Lifecycle & Probes](./k8s-learning-journey-45-days/day-08-pod-lifecycle-and-multi-container-patterns/lesson) — liveness/readiness/startup probes
6. [Day 13: ConfigMap, Secret & Secret Management](./k8s-learning-journey-45-days/day-13-configmap-secret-and-practical-secret-management/lesson) — runtime config, External Secrets
7. [Day 30: Monitoring với Prometheus/Grafana](./k8s-learning-journey-45-days/day-30-monitoring/lesson) — RED/USE metrics, K3s monitoring stack

Sau 7 bài này bạn đã có thể deploy một microservice hoàn chỉnh có config, service discovery, ingress, probes và monitoring. Phần còn lại mở rộng để làm đúng, làm an toàn và tối ưu cho production.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---:|---|
| Phase 1 — Nền tảng & K3s Setup | Day 01-04 | Mental model, Architecture, K3s, kubectl | Local K3s cluster multi-node |
| Phase 2 — Core Workloads & Config | Day 05-14 | Pod, Deployment, StatefulSet, DaemonSet, Job, ConfigMap/Secret, Label/Namespace | Stateless + stateful workload deployment |
| Phase 3 — Networking & Traffic | Day 15-21 | Service, kube-proxy, Ingress, DNS, NetworkPolicy, CNI, Service Mesh | Ingress + NetworkPolicy cho microservices |
| Phase 4 — Storage & Stateful Apps | Day 22-28 | Volume, PV/PVC, StorageClass, CSI, PostgreSQL, Redis, Kafka trên K8s | Stateful workload + storage production |
| Phase 5 — Observability & Security | Day 29-35 | Logging, Monitoring, Tracing, Debugging, RBAC, Pod Security | Observability stack + security hardening |
| Phase 6 — Advanced & Capstone | Day 36-45 | Helm, CRD/Operator, Autoscaling, Scheduling, GitOps, Backup, Capstone | Helm chart + GitOps + Capstone project |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 1 | Mental Model & Lab | Nền tảng tư duy desired state + reconciliation; không hiểu thì không debug được |
| Day 8 | Pod Lifecycle & Probes | Probes quyết định Pod có nhận traffic không; sai probes thì deployment nào cũng lỗi |
| Day 9 | ReplicaSet & Deployment | Workload stateless là pattern phổ biến nhất; rollout/rollback là kỹ năng hàng ngày |
| Day 13 | ConfigMap, Secret | 100% service cần config và secret; biết External Secrets operator cho production |
| Day 15 | Service Types | Service là abstraction network cốt lõi; không hiểu thì không connect được Pod nào |
| Day 17 | Ingress | HTTP routing, TLS termination — production bắt buộc |
| Day 29 | Logging | kubectl logs không đủ cho production; hiểu EFK/Loki pipeline |
| Day 30 | Monitoring | Prometheus/Grafana, RED/USE metrics để biết production có vấn đề gì |
| Day 32 | Debugging Toolkit | Ephemeral containers, events, endpoint debug — cứu mạng khi incident |
| Day 36 | Helm Fundamentals | Đóng gói và parameterize manifest; chuẩn bị cho GitOps |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 2 | Architecture Overview | Biết component nào chịu trách nhiệm gì để debug đúng chỗ |
| Day 3 | K3s vs K8s vs Distros | Chọn đúng distro cho từng môi trường — lab, staging, production |
| Day 4 | Install K3s Single/Multi Node | Hiểu server/agent thật, kubeconfig, node join process |
| Day 7 | kubectl Mastery | Công cụ CLI dùng hàng ngày; jsonpath, events, field-selector |
| Day 10 | StatefulSet | Khi cần stable identity + per-replica storage (database, queue) |
| Day 14 | Namespace, Labels | Tổ chức resource, multi-team, cost allocation |
| Day 16 | kube-proxy modes | iptables vs IPVS vs eBPF; ảnh hưởng performance và debug |
| Day 18 | DNS trong Kubernetes | CoreDNS, service discovery, troubleshooting |
| Day 19 | Network Policies | Default deny, zero-trust giữa các service |
| Day 23 | PV/PVC | Lưu dữ liệu bền vững; binding, reclaim policy |
| Day 32 | Debugging Toolkit | Kỹ năng sống còn khi production incident |
| Day 33 | Resource Debugging | OOMKilled, CPU throttling, node pressure |
| Day 34 | RBAC, k9s, Lens | Quản lý quyền và operations hàng ngày |
| Day 39 | Autoscaling | HPA, VPA, KEDA — scale workload theo metric thực tế |
| Day 41 | GitOps với ArgoCD | Release automation, image promotion, ApplicationSet |

### Nhóm C — Học sau khi làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---|
| Day 5-6 | Control Plane & Worker Node Deep Dive | Khi cần hiểu internals để debug lỗi hệ thống hiếm gặp |
| Day 11 | DaemonSet | Khi cần node agent (log, monitoring, CNI) |
| Day 12 | Job & CronJob | Khi cần batch processing định kỳ |
| Day 20 | CNI Deep Dive | Khi cần chọn/tune network plugin cho performance |
| Day 21 | Service Mesh | Khi cần mTLS, traffic splitting, observability L7 |
| Day 24 | StorageClass & Dynamic Provisioning | Khi chọn storage backend cho production |
| Day 25 | CSI Drivers | Khi cần storage production với Longhorn/Rook/Ceph |
| Day 26-28 | PostgreSQL, Redis, Kafka on K8s | Khi thực sự chạy stateful workload trên Kubernetes |
| Day 31 | Distributed Tracing | Khi cần trace request xuyên service |
| Day 35 | Pod Security & Admission Control | Khi cần chặn workload không an toàn ở cấp cluster |
| Day 37 | Helm Chart cho Microservices | Khi có nhiều microservice cần chart chuẩn |
| Day 38 | CRD & Operator | Khi cần tự động hóa operational knowledge |
| Day 40 | Advanced Scheduling | Khi cần kiểm soát Pod placement chính xác |
| Day 42 | Backup/Restore/DR | Khi dữ liệu production cần được bảo vệ |
| Day 43 | Managed K8s Production Readiness | Khi chuẩn bị lên EKS/GKE/AKS |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---|
| Day 22 | Volumes cơ bản | Đọc nhanh, tập trung vào emptyDir và hostPath |
| Phase Summaries | Tổng kết phase | Đọc để review, không cần học mới |
| Các file `document.md` | Chi tiết mở rộng | Tra cứu khi cần cheatsheet, sơ đồ, bảng so sánh |
| Lab nâng cao trong `exercises.md` | Bài tập mở rộng | Làm sau khi hoàn thành core path |

## Cách học đề xuất

1. **Ưu tiên Phase 1 + 2 + 3 trước** (Day 01-21): đây là 20% kiến thức tạo 80% giá trị deployment. Học xong bạn deploy được microservices có config, service mesh, ingress và monitoring.
2. **Sau đó làm Phase 5** (Day 29-35): observability và debugging — kỹ năng sống còn khi vận hành production.
3. **Phase 4** (Day 22-28): học khi cần chạy stateful workload (database, queue, cache) trên Kubernetes.
4. **Phase 6** (Day 36-45): học khi chuẩn bị GitOps, Helm, autoscaling và capstone.

Mỗi ngày học 2-2.5 giờ theo format:
- 15 phút: đọc mục tiêu và TL;DR
- 30-45 phút: học concept chính (đọc `lesson.md`)
- 45-60 phút: hands-on (làm `exercises.md`, tham khảo `document.md`)
- 20 phút: ghi chú trade-off, production caveat
- 10 phút: update learning log

## Mini project — Capstone Microservices Platform

**Mô tả:** Xây dựng nền tảng microservices hoàn chỉnh trên Kubernetes/K3s trong 2 ngày cuối (Day 44-45).

**Stack:**
- API Gateway (Kong/KrakenD) + Ingress (Traefik/NGINX)
- Microservices: user-service, order-service, notification-service
- Database: PostgreSQL (StatefulSet + Operator), Redis (Sentinel/Cluster)
- Message Queue: Kafka (Strimzi Operator)
- Observability: Prometheus + Grafana + Loki + Tempo
- Package: Helm chart cho mỗi service
- GitOps: ArgoCD với ApplicationSet

**Kiến thức áp dụng:**
- Deployment, Service, Ingress, ConfigMap, Secret
- StatefulSet, PV/PVC, StorageClass
- HPA, PDB, resource requests/limits
- Helm chart, values, dependency
- ArgoCD, image promotion, ApplicationSet
- Logging, monitoring, tracing
- Backup/restore với Velero

**Tiêu chí hoàn thành:**
- Cluster chạy với ít nhất 2 node (hoặc k3d multi-node)
- API Gateway route request đến đúng service
- Service A gọi Service B qua Service DNS
- Stateful workload có PV/PVC + backup
- Monitoring dashboards hiển thị RED metrics
- ArgoCD sync app từ Git repo
- Rollout và rollback không làm rơi traffic

## Checklist học nhanh

- [ ] Tôi đã hiểu Kubernetes là control system với desired state và reconciliation loop
- [ ] Tôi đã học xong toàn bộ nhóm A (Day 1, 8, 9, 13, 15, 17, 29, 30, 32, 36)
- [ ] Tôi đã deploy được microservice đầu tiên với Deployment + Service + Ingress
- [ ] Tôi đã cấu hình probes đúng và biết debug rollout kẹt
- [ ] Tôi đã setup Prometheus + Grafana để quan sát cluster
- [ ] Tôi đã dùng kubectl events, describe, logs, ephemeral containers để debug
- [ ] Tôi đã package app bằng Helm và deploy qua ArgoCD
- [ ] Tôi biết phần nào thuộc nhóm C/D để quay lại sau

## Flashcard / câu hỏi ôn tập gợi ý

1. Kubernetes khác Docker Compose ở điểm nào?
   - **Đáp án:** Là control system có reconciliation loop, desired state, tự động sửa lỗi, scheduler, service discovery built-in.
   - **Liên quan:** Day 01

2. `kubectl get pods` thấy Pod `Pending` — nguyên nhân thường gặp nhất là gì?
   - **Đáp án:** Thiếu tài nguyên (CPU/memory), image pull lỗi, PVC pending, node selector/taint không match.
   - **Liên quan:** Day 32

3. `readinessProbe` khác `livenessProbe` thế nào?
   - **Đáp án:** readiness quyết định Pod có nhận traffic từ Service không; liveness quyết định container có được restart không.
   - **Liên quan:** Day 08

4. Khi nào dùng StatefulSet thay vì Deployment?
   - **Đáp án:** Khi cần stable network identity (pod-0, pod-1) + per-replica storage (volume claim template).
   - **Liên quan:** Day 10

5. `ClusterIP` Service khác `NodePort` thế nào?
   - **Đáp án:** ClusterIP chỉ truy cập trong cluster network; NodePort expose port trên mỗi node IP.
   - **Liên quan:** Day 15

6. Làm sao để biết Service có endpoints không?
   - **Đáp án:** `kubectl get endpoints <service>` hoặc `kubectl describe svc <service>`.
   - **Liên quan:** Day 15

7. `ConfigMap` và `Secret` khác nhau ở điểm nào?
   - **Đáp án:** Secret được base64-encoded, có encryption at rest, có thể dùng external secret system. ConfigMap là plain text.
   - **Liên quan:** Day 13

8. Helm chart gồm những thành phần nào?
   - **Đáp án:** `Chart.yaml`, `values.yaml`, `templates/`, `helpers.tpl`, `charts/` (dependencies).
   - **Liên quan:** Day 36

9. Khi nào nên dùng NetworkPolicy?
   - **Đáp án:** Khi cần zero-trust giữa các service: chỉ cho phép Service A gọi Service B, chặn tất cả phần còn lại.
   - **Liên quan:** Day 19

10. RED metrics trong monitoring là gì?
    - **Đáp án:** Rate (request rate), Errors (error rate), Duration (latency distribution).
    - **Liên quan:** Day 30

11. ArgoCD so với Helm CLI khác nhau thế nào?
    - **Đáp án:** Helm CLI deploy thủ công/từ CI; ArgoCD là GitOps operator tự động sync cluster state với Git repo.
    - **Liên quan:** Day 41

12. Làm sao để scale Deployment dựa trên CPU?
    - **Đáp án:** Tạo HPA (HorizontalPodAutoscaler) với target CPU utilization percentage.
    - **Liên quan:** Day 39

## Tài nguyên

- [README tổng quan khóa học](./k8s-learning-journey-45-days/README.md)
- [Phase 1 Summary: Nền tảng & K3s Setup](./k8s-learning-journey-45-days/phase-1-summary.md)
- [Phase 2 Summary: Core Workloads](./k8s-learning-journey-45-days/phase-2-summary.md)
- [Phase 3 Summary: Networking](./k8s-learning-journey-45-days/phase-3-summary.md)
- [Phase 4 Summary: Storage & Stateful Apps](./k8s-learning-journey-45-days/phase-4-summary.md)
- [Phase 5 Summary: Observability & Security](./k8s-learning-journey-45-days/phase-5-summary.md)
- [Phase 6 Summary: Advanced & Capstone](./k8s-learning-journey-45-days/phase-6-summary.md)
- [K8s Documentation](https://kubernetes.io/docs/)
- [K3s Documentation](https://docs.k3s.io/)
- [k3d Documentation](https://k3d.io/)
- [Helm Documentation](https://helm.sh/docs/)
