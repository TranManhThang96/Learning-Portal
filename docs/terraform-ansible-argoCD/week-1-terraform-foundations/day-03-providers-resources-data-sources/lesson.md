# Day 3 - Providers, Resources, Data Sources, Dependency Graph

**Thời lượng:** 2 giờ | **Level:** Intermediate | **Prereq:** Day 1-2

---

## Mục tiêu ngày học

Sau khi hoàn thành Day 3, bạn có thể:

1. Cấu hình provider với version constraint và alias cho multi-region/multi-account
2. Phân biệt rõ resource, data source, variable - biết dùng cái nào trong tình huống nào
3. Phân tích dependency graph bằng `terraform graph` và đọc output Graphviz
4. Quản lý explicit và implicit dependency đúng cách, tránh circular dependency
5. Dùng Docker provider hoặc local provider để tạo infrastructure thật sự không tốn cloud cost

---

## Bối cảnh thực tế

### Tại sao phần này quan trọng trong production?

Bạn đã biết Terraform plan/apply từ Day 1-2. Nhưng khi infrastructure phức tạp lên - 50 resources, 3 regions, 2 AWS accounts - dependency sai là thảm họa.

**Incident thật trong production:**

**Incident 1 - Database trước Application:**
Team deploy một hệ thống gồm RDS database và ECS service. Developer quên thêm dependency giữa ECS task definition và database security group. Terraform apply chạy song song, ECS service spin up trước khi security group inbound rule cho database được tạo. Application crash ngay khi deploy. Rollback mất 40 phút vì phải figure out thứ tự.

**Incident 2 - Stale data source:**
Team dùng `data source` để lấy AMI ID mới nhất cho EC2. Mỗi lần apply, AMI ID thay đổi làm EC2 instance bị recreate. Production database trên EC2 bị xóa cùng instance. Không có backup. Data mất.

**Incident 3 - Provider version không pin:**
Upgrade Terraform từ 1.3 lên 1.6, AWS provider tự upgrade từ 4.x lên 5.x. Breaking changes trong provider 5.x làm 30 resources bị drift. Mất 2 ngày reconcile.

**Bài học chung:** Hiểu dependency graph và provider lifecycle không phải optional - đó là survival skill trong production Terraform.

---

## Kiến thức nền tảng - 30 phút

### 1. Provider - The Bridge to Infrastructure APIs

Provider là plugin Terraform dùng để giao tiếp với các API bên ngoài. AWS provider nói chuyện với AWS API. Docker provider nói chuyện với Docker daemon. Local provider làm việc với filesystem local.

**Cấu trúc provider configuration:**

```hcl
# terraform block - khai báo required providers
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    # Tên "docker" là local name - bạn dùng tên này trong code
    docker = {
      source  = "kreuzwerker/docker"   # registry.terraform.io/kreuzwerker/docker
      version = "~> 3.0"              # version constraint
    }

    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 6.0"      # range constraint
    }
  }
}

# provider block - cấu hình authentication và defaults
provider "docker" {
  host = "unix:///var/run/docker.sock"  # hoặc "npipe:////./pipe/docker_engine" trên Windows
}

provider "aws" {
  region = "ap-southeast-1"
  # Không hard-code credentials ở đây
  # Dùng env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  # Hoặc IAM role, AWS profile
}
```

**Provider version constraints - cú pháp:**

| Constraint | Ý nghĩa | Khi dùng |
|-----------|---------|---------|
| `= 3.0.0` | Chính xác version này | Rất hiếm, thường không nên |
| `>= 3.0.0` | Từ version này trở lên | Khi muốn linh hoạt |
| `~> 3.0` | >= 3.0, < 4.0 (minor updates ok) | **Recommended** cho most cases |
| `~> 3.0.1` | >= 3.0.1, < 3.1.0 (patch only) | Khi cần stability cao |
| `>= 3.0, < 4.0` | Range tường minh | Khi cần control chính xác |

**Provider Alias - multi-region/multi-account:**

```hcl
# Provider mặc định
provider "aws" {
  region = "ap-southeast-1"  # Singapore - primary region
}

# Provider alias cho secondary region
provider "aws" {
  alias  = "us_east"
  region = "us-east-1"
}

# Provider alias cho account khác (dùng assume_role)
provider "aws" {
  alias  = "staging"
  region = "ap-southeast-1"
  assume_role {
    role_arn = "arn:aws:iam::STAGING_ACCOUNT_ID:role/TerraformRole"
  }
}

# Resource dùng alias provider
resource "aws_s3_bucket" "us_backup" {
  provider = aws.us_east   # chỉ định dùng alias provider
  bucket   = "my-app-us-backup"
}

resource "aws_s3_bucket" "primary" {
  # Không chỉ định provider -> dùng default provider
  bucket = "my-app-primary"
}
```

---

### 2. Resource Lifecycle - Vòng đời của một resource

Mỗi resource trong Terraform có 4 operations cơ bản. Hiểu lifecycle giúp bạn predict behavior khi thay đổi config.

```
┌─────────────────────────────────────────────────────────────┐
│                   Resource Lifecycle                        │
│                                                             │
│   terraform apply           terraform apply                 │
│   (first time)              (change config)                 │
│        │                         │                          │
│        ▼                         ▼                          │
│   ┌─────────┐            ┌─────────────┐                   │
│   │ CREATE  │            │   UPDATE    │  (in-place)        │
│   │         │            │  hoặc       │                   │
│   │ API call│            │  REPLACE    │  (destroy+create)  │
│   └────┬────┘            └──────┬──────┘                   │
│        │                        │                           │
│        ▼                        ▼                           │
│   ┌─────────┐            ┌─────────────┐                   │
│   │  READ   │◄───────────│    READ     │                   │
│   │ (state  │            │  (refresh)  │                   │
│   │  saved) │            └─────────────┘                   │
│   └─────────┘                                               │
│                                                             │
│   terraform destroy                                         │
│        │                                                    │
│        ▼                                                    │
│   ┌─────────┐                                               │
│   │ DELETE  │                                               │
│   └─────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

**Ví dụ resource lifecycle trong code:**

```hcl
resource "docker_container" "app" {
  name  = "my-app"
  image = docker_image.app.image_id

  # lifecycle block kiểm soát behavior
  lifecycle {
    # Không destroy resource nếu có thay đổi - hỏi thêm
    prevent_destroy = true

    # Ignore thay đổi ở một số attributes
    # Dùng khi attribute bị thay đổi bởi external process
    ignore_changes = [
      labels,  # Docker labels có thể bị thay đổi bởi Docker daemon
    ]

    # Create replacement TRƯỚC KHI destroy instance cũ
    # Dùng cho zero-downtime replace (khi cloud cho phép)
    create_before_destroy = true
  }
}
```

**UPDATE vs REPLACE - quan trọng:**

Khi bạn thay đổi một attribute của resource:
- Một số attribute cho phép **update in-place** (không downtime) - ví dụ: change Docker container environment variable thông qua update
- Một số attribute **forces replacement** (destroy + create mới) - ví dụ: change Docker image, change EC2 instance type trong một số cases

Terraform sẽ báo `# forces replacement` trong plan output. Luôn đọc plan kỹ trước khi apply.

---

### 3. Data Source - Đọc thông tin, không quản lý

Data source cho phép Terraform **đọc** thông tin từ provider mà không tạo hay quản lý resource đó.

```hcl
# DATA SOURCE - chỉ đọc, không tạo mới
data "docker_image" "nginx" {
  name = "nginx:1.27-alpine"   # Phải tồn tại trong Docker registry hoặc local
}

# RESOURCE - Terraform tạo và quản lý
resource "docker_image" "custom_app" {
  name = "my-custom-app:1.0"
  # ...
}
```

**So sánh Resource vs Data Source vs Variable:**

```
┌──────────────────────────────────────────────────────────────────────┐
│              Resource vs Data Source vs Variable                     │
├───────────────┬──────────────────┬──────────────────────────────────┤
│               │     Resource     │  Data Source  │    Variable      │
├───────────────┼──────────────────┼───────────────┼──────────────────┤
│ Terraform     │ Tạo, update,     │ Chỉ read      │ Không tương tác  │
│ manages?      │ delete           │               │ với provider     │
├───────────────┼──────────────────┼───────────────┼──────────────────┤
│ Nằm trong     │ terraform.tfstate│ Không (fetch  │ Không            │
│ state?        │                  │ mỗi plan/apply│                  │
├───────────────┼──────────────────┼───────────────┼──────────────────┤
│ Dùng khi      │ Muốn Terraform   │ Resource tồn  │ Giá trị đến từ   │
│               │ sở hữu lifecycle │ tại NGOÀI     │ bên ngoài module,│
│               │ của resource     │ Terraform     │ không từ infra   │
├───────────────┼──────────────────┼───────────────┼──────────────────┤
│ Ví dụ         │ EC2 instance bạn │ AMI ID của    │ Environment name │
│               │ tạo mới          │ base image    │ ("staging",      │
│               │                  │ do team khác  │ "production")    │
│               │                  │ publish       │                  │
└───────────────┴──────────────────┴───────────────┴──────────────────┘
```

---

### 4. Dependency - Implicit và Explicit

Terraform tự động xây dựng dependency graph để biết thứ tự tạo resources.

**Implicit dependency - tự động từ reference:**

```hcl
resource "docker_image" "nginx" {
  name = "nginx:1.25"
}

resource "docker_container" "web" {
  name  = "my-nginx"
  # Tham chiếu đến docker_image.nginx.image_id
  # Terraform tự hiểu: docker_image.nginx phải tạo TRƯỚC docker_container.web
  image = docker_image.nginx.image_id
  #       ^^^^^^^^^^^^^^^^^^^^^^^^ implicit dependency
}
```

**Explicit dependency - dùng depends_on:**

```hcl
resource "docker_network" "app_network" {
  name = "app-network"
}

resource "docker_container" "database" {
  name  = "postgres-db"
  image = "postgres:15"

  networks_advanced {
    name = docker_network.app_network.name
  }
}

resource "docker_container" "app" {
  name  = "my-app"
  image = "my-app:1.0"

  networks_advanced {
    name = docker_network.app_network.name
  }

  # App cần database healthy TRƯỚC KHI start
  # Nhưng không có attribute reference nào từ app sang database
  # Phải dùng explicit depends_on
  depends_on = [
    docker_container.database  # explicit dependency
  ]
}
```

**Khi nào dùng depends_on:**
- Resource A cần resource B tồn tại, nhưng A không reference bất kỳ attribute nào của B
- Thứ tự tạo quan trọng về mặt logic (database trước app) nhưng không có implicit reference
- External resource phải sẵn sàng trước

---

### 5. Terraform Graph - Visualize Dependency

```bash
# Generate dependency graph dạng DOT format
terraform graph

# Xuất file và visualize (cần graphviz installed)
terraform graph | dot -Tsvg > graph.svg

# Hoặc xem online: copy output vào https://dreampuf.github.io/GraphvizOnline/
```

**Ví dụ dependency graph output (ASCII representation):**

```
Dependency Graph - Docker Infrastructure:

docker_image.nginx ──────────────────┐
                                      ▼
docker_network.app_net ──────► docker_container.web (nginx)
                          │
                          └──► docker_container.db (postgres)
                                      │
                                      │ depends_on
                                      ▼
                              docker_container.app
                                      ▲
docker_image.app ────────────────────┘

Thứ tự execution:
1. docker_image.nginx
2. docker_network.app_net  (song song với step 1)
3. docker_container.web    (sau step 1 và 2)
4. docker_container.db     (sau step 2)
5. docker_container.app    (sau step 3 và 4)
```

Terraform thực thi **song song** những resources không có dependency với nhau. Đó là lý do `terraform apply` nhanh hơn khi structure đúng.

---

## Deep Dive & Trade-offs - 30 phút

### 1. Provider Aliasing - Multi-region và Multi-account

**Pattern thực tế - Multi-region deployment:**

```hcl
# providers.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Primary region - Singapore
provider "aws" {
  region = var.primary_region   # "ap-southeast-1"
}

# DR region - Tokyo
provider "aws" {
  alias  = "dr"
  region = var.dr_region        # "ap-northeast-1"
}

# Primary S3 bucket
resource "aws_s3_bucket" "app_data" {
  # Dùng default provider (Singapore)
  bucket = "${var.app_name}-data-${var.environment}"
}

# DR S3 bucket
resource "aws_s3_bucket" "app_data_dr" {
  provider = aws.dr             # Chỉ định provider alias
  bucket   = "${var.app_name}-data-dr-${var.environment}"
}

# Cross-region replication từ primary sang DR
resource "aws_s3_bucket_replication_configuration" "dr_replication" {
  bucket = aws_s3_bucket.app_data.id
  role   = aws_iam_role.replication.arn

  rule {
    id     = "replicate-to-dr"
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.app_data_dr.arn
      storage_class = "STANDARD_IA"
    }
  }
}
```

**Pattern - Multi-account (Organization):**

```hcl
# Shared Services Account (network hub)
provider "aws" {
  alias  = "network"
  region = "ap-southeast-1"
  assume_role {
    role_arn     = "arn:aws:iam::${var.network_account_id}:role/TerraformCrossAccountRole"
    session_name = "terraform-network-${var.environment}"
  }
}

# Application Account
provider "aws" {
  alias  = "app"
  region = "ap-southeast-1"
  assume_role {
    role_arn     = "arn:aws:iam::${var.app_account_id}:role/TerraformCrossAccountRole"
    session_name = "terraform-app-${var.environment}"
  }
}

# VPC trong Network account
resource "aws_vpc" "main" {
  provider   = aws.network
  cidr_block = "10.0.0.0/16"
}

# EC2 trong App account, attach vào shared VPC
resource "aws_instance" "app_server" {
  provider  = aws.app
  subnet_id = aws_subnet.shared.id  # subnet từ network account
  # ...
}
```

---

### 2. Data Source vs Resource vs Variable - Decision Framework

**Framework ra quyết định:**

```
BẠN MUỐN DÙNG THÔNG TIN VỀ X?
│
├─ X có nằm trong Terraform configuration hiện tại không?
│   ├─ CÓ -> Dùng resource reference trực tiếp (output attribute)
│   └─ KHÔNG
│       │
│       ├─ X được tạo bởi Terraform khác (state khác)?
│       │   └─ Dùng terraform_remote_state data source
│       │
│       ├─ X tồn tại trong cloud/infrastructure nhưng không do Terraform này quản lý?
│       │   └─ Dùng DATA SOURCE (ví dụ: AMI ID, existing VPC, DNS zone)
│       │
│       └─ X là config value (environment name, app name, feature flag)?
│           └─ Dùng VARIABLE

BẠN MUỐN TẠO X?
│
└─ Dùng RESOURCE
```

**Ví dụ quyết định trong thực tế:**

```hcl
# ĐÚNG: AMI do team Platform publish, không do team App quản lý -> Data Source
data "aws_ami" "base_image" {
  most_recent = true
  owners      = ["self"]   # Chỉ lấy AMI của account mình
  filter {
    name   = "name"
    values = ["platform-base-ami-*"]
  }
}

# SAI (anti-pattern): Hard-code AMI ID vào variable
# variable "ami_id" { default = "ami-0123456789abcdef0" }
# Lý do sai: AMI ID thay đổi theo region, theo update cycle,
# developer phải maintain manually

# ĐÚNG: EC2 instance do team này tạo -> Resource
resource "aws_instance" "app" {
  ami           = data.aws_ami.base_image.id  # Lấy từ data source
  instance_type = var.instance_type           # Lấy từ variable
}

# ĐÚNG: Environment name là config, không phải infra -> Variable
variable "environment" {
  type        = string
  description = "Deployment environment: staging, production"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}
```

---

### 3. Dependency Management Strategies

**Strategy 1 - Minimize explicit depends_on:**

`depends_on` là last resort. Nếu bạn thấy mình cần depends_on, hãy hỏi: "Có reference nào tôi có thể dùng không?"

```hcl
# TRÁNH: depends_on khi có thể dùng implicit reference
resource "aws_security_group" "db" { ... }
resource "aws_db_instance" "main" {
  depends_on = [aws_security_group.db]  # Không nên nếu có thể reference attribute
}

# TỐT HƠN: Reference attribute - vừa tạo dependency, vừa dùng giá trị
resource "aws_db_instance" "main" {
  vpc_security_group_ids = [aws_security_group.db.id]  # implicit dependency + value
}
```

**Strategy 2 - Module dependency isolation:**

Trong module lớn, chia resources thành layers với dependency rõ ràng:

```
Layer 0: networking (VPC, subnets, route tables)
    ↓
Layer 1: security (security groups, IAM roles) - depends on Layer 0
    ↓
Layer 2: data (RDS, ElastiCache) - depends on Layer 1
    ↓
Layer 3: compute (EC2, ECS, Lambda) - depends on Layer 2
    ↓
Layer 4: routing (ALB, Route53) - depends on Layer 3
```

---

### 4. Provider Version Pinning Strategy

**Pin version trong team environment:**

```hcl
terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      # ~> 5.30: Cho phép patch updates (5.30.x) nhưng không major
      # Đủ stable, đủ flexible để nhận security patches
      version = "~> 5.30"
    }

    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}
```

**Dùng .terraform.lock.hcl:**

File `.terraform.lock.hcl` được tạo tự động khi `terraform init`. File này lock chính xác version và hash. Commit file này vào git.

```bash
# Upgrade provider version khi muốn
terraform init -upgrade

# Verify lock file được update
cat .terraform.lock.hcl
```

**Lock file giải quyết "works on my machine":** Mọi developer và CI/CD pipeline đều dùng cùng một provider version.

---

### 5. Common Pitfalls

**Pitfall 1 - Circular dependency:**

```hcl
# SAI: Circular dependency - Terraform không thể resolve
resource "aws_security_group" "app" {
  ingress {
    security_groups = [aws_security_group.lb.id]  # app depends on lb
  }
}

resource "aws_security_group" "lb" {
  egress {
    security_groups = [aws_security_group.app.id]  # lb depends on app
  }
}
# Error: Cycle: aws_security_group.app, aws_security_group.lb
```

**Fix circular dependency:**

```hcl
# TỐT: Dùng aws_security_group_rule riêng biệt
resource "aws_security_group" "app" { ... }
resource "aws_security_group" "lb" { ... }

# Rules được tạo sau khi cả 2 SG tồn tại
resource "aws_security_group_rule" "app_from_lb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.lb.id
  from_port = 8080
  to_port   = 8080
  protocol  = "tcp"
}
```

**Pitfall 2 - Stale data source:**

```hcl
# NGUY HIỂM: most_recent = true có thể thay đổi mỗi lần apply
data "aws_ami" "ubuntu" {
  most_recent = true            # <-- Nguy hiểm nếu không control
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-*-22.04-amd64-server-*"]
  }
}

# KẾT QUẢ: Mỗi lần ami-xxx mới được publish, terraform plan sẽ thấy
# "change" và có thể thay thế EC2 instance -> DATA LOSS nếu có stateful data
```

**Fix:**

```hcl
# Option 1: Pin specific AMI ID trong variable sau khi validate
variable "base_ami_id" {
  type        = string
  description = "AMI ID đã được team Platform validate. Update có chủ ý."
  default     = "ami-0abcdef1234567890"  # cụ thể, không dùng most_recent
}

# Option 2: Filter bằng specific version tag
data "aws_ami" "ubuntu" {
  owners = ["099720109477"]
  filter {
    name   = "tag:PlatformVersion"
    values = ["v2024.01"]   # Pin bằng tag, không phải most_recent
  }
}
```

**Pitfall 3 - Provider misconfiguration với alias:**

```hcl
# THIẾU: Module cần provider alias nhưng không được truyền vào
module "dr_setup" {
  source = "./modules/dr"
  # Quên truyền providers map
}

# SAI TRONG MODULE:
# resource "aws_s3_bucket" "dr" {
#   provider = aws.dr  # Lỗi: provider "aws.dr" không được khai báo trong module
# }

# ĐÚNG: Truyền provider vào module
module "dr_setup" {
  source = "./modules/dr"
  providers = {
    aws.dr = aws.dr   # Truyền alias provider vào module
  }
}
```

---

## Hands-on Lab - 60 phút

### Lab Setup

Lab này dùng **Docker provider** - không cần cloud account, không tốn tiền.

**Yêu cầu:**
- Docker Desktop đang chạy
- Terraform >= 1.5.0 installed
- (Optional) Graphviz để visualize dependency graph: `apt install graphviz` hoặc `brew install graphviz`

**Mục tiêu lab:**
1. Tạo Docker network, volumes, containers có dependency thật sự
2. Dùng data source để reference existing Docker image
3. Visualize dependency graph
4. Thực hành provider version pinning

---

### Bước 1 - Khởi tạo project structure

```bash
mkdir -p ~/terraform-day3-lab && cd ~/terraform-day3-lab
```

Tạo file structure:
```
terraform-day3-lab/
├── main.tf
├── providers.tf
├── variables.tf
├── outputs.tf
└── data.tf
```

---

### Bước 2 - providers.tf

```hcl
# providers.tf
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  # Linux/Mac
  host = "unix:///var/run/docker.sock"

  # Windows Docker Desktop (uncomment nếu dùng Windows)
  # host = "npipe:////./pipe/docker_engine"
}
```

---

### Bước 3 - variables.tf

```hcl
# variables.tf
variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod"
  }
}

variable "app_name" {
  type        = string
  description = "Application name, used as prefix"
  default     = "myapp"
}

variable "nginx_port" {
  type        = number
  description = "Port to expose nginx on localhost"
  default     = 8080
}

variable "postgres_password" {
  type        = string
  description = "PostgreSQL root password"
  sensitive   = true
  default     = "dev_password_change_in_production"
}
```

---

### Bước 4 - data.tf

```hcl
# data.tf
# Data source: đọc thông tin image từ Docker registry
# Không tạo image, chỉ reference để lấy image_id
data "docker_image" "nginx" {
  name = "nginx:1.25-alpine"
}

data "docker_image" "postgres" {
  name = "postgres:15-alpine"
}
```

**Lưu ý:** Data source `docker_image` yêu cầu image phải tồn tại local (đã pull). Pull trước:

```bash
docker pull nginx:1.25-alpine
docker pull postgres:15-alpine
```

---

### Bước 5 - main.tf

```hcl
# main.tf

# ─── Network Layer ──────────────────────────────────────────────────────────

# Docker network cho toàn bộ stack
resource "docker_network" "app_network" {
  name = "${var.app_name}-${var.environment}-network"

  driver = "bridge"

  # Internal: containers có thể giao tiếp với nhau qua tên container
  ipam_config {
    subnet  = "172.28.0.0/16"
    gateway = "172.28.0.1"
  }
}

# ─── Storage Layer ──────────────────────────────────────────────────────────

# Persistent volume cho PostgreSQL data
resource "docker_volume" "postgres_data" {
  name = "${var.app_name}-${var.environment}-postgres-data"

  labels {
    label = "app"
    value = var.app_name
  }

  labels {
    label = "environment"
    value = var.environment
  }
}

# ─── Database Layer ─────────────────────────────────────────────────────────

# PostgreSQL container - phải tạo trước app container
resource "docker_container" "postgres" {
  name  = "${var.app_name}-${var.environment}-postgres"
  image = data.docker_image.postgres.image_id  # implicit dependency trên data source

  # Restart policy
  restart = "unless-stopped"

  # Environment variables
  env = [
    "POSTGRES_DB=${var.app_name}",
    "POSTGRES_USER=appuser",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "PGDATA=/var/lib/postgresql/data/pgdata",
  ]

  # Mount persistent volume
  mounts {
    type   = "volume"
    target = "/var/lib/postgresql/data"
    source = docker_volume.postgres_data.name  # implicit dependency
  }

  # Attach vào network - implicit dependency trên docker_network.app_network
  networks_advanced {
    name    = docker_network.app_network.name
    aliases = ["postgres", "db"]  # Container có thể được resolve bằng tên này
  }

  # Health check
  healthcheck {
    test         = ["CMD-SHELL", "pg_isready -U appuser -d ${var.app_name}"]
    interval     = "10s"
    timeout      = "5s"
    start_period = "30s"
    retries      = 5
  }

  labels {
    label = "traefik.enable"
    value = "false"
  }
}

# ─── Web Layer ──────────────────────────────────────────────────────────────

# Nginx config được tạo dưới dạng docker config
resource "docker_config" "nginx_conf" {
  name = "${var.app_name}-${var.environment}-nginx-conf"

  data = base64encode(templatefile("${path.module}/nginx.conf.tpl", {
    app_name = var.app_name
  }))
}

# Nginx container - web server
resource "docker_container" "nginx" {
  name  = "${var.app_name}-${var.environment}-nginx"
  image = data.docker_image.nginx.image_id  # implicit dependency trên data source

  restart = "unless-stopped"

  # Port mapping
  ports {
    internal = 80
    external = var.nginx_port
    protocol = "tcp"
  }

  # Attach vào cùng network
  networks_advanced {
    name    = docker_network.app_network.name
    aliases = ["nginx", "web"]
  }

  # Nginx phải start SAU database - không có attribute reference trực tiếp
  # nên cần explicit depends_on
  depends_on = [
    docker_container.postgres
  ]

  labels {
    label = "app"
    value = var.app_name
  }

  labels {
    label = "environment"
    value = var.environment
  }

  lifecycle {
    # Ignore thay đổi labels từ bên ngoài (Docker daemon có thể add labels)
    ignore_changes = [labels]
  }
}
```

Tạo nginx config template:

```bash
cat > ~/terraform-day3-lab/nginx.conf.tpl << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream app_backend {
        # Trong thực tế, sẽ point vào app containers
        server postgres:5432;  # Demo: postgres accessible by hostname
    }

    server {
        listen 80;
        server_name localhost;

        location /health {
            return 200 '{"status":"ok","app":"${app_name}"}';
            add_header Content-Type application/json;
        }

        location / {
            return 200 '<html><body><h1>${app_name} is running</h1></body></html>';
            add_header Content-Type text/html;
        }
    }
}
EOF
```

---

### Bước 6 - outputs.tf

```hcl
# outputs.tf
output "network_id" {
  description = "Docker network ID"
  value       = docker_network.app_network.id
}

output "postgres_container_id" {
  description = "PostgreSQL container ID"
  value       = docker_container.postgres.id
}

output "nginx_container_id" {
  description = "Nginx container ID"
  value       = docker_container.nginx.id
}

output "nginx_url" {
  description = "URL để access nginx"
  value       = "http://localhost:${var.nginx_port}"
}

output "postgres_volume_name" {
  description = "PostgreSQL persistent volume name"
  value       = docker_volume.postgres_data.name
}

output "nginx_image_id" {
  description = "Image ID được dùng bởi nginx container"
  value       = data.docker_image.nginx.image_id
}
```

---

### Bước 7 - Khởi tạo và plan

```bash
cd ~/terraform-day3-lab

# Init - download docker provider
terraform init
```

**Expected output:**
```
Initializing the backend...
Initializing provider plugins...
- Finding kreuzwerker/docker versions matching "~> 3.0"...
- Installing kreuzwerker/docker v3.0.2...
- Installed kreuzwerker/docker v3.0.2 (self-signed, key ID ...)

Terraform has been successfully initialized!
```

```bash
# Xem plan
terraform plan
```

**Expected output (phần quan trọng):**
```
  # docker_container.nginx will be created
  # docker_container.postgres will be created
  # docker_network.app_network will be created
  # docker_volume.postgres_data will be created
  # data.docker_image.nginx will be read during apply

Plan: 4 to add, 0 to change, 0 to destroy.
```

---

### Bước 8 - Apply và verify

```bash
terraform apply -auto-approve
```

**Expected output:**
```
docker_network.app_network: Creating...
docker_volume.postgres_data: Creating...
docker_network.app_network: Creation complete after 0s [id=abc123...]
docker_volume.postgres_data: Creation complete after 0s [id=myapp-dev-postgres-data]
docker_container.postgres: Creating...
docker_container.postgres: Creation complete after 2s [id=def456...]
docker_container.nginx: Creating...
docker_container.nginx: Creation complete after 1s [id=ghi789...]

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:
nginx_url = "http://localhost:8080"
```

Verify:
```bash
# Kiểm tra containers đang chạy
docker ps | grep myapp

# Test nginx
curl http://localhost:8080/health

# Kiểm tra network
docker network inspect myapp-dev-network
```

---

### Bước 9 - Phân tích Dependency Graph

```bash
# Generate graph
terraform graph

# Nếu có graphviz installed:
terraform graph | dot -Tsvg > dependency-graph.svg
# Mở file svg trong browser

# Nếu không có graphviz, copy output vào:
# https://dreampuf.github.io/GraphvizOnline/
```

**Đọc graph output:**
```
Tìm các edges như:
"docker_container.nginx" -> "docker_container.postgres"  (depends_on)
"docker_container.postgres" -> "docker_volume.postgres_data"  (implicit)
"docker_container.postgres" -> "docker_network.app_network"    (implicit)
"docker_container.nginx" -> "docker_network.app_network"       (implicit)
```

---

### Bước 10 - Test thay đổi và dependency

Thay đổi nginx port:

```bash
# Plan với giá trị khác
terraform plan -var="nginx_port=9090"
```

**Expected output:**
```
  # docker_container.nginx must be replaced
-/+ resource "docker_container" "nginx" {
      ~ ports {
          ~ external = 8080 -> 9090   # forces replacement
        }
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

Lưu ý: Thay đổi port của Docker container forces replacement (destroy + create mới).

---

### Bước 11 - Cleanup

```bash
terraform destroy -auto-approve
```

**Expected output:**
```
docker_container.nginx: Destroying...
docker_container.nginx: Destruction complete after 1s
docker_container.postgres: Destroying...
docker_container.postgres: Destruction complete after 1s
docker_volume.postgres_data: Destroying...
docker_volume.postgres_data: Destruction complete after 0s
docker_network.app_network: Destroying...
docker_network.app_network: Destruction complete after 0s

Destroy complete! Resources: 4 destroyed.
```

Chú ý thứ tự destroy: **ngược lại** với thứ tự tạo. nginx trước postgres, postgres trước network và volume.

---

### Troubleshooting

**Error: Docker daemon not reachable**
```
Error: Error pinging Docker server: ...
```
Fix: Đảm bảo Docker Desktop đang chạy. Check host trong provider config phù hợp với OS.

**Error: Image not found (data source)**
```
Error: Unable to find image with tag: nginx:1.25-alpine
```
Fix:
```bash
docker pull nginx:1.25-alpine
docker pull postgres:15-alpine
```

**Error: Port already in use**
```
Error binding port 8080: address already in use
```
Fix:
```bash
# Tìm process đang dùng port
lsof -i :8080   # Linux/Mac
netstat -ano | findstr 8080   # Windows

# Hoặc dùng port khác
terraform plan -var="nginx_port=9090"
```

**Error: Circular dependency**
```
Error: Cycle: docker_container.nginx, docker_container.postgres
```
Fix: Kiểm tra lại depends_on và resource references. Đảm bảo không có A depends B và B depends A.

---

## Kiểm tra hiểu bài

1. **Provider aliasing:** Bạn có project Terraform cần tạo S3 bucket ở 3 regions: ap-southeast-1, us-east-1, eu-west-1. Provider block nên được viết như thế nào? Làm sao để resource biết dùng provider alias nào?

2. **Data source vs resource:** Team bạn có một VPC được tạo thủ công (click-ops) từ 2 năm trước. Team muốn dùng Terraform để tạo EC2 trong VPC đó. Bạn có nên import VPC vào Terraform state không? Hay dùng data source? Trade-off là gì?

3. **Dependency graph:** Cho 4 resources: `aws_vpc`, `aws_subnet`, `aws_security_group`, `aws_instance`. Instance cần security group và subnet. Security group cần VPC. Subnet cần VPC. Vẽ dependency graph. Terraform sẽ tạo resources theo thứ tự nào? Resources nào có thể tạo song song?

4. **Stale data source:** Trong production, bạn có data source `data "aws_ami" "base" { most_recent = true ... }` được reference bởi Auto Scaling Group launch template. Khi team Platform publish AMI mới, điều gì sẽ xảy ra khi `terraform apply` được chạy? Đây có phải là behavior bạn muốn không? Nếu không, fix như thế nào?

5. **Version pinning:** Developer mới join team chạy `terraform init` và nhận được provider version khác với những người khác. Điều gì đã xảy ra? Làm sao để prevent? File nào cần commit vào git?

---

## Tóm tắt cuối ngày

### Key Points

| Concept | Điểm cần nhớ |
|---------|-------------|
| Provider | Plugin bridge giữa Terraform và API. Pin version bằng `~>`. Dùng alias cho multi-region/account |
| Resource | Terraform sở hữu lifecycle. Thay đổi attribute có thể trigger update hoặc replace |
| Data Source | Chỉ đọc, không quản lý. Fetch mỗi plan/apply. Cẩn thận với `most_recent` |
| Implicit dep | Tự động từ attribute reference. Ưu tiên dùng |
| Explicit dep | `depends_on` - dùng khi không có attribute reference nhưng cần ordering |
| Graph | `terraform graph` để debug/visualize. Circular dep là bug thật sự |
| Lock file | `.terraform.lock.hcl` commit vào git. Giải quyết "works on my machine" |

### Outputs của Day 3

Bạn đã tạo:
- `~/terraform-day3-lab/` - Project thực hành với Docker provider
- Hiểu dependency graph thực tế
- Kinh nghiệm với data source và resource lifecycle

### Chuẩn bị cho Day 4 - Terraform State Fundamentals

Day 4 sẽ đào sâu vào state - trái tim của Terraform:
- State file structure và format
- State locking và concurrency
- `terraform state` commands (list, show, mv, rm)
- State drift detection
- Sensitive data trong state

Câu hỏi chuẩn bị: Sau khi destroy lab hôm nay, file gì còn lại trong thư mục? Đọc file `terraform.tfstate` và tìm hiểu format của nó.

---

## Tham khảo thêm

- [Terraform Provider Registry](https://registry.terraform.io/browse/providers) - Tìm providers
- [kreuzwerker/docker Provider Docs](https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs) - Docker provider reference
- [Terraform Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock) - Lock file documentation
- [Resource Lifecycle Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) - lifecycle block chi tiết
- [depends_on Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/depends_on) - Khi nào dùng explicit dep
- [GraphvizOnline](https://dreampuf.github.io/GraphvizOnline/) - Visualize terraform graph output online
