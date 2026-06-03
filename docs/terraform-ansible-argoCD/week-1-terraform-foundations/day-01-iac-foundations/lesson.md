# Day 1 - IaC Foundations & Terraform Mental Model

> **Thời gian:** 2 giờ (30 phút lý thuyết + 30 phút deep dive + 60 phút lab)
> **Ngày:** Week 1, Day 1

---

## 1. Mục tiêu ngày học

Sau ngày này, bạn có thể:

- Giải thích **tại sao** IaC ra đời và vấn đề thực tế nó giải quyết
- Phân biệt declarative vs imperative và chọn đúng tool cho đúng context
- Mô tả Terraform workflow (init → plan → apply → destroy) và ý nghĩa từng bước
- Giải thích các core concepts: provider, resource, data source, state, dependency graph
- Cài đặt Terraform và chạy được lab với local/Docker provider, quan sát state file

---

## 2. Bối cảnh thực tế

### Vấn đề bắt đầu từ đây

Bạn là senior dev tại một startup. Team vừa nhận funding Series A. CTO nói: "Tuần tới chúng ta cần 3 môi trường riêng biệt: dev, staging, production. Mỗi môi trường cần RDS PostgreSQL, ElastiCache Redis, EKS cluster, ALB, VPC với public/private subnets, security groups."

Không có IaC. Bạn có 3 lựa chọn:

**Option 1: Click tay trên AWS Console**
- Dev mất 2 ngày click. Staging mất thêm 1 ngày vì nhớ nhầm config. Production thì... ai dám bảo đảm giống staging?
- 3 tháng sau: "cần thêm môi trường cho client demo". Mất 2 ngày nữa.
- 6 tháng sau: "con RDS production config khác con staging ở chỗ nào?" — không ai biết.

**Option 2: Bash script**
```bash
aws ec2 create-vpc --cidr-block 10.0.0.0/16
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24
# ... 500 dòng script
```
- Script create thì được. Nhưng update thì sao? Delete thì sao?
- `aws ec2 create-vpc` không idempotent — chạy lại sẽ tạo thêm một VPC nữa.

**Option 3: Terraform**
```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = { Name = "production-vpc" }
}
```
- Chạy `terraform apply` — VPC được tạo.
- Chạy lại `terraform apply` — không làm gì (idempotent, đã có rồi).
- Sửa `cidr_block` rồi `terraform apply` — Terraform báo sẽ destroy và recreate (hay modify nếu supported).
- `terraform destroy` — xóa sạch, không để lại orphan resources.

### Microservices context

Trong hệ thống microservices thực tế, một service deploy lên production cần:
- Kubernetes namespace + RBAC
- Service account với IAM role (IRSA trên EKS)
- RDS instance hoặc database trong shared cluster
- S3 bucket cho assets
- ElastiCache cho session/cache
- CloudWatch log groups
- Security groups với least-privilege rules

Nhân 10 services, nhân 3 environments = 30 lần cấu hình. Không có IaC thì đây là thảm họa vận hành.

---

## 3. Kiến thức nền tảng — 30 phút

### 3.1 Tại sao cần IaC?

IaC giải quyết 4 vấn đề cốt lõi:

| Vấn đề | Không có IaC | Có IaC |
|--------|-------------|--------|
| **Reproducibility** | "Môi trường dev của tôi khác production" | Apply cùng code → cùng infrastructure |
| **Drift detection** | Không biết ai đã sửa gì trên console | `terraform plan` phát hiện ngay drift |
| **Collaboration** | Infrastructure là "tribal knowledge" | Infra là code → review, PR, audit trail |
| **Speed** | Tạo môi trường mới mất 2-3 ngày | Tạo môi trường mới: `terraform workspace new staging && terraform apply` |

Bạn đã làm việc với Git, Docker, Kubernetes — những thứ này cũng là "as code" về bản chất. IaC là cùng philosophy đó áp dụng cho infrastructure layer.

### 3.2 Declarative vs Imperative

Đây là sự phân biệt quan trọng nhất khi học Terraform.

**Imperative** — "Làm từng bước này":
```bash
# Bash script
if ! vpc_exists; then
  create_vpc
fi
if ! subnet_exists; then
  create_subnet
fi
```
Bạn phải tự quản lý state, tự xử lý idempotency, tự biết thứ tự.

**Declarative** — "Tôi muốn trạng thái cuối cùng là thế này":
```hcl
# Terraform
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}
```
Bạn mô tả **desired state**. Terraform tự tính toán delta giữa current state và desired state, rồi thực hiện các actions cần thiết.

```
Desired State (code) ──► Terraform ──► Actions
                                          │
Current State (state) ─────────────────►─┘
```

Kubernetes cũng declarative — bạn apply Deployment YAML, K8s controller loop lo phần còn lại. Terraform hoạt động theo cùng philosophy này cho infrastructure.

### 3.3 Terraform Workflow

```
┌─────────────────────────────────────────────────────────┐
│                   Terraform Workflow                      │
│                                                           │
│  .tf files                                                │
│  (code)                                                   │
│     │                                                     │
│     ▼                                                     │
│  terraform init                                           │
│  ├── Download providers (~/.terraform/providers/)         │
│  ├── Initialize backend (where state is stored)           │
│  └── Create .terraform.lock.hcl                           │
│     │                                                     │
│     ▼                                                     │
│  terraform plan                                           │
│  ├── Read current state                                   │
│  ├── Call provider APIs to refresh actual state           │
│  ├── Compare: desired (code) vs actual (state)            │
│  └── Output: execution plan (+ create, ~ modify, - destroy)│
│     │                                                     │
│     ▼                                                     │
│  terraform apply                                          │
│  ├── Show plan again                                      │
│  ├── Ask for confirmation (yes/no)                        │
│  ├── Execute API calls                                    │
│  └── Update state file                                    │
│     │                                                     │
│     ▼                                                     │
│  terraform destroy (khi cần)                              │
│  ├── Tạo plan để xóa toàn bộ resources                   │
│  └── Thực thi xóa theo đúng thứ tự dependency            │
└─────────────────────────────────────────────────────────┘
```

**Các lệnh quan trọng khác:**
- `terraform fmt` — format code theo standard style
- `terraform validate` — validate syntax và config
- `terraform show` — hiện current state (human-readable)
- `terraform output` — hiện output values
- `terraform state list` — list tất cả resources trong state
- `terraform import` — import existing resource vào state

### 3.4 Core Concepts

#### Provider

Provider là plugin kết nối Terraform với một API cụ thể. Provider define các resource types và data sources có thể dùng.

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"           # >= 5.0.0, < 6.0.0
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"        # Singapore
}
```

Providers có ở [Terraform Registry](https://registry.terraform.io/browse/providers). Có hàng ngàn providers: AWS, GCP, Azure, Kubernetes, GitHub, Datadog, Cloudflare...

#### Resource

Resource là object infrastructure bạn muốn manage. Syntax luôn là:
```hcl
resource "<provider>_<type>" "<local_name>" {
  argument = value
}
```

```hcl
resource "aws_s3_bucket" "uploads" {     # local name: "uploads"
  bucket = "my-app-uploads-prod-2024"
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id      # reference: <type>.<name>.<attribute>
  versioning_configuration {
    status = "Enabled"
  }
}
```

#### Data Source

Data source là read-only query — lấy thông tin về resource đã tồn tại (không manage bởi Terraform này).

```hcl
# Lấy thông tin AMI mới nhất của Amazon Linux 2
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# Dùng trong resource
resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id   # reference data source
  instance_type = "t3.micro"
}
```

Data source vs Resource:
- `resource` → Terraform tạo và manage
- `data` → Terraform chỉ đọc, không tạo, không xóa

#### State

State là **trái tim** của Terraform. Đây là file JSON lưu mapping giữa Terraform resources và real-world objects.

```
terraform.tfstate
{
  "resources": [
    {
      "type": "aws_s3_bucket",
      "name": "uploads",
      "instances": [{
        "attributes": {
          "id": "my-app-uploads-prod-2024",
          "arn": "arn:aws:s3:::my-app-uploads-prod-2024",
          ...
        }
      }]
    }
  ]
}
```

Tại sao state quan trọng:
- Terraform biết resource nào đang tồn tại (để không tạo lại)
- Terraform biết attribute của resource đã tạo (để dùng trong outputs và references)
- Terraform track dependencies giữa resources
- `terraform plan` so sánh desired state (code) với current state (state file) và actual state (API query)

**Cảnh báo:** State file chứa sensitive data (passwords, private keys). Không commit state file vào Git. Production dùng remote backend (S3 + DynamoDB, Terraform Cloud, etc).

#### Dependency Graph

Terraform tự động xây dựng dependency graph dựa trên references giữa resources.

```hcl
resource "aws_vpc" "main" { ... }                        # Node A

resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id                              # A → B dependency
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id                              # A → C dependency
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id                              # A → D dependency
  route {
    gateway_id = aws_internet_gateway.igw.id            # C → D dependency
  }
}
```

```
     aws_vpc.main (A)
      /          \
     /            \
aws_subnet.public  aws_internet_gateway.igw
     (B)                    (C)
                             |
                    aws_route_table.public
                             (D)
```

Terraform dùng graph này để:
- Tạo resources theo đúng thứ tự (A trước, rồi B và C song song, rồi D)
- Xóa resources theo thứ tự ngược lại
- Parallelize những gì không phụ thuộc nhau

### 3.5 So sánh Terraform với các alternatives

| | Terraform | Bash/AWS CLI | Ansible | Pulumi | CloudFormation |
|---|---|---|---|---|---|
| **Approach** | Declarative | Imperative | Mostly imperative (for infra) | Declarative (code) | Declarative |
| **Language** | HCL | Bash | YAML | Python/TS/Go/C# | JSON/YAML |
| **State mgmt** | Built-in | Tự làm | Không có | Built-in | AWS-managed |
| **Multi-cloud** | Yes | Yes (manual) | Partial | Yes | No (AWS only) |
| **Ecosystem** | Rất lớn | N/A | Lớn | Nhỏ hơn | AWS-only |
| **Learning curve** | Medium | Low | Low-Medium | Medium-High | Medium |
| **OOP/abstraction** | Modules, no OOP | Functions | Roles | Full OOP | Stacks, nested |
| **Best for** | Infrastructure provisioning | Ad-hoc tasks, CI scripts | Config management, app deployment | Devs prefer real code | AWS-heavy shops |

**Khi nào dùng cái gì:**
- **Terraform**: Provision và lifecycle manage cloud infrastructure (VPC, RDS, EKS, IAM...)
- **Ansible**: Configure servers sau khi provision (install packages, configure services) — Day 8-14
- **Bash/CLI**: Ad-hoc tasks, quick fixes, CI/CD glue code
- **Pulumi**: Team Python/TypeScript mạnh, muốn unit test infra code thực sự
- **CloudFormation**: AWS-only shop, muốn zero external dependencies

**Terraform không thay thế Ansible** — chúng làm việc ở các layer khác nhau và thường dùng cùng nhau.

---

## 4. Deep Dive & Trade-offs — 30 phút

### 4.1 State Management: Local vs Remote

Câu hỏi đầu tiên khi dùng Terraform production là: **state file lưu ở đâu?**

**Local state (default)**
```hcl
# Không cần config gì — terraform.tfstate nằm trong thư mục hiện tại
```

Ưu điểm: Zero setup, phù hợp học.
Nhược điểm: Không share được với team, risk mất file, không lock (2 người apply cùng lúc = corruption).

**Remote state — S3 + DynamoDB (AWS)**
```hcl
terraform {
  backend "s3" {
    bucket         = "my-company-terraform-state"
    key            = "production/vpc/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"   # Distributed lock
  }
}
```

Ưu điểm: Team share được, encrypted at rest, locking ngăn concurrent apply, versioned (S3 versioning).
Nhược điểm: Cần setup S3 bucket và DynamoDB table trước (chicken-and-egg problem — thường bootstrap bằng local state rồi migrate).

**Terraform Cloud / HCP Terraform**
```hcl
terraform {
  cloud {
    organization = "my-company"
    workspaces {
      name = "production"
    }
  }
}
```

Ưu điểm: Managed, remote execution, UI, RBAC, secrets management, audit logs.
Nhược điểm: Cost, vendor lock-in với HashiCorp.

**Khuyến nghị theo context:**

| Context | State backend |
|---------|--------------|
| Học / cá nhân | Local |
| Team nhỏ (<5 người), AWS | S3 + DynamoDB |
| Startup tăng trưởng nhanh | Terraform Cloud (free tier đủ dùng) |
| Enterprise | Terraform Enterprise hoặc self-hosted Atlantis + S3 |
| Bank/regulated | On-prem Terraform Enterprise với audit logging |

### 4.2 Terraform State: Common Pitfalls

**Pitfall 1: Commit state file vào Git**

State chứa plaintext passwords, private keys. Một git push có thể expose toàn bộ infra secrets.

```bash
# .gitignore bắt buộc phải có
*.tfstate
*.tfstate.backup
.terraform/
.terraform.lock.hcl  # Nên commit cái này — nó lock provider versions
```

**Pitfall 2: Apply trực tiếp không qua plan review**

```bash
# Nguy hiểm trong production
terraform apply

# Tốt hơn: save plan, review, apply plan đó
terraform plan -out=tfplan
# Review tfplan
terraform apply tfplan    # Thực thi chính xác plan đã review
```

**Pitfall 3: State drift — ai đó sửa tay trên console**

```bash
terraform plan    # Sẽ detect drift và propose để revert changes
```

Quyết định:
- Nếu change hợp lệ: update code để match reality
- Nếu change không hợp lệ: `terraform apply` để revert về desired state

**Pitfall 4: Xóa resource khỏi code = destroy resource đó**

```hcl
# Nếu bạn xóa block này khỏi code
resource "aws_s3_bucket" "uploads" { ... }
# terraform apply sẽ DESTROY bucket này (và mọi dữ liệu trong đó)
```

Dùng `lifecycle` block để bảo vệ:
```hcl
resource "aws_s3_bucket" "uploads" {
  bucket = "my-app-uploads-prod"

  lifecycle {
    prevent_destroy = true    # Terraform error thay vì destroy
  }
}
```

### 4.3 Workspaces vs Separate Directories

Terraform workspaces cho phép dùng cùng code với multiple state files.

```bash
terraform workspace new staging
terraform workspace select staging
terraform apply    # State lưu ở terraform.tfstate.d/staging/
```

Nhưng có trade-offs:

| | Workspaces | Separate directories |
|---|---|---|
| **Code duplication** | Không | Có (hoặc dùng modules) |
| **Isolation** | Chỉ state — cùng backend | Hoàn toàn isolate |
| **Risk** | Nhầm workspace = apply vào production | Phải cd đúng thư mục |
| **Common use** | Environments nhỏ, ít khác biệt | Environments với infra khác nhau |
| **Best practice** | Không dùng cho prod/non-prod isolation | Dùng cho prod/non-prod |

HashiCorp khuyên: **đừng dùng workspaces để phân biệt production và non-production**. Dùng separate directories với shared modules thay vào đó.

---

## 5. Hands-on Lab — 60 phút

### Lab: Terraform với Docker Provider

Tại sao Docker provider?
- Không cần cloud account
- Instant feedback (local)
- Minh họa đầy đủ Terraform concepts
- Docker bạn đã biết — focus được vào Terraform, không bị distract bởi AWS concepts

**Prerequisites:**
- Docker Desktop đang chạy
- Terraform chưa cài (sẽ cài trong lab này)

---

### Bước 1: Cài Terraform

**macOS (Homebrew):**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
terraform version
# Terraform v1.9.x
```

**Ubuntu/Debian:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
terraform version
```

**Windows (Chocolatey):**
```powershell
choco install terraform
terraform version
```

**Verify:**
```bash
terraform version
# Expected: Terraform v1.9.x (hoặc cao hơn)
```

---

### Bước 2: Setup project structure

```bash
mkdir -p ~/terraform-labs/day-01
cd ~/terraform-labs/day-01
```

```
day-01/
├── main.tf          # Resources chính
├── variables.tf     # Input variables
├── outputs.tf       # Output values
└── terraform.tfvars # Variable values (không commit nếu chứa secrets)
```

---

### Bước 3: Viết Terraform configuration

**`main.tf`**
```hcl
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
  # Trên macOS/Linux: mặc định kết nối unix:///var/run/docker.sock
  # Trên Windows Docker Desktop: host = "npipe:////.//pipe//docker_engine"
}

# Pull image từ Docker Hub
resource "docker_image" "nginx" {
  name         = "nginx:${var.nginx_version}"
  keep_locally = false    # Xóa image khi terraform destroy
}

# Tạo Docker network
resource "docker_network" "lab_network" {
  name   = "${var.app_name}-network"
  driver = "bridge"
}

# Tạo container
resource "docker_container" "web" {
  name  = "${var.app_name}-web"
  image = docker_image.nginx.image_id

  # Map port: host:container
  ports {
    internal = 80
    external = var.host_port
  }

  networks_advanced {
    name = docker_network.lab_network.name
  }

  # Environment variables
  env = [
    "NGINX_HOST=${var.app_name}.local",
    "NGINX_PORT=80"
  ]

  # Restart policy
  restart = "unless-stopped"

  labels {
    label = "managed-by"
    value = "terraform"
  }

  labels {
    label = "environment"
    value = var.environment
  }
}
```

**`variables.tf`**
```hcl
variable "app_name" {
  description = "Tên ứng dụng, dùng để đặt tên resources"
  type        = string
  default     = "myapp"
}

variable "environment" {
  description = "Môi trường deploy: dev, staging, production"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment phải là: dev, staging, hoặc production."
  }
}

variable "nginx_version" {
  description = "Nginx Docker image tag"
  type        = string
  default     = "1.25-alpine"
}

variable "host_port" {
  description = "Port trên host machine để access nginx"
  type        = number
  default     = 8080
}
```

**`outputs.tf`**
```hcl
output "container_name" {
  description = "Tên của Docker container đã tạo"
  value       = docker_container.web.name
}

output "container_id" {
  description = "ID của Docker container"
  value       = docker_container.web.id
}

output "access_url" {
  description = "URL để access nginx"
  value       = "http://localhost:${var.host_port}"
}

output "network_name" {
  description = "Tên Docker network đã tạo"
  value       = docker_network.lab_network.name
}
```

**`terraform.tfvars`**
```hcl
app_name      = "terraform-lab"
environment   = "dev"
nginx_version = "1.25-alpine"
host_port     = 8080
```

---

### Bước 4: terraform init

```bash
cd ~/terraform-labs/day-01
terraform init
```

**Expected output:**
```
Initializing the backend...
Initializing provider plugins...
- Finding kreuzwerker/docker versions matching "~> 3.0"...
- Installing kreuzwerker/docker v3.0.2...
- Installed kreuzwerker/docker v3.0.2 (self-signed, key ID ...)

Terraform has created a lock file .terraform.lock.hcl to record the
provider selections made above.

Terraform has been successfully initialized!
```

**Sau init, kiểm tra:**
```bash
ls -la
# .terraform/          <- provider binaries download về đây
# .terraform.lock.hcl  <- lock file, nên commit vào Git
# main.tf
# variables.tf
# outputs.tf
# terraform.tfvars

ls .terraform/providers/
# registry.terraform.io/kreuzwerker/docker/3.0.2/...
```

---

### Bước 5: terraform validate và fmt

```bash
terraform validate
# Success! The configuration is valid.

terraform fmt
# Nếu có file nào được format lại, tên file sẽ hiện ra
# Nếu không có gì thay đổi: không output
```

---

### Bước 6: terraform plan

```bash
terraform plan
```

**Expected output:**
```
Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # docker_container.web will be created
  + resource "docker_container" "web" {
      + env         = [
          + "NGINX_HOST=terraform-lab.local",
          + "NGINX_PORT=80",
        ]
      + id          = (known after apply)
      + image       = (known after apply)
      + name        = "terraform-lab-web"
      + restart     = "unless-stopped"
      ...
    }

  # docker_image.nginx will be created
  + resource "docker_image" "nginx" {
      + id           = (known after apply)
      + image_id     = (known after apply)
      + name         = "nginx:1.25-alpine"
      ...
    }

  # docker_network.lab_network will be created
  + resource "docker_network" "lab_network" {
      + driver = "bridge"
      + id     = (known after apply)
      + name   = "terraform-lab-network"
      ...
    }

Plan: 3 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + access_url     = "http://localhost:8080"
  + container_id   = (known after apply)
  + container_name = "terraform-lab-web"
  + network_name   = "terraform-lab-network"
```

Lưu ý `(known after apply)` — những giá trị này chỉ có sau khi tạo resource (như ID).

---

### Bước 7: terraform apply

```bash
terraform apply
```
Terraform hiện lại plan và hỏi:
```
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes
```

Gõ `yes` và Enter.

**Expected output:**
```
docker_network.lab_network: Creating...
docker_image.nginx: Pulling from registry...
docker_network.lab_network: Creation complete after 0s [id=abc123...]
docker_image.nginx: Still pulling... 10s elapsed
docker_image.nginx: Creation complete after 15s [id=sha256:...]
docker_container.web: Creating...
docker_container.web: Creation complete after 1s [id=def456...]

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.

Outputs:

access_url     = "http://localhost:8080"
container_id   = "def456..."
container_name = "terraform-lab-web"
network_name   = "terraform-lab-network"
```

**Verify:**
```bash
# Kiểm tra container đang chạy
docker ps | grep terraform-lab
# CONTAINER ID  IMAGE              COMMAND    ...  PORTS                 NAMES
# def456...     nginx:1.25-alpine  ...        ...  0.0.0.0:8080->80/tcp  terraform-lab-web

# Test nginx
curl http://localhost:8080
# <!DOCTYPE html>...Welcome to nginx!...

# Kiểm tra network
docker network ls | grep terraform-lab
# abc123...  terraform-lab-network  bridge  local
```

---

### Bước 8: Quan sát State File

```bash
cat terraform.tfstate
```

Đây là JSON file. Chú ý các fields:
```json
{
  "version": 4,
  "terraform_version": "1.9.x",
  "resources": [
    {
      "mode": "managed",
      "type": "docker_container",
      "name": "web",
      "provider": "provider[\"registry.terraform.io/kreuzwerker/docker\"]",
      "instances": [
        {
          "schema_version": 2,
          "attributes": {
            "id": "def456...",
            "image": "sha256:...",
            "name": "terraform-lab-web",
            "ports": [{"external": 8080, "internal": 80, ...}],
            ...
          }
        }
      ]
    }
  ]
}
```

```bash
# List resources trong state
terraform state list
# docker_container.web
# docker_image.nginx
# docker_network.lab_network

# Xem chi tiết một resource
terraform state show docker_container.web
```

---

### Bước 9: Thay đổi và observe plan

Sửa `terraform.tfvars` — đổi port:
```hcl
host_port = 9090    # Đổi từ 8080 thành 9090
```

```bash
terraform plan
```

**Expected output:**
```
  # docker_container.web must be replaced
-/+ resource "docker_container" "web" {
      ~ id   = "def456..." -> (known after apply)
        name = "terraform-lab-web"
      ~ ports {
          ~ external = 8080 -> 9090           # Dòng này thay đổi
            internal = 80
            ...
        }
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

Terraform thấy ports thay đổi → phải destroy container cũ và create mới (Docker không cho phép update port live). Đây là **replace/recreate**.

Không apply bây giờ — revert lại:
```hcl
host_port = 8080    # Revert
```

---

### Bước 10: terraform destroy

```bash
terraform destroy
```

Terraform hiện plan destroy:
```
  # docker_container.web will be destroyed
  - resource "docker_container" "web" { ... }
  # docker_image.nginx will be destroyed
  - resource "docker_image" "nginx" { ... }
  # docker_network.lab_network will be destroyed
  - resource "docker_network" "lab_network" { ... }

Plan: 0 to add, 0 to change, 3 to destroy.

Do you really want to destroy all resources?
  Enter a value: yes
```

```bash
# Verify resources đã bị xóa
docker ps | grep terraform-lab     # Không có gì
docker network ls | grep terraform # Không có gì
docker images | grep nginx         # Không có gì (keep_locally = false)
```

---

### Troubleshooting

**Lỗi: Docker daemon not running**
```
Error: Error pinging Docker server: ...
```
Giải quyết: Khởi động Docker Desktop.

**Lỗi: Port already in use**
```
Error: ... bind: address already in use
```
Giải quyết: Đổi `host_port` trong `terraform.tfvars` hoặc kill process đang dùng port đó:
```bash
lsof -i :8080 | grep LISTEN
kill -9 <PID>
```

**Lỗi: Provider version conflict**
```
Error: Failed to query available provider packages
```
Giải quyết:
```bash
rm -rf .terraform .terraform.lock.hcl
terraform init
```

**Lỗi: State locked**
```
Error: Error acquiring the state lock
```
Giải quyết (chỉ khi chắc chắn không có apply nào đang chạy):
```bash
terraform force-unlock <LOCK_ID>
```

---

## 6. Kiểm tra hiểu bài

**Câu 1 — Giải thích concept:**
Terraform state file chứa thông tin gì? Tại sao không nên commit nó vào Git? Nếu state file bị mất, điều gì xảy ra?

**Câu 2 — Chọn approach đúng:**
Team bạn có 8 người, đang dùng AWS, cần 3 environments (dev/staging/prod). Bạn sẽ dùng backend nào cho Terraform state? Tại sao?
- A. Local state trong mỗi máy developer
- B. S3 + DynamoDB với separate state files per environment
- C. Terraform Cloud
- D. Commit state file vào private Git repo

**Câu 3 — Debug:**
Bạn chạy `terraform apply` và thấy:
```
Error: Error creating S3 bucket: BucketAlreadyExists
```
Bucket này tồn tại trong AWS nhưng không có trong state. Điều gì đã xảy ra? Bạn xử lý thế nào?

**Câu 4 — Trade-offs:**
Đồng nghiệp đề xuất: "Chúng ta nên dùng Terraform workspaces cho dev/staging/production environments." Bạn có đồng ý không? Giải thích trade-offs.

**Câu 5 — Phân biệt:**
Sự khác nhau giữa `resource` và `data` trong Terraform? Cho ví dụ khi nào dùng data source thay vì resource.

---

## 7. Tóm tắt cuối ngày

**5 điểm cốt lõi:**

1. **IaC giải quyết reproducibility, drift, và collaboration** — không phải chỉ để "automate" mà là để infra trở thành first-class citizen trong engineering workflow.

2. **Terraform là declarative** — bạn mô tả desired state, Terraform tự tính delta và thực thi. Đây là sự khác biệt quan trọng nhất với Bash scripts.

3. **State là trái tim của Terraform** — nó mapping giữa code và real resources. Mất state = Terraform không biết gì về infra đang có. Production luôn dùng remote backend.

4. **Workflow: init → validate → plan → apply** — không bao giờ skip `plan` trong production. Plan là safety net quan trọng nhất.

5. **Provider, resource, data source, output, variable** — 5 building blocks. Nắm vững 5 thứ này là nền tảng cho mọi thứ tiếp theo.

**Outputs đã tạo:**
- Terraform project structure với Docker provider
- Docker container Nginx đã được provision bằng Terraform
- State file đã được observe và hiểu
- Đã thực hành full cycle: init → plan → apply → modify → destroy

**Chuẩn bị cho Day 2:**
- Day 2 sẽ đi sâu vào **Variables, Outputs, và Locals** — cách làm cho Terraform code reusable
- Sẽ refactor Day 1 code thành cấu trúc tốt hơn
- Bắt đầu với **Local Values** và `for_each` để tạo multiple resources

---

## 8. Tham khảo thêm

**Official Documentation:**
- [Terraform Documentation](https://developer.hashicorp.com/terraform/docs) — nguồn chính, luôn up to date
- [Terraform Registry](https://registry.terraform.io/) — tìm providers và modules
- [Docker Provider Docs](https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs)

**Quality Reading:**
- [Terraform: Up & Running (Yevgeniy Brikman)](https://www.terraformupandrunning.com/) — best book trên thị trường, tác giả là Gruntwork co-founder
- [How Terraform Works: A Visual Intro](https://blog.gruntwork.io/an-introduction-to-terraform-f17df9c6d180) — Gruntwork blog, chất lượng cao
- [Terraform Best Practices](https://www.terraform-best-practices.com/) — community best practices, real-world patterns

**Video:**
- [HashiCorp Learn: Get Started - Docker](https://developer.hashicorp.com/terraform/tutorials/docker-get-started) — official tutorial, free
