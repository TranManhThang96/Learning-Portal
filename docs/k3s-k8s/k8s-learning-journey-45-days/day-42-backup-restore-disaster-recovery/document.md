# Day 42 Document: Backup/Restore Runbook

## Backup layers

```text
Layer 1: Git
  manifests, Helm values, policies

Layer 2: Kubernetes API state
  Namespace, Deployment, Secret, CRD, PVC objects

Layer 3: Persistent data
  PVC snapshots, database backups, Kafka replication

Layer 4: External dependencies
  DNS, IAM, registry, object storage, cloud databases
```

## RPO/RTO worksheet

| Workload | Data type | RPO | RTO | Backup method | Restore owner |
|---|---|---:|---:|---|---|
| api-gateway | Stateless | 0 config loss | 15m | GitOps | Platform |
| order-service | Stateless + DB | 5m | 30m | GitOps + PostgreSQL WAL | App + DBA |
| Redis cache | Cache | 1h hoặc none | 15m | Rebuild/cache warm | App |
| Redis session | Stateful | 5m | 30m | AOF/RDB + replica | App |
| Kafka | Event log | Depends retention | 1h+ | Replication/replay | Platform + App |
| ArgoCD | Deployment state | 15m | 30m | Git + secret backup | Platform |

## Velero commands

Install thường cần provider plugin. Command dưới đây là pattern, cần thay provider theo môi trường:

```bash
velero install \
  --provider <provider> \
  --plugins <plugin-image> \
  --bucket <bucket> \
  --backup-location-config <key=value> \
  --snapshot-location-config <key=value>
```

Backup namespace:

```bash
velero backup create logistics-dev-backup \
  --include-namespaces logistics-dev
```

Backup theo label:

```bash
velero backup create order-service-backup \
  --selector app.kubernetes.io/name=order-service
```

Xem backup:

```bash
velero backup get
velero backup describe logistics-dev-backup --details
velero backup logs logistics-dev-backup
```

Restore:

```bash
velero restore create logistics-dev-restore \
  --from-backup logistics-dev-backup
```

Restore đổi namespace:

```bash
velero restore create logistics-restore-to-test \
  --from-backup logistics-dev-backup \
  --namespace-mappings logistics-dev:logistics-restore
```

## K3s datastore snapshot commands

K3s datastore không luôn là `etcd`:

| K3s install mode | Datastore | Command/backup direction |
|---|---|---|
| Single-server mặc định | SQLite | Filesystem backup của DB K3s theo docs/runbook; không dùng `k3s etcd-snapshot` |
| HA embedded datastore | Embedded `etcd` | `k3s etcd-snapshot save/ls/prune` |
| External datastore | MySQL/PostgreSQL/external etcd | Backup native của datastore đó |

Tạo snapshot thủ công:

```bash
sudo k3s etcd-snapshot save --name pre-upgrade
```

Liệt kê snapshot:

```bash
sudo k3s etcd-snapshot ls
```

Snapshot file thường cần copy ra nơi ngoài node:

```bash
sudo ls -lah /var/lib/rancher/k3s/server/db/snapshots/
```

Restore K3s snapshot là thao tác control plane nhạy cảm. Luôn đọc docs version đang dùng và test trong lab trước khi chạy production.

## PostgreSQL app-level backup mẫu

Logical dump cho lab:

```bash
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U postgres postgres' > logistics-pg-dump.sql
```

Restore vào Pod PostgreSQL lab:

```bash
kubectl cp logistics-pg-dump.sql logistics/postgres-0:/tmp/logistics-pg-dump.sql
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -f /tmp/logistics-pg-dump.sql'
```

Production caveat:

- `pg_dump` phù hợp database nhỏ, restore chọn lọc hoặc migration lab.
- Database lớn cần physical backup, WAL archive và PITR.
- Backup thành công chưa đủ; phải chạy query validation sau restore.
- PVC snapshot có thể crash-consistent, nhưng không thay thế restore drill ở tầng PostgreSQL.

## Restore order gợi ý

```text
1. Dựng cluster hoặc namespace target.
2. Cài CRD/operator cần thiết.
3. Tạo StorageClass/CSI tương thích.
4. Restore Secret/ConfigMap cần cho operator/app.
5. Restore PVC/data hoặc database backup.
6. Restore workload manifests bằng GitOps/Velero.
7. Chạy migration/smoke test.
8. Mở traffic.
9. Ghi lại duration và issue.
```

## CRD/operator restore caveat

Nếu backup có custom resources như:

- `Application` của ArgoCD.
- `Certificate` của cert-manager.
- `IngressRoute` của Traefik.
- `Postgresql` của operator.
- `Kafka` của Strimzi.

Cluster target phải có CRD tương ứng trước, nếu không restore sẽ fail.

## StorageClass migration table

| Source | Target | Vấn đề | Cách xử lý |
|---|---|---|---|
| K3s `local-path` | EKS EBS | Access mode/topology khác | Restore data bằng app-level backup |
| Longhorn | Longhorn cluster mới | Replica/snapshot location | Cấu hình backup target Longhorn |
| EBS gp3 | GKE PD | Snapshot không portable trực tiếp | Dump logical hoặc tool migration |
| NFS RWX | Cloud block RWO | App kỳ vọng RWX | Đổi architecture hoặc dùng cloud file storage |

## Post-restore verification

```bash
kubectl get all -n <namespace>
kubectl get pvc -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl rollout status deploy/<name> -n <namespace>
kubectl logs deploy/<name> -n <namespace> --since=10m
kubectl run curl -n <namespace> --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://<service>
```

App-level checks:

- API health endpoint trả `200`.
- Database schema version đúng.
- Có thể tạo/read/update record test.
- Kafka consumer group không reset offset ngoài ý muốn.
- Redis key/session behavior đúng.

## Backup quality checklist

- [ ] Backup chạy theo lịch và có alert khi fail.
- [ ] Backup lưu ngoài cluster/failure domain.
- [ ] Backup được mã hóa.
- [ ] Access backup bucket hạn chế theo least privilege.
- [ ] Retention rõ: daily/weekly/monthly.
- [ ] Restore drill có log thời gian thực tế.
- [ ] Restore được test trên cluster khác.
- [ ] Có runbook cho namespace restore và cluster rebuild.
- [ ] Có owner cho từng dữ liệu stateful.
- [ ] Có cleanup policy cho backup cũ.
