# Day 29 - Infrastructure Network Layer — Reference Document

## 1. VPC Design Cheat Sheet

### CIDR Planning

```
RFC 1918 Private Ranges:
  10.0.0.0/8     — Class A (16,777,216 IPs) — Recommended cho large VPC
  172.16.0.0/12  — Class B (1,048,576 IPs) — Dev/AWS reserved ranges
  192.168.0.0/16 — Class C (65,536 IPs)   — Small VPC only

Production recommendation: 10.0.0.0/16
  - Đủ IP cho multi-AZ, multi-tier deployment
  - Không overlap với common VPN (10.50, 10.99, 192.168.1.x)
  - Prefix /16 → chia subnet linh hoạt

RFC 6598 CGN (Carrier-Grade NAT): 100.64.0.0/10
  - Dùng cho VPC peering shared services (tránh CIDR overlap)

DO NOT dùng:
  - 172.17.0.0/16 → Docker default
  - 172.18.0.0/16, 172.19.0.0/16 → Docker compose default
  - 192.168.0.0/24 → local dev default
```

### Subnet Split Formula

```
VPC CIDR: 10.0.0.0/16 (65,536 IPs)

For 3 AZ × 3 subnet types (9 subnets total):

Step 1: Determine bits for AZ dimension
  AZs = 3 → ceil(log2(3)) = 2 bits
  Remaining bits = 16 - 8 (for /16) - 2 (for AZ) = 6 bits
  → /18 per AZ group

Step 2: Determine bits for subnet type dimension
  Subnet types = 3 → ceil(log2(3)) = 2 bits
  → /20 per subnet type

Step 3: Assign subnet CIDRs
  us-east-1a public:   10.0.0.0/20   (10.0.0.0   - 10.0.15.255)   4,096 IPs
  us-east-1a private:   10.0.16.0/20  (10.0.16.0  - 10.0.31.255)   4,096 IPs
  us-east-1a intra:     10.0.32.0/20  (10.0.32.0  - 10.0.47.255)   4,096 IPs

  us-east-1b public:    10.0.48.0/20  (10.0.48.0  - 10.0.63.255)   4,096 IPs
  us-east-1b private:   10.0.64.0/20  (10.0.64.0  - 10.0.79.255)   4,096 IPs
  us-east-1b intra:     10.0.80.0/20  (10.0.80.0  - 10.0.95.255)   4,096 IPs

  us-east-1c public:    10.0.96.0/20  (10.0.96.0  - 10.0.111.255)  4,096 IPs
  us-east-1c private:   10.0.112.0/20 (10.0.112.0 - 10.0.127.255)  4,096 IPs
  us-east-1c intra:     10.0.128.0/20 (10.0.128.0 - 10.0.143.255)  4,096 IPs

/terraform-aws-modules/vpc/aws tự tính subnet CIDR qua cidrsubnet() — không cần tính tay
```

---

## 2. EKS Subnet Sizing — IP Requirement Matrix

### VPC CNI vs Custom CNI

```
AWS VPC CNI (default):
  - Mỗi pod nhận IP từ VPC subnet
  - Mỗi ENI có số lượng IP giới hạn (instance type dependent)
  - Security Group per ENI → mỗi ENI consume IP
  - → IP hungry: cần subnet lớn

Cilium (eBPF-based):
  - Pod IP từ CIDR riêng (không trùng VPC subnet)
  - Dùng IPAM nội bộ
  - Không phụ thuộc ENI/IP
  - → Ít IP hơn từ VPC subnet

Calico:
  - Có thể dùng IP pool riêng
  - Policy-driven IP management
  - → Linh hoạt hơn VPC CNI
```

### IP Requirement Per Instance Type

```
Instance Type  | Max ENIs | IPs/ENI | Max Pods (approx) | IPs Used from Subnet
---------------|----------|---------|--------------------|-------------------------
t3.micro       | 2        | 4       | 17                 | 2-4
t3.small       | 2        | 6       | 25                 | 2-4
t3.medium       | 3        | 6       | 34                 | 3-6
t3.large        | 3        | 10      | 58                 | 3-6
m5.large        | 3        | 10      | 58                 | 3-6
m5.xlarge       | 4        | 15      | 118                | 4-8
m5.2xlarge      | 4        | 15      | 118                | 4-8
m5.4xlarge      | 8        | 15      | 234                | 8-16
c5.2xlarge      | 4        | 15      | 118                | 4-8
r5.xlarge       | 4        | 15      | 118                | 4-8

Formula: max_pods = (max_ENIs × IPs_per_ENI) - 1  (1 IP cho ENI itself)
```

### Subnet Sizing Decision Matrix

```
Workload Type          | Node Count | Max Pods/Node | Total IPs | Recommended Subnet
-----------------------|------------|---------------|-----------|------------------
Dev/Single node       | 1-3        | 110           | 330       | /24 (254 IPs) ❌ SMALL
Staging/Multi node     | 3-6        | 110           | 660       | /23 (510 IPs) ❌ SMALL
Production small       | 6-12       | 110           | 1,320     | /22 (1,022 IPs) ⚠️ TIGHT
Production medium      | 12-24      | 110           | 2,640     | /21 (2,046 IPs) ⚠️ TIGHT
Production large       | 24-50      | 110           | 5,500     | /20 (4,094 IPs) ✅ MINIMUM
Production enterprise  | 50-150     | 110           | 16,500    | /19 (8,190 IPs) ✅ COMFORTABLE

Recommendation:
  EKS node subnet: /20 minimum (4,094 IPs per AZ)
  Buffer for future: /18 (16,382 IPs per AZ)
```

### Prefix Delegation (WARM_PREFIX_TARGET)

```
VPC CNI ConfigMap settings:
  WARM_PREFIX_TARGET = 1  (default)
  → Reserve 1 ENI prefix per node (default, IP efficient)
  WARM_IP_TARGET = 3
  → Keep 3 free IPs available (for new pods)

  MINIMUM_IP_TARGET = 6
  → Never drop below 6 free IPs (ensures fast pod scheduling)

Warning: prefix delegation mode (NEW) assigns /28 block per pod group
→ More IP efficient but needs VPC CNI >= 1.9.0
→ Still uses VPC IPs — does NOT solve exhaustion problem
```

---

## 3. NAT Gateway Alternatives Comparison

```
Alternative              | Cost/mo        | HA  | Managed | Complexity | Use Case
-------------------------|----------------|-----|---------|------------|---------------------------
S3/DynamoDB Gateway EP  | FREE           | Yes | Yes    | None       | AWS internal traffic
Other Interface EP       | ~$7/AZ/service | Yes | Yes    | Low        | ECR, STS, Secrets, Logs
Single NAT (1 AZ)        | ~$32           | No* | Yes    | Low        | Dev/Staging, non-prod
NAT per AZ (2 AZ)        | ~$64           | Yes | Yes    | Low        | Production budget
NAT per AZ (3 AZ)        | ~$96           | Yes | Yes    | Low        | Enterprise production
NAT Instance (t3)        | ~$10           | No  | No     | High       | Legacy, cost-constrained
Proxy ASG + ALB          | ~$15-25        | Yes | No     | High       | Custom logging/cache
Transit Gateway NAT      | Variable       | Yes | Partial| Very High  | Multi-VPC/multi-region
No NAT (VPC endpoints)   | ~$35-70        | Yes | Yes    | Medium     | Best for EKS workloads

* Single NAT: AZ failure = egress failure. Mitigate: Route53 health check + failover route table

RECOMMENDATION BY CONTEXT:
  Local kind: No NAT needed
  Dev: 1 NAT Gateway + VPC endpoints for AWS services
  Staging: 1 NAT Gateway + VPC endpoints
  Production: NAT per AZ (2 AZ minimum) + VPC endpoints
```

---

## 4. VPC Endpoint Catalog

### Gateway Endpoints (FREE — Always Deploy)

```
Service      | Endpoint Service Name                    | Region | Protocol | Notes
-------------|-----------------------------------------|--------|----------|---------------------------
S3           | com.amazonaws.us-east-1.s3              | Regional | HTTPS | Automatically routes via AWS backbone
DynamoDB     | com.amazonaws.us-east-1.dynamodb        | Regional | HTTPS | Automatically routes via AWS backbone

terraform-aws-modules/vpc/aws:
  create_s3_endpoint = true  (automatic when enable_nat_gateway = true)
  create_dynamodb_endpoint = true

Cost: FREE — không giới hạn traffic
```

### Interface Endpoints (PrivateLink — $7/AZ/month)

```
Service              | Endpoint Service Name           | Prereq for | Priority
---------------------|----------------------------------|------------|--------
STS                  | com.amazonaws.{region}.sts       | IRSA       | CRITICAL
ECR API              | com.amazonaws.{region}.ecr.api   | ECR pull   | HIGH
ECR Docker           | com.amazonaws.{region}.ecr.dkr   | docker pull| HIGH
Secrets Manager      | com.amazonaws.{region}.secretsmanager | ESO  | HIGH
CloudWatch Logs      | com.amazonaws.{region}.logs      | Logging    | HIGH
CloudWatch Metrics   | com.amazonaws.{region}.monitoring| Monitoring | MEDIUM
CloudFormation       | com.amazonaws.{region}.cloudformation| CFN    | MEDIUM
ELB                  | com.amazonaws.{region}.elasticloadbalancing| ALB | MEDIUM
KMS                  | com.amazonaws.{region}.kms        | Encryption | MEDIUM
SQS                  | com.amazonaws.{region}.sqs        | Queue     | LOW
SNS                  | com.amazonaws.{region}.sns        | Notif     | LOW
Lambda               | com.amazonaws.{region}.lambda     | Serverless| LOW

Cost calculation (us-east-1):
  5 endpoints × 3 AZs × $0.01/hour × 730 hours = $109.50/month
  BUT: 1 AZ setup (single_nat_gateway = true) → 5 endpoints × 1 AZ × $0.01 × 730 = $36.50/month
  + $0.01/GB data processing (negligible for most workloads)

Minimum for EKS workload: STS + ECR API + ECR DKR + Secrets Manager + Logs = 5 endpoints
```

### VPC Endpoint DNS Configuration

```
private_dns_enabled = true (RECOMMENDED)
  → Endpoint gets private DNS: vpce-xxxxx.sns.us-east-1.vpce.amazonaws.com
  → Các AWS SDK tự động resolve nội bộ VPC
  → Không cần hardcode endpoint URL

private_dns_enabled = false
  → Phải set AWS endpoint override trong SDK config
  → Phức tạp hơn, dễ miss
```

---

## 5. Security Group Strategy Templates

### 3-Tier Architecture Template

```hcl
# ALB Security Group (internet-facing)
resource "aws_security_group" "alb" {
  name = "${prefix}-alb"
  vpc_id = var.vpc_id

  # Inbound: HTTP/HTTPS from internet
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from internet"
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  # Outbound: to EKS nodes (via ALB target group)
  egress {
    from_port                = 443
    to_port                  = 443
    protocol                 = "tcp"
    description              = "To EKS nodes"
    source_security_group_id = aws_security_group.eks_nodes.id
  }
}

# EKS Node Security Group
resource "aws_security_group" "eks_nodes" {
  name = "${prefix}-eks-nodes"
  vpc_id = var.vpc_id

  # Inbound: from ALB
  ingress {
    from_port                = 443
    to_port                  = 443
    protocol                 = "tcp"
    description              = "From ALB"
    source_security_group_id = aws_security_group.alb.id
  }

  # Inbound: from other EKS nodes (cluster internal)
  ingress {
    from_port                = 0
    to_port                  = 65535
    protocol                 = "tcp"
    description              = "Intra-cluster"
    source_security_group_id = aws_security_group.eks_nodes.id
  }

  # Inbound: from bastion (optional, for debugging)
  ingress {
    from_port                = 22
    to_port                  = 22
    protocol                 = "tcp"
    description              = "SSH from bastion"
    source_security_group_id = aws_security_group.bastion.id
  }
}

# Database Security Group
resource "aws_security_group" "rds" {
  name = "${prefix}-rds"
  vpc_id = var.vpc_id

  # Inbound: from EKS nodes only
  ingress {
    from_port                = 5432
    to_port                  = 5432
    protocol                 = "tcp"
    description              = "PostgreSQL from EKS nodes"
    source_security_group_id = aws_security_group.eks_nodes.id
  }
}
```

### Per-Service Microservices Template

```hcl
# Per-service SG pattern (recommended for microservices)
locals {
  services = {
    api-service      = { port = 8080, health_check = "/health" }
    worker-service   = { port = 8081, health_check = "/health" }
    frontend-service = { port = 3000, health_check = "/health" }
  }
}

resource "aws_security_group" "services" {
  for_each = local.services

  name = "${var.prefix}-${each.key}"
  vpc_id = var.vpc_id

  # Allow traffic from ALB
  ingress {
    from_port                = each.value.port
    to_port                  = each.value.port
    protocol                 = "tcp"
    description              = "From ALB"
    source_security_group_id = aws_security_group.alb.id
  }

  # Allow traffic from other services (for internal calls)
  ingress {
    from_port                = each.value.port
    to_port                  = each.value.port
    protocol                 = "tcp"
    description              = "Inter-service"
    source_security_group_id = aws_security_group.eks_nodes.id
  }
}

# Database: allow from specific service SGs (not entire EKS nodes SG)
resource "aws_security_group" "rds" {
  name = "${var.prefix}-rds"
  vpc_id = var.vpc_id

  # Allow from api-service only
  ingress {
    from_port                = 5432
    to_port                  = 5432
    protocol                 = "tcp"
    source_security_group_id = aws_security_group.services["api-service"].id
  }
}
```

---

## 6. Module Input/Output Reference

### Module Inputs (terraform/modules/vpc/variables.tf)

```hcl
variable "project"                  { type = string,  description = "Project name",           default = "capstone" }
variable "env"                      { type = string,  description = "Environment (dev/stg/prod)", default = "dev" }
variable "cidr"                     { type = string,  description = "VPC CIDR block",           default = "10.0.0.0/16" }
variable "availability_zones"       { type = list(string), description = "AZ list", default = ["us-east-1a","us-east-1b","us-east-1c"] }
variable "single_nat_gateway"       { type = bool,    description = "1 NAT for all AZs (SPOF, cost-optimized)", default = true }
variable "enable_nat_gateway"       { type = bool,    description = "Enable NAT Gateway",        default = true }
variable "create_s3_endpoint"       { type = bool,    description = "S3 gateway endpoint",       default = true }
variable "create_dynamodb_endpoint" { type = bool,    description = "DynamoDB gateway endpoint", default = true }
variable "tags"                     { type = map(string), default = {} }
variable "vpc_flow_log_bucket"      { type = string,  description = "S3 bucket for VPC Flow Logs", default = "" }
```

### Module Outputs (terraform/modules/vpc/outputs.tf)

```hcl
# VPC Core
output "vpc_id"                     { value = module.vpc.vpc_id }
output "vpc_cidr"                   { value = module.vpc.vpc_cidr_block }
output "vpc_name"                    { value = local.name }

# Subnets (list — all AZs)
output "public_subnet_ids"           { value = module.vpc.public_subnets }
output "private_subnet_ids"          { value = module.vpc.private_subnets }
output "intra_subnet_ids"            { value = module.vpc.intra_subnets }
output "availability_zones"         { value = var.availability_zones }

# Route Tables
output "public_route_table_id"       { value = module.vpc.public_route_table_ids[0] }
output "private_route_table_ids"     { value = module.vpc.private_route_table_ids }

# NAT Gateway
output "nat_gateway_id"              { value = one(module.vpc.nat_gateway_ids) }
output "nat_gateway_ids"             { value = module.vpc.nat_gateway_ids }

# IGW
output "igw_id"                      { value = module.vpc.igw_id }

# Security Groups (individual)
output "eks_cluster_sg_id"           { value = aws_security_group.eks_cluster.id }
output "eks_nodes_sg_id"             { value = aws_security_group.eks_nodes.id }
output "rds_sg_id"                   { value = aws_security_group.rds.id }
output "elasticache_sg_id"           { value = aws_security_group.elasticache.id }
output "vpc_endpoints_sg_id"         { value = aws_security_group.vpc_endpoints.id }

# Security Groups (map — for Day 30 EKS module)
output "all_security_group_ids" {
  value = {
    eks_cluster   = aws_security_group.eks_cluster.id
    eks_nodes     = aws_security_group.eks_nodes.id
    rds           = aws_security_group.rds.id
    elasticache   = aws_security_group.elasticache.id
    vpc_endpoints = aws_security_group.vpc_endpoints.id
  }
}

# VPC Endpoints
output "vpc_endpoint_ids" {
  value = {
    sts            = aws_vpc_endpoint.sts.id
    ecr_api        = aws_vpc_endpoint.ecr_api.id
    ecr_dkr        = aws_vpc_endpoint.ecr_dkr.id
    secretsmanager = aws_vpc_endpoint.secretsmanager.id
    logs           = aws_vpc_endpoint.logs.id
  }
}
output "sts_vpc_endpoint_dns"        { value = aws_vpc_endpoint.sts.dns_entries }
```

---

## 7. Cost Optimization Checklist (10 Items)

```
[ ] 1. S3 Gateway endpoint deployed — free S3 traffic
[ ] 2. DynamoDB Gateway endpoint deployed — free DynamoDB traffic
[ ] 3. ECR/DKR Interface endpoint deployed — avoid NAT for container pulls
[ ] 4. STS Interface endpoint deployed — IRSA uses internal route
[ ] 5. Secrets Manager Interface endpoint deployed — ESO avoids NAT
[ ] 6. CloudWatch Logs Interface endpoint deployed — log shipping avoids NAT
[ ] 7. Dev/Staging: single_nat_gateway = true (1 AZ, SPOF acceptable)
[ ] 8. Production: single_nat_gateway = false (1 NAT per AZ, 2 AZ minimum)
[ ] 9. EKS node subnet /20 — enough for 4,000 IPs, not /16 wasteful
[ ] 10. Spot instances for non-production workloads (dev, staging)
```

---

## 8. Anti-Patterns (10-12)

```
1. ❌ Single subnet for entire VPC (10.0.0.0/16 = 1 subnet)
   → FIX: Multi-tier subnet (public/private/intra) × AZs

2. ❌ CIDR overlap khi VPC peering
   → FIX: Dùng RFC 6598 100.64.0.0/10 cho shared services VPC

3. ❌ /24 subnet cho EKS nodes
   → FIX: /20 minimum, theo dõi IP consumption qua CNI metrics

4. ❌ Public RDS (DB trong public subnet)
   → FIX: Private subnet only, dùng bastion hoặc Session Manager

5. ❌ Allow all inbound (0.0.0.0/0) trong security group
   → FIX: Security group reference hoặc specific CIDR

6. ❌ Không có VPC endpoint, egress qua NAT cho AWS internal traffic
   → FIX: Deploy S3 + DynamoDB gateway endpoint (free), STS + ECR interface endpoints

7. ❌ Single AZ cho production
   → FIX: Minimum 2 AZ, recommended 3 AZ

8. ❌ Hardcode region, account ID trong Terraform
   → FIX: Dùng data "aws_region", data "aws_caller_identity"

9. ❌ Dùng default VPC
   → FIX: Create dedicated VPC per environment với naming convention

10. ❌ Terraform state local trong repo
    → FIX: S3 backend với DynamoDB state locking

11. ❌ Không enable VPC Flow Logs
    → FIX: Enable Flow Logs → S3 bucket hoặc CloudWatch Logs

12. ❌ Kubernetes service LoadBalancer type → tạo ELB mới mỗi service
    → FIX: Dùng AWS LB Controller + shared ALB ingress → 1 ALB cho tất cả
```

---

## 9. Common Terraform Errors — VPC

```
Error: "The CIDR defined is already in use"
  Cause: CIDR overlap với existing VPC hoặc VPN
  Fix: Chọn CIDR khác, kiểm tra all VPC trong account
       aws ec2 describe-vpcs --query 'Vpcs[*].CidrBlock'

Error: "Value for undeclared variable" (subnet CIDR)
  Cause: cidrsubnet() overflow — không đủ bits
  Fix: Tăng VPC CIDR size (dùng /16 thay vì /20) hoặc giảm số subnet

Error: "No qualifying subnet found for AZ us-east-1d"
  Cause: AZ không có capacity hoặc không tồn tại trong region
  Fix: Kiểm tra azs trong region
       aws ec2 describe-availability-zones --region us-east-1

Error: "Creating EC2 Subnet failed: The size of the CIDR must be between /16 and /28"
  Cause: Subnet CIDR quá nhỏ hoặc quá lớn
  Fix: /16 max (VPC CIDR), /28 min (16 IPs — quá nhỏ)

Error: "InvalidGatewayID" — route to igw- not found
  Cause: Internet Gateway chưa attach vào VPC
  Fix: module.vpc tự attach IGW, kiểm tra module version

Error: "NatGateway ID not found" sau khi xóa NAT Gateway
  Cause: Route table vẫn reference NAT Gateway cũ
  Fix: terraform apply lại sau khi NAT Gateway destroy

Error: "VPC endpoint validation failed: Invalid service name"
  Cause: Sai region trong service name
  Fix: Dùng correct region format: com.amazonaws.{region}.{service}
       region = "us-east-1" → com.amazonaws.us-east-1.s3

Error: "Security group rule source security group X is in VPC Y, but rule is in VPC Z"
  Cause: Reference SG từ VPC khác (VPC peering hoặc shared SG)
  Fix: Mỗi SG chỉ reference SG cùng VPC

Error: "CIDR [x.x.x.x/28] is too small; minimum size is /24"
  Cause: EKS node subnet nhỏ hơn /24 không đủ IP
  Fix: Tăng subnet size lên /24 hoặc lớn hơn
```

---

## 10. Architecture Diagram — Production VPC

```
┌─────────────────────────────────────────────────────────────────┐
│                        VPC: 10.0.0.0/16                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  us-east-1a                   us-east-1b    us-east-1c   │  │
│  │                                                           │  │
│  │  [Public Subnet]      [Public Subnet]  [Public Subnet]  │  │
│  │  10.0.0.0/20           10.0.48.0/20   10.0.96.0/20      │  │
│  │  ┌──────────┐          ┌──────────┐    ┌──────────┐     │  │
│  │  │ ALB      │          │          │    │          │     │  │
│  │  └──────────┘          └──────────┘    └──────────┘     │  │
│  │  0.0.0.0/0 → igw-xxx   (IGW shared across AZs)         │  │
│  │                                                           │  │
│  │  [Private Subnet]     [Private Subnet]  [Private Subnet] │  │
│  │  10.0.16.0/20         10.0.64.0/20   10.0.112.0/20      │  │
│  │  ┌──────────┐          ┌──────────┐    ┌──────────┐     │  │
│  │  │ EKS Node │          │ EKS Node │    │ EKS Node │     │  │
│  │  │ (pod)    │          │ (pod)    │    │ (pod)    │     │  │
│  │  │ (pod)    │          │          │    │          │     │  │
│  │  └──────────┘          └──────────┘    └──────────┘     │  │
│  │       ↑                      ↑               ↑          │  │
│  │  0.0.0.0/0 ───────→ NAT-GW ←───────────────────────────  │  │
│  │                                                           │  │
│  │  [Intra Subnet]       [Intra Subnet]   [Intra Subnet]   │  │
│  │  10.0.32.0/20         10.0.80.0/20   10.0.128.0/20      │  │
│  │  ┌──────────┐          ┌──────────┐    ┌──────────┐     │  │
│  │  │ Bastion  │          │          │    │          │     │  │
│  │  │ (no EIP) │          └──────────┘    └──────────┘     │  │
│  │  └──────────┘                                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  VPC Endpoints (Interface) — PrivateLink:                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ vpce-sts        vpce-ecr-api    vpce-ecr-dkr           │  │
│  │ vpce-secrets    vpce-logs       (all in private subnets) │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  VPC Endpoints (Gateway) — FREE:                              │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│  │ S3 Gateway (vpce-s3)    │  │ DynamoDB Gateway (vpce-ddb)│  │
│  └─────────────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```
