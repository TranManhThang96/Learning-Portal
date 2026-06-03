# Day 17: Mini-project — Deploy Microservice Stack on Local Kubernetes

## 1. Mục tiêu bài học

Sau mini-project này, bạn sẽ đo được các kết quả sau:

1. **Deploy được** một microservice stack hoàn chỉnh (tối thiểu 3 services) trên local Kubernetes cluster.
2. **Cấu hình được** Ingress routing, ConfigMap/Secret, PVC cho stateful service, và health checks.
3. **Sử dụng được** Helm chart hoặc Kustomize overlay để quản lý manifests.
4. **Debug được** các lỗi thường gặp khi deploy multi-service architecture trên Kubernetes.
5. **Viết được** cleanup script, troubleshooting notes và incident note ngắn cho stack.

---

## 2. Bối cảnh & Động lực

Ở các bài trước, bạn đã học từng mảnh của Kubernetes: `Deployment`, `Service`, `Ingress`, `ConfigMap`, `Secret`, `PVC`, Helm/Kustomize. Production không vận hành từng mảnh riêng lẻ; rủi ro thường xuất hiện ở điểm nối giữa các thành phần: route sai, service discovery sai, probe sai, secret thiếu, PVC mất dữ liệu hoặc cleanup không đầy đủ.

Mini-project này gom các concept đó vào một stack local-first để bạn luyện cách triển khai, verify và debug end-to-end trong khoảng 2 giờ. Nếu làm sai trong production, hậu quả không chỉ là pod lỗi mà còn có thể là downtime, 502 từ gateway, mất dữ liệu stateful, hoặc rollback khó vì manifest không được quản lý nhất quán.

### Scenario: BookStore Microservices

Bạn được giao triển khai hệ thống quản lý cửa hàng sách online gồm 3 services:

```
┌─────────────────────────────────────────────────────┐
│                    Client (Browser)                  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
                       ▼
┌──────────────────────────────────────────────────────┐
│              NGINX Ingress Controller                 │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ /api/*          │  │ /                        │   │
│  │ → api-gateway   │  │ → frontend               │   │
│  └─────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐
│  API Gateway     │    │   Frontend       │
│  (NGINX proxy)   │    │   (NGINX static) │
│  Port: 8080      │    │   Port: 80       │
│  Stateless       │    │   Stateless      │
└────────┬─────────┘    └──────────────────┘
         │
         ▼
┌──────────────────────┐
│   Book Service        │
│   (NGINX + API mock)  │
│   Port: 80            │
│   Stateless           │
│   ConfigMap: app cfg  │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│   Redis Cache         │
│   Port: 6379          │
│   Stateful (PVC)      │
│   Secret: password    │
└──────────────────────┘
```

### Tại sao scenario này?

- **4 services** ở mức đủ phức tạp để thấy vấn đề thật nhưng vẫn deploy được trong 2 giờ.
- **Mix stateless/stateful**: frontend + api là stateless, Redis là stateful.
- **Service-to-service communication**: API gateway → book service → Redis.
- **Ingress routing**: path-based routing cho frontend và API.
- **Config & Secret**: ConfigMap cho app config, Secret cho Redis password.
- **PVC**: Redis cần persistent storage.

---

## 3. Kiến thức nền tảng

Các khái niệm nền tảng cần nắm trước khi deploy:

- `Deployment` phù hợp cho workload stateless như frontend, API gateway và book-service vì có thể scale ngang, rolling update và tự thay thế pod lỗi.
- `StatefulSet` phù hợp cho Redis trong bài này vì cần identity ổn định (`redis-0`) và PVC gắn theo pod.
- `Service` cung cấp DNS ổn định để service-to-service communication không phụ thuộc IP động của pod.
- `Ingress` nhận request từ local machine và route theo host/path vào service nội bộ.
- `ConfigMap` chứa cấu hình không nhạy cảm như NGINX config, HTML mock, app settings.
- `Secret` chứa dữ liệu nhạy cảm hơn ConfigMap, nhưng trong Kubernetes mặc định chỉ được base64 encode, không phải encryption end-to-end.
- `PVC` tách lifecycle dữ liệu khỏi pod lifecycle; xóa pod không mất dữ liệu, nhưng xóa PVC có thể mất dữ liệu.
- Kustomize overlay giúp giữ một `base` chung và thay đổi dev/prod bằng patch nhỏ, tránh copy-paste toàn bộ manifest.

Trong bài này, cluster local bằng kind đóng vai trò production-like sandbox: đủ để kiểm tra manifest, route, readiness/liveness, DNS, PVC và cleanup flow trước khi chuyển sang cluster thật.

---

## 4. Deep Dive

### Component Interaction

```
                    ┌─────────────────────────┐
                    │      Ingress             │
                    │  bookstore.local         │
                    │  /      → frontend       │
                    │  /api/* → api-gateway    │
                    └─────┬──────────┬─────────┘
                          │          │
              ┌───────────┘          └───────────┐
              ▼                                  ▼
     ┌─────────────────┐              ┌─────────────────┐
     │ frontend         │              │ api-gateway      │
     │ Deployment       │              │ Deployment       │
     │ replicas: 1      │              │ replicas: 2      │
     │ image: nginx     │              │ image: nginx     │
     │ ConfigMap:       │              │ ConfigMap:       │
     │   index.html     │              │   nginx.conf     │
     └─────────────────┘              │   (proxy to      │
                                      │    book-service)  │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ book-service     │
                                      │ Deployment       │
                                      │ replicas: 2      │
                                      │ image: nginx     │
                                      │ ConfigMap:       │
                                      │   API responses  │
                                      │ Secret ref:      │
                                      │   redis-password │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ redis            │
                                      │ StatefulSet      │
                                      │ replicas: 1      │
                                      │ PVC: 1Gi         │
                                      │ Secret:          │
                                      │   redis-password │
                                      └─────────────────┘
```

### Kubernetes Resources tạo ra

| Resource | Tên | Mục đích |
|----------|-----|----------|
| Namespace | bookstore | Isolation |
| Deployment | frontend | Serve static HTML |
| Deployment | api-gateway | Reverse proxy to book-service |
| Deployment | book-service | API mock trả JSON |
| StatefulSet | redis | Cache layer, persistent storage |
| Service (ClusterIP) | frontend | Internal access |
| Service (ClusterIP) | api-gateway | Internal access |
| Service (ClusterIP) | book-service | Internal access |
| Service (ClusterIP, Headless) | redis | Stable network identity |
| Ingress | bookstore-ingress | External routing |
| ConfigMap | frontend-config | HTML content |
| ConfigMap | api-gateway-config | NGINX proxy config |
| ConfigMap | book-service-config | API response data |
| Secret | redis-secret | Redis password |
| PVC | redis-data | Persistent storage |

---

## 5. Trade-offs & Best Practices ⭐

| Quyết định | Lựa chọn trong project | Trade-off production |
|------------|------------------------|----------------------|
| API gateway bằng NGINX | Dễ chạy local, ít dependency | Không thay thế được API gateway đầy đủ như Envoy/Kong nếu cần auth, rate limit, tracing sâu |
| Redis chạy bằng StatefulSet | Minh họa stateful workload và PVC | Production cần backup, restore test, persistence mode rõ ràng và anti-affinity |
| Secret inline base64 | Đơn giản cho lab local | Production nên dùng External Secrets, Sealed Secrets hoặc secret manager |
| Kustomize overlay | Dễ đọc diff giữa dev/prod | Với app nhiều biến thể hoặc dependency phức tạp có thể cần Helm chart |
| Ingress path routing | Dễ test bằng `bookstore.local` | Production cần TLS, WAF/rate limit, timeout policy và observability |

Best practices theo scenario:

- **Startup nhỏ**: dùng Kustomize base/overlay, kind cho dev, một ingress controller chuẩn, CI chạy `kubectl apply --dry-run=server`.
- **Mid-size company**: thêm Helm/Kustomize convention, policy kiểm tra resource/probe/secret, namespace riêng theo team hoặc environment.
- **Enterprise**: chuẩn hóa platform templates, GitOps, admission policy, external secret manager, network isolation và audit trail.
- **High-traffic system**: tách gateway, backend, cache thành scaling unit riêng; thêm HPA, PDB, topology spread, load test và SLO-based rollout.

Anti-patterns cần tránh:

- Copy manifest giữa dev/staging/prod rồi sửa tay từng file.
- Dùng `latest` image tag cho workload quan trọng.
- Đưa password thật vào Git hoặc truyền qua command line.
- Chỉ test `kubectl apply` mà không test route end-to-end.
- Xóa PVC như một bước cleanup mặc định trong môi trường có dữ liệu thật.

---

## 6. Performance & Scalability ⭐

Stack này nhỏ nhưng có đủ điểm nghẽn thường gặp:

- **Ingress Controller**: nghẽn ở connection handling, timeout hoặc upstream keepalive. Phát hiện bằng access log, 4xx/5xx rate và latency p95/p99.
- **API gateway**: nếu replicas quá ít, gateway thành bottleneck trước backend. Scale ngang gateway khi CPU/network tăng và backend còn dư capacity.
- **Book service**: stateless nên scale ngang dễ, nhưng cần readiness probe đúng để tránh route vào pod chưa sẵn sàng.
- **Redis**: scale không đơn giản như stateless service; tăng replica không tự động tăng write capacity nếu chưa dùng Redis Cluster/Sentinel.
- **PVC/storage**: local kind đủ cho lab, nhưng production cần IOPS/latency, backup/restore và reclaim policy rõ ràng.

Scaling strategy:

- **Vertical scaling**: tăng requests/limits khi pod bị CPU throttling hoặc OOMKilled do sizing thấp.
- **Horizontal scaling**: tăng replicas cho frontend, gateway, book-service khi workload stateless và latency tăng theo traffic.
- **Queue-based scaling**: chưa dùng trong project này, nhưng phù hợp nếu backend xử lý job async.
- **Event-driven scaling**: sẽ nối sang Day 19 với KEDA khi workload phụ thuộc queue/event.

Khi scale là sai giải pháp: DNS/service name sai, readiness probe fail, ConfigMap mount sai hoặc PVC mất dữ liệu không thể giải quyết bằng tăng replicas.

---

## 7. Security & Reliability Considerations

- **Least privilege**: project chưa tạo RBAC riêng; production nên dùng ServiceAccount riêng cho từng workload và hạn chế quyền API server.
- **Secret management**: Secret trong bài là local demo. Không dùng giá trị thật, không commit secret thật, không truyền password qua `--set` hoặc shell history.
- **Attack surface**: chỉ expose Ingress cần thiết; Redis chỉ dùng ClusterIP/headless nội bộ, không expose ra ngoài cluster.
- **Failure isolation**: frontend, gateway, backend, Redis tách thành resource riêng để lỗi từng lớp dễ quan sát và rollback.
- **Rollback plan**: Kustomize base/overlay trong Git giúp revert manifest; với Helm cần kiểm soát release history và `helm rollback`.
- **Blast radius**: namespace `bookstore` cô lập resource lab; cleanup chỉ nhắm namespace/project này.
- **Reliability**: readiness/liveness probes giúp tránh route traffic vào pod lỗi, nhưng probe sai có thể gây restart loop hoặc remove pod healthy khỏi endpoints.

---

## 8. Hands-on Example

### Prerequisites & Setup

### Tools cần thiết

```bash
# Kiểm tra
docker --version        # >= 20.10
kubectl version --client # >= 1.25
kind version            # >= 0.17
helm version            # >= 3.10 (optional nếu dùng Kustomize)
```

### Tạo kind cluster với Ingress support

```bash
# Tạo cluster config
cat > kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
EOF

# Tạo cluster
kind create cluster --name bookstore --config kind-config.yaml

# Verify
kubectl cluster-info --context kind-bookstore
kubectl get nodes
# Expected:
# NAME                      STATUS   ROLES           AGE   VERSION
# bookstore-control-plane   Ready    control-plane   30s   v1.xx.x

# Cài NGINX Ingress Controller cho kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Đợi Ingress Controller ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

---

### Step-by-step Implementation Guide

### Bước 1: Tạo project structure

```bash
mkdir -p bookstore-k8s/{base,overlays/dev}
```

Các file YAML bên dưới đặt trong thư mục `bookstore-k8s/`. Ví dụ comment `# base/namespace.yaml` nghĩa là tạo file `bookstore-k8s/base/namespace.yaml`. Các lệnh deploy/verify giả định bạn đang đứng ở thư mục cha chứa `bookstore-k8s`.

### Bước 2: Namespace

```yaml
# base/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: bookstore
  labels:
    app.kubernetes.io/part-of: bookstore
```

### Bước 3: Redis (Stateful Service)

```yaml
# base/redis-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: redis-secret
  namespace: bookstore
type: Opaque
data:
  redis-password: Ym9va3N0b3JlLXJlZGlzLXBhc3M=  # bookstore-redis-pass
```

```yaml
# base/redis-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
  namespace: bookstore
  labels:
    app: redis
spec:
  serviceName: redis
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          command:
            - redis-server
            - "--requirepass"
            - "$(REDIS_PASSWORD)"
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: redis-password
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          readinessProbe:
            exec:
              command:
                - redis-cli
                - -a
                - "$(REDIS_PASSWORD)"
                - ping
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            exec:
              command:
                - redis-cli
                - -a
                - "$(REDIS_PASSWORD)"
                - ping
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: redis-data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: redis-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
```

```yaml
# base/redis-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: bookstore
spec:
  clusterIP: None
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

### Bước 4: Book Service (Backend API)

```yaml
# base/book-service-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: book-service-config
  namespace: bookstore
data:
  default.conf: |
    server {
        listen 80;
        server_name _;

        location /api/books {
            default_type application/json;
            return 200 '[
              {"id": 1, "title": "The Pragmatic Programmer", "author": "David Thomas", "price": 49.99},
              {"id": 2, "title": "Clean Code", "author": "Robert C. Martin", "price": 39.99},
              {"id": 3, "title": "Designing Data-Intensive Applications", "author": "Martin Kleppmann", "price": 44.99},
              {"id": 4, "title": "Site Reliability Engineering", "author": "Google SRE Team", "price": 54.99},
              {"id": 5, "title": "Kubernetes in Action", "author": "Marko Luksa", "price": 59.99}
            ]';
        }

        location /api/health {
            default_type application/json;
            return 200 '{"status": "healthy", "service": "book-service"}';
        }

        location / {
            default_type application/json;
            return 404 '{"error": "not found"}';
        }
    }
  APP_ENV: "development"
  LOG_LEVEL: "debug"
```

```yaml
# base/book-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
  labels:
    app: book-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: book-service
  template:
    metadata:
      labels:
        app: book-service
    spec:
      containers:
        - name: book-service
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          env:
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: redis-password
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /api/health
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /api/health
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/conf.d/
      volumes:
        - name: nginx-config
          configMap:
            name: book-service-config
            items:
              - key: default.conf
                path: default.conf
```

```yaml
# base/book-service-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: book-service
  namespace: bookstore
spec:
  selector:
    app: book-service
  ports:
    - port: 80
      targetPort: 80
```

### Bước 5: API Gateway

```yaml
# base/api-gateway-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-gateway-config
  namespace: bookstore
data:
  default.conf: |
    upstream book_service {
        server book-service.bookstore.svc.cluster.local:80;
    }

    server {
        listen 8080;
        server_name _;

        location /api/ {
            proxy_pass http://book_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Request-ID $request_id;
            proxy_connect_timeout 5s;
            proxy_read_timeout 10s;
        }

        location /gateway/health {
            default_type application/json;
            return 200 '{"status": "healthy", "service": "api-gateway"}';
        }
    }
```

```yaml
# base/api-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
  labels:
    app: api-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: api-gateway
          image: nginx:1.25-alpine
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /gateway/health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /gateway/health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: nginx-config
              mountPath: /etc/nginx/conf.d/
      volumes:
        - name: nginx-config
          configMap:
            name: api-gateway-config
```

```yaml
# base/api-gateway-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: bookstore
spec:
  selector:
    app: api-gateway
  ports:
    - port: 8080
      targetPort: 8080
```

### Bước 6: Frontend

```yaml
# base/frontend-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-config
  namespace: bookstore
data:
  index.html: |
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>BookStore</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 0 20px; }
            h1 { color: #333; }
            .book { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .book h3 { margin: 0; color: #2196F3; }
            .book p { margin: 5px 0; color: #666; }
            .price { color: #4CAF50; font-weight: bold; }
            #status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .healthy { background: #e8f5e9; color: #2e7d32; }
            .error { background: #ffebee; color: #c62828; }
            button { background: #2196F3; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 5px; margin: 5px; }
            button:hover { background: #1976D2; }
        </style>
    </head>
    <body>
        <h1>BookStore - Kubernetes Demo</h1>
        <div>
            <button onclick="loadBooks()">Load Books</button>
            <button onclick="checkHealth()">Health Check</button>
        </div>
        <div id="status"></div>
        <div id="books"></div>
        <script>
            async function loadBooks() {
                try {
                    const res = await fetch('/api/books');
                    const books = await res.json();
                    document.getElementById('books').innerHTML = books.map(b =>
                        `<div class="book"><h3>${b.title}</h3><p>Author: ${b.author}</p><p class="price">$${b.price}</p></div>`
                    ).join('');
                    document.getElementById('status').className = 'healthy';
                    document.getElementById('status').textContent = `Loaded ${books.length} books`;
                } catch(e) {
                    document.getElementById('status').className = 'error';
                    document.getElementById('status').textContent = 'Error: ' + e.message;
                }
            }
            async function checkHealth() {
                try {
                    const res = await fetch('/api/health');
                    const data = await res.json();
                    document.getElementById('status').className = 'healthy';
                    document.getElementById('status').textContent = JSON.stringify(data);
                } catch(e) {
                    document.getElementById('status').className = 'error';
                    document.getElementById('status').textContent = 'Health check failed: ' + e.message;
                }
            }
        </script>
    </body>
    </html>
```

```yaml
# base/frontend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
  labels:
    app: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 30m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
          volumeMounts:
            - name: html
              mountPath: /usr/share/nginx/html/
      volumes:
        - name: html
          configMap:
            name: frontend-config
```

```yaml
# base/frontend-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: bookstore
spec:
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
```

### Bước 7: Ingress

```yaml
# base/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bookstore-ingress
  namespace: bookstore
spec:
  ingressClassName: nginx
  rules:
    - host: bookstore.local
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 8080
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

### Bước 8: Kustomization file

```yaml
# base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  # Redis (stateful)
  - redis-secret.yaml
  - redis-statefulset.yaml
  - redis-service.yaml
  # Book Service
  - book-service-configmap.yaml
  - book-service-deployment.yaml
  - book-service-service.yaml
  # API Gateway
  - api-gateway-configmap.yaml
  - api-gateway-deployment.yaml
  - api-gateway-service.yaml
  # Frontend
  - frontend-configmap.yaml
  - frontend-deployment.yaml
  - frontend-service.yaml
  # Ingress
  - ingress.yaml

commonLabels:
  app.kubernetes.io/part-of: bookstore
  managed-by: kustomize
```

### Bước 9: Dev Overlay

```yaml
# overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

commonLabels:
  env: dev

patches:
  - target:
      kind: Deployment
      name: api-gateway
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
  - target:
      kind: Deployment
      name: book-service
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
```

---

### Verification & Testing

### Deploy toàn bộ stack

```bash
# Preview trước
kubectl kustomize bookstore-k8s/overlays/dev

# Apply
kubectl apply -k bookstore-k8s/overlays/dev

# Đợi tất cả pods ready
kubectl wait --namespace bookstore \
  --for=condition=ready pod \
  --all \
  --timeout=120s

# Kiểm tra tổng quan
kubectl get all -n bookstore

# Expected output:
# NAME                             READY   STATUS    RESTARTS   AGE
# pod/api-gateway-xxx              1/1     Running   0          45s
# pod/book-service-xxx             1/1     Running   0          45s
# pod/frontend-xxx                 1/1     Running   0          45s
# pod/redis-0                      1/1     Running   0          45s
#
# NAME                   TYPE        CLUSTER-IP      PORT(S)    AGE
# service/api-gateway    ClusterIP   10.96.x.x       8080/TCP   45s
# service/book-service   ClusterIP   10.96.x.x       80/TCP     45s
# service/frontend       ClusterIP   10.96.x.x       80/TCP     45s
# service/redis          ClusterIP   None            6379/TCP   45s
```

### Test service-to-service communication

```bash
# Test book-service trực tiếp
kubectl exec -n bookstore deploy/api-gateway -- \
  curl -s http://book-service.bookstore.svc.cluster.local/api/books | head -20

# Test api-gateway → book-service
kubectl exec -n bookstore deploy/frontend -- \
  curl -s http://api-gateway.bookstore.svc.cluster.local:8080/api/books | head -20

# Test Redis
kubectl exec -n bookstore redis-0 -- \
  redis-cli -a bookstore-redis-pass ping
# Expected: PONG
```

### Test Ingress

```bash
# Thêm host vào /etc/hosts (Linux/macOS) hoặc C:\Windows\System32\drivers\etc\hosts (Windows)
echo "127.0.0.1 bookstore.local" | sudo tee -a /etc/hosts

# Test frontend
curl -s http://bookstore.local/
# Expected: HTML page

# Test API through Ingress
curl -s http://bookstore.local/api/books
# Expected: JSON array of books

# Test health
curl -s http://bookstore.local/api/health
# Expected: {"status": "healthy", "service": "book-service"}
```

### Verify PVC

```bash
# Kiểm tra PVC
kubectl get pvc -n bookstore
# Expected:
# NAME                STATUS   VOLUME     CAPACITY   ACCESS MODES   AGE
# redis-data-redis-0  Bound    pvc-xxx    1Gi        RWO            2m

# Ghi data vào Redis
kubectl exec -n bookstore redis-0 -- \
  redis-cli -a bookstore-redis-pass SET test-key "persistent-data"

# Xóa pod Redis (sẽ tự tạo lại nhờ StatefulSet)
kubectl delete pod redis-0 -n bookstore

# Đợi pod mới
kubectl wait --namespace bookstore \
  --for=condition=ready pod/redis-0 \
  --timeout=60s

# Kiểm tra data vẫn còn
kubectl exec -n bookstore redis-0 -- \
  redis-cli -a bookstore-redis-pass GET test-key
# Expected: "persistent-data"
```

### Verify ConfigMap hot-reload

```bash
# Kiểm tra ConfigMap
kubectl get cm -n bookstore
kubectl describe cm book-service-config -n bookstore
```

---

### Cleanup Script

```bash
#!/bin/bash
# cleanup.sh - Xóa toàn bộ BookStore stack

set -euo pipefail

echo "=== Cleaning up BookStore stack ==="

# Xóa Kustomize resources
echo "Deleting Kustomize resources..."
kubectl delete -k bookstore-k8s/overlays/dev --ignore-not-found=true 2>/dev/null || true

# Xóa PVC (không tự xóa khi delete StatefulSet)
echo "Deleting PVCs..."
kubectl delete pvc -n bookstore --all --ignore-not-found=true 2>/dev/null || true

# Xóa namespace (cleanup mọi thứ còn sót)
echo "Deleting namespace..."
kubectl delete namespace bookstore --ignore-not-found=true 2>/dev/null || true

# Đợi namespace xóa xong
echo "Waiting for namespace deletion..."
kubectl wait --for=delete namespace/bookstore --timeout=60s 2>/dev/null || true

echo "=== Cleanup complete ==="

# Optional: xóa kind cluster
# kind delete cluster --name bookstore
```

```bash
# Chạy cleanup
chmod +x cleanup.sh
./cleanup.sh
```

---

## 9. Common Pitfalls & Debugging

### Lỗi thường gặp khi deploy multi-service stack

| # | Lỗi | Nguyên nhân | Fix |
|---|------|-------------|-----|
| 1 | Pod `Pending` | Không đủ resources hoặc PVC không bind | `kubectl describe pod`, check events |
| 2 | Pod `CrashLoopBackOff` | Config sai, command fail | `kubectl logs <pod>`, check ConfigMap mount |
| 3 | Service không resolve | DNS chưa ready hoặc sai service name | `kubectl exec -- nslookup <service>` |
| 4 | Ingress 404 | Path rule sai hoặc Ingress Controller chưa ready | Check Ingress annotations, `kubectl describe ingress` |
| 5 | Ingress 502/503 | Backend pod chưa ready | Check readiness probe, `kubectl get endpoints` |
| 6 | Redis connection refused | Secret password sai hoặc headless service chưa ready | Check Secret, `redis-cli ping` |
| 7 | PVC Pending | StorageClass không tồn tại | `kubectl get sc`, kind tự có `standard` SC |

### Debug commands

```bash
# Tổng quan nhanh
kubectl get all -n bookstore
kubectl get events -n bookstore --sort-by='.lastTimestamp'

# Debug pod cụ thể
kubectl describe pod <pod-name> -n bookstore
kubectl logs <pod-name> -n bookstore
kubectl logs <pod-name> -n bookstore --previous  # logs từ crash trước

# Debug networking
kubectl exec -n bookstore deploy/api-gateway -- nslookup book-service
kubectl exec -n bookstore deploy/api-gateway -- curl -v http://book-service/api/health

# Debug Ingress
kubectl describe ingress bookstore-ingress -n bookstore
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | tail -20

# Debug PVC
kubectl describe pvc redis-data-redis-0 -n bookstore
kubectl get pv
```

---

### Self-review Checklist

### Kiến thức Phase 2 đã áp dụng

| Day | Topic | Áp dụng trong project |
|-----|-------|-----------------------|
| Day 8 | Docker Internals | Image selection (alpine), layer optimization |
| Day 9 | Image Security | Non-default images, resource limits |
| Day 10 | K8s Architecture | Declarative manifests, controller pattern |
| Day 11 | Workload Resources | Deployment (stateless), StatefulSet (stateful) |
| Day 12 | Networking | Service discovery, ClusterIP, headless service |
| Day 13 | Ingress | Path-based routing, Ingress Controller |
| Day 14 | ConfigMap/Secret | App config, Redis password |
| Day 15 | Storage | PVC cho Redis data persistence |
| Day 16 | Helm/Kustomize | Kustomize overlay cho environment management |

### Checklist

- [ ] Tối thiểu 3 services deploy thành công
- [ ] Ingress routing hoạt động (frontend + API)
- [ ] ConfigMap được mount và sử dụng đúng
- [ ] Secret được inject vào container
- [ ] PVC bound và data persist qua pod restart
- [ ] Health checks (readiness + liveness) configured
- [ ] Resource requests/limits set cho mọi container
- [ ] Service-to-service communication hoạt động
- [ ] Cleanup script xóa sạch resources
- [ ] Có thể debug và fix issues tự phát

---

## 10. Kết nối với bài trước & bài sau

### Phase 2 Summary

Qua 10 ngày (Day 8-17), bạn đã học và thực hành:
- Container internals và image optimization
- Kubernetes architecture và core concepts
- Workload resources, networking, Ingress
- Configuration management (ConfigMap, Secret, Storage)
- Package management (Helm, Kustomize)
- Và tổng hợp tất cả trong mini-project này

### Phase 3 Preview

Từ Day 18, bạn sẽ chuyển sang **Production Hardening**:
- **Day 18**: Resource requests/limits, QoS — optimize resources cho mỗi service trong stack này.
- **Day 19**: Autoscaling — thêm HPA cho api-gateway và book-service.
- **Day 20**: RBAC, NetworkPolicy — bảo mật communication giữa services.
- **Day 21**: Admission controllers — enforce policies (bắt buộc resource limits, cấm privileged).
- **Day 22**: Troubleshooting — debug production issues trên stack tương tự.
- **Day 25**: Mini-project Phase 3 — harden stack này thành production-ready.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Documentation - Tutorials](https://kubernetes.io/docs/tutorials/) — Official hands-on guides.
- [kind - Ingress Configuration](https://kind.sigs.k8s.io/docs/user/ingress/) — Setup Ingress trên kind.

### Nice-to-have

- [NGINX Ingress Annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/) — Full annotation reference.
- [Kubernetes Patterns (O'Reilly)](https://www.oreilly.com/library/view/kubernetes-patterns/9781492050278/) — Design patterns cho K8s applications.

### Deep-dive

- [12-Factor App](https://12factor.net/) — Principles cho cloud-native applications.
- [Microservices on Kubernetes (Google Cloud Blog)](https://cloud.google.com/blog/products/containers-kubernetes) — Real-world deployments.

