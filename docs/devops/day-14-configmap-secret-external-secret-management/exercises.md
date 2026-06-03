# Day 14: Bài tập — ConfigMap, Secret & External Secret Management

---

## Bài 1: Easy — ConfigMap và Secret cơ bản

### Context
Bạn cần deploy một application với configuration từ ConfigMap và credentials từ Secret, sử dụng cả 2 phương pháp: environment variable và volume mount.

### Yêu cầu
1. Tạo ConfigMap `myapp-config` với các giá trị:
   - `APP_NAME`: "MyApp"
   - `APP_ENV`: "staging"
   - `LOG_LEVEL`: "debug"
   - `MAX_RETRIES`: "3"
2. Tạo Secret `myapp-secrets` với:
   - `DB_PASSWORD`: "super-secret-123"
   - `REDIS_PASSWORD`: "redis-pass-456"
3. Tạo Pod `myapp-env` inject ConfigMap và Secret qua environment variables.
4. Tạo Pod `myapp-mount` inject ConfigMap và Secret qua volume mount.
5. Verify giá trị trong cả 2 pods.
6. Update ConfigMap `LOG_LEVEL` thành "info" và quan sát sự khác biệt giữa env var và volume mount.

### Expected Outcome
- Pod `myapp-env`: env vars có đúng giá trị, KHÔNG update khi ConfigMap thay đổi.
- Pod `myapp-mount`: files có đúng giá trị, TỰ ĐỘNG update sau 1-2 phút.

### Hints
- Dùng `envFrom` để import tất cả keys từ ConfigMap.
- Dùng `valueFrom.secretKeyRef` cho từng secret key.
- Volume mount: `defaultMode: 0400` cho secrets.
- Chờ 90 giây sau khi update ConfigMap để volume mount sync.

### Acceptance Criteria
- [ ] ConfigMap và Secret tạo thành công
- [ ] Pod env var đọc đúng giá trị
- [ ] Pod volume mount đọc đúng giá trị
- [ ] Update behavior khác nhau giữa 2 phương pháp được verify

### Bonus Challenge
- Dùng `subPath` mount để mount chỉ 1 file từ ConfigMap vào existing directory.
- So sánh: subPath có auto-update không? (Spoiler: không)

<details>
<summary>Solution</summary>

```yaml
# myapp-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
data:
  APP_NAME: "MyApp"
  APP_ENV: "staging"
  LOG_LEVEL: "debug"
  MAX_RETRIES: "3"
---
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secrets
type: Opaque
stringData:
  DB_PASSWORD: "super-secret-123"
  REDIS_PASSWORD: "redis-pass-456"
---
# Pod with env vars
apiVersion: v1
kind: Pod
metadata:
  name: myapp-env
spec:
  containers:
    - name: app
      image: busybox:1.36
      command: ["sh", "-c", "env | grep -E '^(APP_|LOG_|MAX_|DB_|REDIS_)' | sort && sleep 3600"]
      envFrom:
        - configMapRef:
            name: myapp-config
      env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: myapp-secrets
              key: DB_PASSWORD
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: myapp-secrets
              key: REDIS_PASSWORD
      resources:
        requests:
          cpu: 25m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 32Mi
---
# Pod with volume mounts
apiVersion: v1
kind: Pod
metadata:
  name: myapp-mount
spec:
  containers:
    - name: app
      image: busybox:1.36
      command:
        - sh
        - -c
        - |
          echo "=== Config ==="
          for f in /config/*; do echo "$(basename $f)=$(cat $f)"; done
          echo "=== Secrets ==="
          for f in /secrets/*; do echo "$(basename $f)=$(cat $f | head -c3)***"; done
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
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 32Mi
  volumes:
    - name: config
      configMap:
        name: myapp-config
    - name: secrets
      secret:
        secretName: myapp-secrets
        defaultMode: 0400
```

```bash
kubectl apply -f myapp-config.yaml
kubectl wait --for=condition=Ready pod/myapp-env pod/myapp-mount --timeout=30s

# Check env var pod
kubectl logs myapp-env

# Check mount pod
kubectl logs myapp-mount

# Update ConfigMap
kubectl patch configmap myapp-config -p '{"data":{"LOG_LEVEL":"info"}}'

# Check env var - NOT updated
kubectl exec myapp-env -- sh -c 'echo $LOG_LEVEL'  # Still "debug"

# Wait ~90s then check mount - UPDATED
sleep 90
kubectl exec myapp-mount -- cat /config/LOG_LEVEL  # Now "info"

# Cleanup
kubectl delete pod myapp-env myapp-mount
kubectl delete configmap myapp-config
kubectl delete secret myapp-secrets
```

</details>

---

## Bài 2: Medium — Secret Management với multiple environments

### Context
Bạn cần thiết kế configuration strategy cho một application chạy ở 3 environments: dev, staging, production. Mỗi environment có config và secret riêng.

### Yêu cầu
1. Tạo 3 namespaces: `dev`, `staging`, `prod`.
2. Trong mỗi namespace, tạo:
   - ConfigMap `app-config` với giá trị khác nhau (LOG_LEVEL, DB_HOST, FEATURE_FLAGS).
   - Secret `app-secrets` với credentials khác nhau (DB_PASSWORD).
3. Deploy cùng 1 Deployment YAML cho cả 3 environments (dùng `kubectl apply -n <namespace>`).
4. Verify mỗi environment đọc đúng config/secret riêng.
5. Mô phỏng secret rotation:
   - Tạo Secret mới `app-secrets-v2` với password mới.
   - Update Deployment để dùng secret mới.
   - Verify app dùng password mới.
   - Delete secret cũ.
6. Document secret rotation process.

### Expected Outcome
- 3 environments hoạt động độc lập với config riêng.
- Secret rotation không gây downtime.
- Rotation process documented.

### Hints
- ConfigMap/Secret namespace-scoped → tên giống nhau ở namespace khác nhau không conflict.
- Dùng `kubectl rollout restart` để force pod re-read secrets khi dùng env var.
- Volume mount tự update nhưng app có thể cần reload.

### Acceptance Criteria
- [ ] 3 namespaces với config riêng
- [ ] Cùng Deployment YAML chạy được ở cả 3 environments
- [ ] Secret rotation thành công không downtime
- [ ] Rotation process documented

### Bonus Challenge
- Dùng Kustomize overlay để quản lý config per environment (preview Day 16).
- Tạo script automating secret rotation.

<details>
<summary>Solution</summary>

```bash
# Create namespaces
kubectl create namespace dev
kubectl create namespace staging
kubectl create namespace prod
```

```yaml
# base-deployment.yaml (shared across environments)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: app
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              while true; do
                echo "[$(date)] ENV=$APP_ENV LOG=$LOG_LEVEL DB=$DB_HOST PASS_LEN=$(echo -n $DB_PASSWORD | wc -c)"
                sleep 30
              done
          envFrom:
            - configMapRef:
                name: app-config
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: DB_PASSWORD
          resources:
            requests:
              cpu: 25m
              memory: 16Mi
            limits:
              cpu: 50m
              memory: 32Mi
```

```bash
# Dev environment
kubectl create configmap app-config -n dev \
  --from-literal=APP_ENV=development \
  --from-literal=LOG_LEVEL=debug \
  --from-literal=DB_HOST=localhost
kubectl create secret generic app-secrets -n dev \
  --from-literal=DB_PASSWORD=dev-pass-123

# Staging environment
kubectl create configmap app-config -n staging \
  --from-literal=APP_ENV=staging \
  --from-literal=LOG_LEVEL=info \
  --from-literal=DB_HOST=staging-db.internal
kubectl create secret generic app-secrets -n staging \
  --from-literal=DB_PASSWORD=staging-pass-456

# Production environment
kubectl create configmap app-config -n prod \
  --from-literal=APP_ENV=production \
  --from-literal=LOG_LEVEL=warn \
  --from-literal=DB_HOST=prod-db.internal
kubectl create secret generic app-secrets -n prod \
  --from-literal=DB_PASSWORD=prod-pass-789-secure

# Deploy to all environments
kubectl apply -f base-deployment.yaml -n dev
kubectl apply -f base-deployment.yaml -n staging
kubectl apply -f base-deployment.yaml -n prod

# Verify each environment
for ns in dev staging prod; do
  echo "=== $ns ==="
  kubectl logs -n $ns -l app=myapp --tail=1
done

# === Secret Rotation ===
# Step 1: Create new secret
kubectl create secret generic app-secrets-v2 -n prod \
  --from-literal=DB_PASSWORD=new-prod-pass-rotated

# Step 2: Update deployment to use new secret
kubectl set env deployment/myapp -n prod --from=secret/app-secrets-v2

# Step 3: Verify
kubectl rollout status deployment/myapp -n prod
kubectl logs -n prod -l app=myapp --tail=1

# Step 4: Delete old secret
kubectl delete secret app-secrets -n prod

# Cleanup
kubectl delete namespace dev staging prod
```

</details>

---

## Bài 3: Hard — Production Secret Management Architecture

### Context
Bạn là DevOps engineer cần thiết kế và implement secret management strategy cho một microservice platform production-grade. Yêu cầu:
- Secrets không được commit vào git dưới dạng plain text.
- Có audit trail cho mọi secret access.
- Có rotation strategy.
- Có encryption at rest.

### Yêu cầu
1. Deploy một application stack gồm 2 services:
   - `api-service`: cần DB_PASSWORD, JWT_SECRET, API_KEY.
   - `worker-service`: cần DB_PASSWORD, QUEUE_PASSWORD.
2. Implement các layers security:
   - RBAC: tạo ServiceAccount riêng cho mỗi service, chỉ access secret cần thiết.
   - Volume mount với `defaultMode: 0400`.
   - Security context: `readOnlyRootFilesystem: true`, non-root user.
3. Tạo checklist secret management cho production.
4. Document decision record: tại sao chọn native Secret + RBAC thay vì Vault cho scenario này.
5. Mô phỏng secret leak scenario và incident response:
   - Phát hiện secret bị leak.
   - Rotate secret ngay lập tức.
   - Verify services dùng secret mới.
   - Document timeline.

### Expected Outcome
- 2 services chạy với secrets riêng, RBAC isolated.
- RBAC verify: `api-service` SA không đọc được `worker-secrets`.
- Secret rotation hoàn thành không downtime.
- Checklist và decision record viết xong.

### Hints
- Tạo Role cho phép `get` secret resource cụ thể, không phải tất cả secrets.
- Dùng `kubectl auth can-i --as=system:serviceaccount:<ns>:<sa>` để verify RBAC.
- `readOnlyRootFilesystem` cần `emptyDir` cho tmp nếu app cần write temp files.

### Acceptance Criteria
- [ ] 2 services deploy với separate secrets
- [ ] RBAC isolated — cross-access bị denied
- [ ] Security context non-root, read-only root
- [ ] Secret rotation procedure works without downtime
- [ ] Production checklist complete
- [ ] Decision record documented

### Bonus Challenge
- Install Sealed Secrets controller và encrypt secrets cho git.
- Tạo CronJob auto-rotation: tạo secret mới, update deployment, delete secret cũ.
- Implement secret scanning: tạo Job chạy `trufflehog` hoặc `gitleaks` trên repo.

<details>
<summary>Solution</summary>

```yaml
# production-secrets.yaml
# --- Service Accounts ---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-service-sa
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: worker-service-sa
automountServiceAccountToken: false
---
# --- Secrets ---
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
type: Opaque
stringData:
  DB_PASSWORD: "api-db-pass-secure"
  JWT_SECRET: "jwt-secret-key-256bit-long"
  API_KEY: "sk-api-key-production"
---
apiVersion: v1
kind: Secret
metadata:
  name: worker-secrets
type: Opaque
stringData:
  DB_PASSWORD: "worker-db-pass-secure"
  QUEUE_PASSWORD: "queue-pass-production"
---
# --- RBAC ---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-secret-reader
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["api-secrets"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: worker-secret-reader
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["worker-secrets"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-secret-binding
subjects:
  - kind: ServiceAccount
    name: api-service-sa
roleRef:
  kind: Role
  name: api-secret-reader
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: worker-secret-binding
subjects:
  - kind: ServiceAccount
    name: worker-service-sa
roleRef:
  kind: Role
  name: worker-secret-reader
  apiGroup: rbac.authorization.k8s.io
---
# --- Deployments ---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      serviceAccountName: api-service-sa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: api
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              echo "API Service started"
              echo "Secrets mounted at /secrets"
              ls -la /secrets/
              while true; do
                echo "[$(date)] API running, DB_PASS=$(cat /secrets/DB_PASSWORD | head -c3)***"
                sleep 60
              done
          volumeMounts:
            - name: secrets
              mountPath: /secrets
              readOnly: true
            - name: tmp
              mountPath: /tmp
          securityContext:
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
      volumes:
        - name: secrets
          secret:
            secretName: api-secrets
            defaultMode: 0400
        - name: tmp
          emptyDir: {}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: worker-service
  template:
    metadata:
      labels:
        app: worker-service
    spec:
      serviceAccountName: worker-service-sa
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: worker
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              echo "Worker Service started"
              ls -la /secrets/
              while true; do
                echo "[$(date)] Worker processing, QUEUE=$(cat /secrets/QUEUE_PASSWORD | head -c3)***"
                sleep 60
              done
          volumeMounts:
            - name: secrets
              mountPath: /secrets
              readOnly: true
            - name: tmp
              mountPath: /tmp
          securityContext:
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
      volumes:
        - name: secrets
          secret:
            secretName: worker-secrets
            defaultMode: 0400
        - name: tmp
          emptyDir: {}
```

```bash
# Apply
kubectl apply -f production-secrets.yaml

# Verify RBAC isolation
kubectl auth can-i get secret/api-secrets --as=system:serviceaccount:default:api-service-sa
# Expected: yes

kubectl auth can-i get secret/worker-secrets --as=system:serviceaccount:default:api-service-sa
# Expected: no

kubectl auth can-i get secret/api-secrets --as=system:serviceaccount:default:worker-service-sa
# Expected: no

# Verify services running
kubectl logs -l app=api-service --tail=2
kubectl logs -l app=worker-service --tail=2

# === Secret Rotation Simulation ===
echo "=== INCIDENT: Secret leaked! Starting rotation ==="
echo "$(date): Detected API_KEY exposed in logs"

# Step 1: Create rotated secret
kubectl create secret generic api-secrets-rotated \
  --from-literal=DB_PASSWORD="rotated-db-pass-$(date +%s)" \
  --from-literal=JWT_SECRET="rotated-jwt-secret-$(date +%s)" \
  --from-literal=API_KEY="sk-rotated-$(date +%s)"

# Step 2: Update deployment
kubectl set env deployment/api-service --from=secret/api-secrets-rotated --overwrite=false
kubectl patch deployment api-service -p \
  '{"spec":{"template":{"spec":{"volumes":[{"name":"secrets","secret":{"secretName":"api-secrets-rotated","defaultMode":256}}]}}}}'

# Step 3: Verify rollout
kubectl rollout status deployment/api-service
kubectl logs -l app=api-service --tail=1

# Step 4: Revoke old secret
kubectl delete secret api-secrets
echo "$(date): Old secret deleted, rotation complete"

# Cleanup
kubectl delete -f production-secrets.yaml
kubectl delete secret api-secrets-rotated 2>/dev/null
```

</details>

