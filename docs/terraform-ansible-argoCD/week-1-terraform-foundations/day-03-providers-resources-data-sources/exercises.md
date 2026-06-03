# Day 3 - Exercises: Providers, Resources, Data Sources, Dependency Management

**Độ khó tăng dần.** Làm từng exercise theo thứ tự. Mỗi exercise có hint nếu bị stuck.

---

## Exercise 1 - Provider Version Audit (Beginner, ~15 phút)

### Bối cảnh

Bạn nhận một Terraform codebase cũ từ teammate. File `providers.tf` như sau:

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 3.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "= 2.5.0"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}
```

### Yêu cầu

1. Liệt kê **3 vấn đề** với version constraints trong file trên. Giải thích tại sao mỗi vấn đề là vấn đề.
2. Viết lại `providers.tf` với constraints đúng chuẩn production. Dùng version phổ biến hiện tại (AWS ~> 5.0, Kubernetes ~> 2.0, Helm ~> 2.12, Random ~> 3.5).
3. Sau khi fix, command nào bạn chạy để update `.terraform.lock.hcl`?
4. File nào cần commit vào git, file nào không? Giải thích.

### Hint

<details>
<summary>Hint (chỉ mở nếu stuck sau 10 phút)</summary>

- `>= 3.0` cho AWS provider: AWS provider đã có v4.x và v5.x với breaking changes. Constraint này không ngăn được upgrade phá vỡ code.
- `kubernetes` không có version: Bất kỳ version nào đều chấp nhận. Nguy hiểm.
- `= 2.5.0` cho helm: Lock cứng, không nhận được security patches. Trade-off: stability vs security.
- `terraform init -upgrade` để update lock file.
- `.terraform.lock.hcl` commit, `.terraform/` không commit.

</details>

---

## Exercise 2 - Dependency Graph Analysis (Beginner-Intermediate, ~20 phút)

### Bối cảnh

Bạn được cho đoạn code Terraform sau. Không chạy code, chỉ đọc và phân tích.

```hcl
resource "docker_network" "backend" {
  name = "backend-network"
}

resource "docker_network" "frontend" {
  name = "frontend-network"
}

resource "docker_volume" "db_data" {
  name = "database-data"
}

resource "docker_container" "postgres" {
  name  = "postgres"
  image = "postgres:15"

  mounts {
    type   = "volume"
    target = "/var/lib/postgresql/data"
    source = docker_volume.db_data.name
  }

  networks_advanced {
    name = docker_network.backend.name
  }
}

resource "docker_container" "redis" {
  name  = "redis"
  image = "redis:7-alpine"

  networks_advanced {
    name = docker_network.backend.name
  }
}

resource "docker_container" "api" {
  name  = "api-server"
  image = "my-api:1.0"

  networks_advanced {
    name = docker_network.backend.name
  }

  networks_advanced {
    name = docker_network.frontend.name
  }

  depends_on = [
    docker_container.postgres,
    docker_container.redis,
  ]
}

resource "docker_container" "nginx" {
  name  = "nginx-proxy"
  image = "nginx:1.25"

  networks_advanced {
    name = docker_network.frontend.name
  }

  depends_on = [
    docker_container.api,
  ]
}
```

### Yêu cầu

1. Vẽ dependency graph dạng ASCII. Dùng `──►` để chỉ "phụ thuộc vào" (direction: B ──► A nghĩa là B cần A trước).
2. Liệt kê các resources có thể tạo **song song** ở mỗi wave (đợt).
3. `docker_container.api` có TWO `networks_advanced` blocks - đây có phải circular dependency không? Tại sao?
4. Dependency nào là **implicit** và dependency nào là **explicit**? Liệt kê từng cái.
5. Nếu bạn destroy toàn bộ stack, thứ tự destroy là gì?

### Expected Output Format

```
Wave 1 (song song): ...
Wave 2 (song song): ...
Wave 3: ...
Wave 4: ...

Destroy order: ...
```

---

## Exercise 3 - Data Source Decision Making (Intermediate, ~25 phút)

### Bối cảnh

Bạn đang viết Terraform cho một application deployment. Với mỗi tình huống dưới đây, quyết định dùng **resource**, **data source**, hay **variable** (hoặc combination). Giải thích reasoning.

### Tình huống

**Tình huống A:**
Team Network đã tạo VPC và subnets bằng Terraform riêng, kết quả được lưu vào S3 state bucket tại key `network/terraform.tfstate`. Team bạn cần tạo EC2 instances trong subnets đó.

**Tình huống B:**
Application cần một S3 bucket để lưu user-uploaded files. Bucket này chưa tồn tại. Terraform cần tạo mới với versioning enabled.

**Tình huống C:**
EC2 instances cần dùng AMI được build bởi Packer pipeline của team Platform. AMI được tag với `tag:PlatformVersion = "v2024.Q1"`. AMI ID thay đổi mỗi quý khi Platform team update.

**Tình huống D:**
Lambda function cần biết environment name (staging/production) để connect đúng database. Giá trị này khác nhau tùy theo deployment.

**Tình huống E:**
Security group cần allow traffic từ một IP address của third-party vendor. IP này thỉnh thoảng thay đổi (vendor thông báo qua email mỗi lần thay đổi). Giá trị hiện tại là `203.0.113.10/32`.

**Tình huống F:**
Terraform cần biết AWS Account ID hiện tại để construct ARN đúng. Account ID không nên hard-code vì cùng code deploy cho nhiều accounts.

### Yêu cầu

Với mỗi tình huống:
1. Chọn: resource / data source / variable / combination
2. Viết code snippet (5-10 dòng) minh họa cách implement
3. Giải thích một trade-off hoặc risk của approach bạn chọn

---

## Exercise 4 - Multi-region Provider Aliasing (Intermediate, ~30 phút)

### Bối cảnh

Bạn cần setup Disaster Recovery cho một application đang chạy ở Singapore (ap-southeast-1). DR region là Tokyo (ap-northeast-1). Yêu cầu:

- S3 bucket primary ở Singapore
- S3 bucket DR ở Tokyo  
- Cross-region replication từ Singapore sang Tokyo
- CloudFront distribution trỏ vào cả hai buckets (CloudFront phải dùng `us-east-1` provider vì ACM certificates cho CloudFront phải ở us-east-1)
- SNS topic ở Singapore để alert khi replication fail

### Yêu cầu

1. Viết `providers.tf` với tất cả provider aliases cần thiết. Comments giải thích tại sao mỗi alias tồn tại.

2. Viết provider configuration cho cấu hình sau:
   - Primary account: không cần assume_role (đã có credentials)
   - DR account: assume role `arn:aws:iam::DR_ACCOUNT_ID:role/TerraformDRRole`
   - CloudFront (us-east-1) trong primary account

3. Viết skeleton `main.tf` (chỉ cần resource declarations, không cần attributes đầy đủ) cho tất cả resources. Mỗi resource phải chỉ định đúng provider.

4. Câu hỏi tư duy: CloudFront có dependency vào S3 buckets (cả 2 regions) và ACM certificate (us-east-1). Điều này có tạo ra circular dependency không? Tại sao?

### Hint

<details>
<summary>Hint (chỉ mở nếu stuck)</summary>

- CloudFront là global service nhưng ACM certificate cho CloudFront phải ở us-east-1. Cần provider alias cho us-east-1.
- Cross-region replication config là attribute của primary S3 bucket resource, không phải resource riêng (tuỳ provider version).
- 4 providers cần thiết: ap-southeast-1 (primary), ap-northeast-1 (dr region), us-east-1 (cloudfront/acm), và có thể ap-southeast-1 với DR account credentials.

</details>

---

## Exercise 5 - Circular Dependency Fix (Intermediate-Advanced, ~25 phút)

### Bối cảnh

Code dưới đây có circular dependency. Terraform sẽ error: `Cycle: ...`

```hcl
# Attempt to create two security groups that allow traffic from each other

resource "aws_security_group" "app" {
  name        = "app-sg"
  description = "Security group for app servers"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.load_balancer.id]  # depends on lb
  }

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.database.id]  # depends on database
  }
}

resource "aws_security_group" "load_balancer" {
  name        = "lb-sg"
  description = "Security group for load balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]  # depends on app -> CYCLE!
  }
}

resource "aws_security_group" "database" {
  name        = "db-sg"
  description = "Security group for database"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]  # depends on app -> CYCLE!
  }
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
```

### Yêu cầu

1. Xác định chính xác cycle nào tồn tại trong code trên (có thể có nhiều hơn 1).

2. Giải thích tại sao circular dependency là vấn đề không thể resolve của Terraform (về mặt graph theory).

3. Refactor code để loại bỏ circular dependency mà vẫn giữ đúng security rules:
   - LB có thể gửi traffic đến App port 8080
   - App có thể gửi traffic đến DB port 5432
   - Không có rule nào bi mất

4. Sau khi fix, vẽ lại dependency graph. Confirm không còn cycle.

### Constraint

Không dùng `cidr_blocks` để replace `security_groups` references. Fix phải dùng `aws_security_group_rule` resources riêng biệt.

---

## Exercise 6 - Provider Misconfiguration Debug (Advanced, ~30 phút)

### Bối cảnh

Team bạn có module structure sau. Code không chạy được, có lỗi liên quan đến provider. Tìm và fix TẤT CẢ vấn đề.

**Root module - `main.tf`:**
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

provider "aws" {
  region = "us-east-1"
}

module "primary_infra" {
  source = "./modules/infra"
}

module "cdn_setup" {
  source = "./modules/cdn"
}
```

**Module `modules/infra/main.tf`:**
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-app-data-bucket"
}

resource "aws_s3_bucket" "us_backup" {
  provider = aws.us_east
  bucket   = "my-app-us-backup"
}
```

**Module `modules/cdn/main.tf`:**
```hcl
resource "aws_acm_certificate" "cert" {
  provider          = aws.us_east
  domain_name       = "example.com"
  validation_method = "DNS"
}

resource "aws_cloudfront_distribution" "cdn" {
  # ... simplified
  enabled = true
  viewer_certificate {
    acm_certificate_arn = aws_acm_certificate.cert.arn
  }
}
```

### Yêu cầu

1. Liệt kê TẤT CẢ lỗi trong code trên. Giải thích tại sao mỗi cái là lỗi.

2. Viết phiên bản đúng của tất cả files. Comments giải thích each fix.

3. Câu hỏi bonus: Trong root module, có 2 `provider "aws"` blocks mà không có `alias`. Terraform sẽ báo lỗi gì?

---

## Exercise 7 - Production Scenario: Stale Data Source Mitigation (Advanced, ~30 phút)

### Bối cảnh

Bạn được assign một task: "Thiết kế strategy để safely update base AMI cho toàn bộ Auto Scaling Groups trong production mà không gây outage."

Hiện tại code đang dùng:
```hcl
data "aws_ami" "base" {
  most_recent = true
  owners      = ["self"]
  filter {
    name   = "name"
    values = ["platform-base-*"]
  }
}

resource "aws_launch_template" "app" {
  image_id      = data.aws_ami.base.id
  instance_type = "t3.medium"
  # ...
}

resource "aws_autoscaling_group" "app" {
  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }
  min_size         = 2
  max_size         = 10
  desired_capacity = 4
  # ...
}
```

**Vấn đề đang gặp:**
- Mỗi lần Platform team publish AMI mới, `data.aws_ami.base.id` thay đổi
- `terraform plan` thấy change và update launch template
- Với `version = "$Latest"`, ASG tự động dùng template version mới
- Instances bị terminate và launch lại với AMI mới - có thể gây outage

### Yêu cầu

1. Phân tích tại sao `version = "$Latest"` kết hợp với data source `most_recent = true` nguy hiểm.

2. Đề xuất 2 strategies khác nhau để kiểm soát AMI updates. Mỗi strategy:
   - Viết code minh họa
   - Pros và cons
   - Suitable use case

3. Implement strategy bạn cho là tốt hơn. Code production-ready với:
   - Proper version pinning
   - Validation để prevent accidents
   - Comments giải thích rationale

4. Viết một `validation` block trong Terraform để prevent AMI ID bắt đầu bằng một specific prefix không hợp lệ. Ví dụ: AMI ID phải bắt đầu bằng `ami-`.

5. Câu hỏi tư duy: Nếu bạn MUỐN auto-update AMI nhưng với controlled rollout (ví dụ: 10% instances trước, rồi 100%), Terraform là đúng tool không? Hay cần kết hợp thêm gì?

---

## Answer Guide (Tự chấm)

### Exercise 1 - Vấn đề với providers.tf

**3 vấn đề:**
1. `aws >= 3.0`: Quá loose. AWS provider có major breaking changes giữa v3, v4, v5. Constraint này cho phép upgrade từ 3.x lên 5.x tự động.
2. `kubernetes` không có version: Nguy hiểm nhất. Terraform sẽ dùng bất kỳ version nào available.
3. `helm = 2.5.0`: Quá cứng. Không nhận security patches. Phải update manually mỗi patch.

**Fixed providers.tf:**
```hcl
terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}
```

**Command:** `terraform init -upgrade`

**Git:** Commit `.terraform.lock.hcl`. Không commit `.terraform/` directory (add vào `.gitignore`).

---

### Exercise 2 - Dependency Graph

```
Dependency Graph (B ──► A = B phụ thuộc A):

docker_container.nginx ──────────────────────────────► docker_container.api
                                                                │
                                         ┌──────────────────────┘
                                         │
docker_container.api ──────────────────►docker_container.postgres ──► docker_volume.db_data
                     │                                             │
                     │                  docker_container.redis     └──► docker_network.backend
                     │                         │
                     └─► docker_network.backend◄┘
                     └─► docker_network.frontend

Wave 1 (song song): docker_network.backend, docker_network.frontend, docker_volume.db_data
Wave 2 (song song): docker_container.postgres, docker_container.redis
Wave 3: docker_container.api
Wave 4: docker_container.nginx

Destroy order (ngược lại):
docker_container.nginx -> docker_container.api -> docker_container.postgres, docker_container.redis (song song) -> docker_volume.db_data, docker_network.backend, docker_network.frontend (song song)
```

**Câu 3:** Không phải circular dependency. `api` có 2 network connections nhưng cả 2 đều là references vào `docker_network` resources (không reference lại `api`).

**Câu 4:**
- Implicit: `docker_container.postgres -> docker_volume.db_data` (mounts source), `docker_container.postgres -> docker_network.backend` (networks_advanced name), `docker_container.redis -> docker_network.backend`, `docker_container.api -> docker_network.backend`, `docker_container.api -> docker_network.frontend`, `docker_container.nginx -> docker_network.frontend`
- Explicit: `docker_container.api -> docker_container.postgres` (depends_on), `docker_container.api -> docker_container.redis` (depends_on), `docker_container.nginx -> docker_container.api` (depends_on)

---

### Exercise 3 - Data Source Decision

**A:** `data "terraform_remote_state"` - bởi vì network state được quản lý bởi Terraform khác, đây là cách clean nhất để cross-reference outputs. Trade-off: tight coupling giữa 2 Terraform states.

**B:** `resource "aws_s3_bucket"` - Terraform cần own lifecycle của bucket này. Trade-off: destroy sẽ xóa bucket và data nếu không có protect.

**C:** `data "aws_ami"` với filter by tag version (không dùng `most_recent = true`). Trade-off: khi Platform team update, phải update tag filter hoặc variable.

**D:** `variable "environment"` với validation. Trade-off: phải được passed vào ở deploy time, không tự động.

**E:** `variable "vendor_ip_cidr"` với default value. Trade-off: khi IP thay đổi, phải update variable và re-apply. Không thể tự động.

**F:** `data "aws_caller_identity" "current" {}` - điển hình nhất. Trade-off: gần như không có, đây là best practice.

---

### Exercise 5 - Circular Dependency Fix

**Cycles:**
1. `aws_security_group.app` -> `aws_security_group.load_balancer` -> `aws_security_group.app`
2. `aws_security_group.app` -> `aws_security_group.database` -> `aws_security_group.app`

**Fix - tách rules ra:**
```hcl
resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id
  # Không có inline ingress/egress rules
}

resource "aws_security_group" "load_balancer" {
  name   = "lb-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name   = "db-sg"
  vpc_id = aws_vpc.main.id
}

# Rules được tạo SAU KHI cả hai SG tồn tại
resource "aws_security_group_rule" "app_from_lb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.load_balancer.id
  from_port = 8080
  to_port   = 8080
  protocol  = "tcp"
}

resource "aws_security_group_rule" "lb_to_app" {
  type                     = "egress"
  security_group_id        = aws_security_group.load_balancer.id
  source_security_group_id = aws_security_group.app.id
  from_port = 8080
  to_port   = 8080
  protocol  = "tcp"
}

resource "aws_security_group_rule" "app_to_db" {
  type                     = "egress"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.database.id
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"
}

resource "aws_security_group_rule" "db_from_app" {
  type                     = "ingress"
  security_group_id        = aws_security_group.database.id
  source_security_group_id = aws_security_group.app.id
  from_port = 5432
  to_port   = 5432
  protocol  = "tcp"
}
```

---

### Exercise 6 - Errors Found

1. **Root module**: 2 `provider "aws"` không có alias -> Error: duplicate provider configuration
2. **Module infra**: `provider = aws.us_east` reference alias không được khai báo và không được truyền vào module
3. **Module cdn**: `provider = aws.us_east` same issue
4. **Root module**: Không truyền `providers` map vào modules dù modules cần alias providers

**Fix cần:** Thêm alias, khai báo `configuration_aliases` trong modules, truyền `providers` map.

---

*Hoàn thành tất cả exercises trong 2-3 ngày. Không cần làm hết trong 1 buổi.*
