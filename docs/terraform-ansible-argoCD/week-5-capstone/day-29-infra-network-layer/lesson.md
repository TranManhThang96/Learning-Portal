# Day 29 - Infrastructure Network Layer

## 1. Mục tiêu ngày học

- Hiểu VPC design principles: CIDR planning, subnet segmentation, multi-AZ
- Phân biệt public subnet, private subnet, intra subnet — khi nào dùng cái nào
- Nắm được NAT Gateway cost model và các alternatives (VPC endpoint, proxy instance)
- Viết Security Group đúng: stateful, default deny inbound, least privilege
- Hiểu NACL vs Security Group — stateless vs stateful, ordering
- Triển khai VPC module với `terraform-aws-modules/vpc/aws`
- Chuẩn bị network config output để Day 30 reuse

---

## 2. Bối cảnh thực tế — Pain Story

Một team tôi từng mentor đã design VPC `10.0.0.0/16` với 1 subnet duy nhất cho cả EKS, RDS, Redis. Sau 6 tháng:

- **CIDR overlap**: team khác cần peering → không match được → phải migrate toàn bộ cluster, 3 ngày downtime
- **IP exhaustion**: EKS pod density cao → subnet /24 hết IP → pod pending, CNI crash → phải recreate VPC
- **Single-AZ**: NAT Gateway bị maintenance 1 AZ → toàn bộ egress fail → pagerduty 2AM
- **Không có VPC endpoint**: ECR pull qua NAT Gateway → NAT bill $800/tháng cho traffic nội bộ AWS
- **Public DB subnet**: RDS trong public subnet, security group lỏng lẻo → security audit fail → phải rebuild từ đầu

**Lesson: Network layer sai từ đầu = cost cao + downtime lớn + migration đau**

---

## 3. Kiến thức nền tảng

### 3.1 VPC — Isolated Network

VPC là isolated virtual network trên AWS. Mỗi VPC có một CIDR block — đây là IP range mà tất cả resource bên trong sẽ dùng.

```
CIDR block: 10.0.0.0/16
- 65,536 IPs total (10.0.0.0 - 10.0.255.255)
- /16 cho production platform đủ dùng
- Không overlap với on-prem, VPN, other VPC
```

**Quy tắc vàng**: Chọn CIDR một lần, không bao giờ thay đổi. Nếu cần mở rộng, dùng IPv6 hoặc Secondary CIDR block (không recommended).

### 3.2 Subnet Types — Phân biệt 3 loại

| Type | Route to Internet | Use case |
|------|-------------------|----------|
| **Public** | 0.0.0.0/0 → Internet Gateway | ALB, NAT Gateway instance, bastion host |
| **Private** | 0.0.0.0/0 → NAT Gateway | EKS nodes, RDS, ElastiCache, app servers |
| **Intra** | Không có route ra ngoài | Bastion không có EIP, internal tools |

```
Route table - public subnet:
  Destination       Target
  10.0.0.0/16       local
  0.0.0.0/0         igw-xxxxxxxx

Route table - private subnet:
  Destination       Target
  10.0.0.0/16       local
  0.0.0.0/0         nat-xxxxxxxx  (NAT Gateway)

Route table - intra subnet:
  Destination       Target
  10.0.0.0/16       local
  (no internet route)
```

### 3.3 Multi-AZ Design

Production bắt buộc minimum 2 AZ, recommend 3 AZ. Mỗi subnet nằm trong 1 Availability Zone riêng biệt.

```
VPC: 10.0.0.0/16
│
├── us-east-1a (AZ-1)
│   ├── subnet-public-1a   10.0.0.0/24
│   ├── subnet-private-1a  10.0.1.0/24
│   └── subnet-intra-1a    10.0.2.0/24
│
├── us-east-1b (AZ-2)
│   ├── subnet-public-1b   10.0.3.0/24
│   ├── subnet-private-1b  10.0.4.0/24
│   └── subnet-intra-1b    10.0.5.0/24
│
└── us-east-1c (AZ-3)
    ├── subnet-public-1c   10.0.6.0/24
    ├── subnet-private-1c  10.0.7.0/24
    └── subnet-intra-1c    10.0.8.0/24
```

### 3.4 NAT Gateway — Cost Warning

**CRITICAL: NAT Gateway cost rất dễ surprise.**

```
NAT Gateway pricing (us-east-1):
  - $0.045 per hour  →  ~$32/month per NAT
  - $0.045 per GB data processed

Scenario: 3 NAT Gateway (1 per AZ) + 500 GB egress/month
  → $32 × 3 = $96/month (hourly cost)
  → + $22.50 data processing
  → Total: ~$118/month baseline — CHƯA tính actual traffic

EKS node egress typical: 50-100 GB/month per node × 3 nodes = 150-300 GB
  → Thêm $6.75 - $13.50/month traffic
```

**Strategy giảm NAT cost**:
- Dùng VPC endpoint cho S3, DynamoDB (FREE gateway)
- Dùng VPC endpoint interface cho ECR, Secrets Manager, STS (~$7/month per AZ)
- CloudWatch Logs qua VPC endpoint (free)
- chỉ NAT Gateway cho thực sự cần egress ra internet (yum/apt update, third-party API)

### 3.5 Security Group vs NACL

```
Security Group (Stateful - Stateful firewall per ENI):
  - Default: ALLOW all outbound, DENY all inbound
  - Stateful: response traffic auto-allowed
  - Evaluate all rules (allow only, no deny)
  - Applied at ENI level (instance/ECS/EKS pod)

Network ACL (Stateless - subnet boundary):
  - Default: ALLOW all inbound AND outbound
  - Stateless: response traffic must be explicitly allowed
  - Ordered rules (100, 200, 300...) — first match wins
  - Applied at subnet level

Use NACL for:
  - Subnet-level deny (block specific IP ranges)
  - Backup deny rule (DENY known bad actors at subnet boundary)

Use Security Group for:
  - Application-level firewall (web/app/db tier)
  - Everything else — SG is primary firewall tool
```

### 3.6 VPC Endpoint — Gateway vs Interface

**Gateway Endpoint (S3, DynamoDB)**: Free, HA by default, regional.

**Interface Endpoint (PrivateLink)**: ~$7/month per AZ per endpoint + per-GB data processing.

```
Gateway endpoints (FREE — luôn dùng):
  - com.amazonaws.us-east-1.s3       (S3 bucket access)
  - com.amazonaws.us-east-1.dynamodb (DynamoDB)

Interface endpoints (~$7/AZ/tháng — chọn lọc):
  - com.amazonaws.us-east-1.ecr.api   (ECR API)
  - com.amazonaws.us-east-1.ecr.dkr   (ECR Docker)
  - com.amazonaws.us-east-1.sts        (STS — cần cho IRSA)
  - com.amazonaws.us-east-1.secretsmanager
  - com.amazonaws.us-east-1.logs       (CloudWatch Logs)
  - com.amazonaws.us-east-1.ec2        (EC2 API — cho EKS)

Minimum recommended interface endpoints (đủ cho EKS + IRSA):
  - S3 Gateway  (free)
  - DynamoDB Gateway (free)
  - ECR API + ECR DKR (~$14-28/month)
  - STS (~$7/month)
  - Secrets Manager (~$7/month)
  - Logs (~$7/month) hoặc CloudWatch Agent qua S3 gateway
```

### 3.7 DNS — enable_dns_hostnames + enable_dns_support

```
VPC DNS Settings:
  enable_dns_support = true         → VPC DNS resolver hoạt động
  enable_dns_hostnames = true       → Instance nhận public DNS hostname

Khi enable:
  - Instance trong private subnet có DNS: ip-10-0-1-23.ec2.internal
  - EKS endpoint nội bộ: https://capstone.eks.internal
  - Internal LB access qua private DNS
```

**Private Hosted Zone (Route53)**: Associate với VPC để dùng custom domain nội bộ.

### 3.8 Local Mode — kind Network Mapping

kind (Kubernetes in Docker) dùng Docker bridge network mặc định — không cần VPC. Nhưng hiểu mapping giúp transition sang AWS mode nhanh hơn.

```
Local mode (kind):
  Docker bridge: 172.17.0.0/16  (default kind range)
  kind network:  10.89.0.0/16   (configurable)
  Container:     eth0 → kind bridge → docker0 → host

Mapping concept:
  Docker bridge  ≈ VPC
  kind subnet    ≈ Subnet (private, không egress ra internet tự nhiên)
  Container port ≈ ENI (network interface)
  host port      ≈ Public subnet (có direct internet access)
```

Kind không có NAT Gateway vì container trực tiếp route qua docker0 bridge. Khi chuyển lên AWS, tư duy tương tự nhưng thay docker0 bằng NAT Gateway/IGW.

---

## 4. Deep Dive & Trade-offs

### 4.1 3 Cách Triển Khai VPC Module

| Approach | Pros | Cons |
|----------|------|------|
| `terraform-aws-modules/vpc/aws` | Opinionated, tested, full-feature, maintained | Opinionated — có thể overkill cho simple setup |
| Custom `aws_vpc`, `aws_subnet`, `aws_route_table` resources | Full control, learning sâu | Boilerplate nhiều, dễ miss details, phải tự manage everything |
| CloudPosse/terraform-aws-vpc | Combines modules, opinionated | Heavier dependencies |

**Recommendation**: Dùng `terraform-aws-modules/vpc/aws ~> 5.0` cho production. Module đủ linh hoạt để customize qua input variables, nhưng có best practices baked-in (route table organization, tag conventions).

### 4.2 NAT Gateway Alternatives — Chi Tiết

```
1. VPC Endpoint (BEST cho AWS internal traffic)
   ✅ Free for S3/DynamoDB, $7/AZ for others
   ✅ Highly available (AWS managed)
   ✅ Không tốn NAT cost
   ✅ Security: traffic không ra internet
   ❌ Chỉ hoạt động cho AWS service thuần túy
   ✅ Action: Luôn deploy S3 + DynamoDB gateway endpoint

2. Single NAT Gateway (1 AZ only — cost optimized)
   ✅ Giảm 2/3 cost so với NAT per AZ ($32 → $32/month thay vì $96)
   ✅ Đủ cho dev/staging
   ❌ Single point of failure — 1 AZ fail = no egress
   ✅ Mitigation: Deploy NAT instance backup (tự động failover via route table)
   ✅ Action: Dev/Staging dùng 1 NAT; Production dùng NAT per AZ

3. NAT Instance (t2.micro, ~$10/tháng)
   ✅ Rẻ hơn NAT Gateway
   ❌ Không managed, phải tự manage, patching, HA
   ❌ Source/destination check phải disable thủ công
   ❌ Legacy — không recommended cho production

4. Proxy Instance (squid, HAProxy)
   ✅ Chi phí thấp hơn NAT Gateway
   ✅ Có thể cache → giảm bandwidth
   ❌ Single point of failure (phải auto-scaling group + ALB để HA)
   ❌ Phải manage instance, IAM role, security group cho proxy
   ❌ Không scale tự động như NAT Gateway
   ✅ Action: Chỉ dùng khi budget cực kỳ hạn chế, cần HA proxy setup

5. NAT Gateway per AZ (production recommended)
   ✅ High availability — 1 AZ fail không ảnh hưởng
   ✅ Fully managed by AWS
   ✅ Elastic IP tự động
   ❌ Cost: ~$32/NAT × Số AZ × Số AZ used
   ✅ Action: Production dùng, dev/staging không cần
```

### 4.3 Subnet Sizing — EKS Focus

**AWS VPC CNI tốn IP rất nhiều** — mỗi EKS node chiếm 1 ENI + nhiều secondary ENI cho pod. Security group cũng consume IP.

```
EKS Node IP requirement (m3.large example):
  - ENI primary: 1 IP
  - Pod per ENI: m3.large max 12 ENIs, ~10 pods/ENI = ~120 pods
  - Security Group: 1-3 SG × IPs = 3 IPs per instance
  - Total per node: ~125 IPs (but /24 = 254 IPs, node chỉ dùng 1-3 IPs)

Pod IP exhaustion scenarios:
  - Node cần nhiều ENI (truncate/prefix delegation) → mỗi ENI = nhiều IPs
  - Security group-based enforcement (SG per pod) → mỗi pod = nhiều IPs hơn
  - 1 subnet /24 có thể chỉ đủ cho 2-3 EKS nodes lớn

Subnet sizing recommendation:
  - EKS node subnet: /20 (4,096 IPs) minimum cho production
  - RDS subnet: /24 (256 IPs) đủ cho DB tier
  - Intra subnet: /28 (16 IPs) cho bastion, internal tools
  - ALB subnet (public): /24 (256 IPs) — ALB IP per AZ
```

### 4.4 Security Group Strategy

```
Per-tier approach (recommended cho 3-tier app):
  - sg-web: ALB inbound 80/443 from 0.0.0.0/0
  - sg-app: App inbound 8080 from sg-web
  - sg-db: DB inbound 5432 from sg-app
  - sg-eks-nodes: Node inbound from SG của service thuộc nó

Per-service approach (recommended cho microservices):
  - sg-api-service: pod/service specific rules
  - sg-worker-service: background job rules
  - sg-frontend-service: web-facing rules
  - sg-shared: common access (efs, s3 via VPC endpoint)

Trade-off:
  Per-tier: Đơn giản, dễ manage, nhưng permission rộng hơn
  Per-service: Fine-grained, more secure, nhưng nhiều SG hơn
  Hybrid: Per-tier cho infra (EKS/RDS/Redis) + Per-service cho app
```

### 4.5 Cost Optimization Checklist

```
□ S3 Gateway endpoint (free) — luôn deploy
□ DynamoDB Gateway endpoint (free) — luôn deploy
□ ECR/DKR interface endpoint — deploy ở private subnet, không NAT
□ STS interface endpoint — cần cho IRSA, dùng thay vì NAT
□ Secrets Manager interface endpoint — tránh NAT cho secret access
□ CloudWatch Logs interface endpoint — tránh NAT cho log shipping
□ 1 NAT Gateway cho dev/staging (không phải 2-3 NAT)
□ NAT Gateway chỉ cho: yum/apt update, external API calls, GitHub actions runner
□ Dùng Spot instance cho non-critical workloads
□ EKS node subnet /20 — đủ cho EKS, không dư thừa IP
```

### 4.6 Context-Based Best Solution

| Context | Recommended Architecture |
|---------|--------------------------|
| **Cá nhân học / dev** | Local kind mode — zero cost |
| **Startup MVP** | Single NAT 1 AZ + S3/DynamoDB gateway + ECR/STS interface endpoints |
| **SME production** | NAT per AZ (2 AZ) + full VPC endpoint set |
| **Enterprise multi-region** | Transit Gateway hub-spoke + NAT per AZ + full endpoint set |
| **Bank / regulated industry** | Transit Gateway + dedicated VPC per workload + VPC endpoint full + no NAT |

### 4.7 Pitfalls — Common Mistakes

```
1. CIDR overlap khi peering
   → Fix: Dùng RFC 6598 (10.64-127.x.x.x) cho shared services
   → Dùng 100.64.0.0/10 range (CGN — Carrier-Grade NAT space)

2. Subnet hết IP cho EKS pod
   → Fix: /20 thay vì /24, theo dõi IP usage qua VPC CNI metrics
   → Enable prefix delegation

3. NAT Gateway cost surprise
   → Fix: Deploy VPC endpoint cho AWS service trước
   → Monitor NAT traffic qua NAT Gateway CloudWatch metric

4. RDS trong public subnet
   → Fix: Chỉ private subnet, dùng bastion hoặc Systems Manager Session Manager

5. Security group để allow all (0.0.0.0/0 ingress)
   → Fix: Hard rule — không bao giờ allow all inbound

6. Không enable DNS support → EKS cluster endpoint không resolve được
   → Fix: Bật enable_dns_support = true và enable_dns_hostnames = true

7. Dùng /16 cho tất cả subnet (quá rộng)
   → Fix: Subnet split theo usage: /20 cho EKS, /24 cho RDS, /28 cho intra

8. Không tạo VPC endpoint cho STS → IRSA fail
   → Fix: STS endpoint là prerequisite cho IRSA
```

---

## 5. Hands-on Lab

### Pre-requisites

- **Mode A (default, free)**: Docker + kind đã cài từ Day 17
- **Mode B (optional, có cost)**:
  - AWS account với billing alert đã set
  - AWS CLI configured (`aws configure`)
  - Terraform >= 1.6 installed
  - kubectl >= 1.27
  - **Cost warning**: VPC + NAT Gateway (1 AZ) + 3 interface endpoints ~$60-80/tháng

---

### Mode A — Local kind Network (Default, Free)

**Thời gian**: 30-45 phút

**Step 1**: Verify Docker và kind đã ready

```bash
docker --version
kind get clusters
```

**Step 2**: Inspect Docker network

```bash
docker network ls
docker network inspect bridge
```

Giải thích:
- `bridge` network: IP range default 172.17.0.0/16 — tương đương VPC CIDR
- kind dùng network riêng: kiểm tra `kind` network nếu đã tạo cluster

```bash
docker network inspect kind 2>/dev/null || echo "No kind network yet"
```

**Step 3**: Tạo document mapping Docker ↔ VPC concept

Tạo file `D:/my-source/learning/capstone-infra/local/network.md`:

```markdown
# Local Network Mapping — Docker/kind vs AWS VPC

## Docker Network = VPC (Conceptual Mapping)

| Docker/kind Concept | AWS VPC Equivalent |
|---------------------|---------------------|
| Docker bridge (172.17.0.0/16) | VPC CIDR (e.g., 10.0.0.0/16) |
| kind cluster network | Private subnet (không direct internet) |
| Container port mapping (-p) | Security group inbound rule |
| docker0 bridge | NAT Gateway + IGW (internet egress) |
| Container-to-container (same bridge) | ENI-to-ENI trong same VPC |
| Host network mode | Public subnet (direct host access) |

## kind Network Behavior

- kind cluster tạo Docker network riêng (default: 10.89.0.0/16)
- Node container: 1 IP trong kind network
- Pod container: IP từ node container network
- kind worker node đi internet qua container runtime → host docker0 bridge

## Mode B Transition Notes

Khi chuyển lên AWS:
1. kind cluster network → Private subnet (10.0.x.0/24)
2. Container egress → NAT Gateway
3. Docker bridge → VPC with IGW
4. Port mapping → Security group inbound rules
5. Service type LoadBalancer → AWS ALB

## kubectl Context

```bash
kind get clusters
kubectl cluster-info --context kind-capstone
```
```

**Step 4**: Verify kubectl context (nếu kind cluster đã có từ Day 28)

```bash
kubectl config get-contexts
kubectl get nodes
```

---

### Mode B — AWS VPC Module (Optional, Có Cost)

**Thời gian**: 60-90 phút

> **COST WARNING** ⚠️
> VPC resource (free) + NAT Gateway (1 AZ): ~$32-35/tháng
> Interface endpoints (ECR, STS, Secrets, Logs): ~$28-35/tháng/tháng
> **Total estimate: ~$60-80/tháng**
> Setup billing alert trước khi apply
> **BẮT BUỘC chạy `terraform destroy` sau lab**

**Step 1**: Navigate vào capstone-infra repo

```bash
cd D:/my-source/learning/capstone-infra
mkdir -p terraform/modules/vpc terraform/envs/dev
```

**Step 2**: Tạo module `terraform/modules/vpc/versions.tf`

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

**Step 3**: Tạo `terraform/modules/vpc/variables.tf`

```hcl
variable "project" {
  description = "Project name"
  type        = string
}

variable "env" {
  description = "Environment name"
  type        = string
}

variable "cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "single_nat_gateway" {
  description = "Use single NAT Gateway (cost-optimized, 1 AZ only)"
  type        = bool
  default     = true
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway (disable for local mode)"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}
```

**Step 4**: Tạo `terraform/modules/vpc/main.tf`

```hcl
locals {
  name = "${var.project}-${var.env}"
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = var.cidr

  # AZs
  azs = var.availability_zones

  # Public subnets — for ALB, NAT Gateway instance, bastion
  public_subnets = [for i, az in var.availability_zones : cidrsubnet(var.cidr, 4, i)]

  # Private subnets — for EKS nodes, RDS, ElastiCache, app tier
  private_subnets = [for i, az in var.availability_zones : cidrsubnet(var.cidr, 4, length(var.availability_zones) + i)]

  # Intra subnets — for bastion without EIP, internal tools
  intra_subnets = [for i, az in var.availability_zones : cidrsubnet(var.cidr, 4, 2 * length(var.availability_zones) + i)]

  # NAT Gateway strategy
  enable_nat_gateway = var.enable_nat_gateway

  # Cost-optimized: 1 NAT Gateway (single_nat_gateway = true)
  # Production: single_nat_gateway = false → 1 NAT per AZ
  single_nat_gateway = var.single_nat_gateway

  # VPC DNS
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Public subnet tags — for ALB controller
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  # Private subnet tags — for EKS node group
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "kubernetes.io/cluster/${local.name}-eks" = "owned"
  }

  # Tags
  tags = merge(var.tags, {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "Terraform"
  })

  # Common tags applies to all resources
  vpc_tags = {
    Name = "${local.name}-vpc"
  }
}

# Security Group: EKS Cluster
resource "aws_security_group" "eks_cluster" {
  name        = "${local.name}-eks-cluster"
  description = "Security group for EKS cluster control plane"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${local.name}-eks-cluster"
  }
}

# Security Group: EKS Nodes
resource "aws_security_group" "eks_nodes" {
  name        = "${local.name}-eks-nodes"
  description = "Security group for EKS nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    description = "Allow all traffic from within VPC"
    cidr_blocks = [var.cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${local.name}-eks-nodes"
  }
}

# Security Group: RDS/PostgreSQL
resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    description     = "PostgreSQL from EKS nodes"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${local.name}-rds"
  }
}

# Security Group: ElastiCache/Redis
resource "aws_security_group" "elasticache" {
  name        = "${local.name}-elasticache"
  description = "Security group for ElastiCache Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    description     = "Redis from EKS nodes"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${local.name}-elasticache"
  }
}

# VPC Endpoint: S3 Gateway (FREE)
endpoint_services = ["s3"]

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = module.vpc.vpc_id
  service_name = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.s3"
  # S3 gateway endpoint là regional, nhưng terraform-aws-modules/vpc/aws
  # có hỗ trợ tự động tạo gateway endpoint
  # Dùng cách khác:

  tags = {
    Name = "${local.name}-s3-endpoint"
  }
}
```

**Step 4 (Revised)**: Refactor main.tf — dùng gateway endpoint từ VPC module + interface endpoints riêng:

```hcl
# S3 Gateway endpoint (free) — terraform-aws-modules/vpc/aws tự tạo
# Khi bật enable_nat_gateway = true, module tự tạo S3 endpoint

# DynamoDB Gateway endpoint (free) — cũng được tạo bởi module

# VPC Endpoint: STS Interface (REQUIRED for IRSA)
resource "aws_vpc_endpoint" "sts" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.sts"
  vpc_endpoint_type = "Interface"
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name}-sts-endpoint"
  }
}

# VPC Endpoint: ECR API
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.ecr.api"
  vpc_endpoint_type = "Interface"
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name}-ecr-api-endpoint"
  }
}

# VPC Endpoint: ECR Docker
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.ecr.dkr"
  vpc_endpoint_type = "Interface"
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name}-ecr-dkr-endpoint"
  }
}

# VPC Endpoint: Secrets Manager
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.secretsmanager"
  vpc_endpoint_type = "Interface"
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name}-secretsmanager-endpoint"
  }
}

# VPC Endpoint: CloudWatch Logs
resource "aws_vpc_endpoint" "logs" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.availability_zones[0].regex_replace("[a-z]", "")}.logs"
  vpc_endpoint_type = "Interface"
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${local.name}-logs-endpoint"
  }
}

# Security Group cho VPC Interface Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "${local.name}-vpc-endpoints"
  description = "Security group for VPC Interface Endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.cidr]
    description = "HTTPS from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${local.name}-vpc-endpoints"
  }
}
```

**Step 5**: Tạo `terraform/modules/vpc/outputs.tf` — **Đầy đủ output cho Day 30**

```hcl
# VPC
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "vpc_name" {
  description = "VPC name tag"
  value       = local.name
}

# Subnets
output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnets
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnets
}

output "intra_subnet_ids" {
  description = "List of intra subnet IDs"
  value       = module.vpc.intra_subnets
}

output "availability_zones" {
  description = "List of AZs"
  value       = var.availability_zones
}

# Route Tables
output "public_route_table_id" {
  description = "Public subnet route table ID"
  value       = module.vpc.public_route_table_ids[0]
}

output "private_route_table_ids" {
  description = "Private subnet route table IDs"
  value       = module.vpc.private_route_table_ids
}

# NAT Gateway
output "nat_gateway_id" {
  description = "NAT Gateway ID (single) — null if single_nat_gateway=true and AZ 0 is used"
  value       = length(module.vpc.nat_gateway_ids) > 0 ? module.vpc.nat_gateway_ids[0] : null
}

output "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  value       = module.vpc.nat_gateway_ids
}

# Internet Gateway
output "igw_id" {
  description = "Internet Gateway ID"
  value       = module.vpc.igw_id
}

# Security Groups
output "eks_cluster_sg_id" {
  description = "EKS Cluster security group ID"
  value       = aws_security_group.eks_cluster.id
}

output "eks_nodes_sg_id" {
  description = "EKS Nodes security group ID"
  value       = aws_security_group.eks_nodes.id
}

output "rds_sg_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "elasticache_sg_id" {
  description = "ElastiCache security group ID"
  value       = aws_security_group.elasticache.id
}

output "vpc_endpoints_sg_id" {
  description = "VPC Endpoints security group ID"
  value       = aws_security_group.vpc_endpoints.id
}

output "all_security_group_ids" {
  description = "Map of all security group names to IDs"
  value = {
    eks_cluster    = aws_security_group.eks_cluster.id
    eks_nodes      = aws_security_group.eks_nodes.id
    rds            = aws_security_group.rds.id
    elasticache    = aws_security_group.elasticache.id
    vpc_endpoints  = aws_security_group.vpc_endpoints.id
  }
}

# VPC Endpoints
output "vpc_endpoint_ids" {
  description = "Map of VPC endpoint IDs"
  value = {
    sts            = aws_vpc_endpoint.sts.id
    ecr_api        = aws_vpc_endpoint.ecr_api.id
    ecr_dkr        = aws_vpc_endpoint.ecr_dkr.id
    secretsmanager = aws_vpc_endpoint.secretsmanager.id
    logs           = aws_vpc_endpoint.logs.id
  }
}

output "sts_vpc_endpoint_dns" {
  description = "STS VPC endpoint DNS entries (for IRSA configuration)"
  value       = aws_vpc_endpoint.sts.dns_entries
}
```

**Step 6**: Tạo `terraform/envs/dev/main.tf`

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source = "../../modules/vpc"

  project = "capstone"
  env     = "dev"

  cidr = "10.0.0.0/16"

  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

  # Cost-optimized: 1 NAT Gateway (SPOF acceptable for dev)
  enable_nat_gateway  = true
  single_nat_gateway  = true

  tags = {
    Project     = "capstone"
    Environment = "dev"
    CostCenter  = "capstone-dev"
  }
}

# Terraform state remote backend recommendation (for team)
terraform {
  backend "s3" {
    bucket         = "capstone-terraform-state-${data.aws_caller_identity.current.account_id}"
    key            = "capstone-infra/dev/vpc/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
  }
}

data "aws_caller_identity" "current" {}
```

**Step 7**: Initialize và plan

```bash
cd terraform/envs/dev
terraform init
terraform plan -out=tfplan
```

Review plan output — kiểm tra:
- VPC CIDR: 10.0.0.0/16
- 9 subnets (3 AZ × 3 types)
- 1 NAT Gateway (single_nat_gateway = true)
- S3 + DynamoDB gateway endpoints (automatic from module)
- 5 Interface VPC endpoints
- 5 security groups

**Step 8**: Apply

```bash
terraform apply tfplan
```

**Step 9**: Verify trong AWS Console

```bash
# CLI verification
aws ec2 describe-vpcs --vpc-ids $(terraform output -raw vpc_id)
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$(terraform output -raw vpc_id)"
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$(terraform output -raw vpc_id)"
```

**Step 10**: Export outputs file cho Day 30 reuse

```bash
terraform output -json > outputs.json
cat outputs.json
```

Kiểm tra output quan trọng:
- `vpc_id` — input cho EKS module
- `private_subnet_ids` — input cho EKS node group
- `eks_nodes_sg_id` — input cho EKS node group
- `vpc_endpoint_ids` — cấu hình IRSA

**Step 11**: **CLEANUP — BẮT BUỘC**

```bash
terraform destroy
```

Xác nhận cleanup đã chạy hoàn tất trước khi kết thúc lab. Nếu muốn giữ lại infrastructure (tốn ~$60-80/tháng), ghi chú lại VPC ID để skip Day 29 lab trong Day 30.

---

## 6. Kiểm tra hiểu bài

**Câu 1**: Tại sao NAT Gateway 3 AZ (1 NAT per AZ) tốn $96/tháng, và làm sao giảm xuống ~$32/tháng mà vẫn có egress?

> Đáp: 1 NAT Gateway × $0.045/giờ × 730 giờ ≈ $32.80/tháng. Nhân 3 AZ = ~$99/tháng. Giảm bằng cách dùng `single_nat_gateway = true` → 1 NAT Gateway duy nhất cho tất cả private subnet trong mọi AZ. Trade-off: SPOF (1 AZ fail = no egress) nhưng chấp nhận được cho dev/staging.

**Câu 2**: Security Group có stateful — vậy khi cho phép inbound port 443, tại sao không cần allow outbound response?

> Đáp: Stateful = AWS track connection state tự động. Khi inbound 443 được allow, response traffic (source port 443 → dest random port) tự động được allowed mà không cần explicit rule. NACL thì stateless → phải allow cả outbound response.

**Câu 3**: EKS pod subnet /24 (254 IPs) bị exhausted sau khi chỉ tạo 5 nodes. Giải thích nguyên nhân và solution.

> Đáp: AWS VPC CNI assign IP cho mỗi pod từ subnet. m3.large có thể chạy 12 ENIs × ~10 pods/ENI = 120 pods. Mỗi node chiếm 1-3 IPs (ENI primary + SG IPs). 5 nodes × 3 IPs = 15 IPs. Nhưng thực tế: VPC CNI prefix delegation (WARM_PREFIX_TARGET) + pod density cao → nhanh chóng hết. Solution: Dùng subnet /20 (4,096 IPs) hoặc custom CNI (cilium/calico) dùng IPAM riêng.

**Câu 4**: IRSA (IAM Role for Service Account) cần VPC endpoint nào, tại sao không dùng NAT Gateway?

> Đáp: STS VPC endpoint (Interface) là bắt buộc cho IRSA. Khi pod gọi `sts:AssumeRoleWithWebIdentity`, request phải đi qua STS endpoint nội bộ VPC. Dùng NAT Gateway được nhưng tốn cost (traffic ra internet + vào lại). STS endpoint interface ~$7/tháng/AZ + traffic free nội bộ → rẻ hơn và secure hơn.

**Câu 5**: S3 bucket access từ EKS pod — dùng S3 Gateway endpoint hay S3 over NAT?

> Đáp: Luôn dùng S3 Gateway endpoint (free). S3 Gateway endpoint là free và highly available. NAT Gateway tốn $0.045/GB. 100GB S3 traffic/month = $4.50 qua NAT, free qua gateway endpoint. Thêm vào đó, traffic qua gateway endpoint không rời AWS network → lower latency, better security.

---

## 7. Tóm tắt cuối ngày

### Key takeaways

- **VPC design = CIDR planning + subnet segmentation + AZ distribution**. Chọn CIDR một lần, không thay đổi.
- **Private subnet = route through NAT Gateway; Public subnet = route through IGW; Intra = no internet route**
- **NAT Gateway cost: $0.045/giờ = $32/tháng/NAT. Single NAT = 1/3 cost, acceptable cho dev/staging**
- **VPC endpoint gateway (S3/DynamoDB) = FREE. Interface endpoints = ~$7/AZ/tháng. Luôn dùng gateway endpoint**
- **Security Group: Stateful, per-ENI, default deny inbound. NACL: Stateless, per-subnet, ordered rules**
- **EKS subnet sizing: /20 minimum cho production (VPC CNI tốn IP nhiều)**

### Deliverables (Day 29)

```
capstone-infra/
├── terraform/
│   ├── modules/
│   │   └── vpc/
│   │       ├── main.tf          # VPC module + SGs + VPC endpoints
│   │       ├── variables.tf     # All inputs
│   │       ├── outputs.tf       # All outputs for Day 30
│   │       └── versions.tf      # Terraform + provider version constraints
│   └── envs/
│       └── dev/
│           ├── main.tf          # Dev environment calling vpc module
│           └── outputs.json     # (generated after terraform apply)
└── local/
    └── network.md               # Docker/kind ↔ VPC mapping (Mode A)
```

### Chuẩn bị Day 30

Day 30 (Kubernetes & IAM Layer) cần:
- `vpc_id` — tạo EKS cluster
- `private_subnet_ids` — node group subnet placement
- `eks_nodes_sg_id` — node security group
- `eks_cluster_sg_id` — cluster security group
- `vpc_endpoint_ids.sts` — IRSA hoạt động
- AWS account với permissions: `eks:*`, `iam:*`, `ec2:*`, `ecr:*`

---

## 8. Tham khảo thêm

- [terraform-aws-modules/vpc/aws](https://github.com/terraform-aws-modules/terraform-aws-vpc) — VPC module documentation, input variables reference
- [AWS VPC Pricing](https://aws.amazon.com/vpc/pricing/) — NAT Gateway, VPC endpoints cost
- [EKS Subnet Sizing](https://docs.aws.amazon.com/eks/latest/best-practices/networking.html) — Official AWS best practice
- [AWS VPC CNI IP](https://aws.github.io/aws-eks-best-practices/networking/implementations/) — Pod IP exhaustion prevention
- [IRSA with VPC Endpoint](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) — STS endpoint requirement
- [VPC Endpoint for EKS](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoints.html) — Private access vs public
