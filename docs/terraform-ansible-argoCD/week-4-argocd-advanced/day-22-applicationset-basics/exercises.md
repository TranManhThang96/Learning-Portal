# Day 22 — Exercises: ApplicationSet Basics

<div v-pre>

## Before You Start

```bash
# Verify pre-req
kubectl get pods -n argocd | grep applicationset
kind get clusters
argocd version --client
```

---

## Challenge 1: Git File Generator cho 5 services × 3 envs

**Mục tiêu:** Tạo ApplicationSet deploy 5 services vào 3 env (dev/staging/prod) với replicas và memory khác nhau per env.

### Setup

Tạo 5 services: `api`, `worker`, `frontend`, `cache`, `scheduler`.

### Yêu cầu

1. Mỗi service có `services/<name>/config.yaml`:
   ```yaml
   service: <name>
   replicas: <per-env value>
   memory: <per-env value>
   ```

2. Values thực tế:

| Service | dev replicas | staging replicas | prod replicas | memory dev | memory staging | memory prod |
|---|---|---|---|---|---|---|
| api | 1 | 2 | 5 | 256Mi | 512Mi | 2Gi |
| worker | 1 | 2 | 3 | 128Mi | 256Mi | 1Gi |
| frontend | 1 | 2 | 4 | 128Mi | 256Mi | 1Gi |
| cache | 1 | 1 | 2 | 256Mi | 512Mi | 1Gi |
| scheduler | 1 | 1 | 2 | 64Mi | 128Mi | 256Mi |

3. Tạo ApplicationSet dùng Git File generator:
   - Pattern: `services/*/config.yaml`
   - `{<!-- -->{values.service}}-{<!-- -->{values.env}}` làm tên Application
   - SyncPolicy: automated với `prune: false` (an toàn)
   - `CreateNamespace: true`

4. **Deliverable:** Git commit URL + output:
   ```bash
   kubectl get application -l app.kubernetes.io/created-by=applicationset
   # Phải thấy 15 Application
   argocd app list
   ```

5. **Verification:** Thêm prod replica count = 10 cho `api`, commit, observe OutOfSync → sync → verify `kubectl get deployment api -n prod -o jsonpath='{.spec.replicas}'`

---

## Challenge 2: Naming Convention Design

**Mục tiêu:** Thiết kế naming convention cho scenario phức tạp.

### Scenario

- Services: `payment-gateway-v2`, `auth-service`, `user-profile-api`, `notification-hub`
- Envs: `dev`, `staging`, `uat`, `production`
- Constraints:
  - Kubernetes name tối đa 253 ký tự, chỉ a-z, 0-9, `-`
  - ArgoCD hiển thị theo group (env trước)
  - Tránh xung đột nếu service tên dài

### Yêu cầu

1. Đề xuất 2-3 naming convention options (env-service, truncated, có prefix)
2. Chọn 1 convention tối ưu, giải thích lý do
3. Viết ApplicationSet template dùng convention đó
4. Kiểm tra: tất cả 16 Application name phải hợp lệ (Kubernetes rules)
5. Test: tạo thêm service `external-partner-integration-service` → verify name không conflict

**Hint:** Dùng `{<!-- -->{path[1] | lower | replace " " "-"}}` để sanitize.

---

## Challenge 3: Debug — Missing Application

**Mục tiêu:** Debug scenario thực tế.

### Scenario

Bạn thêm folder `services/analytics-service/overlays/dev/` vào repo, commit, push. Chờ 5 phút nhưng `analytics-service-dev` Application không xuất hiện.

### Yêu cầu

1. **Chuẩn đoán:** Viết script/danh sách bước kiểm tra (không được sửa gì):
   - Git push thành công?
   - ApplicationSet pattern match?
   - File `kustomization.yaml` có tồn tại trong folder?
   - ApplicationSet controller log nói gì?
   - Repo credentials trong ArgoCD có quyền đọc repo không?

2. **Reproduce:** Tạo 3 scenario gây lỗi khác nhau:
   - a) Thiếu `kustomization.yaml`
   - b) Pattern không match (sai path)
   - c) Tên folder gây trùng Application name

3. **Fix + Verify:** Với mỗi scenario, fix và verify Application xuất hiện.

4. **Deliverable:** Document tất cả log output, error messages, và fix.

---

## Challenge 4: Safe Cleanup Design

**Mục tiêu:** Thiết kế flow an toàn khi xóa service.

### Scenario

Service team muốn xóa `legacy-reporting-service` khỏi repo. Nhưng họ không muốn:
- Namespace `legacy` bị xóa (còn service khác)
- Workload của service khác bị ảnh hưởng
- Application CRD bi xóa vội (cần audit trail)

### Yêu cầu

1. Thiết kế deletion flow đảm bảo:
   - [ ] Namespace `legacy` còn lại (service khác đang dùng)
   - [ ] Workload của `legacy-reporting-service` bị prune sau khi xác nhận
   - [ ] Application CRD được preserve trước khi xóa (backup)
   - [ ] Không có downtime cho các service khác

2. Implement:

   a) Tạo script `scripts/safe-remove-service.sh <service-name>`:
   ```bash
   # 1. Backup Application CRD ra YAML file
   # 2. Annotate ApplicationSet để preserve resource
   # 3. Xóa folder trong Git
   # 4. Verify ApplicationSet sinh ra Application mới (không có service đó)
   # 5. Sau X ngày, cho phép prune workload
   # 6. Xóa backup file
   ```

   b) Áp dụng script xóa `legacy-reporting-service`

3. **Deliverable:** Script + output log + verification.

---

## Challenge 5: Migration — 30 App of Apps → ApplicationSet (0 downtime)

**Mục tiêu:** Migrate từ App of Apps có 30 child Application sang ApplicationSet.

### Scenario

```
apps-repo/argocd/applications/   # 30 Application YAML files
├── team-platform/
│   ├── monitoring-dev.yaml
│   ├── monitoring-staging.yaml
│   └── ... (10 files)
├── team-payment/
│   ├── payment-api-dev.yaml
│   └── ... (10 files)
└── team-core/
    └── ... (10 files)
```

Mỗi Application đã có syncPolicy và destination khác nhau.

### Yêu cầu

1. **Phân tích:**
   - Các pattern chung giữa 30 file (template hóa được gì?)
   - Các file có spec hoàn toàn khác nhau (cần giữ riêng?)
   - Estimate: bao nhiêu ApplicationSet cần tạo?

2. **Plan migration** (viết ra paper plan):
   - Step 1: Inventory 30 file → phân nhóm
   - Step 2: Identify template-able vs unique specs
   - Step 3: Quyết định: 1 ApplicationSet hay N ApplicationSet
   - Step 4: Migration sequence (không downtime)

3. **Implement cho 10 sample Application** (team-platform):
   - Tạo `services/platform/*/overlays/*/` structure
   - Tạo ApplicationSet cho team-platform (10 Application)
   - Verify sync trước khi migrate phần còn lại

4. **Rollback plan:** Nếu ApplicationSet fail sau khi deploy, làm sao revert nhanh?

5. **Deliverable:** Migration plan document + implemented sample + verification.

---

## Challenge 6 (Bonus): Nested ApplicationSet Anti-pattern?

**Mục tiêu:** Phân tích và thiết kế pattern phức tạp.

### Scenario

Một developer đề xuất:

> "Tao 1 ApplicationSet sinh ra Application, nhưng bản thân Application đó có source là... 1 ApplicationSet manifest. Rồi ArgoCD sync nó → tạo ra ApplicationSet thật sự."

Mục tiêu: động lực tạo ApplicationSet từ Git (thay vì apply trực tiếp).

### Yêu cầu

1. **Phân tích:** Đây là pattern hay anti-pattern?
   - Ưu điểm?
   - Nhược điểm?
   - Risk về security, performance, debugging?

2. **Research:** Tìm kiếm pattern này trong ArgoCD community
   - Có ai đã làm chưa?
   - ArgoCD có hỗ trợ native không?
   - Alternative nào tốt hơn?

3. **Design alternative:** Nếu đây là anti-pattern, đề xuất pattern thay thế đạt cùng mục tiêu (ApplicationSet từ Git, không cần apply trực tiếp).

4. **Deliverable:** Phân tích 1-2 trang (viết trong file `exercises/bonus-nested-analysis.md`).

---

## Submission

Sau khi hoàn thành, chạy:

```bash
echo "=== Day 22 Exercise Status ==="
kubectl get application -l app.kubernetes.io/created-by=applicationset | wc -l
argocd app list --selector app.kubernetes.io/created-by=applicationset --output wide
```

Commit tất cả manifests vào branch `day-22/exercises` và push.

</div>
