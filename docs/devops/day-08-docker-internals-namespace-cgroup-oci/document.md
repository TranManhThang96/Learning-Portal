# Day 8: Document — Docker Internals Reference

## 1. Docker Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Client (CLI)                    │
│                    docker build / run / push              │
└────────────────────────┬─────────────────────────────────┘
                         │ REST API
                         ▼
┌──────────────────────────────────────────────────────────┐
│                  Docker Engine (dockerd)                  │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Image Manager │  │  Network     │  │  Volume      │ │
│  │  (build/pull)  │  │  Manager     │  │  Manager     │ │
│  └────────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────────┬─────────────────────────────────┘
                         │ gRPC
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    containerd                             │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Container     │  │  Content     │  │  Snapshot    │ │
│  │  Service       │  │  Store       │  │  Manager     │ │
│  └────────┬───────┘  └──────────────┘  └──────────────┘ │
│           │ OCI Runtime Spec                              │
│           ▼                                               │
│  ┌────────────────┐                                      │
│  │     runc       │ ← OCI Runtime                        │
│  │                │                                      │
│  │  1. Clone      │                                      │
│  │  2. Namespace  │                                      │
│  │  3. Cgroup     │                                      │
│  │  4. Mount FS   │                                      │
│  │  5. Exec       │                                      │
│  └────────────────┘                                      │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Namespace Types Reference

| Namespace | Flag | Isolates | Kernel Version | Ý nghĩa production |
|-----------|------|----------|----------------|---------------------|
| **PID** | `CLONE_NEWPID` | Process IDs | 2.6.24 | Container thấy PID tree riêng |
| **NET** | `CLONE_NEWNET` | Network interfaces, IPs, ports | 2.6.29 | Container có network stack riêng |
| **MNT** | `CLONE_NEWNS` | Mount points | 2.4.19 | Container có filesystem riêng |
| **UTS** | `CLONE_NEWUTS` | Hostname, domain | 2.6.19 | Container có hostname riêng |
| **IPC** | `CLONE_NEWIPC` | SysV IPC, POSIX queues | 2.6.19 | Shared memory isolation |
| **USER** | `CLONE_NEWUSER` | UIDs, GIDs | 3.8 | UID 0 trong container ≠ UID 0 host |
| **CGROUP** | `CLONE_NEWCGROUP` | Cgroup root | 4.6 | Container chỉ thấy cgroup của mình |

### Namespace Commands

```bash
# Xem namespace của container
docker inspect CONTAINER --format '{{.State.Pid}}'
ls -la /proc/PID/ns/

# Vào namespace container từ host
sudo nsenter -t PID -n ip addr        # Network namespace
sudo nsenter -t PID -p -r ps aux      # PID namespace
sudo nsenter -t PID -m ls /           # Mount namespace

# Tạo container share namespace
docker run --pid=container:OTHER --network=container:OTHER IMAGE
```

---

## 3. Cgroup Parameters Reference

### CPU

| Parameter (cgroup v2) | Docker flag | Mô tả |
|------------------------|------------|--------|
| `cpu.max` | `--cpus=N` | CPU quota (max microseconds per period) |
| `cpu.weight` | `--cpu-shares=N` | Relative CPU weight (1-10000) |
| `cpuset.cpus` | `--cpuset-cpus="0,1"` | Pin to specific CPUs |

```bash
# Ví dụ
docker run --cpus=0.5 myapp          # 50% of 1 CPU
docker run --cpus=2 myapp            # 2 CPUs max
docker run --cpu-shares=512 myapp    # Half weight vs default 1024
docker run --cpuset-cpus="0,1" myapp # Only use CPU 0 and 1
```

### Memory

| Parameter (cgroup v2) | Docker flag | Mô tả |
|------------------------|------------|--------|
| `memory.max` | `--memory=N` | Hard memory limit |
| `memory.swap.max` | `--memory-swap=N` | Memory + swap limit |
| `memory.low` | `--memory-reservation=N` | Soft limit (best-effort) |

```bash
# Ví dụ
docker run --memory=256m myapp                   # 256MB memory limit
docker run --memory=256m --memory-swap=256m myapp # No swap allowed
docker run --memory=256m --memory-swap=512m myapp # 256MB swap

# OOM behavior
docker run --memory=64m --oom-kill-disable myapp  # Disable OOM killer (cẩn thận!)
```

### I/O

```bash
# Disk I/O limits
docker run --device-read-bps=/dev/sda:1mb myapp   # Read limit
docker run --device-write-bps=/dev/sda:1mb myapp   # Write limit
docker run --device-read-iops=/dev/sda:1000 myapp  # IOPS limit
```

### PIDs

```bash
docker run --pids-limit=100 myapp   # Max 100 processes
```

---

## 4. Dockerfile Instruction Reference

| Instruction | Best Practice | Anti-pattern |
|-------------|---------------|--------------|
| `FROM` | Dùng specific tag: `node:20-alpine` | `FROM node:latest` (unpinned) |
| `WORKDIR` | Luôn set: `WORKDIR /app` | `RUN cd /app && ...` |
| `COPY` | Copy deps trước: `COPY package.json ./` | `COPY . .` đầu tiên |
| `RUN` | Gộp commands: `RUN apt update && apt install && rm -rf...` | Mỗi command 1 RUN |
| `ENV` | Build-time config | Secret values |
| `ARG` | Build-time variables | `ARG PASSWORD=xxx` |
| `EXPOSE` | Document port: `EXPOSE 8080` | Bỏ qua |
| `USER` | Non-root: `USER 65534` | Mặc định root |
| `CMD` | Exec form: `CMD ["node", "app.js"]` | Shell form: `CMD node app.js` |
| `ENTRYPOINT` | Fixed command: `ENTRYPOINT ["/app"]` | Dùng khi cần override CMD |
| `HEALTHCHECK` | `HEALTHCHECK CMD curl -f localhost:8080/health` | Bỏ qua |

### Layer Size Tips

```dockerfile
# ❌ 3 layers, apt cache giữ lại
RUN apt-get update
RUN apt-get install -y curl wget
RUN apt-get clean

# ✅ 1 layer, clean trong cùng RUN
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl wget && \
    rm -rf /var/lib/apt/lists/*
```

---

## 5. Multi-stage Build Patterns

### Pattern 1: Build + Runtime (Go)

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server

FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /server /server
USER 65534:65534
ENTRYPOINT ["/server"]
```

### Pattern 2: Build + Runtime (Node.js)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build  # TypeScript → JavaScript

FROM node:20-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
USER app
CMD ["node", "dist/index.js"]
```

### Pattern 3: Build + Test + Runtime

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o /server

FROM builder AS tester
RUN go test ./...

FROM scratch
COPY --from=builder /server /server
ENTRYPOINT ["/server"]
```

### Pattern 4: Dev + Prod

```dockerfile
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./

FROM base AS dev
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]

FROM base AS prod
RUN npm ci --omit=dev
COPY . .
USER node
CMD ["node", "app.js"]
```

---

## 6. Image Optimization Checklist

### Build Time

- [ ] Dependencies copied trước source code (cache layers)
- [ ] `.dockerignore` loại bỏ `node_modules/`, `.git/`, `*.md`, test files
- [ ] BuildKit enabled (`DOCKER_BUILDKIT=1`)
- [ ] Cache mount cho package managers (`--mount=type=cache`)
- [ ] Multi-stage build tách build/runtime

### Image Size

- [ ] Base image nhỏ nhất phù hợp (alpine > slim > full)
- [ ] `--omit=dev` / `--no-dev` loại bỏ dev dependencies
- [ ] Package manager cache cleared (`rm -rf /var/lib/apt/lists/*`)
- [ ] Gộp RUN commands giảm layers
- [ ] Binary stripped (`-ldflags="-s -w"` cho Go)
- [ ] Multi-stage build chỉ copy artifacts cần thiết

### Security

- [ ] Non-root user (`USER 65534` hoặc custom user)
- [ ] No secrets trong image (check `docker history`)
- [ ] Specific image tag (không dùng `:latest`)
- [ ] Image pin by digest cho production critical
- [ ] HEALTHCHECK instruction thêm vào
- [ ] Read-only root filesystem compatible

---

## 7. Docker Debug Commands

### Container Inspection

```bash
# Overview
docker ps -a                                    # List all containers
docker inspect CONTAINER                        # Full JSON details
docker inspect CONTAINER --format '{{.State.Status}}'

# Logs
docker logs CONTAINER                           # All logs
docker logs CONTAINER -f                        # Follow
docker logs CONTAINER --since 5m                # Last 5 minutes
docker logs CONTAINER --tail 100                # Last 100 lines

# Process
docker top CONTAINER                            # Process list
docker stats CONTAINER --no-stream              # Resource usage

# Execute inside
docker exec -it CONTAINER sh                    # Shell access
docker exec CONTAINER cat /etc/os-release       # Run command
```

### Image Inspection

```bash
# List images
docker images                                   # All images
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Layer analysis
docker history IMAGE                            # Layer history
docker history IMAGE --no-trunc                 # Full commands

# Image details
docker inspect IMAGE                            # Full manifest
docker inspect IMAGE --format '{{.Config.Cmd}}'
docker inspect IMAGE --format '{{.Config.User}}'
docker inspect IMAGE --format '{{.Config.ExposedPorts}}'
```

### Network Debug

```bash
# Container network
docker network ls
docker network inspect bridge
docker inspect CONTAINER --format '{{.NetworkSettings.IPAddress}}'

# Test connectivity between containers
docker exec CONTAINER curl http://OTHER:PORT
docker exec CONTAINER ping OTHER
```

### Storage

```bash
# Disk usage
docker system df                                # Overview
docker system df -v                             # Detailed

# Cleanup
docker system prune                             # Remove unused data
docker image prune -a                           # Remove all unused images
docker volume prune                             # Remove unused volumes
docker builder prune                            # Remove build cache
```

---

## 8. .dockerignore Template

```gitignore
# Version control
.git
.gitignore

# Documentation
*.md
LICENSE

# Docker files
Dockerfile*
docker-compose*
.dockerignore

# IDE
.idea/
.vscode/
*.swp

# Environment
.env
.env.*

# Dependencies (will be installed in build)
node_modules/
vendor/
.venv/
__pycache__/

# Tests
*_test.go
*.test.js
*.spec.js
tests/
test/
coverage/

# Build artifacts
dist/
build/
tmp/

# OS files
.DS_Store
Thumbs.db

# CI/CD
.github/
.gitlab-ci.yml
Jenkinsfile

# Secrets
*.key
*.pem
*.p12
credentials*
```

---

## 9. Common Error → Fix Reference

| Error | Nguyên nhân | Fix |
|-------|-------------|-----|
| `COPY failed: file not found` | File không có hoặc bị .dockerignore | Kiểm tra path và .dockerignore |
| `failed to solve: no build stage` | FROM missing hoặc syntax sai | Kiểm tra Dockerfile syntax |
| `bind: address already in use` | Port đã bị chiếm | `docker rm -f` container cũ hoặc đổi port |
| `OOMKilled` | Container vượt memory limit | Tăng `--memory` hoặc fix memory leak |
| `exec format error` | Binary build cho arch khác | Build đúng GOARCH/platform |
| `permission denied` | Non-root user không có quyền | `chown` files, check permissions |
| `npm ERR! could not determine executable to run` | npm cache hoặc lock file lỗi | `npm ci` thay `npm install` |
| `no space left on device` | Docker disk full | `docker system prune` |
| `certificate signed by unknown authority` | Missing CA certs trong scratch | Copy `/etc/ssl/certs/ca-certificates.crt` |

