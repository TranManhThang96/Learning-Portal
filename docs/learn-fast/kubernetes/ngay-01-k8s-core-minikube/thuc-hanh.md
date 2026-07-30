# Ngày 1 — Thực hành: Kubernetes Core & Minikube

## Chuẩn bị

### Bước 1: Cài Docker

Docker là container runtime dùng làm driver cho Minikube.

- Linux: cài theo hướng dẫn chính thức tại https://docs.docker.com/engine/install/
- Sau khi cài, kiểm tra:

```bash
docker --version
```

**Kết quả mong đợi**: in ra version Docker, ví dụ `Docker version 27.x.x`.

### Bước 2: Cài Minikube

```bash
# Linux (x86_64)
curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube /usr/local/bin/minikube
```

Kiểm tra:

```bash
minikube version
```

**Kết quả mong đợi**: in ra version Minikube.

### Bước 3: Cài kubectl

```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

Kiểm tra:

```bash
kubectl version --client
```

**Kết quả mong đợi**: in ra version kubectl client.

### Bước 4: Khởi động cluster Minikube

```bash
minikube start --driver=docker
```

**Kết quả mong đợi**: log hiển thị các bước "Creating docker container", "Preparing Kubernetes", "Done! kubectl is now configured...".

### Bước 5: Verify cluster sẵn sàng

```bash
kubectl get nodes
```

**Kết quả mong đợi**:

```
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   1m    v1.36.x
```

Cột `STATUS` phải là `Ready`. Nếu là `NotReady`, đợi thêm vài chục giây rồi chạy lại lệnh.

---

## Bài tập 1 (Beginner): Deploy app đơn giản bằng Deployment

**Mục tiêu**: hiểu cách tạo Deployment bằng YAML và quan sát Pod được tạo ra.

**Yêu cầu**: đã hoàn thành phần Chuẩn bị, `kubectl get nodes` thấy `Ready`.

### Các bước

**Bước 1**: Tạo thư mục làm việc và file `deployment.yaml`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-echo
  labels:
    app: hello-echo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello-echo
  template:
    metadata:
      labels:
        app: hello-echo
    spec:
      containers:
        - name: http-echo
          image: hashicorp/http-echo:1.0.0
          args:
            - "-text=Xin chao tu Kubernetes!"
          ports:
            - containerPort: 5678
```

**Bước 2**: Áp dụng file YAML vào cluster.

```bash
kubectl apply -f deployment.yaml
```

**Kết quả mong đợi**: `deployment.apps/hello-echo created`.

**Bước 3**: Kiểm tra Pod được tạo.

```bash
kubectl get pods
```

**Kết quả mong đợi**: thấy 2 Pod tên dạng `hello-echo-xxxxxxxxxx-yyyyy`, cột `STATUS` là `Running` sau vài chục giây, cột `READY` là `1/1`.

**Bước 4**: Xem chi tiết 1 Pod.

```bash
kubectl describe pod <ten-pod-vua-lay-tu-buoc-3>
```

**Kết quả mong đợi**: thấy mục `Events` ở cuối, có dòng `Pulled`, `Created`, `Started` — xác nhận container đã chạy thành công.

**Kiến thức luyện tập**: viết Deployment YAML cơ bản, quan sát Deployment tạo ReplicaSet rồi ReplicaSet tạo Pod, đọc `describe` để xác nhận trạng thái.

---

## Bài tập 2 (Practical): Service, ConfigMap/Secret, Scale, Rolling Update, Rollback

**Mục tiêu**: expose app ra ngoài bằng Service, truyền config qua ConfigMap/Secret, thực hành scale và rolling update/rollback.

**Yêu cầu**: đã hoàn thành Bài tập 1, Deployment `hello-echo` đang chạy.

### Phần A: Thêm Service (NodePort) để truy cập app

**Bước 1**: Tạo file `service.yaml`.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello-echo-svc
spec:
  type: NodePort
  selector:
    app: hello-echo
  ports:
    - port: 80
      targetPort: 5678
      nodePort: 30080
```

**Bước 2**: Áp dụng và kiểm tra.

```bash
kubectl apply -f service.yaml
kubectl get svc hello-echo-svc
```

**Kết quả mong đợi**: thấy `hello-echo-svc` với `TYPE` là `NodePort`, cột `PORT(S)` có dạng `80:30080/TCP`.

**Bước 3**: Truy cập app qua Minikube.

```bash
minikube service hello-echo-svc
```

**Kết quả mong đợi**: trình duyệt mở ra (hoặc in ra URL), hiển thị nội dung `Xin chao tu Kubernetes!`.

### Phần B: Thêm ConfigMap và Secret

**Bước 4**: Tạo file `config.yaml` gồm cả ConfigMap và Secret.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-echo-config
data:
  GREETING_TEXT: "Xin chao tu ConfigMap!"
---
apiVersion: v1
kind: Secret
metadata:
  name: hello-echo-secret
type: Opaque
stringData:
  API_TOKEN: "super-secret-token"
```

**Bước 5**: Cập nhật `deployment.yaml`, thêm phần `env` lấy giá trị từ ConfigMap và Secret (giữ nguyên `args` cũ, chỉ thêm `env`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-echo
  labels:
    app: hello-echo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello-echo
  template:
    metadata:
      labels:
        app: hello-echo
    spec:
      containers:
        - name: http-echo
          image: hashicorp/http-echo:1.0.0
          args:
            - "-text=Xin chao tu Kubernetes!"
          ports:
            - containerPort: 5678
          env:
            - name: GREETING_TEXT
              valueFrom:
                configMapKeyRef:
                  name: hello-echo-config
                  key: GREETING_TEXT
            - name: API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: hello-echo-secret
                  key: API_TOKEN
```

**Bước 6**: Áp dụng và kiểm tra biến môi trường trong Pod.

```bash
kubectl apply -f config.yaml
kubectl apply -f deployment.yaml
kubectl get pods   # lấy tên pod mới
kubectl exec <ten-pod-moi> -- env | grep -E "GREETING_TEXT|API_TOKEN"
```

**Kết quả mong đợi**: in ra `GREETING_TEXT=Xin chao tu ConfigMap!` và `API_TOKEN=super-secret-token`.

### Phần C: Scale

**Bước 7**: Tăng số Pod lên 4.

```bash
kubectl scale deploy/hello-echo --replicas=4
kubectl get pods
```

**Kết quả mong đợi**: thấy 4 Pod, tất cả `Running`.

### Phần D: Rolling Update và Rollback

**Bước 8**: Cập nhật image sang version mới (giả lập rolling update).

```bash
kubectl set image deploy/hello-echo http-echo=hashicorp/http-echo:1.0.0
kubectl rollout status deploy/hello-echo
```

**Kết quả mong đợi**: log hiển thị tiến trình, cuối cùng in `deployment "hello-echo" successfully rolled out`.

**Bước 9**: Xem lịch sử rollout.

```bash
kubectl rollout history deploy/hello-echo
```

**Kết quả mong đợi**: thấy ít nhất 2 revision.

**Bước 10**: Rollback về revision trước.

```bash
kubectl rollout undo deploy/hello-echo
kubectl rollout status deploy/hello-echo
```

**Kết quả mong đợi**: rollout thành công, Deployment quay về image trước đó.

**Kiến thức luyện tập**: Service kết nối Pod qua label selector, ConfigMap/Secret bơm config vào Pod qua biến môi trường, scale thay đổi số Pod tức thì, rolling update/rollback không downtime.

---

## Bài tập 3 (Advanced/Differentiating — tùy chọn): Debug lỗi thường gặp

**Mục tiêu**: luyện phản xạ debug khi Pod lỗi, hiểu 2 lỗi phổ biến nhất: `ImagePullBackOff` và `CrashLoopBackOff`.

**Yêu cầu**: đã hoàn thành Bài tập 1.

### Các bước

**Bước 1**: Tạo file `broken-deployment.yaml` với image sai tên (không tồn tại).

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: broken-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: broken-app
  template:
    metadata:
      labels:
        app: broken-app
    spec:
      containers:
        - name: broken-container
          image: hashicorp/http-echo-khong-ton-tai:v999
```

**Bước 2**: Áp dụng và quan sát.

```bash
kubectl apply -f broken-deployment.yaml
kubectl get pods
```

**Kết quả mong đợi**: sau khoảng 30-60 giây, cột `STATUS` hiển thị `ImagePullBackOff` hoặc `ErrImagePull`.

**Bước 3**: Debug bằng `describe`.

```bash
kubectl describe pod <ten-pod-broken-app>
```

**Kết quả mong đợi**: mục `Events` có dòng `Failed to pull image` — giải thích: kubelet không tìm được image trên registry, do sai tên/tag hoặc registry riêng cần đăng nhập.

**Bước 4**: Sửa lỗi bằng cách đổi lại image đúng và tạo `crash-deployment.yaml` để giả lập `CrashLoopBackOff` (container tự thoát ngay sau khi chạy).

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crash-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crash-app
  template:
    metadata:
      labels:
        app: crash-app
    spec:
      containers:
        - name: crash-container
          image: busybox:1.36
          command: ["sh", "-c", "echo 'Toi sap thoat'; exit 1"]
```

**Bước 5**: Áp dụng và quan sát.

```bash
kubectl apply -f crash-deployment.yaml
kubectl get pods --watch
```

**Kết quả mong đợi**: cột `STATUS` chuyển từ `Running` sang `Error` rồi thành `CrashLoopBackOff`, cột `RESTARTS` tăng dần.

**Bước 6**: Debug bằng `logs` và `describe`.

```bash
kubectl logs <ten-pod-crash-app>
kubectl describe pod <ten-pod-crash-app>
```

**Kết quả mong đợi**: `logs` in ra `Toi sap thoat`. `describe` cho thấy `Exit Code: 1` và `Back-off restarting failed container` trong Events.

**Giải thích**:
- `ImagePullBackOff` / `ErrImagePull`: kubelet không tải được image (sai tên, sai tag, private registry chưa auth). Container chưa từng chạy nên `kubectl logs` sẽ trống hoặc lỗi — đây là lý do phải xem `describe` trước.
- `CrashLoopBackOff`: container đã chạy nhưng tự thoát (exit code khác 0) liên tục, K8s tăng dần thời gian chờ trước khi thử lại (exponential backoff). Nguyên nhân thường là lỗi trong chính ứng dụng (thiếu config, lỗi code, thiếu quyền).

**Bước 7**: Dọn dẹp các resource lỗi.

```bash
kubectl delete -f broken-deployment.yaml
kubectl delete -f crash-deployment.yaml
```

**Kiến thức luyện tập**: phân biệt lỗi ở tầng "kéo image" (trước khi container chạy) và lỗi ở tầng "chạy container" (sau khi container chạy), phản xạ dùng `describe` trước `logs`.

---

## Checklist hoàn thành

- [ ] Cài xong Docker, Minikube, kubectl và verify version từng công cụ
- [ ] `minikube start` chạy thành công, `kubectl get nodes` thấy `Ready`
- [ ] Deploy được `hello-echo` bằng Deployment YAML, thấy Pod `Running`
- [ ] Tạo Service NodePort và truy cập app thành công qua `minikube service`
- [ ] Tạo ConfigMap + Secret và xác nhận biến môi trường xuất hiện đúng trong Pod
- [ ] Scale Deployment lên 4 replicas thành công
- [ ] Thực hiện 1 lần rolling update (`kubectl set image`) và xem `rollout status`
- [ ] Thực hiện 1 lần rollback (`kubectl rollout undo`) thành công
- [ ] (Tùy chọn) Tạo được lỗi `ImagePullBackOff` và giải thích đúng nguyên nhân qua `describe`
- [ ] (Tùy chọn) Tạo được lỗi `CrashLoopBackOff` và giải thích đúng nguyên nhân qua `logs` + `describe`
- [ ] Dọn dẹp toàn bộ resource test (`kubectl delete -f ...`) sau khi hoàn thành

---

⬅️ Quay lại: [bai-hoc.md](./bai-hoc.md) · [tai-lieu.md](./tai-lieu.md)
