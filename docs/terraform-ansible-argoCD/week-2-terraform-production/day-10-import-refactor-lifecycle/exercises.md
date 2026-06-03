# Day 10 - Extra Exercises: Lifecycle, Import, Moved Blocks

**Danh cho:** Engineer muon di sau hon ngoai lab chinh.
**Prerequisites:** Hoan thanh lesson.md lab truoc.

---

## Exercise 1: Complex Multi-Resource Import

**Boi canh:** Ban tiep nhan mot legacy environment. Co 6 resources duoc tao thu cong tren AWS (simulate bang local provider). Nhiem vu: import tat ca vao Terraform va dam bao plan sach (No changes).

**Setup - tao "legacy" resources:**

```bash
mkdir -p ~/terraform-labs/day-10-ex1
cd ~/terraform-labs/day-10-ex1
```

Tao `providers.tf`:

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}
```

Tao `legacy_infra.tf` (simulate manually-created infra):

```hcl
# Chay file nay, ghi nho cac file duoc tao, sau do xoa state
resource "local_file" "vpc_config" {
  filename        = "${path.module}/vpc.json"
  file_permission = "0644"
  content = jsonencode({
    vpc_id   = "vpc-legacy-001"
    cidr     = "10.0.0.0/16"
    env      = "production"
    owner    = "platform-team"
    tags = {
      "ManagedBy"   = "manual"
      "Environment" = "production"
      "CostCenter"  = "platform"
    }
  })
}

resource "local_file" "subnet_public" {
  filename        = "${path.module}/subnet-public.json"
  file_permission = "0644"
  content = jsonencode({
    subnet_id = "subnet-pub-001"
    cidr      = "10.0.1.0/24"
    type      = "public"
    az        = "us-east-1a"
  })
}

resource "local_file" "subnet_private" {
  filename        = "${path.module}/subnet-private.json"
  file_permission = "0644"
  content = jsonencode({
    subnet_id = "subnet-prv-001"
    cidr      = "10.0.2.0/24"
    type      = "private"
    az        = "us-east-1a"
  })
}

resource "local_file" "security_group_web" {
  filename        = "${path.module}/sg-web.json"
  file_permission = "0644"
  content = jsonencode({
    sg_id   = "sg-web-001"
    name    = "web-servers"
    ingress = [{ port = 80, cidr = "0.0.0.0/0" }, { port = 443, cidr = "0.0.0.0/0" }]
    egress  = [{ port = 0, cidr = "0.0.0.0/0", protocol = "all" }]
  })
}

resource "local_file" "security_group_db" {
  filename        = "${path.module}/sg-db.json"
  file_permission = "0644"
  content = jsonencode({
    sg_id   = "sg-db-001"
    name    = "database"
    ingress = [{ port = 5432, cidr = "10.0.0.0/16" }]
    egress  = []
  })
}

resource "local_file" "rds_config" {
  filename        = "${path.module}/rds.json"
  file_permission = "0600"
  content = jsonencode({
    db_id              = "prod-postgres-001"
    engine             = "postgres"
    engine_version     = "14.8"
    instance_class     = "db.r5.large"
    allocated_storage  = 100
    multi_az           = true
    deletion_protection = true
    backup_retention   = 7
  })
}
```

```bash
terraform init && terraform apply -auto-approve
# Sau khi tao xong, xoa state de simulate "outside terraform"
terraform state rm local_file.vpc_config
terraform state rm local_file.subnet_public
terraform state rm local_file.subnet_private
terraform state rm local_file.security_group_web
terraform state rm local_file.security_group_db
terraform state rm local_file.rds_config
mv legacy_infra.tf legacy_infra.tf.bak
```

**Nhiem vu:**

1. Viet `main.tf` voi tat ca 6 resource blocks tuong ung. RDS phai co `prevent_destroy = true` va `ignore_changes = [content]`. Security groups phai co `create_before_destroy = true`.

2. Viet `import_blocks.tf` su dung import block (khong dung CLI import) de import tat ca 6 resources.

3. Chay `terraform plan` - target: `No changes`. Neu co changes, dieu chinh HCL.

4. Apply, xoa `import_blocks.tf`, chay plan lai verify sach.

5. Viet mot file `IMPORT_LOG.md` ghi lai: thoi gian, resources duoc import, ai thuc hien, ket qua verify. Day la audit trail practice.

**Diem khong khuyen cao:** Dung `import {}` voi `generate-config-out` va paste output. Phai tu viet HCL de luyen tap hieu cau truc resource.

---

## Exercise 2: Multi-Module Refactoring

**Boi canh:** Codebase hien tai co tat ca resources trong root module. Nhiem vu: refactor thanh 3 modules (`networking`, `security`, `database`) su dung moved blocks, dam bao zero destroy.

**Starting codebase - tao `main.tf`:**

```hcl
# main.tf - flat structure, can refactor
locals {
  environment = "production"
  project     = "ecommerce"
  region      = "us-east-1"
}

# Networking
resource "local_file" "vpc" {
  filename        = "${path.module}/infra/vpc.json"
  file_permission = "0644"
  content = jsonencode({
    id          = "${local.project}-${local.environment}-vpc"
    cidr        = "10.0.0.0/16"
    environment = local.environment
  })
}

resource "local_file" "subnet_az1" {
  filename        = "${path.module}/infra/subnet-az1.json"
  file_permission = "0644"
  content = jsonencode({
    id   = "${local.project}-${local.environment}-subnet-az1"
    cidr = "10.0.1.0/24"
    az   = "${local.region}a"
  })
}

resource "local_file" "subnet_az2" {
  filename        = "${path.module}/infra/subnet-az2.json"
  file_permission = "0644"
  content = jsonencode({
    id   = "${local.project}-${local.environment}-subnet-az2"
    cidr = "10.0.2.0/24"
    az   = "${local.region}b"
  })
}

# Security
resource "local_file" "sg_web" {
  filename        = "${path.module}/infra/sg-web.json"
  file_permission = "0644"
  content = jsonencode({
    id   = "${local.project}-${local.environment}-sg-web"
    type = "web"
    rules = ["80/tcp", "443/tcp"]
  })
  lifecycle {
    create_before_destroy = true
  }
}

resource "local_file" "sg_database" {
  filename        = "${path.module}/infra/sg-database.json"
  file_permission = "0644"
  content = jsonencode({
    id   = "${local.project}-${local.environment}-sg-database"
    type = "database"
    rules = ["5432/tcp from 10.0.0.0/16"]
  })
  lifecycle {
    create_before_destroy = true
  }
}

# Database
resource "local_file" "postgres_primary" {
  filename        = "${path.module}/infra/postgres-primary.json"
  file_permission = "0600"
  content = jsonencode({
    id             = "${local.project}-${local.environment}-postgres"
    engine         = "postgres14"
    instance_class = "db.r5.2xlarge"
    multi_az       = true
  })
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [content]
  }
}

resource "local_file" "postgres_replica" {
  filename        = "${path.module}/infra/postgres-replica.json"
  file_permission = "0600"
  content = jsonencode({
    id             = "${local.project}-${local.environment}-postgres-replica"
    source         = "${local.project}-${local.environment}-postgres"
    instance_class = "db.r5.xlarge"
  })
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [content]
  }
}
```

```bash
mkdir -p ~/terraform-labs/day-10-ex2/infra
cd ~/terraform-labs/day-10-ex2
# Copy providers.tf tu ex1
terraform init && terraform apply -auto-approve
```

**Nhiem vu:**

1. Thiet ke module structure:
   ```
   modules/
     networking/
       main.tf, variables.tf, outputs.tf
     security/
       main.tf, variables.tf, outputs.tf
     database/
       main.tf, variables.tf, outputs.tf
   ```

2. Viet tung module voi input variables ro rang. `database` module phai nhan `security_group_ids` tu `security` module output (cross-module dependency).

3. Viet `moved.tf` cho TAT CA 8 resources (bao gom ca hai postgres).

4. Viet `main.tf` moi goi 3 modules theo thu tu dependency dung (networking truoc, security dat dung, database cuoi).

5. Dat cau hoi: Doi voi resource inside module co `prevent_destroy`, khi module bi xoa khoi root module thi dieu gi xay ra? Test thu va ghi lai ket qua.

6. Chay `terraform plan` - chi accept neu output la `0 to add, 0 to change, 0 to destroy`. Khong hop le neu co chi tiet "has moved to ... but the moved blocks will prevent destroying" - phai fix.

7. Apply va verify `terraform state list` show dung module structure.

**Challenge them:** Sau khi refactor xong, thu thay doi `environment` local tu `production` sang `staging` va chay plan. Ghi lai nhung gi se bi thay doi va tai sao.

---

## Exercise 3: Production Incident Simulation

**Boi canh:** Day la disaster recovery exercise. Ban se simulate mot production incident va phai recover ma khong mat data, khong downtime.

**Incident setup:**

```bash
mkdir -p ~/terraform-labs/day-10-ex3
cd ~/terraform-labs/day-10-ex3
```

Tao infrastructure:

```hcl
# main.tf
resource "local_file" "critical_database" {
  filename        = "${path.module}/database-critical.json"
  file_permission = "0600"
  content = jsonencode({
    id              = "prod-critical-db-001"
    engine          = "postgres"
    data_size_gb    = 500
    backup_enabled  = true
    last_backup     = "2024-01-15T03:00:00Z"
    critical_data   = "FINANCIAL_RECORDS"
    # Simulating real production data marker
    recovery_point_objective = "15 minutes"
  })

  # INTENTIONALLY NO LIFECYCLE PROTECTION - this is the bug we will discover
}

resource "local_file" "application_server" {
  filename        = "${path.module}/app-server.json"
  file_permission = "0644"
  content = jsonencode({
    id = "prod-app-server-001"
    type = "web"
  })
}

resource "local_file" "load_balancer" {
  filename        = "${path.module}/load-balancer.json"
  file_permission = "0644"
  content = jsonencode({
    id = "prod-alb-001"
    scheme = "internet-facing"
  })
}
```

```bash
terraform init && terraform apply -auto-approve
```

**Simulate incident - engineer chay sai command:**

```bash
# Engineer muon destroy dev env nhung chay nham tren prod state
terraform destroy -target=local_file.critical_database -auto-approve
```

**Output sau incident:**
```
Destroy complete! Resources: 1 destroyed.
# File database-critical.json da bi xoa
# State khong con track resource nay
```

**Nhiem vu recover:**

**Buoc 1 - Assess damage:**
```bash
terraform state list
ls -la *.json
terraform plan
```
Ghi lai: resources nao con, resource nao mat.

**Buoc 2 - Restore tu backup (simulate):**
Tao lai file tu "backup":
```bash
cat > database-critical.json << 'EOF'
{
  "id": "prod-critical-db-001",
  "engine": "postgres",
  "data_size_gb": 500,
  "backup_enabled": true,
  "last_backup": "2024-01-15T03:00:00Z",
  "critical_data": "FINANCIAL_RECORDS",
  "recovery_point_objective": "15 minutes",
  "RESTORED_FROM_BACKUP": "2024-01-15T09:30:00Z"
}
EOF
```

**Buoc 3 - Import resource da restore:**
- Viet import block de re-import database resource vao state
- Verify plan sach sau import
- Them `prevent_destroy = true` va `ignore_changes = [content]` vao resource

**Buoc 4 - Post-incident remediation:**
Viet file `incident_prevention.md` (chi trong lab nay - thuc te dung Confluence/Notion) voi:
- Root cause analysis
- Immediate fix da thuc hien
- Long-term prevention measures:
  - Them `prevent_destroy` cho tat ca cac critical resources nhu the nao
  - Pipeline guard de detect workspace truoc khi destroy
  - Terraform state backup automation

**Buoc 5 - Add proper lifecycle protection:**
Cap nhat resource voi lifecycle rules dung va verify plan sach.

---

## Exercise 4: for_each Key Migration

**Boi canh:** Team doi naming convention cho AZs. Resources duoc tao voi keys la `zone-a`, `zone-b`, `zone-c`. Can doi sang `us-east-1a`, `us-east-1b`, `us-east-1c` ma khong destroy va tao lai.

**Starting state:**

```hcl
# main.tf - legacy naming
variable "availability_zones" {
  default = {
    "zone-a" = { cidr = "10.0.1.0/24", order = 1 }
    "zone-b" = { cidr = "10.0.2.0/24", order = 2 }
    "zone-c" = { cidr = "10.0.3.0/24", order = 3 }
  }
}

resource "local_file" "subnet" {
  for_each        = var.availability_zones
  filename        = "${path.module}/subnet-${each.key}.json"
  file_permission = "0644"
  content = jsonencode({
    id    = "subnet-${each.key}"
    cidr  = each.value.cidr
    order = each.value.order
    name  = "private-subnet-${each.key}"
  })
}

resource "local_file" "nat_gateway" {
  for_each        = var.availability_zones
  filename        = "${path.module}/nat-${each.key}.json"
  file_permission = "0644"
  content = jsonencode({
    id     = "nat-${each.key}"
    subnet = "subnet-${each.key}"
  })
}
```

```bash
mkdir -p ~/terraform-labs/day-10-ex4
cd ~/terraform-labs/day-10-ex4
terraform init && terraform apply -auto-approve
terraform state list
# Phai thay: local_file.nat_gateway["zone-a"], local_file.subnet["zone-a"], etc.
```

**Nhiem vu:**

1. Cap nhat `variables.tf` (tach ra) voi naming moi:
   ```hcl
   variable "availability_zones" {
     default = {
       "us-east-1a" = { cidr = "10.0.1.0/24", order = 1 }
       "us-east-1b" = { cidr = "10.0.2.0/24", order = 2 }
       "us-east-1c" = { cidr = "10.0.3.0/24", order = 3 }
     }
   }
   ```

2. Cap nhat `main.tf` - doi filename pattern tu `subnet-${each.key}` sang `subnet-${replace(each.key, "us-east-1", "az")}` (hoac naming hop ly khac).

3. Viet 6 moved blocks (3 cho subnet, 3 cho nat_gateway) map tung zone-x sang us-east-1x.

4. Chay plan - target: chi thay `has moved to`, khong co `destroy`.

5. Apply va verify:
   ```bash
   terraform state list
   # Phai thay: local_file.nat_gateway["us-east-1a"] etc.
   ls -la *.json
   # Files phai van con voi ten moi neu filename doi
   ```

6. **Bonus challenge:** Sau khi moved xong, update resource content de thay ten file cu bang `az-1`, `az-2`, `az-3` thay vi `zone-a`, `zone-b`, `zone-c` va `us-east-1a`, `us-east-1b`, `us-east-1c`. Ghi lai trong plan: bao nhieu resources se update content?

---

## Exercise 5: Lifecycle Conflict Resolution

**Boi canh:** Mot engineer nhat dinh rang toan bo cluster (10 resources) phai co `prevent_destroy = all`. Sau mot thang, yeu cau shutdown staging environment. Ban phai thiet ke workflow cho phep shutdown ma van giu `prevent_destroy` tren production.

**Nhiem vu (Design exercise, khong can code day du):**

Viet mot document `lifecycle-strategy.md` (chi trong lab, khong lam ngoai thuc tien neu khong duoc yeu cau) mo ta:

**Section 1: Van de voi "prevent_destroy everywhere"**
- Liet ke 3 tinh huong cu the where `prevent_destroy` blocks legitimate operations
- Giai thich tai sao `prevent_destroy = true` tren ephemeral resources (lambda, ECS task def) la anti-pattern

**Section 2: Tiered protection strategy**
Thiet ke strategy phan chia resources thanh tiers:

```
Tier 1 - Critical (prevent_destroy = true, khong ngoai le):
  - [ ] Liet ke cac resource types

Tier 2 - Important (prevent_destroy = true, nhung co documented removal process):
  - [ ] Liet ke cac resource types
  - [ ] Documented removal process la gi?

Tier 3 - Standard (khong co prevent_destroy, nhung co tagging/monitoring):
  - [ ] Liet ke cac resource types
  - [ ] Monitoring la gi?

Tier 4 - Ephemeral (khong co prevent_destroy, expected to be destroyed regularly):
  - [ ] Liet ke cac resource types
```

**Section 3: Environment-specific lifecycle**

Thiet ke cach dung `var.environment` de conditional lifecycle:

```hcl
# Viet HCL su dung dynamic hoac conditional de lifecycle khac nhau
# tuy theo environment (production vs staging vs dev)
# Luu y: lifecycle block KHONG ho tro expressions/dynamic values truc tiep
# Phai dung workaround - tim hieu va mo ta workaround do
```

Goi y: Nghien cuu "lifecycle dynamic values Terraform" va tim hieu tai sao lifecycle khong support expressions, va alternative pattern (vi du: separate resource definitions per environment).

**Section 4: Emergency destroy procedure**

Viet step-by-step procedure cho "emergency destroy staging environment" khi co `prevent_destroy` tren nhieu resources:

1. Ai co quyen approve?
2. Sequence cac buoc cu the
3. Checklist truoc va sau
4. Rollback plan neu can

---

## Grading Rubric (Tu danh gia)

| Exercise | Tieu chi thanh cong | Diem |
|---|---|---|
| Ex 1 | Plan "No changes" sau khi import tat ca 6 resources bang import block | 20 |
| Ex 1 bonus | Import log day du, ro rang | 5 |
| Ex 2 | Plan "0 to destroy" sau module refactoring | 25 |
| Ex 2 bonus | Giai thich dung hieu ung cua environment change | 10 |
| Ex 3 | Import thanh cong sau incident, prevent_destroy duoc them | 20 |
| Ex 3 bonus | RCA va prevention measures ro rang, actionable | 10 |
| Ex 4 | Plan chi show "has moved to", 0 destroy | 15 |
| Ex 4 bonus | Content update sau moved dung so luong resources | 5 |
| Ex 5 | Tiered strategy co logic ro rang | 10 |
| **Total** | | **120** |

**80+:** Hieu chac lifecycle, import, moved - san sang cho Day 11 CI/CD.
**100+:** Co the mentor nguoi khac ve topic nay va thiet ke production refactoring plans.
