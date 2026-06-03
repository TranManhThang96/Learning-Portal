# Document - Day 36: Helm Fundamentals Reference

## Command quick reference

```bash
helm version
helm repo list
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo nginx
helm create my-chart
helm lint ./my-chart
helm template my-release ./my-chart
helm template my-release ./my-chart -f values-dev.yaml --debug
helm install my-release ./my-chart -n app --create-namespace
helm upgrade my-release ./my-chart -n app -f values-prod.yaml
helm upgrade --install my-release ./my-chart -n app --create-namespace --wait --atomic
helm diff upgrade my-release ./my-chart -n app -f values-prod.yaml  # cần plugin helm diff
helm status my-release -n app
helm history my-release -n app
helm rollback my-release 1 -n app
helm get values my-release -n app
helm get manifest my-release -n app
helm uninstall my-release -n app
```

## Chart structure

```text
service-chart/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── NOTES.txt
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   └── tests/
│       └── test-connection.yaml
└── charts/
```

## `Chart.yaml` skeleton

```yaml
apiVersion: v2
name: service-chart
description: Reusable microservice chart
type: application
version: 0.1.0
appVersion: "1.0.0"
```

Version meaning:

| Field | Meaning |
|---|---|
| `version` | Version của chart package |
| `appVersion` | Version mặc định của app được chart deploy |
| `type: application` | Chart deploy một app |
| `type: library` | Chart chỉ cung cấp helper/templates dùng lại |

## Values precedence

Từ thấp đến cao:

```text
Chart values.yaml
  < parent chart values
  < -f base.yaml
  < -f env.yaml
  < --set key=value
  < --set-string key=value
```

Debug final values:

```bash
helm get values <release> -n <namespace>
helm get values <release> -n <namespace> --all
```

## Common values shape

```yaml
replicaCount: 2

image:
  repository: ghcr.io/acme/order-service
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: false
  className: traefik
  hosts:
  - host: order.local
    paths:
    - path: /
      pathType: Prefix

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 256Mi

podSecurityContext:
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
```

## Helper patterns

Name helper:

```gotemplate
{{- define "service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
```

Fullname helper:

```gotemplate
{{- define "service.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "service.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
```

Common labels:

```gotemplate
{{- define "service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
```

Selector labels:

```gotemplate
{{- define "service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

Rule: selector labels phải ổn định qua upgrade.

## Useful template functions

| Function | Use case |
|---|---|
| `default` | Default value nếu value rỗng |
| `required` | Fail render nếu thiếu value bắt buộc |
| `include` | Gọi named template/helper |
| `toYaml` | Render object/list thành YAML |
| `nindent` | Indent YAML block |
| `quote` | Quote string |
| `tpl` | Render string value như template, dùng thận trọng |
| `lookup` | Đọc object live từ cluster, tránh lạm dụng |

Example:

```gotemplate
{{- with .Values.resources }}
resources:
{{- toYaml . | nindent 10 }}
{{- end }}
```

## Debug render

```bash
helm template api ./chart -f values.yaml --debug > rendered.yaml
kubectl apply --dry-run=server -f rendered.yaml
kubectl diff -f rendered.yaml
```

Nếu dùng plugin `helm diff`, xem thay đổi ở lớp Helm trước khi upgrade:

```bash
helm diff upgrade api ./chart -n app -f values.yaml
```

Plugin này là optional. Trong CI production, nó hữu ích để reviewer thấy manifest diff nhưng không thay thế server-side dry-run hoặc policy check.

Common render errors:

| Error | Likely cause |
|---|---|
| `nil pointer evaluating interface` | Truy cập nested value không tồn tại |
| `yaml: line ... did not find expected key` | Indentation/template block sai |
| `required value is missing` | `required` helper fail |
| `can't evaluate field` | Sai scope trong `range`/`with` |

## Release troubleshooting

```bash
helm list -A
helm status <release> -n <namespace>
helm history <release> -n <namespace>
helm get manifest <release> -n <namespace>
helm get hooks <release> -n <namespace>
kubectl get all -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Status interpretation:

| Status | Meaning |
|---|---|
| `deployed` | Last operation succeeded |
| `failed` | Install/upgrade failed |
| `pending-install` | Install chưa hoàn tất |
| `pending-upgrade` | Upgrade chưa hoàn tất |
| `superseded` | Revision cũ đã bị revision mới thay thế |

## Hooks reference

Annotation example:

```yaml
metadata:
  annotations:
    "helm.sh/hook": pre-upgrade
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
```

Use hooks for:

- Short preflight job.
- Idempotent migration.
- Smoke test.

Avoid hooks for:

- Long-running controllers.
- Non-idempotent destructive DB migration.
- Business workflow that should be managed outside release lifecycle.

## Lab cleanup pattern

```bash
helm uninstall <release> -n <namespace>
kubectl delete namespace <namespace>
```
