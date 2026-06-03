# Day 9: Container Image Optimization & Security

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Scan được** container image bằng Trivy và phân loại severity của CVE.
2. **Chuyển đổi được** Dockerfile từ root sang non-root user đúng cách cho từng ngôn ngữ.
3. **Đánh giá được** trade-off giữa Alpine, Distroless, và Scratch cho từng use case.
4. **Hiểu được** supply chain risks và cách phòng tránh (image pinning, SBOM, signing).
5. **Xây dựng được** container image security pipeline tích hợp vào CI/CD.

---

## 2. Bối cảnh & Động lực

### Vì sao container security quan trọng?

Day 8 bạn đã học cách build container. Nhưng container **an toàn** là câu chuyện khác hoàn toàn.

**Thực tế production:**
- 75% container images chứa ít nhất 1 CVE ở mức HIGH hoặc CRITICAL (theo Snyk State of Container Security).
- Container chạy root là vector tấn công phổ biến nhất cho container escape.
- Secret bị bake vào image layer là nguyên nhân credential leak thường gặp nhất.
- Supply chain attack (SolarWinds, Codecov, Log4Shell) cho thấy dependency trust là vấn đề nghiêm trọng.

### Nếu bỏ qua container security?

| Rủi ro | Hậu quả |
|--------|---------|
| Container chạy root | Container escape → root access trên host |
| CVE trong base image | Remote code execution, data theft |
| Secret trong image layer | Credential leak dù đã "xóa" |
| Unverified base image | Supply chain attack, malware injection |
| No image scanning | Compliance violation, audit failure |

### Liên hệ với Day 8

| Day 8 đã học | Day 9 mở rộng |
|---|---|
| Image layers, copy-on-write | Secret vẫn tồn tại trong layer cũ |
| Base image (FROM) | So sánh security: Alpine vs Distroless vs Scratch |
| Namespace isolation | User namespace, non-root container |
| Multi-stage build | Giảm attack surface qua multi-stage |

---

## 3. Kiến thức nền tảng

### Container Attack Surface

```
┌─────────────────────────────────────────┐
│            Attack Surface                │
│                                          │
│  ┌─── Base Image ─────────────────────┐ │
│  │  OS packages (CVEs)                │ │
│  │  Libraries (vulnerable versions)   │ │
│  │  Shell & tools (attacker toolkit)  │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌─── Application Layer ──────────────┐ │
│  │  App dependencies (npm, pip, go)   │ │
│  │  Custom code vulnerabilities       │ │
│  │  Hardcoded secrets                 │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌─── Runtime Configuration ──────────┐ │
│  │  Running as root                   │ │
│  │  Excessive capabilities            │ │
│  │  Writable filesystem               │ │
│  │  Privileged mode                   │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Vì sao Root trong Container nguy hiểm?

```
# Container chạy root (UID 0)
docker run --rm -it ubuntu whoami
# root

# Nếu container escape vulnerability tồn tại:
# UID 0 trong container = UID 0 trên host (khi không dùng user namespace)
# → Full root access trên host machine
# → Đọc/ghi bất kỳ file nào
# → Tạo container mới với --privileged
# → Pivot sang containers khác
```

**Defense in depth principle**: Dù namespace isolation "nên" ngăn escape, luôn chạy non-root vì:
1. Giảm blast radius nếu có escape vulnerability
2. Ngăn ghi vào system files trong container
3. Compliance requirement (PCI-DSS, SOC2, HIPAA)

---

## 4. Deep Dive

### 4.1 Root vs Non-root Container

```dockerfile
# Pattern cho Node.js
FROM node:20-alpine
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup package*.json ./
RUN npm ci --omit=dev
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["node", "app.js"]

# Pattern cho Golang (scratch)
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /server

FROM scratch
COPY --from=builder /server /server
USER 65534:65534
ENTRYPOINT ["/server"]

# Pattern cho Python
FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r appgroup && useradd -r -g appgroup -s /sbin/nologin appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appgroup . .
USER appuser
CMD ["python", "app.py"]

# Pattern cho Java
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup target/app.jar .
USER appuser
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
```

### 4.2 Base Image Comparison

```
Attack Surface (packages/binaries):

scratch        │                    ← 0 packages
distroless     │██                  ← ~20 packages (CA certs, tzdata)
alpine         │████████            ← ~50 packages
debian-slim    │████████████████    ← ~100 packages
ubuntu         │████████████████████ ← ~150 packages

Image Size:

scratch        │                    ← 0 MB
distroless     │█                   ← 2-20 MB
alpine         │██                  ← 7 MB
debian-slim    │████████            ← 80 MB
ubuntu         │██████████          ← 77 MB
node:20        │████████████████████████████ ← 1.1 GB
```

| Base | Size | Shell | Package Mgr | Debug | glibc | CVEs typical |
|------|------|-------|-------------|-------|-------|-------------|
| `scratch` | 0MB | ❌ | ❌ | ❌ | ❌ | 0 |
| `distroless/static` | ~2MB | ❌ | ❌ | ❌ | ❌ | 0-2 |
| `distroless/base` | ~20MB | ❌ | ❌ | ❌ | ✅ | 2-5 |
| `alpine:3.19` | ~7MB | ✅ ash | ✅ apk | ⚠️ | ❌ musl | 0-5 |
| `debian:bookworm-slim` | ~80MB | ✅ bash | ✅ apt | ✅ | ✅ | 10-30 |
| `ubuntu:22.04` | ~77MB | ✅ bash | ✅ apt | ✅ | ✅ | 10-40 |

### 4.3 Alpine Trade-offs

```
✅ Alpine ưu điểm:
├── Image nhỏ (~7MB base)
├── Ít package = ít CVE
├── Có shell (debug được)
├── Có package manager (cài thêm tool khi cần)
└── Community lớn, documentation tốt

❌ Alpine nhược điểm:
├── musl libc (không phải glibc)
│   ├── DNS resolver behavior khác
│   │   └── ndots:5 default trong K8s gây DNS lookup chậm
│   ├── Thread stack size mặc định nhỏ hơn
│   ├── Một số C extension không compatible
│   │   └── Python packages với native code có thể fail
│   └── Performance có thể chậm hơn 5-10% cho một số workload
├── Không có bash (chỉ có ash/sh)
└── Một số tool khác behavior so với glibc-based distro
```

**Alpine DNS issue trong Kubernetes:**
```yaml
# Kubernetes default resolv.conf
nameserver 10.96.0.10
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5

# Khi app resolve "api.external.com":
# musl DNS resolver kiểm tra ndots (số dấu chấm)
# "api.external.com" có 2 dots < ndots:5
# → Thử: api.external.com.default.svc.cluster.local (fail)
# → Thử: api.external.com.svc.cluster.local (fail)
# → Thử: api.external.com.cluster.local (fail)
# → Cuối cùng: api.external.com (success)
# → 3 DNS queries thừa, thêm 15-50ms latency!

# Fix: set ndots:1 trong Pod spec
# dnsConfig:
#   options:
#     - name: ndots
#       value: "1"
```

### 4.4 Image Scanning với Trivy

```
Scanning Flow:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Docker   │───▶│  Trivy   │───▶│ Vuln DB  │───▶│  Report  │
│  Image    │    │  Scanner │    │ (NVD,    │    │  (JSON/  │
│           │    │          │    │  Alpine, │    │  Table)  │
│           │    │          │    │  Debian) │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘

Trivy kiểm tra:
├── OS packages (apt, apk, yum)
├── Application dependencies
│   ├── npm/yarn (package-lock.json)
│   ├── pip (requirements.txt)
│   ├── go (go.sum)
│   ├── maven (pom.xml)
│   └── cargo (Cargo.lock)
├── Dockerfile misconfigurations
├── Secrets trong image
└── License compliance
```

```bash
# Cài Trivy
# macOS: brew install trivy
# Linux: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh

# Scan image
trivy image nginx:latest
# Output:
# nginx:latest (debian 12.4)
# Total: 142 (UNKNOWN: 0, LOW: 85, MEDIUM: 45, HIGH: 10, CRITICAL: 2)
#
# ┌──────────────────┬────────────────┬──────────┬───────────┬──────────────────────────┐
# │     Library      │ Vulnerability  │ Severity │  Version  │    Fixed Version         │
# ├──────────────────┼────────────────┼──────────┼───────────┼──────────────────────────┤
# │ libssl3          │ CVE-2024-xxxx  │ CRITICAL │ 3.0.11    │ 3.0.13                   │
# │ libcurl4         │ CVE-2024-yyyy  │ HIGH     │ 7.88.1    │ 7.88.1-10+deb12u5        │
# └──────────────────┴────────────────┴──────────┴───────────┴──────────────────────────┘

# Scan chỉ HIGH/CRITICAL
trivy image --severity HIGH,CRITICAL nginx:latest

# Output JSON
trivy image --format json --output report.json nginx:latest

# Scan và fail nếu có CRITICAL
trivy image --exit-code 1 --severity CRITICAL nginx:latest

# Scan Dockerfile (misconfig check)
trivy config Dockerfile

# Scan filesystem (dependencies)
trivy fs --scanners vuln .
```

### 4.5 SBOM (Software Bill of Materials)

```
SBOM là gì?
├── Danh sách TẤT CẢ components trong image
├── Bao gồm: OS packages + app dependencies + libraries
├── Giống "bảng thành phần" (ingredient list) của phần mềm
├── Formats: SPDX (Linux Foundation), CycloneDX (OWASP)
└── Yêu cầu: Executive Order 14028 (US), EU Cyber Resilience Act
```

```bash
# Generate SBOM bằng Trivy
trivy image --format spdx-json --output sbom.json nginx:latest

# Generate SBOM bằng syft (Anchore)
syft nginx:latest -o spdx-json > sbom.json
syft nginx:latest -o cyclonedx-json > sbom-cyclonedx.json

# Scan SBOM for vulnerabilities
trivy sbom sbom.json
```

### 4.6 Supply Chain Risks

```
Supply Chain Attack Vectors:

1. Compromised Base Image
   └── Attacker inject malware vào popular image
       └── Ví dụ: typosquatting (ngnix thay vì nginx)

2. Dependency Confusion
   └── Malicious package trùng tên internal package
       └── Ví dụ: npm package "company-utils" trên public registry

3. CI/CD Pipeline Poisoning
   └── Attacker sửa build script, inject vào artifact
       └── Ví dụ: SolarWinds, Codecov

4. Registry Compromise
   └── Attacker push malicious image lên registry
       └── Ví dụ: Docker Hub automated builds

Prevention:
├── Pin image by digest (không dùng tag)
├── Scan tất cả dependencies
├── Sign và verify images
├── Private registry với access control
├── SBOM cho mọi release
└── Audit supply chain thường xuyên
```

**Image pinning by digest:**
```dockerfile
# ❌ Tag có thể bị overwrite
FROM node:20-alpine

# ✅ Digest là immutable
FROM node:20-alpine@sha256:abc123def456...

# Lấy digest
docker inspect node:20-alpine --format '{{index .RepoDigests 0}}'
```

---

## 5. Trade-offs & Best Practices ⭐

### Base Image Decision Framework

```
Chọn base image:

Go/Rust (static binary)?
├── Yes → scratch hoặc distroless/static
│         ✅ Nhỏ nhất, an toàn nhất
│         ❌ Không debug được (no shell)
│         💡 Dùng kubectl debug cho K8s
└── No ↓

Cần glibc?
├── Yes (Python native, Java, .NET) → distroless/{language} hoặc debian-slim
│         ✅ glibc compatible
│         ⚠️ Lớn hơn Alpine
└── No ↓

Cần shell để debug?
├── Yes → alpine
│         ✅ Nhỏ, có shell
│         ⚠️ musl DNS issues
└── No → distroless
          ✅ Nhỏ, an toàn
          ❌ Không debug được
```

### CVE Response Matrix

| Severity | Response Time | Action |
|----------|--------------|--------|
| CRITICAL | < 24 giờ | Patch ngay, rebuild và deploy |
| HIGH | < 1 tuần | Patch trong sprint tiếp theo |
| MEDIUM | < 1 tháng | Batch update |
| LOW | Next release | Update khi convenient |
| UNKNOWN | Assess | Research và classify lại |

### Scanning Strategy

```
Khi nào scan?

1. CI/CD Pipeline (build time)
   └── Scan mỗi PR → fail nếu CRITICAL
   
2. Registry (post-push)
   └── Scan định kỳ images trong registry
   └── Phát hiện CVE mới cho image đã deploy
   
3. Runtime (production)
   └── Scan containers đang chạy
   └── Detect drift từ approved image
```

### Anti-patterns

1. **Chỉ scan khi build, không scan lại**
   - CVE mới được phát hiện hàng ngày
   - Image an toàn hôm nay có thể có CRITICAL CVE ngày mai
   - Fix: scan registry định kỳ (daily)

2. **Ignore tất cả vulnerabilities vì quá nhiều**
   - Fix: focus CRITICAL + HIGH, tạo exception process cho false positives

3. **Dùng `:latest` tag**
   - Không reproducible, không biết version nào đang chạy
   - Fix: pin version hoặc digest

---

## 6. Performance & Scalability ⭐

### Image Size ảnh hưởng cold start

```
Kubernetes Pod startup:

1. Schedule pod to node          ~100ms
2. Pull image (if not cached)    <-- BOTTLENECK
   - 1GB image @ 100Mbps = 80s
   - 50MB image @ 100Mbps = 4s
   - 5MB image @ 100Mbps = 0.4s
3. Start container               ~100ms
4. App startup                   Varies

Cold start total:
  1GB image: 80-90 seconds
  50MB image: 5-10 seconds
  5MB image: 1-2 seconds

Impact on HPA scaling:
  Traffic spike → HPA triggers scale-up → new node pulls image
  Nếu image 1GB → 80s trước khi pod ready → user timeout!
```

### Scanning Time Impact on CI

```
CI Pipeline thêm scanning:

Without scanning:  build → test → push          (5 min)
With scanning:     build → test → scan → push   (7-12 min)

Optimization:
├── Parallel scan: scan image during push        (save 2-3 min)
├── Cache Trivy DB: download DB 1x/day           (save 30s/build)
├── Scan only diff layers: nếu base không đổi    (save 50%+ time)
└── Fail fast: scan CRITICAL only trước           (quick feedback)
```

---

## 7. Security & Reliability Considerations

### Container Capabilities

```bash
# Default capabilities Docker cấp cho container
docker run --rm alpine cat /proc/1/status | grep Cap

# Drop ALL capabilities, chỉ giữ cái cần
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE myapp

# Kubernetes Pod Security Context
# securityContext:
#   capabilities:
#     drop: ["ALL"]
#     add: ["NET_BIND_SERVICE"]
```

### Read-only Root Filesystem

```bash
# Chạy container read-only
docker run --read-only \
  --tmpfs /tmp \
  --tmpfs /var/run \
  myapp:v1

# App cần write logs?
docker run --read-only \
  --tmpfs /tmp \
  -v /var/log/myapp:/app/logs \
  myapp:v1
```

### Image Signing với Cosign

```bash
# Install cosign
# brew install cosign (macOS)
# go install github.com/sigstore/cosign/v2/cmd/cosign@latest

# Generate key pair
cosign generate-key-pair

# Sign image
cosign sign --key cosign.key myregistry.com/myapp:v1.0.0

# Verify image
cosign verify --key cosign.pub myregistry.com/myapp:v1.0.0

# Keyless signing (recommended — dùng OIDC identity)
cosign sign myregistry.com/myapp:v1.0.0
# → Authenticate qua GitHub/Google OIDC

# Verify keyless
cosign verify \
  --certificate-identity=user@example.com \
  --certificate-oidc-issuer=https://accounts.google.com \
  myregistry.com/myapp:v1.0.0
```

---

## 8. Hands-on Example

### Complete Security Hardening Exercise

```bash
# Setup
mkdir -p /tmp/security-demo && cd /tmp/security-demo

# Tạo app đơn giản
cat > app.js << 'EOF'
const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({status: 'ok', user: process.getuid?.() ?? 'N/A'}));
});
process.on('SIGTERM', () => server.close(() => process.exit(0)));
server.listen(8080, () => console.log(`Server on :8080 as UID ${process.getuid?.() ?? 'N/A'}`));
EOF

cat > package.json << 'EOF'
{"name":"sec-demo","version":"1.0.0","dependencies":{"express":"4.17.1"}}
EOF
```

#### Step 1: Vulnerable Dockerfile

```dockerfile
# File: Dockerfile.vulnerable
FROM node:18
WORKDIR /app
COPY . .
RUN npm install
# Giả lập secret bị bake vào
RUN echo "AWS_SECRET=AKIAIOSFODNN7EXAMPLE" > /app/.env
RUN rm /app/.env
CMD ["node", "app.js"]
```

```bash
docker build -f Dockerfile.vulnerable -t demo:vulnerable .
echo "=== Scan vulnerable image ==="
trivy image --severity HIGH,CRITICAL demo:vulnerable 2>/dev/null || echo "(Install trivy to scan)"

echo "=== Check for secrets in layers ==="
docker history demo:vulnerable --no-trunc | grep -i "secret\|aws\|env" || echo "Secret visible in history!"
```

#### Step 2: Secured Dockerfile

```dockerfile
# File: Dockerfile.secure
FROM node:20-alpine
WORKDIR /app

# Non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Dependencies first (cache)
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

# App code
COPY --chown=appuser:appgroup app.js .

# Switch to non-root
USER appuser

EXPOSE 8080
CMD ["node", "app.js"]
```

```bash
docker build -f Dockerfile.secure -t demo:secure .

echo "=== Compare sizes ==="
docker images demo --format "table {{.Tag}}\t{{.Size}}"

echo "=== Scan secure image ==="
trivy image --severity HIGH,CRITICAL demo:secure 2>/dev/null || echo "(Install trivy)"

echo "=== Verify non-root ==="
docker run --rm demo:secure whoami 2>/dev/null || \
  docker run --rm demo:secure id

echo "=== Test functionality ==="
docker run -d --name sec-test -p 8080:8080 demo:secure
sleep 1
curl -s http://localhost:8080 | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080
docker rm -f sec-test

echo "=== Check no secrets in history ==="
docker history demo:secure --no-trunc | grep -i "secret\|aws" || echo "No secrets found ✅"
```

#### Step 3: Generate SBOM

```bash
# Với Trivy
trivy image --format spdx-json --output sbom.json demo:secure 2>/dev/null
echo "SBOM generated: sbom.json"
cat sbom.json | python3 -m json.tool 2>/dev/null | head -20 || echo "(Trivy not installed)"
```

### Cleanup

```bash
docker rmi demo:vulnerable demo:secure 2>/dev/null
rm -rf /tmp/security-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Permission Denied sau khi chuyển Non-root

```bash
# Triệu chứng
# Error: EACCES: permission denied, open '/app/logs/app.log'

# Debug
docker run --rm demo:secure ls -la /app/
# → File owned by root, user là appuser

# Fix: COPY --chown hoặc RUN chown
COPY --chown=appuser:appgroup . .
# HOẶC
RUN chown -R appuser:appgroup /app
```

### Pitfall 2: Alpine DNS Issues trong Kubernetes

```bash
# Triệu chứng: DNS resolution chậm 5-10 giây
# Nguyên nhân: musl libc + ndots:5 default

# Debug
docker exec container cat /etc/resolv.conf
# search default.svc.cluster.local ...
# options ndots:5

# Fix trong K8s Pod spec:
# dnsConfig:
#   options:
#     - name: ndots
#       value: "1"
```

### Pitfall 3: Distroless — Không debug được

```bash
# Triệu chứng: cần debug container nhưng không có shell
docker exec distroless-container sh
# OCI runtime exec failed: exec failed: unable to start container process: exec: "sh": not found

# Fix 1: Kubernetes ephemeral containers
kubectl debug -it POD_NAME --image=busybox --target=CONTAINER_NAME

# Fix 2: Copy debug tools vào volume
docker run -v debugtools:/tools busybox cp /bin/sh /tools/
docker run -v debugtools:/tools distroless-container /tools/sh

# Fix 3: Dùng debug variant
FROM gcr.io/distroless/base:debug  # Có busybox shell
```

### Pitfall 4: False CVEs blocking CI

```bash
# Triệu chứng: CI fail vì CVE không applicable

# Tạo ignore file
cat > .trivyignore << 'EOF'
# CVE not applicable - we don't use affected function
CVE-2024-12345

# Will be fixed in next base image update (tracked in JIRA-456)
CVE-2024-67890
EOF

# Scan với ignore
trivy image --ignorefile .trivyignore --severity CRITICAL demo:secure
```

### Case Study: Leaked AWS Credentials trong Docker Hub Image

**Context**: SaaS startup, 20 developers, auto-build Docker images trên Docker Hub.

**Symptom**: AWS bill tăng đột biến ($50K/ngày). CloudTrail cho thấy API calls từ IP lạ.

**Investigation**: Trivy scan image trên Docker Hub → phát hiện AWS access key trong layer 3 (COPY .env). Developer đã xóa `.env` ở layer sau nhưng layer cũ vẫn chứa secret.

**Root Cause**: `.env` chứa AWS credentials, bị COPY vào image. `RUN rm .env` chỉ tạo whiteout file ở layer mới, không xóa data ở layer cũ.

**Fix**:
1. Rotate tất cả AWS credentials ngay lập tức
2. Xóa image khỏi Docker Hub
3. Thêm `.env` vào `.dockerignore`
4. Chuyển sang Docker secrets / runtime environment variables
5. Thêm gitleaks pre-commit hook
6. Thêm Trivy secret scanning vào CI

**Lesson**: Image layers là immutable. Secrets bake vào image KHÔNG BAO GIỜ xóa được hoàn toàn chỉ bằng `rm`.

---

## 10. Kết nối với bài trước & bài sau

### Kiến thức từ bài trước

| Bài | Áp dụng |
|-----|---------|
| Day 8 (Docker Internals) | Image layers → hiểu vì sao secret tồn tại dù đã rm |
| Day 8 (Multi-stage) | Multi-stage → giảm attack surface |
| Day 8 (Namespace) | User namespace → non-root isolation |

### Preview bài sau

| Bài | Mở rộng |
|-----|---------|
| Day 10 (K8s Architecture) | Secured images deploy lên K8s cluster |
| Day 14 (Secret Management) | External secret management cho containers |
| Day 20 (RBAC, Pod Security) | Pod Security Standards enforce non-root |
| Day 21 (Admission Controller) | Policy: chỉ cho images từ trusted registry |
| Day 37 (Supply Chain) | Cosign, SBOM, SLSA trong CI/CD pipeline |

---

## 11. Tài liệu tham khảo

### Must-read
- [Trivy Documentation](https://aquasecurity.github.io/trivy/) — Official Trivy docs
- [Docker Security Best Practices](https://docs.docker.com/build/building/best-practices/#security) — Official Docker guide
- [Google Distroless](https://github.com/GoogleContainerTools/distroless) — Distroless images repo

### Nice-to-have
- [NIST Container Security Guide (SP 800-190)](https://csrc.nist.gov/publications/detail/sp/800-190/final) — Government security standard
- [Chainguard Images](https://www.chainguard.dev/chainguard-images) — Hardened container images
- [Sigstore/Cosign](https://docs.sigstore.dev/) — Container signing

### Deep-dive
- [Container Security by Liz Rice](https://www.oreilly.com/library/view/container-security/9781492056690/) — O'Reilly book
- [SLSA Framework](https://slsa.dev/) — Supply chain security levels
- [Snyk State of Container Security](https://snyk.io/blog/container-security/) — Industry report

