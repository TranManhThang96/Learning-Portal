# Ngày 7 (Capstone) — Tài liệu tra cứu nhanh

---

## 1. Checklist thiết kế hệ thống production trên K8s

Trả lời được các câu hỏi sau trước khi coi thiết kế là "production-ready":

- **Điểm vào:** Client vào hệ thống qua đâu? Có TLS chưa? Có rate limit/chặn abuse chưa?
- **Scale:** Service nào cần scale ngang? Ngưỡng CPU/memory nào trigger HPA? Scale tối đa bao nhiêu Pod là hợp lý (tránh scale vô hạn làm sập DB phía sau)?
- **HA (High Availability):** Mỗi service quan trọng chạy tối thiểu mấy replica? Nếu 1 node chết, hệ thống còn sống không (đã dùng `podAntiAffinity`/nhiều node chưa)?
- **Dữ liệu:** Cái gì cần cache (Redis)? Cache invalidate khi nào? Cái gì cần bền (DB)? Cái gì chỉ cần "gửi rồi quên" (Kafka)?
- **Giao tiếp giữa service:** Đồng bộ hay bất đồng bộ? Nếu đồng bộ, có timeout/retry/circuit breaker chưa?
- **Observability:** Có thấy được metrics theo thời gian thực chưa (Prometheus/Grafana)? Có tìm log tập trung được không khi debug (ELK)? Có alert khi lỗi tăng bất thường không?
- **Triển khai:** Ai/cái gì được phép `apply` vào cluster production? Đã qua GitOps (Argo CD) chưa, hay vẫn `kubectl apply` tay?
- **Hạ tầng:** Cluster/network được tạo bằng tay hay bằng Terraform? Có review qua PR trước khi provision không?
- **Bảo mật:** Secret nằm ở đâu, có nằm trần trong Git không? Service nào được phép gọi service nào (NetworkPolicy)? Ai được quyền gì trong cluster (RBAC)?
- **Sự cố:** Nếu Redis/Kafka/1 service chết, hệ thống còn hoạt động ở mức nào (degrade nhẹ) hay sập toàn bộ?

---

## 2. Bảng ánh xạ yêu cầu phi chức năng → giải pháp K8s

| Yêu cầu phi chức năng | Giải pháp K8s tương ứng |
| --- | --- |
| **Scalability** (chịu tải tăng) | `HorizontalPodAutoscaler`, thiết kế service stateless |
| **High Availability** | `replicas ≥ 2`, `PodDisruptionBudget`, trải Pod nhiều node (`podAntiAffinity`) |
| **Observability** | `ServiceMonitor` (Prometheus), Grafana dashboard, Filebeat/Fluentd → ELK |
| **Security** | `NetworkPolicy`, `Secret` (kèm External/Sealed Secrets), `RBAC`, `ServiceAccount` riêng theo service |
| **Recoverability** (tự phục hồi) | Liveness/readiness probe, Deployment tự tạo lại Pod chết |
| **Configurability theo môi trường** | Helm `values-dev.yaml` / `values-prod.yaml`, `ConfigMap`/`Secret` |
| **Traceability khi deploy** | GitOps (Argo CD) — mọi thay đổi đi qua Git commit, có lịch sử |
| **Reproducibility hạ tầng** | Terraform — hạ tầng là code, apply lại được ở môi trường khác |

---

## 3. Lệnh nhanh: deploy Kafka bằng Helm

Có 2 lựa chọn chart phổ biến: **Bitnami** (đơn giản, nhanh để học/demo) hoặc **Strimzi** (Kafka Operator, gần với cách vận hành Kafka thật trên K8s, dùng CRD).

### Cách 1 — Bitnami Kafka (nhanh, phù hợp học/demo)

```bash
# Thêm repo Bitnami (chỉ cần làm 1 lần)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Deploy Kafka vào namespace "capstone", bật KRaft (không cần ZooKeeper riêng)
helm install kafka bitnami/kafka \
  --namespace capstone --create-namespace \
  --set replicaCount=1 \
  --set kraft.enabled=true

# Kiểm tra Pod đã lên chưa
kubectl get pods -n capstone -l app.kubernetes.io/instance=kafka
```

### Cách 2 — Strimzi (Kafka Operator, gần production hơn)

```bash
# Cài Strimzi Operator vào namespace "capstone"
kubectl create namespace capstone
helm repo add strimzi https://strimzi.io/charts/
helm repo update
helm install strimzi-operator strimzi/strimzi-kafka-operator -n capstone

# Sau khi Operator chạy, tạo cluster Kafka qua CRD (Kafka resource)
# — xem ví dụ YAML CRD "Kafka" trong tai-lieu chính thức của Strimzi (link mục 4)
kubectl get pods -n capstone
```

> Bitnami phù hợp để **học nhanh và demo** trong bài này. Strimzi phù hợp hơn khi thật sự triển khai Kafka **production** vì quản lý lifecycle (upgrade, scale, TLS) qua Operator/CRD bài bản hơn.

---

## 4. Tài liệu tham khảo

- [Kafka Documentation (chính thức Apache Kafka)](https://kafka.apache.org/documentation/) — đọc phần "Introduction" và "Concepts" trước để hiểu topic/partition/consumer group ở mức nền tảng. Dùng làm tài liệu gốc khi cần hiểu sâu hơn phần kiến trúc đã học ở bài này.
- [Strimzi Documentation](https://strimzi.io/docs/operators/latest/overview) — đọc "Overview" trước, sau đó "Deploying and Upgrading" nếu muốn triển khai Kafka bằng Operator/CRD trên K8s thật thay vì chart Bitnami đơn giản.
- [Kubernetes Concepts (chính thức)](https://kubernetes.io/docs/concepts/) — đọc lại phần Workloads, Services, Configuration để ôn tổng hợp trước khi thiết kế hệ thống của riêng bạn.
- [The Twelve-Factor App](https://12factor.net/) — đọc toàn bộ (ngắn, 12 mục), áp dụng khi thiết kế microservice: config qua env, stateless process, logs như event stream — đúng với tinh thần các service trong bài capstone này.
- [CNCF Cloud Native Landscape](https://landscape.cncf.io/) — dùng để tra cứu, khi cần biết "còn công cụ nào khác cùng nhóm với Kafka/Prometheus/Argo CD" mà chưa học trong 7 ngày này.
