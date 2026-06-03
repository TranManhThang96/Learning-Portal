# Day 12: Job và CronJob

## Mục tiêu bài học

- Phân biệt `Job`, `CronJob`, `Deployment` và external scheduler.
- Cấu hình được `completions`, `parallelism`, `backoffLimit`, `activeDeadlineSeconds`, `ttlSecondsAfterFinished`, `restartPolicy`.
- Hiểu `CronJob` schedule, `concurrencyPolicy`, `startingDeadlineSeconds`, `successfulJobsHistoryLimit`, `failedJobsHistoryLimit` và `suspend`.
- Thiết kế batch workload idempotent, có retry an toàn và quan sát được.
- Debug được Job fail, retry quá nhiều, CronJob missed schedule, image lỗi hoặc concurrency không như mong muốn.

## Vấn đề cần giải quyết

Không phải workload nào cũng là service chạy mãi:

- Chạy migration database.
- Import/export dữ liệu.
- Gửi báo cáo định kỳ.
- Reconcile dữ liệu từ API ngoài.
- Xử lý batch theo lô.
- Cleanup object cũ.

Nếu dùng `Deployment` cho batch, bạn phải tự viết logic dừng, retry và cleanup. `Job` và `CronJob` đưa các behavior đó vào Kubernetes API.

## Mental Model

```text
Deployment = keep service running.
Job        = run until success N times.
CronJob    = create Jobs from a time schedule.
```

Điểm quan trọng: `Job` không đảm bảo "exactly once". Vì retry, node failure hoặc controller behavior, một task có thể chạy lại. Code batch phải idempotent hoặc có cơ chế deduplication/locking ở tầng app/data.

## Lý thuyết cốt lõi

### Job

`Job` tạo Pod để chạy một workload đến khi đạt số lần thành công mong muốn.

Manifest tối thiểu:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: hello
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: hello
        image: busybox:1.36
        command: ["sh", "-c", "echo hello && sleep 5"]
```

Các field quan trọng:

| Field | Ý nghĩa |
|---|---|
| `completions` | Tổng số Pod success cần đạt |
| `parallelism` | Số Pod chạy đồng thời tối đa |
| `backoffLimit` | Số lần retry trước khi Job fail |
| `activeDeadlineSeconds` | Thời gian tối đa Job được active |
| `ttlSecondsAfterFinished` | Tự cleanup Job sau khi finished |
| `suspend` | Tạm dừng tạo Pod mới |
| `template.spec.restartPolicy` | Với Job thường dùng `Never` hoặc `OnFailure` |

Nếu không set `completions`, Job mặc định cần một successful Pod. Nếu set `parallelism` cao, controller có thể tạo nhiều Pod cùng lúc để đạt completions nhanh hơn.

Các mode nâng cao cần biết khi thiết kế batch lớn:

| Cơ chế | Ý nghĩa | Khi cân nhắc |
|---|---|---|
| `completionMode: Indexed` | Mỗi completion có index ổn định qua annotation/env/hostname | Batch chia partition rõ, ví dụ shard 0..N |
| `backoffLimitPerIndex` | Retry limit riêng cho từng index | Một partition fail không nên làm retry toàn job mù quáng |
| `podFailurePolicy` | Phân loại Pod failure để fail/ignore/count theo rule | Muốn fail nhanh với lỗi không retry được như config sai |

Các field này phụ thuộc version Kubernetes và feature maturity. Trong lab cơ bản, dùng Job non-indexed trước; khi production có partition cố định, hãy đọc API của cluster hiện tại trước khi dùng.

### restartPolicy: Never vs OnFailure

`Never`:

- Container fail thì Pod fail.
- Job controller tạo Pod mới nếu còn retry.
- Dễ quan sát từng attempt qua Pod riêng.

`OnFailure`:

- Kubelet restart container trong cùng Pod khi container fail.
- Ít Pod hơn nhưng log/attempt có thể khó tách hơn.

Trong lab và nhiều batch production, `Never` dễ debug hơn. Với task rất ngắn, `OnFailure` có thể giảm overhead Pod recreation nhưng cần logging rõ.

### CronJob

`CronJob` tạo `Job` theo lịch cron:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: report
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: report
            image: busybox:1.36
            command: ["sh", "-c", "date && echo report"]
```

Field quan trọng:

| Field | Ý nghĩa |
|---|---|
| `schedule` | Cron expression |
| `timeZone` | Time zone dùng để diễn giải schedule nếu cluster hỗ trợ |
| `concurrencyPolicy` | `Allow`, `Forbid`, hoặc `Replace` |
| `startingDeadlineSeconds` | Deadline để start Job nếu missed schedule |
| `successfulJobsHistoryLimit` | Giữ bao nhiêu Job success cũ |
| `failedJobsHistoryLimit` | Giữ bao nhiêu Job fail cũ |
| `suspend` | Tạm dừng tạo Job mới |

### concurrencyPolicy

| Policy | Hành vi | Khi dùng |
|---|---|---|
| `Allow` | Cho phép Job overlap | Task độc lập, idempotent, chịu được chạy song song |
| `Forbid` | Nếu Job trước chưa xong, bỏ qua run mới | Report, sync, ETL không được overlap |
| `Replace` | Hủy Job cũ, tạo Job mới | Chỉ cần kết quả mới nhất, ví dụ refresh cache |

`Forbid` không queue vô hạn. Nếu lịch mới đến khi Job cũ còn chạy, lần đó bị skip.

`timeZone` giúp tránh hiểu nhầm giữa UTC và giờ địa phương, nhưng không nên copy manifest mù quáng giữa cluster cũ/mới. Nếu API server reject field này, bỏ `timeZone` và quy ước schedule theo timezone mặc định của controller. Với production, ghi rõ timezone trong runbook và dashboard, không chỉ trong manifest.

### Idempotency là bắt buộc

Kubernetes có thể retry. Node có thể chết sau khi task đã ghi một phần dữ liệu. Controller có thể tạo Pod mới. Vì vậy batch job nên:

- Có idempotency key hoặc checkpoint.
- Ghi trạng thái transactionally vào database.
- Có lock hoặc lease nếu chỉ một worker được xử lý một partition.
- Có output path deterministic và overwrite/merge an toàn.
- Log correlation id, input range, attempt id.

Nếu task gửi email/chuyển tiền/gọi API ngoài, retry mù quáng là nguy hiểm.

Checklist trước khi rerun một Job production:

- Output/side effect của attempt cũ đã ghi đến đâu?
- Có idempotency key, lock hoặc checkpoint để tránh xử lý trùng không?
- Downstream database/API có đang rate limit hoặc degraded không?
- Log có đủ input range, attempt id và correlation id không?
- Có cần cleanup partial output trước khi tạo Job mới không?

## Deep Dive: Job/CronJob controller làm gì bên trong

```text
Job:
1. User tạo Job.
2. Job controller tạo Pod từ template.
3. Pod chạy đến Succeeded hoặc Failed.
4. Controller đếm succeeded/failed Pods.
5. Nếu chưa đủ completions và chưa vượt backoff/deadline, tạo thêm Pod.
6. Khi đủ completions, Job status Complete.

CronJob:
1. CronJob controller tính lịch từ schedule.
2. Đến thời điểm phù hợp, controller tạo Job từ jobTemplate.
3. Controller áp dụng concurrencyPolicy.
4. Controller cleanup history theo successful/failed history limit.
```

Debug batch phải nhìn object chain:

```text
CronJob -> Job -> Pod -> container logs/events
```

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Khía cạnh | K3s | Kubernetes chuẩn tự dựng | EKS/GKE/AKS |
|---|---|---|---|
| Job/CronJob API | Giống upstream | Giống upstream | Giống upstream |
| Controller | Chạy trong control plane K3s | Chạy trong kube-controller-manager | Managed control plane chạy controller |
| Node capacity | Lab nhỏ dễ Pending khi parallelism cao | Tùy node pool | Có thể dùng autoscaler, quota vẫn giới hạn |
| Time/schedule | Phụ thuộc control plane và clock | Cần đồng bộ NTP | Cloud quản control plane, workload timezone vẫn cần rõ |
| Image/registry auth | Tự cấu hình secret/runtime | Tự cấu hình | Có thể tích hợp IAM/registry cloud |

K3s single-node rất phù hợp để học retry, backoff và concurrency. Nhưng performance batch trên laptop không phản ánh production. Với managed Kubernetes, cloud quản lý control plane nhưng team vẫn phải thiết kế idempotency, quota, resource requests, observability và data safety.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Performance implication | Operational complexity | Failure mode |
|---|---|---|---|---|
| `Job` | Batch one-off hoặc triggered | Tạo Pod theo nhu cầu | Thấp-trung bình | Retry gây duplicate side effect |
| `CronJob` | Batch định kỳ | Burst theo lịch | Cần schedule discipline | Missed/overlap schedule |
| `Deployment` worker | Queue consumer chạy liên tục | Latency thấp hơn cho event stream | Cần app-level scaling | Không tự kết thúc |
| External scheduler | Airflow/Temporal/Argo Workflows cần DAG | Tối ưu workflow phức tạp | Cao hơn | Thêm platform vận hành |
| `parallelism` cao | Task chia nhỏ độc lập | Throughput cao, burst resource | Cần quota/rate limit | Làm nghẽn DB/API ngoài |
| `Forbid` | Không được overlap | Bảo vệ downstream | Có thể skip run | Dữ liệu trễ |
| `Replace` | Chỉ cần run mới nhất | Ít backlog | Có thể hủy work dở | Partial output |
| `Allow` | Task idempotent độc lập | Tối đa concurrency | Cần app safe | Duplicate/overlap side effect |

### Best Practices

Nên làm:

- Thiết kế job idempotent trước khi tăng retry/parallelism.
- Set `resources.requests` và `limits` để batch không bóp nghẹt service online.
- Set `backoffLimit` và `activeDeadlineSeconds` để fail hữu hạn.
- Dùng `ttlSecondsAfterFinished` hoặc history limits để tránh rác object.
- Với CronJob production, set `concurrencyPolicy` rõ ràng, không dựa vào default.
- Log input range, attempt, start/end time và summary.
- Tách namespace/quota cho batch nặng.
- Với task quan trọng, có dashboard/alert cho Job failed/missed.

Tránh làm:

- Chạy migration phá schema bằng CronJob lặp lại.
- Đặt `parallelism` cao khi downstream database/API có rate limit.
- Tin rằng CronJob là exactly-once scheduler.
- Dùng `Allow` cho task không idempotent.
- Giữ history quá nhiều làm API output nhiễu.
- Dùng Job cho workflow DAG phức tạp nếu cần orchestration thật sự.

## Performance Considerations

- Mỗi Job Pod có overhead scheduling, image pull, container startup. Với task vài trăm ms, overhead có thể lớn hơn work thật.
- `parallelism` cao tạo burst CPU/memory/network/disk và áp lực lên registry.
- Batch có thể tranh tài nguyên với online service nếu không có requests/limits/quota.
- CronJob đồng loạt theo mốc phút có thể tạo thundering herd. Nên phân tán lịch nếu có nhiều job.
- Retry nhanh có thể làm downstream fail nặng hơn. Cần backoff ở app hoặc queue.
- Log quá nhiều từ batch song song có thể làm nghẽn logging pipeline.
- `ttlSecondsAfterFinished` dọn object nhưng cũng làm mất logs/status nếu log chưa được ship.

## Debugging Checklist

Job không complete:

```bash
kubectl get job,pod -n <namespace>
kubectl describe job <job> -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Job retry nhiều:

```bash
kubectl get job <job> -o yaml
kubectl get pods -l job-name=<job>
kubectl logs <pod> --previous
```

CronJob không tạo Job:

```bash
kubectl get cronjob -n <namespace>
kubectl describe cronjob <cronjob> -n <namespace>
kubectl get jobs -n <namespace> --sort-by=.metadata.creationTimestamp
```

CronJob overlap hoặc skip:

```bash
kubectl describe cronjob <cronjob>
kubectl get jobs,pods
kubectl get events --sort-by=.lastTimestamp
```

Lab fix là sửa manifest và tạo lại Job. Production fix phải kiểm tra side effect đã xảy ra chưa trước khi rerun.

## Liên hệ với kiến thức đã biết

`Job` giống một worker process chạy đến khi xong. `CronJob` giống cron truyền thống nhưng tạo Kubernetes Job thay vì process local. Khác biệt quan trọng là retry và scheduling nằm trong control plane, còn idempotency, transaction boundary và deduplication vẫn là trách nhiệm của app.

## Tóm tắt

`Job` chạy batch đến khi đạt số completions. `CronJob` tạo Job theo lịch. Chúng phù hợp cho task hữu hạn, nhưng không đảm bảo exactly-once. Production batch cần idempotency, resource control, retry hữu hạn, concurrency policy rõ ràng và observability tốt. Debug luôn đi theo chuỗi `CronJob -> Job -> Pod -> logs/events`.

## Câu hỏi tự kiểm tra

1. Vì sao `Job` không phù hợp để đảm bảo exactly-once side effect?
2. `parallelism` và `completions` khác nhau thế nào?
3. Khi nào chọn `concurrencyPolicy: Forbid`?
4. `ttlSecondsAfterFinished` có trade-off gì?
5. Nếu CronJob không tạo Job mới, bạn kiểm tra object nào trước?

## Tài liệu tham khảo

- Kubernetes Jobs: https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Kubernetes CronJob: https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- Kubernetes Job API: https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/job-v1/
- Kubernetes CronJob API: https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/cron-job-v1/
- Kubernetes Debug Pods: https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
