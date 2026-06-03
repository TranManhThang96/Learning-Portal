# Day 45: Capstone Project Part 2

## Mục tiêu bài học

- Hoàn thiện capstone bằng Redis, PostgreSQL, Kafka, monitoring, GitOps và backup strategy.
- Biết phân biệt phần nào nên chạy trong Kubernetes lab và phần nào nên dùng managed service ở production.
- Thêm HPA, PDB, NetworkPolicy, observability và production checklist cho hệ thống giao vận.
- Thiết kế release/rollback bằng ArgoCD và backup/restore drill tối thiểu.
- Tổng kết toàn bộ 45 ngày thành một bản production readiness review có trade-offs rõ ràng.

## Vấn đề cần giải quyết

Day 44 tạo được stateless routing. Nhưng hệ thống microservices thực tế không dừng ở đó:

- Order cần database.
- Tracking có thể dùng cache.
- Notification/payment có thể phát event.
- Release cần GitOps.
- Incident cần logs/metrics/traces.
- Dữ liệu cần backup.
- Production cần security, scaling và upgrade plan.

Day 45 không yêu cầu biến lab thành production thật. Mục tiêu là biết ranh giới: lab deploy để học mechanics; production decision phải cân nhắc managed services, SLO, cost, team capacity và failure mode.

## Target architecture

```text
Client
  |
  v
Ingress
  |
  v
api-gateway
  |
  +--> order-service ----> PostgreSQL
  |        |
  |        +-----------> Kafka topic: order-events
  |
  +--> tracking-service -> Redis
  |
  +--> notification-service -> Kafka consumer

Platform:
  + ArgoCD
  + Prometheus/Grafana hoặc metrics stack
  + Backup/restore runbook
  + NetworkPolicy/RBAC/Pod Security
```

## Mental Model

```text
Production-ready capstone =
  deployable
  + observable
  + scalable
  + recoverable
  + secure enough
  + explainable trade-offs
```

Không phải mọi thành phần phải production-grade trong lab. Nhưng bạn phải biết nếu production thật thì thành phần nào cần thay bằng managed service hoặc operator.

## Lý thuyết cốt lõi

### PostgreSQL decision

Trong lab:

- Dùng single-instance PostgreSQL bằng Helm chart hoặc manifest.
- PVC nhỏ.
- Secret đơn giản.
- Backup bằng `pg_dump` hoặc Velero demo.

Trong production:

- Ưu tiên managed PostgreSQL nếu chạy trên cloud.
- Nếu self-managed trong Kubernetes, dùng operator như CloudNativePG/Zalando và backup/PITR nghiêm túc.
- Không coi PVC snapshot là backup duy nhất.

Trade-off:

| Option | Khi chọn | Rủi ro |
|---|---|---|
| Managed PostgreSQL | Dữ liệu critical, cloud production | Cost, provider lock-in |
| PostgreSQL operator | Cần chạy trong cluster/on-prem | Vận hành backup/failover phức tạp |
| Single Pod PostgreSQL | Lab/dev | Không HA, backup yếu |

### Redis decision

Redis có thể là cache hoặc state store. Hai use case này khác nhau:

| Use case | Backup yêu cầu | Production approach |
|---|---|---|
| Cache thuần | Có thể mất và warm lại | Managed Redis hoặc Redis đơn giản |
| Session/rate limit state | Cần persistence/replica | Managed Redis/Redis HA |
| Queue tạm | Cần hiểu loss semantics | Cân nhắc Kafka/RabbitMQ |

Trong capstone, Redis lab giúp service discovery, Secret, ConfigMap và dependency readiness.

### Kafka decision

Kafka trên Kubernetes có nhiều ràng buộc:

- Broker identity ổn định.
- Storage latency/throughput.
- Network và advertised listeners.
- Rebalancing và partition placement.
- Backup/DR không đơn giản như DB.

Lab có thể dùng Strimzi hoặc chart nhẹ. Production nên cân nhắc managed Kafka nếu team không có kinh nghiệm vận hành broker/storage.

### Monitoring và SLO

Capstone cần tối thiểu:

- Pod health/restart.
- CPU/memory.
- Request rate/error/latency nếu app expose metrics.
- Ingress/gateway latency.
- PostgreSQL/Redis/Kafka basic health.

SLO mẫu:

```text
api-gateway availability: 99.9%
order creation p95 latency: < 300ms
error rate: < 1%
restore order database RTO: 1h
order database RPO: 15m
```

### GitOps final shape

GitOps repo nên có:

```text
capstone/
  charts/
  envs/
    dev/
      values.yaml
    prod/
      values.yaml
  applications/
    logistics-dev.yaml
```

ArgoCD quản lý:

- Namespace.
- Stateless services.
- Stateful lab dependencies nếu dùng trong cluster.
- Monitoring add-ons nếu scope cho phép.
- NetworkPolicy/PDB/HPA.

Secret production không commit plaintext.

### Minimum implementation contract cho Day 45

Day 45 không chỉ là worksheet. Bản hoàn thành tối thiểu phải có manifest hoặc Helm values chạy được cho:

- Redis lab `Deployment`/`Service`.
- PostgreSQL lab `StatefulSet`/`Service`/PVC và backup `pg_dump` Job.
- Kafka lab single broker hoặc Strimzi CR nếu máy đủ tài nguyên; nếu không chạy được, phải commit manifest và ghi rõ resource blocker.
- HPA/PDB cho stateless services.
- NetworkPolicy có default-deny có kiểm soát, rule DNS egress và rule traffic gateway/backend/data.
- ArgoCD `Application` trỏ tới Git repo thật của capstone.
- Monitoring baseline: ít nhất `metrics-server`/`kubectl top` hoặc kube-prometheus-stack nếu cluster đủ tài nguyên.

Phần nào không chạy được trong laptop phải có evidence: command fail, lý do môi trường, và production replacement.

## Deep dive: Production readiness review

Review capstone theo failure mode:

```text
What if api-gateway Pod dies?
  Deployment recreates, Service routes to remaining Ready Pod, PDB protects voluntary disruption.

What if order-service cannot connect PostgreSQL?
  Readiness should fail or app should degrade clearly; logs/metrics expose dependency error.

What if node is drained?
  PDB/topology/resources decide disruption.

What if release is bad?
  ArgoCD rollback image/config; DB migration must be backward-compatible.

What if namespace is deleted?
  GitOps restores manifests; backup restores data.

What if cloud region fails?
  Need DR design beyond this lab.
```

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Thành phần | K3s lab | Self-managed production | EKS/GKE/AKS production |
|---|---|---|---|
| Ingress | Traefik mặc định hoặc NGINX | MetalLB/LB + controller | Cloud LB/Ingress controller |
| PostgreSQL | Single Pod/chart | Operator + backup/PITR | Managed DB thường tốt hơn |
| Redis | Single/replica lab | Operator/HA | Managed Redis thường tốt hơn |
| Kafka | Strimzi lab nếu đủ tài nguyên | Strimzi + storage/network expertise | Managed Kafka thường tốt hơn |
| GitOps | ArgoCD single instance | ArgoCD HA/RBAC/backup | ArgoCD + cloud IAM/private repo |
| Backup | Velero/pg_dump demo | Velero + storage + app backup | Cloud backup + app backup + Velero |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Trade-off |
|---|---|---|
| Chạy toàn bộ trong cluster | Lab, on-prem, học vận hành | Complexity stateful cao |
| Managed data services | Cloud production, dữ liệu critical | Cost và provider dependency |
| HPA theo CPU | Stateless service đơn giản | Không phản ánh queue/latency |
| HPA theo custom metrics | Traffic/queue driven | Cần metrics pipeline |
| NetworkPolicy default deny | Security tốt | Cần map traffic đầy đủ |
| GitOps auto-sync | Dev/staging | Production cần gate |
| Manual production sync | Kiểm soát release | Chậm hơn |

### Best Practices

- Viết README kiến trúc và ADR cho các quyết định chính.
- Tạo production checklist trước khi gọi hệ thống là "ready".
- Không chạy database production trong Kubernetes nếu team chưa có năng lực backup/failover/upgrade.
- Dùng PDB và topology spread cho gateway/service critical.
- Dùng NetworkPolicy để backend không bị gọi tùy tiện.
- Dùng ArgoCD cho deploy, không để CI apply trực tiếp production.
- Có restore drill cho database, không chỉ backup schedule.
- Có dashboard/alert tối thiểu trước khi demo hoàn tất.

## Performance Considerations

Toàn hệ thống có nhiều bottleneck:

- API Gateway: connection pooling, timeout, retry.
- Order service: DB connection pool, transaction latency.
- PostgreSQL: disk IOPS, locks, connection count.
- Redis: memory eviction, persistence fsync, network.
- Kafka: partition count, broker disk/network, consumer lag.
- Kubernetes: resource requests, node autoscaling delay, image pull time.

Capstone production review phải chỉ ra:

- Service nào scale horizontal được.
- Service nào bị stateful dependency giới hạn.
- Metrics nào dùng để scale.
- Bottleneck nào cần load test.
- Failure nào có blast radius lớn nhất.

## Debugging Checklist

End-to-end:

```bash
kubectl get pods -n logistics
kubectl get svc,ingress,endpointslice -n logistics
kubectl get hpa,pdb,networkpolicy -n logistics
kubectl logs deploy/api-gateway -n logistics
kubectl logs deploy/order-service -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --labels=app.kubernetes.io/component=debug --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl get events -n logistics --sort-by=.lastTimestamp
```

Stateful:

```bash
kubectl get pvc -n logistics
kubectl describe pvc <pvc> -n logistics
kubectl logs statefulset/<name> -n logistics
kubectl exec -n logistics <postgres-pod> -- pg_isready
kubectl exec -n logistics <redis-pod> -- redis-cli ping
```

GitOps:

```bash
kubectl get applications -n argocd
argocd app get logistics-dev
argocd app diff logistics-dev
argocd app sync logistics-dev
```

Backup:

```bash
velero backup get
velero restore get
kubectl get jobs -n logistics
kubectl logs job/<backup-job> -n logistics
```

## Liên hệ với kiến thức đã biết

Capstone buộc bạn nối backend architecture với platform contract. PostgreSQL connection pool không chỉ là code config, nó ảnh hưởng Pod resources và HPA. Kafka topic design ảnh hưởng storage và DR. API Gateway retry policy ảnh hưởng backend overload. Kubernetes không loại bỏ system design; nó làm các giả định vận hành trở nên rõ ràng hơn.

## Tóm tắt

- Day 45 hoàn thiện capstone bằng stateful dependencies, observability, GitOps, backup và production review.
- Lab có thể chạy single-instance dependency, nhưng production cần managed service/operator và restore drill.
- Production readiness là khả năng deploy, quan sát, scale, phục hồi và giải thích trade-offs.
- Hoàn thành 45 ngày không biến bạn thành platform team đầy đủ, nhưng đủ nền để thiết kế, deploy và debug microservices Kubernetes một cách có hệ thống.

## Câu hỏi tự kiểm tra

1. Thành phần nào trong capstone nên dùng managed service nếu lên production cloud?
2. GitOps restore được gì và không restore được gì?
3. NetworkPolicy default deny sẽ làm lộ lỗi thiết kế traffic nào?
4. Vì sao rollback app có thể không rollback được database state?
5. Bạn sẽ chứng minh capstone đạt production readiness bằng evidence nào?

## Tài liệu tham khảo

- Kubernetes Documentation: https://kubernetes.io/docs/
- Helm Documentation: https://helm.sh/docs/
- Argo CD Documentation: https://argo-cd.readthedocs.io/
- Velero Documentation: https://velero.io/docs/
- Prometheus Operator/kube-prometheus: https://github.com/prometheus-operator/kube-prometheus
- Strimzi Documentation: https://strimzi.io/docs/
