# Day 50: Bài tập — Capstone Production Platform Design

---

## Bài 1: Easy — Single Service Production Deployment

### Context

Trước khi tackle full capstone, bạn warm up bằng cách deploy MỘT service với đầy đủ production concerns. Chọn `order-service` từ NextShop scenario.

### Yêu cầu

Deploy order-service trên kind cluster với:

1. **Complete Deployment YAML**:
   - 3 replicas với RollingUpdate strategy
   - Resource requests/limits (Guaranteed hoặc Burstable QoS)
   - Liveness, readiness, startup probes
   - Security context (non-root, readOnlyRootFilesystem)
   - Graceful shutdown (preStop hook)
   - Anti-affinity (spread across zones/nodes)

2. **Supporting Resources**:
   - ServiceAccount với minimal RBAC
   - Service (ClusterIP)
   - HPA (CPU + memory based)
   - PodDisruptionBudget (minAvailable=2)
   - NetworkPolicy (restrict ingress/egress)

3. **Configuration**:
   - ConfigMap cho non-sensitive config
   - Secret cho DB password (local, không cần external secrets)

4. **Verification**:
   - Deploy thành công với 3/3 pods ready
   - HPA triggered khi load test
   - NetworkPolicy blocks unauthorized traffic
   - Rolling update không downtime

### Expected Outcome

- Production-ready service deployment
- All probes working
- HPA scales up on load
- NetworkPolicy enforced
- Rolling update demo

### Hint

- Dùng nginx hoặc echo service đơn giản cho demo
- Test HPA bằng `hey` hoặc `k6` load test
- Test NetworkPolicy bằng `kubectl exec` từ pod khác

### Acceptance Criteria

- [ ] Deployment YAML đầy đủ với tất cả production concerns
- [ ] 3/3 pods ready
- [ ] HPA config working (demo scale up)
- [ ] NetworkPolicy enforced (test blocked traffic)
- [ ] Rolling update completes without errors
- [ ] PDB prevents more than 1 pod disruption
- [ ] ServiceAccount có minimal permissions

### Bonus Challenge

- Add VerticalPodAutoscaler recommendation mode
- Implement graceful shutdown với connection draining
- Add Prometheus annotations + simulate metrics endpoint

---

## Bài 2: Medium — Observability + Security Stack

### Context

Tiếp tục build trên Bài 1. Thêm observability và security layers đầy đủ.

### Yêu cầu

1. **Observability Stack**:
   - Deploy Prometheus + Grafana (Helm charts OK)
   - Instrument order-service với /metrics endpoint
   - Create Grafana dashboard với Golden Signals:
     - Traffic (RPS)
     - Latency (P50, P95, P99)
     - Errors (rate)
     - Saturation (CPU, memory)
   - Setup alert rules (high error rate, high latency)

2. **Logging**:
   - Deploy Loki + Promtail
   - Verify order-service logs flowing to Loki
   - Create LogQL queries cho common debugging scenarios

3. **Tracing**:
   - Deploy Tempo hoặc Jaeger
   - Configure order-service to export traces (OpenTelemetry)
   - Verify traces appear in UI

4. **Security Layer**:
   - Kyverno policies:
     - Enforce non-root
     - Require resource limits
     - Disallow privileged containers
     - Require runAsNonRoot
   - Test policies bằng cách deploy non-compliant pod → should be rejected
   - Scan container image với Trivy
   - Generate SBOM

5. **Secret Management**:
   - Install External Secrets Operator
   - Use Kubernetes secrets as backend (or local HashiCorp Vault)
   - Rotate a secret và verify pod picks up new value

### Expected Outcome

- Complete observability stack working
- Grafana dashboard showing Golden Signals
- Kyverno policies enforced
- External Secrets rotating secrets

### Hint

- `helm install prometheus prometheus-community/kube-prometheus-stack`
- Order service có thể dùng `jsonplaceholder.typicode.com` hoặc echo-server cho simulation
- Kyverno: `helm install kyverno kyverno/kyverno`

### Acceptance Criteria

- [ ] Prometheus scraping order-service metrics
- [ ] Grafana dashboard với 4 Golden Signals
- [ ] 2+ alert rules configured
- [ ] Loki aggregating logs
- [ ] Tempo/Jaeger showing traces
- [ ] ≥ 4 Kyverno policies in enforce mode
- [ ] Non-compliant pod correctly blocked
- [ ] Trivy scan report generated
- [ ] External Secrets working

### Bonus Challenge

- Add SLO dashboard với burn rate alerts
- Implement exemplar linking (metrics → traces)
- Add tempo service dependency graph

---

## Bài 3: Hard — Complete Capstone Deliverable

### Context

Đây là final deliverable của 50-day program. Tạo complete production-grade platform design cho NextShop theo scenario trong lesson.md.

### Yêu cầu

Complete tất cả 12 deliverables:

1. **Architecture Diagram** (C4 Model, 3 levels): Context, Container, Component
2. **Kubernetes Deployment Skeleton** cho ≥ 2 services với production concerns
3. **Helm Chart hoặc Kustomize Structure** cho 2 services
4. **Terraform Module Skeleton**:
   - VPC module
   - EKS module
   - RDS module
   - At least 2 environments (production + staging)
5. **GitHub Actions Pipeline**:
   - Build + test + scan + sign
   - Deploy to staging + production
   - Canary deployment
6. **Observability Plan**:
   - Metrics (Prometheus setup)
   - Logs (Loki architecture)
   - Traces (Tempo/Jaeger)
   - 3 dashboard designs (executive, service, debug)
   - 10+ alert rules
7. **Deployment Strategy**:
   - Canary hoặc Blue-Green
   - Rollback procedure
   - Traffic management
8. **Security Plan**:
   - RBAC matrix (per service, per team)
   - NetworkPolicy strategy
   - Secret management architecture
   - Image scanning pipeline
   - Compliance mapping (PCI DSS)
9. **DR Plan**:
   - RPO/RTO per component
   - Backup/restore runbook
   - DR activation procedure
   - Test schedule
10. **Cost Breakdown & Optimization**:
    - Monthly cost estimate
    - Optimization recommendations (≥ 10 items)
    - Savings vs reliability trade-offs
    - Cost per customer/transaction
11. **Top 5 Incident Runbooks**:
    - Service down
    - High latency
    - Database slow
    - Message queue lag
    - Bad deployment
12. **Final Review**:
    - Trade-offs documented (≥ 10)
    - Scale 10x analysis
    - Budget reduce 50% analysis  
    - Team scale 100 engineers analysis

### Expected Outcome

Complete production platform design document như một real-world deliverable, có thể review bởi architect/CTO và triển khai được.

### Hint

- Tham khảo lesson.md cho template và example
- Không cần implement TẤT CẢ — skeleton là đủ
- Focus vào decisions và trade-offs, không chỉ code
- Document "why" behind each decision

### Acceptance Criteria

- [ ] All 12 deliverables completed
- [ ] Architecture diagrams (C4 3 levels) using mermaid
- [ ] Kubernetes YAML cho ≥ 2 services (production-grade)
- [ ] Terraform skeleton (modules + environments)
- [ ] CI/CD pipeline YAML đầy đủ stages
- [ ] 3 Grafana dashboard designs
- [ ] 10+ alert rules
- [ ] RBAC matrix documented
- [ ] DR plan với RPO/RTO per component
- [ ] Cost breakdown với optimization recommendations
- [ ] 5 incident runbooks
- [ ] Trade-off analysis comprehensive

### Bonus Challenge

- Deploy actual components trên kind cluster (at least 2 services)
- Create video walkthrough of architecture
- Write ADRs (Architecture Decision Records) cho top 5 decisions
- Design chaos engineering test plan
- Estimate unit economics (cost per order processed)

---

## Solutions

<details>
<summary>Solution Bài 1: Single Service Production Deployment</summary>

### Setup

```bash
kind create cluster --name capstone-easy --config=<(cat <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
- role: worker
EOF
)

kubectl create namespace production
```

### Complete Deployment

```yaml
# Apply the order-service.yaml from lesson.md (Section 4)
# with modifications for kind (remove istio references, use simple echo server)

cat <<'EOF' | kubectl apply -f -
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service
  namespace: production
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service-config
  namespace: production
data:
  LOG_LEVEL: info
  SERVICE_NAME: order-service
---
apiVersion: v1
kind: Secret
metadata:
  name: order-service-secret
  namespace: production
type: Opaque
stringData:
  DB_PASSWORD: demo-password
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      serviceAccountName: order-service
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        fsGroup: 1001
      containers:
      - name: app
        image: hashicorp/http-echo:0.2.3
        args: ["-text=OK", "-listen=:8080"]
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: order-service-config
        - secretRef:
            name: order-service-secret
        resources:
          requests:
            cpu: 100m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: order-service
              topologyKey: kubernetes.io/hostname
      terminationGracePeriodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: production
spec:
  selector:
    app: order-service
  ports:
  - port: 8080
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service
  namespace: production
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: order-service
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: order-service
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - port: 8080
  egress:
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - port: 53
      protocol: UDP
EOF
```

### Verification

```bash
# Check pods
kubectl get pods -n production

# Test service
kubectl port-forward svc/order-service -n production 8080:8080 &
curl http://localhost:8080

# Load test
kubectl run load-test --image=williamyeh/hey --rm -it --restart=Never -- \
  hey -z 60s -c 50 http://order-service.production:8080/

# Watch HPA
kubectl get hpa -n production -w

# Rolling update test
kubectl set image deploy/order-service app=hashicorp/http-echo:0.2.4 -n production
kubectl rollout status deploy/order-service -n production

# Cleanup
kind delete cluster --name capstone-easy
```

</details>

<details>
<summary>Solution Bài 2: Observability + Security (Abbreviated)</summary>

```bash
kind create cluster --name capstone-medium

# Install Prometheus + Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin

# Install Loki stack
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki-stack \
  --namespace monitoring

# Install Tempo
helm install tempo grafana/tempo \
  --namespace monitoring

# Install Kyverno
helm repo add kyverno https://kyverno.github.io/kyverno/
helm install kyverno kyverno/kyverno \
  --namespace kyverno --create-namespace

# Install External Secrets
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace

# Apply Kyverno policies
kubectl apply -f - <<'EOF'
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-non-root
spec:
  validationFailureAction: Enforce
  rules:
  - name: check-non-root
    match:
      resources:
        kinds: [Pod]
    validate:
      message: "Must run as non-root"
      pattern:
        spec:
          =(securityContext):
            =(runAsNonRoot): true
EOF

# Port-forward Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
echo "Grafana: http://localhost:3000 (admin/admin)"
```

</details>

<details>
<summary>Solution Bài 3: Complete Capstone (Outline)</summary>

Xem `lesson.md` — provides complete skeleton cho all 12 deliverables.

### Deliverable Structure

```
nextshop-platform/
├── architecture/
│   ├── c4-context.md
│   ├── c4-container.md
│   ├── c4-component-order.md
│   └── adrs/
│       ├── 0001-choose-eks.md
│       ├── 0002-canary-deployment.md
│       ├── 0003-warm-dr-strategy.md
│       ├── 0004-self-host-postgres.md
│       └── 0005-finops-strategy.md
├── kubernetes/
│   ├── base/
│   │   ├── order-service/
│   │   ├── product-service/
│   │   └── api-gateway/
│   └── overlays/
│       ├── production/
│       ├── staging/
│       └── dr/
├── terraform/
│   ├── modules/
│   │   ├── vpc/
│   │   ├── eks/
│   │   ├── rds/
│   │   └── msk/
│   └── environments/
│       ├── production/
│       ├── staging/
│       └── dr/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-staging.yml
│       └── deploy-production.yml
├── observability/
│   ├── prometheus/
│   │   └── rules/
│   ├── grafana/
│   │   └── dashboards/
│   └── tempo/
├── security/
│   ├── rbac/
│   ├── kyverno-policies/
│   └── external-secrets/
├── runbooks/
│   ├── 01-service-down.md
│   ├── 02-high-latency.md
│   ├── 03-database-slow.md
│   ├── 04-kafka-lag.md
│   └── 05-bad-deployment.md
├── dr/
│   ├── failover-runbook.md
│   ├── backup-strategy.md
│   └── test-plan.md
└── README.md
    ├── Architecture overview
    ├── Getting started
    ├── Cost analysis
    ├── Decisions & trade-offs
    └── Future roadmap
```

Complete solutions có thể tham khảo trong lesson.md. Focus:
1. Hiểu WHY behind each decision
2. Document trade-offs thoroughly
3. Create executable skeleton (không cần full implementation)

</details>

