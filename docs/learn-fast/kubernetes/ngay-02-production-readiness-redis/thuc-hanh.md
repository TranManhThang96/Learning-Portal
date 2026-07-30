# Thực hành Ngày 2: Production Readiness và Redis

## Chuẩn bị

```bash
# Bật Ingress controller
minikube addons enable ingress

# Bật metrics-server (bắt buộc cho HPA)
minikube addons enable metrics-server

# Verify cả hai đã bật
minikube addons list | grep -E "ingress|metrics-server"

# Verify ingress-nginx controller Pod đang Running (có thể mất 30-60s)
kubectl get pods -n ingress-nginx

# Verify metrics-server có dữ liệu (có thể mất 1-2 phút để có số liệu)
kubectl top nodes
kubectl top pods
```

Nếu `kubectl top` trả lỗi "metrics not available yet", đợi thêm 1-2 phút rồi thử lại.

---

## Bài 1 (Beginner): Thêm probes và resource limits vào Deployment

**Mục tiêu:** Hiểu cách probe ảnh hưởng đến trạng thái Pod, quan sát hậu quả khi probe fail.

**Yêu cầu:** Đã có app từ Ngày 1 (hoặc dùng image mẫu `nginx` để thực hành cấu trúc YAML).

**Các bước:**

1. Tạo file `deployment-app.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: my-app
          image: nginx:1.27
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
            failureThreshold: 2
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "128Mi"
```

2. Apply và kiểm tra:

```bash
kubectl apply -f deployment-app.yaml
kubectl get pods -l app=my-app
kubectl describe pod -l app=my-app
```

3. Thử cố tình làm readiness probe fail: sửa `path: /khong-ton-tai` trong readinessProbe, apply lại, rồi quan sát:

```bash
kubectl apply -f deployment-app.yaml
kubectl get pods -l app=my-app -w
# Quan sát cột READY: 0/1 nghĩa là Pod Running nhưng không nhận traffic
kubectl describe pod -l app=my-app
# Tìm phần Events: sẽ thấy "Readiness probe failed"
```

4. Sửa lại path đúng (`/`) và apply lại để phục hồi.

**Kết quả mong đợi:**
- Khi readiness probe fail: Pod ở trạng thái `Running` nhưng `READY 0/1`, bị loại khỏi Service Endpoints.
- Khi readiness probe đúng: Pod chuyển `READY 1/1` sau vài giây.
- `kubectl describe pod` hiển thị Events cảnh báo probe failed.

**Kiến thức luyện tập:** Phân biệt Pod "Running" với Pod "Ready"; đọc Events trong `kubectl describe` để debug probe.

Checklist:
- [ ] Deployment với readiness + liveness probe đã apply thành công
- [ ] Quan sát được Pod READY 0/1 khi probe fail
- [ ] Đọc được Events trong kubectl describe
- [ ] Resource requests/limits đã cấu hình

---

## Bài 2 (Practical): Deploy Redis, kết nối app, tạo Ingress đa path

**Mục tiêu:** Deploy Redis làm cache, kết nối app tới Redis qua Service DNS, expose 2 app qua 1 Ingress.

**Yêu cầu:** Đã hoàn thành Bài 1, có 2 app (hoặc dùng `nginx` demo làm app1/app2 để tập trung vào routing).

**Các bước:**

1. Tạo `redis.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
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
          image: redis:7.4-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "128Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

> Lưu ý: đây là Deployment đơn giản cho mục đích học. Production nên dùng StatefulSet (nếu tự host, cần volume + định danh ổn định) hoặc managed Redis.

2. Apply và test Redis:

```bash
kubectl apply -f redis.yaml
kubectl get pods -l app=redis
kubectl exec -it deploy/redis -- redis-cli PING
# Kết quả mong đợi: PONG
```

3. App kết nối Redis qua DNS nội bộ: trong code app, dùng host `redis` (tên Service), port `6379`, ví dụ connection string `redis:6379`. Vì Service và app cùng namespace, DNS ngắn `redis` đủ dùng (không cần FQDN đầy đủ).

4. Tạo 2 Service demo (app1, app2) nếu chưa có:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app1-service
spec:
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: app2-service
spec:
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 80
```

5. Tạo `ingress.yaml`:

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

6. Apply và truy cập:

```bash
kubectl apply -f ingress.yaml
kubectl get ingress

# Mở tunnel để truy cập từ máy host (chạy ở terminal riêng, giữ chạy)
minikube tunnel

# Ở terminal khác, lấy IP Ingress rồi test
kubectl get ingress app-ingress
curl http://<INGRESS-IP>/app1
curl http://<INGRESS-IP>/app2
```

**Kết quả mong đợi:**
- `redis-cli PING` trả về `PONG`.
- `curl /app1` và `curl /app2` trả response từ đúng Service tương ứng, qua cùng 1 Ingress IP.

**Kiến thức luyện tập:** Service DNS nội bộ cho kết nối giữa Pod; Ingress định tuyến theo path tới nhiều Service; vai trò `minikube tunnel` để expose LoadBalancer/Ingress trên môi trường local.

Checklist:
- [ ] Redis Deployment + Service chạy thành công, PING trả PONG
- [ ] App cấu hình kết nối Redis qua DNS `redis:6379`
- [ ] Ingress route đúng 2 path tới 2 Service
- [ ] Truy cập thành công qua minikube tunnel

---

## Bài 3 (Advanced/Differentiating): HPA và OOMKilled

**Mục tiêu:** Thấy HPA tự scale theo tải thực tế, và hiểu hậu quả khi memory limit quá thấp.

**Yêu cầu:** Đã hoàn thành Bài 1, metrics-server đã bật (phần Chuẩn bị).

### Phần A: HPA autoscale theo CPU

1. Tạo HPA cho `my-app`:

```bash
kubectl autoscale deployment my-app --cpu-percent=50 --min=1 --max=5
kubectl get hpa my-app -w
```

2. Tạo tải giả để đẩy CPU lên:

```bash
kubectl run load-generator --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://my-app-service; done"
```

(Cần Service `my-app-service` trỏ tới Deployment `my-app` nếu chưa có, tạo tương tự Bài 2 bước 4.)

3. Quan sát:

```bash
kubectl get hpa my-app -w
kubectl get pods -l app=my-app -w
```

4. Dọn dẹp sau khi quan sát xong:

```bash
kubectl delete pod load-generator
kubectl delete hpa my-app
```

**Kết quả mong đợi:** Cột `TARGETS` trong `kubectl get hpa` tăng lên, số `REPLICAS` tăng theo (tối đa 5) khi CPU vượt 50%, và giảm dần về `min=1` sau khi tải giả bị xóa và CPU hạ nhiệt (thường vài phút do có cooldown).

### Phần B: Cố tình gây OOMKilled

1. Tạo `oom-test.yaml` với memory limit rất thấp:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: oom-test
spec:
  containers:
    - name: oom-test
      image: polinux/stress
      resources:
        requests:
          memory: "20Mi"
        limits:
          memory: "20Mi"
      command: ["stress"]
      args: ["--vm", "1", "--vm-bytes", "50M", "--vm-hang", "1"]
  restartPolicy: Never
```

2. Apply và quan sát:

```bash
kubectl apply -f oom-test.yaml
kubectl get pod oom-test -w
# Quan sát STATUS chuyển sang OOMKilled
kubectl describe pod oom-test
# Tìm phần "Last State: Terminated, Reason: OOMKilled"
```

3. Dọn dẹp:

```bash
kubectl delete pod oom-test
```

**Giải thích:** Container `stress` cố cấp phát 50Mi RAM nhưng limit chỉ 20Mi. Kernel OOM killer trong cgroup của container kill process ngay khi vượt limit memory — khác hoàn toàn với CPU, chỉ bị throttle (chậm lại) mà không bị kill.

**Kết quả mong đợi:** `kubectl describe pod oom-test` hiển thị `Reason: OOMKilled` trong phần Last State.

**Kiến thức luyện tập:** Cách đọc HPA target/replicas theo thời gian thực; phân biệt rõ ràng bằng thực nghiệm giữa throttle (CPU) và OOMKilled (memory).

Checklist:
- [ ] HPA tạo thành công, quan sát được replicas tăng khi có tải
- [ ] Replicas giảm về min sau khi xóa tải giả
- [ ] Tái tạo được OOMKilled và đọc được Reason trong kubectl describe
- [ ] Giải thích được sự khác biệt throttle vs OOMKilled bằng lời của mình

---

⬅️ [bai-hoc.md](./bai-hoc.md) | [tai-lieu.md](./tai-lieu.md)
