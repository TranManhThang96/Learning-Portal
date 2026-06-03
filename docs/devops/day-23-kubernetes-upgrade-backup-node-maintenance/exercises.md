# Day 23: Exercises — Kubernetes Upgrade, Backup & Node Maintenance

---

## Bài 1: Easy — Cordon, Drain & PDB Cơ Bản

### Context

Bạn cần bảo trì 1 worker node trong cluster. Cluster đang chạy 1 web application với 3 replicas. Bạn cần drain node mà không gây downtime.

### Yêu cầu

1. Tạo kind cluster với 1 control-plane + 2 workers.
2. Deploy Deployment `web-server` (nginx, 4 replicas) với PDB `minAvailable: 2`.
3. Verify pods phân bố trên cả 2 workers.
4. Cordon 1 worker → verify node SchedulingDisabled, pods vẫn chạy.
5. Drain worker đã cordon → verify pods reschedule sang worker còn lại.
6. Uncordon worker → verify node Schedulable.

### Expected Outcome

- PDB respected: luôn có ≥ 2 pods Running trong quá trình drain.
- Drain hoàn thành trong < 60s.
- Sau uncordon, node có thể nhận pods mới.

### Hint

- `kubectl drain` cần flag `--ignore-daemonsets`.
- Xem `kubectl get pdb` để track ALLOWED DISRUPTIONS.
- Dùng `kubectl get pods -o wide --watch` trong terminal khác để observe real-time.

### Acceptance Criteria

- [ ] Cluster 3 nodes (1 CP + 2 worker) tạo thành công.
- [ ] 4 pods phân bố trên 2 workers.
- [ ] PDB created, ALLOWED DISRUPTIONS = 2.
- [ ] Cordon thành công, node SchedulingDisabled.
- [ ] Drain thành công, pods trên worker bị drain → rescheduled.
- [ ] Uncordon thành công.
- [ ] Không có downtime (luôn ≥ 2 pods Running).

### Bonus Challenge

Thêm deployment thứ 2 `critical-app` (2 replicas) với PDB `minAvailable: 2` — PDB = replicas. Thử drain node chứa 1 pod của `critical-app` → quan sát drain bị stuck. Giải thích tại sao và đề xuất fix.

<details>
<summary>Solution</summary>

```bash
# 1. Tạo cluster
kind create cluster --name drain-lab --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

# 2. Deploy app + PDB
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web-server
  template:
    metadata:
      labels:
        app: web-server
    spec:
      containers:
        - name: nginx
          image: nginx:1.25-alpine
          resources:
            requests: {cpu: 50m, memory: 32Mi}
            limits: {cpu: 100m, memory: 64Mi}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-server-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: web-server
EOF

# 3. Verify distribution
kubectl get pods -o wide
kubectl get pdb

# 4. Cordon worker 1
NODE=$(kubectl get nodes --no-headers | grep worker | head -1 | awk '{print $1}')
kubectl cordon $NODE
kubectl get nodes

# 5. Drain
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=120s

# Watch trong terminal khác:
# kubectl get pods -o wide --watch

kubectl get pods -o wide
# Tất cả pods trên worker còn lại

# 6. Uncordon
kubectl uncordon $NODE
kubectl get nodes

# Bonus: PDB = replicas (stuck drain)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: critical-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: critical-app
  template:
    metadata:
      labels:
        app: critical-app
    spec:
      containers:
        - name: app
          image: nginx:1.25-alpine
          resources:
            requests: {cpu: 50m, memory: 32Mi}
            limits: {cpu: 100m, memory: 64Mi}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: critical-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: critical-app
EOF

kubectl get pods -o wide
# critical-app pods trên 2 workers

# Drain worker chứa 1 critical-app pod
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=30s
# STUCK! Cannot evict pod: would violate PDB
# Fix: minAvailable nên < replicas, ví dụ minAvailable: 1

# Cleanup
kind delete cluster --name drain-lab
```

</details>

---

## Bài 2: Medium — Full Upgrade Simulation với etcd Backup

### Context

Bạn là DevOps engineer chuẩn bị upgrade cluster Kubernetes. Trước khi upgrade, bạn cần: backup etcd, test PDB behavior, drain nodes theo đúng quy trình, và verify cluster health sau maintenance.

### Yêu cầu

1. Tạo kind cluster (1 CP + 2 workers).
2. Deploy 2 ứng dụng:
   - `api-server`: 3 replicas, PDB maxUnavailable=1.
   - `background-worker`: 2 replicas, PDB minAvailable=1.
3. **Backup etcd** từ control plane node.
4. **Pre-upgrade checklist**: verify versions, PDB status, node conditions.
5. **Simulate node maintenance**:
   - Drain worker-1 (verify PDB respected).
   - "Upgrade" worker-1 (chỉ simulate bằng uncordon).
   - Drain worker-2.
   - "Upgrade" worker-2.
6. **Post-upgrade verification**: tất cả pods Running, services healthy, PDB OK.

### Expected Outcome

- etcd backup file tạo thành công, verified.
- Drain/uncordon workflow hoàn chỉnh, zero downtime.
- Pre/post checklist documented.

### Hint

- etcd certs nằm ở `/etc/kubernetes/pki/etcd/` trong kind control plane container.
- Dùng `docker exec -it <container> bash` để vào control plane.
- PDB maxUnavailable=1 cho phép drain 1 pod tại 1 thời điểm.

### Acceptance Criteria

- [ ] etcd backup created và verified (status command thành công).
- [ ] Pre-upgrade checklist completed (versions, PDB, node status).
- [ ] Worker-1 drained → pods rescheduled → uncordoned.
- [ ] Worker-2 drained → pods rescheduled → uncordoned.
- [ ] Zero downtime verified (luôn có pods Running cho cả 2 apps).
- [ ] Post-upgrade checklist completed.
- [ ] Toàn bộ quy trình documented (commands + output).

### Bonus Challenge

Viết bash script tự động hóa upgrade workflow: pre-check → backup → drain → uncordon → post-check cho từng node.

<details>
<summary>Solution</summary>

```bash
# 1. Create cluster
kind create cluster --name upgrade-sim --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF

# 2. Deploy apps + PDB
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: nginx:1.25-alpine
          ports: [{containerPort: 80}]
          resources:
            requests: {cpu: 50m, memory: 32Mi}
            limits: {cpu: 100m, memory: 64Mi}
          readinessProbe:
            httpGet: {path: /, port: 80}
            initialDelaySeconds: 3
            periodSeconds: 3
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: api-server
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: background-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: background-worker
  template:
    metadata:
      labels:
        app: background-worker
    spec:
      containers:
        - name: worker
          image: busybox:1.36
          command: ["sh", "-c", "while true; do echo working; sleep 10; done"]
          resources:
            requests: {cpu: 50m, memory: 32Mi}
            limits: {cpu: 100m, memory: 64Mi}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: worker-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: background-worker
EOF

sleep 15
kubectl get pods -o wide
kubectl get pdb

# 3. Backup etcd
docker exec -it upgrade-sim-control-plane bash -c '
ETCDCTL_API=3 etcdctl snapshot save /tmp/etcd-backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key && \
ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-backup.db --write-table
'
docker cp upgrade-sim-control-plane:/tmp/etcd-backup.db ./etcd-backup.db

# 4. Pre-upgrade checklist
echo "=== PRE-UPGRADE CHECKLIST ==="
echo "--- Node Versions ---"
kubectl get nodes -o custom-columns=NAME:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion,STATUS:.status.conditions[-1].type
echo "--- PDB Status ---"
kubectl get pdb
echo "--- Pod Distribution ---"
kubectl get pods -o wide

# 5. Rolling node maintenance
WORKERS=$(kubectl get nodes --no-headers | grep worker | awk '{print $1}')
for NODE in $WORKERS; do
  echo "=== Maintaining $NODE ==="
  kubectl cordon $NODE
  kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=120s
  echo "Node $NODE drained. Simulating upgrade..."
  sleep 5
  kubectl uncordon $NODE
  echo "Node $NODE uncordoned."
  sleep 10
  kubectl get pods -o wide
  echo ""
done

# 6. Post-upgrade
echo "=== POST-UPGRADE CHECKLIST ==="
kubectl get nodes
kubectl get pods -o wide
kubectl get pdb
kubectl get endpoints

# Cleanup
kind delete cluster --name upgrade-sim
rm -f etcd-backup.db
```

**Bonus — Upgrade automation script:**

```bash
#!/bin/bash
set -euo pipefail

CLUSTER_NAME="production"
BACKUP_DIR="/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=== Step 1: Pre-flight checks ==="
kubectl get nodes
kubectl get pdb -A
kubectl get pods -A | grep -v Running | grep -v Completed

echo "=== Step 2: etcd Backup ==="
# (backup commands here)
echo "Backup saved to $BACKUP_DIR"

echo "=== Step 3: Rolling Node Upgrade ==="
WORKERS=$(kubectl get nodes --no-headers -l 'node-role.kubernetes.io/control-plane!=' | awk '{print $1}')
TOTAL=$(echo "$WORKERS" | wc -l)
COUNT=0

for NODE in $WORKERS; do
  COUNT=$((COUNT + 1))
  echo "--- Upgrading node $NODE ($COUNT/$TOTAL) ---"

  echo "Cordoning..."
  kubectl cordon "$NODE"

  echo "Draining..."
  kubectl drain "$NODE" \
    --ignore-daemonsets \
    --delete-emptydir-data \
    --timeout=300s

  echo "Performing upgrade on $NODE..."
  # ssh $NODE "sudo apt-get update && sudo apt-get install -y kubelet=1.30.0-00 kubectl=1.30.0-00"
  # ssh $NODE "sudo systemctl restart kubelet"
  sleep 5  # Simulate

  echo "Uncordoning..."
  kubectl uncordon "$NODE"

  echo "Waiting for node Ready..."
  kubectl wait --for=condition=Ready node/"$NODE" --timeout=120s

  echo "Waiting for pods to reschedule..."
  sleep 15

  echo "Node $NODE upgraded. Verifying..."
  kubectl get pods -o wide | grep -v Running | grep -v Completed || true
  echo ""
done

echo "=== Step 4: Post-upgrade Verification ==="
kubectl get nodes -o custom-columns=NAME:.metadata.name,VERSION:.status.nodeInfo.kubeletVersion,STATUS:.status.conditions[-1].type
kubectl get pods -A | grep -v Running | grep -v Completed | head -10 || echo "All pods healthy"
echo "Upgrade complete!"
```

</details>

---

## Bài 3: Hard — Disaster Recovery: Backup, Simulate Failure, Restore

### Context

Bạn là SRE cho một logistics platform. CTO yêu cầu: "Chứng minh rằng chúng ta có thể recover cluster trong 30 phút nếu namespace `logistics` bị xóa nhầm." Bạn cần implement backup strategy, simulate disaster, và restore.

### Yêu cầu

1. Tạo kind cluster.
2. Deploy "logistics platform" trong namespace `logistics`:
   - Deployment `shipment-api` (3 replicas, nginx).
   - Deployment `tracking-worker` (2 replicas, busybox).
   - Service `shipment-api-svc`.
   - ConfigMap `app-config` (với 3 config entries).
   - PDB cho `shipment-api`.
3. **Backup namespace** bằng `kubectl get` export (vì Velero cần cloud storage).
4. **Simulate disaster**: xóa toàn bộ namespace `logistics`.
5. **Restore**: recreate namespace và apply backup.
6. **Verify**: tất cả resources restored đúng.
7. **Viết DR runbook**: step-by-step restore procedure, estimated RTO.

### Expected Outcome

- Backup chứa tất cả resources trong namespace.
- Sau delete + restore, tất cả resources hoạt động lại.
- DR runbook có RTO estimate < 15 phút.

### Hint

- `kubectl get all,configmap,pdb -n logistics -o yaml > backup.yaml` để export.
- Cần clean up metadata (resourceVersion, uid, status) trước khi restore.
- Dùng `yq` hoặc manual edit để clean metadata.
- Namespace phải tạo lại trước khi apply resources.

### Acceptance Criteria

- [ ] Logistics platform deployed + verified hoạt động.
- [ ] Backup file tạo thành công, chứa đủ resources.
- [ ] Namespace deleted → verified mất hết.
- [ ] Restore thành công từ backup.
- [ ] Tất cả pods Running, service có endpoints, ConfigMap có data.
- [ ] DR runbook viết ≥ 10 steps, có RTO estimate.
- [ ] RTO thực tế < 15 phút.

### Bonus Challenge

Viết script tự động backup: chạy mỗi giờ, giữ 24 bản backup gần nhất, rotate bản cũ. Test restore từ backup 3 giờ trước.

<details>
<summary>Solution</summary>

```bash
# 1. Create cluster
kind create cluster --name dr-lab

# 2. Deploy logistics platform
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: logistics
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: logistics
data:
  DATABASE_URL: "postgres://db:5432/logistics"
  REDIS_URL: "redis://cache:6379"
  LOG_LEVEL: "info"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shipment-api
  namespace: logistics
spec:
  replicas: 3
  selector:
    matchLabels:
      app: shipment-api
  template:
    metadata:
      labels:
        app: shipment-api
    spec:
      containers:
        - name: api
          image: nginx:1.25-alpine
          ports: [{containerPort: 80}]
          envFrom:
            - configMapRef:
                name: app-config
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 100m, memory: 128Mi}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tracking-worker
  namespace: logistics
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tracking-worker
  template:
    metadata:
      labels:
        app: tracking-worker
    spec:
      containers:
        - name: worker
          image: busybox:1.36
          command: ["sh", "-c", "while true; do echo tracking; sleep 10; done"]
          resources:
            requests: {cpu: 50m, memory: 32Mi}
            limits: {cpu: 100m, memory: 64Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: shipment-api-svc
  namespace: logistics
spec:
  selector:
    app: shipment-api
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: shipment-api-pdb
  namespace: logistics
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: shipment-api
EOF

# Verify
sleep 15
echo "=== Pre-backup state ==="
kubectl get all,cm,pdb -n logistics

# 3. Backup
mkdir -p backups
kubectl get deployments -n logistics -o yaml > backups/deployments.yaml
kubectl get services -n logistics -o yaml > backups/services.yaml
kubectl get configmaps -n logistics -o yaml > backups/configmaps.yaml
kubectl get pdb -n logistics -o yaml > backups/pdb.yaml

# Clean metadata for restore (remove resourceVersion, uid, status, creationTimestamp)
for f in backups/*.yaml; do
  # Simple cleanup - in production, use yq or proper tool
  sed -i '/resourceVersion:/d' "$f"
  sed -i '/uid:/d' "$f"
  sed -i '/creationTimestamp:/d' "$f"
  sed -i '/selfLink:/d' "$f"
  sed -i '/generation:/d' "$f"
done

echo "=== Backup files ==="
ls -la backups/

# 4. Simulate disaster
echo "=== DISASTER: Deleting namespace ==="
kubectl delete namespace logistics --timeout=60s

echo "=== Verify deletion ==="
kubectl get namespace logistics 2>&1 || echo "Namespace deleted!"

# 5. Restore
echo "=== RESTORING ==="
START_TIME=$(date +%s)

kubectl create namespace logistics
kubectl apply -f backups/configmaps.yaml
kubectl apply -f backups/deployments.yaml
kubectl apply -f backups/services.yaml
kubectl apply -f backups/pdb.yaml

# Wait for pods
echo "Waiting for pods..."
kubectl wait --for=condition=Available deployment --all -n logistics --timeout=120s

END_TIME=$(date +%s)
RTO=$((END_TIME - START_TIME))

# 6. Verify
echo "=== POST-RESTORE VERIFICATION ==="
kubectl get all,cm,pdb -n logistics
kubectl get endpoints -n logistics
echo ""
echo "RTO: ${RTO} seconds"

# 7. DR Runbook (printed)
cat <<'RUNBOOK'
# DR Runbook: Restore Namespace "logistics"

## Prerequisites
- kubectl access to cluster
- Backup files in /backups/ directory
- RBAC permission to create namespace + resources

## Steps
1. Verify disaster scope: `kubectl get ns logistics`
2. Check backup availability: `ls -la /backups/`
3. Create namespace: `kubectl create namespace logistics`
4. Apply ConfigMaps: `kubectl apply -f backups/configmaps.yaml`
5. Apply Deployments: `kubectl apply -f backups/deployments.yaml`
6. Apply Services: `kubectl apply -f backups/services.yaml`
7. Apply PDBs: `kubectl apply -f backups/pdb.yaml`
8. Wait for pods: `kubectl wait --for=condition=Available deployment --all -n logistics --timeout=120s`
9. Verify endpoints: `kubectl get endpoints -n logistics`
10. Verify ConfigMap data: `kubectl get cm app-config -n logistics -o yaml`
11. Run smoke test: `kubectl exec -n logistics deploy/shipment-api -- curl -s localhost:80`
12. Notify stakeholders: all-clear

## Estimated RTO
- Namespace + resources restore: ~30 seconds
- Pod scheduling + image pull: ~60-120 seconds
- Total: ~2-3 minutes (cached images) / ~5-10 minutes (cold pull)

## Limitations
- PersistentVolume data NOT restored (this backup is resource-level only)
- Secrets need separate restore from vault
- In-flight requests during disaster are lost
RUNBOOK

# Cleanup
kind delete cluster --name dr-lab
rm -rf backups/
```

**Bonus — Auto backup script:**

```bash
#!/bin/bash
# backup-logistics.sh — Run via cron every hour
set -euo pipefail

BACKUP_DIR="/backups/logistics"
NAMESPACE="logistics"
MAX_BACKUPS=24
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
CURRENT_BACKUP="$BACKUP_DIR/$TIMESTAMP"

mkdir -p "$CURRENT_BACKUP"

# Export resources
for RESOURCE in deployments services configmaps pdb secrets; do
  kubectl get "$RESOURCE" -n "$NAMESPACE" -o yaml > "$CURRENT_BACKUP/$RESOURCE.yaml" 2>/dev/null || true
done

echo "$TIMESTAMP" > "$CURRENT_BACKUP/timestamp.txt"
echo "Backup saved to $CURRENT_BACKUP"

# Rotate old backups
BACKUP_COUNT=$(ls -1d "$BACKUP_DIR"/20* 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
  REMOVE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
  ls -1d "$BACKUP_DIR"/20* | head -n "$REMOVE_COUNT" | xargs rm -rf
  echo "Rotated $REMOVE_COUNT old backups"
fi
```

</details>

---

## Solution/Reference Implementation

Các lời giải chi tiết nằm trong block `<details><summary>Solution</summary>` của từng bài để người học có thể thử trước khi mở đáp án. Reference cuối file:

- **Bài 1 — Easy**: tạo cluster nhiều node, test `cordon`/`drain`, quan sát PDB và cleanup.
- **Bài 2 — Medium**: mô phỏng upgrade workflow với etcd backup, pre-check, rolling node maintenance và post-check.
- **Bài 3 — Hard**: backup namespace, mô phỏng disaster, restore workload và viết DR runbook cùng backup script.

