# Day 30 — Kubernetes & IAM Layer: Exercises

---

## Challenge 1: Migrate Node Group On-Demand → 70% Spot Mix với HA

**Mục tiêu:** Tiết kiệm 50-60% chi phí node mà vẫn đảm bảo HA.

**Yêu cầu:**
- Baseline: 2 On-Demand node (t3.medium) — không bao giờ Spot
- Spot burst: 8 node Spot (diversified across 4 instance families)
- Mỗi deployment phải có `PodDisruptionBudget` với `minAvailable: 1`
- Mỗi pod phải tolerate Spot taint
- Verify: chạy `kubectl get nodes -l node-type=spot` sau khi apply

**Output cần nộp:**
- File `terraform/modules/eks-spot/main.tf` hoàn chỉnh
- File `kubernetes/deployments/api-service.yaml` với PDB + toleration
- Screenshot `kubectl get nodes` sau khi scale

**Hints:**
- Dùng `capacity_type = "SPOT"` trong `eks_managed_node_groups`
- `instance_types` list càng dài → AWS tìm capacity càng dễ
- PDB `minAvailable` = 1 trong multi-replica deployment đảm bảo 0 downtime khi Spot reclaim

---

## Challenge 2: Refactor 5 Pod từ Node IAM Role → IRSA riêng

**Mục tiêu:** Loại bỏ over-privilege, implement least-privilege per workload.

**Scenario:** Capstone có 5 microservice, tất cả đang dùng node IAM role. Cần refactor:

| Service | Cần quyền |
|---|---|
| `api-service` | ECR pull + S3 read `capstone-data-dev/*` |
| `worker-service` | SQS receive message + DynamoDB write |
| `frontend-service` | CloudFront invalidation (scaling disabled) |
| `scheduler-service` | EventBridge put rule + ECS describe task |
| `backup-service` | EFS backup → S3 `capstone-backups/*` |

**Yêu cầu:**
- Tạo 5 IAM role riêng qua terraform (1 role per service account)
- Trust policy: chỉ `system:serviceaccount:capstone:<sa-name>` được assume
- Policy: least-privilege — chỉ resource ARNs cần thiết
- Update Kubernetes manifests để thêm `eks.amazonaws.com/role-arn` annotation
- Không dùng wildcard `Resource = "*"` trừ khi bắt buộc

**Output cần nộp:**
- 5 Terraform files trong `terraform/modules/irsa/services/`
- 5 Kubernetes manifest files với IRSA annotation
- 5 trust policy JSON đã verify

---

## Challenge 3: Multi-Tenancy — 3 Team Share EKS

**Mục tiêu:** Isolate 3 team trên 1 EKS cluster bằng namespace + IRSA + ECR.

**Scenario:** 3 team cần deploy lên 1 EKS:

| Team | Namespace | Service Account | ECR Repo | IAM Role |
|---|---|---|---|---|
| `team-alpha` | `team-alpha` | `team-alpha-app` | `capstone/team-alpha/*` | `capstone-team-alpha-*` |
| `team-beta` | `team-beta` | `team-beta-app` | `capstone/team-beta/*` | `capstone-team-beta-*` |
| `team-gamma` | `team-gamma` | `team-gamma-app` | `capstone/team-gamma/*` | `capstone-team-gamma-*` |

**Yêu cầu:**
- Tạo namespace + RBAC (ResourceQuota + LimitRange) cho từng team
- Tạo IAM role per team với ECR pull permission cho repo riêng
- Team không thể access namespace của team khác
- Tạo ECR repo per team với lifecycle policy giữ 5 images
- Team `team-alpha` có thêm quyền đọc S3 `capstone-shared/*` (chỉ read)
- Không có team nào có `*` trong IAM policy

**Bonus:** Tạo RBAC `Role` + `RoleBinding` thay vì `ClusterRole` + `ClusterRoleBinding`

---

## Challenge 4: Debug "Pod CrashLoopBackOff: NoCredentialProviders"

**Mục tiêu:** Debug và fix IRSA misconfiguration trong 5 bước.

**Given:** Pod đang crash, logs:

```
Failed to pull image "123456789.dkr.ecr.us-east-1.amazonaws.com/capstone/api:0.1.0":
  Error: NoCredentialProviders: no valid providers in chain
```

**Yêu cầu:** Trình bày step-by-step debug process, xác định root cause và fix.

**Expected steps:**
1. Verify pod annotation và service account
2. Verify IRSA role trust policy
3. Verify OIDC provider tồn tại
4. Verify token được mount vào pod
5. Verify STS endpoint accessible từ pod
6. Apply fix bằng Terraform hoặc kubectl

**Output cần nộp:**
- File `debug-flow.md` mô tả 5 bước + command + expected output
- File `fix.yaml` Kubernetes manifest đúng
- File `fix.tf` Terraform snippet cho IRSA role đúng

---

## Challenge 5: Karpenter Migration Plan từ Managed Node Group

**Mục tiêu:** Ước tính cost saving khi migrate từ managed node group sang Karpenter.

**Given current state (managed node group):**
- 3 On-Demand t3.medium × 730h = $91.32/tháng
- 5 Spot t3.medium × 730h × 0.7 = $63.92/tháng
- EKS control plane: $73/tháng
- EBS gp3 (3×20Gi): $6.90/tháng
- **Total: $235.14/tháng**

**Migration plan cần viết:**

| Phần | Nội dung |
|---|---|
| Pre-requisites | EKS 1.29+, Karpenter add-on, instance profile, security group |
| Provisioner design | 2 provisioner (on-demand baseline + spot burst) |
| Node pool configuration | Instance types, AZ diversification |
| Migration steps | 0-downtime migration process |
| Cost estimate (post-migration) | On-demand baseline + spot burst với Karpenter |
| Savings calculation | % savings vs current |
| Risk & rollback plan | Nếu Karpenter fail |
| Monitoring | Karpenter metrics + CloudWatch |

**Output cần nộp:**
- File `karpenter-migration/MIGRATION.md`
- File `karpenter-migration/provisioner-on-demand.yaml`
- File `karpenter-migration/provisioner-spot.yaml`
- File `karpenter-migration/terraform-values.tf`

**Hint:** Karpenter có thể scale to 0 khi idle — cost saving chủ yếu đến từ việc không giữ idle node qua giờ làm.

---

## Bonus Challenge: ECR Cross-Account Replication

**Mục tiêu:** Tạo multi-region ECR replication cho DR scenario.

**Scenario:**
- Account A (prod): `123456789.dkr.ecr.us-east-1.amazonaws.com/capstone/api`
- Account B (dr): replicate tự động từ us-east-1
- Cả 2 account cần pull được image

**Yêu cầu:**
- Account A: tạo ECR repo + replication rule (replicate to us-west-2)
- Account B: tạo cross-account IAM role cho ECR pull
- Account B: verify image available sau khi push vào Account A
- Account A: thêm lifecycle policy giữ 20 images
- Terraform output cả 2 account URLs

**Output cần nộp:**
- File `terraform/modules/ecr-cross-account/main.tf` (account A)
- File `terraform/modules/ecr-cross-account/dr-role.tf` (account B IAM)
- File `kubernetes/dr-deployment.yaml` deploy từ DR registry
- Verification script `verify-replication.sh`

---

## Submission Checklist

Mỗi challenge cần nộp:

- [ ] Source code (Terraform + Kubernetes YAML)
- [ ] Giải thích ngắn (3-5 dòng) tại sao chọn approach đó
- [ ] Ước tính cost thay đổi (nếu có)
- [ ] Expected output sau khi apply

**Total: 5 challenges + 1 bonus. Mỗi challenge = 1 directory trong `exercises/day-30/`**
