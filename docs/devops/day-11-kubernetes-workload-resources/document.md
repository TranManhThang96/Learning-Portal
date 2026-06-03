# Day 11: Kubernetes Workload Resources — Cheat Sheet & Decision Framework

## Quick Reference: Workload Resources

### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <name>
spec:
  replicas: <N>
  selector:
    matchLabels:
      app: <label>
  strategy:
    type: RollingUpdate | Recreate
    rollingUpdate:          # Chỉ khi type: RollingUpdate
      maxSurge: 25%
      maxUnavailable: 25%
  template:
    metadata:
      labels:
        app: <label>
    spec:
      containers:
        - name: <container>
          image: <image>:<tag>
```

**Commands thường dùng:**
```bash
kubectl rollout status deployment/<name>
kubectl rollout history deployment/<name>
kubectl rollout undo deployment/<name>
kubectl rollout undo deployment/<name> --to-revision=<N>
kubectl scale deployment/<name> --replicas=<N>
kubectl set image deployment/<name> <container>=<new-image>
```

### StatefulSet
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: <name>
spec:
  serviceName: <headless-service>    # BẮT BUỘC
  replicas: <N>
  podManagementPolicy: OrderedReady | Parallel
  selector:
    matchLabels:
      app: <label>
  template: ...
  volumeClaimTemplates:              # PVC per pod
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: <size>
```

**Lưu ý quan trọng:**
- Cần headless Service (clusterIP: None)
- Pod name: `<sts-name>-<ordinal>` (web-0, web-1, web-2)
- DNS: `<pod-name>.<service-name>.<namespace>.svc.cluster.local`
- PVC **không bị xóa** khi delete StatefulSet hoặc scale down

### DaemonSet
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: <name>
spec:
  selector:
    matchLabels:
      app: <label>
  updateStrategy:
    type: RollingUpdate | OnDelete
  template: ...
```

**Node selection:**
```yaml
spec:
  template:
    spec:
      nodeSelector:
        role: monitoring    # Chỉ chạy trên node có label này
      tolerations:          # Cho phép chạy trên tainted nodes
        - key: node-role.kubernetes.io/control-plane
          effect: NoSchedule
```

### Job
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: <name>
spec:
  completions: 1           # Tổng số lần cần hoàn thành
  parallelism: 1           # Số pod chạy song song
  backoffLimit: 6           # Retry limit
  activeDeadlineSeconds: 300 # Timeout
  ttlSecondsAfterFinished: 100  # Auto cleanup
  template:
    spec:
      restartPolicy: OnFailure | Never
      containers: ...
```

### CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: <name>
spec:
  schedule: "*/5 * * * *"
  concurrencyPolicy: Allow | Forbid | Replace
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  startingDeadlineSeconds: 200
  suspend: false
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers: ...
```

---

## Decision Framework: Chọn Workload Resource

```
                    Workload cần chạy liên tục?
                    ┌───────┴───────┐
                   YES              NO
                    │                │
              Cần stable           Job hay CronJob?
              identity/storage?    ┌───────┴───────┐
              ┌─────┴─────┐      One-shot      Scheduled
             YES          NO        │              │
              │            │       Job          CronJob
        StatefulSet    Chạy trên
                       mỗi node?
                    ┌────┴────┐
                   YES        NO
                    │          │
               DaemonSet  Deployment
```

### Chi tiết Decision Criteria

| Câu hỏi | Nếu YES | Nếu NO |
|----------|---------|--------|
| App cần chạy 24/7? | Deployment/StatefulSet/DaemonSet | Job/CronJob |
| App cần stable network identity (pod-0, pod-1)? | StatefulSet | Deployment |
| App cần persistent storage per pod? | StatefulSet | Deployment |
| App cần chạy trên MỌI node? | DaemonSet | Deployment |
| Task chạy 1 lần rồi thôi? | Job | CronJob nếu lặp lại |
| Task chạy theo schedule? | CronJob | Job nếu 1 lần |
| App stateless, có thể scale ngang? | Deployment | Xem StatefulSet |

---

## Comparison Matrix

| Feature | Deployment | StatefulSet | DaemonSet | Job | CronJob |
|---------|-----------|-------------|-----------|-----|---------|
| **Replicas** | User-defined | User-defined | 1 per node | completions | Per schedule |
| **Pod identity** | Random hash | Ordinal (0,1,2) | Per node | Random | Random |
| **Pod ordering** | Parallel | Sequential* | Parallel | Parallel* | N/A |
| **Storage** | Shared PVC | PVC per pod | Host path | Temp | Temp |
| **Network** | ClusterIP svc | Headless svc | Host network opt | N/A | N/A |
| **Update** | RollingUpdate/Recreate | RollingUpdate/OnDelete | RollingUpdate/OnDelete | N/A | N/A |
| **Restart** | Always | Always | Always | OnFailure/Never | OnFailure/Never |
| **Scale** | kubectl scale | kubectl scale | Add/remove nodes | parallelism | N/A |
| **Self-healing** | ✅ | ✅ | ✅ | ✅ (retry) | ✅ |
| **Rollback** | ✅ | ✅ | ✅ | ❌ | ❌ |

*StatefulSet: tuần tự mặc định, có thể `Parallel`. Job: theo `parallelism` setting.

---

## Update Strategy Comparison

### Deployment Strategies

| Strategy | Downtime | Resource cost | Complexity | Best for |
|----------|----------|---------------|------------|----------|
| RollingUpdate (maxSurge=25%, maxUnavail=25%) | Zero | +25% temp | Low | Hầu hết apps |
| RollingUpdate (maxSurge=1, maxUnavail=0) | Zero | +1 pod temp | Low | Zero-risk update |
| RollingUpdate (maxSurge=0, maxUnavail=1) | Minimal | No extra | Low | Resource-tight |
| Recreate | YES | No extra | Lowest | Single-instance apps |

### maxSurge vs maxUnavailable Quick Guide

```
Ưu tiên availability (zero downtime):
  maxSurge: 1 (hoặc 25%)
  maxUnavailable: 0

Ưu tiên tốc độ update:
  maxSurge: 50%
  maxUnavailable: 50%

Ưu tiên tiết kiệm resource:
  maxSurge: 0
  maxUnavailable: 1
```

---

## Production Checklist cho Workload

### Deployment Checklist
- [ ] Resource requests/limits được set
- [ ] Readiness probe configured
- [ ] Liveness probe configured (cẩn thận timeout)
- [ ] Update strategy phù hợp
- [ ] PodDisruptionBudget nếu critical
- [ ] Image tag pinned (không dùng `:latest`)
- [ ] Security context (non-root, drop caps)
- [ ] Topology spread constraints nếu multi-AZ
- [ ] Anti-affinity nếu cần HA

### StatefulSet Checklist
- [ ] Headless service tạo trước
- [ ] Volume claim template đúng size
- [ ] Reclaim policy phù hợp (Retain cho production)
- [ ] Backup strategy cho data
- [ ] Ordered vs parallel pod management
- [ ] Pod anti-affinity cho HA

### Job/CronJob Checklist
- [ ] backoffLimit hợp lý
- [ ] activeDeadlineSeconds set (tránh job zombie)
- [ ] concurrencyPolicy cho CronJob
- [ ] History limits set
- [ ] startingDeadlineSeconds cho CronJob
- [ ] ttlSecondsAfterFinished nếu cần auto cleanup

---

## Debugging Quick Reference

### Pod không start
```bash
kubectl describe pod <name>           # Xem Events
kubectl get events --sort-by='.lastTimestamp'
```

### Pod CrashLoopBackOff
```bash
kubectl logs <pod> --previous         # Logs lần chạy trước
kubectl describe pod <pod>            # Exit code, reason
```

### Rollout bị kẹt
```bash
kubectl rollout status deployment/<name>
kubectl get rs                        # Xem ReplicaSet cũ/mới
kubectl rollout undo deployment/<name>  # Rollback ngay
```

### Job không complete
```bash
kubectl describe job <name>           # Xem conditions
kubectl get pods -l job-name=<name>   # Xem pods
kubectl logs <pod-of-job>             # Xem output
```

### StatefulSet pod stuck
```bash
kubectl get pvc                       # PVC có bound?
kubectl describe pod <sts-pod>        # Volume mount issue?
kubectl delete pod <name> --force --grace-period=0  # Last resort
```

