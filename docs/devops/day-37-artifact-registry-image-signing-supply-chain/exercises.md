# Day 37: Exercises — Artifact Registry, Image Signing & Supply Chain

## Bài 1: Image Tag Strategy & Local Registry (Easy)

### Context
Bạn join team DevOps tại một startup SaaS. Team đang dùng `latest` tag cho mọi thứ — cả staging và production. Tuần trước, một developer push image mới với tag `latest`, staging tự pull về nhưng production vẫn dùng cached `latest` cũ → 2 environments chạy khác version mà không ai biết.

### Yêu cầu
1. Setup local Docker registry.
2. Build một sample app (dùng `nginx:alpine` hoặc app đơn giản) với immutable tag strategy:
   - Tag 1: Semantic version `v1.0.0`
   - Tag 2: Git commit SHA (short)
   - Tag 3: Cả 2 kết hợp: `v1.0.0-abc123d`
3. Push tất cả tags lên local registry.
4. Thêm OCI labels: `org.opencontainers.image.revision`, `org.opencontainers.image.version`, `org.opencontainers.image.created`.
5. Verify tags và labels bằng `docker inspect` hoặc `curl` API.

### Expected Outcome
- Local registry chạy ở `localhost:5000`.
- Image có 3 tags khác nhau, tất cả trỏ đến cùng digest.
- OCI labels chứa đúng git SHA, version, build date.

### Hint
- `docker run -d -p 5000:5000 --name registry registry:2`
- `docker build --label "org.opencontainers.image.revision=$(git rev-parse --short HEAD)" ...`
- `curl http://localhost:5000/v2/_catalog`
- Dùng `docker inspect --format='&#123;&#123;json .Config.Labels&#125;&#125;'` để xem labels.

### Acceptance Criteria
- [ ] Local registry chạy thành công.
- [ ] Image có ≥ 3 immutable tags.
- [ ] OCI labels chứa revision, version, created.
- [ ] `curl` API confirm tất cả tags tồn tại.
- [ ] Không dùng tag `latest`.

### Bonus Challenge
- Viết script tự động tạo tags từ git info.
- Enable immutable tags trên registry (reject push nếu tag đã tồn tại).

---

## Bài 2: Vulnerability Scanning & SBOM Pipeline (Medium)

### Context
Team bạn vừa bị security audit. Auditor hỏi: "Service X chạy production dùng image nào? Image đó có CVE nào không? Dependencies của nó là gì?" Không ai trả lời được. Auditor yêu cầu: mọi image production phải có vulnerability scan report và SBOM.

### Yêu cầu
1. Chọn một image phổ biến (ví dụ: `node:18`, `python:3.11`, hoặc image của project thật).
2. Scan vulnerability bằng Trivy:
   - Output table format (human-readable).
   - Output JSON format (machine-readable, cho CI/CD).
   - Filter chỉ HIGH và CRITICAL.
   - Cấu hình exit code ≠ 0 nếu có CRITICAL CVE.
3. Generate SBOM:
   - Dùng Trivy hoặc Syft.
   - Format: CycloneDX JSON.
   - Đếm số lượng dependencies.
   - Tìm xem có dependency nào có known CVE không.
4. Viết CI pipeline snippet (GitHub Actions hoặc GitLab CI):
   - Build image → Scan → Generate SBOM → Fail nếu CRITICAL CVE.
5. Tạo "vulnerability response checklist" — khi CVE mới được công bố, team làm gì?

### Expected Outcome
- Scan report hiển thị CVEs với severity levels.
- SBOM file chứa đầy đủ dependencies.
- CI pipeline snippet hoạt động logic đúng.
- Checklist có bước cụ thể.

### Hint
- `trivy image --format json --output report.json <image>`
- `trivy image --severity HIGH,CRITICAL --exit-code 1 <image>`
- `syft <image> -o cyclonedx-json > sbom.json`
- `cat sbom.json | jq '.components | length'`
- So sánh: `node:18` (nhiều CVE) vs `node:18-alpine` (ít hơn) vs `gcr.io/distroless/nodejs18-debian12` (ít nhất).

### Acceptance Criteria
- [ ] Trivy scan chạy thành công, output cả table và JSON.
- [ ] Scan filter đúng severity (HIGH + CRITICAL).
- [ ] SBOM generated ở CycloneDX format.
- [ ] SBOM chứa ≥ 10 dependencies (tuỳ image).
- [ ] CI pipeline snippet có step: build → scan → sbom → gate.
- [ ] Vulnerability response checklist có ≥ 5 bước.

### Bonus Challenge
- So sánh SBOM của cùng app trên 3 base images khác nhau (alpine, debian, distroless).
- Integrate Trivy scan result vào GitHub Security tab (SARIF format).
- Tìm CVE cụ thể trong SBOM bằng `jq` query.

---

## Bài 3: End-to-End Supply Chain Security (Hard)

### Context
Bạn là Security-focused DevOps Engineer tại một fintech platform xử lý payment (PCI-DSS compliance). Sau incident SolarWinds-like ở vendor đối tác, CISO yêu cầu:
- Mọi container image phải được signed trước khi deploy.
- Kubernetes cluster phải reject unsigned images.
- Mọi image phải có SBOM attached.
- CI/CD pipeline phải đạt SLSA Level 2.

### Yêu cầu

**Part A: Image Signing Workflow**
1. Generate Cosign key pair.
2. Build và push sample image lên local registry.
3. Sign image bằng Cosign.
4. Verify signature.
5. Thử verify image chưa được sign → phải fail.

**Part B: Kubernetes Admission Policy**
6. Cài Kyverno hoặc OPA/Gatekeeper trên local cluster.
7. Viết policy: reject pods dùng unsigned images.
8. Test: deploy pod với signed image → pass.
9. Test: deploy pod với unsigned image → rejected.

**Part C: SBOM Attachment**
10. Generate SBOM cho image.
11. Attach SBOM vào image bằng Cosign.
12. Verify SBOM attachment.

**Part D: SLSA Level 2 Assessment**
13. Viết document đánh giá CI/CD pipeline hiện tại theo SLSA framework.
14. Xác định gap cần close để đạt SLSA Level 2.
15. Đề xuất actionable improvements.

### Expected Outcome
- Image signing workflow hoàn chỉnh: build → sign → verify.
- Kubernetes cluster reject unsigned images.
- SBOM attached vào image metadata.
- SLSA assessment document với gaps và recommendations.

### Hint
- `cosign generate-key-pair`
- `cosign sign --key cosign.key <image>`
- `cosign verify --key cosign.pub <image>`
- Kyverno policy:
  ```yaml
  apiVersion: kyverno.io/v1
  kind: ClusterPolicy
  metadata:
    name: verify-image-signature
  spec:
    validationFailureAction: Enforce
    rules:
      - name: verify-cosign-signature
        match:
          any:
            - resources:
                kinds:
                  - Pod
        verifyImages:
          - imageReferences:
              - "localhost:5000/*"
            attestors:
              - entries:
                  - keys:
                      publicKeys: |-
                        <cosign.pub content>
  ```
- `cosign attach sbom --sbom sbom.json <image>`

### Acceptance Criteria
- [ ] Cosign key pair generated.
- [ ] Image signed và verify thành công.
- [ ] Unsigned image verify → fail.
- [ ] Kyverno/OPA policy deployed.
- [ ] Signed image pod → admitted.
- [ ] Unsigned image pod → rejected bởi admission controller.
- [ ] SBOM attached và verifiable.
- [ ] SLSA assessment có ≥ 3 gaps identified.
- [ ] Mỗi gap có actionable recommendation.
- [ ] Cleanup script xoá tất cả resources.

### Bonus Challenge
- Implement keyless signing với Fulcio (OIDC-based) thay vì key pair.
- Thêm Rekor transparency log verification.
- Tạo GitHub Actions workflow hoàn chỉnh: build → scan → sbom → sign → push → deploy (notify nếu fail).
- Viết compliance matrix mapping: SLSA requirements ↔ team's current state ↔ remediation plan.

---

## Solutions

<details>
<summary>Solution Bài 1: Image Tag Strategy</summary>

```bash
#!/bin/bash
set -euo pipefail

# 1. Setup local registry
docker run -d --name registry -p 5000:5000 --restart=always registry:2

# 2. Create sample app
mkdir -p /tmp/tag-demo && cd /tmp/tag-demo
cat > Dockerfile <<'EOF'
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost/ || exit 1
EOF

echo "<h1>Tag Demo App</h1>" > index.html
git init && git add . && git commit -m "initial"

# 3. Build with immutable tags
GIT_SHA=$(git rev-parse --short HEAD)
VERSION="1.0.0"
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

docker build \
  --label "org.opencontainers.image.revision=${GIT_SHA}" \
  --label "org.opencontainers.image.version=${VERSION}" \
  --label "org.opencontainers.image.created=${BUILD_DATE}" \
  --label "org.opencontainers.image.source=https://github.com/example/tag-demo" \
  -t localhost:5000/tag-demo:v${VERSION} \
  -t localhost:5000/tag-demo:${GIT_SHA} \
  -t localhost:5000/tag-demo:v${VERSION}-${GIT_SHA} \
  .

# 4. Push all tags
docker push localhost:5000/tag-demo:v${VERSION}
docker push localhost:5000/tag-demo:${GIT_SHA}
docker push localhost:5000/tag-demo:v${VERSION}-${GIT_SHA}

# 5. Verify
echo "=== Tags ==="
curl -s http://localhost:5000/v2/tag-demo/tags/list | jq

echo "=== Labels ==="
docker inspect --format='{{json .Config.Labels}}' localhost:5000/tag-demo:v${VERSION} | jq

echo "=== Digest ==="
docker inspect --format='{{index .RepoDigests 0}}' localhost:5000/tag-demo:v${VERSION}

# Cleanup
docker stop registry && docker rm registry
docker rmi localhost:5000/tag-demo:v${VERSION}
docker rmi localhost:5000/tag-demo:${GIT_SHA}
docker rmi localhost:5000/tag-demo:v${VERSION}-${GIT_SHA}
rm -rf /tmp/tag-demo
```

</details>

<details>
<summary>Solution Bài 2: Vulnerability Scanning & SBOM</summary>

```bash
#!/bin/bash
set -euo pipefail

IMAGE="node:18"

# 1. Scan - Table format
echo "=== Vulnerability Scan (Table) ==="
trivy image --severity HIGH,CRITICAL ${IMAGE}

# 2. Scan - JSON format
echo "=== Vulnerability Scan (JSON) ==="
trivy image --format json --output scan-report.json ${IMAGE}
echo "Total vulnerabilities:"
cat scan-report.json | jq '[.Results[].Vulnerabilities[]?] | length'
echo "CRITICAL:"
cat scan-report.json | jq '[.Results[].Vulnerabilities[]? | select(.Severity=="CRITICAL")] | length'

# 3. CI gate - exit code
echo "=== CI Gate Check ==="
if trivy image --severity CRITICAL --exit-code 1 ${IMAGE} 2>/dev/null; then
  echo "PASS: No CRITICAL CVEs"
else
  echo "FAIL: CRITICAL CVEs found - build should fail"
fi

# 4. Generate SBOM
echo "=== SBOM Generation ==="
trivy image --format cyclonedx --output sbom.json ${IMAGE}
echo "Total dependencies:"
cat sbom.json | jq '.components | length'
echo "Top 10 dependencies:"
cat sbom.json | jq -r '.components[:10][] | "\(.name):\(.version)"'

# 5. Compare base images
echo "=== Base Image Comparison ==="
for img in "node:18" "node:18-alpine" ; do
  echo "--- ${img} ---"
  trivy image --severity HIGH,CRITICAL --quiet ${img} 2>/dev/null | tail -1
done

# Cleanup
rm -f scan-report.json sbom.json
```

### CI Pipeline Snippet (GitHub Actions)

```yaml
name: Security Scan Pipeline

on: [push]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: Upload scan results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: myapp:${{ github.sha }}
          format: cyclonedx-json
          output-file: sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json
```

### Vulnerability Response Checklist

```markdown
## CVE Response Checklist

1. [ ] Xác nhận CVE severity và affected packages
2. [ ] Query SBOM: service nào dùng affected package?
   - `cat sbom.json | jq '.components[] | select(.name=="<pkg>")'`
3. [ ] Đánh giá exploitability trong context ứng dụng
4. [ ] Nếu CRITICAL + exploitable: tạo incident, patch within 24h
5. [ ] Nếu HIGH: patch within 7 days
6. [ ] Rebuild image với patched base/dependencies
7. [ ] Re-scan để confirm CVE resolved
8. [ ] Deploy patched version (progressive delivery)
9. [ ] Update SBOM
10. [ ] Document trong security log
```

</details>

<details>
<summary>Solution Bài 3: End-to-End Supply Chain (Key Parts)</summary>

### Part A: Image Signing

```bash
# Setup
docker run -d --name registry -p 5000:5000 registry:2
kind create cluster --name supply-chain

# Build and push
docker build -t localhost:5000/secure-app:v1.0.0 .
docker push localhost:5000/secure-app:v1.0.0

# Generate keys
cosign generate-key-pair
# Creates: cosign.key, cosign.pub

# Sign
cosign sign --key cosign.key --allow-insecure-registry localhost:5000/secure-app:v1.0.0

# Verify (should pass)
cosign verify --key cosign.pub --allow-insecure-registry localhost:5000/secure-app:v1.0.0

# Verify unsigned image với digest khác (should fail)
docker pull busybox:1.36
docker tag busybox:1.36 localhost:5000/unsigned-app:v1.0.0
docker push localhost:5000/unsigned-app:v1.0.0
cosign verify --key cosign.pub --allow-insecure-registry localhost:5000/unsigned-app:v1.0.0
# Error: no matching signatures
```

### Part B: Kyverno Policy

```yaml
# kyverno-image-verify.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: Enforce
  background: false
  rules:
    - name: verify-cosign-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "localhost:5000/*"
          attestors:
            - entries:
                - keys:
                    publicKeys: |-
                      -----BEGIN PUBLIC KEY-----
                      <paste cosign.pub content here>
                      -----END PUBLIC KEY-----
```

```bash
# Install Kyverno
helm install kyverno kyverno/kyverno -n kyverno --create-namespace

# Apply policy
kubectl apply -f kyverno-image-verify.yaml

# Test: signed image (should pass)
kubectl run signed-app --image=localhost:5000/secure-app:v1.0.0

# Test: unsigned image (should fail)
kubectl run unsigned-app --image=localhost:5000/unsigned-app:v1.0.0
# Error: image verification failed
```

### Part D: SLSA Level 2 Assessment

```markdown
## SLSA Level 2 Assessment

### Current State
| Requirement | Status | Gap |
|------------|--------|-----|
| Source: version controlled | ✅ | None |
| Build: scripted (not manual) | ✅ | None |
| Build: hosted (not local dev) | ✅ GitHub Actions | None |
| Build: generates provenance | ❌ | No provenance attestation |
| Provenance: signed | ❌ | Not implemented |
| Provenance: service generated | ❌ | Not implemented |

### Gaps to Close
1. **No build provenance**: Need SLSA GitHub Generator
2. **No provenance signing**: Need Sigstore integration
3. **No provenance verification**: Need admission policy

### Recommendations
1. Add `slsa-framework/slsa-github-generator` to CI pipeline
2. Enable keyless signing via Fulcio/Sigstore
3. Add Kyverno policy verifying SLSA provenance
4. Enable Rekor transparency log for audit
```

### Cleanup

```bash
kubectl delete clusterpolicy verify-image-signature
helm uninstall kyverno -n kyverno
kind delete cluster --name supply-chain
docker stop registry && docker rm registry
rm -f cosign.key cosign.pub
```

</details>

