# Day 27: Exercises — Terraform Fundamentals

## Exercise 1: Easy — Terraform Basics với Local Provider

### Context

Bạn được giao task đầu tiên với Terraform: quản lý configuration files bằng IaC thay vì tạo thủ công. Dùng `local` provider (không cần cloud account).

### Yêu cầu

1. Tạo Terraform project quản lý các config files sau:
   - `/tmp/terraform-lab/app/config.json` — chứa JSON config cho application
   - `/tmp/terraform-lab/app/env.txt` — chứa environment variables
   - `/tmp/terraform-lab/nginx/nginx.conf` — chứa NGINX configuration

2. Sử dụng:
   - `variable` cho environment name (dev/staging/prod)
   - `locals` cho computed values
   - `output` hiển thị đường dẫn files đã tạo
   - `local_file` resource

3. Config content phải thay đổi theo environment:
   - dev: debug=true, log_level=debug
   - staging: debug=false, log_level=info
   - prod: debug=false, log_level=warn

### Expected Outcome

```bash
terraform apply -var="environment=dev"
# Creates 3 files with dev-specific content

terraform apply -var="environment=prod"
# Updates 3 files with prod-specific content

terraform plan
# No changes (idempotent)
```

### Hint

- Dùng `templatefile()` hoặc `heredoc` cho multi-line content.
- Dùng conditional: `var.environment == "prod" ? "warn" : "debug"`.
- `local_file` resource từ `hashicorp/local` provider.

### Acceptance Criteria

- [ ] 3 files được tạo đúng theo environment
- [ ] Thay đổi environment → files update tương ứng
- [ ] Apply lần 2 → "No changes"
- [ ] `terraform destroy` xóa sạch files
- [ ] Code có variables, locals, outputs

### Bonus Challenge

Thêm `validation` block cho variable `environment` — chỉ chấp nhận dev/staging/prod.

<details>
<summary>Solution</summary>

```hcl
# providers.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

# variables.tf
variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# locals.tf
locals {
  base_dir = "/tmp/terraform-lab"
  
  env_config = {
    dev = {
      debug     = true
      log_level = "debug"
      replicas  = 1
    }
    staging = {
      debug     = false
      log_level = "info"
      replicas  = 2
    }
    prod = {
      debug     = false
      log_level = "warn"
      replicas  = 3
    }
  }

  config = local.env_config[var.environment]
}

# main.tf
resource "local_file" "app_config" {
  filename = "${local.base_dir}/app/config.json"
  content = jsonencode({
    environment = var.environment
    debug       = local.config.debug
    log_level   = local.config.log_level
    replicas    = local.config.replicas
    version     = "1.0.0"
  })
}

resource "local_file" "env_file" {
  filename = "${local.base_dir}/app/env.txt"
  content  = <<-EOT
    ENVIRONMENT=${var.environment}
    DEBUG=${local.config.debug}
    LOG_LEVEL=${local.config.log_level}
    REPLICAS=${local.config.replicas}
  EOT
}

resource "local_file" "nginx_config" {
  filename = "${local.base_dir}/nginx/nginx.conf"
  content  = <<-EOT
    worker_processes auto;
    error_log /var/log/nginx/error.log ${local.config.log_level == "debug" ? "debug" : "warn"};
    
    http {
      access_log ${local.config.debug ? "/var/log/nginx/access.log" : "off"};
      
      upstream app {
        %{for i in range(local.config.replicas)}
        server app-${i}:8080;
        %{endfor}
      }
      
      server {
        listen 80;
        location / {
          proxy_pass http://app;
        }
      }
    }
  EOT
}

# outputs.tf
output "created_files" {
  value = [
    local_file.app_config.filename,
    local_file.env_file.filename,
    local_file.nginx_config.filename,
  ]
}

output "environment" {
  value = var.environment
}
```

</details>

---

## Exercise 2: Medium — Docker Infrastructure với Terraform

### Context

Team của bạn cần một development environment gồm NGINX reverse proxy + Redis cache, quản lý hoàn toàn bằng Terraform. Dùng Docker provider.

### Yêu cầu

1. Tạo Terraform project quản lý:
   - Docker network riêng
   - NGINX container (reverse proxy)
   - Redis container (cache)
   - Custom NGINX config route `/api` → thông báo, `/cache` → thông báo

2. Sử dụng:
   - Variables cho port mapping, image versions
   - Outputs cho container IPs, ports, access URLs
   - Health checks cho cả 2 containers
   - Labels cho tất cả resources
   - `count` hoặc `for_each` nếu phù hợp

3. Verification:
   - `curl http://localhost:<port>` trả về response
   - `docker ps` hiện 2 containers với labels
   - `terraform state list` hiện tất cả resources

### Expected Outcome

```bash
terraform apply
# Creates: 1 network, 2 images, 2 containers
# Output shows access URLs

curl http://localhost:8080
# Returns NGINX page

terraform state list
# docker_container.nginx
# docker_container.redis
# docker_image.nginx
# docker_image.redis
# docker_network.app
```

### Hint

- Docker provider: `kreuzwerker/docker`.
- Redis image: `redis:7-alpine`.
- NGINX cần `upload` block hoặc `volumes` cho custom config.
- Health check: `["CMD", "redis-cli", "ping"]` cho Redis.

### Acceptance Criteria

- [ ] 2 containers chạy trên cùng Docker network
- [ ] NGINX accessible qua browser/curl
- [ ] Redis có health check
- [ ] Outputs hiện URLs và container info
- [ ] Labels present trên tất cả resources
- [ ] `terraform destroy` cleanup sạch

### Bonus Challenge

Thêm container thứ 3: một simple web app (dùng `hashicorp/http-echo`) proxy qua NGINX.

<details>
<summary>Solution</summary>

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

provider "docker" {}

# variables.tf
variable "nginx_port" {
  type    = number
  default = 8080
}

variable "redis_port" {
  type    = number
  default = 6379
}

variable "project_name" {
  type    = string
  default = "tf-lab"
}

# locals.tf
locals {
  common_labels = {
    "managed-by" = "terraform"
    "project"    = var.project_name
  }
}

# main.tf
resource "docker_network" "app" {
  name = "${var.project_name}-network"
}

resource "docker_image" "nginx" {
  name         = "nginx:alpine"
  keep_locally = false
}

resource "docker_image" "redis" {
  name         = "redis:7-alpine"
  keep_locally = false
}

resource "docker_container" "nginx" {
  name  = "${var.project_name}-nginx"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = var.nginx_port
  }

  networks_advanced {
    name = docker_network.app.name
  }

  dynamic "labels" {
    for_each = local.common_labels
    content {
      label = labels.key
      value = labels.value
    }
  }

  labels {
    label = "service"
    value = "nginx"
  }

  upload {
    content = <<-EOT
      server {
        listen 80;
        location / {
          return 200 "NGINX is running. Routes: /api, /cache\n";
          add_header Content-Type text/plain;
        }
        location /api {
          return 200 "API endpoint - managed by Terraform\n";
          add_header Content-Type text/plain;
        }
        location /cache {
          return 200 "Cache info: Redis at ${var.project_name}-redis:6379\n";
          add_header Content-Type text/plain;
        }
        location /health {
          access_log off;
          return 200 "healthy\n";
        }
      }
    EOT
    file    = "/etc/nginx/conf.d/default.conf"
  }

  healthcheck {
    test     = ["CMD", "curl", "-f", "http://localhost/health"]
    interval = "10s"
    timeout  = "5s"
    retries  = 3
  }

  restart  = "unless-stopped"
  must_run = true
}

resource "docker_container" "redis" {
  name  = "${var.project_name}-redis"
  image = docker_image.redis.image_id

  ports {
    internal = 6379
    external = var.redis_port
  }

  networks_advanced {
    name = docker_network.app.name
  }

  dynamic "labels" {
    for_each = local.common_labels
    content {
      label = labels.key
      value = labels.value
    }
  }

  labels {
    label = "service"
    value = "redis"
  }

  healthcheck {
    test     = ["CMD", "redis-cli", "ping"]
    interval = "10s"
    timeout  = "5s"
    retries  = 3
  }

  restart  = "unless-stopped"
  must_run = true
}

# outputs.tf
output "nginx_url" {
  value = "http://localhost:${var.nginx_port}"
}

output "redis_endpoint" {
  value = "localhost:${var.redis_port}"
}

output "containers" {
  value = {
    nginx = {
      name = docker_container.nginx.name
      id   = docker_container.nginx.id
    }
    redis = {
      name = docker_container.redis.name
      id   = docker_container.redis.id
    }
  }
}

output "network" {
  value = docker_network.app.name
}
```

**Verification:**

```bash
terraform init && terraform apply -auto-approve
curl http://localhost:8080
curl http://localhost:8080/api
curl http://localhost:8080/cache
curl http://localhost:8080/health
docker ps --filter "label=managed-by=terraform"
terraform state list
terraform destroy -auto-approve
```

</details>

---

## Exercise 3: Hard — Multi-environment Docker Stack

### Context

Bạn cần thiết kế Terraform configuration cho development stack có thể deploy nhiều environments trên cùng máy (dev, staging). Mỗi environment có isolated network, ports khác nhau, và resource configs khác nhau.

### Yêu cầu

1. Tạo Terraform project hỗ trợ **multiple environments** trên cùng máy:
   - Mỗi environment: NGINX + Redis + app network
   - Port ranges: dev (8080-8089), staging (8090-8099)
   - Network isolated giữa environments

2. Sử dụng **Terraform workspaces** để quản lý environments:
   ```bash
   terraform workspace new dev
   terraform workspace new staging
   terraform workspace select dev && terraform apply
   terraform workspace select staging && terraform apply
   ```

3. Tạo `.tfvars` files cho mỗi environment:
   - `dev.tfvars` — small resources, debug enabled
   - `staging.tfvars` — medium resources, debug disabled

4. Viết script `manage.sh` để:
   - Deploy một environment: `./manage.sh deploy dev`
   - Destroy một environment: `./manage.sh destroy staging`
   - Status: `./manage.sh status`
   - Destroy all: `./manage.sh destroy-all`

### Expected Outcome

```bash
./manage.sh deploy dev
# Creates dev stack on ports 8080+

./manage.sh deploy staging
# Creates staging stack on ports 8090+

./manage.sh status
# Shows both environments running

curl http://localhost:8080  # dev nginx
curl http://localhost:8090  # staging nginx

./manage.sh destroy-all
# Cleans up everything
```

### Hint

- `terraform.workspace` cho current workspace name.
- Port offset: `var.base_port + index`.
- workspace = lightweight environment isolation.
- Script dùng `terraform workspace select` + `apply/destroy`.

### Acceptance Criteria

- [ ] 2 environments chạy đồng thời, isolated
- [ ] Ports không conflict
- [ ] Networks isolated
- [ ] Workspace switching hoạt động
- [ ] manage.sh script functional
- [ ] `destroy-all` cleanup sạch tất cả
- [ ] Idempotent — deploy lại không thay đổi

### Bonus Challenge

Thêm `terraform output -json` vào script để tự động detect ports và URLs cho mỗi environment.

<details>
<summary>Solution</summary>

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

provider "docker" {}

# variables.tf
variable "base_port" {
  type = number
}

variable "debug" {
  type    = bool
  default = false
}

variable "redis_maxmemory" {
  type    = string
  default = "64mb"
}

# locals.tf
locals {
  env     = terraform.workspace
  project = "multi-env-${local.env}"
}

# main.tf
resource "docker_network" "app" {
  name = "${local.project}-net"
}

resource "docker_image" "nginx" {
  name = "nginx:alpine"
}

resource "docker_image" "redis" {
  name = "redis:7-alpine"
}

resource "docker_container" "nginx" {
  name  = "${local.project}-nginx"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = var.base_port
  }

  networks_advanced {
    name = docker_network.app.name
  }

  upload {
    content = <<-EOT
      server {
        listen 80;
        location / {
          return 200 "Environment: ${local.env}\nDebug: ${var.debug}\n";
          add_header Content-Type text/plain;
        }
        location /health {
          return 200 "ok";
        }
      }
    EOT
    file = "/etc/nginx/conf.d/default.conf"
  }

  restart  = "unless-stopped"
  must_run = true
}

resource "docker_container" "redis" {
  name  = "${local.project}-redis"
  image = docker_image.redis.image_id
  
  command = ["redis-server", "--maxmemory", var.redis_maxmemory]

  ports {
    internal = 6379
    external = var.base_port + 1
  }

  networks_advanced {
    name = docker_network.app.name
  }

  restart  = "unless-stopped"
  must_run = true
}

# outputs.tf
output "environment" {
  value = local.env
}

output "nginx_url" {
  value = "http://localhost:${var.base_port}"
}

output "redis_port" {
  value = var.base_port + 1
}
```

**dev.tfvars:**
```hcl
base_port       = 8080
debug           = true
redis_maxmemory = "32mb"
```

**staging.tfvars:**
```hcl
base_port       = 8090
debug           = false
redis_maxmemory = "128mb"
```

**manage.sh:**
```bash
#!/bin/bash
set -euo pipefail

ACTION=${1:-help}
ENV=${2:-}

deploy() {
  local env=$1
  echo "=== Deploying $env ==="
  terraform workspace select "$env" 2>/dev/null || terraform workspace new "$env"
  terraform apply -var-file="${env}.tfvars" -auto-approve
  echo "=== $env deployed ==="
  terraform output
}

destroy_env() {
  local env=$1
  echo "=== Destroying $env ==="
  terraform workspace select "$env" 2>/dev/null || { echo "Workspace $env not found"; exit 1; }
  terraform destroy -var-file="${env}.tfvars" -auto-approve
  terraform workspace select default
  terraform workspace delete "$env" 2>/dev/null || true
  echo "=== $env destroyed ==="
}

status() {
  echo "=== Terraform Workspaces ==="
  terraform workspace list
  echo ""
  for ws in $(terraform workspace list | tr -d ' *'); do
    if [ "$ws" != "default" ]; then
      echo "--- $ws ---"
      terraform workspace select "$ws" 2>/dev/null
      terraform output 2>/dev/null || echo "  No resources"
    fi
  done
  terraform workspace select default 2>/dev/null
}

case $ACTION in
  deploy)
    [ -z "$ENV" ] && { echo "Usage: $0 deploy <env>"; exit 1; }
    deploy "$ENV"
    ;;
  destroy)
    [ -z "$ENV" ] && { echo "Usage: $0 destroy <env>"; exit 1; }
    destroy_env "$ENV"
    ;;
  destroy-all)
    for ws in $(terraform workspace list | tr -d ' *'); do
      if [ "$ws" != "default" ]; then
        destroy_env "$ws"
      fi
    done
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: $0 {deploy|destroy|destroy-all|status} [env]"
    ;;
esac
```

```bash
chmod +x manage.sh
terraform init
./manage.sh deploy dev
./manage.sh deploy staging
./manage.sh status
curl http://localhost:8080
curl http://localhost:8090
./manage.sh destroy-all
```

</details>

