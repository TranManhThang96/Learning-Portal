# Day 17: Document — Microservice Stack Deployment Reference

---

## 1. kubectl Debug Cheat Sheet cho Multi-service Deployments

### Tổng quan nhanh

```bash
# Xem tất cả resources trong namespace
kubectl get all -n <namespace>

# Xem events (sorted by time)
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Xem resource usage (cần metrics-server)
kubectl top pods -n <namespace>
kubectl top nodes
```

### Pod Debugging

```bash
# Xem pod status
kubectl get pods -n <ns> -o wide

# Xem chi tiết pod (events, conditions, volumes)
kubectl describe pod <pod> -n <ns>

# Xem logs
kubectl logs <pod> -n <ns>
kubectl logs <pod> -n <ns> --previous          # logs từ crash trước
kubectl logs <pod> -n <ns> -c <container>       # multi-container pod
kubectl logs <pod> -n <ns> --tail=100           # 100 dòng cuối
kubectl logs <pod> -n <ns> -f                   # follow logs
kubectl logs -l app=api-gateway -n <ns>         # logs theo label

# Exec vào pod
kubectl exec -it <pod> -n <ns> -- /bin/sh
kubectl exec <pod> -n <ns> -- env              # xem env vars
kubectl exec <pod> -n <ns> -- cat /etc/nginx/conf.d/default.conf

# Debug pod không start được
kubectl debug <pod> -n <ns> -it --image=busybox
```

### Service & Networking

```bash
# Xem service endpoints
kubectl get endpoints <service> -n <ns>
kubectl get endpointslices -l kubernetes.io/service-name=<service> -n <ns>

# Test DNS resolution
kubectl exec <pod> -n <ns> -- nslookup <service>
kubectl exec <pod> -n <ns> -- nslookup <service>.<ns>.svc.cluster.local

# Test connectivity
kubectl exec <pod> -n <ns> -- curl -s http://<service>:<port>/health
kubectl exec <pod> -n <ns> -- wget -qO- http://<service>:<port>/api/books

# Port forward để test từ local
kubectl port-forward svc/<service> <local-port>:<service-port> -n <ns>
kubectl port-forward pod/<pod> <local-port>:<container-port> -n <ns>
```

### ConfigMap & Secret

```bash
# Xem ConfigMap
kubectl get cm -n <ns>
kubectl describe cm <name> -n <ns>
kubectl get cm <name> -n <ns> -o yaml

# Xem Secret (decoded)
kubectl get secret <name> -n <ns> -o jsonpath='{.data.<key>}' | base64 -d

# Verify ConfigMap mount trong pod
kubectl exec <pod> -n <ns> -- ls /etc/nginx/conf.d/
kubectl exec <pod> -n <ns> -- cat /etc/nginx/conf.d/default.conf
```

### Storage

```bash
# PVC status
kubectl get pvc -n <ns>
kubectl describe pvc <name> -n <ns>

# PV details
kubectl get pv
kubectl describe pv <name>

# Verify data trong volume
kubectl exec <pod> -n <ns> -- ls /data/
kubectl exec <pod> -n <ns> -- df -h /data/
```

### Ingress

```bash
# Xem Ingress
kubectl get ingress -n <ns>
kubectl describe ingress <name> -n <ns>

# Ingress Controller logs
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=50
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | grep "bookstore"

# Test Ingress rules
curl -H "Host: bookstore.local" http://localhost/
curl -H "Host: bookstore.local" http://localhost/api/books
```

---

## 2. Kubernetes Resource Relationship Diagram

```
Namespace: bookstore
│
├── Deployments
│   ├── frontend (replicas: 1)
│   │   ├── Pod: frontend-xxx-yyy
│   │   │   └── Container: frontend (nginx:1.25-alpine)
│   │   │       ├── Volume: html → ConfigMap/frontend-config
│   │   │       ├── Port: 80
│   │   │       ├── ReadinessProbe: HTTP GET / :80
│   │   │       └── LivenessProbe: HTTP GET / :80
│   │   └── Service: frontend (ClusterIP, port 80)
│   │
│   ├── api-gateway (replicas: 2)
│   │   ├── Pod: api-gateway-xxx-yyy
│   │   │   └── Container: api-gateway (nginx:1.25-alpine)
│   │   │       ├── Volume: nginx-config → ConfigMap/api-gateway-config
│   │   │       ├── Port: 8080
│   │   │       ├── ReadinessProbe: HTTP GET /gateway/health :8080
│   │   │       └── LivenessProbe: HTTP GET /gateway/health :8080
│   │   └── Service: api-gateway (ClusterIP, port 8080)
│   │
│   └── book-service (replicas: 2)
│       ├── Pod: book-service-xxx-yyy
│       │   └── Container: book-service (nginx:1.25-alpine)
│       │       ├── Volume: nginx-config → ConfigMap/book-service-config
│       │       ├── Env: REDIS_PASSWORD → Secret/redis-secret
│       │       ├── Port: 80
│       │       ├── ReadinessProbe: HTTP GET /api/health :80
│       │       └── LivenessProbe: HTTP GET /api/health :80
│       └── Service: book-service (ClusterIP, port 80)
│
├── StatefulSets
│   └── redis (replicas: 1)
│       ├── Pod: redis-0
│       │   └── Container: redis (redis:7-alpine)
│       │       ├── VolumeMount: /data → PVC/redis-data-redis-0
│       │       ├── Env: REDIS_PASSWORD → Secret/redis-secret
│       │       ├── Port: 6379
│       │       └── ReadinessProbe: exec redis-cli ping
│       ├── Service: redis (Headless ClusterIP=None, port 6379)
│       └── PVC: redis-data-redis-0 (1Gi, RWO)
│
├── ConfigMaps
│   ├── frontend-config (index.html)
│   ├── api-gateway-config (nginx proxy config)
│   └── book-service-config (API mock config)
│
├── Secrets
│   └── redis-secret (redis-password)
│
└── Ingress
    └── bookstore-ingress
        ├── Rule: bookstore.local/api/* → api-gateway:8080
        └── Rule: bookstore.local/* → frontend:80
```

---

## 3. Deployment Checklist

### Pre-deployment

- [ ] Kind cluster running: `kind get clusters`
- [ ] kubectl context đúng: `kubectl config current-context`
- [ ] NGINX Ingress Controller ready: `kubectl get pods -n ingress-nginx`
- [ ] All YAML files valid: `kubectl apply --dry-run=client -k overlays/dev`
- [ ] Host entry configured: `grep bookstore /etc/hosts`

### During deployment

- [ ] Apply manifests: `kubectl apply -k overlays/dev`
- [ ] Wait for pods: `kubectl wait --for=condition=ready pod --all -n bookstore`
- [ ] Check events: `kubectl get events -n bookstore`
- [ ] No error events: `kubectl get events -n bookstore --field-selector type=Warning`

### Post-deployment verification

- [ ] All pods Running/Ready: `kubectl get pods -n bookstore`
- [ ] All services have endpoints: `kubectl get endpoints -n bookstore`
- [ ] PVC bound: `kubectl get pvc -n bookstore`
- [ ] Ingress configured: `kubectl get ingress -n bookstore`
- [ ] Frontend accessible: `curl -s http://bookstore.local/`
- [ ] API accessible: `curl -s http://bookstore.local/api/books`
- [ ] Redis responding: `kubectl exec -n bookstore redis-0 -- redis-cli -a bookstore-redis-pass ping`
- [ ] Service-to-service: `kubectl exec -n bookstore deploy/api-gateway -- curl -s http://book-service/api/health`

---

## 4. Common Error Resolution Guide

### Pod Issues

| Status | Nguyên nhân thường gặp | Debug command | Fix |
|--------|----------------------|---------------|-----|
| **Pending** | Không đủ resources, PVC chưa bound | `kubectl describe pod <pod>` | Kiểm tra node resources, StorageClass |
| **ImagePullBackOff** | Image không tồn tại | `kubectl describe pod <pod>` | Kiểm tra image name/tag |
| **CrashLoopBackOff** | App crash, config sai | `kubectl logs <pod> --previous` | Kiểm tra config, command |
| **OOMKilled** | Memory limit quá thấp | `kubectl describe pod <pod>` | Tăng memory limit |
| **CreateContainerConfigError** | Secret/ConfigMap thiếu | `kubectl describe pod <pod>` | Tạo missing Secret/ConfigMap |
| **Error** | Nhiều nguyên nhân | `kubectl logs <pod>` | Xem logs chi tiết |
| **Terminating** (stuck) | Finalizer hoặc volume unmount | `kubectl describe pod <pod>` | Force delete: `kubectl delete pod <pod> --force --grace-period=0` |

### Service Issues

| Vấn đề | Debug | Fix |
|--------|-------|-----|
| Service không resolve | `kubectl exec -- nslookup <svc>` | Kiểm tra Service selector match pod labels |
| Service trả empty response | `kubectl get endpoints <svc>` | Kiểm tra pods running và ready |
| Connection refused | `curl -v http://<svc>:<port>` | Kiểm tra container port và targetPort match |

### Ingress Issues

| Vấn đề | Debug | Fix |
|--------|-------|-----|
| 404 Not Found | `kubectl describe ingress` | Kiểm tra path rules, rewrite annotations |
| 502 Bad Gateway | `kubectl get endpoints` | Backend pods not ready |
| 503 Service Unavailable | Ingress Controller logs | Service hoặc upstream không available |
| SSL error | Cert check | Kiểm tra TLS secret |

### Storage Issues

| Vấn đề | Debug | Fix |
|--------|-------|-----|
| PVC Pending | `kubectl describe pvc` | Kiểm tra StorageClass tồn tại |
| Data lost after recreate | PV reclaim policy | Dùng `Retain` policy, backup trước khi delete |
| Permission denied | `kubectl exec -- ls -la /data` | Kiểm tra securityContext, fsGroup |

---

## 5. Quick Verification Script

```bash
#!/bin/bash
# verify-bookstore.sh - Quick health check for BookStore stack

set -euo pipefail
NAMESPACE="bookstore"
PASS=0
FAIL=0

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "✅ $desc"
        ((PASS++))
    else
        echo "❌ $desc"
        ((FAIL++))
    fi
}

echo "=== BookStore Stack Verification ==="
echo ""

# Pod checks
echo "--- Pod Status ---"
check "frontend pods ready" kubectl wait -n $NAMESPACE --for=condition=ready pod -l app=frontend --timeout=5s
check "api-gateway pods ready" kubectl wait -n $NAMESPACE --for=condition=ready pod -l app=api-gateway --timeout=5s
check "book-service pods ready" kubectl wait -n $NAMESPACE --for=condition=ready pod -l app=book-service --timeout=5s
check "redis pods ready" kubectl wait -n $NAMESPACE --for=condition=ready pod -l app=redis --timeout=5s

# Service checks
echo ""
echo "--- Service Endpoints ---"
check "frontend has endpoints" test "$(kubectl get endpoints frontend -n $NAMESPACE -o jsonpath='{.subsets[0].addresses}' 2>/dev/null)" != ""
check "api-gateway has endpoints" test "$(kubectl get endpoints api-gateway -n $NAMESPACE -o jsonpath='{.subsets[0].addresses}' 2>/dev/null)" != ""
check "book-service has endpoints" test "$(kubectl get endpoints book-service -n $NAMESPACE -o jsonpath='{.subsets[0].addresses}' 2>/dev/null)" != ""

# PVC check
echo ""
echo "--- Storage ---"
check "redis PVC bound" test "$(kubectl get pvc redis-data-redis-0 -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null)" = "Bound"

# Connectivity checks
echo ""
echo "--- Connectivity ---"
check "book-service API works" kubectl exec -n $NAMESPACE deploy/api-gateway -- curl -sf http://book-service/api/health
check "Redis responds" kubectl exec -n $NAMESPACE redis-0 -- redis-cli -a bookstore-redis-pass ping

# Ingress checks (only if host configured)
echo ""
echo "--- Ingress ---"
check "Ingress exists" kubectl get ingress bookstore-ingress -n $NAMESPACE

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ $FAIL -gt 0 ]; then
    echo "⚠️  Some checks failed. Run debug commands to investigate."
    exit 1
fi
```

---

## 6. Project File Structure Reference

```
bookstore-k8s/
├── base/
│   ├── kustomization.yaml          # Resource list + common labels
│   ├── namespace.yaml              # bookstore namespace
│   │
│   ├── redis-secret.yaml           # Redis password (base64)
│   ├── redis-statefulset.yaml      # StatefulSet + PVC template
│   ├── redis-service.yaml          # Headless service
│   │
│   ├── book-service-configmap.yaml # NGINX config + app config
│   ├── book-service-deployment.yaml
│   ├── book-service-service.yaml
│   │
│   ├── api-gateway-configmap.yaml  # NGINX proxy config
│   ├── api-gateway-deployment.yaml
│   ├── api-gateway-service.yaml
│   │
│   ├── frontend-configmap.yaml     # HTML content
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   │
│   └── ingress.yaml               # Path-based routing
│
├── overlays/
│   ├── dev/
│   │   └── kustomization.yaml     # Reduce replicas for dev
│   └── prod/
│       ├── kustomization.yaml     # Production settings
│       └── deployment-patches.yaml # Higher replicas + resources
│
├── cleanup.sh                      # Cleanup script
└── verify.sh                       # Verification script
```

