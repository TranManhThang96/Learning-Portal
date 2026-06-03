# Document - Day 22: Volume Reference

## Volume lifecycle

| Storage place | Scope | Survives container restart | Survives Pod deletion | Typical use |
|---|---|---:|---:|---|
| Container writable layer | Container | No/implementation-dependent | No | Temporary app writes only |
| `emptyDir` | Pod on one node | Yes | No | Scratch/cache/shared workspace |
| `configMap` volume | Pod | Yes | No | Config file injection |
| `secret` volume | Pod | Yes | No | Secret/cert file injection |
| `hostPath` | Node path | Yes if same node/path | Not portable | Node agent/lab only |
| PVC-backed volume | Storage backend | Yes | Depends reclaim policy | Persistent app data |

## Common volume types

| Type | Good for | Avoid for |
|---|---|---|
| `emptyDir` | Scratch, cache, init-to-app handoff | Durable data |
| `emptyDir.medium: Memory` | Fast temp files, sensitive temp data | Large unbounded writes |
| `configMap` | Non-sensitive config files | Secrets, large binary data |
| `secret` | Credentials, TLS certs | Long-term secret lifecycle alone |
| `projected` | Combine config/secret/token/metadata | Hiding ownership of too many inputs |
| `hostPath` | Node-level agents | Normal application storage |

## Minimal `emptyDir`

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
spec:
  volumes:
  - name: work
    emptyDir:
      sizeLimit: 512Mi
  containers:
  - name: writer
    image: busybox:1.36
    command: ["sh", "-c", "while true; do date >> /work/out.txt; sleep 5; done"]
    volumeMounts:
    - name: work
      mountPath: /work
```

## Shared volume between containers

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: shared-volume-demo
spec:
  volumes:
  - name: shared
    emptyDir: {}
  containers:
  - name: writer
    image: busybox:1.36
    command: ["sh", "-c", "while true; do date > /shared/time.txt; sleep 2; done"]
    volumeMounts:
    - name: shared
      mountPath: /shared
  - name: reader
    image: busybox:1.36
    command: ["sh", "-c", "while true; do cat /shared/time.txt 2>/dev/null || true; sleep 2; done"]
    volumeMounts:
    - name: shared
      mountPath: /shared
```

## ConfigMap as files

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  app.yaml: |
    logLevel: info
    featureFlag: false
---
apiVersion: v1
kind: Pod
metadata:
  name: config-volume-demo
spec:
  volumes:
  - name: config
    configMap:
      name: app-config
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "cat /etc/app/app.yaml; sleep 3600"]
    volumeMounts:
    - name: config
      mountPath: /etc/app
      readOnly: true
```

## Secret as files

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
type: Opaque
stringData:
  password: change-me
---
apiVersion: v1
kind: Pod
metadata:
  name: secret-volume-demo
spec:
  volumes:
  - name: secret
    secret:
      secretName: app-secret
      defaultMode: 0400
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "ls -l /run/secret; sleep 3600"]
    volumeMounts:
    - name: secret
      mountPath: /run/secret
      readOnly: true
```

## Projected volume

```yaml
volumes:
- name: app-inputs
  projected:
    sources:
    - configMap:
        name: app-config
    - secret:
        name: app-secret
    - downwardAPI:
        items:
        - path: pod-name
          fieldRef:
            fieldPath: metadata.name
```

## `subPath` example

```yaml
volumeMounts:
- name: config
  mountPath: /etc/nginx/conf.d/default.conf
  subPath: default.conf
  readOnly: true
```

Use `subPath` when you need to mount one file without replacing the whole directory. Avoid assuming ConfigMap/Secret updates propagate cleanly through `subPath`.

## Debug commands

```bash
kubectl get pod <pod> -o yaml
kubectl describe pod <pod>
kubectl get configmap,secret
kubectl exec -it <pod> -- sh
kubectl exec <pod> -- mount
kubectl exec <pod> -- df -h
kubectl exec <pod> -- ls -la <mount-path>
kubectl get events --sort-by=.lastTimestamp
```

## Failure modes

| Symptom | Likely cause | First check |
|---|---|---|
| Pod stuck `CreateContainerConfigError` | Missing ConfigMap/Secret | `describe pod`, object namespace |
| File not found in container | Wrong mount path/key/items | Pod YAML and `ls` inside container |
| Config changed but app still old | App does not reload or env var used | Restart/rollout strategy |
| Permission denied | File mode/user/fsGroup | `ls -l`, securityContext |
| Node disk pressure | Unbounded writes to `emptyDir` | Events, node conditions |
| Pod works only on one node | `hostPath` node dependency | Pod node, path on node |

## Decision guide

```text
Need temp files only?
  -> emptyDir

Need file shared between containers in one Pod?
  -> emptyDir

Need non-sensitive config file?
  -> configMap volume

Need credential/cert file?
  -> secret volume

Need node filesystem?
  -> hostPath, only for node-agent/lab

Need data survive Pod deletion?
  -> PV/PVC, Day 23
```

## Production checklist

- [ ] Volume type matches desired lifecycle.
- [ ] Mounts are read-only unless write is required.
- [ ] `emptyDir` has `sizeLimit` for risky workloads.
- [ ] `hostPath` usage is documented and restricted.
- [ ] Config/Secret update behavior is tested.
- [ ] Sensitive temp data uses memory-backed volume or proper cleanup.
- [ ] Node disk pressure alerts exist for write-heavy Pods.
