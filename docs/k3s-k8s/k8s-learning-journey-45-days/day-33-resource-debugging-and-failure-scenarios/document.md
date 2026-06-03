# Document - Day 33: Resource Debugging Reference

## First commands by symptom

| Symptom | First commands |
|---|---|
| `OOMKilled` | `kubectl describe pod <pod>`, `kubectl logs <pod> --previous`, `kubectl top pod <pod>` |
| `CrashLoopBackOff` | `kubectl describe pod <pod>`, `kubectl logs <pod> --previous`, `kubectl get events --sort-by=.lastTimestamp` |
| `Pending` | `kubectl describe pod <pod>`, `kubectl describe node <node>`, `kubectl get events` |
| CPU latency spike | `kubectl top pod`, inspect CPU limits, check throttling metrics |
| `Evicted` | `kubectl describe pod <pod>`, `kubectl describe node <node>`, `kubectl top node`, check disk/memory pressure |
| Disk pressure | `kubectl describe node <node>`, inspect ephemeral storage usage, logs volume |

## Resource fields quick reference

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
    ephemeral-storage: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
    ephemeral-storage: 1Gi
```

Meaning:

- `cpu: 100m` = 0.1 CPU core.
- `memory: 128Mi` = binary mebibytes.
- CPU request influences scheduling and CPU share.
- CPU limit creates runtime quota and can cause throttling.
- Memory request influences scheduling.
- Memory limit can cause `OOMKilled`.
- Ephemeral storage covers writable layer, logs and `emptyDir` usage.

## Requests vs limits

| Field | Used by | Main effect | Failure mode |
|---|---|---|---|
| CPU request | scheduler, kubelet CPU shares | Scheduling and relative CPU share | Pod `Pending` if no node has capacity |
| CPU limit | runtime/cgroup | Max CPU quota | Throttling, latency increase |
| Memory request | scheduler | Scheduling and QoS | Pod `Pending` if no node has capacity |
| Memory limit | runtime/cgroup/kernel | Max memory usage | `OOMKilled`, exit code 137 |
| Ephemeral-storage request | scheduler | Scheduling disk reservation | Pod `Pending` if insufficient |
| Ephemeral-storage limit | kubelet | Max local writable storage | Eviction or write failures |

## QoS class matrix

| QoS | Example | Eviction priority |
|---|---|---|
| `Guaranteed` | Every container has CPU and memory request equal to limit | Last |
| `Burstable` | At least one request/limit exists, but not Guaranteed | Middle |
| `BestEffort` | No CPU/memory requests or limits | First |

Check QoS:

```bash
kubectl get pod <pod> -o jsonpath='{.status.qosClass}'
```

## Pod status interpretation

| Status/reason | What it really means | Not enough to conclude |
|---|---|---|
| `Pending` | Pod not scheduled or dependency not ready | Not necessarily image problem |
| `CrashLoopBackOff` | Container exits repeatedly | Not necessarily Kubernetes problem |
| `OOMKilled` | Process killed due to memory pressure/limit | Not necessarily leak; could be sizing/runtime config |
| `Evicted` | kubelet removed Pod to protect node | Not necessarily app crash |
| `Running` not Ready | Process exists but readiness condition fails | Not necessarily healthy |

CrashLoopBackOff can be resource-related, but often is not. Always separate:

- `Reason: OOMKilled` or exit code `137`: memory path.
- Non-zero app exit code with app logs: command/config/code path.
- `Liveness probe failed`: kubelet killed a process that may still be starting.

## Event messages to recognize

| Event fragment | Likely cause |
|---|---|
| `Insufficient cpu` | CPU requests cannot fit on any node |
| `Insufficient memory` | Memory requests cannot fit on any node |
| `had untolerated taint` | Missing toleration |
| `didn't match Pod's node affinity/selector` | Node selector/affinity mismatch |
| `Back-off restarting failed container` | Process exits repeatedly |
| `Liveness probe failed` | Probe killed container |
| `Readiness probe failed` | Pod removed from endpoints |
| `The node was low on resource` | Eviction due to node pressure |
| `exceeded its local ephemeral storage limit` | Pod used too much local storage |

## Debug order: `OOMKilled`

```bash
kubectl get pod <pod> -o wide
kubectl describe pod <pod>
kubectl logs <pod> --previous
kubectl top pod <pod>
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}'
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.exitCode}'
```

Questions:

- Which container was killed?
- Did memory usage climb over time or spike suddenly?
- Was there a rollout, config change or traffic spike?
- Does runtime heap limit leave headroom below container limit?
- Is liveness probe masking slow startup or recovery?

## Debug order: `Pending`

```bash
kubectl describe pod <pod>
kubectl get nodes
kubectl describe node <node>
kubectl get quota,limitrange -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Questions:

- Are requests larger than any node allocatable?
- Is namespace quota exhausted?
- Are taints, selectors, affinity or topology constraints blocking scheduling?
- Is a PVC waiting for first consumer or storage provisioning?

## Debug order: `CrashLoopBackOff` non-resource

```bash
kubectl get pod <pod> -o wide
kubectl describe pod <pod>
kubectl logs <pod> --previous
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}'
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.exitCode}'
```

Questions:

- Did the process exit by itself, or did kubelet kill it?
- Does `Last State` say `OOMKilled`, `Error`, or liveness probe failure?
- Do previous logs show missing config, failed migration, panic or bad command?
- Did a recent ConfigMap/Secret/image change happen?

## CPU throttling signals

Kubernetes CLI:

```bash
kubectl top pod -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl get pod <pod> -n <namespace> -o yaml
```

Prometheus/cAdvisor examples:

```promql
sum by (pod, container) (
  rate(container_cpu_usage_seconds_total{namespace="<namespace>", container!="POD", container!=""}[5m])
)
```

```promql
sum by (pod, container) (
  rate(container_cpu_cfs_throttled_periods_total{namespace="<namespace>", container!="POD", container!=""}[5m])
)
/
sum by (pod, container) (
  rate(container_cpu_cfs_periods_total{namespace="<namespace>", container!="POD", container!=""}[5m])
)
```

Interpretation:

- CPU usage near limit plus throttling ratio rising means quota is constraining runtime.
- `kubectl top` alone does not prove throttling; it only shows current CPU/memory usage.
- Latency spike without restart often points to CPU, downstream dependency or lock contention.
- HPA based on CPU may need request tuning before it scales predictably.

## Memory sizing worksheet

| Input | Value |
|---|---|
| Steady-state working set | |
| p95 memory during normal traffic | |
| p99 memory during peak traffic | |
| Startup peak | |
| Runtime heap limit | |
| Native memory/headroom | |
| Proposed request | |
| Proposed limit | |
| Alert threshold | |

Rule of thumb:

- Request should reflect capacity you need reserved.
- Limit should protect the node but leave enough headroom for real spikes.
- Runtime heap should be lower than container limit.

## CPU sizing worksheet

| Input | Value |
|---|---|
| Idle CPU | |
| p95 CPU normal traffic | |
| p99 CPU peak traffic | |
| Single-request CPU cost | |
| Desired max concurrency per Pod | |
| Proposed request | |
| Proposed limit or no limit | |
| HPA target | |

Questions:

- Is the service latency-sensitive?
- Is CPU usage bursty?
- Does the runtime use multiple threads?
- Would adding replicas reduce p99 latency?
- Is CPU throttling already visible?

## Node pressure checklist

```bash
kubectl get nodes
kubectl describe node <node>
kubectl top node
kubectl get pods -A -o wide --field-selector spec.nodeName=<node>
kubectl get events -A --sort-by=.lastTimestamp
```

Check node conditions:

- `MemoryPressure`
- `DiskPressure`
- `PIDPressure`
- `Ready`

Common causes:

- Too many BestEffort/Burstable Pods using memory above requests.
- Log volume too high.
- Image garbage collection cannot keep up.
- Batch jobs write large temporary files.
- Node pool too small for workload shape.

## Lab cleanup

```bash
kubectl delete namespace day33
```
