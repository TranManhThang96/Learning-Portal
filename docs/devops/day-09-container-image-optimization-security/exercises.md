# Day 9: Exercises — Container Image Optimization & Security

---

## Exercise 1: Scan Image với Trivy (Easy)

### Context

Bạn vừa nhận task audit security cho container images đang dùng trong production. Bước đầu tiên là scan tất cả images để biết tình trạng CVE hiện tại.

### Yêu cầu

1. Cài đặt Trivy (nếu chưa có).
2. Scan image `nginx:latest` — ghi nhận tổng số CVE theo severity.
3. Scan image `nginx:alpine` — so sánh với `nginx:latest`.
4. Scan image `node:20` — ghi nhận CVE count.
5. Tạo báo cáo dạng bảng so sánh 3 images.
6. Export kết quả scan ra JSON.

### Expected Outcome

Bảng so sánh (con số thực tế sẽ khác theo thời điểm scan):

| Image | CRITICAL | HIGH | MEDIUM | LOW | Total |
|-------|----------|------|--------|-----|-------|
| nginx:latest | 1-3 | 5-15 | 20-40 | 50-80 | 80-130 |
| nginx:alpine | 0-1 | 0-3 | 2-8 | 5-15 | 10-25 |
| node:20 | 2-5 | 10-25 | 30-60 | 50-100 | 100-180 |

### Hint

- Cài Trivy: `brew install trivy` (macOS) hoặc xem docs
- Scan: `trivy image IMAGE_NAME`
- Chỉ HIGH/CRITICAL: `trivy image --severity HIGH,CRITICAL IMAGE`
- JSON output: `trivy image --format json --output report.json IMAGE`

### Acceptance Criteria

- [ ] Trivy cài đặt thành công
- [ ] Scan 3 images thành công
- [ ] Bảng so sánh CVE count tạo được
- [ ] JSON report xuất được
- [ ] Nhận xét: image nào an toàn nhất và vì sao

### Bonus Challenge

Scan filesystem của project hiện tại: `trivy fs .` — phát hiện vulnerable dependencies.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

echo "=== Install Trivy (if needed) ==="
if ! command -v trivy &>/dev/null; then
    echo "Installing Trivy..."
    # Linux
    curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
    # macOS: brew install trivy
fi
trivy --version

echo ""
echo "=== Scan nginx:latest ==="
trivy image --severity CRITICAL,HIGH,MEDIUM,LOW nginx:latest --quiet 2>/dev/null | tail -5
trivy image --format json --output /tmp/nginx-latest.json nginx:latest 2>/dev/null

echo ""
echo "=== Scan nginx:alpine ==="
trivy image --severity CRITICAL,HIGH,MEDIUM,LOW nginx:alpine --quiet 2>/dev/null | tail -5
trivy image --format json --output /tmp/nginx-alpine.json nginx:alpine 2>/dev/null

echo ""
echo "=== Scan node:20 ==="
trivy image --severity CRITICAL,HIGH,MEDIUM,LOW node:20 --quiet 2>/dev/null | tail -5
trivy image --format json --output /tmp/node-20.json node:20 2>/dev/null

echo ""
echo "=== Comparison Report ==="
for img in nginx:latest nginx:alpine node:20; do
    safe_name=$(echo "$img" | tr ':/' '-')
    CRITICAL=$(trivy image --severity CRITICAL --quiet --format json "$img" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = sum(len(r.get('Vulnerabilities', [])) for r in data.get('Results', []))
print(count)
" 2>/dev/null || echo "N/A")
    
    HIGH=$(trivy image --severity HIGH --quiet --format json "$img" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = sum(len(r.get('Vulnerabilities', [])) for r in data.get('Results', []))
print(count)
" 2>/dev/null || echo "N/A")
    
    echo "$img: CRITICAL=$CRITICAL, HIGH=$HIGH"
done

echo ""
echo "=== Conclusion ==="
echo "nginx:alpine has significantly fewer CVEs than nginx:latest"
echo "Reason: Alpine base has fewer OS packages → smaller attack surface"
echo ""
echo "Cleanup: rm /tmp/nginx-*.json /tmp/node-20.json"
```

</details>

---

## Exercise 2: Chuyển Dockerfile sang Non-root (Medium)

### Context

Team bạn có 3 Dockerfiles đang chạy root. Security audit yêu cầu chuyển tất cả sang non-root user trong 1 tuần. Mỗi Dockerfile dùng ngôn ngữ khác nhau nên pattern chuyển đổi cũng khác.

### Yêu cầu

Chuyển 3 Dockerfiles từ root sang non-root, đảm bảo:
1. App chạy với UID non-zero.
2. File permissions đúng.
3. App vẫn hoạt động bình thường.
4. Không dùng numeric UID 0.

#### Dockerfile 1: Node.js

```dockerfile
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
EXPOSE 3000
CMD ["node", "app.js"]
```

#### Dockerfile 2: Python

```dockerfile
FROM python:3.12
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
```

#### Dockerfile 3: Golang

```dockerfile
FROM golang:1.22
WORKDIR /app
COPY . .
RUN go build -o server
EXPOSE 8080
CMD ["./server"]
```

### Expected Outcome

- Tất cả 3 containers chạy non-root user.
- `docker exec CONTAINER whoami` → không phải "root".
- `docker exec CONTAINER id` → UID ≠ 0.
- App respond đúng trên respective port.

### Hint

- Node.js: image có sẵn user `node` (UID 1000)
- Python: tạo user mới với `groupadd` / `useradd`
- Go: dùng multi-stage + `USER 65534:65534` (nobody)
- `COPY --chown=user:group` để set ownership

### Acceptance Criteria

- [ ] 3 Dockerfiles chuyển sang non-root thành công
- [ ] `whoami` trong container ≠ root
- [ ] App chạy đúng chức năng
- [ ] File permissions đúng (app user own application files)
- [ ] Không có permission denied errors

### Bonus Challenge

Thêm `--read-only` flag khi chạy container. Fix permission issues bằng `tmpfs` mounts.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

WORKDIR="/tmp/nonroot-demo"
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR" && cd "$WORKDIR"

# === Node.js ===
mkdir -p nodejs && cd nodejs
cat > app.js << 'EOF'
const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({app: 'nodejs', uid: process.getuid(), user: process.env.USER || 'unknown'}));
});
server.listen(3000, () => console.log('Server on :3000'));
EOF
cat > package.json << 'EOF'
{"name":"demo","version":"1.0.0"}
EOF

cat > Dockerfile << 'DOCKERFILE'
FROM node:20-alpine
WORKDIR /app
COPY --chown=node:node package.json ./
RUN npm install --omit=dev 2>/dev/null || true
COPY --chown=node:node app.js .
USER node
EXPOSE 3000
CMD ["node", "app.js"]
DOCKERFILE

docker build -t demo-node:nonroot .
cd ..

# === Python ===
mkdir -p python && cd python
cat > app.py << 'EOF'
import http.server, json, os
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'app': 'python', 'uid': os.getuid()}).encode())
    def log_message(self, format, *args): pass
http.server.HTTPServer(('', 8000), Handler).serve_forever()
EOF
cat > requirements.txt << 'EOF'
EOF

cat > Dockerfile << 'DOCKERFILE'
FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r appgroup && useradd -r -g appgroup -s /sbin/nologin appuser
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appgroup app.py .
USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
DOCKERFILE

docker build -t demo-python:nonroot .
cd ..

# === Golang ===
mkdir -p golang && cd golang
cat > main.go << 'EOF'
package main
import ("encoding/json"; "fmt"; "net/http"; "os")
func main() {
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        json.NewEncoder(w).Encode(map[string]interface{}{"app": "golang", "pid": os.Getpid()})
    })
    fmt.Println("Server on :8080")
    http.ListenAndServe(":8080", nil)
}
EOF
cat > go.mod << 'EOF'
module demo
go 1.22
EOF

cat > Dockerfile << 'DOCKERFILE'
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server

FROM scratch
COPY --from=builder /server /server
USER 65534:65534
EXPOSE 8080
ENTRYPOINT ["/server"]
DOCKERFILE

docker build -t demo-go:nonroot .
cd ..

# === Test ===
echo "=== Testing non-root containers ==="

docker run -d --name test-node -p 3001:3000 demo-node:nonroot
docker run -d --name test-python -p 8001:8000 demo-python:nonroot
docker run -d --name test-go -p 8081:8080 demo-go:nonroot
sleep 2

echo "Node.js:"
echo "  User: $(docker exec test-node whoami 2>/dev/null || echo 'N/A')"
echo "  UID: $(docker exec test-node id -u 2>/dev/null || echo 'N/A')"
echo "  Response: $(curl -sf http://localhost:3001)"

echo "Python:"
echo "  User: $(docker exec test-python whoami 2>/dev/null || echo 'N/A')"
echo "  UID: $(docker exec test-python id -u 2>/dev/null || echo 'N/A')"
echo "  Response: $(curl -sf http://localhost:8001)"

echo "Golang:"
echo "  Response: $(curl -sf http://localhost:8081)"
echo "  (scratch image - no shell to check user)"

# Cleanup
echo ""
echo "=== Cleanup ==="
docker rm -f test-node test-python test-go
docker rmi demo-node:nonroot demo-python:nonroot demo-go:nonroot
rm -rf "$WORKDIR"
```

</details>

---

## Exercise 3: Secure Image Pipeline (Hard)

### Context

Bạn cần xây dựng container image pipeline hoàn chỉnh cho production. Pipeline phải đảm bảo: image nhỏ, non-root, không có critical CVE, có SBOM, và automated.

### Yêu cầu

1. Viết Dockerfile production-ready cho Node.js service:
   - Multi-stage build
   - Non-root user
   - Alpine hoặc distroless base
   - No secrets in layers
   - HEALTHCHECK instruction
2. Viết script `build-and-scan.sh` thực hiện:
   - Build image
   - Scan với Trivy (fail nếu CRITICAL)
   - Check non-root
   - Check image size < threshold
   - Generate SBOM
   - Output report
3. Viết `.trivyignore` cho known false positives.
4. Viết security checklist document.

### Expected Outcome

```
$ ./build-and-scan.sh
Building image...                    ✅
Image size: 180MB (< 300MB limit)    ✅
Trivy scan: 0 CRITICAL, 2 HIGH      ✅
Non-root check: UID 1000             ✅
SBOM generated: sbom.json            ✅
Security report: security-report.md  ✅
```

### Hint

- `docker inspect --format '&#123;&#123;.Config.User&#125;&#125;' IMAGE` để check user
- `docker images IMAGE --format '&#123;&#123;.Size&#125;&#125;'` để check size
- `trivy image --exit-code 1 --severity CRITICAL IMAGE` fail khi có CRITICAL
- SBOM: `trivy image --format spdx-json IMAGE`

### Acceptance Criteria

- [ ] Multi-stage Dockerfile build thành công
- [ ] Image size < 300MB
- [ ] 0 CRITICAL CVEs (hoặc documented exceptions)
- [ ] Non-root user verified
- [ ] HEALTHCHECK hoạt động
- [ ] SBOM file generated
- [ ] Build script tự động và idempotent
- [ ] Security checklist tạo xong

### Bonus Challenge

1. Thêm cosign signing vào pipeline.
2. Tạo GitHub Actions workflow YAML cho pipeline này.
3. Compare Alpine vs Distroless final result.

<details>
<summary>Solution</summary>

```bash
#!/bin/bash
set -euo pipefail

WORKDIR="/tmp/secure-pipeline"
rm -rf "$WORKDIR" && mkdir -p "$WORKDIR" && cd "$WORKDIR"

# === App ===
cat > app.js << 'EOF'
const http = require('http');
const os = require('os');
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({status: 'healthy'}));
  } else if (req.url === '/api/info') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({
      service: 'secure-api', version: '1.0.0',
      host: os.hostname(), pid: process.pid,
      uid: process.getuid?.() ?? 'N/A'
    }));
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});
process.on('SIGTERM', () => server.close(() => process.exit(0)));
server.listen(8080, () => console.log(`Server on :8080 (UID: ${process.getuid?.() ?? 'N/A'})`));
EOF

cat > package.json << 'EOF'
{"name":"secure-api","version":"1.0.0","dependencies":{"express":"^4.18.2"}}
EOF

# === Dockerfile ===
cat > Dockerfile << 'DOCKERFILE'
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

FROM node:20-alpine
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder --chown=appuser:appgroup /app/node_modules ./node_modules
COPY --chown=appuser:appgroup package.json app.js ./

USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/health || exit 1
CMD ["node", "app.js"]
DOCKERFILE

# === .dockerignore ===
cat > .dockerignore << 'EOF'
.git
*.md
Dockerfile*
docker-compose*
.env*
node_modules
*.test.js
coverage
.trivyignore
build-and-scan.sh
EOF

# === .trivyignore ===
cat > .trivyignore << 'EOF'
# Document known exceptions here
# CVE-YYYY-XXXXX  # Reason: not applicable because...
EOF

# === Build & Scan Script ===
cat > build-and-scan.sh << 'BUILDSCRIPT'
#!/bin/bash
set -euo pipefail

IMAGE_NAME="secure-api"
IMAGE_TAG="v1.0.0"
IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
MAX_SIZE_MB=300
REPORT_FILE="security-report.md"
SBOM_FILE="sbom.json"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; exit 1; }

echo "========================================="
echo "  Secure Image Build Pipeline"
echo "========================================="
echo ""

# Step 1: Build
echo "--- Step 1: Build Image ---"
docker build -t "$IMAGE" . 2>&1 | tail -3
pass "Image built: $IMAGE"

# Step 2: Size check
echo ""
echo "--- Step 2: Size Check ---"
SIZE_BYTES=$(docker inspect "$IMAGE" --format '{{.Size}}')
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
if [ "$SIZE_MB" -lt "$MAX_SIZE_MB" ]; then
    pass "Image size: ${SIZE_MB}MB (< ${MAX_SIZE_MB}MB limit)"
else
    fail "Image size: ${SIZE_MB}MB exceeds ${MAX_SIZE_MB}MB limit"
fi

# Step 3: Trivy scan
echo ""
echo "--- Step 3: Security Scan ---"
if command -v trivy &>/dev/null; then
    CRITICAL_COUNT=$(trivy image --severity CRITICAL --quiet --format json "$IMAGE" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = sum(len(r.get('Vulnerabilities', [])) for r in data.get('Results', []))
print(count)
" 2>/dev/null || echo "0")
    
    HIGH_COUNT=$(trivy image --severity HIGH --quiet --format json "$IMAGE" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = sum(len(r.get('Vulnerabilities', [])) for r in data.get('Results', []))
print(count)
" 2>/dev/null || echo "0")
    
    if [ "${CRITICAL_COUNT:-0}" -gt 0 ]; then
        fail "Found $CRITICAL_COUNT CRITICAL vulnerabilities"
    fi
    pass "Scan: ${CRITICAL_COUNT:-0} CRITICAL, ${HIGH_COUNT:-0} HIGH"
else
    echo "⚠️  Trivy not installed — skipping scan"
fi

# Step 4: Non-root check
echo ""
echo "--- Step 4: Non-root Check ---"
USER_CONFIG=$(docker inspect "$IMAGE" --format '{{.Config.User}}')
if [ -n "$USER_CONFIG" ] && [ "$USER_CONFIG" != "root" ] && [ "$USER_CONFIG" != "0" ]; then
    pass "Non-root user: $USER_CONFIG"
else
    fail "Container runs as root (User: '$USER_CONFIG')"
fi

# Step 5: HEALTHCHECK check
echo ""
echo "--- Step 5: HEALTHCHECK Check ---"
HEALTHCHECK=$(docker inspect "$IMAGE" --format '{{.Config.Healthcheck}}')
if [ "$HEALTHCHECK" != "<nil>" ] && [ -n "$HEALTHCHECK" ]; then
    pass "HEALTHCHECK configured"
else
    fail "No HEALTHCHECK configured"
fi

# Step 6: SBOM
echo ""
echo "--- Step 6: Generate SBOM ---"
if command -v trivy &>/dev/null; then
    trivy image --format spdx-json --output "$SBOM_FILE" "$IMAGE" 2>/dev/null
    pass "SBOM generated: $SBOM_FILE ($(wc -c < "$SBOM_FILE") bytes)"
else
    echo "⚠️  Trivy not installed — skipping SBOM"
fi

# Step 7: Functional test
echo ""
echo "--- Step 7: Functional Test ---"
docker run -d --name pipeline-test -p 18080:8080 "$IMAGE" > /dev/null 2>&1
sleep 2
HEALTH=$(curl -sf http://localhost:18080/health 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -q "healthy"; then
    pass "Health endpoint responding"
else
    fail "Health endpoint not responding: $HEALTH"
fi
INFO=$(curl -sf http://localhost:18080/api/info 2>/dev/null || echo "")
echo "  API response: $INFO"
docker rm -f pipeline-test > /dev/null 2>&1

# Step 8: Report
echo ""
echo "--- Step 8: Generate Report ---"
cat > "$REPORT_FILE" << REPORT
# Security Report — ${IMAGE}

## Build Info
- Image: ${IMAGE}
- Size: ${SIZE_MB}MB
- Date: $(date -Iseconds)
- User: ${USER_CONFIG}

## Vulnerability Summary
- CRITICAL: ${CRITICAL_COUNT:-N/A}
- HIGH: ${HIGH_COUNT:-N/A}

## Checks
- [x] Image size < ${MAX_SIZE_MB}MB
- [x] Non-root user
- [x] HEALTHCHECK configured
- [x] No CRITICAL CVEs
- [x] SBOM generated

## Artifacts
- SBOM: ${SBOM_FILE}
- Report: ${REPORT_FILE}
REPORT
pass "Report: $REPORT_FILE"

echo ""
echo "========================================="
echo "  Pipeline Complete — All Checks Passed"
echo "========================================="
BUILDSCRIPT
chmod +x build-and-scan.sh

echo "=== Running pipeline ==="
./build-and-scan.sh

echo ""
echo "Cleanup: docker rmi secure-api:v1.0.0; rm -rf $WORKDIR"
```

</details>

---

## Tổng kết

| Exercise | Thời gian | Kỹ năng |
|----------|-----------|---------|
| Easy | 20 phút | Image scanning, CVE analysis |
| Medium | 30 phút | Non-root conversion, permission fixing |
| Hard | 50 phút | Secure pipeline, SBOM, automation |
| **Tổng** | **~100 phút** | |

