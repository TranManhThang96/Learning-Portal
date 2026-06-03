# Day 28: Kafka on Kubernetes

## Mục tiêu bài học

- Hiểu vì sao Kafka khó hơn PostgreSQL/Redis khi chạy trên Kubernetes.
- Deploy được Kafka single-broker dạng lab để thực hành topic, partition, produce/consume và persistence.
- Nắm broker identity, advertised listeners, storage, replication factor và network constraints.
- Hiểu Strimzi operator ở mức architecture và resource model.
- Biết các production caveat trước khi tự vận hành Kafka trong Kubernetes.

## Vấn đề cần giải quyết

Kafka là distributed log. Nó không chỉ cần một process chạy được. Kafka cần:

- Broker identity ổn định.
- Network address được advertise đúng cho clients và brokers.
- Durable storage cho log segments.
- Replication factor và ISR để chịu lỗi broker.
- Controller quorum.
- Partition count, retention, compaction và throughput sizing.
- Client behavior khi rebalance, timeout, retry và ordering.

Kubernetes có thể cung cấp StatefulSet, PVC và Service DNS. Nhưng Kafka correctness còn phụ thuộc Kafka-level replication, listener config, storage latency và operational automation.

## Mental Model

```text
Producer/Consumer
  |
  v
Bootstrap Service kafka:9092
  |
  v
Broker advertised listener
  |
  v
StatefulSet broker identity: kafka-0, kafka-1, kafka-2
  |
  +-- PVC per broker
  +-- partition replicas
  +-- controller quorum
```

Kafka client không chỉ dùng bootstrap address. Sau khi bootstrap, client nhận metadata và kết nối tới broker addresses được Kafka advertise. Nếu `advertised.listeners` sai, bootstrap có thể thành công nhưng produce/consume vẫn fail.

## Lý thuyết cốt lõi

### Broker identity

Mỗi Kafka broker cần identity ổn định:

- `broker.id` hoặc `node.id`.
- Hostname/DNS ổn định.
- Data directory gắn với identity đó.

`StatefulSet` phù hợp hơn `Deployment` vì Pod name và PVC ổn định: `kafka-0`, `kafka-1`, `kafka-2`.

### Listeners và advertised listeners

Kafka có hai lớp địa chỉ:

- Listener bind address: broker listen ở đâu bên trong container/Pod.
- Advertised listener: broker nói với client rằng "hãy kết nối tới tôi ở địa chỉ này".

Trong Kubernetes, advertised listener nội bộ thường dùng DNS ổn định:

```text
kafka-0.kafka-headless.<namespace>.svc.cluster.local:9092
```

Expose Kafka ra ngoài cluster khó hơn HTTP vì clients cần kết nối tới từng broker, không chỉ một ingress endpoint.

### Storage và log segments

Kafka lưu topic partitions thành log segments trên disk. PVC mất hoặc mount nhầm có thể làm broker mất log local. Replication factor giúp chịu lỗi broker/disk, nhưng chỉ khi topic được tạo với replication factor phù hợp và có đủ brokers.

PVC snapshot không phải backup Kafka hoàn chỉnh nếu bạn chưa hiểu consistency, replication state và consumer offsets. Với Kafka, disaster recovery thường dùng replication sang cluster khác, ví dụ MirrorMaker 2, hơn là chỉ snapshot disk.

### Replication factor, ISR và min.insync.replicas

Các concept quan trọng:

- Replication factor: số bản sao của partition.
- Leader replica: broker nhận read/write cho partition.
- ISR: in-sync replicas.
- `min.insync.replicas`: số replicas tối thiểu phải bắt kịp để nhận write khi producer dùng `acks=all`.

Single-broker lab chỉ dùng replication factor `1`. Điều này không chịu được broker/disk failure.

### KRaft và ZooKeeper

Kafka hiện đại dùng KRaft để thay ZooKeeper cho metadata quorum. Nhiều cluster cũ vẫn dùng ZooKeeper. Khi học hoặc vận hành, cần biết cluster của bạn đang ở mode nào vì deployment, upgrade và troubleshooting khác nhau.

### Strimzi overview

Strimzi là operator phổ biến để chạy Apache Kafka trên Kubernetes. Nó reconcile custom resources như:

- `Kafka`: định nghĩa cluster, listeners, storage, versions.
- `KafkaNodePool`: nhóm node/broker trong kiến trúc mới hơn.
- `KafkaTopic`: quản lý topic declaratively.
- `KafkaUser`: quản lý users/certs/ACLs.
- `KafkaConnect`: chạy Kafka Connect.
- `KafkaMirrorMaker2`: replication giữa clusters.
- `KafkaRebalance`: tích hợp Cruise Control cho rebalance.

Strimzi giúp giảm YAML thủ công, nhưng production Kafka vẫn cần sizing, monitoring, upgrade, storage và incident runbook.

### Probes cho Kafka

Kafka startup có thể chậm hơn web service vì format data dir, controller quorum, log recovery và metadata initialization. Vì vậy probe nên có ba vai trò rõ:

- `startupProbe`: cho Kafka đủ thời gian boot/recover trước khi liveness được bật.
- `readinessProbe`: chỉ nhận client traffic khi broker trả metadata/API version được.
- `livenessProbe`: phát hiện broker kẹt lâu, nhưng không quá hung hăng để tránh restart loop trong lúc recovery.

Single-broker lab có thể dùng `kafka-broker-api-versions.sh` local. Production nên dùng probe do operator/distribution khuyến nghị và phải test với broker restart có dữ liệu thật.

## Kafka trên Kubernetes khó ở đâu?

### Network

Kafka không giống HTTP service đơn giản. Client bootstrap tới một endpoint, sau đó phải reach được từng broker advertised. Load balancing mù qua một Service có thể làm metadata hoặc connection behavior sai.

### Storage

Kafka throughput phụ thuộc disk. Distributed storage có replication riêng có thể cộng thêm latency và write amplification. Kafka đã có replication ở application layer, nên cần cân nhắc kỹ khi đặt lên replicated block storage.

### Scheduling

Production Kafka cần:

- Anti-affinity để brokers không nằm cùng node.
- Topology spread theo zone/rack.
- PodDisruptionBudget.
- Controlled rolling restart.
- Capacity headroom khi rebalance.

### Operations

Kafka incident thường liên quan nhiều lớp:

- Broker logs.
- Controller/quorum state.
- Topic config.
- Consumer group lag.
- Disk usage/retention.
- Network between clients and brokers.
- JVM heap/GC nếu dùng distribution JVM.

## K3s notes

- K3s/k3d rất tốt để học object model và Kafka commands.
- Single-node K3s không chứng minh Kafka HA.
- local-path storage chỉ phù hợp lab.
- Expose Kafka ra ngoài local cluster thường tốn thời gian hơn giá trị học ngày này. Bắt đầu với client Pod trong cluster.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điều phù hợp | Caveat |
|---|---|---|
| K3s/k3d lab | Học listener nội bộ, topic command, PVC persistence | Không chứng minh HA, multi-zone, throughput hoặc external listener |
| Kubernetes self-managed | Chạy Kafka được nếu dùng operator/runbook/storage tốt | Team tự chịu broker/quorum/storage/upgrade/rebalance incidents |
| Managed Kubernetes + Strimzi | Cloud CSI/node pools hỗ trợ hạ tầng, Strimzi reconcile Kafka lifecycle | Vẫn cần Kafka sizing, client config, monitoring và DR |
| Managed Kafka | Provider xử lý nhiều phần broker HA/upgrade/storage | App team vẫn chịu topic design, producer settings, consumer lag và cost |

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Rủi ro chính |
|---|---|---|
| Single-broker YAML | Lab local trong 1 ngày | Không HA, không scale an toàn, config brittle |
| Hand-written multi-broker StatefulSet | Hiếm khi nên chọn | Dễ sai listener/quorum/rolling upgrade/rebalance |
| Strimzi/operator | Self-managed Kafka production | Phải vận hành CRD/operator và hiểu Kafka internals |
| Managed Kafka | Production critical, team không muốn broker on-call | Cost, provider limits, networking/IAM |

### Best Practices

- Nên dùng operator hoặc managed Kafka cho production.
- Nên đặt RF=3 và `min.insync.replicas=2` cho topic quan trọng nếu có đủ brokers.
- Nên dùng anti-affinity/topology spread/PDB cho brokers.
- Tránh expose Kafka qua một Service/Ingress duy nhất mà bỏ qua advertised listeners.
- Tránh snapshot PVC làm DR strategy duy nhất.

## Performance Considerations

Kafka throughput phụ thuộc vào:

- Disk sequential write/read và page cache.
- Partition count, leader distribution và hot partitions.
- Producer `batch.size`, `linger.ms`, compression, `acks`.
- Consumer group parallelism và downstream speed.
- Network giữa clients, brokers và replicas.
- JVM heap/GC với distribution JVM.

Distributed storage có thể cộng thêm replication latency trong khi Kafka đã replicate ở application layer. Benchmark storage và network trước khi chọn backend.

## Debugging Checklist

```bash
kubectl get pod,pvc,svc,endpoints -n <ns> -o wide
kubectl logs kafka-0 -n <ns> --tail=150
kubectl describe pod kafka-0 -n <ns>
kubectl exec -n <ns> kafka-client -- kafka-broker-api-versions.sh --bootstrap-server kafka:9092
kubectl exec -n <ns> kafka-client -- kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic <topic>
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

Nếu bootstrap thành công nhưng producer/consumer fail, nghi ngờ `advertised.listeners` trước khi debug app code.

## Liên hệ với kiến thức đã biết

Kafka trong microservices là event log và integration backbone. Các khái niệm quen thuộc như retry, idempotency, ordering, backpressure và schema evolution vẫn quyết định độ an toàn. Kubernetes thêm broker identity, Service DNS, PVC lifecycle, scheduling và operator reconciliation vào bài toán.

## Tóm tắt

Kafka trên Kubernetes là bài toán distributed system operations. StatefulSet và PVC chỉ giải quyết identity và storage binding. Production Kafka cần listener design, replication, quorum, scheduling, monitoring, capacity planning và upgrade discipline. Strimzi giúp automate nhiều phần, nhưng không thay thế hiểu biết Kafka cốt lõi.

## Câu hỏi tự kiểm tra

1. Vì sao Kafka cần `advertised.listeners` đúng?
2. Single-broker lab chứng minh được gì và không chứng minh được gì?
3. `startupProbe` khác gì `readinessProbe` với Kafka?
4. RF, ISR và `min.insync.replicas` liên quan thế nào?
5. Strimzi giảm rủi ro nào và vẫn để lại trách nhiệm nào cho team?

## Production checklist

- [ ] Có lý do rõ khi tự chạy Kafka thay vì managed Kafka.
- [ ] Dùng operator hoặc automation có owner.
- [ ] Broker/controller count đủ cho failure domain.
- [ ] Replication factor và `min.insync.replicas` phù hợp.
- [ ] Producer `acks`, retry và idempotence được chuẩn hóa.
- [ ] Storage latency, throughput và disk capacity được benchmark.
- [ ] Rack/zone awareness, anti-affinity và PDB được cấu hình.
- [ ] Monitoring có broker health, under-replicated partitions, consumer lag, disk, request latency.
- [ ] Backup/DR dùng replication hoặc strategy rõ, không chỉ PVC snapshot.
- [ ] Upgrade và rolling restart được rehearsed.

## Anti-patterns

- Dùng single-broker Kafka làm production queue.
- Expose Kafka qua một Service/Ingress rồi bỏ qua advertised listeners.
- Tạo topic replication factor `1` rồi kỳ vọng chịu lỗi broker.
- Đặt Kafka lên storage latency cao mà chưa benchmark.
- Không monitor consumer lag.
- Tự cài Kafka thủ công trong production khi team chưa có runbook.

## Tài liệu tham khảo

- Apache Kafka documentation: Operations.
- Apache Kafka documentation: KRaft.
- Strimzi documentation.
- Kubernetes documentation: StatefulSets.
