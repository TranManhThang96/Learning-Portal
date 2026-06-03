# Day 12: Kubernetes Networking Core

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** mô hình networking của Kubernetes: mỗi pod có IP riêng, pod-to-pod communication không cần NAT.
2. **Phân biệt được** các Service types: `ClusterIP`, `NodePort`, `LoadBalancer` và khi nào dùng loại nào.
3. **Hiểu được** cách `kube-proxy` routing traffic và sự khác biệt giữa `iptables`, `IPVS`, `eBPF`.
4. **Debug được** các vấn đề service discovery: DNS resolution failure, service không route được traffic, endpoint không ready.
5. **Cấu hình được** internal service communication giữa 2+ services trong cluster.

---

## 2. Bối cảnh & Động lực

### Vì sao topic này quan trọng?

Ở Day 11, bạn đã deploy workload (Deployment, StatefulSet...) nhưng các pod chưa giao tiếp được với nhau một cách ổn định. Pod IP thay đổi mỗi khi pod restart — bạn không thể hardcode IP.

Kubernetes networking giải quyết 3 bài toán cốt lõi:
1. **Pod-to-pod**: Mọi pod có thể giao tiếp trực tiếp với mọi pod khác (flat network).
2. **Pod-to-Service**: Service cung cấp stable virtual IP + DNS name, load balance traffic đến các pod backend.
3. **External-to-Service**: Expose service ra ngoài cluster (NodePort, LoadBalancer, Ingress).

### Nếu làm sai thì sao?

- **Service discovery fail** → microservices không gọi được nhau → hệ thống chết.
- **DNS cache stale** → request đến pod đã chết → 5xx errors tăng đột biến.
- **Expose NodePort không cần thiết** → attack surface mở rộng.
- **Không hiểu endpoint** → debug mất hàng giờ cho vấn đề đơn giản.

### Liên hệ với developer background

- `Service` giống reverse proxy / load balancer nội bộ (Nginx upstream, HAProxy backend).
- `ClusterIP` giống internal DNS record trỏ đến pool of servers.
- `Endpoint` giống server pool configuration trong load balancer.
- Kubernetes DNS giống service registry (Consul, Eureka) nhưng built-in.

---

## 3. Kiến thức nền tảng

### Kubernetes Networking Model — 4 yêu cầu cơ bản

Kubernetes đặt ra 4 quy tắc networking bắt buộc:

1. **Pod-to-pod**: Mọi pod giao tiếp với mọi pod khác mà **không cần NAT**.
2. **Node-to-pod**: Mọi node giao tiếp với mọi pod mà không cần NAT.
3. **Pod IP = Real IP**: IP mà pod thấy là IP mà pod khác thấy (no SNAT cho intra-cluster).
4. **Container-in-pod**: Các container trong cùng pod chia sẻ network namespace (localhost).

```
┌─────────────────────────────────────────────────┐
│                  Kubernetes Cluster              │
│                                                   │
│  ┌──────────────┐         ┌──────────────┐       │
│  │    Node 1     │         │    Node 2     │       │
│  │               │         │               │       │
│  │  ┌────────┐   │   CNI   │  ┌────────┐   │       │
│  │  │ Pod A  │───│────────│──│ Pod C  │   │       │
│  │  │10.0.1.2│   │  Overlay│  │10.0.2.3│   │       │
│  │  └────────┘   │  or     │  └────────┘   │       │
│  │  ┌────────┐   │  Routing│  ┌────────┐   │       │
│  │  │ Pod B  │───│────────│──│ Pod D  │   │       │
│  │  │10.0.1.3│   │         │  │10.0.2.4│   │       │
│  │  └────────┘   │         │  └────────┘   │       │
│  └──────────────┘         └──────────────┘       │
└─────────────────────────────────────────────────┘
```

### CNI — Container Network Interface

CNI là plugin chuẩn mà Kubernetes dùng để setup networking cho pod. Kubernetes không tự implement networking — nó delegate cho CNI plugin.

| CNI Plugin | Approach | NetworkPolicy | Performance | Phổ biến ở |
|------------|----------|---------------|-------------|------------|
| **Calico** | BGP / VXLAN | ✅ Full | High | Production, on-prem |
| **Cilium** | eBPF | ✅ Advanced | Very High | Cloud-native, high perf |
| **Flannel** | VXLAN | ❌ Basic | Medium | Dev, simple clusters |
| **Weave** | VXLAN | ✅ Basic | Medium | Small clusters |
| **AWS VPC CNI** | Native VPC | ✅ | High | EKS |
| **kindnet** | Bridge | ❌ | N/A | kind (local dev) |

---

## 4. Deep Dive

### 4.1 Service — Stable access point

Service tạo một **virtual IP (ClusterIP)** và **DNS name** ổn định, load balance traffic đến các pod backend.

```
                    ┌─────────────────┐
                    │     Service     │
                    │  ClusterIP:     │
                    │  10.96.0.100    │
                    │  DNS: app-svc   │
                    └───────┬─────────┘
                            │
                 ┌──────────┼──────────┐
                 │          │          │
            ┌────▼───┐ ┌───▼────┐ ┌───▼────┐
            │ Pod 1  │ │ Pod 2  │ │ Pod 3  │
            │10.0.1.2│ │10.0.1.3│ │10.0.2.4│
            └────────┘ └────────┘ └────────┘
                    Endpoints
```

**Service YAML cơ bản:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app-svc
spec:
  selector:
    app: my-app      # Chọn pods có label app=my-app
  ports:
    - port: 80        # Port mà service expose
      targetPort: 8080 # Port mà container lắng nghe
      protocol: TCP
  type: ClusterIP     # Default
```

### 4.2 Service Types

#### ClusterIP (default)

Chỉ accessible **trong cluster**. Đây là type phổ biến nhất.

```yaml
spec:
  type: ClusterIP
  # ClusterIP được assign tự động, ví dụ: 10.96.0.100
```

- Dùng cho: internal service-to-service communication.
- DNS: `<service-name>.<namespace>.svc.cluster.local`
- Short DNS: `<service-name>` (trong cùng namespace) hoặc `<service-name>.<namespace>`

#### NodePort

Expose service ra ngoài qua **port trên mỗi node** (range: 30000-32767).

```yaml
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080    # Tùy chọn, Kubernetes tự assign nếu không set
```

```
External Client
      │
      ▼
  Node IP:30080  ──► Service:80  ──► Pod:8080
```

- Dùng cho: dev/test, expose đơn giản không qua Ingress.
- **Không dùng cho production** trực tiếp vì: port range giới hạn, phải biết node IP, không có TLS termination.

#### LoadBalancer

Provision **external load balancer** từ cloud provider.

```yaml
spec:
  type: LoadBalancer
  ports:
    - port: 80
      targetPort: 8080
```

```
Internet ──► Cloud LB (external IP) ──► NodePort ──► Service ──► Pod
```

- Dùng cho: expose service ra internet trên cloud.
- **Mỗi LoadBalancer = 1 external IP + 1 cloud LB** → tốn tiền nếu nhiều service.
- Trên local (kind) cần thêm tool như MetalLB.

#### Headless Service (clusterIP: None)

Không có virtual IP. DNS trả về trực tiếp **pod IPs**.

```yaml
spec:
  clusterIP: None
  selector:
    app: database
```

- Dùng cho: StatefulSet, khi client cần biết từng pod IP (database replication, distributed systems).

### 4.3 Endpoint & EndpointSlice

Khi tạo Service, Kubernetes tự tạo **Endpoints** object chứa danh sách pod IPs khớp selector.

```bash
kubectl get endpoints app-svc
# NAME      ENDPOINTS                                AGE
# app-svc   10.0.1.2:8080,10.0.1.3:8080,10.0.2.4:8080   5m
```

**EndpointSlice** (mới, mặc định từ K8s 1.21+): chia endpoints thành slices (mỗi slice tối đa 100 endpoints). Cải thiện performance cho service có hàng nghìn pods.

### 4.4 kube-proxy

kube-proxy chạy trên **mỗi node**, chịu trách nhiệm **route traffic từ Service IP đến pod IP**.

```
┌─────────────┐     ┌─────────────┐     ┌─────────┐
│   Client    │────►│  Service    │────►│  Pod    │
│  (in pod)   │     │  ClusterIP  │     │  IP     │
└─────────────┘     └─────────────┘     └─────────┘
                          │
                    ┌─────┴─────┐
                    │ kube-proxy │
                    │ (per node) │
                    └───────────┘
                    Rewrites dst IP
                    from Service IP
                    to Pod IP
```

**3 modes của kube-proxy:**

| Mode | Cơ chế | Performance | Scale | Maturity |
|------|--------|-------------|-------|----------|
| **iptables** (default) | iptables rules | Good (O(n) rules) | ~5000 services | Stable, proven |
| **IPVS** | Linux IPVS kernel module | Better (O(1) lookup) | 10000+ services | Stable |
| **eBPF** (Cilium) | Replace kube-proxy entirely | Best | Unlimited | Modern |

**iptables mode** hoạt động:
1. kube-proxy watch API server cho Service/Endpoint changes.
2. Tạo iptables rules trên node.
3. Khi pod gửi traffic đến Service IP → iptables rewrite destination IP sang pod IP (DNAT).
4. Random load balancing giữa các endpoints.

### 4.5 DNS trong cluster

Kubernetes chạy CoreDNS (hoặc kube-dns) làm cluster DNS server.

**DNS naming convention:**

```
# Service
<service-name>.<namespace>.svc.cluster.local

# Pod (ít dùng trực tiếp)
<pod-ip-dashed>.<namespace>.pod.cluster.local

# StatefulSet pod (qua headless service)
<pod-name>.<service-name>.<namespace>.svc.cluster.local
```

**Ví dụ thực tế:**
```
# Trong cùng namespace "default"
curl http://app-svc              # Short name
curl http://app-svc.default      # Với namespace
curl http://app-svc.default.svc.cluster.local  # FQDN

# Cross namespace
curl http://app-svc.production   # Service "app-svc" trong namespace "production"

# StatefulSet pod
curl http://mysql-0.mysql-svc.default.svc.cluster.local
```

**DNS resolution flow:**

```
Pod → /etc/resolv.conf → CoreDNS (kube-dns service)
                          → Cluster domain? → Return ClusterIP
                          → External?       → Forward to upstream DNS
```

---

## 5. Trade-offs & Best Practices ⭐

### Chọn Service Type nào?

| Scenario | Service Type | Lý do |
|----------|-------------|-------|
| Microservice gọi microservice | ClusterIP | Internal only, simple, secure |
| Database access từ app | ClusterIP hoặc Headless | Headless cho StatefulSet |
| Dev/test expose tạm | NodePort | Đơn giản, không cần LB |
| Expose ra internet (cloud) | LoadBalancer | Cloud LB tự provision |
| Expose nhiều services | ClusterIP + Ingress | Cost-effective, flexible routing |

### kube-proxy mode trade-offs

| Criteria | iptables | IPVS | eBPF (Cilium) |
|----------|----------|------|---------------|
| Setup complexity | Default, zero config | Cần IPVS kernel module | Cần Cilium |
| Performance (< 1000 svc) | ✅ Đủ tốt | ✅ Tốt | ✅ Best |
| Performance (> 5000 svc) | ⚠️ Chậm | ✅ Tốt | ✅ Best |
| Load balancing | Random | Round-robin, weighted, least-conn | Maglev, random |
| Observability | iptables counters | ipvsadm stats | eBPF maps, Hubble |
| Recommendation | Startup, < 1000 services | Mid-size, > 1000 services | Enterprise, high perf |

### Best Practices

1. **Luôn dùng ClusterIP** cho internal communication — đừng dùng NodePort nội bộ.
2. **Dùng DNS name, không hardcode IP** — Service IP có thể thay đổi khi recreate.
3. **Readiness probe bắt buộc** — pod chưa ready sẽ bị remove khỏi endpoints = không nhận traffic.
4. **Dùng `port` và `targetPort` rõ ràng** — đặc biệt khi port mapping khác nhau.
5. **Limit NodePort usage** — chỉ dùng cho dev/test hoặc khi không có Ingress.
6. **Set `publishNotReadyAddresses: false`** (default) — tránh route traffic đến pod chưa ready.

### Anti-patterns

1. **Service không có selector** → không route traffic vào đâu (trừ khi dùng manual Endpoints).
2. **Pod label không match service selector** → service không tìm thấy pod.
3. **targetPort sai** → service route đến port pod không listen.
4. **Dùng pod IP trực tiếp** → pod restart = IP mới = connection fail.

---

## 6. Performance & Scalability ⭐

### Connection Handling

- **ClusterIP dùng iptables DNAT**: thêm latency ~micro giây, chấp nhận được.
- **NodePort thêm 1 hop**: external → node → pod. Nếu pod ở node khác → cross-node hop.
- **externalTrafficPolicy**: `Cluster` (default) = load balance đều nhưng thêm hop. `Local` = chỉ route đến pod trên cùng node, giảm latency nhưng uneven distribution.

### DNS Performance

- **ndots setting** trong `/etc/resolv.conf`: mặc định `ndots:5` → mỗi DNS query thử 4-5 suffix trước khi resolve. Với external domain, điều này gây 4-5x DNS queries.
- **Fix cho high-traffic**: set `ndots:2` trong pod spec hoặc dùng FQDN (tận cùng `.`).

```yaml
spec:
  dnsConfig:
    options:
      - name: ndots
        value: "2"
```

### Metrics cần theo dõi

| Metric | Mô tả | Concern |
|--------|--------|---------|
| CoreDNS query latency | Thời gian DNS resolve | > 5ms cần investigate |
| CoreDNS NXDOMAIN rate | DNS lookup fail | Tăng đột biến = service down hoặc typo |
| Endpoint count per service | Số pods backing service | 0 = service không hoạt động |
| Connection refused rate | App không nhận connection | Port mismatch hoặc app crash |

---

## 7. Security & Reliability Considerations

### Security

- **NetworkPolicy** (sẽ deep dive Day 20): giới hạn pod nào được giao tiếp với pod nào.
- **Không expose NodePort nếu không cần** — mỗi NodePort là một open port trên TẤT CẢ nodes.
- **Service account token mount** — mặc định pod mount SA token → có thể gọi API server. Set `automountServiceAccountToken: false` nếu không cần.

### Reliability

- **Readiness probe** đảm bảo chỉ pod healthy mới nhận traffic.
- **PodDisruptionBudget** đảm bảo không lose quá nhiều endpoints khi node maintenance.
- **Topology-aware routing** (Service topology / TopologyAwareHints): ưu tiên route traffic đến pod gần nhất (same zone) → giảm latency, giảm cross-AZ cost.

---

## 8. Hands-on Example

### Chuẩn bị

```bash
# Dùng cluster kind từ Day 11 (hoặc tạo mới)
kind create cluster --name devops-lab 2>/dev/null || echo "Cluster already exists"
kubectl cluster-info
```

### 8.1 Deploy 2 services giao tiếp nội bộ

**Service A (Frontend)** gọi **Service B (Backend)**:

```yaml
# file: backend-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  labels:
    app: backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: hashicorp/http-echo:0.2.3
          args:
            - "-text=Hello from Backend!"
            - "-listen=:5678"
          ports:
            - containerPort: 5678
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 5678
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: backend-svc
spec:
  selector:
    app: backend
  ports:
    - port: 80
      targetPort: 5678
  type: ClusterIP
```

```yaml
# file: frontend-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  labels:
    app: frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: nginx:1.25-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 50m
              memory: 64Mi
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: frontend-svc
spec:
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
```

```bash
# Deploy
kubectl apply -f backend-service.yaml
kubectl apply -f frontend-service.yaml

# Verify deployments
kubectl get deploy
kubectl get svc
kubectl get endpoints

# Expected:
# NAME          TYPE        CLUSTER-IP     PORT(S)   AGE
# backend-svc   ClusterIP   10.96.x.x     80/TCP    30s
# frontend-svc  ClusterIP   10.96.x.x     80/TCP    30s
```

### 8.2 Test service discovery bằng DNS

```bash
# Exec vào frontend pod và gọi backend qua DNS
kubectl exec -it $(kubectl get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}') -- sh

# Trong pod shell:
# Test DNS resolution
nslookup backend-svc
# Expected:
# Server:    10.96.0.10
# Address:   10.96.0.10#53
# Name:      backend-svc.default.svc.cluster.local
# Address:   10.96.x.x

# Test curl
wget -qO- http://backend-svc
# Expected: Hello from Backend!

# Test FQDN
wget -qO- http://backend-svc.default.svc.cluster.local
# Expected: Hello from Backend!

# Exit pod
exit
```

### 8.3 Inspect endpoints và service routing

```bash
# Xem endpoints
kubectl get endpoints backend-svc
# Expected:
# NAME          ENDPOINTS                     AGE
# backend-svc   10.0.0.x:5678,10.0.0.y:5678   2m

# Xem chi tiết endpoint slice
kubectl get endpointslice -l kubernetes.io/service-name=backend-svc -o yaml

# Verify traffic load balancing (chạy nhiều lần)
for i in $(seq 1 10); do
  kubectl exec $(kubectl get pod -l app=frontend -o jsonpath='{.items[0].metadata.name}') -- wget -qO- http://backend-svc 2>/dev/null
done

# Scale backend xuống 0 và test lại
kubectl scale deployment backend --replicas=0
kubectl get endpoints backend-svc
# Expected: ENDPOINTS = <none>

# Scale back
kubectl scale deployment backend --replicas=2
kubectl get endpoints backend-svc
```

### 8.4 NodePort example

```yaml
# file: nodeport-demo.yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-nodeport
spec:
  selector:
    app: backend
  ports:
    - port: 80
      targetPort: 5678
      nodePort: 30080
  type: NodePort
```

```bash
kubectl apply -f nodeport-demo.yaml
kubectl get svc backend-nodeport

# Expected:
# NAME               TYPE       CLUSTER-IP    EXTERNAL-IP   PORT(S)       AGE
# backend-nodeport   NodePort   10.96.x.x     <none>        80:30080/TCP  5s

# Test (trên kind, cần docker exec vào node)
docker exec devops-lab-control-plane curl -s localhost:30080
# Expected: Hello from Backend!
```

### Cleanup

```bash
kubectl delete -f backend-service.yaml
kubectl delete -f frontend-service.yaml
kubectl delete -f nodeport-demo.yaml 2>/dev/null
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Service không route traffic

**Triệu chứng**: curl đến service bị timeout hoặc connection refused.

```bash
# Debug flow:
# 1. Kiểm tra endpoints
kubectl get endpoints <service-name>
# Nếu ENDPOINTS trống → selector không match pod labels

# 2. Kiểm tra labels
kubectl get pods --show-labels
kubectl get svc <service-name> -o jsonpath='{.spec.selector}'

# 3. Kiểm tra pod readiness
kubectl get pods
# Nếu pod READY 0/1 → readiness probe fail → pod bị remove khỏi endpoints

# 4. Kiểm tra targetPort
kubectl get svc <service-name> -o jsonpath='{.spec.ports[0].targetPort}'
kubectl exec <pod> -- ss -tlnp  # Verify pod đang listen đúng port
```

### Pitfall 2: DNS resolution fail

**Triệu chứng**: `nslookup <service>` fail, `Could not resolve host`.

```bash
# 1. Kiểm tra CoreDNS running
kubectl get pods -n kube-system -l k8s-app=kube-dns

# 2. Kiểm tra DNS service
kubectl get svc -n kube-system kube-dns

# 3. Test DNS từ debug pod
kubectl run dns-debug --rm -it --image=busybox:1.36 --restart=Never -- nslookup kubernetes.default

# 4. Kiểm tra /etc/resolv.conf trong pod
kubectl exec <pod> -- cat /etc/resolv.conf
```

### Pitfall 3: Cross-namespace service discovery fail

**Triệu chứng**: service gọi service ở namespace khác bị fail.

```bash
# Sai:
curl http://other-service              # Chỉ tìm trong cùng namespace

# Đúng:
curl http://other-service.other-namespace
curl http://other-service.other-namespace.svc.cluster.local
```

### Case Study: DNS Storm do ndots:5

**Bối cảnh**: Team có 200 pods, mỗi pod gọi external API `api.stripe.com` hàng trăm lần/phút.

**Triệu chứng**: CoreDNS CPU spike 90%, DNS timeout tăng, app latency tăng.

**Root cause**: `ndots:5` (default) khiến mỗi query `api.stripe.com` thử 5 suffixes trước:
1. `api.stripe.com.default.svc.cluster.local` → NXDOMAIN
2. `api.stripe.com.svc.cluster.local` → NXDOMAIN
3. `api.stripe.com.cluster.local` → NXDOMAIN
4. `api.stripe.com.` → SUCCESS

= 4 DNS queries thay vì 1. Nhân 200 pods × 100 calls/min = 80,000 → 320,000 DNS queries/min.

**Fix**: Dùng FQDN với trailing dot: `api.stripe.com.` hoặc set `ndots:2` trong pod spec.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 11: Kubernetes Workload Resources)
- Đã deploy Deployment, StatefulSet → bài này hiểu cách pod giao tiếp.
- StatefulSet cần headless service → đã giải thích chi tiết.
- DaemonSet expose metrics → liên quan đến service discovery.

### Bài sau (Day 13: Ingress, Gateway API & Load Balancing)
- ClusterIP service chỉ accessible trong cluster → cần Ingress/Gateway API để expose ra ngoài.
- Service là backend cho Ingress routing rules.
- TLS termination, path-based routing sẽ được giải thích.

---

## 11. Tài liệu tham khảo

### Must-read
- [Kubernetes Service — Official Docs](https://kubernetes.io/docs/concepts/services-networking/service/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Cluster Networking — Official Docs](https://kubernetes.io/docs/concepts/cluster-administration/networking/)

### Nice-to-have
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/)
- [CoreDNS Configuration](https://coredns.io/manual/toc/)
- [kube-proxy modes](https://kubernetes.io/docs/reference/networking/virtual-ips/)

### Deep-dive
- "Kubernetes in Action" — Chapter 5: Services
- [Life of a Packet in Kubernetes](https://www.youtube.com/watch?v=0Omvgd7Hg1I) — KubeCon talk
- [Cilium — eBPF-based Networking](https://docs.cilium.io/en/stable/network/concepts/)
- [Understanding Kubernetes Networking](https://sookocheff.com/post/kubernetes/understanding-kubernetes-networking-model/) — Kevin Sookocheff blog

