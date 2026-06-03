# Day 43: Managed Kubernetes và Production Readiness

## Mục tiêu bài học

- Hiểu khác biệt trách nhiệm giữa self-managed K3s/Kubernetes và managed Kubernetes như EKS/GKE/AKS.
- Thiết kế node pool, networking, storage, ingress/load balancer và IAM ở mức production readiness.
- Biết checklist workload production: probes, resources, PDB, HPA, securityContext, NetworkPolicy, rollout strategy.
- Lập upgrade strategy cho cluster, node pool, add-ons và ứng dụng.
- Nhận diện cost/performance trade-offs khi chạy microservices trên cloud Kubernetes.

## Vấn đề cần giải quyết

Managed Kubernetes không có nghĩa là "cloud lo hết". Cloud provider thường quản lý:

- Control plane availability.
- API server endpoint.
- Control plane patches/upgrades theo cơ chế provider.
- Tích hợp load balancer, disk, IAM ở mức nền tảng.

Team vẫn chịu trách nhiệm:

- Workload YAML/Helm chart.
- Node pool capacity và cost.
- Security baseline.
- Observability.
- Backup app data.
- Upgrade compatibility.
- Incident response.

Nhiều sự cố production không đến từ control plane mà đến từ `requests` sai, node pool thiếu capacity, probe cấu hình xấu, PDB chặn drain, cloud quota hết, IAM sai hoặc storage topology không hiểu.

## Mental Model

```text
Managed Kubernetes responsibility split

Cloud provider:
  control plane
  API endpoint
  managed add-on options
  cloud integrations

Platform team:
  node pools
  CNI/CSI/Ingress choices
  IAM integration
  policy/security
  observability/backup

App team:
  manifests/Helm
  resources/probes
  scaling
  release/rollback
  data correctness
```

Production readiness là hợp đồng giữa ba lớp này.

## Lý thuyết cốt lõi

### Managed control plane

EKS/GKE/AKS chạy Kubernetes control plane dưới quyền cloud provider. Bạn thường không SSH vào control plane node và không trực tiếp backup `etcd`.

Lợi ích:

- Giảm vận hành control plane.
- Control plane HA dễ hơn self-managed.
- Tích hợp cloud IAM/LB/storage.
- Upgrade path có tooling/provider support.

Giới hạn:

- Vẫn có version skew và deprecation.
- Control plane outage vẫn có thể ảnh hưởng deploy/scale, dù Pod đang chạy tiếp.
- Add-on version/CNI/CSI cần quản lý.
- Cloud quota, IAM và networking có thể gây incident.

### Node pool strategy

Node pool nên phản ánh workload class:

| Node pool | Workload | Đặc điểm |
|---|---|---|
| `system` | CoreDNS, ingress, monitoring, controllers | Taint để tránh app thường |
| `general` | API/services stateless | On-demand, autoscale |
| `spot` | Worker/batch chịu interrupt | Rẻ hơn, cần toleration/affinity |
| `memory` | Redis, JVM heap lớn | RAM nhiều |
| `storage` | Stateful workloads self-managed | Disk/network ổn định |
| `gpu` | ML/video workloads | Taint riêng, cost cao |

Không nên để tất cả workload chạy chung một node pool nếu production có nhiều loại workload. Nhưng quá nhiều node pool làm scheduling/cost phức tạp.

### Cloud LoadBalancer và Ingress

Trong K3s lab, `Traefik` và `Service` kiểu `LoadBalancer` có thể được mô phỏng bằng local/load balancer component. Trên cloud:

- `Service type LoadBalancer` thường tạo cloud LB.
- Ingress controller có thể tạo ALB/NLB/GCLB/Application Gateway tùy controller.
- TLS certificate có thể dùng cert-manager hoặc cloud certificate manager.
- External DNS có thể tự động cập nhật DNS records.

Trade-off:

| Pattern | Khi dùng | Điểm cần chú ý |
|---|---|---|
| One LB per Service | Service độc lập, L4 | Cost tăng, nhiều public endpoint |
| Shared Ingress LB | HTTP services, routing theo host/path | Controller là shared dependency |
| API Gateway ngoài cluster | Enterprise gateway, auth/rate limit | Thêm hop, config split |
| Service mesh ingress | Cần L7 policy/mTLS thống nhất | Complexity cao |

### Cloud CSI và storage topology

Cloud CSI tạo volume từ disk provider:

- EBS trên AWS thường gắn với một Availability Zone.
- GCE PD cũng có topology theo zone/region tùy loại.
- Azure Disk có giới hạn attach/topology riêng.

Điểm production:

- PVC binding mode `WaitForFirstConsumer` giúp scheduler chọn zone hợp lý.
- StatefulSet multi-zone cần hiểu replication ở app/storage layer.
- Volume snapshot không giống backup application-consistent.
- Disk performance phụ thuộc size/type/provisioned IOPS.

### IAM và workload identity

Không nên nhét cloud access key dài hạn vào Kubernetes Secret nếu provider có workload identity:

- AWS: IRSA/EKS Pod Identity.
- GCP: Workload Identity.
- Azure: Workload Identity/Managed Identity.

Mục tiêu:

```text
Pod ServiceAccount
  -> mapped cloud identity
  -> least privilege IAM policy
  -> access cloud API
```

Điều này giảm rủi ro secret leakage và xoay vòng key.

Provider-specific notes:

| Provider | Cơ chế identity | Ghi chú vận hành |
|---|---|---|
| EKS | IRSA hoặc EKS Pod Identity | Map Kubernetes `ServiceAccount` tới IAM role; policy nên giới hạn theo bucket/queue/topic cụ thể |
| GKE | Workload Identity Federation for GKE | Map KSA tới Google Service Account; tránh JSON key trong Secret |
| AKS | Microsoft Entra Workload ID/Managed Identity | Dùng federated credential cho ServiceAccount; kiểm tra audience/issuer khi debug |

Khi migrate từ K3s lab sang cloud, Secret chứa access key trong lab nên được thay bằng workload identity. Nếu vẫn cần Secret tạm thời, phải có rotation, owner và scope ngắn hạn.

### Production workload checklist

Một Deployment production tối thiểu nên có:

- `resources.requests` và `limits` hợp lý.
- `readinessProbe`, `livenessProbe`, `startupProbe` nếu app cần warmup.
- `PodDisruptionBudget`.
- `topologySpreadConstraints` hoặc anti-affinity mềm.
- `securityContext`.
- Labels/annotations chuẩn.
- HPA nếu stateless và metrics phù hợp.
- Rollout strategy và rollback plan.
- NetworkPolicy nếu CNI hỗ trợ.
- Log/metrics/tracing.

## Deep dive: Upgrade strategy

Upgrade không chỉ là control plane version:

```text
Kubernetes version
  + control plane
  + node kubelet
  + CNI
  + CSI
  + ingress controller
  + cert-manager
  + external-dns
  + ArgoCD
  + CRDs/operators
  + workload APIs
```

Upgrade order thường:

1. Kiểm tra API deprecation.
2. Upgrade/test add-ons trong staging.
3. Upgrade control plane.
4. Upgrade node pools từng pool.
5. Drain node có kiểm soát.
6. Verify workloads, metrics, logs.
7. Rollback/mitigation nếu có.

PDB, readiness và graceful shutdown quyết định drain có an toàn không. PDB quá chặt có thể chặn upgrade; PDB thiếu có thể làm mất availability.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Chủ đề | K3s local/self-managed | Kubernetes self-managed | EKS/GKE/AKS |
|---|---|---|---|
| Control plane | Team tự vận hành, K3s đóng gói nhẹ | Team tự vận hành đầy đủ | Provider quản lý |
| LB | Traefik/ServiceLB/MetalLB/lab | MetalLB/hardware/cloud | Cloud LB/controller |
| Storage | local-path/Longhorn/NFS | CSI tự chọn | Cloud CSI managed/add-on |
| IAM | Không có cloud identity mặc định | Tự tích hợp | Workload identity/IAM native |
| Upgrade | Team tự lên kế hoạch | Team tự vận hành sâu | Provider hỗ trợ nhưng vẫn cần test |
| DR | Team backup datastore | Team backup etcd | Provider lo control plane, team lo data |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Trade-off |
|---|---|---|
| Managed Kubernetes | Production cloud, muốn giảm vận hành control plane | Cost, provider-specific integration |
| Self-managed K3s | Edge, lab, small cluster, cost thấp | Team chịu trách nhiệm HA/backup/upgrade |
| One general node pool | Team nhỏ, workload đồng nhất | Noisy neighbor, khó isolation |
| Nhiều node pool | Workload đa dạng, cost optimization | Scheduling/IAM/autoscaling phức tạp |
| Spot nodes | Batch/worker chịu restart | Interruption, cần resilience |
| Managed DB | Dữ liệu critical | Cost cao hơn, ít control hơn |
| DB trong Kubernetes | Lab, edge, yêu cầu đặc biệt | Backup/failover/storage khó |

### Best Practices

- Dùng managed control plane cho production cloud nếu không có lý do mạnh để self-managed.
- Tách system workload khỏi app workload bằng node pool/taint.
- Luôn cấu hình requests trước khi bật autoscaling.
- Không chạy production với default namespace và secret thủ công.
- Dùng workload identity thay vì static cloud keys.
- Kiểm tra API deprecation trước upgrade.
- Có PDB nhưng không đặt quá chặt.
- Thiết kế observability trước khi incident.
- Có cost tags/labels cho namespace/app/team.
- Test node drain trong staging.

## Performance Considerations

Managed Kubernetes performance phụ thuộc nhiều lớp:

- Node instance type: CPU generation, network bandwidth, disk throughput.
- CNI: pod density, IP exhaustion, overlay/routed, eBPF.
- Cloud LB: connection handling, cross-zone traffic, idle timeout.
- Storage: IOPS/throughput/latency, zone placement.
- Autoscaling: HPA metric delay, Cluster Autoscaler provisioning delay.
- Image pull: registry location, image size, node cache.

Bottleneck thường gặp:

- CPU throttling do limit thấp.
- Node memory pressure do requests thấp hơn thực tế.
- IP exhaustion trong subnet.
- LB health check không khớp readiness.
- PVC gắn sai zone làm Pod Pending.
- Autoscaler không scale vì PDB/affinity/taints.

## Debugging Checklist

Cluster readiness:

```bash
kubectl get nodes -o wide
kubectl describe node <node>
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
kubectl top nodes
kubectl top pods -A
```

Workload readiness:

```bash
kubectl rollout status deploy/<name> -n <namespace>
kubectl describe deploy/<name> -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace>
kubectl get pdb,hpa,svc,ingress,pvc -n <namespace>
```

Cloud integration:

```bash
kubectl describe svc <svc> -n <namespace>
kubectl describe ingress <ingress> -n <namespace>
kubectl describe pvc <pvc> -n <namespace>
kubectl get storageclass
kubectl auth can-i --list -n <namespace>
```

Root cause phổ biến:

| Symptom | Root cause |
|---|---|
| LB không có external IP/hostname | Cloud controller/IAM/quota/subnet tag sai |
| Pod Pending sau upgrade | node selector/taint/resource/PVC topology |
| Drain kẹt | PDB quá chặt hoặc Pod không evict được |
| HPA không scale | Metrics server/Prometheus adapter thiếu hoặc requests sai |
| App lỗi sau upgrade | Deprecated API, admission policy, controller version mismatch |

## Liên hệ với kiến thức đã biết

Managed Kubernetes giống dùng managed database: provider giảm phần vận hành nền, nhưng schema, query, connection pool, backup logic và SLO vẫn là trách nhiệm của team. Với microservices, node pool tương tự capacity tier, Ingress/LB tương tự edge routing, workload identity tương tự service-to-cloud authorization.

## Tóm tắt

- Managed Kubernetes giảm gánh nặng control plane, không thay thế platform engineering.
- Production readiness cần phối hợp node pool, IAM, networking, storage, security, observability và workload spec.
- Upgrade là quy trình nhiều thành phần, không chỉ đổi version cluster.
- PDB, probes, requests và topology quyết định availability khi node drain/rollout.
- K3s rất tốt cho học/lab/edge, nhưng production cloud thường nên cân nhắc EKS/GKE/AKS nếu team không muốn tự vận hành control plane.

## Câu hỏi tự kiểm tra

1. Cloud provider quản lý gì và team vẫn phải quản lý gì trong EKS/GKE/AKS?
2. Vì sao node pool `system` nên tách khỏi app workload?
3. PDB có thể gây lỗi gì khi upgrade node pool?
4. Workload identity tốt hơn static cloud key ở điểm nào?
5. Vì sao PVC topology có thể làm Pod Pending?

## Tài liệu tham khảo

- Kubernetes Production Best Practices: https://kubernetes.io/docs/setup/production-environment/
- Amazon EKS Documentation: https://docs.aws.amazon.com/eks/
- Google Kubernetes Engine Documentation: https://cloud.google.com/kubernetes-engine/docs
- Azure Kubernetes Service Documentation: https://learn.microsoft.com/azure/aks/
- Kubernetes Pod Disruption Budgets: https://kubernetes.io/docs/tasks/run-application/configure-pdb/
