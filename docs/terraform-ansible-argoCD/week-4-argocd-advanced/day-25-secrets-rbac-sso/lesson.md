# Day 25 - Secrets Management, RBAC, SSO, Private Repo

## Header

**Module**: ArgoCD Advanced (Week 4)
**Day**: 25 / 35
**Topic**: Secrets Management, RBAC, SSO, Private Repo
**Prerequisite**: Day 17 (ArgoCD core), Day 22 (ApplicationSet), Day 24 (sync waves & hooks)
**Duration**: 2 tiếng (30 phút theory + 30 phút deep dive + 60 phút lab)

---

## 1. Muc tieu

- Phan biet 4 secret pattern cho GitOps: Sealed Secrets, SOPS, ESO, CSI
- Cau hinh ArgoCD RBAC bang declarative policy.csv va AppProject
- Hieu co che SSO/OIDC trong ArgoCD
- Quan ly private repo credentials bang declarative
- Chon duoc secret strategy phu hop theo team size va compliance context

---

## 2. Boi canh thuc te

### Pain: Secret hardcode trong Git

Khi commit `values.yaml` len Git, tat ca developer deu doc duoc secret:
- AWS access key trong Helm values
- Database password
- ArgoCD admin password

### 3 incident pho bien

| # | Incident | Hau qua |
|---|----------|---------|
| 1 | AWS access key commit public repo | Bi mining 30 phut, bill $5000 |
| 2 | DB password trong values.yaml | Dev nghi viec van con quyen doc 3 thang |
| 3 | ArgoCD admin mac dinh khong doi | Nhan su ngoai team enable destroy |

### Muc tieu Day 25

Build security baseline cho GitOps: secret safe-in-git + RBAC + SSO + private repo.

---

## 3. Kien thuc nen tang (~30 phut)

### 3.1 Tai sao Kubernetes Secret thuong KHONG du

```yaml
# Kubernetes Secret - chi la base64, KHONG phai ma hoa
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
type: Opaque
data:
  password: cGFzc3dvcmQxMjM=  # "password123" - bat ky ai cung doc duoc
```

**Han che cua Kubernetes Secret**:
- Base64 != encryption; `base64 -d` la 1 command
- etcd encryption-at-rest chi khi da cau hinh; attacker co RBAC van lay duoc
- Khong the commit len Git (toan bo data lo)
- Khong co audit trail khi doc secret
- Khong rotation mechanism built-in

### 3.2 4 cach quan ly secret + Git compatible

#### Pattern 1: Sealed Secrets (Bitnami)

**Y tuong**: Ma hoa cluster-side bang public key cluster. Manifest da duoc ma hoa co the commit len Git an toan.

```bash
# Ca doi tuong SealedSecret va secret da duoc ma hoa boi controller public key
# Private key nam trong cluster - KHONG bao gio commit len Git
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-creds
spec:
  encryptedData:
    password: AgA...  # Da ma hoa boi cluster public key
```

**Uu diem**: Ca manifest commit duoc, cluster-side decryption, khong can external store
**Nhuoc diem**: Mất sealing key cluster = mất tất cả secret; single point of failure

#### Pattern 2: SOPS + age/KMS

**Y tuong**: Mozilla SOPS ma hoa file YAML/JSON. Key co the la age (offline, 1 file) hoac cloud KMS.

```bash
# Tao key age
age-keygen -o age.key

# Ma hoa file values.yaml
sops --encrypt --age <AGE_PUB_KEY> --encrypted-regex '^(password|token|key)' values.yaml > values.enc.yaml

# ArgoCD plugin (kustomize-sops) decrypt khi render
```

**Uu diem**: Integration Kustomize/Helm native; cloud KMS audit log
**Nhuoc diem**: Leak age private key = leak all; CI/CD can luu key

#### Pattern 3: External Secrets Operator (ESO)

**Y tuong**: Pull tu external secret store (AWS Secrets Manager, Vault, ...). Manifest ExternalSecret chi la **reference**, khong co gia tri.

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: orders-db
spec:
  refreshInterval: 1h        # Tan suat sync
  secretStoreRef:
    name: aws-store
    kind: ClusterSecretStore  # Cluster-wide store
  target:
    name: orders-db          # Kubernetes Secret duoc tao
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: prod/orders/db    # Ten secret trong AWS Secrets Manager
      version: AWSCURRENT
```

```yaml
# SecretStore - khai bao ket noi den AWS Secrets Manager
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: aws-store
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: eso-sa           # IRSA - không can secret key
```

**Uu diem**: Rotation native; audit log cloud; centralized; IRSA khong can key
**Nhuoc diem**: External dependency; chicken-and-egg bootstrap

#### Pattern 4: CSI Secret Store Driver

**Y tuong**: Mount truc tiep tu provider thanh volume, khong qua Kubernetes Secret.

```yaml
# Pod su dung CSI mount
volumes:
- name: db-creds
  csi:
    driver: secrets-store.csi.k8s.io
    readOnly: true
    volumeAttributes:
      secretProviderClass: "aws-secrets"
```

**Uu diem**: Khong co Kubernetes Secret intermediary; strong consistency
**Nhuoc diem**: Pod-specific; phuc tap hon; khong dung duoc ArgoCD sync

### 3.3 ArgoCD RBAC

**2 layer RBAC**:

1. **Built-in roles**: `role:admin`, `role:readonly`, `role:edit`
2. **Custom policies**: `argocd-rbac-cm` ConfigMap

```yaml
# argocd-rbac-cm - declarative RBAC
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.default: role:readonly
  # scopes: '[groups, email]'  # OIDC group claim
  policy.csv: |
    g, my-org:platform-team, role:admin
    p, my-org:developers, applications, sync, default/*, allow
    p, my-org:developers, applications, delete, default/*, deny
```

**policy.csv format**: `p, subject, resource, action, object, effect`
**Group mapping**: `g, <group-claim>, <role>`

**AppProject - logical security boundary**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: apps
spec:
  sourceRepos:
  - 'https://github.com/org/gitops-apps'
  destinations:
  - namespace: team-a-*
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: '*'
    kind: '*'
  namespaceResourceBlacklist:  # Hoac whitelist
  - group: ''
    kind: Secret
  roles:
  - name: dev
    description: Dev team role
    policies:
    - p, proj:apps:dev, applications, *, apps/*, allow
    - p, proj:apps:dev, applications, delete, *, deny
```

**Local user account** (declarative):

```yaml
# argocd-cm
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  accounts.platform-admin: login   # Tạo local user
  accounts.platform-admin.tabs:    # Các tab user được thấy
    enabled: '*'
```

### 3.4 SSO Overview

ArgoCD bundling **Dex** la OIDC provider, ket noi:
- GitHub OAuth
- Google Workspace
- OIDC generic (Azure AD, Okta, Keycloak)
- SAML, LDAP

```yaml
# argocd-cm - SSO config
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  url: https://argocd.example.com
  oidc.config: |
    name: GitHub
    issuer: https://github.com
    clientID: <CLIENT_ID>
    clientSecret: $oidc.github.clientSecret  # Reference secret
    requestedScopes:
    - openid
    - profile
    - email
    - groups
```

**Group claim mapping**:

```yaml
# Trong argocd-rbac-cm
scopes: '[groups]'
policy.csv: |
  g, argocd-admins, role:admin
  g, platform-team, role:admin
  g, developers, role:readonly
```

### 3.5 Private Repo Credentials

**Declarative via Secret type `repository`**:

```yaml
# HTTPS token
apiVersion: v1
kind: Secret
metadata:
  name: gh-deploy-key
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  url: https://github.com/org/private-repo
  username: git
  password: ghp_<PAT_TOKEN>     # GitHub PAT

# SSH key
stringData:
  url: git@github.com:org/private-repo.git
  sshPrivateKey: |
    -----BEGIN OPENSSH PRIVATE KEY-----
    ...
    -----END OPENSSH PRIVATE KEY-----
```

**GitHub App** (recommended enterprise):
- Scoped per org/repo
- Expiring token (1 gio)
- Audit log nhu nhan vat

---

## 4. Deep dive & Trade-offs (~30 phut)

### 4.1 Bang so sanh 4 secret pattern

| Tieu chi | Sealed Secrets | SOPS+age | ESO | CSI |
|----------|---------------|----------|-----|-----|
| Storage location | Cluster | Git (encrypted) | External store | External store |
| Rotation | Manual redeploy | Re-encrypt | Auto (5m-1h) | Auto |
| Audit trail | Khong co | Cloud KMS | Full cloud log | Full |
| Disaster recovery | Backup seal key | Backup age key | Full | Full |
| Bootstrap complexity | Medium | Medium | High | Medium |
| External dependency | Khong | Khong | Co | Co |
| Cost | Free | Free | $0.40/secret/mo | $0.40/secret/mo |
| Best fit | Small team | Dev/offline | Cloud-native | Pod-level mount |

### 4.2 Best solution theo context

| Context | Recommended | Ly do |
|---------|-------------|-------|
| Ca nhan hoc tap | SOPS + age | Offline, 1 file key, khong cloud |
| Small team, khong cloud | Sealed Secrets | 1 controller, khong external |
| Startup AWS | ESO + AWS Secrets Manager + IRSA | Native rotation, khong key |
| Enterprise multi-cloud | ESO + HashiCorp Vault | Centralized, audit, HSM |
| Bank/regulated | HSM Vault + dual-control + signed commits | Compliance, hardware custody |

### 4.3 ArgoCD RBAC trade-off

- **Coarse-grained** (per project): Don gian, du cho 80% use case
- **Fine-grained** (per resource action): Phuc tap, dung khi can compliance
- **SSO group claim**: Map `groups` claim tu OIDC provider → ArgoCD role
- **Pitfall**: policy.csv khong auto-reload; can restart argocd-server
- **Test**: `argocd account can-i sync applications "apps/api-service"`

### 4.4 Private repo trade-off

| Method | Pros | Cons |
|--------|------|------|
| PAT | De setup | Tied to user; mat het khi user offboard |
| SSH key | De setup | Rotation pain; it audit |
| GitHub App | Scoped; expiring; audit | Phuc tap setup |

### 4.5 Pitfalls day 25

- Sealed Secrets: mat seal key cluster = mat tat ca encrypted secret
- SOPS: leak age private key = leak all
- ESO: SecretStore credentials cuong phai bao ve → IRSA recommended
- ArgoCD RBAC: policy.csv khong reload nhanh, can restart server
- SSO: group claim mismatch → user khong co quyen du dang da login
- **ArgoCD admin password mac dinh = name of argocd-server pod → MUST change**
- ESO chicken-and-egg: ESO can not start neu secret store can no khoi tao

---

## 5. Hands-on Lab (60 phut)

### Pre-req

```bash
kind create cluster --name gitops25
kubectl ns argocd
# Day 17, 22, 24 da hoan thanh
```

---

### Part A — ESO + Fake Provider (~15 phut)

**Step A1**: Cai ESO qua Helm (sync wave -10)

```yaml
# https://charts.external-secrets.io
# Cluster-scoped, nhung chi dung ClusterSecretStore
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-secrets
  namespace: argocd
spec:
  syncPolicy:
    automated:
      prune: true
    syncOptions:
    - CreateNamespace=true
  source:
    chart: external-secrets
    repoURL: https://charts.external-secrets.io
    targetRevision: "0.10.0"
    helm:
      valueFiles:
      - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: external-secrets
```

```yaml
# values/external-secrets.yaml
# Dung fake provider cho lab
# <PLACEHOLDER: full helm values voi image.tag, serviceMonitor, installCRDs=true>
```

**Step A2**: Tao Fake ClusterSecretStore

```yaml
# clusters/dev/external-secrets/store.yaml
# <PLACEHOLDER: ClusterSecretStore voi provider: fake, fake:
#   data:
#   - secretKey: db-password
#     remoteRef:
#       key: orders-db-password
#       secret: "super-secret-pass-123">
```

**Step A3**: Tao ExternalSecret reference

```yaml
# clusters/dev/external-secrets/orders-db-secret.yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: orders-db
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: fake-store
    kind: ClusterSecretStore
  target:
    name: orders-db
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: orders-db-password
```

**Step A4**: Apply + verify

```bash
kubectl apply -f clusters/dev/external-secrets/store.yaml
kubectl apply -f clusters/dev/external-secrets/orders-db-secret.yaml

# Kiem tra
kubectl get externalsecret orders-db
kubectl get secret orders-db -o yaml | grep password

# Demo rotation: update fake store value → ESO sync
# <PLACEHOLDER: kubectl annotate externalsecret orders-db
#   external-secrets.io/sync-policy=reconcile>
```

---

### Part B — ArgoCD RBAC Declarative (~15 phut)

**Step B1**: Apply RBAC policy

```yaml
# clusters/dev/argocd/rbac.yaml
# <PLACEHOLDER: argocd-rbac-cm ConfigMap voi:
#   policy.default: role:readonly
#   policy.csv:
#     g, dev-team, role:readonly
#     p, dev-team, applications, get, apps/*, allow
#     p, dev-team, applications, sync, apps/*, allow
#     g, platform-team, role:admin
#     p, platform-team, applications, *, platform/*, allow
#     g, sre-team, role:admin
#     p, sre-team, applications, *, *, allow>
```

**Step B2**: Tao local user

```yaml
# clusters/dev/argocd/accounts.yaml
# <PLACEHOLDER: argocd-cm patch voi:
#   accounts.dev-user: login
#   accounts.dev-user.enabled: "true"
#   accounts.platform-bot: login
#   accounts.platform-bot.enabled: "true"
#   accounts.platform-bot.capabilities: api-key>
```

**Step B3**: Test voi `argocd account can-i`

```bash
argocd account can-i sync applications "apps/api-service" "dev-team"
argocd account can-i delete applications "apps/api-service" "dev-team"
argocd account can-i sync applications "platform/cicd" "platform-team"
# Expected:
#   dev-team sync apps/* → yes
#   dev-team delete apps/* → no (implicit deny)
```

**Step B4**: AppProject voi roles + token

```yaml
# clusters/dev/argocd/project-apps.yaml
# <PLACEHOLDER: AppProject "apps" voi:
#   sourceRepos: ["https://github.com/org/gitops"]
#   destinations: [{namespace: "team-a-*", server: "*-cluster"}]
#   roles:
#     name: dev
#     policies: ["p, proj:apps:dev, applications, *, apps/*, allow"]
#   description: Token cho CI/CD, generate: kubectl argocd account generate-token
#   --account dev-ci -p apps>
```

---

### Part C — Private Repo Credentials (~15 phut)

**Step C1**: Tao Secret type `repository`

```yaml
# clusters/dev/argocd/repo-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: private-repo-credentials
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  url: https://github.com/org/private-gitops.git
  username: git
  password: ghp_<PLACEHOLDER_PAT>
```

**Step C2**: Apply + verify

```bash
kubectl apply -f clusters/dev/argocd/repo-secret.yaml
argocd repo list
# Kiem tra repo duoc add thanh cong
```

**Step C3**: Tao Application dung repo private

```yaml
# <PLACEHOLDER: Application "private-app" su dung source:
#   repoURL: https://github.com/org/private-gitops.git
#   path: ./app
#   destination: default cluster>
```

**Step C4**: GitHub App overview (khong can thuc hien day du)

```bash
# Setup GitHub App - cac buoc chinh:
# 1. GitHub org → Settings → Developer settings → GitHub Apps
# 2. Set webhook URL, permissions (repo: read)
# 3. Install vao org/repo
# 4. Tao Secret voi appID + privateKey
# <PLACEHOLDER: Chi tiết tai https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/>
```

---

### Part D — SSO Config Overview (~15 phut)

**Step D1**: SSO config (chi cau hinh, khong OAuth thuc)

```yaml
# clusters/dev/argocd/oidc.yaml
# <PLACEHOLDER: argocd-cm oidc.config:
#   name: GitHub
#   issuer: https://github.com
#   clientID: <PLACEHOLDER_CLIENT_ID>
#   clientSecret: $oidc.github.clientSecret  # ref Secret
#   requestedScopes: [openid, profile, email, groups]
# scopes: '[groups]'
# policy.csv: g, argocd-admins, role:admin>
```

**Step D2**: Group → role mapping

```yaml
# <PLACEHOLDER: tiep tuc argocd-rbac-cm:
#   g, platform-team, role:admin
#   g, readonly-users, role:readonly>
```

**Step D3**: Verify config

```bash
# Restart argocd-server de apply RBAC changes
kubectl rollout restart deployment argocd-server -n argocd
kubectl logs -n argocd deployment/argocd-server | grep "SSO"
# <PLACEHOLDER: kiem tra log hien thi " SSAO provider initialized">
```

---

### Cleanup

```bash
# Xoa lab resources
kubectl delete -f clusters/dev/external-secrets/
kubectl delete -f clusters/dev/argocd/rbac.yaml
kubectl delete -f clusters/dev/argocd/accounts.yaml
kubectl delete -f clusters/dev/argocd/repo-secret.yaml
# KHONG xoa argocd core - du dung cho Day 26
```

### Troubleshooting

| Issue | Check |
|-------|-------|
| ExternalSecret `SecretSynced=False` | `kubectl describe es <name>` → SecretStore not found |
| ExternalSecret pending forever | ESO pod running? `kubectl get pods -n external-secrets` |
| ArgoCD repo denied | Secret co label `argocd.argoproj.io/secret-type: repository`? |
| RBAC policy khong apply | `kubectl rollout restart deployment argocd-server -n argocd` |
| SSO login that bai | `kubectl logs -n argocd deploy/argocd-server` → OIDC error |

---

## 6. Kiem tra hieu bai

1. **Chon secret pattern**: Team 5 dev, khong AWS → chon Sealed Secrets hay ESO? Tai sao?

2. **Debug**: ExternalSecret co `SecretSynced=False` sau 30 phut → root cause checklist?

3. **ArgoCD RBAC**: Cau hinh de team A chi deploy duoc vao namespace `team-a-*`?

4. **Disaster recovery**: Cluster phuc hoi nhung mat seal key Sealed Secrets → recovery plan?

5. **Refactor**: Chuyen 50 secret tu values.yaml (helm-secrets/SOPS) sang ESO →cac buoc?

---

## 7. Tom tat cuoi ngay

**Key takeaway**: Secret trong GitOps can duoc bao ve 3 lop:
1. **Encryption** (SOPS, Sealed Secrets, ESO) - gia tri khong the doc
2. **Access control** (ArgoCD RBAC, AppProject) - ai duoc phep lam gi
3. **Authentication** (SSO, private repo credentials) - ai duoc phep dang nhap

**Solution decision tree**:
```
Co AWS?
├─ Co: ESO + AWS Secrets Manager + IRSA
└─ Khong:
   ├─ Startup: ESO + Vault (hoac Sealed Secrets neu nho)
   └─ Hoc tap: SOPS + age
```

**Day 26 tiep theo**: Argo Rollouts - progressive delivery, blue/green, canary.

---

## 8. Tham khao

- External Secrets Operator: https://external-secrets.io/latest/
- ArgoCD RBAC: https://argo-cd.readthedocs.io/en/stable/user-management/rbac/
- ArgoCD SSO: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/
- Bitnami Sealed Secrets: https://github.com/bitnami-labs/sealed-secrets
- Mozilla SOPS: https://github.com/mozilla/sops
- ArgoCD Private Repos: https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/
