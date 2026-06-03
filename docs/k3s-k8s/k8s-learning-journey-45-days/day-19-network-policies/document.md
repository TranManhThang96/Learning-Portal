# Document - Day 19: NetworkPolicy Reference

## Policy isolation rules

| State | Ingress behavior | Egress behavior |
|---|---|---|
| No policy selects Pod | Allow all ingress | Allow all egress |
| Policy selects Pod with `Ingress` | Only allowed ingress | Egress unchanged |
| Policy selects Pod with `Egress` | Ingress unchanged | Only allowed egress |
| Policy selects Pod with both | Only allowed ingress | Only allowed egress |

Policy là additive allow. Không có explicit deny trong Kubernetes `NetworkPolicy`.

## Default deny all

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

## Allow DNS egress

Kiểm tra label CoreDNS trước:

```bash
kubectl -n kube-system get pods --show-labels | grep -i dns
```

Template phổ biến:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

Nếu namespace không có label `kubernetes.io/metadata.name`, thêm label rõ ràng hoặc dùng selector phù hợp với cluster của bạn.

## Same-namespace frontend to api

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-api
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-egress-to-api
spec:
  podSelector:
    matchLabels:
      role: frontend
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: api
    ports:
    - protocol: TCP
      port: 8080
```

## Cross-namespace selector patterns

AND: Pod label trong namespace label.

```yaml
from:
- namespaceSelector:
    matchLabels:
      team: payments
  podSelector:
    matchLabels:
      app: payment-api
```

OR: toàn bộ namespace hoặc Pod trong namespace hiện tại.

```yaml
from:
- namespaceSelector:
    matchLabels:
      team: payments
- podSelector:
    matchLabels:
      app: payment-api
```

## `ipBlock` template

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-to-partner-api
spec:
  podSelector:
    matchLabels:
      app: billing-worker
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 203.0.113.0/24
        except:
        - 203.0.113.42/32
    ports:
    - protocol: TCP
      port: 443
```

## Selector cheat sheet

| Need | Selector |
|---|---|
| All Pods in current namespace | `podSelector: {}` |
| Pods with one label | `matchLabels: { app: api }` |
| Pods in namespaces with team label | `namespaceSelector.matchLabels.team` |
| Pods with label in namespaces with label | Same `from`/`to` item contains both selectors |
| External CIDR | `ipBlock.cidr` |

## Debug commands

```bash
kubectl get netpol -A
kubectl describe netpol <name> -n <namespace>
kubectl get pods -n <namespace> -o wide --show-labels
kubectl get ns --show-labels
kubectl get svc,endpoints,endpointslice -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Test DNS and HTTP:

```bash
kubectl exec -it <pod> -n <namespace> -- nslookup kubernetes.default
kubectl exec -it <pod> -n <namespace> -- nslookup <service>.<namespace>.svc.cluster.local
kubectl exec -it <pod> -n <namespace> -- wget -qO- --timeout=2 http://<service>:<port>
```

Inspect CNI:

```bash
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
kubectl -n kube-system logs <cni-pod> --tail=100
```

## Common failure modes

| Symptom | Có thể do | First check |
|---|---|---|
| Policy apply thành công nhưng không chặn | CNI không enforce NetworkPolicy | CNI docs/logs, K3s network policy setting |
| App báo DNS fail sau default deny | Thiếu allow DNS egress | `nslookup kubernetes.default` từ Pod |
| Curl timeout nhưng DNS OK | Policy chặn L3/L4 | `describe netpol`, labels nguồn/đích |
| Cross-namespace allow không chạy | Namespace labels sai | `kubectl get ns --show-labels` |
| Chỉ một service bị fail | Selector hoặc port sai | `get pods --show-labels`, `describe svc` |
| Direct Pod IP khác Service behavior | NAT/dataplane/CNI behavior | Test cả Service và Pod IP |

## Service/NAT nuance

- Policy nên match Pod/namespace labels thay vì `ClusterIP` hoặc Pod IP nội bộ.
- Khi gọi qua Service, một số CNI enforce policy quanh thời điểm DNAT khác nhau; test cả Service DNS và direct Pod IP nếu behavior lạ.
- `ports.port` nên phản ánh port backend Pod nhận traffic. Nếu Service `port` khác `targetPort`, kiểm tra implementation CNI bằng test thực tế.
- Egress ra ngoài cluster có thể bị SNAT thành node/NAT/egress gateway IP.

## K3s notes

- K3s thường dùng Flannel làm CNI mặc định.
- K3s có network policy controller mặc định; disable bằng `k3s server --disable-network-policy`.
- Khi dùng custom CNI, K3s docs khuyến nghị `--flannel-backend=none` và thường thêm `--disable-network-policy` để tránh xung đột với policy engine của CNI mới.
- Đừng giả định selector CoreDNS giống mọi cluster; kiểm tra labels thực tế.

## Production checklist

- [ ] Namespace mới có baseline default deny.
- [ ] DNS egress được allow có kiểm soát.
- [ ] Mỗi service có dependency graph rõ.
- [ ] Labels được chuẩn hóa và không đổi tùy tiện.
- [ ] Positive và negative tests nằm trong CI/GitOps validation.
- [ ] CNI policy enforcement được xác nhận sau install/upgrade.
- [ ] Có dashboard/log/metrics cho policy drops nếu CNI hỗ trợ.
- [ ] Runbook phân biệt DNS, Service endpoint và policy drop.

## Quick answer key

- Pod mặc định non-isolated; policy chỉ isolate Pod được `podSelector` chọn theo direction tương ứng.
- Policies là additive allow-list, không có explicit deny trong `NetworkPolicy` chuẩn.
- `podSelector` và `namespaceSelector` trong cùng một list item là AND; hai list items riêng là OR.
- Default deny egress phải allow DNS UDP/TCP 53 tới CoreDNS nếu app dùng service discovery.
- Apply policy thành công không chứng minh policy được enforce; cần xác nhận CNI/policy engine.
