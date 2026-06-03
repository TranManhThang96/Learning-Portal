# Bài thực hành - Day 29: Logging

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `busybox:1.36`, `nginx:1.27` và `fluent/fluent-bit:3.1`.
- Bạn có quyền tạo `Namespace`, `Deployment`, `DaemonSet`, `ConfigMap`, `ServiceAccount`, `ClusterRole` và `ClusterRoleBinding`.
- Shell mặc định cho lab là Linux/WSL/Bash.

## Lab Scenario

Bạn sẽ deploy một app ghi JSON log ra `stdout`, dùng `kubectl logs` để đọc log theo Pod/Deployment/label, tạo một container crash để đọc `--previous`, deploy Fluent Bit dạng DaemonSet để minh họa node-level log collection, rồi kiểm tra RBAC, multiline và redaction.

Lab này không dựng Loki hoặc Elasticsearch đầy đủ. Fluent Bit sẽ output ra chính log của collector để bạn thấy collector đọc log container và enrich metadata. Trong production, output này sẽ được thay bằng Loki, Elasticsearch/OpenSearch hoặc cloud logging.

Core Path dự kiến 115 phút. Mapping chi tiết sang Loki/Elasticsearch nằm trong Stretch Goals.

## Task 1: Tạo namespace (5 phút)

```bash
kubectl create namespace day29
kubectl config set-context --current --namespace=day29
```

## Task 2: Deploy app ghi structured log (20 phút)

Tạo file `json-logger.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: json-logger
  labels:
    app.kubernetes.io/name: json-logger
    app.kubernetes.io/part-of: observability-lab
spec:
  replicas: 2
  selector:
    matchLabels:
      app: json-logger
  template:
    metadata:
      labels:
        app: json-logger
        app.kubernetes.io/name: json-logger
        app.kubernetes.io/version: v1
        team: platform
    spec:
      containers:
      - name: logger
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          i=0
          while true; do
            i=$((i+1))
            level="info"
            if [ $((i % 7)) -eq 0 ]; then level="error"; fi
            printf '{"ts":"%s","level":"%s","service":"json-logger","version":"v1","request_id":"req-%04d","msg":"synthetic event","counter":%d}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$level" "$i" "$i"
            sleep 2
          done
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
```

Apply:

```bash
kubectl apply -f json-logger.yaml
kubectl rollout status deploy/json-logger
kubectl get pod -l app=json-logger -o wide
```

Đọc log:

```bash
kubectl logs deploy/json-logger --tail=20
kubectl logs -l app=json-logger --tail=20 --timestamps
kubectl logs -l app=json-logger --since=2m --tail=50
```

### Expected output

- Có 2 Pod `json-logger`.
- Log là JSON một dòng.
- Một số dòng có `"level":"error"` để bạn query/filter thủ công.

## Task 3: Đọc log trong Pod nhiều container (15 phút)

Tạo file `multi-container-logs.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-logger
  labels:
    app: multi-logger
spec:
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      while true; do
        echo "app container handled request at $(date -u +%H:%M:%S)"
        sleep 3
      done
  - name: worker
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      while true; do
        echo "worker container processed job at $(date -u +%H:%M:%S)"
        sleep 5
      done
```

Apply và đọc log từng container:

```bash
kubectl apply -f multi-container-logs.yaml
kubectl wait --for=condition=Ready pod/multi-logger --timeout=120s
kubectl logs multi-logger -c app --tail=10
kubectl logs multi-logger -c worker --tail=10
kubectl logs multi-logger --all-containers=true --tail=20
```

### Câu hỏi

- Nếu bỏ `-c app` ở Pod nhiều container, `kubectl logs` báo gì?
- Trong production, bạn muốn query theo `container` hay chỉ theo `pod`?

## Task 4: Đọc log container vừa crash bằng `--previous` (20 phút)

Tạo file `crashy.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crashy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crashy
  template:
    metadata:
      labels:
        app: crashy
        app.kubernetes.io/name: crashy
    spec:
      containers:
      - name: crashy
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo '{"level":"info","msg":"starting crashy container"}'
          echo '{"level":"error","msg":"simulated fatal error before exit"}'
          exit 42
```

Apply và kiểm tra:

```bash
kubectl apply -f crashy.yaml
kubectl get pod -l app=crashy
kubectl describe pod -l app=crashy
kubectl logs deploy/crashy --previous
```

### Expected output

- Pod vào trạng thái `CrashLoopBackOff`.
- `kubectl logs deploy/crashy` có thể chỉ thấy container hiện tại.
- `kubectl logs deploy/crashy --previous` cho thấy log lần chạy trước.

## Task 5: Deploy Fluent Bit collector DaemonSet (35 phút)

Tạo file `fluent-bit-stdout.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: fluent-bit
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: day29-fluent-bit-read
rules:
- apiGroups: [""]
  resources:
  - pods
  - namespaces
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: day29-fluent-bit-read
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: day29-fluent-bit-read
subjects:
- kind: ServiceAccount
  name: fluent-bit
  namespace: day29
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         2
        Log_Level     info
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Path              /var/log/containers/*day29*.log
        Parser            cri
        Tag               kube.*
        Refresh_Interval  5
        Mem_Buf_Limit     5MB
        Skip_Long_Lines   On

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Merge_Log           On
        Keep_Log            Off

    [FILTER]
        Name    modify
        Match   kube.*
        Remove  token
        Remove  password
        Remove  authorization
        Remove  email

    [OUTPUT]
        Name   stdout
        Match  kube.*
  parsers.conf: |
    [PARSER]
        Name        cri
        Format      regex
        Regex       ^(?<time>[^ ]+) (?<stream>stdout|stderr) (?<logtag>[^ ]*) (?<log>.*)$
        Time_Key    time
        Time_Format %Y-%m-%dT%H:%M:%S.%L%z
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      serviceAccountName: fluent-bit
      tolerations:
      - operator: Exists
      containers:
      - name: fluent-bit
        image: fluent/fluent-bit:3.1
        args:
        - -c
        - /fluent-bit/etc/fluent-bit.conf
        volumeMounts:
        - name: config
          mountPath: /fluent-bit/etc
        - name: varlog
          mountPath: /var/log
          readOnly: true
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            memory: 128Mi
      volumes:
      - name: config
        configMap:
          name: fluent-bit-config
      - name: varlog
        hostPath:
          path: /var/log
```

Apply:

```bash
kubectl apply -f fluent-bit-stdout.yaml
kubectl rollout status daemonset/fluent-bit --timeout=180s
kubectl auth can-i list pods --as=system:serviceaccount:day29:fluent-bit -n day29
kubectl auth can-i watch namespaces --as=system:serviceaccount:day29:fluent-bit
kubectl logs daemonset/fluent-bit --tail=80
```

### Expected output

- Fluent Bit chạy trên mỗi node.
- Log của Fluent Bit chứa event từ các Pod `day29`.
- Event có metadata Kubernetes như namespace, pod, container hoặc labels nếu filter enrich thành công.
- `kubectl auth can-i` trả `yes` cho quyền đọc Pod/Namespace metadata.

Nếu không thấy log:

```bash
kubectl describe daemonset/fluent-bit
kubectl logs daemonset/fluent-bit --tail=200
kubectl get pod -l app=json-logger -o wide
```

Trên một số local cluster, đường dẫn host log có thể khác. Ghi lại path thực tế trong môi trường của bạn.

## Task 6: Inject multiline và sensitive fields (20 phút)

Tạo file `sensitive-logger.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: sensitive-logger
  labels:
    app: sensitive-logger
spec:
  restartPolicy: Never
  containers:
  - name: app
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo '{"ts":"2026-05-08T00:00:00Z","level":"error","service":"payment","email":"alice@example.com","token":"secret-token-123","msg":"payment provider failed"}'
      echo '2026-05-08T00:00:01Z ERROR java.lang.RuntimeException: simulated stack trace'
      echo '    at com.example.Payment.charge(Payment.java:42)'
      echo '    at com.example.Api.handle(Api.java:10)'
      sleep 20
```

Apply và quan sát:

```bash
kubectl apply -f sensitive-logger.yaml
kubectl wait --for=condition=Ready pod/sensitive-logger --timeout=60s || true
kubectl logs sensitive-logger
kubectl logs daemonset/fluent-bit --tail=200 | grep -E 'secret-token|alice@example.com' || echo "sensitive fields redacted or not present in current tail"
kubectl logs daemonset/fluent-bit --tail=200 | grep -E 'RuntimeException|Payment.java|Api.java'
```

### Expected output

- Log gốc của app có `email` và `token`.
- Log output từ Fluent Bit không nên còn `email`/`token` sau filter `modify` nếu JSON merge thành công.
- Stack trace nhiều dòng vẫn có thể bị tách thành nhiều event vì lab chưa bật multiline parser production.

Ghi lại:

```text
Sensitive fields redacted?:
Stack trace split or grouped?:
Would I fix in app JSON logging or collector multiline parser?:
```

## Stretch Goal: Thiết kế mapping sang Loki hoặc Elasticsearch (20 phút)

Tạo bảng trả lời trong file ghi chú riêng:

| Field | Đưa vào label/index field? | Lý do |
|---|---|---|
| namespace | label/index field | Cardinality thấp, query thường xuyên |
| app | label/index field | Query theo service |
| version | label/index field | Debug rollout |
| request_id | log content | Cardinality cao |
| user_id | log content hoặc redact | Cardinality cao, có thể nhạy cảm |
| trace_id | log content | Dùng để correlate, không nên là Loki label |
| level | label/index field có kiểm soát | Query error/warn nhanh |

### Câu hỏi

- Nếu dùng Loki, bạn chọn label nào?
- Nếu dùng Elasticsearch/OpenSearch, field nào cần index và field nào nên giữ dạng text?
- Retention bao lâu cho debug log, app log và audit log?

## Task 7: Cleanup

```bash
kubectl delete namespace day29
kubectl delete clusterrole day29-fluent-bit-read
kubectl delete clusterrolebinding day29-fluent-bit-read
```

## Checklist hoàn thành

- [ ] Đọc được log theo Deployment, label selector và container name.
- [ ] Dùng được `--previous` để đọc log container crash.
- [ ] Hiểu vì sao app nên log ra `stdout`/`stderr`.
- [ ] Deploy được log collector DaemonSet dạng lab.
- [ ] Xác minh RBAC metadata enrichment bằng `kubectl auth can-i`.
- [ ] Quan sát được sensitive JSON fields được redact ở collector.
- [ ] Nhận diện được multiline stack trace bị split khi chưa có parser phù hợp.
- [ ] Phân biệt được Loki label và log content.
- [ ] Viết được retention và redaction policy cơ bản.
