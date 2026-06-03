# Day 49: Cost Optimization & FinOps

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích** được FinOps mindset và vì sao cost optimization là trách nhiệm của engineering, không chỉ finance.
2. **Phân tích** được cost breakdown của Kubernetes platform và xác định top cost drivers.
3. **Áp dụng** được ít nhất 10 kỹ thuật giảm cost mà không ảnh hưởng reliability.
4. **Thiết kế** được cost allocation strategy cho multi-team Kubernetes cluster.
5. **Đánh giá** được trade-off giữa cost, performance và reliability cho mỗi quyết định infrastructure.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Cloud bill tăng là vấn đề phổ biến nhất của mọi team:

```
Year 1: "Cloud rẻ hơn on-premise!"     →  $5K/month
Year 2: "Hơi đắt nhưng chấp nhận được" →  $25K/month
Year 3: "Sao bill tháng này $80K???"    →  $80K/month
Year 4: "CEO: giảm 40% cloud cost"     →  panic mode
```

**Gartner ước tính**: 70% cloud spend bị lãng phí hoặc chưa tối ưu.

### Hậu quả nếu không quản lý cost

- **Over-provisioning**: Chạy m5.2xlarge cho service chỉ dùng 10% CPU → 90% waste
- **Zombie resources**: Load balancers, EBS volumes, IP addresses không ai dùng
- **Log explosion**: Prometheus retain 90 ngày, Loki lưu tất cả logs → storage cost tăng 10x
- **No showback**: Team A dùng 80% cluster nhưng không biết → không có incentive optimize

### Liên hệ với developer

FinOps giống **code optimization**:
- Không optimize trước khi đo (profile first, optimize second)
- 80/20 rule: 20% changes giải quyết 80% cost
- Premature optimization is the root of all evil → premature cost cutting cũng vậy
- Benchmark → identify bottleneck → fix → re-benchmark

---

## 3. Kiến thức nền tảng

### FinOps là gì?

**FinOps = Financial Operations** — một practice kết hợp finance, engineering, và business để quản lý cloud cost.

```
FinOps Lifecycle:
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Inform  │ ──→ │ Optimize │ ──→ │ Operate  │
│          │     │          │     │          │
│ Visibility│     │ Right-   │     │ Continuous│
│ Allocation│     │ sizing   │     │ monitoring│
│ Reporting │     │ Reserved │     │ Governance│
│           │     │ Spot     │     │ Automation│
└──────────┘     └──────────┘     └──────────┘
      ▲                                │
      └────────────────────────────────┘
                  Iterate
```

**3 principles**:
1. **Teams need to collaborate**: Engineering + Finance + Business cùng quyết định
2. **Everyone takes ownership**: Mỗi team chịu trách nhiệm cost của mình
3. **FinOps is iterative**: Optimize liên tục, không phải one-time project

### Cloud Cost Structure

```
Cloud bill breakdown (typical):
┌────────────────────────────────────┐
│ Compute (EC2, EKS nodes)    60%   │ ← Biggest opportunity
├────────────────────────────────────┤
│ Database (RDS, ElastiCache) 15%   │
├────────────────────────────────────┤
│ Storage (S3, EBS)           10%   │
├────────────────────────────────────┤
│ Network (NAT, data transfer) 8%   │ ← Often overlooked
├────────────────────────────────────┤
│ Other (LB, DNS, KMS, etc.)  7%   │
└────────────────────────────────────┘
```

### Kubernetes Cost Allocation

Kubernetes mặc định **không có cost visibility** — tất cả pods chia shared cluster → ai trả bao nhiêu?

```
Cluster cost: $10,000/month
├── Team A (20 pods, 40% resources) → $4,000
├── Team B (50 pods, 35% resources) → $3,500
├── Team C (10 pods, 15% resources) → $1,500
├── Shared (monitoring, ingress)    → $1,000
└── Idle/wasted                     → ???
```

**3 phương pháp allocation**:

| Method | Description | Accuracy | Effort |
|--------|-------------|----------|--------|
| **Namespace-based** | Cost per namespace | Low | Easy |
| **Label-based** | Cost per team/product label | Medium | Medium |
| **Request-based** | Cost per actual resource requests | High | High |

---

## 4. Deep Dive

### Cost Optimization Hierarchy

```mermaid
graph TB
    subgraph "Impact: HIGH"
        A[1. Right-sizing<br/>Compute instances]
        B[2. Pricing models<br/>Reserved/Spot/Savings Plans]
        C[3. Auto-scaling<br/>Scale down off-hours]
    end
    
    subgraph "Impact: MEDIUM"
        D[4. Storage optimization<br/>Lifecycle policies]
        E[5. Network optimization<br/>NAT, data transfer]
        F[6. Database optimization<br/>Right instance, read replicas]
    end
    
    subgraph "Impact: LOW-MEDIUM"
        G[7. Observability cost<br/>Log/metric retention]
        H[8. Zombie resource cleanup<br/>Unused LBs, volumes]
        I[9. Architecture changes<br/>Serverless, spot-friendly]
    end
    
    A --> D
    B --> E
    C --> F
    D --> G
    E --> H
    F --> I
```

### 1. Right-sizing (Impact: 20-40% savings)

```
Vấn đề:
Pod requests: cpu=1000m, memory=2Gi
Pod actual usage: cpu=100m, memory=256Mi
→ 90% CPU wasted, 87% memory wasted

Giải pháp:
1. Đo actual usage (Prometheus metrics, VPA recommendations)
2. Set requests = P95 actual usage × 1.2 (20% buffer)
3. Set limits = requests × 2 (burst headroom)
```

```bash
# Xem actual usage vs requests
kubectl top pods -n production --containers

# VPA recommendation
kubectl get vpa -n production -o yaml | grep -A10 recommendation
```

```yaml
# Before (over-provisioned)
resources:
  requests:
    cpu: "1"
    memory: 2Gi
  limits:
    cpu: "2"
    memory: 4Gi

# After (right-sized based on metrics)
resources:
  requests:
    cpu: 150m
    memory: 320Mi
  limits:
    cpu: 500m
    memory: 640Mi
```

### 2. Pricing Models

```
AWS EC2 pricing comparison (m5.xlarge, us-east-1):

┌──────────────────┬──────────┬──────────┬──────────┐
│ Pricing          │ $/hour   │ $/month  │ Savings  │
├──────────────────┼──────────┼──────────┼──────────┤
│ On-Demand        │ $0.192   │ $140.16  │ 0%       │
│ 1yr Reserved     │ $0.121   │ $88.33   │ 37%      │
│ 3yr Reserved     │ $0.081   │ $59.13   │ 58%      │
│ 1yr Savings Plan │ $0.121   │ $88.33   │ 37%      │
│ 3yr Savings Plan │ $0.077   │ $56.21   │ 60%      │
│ Spot Instance    │ ~$0.058  │ ~$42.34  │ 70%      │
└──────────────────┴──────────┴──────────┴──────────┘
```

**Khi nào dùng gì**:

| Pricing | Use Case | Risk |
|---------|----------|------|
| **On-Demand** | Dev/test, bursty workloads | Đắt nhưng flexible |
| **Reserved / Savings Plan** | Baseline production load | Commit 1-3 năm |
| **Spot** | Stateless workers, batch jobs, CI/CD runners | 2-minute interruption notice |

### 3. Kubernetes-specific Cost Optimization

#### Cluster Autoscaler + Consolidation

```yaml
# Karpenter (AWS) — aggressive bin-packing
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
      - key: karpenter.sh/capacity-type
        operator: In
        values: ["spot", "on-demand"]
      - key: node.kubernetes.io/instance-type
        operator: In
        values: ["m5.large", "m5.xlarge", "m5a.large", "m5a.xlarge"]
    
  disruption:
    consolidationPolicy: WhenUnderutilized
    consolidateAfter: 30s
  
  limits:
    cpu: 100     # Max 100 vCPUs
    memory: 400Gi
```

#### Off-hours Scaling

```yaml
# KEDA: Scale to 0 during off-hours
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: staging-api
spec:
  scaleTargetRef:
    name: api-server
  minReplicaCount: 0
  maxReplicaCount: 5
  triggers:
  - type: cron
    metadata:
      timezone: Asia/Ho_Chi_Minh
      start: "0 8 * * 1-5"   # 8 AM weekdays
      end: "0 20 * * 1-5"    # 8 PM weekdays
      desiredReplicas: "3"
```

**Impact**: Staging environment chỉ chạy 12h × 5 ngày = 60/168 giờ → **tiết kiệm 64%**.

### Kubecost Architecture

```mermaid
graph TB
    subgraph "Kubecost"
        KC[Kubecost Server]
        ETL[ETL Pipeline]
        CS[Cost Store]
    end
    
    subgraph "Data Sources"
        P[Prometheus<br/>Resource metrics]
        API[K8s API<br/>Pod/Node info]
        CLOUD[Cloud API<br/>Pricing data]
    end
    
    subgraph "Output"
        DASH[Dashboard<br/>Cost per namespace/label]
        ALERT[Alerts<br/>Budget exceeded]
        REPORT[Reports<br/>Monthly cost]
        SAVINGS[Savings<br/>Recommendations]
    end
    
    P --> ETL
    API --> ETL
    CLOUD --> ETL
    ETL --> CS
    CS --> KC
    KC --> DASH
    KC --> ALERT
    KC --> REPORT
    KC --> SAVINGS
```

### Observability Cost

```
Log cost formula:
Daily log volume × retention days × storage cost per GB

Example:
- 50 pods × 100 log lines/second = 5000 lines/second
- Average line: 500 bytes
- Daily: 5000 × 500 × 86400 = 216 GB/day
- 30-day retention: 216 × 30 = 6.48 TB
- S3 storage: 6.48TB × $0.023 = $149/month
- EBS (Elasticsearch): 6.48TB × $0.10 = $648/month

Optimization:
1. Reduce log verbosity (INFO → WARN for production)
2. Structured logging → filter before store
3. Tiered retention:
   - Hot (7 days): Elasticsearch/Loki → fast query
   - Warm (30 days): S3 Standard → slower query
   - Cold (90+ days): S3 Glacier → archive only
4. Sample high-volume logs (keep 10% of DEBUG)
```

```
Metrics cost formula:
Active time series × scrape interval × retention × storage per sample

Example:
- 100,000 active time series
- 15s scrape interval
- 15-day retention
- ~2 bytes per sample (compressed TSDB)
- Samples: 100K × (86400/15) × 15 = 8.64 billion samples
- Storage: 8.64B × 2 bytes = ~17 GB (surprisingly small)
- BUT: cardinality explosion (1M series) → 170 GB → OOM

Optimization:
1. Drop unused metrics (relabel_configs)
2. Increase scrape interval for non-critical (15s → 60s)
3. Recording rules → pre-aggregate, drop raw
4. Reduce label cardinality (no pod_name in metrics)
5. Short retention locally (7d) + long-term Thanos/Mimir
```

---

## 5. Trade-offs & Best Practices ⭐

### Top 10 Cost Optimization Techniques

| # | Technique | Savings | Risk | Effort |
|---|-----------|---------|------|--------|
| 1 | Right-size pods (requests/limits) | 20-40% | Low | Medium |
| 2 | Spot instances cho stateless | 60-70% | Medium | Medium |
| 3 | Reserved/Savings Plans cho baseline | 30-60% | Low (commit) | Low |
| 4 | Off-hours scaling (staging/dev) | 50-70% | Low | Low |
| 5 | Cluster consolidation (Karpenter) | 15-30% | Low | Medium |
| 6 | Log retention reduction | varies | Low | Low |
| 7 | EBS volume optimization (gp2→gp3) | 20% | None | Low |
| 8 | NAT Gateway optimization | 10-30% | Medium | High |
| 9 | Zombie resource cleanup | 5-15% | None | Low |
| 10 | Architecture: serverless for spiky | varies | Medium | High |

### Cost vs Reliability Trade-offs

```
Cost optimization spectrum:

← SAVE MONEY                              SPEND MONEY →
  
  Spot only → Spot+OD mix → On-Demand → Reserved → Dedicated
  Risk: HIGH    MEDIUM       LOW         LOW        LOWEST
  
  1 replica → 2 replicas → 3 replicas → N+2
  Risk: HIGH    LOW          LOWEST      OVERKILL
  
  No DR → Cold DR → Warm DR → Active-Passive → Active-Active
  Risk: HIGH  MEDIUM   LOW      LOW              LOWEST
  
  gp2 → gp3 → io1 → io2 → Local NVMe
  Cost: LOW    LOW   MEDIUM   HIGH    HIGHEST
```

### Recommendations by Company Size

#### Startup (< $5K/month cloud)

```
Focus:
1. Right-size pods — biggest bang for buck
2. Use spot for non-production
3. Off-hours scaling for staging
4. gp3 instead of gp2 (free upgrade)
5. Clean up zombie resources monthly

Skip:
- Reserved instances (too early to commit)
- Kubecost (manual tracking sufficient)
- Multi-tier log retention (low volume)
```

#### Mid-size ($5K-50K/month)

```
Focus:
1. All startup optimizations
2. Savings Plans for baseline compute
3. Karpenter for cluster autoscaling
4. Kubecost for cost allocation
5. Log/metrics retention policies
6. NAT Gateway optimization
7. Budget alerts per team

Consider:
- Spot instances for production stateless
- Database right-sizing
- Reserved instances for databases
```

#### Enterprise ($50K+/month)

```
Focus:
1. All mid-size optimizations  
2. Full FinOps practice (dedicated person/team)
3. Chargeback/showback per team
4. Automated right-sizing (VPA + monitoring)
5. Spot everywhere possible (with fallback)
6. Multi-tier storage lifecycle
7. Network architecture optimization
8. FinOps tooling (Kubecost Enterprise, CloudHealth)
9. Negotiated pricing (EDP, private pricing)
10. Regular architecture reviews for cost
```

### Anti-patterns

1. **"Cut cost by reducing replicas"**: 3→1 replica saves 67% cost nhưng SLA drops to 0% khi pod crash
2. **"Spot for everything"**: Spot cho database = data loss risk
3. **"No monitoring to save cost"**: Không biết usage → không optimize được → cost higher
4. **"Over-optimize dev environment"**: Developer productivity loss > server cost savings
5. **"Wait for bill to optimize"**: Reactive → fix cost after spending. Proactive → prevent waste

---

## 6. Performance & Scalability ⭐

### Cost-Performance Relationship

```
Performance curve vs cost:
                  ╭───── Diminishing returns
                 ╱
Performance  ───╱────────────────────────
               ╱│
              ╱ │
             ╱  │
            ╱   │ ← Sweet spot
           ╱    │   (80% performance
          ╱     │    at 40% cost)
         ╱      │
        ╱       │
───────╱────────┼──────────────────── Cost
     Low     Sweet    Max
              spot
```

### Spot Instance Performance Impact

```
Spot interruption handling:

1. AWS sends 2-minute warning
2. Pod receives SIGTERM
3. Graceful shutdown (connection drain, in-flight request completion)
4. Pod rescheduled to available node

Impact:
- Stateless HTTP services: minimal (LB routes around)
- Batch jobs: retry mechanism needed
- CI/CD runners: build restart (10-30 minute delay)
- Databases: NEVER USE SPOT for stateful workloads
```

### Right-sizing Impact on Performance

```
Over-provisioned:
  cpu: 2000m request → actual 200m → NO throttling but wasteful
  
Right-sized:  
  cpu: 300m request → actual 200m → safe, 50% headroom
  
Under-provisioned:
  cpu: 150m request → actual 200m → CPU THROTTLING → latency ↑↑↑
  
Rule: request = P95(actual) × 1.2
      limit = request × 2 (burst)
```

---

## 7. Security & Reliability Considerations

### Security trong Cost Optimization

- **Spot instances**: Termination = data in memory lost → encrypt sensitive data at rest
- **Shared clusters**: Namespace isolation, RBAC — team A không thấy team B costs
- **Cost anomaly detection**: Sudden cost spike = potential crypto mining attack
- **Savings Plans**: Commit carefully — over-commit = locked in, under-commit = missed savings

### Reliability Risks

```
Cost optimization KHÔNG được compromise:
❌ Reduce replicas below minAvailable (PDB)
❌ Remove monitoring to save cost
❌ Skip backups to save storage
❌ Use spot for databases or stateful services
❌ Reduce DR capability below RPO/RTO targets
❌ Remove health checks/probes for "simplicity"

Cost optimization CÓ THỂ safely:
✅ Right-size overprovisioned pods
✅ Spot for stateless, fault-tolerant workloads
✅ Off-hours scaling for non-production
✅ Log retention reduction (keep enough for debugging)
✅ Storage tiering (hot → warm → cold)
✅ gp2 → gp3 migration (same/better performance, lower cost)
```

---

## 8. Hands-on Example

### Tạo Cost Breakdown cho Kubernetes Platform

#### Scenario

Platform "TechCorp" chạy trên AWS EKS:
- 3 node groups: system, application, monitoring
- 8 microservices
- PostgreSQL RDS
- Redis ElastiCache
- S3 for assets
- Prometheus + Grafana + Loki monitoring stack

#### Bước 1: Inventory Current Resources

```bash
# List all nodes and their types
kubectl get nodes -o custom-columns=\
"NAME:.metadata.name,TYPE:.metadata.labels.node\.kubernetes\.io/instance-type,ZONE:.metadata.labels.topology\.kubernetes\.io/zone"

# List all pods and their resource requests
kubectl get pods --all-namespaces -o custom-columns=\
"NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory" \
| head -50

# Total resource requests vs capacity
kubectl describe nodes | grep -A5 "Allocated resources"
```

#### Bước 2: Cost Breakdown Spreadsheet

```markdown
## TechCorp Infrastructure Cost Breakdown

### Compute (EKS Nodes)
| Node Group | Instance | Count | On-Demand $/month | Current Pricing |
|-----------|----------|-------|-------------------|-----------------|
| System | m5.large | 2 | $140 × 2 = $280 | On-Demand |
| App | m5.xlarge | 4 | $280 × 4 = $1,120 | On-Demand |
| Monitoring | m5.large | 2 | $140 × 2 = $280 | On-Demand |
| **Subtotal** | | **8** | **$1,680** | |

### EKS
| Item | Cost |
|------|------|
| Control Plane | $73 |

### Database
| Service | Type | Cost |
|---------|------|------|
| RDS PostgreSQL | db.r6g.large Multi-AZ | $560 |
| ElastiCache Redis | cache.r6g.large × 2 | $400 |
| **Subtotal** | | **$960** |

### Storage
| Type | Size | Cost |
|------|------|------|
| EBS gp2 (nodes) | 8 × 100GB = 800GB | $80 |
| EBS gp2 (PVCs) | 500GB | $50 |
| S3 (assets) | 2TB | $46 |
| S3 (backups) | 500GB | $12 |
| **Subtotal** | | **$188** |

### Network
| Type | Cost |
|------|------|
| NAT Gateway (3 AZs) | $97 × 3 = $291 |
| ALB | $25 |
| Data transfer | $150 |
| **Subtotal** | **$466** |

### Monitoring
| Service | Cost |
|---------|------|
| Prometheus storage (PVC) | included in EBS |
| Loki storage (S3) | ~$30 |
| Grafana (in-cluster) | $0 |
| **Subtotal** | **$30** |

### TOTAL: $3,397/month
```

#### Bước 3: Identify Optimization Opportunities

```markdown
## Optimization Recommendations

### 1. Right-size pods (Est. savings: $400/month)
Current: Most pods request 500m CPU, use < 100m
Action: Reduce to actual P95 × 1.2
Impact: Can run on 3 app nodes instead of 4

### 2. Savings Plans for baseline (Est: $500/month)
Current: All On-Demand
Action: 1-year Compute Savings Plan for baseline (6 nodes)
Savings: 37% on committed nodes

### 3. Spot for app nodes (Est: $350/month)
Current: All On-Demand
Action: 2 of 4 app nodes → Spot (with fallback to OD)
Savings: 60% on 2 nodes

### 4. gp2 → gp3 migration (Est: $26/month)
Current: gp2 ($0.10/GB)
Action: Migrate to gp3 ($0.08/GB + baseline 3K IOPS free)
Savings: 20% on EBS, better performance

### 5. NAT Gateway optimization (Est: $145/month)
Current: 3 NAT Gateways (one per AZ)
Action: Use 1 NAT Gateway + VPC endpoints for S3/ECR
Savings: Remove 2 NAT Gateways

### 6. Off-hours scaling for monitoring (Est: $100/month)
Current: Full monitoring stack 24/7
Action: Scale down Prometheus replicas off-hours
Savings: 50% on monitoring nodes

### 7. Log retention (Est: $15/month)
Current: Loki retains 90 days
Action: 7 days hot, 30 days warm (S3 IA), delete after
Savings: 50% on log storage

## Summary
| # | Optimization | Monthly Savings | Risk |
|---|-------------|-----------------|------|
| 1 | Right-size pods | $400 | Low |
| 2 | Savings Plans | $500 | Low |
| 3 | Spot instances | $350 | Medium |
| 4 | gp3 migration | $26 | None |
| 5 | NAT optimization | $145 | Low |
| 6 | Off-hours monitoring | $100 | Low |
| 7 | Log retention | $15 | Low |
| **Total** | | **$1,536/month** | |
| **Savings %** | | **45%** | |

New monthly cost: $3,397 - $1,536 = $1,861/month
Annual savings: $18,432
```

#### Bước 4: Implement Quick Wins

```bash
# 1. gp3 migration (zero risk)
# Update StorageClass
cat <<'EOF' | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
EOF

# 2. Right-size example pod
kubectl patch deploy api-server -n production --type='merge' -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "api",
          "resources": {
            "requests": {"cpu": "150m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"}
          }
        }]
      }
    }
  }
}'

# 3. Set budget alert
# AWS Budgets CLI
aws budgets create-budget --account-id 123456789 \
  --budget '{
    "BudgetName": "Monthly-EKS",
    "BudgetLimit": {"Amount": "2000", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "devops@techcorp.com"
    }]
  }]'
```

**Expected output**:

```text
storageclass.storage.k8s.io/gp3 configured
deployment.apps/api-server patched
# aws budgets create-budget thường không in output nếu thành công
```

**Verify**:

```bash
# Verify default StorageClass moved to gp3
kubectl get storageclass

# Verify pod resources changed
kubectl get deploy api-server -n production \
  -o jsonpath='{.spec.template.spec.containers[0].resources}'

# Verify AWS budget exists
aws budgets describe-budget --account-id 123456789 \
  --budget-name Monthly-EKS
```

**Cleanup**:

```bash
# Lab-only cleanup: revert the sample deployment resources if needed
kubectl rollout undo deploy/api-server -n production

# Delete sample budget created for the exercise
aws budgets delete-budget --account-id 123456789 \
  --budget-name Monthly-EKS
```

---

## 9. Common Pitfalls & Debugging

### Lỗi thường gặp

| Pitfall | Impact | Fix |
|---------|--------|-----|
| Right-size quá aggressive | Pod OOMKilled, CPU throttle | Buffer 20% above P95 |
| Spot không có fallback | Service down khi spot reclaimed | Mixed node group: spot + on-demand |
| Savings Plan over-commit | Paying for unused commitment | Start with 50-70% coverage |
| Delete monitoring to save cost | Can't debug production issues | Optimize retention, not remove |
| Shared cluster no limits | One team uses all resources | ResourceQuota per namespace |

### Production Case Study: Observability Cost Explosion

#### Context
SaaS platform, 100 microservices, Prometheus + Loki + Tempo stack. Cloud bill: $15K/month.

#### Symptom
- Month 6: monitoring cost tăng từ $800 lên $3,200 (4x)
- Prometheus OOMKilled 3 lần/tuần
- EBS volumes cho Prometheus gần full

#### Investigation
```bash
# Check cardinality
curl -s http://prometheus:9090/api/v1/label/__name__/values | jq '. | length'
# Result: 45,000 metric names

# Top cardinality metrics
curl -s 'http://prometheus:9090/api/v1/query?query=topk(10,count by(__name__)({__name__=~".+"}))'
# Found: custom_http_request_duration_bucket with user_id label
# 50,000 users × 10 endpoints × 20 buckets = 10,000,000 time series!
```

#### Root Cause
- Developer added `user_id` label to histogram metric
- 50K active users → 10M time series → Prometheus needs 40GB RAM
- Storage: 10M series × 2 bytes/sample × 5760 samples/day × 15 days = 1.7TB

#### Fix
```yaml
# 1. Remove high-cardinality label at scrape
- job_name: 'api-server'
  metric_relabel_configs:
  - source_labels: [__name__]
    regex: 'custom_http_request_duration_bucket'
    action: drop  # Drop entirely, rewrite without user_id
    
# 2. Or relabel to drop user_id
  - source_labels: [user_id]
    target_label: user_id
    action: labeldrop

# 3. Reduce retention
# prometheus.yml
storage:
  tsdb:
    retention.time: 7d  # Was 15d
    retention.size: 50GB
```

**Result**: Prometheus RAM 40GB → 4GB, storage cost -75%.

#### Lesson Learned
- **Never put high-cardinality values as metric labels** (user_id, request_id, IP)
- Monitor `prometheus_tsdb_head_series` metric
- Alert when cardinality > threshold
- Code review metric definitions before merge

---

## 10. Kết nối với bài trước & bài sau

### Bài trước — Day 48: Multi-region & Disaster Recovery

- DR infrastructure = cost overhead (50-100% extra) → cần optimize
- Warm standby cheaper than active-passive → cost-aware DR design
- Spot instances cho DR warm standby acceptable (non-critical)
- S3 Glacier cho long-term backup → giảm storage cost

### Bài sau — Day 50: Capstone Project

- Cost breakdown là 1 trong 12 deliverables của capstone
- Trade-offs giữa cost và reliability → core decision trong capstone
- Budget constraint là real production requirement
- FinOps mindset áp dụng cho toàn bộ architecture design

### Kiến thức tái sử dụng

- **Resource management** (Day 18): Right-sizing requests/limits
- **Autoscaling** (Day 19): HPA/KEDA cho efficient scaling
- **Observability** (Day 38-42): Log/metrics cost optimization
- **Storage** (Day 15): StorageClass selection affects cost
- **Spot instances**: Deployment strategies (Day 35) cho spot-friendly

---

## 11. Tài liệu tham khảo

### Must-read
- [FinOps Foundation](https://www.finops.org/) — FinOps framework và community
- [Kubecost Documentation](https://docs.kubecost.com/) — Kubernetes cost management
- [AWS Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/) — Well-Architected Framework

### Nice-to-have
- [OpenCost](https://www.opencost.io/) — CNCF open-source cost monitoring
- [Karpenter](https://karpenter.sh/) — AWS node provisioning (cost-efficient)
- [Spot.io](https://spot.io/) — Multi-cloud spot management

### Deep-dive
- **Book**: "Cloud FinOps" (J.R. Storment, Mike Fuller) — FinOps bible
- **Blog**: [Last Week in AWS](https://www.lastweekinaws.com/) — Corey Quinn's cloud cost insights
- **Talk**: [KubeCon Cost Optimization talks](https://www.youtube.com/results?search_query=kubecon+cost+optimization) — real-world case studies

