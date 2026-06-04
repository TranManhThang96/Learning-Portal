# Day 23 - ApplicationSet Advanced: Matrix, Merge, Multi-Cluster

## Muc Tieu

- Hieu ro su khac biet giua Matrix generator (cartesian product) va Merge generator (join + override)
- Thiet ke ApplicationSet cho multi-cluster GitOps: 1 ArgoCD hub -> nhieu spoke cluster
- Ap dung Cluster generator voi labels va values de truyen config theo cluster
- Nhan dien va tranh cac anti-patterns khi scale den 100+ Applications
- Debug ApplicationSet khi no sinh ra so luong Application khong nhu expected

---

## 1. Boi Canh Thuc Te

### Pain Point tu Day 22

Day 22 da hoc: List, Git Directory, Git File, Cluster generator. Moi generator giai quyet 1 chieu thay doi. Nhung thuc te:

```
5 services  (api, worker, frontend, auth, notif)
x 3 envs    (dev, staging, prod)
x 3 regions (us-east, eu-west, ap-southeast)
= 45 Applications
```

Day 22: tao 45 Application bang cach nao? **Khong the** voi 1 generator don. Phai tao 15 ApplicationSet, moi ApplicationSet lai phai list 3 cluster? Rat cu phap, rat kho bao tri.

### Real Scenario: Team Chuyen sang Multi-Cluster

Mot team tu single-region kind cluster chuyen sang multi-cluster:

```
Truoc: 1 kind cluster, 3 namespace (dev/staging/prod)
Sau:   3 regional clusters x 3 envs = 9 deployment target
       us-east-prod    eu-west-prod    ap-southeast-prod
       us-east-staging  eu-west-staging ap-southeast-staging
       us-east-dev     eu-west-dev     ap-southeast-dev
```

Voi 5 services -> 45 Application can deploy. Dung Matrix generator: **1 ApplicationSet** thay vi 45 ApplicationSet rieng le.

---

## 2. Kien thuc nen tang - 30 phut: Matrix Generator

### Khai Niem

Matrix generator la cartesian product cua 2 child generators. Moi Application duoc tao = 1 phan tu tu generator #1 nhan voi 1 phan tu tu generator #2.

```
Generator A: [svc-api, svc-worker, svc-frontend]  (3 items)
Generator B: [cluster-dev, cluster-prod]           (2 items)
Matrix: 3 x 2 = 6 Applications
```

### Cu Phap

```yaml
generators:
  - matrix:
      generators:
        - <generator-1>   # child dau tien
        - <generator-2>   # child thu hai
```

### Vi Du Day 23: Services x Clusters

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: matrix-services-clusters
spec:
  generators:
    - matrix:
        generators:
          - git:                                    # Chieu 1: danh sach services
              repoURL: https://github.com/org/apps-repo.git
              revision: HEAD
              directories:
                - path: services/*
          - clusters:                              # Chieu 2: danh sach cluster
              selector:
                matchLabels:
                  argocd.argoproj.io/secret-type: cluster
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

Template field tu generator #1: `{<!-- -->{path.basename}}` (ten thu muc)
Template field tu generator #2: `{<!-- -->{name}}`, `{<!-- -->{server}}` (ten cluster, server URL)

### Gioi Han Quan Trong

- **Chi dung 2 child generators**. Khong ho tro `matrix` long nhau (khong co nested matrix chinh thuc). Giai phap: ket hop matrix voi git generator con nhieu path.
- **Neu 1 trong 2 child tra ve empty list**: 0 Application duoc tao (silent — kiem tra controller log).
- **Field trung ten**: field tu child thu 2 ghi de field tu child thu 1.

---

## 3. Merge Generator

### Khai Niem

Merge generator ket hop data tu nhieu generators theo `mergeKeys` (join trong SQL terms). Neu key trung nhau, generator o duoi ghi de generator o tren.

```
Merge order: bottom-to-top override
Generator 1 (base):    {name: "api", replicas: 1, image: "v1.0"}
Generator 2 (override):{name: "api", env: "prod"}
Ket qua merge:        {name: "api", replicas: 1, image: "v1.0", env: "prod"}
```

### Khac Biet voi Matrix

| Thuoc tinh            | Matrix                          | Merge                           |
|----------------------|---------------------------------|---------------------------------|
| So luong Application | Cartesian product (A x B)       | Join theo key (A left join B)   |
| Field trung lap      | Ghi de (child #2 > child #1)    | Ghi de (bottom > top)           |
| Use case chinh       | Tat ca combination deu can      | Base + partial override         |
| mergeKeys            | Khong can                        | Bat buoc, phai unique           |

### Vi Du: Base Config + Per-Env Override

```yaml
generators:
  - merge:
      mergeKeys:
        - name                    # Khoa unique: ten service
      generators:
        - git:                    # Base values tu Git (replicas, limits)
            repoURL: https://github.com/org/config-repo.git
            revision: HEAD
            files:
              - path: base/services.yaml
        - list:                   # Override per env
            elements:
              - name: api
                env: dev
                replicas: 1
              - name: api
                env: prod
                replicas: 5
              - name: worker
                env: prod
                replicas: 3
```

### Gioi Han Quan Trong

- `mergeKeys` phai ton tai trong **tat ca** cac generator output. Mat 1 key -> merge that bai, ApplicationSet bi stuck.
- mergeKeys phai unique trong tung generator. 2 entry cung `name` trong 1 generator -> conflict.
- Merge chi replace top-level field, khong deep merge (nested object bi thay the toan bo).

---

## 4. Cluster Generator Nang Cao

### Selector voi Labels

```yaml
generators:
  - clusters:
      selector:
        matchLabels:
          env: prod
          region: us-east
```

### Values Per Cluster

```yaml
generators:
  - clusters:
      values:
        replicas: '1'
      selector:
        matchLabels:
          env: dev
  - clusters:
      values:
        replicas: '5'
        autoscaling: 'true'
      selector:
        matchLabels:
          env: prod
```

Trong template: `{<!-- -->{values.replicas}}`, `{<!-- -->{values.autoscaling}}`

### Multi-Cluster GitOps: Hub & Spoke

```
+---------------------------+
|       ArgoCD Hub          |
|   (management cluster)    |
|   1x ArgoCD install       |
|   cluster secret -> spoke |
+---------------------------+
    |          |          |
    v          v          v
+------+ +--------+ +-------------+
|us-east| |eu-west | |ap-southeast|
|prod   | |prod    | |prod        |
+------+ +--------+ +-------------+
```

Cluster secret khai bao declarative:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cluster-us-east-prod
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: cluster
    env: prod
    region: us-east
type: Opaque
stringData:
  name: us-east-prod
  server: https://us-east.k8s.example.com
  config: |
    { "bearerToken": "...", "tlsClientConfig": { ... } }
```

---

## 5. Diagram: Matrix vs Merge Data Flow

```
MATRIX (Cartesian Product)
==========================
Generator A: [svc-api, svc-worker]
Generator B: [cluster-dev, cluster-prod]

Matrix output:
  {path.basename: api,     name: dev}    --> Application: api-dev
  {path.basename: api,     name: prod}   --> Application: api-prod
  {path.basename: worker, name: dev}    --> Application: worker-dev
  {path.basename: worker, name: prod}   --> Application: worker-prod

MERGE (Join theo mergeKeys)
===========================
Generator A (base):
  {name: api,     replicas: 1, image: v1}
  {name: worker, replicas: 1, image: v1}
Generator B (override):
  {name: api,     env: prod, replicas: 5}
  {name: worker,  env: prod, replicas: 3}

mergeKeys: [name]
Merge output:
  {name: api,     replicas: 5, image: v1, env: prod}   --> Application: api
  {name: worker,  replicas: 3, image: v1, env: prod}  --> Application: worker
```

---

## 6. Deep Dive & Trade-offs - 30 phut: Generator Decision Tree

```
|____ 1 chieu thay doi (services hoac clusters hoac envs)
      --> Don generator: List / Git Directory / Git File / Cluster

|____ 2+ chieu thay doi
      |
      +-- Tat ca combination deu can? (services x envs x clusters)
      |   --> MATRIX generator
      |   Vi du: 3 services x 2 clusters = 6 Applications, deu can
      |
      +-- Chi mot so combination, co base config chung
          --> MERGE generator
          Vi du: base replicas=1 cho tat ca, nhung prod override=5
```

### Multi-Cluster Patterns

**1. Hub & Spoke (recommended < 10 clusters)**

- 1 ArgoCD hub quan ly tat ca spoke cluster
- Khu vuot: hub chet -> tat ca mat GitOps
- Tang controller replicas cho HA

**2. Federated (10+ clusters, compliance khac nhau)**

- 1 ArgoCD per cluster
- Loi: config base phai sync nhieu noi, khong co view tong
- Loi: khi thay doi base, phai apply nhieu lan

**3. Agent-based (ArgoCD Agent)**

- Hub nhe, agent nho chay tren spoke
- Giai quyet hub chet, scaled hon Hub & Spoke
- Thuc hien khi co > 50 clusters

### Naming Convention o Scale

| Pattern             | Vi du                  | Uu/Nhuoc            |
|---------------------|------------------------|---------------------|
| `{svc}-{env}-{clus}`| api-prod-us-east       | Ngan, ro rang       |
| `{team}-{svc}-{e}-{r}`| tpay-api-p-us        | Co team prefix      |
| `{svc}` (merge)     | api                    | Ngan, can them label|

 Gioi han Kubernetes: Application name <= 253 chars, label value <= 63 chars.

### Scale Issue

- **500+ Application**: ApplicationSet controller render time tang, CPU spike
- **Giai phap**: tang `replicas: 3` cho controller; shard ApplicationSet
- **App exclusion**: dung selector de loc cluster, khong tao Application cho cluster khong can
- **Network**: hub-spoke latency khi cluster xa nhau, neu > 200ms thi可以考虑 federation

---

## 7. Hands-on Lab

**Pre-requisites**: kind cluster chay ArgoCD, Applications da co tu Day 22.

### Setup: Multi-Cluster Simulation

**Cach 1 (recommended)**: Tao 2 kind cluster

```bash
kind create cluster --name kind-dev    --context kind-dev
kind create cluster --name kind-staging --context kind-staging
argocd cluster add kind-dev    --label env=dev    --label region=local
argocd cluster add kind-staging --label env=staging --label region=local
```

**Cach 2** (neu RAM < 8GB): 1 cluster, nhieu namespace gia dinh

```bash
kubectl create ns staging-ns
# Khong tao cluster secret; dung cluster generator voi namespace thay vi cluster
# Chu y: day chi mo phong, gioi han khi debug cluster-level issue
```

### Buoc 1: Verify Cluster Secret

```bash
kubectl get secret -n argocd -l argocd.argoproj.io/secret-type=cluster \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels}{"\n"}{end}'
```

Duy nhat 2 secret: `kind-dev`, `kind-staging` (hoac ten tuong ung).

### Buoc 2: Lab Matrix Generator

**Cau truc apps-repo can co:**

```
apps-repo/
  services/
    api/
      base/
        kustomization.yaml
        deployment.yaml
      overlays/
        dev/kustomization.yaml
        prod/kustomization.yaml
    worker/base/...
    frontend/base/...
```

**Tao ApplicationSet Matrix:**

```yaml
# matrix-appset.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: matrix-services-clusters
spec:
  generators:
    - matrix:
        generators:
          - git:
              repoURL: https://github.com/org/apps-repo.git
              revision: HEAD
              directories:
                - path: services/*
          - clusters:
              selector:
                matchLabels:
                  argocd.argoproj.io/secret-type: cluster
  template:
    metadata:
      name: '{{path.basename}}-{{name}}'
      labels:
        app: '{{path.basename}}'
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

```bash
kubectl apply -f matrix-appsets.yaml
# Quan sat: 3 services x 2 clusters = 6 Applications
argocd app list
kubectl get application -n argocd
```

### Buoc 3: Lab Merge Generator

**config-repo chua base config:**

```yaml
# configs/base.yaml
replicas: 1
memoryLimit: 512Mi
imageTag: v1.0
```

**Override config per env:**

```yaml
# override.yaml (git generator, path khac)
replicas: 3
memoryLimit: 2Gi
imageTag: v1.2
```

**ApplicationSet Merge:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: merge-services-override
spec:
  generators:
    - merge:
        mergeKeys:
          - path.basename
        generators:
          - git:
              repoURL: https://github.com/org/config-repo.git
              revision: HEAD
              files:
                - path: configs/base.yaml
          - list:
              elements:
                - path.basename: api
                  replicas: 2
                  memoryLimit: 1Gi
                - path.basename: worker
                  replicas: 4
                  memoryLimit: 4Gi
  template:
    metadata:
      name: '{{path.basename}}-config'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/apps-repo.git
        targetRevision: HEAD
        path: '{{path.basename}}'
        helm:
          parameters:
            - name: replicas
              value: '{{values.replicas}}'
            - name: memoryLimit
              value: '{{values.memoryLimit}}'
            - name: imageTag
              value: '{{values.imageTag}}'
      destination:
        server: '{{server}}'
        namespace: default
```

Apply va kiem tra ket qua: moi service co 1 Application voi merged values.

### Buoc 4: Cluster Generator voi Values

**Tao 2 cluster secret voi labels khac nhau:**

```bash
# Neu dung kind cluster cua minh, them label
kubectl label secret kind-dev env=dev --namespace argocd
kubectl label secret kind-staging env=staging --namespace argocd
```

**ApplicationSet voi values per cluster:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-values-demo
spec:
  generators:
    - clusters:
        values:
          replicas: '1'
        selector:
          matchLabels:
            env: dev
    - clusters:
        values:
          replicas: '3'
          autoscaling: 'true'
        selector:
          matchLabels:
            env: staging
  template:
    metadata:
      name: demo-{{name}}
    spec:
      project: default
      source:
        repoURL: https://github.com/org/demo-app.git
        targetRevision: HEAD
        path: app
        helm:
          parameters:
            - name: replicaCount
              value: '{{values.replicas}}'
            - name: autoscaling.enabled
              value: '{{values.autoscaling}}'
      destination:
        server: '{{server}}'
        namespace: demo
```

### Buoc 5: Naming Convention Refactor

**Van de**: Ten `service-environment-cluster` dai 30+ chars, chan chan 63-chars label limit.

**Giai phap**: Dung `nameSuffix` trong template + rut ngon cluster name

```yaml
# Thay vi: name: '{{path.basename}}-{{metadata.labels.env}}-{{name}}'
# -> 25+ chars voi cluster name dai

# Rut ngan:
template:
  metadata:
    name: '{{path.basename}}-{{values.envShort}}-{{values.regionShort}}'
  spec:
    source:
      helm:
        parameters:
          - name: environment
            value: '{{values.envShort}}'
```

```yaml
# List generator override values
generators:
  - merge:
      mergeKeys:
        - path.basename
      generators:
        - git: ...
        - list:
            elements:
              - path.basename: api
                envShort: d
                regionShort: us
              - path.basename: api
                envShort: p
                regionShort: us
```

### Buoc 6: Scale Test

**Mo phong**: Them 5 services x 3 envs x 2 clusters = 30 Application.

```bash
# Them 5 service directory vao apps-repo/services/
# Tao 1 env moi (uat) trong cluster labels

kubectl label secret kind-staging env=uat --namespace argocd
# Cap nhat ApplicationSet de include uat

# Quan sat controller
kubectl logs -n argocd deploy/argocd-applicationset-controller --tail=50

# Doi 1-2 phut, kiem tra so Application
argocd app list | wc -l
```

Neu > 50 Applications: kiem tra render time trong controller log.

### Buoc 7: Disaster Scenario

```bash
# Xoa cluster secret (simulate cluster remove)
kubectl delete secret kind-staging -n argocd

# Quan sat: Application cua kind-staging bi xoa ngay
argocd app list  # thay so luong giam

# Recovery: re-register cluster
argocd cluster add kind-staging --label env=staging --label region=local
# Application tuong lai duoc tao lai
```

### Cleanup

```bash
kubectl delete -f matrix-appsets.yaml
kubectl delete -f merge-appsets.yaml
kubectl delete -f cluster-values-demo.yaml
# Khong xoa cluster secret neu van can cho Day 24
kind delete cluster --name kind-dev
kind delete cluster --name kind-staging
```

### Troubleshooting

```bash
# 1. Xem rendered Application tu ApplicationSet
argocd appset get matrix-services-clusters

# 2. Xem ApplicationSet controller log
kubectl logs -n argocd deploy/argocd-applicationset-controller -f

# 3. Debug generator output
kubectl get applicationset matrix-services-clusters -n argocd -o yaml
# Tim phan: status.conditions

# 4. Check审批: Application bi stuck o trang thai nao?
argocd app list --selector app=api

# 5. Neu Application khong sync duoc
argocd app get <app-name> --show-pod
```

---

## 8. Kiem Tra Hieu Bai

**Cau 1**: Ban co 6 services x 4 envs x 2 regions = 48 Application. Dung generator nao? Tai sao khong dung 1 don generator?

**Cau 2**: Mo ta su khac biet giua Matrix va Merge generator. Cho vi du use case cho tung loai.

**Cau 3**: Neu dung `clusters: {}` (khong selector), đieu gi se xay ra? Lam sao tranh?

**Cau 4**: Ban co 100 services x 5 envs x 4 clusters = 2000 Application. Hub ArgoCD dang chay cham. Ke ten 3 phuong an va noi tai sao?

**Cau 5**: Refactor: ban dang co 4 ApplicationSet rieng le (1 cho moi env), moi ApplicationSet deu list 10 cluster. Lam sao gop thanh 1 ApplicationSet matrix ma van giu duoc per-cluster config khac nhau?

---

## 9. Tom Tat Ngay 23

| Chu de                     | Key Takeaway                                    |
|----------------------------|-------------------------------------------------|
| Matrix generator           | Cartesian product, chi 2 child, 0 neu 1 empty   |
| Merge generator            | Join + override, can mergeKeys unique, bottom-up |
| Cluster generator          | Labels + values per cluster, selector required  |
| Multi-cluster GitOps       | Hub & Spoke < 10 cluster, Federation > 10       |
| Naming convention         | < 253 chars app name, < 63 chars label value    |
| Scale                     | Tang controller replicas, shard, selector loc    |
| Anti-patterns              | clusters: {}, mergeKeys conflict, nested matrix |

**Next**: Day 24 — Sync Waves & Hooks: cross-cutting deployment logic, PreSync/Sync/PostSync hook, Data migration.

---

## 10. Tham Khao

- [ArgoCD ApplicationSet Generators](https://argocd-applicationset.readthedocs.io/en/stable/Generators-Matrix/)
- [Matrix Generator](https://github.com/argoproj/applicationset/blob/master/docs/Generators-Matrix.md)
- [Merge Generator](https://github.com/argoproj/applicationset/blob/master/docs/Generators-Merge.md)
- [Cluster Generator](https://github.com/argoproj/applicationset/blob/master/docs/Generators-Cluster.md)
- [Template Reference](https://github.com/argoproj/applicationset/blob/master/docs/Template.md)
- [ApplicationSet Controller Scaling](https://argocd-applicationset.readthedocs.io/en/stable/Controller/)
