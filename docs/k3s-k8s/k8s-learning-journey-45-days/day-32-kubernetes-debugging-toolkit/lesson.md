# Day 32: Kubernetes Debugging Toolkit

## Mục tiêu bài học

- Có quy trình debug Kubernetes có thứ tự thay vì chạy lệnh ngẫu nhiên.
- Biết dùng `get`, `describe`, `events`, `logs`, `exec`, `port-forward`, `top`, `rollout` và `debug`.
- Debug được lỗi Pod, Service, DNS, Endpoints/EndpointSlice và Ingress.
- Hiểu khi nào dùng ephemeral containers và debug image như `netshoot`.
- Biết viết incident note ngắn: symptom, scope, evidence, root cause, fix và prevention.

## Vấn đề cần giải quyết

Trong Kubernetes, cùng một symptom có thể đến từ nhiều lớp.

Ví dụ "API không gọi được service":

- Pod service đích không Running.
- Container Running nhưng không Ready.
- Service selector sai.
- Endpoints rỗng.
- Port hoặc `targetPort` sai.
- DNS không resolve.
- NetworkPolicy chặn.
- Ingress route sai.
- App bind sai interface.
- App trả 500 nhưng network vẫn tốt.

Nếu debug không có thứ tự, bạn sẽ mất thời gian ở lớp sai. Debug Kubernetes cần đi theo object graph.

## Mental Model

```text
User/client
  |
  v
Ingress / Gateway
  |
  v
Service DNS name
  |
  v
Service selector + port
  |
  v
EndpointSlice / Endpoints
  |
  v
Ready Pod IP + targetPort
  |
  v
Container process
  |
  +-- logs
  +-- probes
  +-- resources
  +-- config/secrets
```

Debug theo graph này giúp bạn xác định nhanh lỗi thuộc Kubernetes wiring hay application behavior.

## Quy trình debug cơ bản

### 1. Xác định symptom và scope

Trước khi chạy lệnh:

- Lỗi là gì: timeout, connection refused, DNS fail, 404, 500, TLS error?
- Ảnh hưởng một Pod, một service, một namespace hay toàn cluster?
- Bắt đầu từ lúc nào?
- Có rollout, config change, node change hoặc policy change gần đó không?

### 2. Kiểm tra desired state và actual state

```bash
kubectl get deploy,rs,pod,svc,endpoints,endpointslice -n <namespace> -o wide
kubectl describe deploy <name> -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

`get` cho overview. `describe` cho conditions và events gần object. Events cho timeline.

### 3. Kiểm tra resource usage nhanh

```bash
kubectl top nodes
kubectl top pods -n <namespace>
kubectl top pods -A --sort-by=cpu
```

`kubectl top` cần Metrics Server hoặc metrics API tương đương. Nếu lệnh không chạy được, hãy ghi rõ observability gap trong incident note thay vì kết luận CPU/memory không liên quan.

`top` cho usage hiện tại, không thay thế metrics lịch sử. Với CPU throttling, OOM hoặc spike ngắn, bạn vẫn cần Prometheus/cAdvisor, logs và events.

### 4. Kiểm tra logs

```bash
kubectl logs deploy/<name> -n <namespace> --tail=100
kubectl logs <pod> -n <namespace> -c <container> --previous
kubectl logs -l app=<app> -n <namespace> --since=10m --tail=200
```

Nếu Pod restart, luôn kiểm tra `--previous`.

### 5. Kiểm tra network từ trong cluster

Dùng debug/client Pod:

```bash
kubectl run debug --image=busybox:1.36 --restart=Never --command -- sleep 3600
kubectl exec debug -- nslookup <service>
kubectl exec debug -- wget -S -O- http://<service>:<port>/
```

Nếu có `nicolaka/netshoot`, bạn có thêm `dig`, `curl`, `tcpdump`, `ss`, `ip`, `openssl`.

### 6. Kiểm tra endpoints

Service chỉ route tới Pod Ready có label match selector.

```bash
kubectl describe svc <service>
kubectl get endpoints <service> -o wide
kubectl get endpointslice -l kubernetes.io/service-name=<service> -o wide
```

Endpoints rỗng thường là:

- Selector sai.
- Pod labels sai.
- Pod chưa Ready.
- Readiness probe fail.
- Service ở namespace sai.

### 7. Kiểm tra Ingress

```bash
kubectl get ingress -A
kubectl describe ingress <name> -n <namespace>
kubectl get svc,endpoints <backend-service> -n <namespace>
kubectl logs -n kube-system deploy/traefik --tail=100
```

Ingress chỉ là rule. Traffic thật còn phụ thuộc Ingress controller, Service backend, DNS/Host header và TLS config.

## Toolkit commands

### `kubectl get`

Dùng để nhìn overview nhanh:

```bash
kubectl get all -n <namespace>
kubectl get pod -o wide
kubectl get deploy,rs,pod,svc,endpoints,endpointslice -o wide
kubectl get pod --show-labels
```

### `kubectl describe`

Dùng để đọc:

- Conditions.
- Events.
- Image pull errors.
- Scheduling errors.
- Probe failures.
- Volume mount errors.

```bash
kubectl describe pod <pod>
kubectl describe svc <service>
kubectl describe ingress <ingress>
```

### `kubectl logs`

Dùng để đọc app output:

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous
kubectl logs deploy/<deployment>
```

### `kubectl exec`

Dùng khi container có shell/tool:

```bash
kubectl exec -it <pod> -- sh
kubectl exec <pod> -- printenv
kubectl exec <pod> -- wget -qO- http://service:port/healthz
```

Không phải image nào cũng có shell. Distroless image thường không có.

### `kubectl debug` và ephemeral containers

Ephemeral containers cho phép attach một debug container vào Pod đang chạy mà không rebuild image.

Ví dụ:

```bash
kubectl debug -it pod/<pod> --image=nicolaka/netshoot --target=<container>
```

Dùng khi:

- App image không có shell.
- Bạn cần network tools.
- Bạn muốn debug Pod context hiện tại.

Không dùng ephemeral container để "fix" production Pod thủ công. Nó là công cụ điều tra.

### `kubectl port-forward`

Dùng để truy cập service/pod nội bộ từ local:

```bash
kubectl port-forward svc/<service> 8080:80
kubectl port-forward pod/<pod> 8080:8080
```

Nếu port-forward tới Pod thành công nhưng Service fail, lỗi có thể nằm ở Service selector/port/endpoints.

### `kubectl top`

Dùng để lấy resource snapshot:

```bash
kubectl top nodes
kubectl top pods -n <namespace>
kubectl top pod <pod> -n <namespace>
```

Ý nghĩa đúng:

- CPU/memory đang dùng tại thời điểm query.
- Hữu ích để phát hiện Pod đang bão hòa resource.
- Không cho biết trực tiếp CPU throttling, lịch sử spike hoặc nguyên nhân restart.

### `kubectl rollout`

Dùng khi lỗi liên quan Deployment:

```bash
kubectl rollout status deploy/<name>
kubectl rollout history deploy/<name>
kubectl rollout undo deploy/<name>
```

Rollback là thao tác production nghiêm túc. Cần biết rollout nào gây lỗi trước khi undo.

## Debugging Checklist

### Pod không Running

Kiểm tra:

```bash
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp
```

Common causes:

- `ImagePullBackOff`.
- Scheduling fail vì resource/taint/node selector.
- Volume mount fail.
- Init container fail.
- Admission policy reject.

### Pod Running nhưng service không truy cập được

Kiểm tra:

```bash
kubectl get pod --show-labels
kubectl describe svc <service>
kubectl get endpoints <service> -o wide
kubectl get endpointslice -l kubernetes.io/service-name=<service> -o wide
kubectl exec <client> -- nslookup <service>
kubectl exec <client> -- wget -S -O- http://<service>:<port>/
```

Common causes:

- Service selector sai.
- `targetPort` sai.
- Pod không Ready.
- App bind `127.0.0.1` thay vì `0.0.0.0`.
- NetworkPolicy block.

### DNS fail

Kiểm tra:

```bash
kubectl exec <client> -- nslookup kubernetes.default
kubectl exec <client> -- nslookup <service>.<namespace>.svc.cluster.local
kubectl get pod -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
```

Common causes:

- Sai namespace.
- Service không tồn tại.
- CoreDNS lỗi.
- NetworkPolicy chặn DNS egress.
- Pod `dnsPolicy` hoặc `/etc/resolv.conf` bất thường.

### Ingress fail

Kiểm tra:

```bash
kubectl describe ingress <ingress>
kubectl get ingress <ingress> -o yaml
kubectl get svc,endpoints <backend-service>
kubectl logs -n kube-system deploy/traefik --tail=100
```

Common causes:

- Host/path rule sai.
- Backend service name/port sai.
- IngressClass mismatch.
- TLS secret sai.
- Controller không nhận Ingress.
- Service backend không có endpoints.

## Deep dive: Cách hoạt động bên trong

Khi bạn debug Kubernetes, phần lớn bằng chứng đến từ các controller đã reconcile object trước đó:

- Deployment controller tạo ReplicaSet và Pod theo desired state.
- EndpointSlice controller chỉ đưa Pod `Ready` và match selector vào endpoint list.
- kubelet cập nhật Pod conditions, restart count và probe status.
- Events được ghi bởi scheduler, kubelet, controller hoặc admission/webhook, nhưng không phải audit log dài hạn.
- Ingress controller watch Ingress/Service/EndpointSlice rồi tự cấu hình dataplane riêng.

Vì vậy thứ tự debug tốt là đọc object graph và conditions trước, sau đó mới đi vào packet/app-level. Nếu EndpointSlice rỗng, Ingress debug sâu thường chỉ làm mất thời gian.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Object graph Pod -> Service -> EndpointSlice -> Ingress giống nhau | Metrics Server, Ingress controller và NetworkPolicy phụ thuộc add-on |
| K3s local/lab | Traefik thường có sẵn, thuận tiện debug Ingress | Cách expose Traefik ra host tùy k3d/K3s direct install; `127.0.0.1` không luôn đúng |
| Self-managed production | Team kiểm soát metrics, ingress, CNI, policy và debug images | Phải chuẩn hóa runbook, RBAC debug, audit và tooling |
| EKS/GKE/AKS | `kubectl` workflow vẫn giống upstream | Cloud LB/Ingress controller, metrics add-on và IAM/RBAC integration có khác biệt theo provider |

## Trade-offs và Best Practices

### Trade-offs

| Cách debug | Khi nên dùng | Rủi ro |
|---|---|---|
| `describe`/events trước | Pod không Ready, Pending, restart | Events ngắn hạn, có thể mất lịch sử |
| Logs trước | CrashLoop, HTTP 500, app error | Dễ bỏ qua Service/Endpoint lỗi |
| Debug Pod/client Pod | DNS/HTTP từ trong cluster | Cần image/tool được phê duyệt |
| Ephemeral container | Image app minimal/distroless | Cần RBAC riêng và audit |
| Port-forward | Tách lỗi app với Service/Ingress | Không chứng minh đường traffic production |
| UI tool | Incident cần quan sát nhiều object | Dễ thao tác live nếu kubeconfig quá rộng |

### Best Practices

- Nên debug theo object graph thay vì nhảy thẳng vào Ingress hoặc app logs.
- Nên lưu evidence trước khi xóa Pod hoặc rollback.
- Nên dùng FQDN khi debug cross-namespace DNS.
- Nên có fallback Ingress test: Host header, node/LB IP, hoặc port-forward controller.
- Nên ghi rõ khi Metrics API hoặc NetworkPolicy enforcement không có trong lab.

## Performance Considerations

- `kubectl get -A` và UI watch rộng trên cluster lớn có thể tạo tải API server đáng kể.
- Debug image lớn kéo chậm khi incident; nên chuẩn hóa image nhỏ nhưng đủ tool.
- Port-forward không đại diện latency thực tế qua Ingress/LB.
- `kubectl top` là snapshot, không thay thế dashboard lịch sử khi debug spike ngắn.
- Ephemeral containers tăng resource trong Pod tạm thời và cần kiểm soát RBAC.

## Liên hệ với kiến thức đã biết

- Với API Gateway, object graph giúp tách lỗi route/Host/TLS khỏi lỗi backend Service.
- Với observability, Day 29-31 cung cấp logs/metrics/traces; Day 32 là thứ tự dùng tín hiệu đó khi incident.
- Với NetworkPolicy, cùng symptom timeout có thể đến từ policy, app hang hoặc node network.

## Incident note template

```text
Symptom:
Scope:
Start time:
Recent changes:
Evidence:
Root cause:
Fix:
Verification:
Prevention:
```

Viết note ngắn giúp incident sau không lặp lại cùng lỗi.

## Production checklist

- [ ] Có debug image chuẩn được phê duyệt.
- [ ] Engineers biết dùng `events`, `describe`, `logs --previous`, `endpointslice`.
- [ ] RBAC cho debug vừa đủ, không mở quá rộng.
- [ ] Runbook có thứ tự kiểm tra Pod -> Service -> DNS -> Ingress -> app.
- [ ] Logs/metrics/traces liên kết được với namespace/app/version.
- [ ] Có quy trình rollback và ghi nhận incident.
- [ ] Không chỉnh tay resource production ngoài GitOps nếu hệ thống dùng GitOps, trừ break-glass có kiểm soát.

## Anti-patterns

- Xóa Pod ngay trước khi đọc `describe`, events và `--previous` logs.
- Debug Ingress trước khi kiểm tra Service endpoints.
- Chỉ nhìn Pod `Running` rồi bỏ qua readiness.
- Dùng shell trong container production để sửa file/config tạm.
- Không ghi lại root cause và prevention.
- Cấp quyền cluster-admin rộng chỉ để debug logs.

## Tóm tắt

Debug Kubernetes hiệu quả là debug theo graph: client -> Ingress -> Service -> Endpoints -> Pod -> container process. Công cụ quan trọng không chỉ là lệnh, mà là thứ tự kiểm tra và khả năng phân biệt lỗi wiring của Kubernetes với lỗi application. Khi có logs, metrics, traces từ các ngày trước, toolkit ngày này giúp bạn nối tín hiệu thành runbook xử lý sự cố.

## Câu hỏi tự kiểm tra

- Vì sao phải kiểm tra endpoints trước khi debug Ingress sâu?
- `kubectl top` chứng minh được gì và không chứng minh được gì?
- Khi Service DNS resolve nhưng HTTP timeout, bạn kiểm tra ba lớp nào tiếp theo?
- Vì sao port-forward tới Pod thành công nhưng Ingress fail chưa đủ để kết luận app khỏe?

## Tài liệu tham khảo

- Kubernetes Documentation: Debug Pods, Services và Ingress.
- Kubernetes Documentation: `kubectl debug`, ephemeral containers và Metrics API.
- Kubernetes Documentation: Services, EndpointSlice và NetworkPolicy.
- K3s Documentation: Traefik Ingress controller và networking defaults.
