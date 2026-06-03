# Day 21: Admission Controller, OPA/Gatekeeper, Kyverno

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** luồng admission controller trong Kubernetes API server — request đi qua những bước nào trước khi được persist vào etcd.
2. **Phân biệt được** mutating admission webhook và validating admission webhook — khi nào cần thay đổi request, khi nào cần chặn request.
3. **So sánh và lựa chọn được** giữa OPA/Gatekeeper và Kyverno theo context cụ thể (startup, mid-size, enterprise).
4. **Viết và deploy được** ít nhất 3 policy thực tế: chặn privileged pod, bắt buộc resource limits, bắt buộc labels.
5. **Debug được** khi policy chặn nhầm workload hợp lệ trong production.

---

## 2. Bối cảnh & Động lực

### Vấn đề thực tế

Trong Day 20, bạn đã học RBAC để kiểm soát **ai được làm gì**. Nhưng RBAC không kiểm soát **nội dung** của request. Ví dụ:

- RBAC cho phép developer tạo pod, nhưng không ngăn họ tạo pod **privileged** (có quyền root trên node).
- RBAC cho phép tạo deployment, nhưng không bắt buộc phải có **resource requests/limits**.
- RBAC không thể bắt buộc mọi workload phải có **label** `team`, `environment`, `cost-center`.

### Analogy cho Developer

Admission controller giống **middleware** trong web framework:

```
HTTP Request → Auth Middleware → Validation Middleware → Rate Limit → Handler
K8s Request → Authentication → Authorization (RBAC) → Admission Controllers → etcd
```

Như Express.js middleware, admission controller có thể:
- **Mutate**: thêm/sửa field trong request (giống middleware thêm header)
- **Validate**: chặn request không hợp lệ (giống validation middleware return 400)

### Hậu quả nếu không có admission control

| Tình huống | Hậu quả |
|------------|---------|
| Developer deploy pod privileged | Container escape, compromise toàn bộ node |
| Workload không có resource limits | Noisy neighbor, OOMKilled cascade |
| Thiếu labels | Không track được cost, không biết workload thuộc team nào |
| Image từ registry không tin cậy | Supply chain attack, malware trong cluster |

### Production Case Study ngắn

Một fintech company cho phép developer tự deploy lên shared cluster. Một developer vô tình deploy pod với `hostNetwork: true` và `privileged: true` để debug. Pod đó có thể đọc traffic của mọi pod khác trên cùng node — bao gồm cả pod xử lý payment. Sau incident, họ deploy Kyverno với policy chặn privileged pods — giải quyết triệt để trong 30 phút.

---

## 3. Kiến thức nền tảng

### Kubernetes API Request Lifecycle

Khi bạn chạy `kubectl apply -f deployment.yaml`, request đi qua các bước:

```
kubectl → API Server
                ↓
    1. Authentication (ai đang gọi?)
                ↓
    2. Authorization / RBAC (có quyền không?)
                ↓
    3. Mutating Admission (sửa request nếu cần)
                ↓
    4. Schema Validation (request có đúng format?)
                ↓
    5. Validating Admission (request có hợp lệ theo policy?)
                ↓
    6. Persist to etcd
```

### Built-in Admission Controllers

Kubernetes có sẵn nhiều admission controller (enable bằng flag `--enable-admission-plugins`):

| Controller | Loại | Chức năng |
|-----------|------|-----------|
| `NamespaceLifecycle` | Validating | Chặn tạo object trong namespace đang bị xóa |
| `LimitRanger` | Mutating + Validating | Apply default resource limits từ LimitRange |
| `DefaultStorageClass` | Mutating | Gán default StorageClass cho PVC không chỉ định |
| `ResourceQuota` | Validating | Enforce quota per namespace |
| `PodSecurity` | Validating | Enforce Pod Security Standards (Day 20) |

### Dynamic Admission Control — Webhook

Bên cạnh built-in controllers, Kubernetes cho phép đăng ký **webhook** (HTTP endpoint) để custom admission logic:

- **MutatingAdmissionWebhook**: gọi webhook, webhook trả về patch JSON để sửa request.
- **ValidatingAdmissionWebhook**: gọi webhook, webhook trả về allow/deny.

OPA/Gatekeeper và Kyverno đều hoạt động bằng cách đăng ký webhook với API server.

---

## 4. Deep Dive

### 4.1 Admission Webhook Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        API Server                                │
│                                                                  │
│  Request ──→ AuthN ──→ AuthZ ──→ Mutating Webhooks (tuần tự)    │
│                                        │                         │
│                                        ▼                         │
│                              Schema Validation                   │
│                                        │                         │
│                                        ▼                         │
│                              Validating Webhooks (song song)     │
│                                        │                         │
│                                        ▼                         │
│                                   etcd Persist                   │
└──────────────────────────────────────────────────────────────────┘
```

**Lưu ý quan trọng:**
- Mutating webhooks chạy **tuần tự** (vì webhook sau có thể phụ thuộc kết quả webhook trước).
- Validating webhooks chạy **song song** (chỉ cần allow/deny, không sửa request).
- Nếu **bất kỳ** validating webhook nào deny → request bị reject.

### 4.2 Webhook Configuration

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: example-policy
webhooks:
  - name: validate.example.com
    clientConfig:
      service:
        name: policy-engine
        namespace: policy-system
        path: "/validate"
    rules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]
    failurePolicy: Fail    # Fail hoặc Ignore
    sideEffects: None
    timeoutSeconds: 10     # Max 30s
```

### 4.3 OPA/Gatekeeper

**OPA (Open Policy Agent)** là policy engine đa mục đích — không chỉ cho Kubernetes. **Gatekeeper** là adapter của OPA cho Kubernetes.

```
┌─────────────────────────────────────────────┐
│                Gatekeeper                    │
│                                             │
│  ConstraintTemplate ──→ Định nghĩa policy   │
│         │                (Rego language)     │
│         ▼                                   │
│  Constraint ──→ Apply policy cho resource    │
│         │       cụ thể (scope, parameters)  │
│         ▼                                   │
│  Audit Controller ──→ Scan existing         │
│                       resources             │
└─────────────────────────────────────────────┘
```

**ConstraintTemplate** (định nghĩa logic policy bằng Rego):

```yaml
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
          provided := {label | input.review.object.metadata.labels[label]}
          required := {label | label := input.parameters.labels[_]}
          missing := required - provided
          count(missing) > 0
          msg := sprintf("Missing required labels: %v", [missing])
        }
```

**Constraint** (apply policy):

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
  parameters:
    labels: ["team", "environment"]
```

### 4.4 Kyverno

Kyverno dùng **native Kubernetes YAML** — không cần học Rego.

```
┌─────────────────────────────────────────────┐
│                  Kyverno                     │
│                                             │
│  ClusterPolicy ──→ Policy áp cho toàn       │
│         │          cluster                   │
│  Policy ──→ Policy áp cho 1 namespace       │
│         │                                   │
│  Rule types:                                │
│    - validate (chặn)                        │
│    - mutate (sửa)                           │
│    - generate (tự tạo resource)             │
│    - verifyImages (kiểm tra image signature)│
└─────────────────────────────────────────────┘
```

**Ví dụ Kyverno policy — chặn privileged pod:**

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged
spec:
  validationFailureAction: Enforce  # Enforce hoặc Audit
  background: true
  rules:
    - name: deny-privileged
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "Privileged pods are not allowed."
        pattern:
          spec:
            containers:
              - securityContext:
                  privileged: "!true"
```

### 4.5 Mutating vs Validating — Khi nào dùng gì?

| Hành động | Loại | Ví dụ |
|-----------|------|-------|
| Inject sidecar | Mutating | Istio inject envoy proxy |
| Thêm default labels | Mutating | Auto-add `managed-by: kyverno` |
| Set default resource limits | Mutating | Nếu không set → tự thêm defaults |
| Chặn privileged pod | Validating | Block `privileged: true` |
| Bắt buộc labels | Validating | Reject nếu thiếu `team` label |
| Chỉ cho phép trusted registry | Validating | Block image không từ `gcr.io/mycompany/` |

---

## 5. Trade-offs & Best Practices ⭐

### OPA/Gatekeeper vs Kyverno

| Tiêu chí | OPA/Gatekeeper | Kyverno |
|----------|----------------|---------|
| **Ngôn ngữ policy** | Rego (DSL riêng, learning curve cao) | Native YAML (quen thuộc) |
| **Mutating** | Hỗ trợ hạn chế (cần Gatekeeper mutation) | First-class support |
| **Generate resource** | Không hỗ trợ | Hỗ trợ (auto tạo NetworkPolicy, etc.) |
| **Image verification** | Cần thêm tool | Built-in (cosign/notary) |
| **Multi-purpose** | OPA dùng cho cả API gateway, Terraform, Envoy | Chỉ cho Kubernetes |
| **Community** | CNCF Graduated, lớn hơn | CNCF Incubating, đang phát triển nhanh |
| **Audit** | Built-in audit controller | Built-in policy reports |
| **Performance** | Nhanh hơn với policy phức tạp (Rego compiled) | Đủ nhanh cho hầu hết cases |

### Recommendation theo context

| Context | Recommendation | Lý do |
|---------|---------------|-------|
| **Startup (< 20 engineers)** | Kyverno | YAML native, ít learning curve, nhanh setup |
| **Mid-size (20-100)** | Kyverno hoặc Gatekeeper | Tùy team skill. Nếu team quen Rego → Gatekeeper |
| **Enterprise (> 100)** | Gatekeeper + OPA | Policy reuse across Terraform, Envoy, API gateway |
| **Đã dùng OPA cho hệ thống khác** | Gatekeeper | Tận dụng Rego policy existing |
| **Cần mutating/generate nhiều** | Kyverno | Gatekeeper mutation hạn chế hơn |

### Anti-patterns

1. **Enforce ngay từ đầu**: Deploy policy ở mode `Enforce` trước khi biết impact → chặn nhầm production workload. **Luôn bắt đầu bằng `Audit` mode**.
2. **Policy quá strict**: Bắt buộc mọi thứ cùng lúc → developer frustration, shadow deployment. **Rollout từng policy một**.
3. **Không exclude system namespaces**: Policy chặn cả `kube-system`, `cert-manager` → cluster broken. **Luôn exclude critical namespaces**.
4. **failurePolicy: Fail cho mọi webhook**: Nếu webhook service down → mọi deployment bị chặn. **Dùng `Ignore` cho non-critical policies**.

---

## 6. Performance & Scalability ⭐

### Latency Impact

Mỗi admission webhook thêm **1 HTTP round-trip** vào API request:

| Metric | Giá trị thường thấy |
|--------|---------------------|
| Webhook latency (P50) | 5-15ms |
| Webhook latency (P99) | 50-100ms |
| Tổng admission overhead | 20-200ms per request |
| Timeout mặc định | 10s (max 30s) |

### Bottleneck thường gặp

1. **Quá nhiều webhooks**: Mỗi webhook là 1 HTTP call. 10 mutating webhooks = 10 round trips tuần tự.
2. **Webhook service thiếu resource**: Kyverno/Gatekeeper pod bị CPU throttled → latency tăng.
3. **Policy phức tạp**: Rego policy lồng nhiều loop → tăng thời gian evaluate.

### Cách phát hiện bottleneck

```bash
# Kiểm tra webhook latency
kubectl get --raw /metrics | grep apiserver_admission_webhook_admission_duration_seconds

# Kiểm tra rejection rate
kubectl get --raw /metrics | grep apiserver_admission_webhook_rejection_count

# Kyverno metrics
kubectl get --raw /metrics -n kyverno | grep kyverno_policy_execution_duration
```

### Best practices về performance

- **Set `timeoutSeconds: 5-10`** cho webhook (default 10, max 30).
- **Dùng `namespaceSelector`** hoặc `objectSelector` để giảm scope — không cần evaluate mọi request.
- **Allocate đủ resource** cho policy engine: Kyverno cần ít nhất 256Mi memory, 100m CPU (production nên 512Mi+).
- **Dùng `failurePolicy: Ignore`** cho non-critical policies (tránh block API khi webhook down).

---

## 7. Security & Reliability Considerations

### Security

- **Webhook communication phải qua TLS**: API server gọi webhook qua HTTPS. Certificate phải valid.
- **Least privilege cho policy engine**: Kyverno/Gatekeeper cần RBAC rộng (đọc mọi resource để evaluate). Đây là **attack surface** — nếu compromise policy engine → có quyền lớn trong cluster.
- **Audit mode trước, Enforce sau**: Giảm blast radius khi policy sai.

### Reliability

- **Webhook availability**: Nếu policy engine pod down + `failurePolicy: Fail` → mọi deployment bị chặn.
- **High Availability**: Deploy policy engine với `replicas >= 2` + PodDisruptionBudget.
- **Exclude critical namespaces**: Luôn exclude `kube-system`, `kyverno` (hoặc `gatekeeper-system`).

### Rollback Plan

1. Nếu policy chặn nhầm production → **switch policy sang `Audit`** mode (không cần xóa policy).
2. Nếu webhook service bị crash → **failurePolicy: Ignore** sẽ cho request qua.
3. Emergency fallback: xóa `ValidatingWebhookConfiguration` để bypass hoàn toàn.

```bash
# Emergency: xóa webhook config (bypass all policies)
kubectl delete validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg
```

---

## 8. Hands-on Example

### Prerequisites

```bash
# Cluster local (kind)
kind create cluster --name policy-lab

# Verify cluster
kubectl cluster-info
```

### 8.1 Cài đặt Kyverno

```bash
# Install Kyverno via Helm
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=1

# Verify installation
kubectl get pods -n kyverno
```

Expected output:
```
NAME                       READY   STATUS    RESTARTS   AGE
kyverno-xxxxxxxxx-xxxxx    1/1     Running   0          60s
```

### 8.2 Policy 1: Chặn Privileged Pod

```yaml
# policy-disallow-privileged.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged-containers
  annotations:
    policies.kyverno.io/title: Disallow Privileged Containers
    policies.kyverno.io/severity: high
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
        message: >-
          Privileged mode is not allowed. Set
          spec.containers[*].securityContext.privileged to false.
        pattern:
          spec:
            containers:
              - =(securityContext):
                  =(privileged): false
```

```bash
# Apply policy
kubectl apply -f policy-disallow-privileged.yaml

# Verify policy
kubectl get clusterpolicy
```

Expected output:
```
NAME                              ADMISSION   BACKGROUND   VALIDATE ACTION   READY   AGE
disallow-privileged-containers    true        true         Enforce           True    5s
```

**Test — tạo privileged pod (phải bị chặn):**

```yaml
# test-privileged-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: bad-privileged-pod
spec:
  containers:
    - name: nginx
      image: nginx:1.25
      securityContext:
        privileged: true
```

```bash
kubectl apply -f test-privileged-pod.yaml
```

Expected output:
```
Error from server: error when creating "test-privileged-pod.yaml": admission webhook
"validate.kyverno.svc-fail" denied the request:
resource Pod/default/bad-privileged-pod was blocked due to the following policies:
disallow-privileged-containers:
  deny-privileged: 'validation error: Privileged mode is not allowed.'
```

**Test — tạo pod bình thường (phải được phép):**

```yaml
# test-normal-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: good-pod
spec:
  containers:
    - name: nginx
      image: nginx:1.25
      securityContext:
        privileged: false
```

```bash
kubectl apply -f test-normal-pod.yaml
# Expected: pod/good-pod created
```

### 8.3 Policy 2: Bắt buộc Resource Requests/Limits

```yaml
# policy-require-resources.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
  annotations:
    policies.kyverno.io/title: Require Resource Limits
    policies.kyverno.io/severity: medium
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-limits
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
        message: >-
          All containers must have CPU and memory requests and limits defined.
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
kubectl apply -f policy-require-resources.yaml

# Test — pod không có resources (phải bị chặn)
kubectl run test-no-resources --image=nginx:1.25
# Expected: blocked!

# Test — pod có resources (phải được phép)
kubectl run test-with-resources --image=nginx:1.25 \
  --requests='cpu=100m,memory=128Mi' \
  --limits='cpu=200m,memory=256Mi'
# Expected: pod/test-with-resources created
```

### 8.4 Policy 3: Bắt buộc Labels

```yaml
# policy-require-labels.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: Audit  # Bắt đầu bằng Audit mode
  background: true
  rules:
    - name: require-team-label
      match:
        any:
          - resources:
              kinds:
                - Deployment
                - StatefulSet
      exclude:
        any:
          - resources:
              namespaces:
                - kube-system
                - kyverno
      validate:
        message: "Label 'team' is required on all Deployments and StatefulSets."
        pattern:
          metadata:
            labels:
              team: "?*"
```

```bash
kubectl apply -f policy-require-labels.yaml

# Test — tạo deployment không có label team
kubectl create deployment test-no-label --image=nginx:1.25

# Vì policy ở mode Audit → deployment vẫn được tạo nhưng có violation report
kubectl get policyreport -A
```

### 8.5 Policy 4: Mutating — Tự thêm default labels

```yaml
# policy-mutate-labels.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-labels
spec:
  rules:
    - name: add-managed-by
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
      mutate:
        patchStrategicMerge:
          metadata:
            labels:
              +(managed-by): kyverno
              +(environment): dev
```

```bash
kubectl apply -f policy-mutate-labels.yaml

# Tạo pod → kiểm tra labels tự thêm
kubectl run test-mutate --image=nginx:1.25 \
  --requests='cpu=100m,memory=128Mi' \
  --limits='cpu=200m,memory=256Mi'

kubectl get pod test-mutate --show-labels
```

Expected output:
```
NAME          READY   STATUS    RESTARTS   AGE   LABELS
test-mutate   1/1     Running   0          10s   environment=dev,managed-by=kyverno,run=test-mutate
```

### 8.6 Cleanup

```bash
# Xóa policies
kubectl delete clusterpolicy --all

# Xóa test pods
kubectl delete pod --all

# Xóa Kyverno
helm uninstall kyverno -n kyverno
kubectl delete namespace kyverno

# Xóa kind cluster
kind delete cluster --name policy-lab
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Policy chặn kube-system

**Dấu hiệu**: Sau khi deploy policy, `kube-dns` hoặc `coredns` bị restart loop, cluster DNS broken.

**Nguyên nhân**: Policy apply cho tất cả namespace, bao gồm `kube-system`.

**Fix**:
```yaml
exclude:
  any:
    - resources:
        namespaces:
          - kube-system
          - kyverno
          - cert-manager
```

### Pitfall 2: Webhook timeout gây block deployment

**Dấu hiệu**: `kubectl apply` trả về `context deadline exceeded` hoặc rất chậm.

**Debug**:
```bash
# Check webhook configuration
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration

# Check policy engine pod status
kubectl get pods -n kyverno
kubectl logs -n kyverno deployment/kyverno

# Check webhook latency
kubectl get --raw /metrics | grep apiserver_admission_webhook
```

**Fix**: Tăng resource cho policy engine, hoặc set `failurePolicy: Ignore`.

### Pitfall 3: failurePolicy: Fail + policy engine down

**Dấu hiệu**: Mọi `kubectl apply`, `kubectl create`, thậm chí `kubectl delete` đều fail.

**Fix khẩn cấp**:
```bash
# Bypass webhook bằng cách xóa config
kubectl delete validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg
```

### Production Case Study: Policy Chặn Nhầm Trong Rollout

**Context**: Một e-commerce platform (500 RPS) dùng Kyverno với policy require `app.kubernetes.io/version` label trên mọi Deployment.

**Symptom**: Sau khi CI/CD pipeline deploy version mới, rollout bị stuck. New pods không được tạo.

**Investigation**:
```bash
kubectl describe deployment api-gateway
# Events: "admission webhook denied the request"

kubectl get policyreport -A
# Violation: missing label app.kubernetes.io/version
```

**Root Cause**: CI/CD pipeline dùng `kustomize` để set image mới nhưng quên update label `app.kubernetes.io/version`. Policy đang ở `Enforce` mode → chặn mọi pod mới.

**Mitigation**: Switch policy sang `Audit` mode ngay → new pods được tạo → rollout tiếp tục.

**Long-term Fix**:
1. CI/CD pipeline tự động update labels khi deploy version mới.
2. Policy thêm `exclude` cho CI/CD ServiceAccount trong 5 phút đầu rollout.
3. Thêm pre-deploy validation trong CI pipeline.

**Lesson Learned**: Luôn test policy với CI/CD workflow trước khi Enforce. Policy là code — cần CI/CD cho policy nữa.

---

## 10. Kết nối với bài trước & bài sau

### Từ Day 20 (RBAC, PSS, NetworkPolicy)

Day 20 dạy **3 lớp bảo mật** trong Kubernetes:
- **RBAC**: kiểm soát ai được làm gì (authn/authz)
- **Pod Security Standards**: kiểm soát pod chạy ở level nào (restricted/baseline/privileged)
- **NetworkPolicy**: kiểm soát traffic giữa pods

Day 21 thêm **lớp thứ 4**: **Admission Control** — kiểm soát nội dung của request trước khi persist. Admission controller bổ sung cho PSS (PSS chỉ cover security context, admission controller cover toàn bộ spec).

### Sang Day 22 (Kubernetes Troubleshooting)

Khi admission policy chặn nhầm workload, bạn cần kỹ năng troubleshooting để debug:
- `kubectl describe` để xem event "admission webhook denied"
- `kubectl get policyreport` để xem violations
- Hiểu log flow từ API server → webhook → response

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Admission Controllers Reference](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Kyverno Documentation](https://kyverno.io/docs/)
- [Kyverno Policies Library](https://kyverno.io/policies/)

### Nice-to-have

- [OPA Gatekeeper Documentation](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [OPA Rego Language Reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [Kubernetes Blog: A Guide to Kubernetes Admission Controllers](https://kubernetes.io/blog/2019/03/21/a-guide-to-kubernetes-admission-controllers/)

### Deep-dive

- [Gatekeeper vs Kyverno - Nirmata Blog](https://nirmata.com/2021/01/kyverno-vs-opa-gatekeeper/)
- [Policy as Code - Thoughtworks Tech Radar](https://www.thoughtworks.com/radar/techniques/policy-as-code)
- [CNCF Policy Working Group](https://github.com/kubernetes/community/tree/master/sig-auth)

