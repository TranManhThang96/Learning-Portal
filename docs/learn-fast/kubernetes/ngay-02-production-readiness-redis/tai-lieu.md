# Tài liệu tham khảo Ngày 2: Production Readiness và Redis

## Cheatsheet YAML

### Liveness / Readiness / Startup Probe

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
        - name: web-app
          image: myregistry/web-app:1.0.0
          ports:
            - containerPort: 8080
          # Startup probe: cho app thời gian khởi động trước khi tính liveness/readiness
          startupProbe:
            httpGet:
              path: /healthz
              port: 8080
            failureThreshold: 30       # 30 lần thử
            periodSeconds: 2           # cách nhau 2s => tối đa 60s để boot
          # Liveness probe: phát hiện app bị treo, kích hoạt restart
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          # Readiness probe: quyết định có nhận traffic hay không
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 2
```

### Resource Requests & Limits

```yaml
          resources:
            requests:
              cpu: "100m"      # 0.1 CPU core - đảm bảo tối thiểu để scheduler đặt Pod
              memory: "128Mi"
            limits:
              cpu: "500m"      # vượt => bị throttle (chậm lại, không kill)
              memory: "256Mi"  # vượt => bị OOMKilled (container bị kill)
```

### HPA (Horizontal Pod Autoscaler)

Tạo nhanh bằng lệnh:

```bash
# Autoscale Deployment web-app, giữ CPU trung bình 70%, min 2 max 10 Pod
kubectl autoscale deployment web-app --cpu-percent=70 --min=2 --max=10
```

Hoặc YAML tương đương:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Ingress mẫu (routing theo path)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /app1
            pathType: Prefix
            backend:
              service:
                name: app1-service
                port:
                  number: 80
          - path: /app2
            pathType: Prefix
            backend:
              service:
                name: app2-service
                port:
                  number: 80
```

### Bật addon Minikube cần thiết

```bash
# Bật Ingress controller (ingress-nginx) trên Minikube
minikube addons enable ingress

# Bật metrics-server, bắt buộc cho HPA hoạt động
minikube addons enable metrics-server

# Kiểm tra addon đã bật
minikube addons list | grep -E "ingress|metrics-server"
```

### Test Redis

```bash
# Vào container Redis và chạy redis-cli
kubectl exec -it deploy/redis -- redis-cli

# Test nhanh không cần vào shell
kubectl exec -it deploy/redis -- redis-cli PING
kubectl exec -it deploy/redis -- redis-cli SET test-key "hello"
kubectl exec -it deploy/redis -- redis-cli GET test-key
```

## Tài liệu tham khảo chính thức

| Link | Đọc gì trước | Dùng để làm gì |
|---|---|---|
| [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) | Phần "Types of probe" và "When should you use a liveness probe?" | Hiểu đúng cách cấu hình 3 loại probe, tránh cấu hình sai gây restart loop |
| [Managing Resources for Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) | Phần "Requests and limits" và "Meaning of memory" | Hiểu cơ chế throttle CPU vs OOMKilled RAM, cách tính resource |
| [Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) | Phần "How does the HPA work?" | Hiểu thuật toán scale, yêu cầu metrics-server |
| [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) | Phần "What is Ingress?" và "Types of Ingress" | Hiểu khái niệm Ingress resource, phân biệt với Ingress Controller |
| [Ingress Controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/) | Toàn bài (ngắn) | Biết cần cài Ingress Controller riêng, Kubernetes không có sẵn |
| [ingress-nginx (kubernetes.github.io/ingress-nginx)](https://kubernetes.github.io/ingress-nginx/) | Phần "Deployment" | Cách cài đặt và cấu hình cụ thể cho ingress-nginx trên Minikube |
| [Minikube Addons Handbook](https://minikube.sigs.k8s.io/docs/handbook/addons/) | Toàn bài (ngắn) | Cách enable/disable addon như ingress, metrics-server trên Minikube |
| [Redis Docs](https://redis.io/docs/latest/) | Phần "Get started" (cần kiểm chứng đường dẫn cụ thể do Redis Docs thường đổi cấu trúc) | Hiểu Redis cơ bản, lệnh redis-cli, khái niệm persistence |

---

➡️ [bai-hoc.md](./bai-hoc.md) | [thuc-hanh.md](./thuc-hanh.md)
