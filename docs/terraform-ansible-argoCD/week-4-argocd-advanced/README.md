# Week 4 - ArgoCD Advanced (Day 20-27)

## Tổng quan

Week 4 đào sâu các pattern ArgoCD production-grade. Từ thiết kế GitOps repo structure ở quy mô team (Day 20), App-of-Apps để bootstrap nhiều app (Day 21), ApplicationSet cho multi-env (Day 22) và matrix/merge/multi-cluster (Day 23), sync waves + hooks cho dependency ordering (Day 24), secrets management + RBAC + SSO + private repo (Day 25), Argo Rollouts cho progressive delivery (Day 26), đến observability + notifications + backup + disaster recovery để đóng tuần (Day 27).

> **Trạng thái:** Day 20-27 đã hoàn tất. Chuyển sang Week 5 — Capstone Production-Grade.

## Lộ trình học

| Ngày | Chủ đề | Thời lượng | Files |
|------|--------|------------|-------|
| Day 20 | GitOps Repo Structure | 2h | [lesson](day-20-gitops-repo-structure/lesson.md) · [document](day-20-gitops-repo-structure/document.md) · [exercises](day-20-gitops-repo-structure/exercises.md) |
| Day 21 | App of Apps Pattern | 2h | [lesson](day-21-app-of-apps/lesson.md) · [document](day-21-app-of-apps/document.md) · [exercises](day-21-app-of-apps/exercises.md) |
| Day 22 | ApplicationSet Basics | 2h | [lesson](day-22-applicationset-basics/lesson.md) · [document](day-22-applicationset-basics/document.md) · [exercises](day-22-applicationset-basics/exercises.md) |
| Day 23 | ApplicationSet Advanced (Matrix, Merge, Multi-Cluster) | 2h | [lesson](day-23-applicationset-advanced/lesson.md) · [document](day-23-applicationset-advanced/document.md) · [exercises](day-23-applicationset-advanced/exercises.md) |
| Day 24 | Sync Waves, Hooks, Dependencies | 2h | [lesson](day-24-sync-waves-hooks/lesson.md) · [document](day-24-sync-waves-hooks/document.md) · [exercises](day-24-sync-waves-hooks/exercises.md) |
| Day 25 | Secrets Management, RBAC, SSO, Private Repo | 2h | [lesson](day-25-secrets-rbac-sso/lesson.md) · [document](day-25-secrets-rbac-sso/document.md) · [exercises](day-25-secrets-rbac-sso/exercises.md) |
| Day 26 | Argo Rollouts, Progressive Delivery | 2h | [lesson](day-26-argo-rollouts/lesson.md) · [document](day-26-argo-rollouts/document.md) · [exercises](day-26-argo-rollouts/exercises.md) |
| Day 27 | ArgoCD Observability, Notifications, Backup & DR | 2h | [lesson](day-27-argocd-observability-dr/lesson.md) · [document](day-27-argocd-observability-dr/document.md) · [exercises](day-27-argocd-observability-dr/exercises.md) |

## Chi tiết từng ngày

### Day 20 - GitOps Repo Structure

**Mục tiêu:** Phân biệt monorepo vs polyrepo, tách `infra-repo` / `platform-repo` / `apps-repo` đúng ownership, áp dụng environment folder strategy (per-env folder vs per-env branch), promotion qua Pull Request, rollback bằng Git revert.

- **Kiến thức:** 4 lý do tách repo (ownership boundary, change frequency, blast radius, compliance), mô hình 3-repo và dependency direction (infra → platform → apps), monorepo vs polyrepo trade-off, 3 strategy folder env, trunk-based branching, promotion = thay đổi image tag qua PR, rollback = `git revert` (không dùng `git reset --hard` hoặc `argocd app rollback` trên prod).
- **Lab:** Skeleton 3 repo với CODEOWNERS chuẩn, README ownership, promotion flow + bot (image-bump GitHub Action + promote workflow), ArgoCD root Application point vào `platform-repo`, 1 promotion thực dev → staging và rollback bằng `git revert`.
- **Document:** 4 repo template (solo / small-team / enterprise / bank regulated), ownership matrix 10×10, README template, CODEOWNERS reference, branch protection settings, promotion flow diagrams, rollback runbook 3 scenarios, CI/CD job catalog, 15-bullet anti-patterns.
- **Exercises:** 6 challenges + 2 bonus.

### Day 21 - App of Apps Pattern

**Mục tiêu:** Triển khai root Application quản lý nhiều child Application, cấu hình bootstrap ordering (CRD → platform addon → workload), dùng finalizer `resources-finalizer.argocd.argoproj.io` để cascade delete, phân biệt khi nào dùng App of Apps vs ApplicationSet.

- **Kiến thức:** Diagram root → child, cấu trúc YAML root Application, bootstrap ordering 7-layer (CRD → controller → secret → workload), chicken-and-egg scenarios (ArgoCD self-managed, Sealed Secrets seal key), finalizer cascade behavior table 5×5.
- **Deep dive:** So sánh 3 cách bootstrap (manual / App of Apps / ApplicationSet), 5 common pitfalls (cascade stuck, finalizer loop, sync policy mismatch, recursive App of Apps, namespace race).
- **Lab (13 bước):** Tạo branch `platform-repo`, AppProject platform, 5 child Application YAML (ingress-nginx, cert-manager, kube-prometheus-stack, guestbook, demo), root `bootstrap/root-app.yaml`, manual bootstrap, quan sát chain sync, test thêm/xóa app qua Git, test cascade deletion với/không finalizer.
- **Document:** 4 template YAML (root, child Helm/Kustomize/Plain), sync policy combination table, finalizer behavior table, bootstrap ordering checklist, 15-bullet anti-patterns, migration path App of Apps → ApplicationSet.
- **Exercises:** 6 challenges (refactor 8 app → App of Apps; bootstrap order 6 component; multi-cluster shared template; debug root stuck; DR khi xóa root không finalizer; self-managed ArgoCD).

### Day 22 - ApplicationSet Basics

**Mục tiêu:** Hiểu ApplicationSet CRD + controller, nắm 4 generator cơ bản (List, Git Directory, Git File, Cluster), viết template với Go template syntax, deploy 3 services × 2 envs bằng 1 ApplicationSet, thêm service mới chỉ bằng tạo folder.

- **Kiến thức:** ApplicationSet CRD + controller riêng biệt, render template từ generator → CREATE/UPDATE/DELETE Application, Go template syntax (`{{path.basename}}`, `{{values.key}}`), `preserveResourcesOnDeletion`.
- **Deep dive:** Bảng so sánh App of Apps vs ApplicationSet, decision tree generator, operational complexity (mass create/delete, dry-run, `goTemplate: true` vs legacy), pitfalls (tên trùng, generator data thay đổi → app bị xóa, race condition 2 ApplicationSet).
- **Lab (10 bước):** Skeleton apps-repo `services/{api,worker,frontend}/{base,overlays/{dev,staging}}`, List generator warm-up, refactor sang Git Directory, auto-discovery thêm service, thêm env mới, xóa overlay → prune, Git File generator, failure scenario tên trùng.
- **Document:** Cheat sheet 4 generator với YAML đầy đủ, template syntax reference, naming convention recipe, decision tree, common errors table, migration recipe, 10+ anti-patterns.
- **Exercises:** 6 challenges (5×3 Git File với resources/replicas khác nhau; naming convention; debug 3 failure scenarios; safe cleanup script; migration 30 child apps → 0 downtime; bonus nested ApplicationSet).

### Day 23 - ApplicationSet Advanced: Matrix, Merge, Multi-Cluster

**Mục tiêu:** Phân biệt Matrix (cartesian product) vs Merge (join + override), thiết kế hub-and-spoke multi-cluster, áp dụng Cluster generator với labels + values per cluster, tránh anti-patterns ở scale 100+ Applications.

- **Kiến thức:** Matrix YAML (`matrix > generators > [g1, g2]`, cartesian, giới hạn 2 child generators), Merge với `mergeKeys` (join semantics, bottom-to-top override), Cluster generator nâng cao (selector qua label + `values` block), SCM Provider + Pull Request generator overview.
- **Deep dive:** Decision tree generator combination, multi-cluster patterns (hub-and-spoke recommended, federation, ArgoCD Agent), naming convention ở scale (DNS limit 253 chars, label limit 63 chars), scale issue (500+ App = render time, sharding controller), pitfalls (matrix nested, mergeKeys collision, `selector: {}` = TẤT CẢ cluster).
- **Lab (7 bước):** 2 kind cluster (`kind-dev`, `kind-staging`), đăng ký cluster declarative, Matrix services × clusters, Merge `mergeKeys: service`, Cluster selector + values per cluster, naming convention với `nameSuffix`, scale test 30 Application, disaster scenario xóa cluster secret.
- **Document:** Generator decision tree, Matrix vs Merge cheat sheet, declarative cluster secret + labels, multi-cluster topology comparison, naming convention reference, scale tuning checklist, 15-bullet anti-patterns.
- **Exercises:** 6 challenges + 3 bonus (8×4×3 = 96 App design; per-cluster GDPR sidecar; debug missing 1/4; tên Application > 63 chars refactor; migration 1 hub 800 App → shard/federation; bonus Pull Request generator + dynamic preview env per PR).

### Day 24 - Sync Waves, Hooks, Dependencies

**Mục tiêu:** Hiểu sync wave (annotation `argocd.argoproj.io/sync-wave`) vs hook (`argocd.argoproj.io/hook`), cấu hình 4 hook type + PostDelete, thiết kế CRD ordering, viết migration Job idempotent, debug stuck sync.

- **Kiến thức:** ArgoCD sync flow 3 phase (PreSync → Sync → PostSync, +SyncFail), trong mỗi phase resources nhóm theo wave (default 0, wave nhỏ trước), hook là transient resource (Job phổ biến), hook deletion policy (`HookSucceeded`, `HookFailed`, `BeforeHookCreation`), CRD ordering tự động, idempotency là yêu cầu bắt buộc.
- **Deep dive:** Sync wave vs hook (wave = ordering, hook = transient task), 3 pattern phổ biến (DB migration PreSync Job, wait-for dependency, smoke test PostSync), trade-off hook vs init container vs Job thường, 10 pitfalls.
- **Lab (14 bước):** namespace `demo-orders` qua wave -1, bootstrap ESO preview Day 25 (wave -10/-5/0), demo `orders` với schema migration (Hook PreSync Job), failure scenarios (migration exit 1; imagePullBackOff), idempotency test, CRD ordering test, sync wave + secret + app, cleanup với finalizer.
- **Document:** Annotations table, phase timeline diagram, common patterns YAML (DB migration, wait-for, notification, smoke test), bootstrap order recipe 8 component, idempotent migration playbook, hook deletion policy decision tree, 15-bullet anti-patterns, Helm hook vs ArgoCD hook comparison.
- **Exercises:** 6 challenges (bootstrap order 8 component; long-running Flyway 15 phút + timeout; debug stuck Progressing 2h; refactor init container migration → ArgoCD hook; non-idempotent partial state DB recovery; bonus cross-Application dependency workaround).

### Day 25 - Secrets Management, RBAC, SSO, Private Repo

**Mục tiêu:** Phân biệt 4 secret pattern Git-compatible (Sealed Secrets, SOPS+age/KMS, External Secrets Operator, CSI Secret Store), cấu hình ArgoCD RBAC declarative qua `policy.csv` + AppProject, hiểu SSO/OIDC qua Dex, quản private repo credentials declarative (PAT/SSH/GitHub App).

- **Kiến thức:** Tại sao Kubernetes Secret thường KHÔNG đủ (base64 ≠ encrypt), 4 pattern Git-compatible, ArgoCD RBAC 2 layer (built-in + custom policy.csv qua `argocd-rbac-cm`), AppProject là logical security boundary, SSO Dex bundled, private repo via Secret type `repository`.
- **Deep dive:** Bảng so sánh 4 pattern × 6 axes, best solution theo context (cá nhân: SOPS+age; small team: Sealed Secrets; startup AWS: ESO+ASM+IRSA; enterprise: ESO+Vault; bank: HSM Vault + dual-control + signed commits), pitfalls (mất seal key, SOPS key leak, IRSA scope, policy.csv reload, admin password mặc định).
- **Lab 4 phần (60 phút):** Part A — ESO Helm wave -10, SecretStore demo, ExternalSecret → k8s Secret `orders-db`, rotation refresh; Part B — `argocd-rbac-cm` policy 3 role (dev / platform / sre), local user, AppProject roles + token; Part C — Secret type `repository` GitHub PAT → GitHub App; Part D — `dex.config` GitHub OIDC mock + group → role mapping.
- **Document:** Decision matrix 4×6, RBAC cheat sheet (built-in roles, action verbs, `p,g` syntax, AppProject roles), SSO checklist, private repo reference, bootstrap chicken-and-egg playbook, rotation playbook, 17-bullet anti-patterns.
- **Exercises:** 6 challenges (ESO+ASM+IRSA startup 10 dev; bank dual-control signed commits 4-eye; migration 80 service Sealed Secrets → ESO; debug ExternalSecret stuck `SecretSyncedError`; refactor RBAC `*,*,allow,*` → least privilege; bonus hardening ArgoCD self).

### Day 26 - Argo Rollouts, Progressive Delivery

**Mục tiêu:** Phân biệt rolling vs blue-green vs canary, refactor Deployment → Rollout CRD, cấu hình canary với traffic step + AnalysisTemplate Prometheus, simulate bad version + rollback bằng `kubectl argo rollouts undo` hoặc Git revert.

- **Kiến thức:** Argo Rollouts CRD `Rollout` thay Deployment, strategy block `canary` / `blueGreen`, AnalysisTemplate + AnalysisRun (Prometheus metric), traffic shaping (replica-based vs Istio/SMI/ALB Ingress), diagram timeline canary 0% → 25% → 50% → 100%.
- **Deep dive:** 3 cách tiếp cận (Deployment + RollingUpdate / Argo Rollouts / service mesh native), bảng so sánh, performance/cost/security implications, pitfalls (cluster không có Prometheus, query trả null, traffic split với ClusterIP, abort vs revert, blue-green giữ 2× resource), best solution per context.
- **Lab (8 bước):** Cài Argo Rollouts controller + kubectl plugin, refactor Deployment `orders` → `Rollout` với canary steps + pause, deploy v1 → v2 quan sát canary, failure scenario v3 image lỗi → manual abort + `kubectl argo rollouts undo`, AnalysisTemplate Prometheus check success-rate.
- **Document:** Strategy reference YAML đầy đủ (canary + blue-green), 5 AnalysisTemplate (Prometheus p95/error/success, Datadog, Web), traffic shaping comparison, decision tree canary/blue-green/rolling, 15-bullet anti-patterns, 9-error reference, CLI quick reference.
- **Exercises:** 5 challenges + 1 bonus (refactor 5 service → Rollout; AnalysisTemplate 3 metric; debug AnalysisRun stuck Inconclusive; blue-green với DB migration backward-compatible; multi-cluster canary promotion gate; bonus Flagger vs Argo Rollouts).

### Day 27 - ArgoCD Observability, Notifications, Backup & DR

**Mục tiêu:** Expose ArgoCD metrics qua ServiceMonitor + Prometheus scrape, đọc 20+ key metrics, cấu hình PrometheusRule alert (ArgoAppSyncFailed, ArgoAppNotHealthy, ArgoAppOutOfSync), cấu hình argocd-notifications trigger qua webhook mock, backup/restore bằng `argocd admin export`/`import`, thiết kế DR strategy với RPO/RTO target.

- **Kiến thức:** 3 endpoint metrics (server `:8083`, app-controller `:8082`, repo-server `:8084`), top 20 key metrics (`argocd_app_info`, `sync_total`, `reconcile`, `health`, `cluster_*`), Prometheus ServiceMonitor pattern (label `release: prometheus` bắt buộc), Grafana dashboard 14584/19974, argocd-notifications architecture, backup scope, 3 backup strategy (GitOps-only / `argocd admin export` / Velero), RPO/RTO matrix.
- **Deep dive:** Backup comparison × 7 axes (RPO/RTO/coverage/secret/cost), notification routing (per AppProject / per team / per severity P0-P3), alert fatigue vs missed incident, cost (Prometheus retention, Grafana Cloud, Slack), security (backup chứa secret, webhook token leak), best solution per context, 7 pitfalls.
- **Lab (9 bước):** kube-prometheus-stack qua Application sync wave -10, 3 ServiceMonitor, Grafana dashboard 14584 + 19974, PrometheusRule 3 alert (`for: 10m / 1m / 5m`), argocd-notifications webhook.site mock, fail-demo trigger notification, backup `argocd admin export` + restore, GitOps-style DR (delete `argocd` namespace + reinstall + restore + sync all), cleanup.
- **Document:** Metrics catalog 20+ entries, ServiceMonitor YAML template, notification trigger reference + CEL filter, backup checklist (must-have / should-have / nice-to-have), DR runbook 3 scenarios (lost ArgoCD <30min, lost cluster <4h, lost Git repo <24h), RPO/RTO matrix 4 tier, 15-bullet anti-patterns, 10-error reference.
- **Exercises:** 6 challenges + 3 bonus (alert design 5 service × 4 alert; notification routing 3 team × 4 severity + maintenance suppression; full cluster loss DR <30min; Sealed Secrets seal key lost recovery; multi-cluster Prometheus federation; incident postmortem template; bonus 3 GameDay scenarios).

## Cấu trúc folder

```
week-4-argocd-advanced/
├── README.md
├── day-20-gitops-repo-structure/      lesson + document + exercises
├── day-21-app-of-apps/                lesson + document + exercises
├── day-22-applicationset-basics/      lesson + document + exercises
├── day-23-applicationset-advanced/    lesson + document + exercises
├── day-24-sync-waves-hooks/           lesson + document + exercises
├── day-25-secrets-rbac-sso/           lesson + document + exercises
├── day-26-argo-rollouts/              lesson + document + exercises
└── day-27-argocd-observability-dr/    lesson + document + exercises
```

## Cách sử dụng

1. Học tuần tự Day 20 → Day 27 (nội dung ngày sau build trên ngày trước)
2. Mỗi ngày bắt đầu bằng `lesson.md`: 30 phút theory → 30 phút deep dive → 60 phút lab
3. Tra cứu nhanh trong `document.md` khi cần reference (cheat sheet, decision tree, anti-patterns)
4. Làm thêm `exercises.md` nếu muốn nâng cao (5-6 challenges/ngày)

## Yêu cầu môi trường

- **Docker Desktop / Docker Engine**
- **kind** >= 0.20 hoặc **minikube** (lab local ArgoCD; Day 23 multi-cluster cần ≥ 8GB RAM)
- **kubectl** >= 1.28
- **Helm** >= 3.13
- **Kustomize** >= 5.x
- **argocd CLI** >= v3.4 (hoặc một release ArgoCD còn supported)
- **External Secrets Operator** (Day 24-25, cài qua Helm)
- **Argo Rollouts controller** + **kubectl argo rollouts** plugin (Day 26)
- **kube-prometheus-stack** (Day 27, cài qua Helm)
- **GitHub account** (cho lab repo public hoặc local bare repo fallback)
- **gh CLI** (optional, cho automation Day 20)

## Chi phí cloud

- Day 20-27: **Miễn phí** hoàn toàn (chạy ArgoCD + tooling trên kind cluster local + GitHub free tier)
- Day 23 multi-cluster lab dùng nhiều kind cluster local hoặc namespace simulation, không cần EKS thật
- Day 25 ESO Part A dùng fake provider hoặc HashiCorp Vault dev mode (không AWS Secrets Manager thật)
- Day 27 notification dùng webhook.site mock, Prometheus + Grafana chạy local
- Chỉ Capstone (Week 5) mới có option AWS production-like

## Tính liên tục

**Input từ Week 3:**
- kind cluster + ArgoCD installed (Day 17)
- Application + AppProject patterns (Day 18)
- Helm/Kustomize base/overlay structure (Day 19)

**Trong Week 4 — chuỗi build:**
- Day 20 → Day 21: 3-repo skeleton + `bootstrap/root-app.yaml` được Day 21 implement đầy đủ qua App of Apps
- Day 21 → Day 22: ApplicationSet giải quyết boilerplate khi N services × M envs
- Day 22 → Day 23: Matrix/Merge/Multi-Cluster nâng cấp Cluster generator + multi-cluster topology
- Day 23 → Day 24: cross-cutting ordering concern, áp dụng cho cả Application thường và ApplicationSet
- Day 24 → Day 25: sync wave -10 dùng cho ESO Helm trước SecretStore → ExternalSecret → app
- Day 25 → Day 26: AppProject + RBAC làm security boundary cho Rollout, Rollout reuse `orders` app từ Day 24
- Day 26 → Day 27: progressive delivery cần observability để promote/abort an toàn → Prometheus metrics + alert + DR khi rollout fail

**Output cho Week 5 (Capstone):**
- Repo structure (infra/platform/apps) Day 20 = skeleton chính cho Capstone Day 28-35
- App of Apps + ApplicationSet (Day 21-23) = backbone bootstrap platform layer Day 32
- Sync waves (Day 24) cho ordering CRD → operator → secret → DB migration → app trong Day 33
- Secrets management (Day 25) = tiền đề cho ESO + AWS Secrets Manager Capstone Mode B
- RBAC + AppProject Day 25 = security baseline cho Capstone production-like
- Argo Rollouts Day 26 = công cụ promote dev → staging → prod Day 33
- Observability + DR Day 27 = blueprint cho Capstone Day 34-35

## Tiếp theo

Week 5 - Capstone Production-Grade (Day 28-35) build platform end-to-end với 3 microservice, observability stack, CI/CD pipeline, và disaster recovery scenarios. Xem [`../week-5-capstone/README.md`](../week-5-capstone/README.md).
