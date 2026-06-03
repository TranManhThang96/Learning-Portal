# Day 35: Pod Security và Admission Control

## Mục tiêu bài học

- Hiểu `Pod Security Standards` gồm `Privileged`, `Baseline`, `Restricted` và khi nào dùng từng profile.
- Biết cấu hình `Pod Security Admission` bằng namespace labels với mode `enforce`, `audit`, `warn`.
- Hiểu admission control nằm ở đâu trong request path và khác RBAC thế nào.
- So sánh built-in Pod Security Admission với OPA/Gatekeeper, Kyverno và admission webhooks.
- Debug được workload bị reject vì policy/security context.

## Vấn đề cần giải quyết

RBAC trả lời: "Ai được tạo Pod?". Nhưng RBAC không trả lời đủ: "Pod đó có an toàn để chạy không?".

Ví dụ một user có quyền `create pods` có thể tạo Pod:

- `privileged: true`.
- Mount host filesystem.
- Chạy `hostNetwork`, `hostPID`.
- Add Linux capabilities nguy hiểm.
- Chạy root và cho phép privilege escalation.
- Không đặt seccomp profile.

Trong production multi-team cluster, bạn cần policy trước khi workload được lưu và chạy. Admission control là lớp chặn cuối cùng trước khi object vào cluster state.

## Mental Model

```text
kubectl apply
  |
  v
kube-apiserver
  |
  +-- authentication: bạn là ai?
  +-- authorization/RBAC: bạn được làm gì?
  +-- admission:
        +-- mutating: sửa/thêm default nếu được phép
        +-- validating: chấp nhận hoặc từ chối object
  |
  v
object persisted
  |
  v
controllers/kubelet act on it
```

RBAC kiểm tra quyền của subject. Admission kiểm tra nội dung object.

## Lý thuyết cốt lõi

### Pod Security Standards

`Pod Security Standards` là bộ policy mức Pod do Kubernetes định nghĩa:

| Profile | Mục tiêu | Dùng ở đâu |
|---|---|---|
| `Privileged` | Không hạn chế đáng kể | System components, trusted infrastructure namespace |
| `Baseline` | Chặn cấu hình privilege rõ ràng nguy hiểm | Default tốt cho nhiều app namespace |
| `Restricted` | Hardening mạnh theo best practices hiện đại | Workload production có thể tuân thủ non-root, seccomp, drop capabilities |

`Restricted` an toàn hơn nhưng đòi hỏi image và manifest được chuẩn bị tốt. Nhiều image legacy chạy root, ghi vào filesystem tùy ý hoặc cần capabilities sẽ fail.

### Pod Security Admission

`Pod Security Admission` là admission controller built-in để enforce Pod Security Standards theo namespace labels.

Ba mode chính:

| Mode | Hành vi |
|---|---|
| `enforce` | Từ chối Pod vi phạm |
| `warn` | Cho phép nhưng trả warning cho client |
| `audit` | Cho phép nhưng thêm audit annotation vào API audit log nếu audit logging được bật |

Ví dụ namespace label:

```bash
kubectl label namespace app \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted
```

Trong production, nên pin version policy:

```bash
kubectl label namespace app \
  pod-security.kubernetes.io/enforce-version=<cluster-minor> \
  pod-security.kubernetes.io/warn-version=<cluster-minor> \
  pod-security.kubernetes.io/audit-version=<cluster-minor>
```

`<cluster-minor>` là minor version của API server, ví dụ dạng `v1.xx`. Không copy một version từ tài liệu sang cluster khác nếu chưa kiểm tra `kubectl version`. Trong lab, có thể dùng `latest` để tránh phải biết chính xác cluster version.

### SecurityContext quan trọng

Các field thường gặp trong Pod/container `securityContext`:

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

Ý nghĩa:

- `runAsNonRoot`: không cho process chạy root.
- `allowPrivilegeEscalation: false`: chặn process lấy quyền cao hơn qua setuid hoặc cơ chế tương tự.
- `capabilities.drop: ["ALL"]`: bỏ Linux capabilities mặc định.
- `seccompProfile.type: RuntimeDefault`: dùng seccomp profile mặc định của runtime.

Các cấu hình thường bị policy chặn:

- `privileged: true`
- `hostNetwork: true`
- `hostPID: true`
- `hostIPC: true`
- `hostPath` volume nhạy cảm
- add capabilities như `NET_ADMIN`, `SYS_ADMIN`
- chạy root trong namespace `restricted`

### Admission webhooks

Admission webhooks cho phép gọi service bên ngoài API server để mutate hoặc validate request.

Hai loại:

- `MutatingAdmissionWebhook`: sửa object trước khi validate/persist.
- `ValidatingAdmissionWebhook`: từ chối hoặc cho phép object.

Gatekeeper, Kyverno và nhiều platform tools dùng admission webhook để thực thi policy linh hoạt hơn Pod Security Admission.

Rủi ro webhook:

- Webhook chậm làm apply chậm.
- Webhook down có thể block deploy nếu `failurePolicy: Fail`.
- Policy sai có thể chặn cả system workloads.
- Upgrade webhook/controller cần kế hoạch.

### OPA/Gatekeeper

Gatekeeper dùng OPA và policy thường viết bằng Rego thông qua `ConstraintTemplate` và `Constraint`.

Phù hợp khi:

- Organization đã dùng OPA/Rego.
- Cần policy mạnh, biểu đạt logic phức tạp.
- Muốn audit violations trên nhiều resource.

Trade-off:

- Rego có learning curve.
- Debug policy cần kỹ năng riêng.
- Cần vận hành webhook/controller.

### Kyverno

Kyverno dùng policy dạng Kubernetes-native YAML. Nó có thể validate, mutate, generate và verify image.

Phù hợp khi:

- Team muốn policy đọc giống Kubernetes manifest.
- Cần mutate default securityContext/labels.
- Cần generate resource hoặc verify image signature.

Trade-off:

- Vẫn là admission controller cần vận hành.
- Policy quá nhiều hoặc match quá rộng có thể ảnh hưởng API latency.
- Mutation có thể che giấu manifest thiếu chuẩn nếu không quản lý rõ.

## Deep dive: Admission decision và failure modes

### Request bị reject trước khi Pod tồn tại

Nếu admission từ chối object, Pod không được lưu. Vì vậy:

```bash
kubectl get pod <name>
```

có thể không thấy gì. Evidence nằm ngay trong output `kubectl apply` hoặc API error:

```text
Error from server (Forbidden): pods "bad" is forbidden: violates PodSecurity "restricted:latest": ...
```

Không kỳ vọng `kubectl get events` trong namespace sẽ luôn có record cho Pod bị PSA reject, vì object chưa được tạo. Với mode `audit`, evidence nằm trong API audit log nếu cluster bật audit logging; với mode `warn`, evidence nằm trong warning trả về client.

### Warning không đồng nghĩa pass production

Nếu namespace đang `warn=restricted`, apply có thể thành công nhưng client nhận warning. Đây là giai đoạn tốt để migration:

1. Bật `warn`/`audit`.
2. Sửa manifest vi phạm.
3. Theo dõi audit.
4. Chuyển sang `enforce`.

Không nên bật `enforce=restricted` toàn cluster một phát nếu workload chưa được kiểm tra.

### Policy ordering

Admission gồm nhiều plugin và webhook. Một mutating webhook có thể thêm securityContext trước khi validating policy chạy. Nhưng dựa vào mutation để "cứu" manifest kém cần thận trọng:

- Developer có thể không biết manifest thật thiếu gì.
- Debug diff khó hơn.
- GitOps drift có thể xuất hiện nếu cluster mutate object.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | Pod Security Admission và admission webhook là API/behavior upstream | Cần kiểm tra version, enabled admission plugins và namespace labels |
| K3s local/lab | Phù hợp test namespace labels, warning, reject và securityContext | System namespace của K3s có component cần quyền cao; không áp policy bừa lên `kube-system` |
| Self-managed production | Team kiểm soát admission config, webhook availability, audit và policy rollout | Phải tự vận hành Gatekeeper/Kyverno nếu dùng |
| EKS/GKE/AKS | Workload admission semantics vẫn là Kubernetes; cloud quản lý control plane | Team vẫn phải đặt namespace labels/policy controller; cloud có thể có add-on/integration riêng nhưng không thay thế thiết kế policy |

Managed Kubernetes không có nghĩa workload tự an toàn. Cloud provider quản lý API server/control plane, còn team vẫn quyết định policy cho namespace và workload.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| `enforce=baseline` | Default cho nhiều app namespace | Chưa đủ hardening cho workload nhạy cảm |
| `enforce=restricted` | Production app đã chuẩn hóa image/securityContext | Có thể phá legacy apps nếu rollout nhanh |
| `warn`/`audit` trước | Migration, đánh giá impact | Không chặn vi phạm thật nếu kéo dài mãi |
| Pod Security Admission | Built-in, đơn giản, ít vận hành | Chỉ cover Pod security, không policy tùy biến rộng |
| Kyverno | YAML-native, validate/mutate/generate | Cần vận hành controller/webhook; policy design có thể phức tạp |
| Gatekeeper | Policy mạnh với OPA/Rego | Rego learning curve, vận hành webhook |
| `failurePolicy: Fail` webhook | Bảo mật mạnh, fail closed | Webhook down có thể block deploy |
| `failurePolicy: Ignore` webhook | Availability deploy cao hơn | Policy có thể bị bypass khi webhook lỗi |

### Best Practices

- Nên dùng `warn`/`audit` trước khi bật `enforce` cho namespace đang có workload.
- Nên dùng `baseline` làm default tối thiểu cho app namespace.
- Nên hướng workload mới tới `restricted`.
- Nên pin policy version trong production sau khi test.
- Nên tách namespace system/infrastructure khỏi namespace app.
- Nên chuẩn hóa image chạy non-root và không cần privilege.
- Nên thêm securityContext vào Helm chart/service template.
- Nên monitor admission webhook latency/error nếu dùng Gatekeeper/Kyverno.
- Tránh cấp quyền tạo privileged Pod cho app team thông thường.
- Tránh dùng policy mutation để che manifest thiếu securityContext mà không có chuẩn repo.

## Performance Considerations

- Pod Security Admission built-in thường nhẹ hơn webhook bên ngoài vì không cần network call.
- Admission webhook thêm latency vào mỗi request match policy.
- Webhook match quá rộng có thể ảnh hưởng mọi apply/update trong cluster.
- Policy engine down với `failurePolicy: Fail` có thể gây deployment outage.
- Quá nhiều warning/audit violations tạo noise và tăng chi phí audit/log.
- Image chạy non-root/read-only filesystem có thể cần thay đổi app path, startup và volume mount; nếu làm vội có thể gây crash không liên quan Kubernetes.

## Debugging Checklist

Khi `kubectl apply` bị reject:

```bash
kubectl apply -f <file>.yaml
kubectl get namespace <namespace> --show-labels
kubectl describe namespace <namespace>
kubectl auth can-i create pods -n <namespace>
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
```

Kiểm tra:

- Error nói vi phạm profile nào: `baseline` hay `restricted`?
- Namespace đang `enforce`, `warn`, `audit` gì?
- Object bị reject trước khi tạo hay Pod tạo rồi crash?
- Field nào vi phạm: privileged, capabilities, host namespace, seccomp, runAsNonRoot?
- Có webhook nào ngoài Pod Security Admission tham gia không?
- Webhook controller có healthy không?

Lab fix khác production fix:

- Lab: sửa manifest trực tiếp để thấy policy pass.
- Production: sửa Helm chart/template, review securityContext, test ở staging, rồi rollout.

## Production checklist

- [ ] Namespace app có Pod Security labels tối thiểu `baseline`.
- [ ] Workload mới có chuẩn `restricted` nếu khả thi.
- [ ] Policy version được pin và có kế hoạch upgrade.
- [ ] Helm chart/service template có securityContext mặc định tốt.
- [ ] Image chạy non-root và không cần privileged mode.
- [ ] Có exception process cho workload hạ tầng cần quyền cao.
- [ ] Gatekeeper/Kyverno nếu dùng có monitoring, alert và upgrade plan.
- [ ] Audit violations được review định kỳ.
- [ ] RBAC không cho app team tự bypass policy bằng namespace/system quyền rộng.

## Anti-patterns

- Bật `enforce=restricted` toàn cluster khi chưa audit workload.
- Dùng `privileged: true` để fix lỗi permission mà không hiểu nguyên nhân.
- Mount `hostPath` vào app namespace không có review.
- Cho phép `hostNetwork`/`hostPID` cho app thường.
- Dùng image buộc chạy root cho service mới.
- Cài nhiều policy engine chồng chéo nhưng không có owner.
- Để webhook policy down làm block mọi deployment mà không có runbook.
- Bỏ qua warning vì apply vẫn thành công.

## Liên hệ với kiến thức đã biết

- Với Helm charts, `securityContext` nên là default có thể override có kiểm soát.
- Với image build, non-root user và writable path phải được chuẩn hóa từ Dockerfile, không chỉ patch YAML.
- Với RBAC, quyền `create pods` không đủ an toàn nếu admission không kiểm tra nội dung Pod.
- Với GitOps/CI, warning từ PSA nên được xem như migration signal trước khi bật `enforce`.

## Tóm tắt

Pod Security và admission control là lớp bảo vệ nội dung workload trước khi nó chạy. RBAC quyết định ai được gửi request, còn admission quyết định object đó có đạt policy không. Với phần lớn cluster, lộ trình thực dụng là bật `warn`/`audit`, sửa workload để đạt `baseline` hoặc `restricted`, rồi mới enforce. Khi cần policy rộng hơn Pod security, dùng Kyverno hoặc Gatekeeper, nhưng phải xem chúng như thành phần production cần monitoring, upgrade và incident runbook.

## Câu hỏi tự kiểm tra

- Vì sao Pod bị PSA `enforce` reject thường không xuất hiện trong `kubectl get pod`?
- PSA `audit` ghi evidence ở đâu và điều kiện là gì?
- Khi nào nên dùng Kyverno/Gatekeeper thay vì Pod Security Admission?
- Vì sao production nên pin PSA version theo cluster minor?

## Tài liệu tham khảo

- Kubernetes Documentation: Pod Security Standards.
- Kubernetes Documentation: Pod Security Admission.
- Kubernetes Documentation: Admission Controllers.
- Kyverno Documentation và OPA/Gatekeeper Documentation.
