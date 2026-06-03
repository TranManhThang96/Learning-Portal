# Day 31: GitOps with ArgoCD & Flux

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được 4 nguyên tắc cốt lõi của GitOps** và phân biệt GitOps với CI/CD truyền thống (push vs pull deployment).
2. **Mô tả được kiến trúc ArgoCD** (API Server, Repo Server, Application Controller, Redis) và luồng xử lý từ Git commit đến cluster state.
3. **Cài đặt và vận hành ArgoCD trên local cluster**, deploy application từ Git repository, và quan sát self-healing khi cluster bị drift.
4. **So sánh được ArgoCD và Flux** theo các tiêu chí: architecture, UI, multi-tenancy, scalability, learning curve — và chọn được tool phù hợp theo context.
5. **Thiết kế được GitOps workflow cho production** bao gồm: secret handling, rollback strategy, sync policy, và drift reconciliation.

---

## 2. Bối cảnh & Động lực

### Vấn đề của deployment truyền thống

Trong CI/CD truyền thống (push model), pipeline chạy `kubectl apply` hoặc `helm upgrade` trực tiếp vào cluster. Mô hình này gặp nhiều vấn đề:

- **Drift không kiểm soát**: Ai đó `kubectl edit` trong production → cluster state khác Git → không ai biết state thật là gì.
- **No single source of truth**: State nằm rải rác: CI config, Helm values, manual patches, hotfixes.
- **Audit trail yếu**: Ai deploy gì, lúc nào, vì sao? Phải đào log CI server.
- **Rollback khó**: Rollback = re-run pipeline cũ? Hay `helm rollback`? Hay `kubectl apply` manifest cũ?
- **Security risk**: CI server cần cluster credentials (kubeconfig) → CI server bị hack = cluster bị hack.

### GitOps giải quyết gì

GitOps đảo ngược mô hình: thay vì CI **push** vào cluster, một agent trong cluster **pull** state từ Git:

- Git = single source of truth cho desired state.
- Agent liên tục so sánh desired state (Git) vs actual state (cluster).
- Mọi thay đổi phải qua Git (PR review, approval, audit log miễn phí).
- Drift tự động bị phát hiện và sửa.

### Liên hệ với developer

Nếu bạn đã dùng React/Vue, GitOps giống **declarative UI rendering**:
- Git repo = virtual DOM (desired state).
- Cluster = actual DOM (actual state).
- ArgoCD/Flux = reconciliation engine (diff & patch).
- Khi desired state thay đổi (git push) → engine tự động reconcile actual state.

Nếu bạn đã learn Terraform (Day 26-28), GitOps áp dụng cùng triết lý **desired state + reconciliation** nhưng cho Kubernetes workloads thay vì infrastructure.

---

## 3. Kiến thức nền tảng

### 3.1 Bốn nguyên tắc GitOps (OpenGitOps)

| # | Nguyên tắc | Giải thích |
|---|-----------|-----------|
| 1 | **Declarative** | Toàn bộ system được mô tả declaratively (YAML/HCL) |
| 2 | **Versioned & Immutable** | Desired state được lưu trong Git — mọi thay đổi có history |
| 3 | **Pulled Automatically** | Agent tự động pull và apply desired state |
| 4 | **Continuously Reconciled** | Agent liên tục so sánh desired vs actual, tự sửa drift |

### 3.2 Push vs Pull Deployment

```
Push Model (CI/CD truyền thống):
┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Developer │────▶│ CI Server │────▶│  K8s Cluster  │
│ git push  │     │ kubectl   │     │              │
└──────────┘     │ apply     │     └──────────────┘
                 └──────────┘
                  CI cần credentials

Pull Model (GitOps):
┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Developer │────▶│ Git Repo  │◀────│  K8s Cluster  │
│ git push  │     │ (source   │     │  ArgoCD/Flux  │
└──────────┘     │  of truth)│     │  (pulls)      │
                 └──────────┘     └──────────────┘
                  Agent trong cluster kéo state
```

**Khác biệt quan trọng**:

| Tiêu chí | Push Model | Pull Model (GitOps) |
|----------|-----------|-------------------|
| Credentials | CI server giữ kubeconfig | Agent trong cluster, không cần expose credentials ra ngoài |
| Drift detection | Không có (fire-and-forget) | Liên tục reconcile |
| Audit trail | CI logs (có thể bị xóa) | Git history (immutable) |
| Rollback | Re-run pipeline hoặc manual | `git revert` |
| Security | CI server = attack surface lớn | Cluster pull từ Git (read-only) |

### 3.3 Repository Strategy

Có 2 chiến lược tổ chức Git repo cho GitOps:

**Mono-repo**: App code + K8s manifests trong cùng repo.
```
my-app/
├── src/
├── Dockerfile
├── k8s/
│   ├── base/
│   └── overlays/
│       ├── dev/
│       ├── staging/
│       └── prod/
```

**Multi-repo (recommended)**: Tách app repo và config repo.
```
# App repo: my-app
my-app/
├── src/
├── Dockerfile
└── .github/workflows/build.yaml

# Config repo: my-app-config  
my-app-config/
├── base/
└── overlays/
    ├── dev/
    ├── staging/
    └── prod/
```

**Tại sao multi-repo tốt hơn cho production**:
- CI build app → push image → update image tag trong config repo → ArgoCD deploy.
- Tách quyền: developer có write access app repo, chỉ CD bot có write access config repo.
- Tránh infinite loop: CI trigger khi code thay đổi, không trigger khi config thay đổi.

---

## 4. Deep Dive

### 4.1 ArgoCD Architecture

```mermaid
graph TB
    subgraph "Git Repository"
        GR[Git Repo<br/>Manifests/Helm/Kustomize]
    end

    subgraph "ArgoCD Components"
        API[API Server<br/>gRPC/REST + UI]
        REPO[Repo Server<br/>Clone & render manifests]
        AC[Application Controller<br/>Reconciliation loop]
        REDIS[Redis<br/>Cache]
        DEX[Dex<br/>SSO/OIDC]
    end

    subgraph "Kubernetes Cluster"
        KA[kube-apiserver]
        WL[Workloads<br/>Pods, Services, etc.]
    end

    GR -->|clone & poll| REPO
    REPO -->|rendered manifests| AC
    AC -->|compare desired vs actual| KA
    AC -->|sync/apply| KA
    KA --> WL
    API -->|queries| REPO
    API -->|queries| AC
    API -->|cache| REDIS
    DEX -->|auth| API
    
    User[User/CI] -->|UI/CLI/API| API
```

**Các component chính**:

| Component | Vai trò | Resource usage |
|-----------|--------|---------------|
| **API Server** | gRPC + REST API, Web UI, authentication, RBAC | Medium |
| **Repo Server** | Clone Git repos, render manifests (Helm template, Kustomize build) | High CPU khi render |
| **Application Controller** | Core reconciliation loop — so sánh desired vs actual state | High — heart of ArgoCD |
| **Redis** | Cache cho repo data và app state | Low-Medium |
| **Dex** | SSO integration (OIDC, LDAP, SAML) | Low |
| **ApplicationSet Controller** | Tự động tạo Applications từ template (monorepo, cluster generator) | Low |

### 4.2 ArgoCD Reconciliation Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Git as Git Repo
    participant RS as Repo Server
    participant AC as App Controller
    participant K8s as K8s API

    Dev->>Git: git push (update manifests)
    
    loop Every 3 minutes (default)
        AC->>RS: Get desired state
        RS->>Git: git clone/pull
        RS->>RS: Render manifests<br/>(helm template / kustomize build)
        RS-->>AC: Rendered YAML
        AC->>K8s: Get actual state
        AC->>AC: Diff desired vs actual
        
        alt OutOfSync detected
            alt Auto-sync enabled
                AC->>K8s: kubectl apply
                AC->>AC: Update status: Synced
            else Manual sync
                AC->>AC: Update status: OutOfSync
                Note over AC: Wait for user action
            end
        end
    end
    
    Dev->>AC: Manual sync (UI/CLI)
    AC->>K8s: kubectl apply
```

**Polling interval**: Mặc định 3 phút. Có thể dùng **webhook** từ Git để trigger sync ngay lập tức (giảm delay xuống seconds).

### 4.3 Flux Architecture

```mermaid
graph TB
    subgraph "Flux Controllers"
        SC[Source Controller<br/>GitRepository, HelmRepository]
        KC[Kustomize Controller<br/>Apply Kustomization]
        HC[Helm Controller<br/>Apply HelmRelease]
        NC[Notification Controller<br/>Alerts & Events]
        IC[Image Automation<br/>Controller]
    end

    subgraph "Git"
        GR[Git Repo]
        HR[Helm Repo]
    end

    subgraph "Cluster"
        KA[kube-apiserver]
        WL[Workloads]
    end

    GR -->|poll/webhook| SC
    HR -->|poll| SC
    SC -->|artifacts| KC
    SC -->|artifacts| HC
    KC -->|apply| KA
    HC -->|apply| KA
    KA --> WL
    NC -->|notify| Slack[Slack/Teams/etc.]
    IC -->|update image tag| GR
```

**Flux khác ArgoCD**:
- Flux là **tập hợp controllers** chạy trong cluster, không có centralized server.
- Không có built-in UI (dùng Weave GitOps UI hoặc CLI).
- Native Kubernetes: mọi config là CRDs.
- Image automation: tự động update image tag trong Git khi có new image.

### 4.4 Sync Policies

| Policy | ArgoCD | Flux | Khi nào dùng |
|--------|--------|------|-------------|
| **Manual Sync** | `syncPolicy: {}` hoặc không có `automated` | Không set auto | Production critical, cần approval |
| **Auto Sync** | `syncPolicy.automated.enabled: true` | `interval: 5m` | Dev/staging environments |
| **Self-Heal** | `automated.selfHeal: true` | Mặc định (reconcile loop) | Revert drift về desired state trong Git |
| **Prune** | `automated.prune: true` | `prune: true` | Xóa resource từng được quản lý nhưng đã bị bỏ khỏi Git |

Trong ArgoCD, một `Application` production nên thể hiện rõ `source`, `destination` và `syncPolicy`. Nếu `syncPolicy` không cấu hình `automated`, manual sync là default: ArgoCD vẫn diff desired state trong Git với actual state trong cluster, nhưng chờ người vận hành bấm sync hoặc chạy CLI.

**Self-Heal flow**:
```
1. ArgoCD sync app → cluster có Deployment với 3 replicas
2. Ai đó chạy: kubectl scale deployment app --replicas=10
3. ArgoCD detect drift (actual ≠ desired)
4. selfHeal: true → ArgoCD tự revert về 3 replicas
5. selfHeal: false → ArgoCD chỉ báo OutOfSync, không tự sửa
```

### 4.5 Secret Handling trong GitOps

Secret là thách thức lớn nhất của GitOps vì: **không thể commit plaintext secrets vào Git**.

| Solution | Cách hoạt động | Ưu điểm | Nhược điểm |
|----------|---------------|---------|-----------|
| **Sealed Secrets** | Encrypt secret bằng cluster public key, commit encrypted version | Đơn giản, native K8s | Key rotation phức tạp, cluster-specific |
| **SOPS** | Encrypt values trong YAML bằng KMS/PGP/age | Multi-cloud KMS, partial encryption | Cần setup KMS access |
| **External Secrets Operator** | Sync secrets từ Vault/AWS SM/GCP SM vào K8s | Best for production, centralized | Thêm dependency (Vault/cloud) |
| **Vault Agent Injector** | Sidecar inject secrets vào pod | Dynamic secrets, rotation | Complex setup, sidecar overhead |

**production recommendation**: External Secrets Operator + Vault/AWS Secrets Manager.

### 4.6 Rollback trong GitOps

```mermaid
graph LR
    A[Bug detected] --> B{Rollback strategy?}
    B -->|Git Revert| C[git revert commit<br/>Push to Git<br/>ArgoCD auto-sync]
    B -->|ArgoCD Rollback| D[argocd app rollback<br/>Revert to previous sync]
    B -->|Helm Rollback| E[argocd app actions<br/>run --kind HelmRelease<br/>rollback]
    
    C -->|✅ Recommended| F[Git history clean<br/>Audit trail complete]
    D -->|⚠️ Temporary| G[Cluster reverted<br/>Git still has bad commit<br/>Next sync = re-apply bug]
    E -->|⚠️ Helm only| H[Helm revision reverted<br/>Need sync Git after]
```

**Best practice**: Luôn rollback qua `git revert` — đảm bảo Git và cluster luôn đồng bộ.

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 ArgoCD vs Flux

| Tiêu chí | ArgoCD | Flux |
|----------|--------|------|
| **UI** | ✅ Built-in Web UI (rất tốt) | ❌ Không có (dùng Weave GitOps) |
| **Multi-cluster** | ✅ Một ArgoCD quản lý nhiều clusters | ⚠️ Mỗi cluster cài Flux riêng |
| **Multi-tenancy** | ✅ Projects, RBAC, SSO | ⚠️ Dùng K8s native RBAC |
| **Learning curve** | ⚠️ Nhiều concepts (App, Project, AppSet) | ✅ Ít concepts, Kubernetes-native |
| **Scalability** | ✅ Tốt (sharding, ApplicationSet) | ✅ Rất tốt (lightweight controllers) |
| **Image automation** | ❌ Cần Argo Image Updater (alpha) | ✅ Built-in Image Automation |
| **Helm support** | ✅ Native | ✅ HelmRelease CRD |
| **Kustomize** | ✅ Native | ✅ Native |
| **Community** | ✅ CNCF Graduated, rất lớn | ✅ CNCF Graduated |
| **Resource overhead** | ⚠️ Nhiều components | ✅ Lightweight |

### 5.2 Khi nào chọn gì

| Scenario | Recommendation | Lý do |
|----------|---------------|------|
| **Startup 5-10 engineers** | ArgoCD | UI giúp team non-DevOps dễ adopt, visibility cao |
| **Platform team chuyên** | Flux | Kubernetes-native, lightweight, dễ customize |
| **Multi-cluster enterprise** | ArgoCD | Centralized management, SSO/RBAC built-in |
| **Edge / IoT (nhiều clusters nhỏ)** | Flux | Resource footprint nhỏ hơn |
| **Team đã dùng Helm nhiều** | Cả hai | Cả hai support Helm tốt |
| **Cần image auto-update** | Flux | Built-in Image Automation Controller |

### 5.3 Best Practices

1. **Tách app repo và config repo** — tránh CI infinite loop, tách access control.
2. **Dùng Kustomize overlay cho multi-env** — base → dev/staging/prod overlays.
3. **Bật Self-Heal cho production** — ngăn manual drift.
4. **KHÔNG bật auto-prune cho production ban đầu** — risk xóa nhầm resource.
5. **Dùng Sync Waves / Hooks** — control thứ tự deploy (namespace → configmap → deployment).
6. **Health checks custom** — ArgoCD hỗ trợ custom health check cho CRDs.
7. **Git webhook thay vì polling** — giảm sync delay từ 3 phút xuống seconds.
8. **ApplicationSet cho nhiều apps/clusters** — thay vì copy-paste Application manifests.

### 5.4 Anti-patterns

| Anti-pattern | Vấn đề | Giải pháp |
|-------------|--------|----------|
| Commit secrets plaintext vào Git | Lộ credentials, không thể un-commit | Dùng Sealed Secrets / External Secrets |
| Auto-sync + auto-prune trên prod ngay | Xóa nhầm resources | Bắt đầu manual sync, dần enable auto |
| Dùng `kubectl apply` song song ArgoCD | ArgoCD detect drift, revert changes | Mọi thay đổi phải qua Git |
| Một ArgoCD Application cho toàn bộ cluster | Blast radius quá lớn | Tách Application per team/service |
| Không monitoring ArgoCD itself | ArgoCD down = không deploy được | Monitor ArgoCD health, HA setup |

---

## 6. Performance & Scalability ⭐

### 6.1 ArgoCD Performance

| Metric | Default | Recommendation |
|--------|---------|---------------|
| Polling interval | 3 min | Dùng webhook (near-realtime) |
| Reconciliation timeout | 3 min | Tăng cho large apps |
| Repo cache | 24h | Đủ cho hầu hết cases |
| Max concurrent syncs | 10 | Tăng nếu nhiều apps |

### 6.2 Scaling ArgoCD

| Apps | Recommendation |
|------|---------------|
| < 50 | Single instance, default settings |
| 50-200 | Tăng resource cho Application Controller, Redis |
| 200-1000 | Enable sharding, horizontal scaling Repo Server |
| > 1000 | Multiple ArgoCD instances, ApplicationSet patterns |

### 6.3 Bottlenecks thường gặp

1. **Repo Server CPU**: Render nhiều Helm charts lớn → tăng CPU/replicas cho Repo Server.
2. **Application Controller memory**: Theo dõi nhiều resources → tăng memory.
3. **Git rate limiting**: Polling quá nhiều repos → dùng webhook, tăng cache TTL.
4. **Large manifests**: Một Application có hàng nghìn resources → tách thành nhiều Applications.
5. **etcd pressure**: ArgoCD lưu state vào K8s (ConfigMaps/Secrets) → impact etcd nếu quá nhiều apps.

---

## 7. Security & Reliability Considerations

### 7.1 Security

| Concern | Mitigation |
|---------|-----------|
| ArgoCD credentials | Enable SSO (Dex), disable admin account, OIDC preferred |
| Git access | Deploy key (read-only SSH key per repo) |
| Cluster access | ArgoCD chạy trong cluster, dùng in-cluster config |
| RBAC | ArgoCD Projects giới hạn: namespaces, resources, repos per team |
| Network | ArgoCD API Server nên sau VPN/Ingress với auth |
| Secrets | KHÔNG commit plaintext — dùng Sealed Secrets / External Secrets |

### 7.2 Reliability

| Concern | Mitigation |
|---------|-----------|
| ArgoCD down | HA mode (3 replicas API + Controller) |
| Git down | ArgoCD cache last-known state, cluster vẫn chạy |
| Cluster drift protection | `selfHeal: true` cho critical apps |
| Bad deployment | Automated rollback dựa trên health check |
| Blast radius | Tách Applications per service, dùng Sync Waves |

### 7.3 Disaster Recovery

```
ArgoCD DR Checklist:
□ Backup ArgoCD config (Applications, Projects, Settings)
□ Git repo là source of truth → cluster có thể recreate từ Git
□ Export ArgoCD secrets (Repo credentials, cluster configs)
□ Test: delete ArgoCD namespace → reinstall → re-register repos → verify sync
```

---

## 8. Hands-on Example

### Prerequisites

```bash
# Cần có sẵn
docker --version    # Docker Desktop/Engine
kind version        # kind CLI
kubectl version --client
```

### Bước 1: Tạo local cluster

```bash
# Tạo kind cluster
kind create cluster --name gitops-lab

# Verify
kubectl cluster-info --context kind-gitops-lab
kubectl get nodes
```

Expected output:
```
Kubernetes control plane is running at https://127.0.0.1:xxxx
NAME                       STATUS   ROLES           AGE   VERSION
gitops-lab-control-plane   Ready    control-plane   30s   v1.31.x
```

### Bước 2: Cài ArgoCD

```bash
# Tạo namespace
kubectl create namespace argocd

# Cài ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Chờ pods ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s

# Kiểm tra
kubectl get pods -n argocd
```

Expected output:
```
NAME                                               READY   STATUS    RESTARTS   AGE
argocd-application-controller-0                    1/1     Running   0          60s
argocd-applicationset-controller-xxx               1/1     Running   0          60s
argocd-dex-server-xxx                              1/1     Running   0          60s
argocd-notifications-controller-xxx                1/1     Running   0          60s
argocd-redis-xxx                                   1/1     Running   0          60s
argocd-repo-server-xxx                             1/1     Running   0          60s
argocd-server-xxx                                  1/1     Running   0          60s
```

### Bước 3: Access ArgoCD UI

```bash
# Lấy admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
# Ghi lại password

# Port-forward ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# Mở browser: https://localhost:8080
# Login: admin / <password ở trên>
```

### Bước 4: Cài ArgoCD CLI (optional nhưng recommended)

```bash
# Linux/macOS
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x argocd
sudo mv argocd /usr/local/bin/

# Login CLI
argocd login localhost:8080 --insecure --username admin --password <password>
```

### Bước 5: Deploy application từ Git

Dùng ArgoCD example repo (public):

```bash
# Tạo Application bằng CLI
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default

# Hoặc tạo bằng YAML
cat <<EOF | kubectl apply -f -
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
  syncPolicy: {}  # Manual sync default: không có automated
EOF

# Lúc này Application được tạo nhưng chưa apply workload
argocd app get guestbook

# Manual sync
argocd app sync guestbook

# Kiểm tra status
argocd app get guestbook
kubectl get pods -n default
```

Expected output:
```
Name:               guestbook
Server:             https://kubernetes.default.svc
Namespace:          default
URL:                https://localhost:8080/applications/guestbook
Repo:               https://github.com/argoproj/argocd-example-apps.git
Target:
Path:               guestbook
SyncWindow:         Sync Allowed
Sync Policy:        <none>
Sync Status:        Synced to  (HEAD)
Health Status:      Healthy
```

### Bước 6: Bật automated sync, prune và self-heal

```bash
argocd app set guestbook \
  --sync-policy automated \
  --self-heal \
  --auto-prune

argocd app get guestbook
```

Expected output:
```
Sync Policy:        Automated (Prune)
Sync Status:        Synced to  (HEAD)
Health Status:      Healthy
```

`--auto-prune` chỉ xóa resource đang thuộc Application khi resource đó đã bị loại khỏi Git. Nó không xóa resource lạ được tạo thủ công trong namespace nhưng không thuộc tracking của Application.

### Bước 7: Test Self-Healing (Drift Detection)

```bash
# Sửa trực tiếp trên cluster (simulate drift)
kubectl scale deployment guestbook-ui --replicas=5

# Quan sát ArgoCD phát hiện drift
kubectl get deployment guestbook-ui -w

# Nếu selfHeal=true → ArgoCD sẽ revert replicas về giá trị trong Git
# Quan sát trong UI: app sẽ flash OutOfSync → Synced
```

Expected behavior:
```
# Trước khi sửa
guestbook-ui   1/1   1   1   5m

# Sau kubectl scale 
guestbook-ui   5/5   5   5   5m

# Sau ArgoCD self-heal (~10-30 giây)
guestbook-ui   1/1   1   1   6m    # Reverted về 1 replica
```

### Bước 8: Test Manual Change Detection

```bash
# Thêm label bằng tay
kubectl label deployment guestbook-ui manual-change=true

# Check ArgoCD diff
argocd app diff guestbook

# ArgoCD sẽ detect OutOfSync và self-heal
argocd app get guestbook
```

### Bước 9: Cleanup

```bash
# Xóa application
argocd app delete guestbook --cascade

# Xóa ArgoCD
kubectl delete namespace argocd

# Xóa cluster
kind delete cluster --name gitops-lab
```

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|------------|----------|
| `ComparisonError` | Repo Server không render được manifests | Check Helm values, Kustomize syntax |
| `SyncError` | Apply fail (RBAC, quota, validation) | Check events: `argocd app get <app>` |
| `Unknown` health | CRD không có health check definition | Add custom health check trong ArgoCD config |
| App stuck `Progressing` | Deployment rollout chưa complete | Check pod events, image pull issues |
| `OutOfSync` liên tục | Resource có field server tự thêm (annotations, status) | Dùng `ignoreDifferences` |
| Repo unreachable | SSH key expired, token revoked, firewall | Check: `argocd repo list`, test connectivity |

### 9.2 Debug Commands

```bash
# ArgoCD app status
argocd app get <app-name>
argocd app diff <app-name>
argocd app logs <app-name>
argocd app history <app-name>

# ArgoCD server logs
kubectl logs -n argocd deployment/argocd-application-controller
kubectl logs -n argocd deployment/argocd-repo-server
kubectl logs -n argocd deployment/argocd-server

# Check sync status
argocd app list
argocd app sync <app-name> --dry-run

# Resource tree
argocd app resources <app-name>

# Force refresh (bypass cache)
argocd app get <app-name> --refresh
```

### 9.3 Production Case Study: Drift Detection Saves the Day

#### Context
Một fintech startup (~50 engineers) dùng ArgoCD cho 30 microservices trên 3 clusters (dev/staging/prod).

#### Symptom
Lúc 2h sáng, PagerDuty alert: payment service trả error rate 15%. On-call engineer check → service đang chạy image tag cũ, không phải version trong Git.

#### Investigation
1. Check ArgoCD → payment-service hiện **OutOfSync**. Vì `selfHeal` bị tắt, ArgoCD phát hiện drift nhưng không tự revert.
2. Check `kubectl describe deployment` → image tag bị sửa bằng `kubectl set image` manual lúc 11 PM bởi engineer khác để "hotfix".
3. Hotfix đó có bug → crash sau vài giờ.

#### Root Cause
Engineer bypass GitOps flow, dùng `kubectl set image` trực tiếp. ArgoCD detect drift nhưng không bật `selfHeal`, nên hệ thống vẫn chạy bad image cho đến khi người vận hành sync lại.

#### Mitigation
- Revert: `argocd app sync payment-service` (apply lại state từ Git).
- Service recovered trong 2 phút.

#### Long-term Fix
1. Bật `selfHeal: true` cho tất cả production apps.
2. Cài Kyverno policy chặn `kubectl set image` / `kubectl edit` trên production namespace.
3. Cấu hình ArgoCD notification → Slack khi detect OutOfSync.

#### Lesson Learned
GitOps chỉ hiệu quả khi **enforce** — nếu ai cũng có thể bypass bằng kubectl, Git không còn là source of truth.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ các bài trước được dùng

| Bài trước | Kiến thức sử dụng |
|----------|------------------|
| Day 10-11 | Kubernetes object lifecycle, Deployment, manifests |
| Day 14 | ConfigMap/Secret → GitOps secret handling challenge |
| Day 16 | Helm/Kustomize → ArgoCD render manifests |
| Day 20 | RBAC → ArgoCD RBAC, ServiceAccount |
| Day 21 | Admission Controllers → enforce GitOps policies |
| Day 26 | IaC principles: declarative, desired state, drift → cùng triết lý |
| Day 27-28 | Terraform state management → tương tự Git as state |

### Phase 4 checkpoint — Tổng kết IaC & GitOps

Sau 6 ngày (Day 26-31), bạn đã học:

| Ngày | Topic | Key takeaway |
|------|-------|-------------|
| Day 26 | IaC Principles | Declarative, desired state, drift, idempotency |
| Day 27 | Terraform Basics | Provider, resource, state, plan/apply |
| Day 28 | Terraform Advanced | Remote state, modules, drift handling |
| Day 29 | Pulumi vs Terraform vs CDK | DSL vs GPL trade-offs, decision framework |
| Day 30 | Ansible | Config management, agentless, idempotent playbooks |
| Day 31 | GitOps | Git as source of truth, ArgoCD/Flux, self-healing |

**Mental model**: Terraform quản lý **infrastructure** (VPC, cluster, DB), GitOps (ArgoCD/Flux) quản lý **workloads** trên Kubernetes. Ansible quản lý **configuration** cho legacy/bare-metal.

### Bài sau sẽ mở rộng

- **Day 32**: CI/CD Design Patterns — pipeline stages, quality gates. GitOps là **CD phần cuối** (deployment), CI/CD pipeline là **phần trước** (build, test, scan).
- **Day 33**: GitHub Actions — CI pipeline tạo artifacts, push image → trigger GitOps sync.
- **Day 35**: Deployment Strategies — rolling, canary, blue-green → kết hợp với ArgoCD/Argo Rollouts.

---

## 11. Tài liệu tham khảo

### Must-read

- [ArgoCD Official Docs — Getting Started](https://argo-cd.readthedocs.io/en/stable/getting_started/)
- [OpenGitOps Principles](https://opengitops.dev/)
- [Flux Official Docs — Get Started](https://fluxcd.io/docs/get-started/)

### Nice-to-have

- [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/operator-manual/best_practices/)
- [GitOps with ArgoCD — Codefresh eBook](https://codefresh.io/ebooks/implement-gitops-scale-today/)
- [Flux vs ArgoCD — CNCF comparison](https://www.cncf.io/blog/)
- [Weaveworks GitOps Guide](https://www.weave.works/technologies/gitops/)

### Deep-dive

- [ArgoCD ApplicationSet — Multi-cluster Patterns](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [Sealed Secrets by Bitnami](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [ArgoCD HA setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/)
- Sách: "GitOps and Kubernetes" — Billy Yuen, Alexander Matyushentsev (Manning)

