# Day 4 - Terraform State Fundamentals

> **Thời gian**: 2 giờ (30 phút lý thuyết + 30 phút deep dive + 60 phút lab)
> **Prerequisite**: Đã hoàn thành Day 1-3. Biết cách viết HCL cơ bản, chạy `terraform init/plan/apply`.

---

## 1. Mục tiêu ngày học

Sau Day 4, bạn có thể:

- Giải thích được Terraform state là gì và tại sao nó tồn tại - không đọc vẹt, mà giải thích bằng mental model của riêng mình.
- Đọc và phân tích một `terraform.tfstate` file thật sự.
- Nhận biết state drift, chạy `terraform refresh`, và quyết định cách xử lý phù hợp.
- Sử dụng thành thạo các lệnh `terraform state list/show/mv/rm/pull`.
- Hiểu rõ rủi ro bảo mật từ sensitive data trong state và biện pháp giảm thiểu.

---

## 2. Bối cảnh thực tế

### Tại sao state lại quan trọng đến vậy?

Hãy tưởng tượng bạn đang quản lý 200 microservices trên Kubernetes, mỗi service có EKS node group, RDS instance, ElastiCache, S3 bucket, CloudFront distribution riêng. Tổng cộng ~2000 resource AWS.

Terraform không thể gọi AWS API và hỏi "resource nào do tôi tạo?" vì AWS không phân biệt được. Terraform cần một nơi lưu trữ ánh xạ: **"resource block này trong code của tôi = resource thật này trên AWS"**. Đó chính là state.

### Thảm họa thực tế từ state mismanagement

**Incident 1 - Concurrent apply:**
Hai engineer cùng chạy `terraform apply` vào cùng thời điểm. State file không có lock. Kết quả: state bị corrupt, 15 resource mất khỏi state dù vẫn còn trên AWS. Team mất 8 tiếng để reconcile thủ công.

**Incident 2 - State bị xóa nhầm:**
Junior dev chạy `terraform workspace delete production` mà không biết rằng thao tác này xóa state của production workspace. 47 resource AWS không còn được Terraform track. Không thể chạy `terraform destroy` để cleanup. Resource bị bỏ lơ, bill tăng thêm $3,000/tháng.

**Incident 3 - Sensitive data leak:**
State file được commit lên Git repo public. State chứa plaintext: RDS master password, AWS access key của service account, private key của TLS certificate. Security breach toàn bộ production.

**Incident 4 - State drift trong microservices:**
DevOps team dùng Terraform. Developer team dùng AWS Console để "test nhanh" một security group rule. Ba tuần sau, ai đó chạy `terraform apply` - rule đó bị xóa. Production API không gọi được third-party service. Downtime 45 phút.

### State problems trong team environment

Trong môi trường microservices team lớn:

```
Team A (Backend)     Team B (Frontend)    Team C (Data)
     |                      |                   |
     v                      v                   v
 state-backend.tfstate  state-frontend.tfstate  state-data.tfstate
     |                      |                   |
     +----------+-----------+-------------------+
                |
         Shared VPC state (ai sở hữu?)
```

Vấn đề phổ biến:
- State file của shared infrastructure (VPC, subnets) bị nhiều team cùng modify.
- Không ai biết ai đang chạy apply khi không có locking.
- State leak: team này đọc được output (secrets) của team khác.

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 Terraform state là gì?

State là một JSON file chứa **snapshot** của infrastructure mà Terraform đang quản lý. Nó ánh xạ:

```
[Terraform resource block]  <-->  [Real-world resource]
                            state
```

**Analogy 1 - Database:**
Nghĩ về state như một database table:
- Code Terraform = schema + business logic
- State = data rows hiện tại
- `terraform apply` = transaction cập nhật data

**Analogy 2 - Git:**
- Code Terraform = source code
- State = deployed artifact (binary đang chạy trên production)
- `terraform plan` = `git diff` giữa code và deployed artifact
- `terraform apply` = deploy mới

Nhưng khác Git ở chỗ: state không version-controlled theo mặc định, và state có thể chứa sensitive data.

### 3.2 Tại sao Terraform cần state?

**Lý do 1 - Mapping to real world:**

Khi bạn viết:
```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
}
```

AWS trả về `instance_id = "i-0a1b2c3d4e5f67890"`. Terraform lưu mapping này vào state. Lần sau khi bạn chạy `plan`, Terraform gọi AWS API với ID đó để lấy current state, so sánh với desired state trong code.

Nếu không có state, Terraform không biết `aws_instance.web` tương ứng với EC2 instance nào trong số hàng trăm instance đang chạy.

**Lý do 2 - Performance:**

AWS account của bạn có 500 resources. Nếu Terraform phải gọi API để list toàn bộ resources mỗi lần `plan` chạy → rất chậm, có thể bị rate-limit.

State cho phép Terraform chỉ gọi API cho những resource cụ thể mà nó quản lý, dựa trên ID đã lưu trong state.

**Lý do 3 - Dependency tracking:**

```hcl
resource "aws_vpc" "main" { ... }

resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id  # dependency
}
```

State lưu thứ tự tạo/xóa resource dựa trên dependency graph. Khi destroy, Terraform xóa subnet trước, VPC sau - không phải ngẫu nhiên.

### 3.3 State file structure - JSON deep dive

Chạy `cat terraform.tfstate` sau khi apply, bạn thấy:

```json
{
  "version": 4,
  "terraform_version": "1.6.0",
  "serial": 5,
  "lineage": "3b3e2e3d-1234-5678-abcd-ef0123456789",
  "outputs": {
    "instance_ip": {
      "value": "10.0.1.42",
      "type": "string",
      "sensitive": false
    }
  },
  "resources": [
    {
      "mode": "managed",
      "type": "docker_container",
      "name": "nginx",
      "provider": "provider[\"registry.terraform.io/kreuzwerker/docker\"]",
      "instances": [
        {
          "schema_version": 2,
          "attributes": {
            "id": "a1b2c3d4e5f6...",
            "name": "nginx-web",
            "image": "sha256:abc123...",
            "ports": [
              {
                "internal": 80,
                "external": 8080,
                "ip": "0.0.0.0",
                "protocol": "tcp"
              }
            ]
          },
          "sensitive_attributes": [],
          "private": "base64encodeddata..."
        }
      ]
    }
  ]
}
```

**Các field quan trọng:**

| Field | Ý nghĩa |
|-------|---------|
| `version` | Schema version của state format (Terraform internal) |
| `serial` | Tăng mỗi lần state được cập nhật. Dùng để detect conflict |
| `lineage` | UUID gắn với state file này từ khi được tạo. Prevent mixing state files |
| `mode` | `managed` = resource bạn tạo; `data` = data source |
| `instances` | Một resource có thể có nhiều instances (dùng `count` hoặc `for_each`) |
| `attributes` | Toàn bộ attributes của resource, kể cả computed values |
| `sensitive_attributes` | Paths đến attributes được mark là sensitive |
| `private` | Internal provider data, không phải để đọc trực tiếp |

**Quan trọng về `serial`:**

```
Initial apply  → serial: 1
Second apply   → serial: 2
terraform mv   → serial: 3
...
```

Khi hai người cùng apply, người sau sẽ fail vì serial trên remote state đã tăng. Đây là một phần của conflict detection mechanism.

### 3.4 State drift - Định nghĩa, nguyên nhân, kịch bản thực tế

**State drift = Trạng thái thực tế của infrastructure KHÁC với trạng thái Terraform đang track trong state.**

```
┌─────────────────────────────────────────────────────┐
│                     DRIFT                           │
│                                                     │
│  Terraform State          Real World                │
│  ┌─────────────┐         ┌─────────────┐           │
│  │ t3.micro    │  ≠      │ t3.large    │  ← drift  │
│  │ sg-a, sg-b  │  ≠      │ sg-a        │  ← drift  │
│  │ tag: v1.0   │  =      │ tag: v1.0   │  ← ok     │
│  └─────────────┘         └─────────────┘           │
└─────────────────────────────────────────────────────┘
```

**Nguyên nhân phổ biến:**

1. **Manual change qua Console/CLI**: Engineer SSH vào server, thêm security group rule.
2. **Auto-scaling**: AWS tự scale EC2 instances, Terraform không biết.
3. **Service tự sửa config**: AWS managed service tự update config (ví dụ RDS minor version upgrade).
4. **Resource bị xóa ngoài Terraform**: Ai đó dùng `aws ec2 terminate-instances` trực tiếp.
5. **Provider update**: Provider mới interpret attribute khác với provider cũ.

**Kịch bản thực tế trong microservices:**

```
08:00 - Terraform apply: EC2 instance với SG có port 443 open
10:30 - Developer mở thêm port 8080 qua Console để test
14:00 - Security audit yêu cầu tắt 8080
14:05 - Terraform plan: không thấy 8080 vì state không biết 8080 tồn tại
14:10 - Terraform apply: không làm gì với 8080 → 8080 vẫn còn
```

### 3.5 State locking

**Vấn đề không có locking:**

```
Time →
Engineer A: plan ... apply (đang chạy)
Engineer B:           plan ... apply (đang chạy)
                                    ↕
                              CONFLICT:
                         cả hai cùng cập nhật state
                         state bị corrupt
```

**Với locking:**

```
Time →
Engineer A: plan ... acquire lock ... apply ... release lock
Engineer B:           request lock ... WAIT... acquire lock ... apply
```

**Local state không có locking** - đây là lý do local state chỉ phù hợp khi làm việc một mình.

**Remote backends cung cấp locking:**
- S3 + DynamoDB: DynamoDB table làm lock store.
- Terraform Cloud: built-in locking.
- GCS: object locking.
- Azure Blob: lease-based locking.

Khi apply bị interrupt (mất kết nối, Ctrl+C), lock có thể bị stuck. Cần `terraform force-unlock <lock-id>` để giải phóng.

### 3.6 Local state vs Remote state

```
┌──────────────────────────────────────────────────────────────────┐
│                    LOCAL STATE                                   │
│                                                                  │
│  terraform.tfstate  ← file trên disk của bạn                    │
│                                                                  │
│  Pros:                          Cons:                            │
│  + Zero setup                   - Không share được với team      │
│  + Fast                         - Không có locking               │
│  + Simple debugging             - Mất khi mất máy                │
│                                 - Sensitive data trên disk cục bộ│
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    REMOTE STATE                                  │
│                                                                  │
│  S3 / GCS / Azure Blob / Terraform Cloud ← state lưu trên đây  │
│                                                                  │
│  Pros:                          Cons:                            │
│  + Team collaboration           - Setup phức tạp hơn            │
│  + Locking (với DynamoDB etc)   - Cần network access            │
│  + Versioning (S3 versioning)   - Cost nhỏ (storage)            │
│  + Access control               - Latency cao hơn               │
└──────────────────────────────────────────────────────────────────┘
```

Day 5 sẽ đi sâu vào Remote Backend. Hôm nay focus vào local state để hiểu cơ chế.

### 3.7 Sensitive data trong state

**Đây là một trong những security risk lớn nhất của Terraform.**

Khi bạn tạo RDS instance:
```hcl
resource "aws_db_instance" "postgres" {
  password = var.db_password  # bạn mark var này là sensitive
}
```

Terraform KHÔNG encrypt password trong state:
```json
{
  "attributes": {
    "password": "MySecretP@ssword123",  // PLAINTEXT trong state!
    ...
  }
}
```

**Terraform docs nói gì:** State "may contain sensitive values" và bạn phải "treat the state itself as sensitive data". Encryption at rest là trách nhiệm của bạn thông qua remote backend.

**Những gì thường bị expose trong state:**
- Database passwords
- API keys và tokens
- Private keys (TLS, SSH)
- Connection strings
- AWS access keys

**Biện pháp:**
1. Không bao giờ commit state vào Git.
2. Dùng remote backend với encryption at rest (S3 với SSE-KMS).
3. Restrict IAM/RBAC access vào state storage.
4. Dùng `.gitignore` để block `*.tfstate` và `*.tfstate.backup`.

```gitignore
# .gitignore
*.tfstate
*.tfstate.backup
.terraform/
.terraform.lock.hcl  # cái này thì nên commit
```

### 3.8 State workflow - ASCII diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    TERRAFORM WORKFLOW                           │
└─────────────────────────────────────────────────────────────────┘

  Your Code (*.tf)
       │
       │ terraform plan
       ▼
  ┌──────────┐    Read    ┌──────────────┐    Read    ┌──────────┐
  │ Desired  │ ◄────────► │   State      │ ◄────────► │  Real    │
  │  State   │            │   File       │  API calls │  World   │
  │ (HCL)    │            │ (.tfstate)   │            │ (AWS etc)│
  └──────────┘            └──────────────┘            └──────────┘
       │                        │                          │
       │         Plan           │                          │
       │ ◄──────────────────────┘                          │
       │                                                   │
       │    "create X, change Y, destroy Z"                │
       │                                                   │
       │ terraform apply                                   │
       ▼                                                   │
  ┌──────────┐   API calls  ┌──────────────┐              │
  │ Terraform│ ────────────►│  Real World  │              │
  │  Engine  │              │  (mutated)   │              │
  └──────────┘              └──────────────┘              │
       │                          │                        │
       │ Update state             │                        │
       ▼                          │                        │
  ┌──────────────┐                │                        │
  │  New State   │ ◄──────────────┘                        │
  │   File       │   (reflect new real world state)        │
  └──────────────┘                                         │
                                                           │
  ┌──────────────────────────────────────────────────────┐ │
  │  STATE DRIFT (khi ai đó thay đổi real world ngoài   │ │
  │  Terraform):                                         │ │
  │                                                      │ │
  │  State File ≠ Real World  ← DRIFT                    │ │
  │                                                      │ │
  │  terraform refresh → update state to match real world│ │
  │  terraform plan    → show diff (desired vs real)     │ │
  └──────────────────────────────────────────────────────┘ │
```

---

## 4. Deep dive & Trade-offs - 30 phút

### 4.1 State management strategies - So sánh

| Strategy | Use case | Pros | Cons |
|----------|----------|------|------|
| Local state | Learning, personal projects, CI với single runner | Zero setup | Không team-friendly, no locking |
| S3 + DynamoDB | AWS shops, production | Mature, versioning, locking, IAM | Cần AWS account, setup phức tạp hơn |
| Terraform Cloud | SaaS-first teams | Built-in locking, UI, VCS integration | Cost ($20/user/tháng), vendor lock-in |
| GCS + Cloud Storage lock | GCP shops | Native GCP integration | GCP-specifc |
| Azure Blob | Azure shops | Native Azure integration | Azure-specific |
| GitLab Terraform State | GitLab CI/CD users | Integrated với GitLab | GitLab-dependent |

**Decision tree:**

```
Làm một mình? → Local state OK (nhưng backup thường xuyên)
     │
     No
     │
     ▼
Dùng AWS? → S3 + DynamoDB (Day 5)
     │
     No
     │
     ▼
Muốn managed solution? → Terraform Cloud / HCP Terraform
     │
     No
     │
     ▼
GCP? → GCS backend
Azure? → Azure Blob backend
```

### 4.2 State drift - Detection và remediation

**Phát hiện drift:**

```bash
# Option 1: terraform refresh (deprecated trong newer versions)
terraform refresh

# Option 2: terraform plan -refresh-only (recommended từ Terraform 0.15.4+)
terraform plan -refresh-only

# Option 3: terraform plan (sẽ show drift như một phần của plan output)
terraform plan
```

**Đọc output của `terraform plan -refresh-only`:**

```
~ aws_instance.web (drift detected)
  ~ instance_type = "t3.micro" -> "t3.large"  # ai đó đổi instance type
  ~ tags = {
    + "Environment" = "test"                   # tag được thêm ngoài Terraform
  }
```

**Remediation options:**

| Option | Khi nào dùng | Lệnh |
|--------|-------------|------|
| **Accept drift** - Cập nhật state theo thực tế | Thay đổi là hợp lệ, muốn giữ | `terraform apply -refresh-only` |
| **Revert drift** - Apply lại để đưa về desired state | Thay đổi không được authorize | `terraform apply` |
| **Import** - Bring resource vào Terraform management | Resource tốt nhưng chưa trong state | `terraform import` |
| **Ignore** - Cập nhật code để match thực tế | Quyết định thay đổi desired state | Sửa code + apply |

**Khi nào NOT nên revert drift:**
- Auto-scaling groups: instance count thay đổi là expected.
- Managed services tự update (RDS minor version).
- Kubernetes node groups với spot instances.

### 4.3 State file security

**Threat model:**

```
Attacker access to state file
           │
           ├─► Read plaintext passwords → RDS breach
           ├─► Read API keys → AWS account breach
           ├─► Modify state → Next apply destroys prod
           └─► Delete state → Infrastructure orphaned
```

**Defense in depth:**

```
Layer 1: Storage encryption (S3 SSE-KMS, GCS CMEK)
Layer 2: Transport encryption (HTTPS)
Layer 3: Access control (IAM policies, bucket policies)
Layer 4: Audit logging (CloudTrail, GCS audit logs)
Layer 5: State versioning (S3 versioning để recover từ delete/corrupt)
Layer 6: Secrets management (Vault, AWS Secrets Manager) - không để secrets trong Terraform
```

**Thực tế tốt nhất:** Dùng AWS Secrets Manager hoặc Vault để lưu secrets, retrieve trong Terraform qua data source. State vẫn chứa reference, không phải secret value thật:

```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "prod/myapp/db-password"
}

resource "aws_db_instance" "postgres" {
  password = data.aws_secretsmanager_secret_version.db_password.secret_string
}
```

State vẫn chứa password value, nhưng ít nhất bạn không hard-code trong code và có thể rotate secret mà không thay đổi Terraform code.

### 4.4 terraform state commands

**`terraform state list`** - List tất cả resources trong state:

```bash
$ terraform state list
docker_container.nginx
docker_image.nginx
local_file.config
module.vpc.aws_vpc.main
module.vpc.aws_subnet.public[0]
module.vpc.aws_subnet.public[1]
```

**`terraform state show`** - Xem chi tiết một resource:

```bash
$ terraform state show docker_container.nginx
# docker_container.nginx:
resource "docker_container" "nginx" {
    id    = "a1b2c3d4..."
    image = "sha256:abc123..."
    name  = "nginx-web"
    ports {
        external = 8080
        internal = 80
        ip       = "0.0.0.0"
        protocol = "tcp"
    }
}
```

**`terraform state mv`** - Đổi tên/di chuyển resource trong state:

```bash
# Use case: bạn rename resource trong code từ "web" sang "app"
# Nếu không mv, Terraform sẽ destroy "web" và create "app" → downtime!
terraform state mv aws_instance.web aws_instance.app

# Move resource vào module
terraform state mv aws_instance.web module.app.aws_instance.web

# Move resource giữa modules
terraform state mv module.old.aws_instance.web module.new.aws_instance.web
```

**`terraform state rm`** - Xóa resource khỏi state (không xóa real resource):

```bash
# Use case: bạn muốn Terraform không quản lý resource này nữa
# Resource vẫn tồn tại trên infrastructure, chỉ mất khỏi state
terraform state rm aws_instance.legacy

# Xóa cả module
terraform state rm module.legacy_vpc
```

**`terraform state pull`** - Tải state từ remote về local (pretty-print JSON):

```bash
terraform state pull > backup.tfstate
terraform state pull | jq '.resources[] | select(.type == "aws_instance")'
```

**`terraform state push`** - Đẩy local state lên remote (NGUY HIỂM):

```bash
# Chỉ dùng khi recovery, biết mình đang làm gì
terraform state push backup.tfstate

# Force push khi serial conflict (rất nguy hiểm)
terraform state push -force backup.tfstate
```

### 4.5 Khi nào manipulate state thủ công vs để Terraform tự xử lý?

**Để Terraform tự xử lý (99% trường hợp):**
- Tạo, update, delete resource thông thường.
- Dependency tracking.
- Drift detection qua `terraform plan`.

**Manipulate state thủ công (có lý do rõ ràng):**

| Tình huống | Lệnh |
|-----------|------|
| Rename resource trong code mà không muốn recreate | `state mv` |
| Refactor code vào module mới | `state mv` |
| Import resource tạo ngoài Terraform | `terraform import` |
| Tách state: một codebase → nhiều codebase | `state mv` + `state push` |
| Resource bị lỗi, muốn skip khỏi Terraform | `state rm` + `terraform.ignore` hoặc lifecycle |
| Recovery từ state corruption | `state push` |

**Nguyên tắc:** Mỗi lần manipulate state thủ công, hãy backup state trước, document lý do, và verify bằng `terraform plan` sau khi xong.

### 4.6 Common pitfalls

**Pitfall 1 - Concurrent modifications:**
```
Problem: Hai CI/CD pipeline cùng trigger terraform apply cho cùng workspace
Fix: Remote backend với locking, hoặc serialize pipeline (một pipeline tại một thời điểm)
```

**Pitfall 2 - State corruption:**
```
Problem: Kill -9 terraform apply đang chạy → state ở trạng thái half-written
Fix: S3 versioning → restore về version trước. Local → dùng terraform.tfstate.backup
```

**Pitfall 3 - Accidental state deletion:**
```
Problem: terraform workspace delete production (xóa cả state!)
Fix: S3 versioning + MFA delete. Terraform Cloud: state history 30+ days.
Prevention: IAM policy restrict workspace delete trên production
```

**Pitfall 4 - State chứa thông tin nhạy cảm bị commit:**
```
Problem: developer git add . mà không có .gitignore
Fix: git history rewrite (BFG Repo Cleaner) + rotate tất cả secrets bị expose
Prevention: pre-commit hook kiểm tra *.tfstate
```

**Pitfall 5 - Wrong workspace:**
```
Problem: terraform apply đang ở staging workspace, dev nghĩ đang ở dev
Fix: Luôn check terraform workspace show trước khi apply
Prevention: Naming convention rõ ràng, CI/CD tự set workspace
```

### 4.7 Best practices theo context

**Individual developer:**
- Local state OK cho experiment.
- Luôn có `.gitignore` block state files.
- Backup config quan trọng vào remote (even S3 personal bucket).

**Small team (2-5 người):**
- Remote backend bắt buộc (S3 + DynamoDB cho AWS).
- Separate state per environment (dev/staging/prod).
- State access restricted: chỉ DevOps access được prod state.
- Terraform Cloud free tier (5 users) là lựa chọn tốt.

**Enterprise (20+ người):**
- Separate AWS account per environment.
- State per team + per service (Atlantis hoặc Terraform Cloud).
- Policy as Code (Sentinel hoặc OPA) để gate apply.
- Automated drift detection (scheduled `terraform plan`).
- State audit logging (CloudTrail + alerts khi state được modify).

---

## 5. Hands-on Lab - 60 phút

### Mục tiêu lab

- Inspect state file thực tế.
- Simulate state drift (thay đổi resource ngoài Terraform).
- Phát hiện và xử lý drift.
- Practice `terraform state` commands.

### Prerequisites

- Docker đang chạy (`docker ps` không lỗi).
- Terraform >= 1.0 installed.
- `jq` installed (optional nhưng hữu ích).

### Setup - 10 phút

Tạo working directory:

```bash
mkdir -p ~/tf-state-lab && cd ~/tf-state-lab
```

Tạo `main.tf`:

```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# Pull nginx image
resource "docker_image" "nginx" {
  name         = "nginx:alpine"
  keep_locally = true
}

# Container 1: web server
resource "docker_container" "web" {
  name  = "tf-state-web"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = 8080
  }

  labels {
    label = "managed-by"
    value = "terraform"
  }

  labels {
    label = "environment"
    value = "lab"
  }
}

# Container 2: api server
resource "docker_container" "api" {
  name  = "tf-state-api"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = 8081
  }

  labels {
    label = "managed-by"
    value = "terraform"
  }
}

output "web_url" {
  value       = "http://localhost:${docker_container.web.ports[0].external}"
  description = "Web container URL"
}

output "api_url" {
  value       = "http://localhost:${docker_container.api.ports[0].external}"
  description = "API container URL"
}
```

```bash
terraform init
```

Expected output:
```
Initializing the backend...
Initializing provider plugins...
- Finding kreuzwerker/docker versions matching "~> 3.0"...
- Installing kreuzwerker/docker v3.x.x...
Terraform has been successfully initialized!
```

### Step 1: Apply và inspect state - 10 phút

```bash
terraform apply -auto-approve
```

Expected output:
```
docker_image.nginx: Creating...
docker_image.nginx: Still creating...
docker_image.nginx: Creation complete after Xs [id=sha256:...]
docker_container.web: Creating...
docker_container.web: Creation complete after 1s [id=...]
docker_container.api: Creating...
docker_container.api: Creation complete after 1s [id=...]

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.

Outputs:
api_url = "http://localhost:8081"
web_url = "http://localhost:8080"
```

**Verify containers đang chạy:**
```bash
docker ps --filter "name=tf-state"
```

**Inspect state file:**
```bash
# Xem raw state
cat terraform.tfstate

# Đếm số resources
cat terraform.tfstate | grep '"type":' | wc -l

# List resources trong state
terraform state list
```

Expected từ `terraform state list`:
```
docker_container.api
docker_container.web
docker_image.nginx
```

**Xem chi tiết web container:**
```bash
terraform state show docker_container.web
```

**Nếu có jq, phân tích state:**
```bash
# Xem tất cả resource types
cat terraform.tfstate | jq '[.resources[].type] | unique'

# Xem attributes của web container
cat terraform.tfstate | jq '.resources[] | select(.name == "web") | .instances[0].attributes'

# Kiểm tra serial (sẽ tăng sau mỗi apply)
cat terraform.tfstate | jq '{serial: .serial, lineage: .lineage}'
```

**Ghi nhớ serial hiện tại:**
```bash
cat terraform.tfstate | jq '.serial'
# ví dụ: 3
```

### Step 2: Simulate state drift - 10 phút

Bây giờ "ai đó" thay đổi infrastructure ngoài Terraform - giống như developer dùng Docker CLI trực tiếp.

**Scenario: Stop container web giả lập "crash"**

```bash
# Xóa container web trực tiếp bằng Docker (không qua Terraform)
docker stop tf-state-web && docker rm tf-state-web
```

**Verify container đã biến:**
```bash
docker ps --filter "name=tf-state"
# Chỉ còn tf-state-api
```

**Nhưng Terraform state vẫn nghĩ container web đang chạy:**
```bash
terraform state list
# Vẫn thấy docker_container.web trong state!
```

**Đây chính là drift:** Real world (container không tồn tại) KHÁC với state (container vẫn được track).

### Step 3: Phát hiện và xử lý drift - 15 phút

**Phát hiện drift:**
```bash
terraform plan
```

Expected output:
```
docker_container.web: Refreshing state... [id=<old_id>]

Note: Objects have changed outside of Terraform

docker_container.web has been deleted

Terraform will perform the following actions:

  # docker_container.web will be created
  + resource "docker_container" "web" {
      + id    = (known after apply)
      + name  = "tf-state-web"
      ...
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

Terraform detect drift và muốn recreate container.

**Option A - Revert drift (bring back container):**
```bash
terraform apply -auto-approve
```

Đây là hành vi mong muốn: Terraform đưa infrastructure về desired state.

```bash
docker ps --filter "name=tf-state"
# Cả hai container đều chạy lại
```

**Simulate drift lần 2 - Thay đổi label (config change):**

Lần này simulate một drift khác: ai đó thêm label vào container api.

```bash
# Không thể add label vào container đang chạy qua Docker CLI
# Simulate bằng cách edit state trực tiếp (CHỈ LÀM TRONG LAB, không làm production!)

# Backup state trước
cp terraform.tfstate terraform.tfstate.backup-$(date +%Y%m%d-%H%M%S)

# Refresh state để xem current state
terraform plan -refresh-only
```

**Option B - Accept drift với refresh-only:**
```bash
# Nếu drift là hợp lệ, accept nó
terraform apply -refresh-only -auto-approve
# State được cập nhật để match real world
```

### Step 4: Practice state commands - 15 phút

**Exercise 4.1 - State backup:**
```bash
# Pull state và save backup
terraform state pull > manual-backup.json

# Verify backup
cat manual-backup.json | jq '.serial'

# Compare với local state
diff <(cat terraform.tfstate | jq .) <(cat manual-backup.json | jq .)
# Không có diff: chúng giống nhau
```

**Exercise 4.2 - State mv (rename resource):**

Simulate rename resource trong code từ `web` sang `frontend`:

```bash
# Trước khi rename code, move trong state
terraform state mv docker_container.web docker_container.frontend

# Verify
terraform state list
# docker_container.api
# docker_container.frontend  ← đã đổi tên
# docker_image.nginx
```

Bây giờ đổi tên trong `main.tf`:
```hcl
# Đổi từ:
# resource "docker_container" "web" {
# Thành:
resource "docker_container" "frontend" {
  name  = "tf-state-web"  # name vẫn giữ nguyên (Docker container name)
  ...
}

# Cập nhật output:
output "web_url" {
  value = "http://localhost:${docker_container.frontend.ports[0].external}"
}
```

```bash
terraform plan
# Expected: No changes. Infrastructure is up-to-date.
# Nếu thấy changes, kiểm tra lại state mv và code
```

**Exercise 4.3 - State rm:**
```bash
# Xóa api container khỏi state (container vẫn chạy)
terraform state rm docker_container.api

# Verify: container vẫn chạy
docker ps --filter "name=tf-state-api"

# Verify: không còn trong state
terraform state list
# docker_container.frontend
# docker_image.nginx
# docker_container.api biến mất khỏi state

# Plan: Terraform muốn CREATE api container vì nó trong code nhưng không trong state
terraform plan
# Sẽ show: 1 to add (docker_container.api)
```

**Cleanup:**
```bash
# Đưa api container vào state lại bằng import
CONTAINER_ID=$(docker inspect tf-state-api --format '{{.Id}}')
terraform import docker_container.api $CONTAINER_ID

# Verify
terraform state list
terraform plan
# Expected: No changes.
```

**Exercise 4.4 - Xem internal state change:**
```bash
# Xem serial trước
SERIAL_BEFORE=$(cat terraform.tfstate | jq '.serial')
echo "Serial before: $SERIAL_BEFORE"

# Thực hiện một thay đổi nhỏ
terraform apply -auto-approve  # ngay cả khi no changes, serial không tăng

# Touch một resource để force update
# Thêm tag vào main.tf:
# labels { label = "version" value = "2" }
# sau đó:
terraform apply -auto-approve

SERIAL_AFTER=$(cat terraform.tfstate | jq '.serial')
echo "Serial after: $SERIAL_AFTER"
# Serial tăng lên 1
```

### Cleanup Lab

```bash
# Về code ban đầu nếu cần
# Destroy tất cả
terraform destroy -auto-approve

# Verify
docker ps --filter "name=tf-state"
# Không còn container nào

# Clean workspace
rm -rf ~/tf-state-lab
```

### Troubleshooting common errors

**Error: `Error: Failed to query available provider packages`**
```
Fix: Kiểm tra internet connection. Nếu có proxy, set HTTP_PROXY env var.
     terraform init -upgrade để refresh provider cache.
```

**Error: `Error response from daemon: Conflict. The container name is already in use`**
```
Fix: Container tên đó đang chạy ngoài Terraform.
     docker rm -f <container-name>
     Hoặc terraform import để đưa vào state.
```

**Error: `Error: Invalid index` khi access ports[0]**
```
Fix: Container chưa có port mapping, hoặc container chưa chạy.
     Kiểm tra docker_container resource có ports block không.
```

**Error: `There are some problems with the CLI flags` sau terraform state mv**
```
Fix: Syntax state mv: terraform state mv <source> <destination>
     Cả source và destination phải là resource address hợp lệ.
```

**State bị corrupt - dấu hiệu:**
```
Error: Failed to load state: state snapshot was created by Terraform vX.Y.Z...
Fix: terraform state pull > corrupt.json
     # Analyze corrupt.json để tìm issue
     # Restore từ backup: terraform state push backup.json
```

---

## 6. Kiểm tra hiểu bài

1. **Câu hỏi 1**: Terraform state lưu ở đâu theo mặc định? Tại sao không nên commit file này vào Git? Kể ra ít nhất 3 loại thông tin nhạy cảm có thể bị expose.

2. **Câu hỏi 2**: Giải thích sự khác biệt giữa `terraform refresh` / `terraform plan -refresh-only` và `terraform apply -refresh-only`. Khi nào bạn dùng cái nào?

3. **Câu hỏi 3**: Bạn rename resource `aws_instance.web_server` thành `aws_instance.app_server` trong code. Nếu bạn chỉ đổi tên trong code mà không làm gì thêm, `terraform plan` sẽ cho kết quả gì? Phải làm gì để tránh downtime?

4. **Câu hỏi 4**: Serial number trong state file là gì và nó được dùng để phòng chống vấn đề gì? Điều gì xảy ra nếu hai người cùng chạy `terraform apply` cùng lúc với local state?

5. **Câu hỏi 5 (bonus)**: `terraform state rm docker_container.api` thực sự làm gì với Docker container đang chạy? Sau lệnh này, nếu bạn chạy `terraform apply`, điều gì xảy ra và tại sao?

---

## 7. Tóm tắt cuối ngày

### Key points

- **State là single source of truth** của Terraform về infrastructure. Mất state = mất khả năng manage infrastructure qua Terraform.
- **State chứa plaintext sensitive data**. Không bao giờ commit vào Git. Luôn có `.gitignore` đúng cách.
- **Local state**: Tốt cho học, không phù hợp team. Remote state với locking là bắt buộc cho production.
- **State drift** xảy ra khi real world thay đổi ngoài Terraform. Detect bằng `terraform plan`. Xử lý bằng `apply` hoặc `apply -refresh-only` tùy tình huống.
- **`serial`** tăng theo mỗi state update, giúp detect concurrent modification conflicts.
- **`terraform state mv`** là cách đổi tên resource mà không destroy/recreate. Không biết lệnh này gây downtime không cần thiết.
- **Backup state trước mọi thao tác manual**. State corruption rất khó phục hồi nếu không có backup.

### Outputs của ngày hôm nay

- Đọc được và phân tích `terraform.tfstate` file.
- Simulate và xử lý state drift thành công.
- Sử dụng được `state list`, `state show`, `state mv`, `state rm`, `state pull`.
- Hiểu rõ rủi ro security của state file.

### Prep cho Day 5 - Remote Backend

Day 5 sẽ implement remote state với S3 + DynamoDB:
- Tại sao local state không đủ cho team.
- Setup S3 bucket và DynamoDB table cho state backend.
- Migration từ local state sang remote state.
- State locking thực tế với DynamoDB.
- Workspace management với remote backend.
- `terraform_remote_state` data source để share outputs giữa các Terraform projects.

Trước Day 5, bạn nên có AWS account (free tier OK) và `aws` CLI đã configured.

---

## 8. Tham khảo thêm

- [Terraform State Documentation](https://developer.hashicorp.com/terraform/language/state) - Official docs
- [Sensitive Data in State](https://developer.hashicorp.com/terraform/language/state/sensitive-data) - Security considerations
- [State Command Reference](https://developer.hashicorp.com/terraform/cli/commands/state) - Tất cả state subcommands
- [Backends Overview](https://developer.hashicorp.com/terraform/language/settings/backends/configuration) - Remote backend types
- [Import](https://developer.hashicorp.com/terraform/cli/import) - Bring existing infra vào Terraform
- [Drift Detection blog](https://www.hashicorp.com/blog/terraform-0-15-4-improves-handling-of-configuration-drift) - refresh-only mode announcement
- [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) - Xóa secrets đã commit khỏi Git history
