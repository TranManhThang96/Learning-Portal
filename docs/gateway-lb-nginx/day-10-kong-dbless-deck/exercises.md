# Day 10: Exercises — Hands-on decK Workflow

> **Yêu cầu**: Docker, Docker Compose, curl, jq
> **decK version**: 1.40.0
> **Kong version**: 3.7
> **Thời gian ước tính**: 90-120 phút

---

## Cài đặt decK

```bash
# Linux / WSL
curl -sL https://github.com/kong/deck/releases/download/v1.40.0/deck_1.40.0_linux_amd64.tar.gz \
  | tar -xz -C /usr/local/bin deck

# macOS
brew install kong/deck/deck

# Verify
deck version
# Output: decK v1.40.0
```

---

## Exercise 1: Bootstrap Kong DB-less + deck gateway ping

**Mục tiêu**: Khởi động Kong DB-less, verify connectivity với decK.

### Bước 1: Tạo file kong.yml tối thiểu

```bash
mkdir -p ~/kong-lab && cd ~/kong-lab

cat > kong.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: httpbin
    url: https://httpbin.org
    routes:
      - name: httpbin-route
        paths:
          - /httpbin
        strip_path: true
EOF
```

### Bước 2: Khởi động Kong DB-less

```bash
docker run -d \
  --name kong-dbless \
  -e KONG_DATABASE=off \
  -e KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yml \
  -e KONG_ADMIN_LISTEN="0.0.0.0:8001" \
  -e KONG_PROXY_LISTEN="0.0.0.0:8000" \
  -v $(pwd)/kong.yml:/kong/declarative/kong.yml \
  -p 8000:8000 \
  -p 8001:8001 \
  kong:3.7

# Chờ Kong ready
sleep 5
curl -sf http://localhost:8001/ | jq '.version'
```

### Bước 3: Test connectivity với decK

```bash
deck gateway ping --kong-addr http://localhost:8001
```

**Expected output:**
```
Successfully connected to Kong!
Kong version:  3.7.x
```

### Bước 4: Verify DB-less mode

```bash
# Admin API readonly — không thể POST service trực tiếp
curl -s -X POST http://localhost:8001/services \
  -d name=test \
  -d url=http://test.com | jq '.message'
# Expected: "declarative config is read-only"

# Verify service đã load từ kong.yml
curl -s http://localhost:8001/services | jq '.data[].name'
# Expected: "httpbin"
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `connection refused :8001` | Kong chưa ready | Chờ thêm 10s, check `docker logs kong-dbless` |
| `Kong is unreachable` | URL sai | Kiểm tra `--kong-addr http://localhost:8001` |
| `declarative config failed` | kong.yml syntax lỗi | Chạy `deck file lint kong.yml` |

---

## Exercise 2: Workflow Chuẩn — Edit → Lint → Validate → Diff → Sync

**Mục tiêu**: Thực hành full workflow decK cho một thay đổi config.

### Bước 1: Thêm service mới vào kong.yml

```bash
cat >> kong.yml << 'EOF'

  - name: echo-service
    url: http://httpbin.org/anything
    tags:
      - team-a
      - production
    routes:
      - name: echo-route
        paths:
          - /echo
        methods:
          - GET
          - POST
        strip_path: false
    plugins:
      - name: rate-limiting
        config:
          minute: 1000
          policy: local
EOF
```

### Bước 2: Lint offline

```bash
deck file lint kong.yml
```

**Expected output:**
```
Linting kong.yml...
No issues found.
```

**Thử tạo lỗi để xem lint hoạt động:**
```bash
# Thêm field không hợp lệ
echo "    invalid_field: true" >> kong.yml
deck file lint kong.yml
# Expected: [ERROR] ...schema violation...

# Revert lỗi
git checkout kong.yml  # hoặc xóa dòng vừa thêm thủ công
```

### Bước 3: Validate online

```bash
deck gateway validate kong.yml --kong-addr http://localhost:8001
```

**Expected output:**
```
Validating...
No issues found.
```

### Bước 4: Xem diff

```bash
deck gateway diff kong.yml --kong-addr http://localhost:8001
```

**Expected output:**
```
creating service echo-service
creating route echo-route for service echo-service
creating plugin rate-limiting for service echo-service

Summary:
  Created: 3
  Updated: 0
  Deleted: 0
```

### Bước 5: Apply sync

```bash
deck gateway sync kong.yml --kong-addr http://localhost:8001
```

**Expected output:**
```
creating service echo-service
creating route echo-route for service echo-service
creating plugin rate-limiting for service echo-service

Summary:
  Created: 3
  Updated: 0
  Deleted: 0
```

### Bước 6: Verify idempotency

```bash
# Chạy sync lần 2 — không có gì thay đổi
deck gateway sync kong.yml --kong-addr http://localhost:8001
# Expected:
# Summary:
#   Created: 0
#   Updated: 0
#   Deleted: 0
```

### Bước 7: Verify qua Admin API

```bash
curl -s http://localhost:8001/services | jq '.data[] | {name, url}'
# Expected:
# {"name": "httpbin", "url": "https://httpbin.org"}
# {"name": "echo-service", "url": "http://httpbin.org/anything"}

curl -s http://localhost:8000/echo
# Expected: HTTP 200, JSON response từ httpbin.org/anything
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `schema violation: rate-limiting` | Plugin config sai | Check `config.minute` là integer, không phải string |
| Sync OK nhưng route không hoạt động | strip_path conflict | Kiểm tra `strip_path: false` vs `true` |
| `duplicate key value` | Service/route name đã tồn tại | Dùng `deck gateway diff` để xem conflict |

---

## Exercise 3: File Splitting với deck file render

**Mục tiêu**: Tách config thành nhiều file, merge và sync.

### Bước 1: Tạo các file riêng biệt

```bash
mkdir -p ~/kong-lab/split && cd ~/kong-lab/split

cat > services.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: user-service
    url: http://user-svc:3000
    tags: [team-a, production]
    routes:
      - name: user-route
        paths: [/api/v1/users]
        methods: [GET, POST, PUT, DELETE]
        strip_path: false

  - name: order-service
    url: http://order-svc:3001
    tags: [team-b, production]
    routes:
      - name: order-route
        paths: [/api/v1/orders]
        methods: [GET, POST]
        strip_path: false
EOF

cat > consumers.yml << 'EOF'
_format_version: "3.0"
_transform: true

consumers:
  - username: mobile-app
    tags: [team-a, production]
    keyauth_credentials:
      - key: "mobile-app-key-2026"

  - username: web-app
    tags: [team-b, production]
    keyauth_credentials:
      - key: "web-app-key-2026"
EOF

cat > plugins.yml << 'EOF'
_format_version: "3.0"
_transform: true

plugins:
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
EOF
```

### Bước 2: Render thành 1 file để review

```bash
deck file render services.yml consumers.yml plugins.yml -o merged.yml
cat merged.yml
```

**Expected**: File merged.yml chứa tất cả entity từ 3 file, với `_format_version: "3.0"`.

### Bước 3: Lint merged file

```bash
deck file lint merged.yml
```

### Bước 4: Sync trực tiếp từ nhiều file

```bash
# Không cần merge — deck tự merge khi sync
deck gateway sync services.yml consumers.yml plugins.yml \
  --kong-addr http://localhost:8001

# Verify
curl -s http://localhost:8001/services | jq '[.data[].name]'
curl -s http://localhost:8001/consumers | jq '[.data[].username]'
curl -s http://localhost:8001/plugins | jq '[.data[].name]'
```

### Bước 5: Dump lại để verify round-trip

```bash
deck gateway dump -o dumped.yml --kong-addr http://localhost:8001
diff <(cat merged.yml | grep "name:") <(cat dumped.yml | grep "name:")
# Không có diff lớn (có thể khác về ordering và auto-generated fields như id, created_at)
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `duplicate service name` khi render | 2 file cùng define service | Kiểm tra không có tên trùng |
| Consumer credential không apply | `_transform: false` | Đổi thành `_transform: true` |
| Render output thiếu entity | File path sai | Dùng absolute path hoặc kiểm tra cwd |

---

## Exercise 4: Tag-based Partial Sync

**Mục tiêu**: Sync config của team-a mà không ảnh hưởng team-b.

### Bước 1: Tạo config cho 2 team

```bash
mkdir -p ~/kong-lab/teams && cd ~/kong-lab/teams

cat > team-a.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: team-a-api
    url: http://team-a-backend:3000
    tags: [team-a]
    routes:
      - name: team-a-route
        paths: [/team-a]
        tags: [team-a]
    plugins:
      - name: rate-limiting
        tags: [team-a]
        config:
          minute: 500
          policy: local
EOF

cat > team-b.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: team-b-api
    url: http://team-b-backend:3001
    tags: [team-b]
    routes:
      - name: team-b-route
        paths: [/team-b]
        tags: [team-b]
    plugins:
      - name: rate-limiting
        tags: [team-b]
        config:
          minute: 200
          policy: local
EOF
```

### Bước 2: Sync cả 2 team lần đầu

```bash
deck gateway sync team-a.yml team-b.yml \
  --kong-addr http://localhost:8001

# Verify
curl -s http://localhost:8001/services | jq '[.data[].name]'
# ["team-a-api", "team-b-api"]
```

### Bước 3: Thay đổi config team-a, sync chỉ team-a

```bash
# Tăng rate limit của team-a
sed -i 's/minute: 500/minute: 1000/' team-a.yml

# Sync chỉ team-a
deck gateway sync --select-tag team-a team-a.yml \
  --kong-addr http://localhost:8001
```

**Expected output:**
```
updating plugin rate-limiting for service team-a-api
  -  minute: 500
  +  minute: 1000

Summary:
  Created: 0
  Updated: 1
  Deleted: 0
```

### Bước 4: Verify team-b không bị ảnh hưởng

```bash
# Rate limit của team-b vẫn là 200
curl -s http://localhost:8001/services/team-b-api/plugins \
  | jq '.data[] | select(.name=="rate-limiting") | .config.minute'
# Expected: 200
```

### Bước 5: Thử xóa service team-a (chỉ ảnh hưởng team-a)

```bash
# Tạo file team-a rỗng (không có service)
cat > team-a-empty.yml << 'EOF'
_format_version: "3.0"
_transform: true
EOF

# Diff trước
deck gateway diff --select-tag team-a team-a-empty.yml \
  --kong-addr http://localhost:8001
# Expected: deleting service team-a-api, deleting route team-a-route, ...

# Không sync — chỉ xem diff
# Restore team-a.yml
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| `--select-tag` xóa entity của team khác | Entity không có tag | Đảm bảo mọi entity đều có tag |
| Sync không apply change | Tag không match | Kiểm tra tag trong YAML khớp với `--select-tag` |
| `tag not found` | decK version cũ | Upgrade lên decK 1.40+ |

---

## Exercise 5: Rollback Drill

**Mục tiêu**: Thực hành backup → apply broken change → rollback.

### Bước 1: Backup state hiện tại

```bash
cd ~/kong-lab

BACKUP_FILE="backup-pre-change-$(date +%F-%H%M).yml"
deck gateway dump -o "${BACKUP_FILE}" --kong-addr http://localhost:8001
echo "Backup saved: ${BACKUP_FILE}"
cat "${BACKUP_FILE}"
```

### Bước 2: Apply một change "broken"

```bash
cat > broken-change.yml << 'EOF'
_format_version: "3.0"
_transform: true

plugins:
  - name: rate-limiting
    config:
      minute: 1
      policy: local
EOF

deck gateway sync broken-change.yml --kong-addr http://localhost:8001
```

### Bước 3: Verify bị broken

```bash
# Gửi 2 request liên tiếp
curl -s http://localhost:8000/echo
curl -s http://localhost:8000/echo
# Request thứ 2 expected: HTTP 429 Too Many Requests
# {"message":"API rate limit exceeded"}
```

### Bước 4: Rollback

```bash
# Xem diff trước khi rollback
deck gateway diff "${BACKUP_FILE}" --kong-addr http://localhost:8001

# Rollback
deck gateway sync "${BACKUP_FILE}" --kong-addr http://localhost:8001
```

**Expected output:**
```
deleting plugin rate-limiting

Summary:
  Created: 0
  Updated: 0
  Deleted: 1
```

### Bước 5: Verify restored

```bash
curl -s http://localhost:8000/echo
# Expected: HTTP 200 OK

# Verify không còn global rate-limit plugin
curl -s http://localhost:8001/plugins | jq '.data | length'
# Expected: 0 (hoặc số plugin trước khi thêm broken-change)
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Rollback không xóa plugin | Plugin có tag, dùng `--select-tag` | Sync không có `--select-tag` để touch tất cả |
| Backup file thiếu entity | `--skip-consumers` flag | Dump không có flag skip |
| Rollback tạo entity mới | Backup cũ hơn state hiện tại | Dùng backup gần nhất |

---

## Exercise 6: DB-mode Comparison

**Mục tiêu**: Verify decK hoạt động giống nhau với DB-mode và DB-less.

### Bước 1: Khởi động Kong với PostgreSQL

```bash
mkdir -p ~/kong-lab/db-mode && cd ~/kong-lab/db-mode

cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpass
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "kong"]
      interval: 5s
      timeout: 5s
      retries: 5

  kong-migrations:
    image: kong:3.7
    command: kong migrations bootstrap
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_PG_DATABASE: kong
    depends_on:
      postgres:
        condition: service_healthy

  kong:
    image: kong:3.7
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_PG_DATABASE: kong
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
    ports:
      - "8002:8001"
      - "8003:8000"
    depends_on:
      - kong-migrations
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
EOF

docker compose up -d
sleep 15

# Verify DB-mode
curl -s http://localhost:8002/ | jq '.configuration.database'
# Expected: "postgres"
```

### Bước 2: Tạo entity qua Admin API (imperative)

```bash
# Tạo service qua Admin API
curl -s -X POST http://localhost:8002/services \
  -d name=api-via-admin \
  -d url=http://httpbin.org \
  | jq '{name, url}'

# Tạo route
curl -s -X POST http://localhost:8002/services/api-via-admin/routes \
  -d name=route-via-admin \
  -d 'paths[]=/admin-created' \
  | jq '{name, paths}'
```

### Bước 3: Dump state từ DB-mode

```bash
deck gateway dump \
  --kong-addr http://localhost:8002 \
  -o db-mode-state.yml

cat db-mode-state.yml
# Expected: YAML với format 3.0, chứa service và route vừa tạo
```

### Bước 4: Sync thêm entity vào DB-mode

```bash
cat > extra-service.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: api-via-admin
    url: http://httpbin.org
    routes:
      - name: route-via-admin
        paths: [/admin-created]

  - name: api-via-deck
    url: http://httpbin.org/anything
    routes:
      - name: route-via-deck
        paths: [/deck-created]
EOF

deck gateway sync extra-service.yml \
  --kong-addr http://localhost:8002

# Verify
curl -s http://localhost:8002/services | jq '[.data[].name]'
# Expected: ["api-via-admin", "api-via-deck"]
```

### Bước 5: Verify decK hoạt động giống nhau

```bash
# Diff lần 2 — idempotent
deck gateway diff extra-service.yml --kong-addr http://localhost:8002
# Expected: Summary: Created: 0, Updated: 0, Deleted: 0
```

**Kết luận**: decK hoạt động giống nhau với DB-mode và DB-less. Sự khác biệt chỉ ở backing store, không ảnh hưởng đến decK workflow.

---

## Exercise 7 (Optional): Hybrid Mode Setup

**Mục tiêu**: Thiết lập CP-DP, verify config propagation.

### Bước 1: Generate cluster certificate

```bash
mkdir -p ~/kong-lab/hybrid/certs && cd ~/kong-lab/hybrid

docker run --rm \
  -v $(pwd)/certs:/certs \
  kong:3.7 \
  kong hybrid gen_cert \
    /certs/cluster.crt \
    /certs/cluster.key

ls -la certs/
# cluster.crt  cluster.key
```

### Bước 2: Tạo docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: "3.8"
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpass
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "kong"]
      interval: 5s
      retries: 5

  kong-migrations:
    image: kong:3.7
    command: kong migrations bootstrap
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
    depends_on:
      postgres:
        condition: service_healthy

  kong-cp:
    image: kong:3.7
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_ROLE: control_plane
      KONG_CLUSTER_CERT: /certs/cluster.crt
      KONG_CLUSTER_CERT_KEY: /certs/cluster.key
      KONG_CLUSTER_LISTEN: "0.0.0.0:8005"
      KONG_CLUSTER_TELEMETRY_LISTEN: "0.0.0.0:8006"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "off"
    volumes:
      - ./certs:/certs:ro
    ports:
      - "8001:8001"
      - "8005:8005"
    depends_on:
      - kong-migrations

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
      KONG_ADMIN_LISTEN: "off"
    volumes:
      - ./certs:/certs:ro
      - dp1-cache:/usr/local/kong
    ports:
      - "8100:8000"
    depends_on:
      - kong-cp

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
      - "8200:8000"
    depends_on:
      - kong-cp

volumes:
  dp1-cache:
  dp2-cache:
EOF

docker compose up -d
sleep 20
```

### Bước 3: Verify CP-DP connectivity

```bash
# Xem DP đang kết nối
curl -s http://localhost:8001/clustering/data-planes \
  | jq '.data[] | {hostname, last_seen, config_hash}'
# Expected: 2 DP entries với last_seen gần đây
```

### Bước 4: Sync config qua CP, verify DP nhận được

```bash
cat > hybrid-test.yml << 'EOF'
_format_version: "3.0"
_transform: true

services:
  - name: hybrid-test
    url: https://httpbin.org
    routes:
      - name: hybrid-route
        paths: [/hybrid]
        strip_path: true
EOF

# Sync vào CP
deck gateway sync hybrid-test.yml --kong-addr http://localhost:8001

# Chờ DP nhận config (1-2s)
sleep 3

# Test qua DP 1
curl -s http://localhost:8100/hybrid/get | jq '.url'
# Expected: "https://httpbin.org/get"

# Test qua DP 2
curl -s http://localhost:8200/hybrid/get | jq '.url'
# Expected: "https://httpbin.org/get"
```

### Bước 5: Test DP resilience khi CP down

```bash
# Stop CP
docker compose stop kong-cp

# DP vẫn proxy được (dùng cache)
curl -s http://localhost:8100/hybrid/get | jq '.url'
# Expected: HTTP 200 — DP dùng cached config

# Restart CP
docker compose start kong-cp
sleep 5

# Verify DP reconnect
curl -s http://localhost:8001/clustering/data-planes \
  | jq '.data[] | {hostname, last_seen}'
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| DP không kết nối CP | Port 8005 blocked | Check firewall, `docker compose ps` |
| `certificate verify failed` | Cert domain mismatch | Đảm bảo `KONG_CLUSTER_CERT_DOMAIN=kong_clustering` |
| DP không nhận config mới | Version mismatch | Đảm bảo CP và DP cùng major version |
| `clustering/data-planes` trả về empty | DP chưa kết nối | Chờ thêm 10s, check `docker logs kong-dp-1` |

---

## Cleanup

```bash
# Dừng tất cả container
docker stop kong-dbless 2>/dev/null
docker rm kong-dbless 2>/dev/null

cd ~/kong-lab/db-mode && docker compose down -v
cd ~/kong-lab/hybrid && docker compose down -v

# Xóa lab files (optional)
rm -rf ~/kong-lab
```

---

## Tổng Kết

| Exercise | Lệnh chính | Kỹ năng |
|---|---|---|
| 1 | `deck gateway ping` | Bootstrap, connectivity |
| 2 | `lint → validate → diff → sync` | Full workflow |
| 3 | `deck file render` | File splitting |
| 4 | `--select-tag` | Multi-team isolation |
| 5 | `dump → sync backup` | Rollback |
| 6 | DB-mode + decK | Mode comparison |
| 7 | Hybrid CP-DP | Advanced deployment |
