# Day 17 - GitOps Principles & ArgoCD Architecture

**Thời lượng:** 2 tiếng (30 phút lý thuyết + 30 phút deep dive + 60 phút lab)
**Folder lab:** `D:/my-source/learning/terraform-ansible-argocd/week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/`

---

## 1. Mục tiêu ngày học

Sau ngày học, học viên sẽ:

- Giải thích được 4 nguyên tắc GitOps và phân biệt được sự khác biệt giữa CI/CD push-based và GitOps pull-based deployment
- Mô tả được từng component trong kiến trúc ArgoCD (API server, repo-server, application-controller, dex, redis) và data flow giữa chúng
- Phân biệt được khi nào nên dùng ArgoCD vs Flux dựa trên team size, architecture, và use-case thực tế
- Cài đặt được ArgoCD trên kind cluster local và deploy ứng dụng đầu tiên qua Git (cả qua CLI lẫn declarative YAML)
- Quan sát được reconciliation loop và drift detection thực tế trên cluster

---

## 2. Bối cảnh thực tế

### Câu chuyện: Team Microservices chuyển từ Push-based sang GitOps

Một team có 12 microservices deploy qua Jenkins pipeline push-based. Pipeline mỗi lần chạy đều có quyền `cluster-admin` để `kubectl apply` manifest lên production cluster.

**Những vấn đề xảy ra hàng ngày:**

1. **Security risk**: CI server có quyền cluster-admin — nếu Jenkins bị compromise, kẻ tấn công có toàn quyền trên cluster. Không có RBAC per-pipeline, không có audit trail cho từng deployment action.

2. **Drift không ai phát hiện**: Devops engineer ssh vào server, chỉnh sửa Deployment replicas cho test nhanh, quên commit lên Git. 2 tuần sau không ai hiểu tại sao staging replicas không match với production.

3. **Rollback chậm**: Muốn rollback về version trước phải re-run Jenkins job với image tag cũ. Log scattered giữa Jenkins history, kubectl events, và Slack message của người deploy. Audit trail rời rạc, không có single source of truth.

4. **Multi-cluster khó quản lý**: Có 3 cluster (dev, staging, prod). Mỗi cluster có pipeline riêng. Khi cần push hotfix lên cả 3 cluster cùng lúc, phải chạy 3 Jenkins job, không có cách nào đảm bảo chúng sync.

**GitOps giải quyết như thế nào:**

| Vấn đề cũ | Giải pháp GitOps |
|---|---|
| Pipeline có cluster-admin | CI chỉ commit vào Git, không có cluster credential |
| Drift không phát hiện | ArgoCD agent liên tục reconcile, drift = OutOfSync |
| Rollback = re-run job | Rollback = `git revert`, ArgoCD sync ngay |
| Audit scattered | Git history = audit log hoàn chỉnh |
| Multi-cluster khó | Mỗi cluster có agent riêng pull cùng Git (hoặc 1 ArgoCD quản lý nhiều cluster) |

**Transition plan thực tế:**
- Day 1-3: Cài ArgoCD, deploy 1 app đơn giản (lab hôm nay)
- Day 4-7: Migrate từng service, CI chuyển từ `kubectl apply` sang `git commit`
- Week 2: Bật automated sync, loại bỏ Jenkins credential khỏi cluster
- Week 3: Multi-cluster, ApplicationSet (Day 22)

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 GitOps là gì?

GitOps là tập hợp các best practice để quản lý infrastructure và application configuration thông qua Git. Khái niệm được phổ biến bởi Weaveworks (2017) và sau đó được CNCF formalize qua **OpenGitOps** project.

**4 nguyên tắc cốt lõi của OpenGitOps:**

```
┌─────────────────────────────────────────────────────────────┐
│                   4 GitOps Principles (OpenGitOps)          │
├─────────────────────────────────────────────────────────────┤
│  1. DECLARATIVE                                             │
│     Toàn bộ system được mô tả declarative (YAML/JSON),      │
│     không phải imperative script                           │
│                                                             │
│  2. VERSIONED & IMMUTABLE                                   │
│     Desired state được lưu trong Git, mọi thay đổi         │
│     đều có commit history, có thể rollback                 │
│                                                             │
│  3. PULLED AUTOMATICALLY                                    │
│     Agent trên cluster tự động pull desired state từ Git,  │
│     không có external trigger từ CI pipeline                │
│                                                             │
│  4. CONTINUOUSLY RECONCILED                                 │
│     Agent liên tục so sánh actual state (cluster) với       │
│     desired state (Git), tự động corrective action nếu     │
│     có drift                                                │
└─────────────────────────────────────────────────────────────┘
```

**Tại sao GitOps phù hợp với Kubernetes:**

Kubernetes đã có declarative model ở level resource (Pod, Deployment, Service...). Bạn viết `replicas: 3`, Kubernetes controller đảm bảo cluster state = desired state. GitOps mở rộng pattern này lên level application và infrastructure:

```
Layer 1 (Kubernetes):  Controller reconciler Pod/Deployment/Service
                        etcd ← kubectl ← desired state

Layer 2 (GitOps):      ArgoCD/Flux reconciler entire application
                        Git  ← ArgoCD  ← desired state

Pattern giống nhau: desired state + reconciliation loop
Chỉ khác scope và trigger: etcd vs Git
```

**So sánh Push-based vs Pull-based:**

```
PUSH-BASED (CI/CD truyền thống)
─────────────────────────────────
  Developer → Git commit → CI Pipeline → kubectl apply → Cluster
                ↑                              │
                │                              │
        Pipeline có credential            Credential
        để access cluster                  nằm ở CI server


PULL-BASED (GitOps)
────────────────────
  Developer → Git commit
       │
       ▼
  Git Repo (source of truth)
       │  ArgoCD/Flux agent pull
       ▼
  Cluster ←─────────────
       │  continuous reconcile
       ▼
  Self-heal nếu drift
```

**Ưu điểm Pull-based:**
- CI server không cần cluster credential — giảm attack surface đáng kể
- Multi-cluster scale tốt: mỗi cluster có agent riêng, cluster mới chỉ cần install agent + point vào Git
- Outbound-only network: cluster không cần expose API port cho external access
- Disaster recovery đơn giản: cluster mới chỉ cần ArgoCD/Flux installed + Git URL

**Ưu điểm Push-based:**
- Setup đơn giản hơn cho 1-2 cluster
- Latency thấp hơn (CI chạy xong là deploy ngay)
- Phù hợp cho environment không có persistent agent (serverless)

### 3.2 Desired State vs Actual State vs Reconciliation Loop

Đây là trái tim của cả Kubernetes controller pattern lẫn GitOps.

```
┌──────────────────────────────────────────────────────────────────┐
│                     ArgoCD Reconciliation Loop                    │
│                                                                  │
│   ┌──────────────┐         ┌──────────────────────┐              │
│   │   Git Repo   │         │    Kubernetes API    │              │
│   │(desired state)│        │   (actual state)     │              │
│   └──────┬───────┘         └──────────┬───────────┘              │
│          │ git clone                  │ kubectl get              │
│          │                            │                          │
│          ▼                            ▼                          │
│   ┌──────────────┐         ┌──────────────────────┐              │
│   │ repo-server  │         │  application-        │              │
│   │ render Helm/ │         │  controller           │              │
│   │ Kustomize   │────────▶│  compare & reconcile  │              │
│   └──────────────┘ manifest└──────────────────────┘              │
│          │                            │                          │
│          │                            │ kubectl apply           │
│          ▼                            ▼                          │
│   manifest ①              ┌──────────────────────┐              │
│   (after render)          │ Cluster matches Git?  │              │
│                           │  YES → Healthy ✅     │              │
│                           │  NO  → OutOfSync 🔴   │              │
│                           └──────────────────────┘              │
└──────────────────────────────────────────────────────────────────┘

Mặc định: reconciliation mỗi 3 phút
Có thể trigger manual: argocd app sync <app-name>
```

**Sync Policy variants:**

```yaml
# Policy 1: Manual (default)
syncPolicy:
  automated: null  # không có gì → manual only
# → ArgoCD chỉ alert OutOfSync, KHÔNG tự apply
# → Phù hợp: production environment, cần human approval

# Policy 2: Automated (Git changes trigger sync)
syncPolicy:
  automated:
    prune: false   # KHÔNG xóa resource không còn trong Git
    selfHeal: false # KHÔNG revert cluster drift (chỉ apply Git changes)
# → ArgoCD tự apply khi Git thay đổi
# → Phù hợp: staging, dev environment

# Policy 3: Automated + Self-Heal (aggressive)
syncPolicy:
  automated:
    prune: true    # Xóa resource không còn trong Git
    selfHeal: true # Revert cluster drift (dù drift từ đâu)
# → ArgoCD reconcile cả Git changes lẫn manual cluster changes
# → Phù hợp: dev environment, immutable infrastructure
```

**Drift detection scenarios:**

| Drift type | Git nói | Cluster thực tế | ArgoCD behavior (manual) | ArgoCD behavior (selfHeal) |
|---|---|---|---|---|
| Replicas change | `replicas: 3` | `replicas: 5` | OutOfSync alert | Auto-revert to 3 |
| Image tag change | `image: v1.2.0` | `image: v1.3.0` | OutOfSync alert | Auto-revert to v1.2.0 |
| Label missing | có label `app: backend` | label bị xóa | OutOfSync alert | Auto-add label |
| Resource deleted | Deployment tồn tại | Deployment bị xóa | OutOfSync alert | Auto-recreate |
| Resource added | không có | manual Deployment | Prune=false: ignore | Prune=true: delete |

### 3.3 Pull-based vs Push-based — chi tiết

```
PUSH-BASED DEPLOYMENT (Jenkins / GitLab CI / GitHub Actions)

┌─────────────┐    commit    ┌─────────────┐   kubectl   ┌──────────┐
│  Developer  │ ───────────▶│ CI Pipeline │ ──────────▶│ Cluster  │
└─────────────┘              └─────────────┘             └──────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │ jenkins has │
                            │ cluster cred│ ← Security risk
                            └─────────────┘


PULL-BASED DEPLOYMENT (ArgoCD / Flux)

┌─────────────┐    commit    ┌─────────────┐
│  Developer  │ ───────────▶│   Git Repo  │
└─────────────┘              └──────┬──────┘
                                    │ agent pull (every 3 min)
                                    ▼
┌─────────────┐              ┌─────────────┐   kubectl   ┌──────────┐
│  Developer  │              │ ArgoCD/Flux │ ──────────▶│ Cluster  │
└─────────────┘              └─────────────┘             └──────────┘
                                    │
                              CI pipeline
                              KHÔNG có
                              cluster cred


HYBRID (GitOps + CI notification)

┌─────────────┐    commit    ┌─────────────┐
│  Developer  │ ───────────▶│   Git Repo  │
└─────────────┘              └──────┬──────┘
         ▲                         │ agent pull
         │                         ▼
         │                  ┌─────────────┐   kubectl   ┌──────────┐
         │                  │ ArgoCD/Flux │ ──────────▶│ Cluster  │
         │                  └─────────────┘             └──────────┘
         │                         ▲
         │                         │ notify
         │                  ┌─────────────┐
         └──────────────────│ CI Pipeline │  ← chỉ notify, không deploy
                            └─────────────┘
```

### 3.4 ArgoCD Architecture

```
                         ┌─────────────────────────────────────┐
                         │          ArgoCD Architecture       │
                         └─────────────────────────────────────┘

  External                                ArgoCD Namespace
  ─────────                               ────────────────

  User (CLI/UI) ─────── HTTPS ──────┐
  ───────────────────────────────┐   │ gRPC/HTTPS
                                  ▼   ▼
                         ┌──────────────────────┐
                         │  argocd-server       │
                         │  (API server)        │
                         │  Port: 443           │
                         │  - REST + gRPC API   │
                         │  - Auth + RBAC       │
                         │  - Session mgmt      │
                         │  - Serve UI          │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
    │ argocd-applicati-│  │ argocd-repo-     │  │ argocd-dex-server   │
    │ on-controller    │  │ server           │  │ (optional)          │
    │                   │  │                  │  │                     │
    │ - Watch App CRD   │  │ - git clone      │  │ - OIDC/SAML/LDAP    │
    │ - Reconcile loop  │  │ - Helm render    │  │   bridge            │
    │ - kubectl apply   │  │ - Kustomize build│ │ - SSO integration   │
    │ - Health check    │  │ - Generate manifest││                     │
    │ - Sync waves      │  │ - Cache manifests │ │                     │
    └────────┬─────────┘  └────────┬─────────┘  └─────────────────────┘
             │                     │
             │ kubectl apply       │ git / Helm / Kustomize
             │ health check        │
             ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ Kubernetes API  │  │   Git Repos     │
    │ (your apps)     │  │  (desired state) │
    └──────────────────┘  └──────────────────┘

    ┌──────────────────┐
    │ argocd-redis    │
    │ - Session cache │
    │ - Manifest cache│
    │ - Token cache   │
    └──────────────────┘

    ┌────────────────────────────────────┐
    │ argocd-applicationset-controller  │ ← Optional (Day 22)
    │ argocd-notifications-controller     │ ← Optional
    └────────────────────────────────────┘
```

**Chi tiết từng component:**

#### 3.4.1 argocd-server (API Server)

- **Image**: `quay.io/argoproj/argocd:<version>`
- **Deployment** (1 replica mặc định, có thể scale 2+ với Redis HA)
- **Port**: 443 (gRPC+HTTPS), 8080 (HTTP, không dùng trong production)
- **Role**: 
  - REST + gRPC API cho CLI và UI
  - Authentication (password, OIDC, SSO via Dex)
  - RBAC enforcement
  - Project và Application CRUD
  - Webhook handler (Git webhook → trigger sync)
- **Không stateless hoàn toàn**: cần Redis cho session storage
- **Có thể expose external**: thường qua Ingress hoặc port-forward local

#### 3.4.2 argocd-repo-server

- **Image**: `quay.io/argoproj/argocd:<version>`
- **Deployment** (1+ replica)
- **Role**:
  - Clone Git repositories
  - Render Helm charts (server-side rendering)
  - Run Kustomize build
  - Generate final manifests từ mixed sources
  - Cache manifests theo revision (không pull lại nếu revision không đổi)
- **Stateless**: có thể scale nhiều replica để handle nhiều app đồng thời
- **Memory intensive**: nếu repo lớn (monorepo), cần nhiều RAM, có thể OOM → cần resource limit
- **Git credential**: credentials lưu trong cluster Secret, repo-server sử dụng để clone private repo

#### 3.4.3 argocd-application-controller

- **Image**: `quay.io/argoproj/argocd:<version>`
- **StatefulSet** (1 replica mặc định, có thể sharding cho 1000+ app)
- **Role**:
  - Watch `Application` CRD (ArgoCD CRD, không phải K8s standard CRD)
  - Reconciliation loop: so sánh desired state (từ repo-server) với actual state (từ Kubernetes API)
  - Execute kubectl apply/helm install/kustomize apply
  - Health check resource sau khi apply
  - Emit Kubernetes events khi sync
  - Handle Sync Waves và Hooks
- **Reconciliation interval**: mặc định 3 phút, configurable qua `timeout.reconciliation` trong argocd-cm
- **Sharding**: khi có 1000+ Application, cần sharding qua `controller.shards` (2+ replicas, mỗi quản lý subset)

#### 3.4.4 argocd-dex-server

- **Image**: `quay.io/argoproj/argocd-dex-server:<version>`
- **Deployment** (1 replica)
- **Role**: OIDC/SAML/LDAP bridge cho SSO
  - GitHub OAuth, GitLab, Google, LDAP, SAML 2.0
  - ArgoCD UI login → Dex → Identity provider → ArgoCD
- **Optional**: nếu không dùng SSO (chỉ dùng local admin account), có thể disable
- **Production**: nên disable Dex, dùng direct OIDC provider thay thế

#### 3.4.5 argocd-redis

- **Image**: `redis:<version>`
- **Deployment** (1 replica, 3 cho HA)
- **Role**:
  - Cache manifests đã render (giảm repo-server load)
  - Session storage (user login session, token)
  - Rate limiting
- **Persistence**: không cần PVC (stateless cache)
- **HA mode**: cần 3 replicas + Redis Sentinel hoặc Redis HA chart

#### 3.4.6 argocd-applicationset-controller (optional)

- **Image**: `quay.io/argoproj/argocd:<version>` (same image, different entrypoint)
- **Deployment**
- **Role**: Generate Application từ template (Day 22)
  - Pull from Git generator (list apps từ file trong Git)
  - Matrix generator
  - SCM provider generator (GitHub, GitLab)
  - Cluster generator

#### 3.4.7 argocd-notifications-controller (optional)

- **Image**: `quay.io/argoproj/argocd:<version>`
- **Deployment**
- **Role**: Notify Slack, Teams, Email khi app sync/health state thay đổi

**Data flow tổng hợp cho một sync cycle:**

```
1. User/Webhook triggers sync
   │
   ▼
2. argocd-server receives sync request (gRPC)
   │
   ▼
3. argocd-server creates Sync task, enqueues
   │
   ▼
4. argocd-application-controller picks up sync task
   │
   ▼
5. application-controller calls repo-server:
   │   POST /generate  (send Application spec)
   │   repo-server clones Git, renders Helm/Kustomize
   │   returns rendered manifests
   │
   ▼
6. application-controller diffs:
   │   rendered manifests vs actual cluster state (kubectl get)
   │
   ▼
7. application-controller applies diff:
   │   kubectl apply / helm upgrade / kustomize apply
   │
   ▼
8. application-controller health checks:
   │   kubectl get, check pod status
   │
   ▼
9. application-controller updates Application CRD status:
   │   status.sync.status = Synced
   │   status.health.status = Healthy
   │
   ▼
10. argocd-server reflects new status in UI
```

### 3.5 Application CRD — Preview cho Day 18

ArgoCD định nghĩa `Application` như một CRD (Custom Resource Definition) trong Kubernetes. Application CRD mô tả: ứng dụng nào, ở đâu trong Git, deploy đến đâu trong cluster, và sync policy ra sao.

```yaml
# application-guestbook.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook              # Tên Application trong ArgoCD
  namespace: argocd            # ArgoCD quản lý CRD trong namespace argocd
spec:
  project: default             # AppProject — namespace/cluster permission (Day 18)
  
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD       # Có thể là tag, branch, commit SHA
    path: guestbook            # Thư mục chứa manifest (hoặc Helm chart path)
    
  destination:
    server: https://kubernetes.default.svc  # Cluster Kubernetes target
    # server: https://<remote-cluster-api>  # Remote cluster (Day 22)
    namespace: default         # Namespace deploy trong cluster
    
  syncPolicy:
    automated:                 # null = manual; bật = automated
      prune: true             # Xóa resource không còn trong Git
      selfHeal: true          # Revert drift trên cluster
    syncOptions:
    - CreateNamespace=true     # Tự động tạo namespace nếu chưa có
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
```

Cấu trúc tóm tắt Application spec:

```
Application.spec
├── project          # AppProject name (RBAC boundary)
├── source           # Git/Helm repo + path/tag
│   ├── repoURL
│   ├── path         # (hoặc chart.name + chart.version cho Helm)
│   └── targetRevision
├── destination      # Cluster + namespace target
│   ├── server
│   └── namespace
├── syncPolicy       # Manual / Automated / Self-Heal
├── ignoreDifferences # Bỏ qua một số field khi diff (e.g., status)
└── info             # Metadata hiển thị trong UI
```

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 So sánh ArgoCD vs Flux v2

Đây là câu hỏi phỏng vấn DevOps thường gặp. Cả hai đều là CNCF Graduated projects, đều implement GitOps, nhưng có philosophy và capability khác nhau đáng kể.

```
┌──────────────────────────────────────────────────────────────────────┐
│                   ArgoCD vs Flux v2 — Full Comparison                │
├─────────────────────┬──────────────────────┬────────────────────────┤
│ Tiêu chí            │ ArgoCD               │ Flux v2                │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Born                │ 2018, Intuit/CNCF    │ 2019, Weave/CNCF       │
│ Architecture        │ Centralized          │ Decentralized          │
│                     │ (1 ArgoCD quản lý    │ (Flux agent per        │
│                     │  nhiều cluster)      │  cluster, no central) │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ UI                  │ Built-in, rich       │ No built-in UI         │
│                     │ - App tree view      │ Need: Weave GitOps     │
│                     │ - Diff view          │ (OSS) hoặc thuê 3rd    │
│                     │ - History/timeline   │ party như Flux Cloud   │
│                     │ - Sync graph         │                        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Application model   │ Application CRD      │ GitRepository CRD      │
│                     │ (1 CR = 1 app)       │ + Kustomization CRD    │
│                     │                      │ + HelmRelease CRD      │
│                     │                      │ (compose nhiều CRD)    │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Multi-cluster mgmt  │ Central ArgoCD quản  │ Mỗi cluster cài Flux   │
│                     │ lý nhiều cluster     │ riêng, quản lý qua     │
│                     │ qua context          │ GitOps engine (GitOps  │
│                     │                      │ Operator per cluster)  │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ ApplicationSet /    │ Có (generators:      │ Không có. Dùng         │
│ Template mgmt       │ Git, Matrix, SCM,    │ Kustomize overlay      │
│                     │ Cluster)             │ hoặc Fleet (experimental│
│                     │ → generate 1000+ App │                      │
│                     │ từ 1 template        │                      │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Multi-tenancy       │ AppProject + RBAC    │ Namespace + RBAC       │
│                     │ - Limit namespace    │ - ns-scoped Flux       │
│                     │ - Limit cluster      │ - IRSA/k8s RBAC        │
│                     │ - Role binding       │                        │
│                     │ - Quota              │                        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ SSO / Auth          │ Dex built-in         │ External OIDC only     │
│                     │ (OIDC, SAML, LDAP)  │ (no built-in bridge)   │
│                     │                      │                        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Image Automation    │ ArgoCD Image         │ Image Reflector +      │
│                     │ Updater (extra)      │ Automation CRD built-in│
│                     │                      │ (watch image tag,      │
│                     │                      │  auto-commit Git)      │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Helm support        │ Server-side render   │ Helm Controller        │
│                     │ via repo-server     │ (server-side)          │
│                     │ OCI registry: hỗ trợ│ OCI registry: hỗ trợ   │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Notification        │ Notifications        │ Notifications CRD      │
│                     │ Controller (optional)│ built-in               │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Dependency mgmt    │ No native            │ Kustomize dependency   │
│                     │ (dùng Kustomize)    │ (kustomize.yaml refs)  │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Drift handling      │ OutOfSync detection  │ Resource health +      │
│                     │ + selfHeal           │ drift detection        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ CLI                 │ argocd CLI           │ flux CLI               │
│                     │ (rich commands)      │ (rich commands)        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ GitOps Toolkit     │ ArgoCD Core          │ Flux is GitOps Toolkit │
│ compatibility      │ (không dùng Flux)    │ (use with other tools) │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Rollback           │ Via ArgoCD UI/CLI    │ Via flux reconcile     │
│                     │ git revert + sync    │ --with-source          │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Resource footprint │ ~1GB RAM (full)      │ ~300MB RAM (lighter)   │
│ (default install)  │                      │                        │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Upgrade path       │ Helm/kubectl apply   │ flux bootstrap         │
│                     │ (manual)             │ (automated via CLI)   │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Managed service    │ Akuity Platform      │ Flux Cloud (Weaveworks)│
│                    │ (3rd party, paid)    │ (paid, SaaS option)   │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Observability       │ Prometheus metrics   │ Prometheus metrics     │
│                     │ + Grafana dashboard  │ + Grafana dashboard   │
├─────────────────────┼──────────────────────┼────────────────────────┤
│ Common use cases   │ - Enterprise (RBAC)  │ - Multi-cluster edge   │
│                    │ - Multi-team         │ - Progressive delivery │
│                    │ - Need UI for dev    │ - Git-native mindset   │
│                    │ - Progressive delivery│ - Team autonomy      │
│                    │   (Rollouts)         │                        │
└─────────────────────┴──────────────────────┴────────────────────────┘
```

**Decision matrix thực tế:**

```
Chọn ArgoCD khi:
  ✅ Team cần UI để developer tự debug (không phải ai cũng thành thạo CLI)
  ✅ Multi-team, cần RBAC/AppProject
  ✅ Quản lý nhiều cluster từ 1 central control plane
  ✅ Cần ApplicationSet cho 100+ microservice
  ✅ Cần deploy từ nhiều Git repos khác nhau
  ✅ Đã dùng Argo Rollouts (progressive delivery)

Chọn Flux khi:
  ✅ Multi-cluster, decentralized architecture (mỗi cluster tự quản lý)
  ✅ Team ưa thích Git-native, GitOps Toolkit (gồm many controllers)
  ✅ Cần built-in image automation
  ✅ Cần lightweight footprint (edge, IoT clusters)
  ✅ Dùng Weave GitOps (UI layer trên Flux)
  ✅ Team có kinh nghiệm với Kubernetes operators

Không chọn ArgoCD khi:
  ❌ Cluster resource cực kỳ hạn chế (cân nhắc Flux nhẹ hơn)
  ❌ Cần decentralized multi-cluster không central control plane
  ❌ Chỉ cần simple CI trigger, không cần full GitOps

Không chọn Flux khi:
  ❌ Team cần UI cho non-DevOps (PM, manager muốn xem status)
  ❌ Không có kinh nghiệm viết nhiều CRD YAML
```

**Hybrid pattern**: Nhiều organization dùng ArgoCD làm central control plane + Flux trên edge cluster. ArgoCD manage cluster chính, edge cluster tự deploy qua Flux bootstrap.

### 4.2 Security Deep Dive

#### 4.2.1 ArgoCD RBAC permissions (AppProject)

```yaml
# appproject-example.yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: backend-team
  namespace: argocd
spec:
  description: Backend team project
  sourceRepos:
    - 'https://github.com/org/backend-services.git'
    - 'https://github.com/org/shared-libs.git'
  destinations:
    - server: https://kubernetes.default.svc
      namespace: backend-*
  namespaceResourceBlacklist:
    # Backend team không được tạo resource trong kube-system
    - group: ''
      kind: Namespace
  clusterResourceBlacklist:
    # Không được apply cluster-wide resource
    - group: 'rbac.authorization.k8s.io'
      kind: ClusterRoleBinding
  roles:
    - name: developer
      description: Developer role
      policies:
        - p, proj:backend-team:developer,applications,get,backend-team/*,allow
        - p, proj:backend-team:developer,applications,sync,backend-team/*,allow
        - p, proj:backend-team:developer,applications,override,backend-team/*,deny
          # Developer có thể sync nhưng không được override health check
```

#### 4.2.2 Secret management cho Git credentials

ArgoCD lưu Git credentials trong Kubernetes Secret. Production cần:

1. **Encrypt etcd** (KMS encryption at rest)
2. **Sealed Secrets hoặc External Secrets Operator**:
```yaml
# external-secret-gitcreds.yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: argocd-repo-creds
  namespace: argocd
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: argocd-repo-creds
    creationPolicy: Owner
  data:
    - secretKey: git-username
      remoteRef:
        key: production/argocd/github
        property: username
    - secretKey: git-password
      remoteRef:
        key: production/argocd/github
        property: token
```

#### 4.2.3 argocd-server RBAC default roles

```
role:admin     → toàn quyền (không nên assign cho user thường)
role:edit      → sync app, view, không delete app
role:view      → chỉ view, không sync
custom roles   → define trong AppProject policies
```

### 4.3 Performance Considerations

#### Reconciliation interval

```bash
# Thay đổi reconciliation interval (default: 3 phút)
# ArgoCD ConfigMap
kubectl edit configmap argocd-cm -n argocd
```
```yaml
data:
  timeout.reconciliation: 180s  # 3 phút (default)
  # Giảm xuống 60s cho dev environment (tăng API load)
  # Tăng lên 600s cho large cluster (giảm load)
```

#### Application controller sharding (1000+ apps)

```bash
# Scale application-controller ra nhiều replicas với sharding
# argocd-cm ConfigMap
kubectl edit configmap argocd-cm -n argocd
```
```yaml
data:
  controller.sharding.algorithm: round-robin
  # Các algorithms: round-robin, consistent-hash (key by app name)
  # round-robin: chia app đều cho các shard
  # consistent-hash: app cùng name luôn cùng shard (tránh reconcile conflict)
```

```bash
# Scale StatefulSet
kubectl scale statefulset argocd-application-controller \
  -n argocd --replicas=3
```

#### Repo-server scaling

```bash
# Repo-server OOM prevention: set resource limit
kubectl edit deploy argocd-repo-server -n argocd
```
```yaml
resources:
  requests:
    memory: 256Mi
    cpu: 500m
  limits:
    memory: 2Gi   # Quan trọng: prevent OOM cho monorepo
    cpu: 2000m
```

### 4.4 Common Pitfalls

```
⚠️  Pitfall 1: Bật automated sync quá sớm
    Hậu quả: prune=true xóa resource không mong muốn
    Giải pháp: Test trên dev trước, bắt đầu với automated: { prune: false, selfHeal: false }
    Sau 1 tuần không drift: bật selfHeal
    Sau 2 tuần: bật prune

⚠️  Pitfall 2: targetRevision: HEAD (tracking latest commit)
    Hậu quả: Unintentional commit = immediate deployment
    Giải pháp: Lock targetRevision vào tag hoặc commit SHA
    → Khi merge PR: tự động update targetRevision qua CI

⚠️  Pitfall 3: Application chứa quá nhiều resource không liên quan
    Hậu quả: Sync hook chạy không đúng thứ tự
    Giải pháp: Dùng Sync Wave (annotations), hoặc chia thành nhiều Application

⚠️  Pitfall 4: Dùng --insecure cho Git private repo
    Hậu quả: Token/password truyền plain text
    Giải pháp: Dùng HTTPS + TLS, configure certificate

⚠️  Pitfall 5: Quên resource quota cho repo-server
    Hậu quả: Monorepo lớn → repo-server OOM kill → tất cả app OutOfSync
    Giải pháp: Set memory limit + requests cho repo-server

⚠️  Pitfall 6: Không có backup của ArgoCD config
    Hậu quả: Cluster crash → mất tất cả Application definition
    Giải pháp: GitOps-ify ArgoCD config (Application as Code)
    → argocd-apps config sync từ Git repo riêng
```

### 4.5 ArgoCD in Production — Checklist

```
Pre-deployment:
  ☐ Quyết định deployment mode: standalone vs HA
  ☐ Plan RBAC: ai được sync, ai được view, ai được admin
  ☐ Secret management: Vault/Sealed Secrets cho Git credentials
  ☐ Backup strategy: export ArgoCD resources as YAML
  ☐ Network: cluster → Git outbound only, không cần inbound cho CI
  ☐ Resource quota: repo-server memory limit

Post-deployment:
  ☐ SSO integration (LDAP/GitHub OAuth)
  ☐ Notification: Slack/Teams integration
  ☐ Monitoring: Prometheus metrics + Grafana dashboard
  ☐ Log aggregation: application-controller logs
  ☐ Backup: CronJob export ArgoCD resources to Git
  ☐ Security: RBAC AppProject, disable admin default account
```

---

## 5. Hands-on Lab — 60 phút

**Mục tiêu lab:** Cài ArgoCD trên kind cluster local, deploy app đầu tiên, quan sát reconciliation loop, simulate drift.

**Pre-requisites:**
- Docker Desktop (Windows 11) với WSL2 backend, hoặc Docker Engine standalone
- kind >= 0.20.0
- kubectl >= 1.28
- Helm >= 3.13
- Git
- argocd CLI v3.4.x (hoặc một release ArgoCD còn supported)

### 5.1 Cài đặt pre-requisites (nếu chưa có)

**Trên Windows 11 + WSL2:**

```bash
# Trong WSL2 terminal (Ubuntu 22.04)
# 1. kind
curl -Lo /usr/local/bin/kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x /usr/local/bin/kind

# 2. kubectl
curl -Lo /usr/local/bin/kubectl \
  "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl

# 3. Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 4. argocd CLI
# Download từ GitHub release v3.4.x. Pin patch version, không dùng "latest".
curl -sLO https://github.com/argoproj/argo-cd/releases/download/v3.4.2/argocd-linux-amd64
mv argocd-linux-amd64 /usr/local/bin/argocd
chmod +x /usr/local/bin/argocd
argocd version --client  # Verify
```

**Kiểm tra Docker Desktop (Windows):**

```powershell
# PowerShell
docker --version
docker context ls
# Ensure Docker Desktop running và WSL2 integration enabled
```

### 5.2 Step 1: Tạo kind cluster

```bash
# Tạo config để expose port cho ArgoCD Ingress
cat <<'EOF' > /tmp/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30080
        hostPort: 30080
        protocol: TCP
EOF

kind create cluster \
  --name argocd-day17 \
  --config /tmp/kind-config.yaml \
  --wait 5m

# Verify
kubectl cluster-info --context kind-argocd-day17
kubectl get nodes
```

**Expected output:**
```
NAME                          STATUS   ROLES           AGE
argocd-day17-control-plane   Ready    control-plane   2m
```

### 5.3 Step 2: Cài ArgoCD

**Cách 1: manifests install (recommended cho learning)**

```bash
kubectl create namespace argocd

# Install v3.4.2 (version pinned — không dùng HEAD)
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

# Wait for all pods ready (có thể mất 2-3 phút)
kubectl wait --for=condition=available \
  deployment/argocd-server \
  -n argocd \
  --timeout=300s

# Verify tất cả pod
kubectl get pods -n argocd -w &
# Wait for: 7/7 Running (bỏ & để không background nếu muốn watch)
```

**Expected pods (7 pods):**

```
NAME                                      READY   STATUS    RESTARTS   AGE
argocd-applicationset-controller-xxx     1/1     Running   0          2m
argocd-dex-server-xxx                     1/1     Running   0          2m
argocd-notifications-controller-xxx        1/1     Running   0          2m
argocd-redis-xxx                           1/1     Running   0          2m
argocd-repo-server-xxx                     1/1     Running   0          2m
argocd-server-xxx                          1/1     Running   0          2m
argocd-application-controller-0           1/1     Running   0          2m
```

**Cách 2: Helm install (recommended cho production)**

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# Verify chart/app mapping trước khi dùng production.
helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 9.5.14 \
  --set server.ingress.enabled=true \
  --set server.ingress.ingressClassName=nginx
```

### 5.4 Step 3: Login UI + CLI

**Lấy initial admin password:**

```bash
# Password nằm trong Kubernetes Secret
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Lưu lại password
ARGOCD_PWD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d)
echo "Password: $ARGOCD_PWD"
```

**Port-forward ArgoCD server (Terminal 1):**

```bash
# Chạy port-forward trong background
kubectl port-forward svc/argocd-server -n argocd 8080:443 \
  --address=0.0.0.0 &

# Sau đó mở trình duyệt: https://localhost:8080
# ⚠️ Bỏ qua warning certificate (self-signed)
# Login: admin / <password>
```

**CLI login:**

```bash
# Login (dùng --insecure vì self-signed cert)
argocd login localhost:8080 \
  --username admin \
  --password "$ARGOCD_PWD" \
  --insecure

# Verify
argocd version
argocd app list
argocd cluster list
```

### 5.5 Step 4: Deploy app đơn giản

Dùng public repository: `https://github.com/argoproj/argocd-example-apps`, path `guestbook`

#### Cách A: ArgoCD CLI (imperative)

```bash
# Tạo Application bằng CLI
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default \
  --sync-policy manual

# Check status
argocd app get guestbook

# Sync app (trigger reconciliation)
argocd app sync guestbook

# Watch status
argocd app get guestbook --watch
```

#### Cách B: Declarative YAML (recommended, production pattern)

```bash
# Tạo file application-guestbook.yaml
cat <<'EOF' > /tmp/application-guestbook.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
EOF

# Apply declarative
kubectl apply -f /tmp/application-guestbook.yaml

# Verify
argocd app get guestbook
```

### 5.6 Step 5: Quan sát reconciliation

```bash
# Xem Application status
kubectl get application -n argocd guestbook -o yaml | grep -A 20 status

# Detailed describe
argocd app get guestbook

# Xem sync history
argocd app history guestbook

# Xem diff giữa Git và cluster
argocd app diff guestbook

# Trong ArgoCD UI:
# 1. Mở https://localhost:8080
# 2. Vào Applications → guestbook
# 3. Quan sát:
#    - App tree: các resource được deploy
#    - Sync status: Synced ✅
#    - Health: Healthy ✅
#    - Revision: HEAD (commit SHA)
```

**Drift detection demonstration:**

```bash
# Simulate drift: sửa replicas trực tiếp trên cluster (không qua Git)
kubectl get deployment -n default
kubectl scale deployment guestbook-ui -n default --replicas=5

# ArgoCD phát hiện drift sau tối đa 3 phút
# Hoặc trigger ngay:
argocd app get guestbook  # Sẽ show OutOfSync 🔴

# Xem diff
argocd app diff guestbook

# Sync để restore
argocd app sync guestbook

# Verify replicas trở về 1
kubectl get deployment guestbook-ui -n default
```

### 5.7 Step 6: Inspect components

```bash
# Xem tất cả pod trong ArgoCD namespace
kubectl get pods -n argocd -o wide

# Watch application-controller logs (xem reconciliation loop)
kubectl logs -n argocd statefulset/argocd-application-controller -f
# Nhấn Ctrl+C để thoát

# Watch repo-server logs (xem git clone + render)
kubectl logs -n argocd deploy/argocd-repo-server -f --tail=50

# Watch argocd-server logs
kubectl logs -n argocd deploy/argocd-server -f --tail=50

# Xem ArgoCD configmap (ArgoCD cm = ArgoCD configuration)
kubectl get configmap -n argocd
kubectl get configmap argocd-cm -n argocd -o yaml

# Xem RBAC policy
kubectl get configmap argocd-rbac-cm -n argocd -o yaml
```

### 5.8 Step 7: Experiment với sync policies

```yaml
# Test 1: Manual sync (chỉ alert, không apply)
# Sửa Application:
kubectl patch application guestbook -n argocd \
  --type=merge \
  -p '{"spec":{"syncPolicy":{"automated":null}}}'

argocd app get guestbook  # Status: Synced (vì đã sync ở step trước)

# Tạo drift:
kubectl scale deployment guestbook-ui -n default --replicas=10
argocd app get guestbook  # Status: OutOfSync 🔴 ( ArgoCD không auto-fix)
argocd app diff guestbook
```

```yaml
# Test 2: Automated sync (apply Git changes, không selfHeal)
kubectl patch application guestbook -n argocd \
  --type=merge \
  -p '{
    "spec":{
      "syncPolicy":{
        "automated":{"prune":false,"selfHeal":false}
      }
    }
  }'

# Tạo drift:
kubectl scale deployment guestbook-ui -n default --replicas=10
argocd app get guestbook  # Still OutOfSync

# ArgoCD sẽ tự sync khi Git thay đổi (nhưng không revert cluster manual changes)
```

```yaml
# Test 3: Automated + selfHeal
kubectl patch application guestbook -n argocd \
  --type=merge \
  -p '{
    "spec":{
      "syncPolicy":{
        "automated":{"prune":true,"selfHeal":true}
      }
    }
  }'

# ArgoCD sẽ revert replicas về 1 trong vòng 3 phút (reconciliation)
# Hoặc trigger ngay:
argocd app sync guestbook
kubectl get deployment guestbook-ui -n default -o jsonpath='{.spec.replicas}'
# Should be: 1
```

### 5.9 Step 8: Truoubleshooting

**Lỗi 1: "context deadline exceeded" khi argocd app get**

```
Error: rpc error: code = Unavailable desc = error reading from server: 
connection reset
```
→ argocd-server pod chưa ready
```bash
kubectl rollout status deployment argocd-server -n argocd --timeout=120s
```

**Lỗi 2: "repository not found" khi sync**

```
Unable to connect to repository: authentication required
```
→ Private repository: cần config credential
```bash
# Thêm Git credential vào ArgoCD
argocd repo add https://github.com/org/private-repo.git \
  --username <username> \
  --password <token>

# Hoặc qua YAML:
kubectl apply -f repo-credential.yaml
```

**Lỗi 3: Pod stuck Pending**

```
kubectl get pods -n argocd
# NAME                    READY   STATUS
# argocd-server-xxx       0/1     Pending
```
→ Kind cluster không đủ resource
```bash
# Tăng kind cluster resource
# Xóa cluster cũ
kind delete cluster --name argocd-day17

# Tạo lại với more resources
cat <<'EOF' > /tmp/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 30080
        hostPort: 30080
        protocol: TCP
    # Thêm resource cho kind (nếu Docker Desktop có nhiều RAM)
EOF
```

**Lỗi 4: argocd CLI không connect**

```
FATA[0000] rpc error: code = Unavailable desc = 
connection error: desc = "transport: Error while dialing 
dial tcp 127.0.0.1:8080: connect: connection refused"
```
→ Port-forward chưa active hoặc sai port
```bash
# Kill existing port-forward
pkill -f "port-forward svc/argocd-server"

# Restart port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443 \
  --address=0.0.0.0

# Verify: mở browser http://localhost:8080 (không phải https)
# Hoặc verify port:
curl -k https://localhost:8080 2>&1 | head -5
```

**Lỗi 5: Deployment guestbook không tạo ra pods**

```bash
# Check all events trong namespace default
kubectl get events -n default --sort-by='.lastTimestamp'

# Check pod logs
kubectl describe deployment guestbook-ui -n default

# Check service
kubectl get svc -n default
```

### 5.10 Step 9: Cleanup

```bash
# Xóa Application
argocd app delete guestbook --cascade

# Verify namespace default đã clean
kubectl get all -n default

# Xóa ArgoCD (nếu không cần)
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.2/manifests/install.yaml

# Xóa kind cluster
kind delete cluster --name argocd-day17

# Verify cleanup
kind get clusters  # Should be empty
```

---

## 6. Kiểm tra hiểu bài

### Câu 1
Giải thích reconciliation loop của ArgoCD khác gì với control loop của Kubernetes controller. Điểm giống nhau và khác nhau cơ bản?

**Đáp án mẫu:**
- Giống: cả hai đều liên tục so sánh desired state vs actual state, tự động corrective action khi có drift
- Khác: Kubernetes controller watch etcd (actual cluster state), ArgoCD watch Git repo (desired state definition) + Kubernetes API (actual state). ArgoCD là controller cho application-level, dùng Application CRD (ArgoCD CRD) chứ không phải standard K8s resource CRD

### Câu 2
Khi nào bạn chọn Flux thay vì ArgoCD? Trình bày 3 scenarios cụ thể.

**Đáp án mẫu:**
1. Decentralized multi-cluster: mỗi edge cluster tự quản lý với Flux agent, không cần central control plane
2. Git-native team: team ưa thích GitOps Toolkit (Flux là collection of controllers), muốn compose multi-controller architecture
3. Built-in image automation: cần tự động update image tag trong Git khi registry có new image, không muốn cài thêm ArgoCD Image Updater

### Câu 3
Application trong ArgoCD UI hiển thị "Synced" + "Healthy" nhưng ứng dụng không chạy. Bạn sẽ debug như thế nào? Liệt kê 5 bước.

**Đáp án mẫu:**
1. ArgoCD chỉ check resource tồn tại + Kubernetes health check cơ bản. Kiểm tra: `kubectl get pods -n <namespace>` — pod có thể CrashLoopBackOff hoặc ImagePullBackOff
2. Xem Kubernetes events: `kubectl describe pod <pod> -n <namespace>` — có thể thiếu Secret, ConfigMap, PVC
3. Xem pod logs: `kubectl logs <pod> -n <namespace>` — ứng dụng có crash hay chỉ là configuration issue
4. Check resource dependency: ArgoCD không track cross-namespace dependency. Service A cần ConfigMap từ namespace khác?
5. Check ArgoCD sync options: `CreateNamespace=true` đã enable? Namespace đích đã tồn tại chưa?

### Câu 4
Tại sao pull-based GitOps an toàn hơn push-based từ góc độ security? Phân tích 3 điểm.

**Đáp án mẫu:**
1. CI/CD server không có cluster credential — nếu CI bị compromise, kẻ tấn công không thể kubectl vào cluster
2. Cluster chỉ cần outbound access đến Git (HTTPS port 443 outbound), không cần expose Kubernetes API port cho CI server
3. Git history cung cấp audit log hoàn chỉnh: ai commit gì, lúc nào. Mọi deployment action đều traceable qua Git

### Câu 5
Nhận định trade-off khi bật `automated: { prune: true, selfHeal: true }` ngay từ đầu cho tất cả Application.

**Đáp án mẫu:**
- **Pros**: Drift được auto-fix ngay, cluster luôn match Git, team có thể edit cluster thoải mái (ArgoCD tự revert)
- **Cons**: 
  1. Nếu Application YAML có bug (sai namespace, wrong resource), ArgoCD sẽ apply bug ngay → production incident
  2. `prune: true` xóa resource không còn trong Git — nếu unintentionally remove resource từ Git, ArgoCD xóa luôn production resource
  3. Dev đổi config trên cluster để test, ArgoCD revert ngay → dev frustrated
- **Recommendation**: Bắt đầu với manual → automated (prune:false, selfHeal:false) → sau 2 tuần stable: bật selfHeal → sau 1 tháng: bật prune

---

## 7. Tóm tắt cuối ngày

**4 nguyên tắc GitOps (OpenGitOps):**
1. Declarative — toàn bộ system mô tả declarative
2. Versioned & Immutable — desired state lưu trong Git
3. Pulled Automatically — agent trên cluster tự pull từ Git
4. Continuously Reconciled — agent so sánh actual vs desired liên tục

**5 components ArgoCD core:**
1. `argocd-server` — API, UI, Auth, RBAC
2. `argocd-repo-server` — clone Git, render Helm/Kustomize, stateless
3. `argocd-application-controller` — reconciliation engine, watch Application CRD, kubectl apply
4. `argocd-dex-server` — SSO/OIDC bridge (optional)
5. `argocd-redis` — cache, session storage

**ArgoCD vs Flux quick decision:**
- ArgoCD: UI + multi-team + centralized multi-cluster
- Flux: decentralized + Git-native + lightweight

**Output của ngày hôm nay:**
- kind cluster `argocd-day17` đã tạo và xóa
- ArgoCD v3.4.2 installed (hoặc Helm install cùng major supported)
- Login ArgoCD UI + CLI
- 1 Application `guestbook` deployed từ Git
- Quan sát được OutOfSync khi drift và Synced khi sync
- CLI familiar: `argocd app create/get/sync/diff/list`

**Chuẩn bị cho Day 18:**
- Application CRD fields chi tiết (spec.project, spec.source, spec.destination, spec.syncPolicy, spec.ignoreDifferences)
- AppProject — RBAC boundary cho Application
- Sync Policy variants (Manual / Automated / SelfHeal)
- Tiếp tục lab: deploy multi-app, AppProject, health check, retry

---

## 8. Tham khảo thêm

### Documentation chính thức
- ArgoCD Documentation: https://argo-cd.readthedocs.io/
- ArgoCD GitHub: https://github.com/argoproj/argo-cd
- ArgoCD Slack: `#argo-cd` trên CNCF Slack
- ArgoCD Blog: https://blog.argoproj.io/

### OpenGitOps
- OpenGitOps Principles: https://opengitops.dev/
- CNCF GitOps Working Group: https://github.com/cncf/wg-gitops

### So sánh ArgoCD vs Flux
- CNCF Blog "GitOps with ArgoCD and Flux": https://www.cncf.io/blog/2022/08/16/gitops-with-argo-cd-and-flux/
- ArgoCD vs Flux Decision Guide: https://akuity.io/blog/argo-cd-vs-flux/

### Video / Course
- ArgoCD Official Walkthrough: https://www.youtube.com/@ArgoCD
- CNCF GitOps Certification preparation

### Books / Articles
- Kelsey Hightower "GitOps: A Path to Leaner Operations": https://www.weave.works/blog/gitops-a-path-to-leaner-operations
- "GitOps and Kubernetes" — Deployment through Git by Billy Yuen, Alex Belding
- "Production Kubernetes" — O’Reilly (Chapter 14: GitOps)

### Architecture Reference
- ArgoCD Architecture Diagram: https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/
- ArgoCD High Availability: https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/
- ArgoCD Security Model: https://argo-cd.readthedocs.io/en/stable/security/

---

**Bài tiếp theo:** Day 18 — ArgoCD Application CRD, AppProject, Sync Policy chi tiết
