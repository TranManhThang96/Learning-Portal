# Bài thực hành - Day 10: StatefulSet

## Prerequisites

- K3s cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster có `StorageClass` mặc định. Với K3s thường là `local-path`.
- Đã hiểu `Deployment` và readiness probe từ Day 09.

## Lab Scenario

Bạn triển khai một web cluster giả lập workload stateful. Mỗi Pod có identity riêng, DNS riêng và PVC riêng. Bạn sẽ ghi dữ liệu khác nhau vào từng replica, scale down/up để kiểm tra PVC retention, thêm `PodDisruptionBudget`/anti-affinity cơ bản và tạo lỗi storage để debug. Partitioned rollout được để trong `Stretch Goals`.

## Core Path trong 2 giờ

Core path là Task 1-6, khoảng 110-115 phút. Partitioned rollout, `OnDelete`, hard anti-affinity và benchmark PVC nằm ở `Stretch Goals`.

## Task 1: Kiểm tra StorageClass và tạo namespace (10 phút)

### Mục tiêu

Xác nhận cluster có dynamic provisioning trước khi tạo PVC.

### Các bước thực hiện

```bash
kubectl get storageclass
kubectl create namespace day10
kubectl config set-context --current --namespace=day10
```

Nếu không có StorageClass mặc định, ghi lại tên StorageClass bạn muốn dùng để thêm vào manifest:

```yaml
storageClassName: <storage-class-name>
```

### Expected output

- K3s thường có StorageClass `local-path`.
- Namespace `day10` được tạo.

## Task 2: Tạo Headless Service và StatefulSet (25 phút)

### Mục tiêu

Tạo 3 Pod có ordinal, DNS và PVC riêng.

### Các bước thực hiện

Tạo file `web-statefulset.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  labels:
    app: nginx
spec:
  clusterIP: None
  selector:
    app: nginx
  ports:
  - name: web
    port: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: nginx
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  podManagementPolicy: OrderedReady
  updateStrategy:
    type: RollingUpdate
  template:
    metadata:
      labels:
        app: nginx
    spec:
      terminationGracePeriodSeconds: 10
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - name: web
          containerPort: 80
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
        readinessProbe:
          httpGet:
            path: /
            port: web
          periodSeconds: 5
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 250m
            memory: 128Mi
  volumeClaimTemplates:
  - metadata:
      name: www
      labels:
        app: nginx
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

Apply:

```bash
kubectl apply -f web-statefulset.yaml
kubectl rollout status statefulset/web
kubectl get sts,pod,svc,pvc -o wide
kubectl get pv
```

### Expected output

- Pod xuất hiện theo thứ tự `web-0`, `web-1`, `web-2`.
- Có PVC `www-web-0`, `www-web-1`, `www-web-2`.
- Service `nginx` có `CLUSTER-IP` là `None`.

### Troubleshooting

Nếu Pod `Pending`, chạy:

```bash
kubectl describe pod web-0
kubectl describe pvc www-web-0
kubectl get events --sort-by=.lastTimestamp
```

## Task 3: Kiểm tra stable DNS và dữ liệu riêng từng Pod (20 phút)

### Mục tiêu

Chứng minh mỗi ordinal có DNS và volume riêng.

### Các bước thực hiện

Ghi nội dung khác nhau vào từng Pod:

```bash
kubectl exec web-0 -- sh -c 'echo web-0 > /usr/share/nginx/html/index.html'
kubectl exec web-1 -- sh -c 'echo web-1 > /usr/share/nginx/html/index.html'
kubectl exec web-2 -- sh -c 'echo web-2 > /usr/share/nginx/html/index.html'
```

Kiểm tra hostname:

```bash
kubectl exec web-0 -- hostname
kubectl exec web-1 -- hostname
kubectl exec web-2 -- hostname
```

Kiểm tra DNS từng Pod:

```bash
kubectl run dns-debug --rm -it --restart=Never --image=busybox:1.36 --command -- nslookup web-0.nginx.day10.svc.cluster.local
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -s http://web-0.nginx.day10.svc.cluster.local
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -s http://web-1.nginx.day10.svc.cluster.local
```

### Expected output

- `hostname` lần lượt là `web-0`, `web-1`, `web-2`.
- Curl tới `web-0` trả `web-0`; curl tới `web-1` trả `web-1`.

## Task 4: Scale down/up và xác minh PVC retention (20 phút)

### Mục tiêu

Thấy Pod bị xóa nhưng PVC vẫn giữ dữ liệu.

### Các bước thực hiện

```bash
kubectl scale statefulset web --replicas=1
kubectl get pod,pvc -o wide
```

Quan sát:

- `web-2` và `web-1` bị xóa trước.
- PVC `www-web-1` và `www-web-2` vẫn còn.

Scale lại:

```bash
kubectl scale statefulset web --replicas=3
kubectl rollout status statefulset/web
kubectl get pod,pvc -o wide
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -s http://web-2.nginx.day10.svc.cluster.local
```

### Expected output

- `web-2` được tạo lại với cùng tên.
- Dữ liệu `web-2` vẫn còn nếu PVC/PV không bị xóa.

### Troubleshooting

Nếu dữ liệu mất, kiểm tra bạn có xóa PVC/PV không:

```bash
kubectl get pvc,pv
kubectl describe pvc www-web-2
```

## Task 5: Thêm PDB và anti-affinity mềm (20 phút)

### Mục tiêu

Thêm guardrail production tối thiểu: tránh voluntary disruption quá mức và khuyến khích spread replica khi có nhiều node.

### Các bước thực hiện

Tạo file `web-pdb.yaml`:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: nginx
```

Tạo file patch `web-affinity-patch.json`:

```json
{
  "spec": {
    "template": {
      "spec": {
        "affinity": {
          "podAntiAffinity": {
            "preferredDuringSchedulingIgnoredDuringExecution": [
              {
                "weight": 100,
                "podAffinityTerm": {
                  "labelSelector": {
                    "matchLabels": {
                      "app": "nginx"
                    }
                  },
                  "topologyKey": "kubernetes.io/hostname"
                }
              }
            ]
          }
        }
      }
    }
  }
}
```

Apply PDB và patch StatefulSet hiện có:

```bash
kubectl apply -f web-pdb.yaml
kubectl patch statefulset web --type=merge --patch-file web-affinity-patch.json
kubectl rollout status statefulset/web
kubectl get pdb
kubectl describe pdb web-pdb
kubectl get statefulset web -o yaml
```

### Expected output

- `web-pdb` có `minAvailable: 2`.
- StatefulSet template có `preferredDuringSchedulingIgnoredDuringExecution`.
- Trên single-node K3s, anti-affinity mềm không block scheduling; trên multi-node, scheduler sẽ cố spread Pod nếu có tài nguyên.

### Troubleshooting

- Nếu `--patch-file` không được kubectl version của bạn hỗ trợ, dùng `kubectl patch statefulset web --type=merge -p '<json-tren-mot-dong>'` hoặc `kubectl edit statefulset web` trong lab.
- Không dùng hard `requiredDuringSchedulingIgnoredDuringExecution` trong single-node lab vì sẽ làm replica sau bị `Pending`.

## Task 6: Inject lỗi storage và debug (20 phút)

### Mục tiêu

Hiểu lỗi PVC không bind làm Pod `Pending`, không trộn lỗi này với Service identity của StatefulSet chính.

### Lỗi cần tạo

Tạo file `broken-statefulset.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: broken
spec:
  clusterIP: None
  selector:
    app: broken
  ports:
  - name: web
    port: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: broken
spec:
  serviceName: broken
  replicas: 1
  selector:
    matchLabels:
      app: broken
  template:
    metadata:
      labels:
        app: broken
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        volumeMounts:
        - name: data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: data
      labels:
        app: broken
    spec:
      storageClassName: does-not-exist
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

Apply và điều tra:

```bash
kubectl apply -f broken-statefulset.yaml
kubectl get pod,pvc,svc
kubectl describe pod broken-0
kubectl describe pvc data-broken-0
kubectl get events --sort-by=.lastTimestamp
```

### Symptom

- `broken-0` không chạy được.
- PVC `data-broken-0` không bind vì StorageClass không tồn tại.

### Cách fix

Với lab, xóa object lỗi rồi tạo lại với StorageClass đúng:

```bash
kubectl delete statefulset broken
kubectl delete svc broken
kubectl delete pvc data-broken-0
```

Trong production, không xóa PVC chứa data thật nếu chưa backup và chưa hiểu reclaim policy.

## Cleanup

```bash
kubectl delete namespace day10
kubectl config set-context --current --namespace=default
```

## Common Pitfalls

- Quên tạo Headless Service hoặc `serviceName` sai.
- Nghĩ scale down sẽ xóa data, trong khi PVC thường vẫn còn.
- Nghĩ `local-path` là HA storage.
- Readiness probe chỉ kiểm tra process còn sống, không kiểm tra app đã join cluster.
- Dùng hard anti-affinity trong single-node lab làm Pod `Pending`.
- Dùng `Parallel` cho hệ thống cần bootstrap có thứ tự.

## Stretch Goals

Nếu muốn làm stretch, thực hiện trước Cleanup hoặc tạo lại namespace `day10`.

### Stretch 1: Partitioned rolling update (25 phút)

Đặt partition để chỉ update ordinal >= 2:

```bash
kubectl patch statefulset web -p '{"spec":{"updateStrategy":{"type":"RollingUpdate","rollingUpdate":{"partition":2}}}}'
kubectl set image statefulset/web nginx=nginx:1.28
kubectl rollout status statefulset/web
kubectl get pods -o custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image
```

Sau đó rollout toàn bộ:

```bash
kubectl patch statefulset web -p '{"spec":{"updateStrategy":{"type":"RollingUpdate","rollingUpdate":{"partition":0}}}}'
kubectl rollout status statefulset/web
kubectl get pods -o custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image
```

- Khi `partition: 2`, chỉ `web-2` chuyển sang `nginx:1.28`.
- Khi `partition: 0`, các Pod còn lại được update.

### Stretch khác

- Đổi `podManagementPolicy: Parallel` trên một StatefulSet mới và so sánh thời gian scale up.
- Thử `updateStrategy: OnDelete`, đổi image rồi tự xóa từng Pod.
- Benchmark latency đọc/ghi đơn giản trên PVC bằng `fio` nếu cluster lab đủ tài nguyên.
