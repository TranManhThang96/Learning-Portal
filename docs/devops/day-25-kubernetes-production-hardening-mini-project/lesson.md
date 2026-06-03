# Day 25: Mini-project — Harden, Scale & Debug Kubernetes App

## 1. Mục tiêu bài học

Đây là **capstone project của Phase 3** (Kubernetes Production). Bạn sẽ tổng hợp kiến thức từ Day 18-24 để harden một microservice stack từ "chạy được" thành "production-ready".

### Deliverables bắt buộc

1. **Updated manifests** — tất cả YAML đã hardened (resource limits, probes, RBAC, NetworkPolicy, Kyverno policies).
2. **Security checklist** — checklist đã điền (passed/failed mỗi item).
3. **Scaling test report** — kết quả load test + HPA behavior.
4. **Incident runbook** — 5 runbooks cho common failures.

### Acceptance Criteria

- [ ] Tất cả containers có resource requests/limits.
- [ ] Tất cả deployments có liveness + readiness probes.
- [ ] HPA configured cho API Gateway và Book Service.
- [ ] Dedicated ServiceAccounts với least-privilege RBAC.
- [ ] NetworkPolicy default deny + explicit allow rules.
- [ ] Kyverno policies: require labels, require limits, block privileged.
- [ ] 3 incidents simulated và debugged theo methodology (Day 22).
- [ ] 5 incident runbooks viết theo template.
- [ ] Production readiness score ≥ 60%.

---

## 2. Bối cảnh & Động lực

### Scenario

> Bạn vừa được assign làm **DevOps engineer** cho team BookStore. Team đã deploy microservice stack lên Kubernetes (Day 17) nhưng chưa qua production hardening. CTO yêu cầu: "Harden stack này trước khi go-live tuần tới."

### BookStore Architecture (Day 17)

```
                    ┌──────────────┐
                    │   Ingress    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Frontend   │ (nginx, port 80)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  API Gateway │ (nginx, port 80)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │                         │
       ┌──────▼───────┐         ┌──────▼───────┐
       │ Book Service │         │    Redis     │
       │ (nginx, 80)  │         │ (redis, 6379)│
       └──────────────┘         └──────────────┘
```

### Gaps cần fix

| Area | Current State | Target State |
|------|--------------|-------------|
| Resources | Không có | requests + limits trên mọi container |
| Probes | Không có | liveness + readiness trên mọi service |
| Replicas | 1 | ≥ 2 cho stateless services |
| Autoscaling | Không có | HPA cho API Gateway + Book Service |
| RBAC | default ServiceAccount | Dedicated SA per service |
| NetworkPolicy | Không có | Default deny + explicit allow |
| Admission Policy | Không có | Kyverno policies enforced |
| Runbooks | Không có | Top 5 failure runbooks |

---

## 3. Kiến thức nền tảng

Production hardening không phải là thêm một danh sách YAML cho đẹp. Mục tiêu là giảm xác suất incident, giảm blast radius khi incident xảy ra, và làm cho hệ thống có thể debug/rollback trong thời gian chấp nhận được.

Một workload "production-ready" tối thiểu cần trả lời được 6 câu hỏi:

1. **Nó cần bao nhiêu tài nguyên?** `requests` giúp scheduler đặt pod đúng chỗ; `limits` giới hạn blast radius nhưng có thể gây throttling hoặc OOMKilled nếu đặt sai.
2. **Khi nào nó được nhận traffic?** `readinessProbe` bảo vệ người dùng khỏi pod chưa sẵn sàng; `livenessProbe` chỉ nên restart khi process thật sự kẹt.
3. **Nó được scale bằng tín hiệu nào?** HPA cần metric ổn định, target hợp lý, và workload stateless hoặc đã xử lý state đúng cách.
4. **Nó được phép làm gì?** RBAC và ServiceAccount riêng giúp kiểm soát quyền Kubernetes API theo least privilege.
5. **Nó được nói chuyện với ai?** NetworkPolicy chuyển network từ implicit trust sang explicit allow.
6. **Cluster có chặn cấu hình nguy hiểm từ đầu vào không?** Admission policies giúp fail fast trước khi workload rủi ro vào cluster.

Với góc nhìn developer, hardening giống như chuyển từ "unit test pass" sang "service có contract vận hành": có resource envelope, health contract, access boundary, rollout path, và runbook khi lỗi.

---

## 4. Deep Dive

Luồng hardening của mini-project đi theo thứ tự giảm rủi ro:

```text
Base manifests
  │
  ├─ Resource requests/limits + probes
  │     └─ scheduler ổn định hơn, traffic chỉ tới pod ready
  │
  ├─ HPA + PDB
  │     └─ scale khi có tải, giữ availability khi maintenance
  │
  ├─ RBAC + ServiceAccount
  │     └─ workload không dùng default token/quyền thừa
  │
  ├─ NetworkPolicy
  │     └─ chỉ allow traffic cần thiết giữa frontend/api/book/redis/DNS
  │
  ├─ Kyverno policies
  │     └─ chặn privileged pod, thiếu resources, thiếu label
  │
  └─ Incident simulation + runbook
        └─ kiểm chứng khả năng detect, debug, fix, prevent
```

Failure modes cần để ý trong dự án này:

- **False positive từ probe**: probe quá aggressive khiến rollout tự tạo outage.
- **CPU throttling**: CPU limit thấp làm latency tăng dù `kubectl top` nhìn không quá cao.
- **HPA không scale**: thiếu metrics-server, thiếu CPU requests, hoặc workload không tạo đủ CPU utilization.
- **NetworkPolicy chặn DNS**: default deny egress nhưng quên allow UDP/TCP 53 tới `kube-dns`.
- **Admission policy tự khóa mình**: enforce policy quá sớm có thể chặn cả workload hệ thống hoặc CI/CD rollout.
- **PDB không cứu được single replica**: PDB chỉ hữu ích khi replicas đủ và cluster còn capacity để reschedule.

---

## 5. Trade-offs & Best Practices ⭐

| Quyết định | Nên chọn khi | Trade-off |
|------------|--------------|-----------|
| CPU limit thấp | Muốn chặn noisy neighbor trong shared cluster | Dễ gây throttling và tail latency |
| Không đặt CPU limit, chỉ đặt request | Latency-sensitive service, node pool đáng tin | Cần quota/capacity planning chặt |
| HPA theo CPU | Service CPU-bound, traffic tương quan CPU | Kém hiệu quả với I/O-bound workload |
| HPA theo custom metric | Queue depth, RPS, latency phản ánh tải tốt hơn | Cần Prometheus Adapter/KEDA và metric quality |
| Default deny NetworkPolicy | Namespace production/shared cluster | Cần maintain allow rules, dễ chặn nhầm DNS/egress |
| Kyverno enforce ngay | Policy đã test kỹ ở staging | Có thể block rollout khẩn cấp nếu policy sai |
| Kyverno audit trước | Team mới áp policy hoặc legacy workload | Violation vẫn vào cluster trong giai đoạn audit |

Best practices theo quy mô:

- **Startup nhỏ**: bắt buộc resources/probes/replicas tối thiểu, dùng Kyverno audit trước, checklist bằng script đơn giản.
- **Mid-size company**: enforce label/resources/securityContext, dùng namespace default deny, chuẩn hóa Helm/Kustomize.
- **Enterprise**: policy theo tenant, exception có expiry, admission report định kỳ, SLO/error budget gắn vào release gate.
- **High-traffic system**: load test trước khi đặt HPA target, tránh CPU limit quá thấp, tách node pool cho critical services.

Anti-patterns cần tránh:

- Copy resource limits giữa services mà không đo workload.
- Đặt livenessProbe trùng readinessProbe cho dependency bên ngoài rồi restart app khi database chậm.
- Dùng `default` ServiceAccount cho mọi deployment.
- Enforce policy trên toàn cluster mà chưa exclude `kube-system` và namespace của controller.
- Viết runbook chỉ có mô tả, không có command verify và rollback.

---

## 6. Performance & Scalability ⭐

Performance trong bài này phụ thuộc vào 4 lớp:

- **Scheduling**: `requests` quá cao làm pod Pending; quá thấp làm bin-pack quá chặt và dễ contention.
- **Runtime**: CPU limit gây CFS throttling; memory limit gây OOMKilled; probe quá dày tạo overhead không cần thiết.
- **Autoscaling**: HPA có độ trễ vì cần metrics window, scale-up/down behavior và thời gian pod warm-up.
- **Network**: NetworkPolicy làm rule set rõ hơn nhưng plugin CNI kém tối ưu có thể tăng latency khi policy rất nhiều.

Cách phát hiện bottleneck:

```bash
kubectl top pods -n bookstore
kubectl describe hpa -n bookstore
kubectl describe pod -n bookstore <pod-name> | grep -A5 -E "Limits|Requests|Last State|Events"
kubectl get events -n bookstore --sort-by=.lastTimestamp
```

Scaling strategy:

- **Vertical scaling**: tăng requests/limits khi service ổn định nhưng thiếu tài nguyên rõ ràng.
- **Horizontal scaling**: tăng replicas/HPA cho stateless HTTP services.
- **Queue-based scaling**: dùng KEDA khi backlog/queue depth là tín hiệu tải chính.
- **Event-driven scaling**: phù hợp batch/consumer workload, nhưng cần idempotency và backpressure.

Khi scale là sai giải pháp:

- Service routing sai selector, endpoints rỗng.
- Liveness probe làm app restart liên tục.
- CPU throttling do limit quá thấp nhưng bottleneck thật là database/query.
- NetworkPolicy chặn dependency nên tăng replicas chỉ nhân lỗi lên nhiều pod hơn.

---

## 7. Security & Reliability Considerations

Security controls trong mini-project cần được thiết kế theo defense in depth:

- **RBAC**: mỗi service dùng ServiceAccount riêng; không bind wildcard verbs/resources nếu không cần.
- **NetworkPolicy**: default deny ingress/egress, allow DNS rõ ràng, allow traffic theo app label thay vì IP tĩnh.
- **Admission policy**: chặn privileged pod, thiếu resources, thiếu ownership labels, image registry không tin cậy nếu mở rộng.
- **Pod security**: thêm `runAsNonRoot`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem` khi image hỗ trợ.
- **Reliability**: PDB cho stateless services ≥ 2 replicas; readinessProbe phải phản ánh khả năng nhận traffic.
- **Rollback**: mọi patch cần có command revert hoặc manifest trước/sau; policy mới nên đi qua `Audit` trước `Enforce`.

Blast radius mục tiêu sau hardening:

- Một pod lỗi không làm toàn service downtime vì có replicas + readiness.
- Một service compromised không scan/talk toàn namespace vì có NetworkPolicy.
- Một manifest nguy hiểm không vào cluster vì admission policy reject.
- Một node maintenance không evict quá nhiều pod cùng lúc vì có PDB.

---

## 8. Hands-on Example — Harden BookStore App

### 8.1 Setup Cluster

```bash
# Tạo kind cluster với metrics-server support
kind create cluster --name bookstore-prod --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
  - role: worker
EOF

# Install metrics-server (cần cho HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch metrics-server cho kind (disable TLS verify)
kubectl patch deployment metrics-server -n kube-system --type json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Chờ metrics-server ready
kubectl wait --for=condition=Available deployment/metrics-server -n kube-system --timeout=120s
```

### 8.2 Deploy Base Application (chưa hardened)

```yaml
# bookstore-base.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: bookstore
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: web
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: gateway
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: book-service
  template:
    metadata:
      labels:
        app: book-service
    spec:
      containers:
        - name: service
          image: nginx:1.25
          ports:
            - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bookstore
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: frontend-svc
  namespace: bookstore
spec:
  selector:
    app: frontend
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway-svc
  namespace: bookstore
spec:
  selector:
    app: api-gateway
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: book-service-svc
  namespace: bookstore
spec:
  selector:
    app: book-service
  ports:
    - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: redis-svc
  namespace: bookstore
spec:
  selector:
    app: redis
  ports:
    - port: 6379
```

```bash
kubectl apply -f bookstore-base.yaml
sleep 15
kubectl get all -n bookstore
```

---

### 8.3 Task Breakdown

#### Task 1: Resource Management (Day 18)

Thêm resource requests/limits cho tất cả containers. Tăng replicas cho stateless services.

```yaml
# task1-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: bookstore
  labels:
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
        team: product
        environment: production
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: web
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: bookstore
  labels:
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
        team: product
        environment: production
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: gateway
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: book-service
  namespace: bookstore
  labels:
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 2
  selector:
    matchLabels:
      app: book-service
  template:
    metadata:
      labels:
        app: book-service
        team: product
        environment: production
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: service
          image: nginx:1.25
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 200m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: bookstore
  labels:
    team: product
    environment: production
    cost-center: engineering
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
        team: product
        environment: production
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            initialDelaySeconds: 5
            periodSeconds: 5
```

```bash
kubectl apply -f task1-resources.yaml
sleep 15

# Verify
kubectl get pods -n bookstore -o wide
kubectl get pods -n bookstore -o custom-columns=\
NAME:.metadata.name,\
CPU_REQ:.spec.containers[0].resources.requests.cpu,\
MEM_REQ:.spec.containers[0].resources.requests.memory,\
QOS:.status.qosClass
```

#### Task 2: Autoscaling — HPA (Day 19)

```yaml
# task2-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: bookstore
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: book-service-hpa
  namespace: bookstore
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: book-service
  minReplicas: 2
  maxReplicas: 4
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

```bash
kubectl apply -f task2-hpa.yaml

# Verify
kubectl get hpa -n bookstore
```

#### Task 3: RBAC — Dedicated ServiceAccounts (Day 20)

```yaml
# task3-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: frontend-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-gateway-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: book-service-sa
  namespace: bookstore
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: redis-sa
  namespace: bookstore
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-reader
  namespace: bookstore
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-gateway-binding
  namespace: bookstore
subjects:
  - kind: ServiceAccount
    name: api-gateway-sa
    namespace: bookstore
roleRef:
  kind: Role
  name: app-reader
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: book-service-binding
  namespace: bookstore
subjects:
  - kind: ServiceAccount
    name: book-service-sa
    namespace: bookstore
roleRef:
  kind: Role
  name: app-reader
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f task3-rbac.yaml

# Patch deployments to use ServiceAccounts
kubectl patch deployment frontend -n bookstore \
  --type json -p '[{"op":"add","path":"/spec/template/spec/serviceAccountName","value":"frontend-sa"}]'
kubectl patch deployment api-gateway -n bookstore \
  --type json -p '[{"op":"add","path":"/spec/template/spec/serviceAccountName","value":"api-gateway-sa"}]'
kubectl patch deployment book-service -n bookstore \
  --type json -p '[{"op":"add","path":"/spec/template/spec/serviceAccountName","value":"book-service-sa"}]'
kubectl patch deployment redis -n bookstore \
  --type json -p '[{"op":"add","path":"/spec/template/spec/serviceAccountName","value":"redis-sa"}]'

# Verify
kubectl auth can-i list pods --as=system:serviceaccount:bookstore:api-gateway-sa -n bookstore
# Expected: no

kubectl auth can-i get configmaps --as=system:serviceaccount:bookstore:api-gateway-sa -n bookstore
# Expected: yes
```

#### Task 4: NetworkPolicy (Day 20)

```yaml
# task4-networkpolicy.yaml
# Default deny all
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: bookstore
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
# Allow DNS for all pods
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: bookstore
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to: []
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
# Frontend: receive from outside, send to API gateway
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from: []
      ports:
        - port: 80
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 80
---
# API Gateway: receive from frontend, send to book-service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - port: 80
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: book-service
      ports:
        - port: 80
---
# Book Service: receive from API gateway, send to Redis
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: book-service-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels:
      app: book-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 80
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - port: 6379
---
# Redis: receive from book-service only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: redis-policy
  namespace: bookstore
spec:
  podSelector:
    matchLabels:
      app: redis
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: book-service
      ports:
        - port: 6379
```

```bash
kubectl apply -f task4-networkpolicy.yaml

# Verify: book-service → redis (allowed)
kubectl exec -n bookstore deploy/book-service -- sh -c "nc -zv redis-svc 6379 2>&1" || true

# Verify: frontend → redis (blocked)
kubectl exec -n bookstore deploy/frontend -- sh -c "nc -zv redis-svc 6379 -w 3 2>&1" || true
```

#### Task 5: Admission Policies — Kyverno (Day 21)

```bash
# Install Kyverno
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=1
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kyverno -n kyverno --timeout=120s
```

```yaml
# task5-kyverno.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: Audit
  background: true
  rules:
    - name: require-team-label
      match:
        any:
          - resources:
              kinds: [Deployment]
      exclude:
        any:
          - resources:
              namespaces: [kube-system, kyverno]
      validate:
        message: "Label 'team' is required."
        pattern:
          metadata:
            labels:
              team: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resources
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: require-limits
      match:
        any:
          - resources:
              kinds: [Pod]
      exclude:
        any:
          - resources:
              namespaces: [kube-system, kyverno]
      validate:
        message: "Resource requests and limits are required."
        pattern:
          spec:
            containers:
              - resources:
                  requests:
                    memory: "?*"
                    cpu: "?*"
                  limits:
                    memory: "?*"
                    cpu: "?*"
---
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: deny-privileged
      match:
        any:
          - resources:
              kinds: [Pod]
      exclude:
        any:
          - resources:
              namespaces: [kube-system, kyverno]
      validate:
        message: "Privileged containers are not allowed."
        pattern:
          spec:
            containers:
              - =(securityContext):
                  =(privileged): false
```

```bash
kubectl apply -f task5-kyverno.yaml

# Verify: privileged pod blocked
kubectl run test-priv --image=nginx:1.25 -n bookstore \
  --overrides='{"spec":{"containers":[{"name":"test","image":"nginx:1.25","securityContext":{"privileged":true},"resources":{"requests":{"cpu":"50m","memory":"64Mi"},"limits":{"cpu":"100m","memory":"128Mi"}}}]}}' 2>&1 || true
# Expected: blocked

# Verify: pod without resources blocked
kubectl run test-nores --image=nginx:1.25 -n bookstore 2>&1 || true
# Expected: blocked
```

#### Task 6: PDB (Day 23)

```yaml
# task6-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: frontend-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: frontend
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api-gateway
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: book-service-pdb
  namespace: bookstore
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: book-service
```

```bash
kubectl apply -f task6-pdb.yaml
kubectl get pdb -n bookstore
```

#### Task 7: Incident Simulation & Debug (Day 22)

Simulate 3 incidents và debug theo systematic methodology.

**Incident 1**: Giảm memory limit của book-service xuống 10Mi → OOMKilled.

```bash
kubectl patch deployment book-service -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"10Mi"}]'

# Chờ crash
sleep 30

# Debug
kubectl get pods -n bookstore -l app=book-service
kubectl describe pod -n bookstore -l app=book-service | grep -A3 "Last State"
# Reason: OOMKilled, Exit Code: 137

# Fix
kubectl patch deployment book-service -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}]'
```

**Incident 2**: Sửa service selector → routing issue.

```bash
kubectl patch svc book-service-svc -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/selector/app","value":"book-service-v2"}]'

# Debug
kubectl get endpoints book-service-svc -n bookstore
# ENDPOINTS: <none>

# Fix
kubectl patch svc book-service-svc -n bookstore --type json \
  -p '[{"op":"replace","path":"/spec/selector/app","value":"book-service"}]'
```

**Incident 3**: Deploy pod với image sai → ImagePullBackOff.

```bash
kubectl set image deployment/frontend -n bookstore web=nginx:999-broken

# Debug
sleep 15
kubectl describe pod -n bookstore -l app=frontend | grep -A2 "Events"

# Fix
kubectl set image deployment/frontend -n bookstore web=nginx:1.25
```

---

### 8.4 Verification & Testing

```bash
echo "=== FINAL VERIFICATION ==="

echo "--- Pods ---"
kubectl get pods -n bookstore -o wide

echo "--- Resources ---"
kubectl get pods -n bookstore -o custom-columns=\
NAME:.metadata.name,\
CPU_REQ:.spec.containers[0].resources.requests.cpu,\
MEM_LIM:.spec.containers[0].resources.limits.memory

echo "--- HPA ---"
kubectl get hpa -n bookstore

echo "--- PDB ---"
kubectl get pdb -n bookstore

echo "--- NetworkPolicy ---"
kubectl get networkpolicy -n bookstore

echo "--- ServiceAccounts ---"
kubectl get sa -n bookstore

echo "--- Kyverno Policies ---"
kubectl get clusterpolicy

echo "--- Endpoints ---"
kubectl get endpoints -n bookstore

echo "--- Production Score ---"
# Count passed items
PASS=0
TOTAL=12

# W1: Resources
kubectl get pods -n bookstore -o json | jq -e '[.items[].spec.containers[] | select(.resources.requests!=null)] | length > 0' > /dev/null && PASS=$((PASS+1))
# W3+W4: Probes
kubectl get pods -n bookstore -o json | jq -e '[.items[].spec.containers[] | select(.livenessProbe!=null)] | length > 0' > /dev/null && PASS=$((PASS+1))
# W9: Replicas >= 2
[ "$(kubectl get deploy frontend -n bookstore -o jsonpath='{.spec.replicas}')" -ge 2 ] && PASS=$((PASS+1))
# HPA
kubectl get hpa -n bookstore --no-headers | wc -l | grep -q "[1-9]" && PASS=$((PASS+1))
# PDB
kubectl get pdb -n bookstore --no-headers | wc -l | grep -q "[1-9]" && PASS=$((PASS+1))
# NetworkPolicy
kubectl get networkpolicy -n bookstore --no-headers | wc -l | grep -q "[1-9]" && PASS=$((PASS+1))
# ServiceAccount (not default)
kubectl get deploy -n bookstore -o json | jq -e '[.items[] | select(.spec.template.spec.serviceAccountName!=null and .spec.template.spec.serviceAccountName!="default")] | length > 0' > /dev/null && PASS=$((PASS+1))
# Kyverno policies
kubectl get clusterpolicy --no-headers | wc -l | grep -q "[1-9]" && PASS=$((PASS+1))
# Endpoints populated
EMPTY=$(kubectl get endpoints -n bookstore -o json | jq '[.items[] | select(.subsets==null)] | length')
[ "$EMPTY" -eq 0 ] && PASS=$((PASS+1))
# Labels
kubectl get deploy -n bookstore -o json | jq -e '[.items[] | select(.metadata.labels.team!=null)] | length > 0' > /dev/null && PASS=$((PASS+1))

echo "Score: $PASS/$TOTAL ($((PASS*100/TOTAL))%)"
```

---

### 8.5 Deliverables Checklist

- [ ] **Updated manifests**: Tất cả YAML files (task1 → task6)
- [ ] **Security checklist**: Điền form từ Day 24 document.md
- [ ] **Scaling test report**: HPA status + load test result (nếu chạy được)
- [ ] **Incident runbooks**: 5 runbooks theo template dưới đây

### Runbook Template

```markdown
# Runbook: [Tên lỗi]

### Symptom
- [Mô tả dấu hiệu]

### Severity
- P1/P2/P3

### Detection
- Alert: [tên alert nếu có]
- Command: `kubectl get pods -n bookstore | grep -v Running`

### Debug Steps
1. `[command 1]` → tìm gì?
2. `[command 2]` → tìm gì?
3. `[command 3]` → confirm hypothesis

### Fix
```bash
# [command fix]
```

### Verify
```bash
# [command verify]
```

### Prevention
- [Làm gì để không xảy ra lại]
```

### 5 Required Runbooks

1. **Service OOMKilled** — container vượt memory limit
2. **Service Routing Failure** — service selector mismatch, empty endpoints
3. **ImagePullBackOff** — wrong image tag, registry auth issue
4. **Pod Pending** — insufficient resources, taint/toleration
5. **High Latency / CPU Throttling** — CPU limit quá thấp, cần right-size

---

### 8.6 Self-review Checklist (Day 24)

### Before Hardening

| Category | Score |
|----------|-------|
| Workload | 0/12 |
| Security | 0/14 |
| Total | ~0% |

### After Hardening

| Category | Score |
|----------|-------|
| Workload | 8/12 |
| Security | 6/14 |
| Total | ~55-65% |

### Remaining Gaps (for future work)

- [ ] Monitoring stack (Prometheus + Grafana) — Phase 6
- [ ] Structured logging — Phase 6
- [ ] CI/CD pipeline — Phase 5
- [ ] Secret management — External Secrets
- [ ] Image signing — cosign
- [ ] DR plan + Velero — Day 23 advanced

---

### 8.7 Cleanup

```bash
# Remove Kyverno
helm uninstall kyverno -n kyverno
kubectl delete namespace kyverno

# Remove bookstore
kubectl delete namespace bookstore

# Delete cluster
kind delete cluster --name bookstore-prod
```

---

## 9. Common Pitfalls & Debugging

| Pitfall | Dấu hiệu | Debug command | Cách xử lý |
|---------|----------|---------------|------------|
| HPA không có metrics | `TARGETS <unknown>/70%` | `kubectl describe hpa -n bookstore` | Kiểm tra metrics-server và CPU requests |
| Pod bị OOMKilled sau hardening | `Last State: OOMKilled`, exit 137 | `kubectl describe pod ...` | Tăng memory limit hoặc fix leak/right-size |
| Service không có endpoints | `ENDPOINTS <none>` | `kubectl get ep -n bookstore` | So selector của Service với label của Pod |
| Traffic nội bộ timeout | App gọi service khác bị timeout | `kubectl get netpol -n bookstore` | Thêm allow rule đúng chiều ingress/egress |
| Kyverno block rollout hợp lệ | `admission webhook denied` | `kubectl describe clusterpolicy <name>` | Chuyển policy về Audit, thêm exception có expiry |
| Drain node bị kẹt | `Cannot evict pod as it would violate PDB` | `kubectl get pdb -n bookstore` | Tăng replicas/capacity hoặc điều chỉnh PDB |

Debug flow chuẩn cho mini-project:

1. Xác định scope: `kubectl get pods,svc,ep,hpa,pdb,netpol -n bookstore`.
2. Chọn symptom lớn nhất trước: Pending/ImagePull/OOM/No endpoints/Network deny.
3. Dùng `kubectl describe` để lấy Events, không đoán từ YAML.
4. Fix nhỏ nhất có thể, verify bằng command cụ thể.
5. Ghi runbook: symptom, root cause, command debug, command fix, prevention.

Case study nhỏ: sau khi bật default deny egress, frontend và API gateway đều Running nhưng request tới service nội bộ timeout. Pod không crash nên liveness/readiness đều xanh. Root cause là NetworkPolicy chỉ allow ingress mà quên egress DNS và egress tới service downstream. Fix đúng là thêm allow egress DNS + allow egress theo label đích, không phải restart pod hay tăng replicas.

---

## 10. Kết nối với bài trước & bài sau

### Phase 3 Summary

Day 25 kết thúc **Phase 3: Kubernetes Production**. Bạn đã học:

| Day | Topic | Skill |
|-----|-------|-------|
| 18 | Resources, QoS | Right-size workloads |
| 19 | Autoscaling | HPA, VPA, KEDA |
| 20 | RBAC, PSS, NetworkPolicy | Secure cluster |
| 21 | Admission Controllers | Policy as Code |
| 22 | Troubleshooting | Systematic debugging |
| 23 | Upgrade, Backup | Maintenance operations |
| 24 | Production Checklist | Assessment framework |
| 25 | **Mini-project** | **Apply all together** |

### Phase 4 Preview (Day 26+): Infrastructure as Code & GitOps

- Day 26: IaC Principles
- Day 27: Terraform Fundamentals
- Day 28: Terraform Advanced
- Day 29: Pulumi vs Terraform vs CDK
- Day 30: Ansible
- Day 31: GitOps with ArgoCD & Flux

---

## 11. Tài liệu tham khảo

### Must-read

- [Kubernetes Production Best Practices (learnk8s.io)](https://learnk8s.io/production-best-practices)
- [Kubernetes Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)

### Nice-to-have

- [Polaris — Best Practices Validation](https://github.com/FairwindsOps/polaris)
- [Kubescape — Security Scanner](https://github.com/kubescape/kubescape)

### Deep-dive

- [NSA/CISA Kubernetes Hardening Guide](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)

