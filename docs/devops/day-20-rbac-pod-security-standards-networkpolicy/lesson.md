# Day 20: RBAC, Pod Security Standards & NetworkPolicy

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Thiết kế được** RBAC policies theo nguyên tắc least privilege: ServiceAccount → Role → RoleBinding.
2. **Cấu hình được** Pod Security Standards (Privileged/Baseline/Restricted) cho namespace.
3. **Tạo được** NetworkPolicy để isolate traffic giữa các services và namespaces.
4. **Verify được** permissions bằng `kubectl auth can-i` và test network isolation.
5. **Phân tích được** security risks khi không có RBAC/NetworkPolicy trong production.

---

## 2. Bối cảnh & Động lực

### Vì sao security trong Kubernetes quan trọng?

Kubernetes mặc định **mở**: mọi pod có thể giao tiếp với mọi pod khác, default ServiceAccount có quyền truy cập API server. Đây là thiết kế thuận tiện cho development nhưng **nguy hiểm cho production**.

### Production incidents thực tế

| Incident | Nguyên nhân | Hậu quả |
|----------|------------|---------|
| **Tesla cryptojacking (2018)** | Kubernetes dashboard exposed, không auth | Attacker deploy crypto miner trên cluster |
| **Capital One breach (2019)** | Over-privileged IAM role, SSRF exploit | 100M+ customer records leaked |
| **Lateral movement attacks** | Không có NetworkPolicy, mọi pod giao tiếp tự do | Compromise 1 pod → access toàn bộ cluster |

### Defense in Depth

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Network Security (NetworkPolicy)        │
│  ├── Chặn traffic không mong muốn                │
│  └── Default deny → explicit allow               │
│                                                   │
│ Layer 2: Pod Security (Pod Security Standards)    │
│  ├── Cấm privileged containers                   │
│  └── Enforce security context                     │
│                                                   │
│ Layer 3: API Access (RBAC)                        │
│  ├── Least privilege cho ServiceAccounts          │
│  └── Restrict who can do what                     │
│                                                   │
│ Layer 4: Admission Control (Day 21)              │
│  └── Policy enforcement trước khi resources tạo   │
└─────────────────────────────────────────────────┘
```

### Liên hệ với developer

- **RBAC** giống IAM roles trong AWS/GCP — ai được làm gì trên resource nào.
- **NetworkPolicy** giống firewall rules — traffic nào được đi đâu.
- **Pod Security Standards** giống security profiles — app chạy với quyền gì.

---

## 3. Kiến thức nền tảng

### 3.1 Kubernetes Security Model

```
User/ServiceAccount
       │
       ▼
┌──────────────┐
│Authentication │ ← "Bạn là ai?" (certificates, tokens, OIDC)
└──────┬───────┘
       ▼
┌──────────────┐
│Authorization  │ ← "Bạn được làm gì?" (RBAC)
└──────┬───────┘
       ▼
┌──────────────┐
│Admission     │ ← "Request có hợp lệ không?" (Pod Security, OPA)
│Control       │
└──────┬───────┘
       ▼
   API Server
   executes request
```

### 3.2 Authentication vs Authorization

| Concept | Mô tả | Kubernetes mechanism |
|---------|--------|---------------------|
| **Authentication** (AuthN) | Xác định identity | X.509 certs, ServiceAccount tokens, OIDC |
| **Authorization** (AuthZ) | Xác định permissions | RBAC (Role-Based Access Control) |

---

## 4. Deep Dive

### 4.1 RBAC — Role-Based Access Control

#### Core Components

```
┌─────────────────┐         ┌──────────────┐         ┌──────────────┐
│ ServiceAccount   │◄───────│ RoleBinding   │────────▶│    Role       │
│ (WHO)            │   binds │ (GLUE)       │ references│ (WHAT)      │
│                  │         │              │          │              │
│ sa: deployer     │         │ Bind deployer│          │ Verbs: get,  │
│ ns: production   │         │ to pod-reader│          │   list, watch│
└─────────────────┘         └──────────────┘          │ Resources:   │
                                                      │   pods       │
                                                      │ Namespace:   │
                                                      │   production │
                                                      └──────────────┘
```

#### Namespace-scoped vs Cluster-scoped

| | Namespace-scoped | Cluster-scoped |
|--|-----------------|----------------|
| **Role** | Role | ClusterRole |
| **Binding** | RoleBinding | ClusterRoleBinding |
| **Scope** | Single namespace | Toàn cluster |
| **Use case** | Team permissions per ns | Cluster-wide admin, nodes, CRDs |

#### RBAC Verbs

| Verb | HTTP Method | Mô tả |
|------|-------------|--------|
| `get` | GET (single) | Đọc 1 resource |
| `list` | GET (collection) | Liệt kê resources |
| `watch` | GET (streaming) | Watch changes |
| `create` | POST | Tạo mới |
| `update` | PUT | Cập nhật toàn bộ |
| `patch` | PATCH | Cập nhật một phần |
| `delete` | DELETE | Xóa |
| `deletecollection` | DELETE (collection) | Xóa nhiều |

#### Role Example

```yaml
# Role: chỉ đọc pods trong namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
  - apiGroups: [""]           # core API group
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]    # sub-resource
    verbs: ["get"]
```

```yaml
# ClusterRole: đọc pods trên toàn cluster
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cluster-pod-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "endpoints"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

#### Binding Examples

```yaml
# RoleBinding: bind ServiceAccount to Role
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deployer-pod-reader
  namespace: production
subjects:
  - kind: ServiceAccount
    name: deployer
    namespace: production
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

```yaml
# ClusterRoleBinding: bind to ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: monitoring-reader
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: monitoring
roleRef:
  kind: ClusterRole
  name: cluster-pod-reader
  apiGroup: rbac.authorization.k8s.io
```

### 4.2 Pod Security Standards

Pod Security Standards thay thế PodSecurityPolicy (PSP, removed K8s 1.25+).

#### 3 Levels

```
┌───────────────────────────────────────────────────────┐
│                 Pod Security Standards                  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Privileged    │  │ Baseline     │  │ Restricted   │ │
│  │              │  │              │  │              │ │
│  │ No           │  │ Ngăn known   │  │ Best         │ │
│  │ restrictions │  │ privilege    │  │ practices    │ │
│  │              │  │ escalations  │  │ hardening    │ │
│  │ Use: system  │  │ Use: hầu hết │  │ Use: high    │ │
│  │ components   │  │ workloads    │  │ security     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  Restrictiveness: ─────────────────────────────────▶    │
│                   Low            Medium         High     │
└─────────────────────────────────────────────────────────┘
```

| Level | Cho phép | Cấm | Use case |
|-------|---------|-----|----------|
| **Privileged** | Mọi thứ | Không cấm gì | System components (CNI, CSI, monitoring agents) |
| **Baseline** | Hầu hết workloads | privileged containers, hostNetwork, hostPID, hostIPC | Default cho production workloads |
| **Restricted** | Chỉ hardened workloads | + runAsNonRoot required, drop ALL capabilities, seccomp required | High-security environments |

#### Enforcement Modes

```yaml
# Apply Pod Security Standards qua namespace labels
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Mode: enforce (reject), audit (log), warn (warning)
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

- **enforce**: Reject pods không meet standard.
- **audit**: Log violations, không reject.
- **warn**: Hiện warning cho user, không reject.

Best practice: enforce `baseline`, audit + warn `restricted`.

### 4.3 NetworkPolicy

#### Default Behavior

**Mặc định: KHÔNG có NetworkPolicy = ALLOW ALL**

Mọi pod có thể giao tiếp với mọi pod khác trong cluster, bất kể namespace.

```
Không có NetworkPolicy:

Pod A ──────▶ Pod B    ✅ Allowed
  │
  ├────────▶ Pod C    ✅ Allowed
  │
  └────────▶ Pod D    ✅ Allowed (khác namespace cũng OK)
```

#### Default Deny Pattern

```yaml
# Deny all ingress traffic to pods in namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}          # Apply to ALL pods
  policyTypes:
    - Ingress              # Block ALL incoming traffic
---
# Deny all egress traffic from pods in namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
```

#### Allow Specific Traffic

```yaml
# Allow frontend → api-gateway on port 8080
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-api
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api-gateway         # Target: api-gateway pods
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend    # Source: frontend pods
      ports:
        - protocol: TCP
          port: 8080
```

```yaml
# Allow api-gateway → book-service (cross-namespace)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-to-books
  namespace: backend
spec:
  podSelector:
    matchLabels:
      app: book-service
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: frontend-ns
          podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - protocol: TCP
          port: 80
```

#### Allow DNS (quan trọng — quên cái này sẽ break mọi thứ)

```yaml
# Allow DNS resolution (kube-dns/CoreDNS)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

#### CNI Requirement

> **Quan trọng**: NetworkPolicy chỉ hoạt động khi CNI plugin hỗ trợ. Flannel KHÔNG hỗ trợ. Cần: **Calico**, **Cilium**, **Weave Net**, hoặc **Antrea**.

```bash
# Kiểm tra CNI
kubectl get pods -n kube-system | grep -E "(calico|cilium|weave)"

# Kind mặc định dùng kindnet (KHÔNG hỗ trợ NetworkPolicy)
# Cần install Calico cho kind:
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml
```

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 RBAC

| Approach | Ưu điểm | Nhược điểm | Khi nào dùng |
|--------|---------|------------|-------------|
| **Granular roles** (1 role per resource) | Least privilege chính xác | Quản lý phức tạp, nhiều roles | Multi-tenant, compliance |
| **Aggregated roles** (combined) | Đơn giản quản lý | Có thể over-privilege | Small-medium teams |
| **ClusterRole + RoleBinding** | Reuse role definition | ClusterRole visible cluster-wide | Pattern chuẩn |
| **Namespace admin** | Team autonomy | Risk nếu không giới hạn | Platform team model |

### 5.2 NetworkPolicy

| Strategy | Security Level | Complexity | Recommendation |
|----------|---------------|------------|----------------|
| **No NetworkPolicy** | Rất thấp | Không | Chỉ dev/test |
| **Default deny + allow specific** | Cao | Trung bình | **Production recommended** |
| **Namespace isolation** | Trung bình | Thấp | Multi-tenant minimum |
| **Zero-trust (per-pod)** | Rất cao | Cao | Financial, healthcare |

### 5.3 Anti-patterns

| Anti-pattern | Risk | Fix |
|-------------|------|-----|
| `*` wildcard verbs/resources | Over-privilege, lateral movement | Explicit verbs và resources |
| Default ServiceAccount used by apps | Shared permissions | Tạo dedicated SA per app |
| No NetworkPolicy | Unrestricted lateral movement | Default deny + explicit allow |
| `privileged: true` không cần thiết | Container escape risk | Baseline Pod Security Standard |
| ClusterRoleBinding cho team users | Cluster-wide access | RoleBinding per namespace |
| Forget DNS egress rule | Pods can't resolve services | Always allow DNS egress |

---

## 6. Performance & Scalability ⭐

### 6.1 RBAC

- RBAC evaluation adds **< 1ms** per API request — negligible.
- **At scale** (1000+ roles): compile rules into in-memory cache → minimal impact.
- **Watch**: quá nhiều RoleBindings trong cluster có thể tăng etcd load.

### 6.2 NetworkPolicy

| CNI | Performance Impact | Notes |
|-----|--------------------|-------|
| **Calico** (iptables) | ~5-10% latency tăng | Mature, well-tested |
| **Calico** (eBPF) | < 2% latency tăng | Better performance |
| **Cilium** (eBPF) | < 2% latency tăng | Best performance at scale |
| **Many rules** | Tăng theo số rules | Tối ưu: tổng hợp rules |

- Mỗi NetworkPolicy thêm iptables rules → nhiều policies = nhiều rules → potential performance impact.
- **Best practice**: Dùng label selectors rộng thay vì pod-specific rules.

---

## 7. Security & Reliability Considerations

### 7.1 Default ServiceAccount Dangers

```yaml
# Mỗi namespace có default ServiceAccount
# Mặc định: KHÔNG có RBAC permissions (K8s 1.24+)
# NHƯNG: token vẫn mount vào mọi pod → attacker có thể dùng

# Fix: Disable auto-mount cho default SA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: default
  namespace: production
automountServiceAccountToken: false
```

### 7.2 Privilege Escalation Risks

```yaml
# NGUY HIỂM: cho phép tạo RoleBindings
rules:
  - apiGroups: ["rbac.authorization.k8s.io"]
    resources: ["rolebindings"]
    verbs: ["create"]  # Người dùng tự bind mình vào admin role!

# NGUY HIỂM: cho phép exec vào pods
rules:
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"]  # Exec vào pod = access secrets, network

# NGUY HIỂM: cho phép đọc secrets cluster-wide
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list"]  # Đọc tất cả credentials
```

### 7.3 Lateral Movement Prevention

```
Attacker compromise Pod A:

Không có NetworkPolicy:
  Pod A → Pod B → Pod C → Database → Exfiltrate data

Có NetworkPolicy (default deny):
  Pod A → ❌ Blocked (chỉ được giao tiếp Service X)
  Pod A → Service X → ✅ Allowed (explicit rule)
  Pod A → Database → ❌ Blocked
  Pod A → Internet → ❌ Blocked (egress deny)
```

---

## 8. Hands-on Example

### Prerequisites

```bash
# Kind cluster
kind get clusters || kind create cluster --name devops-lab

# Install Calico cho NetworkPolicy support trên kind
# (kind mặc định dùng kindnet, KHÔNG hỗ trợ NetworkPolicy)
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/calico.yaml
kubectl wait --namespace kube-system --for=condition=ready pod -l k8s-app=calico-node --timeout=120s
```

### 8.1 RBAC — Tạo Restricted ServiceAccount

```yaml
# rbac-demo.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rbac-demo
---
# ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pod-reader-sa
  namespace: rbac-demo
---
# Role: chỉ đọc pods
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: rbac-demo
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
---
# RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader-binding
  namespace: rbac-demo
subjects:
  - kind: ServiceAccount
    name: pod-reader-sa
    namespace: rbac-demo
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
---
# Test pod sử dụng ServiceAccount
apiVersion: v1
kind: Pod
metadata:
  name: test-rbac
  namespace: rbac-demo
spec:
  serviceAccountName: pod-reader-sa
  containers:
    - name: kubectl
      image: bitnami/kubectl:1.30.7
      command: ["sleep", "3600"]
```

```bash
# Apply
kubectl apply -f rbac-demo.yaml
kubectl wait --namespace rbac-demo --for=condition=ready pod/test-rbac --timeout=60s

# Tạo một pod để test
kubectl run nginx-test --image=nginx:1.25-alpine -n rbac-demo

# Test permissions từ trong pod
# ✅ Should succeed: list pods
kubectl exec -n rbac-demo test-rbac -- kubectl get pods -n rbac-demo
# Expected: NAME        READY   STATUS    ...

# ✅ Should succeed: get pod logs
kubectl exec -n rbac-demo test-rbac -- kubectl logs nginx-test -n rbac-demo

# ❌ Should fail: create pod
kubectl exec -n rbac-demo test-rbac -- kubectl run test --image=nginx:1.25-alpine -n rbac-demo 2>&1
# Expected: Error from server (Forbidden): ...

# ❌ Should fail: delete pod
kubectl exec -n rbac-demo test-rbac -- kubectl delete pod nginx-test -n rbac-demo 2>&1
# Expected: Error from server (Forbidden): ...

# ❌ Should fail: access secrets
kubectl exec -n rbac-demo test-rbac -- kubectl get secrets -n rbac-demo 2>&1
# Expected: Error from server (Forbidden): ...

# ❌ Should fail: access other namespace
kubectl exec -n rbac-demo test-rbac -- kubectl get pods -n default 2>&1
# Expected: Error from server (Forbidden): ...

# Verify bằng kubectl auth can-i
kubectl auth can-i get pods --as=system:serviceaccount:rbac-demo:pod-reader-sa -n rbac-demo
# yes
kubectl auth can-i create pods --as=system:serviceaccount:rbac-demo:pod-reader-sa -n rbac-demo
# no
kubectl auth can-i delete pods --as=system:serviceaccount:rbac-demo:pod-reader-sa -n rbac-demo
# no
kubectl auth can-i get secrets --as=system:serviceaccount:rbac-demo:pod-reader-sa -n rbac-demo
# no
```

### 8.2 Pod Security Standards

```yaml
# pss-demo.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pss-restricted
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: pss-baseline
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
```

```bash
# Apply
kubectl apply -f pss-demo.yaml

# Test: deploy privileged pod → REJECT in restricted namespace
kubectl run privileged-test --image=nginx:1.25-alpine -n pss-restricted \
  --overrides='{"spec":{"containers":[{"name":"nginx","image":"nginx:1.25-alpine","securityContext":{"privileged":true}}]}}' 2>&1
# Expected: Error - violates PodSecurity "restricted:latest"

# Test: deploy normal pod → REJECT (needs runAsNonRoot, seccompProfile, etc.)
kubectl run normal-test --image=nginx:1.25-alpine -n pss-restricted 2>&1
# Expected: Warning or Error about restricted requirements

# Test: compliant pod in restricted namespace
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: restricted-pod
  namespace: pss-restricted
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: nginx:1.25-alpine
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
        runAsUser: 1000
EOF
# Expected: pod/restricted-pod created

# Test: same pod in baseline namespace → OK
kubectl run baseline-test --image=nginx:1.25-alpine -n pss-baseline
# Expected: pod/baseline-test created (baseline is less strict)
```

### 8.3 NetworkPolicy

```yaml
# netpol-demo.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: netpol-demo
---
# Backend pod
apiVersion: v1
kind: Pod
metadata:
  name: backend
  namespace: netpol-demo
  labels:
    app: backend
    role: api
spec:
  containers:
    - name: nginx
      image: nginx:1.25-alpine
      ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: netpol-demo
spec:
  selector:
    app: backend
  ports:
    - port: 80
---
# Frontend pod
apiVersion: v1
kind: Pod
metadata:
  name: frontend
  namespace: netpol-demo
  labels:
    app: frontend
    role: web
spec:
  containers:
    - name: curl
      image: curlimages/curl:8.10.1
      command: ["sleep", "3600"]
---
# Attacker pod (simulated)
apiVersion: v1
kind: Pod
metadata:
  name: attacker
  namespace: netpol-demo
  labels:
    app: attacker
    role: malicious
spec:
  containers:
    - name: curl
      image: curlimages/curl:8.10.1
      command: ["sleep", "3600"]
```

```bash
# Apply
kubectl apply -f netpol-demo.yaml
kubectl wait --namespace netpol-demo --for=condition=ready pod --all --timeout=60s

# Test: TRƯỚC NetworkPolicy — mọi pod giao tiếp tự do
echo "=== Before NetworkPolicy ==="
kubectl exec -n netpol-demo frontend -- curl -s -m 3 http://backend
# Expected: NGINX welcome page ✅

kubectl exec -n netpol-demo attacker -- curl -s -m 3 http://backend
# Expected: NGINX welcome page ✅ (attacker cũng access được!)

# Apply Default Deny
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: netpol-demo
spec:
  podSelector: {}
  policyTypes:
    - Ingress
EOF

# Test: SAU Default Deny — tất cả bị chặn
echo "=== After Default Deny ==="
kubectl exec -n netpol-demo frontend -- curl -s -m 3 http://backend 2>&1
# Expected: Timeout ❌

kubectl exec -n netpol-demo attacker -- curl -s -m 3 http://backend 2>&1
# Expected: Timeout ❌

# Allow chỉ frontend → backend
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: netpol-demo
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 80
EOF

# Test: SAU Allow Rule
echo "=== After Allow Frontend ==="
kubectl exec -n netpol-demo frontend -- curl -s -m 3 http://backend
# Expected: NGINX welcome page ✅ (frontend allowed)

kubectl exec -n netpol-demo attacker -- curl -s -m 3 http://backend 2>&1
# Expected: Timeout ❌ (attacker still blocked!)

echo "✅ Security: frontend can access backend, attacker cannot"
```

### Cleanup toàn bộ

```bash
kubectl delete namespace rbac-demo pss-restricted pss-baseline netpol-demo --ignore-not-found
rm -f rbac-demo.yaml pss-demo.yaml netpol-demo.yaml
```

---

## 9. Common Pitfalls & Debugging

### 9.1 RBAC Pitfalls

| Pitfall | Triệu chứng | Fix |
|---------|-------------|-----|
| Wildcard `*` permissions | Over-privilege, security audit fail | Explicit verbs/resources |
| Forgot `apiGroups` | Role doesn't match | Check: `""` = core, `"apps"`, `"rbac.authorization.k8s.io"` |
| SA token auto-mount | Every pod has API access | `automountServiceAccountToken: false` on default SA |
| RoleBinding wrong namespace | Permissions don't work | roleRef.namespace must match Role namespace |

```bash
# Debug RBAC
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa> -n <ns>
kubectl auth can-i get pods --as=system:serviceaccount:<ns>:<sa> -n <ns>

# Xem role details
kubectl describe role <name> -n <ns>
kubectl describe rolebinding <name> -n <ns>

# Xem ai có quyền cluster-admin
kubectl get clusterrolebindings -o json | jq -r '.items[] | select(.roleRef.name=="cluster-admin") | .subjects[].name'
```

### 9.2 NetworkPolicy Pitfalls

| Pitfall | Triệu chứng | Fix |
|---------|-------------|-----|
| CNI doesn't support NetworkPolicy | Policies applied but not enforced | Install Calico/Cilium |
| Forgot DNS egress rule | Pods can't resolve any service names | Add DNS egress allow rule |
| Wrong label selector | Policy not applied to intended pods | Double-check labels |
| Egress deny without allow | Pods can't reach external APIs | Add egress allow rules |

```bash
# Debug NetworkPolicy
kubectl get networkpolicy -n <ns>
kubectl describe networkpolicy <name> -n <ns>

# Verify CNI supports NetworkPolicy
kubectl get pods -n kube-system | grep -E "(calico|cilium)"

# Test connectivity
kubectl exec <pod> -n <ns> -- curl -v -m 5 http://<service>:<port>
kubectl exec <pod> -n <ns> -- nslookup <service>
```

### 9.3 Production Case Study: Lateral Movement via Default ServiceAccount

#### Context
SaaS platform, 100+ microservices trên K8s, no RBAC hardening.

#### Symptom
Alert: unusual API calls FROM pod in `staging` namespace TO `production` secrets.

#### Investigation
```bash
# Kiểm tra pod
kubectl get pod suspect-pod -n staging -o jsonpath='{.spec.serviceAccountName}'
# "default" ← dùng default SA

# Kiểm tra default SA permissions
kubectl auth can-i --list --as=system:serviceaccount:staging:default -n production
# get secrets → yes! (cluster-wide ClusterRoleBinding)
```

#### Root Cause
Một ClusterRoleBinding gán `view` ClusterRole cho toàn bộ `system:serviceaccounts` group → mọi SA ở mọi namespace đều đọc được secrets cluster-wide.

#### Fix
```bash
# Xóa over-privileged ClusterRoleBinding
kubectl delete clusterrolebinding overly-permissive-view

# Tạo specific RoleBindings per namespace
kubectl create rolebinding staging-view \
  --clusterrole=view \
  --serviceaccount=staging:default \
  -n staging

# Disable auto-mount trên default SA
kubectl patch serviceaccount default -n staging \
  -p '{"automountServiceAccountToken": false}'
```

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Áp dụng |
|-----|---------|
| Day 12 (Networking) | NetworkPolicy dựa trên Service networking model |
| Day 14 (Secrets) | RBAC restrict secret access |
| Day 17 (Mini-project) | Apply RBAC/NetworkPolicy cho BookStore stack |
| Day 18 (Resources) | ResourceQuota + RBAC = namespace resource isolation |

### Bài sau sẽ mở rộng

- **Day 21 (Admission Controllers)**: OPA/Gatekeeper/Kyverno enforce policies tự động — bắt buộc labels, cấm privileged pods.
- **Day 24 (Production Checklist)**: Security checklist bao gồm RBAC, NetworkPolicy, Pod Security.
- **Day 25 (Mini-project)**: Harden BookStore stack với RBAC + NetworkPolicy.
- **Day 45 (DevSecOps)**: Security scanning, SAST, DAST trong CI/CD.

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes RBAC Documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) — Official RBAC guide.
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — Official PSS reference.
- [NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — Official NetworkPolicy guide.

### Nice-to-have

- [NetworkPolicy Editor (Cilium)](https://editor.networkpolicy.io/) — Visual NetworkPolicy editor.
- [RBAC Lookup tool](https://github.com/FairwindsOps/rbac-lookup) — Command-line RBAC investigation.
- [KubeAudit](https://github.com/Shopify/kubeaudit) — Automated K8s security auditing.

### Deep-dive

- [Kubernetes Security Best Practices (CIS Benchmark)](https://www.cisecurity.org/benchmark/kubernetes) — Industry standard security benchmark.
- [Hacking Kubernetes (O'Reilly)](https://www.oreilly.com/library/view/hacking-kubernetes/9781492081722/) — Attack và defense patterns.
- [NSA Kubernetes Hardening Guide](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF) — Government security guidance.

