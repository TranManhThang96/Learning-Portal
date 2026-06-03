# Day 18 - Reference Documentation

**Application CRD Field Reference | AppProject CRD Field Reference | Sync Policy Decision Matrix | Sync Options Cheatsheet | Status Combination Table | RBAC Cheatsheet | AppProject Template Library | ignoreDifferences Cookbook | Annotation Reference**

---

## 1. Application CRD Field Reference

### 1.1 Top-level fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `apiVersion` | string | Yes | — | `argoproj.io/v1alpha1` |
| `kind` | string | Yes | — | `Application` |
| `metadata.name` | string | Yes | — | Unique name trong ArgoCD namespace. Format: `<project>/<app>` khi dùng project scoping |
| `metadata.namespace` | string | Yes | — | Luôn `argocd` |
| `metadata.generateName` | string | No | — | Prefix cho generated name (dùng với ApplicationSet) |
| `metadata.labels` | map[string]string | No | — | Labels cho Application |
| `metadata.annotations` | map[string]string | No | — | Annotations (không chứa sensitive data) |
| `metadata.finalizers[]` | []string | No | — | `resources-finalizer.argocd.argoproj.io` = cascade delete |
| `metadata.deletionGracePeriodSeconds` | int | No | — | Grace period trước khi xóa |
| `metadata.ownerReferences[]` | []OwnerReference | No | — | Kubernetes owner reference (ArgoCD không recommend dùng) |

### 1.2 spec fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec.project` | string | Yes | — | AppProject name. Application chỉ được tạo trong 1 project. Thay đổi project = migrate |
| `spec.source` | Source | Yes | — | Git/Helm/Kustomize location. Xem bảng Source fields |
| `spec.destination` | Destination | Yes | — | Target cluster + namespace. Xem bảng Destination fields |
| `spec.syncPolicy` | SyncPolicy | No | — | Sync behavior. No block = manual sync |
| `spec.ignoreDifferences[]` | []ResourceIgnoreDifference | No | — | Bỏ qua diff ở specific fields. Xem Cookbook |
| `spec.revisionHistoryLimit` | int | No | `10` | Số history entry giữ lại. Recommended: 5-10 |
| `spec.info[]` | []Info | No | — | Hiển thị metadata trong ArgoCD UI |
| `spec.ignoreDifferences` | []ResourceIgnoreDifference | No | — | Field-level ignore. Xem 1.6 |

### 1.3 spec.source fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec.source.repoURL` | string | Yes | — | Git URL (https/ssh/file). Required |
| `spec.source.targetRevision` | string | No | `HEAD` | Branch, tag, commit SHA |
| `spec.source.path` | string | No* | — | Relative path trong repo. Required nếu không dùng `chart` |
| `spec.source.ref` | ResRef | No | — | Named reference (branch/tag override) |
| `spec.source.helm` | HelmSource | No* | — | Helm-specific. Mutually exclusive với kustomize/directory |
| `spec.source.kustomize` | KustomizeSource | No* | — | Kustomize-specific. Mutually exclusive |
| `spec.source.directory` | DirectorySource | No* | — | Plain manifest. Mutually exclusive |
| `spec.source.chart` | string | No* | — | Helm chart name (OCIRepo) |

### 1.4 spec.destination fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec.destination.server` | string | No* | — | Kubernetes API server URL. `https://kubernetes.default.svc` = in-cluster |
| `spec.destination.namespace` | string | Yes | — | Target namespace. Tạo nếu syncOptions.CreateNamespace=true |
| `spec.destination.name` | string | No* | — | Named cluster reference. Alt cho `server` |

> **Note:** Phải có `server` HOẶC `name`, không phải cả hai.

### 1.5 spec.syncPolicy fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec.syncPolicy.automated` | AutomatedSyncPolicy | No | — | No block = manual sync |
| `spec.syncPolicy.syncOptions[]` | []string | No | — | Array của sync option strings. Xem Section 3 |
| `spec.syncPolicy.retry` | RetryStrategy | No | — | Retry khi sync fail. No retry = fail permanently |

### 1.6 spec.syncPolicy.automated fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `automated.prune` | bool | No | `false` | Xóa resource khỏi cluster khi file bị xóa khỏi Git |
| `automated.selfHeal` | bool | No | `false` | Revert cluster drift về Git desired state |
| `automated.allowEmpty` | bool | No | `false` | Cho phép sync khi manifest rỗng |

### 1.7 spec.ignoreDifferences[] fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `ignoreDifferences[].group` | string | No | `*` | API group (VD: `apps`, `networking.k8s.io`) |
| `ignoreDifferences[].kind` | string | No | `*` | Kind (VD: `Deployment`, `Service`) |
| `ignoreDifferences[].name` | string | No | — | Specific resource name |
| `ignoreDifferences[].namespace` | string | No | — | Specific namespace |
| `ignoreDifferences[].jsonPointers[]` | []string | Yes* | — | JSON path cần bỏ qua. Required khi dùng group/kind |

### 1.8 RetryStrategy fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `retry.limit` | int | No | `-1` | Số lần retry. `-1` = infinite. `0` = no retry |
| `retry.backoff.duration` | string | No | `5s` | Initial backoff (goh duration string) |
| `retry.backoff.factor` | int | No | `2` | Exponential multiplier |
| `retry.backoff.maxDuration` | string | No | `5m` | Maximum backoff ceiling |
| `retry.retryPolicy` | string | No | `on-failure` | `on-error` \| `on-failure` \| `always` |

---

## 2. AppProject CRD Field Reference

### 2.1 Top-level fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `metadata.name` | string | Yes | — | Unique project name. 1-63 chars, lowercase, hyphen allowed |
| `metadata.namespace` | string | Yes | — | Luôn `argocd` |
| `metadata.finalizers[]` | []string | No | — | `resources-finalizer.argocd.argoproj.io` để cascade delete |
| `spec.description` | string | No | — | Human-readable mô tả |

### 2.2 spec fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `spec.sourceRepos[]` | []string | Yes | — | Whitelist Git repo URL. `['*']` = cho phép mọi repo (security risk) |
| `spec.destinations[]` | []ApplicationDestination | Yes | — | Whitelist cluster/namespace. Xem bảng bên dưới |
| `spec.clusterResourceWhitelist[]` | []GroupKind | No | — | Allow cluster-scoped resource. `['*']` = allow all |
| `spec.namespaceResourceBlacklist[]` | []GroupKind | No | — | Deny namespace-scoped resource |
| `spec.roles[]` | []ProjectRole | No | — | RBAC roles. Xem Section 2.3 |
| `spec.signatureKeys[]` | []SignatureKey | No | — | GPG/Cosign key để verify signed commits |
| `spec.syncWindows[]` | []SyncWindow | No | — | Allow/deny schedule cho sync |

### 2.3 Destination field

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `destinations[].server` | string | No | — | Kubernetes API server URL |
| `destinations[].namespace` | string | No | — | Namespace name. `*` = mọi namespace |
| `destinations[].name` | string | No | — | Named cluster reference |
| `destinations[].env` | string | No | — | Environment filter (ArgoCD v2.5+) |

> Phải có `server` HOẶC `name` HOẶC `env`.

### 2.4 GroupKind (clusterResourceWhitelist / namespaceResourceBlacklist)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `groupKind.group` | string | No | `*` | API group (VD: `apps`, `networking.k8s.io`, `''` = core) |
| `groupKind.kind` | string | No | `*` | Resource kind (VD: `Deployment`, `Pod`, `Namespace`) |

### 2.5 ProjectRole fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `roles[].name` | string | Yes | — | Unique role name trong project |
| `roles[].description` | string | No | — | Mô tả role |
| `roles[].policies[]` | []string | Yes | — | RBAC policy strings. Format: `p,<sub>,<act>,<res>,<eff>` |
| `roles[].groups[]` | []string | No | — | External group claim (LDAP/SSO) |
| `roles[].jwttokens[]` | []JWTToken | No | — | Service account JWT tokens |

### 2.6 SyncWindow fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `syncWindows[].kind` | string | Yes | — | `allow` hoặc `deny` |
| `syncWindows[].schedule` | string | Yes | — | Cron expression (5-field) |
| `syncWindows[].duration` | string | Yes | — | Duration string (VD: `4h`, `30m`, `2h30m`) |
| `syncWindows[].applications[]` | []string | No | `['*']` | App name patterns (`*`, `*production*`) |
| `syncWindows[].namespaces[]` | []string | No | — | Namespace filter |
| `syncWindows[].clusters[]` | []string | No | — | Cluster filter |
| `syncWindows[].manualSync` | bool | No | `true` | Cho phép manual sync trong deny window |

### 2.7 SignatureKey fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `signatureKeys[].keyID` | string | Yes | — | GPG key ID hoặc `cosign:<key-name>` |

---

## 3. Sync Policy Decision Matrix

Chọn sync policy theo môi trường và team maturity:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYNC POLICY DECISION TREE                       │
│                                                                         │
│  Is this a regulated/production environment?                            │
│    YES → Does team require manual approval for every change?           │
│      YES → ① Manual Only                                              │
│      NO  → ② Automated (no prune, no selfHeal)                        │
│    NO  → Is this a dev/exploration environment?                       │
│      YES → ③ Automated + selfHeal                                     │
│      NO  → Does team have mature CI/CD with tests before commit?      │
│        YES → ④ Automated + selfHeal + prune                           │
│        NO  → ② Automated (no prune, no selfHeal)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Decision matrix theo môi trường

| Env | Recommended Policy | SelfHeal | Prune | Manual Sync Allow | Reason |
|---|---|---|---|---|---|
| **Local/Dev** | `automated` + selfHeal | ✓ | ✗ | ✗ | Fast iteration, engineer tự quản |
| **Staging/QA** | `automated` + selfHeal | ✓ | ✗ | ✓ | Catch drift, cho phép manual override |
| **Production** | Manual | ✗ | ✗ | ✓ | Change control, rollback ready |
| **Bank/Regulated** | Manual + approval + signature | ✗ | ✗ | ✓ (with ticket) | Audit, compliance |
| **Pre-prod (demo)** | `automated` (no selfHeal/prune) | ✗ | ✗ | ✓ | Observation, no auto-destructive action |

### Decision matrix theo team size

| Team Size | AppProject Pattern | Sync Policy | RBAC |
|---|---|---|---|
| Solo/Pair | `default` project | Manual hoặc automated | Không cần RBAC phức tạp |
| 2-5 dev | 1 project per env | Dev: automated+selfHeal, Prod: manual | viewer + deployer |
| 5-20 devs, multiple teams | 1 project per team | Dev: auto+selfHeal, Staging: auto, Prod: manual | viewer + deployer + prod-deployer |
| 20+ devs, regulated | 1 project per domain | Dev: auto, Prod: manual+approval+signature | Fine-grained per app |

---

## 4. Sync Options Cheatsheet (15+ options)

### 4.1 Namespace & Creation

```yaml
syncOptions:
  - CreateNamespace=true          # Tạo namespace trước khi apply resource
```

### 4.2 Apply Strategy

```yaml
syncOptions:
  # SSR (Server-Side Apply) — RECOMMENDED cho production
  - ServerSideApply=true

  # Chỉ apply OutOfSync resource — tốt cho app lớn
  - ApplyOutOfSyncOnly=true
```

### 4.3 Prune Controls

```yaml
syncOptions:
  # Propagation policy: foreground = children trước, background = parent trước
  - PrunePropagationPolicy=foreground
  - PrunePropagationPolicy=background
  - PrunePropagationPolicy=orphan

  # Apply trước, prune sau — AN TOÀN NHẤT
  - PruneLast=true

  # Vô hiệu hóa prune hoàn toàn (override automated.prune)
  - Prune=false
```

### 4.4 Validation

```yaml
syncOptions:
  # Bỏ qua kubectl validation (khi CRD chưa installed)
  - Validate=false
```

### 4.5 Diff Strategy

```yaml
syncOptions:
  # Áp dụng ignoreDifferences khi sync (default: true)
  - RespectIgnoreDifferences=true

  # Bỏ qua resource không có trong Git (orphan resources)
  - CompareOptions=IgnoreExtraneous
```

### 4.6 Other

```yaml
syncOptions:
  # Không fail khi resource bị share giữa nhiều Application
  - FailOnSharedResource=false

  # Legacy behavior
  - RespectLegacyResourcesField=true
```

---

## 5. Sync Status × Health Status Combination Table

### 5.1 Complete Matrix

| | **Healthy** | **Progressing** | **Degraded** | **Suspended** | **Missing** | **Unknown** |
|---|---|---|---|---|---|---|
| **Synced** | App OK | Rolling update/backup đang chạy | Runtime fail dù desired đúng | Rollout paused | Chưa tạo resource | Health check lỗi |
| **OutOfSync** | Drift, app vẫn chạy | Drift đang được sync | Drift + runtime fail | Drift + resource suspended | Resource bị xóa khỏi cluster | Refresh pending |
| **Unknown** | — | — | — | — | — | Controller error |

### 5.2 Action Guide

| Combination | Priority | Recommended Action |
|---|---|---|
| Synced + Healthy | — | Không cần làm gì |
| OutOfSync + Healthy | Medium | Review diff, sync nếu drift mong muốn |
| Synced + Degraded | High | Debug runtime (image, probe, resource) |
| OutOfSync + Degraded | Critical | Drift + runtime fail: fix both |
| OutOfSync + Missing | High | Sync lại hoặc restore resource |
| Synced + Missing | Medium | Chờ resource tạo (delay) hoặc debug manifest |
| OutOfSync + Progressing | Low | Đang tự fix, watch and confirm |
| Synced + Suspended | Low | Kiểm tra rollout/pause reason |
| Any + Unknown | Medium | Check ArgoCD controller logs |

---

## 6. RBAC Policy Syntax Cheatsheet

### 6.1 Policy format

```
p,<subject>,<action>,<resource>,<effect>
```

| Component | Options | Description |
|---|---|---|
| `p` | `p` (policy) | Fixed value |
| `<subject>` | `proj:<project>:<role>` | Project-scoped subject |
| `<action>` | `get` `create` `update` `delete` `sync` `override` `action/<name>` | What to do |
| `<resource>` | `applications` `projects` `clusters` `repositories` `*` | Resource type |
| `<effect>` | `allow` `deny` | Permission |

### 6.2 Built-in roles

| Role | Policies |
|---|---|
| `role:readonly` | `*, get, *, allow` |
| `role:agent` | `applications, sync, *, allow` |
| `role:admin` | `*, *, *, allow` |

### 6.3 Group-based policy

```
g,<group-claim>,<effect>
```

Example:
```
# LDAP group: acme:sre-leads
g,acme:sre-leads,allow
```

### 6.4 Common policies

```yaml
# Viewer: chỉ đọc
p, proj:team-platform:viewer, applications, get, team-platform/*, allow

# Deployer: đọc + sync staging
p, proj:team-platform:deployer, applications, get, team-platform/*staging*, allow
p, proj:team-platform:deployer, applications, sync, team-platform/*staging*, allow

# Prod deployer: chỉ sync prod
p, proj:team-platform:prod-deployer, applications, sync, team-platform/*production*, allow
p, proj:team-platform:prod-deployer, applications, get, team-platform/*, allow

# Admin: full control
p, proj:team-platform:admin, applications, *, team-platform/*, allow
p, proj:team-platform:admin, projects, *, team-platform, allow
```

### 6.5 ArgoCD CLI RBAC test

```bash
# Test RBAC without login
argocd account can-i get applications '*'
argocd account can-i sync applications 'team-platform/*production*' --role prod-deployer

# Test specific action
argocd account can-i sync applications 'team-platform/api-service' --role deployer
# → yes (staging) | no (prod)

# Check current user
argocd account current-user
```

---

## 7. AppProject Template Library

### Template 1: 1-project-per-env (DevOps Team đơn giản)

Phù hợp: small team, 1-10 app, muốn tách dev/staging/prod đơn giản.

```yaml
# AppProject: env-staging
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: env-staging
  namespace: argocd
spec:
  description: "Staging environment - auto-deploy on Git change"
  sourceRepos:
    - https://github.com/acme/gitops-repo.git
  destinations:
    - namespace: 'staging'
      server: https://kubernetes.default.svc
  roles:
    - name: deployer
      policies:
        - p, proj:env-staging:deployer, applications, get, env-staging/*, allow
        - p, proj:env-staging:deployer, applications, sync, env-staging/*, allow
      groups:
        - acme:developers
    - name: admin
      policies:
        - p, proj:env-staging:admin, *, *, env-staging/*, allow
      groups:
        - acme:sre-leads
---
# AppProject: env-production
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: env-production
  namespace: argocd
spec:
  description: "Production environment - manual sync only"
  sourceRepos:
    - https://github.com/acme/gitops-repo.git
  destinations:
    - namespace: 'production'
      server: https://kubernetes.default.svc
  syncWindows:
    - kind: deny
      schedule: '0 0 * * 0'        # Block Sunday 00:00
      duration: 48h
      applications:
        - '*'
  roles:
    - name: deployer
      policies:
        - p, proj:env-production:deployer, applications, sync, env-production/*, allow
        - p, proj:env-production:deployer, applications, get, env-production/*, allow
      groups:
        - acme:sre-leads
```

**Ưu điểm:** Đơn giản, dễ hiểu, tách biệt rõ env.
**Nhược điểm:** Nếu có 20 app → 20 Application × 3 env = 60 objects, nhưng vẫn quản lý được.

---

### Template 2: 1-project-per-team (Multi-team, Scalable)

Phù hợp: 3+ teams, mỗi team tự quản app của mình.

```yaml
# AppProject: team-platform
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-platform
  namespace: argocd
spec:
  description: "Platform team - manages shared infra services"
  sourceRepos:
    - https://github.com/acme/platform-repo.git
    - https://github.com/acme/gitops-shared.git
  destinations:
    - namespace: 'platform-dev'
      server: https://kubernetes.default.svc
    - namespace: 'platform-staging'
      server: https://kubernetes.default.svc
    - namespace: 'platform-production'
      server: https://kubernetes.default.svc
  roles:
    - name: developer
      policies:
        - p, proj:team-platform:developer, applications, get, team-platform/*dev*, allow
        - p, proj:team-platform:developer, applications, sync, team-platform/*dev*, allow
        - p, proj:team-platform:developer, applications, get, team-platform/*staging*, allow
      groups:
        - acme:platform-devs
    - name: release-engineer
      policies:
        - p, proj:team-platform:release-engineer, applications, sync, team-platform/*, allow
        - p, proj:team-platform:release-engineer, applications, get, team-platform/*, allow
      groups:
        - acme:sre-leads
    - name: admin
      policies:
        - p, proj:team-platform:admin, *, *, team-platform/*, allow
      groups:
        - acme:platform-team-admins
---
# AppProject: team-payments
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-payments
  namespace: argocd
spec:
  description: "Payments team - billing, checkout, invoices"
  sourceRepos:
    - https://github.com/acme/payments-repo.git
  destinations:
    - namespace: 'payments-*'
      server: https://kubernetes.default.svc
  # Blacklist: không cho tạo ResourceQuota (ngăn quota war giữa team)
  namespaceResourceBlacklist:
    - group: ''
      kind: ResourceQuota
  roles:
    - name: developer
      policies:
        - p, proj:team-payments:developer, applications, get, team-payments/*, allow
        - p, proj:team-payments:developer, applications, sync, team-payments/*staging*, allow
      groups:
        - acme:payments-devs
    - name: admin
      policies:
        - p, proj:team-payments:admin, *, *, team-payments/*, allow
      groups:
        - acme:payments-team-leads
---
# AppProject: team-data
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-data
  namespace: argocd
spec:
  description: "Data team - ML pipelines, analytics, data warehouse"
  sourceRepos:
    - https://github.com/acme/data-repo.git
  destinations:
    - namespace: 'data-*'
      server: https://kubernetes.default.svc
    - namespace: 'ml-*'
      server: https://kubernetes.default.svc
  roles:
    - name: data-engineer
      policies:
        - p, proj:team-data:data-engineer, applications, get, team-data/*, allow
        - p, proj:team-data:data-engineer, applications, sync, team-data/*, allow
      groups:
        - acme:data-team
    - name: admin
      policies:
        - p, proj:team-data:admin, *, *, team-data/*, allow
      groups:
        - acme:data-team-leads
```

**Ưu điểm:** Team tự quản, clear ownership, security boundary.
**Nhược điểm:** SRE lead cần access nhiều project → phải thêm vào nhiều group.

---

### Template 3: Bank/Regulated Environment (Signed Commits + Sync Windows + Strict RBAC)

Phù hợp: bank, healthcare, fintech, regulated industry.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: prod-critical
  namespace: argocd
spec:
  description: "Production critical systems - maximum security"
  sourceRepos:
    # Chỉ dùng 1 repo đã được security review
    - https://github.com/acme/prod-gitops.git
  destinations:
    - namespace: 'prod-core'
      server: https://kubernetes.default.svc
    - namespace: 'prod-payments'
      server: https://kubernetes.default.svc
  # Require signed commits (GPG key của DevOps lead)
  signatureKeys:
    - keyID: ABCDEF1234567890
  # Whitelist rất hẹp: không cho tạo cluster-admin, pod privileged
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace
    - group: rbac.authorization.k8s.io
      kind: Role
    - group: rbac.authorization.k8s.io
      kind: RoleBinding
    - group: networking.k8s.io
      kind: NetworkPolicy
  # Blacklist dangerous resources
  namespaceResourceBlacklist:
    - group: ''
      kind: Pod
    - group: ''
      kind: ResourceQuota
    - group: ''
      kind: LimitRange
    - group: policy
      kind: PodDisruptionBudget
  # Strict sync windows
  syncWindows:
    # Deny tất cả deploy cuối tuần
    - kind: deny
      schedule: '0 18 * * 5'      # Friday 18:00
      duration: 60h                 # Đến Monday 06:00
      applications:
        - '*'
    # Deny deploy giờ peak (12h-13h và 18h-09h)
    - kind: deny
      schedule: '0 12 * * 1-5'
      duration: 21h
      applications:
        - '*'
    # Maintenance window: cho phép deploy Wed 02:00-04:00
    - kind: allow
      schedule: '0 2 * * 3'
      duration: 2h
      applications:
        - '*'
  roles:
    # Developer: chỉ view, không sync
    - name: readonly
      policies:
        - p, proj:prod-critical:readonly, applications, get, prod-critical/*, allow
      groups:
        - acme:all-developers
    # Change advisory board: view + manual sync
    - name: change-manager
      policies:
        - p, proj:prod-critical:change-manager, applications, get, prod-critical/*, allow
        - p, proj:prod-critical:change-manager, applications, sync, prod-critical/*, allow
        - p, proj:prod-critical:change-manager, applications, rollback, prod-critical/*, allow
      groups:
        - acme:change-advisory-board
    # DevOps lead: full control
    - name: admin
      policies:
        - p, proj:prod-critical:admin, *, *, prod-critical/*, allow
      groups:
        - acme:devops-leads
```

---

## 8. ignoreDifferences Cookbook

### Pattern 1: HPA (HorizontalPodAutoscaler)

```yaml
ignoreDifferences:
  # HPA tự scale replicas → bỏ qua /spec/replicas
  - group: autoscaling
    kind: HorizontalPodAutoscaler
    jsonPointers:
      - /status
      - /metadata/annotations
```

### Pattern 2: HPA + Deployment replicas (HPA quản lý)

```yaml
ignoreDifferences:
  # Khi HPA quản lý replicas → ArgoCD bỏ qua
  - group: apps
    kind: Deployment
    jsonPointers:
      - /spec/replicas

  # Cert-manager tự thay đổi certificate status
  - group: cert-manager.io
    kind: Certificate
    jsonPointers:
      - /status
```

### Pattern 3: ArgoCD annotations tự thêm

```yaml
ignoreDifferences:
  # ArgoCD tự thêm annotation reconcile-at
  - group: '*'
    kind: '*'
    jsonPointers:
      - /metadata/annotations/argocd\.argoproj\.io/reconcile-at
```

### Pattern 4: Deployment managedFields (kubectl apply artifact)

```yaml
ignoreDifferences:
  # managedFields do kubectl apply tạo ra, không có trong Git
  - group: '*'
    kind: '*'
    jsonPointers:
      - /metadata/managedFields
```

### Pattern 5: Secret (external secrets, cert-manager)

```yaml
ignoreDifferences:
  # Secret được external-secrets operator quản lý
  - group: ''
    kind: Secret
    jsonPointers:
      - /data
      - /metadata/annotations

  # Certificate: cert-manager tự renewal
  - group: cert-manager.io
    kind: Certificate
    jsonPointers:
      - /status
      - /metadata/annotations
```

### Pattern 6: Pod template hash (Kustomize generates unique name)

```yaml
ignoreDifferences:
  # Kustomize hash suffix thay đổi mỗi khi spec thay đổi
  # nhưng không muốn báo OutOfSync
  - group: apps
    kind: Deployment
    jsonPointers:
      - /metadata/labels/app\.kubernetes\.io/hash
```

### Debug ignoreDifferences

```bash
# Thử nghiệm ignoreDifferences trước khi apply
argocd app diff team-platform/api-service --local ./path/to/manifest

# Dry-run: xem diff sau khi apply
argocd app diff team-platform/api-service \
  --local ./path/to/manifest \
  --ignore-differences '{"jsonPointers":["/spec/replicas"]}'

# Kiểm tra resource đang có managedFields
kubectl get deployment api-service -n staging -o jsonpath='{.metadata.managedFields}' | jq .
```

---

## 9. Annotation Reference

### 9.1 Application annotations

| Annotation | Value | Description |
|---|---|---|
| `argocd.argoproj.io/sync-wave` | string | Sync order (Day 24) |
| `argocd.argoproj.io/reconcile-at` | RFC3339 | Trigger immediate reconciliation |
| `argocd.argoproj.io/compare-options` | string | Additional compare options |
| `argocd.argoproj.io/refresh` | `normal` \| `hard` | Force refresh Application status |
| `argocd.argoproj.io/hook` | `PreSync`\|`Sync`\|`PostSync`\|`Skip` | Hook lifecycle (Day 24) |
| `argocd.argoproj.io/hook-delete-policy` | `Foreground`\|`Background`\|`HookFailed` | Khi nào xóa hook Pod |

### 9.2 Resource annotations (trong manifest)

| Annotation | Value | Description |
|---|---|---|
| `argocd.argoproj.io/compare-options` | `IgnoreExtraneous` | Bỏ qua resource không có trong Git |
| `argocd.argoproj.io/sync-options` | `Prune=false` | Disable prune cho resource cụ thể |
| `argocd.argoproj.io/daemon` | `""` | Cho phép resource tồn tại ngoài Git (sidecar, etc.) |

### 9.3 Sync hook annotations

```yaml
# Trong manifest: khai báo hook
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync    # Sync | PostSync | Sync | Skip
    argocd.argoproj.io/hook-delete-policy: HookFailed   # Foreground | Background | HookFailed
```

---

## 10. Quick Reference Commands

```bash
# Application CRUD
argocd app list
argocd app get <app>
argocd app create <app> -f app.yaml
argocd app delete <app> --cascade
argocd app sync <app>
argocd app sync <app> --force
argocd app sync <app> --prune
argocd app rollback <app> <revision>

# Refresh & Diff
argocd app get <app> --refresh
argocd app diff <app>
argocd app diff <app> --local ./path

# History
argocd app history <app>
argocd app resources <app>

# Project CRUD
argocd proj list
argocd proj get <proj>
argocd proj create <proj> -f proj.yaml
argocd proj delete <proj>
argocd proj add-source <proj> https://github.com/repo.git
argocd proj add-destination <proj> https://kubernetes.default.svc staging

# Sync windows
argocd proj add-sync-window <proj> deny \
  --schedule="0 0 * * 0" \
  --duration=48h \
  --applications='*prod*'

# RBAC
argocd account can-i <action> <resource>
argocd account current-user
argocd account list

# Patch (kubectl)
kubectl patch application <app> -n argocd --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true}}}}'

kubectl patch application <app> -n argocd --type merge \
  -p '{"spec":{"project":"new-project"}}}'
```
