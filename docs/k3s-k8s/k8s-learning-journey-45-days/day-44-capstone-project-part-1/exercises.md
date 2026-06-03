# Bài thực hành - Day 44: Capstone Project Part 1

## Prerequisites

- Kubernetes/K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- `helm` đã cài. Day 44 dùng Helm làm main path.
- Có Ingress controller. Với K3s thường là Traefik mặc định; với cluster khác cần NGINX/Traefik hoặc chỉ test bằng `Service`/port-forward.

## Lab Scenario

Bạn sẽ deploy stateless layer của hệ thống giao vận bằng một Helm chart nhỏ:

- `api-gateway` route thật `/orders` và `/tracking`.
- `order-service` và `tracking-service` là backend nội bộ.
- `Service`, `Ingress`, `ConfigMap`, `Secret`, probes, resources và PDB tối thiểu.

Core path khoảng 105-115 phút. Backend dùng `hashicorp/http-echo` để trả response khác nhau; gateway dùng NGINX non-root reverse proxy. Production có thể thay bằng service thật sau khi Kubernetes contract đã đúng.

## Task 1: Tạo Helm chart skeleton (15 phút)

```bash
mkdir -p logistics-stateless/templates
```

Tạo `logistics-stateless/Chart.yaml`:

```yaml
apiVersion: v2
name: logistics-stateless
description: Stateless layer for the logistics capstone
type: application
version: 0.1.0
appVersion: "0.1.0"
```

Tạo `logistics-stateless/values.yaml`:

```yaml
namespace: logistics
host: logistics.local
partOf: logistics-platform
```

## Task 2: Tạo templates cho gateway, backends, Ingress và PDB (35 phút)

Tạo `logistics-stateless/templates/all.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.namespace }}
  labels:
    app.kubernetes.io/part-of: {{ .Values.partOf }}
---
apiVersion: v1
kind: Secret
metadata:
  name: logistics-secret
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  API_TOKEN: lab-token-change-me
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-gateway-nginx
  namespace: {{ .Values.namespace }}
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
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: {{ .Values.namespace }}
  labels:
    app.kubernetes.io/name: api-gateway
    app.kubernetes.io/component: gateway
    app.kubernetes.io/part-of: {{ .Values.partOf }}
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api-gateway
        app.kubernetes.io/component: gateway
        app.kubernetes.io/part-of: {{ .Values.partOf }}
    spec:
      containers:
      - name: nginx
        image: nginxinc/nginx-unprivileged:1.25-alpine
        ports:
        - containerPort: 8080
        envFrom:
        - secretRef:
            name: logistics-secret
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            memory: 128Mi
        securityContext:
          runAsNonRoot: true
          runAsUser: 101
          runAsGroup: 101
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
        volumeMounts:
        - name: nginx-config
          mountPath: /etc/nginx/conf.d/default.conf
          subPath: default.conf
      volumes:
      - name: nginx-config
        configMap:
          name: api-gateway-nginx
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: {{ .Values.namespace }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: api-gateway
  ports:
  - name: http
    port: 80
    targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: {{ .Values.namespace }}
  labels:
    app.kubernetes.io/name: order-service
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: {{ .Values.partOf }}
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: order-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: order-service
        app.kubernetes.io/component: backend
        app.kubernetes.io/part-of: {{ .Values.partOf }}
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
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: {{ .Values.namespace }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: order-service
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tracking-service
  namespace: {{ .Values.namespace }}
  labels:
    app.kubernetes.io/name: tracking-service
    app.kubernetes.io/component: backend
    app.kubernetes.io/part-of: {{ .Values.partOf }}
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: tracking-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: tracking-service
        app.kubernetes.io/component: backend
        app.kubernetes.io/part-of: {{ .Values.partOf }}
    spec:
      containers:
      - name: app
        image: hashicorp/http-echo:1.0
        args:
        - -listen=:8080
        - -text=tracking-service
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
---
apiVersion: v1
kind: Service
metadata:
  name: tracking-service
  namespace: {{ .Values.namespace }}
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: tracking-service
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: logistics
  namespace: {{ .Values.namespace }}
spec:
  rules:
  - host: {{ .Values.host }}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-gateway
            port:
              number: 80
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway
  namespace: {{ .Values.namespace }}
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service
  namespace: {{ .Values.namespace }}
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: order-service
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tracking-service
  namespace: {{ .Values.namespace }}
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: tracking-service
```

## Task 3: Render, install và verify (20 phút)

```bash
helm lint ./logistics-stateless
helm template logistics ./logistics-stateless | head -n 40
helm upgrade --install logistics ./logistics-stateless --namespace logistics --create-namespace
kubectl rollout status deploy/api-gateway -n logistics
kubectl rollout status deploy/order-service -n logistics
kubectl rollout status deploy/tracking-service -n logistics
kubectl get deploy,svc,pdb,pod -n logistics
kubectl get endpointslice -n logistics
```

### Expected output

- 3 Deployment đều rollout thành công.
- `api-gateway`, `order-service`, `tracking-service` đều có Service.
- `EndpointSlice` có endpoint Ready cho từng Service.
- PDB tồn tại cho gateway và backends.

## Task 4: Test routing bằng debug Pod riêng (20 phút)

Không exec vào NGINX gateway để giả định có `wget/curl`. Dùng debug Pod riêng:

```bash
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/tracking
```

### Expected output

```text
order-service
tracking-service
```

Nếu muốn test từ máy local:

```bash
kubectl port-forward svc/api-gateway -n logistics 8080:80
curl http://localhost:8080/orders
curl http://localhost:8080/tracking
```

## Task 5: Expose qua Ingress (15 phút)

```bash
kubectl get ingress -n logistics
kubectl describe ingress logistics -n logistics
```

Nếu Ingress controller expose local endpoint, thêm host mapping phù hợp rồi test:

```bash
curl -H "Host: logistics.local" http://<ingress-address>/orders
curl -H "Host: logistics.local" http://<ingress-address>/tracking
```

Nếu cluster chưa có Ingress controller, ghi rõ blocker và giữ port-forward test làm evidence.

## Task 6: Inject lỗi selector và debug (20 phút)

Patch Service selector sai:

```bash
kubectl patch svc order-service -n logistics --type merge -p '{"spec":{"selector":{"app.kubernetes.io/name":"order-service-wrong"}}}'
kubectl get endpointslice -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl describe svc order-service -n logistics
```

### Expected output

- `order-service` không còn endpoint Ready.
- Gateway trả lỗi proxy như `502 Bad Gateway` hoặc request timeout.
- Evidence nằm ở Service selector/EndpointSlice trước khi cần xem app logs.

Khôi phục:

```bash
kubectl patch svc order-service -n logistics --type merge -p '{"spec":{"selector":{"app.kubernetes.io/name":"order-service"}}}'
kubectl get endpointslice -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
```

## Task 7: Viết README capstone Part 1 (10 phút)

Tạo `capstone-readme.md`:

```markdown
# Logistics Capstone - Part 1

## Architecture

## Helm release

## Services

## Traffic flow

## Why only API Gateway is public

## Debug evidence

## Known gaps for Day 45
```

## Cleanup

Nếu muốn tiếp tục Day 45, giữ release `logistics`.

Nếu muốn xóa:

```bash
helm uninstall logistics -n logistics
kubectl delete namespace logistics
```

## Common Pitfalls

- Ingress tồn tại nhưng không có Ingress controller.
- Service selector không khớp label Pod.
- Gateway chỉ trả default page và không proxy tới backend thật.
- Dùng `kubectl exec` vào image production rồi giả định có debug tools.
- Readiness probe sai path/port làm Service không có Ready endpoints.
- Dùng Secret plaintext trong Git và tưởng là an toàn.

## Stretch Goals

- Tách chart tổng thành reusable chart per service.
- Thay `hashicorp/http-echo` bằng service thật có `/health`, `/ready`, `/orders`, `/tracking`.
- Thêm NetworkPolicy chỉ cho phép API Gateway gọi backend.
- Thêm values cho image tag, replicas, resources và ingress class.
