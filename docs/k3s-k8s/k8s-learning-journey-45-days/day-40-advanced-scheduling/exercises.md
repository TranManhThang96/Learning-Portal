# Bài thực hành - Day 40: Advanced Scheduling

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Quyền label/taint node.
- Khuyến nghị multi-node cluster để thấy anti-affinity/topology spread rõ hơn.
- Nếu chỉ có single-node, vẫn làm được nodeSelector, taint/toleration và Pending debug.

## Lab Scenario

Bạn sẽ gắn label/taint tạm thời lên node, deploy Pod với nodeSelector, node affinity, tolerations, anti-affinity và topology spread. Mục tiêu chính là đọc scheduler events và hiểu vì sao Pod được schedule hoặc bị Pending.

## Core Path (105-115 phút)

- Task 1-6 và Task 10 là phần bắt buộc.
- Task 7-9 là stretch/worksheet vì phụ thuộc multi-node capacity hoặc policy của cluster.

## Task 1: Khảo sát node labels và tạo namespace (10 phút)

```bash
kubectl create namespace day40
kubectl get nodes -o wide
kubectl get nodes --show-labels
```

Chọn một node làm lab node:

```bash
$NODE = kubectl get nodes -o jsonpath='{.items[0].metadata.name}'
Write-Output $NODE
```

Linux/macOS:

```bash
NODE=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
echo $NODE
```

Gắn labels:

```bash
kubectl label node $NODE nodepool=day40 disk=fast day40.example.com/zone=lab-a --overwrite
```

### Câu hỏi

- Node đang có label topology nào sẵn?
- Cluster của bạn single-node hay multi-node?
- Label nào do cloud/provider đặt, label nào bạn vừa đặt?
- Vì sao không nên ghi đè `topology.kubernetes.io/zone` trên managed Kubernetes?

## Task 2: nodeSelector schedule thành công (15 phút)

Tạo file `pod-nodeselector.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nodeselector-ok
  namespace: day40
spec:
  nodeSelector:
    nodepool: day40
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Apply:

```bash
kubectl apply -f pod-nodeselector.yaml
kubectl get pod nodeselector-ok -n day40 -o wide
kubectl describe pod nodeselector-ok -n day40
```

### Expected output

- Pod chạy trên node có label `nodepool=day40`.

### Câu hỏi

- Nếu label bị xóa sau khi Pod chạy, Pod có tự bị evict không?
- nodeSelector phù hợp với constraint phức tạp không?

## Task 3: nodeSelector lỗi và đọc scheduler events (15 phút)

Tạo file `pod-nodeselector-fail.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nodeselector-fail
  namespace: day40
spec:
  nodeSelector:
    nodepool: does-not-exist
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Apply và debug:

```bash
kubectl apply -f pod-nodeselector-fail.yaml
kubectl get pod nodeselector-fail -n day40
kubectl describe pod nodeselector-fail -n day40
kubectl get events -n day40 --sort-by=.lastTimestamp
```

### Expected output

- Pod `Pending`.
- Event nhắc node affinity/selector mismatch.

Cleanup:

```bash
kubectl delete pod nodeselector-fail -n day40
```

### Câu hỏi

- Evidence nào chứng minh lỗi nằm ở scheduling constraint?
- Trong production, bạn sửa Pod spec hay label node?

## Task 4: Taint node và dùng toleration (25 phút)

Taint node:

```bash
kubectl taint node $NODE dedicated=day40:NoSchedule
kubectl describe node $NODE
```

Tạo Pod không toleration:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: taint-fail
  namespace: day40
spec:
  nodeSelector:
    nodepool: day40
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Lưu thành `pod-taint-fail.yaml`, apply:

```bash
kubectl apply -f pod-taint-fail.yaml
kubectl get pod taint-fail -n day40
kubectl describe pod taint-fail -n day40
```

### Expected output

- Pod `taint-fail` phải `Pending`.
- Event có `had untolerated taint` vì Pod bị `nodeSelector` ép vào đúng node đã taint.
- Nếu Pod vẫn chạy, kiểm tra lại node label `nodepool=day40` và taint `dedicated=day40:NoSchedule`.

Tạo Pod có toleration và nodeSelector:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: taint-ok
  namespace: day40
spec:
  nodeSelector:
    nodepool: day40
  tolerations:
  - key: dedicated
    operator: Equal
    value: day40
    effect: NoSchedule
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Lưu thành `pod-taint-ok.yaml`, apply:

```bash
kubectl apply -f pod-taint-ok.yaml
kubectl get pod taint-ok -n day40 -o wide
```

Cleanup Pod fail:

```bash
kubectl delete pod taint-fail -n day40
```

### Câu hỏi

- Toleration có kéo Pod vào node tainted không, hay chỉ cho phép?
- Vì sao dedicated node pool thường cần cả taint và node affinity/nodeSelector?
- `NoSchedule` có evict Pod đang chạy trước đó không?

## Task 5: Required node affinity (20 phút)

Tạo file `pod-node-affinity.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: node-affinity-ok
  namespace: day40
spec:
  tolerations:
  - key: dedicated
    operator: Equal
    value: day40
    effect: NoSchedule
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: disk
            operator: In
            values:
            - fast
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Apply:

```bash
kubectl apply -f pod-node-affinity.yaml
kubectl get pod node-affinity-ok -n day40 -o wide
```

### Câu hỏi

- Node affinity linh hoạt hơn nodeSelector ở đâu?
- `IgnoredDuringExecution` nghĩa là gì?

## Task 6: Pod anti-affinity và topology spread hard rule (multi-node recommended, 30 phút)

Tạo Deployment với topology spread theo hostname:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spread-api
  namespace: day40
spec:
  replicas: 3
  selector:
    matchLabels:
      app: spread-api
  template:
    metadata:
      labels:
        app: spread-api
    spec:
      tolerations:
      - key: dedicated
        operator: Equal
        value: day40
        effect: NoSchedule
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: kubernetes.io/hostname
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: spread-api
      containers:
      - name: app
        image: nginx:1.25
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
```

Lưu thành `deploy-spread.yaml`, apply:

```bash
kubectl apply -f deploy-spread.yaml
kubectl get pods -n day40 -o wide -l app=spread-api
kubectl describe pod -n day40 -l app=spread-api
```

Nếu cluster multi-node, quan sát Pod được spread thế nào. `DoNotSchedule` là hard rule: nếu scheduler không giữ được `maxSkew`, Pod mới sẽ `Pending`. Trên single-node, constraint theo `kubernetes.io/hostname` có thể không chứng minh HA thật vì chỉ có một failure domain; ghi lại giới hạn này thay vì kết luận app đã HA.

### Câu hỏi

- `DoNotSchedule` khác `ScheduleAnyway` thế nào?
- Vì sao topology spread theo zone cần node labels zone thật?
- Replica count và số node/zone ảnh hưởng kết quả thế nào?

## Task 7: Inject required anti-affinity impossible (optional, 20 phút)

Chỉ làm nếu bạn hiểu cleanup. Deployment này yêu cầu replicas không cùng hostname. Trên single-node hoặc ít node hơn replicas, Pod sẽ Pending.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anti-affinity-hard
  namespace: day40
spec:
  replicas: 2
  selector:
    matchLabels:
      app: anti-hard
  template:
    metadata:
      labels:
        app: anti-hard
    spec:
      tolerations:
      - key: dedicated
        operator: Equal
        value: day40
        effect: NoSchedule
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchLabels:
                app: anti-hard
            topologyKey: kubernetes.io/hostname
      containers:
      - name: app
        image: nginx:1.25
        resources:
          requests:
            cpu: 20m
            memory: 32Mi
          limits:
            memory: 64Mi
```

Apply và debug:

```bash
kubectl apply -f deploy-anti-hard.yaml
kubectl get pods -n day40 -l app=anti-hard -o wide
kubectl describe pod <pending-pod> -n day40
```

Cleanup:

```bash
kubectl delete deploy anti-affinity-hard -n day40
```

### Câu hỏi

- Required anti-affinity có thể làm rollout kẹt thế nào?
- Khi nào preferred anti-affinity thực dụng hơn?

## Task 8: PriorityClass mini-task (optional, 10 phút)

Không test preemption trong core lab. Chỉ tạo PriorityClass và gắn vào một Pod nhỏ để hiểu field và cleanup.

Tạo file `priorityclass-day40.yaml`:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: day40-high
value: 100000
globalDefault: false
description: "Lab PriorityClass for Day 40. Do not use as production default."
```

Tạo file `pod-priority.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: priority-demo
  namespace: day40
spec:
  priorityClassName: day40-high
  nodeSelector:
    nodepool: day40
  tolerations:
  - key: dedicated
    operator: Equal
    value: day40
    effect: NoSchedule
  containers:
  - name: app
    image: nginx:1.25
    resources:
      requests:
        cpu: 20m
        memory: 32Mi
      limits:
        memory: 64Mi
```

Apply và kiểm tra:

```bash
kubectl apply -f priorityclass-day40.yaml
kubectl apply -f pod-priority.yaml
kubectl get pod priority-demo -n day40 -o yaml
```

### Câu hỏi

- Vì sao `PriorityClass` không tự tạo capacity mới?
- Preemption có thể gây ảnh hưởng gì tới workload priority thấp?
- Vì sao không nên đặt `globalDefault: true` trong lab?

## Task 9: Node pool placement worksheet (15 phút)

Điền cho một production cluster giả định:

```text
Node pool: system
Labels:
Taints:
Allowed workloads:
Forbidden workloads:

Node pool: general
Labels:
Taints:
Allowed workloads:
Spread requirements:

Node pool: workers-spot
Labels:
Taints:
Allowed workloads:
Interruption handling:

Node pool: data
Labels:
Taints:
Allowed workloads:
Storage/zone caveats:
```

### Câu hỏi

- Workload nào cần dedicated node pool?
- Workload nào không nên chạy trên spot?
- Constraint nào cần hard, constraint nào nên soft?

## Task 10: Cleanup

Xóa resources:

```bash
kubectl delete namespace day40
kubectl delete priorityclass day40-high --ignore-not-found
```

Gỡ taint và labels đã đặt:

```bash
kubectl taint node $NODE dedicated=day40:NoSchedule-
kubectl label node $NODE nodepool- disk- day40.example.com/zone-
```

Xóa file local nếu không cần:

```bash
Remove-Item -Force .\pod-nodeselector.yaml,.\pod-nodeselector-fail.yaml,.\pod-taint-fail.yaml,.\pod-taint-ok.yaml,.\pod-node-affinity.yaml,.\deploy-spread.yaml,.\deploy-anti-hard.yaml,.\priorityclass-day40.yaml,.\pod-priority.yaml -ErrorAction SilentlyContinue
```

Linux/macOS:

```bash
rm -f ./pod-nodeselector.yaml ./pod-nodeselector-fail.yaml ./pod-taint-fail.yaml ./pod-taint-ok.yaml ./pod-node-affinity.yaml ./deploy-spread.yaml ./deploy-anti-hard.yaml ./priorityclass-day40.yaml ./pod-priority.yaml
```

## Stretch Goals

- Chạy Task 7 để tạo required anti-affinity impossible trên multi-node cluster.
- Hoàn thành PriorityClass mini-task và ghi rõ vì sao priority không tự tạo thêm capacity.
- Viết node pool placement worksheet cho workload stateless, batch và stateful.

## Checklist hoàn thành

- [ ] Label được node và schedule bằng nodeSelector.
- [ ] Tạo được Pod Pending do selector mismatch và đọc events.
- [ ] Taint node và dùng toleration đúng.
- [ ] Hiểu toleration khác node selection.
- [ ] Dùng required node affinity.
- [ ] Thử topology spread `DoNotSchedule` hoặc hiểu giới hạn single-node.
- [ ] Debug được required anti-affinity impossible.
- [ ] Optional: tạo và cleanup được PriorityClass lab.
- [ ] Viết được node pool placement worksheet.
