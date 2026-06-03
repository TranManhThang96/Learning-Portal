# Bài thực hành - Day 09: ReplicaSet và Deployment

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Đã nắm readiness probe từ Day 08.

## Lab Scenario

Bạn triển khai một service stateless bằng Deployment, quan sát ReplicaSet được tạo, thực hiện rolling update, cố tình rollout image lỗi, rollback, sau đó thử pause/resume để gom thay đổi.

## Core Path trong 2 giờ

Core path là Task 1-5, khoảng 100-105 phút. Readiness-fail rollout và pause/resume là `Stretch Goals` vì đã có lỗi image trong core và hai phần đó dễ làm lab kéo dài.

## Task 1: Tạo Deployment có rolling update strategy (20 phút)

### Mục tiêu

Tạo Deployment đúng pattern production cơ bản.

### Các bước thực hiện

```bash
kubectl create namespace day09
kubectl config set-context --current --namespace=day09
```

Tạo file `web-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
  annotations:
    kubernetes.io/change-cause: "initial nginx 1.27"
spec:
  replicas: 3
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: web
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  minReadySeconds: 5
  progressDeadlineSeconds: 120
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: nginx:1.27
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 250m
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
```

Apply:

```bash
kubectl apply -f web-deployment.yaml
kubectl rollout status deployment/web
kubectl get deploy,rs,pod,svc,endpoints,endpointslice -o wide
kubectl describe deployment web
```

### Expected output

- Deployment `web` có 3/3 available.
- Có một ReplicaSet active.
- Service endpoint có ba Pod IP.

## Task 2: Inspect ReplicaSet ownership và status fields (15 phút)

### Mục tiêu

Hiểu quan hệ Deployment -> ReplicaSet -> Pod.

### Các bước thực hiện

```bash
kubectl get rs --show-labels
kubectl get pods --show-labels
kubectl get pod <pod-name> -o jsonpath='{.metadata.ownerReferences[*].kind}{" "}{.metadata.ownerReferences[*].name}{"\n"}'
kubectl get rs <rs-name> -o jsonpath='{.metadata.ownerReferences[*].kind}{" "}{.metadata.ownerReferences[*].name}{"\n"}'
kubectl get deployment web -o jsonpath='{.status.updatedReplicas}{" updated / "}{.status.availableReplicas}{" available\n"}'
```

### Expected output

- Pod owner là ReplicaSet.
- ReplicaSet owner là Deployment.
- Status phản ánh số replicas updated/available.

### Troubleshooting

- Nếu JSONPath trả rỗng, dùng `kubectl get pod <pod-name> -o yaml` để xem field thật.

## Task 3: Rolling update image và theo dõi ReplicaSet mới (20 phút)

### Mục tiêu

Thấy Deployment tạo revision mới khi Pod template đổi.

### Các bước thực hiện

```bash
kubectl annotate deployment web kubernetes.io/change-cause="update nginx to 1.28" --overwrite
kubectl set image deployment/web web=nginx:1.28
kubectl rollout status deployment/web
kubectl get deploy,rs,pod -o wide
kubectl rollout history deployment/web
```

Trong lúc rollout, nếu muốn quan sát live:

```bash
kubectl get pods -l app=web -w
```

### Expected output

- Có ReplicaSet mới.
- ReplicaSet cũ scale về 0 nhưng vẫn còn để rollback.
- Rollout history có ít nhất hai revision.

### Verification

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sSI http://web.day09.svc.cluster.local
```

## Task 4: Inject rollout lỗi bằng image tag sai (25 phút)

### Mục tiêu

Debug rollout kẹt mà không làm mất toàn bộ service cũ.

### Lỗi cần tạo

```bash
kubectl annotate deployment web kubernetes.io/change-cause="bad image rollout" --overwrite
kubectl set image deployment/web web=nginx:this-tag-does-not-exist
kubectl rollout status deployment/web --timeout=60s
```

Điều tra:

```bash
kubectl get deploy,rs,pod -o wide
kubectl describe deployment web
kubectl describe pod -l app=web
kubectl get events --sort-by=.lastTimestamp
kubectl rollout history deployment/web
```

### Symptom

- Rollout không hoàn tất.
- Pod mới vào `ImagePullBackOff`.
- Pod version cũ vẫn phục vụ vì `maxUnavailable=0`.

### Cách fix bằng rollback

```bash
kubectl rollout undo deployment/web
kubectl rollout status deployment/web
kubectl get deploy,rs,pod -o wide
```

### Verification

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sSI http://web.day09.svc.cluster.local
```

## Task 5: So sánh rolling update strategy và capacity budget (20 phút)

### Mục tiêu

Tính tác động của `maxSurge`/`maxUnavailable` lên capacity và quan sát rollout với strategy ít cần headroom hơn.

### Các bước thực hiện

```bash
kubectl get deployment web -o jsonpath='{.spec.replicas}{" replicas, maxSurge="}{.spec.strategy.rollingUpdate.maxSurge}{", maxUnavailable="}{.spec.strategy.rollingUpdate.maxUnavailable}{"\n"}'
kubectl get pod -l app=web -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory
```

Với manifest hiện tại:

```text
replicas = 3
request per Pod = 50m CPU, 64Mi memory
maxSurge = 1
peak Pods khi rollout = 4
peak request = 200m CPU, 256Mi memory
min available = 3
```

Đổi sang strategy không tạo Pod vượt replicas nhưng chấp nhận giảm capacity tạm thời:

```bash
kubectl patch deployment web --type=merge -p '{"spec":{"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxSurge":0,"maxUnavailable":1}}}}'
kubectl annotate deployment web kubernetes.io/change-cause="compare maxUnavailable 1 strategy" --overwrite
kubectl set image deployment/web web=nginx:1.27
kubectl rollout status deployment/web
kubectl get deploy,rs,pod -o wide
```

Khôi phục strategy an toàn hơn cho service quan trọng:

```bash
kubectl patch deployment web --type=merge -p '{"spec":{"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxSurge":1,"maxUnavailable":0}}}}'
```

### Expected output

- Với `maxSurge=0,maxUnavailable=1`, rollout không cần Pod thứ 4.
- Trong lúc rollout, available replicas có thể giảm tạm thời còn 2/3.
- Strategy được restore về `maxSurge=1,maxUnavailable=0` sau task.

### Troubleshooting

- Nếu rollout kẹt `Pending`, kiểm tra resource requests và node allocatable.
- Nếu shell quote lỗi với JSON patch, dùng `--patch-file strategy.json`.

## Cleanup

```bash
kubectl delete namespace day09
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Quản lý ReplicaSet trực tiếp thay vì Deployment.
- Dùng image tag `latest`, rollback không predictable.
- Bỏ readiness probe làm rolling update route traffic quá sớm.
- Đặt `maxSurge` cao trong cluster lab thiếu capacity.
- Rollback bằng `kubectl` nhưng không sửa Git/Helm values trong production.

## Stretch Goals

Nếu muốn làm stretch, thực hiện trước Cleanup hoặc tạo lại namespace `day09`.

### Stretch 1: Inject readiness rollout lỗi (20 phút)

Mục tiêu: thấy Deployment kẹt khi Pod chạy nhưng không available.

```bash
kubectl patch deployment web --type='json' -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/not-ready"}]'
kubectl rollout status deployment/web --timeout=60s
kubectl get pods -l app=web
kubectl describe deployment web
kubectl get endpoints,endpointslice
```

Fix:

```bash
kubectl patch deployment web --type='json' -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/"}]'
kubectl rollout status deployment/web
```

### Stretch 2: Pause/resume để gom thay đổi (20 phút)

```bash
kubectl rollout pause deployment/web
kubectl set image deployment/web web=nginx:1.28
kubectl set resources deployment/web -c=web --requests=cpu=75m,memory=80Mi --limits=cpu=300m,memory=160Mi
kubectl get deployment web -o jsonpath='{.spec.paused}{"\n"}'
kubectl rollout history deployment/web
kubectl rollout resume deployment/web
kubectl rollout status deployment/web
kubectl rollout history deployment/web
```

Nếu quên `resume`, Deployment không rollout các thay đổi mới.

- Đổi `maxUnavailable` từ `0` sang `1`, rollout lại và so sánh availability.
- Set `progressDeadlineSeconds` thấp để thấy condition `ProgressDeadlineExceeded` nhanh hơn.
- Dùng `kubectl diff -f web-deployment.yaml` trước khi apply.
- Dùng image digest thay vì tag nếu bạn có registry/image phù hợp.
