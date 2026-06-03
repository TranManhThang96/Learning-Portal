# Day 7: Module Design for Production - Extra Exercises

**Danh cho:** Hoc vien muon di sau hon sau khi hoan thanh lab chinh.  
**Prerequisites:** Hoan thanh lab trong lesson.md.  
**Khong co dap an mau** - Day la engineering exercise, co nhieu cach tiep can dung.

---

## Exercise 1: Module Boundary Refactoring

### Boi canh

Ban nhan duoc module sau tu mot teammate. Module nay "chay duoc" nhung co nhieu van de ve design.

```hcl
# modules/everything/main.tf  (module that su ton tai trong team)

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
}

resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone = data.aws_availability_zones.available.names[count.index]
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group" "web" {
  name   = "web-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name   = "rds-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "main-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier        = "prod-postgres"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = "db.t3.medium"
  allocated_storage = 20
  db_name           = var.db_name
  username          = var.db_username
  password          = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  skip_final_snapshot = true
}

resource "aws_instance" "app" {
  count         = 2
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.private[count.index].id

  vpc_security_group_ids = [aws_security_group.app.id]

  tags = {
    Name = "app-server-${count.index}"
  }
}

resource "aws_lb" "main" {
  name               = "main-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.web.id]
  subnets            = aws_subnet.public[*].id
}
```

### Nhiem vu

1. **Phan tich module tren** bang Decision Matrix tu document.md. Liet ke it nhat 5 van de cu the (blast radius, lifecycle, ownership, naming, v.v.).

2. **Thiet ke lai module boundary.** Ve so do (ASCII hoac text) the hien cach ban muon tach module nay. Giai thich ly do cho moi ranh gioi.

3. **Viet interface (variables.tf va outputs.tf) cho 2 module** trong kien truc moi. Khong can viet full main.tf, chi can interface.

4. **Viet root module** (main.tf) the hien cach wire cac module moi lai voi nhau.

5. **Xac dinh it nhat 3 hardcode value** trong module cu va de xuat cach parameterize chung.

---

## Exercise 2: Interface Review - Phat hien Breaking Changes

### Boi canh

Module `vpc-core` phien ban v1.0 dang duoc 4 team dung. Tech lead muon release v2.0 voi cac thay doi sau. Nhiem vu cua ban la review va phan loai.

**v1.0 interface:**

```hcl
# variables.tf v1.0
variable "name" { type = string }
variable "cidr" { type = string }
variable "azs" { type = list(string) }
variable "public_subnets" { type = list(string) }
variable "private_subnets" { type = list(string) }
variable "enable_nat" { type = bool; default = false }

# outputs.tf v1.0
output "vpc_id" { value = aws_vpc.main.id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "nat_gateway_ids" { value = aws_nat_gateway.main[*].id }
```

**Proposed v2.0 changes (danh sach tu tech lead):**

```
Change A: Doi ten variable "name" thanh "vpc_name" 
Change B: Them required variable "project_name" (khong co default)
Change C: Them optional variable "tags" (default = {})
Change D: Doi "enable_nat" type tu bool sang object:
          enable_nat -> nat_config = object({ enabled=bool, single_az=optional(bool,true) })
Change E: Them output "subnet_ids" moi: { public=[], private=[] }
Change F: Xoa output "nat_gateway_ids" (thay bang xem trong AWS Console)
Change G: Doi output "public_subnet_ids" va "private_subnet_ids":
          Giu nguyen nhung them "(deprecated: dung subnet_ids thay the)"
Change H: Them validation cho "cidr": chi chap nhan /16 den /28
```

### Nhiem vu

1. Phan loai moi change (A-H) theo: **Breaking** / **Non-breaking** / **Potentially Breaking**.  
   Giai thich ly do cu the cho tung change.

2. Viet **migration guide** ngan gon cho consumer muon upgrade tu v1.0 len v2.0.  
   Format: "Truoc khi upgrade, thay doi X thanh Y trong root module cua ban."

3. De xuat **thu tu release**: Neu phai release tung buoc (khong phai "big bang v2.0"), ban se group cac change nao vao cung phien ban? Giai thich logic.

4. Viet **CHANGELOG entry** cho v2.0 theo Conventional Commits / Keep a Changelog format.

---

## Exercise 3: Debug Scenarios

Cac scenario sau dua tren loi thuc te trong production. Tim nguyen nhan goc re va de xuat fix.

### Scenario A: Plan thay doi bat ngo

```bash
$ terraform plan

  ~ module.vpc.aws_subnet.private[0]
      ~ tags = {
          - "kubernetes.io/role/internal-elb" = "1" -> null
        }
  ~ module.vpc.aws_subnet.private[1]
      ~ tags = {
          - "kubernetes.io/role/internal-elb" = "1" -> null
        }

Plan: 0 to add, 2 to change, 0 to destroy.
```

Khong ai thay doi code. Ran `terraform plan` hom qua thi `No changes`. Hom nay runner CI chay plan thi ra change nay.

**Cau hoi:** 
- Nguyen nhan co the la gi?
- Lam the nao de debug (command nao can chay)?
- Lam the nao de ngan chan tinh trang nay trong tuong lai?

---

### Scenario B: Module goi thanh cong nhung resource khong duoc tao

```hcl
# Root module
module "vpc" {
  source = "../../modules/vpc-production"

  project_name = "myapp"
  environment  = "dev"
  vpc_cidr     = "10.10.0.0/16"

  availability_zones   = ["ap-southeast-1a", "ap-southeast-1b"]
  public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
  private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]

  flow_logs_config = {
    enabled        = true
    retention_days = 30
    traffic_type   = "ALL"
  }
}
```

```bash
$ terraform apply
Apply complete! Resources: 13 to add, 0 to change, 0 to destroy.

$ terraform output flow_logs_log_group_name
null
```

Flow log group name la null nhung `flow_logs_config.enabled = true`. Apply khong co loi.

**Cau hoi:**
- Giai thich tai sao output la null du enabled = true
- Co nhung nguyen nhan nao co the xay ra?
- Viet buoc debug step-by-step

---

### Scenario C: "Index out of range" khi thay doi AZ

```hcl
# Truoc: 3 AZ
availability_zones   = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24", "10.10.3.0/24"]
private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24", "10.10.13.0/24"]

# Muon scale xuong: 2 AZ (thay doi trong terraform.tfvars)
availability_zones   = ["ap-southeast-1a", "ap-southeast-1b"]
public_subnet_cidrs  = ["10.10.1.0/24", "10.10.2.0/24"]
private_subnet_cidrs = ["10.10.11.0/24", "10.10.12.0/24"]
```

```bash
$ terraform plan
Error: Reference to undeclared resource

  on ../../modules/vpc-production/main.tf line 89:
  |     nat_gateway_id = aws_nat_gateway.main[count.index].id

The given key does not identify an element in this collection value.
```

**Cau hoi:**
- Giai thich chuoi nhan qua nhat dan den loi nay (khong chi la "index out of range")
- Tac dong len state la gi? Terraform se xoa subnet index [2] hay giu?
- Neu dang co workload chay tren subnet index [2], viec chay `terraform apply` sau khi debug co an toan khong?
- De xuat cach thay doi module de tranh loi nay trong tuong lai

---

### Scenario D: Circular dependency

```hcl
# modules/vpc-production/security_groups.tf
resource "aws_security_group" "app" {
  name   = "${local.name_prefix}-app-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group_rule" "app_to_db" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.db.id  # Reference den db SG
  security_group_id        = aws_security_group.app.id
}

resource "aws_security_group" "db" {
  name   = "${local.name_prefix}-db-sg"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group_rule" "db_from_app" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id  # Reference den app SG
  security_group_id        = aws_security_group.db.id
}
```

```bash
$ terraform plan
Error: Cycle: aws_security_group.app, aws_security_group.db
```

**Cau hoi:**
- Giai thich tai sao xay ra circular dependency (Terraform xay dung dependency graph nhu the nao?)
- Rewrite code tren de giai quyet van de ma khong thay doi security intent
- Giai phap nao tot hon trong truong hop SG cua 2 module khac nhau can reference nhau?

---

## Exercise 4: Module Design Challenge - Tiet kiem Security Group

### Boi canh

Ban dang thiet ke module `security-groups` cho internal platform. Co 3 loai workload:

1. **ALB (Application Load Balancer):** Can inbound 80, 443 tu 0.0.0.0/0
2. **App Server (ECS/EC2):** Can inbound tu ALB SG, outbound tuy do
3. **RDS PostgreSQL:** Can inbound 5432 tu App Server SG

### Requirement tu security team

- Moi SG chi mo port can thiet, khong "all traffic"
- Phai support truong hop: khong co ALB (dev environment dung port-forward truc tiep)
- Phai support truong hop: App server can access ca 2 database (RDS va ElastiCache)
- Tag tat ca SG voi `Tier = alb|app|db|cache`
- Output tat ca SG ID de module khac co the reference

### Nhiem vu

1. Viet day du `variables.tf` cho module `security-groups`.  
   Goi y: Suy nghi ve relationship giua cac SG - SG nay reference SG kia theo chieu nao?

2. Viet `main.tf` voi cac SG va rules.  
   Luu y: Khi SG A reference SG B, Terraform can biet B ton tai truoc. Sap xep dung dependency.

3. Viet `outputs.tf` voi structured output.  
   Goi y: Consumer (module ECS, module RDS) can gì? Output dung structure phu hop.

4. Viet `variables.tf` cho root module va the hien cach truyen SG ID tu `security-groups` module sang `ecs` module va `rds` module.

---

## Exercise 5: Versioning Migration Simulation

### Boi canh

Ban la platform engineer. Module `vpc-production` v0.1.0 dang duoc 3 environment (dev, staging, prod) dung:

```
environments/
  dev/     --> module "vpc" { source = "...?ref=v0.1.0" }
  staging/ --> module "vpc" { source = "...?ref=v0.1.0" }
  prod/    --> module "vpc" { source = "...?ref=v0.1.0" }
```

Ban muon release `v0.2.0` voi thay doi:
- Them `vpc_metadata` output (non-breaking)
- Them `subnet_details` output (non-breaking)
- Thay doi `subnet_ids` tu `{ public=[], private=[] }` sang theem `az_mapping` key (potentially breaking)
- Them validation cho `vpc_cidr` (could affect existing consumers voi invalid CIDR)

### Nhiem vu: Viet Rollout Plan

Viet rollout plan chi tiet, bao gom:

1. **Pre-release checklist:** Nhung gi ban kiem tra truoc khi tag v0.2.0

2. **Rollout order:** Tai sao phai roll out theo thu tu dev -> staging -> prod? Co truong hop nao can reverse order khong?

3. **Viet migration script** (bash hoac Makefile target) de update `source` trong moi environment.

4. **Rollback procedure:** Neu prod gap loi sau upgrade, cac buoc rollback cu the la gi? Co can chay `terraform state mv` khong?

5. **Communication template:** Viet thong bao ngan gon gui cho 3 team consumer (format: Slack message). Can ghi ro: change gi, anh huong gi, consumer can lam gi, deadline la khi nao.

---

## Exercise 6: Module Testing Strategy (Conceptual)

### Boi canh

Ban chua lam Terratest truoc day. Day la exercise conceptual - suy nghi ve strategy truoc khi code.

### Module `vpc-production` can duoc test nhung gi?

Hay liet ke va phan loai:

**1. Static validation (khong can AWS, chi can Terraform):**
- Nhung loai loi nao co the detect bang `terraform validate`?
- Nhung loai loi nao detect bang `terraform plan` ma khong can apply?
- Nhung command nao chay trong CI pipeline ma khong can AWS credentials?

**2. Integration test (can AWS, tao real resource):**
- Viet pseudocode cho mot integration test verify:
  - VPC duoc tao dung CIDR
  - Public subnet co `map_public_ip_on_launch = true`
  - Private subnet co `map_public_ip_on_launch = false`
  - Khi `flow_logs_config.enabled = false`, khong co CloudWatch log group nao duoc tao
  - Khi `flow_logs_config.enabled = true`, log group ton tai va co dung `retention_in_days`

**3. Contract test (test interface, khong test implementation):**
- Viet danh sach cac assertion ve output format ma consumer expect
- Dung go pseudocode hoac plain English

**4. Cost control trong testing:**
- Khi chay integration test, resource se ton tien (EIP, NAT Gateway, etc.)
- De xuat strategy de minimize cost trong test environment
- Khi nao test nen chay (vi du: chi chay khi co PR thay doi modules/, khong chay khi thay doi environments/)

---

## Ghi chu

Cac exercise tren duoc thiet ke theo thu tu tang dan do phuc tap:

- Exercise 1-2: Conceptual analysis, khong can code
- Exercise 3: Debug reasoning, khong can AWS
- Exercise 4-5: Require viet code va planning
- Exercise 6: Architecture design thinking

Neu chay het thoi gian, uu tien Exercise 1 va Exercise 3 - chung cover nhieu concept quan trong nhat cua ngay hoc.
