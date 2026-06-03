# Day 44 Document: Capstone Architecture Spec

## Target architecture

```text
Client
  |
  v
Ingress: logistics.local
  |
  v
api-gateway:80
  |
  +-- order-service:80
  +-- tracking-service:80
  +-- notification-service:80
```

## Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: logistics
  labels:
    app.kubernetes.io/part-of: logistics-platform
```

## Service catalog

| Service | Exposure | Role | Day 44 state |
|---|---|---|---|
| `api-gateway` | Ingress -> ClusterIP | Edge routing | Required |
| `order-service` | ClusterIP only | Order API | Required |
| `tracking-service` | ClusterIP only | Tracking API | Required |
| `notification-service` | ClusterIP only | Notification API | Optional |
| PostgreSQL | ClusterIP/headless | Database | Day 45 |
| Redis | ClusterIP | Cache/session | Day 45 |
| Kafka | ClusterIP/headless | Event bus | Day 45 |

## Standard labels

```yaml
app.kubernetes.io/name: order-service
app.kubernetes.io/instance: logistics
app.kubernetes.io/part-of: logistics-platform
app.kubernetes.io/component: backend
app.kubernetes.io/managed-by: Helm
```

## Minimal Deployment template

Backend lab service:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: logistics
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: order-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: order-service
        app.kubernetes.io/part-of: logistics-platform
    spec:
      containers:
      - name: app
        image: hashicorp/http-echo:1.0
        args:
        - -listen=:8080
        - -text=order-service
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: 8080
        livenessProbe:
          httpGet:
            path: /
            port: 8080
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            memory: 128Mi
```

Gateway NGINX reverse proxy config:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-gateway-nginx
  namespace: logistics
data:
  default.conf: |
    server {
      listen 8080;

      location = /health {
        return 200 "ok\n";
      }

      location /orders {
        proxy_pass http://order-service:8080/;
      }

      location /tracking {
        proxy_pass http://tracking-service:8080/;
      }
    }
```

## Minimal Service template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: logistics
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: order-service
  ports:
  - name: http
    port: 8080
    targetPort: 8080
```

## Ingress template

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: logistics
  namespace: logistics
spec:
  rules:
  - host: logistics.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
```

Nếu dùng NGINX Ingress, có thể cần `ingressClassName: nginx`. K3s với Traefik thường có default IngressClass tùy cấu hình cluster.

## Helm values skeleton

```yaml
global:
  namespace: logistics
  partOf: logistics-platform

services:
  apiGateway:
    name: api-gateway
    image: nginxinc/nginx-unprivileged:1.25-alpine
    replicas: 2
    component: gateway
    containerPort: 8080
    env:
      ORDER_SERVICE_URL: http://order-service
      TRACKING_SERVICE_URL: http://tracking-service
  order:
    name: order-service
    image: hashicorp/http-echo:1.0
    replicas: 2
    component: backend
    text: order-service
  tracking:
    name: tracking-service
    image: hashicorp/http-echo:1.0
    replicas: 2
    component: backend
    text: tracking-service

ingress:
  enabled: true
  host: logistics.local
```

## Debug graph

```text
kubectl get ingress
  -> backend service name/port đúng?

kubectl get svc api-gateway
  -> selector đúng labels Pod?

kubectl get endpointslice
  -> có endpoint Ready?

kubectl logs deploy/api-gateway
  -> gateway có gọi backend đúng DNS?

kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
  -> gateway route và service discovery nội bộ OK?
```

## Architecture decision record mẫu

```markdown
# ADR: Expose only API Gateway

## Context
Hệ thống có nhiều microservices backend, nhưng client chỉ cần một public HTTP entrypoint.

## Decision
Chỉ expose `api-gateway` qua Ingress. Backend services dùng `ClusterIP`.

## Consequences
- Giảm public attack surface.
- Routing/auth/rate limit tập trung.
- API Gateway trở thành critical path, cần replicas, PDB, monitoring.
```

## Day 44 acceptance criteria

- [ ] Helm release `logistics` cài được và render được manifest hợp lệ.
- [ ] Namespace `logistics` tồn tại.
- [ ] `api-gateway`, `order-service`, `tracking-service` chạy Ready.
- [ ] Mỗi service có `Deployment` và `Service`.
- [ ] Gateway route `/orders` tới `order-service` và `/tracking` tới `tracking-service`.
- [ ] Gateway expose qua Ingress.
- [ ] Backend services chỉ dùng `ClusterIP`.
- [ ] Có ConfigMap/Secret tối thiểu.
- [ ] Có requests/probes và PDB tối thiểu.
- [ ] Debug được lỗi selector hoặc service name sai.
- [ ] Có README/ADR ghi trade-offs.
