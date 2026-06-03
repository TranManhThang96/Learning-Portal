# Day 11: Kubernetes Workload Resources

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt được** khi nào dùng `Deployment`, `StatefulSet`, `DaemonSet`, `Job`, `CronJob` trong production.
2. **Giải thích được** mối quan hệ giữa `Pod`, `ReplicaSet` và `Deployment` trong reconciliation loop.
3. **Cấu hình được** update strategy (`RollingUpdate`, `Recreate`) và hiểu impact của từng strategy lên availability.
4. **Thiết kế được** workload phù hợp cho các use case: web server, background worker, batch processing, scheduled task, node-level agent.
5. **Debug được** các lỗi thường gặp: `CrashLoopBackOff`, pod stuck `Terminating`, rollout bị kẹt.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng?

Ở Day 10, bạn đã hiểu Kubernetes architecture — control plane, data plane, reconciliation loop. Nhưng khi deploy một ứng dụng thực tế, câu hỏi đầu tiên là: **dùng workload resource nào?**

Chọn sai workload resource sẽ dẫn đến:
- **Data loss**: dùng `Deployment` cho database thay vì `StatefulSet` → pod restart mất identity, volume bị mix.
- **Downtime**: dùng `Recreate` strategy cho service có traffic → toàn bộ pod bị kill trước khi pod mới lên.
- **Resource waste**: dùng `Deployment` cho task chạy 1 lần → pod chạy xong vẫn restart liên tục.
- **Missing monitoring**: không chạy `DaemonSet` cho log collector → một số node không có logs.

### Liên hệ với developer background

Nếu bạn đã viết microservices, hãy nghĩ:
- `Deployment` = process manager cho stateless HTTP server (giống PM2 cluster mode).
- `StatefulSet` = process manager có đánh số, giữ identity (giống database replica set).
- `DaemonSet` = agent chạy trên mỗi máy (giống syslog daemon, monitoring agent).
- `Job` = one-shot script (giống cron job trên server, nhưng có retry).
- `CronJob` = scheduled task (giống Linux crontab).

---

## 3. Kiến thức nền tảng

### Pod — đơn vị nhỏ nhất

Pod là đơn vị deploy nhỏ nhất trong Kubernetes. Một pod chứa 1 hoặc nhiều container chia sẻ:
- **Network namespace**: cùng IP, cùng port space.
- **Storage volumes**: có thể mount chung volume.
- **Lifecycle**: tất cả container trong pod start/stop cùng nhau.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: simple-app
spec:
  containers:
    - name: app
      image: nginx:1.25
      ports:
        - containerPort: 80
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 200m
          memory: 256Mi
```

> **Quan trọng**: Trong production, bạn **hầu như không bao giờ** tạo Pod trực tiếp. Luôn dùng higher-level resource (Deployment, StatefulSet, ...) vì Pod đơn lẻ không có self-healing.

### Restart Policy

| Policy | Mô tả | Dùng cho |
|--------|--------|----------|
| `Always` (default) | Restart container khi exit | Deployment, StatefulSet, DaemonSet |
| `OnFailure` | Chỉ restart khi exit code ≠ 0 | Job |
| `Never` | Không restart | Debug pod, one-shot task |

### ReplicaSet — đảm bảo số lượng pod

ReplicaSet đảm bảo luôn có đúng N pod đang chạy. Nếu pod chết, ReplicaSet tạo pod mới.

```
Desired state: 3 replicas
Current state: 2 pods running
→ ReplicaSet tạo thêm 1 pod
```

> Bạn **không nên tạo ReplicaSet trực tiếp**. Dùng `Deployment` — nó quản lý ReplicaSet cho bạn và thêm khả năng rollout/rollback.

---

## 4. Deep Dive

### 4.1 Deployment

Deployment là workload resource phổ biến nhất, quản lý stateless application.

```
┌─────────────────────────────────────────────┐
│                 Deployment                   │
│  (manages rollout strategy & history)        │
│                                              │
│  ┌──────────────┐    ┌──────────────┐       │
│  │ ReplicaSet   │    │ ReplicaSet   │       │
│  │ (revision 2) │    │ (revision 1) │       │
│  │   ACTIVE     │    │   SCALED TO 0│       │
│  │              │    │              │       │
│  │ ┌────┐┌────┐│    │              │       │
│  │ │Pod ││Pod ││    │              │       │
│  │ │ v2 ││ v2 ││    │              │       │
│  │ └────┘└────┘│    └──────────────┘       │
│  └──────────────┘                           │
└─────────────────────────────────────────────┘
```

**Update Strategies:**

#### RollingUpdate (default)

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%        # Tối đa thêm bao nhiêu pod so với desired
      maxUnavailable: 25%   # Tối đa bao nhiêu pod có thể unavailable
```

Flow:
```
Time 0: [v1] [v1] [v1] [v1]       ← 4 pods v1
Time 1: [v1] [v1] [v1] [v1] [v2]  ← surge: tạo 1 pod v2
Time 2: [v1] [v1] [v1] [v2] [v2]  ← kill 1 v1, tạo 1 v2
Time 3: [v1] [v1] [v2] [v2] [v2]  ← tiếp tục rolling
Time 4: [v2] [v2] [v2] [v2]       ← hoàn tất
```

#### Recreate

```yaml
spec:
  strategy:
    type: Recreate
```

Flow:
```
Time 0: [v1] [v1] [v1] [v1]  ← 4 pods v1
Time 1: [  ] [  ] [  ] [  ]  ← KILL ALL → DOWNTIME!
Time 2: [v2] [v2] [v2] [v2]  ← tạo mới tất cả v2
```

> **Khi nào dùng Recreate?** Khi app không thể chạy 2 version cùng lúc (ví dụ: database migration chạy đúng 1 instance, hoặc app dùng file lock).

### 4.2 StatefulSet

StatefulSet dùng cho workload cần:
- **Stable network identity**: pod-0, pod-1, pod-2 (không phải random hash).
- **Stable storage**: mỗi pod có PVC riêng, không bị swap.
- **Ordered deployment**: pod-0 phải ready trước khi tạo pod-1.

```
┌─────────────────────────────────────────┐
│              StatefulSet                 │
│                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │  pod-0   │ │  pod-1   │ │  pod-2   ││
│  │          │ │          │ │          ││
│  │  PVC-0   │ │  PVC-1   │ │  PVC-2   ││
│  │  ┌────┐  │ │  ┌────┐  │ │  ┌────┐  ││
│  │  │ PV │  │ │  │ PV │  │ │  │ PV │  ││
│  │  └────┘  │ │  └────┘  │ │  └────┘  ││
│  └──────────┘ └──────────┘ └──────────┘│
│                                          │
│  Headless Service: app-0.svc, app-1.svc │
└─────────────────────────────────────────┘
```

**Đặc điểm quan trọng:**
- Pod name có format `<statefulset-name>-<ordinal>`: `mysql-0`, `mysql-1`.
- DNS record riêng qua headless service: `mysql-0.mysql-svc.namespace.svc.cluster.local`.
- Scale down theo thứ tự ngược: `pod-2` bị xóa trước `pod-1`.
- PVC **không bị xóa** khi pod bị xóa → data được bảo toàn.

### 4.3 DaemonSet

DaemonSet đảm bảo **mỗi node** (hoặc subset node) chạy đúng 1 pod.

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│  Node 1  │  │  Node 2  │  │  Node 3  │
│          │  │          │  │          │
│ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │
│ │ DS   │ │  │ │ DS   │ │  │ │ DS   │ │
│ │ Pod  │ │  │ │ Pod  │ │  │ │ Pod  │ │
│ └──────┘ │  │ └──────┘ │  │ └──────┘ │
└──────────┘  └──────────┘  └──────────┘
```

**Use cases:**
- Log collector (Fluentd, Fluent Bit, Filebeat).
- Monitoring agent (Prometheus Node Exporter, Datadog Agent).
- Storage daemon (Ceph, GlusterFS).
- Network plugin (Calico, Cilium).
- Security agent (Falco).

### 4.4 Job & CronJob

**Job**: chạy task đến khi hoàn thành (exit code 0).

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
spec:
  backoffLimit: 3          # Retry tối đa 3 lần
  activeDeadlineSeconds: 600  # Timeout 10 phút
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: myapp:latest
          command: ["./migrate", "--target", "v5"]
```

**CronJob**: tạo Job theo schedule.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-report
spec:
  schedule: "0 2 * * *"           # 2:00 AM hàng ngày
  concurrencyPolicy: Forbid        # Không chạy overlap
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  startingDeadlineSeconds: 200
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: report
              image: myapp:report
              command: ["./generate-report"]
```

**ConcurrencyPolicy options:**

| Policy | Mô tả |
|--------|--------|
| `Allow` (default) | Cho phép nhiều Job chạy đồng thời |
| `Forbid` | Không tạo Job mới nếu Job cũ chưa xong |
| `Replace` | Kill Job cũ, tạo Job mới |

---

## 5. Trade-offs & Best Practices ⭐

### Decision Matrix: Chọn Workload Resource nào?

| Tiêu chí | Deployment | StatefulSet | DaemonSet | Job | CronJob |
|-----------|------------|-------------|-----------|-----|---------|
| Stateless web/API | ✅ Best | ❌ | ❌ | ❌ | ❌ |
| Database/cache | ❌ | ✅ Best | ❌ | ❌ | ❌ |
| Node agent/monitor | ❌ | ❌ | ✅ Best | ❌ | ❌ |
| Data migration | ❌ | ❌ | ❌ | ✅ Best | ❌ |
| Scheduled backup | ❌ | ❌ | ❌ | ❌ | ✅ Best |
| Stable network ID | ❌ | ✅ | ❌ | ❌ | ❌ |
| Stable storage | ❌ | ✅ | ❌ | ❌ | ❌ |
| Run on every node | ❌ | ❌ | ✅ | ❌ | ❌ |
| Run to completion | ❌ | ❌ | ❌ | ✅ | ✅ |

### Update Strategy Trade-offs

| Strategy | Downtime | Complexity | Use case |
|----------|----------|------------|----------|
| RollingUpdate | Zero downtime | Medium | Hầu hết stateless apps |
| Recreate | Có downtime | Low | App không chạy được 2 version |
| Blue-Green (manual) | Zero downtime | High | Mission-critical releases |

### Best Practices theo scenario

**Startup nhỏ (< 10 developers):**
- Dùng `Deployment` cho mọi stateless service.
- Database dùng managed service (RDS, Cloud SQL) thay vì StatefulSet.
- CronJob cho batch tasks.
- Chưa cần DaemonSet nếu dùng managed Kubernetes.

**Mid-size company (10-50 developers):**
- Deployment + HPA cho web services.
- StatefulSet cho cache layer (Redis cluster) nếu cần.
- DaemonSet cho centralized logging.
- Job cho database migrations trong CI/CD.

**Enterprise / High-traffic:**
- Deployment với PodDisruptionBudget.
- StatefulSet với anti-affinity rules cho database replicas.
- DaemonSet cho monitoring, security agents với resource limits.
- CronJob với concurrencyPolicy: Forbid cho critical batch jobs.

### Anti-patterns cần tránh

1. **Tạo Pod trực tiếp** → không có self-healing, pod chết là mất.
2. **Dùng Deployment cho database** → pod restart mất identity, volume mapping sai.
3. **maxUnavailable: 100%** → tất cả pod bị kill cùng lúc = downtime.
4. **Không set resource requests/limits** → scheduler không biết đặt pod ở đâu.
5. **CronJob không có deadline** → job zombie chạy mãi.

---

## 6. Performance & Scalability ⭐

### Deployment Scaling

```yaml
spec:
  replicas: 3  # Có thể scale bằng kubectl hoặc HPA
```

**Bottleneck thường gặp:**
- **Image pull**: image lớn → pod start chậm → rolling update kéo dài. Giải pháp: dùng image nhỏ (distroless), pre-pull image.
- **Readiness probe**: probe chậm → pod không nhận traffic kịp → request dồn vào pod cũ.
- **Resource contention**: nhiều pod trên cùng node → CPU throttling, OOMKilled.

### StatefulSet Scaling

- Scale **tuần tự**: pod-0 ready → pod-1 → pod-2. Chậm hơn Deployment.
- Scale down **ngược**: pod-2 delete trước. Quan trọng cho database replication.
- **Parallel pod management** (`podManagementPolicy: Parallel`) có thể dùng khi không cần thứ tự.

### Metrics cần theo dõi

| Metric | Mô tả | Alert threshold |
|--------|--------|-----------------|
| `kube_deployment_status_replicas_available` | Số pod available | < desired replicas |
| `kube_deployment_status_replicas_updated` | Số pod đã update | < desired (rollout chậm) |
| `kube_pod_container_status_restarts_total` | Số lần restart | > 5 trong 10 phút |
| `kube_job_status_failed` | Job fail count | > 0 |

---

## 7. Security & Reliability Considerations

### Security

- **Không chạy container as root**: set `securityContext.runAsNonRoot: true`.
- **Read-only filesystem**: `securityContext.readOnlyRootFilesystem: true` cho stateless apps.
- **Drop capabilities**: `securityContext.capabilities.drop: ["ALL"]`.
- **Image pull policy**: dùng `IfNotPresent` hoặc `Always` tùy môi trường. Production nên pin exact tag.

```yaml
spec:
  containers:
    - name: app
      image: myapp:v1.2.3  # Pin exact version, không dùng :latest
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
```

### Reliability

- **Liveness probe**: detect container bị hang → restart.
- **Readiness probe**: detect container chưa sẵn sàng → không route traffic.
- **Startup probe**: cho app start chậm (Java, heavy init).
- **PodDisruptionBudget**: đảm bảo minimum available pods khi node maintenance.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2    # Luôn giữ ít nhất 2 pod
  selector:
    matchLabels:
      app: my-app
```

---

## 8. Hands-on Example

### Chuẩn bị

```bash
# Tạo cluster kind (nếu chưa có từ Day 10)
kind create cluster --name devops-lab

# Verify cluster
kubectl cluster-info
kubectl get nodes
```

### 8.1 Deploy app bằng Deployment

```yaml
# file: deployment-demo.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  labels:
    app: web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
```

```bash
# Apply
kubectl apply -f deployment-demo.yaml

# Verify
kubectl get deployment web-app
kubectl get replicaset
kubectl get pods -l app=web-app

# Expected output:
# NAME      READY   UP-TO-DATE   AVAILABLE   AGE
# web-app   3/3     3            3           30s

# Test rolling update
kubectl set image deployment/web-app nginx=nginx:1.26

# Quan sát rollout
kubectl rollout status deployment/web-app

# Xem revision history
kubectl rollout history deployment/web-app

# Rollback nếu cần
kubectl rollout undo deployment/web-app
```

### 8.2 Deploy app bằng Job

```yaml
# file: job-demo.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-processor
spec:
  backoffLimit: 3
  activeDeadlineSeconds: 120
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: processor
          image: busybox:1.36
          command:
            - /bin/sh
            - -c
            - |
              echo "Starting data processing..."
              echo "Processing batch 1/3..."
              sleep 5
              echo "Processing batch 2/3..."
              sleep 5
              echo "Processing batch 3/3..."
              sleep 5
              echo "Data processing completed!"
          resources:
            requests:
              cpu: 50m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 64Mi
```

```bash
# Apply
kubectl apply -f job-demo.yaml

# Theo dõi progress
kubectl get jobs -w

# Xem logs
kubectl logs job/data-processor

# Expected output:
# Starting data processing...
# Processing batch 1/3...
# Processing batch 2/3...
# Processing batch 3/3...
# Data processing completed!

# Kiểm tra status
kubectl get job data-processor -o jsonpath='{.status.succeeded}'
# Expected: 1
```

### 8.3 Deploy CronJob

```yaml
# file: cronjob-demo.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: health-reporter
spec:
  schedule: "*/2 * * * *"  # Mỗi 2 phút (cho demo)
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 2
  startingDeadlineSeconds: 60
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: reporter
              image: busybox:1.36
              command:
                - /bin/sh
                - -c
                - |
                  echo "[$(date)] Health check report"
                  echo "Status: all systems operational"
              resources:
                requests:
                  cpu: 25m
                  memory: 16Mi
                limits:
                  cpu: 50m
                  memory: 32Mi
```

```bash
# Apply
kubectl apply -f cronjob-demo.yaml

# Chờ 2-3 phút rồi kiểm tra
kubectl get cronjob health-reporter
kubectl get jobs --selector=job-name -l app!=web-app

# Xem logs của job gần nhất
kubectl logs $(kubectl get pods --selector=job-name -l app!=web-app --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null || echo "waiting-for-pod")
```

### 8.4 StatefulSet đơn giản

```yaml
# file: statefulset-demo.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-sts-svc
spec:
  clusterIP: None  # Headless service - bắt buộc cho StatefulSet
  selector:
    app: web-sts
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web-sts
spec:
  serviceName: web-sts-svc
  replicas: 3
  selector:
    matchLabels:
      app: web-sts
  template:
    metadata:
      labels:
        app: web-sts
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
          volumeMounts:
            - name: data
              mountPath: /usr/share/nginx/html
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
  volumeClaimTemplates:
    - metadata:
        name: data
        labels:
          app: web-sts
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 100Mi
```

```bash
# Apply
kubectl apply -f statefulset-demo.yaml

# Quan sát thứ tự tạo pod
kubectl get pods -l app=web-sts -w

# Expected: web-sts-0, web-sts-1, web-sts-2 (tạo tuần tự)

# Kiểm tra PVC
kubectl get pvc

# Test persistence: ghi data vào pod-0
kubectl exec web-sts-0 -- sh -c 'echo "Hello from pod-0" > /usr/share/nginx/html/index.html'

# Delete pod-0 (nó sẽ được tạo lại)
kubectl delete pod web-sts-0

# Chờ pod tạo lại
kubectl wait --for=condition=Ready pod/web-sts-0 --timeout=60s

# Verify data vẫn còn
kubectl exec web-sts-0 -- cat /usr/share/nginx/html/index.html
# Expected: Hello from pod-0
```

### Cleanup

```bash
kubectl delete -f deployment-demo.yaml
kubectl delete -f job-demo.yaml
kubectl delete -f cronjob-demo.yaml
kubectl delete -f statefulset-demo.yaml

# Xóa PVC (StatefulSet không tự xóa PVC; label được set trong volumeClaimTemplates)
kubectl delete pvc -l app=web-sts
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: CrashLoopBackOff

**Triệu chứng**: Pod restart liên tục, status `CrashLoopBackOff`.

```bash
# Debug flow
kubectl describe pod <pod-name>    # Xem Events
kubectl logs <pod-name>            # Xem app logs
kubectl logs <pod-name> --previous # Xem logs lần chạy trước
```

**Nguyên nhân phổ biến:**
- App crash do config sai hoặc thiếu env var.
- Port conflict.
- Permission denied (non-root user nhưng app cần root).
- Liveness probe quá aggressive → kill pod tốt.

### Pitfall 2: Rollout bị kẹt

**Triệu chứng**: `kubectl rollout status` treo, pod mới không `Ready`.

```bash
kubectl rollout status deployment/web-app
kubectl get replicaset  # Xem RS cũ và mới
kubectl describe pod <new-pod>  # Xem lý do pod không ready

# Rollback ngay
kubectl rollout undo deployment/web-app
```

**Nguyên nhân phổ biến:**
- Image không tồn tại (`ImagePullBackOff`).
- Readiness probe fail.
- Không đủ resource trên cluster.

### Pitfall 3: StatefulSet pod stuck Terminating

```bash
# Force delete (cẩn thận trong production!)
kubectl delete pod web-sts-0 --force --grace-period=0
```

**Nguyên nhân**: Pod không xử lý `SIGTERM` đúng cách, hoặc volume unmount chậm.

### Case Study: CronJob tạo quá nhiều Job

**Bối cảnh**: Team chạy CronJob mỗi phút mà không set `concurrencyPolicy` và `successfulJobsHistoryLimit`. Sau 1 tuần, có hàng nghìn completed Job objects trong etcd, khiến API server chậm.

**Fix**:
```yaml
spec:
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
```

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 10: Kubernetes Architecture)
- Đã hiểu reconciliation loop → bài này thấy nó hoạt động: Deployment controller đảm bảo pod count, StatefulSet controller đảm bảo ordered identity.
- Đã hiểu API server, scheduler, kubelet → bài này apply manifest và trace flow.

### Bài sau (Day 12: Kubernetes Networking Core)
- Sau khi deploy workload, cần hiểu pod-to-pod networking, Service types, DNS.
- StatefulSet cần headless service → sẽ deep dive ở Day 12.
- DaemonSet thường expose metrics → liên quan đến service discovery ở Day 12.

---

## 11. Tài liệu tham khảo

### Must-read
- [Kubernetes Workloads — Official Docs](https://kubernetes.io/docs/concepts/workloads/)
- [Deployments — Official Docs](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [StatefulSets — Official Docs](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

### Nice-to-have
- [Jobs — Official Docs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [DaemonSet — Official Docs](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Managing Resources for Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

### Deep-dive
- "Kubernetes in Action" — Chapter 9: Deployments, Chapter 10: StatefulSets
- "Kubernetes Up & Running" — Chapter 12: Jobs, Chapter 15: StatefulSets
- [Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way) — hiểu sâu về cách controller hoạt động

