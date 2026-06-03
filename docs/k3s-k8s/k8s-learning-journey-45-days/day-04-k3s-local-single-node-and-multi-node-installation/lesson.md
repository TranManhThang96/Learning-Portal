# Day 04: Cài đặt K3s trực tiếp single-node và multi-node

## Mục tiêu bài học

- Cài được K3s `server` single-node và xác minh cluster bằng `kubectl`.
- Hiểu kubeconfig, node token, luồng `agent` join vào `server`.
- Dựng được lab multi-node tối thiểu với một control-plane node và một worker node.
- Biết cách reset/uninstall K3s đúng node, đúng vai trò.
- Nhận diện khác biệt giữa `k3d` local lab, K3s cài trực tiếp, Kubernetes tự dựng và managed Kubernetes khi tạo cluster.

## Vấn đề cần giải quyết

Từ ngày 1-3 bạn đã có mental model và một lab nhanh bằng `k3d`. Ngày 4 chuyển sang K3s cài trực tiếp trên Linux/VM để thấy cách cluster thật được bootstrapped bằng `systemd`, kubeconfig, token và node join. Nếu setup lab không rõ ràng, các ngày sau sẽ bị nhiễu bởi lỗi kubeconfig, token, firewall, CNI, DNS hoặc node join. Mục tiêu không phải chỉ chạy một lệnh cài đặt, mà là hiểu K3s đã cài gì, file nào quan trọng, khi node không join thì debug từ đâu.

## Mental Model

```text
K3s server = Kubernetes API + control plane + datastore + packaged addons
K3s agent  = kubelet + kube-proxy + container runtime, kết nối về server

kubeconfig = credential để client nói chuyện với API server
node token = credential để agent/server mới join cluster
```

K3s được cài như một `systemd service`. Sau khi service chạy, `k3s server` expose Kubernetes API trên port `6443`, tạo kubeconfig ở `/etc/rancher/k3s/k3s.yaml`, và tạo join token ở `/var/lib/rancher/k3s/server/node-token`. Agent node join bằng `K3S_URL` và `K3S_TOKEN`.

```text
kubectl/admin
    |
    | kubeconfig -> https://<server-ip>:6443
    v
K3s server
    |  API server + scheduler + controllers + datastore
    |  node-token
    v
K3s agent
    |  kubelet + kube-proxy + containerd
    v
Workload Pods
```

## Lý thuyết cốt lõi

### Single-node K3s

Single-node là cách nhanh nhất để có một Kubernetes cluster thật cho lộ trình này:

```bash
curl -sfL https://get.k3s.io | sh -
```

Theo tài liệu K3s, lệnh mặc định này cài K3s server, tạo kubeconfig ở `/etc/rancher/k3s/k3s.yaml`, tạo join token ở `/var/lib/rancher/k3s/server/node-token`, và sau đó có thể xác minh bằng:

```bash
sudo kubectl get nodes
```

Với lab dài ngày hoặc production, không nên chỉ dựa vào command history. Chọn version K3s đã chuẩn hóa và ghi config bền vững trước khi cài:

```bash
export INSTALL_K3S_VERSION="<pinned-k3s-version>"

sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml >/dev/null <<'EOF'
write-kubeconfig-mode: "0644"
# tls-san:
#   - "<server-ip-or-dns>"
# disable:
#   - traefik
EOF

curl -sfL https://get.k3s.io | sh -
```

Thay `<pinned-k3s-version>` bằng release K3s mà bạn đã chọn/test cho lab hoặc môi trường production-like. Trong lab mới bắt đầu, bạn có thể dùng default để giảm ma sát. Khi cần tái lập hoặc harden, pin version và config file giúp audit rõ hơn.

Trong lab, single-node đủ cho `Pod`, `Deployment`, `Service`, `Ingress`, `ConfigMap`, `Secret`, `PVC` với local storage. Nhưng nó không mô phỏng tốt node failure, scheduling đa node, network path giữa node, hoặc upgrade/maintenance.

### Kubeconfig

`kubeconfig` là file client config cho `kubectl`. Nó chứa:

- API server endpoint.
- Cluster certificate authority.
- User credential.
- Context hiện tại.

Trên node K3s server, kubeconfig mặc định trỏ về `https://127.0.0.1:6443`. Nếu copy file này sang máy khác, cần đổi `server:` thành IP/DNS mà máy client truy cập được.

Ví dụ:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
kubectl get nodes
```

Không commit kubeconfig thật vào Git. Nó là credential có quyền truy cập cluster.

### Multi-node K3s

K3s phân biệt hai vai trò chính:

- `server`: chạy control plane và datastore.
- `agent`: chạy workload như worker node.

Agent join cluster bằng API endpoint của server và token:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<node-token> sh -
```

Trước khi join, kiểm tra tối thiểu:

- Server và worker có hostname khác nhau, IP ổn định, đồng bộ thời gian.
- Worker reach được `https://<server-ip>:6443/version`.
- Firewall/security group cho phép TCP `6443` từ agent đến server.
- Nếu dùng Flannel VXLAN mặc định, node-to-node UDP `8472` không bị chặn.
- Nếu chạy nhiều K3s server HA embedded `etcd`, mở thêm traffic `2379-2380` giữa server nodes theo thiết kế.
- Pod/service CIDR không trùng với network thật của VM/VPC.

Luồng join:

1. Agent gọi API server qua `K3S_URL`.
2. Token được kiểm tra để xác thực node join.
3. Agent start kubelet/container runtime.
4. Kubelet đăng ký `Node` object với API server.
5. Scheduler có thể đặt Pod lên node mới nếu node `Ready` và không bị taint/cordon.

### Reset và uninstall

K3s tạo script uninstall riêng theo vai trò:

```bash
# Trên server node
/usr/local/bin/k3s-uninstall.sh

# Trên agent node
/usr/local/bin/k3s-agent-uninstall.sh
```

Các script này dừng service, xóa binary/link, xóa dữ liệu local của K3s và các Pod đang chạy trên node đó. Vì vậy trong production không chạy tùy tiện. Trong lab, đây là cách reset sạch khi cluster bị hỏng nặng.

## Deep Dive: Install script thật sự làm gì

Install script của K3s chủ yếu làm các việc sau:

- Tải binary K3s phù hợp.
- Tạo `systemd service` tương ứng `k3s` hoặc `k3s-agent`.
- Ghi environment/config cần thiết.
- Enable và start service.
- Cài các symlink hoặc helper command như `kubectl`, `crictl`, `ctr` tùy môi trường.
- Với server, bootstrap datastore và render packaged manifests.

Điểm cần nhớ: K3s không chỉ là một binary chạy nền. Nó còn quản lý nhiều packaged component như CoreDNS, Traefik, local storage provisioner, metrics-server, ServiceLB tùy phiên bản/cấu hình. Khi bạn thấy các Pod trong `kube-system`, hãy phân biệt component Kubernetes core với addon do K3s đóng gói.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s cài trực tiếp | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Tạo cluster | Install script hoặc binary K3s | kubeadm/tool riêng, tự chọn CNI/CSI/addon | Cloud API/console/IaC |
| Control plane | `k3s server` đóng gói nhiều component | Component thường chạy static pod/systemd riêng | Provider quản lý |
| Worker join | `K3S_URL` + `K3S_TOKEN` | `kubeadm join` + bootstrap token/cert | Node group/agent do cloud tích hợp |
| Kubeconfig | `/etc/rancher/k3s/k3s.yaml` | `/etc/kubernetes/admin.conf` thường gặp | Sinh từ cloud CLI |
| LoadBalancer | ServiceLB/MetalLB/tùy cấu hình | Cần cài riêng nếu bare-metal | Cloud Load Balancer |
| Storage | local-path mặc định cho lab | Cần cài CSI/provisioner | Cloud CSI |
| Trách nhiệm team | OS, K3s, backup, upgrade, workload | Gần như toàn bộ cluster | Workload, node pool, policy, cost, observability |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Single-node K3s | Học nhanh, laptop/VM nhỏ | Ít overhead, không có network cross-node | Thấp | Một node hỏng là mất toàn bộ lab |
| Multi-node K3s | Học scheduling, node lifecycle, service routing | Tốn thêm CPU/RAM/network | Trung bình | Firewall/token/CNI làm node không `Ready` |
| SQLite default | Single-node lab | Nhẹ, đơn giản | Thấp | Không phù hợp HA |
| Embedded etcd | HA K3s server | Cần disk/network ổn định | Cao hơn | etcd quorum/disk latency gây lỗi control plane |
| Install script nhanh | Lab, thử nghiệm | Setup nhanh | Thấp | Cấu hình rải rác nếu không ghi lại |
| Config file rõ ràng | Lab dài ngày/small prod | Không khác đáng kể | Trung bình | Sai config làm service không start |

### Best Practices

Nên làm:

- Ghi lại OS, IP, hostname, vai trò node, K3s version và command cài đặt.
- Pin K3s version cho lab dài ngày hoặc môi trường production-like; tránh để install script tự chọn version khác nhau giữa các node.
- Ghi config vào `/etc/rancher/k3s/config.yaml` trước khi cài nếu bạn cần giữ lựa chọn như `tls-san`, disable packaged component hoặc datastore mode.
- Dùng hostname ổn định, IP không thay đổi trong suốt lab.
- Copy kubeconfig vào `~/.kube/config` cho user thường, nhưng bảo vệ file như secret.
- Mở tối thiểu API server port `6443` từ agent đến server và kiểm tra CNI/node-to-node traffic nếu làm multi-node.
- Sau khi join node, luôn kiểm tra `kubectl get nodes -o wide` và Pod trong `kube-system`.
- Trong production K3s, viết config vào `/etc/rancher/k3s/config.yaml` thay vì chỉ dựa vào command history.

Tránh làm:

- Chạy uninstall script trên node production nếu chưa có drain/backup/rollback plan.
- Commit node token hoặc kubeconfig vào repository.
- Dùng `local-path-provisioner` cho dữ liệu production quan trọng.
- Debug node join chỉ bằng `kubectl`; khi node chưa join, phải đọc `systemd` và journal logs trên node.

## Performance Considerations

- Single-node K3s đủ nhẹ cho laptop/VM nhỏ, nhưng image pull, disk I/O và memory pressure vẫn ảnh hưởng toàn bộ cluster.
- Multi-node lab cần network ổn định giữa server và agent. CNI overlay có thể tạo thêm overhead network so với host networking.
- Disk chậm trên server node làm API/datastore phản hồi chậm, kéo theo controller và scheduler chậm.
- `local-path` storage dùng disk local của node; performance có thể tốt trong lab nhưng failure semantics không giống network/block storage production.
- Trên VM nhỏ, tránh chạy quá nhiều addon cùng lúc; ưu tiên học từng lớp để không lẫn lỗi thiếu tài nguyên với lỗi Kubernetes concept.

## Debugging Checklist

Khi install hoặc join lỗi, kiểm tra theo thứ tự:

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
```

Trên K3s server:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 100 --no-pager
sudo cat /var/lib/rancher/k3s/server/node-token
sudo ss -lntp | grep 6443
```

Trên K3s agent:

```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 100 --no-pager
curl -k https://<server-ip>:6443/version
```

Symptom thường gặp:

| Symptom | Root cause phổ biến | Hướng xử lý |
|---|---|---|
| `kubectl` báo connection refused | K3s server chưa chạy hoặc kubeconfig sai endpoint | Kiểm tra `systemctl status k3s`, sửa kubeconfig |
| Agent không xuất hiện trong `kubectl get nodes` | Sai token, không reach được `6443`, DNS/IP sai | Kiểm tra token, firewall, `journalctl -u k3s-agent` |
| Node `NotReady` | CNI chưa chạy, kubelet lỗi, runtime lỗi | Xem Pod `kube-system`, describe node, journal logs |
| Pod trong `kube-system` pending | Thiếu tài nguyên hoặc node taint | `kubectl describe pod -n kube-system <pod>` |
| `LoadBalancer` không có external IP | Không có ServiceLB/MetalLB/cloud LB | Xác định loại cluster và LB implementation |

Lab fix thường là sửa config, restart service hoặc reinstall node. Production fix cần drain workload, bảo toàn data, kiểm soát blast radius và ghi incident notes.

## Liên hệ với kiến thức đã biết

Hãy nhìn K3s lab như môi trường staging cực nhỏ cho microservices. Kubeconfig giống credential/API endpoint trong hệ thống nội bộ. Node token giống bootstrap secret. Agent join giống thêm worker vào compute pool. Khác biệt lớn là Kubernetes có reconciliation liên tục: khi node join, control plane tự đưa nó vào scheduling pool; khi node mất, Pod và Node status phản ánh qua API.

## Tóm tắt

Ngày 4 tạo nền thực hành cho toàn bộ lộ trình. Bạn cần cài được K3s single-node, hiểu kubeconfig và token, join được agent node, biết uninstall/reset đúng cách, và debug được lỗi install/join ở cả lớp Kubernetes API lẫn lớp node/systemd.

## Câu hỏi tự kiểm tra

1. Kubeconfig khác node token ở điểm nào?
2. Vì sao single-node K3s không đủ để học node failure và scheduling đa node?
3. Khi agent không join cluster, bạn kiểm tra `kubectl` trước hay `journalctl` trước? Vì sao?
4. Nếu copy `/etc/rancher/k3s/k3s.yaml` sang máy khác, cần sửa gì?
5. Trong production K3s, vì sao nên dùng config file và backup plan thay vì chỉ dựa vào install command?

## Tài liệu tham khảo

- K3s Quick Start: https://docs.k3s.io/quick-start
- K3s Installation: https://docs.k3s.io/installation
- K3s Requirements: https://docs.k3s.io/installation/requirements
- K3s Uninstall: https://docs.k3s.io/installation/uninstall
- K3s Configuration File: https://docs.k3s.io/installation/configuration
- Kubernetes Nodes: https://kubernetes.io/docs/concepts/architecture/nodes/
