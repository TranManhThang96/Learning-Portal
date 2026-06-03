# Day 20: Document — RBAC, Pod Security Standards, NetworkPolicy Reference

---

## 1. RBAC Quick Reference

### API Groups & Resources

| API Group | Resources | Ví dụ |
|-----------|-----------|-------|
| `""` (core) | pods, services, configmaps, secrets, namespaces, nodes, endpoints, persistentvolumeclaims, serviceaccounts | `kubectl get pods` |
| `apps` | deployments, replicasets, statefulsets, daemonsets | `kubectl get deployments` |
| `batch` | jobs, cronjobs | `kubectl get jobs` |
| `networking.k8s.io` | ingresses, networkpolicies | `kubectl get ingress` |
| `rbac.authorization.k8s.io` | roles, clusterroles, rolebindings, clusterrolebindings | `kubectl get roles` |
| `autoscaling` | horizontalpodautoscalers | `kubectl get hpa` |
| `policy` | poddisruptionbudgets | `kubectl get pdb` |
| `storage.k8s.io` | storageclasses, csinodes | `kubectl get sc` |

### Verbs Reference

| Verb | HTTP | Ý nghĩa | Ví dụ |
|------|------|---------|-------|
| `get` | GET /resource/name | Đọc 1 resource | `kubectl get pod nginx` |
| `list` | GET /resources | Liệt kê resources | `kubectl get pods` |
| `watch` | GET /resources?watch=true | Watch changes | `kubectl get pods -w` |
| `create` | POST /resources | Tạo mới | `kubectl create deploy` |
| `update` | PUT /resource/name | Update toàn bộ | `kubectl replace` |
| `patch` | PATCH /resource/name | Update một phần | `kubectl patch` |
| `delete` | DELETE /resource/name | Xóa 1 | `kubectl delete pod` |
| `deletecollection` | DELETE /resources | Xóa nhiều | `kubectl delete pods --all` |

### Sub-resources

| Sub-resource | Verb | Ý nghĩa |
|-------------|------|---------|
| `pods/log` | get | Đọc pod logs |
| `pods/exec` | create | Exec vào pod |
| `pods/portforward` | create | Port forward |
| `pods/status` | get, patch | Đọc/update pod status |
| `deployments/scale` | get, patch | Scale deployment |
| `nodes/proxy` | * | Proxy to node |

---

## 2. Common Role/ClusterRole Templates

### Read-only trong Namespace

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: namespace-viewer
rules:
  - apiGroups: ["", "apps", "batch", "networking.k8s.io"]
    resources: ["pods", "services", "deployments", "jobs", "ingresses", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
```

### Namespace Admin (không access secrets)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: namespace-admin
rules:
  - apiGroups: ["", "apps", "batch", "networking.k8s.io", "autoscaling", "policy"]
    resources: ["*"]
    verbs: ["*"]
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]  # read-only secrets
```

### CI/CD ServiceAccount

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cicd-deployer
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "patch", "update"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["services", "configmaps"]
    verbs: ["get", "list", "create", "update", "patch"]
```

### Monitoring Read-only (Cluster-wide)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "endpoints", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - nonResourceURLs: ["/metrics", "/healthz"]
    verbs: ["get"]
```

---

## 3. Pod Security Standards Comparison Matrix

| Control | Privileged | Baseline | Restricted |
|---------|-----------|----------|------------|
| **HostProcess** | Allowed | Not allowed | Not allowed |
| **Host Namespaces** (hostPID, hostIPC, hostNetwork) | Allowed | Not allowed | Not allowed |
| **Privileged Containers** | Allowed | Not allowed | Not allowed |
| **Capabilities** | Allowed | Drop ALL except core set | Must drop ALL |
| **HostPath Volumes** | Allowed | Not allowed | Not allowed |
| **Host Ports** | Allowed | Defined list only | Not allowed |
| **AppArmor** | Any | Not overridden | RuntimeDefault or localhost |
| **SELinux** | Any | Limited | Limited + no custom |
| **/proc Mount Type** | Any | Default Masked | Default Masked |
| **Seccomp** | Any | Any | RuntimeDefault or Localhost |
| **Sysctls** | Any | Defined safe set | Defined safe set |
| **Volumes** | Any | All except hostPath | Limited set |
| **Privilege Escalation** | Allowed | Any | Must be false |
| **Running as Non-root** | Any | Any | Must be non-root |
| **Running as Non-root User** | Any | Any | Must set non-zero runAsUser |
| **Seccomp Profile** | Any | Any | Must set RuntimeDefault or Localhost |

### Compliant Pod Template cho Restricted

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: myapp:1.0
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
        runAsUser: 1000
        readOnlyRootFilesystem: true
```

---

## 4. NetworkPolicy Templates

### Default Deny All (Ingress + Egress)

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

### Allow DNS (Required with egress deny)

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
    - ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

### Allow Same Namespace Only

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-same-namespace
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}
```

### Allow Specific Service Access

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
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

### Allow Cross-namespace

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-monitoring
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
```

### Allow Egress to Specific CIDR

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external-api
spec:
  podSelector:
    matchLabels:
      app: data-fetcher
  policyTypes:
    - Egress
  egress:
    - to:
        - ipBlock:
            cidr: 203.0.113.0/24
      ports:
        - protocol: TCP
          port: 443
```

---

## 5. kubectl Auth Commands Cheat Sheet

```bash
# === Can-I checks ===
# Check as current user
kubectl auth can-i create deployments -n production

# Check as ServiceAccount
kubectl auth can-i get pods \
  --as=system:serviceaccount:<namespace>:<sa-name> \
  -n <target-namespace>

# List all permissions for a SA
kubectl auth can-i --list \
  --as=system:serviceaccount:<namespace>:<sa-name> \
  -n <target-namespace>

# Check as user
kubectl auth can-i get pods --as=jane -n production

# === Role investigation ===
# List roles in namespace
kubectl get roles -n <ns>
kubectl get rolebindings -n <ns>

# Describe role details
kubectl describe role <name> -n <ns>
kubectl describe rolebinding <name> -n <ns>

# Cluster-wide
kubectl get clusterroles
kubectl get clusterrolebindings

# Find who has cluster-admin
kubectl get clusterrolebindings -o json | \
  jq -r '.items[] | select(.roleRef.name=="cluster-admin") | "\(.metadata.name): \(.subjects[].kind)/\(.subjects[].name)"'

# Find all bindings for a specific SA
kubectl get rolebindings,clusterrolebindings -A -o json | \
  jq -r '.items[] | select(.subjects[]? | .name=="<sa-name>") | "\(.metadata.namespace // "cluster")/\(.metadata.name)"'

# === NetworkPolicy investigation ===
kubectl get networkpolicy -n <ns>
kubectl describe networkpolicy <name> -n <ns>

# === Pod Security ===
# Check namespace PSS labels
kubectl get ns <ns> --show-labels | grep pod-security

# Dry-run pod against PSS
kubectl run test --image=nginx:1.25-alpine --dry-run=server -n <restricted-ns>
```

---

## 6. Security Audit Checklist

### RBAC

- [ ] No wildcard (`*`) verbs in production Roles
- [ ] No wildcard (`*`) resources in production Roles
- [ ] Default ServiceAccount has `automountServiceAccountToken: false`
- [ ] Each application has dedicated ServiceAccount
- [ ] No unnecessary ClusterRoleBindings (especially to cluster-admin)
- [ ] CI/CD ServiceAccount has minimal permissions
- [ ] No `pods/exec` permission for non-admin roles
- [ ] No `secrets` write access for non-admin roles
- [ ] Cross-namespace access explicitly documented and justified

### Pod Security

- [ ] Production namespaces enforce at least `baseline`
- [ ] Sensitive namespaces enforce `restricted`
- [ ] No `privileged: true` containers (except system components)
- [ ] Containers run as non-root where possible
- [ ] `allowPrivilegeEscalation: false` set
- [ ] Capabilities dropped: ALL (add back only what's needed)
- [ ] `readOnlyRootFilesystem: true` where possible
- [ ] seccompProfile set to RuntimeDefault

### NetworkPolicy

- [ ] Default deny ingress in all production namespaces
- [ ] Default deny egress in sensitive namespaces
- [ ] DNS egress explicitly allowed
- [ ] Cross-namespace access explicitly allowed and documented
- [ ] No blanket allow-all rules
- [ ] Egress to internet restricted to pods that need it
- [ ] CNI plugin supports NetworkPolicy (NOT flannel/kindnet)

### General

- [ ] Kubernetes API server not publicly exposed
- [ ] Dashboard (if installed) protected with auth
- [ ] RBAC audit log enabled
- [ ] Regular permission review (quarterly)
- [ ] Incident response plan for unauthorized access

