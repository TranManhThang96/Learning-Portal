# Day 49: Bài tập — Cost Optimization & FinOps

---

## Bài 1: Easy — Cost Audit và Quick Wins

### Context

Bạn mới join team DevOps tại startup "CloudApp". CTO phàn nàn cloud bill tăng 40% trong 3 tháng gần đây nhưng không biết nguyên nhân. Task đầu tiên: audit current infrastructure cost và tìm quick wins.

Platform hiện tại (AWS):
- EKS cluster: 5 nodes (m5.xlarge, On-Demand)
- 12 microservices, mỗi service request cpu=500m, memory=1Gi
- RDS PostgreSQL db.r6g.large Multi-AZ
- ElastiCache Redis cache.r6g.large
- 3 NAT Gateways
- S3: 500GB product images, 200GB logs
- EBS: tất cả dùng gp2

### Yêu cầu

1. Tạo cost breakdown spreadsheet cho platform hiện tại
2. Xác định top 3 cost drivers
3. Đề xuất 5 quick wins (effort < 1 ngày, risk thấp)
4. Estimate savings cho mỗi quick win
5. Tạo monthly budget alert configuration

### Expected Outcome

- Cost breakdown table đầy đủ
- 5 quick wins với estimated savings
- Total potential savings > 20%

### Hint

- Dùng AWS pricing calculator hoặc ước tính từ public pricing
- gp2 → gp3 là always-win (same/better perf, lower cost)
- Kiểm tra pod actual usage vs requests (right-sizing)
- NAT Gateway: $0.045/hour + $0.045/GB data processed

### Acceptance Criteria

- [ ] Cost breakdown có ≥ 5 categories (compute, database, storage, network, other)
- [ ] Top 3 cost drivers identified với % of total
- [ ] 5 quick wins documented với effort/risk/savings
- [ ] Total savings estimated > 20%
- [ ] Budget alert configuration (AWS Budgets hoặc equivalent)

### Bonus Challenge

- Tạo Grafana dashboard concept cho cost monitoring
- So sánh monthly cost nếu migrate từ On-Demand sang Savings Plans

---

## Bài 2: Medium — Kubernetes Cost Allocation và Right-sizing

### Context

"CloudApp" có 4 teams chia sẻ 1 EKS cluster. Mỗi tháng bill $8,000 nhưng không ai biết team nào tốn bao nhiêu. CTO yêu cầu implement cost allocation và right-sizing.

Teams và services:
- **Team Platform** (namespace: platform): ingress-controller, cert-manager, monitoring
- **Team Product** (namespace: product): product-api, search-service, image-processor
- **Team Order** (namespace: order): order-api, payment-service, notification
- **Team Data** (namespace: data): analytics-pipeline, etl-worker, data-api

Current resource allocation (tất cả pods):
- Requests: cpu=500m, memory=1Gi
- Limits: cpu=1000m, memory=2Gi
- Actual usage (measured): cpu=50-200m, memory=128-512Mi

### Yêu cầu

1. Design cost allocation model (namespace-based + label-based)
2. Calculate cost per team dựa trên resource requests
3. Identify over-provisioned services (requests >> actual usage)
4. Create right-sizing recommendations cho mỗi service
5. Implement ResourceQuota per namespace
6. Estimate savings sau right-sizing

### Expected Outcome

- Cost allocation table per team
- Right-sizing recommendations per service
- ResourceQuota YAML cho mỗi namespace
- Estimated savings > 30%

### Hint

- Cost per team = (team CPU requests / total CPU) × total compute cost
- Right-size: requests = P95(actual) × 1.2
- ResourceQuota prevent one team from consuming all resources
- Labels: `team`, `product`, `environment` cho Kubecost/OpenCost

### Acceptance Criteria

- [ ] Cost allocation model documented (formula + justification)
- [ ] Cost per team calculated ($X/month each)
- [ ] ≥ 8 services right-sized (before/after comparison)
- [ ] ResourceQuota for 4 namespaces (YAML)
- [ ] Savings estimated with confidence level
- [ ] Cost report template (monthly)

### Bonus Challenge

- Deploy OpenCost và verify cost allocation matches manual calculation
- Create automated right-sizing recommendation script (kubectl + jq)

---

## Bài 3: Hard — Enterprise FinOps Strategy

### Context

Bạn là FinOps Lead tại một mid-size SaaS company. AWS spend: $120K/month, growing 15%/quarter. CEO yêu cầu giảm 30% cost trong 6 tháng mà không ảnh hưởng performance hoặc reliability.

Current infrastructure:
- 3 EKS clusters: production, staging, development
- 200+ pods across all clusters
- 15 RDS instances (various sizes)
- 50+ S3 buckets
- Prometheus + Grafana + Loki + Tempo (full observability)
- All On-Demand pricing
- No cost tagging strategy
- No budget alerts

Teams: 8 engineering teams, 60+ engineers.

### Yêu cầu

1. **FinOps Assessment**: Evaluate current FinOps maturity (crawl/walk/run)
2. **Cost Reduction Plan** (6-month phased):
   - Month 1-2: Quick wins (tagging, zombie cleanup, gp3 migration)
   - Month 3-4: Medium effort (right-sizing, Savings Plans, spot)
   - Month 5-6: Architecture optimization (auto-scaling, consolidation)
3. **Governance Framework**:
   - Tagging policy (mandatory tags)
   - Budget alerts per team
   - Cost review cadence
   - Approval process for new resources
4. **Cost Allocation Model**:
   - Showback/chargeback per team
   - Shared cost distribution (monitoring, networking)
   - Unit economics (cost per customer, cost per transaction)
5. **Tooling Recommendation**:
   - Cost visibility (Kubecost, AWS Cost Explorer, custom)
   - Automated optimization (Karpenter, KEDA)
   - Reporting and alerting
6. **Risk Assessment**: Reliability impact cho mỗi optimization

### Expected Outcome

- FinOps maturity assessment
- 6-month cost reduction plan (phased)
- Governance framework document
- Cost allocation model
- Tooling architecture
- Risk matrix

### Hint

- 30% of $120K = $36K/month savings target
- Savings Plans typically save 30-40% on committed compute
- Right-sizing + spot typically save 20-40%
- Staging/dev off-hours = 50-70% savings on non-prod
- Observability cost often 10-15% of total

### Acceptance Criteria

- [ ] FinOps maturity level assessed với evidence
- [ ] 6-month plan với monthly milestones
- [ ] ≥ 15 optimization actions documented
- [ ] Each action: effort, savings estimate, risk level, owner
- [ ] Governance: tagging policy, budget alerts, review process
- [ ] Cost allocation: per-team breakdown, shared cost formula
- [ ] Tooling architecture diagram
- [ ] Risk matrix: ≥ 5 reliability risks assessed
- [ ] Total estimated savings ≥ $36K/month (30%)

### Bonus Challenge

- Create executive dashboard mockup (cost trends, savings, team comparison)
- Design automated cost anomaly detection (alert on >20% spike)
- Calculate ROI cho FinOps investment (tooling + personnel)

---

## Solutions

<details>
<summary>Solution Bài 1: Cost Audit</summary>

### Cost Breakdown

| Category | Resource | Spec | Monthly Cost |
|---------|----------|------|-------------|
| **Compute** | EKS Control Plane | 1 cluster | $73 |
| | EC2 (5 × m5.xlarge) | On-Demand | $700 |
| **Database** | RDS PostgreSQL | db.r6g.large MA | $560 |
| | ElastiCache Redis | cache.r6g.large | $200 |
| **Storage** | EBS gp2 (nodes) | 5 × 100GB | $50 |
| | EBS gp2 (PVCs) | 200GB | $20 |
| | S3 (images) | 500GB | $12 |
| | S3 (logs) | 200GB | $5 |
| **Network** | NAT Gateway (3) | 3 × $97 | $291 |
| | ALB | 1 | $25 |
| | Data transfer | ~100GB | $9 |
| **Total** | | | **$1,945** |

### Top 3 Cost Drivers

1. **Compute (EC2)**: $700 = 36% of total
2. **Database (RDS+Redis)**: $760 = 39% of total
3. **Network (NAT)**: $291 = 15% of total

### 5 Quick Wins

| # | Action | Effort | Risk | Savings |
|---|--------|--------|------|---------|
| 1 | gp2 → gp3 (all EBS) | 2h | None | $14/mo (20%) |
| 2 | Reduce NAT to 1 + VPC endpoints | 4h | Low | $145/mo |
| 3 | Right-size pods (500m→150m CPU) | 4h | Low | ~$140/mo (1 fewer node) |
| 4 | S3 lifecycle (logs 30d → IA, 90d → delete) | 1h | None | $3/mo |
| 5 | Budget alert setup | 1h | None | $0 (prevention) |

**Total quick win savings: ~$302/month (15.5%)**

### Budget Alert

```bash
aws budgets create-budget --account-id 123456789 \
  --budget '{
    "BudgetName": "CloudApp-Monthly",
    "BudgetLimit": {"Amount": "2000", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[
    {"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"devops@cloudapp.com"}]},
    {"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"cto@cloudapp.com"}]}
  ]'
```

</details>

<details>
<summary>Solution Bài 2: Cost Allocation và Right-sizing</summary>

### Cost Allocation Formula

```
Team cost = (Team CPU requests / Total cluster CPU requests) × Total compute cost
           + (Team Memory requests / Total cluster Memory requests) × Total compute cost
           ÷ 2  (average of CPU and memory proportion)
```

### Cost Per Team

| Team | # Pods | CPU Req | Mem Req | % Cluster | Cost/month |
|------|--------|---------|---------|-----------|------------|
| Platform | 6 | 3000m | 6Gi | 25% | $2,000 |
| Product | 6 | 3000m | 6Gi | 25% | $2,000 |
| Order | 6 | 3000m | 6Gi | 25% | $2,000 |
| Data | 6 | 3000m | 6Gi | 25% | $2,000 |
| **Total** | **24** | **12000m** | **24Gi** | **100%** | **$8,000** |

### Right-sizing Recommendations

| Service | Current CPU Req | Actual P95 | New CPU Req | Current Mem | Actual P95 | New Mem |
|---------|----------------|------------|-------------|-------------|------------|---------|
| product-api | 500m | 180m | 220m | 1Gi | 400Mi | 480Mi |
| search-service | 500m | 120m | 150m | 1Gi | 256Mi | 320Mi |
| image-processor | 500m | 200m | 250m | 1Gi | 512Mi | 640Mi |
| order-api | 500m | 150m | 180m | 1Gi | 350Mi | 420Mi |
| payment-service | 500m | 80m | 100m | 1Gi | 200Mi | 250Mi |
| notification | 500m | 50m | 65m | 1Gi | 128Mi | 160Mi |
| analytics-pipeline | 500m | 100m | 125m | 1Gi | 300Mi | 360Mi |
| etl-worker | 500m | 180m | 220m | 1Gi | 450Mi | 540Mi |

**Total CPU after right-sizing: 12000m → 3720m (69% reduction)**

### ResourceQuota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-product-quota
  namespace: product
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
    pods: "20"
    persistentvolumeclaims: "10"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-order-quota
  namespace: order
spec:
  hard:
    requests.cpu: "1500m"
    requests.memory: 3Gi
    limits.cpu: "3"
    limits.memory: 6Gi
    pods: "15"
```

**Estimated savings: 2 fewer nodes = $280/month (35% compute savings)**

</details>

<details>
<summary>Solution Bài 3: Enterprise FinOps (Outline)</summary>

### FinOps Maturity: CRAWL

```
Evidence:
- No cost tagging ❌
- No budget alerts ❌
- All On-Demand ❌
- No cost visibility per team ❌
- No optimization process ❌
Score: 1/5 (Crawl stage)
```

### 6-Month Plan Summary

```
Month 1-2 (Quick Wins): Target $12K savings
├── Tagging policy implementation
├── gp2 → gp3 migration ($500)
├── NAT Gateway optimization ($2,000)
├── Zombie resource cleanup ($3,000)
├── Dev/staging off-hours ($4,000)
└── Right-size obvious over-provisioning ($2,500)

Month 3-4 (Medium Effort): Target $15K savings
├── 1-year Savings Plans for baseline ($8,000)
├── Spot instances for stateless prod ($4,000)
├── Database right-sizing ($2,000)
└── Log/metrics retention optimization ($1,000)

Month 5-6 (Architecture): Target $9K savings
├── Karpenter consolidation ($4,000)
├── KEDA for event-driven scaling ($2,000)
├── S3 lifecycle automation ($1,000)
├── Reserved capacity for databases ($2,000)
└── Total: $36K/month (30% reduction) ✅
```

### Tagging Policy

```
Required tags:
- team: [platform|product|order|data|infra]
- environment: [production|staging|development]
- service: [service-name]
- cost-center: [CC-XXXX]
- owner: [email]

Enforcement:
- AWS Config rule: check tag compliance
- CI/CD gate: Terraform plan must include tags
- Monthly audit: untagged resources report
```

</details>

