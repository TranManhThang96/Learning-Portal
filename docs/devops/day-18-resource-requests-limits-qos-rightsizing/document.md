# Day 18: Document — Resource Management Reference

---

## 1. Resource Sizing Reference theo Language/Framework

| Language/Framework | CPU Request | CPU Limit | Memory Request | Memory Limit | Ghi chú |
|-------------------|-------------|-----------|----------------|--------------|---------|
| **NGINX** (static) | 10-50m | 100-200m | 32-64Mi | 64-128Mi | Rất lightweight |
| **Node.js** (API) | 100-250m | 500m-1 | 128-256Mi | 256-512Mi | Set `--max-old-space-size` |
| **Go** (API) | 50-200m | 200m-1 | 32-128Mi | 64-256Mi | Set `GOMAXPROCS` |
| **Java/Spring** (API) | 250-500m | 1-2 | 512Mi-1Gi | 1-2Gi | Set `-XX:MaxRAMPercentage=75` |
| **Python/Django** (API) | 100-250m | 500m-1 | 128-256Mi | 256-512Mi | Gunicorn workers × memory |
| **Redis** | 50-100m | 200-500m | Dataset size | Dataset + 50% | `maxmemory` config |
| **PostgreSQL** | 250-500m | 1-2 | 256Mi-1Gi | Shared buffers + work_mem | Guaranteed QoS recommended |
| **Kafka** (broker) | 500m-1 | 2-4 | 1-2Gi | 4-6Gi | JVM heap + page cache |
| **Elasticsearch** | 500m-1 | 2-4 | 2-4Gi | 4-8Gi | Heap = 50% memory limit |

---

## 2. QoS Class Decision Matrix

```
Bạn đang deploy workload gì?
│
├── Critical service (payment, auth, database)
│   └── → Guaranteed (requests = limits)
│       Lý do: evicted cuối cùng, predictable performance
│
├── Standard API/Worker
│   ├── Latency-sensitive? → Burstable (limits = 2-3× requests)
│   │   Lý do: burst khi cần, nhưng có cap
│   └── Throughput-oriented? → Burstable (limits = 3-5× requests)
│       Lý do: burst nhiều hơn cho batch processing
│
├── Batch Job / CronJob
│   └── → Burstable (requests = average, limits = peak hoặc không set CPU limit)
│       Lý do: burst toàn bộ khi chạy, giải phóng khi xong
│
└── Dev/Test
    └── → Burstable với limits thấp
        Lý do: tiết kiệm resources dev cluster
```

---

## 3. Right-sizing Methodology Checklist

### Phase 1: Baseline (Day 1-3)

- [ ] Deploy với generous limits (2-3× ước đoán)
- [ ] Enable metrics-server hoặc Prometheus
- [ ] Record baseline metrics: `kubectl top pod` mỗi giờ
- [ ] Identify peak hours

### Phase 2: Collect (Day 3-7)

- [ ] Thu thập CPU P50, P95, P99 usage
- [ ] Thu thập Memory P50, P95, P99 usage
- [ ] Thu thập throttling stats (`nr_throttled`)
- [ ] Kiểm tra OOMKilled events
- [ ] Record peak usage timing

### Phase 3: Analyze (Day 7)

- [ ] Requests = P95 CPU usage × 1.2 (20% buffer)
- [ ] Limits = Requests × 2 (burst headroom)
- [ ] Memory requests = P99 memory usage × 1.2
- [ ] Memory limits = Memory requests × 1.5
- [ ] Kiểm tra: tổng requests < 80% node capacity

### Phase 4: Apply & Monitor (Day 8-14)

- [ ] Apply new resource config
- [ ] Monitor throttling (should be < 5%)
- [ ] Monitor OOMKilled (should be 0)
- [ ] Monitor latency changes
- [ ] Adjust if needed

### Phase 5: Maintain (Ongoing)

- [ ] Review mỗi quý hoặc khi traffic pattern thay đổi
- [ ] Alert khi throttling > 10%
- [ ] Alert khi memory > 85% limit
- [ ] Update khi deploy major version changes

---

## 4. LimitRange / ResourceQuota Templates

### LimitRange cho Production Namespace

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: production-limits
spec:
  limits:
    - type: Container
      default:
        cpu: 200m
        memory: 256Mi
      defaultRequest:
        cpu: 100m
        memory: 128Mi
      max:
        cpu: "4"
        memory: 4Gi
      min:
        cpu: 10m
        memory: 16Mi
    - type: Pod
      max:
        cpu: "8"
        memory: 8Gi
    - type: PersistentVolumeClaim
      max:
        storage: 100Gi
      min:
        storage: 1Gi
```

### ResourceQuota cho Team Namespace

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
spec:
  hard:
    # Compute
    requests.cpu: "10"
    requests.memory: 20Gi
    limits.cpu: "20"
    limits.memory: 40Gi
    # Objects
    pods: "50"
    services: "20"
    configmaps: "50"
    secrets: "50"
    persistentvolumeclaims: "20"
    # Storage
    requests.storage: 200Gi
  scopes: []
```

---

## 5. Debug Commands Quick Reference

### CPU Throttling

```bash
# Kiểm tra throttling trong container
kubectl exec <pod> -- cat /sys/fs/cgroup/cpu.stat
# Key metrics:
# nr_periods: total CFS periods
# nr_throttled: throttled periods
# throttled_time: total throttle time (ns)

# Throttle ratio
# throttle_ratio = nr_throttled / nr_periods
# < 5%: acceptable
# 5-20%: warning, consider increasing limit
# > 20%: critical, latency significantly impacted

# PromQL (nếu có Prometheus)
# rate(container_cpu_cfs_throttled_periods_total[5m]) / rate(container_cpu_cfs_periods_total[5m])
```

### OOMKilled

```bash
# Kiểm tra pod bị OOMKilled
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'

# Xem chi tiết
kubectl describe pod <pod> | grep -A 10 "Last State"

# Tìm tất cả pods bị OOMKilled
kubectl get pods -A -o json | jq -r '.items[] | select(.status.containerStatuses[0].lastState.terminated.reason == "OOMKilled") | .metadata.namespace + "/" + .metadata.name'

# Xem events
kubectl get events -A --field-selector reason=OOMKilling --sort-by='.lastTimestamp'
```

### Resource Usage

```bash
# Pod usage
kubectl top pod -n <ns>
kubectl top pod -n <ns> --containers   # per-container
kubectl top pod -n <ns> --sort-by=cpu
kubectl top pod -n <ns> --sort-by=memory

# Node usage
kubectl top node

# Node allocated vs capacity
kubectl describe node <node> | grep -A 20 "Allocated resources"

# Tìm pods không set resources
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.spec.containers[] | .resources.requests == null or .resources.requests == {}) |
  "\(.metadata.namespace)/\(.metadata.name)"
'
```

### Quota & LimitRange

```bash
# Xem quota usage
kubectl describe resourcequota -n <ns>
kubectl get resourcequota -n <ns> -o yaml

# Xem LimitRange
kubectl describe limitrange -n <ns>

# Kiểm tra pod sẽ được gán resources gì
kubectl run test --image=nginx:1.25-alpine --dry-run=server -n <ns> -o yaml | grep -A 10 resources
```

---

## 6. Production Resource Configuration Templates

### API Server (latency-sensitive)

```yaml
resources:
  requests:
    cpu: 200m
    memory: 256Mi
  limits:
    cpu: "1"          # 5× request cho burst
    memory: 512Mi     # 2× request cho safety
```

### Background Worker

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

### Database (Guaranteed QoS)

```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 500m         # = request (Guaranteed)
    memory: 1Gi       # = request (Guaranteed)
```

### Batch Job

```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    # CPU: không set limit → burst tối đa
    memory: 1Gi       # Hard cap memory
```

### Init Container

```yaml
initContainers:
  - name: init
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 128Mi
```

