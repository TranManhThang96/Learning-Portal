# Document - Day 35: Pod Security và Admission Control Reference

## Admission flow

```text
Client request
  |
  v
Authentication
  |
  v
Authorization / RBAC
  |
  v
Mutating admission
  |
  v
Validating admission
  |
  v
Persist object in etcd
```

RBAC answers: can this subject perform this action?

Admission answers: is this object acceptable?

## Pod Security profiles

| Profile | Intent | Examples allowed/blocked |
|---|---|---|
| `Privileged` | Unrestricted | Allows privileged/system workloads |
| `Baseline` | Prevent known privilege escalation primitives | Blocks privileged containers and many host namespace usages |
| `Restricted` | Strong hardening | Requires non-root-friendly config, seccomp, drop capabilities, no privilege escalation |

## Namespace labels

Lab-friendly:

```bash
kubectl label namespace <ns> \
  pod-security.kubernetes.io/enforce=baseline \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/audit=restricted \
  --overwrite
```

Production-style with pinned version:

```bash
kubectl label namespace <ns> \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=<cluster-minor> \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/warn-version=<cluster-minor> \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/audit-version=<cluster-minor> \
  --overwrite
```

Set `<cluster-minor>` from the API server minor version, for example `v1.xx`. Check `kubectl version` before pinning; do not reuse a hardcoded version across clusters.

Inspect labels:

```bash
kubectl get namespace <ns> --show-labels
kubectl describe namespace <ns>
```

## Common violations

| Violation | Typical error/warning |
|---|---|
| `privileged: true` | privileged containers not allowed |
| `hostNetwork: true` | host namespaces not allowed by profile |
| `hostPID: true` | host namespaces not allowed |
| `hostPath` volume | restricted hostPath volume usage |
| `allowPrivilegeEscalation` missing/true | must be false under restricted |
| capabilities not dropped | must drop `ALL` under restricted |
| no seccomp profile | must set `RuntimeDefault` or `Localhost` |
| root user | must run as non-root or explicit non-zero UID |

## Restricted-friendly Pod template

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: restricted-ok
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
      runAsUser: 1000
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

## SecurityContext field reference

| Field | Recommended direction |
|---|---|
| `runAsNonRoot` | `true` |
| `runAsUser` | non-zero UID if image supports it |
| `allowPrivilegeEscalation` | `false` |
| `capabilities.drop` | include `ALL` |
| `seccompProfile.type` | `RuntimeDefault` |
| `privileged` | `false` or unset |
| `readOnlyRootFilesystem` | `true` when app supports it |
| `hostNetwork`/`hostPID`/`hostIPC` | avoid for app workloads |

## Policy tool comparison

| Tool | Strength | Cost |
|---|---|---|
| Pod Security Admission | Built-in, simple, low operational overhead | Pod-only, fixed profiles |
| Kyverno | YAML-native validate/mutate/generate/verify | Operate controller/webhook, policy design discipline |
| OPA/Gatekeeper | Powerful Rego policies and audit | Rego learning curve, operate controller/webhook |
| Custom admission webhook | Fully custom logic | Highest maintenance and availability risk |

## Webhook operational checklist

```bash
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
kubectl get pod -n <policy-namespace>
kubectl logs -n <policy-namespace> deploy/<policy-controller> --tail=100
kubectl get events -n <policy-namespace> --sort-by=.lastTimestamp
```

Review:

- `failurePolicy`: `Fail` or `Ignore`.
- `timeoutSeconds`.
- `namespaceSelector`.
- `objectSelector`.
- CA bundle/cert rotation.
- Controller replicas and readiness.
- Metrics for admission latency/errors.

Note: these Events are for policy controller/webhook Pods. Pod Security Admission `audit` mode writes audit annotations to the API audit log when audit logging is enabled; it does not create a normal namespace Event for every rejected or audited Pod.

## Migration plan to `restricted`

1. Label namespace with `warn=restricted` and `audit=restricted`.
2. Apply normal workload manifests and collect warnings.
3. Fix image/runtime issues:
   - run non-root
   - drop capabilities
   - set seccomp
   - disable privilege escalation
4. Add securityContext to Helm chart or service template.
5. Test in staging with `enforce=restricted`.
6. Pin policy version.
7. Roll to production namespace.
8. Monitor rejected requests and audit violations.

## Debug rejected Pod

```bash
kubectl apply -f pod.yaml
kubectl get namespace <ns> --show-labels
kubectl describe namespace <ns>
kubectl auth can-i create pods -n <ns>
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
```

Evidence matrix:

| Mode/path | Where evidence appears |
|---|---|
| `enforce` reject | `kubectl apply` error/API response; Pod is not persisted |
| `warn` | Warning returned to client while request may succeed |
| `audit` | API audit log annotation if audit logging is enabled |
| External webhook reject | `kubectl apply` error plus policy controller/webhook logs |
| Namespace Events | Useful for controller/webhook health, not reliable evidence for PSA reject |

Read the error:

```text
violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false, unrestricted capabilities, seccompProfile
```

Map each fragment to a manifest fix:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```

## Exception worksheet

Use this before allowing privileged or host-level workload:

```text
Workload:
Namespace:
Owner:
Why standard restricted/baseline does not work:
Exact permissions needed:
Alternative considered:
Blast radius:
Node pool isolation:
RBAC subject:
NetworkPolicy:
Monitoring:
Review date:
Rollback plan:
```

## Cleanup

```bash
kubectl delete namespace day35-baseline
kubectl delete namespace day35-restricted
```
