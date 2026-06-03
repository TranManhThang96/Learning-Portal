# Bài thực hành - Day 26: PostgreSQL on Kubernetes

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `postgres:16-alpine`.
- Có StorageClass mặc định hoặc biết tên StorageClass sẽ dùng.
- Shell mặc định cho lab là Linux/WSL/Bash. Nếu dùng PowerShell, thay các biến như `PV_NAME=$(...)` bằng `$PV_NAME = kubectl ...`.

## Lab Scenario

Bạn sẽ deploy PostgreSQL single-primary cho lab, ghi dữ liệu, restart Pod để kiểm tra persistence và tạo backup logical bằng `pg_dump`.

Lab này không phải production HA.

Core Path dự kiến 105 phút. Phần scale anti-pattern, operator CR và PgBouncer nằm trong Stretch Goals để giữ lab trong 2 giờ.

## Task 1: Tạo namespace và kiểm tra storage (10 phút)

```bash
kubectl create namespace day26
kubectl config set-context --current --namespace=day26
kubectl get storageclass
```

Ghi lại:

```text
Default StorageClass:
Provisioner:
VolumeBindingMode:
allowVolumeExpansion:
```

## Task 2: Deploy PostgreSQL bằng StatefulSet (30 phút)

Tạo file `postgres-lab.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
type: Opaque
stringData:
  POSTGRES_DB: appdb
  POSTGRES_USER: app
  POSTGRES_PASSWORD: dev-password
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
  - name: postgres
    port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
  - name: postgres
    port: 5432
    targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - name: postgres
          containerPort: 5432
        envFrom:
        - secretRef:
            name: postgres-secret
        env:
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        readinessProbe:
          exec:
            command:
            - sh
            - -c
            - pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          exec:
            command:
            - sh
            - -c
            - pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 512Mi
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 1Gi
```

Apply:

```bash
kubectl apply -f postgres-lab.yaml
kubectl rollout status statefulset/postgres --timeout=180s
kubectl get pod,pvc,svc -o wide
kubectl describe pod postgres-0
```

### Expected output

- Pod `postgres-0` Running và Ready.
- PVC `data-postgres-0` Bound.
- Service `postgres` expose port `5432`.

## Task 3: Kết nối và ghi dữ liệu (20 phút)

Tạo client Pod:

```bash
kubectl run pg-client \
  --image=postgres:16-alpine \
  --restart=Never \
  --env="PGPASSWORD=dev-password" \
  --command -- sleep 3600

kubectl wait --for=condition=Ready pod/pg-client --timeout=120s
```

Tạo bảng và insert dữ liệu:

```bash
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "CREATE TABLE IF NOT EXISTS orders (id serial PRIMARY KEY, item text, created_at timestamptz DEFAULT now());"
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "INSERT INTO orders (item) VALUES ('coffee'), ('tea'), ('book');"
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "SELECT * FROM orders ORDER BY id;"
```

### Expected output

- Query trả về 3 rows.
- Client dùng Service DNS `postgres` thay vì Pod IP.

## Task 4: Kiểm tra persistence qua Pod restart (20 phút)

Xóa Pod PostgreSQL:

```bash
kubectl delete pod postgres-0
kubectl rollout status statefulset/postgres --timeout=180s
kubectl get pod,pvc -o wide
```

Query lại:

```bash
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "SELECT count(*) AS order_count FROM orders;"
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "SELECT * FROM orders ORDER BY id;"
```

Map PVC/PV:

```bash
PV_NAME=$(kubectl get pvc data-postgres-0 -o jsonpath='{.spec.volumeName}')
kubectl describe pvc data-postgres-0
kubectl describe pv "$PV_NAME"
```

### Expected output

- Data vẫn còn sau Pod recreation.
- PVC vẫn là `data-postgres-0`.
- Bạn phân biệt được restart recovery với HA/failover.

## Task 5: Tạo logical backup bằng pg_dump (25 phút)

Tạo backup ra máy local:

```bash
kubectl exec pg-client -- sh -c 'PGPASSWORD=dev-password pg_dump -h postgres -U app -d appdb' > day26-appdb.sql
```

Kiểm tra file:

```bash
ls -lh day26-appdb.sql
head -n 20 day26-appdb.sql
```

Tạo database mới và restore thử:

```bash
kubectl exec pg-client -- createdb -h postgres -U app restoredb
kubectl exec -i pg-client -- sh -c 'PGPASSWORD=dev-password psql -h postgres -U app -d restoredb' < day26-appdb.sql
kubectl exec pg-client -- psql -h postgres -U app -d restoredb -c "SELECT count(*) FROM orders;"
```

### Expected output

- Backup file có nội dung SQL.
- Restore vào `restoredb` thành công.
- Bạn chứng minh được backup có thể restore, không chỉ tạo file.

## Verification cuối Core Path

Chạy lại các command sau trước khi cleanup:

```bash
kubectl get statefulset,pod,pvc,svc -o wide
kubectl exec pg-client -- pg_isready -h postgres -U app -d appdb
kubectl exec pg-client -- psql -h postgres -U app -d appdb -c "SELECT count(*) AS order_count FROM orders;"
test -s day26-appdb.sql
```

Expected:

- `postgres-0` Ready.
- PVC `data-postgres-0` vẫn `Bound`.
- `order_count` là `3`.
- File backup local không rỗng.

## Stretch Goal 1: Chứng minh scale StatefulSet không tạo replication (20 phút)

Không chạy bước này trong production. Đây là lab để thấy anti-pattern.

```bash
kubectl scale statefulset postgres --replicas=2
kubectl rollout status statefulset/postgres --timeout=180s
kubectl get pod,pvc -o wide
```

Quan sát:

```bash
kubectl exec pg-client -- psql -h postgres-0.postgres-headless -U app -d appdb -c "SELECT count(*) FROM orders;"
kubectl exec pg-client -- psql -h postgres-1.postgres-headless -U app -d appdb -c "SELECT count(*) FROM orders;" || true
```

Scale lại:

```bash
kubectl scale statefulset postgres --replicas=1
```

### Expected output

- `postgres-1` có PVC riêng và không tự động là replica của `postgres-0`.
- Nếu query vào `postgres-1`, data có thể không giống `postgres-0`.
- HA PostgreSQL cần replication/failover layer, thường qua operator hoặc managed service.

## Stretch Goal 2: Đọc operator CR và PgBouncer design (25 phút)

Không cần cài operator trong bài này. Đọc ví dụ `CloudNativePG Cluster` và PgBouncer trong `document.md`, sau đó tạo file ghi chú `day26-postgres-operator-notes.md`:

```text
Candidate:
Install method:
Custom resources:
Backup support:
Restore/PITR support:
Replication/failover model:
Connection routing model:
Connection pooling/PgBouncer model:
Major upgrade story:
Monitoring integration:
Storage assumptions:
Known caveats:
Would I use it for production here? Why?
```

Điền ít nhất hai lựa chọn:

- CloudNativePG.
- Zalando Postgres Operator.
- Managed PostgreSQL của cloud/provider nếu môi trường có.

Nếu muốn tự thiết kế PgBouncer, ghi rõ:

```text
App max pods:
Max client connections:
PostgreSQL max_connections:
PgBouncer pool_mode:
Default pool size:
Prepared statement/session-state caveats:
Failover routing story:
```

## Cleanup

```bash
kubectl delete namespace day26
```

Nếu PV còn lại do reclaim policy:

```bash
kubectl get pv
kubectl describe pv <pv-name>
```

Không xóa PV thủ công nếu chưa chắc nó chỉ thuộc lab này.

## Câu hỏi tự kiểm tra

1. Vì sao StatefulSet replicas 2 không tự tạo PostgreSQL primary/replica?
2. PVC `Bound` chứng minh được điều gì và không chứng minh được điều gì?
3. `pg_dump` khác gì với physical backup + WAL archive?
4. Khi nào nên chọn managed PostgreSQL?
5. Bạn cần test gì trước khi gọi một PostgreSQL deployment là production-ready?
