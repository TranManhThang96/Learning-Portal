# Day 23: Document — Kubernetes Upgrade, Backup & Node Maintenance

## 1. Upgrade Checklist

### Pre-Upgrade

- [ ] **Đọc release notes** của target version (breaking changes, deprecated APIs)
- [ ] **Check version skew**: current version → target version (chỉ +1 minor)
- [ ] **Check deprecated APIs**: `kubectl deprecations` hoặc `kubent` tool
- [ ] **Verify cluster health**: tất cả nodes Ready, pods healthy
- [ ] **Backup etcd**: snapshot + copy ra external storage
- [ ] **Backup critical resources**: Velero hoặc `kubectl get -o yaml`
- [ ] **Test upgrade trên staging/dev** cluster trước
- [ ] **Notify team**: maintenance window, expected downtime
- [ ] **Verify PDB**: tất cả critical workloads có PDB
- [ ] **Check certificate expiry**: `kubeadm certs check-expiration`
- [ ] **Verify addon compatibility**: Ingress controller, CNI, CSI, monitoring stack
- [ ] **Document rollback plan**: etcd restore steps, version downgrade

### During Upgrade

- [ ] **Upgrade control plane** trước (API server, controller-manager, scheduler)
- [ ] **Verify control plane healthy**: `kubectl get componentstatuses` (deprecated nhưng hữu ích)
- [ ] **Upgrade nodes tuần tự** (1 node tại 1 thời điểm):
  - [ ] Cordon node
  - [ ] Drain node (with --ignore-daemonsets)
  - [ ] Upgrade kubelet + kube-proxy
  - [ ] Restart kubelet
  - [ ] Uncordon node
  - [ ] Verify node Ready + pods rescheduled
- [ ] **Monitor PDB violations**: `kubectl get pdb -A`
- [ ] **Monitor pod health**: `kubectl get pods -A | grep -v Running`
- [ ] **Check version consistency**: `kubectl get nodes -o wide`

### Post-Upgrade

- [ ] **Verify all nodes** ở target version: `kubectl get nodes`
- [ ] **Verify all pods** Running: `kubectl get pods -A`
- [ ] **Verify services healthy**: endpoints populated, traffic flowing
- [ ] **Run smoke tests**: critical API paths
- [ ] **Check monitoring**: no new alerts, metrics normal
- [ ] **Update kubectl** trên admin machines
- [ ] **Update documentation**: cluster version, addon versions
- [ ] **Archive upgrade notes**: timeline, issues encountered, fixes applied

---

## 2. Version Skew Compatibility Matrix

### Kubernetes 1.28 - 1.31

```
                    API Server Version
                    1.28    1.29    1.30    1.31
kubelet   1.28      ✅      ✅      ✅      ❌
          1.29      ❌      ✅      ✅      ✅
          1.30      ❌      ❌      ✅      ✅
          1.31      ❌      ❌      ❌      ✅

kubectl   1.28      ✅      ✅      ❌      ❌
          1.29      ✅      ✅      ✅      ❌
          1.30      ❌      ✅      ✅      ✅
          1.31      ❌      ❌      ✅      ✅
```

**Quy tắc nhớ nhanh:**
- kubelet: cùng hoặc cũ hơn API server tối đa 2 minor versions
- kubectl: ± 1 minor version so với API server
- controller-manager, scheduler: cùng hoặc cũ hơn 1 minor

### Upgrade Path Examples

```
✅ Correct: 1.27 → 1.28 → 1.29 → 1.30
❌ Wrong:   1.27 → 1.30 (skip 2 minor versions)
❌ Wrong:   Upgrade kubelet trước API server
✅ Correct: Upgrade API server → rồi kubelet
```

---

## 3. Drain & Cordon Command Reference

### Cordon

```bash
# Mark node unschedulable
kubectl cordon <node-name>

# Verify
kubectl get nodes
# NAME          STATUS                     ROLES    AGE
# worker-1      Ready,SchedulingDisabled   <none>   1d

# Undo cordon
kubectl uncordon <node-name>
```

### Drain

```bash
# Basic drain (sẽ fail nếu có DaemonSet pods hoặc local data)
kubectl drain <node-name>

# Production drain
kubectl drain <node-name> \
  --ignore-daemonsets \          # Bỏ qua DaemonSet pods (chúng sẽ respawn)
  --delete-emptydir-data \       # Xác nhận xóa emptyDir data
  --force \                      # Force evict standalone pods (không có controller)
  --grace-period=30 \            # Override pod terminationGracePeriod
  --timeout=300s \               # Drain timeout (fail nếu quá lâu)
  --pod-selector='app!=critical' # Chỉ drain pods match selector
  --dry-run=client               # Preview — không thực sự drain

# Drain với output chi tiết
kubectl drain <node-name> \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --timeout=300s \
  -v=4                           # Verbose logging
```

### Drain Troubleshooting

| Error | Nguyên nhân | Fix |
|-------|-------------|-----|
| `cannot delete DaemonSet-managed Pods` | DaemonSet pods trên node | `--ignore-daemonsets` |
| `cannot delete Pods with local storage` | emptyDir volumes | `--delete-emptydir-data` |
| `cannot delete Pods not managed by...` | Standalone pods (không có controller) | `--force` |
| `Cannot evict pod... disruption budget` | PDB blocking | Wait, hoặc fix PDB |
| `context deadline exceeded` | Drain quá timeout | Tăng `--timeout` |

---

## 4. PDB Configuration Templates

### Template 1: Web API (High Availability)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-api-pdb
  namespace: production
spec:
  minAvailable: "60%"    # Luôn có ≥ 60% pods
  selector:
    matchLabels:
      app: web-api
      tier: frontend
```

### Template 2: Background Worker (Flexible)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: worker-pdb
  namespace: production
spec:
  maxUnavailable: 2       # Cho phép 2 pods down cùng lúc
  selector:
    matchLabels:
      app: background-worker
```

### Template 3: Critical Service (Strict)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-pdb
  namespace: production
spec:
  minAvailable: 2         # Luôn có ≥ 2 pods (cho 3 replicas)
  selector:
    matchLabels:
      app: payment-gateway
```

### PDB Decision Guide

| Workload Type | Replicas | PDB Recommendation |
|---------------|----------|-------------------|
| Critical API (payment, auth) | 3+ | minAvailable: N-1 |
| Standard API | 2-5 | maxUnavailable: 1 |
| Web frontend | 3-10 | maxUnavailable: "25%" |
| Background worker | 2+ | minAvailable: 1 |
| Batch job | 1+ | Không cần PDB |
| Singleton (1 replica) | 1 | Không dùng PDB (sẽ block drain) |

**Cảnh báo**: Không set `minAvailable = replicas` — drain sẽ KHÔNG BAO GIỜ hoàn thành.

---

## 5. Velero Command Cheat Sheet

### Installation

```bash
# Install CLI
brew install velero           # macOS
choco install velero          # Windows
# hoặc download từ GitHub releases

# Install server (AWS S3 example)
velero install \
  --provider aws \
  --plugins velero/velero-plugin-for-aws:v1.8.0 \
  --bucket my-velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config region=us-east-1

# Verify installation
velero version
kubectl get pods -n velero
```

### Backup Commands

```bash
# Backup toàn bộ cluster
velero backup create full-backup

# Backup 1 namespace
velero backup create ns-backup --include-namespaces production

# Backup nhiều namespaces
velero backup create multi-backup --include-namespaces production,staging

# Backup theo label
velero backup create label-backup --selector app=payment

# Backup exclud resource types
velero backup create no-events --exclude-resources events

# Backup với TTL (tự xóa sau 30 ngày)
velero backup create tmp-backup --ttl 720h

# Backup snapshot volumes
velero backup create vol-backup \
  --include-namespaces production \
  --snapshot-volumes=true

# List backups
velero backup get

# Describe backup (chi tiết)
velero backup describe <backup-name> --details

# Backup logs
velero backup logs <backup-name>

# Delete backup
velero backup delete <backup-name>
```

### Restore Commands

```bash
# Restore toàn bộ backup
velero restore create --from-backup <backup-name>

# Restore vào namespace khác
velero restore create --from-backup <backup-name> \
  --namespace-mappings production:production-restored

# Restore chỉ 1 resource type
velero restore create --from-backup <backup-name> \
  --include-resources deployments,services

# Restore exclude namespace
velero restore create --from-backup <backup-name> \
  --exclude-namespaces kube-system

# List restores
velero restore get

# Describe restore
velero restore describe <restore-name> --details

# Restore logs
velero restore logs <restore-name>
```

### Schedule Commands

```bash
# Daily backup lúc 2 AM
velero schedule create daily \
  --schedule="0 2 * * *" \
  --include-namespaces production \
  --ttl 720h

# Weekly backup
velero schedule create weekly \
  --schedule="0 3 * * 0" \
  --ttl 2160h

# List schedules
velero schedule get

# Delete schedule
velero schedule delete <schedule-name>
```

---

## 6. Backup & Restore Runbook Template

```markdown
# Runbook: Kubernetes Backup & Restore

## 1. Routine Backup Verification (Monthly)

### Steps
1. Check backup schedule running:
   ```bash
   velero schedule get
   velero backup get --sort-by=.metadata.creationTimestamp
   ```
2. Verify latest backup completed:
   ```bash
   velero backup describe <latest-backup> --details
   ```
3. Test restore to staging:
   ```bash
   velero restore create test-restore \
     --from-backup <latest-backup> \
     --namespace-mappings production:restore-test
   ```
4. Verify restored resources:
   ```bash
   kubectl get all -n restore-test
   ```
5. Cleanup test:
   ```bash
   kubectl delete namespace restore-test
   velero restore delete test-restore
   ```

## 2. Emergency Restore Procedure

### Pre-conditions
- [ ] Backup exists and is valid
- [ ] kubectl access to target cluster
- [ ] Velero CLI installed

### Steps
1. **Assess damage**: What was lost? Namespace? Specific resources?
2. **Identify backup**: Find suitable backup
   ```bash
   velero backup get
   velero backup describe <backup> --details
   ```
3. **Notify team**: "Initiating restore from backup [name], ETA [X] minutes"
4. **Execute restore**:
   ```bash
   velero restore create emergency-restore \
     --from-backup <backup-name> \
     --include-namespaces <namespace>
   ```
5. **Monitor restore**:
   ```bash
   velero restore describe emergency-restore --details
   velero restore logs emergency-restore
   ```
6. **Verify**:
   ```bash
   kubectl get pods -n <namespace>
   kubectl get endpoints -n <namespace>
   # Run smoke tests
   ```
7. **Post-restore**:
   - Check persistent data consistency
   - Verify secrets/configmaps correct
   - Run integration tests
   - Update team: "Restore complete"

### Estimated RTO
| Scope | Estimated Time |
|-------|---------------|
| Single namespace (no volumes) | 2-5 minutes |
| Single namespace (with volumes) | 5-15 minutes |
| Multiple namespaces | 10-30 minutes |
| Full cluster restore | 30-60 minutes |

### Rollback
If restore causes issues:
```bash
# Delete restored resources
kubectl delete namespace <namespace>
# Or delete specific resources
velero restore delete emergency-restore
```
```

---

## 7. etcd Backup Quick Reference

```bash
# === BACKUP ===

# Snapshot etcd
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-$(date +%Y%m%d%H%M).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify snapshot
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd-*.db --write-table

# === RESTORE (DANGER — only for disaster recovery) ===

# 1. Stop API server
sudo mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/

# 2. Stop etcd
sudo mv /etc/kubernetes/manifests/etcd.yaml /tmp/

# 3. Backup current data
sudo mv /var/lib/etcd /var/lib/etcd.bak

# 4. Restore from snapshot
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-YYYYMMDD.db \
  --data-dir=/var/lib/etcd

# 5. Restart etcd
sudo mv /tmp/etcd.yaml /etc/kubernetes/manifests/

# 6. Wait for etcd ready, then restart API server
sudo mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/

# 7. Verify
kubectl get nodes
kubectl get pods -A
```

### etcd Backup Automation (CronJob on control plane)

```bash
# /etc/cron.d/etcd-backup
0 */6 * * * root ETCDCTL_API=3 /usr/local/bin/etcdctl snapshot save \
  /backup/etcd-$(date +\%Y\%m\%d-\%H\%M).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  && find /backup -name 'etcd-*.db' -mtime +7 -delete \
  2>&1 | logger -t etcd-backup
```

