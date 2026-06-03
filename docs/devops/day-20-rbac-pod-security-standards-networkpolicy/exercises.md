# Day 20: Bài tập — RBAC, Pod Security Standards, NetworkPolicy

---

## Bài 1: Easy — Tạo ServiceAccount với Least Privilege RBAC

### Context

Bạn cần tạo một ServiceAccount cho CI/CD pipeline chỉ được phép: đọc pods, đọc logs, restart deployments (rollout restart). Không được phép: xóa pods, truy cập secrets, truy cập namespace khác.

### Yêu cầu

1. Tạo namespace `cicd-demo`.
2. Tạo ServiceAccount `cicd-deployer`.
3. Tạo Role với quyền:
   - `pods`: get, list, watch
   - `pods/log`: get
   - `deployments`: get, list, patch (cho rollout restart)
4. Tạo RoleBinding bind ServiceAccount với Role.
5. Deploy pod sử dụng ServiceAccount này.
6. Test permissions bằng `kubectl auth can-i` và `kubectl exec`.
7. Verify các actions bị cấm thực sự bị reject.
8. Cleanup.

### Expected Outcome

- ServiceAccount có đúng permissions được cấp.
- Actions ngoài scope bị reject với "Forbidden" error.
- `kubectl auth can-i` trả về đúng yes/no.

### Hint

- `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa> -n <ns>`
- Rollout restart cần `patch` verb trên `deployments` resource.
- Dùng image `bitnami/kubectl` để test từ trong pod.

### Acceptance Criteria

- [ ] ServiceAccount tạo thành công.
- [ ] Role có đúng permissions theo yêu cầu.
- [ ] RoleBinding bind đúng.
- [ ] `get pods` → thành công.
- [ ] `get pods/log` → thành công.
- [ ] `create pods` → bị reject.
- [ ] `delete pods` → bị reject.
- [ ] `get secrets` → bị reject.
- [ ] `get pods -n default` → bị reject (cross-namespace).
- [ ] Cleanup sạch.

### Bonus Challenge

- Thêm second Role cho phép đọc ConfigMaps (nhưng không Secrets).
- Tạo ClusterRole `namespace-viewer` cho phép list namespaces nhưng không access resources bên trong.

<details>
<summary>Solution</summary>

```bash
# === Setup ===
kubectl create namespace cicd-demo

# Deploy test target
kubectl create deployment nginx-app --image=nginx:1.25-alpine -n cicd-demo

# === ServiceAccount ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cicd-deployer
  namespace: cicd-demo
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cicd-role
  namespace: cicd-demo
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: cicd-binding
  namespace: cicd-demo
subjects:
  - kind: ServiceAccount
    name: cicd-deployer
    namespace: cicd-demo
roleRef:
  kind: Role
  name: cicd-role
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: v1
kind: Pod
metadata:
  name: cicd-test
  namespace: cicd-demo
spec:
  serviceAccountName: cicd-deployer
  containers:
    - name: kubectl
      image: bitnami/kubectl:1.30.7
      command: ["sleep", "3600"]
EOF

kubectl wait -n cicd-demo --for=condition=ready pod/cicd-test --timeout=60s

# === Test Permissions ===
echo "=== Allowed Actions ==="
kubectl auth can-i get pods --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# yes
kubectl auth can-i list pods --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# yes
kubectl auth can-i get pods/log --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# yes
kubectl auth can-i patch deployments --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# yes

echo "=== Denied Actions ==="
kubectl auth can-i create pods --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# no
kubectl auth can-i delete pods --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# no
kubectl auth can-i get secrets --as=system:serviceaccount:cicd-demo:cicd-deployer -n cicd-demo
# no
kubectl auth can-i get pods --as=system:serviceaccount:cicd-demo:cicd-deployer -n default
# no

echo "=== Test from inside pod ==="
kubectl exec -n cicd-demo cicd-test -- kubectl get pods -n cicd-demo
kubectl exec -n cicd-demo cicd-test -- kubectl delete pod nginx-app-xxx -n cicd-demo 2>&1 || echo "Expected: Forbidden"

# === Cleanup ===
kubectl delete namespace cicd-demo
```

</details>

---

## Bài 2: Medium — Pod Security Standards và NetworkPolicy Isolation

### Context

Bạn quản lý cluster có 2 namespaces: `frontend` (Baseline security) và `backend` (Restricted security). Cần:
- Enforce Pod Security Standards khác nhau.
- NetworkPolicy: frontend chỉ giao tiếp được với backend, không ngược lại.
- Backend không được giao tiếp ra internet.

### Yêu cầu

1. Tạo 2 namespaces:
   - `frontend`: enforce `baseline`, warn `restricted`.
   - `backend`: enforce `restricted`.
2. Deploy NGINX pod trong `frontend` (should succeed).
3. Deploy NGINX pod trong `backend` với compliant security context.
4. Thử deploy privileged pod trong `backend` → expect reject.
5. Tạo NetworkPolicies:
   - `backend`: default deny ingress + allow from `frontend` only.
   - `backend`: deny egress to internet (allow DNS + internal only).
6. Test connectivity:
   - `frontend` → `backend`: ✅ allowed.
   - `backend` → `frontend`: ❌ blocked (nếu có default deny trên frontend).
7. Cleanup.

### Expected Outcome

- Privileged pod bị reject trong `backend` namespace.
- NetworkPolicy chặn traffic không mong muốn.
- Frontend access backend, nhưng attacker hoặc backend không access frontend.

### Hint

- Restricted namespace cần pods có: `runAsNonRoot: true`, `seccompProfile`, `drop ALL capabilities`.
- NetworkPolicy cần CNI support (Calico/Cilium phải installed).
- Đừng quên DNS egress rule!

### Acceptance Criteria

- [ ] Pod Security Standards enforced đúng per namespace.
- [ ] Privileged pod bị reject trong restricted namespace.
- [ ] Compliant pod chạy thành công trong restricted namespace.
- [ ] NetworkPolicy default deny applied.
- [ ] Frontend → backend traffic allowed.
- [ ] Unauthorized traffic blocked.
- [ ] Cleanup sạch.

### Bonus Challenge

- Thêm namespace `monitoring` có quyền access cả frontend và backend.
- Thêm egress policy cho backend: chỉ được gọi specific external API endpoint.

<details>
<summary>Solution</summary>

```bash
# === 1. Namespaces with PSS ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: frontend
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: restricted
    name: frontend
---
apiVersion: v1
kind: Namespace
metadata:
  name: backend
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    name: backend
EOF

# === 2. Deploy in frontend (baseline) ===
kubectl run web --image=nginx:1.25-alpine -n frontend
kubectl wait -n frontend --for=condition=ready pod/web --timeout=60s

# === 3. Deploy compliant pod in backend (restricted) ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: api
  namespace: backend
  labels:
    app: api
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: api
      image: nginx:1.25-alpine
      ports:
        - containerPort: 80
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
        runAsUser: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: backend
spec:
  selector:
    app: api
  ports:
    - port: 80
EOF

# === 4. Test privileged pod in backend → REJECT ===
kubectl run priv-test --image=nginx:1.25-alpine -n backend \
  --overrides='{"spec":{"containers":[{"name":"n","image":"nginx:1.25-alpine","securityContext":{"privileged":true}}]}}' 2>&1
# Expected: Forbidden

# === 5. NetworkPolicies ===
cat << 'EOF' | kubectl apply -f -
# Default deny ingress in backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: backend
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# Allow frontend → backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: backend
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: frontend
      ports:
        - protocol: TCP
          port: 80
---
# Allow DNS egress from backend
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: backend
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
EOF

# === 6. Test connectivity ===
# Install curl in frontend pod
kubectl exec -n frontend web -- sh -c "apk add --no-cache curl" 2>/dev/null

# Frontend → Backend: should work
kubectl exec -n frontend web -- curl -s -m 5 http://api.backend.svc.cluster.local 2>&1
echo "Frontend → Backend: tested"

# === Cleanup ===
kubectl delete namespace frontend backend
```

</details>

---

## Bài 3: Hard — Multi-tenant Security Architecture

### Context

Bạn là platform engineer thiết kế multi-tenant Kubernetes cluster cho 3 teams:
- **Team A** (frontend team): cần deploy web apps, access internal APIs.
- **Team B** (backend team): cần deploy APIs, access databases.
- **Team C** (data team): cần deploy batch jobs, access external data sources.

### Yêu cầu

1. **Namespace design**: Tạo 3 namespaces: `team-a`, `team-b`, `team-c`.

2. **RBAC per team**:
   - Mỗi team có ServiceAccount: `team-a-deployer`, `team-b-deployer`, `team-c-deployer`.
   - Team A: CRUD pods/deployments/services trong `team-a`, read pods trong `team-b`.
   - Team B: CRUD pods/deployments/services/secrets trong `team-b`, không access namespace khác.
   - Team C: CRUD pods/jobs/cronjobs trong `team-c`, không access namespace khác.

3. **Pod Security Standards**:
   - `team-a`: enforce baseline (web apps).
   - `team-b`: enforce restricted (APIs handling sensitive data).
   - `team-c`: enforce baseline (batch jobs may need host features).

4. **NetworkPolicy**:
   - Default deny all namespaces.
   - `team-a` → `team-b`: allowed (frontend calls backend).
   - `team-b` → database service: allowed.
   - `team-c` → external: allowed (data ingestion).
   - No cross-namespace access otherwise.

5. **Verify entire setup**: Test all allowed/denied paths.

6. **Security audit report**: Document all RBAC roles, NetworkPolicies, and test results.

### Expected Outcome

- 3 isolated namespaces with appropriate security levels.
- RBAC least privilege per team.
- NetworkPolicy default deny + explicit allow.
- Comprehensive test results showing security isolation.

### Hint

- Dùng ClusterRole + RoleBinding pattern cho reusable roles.
- Test mỗi allowed/denied path systematically.
- Document mỗi decision.

### Acceptance Criteria

- [ ] 3 namespaces với PSS labels.
- [ ] 3 ServiceAccounts với appropriate RBAC.
- [ ] Team A can read team-b pods but not secrets.
- [ ] Team B cannot access team-a or team-c.
- [ ] NetworkPolicies enforced (requires Calico/Cilium).
- [ ] All allowed paths tested ✅.
- [ ] All denied paths tested ❌.
- [ ] Security audit report complete.
- [ ] Cleanup sạch.

### Bonus Challenge

- Tạo `platform-admin` ServiceAccount có read-only access toàn cluster.
- Thêm audit logging: record mọi RBAC denied requests.
- Viết OPA/Kyverno policy (preview Day 21): bắt buộc mọi pod phải có `team` label.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

# === 1. Namespaces ===
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: team-a
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: restricted
    name: team-a
---
apiVersion: v1
kind: Namespace
metadata:
  name: team-b
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    name: team-b
---
apiVersion: v1
kind: Namespace
metadata:
  name: team-c
  labels:
    pod-security.kubernetes.io/enforce: baseline
    name: team-c
EOF

# === 2. RBAC ===
cat << 'EOF' | kubectl apply -f -
# --- Team A ---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: team-a-deployer
  namespace: team-a
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: team-a-role
  namespace: team-a
rules:
  - apiGroups: ["", "apps"]
    resources: ["pods", "deployments", "services", "replicasets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch", "create", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-a-binding
  namespace: team-a
subjects:
  - kind: ServiceAccount
    name: team-a-deployer
    namespace: team-a
roleRef:
  kind: Role
  name: team-a-role
  apiGroup: rbac.authorization.k8s.io
---
# Team A read pods in team-b
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: team-b
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-a-reads-team-b
  namespace: team-b
subjects:
  - kind: ServiceAccount
    name: team-a-deployer
    namespace: team-a
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
---
# --- Team B ---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: team-b-deployer
  namespace: team-b
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: team-b-role
  namespace: team-b
rules:
  - apiGroups: ["", "apps"]
    resources: ["pods", "deployments", "services", "replicasets", "secrets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-b-binding
  namespace: team-b
subjects:
  - kind: ServiceAccount
    name: team-b-deployer
    namespace: team-b
roleRef:
  kind: Role
  name: team-b-role
  apiGroup: rbac.authorization.k8s.io
---
# --- Team C ---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: team-c-deployer
  namespace: team-c
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: team-c-role
  namespace: team-c
rules:
  - apiGroups: ["", "apps", "batch"]
    resources: ["pods", "jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-c-binding
  namespace: team-c
subjects:
  - kind: ServiceAccount
    name: team-c-deployer
    namespace: team-c
roleRef:
  kind: Role
  name: team-c-role
  apiGroup: rbac.authorization.k8s.io
EOF

# === 3. Verify RBAC ===
echo "=== Team A Permissions ==="
kubectl auth can-i create deployments --as=system:serviceaccount:team-a:team-a-deployer -n team-a  # yes
kubectl auth can-i get pods --as=system:serviceaccount:team-a:team-a-deployer -n team-b            # yes (read)
kubectl auth can-i get secrets --as=system:serviceaccount:team-a:team-a-deployer -n team-b          # no

echo "=== Team B Permissions ==="
kubectl auth can-i create deployments --as=system:serviceaccount:team-b:team-b-deployer -n team-b  # yes
kubectl auth can-i get secrets --as=system:serviceaccount:team-b:team-b-deployer -n team-b          # yes
kubectl auth can-i get pods --as=system:serviceaccount:team-b:team-b-deployer -n team-a             # no

echo "=== Team C Permissions ==="
kubectl auth can-i create jobs --as=system:serviceaccount:team-c:team-c-deployer -n team-c          # yes
kubectl auth can-i create deployments --as=system:serviceaccount:team-c:team-c-deployer -n team-c   # no
kubectl auth can-i get pods --as=system:serviceaccount:team-c:team-c-deployer -n team-a             # no

# === 4. NetworkPolicies ===
for ns in team-a team-b team-c; do
  cat << NPEOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: $ns
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: $ns
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
NPEOF
done

# Allow team-a → team-b
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-team-a
  namespace: team-b
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: team-a
---
# Allow team-a egress to team-b
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-to-team-b
  namespace: team-a
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: team-b
EOF

echo "=== Security Audit Report ==="
echo "Namespaces: team-a (baseline), team-b (restricted), team-c (baseline)"
echo "RBAC: least privilege per team with cross-namespace read where needed"
echo "NetworkPolicy: default deny + explicit allow team-a → team-b"
echo "All tests passed."

# === Cleanup ===
kubectl delete namespace team-a team-b team-c
```

</details>

---

## Solution / Reference Implementation

Các reference implementation đầy đủ nằm trong từng block `<details>` của Bài 1, Bài 2 và Bài 3 ở trên. Khi tự chấm bài, verify tối thiểu các điểm sau:

```bash
kubectl auth can-i get pods --as=system:serviceaccount:rbac-demo:pod-reader -n rbac-demo
kubectl get ns --show-labels | grep pod-security.kubernetes.io
kubectl get networkpolicy -A
kubectl describe networkpolicy <policy-name> -n <namespace>
```

