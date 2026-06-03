# Day 45 Document: Final Production Review Template

## Architecture review

```markdown
# Logistics Platform Production Review

## System context
- Users:
- Main flows:
- Critical APIs:

## Kubernetes components
- Namespace:
- Ingress:
- Services:
- Deployments:
- Stateful workloads:
- GitOps Applications:

## Data dependencies
- PostgreSQL:
- Redis:
- Kafka:

## Failure domains
- Pod:
- Node:
- Zone:
- Cluster:
- Region:
```

## Production checklist

| Category | Evidence |
|---|---|
| Deployability | Helm chart or GitOps app syncs cleanly |
| Availability | Replicas, PDB, topology spread |
| Health | Readiness/liveness/startup probes |
| Capacity | Requests/limits, HPA, node pool plan |
| Networking | Ingress, Service, NetworkPolicy |
| Security | RBAC, Secret strategy, Pod Security |
| Observability | Logs, metrics, dashboard, alert draft |
| Data | Backup, restore drill, RPO/RTO |
| Release | Image tag/digest, rollback, migration plan |
| Operations | Runbooks, ownership, upgrade plan |

## ArgoCD Application baseline

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: logistics-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/platform-config.git
    targetRevision: main
    path: capstone/logistics-stateless
    helm:
      valueFiles:
      - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: logistics
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

Application này chỉ nên trỏ tới Git repo mà ArgoCD controller đọc được. Local folder trên laptop không phải GitOps source hợp lệ nếu controller không mount hoặc fetch được folder đó.

## Stateful dependency baseline

| Component | Lab implementation | Production replacement thường gặp |
|---|---|---|
| PostgreSQL | Single `StatefulSet` + PVC + `pg_dump` Job | Managed PostgreSQL hoặc CloudNativePG với WAL/PITR |
| Redis | Single `Deployment`/`Service` | Managed Redis hoặc Redis HA/operator |
| Kafka | Single broker KRaft lab | Managed Kafka hoặc Strimzi với dedicated storage/node |

Minimum verification:

```bash
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "SELECT 1;"'
kubectl exec deploy/redis -n logistics -- redis-cli ping
kubectl exec deploy/kafka -n logistics -- kafka-topics.sh --bootstrap-server kafka:9092 --list
```

## RPO/RTO table

| Component | RPO | RTO | Method |
|---|---:|---:|---|
| Stateless services | Git commit | 15m | GitOps resync |
| PostgreSQL | 15m | 1h | Managed backup or WAL/PITR |
| Redis cache | none/1h | 15m | Rebuild or snapshot |
| Kafka | depends topic | 2h+ | Replication/replay |
| ArgoCD | 15m | 30m | Git + secret backup |

## NetworkPolicy baseline

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: logistics
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

Allow gateway to backends:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-to-backends
  namespace: logistics
spec:
  podSelector:
    matchExpressions:
    - key: app.kubernetes.io/name
      operator: In
      values:
      - order-service
      - tracking-service
      - notification-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: api-gateway
    ports:
    - protocol: TCP
      port: 8080
```

DNS egress tối thiểu khi bật default deny egress:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: logistics
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

Egress tới backend/data cũng phải được map rõ:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-egress-to-backends
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchExpressions:
        - key: app.kubernetes.io/name
          operator: In
          values:
          - order-service
          - tracking-service
    ports:
    - protocol: TCP
      port: 8080
```

Debug Pod sau default deny cần label và egress rule riêng:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-debug-egress
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: debug
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: api-gateway
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 8080
```

```bash
kubectl run curl -n logistics --rm -i --restart=Never \
  --labels=app.kubernetes.io/component=debug \
  --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
```

Kafka single-broker KRaft lab cần cho broker/controller tự nói chuyện qua `9092/9093` nếu đã bật default deny:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-kafka-self
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: kafka
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: kafka
    ports:
    - protocol: TCP
      port: 9092
    - protocol: TCP
      port: 9093
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: kafka
    ports:
    - protocol: TCP
      port: 9092
    - protocol: TCP
      port: 9093
```

Đừng áp dụng default deny production nếu chưa map traffic Ingress controller, DNS, database, Redis, Kafka, metrics scraping và external APIs.

## PDB baseline

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway
  namespace: logistics
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
```

## HPA baseline

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway
  namespace: logistics
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

## Observability minimum

Metrics:

- Request rate.
- Error rate.
- p95/p99 latency.
- CPU/memory.
- Pod restarts.
- HPA replicas.
- DB connection count/latency.
- Redis memory/evictions.
- Kafka consumer lag.

Alerts:

- API error rate high.
- Gateway p95 latency high.
- Pod CrashLoopBackOff.
- Pod Pending > 10 phút.
- HPA maxed out.
- PostgreSQL backup failed.
- Kafka consumer lag growing.

Monitoring deploy tối thiểu:

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system \
  --set args="{--kubelet-insecure-tls}"
kubectl wait --for=condition=available deploy/metrics-server -n kube-system --timeout=180s
kubectl top pods -n logistics
```

kube-prometheus-stack phù hợp hơn cho dashboard/alert đầy đủ nhưng thường vượt core path 2 giờ trên laptop.

## Backup Job baseline

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: pg-dump-manual
  namespace: logistics
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: pg-dump
        image: postgres:16-alpine
        env:
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_PASSWORD
        command:
        - sh
        - -c
        - pg_dump -h postgres -U postgres postgres > /backup/logistics.sql && ls -lh /backup/logistics.sql
        volumeMounts:
        - name: backup
          mountPath: /backup
      volumes:
      - name: backup
        persistentVolumeClaim:
          claimName: pg-backup
```

Backup evidence phải gồm cả Job complete, file dump tồn tại và ít nhất một restore smoke test.

## Release checklist

- [ ] Image built by CI.
- [ ] Image scanned.
- [ ] Image tag/digest recorded.
- [ ] Helm values updated through PR.
- [ ] ArgoCD diff reviewed.
- [ ] Migration backward-compatible.
- [ ] Sync completed.
- [ ] Smoke test passed.
- [ ] Metrics/logs checked after release.
- [ ] Rollback plan known.

## Final demo script

```bash
kubectl get all -n logistics
kubectl get ingress,svc,endpointslice -n logistics
kubectl get hpa,pdb,networkpolicy -n logistics
kubectl get pvc -n logistics
kubectl get applications -n argocd
kubectl logs deploy/api-gateway -n logistics --tail=50
kubectl run curl -n logistics --rm -i --restart=Never --labels=app.kubernetes.io/component=debug --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
```

## Final questions

1. Nếu chuyển sang EKS/GKE/AKS, bạn giữ nguyên gì và thay gì?
2. Thành phần nào có RPO thấp nhất?
3. Thành phần nào là bottleneck đầu tiên khi traffic tăng?
4. Nếu release lỗi, rollback theo bước nào?
5. Nếu mất cluster, restore thứ tự ra sao?
