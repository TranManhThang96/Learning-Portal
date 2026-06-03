# Day 49: Document — Cost Optimization & FinOps Reference

---

## 1. FinOps Maturity Model

### Level 0: No FinOps

```
Signs:
- No cost visibility
- No tagging strategy
- All resources On-Demand
- No budget alerts
- Monthly surprise bill
- Blame culture (finance vs engineering)
```

### Level 1: Crawl (Visibility)

```
Objectives:
- Mandatory tagging policy
- Budget alerts per team/environment
- Monthly cost reviews
- Basic cost allocation (namespace/team)
- Zombie resource detection

Tools: AWS Cost Explorer, tags, budgets
Typical savings: 10-15% from hygiene
```

### Level 2: Walk (Optimization)

```
Objectives:
- Right-sizing program
- Savings Plans / Reserved Instances
- Spot instances for non-critical
- Automated recommendations (Compute Optimizer)
- Kubernetes cost allocation (Kubecost/OpenCost)
- Showback to teams (quarterly)

Tools: Kubecost, Compute Optimizer, Savings Plans
Typical savings: 20-35% total
```

### Level 3: Run (Automation)

```
Objectives:
- Automated right-sizing (VPA)
- Spot instance automation with fallback
- Karpenter/cluster autoscaler aggressive consolidation
- Unit economics (cost per customer/transaction)
- Chargeback to teams
- Cost anomaly detection
- FinOps as engineering practice

Tools: Karpenter, custom automation, advanced Kubecost
Typical savings: 40-50%+ total
```

---

## 2. Kubernetes Cost Allocation Methods

### Method 1: Namespace-based

```
Simplest approach:
- Each team = 1 namespace
- Cost = (namespace resources / cluster resources) × cluster cost

Pros:
+ Simple to implement
+ Clear ownership boundaries

Cons:
- No sub-team allocation
- Doesn't handle shared services well
- All cluster cost split, including system overhead

Formula:
team_cost = Σ(pod_cpu_request × cpu_cost + pod_memory_request × memory_cost)
         where pods in namespace
```

### Method 2: Label-based

```
More flexible:
- Label pods with team, product, environment
- Cost allocation follows labels

Example labels:
labels:
  team: product
  product: search
  environment: production
  cost-center: CC-1234

Formula:
team_cost = Σ(pod resources) WHERE pod.labels.team = "X"
```

### Method 3: Request-based (Kubecost)

```
Most accurate:
- Measures actual resource requests
- Accounts for node type, zone, pricing model
- Handles shared resources (PV, LoadBalancer)

Formula:
allocated_cost = (pod.cpu_request / node.cpu_capacity) × node.hourly_cost × hours
                + (pod.memory_request / node.memory_capacity) × node.hourly_cost × hours
                + pv.cost (if any)
                + network_cost (if measured)
```

### Shared Cost Distribution

```
Shared services (monitoring, ingress, DNS):
- Option A: Split equally among teams
- Option B: Split proportionally to team usage
- Option C: Platform team pays (subsidized)

Example (Method B):
cluster_cost = $10,000
shared_cost = $1,500 (monitoring + ingress + system)
team_allocated_cost = $10,000 - $1,500 = $8,500

Team A usage: 40% of team resources → $3,400
Team A shared: 40% × $1,500 = $600
Team A total: $4,000
```

---

## 3. Spot vs Reserved vs On-Demand Decision Matrix

### AWS EC2 Pricing Comparison

```
Instance: m5.xlarge, us-east-1

Pricing Model              | $/hour  | $/month | Discount | Commitment  | Risk
───────────────────────────┼─────────┼─────────┼──────────┼─────────────┼──────
On-Demand                  | $0.192  | $140    | 0%       | None        | None
1-year Reserved (All Up)   | $0.120  | $88     | 37.5%    | 1 year      | Low
1-year Reserved (Convert)  | $0.127  | $92     | 34%      | 1 year      | Lower
3-year Reserved (All Up)   | $0.081  | $59     | 58%      | 3 years     | Low
3-year Reserved (Convert)  | $0.087  | $63     | 55%      | 3 years     | Lower
Compute Savings Plan 1yr   | $0.121  | $88     | 37%      | 1 year      | Lower
Compute Savings Plan 3yr   | $0.077  | $56     | 60%      | 3 years     | Lower
Spot Instance              | ~$0.058 | ~$42    | 70%      | None        | Reclaim risk
```

### Decision Tree

```
Workload characteristics? 
│
├── Stateful, stateful database, cannot be interrupted?
│   └── YES → On-Demand hoặc Reserved
│       ├── Baseline (predictable)? → Reserved/Savings Plan
│       └── Bursty? → On-Demand
│
├── Stateless, can restart?
│   ├── Long-running baseline → Savings Plan
│   └── Flexible/bursty → Mix of Spot + On-Demand
│
├── Batch jobs, CI/CD, training?
│   └── Spot Instances (significant savings)
│
└── Development/testing?
    └── On-Demand (low usage, flexibility > savings)
```

### Optimal Mix Strategy

```
Baseline load: 60-70% Reserved/Savings Plan (locked in)
Variable load: 20-30% On-Demand
Burst/batch: 10% Spot (or more if fault-tolerant)

Example: 10 nodes needed on average, up to 15 at peak
├── 6 nodes: 3-year Compute Savings Plan (60% savings)
├── 4 nodes: On-Demand (handle variability)
└── Peak: Auto-scale with Spot (70% savings, fault-tolerant)

Blended cost: 50-55% of all-On-Demand
```

---

## 4. Cost Optimization Checklist (30+ items)

### Compute Optimization

- [ ] Audit all pods for over-provisioned resources (P95 actual << requests)
- [ ] Implement Vertical Pod Autoscaler (VPA) in recommendation mode
- [ ] Set LimitRange for namespace defaults
- [ ] Configure HPA for variable load services
- [ ] Enable Cluster Autoscaler / Karpenter
- [ ] Use Karpenter for aggressive consolidation
- [ ] Purchase Savings Plans / Reserved Instances for baseline
- [ ] Enable Spot instances for stateless workloads
- [ ] Scale down staging/dev environments off-hours
- [ ] Delete unused deployments/pods
- [ ] Right-size node instance types (memory-optimized for DB, compute for CPU-bound)
- [ ] Consolidate multiple small clusters if applicable

### Storage Optimization

- [ ] Migrate gp2 → gp3 (same performance, 20% cheaper)
- [ ] Delete unattached EBS volumes (zombie storage)
- [ ] Delete old EBS snapshots
- [ ] S3 Intelligent-Tiering for unpredictable access
- [ ] S3 Lifecycle policies (Standard → IA → Glacier → Delete)
- [ ] Enable S3 Intelligent-Tiering
- [ ] Compress logs before storing
- [ ] Delete old backups (beyond retention)
- [ ] Database storage right-sizing (don't over-provision)
- [ ] Consider EFS vs EBS for shared storage needs

### Network Optimization

- [ ] Audit NAT Gateway usage (expensive: $0.045/hour + $0.045/GB)
- [ ] Use VPC endpoints (Gateway) for S3 and DynamoDB (free!)
- [ ] Consider VPC endpoints (Interface) for frequently-accessed services
- [ ] Consolidate NAT Gateways if possible (1 vs 1-per-AZ)
- [ ] CloudFront for static assets (reduce EC2→S3 transfer)
- [ ] Same-AZ placement for chatty services
- [ ] Data transfer analysis (CloudWatch metrics)
- [ ] Compress API responses (reduce egress)

### Database Optimization

- [ ] Right-size RDS instance class
- [ ] Enable storage autoscaling (vs manual)
- [ ] Read replicas for read-heavy workloads (cheaper than bigger primary)
- [ ] Reserved Instances for databases (30-60% savings)
- [ ] Aurora Serverless v2 for variable workloads
- [ ] Delete old RDS snapshots
- [ ] Parameter tuning (max_connections không over-provision)

### Observability Optimization

- [ ] Review Prometheus cardinality (drop high-cardinality labels)
- [ ] Prometheus recording rules (reduce query cost)
- [ ] Shorter hot retention + object storage cold
- [ ] Log level optimization (INFO → WARN for production)
- [ ] Log sampling for high-volume services
- [ ] Tiered log retention (hot/warm/cold)
- [ ] Metrics retention: local 7d + Thanos/Mimir 1y
- [ ] Disable unused Grafana datasources

### Governance

- [ ] Mandatory tagging policy
- [ ] Budget alerts per team/environment
- [ ] Cost review cadence (weekly/monthly)
- [ ] Approval process for expensive resources
- [ ] Zombie resource detection automation
- [ ] Cost anomaly detection (AWS Cost Anomaly Detection)
- [ ] Cost allocation per team (showback/chargeback)
- [ ] Unit economics tracking (cost per transaction/user)

---

## 5. Kubecost Quick Setup

```bash
# Install Kubecost via Helm
helm repo add kubecost https://kubecost.github.io/cost-analyzer/
helm repo update

helm install kubecost kubecost/cost-analyzer \
  --namespace kubecost --create-namespace \
  --set kubecostToken="YOUR_TOKEN" \
  --set prometheus.server.persistentVolume.size=32Gi \
  --set persistentVolume.enabled=true

# Port-forward to access UI
kubectl port-forward --namespace kubecost \
  deployment/kubecost-cost-analyzer 9090

# Access: http://localhost:9090
```

### Key Kubecost Metrics

```
Allocation by:
├── Namespace
├── Label (team, product, environment)
├── Pod
├── Node
└── Service

Views:
├── Efficiency (request vs usage)
├── Shared cost distribution
├── Savings recommendations
└── Cost over time trends

Integrations:
├── AWS/GCP/Azure billing APIs
├── Prometheus (metrics source)
├── Slack (alerts)
└── PagerDuty (budget alerts)
```

---

## 6. Cloud Cost Calculator Templates

### AWS EKS Cluster Monthly Cost Estimate

```
| Component | Formula | Your Value |
|-----------|---------|-----------|
| EKS Control Plane | $73/cluster/month | $73 |
| EC2 nodes | count × instance price | $___ |
| EBS (nodes) | count × 100GB × $0.08 (gp3) | $___ |
| EBS (PVCs) | total GB × $0.08 (gp3) | $___ |
| EBS snapshots | total GB × $0.05 | $___ |
| ALB | $25/LB + data | $___ |
| NAT Gateway | $97 × count + data | $___ |
| Data transfer (cross-AZ) | GB × $0.01 | $___ |
| Data transfer (egress) | GB × $0.09 (first 10TB) | $___ |
| CloudWatch (logs + metrics) | ~$20-100 | $___ |
| **Total** | | **$___** |
```

### Savings Plans Break-even Calculator

```
On-Demand cost per month: $X
1-year SP cost per month: $X × 0.63 = $Y
Savings: $X - $Y = $Z/month

Break-even vs On-Demand if you use > 30% of committed capacity.

Recommendation: Start with SP covering 50-70% of baseline to avoid over-commit.
```

---

## 7. Cost Reporting Dashboard Design

### Executive Dashboard (Monthly)

```
┌─────────────────────────────────────────────┐
│ Total Monthly Spend: $120K (↑5% vs last mo) │
│ Budget: $130K (92% utilized)                │
├─────────────────────────────────────────────┤
│ Cost per Customer: $12.50 (↓3%)             │
│ Cost per Transaction: $0.08 (↓8%)           │
├─────────────────────────────────────────────┤
│ Savings This Month: $8K (from optimization) │
│ Projected Annual Savings: $96K              │
└─────────────────────────────────────────────┘
```

### Engineering Dashboard (Real-time)

```
┌─────────────────────────────────────────────┐
│ Top 10 Cost Services (This Month)           │
│ 1. EKS compute              $45K  (37%)     │
│ 2. RDS databases            $20K  (17%)     │
│ 3. Data transfer            $12K  (10%)     │
│ 4. S3 storage                $8K   (7%)     │
│ 5. Observability stack       $7K   (6%)     │
│ ...                                         │
├─────────────────────────────────────────────┤
│ Cost per Team (This Month)                  │
│ Team Product   $28K    (↑10%)    ⚠️         │
│ Team Order     $22K    (↓5%)      ✅        │
│ Team Data      $18K    (↑2%)                │
│ Team Platform  $15K    (↔ 0%)               │
└─────────────────────────────────────────────┘
```

### Alert Rules

```yaml
# Budget alert (80%)
- Alert: BudgetWarning
  Condition: team_cost > team_budget * 0.80
  Notify: team-lead, devops
  Severity: Warning

# Budget alert (100%)  
- Alert: BudgetExceeded
  Condition: team_cost > team_budget
  Notify: team-lead, devops, cto
  Severity: Critical

# Cost anomaly
- Alert: CostSpike
  Condition: daily_cost > avg(last_7d) * 1.5
  Notify: devops
  Severity: Warning
  Action: investigate cost driver

# Idle resources
- Alert: IdlePods
  Condition: cpu_usage < 5% AND memory_usage < 10% for 7 days
  Notify: service owner
  Severity: Info
  Action: right-size or scale down
```

---

## 8. FinOps Process Template

### Monthly Cadence

```
Week 1: Data collection
- Pull previous month costs
- Calculate per-team allocation
- Generate reports

Week 2: Analysis
- Identify top cost drivers
- Compare vs budget
- Spot optimization opportunities

Week 3: Review meeting
- Engineering + Finance + Product
- Discuss trends and outliers
- Prioritize optimization actions
- Update forecasts

Week 4: Execution
- Implement optimization actions
- Update tagging
- Adjust budgets if needed
- Prepare for next month
```

### Quarterly Review

```
- Savings Plan utilization check
- Reserved Instance coverage analysis
- Tagging compliance audit
- Zombie resource cleanup campaign
- Architecture review for cost
- Unit economics trends
- ROI of FinOps initiatives
```

---

## 9. Cost Anomaly Detection

### Simple Threshold-based

```python
# Pseudo-code
def detect_anomaly(current_cost, historical_costs):
    avg = mean(historical_costs)
    stddev = stddev(historical_costs)
    
    if current_cost > avg + 2 * stddev:
        return "HIGH_ANOMALY"
    elif current_cost > avg * 1.5:
        return "MEDIUM_ANOMALY"
    return "NORMAL"
```

### AWS Cost Anomaly Detection (managed)

```bash
aws ce create-anomaly-monitor --anomaly-monitor '{
  "MonitorName": "EKS-Cost-Monitor",
  "MonitorType": "DIMENSIONAL",
  "MonitorDimension": "SERVICE"
}'

aws ce create-anomaly-subscription --anomaly-subscription '{
  "SubscriptionName": "Daily-Email",
  "Threshold": 100,
  "Frequency": "DAILY",
  "MonitorArnList": ["MONITOR_ARN"],
  "Subscribers": [{"Type": "EMAIL", "Address": "devops@company.com"}]
}'
```

