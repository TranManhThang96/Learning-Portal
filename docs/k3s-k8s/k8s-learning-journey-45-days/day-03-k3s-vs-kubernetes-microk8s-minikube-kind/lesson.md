# Day 03: K3s vs Kubernetes chuẩn vs MicroK8s vs Minikube vs Kind

## Mục tiêu bài học

- Phân biệt Kubernetes upstream, Kubernetes distribution và local cluster tool.
- Hiểu K3s tối ưu cho bối cảnh nào và khác gì so với cluster Kubernetes tự dựng.
- So sánh K3s, MicroK8s, Minikube, Kind và managed Kubernetes theo use case thực tế.
- Nhận diện packaged defaults của K3s như `containerd`, Flannel, CoreDNS, Traefik, local storage và ServiceLB.
- Chọn môi trường lab/production phù hợp cho từng mục tiêu học hoặc vận hành.

## Vấn đề cần giải quyết

Nhiều người nói "dùng Kubernetes" nhưng thực tế có nhiều lựa chọn rất khác nhau:

- Upstream Kubernetes tự dựng bằng kubeadm hoặc tool tương tự.
- K3s như một Kubernetes distribution nhẹ.
- MicroK8s như distro đóng gói bằng snap.
- Minikube như local learning cluster.
- Kind như Kubernetes chạy bằng Docker container nodes cho CI/test.
- EKS/GKE/AKS như managed Kubernetes.

Nếu không phân biệt, bạn có thể học sai tín hiệu: lab chạy rất dễ nhưng production lại vướng cloud CNI, IAM, LoadBalancer, CSI, upgrade và backup.

## Mental Model

```text
Kubernetes API = contract chính
Distribution/tool = cách đóng gói và vận hành contract đó
Cloud provider = ai quản lý control plane, node, network, storage, identity
```

Điều bạn học từ `Deployment`, `Service`, `Pod`, `ConfigMap`, `Secret`, `RBAC` thường portable. Điều khác biệt nằm ở default components, lifecycle management, storage/network integration và operational responsibility.

## Lý thuyết cốt lõi

### Kubernetes chuẩn

Kubernetes upstream là project gốc với các component như `kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager`, `kubelet`, `kube-proxy`. Khi tự dựng, bạn phải chọn và vận hành CNI, CSI, Ingress controller, monitoring, logging, backup, upgrade, certificate rotation và security baseline.

Ưu điểm là kiểm soát tối đa. Nhược điểm là operational burden cao.

### K3s

K3s là certified Kubernetes distribution nhẹ, đóng gói thành single binary và giảm dependency bên ngoài. Theo tài liệu K3s, nó có trải nghiệm "batteries-included" với các component thiết yếu như `containerd`, Flannel, CoreDNS, Traefik và local storage provisioner; đồng thời có các controller cho load balancing, network policy và persistent volume provisioning.

Các điểm quan trọng:

- `k3s server` đóng gói nhiều control plane component.
- `k3s agent` chạy ở worker node.
- Single-node thường dùng SQLite mặc định.
- HA có thể dùng embedded `etcd` hoặc external datastore như MySQL/PostgreSQL.
- Packaged components do K3s quản lý, không nên sửa trực tiếp manifest được K3s sinh ra.

K3s rất phù hợp lab, edge, IoT, homelab, small production hoặc môi trường cần footprint thấp. Nó không tự động làm production readiness thay bạn: vẫn cần backup, HA, monitoring, security hardening và upgrade plan.

K3s defaults phụ thuộc version và config lúc cài. Đừng mặc định rằng mọi cluster K3s đều bật Traefik, ServiceLB, local-path, metrics-server hoặc network policy theo cùng một cách. Luôn xác minh bằng `kubectl get pods -n kube-system`, `kubectl get ingressclass`, `kubectl get storageclass`, `kubectl get svc -A` và config trong `/etc/rancher/k3s/config.yaml` nếu có quyền node.

### MicroK8s

MicroK8s là Kubernetes distribution của Canonical, thường tiện trên Ubuntu và mô hình snap/addon. Nó hợp cho lab, workstation, edge hoặc small cluster. Điểm mạnh là bật/tắt addon nhanh; điểm cần cẩn trọng là addon mặc định/lab có thể không giống production cloud.

### Minikube

Minikube tập trung vào local Kubernetes learning/development. Nó có nhiều driver như Docker, VM driver, và addon tiện để học. Nó tốt khi cần cluster cá nhân nhanh, nhưng không phải production distribution.

### Kind

Kind nghĩa là Kubernetes IN Docker. Theo tài liệu kind, nó chạy local Kubernetes clusters bằng Docker container "nodes", được thiết kế ban đầu để test Kubernetes nhưng được dùng rộng rãi trong local development và CI/CD. Kind hỗ trợ cluster single-node, multi-node, cấu hình port mapping, mount, networking và image Kubernetes cụ thể.

Kind rất mạnh cho test manifest/controller trong CI vì tạo/xóa cluster nhanh và tái lập tốt. Caveat là node thực chất là container, nên storage/networking/load balancer không đại diện đầy đủ cho production.

### Managed Kubernetes

EKS/GKE/AKS quản lý control plane và tích hợp cloud network/storage/load balancer/IAM. Đây thường là lựa chọn tốt cho medium/large production trên cloud. Nhưng managed không có nghĩa là "không cần vận hành":

- Node pool vẫn cần sizing, upgrade và cost control.
- Workload vẫn cần requests/limits, probes, PDB, HPA.
- Security vẫn cần RBAC, secret management, policy và image scanning.
- Observability và incident response vẫn là trách nhiệm của team.

## Deep Dive: Vì sao K3s nhẹ hơn

K3s giảm độ phức tạp bằng cách:

- Đóng gói nhiều component trong một binary.
- Dùng SQLite mặc định cho single-node để tránh vận hành `etcd` ngay từ đầu.
- Bundled runtime và packaged components để cluster có thể usable nhanh.
- Giảm dependency OS, phù hợp edge/resource-constrained environments.

Trade-off là bạn cần hiểu defaults. Ví dụ Traefik có thể tiện cho lab, nhưng production có thể cần NGINX Ingress, HAProxy, cloud Load Balancer Controller hoặc Gateway API tùy chuẩn tổ chức. `local-path-provisioner` tiện để học PVC, nhưng không thay thế storage replicated/backup-ready cho production data.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Mục tiêu | Lightweight, edge, lab, small cluster | Full control | Cloud production |
| Control plane | `k3s server` đóng gói | Component tách rời | Provider quản lý |
| Datastore | SQLite, embedded etcd, external DB | etcd | Provider quản lý |
| Default addons | Có nhiều packaged components | Tùy bạn cài | Cloud addon/integration |
| LoadBalancer | ServiceLB hoặc tùy cấu hình | Cần giải pháp riêng | Cloud LB |
| Storage | local-path cho lab, CSI tùy chọn | Cần CSI/provisioner | Cloud CSI |
| Upgrade | Team tự kiểm soát | Team tự kiểm soát | Provider hỗ trợ control plane/node |
| Best fit | Lab/edge/small prod | On-prem/full control | Medium/large cloud production |

## Trade-offs và Best Practices

### Trade-offs

| Option | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| K3s | Muốn Kubernetes thật, nhẹ, nhanh | Footprint thấp, tốt cho node nhỏ | Trung bình | Packaged default không khớp production target |
| MicroK8s | Ubuntu workstation/edge, addon tiện | Tùy addon bật | Trung bình | Snap/addon lifecycle cần hiểu |
| Minikube | Học local, demo nhanh | Tùy driver | Thấp | Không đại diện production |
| Kind | CI/test manifest/controller | Tạo/xóa nhanh, containerized nodes | Thấp | Networking/storage/LB khác production |
| Managed K8s | Production cloud | Control plane ổn định, cloud-native integration | Trung bình | IAM/CNI/quota/cloud dependency |
| Upstream self-managed | On-prem hoặc cần full control | Tùy thiết kế | Cao | Team chịu mọi sự cố control plane |

### Best Practices

Nên làm:

- Chọn tool theo mục tiêu học: K3s cho cluster thật nhẹ, Kind cho CI, managed K8s cho production cloud.
- Ghi rõ khác biệt giữa lab và target production trong mỗi design decision.
- Với K3s production, disable/replace packaged component nếu organization đã có chuẩn riêng.
- Kiểm tra backup datastore trước khi gọi cluster là production-ready.

Tránh làm:

- Đánh đồng Kind/Minikube với production cluster.
- Dùng `local-path-provisioner` cho dữ liệu production quan trọng.
- Tin rằng managed Kubernetes thay thế hoàn toàn DevOps/SRE work.
- Sửa trực tiếp file packaged component do K3s quản lý.

## Performance Considerations

- K3s tiết kiệm tài nguyên control plane, hữu ích trên VM nhỏ hoặc edge node.
- Kind phụ thuộc Docker host; performance I/O/networking không phản ánh node thật.
- Minikube với VM driver có overhead khác Docker driver.
- Managed Kubernetes có control plane tốt hơn về vận hành, nhưng app latency vẫn phụ thuộc node type, CNI, zone topology, LB và workload config.
- Local storage trong lab thường nhanh nhưng có failure semantics rất khác network/block storage production.

## Debugging Checklist

Khi gặp lỗi trên một cluster lạ, hỏi trước:

- Đây là K3s, Kind, Minikube, MicroK8s, upstream hay managed?
- Component nào là packaged/default?
- Ingress controller nào đang chạy?
- StorageClass default là gì?
- Service type `LoadBalancer` được xử lý bởi cloud provider, ServiceLB, MetalLB hay không có gì?
- CNI là gì?
- Cluster có policy engine thực sự enforce `NetworkPolicy` không, hay chỉ có CNI không enforce policy?

Commands:

```bash
kubectl version
kubectl get nodes -o wide
kubectl get pods -n kube-system
kubectl get storageclass
kubectl get ingressclass
kubectl get svc -A
kubectl get events -A --sort-by=.lastTimestamp
```

Với K3s node:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 100 --no-pager
sudo cat /etc/rancher/k3s/config.yaml
```

Symptom thường gặp:

| Symptom | Cluster type hay gặp | Root cause |
|---|---|---|
| `LoadBalancer` mãi `pending` | Kind/Minikube/upstream bare-metal | Không có cloud LB/MetalLB/ServiceLB |
| Ingress không route | K3s/local | Traefik disabled, IngressClass sai, port mapping thiếu |
| PVC bound nhưng mất data sau reset | Local lab | Local path/host storage không durable |
| CI test pass nhưng cloud fail | Kind -> managed | CNI/IAM/LB/CSI khác nhau |

## Liên hệ với kiến thức đã biết

Hãy xem các distro/tool như environment runtime khác nhau cho cùng Kubernetes API contract. Giống việc code chạy trên local Postgres và cloud managed Postgres: SQL có thể giống, nhưng backup, network, IAM, HA, monitoring và performance profile khác nhau đáng kể.

## Tóm tắt

Ngày 3 giúp bạn chọn đúng công cụ. K3s là Kubernetes nhẹ, hữu ích cho lab/edge/small cluster. Kind rất tốt cho CI/test. Minikube và MicroK8s tiện cho learning/development. Managed Kubernetes thường là hướng pragmatic cho production cloud. API Kubernetes là phần portable; operational defaults mới là nơi khác biệt lớn.

## Câu hỏi tự kiểm tra

1. K3s khác Kubernetes upstream tự dựng ở những điểm operational nào?
2. Vì sao Kind phù hợp CI nhưng không đại diện đầy đủ cho production networking/storage?
3. Nếu `Service type LoadBalancer` bị `pending` trên local cluster, bạn nghĩ tới nguyên nhân nào?
4. Với small production trên K3s, những checklist nào bắt buộc trước khi go-live?
5. Khi chuyển từ K3s lab sang EKS/GKE/AKS, phần nào của manifest thường portable và phần nào cần đổi?

## Tài liệu tham khảo

- K3s Documentation: https://docs.k3s.io/
- K3s Architecture: https://docs.k3s.io/architecture
- K3s Packaged Components: https://docs.k3s.io/installation/packaged-components
- Kubernetes Components: https://kubernetes.io/docs/concepts/overview/components/
- kind Documentation: https://kind.sigs.k8s.io/docs/
- kind Quick Start: https://kind.sigs.k8s.io/docs/user/quick-start/
