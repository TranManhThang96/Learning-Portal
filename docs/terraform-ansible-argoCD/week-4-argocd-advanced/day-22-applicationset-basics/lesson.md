# Day 22 — ApplicationSet Basics

<div v-pre>

## Mục tiêu ngày học

- Hiểu ApplicationSet CRD và ApplicationSet controller khác gì so với Application thuong
- Nắm 3 generator co ban: List, Git (directory + file), Cluster
- Viet duoc ApplicationSet template dung Go template syntax
- Deploy 3 service vao 2+ env bang 1 ApplicationSet thay vi 6 file Application
- Them service moi chi bang cach tao folder — quan sat Application tu sinh khong can tao file YAML

---

## 1. Bối cảnh: Pain point từ Day 21

Day 21 ket thuc voi App of Apps pattern: 5-10 platform apps duoc tao boi 1 root Application. Ban da biết gioi han:

```
Day 21: 3 services × 3 envs = 9 Application files
Service moi = +3 file copy-paste
Doi naming convention = sua N file
```

**Pain points thuc te:**
- Drift giua cac Application file: syncPolicy khac nhau, metadata labels thieu
- Missing label → Application khong duoc ArgoCD quản ly đúng
- 1 người tao App of Apps, cả team phải học convention đó
- Review 30+ Application file trong PR = noise khong can thiet

**Solution:** 1 ApplicationSet + 1 generator → tu sinh ra N Application.

---

## 2. Kiến thức nền tảng - 30 phút: ApplicationSet la gi?

**ApplicationSet** la 1 Custom Resource Definition (CRD) do `ApplicationSet controller` (pod riêng trong namespace `argocd`) reconcile.

```
ApplicationSet controller (pod)
  ├── Doc Git generator config
  ├── Lay data tu generator
  ├── Render Go template
  └── CREATE/UPDATE/DELETE Application CRD
```

**Ket qua:** N Application CRD, moi Application quản ly 1 workload. ApplicationSet KHÔNG tao workload truc tiep — no chi tao Application object, Application do sync workload.

**Khác biệt voi Application thuong:**

| | Application | ApplicationSet |
|---|---|---|
| Quản lý bởi | ArgoCD controller | ApplicationSet controller |
| Số lượng | 1 manifest = 1 workload | 1 manifest = N workload |
| Template | Static | Dynamic (Go template) |
| Sync | Từng app | Từng app (controller sinh ra) |

**ASCII flow:**

```
Git Repo: services/*/overlays/*/
   │
   ▼
ApplicationSet (Git Directory Generator)
   │
   ├── { path: services/api-service/overlays/dev }
   ├── { path: services/api-service/overlays/staging }
   ├── { path: services/worker-service/overlays/dev }
   └── { path: services/worker-service/overlays/staging }
   │
   ▼
ApplicationSet Template (Go template)
   │
   ├── Application: api-service-dev
   ├── Application: api-service-staging
   ├── Application: worker-service-dev
   └── Application: worker-service-staging
   │
   ▼
ArgoCD Sync → Kubernetes Workloads
```

---

## 3. Ba Generator cơ bản (Day 22)

### 3.1 List Generator — Don gian nhat

Hardcode list params. Dùng cho testing hoac fixed small set.

```yaml
generators:
  - list:
      elements:
        - service: api-service;   env: dev
        - service: api-service;   env: staging
        - service: worker-service; env: dev
```

Thực tế dùng khi: demo, fixed 2-3 env, không cần auto-discovery.

### 3.2 Git Generator — Directory Mode

Scan folder trong Git repo. Moi subfolder = 1 Application.

```yaml
generators:
  - git:
      repoURL: https://github.com/org/apps-repo.git
      revision: HEAD
      directories:
        - path: services/*/overlays/*
```

**Params sinh ra:**
- `{<!-- -->{path}}`           — full path tu root repo: `services/api-service/overlays/dev`
- `{<!-- -->{path.basename}}`  — ten cuoi cung: `dev`
- `{<!-- -->{path[0]}}`        — phan tu thu 0: `services`
- `{<!-- -->{path[1]}}`        — phan tu thu 1: `api-service`
- `{<!-- -->{path[2]}}`        — phan tu thu 2: `overlays`
- `{<!-- -->{path[3]}}`        — phan tu thu 3: `dev`

**Recommended cho microservices:** Them folder = tu dong co Application.

### 3.3 Git Generator — File Mode

Scan file pattern. Moi file = 1 Application, data trong file = params.

```yaml
generators:
  - git:
      repoURL: https://github.com/org/apps-repo.git
      revision: HEAD
      files:
        - path: "services/*/config.yaml"
```

File `services/api-service/config.yaml`:
```yaml
service: api-service
env: dev
replicas: 2
memory: 512Mi
```

Params: `{<!-- -->{values.service}}`, `{<!-- -->{values.env}}`, `{<!-- -->{values.replicas}}`.

**Dùng khi:** can overwrite replicas/memory khac nhau giua env mà không hardcode trong template.

### 3.4 Cluster Generator

Scan Secrets co label `argocd.argoproj.io/secret-type=cluster`.

```yaml
generators:
  - clusters:
      selector:
        matchLabels:
          argocd.argoproj.io/secret-type: cluster
```

**Params:**
- `{<!-- -->{name}}`          — ten cluster (trong ArgoCD)
- `{<!-- -->{nameNormalized}}` — ten da normalize (an toàn cho Kubernetes name)
- `{<!-- -->{server}}`        — API server URL
- `{<!-- -->{metadata.labels}}` — labels tren Secret

**Dùng khi:** multi-cluster fleet deployment. Day 23 se dung Matrix generator de ket hop Cluster + Git.

---

## 4. Template Structure

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices
spec:
  goTemplate: true                          # BAT BUOC: dung Go template syntax
  generators:
    - git:
        repoURL: https://github.com/org/apps-repo.git
        revision: HEAD
        directories:
          - path: services/*/overlays/*
  template:
    metadata:
      name: '{{path[1]}}-{{path[3]}}'       # vd: api-service-dev
      labels:
        app.kubernetes.io/created-by: applicationset
        app.kubernetes.io/part-of: microservices
    spec:
      project: default
      source:
        repoURL: https://github.com/org/apps-repo.git
        targetRevision: HEAD
        path: '{{path}}'                    # services/api-service/overlays/dev
        kustomize:
          images:
            - myorg/{{path[1]}}:1.0.0      # demo tag; production dùng immutable release tag
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path[3]}}'            # dev, staging
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
```

**goTemplate: true** — Bat buoc dung trong production. Khong dung se bi legacy template collision voi `{<!-- -->{` trong YAML.

---

## 5. Lifecycle & Deletion Behavior

### Application sinh ra co ten nao?

ArgoCD chi tao 1 Application cho 1 name. Neu 2 ApplicationSet cung tao Application trùng tên: **một sẽ thắng, một sẽ bi ignored**, không error rõ ràng.

### preserveResourcesOnDeletion

Mac dinh: xoa ApplicationSet → toan bo Application bi xóa theo.

```yaml
spec:
  syncPolicy:
    preserveResourcesOnDeletion: true
```

→ Xóa ApplicationSet → Application CRD con lai trên cluster (không bi xoa). Workload cũng khong bi xoa vi ArgoCD khong prunes khi khong con Application.

**Cảnh báo:** Dùng `preserveResourcesOnDeletion` khi không muốn mass-delete vô tình.

---

## 6. Deep Dive & Trade-offs - 30 phút: App of Apps vs ApplicationSet

| Tiêu chí | App of Apps | ApplicationSet |
|---|---|---|
| Số lượng manifest | N×M (service × env) | 1 (generator + template) |
| Thêm service mới | Tạo N file Application | Tạo folder mới |
| Boilerplate | Có (copy-paste) | Không |
| Drift risk | Cao (sửa tay N file) | Thấp (template duy nhất) |
| Review PR | N file noisy | 1 file hoặc 1 folder |
| Generator flexibility | Không có | List/Git/Cluster/Matrix |
| Migration từ App of Apps | — | Step-by-step (xem Day 23) |
| Learning curve | Thấp | Trung bình |
| Debugging | Quen thuộc | Can know generator params |

**Khi nào dùng App of Apps thay vì ApplicationSet?**
- Team nho (2-3 người), ít service, ít thay đổi
- Khi can Application có spec hoàn toàn khác nhau (không uniform structure)
- Khi can inter-dependency giua các Application (App of Apps tao theo thứ tự)

**Khi nào dùng ApplicationSet?**
- Service ≥ 5, env ≥ 3
- Multi-cluster
- Auto-discovery (service team tự tạo folder, không cần platform team)
- Muốn template duy nhất, drift bằng 0

---

## 7. Trade-offs & Pitfalls

### Operational Risk
ApplicationSet controller bug = mass create/delete Application. **Thực tế:** 
- Review controller log: `kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller`
- Dung `preserveResourcesOnDeletion` khi migrate
- Backup Application CRD truoc khi apply ApplicationSet mới

### Performance
- 200+ Application từ 1 ApplicationSet: render time ~5-10s
- Memory: ApplicationSet controller pod limit mac dinh ~1Gi
- Recommendation: split 1 ApplicationSet lon thanh nhieu ApplicationSet nho theo team/service

### Security
- Template injection: data trong Git (path, values) co ky tu dac biet → render fail hoặc sai
- Signature verification tren Git generator: `spec.securityPolicy` (Day 25)
- RBAC: ApplicationSet tao Application trong namespace nao? Cần ClusterRole hoặc RoleBinding đúng

### Pitfalls thực tế

```
1. Ten trung nhau
   → 2 ApplicationSet cùng generate api-service-dev
   → 1 bi ignored, log: "Application excluded by exclusion filter"

2. path không unique
   → Pattern services/*/overlays/* sinh ra trùng
   → Debug: kiem tra generator params bang dry-run

3. goTemplate: false (default) + {{ trong YAML
   → Template render sai, khong debug duoc de
   → Fix: luon dat goTemplate: true

4. Generator data thay doi → Application bi xoa
   → Khong có preserveResourcesOnDeletion → workload bi prune
   → Test: xóa folder → kubectl get application | grep <name>

5. Race condition
   → 2 ApplicationSet cùng generate 1 Application
   → ApplicationSet controller process lần lượt nên thường OK
   → Nguy hiem khi apply đồng thời 2 ApplicationSet
```

---

## 8. Hands-on Lab (60 phút)

### Pre-req
- kind cluster + ArgoCD (Day 17)
- `apps-repo` skeleton (Day 20)
- Xóa hoặc disable App of Apps Application tu Day 21

### Step 1: Verify ApplicationSet controller

```bash
kubectl get pods -n argocd | grep applicationset
# EXPECTED: argocd-applicationset-controller-xxx Running
```

### Step 2: Cấu trúc apps-repo

```bash
# Clone repo cua ban
git clone https://github.com/<org>/apps-repo.git
cd apps-repo

# Tao structure
mkdir -p services/api-service/overlays/{dev,staging}
mkdir -p services/worker-service/overlays/{dev,staging}
mkdir -p services/frontend-service/overlays/{dev,staging}
mkdir -p services/notification-service/overlays/{dev,staging}  # them sau

# Tao base kustomization cho moi service
for svc in api-service worker-service frontend-service; do
  cat > services/$svc/base/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
EOF
  cat > services/$svc/base/deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $svc
spec:
  replicas: 2
  selector:
    matchLabels:
      app: $svc
  template:
    metadata:
      labels:
        app: $svc
    spec:
      containers:
        - name: $svc
          image: myorg/$svc:1.0.0
          resources:
            limits:
              memory: 256Mi
              cpu: 250m
EOF
  cat > services/$svc/base/service.yaml <<EOF
apiVersion: v1
kind: Service
metadata:
  name: $svc
spec:
  selector:
    app: $svc
  ports:
    - port: 80
      targetPort: 8080
EOF
done

# Tao overlays cho dev (replicas=1)
for svc in api-service worker-service frontend-service; do
  cat > services/$svc/overlays/dev/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
bases:
  - ../../base
namespace: dev
commonLabels:
  env: dev
patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
EOF
done

# Tao overlays cho staging (replicas=2)
for svc in api-service worker-service frontend-service; do
  cat > services/$svc/overlays/staging/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
bases:
  - ../../base
namespace: staging
commonLabels:
  env: staging
EOF
done

git add . && git commit -m "feat: initial service structure" && git push
```

### Step 3: ApplicationSet voi List Generator (warm-up)

```bash
cat > argocd/appsets/microservices-list.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-list
spec:
  goTemplate: true
  generators:
    - list:
        elements:
          - service: api-service;       env: dev
          - service: api-service;       env: staging
          - service: worker-service;     env: dev
          - service: worker-service;     env: staging
          - service: frontend-service;   env: dev
          - service: frontend-service;   env: staging
  template:
    metadata:
      name: '{{.service}}-{{.env}}'
      labels:
        app.kubernetes.io/created-by: applicationset
    spec:
      project: default
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: 'services/{{.service}}/overlays/{{.env}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{.env}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
EOF

kubectl apply -f argocd/appsets/microservices-list.yaml
```

**Quan sát:**
```bash
kubectl get application        # 6 Application duoc sinh ra
argocd app list                # xem trong ArgoCD UI
argocd app get api-service-dev # xem chi tiet
```

### Step 4: Refactor sang Git Directory Generator

```bash
cat > argocd/appsets/microservices-git-dir.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-git-dir
spec:
  goTemplate: true
  generators:
    - git:
        repoURL: https://github.com/<org>/apps-repo.git
        revision: HEAD
        directories:
          - path: services/*/overlays/*
  template:
    metadata:
      name: '{{path[1]}}-{{path[3]}}'
      labels:
        app.kubernetes.io/created-by: applicationset
        app.kubernetes.io/service: '{{path[1]}}'
        app.kubernetes.io/env: '{{path[3]}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{path[3]}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
EOF

# Xoa List generator, apply Git directory
kubectl delete -f argocd/appsets/microservices-list.yaml
kubectl apply -f argocd/appsets/microservices-git-dir.yaml
sleep 5
kubectl get application        # 6 Application, cung ten
```

### Step 5: Test auto-discovery — thêm service mới

```bash
# Tao notification-service
mkdir -p services/notification-service/base
mkdir -p services/notification-service/overlays/{dev,staging}

# Copy base files
cp services/api-service/base/kustomization.yaml services/notification-service/base/kustomization.yaml
sed 's/api-service/notification-service/g' services/api-service/base/deployment.yaml > services/notification-service/base/deployment.yaml
sed 's/api-service/notification-service/g' services/api-service/base/service.yaml > services/notification-service/base/service.yaml

# Tao overlays
cp services/api-service/overlays/dev/kustomization.yaml services/notification-service/overlays/dev/kustomization.yaml
cp services/api-service/overlays/staging/kustomization.yaml services/notification-service/overlays/staging/kustomization.yaml

git add . && git commit -m "feat: add notification-service" && git push
```

**Quan sát:** Sau 2-3 phut (ArgoCD sync interval), 2 Application mới tự sinh:
```bash
kubectl get application | grep notification
# notification-service-dev
# notification-service-staging
```

### Step 6: Test them env mới — them qa overlay

```bash
mkdir -p services/api-service/overlays/qa
cp services/api-service/overlays/staging/kustomization.yaml services/api-service/overlays/qa/kustomization.yaml
sed -i 's/env: staging/env: qa/g' services/api-service/overlays/qa/kustomization.yaml
sed -i 's/namespace: staging/namespace: qa/g' services/api-service/overlays/qa/kustomization.yaml

git add . && git commit -m "feat: add qa env for api-service" && git push
# Quan sat: api-service-qa tu sinh
```

### Step 7: Test xóa overlay (khong có preserveResourcesOnDeletion)

```bash
# Xóa notification-service folder
rm -rf services/notification-service
git add . && git commit -m "chore: remove notification-service" && git push
# Quan sat: notification-service-dev, notification-service-staging bi xoa
# WORKLOAD cũng bi prune (vi prune: true)
```

### Step 8: Git File Generator — per-env values

```bash
# Tao config file cho moi service/env
cat > services/api-service/config.yaml <<EOF
service: api-service
env: default
replicas: 2
memoryLimit: 512Mi
EOF

cat > services/api-service/overlays/dev/config.yaml <<EOF
service: api-service
env: dev
replicas: 1
memoryLimit: 256Mi
EOF

cat > services/api-service/overlays/staging/config.yaml <<EOF
service: api-service
env: staging
replicas: 3
memoryLimit: 1Gi
EOF

git add . && git commit -m "feat: add per-env config files" && git push
```

```bash
cat > argocd/appsets/microservices-git-file.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-git-file
spec:
  goTemplate: true
  generators:
    - git:
        repoURL: https://github.com/<org>/apps-repo.git
        revision: HEAD
        files:
          - path: "services/*/config.yaml"
  template:
    metadata:
      name: '{{path[1]}}-{{values.env}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: 'services/{{values.service}}/overlays/{{values.env}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{values.env}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
EOF
```

### Step 9: Failure scenario — path khong unique

```bash
# Tao duplicate path
mkdir -p services/api-service/overlays/dev/variant-a
cp services/api-service/overlays/dev/kustomization.yaml services/api-service/overlays/dev/variant-a/kustomization.yaml
# Pattern services/*/overlays/* se match ca dev/ va dev/variant-a
# → 2 Application trùng tên api-service-dev → 1 bi ignored
git add . && git commit -m "chore: add variant" && git push
# Kiem tra log
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller --tail=50 | grep -i "exclude\|duplicate\|conflict"
```

### Step 10: Cleanup

```bash
kubectl delete -f argocd/appsets/microservices-git-dir.yaml
# Workload bi prune (vi prune: true)
# Apply lai voi preserveResourcesOnDeletion neu can
```

### Expected output

```
kubectl get application
NAME                   DESTINATION   SYNC STATUS
api-service-dev        dev           Synced
api-service-staging    staging       Synced
api-service-qa         qa            Synced
worker-service-dev     dev           Synced
worker-service-staging staging       Synced
frontend-service-dev   dev           Synced
frontend-service-staging staging    Synced
```

### Troubleshooting

```bash
# 1. Application khong xuat hien
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller --tail=100 | grep -i error

# 2. Dry-run: render truc tiep
# ApplicationSet controller khong co built-in dry-run
# Debug bang cach chạy argo-cd CLI:
argocd appset get microservices-git-dir

# 3. Kiem tra generator params
kubectl get applicationset microservices-git-dir -n argocd -o jsonpath='{.status}'

# 4. Force refresh
kubectl annotate applicationset microservices-git-dir -n argocd argocd.argoproj.io/application-set-refresh=$(date +%s) --overwrite
```

---

## 9. Kiểm tra hiểu bài

**Câu 1:** Git Directory mode vs Git File mode khác nhau thế nào? Khi nào dùng mode nào?

> Git Directory: moi folder = 1 Application, không can file phu. Best cho auto-discovery.
> Git File: moi file config = 1 Application, data trong file = params. Best khi can gia tri khac nhau per env/service mà không hardcode trong template.

**Câu 2:** Ban them folder `services/worker-service/overlays/production/` nhung Application khong xuat hien. Kiem tra gi?

> 1. Git push thành công? 2. Pattern `services/*/overlays/*` có match production? 3. Overlay có chứa `kustomization.yaml`? 4. Xem ApplicationSet controller log: `kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller`. 5. Check sync status: `argocd app list`.

**Câu 3:** Khi nào nên dùng App of Apps thay vì ApplicationSet?

> Service < 5, env < 2, cần Application spec hoàn toàn khác nhau, hoặc cần inter-dependency (A sync truoc B).

**Câu 4:** 1 ApplicationSet cho tất cả service vs 1 ApplicationSet/service — trade-off?

> 1 lon: dễ quản lý template, nhưng conflict neu pattern trùng, 1 bug = ảnh hưởng toàn bộ.
> N nho: isolation, team ownership độc lập, nhưng overhead khi them service moi (can tao ApplicationSet moi).

**Câu 5:** List generator 50 entries → migrate sang generator nao?

> Git Directory generator. Đưa 50 entry thành 50 folder trong repo, mỗi folder = service/env. Thêm service = tạo folder, không cần sửa ApplicationSet manifest.

---

## 10. Tóm tắt cuối ngày

Sau Day 22, ban có:

```
1 ApplicationSet template
  + Git directory generator
  → Tự sinh 7 Application (3 services × 2 envs + 1 qa)
  → Auto-discovery: thêm folder = thêm Application
  → 0 boilerplate Application file
  → Drift = 0 (template duy nhất)
```

**Key takeaway:** ApplicationSet là bước tiến tự nhiên từ App of Apps. Khi service × env tăng, ApplicationSet loại bỏ hoàn toàn boilerplate. Day 23 mở rộng với Matrix và Merge generator để handle multi-cluster và phức tạp hơn.

---

## 11. Tham khảo

- [ArgoCD ApplicationSet Documentation](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [ApplicationSet Generators](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators/)
- [Git Generator](https://github.com/argoproj/applicationset/blob/master/docs/Generators-Git.md)
- [Cluster Generator](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Cluster/)
- [List Generator](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-List/)
- [Controlling Resource Modification](https://github.com/argoproj/applicationset/blob/master/docs/Controlling-Resource-Modification.md)

</div>
