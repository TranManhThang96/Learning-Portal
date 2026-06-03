# Day 30 - Kubernetes & IAM Layer

## 1. Mục tiêu ngày học

- Hiểu EKS managed control plane vs self-managed node, trade-off cost/operation.
- Phân biệt managed node group vs self-managed vs Karpenter vs Fargate.
- Nắm Spot instance lifecycle + interruption handling (2 phút notice).
- Triển khai IRSA (IAM Role for Service Account) — pod-level least-privilege thay vì node-level.
- Hiểu OIDC provider flow: EKS → token → AssumeRoleWithWebIdentity → IAM role.
- So sánh ECR vs GHCR, chọn đúng cho từng context.
- Thực hành: Mode A tạo kind cluster local; Mode B tạo EKS + managed node group + IRSA + ECR repo.

---

## 2. Bối cảnh thực tế

### Pain points trong production

| Vấn đề | Hậu quả | Giải pháp |
|---|---|---|
| Tự cài K8s control plane (etcd HA, API server HA, version patch) | Team mất 2-4 tuần setup, lỗi upgrade mỗi quý | EKS managed control plane |
| Long-lived AWS access key trong pod | Security audit fail, key leak → breakout | IRSA (pod-level IAM) |
| Pod dùng node IAM role (instance profile) | Tất cả pod trên node có quyền như nhau → blast radius lớn | IRSA per workload |
| Spot instance không có `toleration` | Spot reclaim → pod evict storm → outage | Spot + toleration + on-demand baseline |
| ECR repo không lifecycle policy | Image chồng chất → $50-200/tháng cho storage | Lifecycle policy giữ 10 images |
| Quên tạo OIDC provider trước khi dùng IRSA | Pod assume role fail → `NoCredentialProviders` | Terraform module tự tạo |

---

## 3. Kiến thức nền tảng (~30 phút)

### 3.1 EKS — Managed Control Plane

```
EKS = AWS quản lý control plane (API server, etcd, scheduler, controller manager)
Học viên chỉ quản lý: node, workload, IAM, networking
Chi phí: ~$73/cluster/tháng (plus node)
```

**Ưu điểm:**
- Control plane HA (3 AZ), tự patch, tự upgrade
- Tích hợp IAM, VPC CNI, CloudWatch, X-Ray
- Fargate profile, Karpenter, managed node group đều hỗ trợ

**Nhược điểm:**
- $73/tháng ngay cả khi cluster idle
- Region-locked (không multi-region tự nhiên)
- Add-on có thể đi sau upstream K8s 1-2 minor version

### 3.2 Node Group Types

```
┌─────────────────────────────────────────────────────────────┐
│                    EKS Cluster                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Managed Node Group (AWS tạo + quản lý ASG, AMI)     │   │
│  │  Self-Managed (học viên tạo ASG, custom AMI)         │   │
│  │  Karpenter (node tự tạo theo Pod spec, modern)       │   │
│  │  Fargate (serverless, không quản node, per-pod billing)│   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Managed Node Group:**
- AWS tạo ASG + managed lifecycle (rolling update tự động)
- Hỗ trợ Spot ( `--spot-instance-treats-as-non-warm-true` flag )
- Bottlerocket, AL2023, Ubuntu AMI options
- Rolling update với surge/unsatisfied count

**Self-Managed Node Group:**
- Học viên tạo ASG, gắn vào EKS node role
- Full control: custom AMI (Bottlerocket có hardened config), kernel tuning
- Phù hợp: regulated environment (bank, healthcare) cần signed AMI + hardening
- Nhiều operational overhead hơn

**Karpenter (recommended production):**
- Node tạo theo Pod spec (not ASG-based)
- Tự động scale down khi không cần
- Hỗ trợ Spot tốt hơn (diversification across instance types)
- Cost saving: 40-60% vs managed node group trong nhiều workload

**Fargate:**
- Không quản node, per-pod billing
- Phù hợp: stateless microservice, spike workload
- Không hỗ trợ: DaemonSet, host network, certain CSI drivers
- Cost: đắt hơn On-Demand node với workload ổn định, rẻ hơn nếu workload spiky

### 3.3 On-Demand vs Spot vs Reserved

| Instance type | Use case | Price | Interruption |
|---|---|---|---|
| On-Demand | Baseline HA, stateful, databases | 100% | Không |
| Spot | Stateless, batch, worker, dev/test | 60-70% off | 2 phút notice |
| Reserved/Savings Plan | Baseline ổn định dài hạn | 30-60% off | Không |

**Spot Interruption Handling:**
```
AWS sent Spot interruption notice (2 phút trước)
  → Node taint "aws-node interruption" + drain tự động (nếu dùng node group)
  → Pod bị evicted theo graceful termination policy
  → Pod scheduling lại trên node khác hoặc On-Demand
```

### 3.4 IAM Role for Service Account (IRSA)

```
┌─────────────┐     OIDC Provider     ┌──────────────────────┐
│   Pod       │───(JWT token)───────▶│  AWS STS             │
│  (JWT sa)   │                       │  AssumeRoleWith      │
│             │◀──(temp creds)────────│  WebIdentity         │
└─────────────┘                       └──────────────────────┘
                                               │
                                               ▼
                                        ┌─────────────────┐
                                        │  IAM Role       │
                                        │  (least privilege│
                                        │  per workload)  │
                                        └─────────────────┘
```

**Trust Policy Template (least-privilege):**
```yaml
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${account_id}:oidc-provider/${oidc_provider_url}"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "${oidc_provider_url}:sub": "system:serviceaccount:${namespace}:${service_account}"
      }
    }
  }]
}
```

**OIDC Provider Setup:**
```bash
# terraform-aws-modules/eks tự tạo OIDC provider
# Hoặc manual:
aws iam create-open-id-connect-provider \
  --url https://oidc.eks.us-east-1.amazonaws.com/id/XXXXXXXXXX \
  --thumbprint-list XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX \
  --client-id-list sts.amazonaws.com
```

### 3.5 ECR vs GHCR

| Tiêu chí | ECR (Private) | ECR (Public) | GHCR |
|---|---|---|---|
| Auth | IAM-based | Anonymous | GitHub token (GITHUB_TOKEN) |
| Cost | $0.09/GB storage + transfer | Free egress | Free (public), $0.25/GB bandwidth (private) |
| Region | Per-region | Global | Global |
| IRSA | ✅ Native | ✅ | ❌ (không support OIDC) |
| Lifecycle | ✅ Policy giữ N images | ❌ | ❌ |
| Vulnerability scan | ✅ Basic free | ❌ | ❌ |

**Recommendation capstone:**
- Mode B: ECR private (tích hợp IRSA, lifecycle policy)
- Mode A: GHCR public (miễn phí, dễ setup)

### 3.6 kind cho Local Development

```yaml
# capstone-infra/local/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "127.0.0.1"
  apiServerPort: 6443
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=control-plane"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
  labels:
    node-role: worker
- role: worker
  labels:
    node-role: worker
```

**Lưu ý kind:**
- Không có IRSA (không support OIDC)
- Dùng `imagePullSecrets` cho GHCR private
- MetalLB cung cấp LoadBalancer service
- Phù hợp CI/CD pipeline hoặc dev local

---

## 4. Deep Dive & Trade-offs (~30 phút)

### 4.1 Node Group Strategy Decision Matrix

```
Use case              │ Managed Node │ Karpenter │ Fargate │ Self-managed
──────────────────────┼──────────────┼───────────┼─────────┼─────────────
Dev/Test cluster      │     ★★       │    ★★★    │   ★     │     ★
Startup production    │     ★★       │    ★★★    │   ★     │     ★
Enterprise (bank)     │     ★        │    ★★     │   ★     │    ★★★
Batch/ML workload    │     ★        │    ★★★    │   ★     │     ★
Spiky traffic API     │     ★★       │    ★★★    │  ★★★    │     ★
Regulated/HIPAA       │     ★        │    ★      │   ★     │    ★★★
```

### 4.2 Spot Strategy — Production Mix

```yaml
# Managed Node Group với Spot
# terraform/modules/eks-node-group/main.tf (fragment)
scaling_config {
  desired_size = 2        # baseline On-Demand
  min_size     = 2
  max_size     = 10

  # Spot config
  # Dùng mixed-instances policy
  # (terraform-aws-modules/eks hỗ trợ via node_groups)
}

# Tốt hơn: Karpenter với Spot
# karpenter-provisioner.yaml
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: default
spec:
  requirements:
    - key: "karpenter.sh/capacity-type"
      operator: In
      values: ["spot", "on-demand"]
    - key: "node.kubernetes.io.instance-type"
      operator: In
      values: ["t3.medium", "t3.large", "m5.large", "m5.xlarge"]
  limits:
    resources:
      cpu: "100"
      memory: "300Gi"
  provider:
    instanceProfile: ${instance_profile_name}
  ttlSecondsAfterEmpty: 60
```

**Spot diversification strategy:**
- 3-5 instance types khác nhau (family + size)
- `capacity-optimized` allocation cho stateful workload
- `lowest-price` cho batch dev/test

### 4.3 Pod Disruption Budget + Spot

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 1   # Ensure at least 1 replica available during Spot reclaim
  selector:
    matchLabels:
      app: api-service
```

**Pod toleration for Spot:**
```yaml
tolerations:
- key: "node.kubernetes.io/lifecycle"
  operator: "Equal"
  value: "spot"
  effect: "NoSchedule"
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      preference:
        matchExpressions:
        - key: "node.kubernetes.io/lifecycle"
          operator: In
          values: ["on-demand"]  # Prefer on-demand, tolerate spot
```

### 4.4 Pod Identity vs IRSA

| Tiêu chí | IRSA (Legacy) | Pod Identity (AWS 2023+) |
|---|---|---|
| Setup | OIDC provider + trust policy + annotation | AWS Pod Identity Agent + annotation |
| OIDC mount | ServiceAccount token mounted vào pod | Không cần mount (agent fetch) |
| Cluster version | K8s 1.14+ | EKS 1.27+ (recommended) |
| Permission boundary | IAM role + trust policy | IAM role + Pod Identity policy |
| Multi-account | Khó hơn | Dễ hơn |
| Audit log | CloudTrail STS | CloudTrail AssumeRole |

**Recommendation:**
- EKS 1.27+: dùng Pod Identity (đơn giản hơn)
- EKS < 1.27: dùng IRSA
- kind/local: mock bằng Kubernetes Secret hoặc kube2iam

### 4.5 Cost Breakdown — Capstone Dev Cluster (Mode B)

```
EKS control plane:         $73.00/month
Managed Node Group (2x t3.medium on-demand):
                         × $0.0416/hr × 730hr = $60.74/month
                         (nếu dùng Spot: ~$18.22/month × 2 = $36.44)
EBS volumes (gp3):          ~$10.00/month
ECR storage (3 repos):      ~$5.00/month
NAT Gateway (1 AZ):         ~$32.50/month  ← có thể bỏ trong dev
──────────────────────────────
Mode B dev cluster:        ~$145-165/month (with NAT)
Mode B dev cluster:         ~$115-130/month (without NAT, private subnet NAT instance)
Mode A kind:               $0/month (local)
```

**Cost optimization:**
- Dùng Spot cho worker node (tiết kiệm 60-70%)
- Bỏ NAT Gateway trong dev (VPC endpoint cho ECR + S3)
- Dev cluster: shutdown sau giờ làm (ASG schedule)

### 4.6 Best Solution Per Context

```
┌──────────────────────────────────────────────────────────────┐
│ Context                     │ Recommended Stack              │
├─────────────────────────────┼────────────────────────────────┤
│ Học tập cá nhân            │ kind + GHCR + LocalStack       │
│ Startup MVP                 │ EKS + Karpenter + ECR + Spot 70%│
│ Enterprise (SME)            │ EKS + Karpenter + ECR + Spot   │
│ Bank / Regulated            │ EKS + private control plane    │
│                              │ + Bottlerocket + signed AMI   │
│ Multi-region                │ EKS + Karpenter + cross-account│
│                              │ ECR replication                │
└─────────────────────────────┴────────────────────────────────┘
```

### 4.7 Common Pitfalls

| Pitfall | Hậu quả | Fix |
|---|---|---|
| Quên tạo OIDC provider | IRSA `AssumeRoleWithWebIdentity` fail | Module `terraform-aws-modules/eks` tự tạo |
| IRSA trust policy sai `namespace` | Pod không nhận credential | Check `system:serviceaccount:ns:sa` đúng |
| Spot không có `toleration` | Pod bị evict không graceful | Add toleration + affinity preferred |
| ECR repo không lifecycle | Storage cost tăng | Thêm policy giữ 10 images |
| Cluster có 1 node khi dùng Spot | Spot reclaim = 0 node | Baseline ≥2 On-Demand + Spot burst |
| Dùng node IAM role cho pod | Over-privileged pod | Refactor sang IRSA |
| Không có PodDisruptionBudget | Spot reclaim = downtime | PDB minAvailable = 1 |

---

## 5. Hands-on Lab (~60 phút)

### Pre-requisites

**Mode A (default — $0):**
- Docker Desktop + kind
- kubectl
- GHCR access (GitHub token)
- `capstone-infra/` và `capstone-platform/` directories đã tồn tại

**Mode B (có cost ~$115-165/tháng):**
- Day 29 VPC outputs: `vpc_id`, `private_subnet_ids`, `sg_id`
- AWS CLI configured
- Terraform >= 1.5

---

### Mode A — kind Cluster (Local, Free)

**Step 1: Tạo kind config file**

```bash
mkdir -p capstone-infra/local
```

```yaml
# capstone-infra/local/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: capstone-dev
networking:
  apiServerAddress: "127.0.0.1"
  apiServerPort: 6443
  podSubnet: "10.244.0.0/16"
  serviceSubnet: "10.96.0.0/16"
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=control-plane"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
  kubeadmConfigPatches:
  - |
    kind: JoinConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=worker"
- role: worker
  kubeadmConfigPatches:
  - |
    kind: JoinConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=worker"
```

**Step 2: Tạo kind cluster**

```bash
kind create cluster --config capstone-infra/local/kind-config.yaml --name capstone-dev

# Expected output:
# Creating cluster "capstone-dev" ...
#  ✓ Ensuring node image (kindest/node:v1.29.0) ...
#  ✓ Preparing nodes ...
#  ✓ Writing configuration ...
#  ✓ Starting control-plane  ...
#  ✓ Installing CNI ...
#  ✓ Installing StorageClass ...
#  ✓ Joining worker nodes ...
# Set kubectl context to "kind-capstone-dev"
```

**Step 3: Verify cluster**

```bash
kubectl get nodes -o wide

# Expected:
# NAME                          STATUS   ROLES           AGE   VERSION
# capstone-dev-control-plane     Ready    control-plane   2m    v1.29.0
# capstone-dev-worker           Ready    worker          1m    v1.29.0
# capstone-dev-worker2          Ready    worker          1m    v1.29.0

kubectl get pods -A

# All pods Running = cluster healthy
```

**Step 4: (Optional) Cài MetalLB cho LoadBalancer**

```bash
# MetalLB cung cấp LoadBalancer IP từ pool local
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# Đợi pods ready
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=120s

# Tạo IP pool (dùng range không conflict)
kubectl apply -f - <<'EOF'
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: first-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.240-192.168.1.250
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: l2advertisement
  namespace: metallb-system
spec:
  ipAddressPools:
  - first-pool
EOF
```

**Step 5: Build + push image vào GHCR**

```bash
export GITHUB_USERNAME="your-github-username"
export GITHUB_TOKEN="ghp_your_token_here"  # Fine-grained token với read:packages, write:packages

# Login GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
# Expected: Login Succeeded

# Build sample app
mkdir -p /tmp/hello-app && cd /tmp/hello-app
cat > Dockerfile <<'EOF'
FROM nginx:alpine
RUN echo '<h1>Hello Capstone Day 30</h1><p>Kubernetes & IAM Layer</p>' > /usr/share/nginx/html/index.html
EOF

docker build -t hello-app:0.1.0 .

# Tag cho GHCR
docker tag hello-app:0.1.0 ghcr.io/$GITHUB_USERNAME/capstone/hello-app:0.1.0

# Push
docker push ghcr.io/$GITHUB_USERNAME/capstone/hello-app:0.1.0
# Expected: Pushed digest sha256:...
```

**Step 6: Tạo imagePullSecret cho GHCR**

```bash
# Tạo secret cho GHCR registry
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=$GITHUB_USERNAME \
  --docker-password=$GITHUB_TOKEN \
  --docker-email=${GITHUB_USERNAME}@users.noreply.github.com \
  --namespace=default

# Tạo ServiceAccount gắn secret này
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: capstone-app-sa
  namespace: default
imagePullSecrets:
- name: ghcr-secret
EOF
```

**Step 7: Test pull image**

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-app
  namespace: default
  labels:
    app: hello-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello-app
  template:
    metadata:
      labels:
        app: hello-app
    spec:
      serviceAccountName: capstone-app-sa
      containers:
      - name: hello-app
        image: ghcr.io/YOUR_USERNAME/capstone/hello-app:0.1.0
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            cpu: "200m"
            memory: "128Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: hello-app-svc
  namespace: default
spec:
  type: LoadBalancer  # MetalLB cấp IP
  selector:
    app: hello-app
  ports:
  - port: 80
    targetPort: 80
EOF

kubectl rollout status deployment hello-app --timeout=60s
kubectl get svc, pods

# Verify image pulled
kubectl describe pod -l app=hello-app | grep "Successfully pulled"
```

**Mode A cleanup:**
```bash
kind delete cluster --name capstone-dev
```

---

### Mode B — EKS + Managed Node Group + IRSA + ECR (Có Cost)

> **WARNING: Cluster này phát sinh ~$115-165/tháng. Cleanup bắt buộc sau lab.**

**Step 1: Tạo EKS module structure**

```bash
mkdir -p terraform/modules/eks terraform/modules/irsa terraform/modules/ecr
```

```hcl
# terraform/modules/eks/main.tf
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_vpc" "selected" {
  id = var.vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  tags = {
    Name = "*private*"  # Adjust tag key per your Day 29 output
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"

  vpc_id                   = var.vpc_id
  subnet_ids               = data.aws_subnets.private.ids
  control_plane_subnet_ids = data.aws_subnets.private.ids

  # IAM role for cluster (control plane)
  iam_role_path                = "/capstone/eks/"
  iam_permissions_boundary     = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/capstone-permissions-boundary"

  eks_managed_node_groups = {
    on-demand-baseline = {
      min_size       = 1
      max_size       = 3
      desired_size   = 1

      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      labels = {
        "node-type" = "on-demand"
        "workload-type" = "general"
      }
      tags = {
        "Environment" = var.env
        "Project"     = "capstone"
      }
    }

    spot-workers = {
      min_size       = 1
      max_size       = 5
      desired_size   = 1

      instance_types = ["t3.medium", "t3.large", "m5.large"]
      capacity_type  = "SPOT"
      labels = {
        "node-type" = "spot"
      }
      taints = [{
        key    = "node.kubernetes.io/lifecycle"
        value  = "spot"
        effect = "NoSchedule"
      }]
      tags = {
        "Environment" = var.env
        "Project"     = "capstone"
      }
    }
  }

  # Enable cluster access entry (EKS 1.28+)
  enable_cluster_creator_admin_permissions = true

  # Tags
  tags = {
    Environment = var.env
    Project     = "capstone"
    ManagedBy   = "terraform"
  }
}

# OIDC provider — terraform-aws-modules/eks tự tạo
# Truyền outputs qua module
```

```hcl
# terraform/modules/eks/variables.tf
variable "vpc_id" {
  description = "VPC ID từ Day 29 output"
  type        = string
}

variable "cluster_name" {
  description = "Tên EKS cluster"
  type        = string
  default     = "capstone-dev"
}

variable "env" {
  description = "Environment"
  type        = string
  default     = "dev"
}
```

```hcl
# terraform/modules/eks/outputs.tf
output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster API server endpoint"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "oidc_provider_url" {
  description = "OIDC provider URL"
  value       = module.eks.oidc_provider_url
}

output "oidc_provider_arn" {
  description = "OIDC provider ARN"
  value       = module.eks.oidc_provider_arn
}

output "cluster_security_group_id" {
  description = "Cluster SG ID"
  value       = module.eks.cluster_security_group_id
}
```

**Step 2: Tạo IRSA roles cho capstone workloads**

```hcl
# terraform/modules/irsa/main.tf
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# Template for IRSA role
module "irsa_template" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${var.project}-${var.env}-${var.service_account_name}"

  role_polices = {
    inline = var.inline_policy_json
  }

  oidc_providers = {
    main = {
      provider_arn = var.oidc_provider_arn
      namespace_service_accounts = ["${var.namespace}:${var.service_account_name}"]
    }
  }
}

resource "aws_iam_role" "this" {
  name = "${var.project}-${var.env}-${var.service_account_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAssumeRoleWithWebIdentity"
        Effect    = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:${var.namespace}:${var.service_account_name}"
          }
        }
      }
    ]
  })

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "this" {
  name = "${var.project}-${var.env}-${var.service_account_name}-policy"
  role = aws_iam_role.this.id

  policy = var.inline_policy_json
}
```

```hcl
# terraform/modules/irsa/variables.tf
variable "namespace"              { type = string }
variable "service_account_name"  { type = string }
variable "oidc_provider_arn"      { type = string }
variable "oidc_provider_url"      { type = string }
variable "project"                { type = string }
variable "env"                    { type = string }
variable "inline_policy_json"    { type = string }
```

```hcl
# terraform/modules/irsa/outputs.tf
output "irsa_role_arn" {
  description = "IRSA Role ARN để gắn vào pod annotation"
  value       = aws_iam_role.this.arn
}
```

**Step 3: Tạo ECR repos có lifecycle policy**

```hcl
# terraform/modules/ecr/main.tf
resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = toset(var.repositories)

  repository = aws_ecr_repository.this[each.value].name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_public_repository" "this" {
  count      = var.create_public ? 1 : 0
  repository_name = var.project
  catalog_data {
    description = "Public registry for ${var.project}"
  }
}

resource "aws_ecr_registry_policy" "allow_cross_account" {
  count = var.allow_cross_account != "" ? 1 : 0

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCrossAccountPull"
        Effect = "Allow"
        Principal = {
          AWS = var.allow_cross_account
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage"
        ]
      }
    ]
  })
}
```

```hcl
# terraform/modules/ecr/variables.tf
variable "project"      { type = string }
variable "env"          { type = string }
variable "repositories" {
  description = "List repo names: [api, worker, frontend]"
  type        = list(string)
  default     = ["api", "worker", "frontend"]
}
variable "create_public"    { type = bool   default = false }
variable "allow_cross_account" { type = string default = "" }
```

```hcl
# terraform/modules/ecr/outputs.tf
output "repository_urls" {
  description = "Map of repo name -> full registry URL"
  value = {
    for repo in aws_ecr_repository.this : repo.name => repo.repository_url
  }
}
```

**Step 4: Root module wiring**

```hcl
# terraform/environments/dev/main.tf
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket = "capstone-terraform-state"
    key   = "eks/eks.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

data "terraform_remote_state" "network" {
  backend = "s3"
  config {
    bucket = "capstone-terraform-state"
    key    = "network/vpc.tfstate"
    region = "us-east-1"
  }
}

module "eks" {
  source = "../../modules/eks"

  vpc_id       = data.terraform_remote_state.network.outputs.vpc_id
  cluster_name = "capstone-dev"
  env          = "dev"
}

# IRSA roles placeholder cho Day 32
module "irsa_alb_controller" {
  source = "../../modules/irsa"

  namespace             = "kube-system"
  service_account_name = "aws-load-balancer-controller"
  oidc_provider_arn     = module.eks.oidc_provider_arn
  oidc_provider_url     = module.eks.oidc_provider_url
  project               = "capstone"
  env                   = "dev"

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeVpcs",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeInstances",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTags",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
        ]
        Resource = "*"
      }
    ]
  })
}

module "irsa_external_secrets" {
  source = "../../modules/irsa"

  namespace             = "external-secrets"
  service_account_name  = "external-secrets"
  oidc_provider_arn     = module.eks.oidc_provider_arn
  oidc_provider_url     = module.eks.oidc_provider_url
  project               = "capstone"
  env                   = "dev"

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "*"  # Restrict in production: "arn:aws:secretsmanager:*:*:secret:capstone/*"
      }
    ]
  })
}

module "ecr" {
  source = "../../modules/ecr"

  project      = "capstone"
  env          = "dev"
  repositories = ["api", "worker", "frontend"]
}

# Output cho Day 32
output "eks_cluster_name"     { value = module.eks.cluster_name }
output "eks_cluster_endpoint" { value = module.eks.cluster_endpoint }
output "eks_oidc_arn"         { value = module.eks.oidc_provider_arn }
output "ecr_repository_urls"  { value = module.ecr.repository_urls }
```

**Step 5: Apply + kubeconfig**

```bash
cd terraform/environments/dev

# Plan trước khi apply
terraform plan -out=plan.tfplan

# Apply — WARNING: phát sinh chi phí ~$115-165/tháng
terraform apply -auto-approve plan.tfplan

# Lấy kubeconfig
aws eks update-kubeconfig \
  --region us-east-1 \
  --name capstone-dev \
  --kubeconfig ../kubeconfig

export KUBECONFIG=$PWD/../kubeconfig

# Verify
kubectl get nodes
kubectl get svcaccount -A
```

**Step 6: Build + push image vào ECR**

```bash
# Login ECR (chuyển account + region)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS \
  --password-stdin ${account_id}.dkr.ecr.us-east-1.amazonaws.com

# Get ECR URL
ECR_URL="${account_id}.dkr.ecr.us-east-1.amazonaws.com"

# Build
cd /tmp/hello-app
docker build -t hello-app:0.1.0 .

# Tag + push cho từng service
for SERVICE in api worker frontend; do
  docker tag hello-app:0.1.0 ${ECR_URL}/capstone/${SERVICE}:0.1.0
  docker push ${ECR_URL}/capstone/${SERVICE}:0.1.0
done
```

**Step 7: Verify image pull với IRSA (optional)**

```bash
# Deploy với IRSA annotation (cần IRSA role ARN từ Step 3)
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ecr-puller-sa
  namespace: default
  annotations:
    eks.amazonaws.com/role-arn: "arn:aws:iam::${account_id}:role/capstone-dev-ecr-puller"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecr-test
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ecr-test
  template:
    metadata:
      labels:
        app: ecr-test
    spec:
      serviceAccountName: ecr-puller-sa
      containers:
      - name: test
        image: ${ECR_URL}/capstone/api:0.1.0
EOF

kubectl rollout status deployment ecr-test --timeout=60s
kubectl describe pod -l app=ecr-test | grep "Successfully pulled"
```

**Step 8: CLEANUP — Bắt buộc**

```bash
# Destroys EKS cluster + all IRSA roles + ECR repos
cd terraform/environments/dev
terraform destroy -auto-approve

# Verify
aws eks list-clusters  # should be empty
```

**Chi phí sau cleanup:** $0

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Sự khác biệt chính giữa managed node group và Karpenter là gì? Khi nào dùng Karpenter?

**Câu 2:** IRSA hoạt động như thế nào? Tại sao dùng IRSA thay vì node IAM role?

**Câu 3:** Debug: Pod có annotation `eks.amazonaws.com/role-arn` nhưng vẫn `ImagePullBackOff`. Liệt kê 5 nguyên nhân có thể.

**Câu 4:** Spot instance reclamation đang xảy ra trên 3 trong 5 node. Làm sao tránh pod eviction storm?

**Câu 5:** Chọn registry cho các trường hợp: (a) startup MVP, (b) enterprise OSS project, (c) học viên cá nhân muốn free. Giải thích.

---

## 7. Tóm tắt cuối ngày

**3-5 ý chính:**
1. EKS = managed control plane (bỏ qua etcd HA, control plane patching), chỉ tập trung vào node + workload.
2. Managed node group + Spot mix = cost-effective production; luôn có baseline On-Demand ≥ 1 node trước khi thêm Spot.
3. IRSA (hoặc Pod Identity) = pod-level IAM, least-privilege, không dùng node IAM role cho workload.
4. OIDC provider là cầu nối EKS ↔ IAM; trust policy phải đúng `namespace:serviceaccount`.
5. ECR cho AWS workloads (IRSA native, lifecycle policy, scan); GHCR cho local/OSS miễn phí.

**Output sau Day 30:**

| File | Mode A (kind) | Mode B (EKS) |
|---|---|---|
| `kind-config.yaml` | ✅ kind cluster 1 control + 2 worker | N/A |
| `kubeconfig` | `kind-capstone-dev` | `aws eks update-kubeconfig` |
| `ghcr-secret` | ✅ imagePullSecret GHCR | N/A |
| ECR repos | N/A | `capstone/api`, `capstone/worker`, `capstone/frontend` |
| IRSA roles | N/A | `capstone-dev-alb-controller`, `capstone-dev-external-secrets` |
| `hello-app` image | GHCR pushed | ECR pushed |
| Day 31 ready | Local K8s cluster | EKS cluster + IAM roles |

**Chuẩn bị Day 31 (Data Layer):**
- Mode A: PostgreSQL + Redis bằng Helm chart (Bitnami)
- Mode B: RDS PostgreSQL + ElastiCache Redis (từ terraform-aws-modules/rds, elasticache)
- External Secrets Operator đọc AWS Secrets Manager (dùng IRSA role đã tạo ở Day 30)
- Connection string management qua Kubernetes Secret hoặc ESO

---

## 8. Tham khảo thêm

- [terraform-aws-modules/eks](https://registry.terraform.io/modules/terraform-aws-modules/eks/aws/latest) ~> 20.0
- [EKS Best Practices — Node Management](https://aws.github.io/aws-eks-best-practices/)
- [EKS Best Practices — IRSA](https://aws.github.io/aws-eks-best-practices/iam/)
- [Karpenter Documentation](https://karpenter.sh/)
- [Pod Identity vs IRSA](https://aws.amazon.com/blogs/containers/introducing-amazon-eks-pod-identity/)
- [kind Documentation](https://kind.sigs.k8s.io/)
- [ECR Lifecycle Policies](https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle-policy.html)
- [Spot Instance Interruption Handling](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
