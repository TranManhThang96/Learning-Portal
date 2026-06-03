# Day 07: kubectl mastery và resource inspection

## Mục tiêu bài học

- Dùng thành thạo `kubectl` để đọc desired state, observed state và events của resource.
- Quản lý `context`, `namespace`, output formats, label filtering và watch loop.
- Viết được các truy vấn `jsonpath`/custom columns đủ dùng cho debug hằng ngày.
- Dùng được `--field-selector`, `kubectl wait`, `kubectl diff`, `--dry-run=server` và `kubectl auth can-i` trong workflow kiểm tra thay đổi.
- Biết chọn đúng command khi gặp lỗi `Pending`, `ImagePullBackOff`, `CrashLoopBackOff`, Service no endpoint.
- Phân biệt cách dùng `kubectl` trong K3s, Kubernetes chuẩn và managed Kubernetes.

## Vấn đề cần giải quyết

Kubernetes có nhiều lớp controller, status và event. Nếu chỉ chạy `kubectl get pods`, bạn thường thấy symptom rất muộn và thiếu ngữ cảnh. Senior engineer cần đọc được:

- Object spec nói Kubernetes muốn gì.
- Object status nói cluster đã làm được gì.
- Events nói controller/kubelet gặp lỗi ở bước nào.
- Owner references nói resource do ai tạo và ai reconcile.
- Labels/selectors nói các resource có khớp nhau không.

`kubectl` là debugger chính của Kubernetes API. Thành thạo nó giúp bạn tránh nhảy thẳng vào SSH node hoặc restart workload khi chưa biết root cause.

## Mental Model

```text
kubectl không "điều khiển node" trực tiếp.
kubectl gọi kube-apiserver.
kube-apiserver đọc/ghi object.
Controller/kubelet thấy object thay đổi và reconcile.
kubectl đọc lại status/events để bạn hiểu reconciliation đang kẹt ở đâu.
```

Hãy nghĩ `kubectl` như SQL client cho cluster state, cộng thêm một số lệnh tiện dụng để stream logs, exec và theo dõi rollout.

## Lý thuyết cốt lõi

### Context, cluster, user và namespace

`kubeconfig` chứa nhiều `cluster`, `user` và `context`. Một `context` là tổ hợp cluster + user + namespace mặc định.

Các lệnh quan trọng:

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <context-name>
kubectl config set-context --current --namespace=<namespace>
kubectl cluster-info
kubectl version
```

Trong K3s, kubeconfig mặc định thường nằm ở `/etc/rancher/k3s/k3s.yaml`. Có thể dùng:

```bash
sudo k3s kubectl get nodes
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get pods -A
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

### Resource discovery

Không cần nhớ mọi API resource. Hãy hỏi API server:

```bash
kubectl api-resources
kubectl api-versions
kubectl explain pod
kubectl explain pod.spec.containers
kubectl explain deployment.spec.strategy
```

`kubectl explain` đặc biệt hữu ích khi bạn không chắc field nằm ở đâu trong YAML.

### Output formats

`kubectl get` không chỉ để xem table.

```bash
kubectl get pods -A -o wide
kubectl get pod <pod> -o yaml
kubectl get deployment <name> -o json
kubectl get pods -o name
kubectl get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,PHASE:.status.phase
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'
```

Shell portability:

- Các lệnh trong course ưu tiên Linux/WSL/Bash. Khi chạy PowerShell, tránh phụ thuộc `grep`, `head`, `export` và shell substitution kiểu `$()`.
- `export KUBECONFIG=/etc/rancher/k3s/k3s.yaml` tương đương PowerShell: `$env:KUBECONFIG='/etc/rancher/k3s/k3s.yaml'`.
- Nếu JSON patch bị shell quote làm hỏng, dùng `--patch-file patch.json` hoặc apply manifest YAML thay vì cố nhồi JSON dài vào một dòng.
- JSONPath đơn giản bằng single quote thường chạy được trong Bash và PowerShell; nếu output rỗng, kiểm tra lại field bằng `-o yaml` trước khi kết luận object không có dữ liệu.

Quy tắc thực tế:

| Format | Khi dùng |
|---|---|
| Table mặc định | Scan nhanh |
| `-o wide` | Cần node/IP/image thêm |
| `-o yaml` | Đọc đầy đủ spec/status/managedFields nếu cần |
| `-o json` | Pipe qua `jq` hoặc tooling |
| `jsonpath` | Lấy field chính xác trong script/debug nhanh |
| `custom-columns` | Tạo bảng dễ đọc cho nhiều object |

### Labels, selectors và owner references

Labels là cách Kubernetes nối các resource với nhau. Service chọn Pod qua selector. ReplicaSet chọn Pod qua selector. Deployment tạo ReplicaSet bằng Pod template.

```bash
kubectl get pods --show-labels
kubectl get pods -l app=web
kubectl get svc web -o yaml
kubectl get endpoints,endpointslice -l kubernetes.io/service-name=web
kubectl get pod <pod> -o jsonpath='{.metadata.ownerReferences[*].kind}{" "}{.metadata.ownerReferences[*].name}{"\n"}'
```

Khi Service không có endpoint, kiểm tra selector trước khi nghi kube-proxy.

### Field selector, wait, dry-run, diff và auth check

Label selector lọc theo metadata do bạn đặt; `field-selector` lọc theo field được API server hỗ trợ. Hai loại này bổ sung cho nhau:

```bash
kubectl get pods -l app=web
kubectl get pods --field-selector=status.phase=Running
kubectl get events --field-selector type=Warning --sort-by=.lastTimestamp
```

Trong automation, tránh `sleep` mù:

```bash
kubectl wait --for=condition=Available deployment/web --timeout=60s
kubectl rollout status deployment/web --timeout=60s
```

Trước khi thay đổi object:

```bash
kubectl apply --dry-run=server -f app.yaml
kubectl diff -f app.yaml
kubectl auth can-i get pods -n day07
kubectl auth can-i create deployments.apps -n day07
```

`--dry-run=server` chạy validation/admission phía API server nhưng không persist object. `kubectl diff` cho biết manifest sẽ thay đổi gì so với live object. `auth can-i` giúp phân biệt lỗi manifest với lỗi quyền.

### Events

Events là timeline ngắn hạn của cluster. Đây thường là nguồn sự thật nhanh nhất cho lỗi scheduling, image pull, mount volume và probe.

```bash
kubectl get events -A --sort-by=.lastTimestamp
kubectl events --all-namespaces
kubectl events --for pod/<pod-name> --watch
kubectl describe pod <pod>
```

`describe` gom spec tóm tắt, status và events gần đây theo resource. Khi incident xảy ra, `describe` thường nhanh hơn đọc YAML thô.

### Logs, exec và debug

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous
kubectl logs deployment/<deployment> --all-containers=true
kubectl exec -it <pod> -- sh
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
kubectl debug node/<node-name> -it --image=busybox
```

`logs --previous` quan trọng với `CrashLoopBackOff` vì container hiện tại có thể vừa restart, còn log lỗi nằm ở instance trước.

## Deep Dive: Cách kubectl tương tác với API server

Luồng một lệnh phổ biến:

```text
kubectl apply -f app.yaml
-> đọc kubeconfig để biết API server, user credential, namespace
-> gửi request đến kube-apiserver
-> kube-apiserver chạy authn/authz/admission/validation
-> object được persist vào datastore
-> controller/kubelet watch object và reconcile
-> kubectl get/describe/logs đọc status/log subresource hoặc kubelet proxy
```

Điểm quan trọng:

- `kubectl apply` tạo hoặc cập nhật desired state, không đảm bảo Pod đã chạy.
- `kubectl wait` và `kubectl rollout status` mới kiểm tra tiến trình đạt trạng thái mong muốn.
- `kubectl delete pod` với Pod thuộc Deployment chỉ xóa instance; ReplicaSet sẽ tạo lại Pod.
- `kubectl edit` tiện cho lab nhưng production nên đi qua Git/CI/GitOps để tránh config drift.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Kubeconfig | `/etc/rancher/k3s/k3s.yaml`, có `k3s kubectl` embedded | Tùy kubeadm/tooling | Tạo bằng cloud CLI, IAM tích hợp |
| Namespace hệ thống | `kube-system`, có thể có `traefik`, `local-path-provisioner`, `svclb-*` | Tùy addon đã cài | Nhiều addon/cloud controller riêng |
| Debug node | Thường dùng `sudo k3s crictl`, `journalctl -u k3s/k3s-agent` | `crictl`, `journalctl -u kubelet` | Có thể cần cloud logging, SSM, node shell policy |
| LoadBalancer lab | ServiceLB nếu bật | MetalLB hoặc cloud integration tự cài | Cloud Load Balancer thật |
| RBAC/IAM | Kubernetes RBAC là chính | RBAC + identity tự quản | RBAC + IAM/cloud identity |

Command `kubectl` cấp API gần như giống nhau, nhưng object hệ thống và quyền truy cập node/log có thể rất khác.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `kubectl apply` trực tiếp | Lab, hotfix có kiểm soát | Nhanh, ít overhead | Dễ drift nếu không ghi lại | Git state lệch cluster |
| GitOps/CI apply | Production | Chậm hơn nhưng traceable | Cần pipeline/controller | Pipeline lỗi làm rollout chậm |
| `jsonpath` | Debug/script nhẹ | Nhanh, không cần tool thêm | Syntax khó đọc | Query sai field, output rỗng |
| `jq` với JSON | Phân tích phức tạp | Mạnh hơn cho transform | Cần cài `jq` | Script phụ thuộc tool |
| `kubectl edit` | Lab, emergency nhỏ | Tác động ngay | Không review | Drift, khó audit |
| `kubectl patch` | Sửa field nhỏ, automation | Nhanh | Dễ patch sai path | Object không như mong muốn |

### Best Practices

Nên làm:

- Luôn xác nhận context trước khi thao tác cluster quan trọng.
- Dùng namespace riêng cho lab và cleanup bằng namespace.
- Đọc `describe` + events trước khi sửa manifest.
- Dùng labels/selectors để nối Pod, Service, ReplicaSet, Deployment.
- Dùng `rollout status`/`wait` trong automation thay vì sleep mù.
- Lưu các command JSONPath hay dùng vào cheatsheet.

Tránh làm:

- Chạy `delete`/`patch` khi chưa kiểm tra context/namespace.
- Debug Service bằng cách restart Pod khi endpoint đang rỗng do selector sai.
- Dùng `kubectl edit` như quy trình production thường ngày.
- Xóa Pod thuộc Deployment và nghĩ workload đã biến mất.

## Performance Considerations

- `kubectl get pods -A -o yaml` trên cluster lớn có thể trả về rất nhiều dữ liệu; lọc namespace/label khi có thể.
- Watch nhiều resource liên tục tạo tải cho API server; dùng có chủ đích.
- `kubectl logs --all-containers` trên nhiều Pod có thể nặng và khó đọc; giới hạn bằng `--tail`, label selector hoặc container cụ thể.
- JSONPath/custom columns giảm lượng output, hữu ích khi API latency cao.
- Trong incident, command quá rộng như `get events -A` vẫn hữu ích nhưng nên chuyển nhanh sang namespace/resource cụ thể.

## Debugging Checklist

Xác nhận ngữ cảnh:

```bash
kubectl config current-context
kubectl config get-contexts
kubectl get ns
```

Cluster overview:

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get events -A --sort-by=.lastTimestamp
```

Một Pod lỗi:

```bash
kubectl describe pod <pod>
kubectl logs <pod> --previous
kubectl get pod <pod> -o yaml
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].state}{"\n"}'
```

Service không route:

```bash
kubectl describe svc <service>
kubectl get endpoints,endpointslice
kubectl get pods --show-labels
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
```

Deployment rollout:

```bash
kubectl rollout status deployment/<name>
kubectl rollout history deployment/<name>
kubectl describe deployment <name>
kubectl wait --for=condition=Available deployment/<name> --timeout=60s
```

## Liên hệ với kiến thức đã biết

Nếu bạn quen database, `kubectl get -o jsonpath` giống query lấy field cần thiết. Nếu bạn quen distributed systems, events là timeline của control loop. Nếu bạn quen microservices debugging, labels/selectors tương tự service discovery metadata: sai metadata thì traffic không tới đúng instance.

## Tóm tắt

`kubectl` là công cụ đọc và thay đổi Kubernetes API state. Debug tốt bắt đầu từ context đúng, resource đúng, namespace đúng, rồi đọc spec/status/events theo thứ tự. Học cách lọc output và truy vấn field giúp bạn đi từ symptom đến root cause nhanh hơn nhiều so với thao tác thử-sai.

## Câu hỏi tự kiểm tra

1. `kubectl apply` khác gì với việc Pod đã `Ready`?
2. Khi Service không có endpoint, bạn kiểm tra những field nào?
3. Vì sao `logs --previous` quan trọng với `CrashLoopBackOff`?
4. Khi nào dùng `jsonpath`, khi nào dùng `-o yaml`?
5. Trong K3s, kubeconfig mặc định thường ở đâu?

## Tài liệu tham khảo

- Kubernetes kubectl Reference: https://kubernetes.io/docs/reference/kubectl/
- Kubernetes Debug Running Pods: https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- Kubernetes JSONPath Support: https://kubernetes.io/docs/reference/kubectl/jsonpath/
- Kubernetes Events: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_events/
- K3s Cluster Access: https://docs.k3s.io/cluster-access
