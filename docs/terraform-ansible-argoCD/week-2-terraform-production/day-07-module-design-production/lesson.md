# Day 7: Module Design for Production

**Thoi gian:** 2 gio | **Level:** Intermediate-Advanced | **Phase:** 2 - Terraform Production  
**Prerequisites:** Day 1-6, dac biet Day 6 VPC module lab

---

## 1. Muc tieu ngay hoc

Sau buoi hoc nay, ban co the:

1. Xac dinh dung ranh gioi cua mot module (module boundary) bang cach ap dung it nhat 2 tieu chi cu the: lifecycle alignment va blast radius
2. Thiet ke interface (input/output) cua mot module theo cac nguyen tac: minimal surface area, backward compatibility, validation co y nghia
3. Phan tich su khac biet giua opinionated module va flexible module, chon dung loai theo context (ca nhan / small team / enterprise / regulated)
4. Tra loi duoc cau hoi "khi nao can tach module?" va "khi nao gop module la sai?" bang cac vi du cu the tu production incident
5. Refactor VPC module tu Day 6 theo production standards: them security group co ban, VPC Flow Logs, output co structured type, va versioning ro rang

---

## 2. Boi canh thuc te

### Van de thuc te

Tai Day 6, ban da co mot VPC module chay duoc. No tao ra VPC, subnets, IGW, NAT Gateway, route tables. Module do co the reuse, co input/output.

Nhung "chay duoc" va "production-ready" la hai cai hoan toan khac nhau.

Ban hay tuong tuong ban la Platform Engineer tai mot startup vua Series A. Tech stack: 8 microservices, 3 environment (dev/staging/prod), team gom 6 engineer. Ban vua duoc giao nhiem vu: "Chuan bi Terraform module cho toan bo team dung. Phai dung duoc cho 6 thang toi khi team grow len 20 nguoi."

**Cau hoi khong ai hoi nhung ai cung can biet:**
- Module nay se phat trien nhu the nao khi yeu cau thay doi?
- Neu security team yeu cau bat VPC Flow Logs tren tat ca VPC, ban phai update bao nhieu cho?
- Neu team Auth muon dung module cua ban nhung can config Security Group rieng, ho co the lam khong?
- Khi ban rename mot output de dat ten dep hon, co bao nhieu pipeline se bi break?

### Neu khong thiet ke module dung cach, team gap loi gi?

**Loi 1 - God module (monolithic module):**

```
Incident thuc te: Platform team tai mot fintech startup tao mot module duy nhat
gom tat ca: VPC + subnets + security groups + NAT + flow logs + VPC endpoints.
Module nay co 47 input variables va 23 outputs.

3 thang sau:
- terraform plan mat 8 phut vi qua nhieu resource
- Them tag vao SG = force recreate toan bo VPC (wrong lifecycle)  
- Khong ai dam sua module vi side effect khong ro
- "Module archaeology": phai doc 500 dong code de hieu mot thing nho
```

**Loi 2 - Leaky abstraction:**

```
Module VPC expose ra output "aws_vpc_main_id" (internal resource name ro ra ngoai).
6 thang sau muon doi ten resource tu "main" sang "primary" -> phai doi ca output name
-> breaking change cho 12 noi dang dung module nay.
```

**Loi 3 - Over-flexible module (la god config):**

```
Module co flag "enable_everything" boolean. Hoac accept raw JSON config de truyen thang
vao resource. Cai nay khong phai abstraction - day la config wrapper.
Gia tri của module la enforce standards, khong phai pass-through config.
```

**Loi 4 - Under-validated module:**

```
Module VPC nhan "vpc_cidr" la string, khong validate.
Engineer nao do truyen "10.0.0.0/8" (qua lon) cho prod VPC.
Terraform apply thanh cong. 2 tuan sau, VPC peering fail vi CIDR overlap voi partner network.
Rollback kho khan do state phuc tap.
```

### Van de nay trong microservices

Trong he thong microservices, platform team dong vai tro "infrastructure provider" - giong nhu npm registry nhung cho Terraform. Moi service team la "consumer."

```
Platform team publish:       Service team consume:
  - module/vpc v2.1          module "vpc" {
  - module/eks v1.4            source  = "git::...//vpc?ref=v2.1"
  - module/rds v3.0            vpc_cidr = "10.5.0.0/16"
  - module/alb v1.1            ...
                             }
```

Van de xuat hien khi:
- Service team A can feature X trong module, service team B khong can nhung se bi anh huong
- Platform team muon enforce security policy nhung khong muon break consumer API
- Consumer dang o v1.2, platform team da o v2.0, co breaking change giua 2 phien ban
- Scale team tu 6 len 20, nhieu team hon, nhieu use case hon, module can handle nhieu context hon

Day la ly do module design quan trong nhu API design trong microservices.

---

## 3. Kien thuc nen tang - 30 phut

### 3.1 Module Boundary - Khi nao tach, khi nao gop

Module boundary la quyết dinh: "Resource nao nen nam trong cung mot module?"

Co hai nguyen tac chinh:

**Nguyen tac 1: Lifecycle Alignment**

Resource co cung lifecycle (tao cung luc, xoa cung luc, update cung ly do) nen nam trong cung module.

```
Lifecycle analysis cho VPC networking:

Stable (hiem khi thay doi):
  aws_vpc                  -- tao 1 lan, ton tai hang nam
  aws_internet_gateway     -- tao cung VPC, xoa cung VPC
  aws_subnet.public/private -- thay doi khi add AZ moi (it khi)

Moderate (thay doi theo dich vu):
  aws_nat_gateway          -- on/off theo chi phi, thay doi cau hinh
  aws_route_table          -- thay doi khi add routing rule

Frequent (thay doi thuong xuyen):
  aws_security_group       -- thay doi khi app requirements doi
  aws_security_group_rule  -- thay doi moi khi add/remove inbound rule

Conclusion: VPC + IGW + subnet + basic route table = cung module.
NAT gateway = co the rieng (optional, costly).
Security group = NEN rieng vi lifecycle khac.
```

**Nguyen tac 2: Blast Radius**

Khi module thay doi (plan/apply), resource nao co the bi anh huong? Blast radius cang lon, rui ro cang cao.

```
Blast Radius Analysis:

[VPC] -> [IGW] -> [Subnet] -> [Route Table]
  |
  +---> [NAT Gateway] -> [EIP]
  |
  +---> [Security Group] -> [Security Group Rule]
  |
  +---> [VPC Flow Log] -> [CloudWatch Log Group]
  |
  +---> [VPC Endpoint]

Neu tat ca nam trong 1 module:
  - Doi 1 tag trong Security Group = plan show change cho tat ca
  - Rui ro nham "yes" va thay doi nhieu hon du dinh
  - Kho review plan output khi co 40 resource changes

Neu tach thanh module rieng biet:
  - vpc-core: VPC + IGW + Subnet + basic Route Table  (9 resources)
  - security-groups: Security Group + Rules           (5-10 resources)
  - vpc-extras: Flow Logs + Endpoints                 (2-4 resources)
  
  Blast radius cua moi module nho hon, de review va an toan hon.
```

**Decision Tree - Nen tach hay gop?**

```
Dat cau hoi:                          Tra loi:
                                      
1. Co bao gio resource A duoc         Khong bao gio -> Co the gop
   update ma khong update B?          Thuong xuyen   -> Nen tach
   
2. Neu update A fail, B co bi         Khong          -> Co the gop
   anh huong khong?                   Co             -> Phan tich tiep
   
3. Nhieu team khac nhau quan          Khong          -> Co the gop
   ly A va B?                         Co             -> Nen tach
   
4. A co the ton tai ma khong          Khong          -> Gop
   co B, hoac nguoc lai?              Co             -> Tach
```

**Analogy voi programming:**

Day la cung cau hoi khi thiet ke class hay package trong OOP:
- Single Responsibility Principle: module lam mot viec, lam tot
- Coupling: module phu thuoc it vao module khac
- Cohesion: resource ben trong module co lien quan chat voi nhau

```
// Software analogy
// Bad: God class
class NetworkingSystem {
  createVPC()
  createSubnet()
  createSecurityGroup()
  configureFirewallRules()
  setupFlowLogs()
  createVPCPeering()
  manageEndpoints()
}

// Good: Separate concerns
class VPCManager { createVPC(); createSubnet() }
class SecurityManager { createSecurityGroup(); addRules() }
class ObservabilityManager { setupFlowLogs() }
```

### 3.2 Module Interface Design - Input/Output ro rang

Interface cua module la contract giua module va caller. Design tot = stable contract, it breaking change.

**Nguyen tac thiet ke Input:**

```
1. Minimal necessary surface - chi expose input can thiet
2. Sensible defaults - co default cho optional config
3. Validated constraints - phan loai dau vao, bao ve module khoi invalid state
4. Descriptive names - ten variable phai giai thich ro y nghia
5. Group related variables - dung object type khi co nhom lien quan
```

**Vi du - Bad vs Good interface:**

```hcl
# BAD: Flat, qua nhieu variable, khong ro rang
variable "nat_az1" { type = bool }
variable "nat_az2" { type = bool }
variable "nat_az3" { type = bool }
variable "nat_eip_az1" { type = string }
variable "nat_eip_az2" { type = string }

# GOOD: Structured, ro rang y dinh
variable "nat_gateway_config" {
  description = "Cau hinh NAT Gateway. null = khong tao NAT Gateway."
  type = object({
    enabled            = bool
    single_az          = bool        # true = tiet kiem chi phi, false = full HA
    reuse_eip_ids      = optional(list(string), [])  # Pre-allocated EIPs
  })
  default = {
    enabled   = false
    single_az = true
  }
}
```

**Nguyen tac thiet ke Output:**

```
1. Abstract, khong expose internal - output "vpc_id" tot hon "aws_vpc_main_id"
2. Chi output cai caller can - khong output tat ca attribute cua tat ca resource
3. Structured output khi co nhieu related values - dung object
4. Stable names - doi ten output = breaking change
5. Description day du - caller phai hieu y nghia khong can doc source
```

```hcl
# BAD: Expose internal implementation detail
output "aws_vpc_main_id" { value = aws_vpc.main.id }  # "main" la internal name
output "aws_subnet_public_0_id" { value = aws_subnet.public[0].id }  # Fragile

# GOOD: Abstract interface
output "vpc_id" {
  description = "ID cua VPC. Su dung de reference VPC trong cac module khac."
  value       = aws_vpc.main.id
}

output "subnet_ids" {
  description = "Structured subnet information theo tier va AZ."
  value = {
    public  = aws_subnet.public[*].id
    private = aws_subnet.private[*].id
  }
}
```

### 3.3 Opinionated vs Flexible Module

Day la spectrum, khong phai binary choice.

```
SPECTRUM:

Fully Opinionated                          Fully Flexible
     |                                          |
     |--- Internal Platform Module ------|      |
     |                                   |      |
     |              |--- Wrapper Module --|      |
     |                                   |      |
     |                        |--- Config Passthrough ---|

Fully Opinionated:
  - It input variable (co the chi 3-5)
  - Enforce company standards (naming, tagging, logging)
  - Khong the tat feature bat buoc (VPC Flow Logs luon bat)
  - Easy to use, hard to misuse
  - Vi du: internal platform module cho moi team dung

Fully Flexible:
  - Nhieu input variable (co the 30-50+)
  - Caller phai biet nhieu ve internals
  - Co the configure moi thu
  - Powerful nhung de misuse
  - Vi du: terraform-aws-modules/vpc/aws (community module)
```

**Khi nao dung Opinionated:**
- Module dung noi bo team/org, enforce standards
- Caller khong nen (va khong can) biet implementation detail
- Security/compliance bat buoc mot so feature
- Muon don gian hoa experience cho consumer team

**Khi nao dung Flexible:**
- Building block cho nhieu use case khac nhau
- Module dung boi nhieu org khac nhau (public / shared)
- Consumer can fine-tune vi use case dac biet

**Trong thuc te:** Noi bo team nen opinionated. Neu co community module (terraform-aws-modules), dung no va wrap them opinionated layer tren ngoai.

```hcl
# Pattern: Wrap community module voi opinionated internal module
module "vpc_internal" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # Caller khong expose nhung args nay - platform team enforce
  enable_flow_log                      = true
  flow_log_cloudwatch_log_group_name   = "/aws/vpc/${var.project_name}-${var.environment}"
  flow_log_traffic_type                = "ALL"
  flow_log_destination_type            = "cloud-watch-logs"
  
  # Caller co the customize nhung args nay
  name            = "${var.project_name}-${var.environment}"
  cidr            = var.vpc_cidr
  azs             = var.availability_zones
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs
}
```

### 3.4 Avoid Over-Abstraction

Over-abstraction xay ra khi module "giup do" caller qua muc, khien caller mat kha nang hieu va debug infrastructure cua chinh ho.

**Dau hieu over-abstraction:**

```
1. Module nhan "environment" = "prod" va tu dong thay doi hanh vi hoan toan
   (enable_deletion_protection, instance size, multi-AZ, backup retention...)
   -> Caller khong biet chinh xac resource se duoc tao ra nhu the nao

2. Module gop qua nhieu concern vao mot:
   module "my_full_stack" {
     vpc_cidr     = ...
     rds_instance = "db.t3.large"
     eks_version  = "1.28"
     domain_name  = "api.myapp.com"
   }
   -> Khong the deploy chi update networking ma khong risk anh huong RDS/EKS

3. Module an qua nhieu decision:
   enable_nat_gateway = true  -> module tu quyet dinh size EIP, so luong AZ, timeout...
   Caller khong biet va khong kiem soat duoc

4. Module "magic behavior" - output khac voi input theo cach khong ro rang:
   env = "prod" -> automatically set deletion_protection = true,
                   multi_az = true, backup_retention_period = 30
   Caller khong biet tru khi doc code
```

**Nguon goc metaphor tu programming:**

```python
# Over-abstracted function - qua nhieu magic
def deploy_app(env: str):
    if env == "prod":
        replicas = 10
        cpu = "4"
        memory = "8Gi"
        autoscaling = True
        monitoring = "full"
    # Caller mat kha nang control
    
# Better: Explicit tham so, caller quyet dinh
def deploy_app(replicas: int, cpu: str, memory: str, autoscaling: bool):
    # Module chi organize deployment, khong an decision
```

**Rule of thumb:**
- Neu caller can doc source code de hieu module se lam gi, abstraction bi qua day
- Neu caller khong the doan duoc output tu input (khong co magic/conditional behavior), abstraction dang tot

### 3.5 Diagram - Module Dependency va Interface

```
                    ROOT MODULE (environments/dev/main.tf)
                    
  tfvars ─────────► variables.tf
                         │
                         ▼
               ┌─────────────────────────────────────────┐
               │            module "vpc"                  │
               │  source = "../../modules/vpc-production" │
               │                                          │
               │  Input (explicit contract):              │
               │  - project_name = "myapp"                │
               │  - environment  = "dev"                  │
               │  - vpc_cidr     = "10.10.0.0/16"         │
               │  - azs          = ["ap-southeast-1a"...] │
               │  - nat_config   = { enabled = false }    │
               └─────────────────────────────────────────┘
                         │
                         │ Output (stable interface):
                         │  - vpc_id
                         │  - subnet_ids.public[]
                         │  - subnet_ids.private[]
                         │  - default_sg_id
                         ▼
               ┌─────────────────────────────────────────┐
               │          module "eks"                    │
               │  vpc_id        = module.vpc.vpc_id       │
               │  subnet_ids    = module.vpc.subnet_ids   │
               │                  .private                │
               └─────────────────────────────────────────┘
               
               ┌─────────────────────────────────────────┐
               │          module "rds"                    │
               │  vpc_id        = module.vpc.vpc_id       │
               │  subnet_ids    = module.vpc.subnet_ids   │
               │                  .private                │
               └─────────────────────────────────────────┘
```

---

## 4. Deep Dive & Trade-offs - 30 phut

### 4.1 Phan tich 3 cach tiep can Module Design

**Approach A: Mono-Module (Fat Module)**

Mot module chua tat ca networking resources.

```
modules/
  networking/
    main.tf      # VPC + subnets + IGW + NAT + SG + Flow Logs + Endpoints
    variables.tf # 30+ variables
    outputs.tf   # 15+ outputs
```

| Khia canh | Danh gia |
|-----------|----------|
| Ease of use | Tot: caller chi goi 1 module |
| Blast radius | Xau: 1 thay doi nho = plan 30+ resources |
| Team collaboration | Xau: nhieu nguoi sua 1 file, conflict nhieu |
| Reusability | Xau: kho reuse 1 phan rieng le |
| Testing | Xau: phai spin up toan bo infra de test |
| Plan performance | Xau: cham khi qua nhieu resource |
| Onboarding | Tot: new engineer hoc 1 module |

**Approach B: Micro-Module (Fine-grained)**

```
modules/
  vpc-core/          # Chi VPC + DNS settings
  subnets/           # Chi subnet
  igw/               # Chi Internet Gateway
  nat-gateway/       # Chi NAT Gateway  
  route-tables/      # Chi route tables
  security-groups/   # Chi SG
  flow-logs/         # Chi VPC Flow Logs
```

| Khia canh | Danh gia |
|-----------|----------|
| Blast radius | Tot: moi module co 2-4 resource |
| Reusability | Tot: pick exactly cai can |
| Dependency wiring | Xau: caller phai wire nhieu module |
| Cognitive load | Xau: caller phai hieu toan bo networking stack |
| Onboarding | Xau: new engineer bi overwhelm |
| Team ownership | Tot: clear ownership per module |

**Approach C: Pragmatic Boundary (Recommended)**

```
modules/
  vpc/               # VPC + subnets + IGW + route tables (always together)
  nat-gateway/       # Optional va costly, rieng biet
  security-groups/   # Different per-app, rieng biet
  vpc-extras/        # Flow logs, endpoints (optional compliance features)
```

| Khia canh | Danh gia |
|-----------|----------|
| Blast radius | Vua: 8-12 resource per module core |
| Ease of use | Vua: caller goi 1-3 module tuy need |
| Reusability | Tot: core + optional composition |
| Team collaboration | Tot: clear boundary, it conflict |
| Onboarding | Tot: logic boundary de hieu |

### 4.2 So sanh: Opinionated vs Flexible

| Tieu chi | Opinionated Module | Flexible Module |
|----------|-------------------|-----------------|
| So input variable | Thap (3-8) | Cao (20-50+) |
| Default value | Nhieu, co y nghia | It hoac khong co |
| Standards enforcement | Co, embedded | Khong, caller quyet dinh |
| Ease of use | Cao | Thap (phai doc doc) |
| Configurability | Thap | Cao |
| Blast radius khi update | Tat ca consumer bi anh huong | Tuy consumer config |
| Thich hop cho | Internal platform team | Community / shared library |
| Vi du thuc te | Company internal VPC module | terraform-aws-modules/vpc/aws |
| Breaking change risk | Cao (enforce = moi change la breaking) | Thap (opt-in) |
| Security compliance | Tot (enforce baked in) | Tuy caller |

**Best solution theo context:**

| Context | Recommendation | Ly do |
|---------|---------------|-------|
| Ca nhan / side project | Flexible, viet nhanh | Chi co 1 consumer (ban), khong can enforce |
| Small team (2-5 dev) | Pragmatic + it opinionated | Balance: don gian + co ban chuan |
| Startup (5-20 dev) | Opinionated internal + wrap community | Enforce standards, van tan dung community work |
| Enterprise (20+ dev) | Strongly opinionated + versioned API | Nhieu consumer, stability quan trong |
| Bank / Regulated | Opinionated + immutable releases + audit log | Compliance, cannot skip security controls |

### 4.3 Versioning Strategy So sanh

| Strategy | Cach lam | Uu diem | Nhuoc diem | Phu hop |
|----------|---------|---------|-----------|---------|
| Local path | `source = "./modules/vpc"` | Don gian, khong can version | Tat ca dung cung version | Team nho, mono-repo |
| Git tag | `?ref=v2.1.0` | Pin exact version, co CHANGELOG | Phai manage Git tags | Team vua |
| Git branch | `?ref=main` | Luon latest | Khong reproducible, xau cho prod | Development only |
| Private Registry | HCP Terraform / Artifactory | UI, search, versioned, access control | Chi phi, complexity | Enterprise |
| Semantic versioning | `~> 2.1` (minor updates OK) | Flexible nhung co gia tri | Consumer co the bi surprise update | Community module |

**Versioning decision matrix:**

```
Q: Module nay co bao nhieu consumer?
  - 1 (ban tu dung): Local path, khong can version
  - 2-5 (cung team): Git tag tren cung repo
  - 6+ (nhieu team): Separate repo + Git tag + CHANGELOG
  - 20+ hoac external: Private Registry

Q: Consumer co pin version khong?
  - Pin exact: version = "= 2.1.3"  (prod)
  - Pin minor: version = "~> 2.1"   (staging)
  - Pin major: version = "~> 2.0"   (dev, chap nhan minor changes)
```

### 4.4 Performance, Cost, Security, Operational Complexity

**Performance implications:**

`terraform plan` phai refresh state cua tat ca resource trong module. Module lon = plan cham.
- 10 resource: plan ~5-10 giay
- 50 resource: plan ~30-60 giay
- 150+ resource: plan co the mat 3-5 phut

Tach module = chay plan tren subset resources = nhanh hon, phan hoi nhanh hon cho engineer.

**Cost implications:**

Mot so resource ton tien (NAT Gateway ~$32/thang). Neu nam trong fat module, kho biet chính xác chi phi cua tung component. Tach module nho = cost tracking ro rang hon.

Tag strategy gan voi module boundary:
```hcl
# Neu nat-gateway la module rieng, ban co the tag chinh xac
tags = { CostCenter = "networking-nat", Module = "nat-gateway" }
```

**Security implications:**

- Module lon voi nhieu IAM permission = blast radius lon neu bi compromise
- Tach module = least-privilege trên module level
- Sensitive output (private key, password) nen duoc `sensitive = true` va chi output khi can thiet
- Security group tach rieng = security team co the review va approve SG changes doc lap voi networking changes

**Operational complexity:**

| Aspect | Fat Module | Micro Module | Pragmatic |
|--------|-----------|-------------|-----------|
| Module count | Thap | Cao | Vua |
| Wiring complexity | Thap | Cao | Vua |
| Debugging speed | Cham (nhieu resource) | Nhanh (it resource) | Vua |
| Rollback scope | Lon | Nho | Vua |
| CI/CD pipeline | Don gian | Phuc tap | Vua |

### 4.5 Common Pitfalls Chi Tiet

**Pitfall 1 - God Module:**

Dau hieu: module co tren 15 input variable va tren 50 resource. Fix: phan tich lifecycle, tach theo principle o Section 3.1.

**Pitfall 2 - Tight Coupling qua Output:**

```hcl
# BAD: Output expose too much internal state
output "vpc_object" {
  value = aws_vpc.main  # Expose toan bo resource object
}
# Caller gio co the depend vao bat ky attribute nao cua VPC
# Khi AWS them attribute moi = "surprise" change trong output
# Khi ban refactor (doi ten resource) = breaking change

# GOOD: Expose chi nhung gi can thiet
output "vpc_id" { value = aws_vpc.main.id }
output "vpc_cidr" { value = aws_vpc.main.cidr_block }
```

**Pitfall 3 - Input Variable Name Collision:**

```hcl
# BAD: "name" va "tags" la qua generic
variable "name" { ... }
variable "tags" { ... }

# Khi compose nhieu module, caller phai know which module's "name" is which
# GOOD: Specific, can't be confused
variable "vpc_name_override" {
  description = "Override VPC name. Default: {project}-{env}-vpc"
  type        = string
  default     = null
}
```

**Pitfall 4 - Missing Validation cho Cross-Variable Constraints:**

```hcl
# BAD: Neu nat_config.enabled = true nhung khong co public subnet -> runtime error tu AWS
variable "nat_config" { ... }
variable "public_subnet_cidrs" { ... }

# GOOD: Validate cross-variable constraint
locals {
  # Validation inline
  _validate_nat_requires_public_subnet = (
    var.nat_config.enabled && length(var.public_subnet_cidrs) == 0
    ? tobool("ERROR: NAT Gateway yeu cau it nhat 1 public subnet")
    : true
  )
}
```

**Pitfall 5 - Khong co Backward Compatibility Plan:**

```
Anti-pattern:
v1.0: output "subnet_ids" { value = list }
v2.0: output "subnet_ids" { value = object({public=[], private=[]}) }
-> Breaking change! Tat ca consumer bi loi.

Better:
v2.0: Giu "subnet_ids" cu (deprecated nhung van hoat dong)
      Them "subnet_ids_by_tier" moi
v3.0: Xoa "subnet_ids" cu (sau khi consumer da migrate)
      Document deprecation ro rang
```

---

## 5. Hands-on Lab - 60 phut

### Muc tieu lab

Refactor VPC module tu Day 6 theo production standards:
- Them Security Group co ban (egress-only default SG)
- Them VPC Flow Logs (opinionated: bat mac dinh, co the tat)
- Structured output thay vi flat list
- Cross-variable validation
- Ro rang versioning block
- Clean naming convention

Ket qua lab nay se duoc dung truc tiep trong Day 8 (Multi-Environment).

### Cau truc thu muc sau lab

```
day-07-lab/
├── modules/
│   └── vpc-production/          <- Module moi, production-grade
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── flow_logs.tf         <- Tach file cho clarity
│       ├── security_groups.tf   <- Tach file cho clarity
│       └── versions.tf
└── environments/
    └── dev/                     <- Root module cho dev
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        ├── backend.tf
        └── terraform.tfvars
```

**Tai sao tach file (flow_logs.tf, security_groups.tf)?**

Terraform merge tat ca `.tf` file trong mot thu muc. Khong co requirement phai viet tat ca trong `main.tf`. Tach file theo concern giup:
- De navigate khi debug
- Git diff ro rang hon (ai thay doi networking, ai thay doi security)
- New engineer hieu structure nhanh hon

### Buoc 1 - Tao thu muc

```bash
mkdir -p ~/terraform-day7-lab/modules/vpc-production
mkdir -p ~/terraform-day7-lab/environments/dev

cd ~/terraform-day7-lab
```

### Buoc 2 - Viet versions.tf

```bash
cat > ~/terraform-day7-lab/modules/vpc-production/versions.tf << 'EOF'
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0, < 6.0.0"
    }
  }
}
EOF
```

Luu y: Day 6 dung `~> 5.0`, Day 7 dung `>= 5.0.0, < 6.0.0`. Hai cach tuong duong nhau trong tac dung nhung cach viet `>=, <` ro rang hon ve semantic (cho ai chua biet pessimistic constraint operator).

### Buoc 3 - Viet variables.tf voi structured types

File `~/terraform-day7-lab/modules/vpc-production/variables.tf`:

```hcl
# ==============================================================================
# REQUIRED VARIABLES - Khong co default, caller phai truyen gia tri
# ==============================================================================

variable "project_name" {
  description = <<-EOT
    Ten project. Duoc dung lam prefix cho tat ca resource name.
    Chi chua lowercase letters, numbers, va hyphens.
    Vi du: "myapp", "payment-service", "data-platform"
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,28}[a-z0-9]$", var.project_name))
    error_message = "project_name phai: bat dau bang lowercase letter, chi chua [a-z0-9-], dai 3-30 ky tu."
  }
}

variable "environment" {
  description = "Ten environment. Anh huong den sizing va feature defaults."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment phai la mot trong: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = <<-EOT
    CIDR block cho VPC. Phai la /16 hoac nho hon (khong qua lon).
    Chon CIDR khong overlap voi cac VPC khac trong cung region/account.
    Vi du: "10.10.0.0/16" cho dev, "10.11.0.0/16" cho staging, "10.0.0.0/16" cho prod.
  EOT
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr phai la valid CIDR notation. Vi du: 10.0.0.0/16"
  }

  validation {
    condition = (
      tonumber(split("/", var.vpc_cidr)[1]) >= 16 &&
      tonumber(split("/", var.vpc_cidr)[1]) <= 28
    )
    error_message = "vpc_cidr prefix phai tu /16 den /28. /8 hoac /12 qua lon cho VPC."
  }
}

variable "availability_zones" {
  description = <<-EOT
    Danh sach Availability Zones se deploy subnets vao.
    Khuyen nghi: 2 AZ cho dev/staging, 3 AZ cho prod.
    Vi du: ["ap-southeast-1a", "ap-southeast-1b"]
  EOT
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 1 && length(var.availability_zones) <= 4
    error_message = "availability_zones phai co tu 1 den 4 AZ."
  }
}

variable "public_subnet_cidrs" {
  description = <<-EOT
    Danh sach CIDR cho public subnets.
    So luong phai bang so AZ (availability_zones).
    Public subnet se duoc gan public IP tu dong.
    Vi du: ["10.10.1.0/24", "10.10.2.0/24"]
  EOT
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_cidrs) > 0
    error_message = "Phai co it nhat 1 public subnet CIDR."
  }
}

variable "private_subnet_cidrs" {
  description = <<-EOT
    Danh sach CIDR cho private subnets.
    So luong phai bang so AZ (availability_zones).
    Private subnet khong co public IP, network egress qua NAT Gateway (neu bat).
    Vi du: ["10.10.11.0/24", "10.10.12.0/24"]
  EOT
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_cidrs) > 0
    error_message = "Phai co it nhat 1 private subnet CIDR."
  }
}

# ==============================================================================
# OPTIONAL VARIABLES - Co default, caller co the override
# ==============================================================================

variable "nat_gateway_config" {
  description = <<-EOT
    Cau hinh NAT Gateway cho private subnets.
    enabled = true: Private subnets co internet egress qua NAT.
    single_az = true: Tiet kiem chi phi (~$32/thang) nhung mat HA.
    single_az = false: Full HA (1 NAT per AZ) nhung ton ~$32/thang/AZ.
    
    Default: disabled (tiet kiem chi phi trong dev)
    Production recommendation: enabled = true, single_az = false
  EOT
  type = object({
    enabled   = bool
    single_az = optional(bool, true)
  })
  default = {
    enabled   = false
    single_az = true
  }
}

variable "flow_logs_config" {
  description = <<-EOT
    Cau hinh VPC Flow Logs. Bat mac dinh de dam bao security visibility.
    enabled = false chi duoc phep cho dev environment de tiet kiem chi phi.
    
    retention_days: So ngay giu log trong CloudWatch.
    traffic_type: "ALL" (recommended), "ACCEPT", "REJECT"
  EOT
  type = object({
    enabled        = optional(bool, true)
    retention_days = optional(number, 7)
    traffic_type   = optional(string, "ALL")
  })
  default = {}

  validation {
    condition     = contains(["ALL", "ACCEPT", "REJECT"], var.flow_logs_config.traffic_type)
    error_message = "flow_logs_config.traffic_type phai la: ALL, ACCEPT, hoac REJECT."
  }

  validation {
    condition     = var.flow_logs_config.retention_days >= 1 && var.flow_logs_config.retention_days <= 3653
    error_message = "flow_logs_config.retention_days phai tu 1 den 3653 (10 nam)."
  }
}

variable "tags" {
  description = "Map cac tag bo sung. Se duoc merge voi common tags cua module."
  type        = map(string)
  default     = {}
}
```

### Buoc 4 - Viet main.tf (VPC core resources)

File `~/terraform-day7-lab/modules/vpc-production/main.tf`:

```hcl
# ==============================================================================
# LOCAL VALUES - Computed values dung trong module
# ==============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Common tags ap dung len tat ca resource
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "vpc-production"
      ModuleVersion = "0.1.0"
    },
    var.tags
  )

  # Tinh so luong NAT Gateway
  nat_count = var.nat_gateway_config.enabled ? (
    var.nat_gateway_config.single_az ? 1 : length(var.availability_zones)
  ) : 0

  # Validation: so luong subnet phai bang so luong AZ
  _validate_public_subnets = (
    length(var.public_subnet_cidrs) != length(var.availability_zones)
    ? tobool("ERROR: So luong public_subnet_cidrs (${length(var.public_subnet_cidrs)}) phai bang so luong availability_zones (${length(var.availability_zones)})")
    : true
  )

  _validate_private_subnets = (
    length(var.private_subnet_cidrs) != length(var.availability_zones)
    ? tobool("ERROR: So luong private_subnet_cidrs (${length(var.private_subnet_cidrs)}) phai bang so luong availability_zones (${length(var.availability_zones)})")
    : true
  )
}

# ==============================================================================
# VPC
# ==============================================================================

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true  # Can thiet cho RDS, EKS, ECS service discovery
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# ==============================================================================
# INTERNET GATEWAY
# ==============================================================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# ==============================================================================
# SUBNETS
# ==============================================================================

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Tier = "public"
    # Kubernetes tags - can thiet cho AWS Load Balancer Controller
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Tier = "private"
    # Kubernetes tags - can thiet cho AWS Load Balancer Controller (internal LB)
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# ==============================================================================
# NAT GATEWAY (optional)
# ==============================================================================

resource "aws_eip" "nat" {
  count  = local.nat_count
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip-${count.index + 1}"
  })

  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  count = local.nat_count

  subnet_id     = aws_subnet.public[count.index].id
  allocation_id = aws_eip.nat[count.index].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-${count.index + 1}"
  })

  depends_on = [aws_internet_gateway.main]
}

# ==============================================================================
# ROUTE TABLES
# ==============================================================================

# Public route table: 0.0.0.0/0 -> Internet Gateway
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private route table(s): 0.0.0.0/0 -> NAT Gateway (neu co)
# Neu single_az: 1 route table cho tat ca private subnets
# Neu multi-az NAT: 1 route table per AZ
resource "aws_route_table" "private" {
  count  = max(local.nat_count, 1)
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = local.nat_count > 0 ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = var.nat_gateway_config.single_az ? aws_nat_gateway.main[0].id : aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt-${count.index + 1}"
  })
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id = aws_subnet.private[count.index].id
  route_table_id = (
    local.nat_count > 1
    ? aws_route_table.private[count.index].id
    : aws_route_table.private[0].id
  )
}
```

### Buoc 5 - Viet flow_logs.tf

File `~/terraform-day7-lab/modules/vpc-production/flow_logs.tf`:

```hcl
# ==============================================================================
# VPC FLOW LOGS
# Opinionated: bat mac dinh. Security team yeu cau visibility vao tat ca traffic.
# Chi co the tat qua flow_logs_config.enabled = false (va chi cho dev).
# ==============================================================================

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  count = var.flow_logs_config.enabled ? 1 : 0

  name              = "/aws/vpc/${local.name_prefix}-flow-logs"
  retention_in_days = var.flow_logs_config.retention_days

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-flow-logs"
  })
}

resource "aws_iam_role" "vpc_flow_logs" {
  count = var.flow_logs_config.enabled ? 1 : 0

  name = "${local.name_prefix}-vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  count = var.flow_logs_config.enabled ? 1 : 0

  name = "${local.name_prefix}-vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_flow_log" "main" {
  count = var.flow_logs_config.enabled ? 1 : 0

  vpc_id          = aws_vpc.main.id
  traffic_type    = var.flow_logs_config.traffic_type
  iam_role_arn    = aws_iam_role.vpc_flow_logs[0].arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_logs[0].arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-flow-log"
  })
}
```

### Buoc 6 - Viet security_groups.tf (Default VPC SG)

File `~/terraform-day7-lab/modules/vpc-production/security_groups.tf`:

```hcl
# ==============================================================================
# DEFAULT SECURITY GROUP HARDENING
# AWS tao default SG tu dong khi tao VPC. No cho phep tat ca inbound/outbound
# giua cac instance trong cung SG - day la security risk.
# Module nay "hardening" default SG bang cach xoa tat ca rule.
# ==============================================================================

resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.main.id

  # Xoa tat ca default rules (khong co ingress/egress block = khong cho phep gi)
  # Best practice: Khong dung default SG, tao rieng SG voi least-privilege

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-default-sg-DO-NOT-USE"
    Description = "Hardened default SG. Do not attach to any resource."
  })
}
```

### Buoc 7 - Viet outputs.tf voi structured types

File `~/terraform-day7-lab/modules/vpc-production/outputs.tf`:

```hcl
# ==============================================================================
# PRIMARY OUTPUTS - Nhung gi consumer thuong xuyen can
# ==============================================================================

output "vpc_id" {
  description = "ID cua VPC. Dung de reference VPC trong Security Groups, route tables, va cac module khac."
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block cua VPC. Dung de tao security group rules allow traffic tu within VPC."
  value       = aws_vpc.main.cidr_block
}

# Structured output thay vi flat list
output "subnet_ids" {
  description = <<-EOT
    Subnet IDs duoc to chuc theo tier.
    subnet_ids.public  = list(string) - Cac public subnet IDs (co public IP, reach internet truc tiep)
    subnet_ids.private = list(string) - Cac private subnet IDs (chi reach internet qua NAT neu bat)
    
    Su dung:
      module.vpc.subnet_ids.public  -> cho ALB, bastion host
      module.vpc.subnet_ids.private -> cho EKS workers, RDS, ECS tasks
  EOT
  value = {
    public  = aws_subnet.public[*].id
    private = aws_subnet.private[*].id
  }
}

output "subnet_details" {
  description = <<-EOT
    Chi tiet subnet bao gom AZ information. Dung khi ban can biet subnet nao
    nam trong AZ nao (vi du: affinity scheduling trong EKS).
    
    Format: list of objects { id, cidr, az, tier }
  EOT
  value = concat(
    [for i, s in aws_subnet.public : {
      id   = s.id
      cidr = s.cidr_block
      az   = s.availability_zone
      tier = "public"
    }],
    [for i, s in aws_subnet.private : {
      id   = s.id
      cidr = s.cidr_block
      az   = s.availability_zone
      tier = "private"
    }]
  )
}

# ==============================================================================
# GATEWAY OUTPUTS - Dung khi can tham chieu hoac add routes tu ben ngoai
# ==============================================================================

output "internet_gateway_id" {
  description = "ID cua Internet Gateway. Dung neu can add them custom routes tu root module."
  value       = aws_internet_gateway.main.id
}

output "nat_gateway_ids" {
  description = "Danh sach ID cua NAT Gateways. Empty neu nat_gateway_config.enabled = false."
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = <<-EOT
    Public IP cua NAT Gateways. Can thiet de whitelist trong external firewalls.
    Empty neu nat_gateway_config.enabled = false.
  EOT
  value = aws_eip.nat[*].public_ip
}

# ==============================================================================
# ROUTE TABLE OUTPUTS - Dung khi can add custom routes (VPN, Transit Gateway)
# ==============================================================================

output "route_table_ids" {
  description = <<-EOT
    Route table IDs duoc to chuc theo tier.
    Dung khi can add custom routes (VPN, Transit Gateway, VPC Peering).
  EOT
  value = {
    public  = [aws_route_table.public.id]
    private = aws_route_table.private[*].id
  }
}

# ==============================================================================
# SECURITY GROUP OUTPUTS
# ==============================================================================

output "default_security_group_id" {
  description = <<-EOT
    ID cua default Security Group (da duoc hardened - khong co rules).
    KHONG DUNG cai nay cho resource. Day chi de biet ID de monitoring.
    Tao SG rieng voi least-privilege rules cho moi resource type.
  EOT
  value = aws_default_security_group.default.id
}

# ==============================================================================
# FLOW LOGS OUTPUTS
# ==============================================================================

output "flow_logs_enabled" {
  description = "true neu VPC Flow Logs dang duoc bat."
  value       = var.flow_logs_config.enabled
}

output "flow_logs_log_group_name" {
  description = "Ten CloudWatch Log Group chua VPC Flow Logs. null neu flow logs tat."
  value       = var.flow_logs_config.enabled ? aws_cloudwatch_log_group.vpc_flow_logs[0].name : null
}

# ==============================================================================
# METADATA OUTPUTS - Thong tin ve module va configuration
# ==============================================================================

output "vpc_metadata" {
  description = "Metadata ve VPC configuration. Huu ich cho debugging va documentation."
  value = {
    name_prefix       = local.name_prefix
    availability_zones = var.availability_zones
    nat_enabled       = var.nat_gateway_config.enabled
    nat_single_az     = var.nat_gateway_config.single_az
    flow_logs_enabled = var.flow_logs_config.enabled
    az_count          = length(var.availability_zones)
    public_subnet_count  = length(aws_subnet.public)
    private_subnet_count = length(aws_subnet.private)
  }
}
```

### Buoc 8 - Viet Root Module (environments/dev)

**File `~/terraform-day7-lab/environments/dev/versions.tf`:**

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0, < 6.0.0"
    }
  }
}
```

**File `~/terraform-day7-lab/environments/dev/backend.tf`:**

```hcl
terraform {
  backend "s3" {
    # Thay bang gia tri tu Day 5 lab cua ban
    bucket         = "terraform-state-YOUR_ACCOUNT_ID"
    key            = "day7-lab/dev/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }
}
```

**File `~/terraform-day7-lab/environments/dev/variables.tf`:**

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Ten project"
  type        = string
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block cho VPC"
  type        = string
}
```

**File `~/terraform-day7-lab/environments/dev/main.tf`:**

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "vpc" {
  source = "../../modules/vpc-production"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr

  availability_zones   = local.azs
  public_subnet_cidrs  = [cidrsubnet(var.vpc_cidr, 8, 1), cidrsubnet(var.vpc_cidr, 8, 2)]
  private_subnet_cidrs = [cidrsubnet(var.vpc_cidr, 8, 11), cidrsubnet(var.vpc_cidr, 8, 12)]

  nat_gateway_config = {
    enabled   = false  # Tiet kiem chi phi trong dev
    single_az = true
  }

  flow_logs_config = {
    enabled        = false  # Tat trong dev de tiet kiem chi phi
    retention_days = 7
    traffic_type   = "ALL"
  }

  tags = {
    Lab = "day7-module-design"
  }
}
```

Luu y: `cidrsubnet(var.vpc_cidr, 8, 1)` tu dong tinh subnet CIDR tu VPC CIDR. Voi `vpc_cidr = "10.10.0.0/16"`, ket qua la `10.10.1.0/24`. Cach nay tot hon hardcode vi day la production pattern.

**File `~/terraform-day7-lab/environments/dev/outputs.tf`:**

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "subnet_ids" {
  description = "Subnet IDs by tier"
  value       = module.vpc.subnet_ids
}

output "vpc_metadata" {
  description = "VPC configuration metadata"
  value       = module.vpc.vpc_metadata
}

output "availability_zones" {
  description = "AZs used"
  value       = local.azs
}
```

**File `~/terraform-day7-lab/environments/dev/terraform.tfvars`:**

```hcl
aws_region   = "ap-southeast-1"
project_name = "myapp"
environment  = "dev"
vpc_cidr     = "10.10.0.0/16"
```

### Buoc 9 - Init, Plan, va Kiem tra

```bash
cd ~/terraform-day7-lab/environments/dev

terraform init
```

Expected output:
```
Initializing the backend...
Successfully configured the backend "s3"!

Initializing modules...
- vpc in ../../modules/vpc-production

Initializing provider plugins...
- Finding hashicorp/aws versions matching ">= 5.0.0, < 6.0.0"...
- Using previously-installed hashicorp/aws v5.x.x

Terraform has been successfully initialized!
```

```bash
terraform plan
```

Expected resources (voi flow_logs.enabled = false va nat_gateway.enabled = false):
```
  # module.vpc.aws_default_security_group.default will be created
  # module.vpc.aws_internet_gateway.main will be created
  # module.vpc.aws_route_table.private[0] will be created
  # module.vpc.aws_route_table.public will be created
  # module.vpc.aws_route_table_association.private[0] will be created
  # module.vpc.aws_route_table_association.private[1] will be created
  # module.vpc.aws_route_table_association.public[0] will be created
  # module.vpc.aws_route_table_association.public[1] will be created
  # module.vpc.aws_subnet.private[0] will be created
  # module.vpc.aws_subnet.private[1] will be created
  # module.vpc.aws_subnet.public[0] will be created
  # module.vpc.aws_subnet.public[1] will be created
  # module.vpc.aws_vpc.main will be created

Plan: 13 to add, 0 to change, 0 to destroy.
```

```bash
terraform apply
```

Sau khi apply, kiem tra output:
```bash
terraform output subnet_ids
```

Expected structured output (khac voi Day 6 flat list):
```
{
  "private" = [
    "subnet-0abc...",
    "subnet-0def...",
  ]
  "public" = [
    "subnet-0ghi...",
    "subnet-0jkl...",
  ]
}
```

```bash
terraform output vpc_metadata
```

Expected:
```
{
  "availability_zones" = tolist([
    "ap-southeast-1a",
    "ap-southeast-1b",
  ])
  "az_count" = 2
  "flow_logs_enabled" = false
  "name_prefix" = "myapp-dev"
  "nat_enabled" = false
  "nat_single_az" = true
  "private_subnet_count" = 2
  "public_subnet_count" = 2
}
```

### Buoc 10 - Test Validation

Thu truyen input sai de xem validation hoat dong:

```bash
# Test 1: environment sai
terraform plan -var="environment=qa"
# Expected error:
# Error: Invalid value for variable
#   environment phai la mot trong: dev, staging, prod.

# Test 2: vpc_cidr qua lon
terraform plan -var="vpc_cidr=10.0.0.0/8"
# Expected error:
# Error: Invalid value for variable
#   vpc_cidr prefix phai tu /16 den /28.

# Test 3: project_name co character sai
terraform plan -var='project_name=My App'
# Expected error:
# Error: Invalid value for variable
#   project_name phai: bat dau bang lowercase letter, chi chua [a-z0-9-]
```

### Buoc 11 - Kiem tra state structure

```bash
terraform state list
```

So sanh voi Day 6:
```
# Day 6 - Don gian hon
module.vpc.aws_vpc.main
module.vpc.aws_subnet.public[0]
...

# Day 7 - Co them resource (security group, flow logs)
module.vpc.aws_default_security_group.default
module.vpc.aws_internet_gateway.main
module.vpc.aws_route_table.private[0]
module.vpc.aws_route_table.public
module.vpc.aws_route_table_association.private[0]
module.vpc.aws_route_table_association.private[1]
module.vpc.aws_route_table_association.public[0]
module.vpc.aws_route_table_association.public[1]
module.vpc.aws_subnet.private[0]
module.vpc.aws_subnet.private[1]
module.vpc.aws_subnet.public[0]
module.vpc.aws_subnet.public[1]
module.vpc.aws_vpc.main
```

### Troubleshooting pho bien

**Loi: cidrsubnet formula tinh sai:**
```
Error: Invalid CIDR expression
cidrsubnet("10.10.0.0/16", 8, 11)
```
Dieu nay xay ra khi newbits (8) lam cho prefix qua lon. Voi /16 + 8 bits = /24 la OK. Voi /24 + 8 bits = /32 la khong hop le.
Fix: Tinh lai newbits: muon /24 tu /16 thi can 8 bits bo sung (`24-16=8`).

**Loi: tobool validation khong hoat dong trong Terraform < 1.4:**
```
Error: Invalid expression
tobool("ERROR: ...")
```
Day la technique dung cho cross-variable validation. Yeu cau Terraform >= 1.4. Dam bao `required_version = ">= 1.6.0"` trong `versions.tf`.

**Loi: Flow logs role conflict khi co nhieu VPC module:**
```
Error: EntityAlreadyExists: Role with name myapp-dev-vpc-flow-logs-role already exists.
```
Nguyen nhan: Neu goi module hai lan voi cung `project_name` va `environment`, IAM role se bi trung ten. Fix: Them unique suffix hoac dung `create_before_destroy = false`.

### Buoc 12 - Cleanup

```bash
cd ~/terraform-day7-lab/environments/dev
terraform destroy

# Expected:
# Destroy complete! Resources: 13 destroyed.
```

---

## 6. Kiem tra hieu bai

1. **Module boundary question:** Ban co resource A (VPC), B (Security Group), va C (EKS managed node group). A va B luon ton tai cung nhau. C co the danh cho nhieu VPC. B thuong xuyen thay doi do app requirements. Theo nguyen tac lifecycle alignment va blast radius, ban nen to chuc chung nhu the nao? Giai thich ly do.

2. **Interface design question:** Module VPC hien tai co output `private_subnet_ids = list(string)`. Team EKS muon biet subnet nao nam trong AZ nao de cau hinh affinity. Ban nen them output moi hay doi output cu? Neu doi, can bao truoc va plan gi de khong break consumer hien tai?

3. **Opinionated vs flexible:** Security team yeu cau: "Tat ca VPC trong prod phai bat Flow Logs voi retention 90 ngay." Neu ban dang thiet ke module opinionated, ban implement requirement nay nhu the nao trong code? Neu module flexible, ban handle nhu the nao? Approach nao reduce risk of misconfiguration hon?

4. **Versioning scenario:** Ban co `vpc-production` module v0.1.0 dang duoc dung boi 5 team (dev environment). Ban muon doi output `subnet_ids` tu `list(string)` sang `object({public, private})`. Day la breaking change. Mo ta quy trinh ban se lam de migrate ma khong lam disruption cho 5 team consumer.

5. **Debug scenario:** `terraform plan` cho module fra VPC tao ra unexpected change: `~ tags = { "Name" = "myapp-dev-vpc" -> "myapp-PROD-vpc" }` nhung ban khong thay doi gi trong code. Tim nguyen nhan co the xay ra va cach debug.

---

## 7. Tom tat cuoi ngay

### Key Points

- **Module boundary khong phai tuy y:** Lifecycle alignment va blast radius la hai tieu chi cu the. Resource co lifecycle khac nhau nen tach module. Module lon = rui ro cao khi plan/apply.

- **Interface la contract:** Output name thay doi la breaking change. Design input/output can than tu dau giong nhu design REST API - kho thay doi sau khi co consumer.

- **Opinionated module enforce standards, flexible module expose control:** Noi bo team -> opinionated. Chia se rong -> flexible va well-documented. Ket hop ca hai bang cach wrap community module voi opinionated internal wrapper.

- **Structured output tot hon flat list:** `subnet_ids.private` ro rang hon `private_subnet_ids`. Caller code sach hon, it confusion hon.

- **Validation la documentation co the chay:** `validation` block vua check input hop le vua giai thich cho caller biet constraint la gi. Tot hon comment khong ai doc.

- **Over-abstraction xau nhu under-abstraction:** Module an qua nhieu quyet dinh = caller mat kha nang kiem soat va debug. Moi magic behavior phai ro rang trong documentation.

### Outputs da tao ra

- Module `vpc-production` voi separation of concerns (main.tf, flow_logs.tf, security_groups.tf)
- Structured input (typed objects) va structured output (map, object)
- Cross-variable validation bang `tobool` trick
- Default SG hardening (best practice security)
- Root module dung `cidrsubnet()` thay vi hardcode subnet CIDRs

### Day 8 - Multi-Environment se dung module nay nhu the nao

Day 8 se tao 3 environment (dev, staging, prod) su dung cung module `vpc-production` nhung voi config khac nhau:

```
environments/
  dev/     -> nat_gateway_config.enabled = false, flow_logs = false
  staging/ -> nat_gateway_config.enabled = true, single_az = true
  prod/    -> nat_gateway_config.enabled = true, single_az = false, flow_logs = 90 ngay
```

Day chinh la gia tri cua module design tot: cung mot module template, khac nhau chi o config. No testing, no duplication, no drift.

Truoc khi hoc Day 8: Hay thu tao thu muc `environments/staging` voi cac gia tri khac, goi cung module, va xem module co respond dung voi config moi khong.

---

## 8. Tham khao them

- [Terraform Module Development](https://developer.hashicorp.com/terraform/language/modules/develop) - Official guide ve creating modules
- [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition) - Pattern cho composing modules
- [Custom Validation Rules](https://developer.hashicorp.com/terraform/language/expressions/custom-conditions) - Validation va precondition
- [Object Types](https://developer.hashicorp.com/terraform/language/expressions/type-constraints#structural-types) - Structured type constraints
- [cidrsubnet Function](https://developer.hashicorp.com/terraform/language/functions/cidrsubnet) - Dynamic CIDR calculation
- [terraform-aws-modules/vpc](https://github.com/terraform-aws-modules/terraform-aws-vpc) - Doc source code de hoc production patterns
- [Google SRE Book - Chapter 5](https://sre.google/sre-book/eliminating-toil/) - Toil elimination concept ap dung tot cho IaC module design
- [Semantic Versioning](https://semver.org/) - Hieu ro MAJOR.MINOR.PATCH truoc khi thiet ke module versioning
