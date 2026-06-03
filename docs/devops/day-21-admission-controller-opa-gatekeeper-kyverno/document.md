# Day 21: Document — Admission Controller, OPA/Gatekeeper, Kyverno

## 1. Admission Controller Flow — Quick Reference

```
kubectl apply -f pod.yaml
        │
        ▼
┌─────────────────┐
│  Authentication  │ ← Ai đang gọi? (ServiceAccount, User certificate)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Authorization   │ ← RBAC: có quyền tạo Pod không?
└────────┬────────┘
         ▼
┌─────────────────┐
│ Mutating Admission│ ← Sửa request (inject sidecar, thêm labels)
│  (tuần tự)       │   Kyverno mutate, Istio inject
└────────┬────────┘
         ▼
┌─────────────────┐
│ Schema Validation│ ← YAML có đúng format không?
└────────┬────────┘
         ▼
┌─────────────────┐
│Validating Admission│ ← Kiểm tra policy (block privileged, require labels)
│  (song song)       │   Kyverno validate, Gatekeeper
└────────┬────────┘
         ▼
┌─────────────────┐
│   etcd Persist   │ ← Lưu object vào etcd
└─────────────────┘
```

---

## 2. OPA/Gatekeeper vs Kyverno — Comparison Matrix

| Tiêu chí | OPA/Gatekeeper | Kyverno |
|----------|----------------|---------|
| **CNCF Status** | Graduated | Incubating |
| **Policy Language** | Rego (DSL) | Native Kubernetes YAML |
| **Learning Curve** | Cao (cần học Rego) | Thấp (YAML quen thuộc) |
| **Objects per Policy** | 2 (ConstraintTemplate + Constraint) | 1 (ClusterPolicy) |
| **Validate** | ✅ | ✅ |
| **Mutate** | ✅ (limited, Gatekeeper mutation) | ✅ (first-class) |
| **Generate Resources** | ❌ | ✅ |
| **Verify Images** | ❌ (cần external tool) | ✅ (cosign, notary built-in) |
| **Audit Existing Resources** | ✅ (audit controller) | ✅ (background scan + PolicyReport) |
| **Report Format** | Gatekeeper audit logs | PolicyReport CRD (standard) |
| **Multi-platform** | ✅ (OPA cho Terraform, Envoy, API) | ❌ (Kubernetes only) |
| **Webhook Type** | Validating (+ Mutating beta) | Both Mutating + Validating |
| **External Data** | ✅ (OPA bundles) | ✅ (API calls, ConfigMap) |
| **Performance (simple policy)** | ~5-10ms | ~5-15ms |
| **Performance (complex policy)** | Tốt hơn (Rego compiled) | Tốt cho hầu hết cases |
| **Community Policies** | [OPA Library](https://github.com/open-policy-agent/gatekeeper-library) | [Kyverno Policies](https://kyverno.io/policies/) |
| **Install Size** | ~200MB memory | ~256MB memory |
| **HA Support** | ✅ | ✅ |

### Decision Framework

```
Cần policy cho cả Terraform/Envoy/API gateway?
  ├── YES → OPA/Gatekeeper (+ OPA cho non-K8s)
  └── NO → Team quen Rego?
              ├── YES → Gatekeeper OK
              └── NO → Cần mutate/generate?
                          ├── YES → Kyverno
                          └── NO → Kyverno (simpler) hoặc Gatekeeper
```

---

## 3. Kyverno Policy Cheat Sheet

### Policy Structure

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy          # hoặc Policy (namespace-scoped)
metadata:
  name: policy-name
  annotations:
    policies.kyverno.io/title: "Human-readable title"
    policies.kyverno.io/severity: high|medium|low
    policies.kyverno.io/category: "Security|Best Practices|..."
spec:
  validationFailureAction: Enforce|Audit
  background: true|false      # Scan existing resources?
  rules:
    - name: rule-name
      match:                  # Resources to match
        any:
          - resources:
              kinds: [Pod, Deployment]
              namespaces: [production]
              names: ["app-*"]
              selector:
                matchLabels:
                  app: web
      exclude:                # Resources to exclude
        any:
          - resources:
              namespaces: [kube-system]
      validate:               # hoặc mutate, generate, verifyImages
        message: "Error message"
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    memory: "?*"
```

### Common Patterns

| Pattern | Ý nghĩa |
|---------|---------|
| `"?*"` | Field phải tồn tại và có giá trị |
| `"!value"` | Field không được bằng value |
| `"value1\|value2"` | Field phải match 1 trong các values |
| `"prefix*"` | Field phải bắt đầu bằng prefix |
| `"*suffix"` | Field phải kết thúc bằng suffix |
| `">=0 & <=100"` | Range check cho số |
| `=(field)` | Chỉ check nếu field tồn tại (optional) |
| `+(field)` | Thêm field nếu chưa tồn tại (mutate) |

### Rule Types

```yaml
# VALIDATE — chặn violations
validate:
  message: "Error msg"
  pattern: { ... }           # Pattern match
  # hoặc
  deny:
    conditions:
      any:
        - key: "{{request.object.spec.replicas}}"
          operator: GreaterThan
          value: 10

# MUTATE — sửa resources
mutate:
  patchStrategicMerge:
    metadata:
      labels:
        +(managed-by): kyverno    # Thêm nếu chưa có
  # hoặc
  patchesJson6902: |
    - op: add
      path: /metadata/annotations/timestamp
      value: "{{time.Now()}}"

# GENERATE — tạo resource khi trigger
generate:
  apiVersion: networking.k8s.io/v1
  kind: NetworkPolicy
  name: default-deny
  namespace: "{{request.object.metadata.name}}"
  data:
    spec:
      podSelector: {}
      policyTypes: [Ingress]

# VERIFY IMAGES — kiểm tra image signature
verifyImages:
  - imageReferences: ["gcr.io/mycompany/*"]
    attestors:
      - entries:
          - keys:
              publicKeys: |-
                -----BEGIN PUBLIC KEY-----
                ...
                -----END PUBLIC KEY-----
```

---

## 4. Gatekeeper Quick Reference

### ConstraintTemplate (define policy logic)

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8s<policyname>          # lowercase
spec:
  crd:
    spec:
      names:
        kind: K8s<PolicyName>    # CamelCase
      validation:
        openAPIV3Schema:         # Parameters schema
          type: object
          properties:
            <param>:
              type: <type>
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8s<policyname>
        violation[{"msg": msg}] {
          # Rego logic
          # input.review.object = the K8s resource
          # input.parameters = constraint parameters
          msg := "violation message"
        }
```

### Constraint (apply policy)

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8s<PolicyName>
metadata:
  name: <constraint-name>
spec:
  enforcementAction: deny|warn|dryrun
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
    excludedNamespaces: ["kube-system"]
    namespaces: ["production"]
  parameters:
    <param>: <value>
```

### Common Rego Patterns

```rego
# Access resource fields
input.review.object.metadata.labels["team"]
input.review.object.spec.containers[_].image

# Check label exists
provided := {l | input.review.object.metadata.labels[l]}
required := {l | l := input.parameters.labels[_]}
missing := required - provided
count(missing) > 0

# Check image prefix
not startswith(container.image, "gcr.io/trusted/")

# Check numeric value
to_number(container.resources.limits.cpu) > 4
```

---

## 5. Production Checklist

### Pre-deployment

- [ ] Policy đã test trên dev/staging cluster
- [ ] Policy bắt đầu ở **Audit** mode (không Enforce)
- [ ] Exclude `kube-system`, policy engine namespace, và critical namespaces
- [ ] `failurePolicy` set phù hợp (Fail cho critical, Ignore cho non-critical)
- [ ] `timeoutSeconds` ≤ 10s
- [ ] Policy engine có `replicas >= 2` cho HA
- [ ] PodDisruptionBudget cho policy engine
- [ ] Resource requests/limits cho policy engine pods

### Rollout Process

```
1. Deploy policy ở Audit mode
   ↓
2. Chạy background scan (1-7 ngày)
   ↓
3. Review PolicyReport / audit violations
   ↓
4. Fix existing violations hoặc add exceptions
   ↓
5. Communicate với teams về upcoming Enforce
   ↓
6. Switch sang Enforce (off-peak hours)
   ↓
7. Monitor rejection rate 24-48h
   ↓
8. Đặt alert cho webhook errors
```

### Monitoring

| Metric | Alert khi |
|--------|-----------|
| Webhook latency P99 | > 500ms |
| Webhook error rate | > 1% |
| Policy engine pod restarts | > 0 in 1h |
| Rejection rate (unexpected) | Spike đột ngột |
| Policy engine memory | > 80% limit |

### Emergency Procedures

```bash
# 1. Switch policy sang Audit (nhanh, an toàn)
kubectl patch clusterpolicy <name> --type merge \
  -p '{"spec":{"validationFailureAction":"Audit"}}'

# 2. Nếu webhook service down, bypass webhook
kubectl delete validatingwebhookconfiguration <webhook-name>

# 3. Scale up policy engine
kubectl scale deployment kyverno -n kyverno --replicas=3

# 4. Check webhook configs
kubectl get validatingwebhookconfiguration -o yaml
kubectl get mutatingwebhookconfiguration -o yaml
```

---

## 6. Common Policy Templates

### Security Policies

| Policy | Mô tả | Priority |
|--------|--------|----------|
| Disallow privileged | Chặn `privileged: true` | 🔴 Critical |
| Disallow hostPID/hostIPC | Chặn share PID/IPC namespace | 🔴 Critical |
| Disallow hostNetwork | Chặn `hostNetwork: true` | 🔴 Critical |
| Require runAsNonRoot | Bắt buộc non-root | 🟡 Important |
| Require readOnlyRootFilesystem | Filesystem read-only | 🟢 Nice-to-have |
| Restrict image registries | Chỉ cho trusted registries | 🔴 Critical |
| Disallow latest tag | Chặn `image:latest` | 🟡 Important |
| Require image digest | Bắt buộc `image@sha256:...` | 🟢 Nice-to-have |

### Operational Policies

| Policy | Mô tả | Priority |
|--------|--------|----------|
| Require resource limits | CPU + memory required | 🔴 Critical |
| Require liveness probe | Health check required | 🟡 Important |
| Require labels | `team`, `environment`, `cost-center` | 🟡 Important |
| Restrict replicas | Min 2 replicas trong production | 🟡 Important |
| Require PDB | PodDisruptionBudget required | 🟢 Nice-to-have |

---

## 7. Debugging Commands

```bash
# === KYVERNO ===

# List policies và trạng thái
kubectl get clusterpolicy
kubectl get policy -A

# Xem chi tiết policy
kubectl describe clusterpolicy <name>

# Xem violations (PolicyReport)
kubectl get policyreport -A
kubectl get clusterpolicyreport

# Xem chi tiết violation
kubectl get policyreport -n <ns> -o yaml

# Kyverno logs
kubectl logs -n kyverno deployment/kyverno -f

# Test policy without applying (Kyverno CLI)
kyverno apply policy.yaml --resource resource.yaml

# === GATEKEEPER ===

# List constraints
kubectl get constraints

# Xem violations
kubectl get <ConstraintKind> <name> -o yaml
# violations nằm trong .status.violations

# Gatekeeper audit logs
kubectl logs -n gatekeeper-system deployment/gatekeeper-audit -f

# Gatekeeper controller logs
kubectl logs -n gatekeeper-system deployment/gatekeeper-controller-manager -f

# === COMMON ===

# Xem webhook configurations
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration

# Xem webhook chi tiết (rules, failurePolicy, timeout)
kubectl get validatingwebhookconfiguration <name> -o yaml

# API server admission metrics
kubectl get --raw /metrics | grep apiserver_admission_webhook

# Check nếu webhook đang block
kubectl get events --field-selector reason=FailedCreate -A
```

