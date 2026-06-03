# Day 8: Docker Internals — namespace, cgroup, OCI, Image Layers

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Giải thích được** container khác VM ở điểm nào và tại sao điều đó quan trọng cho production.
2. **Mô tả được** vai trò của Linux namespace, cgroup trong việc tạo container isolation.
3. **Hiểu được** OCI runtime specification và chuỗi Docker Engine → containerd → runc.
4. **Tối ưu được** Dockerfile sử dụng multi-stage build, build cache, và layer ordering.
5. **Phân tích được** image layers bằng `docker history` và giảm image size 60-80%.

---

## 2. Bối cảnh & Động lực

### Vì sao cần hiểu Docker internals?

Hầu hết developer dùng Docker ở mức `docker build`, `docker run` mà không hiểu bên dưới hoạt động thế nào. Điều này gây ra:

- **Image 2GB** cho một API service 10MB binary → deploy chậm, tốn storage.
- **Build 15 phút** mỗi lần thay đổi 1 dòng code → CI/CD bottleneck.
- **Container chạy root** → security risk nghiêm trọng.
- **PID 1 problem** → zombie processes, signal handling sai.
- **Secret leak** trong image layers → credential exposed.

### Liên hệ với Phase 1

| Day 2 đã học | Day 8 mở rộng |
|---|---|
| Linux process model | Container = process + isolation |
| PID, namespace (`/proc`) | PID namespace, NET namespace, MNT namespace |
| Signal handling (SIGTERM) | PID 1 trong container phải xử lý signal |
| systemd quản lý service | Container runtime quản lý container |
| `/proc` filesystem | `/proc` trong container namespace |

### Nếu không hiểu internals?

- Không debug được "container chạy local OK nhưng production fail"
- Không tối ưu được image size → cold start chậm khi scale
- Không hiểu vì sao cgroup limit gây CPU throttling
- Không hiểu vì sao secret vẫn tồn tại dù đã `RUN rm secret.key`

---

## 3. Kiến thức nền tảng

### Container KHÔNG phải VM

```
┌─────────────────────────────────────────────────┐
│                Virtual Machine                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  App A   │  │  App B   │  │  App C   │      │
│  │  Libs    │  │  Libs    │  │  Libs    │      │
│  │  Guest OS│  │  Guest OS│  │  Guest OS│      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────────────────────────────────────┐   │
│  │              Hypervisor                  │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │              Host OS                      │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│                 Container                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  App A   │  │  App B   │  │  App C   │      │
│  │  Libs    │  │  Libs    │  │  Libs    │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────────────────────────────────────┐   │
│  │         Container Runtime (runc)          │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │         Host OS Kernel (shared)           │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Khác biệt cốt lõi:**

| Tiêu chí | VM | Container |
|----------|-----|-----------|
| Isolation | Hardware-level (hypervisor) | OS-level (namespace + cgroup) |
| Kernel | Mỗi VM có kernel riêng | Chia sẻ kernel với host |
| Boot time | 30-60 giây | < 1 giây |
| Image size | GB | MB (nếu tối ưu) |
| Resource overhead | Cao (full OS) | Thấp (chỉ app + libs) |
| Security isolation | Mạnh hơn | Yếu hơn (shared kernel) |

**Analogy cho developer**: Container giống như `chroot` on steroids — cùng chạy trên OS host nhưng mỗi container "nghĩ" nó là hệ thống riêng biệt.

### Ba trụ cột của container

```
Container = Process + Namespace (isolation) + Cgroup (resource limit)
```

---

## 4. Deep Dive

### 4.1 Linux Namespace

Namespace tạo **isolation** — mỗi container có "view" riêng của system resources.

| Namespace | Isolate | Ý nghĩa |
|-----------|---------|---------|
| **PID** | Process IDs | Container thấy PID tree riêng, PID 1 là app |
| **NET** | Network | Container có network interface, IP, port riêng |
| **MNT** | Mount points | Container có filesystem riêng |
| **UTS** | Hostname | Container có hostname riêng |
| **IPC** | Inter-process communication | Shared memory, semaphore isolation |
| **USER** | User/Group IDs | UID 0 trong container ≠ UID 0 trên host (nếu user namespace enabled) |
| **CGROUP** | Cgroup view | Container chỉ thấy cgroup của mình |

```bash
# Xem namespace của container
docker run -d --name test nginx
PID=$(docker inspect test --format '{{.State.Pid}}')

# List namespaces
ls -la /proc/$PID/ns/
# lrwxrwxrwx  cgroup -> 'cgroup:[4026532xxx]'
# lrwxrwxrwx  ipc -> 'ipc:[4026532xxx]'
# lrwxrwxrwx  mnt -> 'mnt:[4026532xxx]'
# lrwxrwxrwx  net -> 'net:[4026532xxx]'
# lrwxrwxrwx  pid -> 'pid:[4026532xxx]'
# lrwxrwxrwx  uts -> 'uts:[4026532xxx]'

# So sánh với host
ls -la /proc/1/ns/
# → Namespace IDs khác nhau = isolated

# Chạy command trong namespace của container
sudo nsenter -t $PID -n ip addr  # Vào NET namespace
sudo nsenter -t $PID -p -r ps aux  # Vào PID namespace

docker rm -f test
```

### 4.2 Linux Cgroup (Control Groups)

Cgroup đặt **resource limits** — ngăn container chiếm hết tài nguyên host.

```
cgroup hierarchy (cgroup v2):
/sys/fs/cgroup/
├── system.slice/
│   └── docker-<container-id>.scope/
│       ├── cpu.max              # CPU limit
│       ├── cpu.stat             # CPU usage stats
│       ├── memory.max           # Memory limit
│       ├── memory.current       # Current memory usage
│       ├── io.max               # I/O limit
│       └── pids.max             # Process count limit
```

```bash
# Container với resource limits
docker run -d --name limited \
  --cpus="0.5" \
  --memory="256m" \
  --memory-swap="256m" \
  --pids-limit=100 \
  nginx

# Xem cgroup settings
PID=$(docker inspect limited --format '{{.State.Pid}}')

# CPU limit (cgroup v2)
cat /sys/fs/cgroup/system.slice/docker-$(docker inspect limited --format '{{.Id}}').scope/cpu.max
# Output: 50000 100000  → 50% CPU (50000/100000)

# Memory limit
cat /sys/fs/cgroup/system.slice/docker-$(docker inspect limited --format '{{.Id}}').scope/memory.max
# Output: 268435456  → 256MB

# Hoặc dùng docker stats
docker stats limited --no-stream
# CONTAINER   CPU %   MEM USAGE / LIMIT   ...
# limited     0.00%   2.5MiB / 256MiB     ...

docker rm -f limited
```

**CPU throttling explained:**

```
CPU quota = --cpus * CPU period (default 100ms)

--cpus=0.5 → 50ms mỗi 100ms period
--cpus=2.0 → 200ms mỗi 100ms period (dùng 2 cores)

Khi container dùng hết quota → bị throttle đến period tiếp theo
→ Latency spike! (p99 tăng dù CPU avg thấp)
```

### 4.3 OCI Runtime Specification

```
Docker Client (docker CLI)
    │
    ▼
Docker Engine (dockerd)         ← Docker daemon, API server
    │
    ▼
containerd                      ← Container runtime (quản lý lifecycle)
    │
    ▼
runc                            ← OCI runtime (tạo container thực tế)
    │
    ├── Clone process
    ├── Set namespaces
    ├── Set cgroups
    ├── Set capabilities
    ├── Mount filesystem
    ├── Execute entrypoint
    └── Container running!
```

**OCI (Open Container Initiative)** định nghĩa 2 spec:
- **Runtime Spec**: cách chạy container (runc implement)
- **Image Spec**: cách đóng gói image (layers, manifest, config)

### 4.4 Image Layers & Union Filesystem

```
docker pull nginx:latest

Layer 5: COPY nginx.conf         [  2 KB] ← Writable (container layer)
Layer 4: EXPOSE 80               [  0 KB] ← Metadata only
Layer 3: RUN apt-get install     [ 25 MB]
Layer 2: RUN apt-get update      [ 30 MB]
Layer 1: FROM debian:bullseye    [ 80 MB] ← Base image
─────────────────────────────────────────
Total:                           ~135 MB

Union Filesystem (overlay2):
┌─────────────────────────┐
│   Container Layer (RW)  │ ← Mỗi container có layer riêng
├─────────────────────────┤
│   Image Layer 5 (RO)   │
├─────────────────────────┤
│   Image Layer 4 (RO)   │ ← Shared giữa tất cả containers
├─────────────────────────┤   từ cùng image
│   Image Layer 3 (RO)   │
├─────────────────────────┤
│   Image Layer 2 (RO)   │
├─────────────────────────┤
│   Image Layer 1 (RO)   │
└─────────────────────────┘
```

**Copy-on-Write (CoW):**
- Image layers là **read-only**
- Khi container sửa file → copy file từ image layer lên container layer → sửa bản copy
- File gốc trong image layer không đổi → tất cả containers khác không bị ảnh hưởng

```bash
# Xem layers
docker history nginx:latest
# IMAGE          CREATED       CREATED BY                                      SIZE
# a8758716bb6a   5 days ago    CMD ["nginx" "-g" "daemon off;"]                0B
# <missing>      5 days ago    STOPSIGNAL SIGQUIT                              0B
# <missing>      5 days ago    EXPOSE 80                                       0B
# <missing>      5 days ago    COPY docker-entrypoint.sh /                     4.62kB
# <missing>      5 days ago    RUN /bin/sh -c set -x && ...                    61.1MB
# <missing>      5 days ago    ENV NGINX_VERSION=1.25.3                        0B
# <missing>      2 weeks ago   /bin/sh -c #(nop) CMD ["bash"]                  0B
# <missing>      2 weeks ago   /bin/sh -c #(nop) ADD file:... in /             74.8MB

# Xem filesystem overlay2
docker inspect nginx --format '{{.GraphDriver.Data.MergedDir}}'
```

### 4.5 Build Cache

Docker cache layer nếu instruction và context không đổi.

**Cache invalidation rules:**
1. Nếu instruction thay đổi → invalidate layer này VÀ tất cả layers sau
2. `COPY`/`ADD`: nếu file content thay đổi (checksum) → invalidate
3. `RUN`: nếu command string thay đổi → invalidate

```dockerfile
# ❌ Cache bị break mỗi lần code thay đổi
FROM node:20
COPY . /app                  # Code thay đổi → invalidate
RUN npm install              # Install lại mỗi lần! (vì layer trước invalidate)
CMD ["node", "app.js"]

# ✅ Tận dụng cache — lock file ít thay đổi
FROM node:20
WORKDIR /app
COPY package.json package-lock.json ./   # Lock file ít thay đổi
RUN npm ci                               # Cached nếu dependencies không đổi
COPY . .                                 # Code thay đổi chỉ invalidate từ đây
CMD ["node", "app.js"]
```

### 4.6 Multi-stage Build

```dockerfile
# Stage 1: Build (image lớn, có compiler)
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/server

# Stage 2: Runtime (image nhỏ, chỉ có binary)
FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /app/server /server
EXPOSE 8080
USER 65534:65534
CMD ["/server"]

# Build stage → ~500MB (Go compiler + tools)
# Runtime stage → ~15MB (Alpine + binary)
# Savings: ~97%!
```

---

## 5. Trade-offs & Best Practices ⭐

### Base Image Comparison

| Base Image | Size | Security | Debug | Use case |
|-----------|------|----------|-------|----------|
| `ubuntu:22.04` | ~77MB | Medium (nhiều packages) | ✅ apt, bash, tools | Development, legacy |
| `debian:bookworm-slim` | ~80MB | Medium | ✅ apt available | General purpose |
| `alpine:3.19` | ~7MB | Good (ít packages) | ⚠️ musl, ash shell | Size-sensitive |
| `gcr.io/distroless/static` | ~2MB | Excellent (no shell) | ❌ Không debug được | Static binary (Go, Rust) |
| `scratch` | 0MB | Perfect (empty) | ❌ Nothing | Static binary chỉ |

### Khi nào dùng Alpine?

```
✅ Dùng Alpine khi:
├── Image size quan trọng (edge, IoT, nhiều microservices)
├── App không phụ thuộc glibc-specific features
├── Team quen với Alpine ecosystem
└── CI/CD pipeline cần pull image nhanh

❌ Tránh Alpine khi:
├── App dùng glibc-specific features (Python, Ruby native extensions)
├── DNS resolution issues (musl DNS resolver khác glibc)
├── Performance-sensitive workload (musl có thể chậm hơn glibc 5-10%)
└── Team không quen debug Alpine-specific issues
```

### Anti-patterns

```dockerfile
# ❌ Anti-pattern 1: Quá nhiều layers
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y wget
RUN apt-get clean

# ✅ Gộp thành 1 layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl wget && \
    rm -rf /var/lib/apt/lists/*

# ❌ Anti-pattern 2: COPY trước dependencies
COPY . /app
RUN pip install -r requirements.txt

# ✅ Dependencies trước, code sau
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY . /app

# ❌ Anti-pattern 3: Secret trong image
COPY .env /app/.env
RUN source .env && ./setup.sh
RUN rm /app/.env  # SECRET VẪN Ở LAYER TRƯỚC!

# ✅ Dùng build args hoặc runtime env
ARG DB_HOST
RUN echo "Configured" # Không bake secret
# Hoặc dùng Docker secrets / mount
RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret
```

---

## 6. Performance & Scalability ⭐

### Image Size ảnh hưởng production thế nào?

| Metric | Image 500MB | Image 50MB | Image 5MB |
|--------|-------------|------------|-----------|
| Pull time (100Mbps) | 40s | 4s | 0.4s |
| Cold start (K8s) | 45-60s | 8-12s | 2-3s |
| Registry storage (100 images) | 50GB | 5GB | 500MB |
| CI build cache transfer | Slow | Fast | Instant |
| Scale-up speed (new nodes) | Chậm | Nhanh | Rất nhanh |

### Build time optimization

```bash
# Đo build time
time docker build -t myapp:v1 .

# Build với BuildKit (nhanh hơn, parallel stages)
DOCKER_BUILDKIT=1 docker build -t myapp:v1 .

# Cache mount cho package managers
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

RUN --mount=type=cache,target=/go/pkg/mod \
    go build -o /app/server

# Layer caching statistics
docker system df -v  # Xem cache usage
```

### CPU Throttling Analysis

```bash
# Container bị throttle
docker run -d --name throttled --cpus=0.1 --rm stress-ng --cpu 1

# Check throttling stats
cat /sys/fs/cgroup/system.slice/docker-$(docker inspect throttled -f '{{.Id}}').scope/cpu.stat
# usage_usec 1234567
# user_usec 1234000
# system_usec 567
# nr_periods 100
# nr_throttled 95      ← 95% periods bị throttle!
# throttled_usec 9500000

# Dấu hiệu: nr_throttled / nr_periods cao → p99 latency spike
docker rm -f throttled
```

---

## 7. Security & Reliability Considerations

### Root vs Non-root

```dockerfile
# ❌ Chạy root (default)
FROM node:20
COPY . /app
CMD ["node", "app.js"]
# → Container chạy UID 0 → nếu container escape → root trên host!

# ✅ Non-root user
FROM node:20
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser
WORKDIR /app
COPY --chown=appuser:appuser . .
RUN npm ci --omit=dev
USER appuser
CMD ["node", "app.js"]
```

### Read-only Root Filesystem

```bash
# Chạy container read-only
docker run --read-only \
  --tmpfs /tmp \
  --tmpfs /var/run \
  myapp:v1

# App cần write → mount tmpfs cho thư mục cụ thể
```

### Secret KHÔNG bao giờ bake vào image

```bash
# Kiểm tra secret trong layers
docker history myapp:v1
# Nếu thấy COPY .env hoặc ARG chứa secret → LEAKED

# Dùng docker secret (Swarm) hoặc mount
docker build --secret id=mysecret,src=secret.txt -t myapp:v1 .
# Trong Dockerfile:
# RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret
```

---

## 8. Hands-on Example

### Tối ưu Dockerfile Node.js

```bash
# Setup project
mkdir -p /tmp/docker-demo && cd /tmp/docker-demo

cat > app.js << 'EOF'
const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({message: 'Hello from optimized container!', pid: process.pid}));
});
process.on('SIGTERM', () => { server.close(() => process.exit(0)); });
server.listen(8080, () => console.log('Server running on :8080'));
EOF

cat > package.json << 'EOF'
{"name": "demo", "version": "1.0.0", "main": "app.js", "dependencies": {"express": "^4.18.2"}}
EOF
```

#### Version 1: Naive Dockerfile

```dockerfile
# File: Dockerfile.naive
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
EXPOSE 8080
CMD ["node", "app.js"]
```

```bash
docker build -f Dockerfile.naive -t demo:naive .
docker images demo:naive
# REPOSITORY   TAG     SIZE
# demo         naive   ~1.1GB
```

#### Version 2: Optimized

```dockerfile
# File: Dockerfile.optimized
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force
COPY app.js .
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser
EXPOSE 8080
CMD ["node", "app.js"]
```

```bash
docker build -f Dockerfile.optimized -t demo:optimized .
docker images demo:optimized
# REPOSITORY   TAG         SIZE
# demo         optimized   ~250MB
```

#### Version 3: Alpine

```dockerfile
# File: Dockerfile.alpine
FROM node:20-alpine
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force
COPY app.js .
USER appuser
EXPOSE 8080
CMD ["node", "app.js"]
```

```bash
docker build -f Dockerfile.alpine -t demo:alpine .
docker images demo:alpine
# REPOSITORY   TAG      SIZE
# demo         alpine   ~180MB
```

#### So sánh kết quả

```bash
echo "=== Image Size Comparison ==="
docker images demo --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
# REPOSITORY   TAG         SIZE
# demo         naive       1.1GB
# demo         optimized   250MB
# demo         alpine      180MB

echo ""
echo "=== Layer Analysis ==="
docker history demo:naive --format "table {{.CreatedBy}}\t{{.Size}}" | head -10
echo "---"
docker history demo:alpine --format "table {{.CreatedBy}}\t{{.Size}}" | head -10

echo ""
echo "=== Verify ==="
docker run -d --name test-demo -p 8080:8080 demo:alpine
sleep 1
curl -s http://localhost:8080 | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080
# {"message":"Hello from optimized container!","pid":1}

# Verify non-root
docker exec test-demo whoami
# appuser

docker rm -f test-demo
```

### Tối ưu Dockerfile Golang

```bash
cat > main.go << 'EOF'
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{"message": "Hello from Go!", "pid": os.Getpid()})
	})
	go func() { log.Fatal(http.ListenAndServe(":8080", nil)) }()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM)
	<-sig
	log.Println("Shutting down")
}
EOF

cat > go.mod << 'EOF'
module demo
go 1.22
EOF
```

```dockerfile
# File: Dockerfile.go
# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o server

# Runtime stage
FROM scratch
COPY --from=builder /app/server /server
EXPOSE 8080
USER 65534:65534
ENTRYPOINT ["/server"]
```

```bash
docker build -f Dockerfile.go -t demo:go .
docker images demo:go
# REPOSITORY   TAG   SIZE
# demo         go    ~6MB  ← Extremely small!

docker run -d --name test-go -p 8081:8080 demo:go
curl -s http://localhost:8081
docker rm -f test-go
```

### Cleanup

```bash
docker rmi demo:naive demo:optimized demo:alpine demo:go 2>/dev/null
rm -rf /tmp/docker-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: PID 1 Problem

Container process chạy PID 1 nhưng không xử lý signal như init system.

```dockerfile
# ❌ Shell form → chạy trong /bin/sh → app không nhận SIGTERM
CMD node app.js
# PID 1: /bin/sh -c "node app.js"
# PID 2: node app.js  ← SIGTERM gửi cho PID 1, không forward!

# ✅ Exec form → app chạy trực tiếp PID 1
CMD ["node", "app.js"]
# PID 1: node app.js  ← Nhận SIGTERM trực tiếp

# ✅ Hoặc dùng tini (init system nhẹ)
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "app.js"]
```

### Pitfall 2: Zombie Processes

```bash
# Kiểm tra zombie process trong container
docker exec mycontainer ps aux | grep Z
# Z = zombie process

# Fix: dùng --init flag
docker run --init myimage
# Docker tự thêm tini init process
```

### Pitfall 3: Build Cache Invalidation

```bash
# Debug build cache
DOCKER_BUILDKIT=1 docker build --progress=plain -t myapp . 2>&1 | grep -E "CACHED|RUN|COPY"
# CACHED [2/5] COPY package.json ...   ← Cached ✅
# [3/5] RUN npm ci ...                  ← Not cached ❌ (vì layer 2 invalidated)
```

### Pitfall 4: Alpine DNS Issues

```bash
# Triệu chứng: DNS resolution chậm hoặc fail trong container Alpine
# Nguyên nhân: musl libc DNS resolver khác glibc

# Fix 1: Thêm DNS options
echo "options ndots:0" >> /etc/resolv.conf

# Fix 2: Dùng debian-slim thay vì Alpine
FROM node:20-slim  # thay vì node:20-alpine
```

### Case Study: Secret Leaked in Image Layer

**Context**: Team deploy microservice, image push lên public registry.

**Symptom**: Scanner phát hiện AWS credentials trong image.

**Investigation**:
```bash
docker history myapp:v1.2.3 --no-trunc
# Thấy: COPY .env /app/.env ở layer 3
# Thấy: RUN rm /app/.env ở layer 5
# → Secret vẫn tồn tại ở layer 3!
```

**Root Cause**: Developer copy `.env` vào image để build, sau đó xóa. Nhưng xóa chỉ tạo layer mới (whiteout file), layer cũ vẫn chứa secret.

**Fix**:
1. Rotate tất cả credentials ngay lập tức
2. Rebuild image không có secret
3. Dùng multi-stage build hoặc `--mount=type=secret`
4. Thêm `.env` vào `.dockerignore`

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ Phase 1

| Bài | Áp dụng |
|-----|---------|
| Day 2 (Process/Signal) | Container = process, PID 1 signal handling |
| Day 4 (Performance) | cgroup limits, CPU throttling, memory pressure |
| Day 5 (Automation) | Dockerfile là automation cho build process |
| Day 7 (Mini-project) | Service từ mini-project sẽ được containerize |

### Preview bài sau

| Bài | Mở rộng |
|-----|---------|
| Day 9 | Container Image Optimization & Security — scan, non-root, distroless |
| Day 10 | Kubernetes Architecture — orchestrate containers bạn vừa build |
| Day 18 | Resource Requests/Limits — K8s áp dụng cgroup limits |

---

## 11. Tài liệu tham khảo

### Must-read
- [Docker Overview](https://docs.docker.com/get-started/docker-overview/) — Official Docker docs
- [Dockerfile Best Practices](https://docs.docker.com/build/building/best-practices/) — Official guide
- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec) — Container runtime standard

### Nice-to-have
- [Jess Frazelle: Containers from Scratch](https://jvns.ca/blog/2016/10/10/what-even-is-a-container/) — Build container with Linux primitives
- [Ivan Velichko: Container Internals](https://iximiuz.com/en/posts/container-networking-is-simple/) — Excellent visual explanations
- [Google Distroless](https://github.com/GoogleContainerTools/distroless) — Minimal container images

### Deep-dive
- [Linux Namespaces (man7.org)](https://man7.org/linux/man-pages/man7/namespaces.7.html) — Manpage reference
- [Cgroup v2 Documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html) — Kernel docs
- ["Container Security" by Liz Rice](https://www.oreilly.com/library/view/container-security/9781492056690/) — Comprehensive security book

