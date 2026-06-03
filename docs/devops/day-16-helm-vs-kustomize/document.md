# Day 16: Document — Helm vs Kustomize Reference

---

## 1. Helm Command Cheat Sheet

### Chart Development

```bash
# Tạo chart mới
helm create <chart-name>

# Lint chart
helm lint <chart-path>
helm lint <chart-path> --strict

# Render template (không gửi lên cluster)
helm template <release-name> <chart-path>
helm template <release-name> <chart-path> -f values-prod.yaml
helm template <release-name> <chart-path> --set key=value --debug

# Package chart
helm package <chart-path>
helm package <chart-path> --version 1.2.0 --app-version 2.0.0
```

### Release Management

```bash
# Install
helm install <release> <chart> --namespace <ns> --create-namespace
helm install <release> <chart> -f values.yaml --wait --atomic --timeout 5m

# Upgrade
helm upgrade <release> <chart> -f values.yaml --wait --atomic
helm upgrade --install <release> <chart>  # install nếu chưa có

# Rollback
helm rollback <release> <revision>
helm rollback <release> <revision> --wait

# Uninstall
helm uninstall <release> --namespace <ns>
helm uninstall <release> --keep-history  # giữ history để rollback

# Status & History
helm list --all-namespaces
helm status <release>
helm history <release>
helm get values <release>
helm get manifest <release>
helm get all <release>
```

### Repository

```bash
# HTTP repo
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo <keyword>
helm search hub <keyword>  # search ArtifactHub

# OCI registry
helm push <chart>.tgz oci://registry.example.com/charts
helm pull oci://registry.example.com/charts/<name> --version 1.0.0
helm install <release> oci://registry.example.com/charts/<name>
```

### Debugging

```bash
# Dry-run against cluster
helm install <release> <chart> --dry-run --debug

# Diff (cần plugin)
helm plugin install https://github.com/databus23/helm-diff
helm diff upgrade <release> <chart> -f values.yaml

# Get rendered manifest
helm get manifest <release> | kubectl apply --dry-run=server -f -

# Debug hooks
helm install <release> <chart> --debug --dry-run | grep -A 20 "helm.sh/hook"
```

---

## 2. Kustomize Command Cheat Sheet

### Build & Preview

```bash
# Build/render overlay
kubectl kustomize <overlay-dir>
kustomize build <overlay-dir>

# Diff với cluster
kubectl diff -k <overlay-dir>

# Apply
kubectl apply -k <overlay-dir>
kubectl apply -k <overlay-dir> --server-side

# Delete
kubectl delete -k <overlay-dir>

# Dry-run
kubectl apply -k <overlay-dir> --dry-run=server
kubectl apply -k <overlay-dir> --dry-run=client -o yaml
```

### Edit (CLI)

```bash
# Thêm resource
kustomize edit add resource deployment.yaml

# Set image
kustomize edit set image nginx=nginx:1.25

# Set namespace
kustomize edit set namespace production

# Add label
kustomize edit add label env:production

# Add annotation
kustomize edit add annotation owner:team-backend

# Set name prefix
kustomize edit set nameprefix prod-
```

---

## 3. Helm vs Kustomize Comparison Matrix

| Tiêu chí | Helm | Kustomize | Winner |
|-----------|------|-----------|--------|
| **Setup** | Cần cài helm CLI | Built-in kubectl | Kustomize |
| **Learning curve** | Cao (Go templates) | Thấp (YAML patches) | Kustomize |
| **Base readability** | Template syntax khó đọc | Valid YAML dễ đọc | Kustomize |
| **Parameterization power** | Cao (conditionals, loops) | Trung bình (patches) | Helm |
| **Package sharing** | Chart repos, OCI registry | Git repos | Helm |
| **Version management** | Chart versioning | Git-based | Helm |
| **Lifecycle management** | install/upgrade/rollback | Không có | Helm |
| **Dependency management** | Sub-charts | Không trực tiếp | Helm |
| **GitOps integration** | Tốt (ArgoCD, Flux) | Rất tốt (native kubectl) | Kustomize |
| **PR review experience** | Khó (template changes) | Dễ (YAML patches) | Kustomize |
| **Multi-env management** | values-dev/staging/prod.yaml | overlays/dev/staging/prod/ | Tie |
| **Testing** | helm test, helm lint | kubectl --dry-run | Tie |
| **Community ecosystem** | Lớn (ArtifactHub) | Nhỏ hơn | Helm |
| **Secret handling** | Plugins (helm-secrets) | SecretGenerator + .gitignore | Tie |
| **Debugging** | helm template --debug | kubectl kustomize | Tie |

---

## 4. Decision Framework

```
Bạn đang triển khai application gì?
│
├── Third-party software (Prometheus, NGINX, cert-manager)
│   └── → Dùng Helm chart có sẵn
│
├── Internal application, team < 5 dev
│   ├── Cần conditional logic, loops? → Helm
│   └── Chỉ khác config giữa envs? → Kustomize
│
├── Internal application, team > 10 dev
│   ├── Cần package sharing giữa teams? → Helm (library chart)
│   ├── Dùng GitOps (ArgoCD/Flux)? → Kustomize hoặc Helm+Kustomize
│   └── Cần lifecycle management (rollback)? → Helm
│
└── Platform team cung cấp template cho dev teams
    └── → Helm library chart + Kustomize overlay
```

---

## 5. Helm Chart Best Practices Checklist

### Chart Structure

- [ ] `Chart.yaml` có đầy đủ name, version, appVersion, description
- [ ] `values.yaml` có comments giải thích mỗi parameter
- [ ] `_helpers.tpl` chứa common labels, fullname, chart name
- [ ] `NOTES.txt` hiển thị thông tin hữu ích sau install
- [ ] `.helmignore` loại trừ files không cần thiết

### Templates

- [ ] Dùng `&#123;&#123; include "chart.fullname" . &#125;&#125;` thay vì hardcode names
- [ ] Dùng `&#123;&#123; .Release.Namespace &#125;&#125;` thay vì hardcode namespace
- [ ] Labels chuẩn: `app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/managed-by`
- [ ] Resource requests/limits configurable qua values
- [ ] Health checks (readiness/liveness) configurable
- [ ] Security context configurable (non-root default)

### Values

- [ ] Sensible defaults cho mọi values
- [ ] Không có secrets trong values.yaml mặc định
- [ ] Support `existingSecret` pattern cho sensitive data
- [ ] Optional resources disabled by default: Ingress, HPA, PDB, NetworkPolicy

### Release Management

- [ ] Dùng `--atomic` cho install/upgrade
- [ ] Dùng `--wait` để đảm bảo resources ready
- [ ] Set `--history-max` để giới hạn release history
- [ ] Dùng `--timeout` phù hợp

### CI/CD

- [ ] `helm lint` trong CI pipeline
- [ ] `helm template` + `kubeval`/`kubeconform` validate output
- [ ] `helm diff` trước upgrade production
- [ ] Pin chart version trong pipeline
- [ ] Scan chart cho security issues

---

## 6. Kustomize Best Practices Checklist

### Structure

- [ ] Base chứa valid Kubernetes YAML (không template syntax)
- [ ] Overlay chỉ chứa differences, không duplicate base
- [ ] Naming convention rõ ràng: `overlays/<env>/`
- [ ] Maximum 2-3 cấp overlay nesting

### Patches

- [ ] Ưu tiên strategic merge patch cho thay đổi đơn giản
- [ ] Dùng JSON patch cho thay đổi phức tạp (add/remove array elements)
- [ ] Mỗi patch file tên mô tả rõ mục đích
- [ ] Nếu patch > 50% base → cân nhắc viết lại base

### Transformers

- [ ] Dùng `namePrefix`/`nameSuffix` cho environment separation
- [ ] Dùng `commonLabels` cho environment tagging
- [ ] Dùng `images` transformer thay vì patch image trực tiếp
- [ ] Dùng `namespace` transformer khi cần

### Generators

- [ ] ConfigMapGenerator cho environment-specific config
- [ ] SecretGenerator + files KHÔNG commit vào Git
- [ ] Dùng `generatorOptions` để control hash suffix behavior

### GitOps

- [ ] Mỗi overlay self-contained (có thể `kubectl apply -k` độc lập)
- [ ] `kubectl diff -k` trước apply production
- [ ] ArgoCD/Flux point trực tiếp vào overlay directory

---

## 7. Common Template Patterns (Helm)

### Optional Resource

```yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "myapp.fullname" . }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ include "myapp.fullname" $ }}
                port:
                  number: {{ $.Values.service.port }}
          {{- end }}
    {{- end }}
{{- end }}
```

### Extra Environment Variables

```yaml
env:
  {{- range .Values.extraEnvVars }}
  - name: {{ .name }}
    value: {{ .value | quote }}
  {{- end }}
  {{- range .Values.extraEnvVarsSecret }}
  - name: {{ .name }}
    valueFrom:
      secretKeyRef:
        name: {{ .secretName }}
        key: {{ .secretKey }}
  {{- end }}
```

### ExistingSecret Pattern

```yaml
{{- if .Values.db.existingSecret }}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.existingSecret }}
      key: {{ .Values.db.existingSecretKey | default "password" }}
{{- else if .Values.db.password }}
- name: DB_PASSWORD
  value: {{ .Values.db.password | quote }}
{{- end }}
```

---

## 8. Common Kustomize Patterns

### Default Deny NetworkPolicy (chỉ thêm ở prod)

```yaml
# overlays/prod/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

```yaml
# overlays/prod/kustomization.yaml
resources:
  - ../../base
  - networkpolicy.yaml
```

### HPA chỉ cho prod

```yaml
# overlays/prod/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### ConfigMap từ file

```yaml
# overlays/prod/kustomization.yaml
configMapGenerator:
  - name: nginx-config
    files:
      - configs/nginx.conf
    options:
      disableNameSuffixHash: true
```

---

## 9. Troubleshooting Quick Reference

### Helm Issues

| Lỗi | Nguyên nhân | Fix |
|------|-------------|-----|
| `Error: INSTALLATION FAILED: cannot re-use a name that is still in use` | Release cùng tên đã tồn tại | `helm uninstall <release>` hoặc đổi tên |
| `Error: rendered manifests contain a resource that already exists` | Resource đã tồn tại ngoài Helm | `kubectl delete` resource hoặc `helm install --force` |
| `Error: UPGRADE FAILED: another operation is in progress` | Release bị stuck | `kubectl delete secret -l owner=helm,status=pending-upgrade` |
| `Error: template: ... function "xxx" not defined` | Sai function name trong template | Kiểm tra Go template docs, `_helpers.tpl` |
| `YAML parse error` | Sai indentation sau render | Dùng `helm template --debug`, check `nindent` values |
| Hook timeout | Pre/post hook chạy quá lâu | Tăng `--timeout`, kiểm tra hook Job |

### Kustomize Issues

| Lỗi | Nguyên nhân | Fix |
|------|-------------|-----|
| `no matches for OriginalId` | Patch target name không match base | Kiểm tra name chính xác trong base vs patch |
| `conflicting label` | commonLabels xung đột | Kiểm tra labels trong base và overlay |
| `accumulating resources` | Resource duplicate | Kiểm tra không reference cùng resource 2 lần |
| Image tag không đổi | `images` transformer name không match | Name phải chính xác match image name trong base |
| `must build at directory` | Path sai | Kiểm tra relative path trong resources |

