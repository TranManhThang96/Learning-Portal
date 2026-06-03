# Day 21: Deep Dive — Chaos Playbook, Benchmark Report, Postmortem & Error Budget Policy

---

## 1. Chaos Engineering Playbook

### 1.1 Full Chaos Workflow Diagram

```mermaid
flowchart TD
    subgraph "Phase 0: Preparation (Pre-Gameday)"
        P1["Define hypotheses\nfor each scenario"]
        P2["Setup monitoring:\nGrafana dashboard\nwith all KPIs visible"]
        P3["Define abort criteria:\nthresholds, on-call contacts"]
        P4["Communicate:\n'Chaos gameday starting'\nto all stakeholders"]
        P5["Backup current state:\ndeck gateway dump\ndatabase snapshot"]
    end

    subgraph "Phase 1: Execute Experiment"
        E1["Trigger chaos action\nvia script/tool"]
        E2["Monitor in real-time:\nGrafana dashboard\nalerts firing"]
        E3{"Is abort criteria\ntriggered?"]
        E3 --|Yes| E4["STOP immediately\nLog incident"]
        E3 --|No| E5["Let experiment run\n10-15 minutes"]
        E5 --> E6{"Is steady state\nreached?"]
        E6 --|No| E2
        E6 --|Yes| R1["Recovery action"]
    end

    subgraph "Phase 2: Recovery"
        R1 --> R2["Remove chaos action\nkill/stop tool"]
        R2 --> R3["Verify service health\nGrafana metrics"]
        R3 --> R4{"Is service healthy?"]
        R4 --|No| E4
        R4 --|Yes| R5["Document findings\nin postmortem"]
    end

    subgraph "Phase 3: Postmortem"
        PM1["What was\nhypothesis?"]
        PM1 --> PM2["What was\nactual behavior?"]
        PM2 --> PM3["Did we meet\nabort criteria?"]
        PM3 --> PM4["What did we\nlearn?"]
        PM4 --> PM5["What needs to\nchange (SLO/runbook)?"]
        PM5 --> PM6["Schedule next\ngameday"]
    end
```

### 1.2 Chaos Script Template

```bash
#!/bin/bash
# chaos-experiment.sh — Template cho chaos experiment
# Usage: ./chaos-experiment.sh <scenario> <duration_seconds>

set -e

SCENARIO="${1:?Usage: $0 <scenario> <duration_seconds>}"
DURATION="${2:-300}"
ABORT_FILE="/tmp/chaos-abort"
RESULTS_FILE="/tmp/chaos-results-${SCENARIO}-$(date +%s).json"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*"; }

# Pre-check: Verify monitoring is up
verify_monitoring() {
    log "Checking Grafana accessibility..."
    curl -sf http://localhost:3000/api/health > /dev/null \
        && log "Grafana: OK" \
        || { log "FATAL: Grafana not accessible"; exit 1; }

    log "Checking Prometheus accessibility..."
    curl -sf http://localhost:9090/-/healthy > /dev/null \
        && log "Prometheus: OK" \
        || { log "FATAL: Prometheus not accessible"; exit 1; }
}

# Abort criteria check
check_abort() {
    local error_rate
    error_rate=$(curl -s "http://localhost:9090/api/v1/query" \
        --data-urlencode 'query=rate(http_requests_total{status=~"5.."}[1m]) / rate(http_requests_total[1m])' \
        | jq -r '.data.result[0].value[1] // "0"' 2>/dev/null)

    log "Current error rate: ${error_rate}"
    local threshold=0.05
    if (( $(echo "${error_rate} > ${threshold}" | bc -l) )); then
        log "ABORT: Error rate ${error_rate} exceeds threshold ${threshold}"
        touch "${ABORT_FILE}"
        return 1
    fi
    return 0
}

# Scenario runners
run_scenario_1_backend_down() {
    log "SCENARIO: Backend service down (kill order-service-1)"
    log "Hypothesis: Kong will failover to order-service-2 within 5s, error rate < 0.5%"

    # Store start metrics
    curl -s http://localhost:9090/api/v1/query \
        --data-urlencode 'query=rate(http_requests_total[5m])' \
        | jq -r '.data.result[0].value[1]' > /tmp/chaos-baseline-rps.txt

    # Trigger chaos: kill backend1
    docker stop order-service-1 &
    local chaos_pid=$!

    # Monitor for 60 seconds
    for i in $(seq 1 12); do
        check_abort || { kill $chaos_pid 2>/dev/null; return 1; }
        log "Monitoring... (${i}/12)"
        sleep 5
    done

    # Recovery
    log "Recovery: starting order-service-1"
    docker start order-service-1

    # Wait for health
    sleep 10
    log "Verification: checking Kong upstream health"
    curl -s http://localhost:8001/upstreams/order-upstream/healths \
        | jq '.data[] | {target, healthy}'
}

run_scenario_5_redis_down() {
    log "SCENARIO: Redis down — testing rate-limit fail-open vs fail-close"
    log "Hypothesis: With fail-open policy, requests are allowed (no rate-limit)"

    # Capture baseline request rate
    local baseline_rps
    baseline_rps=$(curl -s http://localhost:9090/api/v1/query \
        --data-urlencode 'query=rate(http_requests_total{service="order-service"}[5m])' \
        | jq -r '.data.result[0].value[1] // "0"')

    log "Baseline RPS: ${baseline_rps}"

    # Kill Redis
    log "Triggering chaos: stopping redis"
    docker stop redis

    # Monitor: rate-limit should be bypassed (fail-open) or all denied (fail-close)
    for i in $(seq 1 12); do
        local current_rps
        current_rps=$(curl -s http://localhost:9090/api/v1/query \
            --data-urlencode 'query=rate(http_requests_total{service="order-service"}[1m])' \
            | jq -r '.data.result[0].value[1] // "0"')
        log "RPS during Redis down: ${current_rps} (should increase if fail-open)"
        sleep 5
    done

    # Recovery
    log "Recovery: starting redis"
    docker start redis
    sleep 10

    # Verify rate-limiting restored
    log "Verification: checking rate-limit is restored"
    for i in $(seq 1 5); do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/orders)
        log "Request $i: HTTP $STATUS"
        sleep 1
    done
}

run_scenario_8_slowloris() {
    log "SCENARIO: Slowloris — testing worker_connections exhaustion"
    log "Hypothesis: Nginx will return 503 when worker_connections limit is hit"

    # Check current connection count
    log "Baseline connections:"
    curl -s http://localhost:8080/nginx_status

    # Simulate slowloris: many slow connections
    log "Triggering slowloris: opening 200 slow connections..."
    for i in $(seq 1 200); do
        (
            exec 3<>/dev/tcp/localhost/80
            printf "GET / HTTP/1.1\r\nHost: localhost\r\n"
            sleep 30  # Hold connection open for 30s
        ) &
    done

    # Monitor
    sleep 5
    log "During slowloris:"
    curl -s http://localhost:8080/nginx_status
    curl -s -o /dev/null -w "New request: HTTP %{http_code}, time: %{time_total}s\n" \
        http://localhost:8080/api/v1/orders

    # Recovery: kill slow connections
    log "Recovery: killing slow connections"
    pkill -f "sleep 30" 2>/dev/null || true
    sleep 2
    log "After recovery:"
    curl -s http://localhost:8080/nginx_status
}

# Main
main() {
    log "=== Chaos Experiment: ${SCENARIO} ==="
    verify_monitoring

    case "${SCENARIO}" in
        backend-down)    run_scenario_1_backend_down ;;
        redis-down)      run_scenario_5_redis_down ;;
        slowloris)       run_scenario_8_slowloris ;;
        *)               log "Unknown scenario: ${SCENARIO}"; exit 1 ;;
    esac

    log "=== Experiment Complete ==="
}

main "$@"
```

---

## 2. Benchmark Report — Extended Template

### 2.1 Full Report Structure

```markdown
# Benchmark Report — [System Name]
**Date**: YYYY-MM-DD
**Environment**: [Staging / Production-like]
**Tester**: [Name]
**Version**: [Kong 3.7, Nginx 1.25, Backend v1.2.3]

---

## 1. Executive Summary

**Bottom line up front**: [One paragraph summarizing findings]

**Key metrics**:
| Metric | Baseline | After Tuning | Change |
|---|---|---|---|
| Max RPS | X | Y | ±Z% |
| p95 latency | Xms | Yms | ±Z% |
| p99 latency | Xms | Yms | ±Z% |
| Error rate | X% | Y% | ±Z% |
| Cost/1M req | $X | $Y | -Z% |

**Recommendation**: [One sentence]

---

## 2. Environment Details

### 2.1 Infrastructure

| Component | Count | vCPU | RAM | Disk | OS |
|---|---|---|---|---|---|
| Nginx edge | 2 | 2 | 4GB | 50GB SSD | Ubuntu 22.04 |
| Kong gateway | 3 | 4 | 8GB | 50GB SSD | Ubuntu 22.04 |
| order-service | 6 | 1 | 1GB | 10GB SSD | Alpine 3.18 |
| payment-service | 4 | 1 | 1GB | 10GB SSD | Alpine 3.18 |
| tracking-service | 4 | 1 | 1GB | 10GB SSD | Alpine 3.18 |
| Consul | 3 | 2 | 4GB | 20GB SSD | Ubuntu 22.04 |
| Redis | 2 | 2 | 4GB | 20GB SSD | Ubuntu 22.04 |
| Prometheus | 1 | 2 | 8GB | 100GB SSD | Ubuntu 22.04 |
| Grafana | 1 | 2 | 4GB | 50GB SSD | Ubuntu 22.04 |

### 2.2 Software Versions

| Component | Version |
|---|---|
| Kernel | 5.15.0-105-generic |
| Docker | 26.0.0 |
| Docker Compose | 2.26.0 |
| Nginx | 1.25.3 |
| Kong | 3.7.0 |
| Consul | 1.19.0 |
| Redis | 7.2.4 |
| Prometheus | 2.53.0 |
| Grafana | 10.4.0 |
| k6 | 0.54.0 |

### 2.3 Network Topology

```
Load Generator (k6)
  ↓ (loopback — same host)
Nginx edge (2 instances, port 80/443)
  ↓ (Docker network)
Kong gateway (3 instances, port 8000/8443)
  ↓ (Docker network)
Backend services (3 × 2 replicas)
  ↓ (Docker network)
Consul (3-node cluster)
Redis (master + replica)
```

---

## 3. Methodology

### 3.1 Test Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Tool | k6 v0.54.0 | Rate-based, coordinated omission-free |
| Load generator | Same host as Kong (loopback) | Minimize network variability |
| Payload | GET /api/v1/orders (512B JSON) | Representative API response size |
| TLS | Off | Focus on gateway performance |
| Keepalive | On (HTTP/1.1) | Production configuration |
| Warmup | 10s | Avoid cold-start bias |
| Measure duration | 60s per scenario | Statistical significance |
| Plugins active | rate-limiting (local), prometheus | Production-like config |

### 3.2 k6 Script Reference

```javascript
// File: benchmark.js
// Run: k6 run --out json=results.json benchmark.js
// Thresholds passed as CLI flags for CI/CD reuse

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const latency = new Trend('latency');

export const options = {
  scenarios: {
    load: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 200,
      stages: [
        { duration: '2m', target: 100 },   // ramp to 100 RPS
        { duration: '5m', target: 100 },   // hold
        { duration: '1m', target: 0 },     // ramp down
      ],
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'],
    'errors': ['rate<0.01'],
    'latency': ['avg<200'],
  },
};

export default function () {
  const res = http.get('http://localhost:8000/api/v1/orders', {
    tags: { name: 'order-service' },
  });

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'response has data': (r) => r.json('data') !== undefined,
  });

  errorRate.add(!ok);
  latency.add(res.timings.duration);
  sleep(1);
}
```

### 3.3 Coordinated Omission Mitigation

```
Problem (ab, wrk default):
  Thread sends request → waits for response → sends next

  If server takes 5s per request:
    t=0: req1 sent, waiting
    t=5: req1 received, req2 sent
    t=10: req2 received, req3 sent

  Tool reports: 0.2 RPS, 5s latency
  Reality: server is slow but tool "waited" → latency looks OK but throughput is artificially low

Solution (k6 arrival-rate, vegeta):
  Timer fires every 100ms regardless of previous response
  If server is slow → request queues in memory
  → Latency p99 increases (request waited in queue)
  → Throughput is honest (constant rate)

  → p99 includes queue wait time = true latency experienced by user
```

---

## 4. Detailed Results

### 4.1 Results Table Template

| Scenario | VUs/Rate | Duration | RPS | p50 | p95 | p99 | p999 | Max | Error% |
|---|---|---|---|---|---|---|---|---|---|
| Baseline (no tuning) | 100 | 60s | 8,200 | 18ms | 120ms | 450ms | 820ms | 1,200ms | 0.3% |
| + keepalive | 100 | 60s | 12,500 | 12ms | 85ms | 280ms | 510ms | 900ms | 0.1% |
| + worker_connections | 100 | 60s | 13,800 | 11ms | 80ms | 250ms | 480ms | 850ms | 0.1% |
| + sendfile + tcp_nopush | 100 | 60s | 14,200 | 10ms | 78ms | 240ms | 460ms | 820ms | 0.1% |

### 4.2 Metric Definitions

```
http_req_duration (Latency):
  Time from first byte of request sent
  to last byte of response received
  = network + gateway + upstream + network

kong_upstream_latency:
  Time Kong spent waiting for upstream response
  = upstream processing + network to upstream

kong_proxy_latency:
  Time Kong spent in plugin chain + Lua processing
  = proxy latency overhead

Throughput (RPS):
  Successful requests per second
  = count(successful requests) / duration

Error Rate:
  = count(non-2xx responses) / count(all requests)
  Broken down by: 4xx client errors vs 5xx server errors
```

---

## 5. Capacity Planning Case Study

### 5.1 E-Commerce Platform Capacity Planning

**Scenario**: Thiết kế infrastructure cho e-commerce platform với:

```
Peak traffic (Black Friday): 50,000 RPS
Average traffic: 10,000 RPS
Burst capacity needed: 5× average = 50,000 RPS
SLO: 99.9% uptime, p99 < 500ms
Multi-AZ: required (AZ failure resilience)
```

### 5.2 Benchmark Results (per Stack Unit)

```
1 Stack Unit = 1 Nginx + 1 Kong + 3 backend replicas + Consul agent + Redis agent

Benchmark results (1 stack unit):
  Max RPS: 7,800
  p95 at 7,800 RPS: 280ms
  p95 at 5,000 RPS: 150ms  ← target operational point
  Error rate at 5,000 RPS: 0.1%

Cost per stack unit (hourly):
  Compute: 8 vCPU × $0.40 = $3.20/h
  Memory: 16GB × $0.05 = $0.80/h
  Network: included
  Total: ~$4.00/h per stack unit
```

### 5.3 Stack Unit Calculation

```
Required capacity: 50,000 RPS peak
Headroom 30%: 50,000 / 0.7 = 71,428 RPS required total capacity
Stack units needed: ceil(71,428 / 7,800) = ceil(9.16) = 10 units

Architecture:
  Nginx edge: 10 instances (1 per stack unit, fronted by Cloud LB)
  Kong: 10 instances (active-active)
  Backend: 3 services × 5 replicas = 15 instances
  Consul: 3 cluster nodes (shared across stacks)
  Redis: 2 nodes (master + replica, shared across stacks)

Cost:
  Stack units: 10 × $4.00/h = $40.00/h
  Consul: $2.00/h (shared)
  Redis: $1.50/h (shared)
  Monitoring: $5.00/h (Prometheus + Grafana)
  Total: ~$48.50/h = $1,164/month (on-demand)

Reserved instance (1-year): ~$0.50/h × 10 = $5.00/h = $3,600/year
Savings: 90% vs on-demand
```

### 5.4 Autoscale Policy

```
Horizontal Pod Autoscaler (if Kubernetes):

  Kong Gateway:
    metric: cpu_usage_percent
    target: 70%
    min: 10 replicas
    max: 50 replicas
    behavior:
      scaleUp:
        stabilizationWindowSeconds: 60
        policies:
          - type: Percent
            value: 50
            periodSeconds: 60
      scaleDown:
        stabilizationWindowSeconds: 300
        policies:
          - type: Percent
            value: 10
            periodSeconds: 60

  Backend services:
    metric: rps_per_replica
    target: 1,000 RPS per replica
    min: 15 replicas (3 services × 5)
    max: 100 replicas

Alerting thresholds:
  p95 > 300ms: Warning (scale-up pending)
  p95 > 500ms: Critical (immediate scale-up)
  Error rate > 1%: Warning
  Error rate > 5%: Critical (possible outage)
```

---

## 6. Postmortem Template

### 6.1 Blameless Postmortem Format

```markdown
# Postmortem — [Incident Name]
**Date**: YYYY-MM-DD HH:MM to HH:MM (UTC)
**Severity**: SEV-1 / SEV-2 / SEV-3
**Duration**: X hours Y minutes
**Impact**: ~Z users affected, $W revenue impact

---

## Summary

[3-5 sentences: what happened, impact, root cause in one line]

---

## Impact

| Metric | Value |
|---|---|
| Users affected | ~X |
| Requests failed | Y |
| Revenue impact | $Z |
| SLA breach | [yes/no, duration] |
| Error budget consumed | X% of monthly budget |

---

## Timeline (UTC)

| Time | Event |
|---|---|
| HH:MM | Normal operation |
| HH:MM | [First symptom detected] |
| HH:MM | [Alert fired] |
| HH:MM | [On-call acknowledged] |
| HH:MM | [Root cause identified] |
| HH:MM | [Mitigation applied] |
| HH:MM | [Service recovered] |
| HH:MM | [Postmortem created] |

---

## Root Cause Analysis

### Contributing Factors
1. [Factor 1]
2. [Factor 2]
3. [Factor 3]

### Root Cause
[One sentence: the specific technical cause]

### Detection Gap
[Why did it take X minutes to detect? What was missing?]

---

## What Went Well

- [What worked during incident response]
- [What tooling helped]
- [What communication worked]

---

## What Went Wrong

- [What didn't work]
- [What caused delays]
- [What made diagnosis difficult]

---

## Action Items

| Action | Owner | Priority | Due |
|---|---|---|---|
| Add alerting for [specific symptom] | @person | P1 | YYYY-MM-DD |
| Increase [resource] by X% | @person | P2 | YYYY-MM-DD |
| Document runbook for [scenario] | @person | P2 | YYYY-MM-DD |
| Run chaos experiment for [scenario] | @team | P3 | YYYY-MM-DD |

---

## Lessons Learned

1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]
```

### 6.2 Blameless Culture Principles

```
Blameless postmortem = learning opportunity, not accountability tool

Principles:
  1. Focus on SYSTEM failure, not individual failure
  2. Assume people were doing their best with the information they had
  3. Ask "why" 5 times to get to root cause (Toyota 5 Whys)
  4. Action items must have owners and due dates
  5. Share postmortems widely (blameless culture = learning culture)

What is NOT blameless:
  ✗ "Engineer X made a mistake" — focus on the SYSTEM that allowed the mistake
  ✗ "User Y misconfigured something" — focus on the UI/API that allowed misconfiguration
  ✗ "Team Z didn't follow process" — focus on the PROCESS that was confusing
```

---

## 7. Error Budget Policy

### 7.1 Error Budget Calculation

```
Error Budget = Available Error Budget = (1 - SLO) × Total Requests

Example (monthly):
  SLO = 99.9% = 0.999
  Total requests/month = 100,000,000
  Error budget = (1 - 0.999) × 100M = 0.001 × 100M = 100,000 errors

  Error rate = 100,000 errors / 100M requests = 0.1%
  Monthly budget = 100,000 errors

Example (weekly):
  SLO = 99.9%
  Total requests/week = 23,000,000
  Error budget = 0.001 × 23M = 23,000 errors/week
```

### 7.2 Error Budget Policy Matrix

| Budget Remaining | Deployment Policy | Review Cadence |
|---|---|---|
| 100% - 80% | Deploy freely (canary, feature flags OK) | Weekly review |
| 80% - 50% | Review all changes, slow canary | Daily review |
| 50% - 20% | Major freezes, only critical fixes | Twice daily |
| 20% - 0% | Full freeze, all hands on reliability | Continuous |
| 0% | Incident declared, zero-tolerance | Immediate |

### 7.3 Error Budget Burn Rate

```
Burn rate = Error rate / Error budget rate

Example:
  Error rate (last 1h) = 0.05% = 0.0005
  Error budget rate = 0.1% / 30 days = 0.0033% / day = 0.00014% / hour

  Burn rate = 0.0005 / 0.00014 = 3.6×

  → Spending error budget 3.6× faster than sustainable
  → Budget exhausted in: 30 days / 3.6 = 8.3 days

Alert:
  Burn rate > 2× → Warning: error budget depleting fast
  Burn rate > 5× → Critical: deploy freeze recommended
```

### 7.4 SLO Definition for Capstone Architecture

```yaml
# SLO definitions for Day 20 capstone system

slos:
  - name: gateway-availability
    target: 99.9%
    window: 30d
    metric: |
      sum(rate(http_requests_total{status!~"5.."}))  # 2xx/4xx
      /
      sum(rate(http_requests_total))
    alert:
      burn_rate_threshold: 2
      recovery_time_estimate: 4h

  - name: gateway-latency-p99
    target: 99.0%
    window: 30d
    metric: |
      histogram_quantile(0.99,
        sum(rate(http_request_duration_bucket[5m])) by (le)
        / sum(rate(http_request_duration_count[5m]))
      )
    threshold: 500ms
    alert:
      burn_rate_threshold: 2

  - name: upstream-health
    target: 99.5%
    window: 30d
    metric: |
      sum(rate(kong_upstream_target_health{healthy="true"}))
      /
      sum(rate(kong_upstream_target_health))
    alert:
      burn_rate_threshold: 3

error_budgets:
  gateway-availability:
    monthly: 43,200 seconds of downtime (99.9% × 30d)
    weekly: 10.1 minutes of downtime (99.9% × 7d)
    daily: 1.44 minutes of downtime (99.9% × 1d)

  gateway-latency-p99:
    monthly: 1% × 30d × 24h = 7.2 hours of degraded performance
    weekly: 1% × 7d × 24h = 1.68 hours
```

---

## 8. Tools Deep Dive Reference

### 8.1 Pumba — Docker Chaos

```bash
# Pumba: Docker chaos testing tool
# Install: docker run -d --name pumba gaiaadm/pumba pumba

# Kill container (scenario 1)
pumba kill --interval 10s order-service-1

# Pause container (simulate hang)
pumba pause --duration 60s order-service-1

# Network partition (scenario 10)
pumba netem --duration 30s --tc-command "delay 2000ms 500ms" order-service-1

# Stop multiple containers
pumba kill --interval 5s [order-service-1,order-service-2]

# Chaos in CI/CD
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba \
  pumba kill --interval 10s order-service-1
```

### 8.2 Toxiproxy — Network Impairment

```bash
# Toxiproxy: TCP proxy for injecting latency, jitter, disconnects
# Docker Compose setup:
# 1. Start toxiproxy server
docker run -d -p 8474:8474 -p 9876:9876 \
  --name toxiproxy ghcr.io/shopify/toxiproxy2:latest

# 2. Add order-service upstream
docker exec toxiproxy toxiproxy-cli create --listen 127.0.0.1:22100 \
  --upstream order-service-1:3000

# 3. Inject latency (scenario 2)
docker exec toxiproxy toxiproxy-cli toxic add order-service-1 \
  --toxicName latency \
  --type latency \
  --attribute latencyTx=2000 \
  --attribute jitter=500

# 4. Check toxic
docker exec toxiproxy toxiproxy-cli toxic list order-service-1

# 5. Remove toxic (recovery)
docker exec toxiproxy toxiproxy-cli toxic remove --toxicName latency

# Kong config: point to toxiproxy instead of direct backend
# Kong service.url = http://toxiproxy:22100
```

### 8.3 tc netem — Kernel-level Network Control

```bash
# tc netem: network emulation via Linux traffic control
# Requires: iproute2 package

# Network delay (scenario 10)
tc qdisc add dev eth0 root netem delay 2000ms 500ms
# delay 2000ms ± 500ms = 1500-2500ms

# Packet loss
tc qdisc add dev eth0 root netem loss 10%
# 10% packet loss

# Duplicate packets
tc qdisc add dev eth0 root netem duplicate 5%
# 5% duplicated packets

# Corruption
tc qdisc add dev eth0 root netem corrupt 3%
# 3% corrupted packets

# Remove all netem rules
tc qdisc del dev eth0 root

# View current qdisc
tc qdisc show dev eth0

# Container-specific (use in Docker network namespace)
docker exec order-service-1 tc qdisc add dev eth0 root netem delay 5000ms
```

### 8.4 Gremlin — Commercial Chaos (Overview)

```
Gremlin là commercial chaos engineering platform.
Cung cấp 4 attack types:

1. Resource Attacks
   - CPU: spike target CPU to X% for Y seconds
   - Memory: consume X GB of memory
   - Disk: fill disk to X%
   - IO: stress disk I/O

2. Network Attacks
   - Latency: add X ms latency to all traffic
   - Packet loss: drop X% of packets
   - DNS: block DNS resolution
   - Blackhole: drop all traffic to/from target

3. Process Attacks
   - Kill: kill target process
   - Stop: pause target process
   - Restart: restart target process

4. State Attacks
   - Shutdown: shutdown target container/VM
   - Reboot: reboot target host

Integration với Kubernetes:
  - Gremlin Operator
  - Kubernetes-native attack definitions
  - HPA integration (scale based on chaos result)

Cost: Enterprise pricing, free tier có giới hạn attacks/hour
```

---

## 9. Additional Anti-Patterns

### 9.1 Chaos Engineering Anti-Patterns

```
Anti-pattern 1: Test trên production không có abort criteria
  → Có thể gây outage thật sự
  → Fix: luôn có abort threshold, dashboard visible

Anti-pattern 2: Không backup trước experiment
  → Chaos kill container → không có backup → data loss
  → Fix: backup trước, deck dump

Anti-pattern 3: Experiment không có hypothesis rõ ràng
  → "Kill random container and see what happens"
  → → Không learn được gì
  → Fix: hypothesis + expected behavior + acceptance criteria

Anti-pattern 4: Không communicate với team
  → Chaos gây alert → team panic → unnecessary escalation
  → Fix: notify trước khi gameday, #chaos-gameday Slack channel

Anti-pattern 5: Chỉ test 1 scenario mãi
  → System evolve → scenario cũ không còn relevant
  → Fix: rotate scenarios, add new based on recent incidents

Anti-pattern 6: Không follow up action items
  → Gameday discover issues → 0 action items → issues still exist
  → Fix: action items có owner + due date + tracked
```

### 9.2 Benchmark Anti-Patterns

```
Anti-pattern 1: Benchmark trên dev laptop
  → Dev laptop có 2 cores, 8GB RAM
  → Production có 64 cores, 256GB RAM
  → Số liệu không represent production
  → Fix: benchmark trên production-like environment

Anti-pattern 2: Benchmark không có warmup
  → Cold start → latency inflated 2-5×
  → Fix: 10-30s warmup trước khi measure

Anti-pattern 3: Không measure error rate
  → Chỉ measure latency, không thấy errors
  → Fix: luôn include error rate, breakdown by status code

Anti-pattern 4: Benchmark với 1 phút duration
  → Short test → không detect memory leak, connection exhaustion
  → Fix: soak test 30+ phút cho resource leak detection

Anti-pattern 5: Không có threshold
  → k6 chạy nhưng không có pass/fail criteria
  → Fix: define thresholds, fail CI/CD if threshold not met
```
