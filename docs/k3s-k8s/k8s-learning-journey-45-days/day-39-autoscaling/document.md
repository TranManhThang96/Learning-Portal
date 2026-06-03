# Document - Day 39: Autoscaling Reference

## Autoscaler map

```text
HPA
  changes replicas
  needs metrics and scale target

VPA
  changes/recommends requests
  needs usage history

Cluster Autoscaler
  changes node count
  reacts to unschedulable Pods

KEDA
  event-driven scaling
  often creates/manages HPA
```

## First commands

```bash
kubectl get hpa -A
kubectl describe hpa <name> -n <namespace>
kubectl top pods -n <namespace>
kubectl top nodes
kubectl get deploy <name> -n <namespace> -o yaml
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Check metrics-server:

```bash
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl get pods -n kube-system | findstr metrics
kubectl top nodes
```

Nếu `v1beta1.metrics.k8s.io` thiếu hoặc unavailable, HPA CPU/memory thường sẽ hiển thị metric `<unknown>`. Trong lab dùng một lần, chỉ cài metrics-server theo hướng dẫn riêng của cluster. Với shared hoặc production cluster, phải xác minh owner của metrics pipeline, TLS flags, scrape permissions và alerting trước.

Linux/macOS:

```bash
kubectl get pods -n kube-system | grep metrics
```

## HPA CPU formula intuition

```text
utilization = current CPU usage / requested CPU

desiredReplicas ~= currentReplicas * currentUtilization / targetUtilization
```

Example:

```text
current replicas: 2
CPU request per Pod: 100m
current CPU per Pod: 200m
current utilization: 200%
target utilization: 70%
desired replicas ~= 2 * 200 / 70 = 5.7 -> 6
```

## HPA v2 CPU example

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## HPA behavior example

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Percent
      value: 100
      periodSeconds: 60
    - type: Pods
      value: 4
      periodSeconds: 60
    selectPolicy: Max
  scaleDown:
    stabilizationWindowSeconds: 300
    policies:
    - type: Percent
      value: 50
      periodSeconds: 60
    selectPolicy: Max
```

## HPA external metric sketch

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 1
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: queue_messages_ready
      target:
        type: AverageValue
        averageValue: "100"
```

Requires external metrics adapter.

## VPA example

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  updatePolicy:
    updateMode: "Off"
```

Use `Off` for recommendations first:

```bash
kubectl describe vpa api -n <namespace>
```

## KEDA ScaledObject example

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-worker
spec:
  scaleTargetRef:
    name: worker
  minReplicaCount: 0
  maxReplicaCount: 30
  pollingInterval: 30
  cooldownPeriod: 300
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka.kafka.svc.cluster.local:9092
      consumerGroup: order-worker
      topic: orders
      lagThreshold: "100"
```

## Metric selection guide

| Workload | Good metric | Avoid relying only on |
|---|---|---|
| CPU-bound API | CPU utilization, RPS | Memory |
| I/O-bound API | RPS, in-flight, latency | CPU |
| Queue worker | Queue length, lag, message age | CPU |
| Kafka consumer | Consumer lag per partition/group | Pod count |
| Batch jobs | Queue depth, schedule, job backlog | HPA CPU |
| Stateful DB | Domain-specific operator metrics | Generic HPA |

## Debug matrix

| Symptom | Likely cause | Commands |
|---|---|---|
| HPA shows `<unknown>` | Metrics missing | `kubectl describe hpa`, `kubectl top pods` |
| HPA not scaling | Target not reached, min/max, behavior window | `kubectl describe hpa` |
| HPA scales too much | Request too low, target too low | inspect requests and CPU usage |
| HPA scales too slowly | Metric delay, behavior policy, readiness delay | events, HPA behavior |
| Pods Pending after scale | Node capacity, taints, affinity, quota | `describe pod`, events |
| Pending scenario khó đoán | HPA vẫn điều khiển cùng Deployment | dùng Deployment riêng không có HPA |
| Scale-down breaks requests | Bad termination/probes/PDB | logs, PDB, rollout events |
| KEDA scale wrong | Trigger/auth/query wrong | `describe scaledobject`, operator logs |

## Production autoscaling checklist

- [ ] Workload has meaningful CPU/memory requests.
- [ ] HPA uses `autoscaling/v2`.
- [ ] `minReplicas` preserves baseline availability.
- [ ] `maxReplicas` respects downstream limits.
- [ ] Scale behavior is configured for production traffic.
- [ ] Metrics pipeline is monitored.
- [ ] PDB and graceful shutdown are configured.
- [ ] Node pool has headroom or Cluster Autoscaler configured.
- [ ] Load test validates scale-up and scale-down.
- [ ] Alerts exist for HPA maxed out, metric unknown and Pending Pods.
- [ ] KEDA triggers have authentication and failure runbook.
- [ ] VPA recommendations are reviewed before auto mode.

## Capacity worksheet

```text
Service:
Traffic pattern:
Metric chosen:
Target value:
Baseline replicas:
Max replicas:
CPU request:
Memory request:
Pod startup time:
Image pull time:
Downstream DB connection per Pod:
Downstream max safe connections:
Node pool headroom:
Cluster Autoscaler max nodes:
Scale-up SLO:
Scale-down policy:
Rollback/disable plan:
```

## Useful Prometheus signals

HPA saturation:

```promql
kube_horizontalpodautoscaler_status_desired_replicas
/
kube_horizontalpodautoscaler_spec_max_replicas
```

Pending Pods:

```promql
kube_pod_status_phase{phase="Pending"}
```

CPU throttling:

```promql
rate(container_cpu_cfs_throttled_periods_total{container!="",container!="POD"}[5m])
/
rate(container_cpu_cfs_periods_total{container!="",container!="POD"}[5m])
```

Deployment readiness:

```promql
kube_deployment_status_replicas_available
/
kube_deployment_spec_replicas
```
