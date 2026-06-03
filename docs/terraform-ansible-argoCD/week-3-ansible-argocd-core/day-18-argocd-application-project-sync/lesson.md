# Day 18 - Application, AppProject, Sync Policy

**Thời lượng:** 2 giờ
**Module:** Week 3 - Ansible & ArgoCD Core
**Prerequisite:** Day 17 (kind cluster `argocd-day17` với ArgoCD installed)

---

## 1. Mục tiêu ngày học

Sau ngày học này, học viên sẽ:

- Hiểu đầy đủ Application CRD spec, mô tả được vai trò từng field và giá trị mặc định
- Thiết kế AppProject phù hợp cho multi-tenant: RBAC roles, sourceRepos whitelist, destinations whitelist, sync windows
- Phân biệt rõ ràng 4 sync policy combination: `manual` / `automated` / `automated+selfHeal` / `automated+selfHeal+prune`
- Phân biệt **sync status** (Synced/OutOfSync) và **health status** (Healthy/Degraded/Progressing/Missing/Suspended) — 2 trục độc lập
- Áp dụng drift correction strategy đúng theo môi trường (dev/staging/prod)
- Thực hành end-to-end: tạo AppProject → tạo Application → observe self-heal → observe prune → test RBAC

---

## 2. Bối cảnh thực tế

### Bài toán Day 17遗留

Sau Day 17, bạn đã deploy thành công app **guestbook** lên kind cluster bằng ArgoCD. Cluster chạy tốt, team rất hào hứng. Nhưng hiện tại:

```
1 Application duy nhất → guestbook (default project, manual sync)
```

Team bắt đầu mở rộng, sản phẩm gồm **8 microservices** × **3 môi trường** (dev/staging/prod) = **24 Application** cần quản lý.

### Rắc rối bắt đầu

**Chuyện 1:** Dev A lúc 2h sáng vô tình sync nhầm app `production-api` thay vì `staging-api`. Alert唤醒 cả team.

**Chuyện 2:** Engineer B dùng `kubectl edit deployment production-api` để debug. ArgoCD phát hiện OutOfSync, nhưng không làm gì (vì manual sync). Sáng hôm sau, ai đó sync → deployment bị revert → mất log debug.

**Chuyện 3:** Junior Dev C xóa file `deployment.yaml` khỏi Git branch `main`. ArgoCD detect resource biến mất → xóa luôn production Deployment? Hay chờ human confirm?

**Chuyện 4:** Một thành viên mới thử deploy từ repo lạ `https://evil.example.com/manifests.git` vào namespace `production`.

**Chuyện 5:** HPA tự scale Deployment lên 10 replica → ArgoCD báo OutOfSync → dev báo "ArgoCD bug".

### Tất cả những vấn đề này cần:

| Vấn đề | Giải pháp |
|---|---|
| Lộn env khi sync | AppProject: whitelist destination namespace |
| Dev kubectl bị revert không báo trước | automated + selfHeal (hoặc ignoreDifferences) |
| Xóa resource khỏi Git → có nên xóa cluster? | Prune policy |
| Deploy từ repo lạ | AppProject sourceRepos restriction |
| HPA replicas ≠ Git desired | ignoreDifferences |
| Dev đụng prod app | AppProject RBAC |

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Application CRD đầy đủ

Application là **unit of deployment** trong ArgoCD. Mỗi Application maps 1 Git source → 1 destination cluster/namespace.

#### 3.1.1 Minimal Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook              # must be unique within ArgoCD namespace
  namespace: argocd            # ALWAYS argocd namespace
spec:
  project: default             # references an AppProject
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc   # in-cluster API
    namespace: default
```

#### 3.1.2 Production-grade Application (annotated)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service-staging
  namespace: argocd
  # Finalizer cho phép cascade delete:
  # Khi xóa Application, ArgoCD sẽ xóa luôn resource trên cluster
  # NẾU KHÔNG CÓ: xóa Application chỉ xóa CR, resource trên cluster còn lại (orphaned)
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  labels:
    app: api-service
    env: staging
    team: platform
  annotations:
    # ArgoCD UI hiển thị thông tin thêm
    argocd.argoproj.io/description: "API service for staging environment"
    argocd.argoproj.io/sync-wave: "1"           # xem Day 24
spec:
  # ─────────────────────────────────────────────────────────
  # PROJECT: multi-tenancy boundary
  # ─────────────────────────────────────────────────────────
  project: team-platform

  # ─────────────────────────────────────────────────────────
  # SOURCE: Git location
  # ─────────────────────────────────────────────────────────
  source:
    repoURL: https://github.com/acme/apps-repo.git
    targetRevision: main              # branch | tag | commit SHA
    path: services/api-service/overlays/staging

    # --- Helm-specific fields (mutually exclusive với kustomize) ---
    # helm:
    #   releaseName: api-service                    # mặc định = metadata.name
    #   valueFiles:                                 # file values mặc định
    #     - values.yaml
    #     - values-prod.yaml
    #   values: |                                   # inline values (override)
    #     replicaCount: 3
    #     image:
    #       repository: acme/api-service
    #       tag: "1.2.3"
    #   parameters:                                 # override Helm parameters
    #     - name: replicaCount
    #       value: "3"
    #   ignoreMissingValueFiles: false

    # --- Kustomize-specific fields (mutually exclusive với helm) ---
    # kustomize:
    #   namePrefix: staging-        # prefix cho tất cả resource name
    #   nameSuffix: -v2
    #   commonLabels:                # label thêm vào tất cả resource
    #     version: v2
    #   images:                      # override image refs
    #     - name: nginx
    #       newTag: 1.21

    # --- Directory & File filters ---
    # directory:
    #   recurse: true                # đệ quy vào subdirectory
    #   jsonPointers:                # chọn lọc file theo JSON path
    #     - /kind

  # ─────────────────────────────────────────────────────────
  # DESTINATION: nơi resource sẽ được apply
  # ─────────────────────────────────────────────────────────
  destination:
    # server: Kubernetes API server URL
    # Giá trị https://kubernetes.default.svc = in-cluster (same cluster ArgoCD chạy)
    server: https://kubernetes.default.svc
    # Hoặc remote cluster: https://<external-k8s-api> (cần ClusterSecret hoặc in-cluster credential)
    # server: https://35.246.34.12

    # namespace: destination namespace trên cluster
    # ArgoCD sẽ tạo namespace nếu chưa có và syncPolicy.syncOptions có CreateNamespace=true
    namespace: staging

    # name: reference đến registered cluster (thay vì server URL)
    # Thường dùng khi có nhiều cluster
    # name: prod-us-east-1

  # ─────────────────────────────────────────────────────────
  # SYNC POLICY: cách ArgoCD đồng bộ
  # ─────────────────────────────────────────────────────────
  syncPolicy:
    # automated: ArgoCD tự sync khi Git thay đổi
    # Không có block này = manual sync (default)
    automated:
      prune: true          # xóa resource trên cluster khi file bị xóa khỏi Git
      selfHeal: true       # revert drift (cluster thay đổi khác Git)
      allowEmpty: false    # false = không sync nếu manifest rỗng

    # syncOptions: array của option string
    syncOptions:
      - CreateNamespace=true          # tạo namespace nếu chưa có
      - ServerSideApply=true           # dùng Server-Side Apply thay vì client-side
      - PrunePropagationPolicy=foreground  # cascade delete children trước
      - PruneLast=true                 # prune resource sau khi apply (an toàn hơn)
      - Validate=false                 # skip kubectl validation (cho CRD chưa install)
      - ApplyOutOfSyncOnly=true        # chỉ apply resource OutOfSync
      - RespectIgnoreDifferences=true # áp dụng ignoreDifferences khi compare

    # retry: số lần thử lại khi sync thất bại
    retry:
      limit: 5                         # số lần retry tối đa (-1 = infinite)
      backoff:
        duration: 5s                   # thời gian chờ ban đầu
        factor: 2                      # exponential factor (5s → 10s → 20s → ...)
        maxDuration: 3m                # max backoff = 3 phút
      # retryPolicy: "" | "on-error" | "always" | "on-failure"
      # - on-error: retry khi phase = Error
      # - on-failure: retry khi phase = Error hoặc Failed
      # - always: retry luôn (bao gồm Succeeded)

  # ─────────────────────────────────────────────────────────
  # IGNORE DIFFERENCES: bỏ qua drift ở field tự thay đổi
  # ─────────────────────────────────────────────────────────
  ignoreDifferences:
    # HPA tự thay đổi replicas → bỏ qua không báo OutOfSync
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
        - /metadata/annotations

    # Cert-manager tự mutate certificate/spec/issuer
    - group: cert-manager.io
      kind: Certificate
      jsonPointers:
        - /status

    # ArgoCD itself tạo annotations
    - group: '*'
      kind: '*'
      jsonPointers:
        - /metadata/annotations/argocd.argoproj.io/reconcile-at

  # ─────────────────────────────────────────────────────────
  # REVISION HISTORY: giữ bao nhiêu lịch sử sync
  # ─────────────────────────────────────────────────────────
  # Default: 10. Quá thấp → khó rollback. Quá cao → etcd bị phình.
  revisionHistoryLimit: 10

  # ─────────────────────────────────────────────────────────
  # SOURCE INTERNAL POLICIES
  # ─────────────────────────────────────────────────────────
  # sourcePosthook: (deprecated, dùng annotation thay thế)
  # informationOnlyBot: hiển thị notification không trigger action
```

#### Tổng hợp các trường metadata.annotation quan trọng

| Annotation | Giá trị | Ý nghĩa |
|---|---|---|
| `argocd.argoproj.io/sync-wave` | "1", "2", ... | Thứ tự sync (Day 24) |
| `argocd.argoproj.io/reconcile-at` | RFC3339 timestamp | Trigger immediate refresh |
| `argocd.argoproj.io/compare-options` | `IgnoreExtraneous` | Bỏ qua resource không có trong Git |
| `argocd.argoproj.io/refresh` | `normal` \| `hard` | Force refresh Application |
| `argocd.argoproj.io/hook` | `PreSync`\|`Sync`\|`PostSync`\|`Skip` | Hook lifecycle (Day 24) |
| `argocd.argoproj.io/hook-delete-policy` | `Foreground`\|`Background`\|`HookFailed` | Xóa hook như thế nào |

---

### 3.2 AppProject CRD

AppProject (viết tắt: AppProj) là **boundary** cho multi-tenancy. Nó wrap 1 nhóm Application có cùng chính sách.

#### 3.2.1 Đầy đủ AppProject spec

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-platform
  namespace: argocd          # luôn luôn trong namespace ArgoCD
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  description: "Platform team - manages shared infrastructure services"

  # ─────────────────────────────────────────────────────────
  # SOURCE REPOS WHITELIST: chỉ deploy từ repo này
  # ─────────────────────────────────────────────────────────
  # Security: chặn attacker deploy từ repo lạ
  sourceRepos:
    - https://github.com/acme/apps-repo.git
    - https://github.com/acme/platform-repo.git
    - 'git@github.com:acme/apps-repo.git'    # SSH style
    # Wildcard: dùng '*' cho phép mọi repo (KHÔNG NÊN trong prod)
    # - '*'

  # ─────────────────────────────────────────────────────────
  # DESTINATIONS WHITELIST: chỉ deploy vào cluster/namespace này
  # ─────────────────────────────────────────────────────────
  destinations:
    # Rule 1: staging namespace, same cluster
    - namespace: 'staging'
      server: https://kubernetes.default.svc
      # name: staging-us-east-1        # alt: reference cluster by name

    # Rule 2: production namespace, same cluster
    - namespace: 'production'
      server: https://kubernetes.default.svc

    # Rule 3: cho phép all namespace trong cluster nội bộ
    - namespace: '*'
      server: https://kubernetes.default.svc

    # ⚠️ NGHĨ KỸ trước khi allow '*' namespace:
    # → Cho phép deploy Pod privileged, hostPath, anything
    # → Rủi ro: dev có thể deploy vào namespace kube-system

  # ─────────────────────────────────────────────────────────
  # CLUSTER RESOURCE WHITELIST: cho phép tạo cluster-scoped resource
  # ─────────────────────────────────────────────────────────
  clusterResourceWhitelist:
    # Cho phép tạo Namespace, ClusterRole, ClusterRoleBinding
    - group: ''
      kind: Namespace
    - group: rbac.authorization.k8s.io
      kind: ClusterRole
    - group: rbac.authorization.k8s.io
      kind: ClusterRoleBinding
    # ⚠️ blacklist = namespaceResourceBlacklist (deny list)

  # ─────────────────────────────────────────────────────────
  # NAMESPACE RESOURCE BLACKLIST: cấm tạo resource trong namespace
  # ─────────────────────────────────────────────────────────
  namespaceResourceBlacklist:
    # Cấm ResourceQuota và LimitRange trong mọi namespace (tránh quota war)
    - group: ''
      kind: ResourceQuota
    - group: ''
      kind: LimitRange

  # ─────────────────────────────────────────────────────────
  # ROLES: RBAC per project
  # ─────────────────────────────────────────────────────────
  roles:
    # Role 1: viewer - chỉ đọc, không sync
    - name: viewer
      description: Read-only access to all apps in project
      policies:
        # Format: p, <subject>, <action>, <resource>, <effect>
        # p = policy, g = group
        - p, proj:team-platform:viewer, applications, get, team-platform/*, allow
        - p, proj:team-platform:viewer, applications, get, team-platform/*, allow
      groups:
        # LDAP/SSO group membership
        - acme:all-employees

    # Role 2: deployer - được sync app staging
    - name: deployer
      description: Deploy staging environments
      policies:
        # Dev chỉ được sync app có tên ending bằng '-staging'
        - p, proj:team-platform:deployer, applications, get, team-platform/*staging*, allow
        - p, proj:team-platform:deployer, applications, sync, team-platform/*staging*, allow
        # Không có quyền sync production
      groups:
        - acme:developers

    # Role 3: prod-deployer - sync production (restricted)
    - name: prod-deployer
      description: SRE leads - deploy to production
      policies:
        - p, proj:team-platform:prod-deployer, applications, sync, team-platform/*production*, allow
        - p, proj:team-platform:prod-deployer, applications, get, team-platform/*, allow
      groups:
        - acme:sre-leads

    # Role 4: admin - full control trên project
    - name: admin
      description: Project admin
      policies:
        # Policy default được ArgoCD tự sinh cho admin role:
        # - p, proj:team-platform:admin, *, *, team-platform/*, allow
      groups:
        - acme:platform-team

  # ─────────────────────────────────────────────────────────
  # SIGNATURE KEYS: verify Git commit signature (GPG/cosign)
  # ─────────────────────────────────────────────────────────
  signatureKeys:
    # Chỉ deploy commit được signed bằng key này
    # Dùng cho regulated environment (bank, healthcare)
    - keyID: ABCDEF1234567890    # GPG key ID
    # - keyID: cosign:mykey       # Cosign (v2.0+)

  # ─────────────────────────────────────────────────────────
  # SYNC WINDOWS: allow/deny sync theo schedule
  # ─────────────────────────────────────────────────────────
  syncWindows:
    # Window 1: Deny deploy production cuối tuần
    - kind: deny                      # deny | allow
      schedule: '0 0 * * 0'           # cron: 00:00 every Sunday
      duration: 48h                   # block 48 tiếng (Sat 00:00 → Mon 00:00)
      applications:
        - '*production*'             # match app name chứa 'production'
      # namespaces: []                # filter theo namespace (optional)
      # clusters: []                  # filter theo cluster (optional)
      manualSync: false               # true = cho phép manual sync trong window

    # Window 2: Deny deploy giờ nghỉ trưa
    - kind: deny
      schedule: '0 12 * * 1-5'        # 12:00 every weekday (Mon-Fri)
      duration: 1h
      applications:
        - '*prod*'
      manualSync: false

    # Window 3: Maintenance window - allow deploy
    - kind: allow
      schedule: '0 2 * * 3'          # Wed 02:00
      duration: 2h
      applications:
        - '*'
      manualSync: true               # cho phép manual trong window
```

#### Vai trò chính của AppProject

```
┌─────────────────────────────────────────────────────────────┐
│                     AppProject                              │
│  team-platform                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ sourceRepos: https://github.com/acme/apps-repo.git    │ │
│  │                                                        │ │
│  │ destinations:                                          │ │
│  │   - staging  (cluster: in-cluster)                    │ │
│  │   - production (cluster: in-cluster)                  │ │
│  │                                                        │ │
│  │ roles:                                                │ │
│  │   viewer ───────────── GET                            │ │
│  │   deployer ──────────── SYNC (staging only)           │ │
│  │   prod-deployer ─────── SYNC (prod only)             │ │
│  │   admin ─────────────── * (all actions)             │ │
│  │                                                        │ │
│  │ syncWindows: deny prod cuối tuần                     │ │
│  │ signatureKeys: GPG-ABCDEF... (signed commits)       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Managed Applications:                                      │
│    - api-service-staging      (policy: automated)          │
│    - api-service-production   (policy: manual)            │
│    - frontend-staging         (policy: automated)         │
│    - worker-staging           (policy: automated)         │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.3 Sync Policy chi tiết

#### 3.3.1 Bốn combination và use case

```
Sync Policy Matrix
══════════════════════════════════════════════════════════════════════

                    Git Change      Cluster Drift       Prune on Git Delete
                    ──────────      ─────────────       ───────────────────
Manual              No action       No action           No action
──────────────────────────────────────────────────────────────────────
Automated           Auto-sync       No action           No action
──────────────────────────────────────────────────────────────────────
Automated+SelfHeal Auto-sync       Auto-revert         No action
──────────────────────────────────────────────────────────────────────
Automated+All       Auto-sync       Auto-revert         Auto-delete
                    (prune=true, selfHeal=true)
══════════════════════════════════════════════════════════════════════
```

**Chi tiết từng mode:**

**Mode 1: Manual** (default, không khai báo `automated`)

```yaml
spec:
  syncPolicy:
    # KHÔNG có automated block
```
- ArgoCD chỉ detect OutOfSync và báo dashboard/CLI
- Human phải chạy `argocd app sync <app-name>`
- Dùng khi: production critical app, change advisory board, regulated env

**Mode 2: Automated only**

```yaml
spec:
  syncPolicy:
    automated:
      prune: false
      selfHeal: false
```
- ArgoCD auto-sync khi Git thay đổi (Polling ~3 phút hoặc Webhook instant)
- Cluster drift không được revert
- Dùng khi: pre-prod environment, developer có quyền thay đổi cluster để debug

**Mode 3: Automated + SelfHeal**

```yaml
spec:
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
```
- Git change → auto-sync
- Cluster drift → auto-revert sau ~30s (refresh interval)
- Dùng khi: dev environment, immutable infrastructure, developer không cần debug bằng kubectl

**Mode 4: Automated + SelfHeal + Prune** (đầy đủ)

```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - PruneLast=true
```
- Git change → auto-sync
- Cluster drift → auto-revert
- Xóa file khỏi Git → auto-delete resource khỏi cluster
- Dùng khi: mature GitOps team, CI/CD pipeline đã có đủ test, đã hiểu rõ hành vi prune

#### 3.3.2 Sync Options cheatsheet

```yaml
syncOptions:
  # --- NAMESPACE ---
  - CreateNamespace=true        # Tạo namespace nếu chưa có (default: false)
                                # ⚠️ false = app sẽ stuck nếu namespace không tồn tại

  # --- APPLY STRATEGY ---
  - ServerSideApply=true        # Dùng SSA thay client-side apply
                                # ✓ Tốt cho CRD, fields trùng lặp, owned resources
                                # ✗ Cần RBAC write trên resource
                                # ⚠️ first-time apply với existing resource có thể conflict

  - ApplyOutOfSyncOnly=true     # Chỉ apply resource OutOfSync (tối ưu perf cho app lớn)

  # --- VALIDATION ---
  - Validate=false              # Skip kubectl validation (dùng khi CRD chưa apply)
  - Prune=false                 # Disable prune hoàn toàn (override automated.prune)

  # --- PRUNE STRATEGY ---
  - PrunePropagationPolicy=foreground   # Cascade delete: xóa children trước (Pod → ReplicaSet)
  - PrunePropagationPolicy=background    # Xóa parent trước, GC xóa children sau
  - PrunePropagationPolicy=orphan        # Xóa parent, children thành orphaned
  - PruneLast=true                       # Apply trước, prune sau (an toàn, tránh downtime)

  # --- DIFF STRATEGY ---
  - RespectIgnoreDifferences=true  # Áp dụng ignoreDifferences khi sync (default: true)
  - CompareOptions=IgnoreExtraneous # Bỏ qua resource không có trong Git

  # --- RESOURCE HEALTH ---
  - FailOnSharedResource=false     # Không fail khi resource bị share giữa app
  - RespectLegacyResourcesField=true  # Legacy behavior (ArgoCD < 2.0)
```

#### 3.3.3 Retry Policy

```yaml
retry:
  limit: 5              # số lần retry. -1 = infinite. default: -1 (no retry)
  backoff:
    duration: 5s        # initial backoff
    factor: 2           # multiplier mỗi lần retry
    maxDuration: 3m     # ceiling
  retryPolicy: on-failure   # on-error | on-failure | always
```

Retry hay dùng cho: Job/Pod lỗi tạm thời, API rate-limit, webhook race condition.

---

### 3.4 Sync Status vs Health Status

**ĐÂY LÀ SỰ KHÁC NHAU RẤT QUAN TRỌNG — nhiều người nhầm lẫn.**

#### 3.4.1 Sync Status (trục Git ↔ Cluster)

Sync status = "File trên Git và resource trên cluster **có giống nhau không?**"

```
Git:    deployment.spec.replicas: 3
Cluster: deployment.spec.replicas: 3  → Synced ✓
Git:    deployment.spec.replicas: 3
Cluster: deployment.spec.replicas: 5  → OutOfSync ✗
```

| Status | Ý nghĩa | Trigger |
|---|---|---|
| `Synced` | Git desired state = Cluster actual state | Perfect match |
| `OutOfSync` | Có difference giữa Git và Cluster | Git changed, cluster changed, selective sync |
| `Unknown` | ArgoCD chưa xác định được | Initial sync, refresh pending, controller error |
| `Pruned` | Resource đã bị xóa khỏi cluster (không còn trong Git) | Prune thành công |

#### 3.4.2 Health Status (trục Runtime)

Health status = "Resource đang **chạy có tốt không?**"

| Status | Ý nghĩa | Thường thấy ở |
|---|---|---|
| `Healthy` | Resource đạt desired state, ready to serve | Deployment available, Pod running |
| `Progressing` | Resource đang thay đổi → Healthy | Rolling update, Init, Scaling |
| `Degraded` | Resource có vấn đề, không đạt desired | CrashLoopBackOff, OOMKill, probe fail |
| `Suspended` | Resource bị paused/khoá | CronJob suspended, Deployment paused |
| `Missing` | Resource không tồn tại trên cluster | Chưa apply hoặc bị xóa |
| `Unknown` | ArgoCD không biết health của resource | Custom resource chưa có health check |

#### 3.4.3 Combination Matrix (3×6)

```
┌─────────────┬──────────┬─────────────┬──────────┬────────────┬─────────┬─────────┐
│             │ Healthy  │ Progressing │ Degraded │ Suspended  │ Missing │ Unknown │
├─────────────┼──────────┼─────────────┼──────────┼────────────┼─────────┼─────────┤
│ Synced      │ ✓ App OK │  đang deploy│ runtime  │ rollout    │ chưa    │ health  │
│             │          │  (bình thường)│ fail    │ paused    │ apply   │ check   │
│             │          │             │ (image bad│ (kubectl  │ hoàn    │ lỗi    │
│             │          │             │  ...)    │  pause)   │ tấtnh  │         │
├─────────────┼──────────┼─────────────┼──────────┼────────────┼─────────┼─────────┤
│ OutOfSync   │ drift,   │ drift đang  │ drift +  │ drift +    │ bị xóa  │ chưa    │
│             │ app vẫn  │  sync       │ runtime  │ suspended  │ khỏi    │ refresh │
│             │ chạy OK  │  (bình     │ fail     │ resource  │ cluster │ hoặc lỗi│
│             │          │   thường)  │          │           │         │         │
├─────────────┼──────────┼─────────────┼──────────┼────────────┼─────────┼─────────┤
│ Unknown     │ lỗi      │ refresh    │ refresh  │ refresh   │ refresh │ controller│
│             │ health  │  pending   │  pending │  pending  │ pending  │ error   │
│             │ check   │            │          │           │         │         │
└─────────────┴──────────┴─────────────┴──────────┴────────────┴─────────┴─────────┘
```

**Debug strategy theo combination:**

| Combination | Interpretation | Action |
|---|---|---|
| Synced + Healthy | App perfect | Không làm gì |
| Synced + Degraded | App đúng Git nhưng runtime lỗi | Debug image, probe, resource |
| OutOfSync + Healthy | Drift, app vẫn chạy | Review diff, sync nếu cần |
| OutOfSync + Progressing | Drift đang được sync | Chờ, verify source |
| OutOfSync + Degraded | Drift + runtime fail | Fix code hoặc drift |
| OutOfSync + Missing | Resource bị xóa khỏi cluster | Sync lại hoặc restore |
| Synced + Missing | Apply thành công nhưng resource chưa tạo | Wait hoặc debug manifest |

---

### 3.5 Drift Correction Strategy

**Drift** = Cluster actual state khác Git desired state.

#### Strategy 1: Detect-only (ArgoCD as observability tool)

```yaml
spec:
  syncPolicy: {}  # No automated block = manual
```
- ArgoCD chỉ phát hiện và báo OutOfSync
- Human decide có sync hay không
- **Phù hợp:** Production critical, change advisory board, regulated env, bank

#### Strategy 2: Auto-correct (GitOps as source of truth)

```yaml
spec:
  syncPolicy:
    automated:
      selfHeal: true
      prune: false   # chưa bật prune
```
- Mọi drift đều bị revert
- **Phù hợp:** Dev environment, team đã quen GitOps, immutable infra

#### Strategy 3: Selective (Hybrid — Best practice cho staging)

```yaml
spec:
  syncPolicy:
    automated:
      selfHeal: true
      prune: false
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas   # bỏ qua HPA
```
- Tự động revert hầu hết drift
- Bỏ qua field tự thay đổi (HPA, cert-manager, etc.)
- **Phù hợp:** Staging, pre-prod, nơi engineer cần debug tạm thời

#### Môi trường nào dùng strategy nào?

| Env | Strategy | Automated | SelfHeal | Prune | IgnoreDiffs |
|---|---|---|---|---|---|
| Local dev | Auto-correct | ✓ | ✓ | ✗ | HPA replicas |
| Staging | Selective | ✓ | ✓ | ✗ | HPA, cert-manager |
| Production | Detect-only | ✗ | ✗ | ✗ | - |
| Bank/regulated | Manual + approval | ✗ | ✗ | ✗ | - |

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 Trade-off chi tiết từng sync policy

#### automated + prune + selfHeal: Súng hai lưỡi

```yaml
# ⚠️ CẢNH BÁO: Production incident tiềm tàng
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Tình huống nguy hiểm:**
```
Engineer đang refactor → commit file deployment.yaml với syntax error
→ ArgoCD auto-sync → apply error manifest
→ ArgoCD auto-prune → xóa old Deployment vì nó không còn trong Git
→ Cluster: 0 deployment, app down hoàn toàn
→ Rollback: cần revert Git commit + wait ArgoCD sync
→ Downtime: 3-5 phút (hoặc lâu hơn nếu không monitor)
```

**Best practice:**
1. Bật `automated` trước, chạy 1-2 sprint trước khi bật thêm `prune`
2. Luôn có ArgoCD notification (Slack/Teams/PagerDuty) để catch sớm
3. Dùng `PruneLast=true` để apply trước, prune sau
4. Test prune behavior trên staging trước

#### Self-heal vs Manual Debug

```
Problem: Engineer dùng kubectl edit để debug production issue

Without selfHeal:
  kubectl edit deploy api-service  →  Thay đổi tồn tại (cluster ≠ Git)
  ArgoCD: OutOfSync (nhưng không revert)
  Engineer debug xong → thành công

With selfHeal:
  kubectl edit deploy api-service  →  ArgoCD thấy drift
  ArgoCD: auto-revert sau 30s
  Engineer log debug mất tích
  Engineer frustrated ++
```

**Solution:**
```bash
# Cách 1: Tạm thời tắt selfHeal
kubectl patch application api-service --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":false}}}}}'

# Sau khi debug xong, bật lại
kubectl patch application api-service --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true}}}}}'

# Cách 2: Dùng sync window deny (nếu có)
argocd proj add-sync-window team-platform deny \
  --schedule="0 * * * *" --duration=1h --applications=api-service
```

#### AppProject Design: Too wide vs Too narrow

| Design | Pro | Con | Use case |
|---|---|---|---|
| `default` project (all apps) | Đơn giản | Không có isolation, security risk | Local dev/poc |
| 1 project per environment | Tách env rõ ràng | User bị giới hạn theo env | Small team |
| 1 project per team | Team tự quản, RBAC tự nhiên | YAML nhiều hơn | Medium team |
| 1 project per domain | Cleanest separation | Phức tạp hơn | Enterprise |
| 1 project per app | Maximum isolation | YAML explosion (24+ projects) | Bank/regulated |

**Recommended cho course này:**
- 1 project per team (platform / payment / data)
- Hoặc 1 project per environment cho đơn giản

### 4.2 Performance considerations

Application reconciliation time tỉ lệ thuận với:
- Số resource trong Application
- Số Application cùng reconcile
- Manifest size
- K8s API response time

**Optimizations:**
```yaml
# Cho app có nhiều resource
spec:
  syncPolicy:
    syncOptions:
      - ApplyOutOfSyncOnly=true  # Chỉ apply OutOfSync resource

# Cho app phức tạp (Helm chart lớn)
# Thay vì tăng application controller replica,
# Dùng ApplicationSet để batch reconcile (Day 22)
```

### 4.3 Security checklist

```
□ sourceRepos không phải '*' trong prod
□ destinations whitelist không rộng quá (không '*' namespace cho production)
□ clusterResourceWhitelist không có '*' group
□ Sync policy phù hợp với môi trường (prod không automated+prune)
□ RBAC role không có '*' permission
□ Sync windows cho prod environment
□ Signature verification cho regulated env
□ revisionHistoryLimit không quá cao (etcd)
□ Finalizer được set để cascade delete
□ annotations không chứa sensitive data (ArgoCD UI hiển thị plaintext)
```

### 4.4 Common pitfalls (Top 10)

| # | Pitfall | Symptom | Fix |
|---|---|---|---|
| 1 | Quên finalizer | Xóa Application không cascade resource | Thêm `resources-finalizer.argocd.argoproj.io` |
| 2 | ignoreDifferences sai JSONPointer | ArgoCD vẫn báo OutOfSync | Dùng `argocd app diff --dry-run` để verify |
| 3 | `sourceRepos: '*'` | Security: deploy từ repo lạ | Whitelist exact repo URL |
| 4 | `namespace: '*'` | Dev deploy vào kube-system | Whitelist exact namespace |
| 5 | Không set revisionHistoryLimit | etcd bị phình, memory leak | Set `revisionHistoryLimit: 5` hoặc `10` |
| 6 | `CreateNamespace` không set | App stuck với "Namespace not found" | Thêm `CreateNamespace=true` |
| 7 | automated+selfHeal + kubectl debug | Engineer log mất khi ArgoCD revert | Dùng kubectl patch tạm tắt selfHeal |
| 8 | automated+prune khi không hiểu | Production resource bị xóa nhầm | Test trên staging trước, dùng PruneLast |
| 9 | Sync wave + automated+selfHeal infinite loop | Pod restart liên tục | Day 24: tránh PreSync hook tự mutate |
| 10 | Webhook không configured | Sync delay 3 phút sau Git push | Setup webhook (không bắt buộc nhưng recommended) |

---

## 5. Hands-on Lab — 60 phút

**Chi phí:** $0 — hoàn toàn local kind cluster.
**Cluster:** `argocd-day17` (re-create nếu đã xóa)

### Pre-lab: Recreate kind cluster

```bash
# Nếu cluster đã bị xóa
kind delete cluster --name argocd-day17 2>/dev/null || true

kind create cluster --name argocd-day17 --wait 5m

# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Chờ ready
kubectl wait --namespace argocd \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=argocd-server \
  --timeout=120s

# Get password
PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo "Password: $PASSWORD"

# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443 &
```

### Step 1: Tạo Git repo cho lab

Tạo GitHub repo public `gitops-lab-day18` hoặc dùng local repo:

```bash
mkdir -p ~/gitops-lab-day18/apps/api-service
cd ~/gitops-lab-day18

# Initialize git repo
git init
git config user.email "student@acme.com"
git config user.name "Student"

# Tạo deployment manifest
cat > apps/api-service/deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app: api-service
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
        version: v1
    spec:
      containers:
        - name: api-service
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api-service
  labels:
    app: api-service
spec:
  type: ClusterIP
  selector:
    app: api-service
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-service-env
data:
  ENV: "staging"
  LOG_LEVEL: "info"
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-service
EOF

# Tạo kustomization.yaml
cat > apps/api-service/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
commonLabels:
  app.kubernetes.io/managed-by: argocd
  app.kubernetes.io/part-of: api-service
EOF

# Commit
git add .
git commit -m "Initial: api-service manifest"
git branch -M main
```

**Nếu dùng GitHub:**
```bash
git remote add origin https://github.com/<your-username>/gitops-lab-day18.git
git push -u origin main
```

**Nếu dùng local repo (không có GitHub):**
```bash
# Dùng file:// URL hoặc thư mục local
# ArgoCD hỗ trợ local path nếu configured
REPO_URL="file:///root/gitops-lab-day18"  # Adjust path
```

### Step 2: Tạo AppProject team-platform

```bash
cat > ~/appproject-team-platform.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-platform
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  description: "Platform team - api-service, worker-service, frontend"
  sourceRepos:
    - https://github.com/YOUR_USERNAME/gitops-lab-day18.git
    # Thay YOUR_USERNAME bằng username thật
    # Nếu dùng local: file:///root/gitops-lab-day18
  destinations:
    - namespace: 'staging'
      server: https://kubernetes.default.svc
    - namespace: 'production'
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace
  namespaceResourceBlacklist:
    - group: ''
      kind: ResourceQuota
  roles:
    - name: dev-readonly
      policies:
        - p, proj:team-platform:dev-readonly, applications, get, team-platform/*, allow
        - p, proj:team-platform:dev-readonly, applications, sync, team-platform/*staging*, allow
      groups:
        - acme:developers
    - name: prod-deployer
      policies:
        - p, proj:team-platform:prod-deployer, applications, sync, team-platform/*production*, allow
        - p, proj:team-platform:prod-deployer, applications, get, team-platform/*, allow
      groups:
        - acme:sre-leads
  syncWindows:
    - kind: deny
      schedule: '0 0 * * 0'
      duration: 48h
      applications:
        - '*production*'
EOF

kubectl apply -f ~/appproject-team-platform.yaml -n argocd
```

**Verify:**
```bash
argocd proj list
argocd proj get team-platform
```

Output mong đợi:
```
NAME           DESTINATIONS              SOURCEREPOS
team-platform  staging,production         https://github.com/... (1)
```

### Step 3: Tạo Application api-service (manual sync)

```bash
cat > ~/application-api-service.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: api-service
  namespace: argocd
  labels:
    app: api-service
    env: staging
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: team-platform
  source:
    repoURL: https://github.com/YOUR_USERNAME/gitops-lab-day18.git
    targetRevision: main
    path: apps/api-service
    kustomize:
      namePrefix: staging-
  destination:
    server: https://kubernetes.default.svc
    namespace: staging
  syncPolicy:
    automated:
      prune: false
      selfHeal: false
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
  revisionHistoryLimit: 10
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
EOF

# ⚠️ Thay YOUR_USERNAME trong file
sed -i 's/YOUR_USERNAME/your-actual-username/g' ~/application-api-service.yaml
# Hoặc edit trực tiếp file

kubectl apply -f ~/application-api-service.yaml -n argocd
```

**Verify Application:**
```bash
argocd app list
# OUTPUT:
# NAME                CLUSTER              NAMESPACE  PROJECT         STATUS  HEALTH
# team-platform/api-service  https://kubernetes.default.svc  staging  team-platform  OutOfSync  Missing
```

### Step 4: Observe Sync + Health Status

```bash
# Xem chi tiết trạng thái
argocd app get team-platform/api-service

# Xem resources status (JSON)
argocd app get team-platform/api-service -o json | jq '.status'

# Xem history sync
argocd app history team-platform/api-service

# Manual sync lần đầu
argocd app sync team-platform/api-service --force
```

**Sau sync, output:**
```
Status: Synced
Health: Healthy
```

### Step 5: Simulate drift — Cluster modification

```bash
# Scale deployment trên cluster (thay đổi khác Git)
kubectl scale deployment staging-api-service -n staging --replicas=5

# Verify ArgoCD phát hiện OutOfSync
argocd app get team-platform/api-service

# OUTPUT:
# Status: OutOfSync
# Health: Healthy    ← Pod vẫn chạy ổn, chỉ replicas khác

# Xem diff chi tiết
argocd app diff team-platform/api-service
# Expected diff:
#   spec.replicas: 2 → 5

# Sync để revert
argocd app sync team-platform/api-service

# Verify replicas quay về 2
kubectl get deployment -n staging -o jsonpath='{.items[0].spec.replicas}'
# Expected: 2
```

### Step 6: Bật automated + selfHeal

```bash
# Patch syncPolicy: thêm selfHeal
kubectl patch application api-service -n argocd \
  --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true,"prune":false,"allowEmpty":false}}}}'

# Verify
argocd app get team-platform/api-service | grep -E "Sync Policy|Auto-sync"
# OUTPUT: Automated: Enabled (Self-Heal: Enabled)

# Scale lại
kubectl scale deployment staging-api-service -n staging --replicas=10

# Watch ArgoCD tự revert
# ArgoCD sẽ revert sau khoảng 30s (refresh interval)
# Có thể watch logs:
kubectl logs -n argocd statefulset/argocd-application-controller \
  --since=30s | grep -i "api-service" | tail -20

# Verify sau 1 phút
kubectl get deployment staging-api-service -n staging \
  -o jsonpath='{.spec.replicas}'
# Expected: 2 (ArgoCD đã revert)
```

### Step 7: Simulate prune scenario

```bash
# Test 1: Prune=false (default)
# Xóa Service trên cluster bằng kubectl
kubectl delete service staging-api-service -n staging

# ArgoCD detect OutOfSync (vì Service biến mất)
argocd app get team-platform/api-service
# Sync Status: OutOfSync
# ArgoCD sẽ tạo lại Service khi sync (không xóa Deployment vì file vẫn còn trong Git)

argocd app sync team-platform/api-service
kubectl get service staging-api-service -n staging
# Expected: Service được tạo lại

# Test 2: Bật prune
# Thay đổi kustomization.yaml: bỏ service.yaml (hoặc xóa file deployment.yaml)
# Giả lập: commit xóa resource khỏi Git
# Sau đó observe ArgoCD prune resource khỏi cluster
```

### Step 8: Test ignoreDifferences (HPA simulation)

```bash
# Tạo HPA để ArgoCD không OutOfSync khi HPA scale replicas
cat <<'EOF' | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: staging-api-service-hpa
  namespace: staging
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: staging-api-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
EOF

# HPA scale deployment lên 5 replica
# ArgoCD vẫn Synced (nhờ ignoreDifferences)
argocd app get team-platform/api-service
# Status: Synced  (ignoreDifferences hoạt động)
```

### Step 9: AppProject RBAC demonstration

```bash
# Tạo ArgoCD account cho dev-user
# ArgoCD hỗ trợ local accounts hoặc SSO (Dex/OIDC)
argocd account list

# Tạo user (ArgoCD v2.4+)
argocd account create dev-user --password 'DevPass123!' 2>/dev/null || true

# Update password
argocd account update-password \
  --account dev-user \
  --current-password 'DevPass123!' \
  --new-password 'newdevpass'

# Verify dev-user không có quyền sync prod
# Login as dev-user:
argocd login localhost:8080 --username dev-user --password 'newdevpass' --insecure

argocd app list  # Được xem danh sách
argocd app sync team-platform/api-service  # Được sync staging
argocd app sync team-platform/*production*  # Bị deny (RBAC)
```

**Expected RBAC behavior:**
```
dev-user (role: deployer):
  ✓ get    team-platform/*staging*
  ✓ sync   team-platform/*staging*
  ✗ sync   team-platform/*production*   → permission denied

dev-user thử sync prod → error: "rpc error: code = PermissionDenied"
```

### Step 10: Cleanup

```bash
# Xóa Application (cascade xóa resource trên cluster)
argocd app delete team-platform/api-service --cascade

# Verify resource đã xóa
kubectl get all -n staging -l app.kubernetes.io/part-of=api-service
# Expected: No resources found

# Xóa AppProject
kubectl delete -f ~/appproject-team-platform.yaml -n argocd

# Verify
argocd proj list
# team-platform không còn trong danh sách
```

**Giữ lại cluster để Day 19 sử dụng** (Helm + Kustomize với ArgoCD).

### Troubleshooting lab

| Error | Cause | Fix |
|---|---|---|
| `ApplicationDestinationDenied` | AppProject destinations không có namespace | Thêm namespace vào AppProject destinations |
| `ApplicationSourceDenied` | AppProject sourceRepos không match repo URL | Thêm repo URL vào AppProject sourceRepos |
| `Namespace 'staging' not found` | syncOptions không có CreateNamespace | Thêm `CreateNamespace=true` |
| App OutOfSync mãi dùng không thay đổi | `managedFields` hoặc `creationTimestamp` | Thêm vào ignoreDifferences |
| Self-heal không kích hoạt | `automated.selfHeal` không phải `true` | Verify spec.syncPolicy.automated |
| Prune không xóa resource | Resource có `ownerReference` hoặc `Prune=false` annotation | Check annotation hoặc GC |

**Debug commands:**
```bash
# Force refresh Application
argocd app get team-platform/api-service --refresh

# Watch controller logs
kubectl logs -n argocd statefulset/argocd-application-controller -f

# Xem resource diff
argocd app diff team-platform/api-service --local ~/gitops-lab-day18/apps/api-service

# Check managed resources
argocd app resources team-platform/api-service
```

---

## 6. Kiểm tra hiểu bài

### Câu 1: Interpretation
Application có `status.sync.status: OutOfSync` và `status.health.status: Degraded`.
Điều này nghĩa là gì? Cách debug?

**Đáp án:**
- `OutOfSync`: Git desired state khác Cluster actual state (có drift)
- `Degraded`: Runtime lỗi (Pod không healthy, probe fail, replica < desired)
- **Có 2 vấn đề:** drift (cần review diff) VÀ runtime fail (cần fix image/probe/resource)
- **Debug:**
  1. `argocd app diff` để xem drift
  2. `kubectl describe` trên resource để xem lỗi runtime
  3. `kubectl logs` Pod để tìm crash reason
  4. Có thể drift gây ra degraded (VD: scale down replicas trong Git → cluster scale down → degraded)

### Câu 2: Production policy
Tại sao production app thường **không nên** bật `prune: true`?

**Đáp án:**
- Prune xóa resource trên cluster khi file bị xóa khỏi Git
- Trong production: engineer có thể vô tình commit xóa file → ArgoCD xóa resource → **downtime ngay lập tức**
- Git branch protection không ngăn được (vẫn force-push được)
- Recovery: cần revert Git commit + wait ArgoCD sync = downtime
- Best practice: production dùng `prune: false`, xóa resource = manual process với review

### Câu 3: Migration
Application `checkout-service` đang dùng `default` project. Team muốn migrate sang `team-payments` project để áp dụng RBAC riêng. Làm sao migrate mà không gây downtime?

**Đáp án:**
```bash
# 1. Verify team-payments project tồn tại và có đúng destinations/sourceRepos
argocd proj get team-payments

# 2. Patch Application: thay đổi project name
# ArgoCD sẽ verify Application resource thuộc destinations whitelist của project mới
kubectl patch application checkout-service -n argocd \
  --type merge \
  -p '{"spec":{"project":"team-payments"}}'

# 3. Verify
argocd app get checkout-service | grep Project
# Output: Project: team-payments

# 4. Verify app vẫn Synced + Healthy
argocd app get checkout-service

# Note: Không cần xóa và tạo lại → không downtime
```

### Câu 4: revisionHistoryLimit
Giải thích `revisionHistoryLimit` và rủi ro khi set quá thấp hoặc quá cao.

**Đáp án:**
- ArgoCD giữ history của N lần sync gần nhất trong Application status
- **Quá thấp (VD: 2):** Khó rollback, không có audit trail khi có sự cố
- **Quá cao (VD: 100):** etcd phình, Application object lớn, ArgoDB/ArgoCD controller chậm
- **Recommended:** 5-10 (đủ để rollback 1-2 release gần, không quá tốn resource)
- History dùng cho: `argocd app history` và rollback via `argocd app rollback`

### Câu 5: Security
AppProject với `sourceRepos: ['*']` có vấn đề gì về security?

**Đáp án:**
- Attacker có thể deploy manifest từ bất kỳ repo nào (Git URL không bị validate)
- Attacker tạo repo độc hại chứa Pod privileged, hostPath mount, secret extraction
- ArgoCD sẽ apply resource lên cluster mà không kiểm tra source
- **Fix:** Always whitelist exact repo URL:
  ```yaml
  sourceRepos:
    - https://github.com/acme/apps-repo.git
    - https://github.com/acme/platform-repo.git
  ```

---

## 7. Tóm tắt cuối ngày

### Những gì đã học

```
Day 18 Key Concepts
════════════════════════════════════════════════════════════

APPLICATION
  • Unit of deployment: 1 Git source → 1 destination
  • 8 critical spec blocks: project, source, destination,
    syncPolicy, ignoreDifferences, revisionHistoryLimit,
    finalizers, source[helm|kustomize|directory]

APPPROJECT
  • Multi-tenant boundary + RBAC + security policy
  • 5 security layers: sourceRepos, destinations,
    clusterResourceWhitelist, syncWindows, signatureKeys
  • RBAC roles: p,<subject>,<action>,<resource>,<effect>

SYNC POLICY
  • 4 combinations: manual / automated / +selfHeal / +selfHeal+prune
  • SyncOptions: CreateNamespace, ServerSideApply,
    PrunePropagationPolicy, ApplyOutOfSyncOnly, ...

STATUS (2 independent axes)
  • Sync: Synced / OutOfSync / Unknown / Pruned
  • Health: Healthy / Progressing / Degraded / Suspended / Missing / Unknown
  • Combination = complete picture

DRIFT CORRECTION
  • Detect-only (manual) → Staging (auto+selfHeal) → Prod (manual)
  • ignoreDifferences for HPA, cert-manager, ArgoCD annotations
```

### Output của ngày học

```
1. AppProject: team-platform
   - sourceRepos: whitelist
   - destinations: staging + production
   - roles: dev-readonly, prod-deployer
   - syncWindows: deny production cuối tuần

2. Application: team-platform/api-service
   - automated (manual ban đầu, rồi patch selfHeal)
   - ignoreDifferences: /spec/replicas
   - finalizers: resources-finalizer

3. Hands-on experience:
   ✓ Self-heal revert kubectl scale
   ✓ OutOfSync detection
   ✓ ignoreDifferences cho HPA
   ✓ RBAC: dev-user không sync prod
   ✓ Cascade delete với --cascade
```

### Chuẩn bị Day 19

Day 19: **Helm + Kustomize với ArgoCD**
- ArgoCD integrate với Helm chart
- ArgoCD integrate với Kustomize overlays
- Kustomize commonLabels + namePrefix
- ArgoCD Application source `helm` field vs `kustomize` field
- Multi-env: base + overlays (dev/staging/prod)

---

## 8. Tham khảo thêm

### ArgoCD Documentation
- [Application CRD](https://argo-cd.readthedocs.io/stable/operator-manual/application.yaml)
- [AppProject CRD](https://argo-cd.readthedocs.io/stable/operator-manual/declarative-setup/#appprojects)
- [Sync Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-policy/)
- [Sync Options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/)
- [Drift Detection](https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/)
- [Resource Health](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/)
- [Retry Policy](https://argo-cd.readthedocs.io/en/stable/user-guide/retrying/)
- [Ignore Differences](https://argo-cd.readthedocs.io/en/stable/user-guide/ignore-differences/)

### RBAC Reference
- [ArgoCD RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
- Policy syntax: `p, <subject>, <action>, <resource>, <effect>`
- Action: get, sync, update, delete, override, action/<name>
- Resource: applications, projects, clusters, repositories

### Tiếp theo
- **Day 19:** Helm + Kustomize rendering trong ArgoCD
- **Day 20:** GitOps repository structure
- **Day 22:** ApplicationSet for scale
- **Day 24:** Sync waves và Hooks
