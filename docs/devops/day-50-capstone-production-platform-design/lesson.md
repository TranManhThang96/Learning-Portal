# Day 50: Capstone Project — Production Platform Design

## 1. Mục tiêu bài học

Sau capstone này, bạn sẽ:

1. **Thiết kế** được complete production-grade platform từ scratch tích hợp kiến thức từ 49 ngày trước.
2. **Tạo** được architecture diagram theo C4 model với đầy đủ layers (Context, Container, Component).
3. **Xây dựng** được skeleton implementation cho Kubernetes workloads, IaC, CI/CD, và observability.
4. **Viết** được ≥ 5 production runbooks cho critical incidents và operational procedures.
5. **Phân tích** được trade-offs giữa cost, performance, reliability, và security cho mỗi quyết định architecture.

---

## 2. Bối cảnh & Động lực

### Scenario: E-commerce Platform "NextShop"

**Business Context**:
- Startup B2C e-commerce, 2 năm tuổi
- Growing from 10K users/day to 100K users/day trong 6 tháng tới
- Preparing for first Black Friday event (expected 10x traffic)
- Seed funding: $2M, cần optimize cost
- Team: 15 engineers, 2 DevOps

**Technical Requirements**:

| Requirement | Value |
|------------|-------|
| **Microservices** | 6-7 services (see breakdown) |
| **Protocols** | REST (external) + gRPC (internal) |
| **Database** | PostgreSQL (primary) + Redis (cache) |
| **Message Queue** | Kafka (orders, notifications) |
| **SLA Target** | 99.95% availability (~21.9 min/month) |
| **Peak Traffic** | 10,000 RPS (Black Friday) |
| **Baseline Traffic** | 1,000 RPS |
| **Data Volume** | Current 100GB, projected 1TB by year-end |
| **Security** | PCI DSS Level 4 compliance (for payments) |
| **Budget** | < $15K/month cloud cost |
| **Regions** | Primary us-east-1, DR us-west-2 |

### Service Breakdown

| Service | Language | Dependencies | QPS (Peak) |
|---------|----------|--------------|------------|
| **api-gateway** | Go | All services | 10,000 |
| **user-service** | Go | PostgreSQL, Redis | 5,000 |
| **product-service** | Go | PostgreSQL, Redis | 8,000 |
| **order-service** | Go | PostgreSQL, Kafka | 2,000 |
| **payment-service** | Go | PostgreSQL, External (Stripe) | 1,000 |
| **inventory-service** | Go | PostgreSQL, Redis | 3,000 |
| **notification-worker** | Node.js | Kafka, SendGrid, Twilio | N/A (consumer) |

---

### Động lực production

Capstone này mô phỏng việc bạn phải trình bày một platform design trước CTO/SRE lead: không chỉ vẽ diagram, mà còn chứng minh vì sao quyết định đó đáp ứng SLA, peak traffic, security, DR, cost constraint và khả năng vận hành bởi team hiện tại.

Nếu làm sai, hậu quả thường không nằm ở một manifest Kubernetes riêng lẻ mà ở toàn bộ system: deploy không rollback được, observability không chỉ ra root cause, database restore không được test, hoặc cost tối ưu quá mức làm giảm reliability đúng lúc flash sale.

## 3. Kiến thức nền tảng

Capstone dùng lại 5 lớp kiến thức đã học:

| Layer | Cần nhớ | Artifact trong bài |
|-------|---------|--------------------|
| Application runtime | health check, graceful shutdown, config, secret | Kubernetes Deployment skeleton |
| Platform runtime | namespace, RBAC, NetworkPolicy, autoscaling, PDB | K8s manifests + Helm/Kustomize |
| Infrastructure | VPC, EKS, RDS, Redis, Kafka, backup storage | Terraform module skeleton |
| Delivery | test, scan, build, sign, deploy, rollback | GitHub Actions pipeline |
| Operations | metrics, logs, traces, alerts, runbooks, DR, cost | Observability, DR, FinOps, incident runbooks |

Nguyên tắc đọc capstone: mỗi quyết định phải trả lời được `why`, `failure mode`, `rollback`, `blast radius`, và `cost impact`. Một platform production-grade không phải là nhiều YAML hơn, mà là các constraint được thể hiện thành controls có thể verify.

---

## 4. Deep Dive — Architecture Design (C4 Model)

### Level 1: Context Diagram

```mermaid
graph TB
    USER[End User<br/>Web/Mobile]
    ADMIN[Admin<br/>Back-office]
    
    SYSTEM[NextShop Platform<br/>E-commerce SaaS]
    
    STRIPE[Stripe<br/>Payment Provider]
    SENDGRID[SendGrid<br/>Email Provider]
    TWILIO[Twilio<br/>SMS Provider]
    S3_EXT[AWS S3<br/>Product Images]
    CDN[CloudFront<br/>CDN]
    
    USER -->|HTTPS| CDN
    CDN --> SYSTEM
    ADMIN -->|HTTPS + MFA| SYSTEM
    
    SYSTEM -->|Payment API| STRIPE
    SYSTEM -->|Email API| SENDGRID
    SYSTEM -->|SMS API| TWILIO
    SYSTEM -->|Static assets| S3_EXT
    CDN -.->|cache| S3_EXT
```

### Level 2: Container Diagram

```mermaid
graph TB
    subgraph "AWS us-east-1 (Primary)"
        ALB[Application LB<br/>TLS termination]
        
        subgraph "EKS Cluster"
            API[API Gateway<br/>Go]
            USER[User Service<br/>Go]
            PROD[Product Service<br/>Go]
            ORDER[Order Service<br/>Go]
            PAY[Payment Service<br/>Go]
            INV[Inventory Service<br/>Go]
            NOTIF[Notification Worker<br/>Node.js]
        end
        
        RDS[(RDS PostgreSQL<br/>Multi-AZ Primary)]
        REDIS[(ElastiCache Redis<br/>Cluster mode)]
        MSK[MSK Kafka<br/>3 brokers]
        
        subgraph "Observability"
            PROM[Prometheus]
            GRAF[Grafana]
            LOKI[Loki]
            TEMPO[Tempo]
        end
    end
    
    subgraph "AWS us-west-2 (DR)"
        ALB_DR[ALB<br/>Standby]
        EKS_DR[EKS Cluster<br/>Minimal]
        RDS_DR[(RDS Read Replica<br/>Cross-region)]
    end
    
    R53[Route 53<br/>Failover]
    S3_BAK[S3 Backup<br/>Cross-region]
    
    R53 --> ALB
    R53 -.->|failover| ALB_DR
    ALB --> API
    API --> USER & PROD & ORDER & PAY & INV
    USER --> RDS & REDIS
    PROD --> RDS & REDIS
    ORDER --> RDS & MSK
    PAY --> RDS
    INV --> RDS & REDIS
    MSK --> NOTIF
    RDS --> S3_BAK
    RDS -.->|replication| RDS_DR
```

### Level 3: Component Diagram (Order Service)

```mermaid
graph LR
    subgraph "Order Service Pod"
        HTTP[HTTP Server<br/>gRPC :50051<br/>HTTP :8080]
        HANDLER[Order Handler]
        SAGA[Saga Coordinator]
        REPO[Repository Layer]
        METRICS[Prometheus Metrics]
        HEALTH[Health Check]
        
        HTTP --> HANDLER
        HANDLER --> SAGA
        SAGA --> REPO
        HANDLER --> METRICS
    end
    
    REPO -->|SQL| PG[(PostgreSQL)]
    SAGA -->|Publish| KAFKA[Kafka]
    SAGA -->|gRPC| INVENTORY[Inventory Service]
    SAGA -->|gRPC| PAYMENT[Payment Service]
```

---

## 5. Hands-on Example — Kubernetes Deployment Skeleton

### Local-first lab: tạo skeleton repo và verify bằng command

Các bước dưới đây không cần cloud account; mục tiêu là tạo cấu trúc deliverable có thể review, lint cơ bản, và cleanup được trong 10-15 phút.

```bash
mkdir -p nextshop-capstone/{apps/order-service,k8s/base,k8s/overlays/{staging,production},terraform/{modules/{vpc,eks,rds},environments/{staging,production}},docs/{runbooks,adr,observability,dr,cost}}

cat > nextshop-capstone/k8s/base/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- namespace.yaml
- order-service.yaml
commonLabels:
  app.kubernetes.io/part-of: nextshop
EOF

cat > nextshop-capstone/docs/deliverables-check.md <<'EOF'
# NextShop Capstone Deliverables

- [ ] C4 architecture diagram
- [ ] Kubernetes deployment skeleton
- [ ] Helm chart hoặc Kustomize structure
- [ ] Terraform module skeleton
- [ ] GitHub Actions pipeline skeleton
- [ ] Observability plan
- [ ] Deployment strategy + rollback
- [ ] Security plan
- [ ] DR plan
- [ ] Cost breakdown
- [ ] Top 5 incident runbooks
- [ ] Final review
EOF

find nextshop-capstone -maxdepth 2 -type d | sort
```

**Expected output**:

```text
nextshop-capstone
nextshop-capstone/apps
nextshop-capstone/apps/order-service
nextshop-capstone/docs
nextshop-capstone/docs/adr
nextshop-capstone/docs/cost
nextshop-capstone/docs/dr
nextshop-capstone/docs/observability
nextshop-capstone/docs/runbooks
nextshop-capstone/k8s
nextshop-capstone/k8s/base
nextshop-capstone/k8s/overlays
nextshop-capstone/terraform
nextshop-capstone/terraform/environments
nextshop-capstone/terraform/modules
```

**Verify**:

```bash
test -f nextshop-capstone/k8s/base/kustomization.yaml
test -f nextshop-capstone/docs/deliverables-check.md
grep -c '^- \\[ \\]' nextshop-capstone/docs/deliverables-check.md
```

**Expected output**:

```text
12
```

**Cleanup**:

```bash
rm -rf nextshop-capstone
```

### Namespace Structure

```yaml
# 01-namespaces.yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: nextshop-production
  labels:
    team: nextshop
    environment: production
    pod-security.kubernetes.io/enforce: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: nextshop-data
  labels:
    team: data
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: nextshop-monitoring
  labels:
    team: platform
```

### Order Service — Complete Production YAML

```yaml
# order-service.yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service
  namespace: nextshop-production
  labels:
    app: order-service
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: nextshop-production
  labels:
    app: order-service
    version: v1
    team: orders
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: order-service
      automountServiceAccountToken: false
      
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: order-service
              topologyKey: topology.kubernetes.io/zone
      
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: order-service
      
      containers:
      - name: order-service
        image: nextshop/order-service:1.0.0@sha256:abc123...
        imagePullPolicy: IfNotPresent
        
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: grpc
          containerPort: 50051
          protocol: TCP
        - name: metrics
          containerPort: 9090
          protocol: TCP
        
        env:
        - name: LOG_LEVEL
          value: "info"
        - name: ENVIRONMENT
          value: "production"
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://tempo.nextshop-monitoring.svc.cluster.local:4317"
        
        envFrom:
        - configMapRef:
            name: order-service-config
        - secretRef:
            name: order-service-secret
        
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        
        livenessProbe:
          httpGet:
            path: /healthz/live
            port: http
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /healthz/ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        
        startupProbe:
          httpGet:
            path: /healthz/startup
            port: http
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30  # 150s total
        
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
        
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /var/cache
      
      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir: {}
      
      terminationGracePeriodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: nextshop-production
  labels:
    app: order-service
spec:
  type: ClusterIP
  selector:
    app: order-service
  ports:
  - name: http
    port: 8080
    targetPort: http
  - name: grpc
    port: 50051
    targetPort: grpc
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
  namespace: nextshop-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service
  namespace: nextshop-production
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: order-service
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service
  namespace: nextshop-production
spec:
  podSelector:
    matchLabels:
      app: order-service
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 8080
    - protocol: TCP
      port: 50051
  - from:
    - namespaceSelector:
        matchLabels:
          name: nextshop-monitoring
    ports:
    - protocol: TCP
      port: 9090
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: inventory-service
    - podSelector:
        matchLabels:
          app: payment-service
    ports:
    - protocol: TCP
      port: 50051
  - to:
    - namespaceSelector:
        matchLabels:
          name: nextshop-data
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 9092  # Kafka
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

---

## 6. Helm Chart hoặc Kustomize Structure

Trong capstone này chọn **Kustomize** vì skeleton cần dễ đọc, ít templating, và phù hợp local-first review. Helm vẫn hợp lý nếu platform team muốn package chart dùng lại cho nhiều service/team.

### Kustomize layout

```text
k8s/
├── base/
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── order-service.yaml
│   ├── product-service.yaml
│   └── network-policy.yaml
└── overlays/
    ├── staging/
    │   ├── kustomization.yaml
    │   └── patch-replicas.yaml
    └── production/
        ├── kustomization.yaml
        ├── patch-resources.yaml
        └── patch-hpa.yaml
```

### Production overlay

```yaml
# k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: nextshop-production
resources:
- ../../base
patches:
- path: patch-resources.yaml
- path: patch-hpa.yaml
images:
- name: nextshop/order-service
  newName: 123456789.dkr.ecr.us-east-1.amazonaws.com/order-service
  digest: sha256:abc123...
commonLabels:
  environment: production
```

### Khi chọn Helm thay vì Kustomize

| Scenario | Chọn |
|----------|------|
| 2-5 service, ít biến thể giữa environments | Kustomize |
| Nhiều team cần reusable chart chuẩn hóa | Helm |
| Cần expose values contract cho self-service | Helm |
| Cần patch YAML vendor chart | Kustomize |

---

## 7. Infrastructure as Code Skeleton (Terraform)

### Directory Structure

```
terraform/
├── modules/
│   ├── vpc/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── eks/
│   ├── rds/
│   ├── elasticache/
│   └── msk/
├── environments/
│   ├── production/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── dr/
└── global/
    ├── iam/
    ├── route53/
    └── s3-backups/
```

### Core Infrastructure (production/main.tf)

```hcl
terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

provider "aws" {
  region = var.region
  
  default_tags {
    tags = {
      Project     = "nextshop"
      Environment = "production"
      ManagedBy   = "terraform"
      CostCenter  = "engineering"
    }
  }
}

# VPC
module "vpc" {
  source = "../../modules/vpc"
  
  name                = "nextshop-prod"
  cidr                = "10.0.0.0/16"
  azs                 = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets      = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  
  enable_nat_gateway  = true
  single_nat_gateway  = true  # Cost optimization: 1 NAT vs 3
  enable_vpn_gateway  = false
  
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
}

# EKS
module "eks" {
  source = "../../modules/eks"
  
  cluster_name    = "nextshop-prod"
  cluster_version = "1.29"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  eks_managed_node_groups = {
    # System nodes (always on-demand)
    system = {
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      min_size       = 2
      max_size       = 3
      desired_size   = 2
      labels = {
        workload = "system"
      }
      taints = [{
        key    = "workload"
        value  = "system"
        effect = "NO_SCHEDULE"
      }]
    }
    
    # Application nodes (spot + on-demand mix)
    application = {
      instance_types = ["m5.large", "m5.xlarge", "m5a.large", "m5a.xlarge"]
      capacity_type  = "SPOT"
      min_size       = 3
      max_size       = 20
      desired_size   = 3
    }
    
    # Baseline on-demand
    baseline = {
      instance_types = ["m5.large"]
      capacity_type  = "ON_DEMAND"
      min_size       = 2
      max_size       = 4
      desired_size   = 2
    }
  }
  
  cluster_addons = {
    vpc-cni    = { addon_version = "v1.16.0-eksbuild.1" }
    coredns    = { addon_version = "v1.10.1-eksbuild.6" }
    kube-proxy = { addon_version = "v1.29.0-eksbuild.1" }
    aws-ebs-csi-driver = { addon_version = "v1.26.0-eksbuild.1" }
  }
}

# RDS PostgreSQL
module "rds" {
  source = "../../modules/rds"
  
  identifier = "nextshop-prod"
  engine     = "postgres"
  engine_version = "16.1"
  instance_class = "db.r6g.large"
  allocated_storage     = 100
  max_allocated_storage = 500
  storage_encrypted     = true
  storage_type          = "gp3"
  
  db_name  = "nextshop"
  username = "nextshop_admin"
  manage_master_user_password = true
  
  multi_az               = true
  vpc_security_group_ids = [module.rds_sg.security_group_id]
  subnet_ids             = module.vpc.database_subnets
  
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "nextshop-prod-final"
  
  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = true
}

# ElastiCache Redis
module "redis" {
  source = "../../modules/elasticache"
  
  cluster_id         = "nextshop-prod"
  engine_version     = "7.1"
  node_type          = "cache.r6g.large"
  num_cache_clusters = 2
  
  automatic_failover_enabled = true
  multi_az_enabled           = true
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  
  subnet_group_name  = module.vpc.elasticache_subnet_group_name
  security_group_ids = [module.redis_sg.security_group_id]
}

# MSK Kafka
module "msk" {
  source = "../../modules/msk"
  
  cluster_name    = "nextshop-prod"
  kafka_version   = "3.5.1"
  
  number_of_broker_nodes = 3
  broker_node_group_info = {
    instance_type   = "kafka.m7g.large"
    client_subnets  = module.vpc.private_subnets
    security_groups = [module.msk_sg.security_group_id]
    storage_info = {
      ebs_storage_info = {
        volume_size = 100
      }
    }
  }
  
  encryption_info = {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit = {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
}

# S3 Cross-region backup
resource "aws_s3_bucket" "backups" {
  bucket = "nextshop-prod-backups"
}

resource "aws_s3_bucket_replication_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  role   = aws_iam_role.replication.arn
  
  rule {
    id     = "cross-region-dr"
    status = "Enabled"
    
    destination {
      bucket        = aws_s3_bucket.backups_dr.arn
      storage_class = "STANDARD_IA"
    }
  }
}
```

---

## 8. CI/CD Pipeline Skeleton (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Build & Deploy

on:
  push:
    branches: [main]
    paths:
    - 'services/order-service/**'
  pull_request:
    branches: [main]

permissions:
  id-token: write
  contents: read
  security-events: write

env:
  IMAGE_NAME: order-service
  REGISTRY: 123456789.dkr.ecr.us-east-1.amazonaws.com

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with:
        go-version: '1.22'
    - name: Lint
      run: |
        cd services/order-service
        go vet ./...
        go install github.com/golangci/golangci-lint/cmd/golangci-lint@v1.56.0
        golangci-lint run --timeout 5m

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
        ports:
        - 5432:5432
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
    - name: Test
      run: |
        cd services/order-service
        go test -v -race -coverprofile=coverage.out ./...
        go tool cover -func=coverage.out

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: SAST with Semgrep
      uses: returntocorp/semgrep-action@v1
    - name: Dependency scan with Trivy
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'
    - name: Upload SARIF
      uses: github/codeql-action/upload-sarif@v3
      with:
        sarif_file: 'trivy-results.sarif'

  build:
    runs-on: ubuntu-latest
    needs: [lint, test, security-scan]
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
      image-digest: ${{ steps.build.outputs.digest }}
    steps:
    - uses: actions/checkout@v4
    - name: Configure AWS
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::123456789:role/github-actions
        aws-region: us-east-1
    
    - name: Login to ECR
      uses: aws-actions/amazon-ecr-login@v2
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=sha,prefix=
          type=semver,pattern={{version}}
    
    - name: Build and push
      id: build
      uses: docker/build-push-action@v5
      with:
        context: services/order-service
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
    
    - name: Scan image
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ steps.meta.outputs.tags }}
        format: 'table'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
    
    - name: Sign image with Cosign
      run: |
        echo "${{ secrets.COSIGN_PRIVATE_KEY }}" > cosign.key
        cosign sign --key cosign.key ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${{ steps.build.outputs.digest }}

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'pull_request'
    environment: staging
    steps:
    - uses: actions/checkout@v4
    - name: Configure kubectl
      uses: aws-actions/configure-aws-credentials@v4
    - name: Deploy to staging
      run: |
        aws eks update-kubeconfig --name nextshop-staging
        kubectl set image deploy/order-service \
          order-service=${{ needs.build.outputs.image-tag }} \
          -n nextshop-staging
        kubectl rollout status deploy/order-service -n nextshop-staging --timeout=5m

  deploy-production:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: 
      name: production
      url: https://api.nextshop.com
    steps:
    - uses: actions/checkout@v4
    - name: Configure kubectl
      uses: aws-actions/configure-aws-credentials@v4
    
    - name: Deploy canary (10%)
      run: |
        aws eks update-kubeconfig --name nextshop-prod
        kubectl argo rollouts set image order-service \
          order-service=${{ needs.build.outputs.image-tag }} \
          -n nextshop-production
        kubectl argo rollouts get rollout order-service --watch -n nextshop-production
```

---

## 9. Observability Plan

### Metrics (Prometheus + Grafana)

```yaml
# Golden Signals cho mỗi service:
- rate(http_requests_total{service="order-service"}[5m])  # Traffic
- histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))  # Latency
- rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])  # Errors
- avg(container_cpu_usage_seconds_total{pod=~"order-service.*"})  # Saturation

# Business metrics:
- rate(orders_created_total[5m])
- rate(payment_success_total[5m]) / rate(payment_attempts_total[5m])
- histogram_quantile(0.95, order_total_amount_bucket)
```

### Logs (Loki)

```yaml
# Structured logging (JSON)
# All services emit:
{
  "timestamp": "2026-05-12T10:30:00Z",
  "level": "info",
  "service": "order-service",
  "trace_id": "abc123",
  "span_id": "def456",
  "user_id": "user-001",
  "message": "Order created",
  "order_id": "ord-123",
  "total_amount": 99.99
}

# Loki queries:
{service="order-service"} |= "ERROR" | json | line_format "{{.message}}"
{service="order-service"} | json | user_id="user-001"
```

### Traces (OpenTelemetry + Tempo)

```go
// In each service, instrument gRPC + HTTP + DB calls
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
)

tracer := otel.Tracer("order-service")
ctx, span := tracer.Start(ctx, "CreateOrder")
defer span.End()

span.SetAttributes(
    attribute.String("order.id", orderID),
    attribute.Float64("order.amount", amount),
)
```

### Dashboard Plan

| Dashboard | Audience | Panels bắt buộc |
|-----------|----------|-----------------|
| Executive SLA | CTO/PM/on-call lead | SLA monthly, error budget remaining, incidents, deployment frequency |
| Service Golden Signals | service owner | RPS, P50/P95/P99 latency, error rate, CPU/memory, pod restarts |
| Debug Drill-down | on-call engineer | trace latency breakdown, DB slow queries, Kafka lag, cache hit ratio, recent deploy markers |

### Alert Rules

```yaml
groups:
- name: slo-burn-rate
  rules:
  - alert: HighErrorRate
    expr: |
      (sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
       / sum(rate(http_requests_total[5m])) by (service)) > 0.01
    for: 5m
    labels:
      severity: warning
      runbook: https://runbooks.nextshop.com/high-error-rate
    annotations:
      summary: "High error rate on {{ $labels.service }}"
      
  - alert: HighLatency
    expr: |
      histogram_quantile(0.95,
        sum(rate(http_request_duration_seconds_bucket[5m])) by (service, le)
      ) > 1.0
    for: 10m
    labels:
      severity: warning
```

Alert coverage tối thiểu cho capstone:

1. `HighErrorRate`
2. `HighLatency`
3. `ServiceDown`
4. `PodCrashLooping`
5. `HPAAtMaxReplicas`
6. `DatabaseHighCPU`
7. `DatabaseSlowQueries`
8. `RedisLowHitRatio`
9. `KafkaConsumerLag`
10. `ErrorBudgetBurnFast`

---

## 10. Deployment Strategy

**Chosen: Canary Deployment với Argo Rollouts**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-service
spec:
  replicas: 3
  strategy:
    canary:
      canaryService: order-service-canary
      stableService: order-service-stable
      trafficRouting:
        istio:
          virtualService:
            name: order-service
      steps:
      - setWeight: 10
      - pause: {duration: 5m}
      - analysis:
          templates:
          - templateName: success-rate
          - templateName: latency
          args:
          - name: service-name
            value: order-service-canary
      - setWeight: 25
      - pause: {duration: 10m}
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
```

### Rollback Plan

```
Trigger rollback when:
1. Error rate > 2% for 5 minutes
2. Latency P95 > 1s for 10 minutes
3. Business metrics drop > 20%

Procedure:
kubectl argo rollouts abort order-service -n nextshop-production
kubectl argo rollouts undo order-service -n nextshop-production
```

---

## 11. Security & Reliability Considerations

### RBAC

```yaml
# Principle of least privilege
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: order-service
  namespace: nextshop-production
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  resourceNames: ["order-service-config", "order-service-secret"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: order-service
  namespace: nextshop-production
subjects:
- kind: ServiceAccount
  name: order-service
roleRef:
  kind: Role
  name: order-service
  apiGroup: rbac.authorization.k8s.io
```

### Secret Management

```yaml
# External Secrets Operator với AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: order-service-secret
  namespace: nextshop-production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: order-service-secret
  data:
  - secretKey: DB_PASSWORD
    remoteRef:
      key: prod/order-service/db-password
  - secretKey: KAFKA_PASSWORD
    remoteRef:
      key: prod/order-service/kafka-password
```

### Admission Control (Kyverno)

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-non-root
spec:
  validationFailureAction: Enforce
  rules:
  - name: validate-runAsNonRoot
    match:
      resources:
        kinds: [Pod]
    validate:
      message: "Pods must run as non-root"
      pattern:
        spec:
          securityContext:
            runAsNonRoot: true
```

### Image Scanning & Supply Chain

```yaml
# CI policy
image_scanning:
  tool: Trivy
  fail_on:
  - CRITICAL
  - HIGH
  required_artifacts:
  - SARIF upload to GitHub Security
  - signed image digest with Cosign
  - pinned deployment by digest, not mutable tag
```

Reliability controls đi kèm security:

- RBAC theo least privilege, không dùng cluster-admin cho app pipeline.
- NetworkPolicy default-deny để giảm blast radius khi service bị compromise.
- Secret lấy qua External Secrets, rotate được mà không rebuild image.
- PDB + topology spread giúp maintenance node/AZ không làm service mất quorum.
- Canary rollback dựa trên SLO metric, không rollback bằng cảm giác.

---

## 12. DR Plan

### RPO/RTO per Component

| Component | RPO | RTO | Strategy |
|-----------|-----|-----|----------|
| PostgreSQL (orders, payments) | 1 min | 15 min | Cross-region replica + WAL archive |
| PostgreSQL (products, inventory) | 5 min | 30 min | Cross-region replica |
| Redis cache | N/A | 5 min | Rebuild from DB |
| Kafka | 5 min | 15 min | MirrorMaker 2 |
| S3 images | 15 min | 1h | Cross-region replication |
| Application services | N/A | 15 min | Scale up DR region |

### Failover Runbook (summary)

```
1. Confirm primary region down (5 min)
2. Promote RDS read replica (5 min)
3. Scale up EKS in DR region (5 min)
4. Update DNS (Route 53 failover, auto 2 min)
5. Verify health (3 min)

Total RTO: ~20 min
```

---

## 13. Cost Breakdown & Optimization

### Monthly Cost (Production + DR)

```
Primary Region (us-east-1):
├── EKS cluster                   $73
├── EC2 nodes (Savings Plan)      $1,500
├── RDS Multi-AZ r6g.large        $560
├── ElastiCache r6g.large × 2     $400
├── MSK 3 brokers                 $540
├── ALB + NAT + transfer          $400
├── S3 (images + backups)         $100
├── CloudWatch                    $100
└── Subtotal                      $3,673

DR Region (us-west-2):
├── EKS cluster                   $73
├── EC2 nodes (minimal)           $200
├── RDS read replica              $280
├── ElastiCache (minimal)         $100
├── MSK (minimal)                 $200
├── S3 replication                $50
└── Subtotal                      $903

Cross-region data transfer        $200
CDN (CloudFront)                  $50

TOTAL: ~$4,826/month
```

### Cost Optimization Applied

- Spot instances: 60% of app nodes → Save $900/month
- Savings Plan 1-year (baseline compute) → Save $500/month
- Right-sized pods → Save $400/month
- S3 lifecycle (logs → Glacier) → Save $30/month
- Single NAT + VPC endpoints → Save $150/month
- Reduce non-prod replica count outside business hours → Save $120/month
- Tune log cardinality and retention per environment → Save $80/month
- Use CloudFront caching for product catalog/images → Save transfer + origin CPU
- Move batch notification workers to queue-based autoscaling → Reduce idle compute
- Review unattached EBS/EIP/LB weekly with automated report

**Total quantified savings: $2,180/month (~45% of original estimate)**
**Optimized cost before variable traffic savings: ~$2,646/month**

---

## 14. Common Pitfalls & Debugging — Top 5 Incident Runbooks

Pitfalls hay gặp khi làm capstone:

- Diagram đẹp nhưng không map được sang deployable components.
- Autoscaling chỉ dựa CPU trong khi bottleneck thật là DB connection pool hoặc Kafka lag.
- DR plan có RPO/RTO nhưng chưa có restore command và test schedule.
- Security plan chỉ nói encryption nhưng thiếu RBAC, NetworkPolicy, image scanning, secret rotation.
- Cost plan cắt nhầm redundancy ở path nhận tiền/order thay vì cắt retention, non-prod hoặc idle capacity.

### Runbook 1: Service Down (High Severity)

```markdown
# Runbook: Order Service Down

## Detection
- Alert: "OrderServiceDown" from Prometheus
- Symptom: 503 errors from API Gateway to order-service

## Initial Response (5 min)
1. Check pod status:
   kubectl get pods -n nextshop-production -l app=order-service
2. Check recent events:
   kubectl get events -n nextshop-production --sort-by='.lastTimestamp' | tail -20
3. Check HPA:
   kubectl get hpa -n nextshop-production

## Mitigation
- If all pods OOMKilled: temporarily increase memory limits
- If ImagePullBackOff: rollback to previous version
- If database connection issues: check RDS status

## Rollback Procedure
kubectl argo rollouts undo order-service -n nextshop-production

## Escalation
- 15 min unresolved → page on-call senior
- 30 min unresolved → incident commander assigned
```

### Runbook 2: High Latency

```markdown
# Runbook: High Latency

## Detection  
- Alert: P95 latency > 1s for 10 minutes

## Investigation
1. Check database slow queries:
   kubectl exec -n nextshop-data pg-0 -- psql -c "
     SELECT pid, now()-query_start AS duration, query 
     FROM pg_stat_activity 
     WHERE state='active' AND now()-query_start > '5 seconds';"

2. Check cache hit ratio:
   kubectl exec -n nextshop-data redis-0 -- redis-cli INFO stats | grep keyspace

3. Check Kafka consumer lag:
   kubectl exec kafka-0 -n nextshop-data -- kafka-consumer-groups.sh \
     --bootstrap-server localhost:9092 --group order-processor --describe

## Mitigation
- DB slow: Kill long queries, scale up RDS temporarily
- Cache miss: Warm cache from DB
- Kafka lag: Scale up consumers
```

### Runbook 3: Database Slow

```markdown
# Runbook: Database Slow

## Detection
- Alert: RDS CPU > 80% for 10 min
- Alert: Query time P95 > 500ms

## Immediate Actions
1. Identify top queries:
   SELECT query, calls, mean_exec_time 
   FROM pg_stat_statements 
   ORDER BY mean_exec_time DESC LIMIT 10;

2. Check for locks:
   SELECT * FROM pg_locks WHERE granted = false;

3. Check connections:
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;

## Mitigation
- Kill blocking queries: SELECT pg_cancel_backend(pid);
- Add missing indexes (after analysis)
- Scale up RDS instance temporarily (emergency)
- Route reads to replica
```

### Runbook 4: Message Queue Lag

```markdown
# Runbook: Kafka Consumer Lag

## Detection
- Alert: Consumer lag > 10,000 messages

## Investigation
1. Check consumer group:
   kafka-consumer-groups.sh --describe --group order-processor

2. Check consumer logs:
   kubectl logs -l app=notification-worker -n nextshop-production --tail=100

## Mitigation
- Scale up consumers: kubectl scale deploy/notification-worker --replicas=10
- Check for stuck messages (poison pill):
  - Inspect oldest unconsumed message
  - Deploy consumer with skip-poison capability
- Increase consumer resources if CPU-bound
```

### Runbook 5: Bad Deployment

```markdown
# Runbook: Bad Deployment

## Detection
- Alert: Error rate increase after deployment
- Alert: Canary analysis failed

## Immediate Actions
1. Abort rollout:
   kubectl argo rollouts abort <rollout-name> -n nextshop-production

2. Rollback to previous version:
   kubectl argo rollouts undo <rollout-name> -n nextshop-production

3. Verify rollback:
   kubectl get rollout <rollout-name> -n nextshop-production

## Post-rollback
1. Notify team via Slack
2. Update status page
3. Investigate root cause
4. Block further deployments until fixed
5. Schedule postmortem
```

---

## 15. Trade-offs & Best Practices — Final Review

### Trade-offs Made

| Decision | Alternative | Why We Chose |
|----------|-------------|-------------|
| Self-hosted EKS | ECS/Fargate | Portable, industry standard, team expertise |
| Spot instances 60% | All On-Demand | Cost savings 30%, acceptable risk for stateless |
| Warm DR | Active-Active | Cost vs complexity trade-off for startup |
| Canary via Argo Rollouts | Blue-Green | Lower cost, gradual risk |
| Managed RDS | Self-hosted | Team focus, compliance, acceptable cost |
| Istio optional | Mandatory service mesh | Current scale doesn't justify complexity |

Best practices cần giữ:

- Mỗi artifact phải có owner và review cadence.
- Mọi critical path có metric, alert và runbook tương ứng.
- Skeleton dùng digest-pinned images, resource requests/limits, probes, PDB, NetworkPolicy.
- Tối ưu cost theo risk tier, không cắt backup/restore test để giảm bill ngắn hạn.

## 16. Performance & Scalability

### If Scale 10x (100K RPS)

```
Changes needed:
├── Databases
│   ├── Read replicas: 2 → 5+
│   ├── Consider sharding (Citus/Vitess)
│   └── Aurora for better scaling
├── Caching
│   ├── Redis cluster mode (required)
│   └── Multi-tier caching (CDN + Redis + local)
├── Kafka
│   ├── Increase partitions
│   └── Dedicated brokers per topic
├── Compute
│   ├── Dedicated node pools per service
│   └── Consider serverless for bursty endpoints
└── Architecture
    ├── CQRS for read/write separation
    └── Event sourcing for audit trail
```

### If Budget Decreases 50%

```
Cuts priority (preserve reliability):
1. Reduce DR from warm to cold ($500/month)
2. Single AZ RDS for non-critical ($280/month)
3. Remove MSK, use Redis Streams ($500/month)
4. Aggressive spot + smaller instances ($300/month)
5. Reduce observability retention ($100/month)

Keep (even with budget cut):
- Production HA (Multi-AZ compute)
- Security (encryption, RBAC, scanning)
- Backup
- Core monitoring (can reduce retention)
```

### If Team Grows to 100 Engineers

```
New requirements:
├── Platform Engineering team (dedicated)
├── Internal developer platform (Backstage)
├── Multiple clusters (per team or shared)
├── Advanced GitOps (ArgoCD ApplicationSets)
├── Policy as Code enforcement (Kyverno at scale)
├── Centralized secrets management (Vault)
├── Service catalog
├── Developer self-service (preview environments)
├── Comprehensive SRE practice
└── Incident management tooling (PagerDuty, Blameless)
```

---

## 17. Kết nối với bài trước & bài sau

### Kiến thức đã tích lũy

**Phase 1 (Day 1-7)**: Linux, Networking, DevOps mindset
- Đã hiểu: process, signal, TCP/IP, DNS, performance tools, automation

**Phase 2 (Day 8-17)**: Docker & Kubernetes Core
- Đã hiểu: containers, K8s architecture, workloads, networking, storage, Helm

**Phase 3 (Day 18-25)**: Kubernetes Production
- Đã hiểu: resources, autoscaling, RBAC, admission control, troubleshooting

**Phase 4 (Day 26-31)**: IaC & GitOps
- Đã hiểu: Terraform, Ansible, ArgoCD/Flux, state management

**Phase 5 (Day 32-37)**: CI/CD & Release
- Đã hiểu: pipelines, GitHub Actions, deployment strategies, supply chain security

**Phase 6 (Day 38-44)**: Observability & Reliability
- Đã hiểu: metrics, logs, traces, SLO, incident response

**Phase 7 (Day 45-50)**: Production-grade Advanced
- Đã hiểu: DevSecOps, service mesh, database strategies, DR, cost optimization, production design

### Tiếp theo: "What's Next"

```
Recommended learning paths:

Platform Engineering:
├── Backstage.io (developer portal)
├── Crossplane (infrastructure as Kubernetes)
└── Internal Developer Platforms

Advanced Observability:
├── eBPF-based observability (Pixie, Cilium Hubble)
├── Continuous profiling (Parca, Pyroscope)
└── AIOps/MLOps for anomaly detection

Cloud Architecture:
├── Cloud architect certifications (AWS SA Pro, GCP PCA)
├── Serverless architectures (Lambda, Cloud Run, Knative)
└── Multi-cloud strategy

Advanced Kubernetes:
├── Custom controllers (Kubebuilder, Operator SDK)
├── Advanced scheduling (Volcano, YuniKorn)
└── Cluster federation

SRE:
├── Chaos engineering (Chaos Mesh, Litmus)
├── Advanced SLO management
└── Incident command system (ICS)
```

---

## 18. Tài liệu tham khảo

### Must-read
- [Kubernetes Production Checklist](https://learnk8s.io/production-best-practices) — comprehensive checklist
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/) — 6 pillars
- [The Twelve-Factor App](https://12factor.net/) — cloud-native principles

### Nice-to-have
- [CNCF Landscape](https://landscape.cncf.io/) — cloud-native ecosystem
- [DORA State of DevOps Report](https://dora.dev/research/) — latest benchmarks

### Deep-dive
- **Book**: "Designing Data-Intensive Applications" (Martin Kleppmann)
- **Book**: "Seeking SRE" (David N. Blank-Edelman, editor)
- **Book**: "Release It!" (Michael Nygard) — stability patterns
- **Book**: "Phoenix Project" (Gene Kim) — DevOps culture novel
- **Book**: "Accelerate" (Forsgren, Humble, Kim) — DORA research

