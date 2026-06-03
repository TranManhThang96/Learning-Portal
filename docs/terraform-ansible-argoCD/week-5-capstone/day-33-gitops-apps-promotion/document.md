# Day 33 — GitOps Apps Layer & Promotion Strategy: Reference Document

## 1. Apps Repo Structure Reference

### Complete Directory Tree

```
apps-repo/
├── .github/
│   └── workflows/
│       ├── ci-build-push.yml        # Build + push image
│       ├── promote-staging.yml      # PR-triggered: bump tag → staging
│       └── promote-production.yml   # Manual dispatch: bump tag → prod
│
├── services/                        # Mỗi service = 1 Helm chart + overlays
│   ├── api-service/
│   │   ├── base/                   # Helm chart (immutable, versioned)
│   │   │   ├── Chart.yaml
│   │   │   ├── values.yaml         # Defaults cho tất cả env
│   │   │   └── templates/
│   │   │       ├── _helpers.tpl
│   │   │       ├── deployment.yaml
│   │   │       ├── service.yaml
│   │   │       ├── hpa.yaml
│   │   │       └── pdb.yaml
│   │   └── overlays/               # Kustomize patches (env-specific)
│   │       ├── dev/
│   │       │   ├── kustomization.yaml
│   │       │   └── values-overrides.yaml
│   │       ├── staging/
│   │       │   ├── kustomization.yaml
│   │       │   └── values-overrides.yaml
│   │       └── prod/
│   │           ├── kustomization.yaml
│   │           └── values-overrides.yaml
│   ├── worker-service/             # Tương tự api-service
│   └── frontend-service/           # Tương tự api-service
│
└── appsets/                        # ArgoCD ApplicationSet definitions
    ├── services-generator.yaml      # Generator-driven: tự phát hiện service
    ├── services-staging.yaml
    └── services-production.yaml
```

### Ownership Boundary

| Folder | Owner | Nên thay đổi khi |
|---|---|---|
| `services/<name>/base/` | Service team | Helm chart logic thay đổi |
| `services/<name>/overlays/dev/` | Developer | Dev config thay đổi |
| `services/<name>/overlays/staging/` | CI/CD + Dev | Tag promotion |
| `services/<name>/overlays/prod/` | Platform + Lead Dev | Production release |
| `appsets/` | Platform Eng | Thêm cluster mới |

---

## 2. Helm Chart Complete Reference

### Chart.yaml

```yaml
apiVersion: v2                    # Helm 3 required
name: api-service
description: API service for capstone platform
type: application
version: 0.1.0                   # Chart version (semver)
appVersion: "v1.0.0"            # Application version (image tag reference)
```

### values.yaml Full Reference

```yaml
# ─── REPLICAS ───
replicaCount: 2

# ─── IMAGE ───
image:
  repository: ghcr.io/<org>/api-service
  tag: "v1.0.0"                  # Override by env overlay
  pullPolicy: IfNotPresent       # Options: Always / IfNotPresent / Never

# ─── SERVICE ───
service:
  port: 8080
  type: ClusterIP               # Options: ClusterIP / NodePort / LoadBalancer
  annotations: {}

# ─── INGRESS ───
ingress:
  enabled: true
  className: nginx
  host: api.capstone.local
  path: /
  tls:
    enabled: false
    secretName: api-tls

# ─── PROBES ───
probes:
  livenessPath: /health/live
  readinessPath: /health/ready
  startupPath: /health/startup
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

# ─── RESOURCES ───
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# ─── AUTOSCALING ───
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

# ─── SECURITY ───
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false  # Set true in prod
  capabilities:
    drop:
      - ALL

# ─── SERVICE ACCOUNT ───
serviceAccount:
  create: true
  name: api-service-sa
  annotations:
    # IRSA annotation for AWS
    eks.amazonaws.com/role-arn: arn:aws:iam::123456:role/api-service-role

# ─── ENVIRONMENT VARIABLES ───
env:
  - name: LOG_LEVEL
    value: info
  - name: DB_HOST
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: host
```

### Deployment Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "api-service.fullname" . }}
  labels:
    app.kubernetes.io/name: {{ include "api-service.name" . }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
    app.kubernetes.io/managed-by: {{ .Release.Service }}
spec:
  replicas: {{ .Values.replicaCount }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ include "api-service.name" . }}
      app.kubernetes.io/instance: {{ .Release.Name }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        app.kubernetes.io/name: {{ include "api-service.name" . }}
        app.kubernetes.io/instance: {{ .Release.Name }}
        app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion }}
    spec:
      {{- with .Values.podSecurityContext }}
      securityContext:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.serviceAccount }}
      serviceAccountName: {{ .name }}
      {{- end }}
      terminationGracePeriodSeconds: 30
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          {{- if .Values.probes }}
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.livenessPath }}
              port: http
            initialDelaySeconds: {{ .Values.probes.initialDelaySeconds }}
            periodSeconds: {{ .Values.probes.periodSeconds }}
            failureThreshold: {{ .Values.probes.failureThreshold }}
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readinessPath }}
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          {{- end }}
          {{- with .Values.env }}
          env:
            {{- toYaml . | nindent 12 }}
          {{- end }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          {{- with .Values.securityContext }}
          securityContext:
            {{- toYaml . | nindent 12 }}
          {{- end }}
```

---

## 3. Kustomize Overlay Reference

### Dev Overlay

```yaml
# services/api-service/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: dev

patches:
  # Override replicas
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      spec:
        replicas: 1
        strategy:
          type: Recreate   # Dev: recreate OK, no traffic
    target:
      kind: Deployment
      labelSelector: "app.kubernetes.io/name=api-service"

  # Add dev-specific env vars
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      spec:
        template:
          spec:
            containers:
              - name: api-service
              env:
                - name: LOG_LEVEL
                  value: debug
    target:
      kind: Deployment

images:
  - name: ghcr.io/<org>/api-service
    newTag: "dev-latest"

configMapGenerator:
  - name: api-config
    behavior: merge
    literals:
      - ENV=development
      - DEBUG=true
```

### Staging Overlay

```yaml
# services/api-service/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-staging

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: staging

patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      spec:
        replicas: 2
    target:
      kind: Deployment

images:
  - name: ghcr.io/<org>/api-service
    newTag: "v1.0.0"    # Update qua promotion PR
```

### Prod Overlay

```yaml
# services/api-service/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: api-service-prod

resources:
  - ../../base

commonLabels:
  app.kubernetes.io/environment: prod

patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      spec:
        replicas: 3
    target:
      kind: Deployment

images:
  - name: ghcr.io/<org>/api-service
    newTag: "v1.0.0"    # CRITICAL: immutable tag, never latest

# Prod: replicas cao hơn, resources lớn hơn
replicas:
  - name: api-service
    count: 3
```

---

## 4. ApplicationSet Generator Reference

### Git Generator — Full Example

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-all-envs
  namespace: argocd
spec:
  # ── Git Generator: phát hiện service tự động ──
  generators:
    - git:
        repoURL: https://github.com/<org>/apps-repo.git
        revision: HEAD
        directories:
          # Quét tất cả overlay directory
          - path: services/*/overlays/*
        # exclude: loại trừ folder nhất định
        # exclude: [path: services/legacy/*]
        fileMark: kustomization.yaml
        # Chỉ match directories chứa kustomization.yaml

  template:
    metadata:
      name: "{{path.basenameNormalized}}-{{path.basename}}"
      # path.basenameNormalized: api-service, worker-service, ...
      # path.basename: dev, staging, prod
      labels:
        apps-group: microservices
      annotations:
        argocd.argoproj.io/manifest-generate-paths: "."
    spec:
      project: "{{path.basename}}"  # dev-project, staging-project, prod-project
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: "{{path}}"
        kustomize:
          nameSuffix: ""           # Không thêm suffix
          commonLabels:            # Merge labels, không override
            argocd.argoproj.io/manifest-generate-paths: "."
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basenameNormalized}}-{{path.basename}}"
      syncPolicy:
        syncOptions:
          - CreateNamespace=true
          - ApplyOutOfSyncOnly=true
          - PruneLast=true
        retry:
          limit: 5
          backoff:
            duration: 5s
            factor: 2
            maxDuration: 3m
        # automated: chỉ enable cho dev
        {{- if eq (last (splitList "-" (last (splitList "/" .path)))) "dev" }}
        automated:
          prune: true
          selfHeal: true
        {{- end }}
```

### ApplicationSet per Environment (Separated)

```yaml
# appsets/services-dev.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices-dev
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/<org>/apps-repo.git
        revision: HEAD
        directories:
          - path: services/*/overlays/dev

  template:
    metadata:
      name: "{{path.basenameNormalized}}-dev"
    spec:
      project: default
      source:
        repoURL: https://github.com/<org>/apps-repo.git
        targetRevision: HEAD
        path: "{{path}}"
        kustomize: {}
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basenameNormalized}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true

---
# appsets/services-staging.yaml — giống nhưng không automated
# appsets/services-prod.yaml — thêm spec.syncPolicy.automated.approval
```

---

## 5. Promotion Workflow Reference

### Promotion State Machine

```
DEV                           STAGING                       PROD
 │                               │                            │
 ▼                               │                            │
 [CI: build + push]              │                            │
 │                               │                            │
 ▼                               │                            │
 Auto-sync ArgoCD                │                            │
 (triggers on every commit)       │                            │
 │                               │                            │
 ▼                               │                            │
 Dev deployed & verified          │                            │
 │                               │                            │
 ▼                               ▼                            │
                    Dev Engineer creates PR
                    (update tag in staging kustomization)
                    │
                    ▼
                    CI: lint + test + scan
                    │
                    ▼
                    Reviewer approves PR
                    │
                    ▼
                    CI commits tag update to main
                    │
                    ▼
                    ArgoCD detects drift
                    (staging: no automated sync)
                    │
                    ▼
                    Manual sync or auto-sync
                    │
                    ▼
                    Staging deployed & verified
                    │
                    ▼
                    Platform Lead creates production PR
                    (update tag in prod kustomization)
                    │
                    ▼
                    ArgoCD requires manual approval
                    │
                    ▼
                    Approved → sync
                    │
                    ▼
                    Production deployed
```

### PR Template cho Promotion

```markdown
## Promotion: `<service>` → `<environment>`

### Version Information

| Field | Value |
|---|---|
| Image | `{{ image }}` |
| Tag | `{{ tag }}` |
| Git Commit | `{{ sha }}` |
| Previous Tag | `{{ prev_tag }}` |

### CI Pipeline

- [ ] Lint (terraform fmt, kustomize build)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Security scan (Trivy)
- [ ] Image scan (Grype)

### Environment-Specific Notes

<!-- Thêm note nếu có breaking change, config khác biệt, etc. -->

### Rollback Plan

<!-- Cách rollback nếu deployment có vấn đề -->

### Verification Steps

- [ ] Application synced successfully
- [ ] Pods Running
- [ ] Health check passed
- [ ] Smoke test passed
- [ ] Monitoring dashboard verified
```

---

## 6. Rollback Reference

### Rollback Strategy Comparison

| Method | Use case | Speed | Audit trail | ArgoCD revision |
|---|---|---|---|---|
| `git revert` | Standard rollback | Slower (3-5 min) | Full | Correct |
| `argocd app sync --revision N` | Emergency | Fast (seconds) | None (if not committed) | Correct |
| Manual kubectl apply | Last resort | Fastest | None | Broken |

### Rollback Playbook

```bash
#!/bin/bash
# rollback.sh — Emergency rollback script

SERVICE=$1
ENV=$2
TARGET_REVISION=${3:-""}  # Optional: specify revision

if [[ -z "$SERVICE" || -z "$ENV" ]]; then
  echo "Usage: rollback.sh <service> <env> [revision]"
  exit 1
fi

APP="${SERVICE}-${ENV}"

echo "=== Rolling back ${APP} ==="

# Option 1: Rollback via Git revert
if [[ -z "$TARGET_REVISION" ]]; then
  echo "Reverting last commit..."
  git revert HEAD --no-edit
  git push origin main
  echo "Git revert committed. ArgoCD will sync."
  argocd app sync ${APP} --force
else
  # Option 2: Emergency ArgoCD sync
  echo "Emergency sync to revision ${TARGET_REVISION}..."
  argocd app sync ${APP} --revision ${TARGET_REVISION}

  # Then: immediately commit Git revert to maintain audit trail
  echo "Creating Git revert for audit trail..."
  git revert HEAD --no-edit
  git push origin main
fi

echo "=== Monitoring health ==="
argocd app get ${APP} --watch
```

---

## 7. Image Tag Strategy Reference

### CI Pipeline Tag Convention

```yaml
# .github/workflows/build.yml (relevant section)
- name: Push image with multiple tags
  run: |
    # Primary tag: semver (from git tag or package.json version)
    docker tag ${{ env.IMAGE }} ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ env.VERSION }}

    # SHA tag: 100% deterministic, immutable
    docker tag ${{ env.IMAGE }} ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ github.sha }}

    # Environment tags
    docker tag ${{ env.IMAGE }} ${{ env.REGISTRY }}/${{ env.IMAGE }}:dev-latest
    docker tag ${{ env.IMAGE }} ${{ env.REGISTRY }}/${{ env.IMAGE }}:staging

    # Push all
    docker push ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ env.VERSION }}
    docker push ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ github.sha }}
    docker push ${{ env.REGISTRY }}/${{ env.IMAGE }}:dev-latest
    docker push ${{ env.REGISTRY }}/${{ env.IMAGE }}:staging
```

### Tag Usage by Environment

| Environment | Tag Pattern | Source | Update trigger |
|---|---|---|---|
| dev | `dev-latest` | Always latest build | Every commit to main |
| staging | `vX.Y.Z` (semver) | Approved release | PR merge to main |
| prod | `vX.Y.Z` (semver) | Staging-verified | Manual approval |

### Tag Naming Rules

```
1. Production tag PHẢI match git tag (semver format)
2. Tag KHÔNG bao giờ reused (immutable)
3. Tag luôn có 3 octets: vMAJOR.MINOR.PATCH
4. Pre-release tags: v1.0.0-rc.1, v1.0.0-beta.2
5. Tag annotation trong Helm chart phải match: appVersion
```

---

## 8. Security Checklist cho Apps Layer

```markdown
## Pre-deployment Security Checklist

### Image Security
- [ ] Image scan passed (Trivy/Grype — no HIGH/CRITICAL vulnerabilities)
- [ ] Image tag is immutable (not `latest` for prod)
- [ ] Image pull secret configured for private registry
- [ ] `imagePullPolicy: IfNotPresent` with immutable tags; use registry immutability to prevent tag overwrite

### RBAC / Service Account
- [ ] ServiceAccount not using `default` SA
- [ ] IRSA annotation present (for AWS: `eks.amazonaws.com/role-arn`)
- [ ] Pod has explicit securityContext
- [ ] runAsNonRoot: true
- [ ] runAsUser: non-zero (e.g., 1000)
- [ ] capabilities.drop: ALL
- [ ] allowPrivilegeEscalation: false

### Network Policy
- [ ] NetworkPolicy restricts inbound traffic
- [ ] No privileged ports
- [ ] Egress allowed only to required destinations

### Secrets
- [ ] No hard-coded secrets in values.yaml
- [ ] Secrets loaded via External Secrets Operator
- [ ] Secrets not committed to Git

### Resource Limits
- [ ] Memory limit set (prevent OOMKill DoS)
- [ ] CPU limit set (prevent CPU starvation of other pods)
- [ ] No `*-unlimited` resources in prod
```

---

## 9. Cost Optimization Reference

| Config | Dev | Staging | Production |
|---|---|---|---|
| Replicas | 1 | 2 | 3+ |
| Memory request | 64Mi | 128Mi | 256Mi |
| Memory limit | 256Mi | 512Mi | 1Gi |
| CPU request | 50m | 100m | 200m |
| HPA | Disabled | Disabled | Enabled |
| PDB | Disabled | Disabled | Enabled (minAvailable: 1) |
| PodDisruptionBudget | None | None | 1 |

---

## 10. ArgoCD Sync Policy Matrix

| Setting | dev | staging | prod |
|---|---|---|---|
| automated.sync | Enabled | Disabled | Disabled |
| automated.prune | true | false | false |
| automated.selfHeal | true | false | false |
| automated.approval | - | - | Required |
| syncPolicy.retry | true | false | true |
| syncOptions.CreateNamespace | true | true | true |
| syncOptions.ApplyOutOfSyncOnly | false | true | true |

---

## 11. Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---|---|---|
| Application OutOfSync forever | Kustomize path wrong | Check `spec.source.path` matches overlay directory |
| ApplicationSet not generating apps | Git repo not accessible | Check ArgoCD repo credentials + network |
| Image pull error | Image tag not found | Verify tag exists in registry |
| Pod CrashLoopBackOff | Liveness probe failing | `kubectl logs` + check probe path |
| ArgoCD shows healthy but pod not running | Sync policy miss | Check `kubectl get pods` directly |
| Multiple apps with same name | Generator path overlap | Check ApplicationSet paths don't overlap |
| Sync stuck "Waiting" | Sync policy needs approval | `argocd app approve-sync <app>` |
