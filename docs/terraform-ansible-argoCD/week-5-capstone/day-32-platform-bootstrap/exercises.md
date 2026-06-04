# Day 32 — Exercises & Challenges

> **Phần mở rộng sau lab chính — Platform Bootstrap**
> Độ khó: Intermediate (⭐⭐) → Advanced (⭐⭐⭐)
> Không bắt buộc hoàn thành trong 2 tiếng lab chính

---

## Challenge 1: Refactor Bootstrap sang ApplicationSet Generator

**Mức độ:** ⭐⭐ Intermediate
**Thời gian:** 30-45 phút
**Context:** Hiện tại dùng App of Apps — mỗi platform app là 1 Application YAML riêng. Refactor thành ApplicationSet với Matrix generator.

**Yêu cầu:**

1. Tạo `platform-apps/applicationset.yaml` thay thế 5 Application YAML riêng lẻ.

2. Dùng Matrix generator:
   - `generatorA`: Git generator chỉ folder `argocd/platform-apps/charts/`
   - `generatorB`: List generator cho các component: `cert-manager`, `external-secrets`, `ingress-nginx`, `prometheus`

3. Template Application phải include:
   - `name`: `{<!-- -->{ path.basename }}` (tên folder)
   - `namespace`: argocd
   - `destination.server`: https://kubernetes.default.svc
   - `source.repoURL`: Git repo URL
   - `source.path`: `argocd/platform-apps/charts/{<!-- -->{values.component}}/`
   - Helm values inline

4. Thêm label vào ApplicationSet:
   ```yaml
   labels:
     platform-bootstrap: "true"
     managed-by: argocd
   ```

**Hint:**
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: platform-apps
spec:
  generators:
    - matrix:
        generators:
          - git:
              repoURL: https://github.com/<user>/capstone-platform.git
              revision: HEAD
              directories:
                - path: argocd/platform-apps/charts/*
          - list:
              elements:
                - component: cert-manager
                  chartVersion: "1.16.*"
                - component: external-secrets
                  chartVersion: "2.4.*"
                # ...
```

**Deliverable:** File `argocd/platform-apps/applicationset.yaml` + file structure:
```
argocd/platform-apps/charts/
├── cert-manager/
│   ├── Chart.yaml
│   └── values.yaml
├── external-secrets/
│   ├── Chart.yaml
│   └── values.yaml
└── ...
```

---

## Challenge 2: Debug — Platform Bootstrap Failure Scenarios

**Mức độ:** ⭐⭐⭐ Advanced
**Thời gian:** 45-60 phút

Mỗi scenario bên dưới mô phỏng 1 lỗi bootstrap thực tế. Debug từng case.

---

### Scenario 2A: ESO ClusterSecretStore Secret Key Không Tồn Tại

**Symptom:**
```bash
kubectl get externalsecret api-service-secrets
# STATUS: SecretSyncingError
# MESSAGE: "Could not retrieve secret: secret capstone/dev/api-service/database not found."

kubectl describe externalsecret api-service-secrets
# Last sync: <timestamp>
# Status: SecretSyncingError
```

**Debug steps:**
1. Liệt kê các bước cần kiểm tra (cluster, ESO controller, ASM, IAM)
2. Xác định root cause chính xác
3. Đề xuất fix (2 cách: create secret + alternative approach)

**Root cause:** Secret không tồn tại trong AWS Secrets Manager.

**Fix option 1 (tạo secret):**
```bash
aws secretsmanager create-secret \
  --name capstone/dev/api-service/database \
  --secret-string '{"host":"localhost","port":5432,"database":"capstone","user":"admin","password":"changeme"}' \
  --region us-east-1
```

**Fix option 2 (dùng secret thay thế trong values):**
Thay đổi ESO manifest để dùng secret khác tồn tại trong ASM.

---

### Scenario 2B: ArgoCD App OutOfSync nhưng Resource Không Thay Đổi

**Symptom:**
```bash
argocd app get cert-manager
# Sync Status: OutOfSync
# Health:    Progressing
# Comparison:
#   there are no differences but the application status is OutOfSync
```

**Debug steps:**
1. Kiểm tra `argocd app diff cert-manager` — có diff không?
2. Kiểm tra `kubectl get helmrelease cert-manager -n cert-manager`
3. Kiểm tra `argocd app history cert-manager`
4. Kiểm tra ArgoCD repo server logs

**Root cause:** Helm release có `spec.superseded` state — ArgoCD không detect được Helm state mới nhất (Helm 3 "semantic release" vs ArgoCD repo-server rendering mismatch).

**Fix:**
```bash
# Option 1: Sync với force (replace)
argocd app sync cert-manager --force

# Option 2: Thay đổi spec để trigger reconciliation
# Sửa annotation trong Application:
kubectl patch application cert-manager \
  -n argocd \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/force-sync":"'$(date +%s)'"}}}' \
  --type merge

# Option 3: Dùng `ignoreDifferences` để ignore Helm metadata
# Thêm vào Application spec:
# ignoreDifferences:
#   - group: helm.toolkit.fluxcd.io
#     kind: HelmRelease
#     jsonPointers:
#       - /status
```

---

### Scenario 2C: cert-manager Certificate Stuck ở Pending

**Symptom:**
```bash
kubectl get certificate
# NAME         READY   AGE
# api-service  False   5m

kubectl describe certificate api-service
# Events:
#   Type     Reason                 Age   From                     Message
#   Normal   WaitingForCertificate  5m    cert-manager-certificat  "Certificate is not issued yet,
#                                                                  is the ACME solver working?"
```

**Debug steps:**
1. `kubectl get challenges` — có challenge resource không?
2. `kubectl describe challenge` — lỗi cụ thể là gì?
3. `kubectl logs -n cert-manager deploy/cert-manager`
4. Check Ingress resource có annotation `cert-manager.io/cluster-issuer` không?

**Possible causes:**
- HTTP01: Ingress chưa có annotation → fix: thêm annotation
- DNS01: Route53 IAM permission → fix: IRSA annotation trên cert-manager SA
- ACM: ACM certificate pending → fix: verify DNS validation

**Fix (HTTP01 missing annotation):**
```yaml
# Sửa Ingress, thêm annotation:
metadata:
  annotations:
    cert-manager.io/cluster-issuer: selfsigned-issuer
    cert-manager.io/issuer-kind: ClusterIssuer
```

---

### Scenario 2D: Prometheus OOMKilled trong kind

**Symptom:**
```bash
kubectl get pods -n monitoring
# NAME                              READY   STATUS      RESTARTS   AGE
# prometheus-prometheus-0           0/2     OOMKilled   -          3m

kubectl top pods -n monitoring
# NAME                              CPU(c)   MEMORY(bytes)
# prometheus-prometheus-0           0        0 (OOMKilled)
```

**Debug:**
1. Prometheus pod bị OOMKilled → memory limit quá thấp
2. kind cluster có giới hạn Docker Desktop memory

**Fix (giảm resource request):**
```yaml
# Trong values.yaml, giảm retention và memory:
prometheus:
  prometheusSpec:
    retention: 7d
    retentionSize: 2GB
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: standard
          resources:
            requests:
              storage: 2Gi
```

---

## Challenge 3: Platform Bootstrap Design Review

**Mức độ:** ⭐⭐⭐ Advanced
**Thời gian:** 30-45 phút (design + document)

### Part A: Multi-Cluster Bootstrap Design

**Scenario:** Team muốn deploy platform apps lên 3 EKS clusters:
- `eks-dev` (us-east-1)
- `eks-staging` (us-east-1)
- `eks-prod` (eu-west-1)

Mỗi cluster cần: ArgoCD, cert-manager, ESO, Ingress, Prometheus.

**Task:**
1. Vẽ architecture diagram cho multi-cluster bootstrap
2. Thiết kế ApplicationSet structure:
   - Cluster generator: list 3 clusters
   - App of Apps cho mỗi cluster
   - Values per cluster: dev vs prod (Prometheus retention, replica count)
3. Xác định shared vs cluster-specific values
4. Đề xuất secret management strategy: ESO StoreSecret cho từng cluster
5. Đề xuất promotion flow: platform app version từ dev → staging → prod

**Deliverable:** Architecture diagram (ASCII) + ApplicationSet YAML skeleton + ADR cho multi-cluster bootstrap

---

### Part B: Terraform Bootstrap Module Design

**Scenario:** Convert lab bootstrap (Helm apply trực tiếp) thành Terraform `helm_release` cho ArgoCD bootstrap (hybrid pattern).

**Task:**

1. Viết Terraform module `modules/argocd-bootstrap/`:
   - `main.tf`: Helm release cho ArgoCD + ArgoCD SA + IRSA (Mode B)
   - `variables.tf`: inputs cần thiết (cluster_name, oidc_provider_arn, etc.)
   - `outputs.tf`: ArgoCD server URL, admin secret name

2. Viết root module `envs/dev/bootstrap.tf`:
   - Gọi module `argocd-bootstrap`
   - Terraform `local-exec` để apply AppProject sau khi ArgoCD up (vì ArgoCD chưa up khi terraform apply)

3. Thiết kế `local-exec` workaround:
```bash
# Wait for ArgoCD to be ready before applying AppProject
until kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-server | grep -q Running; do
  echo "Waiting for ArgoCD server..."
  sleep 5
done
kubectl apply -f argocd/appproject.yaml
```

4. Đề xuất cách handle drift: khi ArgoCD bootstrap qua Git (thay đổi values), làm sao Terraform không overwrite?

---

## Challenge 4: Security Hardening Bootstrap

**Mức độ:** ⭐⭐⭐ Advanced
**Thời gian:** 30 phút

### Part A: ArgoCD Security Hardening

**Task:** Viết ArgoCD Application đã hardened cho production, bao gồm:

1. **SSO với GitHub (Dex connector):**
   - OAuth App trên GitHub
   - ArgoCD Dex config
   - RBAC policy: `g, platform-team, role:admin`

2. **Repository credential qua ESO:**
   - GitHub PAT được lưu trong ESO/ASM
   - Inject vào ArgoCD ConfigMap không commit vào Git

3. **Resource restrictions:**
   - AppProject không allow wildcard destination
   - ArgoCD không có quyền delete namespace
   - ArgoCD không có quyền modify ArgoCD own Application

```yaml
# ArgoCD Application hardened
spec:
  project: platform
  source:
    repoURL: https://github.com/<user>/capstone-platform.git
    # Không dùng wildcard source
    ref:
      # Dùng branch thay vì HEAD
  destination:
    server: https://kubernetes.default.svc
    # Không dùng wildcard server
  syncPolicy:
    # Không auto-sync trên prod
```

---

## Challenge 5: Observability cho Bootstrap Layer

**Mức độ:** ⭐⭐ Intermediate
**Thời gian:** 20-30 phút

### Part A: Prometheus Alerts cho Platform Bootstrap Health

**Task:** Tạo PrometheusRule cho platform components, bao gồm:

1. **ArgoCD health alerts:**
```yaml
groups:
  - name: argocd-bootstrap
    rules:
      - alert: ArgoCDServerDown
        expr: up{job="argocd-server"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "ArgoCD server is down"
          description: "ArgoCD has been down for more than 2 minutes"
```

2. **cert-manager alerts:**
   - `CertManagerNotReady`: cert-manager pods không Running
   - `CertificateExpiring`: certificate sắp hết hạn (< 7 ngày)
   - `CertificateRequestStuck`: request > 30 phút chưa issued

3. **ESO alerts:**
   - `ESOPodsNotHealthy`: ESO controller không Running
   - `ExternalSecretSyncError`: ExternalSecret ở SecretSyncingError > 10 phút

4. **Ingress alerts:**
   - `IngressControllerDown`: ingress-nginx controller replicas = 0
   - `NGINXHighErrorRate`: error rate > 5% trong 5 phút

### Part B: Grafana Dashboard Fragment

**Task:** Viết JSON/Grafana dashboard fragment cho platform bootstrap overview, gồm:

1. **Panel 1:** ArgoCD Application sync status (pie chart)
2. **Panel 2:** Platform component health (table: name, namespace, status, age)
3. **Panel 3:** Certificate expiry countdown (gauge)
4. **Panel 4:** ESO sync status + last successful refresh

---

## Self-Check Questions

Trả lời ngắn (2-3 câu mỗi câu):

**Q1:** Tại sao ArgoCD không nên có `automated: {}` trên prod environment?

**Q2:** Khi nào dùng `ClusterSecretStore` thay vì `SecretStore`?

**Q3:** Sự khác biệt giữa `ignoreDifferences` và `ignoreHealth` trong ArgoCD Application spec?

**Q4:** cert-manager HTTP01 challenge hoạt động như thế nào? Tại sao cần Ingress Controller?

**Q5:** Prometheus `prometheusSpec.podMonitorSelector` được dùng để làm gì? Điều gì xảy ra nếu không set?

---

## Bonus: Production-Like Enhancement

**Mức độ:** ⭐⭐⭐ Advanced
**Không bắt buộc — cho học viên muốn đi sâu**

### Implement GitOps Promotion cho Platform Apps

1. **Setup promotion flow:**
   - `platform-apps/` repo có branch: `main` (dev), `staging`, `prod`
   - ArgoCD Application dev: `automated: {}`
   - ArgoCD Application staging: manual sync, PR-based promotion
   - ArgoCD Application prod: manual sync, 2-approvals required

2. **Implementation:**
   - ArgoCD Application staging:
   ```yaml
   syncPolicy:
     automated: null  # No auto-sync on staging
     retry:
       limit: 3
   ```

   - Promotion mechanism: Merge PR từ `main` → `staging` → `prod`

3. **Test promotion:**
   - Update cert-manager version trong `main`
   - Verify: dev auto-sync, staging manual, prod manual
   - Rollback: Revert PR

---

## Expected Output của Exercises

```
day-32-platform-bootstrap/
├── exercises/
│   ├── challenge-1-applicationset/
│   │   ├── applicationset.yaml
│   │   └── charts/
│   │       ├── cert-manager/Chart.yaml + values.yaml
│   │       ├── external-secrets/Chart.yaml + values.yaml
│   │       ├── ingress-nginx/Chart.yaml + values.yaml
│   │       └── prometheus/Chart.yaml + values.yaml
│   ├── challenge-2-debug/
│   │   └── debug-notes.md    ← notes cho từng scenario
│   ├── challenge-3-design-review/
│   │   ├── multi-cluster-diagram.md
│   │   └── terraform-bootstrap-module/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   ├── challenge-4-security/
│   │   ├── argocd-hardened.yaml
│   │   └── rbac-policy.md
│   ├── challenge-5-observability/
│   │   ├── platform-alerts.yaml
│   │   └── dashboard-fragment.json
│   └── self-check-answers.md
└── bonus-promotion/
    ├── promotion-flow.md
    └── platform-apps-promotion.yaml
```
