# Bài thực hành - Day 28: Kafka on Kubernetes

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `bitnami/kafka:3.7.0`.
- Có StorageClass mặc định.
- Shell mặc định cho lab là Linux/WSL/Bash. Nếu dùng PowerShell, thay các biến như `PV_NAME=$(...)` bằng `$PV_NAME = kubectl ...`.

## Lab Scenario

Bạn sẽ deploy Kafka single-broker KRaft dạng lab, tạo topic, produce/consume messages, restart broker để kiểm tra persistence, thử tạo topic replication factor `3` để thấy constraint của single broker, và viết worksheet mapping sang Strimzi.

Lab này không phải production Kafka.

Core Path dự kiến 115 phút. Strimzi mapping nằm trong Stretch Goals để giữ lab trong 2 giờ.

## Task 1: Tạo namespace và kiểm tra storage (5 phút)

```bash
kubectl create namespace day28
kubectl config set-context --current --namespace=day28
kubectl get storageclass
```

## Task 2: Deploy Kafka single-broker KRaft (35 phút)

Tạo file `kafka-lab.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kafka
spec:
  selector:
    app: kafka
  ports:
  - name: plaintext
    port: 9092
    targetPort: 9092
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-headless
spec:
  clusterIP: None
  selector:
    app: kafka
  ports:
  - name: plaintext
    port: 9092
    targetPort: 9092
  - name: controller
    port: 9093
    targetPort: 9093
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
spec:
  serviceName: kafka-headless
  replicas: 1
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      securityContext:
        fsGroup: 1001
      containers:
      - name: kafka
        image: bitnami/kafka:3.7.0
        ports:
        - name: plaintext
          containerPort: 9092
        - name: controller
          containerPort: 9093
        env:
        - name: KAFKA_ENABLE_KRAFT
          value: "yes"
        - name: KAFKA_KRAFT_CLUSTER_ID
          value: "abcdefghijklmnopqrstuv"
        - name: KAFKA_CFG_NODE_ID
          value: "0"
        - name: KAFKA_CFG_PROCESS_ROLES
          value: "broker,controller"
        - name: KAFKA_CFG_CONTROLLER_QUORUM_VOTERS
          value: "0@kafka-0.kafka-headless.day28.svc.cluster.local:9093"
        - name: KAFKA_CFG_LISTENERS
          value: "PLAINTEXT://:9092,CONTROLLER://:9093"
        - name: KAFKA_CFG_ADVERTISED_LISTENERS
          value: "PLAINTEXT://kafka-0.kafka-headless.day28.svc.cluster.local:9092"
        - name: KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP
          value: "PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT"
        - name: KAFKA_CFG_CONTROLLER_LISTENER_NAMES
          value: "CONTROLLER"
        - name: KAFKA_CFG_INTER_BROKER_LISTENER_NAME
          value: "PLAINTEXT"
        - name: KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_CFG_TRANSACTION_STATE_LOG_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_CFG_TRANSACTION_STATE_LOG_MIN_ISR
          value: "1"
        - name: KAFKA_CFG_DEFAULT_REPLICATION_FACTOR
          value: "1"
        - name: KAFKA_CFG_MIN_INSYNC_REPLICAS
          value: "1"
        - name: KAFKA_CFG_NUM_PARTITIONS
          value: "3"
        - name: KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE
          value: "false"
        - name: ALLOW_PLAINTEXT_LISTENER
          value: "yes"
        startupProbe:
          exec:
            command:
            - sh
            - -c
            - kafka-broker-api-versions.sh --bootstrap-server 127.0.0.1:9092 >/dev/null 2>&1
          periodSeconds: 10
          failureThreshold: 30
          timeoutSeconds: 5
        readinessProbe:
          exec:
            command:
            - sh
            - -c
            - kafka-broker-api-versions.sh --bootstrap-server 127.0.0.1:9092 >/dev/null 2>&1
          periodSeconds: 10
          timeoutSeconds: 5
        livenessProbe:
          exec:
            command:
            - sh
            - -c
            - kafka-broker-api-versions.sh --bootstrap-server 127.0.0.1:9092 >/dev/null 2>&1
          initialDelaySeconds: 120
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3
        resources:
          requests:
            cpu: 250m
            memory: 768Mi
          limits:
            memory: 1536Mi
        volumeMounts:
        - name: data
          mountPath: /bitnami/kafka
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes:
      - ReadWriteOnce
      resources:
        requests:
          storage: 2Gi
```

Apply:

```bash
kubectl apply -f kafka-lab.yaml
kubectl rollout status statefulset/kafka --timeout=300s
kubectl get pod,pvc,svc -o wide
kubectl logs kafka-0 --tail=80
```

### Expected output

- Pod `kafka-0` Running và Ready.
- PVC `data-kafka-0` Bound.
- Logs không còn lỗi startup/quorum.
- `startupProbe` bảo vệ broker khỏi liveness restart trong lúc boot/recovery.

## Task 3: Tạo Kafka client Pod (10 phút)

```bash
kubectl run kafka-client \
  --image=bitnami/kafka:3.7.0 \
  --restart=Never \
  --command -- sleep 3600

kubectl wait --for=condition=Ready pod/kafka-client --timeout=120s
```

Test metadata:

```bash
kubectl exec kafka-client -- kafka-broker-api-versions.sh --bootstrap-server kafka:9092
```

### Expected output

- Client bootstrap qua Service `kafka:9092`.
- Broker metadata trả về được.

## Task 4: Tạo topic, produce và consume (25 phút)

Tạo topic:

```bash
kubectl exec kafka-client -- kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create \
  --topic orders \
  --partitions 3 \
  --replication-factor 1
```

Describe topic:

```bash
kubectl exec kafka-client -- kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic orders
```

Produce messages:

```bash
kubectl exec kafka-client -- sh -c 'printf "order-1\norder-2\norder-3\n" | kafka-console-producer.sh --bootstrap-server kafka:9092 --topic orders'
```

Consume messages:

```bash
kubectl exec kafka-client -- kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic orders \
  --from-beginning \
  --timeout-ms 5000
```

### Expected output

- Topic `orders` có 3 partitions.
- Messages `order-1`, `order-2`, `order-3` được consume.
- Replication factor là `1` vì chỉ có một broker.

## Task 5: Kiểm tra persistence qua broker restart (20 phút)

```bash
kubectl delete pod kafka-0
kubectl rollout status statefulset/kafka --timeout=300s
kubectl exec kafka-client -- kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic orders \
  --from-beginning \
  --timeout-ms 5000
```

Map PVC/PV:

```bash
PV_NAME=$(kubectl get pvc data-kafka-0 -o jsonpath='{.spec.volumeName}')
kubectl describe pvc data-kafka-0
kubectl describe pv "$PV_NAME"
```

### Expected output

- Messages vẫn đọc lại được sau restart.
- Data nằm trong Kafka log segments trên PVC.
- Đây là restart recovery, không phải broker failure tolerance.

## Task 6: Thử replication factor không hợp lệ (10 phút)

Single broker không thể tạo topic replication factor `3`:

```bash
kubectl exec kafka-client -- kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create \
  --topic impossible-rf3 \
  --partitions 3 \
  --replication-factor 3
```

### Expected output

- Command fail vì replication factor lớn hơn số broker available.
- Bạn thấy rõ single-broker lab không thể chịu lỗi broker.

## Task 7: Inspect Kafka signals (10 phút)

```bash
kubectl exec kafka-client -- kafka-topics.sh --bootstrap-server kafka:9092 --list
kubectl exec kafka-client -- kafka-consumer-groups.sh --bootstrap-server kafka:9092 --list
kubectl logs kafka-0 --tail=120
kubectl describe pod kafka-0
kubectl get events --sort-by=.lastTimestamp
```

Ghi chú:

```text
Broker Pod:
PVC:
Advertised listener:
Topic:
Partitions:
Replication factor:
Consumer groups:
Interesting log lines:
```

## Verification cuối Core Path

```bash
kubectl get statefulset,pod,pvc,svc,endpoints -o wide
kubectl exec kafka-client -- kafka-broker-api-versions.sh --bootstrap-server kafka:9092 >/dev/null
kubectl exec kafka-client -- kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic orders
kubectl logs kafka-0 --tail=40
```

Expected:

- Broker `kafka-0` Ready.
- Topic `orders` tồn tại với replication factor `1`.
- RF=3 fail trong single-broker lab.
- Bạn chỉ kết luận được restart recovery, không kết luận HA.

## Stretch Goal: Strimzi mapping worksheet (30 phút)

Không cần cài Strimzi trong bài này. Tạo file `day28-strimzi-notes.md`:

```text
Kafka CR would define:
Broker count:
Controller/quorum model:
Storage class and size:
Internal listener:
External listener:
Topic management:
User/ACL management:
Kafka Connect need:
MirrorMaker2/DR need:
Rebalance strategy:
Monitoring integration:
Upgrade strategy:
Why Strimzi is safer than hand-written StatefulSet:
Remaining risks:
```

Điền theo một scenario production giả định:

```text
3 brokers, 3 controllers, RF=3, min.insync.replicas=2, internal apps only, 7-day retention.
```

## Cleanup

```bash
kubectl delete namespace day28
```

Nếu còn PV dynamic do reclaim policy:

```bash
kubectl get pv
kubectl describe pv <pv-name>
```

## Câu hỏi tự kiểm tra

1. Vì sao Kafka cần `advertised.listeners` đúng?
2. StatefulSet giúp gì cho Kafka broker identity?
3. Replication factor, ISR và `min.insync.replicas` liên quan thế nào?
4. Vì sao single-broker Kafka không phải production HA?
5. Strimzi giải quyết phần nào và không giải quyết phần nào?
