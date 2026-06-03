# Day 14: ConfigMap, Secret & External Secret Management

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Sử dụng được** ConfigMap và Secret để inject configuration vào pod qua environment variable và volume mount.
2. **Giải thích được** vì sao Kubernetes Secret không phải là encryption thực sự và các rủi ro bảo mật liên quan.
3. **Phân biệt được** các giải pháp secret management: native Secret, Vault, Sealed Secrets, SOPS, External Secrets Operator.
4. **Thiết kế được** secret rotation strategy phù hợp cho production.
5. **Cấu hình được** env var vs mounted file và hiểu trade-offs của từng approach.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng?

Ở Day 13, bạn đã expose service ra ngoài với TLS certificate lưu trong Secret. Nhưng configuration và secret management là bài toán rộng hơn nhiều:

- Mọi application cần **configuration**: database URL, feature flags, log level, API endpoints.
- Mọi application cần **secrets**: database password, API keys, TLS certificates, OAuth tokens.

**12-Factor App** (factor III): **Store config in the environment** — tách config khỏi code.

### Nếu làm sai thì sao?

- **Hardcode secret trong image** → secret bị expose qua Docker registry, git history.
- **Secret trong environment variable** → bị log ra stdout, visible qua `kubectl describe`.
- **Không rotate secret** → credential bị leak → attacker có access vĩnh viễn.
- **ConfigMap sai giá trị** → app crash hoặc hoạt động sai, khó debug.
- **Secret không encrypt at rest** → ai có access etcd = có tất cả secrets.

### Liên hệ với developer background

- **ConfigMap** giống `.env` file hoặc `application.yml` — nhưng managed bởi Kubernetes.
- **Secret** giống credential store (AWS SSM, 1Password) — nhưng chỉ base64 encoded.
- **Vault** giống enterprise credential manager (HashiCorp Vault, AWS Secrets Manager).
- **Sealed Secrets** giống encrypted config file commit được vào git.

---

## 3. Kiến thức nền tảng

### ConfigMap — lưu configuration data

ConfigMap lưu non-confidential data dưới dạng key-value pairs.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  # Key-value pairs đơn giản
  LOG_LEVEL: "info"
  DB_HOST: "postgres-svc"
  DB_PORT: "5432"
  FEATURE_NEW_UI: "true"
  
  # File content (multi-line)
  nginx.conf: |
    server {
      listen 80;
      server_name localhost;
      location / {
        root /usr/share/nginx/html;
      }
    }
```

**Giới hạn:**
- Max size: **1 MiB** (1,048,576 bytes).
- Không dùng cho sensitive data.
- Immutable ConfigMap (`immutable: true`) không thể update — phải delete/recreate.

### Secret — lưu sensitive data

Secret lưu sensitive data, **base64 encoded** (KHÔNG phải encrypted).

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  # Base64 encoded values
  DB_PASSWORD: cGFzc3dvcmQxMjM=      # echo -n "password123" | base64
  API_KEY: c2VjcmV0LWtleS14eXo=      # echo -n "secret-key-xyz" | base64
```

Hoặc dùng `stringData` (plain text, Kubernetes tự encode):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  DB_PASSWORD: password123
  API_KEY: secret-key-xyz
```

### ⚠️ Secret KHÔNG phải encryption

```bash
# Ai cũng có thể decode base64
echo "cGFzc3dvcmQxMjM=" | base64 -d
# Output: password123
```

**Secret chỉ cung cấp:**
- Tách biệt khỏi pod spec (separation of concerns).
- RBAC control (ai được đọc secret nào).
- Audit logging.
- Optional: encryption at rest (cần cấu hình riêng).

**Secret KHÔNG cung cấp:**
- Encryption mặc định (chỉ base64 encoding).
- Protection nếu attacker có access etcd.
- Protection nếu attacker có RBAC read secret.

---

## 4. Deep Dive

### 4.1 Inject ConfigMap/Secret vào Pod

#### Cách 1: Environment Variables

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-env
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "echo DB=$DB_HOST:$DB_PORT && sleep 3600"]
      env:
        # Từ ConfigMap (từng key)
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: DB_HOST
        # Từ Secret (từng key)
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: DB_PASSWORD
      # Hoặc import tất cả keys
      envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
```

#### Cách 2: Volume Mount (files)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-mount
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "cat /config/nginx.conf && sleep 3600"]
      volumeMounts:
        - name: config-volume
          mountPath: /config
          readOnly: true
        - name: secret-volume
          mountPath: /secrets
          readOnly: true
  volumes:
    - name: config-volume
      configMap:
        name: app-config
    - name: secret-volume
      secret:
        secretName: app-secrets
        defaultMode: 0400  # Read-only by owner
```

### 4.2 Environment Variable vs Volume Mount

```
┌───────────────────────────────────────────────────────────┐
│                 Inject Methods Comparison                   │
│                                                             │
│  Environment Variable              Volume Mount             │
│  ┌─────────────────┐              ┌─────────────────┐      │
│  │ DB_HOST=postgres│              │ /config/         │      │
│  │ DB_PORT=5432    │              │   ├── DB_HOST    │      │
│  │ DB_PASS=****    │              │   ├── DB_PORT    │      │
│  │                 │              │   └── nginx.conf │      │
│  │ Process env     │              │                  │      │
│  │ Visible: ps,    │              │ File system      │      │
│  │ /proc, describe │              │ Auto-update ✅   │      │
│  │ No auto-update  │              │ Less visible     │      │
│  └─────────────────┘              └─────────────────┘      │
└───────────────────────────────────────────────────────────┘
```

| Feature | Environment Variable | Volume Mount |
|---------|---------------------|-------------|
| **Update mechanism** | ❌ Cần restart pod | ✅ Auto-update (kubelet sync) |
| **Update delay** | N/A | ~1-2 phút (kubelet sync period) |
| **Visibility** | Visible qua `kubectl describe`, `/proc`, core dumps | File permission control |
| **Multi-line content** | ❌ Khó (escape characters) | ✅ Tốt (file config) |
| **App compatibility** | Hầu hết apps đọc env | App cần đọc file |
| **Secret safety** | ⚠️ Dễ bị log | ✅ Hơn (file có permission) |
| **Best for** | Simple key-value | Config files, certificates, complex data |

> **Production recommendation**: Dùng **volume mount** cho secrets (file permission, auto-update). Dùng **env var** cho simple config (log level, feature flags).

### 4.3 Secret Update Propagation

```
ConfigMap/Secret update
        │
        ▼
┌─────────────────┐
│   API Server    │
│   (etcd update) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Kubelet      │
│ (watch + sync)  │
│ ~60-120s delay  │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
Volume Mount  Env Var
    │         │
 Auto-update  NO update
 (file change) (need restart)
```

### 4.4 External Secret Management Solutions

| Tool | Approach | GitOps-friendly | Complexity | Best for |
|------|----------|----------------|------------|----------|
| **Native Secret** | Base64 in etcd | ❌ (plain in git) | Low | Dev, simple setup |
| **Sealed Secrets** | Encrypt → commit to git → decrypt in cluster | ✅ | Low-Med | Small teams, GitOps |
| **SOPS** | Encrypt YAML/JSON files | ✅ | Medium | Multi-cloud, file-based |
| **HashiCorp Vault** | Centralized secret store | Partial | High | Enterprise, dynamic secrets |
| **External Secrets Operator** | Sync from external store → K8s Secret | ✅ | Medium | Multi-cloud, managed secret stores |

#### Sealed Secrets Flow

```
Developer                   Cluster
┌──────────┐               ┌──────────────────┐
│ Secret   │               │ Sealed Secrets   │
│ YAML     │──kubeseal──►  │ Controller       │
│ (plain)  │   encrypt     │                  │
└──────────┘               │ SealedSecret     │
                           │ (encrypted)      │
     Git Repo              │       │          │
     ┌────────┐            │       ▼          │
     │Sealed  │◄───commit──│ Decrypt →        │
     │Secret  │            │ K8s Secret       │
     │(safe!) │            └──────────────────┘
     └────────┘
```

#### External Secrets Operator Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────┐
│ External Store  │     │ External Secrets │     │ K8s      │
│                 │     │ Operator         │     │ Secret   │
│ AWS SSM         │◄────│                  │────►│          │
│ Vault           │ pull│ ExternalSecret   │ sync│ (auto-   │
│ Azure KV        │     │ resource (CR)    │     │ created) │
│ GCP SM          │     │                  │     │          │
└─────────────────┘     └─────────────────┘     └──────────┘
```

### 4.5 Secret Encryption at Rest

Mặc định, Kubernetes lưu Secret dưới dạng **plain text trong etcd**. Cần cấu hình encryption:

```yaml
# EncryptionConfiguration
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-key>
      - identity: {}  # Fallback: no encryption
```

---

## 5. Trade-offs & Best Practices ⭐

### Chọn Secret Management Tool nào?

| Scenario | Recommendation | Lý do |
|----------|---------------|-------|
| **Dev/learning** | Native Secret | Đơn giản, built-in |
| **Small team, GitOps** | Sealed Secrets | Encrypt + commit, low overhead |
| **Multi-cloud** | SOPS + KMS | Vendor-agnostic encryption |
| **Enterprise** | Vault + External Secrets | Dynamic secrets, audit, rotation |
| **AWS-heavy** | External Secrets + SSM/SM | Native integration |

### Best Practices

1. **Không commit Secret YAML vào git** — dùng Sealed Secrets hoặc External Secrets.
2. **Env var cho config, volume mount cho secrets** — secrets trong files an toàn hơn.
3. **Set `defaultMode: 0400`** cho secret volumes — chỉ owner read.
4. **Enable encryption at rest** — mã hóa secrets trong etcd.
5. **RBAC giới hạn** — chỉ service accounts cần thiết mới read được secret.
6. **Audit logging** — log mọi access đến secrets.
7. **Rotation strategy** — plan cho việc rotate secrets định kỳ.
8. **Immutable ConfigMap** cho config ít thay đổi — giảm load lên API server.

### Anti-patterns

1. **Secret trong Dockerfile / image** → bị bake vĩnh viễn, ai pull image = có secret.
2. **Secret trong git history** → dù đã xóa, vẫn còn trong history.
3. **Dùng `kubectl describe pod` để debug** → hiển thị env vars bao gồm secrets.
4. **Không set RBAC cho secrets** → mọi pod có thể đọc mọi secret.
5. **Log env vars** → secret bị ghi vào log system.

---

## 6. Performance & Scalability ⭐

### ConfigMap/Secret Size Limits

- **Max size**: 1 MiB per ConfigMap/Secret.
- **Watch mechanism**: kubelet watch API server cho changes → cần CPU/memory cho large clusters.
- **Nhiều pod mount cùng Secret** → kubelet sync tất cả → tăng API server load.

### Update Propagation Delay

- Volume mount: **60-120 giây** (configurable qua `kubelet --sync-frequency`).
- Env var: **không update** — phải restart pod.
- Projected volume: tương tự volume mount.

### Optimization Tips

- Dùng `immutable: true` cho ConfigMap/Secret không thay đổi → giảm watch load.
- Giới hạn số Secret per namespace.
- Dùng External Secrets Operator với caching để giảm external API calls.

---

## 7. Security & Reliability Considerations

### Security Checklist

```
1. ✅ Enable encryption at rest (EncryptionConfiguration)
2. ✅ RBAC: least privilege cho secret access
3. ✅ Audit logging cho secret reads
4. ✅ Không log environment variables
5. ✅ Volume mount với restrictive permissions
6. ✅ Rotation plan cho tất cả credentials
7. ✅ Secret scanning trong CI/CD pipeline
8. ✅ Không commit secrets vào git
```

### Rotation Strategy

```
┌─────────────────────────────────────────────────┐
│              Secret Rotation Flow                │
│                                                   │
│  1. Tạo secret mới (version N+1)                │
│  2. Update pod để đọc secret mới                 │
│  3. Verify app hoạt động với secret mới          │
│  4. Revoke secret cũ (version N)                 │
│  5. Monitor cho errors                           │
│                                                   │
│  ⚠️ Cần dual-read period:                        │
│     App chấp nhận CẢ secret cũ VÀ mới           │
│     trong thời gian chuyển đổi                    │
└─────────────────────────────────────────────────┘
```

---

## 8. Hands-on Example

### Chuẩn bị

```bash
# Dùng cluster kind hiện có
kind create cluster --name devops-lab 2>/dev/null || echo "Cluster exists"
```

### 8.1 Tạo ConfigMap và Secret

```yaml
# file: app-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: webapp-config
data:
  APP_ENV: "production"
  LOG_LEVEL: "info"
  DB_HOST: "postgres-svc"
  DB_PORT: "5432"
  MAX_CONNECTIONS: "100"
  app.properties: |
    server.port=8080
    server.host=0.0.0.0
    cache.ttl=300
    feature.dark-mode=true
```

```bash
# Tạo Secret bằng kubectl (không cần YAML file)
kubectl create secret generic webapp-secrets \
  --from-literal=DB_PASSWORD='S3cureP@ss!' \
  --from-literal=API_KEY='sk-abc123xyz789' \
  --from-literal=JWT_SECRET='my-jwt-secret-key-very-long'

# Apply ConfigMap
kubectl apply -f app-config.yaml

# Verify
kubectl get configmap webapp-config
kubectl get secret webapp-secrets

# Xem ConfigMap data
kubectl get configmap webapp-config -o yaml

# Xem Secret data (base64)
kubectl get secret webapp-secrets -o yaml

# Decode secret
kubectl get secret webapp-secrets -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
# Output: S3cureP@ss!
```

### 8.2 Inject qua Environment Variable

```yaml
# file: pod-env.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-env
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo "=== Environment Variables ==="
          echo "APP_ENV=$APP_ENV"
          echo "LOG_LEVEL=$LOG_LEVEL"
          echo "DB_HOST=$DB_HOST"
          echo "DB_PORT=$DB_PORT"
          echo "DB_PASSWORD length: $(echo -n $DB_PASSWORD | wc -c) chars"
          echo ""
          echo "=== All env from ConfigMap ==="
          env | grep -E "^(APP_|LOG_|DB_|MAX_)" | sort
          sleep 3600
      envFrom:
        - configMapRef:
            name: webapp-config
      env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: webapp-secrets
              key: DB_PASSWORD
      resources:
        requests:
          cpu: 25m
          memory: 32Mi
        limits:
          cpu: 50m
          memory: 64Mi
```

```bash
kubectl apply -f pod-env.yaml
kubectl wait --for=condition=Ready pod/app-with-env --timeout=30s
kubectl logs app-with-env

# Expected output:
# === Environment Variables ===
# APP_ENV=production
# LOG_LEVEL=info
# DB_HOST=postgres-svc
# DB_PORT=5432
# DB_PASSWORD length: 11 chars
```

### 8.3 Inject qua Volume Mount

```yaml
# file: pod-mount.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-mount
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo "=== Config Files ==="
          ls -la /config/
          echo ""
          echo "=== app.properties ==="
          cat /config/app.properties
          echo ""
          echo "=== Secret Files ==="
          ls -la /secrets/
          echo ""
          echo "=== DB_PASSWORD (first 3 chars) ==="
          cut -c1-3 /secrets/DB_PASSWORD
          echo "***"
          sleep 3600
      volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        - name: secrets
          mountPath: /secrets
          readOnly: true
      resources:
        requests:
          cpu: 25m
          memory: 32Mi
        limits:
          cpu: 50m
          memory: 64Mi
  volumes:
    - name: config
      configMap:
        name: webapp-config
    - name: secrets
      secret:
        secretName: webapp-secrets
        defaultMode: 0400
```

```bash
kubectl apply -f pod-mount.yaml
kubectl wait --for=condition=Ready pod/app-with-mount --timeout=30s
kubectl logs app-with-mount

# Expected:
# Config files dưới /config/ chứa mỗi key là 1 file
# Secret files dưới /secrets/ với permission 0400
```

### 8.4 So sánh Update Behavior

```bash
# Update ConfigMap
kubectl patch configmap webapp-config -p '{"data":{"LOG_LEVEL":"debug"}}'

# Với env var (pod-env): KHÔNG update
kubectl exec app-with-env -- sh -c 'echo LOG_LEVEL=$LOG_LEVEL'
# Output: LOG_LEVEL=info  ← VẪN LÀ GIÁ TRỊ CŨ

# Với volume mount (pod-mount): TỰ ĐỘNG update sau ~1-2 phút
sleep 90
kubectl exec app-with-mount -- cat /config/LOG_LEVEL
# Output: debug  ← ĐÃ CẬP NHẬT
```

### Cleanup

```bash
kubectl delete pod app-with-env app-with-mount
kubectl delete configmap webapp-config
kubectl delete secret webapp-secrets
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Secret không update trong env var

**Triệu chứng**: Đã update Secret nhưng app vẫn dùng giá trị cũ.

**Root cause**: Environment variables được set lúc pod start và **không bao giờ tự update**.

**Fix**: Restart pod (`kubectl rollout restart deployment/<name>`) hoặc dùng volume mount.

### Pitfall 2: Base64 encoding sai

```bash
# SAI: echo thêm newline
echo "password" | base64
# cGFzc3dvcmQK  ← có \n ở cuối!

# ĐÚNG: echo -n (no newline)
echo -n "password" | base64
# cGFzc3dvcmQ=
```

### Pitfall 3: Mount path override

**Triệu chứng**: Sau khi mount ConfigMap, các files khác trong thư mục biến mất.

**Root cause**: Volume mount **ghi đè toàn bộ directory**.

**Fix**: Dùng `subPath` để mount từng file cụ thể:

```yaml
volumeMounts:
  - name: config
    mountPath: /etc/app/config.yaml
    subPath: config.yaml          # Chỉ mount file này
```

> ⚠️ **subPath không auto-update** khi ConfigMap thay đổi. Trade-off: giữ files khác vs auto-update.

### Pitfall 4: Secret bị log

**Triệu chứng**: Secret xuất hiện trong application logs hoặc `kubectl describe pod`.

**Debug**:
```bash
# Kiểm tra env vars visible qua describe
kubectl describe pod <name> | grep -A 5 "Environment"

# Kiểm tra app không log secrets
kubectl logs <pod> | grep -i "password\|secret\|key\|token"
```

**Fix**: Dùng volume mount thay vì env var cho secrets. Configure app để không log sensitive fields.

### Case Study: Secret leak qua environment variable in crash dump

**Bối cảnh**: Production app crash, crash dump được upload lên error tracking service (Sentry). Crash dump chứa process environment → tất cả secrets bị expose.

**Root cause**: Secrets được inject qua env vars, crash dump include full process environment.

**Fix**:
1. Chuyển secrets sang volume mount.
2. Configure crash dump tool để strip environment variables.
3. Add secret scanning cho error tracking pipeline.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 13: Ingress, Gateway API)
- TLS certificate lưu trong Secret → đã dùng `kubectl create secret tls`.
- Ingress annotations là config → bài này giải thích config management toàn diện.

### Bài sau (Day 15: Storage — PV, PVC, StorageClass, CSI)
- ConfigMap/Secret mount dưới dạng volume → Day 15 deep dive vào persistent storage.
- Secret volume là tmpfs (in-memory) → Day 15 bàn về block/file storage trên disk.

---

## 11. Tài liệu tham khảo

### Must-read
- [ConfigMap — Official Docs](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Secrets — Official Docs](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Encrypting Confidential Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)

### Nice-to-have
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [SOPS — Mozilla](https://github.com/getsops/sops)

### Deep-dive
- [HashiCorp Vault on Kubernetes](https://developer.hashicorp.com/vault/docs/platform/k8s)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
- "Kubernetes in Action" — Chapter 7: ConfigMaps and Secrets

