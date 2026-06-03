# Bài thực hành - Day 04: Cài đặt K3s trực tiếp single-node và multi-node

## Prerequisites

- Một hoặc hai VM/máy Linux. Khuyến nghị Ubuntu/Debian/Rocky tương đương.
- User có quyền `sudo`.
- Network từ worker đến server mở được `https://<server-ip>:6443`.
- Với multi-node dùng Flannel VXLAN mặc định, node-to-node UDP `8472` không bị firewall/security group chặn.
- Hostname mỗi node khác nhau, IP ổn định, time sync hoạt động.
- `curl` có sẵn.
- Nếu chỉ có một máy, làm Task 1-3 và đọc Task 4 như reference.

## Lab Scenario

Bạn cần dựng một K3s lab cho toàn bộ lộ trình 45 ngày. Bản tối thiểu là single-node. Nếu có tài nguyên, thêm một worker để học node lifecycle, scheduling và failure scenario ở các ngày sau.

Core Path: Task 1-4 và Task 6 khoảng 105-115 phút khi đã có VM. Task lỗi join sai token là Stretch vì dễ mất thêm thời gian reinstall agent.

## Task 1: Cài K3s server single-node (25 phút)

### Mục tiêu

Cài được K3s server và xác minh control plane hoạt động.

### Các bước thực hiện

Trên node server:

```bash
hostname -f
ip addr
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
sudo kubectl get nodes -o wide
sudo kubectl get pods -A
```

Nếu muốn lab tái lập hơn, pin version và chuẩn bị config trước khi cài:

```bash
export INSTALL_K3S_VERSION="<pinned-k3s-version>"
sudo mkdir -p /etc/rancher/k3s
sudo tee /etc/rancher/k3s/config.yaml >/dev/null <<'EOF'
write-kubeconfig-mode: "0644"
EOF
curl -sfL https://get.k3s.io | sh -
```

Thay `<pinned-k3s-version>` bằng release K3s bạn đã chọn. Nếu chưa chọn version, dùng command cài mặc định ở trên cho lab ngày 04, rồi ghi lại version thực tế trong notes.

### Expected output

- Service `k3s` ở trạng thái `active`.
- `kubectl get nodes` có một node `Ready`.
- Namespace `kube-system` có các Pod như CoreDNS, Traefik/local-path/metrics-server tùy cấu hình K3s.

### Verification

```bash
sudo kubectl cluster-info
sudo kubectl get events -A --sort-by=.lastTimestamp
```

### Troubleshooting

- Nếu `curl` fail, kiểm tra DNS/proxy/firewall outbound.
- Nếu service không start, đọc `sudo journalctl -u k3s -n 100 --no-pager`.
- Nếu `kubectl` bị permission denied, dùng `sudo kubectl` trước, sau đó cấu hình kubeconfig cho user ở Task 2.

## Task 2: Cấu hình kubeconfig và inventory cluster (25 phút)

### Mục tiêu

Dùng `kubectl` bằng user thường và ghi lại state ban đầu của cluster.

### Các bước thực hiện

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

kubectl config current-context
kubectl version
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
kubectl get storageclass
kubectl get ingressclass
kubectl get svc -A
```

Nếu chạy `kubectl` từ máy khác, copy kubeconfig an toàn rồi đổi endpoint:

```bash
sed -i 's/127.0.0.1/<server-ip>/g' ~/.kube/config
kubectl cluster-info
```

### Expected output

Ghi vào notes:

- K3s/Kubernetes version.
- Node OS, internal IP, container runtime.
- StorageClass mặc định.
- IngressClass hiện có.
- Service `LoadBalancer` implementation nếu thấy `svclb`.

### Troubleshooting

- Nếu `kubectl` trỏ sai cluster, kiểm tra `kubectl config view --minify`.
- Nếu dùng remote kubeconfig mà timeout, kiểm tra endpoint `server:` và network đến port `6443`.

## Task 3: Lấy node token và chuẩn bị join worker (20 phút)

### Mục tiêu

Hiểu token join và kiểm tra network trước khi cài agent.

### Các bước thực hiện

Trên server:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Trên worker:

```bash
curl -k https://<server-ip>:6443/version
```

Nếu command trên trả JSON version, worker reach được API server.

Nếu lab multi-node dùng firewall/security group, kiểm tra thêm node-to-node UDP `8472` cho Flannel VXLAN mặc định và bảo đảm Pod/Service CIDR không trùng network VM/VPC.

### Expected output

- Có node token.
- Worker truy cập được `https://<server-ip>:6443/version`.

### Troubleshooting

- Nếu connection timeout, kiểm tra IP, route, security group/firewall.
- Nếu connection refused, kiểm tra `sudo systemctl status k3s` trên server.

## Task 4: Join worker node vào cluster (30 phút)

### Mục tiêu

Tạo multi-node K3s lab tối thiểu.

### Các bước thực hiện

Trên worker:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<node-token> sh -
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 50 --no-pager
```

Trên server hoặc máy có kubeconfig:

```bash
kubectl get nodes -o wide
kubectl describe node <worker-node-name>
kubectl get pods -A -o wide
```

### Expected output

- Worker xuất hiện trong `kubectl get nodes`.
- Node status là `Ready`.
- Một số Pod hệ thống có thể được schedule lên worker tùy cluster state.

### Verification

Tạo workload nhỏ:

```bash
kubectl create deployment day04-nginx --image=nginx:1.27 --replicas=3
kubectl get pods -o wide
kubectl delete deployment day04-nginx
```

Quan sát Pod có thể được phân bố qua nhiều node hay không.

## Stretch Task: Inject lỗi join sai token và debug (25 phút)

### Mục tiêu

Biết đọc lỗi node join từ agent logs.

### Lỗi cần tạo

Chỉ làm trên worker lab mới hoặc sau khi uninstall agent. Không làm trên node đang chạy workload quan trọng.

Trên worker, uninstall agent nếu đã join:

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
```

Join lại với token sai:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=wrong-token sh -
```

### Symptom

- Worker không xuất hiện hoặc không `Ready`.
- `k3s-agent` log có lỗi authentication/bootstrap.

### Cách điều tra

```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 100 --no-pager
kubectl get nodes -o wide
```

### Cách fix

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<correct-node-token> sh -
kubectl get nodes -o wide
```

## Task 6: Cleanup notes và reset tùy chọn (15 phút)

### Mục tiêu

Biết command reset nhưng không xóa cluster nếu còn dùng cho các ngày sau.

### Các bước thực hiện

Ghi lại:

- Server IP/hostname.
- Worker IP/hostname.
- K3s version.
- Kubeconfig path.
- Có giữ Traefik/ServiceLB/local-path mặc định hay không.

Nếu muốn reset lab:

```bash
# Worker trước
sudo /usr/local/bin/k3s-agent-uninstall.sh

# Server sau
sudo /usr/local/bin/k3s-uninstall.sh
```

## Common Pitfalls

- Copy kubeconfig sang máy khác nhưng quên đổi `127.0.0.1`.
- Dùng token cũ sau khi server đã reinstall.
- Firewall chặn port `6443`.
- Nhầm `k3s` service trên server với `k3s-agent` service trên worker.
- Xóa `/var/lib/rancher/k3s` mà không hiểu đang mất cluster state.

## Stretch Goals

- Tạo `/etc/rancher/k3s/config.yaml` cho server và ghi rõ các flag bạn muốn giữ lâu dài.
- Join thêm worker thứ hai, tạo `Deployment` 6 replicas và quan sát scheduling.
- Disable một packaged component trong lab mới, ví dụ Traefik, rồi xác minh khác biệt trong `kube-system`.
- Viết ADR ngắn: "Lab 45 ngày dùng single-node hay multi-node K3s?"
