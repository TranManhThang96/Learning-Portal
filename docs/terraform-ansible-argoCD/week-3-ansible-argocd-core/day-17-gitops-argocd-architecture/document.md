# Day 17 - ArgoCD Architecture Deep-Dive & Reference

**Reference document** cho Day 17 — GitOps Principles & ArgoCD Architecture
**Audience:** Senior developer học GitOps/ArgoCD lần đầu
**Prerequisite:** Đã đọc lesson.md

---

## 1. Architecture Cheatsheet

### 1.1 ArgoCD Components — Quick Reference

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ArgoCD Architecture Overview                       │
├────────────────┬────────────┬──────────────┬────────────────────────────┤
│ Component      │ Type       │ Port          │ Memory/CPU typical         │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-server  │ Deployment │ 443 (gRPC)   │ 256Mi / 500m              │
│                │            │ 8080 (HTTP)   │                            │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-repo-   │ Deployment │ internal     │ 256Mi–2Gi (scales w/     │
│ server         │ (scalable) │              │  repo size) / 500m        │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-        │ StatefulSet│ internal     │ 512Mi / 500m              │
│ application-   │ (shardable)│              │                            │
│ controller     │            │              │                            │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-dex-    │ Deployment │ 5556 (HTTP)  │ 128Mi / 250m              │
│ server         │ (optional) │              │                            │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-redis   │ Deployment │ 6379         │ 256Mi / 250m              │
│                │ (3x HA)    │              │                            │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-app     │ Deployment │ internal     │ 128Mi / 200m              │
│ set-controller │ (optional) │              │                            │
├────────────────┼────────────┼──────────────┼────────────────────────────┤
│ argocd-        │ Deployment │ internal     │ 128Mi / 100m              │
│ notifications  │ (optional) │              │                            │
└────────────────┴────────────┴──────────────┴────────────────────────────┘
Total default install: ~1.5GB RAM, ~2 CPU cores
```

### 1.2 Component Dependencies

```
argocd-server
    ├── argocd-redis            (session, cache)
    ├── argocd-dex-server       (SSO — optional)
    ├── Kubernetes API          (list Application CRD)
    └── Git Repos               (metadata only)

argocd-application-controller
    ├── argocd-repo-server      (manifest generation)
    ├── Kubernetes API         (apply + watch actual state)
    └── Git Repos               (desired state)

argocd-repo-server
    ├── Git Repos               (clone + fetch)
    ├── Helm (embedded)        (chart render)
    ├── Kustomize (embedded)   (overlay build)
    └── argocd-redis            (manifest cache)

argocd-dex-server
    └── External IdP            (GitHub, LDAP, SAML...)
```

### 1.3 Scale Strategy

| Application count | Strategy |
|---|---|
| < 50 | Default install, 1 controller replica |
| 50–200 | Tăng `timeout.reconciliation` lên 5 phút |
| 200–1000 | Scale application-controller lên 2-3 replicas (sharding) |
| 1000+ | Sharding + scale repo-server replicas |

```bash
# Sharding config
kubectl edit configmap argocd-cm -n argocd
```
```yaml
data:
  controller.sharding.algorithm: consistent-hash  # recommended
  controller.replicas: "3"  # number of shards
```

### 1.4 Network Policy (Production)

```yaml
# argocd-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: argocd-server-network-policy
  namespace: argocd
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: server
  policyTypes:
    - Ingress
  ingress:
    - ports:
        - port: 8080
      from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: argocd-controller-network-policy
  namespace: argocd
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: application-controller
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector: {}  # all namespaces
      ports:
        - port: 443
        - port: 80
```

---

## 2. Comparison Matrix — ArgoCD vs Flux v2 (Extended)

### 2.1 Feature Matrix

```
┌───────────────────────────┬──────────────────────────┬──────────────────────────┐
│ Feature                   │ ArgoCD                   │ Flux v2                  │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Initial release           │ 2018                     │ 2019                     │
│ Maintainer               │ Argo CD Project (CNCF)   │ Weaveworks (CNCF)        │
│ CNCF status              │ Graduated                │ Graduated                 │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Declarative as Code      │ YAML (Application CRD)   │ YAML (multiple CRDs)    │
│ CI tool requirement      │ Zero (Git-only)         │ Zero (Git-only)          │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Git webhook support      │ ✅ Yes                   │ ✅ Yes                    │
│ Polling (no webhook)     │ ✅ Yes (configurable)   │ ✅ Yes (configurable)    │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Native UI                │ ✅ Full-featured         │ ❌ None (use Weave GitOps)│
│ CLI                      │ ✅ Rich argocd CLI       │ ✅ Rich flux CLI          │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ ApplicationSet /         │ ✅ generators            │ ❌ Use kustomize          │
│ templating               │ (Git, Matrix, SCM,       │ or external tooling      │
│                           │  Cluster, List)          │                          │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Helm rendering           │ Server-side (repo-srv)  │ Server-side (Helm CTR)   │
│ Kustomize support        │ Server-side (repo-srv)  │ Server-side (Kustomize) │
│ Plain manifest           │ ✅                       │ ✅                        │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Multi-cluster mgmt       │ Single ArgoCD → multi    │ Per-cluster Flux agent  │
│                           │ cluster (context switch) │ (GitOps bootstrap)       │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ AppProject + RBAC        │ ✅ Full                  │ ✅ Namespace + RBAC        │
│ SSO built-in             │ ✅ (Dex)                │ ❌ External only          │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Image automation         │ ArgoCD Image Updater    │ Image Reflector +        │
│                           │ (extra install)          │ Automation CRD (built-in)│
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Notification              │ Notifications Controller │ Notifications CRD        │
│                           │ (optional)               │ (built-in)               │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Progressive delivery      │ Argo Rollouts CRD       │ Flagger (Weave)          │
│                           │ (separate install)       │ (separate install)       │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Resource health check    │ ✅ Custom + built-in     │ ✅ Custom + built-in      │
│ Sync wave / hooks        │ ✅ Annotations            │ ✅ PostRender hook        │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Drift detection           │ ✅ OutOfSync              │ ✅ Reconciliation         │
│ Auto-remediation          │ ✅ (selfHeal)             │ ✅ (flux reconcile)       │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Audit trail              │ ArgoCD history + Git     │ Flux events + Git        │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Upgrade management       │ kubectl apply / Helm    │ flux bootstrap --mode=   │
│                           │                         │  cluster (auto-upgrade)  │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Backup/DR                 │ Export YAML + Git       │ Git bootstrap = backup   │
│                           │                         │                          │
├───────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Installation size         │ ~1.5GB RAM total        │ ~300MB RAM per cluster   │
│ Upgrade complexity        │ Higher (many resources) │ Lower (flux bootstrap)  │
└───────────────────────────┴──────────────────────────┴──────────────────────────┘
```

### 2.2 Architecture Philosophy Comparison

```
ARGOCD — CENTRALIZED MODEL
──────────────────────────

   ┌─────────────────────────────────────────┐
   │            ArgoCD Server               │
   │  (1 instance, 1 cluster hoặc remote)   │
   └──────────────────┬──────────────────────┘
                      │ gRPC (TLS)
          ┌───────────┼───────────┐
          ▼           ▼           ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Cluster 1│ │ Cluster 2│ │ Cluster 3│
   │ (dev)    │ │ (staging)│ │ (prod)   │
   └──────────┘ └──────────┘ └──────────┘

Pros: Centralized view, 1 RBAC, 1 UI
Cons: Single point of failure (cần HA), network hop


FLUX — DECENTRALIZED MODEL
──────────────────────────

   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ Cluster 1│   │ Cluster 2│   │ Cluster 3│
   │ ┌──────┐ │   │ ┌──────┐ │   │ ┌──────┐ │
   │ │ Flux │ │   │ │ Flux │ │   │ │ Flux │ │
   │ │Agent │ │   │ │Agent │ │   │ │Agent │ │
   │ └──────┘ │   │ └──────┘ │   │ └──────┘ │
   └─────┬────┘   └─────┬────┘   └─────┬────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                 ┌──────────────┐
                 │  Git Repo(s) │
                 └──────────────┘

Pros: No central SPoF, each cluster autonomous
Cons: Mỗi cluster cần manage riêng, no unified UI
```

### 2.3 Migration Path

```
Push-based CI/CD (Jenkins)
         │
         ▼
┌─────────────────────────────────────────┐
│   Phase 1: GitOps Pilot (1-2 tuần)      │
│   Cài ArgoCD, deploy 1 app thử nghiệm  │
│   CI: git commit thay vì kubectl apply │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Phase 2: Incremental Migration         │
│   Migrate service by service            │
│   CI: git tag trigger ArgoCD sync        │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Phase 3: Full GitOps                   │
│   Loại bỏ cluster credential khỏi CI   │
│   ArgoCD automated sync                 │
│   Optional: ApplicationSet cho scale     │
└─────────────────────────────────────────┘
```

---

## 3. Reconciliation Loop — Sequence Diagram

```
┌─────────┐    ┌──────────────┐    ┌────────────────┐    ┌────────────────┐
│ User /  │    │   argocd-    │    │    argocd-     │    │    Git Repo    │
│ Webhook │    │   server     │    │   repo-server   │    │                │
└────┬────┘    └──────┬───────┘    └───────┬────────┘    └───────┬────────┘
     │                │                     │                     │
     │ sync request   │                     │                     │
     │───────────────▶│                     │                     │
     │                │                     │                     │
     │                │ generate manifest   │                     │
     │                │────────────────────▶│                     │
     │                │                     │ git clone/fetch     │
     │                │                     │────────────────────▶│
     │                │                     │◀────────────────────│
     │                │                     │                     │
     │                │                     │ helm template /     │
     │                │                     │ kustomize build     │
     │                │                     │                     │
     │                │◀────────────────────│ rendered manifests  │
     │◀───────────────│                     │                     │
     │                │                     │                     │
     │                │    diff manifests  │                     │
     │                │    vs cluster      │                     │
     │                │══════════════════════                      │
     │                │                     │                     │
     │                │    kubectl apply /  │                     │
     │                │    helm upgrade     │                     │
     │                │══════════════════════════▶ K8s API         │
     │                │                     │                     │
     │                │    health check     │                     │
     │                │══════════════════════                      │
     │                │                     │                     │
     │◀───────────────│ status=Synced       │                     │
     │  Sync complete │ Healthy             │                     │
     │                │                     │                     │
     │                │                     │                     │
     │  EVERY 3 MIN   │                     │                     │
     │  (auto loop)   │                     │                     │
     │────────────────▶│                     │                     │
     │                │ ...same flow...     │                     │

TIMER: Every 3 minutes (default, configurable)
       └── argocd-application-controller reconciliation timer
           ├── Compare: Git manifests vs cluster actual state
           ├── Decision: Synced ✅ or OutOfSync 🔴
           └── Action: (none for manual) or kubectl apply (for automated)
```

---

## 4. ArgoCD CLI Cheat Sheet

### 4.1 Application Management

```bash
# Tạo Application
argocd app create <name> \
  --repo <git-url> \
  --path <path-in-repo> \
  --dest-server <cluster-url> \
  --dest-namespace <namespace> \
  --sync-policy <manual|automated>

# List applications
argocd app list
argocd app list -o wide           # full details
argocd app list --selector app=<label>

# Get application details
argocd app get <app-name>         # summary
argocd app get <app-name> -o yaml # full YAML

# Sync (trigger reconciliation)
argocd app sync <app-name>                    # sync current revision
argocd app sync <app-name> --revision <sha>  # specific revision
argocd app sync <app-name> --force            # force replace
argocd app sync <app-name> --strategy <name> # specific sync strategy

# Diff (compare Git vs cluster)
argocd app diff <app-name>           # diff all resources
argocd app diff <app-name> --local /path/to/local/manifest  # diff vs local

# History (sync revision history)
argocd app history <app-name>

# Rollback (về revision cũ)
argocd app rollback <app-name> <revision-id>

# Delete
argocd app delete <app-name> --cascade  # xóa cả child resources

# Watch (real-time status)
argocd app get <app-name> --watch
```

### 4.2 ApplicationSet (Day 22 preview)

```bash
# List ApplicationSets
argocd appset list

# Create ApplicationSet
argocd appset create appset.yaml

# Get ApplicationSet
argocd appset get <name>
```

### 4.3 Cluster Management

```bash
# List registered clusters
argocd cluster list

# Add cluster
argocd cluster add <context-name>  # lấy context từ kubeconfig

# Get cluster info
argocd cluster get <server-url>

# Remove cluster
argocd cluster rm <server-url>
```

### 4.4 Repository Management

```bash
# List repositories
argocd repo list

# Add repo (HTTPS + username/password)
argocd repo add <repo-url> \
  --username <user> \
  --password <token>

# Add repo (SSH)
argocd repo add <repo-url> \
  --ssh-private-key-path /path/to/key

# Add repo (GitHub App)
argocd repo add <repo-url> \
  --github-app-id <id> \
  --github-app-installation-id <inst-id> \
  --github-app-private-key-path /path/to/key.pem

# Remove repo
argocd repo rm <repo-url>
```

### 4.5 AppProject Management

```bash
argocd proj list
argocd proj get <project-name>
argocd proj create <project-name> -f proj.yaml
argocd proj add-source <project-name> <repo-url>
argocd proj allow-namespace <project-name> <namespace-pattern>
argocd proj deny-namespace <project-name> <namespace-pattern>
```

### 4.6 User & RBAC

```bash
# List users
argocd account list

# Get current user
argocd account current-user

# Generate token (cho SSO/API)
argocd account generate-token --account <username>
```

### 4.7 ArgoCD Server Management

```bash
# ArgoCD server health
argocd server --help

# ArgoCD version
argocd version

# ArgoCD config
argocd admin settings validate  # validate configmap
argocd admin config map         # view current config
```

### 4.8 ArgoCD Notifications

```bash
# Manage notification triggers/templates
argocd notifications template list
argocd notifications trigger list
```

### 4.9 Useful Flags

```bash
--insecure              # skip TLS verification (dev only)
--grpc-web              # use gRPC-web protocol
--plaintext             # HTTP instead of HTTPS
-o json|yaml|wide|table # output format
--auth-token <token>    # pass token directly (CI/CD use)
--server <addr>         # ArgoCD server address
```

---

## 5. Application CRD Field Reference

### 5.1 Full Application spec

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <string>                        # Required, unique trong namespace ArgoCD
  namespace: argocd                      # Thường luôn là argocd
  uid: <string>                         # Auto-generated
  labels:                               # Optional labels
    app.kubernetes.io/name: <app>
  annotations:                           # ArgoCD annotations
    argoproj.io/sync-wave: "0"         # Sync wave ordering
  finalizers:                           # Cleanup khi delete
    - resources-finalizer.argocd.argoproj.io
spec:
  project: <string>                     # Required: AppProject name (default: default)

  # ─── Source: WHERE is desired state? ───
  source:
    repoURL: <string>                   # Git/Helm repo URL
    targetRevision: <string>             # branch, tag, commit SHA, semver range
    path: <string>                      # Path trong repo (mutually exclusive vs chart)
    # OR for Helm chart:
    chart: <string>                     # Helm chart name (e.g., "redis")
    helm:
      valueFiles:                       # Values file list
        - values.yaml
        - values-prod.yaml
      parameters:                        # Override values
        - name: image.tag
          value: v1.2.3
      releaseName: <string>             # Helm release name
      passCredentials: <bool>           # Pass Git creds to Helm
    kustomize:
      namePrefix: <string>              # Kustomize name prefix
      nameSuffix: <string>              # Kustomize name suffix
      images:                           # Kustomize image overrides
        - myimage:tag
      commonLabels: <map>               # Labels applied to all resources
    directory:
      recurse: <bool>                   # Recurse subdirectories
      jsonnet:                          # Jsonnet options
        extVars:
          - name: <string>
            value: <string>
    ref: <string>                       # Go template (advanced)

  # ─── Destination: WHERE to deploy? ───
  destination:
    server: <string>                    # Kubernetes API server URL
    #   https://kubernetes.default.svc  = current cluster
    #   https://<remote-cluster>:6443  = remote cluster
    namespace: <string>                 # Target namespace
    name: <string>                     # Alternative: cluster name (from argocd cluster list)

  # ─── Sync Policy ───
  syncPolicy:
    automated:                         # null = manual
      prune: <bool>                    # Delete resources not in Git
      selfHeal: <bool>                 # Fix cluster drift
      allowEmpty: <bool>               # Allow zero replicas
    syncOptions:                       # Array of sync options
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
      - ApplyOutOfSync=true
      - RespectIgnoreDifferences=true
    retry:
      limit: <number>                  # Số lần retry (default: 0)
      backoff:
        duration: <string>             # e.g., 5s, 2m
        factor: <number>               # Exponential backoff factor
        maxDuration: <string>          # Max wait time

  # ─── Ignore differences ───
  ignoreDifferences:
    - group: <string>
      kind: <string>
      name: <string>
      namespace: <string>
      jsonPointers:
        - /spec/replicas
        - /status

  # ─── Info (metadata hiển thị trong UI) ───
  info:
    - name: description
      value: "Production API gateway"
    - name: maintainer
      value: "team-backend@example.com"

  # ─── Reference to another Application ───
  sources: []                          # Multi-source (v2.9+)

status:
  # Read-only, ArgoCD controller updates
  health:
    status: <Healthy|Degraded|Progressing|Suspended|Missing>
    message: <string>
  sync:
    status: <Synced|OutOfSync|Unknown>
    comparedTo:
      source: <snapshot of spec.source>
      destination: <snapshot of spec.destination>
    revision: <string>
  resources: []                         # Per-resource status
  operationState:                      # Current/last operation
  conditions: []                       # Ready, etc.
```

### 5.2 Application metadata annotations

```yaml
metadata:
  annotations:
    # Sync wave: control execution order khi sync
    argoproj.io/sync-wave: "1"        # Wave number (lower = first)

    # Skip tracking certain resources
    argoproj.io/hook: Sync            # Sync hook (before/after/during)
    argoproj.io/hook-delete-policy: HookSucceeded  # Cleanup policy

    # Refresh: force ArgoCD refresh (annotation thay vì CLI)
    argocd.argoproj.io/refresh: normal|hard

    # Comparison: override global ignoreDifferences
    argocd.argoproj.io/compare-options: IgnoreExtraneous
```

### 5.3 Sync Wave Hook Annotations

```yaml
# Sync hook: chạy trước khi apply
apiVersion: batch/v1
kind: Job
metadata:
  annotations:
    argoproj.io/hook: PreSync         # Sync|HookSucceeded|BeforeHookCreation
    argoproj.io/hook-delete-policy: HookSucceeded  # HookFailed|Succeeded|BeforeHookCreation
spec:
  template:
    spec:
      containers:
        - name: pre-sync-check
          image: busybox:1.36
          command: [sh, -c, 'echo "PreSync"']
      restartPolicy: Never
```

Sync hook types:
- `PreSync`: Chạy TRƯỚC khi apply any resource
- `Sync`: Chạy trong quá trình apply
- `PostSync`: Chạy SAU khi apply tất cả resource
- `SyncFail` (v2.8+): Chạy khi sync fail

### 5.4 AppProject CRD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: <project-name>
  namespace: argocd
spec:
  description: <string>

  # Allowed source repositories
  sourceRepos:
    - 'https://github.com/org/repo.git'
    - 'https://github.com/org/*.git'       # Glob patterns
    - 'git@github.com:org/repo.git'        # SSH

  # Allowed destinations (cluster + namespace)
  destinations:
    - server: https://kubernetes.default.svc
      namespace: team-*-prod              # Glob patterns
    - server: https://kubernetes.default.svc
      namespace: team-*-staging

  # Deny certain resources
  clusterResourceBlacklist:
    - group: 'rbac.authorization.k8s.io'
      kind: ClusterRoleBinding
  namespaceResourceBlacklist:
    - group: ''
      kind: LimitRange

  # Roles (RBAC)
  roles:
    - name: <role-name>
      description: <string>
      policies:                          # RBAC policy lines
        - p, proj:<name>:<role>,applications,*,<name>/*,allow
        - p, proj:<name>:developer,applications,sync,<name>/,allow
        - g, team-members,role:<role-name>  # Group mapping
      groups:
        - team-members@example.com

  # Sync window (cho phép sync trong khoảng thời gian)
  syncWindows:
    - name: maintenance-window
      timeZone: Asia/Ho_Chi_Minh
      clusters:
        - https://kubernetes.default.svc
      namespaces:
        - production
      kinds: Deployment,StatefulSet
      schedule: '0 2 * * 0-6'            # Cron schedule
      duration: 8h
      manualSync: true                   # Allow manual sync only
```

---

## 6. Sync Status & Health Status Meanings

### 6.1 Sync Status

```
┌───────────────┬──────────────────────────────────────────────────────────────┐
│ Status        │ Meaning                                                       │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Synced ✅     │ Cluster state MATCHES Git desired state. Tất cả resource     │
│               │ đúng như trong Git.                                          │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ OutOfSync 🔴  │ Cluster state KHÔNG MATCH Git desired state. Có drift.      │
│               │ Possible causes:                                             │
│               │ 1. Git đã thay đổi nhưng chưa sync                          │
│               │ 2. Manual thay đổi trên cluster (không qua Git)             │
│               │ 3. Sync thất bại một phần                                     │
│               │ 4. Reconciliation đang chạy                                  │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Unknown ❓    │ ArgoCD không thể determine state. Thường là lỗi kết nối.    │
│               │ Possible causes:                                             │
│               │ 1. Kubernetes API unreachable                                │
│               │ 2. Repository không accessible                                │
│               │ 3. RBAC issue                                                │
│               │ 4. Application controller not running                        │
└───────────────┴──────────────────────────────────────────────────────────────┘
```

### 6.2 Health Status

```
┌───────────────┬──────────────────────────────────────────────────────────────┐
│ Status        │ Meaning                                                       │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Healthy ✅    │ Tất cả managed resource đều healthy.                        │
│               │ ArgoCD đã apply resource và resource hoạt động tốt.        │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Progressing ⏳│ Ít nhất 1 resource đang thay đổi trạng thái.              │
│               │ Thường là: Deployment rollout, Pod pending, scaling.        │
│               │ ArgoCD đang chờ resource "settle" về healthy.               │
│               │ Nếu stuck > timeout: chuyển sang Degraded.                  │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Degraded ❌   │ Ít nhất 1 resource KHÔNG healthy.                          │
│               │ Causes:                                                       │
│               │ 1. Pod CrashLoopBackOff                                      │
│               │ 2. PVC pending (storage không available)                    │
│               │ 3. HPA scale failed                                          │
│               │ 4. Custom health check fail                                  │
│               │ 5. Pod not running (ImagePullBackOff, Evicted)              │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Suspended ⏸  │ Deployment/StatefulSet bị paused (.spec.paused=true).      │
│               │ ArgoCD nhận biết và không attempt reconcile health.          │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Missing ⚠     │ Resource được mô tả trong Git KHÔNG TỒN TẠI trong cluster.│
│               │ Thường xảy ra khi:                                          │
│               │ 1. Resource vừa bị xóa thủ công                            │
│               │ 2. Sync đang chạy (chưa tạo xong)                          │
│               │ 3. prune=false nên ArgoCD không recreate                   │
├───────────────┼──────────────────────────────────────────────────────────────┤
│ Unknown ❓    │ ArgoCD không có health check cho resource type này.        │
│               │ Mặc định: các standard resource có health check.          │
│               │ Custom resource: cần define health check function.          │
└───────────────┴──────────────────────────────────────────────────────────────┘
```

### 6.3 Combined Status Table

```
┌────────────┬────────────┬──────────────────────────────────────────────────┐
│ Sync       │ Health     │ Meaning                                          │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ Synced     │ Healthy    │ ✅ PERFECT — cluster matches Git, app running     │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ Synced     │ Progressing│ ⚠ Git đúng nhưng app đang rolling update         │
│            │            │    → Bình thường, đang deploy                     │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ Synced     │ Degraded   │ ⚠️ Cluster matches Git NHƯNG app không healthy   │
│            │            │    → Debug: pod crash, resource limit, config     │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ OutOfSync  │ Healthy    │ 🔴 Git khác cluster (drift), app đang chạy       │
│            │            │    → argocd app sync để apply Git changes       │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ OutOfSync  │ Degraded   │ 🔴🔴 Git khác cluster, app không healthy        │
│            │            │    → Nguy hiểm nhất — debug ngay                  │
├────────────┼────────────┼──────────────────────────────────────────────────┤
│ Unknown    │ Unknown    │ 🔴🔴 ArgoCD không connect được                  │
│            │            │    → Check: controller running? API accessible? │
└────────────┴────────────┴──────────────────────────────────────────────────┘
```

---

## 7. GitOps Maturity Model

### 4 Levels of GitOps Adoption

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GitOps Maturity Model                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LEVEL 4 — FULL GITOPS (Target)                                            │
│  ═══════════════════════════════════                                        │
│  • 100% declarative, zero imperative                                         │
│  • Automated sync + selfHeal enabled                                       │
│  • ArgoCD manages ALL resources (infra + app)                              │
│  • Image tag update tự động commit vào Git                                │
│  • Multi-cluster managed từ central ArgoCD                                │
│  • Drift = incident (không acceptable)                                    │
│                                                                              │
│  ─────────────────────────────────────────────                              │
│                                                                              │
│  LEVEL 3 — AUTOMATED GITOPS                                                │
│  ═══════════════════════════════                                           │
│  • All apps deploy qua ArgoCD                                              │
│  • CI chỉ commit vào Git, không kubectl apply                             │
│  • Automated sync (selfHeal có thể chưa bật)                             │
│  • AppProject/RBAC enforced                                                │
│  • ArgoCD là single source of truth cho app config                         │
│                                                                              │
│  ─────────────────────────────────────────────                              │
│                                                                              │
│  LEVEL 2 — GITOPS ADOPTION                                                  │
│  ══════════════════════════════                                            │
│  • ArgoCD installed, 1-2 apps pilot                                       │
│  • Git = source of truth cho config pilot                                  │
│  • Manual sync (developer trigger)                                         │
│  • CI vẫn có kubectl credential (đang migrate)                            │
│  • Team learning ArgoCD                                                    │
│                                                                              │
│  ─────────────────────────────────────────────                              │
│                                                                              │
│  LEVEL 1 — CI/CD PUSH (Starting Point)                                     │
│  ════════════════════════════════════                                      │
│  • Jenkins/GitLab CI push-based deploy                                    │
│  • CI có cluster credential                                                │
│  • Git lưu config nhưng không phải single source of truth                 │
│  • Manual kubectl edit không được track                                    │
│  • Rollback = re-run pipeline                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Maturity Assessment Checklist

```
LEVEL 1: CI/CD Push
  □ CI/CD pipeline deploys to cluster
  □ Git lưu application configuration
  □ Có thể rollback qua re-run pipeline
  □ Audit log nằm ở CI/CD tool

LEVEL 2: GitOps Adoption
  □ ArgoCD hoặc Flux installed
  □ ≥1 application managed qua GitOps
  □ Developer biết cách sync app
  □ Git commit history = deployment history
  □ Manual kubectl edit được phát hiện (OutOfSync)

LEVEL 3: Automated GitOps
  □ Tất cả application deploy qua ArgoCD
  □ CI không còn cluster credential
  □ Automated sync cho dev/staging
  □ AppProject/RBAC configured
  □ Notification configured (Slack/email)
  □ Backup strategy cho ArgoCD state

LEVEL 4: Full GitOps
  □ Zero imperative deployment (không ai `kubectl apply` thủ công)
  □ Image automation commit tag vào Git tự động
  □ Multi-cluster managed từ 1 ArgoCD
  □ Drift = P1 incident
  □ ArgoCD là single interface cho deployment
  □ Disaster recovery = ArgoCD reinstall + Git repo
```

---

## 8. ArgoCD ConfigMap Reference

### 8.1 argocd-cm (ArgoCD ConfigMap)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  # General
  admin.enabled: "true"                    # Enable admin account
  timeout.reconciliation: "180s"           # Reconciliation interval (default 3m)
  timeout.sync: "180s"                    # Sync operation timeout

  # Resource tracking
  resource.customizations: |              # Custom health check
    argoproj.io/ArgoRollout:
      health.lua: |
        if obj.status.phase == "Healthy" then
          return true, "Healthy"
        elseif obj.status.phase == "Progressing" then
          return true, "Progressing"
        elseif obj.status.phase == "Degraded" then
          return false, "Degraded"
        end
        return false, "Unknown"

  # SSO
  url: https://argocd.example.com          # ArgoCD public URL (for callbacks)

  # User management
  accounts.alice: apiKey,login            # Enable API key + login for user alice
  accounts.bob: login                    # Login only for user bob

  # Sharding
  controller.sharding.algorithm: round-robin
  controller.replicas: "2"
```

### 8.2 argocd-rbac-cm (RBAC ConfigMap)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  # Default RBAC policy
  # policy.default: role:readonly

  # Policy CSV format: p, <subject>, <action>, <resource>, <object>, <effect>
  policy.csv: |
    # Admin full access
    g, system:master, role:admin

    # Developer: sync + view applications in their project
    p, role:developer, applications, get, proj:backend/*, allow
    p, role:developer, applications, sync, proj:backend/*, allow
    p, role:developer, applications, override, proj:backend/*, deny

    # DevOps: manage all applications
    g, devops-team, role:admin

  # Scope (cluster-wide permissions)
  policy.default: role:readonly
```

### 8.3 argocd-secret (Secret — credentials)

```yaml
# argocd-secret là managed secret, không nên edit trực tiếp
# Dùng kubectl edit để update admin password hoặc certificate

# Thay đổi admin password:
kubectl -n argocd patch secret argocd-secret \
  -p '{"stringData": {"admin.password": "$2a$10$XXX"}}'

# Thêm TLS certificate cho Git server:
kubectl -n argocd patch secret argocd-secret \
  -p '{"stringData": {"tls.client.crt": "PEM-CERT", "tls.client.key": "PEM-KEY"}}'
```

---

**Reference complete.** Quay về lesson.md để tiếp tục Day 17 hoặc chuyển sang exercises.md để thực hành.
