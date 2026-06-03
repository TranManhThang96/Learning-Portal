# Day 32 — Platform Bootstrap Cheat Sheet & Reference

> **Reference document cho Day 32 — Platform Bootstrap Layer**
> Chứa: bootstrap matrix, command cheat sheet, comparison tables, security checklist

---

## A. Bootstrap Order Quick Reference

### Phase Timeline

```
t=0    Terraform helm upgrade --install argocd          (manual bootstrap)
t=2m   ArgoCD API server online
t=5m   ArgoCD UI accessible (LoadBalancer ready)
t=10m  AppProject + root AppOfApps synced
t=15m  cert-manager (wave 1)      → ClusterIssuer ready
t=20m  external-secrets (wave 2)  → ClusterSecretStore ready
t=25m  ingress-nginx (wave 3)     → Controller + LoadBalancer ready
t=30m  prometheus (wave 4)       → Prometheus + Grafana ready
t=35m  app workloads (wave 5)     → microservices running
```

### Dependency Checklist

| # | Component | Prerequisite | Dependencies | Approx Time |
|---|-----------|-------------|--------------|-------------|
| 0 | kind/EKS cluster | Day 30 output | None | 5-10 min |
| 1 | ArgoCD (Helm) | cluster | None | 2-5 min |
| 2 | AppProject + root | ArgoCD | ArgoCD up | 1 min |
| 3 | cert-manager | ArgoCD | None | 5-10 min |
| 4 | external-secrets | ArgoCD | IRSA (Day 30) | 5 min |
| 5 | ingress-nginx | cert-manager, ESO | None | 3-5 min |
| 6 | prometheus | ArgoCD | None | 5-10 min |
| 7 | App of Apps (apps) | All above | Day 33 | 5 min |

---

## B. ArgoCD Bootstrap Commands Cheat Sheet

```bash
# ═══════════════════════════════════════════════════════
# ARGO CD BOOTSTRAP
# ═══════════════════════════════════════════════════════

# Cài ArgoCD bằng Helm
helm repo add argo https://argoproj.github.io/argo-helm && helm repo update
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --version 7.7.11 \
  --set server.service.type=LoadBalancer \
  --wait --timeout 5m

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Get ArgoCD server endpoint
kubectl get svc -n argocd argocd-server \
  -o jsonpath='{.status.loadBalancer.ingress[0]}'

# Login ArgoCD CLI
argocd login <server> --username admin --password <pwd> --insecure

# Patch ArgoCD SA với IRSA (Mode B)
kubectl annotate sa argocd-server -n argocd \
  eks.amazonaws.com/role-arn=arn:aws:iam::ACCOUNT:role/ROLE_NAME

# ═══════════════════════════════════════════════════════
# ARGO CD APP MANAGEMENT
# ═══════════════════════════════════════════════════════

argocd app list                           # List all apps
argocd app get <app-name>                 # Get app details
argocd app sync <app-name>                # Manual sync
argocd app sync <app-name> --force        # Force replace
argocd app rollback <app-name>            # Rollback to previous
argocd app set <app-name> --auto-prune    # Set auto-prune
argocd app set <app-name> --self-heal     # Set self-heal
argocd app history <app-name>             # Show revision history
argocd app manifests <app-name>           # Show rendered manifests
argocd app diff <app-name>                # Show diff vs cluster
argocd app sync <app-name> --dry-run      # Preview sync

# ═══════════════════════════════════════════════════════
# EXTERNAL SECRETS
# ═══════════════════════════════════════════════════════

# Verify ESO controller running
kubectl get pods -n external-secrets
kubectl get clustersecretstore

# Create ASM secret (Mode B)
aws secretsmanager create-secret \
  --name capstone/dev/api-service/database \
  --secret-string '{"url":"postgresql://user:pass@host:5432/db"}' \
  --region us-east-1

# Manual refresh ESO
kubectl get externalsecret -A
# ESO auto-refresh theo refreshInterval, không có manual trigger
# Workaround: xóa K8s Secret → ESO tạo lại ngay

# ═══════════════════════════════════════════════════════
# CERT MANAGER
# ═══════════════════════════════════════════════════════

# Verify ClusterIssuer
kubectl get clusterissuer
kubectl describe clusterissuer selfsigned-issuer

# Watch certificate creation
kubectl get certificate -w
kubectl describe certificate test-tls

# Check cert-manager pods
kubectl get pods -n cert-manager

# ACM certificate ARN (Mode B)
aws acm list-certificates \
  --query 'CertificateSummaryList[?DomainName==`*.capstone.dev`]'

# ═══════════════════════════════════════════════════════
# INGRESS + PROMETHEUS
# ═══════════════════════════════════════════════════════

# NGINX Ingress
kubectl get pods -n ingress-nginx
kubectl get ingressclass

# AWS LB Controller (Mode B)
kubectl get pods -n kube-system | grep aws-load-balancer
kubectl get ingress -A

# Prometheus
kubectl get pods -n monitoring
kubectl port-forward -n monitoring svc/prometheus-operated 9090 &
kubectl port-forward -n monitoring svc/prometheus-grafana 3030 &

# Prometheus targets (verify scraping)
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Grafana default credentials (Mode A, empty adminPassword)
# kubectl get secret -n monitoring prometheus-grafana -o jsonpath='{.data.admin-password}' | base64 -d
# Username: admin
```

---

## C. Helm Chart Version Quick Reference

| Chart | Repository | Min Version | Tested Version | Notes |
|-------|-----------|------------|---------------|-------|
| argo/argo-cd | https://argoproj.github.io/argo-helm | 7.x | 7.7.11 | Check https://artifacthub.io/packages/helm/argo/argo-cd |
| cert-manager | https://charts.jetstack.io | 1.14+ | 1.16.3 | Requires k8s 1.26+ for 1.16 |
| external-secrets | https://charts.external-secrets.io | 2.x | 2.4.1 | Serves stable `external-secrets.io/v1`; install CRDs before `ExternalSecret` manifests |
| ingress-nginx | https://kubernetes.github.io/ingress-nginx | 4.8+ | 4.11.1 | ingressClassName: nginx |
| kube-prometheus-stack | https://prometheus-community.github.io/helm-charts | 45+ | 60.3.0 | Heavy chart — 256Mi memory limit dev |

---

## D. Terraform vs ArgoCD vs Hybrid — Decision Matrix

```
┌──────────────────────────────────────────────────────────────────┐
│ COMPONENT              │ TERRAFORM  │  ARGO CD  │  HYBRID        │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ ArgoCD Helm release    │     ✅     │     ❌    │  TERRAFORM    │
│                        │ (bootstrap)│ (circular)│  (Day 32 lab) │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ IRSA/IAM roles         │     ✅     │     ❌    │  TERRAFORM    │
│                        │ (Day 30)   │ (out of   │  (Day 30)    │
│                        │            │  scope)   │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ ESO Helm release        │     ❌     │     ✅    │  ARGO CD      │
│                        │ (not GitOps)│ (GitOps) │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ cert-manager            │     ❌     │     ✅    │  ARGO CD      │
│                        │ (Helm only)│ (GitOps)  │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ Ingress Controller      │     ❌     │     ✅    │  ARGO CD      │
│                        │            │           │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ Prometheus Stack        │     ❌     │     ✅    │  ARGO CD      │
│                        │            │           │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ App workloads           │     ❌     │     ✅    │  ARGO CD      │
│ (Day 33+)              │            │ (AppSet)  │  (Day 33)    │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ Network infra (VPC)    │     ✅     │     ❌    │  TERRAFORM    │
│                        │ (Day 29)   │ (out of   │               │
│                        │            │  scope)   │               │
├────────────────────────┼────────────┼───────────┼────────────────┤
│ EKS Cluster             │     ✅     │     ❌    │  TERRAFORM    │
│                        │ (Day 30)   │ (out of   │  (Day 30)    │
│                        │            │  scope)   │               │
└────────────────────────┴────────────┴───────────┴────────────────┘
```

**Legend:**
- ✅ = Recommended
- ❌ = Not recommended / not applicable
- "HYBRID" column = Capstone recommended approach

---

## E. ESO — ClusterSecretStore Configuration Reference

### Mode A: Kubernetes Secret Store (no IRSA needed)

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    kubernetes:
      server:
        caProvider:
          type: ConfigMap
          name: kube-root-ca.crt
          key: ca.crt
      auth:
        defaultCredentials:
          enabled: true  # Uses pod SA token automatically
```

**Limitation:** Chỉ hoạt động khi ESO nằm cùng cluster. Không dùng cho multi-cluster secret management.

### Mode B: AWS Secrets Manager (IRSA required)

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets          # SA name
            namespace: external-secrets     # SA namespace
```

### Mode B: HashiCorp Vault (for enterprise)

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.internal:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "eso-reader"
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

---

## F. cert-manager — ACME Solver Reference

### HTTP01 Challenge (dùng Ingress)

```yaml
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@capstone.dev
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

### DNS01 Challenge (Route53 — Mode B production)

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@capstone.dev
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          route53:
            region: us-east-1
            # IAM role cần quyền: route53:GetChange, route53:ChangeResourceRecordSets
            # Dùng IRSA annotation trên cert-manager SA
        selector:
          dnsZones:
            - "capstone.dev"
```

**DNS01 vs HTTP01:**

| | HTTP01 | DNS01 |
|-|--------|-------|
| Challenge type | File-based (Ingress) | DNS record |
| Requirement | Public Ingress | DNS provider API key |
| Wildcard support | ❌ | ✅ |
| Validation time | ~30s | ~60s |
| Port 80 required | ✅ | ❌ |
| Suitable for | Dev, staging | Production, wildcard |
| ACME provider | Let's Encrypt | Any ACME (including DigiCert for enterprise) |

---

## G. NGINX Ingress — Annotation Quick Reference

```yaml
annotations:
  # ─── TLS ───────────────────────────────────────────────
  cert-manager.io/cluster-issuer: "selfsigned-issuer"  # or letsencrypt-prod
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/force-ssl-redirect: "true"

  # ─── Rate Limiting ─────────────────────────────────────
  nginx.ingress.kubernetes.io/limit-rps: "10"
  nginx.ingress.kubernetes.io/limit-connections: "100"

  # ─── Rewrite ───────────────────────────────────────────
  nginx.ingress.kubernetes.io/rewrite-target: /
  nginx.ingress.kubernetes.io/proxy-body-size: "50m"

  # ─── Timeouts ──────────────────────────────────────────
  nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "300"

  # ─── Cors ──────────────────────────────────────────────
  nginx.ingress.kubernetes.io/enable-cors: "true"
  nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.capstone.dev"
```

---

## H. AWS LB Controller — Annotation Reference

```yaml
annotations:
  # ─── ALB Settings ──────────────────────────────────────
  alb.ingress.kubernetes.io/scheme: internet-facing
  alb.ingress.kubernetes.io/scheme: internal
  alb.ingress.kubernetes.io/target-type: ip
  alb.ingress.kubernetes.io/target-type: instance
  alb.ingress.kubernetes.io/ip-address-type: ipv4

  # ─── TLS ───────────────────────────────────────────────
  alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:ACCOUNT:certificate/ID
  alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06

  # ─── Health Check ──────────────────────────────────────
  alb.ingress.kubernetes.io/healthcheck-path: /health
  alb.ingress.kubernetes.io/healthcheck-port: "80"
  alb.ingress.kubernetes.io/healthcheck-protocol: HTTP
  alb.ingress.kubernetes.io/success-codes: "200,302"

  # ─── Rules ─────────────────────────────────────────────
  alb.ingress.kubernetes.io/actions.api-service: |
    {
      "Type":"forward","TargetGroupArn":"arn:aws:elasticloadbalancing:..."
    }
  alb.ingress.kubernetes.io/rules: |
    [
      {
        "Path":"/api/*",
        "Backend": {
          "ServiceName": "api-service",
          "ServicePort": 8080
        }
      }
    ]

  # ─── WAF ────────────────────────────────────────────────
  alb.ingress.kubernetes.io/wafv2-web-acl-arn: arn:aws:wafv2:...

  # ─── Access Log ─────────────────────────────────────────
  alb.ingress.kubernetes.io/load-balancer-attributes: access_logs.s3.enabled=true
```

---

## I. Prometheus Stack — Essential Config Reference

```yaml
# values.yaml for kube-prometheus-stack (abbreviated)

prometheus:
  prometheusSpec:
    replicas: 1                          # Dev: 1, HA prod: 2
    retention: 15d                       # Dev: 15d, prod: 30d+
    retentionSize: 50GB                  # Storage estimate: 1 sample/s × 15d × 1KB
    evaluationInterval: 30s              # Rule evaluation
    scrapeInterval: 30s                  # Scrape frequency
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
      limits:
        cpu: 1000m
        memory: 1Gi
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3
          resources:
            requests:
              storage: 10Gi
    # Scrape configs
    podMonitorSelector:
      matchLabels:
        release: prometheus
    ruleSelector:
      matchLabels:
        release: prometheus
    # Exclude self from scrape
    remoteWrite: []  # Add Thanos/receiver for long-term storage

grafana:
  adminPassword: ""  # Empty = set by ESO
  persistence:
    enabled: false  # Dev: false, prod: true
  ingress:
    enabled: false  # Dev: port-forward, prod: true
  sidecar:
    datasources:
      enabled: true
    dashboards:
      enabled: true
      defaultDatasourceUid: prometheus

alertmanager:
  enabled: false  # Dev: false, prod: true

# Disable heavy components in kind
kubeEtcd:
  enabled: false
kubeControllerManager:
  enabled: false
kubeScheduler:
  enabled: false
kubeProxy:
  enabled: false
nodeExporter:
  enabled: true  # Node metrics
kubeStateMetrics:
  enabled: true  # K8s object metrics
```

---

## J. Security Checklist — Platform Bootstrap

### Pre-bootstrap
- [ ] IRSA roles đã tạo từ Day 30
- [ ] AWS Secrets Manager có secret placeholder (Mode B)
- [ ] GitHub token cho ArgoCD repo access đã lưu trong ESO
- [ ] ArgoCD Helm chart version pinned (không dùng `latest`)
- [ ] Domain/resolution plan (MetalLB IP range / Route53 hosted zone)

### During bootstrap
- [ ] ArgoCD admin password không phải default
- [ ] ArgoCD SA không có cluster-admin role không cần thiết
- [ ] ESO ClusterSecretStore verify: Mode A (no IRSA), Mode B (IRSA annotation đúng)
- [ ] cert-manager ClusterIssuer = self-signed (Mode A) hoặc ACM/LetsEncrypt (Mode B)
- [ ] NGINX Ingress Controller không expose toàn bộ cluster (namespace-scoped RBAC)
- [ ] Prometheus không có public ingress

### Post-bootstrap
- [ ] ArgoCD UI accessible qua HTTPS
- [ ] ArgoCD AppProject có `destination` restriction (không allow wildcard server)
- [ ] ESO có thể resolve secret từ remote store
- [ ] Certificate cho test Ingress = Ready
- [ ] Prometheus scrape target: kube-apiserver, kubelet, node-exporter, kube-state-metrics
- [ ] Prometheus retention set (< 30d cho dev)
- [ ] Grafana admin password đã set (thủ công hoặc ESO)

---

## K. AWS Cost Warning — Platform Layer (Mode B)

| Resource | Cost/tháng | Notes |
|----------|-----------|-------|
| ArgoCD ALB (NGINX Ingress) | ~$16-20 | Mode A: MetalLB free |
| Prometheus ALB (if expose) | ~$0-16 | Dev: port-forward, prod: ALB |
| ACM Certificate | $0 | Public certificate free |
| ESO (no AWS cost) | $0 | ESO controller free, ASM secrets $0.40/secret |
| CloudWatch metrics (~500 metrics) | ~$15 | Dev: disable CW, dùng Prometheus remote_write |
| **Total platform LB cost** | **~$31-51/tháng** | Chỉ ALB + CW |

**Cost reduction Mode B:**
- Không expose Prometheus/Grafana qua ALB → dùng kubectl port-forward → tiết kiệm ~$16/tháng
- Không enable CloudWatch metrics → dùng Prometheus remote_write → tiết kiệm ~$15/tháng
- Chỉ ArgoCD ALB ($16) + ACM ($0) = ~$16/tháng

---

## L. Cleanup Reference

```bash
# ═══════════════════════════════════════════════════════
# CLEANUP ORDER (reverse of bootstrap)
# ═══════════════════════════════════════════════════════

# 1. Xóa app of apps root (không xóa ArgoCD itself)
kubectl delete -f argocd/platform-apps/applications/5-app-of-apps.yaml

# 2. Xóa platform apps (theo reverse order)
kubectl delete -f argocd/platform-apps/applications/4-prometheus.yaml
kubectl delete -f argocd/platform-apps/applications/3-ingress-nginx.yaml
kubectl delete -f argocd/platform-apps/applications/2-external-secrets.yaml
kubectl delete -f argocd/platform-apps/applications/1-cert-manager.yaml

# 3. Xóa AppProject
kubectl delete appproject platform

# 4. Xóa ArgoCD
helm uninstall argocd -n argocd
kubectl delete namespace argocd --wait

# 5. Mode B: Xóa ALB (AWS LB Controller cleanup)
helm uninstall aws-load-balancer-controller -n kube-system

# 6. Mode B: Xóa ACM certificates
aws acm list-certificates --query 'CertificateSummaryList[*].CertificateArn' --output text \
  | xargs -I{} aws acm delete-certificate --certificate-arn {}

# 7. Xóa ASM secrets (cleanup demo)
aws secretsmanager delete-secret \
  --secret-id capstone/dev/api-service/database \
  --force-delete-recovery-window

# 8. Mode A: Xóa kind cluster
kind delete cluster --name capstone-dev

# 9. Mode B: Xóa EKS cluster (Day 30 cleanup)
cd terraform/environments/dev && terraform destroy -auto-approve
```
