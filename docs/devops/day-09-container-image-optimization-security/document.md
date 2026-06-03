# Day 9: Document — Container Image Security Reference

## 1. Base Image Comparison Matrix

| Base Image | Size | CVEs (typical) | Shell | Pkg Mgr | glibc | Debug | Best for |
|-----------|------|----------------|-------|---------|-------|-------|----------|
| `scratch` | 0MB | 0 | ❌ | ❌ | ❌ | ❌ | Go/Rust static binary |
| `gcr.io/distroless/static` | ~2MB | 0-2 | ❌ | ❌ | ❌ | ❌ | Go/Rust static binary + CA certs |
| `gcr.io/distroless/base` | ~20MB | 2-5 | ❌ | ❌ | ✅ | ❌ | C/C++, dynamic linking |
| `gcr.io/distroless/java21` | ~230MB | 5-10 | ❌ | ❌ | ✅ | ❌ | Java applications |
| `gcr.io/distroless/nodejs20` | ~130MB | 3-8 | ❌ | ❌ | ✅ | ❌ | Node.js (no npm) |
| `alpine:3.19` | ~7MB | 0-5 | ✅ ash | ✅ apk | ❌ musl | ⚠️ | Size-sensitive, general |
| `debian:bookworm-slim` | ~80MB | 10-30 | ✅ bash | ✅ apt | ✅ | ✅ | General purpose |
| `ubuntu:22.04` | ~77MB | 10-40 | ✅ bash | ✅ apt | ✅ | ✅ | Development, legacy |
| `chainguard/static` | ~2MB | 0 | ❌ | ❌ | ❌ | ❌ | Hardened alternative to distroless |
| `chainguard/node` | ~100MB | 0-2 | ❌ | ❌ | ✅ | ❌ | Hardened Node.js |

---

## 2. Trivy Command Reference

### Basic Scanning

```bash
# Scan image
trivy image IMAGE_NAME

# Scan with severity filter
trivy image --severity CRITICAL,HIGH IMAGE_NAME

# Scan and fail on findings (for CI)
trivy image --exit-code 1 --severity CRITICAL IMAGE_NAME

# Quiet mode (less output)
trivy image --quiet IMAGE_NAME

# Skip specific checks
trivy image --skip-dirs /usr/local/lib IMAGE_NAME
```

### Output Formats

```bash
# Table (default)
trivy image IMAGE_NAME

# JSON
trivy image --format json --output report.json IMAGE_NAME

# SARIF (for GitHub Security tab)
trivy image --format sarif --output report.sarif IMAGE_NAME

# Template (custom format)
trivy image --format template --template "@html.tpl" --output report.html IMAGE_NAME

# SBOM (SPDX)
trivy image --format spdx-json --output sbom.json IMAGE_NAME

# SBOM (CycloneDX)
trivy image --format cyclonedx --output sbom-cdx.json IMAGE_NAME
```

### Scan Types

```bash
# Image scan (default)
trivy image nginx:latest

# Filesystem scan (source code dependencies)
trivy fs /path/to/project

# Repository scan
trivy repo https://github.com/org/repo

# Dockerfile misconfiguration
trivy config Dockerfile

# Kubernetes manifests
trivy config --policy-bundle-repository ghcr.io/aquas k8s-manifests/

# Running container (rootfs)
trivy rootfs /
```

### Ignore / Exception Management

```bash
# .trivyignore file
cat > .trivyignore << 'EOF'
# Format: CVE-ID
CVE-2024-12345
CVE-2024-67890

# With expiry date
CVE-2024-11111 exp:2024-12-31
EOF

# Use ignore file
trivy image --ignorefile .trivyignore IMAGE_NAME

# Ignore unfixed vulnerabilities
trivy image --ignore-unfixed IMAGE_NAME
```

### Database Management

```bash
# Update vulnerability database
trivy image --download-db-only

# Skip DB update (use cached)
trivy image --skip-db-update IMAGE_NAME

# Clear cache
trivy clean --all
```

---

## 3. Dockerfile Security Checklist

### Build Time

- [ ] **Base image**: dùng specific tag, không dùng `:latest`
- [ ] **Image pinning**: pin by digest cho production critical images
- [ ] **Multi-stage build**: tách build dependencies khỏi runtime
- [ ] **No secrets**: không COPY `.env`, credentials, keys vào image
- [ ] **No secret ARGs**: không dùng `ARG PASSWORD=xxx` (hiển thị trong history)
- [ ] **Docker secrets**: dùng `--mount=type=secret` nếu cần secret lúc build
- [ ] **.dockerignore**: loại bỏ `.git/`, `.env`, `node_modules/`, test files
- [ ] **Minimal packages**: `--no-install-recommends`, xóa cache sau install
- [ ] **Verified sources**: chỉ install từ official repositories

### Runtime Security

- [ ] **Non-root user**: `USER appuser` hoặc `USER 65534`
- [ ] **Read-only FS**: compatible với `--read-only` runtime flag
- [ ] **No privileged**: không cần `--privileged` để chạy
- [ ] **Drop capabilities**: `--cap-drop=ALL`, chỉ add cái cần
- [ ] **No new privileges**: `--security-opt=no-new-privileges`
- [ ] **HEALTHCHECK**: có health check instruction
- [ ] **EXPOSE**: document ports rõ ràng
- [ ] **Labels**: có version, maintainer, description labels

### Supply Chain

- [ ] **Image scanning**: Trivy/Grype scan trong CI
- [ ] **SBOM generation**: SPDX hoặc CycloneDX cho mỗi release
- [ ] **Image signing**: Cosign sign mỗi production image
- [ ] **Registry access**: private registry, restricted push access
- [ ] **Provenance**: SLSA provenance attestation (nếu applicable)

---

## 4. CVE Severity Guide

### Severity Levels

| Severity | CVSS Score | Response Time | Action |
|----------|-----------|---------------|--------|
| **CRITICAL** | 9.0-10.0 | < 24h | Patch immediately, rebuild, deploy |
| **HIGH** | 7.0-8.9 | < 1 week | Patch in current sprint |
| **MEDIUM** | 4.0-6.9 | < 1 month | Batch update |
| **LOW** | 0.1-3.9 | Next release | Update when convenient |
| **UNKNOWN** | N/A | 48h | Research and reclassify |

### Response Decision Matrix

```
CVE found → Is it in our image? 
├── No → Ignore (false positive)
└── Yes → Is the vulnerable function used?
    ├── No → Document exception, add to .trivyignore
    └── Yes → Is there a fix available?
        ├── Yes → Patch and rebuild
        │   ├── CRITICAL → Deploy within 24h
        │   ├── HIGH → Deploy within 1 week
        │   └── MEDIUM/LOW → Next scheduled release
        └── No → Mitigation available?
            ├── Yes → Apply mitigation (config change, WAF rule)
            └── No → Accept risk with documentation + monitoring
```

### Exception Documentation Template

```markdown
## CVE Exception: CVE-YYYY-XXXXX

- **Severity**: HIGH (CVSS 7.5)
- **Package**: libfoo 1.2.3
- **Exception date**: 2024-01-15
- **Approved by**: Security Team Lead
- **Review date**: 2024-02-15

### Justification
The vulnerable function `foo_parse()` is not called by our application.
Our usage is limited to `foo_init()` and `foo_close()` which are not affected.

### Mitigation
- Network access to the service is restricted by NetworkPolicy
- Input validation performed at API gateway level
- Monitoring alert configured for anomalous behavior

### Expiry
This exception expires on 2024-03-15 or when a patched version is available.
```

---

## 5. Non-root Dockerfile Patterns by Language

### Go

```dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server

FROM scratch
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /server /server
USER 65534:65534
ENTRYPOINT ["/server"]
```

### Node.js

```dockerfile
FROM node:20-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --chown=app:app package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --chown=app:app . .
USER app
CMD ["node", "app.js"]
```

### Python

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN groupadd -r app && useradd -r -g app -s /sbin/nologin app
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
USER app
CMD ["python", "app.py"]
```

### Java (Spring Boot)

```dockerfile
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY . .
RUN ./mvnw package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder --chown=app:app /app/target/*.jar app.jar
USER app
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
```

### Rust

```dockerfile
FROM rust:1.75-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --target x86_64-unknown-linux-musl

FROM scratch
COPY --from=builder /app/target/x86_64-unknown-linux-musl/release/myapp /myapp
USER 65534:65534
ENTRYPOINT ["/myapp"]
```

---

## 6. Image Signing Quick Reference (Cosign)

```bash
# === Setup ===
# Install
go install github.com/sigstore/cosign/v2/cmd/cosign@latest
# Or: brew install cosign

# === Key-based Signing ===
# Generate key pair
cosign generate-key-pair
# → cosign.key (private), cosign.pub (public)

# Sign
cosign sign --key cosign.key registry.com/myapp:v1.0.0

# Verify
cosign verify --key cosign.pub registry.com/myapp:v1.0.0

# === Keyless Signing (recommended) ===
# Sign (authenticates via OIDC — GitHub, Google, Microsoft)
cosign sign registry.com/myapp:v1.0.0

# Verify
cosign verify \
  --certificate-identity=user@example.com \
  --certificate-oidc-issuer=https://accounts.google.com \
  registry.com/myapp:v1.0.0

# === Attach SBOM ===
cosign attach sbom --sbom sbom.json registry.com/myapp:v1.0.0

# === CI/CD Integration (GitHub Actions) ===
# See: https://docs.sigstore.dev/signing/quickstart/
```

---

## 7. CI/CD Security Pipeline Template

### GitHub Actions

```yaml
name: Secure Build Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-scan-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Trivy Scan (CRITICAL)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          format: sarif
          output: trivy-results.sarif
          severity: CRITICAL,HIGH
          exit-code: 1

      - name: Upload Trivy SARIF
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy-results.sarif

      - name: Generate SBOM
        run: trivy image --format spdx-json --output sbom.json myapp:${{ github.sha }}

      - name: Non-root Check
        run: |
          USER=$(docker inspect myapp:${{ github.sha }} --format '{{.Config.User}}')
          if [ -z "$USER" ] || [ "$USER" = "root" ] || [ "$USER" = "0" ]; then
            echo "ERROR: Image runs as root"
            exit 1
          fi

      - name: Push to Registry
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag myapp:${{ github.sha }} registry.com/myapp:${{ github.sha }}
          docker push registry.com/myapp:${{ github.sha }}

      - name: Sign Image
        if: github.ref == 'refs/heads/main'
        run: cosign sign registry.com/myapp:${{ github.sha }}
```

---

## 8. Common Non-root Permission Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `EACCES: permission denied, open '/app/data'` | Directory owned by root | `COPY --chown=user:group` hoặc `RUN chown` |
| `EACCES: permission denied, mkdir '/app/tmp'` | Cannot create directory | `RUN mkdir -p /app/tmp && chown user:group /app/tmp` |
| `Error: listen EACCES 0.0.0.0:80` | Non-root cannot bind port < 1024 | Dùng port > 1024 (8080, 3000) |
| `npm ERR! EACCES` | npm cache dir owned by root | `ENV npm_config_cache=/tmp/npm-cache` |
| `pip: Permission denied` | pip install vào system dir | `--user` flag hoặc virtualenv |
| `cannot write PID file` | PID file dir read-only | `RUN mkdir /app/run && chown user:group /app/run` |

