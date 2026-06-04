# Day 22 — ApplicationSet Cheat Sheet & Reference

<div v-pre>

## 1. Generator Cheat Sheet

### List Generator

```yaml
generators:
  - list:
      elements:
        - service: api-service; env: dev
        - service: api-service; env: staging
        # Hoặc dạng YAML:
        - service: worker-service
          env: dev
          replicas: 1
```

**Params:** `{{service}}`, `{{env}}`, `{{replicas}}` (tùy field trong element).

---

### Git Generator — Directory Mode

```yaml
generators:
  - git:
      repoURL: https://github.com/org/repo.git
      revision: HEAD              # hoặc branch/tag/commit SHA
      directories:
        - path: services/*/overlays/*   # wildcard: moi subfolder
        - path: apps/**/overlays/*      # ** = recursive
          exclude: [apps/legacy/*]      # loại trừ pattern
```

**Params:**

| Param | Ví dụ | Mô tả |
|---|---|---|
| `{{path}}` | `services/api-service/overlays/dev` | Full path từ repo root |
| `{{path.basename}}` | `dev` | Tên cuối cùng |
| `{{path[0]}}` | `services` | Phần tử thứ 0 |
| `{{path[1]}}` | `api-service` | Phần tử thứ 1 |
| `{{path[2]}}` | `overlays` | Phần tử thứ 2 |
| `{{path[3]}}` | `dev` | Phần tử thứ 3 |
| `{{path.filename}}` | (chỉ file mode) | Tên file không có ext |

---

### Git Generator — File Mode

```yaml
generators:
  - git:
      repoURL: https://github.com/org/repo.git
      revision: HEAD
      files:
        - path: "services/*/config.yaml"   # quotes bắt buộc
        - path: "apps/**/*.json"            # recursive
```

**File format** (`services/api-service/config.yaml`):
```yaml
service: api-service
env: dev
replicas: 2
memoryLimit: 512Mi
cluster: https://10.0.0.1:6443
```

**Params:** `{{path.basename}}`, `{{values.service}}`, `{{values.env}}`, `{{values.replicas}}`, ...

---

### Cluster Generator

```yaml
generators:
  - clusters:
      selector:
        matchLabels:
          argocd.argoproj.io/secret-type: cluster
        matchExpressions:
          - key: environment
            operator: In
            values: [dev, staging]
```

**Params:**

| Param | Mô tả |
|---|---|
| `{{name}}` | Tên cluster (raw, chưa normalize) |
| `{{nameNormalized}}` | Tên đã normalize (an toàn cho Kubernetes name) |
| `{{server}}` | API server URL |
| `{{metadata.labels.<key>}}` | Label trên Secret |
| `{{metadata.annotations.<key>}}` | Annotation trên Secret |

---

## 2. goTemplate Syntax Reference

**Bắt buộc đặt `goTemplate: true` ở spec level.**

```yaml
spec:
  goTemplate: true
  goTemplateOptions:
    - missingkey=error    # Fail fast thay vì render rỗng
    # - missingkey=default
    # - missingkey=omit
```

**Template params:**

```yaml
# String interpolation
name: '{{path[1]}}-{{path[3]}}'

# Index an toàn
namespace: '{{index .path 3}}'    # tương đương {{path[3]}}

# Values (Git file generator)
memory: '{{values.memoryLimit}}'

# Labels
project: '{{index .metadata.labels "environment"}}'

# Nested access
server: '{{.server}}'             # cluster generator

# String functions (Sprig/lib)
name: '{{ path[1] | upper }}'      # UPPER
name: '{{ path[1] | lower }}'      # lower
name: '{{ path[1] | trim }}'       # trim spaces

# Ternary / default
replicas: '{{ .Values.replicas | default "1" }}'

# goTemplate: true => dùng . thay vì .Values
path: '{{ .path[1] }}'             # goTemplate: true
path: '{{path[1]}}'                # goTemplate: false (legacy)
```

**Common mistake:**
```yaml
# Lỗi: {{ trong YAML bị parse sai
name: '{{path[1]}}-dev'    # Lỗi: ArgoCD parse {{path[1]}} là template

# Fix: goTemplate: true
name: '{{path[1]}}-dev'    # OK với goTemplate: true
```

---

## 3. Naming Convention Recipe

**Goal:** Tạo Application name unique, đọc được, Kubernetes-safe.

```yaml
# Recipe: service-env
name: '{{path[1]}}-{{path[3]}}'
# → api-service-dev, worker-service-staging

# Recipe: env-service (nếu muốn group theo env trong ArgoCD UI)
name: '{{path[3]}}-{{path[1]}}'
# → dev-api-service, staging-worker-service

# Recipe: team-service-env (nếu có thêm metadata)
name: '{{metadata.labels.team}}-{{path[1]}}-{{path[3]}}'
# → platform-api-service-dev
```

**Validation:**
- Kubernetes name: lowercase, chỉ a-z, 0-9, `-`
- Tối đa 253 ký tự
- Không trùng tên giữa các ApplicationSet

---

## 4. Generator Selection Decision Tree

```
Bạn có bao nhiêu service/env/cluster?
│
├─ 1-3 service, 1-2 env, 1 cluster
│   └─ List generator (hardcode đủ)
│
├─ 5+ service, 2+ env, 1 cluster
│   └─ Git Directory generator
│       (service/*/overlays/*)
│
├─ Can per-env values khác nhau
│   (replicas, memory, replicas)
│   └─ Git File generator
│       (services/*/config.yaml)
│
├─ 1+ cluster
│   └─ Cluster generator
│
├─ Git + Cluster cùng lúc
│   └─ Matrix generator (Day 23)
│
└─ Git + values cùng lúc
    └─ Merge generator (Day 23)
```

---

## 5. Common Errors Reference

| Error | Nguyên nhân | Fix |
|---|---|---|
| `Application excluded by exclusion filter` | Tên trùng giữa 2 ApplicationSet | Đổi tên hoặc xóa 1 ApplicationSet |
| `Render template error` | Template syntax sai hoặc param không tồn tại | `goTemplate: true` + `missingkey=error` |
| `no matches for kind Kustomization` | Path không chứa `kustomization.yaml` | Kiểm tra folder structure |
| Application tự xóa sau khi tạo | Generator data thay đổi, prune: true | Thêm `preserveResourcesOnDeletion: true` |
| Ứng dụng stuck ở OutOfSync | Path sai hoặc Git repo không đúng | Kiểm tra `kubectl get application <name> -o yaml` |
| Go template render rỗng | Dùng `{{.path}}` thay vì `{{path}}` (khi goTemplate: false) | Dùng đúng syntax theo goTemplate setting |
| `ApplicationSet not found` trong ArgoCD UI | Namespace argocd khác | Kiểm tra namespace trong ApplicationSet |

---

## 6. Migration Recipe: App of Apps → ApplicationSet

### Trước (Day 21): 3 services × 3 envs = 9 Application files

```
apps-repo/
└── argocd/
    └── applications/
        ├── api-service-dev.yaml
        ├── api-service-staging.yaml
        ├── api-service-prod.yaml
        ├── worker-dev.yaml
        ... (9 files)
```

### Sau (Day 22): 1 ApplicationSet

```
apps-repo/
├── services/
│   ├── api-service/
│   │   ├── base/{deployment,service,kustomization}.yaml
│   │   └── overlays/{dev,staging,prod}/
│   ├── worker-service/
│   │   └── ...
│   └── frontend-service/
│       └── ...
└── argocd/
    └── appsets/
        └── microservices.yaml   # 1 file thay thế 9 file
```

### Migration steps (0 downtime)

```bash
# Step 1: Tạo apps-repo structure (services/*/overlays/*/)
# Tao nhu Step 2 trong lesson.md

# Step 2: Apply ApplicationSet (parallel với App of Apps)
kubectl apply -f argocd/appsets/microservices.yaml

# Step 3: Verify 9 Application mới sync OK
argocd app list --selector app.kubernetes.io/created-by=applicationset

# Step 4: Disable App of Apps Application (khong xoa)
# Voi App of Apps root app, set syncPolicy.automated = null

# Step 5: Verify workload ổn định (khong OutOfSync, Health OK)

# Step 6: Xóa App of Apps root Application + child Application files
# CHI SAU KHI ApplicationSet Application 100% OK
kubectl delete -f argocd/applications/   # App of Apps child apps
kubectl delete -f argocd/root-app.yaml   # App of Apps root app

# Step 7: Cleanup preserveResourcesOnDeletion
# Neu dung preserveResourcesOnDeletion trong migration,
# xoa flag sau khi migration hoan tat
```

**Migration checklist:**
- [ ] Tất cả workload cùng Git repo với overlay structure
- [ ] ApplicationSet sync 100% (Health + Sync status OK)
- [ ] App of Apps child app đã disable automated sync
- [ ] Không có drift giữa ApplicationSet-managed và cluster state
- [ ] Backup Application CRD (optional): `kubectl get application -o yaml > backup-apps.yaml`

---

## 7. Anti-patterns Checklist

```
[ ] 1 ApplicationSet cho toàn bộ 50+ service
    → Split theo team hoặc domain

[ ] Không dùng goTemplate: true
    → Legacy template gây ra render bug khó debug

[ ] Không có preserveResourcesOnDeletion trong migration
    → Mass delete Application → mass prune workload

[ ] Tất cả ApplicationSet có automated sync (prune: true)
    → 1 typo trong Git = 1 namespace bi xóa
    → Production: manual sync hoặc prune: false

[ ] Tên Application trùng nhau giữa 2+ ApplicationSet
    → 1 Application bị ignored mà không warning rõ

[ ] Dùng List generator cho > 10 entries
    → Thêm service = sửa ApplicationSet file → PR noise
    → Migrate sang Git Directory generator

[ ] Không có label trên Application sinh ra
    → Không filter được trong ArgoCD UI
    → Them labels: app.kubernetes.io/service, env, team

[ ] Cluster generator dùng {{name}} thay vì {{nameNormalized}}
    → Cluster tên có dấu/chữ hoa → Kubernetes name không hợp lệ

[ ] Quên CreateNamespace=true trong multi-namespace deployment
    → Application sync fail vi namespace chưa tồn tại
```

</div>
