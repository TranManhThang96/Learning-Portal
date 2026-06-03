# Day 22: Security & Multi-tenancy — Authentication, Authorization, Encryption, Quotas

> Companion split: xem `document.md` để đào sâu security model/runbook và `exercises.md` để làm lab/checklist riêng.

## 1. Mục tiêu bài học (Learning Objectives)

Sau 2 giờ học, bạn sẽ:

1. **Hiểu sâu** Kafka security model — tại sao cần security, attack vectors, defense-in-depth layers
2. **Nắm vững** authentication mechanisms: SASL/PLAIN, SASL/SCRAM, mTLS — khi nào dùng gì và trade-off
3. **Thực hành** authorization với ACLs — fine-grained access control cho topics, consumer groups, transactional IDs
4. **Hiểu** encryption: TLS in-transit, encryption at rest — setup và performance impact
5. **Biết** multi-tenancy: quotas, topic naming conventions, tenant isolation strategies, audit logging

## 2. Kiến thức nền (Prerequisites)

- Đã hoàn thành Day 10-14 (Kafka fundamentals, producer/consumer, replication, KRaft)
- Hiểu cơ bản về TLS/SSL, certificates, authentication vs authorization
- Hiểu producer/consumer configuration
- Docker Compose Kafka cluster đang chạy
- Familiar với openssl commands (basic)

## 3. Phạm vi học trong 2 giờ (Scope Control)

### 🔴 Must Learn (90 phút)
- Kafka security model — layers, threat model
- SASL/SCRAM-SHA-256 authentication — setup, user management
- ACLs — topic/group-level authorization, wildcard, deny rules
- TLS encryption in transit — certificate setup, broker/client config
- Hands-on: secure Kafka cluster với SASL/SCRAM + TLS + ACLs

### 🟡 Should Learn (nếu còn thời gian)
- mTLS (mutual TLS) — certificate-based authentication
- Quotas — produce/consume/request rate limiting per user
- Audit logging — track who did what
- Topic naming conventions cho multi-tenancy

### 🟢 Optional Deep Dive
- SASL/OAUTHBEARER — OAuth 2.0 integration (Kafka 2.0+)
- Delegation tokens — short-lived tokens cho distributed apps
- Encryption at rest — disk encryption strategies
- RBAC (Role-Based Access Control) — Confluent Platform feature
- KIP-11: Authorization Interface extensibility

---

## 4. Lý thuyết (Theory)

### 4.1 Kafka Security Model — Defense in Depth

#### WHY — Tại sao Kafka cần Security?

```
KAFKA ATTACK VECTORS:

  ┌─────────────────────────────────────────────────────────┐
  │                   WITHOUT SECURITY                       │
  │                                                         │
  │  ❶ Unauthorized Access:                                 │
  │     Bất kỳ ai biết broker address → produce/consume     │
  │     → Attacker inject malicious messages                │
  │     → Attacker đọc sensitive data (PII, financial)      │
  │                                                         │
  │  ❷ Data Interception (Man-in-the-Middle):               │
  │     Network traffic unencrypted → wireshark → read data │
  │     → Passwords, credit cards, personal info exposed    │
  │                                                         │
  │  ❸ Spoofing:                                            │
  │     Attacker pretend to be legitimate service           │
  │     → Produce fake orders, fake payments                │
  │                                                         │
  │  ❹ Data Tampering:                                      │
  │     Modify messages in transit                          │
  │     → Change amount, change recipient                   │
  │                                                         │
  │  ❺ Denial of Service:                                   │
  │     Flood broker với garbage data                       │
  │     → Disk full, CPU exhaustion, legitimate traffic     │
  │       can't process                                     │
  │                                                         │
  │  ❻ Privilege Escalation:                                │
  │     Service A chỉ cần đọc topic X                      │
  │     → Nhưng cũng có thể write to topic Y, delete Z     │
  └─────────────────────────────────────────────────────────┘


DEFENSE IN DEPTH — 4 Layers:

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  Layer 1: NETWORK SECURITY                              │
  │  ├─ VPC / Private network                               │
  │  ├─ Security groups / Firewall rules                    │
  │  ├─ Kafka port (9092) chỉ accessible từ internal       │
  │  └─ Separate listener cho internal vs external          │
  │                                                         │
  │  Layer 2: AUTHENTICATION (who are you?)                 │
  │  ├─ SASL/SCRAM — username/password                      │
  │  ├─ mTLS — certificate-based                            │
  │  ├─ SASL/OAUTHBEARER — OAuth 2.0                        │
  │  └─ SASL/GSSAPI — Kerberos (enterprise)                │
  │                                                         │
  │  Layer 3: AUTHORIZATION (what can you do?)              │
  │  ├─ ACLs — fine-grained topic/group permissions         │
  │  ├─ Super users — admin access                          │
  │  └─ RBAC — role-based (Confluent Platform)              │
  │                                                         │
  │  Layer 4: ENCRYPTION (protect data)                     │
  │  ├─ TLS in-transit — encrypt network traffic            │
  │  ├─ Encryption at rest — encrypt data on disk           │
  │  └─ Field-level encryption — encrypt sensitive fields   │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

### 4.2 Authentication — SASL Mechanisms

#### WHAT — SASL Overview

```
SASL = Simple Authentication and Security Layer

  Kafka hỗ trợ 4 SASL mechanisms:

  ┌─────────────────────────────────────────────────────────────┐
  │ Mechanism        │ How it works           │ When to use      │
  ├──────────────────┼────────────────────────┼──────────────────┤
  │ SASL/PLAIN       │ Username + password    │ Dev/test only!   │
  │                  │ (plaintext over wire)  │ MUST use with TLS│
  │                  │                        │                  │
  │ SASL/SCRAM-256   │ Salted Challenge       │ Production       │
  │ SASL/SCRAM-512   │ Response Auth          │ (recommended)    │
  │                  │ (password never sent)  │                  │
  │                  │                        │                  │
  │ mTLS             │ Client certificate     │ Service-to-      │
  │ (SASL not needed)│ verified by broker     │ service (zero    │
  │                  │                        │ secret in config)│
  │                  │                        │                  │
  │ SASL/OAUTHBEARER │ OAuth 2.0 tokens       │ Cloud, SSO,      │
  │                  │ (JWT)                  │ centralized auth │
  │                  │                        │                  │
  │ SASL/GSSAPI      │ Kerberos tickets       │ Enterprise       │
  │                  │ (Active Directory)     │ (legacy Hadoop)  │
  └─────────────────────────────────────────────────────────────┘
```

#### HOW — SASL/SCRAM Deep Dive

```
SCRAM = Salted Challenge Response Authentication Mechanism

  WHY SCRAM over PLAIN?
  
  PLAIN:
  Client → Broker: "username=alice, password=secret123"
  → Password sent in CLEAR TEXT over network!
  → Without TLS → anyone sniffing → got password
  → With TLS → transit is protected, nhưng default JAAS config vẫn chứa secrets server-side
  → Chỉ dùng PLAIN khi đã có TLS, secret rotation, và external secret management rõ ràng
  
  SCRAM:
  1. Server stores: salt + iterations + ServerKey + StoredKey
     (NOT the password itself!)
  2. Client proves it knows password WITHOUT sending it:
  
  Client ──── ClientFirstMessage ──────► Broker
         (username, client nonce)
  
  Client ◄─── ServerFirstMessage ──────  Broker
         (server nonce, salt, iterations)
  
  Client ──── ClientFinalMessage ──────► Broker
         (proof = HMAC(password + salt + nonces))
  
  Client ◄─── ServerFinalMessage ──────  Broker
         (server proof — mutual authentication!)
  
  → Password NEVER leaves client
  → Even if broker compromised → password not exposed
  → Mutual auth: client verifies server too


SCRAM USER MANAGEMENT:

  # Create user
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --add-config 'SCRAM-SHA-256=[iterations=8192,password=alice-secret]' \
    --entity-type users --entity-name alice

  # List users  
  kafka-configs --bootstrap-server localhost:9092 \
    --describe --entity-type users

  # Delete user
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --delete-config 'SCRAM-SHA-256' \
    --entity-type users --entity-name alice

  ⚠️ SCRAM credentials stored as salted verifier data in ZooKeeper/KRaft metadata
  → Replicated across cluster → HA
  → Không phải plaintext password, nhưng vẫn là sensitive metadata cần backup/encryption/audit
```

#### mTLS — Certificate-based Authentication

```
mTLS (mutual TLS):

  Normal TLS:  Client verifies Server certificate
  mTLS:        BOTH verify each other's certificate

  ┌──────────┐                    ┌──────────┐
  │  Client   │                    │  Broker   │
  │           │                    │           │
  │ Has:      │                    │ Has:      │
  │ - Client  │    TLS Handshake   │ - Server  │
  │   cert    │◄──────────────────►│   cert    │
  │ - Client  │    Mutual auth     │ - Server  │
  │   key     │                    │   key     │
  │ - CA cert │                    │ - CA cert │
  │   (trust) │                    │ - Client  │
  └──────────┘                    │   CA cert │
                                  └──────────┘

  Certificate DN (Distinguished Name) = Identity
  CN=order-service, OU=payments, O=company
  
  Advantages:
  ✓ No passwords to manage/rotate
  ✓ No secrets in config files (cert = identity)
  ✓ Strong crypto (RSA 2048/4096, ECDSA)
  ✓ Mutual authentication (both sides verified)
  
  Disadvantages:
  ✗ Certificate management complexity (PKI infrastructure)
  ✗ Certificate rotation (before expiry!)
  ✗ More complex initial setup
  ✗ Each service needs unique cert
```

### 4.3 Authorization — ACLs

#### WHAT — Access Control Lists

```
ACL FORMAT:

  Principal (WHO) + Permission (WHAT) + Resource (WHERE) + Host (FROM WHERE)

  ┌──────────────────────────────────────────────────────────────┐
  │                        ACL Entry                              │
  │                                                              │
  │  Principal:   User:alice                                     │
  │  Permission:  ALLOW                                          │
  │  Operation:   READ                                           │
  │  Resource:    Topic:orders                                    │
  │  Pattern:     LITERAL (exact match)                          │
  │  Host:        * (any host)                                   │
  │                                                              │
  │  Meaning: "User alice is ALLOWED to READ from topic orders"  │
  └──────────────────────────────────────────────────────────────┘


RESOURCE TYPES:
  - Topic         (produce, consume, create, delete, describe, alter)
  - Group         (consumer group — read, describe)
  - Cluster       (create topics, alter configs, describe)
  - TransactionalId (exactly-once transactions)
  - DelegationToken (token management)

OPERATIONS:
  ┌──────────────────────────────────────────────────────────┐
  │ Operation     │ Resource │ Use case                      │
  ├───────────────┼──────────┼───────────────────────────────┤
  │ READ          │ Topic    │ Consumer fetch                │
  │ WRITE         │ Topic    │ Producer send                 │
  │ CREATE        │ Topic    │ Auto-create topics            │
  │ DELETE        │ Topic    │ Delete topics                 │
  │ DESCRIBE      │ Topic    │ Metadata, configs             │
  │ ALTER         │ Topic    │ Change topic configs          │
  │ READ          │ Group    │ Join consumer group           │
  │ DESCRIBE      │ Group    │ Describe consumer group       │
  │ WRITE         │ TransId  │ Begin/commit transactions     │
  │ CREATE        │ Cluster  │ Create topics on cluster      │
  │ ALTER         │ Cluster  │ Alter broker configs          │
  │ CLUSTER_ACTION│ Cluster  │ Inter-broker replication      │
  └──────────────────────────────────────────────────────────┘

PATTERN TYPES:
  - LITERAL:  exact match  → Topic:orders (chỉ topic "orders")
  - PREFIXED: prefix match → Topic:orders- (match "orders-*")
  
  Ví dụ: PREFIXED "team-payments-" → match:
    team-payments-orders
    team-payments-refunds  
    team-payments-invoices
```

#### HOW — ACL Commands

```bash
# === PRODUCER ACLs ===
# Allow user "order-service" to WRITE to topic "orders"
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:order-service \
  --operation Write \
  --topic orders

# Allow user "order-service" to DESCRIBE topic (needed for metadata)
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:order-service \
  --operation Describe \
  --topic orders

# === CONSUMER ACLs ===
# Allow user "payment-service" to READ from topic "orders"
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:payment-service \
  --operation Read \
  --topic orders

# Allow user "payment-service" to use consumer group "payment-group"
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:payment-service \
  --operation Read \
  --group payment-group

# === TRANSACTIONAL PRODUCER ACLs ===
# For exactly-once processing
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:order-service \
  --operation Write --operation Describe \
  --transactional-id order-service-txn

# === PREFIXED ACLs (multi-tenancy) ===
# Allow team-payments to access all topics starting with "payments-"
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:team-payments \
  --operation Read --operation Write --operation Describe \
  --topic payments- \
  --resource-pattern-type prefixed

# Allow team-payments to use consumer groups starting with "payments-"
kafka-acls --bootstrap-server localhost:9092 \
  --add --allow-principal User:team-payments \
  --operation Read --operation Describe \
  --group payments- \
  --resource-pattern-type prefixed

# === DENY ACLs ===
# Deny user "intern" from writing to topic "production-orders"
kafka-acls --bootstrap-server localhost:9092 \
  --add --deny-principal User:intern \
  --operation Write \
  --topic production-orders

# === LIST ACLs ===
kafka-acls --bootstrap-server localhost:9092 --list

# === REMOVE ACLs ===
kafka-acls --bootstrap-server localhost:9092 \
  --remove --allow-principal User:old-service \
  --operation Read \
  --topic orders
```

```
ACL EVALUATION ORDER:

  1. If user = super.user → ALLOW (bypass all ACLs)
  2. Check DENY rules → if match → DENY
  3. Check ALLOW rules → if match → ALLOW
  4. If no ACL matches:
     - allow.everyone.if.no.acl.found = false → DENY (default hiện hành)
     - allow.everyone.if.no.acl.found = true → ALLOW cho resource chưa có ACL
  
  ⚠️ CRITICAL: production phải giữ deny-by-default.
  → Set rõ ràng: allow.everyone.if.no.acl.found=false
  → Không bật true để "đỡ lỗi" trong rollout; hãy tạo explicit ACLs trước khi deploy service
  
  DENY takes precedence over ALLOW:
  If DENY(User:alice, Write, Topic:orders)
  AND ALLOW(User:alice, Write, Topic:orders)
  → Result: DENY (DENY wins!)
```

### 4.4 Encryption — TLS In-Transit

```
TLS SETUP COMPONENTS:

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  Certificate Authority (CA):                            │
  │  ├─ Root of trust                                       │
  │  ├─ Signs broker + client certificates                  │
  │  └─ Can be internal (self-signed) or external           │
  │                                                         │
  │  Broker Keystore:                                       │
  │  ├─ Contains broker's private key + certificate         │
  │  ├─ Format: JKS or PKCS12                               │
  │  └─ Each broker has UNIQUE cert (CN=broker hostname)    │
  │                                                         │
  │  Broker Truststore:                                     │
  │  ├─ Contains CA certificate(s) to trust                 │
  │  ├─ Used to verify client certificates (mTLS)           │
  │  └─ Shared across all brokers                           │
  │                                                         │
  │  Client Truststore:                                     │
  │  ├─ Contains CA certificate                             │
  │  └─ Used to verify broker certificate                   │
  │                                                         │
  │  Client Keystore (mTLS only):                           │
  │  ├─ Contains client's private key + certificate         │
  │  └─ Each service has UNIQUE cert                        │
  │                                                         │
  └─────────────────────────────────────────────────────────┘


KAFKA LISTENERS (multiple protocols):

  ┌────────────────────────────────────────────────────────────┐
  │  Broker Configuration:                                     │
  │                                                           │
  │  listeners=                                               │
  │    INTERNAL://0.0.0.0:9092,        ← inter-broker (SASL)  │
  │    EXTERNAL_SASL://0.0.0.0:9093,   ← clients (SASL+TLS)  │
  │    EXTERNAL_MTLS://0.0.0.0:9094    ← clients (mTLS)       │
  │                                                           │
  │  listener.security.protocol.map=                          │
  │    INTERNAL:SASL_PLAINTEXT,                               │
  │    EXTERNAL_SASL:SASL_SSL,                                │
  │    EXTERNAL_MTLS:SSL                                      │
  │                                                           │
  │  inter.broker.listener.name=INTERNAL                      │
  │                                                           │
  │  Protocol Options:                                        │
  │  - PLAINTEXT:      no auth, no encryption (dev only!)     │
  │  - SSL:            TLS encryption + optional mTLS auth    │
  │  - SASL_PLAINTEXT: SASL auth, no encryption               │
  │  - SASL_SSL:       SASL auth + TLS encryption (production)│
  └────────────────────────────────────────────────────────────┘


TLS PERFORMANCE IMPACT:

  ┌─────────────────────────────────────────────────────────┐
  │ Config              │ Throughput Impact │ Latency Impact │
  ├─────────────────────┼──────────────────┼────────────────┤
  │ PLAINTEXT (no TLS)  │ Baseline         │ Baseline       │
  │ SSL (TLS 1.2)       │ -10% to -20%     │ +1-3ms         │
  │ SSL (TLS 1.3)       │ -5% to -15%      │ +0.5-2ms       │
  │ SASL_SSL            │ -15% to -25%     │ +2-5ms         │
  └─────────────────────────────────────────────────────────┘
  
  TLS 1.3 performance improvements:
  - 1-RTT handshake (vs 2-RTT in TLS 1.2)
  - 0-RTT resumption (session tickets)
  - More efficient ciphers (ChaCha20, AES-GCM)
  
  → ALWAYS use TLS in production
  → Performance impact acceptable (5-15%)
  → Security benefit >>> performance cost
```

### 4.5 Multi-tenancy — Quotas & Isolation

#### WHY — Shared Cluster Challenges

```
MULTI-TENANCY CHALLENGES:

  Shared Kafka cluster, 5 teams:
  
  ┌─────────────────────────────────────────────────────────┐
  │                  Shared Kafka Cluster                     │
  │                                                         │
  │  Team Payments:    50 MB/s (mission critical!)          │
  │  Team Analytics:   200 MB/s (batch processing)          │
  │  Team Logging:     100 MB/s (high volume)               │
  │  Team Mobile:      10 MB/s (low volume)                 │
  │  Team ML:          50 MB/s (bursty — training jobs)     │
  │                                                         │
  │  Without isolation:                                     │
  │  Team ML kicks off training → 500 MB/s burst!           │
  │  → Broker saturated                                     │
  │  → Team Payments p99 latency: 5ms → 500ms!             │
  │  → Order processing delayed → revenue impact!          │
  └─────────────────────────────────────────────────────────┘


KAFKA MULTI-TENANCY MECHANISMS:

  1. QUOTAS — Rate limiting per user/client
  2. TOPIC NAMING CONVENTIONS — Namespace isolation
  3. ACLs — Permission isolation
  4. SEPARATE LISTENERS — Network isolation
  5. DEDICATED CLUSTERS — Full isolation (expensive)
```

#### HOW — Quotas

```
QUOTA TYPES:

  1. producer_byte_rate — max bytes/sec a user can PRODUCE
  2. consumer_byte_rate — max bytes/sec a user can CONSUME  
  3. request_percentage — max % of broker I/O thread time

  Quotas apply PER BROKER (not cluster-wide!)
  → User quota 10 MB/s + 3 brokers → effective 30 MB/s cluster-wide


SET QUOTAS:

  # Per user quota
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --add-config 'producer_byte_rate=10485760,consumer_byte_rate=20971520' \
    --entity-type users --entity-name team-analytics
  # team-analytics: max 10 MB/s produce, 20 MB/s consume per broker

  # Per client-id quota (for unauthenticated or shared users)
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --add-config 'producer_byte_rate=5242880' \
    --entity-type clients --entity-name analytics-client
  
  # Default quota for ALL users (catch-all)
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --add-config 'producer_byte_rate=5242880,consumer_byte_rate=10485760' \
    --entity-type users --entity-default

  # Request percentage quota (prevent CPU hogging)
  kafka-configs --bootstrap-server localhost:9092 \
    --alter --add-config 'request_percentage=25' \
    --entity-type users --entity-name team-ml
  # team-ml: max 25% of broker I/O thread time

  # Describe quotas
  kafka-configs --bootstrap-server localhost:9092 \
    --describe --entity-type users


QUOTA ENFORCEMENT:

  When client exceeds quota → Kafka THROTTLES (not rejects):
  
  ┌──────────────────────────────────────────────────────┐
  │ Client sends 20 MB/s, quota = 10 MB/s                │
  │                                                      │
  │ Broker response includes:                            │
  │   throttle_time_ms = X                               │
  │                                                      │
  │ Client MUST wait X ms before sending next request    │
  │ → Effectively limits to 10 MB/s                      │
  │ → JMX metric: produce-throttle-time-avg              │
  │                                                      │
  │ Client sees:                                         │
  │ - Increased latency (waiting)                        │
  │ - buffer.memory may fill up                          │
  │ - Eventually: TimeoutException if buffer full        │
  └──────────────────────────────────────────────────────┘
```

#### Topic Naming Conventions

```
TOPIC NAMING FOR MULTI-TENANCY:

  Pattern: {team}.{domain}.{event-type}.{version}
  
  Examples:
  payments.orders.created.v1
  payments.orders.completed.v1
  analytics.clickstream.page-view.v2
  logging.application.error.v1
  ml.features.user-embedding.v1

  Alternative pattern: {environment}.{team}.{topic}
  prod.payments.orders
  staging.payments.orders

  Benefits:
  ✓ Visual namespace separation
  ✓ ACL prefixed rules: payments.* → team payments only
  ✓ Monitoring: group metrics by team prefix
  ✓ Quota can align with naming (user=team name)


TOPIC NAMING + ACL STRATEGY:

  # Team payments owns all topics starting with "payments."
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:team-payments \
    --operation All \
    --topic payments. \
    --resource-pattern-type prefixed

  # Team analytics can READ (but NOT write) payments topics
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:team-analytics \
    --operation Read --operation Describe \
    --topic payments. \
    --resource-pattern-type prefixed

  # Team analytics owns analytics topics
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:team-analytics \
    --operation All \
    --topic analytics. \
    --resource-pattern-type prefixed
```

### 4.6 Audit Logging

```
AUDIT LOGGING — Track WHO did WHAT:

  Kafka built-in: Authorizer logs (log4j)
  
  # server.properties
  # Log all authorization decisions
  log4j.logger.kafka.authorizer.logger=INFO
  
  # Output format:
  # Principal = User:alice, 
  # Operation = WRITE, 
  # Resource = Topic:orders, 
  # Result = ALLOWED/DENIED
  
  
  For production audit trail:
  
  ┌─────────────────────────────────────────────────────────┐
  │ Approach 1: Authorizer logs → ELK stack                  │
  │ ├─ Parse Kafka logs                                     │
  │ ├─ Send to Elasticsearch                                │
  │ ├─ Kibana dashboard for audit queries                   │
  │ └─ Alert on DENIED operations                           │
  │                                                         │
  │ Approach 2: Custom Authorizer (KIP-11)                  │
  │ ├─ Implement Authorizer interface                       │
  │ ├─ Log to dedicated audit topic                         │
  │ ├─ Structured JSON format                               │
  │ └─ Real-time alerting on suspicious activity            │
  │                                                         │
  │ Approach 3: Confluent Audit Logs (commercial)           │
  │ ├─ Built-in structured audit logging                    │
  │ ├─ Dedicated audit log topic                            │
  │ ├─ Integration with SIEM tools                          │
  │ └─ Compliance-ready (SOC2, HIPAA, PCI-DSS)              │
  └─────────────────────────────────────────────────────────┘

  WHAT TO AUDIT:
  - Authentication failures (brute force detection)
  - Authorization denials (permission misconfig or attack)
  - Topic creation/deletion (schema changes)
  - Config changes (quota, ACL modifications)
  - Administrative operations (user management)
```

---

## 5. Trade-off Analysis

### Authentication Mechanism Selection

| Tiêu chí | SASL/SCRAM | mTLS | OAUTHBEARER |
|----------|-----------|------|-------------|
| Setup complexity | Trung bình | Cao (PKI) | Cao (OAuth server) |
| Credential type | Username/password | Certificate | JWT token |
| Rotation | Password change | Cert renewal | Token refresh (auto) |
| Secret in config | Yes (password) | No (cert file) | No (token endpoint) |
| Centralized mgmt | Kafka internal | PKI/CA | OAuth/OIDC server |
| Performance | Nhanh | Nhanh (after handshake) | Nhanh (token cache) |
| Best for | Most production | Service-to-service | Cloud, SSO |
| Ops overhead | Thấp | Trung bình (cert mgmt) | Trung bình (OAuth infra) |

### Multi-tenancy Isolation Levels

| Level | Method | Isolation | Cost | Use Case |
|-------|--------|-----------|------|----------|
| Namespace | Topic naming + ACLs | Logical | Thấp | Same team, different services |
| User/Quota | SASL users + quotas | Logical + Rate | Thấp | Cross-team shared cluster |
| Listener | Separate listeners | Network | Trung bình | Internal vs external |
| Dedicated | Separate clusters | Full | Cao | Compliance, critical workloads |

### Encryption Trade-offs

| Config | Security | Performance | Complexity |
|--------|----------|-------------|-----------|
| PLAINTEXT | None | Best | Lowest |
| SASL_PLAINTEXT | Auth only | Good | Low |
| SSL (TLS) | Encrypt only | -10-15% | Medium |
| SASL_SSL | Auth + Encrypt | -15-25% | Medium-High |
| SASL_SSL + mTLS | Mutual auth + Encrypt | -15-25% | High |

---

## 6. Best Practices & Common Pitfalls

### Best Practices

```
1. PRODUCTION MINIMUM: SASL_SSL (auth + encryption)
   → SASL/SCRAM-SHA-256 (or 512) for authentication
   → TLS 1.3 for encryption
   → ACLs with allow.everyone.if.no.acl.found=false

2. SEPARATE LISTENERS for different trust levels
   listeners=
     INTERNAL://0.0.0.0:9092,     # inter-broker (high trust)
     CLIENT://0.0.0.0:9093         # client connections
   → Client connections PHẢI dùng SASL_SSL hoặc SSL/mTLS
   → Inter-broker PLAINTEXT/SASL_PLAINTEXT chỉ acceptable trong lab isolated; production nên encrypt cả east-west traffic nếu network không được kiểm soát chặt

3. ACL STRATEGY: deny-by-default + explicit allow
   → allow.everyone.if.no.acl.found=false
   → Create ACLs cho EVERY service BEFORE deploying
   → Use PREFIXED patterns cho team namespaces
   → Super users chỉ cho admin tools, KHÔNG cho services

4. QUOTAS cho MỌI tenant (even trusted teams)
   → Prevent accidental resource exhaustion
   → Default quota cho unrecognized users (catch-all)
   → Set request_percentage để prevent CPU monopoly

5. CERTIFICATE ROTATION plan (mTLS)
   → Cert expiry = production outage nếu không rotate!
   → Automate với cert-manager (K8s) hoặc Vault
   → Monitor cert expiry: alert 30 days trước

6. AUDIT everything in production
   → Log all DENIED operations → detect attacks/misconfig
   → Log topic creation/deletion → track schema changes
   → Alert on authentication failures → brute force detection
```

### Common Pitfalls

```
❌ PITFALL 1: SASL/PLAIN without TLS hoặc quản lý secret cẩu thả
   Sai:  security.protocol=SASL_PLAINTEXT with PLAIN mechanism
   Đúng: security.protocol=SASL_SSL + secret manager/rotation, hoặc ưu tiên SCRAM/mTLS
   Tại sao: PLAIN without TLS exposes password in transit; PLAIN with TLS vẫn để lại rủi ro lưu trữ/rotation server-side

❌ PITFALL 2: Bật allow.everyone.if.no.acl.found=true để "dễ test"
   Sai:  Deploy ACLs MỘT SỐ services, quên set flag
   Đúng: Giữ false (deny-by-default) và tạo ACL tối thiểu cho từng principal
   Tại sao: Nếu true, resource chưa có ACL sẽ mở cho mọi authenticated principal
   → Default hiện hành là deny; đừng tự mở rộng blast radius

❌ PITFALL 3: Super user cho application services
   Sai:  super.users=User:order-service,User:payment-service
   Đúng: super.users=User:admin (admin tool only)
   Tại sao: Super user bypasses ALL ACLs
   → Compromised service = full cluster access

❌ PITFALL 4: Same credentials across environments
   Sai:  Dev/staging/prod dùng cùng username/password
   Đúng: Different credentials per environment
   Tại sao: Dev credentials leak → production compromised

❌ PITFALL 5: No quotas → noisy neighbor
   Sai:  Shared cluster, no quotas
   Đúng: Set default quotas + per-team quotas
   Tại sao: 1 team's burst → impacts ALL teams
   → Quá thường gặp → preventable

❌ PITFALL 6: Certificate expired → production down
   Sai:  Generate certs with 1 year expiry, forget to renew
   Đúng: Automate renewal, alert 30+ days before expiry
   Tại sao: TLS handshake fails → ALL connections fail → outage
```

---

## 7. Performance Considerations

### Security Overhead Benchmarks

```
PERFORMANCE IMPACT (single broker, comparable hardware):

  ┌────────────────────────────────────────────────────────┐
  │ Protocol         │ Throughput   │ Latency (p99) │ CPU  │
  ├──────────────────┼──────────────┼───────────────┼──────┤
  │ PLAINTEXT        │ 200K msg/s   │ 5ms           │ 30%  │
  │ SASL_PLAINTEXT   │ 190K msg/s   │ 6ms           │ 32%  │
  │ SSL (TLS 1.2)    │ 170K msg/s   │ 8ms           │ 45%  │
  │ SSL (TLS 1.3)    │ 180K msg/s   │ 7ms           │ 40%  │
  │ SASL_SSL (SCRAM) │ 160K msg/s   │ 10ms          │ 48%  │
  │ SASL_SSL (mTLS)  │ 165K msg/s   │ 9ms           │ 46%  │
  └────────────────────────────────────────────────────────┘

  KEY OBSERVATIONS:
  - TLS encryption: ~10-15% throughput reduction
  - SASL authentication: ~5% additional reduction
  - Combined: ~15-20% total overhead
  - CPU increase: significant (encryption/decryption)
  - TLS 1.3 meaningfully better than TLS 1.2
  
  OPTIMIZATION:
  - Use TLS 1.3 (faster handshake, better ciphers)
  - Connection pooling (amortize handshake cost)
  - Increase batch size (fewer requests = fewer TLS operations)
  - Hardware acceleration (AES-NI instructions on modern CPUs)
  - Adjust ssl.engine.factory.class for better performance
```

---

## 8. Hands-on Lab

### 8.1 Setup — Secure Kafka Cluster

```bash
# Create working directory
mkdir -p kafka-security-lab/certs
cd kafka-security-lab
```

```bash
#!/bin/bash
# generate-certs.sh — Generate CA + broker + client certificates

CERTS_DIR="./certs"
PASSWORD="kafka-security-lab"
VALIDITY=365

mkdir -p $CERTS_DIR

# 1. Create Certificate Authority (CA)
echo "--- Creating CA ---"
openssl req -new -x509 -keyout $CERTS_DIR/ca-key.pem \
  -out $CERTS_DIR/ca-cert.pem -days $VALIDITY \
  -subj "/CN=Kafka-Security-CA/OU=Lab/O=Learning" \
  -passout pass:$PASSWORD

# 2. Create Broker Keystore + Certificate
echo "--- Creating Broker Keystore ---"
keytool -keystore $CERTS_DIR/kafka.broker.keystore.jks \
  -alias broker -validity $VALIDITY -genkey -keyalg RSA -keysize 2048 \
  -dname "CN=localhost,OU=Kafka,O=Learning" \
  -storepass $PASSWORD -keypass $PASSWORD \
  -ext SAN=DNS:localhost,DNS:kafka,IP:127.0.0.1

# 3. Create CSR (Certificate Signing Request)
keytool -keystore $CERTS_DIR/kafka.broker.keystore.jks \
  -alias broker -certreq -file $CERTS_DIR/broker-csr.pem \
  -storepass $PASSWORD -keypass $PASSWORD \
  -ext SAN=DNS:localhost,DNS:kafka,IP:127.0.0.1

# 4. Sign broker certificate with CA
openssl x509 -req -CA $CERTS_DIR/ca-cert.pem \
  -CAkey $CERTS_DIR/ca-key.pem \
  -in $CERTS_DIR/broker-csr.pem \
  -out $CERTS_DIR/broker-signed.pem \
  -days $VALIDITY -CAcreateserial \
  -passin pass:$PASSWORD \
  -extfile <(printf "subjectAltName=DNS:localhost,DNS:kafka,IP:127.0.0.1")

# 5. Import CA + signed cert into broker keystore
keytool -keystore $CERTS_DIR/kafka.broker.keystore.jks \
  -alias CARoot -importcert -file $CERTS_DIR/ca-cert.pem \
  -storepass $PASSWORD -noprompt

keytool -keystore $CERTS_DIR/kafka.broker.keystore.jks \
  -alias broker -importcert -file $CERTS_DIR/broker-signed.pem \
  -storepass $PASSWORD -noprompt

# 6. Create Broker Truststore (contains CA cert)
echo "--- Creating Broker Truststore ---"
keytool -keystore $CERTS_DIR/kafka.broker.truststore.jks \
  -alias CARoot -importcert -file $CERTS_DIR/ca-cert.pem \
  -storepass $PASSWORD -noprompt

# 7. Create Client Truststore
echo "--- Creating Client Truststore ---"
keytool -keystore $CERTS_DIR/kafka.client.truststore.jks \
  -alias CARoot -importcert -file $CERTS_DIR/ca-cert.pem \
  -storepass $PASSWORD -noprompt

echo "--- Certificates generated successfully ---"
ls -la $CERTS_DIR/
```

```yaml
# docker-compose.yml — KRaft + StandardAuthorizer security baseline
# Lưu ý: đây là baseline hiện đại thay cho ZooKeeper lab. PLAINTEXT admin listener
# chỉ dùng local bootstrap; production phải dùng mTLS/SASL_SSL cho admin.
version: '3.8'
services:
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports:
      - "9092:9092"    # ADMIN bootstrap, local lab only
      - "9093:9093"    # SASL_SSL (production clients)
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:9094"
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER

      # Multiple listeners
      KAFKA_LISTENERS: >-
        CONTROLLER://kafka:9094,
        INTERNAL://kafka:29092,
        ADMIN://0.0.0.0:9092,
        SASL_SSL://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: >-
        INTERNAL://kafka:29092,
        ADMIN://localhost:9092,
        SASL_SSL://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: >-
        CONTROLLER:PLAINTEXT,
        INTERNAL:PLAINTEXT,
        ADMIN:SASL_PLAINTEXT,
        SASL_SSL:SASL_SSL
      KAFKA_INTER_BROKER_LISTENER_NAME: INTERNAL

      # SASL Configuration
      KAFKA_SASL_ENABLED_MECHANISMS: PLAIN,SCRAM-SHA-256
      KAFKA_LISTENER_NAME_ADMIN_PLAIN_SASL_JAAS_CONFIG: >-
        org.apache.kafka.common.security.plain.PlainLoginModule required
        username="admin"
        password="admin-secret"
        user_admin="admin-secret";

      # SSL/TLS Configuration
      KAFKA_SSL_KEYSTORE_LOCATION: /etc/kafka/secrets/kafka.broker.keystore.jks
      KAFKA_SSL_KEYSTORE_PASSWORD: kafka-security-lab
      KAFKA_SSL_KEY_PASSWORD: kafka-security-lab
      KAFKA_SSL_TRUSTSTORE_LOCATION: /etc/kafka/secrets/kafka.broker.truststore.jks
      KAFKA_SSL_TRUSTSTORE_PASSWORD: kafka-security-lab
      KAFKA_SSL_ENDPOINT_IDENTIFICATION_ALGORITHM: ""

      # Authorization
      KAFKA_AUTHORIZER_CLASS_NAME: org.apache.kafka.metadata.authorizer.StandardAuthorizer
      KAFKA_ALLOW_EVERYONE_IF_NO_ACL_FOUND: "false"
      KAFKA_SUPER_USERS: "User:admin"

      # Other
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_NUM_PARTITIONS: 4
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"

      KAFKA_OPTS: >-
        -Djava.security.auth.login.config=/etc/kafka/kafka_jaas.conf
    volumes:
      - ./certs:/etc/kafka/secrets
      - ./config/kafka_jaas.conf:/etc/kafka/kafka_jaas.conf
      - ./client-configs:/etc/kafka/client-configs
```

```bash
# Create config directory
mkdir -p config
```

```
# config/kafka_jaas.conf
KafkaServer {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="admin"
    password="admin-secret";
};
```

```
# Không tạo User:ANONYMOUS superuser. Nếu lệnh admin báo authorization failed,
# bootstrap bằng principal admin qua ADMIN listener rồi thêm ACL tối thiểu.
```

### 8.2 Create SCRAM Users & ACLs

```bash
# Start cluster
bash generate-certs.sh
docker compose up -d

# Wait for broker to be ready
sleep 10

# Admin client config for ADMIN listener. Production should use mTLS/SASL_SSL admin access.
mkdir -p client-configs
cat > client-configs/admin.properties <<'EOF'
security.protocol=SASL_PLAINTEXT
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="admin" password="admin-secret";
EOF

# Add "--command-config client-configs/admin.properties" to all kafka-configs,
# kafka-topics and kafka-acls commands using localhost:9092 below.

# Create SCRAM users (via local ADMIN listener for bootstrap)
echo "--- Creating SCRAM users ---"

# Admin user
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'SCRAM-SHA-256=[iterations=8192,password=admin-secret]' \
  --entity-type users --entity-name admin

# Order service (producer)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'SCRAM-SHA-256=[iterations=8192,password=order-svc-pass]' \
  --entity-type users --entity-name order-service

# Payment service (consumer)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'SCRAM-SHA-256=[iterations=8192,password=payment-svc-pass]' \
  --entity-type users --entity-name payment-service

# Analytics service (consumer, limited)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'SCRAM-SHA-256=[iterations=8192,password=analytics-pass]' \
  --entity-type users --entity-name analytics-service

# List all users
echo "--- Users created ---"
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --describe --entity-type users


# Create topics
echo "--- Creating topics ---"
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic orders --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic payments --partitions 4 --replication-factor 1
  kafka-topics --bootstrap-server localhost:9092 --create \
    --topic analytics-events --partitions 4 --replication-factor 1
"


# Set up ACLs
echo "--- Setting up ACLs ---"

# order-service: WRITE to orders, READ payments
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:order-service \
    --operation Write --operation Describe \
    --topic orders

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:order-service \
    --operation Read --operation Describe \
    --topic payments

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:order-service \
    --operation Read \
    --group order-service-group
"

# payment-service: READ orders, WRITE payments
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:payment-service \
    --operation Read --operation Describe \
    --topic orders

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:payment-service \
    --operation Write --operation Describe \
    --topic payments

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:payment-service \
    --operation Read \
    --group payment-service-group
"

# analytics-service: READ ONLY from orders and payments
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:analytics-service \
    --operation Read --operation Describe \
    --topic orders

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:analytics-service \
    --operation Read --operation Describe \
    --topic payments

  kafka-acls --bootstrap-server localhost:9092 \
    --add --allow-principal User:analytics-service \
    --operation Read \
    --group analytics-group
"

# List all ACLs
echo "--- All ACLs ---"
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-acls --bootstrap-server localhost:9092 --list
```

### 8.3 Client Configuration Templates

```properties
# client-configs/order-service.properties
# Producer config for order-service via SASL_SSL

bootstrap.servers=localhost:9093
security.protocol=SASL_SSL

# SASL/SCRAM authentication
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="order-service" \
  password="order-svc-pass";

# TLS
ssl.truststore.location=./certs/kafka.client.truststore.jks
ssl.truststore.password=kafka-security-lab
ssl.endpoint.identification.algorithm=

# Producer settings
key.serializer=org.apache.kafka.common.serialization.StringSerializer
value.serializer=org.apache.kafka.common.serialization.StringSerializer
acks=all
enable.idempotence=true
```

```properties
# client-configs/payment-service.properties
# Consumer config for payment-service via SASL_SSL

bootstrap.servers=localhost:9093
security.protocol=SASL_SSL

# SASL/SCRAM authentication
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="payment-service" \
  password="payment-svc-pass";

# TLS
ssl.truststore.location=./certs/kafka.client.truststore.jks
ssl.truststore.password=kafka-security-lab
ssl.endpoint.identification.algorithm=

# Consumer settings
key.deserializer=org.apache.kafka.common.serialization.StringDeserializer
value.deserializer=org.apache.kafka.common.serialization.StringDeserializer
group.id=payment-service-group
auto.offset.reset=earliest
```

### 8.4 Test Security — Happy Path + Failure Scenarios

```bash
# Test 1: order-service PRODUCES to orders (ALLOWED)
echo "=== Test 1: order-service writes to orders (should SUCCEED) ==="
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  echo 'test-key:{\"orderId\":\"ORD-001\",\"amount\":100}' | \
  kafka-console-producer \
    --bootstrap-server localhost:9093 \
    --topic orders \
    --producer-property security.protocol=SASL_SSL \
    --producer-property sasl.mechanism=SCRAM-SHA-256 \
    --producer-property 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"order-service\" password=\"order-svc-pass\";' \
    --producer-property ssl.truststore.location=/etc/kafka/secrets/kafka.broker.truststore.jks \
    --producer-property ssl.truststore.password=kafka-security-lab \
    --producer-property ssl.endpoint.identification.algorithm= \
    --property parse.key=true \
    --property key.separator=:
"

# Test 2: analytics-service tries to WRITE to orders (DENIED!)
echo "=== Test 2: analytics-service writes to orders (should FAIL) ==="
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  echo 'hack:{\"malicious\":true}' | \
  kafka-console-producer \
    --bootstrap-server localhost:9093 \
    --topic orders \
    --producer-property security.protocol=SASL_SSL \
    --producer-property sasl.mechanism=SCRAM-SHA-256 \
    --producer-property 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"analytics-service\" password=\"analytics-pass\";' \
    --producer-property ssl.truststore.location=/etc/kafka/secrets/kafka.broker.truststore.jks \
    --producer-property ssl.truststore.password=kafka-security-lab \
    --producer-property ssl.endpoint.identification.algorithm= \
    --property parse.key=true \
    --property key.separator=:
"
# Expected: TopicAuthorizationException!

# Test 3: payment-service READS from orders (ALLOWED)
echo "=== Test 3: payment-service reads orders (should SUCCEED) ==="
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  timeout 5 kafka-console-consumer \
    --bootstrap-server localhost:9093 \
    --topic orders \
    --from-beginning \
    --consumer-property security.protocol=SASL_SSL \
    --consumer-property sasl.mechanism=SCRAM-SHA-256 \
    --consumer-property 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"payment-service\" password=\"payment-svc-pass\";' \
    --consumer-property ssl.truststore.location=/etc/kafka/secrets/kafka.broker.truststore.jks \
    --consumer-property ssl.truststore.password=kafka-security-lab \
    --consumer-property ssl.endpoint.identification.algorithm= \
    --consumer-property group.id=payment-service-group \
    2>/dev/null || true
"

# Test 4: Wrong password (AUTH FAILURE)
echo "=== Test 4: Wrong password (should FAIL auth) ==="
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  timeout 5 kafka-console-consumer \
    --bootstrap-server localhost:9093 \
    --topic orders \
    --from-beginning \
    --consumer-property security.protocol=SASL_SSL \
    --consumer-property sasl.mechanism=SCRAM-SHA-256 \
    --consumer-property 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"order-service\" password=\"wrong-password\";' \
    --consumer-property ssl.truststore.location=/etc/kafka/secrets/kafka.broker.truststore.jks \
    --consumer-property ssl.truststore.password=kafka-security-lab \
    --consumer-property ssl.endpoint.identification.algorithm= \
    --consumer-property group.id=test-group \
    2>&1 || true
"
# Expected: SaslAuthenticationException!

# Test 5: Unknown user (AUTH FAILURE)
echo "=== Test 5: Unknown user (should FAIL) ==="
docker exec -it $(docker ps -q -f name=kafka) bash -c "
  timeout 5 kafka-console-consumer \
    --bootstrap-server localhost:9093 \
    --topic orders \
    --from-beginning \
    --consumer-property security.protocol=SASL_SSL \
    --consumer-property sasl.mechanism=SCRAM-SHA-256 \
    --consumer-property 'sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"hacker\" password=\"any-pass\";' \
    --consumer-property ssl.truststore.location=/etc/kafka/secrets/kafka.broker.truststore.jks \
    --consumer-property ssl.truststore.password=kafka-security-lab \
    --consumer-property ssl.endpoint.identification.algorithm= \
    --consumer-property group.id=test-group \
    2>&1 || true
"
```

### 8.5 Set Quotas

```bash
# Set quotas for each team
echo "--- Setting Quotas ---"

# analytics-service: max 5 MB/s produce, 10 MB/s consume per broker
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'producer_byte_rate=5242880,consumer_byte_rate=10485760' \
  --entity-type users --entity-name analytics-service

# Default quota for unknown users: 1 MB/s (safety net)
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --alter --add-config 'producer_byte_rate=1048576,consumer_byte_rate=2097152' \
  --entity-type users --entity-default

# Describe all quotas
docker exec -it $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --describe --entity-type users

# Check broker logs for authorization events
docker logs $(docker ps -q -f name=kafka) 2>&1 | grep -i "auth" | tail -20
```

### 8.6 Verify Security End-to-End

Acceptance checklist trước khi coi lab pass:

- Anonymous/unauthenticated client bị deny; không có `User:ANONYMOUS` trong `super.users`.
- User đúng password nhưng thiếu ACL bị `TopicAuthorizationException`.
- Wrong password/unknown user bị `SaslAuthenticationException`.
- TLS hostname validation được bật trong production; lab chỉ tắt khi dùng self-signed cert không có SAN đúng.
- Quota test tạo được throttle metric/log, không chỉ tạo config trên giấy.

```bash
# Summary verification script
echo "╔══════════════════════════════════════════════════╗"
echo "║        KAFKA SECURITY VERIFICATION               ║"
echo "╠══════════════════════════════════════════════════╣"

# Check listeners
echo "║ Listeners:"
docker exec $(docker ps -q -f name=kafka) \
  kafka-broker-api-versions --bootstrap-server localhost:9093 \
  --command-config /dev/null 2>&1 | head -1 && echo "║  ✓ SASL_SSL listener responding" || echo "║  ✗ SASL_SSL listener not responding"

# Check users
echo "║"
echo "║ SCRAM Users:"
docker exec $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --describe --entity-type users 2>/dev/null | while read line; do
  echo "║  $line"
done

# Check ACLs
echo "║"
echo "║ ACL Count:"
ACL_COUNT=$(docker exec $(docker ps -q -f name=kafka) \
  kafka-acls --bootstrap-server localhost:9092 --list 2>/dev/null | grep -c "User:")
echo "║  $ACL_COUNT ACL entries configured"

# Check quotas
echo "║"
echo "║ Quotas:"
docker exec $(docker ps -q -f name=kafka) \
  kafka-configs --bootstrap-server localhost:9092 \
  --describe --entity-type users 2>/dev/null | grep "quota" | while read line; do
  echo "║  $line"
done

echo "╚══════════════════════════════════════════════════╝"
```

---

## 9. Tự kiểm tra (Self-Check Questions)

1. **SASL/PLAIN vs SASL/SCRAM: Tại sao PLAIN nguy hiểm hơn ngay cả khi dùng với TLS? Trong trường hợp nào PLAIN acceptable?**
   - Hint: PLAIN gửi password plaintext → broker STORE password plaintext. SCRAM: password never leaves client. PLAIN OK: internal network + TLS + dev.

2. **allow.everyone.if.no.acl.found=false (deny-by-default). Bạn tạo ACL cho service A. Service B (chưa có ACL) có truy cập topic production được không? Nếu bật true thì rủi ro đổi như thế nào?**
   - Hint: Với false, service B bị deny trừ khi có ACL rõ ràng. Nếu bật true, resource chưa có ACL có thể mở cho mọi authenticated principal.

3. **Team analytics có quota producer_byte_rate=5MB/s. Cluster có 3 brokers. Max throughput effective của team này?**
   - Hint: quota apply PER BROKER. 5 MB/s × 3 brokers = 15 MB/s. Nhưng phụ thuộc partition distribution.

4. **Bạn dùng mTLS. Certificate expires trong 2 ngày và bạn quên renew. Hậu quả?**
   - Hint: TLS handshake fail → ALL connections từ client đó fail → service DOWN.

5. **DENY ACL và ALLOW ACL cùng tồn tại cho 1 user trên 1 topic. Kết quả?**
   - Hint: DENY takes precedence ALWAYS. Order: super.user check → DENY rules → ALLOW rules.

6. **Cluster có 50 services, mỗi service cần ACLs riêng. Làm sao quản lý ACLs scalably?**
   - Hint: Prefixed ACLs + naming convention (team.service.*), automation scripts, GitOps.

7. **Performance giảm 20% sau khi enable SASL_SSL. Cách tối ưu mà KHÔNG giảm security?**
   - Hint: TLS 1.3, connection pooling, tăng batch size, hardware AES-NI.

---

## 10. Tài liệu tham khảo (References)

### Official Documentation
- [Kafka Security](https://kafka.apache.org/documentation/#security)
- [Kafka Authorization and ACLs](https://kafka.apache.org/documentation/#security_authz)
- [Kafka SSL/TLS Configuration](https://kafka.apache.org/documentation/#security_ssl)
- [Kafka SASL Configuration](https://kafka.apache.org/documentation/#security_sasl)
- [Kafka Quotas](https://kafka.apache.org/documentation/#design_quotas)

### Blog Posts & Articles
- [Confluent — Kafka Security Tutorial](https://docs.confluent.io/platform/current/security/security-tutorial.html)
- [Confluent — Role-Based Access Control](https://docs.confluent.io/platform/current/security/rbac/index.html)
- [Confluent — Kafka Multi-Tenancy](https://docs.confluent.io/platform/current/multi-dc-deployments/multi-tenancy.html)
- [Strimzi — Kafka Security on Kubernetes](https://strimzi.io/docs/operators/latest/configuring.html#security-str)

### Videos & Talks
- [Kafka Summit — Securing Apache Kafka](https://www.confluent.io/events/kafka-summit/)
- [Confluent Developer — Security Fundamentals](https://developer.confluent.io/courses/)
- [GOTO Conference — Security Best Practices for Event-Driven Architectures](https://www.youtube.com/results?search_query=kafka+security+best+practices)
