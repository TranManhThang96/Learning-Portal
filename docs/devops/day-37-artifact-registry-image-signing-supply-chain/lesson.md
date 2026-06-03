# Day 37: Artifact Registry, Image Signing & Supply Chain Security

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. **Hiểu rõ vai trò của artifact registry** trong CI/CD pipeline — phân biệt được Docker registry, OCI registry, và generic artifact repository.
2. **So sánh được Harbor vs Nexus vs Artifactory vs cloud-native registries** — biết khi nào chọn tool nào theo context team, cost, compliance.
3. **Thiết kế được image tag strategy** phù hợp production: immutable tags, semantic versioning, git SHA — và hiểu vì sao `latest` tag là anti-pattern.
4. **Triển khai được image signing workflow** bằng Cosign — sign, verify, và enforce signature trong admission policy.
5. **Hiểu được SBOM, SLSA, Sigstore** — biết mức độ supply chain security cần áp dụng theo risk level của tổ chức.

---

## 2. Bối cảnh & Động lực

### Supply chain attack là gì?

Trong software, "supply chain" là toàn bộ chuỗi từ source code → build → package → distribute → deploy. Attack vào bất kỳ điểm nào trong chuỗi này đều là supply chain attack.

```
Source Code ──► Build System ──► Artifact Registry ──► Deploy
     │              │                  │                  │
     ▼              ▼                  ▼                  ▼
  Compromised   Inject malware    Tampered image     Run malicious
  dependency    during build      pushed to registry  code in prod
```

### Vì sao topic này quan trọng?

**Thực tế đáng sợ**: Theo Gartner, 45% tổ chức sẽ trải qua software supply chain attack vào 2025. Đây không còn là lý thuyết — đã xảy ra nhiều lần:

- **SolarWinds (2020)**: Build system bị compromise → malicious update gửi đến 18,000 customers bao gồm US government agencies.
- **Codecov (2021)**: Bash uploader script bị inject → credentials từ CI environments bị exfiltrate.
- **ua-parser-js (2021)**: NPM package phổ biến (8M downloads/tuần) bị hijack → crypto miner inject.
- **Log4Shell (2021)**: Vulnerability trong Log4j ảnh hưởng hàng triệu applications vì transitive dependency.

### Nếu làm sai thì sao?

- **Dùng `latest` tag**: Không biết version nào đang chạy → không thể reproduce bug → không thể rollback chính xác.
- **Không sign image**: Ai đó push malicious image vào registry → Kubernetes pull và chạy mà không verify.
- **Registry không bảo mật**: Credential leak → attacker push backdoored image → toàn bộ production compromise.
- **Không có SBOM**: Khi CVE mới ra (như Log4Shell), không biết service nào bị ảnh hưởng → mất hàng ngày scan thay vì vài phút.

### Liên hệ với developer

- **Artifact registry** giống package registry (npm, PyPI, Maven Central) nhưng cho container images và Helm charts.
- **Image signing** giống code signing cho mobile apps (Apple/Google yêu cầu sign trước khi publish).
- **SBOM** giống `package-lock.json` / `go.sum` — manifest liệt kê tất cả dependencies.
- **SLSA** giống audit trail cho build process — chứng minh "image này được build từ source code này, bởi CI system này".

---

## 3. Kiến thức nền tảng

### 3.1 Artifact là gì?

Artifact là bất kỳ output nào từ build process cần được lưu trữ và phân phối:

| Loại Artifact | Ví dụ | Registry |
|--------------|-------|----------|
| Container image | `myapp:v1.2.3` | Docker Hub, Harbor, ECR |
| Helm chart | `myapp-chart-1.2.3.tgz` | ChartMuseum, Harbor, OCI registry |
| OS package | `myapp-1.2.3.deb` | Nexus, Artifactory |
| Binary | `myapp-linux-amd64` | Nexus, Artifactory, S3 |
| Documentation | `api-docs-v1.2.3.zip` | S3, Artifactory |

### 3.2 OCI (Open Container Initiative)

OCI là standard cho container images và distribution:

```
OCI Image Spec:
  ┌─────────────┐
  │   Manifest   │  ← Mô tả layers, config
  ├─────────────┤
  │   Config     │  ← OS, architecture, env vars, entrypoint
  ├─────────────┤
  │   Layer 1    │  ← Base OS files
  │   Layer 2    │  ← Application dependencies
  │   Layer 3    │  ← Application code
  └─────────────┘

OCI Distribution Spec:
  Client ←→ Registry API (push/pull/list/delete)
```

OCI registry không chỉ cho container images — có thể store Helm charts, WASM modules, Cosign signatures, SBOMs.

### 3.3 Image Tag Strategy

| Strategy | Ví dụ | Mutable? | Production? |
|----------|-------|----------|-------------|
| `latest` | `myapp:latest` | ✅ Yes | ❌ Không bao giờ |
| Semantic version | `myapp:v1.2.3` | Nên immutable | ✅ Phù hợp |
| Git SHA | `myapp:a1b2c3d` | ✅ Immutable | ✅ Phù hợp |
| Build number | `myapp:build-456` | ✅ Immutable | ✅ Phù hợp |
| Branch + SHA | `myapp:main-a1b2c3d` | ✅ Immutable | ✅ Cho staging |
| Timestamp | `myapp:20240115-143022` | ✅ Immutable | ⚠️ Khó đọc |

**Best practice**: Dùng kết hợp — `myapp:v1.2.3` (human-readable) + `myapp:abc123d` (unique, traceable to git commit).

### 3.4 Immutable Artifact

```
Mutable tag (NGUY HIỂM):
  Day 1: myapp:v1 → image digest sha256:aaa...
  Day 2: myapp:v1 → image digest sha256:bbb...  ← Image thay đổi, tag giữ nguyên!
  
Immutable tag (AN TOÀN):
  Day 1: myapp:v1.0.0 → image digest sha256:aaa...
  Day 2: Push myapp:v1.0.0 mới → REJECTED bởi registry
  Day 2: Push myapp:v1.0.1 → image digest sha256:bbb...  ← Tag mới, image mới
```

---

## 4. Deep Dive

### 4.1 Registry Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Container Registry                      │
│                                                            │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   API Server     │  │  Auth/AuthZ   │  │  Replication  │ │
│  │                   │  │               │  │  Controller   │ │
│  │  - Push/Pull      │  │  - LDAP/OIDC  │  │               │ │
│  │  - Catalog        │  │  - Robot acct  │  │  - Cross-DC   │ │
│  │  - Tag list       │  │  - RBAC       │  │  - Pull/Push   │ │
│  └────────┬──────────┘  └──────────────┘  └──────────────┘ │
│           │                                                  │
│  ┌────────▼──────────────────────────────────────────────┐  │
│  │              Storage Backend                           │  │
│  │  - Local filesystem                                    │  │
│  │  - S3 / GCS / Azure Blob                              │  │
│  │  - Distributed storage (MinIO, Ceph)                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Additional Features                       │  │
│  │  - Vulnerability scanning (Trivy, Clair)               │  │
│  │  - Image signing verification                          │  │
│  │  - Garbage collection                                  │  │
│  │  - Webhook notifications                               │  │
│  │  - Audit logs                                          │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 So sánh Registry Solutions

| Tiêu chí | Harbor | Nexus | Artifactory | Docker Hub | ECR/GCR/ACR |
|----------|--------|-------|-------------|------------|-------------|
| **Loại** | Container-focused | Multi-format | Multi-format | Container-only | Container-only |
| **Open Source** | ✅ CNCF | ✅ OSS (limited) | ❌ Commercial | ❌ SaaS | ❌ Cloud managed |
| **Self-hosted** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Vuln scanning** | ✅ Built-in (Trivy) | ⚠️ Plugin | ✅ Xray | ❌ Basic | ✅ Built-in |
| **Image signing** | ✅ Cosign/Notary | ❌ | ✅ | ❌ | ⚠️ Basic |
| **Replication** | ✅ Multi-DC | ❌ OSS | ✅ | N/A | N/A |
| **RBAC** | ✅ Project-based | ✅ | ✅ | ⚠️ Org/Team | ✅ IAM |
| **Helm charts** | ✅ | ✅ | ✅ | ❌ | ✅ OCI |
| **Cost** | Free | Free/Pro | $$$ | Free/Pro | Pay-per-use |
| **Best for** | K8s-native teams | Java/multi-lang | Enterprise | Public images | Cloud-native |

### 4.3 Supply Chain Security Stack

```
┌─────────────────────────────────────────────────────┐
│                SLSA Level 3+                         │
│  "Provenance: Who built what, from which source"     │
├─────────────────────────────────────────────────────┤
│                Image Signing (Cosign)                │
│  "This image was signed by trusted entity"           │
├─────────────────────────────────────────────────────┤
│                SBOM (Syft, Trivy)                    │
│  "This image contains these dependencies"            │
├─────────────────────────────────────────────────────┤
│                Vulnerability Scanning (Trivy/Grype)  │
│  "These CVEs exist in this image"                    │
├─────────────────────────────────────────────────────┤
│                Image Registry (Harbor, ECR)           │
│  "Store, distribute, access control"                 │
├─────────────────────────────────────────────────────┤
│                Container Image (OCI)                  │
│  "Packaged application with dependencies"            │
└─────────────────────────────────────────────────────┘
```

### 4.4 Cosign & Sigstore

**Sigstore** là ecosystem mở cho software signing:

```
Sigstore Ecosystem:
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  Cosign   │  │  Fulcio   │  │  Rekor   │
  │           │  │           │  │           │
  │ Sign &    │  │ Certificate│ │ Transparency│
  │ verify    │  │ Authority  │ │ Log        │
  │ artifacts │  │ (keyless)  │ │ (audit)    │
  └──────────┘  └──────────┘  └──────────┘
```

- **Cosign**: CLI tool để sign và verify container images.
- **Fulcio**: Certificate Authority — cấp short-lived cert dựa trên OIDC identity (keyless signing).
- **Rekor**: Transparency log — ghi lại tất cả signing events (tamper-proof audit trail).

**Keyless signing flow**:

```
Developer           Fulcio              Rekor               Registry
    │                  │                  │                    │
    │─ OIDC login ────►│                  │                    │
    │◄─ Short-lived ───│                  │                    │
    │   certificate    │                  │                    │
    │                  │                  │                    │
    │─ Sign image ─────────────────────────────────────────────►│
    │                  │                  │                    │
    │─ Record signature─────────────────►│                    │
    │                  │                  │                    │
    │◄─ Transparency ──────────────────── │                    │
    │   log entry      │                  │                    │
```

### 4.5 SBOM (Software Bill of Materials)

SBOM liệt kê tất cả components trong một software artifact:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "components": [
    {
      "type": "library",
      "name": "express",
      "version": "4.18.2",
      "purl": "pkg:npm/express@4.18.2"
    },
    {
      "type": "library",
      "name": "lodash",
      "version": "4.17.21",
      "purl": "pkg:npm/lodash@4.17.21",
      "vulnerabilities": ["CVE-2021-23337"]
    }
  ]
}
```

### 4.6 SLSA Framework

SLSA (Supply-chain Levels for Software Artifacts) — framework đánh giá mức độ bảo mật supply chain:

| Level | Yêu cầu | Ý nghĩa |
|-------|---------|---------|
| **SLSA 0** | Không có gì | Không có bảo đảm |
| **SLSA 1** | Build process documented | Biết image build từ đâu |
| **SLSA 2** | Hosted build + signed provenance | Build trên CI/CD, có chứng chỉ |
| **SLSA 3** | Hardened build platform | Build platform chống tamper |
| **SLSA 4** | Two-person review + hermetic builds | Highest assurance |

---

## 5. Trade-offs & Best Practices ⭐

### 5.1 Registry Selection

**Startup (< 20 engineers)**:
- Docker Hub (free tier) hoặc cloud-native (ECR/GCR) cho simplicity.
- Scan bằng Trivy trong CI pipeline.
- Tag strategy: `git-sha` + semver.
- Image signing: skip ban đầu, thêm sau khi có compliance requirement.

**Mid-size (20-100 engineers)**:
- Harbor self-hosted hoặc cloud-native registry.
- Built-in vulnerability scanning.
- Image signing với Cosign (key-pair mode).
- SBOM generation cho critical services.
- Immutable tags enforced.

**Enterprise (100+ engineers)**:
- Artifactory hoặc Harbor Enterprise.
- Multi-DC replication.
- Keyless signing với Sigstore/Fulcio.
- SBOM mandatory cho tất cả images.
- SLSA Level 2+ compliance.
- Admission policy: chỉ cho phép signed images.
- Audit log retention ≥ 1 năm.

### 5.2 Tag Strategy Best Practices

**DO**:
- Dùng immutable tags: `v1.2.3`, `abc123d`.
- Gắn git commit SHA vào image label/annotation.
- Dùng image digest (`sha256:...`) trong production manifests.
- Automate tagging trong CI pipeline.

**DON'T**:
- Dùng `latest` tag cho bất kỳ environment nào ngoài local dev.
- Overwrite existing tags (mutable tags).
- Dùng branch name làm tag cho production (`main`, `develop`).
- Tag thủ công — luôn để CI/CD tạo tag.

### 5.3 Anti-patterns

1. **"latest" everywhere**: Không biết version nào đang chạy → rollback impossible.
2. **No garbage collection**: Registry đầy disk → push fail → deployment fail.
3. **Shared credentials**: Tất cả dev dùng chung 1 robot account → không audit được ai push gì.
4. **Skip scanning**: CVE critical trong base image không được phát hiện → production vulnerable.
5. **Sign but don't verify**: Sign image nhưng admission controller không enforce → signing vô nghĩa.
6. **Massive images**: 2GB image → pull chậm → deployment slow → canary analysis timeout.

---

## 6. Performance & Scalability ⭐

### 6.1 Image Pull Performance

| Yếu tố | Impact | Optimization |
|--------|--------|-------------|
| **Image size** | 2GB image = 30-60s pull | Multi-stage build, distroless base |
| **Registry location** | Cross-region pull = high latency | Registry replication hoặc cache proxy |
| **Layer caching** | Shared layers = fast pull | Order Dockerfile instructions properly |
| **Concurrent pulls** | Node có 20 pods pulling = bandwidth saturation | Pre-pull images, image pull policy |
| **Registry throughput** | 100 nodes pulling đồng thời | CDN, multiple replicas, object store backend |

### 6.2 Registry Scaling

- **Storage**: Dùng object storage (S3/GCS/MinIO) thay vì local disk → scale unlimited.
- **API**: Multiple registry replicas behind load balancer.
- **Garbage collection**: Schedule GC off-peak → tránh lock conflict.
- **Replication**: Cross-DC replication cho multi-region clusters → pods pull từ nearest registry.

### 6.3 Bottleneck thường gặp

- **Garbage collection lock**: GC lock registry → push/pull fail → CI/CD pipeline fail.
- **Layer deduplication**: Registry không deduplicate → storage cost tăng nhanh.
- **Rate limiting**: Docker Hub free tier = 100 pulls/6h per IP → shared office/CI bị block.

---

## 7. Security & Reliability Considerations

### 7.1 Security

- **Authentication**: OIDC/LDAP integration, không dùng basic auth.
- **Authorization**: Project-based RBAC — dev chỉ push/pull project của mình.
- **Robot accounts**: CI/CD dùng robot account với quyền tối thiểu (push-only hoặc pull-only).
- **Network**: Registry behind VPN/private network, chỉ expose qua internal load balancer.
- **Encryption**: TLS cho API, encryption at rest cho storage.
- **Audit**: Log mọi push/pull/delete operation.
- **Vulnerability scanning**: Scan on push, block pull nếu có CVE critical.

### 7.2 Reliability

- **High availability**: Multiple replicas + shared storage backend.
- **Backup**: Backup registry database + blob storage.
- **DR**: Cross-DC replication — nếu registry primary down, failover sang secondary.
- **Monitoring**: Alert khi storage > 80%, GC fail, replication lag > threshold.

---

## 8. Hands-on Example

### 8.1 Setup local registry

```bash
# Tạo workspace tạm
mkdir -p /tmp/supply-chain-lab && cd /tmp/supply-chain-lab

# Tạo local registry bằng Docker
docker run -d \
  --name registry \
  -p 5000:5000 \
  --restart=always \
  registry:2

# Verify
curl http://localhost:5000/v2/_catalog
# Expected: {"repositories":[]}
```

### 8.2 Tạo sample app

**File: `package.json`**

```json
{
  "name": "supply-chain-lab",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {},
  "devDependencies": {
    "@types/node": "20.11.30",
    "typescript": "5.4.5"
  }
}
```

**File: `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```

**File: `src/index.ts`**

```ts
import * as http from "node:http";

const port = Number(process.env.PORT ?? "3000");

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify({
    service: "supply-chain-lab",
    version: process.env.APP_VERSION ?? "dev"
  }));
});

server.listen(port, "0.0.0.0", () => {
  console.log(`supply-chain-lab listening on ${port}`);
});
```

```bash
mkdir -p src
npm install
```

### 8.3 Build với immutable tag strategy

**File: `Dockerfile`**

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM deps AS builder
COPY tsconfig.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM node:20-alpine
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D appuser
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -q --spider http://localhost:3000/health || exit 1
CMD ["node", "dist/index.js"]
```

```bash
# Build với immutable tags
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || date +%s)
VERSION="1.0.0"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker build \
  --label "org.opencontainers.image.revision=${GIT_SHA}" \
  --label "org.opencontainers.image.version=${VERSION}" \
  --label "org.opencontainers.image.created=${BUILD_DATE}" \
  -t localhost:5000/myapp:v${VERSION} \
  -t localhost:5000/myapp:${GIT_SHA} \
  .

# Push cả 2 tags
docker push localhost:5000/myapp:v${VERSION}
docker push localhost:5000/myapp:${GIT_SHA}

# Verify
curl http://localhost:5000/v2/myapp/tags/list
# Expected: {"name":"myapp","tags":["v1.0.0","abc123d"]}

# Lấy digest (immutable identifier)
docker inspect --format='{{index .RepoDigests 0}}' localhost:5000/myapp:v${VERSION}
# Expected: localhost:5000/myapp@sha256:abc123...

# Smoke test image vừa build
docker run --rm -d --name myapp-test -p 3000:3000 localhost:5000/myapp:v${VERSION}
curl -s http://localhost:3000/health
# Expected: {"status":"ok"}
docker rm -f myapp-test
```

### 8.4 Vulnerability scanning với Trivy

```bash
# Cài Trivy
# macOS: brew install trivy
# Linux: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh

# Scan image
trivy image localhost:5000/myapp:v1.0.0

# Scan với severity filter
trivy image --severity HIGH,CRITICAL localhost:5000/myapp:v1.0.0

# Scan và output JSON (cho CI/CD)
trivy image --format json --output scan-result.json localhost:5000/myapp:v1.0.0

# Exit code khác 0 nếu có CRITICAL CVE (dùng trong CI pipeline)
trivy image --exit-code 1 --severity CRITICAL localhost:5000/myapp:v1.0.0

# Expected output:
# localhost:5000/myapp:v1.0.0 (alpine 3.18.4)
# ============================================
# Total: 0 (HIGH: 0, CRITICAL: 0)
```

### 8.5 SBOM generation

```bash
# Generate SBOM với Trivy (CycloneDX format)
trivy image --format cyclonedx --output sbom.json localhost:5000/myapp:v1.0.0

# Generate SBOM với Syft
# Cài: curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh
syft localhost:5000/myapp:v1.0.0 -o cyclonedx-json > sbom-syft.json

# Xem SBOM
cat sbom.json | jq '.components | length'
# Expected: số lượng dependencies

cat sbom.json | jq '.components[] | {name, version}'
# Expected: list tất cả packages với version
```

### 8.6 Image signing với Cosign

```bash
# Cài Cosign
# macOS: brew install cosign
# Linux: 
# curl -LO https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
# chmod +x cosign-linux-amd64 && sudo mv cosign-linux-amd64 /usr/local/bin/cosign

# Generate key pair
cosign generate-key-pair
# Tạo cosign.key (private) và cosign.pub (public)
# ⚠️ KHÔNG commit private key vào git!

# Sign image
cosign sign --key cosign.key --allow-insecure-registry localhost:5000/myapp:v1.0.0
# Nhập password cho key

# Verify signature
cosign verify --key cosign.pub --allow-insecure-registry localhost:5000/myapp:v1.0.0

# Expected output:
# Verification for localhost:5000/myapp:v1.0.0 --
# The following checks were performed on each of these signatures:
#   - The cosign claims were validated
#   - The signatures were verified against the specified public key

# Attach SBOM vào image
cosign attach sbom --sbom sbom.json --allow-insecure-registry localhost:5000/myapp:v1.0.0

# Verify SBOM attachment bằng cách download lại SBOM artifact
cosign download sbom --allow-insecure-registry localhost:5000/myapp:v1.0.0 | jq '.components | length'
# Expected: số lượng components > 0
```

### 8.7 CI/CD pipeline integration

```yaml
# .github/workflows/build-sign-push.yaml
name: Build, Scan, Sign, Push

on:
  push:
    branches: [main]
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write  # Cho keyless signing

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern=v{{version}}
            type=sha,prefix=

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Scan image
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Sign image (keyless)
        run: |
          cosign sign --yes \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${{ github.sha }}
```

### 8.8 Cleanup

```bash
# Stop local registry
docker stop registry && docker rm registry

# Remove images
docker rmi localhost:5000/myapp:v1.0.0
docker rmi localhost:5000/myapp:${GIT_SHA}

# Remove cosign keys
rm -f cosign.key cosign.pub

# Remove scan results
rm -f scan-result.json sbom.json sbom-syft.json

# Remove workspace nếu không cần giữ lại
cd /tmp && rm -rf /tmp/supply-chain-lab
```

### 8.9 Verify checklist

- [ ] Local registry chạy thành công
- [ ] Sample app build được từ source trong `/tmp/supply-chain-lab`
- [ ] Image build với immutable tag (semver + git SHA)
- [ ] OCI labels gắn đúng (revision, version, created)
- [ ] Smoke test `/health` trả `{"status":"ok"}`
- [ ] Trivy scan chạy và output kết quả
- [ ] SBOM generate thành công
- [ ] Image signed bằng Cosign
- [ ] Signature verified bằng cosign.pub

---

## 9. Common Pitfalls & Debugging

### 9.1 Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| `denied: requested access to the resource is denied` | Chưa login hoặc không có quyền push | `docker login`, check RBAC |
| `manifest unknown` | Image tag không tồn tại | Check tag name, verify push thành công |
| `error pulling image: registry is not reachable` | Network issue hoặc TLS error | Check DNS, add insecure registry nếu self-signed cert |
| `cosign: error signing: no matching signatures` | Key pair sai hoặc image đã bị thay đổi | Re-sign hoặc verify đúng key |
| `SBOM generation: no packages found` | Distroless image hoặc tool không recognize format | Dùng Syft thay Trivy, hoặc scan build stage |
| `registry storage full` | Không có garbage collection | Enable GC, tăng storage, delete old images |

### 9.2 Debug commands

```bash
# Check registry catalog
curl -s http://localhost:5000/v2/_catalog | jq

# List tags cho specific image
curl -s http://localhost:5000/v2/myapp/tags/list | jq

# Get image manifest
curl -s http://localhost:5000/v2/myapp/manifests/v1.0.0 \
  -H "Accept: application/vnd.oci.image.manifest.v1+json" | jq

# Check image layers
docker manifest inspect localhost:5000/myapp:v1.0.0

# Verify cosign signature
cosign verify --key cosign.pub --allow-insecure-registry localhost:5000/myapp:v1.0.0 2>&1

# Check trivy DB update
trivy image --download-db-only
```

### 9.3 Production Case Study: SolarWinds Supply Chain Attack

**Context**: SolarWinds — công ty IT management phục vụ 300,000+ customers, bao gồm US government, Fortune 500.

**Symptom**: Tháng 12/2020, FireEye phát hiện malware "SUNBURST" trong update của SolarWinds Orion platform. Malware tồn tại trong bản update chính thức ít nhất từ tháng 3/2020.

**Investigation**:
- Attackers (nhóm APT29/Cozy Bear) đã compromise SolarWinds build system.
- Malicious code được inject vào source code trong quá trình build — không phải trong source repository.
- Signed update (legitimate certificate) được distribute → bypass tất cả security checks.
- 18,000 customers cài update bị compromise.

**Root Cause**: Build system không được hardened. Không có integrity verification giữa source code và build output. Signing key used automatically without additional verification.

**Impact**: 
- US Treasury, Commerce Department, Homeland Security bị breach.
- Estimated cost: billions of dollars.
- Trust in software update ecosystem bị tổn thương nghiêm trọng.

**Long-term Fix (cho industry)**:
1. **SLSA framework** ra đời — yêu cầu provenance verification.
2. **Sigstore/Cosign** phát triển mạnh — transparent, verifiable signing.
3. **Executive Order 14028** (US) — yêu cầu SBOM cho software sold to government.
4. **Build system hardening**: hermetic builds, two-person review, build log retention.

**Lesson Learned**: Signing alone is not enough. Cần verify toàn bộ supply chain: source → build → artifact → distribution. SLSA framework giúp đánh giá và cải thiện từng level.

---

## 10. Kết nối với bài trước & bài sau

### Bài trước (Day 36)
- Day 36 học progressive delivery với Argo Rollouts — deploy image theo canary strategy.
- Day 37 bổ sung: image đó phải được **sign, scan, verified** trước khi progressive delivery sử dụng.
- Pipeline hoàn chỉnh: Build → Scan → Sign → Push → Progressive Deploy.

### Bài sau (Day 38)
- Day 38 bắt đầu Phase 6: Observability — Metrics, Logs, Traces.
- Liên quan: registry metrics (pull rate, push rate, storage usage) cũng cần monitoring.
- Image labels/annotations chứa version info → dùng trong observability (biết service nào chạy version nào).

### Day 37 cũng là CI/CD checkpoint
- Kết thúc Phase 5: CI/CD & Release Engineering.
- Review lại: Day 32 (CI/CD patterns) → Day 33 (GitHub Actions) → Day 34 (CI tool comparison) → Day 35 (deployment strategies) → Day 36 (progressive delivery) → Day 37 (supply chain security).
- Full pipeline: Code → CI (lint/test/build/scan) → Artifact (registry/sign/SBOM) → CD (progressive delivery).

### Kiến thức liên quan
- **Day 9**: Container Image Optimization & Security — base image, non-root, Trivy scan.
- **Day 14**: Secret management — registry credentials cũng là secrets.
- **Day 20**: RBAC — registry access control tương tự concept.
- **Day 21**: Admission Controller — dùng Kyverno/OPA enforce image signature verification.

---

## 11. Tài liệu tham khảo

### Must-read
- [Sigstore Documentation](https://docs.sigstore.dev/)
- [Cosign - Signing and Verifying Container Images](https://github.com/sigstore/cosign)
- [SLSA Framework](https://slsa.dev/)
- [Trivy - Comprehensive Security Scanner](https://aquasecurity.github.io/trivy/)

### Nice-to-have
- [Harbor - Cloud Native Registry](https://goharbor.io/docs/)
- [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec)
- [SBOM Everywhere - CNCF](https://www.cncf.io/blog/2022/06/27/software-bill-of-materials-sbom/)

### Deep-dive
- [SolarWinds Attack - Detailed Analysis](https://www.mandiant.com/resources/blog/evasive-attacker-leverages-solarwinds-supply-chain-compromises-with-sunburst-backdoor)
- [Supply Chain Security at Google (SLSA)](https://security.googleblog.com/2021/06/introducing-slsa-end-to-end-framework.html)
- [Netflix Container Security](https://netflixtechblog.com/keeping-netflix-secure-at-scale-48e681a68a96)
- [Kubernetes Image Policy Webhook](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#imagepolicywebhook)

