# Day 48: Multi-region, Disaster Recovery, RPO/RTO

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Phân biệt** được High Availability (HA) và Disaster Recovery (DR) — hai khái niệm thường bị nhầm lẫn.
2. **Tính toán** được RPO và RTO cho từng loại data và service trong hệ thống.
3. **Thiết kế** được DR plan hoàn chỉnh cho production platform bao gồm backup, restore, failover.
4. **So sánh** được active-active vs active-passive architecture và biết khi nào dùng gì.
5. **Viết** được restore runbook và DR test plan có thể thực thi được.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Disasters xảy ra — không phải "nếu" mà là "khi nào":

| Loại disaster | Ví dụ thực tế | Downtime |
|--------------|---------------|----------|
| Hardware failure | Disk chết, server chết | Phút → giờ |
| Network failure | Switch chết, fiber đứt | Phút → giờ |
| AZ outage | AWS us-east-1 AZ failure (2023) | Giờ |
| Region outage | AWS us-east-1 full outage (2017) | 4+ giờ |
| Data center fire | OVH Strasbourg fire (2021) | Ngày → tháng |
| Human error | Drop production database | Phút (nếu có backup) |
| Cyber attack | Ransomware encrypt toàn bộ data | Ngày → tuần |

### Hậu quả nếu không có DR plan

Amazon ước tính mỗi phút downtime tốn **$220,000** revenue. Nhưng ngay cả startup nhỏ:
- Mất dữ liệu khách hàng → mất trust
- Downtime kéo dài → khách hàng chuyển sang competitor
- Không có restore procedure → panic, làm sai, tệ hơn

### Liên hệ với developer

DR giống **database transaction rollback ở tầng infrastructure**:
- Transaction log = WAL / backup
- Rollback = restore from backup
- Savepoint = snapshot / checkpoint
- Recovery point = RPO (bao nhiêu data chấp nhận mất)
- Recovery time = RTO (bao lâu để khôi phục)

---

## 3. Kiến thức nền tảng

### High Availability vs Disaster Recovery

```
High Availability (HA):                    Disaster Recovery (DR):
┌─────────────────────────┐                ┌─────────────────────────┐
│ CÙNG region/data center │                │ KHÁC region/data center │
│                         │                │                         │
│ Primary ←──→ Standby    │                │ Region A  ──→  Region B │
│ Auto failover (giây)    │                │ Manual/auto (phút→giờ)  │
│                         │                │                         │
│ Mục tiêu: giảm          │                │ Mục tiêu: survive khi   │
│ downtime cho small      │                │ toàn bộ region/DC chết  │
│ failures                │                │                         │
└─────────────────────────┘                └─────────────────────────┘
```

| Tiêu chí | High Availability | Disaster Recovery |
|----------|------------------|-------------------|
| **Scope** | Component/AZ failure | Region/DC failure |
| **Failover time** | Giây → phút | Phút → giờ |
| **Data location** | Cùng region | Khác region/DC |
| **Automation** | Thường automatic | Có thể manual |
| **Cost** | Moderate (2x) | High (2-3x+) |
| **Testing** | Continuous | Periodic (quarterly) |
| **Example** | K8s pod restart, DB replica promote | Activate DR site |

### RPO và RTO

```
         Disaster        Recovery
            │              point
            ▼              ▼
──────┬─────┼──────────────┼──────→ time
      │     │              │
      │     │◄────RTO─────►│
      │     │              │
      │◄RPO►│              │
      │     │              │
   Last     │          Service
  backup    │          restored
```

**RPO (Recovery Point Objective)**: Bao nhiêu data chấp nhận mất?
- RPO = 0: không chấp nhận mất bất kỳ transaction nào → synchronous replication
- RPO = 1 giờ: chấp nhận mất tối đa 1 giờ data → hourly backup
- RPO = 24 giờ: chấp nhận mất tối đa 1 ngày data → daily backup

**RTO (Recovery Time Objective)**: Bao lâu để khôi phục service?
- RTO = 0: instant failover → active-active
- RTO = 15 phút: cần automated failover → standby warm
- RTO = 4 giờ: có thể manual restore → cold standby

### RPO/RTO theo loại data

| Data Type | RPO gợi ý | RTO gợi ý | Lý do |
|-----------|----------|----------|-------|
| Financial transactions | 0 | < 5 phút | Mất tiền = lawsuit |
| User data/profiles | < 1 giờ | < 15 phút | Core business data |
| Session data | < 5 phút | < 5 phút | User experience |
| Product catalog | < 4 giờ | < 30 phút | Rebuild from source |
| Analytics/logs | < 24 giờ | < 4 giờ | Non-critical |
| Cache data | N/A (rebuildable) | < 1 phút | Warm up lại |
| Static assets (images) | < 24 giờ | < 1 giờ | CDN cached |

---

## 4. Deep Dive

### DR Architecture Patterns

#### Pattern 1: Backup & Restore (Cold DR)

```mermaid
graph LR
    subgraph "Primary Region (Active)"
        APP1[Application]
        DB1[Database]
        S3_1[Object Storage]
    end
    
    subgraph "DR Region (Cold)"
        INFRA[Infrastructure Code<br/>Terraform/Helm]
    end
    
    subgraph "Cross-region Backup"
        S3_DR[Backup Storage<br/>Cross-region S3]
    end
    
    DB1 -->|backup| S3_1
    S3_1 -->|replicate| S3_DR
    INFRA -.->|deploy when needed| DR_APP[Application]
    S3_DR -.->|restore| DR_DB[Database]
```

- **RTO**: 1-4 giờ (cần provision infrastructure + restore data)
- **RPO**: Phụ thuộc backup frequency (thường 1-24 giờ)
- **Cost**: Thấp nhất (chỉ trả storage cho backups)
- **Phù hợp**: Startup, non-critical systems

#### Pattern 2: Warm Standby (Pilot Light)

```mermaid
graph LR
    subgraph "Primary Region"
        APP1[App Servers<br/>3 instances]
        DB1[Database Primary]
        CACHE1[Redis]
    end
    
    subgraph "DR Region (Warm)"
        APP2[App Server<br/>1 instance minimal]
        DB2[Database Replica<br/>Async replication]
        CACHE2[Redis<br/>Cold]
    end
    
    DB1 -->|async replication| DB2
    
    style APP2 fill:#ffcc00
    style DB2 fill:#ffcc00
    style CACHE2 fill:#ffcc00
```

- **RTO**: 15-60 phút (scale up warm instances)
- **RPO**: Phút (async replication lag)
- **Cost**: Trung bình (minimal infra luôn chạy)
- **Phù hợp**: Mid-size company, business-critical apps

#### Pattern 3: Active-Passive (Hot Standby)

```mermaid
graph LR
    subgraph "Primary Region (Active)"
        LB1[Load Balancer]
        APP1[App Servers<br/>Full capacity]
        DB1[Database Primary<br/>Read/Write]
    end
    
    subgraph "DR Region (Passive)"
        LB2[Load Balancer<br/>Ready]
        APP2[App Servers<br/>Full capacity]
        DB2[Database Replica<br/>Read-only]
    end
    
    DNS[DNS<br/>Route 53 / CloudFlare]
    
    DNS -->|active| LB1
    DNS -.->|failover| LB2
    DB1 -->|sync/async replication| DB2
    LB1 --> APP1
    LB2 --> APP2
    APP1 --> DB1
    APP2 --> DB2
```

- **RTO**: 1-15 phút (DNS failover + promote DB)
- **RPO**: Giây (near-synchronous replication)
- **Cost**: Cao (2x infrastructure)
- **Phù hợp**: Enterprise, financial services, SLA > 99.95%

#### Pattern 4: Active-Active (Multi-region)

```mermaid
graph TB
    GSLB[Global Load Balancer<br/>GeoDNS]
    
    subgraph "Region A (US-East)"
        LBA[Load Balancer]
        APPA[App Servers]
        DBA[Database<br/>Read/Write]
    end
    
    subgraph "Region B (EU-West)"
        LBB[Load Balancer]
        APPB[App Servers]
        DBB[Database<br/>Read/Write]
    end
    
    GSLB -->|US users| LBA
    GSLB -->|EU users| LBB
    LBA --> APPA --> DBA
    LBB --> APPB --> DBB
    DBA <-->|bi-directional<br/>replication| DBB
```

- **RTO**: ~0 (traffic tự động route sang region còn lại)
- **RPO**: ~0 (bi-directional replication) hoặc conflict resolution
- **Cost**: Rất cao (2x+ infrastructure + complexity)
- **Phù hợp**: Global services, ultra-high availability
- **Thách thức**: Data consistency, conflict resolution, schema migration

### DNS Failover

```mermaid
sequenceDiagram
    participant User
    participant DNS as DNS (Route 53)
    participant HC as Health Check
    participant RegA as Region A
    participant RegB as Region B
    
    Note over HC: Normal operation
    HC->>RegA: Health check ✅
    HC->>RegB: Health check ✅
    User->>DNS: Resolve api.example.com
    DNS->>User: Return Region A IP (primary)
    User->>RegA: Request
    RegA->>User: Response ✅
    
    Note over RegA: Region A fails!
    HC->>RegA: Health check ❌
    HC->>RegA: Health check ❌ (confirm)
    HC->>DNS: Region A unhealthy
    
    Note over DNS: DNS failover triggered
    User->>DNS: Resolve api.example.com
    DNS->>User: Return Region B IP (DR)
    User->>RegB: Request
    RegB->>User: Response ✅
```

**DNS TTL considerations**:
- TTL quá cao (3600s) → users vẫn gọi region chết trong 1 giờ
- TTL quá thấp (30s) → DNS query volume tăng, latency tăng
- **Recommended**: 60-300s cho production with failover

### Data Consistency Trade-offs

```
CAP Theorem trong multi-region:

Consistency ←──────→ Availability
     │                      │
     │    Pick 2 of 3       │
     │                      │
     └──────────────────────┘
              │
         Partition
         Tolerance
         (luôn cần)

Synchronous replication:
+ Strong consistency (RPO = 0)
- High latency (cross-region RTT: 50-200ms per write)
- Availability giảm (nếu DR region unreachable → writes block)

Asynchronous replication:
+ Low latency (writes không chờ DR)
+ High availability
- Eventual consistency (RPO > 0, có thể mất vài giây data)

Recommendation:
- Financial data: synchronous (chấp nhận latency penalty)
- User data: async với RPO < 1 phút
- Analytics: async với RPO < 1 giờ
```

---

## 5. Trade-offs & Best Practices ⭐

### DR Strategy theo Company Size

#### Startup (< $10K/month infra)

**Recommendation: Backup & Restore (Cold DR)**

```
Strategy:
- Daily backup database to cross-region S3
- Infrastructure as Code (Terraform) cho rebuild
- Manual restore procedure documented
- DR test: quarterly

Cost: ~$50-200/month extra (S3 cross-region)
RTO: 2-4 giờ
RPO: Up to 24 giờ

Đủ vì:
- Downtime vài giờ chấp nhận được ở giai đoạn early
- Cost optimization quan trọng hơn ultra-high availability
- Team nhỏ, process đơn giản
```

#### Mid-size ($10K-100K/month infra)

**Recommendation: Warm Standby**

```
Strategy:
- Database async replication to DR region
- Minimal infrastructure always running in DR
- Automated scaling scripts cho DR activation
- DR test: monthly

Cost: ~$2K-10K/month extra
RTO: 15-60 phút
RPO: < 5 phút

Hợp lý vì:
- Business impact of downtime significant
- Can afford 10-20% extra for DR
- Automated failover giảm human error risk
```

#### Enterprise ($100K+/month infra)

**Recommendation: Active-Passive hoặc Active-Active**

```
Strategy:
- Full infrastructure in DR region
- Near-synchronous database replication
- Automated DNS failover
- DR test: monthly (automated)
- Game days: quarterly chaos engineering

Cost: 50-100% extra ($50K-100K+/month)
RTO: 1-15 phút
RPO: < 1 phút

Cần vì:
- SLA contractual obligations
- Regulatory requirements (finance, healthcare)
- Revenue impact > $10K/phút downtime
```

### Best Practices

```
✅ Test DR plan ít nhất quarterly — plan chưa test = không có plan
✅ Automate DR activation càng nhiều càng tốt
✅ Document restore procedures step-by-step (không giả định expertise)
✅ Backup đến region/account khác (same-region backup ≠ DR)
✅ DNS TTL < 300s cho services cần failover
✅ Database: backup + replication (backup cho RPO, replication cho RTO)
✅ IaC cho DR region (rebuild nhanh, consistent)
✅ Communication plan: ai thông báo gì cho ai khi DR activate

❌ KHÔNG chỉ backup mà không test restore
❌ KHÔNG đặt DR cùng region với primary (defeats the purpose)
❌ KHÔNG synchronous replication cross-region cho non-critical data
❌ KHÔNG DR test lần đầu khi xảy ra disaster thật
❌ KHÔNG quên application state (sessions, caches, queues)
```

### Anti-patterns

1. **"Backup là đủ"**: Backup ≠ DR. Backup chỉ giải quyết data loss, không giải quyết infrastructure failure.
2. **"Cloud provider không bao giờ down"**: AWS us-east-1 đã down nhiều lần. Single-region ≠ HA.
3. **"DR test lần sau"**: Luôn bị defer → đến khi cần thì procedure đã outdated.
4. **"Sync replication everywhere"**: Cross-region sync replication gây latency penalty cho MỌI write → chỉ dùng cho critical data.
5. **"DNS failover đủ nhanh"**: DNS TTL + client cache + propagation → có thể mất 5-15 phút.

---

## 6. Performance & Scalability ⭐

### Cross-region Latency

```
Region pair                    RTT (round-trip)
us-east-1 ↔ us-west-2         ~60-80ms
us-east-1 ↔ eu-west-1         ~80-100ms
us-east-1 ↔ ap-southeast-1    ~200-250ms
eu-west-1 ↔ ap-southeast-1    ~150-200ms
Same AZ                       ~0.5-1ms
Cross AZ (same region)        ~1-3ms
```

### Impact lên Write Performance

```
Synchronous replication cross-region:
- Write latency += cross-region RTT
- us-east → eu-west: mỗi write +80-100ms
- 1000 TPS writes → mỗi write chờ 100ms → cần 100 concurrent connections

Asynchronous replication:
- Write latency: không ảnh hưởng
- Replication lag: typically 1-5 seconds cross-region
- Risk: mất vài seconds data nếu primary region fail
```

### Scaling Multi-region

```
Read scaling (dễ):
- Read replicas ở mỗi region
- GeoDNS route users đến nearest region
- Consistent reads: read from primary region
- Eventually consistent reads: read from local replica

Write scaling (khó):
- Single-writer: tất cả writes đến primary region
  + Simple, no conflicts
  - Write latency cao cho users xa primary
  
- Multi-writer: writes ở bất kỳ region
  + Low write latency cho mọi users
  - Conflict resolution cực kỳ phức tạp
  - Last-write-wins → data loss risk
  - Application-level conflict resolution
```

### Bottlenecks

1. **DNS propagation**: TTL-based, 60-300s delay
2. **Database replication lag**: Async = seconds, sync = latency
3. **Cache warming**: DR region cache cold → first requests slow
4. **Connection draining**: Active connections to old region timeout
5. **Message queue replay**: Messages in-flight khi failover → duplicate processing

---

## 7. Security & Reliability Considerations

### Security trong DR

- **Backup encryption**: AES-256 at rest, TLS in transit
- **Cross-account backup**: Backup ở AWS account riêng (ransomware protection)
- **Access control**: DR activation chỉ authorized personnel
- **Secrets sync**: DR region phải có access đến secrets (Vault replication)
- **Network security**: DR region có cùng NetworkPolicy, security groups
- **Compliance**: DR region phải satisfy cùng compliance requirements

### Reliability

- **Split brain prevention**: Chỉ 1 region active write tại mỗi thời điểm
- **Data integrity verification**: Checksum sau restore
- **Gradual failback**: Không switch traffic 100% ngay khi primary recovered
- **Runbook maintenance**: Update sau mỗi infra change
- **DR test frequency**: Minimum quarterly, ideally monthly

---

## 8. Hands-on Example

### Thiết kế DR Plan cho E-commerce Platform

#### Scenario

E-commerce platform "ShopFast" với:
- 5 microservices: Web, API, Order, Payment, Notification
- PostgreSQL primary database (orders, users, products)
- Redis cache
- Kafka message queue
- S3 for product images
- Primary region: us-east-1

#### Bước 1: Phân loại data theo criticality

```
┌───────────────────────────────────────────────────────┐
│                   Data Classification                  │
├──────────────────┬──────────┬──────────┬───────────────┤
│ Data             │ RPO      │ RTO      │ Strategy      │
├──────────────────┼──────────┼──────────┼───────────────┤
│ Orders/Payments  │ 0        │ 5 min    │ Sync replica  │
│ User accounts    │ 1 min    │ 15 min   │ Async replica │
│ Product catalog  │ 1 hour   │ 30 min   │ Async replica │
│ Sessions/cache   │ N/A      │ 1 min    │ Rebuild       │
│ Product images   │ 24 hours │ 1 hour   │ S3 cross-reg  │
│ Analytics logs   │ 24 hours │ 4 hours  │ Daily backup  │
│ Kafka messages   │ 5 min    │ 15 min   │ MirrorMaker   │
└──────────────────┴──────────┴──────────┴───────────────┘
```

#### Bước 2: Architecture Design

```yaml
# DR Architecture — Warm Standby

primary_region: us-east-1
dr_region: us-west-2

components:
  database:
    primary: 
      type: CloudNativePG
      instances: 3 (1 primary + 2 replicas)
      region: us-east-1
    dr:
      type: CloudNativePG
      instances: 1 (standby, async streaming replication)
      region: us-west-2
      replication_lag_target: < 30s
  
  redis:
    strategy: no-replication
    dr_action: cold start, warm cache from DB
    rto: 5 minutes
  
  kafka:
    strategy: MirrorMaker 2.0
    replication: async
    rpo: ~1 minute
  
  object_storage:
    strategy: S3 Cross-Region Replication
    rpo: ~15 minutes
  
  application:
    primary: 3 replicas per service
    dr: 1 replica per service (scale up on activation)
  
  dns:
    provider: Route 53
    ttl: 60s
    failover: health-check based
```

#### Bước 3: Restore Runbook

```markdown
# ShopFast DR Activation Runbook

## Trigger Conditions
- Primary region unreachable > 5 minutes
- Multiple AZ failures in primary region
- Confirmed by 2+ team members

## Pre-activation Checklist
- [ ] Confirm primary region truly down (not just monitoring)
- [ ] Notify stakeholders (Slack #incident channel)
- [ ] Open incident ticket
- [ ] Confirm DR region health

## Activation Steps

### Step 1: Database (RTO target: 5 min)
1. Check replication lag:
   kubectl exec pg-dr-1 -n database -- psql -U postgres -c \
     "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();"
2. Promote DR replica to primary:
   kubectl cnpg promote pg-dr -n database
3. Verify writes working:
   kubectl exec pg-dr-1 -n database -- psql -U postgres -d orders -c \
     "INSERT INTO health_check (ts) VALUES (NOW()) RETURNING *;"
4. Scale to 3 instances:
   kubectl patch cluster pg-dr -n database --type merge \
     -p '{"spec":{"instances":3}}'

### Step 2: Application (RTO target: 10 min)
1. Scale up applications:
   for svc in web api order payment notification; do
     kubectl scale deploy/$svc -n production --replicas=3
   done
2. Update database connection strings (if needed):
   kubectl set env deploy/api DATABASE_URL=postgresql://...@pg-dr-rw:5432/orders
3. Verify health checks:
   for svc in web api order payment notification; do
     kubectl exec deploy/$svc -n production -- curl -s http://localhost:8080/health
   done

### Step 3: DNS Failover (RTO target: 2 min)
1. Route 53 health check sẽ tự động failover (nếu configured)
2. Nếu manual: update DNS record:
   aws route53 change-resource-record-sets --hosted-zone-id ZXXXXX \
     --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"api.shopfast.com","Type":"A","AliasTarget":{"HostedZoneId":"Z1H1FL5HABSF5","DNSName":"dr-lb.us-west-2.elb.amazonaws.com","EvaluateTargetHealth":true}}}]}'
3. Verify DNS propagation:
   dig api.shopfast.com +short
   # Should return DR region IP

### Step 4: Verification (5 min)
1. End-to-end test: place test order
2. Check error rates in monitoring
3. Verify Kafka consumers catching up
4. Check cache warming progress

## Post-activation
- [ ] Update status page
- [ ] Continue monitoring for 30 minutes
- [ ] Schedule failback plan
- [ ] Begin incident postmortem
```

#### Bước 4: DR Test Script

```bash
#!/bin/bash
# dr-test.sh — Quarterly DR Test

set -euo pipefail

echo "=== DR Test Started: $(date) ==="

# Step 1: Record current state
echo "Recording primary state..."
PRIMARY_ORDER_COUNT=$(kubectl exec deploy/api -n production -- \
  curl -s http://localhost:8080/api/orders/count)
echo "Orders in primary: $PRIMARY_ORDER_COUNT"

# Step 2: Verify backup/replication current
echo "Checking replication lag..."
LAG=$(kubectl exec pg-dr-1 -n database -- psql -U postgres -t -c \
  "SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp()))::int;")
echo "Replication lag: ${LAG}s"

if [ "$LAG" -gt 60 ]; then
  echo "ERROR: Replication lag > 60s. Aborting test."
  exit 1
fi

# Step 3: Simulate failover (in staging/test namespace)
echo "Simulating failover..."
kubectl cnpg promote pg-dr-test -n dr-test

# Step 4: Verify DR database
echo "Verifying DR database..."
DR_ORDER_COUNT=$(kubectl exec pg-dr-test-1 -n dr-test -- psql -U postgres -t -d orders -c \
  "SELECT count(*) FROM orders;")
echo "Orders in DR: $DR_ORDER_COUNT"

# Step 5: Compare
DIFF=$((PRIMARY_ORDER_COUNT - DR_ORDER_COUNT))
echo "Data difference: $DIFF orders"

if [ "$DIFF" -le 10 ]; then
  echo "✅ DR Test PASSED — data loss within acceptable RPO"
else
  echo "❌ DR Test FAILED — data loss $DIFF orders exceeds RPO"
  exit 1
fi

# Step 6: Cleanup (restore DR to replica mode)
echo "Cleaning up test environment..."
kubectl delete namespace dr-test
echo "=== DR Test Completed: $(date) ==="
```

#### Bước 5: Local verification cho DR plan artifact

Nếu chưa có cluster hoặc cloud account, vẫn phải verify rằng plan có đủ RPO/RTO, restore steps, và test evidence.

```bash
mkdir -p dr-plan-lab

cat > dr-plan-lab/rpo-rto.csv <<'EOF'
component,rpo,rto,strategy
orders-payments,0-1m,5m,sync-or-near-sync-replication
users,1m,15m,async-replica
product-catalog,1h,30m,async-replica
redis-cache,n/a,5m,rebuild-from-db
kafka,5m,15m,mirrormaker
EOF

cat > dr-plan-lab/restore-runbook.md <<'EOF'
# Restore Runbook

1. Confirm incident trigger and assign incident commander.
2. Verify backup or replica freshness.
3. Promote DR database or restore from backup.
4. Scale application workloads in DR region.
5. Switch DNS or load balancer routing.
6. Run smoke test and compare data counts.
7. Record RPO/RTO actuals.
EOF

printf "components=%s\nsteps=%s\n" \
  "$(tail -n +2 dr-plan-lab/rpo-rto.csv | wc -l | tr -d ' ')" \
  "$(grep -c '^[0-9]\.' dr-plan-lab/restore-runbook.md)"
```

**Expected output**:

```text
components=5
steps=7
```

**Verify**:

```bash
grep -q 'orders-payments' dr-plan-lab/rpo-rto.csv
grep -q 'Record RPO/RTO actuals' dr-plan-lab/restore-runbook.md
```

**Cleanup**:

```bash
rm -rf dr-plan-lab
# Nếu deploy lên kind: kind delete cluster --name dr-lab
```

---

## 9. Common Pitfalls & Debugging

### Lỗi thường gặp

| Lỗi | Triệu chứng | Nguyên nhân | Fix |
|------|-------------|-------------|-----|
| DNS propagation delay | Users vẫn gọi dead region | TTL cao, client DNS cache | TTL 60s, application-level retry |
| Split brain | 2 regions accept writes | Failover không disable primary | Fencing: disable old primary first |
| Cold cache | Latency spike sau failover | DR cache empty | Pre-warm cache, gradual traffic shift |
| Schema mismatch | DR restore fails | Migration chạy ở primary chưa replicate | DR region cùng migration pipeline |
| Stale backup | Restore thất bại | Backup corruption, S3 lifecycle delete | Verify backups, longer retention |

### Production Case Study 1: OVH Data Center Fire (2021)

#### Context
OVH cloud provider, data center SBG2 tại Strasbourg, Pháp. Nhiều khách hàng không có DR plan.

#### Symptom
- 10/03/2021: Cháy lớn phá hủy hoàn toàn SBG2, hư hại SBG1
- 3.6 triệu websites down
- Nhiều khách hàng mất data vĩnh viễn

#### Root Cause
- Data center fire destroy physical servers
- Nhiều khách hàng chỉ có backup trong cùng data center
- Backup cùng bị cháy → **total data loss**

#### Lesson Learned
```
1. Backup PHẢI ở location khác (cross-region minimum)
2. "Cloud" không có nghĩa là "safe" — physical disasters vẫn xảy ra
3. SLA ≠ data protection — SLA chỉ refund tiền, không refund data
4. DR plan phải bao gồm physical disaster scenario
```

### Production Case Study 2: AWS us-east-1 Outage (2023)

#### Context
Major AWS outage ảnh hưởng Lambda, DynamoDB, S3 API tại us-east-1.

#### Symptom
- Hundreds of services dependent on us-east-1 down
- Companies without multi-region: complete outage
- Companies with DR: activated failover within minutes

#### Impact Analysis
```
Companies without DR:
- Downtime: 4+ hours
- Revenue loss: estimated millions
- Customer trust: damaged

Companies with active-passive DR:
- Downtime: 15-30 minutes (failover time)
- Revenue loss: minimal
- Customer trust: maintained ("we handled it")

Companies with active-active:
- Downtime: < 5 minutes (automatic)
- Revenue loss: negligible
```

#### Lesson Learned
```
1. us-east-1 là region phổ biến nhất → outage ảnh hưởng nhiều nhất
2. Global services (IAM, Route 53) cũng bị ảnh hưởng
3. DR plan phải include "AWS global services down" scenario
4. Multi-region ≠ multi-AZ — AZ failure và region failure là 2 level khác nhau
```

### Production Case Study 3: GitLab Database Deletion (2017)

#### Context
GitLab.com, PostgreSQL database, 310GB production data.

#### Symptom
- Engineer running maintenance accidentally ran `rm -rf` on production database directory
- Not a backup directory — the actual production data

#### Investigation
```
5 backup methods existed, ALL failed:
1. LVM snapshots: not configured correctly
2. Regular pg_dump: not running (silently failed months ago)
3. Azure disk snapshots: not set up
4. Continuous WAL archiving: not configured
5. S3 backup: only contained old backup (6 hours old)
```

#### Fix
- Restored from 6-hour-old S3 backup → lost 6 hours of data
- 300+ merge requests lost, production wikis lost
- Streamed recovery process live on YouTube (transparency)

#### Lesson Learned
```
1. Multiple backup methods doesn't help if NONE are verified
2. Silent backup failures are WORSE than no backup
3. Monitor backup success/failure actively
4. Test restore regularly (not just backup creation)
5. GitLab now tests backup/restore every single day
```

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 47: Database on Kubernetes vs Managed Database

- Database backup strategy từ Day 47 là foundation cho DR
- CloudNativePG WAL archiving → RPO ~0 cho database
- Managed database (RDS) built-in cross-region replicas → simpler DR
- Failover testing procedure từ Day 47 áp dụng cho DR testing

### Bài sau — Day 49: Cost Optimization & FinOps

- DR infrastructure tốn 50-100% extra cost → cost optimization cần balance
- Active-passive vs active-active: cost difference significant
- Spot instances cho DR warm standby (acceptable risk)
- Reserved instances cho DR primary infrastructure

### Kiến thức tái sử dụng

- **Backup concepts** (Day 23): Velero, etcd backup → infrastructure backup for DR
- **Deployment strategies** (Day 35): Blue-green → active-passive pattern liên quan
- **Observability** (Day 38-42): Monitoring DR replication lag, health checks
- **Incident response** (Day 44): DR activation = major incident, cần IC/CommsLead

---

## 11. Tài liệu tham khảo

### Must-read
- [AWS Disaster Recovery Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- [Google SRE Book: Managing Risk](https://sre.google/sre-book/managing-risk/) — RPO/RTO in practice

### Nice-to-have
- [Velero Documentation](https://velero.io/docs/) — Kubernetes backup/restore
- [Route 53 Health Checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-types.html) — DNS failover

### Deep-dive
- **Book**: "Release It!" (Michael Nygard) — stability patterns, failure modes
- **Talk**: [GitLab Database Incident](https://about.gitlab.com/blog/2017/02/10/postmortem-of-database-outage-of-january-31/) — famous postmortem
- **Blog**: [OVH Fire Postmortem Analysis](https://www.datacenterdynamics.com/en/news/ovhcloud-fire-report/) — physical disaster lessons

