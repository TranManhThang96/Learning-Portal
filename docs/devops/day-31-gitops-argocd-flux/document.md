# Day 31: GitOps with ArgoCD & Flux — Document

## 1. ArgoCD vs Flux Comparison Matrix

| Tiêu chí | ArgoCD | Flux |
|----------|--------|------|
| **CNCF Status** | Graduated | Graduated |
| **Architecture** | Centralized (API Server + Controller) | Distributed (multiple controllers) |
| **UI** | ✅ Built-in Web UI | ❌ Cần Weave GitOps UI |
| **CLI** | ✅ `argocd` CLI | ✅ `flux` CLI |
| **Multi-cluster** | ✅ 1 ArgoCD → nhiều clusters | ⚠️ 1 Flux per cluster (hoặc Flux + remote cluster) |
| **Multi-tenancy** | ✅ AppProject + RBAC | ⚠️ K8s native RBAC |
| **SSO/OIDC** | ✅ Dex built-in | ❌ Cần tự setup |
| **Helm** | ✅ Native | ✅ HelmRelease CRD |
| **Kustomize** | ✅ Native | ✅ Kustomization CRD |
| **Jsonnet** | ✅ | ❌ |
| **Image Auto-update** | ⚠️ Argo Image Updater (beta) | ✅ Built-in Image Automation |
| **Drift Detection** | ✅ Real-time diff trong UI | ✅ Reconciliation loop |
| **Self-Heal** | ✅ Configurable per app | ✅ Default behavior |
| **Sync Waves** | ✅ Annotations-based ordering | ⚠️ Kustomization dependencies |
| **Hooks** | ✅ PreSync/Sync/PostSync | ⚠️ Limited |
| **Notifications** | ✅ ArgoCD Notifications | ✅ Notification Controller |
| **Resource footprint** | ⚠️ ~500MB RAM (all components) | ✅ ~200MB RAM |
| **ApplicationSet** | ✅ Template-based app generation | ❌ (dùng Kustomize generator) |
| **Health Assessment** | ✅ Built-in + custom | ✅ Basic |
| **Rollback** | ✅ UI/CLI rollback | ⚠️ Git revert only |
| **Community size** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Learning curve** | Medium | Low-Medium |

### Decision Framework

```
Cần Web UI?
├── Có → ArgoCD
└── Không
    ├── Quản lý nhiều clusters từ 1 nơi?
    │   ├── Có → ArgoCD
    │   └── Không
    │       ├── Cần image auto-update?
    │       │   ├── Có → Flux
    │       │   └── Không
    │       │       ├── Resource constrained (edge/IoT)?
    │       │       │   ├── Có → Flux
    │       │       │   └── Không → ArgoCD (UI + ecosystem)
    │       │       └──
    │       └──
    └──
```

---

## 2. ArgoCD CLI Cheat Sheet

### Installation

```bash
# Linux
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x argocd && sudo mv argocd /usr/local/bin/

# macOS
brew install argocd

# Verify
argocd version --client
```

### Login & Context

```bash
# Login
argocd login <server>:443 --insecure --username admin --password <pwd>
argocd login <server> --sso                    # SSO login

# Context management
argocd context                                  # List contexts
argocd context <server>                         # Switch context
```

### Application Management

```bash
# Create
argocd app create <name> \
  --repo <git-url> \
  --path <path> \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace <ns> \
  --sync-policy automated \
  --self-heal \
  --auto-prune

# List & Get
argocd app list
argocd app get <name>
argocd app get <name> --refresh                 # Force refresh from Git

# Sync
argocd app sync <name>
argocd app sync <name> --dry-run                # Preview changes
argocd app sync <name> --prune                  # Sync + prune deleted
argocd app sync <name> --force                  # Force sync (recreate)
argocd app sync <name> --resource apps:Deployment:<name>  # Sync specific resource

# Diff
argocd app diff <name>                          # Show diff Git vs cluster
argocd app diff <name> --local <path>           # Diff local vs cluster

# History & Rollback
argocd app history <name>
argocd app rollback <name> <revision>

# Delete
argocd app delete <name>                        # Delete app (keep resources)
argocd app delete <name> --cascade              # Delete app + resources

# Modify
argocd app set <name> --sync-policy automated
argocd app set <name> --self-heal
argocd app set <name> --auto-prune
argocd app unset <name> --sync-policy           # Disable auto-sync

# Wait
argocd app wait <name> --health                 # Wait until healthy
argocd app wait <name> --sync                   # Wait until synced

# Resources
argocd app resources <name>                     # List managed resources
argocd app logs <name>                          # App logs
```

### Repository Management

```bash
# Add repo
argocd repo add <url> --ssh-private-key-path ~/.ssh/id_rsa
argocd repo add <url> --username <user> --password <token>

# List repos
argocd repo list

# Remove repo
argocd repo rm <url>
```

### Project Management

```bash
# Create project
argocd proj create <name> -d https://kubernetes.default.svc,<namespace>
argocd proj add-source <name> <repo-url>

# List projects
argocd proj list
argocd proj get <name>

# RBAC
argocd proj role create <proj> <role>
argocd proj role add-policy <proj> <role> -a sync -p allow -o <app>
```

### Cluster Management

```bash
# Add external cluster
argocd cluster add <context-name>

# List clusters
argocd cluster list

# Remove cluster
argocd cluster rm <server>
```

---

## 3. Flux CLI Cheat Sheet

### Installation

```bash
# Linux/macOS
curl -s https://fluxcd.io/install.sh | sudo bash

# Verify
flux --version
flux check --pre                                # Pre-flight check
```

### Bootstrap

```bash
# Bootstrap with GitHub
flux bootstrap github \
  --owner=<org> \
  --repository=<repo> \
  --path=clusters/my-cluster \
  --personal

# Bootstrap with GitLab
flux bootstrap gitlab \
  --owner=<org> \
  --repository=<repo> \
  --path=clusters/my-cluster
```

### Source Management

```bash
# Git source
flux create source git <name> \
  --url=<git-url> \
  --branch=main \
  --interval=1m

# Helm source
flux create source helm <name> \
  --url=<helm-repo-url> \
  --interval=10m

# List sources
flux get sources git
flux get sources helm
```

### Kustomization

```bash
# Create
flux create kustomization <name> \
  --source=GitRepository/<git-name> \
  --path=<path> \
  --prune=true \
  --interval=5m

# List
flux get kustomizations

# Reconcile (force sync)
flux reconcile kustomization <name>

# Suspend/Resume
flux suspend kustomization <name>
flux resume kustomization <name>
```

### HelmRelease

```bash
# Create
flux create helmrelease <name> \
  --source=HelmRepository/<helm-name> \
  --chart=<chart-name> \
  --target-namespace=<ns>

# List
flux get helmreleases
```

### Monitoring

```bash
# Check Flux health
flux check

# Events
flux events

# Logs
flux logs --level=error
flux logs --kind=Kustomization --name=<name>

# Export (backup)
flux export source git --all > sources.yaml
flux export kustomization --all > kustomizations.yaml
```

---

## 4. GitOps Production Checklist

### Pre-deployment

```
□ Config repo tách riêng khỏi app repo
□ Branch protection enabled trên config repo (main/master)
□ PR review required (ít nhất 1 reviewer cho staging, 2 cho prod)
□ CI validation trên config repo (kustomize build, helm template, kubeval)
□ Secret management solution configured (Sealed Secrets / External Secrets)
□ No plaintext secrets trong Git history
```

### ArgoCD Setup

```
□ ArgoCD installed trong dedicated namespace
□ HA mode enabled cho production (3 replicas)
□ SSO configured (OIDC/LDAP) — admin password disabled
□ AppProjects defined cho mỗi team
□ RBAC policies configured
□ Repo credentials stored as K8s Secrets
□ Webhook configured từ Git → ArgoCD
□ Resource exclusions configured (events, endpoints)
□ Custom health checks cho CRDs
```

### Application Configuration

```
□ Sync Policy phù hợp:
  □ Dev: automated + selfHeal + prune
  □ Staging: automated + selfHeal, prune=false
  □ Prod: automated + selfHeal, prune=false (hoặc manual)
□ Retry policy configured
□ Sync Waves cho dependency ordering
□ ignoreDifferences cho auto-managed fields
□ Health check verified (readiness + liveness)
□ Resource hooks cho database migration (PreSync)
```

### Monitoring & Alerting

```
□ ArgoCD metrics exposed (Prometheus)
□ Dashboard created (Grafana)
□ Alerts configured:
  □ App OutOfSync > 10 min
  □ App Degraded > 5 min
  □ Sync Failed
  □ Component Unhealthy
□ Notifications configured (Slack/Teams/email)
□ Audit log enabled
```

### Security

```
□ Network Policy cho ArgoCD namespace
□ ArgoCD API Server behind VPN/auth proxy
□ Deploy keys (read-only) cho Git repos
□ RBAC least privilege per team
□ No wildcard permissions trong AppProject
□ Secret encryption at rest enabled
□ Regular credential rotation
```

### Disaster Recovery

```
□ ArgoCD config exported (Applications, Projects, Settings)
□ Git repo backed up (multiple remotes)
□ DR test: delete ArgoCD → reinstall → verify apps sync
□ Runbook documented cho ArgoCD recovery
□ Config repo có tag/release cho known-good state
```

---

## 5. ArgoCD Application YAML Templates

### Basic Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io  # Cascade delete
spec:
  project: default
  source:
    repoURL: https://github.com/org/config-repo.git
    targetRevision: main
    path: services/my-app/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app-dev
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
      prune: true
    syncOptions:
      - CreateNamespace=true
      - ApplyOutOfSyncOnly=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        maxDuration: 3m0s
        factor: 2
```

### Application with Helm

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app-helm
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://charts.example.com
    chart: my-app
    targetRevision: 1.2.3
    helm:
      releaseName: my-app
      values: |
        replicaCount: 3
        image:
          tag: v2.0.0
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
      valueFiles:
        - values-prod.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy: {}  # Manual sync mặc định cho production-sensitive release
```

### Application with Sync Waves

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app-ordered
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/config-repo.git
    targetRevision: main
    path: services/my-app
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      enabled: true
      selfHeal: true
---
# Trong manifests, dùng annotations cho ordering:
# Wave -1: Namespace, RBAC
# Wave 0: ConfigMap, Secret, PVC  (default)
# Wave 1: Deployment, Service
# Wave 2: Ingress, HPA
# Wave 3: Post-deploy Job (smoke test)
```

### ApplicationSet (Multi-env generator)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: my-app-all-envs
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - env: dev
            namespace: dev
            autoSync: "true"
            selfHeal: "true"
            prune: "true"
          - env: staging
            namespace: staging
            autoSync: "true"
            selfHeal: "true"
            prune: "false"
          - env: prod
            namespace: prod
            autoSync: "true"
            selfHeal: "true"
            prune: "false"
  template:
    metadata:
      name: 'my-app-{{env}}'
      namespace: argocd
    spec:
      project: default
      source:
        repoURL: https://github.com/org/config-repo.git
        targetRevision: main
        path: 'services/my-app/overlays/{{env}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          enabled: true
          selfHeal: true
          prune: false
```

---

## 6. Debugging Decision Tree

```
ArgoCD App Issue?
│
├── Status: Unknown
│   ├── Check: argocd app get <name>
│   ├── Possible: Repo unreachable
│   │   ├── Check: argocd repo list
│   │   ├── Fix: Update credentials / check network
│   │   └── Fix: Check SSH key / token expiry
│   └── Possible: Manifest render failure
│       ├── Check: kubectl logs -n argocd deploy/argocd-repo-server
│       └── Fix: Fix Helm values / Kustomize syntax
│
├── Status: OutOfSync
│   ├── Expected? (Manual sync policy)
│   │   ├── Yes → argocd app sync <name>
│   │   └── No → Check if selfHeal is enabled
│   ├── Drift detected?
│   │   ├── Check: argocd app diff <name>
│   │   ├── Who changed? kubectl get events
│   │   └── Fix: Enable selfHeal or revert manual change
│   └── ignoreDifferences needed?
│       └── Add to Application spec → fields that controllers auto-manage
│
├── Status: SyncFailed
│   ├── Check: argocd app get <name> (last sync result)
│   ├── RBAC issue?
│   │   └── Check: kubectl auth can-i (ArgoCD ServiceAccount)
│   ├── Validation error?
│   │   └── Check: kubectl apply --dry-run=server
│   ├── Resource conflict?
│   │   └── Check: resource owned by another controller
│   └── Quota exceeded?
│       └── Check: kubectl describe quota -n <ns>
│
├── Health: Degraded
│   ├── Pod issues?
│   │   ├── CrashLoopBackOff → Check logs
│   │   ├── ImagePullBackOff → Check image/registry
│   │   └── OOMKilled → Increase memory limits
│   ├── Service issues?
│   │   └── No healthy endpoints → Check selector/pods
│   └── Ingress issues?
│       └── Check ingress controller logs
│
└── Health: Missing
    ├── Resources deleted outside ArgoCD?
    │   └── Sync to recreate
    └── Namespace deleted?
        └── Check syncOptions: CreateNamespace=true
```

---

## 7. GitOps Workflow Diagrams

### CI + GitOps Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Workflow                         │
│                                                              │
│  1. Developer pushes code to app repo                       │
│  2. CI pipeline: lint → test → build → scan → push image    │
│  3. CI bot updates image tag in config repo                  │
│  4. ArgoCD detects change in config repo                     │
│  5. ArgoCD syncs new state to cluster                        │
│  6. Health check passes → deployment complete                │
│                                                              │
│  ┌──────┐    ┌────────┐    ┌────────────┐    ┌───────────┐  │
│  │ Code │───▶│   CI   │───▶│ Config Repo│◀───│  ArgoCD   │  │
│  │ Repo │    │Pipeline│    │ (Git)      │    │ (Cluster) │  │
│  └──────┘    └────────┘    └────────────┘    └───────────┘  │
│      │           │              │                  │         │
│   git push   build+test    update tag          sync+heal    │
│              push image    (PR/commit)         (pull model)  │
└─────────────────────────────────────────────────────────────┘
```

### Promotion Flow

```
┌──────────────────────────────────────────────────────────┐
│                   Promotion Pipeline                      │
│                                                           │
│     DEV              STAGING            PROD              │
│  ┌────────┐       ┌────────┐        ┌────────┐          │
│  │Auto-   │  PR   │Auto-   │  PR    │Auto-   │          │
│  │deploy  │──────▶│deploy  │───────▶│deploy  │          │
│  │        │       │        │ 2 rev. │        │          │
│  │v1.2.3  │       │v1.2.3  │ req'd  │v1.2.3  │          │
│  └────────┘       └────────┘        └────────┘          │
│      ▲                                                    │
│      │                                                    │
│  CI builds                                                │
│  new image                                                │
└──────────────────────────────────────────────────────────┘
```

---

## 8. Phase 4 Summary: IaC & GitOps

| Day | Topic | Tool | Key Concept |
|-----|-------|------|-------------|
| 26 | IaC Principles | Concepts | Declarative, desired state, drift, idempotency |
| 27 | Terraform Basics | Terraform | Provider, resource, state, plan/apply |
| 28 | Terraform Advanced | Terraform | Remote state, modules, drift, import |
| 29 | IaC Comparison | Terraform/Pulumi/CDK | DSL vs GPL, decision framework |
| 30 | Config Management | Ansible | Agentless, playbook, role, idempotent |
| 31 | GitOps | ArgoCD/Flux | Git as source of truth, pull model, self-heal |

### Khi nào dùng tool nào

```
Infrastructure (VPC, cluster, DB, DNS)
  └── Terraform / Pulumi / CDK

Server Configuration (packages, users, files)
  └── Ansible

Kubernetes Workloads (deployments, services)
  └── ArgoCD / Flux (GitOps)

All of above
  └── Git (version control, review, audit)
```

