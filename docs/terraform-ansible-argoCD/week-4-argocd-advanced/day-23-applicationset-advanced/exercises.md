# Day 23 - Exercises: ApplicationSet Advanced

## General Instructions

- Docs: `../day-23-applicationset-advanced/document.md`
- Lab environment: kind cluster + ArgoCD nhu Day 22
- Tao thu muc `exercises/` trong apps-repo de mo phong cau truc
- Debug voi: `argocd appset get <name>`, `kubectl logs -n argocd deploy/argocd-applicationset-controller`

---

## Exercise 1: Thiết ke ApplicationSet cho 96 Application

### Scenario

Ban co:
- **8 microservices**: api-gateway, user-service, order-service, payment-service, notification-service, analytics-service, search-service, cache-service
- **4 environments**: dev, uat, staging, prod
- **3 regional clusters**: us-east-1, eu-west-1, ap-southeast-1
- **Tong**: 8 x 4 x 3 = **96 Applications**

### Yêu cầu

1. Đề xuất so luong ApplicationSet va cau truc. Tai sao?

2. Viet YAML cho 1 ApplicationSet chinh (dung Matrix generator).

3. Môi truong prod can cau hinh khác biệt: replicas=5, autoscaling=true, memoryLimit=4Gi. Dung gi de achieve? Merge hay matrix? Viet YAML snippet.

4. Đặt ten cho cac Application. Đảm bao:
   - Application name <= 253 chars
   - Label value <= 63 chars
   - Khong trung lap (unique)

### Deliverable

File: `exercises/ex1-96apps-design.yaml` — ApplicationSet YAML hoan chinh.

---

## Exercise 2: Merge Generator cho EU GDPR Compliance

### Scenario

Team EU requires GDPR sidecar container cho tat ca services, nhung US/Asia khong.

```
Services: 5 (api, worker, frontend, auth, notif)
Clusters: 3 (eu-west-1-prod, us-east-1-prod, ap-southeast-1-prod)
```

### Yêu cầu

1. Dung Merge generator de mo phong:
   - Base config: tat ca service deu co `replicas: 3`, `imageTag: v1.2`
   - EU cluster override: them `gdprSidecar: true`, `replicas: 5`
   - US/Asia cluster: khong co override

2. Co the dung Matrix thay Merge cho scenario nay khong? Tai sao?

3. Neu co them requirement: AP cluster can `memoryLimit: 8Gi` (nhu EU), EU can `auditLog: true`, dung Merge lam sao?

### Deliverable

File: `exercises/ex2-merge-gdpr.yaml` — ApplicationSet YAML voi day du 3 generators (base + EU + AP).

---

## Exercise 3: Debug Matrix Generator — Missing Combination

### Scenario

Ban apply ApplicationSet nhu sau nhung chi thay 4 Application thay vi 6.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: debug-matrix
spec:
  generators:
    - matrix:
        generators:
          - git:
              repoURL: https://github.com/org/apps-repo.git
              revision: HEAD
              directories:
                - path: services/api
                - path: services/worker
          - clusters:
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
        path: '{{path}}'
      destination:
        server: '{{server}}'
        namespace: default
```

Cluster list: kind-dev, kind-staging, in-cluster (ArgoCD's own cluster).

### Yêu cầu

1. Tai sao chi co 4 Application thay vi 6?
2. Debug step-by-step: tim root cause bang cach nao?
3. Fix YAML de chi tao 4 Application dung (loai bo in-cluster).
4. Neu `in-cluster` la cluster production thuc su, thi phai xu ly nao?

### Deliverable

File: `exercises/ex3-debug-matrix.md` — Ghi ro step debug va YAML fix.

---

## Exercise 4: Naming Convention Review & Refactor

### Scenario

Ban viet ApplicationSet voi ten:

```yaml
template:
  metadata:
    name: '{{metadata.labels.team}}-{{path.basename}}-{{metadata.labels.environment}}-{{name}}'
    labels:
      app.kubernetes.io/name: '{{metadata.labels.team}}-{{path.basename}}-{{metadata.labels.environment}}-{{name}}'
      app.kubernetes.io/managed-by: argocd
```

Team name: "platform-engineering-team" (24 chars)
Service: "payment-gateway-service" (24 chars)
Env: "staging-environment" (18 chars)
Cluster: "us-east-1-production-cluster" (30 chars)

### Yêu cầu

1. Tinh do dai Application name va label value. Co vuot qua gioi han khong?

2. Đề xuât 2 phuong an rut ngan:
   - Phuong an A: rut ngan tat ca components (khong mat thong tin)
   - Phuong an B: chi rut ngan 1-2 components, giai thich lua chon

3. Viet lai YAML cho ca 2 phuong an.

4. Neu phai support 100+ services, dat ten gi de dam bao uniqueness ma van ngan?

### Deliverable

File: `exercises/ex4-naming-refactor.yaml` — YAML refactored voi 2 phuong an.

---

## Exercise 5: Migrate Hub ArgoCD qua tai

### Scenario

Hub ArgoCD dang qua tai voi thong so:
- **800 Applications** tu 15 ApplicationSet
- **8 regional clusters**, tat ca qua hub
- Hub cluster: 4 CPU cores, 8Gi RAM
- Controller replicas: 1 (mac dinh)
- Hien tai: render time 45 giay, ArgoCD UI chậm, webhook delay 2-3 phut

Target: render time < 10 giay, webhook < 30s.

### Yêu cầu

1. Phan tich root cause: tai sao chậm?

2. Đề xuât 3 phuong an:

   **Option A — Hub Controller HA**:
   - Tang replicas, resource limits
   - Uu/nhuoc diem gi?

   **Option B — Federated ArgoCD**:
   - 1 ArgoCD per region
   - Uu/nhuoc diem gi?

   **Option C — ApplicationSet Sharding**:
   - Chia ApplicationSet theo team hoac region
   - Uu/nhuoc diem gi?

3. Chon 1 phuong an. Ve diagram topology.

4. Viet implementation plan (thu tu buoc,rollback plan).

### Deliverable

File: `exercises/ex5-migration-plan.md` — Phan tich + diagram + plan.

---

## Exercise 6 (Bonus): Pull Request Generator — Dynamic Preview Env

### Scenario

Team muon moi PR tao ra 1 preview environment tu dong:
- PR #123 cho `feature/user-auth` -> preview env: `pr-123-user-auth`
- Cluster: preview cluster (gcp-us-central1-preview)
- Resources: replicas=1, ttl=24h
- Khi PR merge/close -> xoa preview env

### Yêu cầu

1. Thiết ke end-to-end:
   - SCM Provider generator hay Pull Request generator? Tai sao?
   - Filter: chi tao preview cho PR len `main` hoac `release/*`

2. Viet ApplicationSet YAML hoan chinh.

3. Neu dung ArgoCD Image Updater (hoac webhook), khi PR close:
   - ArgoCD nhan event the nao?
   - Co can them Script Hook khong?
   - Xoa Application nhu the nao (garbage collection)?

4. Neu co 50 PR cung luc (sprint end), preview cluster co the chiu duoc khong? Đề xuat scale strategy.

### Deliverable

File: `exercises/ex6-pr-preview-design.md` — Design + YAML + scale plan.

---

## Bonus Challenges

### Challenge A: Nested Matrix Workaround

Matrix chi ho tro 2 child generators. Dùng git directory generator voi `include` va `exclude` de mo phong 3-dimension: services x envs x regions. Chi ra cach lam va gioi han.

### Challenge B: Self-Healing ApplicationSet

Khi cluster secret bi xoa ngoai ý muốn (khong phai xoa tay), Application mat. Viet 1 Script Hook hoac external metric de auto-detect va tao lai Application. (Goihan: khi cluster secret quay lai, ApplicationSet khong auto-recreate; can manual sync).

### Challenge C: Matrix vs Merge Calculator

Viet script `generator-decider.sh`:
- Input: JSON mo ta cac dimension thay doi va relationship
- Output: khuyen nghi generator (matrix/merge/list/cluster) + YAML template skeleton

---

## Hướng dẫn nộp

Moi exercise tao file trong thu muc `exercises/` cua apps-repo. Ten file theo quy uoc: `ex{N}-{slug}.{ext}`.

```bash
apps-repo/
  exercises/
    ex1-96apps-design.yaml
    ex2-merge-gdpr.yaml
    ex3-debug-matrix.md
    ex4-naming-refactor.yaml
    ex5-migration-plan.md
    ex6-pr-preview-design.md
```

Commit message: `day23: add exercises for ApplicationSet advanced`
