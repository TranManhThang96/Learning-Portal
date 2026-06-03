# Document - Day 03: Comparison Matrix và Decision Guide

## Bảng so sánh nhanh

| Tiêu chí | K3s | MicroK8s | Minikube | Kind | Managed K8s |
|---|---|---|---|---|---|
| Loại | Kubernetes distribution | Kubernetes distribution | Local dev/learning tool | Local/CI test tool | Cloud managed service |
| Node model | Process thật trên VM/host | Process thật trên host | VM/container tùy driver | Docker container làm node | Cloud VM/node pool |
| Mục tiêu chính | Lightweight/edge/lab/small prod | Ubuntu lab/edge/addon workflow | Học và demo local | CI/test Kubernetes | Production cloud |
| Startup | Nhanh | Nhanh-trung bình | Trung bình | Rất nhanh | Phụ thuộc cloud |
| Multi-node | Có | Có | Có, nhưng thường dùng local | Có | Có |
| HA production | Có, cần thiết kế datastore | Có, cần thiết kế | Không phải mục tiêu chính | Không phải mục tiêu chính | Provider hỗ trợ control plane |
| Ingress | Traefik thường packaged | Addon | Addon | Cần cài và map port | Cloud/addon/controller |
| LoadBalancer | ServiceLB/MetalLB/tùy chọn | Addon/tùy chọn | tunnel/addon/tùy driver | Cần extra setup | Cloud LB |
| Storage | local-path mặc định cho lab | Addon/storage tùy bật | Addon/local | HostPath/container mount | Cloud CSI |
| CI suitability | Trung bình | Thấp-trung bình | Thấp-trung bình | Cao | Thấp do chi phí/thời gian |
| Production suitability | Có trong bối cảnh phù hợp | Có trong bối cảnh phù hợp | Không | Không | Cao |

## Decision tree

```text
Bạn cần production trên cloud?
  |
  +-- Có --> Ưu tiên EKS/GKE/AKS, trừ khi có lý do mạnh để self-managed.
  |
  +-- Không
       |
       +-- Cần edge/homelab/small cluster thật? --> K3s hoặc MicroK8s.
       |
       +-- Cần test manifest/controller trong CI? --> Kind.
       |
       +-- Cần học nhanh local workstation? --> K3s, Minikube hoặc Kind.
```

## K3s packaged defaults cần nhớ

| Component | Vai trò | Production caveat |
|---|---|---|
| `containerd` | Container runtime | Kiểm tra registry mirror, image GC, runtime config |
| Flannel | CNI/network overlay mặc định phổ biến trong K3s | Không có policy/security nâng cao như một số CNI khác |
| CoreDNS | DNS trong cluster | Cần monitor latency/error, config stub domain nếu cần |
| Traefik | Ingress controller packaged | Có thể cần disable nếu dùng ingress controller chuẩn khác |
| local storage provisioner | Dynamic local PV cho lab | Không dùng cho dữ liệu production cần HA/backup |
| ServiceLB | LoadBalancer implementation đơn giản | Không thay thế cloud LB/MetalLB design phức tạp |
| metrics-server | Resource metrics cho `kubectl top`, HPA CPU/memory | Không thay thế monitoring stack đầy đủ |

## Câu hỏi chọn môi trường

Trước khi chọn tool, trả lời:

1. Mục tiêu là học API Kubernetes, test CI, hay chạy workload thật?
2. Có cần mô phỏng multi-node, node failure, storage failure không?
3. Target production là K3s, self-managed upstream hay EKS/GKE/AKS?
4. Cần Ingress/LoadBalancer giống production đến mức nào?
5. Có yêu cầu backup/restore và upgrade drill không?
6. Team có kỹ năng vận hành Linux, network, storage, certificate và observability không?

## Commands inventory cluster type

```bash
kubectl version
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
kubectl get storageclass
kubectl get ingressclass
kubectl get svc -A
kubectl api-resources
```

K3s node-level:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 100 --no-pager
sudo ls -la /etc/rancher/k3s/
sudo cat /etc/rancher/k3s/config.yaml
```

Kind:

```bash
kind get clusters
kind get nodes --name <cluster-name>
kind export kubeconfig --name <cluster-name>
```

## Ví dụ kind config multi-node

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 80
        hostPort: 8080
        protocol: TCP
      - containerPort: 443
        hostPort: 8443
        protocol: TCP
  - role: worker
  - role: worker
```

Tạo cluster:

```bash
kind create cluster --name lab --config kind-config.yaml --wait 5m
```

Điểm cần nhớ: config này tiện cho local ingress test, nhưng không tương đương cloud LoadBalancer.
