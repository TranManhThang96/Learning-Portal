# Bài thực hành - Day 35: Pod Security và Admission Control

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Quyền hiện tại đủ để tạo namespace và label namespace.
- Cluster hỗ trợ Pod Security Admission.
- Cluster pull được image `busybox:1.36`.
- Optional: Kyverno hoặc Gatekeeper nếu bạn đã có sẵn trong cluster.

## Lab Scenario

Bạn sẽ tạo hai namespace:

- `day35-baseline`: enforce `baseline`, warn/audit `restricted`.
- `day35-restricted`: enforce `restricted`.

Sau đó bạn sẽ apply Pod cố ý vi phạm, đọc warning/error, sửa manifest để pass policy và viết policy migration note.

## Core Path (90-105 phút)

- Task 1-6, Task 8 và Task 9 là phần bắt buộc.
- Task 7 là optional vì Kyverno/Gatekeeper chỉ chạy được khi policy engine đã có sẵn.

## Task 1: Tạo namespace baseline và restricted (10 phút)

```bash
kubectl create namespace day35-baseline
kubectl create namespace day35-restricted
kubectl version
```

Ghi lại server minor version của cluster, ví dụ dạng `v1.xx`. Production nên pin PSA policy version theo minor version của API server hiện tại, không copy cứng version từ tài liệu.

Label namespace baseline:

```bash
kubectl label namespace day35-baseline \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted \
  --overwrite
```

Label namespace restricted:

```bash
kubectl label namespace day35-restricted \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted \
  --overwrite
```

Kiểm tra:

```bash
kubectl get namespace day35-baseline day35-restricted --show-labels
```

### Câu hỏi

- `enforce` khác `warn` thế nào?
- Vì sao migration nên bắt đầu bằng `warn`/`audit`?
- Production nên dùng `latest` hay pin `<cluster-minor>`?

## Task 2: Apply privileged Pod vào baseline namespace (15 phút)

Tạo file `privileged-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: privileged
  namespace: day35-baseline
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    securityContext:
      privileged: true
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

Apply:

```bash
kubectl apply -f privileged-pod.yaml
```

### Expected output

- Request bị từ chối vì `baseline` không cho privileged container.
- Pod không được tạo.

Kiểm tra:

```bash
kubectl get pod privileged -n day35-baseline
```

Không kỳ vọng `kubectl get events` sẽ có event cho request bị PSA reject. Pod bị chặn trước khi được persist, nên evidence chính là error từ `kubectl apply`. Nếu cluster bật API audit logging, mode `audit` ghi audit annotation vào audit log, không phải namespace Event.

### Câu hỏi

- Vì sao `kubectl get pod` không thấy Pod?
- Lỗi này là RBAC hay admission?
- Nếu một DaemonSet hạ tầng thật cần privileged, bạn có nên chạy nó trong app namespace không?

## Task 3: Apply Pod không privileged nhưng chưa restricted (15 phút)

Tạo file `baseline-ok-restricted-warn.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: baseline-ok
  namespace: day35-baseline
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

Apply:

```bash
kubectl apply -f baseline-ok-restricted-warn.yaml
kubectl get pod baseline-ok -n day35-baseline
```

Bạn có thể thấy warning vì namespace đang `warn=restricted`. Namespace cũng có `audit=restricted`, nhưng audit evidence nằm trong API audit log nếu audit logging được bật; không kiểm tra bằng `kubectl get events`.

### Câu hỏi

- Pod này pass `baseline` vì sao?
- Warning `restricted` yêu cầu thêm field nào?
- Nếu warning xuất hiện trong CI, bạn nên fail build hay chỉ ghi nhận?

## Task 4: Apply insecure Pod vào restricted namespace (15 phút)

Tạo file `restricted-fail.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: restricted-fail
  namespace: day35-restricted
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

Apply:

```bash
kubectl apply -f restricted-fail.yaml
```

### Expected output

- Request bị reject vì thiếu securityContext theo `restricted`.
- Error thường nhắc `allowPrivilegeEscalation`, capabilities, seccomp hoặc runAsNonRoot.

### Câu hỏi

- Field nào bị policy yêu cầu?
- Pod có được tạo rồi crash không, hay bị chặn trước khi tạo?
- Vì sao image legacy hay gặp lỗi khi chuyển sang `restricted`?

## Task 5: Sửa manifest để pass restricted (20 phút)

Tạo file `restricted-ok.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: restricted-ok
  namespace: day35-restricted
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    securityContext:
      runAsUser: 1000
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

Apply:

```bash
kubectl apply -f restricted-ok.yaml
kubectl wait --for=condition=Ready pod/restricted-ok -n day35-restricted --timeout=120s
kubectl get pod restricted-ok -n day35-restricted -o yaml
```

### Expected output

- Pod được tạo và Running/Ready.
- Manifest có non-root, no privilege escalation, drop capabilities và seccomp.

### Câu hỏi

- `runAsUser: 1000` có luôn hoạt động với mọi image không?
- Vì sao `readOnlyRootFilesystem` là best practice nhưng có thể cần app thay đổi?
- Bạn sẽ đưa securityContext này vào Helm chart như thế nào?

## Task 6: Kiểm tra admission webhooks đang có (10 phút)

Không cài mới gì ở task này. Chỉ quan sát cluster:

```bash
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
```

Nếu có webhook:

```bash
kubectl describe validatingwebhookconfiguration <name>
kubectl describe mutatingwebhookconfiguration <name>
```

Ghi lại:

```text
Webhook name:
Type: validating/mutating
FailurePolicy:
TimeoutSeconds:
NamespaceSelector:
ObjectSelector:
Service endpoint:
```

### Câu hỏi

- Nếu webhook down và `failurePolicy=Fail`, deploy bị ảnh hưởng thế nào?
- Nếu `failurePolicy=Ignore`, policy có thể bị bypass khi nào?
- Vì sao webhook nên có namespaceSelector rõ?

## Task 7: Kyverno/Gatekeeper policy worksheet (optional, 20 phút)

Không bắt buộc apply nếu cluster chưa cài policy engine.

Policy mong muốn:

```text
Tất cả Pod trong namespace production phải có label app.kubernetes.io/name và app.kubernetes.io/part-of.
```

Viết logic ở mức pseudo-policy:

```text
Match:
  resources: Pod
  namespaces: production namespaces
Validate:
  metadata.labels["app.kubernetes.io/name"] exists
  metadata.labels["app.kubernetes.io/part-of"] exists
Failure action:
  warn in staging
  enforce in production after migration
Exceptions:
  kube-system and policy engine namespaces
```

Nếu dùng Kyverno, sketch YAML:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-standard-labels
spec:
  validationFailureAction: Audit
  rules:
  - name: require-app-labels
    match:
      any:
      - resources:
          kinds:
          - Pod
    validate:
      message: "Pod must include standard app labels"
      pattern:
        metadata:
          labels:
            app.kubernetes.io/name: "?*"
            app.kubernetes.io/part-of: "?*"
```

### Câu hỏi

- Pod Security Admission có kiểm tra label này không?
- Vì sao policy label nên dùng Kyverno/Gatekeeper thay vì Pod Security Admission?
- Bạn rollout policy này bằng audit trước hay enforce ngay?

## Task 8: Viết migration note từ baseline sang restricted (10 phút)

Điền:

```text
Namespace:
Current policy:
Target policy:
Violations observed:
Images needing non-root change:
Manifest fields to add:
CI checks:
Exception list:
Rollout steps:
Verification:
Rollback:
```

Gợi ý rollout:

1. Bật `warn=restricted`.
2. Sửa manifest và image.
3. Test staging `enforce=restricted`.
4. Pin version theo `<cluster-minor>` của API server.
5. Roll production theo namespace.

## Task 9: Cleanup

```bash
kubectl delete namespace day35-baseline
kubectl delete namespace day35-restricted
```

## Stretch Goals

- Nếu cluster đã cài Kyverno hoặc Gatekeeper, chuyển worksheet Task 7 thành policy apply thật trong namespace lab.
- Bổ sung CI check để fail manifest thiếu `runAsNonRoot`, `allowPrivilegeEscalation: false` hoặc `seccompProfile`.

## Checklist hoàn thành

- [ ] Cấu hình được namespace labels cho Pod Security Admission.
- [ ] Thấy privileged Pod bị reject bởi `baseline`.
- [ ] Thấy Pod pass `baseline` nhưng warning `restricted`.
- [ ] Thấy Pod bị reject bởi `restricted`.
- [ ] Sửa được manifest để pass `restricted`.
- [ ] Biết kiểm tra admission webhook configurations.
- [ ] So sánh được Pod Security Admission với Kyverno/Gatekeeper.
- [ ] Viết được migration note từ `baseline` sang `restricted`.
