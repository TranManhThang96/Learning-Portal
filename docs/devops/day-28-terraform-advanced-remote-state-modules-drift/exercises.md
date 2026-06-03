# Day 28: Exercises — Terraform Advanced

## Exercise 1: Easy — Module Basics

### Context

Team yêu cầu bạn refactor một Terraform configuration đang viết inline thành module để tái sử dụng cho nhiều environments.

### Yêu cầu

1. Tạo module `modules/webapp` với:
   - Input variables: `name`, `port`, `environment`, `image_tag`
   - Resources: Docker image + Docker container
   - Outputs: `container_name`, `container_id`, `url`

2. Sử dụng module trong root configuration để tạo 2 web apps:
   - App "frontend" trên port 8080
   - App "backend" trên port 8081

3. Verify:
   - `terraform state list` hiện module resources
   - Cả 2 apps accessible
   - Thay đổi variable → chỉ app tương ứng thay đổi

### Expected Outcome

```bash
terraform apply
# module.frontend.docker_container.app → port 8080
# module.backend.docker_container.app → port 8081

curl http://localhost:8080  # Frontend
curl http://localhost:8081  # Backend
```

### Hint

- Module source: `source = "./modules/webapp"`.
- Mỗi module instance có namespace riêng trong state.
- Module variable defaults giúp giảm boilerplate.

### Acceptance Criteria

- [ ] Module có variables.tf, main.tf, outputs.tf
- [ ] 2 module instances chạy đồng thời
- [ ] State hiện module path (`module.frontend.xxx`)
- [ ] `terraform destroy` cleanup sạch
- [ ] Module reusable (có thể tạo thêm instances)

### Bonus Challenge

Thêm variable `replicas` vào module sử dụng `count`, cho phép mỗi app có nhiều instances.

<details>
<summary>Solution</summary>

```hcl
# modules/webapp/variables.tf
variable "name" {
  type = string
}
variable "port" {
  type = number
}
variable "environment" {
  type    = string
  default = "dev"
}
variable "image_tag" {
  type    = string
  default = "alpine"
}

# modules/webapp/main.tf
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

resource "docker_image" "app" {
  name = "nginx:${var.image_tag}"
}

resource "docker_container" "app" {
  name  = "${var.name}-${var.environment}"
  image = docker_image.app.image_id
  ports {
    internal = 80
    external = var.port
  }
  upload {
    content = "server { listen 80; location / { return 200 '${var.name} (${var.environment})\\n'; add_header Content-Type text/plain; } }"
    file    = "/etc/nginx/conf.d/default.conf"
  }
  must_run = true
  restart  = "unless-stopped"
}

# modules/webapp/outputs.tf
output "container_name" { value = docker_container.app.name }
output "container_id" { value = docker_container.app.id }
output "url" { value = "http://localhost:${var.port}" }

# Root main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}
provider "docker" {}

module "frontend" {
  source      = "./modules/webapp"
  name        = "frontend"
  port        = 8080
  environment = "dev"
}

module "backend" {
  source      = "./modules/webapp"
  name        = "backend"
  port        = 8081
  environment = "dev"
}

output "frontend_url" { value = module.frontend.url }
output "backend_url" { value = module.backend.url }
```

</details>

---

## Exercise 2: Medium — Drift Detection & Resolution

### Context

Production infrastructure bị drift — ai đó modify Docker containers bằng CLI mà không qua Terraform. Bạn cần phát hiện và xử lý drift.

### Yêu cầu

1. Deploy infrastructure bằng Terraform (dùng Docker provider):
   - 1 network
   - 2 containers (web + redis)

2. Giả lập 3 loại drift:
   - **Drift 1**: Rename container bằng `docker rename`
   - **Drift 2**: Stop container bằng `docker stop`
   - **Drift 3**: Tạo container mới bằng `docker run` (resource ngoài Terraform)

3. Sau mỗi drift:
   - Chạy `terraform plan` → ghi lại output
   - Phân tích: Terraform sẽ làm gì?
   - Apply fix hoặc import resource mới bằng configuration-driven import nếu muốn Terraform quản lý resource đó

4. Viết drift detection script: chạy `terraform plan -detailed-exitcode` và alert khi có drift.

### Expected Outcome

```
Drift Report:
- Drift 1 (rename): Terraform detects container missing, recreates
- Drift 2 (stop): Terraform detects container stopped, restarts
- Drift 3 (new resource): Terraform doesn't see it (not in state)
  → Must import or remove manually
```

### Hint

- `terraform plan -detailed-exitcode`: exit code 2 = changes detected.
- `docker rename old new` thay đổi container name.
- Container ngoài Terraform không trong state → dùng `import` block nếu muốn manage trong Git/CI; `terraform import <resource_address> <resource_id>` là fallback thủ công.

### Acceptance Criteria

- [ ] 3 loại drift simulated thành công
- [ ] Plan output ghi lại cho mỗi drift type
- [ ] Drift resolved (apply hoặc import)
- [ ] Detection script functional
- [ ] Hiểu rõ Terraform handle mỗi drift type thế nào

### Bonus Challenge

Tạo scheduled drift check (cron job simulation) chạy plan mỗi phút và log kết quả.

<details>
<summary>Solution</summary>

**drift-check.sh:**
```bash
#!/bin/bash
set -euo pipefail

LOG_FILE="drift-report-$(date +%Y%m%d-%H%M%S).log"

echo "=== Drift Detection Report ===" | tee "$LOG_FILE"
echo "Time: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

terraform plan -detailed-exitcode -no-color 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

case $EXIT_CODE in
  0)
    echo "✅ No drift detected" | tee -a "$LOG_FILE"
    ;;
  1)
    echo "❌ Error running plan" | tee -a "$LOG_FILE"
    ;;
  2)
    echo "⚠️  DRIFT DETECTED — review plan output above" | tee -a "$LOG_FILE"
    echo "Action required: review and run 'terraform apply' to fix" | tee -a "$LOG_FILE"
    ;;
esac

echo "" | tee -a "$LOG_FILE"
echo "Report saved to: $LOG_FILE"
```

**Drift simulation steps:**
```bash
# Deploy
terraform apply -auto-approve

# Drift 1: Rename
docker rename tf-web-0 tf-web-RENAMED
terraform plan  # → recreate container (name changed)
terraform apply -auto-approve  # Fix

# Drift 2: Stop
docker stop tf-web-0
terraform plan  # → restart container (must_run = true)
terraform apply -auto-approve  # Fix

# Drift 3: External resource
docker run -d --name external-app nginx:alpine
terraform plan  # → No changes (not in state)
# Option 1: thêm import block cho docker_container.extra, rồi plan/apply saved plan đã review
# Or: docker rm -f external-app

# Cleanup
terraform destroy -auto-approve
```

</details>

---

## Exercise 3: Hard — Multi-environment Module Architecture

### Context

Bạn thiết kế Terraform architecture cho một SaaS platform cần 3 environments (dev, staging, prod) với shared modules. Mỗi environment có config khác nhau nhưng dùng chung codebase.

### Yêu cầu

1. Tạo directory structure:
   ```
   project/
   ├── modules/
   │   ├── webserver/    # NGINX containers
   │   └── cache/        # Redis containers
   ├── environments/
   │   ├── dev/          # 1 web, 1 redis, small
   │   └── prod/         # 3 web, 1 redis, large
   ```

2. Module requirements:
   - webserver: configurable replicas, ports, nginx version
   - cache: configurable maxmemory, port, redis version

3. Environment differences:

   | Config | Dev | Prod |
   |--------|-----|------|
   | Web replicas | 1 | 3 |
   | Redis maxmemory | 32mb | 256mb |
   | Web ports | 8080+ | 9080+ |
   | Redis port | 6380 | 6381 |

4. Deploy cả 2 environments đồng thời (different state files).

5. Thực hiện "production change" workflow:
   - Modify module (thêm health check)
   - Apply trên dev trước → verify
   - Apply trên prod → verify
   - Rollback nếu cần (revert code + apply)

### Expected Outcome

```bash
# Deploy dev
cd environments/dev && terraform apply
curl http://localhost:8080  # Dev web

# Deploy prod
cd environments/prod && terraform apply
curl http://localhost:9080  # Prod web-0
curl http://localhost:9081  # Prod web-1
curl http://localhost:9082  # Prod web-2

# Module change → deploy dev first → then prod
```

### Acceptance Criteria

- [ ] Module structure clean, reusable
- [ ] 2 environments run simultaneously
- [ ] State files separate per environment
- [ ] Module change workflow: dev → test → prod
- [ ] Rollback demonstrated
- [ ] All containers cleaned up properly

### Bonus Challenge

Thêm `terraform_remote_state` data source để prod environment đọc output từ dev environment (simulate cross-environment references).

<details>
<summary>Solution</summary>

Full solution follows the structure from the lesson's hands-on example. Key additions:

**environments/prod/main.tf:**
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}

provider "docker" {}

locals {
  environment = "prod"
  project     = "saas-platform"
  name_prefix = "${local.project}-${local.environment}"
}

resource "docker_network" "main" {
  name = "${local.name_prefix}-network"
}

module "webserver" {
  source       = "../../modules/webserver"
  name_prefix  = local.name_prefix
  environment  = local.environment
  replicas     = 3
  base_port    = 9080
  network_name = docker_network.main.name
}

module "cache" {
  source       = "../../modules/cache"
  name_prefix  = local.name_prefix
  environment  = local.environment
  maxmemory    = "256mb"
  port         = 6381
  network_name = docker_network.main.name
}

output "web_urls" { value = module.webserver.urls }
output "redis_endpoint" { value = module.cache.endpoint }
```

**Deployment script:**
```bash
#!/bin/bash
set -euo pipefail

deploy_env() {
  local env=$1
  echo "=== Deploying $env ==="
  cd "environments/$env"
  terraform init
  terraform apply -auto-approve
  terraform output
  cd ../..
}

destroy_env() {
  local env=$1
  echo "=== Destroying $env ==="
  cd "environments/$env"
  terraform destroy -auto-approve
  cd ../..
}

case ${1:-help} in
  deploy-all)  deploy_env dev && deploy_env prod ;;
  destroy-all) destroy_env prod && destroy_env dev ;;
  deploy)      deploy_env ${2:?env required} ;;
  destroy)     destroy_env ${2:?env required} ;;
  *) echo "Usage: $0 {deploy-all|destroy-all|deploy|destroy} [env]" ;;
esac
```

</details>

