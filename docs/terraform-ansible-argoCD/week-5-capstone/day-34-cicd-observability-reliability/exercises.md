# Day 34 — CI/CD, Observability, Reliability
## Exercises & Challenges

> 3 challenges + 2 bonus challenges. Mỗi challenge có phần bài tập và gợi ý. Dành 15-20 phút mỗi challenge.

---

## Challenge 1: Debug a Bad Image Push

**Độ khó:** Medium
**Thời gian:** 20 phút
**Mục tiêu:** Debug CI/CD pipeline failure, fix OIDC permission, và viết post-mortem.

### Bài tập

Bạn push code lên `main`, pipeline bắt đầu chạy nhưng fail ở job `build-and-push`:

```
Run Build and Push Image
  ✓ Checkout code
  ✓ Set up Docker Buildx
  ✓ GHCR Login
  ✓ Build and push image
    ghcr.io/myorg/api-service:a1b2c3d → pushed ✓
  ✓ Scan image with Trivy
    ✗ CRITICAL CVE found: CVE-2024-XXXXX in libssl3 (score: 9.8)
  ✗ FAILED: exit-code 1
```

**Câu hỏi:**

1. Tại sao pipeline fail? Trivy exit-code 1 nghĩa là gì?
2. Bạn muốn cho phép push image trong trường hợp này (staging env) nhưng vẫn có bước scan để team biết CVE? Sửa workflow thế nào?
3. Nếu là production environment, bạn sẽ xử lý CVE này thế nào?
4. Viết một `Dockerfile` mới cho `api-service` để fix CVE (dùng base image mới hơn).

### Gợi ý

```bash
# Bước 1: Check CVE details
trivy image --vuln-type os,library ghcr.io/myorg/api-service:a1b2c3d

# Bước 2: Update Dockerfile base image
# Trước: FROM node:18-alpine
# Sau:  FROM node:20-alpine  (hoặc node:18-alpine3.19)

# Bước 3: Rebuild và scan lại
docker build -t ghcr.io/myorg/api-service:a1b2c3d-new .
trivy image --severity CRITICAL ghcr.io/myorg/api-service:a1b2c3d-new
```

---

## Challenge 2: Alert Tuning — Reduce Alert Fatigue

**Độ khó:** Hard
**Thời gian:** 20 phút
**Mục tiêu:** Phân tích alert noise, viết alert quality checklist, và design better alerting strategy.

### Bài tập

Team nhận 47 alert/ngày. On-call developer phàn nàn: "cứ alert là Slack #alerts, nhưng 80% là không cần action". Bạn được giao task: giảm xuống dưới 10 alert/ngày mà không miss incident thật.

**Alert hiện tại:**

```yaml
# Alert 1
- alert: APIServiceContainerRestart
  expr: increase(kube_pod_container_status_restarts_total[5m]) > 0
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Container restarted"

# Alert 2
- alert: APIServiceHighMemoryUsage
  expr: |
    sum(container_memory_working_set_bytes{app="api-service"}) /
    sum(kube_pod_container_resource_limits_memory_bytes{app="api-service"}) > 0.7
  for: 5m
  labels:
    severity: warning

# Alert 3
- alert: APIServicePodDown
  expr: kube_pod_status_phase{phase="Running", app="api-service"} == 0
  for: 2m
  labels:
    severity: critical

# Alert 4
- alert: APIServiceCPUUsage
  expr: |
    sum(rate(container_cpu_usage_seconds_total{app="api-service"}[5m])) > 0.4
  for: 5m
  labels:
    severity: warning

# Alert 5
- alert: APIServiceHighErrorRate
  expr: |
    sum(rate(http_requests_total{status=~"5.."}[5m])) /
    sum(rate(http_requests_total[5m])) > 0.05
  for: 1m
  labels:
    severity: high
```

**Yêu cầu:**

1. Phân loại từng alert: Keep / Modify / Remove. Giải thích lý do.
2. Viết lại alert tốt hơn cho 3 alert cần modify (thêm context, thay đổi threshold, thêm runbook link).
3. Thiết kế alert routing: P1 → PagerDuty, P2 → Slack #incidents, P3 → Slack #alerts, P4 → ticket system.
4. Đề xuất SLO/SLA baseline cho API service (ví dụ: availability 99.9%, P95 latency < 1s).

### Gợi ý

```
Alert quality evaluation criteria:
  - Có action rõ ràng không?
  - Team có biết làm gì khi alert fire?
  - Alert này có predict incident sắp xảy ra?
  - False positive rate bao nhiêu?
  - Cần human response hay tự động fix được?
```

---

## Challenge 3: Reliability Design Review

**Độ khó:** Hard
**Thời gian:** 20 phút
**Mục tiêu:** Review reliability design cho 3 services, phát hiện gaps, và đề xuất improvements.

### Bài tập

Infrastructure team gửi design document cho 3 services. Review và đưa ra recommendations.

**Design hiện tại:**

```yaml
# api-service (Go, stateless)
deployment:
  replicas: 2
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  livenessProbe:
    httpGet:
      path: /healthz
      port: 8080
    initialDelaySeconds: 5

---
# worker-service (Python, có queue dependency)
deployment:
  replicas: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "50m"
    limits:
      memory: "256Mi"
      cpu: "100m"

---
# frontend-service (React, static, stateless)
deployment:
  replicas: 1
  resources:
    requests:
      memory: "64Mi"
      cpu: "50m"
    limits:
      memory: "128Mi"
      cpu: "200m"
```

**Câu hỏi:**

1. **Spot instance scenario:** Node chạy `worker-service` (replicas=1) bị Spot reclaim. Điều gì xảy ra?
2. Thiết kế lại toàn bộ reliability config cho cả 3 services. Với giả định:
   - `api-service`: stateless, high traffic, cần auto-scale
   - `worker-service`: có queue (Redis), cần graceful shutdown
   - `frontend-service`: stateless, CDN-able, replicas 3 cho HA
3. Tính toán memory + CPU requests sao cho cluster 4 node x `t3.medium` (2 vCPU, 4GB RAM) không bị resource pressure khi tất cả replicas running đồng thời.

### Gợi ý

```
Thiết kế reliability checklist:
  [ ] replicas >= 2 (nguyên tắc: không bao giờ replicas=1 cho production)
  [ ] HPA với minReplicas=2
  [ ] PDB với minAvailable=1 hoặc maxUnavailable=1
  [ ] topologySpreadConstraints (multi-zone)
  [ ] PodAntiAffinity (không cùng node)
  [ ] readinessProbe (cho tất cả service)
  [ ] livenessProbe (cho tất cả service)
  [ ] startupProbe (cho service startup > 10s)
  [ ] graceful termination (terminationGracePeriodSeconds)
  [ ] resource requests/limits (memory limit > request)
  [ ] Spot toleration (nếu dùng Spot node)
```

---

## Bonus Challenge 1: Multi-Service Observability Dashboard

**Độ khó:** Medium
**Thời gian:** 30 phút
**Mục tiêu:** Mở rộng Grafana dashboard cho cả 3 microservices.

### Bài tập

Viết thêm PrometheusRule và Grafana dashboard panel cho `worker-service`:

```yaml
# worker-service metrics endpoint: /metrics
# Các metrics cần có:
# - queue_depth (số messages trong queue)
# - processing_rate (messages/second)
# - error_count (lỗi xử lý)
# - job_duration_seconds (thời gian xử lý job)
```

**Yêu cầu:**

1. Viết PrometheusRule cho `worker-service` (3 alert rules minimum)
2. Thiết kế Grafana dashboard với 4 panels cho worker-service
3. Thêm row tổng hợp (overview) cho cả 3 services trên 1 dashboard

### Gợi ý

```yaml
# Alert: Queue backup
- alert: WorkerQueueBackup
  expr: queue_depth > 1000
  for: 5m
  labels:
    severity: high
  annotations:
    summary: "Worker queue has {{ $value }} messages pending"

# Alert: Worker error rate
- alert: WorkerHighErrorRate
  expr: |
    rate(error_count_total[5m]) /
    rate(processing_rate_total[5m]) > 0.1
  for: 5m
  labels:
    severity: medium
```

---

## Bonus Challenge 2: Production Incident Simulation

**Độ khó:** Hard
**Thời gian:** 30 phút
**Mục tiêu:** Simulate incident và viết full post-mortem.

### Bài tập

Simulate 3 incident scenarios. Với mỗi scenario, viết:

1. Symptoms (dấu hiệu observable)
2. Detection (alert nào fire, log nào check)
3. Root cause
4. Mitigation steps (kubectl commands)
5. Prevention (sửa design để không tái diễn)

**Scenario A: OOMKilled**

```
11:30 AM - On-call nhận Slack alert: "APIServiceOOMKilledHistory"
11:31 AM - Check kubectl: 3/3 pod đã restart trong 1 giờ
11:35 AM - Không ai deploy mới trong 2 giờ qua
Question: Tại sao pod restart? Làm sao prevent?
```

**Scenario B: HPA Thrashing**

```
2:00 PM - API latency tăng đột ngột
2:01 PM - HPA scale 2 → 10 replicas trong 2 phút
2:03 PM - Node không đủ resource → 5 pod pending
2:05 PM - Load drop → HPA scale 10 → 2 replicas
2:10 PM - Lather, repeat
Question: Tại sao thrashing? Fix bằng cách nào?
```

**Scenario C: Spot Reclaim + PDB Deadlock**

```
3:00 AM - AWS notify: Spot instance reclaim trong 2 phút
3:01 AM - Kubernetes bắt đầu drain node
3:02 AM - PDB: minAvailable=2 cho replicas=2 → không evict được
3:05 AM - Node termination blocked
3:10 AM - New Spot node không schedule được (resource pressure)
Question: Giải quyết deadlock thế nào? Làm sao avoid trong tương lai?
```

### Gợi ý

```bash
# Scenario A: Investigate OOMKilled
kubectl describe pod <pod-name> | grep -A10 "Last State"
kubectl top pod <pod-name>
kubectl get events --sort-by='.lastTimestamp' | grep OOM

# Fix: Tăng memory limit, check memory leak
# Prevention: Memory > 80% limit → alert

# Scenario B: Fix HPA thrashing
# 1. Tăng stabilizationWindowSeconds cho scaleDown: 300s
# 2. Giảm scaleUp policy: percent=50% thay vì 100%
# 3. Thêm custom metric cho scale decision

# Scenario C: Fix PDB deadlock
# Option 1: Dùng maxUnavailable: 1 thay vì minAvailable
# Option 2: Tăng replicas lên 3 (minAvailable=2)
# Option 3: Không dùng Spot cho stateful workload
```

---

## Exercise Solutions (Partial Reference)

### Challenge 1 Solution

**Q1:** Trivy exit-code 1 = scan fail vì có CRITICAL CVE. Pipeline được configure `exit-code: 1` nên fail.

**Q2:** Sửa workflow để staging không block:

```yaml
- name: Scan image with Trivy
  if: github.event_name != 'pull_request'
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
    exit-code: '0'  # Changed: warn nhưng không block
    severity: 'CRITICAL,HIGH'
  continue-on-error: true

- name: Upload Trivy scan results
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: 'trivy-results.sarif'
```

**Q4:** Fix Dockerfile:

```dockerfile
# Trước
FROM node:18-alpine3.17

# Sau
FROM node:20-alpine3.19  # libssl3 CVE fixed in alpine 3.19
# Hoặc
FROM node:18.21-alpine3.19
```

### Challenge 2 Solution (Alert Triage)

| Alert | Decision | Lý do |
|---|---|---|
| `ContainerRestart` | **REMOVE** | Restart là normal event (OOM recovery) — alert noise |
| `HighMemoryUsage` | **MODIFY** | Thêm: "Risk of OOMKilled if > 90% for 10m" |
| `PodDown` | **KEEP** | P1, cần response ngay lập tức |
| `CPUUsage` | **REMOVE** | Throttling mới là vấn đề, usage > 40% là bình thường |
| `HighErrorRate` | **KEEP + MODIFY** | Thêm: P95 latency context, upstream check |

### Challenge 3 Solution (Reliability Redesign)

```
┌──────────────────────────────────────────────────────────────────┐
│           RELIABILITY DESIGN — REDESIGNED                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  api-service:                                                     │
│    replicas: 3        ← không dưới 2                              │
│    minReplicas: 2                                                    │
│    maxReplicas: 10                                                   │
│    PDB: maxUnavailable=1                                           │
│    topologySpreadConstraints: multi-zone                          │
│    topology: yes (anti-affinity)                                  │
│    resources: req: 100m/128Mi, lim: 500m/256Mi                    │
│    probes: readiness + liveness                                   │
│    Spot: toleration + affinity preferred on-demand                │
│                                                                   │
│  worker-service:                                                  │
│    replicas: 2        ← không replicas=1 cho queue worker         │
│    minReplicas: 2                                                    │
│    graceful shutdown: terminationGracePeriodSeconds=30            │
│    preStop: sleep để drain queue trước khi kill                  │
│    NOT Spot: Stateful-ish, cần stable node                        │
│    resources: req: 100m/256Mi, lim: 250m/512Mi                    │
│                                                                   │
│  frontend-service:                                                │
│    replicas: 3        ← CDN-backed, nhưng vẫn cần HA             │
│    minReplicas: 3                                                    │
│    maxReplicas: 5                                                    │
│    resources: req: 50m/64Mi, lim: 200m/128Mi                      │
│    Spot: OK (stateless)                                           │
│    topologySpreadConstraints: multi-zone                          │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘

Memory calculation cho 4x t3.medium (4GB RAM):
  Node: 4GB, có 500MB reserved → 3.5GB allocatable
  System: ~500MB (OS + kubelet)
  ──────────────────────────────────────────────────
  api-service:     3 × 256Mi = 768Mi (requests)
  worker-service:  2 × 256Mi = 512Mi
  frontend-service: 3 × 64Mi = 192Mi
  Total requests:              ~1.5GB → fits ✓
  Buffer: 3.5GB - 1.5GB = 2GB headroom for burst + HPA scale
```

---

## Output Expectations

Sau khi hoàn thành các challenges, bạn nên có:

```
Day34/
├── exercises.md (đã điền answer)
└── Bổ sung vào repo:
    ├── capstone-platform/
    │   └── manifests/
    │       ├── monitoring/
    │       │   ├── worker-service-prometheusrule.yaml   (Bonus 1)
    │       │   └── worker-service-dashboard.json         (Bonus 1)
    │       └── reliability/
    │           └── worker-service-reliability.yaml         (Challenge 3)
    └── post-mortems/
        ├── 2024-05-15-oomkilled-incident.md              (Bonus 2)
        ├── 2024-05-15-hpa-thrashing-incident.md           (Bonus 2)
        └── 2024-05-15-spot-reclaim-incident.md           (Bonus 2)
```
