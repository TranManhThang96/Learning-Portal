# Bài thực hành - Day 12: Job và CronJob

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Đã hiểu Pod logs/events và `kubectl describe`.

## Lab Scenario

Bạn tạo một batch Job song song, quan sát completions và parallelism. Sau đó bạn tạo Job fail để hiểu retry/backoff. Cuối cùng bạn tạo CronJob chạy mỗi phút, thử `concurrencyPolicy`, suspend/resume và manual trigger.

Core path khoảng 100-110 phút: Task 1-5 và cleanup. `Replace`, `timeZone`, Indexed Job và quota batch nằm trong `Stretch Goals` để giữ lab trong khung 2 giờ.

## Task 1: Tạo namespace và Job chạy một lần (15 phút)

### Mục tiêu

Chạy một Job đơn giản và đọc status/logs.

### Các bước thực hiện

```bash
kubectl create namespace day12
kubectl config set-context --current --namespace=day12
```

Tạo file `hello-job.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: hello
spec:
  backoffLimit: 2
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: hello
        image: busybox:1.36
        command: ["sh", "-c", "echo hello from $HOSTNAME; date -Iseconds; sleep 5"]
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
```

Apply và quan sát:

```bash
kubectl apply -f hello-job.yaml
kubectl get job,pod
kubectl wait --for=condition=complete job/hello --timeout=60s
kubectl logs -l job-name=hello
kubectl describe job hello
```

### Expected output

- Job `hello` có condition `Complete`.
- Pod chuyển sang `Completed`.
- Logs in ra hostname và thời gian.

## Task 2: Parallel Job với completions và parallelism (20 phút)

### Mục tiêu

Thấy Job chạy nhiều Pod nhưng giới hạn concurrency.

### Các bước thực hiện

Tạo file `batch-workers.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-workers
spec:
  completions: 6
  parallelism: 2
  backoffLimit: 2
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: worker
        image: busybox:1.36
        command: ["sh", "-c", "echo start $HOSTNAME at $(date -Iseconds); sleep 10; echo done $HOSTNAME at $(date -Iseconds)"]
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f batch-workers.yaml
kubectl get job,pod -w
```

Sau khi Job complete, mở terminal khác hoặc dừng watch bằng `Ctrl+C` rồi chạy:

```bash
kubectl get pods -l job-name=batch-workers
kubectl logs -l job-name=batch-workers --tail=50
kubectl describe job batch-workers
```

### Expected output

- Tổng cộng 6 completions.
- Tại một thời điểm chỉ khoảng 2 Pod đang chạy.

### Troubleshooting

Nếu Pod `Pending`, kiểm tra resource:

```bash
kubectl describe pod <pod>
kubectl top nodes
```

## Task 3: Inject lỗi và quan sát backoffLimit (20 phút)

### Mục tiêu

Hiểu retry của Job khi container fail.

### Lỗi cần tạo

Tạo file `failing-job.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: failing
spec:
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: fail
        image: busybox:1.36
        command: ["sh", "-c", "echo attempt on $HOSTNAME; date -Iseconds; exit 1"]
```

Apply và điều tra:

```bash
kubectl apply -f failing-job.yaml
kubectl get job,pod -w
```

Sau khi thấy Job fail:

```bash
kubectl describe job failing
kubectl get pods -l job-name=failing
kubectl logs -l job-name=failing --tail=50
kubectl get events --sort-by=.lastTimestamp
```

### Symptom

- Nhiều Pod failed được tạo.
- Job chuyển `Failed` sau khi vượt `backoffLimit`.

### Cách fix trong lab

Job template gần như không nên patch để rerun. Tạo Job mới với manifest đúng:

```bash
kubectl delete job failing
```

Sau đó sửa command `exit 0` hoặc tạo Job tên khác.

## Task 4: Tạo CronJob mỗi phút với concurrencyPolicy Forbid (25 phút)

### Mục tiêu

Quan sát CronJob tạo Job theo lịch và không overlap khi Job cũ còn chạy.

### Các bước thực hiện

Tạo file `minute-report.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: minute-report
spec:
  schedule: "*/1 * * * *"
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 30
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: report
            image: busybox:1.36
            command: ["sh", "-c", "echo start $(date -Iseconds) on $HOSTNAME; sleep 75; echo done $(date -Iseconds)"]
            resources:
              requests:
                cpu: 20m
                memory: 32Mi
              limits:
                cpu: 100m
                memory: 64Mi
```

Apply và quan sát trong 2-3 phút:

```bash
kubectl apply -f minute-report.yaml
kubectl get cronjob,jobs,pods -w
```

Dừng watch rồi inspect:

```bash
kubectl describe cronjob minute-report
kubectl get jobs --sort-by=.metadata.creationTimestamp
kubectl logs -l job-name=<job-name>
```

### Expected output

- CronJob tạo Job mỗi phút nếu policy cho phép.
- Vì Job ngủ 75 giây và `Forbid`, một số schedule có thể bị skip khi Job cũ còn chạy.

### Troubleshooting

Nếu chưa thấy Job, kiểm tra:

```bash
kubectl describe cronjob minute-report
kubectl get events --sort-by=.lastTimestamp
```

## Task 5: Manual trigger, suspend và resume CronJob (15 phút)

### Mục tiêu

Biết chạy thủ công một Job từ CronJob template và tạm dừng lịch.

### Các bước thực hiện

Manual trigger:

```bash
kubectl create job manual-report --from=cronjob/minute-report
kubectl get job,pod
kubectl logs -l job-name=manual-report
```

Suspend:

```bash
kubectl patch cronjob minute-report -p '{"spec":{"suspend":true}}'
kubectl get cronjob minute-report
kubectl describe cronjob minute-report
```

Đợi qua ít nhất một mốc phút, xác nhận không có Job mới. Sau đó resume:

```bash
kubectl patch cronjob minute-report -p '{"spec":{"suspend":false}}'
kubectl get cronjob,jobs
```

### Expected output

- `manual-report` chạy độc lập với schedule.
- Khi `suspend: true`, CronJob không tạo Job mới.

## Stretch Goal: Thử concurrencyPolicy Replace (20 phút)

### Mục tiêu

Hiểu trade-off khi chỉ giữ run mới nhất.

### Các bước thực hiện

Patch policy:

```bash
kubectl patch cronjob minute-report -p '{"spec":{"concurrencyPolicy":"Replace"}}'
kubectl describe cronjob minute-report
kubectl get jobs,pods -w
```

Quan sát qua 2 mốc phút.

### Expected output

- Khi schedule mới tới, Job cũ có thể bị thay thế nếu còn chạy.
- Đây là behavior nguy hiểm nếu task ghi dữ liệu dở dang.

Đổi lại về `Forbid`:

```bash
kubectl patch cronjob minute-report -p '{"spec":{"concurrencyPolicy":"Forbid"}}'
```

## Cleanup

```bash
kubectl delete namespace day12
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Nghĩ `Job` là exactly-once.
- `parallelism` cao làm nghẽn database/API ngoài.
- CronJob schedule theo phút nhưng task chạy lâu hơn một phút và bị overlap.
- Không set `backoffLimit`, Job retry lâu hơn mong muốn.
- Cleanup TTL quá nhanh làm mất evidence debug.
- Rerun Job fail mà không kiểm tra side effect đã ghi một phần.

## Stretch Goals

- Thêm `activeDeadlineSeconds: 30` vào Job ngủ 75 giây để thấy deadline fail.
- Đặt `timeZone: "Asia/Bangkok"` cho CronJob nếu cluster hỗ trợ. Kiểm tra trước bằng `kubectl explain cronjob.spec.timeZone`; nếu API server reject field này, bỏ field và ghi rõ timezone trong runbook.
- Tạo CronJob với `concurrencyPolicy: Allow`, sleep 75 giây và so sánh số Job overlap.
- Thêm namespace `ResourceQuota` để giới hạn tổng Pod batch.
- Tạo `Indexed Job` nhỏ với `completionMode: Indexed` và in `$JOB_COMPLETION_INDEX`.
- Đọc `kubectl explain job.spec.podFailurePolicy` và thiết kế rule fail nhanh cho lỗi exit code không retry được.
