# Day 32 — Platform Bootstrap Layer

> **Capstone Production-Grade Phase — Day 4 of 8**
> **Thời lượng:** 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)
> **Prerequisite:** Hoàn thành Day 28-31 (Architecture + Network + K8s/IAM + Data layer)
> **Output:** ArgoCD bootstrap + platform App of Apps/ApplicationSet + External Secrets + Ingress + Cert Manager + Prometheus

---

## 1. Mục tiêu ngày học

- Hiểu bootstrap order và dependency graph giữa các platform components (ArgoCD → ESO → Cert Manager → Ingress → Prometheus)
- Phân biệt 3 chiến lược bootstrap: Terraform `helm_release`, ArgoCD Application/ApplicationSet, hybrid
- Cài đặt ArgoCD (Mode A: kind; Mode B: EKS) và bootstrap platform apps qua App of Apps hoặc ApplicationSet
- Triển khai External Secrets Operator, cert-manager (self-signed / ACM), NGINX Ingress Controller / AWS LB Controller, kube-prometheus-stack
- Hiểu trade-offs: terraform quản lý Helm vs ArgoCD quản lý Helm vs hybrid — chọn đúng theo context

---

## 2. Bối cảnh thực tế

### Vấn đề khi không có bootstrap layer rõ ràng

Sau khi cluster đã up (Day 30), team thường mắc 3 lỗi:

**1. Deploy apps trước khi setup secrets/ingress/cert**

```
ArgoCD sync app
  → app cần DB password (ExternalSecret chưa có)
  → app cần TLS cert (cert-manager chưa có)
  → app expose via Ingress (Ingress Controller chưa có)
  → 5 lần retry, log đầy error, developer frustrated
```

**2. Không có bootstrap order — circular dependency**

```
ArgoCD cần Ingress để expose UI
Ingress cần Cert Manager để issue certificate
Cert Manager cần DNS (External Secret chưa resolve)
External Secret cần ArgoCD ServiceAccount để auth
→ Circular: ArgoCD → Ingress → Cert Manager → ESO → ArgoCD
```

**3. Terraform + ArgoCD quản lý cùng 1 Helm release**

```
Terraform apply: tạo argocd HelmRelease (namespace=argocd)
ArgoCD sync: thấy HelmRelease khác version → OutOfSync
→ ArgoCD tự revert về version trong Git
→ Terraform下次 apply lại overwrite
→ Drift loop: Terraform ←→ ArgoCD fighting each other
```

**Lesson hôm nay:** Giải quyết cả 3 vấn đề bằng:
1. Bootstrap dependency diagram rõ ràng (không circular)
2. Chọn đúng bootstrap strategy cho từng component
3. Dùng App of Apps hoặc ApplicationSet để bootstrap platform apps thông qua ArgoCD

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Bootstrap Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PLATFORM BOOTSTRAP ORDER                              │
│                                                                         │
│  PHASE 1 — CORE (bắt buộc trước, không có exception)                   │
│                                                                         │
│  ┌──────────────┐                                                      │
│  │ 1. ArgoCD   │ ← Namespace: argocd                                   │
│  │ (Helm chart) │    ArgoCD API Server + Repo Server + Controller       │
│  └──────┬───────┘    UI exposed via Service (NodePort/LoadBalancer)   │
│         │                                                              │
│         │ ArgoCD chạy → sync các app khác                             │
│         ▼                                                              │
│  ┌──────────────┐                                                      │
│  │ 2. Cert-     │ ← Namespace: cert-manager                           │
│  │    Manager   │    ClusterIssuer (self-signed hoặc ACM)              │
│  └──────┬───────┘    Cần Issuer/ClusterIssuer TRƯỚC Ingress           │
│         │                                                              │
│         │ Cert Manager có thể tự resolve (self-signed)                 │
│         │ ACM/challenger cần DNS + ESO                                 │
│         ▼                                                              │
│  ┌──────────────┐                                                      │
│  │ 3. External  │ ← Namespace: external-secrets                        │
│  │    Secrets   │    ClusterSecretStore (ASM/GH/Vault)                 │
│  │    Operator  │    StoreSecret CRD trước khi dùng ExternalSecret    │
│  └──────┬───────┘    IRSA annotation đã setup từ Day 30 (Mode B)     │
│         │                                                              │
│         │ ESO tạo K8s Secret → app pod đọc được                       │
│         ▼                                                              │
│  PHASE 2 — NETWORKING                                                  │
│                                                                         │
│  ┌──────────────┐                                                      │
│  │ 4. Ingress    │ ← Namespace: ingress-nginx (Mode A)                 │
│  │ Controller   │    hoặc kube-system (AWS LB Controller, Mode B)     │
│  └──────┬───────┘    WAIT: Cert Manager + ESO ready                   │
│         │                                                              │
│         │ Ingress Controller tạo LoadBalancer                          │
│         │ Ingress resource cần Certificate (Cert Manager)              │
│         ▼                                                              │
│  ┌──────────────┐                                                      │
│  │ 5. DNS /     │ ← Route53 (Mode B) hoặc /etc/hosts (Mode A)         │
│  │    Ingress   │    TLS cert tự động issue sau khi Ingress created   │
│  │    Resource  │                                                      │
│  └──────┬───────┘                                                      │
│         │                                                              │
│         ▼                                                              │
│  PHASE 3 — OBSERVABILITY                                               │
│                                                                         │
│  ┌──────────────┐                                                      │
│  │ 6. Prometheus│ ← Namespace: monitoring                              │
│  │ Stack       │    Prometheus + Grafana + AlertManager               │
│  │             │    ServiceMonitor/PodMonitor cần RBAC                 │
│  └──────────────┘                                                      │
│                                                                         │
│  PHASE 4 — APPS (Day 33+)                                              │
│                                                                         │
│  ┌──────────────┐                                                      │
│  │ 7. App of    │ ← ArgoCD Application / ApplicationSet               │
│  │    Apps Root │    Sync: api-service, worker, frontend              │
│  └──────────────┘    (không gọi Terraform nữa)                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc vàng:**
- **Phase 1 (ArgoCD + Cert Manager + ESO)**: Không có gì phụ thuộc circular. Mỗi component đứng độc lập.
- **Phase 2 (Ingress)**: Cần cả 3 component phase 1
- **Phase 3 (Prometheus)**: Độc lập, có thể cài song song với Phase 2
- **Phase 4 (Apps)**: Cần tất cả → cài cuối cùng

### 3.2 ArgoCD Bootstrap — Cài đặt lần đầu

Cài ArgoCD bằng Helm (hoặc manifests) trước khi ArgoCD quản lý bất cứ thứ gì khác:

```bash
# Mode A + B: ArgoCD bootstrap via Helm
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 7.4.2 \
  --set server.service.type=LoadBalancer \
  --values - <<'EOF'
server:
  service:
    type: LoadBalancer  # MetalLB (Mode A) hoặc AWS LB (Mode B)
  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod
    hosts:
      - argocd.capstone.local  # Mode A
      - argocd.capstone.dev    # Mode B
    tls:
      - secretName: argocd-tls
        hosts:
          - argocd.capstone.local
redis:
  ha:
    enabled: false  # dev mode, production nên bật
EOF
```

**Lưu ý quan trọng:** ArgoCD được cài BẰNG HELM — nhưng ArgoCD không quản lý chính nó (self-managed = false trong Application). Sau đó, ArgoCD quản lý các platform app khác.

### 3.3 External Secrets Operator — Tổng quan

ESO là bridge giữa external secret store và Kubernetes Secret:

```
┌──────────────────┐     Pull secrets     ┌──────────────────────────┐
│ External Secret  │ ──────────────────▶  │ Kubernetes Secret        │
│ Store           │                      │ (actual workload dùng)   │
│ (ASM/GH/Vault)  │  ESO controller     └──────────────────────────┘
└──────────────────┘  reconcile loop
```

**ESO CRD workflow:**

```yaml
# Step 1: ClusterSecretStore (Mode B: AWS Secrets Manager)
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      # IRSA annotation đã set từ Day 30
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets

---
# Step 2: ExternalSecret (reference Store, tạo K8s Secret)
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: api-service-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: api-service-secrets   # Tên K8s Secret được tạo
    creationPolicy: Owner       # Owner reference → auto-delete khi ES xóa
  data:
    - secretKey: database-url
      remoteRef:
        key: capstone/dev/api-service/database
        property: url
    - secretKey: redis-url
      remoteRef:
        key: capstone/dev/api-service/redis
```

**ESO refresh cycle:**
- Controller check remote secret theo `refreshInterval`
- Nếu secret thay đổi trong ASM → ESO update K8s Secret → pod nhận config mới (tùy restart)
- Không push secret vào Git (ASM = external, không trong Git)
- Không restart pod tự động — dùng `rollout restart` hoặc Reloader pattern

### 3.4 cert-manager — Issuer types

```
cert-manager issuer types:
  ├── Let's Encrypt (ACME)     ← Production, cần DNS challenge
  │     ├── HTTP01 challenge   ← Cần Ingress controller
  │     └── DNS01 challenge    ← Cần Route53/cloudflare API key
  ├── Self-signed              ← Dev/local, không verify domain
  └── CA (internal PKI)        ← Enterprise internal services
```

**Self-signed ClusterIssuer (Mode A — local):**

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: self-signed-ca
spec:
  ca:
    secretName: self-signed-ca-tls
```

**ACME ClusterIssuer (Mode B — production-like):**

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: dev@capstone.local
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          route53:
            region: us-east-1
            # IRSA: cert-manager service account có quyền Route53
        selector:
          dnsZones:
            - "capstone.dev"
```

### 3.5 Ingress Controller — NGINX vs AWS LB Controller

| Tiêu chí | NGINX Ingress (Mode A) | AWS LB Controller (Mode B) |
|----------|----------------------|---------------------------|
| Type | DaemonSet/Deployment trong cluster | Controller tạo AWS ALB bên ngoài |
| Load Balancer | NodePort → manual MetalLB | AWS ALB tự động tạo |
| TLS termination | cert-manager inject vào Secret | cert-manager + ACM hoặc cert-manager |
| Cost | $0 (cluster internal) | ALB ~$16-20/tháng |
| Annotations | `nginx.ingress.kubernetes.io/*` | `alb.ingress.kubernetes.io/*` |
| Path-based routing | ✅ | ✅ |
| Weighted routing | ✅ (nginx.ingress.kubernetes.io) | ✅ (AWS Weighted) |
| WAF integration | ❌ (cần riêng) | ✅ (AWS WAF attach được) |

**NGINX Ingress (Mode A):**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-service-ingress
  namespace: api-service
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: selfsigned-issuer
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.capstone.local
      secretName: api-service-tls
  rules:
    - host: api.capstone.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 8080
```

**AWS LB Controller (Mode B):**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-service-ingress
  namespace: api-service
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:...
    alb.ingress.kubernetes.io/list-ports: '80,443'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
spec:
  ingressClassName: alb
  rules:
    - host: api.capstone.dev
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 8080
```

### 3.6 Prometheus Stack — kube-prometheus-stack

```
kube-prometheus-stack components:
  ├── Prometheus Server        ← Metrics collection (pull-based)
  ├── Prometheus Operator      ← CRD-based Prometheus management
  ├── Alertmanager             ← Alert routing + notification
  ├── node-exporter            ← Node-level metrics (daemonset)
  ├── kube-state-metrics       ← K8s object state metrics
  ├── Grafana                  ← Metrics visualization
  └── prometheus-adapter       ← Custom metrics HPA
```

**ArgoCD sync cho Prometheus stack:**

```yaml
# Trong platform-repo: argocd/platform-apps/prometheus.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prometheus
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: "60.*"
    helm:
      valueFiles:
        - values.yaml
      parameters:
        - name: grafana.adminPassword
          value: "$(GRAFANA_ADMIN_PASSWORD)"  # Từ ESO
        - name: prometheus.prometheusSpec.retention
          value: "15d"
        - name: prometheus.prometheusSpec.replicas
          value: "1"  # Dev: 1 replica, prod: 2+
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 Bootstrap Strategy — Terraform `helm_release` vs ArgoCD Application

**Strategy 1: Terraform quản lý Helm (pure Terraform)**

```hcl
# terraform/modules/bootstrap/main.tf
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "7.4.2"
  namespace  = "argocd"
  create_namespace = true

  set {
    name  = "server.service.type"
    value = "LoadBalancer"
  }

  depends_on = [kubernetes_namespace.platform]
}
```

| Tiêu chí | Terraform helm_release |
|----------|----------------------|
| **Quản lý state** | Terraform state (IaC-first) |
| **Drift detection** | ✅ Terraform biết khi nào resource khác Terraform sửa |
| **GitOps mindset** | ❌ Không phải GitOps — infra team apply, không phải app team |
| **Sync status visibility** | ❌ ArgoCD không thấy Helm release này |
| **Rollback** | `terraform apply -target=helm_release.argocd -var=version=prev` |
| **Khi nào dùng** | Cluster infrastructure components (EKS add-ons, cluster-level) |
| **Khi nào không** | App workloads, app team cần self-service |

**Strategy 2: ArgoCD quản lý Helm (pure GitOps)**

```yaml
# platform-repo/argocd/applications/argocd.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd-platform
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://argoproj.github.io/argo-helm
    chart:argo-cd
    targetRevision: "7.4.2"
    helm:
      values: |
        server:
          service:
            type: LoadBalancer
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

| Tiêu chí | ArgoCD Application |
|----------|------------------|
| **Quản lý state** | ArgoCD reconciliation (GitOps) |
| **Drift detection** | ✅ ArgoCD tự detect + correct drift |
| **GitOps mindset** | ✅ App team tự update values trong Git |
| **Sync status visibility** | ✅ Rõ ràng trong ArgoCD UI |
| **Rollback** | `argocd app rollback argocd-platform` hoặc Git revert |
| **Khi nào dùng** | Platform add-ons, app workloads |
| **Khi nào không** | Cluster bootstrap itself (ArgoCD không tự bootstrap được) |

**Strategy 3: Hybrid Bootstrap (RECOMMENDED — dùng trong Capstone)**

```
RULE: Ai quản lý cái gì?

Terraform (infra-repo):
  ├── ArgoCD Helm release         ← Terraform làm vì ArgoCD cần có TRƯỚC
  ├── Cluster-level IRSA roles    ← infra team (Day 30)
  └── Network resources           ← infra team (Day 29)

ArgoCD (platform-repo):
  ├── External Secrets Operator
  ├── cert-manager
  ├── Ingress Controller (nginx/alb-controller)
  ├── Prometheus Stack
  └── Platform apps (Day 33+)
```

**Nguyên tắc hybrid:**

1. **Terraform quản lý ArgoCD**: Vì ArgoCD không thể tự bootstrap chính nó qua GitOps (circular dependency). Terraform cài ArgoCD lần đầu, sau đó ArgoCD quản lý mọi thứ khác.

2. **Terraform quản lý IRSA roles**: IRSA là infrastructure IAM, thuộc về infra team, không phải app team.

3. **ArgoCD quản lý mọi thứ trong cluster sau khi ArgoCD up**: ESO, cert-manager, Ingress, Prometheus, app workloads — tất cả qua GitOps.

4. **ArgoCD KHÔNG quản lý Terraform state**: Terraform state nằm ngoài scope của ArgoCD.

### 4.2 Comparison Matrix

| Tiêu chí | Terraform Helm | ArgoCD App | Hybrid (Capstone) |
|-----------|---------------|-----------|-------------------|
| **Bootstrap source of truth** | Terraform state | Git repository | Terraform (ArgoCD itself) + Git (rest) |
| **Drift handling** | Terraform plan | ArgoCD sync | ArgoCD correct drift post-terraform |
| **Self-heal** | ❌ (cần terraform apply) | ✅ | ✅ |
| **GitOps purity** | ❌ | ✅ | ✅ (ArgoCD-side) |
| **Multi-cluster** | Cần backend config | Native (cluster generator) | ArgoCD multi-cluster |
| **Helm template rendering** | Client-side | Server-side (repo-server) | Server-side |
| **Secret management** | Variable interpolation | External Secrets + Vault | ESO + ASM |
| **Setup complexity** | Trung bình | Cao (cần ArgoCD up trước) | Trung bình |
| **Team autonomy** | Thấp (cần Terraform access) | Cao (Git PR) | Cao (app team dùng Git) |

### 4.3 App of Apps vs ApplicationSet cho Bootstrap

**App of Apps (Day 21):** 1 root Application sync 1 folder chứa nhiều Application YAML.

**ApplicationSet (Day 22-23):** Controller tự generate Applications từ generator (list/git/matrix/cluster).

| Tiêu chí | App of Apps | ApplicationSet |
|----------|-----------|---------------|
| **Scalability** | OK cho < 20 apps | Tốt cho nhiều apps/env/cluster |
| **Generator** | Folder-based | list, git, cluster, matrix |
| **Progressive delivery** | Manual per app | Generator-based |
| **Bootstrap speed** | Chậm (sequential sync) | Nhanh (parallel generation) |
| **Use case** | Platform bootstrap, dev setup | Multi-env, multi-cluster production |

**Capstone recommendation:**
- Bootstrap platform apps (ESO, cert-manager, Ingress, Prometheus): **App of Apps** (đơn giản, rõ ràng)
- Bootstrap app workloads: **ApplicationSet** (matrix generator: service × env)

### 4.4 Best Practice Per Context

| Context | Bootstrap Strategy | Notes |
|---------|-------------------|-------|
| **Cá nhân học / dev** | ArgoCD quản lý tất cả (Mode A) | Không cần Terraform bootstrap |
| **Startup MVP** | Hybrid: Terraform ArgoCD, ArgoCD rest | Người/infra team quản Terraform |
| **Team 5-10 dev** | Hybrid + ApplicationSet | App team tự quản app qua Git |
| **Enterprise** | Terraform bootstrap layer + ArgoCD app layer + GitOps promotion | RBAC ArgoCD + SSO |
| **Bank/regulated** | Terraform-only bootstrap + ArgoCD read-only cho app team | Compliance audit Terraform |

### 4.5 Security Baseline cho Bootstrap

**MUST:**
- [ ] ArgoCD admin password được generate từ random string, không dùng default `admin`
- [ ] ArgoCD repo credentials là Secret, không commit password vào Git (dùng ESO để inject)
- [ ] ESO StoreSecret được tạo trước ExternalSecret
- [ ] Cert-manager có RBAC restriction (ClusterIssuer, không dùng default admin ClusterRole)
- [ ] Ingress Controller không expose internal services ra public không kiểm soát
- [ ] Prometheus không expose metrics endpoint publicly
- [ ] Helm chart versions pinned (không dùng `latest` hoặc alias tag)

**SHOULD:**
- [ ] ArgoCD `server.config` có `resource.customizations` để ignore HPAs và PodDisruptionBudgets
- [ ] ArgoCD AppProject rõ ràng: dev-team chỉ sync dev apps, không thấy prod
- [ ] Prometheus `values.yaml` có `ingress.enabled: true` với basic auth

### 4.6 Common Pitfalls

| # | Pitfall | Hệ quả | Fix |
|---|---------|--------|-----|
| 1 | ArgoCD cố quản lý chính nó (self-managed=true) | Circular: ArgoCD xóa → app bootstrap bị break | `selfHeal: false` cho ArgoCD Application |
| 2 | Terraform + ArgoCD quản lý cùng 1 Helm release | Drift loop: Terraform ←→ ArgoCD fighting | Dùng hybrid: Terraform ArgoCD, ArgoCD rest |
| 3 | Deploy Ingress trước khi Cert Manager có ClusterIssuer | Certificate ở trạng thái `Pending`, Ingress không TLS | `depends_on` hoặc ArgoCD sync wave |
| 4 | ESO ClusterSecretStore sai region/IRSA | `NoCredentialProviders` error | Verify IRSA annotation từ Day 30 |
| 5 | NGINX Ingress không có `ingressClassName` | Default IngressClass không phải nginx → 404 | Thêm `ingressClassName: nginx` |
| 6 | Prometheus scrape Prometheus itself | Self-scraping loop → OOM | exclude pod: `prometheus-operator/prometheus` |
| 7 | ArgoCD app có `automated: {}` trên prod | Git push = auto deploy prod | Prod: `automated: null`, manual sync |
| 8 | Helm chart không pinned version | `helm upgrade` pull latest → unexpected breaking change | Pin chart version trong Application spec |

---

## 5. Hands-on Lab — 60 phút

**Thời gian:** 60 phút
**Mode:** Mode A (kind, default, $0) hoặc Mode B (EKS, optional, có cost)

### Pre-requisites

**Cả 2 mode cần:**
```bash
helm version          # >= 3.14
kubectl version       # >= 1.28
argocd version        # ArgoCD CLI (optional, kubectl cũng đủ)
```

**Mode A:**
- kind cluster từ Day 30 (`kind-capstone-dev`)
- kubectl context: `kind-capstone-dev`
- MetalLB đã cài (Day 30 Step 4)

**Mode B:**
- EKS cluster từ Day 30
- kubectl context: `arn:aws:eks:us-east-1:...`
- IRSA roles đã tạo (Day 30)
- AWS LB Controller Helm release từ Day 30
- **Cost warning**: ArgoCD ALB ~$16-20/tháng, Prometheus ALB ~$16-20/tháng

---

### Part A — ArgoCD Bootstrap (Terraform hoặc Helm)

> **NOTE:** Trong Capstone hybrid pattern, Terraform bootstrap ArgoCD, sau đó ArgoCD quản lý mọi thứ khác. Trong lab hôm nay, chúng ta dùng Helm trực tiếp để đơn giản — bạn có thể chuyển thành Terraform sau.

**Step 1: Cài ArgoCD**

```bash
# Thêm ArgoCD Helm repo
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Cài ArgoCD
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 7.7.11 \
  --set server.service.type=LoadBalancer \
  --set server.ingress.enabled=true \
  --set server.ingress.className=nginx \
  --wait --timeout 5m

# Mode A: MetalLB sẽ cấp IP từ pool 192.168.1.240-250
# Mode B: AWS LB Controller tạo ALB tự động
```

**Expected output:**

```
NAME: argocd
NAMESPACE: argocd
STATUS: deployed
REVISION: 1
...
```

**Step 2: Verify ArgoCD pods**

```bash
kubectl get pods -n argocd

# Expected (tất cả Running):
# NAME                                              READY   STATUS    AGE
# argocd-applicationset-controller-...            1/1     Running   2m
# argocd-dex-server-...                             1/1     Running   2m
# argocd-notifications-controller-...               1/1     Running   2m
# argocd-redis-...                                 1/1     Running   2m
# argocd-repo-server-...                           1/1     Running   2m
# argocd-server-...                                1/1     Running   2m
```

**Step 3: Lấy ArgoCD admin password + login**

```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Get ArgoCD server URL
kubectl get svc -n argocd argocd-server -o jsonpath='{.status.loadBalancer.ingress[0]}'

# Mode A: MetalLB IP (e.g., 192.168.1.240)
# Mode B: AWS LB hostname (e.g., abc123.elb.us-east-1.amazonaws.com)

# Login bằng CLI (optional)
argocd login <argo-server-url> \
  --username admin \
  --password $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d) \
  --insecure
```

**Step 4: Patch ArgoCD server ServiceAccount cho IRSA (Mode B only)**

```bash
# Mode B: Bind ServiceAccount argocd với IRSA role để ArgoCD có quyền AWS
kubectl annotate serviceaccount argocd-server \
  -n argocd \
  eks.amazonaws.com/role-arn=arn:aws:iam::${ACCOUNT_ID}:role/capstone-dev-argocd
```

---

### Part B — Platform App of Apps Root

**Step 5: Tạo AppProject cho platform**

```bash
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  description: Platform components bootstrap
  sourceRepos:
    - "*"  # Cho phép mọi repo trong lab
  destinations:
    - namespace: "*"
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: "*"
      kind: "*"
  namespaceResourceBlacklist:
    - group: ""
      kind: Namespace
  roles:
    - name: platform-admin
      description: Platform team
      groups:
        - platform-team
      policies:
        - p, proj:platform:platform-admin,applications,*,*,allow
        - p, proj:platform:platform-admin,applications,sync,*,allow
EOF
```

**Step 6: Tạo App of Apps root Application**

```bash
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: platform-apps-root
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/<your-user>/capstone-platform.git
    path: argocd/platform-apps
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: false  # IMPORTANT: ArgoCD không tự self-heal chính nó
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
EOF
```

**Verify root app sync:**

```bash
argocd app list

# Expected:
# NAME                     CLUSTER                         NAMESPACE  STATUS  HEALTH
# platform-apps-root       https://kubernetes.default.svc  argocd     Synced  Healthy
```

---

### Part C — Platform Apps (Helm values cho từng component)

Tạo structure trong `capstone-platform/argocd/platform-apps/`:

```
capstone-platform/
└── argocd/
    └── platform-apps/
        ├── Chart.yaml
        ├── values.yaml
        ├── crds/
        │   ├── cert-manager.yaml
        │   ├── external-secrets.yaml
        │   └── prometheus-stack.yaml
        └── applications/
            ├── 1-cert-manager.yaml
            ├── 2-external-secrets.yaml
            ├── 3-ingress-nginx.yaml
            ├── 4-prometheus.yaml
            └── 5-app-of-apps.yaml
```

**File: `argocd/platform-apps/Chart.yaml`:**

```yaml
apiVersion: v2
name: platform-apps
description: ArgoCD-managed platform bootstrap
version: 0.1.0
dependencies:
  - name: cert-manager
    version: "1.16.*"
    repository: https://charts.jetstack.io
    condition: cert-manager.enabled
  - name: external-secrets
    version: "2.4.*"
    repository: https://charts.external-secrets.io
    condition: external-secrets.enabled
  - name: ingress-nginx
    version: "4.11.*"
    repository: https://kubernetes.github.io/ingress-nginx
    condition: ingress-nginx.enabled
  - name: kube-prometheus-stack
    version: "60.*"
    repository: https://prometheus-community.github.io/helm-charts
    condition: prometheus.enabled
```

**File: `argocd/platform-apps/values.yaml`:**

```yaml
# Mode A (kind/local) — dùng self-signed cert
cert-manager:
  enabled: true
  installCRDs: true
  webhook:
    enabled: true
  replicaCount: 1
  startupapicheck:
    enabled: false

external-secrets:
  enabled: true
  replicaCount: 1
  installCRDs: true
  serviceMonitor:
    enabled: false  # Dev mode, không cần monitor cho ESO

ingress-nginx:
  enabled: true
  controller:
    replicaCount: 1
    service:
      type: LoadBalancer  # MetalLB (Mode A) / AWS LB (Mode B)
    publishService:
      enabled: true
    admissionWebhooks:
      enabled: true
    metrics:
      enabled: true
      serviceMonitor:
        enabled: false
  rbac:
    create: true

prometheus:
  enabled: true
  prometheus:
    prometheusSpec:
      replicas: 1  # Dev: 1, prod: 2+
      retention: 15d
      evaluationInterval: 30s
      scrapeInterval: 30s
  grafana:
    enabled: true
    adminPassword: ""  # Set bằng ESO trong prod
    ingress:
      enabled: false  # Mode A: dùng kubectl port-forward
  alertmanager:
    enabled: false  # Dev: disable, prod: enable + Slack webhook
  kubeEtcd:
    enabled: false  # kind/EKS managed, không cần scrape etcd
```

---

### Part D — Individual Platform Applications (detailed YAML)

**File: `argocd/platform-apps/applications/1-cert-manager.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: cert-manager
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: platform
  source:
    repoURL: https://charts.jetstack.io
    chart: cert-manager
    targetRevision: v1.16.3
    helm:
      releaseName: cert-manager
      values: |
        installCRDs: true
        replicaCount: 1
        startupapicheck:
          enabled: false
        webhook:
          enabled: true
  destination:
    server: https://kubernetes.default.svc
    namespace: cert-manager
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
---
# ClusterIssuer — dùng self-signed cho Mode A
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  selfSigned: {}
```

**File: `argocd/platform-apps/applications/2-external-secrets.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-secrets
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  project: platform
  source:
    repoURL: https://charts.external-secrets.io
    chart: external-secrets
    targetRevision: 2.4.*
    helm:
      releaseName: external-secrets
      values: |
        installCRDs: true
        replicaCount: 1
        serviceMonitor:
          enabled: false
        webhook:
          enabled: true
        certController:
          enabled: true
        leaderElect:
          enabled: false  # Single replica mode
  destination:
    server: https://kubernetes.default.svc
    namespace: external-secrets
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
---
# ClusterSecretStore cho Mode A (Kubernetes Secret Store)
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend  # Mode A: mock store
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  provider:
    kubernetes:
      server:
        caProvider:
          type: ConfigMap
          name: kube-root-ca.crt
          key: ca.crt
      auth:
        # Mode A: không cần IRSA, dùng default service account
        # Mode B: chuyển sang JWT token với IRSA
        defaultCredentials:
          enabled: true
---
# Mode B: ASM Store (dùng IRSA từ Day 30)
# Uncomment khi dùng Mode B
# apiVersion: external-secrets.io/v1
# kind: ClusterSecretStore
# metadata:
#   name: aws-secrets-manager
# spec:
#   provider:
#     aws:
#       service: SecretsManager
#       region: us-east-1
#       auth:
#         jwt:
#           serviceAccountRef:
#             name: external-secrets
#             namespace: external-secrets
```

**File: `argocd/platform-apps/applications/3-ingress-nginx.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ingress-nginx
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  annotations:
    argocd.argoproj.io/sync-wave: "3"
spec:
  project: platform
  source:
    repoURL: https://kubernetes.github.io/ingress-nginx
    chart: ingress-nginx
    targetRevision: 4.11.*
    helm:
      releaseName: ingress-nginx
      values: |
        controller:
          replicaCount: 1
          service:
            type: LoadBalancer
            annotations:
              # MetalLB (Mode A): annotation không cần
              # AWS LB Controller (Mode B): annotation do LB controller tự thêm
          publishService:
            enabled: true
          admissionWebhooks:
            enabled: true
          metrics:
            enabled: true
            serviceMonitor:
              enabled: false
          resources:
            requests:
              cpu: 100m
              memory: 90Mi
            limits:
              cpu: 500m
              memory: 256Mi
          extraArgs:
            publish-status-address: ""
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress-nginx
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**File: `argocd/platform-apps/applications/4-prometheus.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: prometheus
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  annotations:
    argocd.argoproj.io/sync-wave: "4"
spec:
  project: platform
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: "60.*"
    helm:
      releaseName: prometheus
      values: |
        prometheus:
          prometheusSpec:
            replicas: 1
            retention: 15d
            evaluationInterval: 30s
            scrapeInterval: 30s
            resources:
              requests:
                cpu: 200m
                memory: 256Mi
            retentionSize: 10GB
            storageSpec:
              volumeClaimTemplate:
                spec:
                  storageClassName: standard
                  resources:
                    requests:
                      storage: 10Gi
          # Exclude Prometheus itself từ scrape targets
          podMonitorSelector:
            matchLabels:
              release: prometheus
          ruleSelector:
            matchLabels:
              release: prometheus
        grafana:
          enabled: true
          adminPassword: ""  # Set empty → được set bằng ESO trong prod
          ingress:
            enabled: false  # Dùng kubectl port-forward trong dev
          persistence:
            enabled: false  # Dev: stateless, prod: nên bật PVC
          sidecar:
            datasources:
              enabled: true
        alertmanager:
          enabled: false  # Enable trong prod với Slack/email webhook
        kubeEtcd:
          enabled: false
        kubeControllerManager:
          enabled: false
        kubeScheduler:
          enabled: false
        coreDns:
          enabled: true
        kubeDns:
          enabled: false
        nodeExporter:
          enabled: true
        kubeStateMetrics:
          enabled: true
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
```

---

### Part E — Verify Platform Apps

**Step 7: Verify tất cả platform apps đã sync**

```bash
argocd app list -o wide

# Expected:
# NAME                     CLUSTER                         NAMESPACE    STATUS   HEALTH
# platform-apps-root       https://kubernetes.default.svc  argocd       Synced   Healthy
# cert-manager             https://kubernetes.default.svc  cert-manager Synced   Healthy
# external-secrets         https://kubernetes.default.svc  external-sec Healthy
# ingress-nginx            https://kubernetes.default.svc  ingress-...  Synced   Healthy
# prometheus               https://kubernetes.default.svc  monitoring   Synced   Healthy
```

**Step 8: Verify từng component**

```bash
# Cert Manager
kubectl get pods -n cert-manager
kubectl get clusterissuer

# Expected ClusterIssuer:
# NAME                READY   AGE
# selfsigned-issuer   True    2m

# External Secrets
kubectl get pods -n external-secrets
kubectl get clustersecretstore

# Ingress Controller
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx

# Prometheus Stack
kubectl get pods -n monitoring
kubectl get prometheus -n monitoring
kubectl get grafana -n monitoring 2>/dev/null || kubectl get statefulset -n monitoring grafana

# Prometheus UI (port-forward)
kubectl port-forward -n monitoring svc/prometheus-operated 9090 &
open http://localhost:9090

# Grafana (port-forward)
kubectl port-forward -n monitoring svc/prometheus-grafana 3030 &
open http://localhost:3030
```

**Step 9: Verify Ingress resource + TLS (sau khi cert-manager ready)**

```yaml
# Tạo test Ingress để verify cert-manager tự issue certificate
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-tls-ingress
  namespace: default
  annotations:
    cert-manager.io/cluster-issuer: selfsigned-issuer
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - test.capstone.local
      secretName: test-tls
  rules:
    - host: test.capstone.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: nginx
                port:
                  number: 80
EOF

# Watch certificate
kubectl get certificate -w

# Expected (sau ~30s):
# NAME         READY   SECRET       AGE
# test-tls     True    test-tls     30s
```

---

### Part F — Mode B Specific (AWS LB Controller + ACM)

> **COST WARNING**: Các ALB được tạo bởi AWS LB Controller sẽ phát sinh ~$16-20/tháng mỗi ALB.

**Step 10 (Mode B only): Cài AWS LB Controller**

```bash
# AWS LB Controller cần IRSA (đã tạo ở Day 30)
helm upgrade --install aws-load-balancer-controller \
  eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=capstone-dev \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=us-east-1 \
  --set vpcId=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*capstone*" --query 'Vpcs[0].VpcId' --output text) \
  --wait --timeout 5m
```

**Step 11 (Mode B only): Tạo ACM certificate thay vì cert-manager self-signed**

```bash
# Request ACM certificate (tự động verify qua DNS)
aws acm request-certificate \
  --domain-name "*.capstone.dev" \
  --subject-alternative-names "capstone.dev" \
  --validation-method DNS \
  --region us-east-1 \
  --output json | jq -r '.CertificateArn'

# Verify DNS validation
aws acm describe-certificates \
  --certificate-arn <arn> \
  --query 'Certificate[0].DomainValidationOptions'
```

---

### Troubleshooting

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| `cert-manager Pod stuck at Init` | CRD chưa apply xong | `kubectl wait --for=condition=established crd/certificates.cert-manager.io --timeout=60s` |
| `Certificate stuck at Pending` | ClusterIssuer chưa ready hoặc Ingress chưa có annotation | Verify `kubectl get clusterissuer` = True |
| `ESO: NoCredentialProviders` | IRSA annotation sai (Mode B) | Verify `eks.amazonaws.com/role-arn` đúng từ Day 30 Step 3 |
| `Ingress Class not found` | Default ingressclass không phải nginx | `kubectl get ingressclass` → nếu không có `nginx`, tạo IngressClass |
| `Prometheus OOMKilled` | Memory limit quá thấp | Tăng `prometheus.prometheusSpec.resources.limits.memory` |
| `ArgoCD app OutOfSync sau khi thay đổi values.yaml` | Root app có `selfHeal: false` → không auto-correct | `argocd app sync platform-apps-root` hoặc set `selfHeal: true` |
| `argocd-server ALB not ready` | AWS LB Controller chưa install (Mode B) | Chạy Step 10 trước |
| `Ingress 404 hoặc 503` | Backend service chưa ready | `kubectl get svc` verify service có endpoints |

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Tại sao ArgoCD không thể bootstrap chính nó qua GitOps? Làm thế nào để giải quyết vấn đề này?

> **Trả lời:** Circular dependency — ArgoCD cần có trước để sync manifests, nhưng manifests của chính ArgoCD cần ArgoCD để sync. Solution: Dùng Terraform Helm (hoặc kubectl apply) cài ArgoCD lần đầu — bootstrap thủ công một lần, sau đó ArgoCD quản lý mọi thứ khác qua GitOps.

**Câu 2:** Mô tả bootstrap order đúng cho 6 platform components (ArgoCD, ESO, cert-manager, Ingress, Prometheus, Apps).

> **Trả lời:** Phase 1 (ArgoCD → cert-manager → ESO) → Phase 2 (Ingress) → Phase 3 (Prometheus) → Phase 4 (Apps). Phase 1 độc lập, không circular. Ingress cần cert-manager + ESO ready. Prometheus độc lập, có thể cài song song.

**Câu 3:** Debug: ESO ExternalSecret tạo K8s Secret nhưng secret value là empty. Liệt kê 5 nguyên nhân.

> **Trả lời:** (1) ClusterSecretStore spec sai (region, auth method), (2) IRSA annotation sai/IRSA role không có quyền GetSecretValue, (3) Remote secret key không tồn tại trong ASM/GH, (4) ESO controller pod không Running (crashLoopBackOff), (5) SecretStoreRef namespace khác với ESO namespace, (6) `refreshInterval` chưa trigger (cần chờ hoặc restart ESO pod).

**Câu 4:** Team có 2 môi trường (dev + staging) trên cùng EKS cluster. Dùng App of Apps hay ApplicationSet? Giải thích.

> **Trả lời:** ApplicationSet matrix generator (service × env) là lựa chọn tốt hơn vì scale được khi thêm service mới. App of Apps cũng hoạt động nhưng phải thêm Application YAML thủ công mỗi khi thêm service. ApplicationSet tự generate Applications từ folder/file.

**Câu 5:** Terraform đang quản lý 1 Helm release cho ArgoCD. ArgoCD app cũng thấy resource đó. Điều gì xảy ra và cách giải quyết?

> **Trả lời:** Drift loop — Terraform apply ghi đè values → ArgoCD thấy drift → ArgoCD sync về version trong Git → Terraform下次 apply lại ghi đè. Giải pháp: Hybrid pattern. Terraform quản lý ArgoCD Helm release (vì cần bootstrap). ArgoCD KHÔNG có Application cho ArgoCD itself. ArgoCD chỉ quản lý các component khác.

---

## 7. Tóm tắt cuối ngày

### 3-5 ý quan trọng nhất

1. **Bootstrap order rõ ràng:** ArgoCD (Terraform bootstrap) → cert-manager → ESO → Ingress → Prometheus → Apps. Không có circular dependency.

2. **Hybrid là best practice:** Terraform quản lý ArgoCD (vì circular), ArgoCD quản lý mọi thứ khác. Không bao giờ để Terraform + ArgoCD cùng quản lý 1 Helm release.

3. **ESO: Store → ExternalSecret → K8s Secret:** ClusterSecretStore phải ready trước khi dùng ExternalSecret. ESO không restart pod tự động.

4. **Cert Manager: self-signed (dev) vs ACM (prod):** Dev dùng self-signed ClusterIssuer. Production dùng ACM + DNS challenge.

5. **App of Apps cho bootstrap platform apps, ApplicationSet cho multi-service/multi-env:** Đơn giản + đủ cho Capstone.

### Output cuối ngày

```
capstone-platform/argocd/
├── platform-apps/
│   ├── Chart.yaml              ← Helm dependencies
│   ├── values.yaml             ← Global values (Mode A)
│   └── applications/
│       ├── 1-cert-manager.yaml ← Sync wave 1
│       ├── 2-external-secrets.yaml ← Sync wave 2
│       ├── 3-ingress-nginx.yaml ← Sync wave 3
│       ├── 4-prometheus.yaml   ← Sync wave 4
│       └── 5-app-of-apps.yaml  ← Sync wave 5 (apps bootstrap)
└── argocd-install/
    └── root-app.yaml           ← App of Apps root

Kubernetes cluster state:
  Namespace: argocd             ✅ ArgoCD running
  Namespace: cert-manager       ✅ ClusterIssuer ready
  Namespace: external-secrets   ✅ ClusterSecretStore ready
  Namespace: ingress-nginx      ✅ Ingress Controller running
  Namespace: monitoring         ✅ Prometheus + Grafana running
```

### Chuẩn bị cho Day 33

Day 33 (GitOps Apps Layer & Promotion Strategy) sẽ:
- Deploy 3 microservices (api-service, worker-service, frontend-service) qua ArgoCD ApplicationSet
- Tạo Helm chart cho mỗi service
- Tạo Kustomize overlay dev/staging/prod
- Cấu hình image tag promotion flow (Git SHA → semver)
- Setup ArgoCD promotion: dev auto-sync → staging PR → prod manual approval

---

## 8. Tham khảo thêm

### Official Documentation
- [ArgoCD Bootstrap](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)
- [ArgoCD App of Apps](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/#app-of-apps-pattern)
- [ArgoCD ApplicationSet](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/)
- [External Secrets Operator](https://external-secrets.io/latest/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [NGINX Ingress Controller — Helm](https://kubernetes.github.io/ingress-nginx/deploy/#using-helm)
- [AWS LB Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [kube-prometheus-stack](https://prometheus-operator.dev/)

### Tools & Scripts
- [ArgoCD Helm Chart](https://artifacthub.io/packages/helm/argo/argo-cd)
- [ESO Helm Chart](https://artifacthub.io/packages/helm/external-secrets-operator/external-secrets)
- [cert-manager Helm Chart](https://artifacthub.io/packages/helm/cert-manager/cert-manager)
- [NGINX Ingress Helm Chart](https://artifacthub.io/packages/helm/ingress-nginx/ingress-nginx)
- [kube-prometheus-stack Helm Chart](https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack)
