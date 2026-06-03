# Day 25 - Secrets Management, RBAC, SSO, Private Repo

## Reference Document

---

## 1. Secret Pattern Decision Matrix

| Tieu chi | Sealed Secrets | SOPS+age/KMS | ESO | CSI Driver |
|----------|---------------|--------------|-----|-----------|
| Secret storage | Cluster | Git (encrypted file) | External store | External store |
| Rotation effort | Medium (redepoly) | Medium (re-encrypt) | Low (auto 5m-1h) | Low (auto) |
| Audit trail | None | Cloud KMS log | Full cloud log | Full |
| Disaster recovery | Backup sealing key | Backup age key / KMS | Full | Full |
| Bootstrap complexity | Medium | Medium | High | Medium |
| External dependency | None | None | SecretStore connectivity | CSI provider |
| Cost | Free | Free (age) / cloud KMS | $0.40/secret/mo + API | $0.40/secret/mo |
| ArgoCD integration | SealedSecret CRD | kustomize-sops plugin | ExternalSecret CRD | Volume mount |
| Best fit | Small team | Dev/learn | Cloud-native startup | Pod-level secrets |
| Rotation gap | Hours-days | Hours-days | Minutes | Minutes |
| Credential exposure | Cluster only | Git (encrypted) | Cloud IAM | Pod runtime |

**Recommendation quick-pick**:
- Hoc tap / offline: `SOPS + age` (1 file key)
- Small team < 10 dev: `Sealed Secrets`
- Cloud-native AWS: `ESO + AWS Secrets Manager + IRSA`
- Enterprise multi-cloud: `ESO + HashiCorp Vault`
- Regulated (bank/gov): `ESO + Vault HSM + dual-control`

---

## 2. ArgoCD RBAC Reference

### 2.1 Built-in Roles

| Role | Mo ta | Action |
|------|-------|--------|
| `role:admin` | Full access, khong bi chan | Tat ca action tren tat ca resource |
| `role:edit` | Thay doi nhung khong xoa | create, update, sync, rollback |
| `role:readonly` | Chi doc | get, list |

**Default**: Unauthenticated user = `role:readonly` (set qua `policy.default`).

### 2.2 Resource Types

| Resource | Mo ta |
|----------|-------|
| `applications` | ArgoCD Application |
| `clusters` | Kubernetes cluster connections |
| `projects` | AppProject |
| `repositories` | Git repo credentials |
| `exec` | kubectl exec vao Pod qua ArgoCD |
| `accounts` | Local user accounts |
| `certificates` | Cluster certificates |
| `gpgkeys` | GPG key management |

### 2.3 Action Verbs

`get`, `create`, `update`, `delete`, `sync`, `override`, `rollback`, `action`, `*` (all)

### 2.4 policy.csv Syntax Cheat Sheet

```csv
# Group assignment: g, <subject>, <role>
g, my-org:platform-team, role:admin
g, my-org:developers, role:readonly

# Policy: p, <subject>, <resource>, <action>, <object>, <effect>
p, my-org:developers, applications, get, apps/*, allow
p, my-org:developers, applications, sync, apps/*, allow
p, my-org:developers, applications, delete, apps/*, deny

# Object format: <project>/<name> hoac */*
# Effect: allow / deny
# Match mode: glob (default) hoac regex (set policy.matchMode)

# Role inheritance
g, role:admin, role:readonly   # Admin co them quyen cua readonly
```

### 2.5 AppProject Scoping Example

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
  namespace: argocd
spec:
  # Repositories duoc phep
  sourceRepos:
  - 'https://github.com/org/gitops'
  - 'https://github.com/org/k8s-config'

  # Cluster + namespace duoc phep deploy den
  destinations:
  - namespace: platform-*
    server: https://kubernetes.default.svc
  - namespace: argocd
    server: https://kubernetes.default.svc

  # Cluster-scoped resource cho phep
  clusterResourceWhitelist:
  - group: 'monitoring.coreos.com'
    kind: Prometheus

  # Chan namespace-scoped Secret
  namespaceResourceBlacklist:
  - group: ''
    kind: Secret

  # Custom roles trong project
  roles:
  - name: cicd-deployer
    description: CI/CD bot - deploy app moi
    policies:
    - p, proj:platform:cicd-deployer, applications, create, platform/*, allow
    - p, proj:platform:cicd-deployer, applications, sync, platform/*, allow

  # Token cho CI (tao bang lenh, khong declarative)
  # kubectl argocd account generate-token --account cicd-bot -p platform
```

### 2.6 Test RBAC Policy

```bash
# Test permission cho subject
argocd account can-i get applications '*'
argocd account can-i sync applications "apps/api-service" "my-org:developers"
argocd account can-i delete applications "platform/*" "my-org:sre"

# Kiem tra role hien tai cua user
argocd account get-user <username>
```

---

## 3. SSO Setup Checklist

### 3.1 GitHub OAuth

```yaml
# argocd-cm
data:
  url: https://argocd.example.com
  oidc.config: |
    name: GitHub
    issuer: https://github.com
    clientID: <GitHub OAuth App Client ID>
    clientSecret: $oidc.github.clientSecret  # ref Secret
    requestedScopes:
    - openid
    - profile
    - email
```

```bash
# argocd-rbac-cm
# Map GitHub team → ArgoCD role
g, my-org:platform-team, role:admin
g, my-org:developers, role:readonly
```

### 3.2 Google Workspace OIDC

```yaml
oidc.config: |
  name: Google
  issuer: https://accounts.google.com
  clientID: <CLIENT_ID>.apps.googleusercontent.com
  clientSecret: $oidc.google.clientSecret
  requestedScopes:
  - openid
  - profile
  - email
```

### 3.3 Generic OIDC (Azure AD, Okta, Keycloak)

```yaml
oidc.config: |
  name: Okta
  issuer: https://<org>.okta.com
  clientID: <CLIENT_ID>
  clientSecret: $oidc.okta.clientSecret
  requestedScopes:
  - openid
  - profile
  - email
  - groups   # Quan trong: map group claim
  requestedIDTokenClaims:
    groups:
      essential: true
```

### 3.4 SSO Setup Checklist

- [ ] ArgoCD URL duoc cau hinh dung trong `argocd-cm` (khong co trailing slash)
- [ ] Dex pod chay: `kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-dex-server`
- [ ] Client ID/Secret duoc luu trong Secret, khong hardcode
- [ ] `scopes` trong argocd-rbac-cm chua dung claim name (thuong la `groups`)
- [ ] Group claim tu IdP co gia tri (test bang `argocd account can-i`)
- [ ] `policy.csv` co `g` line map group → role
- [ ] Restart argocd-server sau khi thay doi RBAC
- [ ] Test: login bang SSO → kiem tra quyen tren UI

---

## 4. Private Repo Credential Reference

### 4.1 HTTPS PAT (Personal Access Token)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-repo-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  url: https://github.com/org/private-repo
  username: git
  password: ghp_<TOKEN>  # GitHub PAT
```

**Tạo GitHub PAT**:
- Settings → Developer settings → Personal access tokens → Fine-grained tokens
- Permissions: `contents: read` la du
- Han che: dung "machine user" account, khong dung personal account

### 4.2 SSH Key

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-ssh-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  url: git@github.com:org/private-repo.git
  sshPrivateKey: |
    -----BEGIN OPENSSH PRIVATE KEY-----
    <PRIVATE_KEY>
    -----END OPENSSH PRIVATE KEY-----
```

### 4.3 GitHub App (Recommended Enterprise)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: github-app-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  github.com-appID: <APP_ID>
  github.com-app-installation-id: <INSTALLATION_ID>
  github.com-app-private-key: |
    -----BEGIN RSA PRIVATE KEY-----
    <PRIVATE_KEY>
    -----END RSA PRIVATE KEY-----
```

**So sanh**:

| Method | Rotation | Scope | Audit | Setup complexity |
|--------|----------|-------|-------|-----------------|
| PAT | Thủ cong | Full org hoac repo | Limited | Low |
| SSH | Thủ cong | Per key | Limited | Low |
| GitHub App | Auto-expiring | Per org/repo | Full | High |

---

## 5. Bootstrap Chicken-and-Egg Playbook

Day 25 pattern: ESO can cluster secret store, nhung secret store credentials cung can bao ve.

### Phase 0: Backup & Preparation

```bash
# 1. Backup current cluster state
velero backup create pre-eso-install --include-namespaces argocd

# 2. Backup any existing ArgoCD admin password hash
kubectl get secret argocd-initial-admin-secret -n argocd -o yaml > admin-secret-backup.yaml
```

### Phase 1: Install ESO

```yaml
# Cluster-scoped: Application with sync wave -10
# <PLACEHOLDER: external-secrets Application, sync-wave: -10>
```

### Phase 2: Create Initial SecretStore Credentials

**Option A: IRSA (AWS EKS)**:
```yaml
# IAM Role + ServiceAccount annotation
# <PLACEHOLDER: ClusterSecretStore voi AWS provider, auth: jwt: serviceAccountRef: name: eso-sa>
# IAM Role can: secretsmanager:GetSecretValue, secretsmanager:ListSecrets
```

**Option B: Static credentials** (chanh cho production):
```yaml
# <PLACEHOLDER: ClusterSecretStore voi AWS provider, auth: secretRef:
#   accessKeyIDSecretRef + secretAccessKeySecretRef
# WARNING: Khong dung trong production, IRSA required>
```

### Phase 3: Secret Rotation Plan

| Secret | Rotation cadence | Method |
|--------|-----------------|--------|
| DB password | 90 ngay | ESO auto-sync |
| AWS access key | 30 ngay | IRSA rotation |
| ArgoCD admin password | 30 ngay | Manual, backup truoc |
| GitHub PAT | 90 ngay | Manual, machine user |
| TLS cert | 90 ngay | cert-manager + ESO |

---

## 6. Rotation Playbook

### 6.1 DB Password (ESO + AWS Secrets Manager)

```bash
# 1. Generate new password in AWS Secrets Manager
aws secretsmanager rotate-secret \
  --secret-id prod/orders/db-password

# 2. ESO auto-sync (refreshInterval: 1h) hoac force reconcile
kubectl annotate externalsecret orders-db \
  external-secrets.io/sync-policy=reconcile

# 3. Verify new secret in cluster
kubectl get secret orders-db -o jsonpath='{.data.password}' | base64 -d

# 4. Trigger app rollout (mount secret = pod restart)
kubectl rollout restart deployment api-service -n apps
```

### 6.2 AWS Credentials (IRSA)

```bash
# 1. IRSA auto-rotates; chi can update IAM policy
aws iam update-role-policy --role-name eso-role \
  --policy-name eso-policy --policy-document file://eso-policy.json

# 2. Verify ESO pod su dung IRSA
kubectl exec -n external-secrets deploy/external-secrets -- \
  aws sts get-caller-identity
```

### 6.3 ArgoCD Admin Password

```bash
# 1. Change via argocd CLI
argocd account update-password \
  --account admin \
  --current-password <OLD> \
  --new-password <NEW>

# 2. Hoac declarative (patch secret)
# <PLACEHOLDER: argocd-initial-admin-secret patch voi hash moi>
# bcrypt: kubectl run -it --rm argon-bcrypt --image=python:3.10 -- \
#   python3 -c "import bcrypt; print(bcrypt.hashpw(b'newpass', bcrypt.gensalt()).decode())"

# 3. Backup
kubectl get secret argocd-initial-admin-secret -n argocd -o yaml | \
  velero backup create argocd-admin-$(date +%Y%m%d)
```

---

## 7. Anti-Patterns Checklist

- [ ] **KHONG** dung `password` hoac `admin` lam password mac dinh
- [ ] **KHONG** commit `values.yaml` co secret raw len Git
- [ ] **KHONG** dung base64 encoded secret lam "encryption"
- [ ] **KHONG** dung personal PAT cho CI/CD (dung machine user hoac GitHub App)
- [ ] **KHONG** luu age private key / SOPS key trong CI/CD environment variable
- [ ] **KHONG** dung `*, *, allow, *` trong policy.csv (full access)
- [ ] **KHONG** bo qua `namespaceResourceBlacklist` trong AppProject
- [ ] **KHONG** dung `cluster-admin` cho ESO service account
- [ ] **KHONG** dung `kind: Secret` (default) thay vi `kind: SealedSecret` trong Git
- [ ] **KHONG** enable delete permission cho developer role
- [ ] **KHONG** dung ArgoCD admin token cho CI/CD (dung project token)
- [ ] **KHONG** bo qua etcd encryption-at-rest khi dung Kubernetes Secret
- [ ] **KHONG** dung SSH key cho repo deploy (dung PAT hoac GitHub App)
- [ ] **KHONG** commit Sealed Secrets sealing key (private key cluster) len Git
- [ ] **KHONG** bo qua RBAC restart sau khi update policy.csv
- [ ] **KHONG** dung `kind: Secret` thuong cho database credentials (dung ESO)

---

## 8. Common Errors Reference

| Error | Nguyen nhan | Fix |
|-------|------------|-----|
| `ExternalSecret: SecretSynced=False` | SecretStore khong ton tai | Check ClusterSecretStore name |
| `ExternalSecret: SecretSynced=False` | IAM permission thieu | Them `secretsmanager:GetSecretValue` |
| `ExternalSecret: SecretSynced=False` | ESO pod khong chay | `kubectl get pods -n external-secrets` |
| `external-secrets: context deadline exceeded` | Network toi SecretStore | Check VPC endpoint, security group |
| `argocd: repo not found` | Repo credentials sai | Kiem tra Secret label + token |
| `argocd: authentication required` | PAT expired | Renew PAT, update Secret |
| `argocd: permission denied` | RBAC policy chua allow | Check policy.csv + restart server |
| `SealedSecrets: key not found` | Sealing key mat | Restore tu backup |
| `SSO: invalid issuer` | Issuer URL sai | Kiem tra `oidc.config` issuer |
| `SSO: group claim empty` | `scopes` khong chua `groups` | Them scopes: '[groups]' |
| `ArgoCD: admin password invalid` | Chua doi mat khau mac dinh | `argocd account update-password` |
| `SecretStore: no such host` | AWS endpoint khong dung | Kiem tra region + endpoint URL |
