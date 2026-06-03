# Day 1 — Additional Exercises

> **Mức độ:** Tăng dần từ Exercise 1 (easy) đến Exercise 5 (hard)
> **Prerequisite:** Hoàn thành lab chính trong lesson.md

---

## Exercise 1 — Thêm container thứ hai (Easy)

**Mục tiêu:** Thực hành thêm resource vào existing configuration, quan sát plan.

**Yêu cầu:**
Thêm một container Redis vào project Docker từ lab chính. Redis container phải:
- Dùng image `redis:7-alpine`
- Expose port `6379` ra host port `6379`
- Nằm cùng network `lab_network` với nginx container
- Có label `managed-by=terraform`

**Hint:**
```hcl
# Tìm Docker image ID cho redis trong Terraform Registry
# resource type: docker_image, docker_container
# Tham khảo: https://registry.terraform.io/providers/kreuzwerker/docker/latest/docs
```

**Expected outcome:**
```bash
terraform plan
# Plan: 2 to add, 0 to change, 0 to destroy.
# (1 image + 1 container)

terraform apply
docker ps
# Phải thấy cả nginx container và redis container
```

**Câu hỏi sau khi làm:**
- Terraform tạo nginx và redis theo thứ tự nào? Song song hay tuần tự?
- Nếu nginx và redis không phụ thuộc nhau, Terraform làm gì để optimize?

---

## Exercise 2 — Sử dụng `for_each` tạo multiple containers (Medium)

**Mục tiêu:** Hiểu cách `for_each` hoạt động, so sánh với `count`.

**Yêu cầu:**
Refactor project để tạo 3 nginx containers cùng lúc bằng `for_each`, thay vì tạo từng container riêng lẻ. Mỗi container phải có port khác nhau.

**Starting structure:**
```hcl
# variables.tf
variable "web_servers" {
  description = "Map of web server configs"
  type = map(object({
    host_port = number
    env_name  = string
  }))
  default = {
    "web-1" = { host_port = 8081, env_name = "dev-1" }
    "web-2" = { host_port = 8082, env_name = "dev-2" }
    "web-3" = { host_port = 8083, env_name = "dev-3" }
  }
}
```

**Yêu cầu thêm:**
- Output phải list URLs của tất cả containers
- Đặt tên container theo key của map: `nginx-web-1`, `nginx-web-2`, `nginx-web-3`

**Hint về output:**
```hcl
output "all_urls" {
  value = {
    for name, config in var.web_servers :
    name => "http://localhost:${config.host_port}"
  }
}
```

**Câu hỏi sau khi làm:**
- Nếu bạn thêm `"web-4"` vào map, Terraform sẽ làm gì với 3 containers đang có?
- Nếu bạn xóa `"web-2"` khỏi map, container `web-2` bị ảnh hưởng thế nào?
- So sánh `for_each` với `count`: khi nào dùng cái nào?

---

## Exercise 3 — Local Values và conditional resources (Medium)

**Mục tiêu:** Sử dụng `locals`, conditional expressions, và `count = 0/1` pattern.

**Scenario:**
Bạn có một app cần thêm một container monitoring (Prometheus) chỉ khi môi trường là `production`. Ở `dev` và `staging` thì không cần.

**Yêu cầu:**
1. Thêm variable `enable_monitoring` với type `bool`, default `false`
2. Dùng `count = var.enable_monitoring ? 1 : 0` để create/skip Prometheus container
3. Dùng `locals` để tính toán các giá trị derived: memory limit, CPU limit theo environment

```hcl
locals {
  # Production: limit cao hơn
  # Dev/staging: limit thấp hơn để tiết kiệm tài nguyên
  memory_limit = var.environment == "production" ? 512 : 128
  cpu_shares   = var.environment == "production" ? 1024 : 256
}
```

4. Apply Docker resource limits thực sự:
```hcl
resource "docker_container" "web" {
  # ...
  memory    = local.memory_limit   # MB
  cpu_shares = local.cpu_shares
}
```

**Test flow:**
```bash
# Test với monitoring disabled (default)
terraform apply
docker ps   # Chỉ có nginx (và redis nếu còn từ exercise 1)

# Test với monitoring enabled
terraform apply -var="enable_monitoring=true"
docker ps   # Phải thấy thêm prometheus container
```

**Câu hỏi sau khi làm:**
- Khi switch `enable_monitoring` từ `false` sang `true`, Terraform làm gì với các resources hiện có?
- Tại sao pattern `count = condition ? 1 : 0` lại phổ biến hơn là dùng `dynamic` block ở đây?

---

## Exercise 4 — Import existing Docker resource vào Terraform state (Hard)

**Mục tiêu:** Hiểu `terraform import` — workflow thực tế khi có existing infrastructure.

**Scenario:**
Ai đó đã tạo một Docker container bằng tay (không dùng Terraform). Bạn cần "adopt" container này vào Terraform management.

**Bước 1: Tạo container "bằng tay"**
```bash
docker run -d \
  --name manual-nginx \
  -p 9999:80 \
  -l "created-by=manual" \
  nginx:1.25-alpine
```

**Bước 2: Viết resource block**
Trong `main.tf`, thêm resource block mô tả container này:
```hcl
resource "docker_container" "manual" {
  name  = "manual-nginx"
  image = docker_image.nginx.image_id    # Reuse image đã có
  ports {
    internal = 80
    external = 9999
  }
}
```

**Bước 3: Thử plan trước khi import**
```bash
terraform plan
# Terraform sẽ muốn TẠO MỚI container này!
# Nhưng nó đã tồn tại → sẽ bị lỗi khi apply
```

**Bước 4: Import**
```bash
# Lấy container ID
docker inspect manual-nginx --format='{{.Id}}'

# Import vào state
terraform import docker_container.manual <CONTAINER_ID>
```

**Bước 5: Plan sau import**
```bash
terraform plan
# Bây giờ Terraform biết container đã tồn tại
# Sẽ thấy diff nếu có thuộc tính không match
```

**Bước 6: Reconcile**
Sửa resource block để match với actual container config. Chạy plan cho đến khi thấy:
```
No changes. Your infrastructure matches the configuration.
```

**Câu hỏi sau khi làm:**
- Tại sao `terraform import` không tự generate code cho bạn? (Lý do lịch sử và kỹ thuật)
- Terraform 1.5+ có feature gì mới giúp workflow import dễ hơn?
- Khi nào bạn sẽ dùng import trong thực tế?

---

## Exercise 5 — Multi-container Stack với Data Sources (Hard)

**Mục tiêu:** Kết hợp nhiều concepts: data sources, depends_on, local-exec provisioner, complex outputs.

**Scenario:**
Xây dựng một minimal web stack: Nginx (reverse proxy) + một app container. Nginx config phải biết hostname của app container.

**Yêu cầu:**

**Phần 1: Tạo "app" container**
```hcl
resource "docker_container" "app" {
  name  = "${local.app_prefix}-app"
  image = docker_image.nginx.image_id    # Giả lập app bằng nginx khác
  networks_advanced {
    name = docker_network.lab_network.name
  }
  # Không expose port ra ngoài — chỉ accessible trong internal network
}
```

**Phần 2: Dùng data source để lấy container info**
```hcl
data "docker_network" "lab_network" {
  name = docker_network.lab_network.name

  depends_on = [docker_network.lab_network]
}
```

**Phần 3: Output phức tạp**
```hcl
output "stack_info" {
  description = "Thông tin về toàn bộ stack"
  value = {
    proxy_url    = "http://localhost:${var.host_port}"
    app_internal = "${docker_container.app.name}:80"
    network      = docker_network.lab_network.name
    containers   = [
      docker_container.web.name,
      docker_container.app.name
    ]
    total_count  = 2
  }
}
```

**Phần 4: `null_resource` với `local-exec` provisioner**

Sau khi tất cả containers lên, chạy một health check script:
```hcl
resource "null_resource" "health_check" {
  depends_on = [docker_container.web, docker_container.app]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for nginx to start..."
      sleep 3
      curl -f http://localhost:${var.host_port} > /dev/null 2>&1 && \
        echo "Health check PASSED" || \
        echo "Health check FAILED"
    EOT
  }

  # Trigger re-run nếu container ID thay đổi
  triggers = {
    web_container_id = docker_container.web.id
    app_container_id = docker_container.app.id
  }
}
```

**Yêu cầu thêm:**
- Thêm provider `null` vào `required_providers`
- Toàn bộ stack phải apply thành công với health check pass

**Câu hỏi sau khi làm:**
- `null_resource` với `local-exec` có phải là best practice không? Khi nào nên dùng?
- Nếu health check fail, Terraform có rollback không? Tại sao?
- `triggers` trong `null_resource` hoạt động như thế nào?

---

## Bonus Challenge — Terraform State Surgery

**Chỉ dành cho người muốn hiểu sâu về state internals.**

**Scenario:** Bạn cần rename một resource trong code (refactor) mà không destroy và recreate nó.

```hcl
# Trước
resource "docker_container" "web" { ... }

# Sau refactor
resource "docker_container" "nginx_proxy" { ... }
```

Nếu chỉ đổi tên trong code rồi apply, Terraform sẽ destroy `web` và create `nginx_proxy` — downtime!

**Yêu cầu:**
1. Rename resource trong code từ `docker_container.web` sang `docker_container.nginx_proxy`
2. Dùng `terraform state mv` để migrate state mà không destroy container
3. Verify với `terraform plan` — phải thấy `No changes`

```bash
# State surgery command
terraform state mv docker_container.web docker_container.nginx_proxy

# Verify
terraform state list
# docker_container.nginx_proxy  <- tên mới trong state

terraform plan
# No changes. Your infrastructure matches the configuration.
```

**Câu hỏi:**
- Nếu quên chạy `state mv` mà chỉ đổi tên trong code, plan sẽ output gì?
- Có tool nào giúp automate state rename không? (Research: `moved` block trong Terraform 1.1+)
- `moved` block khác gì `terraform state mv`? Khi nào dùng cái nào?

---

## Checklist tự đánh giá

Sau khi hoàn thành các exercises, bạn nên có thể:

- [ ] Tạo và manage multiple resources với dependencies
- [ ] Dùng `for_each` với map để tạo nhiều instances
- [ ] Dùng `locals` để compute derived values
- [ ] Dùng conditional `count` để enable/disable resources
- [ ] Import existing resources vào Terraform state
- [ ] Thực hiện state surgery với `terraform state mv`
- [ ] Giải thích dependency graph và thứ tự tạo resources
- [ ] Phân biệt khi nào cần `depends_on` explicit vs implicit
