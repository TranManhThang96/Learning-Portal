# Day 22: Document — Kubernetes Troubleshooting Methodology

## 1. Debug Decision Tree

```
Pod có vấn đề?
│
├── Status: Pending
│   ├── Events: "Insufficient cpu/memory"
│   │   └── Fix: giảm requests hoặc add nodes
│   ├── Events: "node(s) had taint"
│   │   └── Fix: thêm toleration hoặc remove taint
│   ├── Events: "persistentvolumeclaim not found"
│   │   └── Fix: tạo PVC/PV hoặc check StorageClass
│   └── Events: "node(s) didn't match selector"
│       └── Fix: sửa nodeSelector hoặc label nodes
│
├── Status: ImagePullBackOff / ErrImagePull
│   ├── "manifest unknown" / "tag not found"
│   │   └── Fix: sửa image name/tag
│   ├── "unauthorized" / "access denied"
│   │   └── Fix: tạo imagePullSecret
│   ├── "timeout" / "connection refused"
│   │   └── Fix: check network, proxy, firewall
│   └── "rate limit exceeded"
│       └── Fix: authenticate Docker Hub hoặc dùng mirror
│
├── Status: CrashLoopBackOff
│   ├── Exit Code 1 (application error)
│   │   └── Check: kubectl logs --previous → fix app config/code
│   ├── Exit Code 137 (SIGKILL / OOMKilled)
│   │   └── Check: kubectl describe → Reason: OOMKilled → tăng memory limit
│   ├── Exit Code 139 (Segfault)
│   │   └── Check: app binary compatibility, corrupt image
│   ├── Exit Code 143 (SIGTERM)
│   │   └── Check: graceful shutdown handling, preStop hook
│   └── No logs available
│       └── Check: entrypoint/command sai, missing binary
│
├── Status: Running nhưng không Ready
│   ├── Readiness probe failing
│   │   └── Check: probe path/port, app startup time
│   ├── "0/1 containers ready"
│   │   └── Check: kubectl describe → probe config
│   └── initialDelaySeconds quá ngắn
│       └── Fix: tăng initialDelaySeconds
│
├── Status: Running + Ready nhưng traffic không work
│   ├── Service endpoints rỗng
│   │   └── Fix: label selector mismatch
│   ├── DNS không resolve
│   │   └── Check: CoreDNS, NetworkPolicy UDP/53
│   ├── Connection refused
│   │   └── Check: targetPort mapping, container port
│   └── Timeout
│       └── Check: NetworkPolicy, firewall, pod overloaded
│
├── Status: Terminating (stuck)
│   ├── Finalizer blocking
│   │   └── Remove finalizer (sau khi verify manual cleanup)
│   ├── Node unreachable
│   │   └── Force delete: --grace-period=0 --force
│   └── Volume unmount slow
│       └── Wait hoặc check CSI driver
│
└── Status: Unknown
    └── Node communication issue → kubectl describe node
```

---

## 2. kubectl Troubleshooting Cheat Sheet

### Xem trạng thái

```bash
# Tất cả pods, sorted by status
kubectl get pods -A --sort-by=.status.phase

# Pods không Running
kubectl get pods -A --field-selector=status.phase!=Running

# Pods với restart count cao
kubectl get pods -A -o custom-columns=\
NAME:.metadata.name,\
NS:.metadata.namespace,\
RESTARTS:.status.containerStatuses[0].restartCount,\
STATUS:.status.phase \
--sort-by=.status.containerStatuses[0].restartCount

# Node conditions
kubectl get nodes -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.conditions[-1].type,\
READY:.status.conditions[-1].status

# Resource usage
kubectl top pods -A --sort-by=cpu
kubectl top pods -A --sort-by=memory
kubectl top nodes
```

### Debug Pod

```bash
# Describe (events + status)
kubectl describe pod <pod> -n <ns>

# Logs hiện tại
kubectl logs <pod> -n <ns> [-c <container>]

# Logs lần restart trước
kubectl logs <pod> -n <ns> --previous

# Logs nhiều pods cùng label
kubectl logs -l app=<name> -n <ns> --all-containers

# Logs theo thời gian
kubectl logs <pod> --since=1h
kubectl logs <pod> --since-time="2024-01-15T10:00:00Z"

# Tail logs
kubectl logs <pod> -f --tail=100

# Exec vào container
kubectl exec -it <pod> -n <ns> [-c <container>] -- /bin/sh

# Debug với ephemeral container (khi container không có shell)
kubectl debug <pod> -n <ns> -it --image=busybox --target=<container>

# Debug node
kubectl debug node/<node> -it --image=ubuntu
```

### Debug Network

```bash
# DNS test
kubectl exec <pod> -- nslookup <service>
kubectl exec <pod> -- nslookup <service>.<ns>.svc.cluster.local

# HTTP test
kubectl exec <pod> -- curl -v http://<service>:<port>
kubectl exec <pod> -- wget -qO- http://<service>:<port>

# Check resolv.conf
kubectl exec <pod> -- cat /etc/resolv.conf

# Check endpoints
kubectl get endpoints <service> -n <ns>
kubectl get endpointslices -l kubernetes.io/service-name=<service> -n <ns>

# Port forward (debug từ local)
kubectl port-forward pod/<pod> 8080:80 -n <ns>
kubectl port-forward svc/<service> 8080:80 -n <ns>
```

### Debug Events

```bash
# Events mới nhất
kubectl get events -n <ns> --sort-by=.lastTimestamp

# Events cho object cụ thể
kubectl get events --field-selector involvedObject.name=<name> -n <ns>

# Events loại Warning
kubectl get events --field-selector type=Warning -n <ns>

# Events toàn cluster
kubectl get events -A --sort-by=.lastTimestamp | head -50

# Watch events real-time
kubectl get events -n <ns> -w
```

### Debug Resources

```bash
# Xem resource allocation trên node
kubectl describe node <node> | grep -A 15 "Allocated resources"

# Xem requests/limits của pods
kubectl get pods -n <ns> -o custom-columns=\
NAME:.metadata.name,\
CPU_REQ:.spec.containers[0].resources.requests.cpu,\
CPU_LIM:.spec.containers[0].resources.limits.cpu,\
MEM_REQ:.spec.containers[0].resources.requests.memory,\
MEM_LIM:.spec.containers[0].resources.limits.memory

# Check QoS class
kubectl get pods -n <ns> -o custom-columns=\
NAME:.metadata.name,\
QOS:.status.qosClass

# Check CPU throttling (trong container)
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu/cpu.stat
# nr_throttled > 0 = bị throttle
```

---

## 3. Common Error Messages & Meanings

| Error Message | Loại | Nguyên nhân | Fix nhanh |
|---------------|------|-------------|-----------|
| `ImagePullBackOff` | Image | Image không tồn tại hoặc không auth | Check image name, imagePullSecret |
| `ErrImagePull` | Image | Lần pull đầu tiên fail | Check image + network |
| `CrashLoopBackOff` | Container | Container crash liên tục | `kubectl logs --previous` |
| `OOMKilled` | Memory | Vượt memory limit | Tăng limit hoặc fix memory leak |
| `Evicted` | Node | Node disk/memory pressure | Clean up node, add resources |
| `FailedScheduling` | Scheduler | Không có node phù hợp | Check resources, taints, selectors |
| `FailedMount` | Volume | Volume mount fail | Check PVC, CSI driver |
| `FailedAttachVolume` | Volume | Volume attach fail | Check cloud provider, volume zone |
| `Unhealthy` | Probe | Liveness/readiness probe fail | Check probe config, app health |
| `FailedCreate` | Controller | Không tạo được pod | Check admission, quota, RBAC |
| `DeadlineExceeded` | Job | Job vượt deadline | Tăng activeDeadlineSeconds |
| `BackoffLimitExceeded` | Job | Job fail quá số lần retry | Check job logs, fix command |
| `NetworkNotReady` | Network | CNI chưa ready | Check CNI plugin |

### Exit Codes Reference

| Exit Code | Signal | Ý nghĩa |
|-----------|--------|---------|
| 0 | - | Success (container exit bình thường) |
| 1 | - | General application error |
| 2 | - | Misuse of shell command |
| 126 | - | Permission denied (command not executable) |
| 127 | - | Command not found |
| 128+N | Signal N | Killed by signal N |
| 130 | SIGINT (2) | Ctrl+C |
| 137 | SIGKILL (9) | OOMKilled hoặc force killed |
| 139 | SIGSEGV (11) | Segmentation fault |
| 143 | SIGTERM (15) | Graceful termination |

---

## 4. Incident Note Template

```markdown
# Incident Note: [Tên incident ngắn gọn]

## Metadata
- **Date**: YYYY-MM-DD HH:MM (timezone)
- **Severity**: P1 / P2 / P3 / P4
- **Duration**: X minutes/hours
- **Detected by**: Alert name / User report / Monitoring
- **Resolved by**: [Tên người fix]

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired: [mô tả alert] |
| HH:MM | On-call acknowledged |
| HH:MM | Initial investigation started |
| HH:MM | Hypothesis: [giả thuyết] |
| HH:MM | Root cause identified: [nguyên nhân] |
| HH:MM | Mitigation applied: [action] |
| HH:MM | Verified: service restored |
| HH:MM | Incident closed |

## Impact
- **User-facing**: Có/Không
- **Affected services**: [list services]
- **Error rate**: X% (from Y% baseline)
- **Requests affected**: ~N requests
- **Revenue impact**: $X (nếu applicable)

## Root Cause
[Mô tả chi tiết nguyên nhân gốc]

## Debug Steps
```bash
# Command 1: [mô tả]
kubectl describe pod <name>
# Output tóm tắt: ...

# Command 2: [mô tả]
kubectl logs <name> --previous
# Output tóm tắt: ...
```

## Fix Applied
```bash
# [Mô tả fix]
kubectl patch deployment <name> ...
```

## 5 Whys (nếu P1/P2)
1. Why? → [answer]
2. Why? → [answer]
3. Why? → [answer]
4. Why? → [answer]
5. Why? → [answer]

## Action Items
| # | Action | Owner | Priority | Due Date | Status |
|---|--------|-------|----------|----------|--------|
| 1 | [action] | [name] | P0/P1/P2 | YYYY-MM-DD | Open |
| 2 | [action] | [name] | P0/P1/P2 | YYYY-MM-DD | Open |

## Lessons Learned
- [Bài học 1]
- [Bài học 2]
```

---

## 5. Production Debugging Checklist

### Khi nhận alert

- [ ] **Acknowledge** alert trong PagerDuty/OpsGenie
- [ ] **Assess scope**: 1 pod? 1 service? 1 node? Cluster-wide?
- [ ] **Check recent changes**: `kubectl rollout history`, Git commits, deployment pipeline
- [ ] **Decide**: Mitigation ngay hay investigate trước?

### Thu thập evidence

- [ ] `kubectl get pods -n <ns>` — tổng quan trạng thái
- [ ] `kubectl describe pod <pod>` — events, conditions
- [ ] `kubectl logs <pod> [--previous]` — application logs
- [ ] `kubectl get events -n <ns> --sort-by=.lastTimestamp` — timeline events
- [ ] `kubectl top pod -n <ns>` — resource usage hiện tại
- [ ] `kubectl get endpoints <svc>` — service routing check
- [ ] Screenshot dashboard/monitoring nếu có

### Common quick checks

- [ ] Image name/tag đúng?
- [ ] ConfigMap/Secret tồn tại?
- [ ] Resource requests/limits hợp lý?
- [ ] Liveness/readiness probe config đúng?
- [ ] Service selector match pod labels?
- [ ] NetworkPolicy allow required traffic?
- [ ] PVC bound?
- [ ] Node có đủ resources?

### Sau khi fix

- [ ] Verify pods Running + Ready
- [ ] Verify service endpoints populated
- [ ] Verify traffic flowing (curl/wget test)
- [ ] Check error rate trở về baseline
- [ ] **Viết incident note** (bắt buộc cho P1/P2)
- [ ] **Tạo action items** để prevent recurrence
- [ ] **Notify stakeholders** về resolution

---

## 6. Debug Tools Comparison

| Tool | Khi nào dùng | Require | Impact |
|------|-------------|---------|--------|
| `kubectl get` | Overview nhanh | Reader RBAC | Không |
| `kubectl describe` | Chi tiết events + status | Reader RBAC | Không |
| `kubectl logs` | Application logs | Pod reader RBAC | Thấp |
| `kubectl events` | Cluster event timeline | Event reader | Không |
| `kubectl exec` | Interactive debug trong container | Pod exec RBAC | Thấp |
| `kubectl debug` (ephemeral) | Debug distroless containers | Pod debug RBAC | Trung bình |
| `kubectl debug` (node) | Debug node-level issues | Node debug RBAC | Cao |
| `kubectl top` | Resource usage real-time | metrics-server | Không |
| `kubectl port-forward` | Test từ local machine | Port-forward RBAC | Trung bình |
| `kubectl cp` | Copy files từ/vào container | Pod exec RBAC | Trung bình |
| `kubectl auth can-i` | Check RBAC permissions | Self | Không |

---

## 7. Useful One-liners

```bash
# Pods đang không healthy
kubectl get pods -A | grep -v "Running\|Completed"

# Pods có restart count > 0
kubectl get pods -A -o json | jq -r '.items[] | select(.status.containerStatuses[0].restartCount > 0) | "\(.metadata.namespace)/\(.metadata.name) restarts=\(.status.containerStatuses[0].restartCount)"'

# Services không có endpoints
kubectl get endpoints -A -o json | jq -r '.items[] | select(.subsets == null or .subsets == []) | "\(.metadata.namespace)/\(.metadata.name)"'

# Nodes với conditions
kubectl get nodes -o json | jq -r '.items[] | "\(.metadata.name): \([.status.conditions[] | select(.status=="True") | .type] | join(", "))"'

# Events Warning trong 1 giờ qua
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | head -20

# Pod resource usage vs requests
kubectl top pods -A --no-headers | sort -k3 -rn | head -10

# Check all container images đang chạy
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}: {range .spec.containers[*]}{.image} {end}{"\n"}{end}'
```

