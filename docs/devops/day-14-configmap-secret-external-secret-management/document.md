# Day 14: ConfigMap, Secret & External Secret Management — Cheat Sheet

## ConfigMap Quick Reference

### Tạo ConfigMap

```bash
# Từ literal values
kubectl create configmap app-config \
  --from-literal=KEY1=value1 \
  --from-literal=KEY2=value2

# Từ file
kubectl create configmap app-config --from-file=config.yaml
kubectl create configmap app-config --from-file=my-key=config.yaml  # custom key

# Từ directory (mỗi file = 1 key)
kubectl create configmap app-config --from-file=./config-dir/

# Từ .env file
kubectl create configmap app-config --from-env-file=app.env
```

### ConfigMap YAML

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  # immutable: true  # Optional: prevent updates
data:
  SIMPLE_KEY: "value"
  config.yaml: |
    multi:
      line:
        content: here
binaryData:
  binary-file: <base64-encoded-binary>
```

## Secret Quick Reference

### Tạo Secret

```bash
# Generic (Opaque)
kubectl create secret generic app-secrets \
  --from-literal=DB_PASS=secret123

# TLS
kubectl create secret tls app-tls \
  --cert=tls.crt --key=tls.key

# Docker registry
kubectl create secret docker-registry regcred \
  --docker-server=registry.example.com \
  --docker-username=user \
  --docker-password=pass

# Từ file
kubectl create secret generic ssh-key \
  --from-file=ssh-privatekey=~/.ssh/id_rsa
```

### Secret Types

| Type | Mô tả | Dùng cho |
|------|--------|----------|
| `Opaque` | Generic key-value | App credentials |
| `kubernetes.io/tls` | TLS cert + key | Ingress TLS |
| `kubernetes.io/dockerconfigjson` | Docker registry auth | Image pull |
| `kubernetes.io/service-account-token` | SA token | API access |
| `kubernetes.io/basic-auth` | Username + password | Basic auth |
| `kubernetes.io/ssh-auth` | SSH private key | SSH access |

### Decode Secret

```bash
kubectl get secret <name> -o jsonpath='{.data.<key>}' | base64 -d
kubectl get secret <name> -o go-template='{{range $k,$v := .data}}{{$k}}={{$v | base64decode}}{{"\n"}}{{end}}'
```

## Inject Methods Comparison

| Aspect | Environment Variable | Volume Mount | Volume Mount + subPath |
|--------|---------------------|-------------|----------------------|
| **Auto-update** | ❌ Need pod restart | ✅ ~60-120s | ❌ No auto-update |
| **Visibility** | High (describe, /proc) | Low (file perms) | Low |
| **Multi-line** | ❌ Difficult | ✅ Full file support | ✅ |
| **Existing dir** | N/A | ⚠️ Overwrites dir | ✅ Preserves dir |
| **Use for** | Simple config | Secrets, config files | Single file in existing dir |

### Inject Patterns

```yaml
# Pattern 1: All keys as env vars
envFrom:
  - configMapRef:
      name: app-config
  - secretRef:
      name: app-secrets

# Pattern 2: Specific key as env var
env:
  - name: DB_HOST
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: DB_HOST

# Pattern 3: Volume mount all keys as files
volumes:
  - name: config
    configMap:
      name: app-config
volumeMounts:
  - name: config
    mountPath: /config
    readOnly: true

# Pattern 4: Volume mount specific key
volumes:
  - name: config
    configMap:
      name: app-config
      items:
        - key: nginx.conf
          path: nginx.conf
volumeMounts:
  - name: config
    mountPath: /etc/nginx/nginx.conf
    subPath: nginx.conf

# Pattern 5: Secret with permissions
volumes:
  - name: secrets
    secret:
      secretName: app-secrets
      defaultMode: 0400
```

## Secret Management Tools Comparison

| Tool | Type | GitOps | Dynamic Secrets | Rotation | Complexity | Cost |
|------|------|--------|----------------|----------|------------|------|
| **Native Secret** | Built-in | ❌ | ❌ | Manual | Low | Free |
| **Sealed Secrets** | Encrypt-to-git | ✅ | ❌ | Manual | Low | Free |
| **SOPS** | Encrypt files | ✅ | ❌ | Manual | Medium | Free |
| **Vault** | Central store | Partial | ✅ | Auto | High | Free/Paid |
| **External Secrets** | Sync from store | ✅ | Via store | Via store | Medium | Free |
| **AWS SSM/SM** | Cloud native | Via ESO | ✅ (SM) | ✅ (SM) | Low | Pay-per-use |

### Decision Flowchart

```
Cần dynamic secrets (DB creds auto-generated)?
├─ YES → HashiCorp Vault hoặc AWS Secrets Manager + ESO
└─ NO
   Cần commit secrets vào git (GitOps)?
   ├─ YES
   │  Dùng KMS cloud?
   │  ├─ YES → SOPS + cloud KMS
   │  └─ NO  → Sealed Secrets
   └─ NO
      Dùng cloud managed secret store?
      ├─ YES → External Secrets Operator
      └─ NO  → Native Secret + encryption at rest + RBAC
```

## Production Secret Management Checklist

### Storage & Encryption
- [ ] Encryption at rest enabled (EncryptionConfiguration)
- [ ] Secrets not stored in git (plain text)
- [ ] Secrets not baked into container images
- [ ] Base64 encoding done correctly (no trailing newline)

### Access Control
- [ ] RBAC: least privilege for secret access
- [ ] ServiceAccount per workload (not default SA)
- [ ] automountServiceAccountToken: false where not needed
- [ ] Role restricts to specific secret names (resourceNames)

### Injection
- [ ] Volume mount preferred over env vars for secrets
- [ ] defaultMode: 0400 on secret volumes
- [ ] readOnlyRootFilesystem on containers
- [ ] Secrets not logged by application

### Operations
- [ ] Rotation strategy documented
- [ ] Rotation tested (no downtime)
- [ ] Dual-read period during rotation
- [ ] Old credentials revoked after rotation
- [ ] Audit logging enabled for secret access

### Monitoring
- [ ] Alert on unauthorized secret access attempts
- [ ] Alert on secret creation/deletion in production
- [ ] Secret scanning in CI/CD pipeline
- [ ] Regular review of who has secret access

## Debugging Commands

```bash
# View ConfigMap
kubectl get configmap <name> -o yaml
kubectl describe configmap <name>

# View Secret (careful in production!)
kubectl get secret <name> -o yaml
kubectl get secret <name> -o jsonpath='{.data.<key>}' | base64 -d

# Check what pod sees
kubectl exec <pod> -- env | sort                    # Env vars
kubectl exec <pod> -- ls -la /path/to/mounts        # Mounted files
kubectl exec <pod> -- cat /path/to/config            # File content

# Check RBAC
kubectl auth can-i get secrets --as=system:serviceaccount:<ns>:<sa>
kubectl auth can-i get secrets/<name> --as=system:serviceaccount:<ns>:<sa>

# Events (for mount issues)
kubectl describe pod <name> | grep -A 10 Events
```

