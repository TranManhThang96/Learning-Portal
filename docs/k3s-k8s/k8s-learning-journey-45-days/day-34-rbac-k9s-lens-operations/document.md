# Document - Day 34: RBAC, k9s và Lens Reference

## RBAC object map

```text
User / Group / ServiceAccount
          |
          v
RoleBinding / ClusterRoleBinding
          |
          v
Role / ClusterRole
          |
          v
apiGroups + resources + verbs
```

## Object scope

| Object | Scope | Notes |
|---|---|---|
| `Role` | Namespace | Rules apply to namespaced resources in one namespace |
| `ClusterRole` | Cluster | Can describe cluster-scoped or reusable namespaced rules |
| `RoleBinding` | Namespace | Grants a Role or ClusterRole within one namespace |
| `ClusterRoleBinding` | Cluster | Grants a ClusterRole cluster-wide |
| `ServiceAccount` | Namespace | Identity for Pods/automation |

## Common resources and API groups

| Resource | API group | Example RBAC resource |
|---|---|---|
| Pods | core `""` | `pods` |
| Pod logs | core `""` | `pods/log` |
| Pod exec | core `""` | `pods/exec` |
| Services | core `""` | `services` |
| ConfigMaps | core `""` | `configmaps` |
| Secrets | core `""` | `secrets` |
| Events (legacy) | core `""` | `events` |
| Events | `events.k8s.io` | `events` |
| Deployments | `apps` | `deployments` |
| StatefulSets | `apps` | `statefulsets` |
| Jobs | `batch` | `jobs` |
| Ingress | `networking.k8s.io` | `ingresses` |
| NetworkPolicy | `networking.k8s.io` | `networkpolicies` |
| HPA | `autoscaling` | `horizontalpodautoscalers` |
| Nodes | core `""` | `nodes` |
| Namespaces | core `""` | `namespaces` |

## Verb reference

| Verb | Common command |
|---|---|
| `get` | `kubectl get pod api-xxx` |
| `list` | `kubectl get pods` |
| `watch` | `kubectl get pods -w` |
| `create` | `kubectl create/apply` new object |
| `update` | replace object |
| `patch` | `kubectl patch`, many `kubectl set` commands |
| `delete` | `kubectl delete pod` |
| `deletecollection` | delete multiple objects |

## `kubectl auth can-i` cookbook

Current user:

```bash
kubectl auth can-i list pods -n <ns>
kubectl auth can-i get pods/log -n <ns>
kubectl auth can-i create pods/exec -n <ns>
kubectl auth can-i patch deployments -n <ns>
kubectl auth can-i get nodes
```

As a service account:

```bash
kubectl auth can-i list pods -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i get pods/log -n day34 --as=system:serviceaccount:day34:viewer
kubectl auth can-i create configmaps -n day34 --as=system:serviceaccount:day34:viewer
```

List all allowed actions for current subject:

```bash
kubectl auth can-i --list -n <ns>
```

## Minimal read-only namespace role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: namespace-reader
  namespace: app
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log", "services", "endpoints", "events", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["events.k8s.io"]
  resources: ["events"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses", "networkpolicies"]
  verbs: ["get", "list", "watch"]
```

Bind to a group:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-readers
  namespace: app
subjects:
- kind: Group
  name: app-readers
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: namespace-reader
  apiGroup: rbac.authorization.k8s.io
```

## ServiceAccount pattern

Workload does not need Kubernetes API:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api
automountServiceAccountToken: false
```

Pod usage:

```yaml
spec:
  serviceAccountName: api
  automountServiceAccountToken: false
```

Workload needs API access:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pod-reader
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pod-reader
subjects:
- kind: ServiceAccount
  name: pod-reader
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

## Least-privilege kubeconfig for UI tools

Create a short-lived ServiceAccount token:

```bash
kubectl create token ui-viewer -n day34 --duration=2h
```

Build a separate kubeconfig instead of importing an admin context into k9s/Lens:

```bash
VIEWER_TOKEN=$(kubectl create token ui-viewer -n day34 --duration=2h)
SERVER=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}')
CA_DATA=$(kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

kubectl config set-cluster day34-cluster \
  --server="$SERVER" \
  --certificate-authority-data="$CA_DATA" \
  --kubeconfig=day34-viewer.kubeconfig
kubectl config set-credentials day34-ui-viewer \
  --token="$VIEWER_TOKEN" \
  --kubeconfig=day34-viewer.kubeconfig
kubectl config set-context day34-ui-viewer \
  --cluster=day34-cluster \
  --user=day34-ui-viewer \
  --namespace=day34 \
  --kubeconfig=day34-viewer.kubeconfig
kubectl config use-context day34-ui-viewer --kubeconfig=day34-viewer.kubeconfig
```

Verify real behavior without impersonation:

```bash
kubectl --kubeconfig=day34-viewer.kubeconfig get pods -n day34
kubectl --kubeconfig=day34-viewer.kubeconfig get events.events.k8s.io -n day34
kubectl --kubeconfig=day34-viewer.kubeconfig get secrets -n day34
```

Expected: Pods/events are readable, Secrets are forbidden.

## Debug `Forbidden`

Error example:

```text
User "system:serviceaccount:day34:viewer" cannot get resource "pods/log" in API group "" in the namespace "day34"
```

Parse:

| Part | Value |
|---|---|
| Subject | `system:serviceaccount:day34:viewer` |
| Verb | `get` |
| Resource | `pods/log` |
| API group | `""` |
| Namespace | `day34` |

Check:

```bash
kubectl auth can-i get pods/log -n day34 --as=system:serviceaccount:day34:viewer
kubectl get role,rolebinding -n day34
kubectl describe rolebinding <binding> -n day34
kubectl describe role <role> -n day34
```

## k9s operations notes

Common usage:

```bash
k9s
k9s -n <namespace>
k9s --context <context>
k9s --kubeconfig day34-viewer.kubeconfig -n day34
```

Useful views:

| View | Purpose |
|---|---|
| `:pods` | Pod list |
| `:deploy` | Deployments |
| `:svc` | Services |
| `:events` | Events |
| `:rbac` | RBAC resources if supported by version |
| `/` | Filter current view |
| `l` | Logs on selected Pod |
| `d` | Describe selected object |

Operational rule:

- If k9s can delete, exec or edit, your kubeconfig subject can do that.
- Use least-privilege context by default.
- Keep production context visually distinct.

## Lens operations notes

Checklist before using Lens on production:

- Confirm context name and cluster endpoint.
- Confirm identity is not admin unless in break-glass session.
- Prefer read-only kubeconfig for daily observation.
- Avoid editing live objects if GitOps owns the resource.
- Check audit policy for exec/logs/secret access.

Useful views:

- Workloads: Deployments, StatefulSets, DaemonSets, Jobs.
- Pods: status, logs, shell if permitted.
- Network: Services, Ingresses.
- Config: ConfigMaps, Secrets if permitted.
- Nodes: capacity and pressure.
- Events: timeline for troubleshooting.

## RBAC review questions

- Who can read Secrets?
- Who can exec into production Pods?
- Who can create privileged Pods?
- Who can patch Deployments?
- Who can read logs across namespaces?
- Who can create RoleBindings?
- Who can bind existing ClusterRoles?
- Which service accounts have tokens mounted?
- Which CI/CD tokens are namespace-limited?
- Which contexts in developer machines are admin?

## Cleanup

```bash
kubectl delete namespace day34
```
