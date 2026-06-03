# Day 27: Redis on Kubernetes

## Mục tiêu bài học

- Deploy được Redis dạng lab bằng `StatefulSet`, `Service`, `Secret`, `ConfigMap` và `PVC`.
- Phân biệt Redis standalone, Redis Sentinel và Redis Cluster.
- Hiểu persistence `RDB` và `AOF`, trade-off giữa performance và durability.
- Biết vì sao scale Pod không tự tạo Redis replication/failover.
- Nắm các caveat production: memory, eviction, failover, client compatibility, backup và monitoring.

## Vấn đề cần giải quyết

Redis thường được dùng vì nhanh và đơn giản, nhưng khi đưa vào Kubernetes, nhiều team đánh đồng ba use case rất khác nhau:

- Cache có thể mất dữ liệu.
- Session store cần durability vừa phải.
- Queue/stream hoặc state store cần data safety cao hơn.

Redis có thể chạy trong Kubernetes, nhưng mode vận hành quyết định mức rủi ro:

- Standalone: đơn giản, phù hợp lab/dev/cache nhỏ.
- Sentinel: HA cho một primary với replicas, client cần hiểu Sentinel hoặc dùng proxy/operator.
- Cluster mode: sharding theo hash slots, cần client hỗ trợ Redis Cluster.

Kubernetes restart Pod tốt, nhưng Redis failover đúng cần Redis-level replication và quorum.

## Mental Model

```text
Client
  |
  v
Service redis:6379
  |
  v
StatefulSet redis
  |
  +-- redis-0
        |
        +-- PVC data-redis-0

Optional HA layers:
Redis primary/replica replication
Redis Sentinel quorum
Redis Cluster hash slots
Operator reconciliation
```

PVC giữ file `appendonly.aof` hoặc RDB snapshot. Nó không tự tạo replica, không tự promote primary và không đảm bảo client reconnect đúng sau failover.

## Lý thuyết cốt lõi

### Redis standalone

Standalone chỉ có một Redis instance. Kubernetes có thể restart Pod nếu process chết và mount lại PVC cũ.

Phù hợp:

- Lab.
- Dev/test.
- Cache có thể rebuild.
- Workload nhỏ không cần HA.

Không phù hợp:

- Production state critical.
- RPO/RTO thấp.
- Workload cần failover tự động.

### Redis Sentinel

Sentinel giám sát primary/replica, bầu chọn failover và publish primary mới. Để hoạt động đúng cần:

- Nhiều Redis instances.
- Nhiều Sentinel instances.
- Quorum phù hợp.
- Client hoặc proxy biết hỏi Sentinel để tìm primary.
- Network ổn định giữa Pods.

Kubernetes Service trỏ vào một primary cũ có thể không đủ. Bạn cần routing model rõ sau failover.

### Redis Cluster

Redis Cluster chia keyspace thành hash slots và phân phối lên nhiều masters. Nó giải quyết sharding và HA theo slot, nhưng yêu cầu:

- Client hỗ trợ Redis Cluster redirection.
- Stable Pod identity và network address.
- Mỗi master có replicas.
- Hiểu resharding, rebalance và failure state.

Redis Cluster không chỉ là scale StatefulSet replicas lên nhiều Pod.

### Persistence: RDB và AOF

Redis là in-memory database. Persistence là cách ghi state xuống disk:

| Mode | Ý nghĩa | Trade-off |
|---|---|---|
| RDB | Snapshot theo thời điểm | Nhanh, file gọn, có thể mất dữ liệu từ snapshot cuối |
| AOF | Append command log | Durability tốt hơn, file lớn hơn, có rewrite overhead |
| No persistence | Cache thuần | Nhanh, mất data khi restart |

Với Kubernetes, persistence còn phụ thuộc PVC, storage latency, disk full và restart behavior.

### Memory và eviction

Redis giữ data trong memory. Kubernetes `memory limit` và Redis `maxmemory` phải được thiết kế cùng nhau.

Nếu Redis vượt container memory limit, kubelet có thể kill container với `OOMKilled`. Nếu Redis có `maxmemory` và `maxmemory-policy`, Redis có thể evict key trước khi bị OOM.

Luôn đặt:

- Redis `maxmemory` thấp hơn container memory limit.
- Eviction policy phù hợp use case.
- Alerts cho memory usage, evicted keys và rejected connections.

### Probes

`PING` chỉ chứng minh process trả lời. Với production, readiness có thể cần kiểm tra sâu hơn:

- Instance có phải primary không nếu Service chỉ dành cho write.
- Replication lag có vượt ngưỡng không.
- Loading state sau restart.
- Cluster state `ok` hay `fail`.

Liveness quá hung hăng có thể làm Redis restart trong lúc đang load AOF/RDB lớn.

Trong lab, readiness nên kiểm tra tối thiểu `PING` và `loading:0`. Liveness có thể dùng `PING` với delay dài hơn vì mục tiêu của liveness chỉ là phát hiện process kẹt thật sự, không phải quyết định instance đã sẵn sàng nhận traffic write.

## Operator overview

Redis operators có thể giúp tạo replication, Sentinel, Cluster, failover và config management. Nhưng operator nào cũng cần bạn hiểu:

- Mode Redis đang chạy.
- Client connection model.
- Persistence và backup.
- Resource/memory sizing.
- Failover semantics.
- Upgrade plan.

Với Redis production, managed Redis thường là lựa chọn thực dụng nếu team không cần tự vận hành Redis trong cluster.

## Deep dive: Service load balancing và Redis standalone

Một `Service` Kubernetes load-balance TCP connections tới các endpoints khớp selector. Nếu bạn scale một Redis standalone `StatefulSet` từ 1 lên 2 mà vẫn để cả hai Pod cùng label `app=redis`, Service `redis` sẽ trỏ tới cả `redis-0` và `redis-1`.

Kết quả:

```text
Client -> Service redis
  -> redis-0: has key A
  -> redis-1: does not have key A
```

Với cache thuần, hành vi này đã khó đoán. Với session/state store, nó là lỗi dữ liệu. Muốn nhiều Redis instances an toàn, bạn cần replication/Sentinel/Cluster/operator hoặc routing rõ primary/read replica, không phải chỉ tăng replicas.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điều phù hợp | Caveat |
|---|---|---|
| K3s/k3d lab | Học `StatefulSet`, PVC persistence, Service endpoint behavior | Không chứng minh Redis failover hoặc storage durability production |
| Kubernetes self-managed | Có thể chạy Redis nếu mode, client, memory, backup và failover đã rõ | Team tự chịu Sentinel/Cluster/operator, TLS, upgrades và incidents |
| Managed Kubernetes + self-hosted Redis | Cloud CSI/LB hỗ trợ hạ tầng | Redis HA vẫn là trách nhiệm của team |
| Managed Redis | Provider xử lý phần lớn HA/patching/backup | Cost, cloud coupling, network latency và IAM/security integration |

- K3s local-path đủ để học PVC persistence, không chứng minh Redis production durability.
- Với k3d, Pod restart và PVC behavior là lab tốt, nhưng network/storage không giống production.
- Nếu dùng Longhorn hoặc distributed storage cho Redis, benchmark latency và test failover trước.
- Cache stateless có thể chạy gần app hơn, nhưng stateful Redis cần owner vận hành rõ.

## Trade-offs và Best Practices

### Decision table

| Use case | Recommended mode | Vì sao |
|---|---|---|
| Cache rebuild được, dev/test | Standalone hoặc managed small instance | Đơn giản, RPO có thể bằng 0 nếu cache rebuild được |
| Session store cần survive restart | Managed Redis hoặc Sentinel/operator | Cần persistence và failover predictable |
| Write throughput cao, data chia shard | Redis Cluster hoặc managed cluster | Cần client hỗ trợ cluster và hash slot |
| Team không có Redis on-call | Managed Redis | Giảm operational burden |
| Edge/on-prem không có managed service | Operator/Sentinel/Cluster self-managed | Chỉ khi có runbook, monitoring, backup và failover drill |

### Best Practices

- Nên đặt Redis `maxmemory` thấp hơn container memory limit.
- Nên chọn eviction policy theo use case, không để default mơ hồ.
- Nên test restart, AOF/RDB loading và failover với data thật đại diện.
- Tránh dùng một Service chung cho nhiều Redis standalone độc lập.
- Tránh chỉ dùng `PING` làm bằng chứng production-ready.

## Performance Considerations

Redis thường nghẽn ở memory và network trước CPU:

- `maxmemory` quá gần container limit dẫn tới `OOMKilled` trước khi Redis evict key.
- AOF `appendfsync always` tăng durability nhưng ảnh hưởng latency ghi.
- AOF rewrite cần memory/disk headroom.
- Large keys và slow commands có thể block event loop.
- Client reconnect storm sau Pod restart có thể làm latency spike.

Theo dõi `used_memory`, `mem_fragmentation_ratio`, `evicted_keys`, `rejected_connections`, `instantaneous_ops_per_sec`, latency và AOF write status.

## Debugging Checklist

```bash
kubectl get pod,pvc,svc,endpoints -n <ns> -o wide
kubectl describe pod redis-0 -n <ns>
kubectl logs redis-0 -n <ns> --tail=100
kubectl exec -n <ns> redis-client -- redis-cli -h redis PING
kubectl exec -n <ns> redis-client -- redis-cli -h redis INFO memory
kubectl exec -n <ns> redis-client -- redis-cli -h redis INFO persistence
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

Nếu dữ liệu "lúc có lúc không", kiểm tra endpoints của Service trước khi debug Redis internals. Có thể client đang bị route tới nhiều standalone instances khác nhau.

## Liên hệ với kiến thức đã biết

Redis trong microservices thường là cache/session/rate-limit/queue dependency. Những quyết định quen thuộc như eviction, TTL, client retry, idempotency và cache rebuild vẫn quan trọng. Kubernetes thêm lifecycle, endpoints, memory limit và PVC behavior vào failure surface.

## Tóm tắt

Redis trong Kubernetes dễ chạy ở lab nhưng dễ hiểu sai ở production. Bạn cần bắt đầu từ use case, chọn đúng mode, đặt memory/eviction rõ ràng, hiểu persistence và test failover. Kubernetes giúp giữ Pod và volume, còn Redis HA là bài toán Redis-level.

## Câu hỏi tự kiểm tra

1. Vì sao một Service trỏ vào nhiều Redis standalone có thể trả dữ liệu không nhất quán?
2. Readiness Redis production nên kiểm tra gì ngoài `PING`?
3. Khi nào chọn Sentinel thay vì Cluster?
4. Vì sao Redis `maxmemory` nên nhỏ hơn container memory limit?
5. Managed Redis giảm được rủi ro nào và không giảm được rủi ro nào?

## Production checklist

- [ ] Use case Redis là cache, session, queue hay state store đã được phân loại.
- [ ] Mode standalone/Sentinel/Cluster được chọn có lý do.
- [ ] Client library hỗ trợ mode đã chọn.
- [ ] `maxmemory` và container memory limit được tính toán.
- [ ] Eviction policy phù hợp.
- [ ] Persistence RDB/AOF được cấu hình theo RPO.
- [ ] Backup/restore được test nếu data cần giữ.
- [ ] Failover drill đã chạy.
- [ ] Monitoring có memory, connected clients, latency, evictions, replication lag.
- [ ] NetworkPolicy/auth/TLS được xem xét.

## Anti-patterns

- Scale StatefulSet Redis lên 3 Pod rồi gọi là Cluster.
- Dùng Redis làm durable queue nhưng không cấu hình persistence/backup.
- Không đặt `maxmemory`, để container bị OOMKilled.
- Chỉ test `PING` rồi kết luận Redis healthy.
- Client không hỗ trợ Sentinel/Cluster nhưng lại deploy Sentinel/Cluster.
- Dùng PVC để "đảm bảo không mất dữ liệu" mà chưa test crash/restore.

## Tài liệu tham khảo

- Redis documentation: Persistence.
- Redis documentation: Replication, Sentinel and Cluster.
- Kubernetes documentation: StatefulSets.
- Kubernetes documentation: Services.
