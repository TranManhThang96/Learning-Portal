# Document - Day 04: K3s Installation Cheatsheet

## Lab topology khuyến nghị

| Node | Vai trò | CPU/RAM tối thiểu | Ghi chú |
|---|---|---:|---|
| `k3s-server-1` | K3s server/control plane | 2 CPU / 2-4 GB RAM | Chạy API server, datastore, packaged addons |
| `k3s-agent-1` | Worker | 1-2 CPU / 2 GB RAM | Join bằng token |
| `k3s-agent-2` | Worker tùy chọn | 1-2 CPU / 2 GB RAM | Dùng cho scheduling/failure lab |

Single-node lab có thể chỉ cần `k3s-server-1`. Multi-node lab nên dùng VM Linux riêng hoặc cloud VM nhỏ trong cùng network.

## Sơ đồ join server-agent

```text
admin kubectl
    |
    | kubeconfig
    v
k3s-server-1 :6443
    | node-token + API endpoint
    v
k3s-agent-1
```

Agent không join bằng cách copy Pod hay container từ server. Agent xác thực bằng token, đăng ký `Node` qua API server, rồi kubelet/containerd trên chính agent mới chạy workload.

## Network/firewall checklist

| Luồng | Port/protocol | Bắt buộc khi nào | Ghi chú |
|---|---|---|---|
| Agent -> server API | TCP `6443` | Mọi multi-node K3s | Test bằng `curl -k https://<server-ip>:6443/version` |
| Node -> node Flannel VXLAN | UDP `8472` | Khi dùng Flannel VXLAN mặc định | Nếu bị chặn, Pod cross-node/network DNS có thể lỗi |
| Server -> kubelet | TCP `10250` | Khi cần logs/exec/metrics tới node | Tùy firewall nội bộ, nên cho phép trong lab private network |
| Server -> server etcd | TCP `2379-2380` | K3s HA embedded etcd | Không cần cho single-server lab |
| SSH admin | TCP `22` | Lab VM | Giới hạn theo IP quản trị |

Ngoài port, kiểm tra hostname duy nhất, IP ổn định, time sync, DNS/proxy outbound để pull image, và Pod/Service CIDR không trùng với network thật.

## Command inventory

### Cài K3s server mặc định

```bash
curl -sfL https://get.k3s.io | sh -
sudo kubectl get nodes
sudo kubectl get pods -A
```

### Cài có pin version và config file

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

Dùng placeholder `<pinned-k3s-version>` cho version đã được team chọn và test, ví dụ một release K3s cùng minor với target production. Nếu chỉ học nhanh, command mặc định vẫn ổn; nếu muốn tái lập, pin version.

### Cấu hình kubeconfig cho user hiện tại

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config
kubectl get nodes -o wide
```

Nếu dùng kubeconfig từ máy khác, sửa endpoint:

```bash
sed -i 's/127.0.0.1/<server-ip>/g' ~/.kube/config
kubectl cluster-info
```

### Lấy node token

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Không paste token vào ticket/chat công khai. Xem nó như bootstrap secret.

### Join agent node

Chạy trên worker node:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<server-ip>:6443 K3S_TOKEN=<node-token> sh -
```

Xác minh từ server hoặc máy có kubeconfig:

```bash
kubectl get nodes -o wide
kubectl describe node <agent-node-name>
```

### Kiểm tra service và logs

Server:

```bash
sudo systemctl status k3s
sudo journalctl -u k3s -n 100 --no-pager
```

Agent:

```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 100 --no-pager
```

Network từ agent đến server:

```bash
curl -k https://<server-ip>:6443/version
```

### Uninstall/reset

Server node:

```bash
sudo /usr/local/bin/k3s-uninstall.sh
```

Agent node:

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
```

Sau uninstall, kiểm tra lại data/path trước khi cài lại:

```bash
sudo ls -la /etc/rancher || true
sudo ls -la /var/lib/rancher || true
```

## File và path quan trọng

| Path | Node | Ý nghĩa | Lưu ý |
|---|---|---|---|
| `/etc/rancher/k3s/k3s.yaml` | Server | Kubeconfig admin | Credential nhạy cảm |
| `/var/lib/rancher/k3s/server/node-token` | Server | Token join node | Không commit/chia sẻ rộng |
| `/etc/rancher/k3s/config.yaml` | Server/agent | Config bền vững | Nên dùng cho lab dài ngày/production |
| `/var/lib/rancher/k3s/` | Server/agent | Data runtime | Xóa có thể mất cluster data |
| `/var/lib/rancher/k3s/server/manifests/` | Server | Packaged/static manifests | Không sửa tùy tiện nếu do K3s quản lý |
| `/run/k3s/containerd/containerd.sock` | Node | Container runtime socket | Dùng khi debug runtime |

## Checklist sau khi cài

- [ ] `sudo systemctl status k3s` là `active`.
- [ ] `kubectl get nodes -o wide` thấy node `Ready`.
- [ ] `kubectl get pods -A` không có Pod core bị crash kéo dài.
- [ ] `kubectl get storageclass` thấy storage class lab nếu K3s cài local-path.
- [ ] `kubectl get ingressclass` xác định có Traefik hay không.
- [ ] `kubectl get svc -A` xác định ServiceLB/LoadBalancer behavior.
- [ ] Ghi lại K3s version, node IP, hostname, OS.

## Decision table: single-node hay multi-node

| Mục tiêu | Single-node | Multi-node |
|---|---|---|
| Học Kubernetes API | Đủ | Đủ |
| Học scheduling đa node | Không đủ | Tốt |
| Học node failure | Không đủ | Tốt |
| Học CNI cross-node | Không đủ | Tốt |
| Ít tài nguyên | Tốt | Tốn hơn |
| Lab ngày 4-14 | Đủ nếu máy yếu | Khuyến nghị nếu có tài nguyên |
| Lab networking/storage nâng cao | Hạn chế | Khuyến nghị |

## Troubleshooting matrix

| Dấu hiệu | Command kiểm tra | Nguyên nhân hay gặp | Fix trong lab |
|---|---|---|---|
| `kubectl` không connect | `kubectl cluster-info` | Kubeconfig sai endpoint | Sửa `server:` trong kubeconfig |
| Server service lỗi | `journalctl -u k3s` | Config sai, port conflict, thiếu quyền | Sửa config, restart service |
| Agent không join | `journalctl -u k3s-agent` | Sai token, sai URL, firewall | Lấy lại token, kiểm tra `6443` |
| Node `NotReady` | `kubectl describe node` | CNI/runtime/kubelet lỗi | Xem Pod `kube-system`, restart agent |
| CoreDNS pending | `kubectl describe pod -n kube-system` | Node taint/resource thiếu | Tăng RAM/CPU, kiểm tra taint |

## Ghi chú production

- Với K3s HA, không dùng single-node SQLite. Cần embedded etcd hoặc external datastore và thiết kế quorum/backup.
- `local-path-provisioner` tiện cho lab, không phải storage HA.
- Nếu dùng Traefik/ServiceLB mặc định, phải quyết định rõ có giữ cho production hay thay bằng ingress/LB chuẩn của tổ chức.
- Trước khi uninstall/reset node production, cần `cordon`, `drain`, backup data và rollback plan.
