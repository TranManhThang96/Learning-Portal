# Day 8: Exercises — Docker Internals

---

## Exercise 1: Khám phá Namespace và Cgroup (Easy)

### Context

Bạn cần hiểu container hoạt động thế nào ở mức OS. Bài tập này giúp bạn "nhìn thấy" namespace và cgroup của một container đang chạy.

### Yêu cầu

1. Chạy một container nginx.
2. Tìm PID của container process trên host.
3. Liệt kê tất cả namespace của container.
4. So sánh namespace container vs host.
5. Xem cgroup limits đang áp dụng.
6. Chạy container với resource limits và verify qua cgroup.

### Expected Outcome

- Biết PID của container process trên host.
- Liệt kê được 7 loại namespace.
- Thấy namespace IDs khác nhau giữa container và host.
- Xem được CPU/memory limit từ cgroup filesystem.

### Hint

- `docker inspect --format '&#123;&#123;.State.Pid&#125;&#125;' CONTAINER`
- `ls -la /proc/PID/ns/`
- `/sys/fs/cgroup/` chứa cgroup settings

### Acceptance Criteria

- [ ] Container nginx chạy thành công
- [ ] Tìm được PID trên host
- [ ] List được namespaces (PID, NET, MNT, UTS, IPC, USER, CGROUP)
- [ ] So sánh namespace IDs host vs container
- [ ] Xem được memory.max và cpu.max từ cgroup
- [ ] Container với `--memory=128m --cpus=0.5` verify qua cgroup

### Bonus Challenge

Dùng `nsenter` để vào namespace của container và chạy `ip addr`, `ps aux` từ host.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

echo "=== 1. Run container ==="
docker run -d --name ns-demo --memory=128m --cpus=0.5 nginx:alpine
sleep 2

echo ""
echo "=== 2. Find container PID on host ==="
CPID=$(docker inspect ns-demo --format '{{.State.Pid}}')
echo "Container PID on host: $CPID"

echo ""
echo "=== 3. List container namespaces ==="
ls -la /proc/$CPID/ns/ 2>/dev/null || echo "(Requires Linux host - skip on Docker Desktop)"

echo ""
echo "=== 4. Compare with host (PID 1) ==="
echo "Host namespaces:"
ls -la /proc/1/ns/ 2>/dev/null | head -5 || echo "(Requires Linux host)"
echo ""
echo "Container namespaces:"
ls -la /proc/$CPID/ns/ 2>/dev/null | head -5 || echo "(Requires Linux host)"

echo ""
echo "=== 5. Check cgroup limits ==="
CID=$(docker inspect ns-demo --format '{{.Id}}')
echo "Container ID: $CID"

# Docker Desktop uses different cgroup paths
echo "Memory limit:"
docker inspect ns-demo --format '{{.HostConfig.Memory}}' | awk '{printf "  %d MB\n", $1/1024/1024}'
echo "CPU limit:"
docker inspect ns-demo --format '{{.HostConfig.NanoCpus}}' | awk '{printf "  %.1f CPUs\n", $1/1000000000}'

echo ""
echo "=== 6. Docker stats verification ==="
docker stats ns-demo --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "=== 7. Namespace exploration (Bonus) ==="
echo "Network namespace view:"
docker exec ns-demo ip addr 2>/dev/null || echo "(ip not available in container)"
echo ""
echo "PID namespace view:"
docker exec ns-demo ps aux 2>/dev/null || echo "(ps not available - use: docker top ns-demo)"
docker top ns-demo

echo ""
echo "=== Cleanup ==="
docker rm -f ns-demo
echo "Done!"
```

</details>

---

## Exercise 2: Tối ưu Dockerfile — Giảm Size 80%+ (Medium)

### Context

Team bạn có một Node.js API service với Dockerfile chưa tối ưu. Image hiện tại ~1.1GB, deploy lên Kubernetes mất 45 giây để pull image mỗi lần scale up. Bạn cần tối ưu xuống dưới 200MB.

### Yêu cầu

1. Tạo project Node.js đơn giản.
2. Viết Dockerfile "naive" (chưa tối ưu) — đo size.
3. Tối ưu theo 3 bước:
   - Step 1: Sắp xếp layer order cho build cache
   - Step 2: Dùng slim base image
   - Step 3: Dùng Alpine base
4. So sánh size, build time, layer count.
5. Verify mỗi version chạy đúng.

### Expected Outcome

| Version | Base | Size | Build cache |
|---------|------|------|-------------|
| v1-naive | node:20 | ~1.1GB | ❌ Broken |
| v2-cached | node:20 | ~1.1GB | ✅ Working |
| v3-slim | node:20-slim | ~250MB | ✅ Working |
| v4-alpine | node:20-alpine | ~180MB | ✅ Working |

### Hint

- Tách `COPY package*.json` trước `COPY . .`
- `npm ci --omit=dev` thay vì `npm install`
- `npm cache clean --force` giảm cache size
- `--no-install-recommends` cho apt-get

### Acceptance Criteria

- [ ] 4 Dockerfile versions tạo thành công
- [ ] Image cuối cùng < 200MB
- [ ] Build cache hoạt động (rebuild sau khi sửa code không re-install deps)
- [ ] Tất cả images trả về response đúng khi chạy
- [ ] `docker history` cho thấy layer structure khác nhau

### Bonus Challenge

Thêm version 5: multi-stage build (build trong node:20, chạy trong alpine). Đo build time so sánh.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

WORKDIR="/tmp/docker-optimize"
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR" && cd "$WORKDIR"

# Create project
cat > app.js << 'EOF'
const express = require('express');
const app = express();
app.get('/health', (req, res) => res.json({status: 'ok', version: '1.0.0'}));
app.get('/api/info', (req, res) => res.json({service: 'demo', pid: process.pid}));
process.on('SIGTERM', () => process.exit(0));
app.listen(8080, () => console.log('Server on :8080'));
EOF

cat > package.json << 'EOF'
{
  "name": "docker-demo",
  "version": "1.0.0",
  "dependencies": { "express": "^4.18.2" }
}
EOF

npm install --silent 2>/dev/null

# V1: Naive
cat > Dockerfile.v1 << 'EOF'
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
EXPOSE 8080
CMD ["node", "app.js"]
EOF

# V2: Better cache
cat > Dockerfile.v2 << 'EOF'
FROM node:20
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci && npm cache clean --force
COPY . .
EXPOSE 8080
CMD ["node", "app.js"]
EOF

# V3: Slim
cat > Dockerfile.v3 << 'EOF'
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force
COPY app.js .
RUN groupadd -r app && useradd -r -g app app
USER app
EXPOSE 8080
CMD ["node", "app.js"]
EOF

# V4: Alpine
cat > Dockerfile.v4 << 'EOF'
FROM node:20-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force
COPY app.js .
USER app
EXPOSE 8080
CMD ["node", "app.js"]
EOF

# Build all
for v in v1 v2 v3 v4; do
    echo "Building $v..."
    time docker build -f "Dockerfile.$v" -t "demo:$v" . 2>&1 | tail -1
done

# Compare
echo ""
echo "=== Size Comparison ==="
docker images demo --format "table {{.Tag}}\t{{.Size}}"

# Test each
echo ""
echo "=== Functional Test ==="
for v in v1 v2 v3 v4; do
    docker run -d --name "test-$v" -p "808${v#v}:8080" "demo:$v" 2>/dev/null
    sleep 1
    RESULT=$(curl -sf "http://localhost:808${v#v}/health" 2>/dev/null || echo "FAIL")
    echo "$v: $RESULT"
    docker rm -f "test-$v" > /dev/null 2>&1
done

# Cache test
echo ""
echo "=== Cache Test (modify app.js, rebuild v4) ==="
echo '// modified' >> app.js
time docker build -f Dockerfile.v4 -t demo:v4-rebuild . 2>&1 | grep -E "CACHED|COPY|RUN"

# Cleanup
echo ""
echo "Cleanup: docker rmi demo:v1 demo:v2 demo:v3 demo:v4 demo:v4-rebuild"
echo "         rm -rf $WORKDIR"
```

</details>

---

## Exercise 3: Production-ready Dockerfile với Security (Hard)

### Context

Bạn cần build Dockerfile cho một Golang API service sẽ chạy trong Kubernetes production. Yêu cầu:
- Image size < 20MB
- Non-root user
- Không có secret trong image layers
- Health check built-in
- Signal handling đúng (graceful shutdown)
- Hardened security (no shell, read-only compatible)

### Yêu cầu

1. Viết Go service đơn giản với `/health`, `/api/data`, graceful shutdown.
2. Viết multi-stage Dockerfile:
   - Build stage: `golang:1.22-alpine`
   - Runtime stage: `scratch` hoặc `gcr.io/distroless/static`
3. Đảm bảo: non-root, no shell, static binary, minimal layers.
4. Test: health check, graceful shutdown, image size.
5. Phân tích layers bằng `docker history`.
6. So sánh security: root vs non-root, alpine vs scratch.

### Expected Outcome

- Image < 20MB với scratch, hoặc < 10MB với `-ldflags="-s -w"`.
- Container chạy non-root (UID 65534).
- `docker exec` fail vì không có shell (scratch image).
- Graceful shutdown log khi `docker stop`.

### Hint

- `CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w"` cho static binary nhỏ nhất.
- `USER 65534:65534` là nobody user.
- `COPY --from=builder` copy binary từ build stage.
- `docker stop` gửi SIGTERM, chờ 10s, rồi SIGKILL.

### Acceptance Criteria

- [ ] Multi-stage build thành công
- [ ] Image < 20MB
- [ ] Container chạy UID 65534 (non-root)
- [ ] `/health` trả về 200
- [ ] `docker stop` → graceful shutdown log
- [ ] `docker exec container sh` fail (no shell)
- [ ] `docker history` không chứa secret nào
- [ ] HEALTHCHECK instruction hoạt động

### Bonus Challenge

1. Thêm HEALTHCHECK instruction trong Dockerfile.
2. Build cho multi-architecture: `docker buildx build --platform linux/amd64,linux/arm64`.
3. Tạo `.dockerignore` tối ưu.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

WORKDIR="/tmp/docker-prod"
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR" && cd "$WORKDIR"

# Go service
cat > main.go << 'GOCODE'
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

var startTime = time.Now()

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "healthy",
			"uptime": time.Since(startTime).String(),
		})
	})

	mux.HandleFunc("/api/data", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"service": "production-api",
			"version": "1.0.0",
			"pid":     os.Getpid(),
		})
	})

	server := &http.Server{Addr: ":8080", Handler: mux}

	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("Server starting on :8080 (PID: %d)", os.Getpid())
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-done
	log.Println("Received shutdown signal")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	server.Shutdown(ctx)
	log.Println("Server stopped gracefully")
}
GOCODE

cat > go.mod << 'EOF'
module production-api
go 1.22
EOF

# .dockerignore
cat > .dockerignore << 'EOF'
.git
.gitignore
*.md
Dockerfile*
docker-compose*
.env
.env.*
*.test
*.bench
vendor/
tmp/
EOF

# Production Dockerfile
cat > Dockerfile << 'DOCKERFILE'
# Build stage
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /server main.go

# Runtime stage
FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /server /server
EXPOSE 8080
USER 65534:65534
ENTRYPOINT ["/server"]
DOCKERFILE

# Build
echo "=== Building production image ==="
docker build -t prod-api:v1 .

# Analysis
echo ""
echo "=== Image Size ==="
docker images prod-api:v1 --format "{{.Repository}}:{{.Tag}} — {{.Size}}"

echo ""
echo "=== Layer Analysis ==="
docker history prod-api:v1

echo ""
echo "=== Run Test ==="
docker run -d --name prod-test -p 8080:8080 prod-api:v1
sleep 2

echo "Health check:"
curl -sf http://localhost:8080/health | python3 -m json.tool 2>/dev/null || curl -sf http://localhost:8080/health
echo ""

echo "API data:"
curl -sf http://localhost:8080/api/data | python3 -m json.tool 2>/dev/null || curl -sf http://localhost:8080/api/data
echo ""

echo "=== Security Checks ==="
echo "User ID:"
docker inspect prod-test --format '{{.Config.User}}'

echo "Shell test (should fail):"
docker exec prod-test sh 2>&1 || echo "  → No shell available (expected for scratch image)"

echo ""
echo "=== Graceful Shutdown Test ==="
echo "Stopping container (SIGTERM)..."
docker stop prod-test 2>&1
echo "Check logs:"
docker logs prod-test 2>&1 | tail -3

echo ""
echo "=== Cleanup ==="
docker rm -f prod-test 2>/dev/null
echo "docker rmi prod-api:v1"
echo "rm -rf $WORKDIR"
```

</details>

---

## Tổng kết

| Exercise | Thời gian | Kỹ năng |
|----------|-----------|---------|
| Easy | 20 phút | Namespace, cgroup, container internals |
| Medium | 35 phút | Dockerfile optimization, layer caching |
| Hard | 45 phút | Production Dockerfile, security, multi-stage |
| **Tổng** | **~100 phút** | |

