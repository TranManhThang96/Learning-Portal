# Bài thực hành - Day 17: Ingress và Ingress controllers

## Prerequisites

- K3s cluster đang chạy, khuyến nghị dùng default Traefik cho lab này.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Máy local có `curl`.
- Có `openssl` nếu làm phần TLS.

## Timebox và shell notes

- Core Path: Task 1-4, khoảng 100 phút. Đây là phần bắt buộc để hiểu Ingress controller, host/path routing và debug backend 503.
- Optional: TLS self-signed và controller logs/events nếu bạn còn thời gian hoặc cần đào sâu controller cụ thể.
- Các command dùng cú pháp Bash/WSL. Với PowerShell, thay `grep -E` bằng `Select-String -Pattern` hoặc dùng `kubectl get ... -o wide` rồi lọc thủ công.
- Lab dùng K3s Traefik làm default. Nếu controller của bạn không phải Traefik, đổi `ingressClassName`, namespace và Service port-forward tương ứng.

## Lab Scenario

Bạn expose hai backend nội bộ qua một entrypoint HTTP bằng Ingress: `/web` route tới `web` service, `/api` route tới `api` service. Core lab inject lỗi backend Service sai tên để debug. TLS self-signed là optional vì phụ thuộc `openssl`, controller TLS config và port-forward 443.

## Task 1: Kiểm tra Ingress controller hiện có (20 phút)

### Mục tiêu

Xác định controller và `IngressClass` trước khi viết manifest.

### Các bước thực hiện

```bash
kubectl get ingressclass
kubectl -n kube-system get pods,svc | grep -E 'traefik|ingress|nginx|haproxy'
kubectl get svc -A | grep -E 'traefik|ingress|nginx|haproxy'
```

Nếu dùng K3s mặc định, thường thấy:

- `IngressClass` tên `traefik`.
- Service `traefik` trong namespace `kube-system`.

Nếu cluster không có Ingress controller, dừng lab và cài controller phù hợp trước. Tạo Ingress object mà không có controller sẽ không route traffic.

## Task 2: Tạo namespace, web và api backend (25 phút)

### Mục tiêu

Tạo 2 backend nội bộ bằng `ClusterIP` Service.

### Các bước thực hiện

```bash
kubectl create namespace day17
kubectl config set-context --current --namespace=day17
```

Tạo file `apps.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          echo "web root from $HOSTNAME" > /www/index.html
          echo "web path from $HOSTNAME" > /www/web
          httpd -f -p 8080 -h /www
        ports:
        - name: http
          containerPort: 8080
        readinessProbe:
          httpGet:
            path: /web
            port: http
          initialDelaySeconds: 2
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          mkdir -p /www
          echo "api root from $HOSTNAME" > /www/index.html
          echo "api path from $HOSTNAME" > /www/api
          httpd -f -p 8080 -h /www
        ports:
        - name: http
          containerPort: 8080
        readinessProbe:
          httpGet:
            path: /api
            port: http
          initialDelaySeconds: 2
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply:

```bash
kubectl apply -f apps.yaml
kubectl rollout status deployment/web
kubectl rollout status deployment/api
kubectl get pods,svc,endpoints
```

### Expected output

- 2 Pods `web` và 2 Pods `api` Ready.
- Services `web` và `api` có endpoints.

## Task 3: Tạo Ingress host/path routing (30 phút)

### Mục tiêu

Route một host tới nhiều backend theo path.

### Các bước thực hiện

Tạo file `ingress.yaml`. Nếu `kubectl get ingressclass` trả về class khác `traefik`, đổi `ingressClassName` tương ứng.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: day17-app
spec:
  ingressClassName: traefik
  rules:
  - host: day17.local
    http:
      paths:
      - path: /web
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 8080
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8080
```

Apply:

```bash
kubectl apply -f ingress.yaml
kubectl get ingress -o wide
kubectl describe ingress day17-app
```

Port-forward Traefik ở terminal riêng:

```bash
kubectl -n kube-system port-forward svc/traefik 8080:80
```

Test từ terminal khác:

```bash
curl -H 'Host: day17.local' http://127.0.0.1:8080/web
curl -H 'Host: day17.local' http://127.0.0.1:8080/api
curl -H 'Host: wrong.local' http://127.0.0.1:8080/web
```

### Expected output

- `/web` trả về `web path from ...`.
- `/api` trả về `api path from ...`.
- Host sai thường trả 404.

### Path rewrite caveat

Lab này cố ý để backend phục vụ đúng `/web` và `/api`. `pathType: Prefix` thường forward nguyên path tới backend; nó không tự strip `/api` thành `/`. Nếu backend chỉ phục vụ `/`, bạn cần rewrite/middleware controller-specific hoặc sửa backend base path.

## Task 4: Inject lỗi backend Service sai tên (25 phút)

### Mục tiêu

Phân biệt route match nhưng backend fail.

### Lỗi cần tạo

```bash
kubectl patch ingress day17-app --type=json -p='[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"web-missing"}]'
kubectl describe ingress day17-app
```

Test:

```bash
curl -i -H 'Host: day17.local' http://127.0.0.1:8080/web
curl -i -H 'Host: day17.local' http://127.0.0.1:8080/api
kubectl get svc,endpoints,endpointslice
```

### Symptom

- `/api` vẫn hoạt động.
- `/web` thường trả 503 hoặc lỗi upstream vì Service backend không tồn tại.

### Cách fix

```bash
kubectl patch ingress day17-app --type=json -p='[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"web"}]'
curl -H 'Host: day17.local' http://127.0.0.1:8080/web
```

## Optional Deep Dive: Thêm TLS self-signed (30 phút)

### Mục tiêu

Hiểu TLS termination tại Ingress controller.

### Các bước thực hiện

Tạo cert self-signed:

```bash
openssl req -x509 -nodes -days 1 -newkey rsa:2048 -keyout day17.key -out day17.crt -subj "/CN=day17.local/O=day17"
kubectl create secret tls day17-tls --cert=day17.crt --key=day17.key
```

Tạo file `ingress-tls.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: day17-app
spec:
  ingressClassName: traefik
  tls:
  - hosts:
    - day17.local
    secretName: day17-tls
  rules:
  - host: day17.local
    http:
      paths:
      - path: /web
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 8080
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 8080
```

Apply:

```bash
kubectl apply -f ingress-tls.yaml
kubectl describe ingress day17-app
```

Port-forward HTTPS ở terminal riêng:

```bash
kubectl -n kube-system port-forward svc/traefik 8443:443
```

Test:

```bash
curl -k --resolve day17.local:8443:127.0.0.1 https://day17.local:8443/web
curl -k --resolve day17.local:8443:127.0.0.1 https://day17.local:8443/api
```

### Expected output

- HTTPS request được terminate ở Traefik.
- Backend vẫn nhận HTTP nội bộ qua Service.

## Optional Deep Dive: Đọc logs controller và events (15 phút)

### Mục tiêu

Biết nơi kiểm tra khi route không apply.

### Các bước thực hiện

```bash
kubectl describe ingress day17-app
kubectl get events --sort-by=.lastTimestamp
kubectl -n kube-system logs deploy/traefik --tail=100
```

Nếu dùng controller khác, đổi namespace/deployment tương ứng.

## Cleanup

```bash
kubectl delete namespace day17
kubectl config set-context --current --namespace=default
```

Xóa file cert local nếu không cần giữ:

```bash
rm -f day17.key day17.crt
```

PowerShell tương đương:

```powershell
Remove-Item -Force .\day17.key, .\day17.crt -ErrorAction SilentlyContinue
```

## Common Pitfalls

- Tạo Ingress nhưng không có Ingress controller.
- `ingressClassName` sai hoặc thiếu trong cluster có nhiều controller.
- Curl không set Host header nên route không match.
- Backend Service không có endpoints nhưng chỉ nhìn Ingress.
- Dùng annotation của NGINX trên Traefik.
- Test HTTPS với IP trực tiếp nên SNI không match host.
- Quên rằng TLS Secret phải nằm cùng namespace với Ingress.

## Stretch Goals

- Thêm path `/exact` với `pathType: Exact` và so sánh `/exact` với `/exact/foo`.
- Thêm một host thứ hai `api.day17.local`.
- So sánh response/log khi backend Pod scale về 0.
- Nếu có `cert-manager`, thay self-signed manual bằng Certificate resource trong lab riêng.
- Thử rewrite prefix bằng Traefik Middleware hoặc NGINX annotation trong cluster riêng, rồi ghi rõ manifest đó không portable giữa controller.
