# Day 12: Kubernetes Networking — Cheat Sheet & Reference

## Service Type Comparison

| Feature | ClusterIP | NodePort | LoadBalancer | Headless |
|---------|-----------|----------|--------------|----------|
| **Scope** | Internal only | External via node port | External via cloud LB | Internal (direct pod) |
| **IP** | Virtual IP (stable) | Virtual IP + node port | External IP + virtual IP | No virtual IP |
| **DNS** | Returns ClusterIP | Returns ClusterIP | Returns external IP | Returns pod IPs |
| **Port range** | Any | 30000-32767 | Any | Any |
| **Load balancing** | kube-proxy (random) | kube-proxy | Cloud LB + kube-proxy | Client-side |
| **Cost** | Free | Free | Cloud LB cost | Free |
| **Use case** | Service-to-service | Dev/test, simple expose | Production expose | StatefulSet, direct access |
| **Production** | ✅ Primary choice | ⚠️ Dev/test only | ✅ Single service | ✅ Stateful workloads |

## DNS Reference

### Naming Convention

```
# Service (most common)
<service>.<namespace>.svc.cluster.local

# Short forms (within cluster)
<service>                           # Same namespace
<service>.<namespace>               # Cross namespace

# StatefulSet pod (via headless service)
<pod-name>.<service>.<namespace>.svc.cluster.local

# Pod (rarely used directly)
<pod-ip-dashes>.<namespace>.pod.cluster.local
```

### DNS Debug Commands

```bash
# From inside a pod
nslookup <service-name>
nslookup <service-name>.<namespace>
nslookup <service-name>.<namespace>.svc.cluster.local

# Quick debug pod
kubectl run dns-debug --rm -it --image=busybox:1.36 --restart=Never -- nslookup <service>

# Check resolv.conf
kubectl exec <pod> -- cat /etc/resolv.conf

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

### ndots Optimization

```yaml
# Default ndots:5 causes extra DNS queries for external domains
# Fix: reduce ndots or use FQDN with trailing dot
spec:
  dnsConfig:
    options:
      - name: ndots
        value: "2"
```

## Service Debugging Flowchart

```
Service không hoạt động?
│
├─ kubectl get endpoints <svc>
│  ├─ ENDPOINTS trống?
│  │  ├─ Selector match labels? → kubectl get pods --show-labels
│  │  └─ Pod READY? → kubectl describe pod <pod>
│  │     └─ Readiness probe fail? → Fix probe config
│  │
│  └─ ENDPOINTS có IPs
│     ├─ targetPort đúng? → kubectl get svc -o yaml
│     ├─ Pod listen đúng port? → kubectl exec <pod> -- ss -tlnp
│     └─ Network issue? → kubectl exec <pod> -- wget -qO- http://<svc>
│
├─ DNS issue?
│  ├─ CoreDNS running? → kubectl get pods -n kube-system -l k8s-app=kube-dns
│  ├─ DNS svc accessible? → kubectl get svc -n kube-system kube-dns
│  └─ resolv.conf correct? → kubectl exec <pod> -- cat /etc/resolv.conf
│
└─ NetworkPolicy blocking? → kubectl get networkpolicy
```

## kubectl Networking Commands

```bash
# Services
kubectl get svc                              # List services
kubectl get svc -o wide                      # Show selectors
kubectl describe svc <name>                  # Full details
kubectl get svc <name> -o yaml               # YAML output

# Endpoints
kubectl get endpoints                        # List all endpoints
kubectl get endpoints <svc>                  # Specific service endpoints
kubectl get endpointslice -l kubernetes.io/service-name=<svc>

# DNS debugging
kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- nslookup <svc>
kubectl run curl-test --rm -it --image=curlimages/curl --restart=Never -- curl -v http://<svc>

# Port forwarding (dev/debug)
kubectl port-forward svc/<name> 8080:80      # Forward local:8080 → svc:80
kubectl port-forward pod/<name> 8080:80      # Forward to specific pod

# Network debugging from pod
kubectl exec <pod> -- ss -tlnp               # Show listening ports
kubectl exec <pod> -- cat /etc/resolv.conf   # DNS config
kubectl exec <pod> -- wget -qO- http://<svc> # HTTP test
kubectl exec <pod> -- nslookup <svc>         # DNS test

# kube-proxy
kubectl get pods -n kube-system -l k8s-app=kube-proxy
kubectl logs -n kube-system <kube-proxy-pod>
```

## kube-proxy Mode Comparison

| Aspect | iptables | IPVS | eBPF (Cilium) |
|--------|----------|------|---------------|
| **Default** | ✅ Yes | No | No |
| **Setup** | Zero config | Enable IPVS kernel module | Install Cilium |
| **Rule lookup** | O(n) linear | O(1) hash | O(1) eBPF map |
| **Max services** | ~5,000 | ~100,000 | Unlimited |
| **LB algorithms** | Random | RR, weighted, least-conn, hash | Maglev, random |
| **Connection tracking** | conntrack | conntrack | eBPF conntrack |
| **Session affinity** | ✅ | ✅ | ✅ |
| **Health checking** | Via readiness | Via readiness | ✅ Native |
| **Observability** | iptables -L | ipvsadm -L | Hubble |
| **Recommended for** | < 1000 services | 1000-10000 services | Any scale, modern stack |

## externalTrafficPolicy

```yaml
spec:
  type: NodePort  # or LoadBalancer
  externalTrafficPolicy: Cluster  # default
  # or
  externalTrafficPolicy: Local
```

| Policy | Behavior | Pros | Cons |
|--------|----------|------|------|
| `Cluster` | Forwards to any pod on any node | Even distribution | Extra network hop, lose source IP |
| `Local` | Only forwards to pods on same node | Preserve source IP, no extra hop | Uneven distribution, may fail if no local pod |

## Production Checklist

### Service Configuration
- [ ] Correct selector labels matching pod labels
- [ ] Proper port and targetPort mapping
- [ ] Appropriate service type for use case
- [ ] Named ports for clarity
- [ ] Session affinity if needed

### DNS & Discovery
- [ ] Apps use service DNS names, not pod IPs
- [ ] Cross-namespace calls use full name: `<svc>.<ns>`
- [ ] ndots optimized for external domain heavy workloads
- [ ] CoreDNS resources adequate for cluster size

### Security
- [ ] NodePort restricted to necessary services only
- [ ] NetworkPolicy defined (default deny recommended)
- [ ] automountServiceAccountToken: false where not needed
- [ ] No unnecessary LoadBalancer services

### Monitoring
- [ ] CoreDNS metrics scraped
- [ ] Endpoint count monitored (alert on 0)
- [ ] DNS latency tracked
- [ ] Service response time measured

