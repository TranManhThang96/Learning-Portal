# Day 29 - Infrastructure Network Layer — Exercises

## Challenge 1: Multi-Region VPC Peering Design

**Đề bài**: Thiết kế multi-region VPC architecture cho 5 service sau:

```
Service A (us-east-1): API gateway, cần giao tiếp với Service B
Service B (ap-southeast-1): Main database, chỉ accept connection từ A
Service C (us-east-1): Worker/queue consumer, đọc từ Service B
Service D (eu-west-1): Analytics/reporting, read-only từ Service B
Service E (us-east-1): Background job, access S3 + DynamoDB global
```

**Yêu cầu**:
1. Chọn CIDR cho mỗi VPC — không được overlap (dùng terraform-aws-modules/vpc/aws)
2. Thiết kế VPC peering connections: A↔B, A↔C, B↔D (không có A↔D direct)
3. Mỗi peering: chỉ rõ "requester" và "accepter" VPC
4. Route tables: mỗi subnet type (public/private/intra) cần route gì để reach other region
5. Security group rules cần thiết cho inter-VPC communication
6. Giải thích tại sao KHÔNG dùng Transit Gateway cho setup này

**Constraints**:
- Không dùng overlapping CIDR (không dùng 10.0.0.0/16 cho tất cả)
- Service B database chỉ reachable từ A, C, D — không từ E
- Analytics service D không được phép khởi tạo connection ra ngoài

**Deliverable**: Terraform skeleton cho mỗi VPC module + peering configuration + route table rules

---

## Challenge 2: Cost Reduction từ $300 xuống < $50/tháng

**Đề bài**: Infrastructure hiện tại tốn $300/tháng:

```
3 NAT Gateways (1 per AZ):           $96/month
5 Interface VPC Endpoints × 3 AZs:  $109.50/month
EC2 NAT Instances (3):               $30/month
Data transfer (NAT traffic):         $40/month
VPC Flow Logs S3:                    $25/month
-------------------------------------------
Total:                               ~$300/month
```

**Phân tích và giải quyết**:

1. **Tách cost theo category** — identify 3 main drivers
2. **Đề xuất architecture mới** giữ HA nhưng < $50/tháng:
   - S3 + DynamoDB gateway endpoint: $0 → áp dụng ngay
   - NAT Gateway: giảm từ 3 × $32 → 1 × $32 (single_nat_gateway=true)
   - Interface endpoints: giảm 5 × 3 AZ → 5 × 1 AZ (private subnet chỉ ở 1 AZ cho egress)
   - Data transfer: giảm NAT traffic bằng cách nào
3. **Drawback**: Trade-off của từng thay đổi, SLAs nào bị ảnh hưởng
4. **Alternative**: Nếu không có NAT Gateway được, dùng gì thay thế cho yum/apt update

**Deliverable**: Table so sánh before/after cost + Terraform variables để toggle NAT strategy + trade-off matrix

---

## Challenge 3: Refactor Flat VPC → Tier-Based Subnet (Zero Downtime)

**Đề bài**: Production system đang chạy trên flat VPC:

```hcl
# Current: 1 subnet duy nhất cho tất cả
aws_vpc.main = { cidr = "10.0.0.0/16" }
aws_subnet.main = { cidr = "10.0.0.0/24" }  # Chỉ /24 — sắp hết IP
# 254 IPs, đã dùng 220, RDS cần 10 IPs reserved, EKS pods chiếm 150 IPs
```

**Migrate plan** (zero downtime, production):

```
Phase 1: Tạo new VPC parallel (10.1.0.0/16) với proper subnet segmentation
Phase 2: Deploy new EKS cluster trong new VPC (dual-cluster strategy)
Phase 3: Migrate workload từ old cluster → new cluster
Phase 4: Migrate RDS bằng read replica → promote
Phase 5: Switch Route53 → new VPC
Phase 6: Deprecate old VPC
```

**Yêu cầu**:

1. Viết Terraform module cho new VPC (`terraform/modules/vpc-migration/`):
   - VPC CIDR: 10.1.0.0/16
   - 3 AZ, 3 subnet types (public/private/intra)
   - Subnet sizing: đủ cho EKS production (50 nodes × 110 pods = 5,500 IPs)
   - S3 + DynamoDB gateway endpoint
   - STS + ECR interface endpoints

2. Tính toán:
   - Subnet CIDR cụ thể cho mỗi subnet (dùng cidrsubnet formula)
   - IP buffer còn lại sau migration

3. Migration runbook:
   - Step-by-step để migrate không downtime
   - Rollback plan nếu migration fail
   - DNS cutover strategy (Route53 weighted routing)

4. Security group migration:
   - Old SG reference → New SG
   - Temporary allow rules during migration window

**Deliverable**: Module `terraform/modules/vpc-migration/main.tf` + migration runbook markdown

---

## Challenge 4: Debug "EKS Pod ENI Exhaustion"

**Đề bài**: EKS cluster bị pod stuck ở trạng thái `Pending`:

```
$ kubectl get pods -n api-service
NAME                        READY   STATUS    RESTARTS   AGE
api-deployment-xxx-abc123   0/1     Pending   0          5m
api-deployment-xxx-def456   0/1     Pending   0          5m

$ kubectl describe pod api-deployment-xxx-abc123 -n api-service
Events:
  Warning  FailedScheduling  2m ago   default-scheduler
           0/3 nodes are available: 3 node(s) for pod anti-affinity,
           0/3 nodes had volume node affinity conflict,
           insufficient memory, Insufficient ENIs.

$ kubectl describe node ip-10-0-1-23.ec2.internal
Allocated resources:
  Resource                    Requests     Limits
  cpu                         2 (66%)      4 (133%)
  memory                      4Gi (80%)    8Gi (128%)
  pods                        58 (max 58) ← FULL
```

**Debug steps**:

1. **Xác định root cause** — đọc AWS VPC CNI logs:
   ```bash
   kubectl get pods -n kube-system -l k8s-app=kube-proxy -o wide
   kubectl logs -n kube-system -l k8s-app=aws-node --tail=100
   ```

2. **Phân tích ENI consumption**:
   - Node type: `m5.xlarge` (max 4 ENIs, 15 IPs/ENI = 58 pods max)
   - Tính: 3 nodes × 58 pods = 174 theoretical max
   - Vấn đề: Tất cả pod đang trên 1 node (anti-affinity), IP pool exhausted

3. **Giải pháp tức thời** (không tạo thêm node):
   - Tăng `WARM_IP_TARGET` → giải phóng IP buffer
   - Drain 1 node → IPs trả về pool
   - Pod anti-affinity đang làm gì — tại sao pod không spread

4. **Giải pháp dài hạn**:
   - Tính toán IP requirement mới (50 nodes, m5.xlarge)
   - Subnet resizing: /24 → /20
   - Enable prefix delegation
   - Consider custom CNI (Cilium) nếu IP exhaustion thường xuyên

5. **Terraform fix**:
   - Viết module input để tăng subnet size
   - `aws_subnet` resource update (terraform apply với `-replace`)

**Deliverable**:
- Debug runbook với 5 diagnostic commands
- Terraform snippet fix: subnet resize plan (maintenance window required)
- HCL calculation: subnet /24 → /20 cần thêm bao nhiêu IPs

---

## Challenge 5: Transit Gateway Hub-Spoke cho 4 VPC

**Đề bài**: Thiết kế Transit Gateway architecture cho:

```
Hub VPC (10.0.0.0/16):
  - Shared services: ECR, EFS, Secrets Manager
  - NAT Gateway (shared, 1 AZ)
  - Transit Gateway attachment

Spoke VPC 1 - Dev (10.1.0.0/16):
  - EKS dev cluster
  - Dev workloads

Spoke VPC 2 - Staging (10.2.0.0/16):
  - EKS staging cluster
  - Staging workloads

Spoke VPC 3 - Production (10.3.0.0/16):
  - EKS production cluster
  - Production workloads
```

**Yêu cầu**:

1. **Transit Gateway resource**:
   ```hcl
   resource "aws_ec2_transit_gateway" "main" {
     description = "Capstone TGW"
     # Các options cần thiết
   }
   ```

2. **TGW Route Tables**:
   - Hub VPC route table: default route (0.0.0.0/0 → NAT GW)
   - Spoke VPC route table: route to 0.0.0.0/0 via hub
   - Spoke-to-spoke: YES or NO — giải thích security implication

3. **VPC attachments** (4 attachments):
   - Hub VPC attachment
   - Dev VPC attachment (shared route table)
   - Staging VPC attachment (shared route table)
   - Production VPC attachment (production route table)

4. **Security considerations**:
   - Spoke VPC nào được phép communicate với nhau
   - RBAC: team dev không được quản lý TGW
   - Transit Gateway VPC endpoint (for VPCs that need AWS API access via TGW)

5. **Cost estimate**:
   - TGW hourly: $0.02/hour (us-east-1)
   - TGW attachment: $0.02/hour/attachment
   - TGW Data processing: $0.01/GB
   - 4 VPC × 730 hours × $0.02 = ?

**Deliverable**: Complete Terraform module `terraform/modules/tgw/` với main.tf + outputs.tf

---

## Bonus Challenge: IPv6 Dual-Stack Migration Plan

**Đề bài**: Production VPC đang dùng IPv4 only. Lãnh đạo yêu cầu enable IPv6.

```
Current VPC:
  VPC CIDR:     10.0.0.0/16  (IPv4 only)
  Subnets:      9 subnets (/20 each)
  EKS:          3 nodes, production
  RDS:          Primary + 1 replica
  Services:     API, Worker, Frontend
```

**Migration plan** phải đảm bảo:
- Zero production downtime
- IPv4 backward compatibility trong 6 tháng
- EKS pod IPv6 assignment (VPC CNI có hỗ trợ IPv6 từ version nào?)

**Yêu cầu**:

1. **Pre-migration audit**:
   - Checklist 10 items trước khi enable IPv6
   - Identify services không support IPv6 (legacy dependencies)

2. **Step-by-step migration**:
   - Step 1: Enable VPC IPv6 (assign Amazon-provided IPv6 CIDR)
   - Step 2: Update subnets (assign IPv6 CIDR per subnet)
   - Step 3: Update route tables (::/0 → egress-only IGW)
   - Step 4: Update Security Groups (add IPv6 rules — có cần không?)
   - Step 5: Update NACLs (có cần IPv6 rules không?)
   - Step 6: EKS node group IPv6 (VPC CNI config)
   - Step 7: Service update (dual-stack ingress)

3. **Rollback plan**: Nếu migration fail ở Step 4, rollback procedure là gì

4. **Cost impact**: IPv6 có tốn thêm tiền không? (AWS pricing)

5. **DNS**: Route53 AAAA record strategy, health check dual-stack

**Deliverable**: Migration plan markdown (2-3 trang) + Terraform snippet cho IPv6 enablement + rollback procedure
