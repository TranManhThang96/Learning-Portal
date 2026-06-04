# Day 23 - ApplicationSet Advanced: Cheat Sheets & Reference

## 1. Generator Combination Decision Tree

```
Co the gap bao nhieu chieu thay doi (dimensions)?
  |
  v
1 chieu --> List / Git Directory / Git File / Cluster generator
  |
2 chieu
  + Tat ca cac combination deu can (fully cartesian) --> MATRIX generator
  + Chi mot so combination, co gia tri base + override --> MERGE generator
  + Cac chieu doc nhau, khong chia se gia tri --> MATRIX
  + Cac chieu co gia tri chung, muon ghi de --> MERGE
  |
  v
Nhieu hon 2 generators --> Long noc MATRIX (workaround) hoac chia nhieu ApplicationSet
```

## 2. Matrix vs Merge Cheat Sheet

### Matrix Generator (Cartesian Product)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: matrix-git-cluster
spec:
  generators:
    - matrix:
        generators:
          - git:                        # Generator #1: danh sach services
              repoURL: https://github.com/org/apps-repo.git
              revision: HEAD
              directories:
                - path: services/*
          - clusters:                  # Generator #2: danh sach cluster
              selector:
                matchLabels:
                  env: '[[ .Values.targetEnv ]]'
  template:
    metadata:
      name: '{{path.basename}}-{{name}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/apps-repo.git
        targetRevision: HEAD
        path: '{{path}}/overlays/{{metadata.labels.env}}'
      destination:
        server: '{{server}}'
        namespace: '{{path.basename}}'
```

**Ket qua**: 3 services x 2 clusters = 6 Applications

### Merge Generator (Join + Override)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: merge-base-override
spec:
  generators:
    - merge:
        mergeKeys:
          - name                        # Khoa unique de merge
        generators:
          - git:                        # Base config tu Git
              repoURL: https://github.com/org/config-repo.git
              revision: HEAD
              files:
                - path: configs/base.yaml
          - list:                       # Override per environment
              elements:
                - name: dev
                  replicas: 1
                  memoryLimit: 512Mi
                - name: staging
                  replicas: 2
                  memoryLimit: 1Gi
                - name: prod
                  replicas: 3
                  memoryLimit: 2Gi
  template:
    spec:
      source:
        - repoURL: https://github.com/org/apps-repo.git
          targetRevision: HEAD
          path: app
          helm:
            parameters:
              - name: replicas
                value: '{{values.replicas}}'
              - name: memoryLimit
                value: '{{values.memoryLimit}}'
      destination:
        server: '{{server}}'
        namespace: default
```

**mergeKeys** phai ton tai trong tat ca cac generator output.

## 3. Cluster Registration Cheat Sheet

### Declarative Cluster Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cluster-us-east
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: cluster
    env: prod
    region: us-east
    compliance: soc2
type: Opaque
stringData:
  name: us-east-prod
  server: https://us-east.k8s.example.com
  config: |
    {
      "bearerToken": "<token>",
      "tlsClientConfig": {
        "insecure": false,
        "caData": "<base64-ca>"
      }
    }
```

### Imperative Registration

```bash
argocd cluster add kind-dev --label env=dev --label region=local
argocd cluster add kind-staging --label env=staging --label region=local
```

### Verify Clusters

```bash
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster
argocd cluster list
```

### Label Clusters for Filtering

```bash
kubectl label secret cluster-us-east env=prod --namespace argocd
kubectl label secret cluster-us-east region=us-east --namespace argocd
kubectl label secret cluster-us-east gdpr-required=true --namespace argocd
```

## 4. Multi-Cluster Topology Comparison

```
Topology          | Pros                          | Cons
------------------|-------------------------------|---------------------------
Hub & Spoke       | 1 ArgoCD duy nhat, de quan ly | Hub lai chet => tat ca
(1 ArgoCD hub)    | tat ca cluster deu cung cau   | deu bi; hub can nhieu
                  | Config cluster 1 lan, APPLY   | resource; cross-region
                  | 1 lan cho tat ca               | latency
------------------|-------------------------------|---------------------------
Federated          | Cluster doc lap, khong phu   | Lap lai config nhieu lan;
(1 ArgoCD/cluster)| thuoc hub; network latency   | khong co view tong; blast
                  | thap; blast radius local     | radius khi thay doi base
------------------|-------------------------------|---------------------------
Agent-based        | Giai quyet hub chet; scaled  | Agent phai secure; them
(ArgoCD Agent)    | ra; hub nhe                   | infrastructure; complex
```

**Recommendation**:
- < 10 cluster + cung datacenter: Hub & Spoke
- > 10 cluster + nhieu region: Federated hoac Agent-based
- Multi-region voi compliance khac nhau: Federated per region

## 5. Naming Convention Reference

### Limits

| Object        | Limit       | Notes                                  |
|---------------|-------------|----------------------------------------|
| Application   | 253 chars   | DNS name limit (Kubernetes object)     |
| Label value   | 63 chars    | Kubernetes label limit                 |
| Label key     | 63 chars    | Prefixed keys: 253 - prefix(6) = 247  |
| Kustomize     | 253 chars   | Name prefix + base + suffix            |

### Reserved Characters

```
Application name:  a-z0-9- (khong co . / $ { } )
Template var:      {{name}} hoac $name trong helm
```

### Recommended Patterns

```
# Don gian, tranh collision
'{service}-{env}-{cluster}'
VD: 'api-prod-us-east'   (18 chars - OK)

# Neu co nhieu environment
'{service}-{envShort}-{regionShort}'
VD: 'api-p-us'           (9 chars - rat ngan)

# Co team prefix
't{team}-{service}-{env}-{region}'
VD: 'tpay-api-p-us'      (13 chars - OK)

# Merge-based: 1 App per service, cluster trong label
'{service}'
# Ket hop values.replicas tu merge de phan biet env
```

### Cluster Values Per-Environment

```yaml
generators:
  - clusters:
      values:
        replicas: '1'
        memoryLimit: '512Mi'
      selector:
        matchLabels:
          env: dev
  - clusters:
      values:
        replicas: '3'
        memoryLimit: '4Gi'
      selector:
        matchLabels:
          env: prod
```

## 6. Scale Tuning Checklist

```yaml
# 1. Tang controller replicas
apiVersion: v1
kind: Deployment
metadata:
  name: argocd-applicationset-controller
  namespace: argocd
spec:
  replicas: 3    # Mac dinh 1; tang khi > 200 Applications

---
# 2. Sharding ( enterprises, > 500 Applications)
# Dung ApplicationSet Controller sharding
# spec.shardReplicas: 2

---
# 3. Resource limits
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: '2'
    memory: 2Gi

---
# 4. Reconciliation interval
# spec.reconcileRate:
#   slow: 10m
#   normal: 3m (default)
#   fast: 30s

---
# 5. App exclusion selectors
# Chi tao Application cho nhung cluster/env can thiet
spec:
  generators:
    - matrix:
        generators:
          - clusters:
              selector:
                matchExpressions:
                  - key: argocd.argoproj.io/managed-by
                    operator: In
                    values:
                      - hub-cluster
```

## 7. Anti-Patterns Checklist

- [ ] `clusters: {}` khong co selector = tat ca cluster, ke ca in-cluster (self) => tao Application tro ve chinh ArgoCD
- [ ] mergeKeys trung lap trong 2 generator output => ApplicationSet stuck
- [ ] Matrix gen khong co gia tri tu 1 trong 2 generators => khong tao Application nao (silent fail)
- [ ] Xoa cluster secret => tat ca Application cua cluster do bi xoa ngay lap tuc
- [ ] Ten Application qua dai (> 253 chars) => Kubernetes tao that bai
- [ ] Label value qua dai (> 63 chars) => bi cat hoac loi
- [ ] Nested matrix (matrix trong matrix) khong ho tro chinh thuc
- [ ] Git generator path trung nhau giua cac generator con => duplicate Application
- [ ] Khong dung `matchLabels` cho cluster secret type => cluster khong duoc nhan dien
- [ ] dung `$` trong Application name thay vi `{<!-- -->{}}` => template khong duoc resolve
- [ ] Hub ArgoCD mat network den spoke cluster => Application o trang thai Unknown
- [ ] Cluster secret config sai => Application o trang thai Unknown, khong debug duoc
- [ ] Qua nhieu Application (> 1000) ma khong tang controller replicas => CPU spike
- [ ] Khong dat project cho ApplicationSet => dung default project, violation separation
- [ ] Matrix voi generator chua tra ve gia tri nao (empty list) => tao 0 Application

## 8. Common Errors Reference Table

| Error / Symptom                            | Nguyen Nhan Thuong Gap                    | Cach Khac Phuc                          |
|--------------------------------------------|-------------------------------------------|-----------------------------------------|
| ApplicationSet nam nhung Application 0     | Mot trong 2 generators tra ve empty list  | Debug: bo sung generator output ando log |
| Merge: khong merge duoc                    | mergeKeys khong ton tai trong ca 2 output | Kiem tra mergeKeys = truong ton tai trong tat ca |
| Too many Applications (>500)               | Khong loc cluster, khong loc service      | them matchLabels selector, shard        |
| Application name > 253 chars               | Template name qua dai                     | Rut ngan: vi du `{svc}-{env}-{clus}`   |
| Cluster khong xuat hien trong generator    | Secret thieu label argocd.argoproj.io/..  | them label dung                       |
| App tao ra nhung khong deploy duoc         | Hub mat network spoke                     | kiem tra cluster secret config          |
| ApplicationSet bi stuck, khong update       | mergeKeys conflict                        | debug mergeKeys, kiem tra unique        |
| Matrix tao thieu 1/4 combination           | Mot generator con trong matrix co gia tri  | debug tung generator rieng le            |
| xoa cluster => mat ca Application          | Hanh vi mac dinh cua ApplicationSet       | Backup: tat tien ich Cluster generator, |
|                                             |                                           | dung List thay the                      |
