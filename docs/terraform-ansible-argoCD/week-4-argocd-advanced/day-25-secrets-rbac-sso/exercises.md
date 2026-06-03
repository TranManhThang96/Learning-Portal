# Day 25 - Exercises

## Challenges

---

### Exercise 1: Secret Strategy cho Startup AWS

**Context**: Startup 10 dev, 25 microservices tren AWS EKS, dang dung Sealed Secrets nhung gap van de rotation.

**Yeu cau**:
1. Thiet ke ESO + AWS Secrets Manager + IRSA strategy day nhat
2. Chi tiet IRSA setup: IAM Role, ServiceAccount annotation, ClusterSecretStore YAML
3. Rotation cadence: moi secret type nen co thoi gian refreshInterval nao? Tai sao?
4. Security hardening: IRSA scope, least-privilege IAM policy

**Deliverable**: File `exercises/ex1-eso-aws-strategy.md` voi:
- IRSA setup YAML (ClusterSecretStore, ServiceAccount, IAM)
- IAM policy chi tiet cho ESO role
- Rotation schedule table
- RefreshInterval recommendation cho 5 secret types khac nhau

**Time**: 30 phut

---

### Exercise 2: Bank/Regulated Environment Full Flow

**Context**: Ngân hang ABC, compliance PCI-DSS Level 1, 3 team (Platform, AppDev, Audit).

**Yeu cau**:
Thiet ke day du 4-eye approval + signed commits + dual-control rotation cho secret management:

1. **Dual-control rotation flow**:
   - 2 người cùng xác nhận mới roll được DB password
   - Mô hình: Vault + ESO + CloudTrail audit + signed Git commit

2. **Signed commits**:
   - Setup GPG signing cho CI/CD bot
   - ArgoCD verify GPG key
   - Policy: chi deploy commit da sign

3. **4-eye approval cho production secrets**:
   - Production DB password change = 1 SRE + 1 DBA confirm
   - Integration voi GitHub Protected Branch + CODEOWNERS

**Deliverable**: File `exercises/ex2-bank-secret-flow.md` voi:
- Vault configuration YAML (ES ESO provider)
- CODEOWNERS content
- ArgoCD AppProject policy cho signed-commit enforcement
- Rotation approval workflow (text + diagram)

**Time**: 45 phut

---

### Exercise 3: Migration 80 Services - Sealed Secrets → ESO

**Context**: 80 services đang dùng Sealed Secrets, can migrate sang ESO + AWS Secrets Manager không downtime.

**Yeu cau**:
1. Migration strategy: hybrid mode (chay song song 2 he thong)
2. Migration step-by-step cho 1 service:
   - Import SealedSecret value → AWS Secrets Manager
   - Tao ExternalSecret thay the SealedSecret
   - Validation checklist
3. Batch migration plan cho 80 services:
   - Script outline (bash/python)
   - Risk management: rollback plan
   - Verification sau migration
4. Tinh toan cost (AWS Secrets Manager pricing)

**Deliverable**: File `exercises/ex3-migration-plan.md` voi:
- Migration script outline (pseudo-code, chi tiet)
- Rollback procedure
- Cost estimate table
- Verification checklist

**Time**: 45 phut

---

### Exercise 4: Debug ExternalSecret Stuck

**Context**: ExternalSecret `payment-api-secret` co `SecretSynced=False` ke tu 30 phut, service khong start duoc.

**Logs**:

```
$ kubectl describe externalsecret payment-api-secret
...
Status:
  Conditions:
  - Type:    SecretSynced
    Status:  False
    Message: "remote server rejected request: AccessDeniedException"
  Refresh Time: 2026-05-15T08:30:00Z
```

```
$ kubectl logs -n external-secrets deploy/external-secrets
E0515 08:30:01.234567   1 controller.go:123 "SecretSync" err="AccessDeniedException:
  User: arn:aws:iam::123456789:role/eso-role is not authorized to perform:
  secretsmanager:GetSecretValue"
```

**Yeu cau**:
1. Root cause analysis (khong chi loi IAM)
2. Checklist debug day du (8+ buoc)
3. Fix cho tung root cause
4. Prevention: infrastructure-as-code check cho IAM permissions

**Deliverable**: File `exercises/ex4-debug-checklist.md` voi:
- Root cause analysis table (5 root causes)
- 10-step debug checklist
- Prevention: Terraform/Python script check IAM policy truoc khi deploy ESO

**Time**: 30 phut

---

### Exercise 5: ArgoCD RBAC Refactor - Least Privilege

**Context**: Policy hien tai qua broad, tat ca deu la `role:admin`:
```csv
p, role:admin, applications, *, *, allow
```

5 team can separation:

| Team | Project | Permissions |
|------|---------|-------------|
| platform | platform | Full CRUD |
| backend | apps/backend-* | Sync, View, khong delete |
| frontend | apps/frontend-* | View only |
| data | apps/data-* + infra/data | Full CRUD |
| security | ALL + infra/* | View + audit |

**Yeu cau**:
1. Phan tich 5+ risk cua policy hien tai
2. Thiet ke policy.csv day du cho 5 team + AppProject
3. Implement SSO group → role mapping
4. Test case: 10 scenarios `argocd account can-i` cho tung team
5. Migration plan: changelog, rollback

**Deliverable**: File `exercises/ex5-rbac-least-privilege.md` voi:
- Risk analysis table
- policy.csv day du
- AppProject YAML cho moi team
- 10 test case + expected results
- Migration plan

**Time**: 45 phut

---

### Bonus Exercise: ArgoCD Self-Hardening

**Context**: Production ArgoCD deployment, can harden theo CIS Kubernetes Benchmark.

**Yeu cau** (chon 3 trong 5):

1. **Disable local admin user**:
   - Disable `admin` account
   - Force SSO login
   - Verify: `argocd account list`

2. **Audit log forwarding**:
   - Enable ArgoCD audit log
   - Forward to stdout → Fluent Bit → S3/Elasticsearch
   - Query: "who deleted Application X" trong 90 ngay

3. **Secret backup plan**:
   - Backup ESO sealing key / IRSA role
   - Backup argocd-initial-admin-secret
   - Backup repo credentials
   - Test restore tu backup

4. **Network policy**:
   - ArgoCD pods chi nhan traffic tu ingress
   - ESO pods chi noi voi AWS Secrets Manager endpoint
   - Khong co egress tuong minh

5. **Argocd server TLS hardening**:
   - Custom TLS certificate (cert-manager)
   - Enforce TLS 1.2+
   - Disable TLS 1.0/1.1

**Deliverable**: File `exercises/ex6-argocd-hardening.md` voi:
- 3 challenges da chon, moi challenge: YAML/code + rationale + verification command

**Time**: 60 phut (cho ca 5)

---

## Solution Guidelines

### Exercise 1 - Key Hints
- IRSA: `eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/eso-role`
- ClusterSecretStore `auth.jwt.serviceAccountRef.name: eso-sa`
- DB password: refreshInterval = 15m (compliance)
- TLS cert: refreshInterval = 24h (cert-manager handles rotation)

### Exercise 2 - Key Hints
- ESO Vault provider: `spec.provider.vault.auth.jwt.serviceAccountRef`
- CODEOWNERS: `@team/platform @team/security` cho thu muc secrets
- GitHub Protected Branch: "Require signed commits" + "Require PR"
- CloudTrail: log ten operator + timestamp + secret ID

### Exercise 3 - Key Hints
- Script: loop qua list service → decode sealed secret → put-secret-value → swap CRD
- `kubectl get sealedsecret <name> -o jsonpath='{.spec.encryptedData}' | base64 -d`
- Batch: parallel 5 service/lan, 16 batch = 16 * 5 phut = 80 phut
- Cost: $0.40/secret/mo * 80 = $32/mo + API call

### Exercise 4 - Key Hints
- Root causes: IAM policy thieu, region mismatch, Secret not found, KMS key, ESO CRD version
- Debug: `aws sts get-caller-identity`, `aws secretsmanager list-secrets`, `kubectl auth can-i`
- Prevention: Terraform check: `aws_iam_role_policy` validate before apply

### Exercise 5 - Key Hints
- Risk: anyone can delete, anyone can sync prod, no audit
- AppProject: `namespaceResourceBlacklist: [{group: '', kind: Secret}]`
- `argocd account can-i delete applications "apps/backend-payment" "backend-team"`
- Migration: add deny rules truoc, convert sau, remove deny sau khi verified

### Exercise 6 - Key Hints
- Disable admin: `accounts.admin.enabled: "false"` trong argocd-cm
- Audit: `kubectl get configmap argocd-audit-log -n argocd` hoac sidecar
- Backup: Velero backup `argocd` namespace + ESO CRD
- TLS: `spec.tls.secretName` trong ArgoCD server Deployment
