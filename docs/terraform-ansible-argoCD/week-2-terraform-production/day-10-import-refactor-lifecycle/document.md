# Day 10 - Reference Document: Lifecycle, Import, Moved Blocks

**Muc dich:** Quick reference cho engineer trong khi lam viec. In ra hoac bookmark.

---

## 1. lifecycle Rules - Decision Matrix

### Khi nao dung lifecycle rule nao

| Tinh huong | Rule | Ly do |
|---|---|---|
| Production RDS, CloudSQL, MongoDB Atlas | `prevent_destroy = true` | Data loss = unrecoverable |
| Route53 Hosted Zone | `prevent_destroy = true` | Xoa zone = xoa tat ca DNS records |
| S3 bucket chua state hoac data | `prevent_destroy = true` | Data loss + state corruption |
| KMS Customer Managed Key | `prevent_destroy = true` | Mat key = mat kha nang decrypt data ma key do bao ve |
| EKS Node Group voi Cluster Autoscaler | `ignore_changes = [scaling_config[0].desired_size]` | Autoscaler quan ly desired count |
| RDS instance duoc Secrets Manager rotation password | `ignore_changes = [password]` | SM rotate ngoai Terraform lifecycle |
| ASG voi AWS Auto Scaling quan ly desired | `ignore_changes = [desired_capacity]` | Scaling policy quan ly |
| Security Group bi replace do immutable name | `create_before_destroy = true` | Tranh loi "SG dang duoc dung" |
| ACM Certificate renewal | `create_before_destroy = true` | Validate cert moi truoc khi cut over |
| Launch Template trong ASG | `create_before_destroy = true` | Tao version moi truoc khi ASG pickup |

### lifecycle Block Reference

```hcl
resource "aws_db_instance" "example" {
  # ... config ...

  lifecycle {
    # Ngan terraform destroy resource nay
    prevent_destroy = true

    # Bo qua thay doi tren cac fields nay khi compare
    ignore_changes = [
      password,
      engine_version,
      # Dung all de ignore tat ca (nguy hiem - chi dung khi can thiet)
      # all
    ]

    # Tao resource moi truoc khi xoa resource cu khi replace
    create_before_destroy = true

    # Terraform 1.2+: Dieu kien truoc khi apply
    # precondition {
    #   condition     = var.environment != "production" || var.instance_class != "db.t3.micro"
    #   error_message = "Production DB phai dung instance class lon hon t3.micro."
    # }

    # Terraform 1.2+: Dieu kien sau khi apply
    # postcondition {
    #   condition     = self.status == "available"
    #   error_message = "DB chua san sang sau khi create."
    # }
  }
}
```

---

## 2. terraform import - Workflow Cheat Sheet

### CLI Import (Ad-hoc)

```bash
# Syntax
terraform import <resource_address> <resource_id>

# Vi du
terraform import aws_db_instance.prod my-prod-db-identifier
terraform import aws_s3_bucket.uploads my-company-uploads-2021
terraform import aws_vpc.main vpc-0abc1234def56789a
terraform import aws_instance.web i-0abc1234def56789a
terraform import aws_security_group.alb sg-0abc1234def56789a
terraform import aws_iam_role.app_role my-application-role
terraform import aws_route53_zone.main Z1234567890ABC
terraform import aws_lb.main arn:aws:elasticloadbalancing:us-east-1:123456789:loadbalancer/app/my-alb/abc123

# Target specific module resource
terraform import module.networking.aws_vpc.main vpc-0abc1234

# Target for_each instance
terraform import 'aws_subnet.private["us-east-1a"]' subnet-0abc1234
```

### Import Block (Terraform 1.5+ - Preferred cho Team)

```hcl
# import.tf - commit vao Git, apply, sau do xoa file nay
import {
  to = aws_db_instance.prod
  id = "my-prod-db-identifier"
}

import {
  to = module.networking.aws_vpc.main
  id = "vpc-0abc1234def56789a"
}

# Import vao for_each resource
import {
  to = aws_subnet.private["us-east-1a"]
  id = "subnet-0abc1234def56789a"
}
```

### Import Resource IDs theo AWS Resource Type

| Resource | Import ID | Cach lay ID |
|---|---|---|
| `aws_instance` | Instance ID | `aws ec2 describe-instances --query 'Reservations[].Instances[].InstanceId'` |
| `aws_db_instance` | DB Identifier | `aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier'` |
| `aws_s3_bucket` | Bucket name | `aws s3 ls` |
| `aws_vpc` | VPC ID | `aws ec2 describe-vpcs --query 'Vpcs[].VpcId'` |
| `aws_subnet` | Subnet ID | `aws ec2 describe-subnets --query 'Subnets[].SubnetId'` |
| `aws_security_group` | SG ID | `aws ec2 describe-security-groups --query 'SecurityGroups[].GroupId'` |
| `aws_iam_role` | Role name | `aws iam list-roles --query 'Roles[].RoleName'` |
| `aws_iam_policy` | Policy ARN | `aws iam list-policies --query 'Policies[].Arn'` |
| `aws_route53_zone` | Zone ID | `aws route53 list-hosted-zones --query 'HostedZones[].Id'` |
| `aws_lb` | ALB ARN | `aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerArn'` |
| `aws_eks_cluster` | Cluster name | `aws eks list-clusters --query 'clusters'` |
| `aws_elasticache_cluster` | Cluster ID | `aws elasticache describe-cache-clusters --query 'CacheClusters[].CacheClusterId'` |

### Import Workflow - Step by Step

```
1. Identify resource tren cloud
   aws <service> describe-<resource> --output table

2. Viet HCL config cho resource (TRUOC khi import)
   - Match required attributes
   - Them lifecycle rules ngay tu dau
   - Khong can match moi attribute ngay, se refine sau

3. Chay terraform import
   terraform import <address> <id>

4. Chay terraform plan
   terraform plan

5. Neu plan show changes:
   a. Phan tich moi change trong plan
   b. Neu change la "drift" can fix: update HCL de match reality
   c. Neu change la "improvement" muon apply: OK nhung review ky
   d. Lap lai buoc 4 cho den khi "No changes"

6. Commit HCL va bao cao import hoan thanh

7. Neu dung import block: xoa file import_blocks.tf sau khi apply
```

---

## 3. moved Block - Patterns

### Pattern 1: Doi ten resource

```hcl
# State hien tai: aws_instance.web
# HCL moi:       aws_instance.web_server

moved {
  from = aws_instance.web
  to   = aws_instance.web_server
}
```

### Pattern 2: Dua resource vao module

```hcl
# State hien tai: aws_vpc.main
# HCL moi:       module.networking.aws_vpc.main

moved {
  from = aws_vpc.main
  to   = module.networking.aws_vpc.main
}

moved {
  from = aws_subnet.public["us-east-1a"]
  to   = module.networking.aws_subnet.public["us-east-1a"]
}
```

### Pattern 3: Di chuyen giua modules

```hcl
# State hien tai: module.old_module.aws_security_group.alb
# HCL moi:       module.security.aws_security_group.alb

moved {
  from = module.old_module.aws_security_group.alb
  to   = module.security.aws_security_group.alb
}
```

### Pattern 4: Resource don sang for_each

```hcl
# State hien tai: aws_subnet.private_a, aws_subnet.private_b
# HCL moi:       aws_subnet.private["us-east-1a"], aws_subnet.private["us-east-1b"]

moved {
  from = aws_subnet.private_a
  to   = aws_subnet.private["us-east-1a"]
}

moved {
  from = aws_subnet.private_b
  to   = aws_subnet.private["us-east-1b"]
}
```

### Pattern 5: count sang for_each

```hcl
# State hien tai: aws_instance.worker[0], aws_instance.worker[1]
# HCL moi:       aws_instance.worker["worker-a"], aws_instance.worker["worker-b"]

moved {
  from = aws_instance.worker[0]
  to   = aws_instance.worker["worker-a"]
}

moved {
  from = aws_instance.worker[1]
  to   = aws_instance.worker["worker-b"]
}
```

### moved block vs terraform state mv

| | `moved` block | `terraform state mv` |
|---|---|---|
| Luu trong Git | Co | Khong |
| Hien thi trong `plan` truoc apply | Co ("has moved to") | Khong |
| Team co the review | Co (PR review) | Khong |
| Idempotent | Co | Khong |
| Rollback | Revert commit | Phai chay nguoc lai |
| Audit trail | Git history | Phai log thu cong |
| Su dung trong CI/CD | Co | Phuc tap hon |
| Khi nao dung | Planned refactoring | Emergency fix chi |

---

## 4. Refactoring Safety Checklist

### Truoc khi bat dau

```
[ ] 1. terraform plan = "No changes" (state sach)
       Neu co pending changes, resolve truoc

[ ] 2. Backup state file
       terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate

[ ] 3. Tao feature branch
       git checkout -b refactor/move-resources-to-modules

[ ] 4. Xac nhan terraform version >= 1.1 (cho moved block)
       terraform version

[ ] 5. Xac dinh tat ca resources can di chuyen
       terraform state list > current-state.txt
```

### Trong khi refactor

```
[ ] 6. Viet moved blocks TRUOC khi doi cau truc file
       Dat tat ca moved blocks trong moved.tf rieng

[ ] 7. Doi cau truc HCL (chuyen resources vao module)
       Khong xoa resource blocks, chi move chung

[ ] 8. terraform init (neu them module moi)

[ ] 9. terraform plan
       DUNG neu thay bat ky "to destroy" nao
       Chi proceed neu plan chi show "has moved to"

[ ] 10. Review plan voi dong nghiep
        Khong solo apply production refactoring
```

### Sau khi apply

```
[ ] 11. terraform plan lan cuoi
        Phai la "No changes"

[ ] 12. Verify application functionality
        Health checks, smoke tests

[ ] 13. terraform state list
        Verify addresses dung nhu mong doi

[ ] 14. Commit moved.tf voi comment ngay xoa
        "Safe to delete after: YYYY-MM-DD"

[ ] 15. Schedule PR de xoa moved blocks sau 1 sprint
```

---

## 5. terraform state Commands Reference

```bash
# Xem tat ca resources trong state
terraform state list

# Xem chi tiet mot resource
terraform state show aws_db_instance.prod

# Xem chi tiet resource trong module
terraform state show module.networking.aws_vpc.main

# Xoa resource khoi state (KHONG destroy tren cloud)
terraform state rm aws_instance.old

# Di chuyen resource giua addresses (emergency only)
terraform state mv aws_instance.web aws_instance.web_server
terraform state mv aws_vpc.main module.networking.aws_vpc.main

# Backup state truoc khi thay doi
terraform state pull > backup.tfstate

# Restore state tu backup (nguy hiem)
terraform state push backup.tfstate

# Xem raw state file
terraform state pull | jq .
terraform state pull | jq '.resources[] | select(.type == "aws_db_instance")'

# Force unlock state (khi bi lock do crash)
terraform force-unlock <lock-id>
```

---

## 6. Common Error Messages va Giai Phap

### Error: Instance cannot be destroyed

```
Error: Instance cannot be destroyed
  Resource X has lifecycle.prevent_destroy set, but the plan calls for this resource to be destroyed.
```

**Giai phap:** Xoa hoac set `prevent_destroy = false` trong lifecycle block. Phai la conscious action.

### Error: Provider configuration not present

```
Error: Provider configuration not present
  To work with <resource>, its original provider configuration at
  provider["registry.terraform.io/hashicorp/aws"].alias must be present.
```

**Giai phap xay ra khi import:** HCL chua duoc viet cho resource. Phai viet resource block truoc khi import.

### Error: Resource already managed by Terraform

```
Error: Resource already managed by Terraform
  Terraform is already managing a remote object for <resource>.
```

**Giai phap:** Resource da duoc import truoc do. Chay `terraform state show <address>` de xem current state. Khong can import lai.

### Plan show destroy sau khi refactor

```
Plan: X to add, 0 to change, X to destroy.
```

**Giai phap:**
1. DUNG, khong apply
2. Kiem tra cac addresses trong moved block co chinh xac khong
3. Chay `terraform state list` de xem current addresses
4. So sanh voi `from` address trong moved blocks
5. Sua moved blocks cho dung
6. Chay plan lai

### moved block loi "Source address is not in state"

```
Error: Moved object still exists in configuration
  The moved block "from" address refers to a resource still in configuration.
```

**Giai phap:** `from` address phai la OLD address (khong con trong current code). `to` address phai la NEW address (dang co trong code). Kiem tra lai chiều.

---

## 7. Import Block vs CLI Import - Feature Comparison (Terraform 1.5+)

```
Import Block (terraform 1.5+)          CLI Import
----------------------------------------------
import {                               terraform import \
  to = aws_vpc.main                     aws_vpc.main \
  id = "vpc-0abc123"                    vpc-0abc123
}

Advantages:                            Advantages:
- Version controlled                   - No file creation needed
- Reviewable in PR                     - Fast for single resource
- Plannable (terraform plan)           - Works with all TF versions
- Idempotent
- CI/CD friendly
- No manual state manipulation

Use when:                              Use when:
- Team workflow                        - Emergency/ad-hoc import
- Multiple resources                   - Single resource
- GitOps pipeline                      - Quick verification
- Audit required                       - Terraform < 1.5
```

---

## 8. Terraform Version Feature Timeline

| Version | Feature |
|---|---|
| 1.0 | Stable release, basic lifecycle |
| 1.1 | `moved` block |
| 1.2 | `precondition` / `postcondition` trong lifecycle |
| 1.3 | Optional object attributes |
| 1.4 | Improved error messages |
| 1.5 | `import` block, `check` block |
| 1.6 | `-generate-config-out` voi import block |
| 1.7 | `removed` block (doi xung voi moved, cho removing) |
| 1.8 | Provider-defined functions |
| 1.9 | Variable validation improvements |

**Khuyen cao version constraint:**

```hcl
terraform {
  required_version = ">= 1.5, < 2.0"
}
```
