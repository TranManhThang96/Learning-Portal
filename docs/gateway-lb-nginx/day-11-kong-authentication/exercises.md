# Day 11: Exercises — Hands-on Authentication (Key Auth, JWT, mTLS)

> **Yêu cầu**: Docker, Docker Compose, curl, jq, openssl, jwt-cli (optional)
> **jwt-cli**: `go install github.com/golang-jwt/jwt/v5/cmd/jwt@latest` hoặc dùng jwt.io
> **Kong version**: 3.7
> **Thời gian ước tính**: 90-120 phút

---

## Cài đặt môi trường

### Tạo thư mục lab

```bash
mkdir -p ~/kong-auth-lab && cd ~/kong-auth-lab
```

### docker-compose.yml — Kong DB-mode với httpbin

Lab này dùng **DB-mode** vì mục tiêu là luyện credential lifecycle bằng Admin API: tạo Consumer, rotate API key, thêm/xóa JWT credential, bật/tắt plugin theo route. Nếu chạy DB-less, các lệnh `POST /consumers`, `POST /routes/.../plugins` sẽ fail với lỗi `declarative config is read-only`.

```yaml
version: "3.8"
services:
  postgres:
    image: postgres:15-alpine
    container_name: kong-auth-postgres
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kongpass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kong -d kong"]
      interval: 5s
      timeout: 5s
      retries: 20
    networks:
      - kong-net

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
    networks:
      - kong-net

  kong:
    image: kong:3.7
    container_name: kong-auth
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kongpass
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_PROXY_LISTEN: "0.0.0.0:8000, 0.0.0.0:8443 ssl"
      KONG_LOG_LEVEL: info
      KONG_PLUGINS: key-auth,jwt,rate-limiting,prometheus
    ports:
      - "8000:8000"
      - "8443:8443"
      - "8001:8001"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 10
    depends_on:
      kong-migrations:
        condition: service_completed_successfully
    networks:
      - kong-net

  httpbin:
    image: kennethreitz/httpbin:latest
    container_name: httpbin-auth
    networks:
      - kong-net

networks:
  kong-net:
    driver: bridge
```

> **Lưu ý**: mTLS auth plugin là Enterprise plugin trong Kong Gateway. Các exercise 1-4, 6-7 chạy với image `kong:3.7` OSS; Exercise 5 là optional và cần Kong Gateway Enterprise/Konnect hoặc image có `mtls-auth` plugin.

---

## Exercise 1: Key Auth — Consumer + API Key

**Mục tiêu**: Bảo vệ route bằng key-auth plugin, tạo Consumer và API key credential, verify 401 khi không có key và 200 khi có key đúng.

### Bước 1: Khởi động Kong

```bash
cd ~/kong-auth-lab
docker compose up -d
sleep 8

# Verify Kong ready
curl -sf http://localhost:8001/ | jq '.version'
```

### Bước 2: Tạo Service và Route cho httpbin

```bash
curl -s -X POST http://localhost:8001/services \
  -d "name=httpbin-svc" \
  -d "url=http://httpbin:80" | jq '{name, url}'

curl -s -X POST http://localhost:8001/services/httpbin-svc/routes \
  -d "name=httpbin-route" \
  -d "paths[]=/httpbin" \
  -d "strip_path=true" | jq '{name, paths, strip_path}'

curl -s http://localhost:8000/httpbin/get | jq '.url'
# Expected: http://localhost/httpbin/get
```

### Bước 3: Tạo Consumer

```bash
# Tạo consumer cho mobile app
curl -s -X POST http://localhost:8001/consumers \
  -d "username=mobile-app" \
  -d "custom_id=app-ios-2.1.0" \
  -d "tags=team-mobile" | jq '{username, custom_id}'

# Tạo consumer cho partner B2B
curl -s -X POST http://localhost:8001/consumers \
  -d "username=partner-acme" \
  -d "custom_id=partner-acme-corp" \
  -d "tags=team-partner" | jq '{username, custom_id}'
```

### Bước 4: Tạo API Key credential

```bash
# Mobile app — auto-generate key
MOBILE_KEY=$(curl -s -X POST http://localhost:8001/consumers/mobile-app/key-auth \
  | jq -r '.key')
echo "Mobile API Key: $MOBILE_KEY"
# Output: km_<random_string>

# Partner ACME — chỉ định key
curl -s -X POST http://localhost:8001/consumers/partner-acme/key-auth \
  -d "key=km_partner_acme_2026" | jq '{key, consumer, created_at}'
```

### Bước 5: Bật key-auth plugin trên route

```bash
curl -s -X POST http://localhost:8001/routes/httpbin-route/plugins \
  -d "name=key-auth" \
  -d "config.key_names=apikey,X-API-Key" \
  -d "config.key_in_header=true" \
  -d "config.key_in_query=true" \
  -d "config.hide_credentials=false" | jq '{name, enabled, config}'
```

### Bước 6: Test các trường hợp

```bash
# TEST 1: Không có API key → 401
curl -s -w "\nHTTP Status: %{http_code}\n" http://localhost:8000/httpbin/get
# Expected: HTTP 401 Unauthorized

# TEST 2: API key sai → 401
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: wrong-key" \
  http://localhost:8000/httpbin/get
# Expected: HTTP 401

# TEST 3: API key đúng (header) → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: $MOBILE_KEY" \
  http://localhost:8000/httpbin/get | jq '{url, headers}'
# Expected: HTTP 200

# TEST 4: API key đúng (query param) → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  "http://localhost:8000/httpbin/get?apikey=$MOBILE_KEY" | jq '.headers.X-Consumer-Username'
# Expected: mobile-app

# TEST 5: Dùng X-API-Key header → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "X-API-Key: $MOBILE_KEY" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: mobile-app

# TEST 6: Partner key → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: km_partner_acme_2026" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: partner-acme
```

### Bước 7: Inspect consumer headers

```bash
# Xem headers Kong inject vào request upstream nhận
curl -s -H "apikey: $MOBILE_KEY" http://localhost:8000/httpbin/headers \
  | jq '.headers | with_entries(select(.key | startswith("X-Consumer")))'
# Expected:
# {
#   "X-Consumer-Custom-Id": "app-ios-2.1.0",
#   "X-Consumer-Id": "...",
#   "X-Consumer-Username": "mobile-app"
# }
```

### Bước 8: Inspect credential

```bash
# List all key-auth credentials
curl -s http://localhost:8001/key-auths | jq '.data[] | {key: .key, consumer: .consumer.username, enabled: .enabled}'

# Inspect single consumer's credentials
curl -s http://localhost:8001/consumers/mobile-app/key-auth | jq '.data'
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| 401 khi dùng đúng key | Cache chưa updated | `docker restart kong-auth` |
| Key not in header/query | key_names config sai | Check `config.key_names` |
| X-Consumer-Username không có | Auth plugin fail trước khi set header | Verify plugin enable trên route đúng |

---

## Exercise 2: JWT HS256 — Encode, Verify, Exp Claim

**Mục tiêu**: Tạo JWT credential với HS256, sign token, verify signature và exp claim.

### Bước 1: Tạo JWT credential (Kong side)

```bash
# Tạo JWT credential cho mobile-app
curl -s -X POST http://localhost:8001/consumers/mobile-app/jwt \
  -d "algorithm=HS256" \
  -d "key=mobile-app-issuer" \
  | jq '{algorithm, key, consumer}'
```

> Kong generate secret tự động. Extract secret:

```bash
JWT_SECRET=$(curl -s http://localhost:8001/consumers/mobile-app/jwt \
  | jq -r '.data[0].secret')
echo "JWT Secret: $JWT_SECRET"
```

### Bước 2: Tạo route riêng cho JWT

Không dùng lại `httpbin-route` đang có key-auth, vì route đó yêu cầu API key. JWT được test trên route riêng để từng cơ chế auth có kết quả rõ ràng.

```bash
curl -s -X POST http://localhost:8001/services/httpbin-svc/routes \
  -d "name=jwt-route" \
  -d "paths[]=/jwt" \
  -d "strip_path=true" | jq '{name, paths}'

curl -s -X POST http://localhost:8001/routes/jwt-route/plugins \
  -d "name=jwt" \
  -d "config.claims_to_verify=exp" | jq '{name, enabled, config}'
```

### Bước 3: Tạo JWT token (client side)

**Cách 1: Dùng jwt.io (trình duyệt)**

Mở https://jwt.io/, nhập:

- Header: `{"alg":"HS256","typ":"JWT"}`
- Payload:
  ```json
  {
    "iss": "mobile-app-issuer",
    "sub": "mobile-app",
    "aud": "httpbin",
    "exp": 1893456000,
    "iat": 1749800000,
    "jti": "token-001"
  }
  ```
- Verify signature: nhập `$JWT_SECRET`

Copy token.

**Cách 2: Dùng openssl + base64 (không cần jwt-cli)**

```bash
# Tạo HMAC-SHA256 signature bằng tay
HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
PAYLOAD=$(echo -n '{"iss":"mobile-app-issuer","sub":"mobile-app","aud":"httpbin","exp":1893456000,"iat":1749800000,"jti":"token-001"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')

# Sign với HMAC-SHA256
SIGNATURE=$(echo -n "${HEADER}.${PAYLOAD}" \
  | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary \
  | base64 -w0 | tr '+/' '-_' | tr -d '=')

JWT_TOKEN="${HEADER}.${PAYLOAD}.${SIGNATURE}"
echo "JWT Token: $JWT_TOKEN"
```

### Bước 4: Verify JWT token với Kong

```bash
# TEST 1: Valid token → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8000/jwt/get | jq '.headers.X-Consumer-Username'
# Expected: mobile-app, HTTP 200

# TEST 2: Token thiếu "Bearer " prefix → 401
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: $JWT_TOKEN" \
  http://localhost:8000/jwt/get
# Expected: HTTP 401

# TEST 3: Expired token → 401
# Tạo expired token (exp = 1 giây trước)
PAYLOAD_EXP=$(echo -n '{"iss":"mobile-app-issuer","sub":"mobile-app","aud":"httpbin","exp":1,"iat":1749800000}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
SIG_EXP=$(echo -n "${HEADER}.${PAYLOAD_EXP}" \
  | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary \
  | base64 -w0 | tr '+/' '-_' | tr -d '=')
JWT_EXPIRED="${HEADER}.${PAYLOAD_EXP}.${SIG_EXP}"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_EXPIRED" \
  http://localhost:8000/jwt/get
# Expected: HTTP 401, message chứa "expired"
```

### Bước 5: JWT token không có iss match → 401

```bash
# Token với iss không khớp jwt_secret key
PAYLOAD_BAD=$(echo -n '{"iss":"wrong-issuer","sub":"mobile-app","exp":1893456000}' \
  | base64 -w0 | tr '+/' '-_' | tr -d '=')
SIG_BAD=$(echo -n "${HEADER}.${PAYLOAD_BAD}" \
  | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary \
  | base64 -w0 | tr '+/' '-_' | tr -d '=')
JWT_BAD_ISSUER="${HEADER}.${PAYLOAD_BAD}.${SIG_BAD}"

curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_BAD_ISSUER" \
  http://localhost:8000/jwt/get
# Expected: HTTP 401, message chứa "signature"
```

### Bước 6: Decode token để inspect

```bash
# Decode payload (không verify signature)
echo "$JWT_TOKEN" | cut -d. -f2 | base64 -d | jq .
# Expected: payload với iss, sub, exp, iat, jti
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Signature verification failed | Secret mismatch giữa client và Kong | Verify `JWT_SECRET` khớp với Kong |
| Algorithm mismatch | Client sign RS256, Kong expect HS256 | Check `algorithm` trong jwt credential |
| Token expired | exp claim trong quá khứ | Tạo token mới với exp hợp lệ |

---

## Exercise 3: JWT RS256 — RSA Key Pair, Public Key, Key Rotation

**Mục tiêu**: Tạo RSA key pair, configure JWT RS256, verify signature với public key.

### Bước 1: Generate RSA Key Pair

```bash
cd ~/kong-auth-lab
mkdir -p certs

# Generate RSA 2048-bit key pair
openssl genrsa -out certs/rsa_private.pem 2048

# Extract public key
openssl rsa -in certs/rsa_private.pem -pubout \
  -out certs/rsa_public.pem

# Verify
openssl rsa -in certs/rsa_private.pem -check -noout
# Output: RSA key ok

openssl rsa -pubin -in certs/rsa_public.pem -text -noout \
  | grep "Public-Key"
# Output: Public-Key: (2048 bit)
```

### Bước 2: Register RSA Public Key trong Kong

```bash
# Tạo JWT credential với RS256 cho partner-acme
curl -s -X POST http://localhost:8001/consumers/partner-acme/jwt \
  -d "algorithm=RS256" \
  -d "key=partner-acme-issuer" \
  -d "rsa_public_key=$(cat certs/rsa_public.pem)" \
  | jq '{algorithm, key, consumer}'
```

### Bước 3: Sign JWT với RSA Private Key

```bash
# Payload
RS256_HEADER="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
RS256_PAYLOAD=$(echo -n '{
  "iss": "partner-acme-issuer",
  "sub": "partner-acme",
  "aud": "httpbin",
  "exp": 1893456000,
  "iat": 1749800000,
  "jti": "partner-token-001"
}' | base64 -w0 | tr '+/' '-_' | tr -d '=')

# Sign RS256 (RSA-SHA256)
RS256_SIG=$(echo -n "${RS256_HEADER}.${RS256_PAYLOAD}" \
  | openssl dgst -sha256 -sign certs/rsa_private.pem -binary \
  | base64 -w0 | tr '+/' '-_' | tr -d '=')

JWT_RS256="${RS256_HEADER}.${RS256_PAYLOAD}.${RS256_SIG}"
echo "RS256 JWT Token: $JWT_RS256"

# Verify signature locally
echo -n "${RS256_HEADER}.${RS256_PAYLOAD}" \
  | openssl dgst -sha256 -verify certs/rsa_public.pem -signature <(echo "$RS256_SIG" | base64 -d -)
# Output: Verified OK
```

### Bước 4: Verify RS256 JWT với Kong

```bash
# TEST 1: Valid RS256 token → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_RS256" \
  http://localhost:8000/jwt/get | jq '.headers.X-Consumer-Username'
# Expected: partner-acme, HTTP 200

# TEST 2: Use same RS256 token với key-auth plugin (key-auth vẫn enable)
# → JWT được verify trước (priority 1005) → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_RS256" \
  -H "apikey: km_partner_acme_2026" \
  http://localhost:8000/jwt/get | jq '.headers.X-Consumer-Username'
# Expected: partner-acme
```

### Bước 5: JWKS Endpoint (Optional — chỉ dùng khi có external provider)

```bash
# Kong không có built-in JWKS endpoint cho jwt plugin
# Để expose JWKS, dùng route với pre-function plugin hoặc external service
# JWKS endpoint format:

cat > certs/jwks.json << 'EOF'
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "partner-acme-key-1",
      "alg": "RS256",
      "n": "$(cat certs/rsa_public.pem | grep -v '-----' | tr -d '\n')",
      "e": "AQAB"
    }
  ]
}
EOF

# Xem Kong JWT credential đã lưu
curl -s http://localhost:8001/consumers/partner-acme/jwt \
  | jq '.data[] | {algorithm, key, rsa_public_key: (.rsa_public_key != null)}'
```

### Bước 6: Key Rotation — Thêm key mới (không xóa key cũ)

```bash
# Bước 1: Generate new key pair
openssl genrsa -out certs/rsa_private_v2.pem 2048
openssl rsa -in certs/rsa_private_v2.pem -pubout -out certs/rsa_public_v2.pem

# Bước 2: Thêm credential mới cho cùng consumer (nhiều jwt_secret per consumer)
curl -s -X POST http://localhost:8001/consumers/partner-acme/jwt \
  -d "algorithm=RS256" \
  -d "key=partner-acme-issuer-v2" \
  -d "rsa_public_key=$(cat certs/rsa_public_v2.pem)" \
  | jq '{algorithm, key}'

# Bước 3: Verify Kong chấp nhận cả key cũ và key mới
# Token signed với rsa_private_v2.pem → verify bằng rsa_public_v2.pem
# (thực hành tương tự Bước 3)

# Bước 4: Sau khi migrate xong, xóa key cũ
OLD_KEY_ID=$(curl -s http://localhost:8001/consumers/partner-acme/jwt \
  | jq -r '.data[] | select(.key=="partner-acme-issuer") | .id')
curl -s -X DELETE "http://localhost:8001/consumers/partner-acme/jwt/${OLD_KEY_ID}"
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Public key format sai | PEM multiline không xử lý | Dùng `$(cat file.pem)` với `_transform: true` |
| Algorithm mismatch | Kong lưu RS256 nhưng PEM sai format | Verify bằng `openssl rsa -pubin -in pub.pem` |

---

## Exercise 4: Multiple Auth + Anonymous Consumer

**Mục tiêu**: Enable cả key-auth và jwt trên cùng một route, tạo anonymous consumer để fallback.

### Bước 1: Tạo anonymous consumer

```bash
# Tạo anonymous consumer — không có credential
curl -s -X POST http://localhost:8001/consumers \
  -d "username=anonymous" \
  -d "tags=anonymous" | jq '{username, id}'
```

### Bước 2: Update key-auth plugin với anonymous fallback

```bash
# Update plugin config để set anonymous consumer
KEY_PLUGIN_ID=$(curl -s http://localhost:8001/routes/httpbin-route/plugins \
  | jq -r '.data[] | select(.name=="key-auth") | .id')

curl -s -X PATCH "http://localhost:8001/plugins/${KEY_PLUGIN_ID}" \
  -d "config.anonymous=anonymous" | jq '.config.anonymous'
```

### Bước 3: Enable JWT plugin trên cùng route

```bash
# JWT plugin với anonymous fallback
curl -s -X POST http://localhost:8001/routes/httpbin-route/plugins \
  -d "name=jwt" \
  -d "config.anonymous=anonymous" \
  -d "config.claims_to_verify=exp" | jq '{name, enabled, config}'
```

### Bước 4: Test anonymous fallback

```bash
# TEST 1: Không có credential → anonymous → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: anonymous, HTTP 200

# TEST 2: Có key đúng → real consumer → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: km_partner_acme_2026" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: partner-acme, HTTP 200

# TEST 3: Có JWT đúng → real consumer → 200
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Bearer $JWT_RS256" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: partner-acme, HTTP 200

# TEST 4: Có key SAI → 401
# Anonymous chỉ nên dùng cho request không có credential. Credential sai phải bị reject.
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: wrong-key" \
  http://localhost:8000/httpbin/get
# Expected: HTTP 401
```

### Bước 5: Verify consumer context headers

```bash
# Anonymous request
curl -s http://localhost:8000/httpbin/headers \
  | jq '.headers | with_entries(select(.key | startswith("X-Consumer")))'

# Authenticated request
curl -s -H "apikey: $MOBILE_KEY" http://localhost:8000/httpbin/headers \
  | jq '.headers | with_entries(select(.key | startswith("X-Consumer")))'
```

---

## Exercise 5: mTLS Overview — CA Generation, Client Cert, mtls-auth

**Mục tiêu**: Tạo CA và client certificate, configure Kong HTTPS (TLS), configure mtls-auth plugin.

> **Điều kiện chạy**: `mtls-auth` là Enterprise plugin. Nếu dùng image OSS `kong:3.7`, dừng ở phần đọc hiểu và không chạy các lệnh tạo plugin. Để chạy lab, dùng Kong Gateway Enterprise/Konnect hoặc image có plugin `mtls-auth`, và bật `KONG_PLUGINS=bundled` hoặc thêm `mtls-auth` vào danh sách plugin.

### Bước 1: Precheck plugin và HTTPS port

```bash
curl -s http://localhost:8001/plugins/enabled | jq '.enabled_plugins[]' | grep mtls-auth
# Expected nếu môi trường hỗ trợ: "mtls-auth"

curl -sk https://localhost:8443/httpbin/get | jq '.url'
# Expected: https://localhost/httpbin/get
```

Nếu precheck không thấy `mtls-auth`, đọc tiếp để hiểu flow nhưng không chạy các lệnh Admin API bên dưới trên OSS image.

### Bước 2: Generate CA Certificate (cho mTLS Client Cert Verification)

```bash
mkdir -p ~/kong-auth-lab/certs
cd ~/kong-auth-lab/certs

# Generate CA private key
openssl genrsa -out ca.key 4096

# Self-sign CA certificate
openssl req -x509 -new -nodes -key ca.key -sha256 \
  -days 365 -out ca.crt \
  -subj "/CN=Kong-CA/O=Kong-Lab/C=VN"

# Verify CA
openssl x509 -in ca.crt -text -noout \
  | grep -E "Subject:|Issuer:|Not Before|Not After"
# Expected: Issuer = Subject (self-signed)
```

### Bước 3: Generate Client Certificate

```bash
cd ~/kong-auth-lab/certs
openssl genrsa -out client-partner-a.key 2048

# Generate client CSR (Certificate Signing Request)
openssl req -new -key client-partner-a.key \
  -out client-partner-a.csr \
  -subj "/CN=partner-a-client/O=PartnerA/C=VN"

# Sign CSR với CA
openssl x509 -req -in client-partner-a.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 180 -out client-partner-a.crt \
  -sha256

# Verify cert chain
openssl verify -CAfile ca.crt client-partner-a.crt
# Output: client-partner-a.crt: OK

# Inspect client certificate
openssl x509 -in client-partner-a.crt -text -noout \
  | grep -E "Subject:|Issuer:|Not Before|Not After|Serial"
```

### Bước 4: Configure Kong CA Certificate

```bash
# cd ~/kong-auth-lab/certs
# Register CA certificate trong Kong (từ thư mục certs)
curl -s -X POST http://localhost:8001/ca_certificates \
  -F "cert=@ca.crt" | jq '{id}'
```

### Bước 5: Tạo Service/Route cho mTLS

```bash
# Tạo service mới cho mTLS endpoint
curl -s -X POST http://localhost:8001/services \
  -d "name=mtls-service" \
  -d "url=http://httpbin:80" | jq '{name}'

# Tạo route với HTTPS (TLS termination)
curl -s -X POST http://localhost:8001/services/mtls-service/routes \
  -d "name=mtls-route" \
  -d "paths[]=/mtls" \
  -d "strip_path=true" \
  -d "protocols[]=https" | jq '{name, protocols}'
```

### Bước 6: Enable mtls-auth Plugin

```bash
# Bật mtls-auth plugin với CA đã đăng ký
CA_ID=$(curl -s http://localhost:8001/ca_certificates \
  | jq -r '.data[0].id')

curl -s -X POST http://localhost:8001/routes/mtls-route/plugins \
  -d "name=mtls-auth" \
  -d "config.skip_consumer_lookup=false" \
  -d "config.revocation_check_mode=SKIP" \
  -d "config.send_ca_dn=true" \
  -d "config.ca_certificates[0]=$CA_ID" | jq '{name, enabled, config}'
```

### Bước 7: Tạo Consumer với mTLS Credential

```bash
# Tạo consumer cho partner A
curl -s -X POST http://localhost:8001/consumers \
  -d "username=partner-a-mtls" | jq '{username}'

# Map client certificate subject name → Consumer
curl -s -X POST http://localhost:8001/consumers/partner-a-mtls/mtls-auth \
  -d "ca_certificate=${CA_ID}" \
  -d "subject_name=partner-a-client" | jq '{subject_name, consumer}'
```

### Bước 8: Test mTLS với curl

```bash
# TEST 1: Request không có client certificate → 403
curl -k -s -w "\nHTTP Status: %{http_code}\n" \
  https://localhost:8443/mtls/get
# Expected: HTTP 403 Forbidden

# TEST 2: Request với client certificate signed bởi CA → 200
curl -k -s -w "\nHTTP Status: %{http_code}\n" \
  --cert certs/client-partner-a.crt \
  --key certs/client-partner-a.key \
  --cacert certs/ca.crt \
  https://localhost:8443/mtls/get | jq '.headers.X-Consumer-Username'
# Expected: partner-a-mtls, HTTP 200
```

**Verify mTLS handshake details:**

```bash
# Xem TLS handshake với client certificate
openssl s_client -connect localhost:8443 \
  -cert client-partner-a.crt \
  -key client-partner-a.key \
  -CAfile ca.crt \
  -state -debug 2>&1 | grep -E "SSL|TLS|Certificate|subject|issuer"
```

**Lỗi thường gặp:**

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| 403 khi dùng đúng cert | CA không match | Verify CA đã register đúng trong Kong |
| `SSL handshake failure` | Kong không receive client cert | Check Kong TLS config, `client_verify` |
| Consumer not found | `skip_consumer_lookup=false` + cert không map | Tạo mtls_auth_credential hoặc set `skip_consumer_lookup=true` |

---

## Exercise 6: Auth + Rate Limiting per Consumer

**Mục tiêu**: Kết hợp key-auth và rate-limiting, verify mỗi consumer có quota riêng.

### Bước 1: Rate Limiting per Consumer (auth plugin đã bật)

```bash
# Mobile app: 1000 req/min
curl -s -X POST http://localhost:8001/consumers/mobile-app/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=1000" \
  -d "config.policy=local" | jq '{name, consumer, config}'

# Partner ACME: 500 req/min
curl -s -X POST http://localhost:8001/consumers/partner-acme/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=500" \
  -d "config.policy=local" | jq '{name, consumer, config}'

# Anonymous: 10 req/min
curl -s -X POST http://localhost:8001/consumers/anonymous/plugins \
  -d "name=rate-limiting" \
  -d "config.minute=10" \
  -d "config.policy=local" | jq '{name, consumer, config}'
```

### Bước 2: Verify per-consumer rate limit

```bash
# Mobile app: 1000 req/min → allow 5 requests liên tiếp
echo "=== Mobile App (1000/min) ==="
for i in 1 2 3 4 5; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "apikey: $MOBILE_KEY" \
    https://localhost:8443/httpbin/get 2>/dev/null \
    || curl -s -o /dev/null -w "%{http_code}" \
      -H "apikey: $MOBILE_KEY" \
      http://localhost:8000/httpbin/get)
  echo "Request $i: HTTP $STATUS"
done

# Anonymous: 10 req/min → sau request 11 sẽ bị 429
echo "=== Anonymous (10/min) ==="
for i in $(seq 1 15); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    http://localhost:8000/httpbin/get 2>/dev/null)
  echo "Request $i: HTTP $STATUS"
  if [ "$STATUS" = "429" ]; then
    echo "Rate limit hit at request $i"
    break
  fi
done
```

### Bước 3: Prometheus metrics cho auth + rate limit

```bash
# Bật prometheus plugin (global)
curl -s -X POST http://localhost:8001/plugins \
  -d "name=prometheus" | jq '{name, enabled}'

# Test metrics endpoint
curl -s http://localhost:8001/metrics | grep "^kong_http_requests_total" \
  | grep -E "key_auth|jwt|status=401|status=429" | head -20
```

---

## Exercise 7 (Optional): Key Rotation + Blacklist Strategy

**Mục tiêu**: Thực hành JWT key rotation và API key revocation workflow.

### Bước 1: Simulate API Key Rotation

```bash
# Bước 1: Tạo key mới trước khi revoke key cũ
NEW_KEY=$(curl -s -X POST http://localhost:8001/consumers/mobile-app/key-auth \
  | jq -r '.key')
echo "New Key: $NEW_KEY"

# Bước 2: Verify key mới hoạt động
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: $NEW_KEY" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'

# Bước 3: Verify key cũ vẫn hoạt động
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: $MOBILE_KEY" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'

# Bước 4: Revoke key cũ (sau khi verify key mới hoạt động)
OLD_KEY_ID=$(curl -s http://localhost:8001/consumers/mobile-app/key-auth \
  | jq -r ".data[] | select(.key==\"$MOBILE_KEY\") | .id")
curl -s -X DELETE "http://localhost:8001/consumers/mobile-app/key-auth/${OLD_KEY_ID}"

# Bước 5: Verify key cũ không hoạt động
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: $MOBILE_KEY" \
  http://localhost:8000/httpbin/get
# Expected: HTTP 401

# Bước 6: Verify key mới vẫn hoạt động
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "apikey: $NEW_KEY" \
  http://localhost:8000/httpbin/get | jq '.headers.X-Consumer-Username'
# Expected: mobile-app, HTTP 200
```

### Bước 2: JWT Blacklist Strategy (JWT không revoke được — dùng short exp)

```bash
# JWT không có built-in blacklist. Các chiến lược:

# Strategy 1: Short-lived token
# exp = 900s (15 phút)
# → Nếu token bị leak, attacker chỉ có 15 phút sử dụng

# Strategy 2: Token ID blacklist (requires external store)
# Khi revoke: thêm jti vào Redis blacklist
# Verify JWT: check jti có trong blacklist không
# Kong không có built-in JWT blacklist — cần custom plugin

# Strategy 3: Kong JWT + external blacklist plugin
# (đây là advanced topic — không implement trong lab này)
```

---

## Cleanup

```bash
cd ~/kong-auth-lab
docker compose down -v

# Xóa lab files
rm -rf ~/kong-auth-lab

# Verify cleanup
docker ps | grep kong || echo "All Kong containers removed"
```

---

## Tổng Kết

| Exercise | Chủ đề | Lệnh quan trọng |
|---|---|---|
| 1 | Key Auth | `POST /consumers/{name}/key-auth`, key-auth plugin |
| 2 | JWT HS256 | `POST /consumers/{name}/jwt`, HMAC sign, exp claim |
| 3 | JWT RS256 | `openssl genrsa`, RSA sign/verify, key rotation |
| 4 | Multiple Auth + Anonymous | `config.anonymous=anonymous`, plugin priority |
| 5 | mTLS Overview | CA generation, `POST /ca_certificates`, mtls-auth |
| 6 | Auth + Rate Limiting | Consumer-level rate-limit plugin, per-consumer quota |
| 7 | Key Rotation | Delete credential → immediate revocation |
