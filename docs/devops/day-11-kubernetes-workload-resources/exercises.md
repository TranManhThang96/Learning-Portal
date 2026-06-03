# Day 11: Bài tập — Kubernetes Workload Resources

---

## Bài 1: Easy — Deploy và Scale Deployment

### Context
Bạn cần deploy một web application đơn giản lên Kubernetes cluster và thực hiện các thao tác cơ bản: scale, update image, rollback.

### Yêu cầu
1. Tạo Deployment `hello-web` với image `nginx:1.24`, 2 replicas.
2. Thêm resource requests/limits hợp lý.
3. Thêm readiness probe và liveness probe.
4. Scale lên 5 replicas.
5. Update image lên `nginx:1.25`.
6. Quan sát rolling update process.
7. Rollback về version trước.

### Expected Outcome
- Deployment có 2 replicas ban đầu, scale lên 5.
- Rolling update chuyển từ nginx:1.24 → nginx:1.25 không downtime.
- Rollback thành công về nginx:1.24.
- `kubectl rollout history` hiển thị ít nhất 2 revisions.

### Hints
- Dùng `kubectl rollout status` để theo dõi update.
- Dùng `kubectl rollout history deployment/hello-web` để xem revision.
- Dùng `kubectl rollout undo deployment/hello-web` để rollback.

### Acceptance Criteria
- [ ] Deployment tạo thành công với 2 replicas
- [ ] Resource requests/limits được set
- [ ] Probes hoạt động đúng
- [ ] Scale lên 5 replicas thành công
- [ ] Rolling update không có downtime
- [ ] Rollback thành công

### Bonus Challenge
- Set `maxSurge: 1` và `maxUnavailable: 0` rồi quan sát behavior khác biệt so với default.
- Dùng `kubectl describe deployment` để xem Events trong quá trình rollout.

<details>
<summary>Solution</summary>

```yaml
# hello-web-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello-web
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: hello-web
    spec:
      containers:
        - name: nginx
          image: nginx:1.24
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
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
```

```bash
# Deploy
kubectl apply -f hello-web-deployment.yaml
kubectl get deploy hello-web

# Scale
kubectl scale deployment hello-web --replicas=5
kubectl get pods -l app=hello-web

# Update image
kubectl set image deployment/hello-web nginx=nginx:1.25
kubectl rollout status deployment/hello-web

# Check history
kubectl rollout history deployment/hello-web

# Rollback
kubectl rollout undo deployment/hello-web
kubectl rollout status deployment/hello-web

# Verify rollback
kubectl describe deployment hello-web | grep Image

# Cleanup
kubectl delete -f hello-web-deployment.yaml
```

</details>

---

## Bài 2: Medium — Job Pipeline và CronJob Monitoring

### Context
Bạn cần xây dựng một hệ thống batch processing gồm:
- Một Job chạy data migration (one-shot).
- Một CronJob chạy health check report mỗi 3 phút.
- Xử lý đúng các edge cases: timeout, retry, concurrency.

### Yêu cầu
1. Tạo Job `db-migration` mô phỏng migration process (sleep + echo output).
   - Giới hạn retry 3 lần.
   - Timeout sau 120 giây.
   - Restart policy phải là `OnFailure`.
2. Tạo CronJob `system-health-check` chạy mỗi 3 phút.
   - Không cho phép chạy đồng thời (`concurrencyPolicy: Forbid`).
   - Giữ lại 3 successful jobs và 2 failed jobs.
   - Có `startingDeadlineSeconds`.
3. Tạo Job `failing-job` cố tình fail (exit code 1) để quan sát retry behavior.
4. Kiểm tra logs và status của tất cả jobs.

### Expected Outcome
- `db-migration` hoàn thành thành công (status: Succeeded).
- `system-health-check` tạo Job mới mỗi 3 phút, không overlap.
- `failing-job` retry đúng số lần rồi fail.

### Hints
- Dùng `exit 1` để mô phỏng failure.
- `kubectl get jobs -w` để watch real-time.
- `kubectl describe job <name>` để xem chi tiết retry.

### Acceptance Criteria
- [ ] Job migration hoàn thành thành công
- [ ] CronJob chạy đúng schedule, không overlap
- [ ] Failing job retry đúng backoffLimit lần
- [ ] History limits hoạt động đúng
- [ ] Có thể xem logs của từng job run

### Bonus Challenge
- Tạo Job sử dụng `completions: 3` và `parallelism: 2` để mô phỏng parallel batch processing.
- Quan sát pod creation pattern khi `parallelism < completions`.

<details>
<summary>Solution</summary>

```yaml
# db-migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
spec:
  backoffLimit: 3
  activeDeadlineSeconds: 120
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: busybox:1.36
          command:
            - /bin/sh
            - -c
            - |
              echo "[$(date)] Starting database migration..."
              echo "Step 1: Backup current schema"
              sleep 3
              echo "Step 2: Apply migrations"
              sleep 3
              echo "Step 3: Verify data integrity"
              sleep 2
              echo "[$(date)] Migration completed successfully!"
          resources:
            requests:
              cpu: 50m
              memory: 32Mi
            limits:
              cpu: 100m
              memory: 64Mi
---
# system-health-check-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: system-health-check
spec:
  schedule: "*/3 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 2
  startingDeadlineSeconds: 60
  jobTemplate:
    spec:
      backoffLimit: 1
      activeDeadlineSeconds: 60
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: checker
              image: busybox:1.36
              command:
                - /bin/sh
                - -c
                - |
                  echo "=== System Health Check ==="
                  echo "Time: $(date)"
                  echo "Hostname: $(hostname)"
                  echo "Memory: $(cat /proc/meminfo | head -1)"
                  echo "Status: HEALTHY"
              resources:
                requests:
                  cpu: 25m
                  memory: 16Mi
                limits:
                  cpu: 50m
                  memory: 32Mi
---
# failing-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: failing-job
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: fail
          image: busybox:1.36
          command:
            - /bin/sh
            - -c
            - |
              echo "[$(date)] Attempt started"
              echo "Simulating failure..."
              exit 1
          resources:
            requests:
              cpu: 25m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
```

```bash
# Apply all
kubectl apply -f db-migration-job.yaml
kubectl apply -f system-health-check-cronjob.yaml
kubectl apply -f failing-job.yaml

# Watch migration job
kubectl get job db-migration -w
kubectl logs job/db-migration

# Watch failing job retries
kubectl get pods -l job-name=failing-job -w
kubectl describe job failing-job

# Wait for CronJob
kubectl get cronjob system-health-check
# Wait ~3 minutes
kubectl get jobs -l app!=hello-web

# Parallel batch (bonus)
cat <<'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: parallel-batch
spec:
  completions: 3
  parallelism: 2
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: worker
          image: busybox:1.36
          command: ["sh", "-c", "echo Worker $(hostname) processing; sleep 5; echo Done"]
          resources:
            requests:
              cpu: 25m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
EOF
kubectl get pods -l job-name=parallel-batch -w

# Cleanup
kubectl delete job db-migration failing-job parallel-batch
kubectl delete cronjob system-health-check
```

</details>

---

## Bài 3: Hard — Production-ready StatefulSet với Persistence Test

### Context
Bạn là DevOps engineer cần deploy một Redis cluster đơn giản (standalone mode) trên Kubernetes sử dụng StatefulSet. Yêu cầu:
- Data phải persist qua pod restart.
- Có headless service cho stable DNS.
- Có đầy đủ probes, resource limits, security context.
- Test kịch bản pod failure và data recovery.

### Yêu cầu
1. Tạo headless Service cho Redis StatefulSet.
2. Tạo StatefulSet `redis` với:
   - 1 replica (standalone mode).
   - PVC template với 200Mi storage.
   - Redis config mount (giữ `appendonly yes` cho durability).
   - Readiness probe kiểm tra Redis `PING`.
   - Liveness probe kiểm tra Redis.
   - Security context: non-root, drop all capabilities.
   - Resource requests/limits hợp lý cho Redis.
3. Ghi data vào Redis (SET key value).
4. Delete pod Redis (mô phỏng crash).
5. Chờ pod tạo lại và verify data vẫn còn (GET key).
6. Scale lên 2 replicas và verify mỗi pod có PVC riêng.
7. Scale down về 1 replica và verify PVC vẫn tồn tại.

### Expected Outcome
- Redis pod có stable name `redis-0`.
- Data persist qua pod restart nhờ PVC.
- Scale up tạo `redis-1` với PVC riêng.
- Scale down xóa pod nhưng giữ PVC.

### Hints
- Redis image: `redis:7-alpine`.
- Redis readiness: `redis-cli ping` (expected output: `PONG`).
- Redis default user ID: 999 (trong redis:7-alpine).
- Dùng ConfigMap để mount `redis.conf` với `appendonly yes`.

### Acceptance Criteria
- [ ] Headless service tạo đúng (clusterIP: None)
- [ ] StatefulSet có volumeClaimTemplate
- [ ] Redis pod chạy với non-root user
- [ ] Probes hoạt động đúng
- [ ] Data persist sau pod restart
- [ ] Scale up/down hoạt động đúng
- [ ] PVC không bị xóa khi scale down

### Bonus Challenge
- Thêm `PodDisruptionBudget` cho Redis.
- Tạo Job kiểm tra data integrity sau mỗi lần pod restart.
- Dùng `kubectl debug` (ephemeral container) để inspect Redis từ bên ngoài.

<details>
<summary>Solution</summary>

```yaml
# redis-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-config
data:
  redis.conf: |
    appendonly yes
    appendfilename "appendonly.aof"
    save 60 1000
    maxmemory 100mb
    maxmemory-policy allkeys-lru
---
# redis-statefulset.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-svc
spec:
  clusterIP: None
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis-svc
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      securityContext:
        fsGroup: 999
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          command: ["redis-server", "/etc/redis/redis.conf"]
          volumeMounts:
            - name: data
              mountPath: /data
            - name: config
              mountPath: /etc/redis
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 250m
              memory: 256Mi
          securityContext:
            runAsUser: 999
            runAsGroup: 999
            capabilities:
              drop: ["ALL"]
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: redis-config
  volumeClaimTemplates:
    - metadata:
        name: data
        labels:
          app: redis
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 200Mi
---
# redis-pdb.yaml (bonus)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: redis-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: redis
```

```bash
# Apply
kubectl apply -f redis-config.yaml
kubectl apply -f redis-statefulset.yaml

# Wait for ready
kubectl wait --for=condition=Ready pod/redis-0 --timeout=60s

# Verify DNS
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- nslookup redis-0.redis-svc

# Write data
kubectl exec redis-0 -- redis-cli SET mykey "persistent-data-12345"
kubectl exec redis-0 -- redis-cli SET counter 42
kubectl exec redis-0 -- redis-cli GET mykey
# Expected: "persistent-data-12345"

# Simulate pod crash
kubectl delete pod redis-0
kubectl wait --for=condition=Ready pod/redis-0 --timeout=60s

# Verify data persists
kubectl exec redis-0 -- redis-cli GET mykey
# Expected: "persistent-data-12345"
kubectl exec redis-0 -- redis-cli GET counter
# Expected: "42"

# Scale up
kubectl scale statefulset redis --replicas=2
kubectl wait --for=condition=Ready pod/redis-1 --timeout=60s

# Verify separate PVCs
kubectl get pvc
# Expected: data-redis-0 and data-redis-1

# Scale down
kubectl scale statefulset redis --replicas=1
kubectl get pvc
# Expected: Both PVCs still exist!

# Cleanup
kubectl delete statefulset redis
kubectl delete service redis-svc
kubectl delete configmap redis-config
# Label này được set trong volumeClaimTemplates; nếu thiếu label, xóa trực tiếp data-redis-0/data-redis-1
kubectl delete pvc -l app=redis
```

</details>

