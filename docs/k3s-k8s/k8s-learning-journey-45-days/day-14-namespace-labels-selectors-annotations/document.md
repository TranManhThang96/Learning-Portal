# Document - Day 14: Namespace, Labels, Selectors and Annotations Reference

## Scope reference

| Resource | Namespaced? | Notes |
|---|---|---|
| `Pod` | Yes | Workload runtime object |
| `Deployment` | Yes | Manages ReplicaSets/Pods |
| `Service` | Yes | Selects backend Pods in same namespace |
| `ConfigMap` | Yes | Config for Pods in namespace |
| `Secret` | Yes | Sensitive config in namespace |
| `Role` / `RoleBinding` | Yes | Namespace-scoped RBAC |
| `NetworkPolicy` | Yes | Applies to Pods in namespace |
| `Namespace` | No | Cluster-scoped object |
| `Node` | No | Cluster infrastructure |
| `ClusterRole` / `ClusterRoleBinding` | No | Cluster-scoped RBAC |
| `StorageClass` | No | Cluster storage capability |
| `PersistentVolume` | No | Cluster storage object |

Check from your cluster:

```bash
kubectl api-resources --namespaced=true
kubectl api-resources --namespaced=false
```

## Recommended label baseline

```yaml
metadata:
  labels:
    app.kubernetes.io/name: orders
    app.kubernetes.io/instance: orders-dev
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: commerce
    app.kubernetes.io/managed-by: kubectl
    environment: dev
    owner: platform
    tier: backend
```

## Namespace template

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: orders-dev
  labels:
    environment: dev
    owner: platform
    cost-center: learning
```

## Deployment selector template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  labels:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: orders
      app.kubernetes.io/component: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: orders
        app.kubernetes.io/component: api
        environment: dev
    spec:
      containers:
      - name: app
        image: nginx:1.27-alpine
```

Selector note:

- `Deployment.spec.selector` immutable sau khi object được tạo. Nếu selector sai, cách sửa sạch thường là tạo Deployment mới hoặc delete/recreate có kiểm soát.
- `Service.spec.selector` patch được, nhưng đổi selector là đổi backend traffic ngay. Luôn kiểm tra `EndpointSlice` sau khi đổi.

## Service selector template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-api
spec:
  selector:
    app.kubernetes.io/name: orders
    app.kubernetes.io/component: api
  ports:
  - name: http
    port: 80
    targetPort: 80
```

## Annotation examples

```yaml
metadata:
  annotations:
    runbook.example.com/url: "https://wiki.example.com/orders-runbook"
    git.example.com/commit: "abc1234"
    config.example.com/checksum: "sha256:..."
```

Use annotations for tool metadata. Use labels when you need selection, grouping, filtering or policy.

## Command cheatsheet

```bash
kubectl create namespace orders-dev
kubectl config set-context --current --namespace=orders-dev
kubectl get namespaces --show-labels

kubectl get pods --show-labels
kubectl get pods -l app.kubernetes.io/name=orders
kubectl get pods -l 'environment in (dev,staging)'
kubectl label pod <pod> debug=true
kubectl label pod <pod> debug-

kubectl annotate deployment orders-api runbook.example.com/url=https://wiki.example.com/orders
kubectl annotate deployment orders-api runbook.example.com/url-

kubectl get svc,endpoints,endpointslice
kubectl describe service orders-api

# "get all" không bao gồm mọi resource
kubectl get all -n orders-dev
kubectl get configmap,secret,resourcequota,limitrange,rolebinding,networkpolicy -n orders-dev
kubectl api-resources --namespaced=true
```

## Label design rules

| Rule | Reason |
|---|---|
| Keep selector labels stable | Avoid orphaning Pods or breaking Services |
| Use specific labels | Avoid Service selecting wrong Pods |
| Do not put secrets in labels | Labels are broadly visible and indexed |
| Avoid high-cardinality labels | Metrics/log systems may explode cardinality |
| Prefer `app.kubernetes.io/*` | Tooling understands common labels |
| Use annotations for large/free-form data | Labels have stricter syntax and selection semantics |

## Failure modes

| Symptom | Có thể do | First commands |
|---|---|---|
| Service no endpoints | Selector không match Pod labels | `get pods --show-labels`, `describe svc` |
| Deployment rollout không tạo Pod | Selector/template mismatch hoặc quota | `describe deployment`, events |
| Query không thấy resource | Sai namespace hoặc label selector | `get ns`, `get pods -A -l ...` |
| Policy không áp dụng | `podSelector` sai label | `describe networkpolicy`, `get pods --show-labels` |
| Cleanup xóa nhầm | Label quá rộng | `kubectl get all -l ...` trước khi delete |
| Dashboard/cost sai | Ownership labels thiếu hoặc không nhất quán | audit labels |

## Namespace guardrail templates

ResourceQuota:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: day14-dev-quota
  namespace: day14-dev
spec:
  hard:
    pods: "10"
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.cpu: "2"
    limits.memory: 2Gi
```

LimitRange:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: day14-dev-defaults
  namespace: day14-dev
spec:
  limits:
  - type: Container
    defaultRequest:
      cpu: 20m
      memory: 32Mi
    default:
      cpu: 100m
      memory: 128Mi
```

## Production checklist

- [ ] Namespace strategy được ghi rõ: theo team, app hay environment.
- [ ] Không dùng namespace `default` cho workload production.
- [ ] Mỗi namespace có owner.
- [ ] Có baseline labels cho app/component/environment/owner.
- [ ] Service selectors được review cùng Pod template labels.
- [ ] Labels không chứa secret, token, email cá nhân hoặc dữ liệu nhạy cảm.
- [ ] Annotations dùng cho metadata tool-specific.
- [ ] Có ResourceQuota/LimitRange cho namespace quan trọng.
- [ ] Có RBAC và NetworkPolicy nếu namespace là boundary vận hành.
- [ ] Runbook debug endpoint bắt đầu từ labels/selectors.
