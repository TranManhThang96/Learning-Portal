# Bài thực hành - Day 13: ConfigMap, Secret và secret management thực tế

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`.
- Đã quen `kubectl describe`, `kubectl logs`, `kubectl exec`.

## Lab Scenario

Bạn triển khai một app giả lập đọc config từ `ConfigMap` và credential từ `Secret`. Sau đó bạn cập nhật config, quan sát sự khác biệt giữa env và mounted file, inject lỗi thiếu key để debug `CreateContainerConfigError`, và tạo manifest mẫu cho `ExternalSecret`.

Core path khoảng 100-110 phút: Task 1-4, bỏ qua ExternalSecret stretch, rồi Task 5 và cleanup. `ExternalSecret` là Stretch Goal vì cần operator/CRD riêng nếu muốn apply thật.

## Task 1: Tạo namespace, ConfigMap và Secret (15 phút)

### Mục tiêu

Tạo object cấu hình runtime cho app.

### Các bước thực hiện

```bash
kubectl create namespace day13
kubectl config set-context --current --namespace=day13
```

Tạo file `app-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_MODE: "lab"
  LOG_LEVEL: "debug"
  settings.ini: |
    timeout_seconds=5
    feature_flag=true
```

Tạo file `app-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
type: Opaque
stringData:
  DB_USERNAME: app
  DB_PASSWORD: lab-password
```

Apply:

```bash
kubectl apply -f app-config.yaml
kubectl apply -f app-secret.yaml
kubectl get configmap,secret
kubectl describe configmap app-config
kubectl describe secret app-secret
```

### Expected output

- `app-config` có 3 keys.
- `app-secret` có 2 keys, nhưng `kubectl describe` không in giá trị secret.

## Task 2: Deploy app đọc env và mounted file (25 phút)

### Mục tiêu

Inject `ConfigMap` và `Secret` vào Pod theo 2 cách: env và volume.

### Các bước thực hiện

Tạo file `config-demo.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: config-demo
  labels:
    app: config-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: config-demo
  template:
    metadata:
      labels:
        app: config-demo
    spec:
      containers:
      - name: app
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          while true; do
            echo "pod=$HOSTNAME mode=$APP_MODE user=$DB_USERNAME password_length=${#DB_PASSWORD}"
            echo "--- settings.ini ---"
            cat /etc/app/config/settings.ini
            sleep 20
          done
        env:
        - name: APP_MODE
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: APP_MODE
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: app-secret
              key: DB_USERNAME
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secret
              key: DB_PASSWORD
        volumeMounts:
        - name: app-config-volume
          mountPath: /etc/app/config
          readOnly: true
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            cpu: 100m
            memory: 64Mi
      volumes:
      - name: app-config-volume
        configMap:
          name: app-config
          items:
          - key: settings.ini
            path: settings.ini
```

Apply và quan sát:

```bash
kubectl apply -f config-demo.yaml
kubectl rollout status deployment/config-demo
kubectl get pods -l app=config-demo
kubectl logs -l app=config-demo --tail=20
```

### Verification

Vào một Pod:

```bash
kubectl exec -it deploy/config-demo -- sh
env | sort | grep -E 'APP_MODE|DB_'
cat /etc/app/config/settings.ini
exit
```

Nếu shell trong container không có `grep`, dùng:

```bash
kubectl exec -it deploy/config-demo -- printenv APP_MODE
kubectl exec -it deploy/config-demo -- printenv DB_USERNAME
```

### Expected output

- Log in ra `mode=lab`.
- Log chỉ in độ dài password, không in password.
- File `/etc/app/config/settings.ini` tồn tại trong container.

## Task 3: Cập nhật ConfigMap và quan sát update behavior (20 phút)

### Mục tiêu

Hiểu env không tự đổi, mounted file có thể đổi nhưng app phải reload hoặc đọc lại file.

### Các bước thực hiện

Sửa `app-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_MODE: "production-like"
  LOG_LEVEL: "info"
  settings.ini: |
    timeout_seconds=15
    feature_flag=false
```

Apply:

```bash
kubectl apply -f app-config.yaml
kubectl get configmap app-config -o yaml
kubectl logs -l app=config-demo --tail=30
```

Chờ 1-2 phút rồi kiểm tra file trong Pod:

```bash
kubectl exec -it deploy/config-demo -- cat /etc/app/config/settings.ini
kubectl exec -it deploy/config-demo -- printenv APP_MODE
```

Restart Deployment:

```bash
kubectl rollout restart deployment/config-demo
kubectl rollout status deployment/config-demo
kubectl logs -l app=config-demo --tail=20
```

### Expected output

- Mounted file eventually đổi sang `timeout_seconds=15`.
- `APP_MODE` trong env chỉ đổi sau khi Pod restart.
- Nếu config được mount qua `subPath`, file sẽ không nhận update tự động; đó là lý do `subPath` phải đi kèm rollout restart hoặc object name versioned.

### Troubleshooting

Nếu file chưa đổi ngay, không vội kết luận lỗi. Kubelet cập nhật mounted config không đồng bộ tức thì. Kiểm tra lại sau một khoảng ngắn hoặc restart Pod để so sánh.

## Task 4: Inject lỗi thiếu Secret key và debug (25 phút)

### Mục tiêu

Tạo lỗi `CreateContainerConfigError` do tham chiếu sai key.

### Lỗi cần tạo

Patch Deployment để đọc key không tồn tại:

```bash
kubectl patch deployment config-demo --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/key","value":"DB_PASSWORD_WRONG"}]'
kubectl rollout status deployment/config-demo --timeout=45s
```

Nếu rollout timeout, điều tra:

```bash
kubectl get pods
kubectl describe pod <new-pod-name>
kubectl get secret app-secret -o yaml
kubectl get events --sort-by=.lastTimestamp
```

### Symptom

- Pod mới không chạy.
- `describe pod` báo key không tồn tại trong Secret.

### Cách fix

```bash
kubectl patch deployment config-demo --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/key","value":"DB_PASSWORD"}]'
kubectl rollout status deployment/config-demo
```

### Production note

Trong production, đừng chỉ sửa key rồi rollout. Cần kiểm tra release nào thay đổi contract giữa app và secret, secret có bị rotate thiếu key không, và có service nào dùng chung secret bị ảnh hưởng không.

## Stretch Goal: Tạo manifest mẫu ExternalSecret không apply (20 phút)

### Mục tiêu

Hiểu mô hình external secret mà không cần cài operator trong lab hôm nay.

### Các bước thực hiện

Tạo file `external-secret-example.yaml`:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: app-db
  namespace: day13
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: team-secret-store
    kind: SecretStore
  target:
    name: app-secret
    creationPolicy: Owner
  data:
  - secretKey: DB_PASSWORD
    remoteRef:
      key: production/app/db-password
```

Không apply nếu cluster chưa cài External Secrets Operator. Chỉ đọc object model:

```bash
kubectl api-resources | grep -i externalsecret
kubectl explain externalsecret.spec
```

PowerShell fallback:

```powershell
kubectl api-resources | Select-String -Pattern externalsecret
kubectl explain externalsecret.spec
```

### Expected output

- Nếu chưa cài operator, không thấy resource `externalsecrets`.
- Bạn vẫn hiểu `ExternalSecret` tạo ra target Kubernetes `Secret` để Pod consume.
- Manifest ví dụ dùng `external-secrets.io/v1`; nếu CRD trong cluster dùng `v1beta1` hoặc version khác, chỉnh theo `kubectl explain` thay vì apply mù.

## Task 5: Kiểm tra RBAC đọc Secret (10 phút)

### Mục tiêu

Nhìn secret từ góc độ quyền truy cập.

### Các bước thực hiện

```bash
kubectl auth can-i get secrets
kubectl auth can-i list secrets
kubectl auth can-i get secret app-secret
```

Nếu bạn có quyền đọc, thử decode trong lab:

```bash
kubectl get secret app-secret -o jsonpath='{.data.DB_PASSWORD}'
```

Decode giá trị bằng công cụ phù hợp với shell của bạn:

```bash
# Linux/macOS/WSL
kubectl get secret app-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
```

```powershell
# PowerShell
$encoded = kubectl get secret app-secret -o jsonpath='{.data.DB_PASSWORD}'
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
```

Điểm cần nhớ: ai có quyền đọc Secret object có thể lấy được dữ liệu.

## Cleanup

```bash
kubectl delete namespace day13
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Đưa password vào `ConfigMap`.
- Commit `Secret` plain text vào Git.
- Dùng `envFrom` làm app nhận quá nhiều secret không cần thiết.
- Cập nhật `ConfigMap` rồi chờ env tự đổi.
- Log toàn bộ env trong app startup.
- Không có rotation plan cho secret.
- Không bật encryption at rest trong production.

## Stretch Goals

- Đặt `immutable: true` cho `app-config`, thử apply thay đổi và quan sát lỗi.
- Mount một key bằng `subPath`, cập nhật `ConfigMap`, rồi xác nhận file không đổi cho đến khi Pod restart.
- Tạo Secret type `kubernetes.io/tls` bằng certificate self-signed.
- Cài External Secrets Operator trong cluster lab riêng và thử provider fake/webhook nếu bạn muốn đào sâu.
- Viết checklist rotation cho `DB_PASSWORD` không downtime.
