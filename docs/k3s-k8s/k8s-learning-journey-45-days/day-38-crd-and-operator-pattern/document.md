# Document - Day 38: CRD và Operator Reference

## CRD minimal skeleton

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.platform.example.com
spec:
  group: platform.example.com
  scope: Namespaced
  names:
    plural: webapps
    singular: webapp
    kind: WebApp
    shortNames:
    - wa
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        required:
        - spec
        properties:
          spec:
            type: object
            required:
            - image
            - replicas
            properties:
              image:
                type: string
                minLength: 1
              replicas:
                type: integer
                minimum: 1
                maximum: 10
          status:
            type: object
            properties:
              observedGeneration:
                type: integer
              readyReplicas:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                    reason:
                      type: string
                    message:
                      type: string
    subresources:
      status: {}
```

## Custom resource example

```yaml
apiVersion: platform.example.com/v1
kind: WebApp
metadata:
  name: checkout
  namespace: day38
spec:
  image: nginx:1.25
  replicas: 2
```

## Core fields

| Field | Meaning |
|---|---|
| `spec.group` | API group, e.g. `platform.example.com` |
| `spec.names.kind` | Kind shown in YAML |
| `spec.names.plural` | Resource name used by API path/kubectl |
| `spec.scope` | `Namespaced` or `Cluster` |
| `versions[].served` | API server serves this version |
| `versions[].storage` | Version stored in etcd |
| `openAPIV3Schema` | Validation and pruning schema |
| `subresources.status` | Enables separate status updates |
| `subresources.scale` | Enables scale integration if configured |

## kubectl commands

```bash
kubectl get crd
kubectl describe crd webapps.platform.example.com
kubectl api-resources | findstr WebApp
kubectl explain webapp
kubectl explain webapp.spec
kubectl get webapps -A
kubectl get webapp checkout -n day38 -o yaml
kubectl describe webapp checkout -n day38
```

Linux/macOS:

```bash
kubectl api-resources | grep WebApp
```

## Status condition pattern

```yaml
status:
  observedGeneration: 3
  readyReplicas: 2
  conditions:
  - type: Ready
    status: "True"
    reason: AllReplicasReady
    message: All requested replicas are ready
  - type: Progressing
    status: "False"
    reason: ReconcileComplete
```

Useful condition fields:

| Field | Meaning |
|---|---|
| `type` | Condition category, e.g. `Ready` |
| `status` | `True`, `False`, `Unknown` |
| `reason` | Short machine-readable reason |
| `message` | Human-readable detail |
| `lastTransitionTime` | When condition status last changed |
| `observedGeneration` | Which spec generation this condition reflects |

## Reconcile pseudo-code

```text
reconcile(key):
  cr = get WebApp by key
  if not found:
    return

  if cr.deletionTimestamp exists:
    cleanup external resources
    remove finalizer
    return

  ensure finalizer exists

  desiredDeployment = build from cr.spec
  currentDeployment = get child deployment
  create or patch deployment

  desiredService = build from cr.spec
  currentService = get child service
  create or patch service

  update cr.status.observedGeneration
  update cr.status.readyReplicas
  update cr.status.conditions
```

## Finalizer example

```yaml
metadata:
  finalizers:
  - platform.example.com/finalizer
```

Deletion flow:

```text
kubectl delete webapp checkout --wait=false
  |
  v
API server sets deletionTimestamp, object remains
  |
  v
controller sees deletionTimestamp
  |
  v
controller cleanup external/child resources
  |
  v
controller removes finalizer
  |
  v
object deleted
```

Break-glass patch:

```bash
kubectl patch webapp checkout -n day38 --type=json \
  -p='[{"op":"remove","path":"/metadata/finalizers"}]'
```

Use only after confirming cleanup risk.

Trong lab, ưu tiên `--wait=false` khi cố tình mô phỏng finalizer kẹt. Trong production, lệnh delete chờ quá lâu là tín hiệu phải kiểm tra controller logs và trạng thái cleanup trước khi remove finalizer thủ công.

## OwnerReference example

```yaml
metadata:
  ownerReferences:
  - apiVersion: platform.example.com/v1
    kind: WebApp
    name: checkout
    uid: <owner-uid>
    controller: true
    blockOwnerDeletion: true
```

OwnerReferences clean up in-cluster child resources. They do not clean up external cloud/database resources.

## CRD versioning checklist

- [ ] New version is `served: true`.
- [ ] Exactly one version is `storage: true`.
- [ ] Conversion strategy is planned if schema changes.
- [ ] Old objects can be read by new controller.
- [ ] Required fields do not break existing objects.
- [ ] `status` schema is backward compatible.
- [ ] Backup exists before CRD upgrade.
- [ ] Rollback plan exists for controller and CRD.

## Operator install review

Before installing any Operator:

- What CRDs will it create?
- Which namespaces does it watch?
- Which RBAC permissions does it need?
- Does it need cluster-admin?
- Does it manage data or external cloud resources?
- How does backup/restore work?
- How are upgrades performed?
- What metrics and alerts exist?
- What happens if the controller is down?
- What finalizers can it add?

## Failure mode matrix

| Symptom | Likely cause | First checks |
|---|---|---|
| CR created but nothing happens | Controller missing/down | Operator Pod, logs, Deployment |
| Status stale | Reconcile failing or generation not observed | `status.observedGeneration`, logs |
| Delete stuck | Finalizer cleanup failing | finalizers, deletionTimestamp, logs |
| Controller logs `Forbidden` | RBAC missing | `kubectl auth can-i`, Role/Binding |
| API rejects CR | Schema validation | CRD schema, error output |
| Upgrade breaks old CRs | CRD version/conversion issue | served/storage versions, conversion logs |
| Child resources recreated constantly | Drift loop or competing owner | ownerReferences, GitOps, controller logs |

## Production readiness for Operators

- [ ] Controller runs with HA/leader election if needed.
- [ ] RBAC is least privilege.
- [ ] CRDs and custom resources are backed up.
- [ ] Metrics and alerts cover reconcile errors.
- [ ] Logs include namespace/name/generation.
- [ ] Finalizer runbook exists.
- [ ] Upgrade tested with existing CRs.
- [ ] CRD schema is reviewed before apply.
- [ ] External API/IAM permissions are scoped.
- [ ] Data-loss scenarios are documented.
