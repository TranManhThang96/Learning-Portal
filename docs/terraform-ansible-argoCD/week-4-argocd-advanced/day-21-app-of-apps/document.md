# Day 21 — Reference: App of Apps Pattern Cheat Sheet

> Bổ sung cho `lesson.md` — phần này là cheat sheet để tra cứu nhanh trong thực tế.

---

## 1. Template: root-app.yaml

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-NAME
  namespace: argocd
  labels:
    app.kubernetes.io/name: root-NAME
    app.kubernetes.io/part-of: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_ORG/platform-repo.git
    targetRevision: main
    path: argocd/applications
    directory:
      recurse: true
      exclude: root-*.yaml          # Loại trừ chính nó
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
```

---

## 2. Template: child-app.yaml (Helm)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: CHILD-NAME
  namespace: argocd
  labels:
    layer: platform          # platform | application
    app.kubernetes.io/name: CHILD-NAME
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: PLATFORM_PROJECT_NAME
  source:
    repoURL: https://github.com/YOUR_ORG/platform-repo.git
    targetRevision: main
    path: platform-services/CHILD-NAME
    helm:
      valueFiles:
        - values.yaml
      values: |
        # inline values nếu cần override nhỏ
  destination:
    server: https://kubernetes.default.svc
    namespace: CHILD-NAMESPACE
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

---

## 3. Template: child-app.yaml (Kustomize)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: CHILD-NAME
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: PLATFORM_PROJECT_NAME
  source:
    repoURL: https://github.com/YOUR_ORG/apps-repo.git
    targetRevision: main
    path: services/CHILD-NAME/overlays/STAGING
  destination:
    server: https://kubernetes.default.svc
    namespace: CHILD-NAMESPACE
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 4. Template: child-app.yaml (Plain manifest)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: CHILD-NAME
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: PLATFORM_PROJECT_NAME
  source:
    repoURL: https://github.com/YOUR_ORG/platform-repo.git
    targetRevision: main
    path: manifests/CHILD-NAME
  destination:
    server: https://kubernetes.default.svc
    namespace: CHILD-NAMESPACE
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

---

## 5. Sync Policy Combinations

| Scenario | automated | prune | selfHeal | Khi nào dùng |
|----------|-----------|-------|----------|---------------|
| Dev cluster | true | true | true | Fast iteration, tự fix drift |
| Staging cluster | true | true | false | Fix drift nhưng không tự restart pod |
| Prod cluster | false | - | - | Manual sync, có control |
| Platform bootstrap | true | true | true | Tự động hóa hoàn toàn |
| Critical app | false | - | - | Manual approval bắt buộc |

---

## 6. Finalizer Behavior Table

| Root finalizer | Root prune | Child finalizer | Child prune | Xóa root → | Xóa child → |
|---------------|-----------|----------------|-------------|------------|-------------|
| Có | Có | Có | Có | Xóa root + child + workload | Xóa child + workload |
| Có | Có | Không | Có | Xóa root + child | Workload orphaned |
| Không | Có | Có | Có | Chỉ xóa root | Xóa child + workload |
| Không | Không | Không | Không | Chỉ xóa root | Chỉ xóa child |
| Có | false | Có | false | Xóa root + child (không workload) | Xóa child (không workload) |

**Recommendation:** Luôn dùng `finalizer + prune:true` cho root và child.

---

## 7. Bootstrap Ordering Checklist

### Layer 0: CRD Installer (nếu cần)

```
[] Custom Resource Definition cho external-secrets, cert-manager CRD
[] ClusterRole / ClusterRoleBinding (cluster-wide)
```

### Layer 1: Namespace Foundation

```
[] Namespace: ingress-nginx
[] Namespace: cert-manager
[] Namespace: external-secrets
[] Namespace: monitoring
[] Namespace: (app namespaces)
[] LimitRange / ResourceQuota
```

### Layer 2: Certificate Management

```
[] cert-manager
[] cert-manager CRD (ClusterIssuer, Certificate)
[] Self-signed CA hoặc Let's Encrypt issuer
```

### Layer 3: Ingress Controller

```
[] ingress-nginx (sau cert-manager)
[] IngressClass
[] Default backend (optional)
```

### Layer 4: Secrets Management

```
[] external-secrets operator (sau CRD)
[] SecretStore / ClusterSecretStore
[] Sample ExternalSecret
```

### Layer 5: Observability

```
[] prometheus-community/kube-prometheus-stack (sau cert-manager)
[] Grafana (optional, nếu not disabled)
[] Loki / logging stack
[] ArgoCD notifications (Day 27)
```

### Layer 6: Application Workload

```
[] api-service
[] worker-service
[] frontend-service
[] (依赖 layer 1-5: cert, ingress, secrets, metrics)
```

---

## 8. Anti-Patterns Checklist (15 bullets)

```
## App of Apps Anti-patterns

- [ ] Root app KHÔNG có finalizer
      → Xóa root = child orphaned
      → Fix: Thêm resources-finalizer.argocd.argoproj.io

- [ ] Child app KHÔNG có finalizer
      → Xóa child = workload orphaned
      → Fix: Thêm finalizer vào mọi child app

- [ ] Root app trỏ vào folder chứa chính nó
      → Recursive loop
      → Fix: exclude: root-*.yaml trong directory config

- [ ] Prune: false trong root app
      → Xóa file = child orphaned trong cluster
      → Fix: Luôn dùng prune: true

- [ ] Self-heal: false cho platform apps
      → Drift không được fix tự động
      → Fix: selfHeal: true cho dev, false cho prod

- [ ] Dùng automated sync cho root app prod mà không có sync window
      → Bất kỳ commit nào cũng được apply ngay
      → Fix: Manual sync hoặc sync wave + window

- [ ] Ứng dụng production cần startup order (DB → app) dùng App of Apps thuần
      → ArgoCD không guarantee ordering
      → Fix: Dùng sync waves (Day 24)

- [ ] Helm values chưa tồn tại khi root app apply
      → Sync fail
      → Fix: Tạo placeholder values.yaml trước

- [ ] TargetRevision = specific SHA trong root app
      → Mỗi lần thêm app phải update SHA
      → Fix: Dùng branch name (main, day-21-app-of-apps)

- [ ] 90+ Application file trong 1 folder mà không có naming convention
      → Không biết app nào thuộc layer nào
      → Fix: Dùng prefix (01-, 02-) hoặc folder-per-layer

- [ ] Child app có spec.project không tồn tại
      → Child app stuck ở OutOfSync
      → Fix: Tạo AppProject trước hoặc dùng 'default'

- [ ] Dùng kubectl apply -f thay vì commit vào Git
      → Mất audit trail
      → Fix: Luôn commit, ArgoCD detect

- [ ] Không có ignoreDifferences cho Deployment.replicas
      → HPA override replicas → ArgoCD OutOfSync
      → Fix: Thêm ignoreDifferences

- [ ] Quên CreateNamespace=true trong syncOptions
      → Namespace chưa tồn tại → sync fail
      → Fix: Luôn thêm

- [ ] Root app và child app cùng project
      → Root có thể override child sync policy
      → Fix: Root dùng 'default', child dùng project riêng
```

---

## 9. Diagram: 3 Cách Bootstrap ArgoCD Apps

```
CÁCH 1: MANUAL IMPERATIVE
─────────────────────────────────────────────────────
 kubectl apply -f app1.yaml   ─┐
 kubectl apply -f app2.yaml   ─┼─> Cluster (no audit, no GitOps)
 kubectl apply -f app3.yaml   ─┘

Cons: No GitOps, no audit, DevOps bottleneck


CÁCH 2: APP OF APPS (Root → Children)
─────────────────────────────────────────────────────
 Git: argocd/applications/
   ├── ingress-nginx.yaml     ─┐
   ├── cert-manager.yaml      ├──┐
   └── guestbook.yaml         ─┘  │
                                    │
 ArgoCD root-app                    │
   └── argocd/applications/        │
       └── [Child Apps]             │
                                    │
 ArgoCD Reconciliation Loop         │
   ├── ingress-nginx (child app) ──┼─> Cluster (GitOps, audit trail)
   ├── cert-manager (child app)  ──┘
   └── guestbook (child app)

Pros: Declarative, Git-managed, self-service
Cons: No ordering, boilerplate, hard to parametrize


CÁCH 3: APPLICATIONSET (Generator → Template → N Apps)
─────────────────────────────────────────────────────
 ApplicationSet:
   generators:
     - git:
         files:
           - path: services/**/*.yaml
   template:
     spec:
       source:
         path: "{{path}}/overlays/{{metadata.labels.env}}"

 Git: services/api/overlays/prod/kustomization.yaml
      services/worker/overlays/prod/kustomization.yaml
      services/frontend/overlays/prod/kustomization.yaml

 ArgoCD auto-generates:
   ├── api-service-prod  (from template)
   ├── worker-service-prod
   └── frontend-service-prod

Pros: Template-driven, auto-generate, parametrize
Cons: Complex setup, overkill cho <30 apps
```

---

## 10. Migration Path: App of Apps → ApplicationSet

### Khi nào cần migrate

- Application file count > 30
- Muốn parametrize: image tag, replica count, env name
- Cần auto-detect service mới
- Quản lý nhiều cluster

### Migration steps

```
1. Viết ApplicationSet template cho 1 service × 1 env
   → Test trên dev cluster
   → Verify ArgoCD tạo đúng Application

2. Mở rộng ApplicationSet cover tất cả service × env
   → 1 ApplicationSet thay thế N Application file

3. Xóa từng Application file cũ
   → Xóa từ từ, verify mỗi lần
   → KHÔNG xóa tất cả cùng lúc

4. Cleanup root-app (nếu chỉ dùng để tạo child app)
   → root-app không còn cần thiết khi dùng ApplicationSet
```

### Script: Convert Application YAML → ApplicationSet template

```bash
#!/bin/bash
# Chuyển đổi Application YAML → ApplicationSet values

for f in argocd/applications/*.yaml; do
  APP_NAME=$(basename "$f" .yaml)
  REPO=$(grep "repoURL:" "$f" | awk '{print $2}')
  PATH=$(grep "path:" "$f" | head -1 | awk '{print $2}')
  NAMESPACE=$(grep "namespace:" "$f" | head -1 | awk '{print $2}')

  echo "APP: $APP_NAME"
  echo "  repoURL: $REPO"
  echo "  path: $PATH"
  echo "  namespace: $NAMESPACE"
done
```

### Post-migration

```
 Sau khi migrate:
 ✓ 90 file Application.yaml → 1 ApplicationSet.yaml
 ✓ Thêm service mới = thêm folder, không cần tạo Application
 ✓ Image tag = parameter, không cần sửa từng file
 ✓ Multi-cluster = cluster generator, không cần copy file

 Vẫn giữ App of Apps cho:
 - Bootstrap layer (platform-level, <15 app)
 - One-time setup
 - Chicken-and-egg scenarios
```

---

## 11. Common Errors Reference Table

| Error | Cause | Fix |
|-------|-------|-----|
| `spec.source.path: Invalid value` | Path không tồn tại trong repo | Verify path tồn tại |
| `spec.project: NotFound` | AppProject không tồn tại | Tạo AppProject trước |
| `failed to retrieve manifests` | Repo credentials sai hoặc hết hạn | Kiểm tra ArgoCD repo credentials |
| `namespace not found` | CreateNamespace=false | Thêm `- CreateNamespace=true` |
| `finalizer stuck in terminating` | Orphaned resource không xóa được | `kubectl patch --dry-run=server` + remove finalizer |
| `app does not generate manifests` | repoURL/path sai | Verify repo URL và path |
| `OutOfSync but no diff` | ignoreDifferences missing | Thêm ignoreDifferences cho replicas |
| `TooManyRequests` | ArgoCD repo server quá tải | Tăng repo server replica |
| `Parent cluster is not accessible` | destination.server sai | Dùng `https://kubernetes.default.svc` |
| `Application is part of AppProject` | Không thể xóa app vì project protect | Xóa project trước hoặc force delete |

---

## 12. ArgoCD CLI Quick Reference

```bash
# List all apps
argocd app list

# Get app status
argocd app get root-platform
argocd app get root-platform --watch

# Sync app
argocd app sync root-platform
argocd app sync root-platform --force

# History
argocd app history root-platform
argocd app rollback root-platform REVISION

# Resources của app
argocd app resources root-platform

# Logs
argocd app logs root-platform

# Delete cascade
argocd app delete root-platform --cascade

# Diff
argocd app diff root-platform

# Set sync policy
argocd app set ingress-nginx --sync-policy automated
argocd app set ingress-nginx --automated-sync-enabled=true
argocd app set ingress-nginx --self-heal-enabled=true
argocd app set ingress-nginx --prune-enabled=true

# Sync options
argocd app set root-platform --sync-option CreateNamespace=true
argocd app set root-platform --sync-option PrunePropagationPolicy=foreground
```

---

## 13. File Structure Reference

```
platform-repo/                    # Repo chuẩn sau Day 21
├── argocd/
│   ├── projects/
│   │   └── platform-project.yaml
│   └── applications/             # Folder root app trỏ vào
│       ├── root-platform.yaml    # Root Application (EXCLUDE khỏi directory scan)
│       ├── 01-cert-manager.yaml  # Layer 1
│       ├── 02-ingress-nginx.yaml # Layer 2
│       ├── 03-external-secrets.yaml
│       ├── 04-prometheus-stack.yaml
│       ├── 05-loki.yaml
│       ├── 10-api-service.yaml   # Layer 3: workload
│       ├── 10-worker-service.yaml
│       └── 10-guestbook.yaml
└── platform-services/
    ├── cert-manager/
    │   └── values.yaml
    ├── ingress-nginx/
    │   └── values.yaml
    ├── external-secrets/
    │   └── values.yaml
    └── prometheus-stack/
        └── values.yaml

# Naming convention: số prefix cho layer ordering
# Layer 0x: CRD / infrastructure
# Layer 1x: Platform addons (cert, ingress, secrets)
# Layer 2x: Observability
# Layer 3x: Application workload
```

<!-- APPEND_HERE -->
