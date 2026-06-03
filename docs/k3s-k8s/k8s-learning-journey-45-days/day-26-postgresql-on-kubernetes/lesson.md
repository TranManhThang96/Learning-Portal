# Day 26: PostgreSQL on Kubernetes

## Mục tiêu bài học

- Deploy được PostgreSQL dạng lab bằng `StatefulSet`, `Service`, `Secret` và `PVC`.
- Hiểu vì sao PostgreSQL cần stable identity, durable storage, backup/restore và operational runbook rõ ràng.
- Phân biệt lab single-primary với production database có HA, PITR, monitoring và upgrade plan.
- Biết vai trò của PostgreSQL operators như CloudNativePG và Zalando Postgres Operator.
- Biết khi nào nên chọn managed database thay vì tự vận hành PostgreSQL trong Kubernetes.

## Vấn đề cần giải quyết

Kubernetes rất tốt trong việc chạy và reconcile containers, nhưng database không chỉ là process. PostgreSQL còn có:

- Data directory cần bền vững qua Pod restart.
- WAL, checkpoint, fsync, vacuum và replication lag.
- Backup, restore, PITR và retention.
- Upgrade minor/major version.
- Failover, fencing và split-brain risk.
- Performance phụ thuộc storage latency nhiều hơn web service.

Vì vậy câu hỏi đúng không phải là "có chạy được PostgreSQL trên Kubernetes không", mà là "team có đủ năng lực vận hành PostgreSQL và storage backend này trong failure thật không".

## Mental Model

```text
Client
  |
  v
Service postgres:5432
  |
  v
StatefulSet postgres
  |
  +-- Pod postgres-0
        |
        +-- PVC postgres-data-postgres-0
              |
              +-- PV / Storage backend

Backup path:
PostgreSQL data + WAL -> backup job/operator -> off-cluster object storage
```

`StatefulSet` giúp Pod có identity ổn định. `PVC` giúp data tồn tại qua Pod replacement. Nhưng chúng không tự động tạo HA, backup đúng, restore đúng hoặc failover an toàn.

## Lý thuyết cốt lõi

### PostgreSQL cần gì từ Kubernetes?

Một deployment PostgreSQL tối thiểu cần:

- `Secret` cho username/password.
- `Service` cho endpoint ổn định.
- `StatefulSet` cho stable Pod name và ordered lifecycle.
- `PersistentVolumeClaim` cho data directory.
- `readinessProbe` để chỉ nhận traffic khi PostgreSQL trả lời.
- `resources` đủ rõ để tránh memory pressure bất ngờ.

Production cần thêm:

- Backup off-cluster và restore drill.
- WAL archiving/PITR.
- Replication/failover hoặc managed HA.
- Monitoring PostgreSQL và storage latency.
- Security baseline: TLS, auth, NetworkPolicy, secret rotation.
- Upgrade, maintenance window và rollback plan.

### StatefulSet không đồng nghĩa HA

Một `StatefulSet` replicas `1` chỉ cho bạn một Pod có identity ổn định. Nếu Pod chết, Kubernetes có thể tạo lại Pod mới với cùng PVC. Điều này tốt cho restart recovery, nhưng không phải high availability.

Nếu scale PostgreSQL StatefulSet từ 1 lên 2 mà không cấu hình replication, bạn sẽ có hai instance độc lập, mỗi instance có data directory riêng. Đó không phải primary/replica.

HA PostgreSQL cần replication, leader election, failover, fencing, client routing và restore story. Đây là lý do operator tồn tại.

### Storage là dependency quan trọng nhất

PostgreSQL nhạy với:

- fsync latency.
- random write I/O.
- network latency nếu dùng distributed storage.
- disk full hoặc inode full.
- attach/detach delay khi Pod chuyển node.
- snapshot consistency.

PVC `Bound` chỉ chứng minh volume được cấp phát. Nó không chứng minh latency đủ tốt cho database.

### Backup và restore

Backup chỉ có giá trị khi restore được. Với PostgreSQL có hai nhóm chính:

- Logical backup: `pg_dump`, dễ hiểu, phù hợp database nhỏ hoặc export selective.
- Physical backup + WAL archive: dùng cho PITR, phù hợp production hơn nhưng vận hành phức tạp.

Snapshot PVC có thể hữu ích, nhưng không thay thế backup database-aware nếu bạn chưa hiểu consistency, WAL và restore procedure.

### Operator overview

PostgreSQL operator reconcile custom resources thành cụm database có lifecycle hoàn chỉnh hơn.

CloudNativePG thường tập trung vào Kubernetes-native operations cho PostgreSQL: cluster CR, bootstrap, backup, recovery, replica, failover và rolling maintenance.

Zalando Postgres Operator là operator lâu đời trong hệ sinh thái PostgreSQL on Kubernetes, thường đi cùng Patroni để quản lý HA/failover.

Crunchy Postgres Operator cũng là lựa chọn phổ biến trong môi trường enterprise.

Điểm cần nhớ: operator giảm phần tự viết automation, nhưng không xóa trách nhiệm hiểu PostgreSQL, backup, storage và failure modes.

### Connection pooling và PgBouncer

PostgreSQL tạo process/backend riêng cho mỗi connection. Trong microservices, autoscaling hoặc restart hàng loạt có thể tạo connection storm: hàng trăm Pod cùng mở connection mới, làm PostgreSQL tốn CPU/memory cho connection management thay vì query.

PgBouncer thường được đặt giữa app và PostgreSQL để pool connection:

```text
App Pods -> Service pgbouncer:6432 -> PgBouncer -> Service postgres:5432 -> PostgreSQL primary
```

Trade-off chính:

- Pooling giảm connection count và latency tạo connection mới.
- `transaction` pooling phù hợp nhiều API stateless, nhưng không dùng được với session state như prepared statements/session variables nếu app chưa tương thích.
- PgBouncer không thay thế HA/failover. Sau failover, routing từ PgBouncer tới primary mới vẫn phải được operator/proxy/config xử lý đúng.

### Managed database vs self-hosted

Nên nghiêng về managed PostgreSQL khi:

- Database là critical production dependency.
- Team chưa có năng lực DBA/operations 24/7.
- Cần backup, PITR, patching và HA đã được vận hành ổn định.
- Workload yêu cầu SLA rõ.

Tự chạy trên Kubernetes hợp lý hơn khi:

- Lab, dev, test, ephemeral environment.
- Edge/on-prem không có managed service phù hợp.
- Team có năng lực vận hành PostgreSQL và Kubernetes storage.
- Có lý do platform rõ, không chỉ vì "mọi thứ đều chạy trong cluster".

## Deep dive: Cách hoạt động bên trong

Một request database trong Kubernetes đi qua nhiều lớp trước khi PostgreSQL thực thi query:

```text
App connection pool
  -> Service DNS
  -> kube-proxy/CNI routing
  -> PostgreSQL Pod readiness
  -> PostgreSQL backend process
  -> buffer cache/WAL/checkpoint
  -> PVC/storage backend
```

Khi latency tăng, đừng chỉ nhìn Pod `Running`. Hãy tách nguyên nhân theo lớp:

- Connection acquisition chậm: pool cạn, connection storm, PgBouncer không đủ capacity.
- Query chậm: lock wait, missing index, autovacuum, bad plan.
- Write chậm: fsync/checkpoint/WAL archive/storage latency.
- Kubernetes chậm: Pod restart, PVC attach/detach, node pressure, NetworkPolicy hoặc Service endpoint sai.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điều phù hợp | Điều không nên suy luận |
|---|---|---|
| K3s/k3d lab | Học `StatefulSet`, `PVC`, Service DNS, restart recovery | Không chứng minh HA, latency, PITR hoặc node failure thật |
| Kubernetes self-managed | Có thể chạy PostgreSQL nếu storage/backup/operator/runbook đủ chín | Team vẫn tự chịu DBA, failover, upgrade, backup và on-call |
| EKS/GKE/AKS | Control plane, cloud CSI, cloud LB được provider hỗ trợ | PostgreSQL trong cluster vẫn là trách nhiệm của team nếu không dùng managed DB |
| Managed PostgreSQL | Provider xử lý nhiều phần HA, backup, patching, PITR | Vẫn cần schema migration, connection pooling, monitoring app-side và cost control |

K3s local-path phù hợp lab nhưng không phải distributed HA storage. Với k3d, storage nằm trong Docker node containers nên chỉ dùng để học object model. Longhorn có thể dùng cho homelab/edge, nhưng vẫn cần benchmark và backup off-cluster.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi chọn | Rủi ro chính |
|---|---|---|
| Plain `StatefulSet` | Lab/dev/test, học persistence | Không có HA/failover/backup automation |
| PostgreSQL operator | Self-managed production có team vận hành | Phải hiểu CRD, backup, recovery, storage và upgrade của operator |
| Managed PostgreSQL | Production critical, cần SLA/RPO/RTO rõ | Cost, cloud coupling, network/IAM integration |
| PgBouncer | Nhiều app Pod, connection churn cao | Cần chọn pooling mode tương thích app |

### Best Practices

- Nên có restore drill trước khi tin backup.
- Nên đặt PgBouncer hoặc app-side pool limit cho microservices có autoscaling.
- Nên benchmark storage bằng workload gần thực tế, không chỉ kiểm tra PVC `Bound`.
- Tránh scale PostgreSQL `StatefulSet` thủ công rồi gọi đó là replication.
- Tránh để migration chạy tự do từ nhiều Pod trong lúc rollout.

## Performance Considerations

PostgreSQL trên Kubernetes thường nghẽn ở:

- Connection count: mỗi connection tốn memory/process; dùng app pool và PgBouncer để giới hạn.
- Disk write latency: WAL/fsync/checkpoint rất nhạy với storage backend.
- Checkpoint/autovacuum: có thể tạo burst I/O và latency spike.
- PVC attach/detach: Pod chuyển node có thể mất thời gian trước khi database lên lại.
- Memory pressure: OOMKilled database có thể kéo theo crash recovery dài.

Sizing tối thiểu phải tính `shared_buffers`, `work_mem`, `max_connections`, checkpoint/WAL volume, storage IOPS và headroom cho restore/reindex/migration.

## Debugging Checklist

### Pod CrashLoopBackOff

Nguyên nhân có thể là:

- Secret/env thiếu hoặc sai.
- Data directory permission lỗi.
- PVC mount được nhưng filesystem không writable.
- PostgreSQL version không tương thích data directory cũ.
- Disk full hoặc WAL đầy.

### App timeout tới database

Kiểm tra theo lớp:

```text
Service DNS -> Service endpoints -> Pod readiness -> PostgreSQL process -> auth -> query latency
```

DNS resolve không chứng minh PostgreSQL sẵn sàng nhận query.

### Data mất sau restart

Thường do:

- Dùng `emptyDir` thay vì PVC.
- Mount sai path, PostgreSQL ghi data vào filesystem container.
- Reclaim policy/storage cleanup xóa PV.
- Restore nhầm database/namespace.

### Failover giả

Một số lab chỉ delete Pod rồi thấy Pod tạo lại và kết luận "HA". Đó chỉ là restart recovery. HA phải chứng minh client được route sang primary mới, data không mất, không có split-brain, replication lag trong ngưỡng chấp nhận và restore vẫn chạy được.

Checklist command:

```bash
kubectl get pod,pvc,svc,endpoints -n <ns> -o wide
kubectl describe pod postgres-0 -n <ns>
kubectl logs postgres-0 -n <ns> --previous
kubectl exec -n <ns> pg-client -- pg_isready -h postgres -U app -d appdb
kubectl exec -n <ns> pg-client -- psql -h postgres -U app -d appdb -c "SELECT count(*) FROM pg_stat_activity;"
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

## Liên hệ với kiến thức đã biết

Với microservices, PostgreSQL thường là shared dependency có blast radius lớn hơn một service stateless. Các quyết định quen thuộc như connection pool, migration, index, transaction isolation và backup vẫn giữ nguyên. Kubernetes chỉ thêm các lớp mới: Pod lifecycle, Service routing, PVC lifecycle, node failure và operator reconciliation.

## Tóm tắt

PostgreSQL chạy được trên Kubernetes, nhưng production PostgreSQL là bài toán database operations trước khi là bài toán YAML. Kubernetes cung cấp scheduling, identity và volume attachment. Data safety, backup, restore, failover, performance và upgrade vẫn phải được thiết kế nghiêm túc.

## Câu hỏi tự kiểm tra

1. Vì sao `StatefulSet` replicas `2` không tự tạo PostgreSQL primary/replica?
2. PgBouncer giúp gì và không giúp gì trong PostgreSQL HA?
3. PVC `Bound` chứng minh được điều gì và không chứng minh được điều gì?
4. `pg_dump` khác physical backup + WAL archive ở điểm nào?
5. Khi nào managed PostgreSQL là lựa chọn tốt hơn self-hosted?

## Production checklist

- [ ] Có owner vận hành PostgreSQL rõ ràng.
- [ ] StorageClass đã được benchmark với workload database.
- [ ] Backup off-cluster có lịch, retention và restore drill.
- [ ] WAL archiving/PITR được test nếu cần RPO thấp.
- [ ] Monitoring có connection count, replication lag, WAL, disk, query latency, checkpoint, vacuum.
- [ ] Alerts có backup age, disk full, high latency, failed replication, Pod restart.
- [ ] Upgrade minor/major version có rehearsal.
- [ ] Secret rotation và TLS có quy trình.
- [ ] Node drain/failover đã được test.
- [ ] Có quyết định rõ managed database hay self-hosted.

## Anti-patterns

- Chạy PostgreSQL production bằng YAML lab single Pod rồi gọi là HA.
- Tin PVC snapshot là backup mà chưa test restore.
- Scale StatefulSet lên nhiều replica nhưng không cấu hình replication.
- Dùng distributed storage latency cao rồi blame PostgreSQL.
- Không pin resource và để database bị eviction/OOM bất ngờ.
- Đặt database production vào cluster không có runbook storage.

## Tài liệu tham khảo

- Kubernetes documentation: StatefulSets.
- Kubernetes documentation: Persistent Volumes.
- CloudNativePG documentation.
- PgBouncer documentation.
- PostgreSQL documentation: Backup and Restore.
