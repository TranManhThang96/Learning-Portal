# Day 34: RBAC + k9s + Lens cho Operations

## Mục tiêu bài học

- Hiểu RBAC trong Kubernetes qua `Role`, `ClusterRole`, `RoleBinding`, `ClusterRoleBinding` và `ServiceAccount`.
- Thiết kế quyền theo nguyên tắc least privilege cho team, service và operator.
- Debug được lỗi `Forbidden` bằng `kubectl auth can-i`, events và object scope.
- Biết dùng k9s và Lens như operational UI mà không biến chúng thành lý do cấp `cluster-admin`.
- Tạo được token/kubeconfig least-privilege để kiểm chứng UI bằng identity thật.
- Phân biệt quyền cần cho đọc logs, exec/debug, rollout, edit config và thao tác cluster-level.

## Vấn đề cần giải quyết

Trong lab cá nhân, bạn thường dùng kubeconfig admin. Trong production, đó là anti-pattern. Một engineer chỉ cần đọc logs không nên có quyền xóa namespace. Một CI/CD service account deploy app namespace `payments` không nên đọc Secret namespace `orders`.

RBAC tốt giúp:

- Giới hạn blast radius khi token/kubeconfig bị lộ.
- Phân tách quyền giữa app team, platform team, CI/CD và incident responders.
- Audit thao tác dễ hơn.
- Tránh UI tool như Lens hoặc k9s vô tình trở thành cổng thao tác cluster-admin.

RBAC kém thường chỉ lộ ra khi incident xảy ra: người cần debug thì thiếu quyền, còn automation thì lại có quyền quá rộng.

## Mental Model

```text
Subject
  user / group / ServiceAccount
        |
        v
Binding
  RoleBinding hoặc ClusterRoleBinding
        |
        v
Role
  Role hoặc ClusterRole
        |
        v
Rules
  apiGroups + resources + verbs + resourceNames
        |
        v
Decision
  can or cannot perform action
```

RBAC không cấp quyền cho "màn hình" hoặc "tool". RBAC cấp quyền cho subject. k9s, Lens, `kubectl` hay CI/CD đều dùng kubeconfig/token của subject đó.

## Lý thuyết cốt lõi

### Authentication, authorization và admission

Luồng request Kubernetes:

```text
Client -> authentication -> authorization -> admission -> persist/execute
```

- Authentication xác định bạn là ai.
- Authorization quyết định bạn có quyền làm hành động đó không.
- Admission kiểm tra hoặc mutate object trước khi lưu.

RBAC nằm ở authorization. Nếu RBAC từ chối, bạn thường thấy:

```text
Error from server (Forbidden): ...
```

### Subject

Subject có thể là:

- User: thường đến từ certificate, OIDC, cloud IAM integration hoặc client auth plugin.
- Group: nhóm user, ví dụ `devs`, `platform`, `system:serviceaccounts:<namespace>`.
- `ServiceAccount`: identity cho Pod hoặc automation trong cluster.

Trong app deployment, `ServiceAccount` quan trọng hơn user vì Pod nên dùng identity riêng, không dùng token mặc định có quyền mơ hồ.

### Role và ClusterRole

`Role` là namespaced. Nó chỉ mô tả quyền trong một namespace.

```yaml
kind: Role
metadata:
  namespace: payments
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
```

`ClusterRole` là cluster-scoped. Nó có thể mô tả:

- Quyền trên cluster-scoped resources như `nodes`, `namespaces`, `persistentvolumes`.
- Quyền reusable cho namespaced resources, rồi bind vào từng namespace bằng `RoleBinding`.

Điểm dễ nhầm: `ClusterRole` không tự cấp quyền. Binding mới cấp quyền.

### RoleBinding và ClusterRoleBinding

`RoleBinding` cấp quyền trong namespace của binding. Nó có thể tham chiếu `Role` hoặc `ClusterRole`.

`ClusterRoleBinding` cấp quyền cluster-wide. Dùng rất thận trọng.

Ví dụ hay dùng:

- Tạo một `ClusterRole` `app-readonly`.
- Bind nó bằng `RoleBinding` vào namespace `team-a`.
- Team chỉ đọc namespace đó, không đọc toàn cluster.

### Verbs và resources

Các verb thường gặp:

| Verb | Ý nghĩa vận hành |
|---|---|
| `get` | Đọc một object |
| `list` | Liệt kê object |
| `watch` | Theo dõi thay đổi, cần cho UI/controller |
| `create` | Tạo object mới |
| `update` | Thay toàn bộ object |
| `patch` | Sửa một phần object |
| `delete` | Xóa object |
| `deletecollection` | Xóa nhiều object |

Subresource quan trọng:

| Resource | Dùng cho |
|---|---|
| `pods/log` | `kubectl logs` |
| `pods/exec` | `kubectl exec` |
| `pods/portforward` | `kubectl port-forward` |
| `pods/ephemeralcontainers` | `kubectl debug` ephemeral container |
| `deployments/scale` | scale Deployment |
| `deployments/status` | đọc status |
| `events` trong `events.k8s.io` | đọc Events API mới |

Nếu bạn chỉ cấp `pods`, user chưa chắc đọc được logs hoặc exec được vào Pod.

### ServiceAccount tokens

Pod chạy với một `ServiceAccount`. Nếu không chỉ định, Pod dùng `default` service account của namespace.

Best practice:

- Tạo service account riêng cho workload cần gọi API server.
- Nếu app không cần gọi Kubernetes API, đặt `automountServiceAccountToken: false`.
- Không bind quyền rộng cho `default` service account.
- Token dùng trong Pod phải được xem như secret credential.

Với tool như k9s/Lens, hãy kiểm chứng bằng token/kubeconfig của identity least-privilege, không chỉ bằng `kubectl auth can-i --as`. Lệnh `--as` cần quyền impersonate trên cluster; kubeconfig readonly cho bạn kiểm thử gần với thực tế hơn:

```bash
kubectl create token ui-viewer -n day34 --duration=2h
kubectl --kubeconfig=day34-viewer.kubeconfig get pods -n day34
kubectl --kubeconfig=day34-viewer.kubeconfig get secrets -n day34
```

### Built-in roles

Kubernetes có các `ClusterRole` built-in như `view`, `edit`, `admin`, `cluster-admin`.

Điểm cần cẩn thận:

- `view` thường phù hợp read-only nhưng có thể không đọc Secret.
- `edit` rất rộng cho namespace và có thể dẫn tới leo quyền nếu user tạo Pod dùng service account có quyền cao hoặc đọc Secret.
- `admin` nên giới hạn theo namespace qua `RoleBinding`.
- `cluster-admin` chỉ dành cho break-glass/platform admin có kiểm soát.

## k9s và Lens trong operations

### k9s

k9s là terminal UI dùng kubeconfig hiện tại. Nó giúp:

- Chuyển namespace/context nhanh.
- Xem Pod, logs, describe, events.
- Exec shell, port-forward, delete, scale tùy quyền.
- Lọc theo label và resource.

k9s không bỏ qua RBAC. Nếu subject không có quyền `delete pods`, thao tác xóa từ k9s cũng sẽ bị `Forbidden`.

Trong production, mở k9s bằng context readonly mặc định. Chỉ chuyển sang break-glass/admin context khi có ticket, thời hạn và audit rõ ràng.

### Lens

Lens là desktop UI để quan sát cluster. Nó tiện cho:

- Xem object graph.
- Xem logs/events.
- Kiểm tra resource usage.
- Điều hướng multi-cluster.

Rủi ro Lens thường nằm ở kubeconfig:

- Import nhầm kubeconfig admin.
- Share kubeconfig qua chat/email.
- Không tách context production/staging rõ.
- Dùng Lens để edit live object ngoài GitOps mà không ghi lại.

Tool tốt không thay thế policy tốt. Quyền vẫn phải thiết kế ở RBAC và quy trình.

## Deep dive: Debug lỗi Forbidden

Ví dụ lỗi:

```text
Error from server (Forbidden): pods is forbidden: User "system:serviceaccount:day34:viewer" cannot list resource "pods" in API group "" in the namespace "day34"
```

Đọc lỗi theo cấu trúc:

- Subject: `system:serviceaccount:day34:viewer`
- Verb: `list`
- Resource: `pods`
- API group: `""` core group
- Namespace: `day34`

Sau đó kiểm tra:

```bash
kubectl auth can-i list pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl get rolebinding -n day34
kubectl describe rolebinding <name> -n day34
kubectl describe role <name> -n day34
```

RBAC debug hiệu quả là debug đủ 4 phần: subject, verb, resource và scope.

Nếu user hiện tại không có quyền impersonate, `--as` có thể bị từ chối trước khi bạn kiểm tra được subject mục tiêu. Khi đó hãy tạo kubeconfig/token least-privilege trong lab hoặc nhờ platform team chạy `can-i` bằng quyền phù hợp.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

| Môi trường | Điểm giống | Điểm cần lưu ý |
|---|---|---|
| Kubernetes chuẩn | RBAC API giống nhau: Role, ClusterRole, Binding, ServiceAccount | Identity provider và audit pipeline phụ thuộc cluster setup |
| K3s local/lab | Thường dùng kubeconfig admin từ node server; thuận tiện học nhanh | Đừng lấy thói quen admin kubeconfig sang production; cần tự tạo roles để luyện least privilege |
| Self-managed production | Team tự tích hợp OIDC, certificate, audit logs, break-glass và RBAC baseline | Phải tự quản lý lifecycle user/group, kubeconfig và token rotation |
| EKS/GKE/AKS | Kubernetes RBAC vẫn áp dụng cho API server | Cloud IAM/OIDC/identity integration thêm một lớp; cloud quản lý control plane nhưng team vẫn thiết kế namespace permissions |

Managed Kubernetes không tự thiết kế quyền cho team bạn. Nó chỉ cung cấp cơ chế identity và control plane được quản lý.

## Trade-offs và Best Practices

### Trade-offs

| Lựa chọn | Khi nên dùng | Rủi ro |
|---|---|---|
| `Role` trong namespace | Quyền cụ thể cho team/app | Dễ lặp lại YAML nếu nhiều namespace |
| `ClusterRole` + `RoleBinding` | Reuse permission set nhiều namespace | Dễ nhầm là quyền toàn cluster nếu đọc không kỹ |
| `ClusterRoleBinding` | Platform/admin/cluster-scoped controller | Blast radius lớn |
| Built-in `view` | Read-only nhanh | Có thể thiếu subresource cần thiết như logs tùy rule |
| Custom read-only role | Kiểm soát chính xác logs/events/endpoints | Cần maintain khi API mới phát sinh |
| `edit` cho app team | Namespace dev/staging có kiểm soát | Rộng, có thể tạo rủi ro secrets/service account |
| k9s/Lens | Quan sát nhanh, incident operations | Dễ thao tác live ngoài GitOps nếu quyền quá rộng |
| CLI-only | Audit thao tác rõ hơn nếu đi qua scripts/runbooks | Chậm hơn khi incident cần quan sát nhiều object |

### Best Practices

- Nên cấp quyền theo namespace/team/service, không cấp theo cá nhân tùy hứng.
- Nên dùng group từ identity provider thay vì bind từng user thủ công.
- Nên tạo `ServiceAccount` riêng cho workload cần gọi API.
- Nên đặt `automountServiceAccountToken: false` nếu workload không cần Kubernetes API.
- Nên dùng `kubectl auth can-i` trong runbook và CI check.
- Nên tách quyền read logs, exec/debug và mutate resources.
- Nên cấp cả core `events` và `events.k8s.io` `events` cho readonly operations context.
- Nên giới hạn `cluster-admin` cho break-glass có audit.
- Tránh dùng kubeconfig admin trong Lens/k9s thường ngày.
- Tránh bind quyền rộng cho `default` service account.
- Tránh cho CI/CD quyền cluster-wide nếu chỉ deploy một namespace.

## Performance Considerations

- RBAC decision là một phần của API request path, nhưng thường không phải bottleneck chính.
- UI tools như Lens/k9s dùng `list`/`watch` nhiều resource; trên cluster lớn có thể tạo tải đáng kể lên API server nếu nhiều người mở cùng lúc.
- Cấp quyền `watch` rộng toàn cluster làm client nhận nhiều event hơn, tăng network và memory client.
- Controller/service account bị thiếu quyền có thể retry liên tục, tạo log noise và API load.
- Audit logs cho Kubernetes API cần retention và storage planning, đặc biệt với cluster lớn.

## Debugging Checklist

Khi gặp `Forbidden`:

```bash
kubectl auth can-i <verb> <resource> -n <namespace>
kubectl auth can-i <verb> <resource> -n <namespace> --as=<subject>
kubectl get role,rolebinding -n <namespace>
kubectl get clusterrole,clusterrolebinding
kubectl describe rolebinding <name> -n <namespace>
kubectl describe clusterrolebinding <name>
```

Kiểm tra:

- Subject có đúng không: user, group hay service account?
- Verb có đúng không: `get`, `list`, `watch`, `create`, `patch`, `delete`?
- Resource có phải subresource không: `pods/log`, `pods/exec`, `pods/ephemeralcontainers`?
- Scope có đúng namespace không?
- Binding tham chiếu đúng `Role`/`ClusterRole` không?
- API group có đúng không?

Lab fix khác production fix:

- Lab: có thể patch RoleBinding trực tiếp để học.
- Production: sửa RBAC manifest trong GitOps repo, review, sync, rồi verify bằng `can-i`.

## Production checklist

- [ ] Có RBAC baseline cho readonly, developer, deployer, incident responder và platform admin.
- [ ] Không dùng kubeconfig admin cho thao tác thường ngày.
- [ ] CI/CD service account chỉ có quyền trong namespace cần deploy.
- [ ] Workload service account không tự động mount token nếu không cần.
- [ ] Có audit cho thao tác mutation, exec/debug và secret access.
- [ ] Có break-glass process rõ ràng.
- [ ] k9s/Lens dùng context least-privilege mặc định.
- [ ] Token/kubeconfig UI có thời hạn, owner và quy trình rotation.
- [ ] Runbook ghi rõ quyền cần có cho từng loại incident.

## Anti-patterns

- Bind `cluster-admin` để sửa nhanh lỗi `Forbidden`.
- Dùng cùng một service account cho mọi workload.
- Cấp `edit`/`admin` cho namespace production mà không hiểu quyền Secret.
- Cho UI tool quyền rộng hơn CLI chỉ vì "dễ dùng".
- Không kiểm tra `pods/log`, `pods/exec`, `pods/portforward` là subresource riêng.
- Sửa live RBAC ngoài GitOps rồi quên commit lại.
- Share kubeconfig qua kênh không an toàn.

## Liên hệ với kiến thức đã biết

- Với CI/CD, ServiceAccount deployer nên có quyền namespace-limited thay vì token admin.
- Với GitOps, UI edit live object có thể tạo drift giữa cluster và repo.
- Với observability, readonly identity cần logs/events/endpoints nhưng không cần Secrets hoặc delete.
- Với incident response, break-glass context phải có thời hạn, audit và reason rõ.

## Tóm tắt

RBAC là hệ thống trả lời câu hỏi: subject nào được làm verb nào trên resource nào ở scope nào. Khi nắm được bốn phần đó, lỗi `Forbidden` trở thành vấn đề có thể debug có thứ tự. k9s và Lens là công cụ operations rất tốt, nhưng chúng phải chạy trên identity được cấp quyền đúng. Production Kubernetes cần RBAC như một phần của thiết kế platform, không phải bước sửa sau khi cluster đã chạy.

## Câu hỏi tự kiểm tra

- Vì sao `ClusterRole` không tự cấp quyền nếu chưa có Binding?
- Khi nào dùng `RoleBinding` tới `ClusterRole` thay vì `ClusterRoleBinding`?
- Vì sao k9s/Lens phải dùng kubeconfig least-privilege trong production?
- Quyền đọc `pods/log` khác quyền đọc `pods` như thế nào?

## Tài liệu tham khảo

- Kubernetes Documentation: RBAC Authorization.
- Kubernetes Documentation: ServiceAccount Tokens.
- Kubernetes Documentation: `kubectl auth can-i`.
- k9s Documentation và Lens Documentation về kubeconfig/context.
