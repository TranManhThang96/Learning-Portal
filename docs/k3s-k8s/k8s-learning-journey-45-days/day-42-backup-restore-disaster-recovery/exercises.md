# Bài thực hành - Day 42: Backup, Restore và Disaster Recovery

## Prerequisites

- Kubernetes/K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- `helm` nếu cài Velero bằng chart.
- `velero` CLI và object storage/MinIO chỉ cần nếu làm phần Velero optional.

## Lab Scenario

Bạn sẽ tạo một namespace có app stateless/PVC, mô phỏng mất namespace, rồi restore theo ba lớp:

1. GitOps/manifest restore cho phần stateless.
2. `pg_dump`/restore cho PostgreSQL lab.
3. Velero hoặc runbook giả lập cho phần Kubernetes objects/PVC.

Core path không yêu cầu Velero hay object storage. Nếu không có MinIO/S3, vẫn hoàn thành được restore drill bằng manifest và app-level backup.

## Task 1: Tạo workload cần backup (20 phút)

```bash
kubectl create namespace day42
```

Tạo `app-with-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
  namespace: day42
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: notes
  namespace: day42
spec:
  replicas: 1
  selector:
    matchLabels:
      app: notes
  template:
    metadata:
      labels:
        app: notes
    spec:
      containers:
      - name: app
        image: busybox:1.36
        command:
        - sh
        - -c
        - while true; do date >> /data/notes.log; sleep 10; done
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: data
```

Apply và verify:

```bash
kubectl apply -f app-with-pvc.yaml
kubectl get pod,pvc -n day42
kubectl exec deploy/notes -n day42 -- tail /data/notes.log
```

### Câu hỏi

- File YAML này backup được phần nào?
- Dữ liệu `/data/notes.log` có nằm trong Git không?

## Task 2: Restore stateless bằng manifest (20 phút)

Giả lập mất Deployment:

```bash
kubectl delete deploy notes -n day42
kubectl get pod,pvc -n day42
```

Restore bằng manifest:

```bash
kubectl apply -f app-with-pvc.yaml
kubectl rollout status deploy/notes -n day42
kubectl exec deploy/notes -n day42 -- tail /data/notes.log
```

### Expected output

- Deployment quay lại.
- PVC vẫn còn vì namespace chưa bị xóa.
- Dữ liệu cũ vẫn còn nếu storage backend giữ volume.

### Câu hỏi

- Vì sao xóa Deployment khác xóa namespace?
- Reclaim policy của PV ảnh hưởng gì?

## Task 3: Mô phỏng mất namespace (20 phút)

Trước khi xóa, ghi lại evidence:

```bash
kubectl get all,pvc -n day42
kubectl exec deploy/notes -n day42 -- tail /data/notes.log
```

Xóa namespace:

```bash
kubectl delete namespace day42
kubectl get namespace day42
```

Tạo lại:

```bash
kubectl create namespace day42
kubectl apply -f app-with-pvc.yaml
kubectl get pod,pvc -n day42
kubectl exec deploy/notes -n day42 -- tail /data/notes.log
```

### Expected output

- App chạy lại.
- Dữ liệu cũ có thể mất, đặc biệt với dynamic provisioning local-path.

### Câu hỏi

- Đây có phải restore thật không?
- Nếu dữ liệu mất, lớp backup nào còn thiếu?

## Task 4: App-level PostgreSQL backup/restore bằng `pg_dump` (30 phút)

Tạo PostgreSQL lab nhỏ:

```bash
kubectl create secret generic pg-secret -n day42 --from-literal=POSTGRES_PASSWORD=lab-password
```

Tạo `postgres-lab.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: day42
spec:
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
  namespace: day42
spec:
  serviceName: postgres
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
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: pg-secret
              key: POSTGRES_PASSWORD
        ports:
        - containerPort: 5432
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          periodSeconds: 5
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 512Mi
        volumeMounts:
        - name: pgdata
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: pgdata
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 1Gi
```

Apply và tạo dữ liệu:

```bash
kubectl apply -f postgres-lab.yaml
kubectl rollout status statefulset/postgres -n day42
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "CREATE TABLE IF NOT EXISTS orders(id int primary key, status text); INSERT INTO orders VALUES (1, '\''created'\'') ON CONFLICT DO NOTHING;"'
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "SELECT * FROM orders;"'
```

Dump ra file local:

```bash
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password pg_dump -U postgres postgres' > day42-pg-dump.sql
ls -lh day42-pg-dump.sql
```

Inject lỗi bằng cách xóa table rồi restore:

```bash
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "DROP TABLE orders;"'
kubectl cp day42-pg-dump.sql day42/postgres-0:/tmp/day42-pg-dump.sql
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password psql -U postgres -f /tmp/day42-pg-dump.sql'
kubectl exec pod/postgres-0 -n day42 -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "SELECT * FROM orders;"'
```

### Expected output

- `SELECT * FROM orders;` trả lại dòng `1 | created` sau restore.
- Bạn có thời gian thực tế cho một backup/restore nhỏ để ghi vào RTO lab.

### Câu hỏi

- Vì sao `pg_dump` là application-level backup còn PVC snapshot là storage-level backup?
- Với database lớn, `pg_dump` có thể không đạt RPO/RTO nào?

## Task 5: Optional Velero backup/restore namespace (20 phút)

Velero cần object storage. Nếu chưa có S3/GCS/Azure Blob, có thể dùng MinIO local hoặc bỏ qua phần apply và viết runbook. Không coi lab hỏng nếu môi trường chưa có object storage.

MinIO/Velero path tham khảo:

```bash
helm repo add minio https://charts.min.io/
helm upgrade --install minio minio/minio -n minio --create-namespace \
  --set mode=standalone \
  --set rootUser=minio \
  --set rootPassword=minio123 \
  --set replicas=1 \
  --set persistence.enabled=false
```

Sau đó cài Velero theo provider `aws` trỏ vào MinIO endpoint của bạn. Nếu đã có Velero:

Nếu đã có Velero:

```bash
velero backup create day42-backup --include-namespaces day42
velero backup get
velero backup describe day42-backup --details
```

Xóa namespace:

```bash
kubectl delete namespace day42
```

Restore:

```bash
velero restore create day42-restore --from-backup day42-backup
velero restore get
velero restore describe day42-restore --details
kubectl get all,pvc -n day42
```

Nếu chưa có Velero, viết file `restore-runbook.md` với các mục:

```markdown
# Restore Runbook - day42

## Scope
- Namespace:
- Workloads:
- PVC:
- External dependencies:

## RPO/RTO
- RPO:
- RTO:

## Restore steps
1.
2.
3.

## Verification
-

## Rollback
-
```

### Câu hỏi

- Velero restore có khôi phục được dữ liệu PVC trong môi trường của bạn không?
- Nếu không, thiếu plugin/snapshot/storage capability nào?

## Task 6: Inject lỗi restore do thiếu CRD (10 phút)

Không cần cài CRD thật. Tạo file `fake-cr.yaml`:

```yaml
apiVersion: example.com/v1
kind: DemoApp
metadata:
  name: demo
  namespace: day42
spec:
  replicas: 1
```

Apply:

```bash
kubectl apply -f fake-cr.yaml
```

### Expected output

- API server báo không nhận `kind` này vì thiếu CRD.

### Câu hỏi

- Khi restore backup có custom resource, thứ tự restore cần thay đổi thế nào?
- Operator cần được restore trước hay sau CR?

## Task 7: K3s datastore snapshot review (10 phút)

Trước tiên xác định mode datastore. Nếu single-server K3s mặc định dùng SQLite, lệnh `k3s etcd-snapshot` không áp dụng. Nếu K3s HA embedded `etcd`, dùng:

```bash
sudo k3s etcd-snapshot ls
sudo k3s etcd-snapshot save --name day42-manual
sudo k3s etcd-snapshot ls
```

Nếu dùng K3s SQLite/k3d/kind/managed cluster, chỉ ghi lại:

```text
Current environment:
Datastore mode: SQLite / embedded etcd / external datastore / provider-managed
Control plane backup method:
Who manages etcd:
How to restore cluster state:
```

### Câu hỏi

- Vì sao managed Kubernetes thường không cho bạn restore `etcd` trực tiếp?
- Snapshot control plane có backup PVC data không?

## Cleanup

```bash
kubectl delete namespace day42
```

Giữ Velero nếu muốn dùng về sau.

## Common Pitfalls

- Chỉ backup manifest nhưng tưởng đã backup data.
- Không test restore sang cluster/namespace khác.
- Restore CR trước khi CRD/operator tồn tại.
- StorageClass khác nhau giữa source và target cluster.
- Backup bucket nằm cùng cluster hoặc cùng disk.

## Stretch Goals

- Cài MinIO trong lab và cấu hình Velero backup vào MinIO.
- Restore namespace sang tên khác bằng `--namespace-mappings`.
- Tạo PostgreSQL lab nhỏ và so sánh `pg_dump` với PVC snapshot.
- Viết bảng RPO/RTO cho capstone Day 44-45.
