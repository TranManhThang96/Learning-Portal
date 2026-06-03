# Day 10: Reference Document — decK Command Reference, Hybrid Mode Deep Dive & GitOps Pipeline

---

## 1. decK Command Reference (Kong 3.x / decK 1.40+)

> **Quan trọng**: Từ decK 1.21+, tất cả lệnh tương tác với Kong dùng subcommand `deck gateway <verb>`. Lệnh cũ như `deck dump`, `deck sync` vẫn hoạt động nhưng deprecated. Bài này dùng **decK 1.40+** với **Kong 3.6/3.7**.

### 1.1 Global Flags

| Flag | Default | Mô tả |
|---|---|---|
| `--kong-addr` | `http://localhost:8001` | Admin API URL |
| `--headers` | — | HTTP headers (ví dụ: `"Kong-Admin-Token:secret"`) |
| `--tls-skip-verify` | false | Skip TLS verify (chỉ dùng dev) |
| `--ca-cert` | — | CA cert file cho TLS |
| `--verbose` | 0 | Verbosity level (0-3) |
| `--config` | `$HOME/.deck.yaml` | decK config file |
| `--workspace` | — | Kong workspace (Enterprise) |

### 1.2 deck gateway ping

Test connectivity với Kong Admin API.

```bash
deck gateway ping \
  --kong-addr http://localhost:8001

# Output khi thành công:
# Successfully connected to Kong!
# Kong version:  3.7.1

# Output khi fail:
# Error: could not connect to Kong: ...
```

### 1.3 deck gateway dump

Export toàn bộ Kong config ra YAML file.

```bash
# Dump toàn bộ config
deck gateway dump \
  --kong-addr http://localhost:8001 \
  -o kong.yml

# Dump chỉ entity có tag cụ thể
deck gateway dump \
  --select-tag team-a \
  -o team-a-state.yml

# Dump với format version cụ thể
deck gateway dump \
  --format-version 3.0 \
  -o kong.yml

# Dump không include consumer credentials (security)
deck gateway dump \
  --skip-consumers \
  -o kong-no-creds.yml
```

**Output format:**
```yaml
_format_version: "3.0"
_transform: true

services:
  - name: my-service
    # ... full entity state
```

### 1.4 deck file lint

Validate YAML syntax và schema **offline** (không cần Kong running).

```bash
# Lint single file
deck file lint kong.yml

# Lint multiple files
deck file lint services.yml consumers.yml plugins.yml

# Lint với custom ruleset
deck file lint --ruleset custom-rules.yml kong.yml

# Output khi OK:
# Linting kong.yml...
# No issues found.

# Output khi có lỗi:
# Linting kong.yml...
# [ERROR] services[0].routes[0]: missing required field 'paths'
```

### 1.5 deck gateway validate

Validate YAML **online** — gửi lên Kong để kiểm tra schema và business logic.

```bash
# Validate single file
deck gateway validate kong.yml \
  --kong-addr http://localhost:8001

# Validate multiple files
deck gateway validate services.yml consumers.yml \
  --kong-addr http://localhost:8001

# Output khi OK:
# Validating...
# No issues found.

# Output khi có lỗi:
# Validating...
# [ERROR] service 'my-service': route 'my-route': schema violation (paths: required field missing)
```

**Khác biệt lint vs validate:**
- `deck file lint`: offline, kiểm tra YAML syntax + decK schema
- `deck gateway validate`: online, Kong kiểm tra business logic (ví dụ: plugin config hợp lệ không)

### 1.6 deck gateway diff

So sánh desired state (YAML) với current Kong state. **Không thay đổi gì.**

```bash
# Diff single file
deck gateway diff kong.yml \
  --kong-addr http://localhost:8001

# Diff với tag filter
deck gateway diff \
  --select-tag team-a \
  team-a.yml \
  --kong-addr http://localhost:8001

# Output mẫu:
# creating service echo-service
# creating route echo-route for service echo-service
# updating plugin rate-limiting for service user-service
#   -  minute: 100
#   +  minute: 1000
# deleting service old-service
#
# Summary:
#   Created: 2
#   Updated: 1
#   Deleted: 1
```

### 1.7 deck gateway sync

Apply diff vào Kong. **Idempotent** — chạy nhiều lần cho kết quả giống nhau.

```bash
# Sync single file
deck gateway sync kong.yml \
  --kong-addr http://localhost:8001

# Sync multiple files (merge tự động)
deck gateway sync services.yml consumers.yml plugins.yml \
  --kong-addr http://localhost:8001

# Sync với tag filter (chỉ touch entity có tag)
deck gateway sync \
  --select-tag team-a \
  team-a.yml \
  --kong-addr http://localhost:8001

# Sync với parallelism cao hơn (cho nhiều entity)
deck gateway sync kong.yml \
  --parallelism 20 \
  --kong-addr http://localhost:8001

# Dry-run (chỉ show diff, không apply) — dùng diff thay thế
deck gateway diff kong.yml --kong-addr http://localhost:8001
```

### 1.8 deck gateway reset

**NGUY HIỂM**: Xóa toàn bộ entity trong Kong. Không có undo.

```bash
# Reset toàn bộ (yêu cầu confirm)
deck gateway reset \
  --kong-addr http://localhost:8001
# Prompt: "This will delete all entities in Kong. Are you sure? [y/N]"

# Reset không confirm (dùng trong CI với caution)
deck gateway reset \
  --force \
  --kong-addr http://localhost:8001

# Reset chỉ entity có tag (an toàn hơn)
deck gateway reset \
  --select-tag team-a \
  --force \
  --kong-addr http://localhost:8001
```

**Anti-pattern**: Không bao giờ dùng `deck gateway reset --force` trên production mà không có backup.

### 1.9 deck file render

Merge nhiều YAML file thành 1 file duy nhất.

```bash
# Merge 3 file thành 1
deck file render \
  services.yml consumers.yml plugins.yml \
  -o merged.yml

# Render với output ra stdout
deck file render services.yml consumers.yml plugins.yml

# Render để review trước khi sync
deck file render *.yml | deck gateway diff - --kong-addr http://localhost:8001
```

### 1.10 deck file convert

Convert giữa các format version.

```bash
# Convert từ Kong 2.x format sang Kong 3.x format
deck file convert \
  --from kong-gateway-2.x \
  --to kong-gateway-3.x \
  -i old-kong.yml \
  -o new-kong.yml

# Convert từ format 1.1 sang 3.0
deck file convert \
  --from 1.1 \
  --to 3.0 \
  -i kong-v1.yml \
  -o kong-v3.yml
```

### 1.11 deck file patch

Apply JSON patch operations lên YAML file.

```bash
# Patch một field cụ thể
deck file patch \
  --selector "$.services[?(@.name=='user-service')]" \
  --value '{"read_timeout": 30000}' \
  kong.yml

# Patch plugin config
deck file patch \
  --selector "$.plugins[?(@.name=='rate-limiting')].config" \
  --value '{"minute": 2000}' \
  kong.yml
```

### 1.12 Tóm Tắt Command Matrix

| Command | Online? | Thay đổi Kong? | Dùng khi |
|---|---|---|---|
| `deck gateway ping` | Có | Không | Test connectivity |
| `deck file lint` | Không | Không | Validate YAML offline |
| `deck gateway validate` | Có | Không | Validate schema online |
| `deck gateway dump` | Có | Không | Export current state |
| `deck gateway diff` | Có | Không | Preview changes |
| `deck gateway sync` | Có | **Có** | Apply changes |
| `deck gateway reset` | Có | **Có (xóa hết)** | Wipe Kong state |
| `deck file render` | Không | Không | Merge files |
| `deck file convert` | Không | Không | Migrate format |
| `deck file patch` | Không | Không | Patch YAML |

---

## 2. Hybrid Mode Architecture Deep Dive

### 2.1 Clustering Protocol

Hybrid mode dùng **WebSocket over mTLS** (port 8005) để CP push config xuống DP.

```
CP (port 8005) ←──── mTLS WebSocket ────► DP
                     (persistent conn)
                     
Protocol: wrpc (WebSocket RPC)
- CP push config khi có thay đổi
- DP gửi heartbeat mỗi 30s
- DP gửi vitals data (request count, latency) lên CP
```

### 2.2 Certificate Generation

```bash
# Cách 1: Dùng kong hybrid gen_cert (built-in)
docker run --rm \
  -v $(pwd)/certs:/certs \
  kong:3.7 \
  kong hybrid gen_cert \
    /certs/cluster.crt \
    /certs/cluster.key

# Cách 2: Dùng openssl (manual)
openssl req -new -x509 \
  -nodes \
  -newkey ec \
  -pkeyopt ec_paramgen_curve:P-256 \
  -keyout cluster.key \
  -out cluster.crt \
  -days 1095 \
  -subj "/CN=kong_clustering"

# Verify cert
openssl x509 -in cluster.crt -text -noout | grep -E "Subject:|Not After"
```

### 2.3 Control Plane Configuration

```yaml
# docker-compose.yml — Control Plane
version: "3.8"
services:
  kong-cp:
    image: kong:3.7
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_PG_DATABASE: kong
      KONG_ROLE: control_plane
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_CLUSTER_LISTEN: "0.0.0.0:8005"
      KONG_CLUSTER_TELEMETRY_LISTEN: "0.0.0.0:8006"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "off"  # CP không proxy traffic
      KONG_LOG_LEVEL: info
    volumes:
      - ./certs:/certs:ro
    ports:
      - "8001:8001"  # Admin API
      - "8005:8005"  # Cluster port
    depends_on:
      - postgres
```

### 2.4 Data Plane Configuration

```yaml
# docker-compose.yml — Data Plane
  kong-dp-1:
    image: kong:3.7
    environment:
      KONG_DATABASE: "off"
      KONG_ROLE: data_plane
      KONG_CLUSTER_CONTROL_PLANE: kong-cp:8005
      KONG_CLUSTER_TELEMETRY_ENDPOINT: kong-cp:8006
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_CLUSTER_CERT_DOMAIN: kong_clustering
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "off"  # DP không expose Admin API
      KONG_LOG_LEVEL: info
      # Disk cache location
      KONG_DECLARATIVE_CONFIG_STRING: ""
    volumes:
      - ./certs:/certs:ro
      - dp1-cache:/usr/local/kong
    ports:
      - "8100:8000"  # DP 1 proxy port

  kong-dp-2:
    image: kong:3.7
    environment:
      KONG_DATABASE: "off"
      KONG_ROLE: data_plane
      KONG_CLUSTER_CONTROL_PLANE: kong-cp:8005
      KONG_CLUSTER_TELEMETRY_ENDPOINT: kong-cp:8006
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_CLUSTER_CERT_DOMAIN: kong_clustering
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "off"
    volumes:
      - ./certs:/certs:ro
      - dp2-cache:/usr/local/kong
    ports:
      - "8200:8000"  # DP 2 proxy port

volumes:
  dp1-cache:
  dp2-cache:
```

### 2.5 DP Fallback Cache

DP lưu config cache tại `/usr/local/kong/config.json.gz`. Lifecycle:

```
DP start → connect CP → nhận config → lưu vào disk cache
         ↓ (nếu CP unreachable)
         → load từ disk cache → proxy traffic bình thường
         ↓ (nếu không có disk cache VÀ CP unreachable)
         → fail to start (không có config)
```

**Verify cache:**
```bash
# Exec vào DP container
docker exec kong-dp-1 ls -la /usr/local/kong/
# -rw-r--r-- 1 kong kong 12345 May 18 14:30 config.json.gz

# Xem config hash
docker exec kong-dp-1 kong health
```

### 2.6 Version Compatibility

CP và DP phải cùng **major version**. Minor version có thể khác nhau trong giới hạn:

| CP Version | DP Version | Status |
|---|---|---|
| 3.7.x | 3.7.x | OK (recommended) |
| 3.7.x | 3.6.x | OK (DP có thể thiếu feature mới) |
| 3.7.x | 3.5.x | Cần kiểm tra compatibility matrix |
| 3.7.x | 2.x.x | Không hỗ trợ |

---

## 3. GitOps Pipeline — GitHub Actions

### 3.1 Repository Structure

```
kong-config/
├── .github/
│   └── workflows/
│       ├── ci.yml          # PR validation
│       └── cd.yml          # Deploy to production
├── environments/
│   ├── staging/
│   │   └── kong.yml
│   └── production/
│       └── kong.yml
├── teams/
│   ├── team-a/
│   │   ├── services.yml
│   │   ├── consumers.yml
│   │   └── plugins.yml
│   └── team-b/
│       ├── services.yml
│       └── plugins.yml
└── shared/
    └── global-plugins.yml
```

### 3.2 CI Pipeline (PR Validation)

```yaml
# .github/workflows/ci.yml
name: Kong Config CI

on:
  pull_request:
    branches: [main]
    paths:
      - 'environments/**'
      - 'teams/**'
      - 'shared/**'

env:
  DECK_VERSION: "1.40.0"
  KONG_VERSION: "3.7"

jobs:
  lint-and-validate:
    name: Lint & Validate
    runs-on: ubuntu-latest
    concurrency:
      group: kong-ci-${{ github.ref }}
      cancel-in-progress: true

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install decK
        run: |
          curl -sL "https://github.com/kong/deck/releases/download/v${DECK_VERSION}/deck_${DECK_VERSION}_linux_amd64.tar.gz" \
            | tar -xz -C /usr/local/bin deck
          deck version

      - name: Render merged config
        run: |
          deck file render \
            teams/team-a/services.yml \
            teams/team-a/consumers.yml \
            teams/team-a/plugins.yml \
            teams/team-b/services.yml \
            teams/team-b/plugins.yml \
            shared/global-plugins.yml \
            -o /tmp/merged.yml

      - name: Lint (offline)
        run: deck file lint /tmp/merged.yml

      - name: Start staging Kong
        run: |
          docker run -d \
            --name kong-staging \
            -e KONG_DATABASE=off \
            -e KONG_DECLARATIVE_CONFIG=/kong/declarative/empty.yml \
            -e KONG_ADMIN_LISTEN="0.0.0.0:8001" \
            -p 8001:8001 \
            kong:${KONG_VERSION}
          # Wait for Kong to be ready
          timeout 60 bash -c 'until curl -sf http://localhost:8001/; do sleep 2; done'

      - name: Validate (online — staging)
        run: |
          deck gateway validate /tmp/merged.yml \
            --kong-addr http://localhost:8001

      - name: Diff (staging preview)
        run: |
          deck gateway diff /tmp/merged.yml \
            --kong-addr http://localhost:8001 \
            | tee /tmp/diff-output.txt

      - name: Comment diff on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const diff = fs.readFileSync('/tmp/diff-output.txt', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Kong Config Diff (Staging)\n\`\`\`\n${diff}\n\`\`\``
            });
```

### 3.3 CD Pipeline (Deploy to Production)

```yaml
# .github/workflows/cd.yml
name: Kong Config CD

on:
  push:
    branches: [main]
    paths:
      - 'environments/production/**'
      - 'teams/**'
      - 'shared/**'

env:
  DECK_VERSION: "1.40.0"

jobs:
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    environment: production
    concurrency:
      group: kong-production-deploy
      cancel-in-progress: false  # Không cancel deploy đang chạy

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install decK
        run: |
          curl -sL "https://github.com/kong/deck/releases/download/v${DECK_VERSION}/deck_${DECK_VERSION}_linux_amd64.tar.gz" \
            | tar -xz -C /usr/local/bin deck

      - name: Render merged config
        run: |
          deck file render \
            teams/team-a/services.yml \
            teams/team-a/consumers.yml \
            teams/team-a/plugins.yml \
            teams/team-b/services.yml \
            teams/team-b/plugins.yml \
            shared/global-plugins.yml \
            -o /tmp/merged.yml

      - name: Backup current production state
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_PROD_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_PROD_ADMIN_TOKEN }}
        run: |
          BACKUP_FILE="backups/state-$(date +%F-%H%M)-pre-deploy.yml"
          mkdir -p backups
          deck gateway dump \
            --kong-addr "${KONG_ADMIN_URL}" \
            --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}" \
            -o "${BACKUP_FILE}"
          echo "BACKUP_FILE=${BACKUP_FILE}" >> $GITHUB_ENV
          echo "Backup saved to ${BACKUP_FILE}"

      - name: Upload backup as artifact
        uses: actions/upload-artifact@v4
        with:
          name: kong-backup-${{ github.sha }}
          path: backups/
          retention-days: 30

      - name: Diff production (preview)
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_PROD_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_PROD_ADMIN_TOKEN }}
        run: |
          deck gateway diff /tmp/merged.yml \
            --kong-addr "${KONG_ADMIN_URL}" \
            --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}"

      - name: Sync production
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_PROD_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_PROD_ADMIN_TOKEN }}
        run: |
          deck gateway sync /tmp/merged.yml \
            --kong-addr "${KONG_ADMIN_URL}" \
            --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}" \
            --parallelism 10

      - name: Smoke test
        env:
          KONG_PROXY_URL: ${{ secrets.KONG_PROD_PROXY_URL }}
        run: |
          # Test một số route quan trọng
          curl -sf "${KONG_PROXY_URL}/api/v1/users" -o /dev/null \
            && echo "user-service OK" \
            || (echo "user-service FAILED" && exit 1)

      - name: Tag deployment
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag "deploy-$(date +%F-%H%M)-${{ github.sha }}"
          git push origin --tags
```

### 3.4 Rollback Workflow

```yaml
# .github/workflows/rollback.yml
name: Kong Config Rollback

on:
  workflow_dispatch:
    inputs:
      backup_artifact:
        description: 'Artifact name (e.g., kong-backup-abc123)'
        required: true
      confirm:
        description: 'Type "ROLLBACK" to confirm'
        required: true

jobs:
  rollback:
    name: Rollback Production
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Validate confirmation
        run: |
          if [ "${{ github.event.inputs.confirm }}" != "ROLLBACK" ]; then
            echo "Confirmation failed. Exiting."
            exit 1
          fi

      - name: Install decK
        run: |
          curl -sL "https://github.com/kong/deck/releases/download/v${DECK_VERSION}/deck_${DECK_VERSION}_linux_amd64.tar.gz" \
            | tar -xz -C /usr/local/bin deck
        env:
          DECK_VERSION: "1.40.0"

      - name: Download backup artifact
        uses: actions/download-artifact@v4
        with:
          name: ${{ github.event.inputs.backup_artifact }}
          path: ./backup

      - name: Rollback
        env:
          KONG_ADMIN_URL: ${{ secrets.KONG_PROD_ADMIN_URL }}
          KONG_ADMIN_TOKEN: ${{ secrets.KONG_PROD_ADMIN_TOKEN }}
        run: |
          BACKUP_FILE=$(ls backup/*.yml | head -1)
          echo "Rolling back to: ${BACKUP_FILE}"
          deck gateway sync "${BACKUP_FILE}" \
            --kong-addr "${KONG_ADMIN_URL}" \
            --headers "Kong-Admin-Token:${KONG_ADMIN_TOKEN}"
```

---

## 4. Format Version Migration Guide

### 4.1 Format Version History

| decK Version | Format Version | Kong Version | Notes |
|---|---|---|---|
| < 1.7 | `1.0` | Kong 1.x | Legacy |
| 1.7 - 1.20 | `1.1` | Kong 2.x | Phổ biến nhất cũ |
| 1.21+ | `3.0` | Kong 3.x | Current standard |

### 4.2 Thay Đổi Chính từ 1.1 → 3.0

| Aspect | Format 1.1 | Format 3.0 |
|---|---|---|
| Route paths | `paths: ["/api"]` | `paths: ["/api"]` (giống) |
| Plugin scope | `service_id`, `route_id` | Nested trong service/route |
| Consumer credentials | Flat list | Nested trong consumer |
| Upstream targets | Separate section | Nested trong upstream |
| `_transform` | Không có | Có (default: true) |

### 4.3 Migration Command

```bash
# Convert file từ format cũ sang mới
deck file convert \
  --from kong-gateway-2.x \
  --to kong-gateway-3.x \
  -i old-kong-1.1.yml \
  -o new-kong-3.0.yml

# Verify sau convert
deck file lint new-kong-3.0.yml
deck gateway validate new-kong-3.0.yml --kong-addr http://localhost:8001
```

### 4.4 Ví Dụ Migration

**Format 1.1 (cũ):**
```yaml
_format_version: "1.1"

services:
  - name: my-service
    url: http://backend:3000
    id: "550e8400-e29b-41d4-a716-446655440000"

routes:
  - name: my-route
    service:
      id: "550e8400-e29b-41d4-a716-446655440000"
    paths:
      - /api

plugins:
  - name: rate-limiting
    service_id: "550e8400-e29b-41d4-a716-446655440000"
    config:
      minute: 100
```

**Format 3.0 (mới):**
```yaml
_format_version: "3.0"
_transform: true

services:
  - name: my-service
    url: http://backend:3000
    routes:
      - name: my-route
        paths:
          - /api
    plugins:
      - name: rate-limiting
        config:
          minute: 100
```

---

## 5. decK Config File (~/.deck.yaml)

```yaml
# ~/.deck.yaml — decK global config
kong-addr: http://localhost:8001
headers:
  - "Kong-Admin-Token:my-secret-token"
tls-skip-verify: false
verbose: 0

# Workspace (Kong Enterprise)
# workspace: default
```

Dùng environment variable để override:
```bash
export DECK_KONG_ADDR=http://prod-kong:8001
export DECK_HEADERS="Kong-Admin-Token:prod-secret"
deck gateway diff kong.yml
```
