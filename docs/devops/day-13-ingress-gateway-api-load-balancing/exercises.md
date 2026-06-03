# Day 13: Bài tập — Ingress, Gateway API & Load Balancing

---

## Bài 1: Easy — Path-based Routing với NGINX Ingress

### Context
Bạn cần expose 2 services (API và Web) qua cùng 1 Ingress endpoint, routing dựa trên URL path.

### Yêu cầu
1. Deploy `api-service` (image: `hashicorp/http-echo:0.2.3`, text: "API Response", port 5678).
2. Deploy `web-service` (image: `nginx:1.25-alpine`, port 80).
3. Tạo ClusterIP service cho mỗi deployment.
4. Tạo Ingress resource:
   - `/api` → `api-service`
   - `/web` → `web-service`
5. Test routing bằng curl.
6. Verify bằng `kubectl describe ingress`.

### Expected Outcome
- `curl http://localhost/api` trả về "API Response".
- `curl http://localhost/web` trả về NGINX default page.
- `kubectl describe ingress` hiển thị rules đúng.

### Hints
- Cần NGINX Ingress Controller đã cài sẵn (xem hands-on trong lesson).
- Dùng annotation `nginx.ingress.kubernetes.io/rewrite-target: /` để strip path prefix.
- pathType: `Prefix`.

### Acceptance Criteria
- [ ] 2 deployments và services tạo thành công
- [ ] Ingress routing `/api` → api-service hoạt động
- [ ] Ingress routing `/web` → web-service hoạt động
- [ ] Ingress describe hiển thị rules đúng

### Bonus Challenge
- Thêm default backend cho path không match (404 custom page).
- Thêm annotation rate limiting: `nginx.ingress.kubernetes.io/limit-rps: "5"`.

<details>
<summary>Solution</summary>

```yaml
# easy-ingress.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      containers:
        - name: api
          image: hashicorp/http-echo:0.2.3
          args: ["-text=API Response", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api-svc
spec:
  selector:
    app: api-service
  ports:
    - port: 80
      targetPort: 5678
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-service
  template:
    metadata:
      labels:
        app: web-service
    spec:
      containers:
        - name: web
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web-service
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-routing-exercise
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api-svc
                port:
                  number: 80
          - path: /web
            pathType: Prefix
            backend:
              service:
                name: web-svc
                port:
                  number: 80
```

```bash
kubectl apply -f easy-ingress.yaml
kubectl wait --for=condition=Ready pod -l app=api-service --timeout=60s
kubectl wait --for=condition=Ready pod -l app=web-service --timeout=60s

curl http://localhost/api
curl http://localhost/web
kubectl describe ingress path-routing-exercise

# Cleanup
kubectl delete -f easy-ingress.yaml
```

</details>

---

## Bài 2: Medium — Host-based Routing với TLS

### Context
Bạn cần expose 2 ứng dụng qua 2 domain khác nhau, cả hai đều có HTTPS với self-signed certificates.

### Yêu cầu
1. Deploy `blog-app` (http-echo, text: "Blog App") và `store-app` (http-echo, text: "Store App").
2. Tạo ClusterIP service cho mỗi app.
3. Tạo 2 self-signed TLS certificates:
   - `blog.local.dev`
   - `store.local.dev`
4. Tạo Kubernetes TLS secrets cho mỗi cert.
5. Tạo Ingress với:
   - Host `blog.local.dev` → blog-app, TLS enabled.
   - Host `store.local.dev` → store-app, TLS enabled.
   - HTTP → HTTPS redirect enabled.
6. Test cả HTTP redirect và HTTPS access.

### Expected Outcome
- `curl -k --resolve blog.local.dev:443:127.0.0.1 --noproxy blog.local.dev https://blog.local.dev` → "Blog App".
- `curl -k --resolve store.local.dev:443:127.0.0.1 --noproxy store.local.dev https://store.local.dev` → "Store App".
- HTTP requests redirect sang HTTPS.

### Hints
- `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout blog.key -out blog.crt -subj "/CN=blog.local.dev" -addext "subjectAltName=DNS:blog.local.dev"`.
- `kubectl create secret tls blog-tls --cert=blog.crt --key=blog.key`.
- Annotation: `nginx.ingress.kubernetes.io/ssl-redirect: "true"`.
- Khi test TLS local, dùng `--resolve` thay vì chỉ set `Host` header; TLS certificate được chọn theo SNI trước khi HTTP header được gửi.

### Acceptance Criteria
- [ ] 2 apps deploy thành công
- [ ] TLS secrets tạo đúng
- [ ] Host-based routing hoạt động
- [ ] HTTPS access thành công
- [ ] HTTP redirect đến HTTPS
- [ ] Cert subject đúng domain

### Bonus Challenge
- Dùng 1 Ingress resource với multiple hosts thay vì 2 Ingress riêng.
- Kiểm tra certificate details: `curl -kv --resolve blog.local.dev:443:127.0.0.1 --noproxy blog.local.dev https://blog.local.dev 2>&1 | grep "subject:"`.

<details>
<summary>Solution</summary>

```bash
# Create certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout blog.key -out blog.crt -subj "/CN=blog.local.dev" -addext "subjectAltName=DNS:blog.local.dev"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout store.key -out store.crt -subj "/CN=store.local.dev" -addext "subjectAltName=DNS:store.local.dev"

kubectl create secret tls blog-tls --cert=blog.crt --key=blog.key
kubectl create secret tls store-tls --cert=store.crt --key=store.key
```

```yaml
# medium-ingress.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: blog-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: blog-app
  template:
    metadata:
      labels:
        app: blog-app
    spec:
      containers:
        - name: blog
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Blog App", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: blog-svc
spec:
  selector:
    app: blog-app
  ports:
    - port: 80
      targetPort: 5678
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: store-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: store-app
  template:
    metadata:
      labels:
        app: store-app
    spec:
      containers:
        - name: store
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Store App", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: store-svc
spec:
  selector:
    app: store-app
  ports:
    - port: 80
      targetPort: 5678
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: multi-host-tls
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - blog.local.dev
      secretName: blog-tls
    - hosts:
        - store.local.dev
      secretName: store-tls
  rules:
    - host: blog.local.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: blog-svc
                port:
                  number: 80
    - host: store.local.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: store-svc
                port:
                  number: 80
```

```bash
kubectl apply -f medium-ingress.yaml
kubectl wait --for=condition=Ready pod -l app=blog-app --timeout=60s
kubectl wait --for=condition=Ready pod -l app=store-app --timeout=60s

# Test HTTPS
curl -k --resolve blog.local.dev:443:127.0.0.1 --noproxy blog.local.dev https://blog.local.dev
curl -k --resolve store.local.dev:443:127.0.0.1 --noproxy store.local.dev https://store.local.dev

# Test HTTP redirect
curl -I --resolve blog.local.dev:80:127.0.0.1 --noproxy blog.local.dev http://blog.local.dev

# Check cert
curl -kv --resolve blog.local.dev:443:127.0.0.1 --noproxy blog.local.dev https://blog.local.dev 2>&1 | grep "subject:"

# Cleanup
kubectl delete -f medium-ingress.yaml
kubectl delete secret blog-tls store-tls
rm -f blog.key blog.crt store.key store.crt
```

</details>

---

## Bài 3: Hard — Production Ingress Architecture

### Context
Bạn là DevOps engineer cần thiết kế và triển khai Ingress architecture cho một ứng dụng production-like gồm:
- Public API (`api.app.local`)
- Admin dashboard (`admin.app.local`)
- Monitoring endpoint (`/healthz` trên mỗi service)

Lab này dùng NGINX annotations để bạn hiểu một legacy pattern rất phổ biến. Trong production mới sau 03/2026, architecture decision phải nêu rõ migration path sang Gateway API hoặc một controller còn maintained.

### Yêu cầu
1. Deploy 3 services: `public-api`, `admin-dashboard`, `health-checker`.
2. Tạo Ingress cho public traffic:
   - `api.app.local/v1` → public-api
   - `api.app.local/v2` → public-api (different deployment/version)
   - Rate limiting: 10 RPS
   - TLS enabled
3. Tạo Ingress riêng cho admin traffic:
   - `admin.app.local` → admin-dashboard
   - IP whitelist: chỉ cho phép `10.0.0.0/8`
   - TLS enabled
4. Thêm custom error pages (502, 503, 504).
5. Cấu hình các annotations hữu ích: timeouts, buffer sizes, CORS.
6. Document lại architecture decision.

### Expected Outcome
- Public API accessible với rate limiting.
- Admin dashboard restricted by IP.
- TLS hoạt động trên cả 2 domains.
- Custom annotations đúng cấu hình.
- Architecture decision nêu rõ NGINX annotations là legacy/local-lab choice và đề xuất hướng Gateway API/maintained controller cho production.

### Hints
- Rate limit: `nginx.ingress.kubernetes.io/limit-rps`.
- IP whitelist: `nginx.ingress.kubernetes.io/whitelist-source-range`.
- Timeout: `nginx.ingress.kubernetes.io/proxy-read-timeout`.
- CORS: `nginx.ingress.kubernetes.io/enable-cors`.

### Acceptance Criteria
- [ ] 3 services deploy thành công
- [ ] Path-based routing cho API v1/v2 hoạt động
- [ ] Host-based routing cho admin hoạt động
- [ ] Rate limiting configured
- [ ] IP whitelist configured
- [ ] TLS trên cả 2 domains
- [ ] Timeout annotations set
- [ ] Architecture document viết xong
- [ ] Có migration note sang Gateway API hoặc controller còn maintained

### Bonus Challenge
- Tạo HPA cho NGINX Ingress Controller pods.
- Tạo PodDisruptionBudget cho IC.
- Thêm Prometheus annotations để scrape IC metrics.
- So sánh hiệu năng giữa 1 IC replica và 3 IC replicas bằng cách dùng `hey` hoặc `k6`.

<details>
<summary>Solution</summary>

```bash
# Generate TLS certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout api.key -out api.crt -subj "/CN=api.app.local" -addext "subjectAltName=DNS:api.app.local"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout admin.key -out admin.crt -subj "/CN=admin.app.local" -addext "subjectAltName=DNS:admin.app.local"
kubectl create secret tls api-tls --cert=api.crt --key=api.key
kubectl create secret tls admin-tls --cert=admin.crt --key=admin.key
```

```yaml
# hard-ingress.yaml
# --- Public API v1 ---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: public-api-v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: public-api
      version: v1
  template:
    metadata:
      labels:
        app: public-api
        version: v1
    spec:
      containers:
        - name: api
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Public API v1", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: public-api-v1-svc
spec:
  selector:
    app: public-api
    version: v1
  ports:
    - port: 80
      targetPort: 5678
---
# --- Public API v2 ---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: public-api-v2
spec:
  replicas: 2
  selector:
    matchLabels:
      app: public-api
      version: v2
  template:
    metadata:
      labels:
        app: public-api
        version: v2
    spec:
      containers:
        - name: api
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Public API v2", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: public-api-v2-svc
spec:
  selector:
    app: public-api
    version: v2
  ports:
    - port: 80
      targetPort: 5678
---
# --- Admin Dashboard ---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: admin-dashboard
spec:
  replicas: 1
  selector:
    matchLabels:
      app: admin-dashboard
  template:
    metadata:
      labels:
        app: admin-dashboard
    spec:
      containers:
        - name: admin
          image: hashicorp/http-echo:0.2.3
          args: ["-text=Admin Dashboard", "-listen=:5678"]
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: admin-svc
spec:
  selector:
    app: admin-dashboard
  ports:
    - port: 80
      targetPort: 5678
---
# --- Public Ingress ---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: public-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/limit-rps: "10"
    nginx.ingress.kubernetes.io/limit-burst-multiplier: "3"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.local"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.app.local
      secretName: api-tls
  rules:
    - host: api.app.local
      http:
        paths:
          - path: /v1
            pathType: Prefix
            backend:
              service:
                name: public-api-v1-svc
                port:
                  number: 80
          - path: /v2
            pathType: Prefix
            backend:
              service:
                name: public-api-v2-svc
                port:
                  number: 80
---
# --- Admin Ingress ---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: admin-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,127.0.0.1/32"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - admin.app.local
      secretName: admin-tls
  rules:
    - host: admin.app.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-svc
                port:
                  number: 80
```

```bash
kubectl apply -f hard-ingress.yaml

# Test public API
curl -k --resolve api.app.local:443:127.0.0.1 --noproxy api.app.local https://api.app.local/v1
curl -k --resolve api.app.local:443:127.0.0.1 --noproxy api.app.local https://api.app.local/v2

# Test admin (will be 403 if not from 10.0.0.0/8)
curl -k --resolve admin.app.local:443:127.0.0.1 --noproxy admin.app.local https://admin.app.local

# Verify rate limiting (rapid requests)
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" -k --resolve api.app.local:443:127.0.0.1 --noproxy api.app.local https://api.app.local/v1
done

# Verify config
kubectl describe ingress public-ingress
kubectl describe ingress admin-ingress

# Cleanup
kubectl delete -f hard-ingress.yaml
kubectl delete secret api-tls admin-tls
rm -f api.key api.crt admin.key admin.crt
```

</details>

