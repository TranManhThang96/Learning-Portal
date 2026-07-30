# Ngày 7 (Capstone) — Thực hành

---

## Chuẩn bị

- Minikube đang chạy, đủ tài nguyên (khuyến nghị `minikube start --cpus=4 --memory=6144` — Kafka + Redis + nhiều service cùng lúc khá nặng).
- Helm đã cài (`helm version`).
- Argo CD từ Ngày 4 (tùy chọn, dùng ở bài Advanced).
- Nếu có sẵn chart/manifest từ ngày 2 (Redis, HPA, probes) và ngày 6 (Prometheus/Grafana/ELK), tận dụng lại — bài này là ghép nối, không phải viết lại từ đầu.

---

## Bài 1 (Beginner) — Vẽ sơ đồ kiến trúc của riêng bạn

**Mục tiêu:** tự tay thiết kế (không copy y nguyên bài học) một sơ đồ kiến trúc tối thiểu gồm gateway + 2 service + Redis + Kafka + observability.

**Yêu cầu:** tạo file `so-do-cua-toi.md` trong thư mục làm việc của bạn, viết 1 sơ đồ mermaid.

**Các bước:**

1. Chọn 1 bài toán ví dụ khác với `order-service` trong bài học (ví dụ: blog có `post-service` + `comment-service`, hoặc booking có `booking-service` + `payment-service`).
2. Viết sơ đồ mermaid `flowchart` gồm: Client → Gateway → 2 service của bạn → Redis (cache) + Kafka (event) → nơi Prometheus/Grafana và ELK gắn vào.
3. Liệt kê bên dưới sơ đồ: mỗi thành phần dùng K8s resource gì (ví dụ: "post-service → Deployment + Service + HPA").

**Kết quả mong đợi:** 1 file markdown có sơ đồ mermaid hợp lệ (render được) + bảng liệt kê resource.

**Kiến thức luyện tập:** tổng hợp lại toàn bộ kiến trúc đã học, tự áp dụng vào bài toán khác thay vì học vẹt ví dụ có sẵn.

---

## Bài 2 (Practical) — Deploy mini hệ thống: Gateway + Service + Redis

**Mục tiêu:** deploy được 1-2 service thật, kết nối Redis, truy cập qua Ingress, có probes + resource limits + HPA.

**Yêu cầu:** Minikube đã bật addon `ingress` (`minikube addons enable ingress`), metrics-server đã bật (`minikube addons enable metrics-server`) để HPA hoạt động.

**Các bước:**

1. Tạo namespace:

```bash
kubectl create namespace capstone
```

2. Deploy Redis (Bitnami chart, đơn giản cho demo):

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install redis bitnami/redis \
  --namespace capstone \
  --set auth.enabled=false \
  --set architecture=standalone
```

3. Tạo Deployment cho `order-service` (dùng image demo `hashicorp/http-echo` để mô phỏng nhanh, hoặc thay bằng image thật của bạn nếu có). File `order-service.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: capstone
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
        - name: order-service
          image: hashicorp/http-echo:1.0
          args:
            - "-text=order-service OK"
            - "-listen=:5678"
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "128Mi"
          readinessProbe:
            httpGet:
              path: /
              port: 5678
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 5678
            initialDelaySeconds: 10
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: capstone
spec:
  selector:
    app: order-service
  ports:
    - port: 80
      targetPort: 5678
```

```bash
kubectl apply -f order-service.yaml
```

4. Tạo Ingress làm gateway:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: capstone-gateway
  namespace: capstone
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: capstone.local
      http:
        paths:
          - path: /orders
            pathType: Prefix
            backend:
              service:
                name: order-service
                port:
                  number: 80
```

```bash
kubectl apply -f ingress.yaml
echo "$(minikube ip) capstone.local" | sudo tee -a /etc/hosts
```

5. Verify truy cập qua gateway:

```bash
curl http://capstone.local/orders
# Kỳ vọng: order-service OK
```

6. Thêm HPA cho `order-service`:

```bash
kubectl autoscale deployment order-service -n capstone \
  --cpu-percent=70 --min=2 --max=5

kubectl get hpa -n capstone
```

**Kết quả mong đợi:** `curl capstone.local/orders` trả về response qua Ingress; `kubectl get hpa -n capstone` hiển thị HPA đang theo dõi CPU; `kubectl describe pod` cho thấy readiness/liveness probe đã cấu hình.

**Kiến thức luyện tập:** ghép Ingress + Deployment + probes + limits + HPA thành 1 luồng hoạt động thật, không còn là ví dụ rời rạc từng ngày.

---

## Bài 3 (Advanced/Differentiating) — Thêm Kafka, event bất đồng bộ, observability, failure mode

**Mục tiêu:** chứng minh luồng event bất đồng bộ qua Kafka, cắm observability, và quan sát hệ thống khi 1 thành phần chết.

**Yêu cầu:** đã hoàn thành Bài 2. Đủ tài nguyên máy cho Kafka (khá nặng trên Minikube).

**Các bước:**

1. Deploy Kafka (Bitnami, KRaft mode — không cần ZooKeeper riêng):

```bash
helm install kafka bitnami/kafka \
  --namespace capstone \
  --set replicaCount=1 \
  --set kraft.enabled=true \
  --set listeners.client.protocol=PLAINTEXT

kubectl get pods -n capstone -l app.kubernetes.io/instance=kafka
```

2. Tạo topic `order-events` bằng Pod tạm chạy Kafka client (image đi kèm chart Bitnami):

```bash
kubectl run kafka-client --restart='Never' -n capstone \
  --image docker.io/bitnami/kafka:3.7 --command -- sleep infinity

kubectl exec -it kafka-client -n capstone -- \
  kafka-topics.sh --create --topic order-events \
  --bootstrap-server kafka.capstone.svc.cluster.local:9092 \
  --partitions 3 --replication-factor 1
```

3. Mô phỏng **producer** (gửi 1 event) và **consumer** (đọc event) bằng script có sẵn trong image Kafka, chạy trực tiếp trong Pod để chứng minh luồng bất đồng bộ:

```bash
# Producer: gửi 1 message vào topic order-events
kubectl exec -it kafka-client -n capstone -- bash -c \
  'echo "OrderCreated:order-123" | kafka-console-producer.sh \
  --broker-list kafka.capstone.svc.cluster.local:9092 --topic order-events'

# Consumer: mở terminal khác, đọc message từ đầu topic
kubectl exec -it kafka-client -n capstone -- \
  kafka-console-consumer.sh \
  --bootstrap-server kafka.capstone.svc.cluster.local:9092 \
  --topic order-events --from-beginning
```

**Kết quả mong đợi:** consumer nhận được message `OrderCreated:order-123` đã publish, chứng minh producer/topic/consumer hoạt động — đây là mô phỏng đơn giản cho việc `order-service` publish event và `inventory-service`/`notification-service` consume trong thiết kế thật.

4. Cắm observability (dùng lại từ Ngày 6): trỏ Prometheus scrape namespace `capstone` (thêm `ServiceMonitor` hoặc annotation `prometheus.io/scrape: "true"` lên Service `order-service`), và trỏ Filebeat/Fluentd (nếu đã deploy ở Ngày 6) thu log namespace `capstone`. Verify bằng Grafana dashboard thấy metrics của `order-service`, và Kibana/ELK tìm được log của Pod `order-service`.

5. (Tùy chọn) Deploy toàn bộ qua Argo CD: đóng gói `order-service.yaml` + `ingress.yaml` thành 1 Helm chart, push lên Git repo, tạo Argo CD `Application` trỏ tới repo đó, verify Argo CD tự sync khi có thay đổi (thay `replicas` trong Git, xem Argo CD tự áp dụng).

6. **Thảo luận failure mode** — thử và quan sát:

```bash
# Tắt Redis, xem order-service còn phản hồi không (nếu app có fallback đọc DB)
kubectl scale deployment redis-master -n capstone --replicas=0

# Tắt Kafka, thử producer gửi lại — quan sát lỗi kết nối
kubectl scale statefulset kafka -n capstone --replicas=0

# Tắt 1 trong 2 Pod order-service, xem Service vẫn route được qua Pod còn lại
kubectl scale deployment order-service -n capstone --replicas=1
```

Ghi lại quan sát: điều gì thực sự xảy ra khi mỗi thành phần chết? Có khớp với dự đoán ở bảng "failure mode" trong `bai-hoc.md` không?

**Kết quả mong đợi:** hiểu rõ bằng thực nghiệm (không chỉ lý thuyết) hệ thống phản ứng thế nào khi từng thành phần chết; có ghi chú ngắn về khoảng cách giữa thiết kế lý tưởng và thực tế đã deploy (ví dụ: image demo `http-echo` không có logic fallback thật, nên "Redis chết" trong bài thực hành này sẽ không tự fallback — đây là điểm cần làm thêm nếu triển khai thật).

**Kiến thức luyện tập:** vận hành Kafka ở mức cơ bản trên K8s, ghép observability vào hệ thống nhiều thành phần, và tư duy failure mode thực nghiệm thay vì chỉ đọc lý thuyết.

---

## Checklist hoàn thành cả khóa (7 ngày)

- [ ] **Cấp độ 1 — Hiểu và deploy được:** biết Pod/Deployment/Service/Ingress/ConfigMap/Secret là gì và deploy được 1 app đơn giản (Ngày 1).
- [ ] **Cấp độ 1 — Vận hành cơ bản:** cấu hình được readiness/liveness probe, resource requests/limits, HPA cho 1 service (Ngày 2).
- [ ] **Cấp độ 2 — Đóng gói và tái sử dụng:** viết được Helm chart cho app của mình, quản nhiều môi trường qua `values.yaml` (Ngày 3).
- [ ] **Cấp độ 2 — Triển khai tự động:** hiểu và làm được GitOps cơ bản với Argo CD, biết vai trò CI (Jenkins) trước GitOps (Ngày 4).
- [ ] **Cấp độ 2 — Hạ tầng là code:** viết được Terraform cơ bản để provision hạ tầng, hiểu vì sao không tạo hạ tầng bằng tay (Ngày 5).
- [ ] **Cấp độ 3 — Quan sát được hệ thống:** đọc được metrics qua Prometheus/Grafana, tìm log qua ELK khi debug sự cố (Ngày 6).
- [ ] **Cấp độ 3 — Thiết kế hệ thống hoàn chỉnh:** ghép được gateway + microservices + cache + message broker + observability + GitOps + IaC thành 1 thiết kế nhất quán, biết trade-off của từng lựa chọn (Ngày 7).
- [ ] **Cấp độ 3 — Tư duy vận hành senior:** giải thích được resilience (retry/circuit breaker/graceful degradation), capacity planning, và failure mode của hệ thống mình thiết kế (Ngày 7).

> Hoàn thành hết checklist trên nghĩa là bạn đã đi từ "deploy được 1 Pod" đến "thiết kế và vận hành được 1 hệ thống production-grade nhiều thành phần" — đúng mục tiêu của khóa 7 ngày này.
