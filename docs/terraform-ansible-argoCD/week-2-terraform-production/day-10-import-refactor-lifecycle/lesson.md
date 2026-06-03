# Day 10: Lifecycle, Import, Moved Blocks - Refactor Khong Downtime

**Thoi gian:** 2 gio | **Level:** Intermediate-Advanced | **Phase:** 2 - Terraform Production, Day 4
**Prerequisites:** Day 6-7 (Modules), Day 8 (Multi-env), Day 9 (for_each/dynamic blocks)

---

## 1. Muc tieu ngay hoc

Sau buoi hoc nay, ban co the:

1. Giai thich su khac biet giua ba lifecycle rules (`prevent_destroy`, `ignore_changes`, `create_before_destroy`) va cho biet tinh huong thuc te nao can dung tung rule
2. Thuc hien `terraform import` de dua mot resource co san (da ton tai tren cloud) vao quan ly boi Terraform, bao gom viet config tuong ung va verify khong co drift
3. Viet `moved` block de di chuyen resource address trong state file ma khong xoa va tao lai resource (zero-downtime refactoring)
4. Refactor resources tu root module vao child module bang `moved` block, verify `terraform plan` cho ket qua `0 to add, 0 to destroy`
5. Phan tich rui ro va lua chon dung Strategy (import block vs CLI import, moved block vs `terraform state mv`) cho tung tinh huong refactor production

---

## 2. Boi canh thuc te

### Van de: Refactor Terraform code gay destroy production

Ban la Platform Engineer tai mot fintech company. Team da chay Terraform tu 6 thang truoc, nhung code duoc viet nhanh theo kieu "just get it working". Bay gio co nhiem vu:

**Tinh huong 1 - Legacy resource nam ngoai Terraform:**

Truoc khi co Terraform, DevOps team tao mot RDS PostgreSQL instance bang tay tren AWS Console. Database nay dang chay production voi 50GB data. Yeu cau: dua database nay vao Terraform de quan ly - nhung khong duoc gian doan service, khong duoc mat data.

**Tinh huong 2 - Code refactoring gay recreate:**

Platform team refactor Terraform code, chuyen cac resource tu root module vao module rieng (`module.networking`, `module.database`). Sau khi doi cau truc thu muc va chay `terraform plan`, output hien thi:

```
Plan: 12 to add, 0 to change, 12 to destroy.
```

12 resources bi destroy trong do co production RDS, production ElastiCache, production Load Balancer. Dieu nay xay ra vi khi resource address thay doi (vi du tu `aws_instance.web` sang `module.compute.aws_instance.web`), Terraform khong biet day la cung mot resource - no tinh la delete cai cu va create cai moi.

**Tinh huong 3 - Production incident tu lifecycle mismanagement:**

Engineer thuc hien `terraform destroy` de cleanup dev environment. Script chay `terraform destroy -var-file=dev.tfvars` nhung target sai workspace. Production RDS bi destroy vi khong co `prevent_destroy`. Recovery mat 6 tieng tu backup, mat du lieu 2 tieng cuoi.

**Postmortem findings:**
- Khong co `prevent_destroy` tren database resources
- Khong co pipeline gate kiem tra workspace truoc khi destroy
- `ignore_changes` khong duoc dung cho RDS `engine_version` nen upgrade minor version bi plan lai

### Day la ly do Day 10 ton tai

Ba kien thuc hom nay (lifecycle, import, moved) giai quyet truc tiep ba class of problems tren. Day khong phai theory - day la production survival skills.

---

## 3. Kien thuc nen tang - 30 phut

### 3.1 lifecycle Block

`lifecycle` la meta-argument co the them vao bat ky resource nao. No nam trong block `resource {}` va chi anh huong den cach Terraform quan ly vong doi cua resource do.

```hcl
resource "aws_db_instance" "postgres" {
  identifier = "prod-postgres"
  # ... config ...

  lifecycle {
    prevent_destroy       = true
    ignore_changes        = [password, engine_version]
    create_before_destroy = true
  }
}
```

#### prevent_destroy

**Lam gi:** Ngan Terraform thuc hien destroy resource nay. Neu plan co destroy resource duoc danh dau `prevent_destroy = true`, Terraform se bao loi va khong apply.

**Loi bao la:**

```
Error: Instance cannot be destroyed
  on main.tf line 12, in resource "aws_db_instance" "postgres":
  Resource aws_db_instance.postgres has lifecycle.prevent_destroy set,
  but the plan calls for this resource to be destroyed.
```

**Khi nao dung:**
- Database instances (RDS, CloudSQL, MongoDB Atlas)
- DNS zones (Route53 Hosted Zone - delete zone = delete tat ca records)
- S3 buckets chua data production
- KMS keys (xoa KMS key = mat kha nang decrypt data duoc encrypt bang no)
- IAM roles duoc dung boi nhieu service

**Khi nao KHONG dung:**
- Resources duoc design de tao/xoa thuong xuyen (Lambda versions, ECS task definitions)
- Resources trong dev/test environment (ngay chan iteration cycle)
- Resources co the khoi phuc de dang tu snapshot

**Quan trong:** `prevent_destroy = true` chi ngan destroy qua Terraform. No KHONG ngan delete thu cong tren AWS Console hoac AWS CLI. Day khong phai security control, day la safety net cho workflow.

**Trade-off:** Neu that su can destroy (vi du: xoa environment), phai sua code bo `prevent_destroy` truoc, commit, apply, roi moi destroy. Day la friction co chu y - buoc ban phai consciously confirm "toi muon destroy cai nay".

#### ignore_changes

**Lam gi:** Chi dinh mot list attributes ma Terraform se bo qua khi diff. Neu attribute do thay doi ben ngoai Terraform (qua Console, qua API, qua automation khac), Terraform se khong tinh la drift va khong plan update.

```hcl
resource "aws_eks_node_group" "workers" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "workers"
  scaling_config {
    desired_size = 3
    min_size     = 1
    max_size     = 10
  }

  lifecycle {
    ignore_changes = [
      scaling_config[0].desired_size,  # Quan ly boi Cluster Autoscaler
    ]
  }
}
```

**Trong vi du tren:** Cluster Autoscaler tu dong tang `desired_size` len 6 khi traffic cao. Neu khong co `ignore_changes`, lan sau chay `terraform apply`, Terraform se thay "desired_size la 6 tren cloud nhung 3 trong code" va plan reduce xung 3 - override quyen Autoscaler.

**Cac truong hop dung pho bien:**

| Resource | Attribute nen ignore | Ly do |
|---|---|---|
| `aws_eks_node_group` | `scaling_config[0].desired_size` | Cluster Autoscaler quan ly |
| `aws_db_instance` | `password` | Quan ly boi Secrets Manager rotation |
| `aws_db_instance` | `engine_version` | AWS tu dong patch minor version |
| `aws_elastic_beanstalk_environment` | `solution_stack_name` | Managed platform updates |
| `aws_autoscaling_group` | `desired_capacity` | AWS Auto Scaling quan ly |
| `aws_instance` | `ami` | Khong muon replace instance khi AMI update |

**Dung tat ca attributes:**

```hcl
lifecycle {
  ignore_changes = all
}
```

Day la "nuclear option" - Terraform se khong bao gio update resource nay du co gi thay doi. Chi dung khi resource hoan toan duoc quan ly boi he thong khac va Terraform chi dung de track existence.

**Pitfall nghiem trong:** `ignore_changes` co the mask drift. Neu config quan trong thay doi do loi (ai do sua Security Group rules tren Console), Terraform se im lang bo qua. Can co monitoring ngoai Terraform (AWS Config, Drift detection) de catch nhung truong hop nay.

#### create_before_destroy

**Lam gi:** Dao nguoc thu tu default cua Terraform trong replace operation. Default: destroy cai cu -> create cai moi. Voi `create_before_destroy`: create cai moi -> destroy cai cu.

**Khi nao can thiet:**

Tinh huong: Ban cap nhat `aws_security_group` da duoc attach vao Load Balancer. Terraform can replace SG (vi SG name thay doi, name la immutable). Default flow:

1. Destroy SG cu -> FAIL vi SG dang duoc attach vao ALB, AWS khong cho xoa SG dang su dung
2. Loi, rollback

Voi `create_before_destroy`:

1. Tao SG moi
2. (Thu cong hoac qua dependency): update ALB attach SG moi
3. Xoa SG cu -> OK vi SG cu khong con attachment

```hcl
resource "aws_security_group" "alb" {
  name   = "alb-sg-${var.environment}"
  vpc_id = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}
```

**Truong hop dung khac:**

- `aws_acm_certificate`: Phai tao cert moi truoc, validate, gan vao listener, roi moi xoa cert cu
- `aws_launch_template`: Khi update ASG, tao launch template version moi truoc
- `aws_s3_bucket`: Khi doi bucket name (phai xoa empty bucket truoc, nhung neu co data thi phai migrate)

**Trade-off:** `create_before_destroy` co the gay naming conflict neu resource moi va cu co cung ten. Giai phap: dung `name_prefix` thay `name` (AWS tu generate unique suffix).

```hcl
resource "aws_security_group" "alb" {
  name_prefix = "alb-sg-${var.environment}-"  # Khong dung name
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}
```

**Dependency chain:** `create_before_destroy` propagate. Neu resource A co `create_before_destroy` va resource B depend vao A, B cung se duoc create before destroy du khong declare lifecycle do.

### 3.2 terraform import

`terraform import` la cach dua mot resource da ton tai tren cloud vao duoc quan ly boi Terraform state, ma khong xoa va tao lai resource.

**Analogy voi database migration:**

```
Truoc import: Resource ton tai tren cloud, khong co trong .tfstate
Sau import:   Resource ton tai tren cloud, duoc track trong .tfstate

Tuong tu nhu:
ALTER TABLE          -> Import resource (khong mat data)
vs
DROP TABLE; CREATE TABLE -> terraform destroy + apply (mat data)
```

**Import workflow co hai buoc:**

**Buoc 1: Viet resource config trong .tf file**

Terraform import chi cap nhat state file. No KHONG tu dong generate code. Ban phai tu viet HCL config tuong ung voi resource dang chay.

```hcl
# phai viet thu cong truoc khi import
resource "aws_s3_bucket" "legacy_uploads" {
  bucket = "my-company-uploads-prod-2021"
}
```

**Buoc 2: Chay terraform import**

```bash
terraform import aws_s3_bucket.legacy_uploads my-company-uploads-prod-2021
#               <resource_address>             <resource_id_tren_cloud>
```

Resource ID format khac nhau theo resource type. Phai doc documentation cua tung resource. Vi du:

| Resource Type | Import ID format | Example |
|---|---|---|
| `aws_s3_bucket` | bucket name | `my-company-uploads-prod` |
| `aws_db_instance` | identifier | `prod-postgres-01` |
| `aws_vpc` | VPC ID | `vpc-0abc123def456789` |
| `aws_instance` | Instance ID | `i-0abc123def456789` |
| `aws_security_group` | SG ID | `sg-0abc123def456789` |
| `aws_iam_role` | role name | `my-service-role` |

**Sau import - verify drift:**

```bash
terraform plan
```

Neu HCL config khop voi actual resource config tren cloud: `No changes. Your infrastructure matches the configuration.`

Neu co sai khac, plan se show diff. Ban phai sua HCL cho den khi plan sach. Day la buoc quan trong nhat va kho nhat trong import workflow.

**Import block (Terraform 1.5+):**

Trong Terraform 1.5, HashiCorp gioi thieu khai bao import bang block thay vi CLI command. Day la approach duoc khuyen cao cho team work vi co the track trong Git.

```hcl
# import.tf
import {
  to = aws_s3_bucket.legacy_uploads
  id = "my-company-uploads-prod-2021"
}
```

Voi Terraform 1.6+, co them `generate = true` de tu dong generate config (experimental):

```hcl
import {
  to = aws_s3_bucket.legacy_uploads
  id = "my-company-uploads-prod-2021"
}
```

Chay:
```bash
terraform plan -generate-config-out=generated.tf
```

Terraform se generate HCL vao file `generated.tf`. Review, clean up, move vao dung file. Day la shortcut huu ich nhung output thuong verbose va can edit lai.

### 3.3 moved Block

`moved` block la cach bao Terraform rang resource da doi address trong state file, ma khong destroy va create lai.

**Van de no giai quyet:**

Khi ban refactor code, resource address thay doi:
- Doi ten resource: `aws_instance.web` -> `aws_instance.web_server`
- Dua vao module: `aws_instance.web` -> `module.compute.aws_instance.web`
- Doi tu resource don sang for_each: `aws_subnet.private` -> `aws_subnet.private["us-east-1a"]`

Terraform khong biet day la cung resource - no chi thay "address A bien mat, address B xuat hien" va tinh la destroy A, create B.

**moved block cu phap:**

```hcl
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}
```

Terraform doc block nay va hieu: "address `aws_instance.web` trong state da duoc doi thanh `module.compute.aws_instance.web`. Dung destroy-create."

**Cac pattern pho bien:**

**Pattern 1: Doi ten resource**
```hcl
moved {
  from = aws_s3_bucket.data
  to   = aws_s3_bucket.application_data
}
```

**Pattern 2: Dua resource vao module**
```hcl
moved {
  from = aws_vpc.main
  to   = module.networking.aws_vpc.main
}

moved {
  from = aws_subnet.public
  to   = module.networking.aws_subnet.public
}
```

**Pattern 3: Doi tu resource don sang for_each**
```hcl
# Truoc: resource don
resource "aws_subnet" "private_a" { ... }

# Sau: for_each
resource "aws_subnet" "private" {
  for_each = toset(["us-east-1a", "us-east-1b"])
  ...
}

# moved block de map:
moved {
  from = aws_subnet.private_a
  to   = aws_subnet.private["us-east-1a"]
}
```

**moved block vs terraform state mv:**

| Tieu chi | moved block | terraform state mv |
|---|---|---|
| Track trong Git | Co (.tf file) | Khong (chi su dung CLI) |
| Co the review truoc khi apply | Co (xuat hien trong plan) | Khong (apply ngay) |
| Lam viec voi remote state | Co | Co |
| Require Terraform version | 1.1+ | Moi version |
| Team workflow | Tot hon | Kho audit |
| Rollback | Xoa moved block | Phai chay state mv nguoc lai |

**Khuyen cao:** Trong team environment, luon dung `moved` block thay vi `terraform state mv`. `terraform state mv` la escape hatch khi can sua loi khan cap, khong phai workflow chuan.

**Khi nao xoa moved block:**

`moved` block nen giu lai trong it nhat mot cycle apply sau khi moi nguoi trong team da apply. Sau do co the xoa. Neu xoa qua som, nguoi chua apply se gap "address cu da bien mat, plan destroy".

Convention tot: Giu moved blocks trong 1-2 sprints, comment ngay tao, xoa trong sprint tiep theo sau khi xac nhan moi nguoi da apply.

```hcl
# moved block - added 2024-01-15, safe to remove after 2024-02-01
moved {
  from = aws_vpc.main
  to   = module.networking.aws_vpc.main
}
```

---

## 4. Deep dive & Trade-offs - 30 phut

### 4.1 Import Strategies So Sanh

**CLI import (terraform import):**

```
Pro:
- Nhanh voi resource don le
- Khong can commit gi truoc khi import

Con:
- Khong co trong Git history
- Phai import tung resource mot
- De quen (ai on call import roi dap tat fire, khong ai biet)
- Khong testable (khong chay duoc trong CI)
```

**Import block (Terraform 1.5+):**

```
Pro:
- Track trong Version Control
- Chay duoc trong CI/CD
- Co the planning truoc khi apply
- Idempotent (apply nhieu lan an toan)
- Phu hop voi GitOps workflow

Con:
- Require Terraform >= 1.5
- Import block phai xoa sau khi import xong (neu de lai, re-apply van OK nhung messy)
```

**Khuyen cao chon:**

- Import < 3 resources, khan cap: CLI import
- Import >= 3 resources, co planning: Import block
- Team co GitOps workflow: luon dung Import block

### 4.2 Refactoring Safety Checklist

Truoc khi bat dau bat ky refactoring nao tren production:

```
[ ] 1. Terraform state backup
       terraform state pull > backup-$(date +%Y%m%d-%H%M%S).tfstate

[ ] 2. Xac nhan current state sach
       terraform plan -> phai la "No changes"
       Neu co changes, resolve truoc khi refactor

[ ] 3. Tao feature branch
       Moi refactor trong Git branch rieng, khong lam tren main

[ ] 4. Viet moved blocks TRUOC khi doi cau truc file

[ ] 5. Terraform plan -> verify "0 to destroy"
       Neu co bat ky destroy nao, STOP va investigate

[ ] 6. Peer review plan output
       Khong apply solo voi production refactoring

[ ] 7. Apply trong gio thap diem (low traffic window)

[ ] 8. Verify post-apply
       terraform plan -> phai la "No changes" sau apply

[ ] 9. Giu moved blocks it nhat 1 sprint truoc khi xoa
```

### 4.3 Risk Assessment cho Production Refactoring

**Rui ro thap - Co the lam bat ky luc nao:**
- Them lifecycle rules (`prevent_destroy`, `ignore_changes`)
- Doi output names (chi phai cap nhat references)
- Them variable voi default values
- Viet moved blocks (khong apply, chi plan)

**Rui ro trung - Can change window:**
- Apply moved blocks tren production
- Import resources moi vao state
- Refactor module structure voi moved blocks da verify

**Rui ro cao - Can approval va rollback plan:**
- Xoa `prevent_destroy` truoc khi destroy
- Import va immediately apply changes
- `terraform state rm` (xoa resource khoi state ma khong destroy)
- Refactor co involve `for_each` key changes

### 4.4 Common Pitfalls

**Pitfall 1: Quen `prevent_destroy` tren database**

Pattern thay o production incidents:

```hcl
# WRONG - Khong co lifecycle protection
resource "aws_db_instance" "prod" {
  identifier = "prod-postgres"
  # ...
}

# CORRECT
resource "aws_db_instance" "prod" {
  identifier = "prod-postgres"
  # ...

  lifecycle {
    prevent_destroy = true
  }
}
```

Rule of thumb: Bat ky resource nao chua persistent data hoac la dependency cua service khac deu phai co `prevent_destroy`.

**Pitfall 2: import xong khong check plan**

Sau `terraform import`, nhieu engineer nghi la xong. Thuc te, state da duoc cap nhat nhung HCL co the khong khop voi actual config. Lan sau apply co the conflict.

```bash
# WRONG workflow
terraform import aws_db_instance.prod prod-postgres-01
# "Import successful!" - OK done

# CORRECT workflow
terraform import aws_db_instance.prod prod-postgres-01
terraform plan  # <- PHAI check
# Neu co diff, sua HCL cho den khi "No changes"
```

**Pitfall 3: `ignore_changes` masking configuration drift**

```hcl
resource "aws_security_group" "app" {
  name = "app-sg"
  
  lifecycle {
    ignore_changes = [ingress, egress]  # NGUY HIEM
  }
}
```

Ai do them inbound rule 0.0.0.0/0:22 qua Console. `ignore_changes` se bo qua. Terraform plan se khong canh bao. Security hole ton tai im lang.

**Giai phap:** Dung `ignore_changes` ca ngo voi cac attributes cu the, khong phai entire blocks. Combine voi AWS Config rules detect SG changes.

**Pitfall 4: moved block wrong direction**

```hcl
# WRONG - Dao nguoc from/to
moved {
  from = module.compute.aws_instance.web  # Day la NEW address
  to   = aws_instance.web                 # Day la OLD address
}
```

Terraform se co gang tim `module.compute.aws_instance.web` trong current state (khong co), va thay resource `aws_instance.web`. Ket qua: plan show destroy `aws_instance.web`.

```hcl
# CORRECT
moved {
  from = aws_instance.web          # OLD address (con trong state hien tai)
  to   = module.compute.aws_instance.web  # NEW address (trong code moi)
}
```

**Pitfall 5: for_each key changes destroy instances**

```hcl
# Truoc
resource "aws_subnet" "private" {
  for_each = {
    "zone-a" = "10.0.1.0/24"
    "zone-b" = "10.0.2.0/24"
  }
  # ...
}

# Sau - doi key naming convention
resource "aws_subnet" "private" {
  for_each = {
    "us-east-1a" = "10.0.1.0/24"  # KEY THAY DOI
    "us-east-1b" = "10.0.2.0/24"  # KEY THAY DOI
  }
  # ...
}
```

Terraform thay "zone-a" bi xoa, "us-east-1a" duoc them. Plan show destroy + create. Phai dung moved block:

```hcl
moved {
  from = aws_subnet.private["zone-a"]
  to   = aws_subnet.private["us-east-1a"]
}
moved {
  from = aws_subnet.private["zone-b"]
  to   = aws_subnet.private["us-east-1b"]
}
```

---

## 5. Hands-on Lab - 60 phut

### Setup

Lab nay dung **local provider** de simulate AWS resources ma khong can AWS account. Cau truc simulate infrastructure thuc: VPC -> Subnets -> App instances.

> **Note:** Lab dung `hashicorp/local` va `random` provider thay vi AWS. Pattern va concepts giong het, chi khac la resource types don gian hon. Trong production ban ap dung exactly the same lifecycle/import/moved patterns voi AWS provider.

Tao thu muc lab:

```bash
mkdir -p ~/terraform-labs/day-10-lab
cd ~/terraform-labs/day-10-lab
```

### Part 1: Tao Resources va Simulate Import (15 phut)

**Buoc 1.1: Tao "legacy" infrastructure (simulate resources duoc tao thu cong)**

Tao file `legacy_setup.tf` - day la code de tao resources, nhung ta se pretend chung duoc tao thu cong. Sau do ta se del file nay va import.

Tao file `providers.tf`:

```hcl
# providers.tf
terraform {
  required_version = ">= 1.5"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}
```

Tao file `legacy_create.tf` - file nay simulate "infrastructure duoc tao truoc khi co Terraform":

```hcl
# legacy_create.tf
# Chay file nay de simulate "manually created resources"
# Sau do ta se doi ten no va import vao resources moi

resource "local_file" "app_config_legacy" {
  filename = "${path.module}/app-config.json"
  content = jsonencode({
    app_name    = "payment-service"
    environment = "production"
    version     = "2.1.0"
    database = {
      host = "prod-postgres.internal"
      port = 5432
      name = "payments_db"
    }
    created_by = "manual-deployment"
    created_at = "2023-06-01"
  })
  file_permission = "0644"
}

resource "local_file" "nginx_config_legacy" {
  filename = "${path.module}/nginx.conf"
  content  = <<-EOT
    # NGINX Config - Payment Service
    # Created manually by ops team
    worker_processes  auto;

    events {
        worker_connections  1024;
    }

    http {
        upstream payment_app {
            server 10.0.1.10:8080;
            server 10.0.1.11:8080;
        }

        server {
            listen 80;
            location / {
                proxy_pass http://payment_app;
            }
        }
    }
  EOT
  file_permission = "0644"
}
```

Chay de tao legacy resources:

```bash
terraform init
terraform apply -auto-approve
```

Expected output:
```
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

**Buoc 1.2: Xoa config de simulate "resources ton tai nhung chua duoc Terraform quan ly"**

Rename file (simulate resources ton tai ma chua co Terraform code):

```bash
mv legacy_create.tf legacy_create.tf.bak
```

Luc nay Terraform state van track hai resources, nhung ta se pretend state khong ton tai bang cach xoa state entries:

```bash
terraform state rm local_file.app_config_legacy
terraform state rm local_file.nginx_config_legacy
```

Expected output:
```
Removed local_file.app_config_legacy
Successfully removed 1 resource instance(s).
Removed local_file.nginx_config_legacy
Successfully removed 1 resource instance(s).
```

Files `app-config.json` va `nginx.conf` van ton tai tren disk (simulate "cloud resources da co"), nhung Terraform khong con track chung.

**Buoc 1.3: Viet config cho resources can import**

Tao file `main.tf`:

```hcl
# main.tf
# Config cho resources can duoc import vao Terraform management

locals {
  app_name    = "payment-service"
  environment = "production"
}

resource "local_file" "app_config" {
  filename        = "${path.module}/app-config.json"
  file_permission = "0644"

  content = jsonencode({
    app_name    = local.app_name
    environment = local.environment
    version     = "2.1.0"
    database = {
      host = "prod-postgres.internal"
      port = 5432
      name = "payments_db"
    }
    created_by = "terraform"
    created_at = "2023-06-01"
  })

  lifecycle {
    # Ignore changes to created_at (managed externally)
    ignore_changes = [content]
  }
}

resource "local_file" "nginx_config" {
  filename        = "${path.module}/nginx.conf"
  file_permission = "0644"

  content = <<-EOT
    # NGINX Config - Payment Service
    # Created manually by ops team
    worker_processes  auto;

    events {
        worker_connections  1024;
    }

    http {
        upstream payment_app {
            server 10.0.1.10:8080;
            server 10.0.1.11:8080;
        }

        server {
            listen 80;
            location / {
                proxy_pass http://payment_app;
            }
        }
    }
  EOT

  file_permission = "0644"

  lifecycle {
    prevent_destroy = true
  }
}
```

**Buoc 1.4: Import resources**

Import theo tung resource:

```bash
# Import app config
terraform import local_file.app_config "${PWD}/app-config.json"

# Import nginx config
terraform import local_file.nginx_config "${PWD}/nginx.conf"
```

Expected output cho moi import:
```
local_file.app_config: Importing from ID "/home/user/terraform-labs/day-10-lab/app-config.json"...
local_file.app_config: Import prepared!
  Prepared local_file for import
local_file.app_config: Refreshing state... [id=...]
Import successful!
The resources that were imported are shown above. These resources are now
in your Terraform state and will henceforth be managed by Terraform.
```

**Buoc 1.5: Verify import thanh cong**

```bash
terraform plan
```

Expected output (vi `ignore_changes = [content]` cho app_config):
```
No changes. Your infrastructure matches the configuration.
```

Neu plan show changes, dieu chinh content trong main.tf cho khop voi actual file content.

### Part 2: Add Lifecycle Rules (10 phut)

Tao file `database_simulation.tf` simulate production database:

```hcl
# database_simulation.tf
resource "local_file" "database_config" {
  filename        = "${path.module}/database.conf"
  file_permission = "0600"  # Sensitive - restricted permissions

  content = <<-EOT
    # PostgreSQL Connection Config
    # Production - DO NOT MODIFY WITHOUT APPROVAL
    host=prod-postgres.internal
    port=5432
    dbname=payments_db
    user=app_user
    password=MANAGED_BY_VAULT
    sslmode=verify-full
    sslcert=/etc/ssl/certs/client.crt
    connect_timeout=10
    application_name=payment-service
  EOT

  lifecycle {
    prevent_destroy       = true   # Khong bao gio destroy production DB config
    create_before_destroy = true   # Neu phai replace, tao moi truoc
    ignore_changes = [
      content,        # Password duoc rotation boi Vault, khong track
    ]
  }
}

resource "local_file" "redis_config" {
  filename        = "${path.module}/redis.conf"
  file_permission = "0644"

  content = <<-EOT
    # Redis Config - Session Cache
    maxmemory 2gb
    maxmemory-policy allkeys-lru
    requirepass MANAGED_BY_VAULT
    timeout 300
  EOT

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [content]
  }
}
```

Apply:

```bash
terraform apply -auto-approve
```

Test `prevent_destroy`:

Them vao cuoi file `database_simulation.tf`:

```hcl
# Them tam de test - se tao ra plan error
# lifecycle {
#   prevent_destroy = true  <- Neu comment out dong nay
# }
```

Tao file `test_destroy.tf` voi noi dung:

```hcl
# Luu y: File nay chi de demo, khong apply
# Neu muon test, uncomment va chay terraform plan
# resource "local_file" "database_config" {
#   ... khong co prevent_destroy ...
# }
```

Thay vao do, chay truc tiep destroy de thay loi:

```bash
terraform destroy -target=local_file.database_config
```

Expected output:
```
Error: Instance cannot be destroyed

  on database_simulation.tf line X, in resource "local_file" "database_config":
  Resource local_file.database_config has lifecycle.prevent_destroy set, but the
  plan calls for this resource to be destroyed.
```

Day la behavior mong muon. `prevent_destroy` dang hoat dong dung.

### Part 3: Refactor vao Module Voi moved Blocks (25 phut)

**Buoc 3.1: Tao module structure**

```bash
mkdir -p modules/app-config
```

Tao `modules/app-config/variables.tf`:

```hcl
# modules/app-config/variables.tf
variable "app_name" {
  description = "Application name"
  type        = string
}

variable "environment" {
  description = "Deployment environment (production, staging, dev)"
  type        = string
  validation {
    condition     = contains(["production", "staging", "dev"], var.environment)
    error_message = "Environment must be one of: production, staging, dev."
  }
}

variable "database_host" {
  description = "Database hostname"
  type        = string
}

variable "upstream_servers" {
  description = "List of upstream app server addresses"
  type        = list(string)
  default     = []
}
```

Tao `modules/app-config/main.tf`:

```hcl
# modules/app-config/main.tf
resource "local_file" "app_config" {
  filename        = "${path.module}/../../app-config.json"
  file_permission = "0644"

  content = jsonencode({
    app_name    = var.app_name
    environment = var.environment
    version     = "2.1.0"
    database = {
      host = var.database_host
      port = 5432
      name = "${var.app_name}_db"
    }
    created_by = "terraform"
    created_at = "2023-06-01"
  })

  lifecycle {
    ignore_changes = [content]
  }
}

resource "local_file" "nginx_config" {
  filename        = "${path.module}/../../nginx.conf"
  file_permission = "0644"

  content = templatefile("${path.module}/nginx.conf.tpl", {
    upstream_servers = length(var.upstream_servers) > 0 ? var.upstream_servers : ["10.0.1.10:8080", "10.0.1.11:8080"]
  })

  lifecycle {
    prevent_destroy       = true
    create_before_destroy = true
  }
}
```

Tao `modules/app-config/nginx.conf.tpl`:

```
# NGINX Config - ${app_name}
# Managed by Terraform - Do not edit manually
worker_processes  auto;

events {
    worker_connections  1024;
}

http {
    upstream payment_app {
%{ for server in upstream_servers ~}
        server ${server};
%{ endfor ~}
    }

    server {
        listen 80;
        location / {
            proxy_pass http://payment_app;
        }
    }
}
```

Tao `modules/app-config/outputs.tf`:

```hcl
# modules/app-config/outputs.tf
output "app_config_path" {
  description = "Path to the generated app config file"
  value       = local_file.app_config.filename
}

output "nginx_config_path" {
  description = "Path to the generated nginx config file"
  value       = local_file.nginx_config.filename
}
```

**Buoc 3.2: Cap nhat root module - VIET MOVED BLOCKS TRUOC**

Tao file `moved.tf` - day la buoc quan trong nhat:

```hcl
# moved.tf
# IMPORTANT: Cac moved blocks nay phai duoc apply TRUOC KHI xoa resources
# tu root module va TRUOC KHI goi module moi.
# Giu file nay it nhat 1 sprint sau khi apply.
# Safe to delete after: <them ngay sau khi team da apply>

moved {
  from = local_file.app_config
  to   = module.payment_service_config.local_file.app_config
}

moved {
  from = local_file.nginx_config
  to   = module.payment_service_config.local_file.nginx_config
}
```

**Buoc 3.3: Cap nhat main.tf de goi module**

Thay the noi dung `main.tf`, bo di resource blocks cu, them module call:

```hcl
# main.tf - refactored
locals {
  app_name    = "payment-service"
  environment = "production"
}

module "payment_service_config" {
  source = "./modules/app-config"

  app_name     = local.app_name
  environment  = local.environment
  database_host = "prod-postgres.internal"

  upstream_servers = [
    "10.0.1.10:8080",
    "10.0.1.11:8080",
  ]
}

output "app_config_path" {
  value = module.payment_service_config.app_config_path
}

output "nginx_config_path" {
  value = module.payment_service_config.nginx_config_path
}
```

**Luu y:** File `database_simulation.tf` van giu nguyen vi cac database resources khong duoc move vao module trong buoc nay.

**Buoc 3.4: Chay terraform init va plan - BUOC QUAN TRONG**

```bash
terraform init  # Can init lai vi co module moi
terraform plan
```

Expected output - day la output ban MUON thay:

```
Terraform will perform the following actions:

  # local_file.app_config has moved to module.payment_service_config.local_file.app_config
    resource "local_file" "app_config" {
        id              = "..."
        content         = (sensitive)
        filename        = ".../app-config.json"
        file_permission = "0644"
    }

  # local_file.nginx_config has moved to module.payment_service_config.local_file.nginx_config
    resource "local_file" "nginx_config" {
        id              = "..."
        content         = (sensitive)
        filename        = ".../nginx.conf"
        file_permission = "0644"
    }

Plan: 0 to add, 0 to change, 0 to destroy.
```

`Plan: 0 to add, 0 to change, 0 to destroy` - day la ket qua mong muon. Resources duoc move trong state ma khong bi destroy.

**Neu thay `Plan: X to add, X to destroy` -> DUNG LAI, KHONG APPLY.** Investigate moved blocks, kiem tra addresses co chinh xac khong.

**Buoc 3.5: Apply va verify**

```bash
terraform apply -auto-approve
terraform plan  # Verify lan cuoi - phai la "No changes"
```

### Part 4: End-to-end Verification (10 phut)

**Buoc 4.1: Kiem tra state structure**

```bash
terraform state list
```

Expected output:
```
local_file.database_config
local_file.redis_config
module.payment_service_config.local_file.app_config
module.payment_service_config.local_file.nginx_config
```

**Buoc 4.2: Kiem tra files van ton tai**

```bash
ls -la *.json *.conf 2>/dev/null
cat app-config.json
```

Files phai van ton tai voi noi dung tuong tu truoc khi refactor.

**Buoc 4.3: Verify lifecycle rules hoat dong**

```bash
# Kiem tra nginx config co prevent_destroy
terraform destroy -target=module.payment_service_config.local_file.nginx_config
```

Expected: Loi `prevent_destroy`.

**Buoc 4.4: Test import block (Terraform 1.5+)**

Xoa state cua database_config va import lai bang import block:

```bash
terraform state rm local_file.database_config
```

Tao file `import_blocks.tf`:

```hcl
# import_blocks.tf
import {
  to = local_file.database_config
  id = "${path.module}/database.conf"
}
```

```bash
terraform plan   # Se show "import" action, khong phai "create"
terraform apply -auto-approve
```

Sau khi apply thanh cong, xoa file `import_blocks.tf` (import block chi can chay mot lan):

```bash
rm import_blocks.tf
terraform plan  # Phai la "No changes"
```

### Cleanup

```bash
# Phai xoa prevent_destroy truoc khi destroy
# Sua database_simulation.tf: comment out / xoa lifecycle block
# Sau do:
terraform destroy -auto-approve
rm -rf app-config.json nginx.conf database.conf redis.conf
```

---

## 6. Kiem tra hieu bai

**Cau 1:** Ban co resource `aws_db_instance.prod` voi `prevent_destroy = true`. Requirement moi: phai xoa database nay vi migrate sang Aurora. Quy trinh dung la gi?

<details>
<summary>Dap an</summary>

1. Tao PR xoa `prevent_destroy = true` khoi resource block
2. Code review - can approval vi day la production database
3. Apply PR -> `prevent_destroy` da duoc go bo
4. Chay `terraform plan -destroy` de preview
5. Chay `terraform destroy -target=aws_db_instance.prod`
6. Verify Aurora da san sang truoc buoc 5

Khong duoc dung `-auto-approve` cho production destroy.
</details>

**Cau 2:** Sau khi import resource, `terraform plan` show mot so changes (vi du: tags khac). Dung hay sai khi apply ngay?

<details>
<summary>Dap an</summary>

SAI. Khi plan show changes sau import, co hai truong hop:
- Changes mong muon: cap nhat tag, config de align voi standard. OK ap dung nhung phai review truoc.
- Changes khong mong muon: Terraform muon thay doi config dang chay tot. Can hieu tai sao truoc khi apply (co the HCL chua chinh xac, co the la legitimate drift).

Nguyen tac: Khong bao gio apply changes ma ban chua hieu ro nguon goc. Luon review `terraform plan` output truoc khi apply, dac biet sau import.
</details>

**Cau 3:** Team refactor: chuyen `aws_instance.frontend` vao `module.web.aws_instance.frontend`. Engineer A viet moved block va commit. Engineer B chua pull va apply. Team A apply tren shared state. Engineer B sau do pull, chay plan - ket qua la gi?

<details>
<summary>Dap an</summary>

Engineer B se thay `No changes` (hoac chi thay changes tu cac viec khac).

Ly do: Sau khi Engineer A apply, state file da duoc update: address cu `aws_instance.frontend` da duoc doi thanh `module.web.aws_instance.frontend`. Khi Engineer B pull code moi (co moved block va module call) va chay plan, Terraform doc moved block, thay address trong state da khop voi `to` address, nen khong can lam gi them.

Moved block la idempotent: Neu state da o dung address, no khong co effect.
</details>

**Cau 4:** Khi nao nen dung `ignore_changes = all` va tai sao day la option nguy hiem?

<details>
<summary>Dap an</summary>

Dung khi: Resource hoan toan duoc quan ly boi external system (vi du: Kubernetes operator tu quan ly `aws_lb_target_group_attachment`, hoac service discovery tu dieu chinh health check settings).

Nguy hiem vi:
1. Terraform se khong bao gio bao cao drift. Config security group mo cong 0.0.0.0/0 se bi bo qua.
2. Mat kha nang audit "terraform plan" de verify state.
3. Neu external system co loi va thay doi sai config, Terraform se khong phat hien va correct.

Thay vao do: Prefer `ignore_changes` voi explicit attribute list. Build monitoring ngoai Terraform (AWS Config, OPA) de catch drift tren cac ignored attributes.
</details>

**Cau 5:** `terraform state mv` vs `moved` block: khi nao dung cai nao trong team environment?

<details>
<summary>Dap an</summary>

`moved` block: 99% truong hop trong team environment.
- Duoc review trong PR truoc khi apply
- Chay idempotent (an toan cho team member chua apply)
- Audit trail trong Git history
- Co the rollback bang cach revert commit

`terraform state mv`: Chi dung cho emergency fix khi:
- Phat hien plan se destroy resource sai ngay truoc apply window
- Khong co thoi gian de PR workflow
- Sau do immediate follow-up: tao PR voi proper moved block de document action

Khong bao gio dung `terraform state mv` cho planned refactoring.
</details>

---

## 7. Tom tat cuoi ngay

### Nhung gi da hoc

**lifecycle block** - Ba rules cho three different problems:
- `prevent_destroy`: Dieu kien cuoi cung de bao ve stateful resources. Bat buoc cho databases, DNS, KMS.
- `ignore_changes`: Cho phep external system quan ly specific attributes. Dung ca ngo, never `ignore_changes = all`.
- `create_before_destroy`: Giai quyet circular dependency khi replace immutable-name resources.

**terraform import** - Two approaches:
- CLI (`terraform import`): Nhanh cho ad-hoc, khong track trong Git
- Import block (1.5+): Team-friendly, GitOps-compatible, idempotent

Post-import workflow: LUON chay `terraform plan` va verify "No changes" truoc khi consider import hoan thanh.

**moved block** (Terraform 1.1+) - Production refactoring tool:
- Doi resource address trong state ma khong destroy
- Track trong Git, reviewable, idempotent
- Uu tien over `terraform state mv` trong moi truong hop planned

### Output cua ngay hom nay

Sau khi hoan thanh lab, ban co:
- File `main.tf` voi module call thay vi inline resources
- Thu muc `modules/app-config/` voi module hoan chinh
- Hieu ro workflow import, lifecycle rules, va moved blocks
- Refactored config voi `Plan: 0 to add, 0 to change, 0 to destroy`

### Chuan bi cho Day 11: CI/CD Terraform Pipeline

Day 11 se xay dung GitOps pipeline cho Terraform voi:
- Atlantis hoac GitHub Actions
- Automated `terraform plan` tren PR
- Protected apply (require approvals)
- State locking trong pipeline

Nhung gi can nho tu hom nay truoc khi sang Day 11:
- Import block (1.5+) co the chay trong CI - phan quan trong cua automated import workflows
- `prevent_destroy` co the block CI pipeline neu destroy operation duoc trigger sai
- moved blocks trong PR se duoc plan tu dong boi Atlantis/GH Actions

## 8. Tham khao them

- [Terraform Lifecycle Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)
- [terraform import CLI](https://developer.hashicorp.com/terraform/cli/commands/import)
- [Import Block (1.5+)](https://developer.hashicorp.com/terraform/language/import)
- [moved Block](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring)
- [terraform state mv](https://developer.hashicorp.com/terraform/cli/commands/state/mv)
- [Refactoring Terraform Resources](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring)
- HashiCorp Blog: [Terraform 1.5 brings config-driven import and checks](https://www.hashicorp.com/blog/terraform-1-5-brings-config-driven-import-and-checks)
