# Bài thực hành - Day 03: So sánh Kubernetes Distributions và Local Tools

## Prerequisites

- Có cluster `k3d-k8s-lab` từ Day 01, hoặc một cluster Kubernetes/K3s tương đương đang chạy.
- `kubectl` trỏ đúng context.
- Tùy chọn: có `kind` và Docker nếu muốn làm phần so sánh cluster local.
- Có quyền đọc namespace `kube-system`.

## Lab Scenario

Bạn cần tư vấn môi trường cho ba use case:

- Học cá nhân trong 45 ngày.
- CI pipeline validate Kubernetes manifests.
- Small production cho internal service.

Bạn sẽ inventory cluster hiện tại, xác định packaged components, rồi lập ma trận quyết định.

Core Path: Task 1, 2, 3 và 5 khoảng 100-110 phút. Task 4 tạo Kind cluster là optional/stretch vì có thể vượt 2 giờ nếu Docker pull image chậm hoặc máy yếu.

## Task 1: Xác định cluster hiện tại (25 phút)

### Mục tiêu

Biết mình đang đứng trên loại cluster nào và có những component mặc định nào.

### Các bước thực hiện

```bash
kubectl config current-context
kubectl version
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
kubectl get storageclass
kubectl get ingressclass
kubectl get svc -A
```

Nếu là K3s và bạn có quyền trên node:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 50 --no-pager
sudo ls -la /etc/rancher/k3s/
```

### Expected output

Ghi lại:

- Kubernetes server version.
- Node OS/container runtime.
- CNI hoặc network pods nếu nhận diện được.
- StorageClass mặc định.
- IngressClass hiện có.
- Có `LoadBalancer` service nào được cấp external IP không.

## Task 2: Kiểm tra packaged/default components (25 phút)

### Mục tiêu

Phân biệt component thuộc Kubernetes core và component do distro/tool cài sẵn.

### Các bước thực hiện

```bash
kubectl get pods -n kube-system
kubectl get deploy,ds -n kube-system
kubectl get helmcharts -A
```

Lệnh `helmcharts` áp dụng cho K3s nếu CRD đó tồn tại; nếu báo resource type không tồn tại, ghi chú lại.

K3s packaged components thay đổi theo version/config. Không suy luận rằng Traefik, ServiceLB, local-path hoặc metrics-server luôn bật; hãy ghi nhận state thật của cluster đang dùng.

Với K3s, tìm các component thường gặp:

```bash
kubectl get pods -n kube-system | grep -E "coredns|traefik|local-path|metrics-server|svclb"
```

Nếu shell không có `grep`, dùng:

```bash
kubectl get pods -n kube-system
```

và lọc bằng mắt.

### Verification

Tạo bảng ngắn trong notes:

| Component | Có/Không | Core hay packaged addon | Production note |
|---|---|---|---|
| CoreDNS | | | |
| Traefik | | | |
| local-path-provisioner | | | |
| metrics-server | | | |
| ServiceLB/svclb | | | |

## Task 3: So sánh `LoadBalancer` behavior (30 phút)

### Mục tiêu

Thấy `Service type LoadBalancer` phụ thuộc môi trường.

### Các bước thực hiện

```bash
kubectl create deployment lb-demo --image=nginx:1.27
kubectl expose deployment lb-demo --port=80 --target-port=80 --type=LoadBalancer
kubectl get svc lb-demo -w
```

Chờ 1-2 phút, nhấn `Ctrl+C` để dừng `watch`, rồi kiểm tra:

```bash
kubectl describe svc lb-demo
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- Managed Kubernetes thường cấp external IP/hostname qua cloud LB.
- K3s có thể tạo ServiceLB pods nếu ServiceLB bật.
- Kind/upstream local thường để `EXTERNAL-IP` là `pending` nếu không có MetalLB/cloud integration.

### Cách dọn

```bash
kubectl delete svc lb-demo
kubectl delete deployment lb-demo
```

## Optional Task 4 (Stretch): Tạo kind cluster để so sánh (35 phút)

Chỉ làm nếu đã cài Docker và `kind`.

### Mục tiêu

Tạo một cluster CI-like và nhận ra khác biệt với K3s/local cluster hiện tại.

### Các bước thực hiện

Tạo `kind-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
```

Tạo cluster:

```bash
kind create cluster --name day03 --config kind-config.yaml --wait 5m
kubectl cluster-info --context kind-day03
kubectl get nodes -o wide
kubectl get pods -n kube-system
```

So sánh với cluster ban đầu:

```bash
kubectl config get-contexts
```

Dọn dẹp:

```bash
kind delete cluster --name day03
```

### Troubleshooting

- Nếu Docker không chạy, kind không tạo được cluster.
- Nếu port conflict, đổi config hoặc xóa cluster cũ.
- Nếu `kubectl` context bị đổi, dùng `kubectl config use-context <context>`.

## Task 5: Lập recommendation matrix (25 phút)

### Mục tiêu

Ra quyết định có giải thích trade-offs.

Điền bảng:

| Use case | Chọn gì | Vì sao | Rủi ro chính | Mitigation |
|---|---|---|---|---|
| Học 45 ngày | | | | |
| CI validate manifests | | | | |
| Small production internal service | | | | |
| Medium production cloud | | | | |

Gợi ý:

- Học 45 ngày: K3s single-node trước, multi-node sau.
- CI validate manifests: Kind.
- Small production internal service: K3s nếu team vận hành được; managed K8s nếu đã ở cloud và muốn giảm control plane burden.
- Medium production cloud: EKS/GKE/AKS thường pragmatic hơn.

## Common Pitfalls

- Thấy `LoadBalancer pending` rồi kết luận Kubernetes lỗi; thực tế cluster local không có load balancer implementation.
- Nhầm packaged addon với Kubernetes core.
- Quên đổi context sau khi tạo kind cluster.
- Dùng kết quả performance trên Kind để suy luận production.

## Stretch Goals

- Nếu dùng K3s, thử đọc config file và đề xuất 3 thay đổi cho production hardening.
- Nếu có cloud cluster, so sánh `StorageClass`, `IngressClass`, `LoadBalancer` behavior với K3s.
- Viết một trang ADR ngắn: "Chọn môi trường Kubernetes cho team trong 6 tháng tới".
