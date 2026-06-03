# Day 19: Document — Autoscaling Reference

---

## 1. Autoscaler Comparison Matrix

| Tiêu chí | HPA | VPA | Cluster Autoscaler | KEDA |
|-----------|-----|-----|--------------------|------|
| **Scale target** | Pod replicas | Container resources | Cluster nodes | Pod replicas |
| **Direction** | Horizontal | Vertical | Horizontal (infra) | Horizontal |
| **Default metrics** | CPU, Memory | CPU, Memory history | Pending pods | External events |
| **Custom metrics** | Có (Prometheus adapter) | Không | Không | Có (60+ triggers) |
| **Scale to zero** | Không (min=1) | N/A | Có (nodes) | **Có** |
| **Pod restart** | Không | Có (Auto mode) | Không trực tiếp | Không |
| **Reaction time** | 15-60s | Minutes | 2-7 phút | 15-30s |
| **Built-in K8s** | Có | Không (addon) | Không (addon) | Không (addon) |
| **Production maturity** | Rất cao | Cao | Rất cao | Cao |
| **Best for** | Stateless APIs | Right-sizing | Cloud elasticity | Event-driven |

---

## 2. HPA Configuration Cheat Sheet

### Tạo HPA nhanh

```bash
# CLI tạo HPA đơn giản
kubectl autoscale deployment <name> --cpu-percent=70 --min=2 --max=10

# Xem HPA
kubectl get hpa
kubectl describe hpa <name>
kubectl get hpa <name> -o yaml
```

### HPA YAML Templates

#### Basic — CPU only

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: basic-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

#### Multi-metric — CPU + Memory

```yaml
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Custom metric — Prometheus

```yaml
metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 100
```

#### Aggressive scale-up, conservative scale-down

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0    # Scale up ngay
    policies:
      - type: Percent
        value: 100                    # Double replicas
        periodSeconds: 60
      - type: Pods
        value: 5
        periodSeconds: 60
    selectPolicy: Max
  scaleDown:
    stabilizationWindowSeconds: 300  # Đợi 5 phút
    policies:
      - type: Pods
        value: 1                      # 1 pod mỗi 2 phút
        periodSeconds: 120
    selectPolicy: Min
```

---

## 3. KEDA Trigger Quick Reference

| Trigger | Use Case | Key Parameters |
|---------|----------|----------------|
| **kafka** | Consumer lag | `bootstrapServers`, `topic`, `consumerGroup`, `lagThreshold` |
| **rabbitmq** | Queue depth | `host`, `queueName`, `queueLength` |
| **prometheus** | Custom metrics | `serverAddress`, `query`, `threshold` |
| **cron** | Scheduled scaling | `timezone`, `start`, `end`, `desiredReplicas` |
| **aws-sqs-queue** | SQS messages | `queueURL`, `queueLength`, `awsRegion` |
| **redis-streams** | Stream lag | `address`, `stream`, `consumerGroup`, `lagCount` |
| **postgresql** | Query result | `connectionString`, `query`, `targetQueryValue` |
| **http** | HTTP metric | `url`, `valueLocation`, `targetValue` |

### KEDA ScaledObject Template

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: my-scaledobject
spec:
  scaleTargetRef:
    name: my-deployment
  minReplicaCount: 0
  maxReplicaCount: 30
  pollingInterval: 15        # Check mỗi 15s
  cooldownPeriod: 300        # Đợi 5 phút trước scale to zero
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: my-group
        topic: my-topic
        lagThreshold: "50"
```

---

## 4. Scaling Decision Flowchart

```
Workload cần autoscale?
│
├── Stateful (Database, Cache)?
│   └── KHÔNG autoscale replicas
│       └── Dùng VPA Off mode → xem recommendation → manual adjust
│
├── Stateless API/Web?
│   ├── Traffic-driven?
│   │   └── HPA (CPU 60-70%, min=2 cho HA)
│   ├── Latency-sensitive?
│   │   └── HPA + aggressive scale-up + slow scale-down
│   └── Bursty traffic (flash sales)?
│       └── HPA + KEDA cron (pre-scale trước events)
│
├── Worker/Consumer?
│   ├── Queue-driven?
│   │   └── KEDA (queue lag trigger)
│   ├── Cron/Scheduled?
│   │   └── KEDA (cron trigger, scale to zero)
│   └── Event-driven?
│       └── KEDA (event trigger)
│
├── Batch Job?
│   └── Không dùng autoscaler
│       └── Set concurrency trong Job spec
│
└── Cluster-level?
    └── Cluster Autoscaler
        └── Khi pods Pending do không đủ nodes
```

---

## 5. Load Testing Quick Reference

### hey

```bash
# Install
# Linux: wget https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64
# macOS: brew install hey

# Basic load test
hey -n 10000 -c 50 http://localhost:8080/

# Duration-based
hey -z 120s -c 100 http://localhost:8080/

# With custom headers
hey -z 60s -c 50 -H "Authorization: Bearer token" http://localhost:8080/api

# POST request
hey -z 60s -c 20 -m POST -d '{"key":"value"}' \
  -T "application/json" http://localhost:8080/api
```

### k6

```javascript
// load-test.js
import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 20 },   // Ramp up
    { duration: '3m', target: 50 },   // Sustain
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // P95 < 500ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
  },
};

export default function () {
  const res = http.get('http://localhost:8080/');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.1);
}
```

```bash
# Run k6
k6 run load-test.js
```

### kubectl load generator

```bash
# Quick inline load generator
kubectl run -i --tty load-gen --rm --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while sleep 0.01; do wget -q -O- http://my-service; done"
```

---

## 6. Production Autoscaling Checklist

### Pre-deployment

- [ ] Resource requests set cho tất cả containers (HPA cần requests)
- [ ] Metrics-server hoặc Prometheus adapter installed
- [ ] `minReplicas >= 2` cho production services
- [ ] `maxReplicas` set hợp lý (cost control)
- [ ] PodDisruptionBudget configured

### HPA Configuration

- [ ] Target utilization 60-80% (không quá cao, không quá thấp)
- [ ] Scale-up policies defined (fast enough for traffic spikes)
- [ ] Scale-down stabilization window >= 300s (avoid flapping)
- [ ] Scale-down policy: gradual (1-2 pods per period)

### Operations

- [ ] Alert khi replicas gần maxReplicas (> 80%)
- [ ] Alert khi HPA metrics unavailable
- [ ] Monitor scaling events: `kubectl get events --field-selector reason=SuccessfulRescale`
- [ ] Review scaling behavior weekly (adjust thresholds if needed)
- [ ] Document autoscaling strategy cho mỗi service

### Cost Management

- [ ] Review monthly: actual replicas vs max replicas (right-size max)
- [ ] Consider node autoscaler limits (max nodes)
- [ ] KEDA scale-to-zero cho idle workloads
- [ ] Spot instances cho non-critical scaled workloads

---

## 7. Cost Implications Table

| Config | Avg Pods | Peak Pods | Monthly Cost* | Availability |
|--------|----------|-----------|--------------|-------------|
| Static 10 pods | 10 | 10 | $500 | High (over-provisioned) |
| HPA min=2, max=20 | ~5 | 20 | $250 | High |
| HPA min=1, max=10 | ~3 | 10 | $150 | Medium-High |
| KEDA min=0, max=15 | ~2 | 15 | $100 | Medium (cold start) |
| No scaling, 2 pods | 2 | 2 | $100 | Low (peak drops) |

*Giả sử $50/pod/month

### Savings Formula

```
Monthly savings = (static_pods - avg_autoscaled_pods) × cost_per_pod
ROI = savings / setup_cost

Example:
  Static: 20 pods × $50 = $1,000/mo
  Autoscaled: avg 6 pods × $50 = $300/mo
  Savings: $700/mo
  Setup cost: ~$2,000 (engineering time)
  ROI payback: < 3 months
```

