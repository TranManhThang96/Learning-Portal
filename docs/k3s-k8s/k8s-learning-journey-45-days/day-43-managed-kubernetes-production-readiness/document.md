# Day 43 Document: Production Readiness Checklist

## Responsibility matrix

| Area | K3s self-managed | EKS/GKE/AKS |
|---|---|---|
| Control plane HA | Team | Provider |
| `etcd` backup | Team | Provider-managed |
| Node OS patching | Team | Team/provider tooling |
| Node pool sizing | Team | Team |
| CNI config | Team | Team/provider add-on |
| CSI/storage | Team | Team/provider add-on |
| Workload security | Team | Team |
| App backup | Team | Team |
| Observability | Team | Team |
| Cost control | Team | Team |

## Workload checklist

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: logistics
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: app
        image: registry.example.com/api@sha256:...
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        startupProbe:
          httpGet:
            path: /health
            port: 8080
          failureThreshold: 30
          periodSeconds: 2
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            memory: 256Mi
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
```

Nếu demo bằng NGINX, dùng image non-root như `nginxinc/nginx-unprivileged:1.25-alpine` và port `8080`. `nginx:1.25` mặc định chạy theo giả định root/port 80, nên thêm `runAsNonRoot: true` trực tiếp vào image đó có thể làm Pod fail.

## PDB mẫu

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: api
```

Với `replicas: 2`, `minAvailable: 2` sẽ chặn voluntary disruption hoàn toàn. Cần cân bằng availability và khả năng drain/upgrade.

## HPA mẫu

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
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

HPA cần `resources.requests.cpu` để CPU utilization có ý nghĩa.

## Topology spread mẫu

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app.kubernetes.io/name: api
- maxSkew: 1
  topologyKey: kubernetes.io/hostname
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app.kubernetes.io/name: api
```

`ScheduleAnyway` giảm rủi ro Pod Pending khi cluster thiếu zone/node tạm thời. App critical có thể dùng `DoNotSchedule` nếu availability domain là yêu cầu cứng và capacity đảm bảo.

## Node pool design worksheet

| Pool | Taint | Labels | Min/Max | Workload | Notes |
|---|---|---|---:|---|---|
| system | `dedicated=system:NoSchedule` | `nodepool=system` | 2/5 | CoreDNS, ingress, controllers | On-demand |
| general | none | `nodepool=general` | 3/30 | APIs | Autoscale |
| workers-spot | `lifecycle=spot:NoSchedule` | `nodepool=workers,lifecycle=spot` | 0/50 | Async workers | Interruption-safe |
| memory | `workload=memory:NoSchedule` | `nodepool=memory` | 1/10 | Redis/JVM | Bigger RAM |

## Workload identity notes

| Provider | Kubernetes object cần chú ý | Cloud object cần map |
|---|---|---|
| EKS | `ServiceAccount` annotation hoặc EKS Pod Identity association | IAM role với policy least privilege |
| GKE | Kubernetes ServiceAccount | Google Service Account + IAM binding |
| AKS | `ServiceAccount` annotations/labels theo Workload ID | Managed Identity hoặc app registration federated credential |

Checklist:

- [ ] Không commit static cloud access key vào Git.
- [ ] Mỗi app có ServiceAccount riêng nếu quyền cloud khác nhau.
- [ ] IAM policy giới hạn đúng resource ARN/name/project.
- [ ] Runbook có cách debug token audience/issuer và permission denied.

## Upgrade checklist

- [ ] Xác định current và target Kubernetes version.
- [ ] Kiểm tra API deprecation bằng manifest scan.
- [ ] Kiểm tra version compatibility của CNI, CSI, ingress, cert-manager, ArgoCD, operators.
- [ ] Upgrade staging trước.
- [ ] Chạy smoke test và load test tối thiểu.
- [ ] Kiểm tra PDB có cho phép drain không.
- [ ] Upgrade control plane.
- [ ] Upgrade node pool từng nhóm.
- [ ] Theo dõi node readiness, Pod disruption, latency/error.
- [ ] Có rollback/mitigation plan.

## Debug commands

```bash
kubectl get nodes -o wide
kubectl describe node <node>
kubectl get pods -A --field-selector=status.phase=Pending
kubectl get events -A --sort-by=.lastTimestamp
kubectl get pdb -A
kubectl get hpa -A
kubectl get storageclass
kubectl get pvc -A
kubectl get svc,ingress -A
kubectl top nodes
kubectl top pods -A
```

## Production readiness scorecard

| Category | Must-have |
|---|---|
| Release | GitOps, rollback, image immutability |
| Availability | replicas, PDB, topology spread, probes |
| Capacity | requests, HPA, node autoscaling, quota |
| Security | RBAC, Pod Security, NetworkPolicy, workload identity |
| Observability | logs, metrics, traces, alerts |
| Data | backup, restore drill, migration strategy |
| Operations | runbooks, upgrade plan, incident ownership |
| Cost | labels/tags, right-sizing, spot strategy |
