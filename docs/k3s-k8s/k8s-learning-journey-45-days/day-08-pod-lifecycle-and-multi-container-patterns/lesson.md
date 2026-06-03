# Day 08: Pod lifecycle và multi-container patterns

## Mục tiêu bài học

- Mô tả được lifecycle của `Pod`: scheduling, init, running, ready, restart, termination.
- Phân biệt `phase`, `conditions`, container state và restart policy.
- Dùng đúng `init container`, sidecar, ambassador, adapter và shared volume.
- Thiết kế `startupProbe`, `readinessProbe`, `livenessProbe` tránh gây rollout lỗi.
- Debug được Pod lỗi do probe, init container, container crash hoặc graceful shutdown kém.

## Vấn đề cần giải quyết

Trong production, câu hỏi quan trọng không chỉ là "container có chạy không", mà là:

- App đã sẵn sàng nhận traffic chưa?
- App có bị restart vô hạn do probe cấu hình sai không?
- Dependency migration/config/bootstrap đã hoàn tất chưa?
- Khi shutdown, app có đủ thời gian drain request không?
- Sidecar có làm lifecycle của Pod phức tạp hơn không?

Pod lifecycle là điểm giao giữa Kubernetes và app runtime. Nếu app không hiểu lifecycle này, rollout, autoscaling và maintenance đều dễ tạo downtime.

## Mental Model

```text
Pod = một nhóm container chia sẻ network namespace, volumes và lifecycle tương đối chung.

Init containers chạy tuần tự và phải hoàn tất trước.
App containers chạy song song.
Probes quyết định ready/live/startup.
Kubelet quan sát trạng thái và update Pod status.
Service chỉ route đến Pod Ready.
Termination cần phối hợp SIGTERM + grace period + readiness.
```

Pod không phải VM nhỏ. Nó là một scheduling envelope cho một hoặc nhiều container cần colocate chặt chẽ.

## Lý thuyết cốt lõi

### Pod phase, conditions và container state

`Pod phase` là summary cấp cao:

| Phase | Ý nghĩa |
|---|---|
| `Pending` | Pod đã được API nhận, nhưng chưa chạy đủ container |
| `Running` | Pod đã bind node và ít nhất một container đang chạy/đang restart |
| `Succeeded` | Tất cả container kết thúc thành công |
| `Failed` | Ít nhất một container kết thúc lỗi và không restart |
| `Unknown` | Kubelet không báo được trạng thái |

Đừng chỉ nhìn phase. Cần đọc thêm:

- `PodScheduled`: scheduler đã gán node chưa.
- `Initialized`: init containers đã xong chưa.
- `ContainersReady`: tất cả app containers ready chưa.
- `Ready`: Pod có được đưa vào Service endpoints không.
- `containerStatuses`: state, lastState, restartCount, imageID.

```bash
kubectl get pod <pod> -o yaml
kubectl describe pod <pod>
kubectl get pod <pod> -o jsonpath='{.status.conditions}{"\n"}'
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].restartCount}{"\n"}'
```

`restartPolicy` quyết định kubelet có restart container đã exit hay không:

| `restartPolicy` | Hành vi | Use case chính | Caveat |
|---|---|---|---|
| `Always` | Restart container khi exit, bất kể exit code | `Deployment`, `StatefulSet`, service lâu dài | Default của workload controller như Deployment |
| `OnFailure` | Chỉ restart khi exit code khác 0 | `Job`, task batch cần retry | Không phù hợp service nhận traffic lâu dài |
| `Never` | Không restart container | Debug Pod, one-shot Pod | Pod có thể `Failed` ngay khi command lỗi |

Với Pod thuộc `Deployment`, bạn hầu như không tự đổi `restartPolicy`; controller yêu cầu pattern service dài hạn. Với batch workload, `Job`/`CronJob` sẽ xuất hiện sâu hơn ở Day 12.

### Init containers

`initContainers` chạy tuần tự trước app containers. Mỗi init container phải exit code 0 thì bước kế tiếp mới chạy.

Use cases tốt:

- Chờ dependency nội bộ sẵn sàng trong lab.
- Tạo file/config runtime vào shared `emptyDir`.
- Chạy migration nhỏ trong môi trường học.
- Kiểm tra precondition như DNS/config/secret.

Production caveat: database migration bằng init container có thể nguy hiểm nếu nhiều replica cùng chạy migration. Với app thật, nên dùng Job/migration pipeline có lock/rollback rõ ràng.

### Multi-container patterns

| Pattern | Mô tả | Use case | Caveat |
|---|---|---|---|
| Sidecar | Container phụ chạy cùng app | log shipper, proxy, config reloader | Tăng CPU/memory, termination phức tạp |
| Ambassador | Proxy local đại diện kết nối ra ngoài | DB proxy, service mesh proxy | Debug network thêm một hop |
| Adapter | Chuyển đổi output app sang format chuẩn | metrics/log format adapter | Có thể che lỗi gốc |
| Init container | Chạy trước app rồi thoát | bootstrap/migration/precheck | Không phù hợp task dài hạn |

Kubernetes hiện đại có khái niệm sidecar container native thông qua restartable init container trên cluster hỗ trợ field này. Không giả định mọi cluster đều bật hoặc cùng version; kiểm tra Kubernetes minor version và feature support trước khi dùng trong manifest portable. Pattern sidecar truyền thống vẫn thường được khai báo như một container bình thường trong `containers`.

### Probes

Ba loại probe quan trọng:

| Probe | Câu hỏi | Nếu fail |
|---|---|---|
| `startupProbe` | App đã khởi động xong chưa? | Kubelet chưa chạy liveness/readiness cho đến khi startup pass |
| `readinessProbe` | App đã sẵn sàng nhận traffic chưa? | Pod bị loại khỏi Service endpoints |
| `livenessProbe` | App có bị kẹt và cần restart không? | Kubelet restart container |

Ví dụ:

```yaml
readinessProbe:
  httpGet:
    path: /
    port: 80
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 3
livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 15
  periodSeconds: 10
startupProbe:
  httpGet:
    path: /
    port: 80
  failureThreshold: 30
  periodSeconds: 2
```

Probe không nên kiểm tra dependency ngoài quá sâu trong liveness. Nếu database chậm làm liveness fail, Kubernetes restart app hàng loạt và làm incident nặng hơn.

### Termination lifecycle

Khi xóa Pod hoặc rollout:

```text
1. Pod có deletionTimestamp.
2. Endpoint controller loại Pod khỏi endpoints khi readiness false/terminating.
3. Kubelet chạy preStop hook nếu có.
4. Kubelet gửi SIGTERM đến container.
5. App drain request và thoát.
6. Hết terminationGracePeriodSeconds thì kubelet gửi SIGKILL.
```

Production app nên handle SIGTERM, đóng listener hoặc mark unready, drain in-flight requests và thoát trong grace period.

## Deep Dive: Endpoint readiness và rollout

Service routing phụ thuộc readiness. Một Pod có thể:

- `Running` nhưng `Ready=False`: container process chạy nhưng Service không route vào.
- `Ready=True`: EndpointSlice có Pod IP.
- `Terminating`: endpoint có thể được đánh dấu terminating để controller/dataplane xử lý đúng hơn tùy version/implementation.

Điều này giúp rolling update an toàn: Deployment tạo Pod mới, chờ readiness pass rồi mới giảm Pod cũ theo strategy. Nếu readiness probe sai, rollout sẽ kẹt hoặc route traffic quá sớm.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Pod lifecycle | Giống Kubernetes upstream | Giống upstream | Giống upstream |
| Runtime | `containerd` packaged | Tùy CRI setup | Node image/provider runtime |
| CNI impact | Flannel thường là default | Tùy CNI | Cloud CNI/addon |
| Probes | Do kubelet chạy | Do kubelet chạy | Do kubelet trên managed node chạy |
| Sidecar/service mesh | Tự cài nếu cần | Tự cài | Addon/marketplace/IAM integration tùy cloud |
| Debug logs node | `journalctl -u k3s/k3s-agent`, `k3s crictl` | kubelet/runtime logs | Cloud logging/node access policy |

K3s không làm probes khác đi, nhưng packaged defaults như Traefik/ServiceLB/local-path có thể ảnh hưởng lab networking/storage quanh Pod.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| Single container Pod | App tự xử lý mọi thứ | Ít overhead | Đơn giản | App phình responsibility |
| Sidecar | Cần colocate proxy/agent | Tốn thêm CPU/memory, startup chậm hơn | Trung bình | Sidecar lỗi kéo Pod không ready |
| Init container | Bootstrap tuần tự | Tăng startup time | Dễ quan sát | Kẹt init làm app không chạy |
| Readiness probe sâu | Chặn traffic khi dependency lỗi | Có thể giảm availability | Cần tuning | Endpoint rỗng hàng loạt |
| Liveness probe nông | Restart khi process thật sự kẹt | Ít false positive | Đơn giản | Không bắt được lỗi logic sâu |
| Startup probe | App cold start lâu | Tránh restart sớm | Thêm config | Threshold quá cao che lỗi lâu |

### Best Practices

Nên làm:

- Luôn có readiness probe cho service nhận traffic.
- Dùng startup probe cho app cold start dài trước khi bật liveness.
- Giữ liveness probe đơn giản, kiểm tra process/event loop thay vì dependency ngoài.
- Đặt `terminationGracePeriodSeconds` phù hợp với request timeout và shutdown time.
- Dùng `init container` cho bootstrap idempotent, không dùng cho migration nguy hiểm khi scale nhiều replica.
- Set `resources.requests/limits` cho cả app container và sidecar.

Tránh làm:

- Dùng cùng endpoint `/health` cho readiness và liveness mà logic quá sâu.
- Để sidecar tiêu thụ resource nhưng không khai báo requests.
- Dùng `sleep 30` trong init container thay cho kiểm tra điều kiện thật.
- Bỏ qua `logs -c <container>` trong Pod nhiều container.
- Cho Pod phụ thuộc vào startup order giữa app containers bình thường; Kubernetes không đảm bảo thứ tự đó như init containers.

## Performance Considerations

- Mỗi sidecar tăng memory footprint, CPU usage, image pull time và log volume.
- Init container làm tăng startup latency; rollout nhiều replica có thể chậm đáng kể.
- Probe quá thường xuyên tạo tải cho app và kubelet, nhất là HTTP probe với dependency phức tạp.
- Readiness quá nhạy có thể tạo endpoint flapping, làm latency tăng do connection churn.
- Liveness false positive gây restart storm, cache warmup lại và giảm throughput.
- Graceful shutdown thiếu làm tăng 5xx khi rollout hoặc drain node.

## Debugging Checklist

Pod chưa chạy app:

```bash
kubectl describe pod <pod>
kubectl get pod <pod> -o jsonpath='{.status.initContainerStatuses}{"\n"}'
kubectl logs <pod> -c <init-container>
kubectl get events --sort-by=.lastTimestamp
```

Pod restart:

```bash
kubectl describe pod <pod>
kubectl logs <pod> -c <container> --previous
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState}{"\n"}'
```

Pod chạy nhưng không nhận traffic:

```bash
kubectl get pod <pod> -o wide
kubectl describe pod <pod>
kubectl get endpoints,endpointslice
kubectl describe svc <service>
```

Pod nhiều container:

```bash
kubectl logs <pod> -c <container>
kubectl exec -it <pod> -c <container> -- sh
kubectl describe pod <pod>
```

## Liên hệ với kiến thức đã biết

Readiness giống việc API Gateway chỉ route tới instance đã pass health check. Liveness giống watchdog restart process bị kẹt, nhưng nếu watchdog quá hung hăng thì chính nó gây outage. Init container giống bootstrap job trước khi service process chạy, còn sidecar giống colocated agent/proxy trong cùng host nhưng được đóng gói ở cấp Pod.

## Tóm tắt

Pod lifecycle quyết định workload có start đúng, nhận traffic đúng và shutdown đúng hay không. Init containers xử lý bootstrap tuần tự, sidecar/ambassador/adapter mở rộng chức năng quanh app, probes nối app health với Service routing và restart policy. Debug Pod cần đọc conditions, container statuses, init statuses, events và logs theo container cụ thể.

## Câu hỏi tự kiểm tra

1. `Running` và `Ready` khác nhau thế nào?
2. Khi init container fail, app container có chạy không?
3. Vì sao không nên để liveness probe phụ thuộc database?
4. Sidecar làm tăng những chi phí vận hành nào?
5. Khi Pod nhiều container lỗi, lệnh logs cần thêm flag nào?

## Tài liệu tham khảo

- Kubernetes Pods: https://kubernetes.io/docs/concepts/workloads/pods/
- Kubernetes Pod Lifecycle: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
- Kubernetes Init Containers: https://kubernetes.io/docs/concepts/workloads/pods/init-containers/
- Kubernetes Probes: https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/
- Kubernetes Sidecar Containers: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/
