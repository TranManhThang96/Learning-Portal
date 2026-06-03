# Document - Day 06: Worker Node Debugging Guide

## Worker node responsibility map

| Lớp | Component | Trách nhiệm | Tín hiệu debug |
|---|---|---|---|
| Node registration | kubelet | Đăng ký Node và heartbeat | `kubectl get nodes`, Node conditions, Lease |
| Pod lifecycle | kubelet | Mount volume, run probes, update status | `describe pod`, kubelet logs |
| Container execution | container runtime | Pull image, start/stop container | `crictl ps`, `crictl images`, Pod events |
| Pod network | CNI plugin | Tạo network namespace/IP/routes | CNI pods/logs, Pod IP, node routes |
| Service routing | kube-proxy/dataplane | Route ClusterIP/NodePort đến endpoints | Service, EndpointSlice, node rules |
| Resource pressure | kubelet/cgroups | Enforce requests/limits, eviction | `describe node`, `top`, events |

## Node datapath diagram

```text
API server PodSpec
    |
 kubelet trên node
    |
    +-- CRI/containerd: image -> container process
    +-- CNI: network namespace -> Pod IP
    +-- volume manager: mount config/secret/PVC
    |
 Pod condition Ready=True
    |
EndpointSlice có Pod IP
    |
kube-proxy/dataplane: Service VIP -> Pod IP
```

## Glossary nhanh

| Thuật ngữ | Nghĩa thực tế khi debug |
|---|---|
| `Lease` | Heartbeat nhẹ của node trong namespace `kube-node-lease` |
| `eviction` | Kubelet đẩy Pod khỏi node vì pressure hoặc chính sách tài nguyên |
| `EndpointSlice` | Danh sách backend của Service theo slice nhỏ, nên kiểm tra trước khi debug dataplane |
| `dataplane` | Cơ chế chuyển packet thật trên node: `iptables`, `IPVS`, eBPF hoặc CNI-specific |

## Node commands

Cluster-side:

```bash
kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl get lease -n kube-node-lease
kubectl top nodes
kubectl top pods -A
kubectl get events -A --sort-by=.lastTimestamp
```

Pod-side:

```bash
kubectl get pod <pod> -o wide
kubectl describe pod <pod>
kubectl logs <pod>
kubectl logs <pod> --previous
kubectl exec -it <pod> -- sh
```

K3s node-side:

```bash
sudo systemctl status k3s
sudo systemctl status k3s-agent
sudo journalctl -u k3s -n 200 --no-pager
sudo journalctl -u k3s-agent -n 200 --no-pager
sudo k3s crictl ps
sudo k3s crictl images
sudo k3s crictl pods
```

## Node conditions quick reference

| Condition | Healthy value | Khi bất thường | Kiểm tra tiếp |
|---|---|---|---|
| `Ready` | `True` | `False`/`Unknown` | kubelet/agent logs, CNI, runtime, network |
| `MemoryPressure` | `False` | Memory thiếu, eviction risk | `kubectl top`, app memory, limits |
| `DiskPressure` | `False` | Image/log/ephemeral storage đầy | Disk usage, image GC, logs |
| `PIDPressure` | `False` | Quá nhiều process | Process leak, pod density |
| `NetworkUnavailable` | `False` | CNI chưa ready | CNI pods/logs, node routes |

## Pod status to component mapping

| Pod status/reason | Nghi ngờ đầu tiên | Command |
|---|---|---|
| `Pending` không có `nodeName` | Scheduler | `kubectl describe pod` |
| `Pending` có `nodeName` | Kubelet/CNI/volume/runtime | `describe pod`, node logs |
| `ContainerCreating` lâu | Image pull, CNI, volume mount | events, `journalctl`, CSI/CNI logs |
| `ImagePullBackOff` | Registry/runtime/auth | events, imagePullSecret |
| `CrashLoopBackOff` | App crash/probe/config | `logs --previous`, `describe pod` |
| `Running` nhưng not ready | Readiness probe/app dependency | `describe pod`, app logs |
| `Evicted` | Node pressure | `describe pod`, `describe node` |

## Service routing checklist

Trước khi debug kube-proxy, kiểm tra object-level trước:

```bash
kubectl get svc <svc>
kubectl describe svc <svc>
kubectl get endpoints <svc>
kubectl get endpointslice -l kubernetes.io/service-name=<svc>
kubectl get pods -l <selector> -o wide
```

Nếu endpoint rỗng:

- Selector sai.
- Pod chưa `Ready`.
- Pod không có label đúng.
- Namespace sai.

Nếu endpoint có nhưng traffic fail:

- Test từ Pod cùng namespace.
- Test DNS name và ClusterIP.
- Kiểm tra NetworkPolicy nếu có.
- Kiểm tra kube-proxy/CNI logs.

Debug Pod:

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
curl -v http://<service-name>.<namespace>.svc.cluster.local
curl -v http://<cluster-ip>
```

## Incident checklist 5 phút đầu

```text
1. Scope: một Pod, một Deployment, một namespace, một node hay nhiều node?
2. Pod đã có nodeName chưa? Nếu chưa, ưu tiên scheduler/resource/taint.
3. Nếu đã có nodeName, đọc describe pod + events để tách image/CNI/volume/probe.
4. Nếu nhiều Pod lỗi trên cùng node, đọc Node conditions, Lease và kubelet/runtime logs.
5. Nếu Service fail, xác minh EndpointSlice trước khi nghi kube-proxy/dataplane.
```

## Node maintenance mini-checklist

Lab:

```bash
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl uncordon <node-name>
```

Production notes:

- Kiểm tra `PodDisruptionBudget` trước khi drain.
- Không drain node chứa stateful workload nếu chưa hiểu volume/failover.
- Cordon trước để ngăn Pod mới schedule vào node.
- Theo dõi rollout và error rate sau maintenance.

## Common worker-node failure modes

| Failure | Dấu hiệu | Mitigation lab | Mitigation production |
|---|---|---|---|
| Registry không truy cập được | `ImagePullBackOff` | Sửa image/tag/network | Registry mirror, credentials, rollback |
| App crash | `CrashLoopBackOff` | Xem `logs --previous` | Rollback, feature flag, config fix |
| Node agent down | Node `NotReady` | Restart `k3s-agent` | Cordon/drain, replace node |
| Disk full | `DiskPressure`, eviction | Xóa image/log lab | Expand disk, image GC, log policy |
| CNI lỗi | Pod không có IP, DNS fail | Restart CNI/lab reset | Incident theo CNI, rollback config |
| Selector sai | Service no endpoint | Patch selector | Fix manifest/CI validation |

## Answer key ngắn

| Câu hỏi | Đáp án ngắn |
|---|---|
| Scheduler và kubelet khác nhau thế nào? | Scheduler chọn node; kubelet trên node đó chạy PodSpec thành container thật |
| Vì sao `Running` chưa chắc nhận traffic? | Service chỉ route Pod `Ready` có endpoint hợp lệ |
| `ImagePullBackOff` kiểm tra component nào trước? | Runtime/registry qua events, image name/tag, credential và kubelet/runtime logs |
| Node `NotReady` thường do gì? | Kubelet/agent down, CNI/runtime lỗi, network tới API server lỗi hoặc node pressure |
| Vì sao K3s dùng `sudo k3s crictl`? | K3s đóng gói `containerd` và helper `crictl` trỏ đúng socket/runtime của K3s |
