# Document - Day 18: Kubernetes DNS Reference

## DNS naming patterns

| Object | DNS name | Resolves to |
|---|---|---|
| Service | `<svc>.<ns>.svc.cluster.local` | Service ClusterIP |
| Service short name | `<svc>` | Service in same namespace via search domain |
| Headless Service | `<svc>.<ns>.svc.cluster.local` | Endpoint Pod IPs |
| SRV record | `_<port>._<proto>.<svc>.<ns>.svc.cluster.local` | Port and target records |
| Stateful Pod | `<pod>.<headless-svc>.<ns>.svc.cluster.local` | Stable Pod IP if configured |

## Example `/etc/resolv.conf`

```text
nameserver 10.43.0.10
search day18.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

## dnsPolicy matrix

| dnsPolicy | Use case | Risk |
|---|---|---|
| `ClusterFirst` | Default for normal Pods | Usually correct |
| `Default` | Inherit node DNS | May lose `svc.cluster.local` discovery |
| `ClusterFirstWithHostNet` | `hostNetwork: true` Pods needing cluster DNS | Forgetting it breaks service discovery |
| `None` | Custom `dnsConfig` | Easy to misconfigure |

## Minimal Service and DNS test

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: http
```

```bash
kubectl run dns-test --rm -it --restart=Never --image=busybox:1.36 -- nslookup web
kubectl run dns-test --rm -it --restart=Never --image=busybox:1.36 -- nslookup web.day18.svc.cluster.local
```

## Headless Service template

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-headless
spec:
  clusterIP: None
  selector:
    app: web
  ports:
  - name: http
    port: 8080
    targetPort: http
```

## CoreDNS commands

```bash
kubectl -n kube-system get svc kube-dns
kubectl -n kube-system get deploy,pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system get configmap coredns -o yaml
kubectl -n kube-system logs deploy/coredns --tail=100
kubectl -n kube-system rollout status deployment/coredns
```

## Debug from a Pod

```bash
kubectl exec -it <pod> -n <namespace> -- cat /etc/resolv.conf
kubectl exec -it <pod> -n <namespace> -- nslookup kubernetes.default
kubectl exec -it <pod> -n <namespace> -- nslookup <svc>.<ns>.svc.cluster.local
kubectl exec -it <pod> -n <namespace> -- wget -qO- http://<svc>.<ns>.svc.cluster.local:<port>
```

## Failure modes

| Symptom | Có thể do | First commands |
|---|---|---|
| `nslookup web` fail cross-namespace | Short name wrong namespace | Use FQDN |
| `*.svc.cluster.local` fail all namespaces | CoreDNS down/config issue | `get pods -l k8s-app=kube-dns`, logs |
| External DNS fail, internal DNS ok | Upstream resolver/forward plugin | CoreDNS Corefile, logs |
| DNS ok, curl fail | Service endpoint/dataplane/app port | `get svc,endpoints,endpointslice` |
| Pod only fails when `hostNetwork` | Wrong `dnsPolicy` | Inspect Pod spec/resolv.conf |
| DNS timeout under load | CoreDNS CPU/QPS/cache issue | CoreDNS metrics/logs, Pod resources |
| DNS blocked only in one namespace | NetworkPolicy egress | Check UDP/TCP 53 allow rules |

## NetworkPolicy DNS allow pattern

Preview này dùng cho sau Day 19. Trong Day 18, chỉ cần hiểu DNS có thể bị policy egress chặn; chưa cần debug policy sâu.

Nếu namespace dùng default deny egress, cần allow DNS tới CoreDNS. Selector có thể khác theo distro, nên kiểm tra labels thực tế trước.

```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns --show-labels
```

Example pattern:

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

## Production checklist

- [ ] CoreDNS replicas, CPU/memory and alerts are configured.
- [ ] CoreDNS Corefile is versioned and reviewed.
- [ ] Application config uses FQDN for cross-namespace dependencies.
- [ ] NetworkPolicy allows DNS egress where needed.
- [ ] DNS latency/error rate is monitored.
- [ ] High-QPS clients use caching/connection pooling appropriately.
- [ ] `hostNetwork` Pods use correct `dnsPolicy`.
- [ ] Runbook separates DNS failure from Service/Endpoint failure.

## Quick answer key

- Service thường resolve về `ClusterIP`; Headless Service resolve về endpoint Pod IPs.
- Short name chỉ an toàn trong cùng namespace; cross-namespace nên dùng FQDN.
- `ndots:5` có thể làm external lookup phát sinh nhiều query search-domain trước khi query absolute name.
- `dnsPolicy: None` với nameserver sai làm Pod fail DNS dù CoreDNS khỏe.
- DNS resolve OK chưa đảm bảo HTTP/gRPC connect OK; còn Service, EndpointSlice, NetworkPolicy và app port.
