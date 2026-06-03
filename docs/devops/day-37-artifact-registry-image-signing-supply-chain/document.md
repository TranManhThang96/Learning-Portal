# Day 37: Document — Artifact & Supply Chain Security Checklist

Tài liệu này là reference nhanh cho pipeline build artifact production-grade: tag strategy, registry policy, scanning, signing, SBOM và incident response khi có CVE.

## 1. Artifact Promotion Model

```text
source commit
  -> build once
  -> scan
  -> sign
  -> attach SBOM/provenance
  -> push registry
  -> promote by digest across environments
```

Nguyên tắc quan trọng: build một lần, promote cùng digest qua `dev`, `staging`, `production`. Không rebuild riêng cho production vì sẽ mất tính reproducible và khó audit.

## 2. Image Tagging Policy

| Tag | Mutable? | Dùng cho | Ghi chú |
|-----|----------|----------|---------|
| `v1.4.2` | Không nên mutate | Release human-readable | Có thể dùng ở UI, changelog |
| `git-sha` | Immutable | CI/CD, rollback | Bắt buộc cho traceability |
| `sha256:digest` | Immutable thật sự | Deploy production | Nên pin trong GitOps manifest |
| `latest` | Mutable | Local demo | Không dùng production |
| `main` | Mutable | Preview environment | Không dùng production |

Production manifest nên dùng digest:

```yaml
image: ghcr.io/acme/order-service@sha256:abc123...
```

## 3. Registry Checklist

### Access Control

- [ ] Push permission chỉ dành cho CI identity, không cấp rộng cho developer laptop.
- [ ] Pull permission tách theo environment hoặc namespace.
- [ ] Token có expiry và scope tối thiểu.
- [ ] Admin token không dùng trong pipeline thông thường.

### Retention & Garbage Collection

- [ ] Giữ mọi image đã deploy production ít nhất bằng rollback window.
- [ ] Không xóa digest đang được GitOps manifest hoặc cluster sử dụng.
- [ ] Có scheduled garbage collection cho untagged layers.
- [ ] Registry storage có alert trước khi đầy.

### Audit

- [ ] Bật audit log cho push, delete, tag mutate, permission change.
- [ ] Mọi artifact có OCI labels: revision, source, version, created.
- [ ] Mọi release có SBOM và signature.

## 4. Build Pipeline Checklist

- [ ] Checkout source ở commit cụ thể, không build từ branch floating.
- [ ] Build chạy trong ephemeral runner.
- [ ] Dependency install dùng lockfile.
- [ ] Base image pin bằng digest hoặc được update qua bot có review.
- [ ] Image chạy non-root.
- [ ] Không copy secret, `.git`, test fixture nhạy cảm vào image.
- [ ] Trivy/Syft scan chạy trước push hoặc ngay sau push.
- [ ] Cosign signing chạy sau khi image digest tồn tại.
- [ ] Provenance attestation gắn với workflow identity.

## 5. Cosign Commands Reference

### Key-based Signing

```bash
cosign generate-key-pair
cosign sign --key cosign.key ghcr.io/acme/api@sha256:<digest>
cosign verify --key cosign.pub ghcr.io/acme/api@sha256:<digest>
```

Phù hợp cho lab hoặc environment air-gapped. Production cloud-native nên ưu tiên keyless signing nếu CI/CD hỗ trợ OIDC.

### Keyless Signing

```bash
cosign sign --yes ghcr.io/acme/api@sha256:<digest>
cosign verify \
  --certificate-identity-regexp 'https://github.com/acme/.github/workflows/.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/acme/api@sha256:<digest>
```

Keyless signing giảm rủi ro quản lý private key nhưng phụ thuộc OIDC identity và public transparency log.

## 6. SBOM Reference

### Generate

```bash
syft ghcr.io/acme/api@sha256:<digest> -o cyclonedx-json > sbom.cdx.json
trivy image --format cyclonedx --output sbom-trivy.cdx.json ghcr.io/acme/api@sha256:<digest>
```

### Attach

```bash
cosign attach sbom --sbom sbom.cdx.json ghcr.io/acme/api@sha256:<digest>
```

### Minimum Fields

- Package name.
- Version.
- Package manager/ecosystem.
- License nếu có.
- Image digest/source artifact.
- Creation timestamp.

## 7. CVE Response Runbook

### Triage

```bash
trivy image --severity HIGH,CRITICAL ghcr.io/acme/api@sha256:<digest>
trivy image --ignore-unfixed ghcr.io/acme/api@sha256:<digest>
```

Phân loại:

- Exploitable trong runtime path hay chỉ nằm trong build tooling?
- Package có loaded vào process không?
- Container có internet egress/privilege làm tăng impact không?
- Có fixed version chưa?

### Mitigation

- Rebuild với patched base image hoặc dependency.
- Nếu chưa có fix, giảm attack surface: disable feature, network policy, WAF rule, runtime policy.
- Nếu image đã deploy, xác định environment bằng digest, không dựa vào tag.
- Tạo exception có owner và expiry nếu phải accept risk.

### Verification

```bash
trivy image --exit-code 1 --severity CRITICAL ghcr.io/acme/api@sha256:<new-digest>
cosign verify ghcr.io/acme/api@sha256:<new-digest>
```

## 8. Admission Policy Checklist

- [ ] Chặn image không có digest trong production namespace.
- [ ] Chặn registry ngoài allowlist.
- [ ] Require signature từ CI identity chính thức.
- [ ] Require vulnerability scan pass cho severity policy.
- [ ] Require non-root user và không privileged container.
- [ ] Có break-glass process được audit khi cần deploy khẩn cấp.

## 9. SLSA Mapping

| Capability | SLSA hướng tới | Evidence cần giữ |
|------------|----------------|------------------|
| Build từ version-controlled source | Level 1 | commit SHA, workflow run |
| Hosted build service có provenance | Level 2 | provenance attestation |
| Hardened build platform, non-falsifiable provenance | Level 3 | isolated runner, signed provenance |
| Hermetic/reproducible build | Level 4 | dependency pinning, reproducibility proof |

Đa số team nên đặt mục tiêu thực tế: Level 2 trước, sau đó nâng dần các service critical lên Level 3.

## 10. Anti-patterns

- Dùng `latest` trong deployment manifest.
- Scan source repo nhưng không scan final runtime image.
- Sign tag thay vì sign digest.
- Cho developer push trực tiếp vào production registry.
- Xóa old images mà không kiểm tra cluster đang chạy digest nào.
- Có SBOM nhưng không lưu hoặc không attach vào artifact.

