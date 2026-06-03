# Bài thực hành - Day 45: Capstone Project Part 2

## Prerequisites

- Hoàn thành Day 44 hoặc có Helm release `logistics` trong namespace `logistics`.
- `kubectl` trỏ đúng context.
- `helm` nếu cần cài `metrics-server` hoặc monitoring stack.
- ArgoCD đã cài từ Day 41 nếu muốn apply `Application`.
- Cluster có đủ tài nguyên cho Redis, PostgreSQL và Kafka single-broker lab. Nếu Kafka không chạy nổi trên laptop, vẫn commit manifest và ghi rõ blocker trong final review.

## Lab Scenario

Bạn sẽ biến capstone từ stateless routing thành bản lab có implementation tối thiểu:

- PDB/HPA cho stateless services.
- Redis, PostgreSQL và Kafka single-node lab.
- NetworkPolicy có default deny, DNS egress và rule traffic cần thiết.
- PostgreSQL `pg_dump` backup Job.
- ArgoCD `Application` trỏ tới Git repo thật.
- Monitoring baseline bằng `metrics-server` hoặc kube-prometheus-stack nếu cluster đủ tài nguyên.

Core path khoảng 115-120 phút nếu image pull ổn. Những phần nặng như kube-prometheus-stack, Strimzi production và PITR được để ở stretch.

## Task 1: Kiểm tra trạng thái Day 44 (10 phút)

```bash
kubectl get namespace logistics
helm status logistics -n logistics
kubectl get deploy,svc,pod -n logistics
kubectl get ingress,endpointslice -n logistics
```

Test gateway bằng debug Pod riêng:

```bash
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl run curl -n logistics --rm -i --restart=Never --image=curlimages/curl:8.7.1 -- http://api-gateway/tracking
```

### Expected output

- Helm release tồn tại.
- Gateway trả `order-service` và `tracking-service`.

## Task 2: Thêm PDB và HPA baseline (15 phút)

Tạo `platform-controls.yaml`:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-gateway
  namespace: logistics
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service
  namespace: logistics
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: order-service
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tracking-service
  namespace: logistics
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: tracking-service
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway
  namespace: logistics
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
  namespace: logistics
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tracking-service
  namespace: logistics
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tracking-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

Apply:

```bash
kubectl apply -f platform-controls.yaml
kubectl get pdb,hpa -n logistics
kubectl describe hpa api-gateway -n logistics
```

Nếu HPA báo metrics unavailable, ghi rõ `metrics-server` hoặc custom metrics pipeline là prerequisite production.

## Task 3: Deploy Redis, PostgreSQL và Kafka lab (35 phút)

Tạo `stateful-dependencies.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: logistics
type: Opaque
stringData:
  POSTGRES_PASSWORD: lab-password
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: logistics
spec:
  selector:
    app.kubernetes.io/name: postgres
  ports:
  - name: postgres
    port: 5432
    targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: logistics
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: postgres
  template:
    metadata:
      labels:
        app.kubernetes.io/name: postgres
        app.kubernetes.io/component: database
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_PASSWORD
        ports:
        - containerPort: 5432
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          periodSeconds: 5
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 512Mi
        volumeMounts:
        - name: pgdata
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: pgdata
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: logistics
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: redis
  template:
    metadata:
      labels:
        app.kubernetes.io/name: redis
        app.kubernetes.io/component: cache
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        args:
        - redis-server
        - --appendonly
        - "yes"
        ports:
        - containerPort: 6379
        readinessProbe:
          exec:
            command:
            - redis-cli
            - ping
          periodSeconds: 5
        resources:
          requests:
            cpu: 50m
            memory: 128Mi
          limits:
            memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: logistics
spec:
  selector:
    app.kubernetes.io/name: redis
  ports:
  - name: redis
    port: 6379
    targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka
  namespace: logistics
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: kafka
  template:
    metadata:
      labels:
        app.kubernetes.io/name: kafka
        app.kubernetes.io/component: event-bus
    spec:
      containers:
      - name: kafka
        image: bitnami/kafka:3.7
        env:
        - name: KAFKA_CFG_NODE_ID
          value: "0"
        - name: KAFKA_CFG_PROCESS_ROLES
          value: controller,broker
        - name: KAFKA_CFG_CONTROLLER_QUORUM_VOTERS
          value: 0@kafka:9093
        - name: KAFKA_CFG_LISTENERS
          value: PLAINTEXT://:9092,CONTROLLER://:9093
        - name: KAFKA_CFG_ADVERTISED_LISTENERS
          value: PLAINTEXT://kafka:9092
        - name: KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP
          value: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
        - name: KAFKA_CFG_CONTROLLER_LISTENER_NAMES
          value: CONTROLLER
        - name: KAFKA_CFG_INTER_BROKER_LISTENER_NAME
          value: PLAINTEXT
        - name: KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_CFG_TRANSACTION_STATE_LOG_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_CFG_TRANSACTION_STATE_LOG_MIN_ISR
          value: "1"
        - name: ALLOW_PLAINTEXT_LISTENER
          value: "yes"
        ports:
        - name: broker
          containerPort: 9092
        - name: controller
          containerPort: 9093
        readinessProbe:
          tcpSocket:
            port: 9092
          initialDelaySeconds: 20
          periodSeconds: 10
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
          limits:
            memory: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: kafka
  namespace: logistics
spec:
  selector:
    app.kubernetes.io/name: kafka
  ports:
  - name: broker
    port: 9092
    targetPort: 9092
  - name: controller
    port: 9093
    targetPort: 9093
```

Apply và verify:

```bash
kubectl apply -f stateful-dependencies.yaml
kubectl rollout status statefulset/postgres -n logistics
kubectl rollout status deploy/redis -n logistics
kubectl rollout status deploy/kafka -n logistics --timeout=300s
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "SELECT 1;"'
kubectl exec deploy/redis -n logistics -- redis-cli ping
kubectl exec deploy/kafka -n logistics -- kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic order-events --partitions 1 --replication-factor 1
kubectl exec deploy/kafka -n logistics -- kafka-topics.sh --bootstrap-server kafka:9092 --list
```

### Expected output

- PostgreSQL trả `SELECT 1`.
- Redis trả `PONG`.
- Kafka có topic `order-events`.

## Task 4: Apply NetworkPolicy baseline có DNS egress (20 phút)

Trước khi apply, xác nhận CNI có enforce NetworkPolicy. K3s mặc định với Flannel thường không enforce nếu không có policy-capable CNI.

Tạo `networkpolicy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: logistics
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: logistics
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-to-gateway
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
  policyTypes:
  - Ingress
  ingress:
  - ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-debug-egress
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: debug
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: api-gateway
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-egress-to-backends
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: api-gateway
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchExpressions:
        - key: app.kubernetes.io/name
          operator: In
          values:
          - order-service
          - tracking-service
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-gateway-to-backends
  namespace: logistics
spec:
  podSelector:
    matchExpressions:
    - key: app.kubernetes.io/name
      operator: In
      values:
      - order-service
      - tracking-service
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: api-gateway
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-services-egress-to-data
  namespace: logistics
spec:
  podSelector:
    matchExpressions:
    - key: app.kubernetes.io/name
      operator: In
      values:
      - order-service
      - tracking-service
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchExpressions:
        - key: app.kubernetes.io/name
          operator: In
          values:
          - postgres
          - redis
          - kafka
    ports:
    - protocol: TCP
      port: 5432
    - protocol: TCP
      port: 6379
    - protocol: TCP
      port: 9092
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-kafka-self
  namespace: logistics
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: kafka
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: kafka
    ports:
    - protocol: TCP
      port: 9092
    - protocol: TCP
      port: 9093
  egress:
  - to:
    - podSelector:
        matchLabels:
          app.kubernetes.io/name: kafka
    ports:
    - protocol: TCP
      port: 9092
    - protocol: TCP
      port: 9093
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-data-ingress-from-services
  namespace: logistics
spec:
  podSelector:
    matchExpressions:
    - key: app.kubernetes.io/name
      operator: In
      values:
      - postgres
      - redis
      - kafka
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchExpressions:
        - key: app.kubernetes.io/name
          operator: In
          values:
          - order-service
          - tracking-service
    ports:
    - protocol: TCP
      port: 5432
    - protocol: TCP
      port: 6379
    - protocol: TCP
      port: 9092
```

Apply và test:

```bash
kubectl apply -f networkpolicy.yaml
kubectl get networkpolicy -n logistics
kubectl run curl -n logistics --rm -i --restart=Never --labels=app.kubernetes.io/component=debug --image=curlimages/curl:8.7.1 -- http://api-gateway/orders
kubectl exec deploy/redis -n logistics -- redis-cli ping
```

### Câu hỏi

- CNI của bạn có enforce policy không?
- Vì sao default deny egress cần DNS rule?
- Ingress controller ở namespace khác có cần rule riêng không nếu bạn giới hạn source chặt hơn?

## Task 5: PostgreSQL backup Job và restore smoke test (20 phút)

Tạo `pg-backup-job.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pg-backup
  namespace: logistics
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: batch/v1
kind: Job
metadata:
  name: pg-dump-manual
  namespace: logistics
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: pg-dump
        image: postgres:16-alpine
        env:
        - name: PGPASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_PASSWORD
        command:
        - sh
        - -c
        - |
          pg_dump -h postgres -U postgres postgres > /backup/logistics.sql
          ls -lh /backup/logistics.sql
        volumeMounts:
        - name: backup
          mountPath: /backup
      volumes:
      - name: backup
        persistentVolumeClaim:
          claimName: pg-backup
```

Apply:

```bash
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=lab-password psql -U postgres -c "CREATE TABLE IF NOT EXISTS restore_probe(id int primary key); INSERT INTO restore_probe VALUES (1) ON CONFLICT DO NOTHING;"'
kubectl apply -f pg-backup-job.yaml
kubectl wait --for=condition=complete job/pg-dump-manual -n logistics --timeout=120s
kubectl logs job/pg-dump-manual -n logistics
```

Restore smoke test trong cùng database:

```bash
kubectl cp logistics/$(kubectl get pod -n logistics -l job-name=pg-dump-manual -o jsonpath='{.items[0].metadata.name}'):/backup/logistics.sql ./logistics.sql
kubectl cp ./logistics.sql logistics/postgres-0:/tmp/logistics.sql
kubectl exec pod/postgres-0 -n logistics -- sh -c 'PGPASSWORD=lab-password psql -U postgres -f /tmp/logistics.sql'
```

### Expected output

- Job complete.
- Log hiển thị file `/backup/logistics.sql`.
- Restore command chạy không lỗi.

## Task 6: ArgoCD Application tối thiểu (15 phút)

Commit chart/manifests Day 44-45 vào Git repo thật. Tạo `argocd-application.yaml` và thay `repoURL/path`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: logistics-dev
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-user>/<your-repo>.git
    targetRevision: main
    path: capstone/logistics-stateless
    helm:
      valueFiles:
      - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: logistics
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

Apply nếu ArgoCD đã cài:

```bash
kubectl apply -f argocd-application.yaml
kubectl get applications -n argocd
kubectl describe application logistics-dev -n argocd
```

Nếu chưa có ArgoCD, vẫn lưu manifest này trong repo và ghi blocker.

## Task 7: Monitoring baseline (15 phút)

Đường nhẹ nhất là có `metrics-server` để `kubectl top` và HPA có current metrics:

```bash
kubectl top pods -n logistics
kubectl top nodes
```

Nếu chưa có metrics-server và cluster cho phép cài Helm chart:

```bash
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system \
  --set args="{--kubelet-insecure-tls}"
kubectl wait --for=condition=available deploy/metrics-server -n kube-system --timeout=180s
kubectl top pods -n logistics
```

Nếu muốn baseline đầy đủ hơn, dùng kube-prometheus-stack ở stretch vì chart này nặng hơn đáng kể.

## Task 8: Final production review (10 phút)

Tạo `final-production-review.md` và ghi evidence:

```markdown
# Final Production Review

## What runs now

## What is lab-only

## What changes on EKS/GKE/AKS

## Availability

## Scaling

## Security

## Observability

## Backup and DR

## GitOps release and rollback

## Known risks

## Next 5 improvements
```

Verification commands:

```bash
kubectl get all -n logistics
kubectl get hpa,pdb,networkpolicy -n logistics
kubectl get ingress,svc,endpointslice -n logistics
kubectl get pvc,job -n logistics
kubectl get applications -n argocd
kubectl get events -n logistics --sort-by=.lastTimestamp
```

## Cleanup

Giữ namespace nếu muốn demo final. Nếu muốn xóa lab:

```bash
kubectl delete application logistics-dev -n argocd
helm uninstall logistics -n logistics
kubectl delete namespace logistics
```

## Common Pitfalls

- Kafka single-broker lab cần nhiều RAM hơn Redis/PostgreSQL; nếu fail vì resource, ghi blocker thay vì gọi đó là production decision.
- NetworkPolicy không có tác dụng nếu CNI không enforce.
- Default deny egress mà thiếu DNS rule sẽ làm service discovery fail.
- HPA tồn tại nhưng metrics unavailable nếu thiếu metrics-server/custom metrics.
- GitOps restore được manifest, không restore database data.
- Backup Job có file dump nhưng chưa chạy restore validation thì chưa đạt DR drill.

## Stretch Goals

- Cài kube-prometheus-stack và tạo dashboard cho namespace `logistics`.
- Dùng External Secrets hoặc SOPS cho secret.
- Deploy PostgreSQL bằng CloudNativePG và bật backup/PITR.
- Deploy Kafka bằng Strimzi với `Kafka` CR thay vì single-broker Deployment.
- Viết load test nhỏ và quan sát HPA scale.
