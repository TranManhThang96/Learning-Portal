# Day 15: Bài tập — Storage: PV, PVC, StorageClass, CSI

---

## Bài 1: Easy — PVC cơ bản và Data Persistence

### Context
Bạn cần deploy một ứng dụng ghi log vào persistent storage và verify rằng data không mất khi pod restart.

### Yêu cầu
1. Tạo PVC `app-logs` với 500Mi storage, access mode `ReadWriteOnce`.
2. Tạo Deployment `log-writer` (1 replica, busybox) ghi log mỗi 10 giây vào `/data/app.log`.
3. Verify log file tồn tại và có nội dung.
4. Delete pod (simulate crash).
5. Chờ pod mới tạo lại.
6. Verify log file vẫn còn data từ trước khi crash.
7. So sánh với `emptyDir`: tạo pod tương tự nhưng dùng `emptyDir`, delete pod, verify data mất.

### Expected Outcome
- PVC bound thành công.
- Log data persist qua pod restart (PVC).
- Log data mất khi pod restart (emptyDir).

### Hints
- Dùng `while true; do echo "$(date) log entry" >> /data/app.log; sleep 10; done` làm command.
- `kubectl exec <pod> -- wc -l /data/app.log` để đếm số dòng log.
- `kubectl exec <pod> -- tail -5 /data/app.log` để xem log gần nhất.

### Acceptance Criteria
- [ ] PVC tạo và bound thành công
- [ ] Pod mount PVC đúng
- [ ] Log data ghi được vào PVC
- [ ] Data persist sau pod delete/recreate
- [ ] EmptyDir comparison: data mất sau pod restart

### Bonus Challenge
- Tạo 2 containers trong cùng pod chia sẻ emptyDir volume (sidecar pattern: 1 ghi log, 1 đọc log).
- Thử resize PVC (nếu StorageClass hỗ trợ `allowVolumeExpansion`).

<details>
<summary>Solution</summary>

```yaml
# persistent-logs.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-logs
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-writer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: log-writer
  template:
    metadata:
      labels:
        app: log-writer
    spec:
      containers:
        - name: writer
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              echo "=== Log writer started at $(date) ==="
              while true; do
                echo "[$(date)] Log entry from $(hostname)" >> /data/app.log
                sleep 10
              done
          volumeMounts:
            - name: logs
              mountPath: /data
          resources:
            requests:
              cpu: 25m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
      volumes:
        - name: logs
          persistentVolumeClaim:
            claimName: app-logs
---
# ephemeral-logs.yaml (for comparison)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ephemeral-writer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ephemeral-writer
  template:
    metadata:
      labels:
        app: ephemeral-writer
    spec:
      containers:
        - name: writer
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              while true; do
                echo "[$(date)] Ephemeral log" >> /data/app.log
                sleep 10
              done
          volumeMounts:
            - name: logs
              mountPath: /data
          resources:
            requests:
              cpu: 25m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
      volumes:
        - name: logs
          emptyDir: {}
```

```bash
# Deploy both
kubectl apply -f persistent-logs.yaml
kubectl apply -f ephemeral-logs.yaml

# Wait for ready
kubectl wait --for=condition=Ready pod -l app=log-writer --timeout=60s
kubectl wait --for=condition=Ready pod -l app=ephemeral-writer --timeout=60s

# Wait 30 seconds for some logs
sleep 30

# Check PVC logs
PERSISTENT_POD=$(kubectl get pod -l app=log-writer -o jsonpath='{.items[0].metadata.name}')
kubectl exec $PERSISTENT_POD -- wc -l /data/app.log
kubectl exec $PERSISTENT_POD -- tail -3 /data/app.log

# Check emptyDir logs
EPHEMERAL_POD=$(kubectl get pod -l app=ephemeral-writer -o jsonpath='{.items[0].metadata.name}')
kubectl exec $EPHEMERAL_POD -- wc -l /data/app.log

# Delete both pods
kubectl delete pod -l app=log-writer
kubectl delete pod -l app=ephemeral-writer

# Wait for recreation
kubectl wait --for=condition=Ready pod -l app=log-writer --timeout=60s
kubectl wait --for=condition=Ready pod -l app=ephemeral-writer --timeout=60s

# Check PVC: data persists!
PERSISTENT_POD=$(kubectl get pod -l app=log-writer -o jsonpath='{.items[0].metadata.name}')
kubectl exec $PERSISTENT_POD -- head -3 /data/app.log
echo "Line count:"
kubectl exec $PERSISTENT_POD -- wc -l /data/app.log

# Check emptyDir: data LOST!
EPHEMERAL_POD=$(kubectl get pod -l app=ephemeral-writer -o jsonpath='{.items[0].metadata.name}')
kubectl exec $EPHEMERAL_POD -- wc -l /data/app.log
# Only new entries (old data gone)

# Cleanup
kubectl delete -f persistent-logs.yaml
kubectl delete -f ephemeral-logs.yaml
kubectl delete pvc app-logs
```

</details>

---

## Bài 2: Medium — Database Deployment với Storage Strategy

### Context
Bạn cần deploy MySQL database trên Kubernetes với persistent storage, thực hiện backup/restore test, và document storage decisions.

### Yêu cầu
1. Tạo PVC `mysql-data` với 1Gi storage.
2. Deploy MySQL 8.0 với:
   - PVC mount tại `/var/lib/mysql`.
   - ConfigMap cho MySQL config.
   - Secret cho root password.
   - Resource limits phù hợp.
   - Readiness/liveness probes.
   - Strategy: Recreate (database không nên rolling update).
3. Tạo database, table, insert sample data.
4. Thực hiện logical backup (mysqldump) lưu vào emptyDir volume.
5. Delete deployment (giữ PVC).
6. Recreate deployment → verify data intact.
7. Delete PVC → recreate deployment → verify data LOST.
8. Restore từ backup.
9. Document trade-offs giữa PVC persistence vs backup strategy.

### Expected Outcome
- MySQL chạy ổn định với PVC.
- Data persist qua deployment delete/recreate (khi giữ PVC).
- Data LOST khi xóa PVC.
- Backup/restore hoạt động.

### Hints
- MySQL readiness probe: `mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD`.
- Dùng `subPath: mysql` cho volumeMount để tránh conflict với MySQL init.
- `kubectl exec <pod> -- mysqldump -u root -p<pass> mydb > backup.sql`.
- Strategy `Recreate` bắt buộc cho database (không rolling update).

### Acceptance Criteria
- [ ] MySQL deployment với PVC thành công
- [ ] Data persist qua pod restart
- [ ] Backup thực hiện thành công
- [ ] Data mất khi xóa PVC (documented)
- [ ] Restore từ backup thành công
- [ ] Trade-off document viết xong

### Bonus Challenge
- Deploy MySQL với StatefulSet thay vì Deployment, so sánh behavior.
- Tạo CronJob automatic backup mỗi giờ.
- Implement point-in-time recovery concept.

<details>
<summary>Solution</summary>

```yaml
# mysql-storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: mysql-config
data:
  my.cnf: |
    [mysqld]
    max_connections=100
    innodb_buffer_pool_size=128M
    slow_query_log=1
    slow_query_log_file=/var/log/mysql/slow.log
    long_query_time=2
---
apiVersion: v1
kind: Secret
metadata:
  name: mysql-secret
type: Opaque
stringData:
  MYSQL_ROOT_PASSWORD: "rootpass123"
  MYSQL_DATABASE: "myapp"
  MYSQL_USER: "appuser"
  MYSQL_PASSWORD: "apppass456"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  strategy:
    type: Recreate
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
        - name: mysql
          image: mysql:8.0
          ports:
            - containerPort: 3306
          envFrom:
            - secretRef:
                name: mysql-secret
          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
              subPath: mysql
            - name: config
              mountPath: /etc/mysql/conf.d
            - name: backup
              mountPath: /backup
          resources:
            requests:
              cpu: 200m
              memory: 512Mi
            limits:
              cpu: 500m
              memory: 1Gi
          readinessProbe:
            exec:
              command:
                - bash
                - -c
                - "mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD"
            initialDelaySeconds: 30
            periodSeconds: 10
          livenessProbe:
            exec:
              command:
                - bash
                - -c
                - "mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD"
            initialDelaySeconds: 60
            periodSeconds: 15
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: mysql-data
        - name: config
          configMap:
            name: mysql-config
        - name: backup
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: mysql-svc
spec:
  selector:
    app: mysql
  ports:
    - port: 3306
      targetPort: 3306
```

```bash
# Deploy
kubectl apply -f mysql-storage.yaml
kubectl wait --for=condition=Ready pod -l app=mysql --timeout=180s

# Create data
MYSQL_POD=$(kubectl get pod -l app=mysql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $MYSQL_POD -- mysql -u root -prootpass123 -e "
USE myapp;
CREATE TABLE products (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100), price DECIMAL(10,2));
INSERT INTO products (name, price) VALUES ('Laptop', 999.99), ('Phone', 599.99), ('Tablet', 399.99);
SELECT * FROM products;
"

# Backup
kubectl exec $MYSQL_POD -- bash -c 'mysqldump -u root -prootpass123 myapp > /backup/myapp.sql'
kubectl exec $MYSQL_POD -- ls -la /backup/
kubectl cp $MYSQL_POD:/backup/myapp.sql ./myapp-backup.sql

# Test persistence: delete deployment, keep PVC
kubectl delete deployment mysql
kubectl get pvc mysql-data  # Still Bound!

# Recreate
kubectl apply -f mysql-storage.yaml
kubectl wait --for=condition=Ready pod -l app=mysql --timeout=180s

# Verify data intact
MYSQL_POD=$(kubectl get pod -l app=mysql -o jsonpath='{.items[0].metadata.name}')
kubectl exec $MYSQL_POD -- mysql -u root -prootpass123 -e "USE myapp; SELECT * FROM products;"
# Data still there!

# Test data loss: delete PVC
kubectl delete deployment mysql
kubectl delete pvc mysql-data

# Recreate everything
kubectl apply -f mysql-storage.yaml
kubectl wait --for=condition=Ready pod -l app=mysql --timeout=180s

# Data is GONE
MYSQL_POD=$(kubectl get pod -l app=mysql -o jsonpath='{.items[0].metadata.name}')
kubectl exec $MYSQL_POD -- mysql -u root -prootpass123 -e "USE myapp; SHOW TABLES;" 2>&1
# Empty database

# Restore from backup
kubectl cp ./myapp-backup.sql $MYSQL_POD:/tmp/myapp-backup.sql
kubectl exec $MYSQL_POD -- bash -c 'mysql -u root -prootpass123 myapp < /tmp/myapp-backup.sql'
kubectl exec $MYSQL_POD -- mysql -u root -prootpass123 -e "USE myapp; SELECT * FROM products;"
# Data restored!

# Cleanup
kubectl delete -f mysql-storage.yaml
kubectl delete pvc mysql-data 2>/dev/null
rm -f myapp-backup.sql
```

</details>

---

## Bài 3: Hard — Production Storage Architecture Design

### Context
Bạn là DevOps engineer cần thiết kế storage architecture cho một e-commerce platform gồm:
- PostgreSQL (primary + read replica) — cần high IOPS.
- Redis (persistent mode) — cần low latency.
- File upload service — cần shared storage (RWX).
- Elasticsearch — cần high throughput.

### Yêu cầu
1. Thiết kế StorageClass cho mỗi workload type:
   - `fast-ssd` — high IOPS cho database.
   - `standard` — general purpose.
   - `shared-nfs` — RWX cho file sharing.
2. Deploy PostgreSQL StatefulSet với:
   - `volumeClaimTemplate` sử dụng `fast-ssd` StorageClass.
   - 2 replicas (mô phỏng primary + replica).
   - Headless service.
   - Proper security context.
3. Deploy Redis StatefulSet với persistent storage.
4. Tạo ResourceQuota giới hạn storage per namespace.
5. Mô phỏng disaster scenarios:
   - Pod crash → verify data persistence.
   - Node drain → verify pod reschedule và data intact.
   - PVC deletion attempt → verify protection.
6. Document:
   - Storage architecture diagram.
   - Backup strategy cho mỗi component.
   - Recovery procedure.
   - Cost estimation (giả lập AWS pricing).

### Expected Outcome
- Multiple StorageClasses cho different tiers.
- StatefulSet với per-pod PVC.
- ResourceQuota enforce storage limits.
- Disaster scenarios handled.
- Architecture document hoàn chỉnh.

### Hints
- Trên kind, chỉ có `standard` StorageClass (local-path). Tạo StorageClasses khác với cùng provisioner nhưng naming khác nhau để mô phỏng.
- StatefulSet `volumeClaimTemplates` tự tạo PVC per pod.
- `kubectl drain <node> --ignore-daemonsets` để simulate node maintenance.
- PVC có finalizer protection khi đang được mount.

### Acceptance Criteria
- [ ] Multiple StorageClasses định nghĩa
- [ ] PostgreSQL StatefulSet với per-pod PVC
- [ ] Redis StatefulSet với persistence
- [ ] ResourceQuota enforced
- [ ] Pod crash recovery tested
- [ ] PVC deletion protection verified
- [ ] Architecture document complete
- [ ] Backup strategy documented

### Bonus Challenge
- Implement automated backup CronJob cho PostgreSQL (`pg_dump`).
- Tạo restore Job từ backup.
- Calculate actual AWS cost cho storage architecture (EBS gp3/io2 pricing).
- Implement monitoring: alert khi disk usage > 80%.

<details>
<summary>Solution</summary>

```yaml
# storage-classes.yaml
# Note: Trên kind, tất cả dùng rancher.io/local-path provisioner
# Trong production, mỗi class sẽ map đến storage tier khác nhau
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: rancher.io/local-path  # Production: ebs.csi.aws.com with io2
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: shared-nfs
provisioner: rancher.io/local-path  # Production: efs.csi.aws.com
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
---
# resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: storage-quota
  namespace: default
spec:
  hard:
    requests.storage: 10Gi
    persistentvolumeclaims: 20
---
# postgres-statefulset.yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres-sts-svc
spec:
  clusterIP: None
  selector:
    app: postgres-sts
  ports:
    - port: 5432
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-sts-secret
type: Opaque
stringData:
  POSTGRES_PASSWORD: "secure-sts-pass"
  POSTGRES_DB: "ecommerce"
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-sts
spec:
  serviceName: postgres-sts-svc
  replicas: 2
  selector:
    matchLabels:
      app: postgres-sts
  template:
    metadata:
      labels:
        app: postgres-sts
    spec:
      securityContext:
        fsGroup: 999
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          envFrom:
            - secretRef:
                name: postgres-sts-secret
          volumeMounts:
            - name: pgdata
              mountPath: /var/lib/postgresql/data
              subPath: pgdata
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "postgres"]
            initialDelaySeconds: 15
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["pg_isready", "-U", "postgres"]
            initialDelaySeconds: 30
            periodSeconds: 15
  volumeClaimTemplates:
    - metadata:
        name: pgdata
        labels:
          app: postgres-sts
      spec:
        storageClassName: fast-ssd
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
---
# redis-statefulset.yaml
apiVersion: v1
kind: Service
metadata:
  name: redis-sts-svc
spec:
  clusterIP: None
  selector:
    app: redis-sts
  ports:
    - port: 6379
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-sts-config
data:
  redis.conf: |
    appendonly yes
    save 60 1000
    maxmemory 128mb
    maxmemory-policy allkeys-lru
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-sts
spec:
  serviceName: redis-sts-svc
  replicas: 1
  selector:
    matchLabels:
      app: redis-sts
  template:
    metadata:
      labels:
        app: redis-sts
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
            - name: redis-data
              mountPath: /data
            - name: config
              mountPath: /etc/redis
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
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
            name: redis-sts-config
  volumeClaimTemplates:
    - metadata:
        name: redis-data
        labels:
          app: redis-sts
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 500Mi
```

```bash
# Apply all
kubectl apply -f storage-classes.yaml
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f redis-statefulset.yaml

# Wait for ready
kubectl wait --for=condition=Ready pod/postgres-sts-0 --timeout=120s
kubectl wait --for=condition=Ready pod/postgres-sts-1 --timeout=120s
kubectl wait --for=condition=Ready pod/redis-sts-0 --timeout=60s

# Check PVCs (should have 3: 2 for postgres, 1 for redis)
kubectl get pvc
kubectl get pv

# Write data to postgres-sts-0
kubectl exec postgres-sts-0 -- psql -U postgres -d ecommerce -c "
CREATE TABLE orders (id SERIAL PRIMARY KEY, product VARCHAR(100), amount DECIMAL(10,2));
INSERT INTO orders (product, amount) VALUES ('Laptop', 999.99);
SELECT * FROM orders;
"

# Write data to Redis
kubectl exec redis-sts-0 -- redis-cli SET session:user1 '{"id":1,"name":"Alice"}'
kubectl exec redis-sts-0 -- redis-cli GET session:user1

# Check ResourceQuota
kubectl describe resourcequota storage-quota

# === Disaster Scenario 1: Pod crash ===
kubectl delete pod postgres-sts-0
kubectl wait --for=condition=Ready pod/postgres-sts-0 --timeout=120s
kubectl exec postgres-sts-0 -- psql -U postgres -d ecommerce -c "SELECT * FROM orders;"
# Data intact!

# === Disaster Scenario 2: PVC deletion protection trên disposable PVC ===
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: delete-protection-demo
  labels:
    app: delete-protection-demo
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 100Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: delete-protection-demo
  labels:
    app: delete-protection-demo
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo demo > /data/file && sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
      resources:
        requests:
          cpu: 25m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 32Mi
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: delete-protection-demo
EOF
kubectl wait --for=condition=Ready pod/delete-protection-demo --timeout=60s
kubectl delete pvc delete-protection-demo --wait=false
sleep 2
kubectl get pvc delete-protection-demo
# STATUS: Terminating (pvc-protection finalizer giữ PVC đến khi pod unmount)
kubectl delete pod delete-protection-demo
kubectl wait --for=delete pvc/delete-protection-demo --timeout=60s
kubectl get pvc pgdata-postgres-sts-0
# STATUS: Bound (PVC database chính không bị đụng đến)

# === Backup ===
kubectl exec postgres-sts-0 -- pg_dump -U postgres ecommerce > ecommerce-backup.sql
echo "Backup size: $(wc -c < ecommerce-backup.sql) bytes"

# Cleanup
kubectl delete statefulset postgres-sts redis-sts
kubectl delete svc postgres-sts-svc redis-sts-svc
kubectl delete configmap redis-sts-config
kubectl delete secret postgres-sts-secret
kubectl delete pod delete-protection-demo 2>/dev/null
kubectl delete pvc delete-protection-demo 2>/dev/null
kubectl delete pvc -l app=postgres-sts
kubectl delete pvc -l app=redis-sts
kubectl delete storageclass fast-ssd shared-nfs
kubectl delete resourcequota storage-quota
rm -f ecommerce-backup.sql
```

</details>

