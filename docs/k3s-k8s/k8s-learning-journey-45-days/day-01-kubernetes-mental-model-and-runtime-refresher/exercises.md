# Bài thực hành - Day 01: Kubernetes Mental Model

## Prerequisites

Mục tiêu của ngày đầu là có cluster local chạy được ngay. Môi trường mặc định:

- Docker đang chạy.
- `kubectl` đã cài.
- `k3d` đã cài.
- Network có thể pull image từ Docker Hub và registry Kubernetes.

Kiểm tra nhanh:

```bash
docker version
kubectl version --client
k3d version
```

Nếu một trong ba lệnh trên chưa chạy được, cài công cụ đó trước rồi quay lại bài này. Trên Windows, cách ít nhiễu nhất là dùng Docker Desktop với WSL2 và chạy các lệnh trong Linux shell của WSL2.

## Lab Scenario

Bạn sẽ tự tạo một cluster K3s local bằng `k3d`, deploy service `web`, quan sát Kubernetes biến desired state thành object thật, sau đó cố tình tạo lỗi image để luyện debug.

Core Path: Task 1-6 khoảng 110-120 phút nếu image pull ổn định. Nếu bị chậm registry hoặc máy thiếu tài nguyên, ưu tiên hoàn thành Task 1-5 và chỉ dọn workload thay vì reset toàn bộ cluster.

## Task 1: Tạo local cluster bằng k3d (20 phút)

### Mục tiêu

Tạo được Kubernetes/K3s cluster local để các bài sau dùng lại.

### Các bước thực hiện

Kiểm tra chưa có cluster trùng tên:

```bash
k3d cluster list
```

Tạo cluster:

```bash
k3d cluster create k8s-lab --api-port 6550 -p "8080:80@loadbalancer"
```

Giải thích nhanh:

- `k8s-lab`: tên cluster.
- `--api-port 6550`: expose Kubernetes API ra `localhost:6550`.
- `-p "8080:80@loadbalancer"`: map port 8080 trên máy local vào port 80 của k3d load balancer, dùng cho Ingress ở các bài sau.

Xác minh:

```bash
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
```

### Expected output

- Context hiện tại trỏ tới cluster `k3d-k8s-lab`.
- Có ít nhất một node ở trạng thái `Ready`.

### Troubleshooting

- Nếu `Cannot connect to the Docker daemon`, kiểm tra Docker Desktop/Engine đã chạy chưa.
- Nếu `kubectl` trỏ sai cluster, chạy `k3d kubeconfig merge k8s-lab --kubeconfig-switch-context`.
- Nếu port `6550` hoặc `8080` đã bị chiếm, xóa cluster lỗi rồi tạo lại với port khác.

## Task 2: Khảo sát cluster nền tảng (15 phút)

### Mục tiêu

Đọc được các object nền tảng trước khi deploy workload đầu tiên.

### Các bước thực hiện

```bash
kubectl get nodes -o wide
kubectl get namespaces
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
kubectl get storageclass
kubectl get ingressclass
kubectl get nodes -o custom-columns=NAME:.metadata.name,RUNTIME:.status.nodeInfo.containerRuntimeVersion,KUBELET:.status.nodeInfo.kubeletVersion
```

### Expected output

- Namespace `kube-system` có system pods.
- Với K3s/k3d, bạn thường thấy `coredns`, `local-path-provisioner`, `metrics-server`, `traefik` nếu chưa disable packaged components.
- Có `StorageClass` local-path hoặc tương đương cho lab.
- Runtime của node thường là `containerd://...`, không phải Docker Engine trực tiếp.

### Troubleshooting

- Nếu node `NotReady`, dùng `kubectl describe node <node-name>` và đọc `Conditions`.
- Nếu system Pod bị `ImagePullBackOff`, kiểm tra network, proxy hoặc registry access.

## Task 3: Tạo desired state đầu tiên (25 phút)

### Mục tiêu

Tạo `Deployment` và `Service`, sau đó quan sát Kubernetes tạo `ReplicaSet` và `Pod`.

### Các bước thực hiện

Tạo file `web.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
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
        - name: nginx
          image: nginx:1.27
          ports:
            - containerPort: 80
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
    - port: 80
      targetPort: 80
```

Apply và quan sát:

```bash
kubectl apply -f web.yaml
kubectl get deploy,rs,pod,svc
kubectl rollout status deployment/web
kubectl describe deployment web
```

### Verification

```bash
kubectl get pods -l app=web -o wide
kubectl get endpoints web
kubectl describe svc web
```

`endpoints web` phải có Pod IP nếu `Service` selector match `Pod` labels.

## Task 4: Quan sát reconciliation (20 phút)

### Mục tiêu

Thấy Kubernetes tự kéo actual state về desired state.

### Các bước thực hiện

Mở terminal thứ nhất:

```bash
kubectl get pods -l app=web -w
```

Ở terminal thứ hai, xóa một `Pod`:

```bash
kubectl get pods -l app=web -o name
kubectl delete <pod-resource-name>
```

Ví dụ `<pod-resource-name>` có dạng `pod/web-abc123-xyz89`. Xóa một Pod giúp bạn thấy controller bù đúng một replica, trực quan hơn so với xóa toàn bộ Pod cùng label. Quan sát `Pod` mới được tạo lại. Sau đó scale:

```bash
kubectl scale deployment web --replicas=3
kubectl get deploy,rs,pod -l app=web
```

### Expected output

- Sau khi xóa một Pod, Pod cũ chuyển `Terminating` và `ReplicaSet` tạo đúng một Pod mới.
- Sau khi scale, số `Pod` tăng lên 3.

### Câu hỏi cần tự trả lời

- Bạn xóa `Pod`, nhưng object nào quyết định tạo lại `Pod`?
- `kubectl scale` thay đổi desired state ở đâu?

### Answer key ngắn

- `ReplicaSet` tạo lại `Pod`; `ReplicaSet` đó được `Deployment` quản lý.
- `kubectl scale deployment web --replicas=3` thay đổi `spec.replicas` của `Deployment`, sau đó controller reconcile xuống `ReplicaSet`/`Pod`.

## Task 5: Inject lỗi image và debug (25 phút)

### Mục tiêu

Tạo lỗi phổ biến `ImagePullBackOff`, rồi debug bằng `describe`, events và rollout history.

### Lỗi cần tạo

Đổi image sang tag không tồn tại:

```bash
kubectl set image deployment/web nginx=nginx:tag-khong-ton-tai
kubectl rollout status deployment/web --timeout=60s
```

### Symptom

Pod mới rơi vào `ImagePullBackOff` hoặc `ErrImagePull`.

### Cách điều tra

```bash
kubectl get pods -l app=web
kubectl describe pod <pod-name>
kubectl get events --sort-by=.lastTimestamp
kubectl rollout history deployment/web
```

Khi đọc `describe pod`, tập trung vào:

- `State` và `Reason`.
- `Image`.
- `Events` ở cuối output.

### Cách fix

Rollback:

```bash
kubectl rollout undo deployment/web
kubectl rollout status deployment/web
kubectl get pods -l app=web
```

### Lab vs production

- Lab: rollback trực tiếp để hiểu cơ chế.
- Production: kiểm tra CI image publish, registry auth, rollout strategy, alert, rồi rollback qua pipeline hoặc GitOps source-of-truth.

## Task 6: Dọn dẹp hoặc giữ cluster cho Day 02 (15 phút)

Nếu học tiếp Day 02 ngay, chỉ xóa workload:

```bash
kubectl delete -f web.yaml
kubectl get deploy,rs,pod,svc
```

Nếu muốn reset toàn bộ cluster:

```bash
k3d cluster delete k8s-lab
k3d cluster list
```

Khuyến nghị: giữ cluster `k8s-lab` nếu bạn học liên tục sang Day 02.

## Common Pitfalls

- Docker chưa chạy nhưng lại debug `kubectl`.
- `kubectl` trỏ sai context sau khi từng dùng cluster khác.
- Quên namespace: object tạo ở namespace hiện tại nhưng lại `get` ở namespace khác.
- `Service` không có endpoints vì selector không khớp label.
- Dùng image tag `latest`, dẫn tới kết quả không tái lập.
- Chỉ đọc logs mà không đọc `describe` và events.

## Stretch Goals

- Tạo lại cluster với một worker node riêng:

```bash
k3d cluster delete k8s-lab
k3d cluster create k8s-lab --api-port 6550 -p "8080:80@loadbalancer" --agents 1
kubectl get nodes -o wide
```

- Tạo lỗi selector mismatch giữa `Service` và `Pod`, rồi debug bằng `kubectl get endpoints web`.
- So sánh thời gian rollout khi image đã có cache và khi node phải pull image mới.
- Dùng `kubectl explain deployment.spec.strategy` để đọc schema ngay từ API.
