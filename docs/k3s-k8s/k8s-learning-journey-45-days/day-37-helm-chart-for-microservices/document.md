# Document - Day 37: Microservice Helm Chart Reference

## Recommended chart contract

```yaml
replicaCount: 2

image:
  repository: ghcr.io/acme/order-service
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: http

container:
  port: 8080

env:
  LOG_LEVEL: info
  FEATURE_X_ENABLED: "false"

envFrom:
  configMaps: []
  secrets: []

existingSecret: ""

probes:
  readiness:
    enabled: true
    path: /readyz
    initialDelaySeconds: 5
    periodSeconds: 10
  liveness:
    enabled: true
    path: /healthz
    initialDelaySeconds: 15
    periodSeconds: 20
  startup:
    enabled: false

resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 256Mi

ingress:
  enabled: false
  className: ""
  annotations: {}
  hosts: []

hpa:
  enabled: false
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

pdb:
  enabled: true
  minAvailable: 1

networkPolicy:
  enabled: false
```

## Required templates

| Template | Required | Notes |
|---|---:|---|
| `_helpers.tpl` | Yes | Names, labels, selector labels |
| `serviceaccount.yaml` | Yes | Default `automountServiceAccountToken: false` if possible |
| `deployment.yaml` | Yes | Image, env, probes, resources, security |
| `service.yaml` | Yes | Stable DNS and port mapping |
| `configmap.yaml` | Optional | Only render if config exists |
| `secret.yaml` | Lab only | Avoid plain secret in production |
| `ingress.yaml` | Optional | Controlled by `ingress.enabled` |
| `hpa.yaml` | Optional template, values-gated | Requires metrics stack |
| `pdb.yaml` | Optional template, values-gated | Be careful with replica 1 |
| `networkpolicy.yaml` | Optional | Requires CNI support |

## Deployment template excerpt

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "service.fullname" . }}
  labels:
    {{- include "service.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "service.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "service.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "service.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: {{ .Values.container.port }}
        {{- if or .Values.env .Values.existingSecret .Values.envFrom.configMaps .Values.envFrom.secrets }}
        envFrom:
        {{- if .Values.env }}
        - configMapRef:
            name: {{ include "service.fullname" . }}-config
        {{- end }}
        {{- if .Values.existingSecret }}
        - secretRef:
            name: {{ .Values.existingSecret }}
        {{- end }}
        {{- range .Values.envFrom.configMaps }}
        - configMapRef:
            name: {{ . }}
        {{- end }}
        {{- range .Values.envFrom.secrets }}
        - secretRef:
            name: {{ . }}
        {{- end }}
        {{- end }}
        {{- if .Values.probes.readiness.enabled }}
        readinessProbe:
          httpGet:
            path: {{ .Values.probes.readiness.path }}
            port: http
          initialDelaySeconds: {{ .Values.probes.readiness.initialDelaySeconds }}
          periodSeconds: {{ .Values.probes.readiness.periodSeconds }}
        {{- end }}
        {{- if .Values.probes.liveness.enabled }}
        livenessProbe:
          httpGet:
            path: {{ .Values.probes.liveness.path }}
            port: http
          initialDelaySeconds: {{ .Values.probes.liveness.initialDelaySeconds }}
          periodSeconds: {{ .Values.probes.liveness.periodSeconds }}
        {{- end }}
        {{- if .Values.probes.startup.enabled }}
        startupProbe:
          httpGet:
            path: {{ .Values.probes.startup.path }}
            port: http
          initialDelaySeconds: {{ .Values.probes.startup.initialDelaySeconds | default 0 }}
          periodSeconds: {{ .Values.probes.startup.periodSeconds | default 5 }}
          failureThreshold: {{ .Values.probes.startup.failureThreshold | default 30 }}
        {{- end }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
```

## Service template excerpt

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "service.fullname" . }}
  labels:
    {{- include "service.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
  - port: {{ .Values.service.port }}
    targetPort: {{ .Values.service.targetPort }}
    protocol: TCP
    name: http
  selector:
    {{- include "service.selectorLabels" . | nindent 4 }}
```

Nên dùng named target port cho HTTP service. Trong lab, `service.port: 8080`, `service.targetPort: http` và `container.port: 80` là hợp lệ vì `nginx` listen port 80 còn Service expose port 8080 trong cluster.

## ConfigMap conditional pattern

```gotemplate
{{- if .Values.env }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "service.fullname" . }}-config
data:
{{- range $key, $value := .Values.env }}
  {{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}
```

## Env pattern

```gotemplate
envFrom:
{{- if .Values.env }}
- configMapRef:
    name: {{ include "service.fullname" . }}-config
{{- end }}
{{- if .Values.existingSecret }}
- secretRef:
    name: {{ .Values.existingSecret }}
{{- end }}
{{- range .Values.envFrom.configMaps }}
- configMapRef:
    name: {{ . }}
{{- end }}
{{- range .Values.envFrom.secrets }}
- secretRef:
    name: {{ . }}
{{- end }}
```

## Probe template pattern

```gotemplate
{{- if .Values.probes.readiness.enabled }}
readinessProbe:
  httpGet:
    path: {{ .Values.probes.readiness.path }}
    port: http
  initialDelaySeconds: {{ .Values.probes.readiness.initialDelaySeconds }}
  periodSeconds: {{ .Values.probes.readiness.periodSeconds }}
{{- end }}
```

## HPA template

```yaml
{{- if .Values.hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "service.fullname" . }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "service.fullname" . }}
  minReplicas: {{ .Values.hpa.minReplicas }}
  maxReplicas: {{ .Values.hpa.maxReplicas }}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {{ .Values.hpa.targetCPUUtilizationPercentage }}
{{- end }}
```

## PDB template

```yaml
{{- if .Values.pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "service.fullname" . }}
spec:
  minAvailable: {{ .Values.pdb.minAvailable }}
  selector:
    matchLabels:
      {{- include "service.selectorLabels" . | nindent 6 }}
{{- end }}
```

## Environment values examples

Dev:

```yaml
replicaCount: 1
image:
  tag: dev-latest
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    memory: 128Mi
ingress:
  enabled: true
  className: traefik
  hosts:
  - host: order.local
    paths:
    - path: /
      pathType: Prefix
```

Prod:

```yaml
replicaCount: 3
image:
  tag: "1.4.7"
resources:
  requests:
    cpu: 300m
    memory: 512Mi
  limits:
    memory: 768Mi
hpa:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
pdb:
  enabled: true
  minAvailable: 2
existingSecret: order-service-prod
```

## `values.schema.json` minimal example

```json
{
  "$schema": "https://json-schema.org/schema#",
  "type": "object",
  "required": ["image", "service"],
  "properties": {
    "replicaCount": {
      "type": "integer",
      "minimum": 1
    },
    "image": {
      "type": "object",
      "required": ["repository", "tag"],
      "properties": {
        "repository": { "type": "string", "minLength": 1 },
        "tag": { "type": "string", "minLength": 1 }
      }
    },
    "service": {
      "type": "object",
      "required": ["port", "targetPort"],
      "properties": {
        "port": { "type": "integer", "minimum": 1, "maximum": 65535 },
        "targetPort": {
          "oneOf": [
            { "type": "integer", "minimum": 1, "maximum": 65535 },
            { "type": "string", "minLength": 1 }
          ]
        }
      }
    }
  }
}
```

Validate:

```bash
helm lint ./service-chart -f values-prod.yaml
```

## Debug matrix

| Symptom | Check |
|---|---|
| Pod Running but Service has no endpoints | Selector labels, readinessProbe |
| 502 from Ingress | Ingress class, Service port/targetPort, endpoints |
| Pod `Pending` | resources, node selector, affinity, quota |
| Pod `CrashLoopBackOff` | env/config/secret, command, probes, logs |
| Helm upgrade fails immutable field | selector/name changes in template |
| HPA unknown metrics | metrics-server, CPU requests |
| PDB blocks drain | replicas and `minAvailable` |

## Production chart review checklist

- [ ] Labels follow `app.kubernetes.io/*`.
- [ ] Selector labels are stable.
- [ ] Values do not contain plain production secrets.
- [ ] `resources.requests` exist.
- [ ] Memory limit exists where appropriate.
- [ ] Probes match real endpoints.
- [ ] `securityContext` is compatible with Pod Security profile.
- [ ] ServiceAccount token is disabled unless needed.
- [ ] Ingress class and cloud annotations are values-driven.
- [ ] HPA requires CPU request or external/custom metric.
- [ ] PDB does not block maintenance for replica 1.
- [ ] Chart has schema or lint rules for required values.
