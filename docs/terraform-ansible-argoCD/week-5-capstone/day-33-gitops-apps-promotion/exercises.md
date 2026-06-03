# Day 33 — GitOps Apps Layer & Promotion Strategy: Exercises

## Exercise 1 — Promotion Challenge: Coordinate Multi-Service Release

### Scenario

Team đang release feature "payment-v2" cần update 3 service cùng lúc:
- `api-service`: v1.2.0 (breaking change: response format thay đổi)
- `worker-service`: v1.2.0 (support payload format mới từ api-service)
- `frontend-service`: v1.3.0 (UI update tương thích với api-service v1.2.0)

### Requirements

1. Tạo 3 promotion PR từ dev → staging cho từng service
2. Viết script promotion workflow đảm bảo thứ tự đúng: api-service → worker-service → frontend-service
3. Staging chỉ approved khi cả 3 service đều deployed và smoke test passed
4. Tạo production promotion plan với rollback plan chi tiết

### Hints

- Dùng GitHub Actions workflow có `concurrency` để serialize promotion
- API và worker có dependency: frontend chỉ được promote sau khi api + worker đã stable
- Cần check deployment success trước khi promotion tiếp theo

---

## Exercise 2 — ApplicationSet Auto-Discovery: Thêm Service Mới Không Sửa Manifest

### Scenario

Team muốn thêm `notification-service` vào platform. Với git generator hiện tại, bạn cần đảm bảo:
- Service mới xuất hiện trong dev tự động (auto-sync)
- Service mới xuất hiện trong staging nhưng không auto-sync (chờ promotion)
- Service mới xuất hiện trong prod nhưng cần manual approval

### Requirements

1. Tạo thư mục `services/notification-service/` với cấu trúc chuẩn
2. Sử dụng k8s manifest đơn giản cho notification-service (deployment + service)
3. Commit và push lên apps-repo
4. Verify ArgoCD tự động tạo 3 Application mới (dev, staging, prod)
5. Verify dev auto-synced, staging/prod chờ promotion

### Challenge Extension

Nếu team muốn `preview` environment tự động cho mỗi PR (ephemeral preview), thiết kế thêm ApplicationSet generator dùng **pull request generator** của ArgoCD.

```yaml
# Gợi ý: pull-request generator
generators:
  - pullRequest:
      repoURL: https://github.com/<org>/apps-repo.git
      # Tự động tạo preview environment cho mỗi PR
```

---

## Exercise 3 — Debug Drift Scenario

### Scenario — Production Drift

Lúc 23:00, bạn nhận được alert: `api-service-prod` OutOfSync. Kiểm tra nhanh:

```bash
$ argocd app get api-service-prod
Name:               api-service-prod
Sync Status:        OutOfSync ✗
Health Status:      Healthy ✓
Repository:         https://github.com/<org>/apps-repo
Target Revision:    HEAD
Path:               services/api-service/overlays/prod
Server:             https://kubernetes.default.svc

DIFF:
  metadata.labels.app.kubernetes.io/version:
    - "v1.2.0"     # Git (desired)
    + "v1.1.9"     # Cluster (actual)

$ kubectl get deployment api-service -n api-service-prod -o jsonpath='{.spec.template.spec.containers[0].image}'
ghcr.io/<org>/api-service:v1.1.9
```

### Requirements

1. **Phân tích nguyên nhân:** Tại sao cluster có v1.1.9 trong khi Git có v1.2.0?
2. **Đề xuất 3 hypothesis** và cách verify từng cái
3. **Chọn hành động phù hợp:**
   - ArgoCD sync
   - Git revert
   - kubectl apply (emergency)
   - Không làm gì (sacceptable drift)
4. **Viết post-mortem notes** về lessons learned và preventive measure

### Answer Template

```markdown
## Drift Analysis — api-service-prod

### Timeline
- 22:45 — CI pipeline pushed v1.2.0 to production (PR #456 merged)
- 22:46 — ArgoCD sync triggered
- 22:47 — Pod restarted with v1.1.9 ??? ← abnormal
- 23:00 — Alert fired

### Root Cause Hypotheses

1. **Hypothesis A: [description]**
   - Evidence: [...]
   - Verification: [...]

2. **Hypothesis B: [description]**
   - Evidence: [...]
   - Verification: [...]

3. **Hypothesis C: [description]**
   - Evidence: [...]
   - Verification: [...]

### Chosen Action: [X]

### Preventive Measures
- [...]
```

---

## Exercise 4 — Image Tag Strategy Migration

### Scenario

Team hiện tại dùng `latest` tag cho mọi environment. Bạn cần migrate sang immutable tag strategy mà không gây downtime.

### Requirements

1. **Audit current state:** Viết script scan tất cả Helm values trong apps-repo để tìm tất cả usage của `latest` tag
2. **Design migration plan:** Làm sao migrate tất cả service mà không gây incident?
3. **Implement:** Tạo GitHub Actions workflow tự động:
   - Extract git tag / semantic version từ CI context
   - Push image với immutable tag (semver + sha)
   - Update apps-repo overlay values tự động sau khi image pushed
   - Tạo PR cho staging/prod promotion
4. **Verification:** Sau migration, verify không còn service nào dùng `latest` cho staging/prod

### Migration Safety Rules

- Migration phải reversible
- Không có downtime
- Mỗi service migration là independent commit
- Migration phải có rollback plan

---

## Exercise 5 — Canary Promotion với Argo Rollouts Integration

### Scenario

Team muốn thử canary release cho `api-service` trước khi full promotion lên production. Dùng Argo Rollouts (đã cài từ Day 26) để:

1. Deploy version mới với 10% traffic (canary)
2. Auto-promote nếu error rate < 1% trong 10 phút
3. Auto-rollback nếu error rate > 5%

### Requirements

1. Tạo Argo Rollout manifest cho `api-service` (thay Deployment bằng Rollout)
2. Cấu hình canary strategy: `setWeight: 10`, analysis template
3. Tích hợp với Prometheus metrics cho error rate measurement
4. Tạo GitHub Actions workflow trigger canary promotion
5. Mô phỏng bad release và verify Argo Rollouts rollback tự động

### Hints

```yaml
# Argo Rollout manifest reference
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api-service
spec:
  strategy:
    canary:
      canaryService: api-service-canary
      stableService: api-service-stable
      trafficRouting:
        nginx:
          stableIngress: api-service
      steps:
        - setWeight: 10
        - pause: {duration: 10m}
        - setWeight: 50
        - pause: {duration: 5m}
        - setWeight: 100
      analysis:
        templates:
          - templateName: api-service-analysis
        startingStep: 1
        args:
          - name: service-name
            value: api-service-canary
```

---

## Exercise 6 — Design Review: Multi-Cluster Promotion

### Scenario

Team mở rộng lên 2 cluster: `us-west-2` (primary) và `eu-west-1` (DR). Promotion flow cần:
- dev → staging (shared cluster)
- staging → production-us (primary cluster)
- production-us → production-eu (DR promotion, chỉ sau khi US healthy > 24h)

### Requirements

1. **Thiết kế GitOps repo structure** hỗ trợ multi-cluster
2. **Thiết kế ApplicationSet** dùng cluster generator để deploy đến cả 2 cluster
3. **Thiết kế promotion workflow:**
   - Làm sao ArgoCD biết khi nào US cluster healthy?
   - DR promotion có nên auto hay manual?
4. **Viết disaster recovery plan** cho scenario: US cluster mất hoàn toàn
5. **Tính toán blast radius** nếu promotion workflow bị bug

### Evaluation Criteria

- Blast radius của mỗi step
- Recovery time objective (RTO)
- Promotion gate có đủ không?
- DR cluster có truly independent không?

---

## Exercise 7 — Secrets trong Promotion Workflow

### Scenario

`api-service` cần database credentials để chạy. Credentials được quản lý bằng External Secrets Operator (Day 25). Vấn đề: promotion workflow cần đảm bảo secrets luôn available trước khi app start.

### Requirements

1. Cấu hình External Secrets cho api-service (dùng ESO CRD)
2. Tạo SyncWave/hook để đảm bảo Secret được tạo TRƯỚC KHI Deployment rollout
3. Viết GitHub Actions step kiểm tra secret exists trước khi approve promotion
4. Mô phỏng scenario: secret rotation → app cần restart → promotion workflow xử lý ra sao?

### Hints

- Dùng ArgoCD SyncWave (`annotations.argocd.argoproj.io/sync-wave`) để ordering
- Dùng PreSync hook để verify secret existence
- ESO sync có thể mất vài giây → cần retry logic

---

## Exercise 8 — Performance: Optimize ApplicationSet Reconciliation

### Scenario

Platform có 50 microservices × 3 environments = 150 Applications. Mỗi lần thêm service mới, ArgoCD mất 3-5 phút để phát hiện.

### Requirements

1. **Benchmark current performance:** Measure thời gian reconcile trước và sau optimization
2. **Implement optimizations:**
   - Shallow clone cho git generator
   - Resource exclusions (không scan binary files)
   - ApplicationSet controller replica scaling
3. **Verify:** So sánh thời gian trước và sau
4. **Document:** Best practice cho monorepo với 100+ services

### Metrics to Capture

```bash
# Thời gian git clone
time git clone --depth 1 <repo>

# ApplicationSet reconcile time
kubectl get events -n argocd \
  --field-selector reason=ReconciliationCompleted \
  | tail -20

# ArgoCD API latency
argocd metrics | grep application_sync_total
```

---

## Bonus — Greenfield: Design Zero-Downtime Promotion Pipeline

### Challenge

Thiết kế từ đầu promotion pipeline cho hệ thống mới (greenfield) với yêu cầu:
- Zero-downtime deployment
- Atomic promotion (all-or-nothing)
- Instant rollback (< 30 giây)
- Audit log đầy đủ cho compliance
- Multi-region support

### Constraints

- Budget: $0 cho infrastructure (dùng kind + free tools)
- Team: 1 developer + 1 platform engineer
- Timeline: Phải ship trong 1 sprint (2 tuần)

### Output

1. Architecture diagram (ASCII)
2. GitHub Actions workflow definitions
3. ArgoCD sync policy configuration
4. Rollback automation script
5. Compliance audit log format
