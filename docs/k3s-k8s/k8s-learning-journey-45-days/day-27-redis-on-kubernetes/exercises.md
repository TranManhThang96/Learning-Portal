# Bài thực hành - Day 27: Redis on Kubernetes

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `redis:7-alpine`.
- Có StorageClass mặc định.
- Shell mặc định cho lab là Linux/WSL/Bash. Nếu dùng PowerShell, thay các biến như `PV_NAME=$(...)` bằng `$PV_NAME = kubectl ...`.

## Lab Scenario

Bạn sẽ deploy Redis standalone có AOF persistence, ghi dữ liệu, restart Pod để kiểm tra persistence, scale lên 2 Pod để chứng minh đó không phải replication và thấy vì sao Service load-balance vào nhiều standalone Redis là sai.

Lab này không phải Redis HA.

Core Path dự kiến 105 phút. Worksheet Sentinel/Cluster nằm trong Stretch Goals.

## Task 1: Tạo namespace và Secret (5 phút)

```bash
kubectl create namespace day27
kubectl config set-context --current --namespace=day27
```

Tạo file `redis-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: redis-secret
type: Opaque
stringData:
  REDIS_PASSWORD: dev-password
```

Apply:

```bash
kubectl apply -f redis-secret.yaml
```

## Task 2: Deploy Redis standalone với PVC và AOF (30 phút)

Tạo file `redis-lab.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
  - name: redis
    port: 6379
    targetPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis-headless
spec:
  clusterIP: None
  selector:
    app: redis
  ports:
  - name: redis
    port: 6379
    targetPort: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis-headless
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - name: redis
          containerPort: 6379
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: REDIS_PASSWORD
        command:
        - redis-server
        args:
        - --appendonly
        - "yes"
        - --dir
        - /data
        - --requirepass
        - $(REDIS_PASSWORD)
        - --maxmemory
        - 128mb
        - --maxmemory-policy
        - allkeys-lru
        readinessProbe:
          exec:
            command:
            - sh
            - -c
            - |
              redis-cli -a "$REDIS_PASSWORD" --raw PING | grep -q '^PONG$'
              redis-cli -a "$REDIS_PASSWORD" --raw INFO persistence | grep -q '^loading:0'
          initialDelaySeconds: 5
          periodSeconds: 5
        livenessProbe:
          exec:
            command:
            - sh
            - -c
            - redis-cli -a "$REDIS_PASSWORD" --raw PING | grep -q '^PONG$'
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            cpu: 50m
            memory: 128Mi
          limits:
            memory: 256Mi
        volumeMounts:
        - name: data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 512Mi
```

Apply:

```bash
kubectl apply -f redis-lab.yaml
kubectl rollout status statefulset/redis --timeout=180s
kubectl get pod,pvc,svc -o wide
```

### Expected output

- Pod `redis-0` Running và Ready.
- PVC `data-redis-0` Bound.
- Redis bật AOF và yêu cầu password.
- Readiness kiểm tra Redis không còn `loading`, liveness chỉ kiểm tra process trả lời.

## Task 3: Kết nối bằng client Pod và ghi dữ liệu (20 phút)

Tạo client:

```bash
kubectl run redis-client \
  --image=redis:7-alpine \
  --restart=Never \
  --env="REDISCLI_AUTH=dev-password" \
  --command -- sleep 3600

kubectl wait --for=condition=Ready pod/redis-client --timeout=120s
```

Ghi dữ liệu:

```bash
kubectl exec redis-client -- redis-cli -h redis SET user:1 "alice"
kubectl exec redis-client -- redis-cli -h redis SET user:2 "bob"
kubectl exec redis-client -- redis-cli -h redis INCR pageviews
kubectl exec redis-client -- redis-cli -h redis MGET user:1 user:2 pageviews
```

Kiểm tra config:

```bash
kubectl exec redis-client -- redis-cli -h redis CONFIG GET appendonly
kubectl exec redis-client -- redis-cli -h redis CONFIG GET maxmemory
kubectl exec redis-client -- redis-cli -h redis CONFIG GET maxmemory-policy
```

### Expected output

- Key trả về đúng giá trị.
- `appendonly` là `yes`.
- Redis có `maxmemory` và eviction policy rõ ràng.

## Task 4: Kiểm tra persistence qua Pod restart (15 phút)

```bash
kubectl delete pod redis-0
kubectl rollout status statefulset/redis --timeout=180s
kubectl exec redis-client -- redis-cli -h redis MGET user:1 user:2 pageviews
```

Map volume:

```bash
PV_NAME=$(kubectl get pvc data-redis-0 -o jsonpath='{.spec.volumeName}')
kubectl describe pvc data-redis-0
kubectl describe pv "$PV_NAME"
```

### Expected output

- Key vẫn còn sau Pod restart.
- Persistence đến từ Redis AOF trên PVC, không phải do Kubernetes hiểu Redis data.

## Task 5: Chứng minh scale không tạo replication và Service routing sai (25 phút)

Scale StatefulSet:

```bash
kubectl scale statefulset redis --replicas=2
kubectl rollout status statefulset/redis --timeout=180s
kubectl get pod,pvc -o wide
```

Ghi vào `redis-0`:

```bash
kubectl exec redis-client -- redis-cli -h redis-0.redis-headless SET scale-test "written-on-redis-0"
kubectl exec redis-client -- redis-cli -h redis-0.redis-headless GET scale-test
kubectl exec redis-client -- redis-cli -h redis-1.redis-headless SET only-on-1 "written-on-redis-1"
```

Đọc từ `redis-1`:

```bash
kubectl exec redis-client -- redis-cli -h redis-1.redis-headless GET scale-test
```

Kiểm tra Service `redis` đang có bao nhiêu endpoints:

```bash
kubectl get endpoints redis
```

Đọc qua Service nhiều lần. Mỗi lệnh Redis CLI mở connection mới nên kube-proxy có thể chọn backend khác nhau:

```bash
kubectl exec redis-client -- sh -c 'for i in $(seq 1 12); do printf "try-$i "; redis-cli -h redis MGET scale-test only-on-1; done'
```

Scale lại 1:

```bash
kubectl scale statefulset redis --replicas=1
```

### Expected output

- `redis-1` không tự có key của `redis-0`.
- Hai Pod là hai Redis standalone khác nhau nếu không cấu hình replication.
- Service `redis` có 2 endpoints khi scale lên 2, nên client có thể đọc dữ liệu không nhất quán.
- Redis HA cần Sentinel/Cluster/operator, không chỉ replicas.

## Task 6: Inspect memory và persistence signals (10 phút)

```bash
kubectl exec redis-client -- redis-cli -h redis INFO memory
kubectl exec redis-client -- redis-cli -h redis INFO persistence
kubectl exec redis-client -- redis-cli -h redis INFO stats
```

Ghi chú:

```text
used_memory:
maxmemory:
evicted_keys:
aof_enabled:
aof_last_write_status:
loading:
```

### Expected output

- Bạn đọc được signal Redis-level thay vì chỉ nhìn Pod Running.

## Verification cuối Core Path

```bash
kubectl get statefulset,pod,pvc,svc,endpoints -o wide
kubectl exec redis-client -- redis-cli -h redis PING
kubectl exec redis-client -- redis-cli -h redis INFO persistence | grep loading
kubectl exec redis-client -- redis-cli -h redis INFO memory | grep -E 'used_memory_human|maxmemory_human|evicted_keys'
```

Expected:

- `redis-0` Ready và PVC `data-redis-0` Bound.
- `PING` trả `PONG`.
- `loading:0`.
- Bạn đã ghi lại vì sao Service load-balance vào nhiều standalone Redis là anti-pattern.

## Stretch Goal: Sentinel vs Cluster worksheet (25 phút)

Tạo file `day27-redis-mode-notes.md`:

```text
Use case:
Can data be lost?
Need write HA?
Need sharding?
Client supports Sentinel?
Client supports Redis Cluster?
Persistence mode:
Backup/restore requirement:
Memory limit:
Eviction policy:
Chosen mode:
Reason:
Risks:
```

Điền cho ba scenario:

- Cache product catalog có thể rebuild.
- Session store cần giữ session qua Pod restart.
- High-throughput shared Redis cần scale write/read.

## Cleanup

```bash
kubectl delete namespace day27
```

Nếu còn PV dynamic do reclaim policy:

```bash
kubectl get pv
kubectl describe pv <pv-name>
```

## Câu hỏi tự kiểm tra

1. Redis standalone khác Redis Sentinel và Redis Cluster thế nào?
2. Vì sao scale StatefulSet không tự tạo replication?
3. RDB và AOF trade-off ra sao?
4. Vì sao `maxmemory` nên nhỏ hơn container memory limit?
5. Client cần hỗ trợ gì khi dùng Sentinel hoặc Cluster?
