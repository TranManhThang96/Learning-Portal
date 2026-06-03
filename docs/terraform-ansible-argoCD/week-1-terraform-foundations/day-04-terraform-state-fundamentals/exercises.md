# Day 4 - Exercises: Terraform State

> Thời gian ước tính: 60-90 phút ngoài lab chính.
> Làm trên local với Docker provider - không cần cloud account.

---

## Exercise 1: State Inspection Challenge

**Mục tiêu:** Đọc và trả lời câu hỏi từ state file thực tế.

### Setup

```hcl
# main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "docker" {}

resource "docker_image" "redis" {
  name         = "redis:alpine"
  keep_locally = true
}

resource "docker_image" "postgres" {
  name         = "postgres:15-alpine"
  keep_locally = true
}

resource "docker_container" "cache" {
  name  = "ex1-redis"
  image = docker_image.redis.image_id

  ports {
    internal = 6379
    external = 6379
  }

  env = [
    "REDIS_MAXMEMORY=256mb",
    "REDIS_MAXMEMORY_POLICY=allkeys-lru"
  ]
}

resource "docker_container" "db" {
  name  = "ex1-postgres"
  image = docker_image.postgres.image_id

  ports {
    internal = 5432
    external = 5432
  }

  env = [
    "POSTGRES_DB=appdb",
    "POSTGRES_USER=appuser",
    "POSTGRES_PASSWORD=changeme"
  ]
}

resource "local_file" "db_config" {
  filename = "${path.module}/db-config.json"
  content  = jsonencode({
    host = "localhost"
    port = 5432
    database = docker_container.db.name
  })
}

output "cache_port" {
  value = docker_container.cache.ports[0].external
}

output "db_connection" {
  value     = "postgresql://appuser:changeme@localhost:5432/appdb"
  sensitive = true
}
```

```bash
mkdir -p ~/tf-ex1 && cd ~/tf-ex1
# Tạo main.tf với nội dung trên
terraform init && terraform apply -auto-approve
```

### Câu hỏi (trả lời mà không Google, chỉ dùng state commands)

**Q1.1:** Liệt kê toàn bộ resource addresses trong state. Có bao nhiêu resource?

**Q1.2:** `serial` hiện tại là bao nhiêu? `lineage` là gì?

**Q1.3:** Docker image ID (sha256) của redis image là gì? Dùng `terraform state show`.

**Q1.4:** Output `db_connection` có value là gì? Tại sao `terraform output` không hiển thị trực tiếp? Làm cách nào để xem value?
```bash
terraform output db_connection        # output là gì?
terraform output -raw db_connection   # khác gì?
terraform output -json | jq .         # xem toàn bộ
```

**Q1.5:** File `db-config.json` có nội dung gì? Đây là resource type gì trong state?

**Q1.6:** `postgres` container có bao nhiêu biến môi trường trong state? Có password ở đó không? Bình luận về vấn đề bảo mật.

### Expected answers (tự verify)

```bash
# Q1.1
terraform state list | wc -l

# Q1.2
terraform state pull | jq '{serial, lineage}'

# Q1.3
terraform state show docker_image.redis | grep image_id

# Q1.4
terraform output -raw db_connection

# Q1.5
cat db-config.json  # check content
terraform state show local_file.db_config

# Q1.6
terraform state show docker_container.db | grep -A 5 env
```

### Cleanup
```bash
terraform destroy -auto-approve && cd ~ && rm -rf ~/tf-ex1
```

---

## Exercise 2: Drift Detection Scenarios

**Mục tiêu:** Nhận biết và xử lý 3 loại drift khác nhau theo cách phù hợp.

### Setup

```hcl
# main.tf
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

resource "docker_image" "nginx" {
  name         = "nginx:alpine"
  keep_locally = true
}

resource "docker_container" "frontend" {
  name  = "ex2-frontend"
  image = docker_image.nginx.image_id
  ports {
    internal = 80
    external = 3000
  }
}

resource "docker_container" "backend" {
  name  = "ex2-backend"
  image = docker_image.nginx.image_id
  ports {
    internal = 80
    external = 3001
  }
}

resource "docker_container" "worker" {
  name  = "ex2-worker"
  image = docker_image.nginx.image_id
  # Không expose port (background worker)
}
```

```bash
mkdir -p ~/tf-ex2 && cd ~/tf-ex2
terraform init && terraform apply -auto-approve
```

### Scenario 2.1 - Resource bị xóa ngoài Terraform

```bash
# Simulate: "ai đó" xóa worker container vì nghĩ nó đang idle
docker stop ex2-worker && docker rm ex2-worker
```

**Task:** 
1. Chạy `terraform plan` và đọc output. Terraform muốn làm gì?
2. Quyết định: Bạn muốn **giữ lại** worker container vì nó cần thiết. Chạy lệnh gì?
3. Verify container đang chạy lại.

**Trả lời vào file `scenario-2-1.md`:**
- Output của `terraform plan`
- Lệnh bạn chạy để fix
- Verify command và output

---

### Scenario 2.2 - Resource bị thay đổi ngoài Terraform (drift ta muốn giữ)

```bash
# Simulate: DevOps thay đổi port mapping của backend container
# (phải stop/remove/recreate vì Docker không cho thay đổi port khi đang chạy)
docker stop ex2-backend && docker rm ex2-backend
docker run -d --name ex2-backend -p 4000:80 nginx:alpine
```

**Context:** Team quyết định đổi port backend từ 3001 sang 4000. Thay đổi này đã được approve và cần cập nhật code Terraform để phản ánh.

**Task:**
1. Chạy `terraform plan -refresh-only` - xem drift được detect thế nào.
2. Đây là drift ta muốn **accept**. Nhưng nếu accept nguyên si, lần apply tiếp theo Terraform sẽ đổi lại 4000 → 3001.
3. Cách xử lý đúng: Cập nhật code `main.tf` để `external = 4000`, rồi chạy `terraform plan`. Kết quả?
4. Vấn đề gì xảy ra? Tại sao Terraform vẫn muốn destroy/recreate dù ta đã sửa code?

**Hint:** Docker container không support in-place update của port mapping. Terraform sẽ destroy và recreate. Đây là expected behavior, không phải bug.

---

### Scenario 2.3 - Auto-drift (acceptable drift)

**Context thực tế:** Trong production, một số resource thay đổi là tự nhiên và expected:
- Kubernetes pod restarts → container IDs thay đổi
- EC2 instance metadata thay đổi
- DNS record TTL

**Task lý thuyết (không cần chạy command):**

Viết câu trả lời cho các tình huống sau:

**2.3.a:** ECS task definition auto-updated minor container version. `terraform plan` show drift trên `image` attribute. Bạn muốn giữ image mới (đừng rollback). Lệnh gì?

**2.3.b:** Helm chart được upgrade tự động bởi Renovate bot → một số ConfigMap values thay đổi. Terraform (nếu manage Helm release) sẽ detect drift. Bạn muốn Terraform không bao giờ override Helm values cụ thể. Cách config trong Terraform?

**Hint 2.3.b:**
```hcl
resource "helm_release" "app" {
  ...
  lifecycle {
    ignore_changes = [values]  # hoặc specific paths
  }
}
```

### Cleanup
```bash
terraform destroy -auto-approve && cd ~ && rm -rf ~/tf-ex2
```

---

## Exercise 3: State Manipulation - Refactoring Challenge

**Mục tiêu:** Thực hành `terraform state mv` để refactor code mà không gây downtime.

### Context

Bạn có infrastructure hiện tại với resource naming convention cũ. Team quyết định migrate sang naming convention mới và đưa resources vào modules. Làm sao refactor mà không destroy/recreate bất kỳ container nào?

### Setup - Legacy infrastructure

```hcl
# main.tf (legacy naming)
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

# Legacy: flat structure, không có module
resource "docker_image" "img_nginx" {
  name         = "nginx:alpine"
  keep_locally = true
}

resource "docker_container" "svc_web_01" {
  name  = "ex3-web-01"
  image = docker_image.img_nginx.image_id
  ports { internal = 80; external = 7001 }
}

resource "docker_container" "svc_web_02" {
  name  = "ex3-web-02"
  image = docker_image.img_nginx.image_id
  ports { internal = 80; external = 7002 }
}

resource "docker_container" "svc_api" {
  name  = "ex3-api"
  image = docker_image.img_nginx.image_id
  ports { internal = 80; external = 7003 }
}
```

```bash
mkdir -p ~/tf-ex3 && cd ~/tf-ex3
# Tạo file main.tf với legacy code trên
terraform init && terraform apply -auto-approve
```

### Target - New structure

Mục tiêu cuối cùng là code như sau (tạo file `main_new.tf` để tham khảo, nhưng chưa apply):

```hcl
# Convention mới: bỏ prefix "svc_", bỏ "img_"
# Resource naming: <service>_<instance>

resource "docker_image" "nginx" {     # img_nginx → nginx
  name         = "nginx:alpine"
  keep_locally = true
}

resource "docker_container" "web" {   # svc_web_01 → web (dùng for_each)
  for_each = toset(["01", "02"])
  name     = "ex3-web-${each.key}"
  image    = docker_image.nginx.image_id
  ports {
    internal = 80
    external = each.key == "01" ? 7001 : 7002
  }
}

resource "docker_container" "api" {  # svc_api → api
  name  = "ex3-api"
  image = docker_image.nginx.image_id
  ports { internal = 80; external = 7003 }
}
```

### Task 3.1 - Plan the state migration

Trước khi làm bất cứ thứ gì, lên kế hoạch state migration:

Điền vào bảng (tự điền trước khi xem gợi ý):

| Source (old address) | Destination (new address) | Ghi chú |
|---------------------|--------------------------|---------|
| `docker_image.img_nginx` | ? | |
| `docker_container.svc_web_01` | ? | Chú ý: target dùng for_each |
| `docker_container.svc_web_02` | ? | |
| `docker_container.svc_api` | ? | |

**Gợi ý:** `for_each` với key "01" → address là `docker_container.web["01"]`

### Task 3.2 - Execute migration

```bash
# Bước 1: Backup state
terraform state pull > backup-before-migration.json

# Bước 2: Thực hiện state mv theo thứ tự
# (Điền các lệnh theo kế hoạch ở Task 3.1)
terraform state mv docker_image.img_nginx docker_image.nginx
terraform state mv docker_container.svc_web_01 'docker_container.web["01"]'
# ... tiếp tục

# Bước 3: Verify
terraform state list
```

Expected `terraform state list` sau migration:
```
docker_container.api
docker_container.web["01"]
docker_container.web["02"]
docker_image.nginx
```

### Task 3.3 - Update code và verify no recreation

```bash
# Thay thế main.tf bằng code mới (new structure)
# Sau đó:
terraform plan
```

Kết quả mong đợi:
```
No changes. Your infrastructure matches the configuration.
```

Nếu có changes, đọc kỹ output và fix. Common issues:
- Thiếu một `state mv` → Terraform muốn destroy cái cũ và create cái mới.
- Address không khớp chính xác (case, quotes).

### Task 3.4 - Verify containers vẫn chạy xuyên suốt

```bash
# Verify tất cả containers vẫn chạy (không có downtime!)
docker ps --filter "name=ex3"
# Expected: 4 containers (nginx image + 3 containers)

# Check health
curl http://localhost:7001  # web-01
curl http://localhost:7002  # web-02
curl http://localhost:7003  # api
```

### Cleanup
```bash
terraform destroy -auto-approve && cd ~ && rm -rf ~/tf-ex3
```

---

## Exercise 4: State Recovery Scenarios

**Mục tiêu:** Thực hành recover state trong các tình huống khẩn cấp.

### Scenario 4.1 - Orphaned resources

**Tình huống:** Colleague của bạn đã xóa file `terraform.tfstate` do nhầm. Resources vẫn đang chạy trên infrastructure.

**Setup:**
```bash
mkdir -p ~/tf-ex4 && cd ~/tf-ex4
```

```hcl
# main.tf
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

resource "docker_image" "app" {
  name         = "nginx:alpine"
  keep_locally = true
}

resource "docker_container" "app" {
  name  = "ex4-app"
  image = docker_image.app.image_id
  ports { internal = 80; external = 9090 }
}
```

```bash
terraform init && terraform apply -auto-approve

# Verify
docker ps --filter "name=ex4-app"

# Simulate: "ai đó" xóa state
rm terraform.tfstate

# Kiểm tra: không còn state
terraform state list  # Error: No state file found
```

**Task:**

1. Terraform plan sẽ cho kết quả gì? Chạy và đọc output.
2. Nếu run `terraform apply`, điều gì xảy ra? Tại sao nó lại fail?
3. Import container vào state để recover:

```bash
# Lấy container ID
CONTAINER_ID=$(docker inspect ex4-app --format '{{.Id}}')
echo $CONTAINER_ID

# Import vào state
terraform import docker_container.app $CONTAINER_ID
```

4. Sau import, chạy `terraform plan`. Có clean không?
5. Bạn cần import `docker_image.app` không? Tại sao / tại sao không? Thử:
```bash
IMAGE_ID=$(docker inspect ex4-app --format '{{.ImageID}}')
terraform import docker_image.app $IMAGE_ID
# Kết quả?
```

---

### Scenario 4.2 - State serialization conflict (simulation)

**Context:** Đây là scenario simulate việc state bị "stale" - bạn có state cũ hơn state hiện tại.

```bash
# Tạo backup của state hiện tại (version cũ hơn)
terraform state pull > old-state.json

# Apply một change nhỏ (tăng serial)
# Edit main.tf: thêm env variable vào container
# ...sau đó apply
terraform apply -auto-approve

# Kiểm tra serial mới
terraform state pull | jq .serial
cat old-state.json | jq .serial
# Serial hiện tại cao hơn old-state.json
```

**Task:**

1. Thử push state cũ lên:
```bash
terraform state push old-state.json
# Kết quả? Error message là gì?
```

2. Đọc error message. Tại sao Terraform chặn operation này?

3. Trong tình huống thực tế production, bạn cần push state cũ hơn (vì state hiện tại bị corrupt). Lệnh gì và rủi ro là gì?
```bash
# CHỈ DÙNG KHI THẬT SỰ CẦN THIẾT:
# terraform state push -force old-state.json
# Rủi ro: mất tất cả thay đổi từ sau old-state đến hiện tại
```

4. Sau `-force push`, chạy `terraform plan`. Kết quả nói lên điều gì?

### Cleanup
```bash
terraform destroy -auto-approve && cd ~ && rm -rf ~/tf-ex4
```

---

## Exercise 5: Security Audit

**Mục tiêu:** Tìm và catalog sensitive data trong state file.

### Setup

```hcl
# main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "app_secret_key" {
  type      = string
  default   = "this-is-a-fake-secret-for-lab-only"
  sensitive = true
}

variable "db_password" {
  type      = string
  default   = "FakeDbPassword123!"
  sensitive = true
}

resource "random_password" "api_key" {
  length  = 32
  special = true
}

resource "docker_image" "app" {
  name         = "nginx:alpine"
  keep_locally = true
}

resource "docker_container" "app" {
  name  = "ex5-app"
  image = docker_image.app.image_id

  env = [
    "APP_SECRET=${var.app_secret_key}",
    "DB_PASSWORD=${var.db_password}",
    "API_KEY=${random_password.api_key.result}"
  ]
}

resource "local_file" "app_config" {
  filename        = "${path.module}/app-secret-config.json"
  content         = jsonencode({
    secret_key = var.app_secret_key
    db_password = var.db_password
    api_key    = random_password.api_key.result
  })
  file_permission = "0600"
}

output "api_key" {
  value     = random_password.api_key.result
  sensitive = true
}

output "app_info" {
  value = {
    container_name = docker_container.app.name
    image          = docker_image.app.name
  }
  sensitive = false
}
```

```bash
mkdir -p ~/tf-ex5 && cd ~/tf-ex5
terraform init && terraform apply -auto-approve
```

### Task 5.1 - Audit state cho sensitive data

```bash
# Tìm tất cả string "password" trong state (case insensitive)
cat terraform.tfstate | jq . | grep -i password

# Tìm tất cả "secret" trong state
cat terraform.tfstate | jq . | grep -i secret

# Tìm env variables của container
cat terraform.tfstate | jq '.resources[] | select(.name == "app") | .instances[0].attributes.env'

# Tìm generated password từ random_password resource
cat terraform.tfstate | jq '.resources[] | select(.type == "random_password") | .instances[0].attributes'
```

**Task:** Điền vào bảng audit:

| Loại sensitive data | Nơi trong state | Có được encrypt không? | Rủi ro |
|--------------------|-----------------|----------------------|--------|
| db_password | `resources[].instances[].attributes.env[]` | ? | ? |
| app_secret_key | ? | ? | ? |
| api_key (random) | ? | ? | ? |

### Task 5.2 - Verify gitignore

```bash
# Kiểm tra .gitignore
cat .gitignore 2>/dev/null || echo "NO .gitignore!"

# Tạo .gitignore đúng cách
cat > .gitignore << 'EOF'
# Terraform state files - NEVER commit these
*.tfstate
*.tfstate.backup

# Terraform working directory
.terraform/

# Crash log files
crash.log
crash.*.log

# Generated secret configs
*-secret-config.json

# tfvars files (may contain secrets)
*.tfvars
*.tfvars.json

# BUT: lock file SHOULD be committed
!.terraform.lock.hcl
EOF

# Verify
git check-ignore -v terraform.tfstate  # Nếu là git repo
```

### Task 5.3 - Remediation recommendation

Viết ra (trong file `security-audit-result.md`) các biện pháp cụ thể để fix security issues tìm được:

1. Đối với `db_password` trong env vars: Thay thế bằng gì và how?
2. Đối với `random_password.api_key` trong state: Tại sao vẫn có rủi ro dù đã `sensitive = true` trong output? Biện pháp?
3. `local_file.app_config` chứa toàn bộ secrets trong một file JSON: Đây có phải là pattern tốt không? Alternative?

### Cleanup
```bash
terraform destroy -auto-approve
rm -f app-secret-config.json
cd ~ && rm -rf ~/tf-ex5
```

---

## Exercise 6: State Commands Speed Round

**Chạy nhanh, không setup phức tạp. Dùng lại infrastructure từ Exercise 1.**

```bash
mkdir -p ~/tf-ex6 && cd ~/tf-ex6
# Copy main.tf từ Exercise 1 vào đây
terraform init && terraform apply -auto-approve
```

**Trả lời các câu hỏi chỉ bằng `terraform state` commands (không dùng `cat`, không dùng `jq`):**

```bash
# Q6.1: Image ID của postgres container là gì?
# Hint: terraform state show ...

# Q6.2: Có bao nhiêu instances của resource "docker_image" trong state?
# Hint: terraform state list | ...

# Q6.3: Resource nào phụ thuộc vào docker_image.redis?
# Hint: terraform state show docker_container.cache | grep ...

# Q6.4: Move resource docker_container.cache thành docker_container.redis_cache
terraform state mv docker_container.cache docker_container.redis_cache

# Q6.5: Verify list sau khi mv
terraform state list

# Q6.6: Restore lại (mv ngược)
terraform state mv docker_container.redis_cache docker_container.cache

# Q6.7: Pull state và count số resources
terraform state pull | jq '.resources | length'

# Q6.8: Tìm resource nào có name = "ex1-postgres" trong state
terraform state pull | jq '.resources[] | select(.instances[0].attributes.name == "ex1-postgres") | .type + "." + .name'
```

### Cleanup
```bash
terraform destroy -auto-approve && cd ~ && rm -rf ~/tf-ex6
```

---

## Bonus Challenge: Multi-state Coordination

**Dành cho ai muốn thêm challenge. Thời gian: ~30 phút.**

### Context

Trong thực tế, bạn sẽ có nhiều Terraform projects với separate states, và chúng cần share information. Pattern phổ biến: infrastructure project export VPC ID, application project consume nó.

### Task

```bash
mkdir -p ~/tf-infra ~/tf-app
```

**Project 1 (infra):**
```hcl
# ~/tf-infra/main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    local = { source = "hashicorp/local"; version = "~> 2.0" }
  }
}

resource "local_file" "shared_config" {
  filename = "${path.module}/shared-config.json"
  content = jsonencode({
    environment = "lab"
    network_id  = "net-001"
    api_endpoint = "http://internal-api:8080"
  })
}

output "network_id" {
  value = "net-001"
}

output "api_endpoint" {
  value = "http://internal-api:8080"
}
```

**Project 2 (app) - sử dụng state của infra:**
```hcl
# ~/tf-app/main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    local = { source = "hashicorp/local"; version = "~> 2.0" }
  }
}

# Đọc output từ state của project khác
data "terraform_remote_state" "infra" {
  backend = "local"
  config = {
    path = "${path.module}/../tf-infra/terraform.tfstate"
  }
}

resource "local_file" "app_config" {
  filename = "${path.module}/app-config.json"
  content = jsonencode({
    app_name     = "my-app"
    network_id   = data.terraform_remote_state.infra.outputs.network_id
    api_endpoint = data.terraform_remote_state.infra.outputs.api_endpoint
  })
}

output "app_config_path" {
  value = local_file.app_config.filename
}
```

**Task:**
1. Init và apply infra project trước.
2. Init và apply app project.
3. Xem `app-config.json` - nó lấy values từ infra state đúng không?
4. Thay đổi `network_id` trong infra project, apply. Rồi plan app project. Điều gì xảy ra?
5. Đây là pattern `terraform_remote_state`. Pros và cons của pattern này so với hardcode values?

```bash
# Cleanup
cd ~/tf-app && terraform destroy -auto-approve
cd ~/tf-infra && terraform destroy -auto-approve
cd ~ && rm -rf ~/tf-infra ~/tf-app
```

---

## Tự đánh giá kết quả

Sau khi hoàn thành exercises, bạn nên trả lời được:

- [ ] Tôi có thể đọc `terraform.tfstate` và hiểu ý nghĩa của từng field chính.
- [ ] Tôi phân biệt được khi nào nên dùng `apply -refresh-only` vs `apply` để xử lý drift.
- [ ] Tôi có thể rename resource trong code mà không gây downtime bằng `state mv`.
- [ ] Tôi biết cách recover khi state bị xóa nhầm bằng `terraform import`.
- [ ] Tôi hiểu sensitive data trong state là risk thật sự, không phải lý thuyết.
- [ ] Tôi biết `terraform_remote_state` data source để share state giữa projects.

Nếu còn yếu ở điểm nào, quay lại lesson.md phần tương ứng và đọc lại trước khi sang Day 5.
