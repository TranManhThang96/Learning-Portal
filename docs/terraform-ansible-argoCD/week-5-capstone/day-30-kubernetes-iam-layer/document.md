# Day 30 — Kubernetes & IAM Layer: Reference Document

## 1. EKS Module Input/Output Reference

### terraform-aws-modules/eks v20.x

**Required Inputs:**

| Variable | Type | Description |
|---|---|---|
| `cluster_name` | string | Tên cluster |
| `cluster_version` | string | K8s version (e.g. "1.29") |
| `vpc_id` | string | VPC ID |
| `subnet_ids` | list(string) | Subnet IDs cho node (private recommended) |
| `control_plane_subnet_ids` | list(string) | Subnet cho API server (private recommended) |

**Node Group Variables:**

| Variable | Type | Description |
|---|---|---|
| `eks_managed_node_groups` | map(object) | Managed node group definitions |
| `self_managed_node_groups` | map(object) | Self-managed node group definitions |
| `fargate_profiles` | map(object) | Fargate profile definitions |

**Key Outputs:**

| Output | Description |
|---|---|
| `cluster_name` | Cluster name |
| `cluster_endpoint` | API server URL (sensitive) |
| `cluster_certificate_authority` | CA data (sensitive) |
| `oidc_provider_arn` | ARN của OIDC provider — dùng cho IRSA |
| `oidc_provider_url` | URL của OIDC provider — dùng cho trust policy |
| `cluster_security_group_id` | SG cho control plane ↔ node |
| `eks_managed_node_groups` | Map of node group objects |

**Minimal EKS + Managed Node Group Example:**

```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "capstone-dev"
  cluster_version = "1.29"
  vpc_id          = var.vpc_id
  subnet_ids      = var.private_subnet_ids

  eks_managed_node_groups = {
    default = {
      min_size       = 1
      max_size       = 3
      desired_size   = 1
      instance_types = ["t3.medium"]

      labels = {
        "node-group" = "default"
      }

      taints = []
    }
  }
}
```

---

## 2. Node Group Strategy Decision Tree

```
Start: Bạn cần gì?
│
├─ Stateless workload, cần scale tự động nhanh?
│   └─ K8s version >= 1.27? → YES → Karpenter ✅ (recommended)
│       └─ NO → Managed Node Group với mixed Spot ✅
│
├─ Stateful workload (DB, cache)?
│   └─ On-Demand hoặc Reserved Instance ✅
│   (không dùng Spot cho stateful)
│
├─ Serverless, không muốn quản node?
│   └─ Fargate Profile ✅ (per-pod billing)
│
├─ Enterprise/regulated (bank, healthcare)?
│   └─ Self-managed + Bottlerocket + signed AMI ✅
│   + Hardening theo CIS Benchmark
│
├─ Dev/Test, cần shutdown được?
│   └─ Managed Node Group + ASG scheduled scale-to-0 ✅
│
└─ Batch/ML workload?
    └─ Karpenter + Spot (capacity-optimized) ✅
```

**Managed Node Group vs Self-Managed vs Karpenter vs Fargate:**

| Tiêu chí | Managed NG | Self-Managed | Karpenter | Fargate |
|---|---|---|---|---|
| AMI management | AWS | User | User/AWS | AWS |
| Scaling | ASG | ASG | Provisioner CRD | Pod-level |
| Upgrade process | Rolling update | Manual | Rolling with drain | N/A |
| Spot support | ✅ (flag) | ✅ (manual) | ✅ (native) | ❌ |
| Cost | On-Demand | On-Demand/Spot | Spot-optimized | Per-pod |
| Operational overhead | Low | High | Medium | Lowest |
| Speed to scale | Seconds | Seconds | Seconds | Seconds |
| Custom kernel/AMI | ❌ | ✅ | ✅ | ❌ |
| DaemonSet support | ✅ | ✅ | ✅ | ❌ |

---

## 3. IRSA Setup Checklist

### 3.1 Pre-requisites

- [ ] EKS cluster đã tạo
- [ ] OIDC provider đã tạo (terraform-aws-modules/eks tự động)
- [ ] `eks.amazonaws.com/sts-regional-endpoints=regional` (khuyến nghị)
- [ ] Pod có ServiceAccount
- [ ] IAM policy tối thiểu cần thiết

### 3.2 OIDC Provider Verification

```bash
# Verify OIDC provider tồn tại
aws iam list-open-id-connect-providers | grep $(aws eks describe-cluster \
  --name capstone-dev --query cluster.identity.oidc.issuer --output text \
  | awk -F'/' '{print $NF}')

# Expected: oidc-eks-arn listed

# Verify thumbprint
aws eks describe-cluster --name capstone-dev \
  --query cluster.identity.oidc.issuer --output text
# Output: https://oidc.eks.us-east-1.amazonaws.com/id/XXXXXXXXXX
```

### 3.3 Trust Policy Template

```yaml
# Least-privilege: chỉ 1 namespace + 1 service account được phép
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/oidc.eks.REGION.amazonaws.com/id/CLUSTER_ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.REGION.amazonaws.com/id/CLUSTER_ID:sub": "system:serviceaccount:NAMESPACE:SERVICE_ACCOUNT"
        }
      }
    }
  ]
}
```

---

## 4. IRSA Trust Policy YAML Templates (5 Examples)

### Example 1: External Secrets Operator (ESO)

```hcl
resource "aws_iam_role" "eso" {
  name = "capstone-${var.env}-external-secrets"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:external-secrets:external-secrets"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eso_secretsmanager" {
  name = "eso-secretsmanager"
  role = aws_iam_role.eso.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:ListSecrets"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:capstone/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:*:*:parameter/capstone/*"
      }
    ]
  })
}
```

### Example 2: AWS Load Balancer Controller

```hcl
resource "aws_iam_role" "alb_controller" {
  name = "capstone-${var.env}-alb-controller"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "alb_controller" {
  name = "alb-controller-policy"
  role = aws_iam_role.alb_controller.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeVpcs", "ec2:DescribeSecurityGroups", "ec2:DescribeSubnets",
          "ec2:DescribeTags", "ec2:DescribeVpcs",
          "ec2:DescribeInternetGateways",
          "elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeTags",
          "elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:CreateTargetGroup", "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets",
          "elasticloadbalancing:CreateListener", "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:CreateRule", "elasticloadbalancing:DeleteRule"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### Example 3: Cluster Autoscaler

```hcl
resource "aws_iam_role" "cluster_autoscaler" {
  name = "capstone-${var.env}-cluster-autoscaler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:kube-system:cluster-autoscaler"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name = "cluster-autoscaler-policy"
  role = aws_iam_role.cluster_autoscaler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeScalingActivities",
          "autoscaling:TerminateInstanceInAutoScalingGroup",
          "autoscaling:SetDesiredCapacity",
          "autoscaling:BatchPutScheduledUpdateGroupAction"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["ec2:DescribeLaunchTemplateVersions"]
        Resource = "*"
      }
    ]
  })
}
```

### Example 4: Application đọc S3 bucket

```hcl
resource "aws_iam_role" "app_s3_reader" {
  name = "capstone-${var.env}-app-s3-reader"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:capstone:api-service-account"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "app_s3_reader" {
  name = "app-s3-reader-policy"
  role = aws_iam_role.app_s3_reader.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::capstone-data-${var.env}",
          "arn:aws:s3:::capstone-data-${var.env}/*"
        ]
      }
    ]
  })
}
```

### Example 5: EBS CSI Driver

```hcl
resource "aws_iam_role" "ebs_csi_driver" {
  name = "capstone-${var.env}-ebs-csi-driver"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.oidc_provider_url}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "ebs_csi_driver" {
  name = "ebs-csi-driver-policy"
  role = aws_iam_role.ebs_csi_driver.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateVolume", "ec2:AttachVolume", "ec2:DetachVolume",
          "ec2:DeleteVolume", "ec2:DescribeVolumes", "ec2:DescribeSnapshots",
          "ec2:CreateSnapshot", "ec2:DeleteSnapshot", "ec2:ModifyVolume"
        ]
        Resource = "*"
      }
    ]
  })
}
```

---

## 5. Pod Identity vs IRSA Comparison

| Tiêu chí | IRSA | Pod Identity (EKS 1.27+) |
|---|---|---|
| Setup complexity | Medium (OIDC provider + trust policy) | Low (IAM role + agent) |
| No OIDC mount on pod | ❌ Token mounted | ✅ Agent fetches |
| Cluster version | K8s 1.14+ | EKS 1.27+ recommended |
| Permission boundary | Via IAM trust policy | Via IAM role |
| Multi-account | Complex | Easier |
| EKS Add-on | ❌ | ✅ `eks/pod-identity-agent` |
| `sts:AssumeRoleWithWebIdentity` | ✅ Required | ❌ Not used |
| Audit (CloudTrail) | STS events | AssumeRole events |
| Migration path | IRSA → Pod Identity | Pod Identity → |

**Pod Identity Setup:**

```hcl
# Terraform: tạo Pod Identity Association
resource "aws_eks_pod_identity_association" "app" {
  cluster_name    = module.eks.cluster_name
  namespace       = "capstone"
  service_account = "api-service-account"
  role_arn        = aws_iam_role.app.arn
}
```

```yaml
# Pod annotation không cần nữa với Pod Identity
# Chỉ cần ServiceAccount tồn tại
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-service-account
  namespace: capstone
```

---

## 6. Spot Strategy Reference

### 6.1 Mixed Instances Policy (Managed Node Group)

```hcl
eks_managed_node_groups = {
  spot_mixed = {
    min_size       = 2
    max_size       = 10
    desired_size   = 2

    instance_types = ["t3.medium", "t3.large", "m5.large", "m5.xlarge", "c5.large"]
    capacity_type  = "SPOT"

    labels = { "node-type" = "spot" }
    taints = [
      {
        key    = "node.kubernetes.io/lifecycle"
        value  = "spot"
        effect = "NoSchedule"
      }
    ]
  }

  baseline_on_demand = {
    min_size       = 1
    max_size       = 1
    desired_size   = 1
    instance_types = ["t3.medium"]
    capacity_type  = "ON_DEMAND"

    labels = { "node-type" = "on-demand" }
  }
}
```

### 6.2 Spot Allocation Strategy

| Strategy | Use case | Description |
|---|---|---|
| `lowest-price` | Dev/test batch | Rẻ nhất, không quan tâm capacity |
| `capacity-optimized` | Production stateful | AWS chọn pool có capacity tốt nhất |
| `capacity-optimized-priority` | Mixed | Prioritize theo instance family |

### 6.3 Pod Tolerance + Node Affinity (Spot)

```yaml
# Deployment spec
spec:
  template:
    spec:
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
                operator: "In"
                values: ["on-demand"]
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: api-service
              topologyKey: topology.kubernetes.io/zone
```

---

## 7. ECR vs GHCR Comparison + Lifecycle Policy

### 7.1 Comparison Matrix

| Tiêu chí | ECR Private | ECR Public | GHCR Private | GHCR Public |
|---|---|---|---|---|
| Cost storage | $0.09/GB-tháng | Free | N/A | Free |
| Cost bandwidth | $0.09/GB | Free | ~$0.25/GB (private) | Free |
| Vulnerability scan | ✅ Basic free | ❌ | ❌ | ❌ |
| IAM auth | ✅ Native | ❌ | ❌ (GitHub token) | N/A |
| IRSA compatible | ✅ | ❌ | ❌ | ❌ |
| Lifecycle policy | ✅ | ❌ | ❌ | ❌ |
| Cross-region | ECR Dublicate or Replication | N/A | N/A | ✅ |
| Cross-account | ECR Replication | ✅ | ❌ | ✅ |
| Image tag mutability | MUTABLE/IMMUTABLE | N/A | MUTABLE | MUTABLE |

### 7.2 ECR Lifecycle Policy Template

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Expire untagged images older than 14 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countNumber": 14,
        "countUnit": "days"
      },
      "action": {
        "type": "expire"
      }
    },
    {
      "rulePriority": 2,
      "description": "Keep only last 10 tagged images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["v"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {
        "type": "expire"
      }
    }
  ]
}
```

---

## 8. kind Config Template

```yaml
# capstone-infra/local/kind-config.yaml
# kind: Cluster — multi-node cluster cho local development
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: capstone-dev
networking:
  apiServerAddress: "127.0.0.1"
  apiServerPort: 6443
  # Disable default CNI (dùng Calico/Bird)
  disableDefaultCNI: false
  podSubnet: "10.244.0.0/16"
  serviceSubnet: "10.96.0.0/16"
  kubeProxyMode: "iptables"  # or "ipvs"
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
      [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
        endpoint = ["https://registry-1.docker.io"]
      [plugins."io.containerd.grpc.v1.cri".registry.mirrors."ghcr.io"]
        endpoint = ["https://ghcr.io"]
nodes:
- role: control-plane
  labels:
    node-role: control-plane
    node.kubernetes.io/exclude-from-external-load-balancers: "true"
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
  - containerPort: 443
    hostPort: 6443
    protocol: TCP
- role: worker
  labels:
    node-role: worker
    workload-type: general
  kubeadmConfigPatches:
  - |
    kind: JoinConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=worker,workload-type=general"
- role: worker
  labels:
    node-role: worker
    workload-type: general
  kubeadmConfigPatches:
  - |
    kind: JoinConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "node-role=worker,workload-type=general"
```

---

## 9. Cost Optimization Checklist

- [ ] **Bật Spot** cho worker node (tiết kiệm 60-70%)
- [ ] **Baseline On-Demand ≥ 1** node trước khi dùng Spot
- [ ] **EKS cluster tắt** ngoài giờ làm (ASG schedule `desired_size=0` on-demand node)
- [ ] **Dev cluster: single AZ** (giảm cross-AZ data transfer)
- [ ] **Bỏ NAT Gateway** trong dev: dùng VPC endpoint cho ECR + S3
- [ ] **ECR lifecycle policy** giữ ≤ 10 images mỗi repo
- [ ] **EBS gp3** thay gp2 (10% cheaper, 4x throughput)
- [ ] **Dev không cần Ingress** (ClusterIP + port-forward là đủ)
- [ ] **Graviton instance** nếu workload support (20% cheaper, better perf)
- [ ] **RI/Savings Plan** cho baseline On-Demand dài hạn
- [ ] **Karpenter** thay managed node group (tự scale to 0 khi idle)
- [ ] **Cleanup** EKS + node + EBS sau lab (terraform destroy)

---

## 10. Anti-Patterns (Top 12)

| # | Anti-pattern | Vấn đề | Best practice |
|---|---|---|---|
| 1 | Node IAM role dùng cho tất cả pod | Over-privilege, blast radius lớn | IRSA per workload |
| 2 | Cluster không có OIDC provider | IRSA không hoạt động | terraform-aws-modules/eks tự tạo |
| 3 | IRSA trust policy dùng wildcard `*` | Audit fail, security risk | `namespace:serviceaccount` cụ thể |
| 4 | Spot node không có toleration | Pod evict storm | `toleration: spot` + on-demand baseline |
| 5 | Chỉ có Spot node (0 On-Demand) | Spot reclaim = 0 node = outage | Baseline On-Demand ≥ 1 |
| 6 | ECR không lifecycle policy | Storage cost tăng vô hạn | Giữ ≤ 10 images |
| 7 | Dùng access key trong pod | Security audit fail, key rotation khó | IRSA |
| 8 | Public subnet cho EKS node | Security risk | Private subnet only |
| 9 | Không có PodDisruptionBudget | Spot reclaim = downtime | PDB `minAvailable: 1` |
| 10 | kind cluster với 1 worker | Không realistic, failover test không work | ≥ 2 worker nodes |
| 11 | Không tag resources | Cost allocation không rõ, cleanup khó | Tag all: Environment, Project, Owner |
| 12 | Apply terraform không plan | Production fail | Always `terraform plan` before `apply` |

---

## 11. Common Errors & Fixes

### Error 1: `ImagePullBackOff` — "no credential providers"

**Nguyên nhân:**
1. `imagePullSecrets` không được gắn vào ServiceAccount hoặc Pod
2. GHCR: token hết hạn
3. ECR: `aws ecr get-login-password` chưa chạy
4. ECR: Pod không có IRSA annotation (không pull được private ECR)

**Fix:**
```bash
# GHCR: kiểm tra secret tồn tại
kubectl get secret ghcr-secret
kubectl get serviceaccount capstone-app-sa -o jsonpath='{.imagePullSecrets}'

# ECR: kiểm tra IRSA annotation
kubectl get pod <pod-name> -o jsonpath='{.spec.serviceAccountName}'
# Lấy service account
SA=$(kubectl get pod <pod-name> -o jsonpath='{.spec.serviceAccountName}')
# Kiểm tra annotation
kubectl get sa $SA -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}'
```

### Error 2: `CrashLoopBackOff: NoCredentialProviders`

**Nguyên nhân:**
1. IRSA annotation sai role ARN
2. Trust policy sai `sub` condition (namespace/serviceaccount không đúng)
3. OIDC provider không tồn tại hoặc sai thumbprint
4. Pod không có `eks.amazonaws.com/sts-regional-endpoints=regional`

**Fix — IRSA Debug Flow:**
```bash
# 1. Verify OIDC provider
aws iam list-open-id-connect-providers | grep EKS_CLUSTER_ID

# 2. Verify IRSA role trust policy
aws iam get-role --role-name capstone-dev-external-secrets | \
  jq '.Role.AssumeRolePolicyDocument'

# Expected: Condition.StringEquals."oidc.eks...:sub" = "system:serviceaccount:..."

# 3. Verify pod annotation
kubectl get pod <pod> -o jsonpath='{.spec.serviceAccountName}'
kubectl get sa <sa> -o jsonpath='{.metadata.annotations}'
# Hoặc check pod annotation
kubectl get pod <pod> -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}'

# 4. Verify token mounted trong pod
kubectl exec <pod> -- cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token | \
  head -c 100

# 5. Test STS trực tiếp từ pod
kubectl exec <pod> -- sh -c 'curl -s http://169.254.169.254/latest/api/token'
# Should return token (metadata service accessible)
```

### Error 3: Spot Interruption Misconfiguration

**Symptom:** Pod bị evicted liên tục, không reschedule được.

**Fix:**
```bash
# Kiểm tra node taint
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'

# Verify pod tolerates spot taint
kubectl get pod <pod> -o jsonpath='{.spec.tolerations}'

# Nếu không có: add toleration
kubectl patch deployment <app> -p '{"spec":{"template":{"spec":{"tolerations":[{"key":"node.kubernetes.io/lifecycle","operator":"Equal","value":"spot","effect":"NoSchedule"}]}}}}'
```

### Error 4: EKS `update-kubeconfig` fails — "invalid endpoint"

**Fix:**
```bash
# Dùng regional endpoint
aws eks update-kubeconfig \
  --name capstone-dev \
  --region us-east-1 \
  --region-specific-endpoint

# Verify cluster tồn tại
aws eks list-clusters --region us-east-1

# Verify kubectl context
kubectl config get-contexts
```

### Error 5: ECR `get-login-password` fails — "NoCredentialProviders"

**Fix:**
```bash
# Xác định region đúng
aws configure get region

# Login với đúng region
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS \
  --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
```
