# Day 48: Bài tập — Multi-region, Disaster Recovery, RPO/RTO

---

## Bài 1: Easy — RPO/RTO Analysis và Data Classification

### Context

Bạn là DevOps engineer tại một startup SaaS cung cấp project management tool. Platform có:
- User service (PostgreSQL): user profiles, authentication
- Project service (PostgreSQL): projects, tasks, comments
- File service (S3): uploaded files, attachments
- Notification service (Redis): push notification queue
- Analytics service (ClickHouse): usage analytics

CTO yêu cầu bạn phân loại data và xác định RPO/RTO cho từng service.

### Yêu cầu

1. Phân loại data theo criticality (Critical, High, Medium, Low)
2. Xác định RPO và RTO cho từng service
3. Đề xuất backup strategy phù hợp cho từng service
4. Tính toán estimated recovery time cho worst-case scenario
5. Tạo bảng tổng hợp data classification

### Expected Outcome

- Data classification table hoàn chỉnh
- RPO/RTO justified cho từng service
- Backup strategy mapping
- Total platform RTO estimated

### Hint

- Financial/auth data thường Critical, analytics thường Low
- RPO phụ thuộc vào: data có thể rebuild không? mất bao nhiêu tiền?
- RTO phụ thuộc vào: users chịu được bao lâu không có service này?

### Acceptance Criteria

- [ ] 5 services classified theo criticality
- [ ] RPO/RTO justified (không chỉ đặt số, phải giải thích lý do)
- [ ] Backup strategy phù hợp với RPO (ví dụ: RPO 0 → sync replication)
- [ ] Total platform RTO calculated
- [ ] Cost estimate cho backup infrastructure

### Bonus Challenge

- So sánh cost giữa RPO=0 vs RPO=1h cho user service
- Tạo decision tree: khi nào upgrade RPO/RTO?

---

## Bài 2: Medium — DR Plan Design cho E-commerce Platform

### Context

Bạn là Senior DevOps tại một e-commerce platform "FastShop". Platform hiện chạy trên single region (us-east-1) gồm:
- 4 microservices trên EKS
- PostgreSQL (RDS Multi-AZ)
- Redis ElastiCache
- Kafka (MSK)
- S3 for product images
- Monthly revenue: $500K
- Current SLA: 99.9% (≈ 43 phút downtime/tháng)

Business yêu cầu upgrade lên 99.95% SLA và có DR plan cho region failure.

### Yêu cầu

1. Thiết kế DR architecture (chọn pattern: warm standby hoặc active-passive)
2. Viết DR activation runbook chi tiết (step-by-step)
3. Viết DR test plan (quarterly test procedure)
4. Tính RPO/RTO cho từng component
5. Estimate additional cost cho DR infrastructure
6. Design DNS failover strategy
7. Address data consistency concerns

### Expected Outcome

- DR architecture diagram (mermaid)
- Complete DR activation runbook
- DR test plan with success criteria
- Cost breakdown

### Hint

- Warm standby: minimal infra always running, scale up when needed
- Active-passive: full infra, instant switch
- Route 53 health checks cho DNS failover
- RDS cross-region read replica cho database DR

### Acceptance Criteria

- [ ] DR architecture diagram với primary và DR region
- [ ] DR pattern chosen với justification
- [ ] RPO/RTO per component documented
- [ ] DR activation runbook ≥ 10 steps
- [ ] DR test plan với schedule và success criteria
- [ ] Cost estimate (monthly additional cost for DR)
- [ ] DNS failover strategy documented
- [ ] Data consistency approach documented

### Bonus Challenge

- Design automated DR activation (không cần manual intervention)
- Create communication template cho customers during DR activation
- Plan failback procedure (return to primary region)

---

## Bài 3: Hard — Multi-region Active-Active Design và Chaos Testing

### Context

Bạn là Principal SRE tại một global FinTech platform. Platform phục vụ users ở US, EU, và APAC. Requirements:
- 99.99% availability (≈ 52 phút downtime/năm)
- Transactions phải consistent (no double spending)
- Compliance: EU data phải ở EU (GDPR), US data ở US
- Peak: 50K TPS globally
- 12 microservices
- PostgreSQL + Redis + Kafka

### Yêu cầu

1. **Architecture Design**:
   - Multi-region active-active topology
   - Data routing strategy (geographic)
   - Conflict resolution approach
   - Compliance-aware data placement

2. **Implementation Plan**:
   - Database replication topology
   - Kafka MirrorMaker 2 configuration design
   - DNS/traffic routing (GeoDNS)
   - Cache consistency strategy

3. **Chaos Testing Plan**:
   - Region failure simulation
   - Network partition test
   - Data consistency verification
   - Performance under degraded mode

4. **Operational Procedures**:
   - Region maintenance runbook
   - Capacity planning per region
   - Cost optimization across regions
   - Compliance audit checklist

### Expected Outcome

- Complete multi-region architecture document
- Chaos testing plan (6+ test scenarios)
- 3 operational runbooks
- Cost analysis (3-region deployment)

### Hint

- Active-active writes: CockroachDB hoặc Spanner cho conflict-free
- GDPR: data geofencing, không replicate EU PII đến US
- Chaos testing: Chaos Monkey, Litmus, Gremlin
- GeoDNS: Route 53 geolocation routing

### Acceptance Criteria

- [ ] Multi-region architecture diagram (3 regions)
- [ ] Data routing strategy documented (geo-based)
- [ ] Conflict resolution approach chosen và justified
- [ ] GDPR compliance data placement designed
- [ ] 6+ chaos test scenarios defined
- [ ] Region maintenance runbook
- [ ] Cost breakdown (3 regions vs 1 region)
- [ ] Latency budget per region documented

### Bonus Challenge

- Design automated chaos testing pipeline (weekly)
- Create SLO dashboard cho multi-region (per-region và global)
- Design data sovereignty compliance automation

---

## Solutions

<details>
<summary>Solution Bài 1: RPO/RTO Analysis</summary>

### Data Classification Table

| Service | Data Type | Criticality | RPO | RTO | Backup Strategy | Cost/month |
|---------|-----------|------------|-----|-----|-----------------|------------|
| **User Service** | User profiles, auth | Critical | 1 min | 15 min | Async replication + WAL archive | $50 |
| **Project Service** | Projects, tasks | High | 5 min | 30 min | Async replication + hourly backup | $40 |
| **File Service** | Uploads | Medium | 24h | 1h | S3 Cross-Region Replication | $30 |
| **Notification** | Queue (transient) | Low | N/A | 5 min | No backup (rebuild) | $0 |
| **Analytics** | Usage data | Low | 24h | 4h | Daily pg_dump to S3 | $10 |

### Justification

**User Service (Critical, RPO=1min)**:
- Authentication data — nếu mất: users không login được
- User profiles — khó rebuild, UGC
- RPO=1min: async replication lag ~30s + safety margin
- RTO=15min: users chấp nhận 15 phút maintenance

**Project Service (High, RPO=5min)**:
- Core business data nhưng users có thể survive 5 phút
- Comments/activity có thể regenerate từ email notifications
- RPO=5min: async replication đủ

**File Service (Medium, RPO=24h)**:
- Files uploaded thường cũng có bản gốc ở user's machine
- S3 cross-region replication: ~15 phút lag
- RPO=24h conservative, actual RPO ~15 phút

**Notification (Low, RPO=N/A)**:
- Transient data, rebuild from scratch
- Redis trống → notifications gửi lại sau
- Cost: $0 cho backup

**Analytics (Low, RPO=24h)**:
- Historical data, khó rebuild nhưng non-critical
- Daily backup đủ, mất 1 ngày analytics acceptable

### Total Platform RTO

```
Worst case (region failure):
1. Database restore: 15 min (user) + 30 min (project) = parallel → 30 min
2. Application deploy: 10 min (IaC apply)
3. Cache warm: 5 min
4. DNS propagation: 5 min
5. Verification: 10 min

Total RTO: ~60 minutes (parallel execution)
```

### Cost

```
Monthly DR cost:
- S3 cross-region: $30
- Database replication: $90 (small RDS replica)
- S3 backup storage: $10
Total: ~$130/month
```

</details>

<details>
<summary>Solution Bài 2: DR Plan Design</summary>

### DR Architecture (Warm Standby)

```mermaid
graph TB
    subgraph "Primary: us-east-1"
        ALB1[ALB]
        EKS1[EKS Cluster<br/>4 services × 3 replicas]
        RDS1[RDS PostgreSQL<br/>Multi-AZ Primary]
        REDIS1[ElastiCache Redis<br/>Cluster mode]
        MSK1[MSK Kafka<br/>3 brokers]
        S31[S3 Product Images]
    end
    
    subgraph "DR: us-west-2"
        ALB2[ALB<br/>Ready]
        EKS2[EKS Cluster<br/>4 services × 1 replica]
        RDS2[RDS Read Replica<br/>Cross-region]
        REDIS2[ElastiCache Redis<br/>Single node]
        MSK2[MSK Kafka<br/>1 broker]
        S32[S3 Replica]
    end
    
    R53[Route 53<br/>Health Check Failover]
    
    R53 -->|primary| ALB1
    R53 -.->|failover| ALB2
    RDS1 -->|async replication| RDS2
    S31 -->|CRR| S32
    MSK1 -->|MirrorMaker 2| MSK2
    
    style EKS2 fill:#ffcc00
    style REDIS2 fill:#ffcc00
    style MSK2 fill:#ffcc00
```

### Chọn Warm Standby vì:
- Cost: ~$3K/month extra (vs $8K for active-passive)
- RTO 30 min acceptable cho $500K/month revenue
- Downtime cost: $500K / 30 days / 24h / 60min × 30min = ~$347
- DR cost ($3K) << downtime cost × probability

### DR Activation Runbook

```
Pre-condition: Primary region confirmed down > 5 minutes

Step 1: [IC] Declare DR activation in #incident channel
Step 2: [Ops] Verify DR region health:
        aws ecs describe-clusters --region us-west-2
Step 3: [Ops] Promote RDS read replica to standalone:
        aws rds promote-read-replica --db-instance-identifier fastshop-dr
Step 4: [Ops] Scale EKS services to full capacity:
        kubectl scale deploy --all --replicas=3 -n production
Step 5: [Ops] Scale Redis to cluster mode:
        aws elasticache modify-replication-group ...
Step 6: [Ops] Verify application health:
        curl https://dr-alb.us-west-2.elb.amazonaws.com/health
Step 7: [Ops] DNS failover (if not automatic):
        aws route53 change-resource-record-sets ...
Step 8: [Ops] Verify DNS propagation:
        dig api.fastshop.com +short
Step 9: [Comms] Update status page: "Operating from DR site"
Step 10: [QA] End-to-end test: place test order
Step 11: [Ops] Monitor error rates for 15 minutes
Step 12: [IC] Confirm DR activation complete
```

### Cost Breakdown

```
DR Infrastructure (us-west-2):
- EKS: $73/month (control plane)
- EC2 (4 × t3.medium): $134/month
- RDS read replica (db.t3.medium): $170/month
- ElastiCache (cache.t3.micro): $13/month
- MSK (1 broker): $180/month
- S3 CRR: ~$50/month
- ALB: $16/month + data
- Data transfer: ~$200/month

Total DR: ~$836/month
Primary cost: ~$5,000/month
DR overhead: ~17% extra
```

</details>

<details>
<summary>Solution Bài 3: Multi-region Active-Active (Outline)</summary>

### Architecture

```mermaid
graph TB
    GSLB[Global LB<br/>Route 53 GeoDNS]
    
    subgraph "US-East (Primary US)"
        US_LB[ALB]
        US_APP[12 Services]
        US_DB[CockroachDB<br/>US shard]
        US_KAFKA[Kafka]
    end
    
    subgraph "EU-West (Primary EU)"
        EU_LB[ALB]
        EU_APP[12 Services]
        EU_DB[CockroachDB<br/>EU shard]
        EU_KAFKA[Kafka]
    end
    
    subgraph "AP-Southeast (Primary APAC)"
        AP_LB[ALB]
        AP_APP[12 Services]
        AP_DB[CockroachDB<br/>APAC shard]
        AP_KAFKA[Kafka]
    end
    
    GSLB -->|US users| US_LB
    GSLB -->|EU users| EU_LB
    GSLB -->|APAC users| AP_LB
    
    US_DB <-->|Raft consensus| EU_DB
    EU_DB <-->|Raft consensus| AP_DB
    US_DB <-->|Raft consensus| AP_DB
```

### Data Routing (GDPR compliant)

```
Data geofencing:
- EU user PII → EU-West region ONLY (no replication to US/APAC)
- US user PII → US-East region ONLY
- APAC user PII → AP-Southeast region ONLY
- Non-PII data (product catalog) → replicated everywhere
- Transaction data → region of user's account

CockroachDB zone config:
ALTER TABLE users CONFIGURE ZONE USING
  constraints = '{"+region=eu-west-1": 3}',
  lease_preferences = '[[+region=eu-west-1]]'
  WHERE region = 'eu';
```

### Chaos Test Scenarios

```
1. Single AZ failure → verify automatic pod rescheduling
2. Full region failure → verify traffic routes to other regions
3. Network partition between regions → verify split-brain prevention
4. Database leader failover → verify write availability
5. DNS failure → verify client-side failover
6. Kafka partition loss → verify consumer rebalancing
```

### Cost (3 regions vs 1 region)

```
1 region:  $15,000/month
3 regions: $42,000/month (2.8x, not 3x due to shared services)
Extra:     $27,000/month

Justification:
- 99.99% vs 99.9% = 52 min vs 8.7 hours downtime/year
- Revenue protected: $500K/month × 12 = $6M/year
- Cost of 8 hours downtime: ~$33K
- DR cost: $27K × 12 = $324K/year
- Break-even: 10 hours downtime/year → ROI positive
```

</details>

