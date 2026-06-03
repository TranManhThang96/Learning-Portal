# Document - Day 40: Advanced Scheduling Reference

## Scheduling constraint map

```text
Choose nodes:
  nodeSelector
  nodeAffinity

Repel Pods from nodes:
  taints on nodes
  tolerations on Pods

Place Pods relative to other Pods:
  podAffinity
  podAntiAffinity

Balance across failure domains:
  topologySpreadConstraints

Prefer important Pods:
  PriorityClass / preemption
```

## First debug commands

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl get nodes --show-labels
kubectl describe node <node>
kubectl get pod <pod> -n <namespace> -o yaml
kubectl get pods -n <namespace> -o wide
```

## nodeSelector

```yaml
spec:
  nodeSelector:
    nodepool: general
    disk: ssd
```

Label a node:

```bash
kubectl label node <node> nodepool=general disk=ssd
```

Remove label:

```bash
kubectl label node <node> disk-
```

## Node affinity

Required:

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: nodepool
          operator: In
          values:
          - general
```

Preferred:

```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 80
      preference:
        matchExpressions:
        - key: disk
          operator: In
          values:
          - ssd
```

Operators:

| Operator | Meaning |
|---|---|
| `In` | Label value in list |
| `NotIn` | Label missing or value not in list |
| `Exists` | Label key exists |
| `DoesNotExist` | Label key missing |
| `Gt` | Numeric greater than |
| `Lt` | Numeric less than |

## Taints and tolerations

Add taint:

```bash
kubectl taint nodes <node> dedicated=platform:NoSchedule
```

Remove taint:

```bash
kubectl taint nodes <node> dedicated=platform:NoSchedule-
```

Toleration:

```yaml
tolerations:
- key: dedicated
  operator: Equal
  value: platform
  effect: NoSchedule
```

Exists toleration:

```yaml
tolerations:
- key: dedicated
  operator: Exists
  effect: NoSchedule
```

Effects:

| Effect | Scheduling impact |
|---|---|
| `NoSchedule` | New Pods without toleration cannot schedule |
| `PreferNoSchedule` | Scheduler tries to avoid |
| `NoExecute` | Existing Pods without toleration can be evicted |

## Dedicated node pool pattern

Node:

```bash
kubectl label node <node> nodepool=platform
kubectl taint node <node> dedicated=platform:NoSchedule
```

Pod:

```yaml
spec:
  nodeSelector:
    nodepool: platform
  tolerations:
  - key: dedicated
    operator: Equal
    value: platform
    effect: NoSchedule
```

Taint keeps other Pods out. Node selector pulls this Pod in.

Để taint lab deterministic, ép Pod test vào node đã taint bằng `nodeSelector` hoặc taint tất cả node đủ điều kiện trong lab. Nếu Pod vẫn có thể schedule sang node không bị taint, lab chưa chứng minh được case thiếu toleration.

## Pod anti-affinity

Preferred spread across nodes:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: api
        topologyKey: kubernetes.io/hostname
```

Required hard anti-affinity:

```yaml
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app: api
      topologyKey: kubernetes.io/hostname
```

Use required carefully; it can block rollout when there are fewer nodes than replicas.

## Pod affinity

```yaml
affinity:
  podAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 50
      podAffinityTerm:
        labelSelector:
          matchLabels:
            app: cache
        topologyKey: kubernetes.io/hostname
```

Use when locality matters. Avoid unnecessary coupling.

## Topology spread constraints

Spread across nodes:

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: api
```

Spread across zones:

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: api
```

Fields:

| Field | Meaning |
|---|---|
| `maxSkew` | Max difference across topology domains |
| `topologyKey` | Node label defining domain |
| `whenUnsatisfiable` | `DoNotSchedule` or `ScheduleAnyway` |
| `labelSelector` | Pods counted for spreading |
| `minDomains` | Minimum eligible domains, useful for zones |

## PriorityClass example

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: platform-critical
value: 100000
globalDefault: false
description: "Critical platform workloads"
```

Pod:

```yaml
spec:
  priorityClassName: platform-critical
```

Use sparingly. Preemption can evict other workloads.

## Common scheduler event messages

| Event fragment | Likely cause |
|---|---|
| `Insufficient cpu` | Requests cannot fit |
| `Insufficient memory` | Memory requests cannot fit |
| `had untolerated taint` | Missing toleration |
| `didn't match Pod's node affinity/selector` | Label/affinity mismatch |
| `didn't match pod affinity/anti-affinity` | Required Pod relation impossible |
| `didn't match pod topology spread constraints` | Spread impossible |
| `preemption: ... is not helpful` | Even evicting lower priority Pods would not fit |

## Managed node pool worksheet

```text
Node pool name:
Instance type:
Zones:
Min/max nodes:
Labels:
Taints:
Workloads allowed:
Workloads forbidden:
Storage topology:
Spot/on-demand:
Autoscaler enabled:
Drain/upgrade strategy:
Cost risk:
Failure domain risk:
```

## Production placement checklist

- [ ] Node labels and taints are documented.
- [ ] App charts expose nodeSelector, affinity, tolerations and topologySpread values.
- [ ] Dedicated node pool uses both taint and node affinity/selector.
- [ ] Required constraints are justified.
- [ ] Topology spread uses real topology labels.
- [ ] Replica count matches HA requirement and topology domains.
- [ ] PDB does not conflict with scheduling constraints.
- [ ] Cluster Autoscaler has node groups matching Pod constraints.
- [ ] Spot workloads tolerate interruption.
- [ ] GPU/high-memory nodes are tainted.
- [ ] Scheduler Pending events are part of runbook.

## Decision guide

| Need | Prefer |
|---|---|
| Simple node pool targeting | `nodeSelector` or required node affinity |
| Flexible node preference | preferred node affinity |
| Reserve nodes for special workloads | taint + toleration + node affinity |
| Avoid same app replicas on same node | topology spread or preferred anti-affinity |
| Hard HA across zones | topology spread `DoNotSchedule` with enough zones |
| Keep workload near dependency | preferred pod affinity |
| Protect critical workload scheduling | PriorityClass, with caution |
