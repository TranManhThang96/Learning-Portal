# Bài thực hành - Day 32: Kubernetes Debugging Toolkit

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `nginx:1.27`, `busybox:1.36`, `curlimages/curl:8.10.1`, `registry.k8s.io/pause:3.10`.
- Metrics Server nếu muốn thực hành `kubectl top`. Nếu chưa có, ghi lại `Metrics API not available` và bỏ qua kết luận dựa trên resource usage.
- Optional: image `nicolaka/netshoot:latest` nếu muốn thực hành ephemeral container với nhiều network tools.

## Lab Scenario

Bạn sẽ deploy một stack có lỗi cố ý:

- Service selector sai nên endpoints rỗng.
- Một Deployment crash để luyện `logs --previous`.
- Một client Pod để test DNS và HTTP từ trong cluster.
- Một bước preflight `kubectl top` để nối symptom với resource usage.
- Một Pod minimal không có shell để luyện `kubectl debug`.
- Optional Ingress để kiểm tra controller và backend.
- Optional NetworkPolicy để phân biệt timeout do policy với lỗi Service/DNS.

Mục tiêu không phải apply YAML cho chạy ngay, mà là luyện quy trình debug có bằng chứng. Core path khoảng 110-115 phút; Ingress, ephemeral container và NetworkPolicy là nhánh optional nếu môi trường hỗ trợ.

## Core Path (110-115 phút)

- Task 1-7 và Task 11-12 là phần bắt buộc.
- Task 8-10 là nhánh môi trường/optional nếu cluster hỗ trợ image debug, Ingress hoặc NetworkPolicy.

## Task 1: Tạo namespace (5 phút)

```bash
kubectl create namespace day32
kubectl config set-context --current --namespace=day32
```

## Task 2: Preflight resource snapshot bằng `kubectl top` (10 phút)

Chạy:

```bash
kubectl top nodes
kubectl top pods -A --sort-by=cpu
```

Nếu Metrics Server chưa sẵn sàng, bạn có thể thấy lỗi kiểu:

```text
error: Metrics API not available
```

Trong trường hợp đó, ghi vào incident note: "resource usage chưa xác minh được bằng Metrics API". Đừng kết luận CPU/memory không liên quan chỉ vì `kubectl top` chưa chạy được.

### Expected output

- Nếu Metrics Server hoạt động: thấy CPU/memory hiện tại của nodes và Pods.
- Nếu không hoạt động: biết đây là giới hạn observability của cluster, không phải lỗi app.

## Task 3: Deploy app và Service có lỗi selector (20 phút)

Tạo file `broken-service.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        app.kubernetes.io/name: api
        app.kubernetes.io/version: v1
    spec:
      containers:
      - name: nginx
        image: nginx:1.27
        ports:
        - name: http
          containerPort: 80
        readinessProbe:
          httpGet:
            path: /
            port: http
          periodSeconds: 5
        resources:
          requests:
            cpu: 20m
            memory: 64Mi
          limits:
            memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api-wrong
  ports:
  - name: http
    port: 80
    targetPort: http
```

Apply:

```bash
kubectl apply -f broken-service.yaml
kubectl rollout status deploy/api
kubectl get deploy,pod,svc,endpoints,endpointslice -o wide
```

### Expected output

- Pod `api` Running/Ready.
- Service `api` tồn tại.
- Endpoints của Service `api` rỗng vì selector `app=api-wrong`.

## Task 4: Debug Service endpoints rỗng (25 phút)

Chạy theo thứ tự:

```bash
kubectl get pod --show-labels
kubectl describe svc api
kubectl get endpoints api -o wide
kubectl get endpointslice -l kubernetes.io/service-name=api -o wide
```

Trả lời:

- Service đang select label nào?
- Pod thật có label nào?
- Pod Ready chưa?
- Lỗi nằm ở Pod hay Service?

Fix selector:

```bash
kubectl patch svc api -p '{"spec":{"selector":{"app":"api"}}}'
kubectl get endpoints api -o wide
kubectl get endpointslice -l kubernetes.io/service-name=api -o wide
```

### Expected output

- Endpoints hiển thị IP của 2 Pod `api`.
- EndpointSlice có port `80` và endpoint Ready.

## Task 5: Test DNS và HTTP từ client Pod (20 phút)

Tạo client:

```bash
kubectl run client --image=busybox:1.36 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/client --timeout=120s
kubectl label pod client app=client --overwrite
```

Test DNS:

```bash
kubectl exec client -- nslookup kubernetes.default
kubectl exec client -- nslookup api
kubectl exec client -- nslookup api.day32.svc.cluster.local
```

Test HTTP:

```bash
kubectl exec client -- wget -S -O- http://api/
kubectl exec client -- wget -S -O- http://api.day32.svc.cluster.local/
```

### Câu hỏi

- Tên ngắn `api` resolve được vì client ở namespace nào?
- Nếu client ở namespace khác, bạn dùng DNS name nào?
- Nếu DNS resolve nhưng HTTP timeout, bước tiếp theo là gì?

## Task 6: Debug CrashLoopBackOff bằng events và previous logs (25 phút)

Tạo file `crashloop.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crashloop
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crashloop
  template:
    metadata:
      labels:
        app: crashloop
    spec:
      containers:
      - name: app
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "booting app"
          echo "FATAL: missing DATABASE_URL"
          exit 1
```

Apply và debug:

```bash
kubectl apply -f crashloop.yaml
kubectl get pod -l app=crashloop
kubectl describe pod -l app=crashloop
kubectl logs deploy/crashloop
kubectl logs deploy/crashloop --previous
kubectl get events --sort-by=.lastTimestamp
```

### Expected output

- Pod vào `CrashLoopBackOff`.
- Events thể hiện container restart/backoff.
- Logs cho thấy `FATAL: missing DATABASE_URL`.

### Câu hỏi

- Lỗi này thuộc Kubernetes scheduling hay application config?
- Nếu container restart quá nhanh, vì sao `--previous` quan trọng?

## Task 7: Port-forward để tách lỗi Service và app (15 phút)

Port-forward tới Service:

```bash
kubectl port-forward svc/api 8080:80
```

Trong terminal khác:

```bash
curl -i http://localhost:8080/
```

Nếu Service fail nhưng Pod Ready, thử port-forward tới Pod:

```bash
kubectl get pod -l app=api
kubectl port-forward pod/<api-pod-name> 8081:80
curl -i http://localhost:8081/
```

### Câu hỏi

- Service port-forward thành công chứng minh gì?
- Pod port-forward thành công nhưng Service fail thì nghi ngờ lớp nào?

## Task 8: Debug Pod minimal bằng ephemeral container (optional, 25 phút)

Tạo file `minimal.yaml` cho Pod không có shell:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: minimal
  labels:
    app: minimal
spec:
  containers:
  - name: app
    image: registry.k8s.io/pause:3.10
    resources:
      requests:
        cpu: 10m
        memory: 16Mi
      limits:
        memory: 32Mi
```

Apply:

```bash
kubectl apply -f minimal.yaml
kubectl wait --for=condition=Ready pod/minimal --timeout=120s
```

Thử exec:

```bash
kubectl exec -it minimal -- sh
```

Kết quả kỳ vọng: không có shell.

Attach ephemeral debug container:

```bash
kubectl debug -it pod/minimal --image=nicolaka/netshoot:latest --target=app -- sh
```

Trong shell debug:

```bash
ip addr
ip route
cat /etc/resolv.conf
nslookup kubernetes.default
exit
```

Kiểm tra ephemeral container:

```bash
kubectl describe pod minimal
```

### Câu hỏi

- Vì sao debug container không nên dùng để sửa app?
- RBAC nào cần có để dùng ephemeral containers?
- Debug image production nên được kiểm soát thế nào?

## Task 9: Ingress debugging worksheet (optional, 25 phút)

Nếu cluster có Ingress controller, tạo file `api-ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
spec:
  rules:
  - host: api.localtest.me
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
```

Apply:

```bash
kubectl apply -f api-ingress.yaml
kubectl get ingress api
kubectl describe ingress api
kubectl get svc,endpoints api
```

Nếu dùng K3s mặc định với Traefik:

```bash
kubectl get pod -n kube-system -l app.kubernetes.io/name=traefik
kubectl logs -n kube-system deploy/traefik --tail=100
```

Test theo thứ tự tùy môi trường:

```bash
curl -H 'Host: api.localtest.me' http://127.0.0.1/
```

Nếu `127.0.0.1` không đi qua Ingress controller, thử lấy node IP hoặc địa chỉ LoadBalancer:

```bash
kubectl get ingress api -o wide
kubectl get svc -n kube-system
kubectl get nodes -o wide
curl -H 'Host: api.localtest.me' http://<node-ip>/
```

Nếu cluster local không expose controller ra host, port-forward Service Traefik của K3s:

```bash
kubectl -n kube-system port-forward svc/traefik 8088:80
curl -H 'Host: api.localtest.me' http://127.0.0.1:8088/
```

Nếu controller không phải Traefik, port-forward Service của Ingress controller tương ứng hoặc ghi rõ "Ingress controller không expose được trong lab" và verify backend bằng Service/port-forward.

Nếu vẫn không chạy được, ghi lại bạn đang fail ở lớp nào:

- Ingress object có rule đúng không?
- Controller có chạy không?
- Controller có nhận rule không?
- Backend Service có endpoints không?
- Request có đúng Host header không?

## Task 10: NetworkPolicy timeout drill (optional, 20 phút)

Chỉ chạy task này nếu CNI/policy engine của cluster enforce NetworkPolicy. Nếu behavior không đổi sau khi apply policy, ghi lại đó là giới hạn môi trường lab.

Tạo policy chặn ingress vào Pod `api`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-api-ingress
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
```

Lưu thành `deny-api-ingress.yaml`, apply và test:

```bash
kubectl apply -f deny-api-ingress.yaml
kubectl exec client -- wget -T 5 -S -O- http://api/ || true
kubectl get networkpolicy
```

Expected nếu policy được enforce: DNS vẫn resolve, nhưng HTTP tới `api` timeout.

Thêm allow từ Pod `client`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-client-to-api
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: client
    ports:
    - protocol: TCP
      port: 80
```

Apply và verify:

```bash
kubectl apply -f allow-client-to-api.yaml
kubectl exec client -- wget -S -O- http://api/
kubectl delete networkpolicy deny-api-ingress allow-client-to-api
```

### Câu hỏi

- Timeout do NetworkPolicy khác gì timeout do endpoints rỗng?
- Vì sao DNS vẫn có thể resolve khi HTTP bị policy chặn?
- CNI của lab có enforce NetworkPolicy không?

## Task 11: Viết incident note (15 phút)

Viết note ngắn cho lỗi Service selector sai:

```text
Symptom:
Scope:
Start time:
Recent changes:
Evidence:
Root cause:
Fix:
Verification:
Prevention:
```

Gợi ý evidence:

- `kubectl describe svc api` selector `app=api-wrong`.
- Pod label là `app=api`.
- Endpoints rỗng trước patch.
- Endpoints có 2 Pod sau patch.
- HTTP từ client thành công sau patch.

## Task 12: Cleanup

```bash
kubectl delete namespace day32
```

## Stretch Goals

- Hoàn thành ephemeral container debug với `nicolaka/netshoot` nếu cluster cho phép.
- Chạy Ingress worksheet với fallback node IP/LB IP/port-forward theo môi trường.
- Bật NetworkPolicy timeout drill nếu CNI enforce policy.

## Checklist hoàn thành

- [ ] Debug được Service endpoints rỗng bằng labels/selectors.
- [ ] Chạy hoặc ghi nhận được trạng thái `kubectl top`.
- [ ] Test được DNS và HTTP từ trong cluster.
- [ ] Dùng được events, describe và logs `--previous` cho `CrashLoopBackOff`.
- [ ] Biết dùng port-forward để tách lỗi Service và app.
- [ ] Hiểu khi nào dùng ephemeral containers.
- [ ] Có checklist Ingress debug với fallback theo môi trường.
- [ ] Biết cách nhận diện timeout do NetworkPolicy nếu CNI hỗ trợ.
- [ ] Viết được incident note ngắn có evidence và prevention.
