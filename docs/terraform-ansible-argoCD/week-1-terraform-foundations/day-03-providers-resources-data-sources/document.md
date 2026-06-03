# Day 3 - Reference Document: Providers, Resources, Data Sources, Dependency Management

**Dùng tài liệu này như quick reference khi coding. Không cần đọc từ đầu đến cuối.**

---

## 1. Provider Configuration Reference

### required_providers block

```hcl
terraform {
  required_version = ">= 1.5.0"          # Minimum Terraform CLI version

  required_providers {
    PROVIDER_LOCAL_NAME = {
      source  = "NAMESPACE/PROVIDER_NAME" # Ví dụ: hashicorp/aws, kreuzwerker/docker
      version = "VERSION_CONSTRAINT"
    }
  }
}
```

### Version Constraint Syntax

| Constraint       | Ý nghĩa                       | Ví dụ                    | Dùng khi                     |
|-----------------|-------------------------------|--------------------------|------------------------------|
| `= 3.0.0`       | Chính xác version này         | `= 5.31.0`               | Rất hiếm, không linh hoạt    |
| `!= 3.0.0`      | Không phải version này        | `!= 5.0.0`               | Exclude broken version        |
| `> 3.0.0`       | Lớn hơn                       | `> 5.0`                  | Lower bound mở                |
| `>= 3.0.0`      | Từ version này trở lên        | `>= 5.0`                 | Minimum version               |
| `< 4.0.0`       | Nhỏ hơn                       | `< 6.0`                  | Upper bound                   |
| `<= 4.0.0`      | Không vượt quá                | `<= 5.99`                | Maximum version               |
| `~> 3.0`        | >= 3.0, < 4.0 (minor ok)     | `~> 5.0`                 | **Recommended** - stable major|
| `~> 3.0.1`      | >= 3.0.1, < 3.1.0 (patch)    | `~> 5.31.0`              | Maximum stability             |
| `>= 3.0, < 4.0` | Range tường minh              | `>= 5.0, < 6.0`          | Kiểm soát chính xác           |

**Khuyến nghị thực tế:**
- Production: `~> 5.30` (allow minor + patch, block major breaking changes)
- Critical systems: `~> 5.30.1` (patch only)
- Development: `>= 5.0` (linh hoạt khi exploration)

---

### Provider Block Configuration

```hcl
# Default provider
provider "aws" {
  region = "ap-southeast-1"

  # Authentication - theo thứ tự ưu tiên:
  # 1. Env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  # 2. Shared credentials file: ~/.aws/credentials
  # 3. IAM instance profile (khi chạy trên EC2)
  # 4. ECS task role / EKS pod identity
  # KHÔNG BAO GIỜ hard-code credentials trong provider block

  # Optional: Default tags cho tất cả resources
  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Environment = var.environment
      Project     = var.project_name
    }
  }
}

# Provider với alias
provider "aws" {
  alias  = "us_east"
  region = "us-east-1"
}

# Provider với assume_role (cross-account)
provider "aws" {
  alias  = "production"
  region = "ap-southeast-1"
  assume_role {
    role_arn     = "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
    session_name = "terraform-${var.environment}"
    # Optional: duration, external_id cho security
    duration     = "1h"
  }
}
```

---

### Provider Alias Patterns

```
Pattern 1: Multi-region (same account)
─────────────────────────────────────
provider "aws" { region = "ap-southeast-1" }           # default
provider "aws" { alias = "dr"; region = "us-east-1" }  # DR

Pattern 2: Multi-account (same or different region)
─────────────────────────────────────────────────────
provider "aws" { ... }                    # default (dev account)
provider "aws" {
  alias = "prod"
  assume_role { role_arn = "...prod..." }
}

Pattern 3: Passing alias to modules
────────────────────────────────────
module "dr" {
  source = "./modules/dr-setup"
  providers = {
    aws         = aws          # default provider
    aws.replica = aws.us_east  # map local name to module's expected name
  }
}

# Inside module - khai báo expected providers
terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.replica]  # Báo module cần alias này
    }
  }
}
```

---

## 2. Resource Lifecycle Reference

### Lifecycle Meta-Arguments

```hcl
resource "TYPE" "NAME" {
  # ... resource arguments ...

  lifecycle {
    # 1. prevent_destroy
    # Ngăn terraform destroy resource này
    # Error nếu plan chứa destroy action
    prevent_destroy = true  # default: false

    # 2. create_before_destroy
    # Tạo replacement TRƯỚC KHI destroy instance cũ
    # Cần khi: resource không cho phép rename, zero-downtime replace
    create_before_destroy = true  # default: false

    # 3. ignore_changes
    # Ignore một số attributes khi so sánh state với real infrastructure
    # Dùng khi: external process thay đổi những attrs này
    ignore_changes = [
      tags,           # ignore toàn bộ tags map
      tags["Owner"],  # ignore specific tag key
      user_data,      # ignore nếu external process update
    ]
    # Hoặc ignore tất cả attributes (HIẾM DÙNG)
    # ignore_changes = all

    # 4. replace_triggered_by (Terraform >= 1.2)
    # Force replace resource này khi resource khác thay đổi
    replace_triggered_by = [
      aws_launch_template.app.latest_version  # Thay đổi launch template -> replace ASG
    ]

    # 5. precondition / postcondition (Terraform >= 1.2)
    precondition {
      condition     = var.instance_type != "t2.micro"
      error_message = "t2.micro không được dùng trong production"
    }
  }
}
```

### Resource Operations và Triggers

```
OPERATION       TRIGGER                             BEHAVIOR
─────────────────────────────────────────────────────────────────
Create          Resource chưa tồn tại trong state   Gọi CREATE API
Read            terraform plan / terraform refresh  Gọi READ API (reconcile)
Update          Attribute thay đổi, hỗ trợ in-place Gọi UPDATE API
Replace         Attribute thay đổi, forces replace  DELETE + CREATE API
Delete          terraform destroy / resource removed Gọi DELETE API
```

**Nhận biết "forces replacement" trong plan:**

```
# terraform plan output:
  ~ resource "aws_instance" "web" {
      ~ ami = "ami-old" -> "ami-new"  # forces replacement
    }

  # Plan: 1 to add, 0 to change, 1 to destroy.
  # Ký hiệu -/+ nghĩa là: destroy (-)  và create (+)
```

---

## 3. Data Source Reference

### Cú pháp cơ bản

```hcl
# Khai báo data source
data "PROVIDER_TYPE" "LOCAL_NAME" {
  # filter arguments
  argument1 = "value1"
  argument2 = "value2"
}

# Reference data source result
resource "some_resource" "example" {
  value = data.PROVIDER_TYPE.LOCAL_NAME.ATTRIBUTE
  #       ^^^^ keyword "data" bắt buộc
}
```

### Thời điểm data source được evaluate

```
terraform plan
    │
    ├─ Data sources mà Terraform có đủ thông tin -> evaluate NGAY LẬP TỨC
    │   (known values, no dependency on resources being created)
    │
    └─ Data sources phụ thuộc vào resources chưa tồn tại -> evaluate khi APPLY
        (deferred - giá trị là "known after apply" trong plan)
```

### Phổ biến Data Source Patterns

```hcl
# Pattern 1: Lấy existing resource bên ngoài Terraform
data "aws_vpc" "existing" {
  id = var.vpc_id   # VPC được tạo thủ công hoặc bởi Terraform khác
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "tag:Type"
    values = ["private"]
  }
}

# Pattern 2: Lấy thông tin current account/region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

# Pattern 3: Cross-state reference
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "my-terraform-state"
    key    = "network/terraform.tfstate"
    region = "ap-southeast-1"
  }
}

# Dùng output từ state kia
resource "aws_instance" "app" {
  subnet_id = data.terraform_remote_state.network.outputs.private_subnet_id
}

# Pattern 4: Template/file reading
data "template_file" "user_data" {
  template = file("${path.module}/templates/user_data.sh.tpl")
  vars = {
    app_name = var.app_name
    env      = var.environment
  }
}
# Thay thế hiện đại cho template_file:
locals {
  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    app_name = var.app_name
  })
}
```

---

## 4. Dependency Graph Reference

### Dependency Types

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Dependency Types                               │
│                                                                     │
│  IMPLICIT (recommended)           EXPLICIT (last resort)            │
│  ─────────────────────            ──────────────────────            │
│                                                                     │
│  resource "B" "name" {           resource "B" "name" {             │
│    value = A.name.attr           depends_on = [A.name]             │
│              │                   }                                  │
│              └─ Terraform tự                                        │
│                 biết B cần A     Dùng khi B cần A tồn tại          │
│  }                               nhưng không dùng attribute nào     │
│                                  của A                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Dependency Graph Visualization

```bash
# Generate
terraform graph

# Save và open (cần graphviz)
terraform graph | dot -Tsvg -o graph.svg && open graph.svg  # macOS
terraform graph | dot -Tsvg -o graph.svg && xdg-open graph.svg  # Linux

# Online (không cần cài graphviz)
terraform graph   # Copy output -> https://dreampuf.github.io/GraphvizOnline/

# Chỉ xem plan graph (filtered)
terraform graph -type=plan
terraform graph -type=plan-destroy
```

### Đọc DOT format output

```dot
digraph {
  # Mỗi node là một resource
  "[root] aws_instance.web" [...]

  # Mỗi edge là dependency
  "[root] aws_instance.web" -> "[root] aws_security_group.web"
  # Nghĩa là: aws_instance.web phụ thuộc vào aws_security_group.web
  # aws_security_group.web phải tạo TRƯỚC aws_instance.web
}
```

### Thứ tự Execution với Parallelism

```
Kịch bản:
  A (không phụ thuộc gì)
  B (không phụ thuộc gì)
  C (phụ thuộc A và B)
  D (phụ thuộc C)

Execution order:
  t=0: A ────┐
             ├─ (song song)
  t=0: B ────┘
  t=1: C (đợi A và B xong)
  t=2: D (đợi C xong)

terraform apply mặc định: 10 concurrent operations
Thay đổi: terraform apply -parallelism=5
```

---

## 5. Resource Addressing Reference

```
Địa chỉ resource trong Terraform:

TYPE.NAME
    │    │
    │    └─ Local name (bạn đặt)
    └─ Resource type (từ provider)

Ví dụ:
  aws_instance.web
  docker_container.nginx
  aws_s3_bucket.static_assets

Trong module:
  module.MODULE_NAME.TYPE.NAME

Trong state:
  module.vpc.aws_subnet.private[0]   # Khi dùng count
  module.vpc.aws_subnet.private["az1"]  # Khi dùng for_each
```

---

## 6. .terraform.lock.hcl Reference

```hcl
# .terraform.lock.hcl - AUTO-GENERATED, nhưng COMMIT vào git

provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.31.0"       # Exact version được lock
  constraints = "~> 5.30"      # Version constraint trong config
  hashes = [
    "h1:...",   # Hash để verify integrity
    "zh:...",
  ]
}
```

**Rules:**
- COMMIT `.terraform.lock.hcl` vào git
- KHÔNG COMMIT `.terraform/` directory
- Chạy `terraform init -upgrade` để update lock file
- Review diff của lock file khi provider version thay đổi

---

## 7. Provider Local Name vs Source Name

```
required_providers {
  myaws = {                      # "myaws" - local name (bạn đặt tùy ý)
    source = "hashicorp/aws"     # Actual registry path
    version = "~> 5.0"
  }
}

provider "myaws" {               # Dùng local name
  region = "ap-southeast-1"
}

resource "aws_instance" "web" { # Resource type vẫn dùng "aws" prefix
  provider = myaws               # Trỏ vào local name
}
```

**Best practice:** Dùng tên ngắn gọn và conventional. `aws`, `docker`, `kubernetes` - không đặt tên phức tạp trừ khi cần để phân biệt (ví dụ: `aws_primary`, `aws_dr`).

---

## 8. Common Provider Configuration Patterns

### Docker Provider

```hcl
provider "docker" {
  # Linux
  host = "unix:///var/run/docker.sock"

  # Windows Docker Desktop  
  # host = "npipe:////./pipe/docker_engine"

  # Remote Docker daemon
  # host = "tcp://remote-host:2376"
  # ca_material   = file("ca.pem")
  # cert_material = file("cert.pem")
  # key_material  = file("key.pem")

  # Docker registry auth (để pull private images)
  registry_auth {
    address  = "registry.example.com"
    username = var.registry_username
    password = var.registry_password
  }
}
```

### Kubernetes Provider

```hcl
provider "kubernetes" {
  # Option 1: Dùng kubeconfig file
  config_path    = "~/.kube/config"
  config_context = "my-cluster-context"

  # Option 2: In-cluster (khi Terraform chạy trong pod)
  # host                   = "https://kubernetes.default.svc"
  # token                  = file("/var/run/secrets/kubernetes.io/serviceaccount/token")
  # cluster_ca_certificate = file("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")

  # Option 3: EKS với AWS auth
  # host = data.aws_eks_cluster.main.endpoint
  # cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
  # exec {
  #   api_version = "client.authentication.k8s.io/v1beta1"
  #   command     = "aws"
  #   args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
  # }
}
```

---

## 9. Meta-Argument depends_on - Full Reference

```hcl
resource "TYPE" "NAME" {
  depends_on = [
    # Chấp nhận:
    resource_type.resource_name,          # Resource
    module.module_name,                   # Toàn bộ module
    data.data_type.data_name,             # Data source (hiếm dùng)
  ]
}

# KHÔNG chấp nhận:
# depends_on = [var.something]           # Variables không phải resource
# depends_on = ["literal string"]        # String literals
```

**Khi nào depends_on thực sự cần thiết:**

```
CẦN depends_on khi:
  - Resource A cần resource B tồn tại TRƯỚC, nhưng A không reference attribute của B
  - Ví dụ: App container cần database container healthy
  - Ví dụ: IAM policy phải attach trước khi Lambda function được invoke
  - Ví dụ: S3 bucket policy phải exist trước khi application start

KHÔNG CẦN depends_on khi:
  - Đã có implicit reference (attribute reference)
  - Dùng depends_on trùng với implicit reference -> redundant nhưng không lỗi
```

---

## 10. Lifecycle Diagram

```
                    terraform.tfstate
                           │
              ┌────────────▼────────────┐
              │                         │
    ┌─────────▼──────────┐   ┌─────────▼──────────┐
    │   State has         │   │   State has NO      │
    │   resource entry    │   │   resource entry    │
    └─────────┬──────────┘   └─────────┬──────────┘
              │                         │
              │                         ▼
              │                   terraform plan
              │                   shows: + create
              │
              ▼
    ┌───────────────────────────────────────────────────┐
    │        Config vs State Comparison                 │
    │                                                   │
    ├─ No change ──────────────────────► No-op          │
    │                                                   │
    ├─ Attribute changed (in-place ok) ─► ~ update      │
    │                                                   │
    ├─ Attribute changed (forces repl) ─► -/+ replace   │
    │                                                   │
    └─ Resource removed from config ───► - destroy      │
    └───────────────────────────────────────────────────┘
```
