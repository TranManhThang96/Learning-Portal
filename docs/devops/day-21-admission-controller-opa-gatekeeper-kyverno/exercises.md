# Day 21: Exercises — Admission Controller, OPA/Gatekeeper, Kyverno

---

## Bài 1: Easy — Deploy Kyverno và Viết Policy Cơ Bản

### Context

Bạn được giao nhiệm vụ setup policy engine cho dev cluster. Team lead yêu cầu bắt đầu với 2 policy đơn giản: chặn privileged pod và bắt buộc resource limits.

### Yêu cầu

1. Cài Kyverno lên local kind cluster.
2. Viết `ClusterPolicy` chặn pod có `securityContext.privileged: true`.
3. Viết `ClusterPolicy` bắt buộc mọi container phải có `resources.requests` và `resources.limits` (CPU + memory).
4. Test cả 2 policy bằng cách tạo pod vi phạm và pod hợp lệ.
5. Exclude namespace `kube-system` và `kyverno` khỏi cả 2 policy.

### Expected Outcome

- Pod privileged bị chặn với error message rõ ràng.
- Pod không có resources bị chặn.
- Pod hợp lệ (non-privileged + có resources) được tạo thành công.
- System pods trong `kube-system` không bị ảnh hưởng.

### Hint

- Dùng `helm install` để cài Kyverno.
- Dùng `spec.exclude.any` để loại trừ namespace.
- Dùng pattern `"?*"` trong Kyverno để match "field phải có giá trị".

### Acceptance Criteria

- [ ] Kyverno pod Running.
- [ ] 2 ClusterPolicy ở trạng thái Ready.
- [ ] `kubectl apply` pod privileged → bị reject với message.
- [ ] `kubectl run` pod không có resources → bị reject.
- [ ] `kubectl run` pod hợp lệ → tạo thành công.
- [ ] CoreDNS và các pod `kube-system` vẫn chạy bình thường.

### Bonus Challenge

Thêm policy thứ 3: bắt buộc mọi Deployment phải có annotation `owner` với format email (regex: `.*@.*\..*`).

<details>
<summary>Solution</summary>

```bash
# 1. Tạo cluster
kind create cluster --name policy-exercise

# 2. Cài Kyverno
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=1

# Chờ Kyverno ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kyverno -n kyverno --timeout=120s
```

```yaml
# policy-disallow-privileged.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: deny-privileged
      match:
        any:
          - resources:
              kinds:
                - Pod
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Privileged containers are not allowed."
        pattern:
          spec:
            containers:
              - =(securityContext):
                  =(privileged): false
```

```yaml
# policy-require-resources.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resources
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-requests-limits
      match:
        any:
          - resources:
              kinds:
                - Pod
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "CPU and memory requests/limits are required."
        pattern:
          spec:
            containers:
              - resources:
                  requests:
                    memory: "?*"
                    cpu: "?*"
                  limits:
                    memory: "?*"
                    cpu: "?*"
```

```bash
# Apply policies
kubectl apply -f policy-disallow-privileged.yaml
kubectl apply -f policy-require-resources.yaml

# Verify policies ready
kubectl get clusterpolicy

# Test 1: privileged pod → should fail
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: bad-privileged
spec:
  containers:
    - name: nginx
      image: nginx:1.25
      securityContext:
        privileged: true
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          cpu: 200m
          memory: 256Mi
EOF
# Expected: DENIED

# Test 2: no resources → should fail
kubectl run bad-no-resources --image=nginx:1.25
# Expected: DENIED

# Test 3: valid pod → should succeed
kubectl run good-pod --image=nginx:1.25 \
  --requests='cpu=100m,memory=128Mi' \
  --limits='cpu=200m,memory=256Mi'
# Expected: Created

# Test 4: kube-system unaffected
kubectl get pods -n kube-system
# Expected: all Running
```

**Bonus — require owner annotation:**

```yaml
# policy-require-owner.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-owner-annotation
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-owner-email
      match:
        any:
          - resources:
              kinds:
                - Deployment
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Annotation 'owner' with valid email is required."
        pattern:
          metadata:
            annotations:
              owner: "*@*.*"
```

</details>


---

## Bài 2: Medium — Multi-Policy Setup với Audit → Enforce Workflow

### Context

Bạn là DevOps engineer cho một team 30 developers. Team vừa migrate lên Kubernetes và có nhiều workload không tuân thủ best practices. Bạn cần rollout policy dần dần: bắt đầu **Audit** mode để xem violation, sau đó chuyển sang **Enforce**.

### Yêu cầu

1. Cài Kyverno và deploy 4 policies ở **Audit** mode:
   - Require labels: `team`, `environment` trên mọi Deployment.
   - Require resource requests/limits.
   - Disallow `hostNetwork: true`.
   - Restrict image sources: chỉ cho phép images từ `docker.io/library/` và `nginx` (trusted registry simulation).

2. Deploy 3 workloads vi phạm khác nhau:
   - Deployment không có labels `team`.
   - Deployment dùng `hostNetwork: true`.
   - Deployment sử dụng image từ "untrusted" registry.

3. Xem **PolicyReport** để liệt kê violations.

4. Chuyển policy "disallow hostNetwork" sang **Enforce** mode và verify.

5. Viết script tổng hợp policy compliance report.

### Expected Outcome

- 4 policies deployed ở Audit mode.
- 3 violation workloads deployed thành công (Audit cho qua).
- PolicyReport hiển thị đúng violations.
- Sau khi chuyển Enforce, workload mới vi phạm hostNetwork bị chặn.

### Hint

- `validationFailureAction: Audit` → cho qua nhưng ghi violation.
- `kubectl get policyreport -A -o wide` để xem violations.
- Edit policy field `validationFailureAction` từ `Audit` sang `Enforce`.

### Acceptance Criteria

- [ ] 4 policies ở Audit mode, tất cả Ready.
- [ ] 3 violation workloads chạy bình thường.
- [ ] PolicyReport liệt kê đúng violations cho từng workload.
- [ ] Sau chuyển Enforce, workload hostNetwork mới bị chặn.
- [ ] Compliance report script chạy được, output rõ ràng.

### Bonus Challenge

Thêm **mutating policy**: tự động inject label `managed-by: kyverno` và annotation `policy-version: v1` vào mọi Pod nếu chưa có. Verify bằng cách tạo pod rồi kiểm tra labels/annotations.

<details>
<summary>Solution</summary>

```yaml
# policies-audit.yaml
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-team-env-labels
spec:
  validationFailureAction: Audit
  background: true
  rules:
    - name: check-labels
      match:
        any:
          - resources:
              kinds:
                - Deployment
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Labels 'team' and 'environment' are required."
        pattern:
          metadata:
            labels:
              team: "?*"
              environment: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resources-audit
spec:
  validationFailureAction: Audit
  background: true
  rules:
    - name: check-resources
      match:
        any:
          - resources:
              kinds:
                - Pod
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Resource requests and limits are required."
        pattern:
          spec:
            containers:
              - resources:
                  requests:
                    memory: "?*"
                    cpu: "?*"
                  limits:
                    memory: "?*"
                    cpu: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-host-network
spec:
  validationFailureAction: Audit
  background: true
  rules:
    - name: deny-hostnetwork
      match:
        any:
          - resources:
              kinds:
                - Pod
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "hostNetwork is not allowed."
        pattern:
          spec:
            =(hostNetwork): false
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-image-registries
spec:
  validationFailureAction: Audit
  background: true
  rules:
    - name: validate-registries
      match:
        any:
          - resources:
              kinds:
                - Pod
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Images must be from trusted registries (docker.io/library/)."
        pattern:
          spec:
            containers:
              - image: "docker.io/library/*|nginx*"
```

```bash
# Apply all policies
kubectl apply -f policies-audit.yaml

# Deploy violation workloads
kubectl create deployment no-labels --image=nginx:1.25
kubectl create deployment host-net --image=nginx:1.25 --dry-run=client -o yaml | \
  sed 's/spec:/spec:\n      hostNetwork: true/' | kubectl apply -f -

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: untrusted-image
spec:
  replicas: 1
  selector:
    matchLabels:
      app: untrusted
  template:
    metadata:
      labels:
        app: untrusted
    spec:
      containers:
        - name: app
          image: quay.io/someuser/suspicious:latest
EOF

# View violations
kubectl get policyreport -A -o wide

# Switch hostNetwork policy to Enforce
kubectl patch clusterpolicy disallow-host-network --type merge \
  -p '{"spec":{"validationFailureAction":"Enforce"}}'

# Test: new hostNetwork pod should be blocked
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-hostnet
spec:
  hostNetwork: true
  containers:
    - name: nginx
      image: nginx:1.25
      resources:
        requests: {cpu: 100m, memory: 128Mi}
        limits: {cpu: 200m, memory: 256Mi}
EOF
# Expected: DENIED
```

```bash
# Compliance report script
#!/bin/bash
echo "=== Policy Compliance Report ==="
echo "Date: $(date)"
echo ""
echo "--- Policies ---"
kubectl get clusterpolicy -o custom-columns=\
NAME:.metadata.name,\
ACTION:.spec.validationFailureAction,\
READY:.status.ready
echo ""
echo "--- Violations ---"
kubectl get policyreport -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{range .results[*]}{.policy}{"\t"}{.result}{"\t"}{.message}{"\n"}{end}{end}' 2>/dev/null || echo "No violations"
echo ""
echo "--- Summary ---"
TOTAL=$(kubectl get policyreport -A -o json | jq '[.items[].results[]? | select(.result=="fail")] | length')
echo "Total violations: ${TOTAL:-0}"
```

</details>

---

## Bài 3: Hard — Enterprise Policy Framework với Gatekeeper + Kyverno Comparison

### Context

Bạn là Platform Engineer tại một công ty fintech đang đánh giá policy engine. CTO yêu cầu:
1. Deploy cả Gatekeeper VÀ Kyverno (trên 2 namespace riêng) để so sánh.
2. Implement cùng 1 policy set trên cả 2 engine.
3. Đo performance và viết recommendation report.

### Yêu cầu

1. **Deploy cả 2 engine** (nhưng chỉ 1 engine active webhook tại 1 thời điểm, avoid conflict).

2. **Viết cùng 3 policies trên cả 2 engine:**
   - Require labels: `team`, `cost-center`.
   - Disallow containers running as root (`runAsNonRoot: true`).
   - Restrict image registries (chỉ `docker.io/library/`, `gcr.io/mycompany/`).

3. **So sánh:**
   - Số dòng YAML cần viết cho mỗi engine (policy complexity).
   - Thời gian evaluate (dùng `time kubectl apply`).
   - Error message clarity.
   - Audit/report capability.

4. **Viết recommendation report** (markdown): engine nào phù hợp cho fintech company (50 engineers, 3 clusters, compliance requirements)?

### Expected Outcome

- Cả 2 engine deployed và functional.
- 3 policies trên mỗi engine hoạt động đúng.
- Comparison table với metrics thực tế.
- Recommendation report với reasoning rõ ràng.

### Hint

- Deploy Gatekeeper trước, test xong thì disable webhook, rồi enable Kyverno webhook.
- Gatekeeper cần ConstraintTemplate + Constraint (2 objects per policy).
- Kyverno chỉ cần 1 ClusterPolicy per policy.
- Dùng `time` command đo latency.

### Acceptance Criteria

- [ ] Gatekeeper deployed và 3 ConstraintTemplates + 3 Constraints hoạt động.
- [ ] Kyverno deployed và 3 ClusterPolicies hoạt động.
- [ ] Test cả violation và compliance cho mỗi policy trên mỗi engine.
- [ ] Comparison table có ≥ 5 tiêu chí.
- [ ] Recommendation report ≥ 500 chữ, có trade-offs rõ ràng.

### Bonus Challenge

Thêm **generate policy** (chỉ Kyverno hỗ trợ): khi tạo Namespace mới, tự động tạo:
- NetworkPolicy default deny ingress.
- LimitRange default.
- ResourceQuota default.

So sánh workflow này vs phải tạo manual cho mỗi namespace.

<details>
<summary>Solution</summary>

```bash
# === GATEKEEPER SETUP ===
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper \
  --namespace gatekeeper-system \
  --create-namespace

kubectl wait --for=condition=ready pod -l control-plane=controller-manager \
  -n gatekeeper-system --timeout=120s
```

```yaml
# gatekeeper-require-labels.yaml
---
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels
        violation[{"msg": msg}] {
          provided := {l | input.review.object.metadata.labels[l]}
          required := {l | l := input.parameters.labels[_]}
          missing := required - provided
          count(missing) > 0
          msg := sprintf("Missing labels: %v", [missing])
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-costcenter
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
    excludedNamespaces: ["kube-system", "gatekeeper-system"]
  parameters:
    labels: ["team", "cost-center"]
```

```yaml
# gatekeeper-deny-root.yaml
---
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8sdenyroot
spec:
  crd:
    spec:
      names:
        kind: K8sDenyRoot
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8sdenyroot
        violation[{"msg": msg}] {
          c := input.review.object.spec.containers[_]
          not c.securityContext.runAsNonRoot
          msg := sprintf("Container '%v' must set runAsNonRoot: true", [c.name])
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sDenyRoot
metadata:
  name: deny-root-containers
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    excludedNamespaces: ["kube-system", "gatekeeper-system"]
```

```yaml
# gatekeeper-restrict-registries.yaml
---
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8sallowedregistries
spec:
  crd:
    spec:
      names:
        kind: K8sAllowedRegistries
      validation:
        openAPIV3Schema:
          type: object
          properties:
            registries:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8sallowedregistries
        violation[{"msg": msg}] {
          c := input.review.object.spec.containers[_]
          not startswith_any(c.image, input.parameters.registries)
          msg := sprintf("Image '%v' is not from allowed registries: %v", [c.image, input.parameters.registries])
        }
        startswith_any(str, prefixes) {
          prefix := prefixes[_]
          startswith(str, prefix)
        }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRegistries
metadata:
  name: allowed-registries
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    excludedNamespaces: ["kube-system", "gatekeeper-system"]
  parameters:
    registries:
      - "docker.io/library/"
      - "gcr.io/mycompany/"
      - "nginx"
```

```bash
# Test Gatekeeper policies
kubectl apply -f gatekeeper-require-labels.yaml
kubectl apply -f gatekeeper-deny-root.yaml
kubectl apply -f gatekeeper-restrict-registries.yaml

# Wait for constraints to be enforced
sleep 10

# Test violations
time kubectl create deployment test-gk --image=nginx:1.25 2>&1
```

```yaml
# === KYVERNO EQUIVALENT ===
# kyverno-policies.yaml
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-team-costcenter
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-labels
      match:
        any:
          - resources:
              kinds: ["Deployment"]
      exclude:
        any:
          - resources:
              namespaces: ["kube-system", "kyverno"]
      validate:
        message: "Labels 'team' and 'cost-center' are required."
        pattern:
          metadata:
            labels:
              team: "?*"
              cost-center: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: deny-root-containers
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-run-as-non-root
      match:
        any:
          - resources:
              kinds: ["Pod"]
      exclude:
        any:
          - resources:
              namespaces: ["kube-system", "kyverno"]
      validate:
        message: "Containers must set runAsNonRoot: true."
        pattern:
          spec:
            containers:
              - securityContext:
                  runAsNonRoot: true
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: allowed-registries
spec:
  validationFailureAction: Enforce
  rules:
    - name: validate-image-source
      match:
        any:
          - resources:
              kinds: ["Pod"]
      exclude:
        any:
          - resources:
              namespaces: ["kube-system", "kyverno"]
      validate:
        message: "Only images from docker.io/library/ and gcr.io/mycompany/ are allowed."
        pattern:
          spec:
            containers:
              - image: "docker.io/library/*|gcr.io/mycompany/*|nginx*"
```

```markdown
# Comparison Report

| Tiêu chí | Gatekeeper | Kyverno |
|----------|-----------|---------|
| Lines of YAML (3 policies) | ~120 (6 objects) | ~70 (3 objects) |
| Learning curve | High (Rego) | Low (native YAML) |
| Error messages | Customizable | Customizable |
| Audit capability | Built-in audit | PolicyReport CRD |
| Mutating support | Limited | First-class |
| Generate resources | No | Yes |
| Image verification | No (need external) | Built-in |
| Multi-platform (non-K8s) | Yes (OPA) | No |

## Recommendation for Fintech (50 engineers, 3 clusters, compliance)

**Recommendation: Kyverno** for primary policy engine, with OPA for non-K8s policy needs.

Reasoning:
1. YAML-native → faster adoption across 50 engineers
2. PolicyReport → easier compliance auditing
3. Image verification built-in → critical for fintech supply chain
4. Generate policies → automatic namespace setup (NetworkPolicy, ResourceQuota)
5. If the company needs OPA for Terraform/Envoy policies later, they can add it specifically for those use cases without replacing Kyverno
```

**Bonus — Generate policy:**

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: generate-namespace-defaults
spec:
  rules:
    - name: generate-default-deny-networkpolicy
      match:
        any:
          - resources:
              kinds: ["Namespace"]
      generate:
        apiVersion: networking.k8s.io/v1
        kind: NetworkPolicy
        name: default-deny-ingress
        namespace: "{{request.object.metadata.name}}"
        data:
          spec:
            podSelector: {}
            policyTypes:
              - Ingress
    - name: generate-default-limitrange
      match:
        any:
          - resources:
              kinds: ["Namespace"]
      generate:
        apiVersion: v1
        kind: LimitRange
        name: default-limits
        namespace: "{{request.object.metadata.name}}"
        data:
          spec:
            limits:
              - default:
                  cpu: 500m
                  memory: 512Mi
                defaultRequest:
                  cpu: 100m
                  memory: 128Mi
                type: Container
    - name: generate-default-resourcequota
      match:
        any:
          - resources:
              kinds: ["Namespace"]
      generate:
        apiVersion: v1
        kind: ResourceQuota
        name: default-quota
        namespace: "{{request.object.metadata.name}}"
        data:
          spec:
            hard:
              requests.cpu: "4"
              requests.memory: 8Gi
              limits.cpu: "8"
              limits.memory: 16Gi
              pods: "20"
```

</details>

---

## Solution/Reference Implementation

Các lời giải chi tiết nằm trong block `<details><summary>Solution</summary>` của từng bài để người học có thể thử trước khi mở đáp án. Reference cuối file:

- **Bài 1 — Easy**: cài Kyverno, enforce `disallow-privileged` và `require-resources`, verify bằng pod violating/compliant.
- **Bài 2 — Medium**: triển khai workflow `Audit` → `Enforce`, đọc violation report, tạo compliance report script.
- **Bài 3 — Hard**: so sánh Gatekeeper ConstraintTemplate/Constraint với Kyverno policy tương đương và đưa ra recommendation cho môi trường fintech.

