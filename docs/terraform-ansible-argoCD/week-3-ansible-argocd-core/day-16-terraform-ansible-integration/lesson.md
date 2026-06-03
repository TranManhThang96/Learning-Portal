# Day 16 - Terraform + Ansible Integration

**Thời lượng:** 2 tiếng
**Prerequisites:** Day 13 (Ansible basics, hardening.yml), Day 14 (Jinja2 templates, handlers), Day 15 (Ansible roles, Vault, dynamic inventory aws_ec2.yml), Week 1-2 (Terraform state, modules, remote backend)
**Kết quả đầu ra:** Terraform module bastion + Ansible role bastion-hardening + dynamic inventory + ADR document

---

## 1. Mục tiêu ngày học

Sau ngày học, học viên có khả năng:

- Quyết định chính xác khi nào ghép Terraform với Ansible và khi nào dùng cloud-init / Packer / SSM thay thế, dựa trên context cụ thể của hệ thống
- Generate dynamic inventory từ `terraform output -json` mà không hard-code IP, tránh được configuration drift do manual entry
- Hardening bastion host bằng Ansible role tái sử dụng `node_exporter` từ Day 15 và role `bastion-hardening` mới
- Phân tích trade-off đầy đủ (cost, security, operability, performance) giữa 5 approach config server và viết ADR cho team
- Debug dynamic inventory khi host không xuất hiện (3 nguyên nhân phổ biến: tag missing, IAM permission, region mismatch)
- Tránh anti-pattern `local-exec` provisioner gọi `ansible-playbook` trong production pipeline

---

## 2. Bối cảnh thực tế

### 2.1. Hai anti-pattern phổ biến trong thực tế

**Anti-pattern A: Terraform-only team**

Team chỉ dùng Terraform, server provision xong nhưng OS configuration stale:

```
Terraform apply → EC2 created → SSH manually → apt install nginx → DONE
```

Kết quả sau 3 tháng:
- 30% server drift khỏi golden config
- Không ai biết server nào đang chạy đúng phiên bản nginx
- Security patch không được apply đồng nhất
- Onboarding engineer mất 2 ngày để hiểu current state

**Anti-pattern B: Ansible-only team**

Team chỉ dùng Ansible, nhưng không quản lý được infrastructure lifecycle:

```
ansible-playbook → runs on 10.0.1.5 → works great
```

Sau đó:
- Terraform engineer chạy `terraform apply` thay đổi subnet → IP 10.0.1.5 biến mất
- Không ai có record server nào được provision bởi cái gì
- Disaster recovery không rõ ràng
- Cost explosion vì không ai biết có bao nhiêu "phantom" server

### 2.2. Microservices context: bastion host + worker pool + observability

Trong kiến trúc microservices production:

```
Internet → ALB → ECS/EKS Worker Nodes
                ↘ Bastion Host (jump box)
                ↘ Prometheus (node_exporter on every node)
                ↘ Vault / Secrets Manager
```

- **Bastion host**: SSH entry point duy nhất, phải hardened cao, không chạy app workload
- **Worker nodes**: Auto-scaling group, config bằng launch template / ASG user_data
- **Observability**: node_exporter trên mọi host (Ansible role từ Day 15)

Terraform quản lý: VPC, EC2, Security Group, IAM Role, ASG
Ansible quản lý: OS hardening, package install, service config, agent deployment

### 2.3. Pitfall thường gặp nhất

```hcl
# ❌ ANTI-PATTERN: local-exec gọi ansible-playbook trong Terraform
resource "aws_instance" "bastion" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  provisioner "local-exec" {
    command = "ansible-playbook -i ${self.public_ip}, bastion.yml"
  }
}
```

Vấn đề:
1. Terraform không đợi SSH service ready trước khi chạy command
2. Ansible chạy từ máy local (không qua bastion) → security Group phải mở SSH rộng
3. Không retry, không handle timeout
4. Không có output log, khó debug khi fail
5. Terraform state không tracking Ansible changes

---

## 3. Kiến thức nền tảng

### 3.1. Terraform vs Ansible: Hai trục khác nhau

| Chiều | Terraform | Ansible |
|-------|-----------|---------|
| **Paradigm** | Declarative | Procedural (idempotent) |
| **Mental model** | Immutable infrastructure | Mutable configuration |
| **State** | Full state tracked | No state (stateless) |
| **Scope** | Infrastructure lifecycle | Configuration drift |
| **Trigger** | `terraform apply` | `ansible-playbook` |
| **Parallelism** | Built-in dependency graph | Async by default |
| **Idempotent** | Always (state-driven) | Yes (by design) |

```
Terraform: WHAT → "declare desired state of infrastructure"
Ansible:   HOW  → "procedurally configure to reach desired state"
```

### 3.2. Ba patterns chính để integrate

#### Pattern 1: Decoupled (Recommended - Production default)

```
┌─────────────────────────────────────────────────────────┐
│  CI/CD Pipeline                                         │
│                                                         │
│  Stage 1: terraform apply                               │
│    → Creates EC2, VPC, Security Group                  │
│    → Tags: Project=day16, Role=bastion                  │
│    → Writes outputs to tf-output.json                   │
│                                                         │
│  Stage 2: ansible-playbook                              │
│    → Reads dynamic inventory from aws_ec2.yml           │
│    → Applies bastion-hardening + node_exporter roles   │
└─────────────────────────────────────────────────────────┘
```

**Ưu điểm:**
- Terraform và Ansible chạy độc lập, có thể retry riêng
- Inventory được generate tự động từ Terraform tags
- Debug dễ: output của stage 1 là input của stage 2
- Pipeline có thể parallel nếu dùng dynamic inventory

**Nhược điểm:**
- 2 pipeline stages → latency cao hơn (nhưng đáng giá)
- Cần chờ EC2 SSH-ready trước khi Ansible chạy

#### Pattern 2: Provisioner (Chỉ Dev/PoC)

```hcl
# ❌ Không dùng cho production
provisioner "local-exec" {
  command = "ansible-playbook -i ${self.public_ip}, playbook.yml"
}
```

Dùng khi:
- Demo nhanh, không cần production-grade
- One-off script không lặp lại
- Temporary environment

#### Pattern 3: Bake Image (Packer + Ansible)

```
┌──────────────────────────────────────────────────┐
│  Build Pipeline (offline, one-time)             │
│                                                  │
│  Packer + Ansible (provisioner)                 │
│    → Base AMI Ubuntu 22.04                      │
│    → Ansible applies hardening                  │
│    → Ansible installs node_exporter             │
│    → Output: Golden AMI ID                       │
└──────────────────────────────────────────────────┘
          ↓
┌──────────────────────────────────────────────────┐
│  Deploy Pipeline                                 │
│                                                  │
│  Terraform                                       │
│    → References AMI ID                           │
│    → Launches EC2 from Golden AMI               │
│    → Server boot với config sẵn trong AMI      │
└──────────────────────────────────────────────────┘
```

Dùng khi:
- Scale lớn (ASG 100+ instances)
- Immutable deployment policy
- Compliance yêu cầu auditable golden image

### 3.3. Dynamic inventory từ Terraform: Hai cách

#### Cách 1: Terraform output → Static inventory (simple)

```bash
# terraform output -json tạo JSON
terraform output -json bastion_public_ip
# {"sensitive":false,"type":"string","value":"54.123.45.67"}

# Script parse ra format INI
./scripts/tf-output-to-inventory.sh
# Output:
# [bastion]
# 54.123.45.67 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/bastion.pem
```

#### Cách 2: AWS EC2 dynamic inventory plugin (Recommended)

```yaml
# ansible/inventory/aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
filters:
  tag:Project: day16
  tag:Role: bastion
  instance-state-name: running
keyed_groups:
  - prefix: role
    key: tags.Role
```

Terraform set tags → Ansible filter by tags:

```hcl
resource "aws_instance" "bastion" {
  tags = {
    Name        = "day16-bastion"
    Project     = "day16"
    Role        = "bastion"
    ManagedBy   = "terraform"
    Environment = "learning"
    Owner       = "devops-team"
  }
}
```

### 3.4. Khi nào ghép, khi nào tách

```
Ghép Terraform + Ansible khi:
  ✓ Server cần OS-level config phức tạp (hardening, multi-package)
  ✓ Fleet thay đổi thường xuyên (Ansible re-run dễ hơn rebuild AMI)
  ✓ Cần idempotent config (Ansible guarantees)
  ✓ Team có Ansible expertise

Tách ra dùng cloud-init/Packer khi:
  ✓ Immutable deployment policy
  ✓ Scale > 50 instances, boot time critical
  ✓ Regulated environment yêu cầu auditable image
  ✓ Config rarely changes (stable golden image OK)

Dùng SSM thay Ansible khi:
  ✓ AWS-only environment
  ✓ Không muốn mở port 22
  ✓ Cần centralized audit log của tất cả commands
  ✓ IAM-based access thay vì SSH key

Dùng Packer thay Ansible-on-EC2 khi:
  ✓ Build time không critical (CI/CD build pipeline)
  ✓ Cần deterministic, reproducible image
  ✓ Boot time phải nhanh (scale fast)
  ✓ Compliance yêu cầu image signing
```

---

## 4. Deep Dive & Trade-offs

### 4.1. Comparison Matrix: 5 Approaches Config Server

| Approach | Khi nào dùng | Khi không nên | Pros | Cons |
|---------|-------------|---------------|------|------|
| **Ansible (post-provision)** | Cấu hình phức tạp, fleet thay đổi thường, server-class machine | Container/serverless, immutable AMI đã đủ, dev env tốc độ cao | Idempotent, mạnh mẽ, YAML declarative, large ecosystem | SSH dependency, drift theo thời gian nếu không re-run định kỳ |
| **cloud-init / user_data** | Bootstrap đơn giản, 1-shot config, ASG launch template | Logic phức tạp (multi-step, condition), multi-cloud | Native AWS, không SSH, parallel execution, không tốn chi phí extra | Khó debug (cloud-init logs obscure), không idempotent, giới hạn 16KB user_data |
| **Packer (bake image)** | Immutable AMI, scale lớn, golden image compliance, boot time critical | Config thay đổi nhanh (iteration), dev environment | Boot nhanh, deterministic, audit tốt, share AMI trong org | Build time (5-15 phút), AMI storage cost, AMI sprawl nếu không có lifecycle policy |
| **AWS SSM (Run Command / State Manager)** | AWS-only, không muốn mở port 22, centralized audit | Multi-cloud, on-prem, team không quen IAM | Không cần SSH, IAM-based, audit log tất cả commands, Session Manager free | AWS lock-in, learning curve IAM, rate limiting |
| **Terraform provisioner** | PoC, demo nhanh, one-off automation không lặp lại | Production, repeatable deployment, fleet management | Đơn giản, không cần external tool | Không idempotent, race condition, debug khó, không retry, không có inventory |

### 4.2. Decision Matrix: Chọn approach theo context

```
Bạn cần config server. Trả lời các câu hỏi sau:

Q1: Bao nhiêu server?
   ├─ 1-10 server → Ansible
   └─ 50+ server → Packer

Q2: Server thay đổi config bao thường?
   ├─ Thay đổi thường xuyên (daily/weekly) → Ansible
   └─ Stable trong tháng → Packer

Q3: Có AWS-only không?
   ├─ Yes + muốn không SSH → SSM
   └─ No / multi-cloud → Ansible hoặc Packer

Q4: Compliance yêu cầu golden image?
   ├─ Yes → Packer (mandatory)
   └─ No → Ansible hoặc cloud-init

Q5: Boot time critical?
   ├─ Yes (ASG scale fast) → Packer
   └─ No → Ansible hoặc cloud-init

Default → Decoupled Terraform + Ansible (Pattern 1)
```

### 4.3. Best Practice theo Organization Size

| Context | Recommended Pattern | Rationale |
|---------|---------------------|-----------|
| **Cá nhân học tập** | Decoupled (Terraform + Ansible riêng) | Dễ debug, hiểu rõ từng tool |
| **Small team / Startup** | Decoupled → Packer khi stable | Iterate nhanh, refactor khi scale |
| **Mid-size (10-50 engineers)** | Packer build AMI + Terraform deploy + Ansible one-off | Immutable base, Ansible cho exceptions |
| **Enterprise (50+ engineers)** | Packer + IAM SSM (không SSH) + Terraform + Ansible cho config không phải AWS | Full audit, IAM-based access, no SSH |
| **Bank / Regulated** | Packer + SSM + signed AMI + Terraform | Compliance-first, no SSH, signed image |

### 4.4. Performance / Cost / Security Implications

#### Cost Analysis (AWS US-East-1)

| Component | Monthly Cost (t3.micro) | Notes |
|-----------|------------------------|-------|
| EC2 t3.micro | ~$7.50 (non-free-tier) | Free tier: 750h/month |
| EBS 8GB gp3 | ~$0.64 | 8GB × $0.08/GB |
| NAT Gateway | ~$32.50 | NOT needed if using SSM |
| **Total (with NAT)** | ~$40.64/month | |
| **Total (SSM Session Manager)** | ~$8.14/month | Save $32.50 |
| **Total (Spot + SSM)** | ~$2-3/month | Production option |

**Cost optimization**: Dùng SSM Session Manager thay SSH → tiết kiệm $32.50/month (NAT Gateway hoặc bastion NAT).

#### Security: Bastion Hardening Requirements

Bastion host là entry point duy nhất, yêu cầu:

1. **SSH**: Key-only (no password), MFA enabled, non-standard port (option)
2. **Network**: Security Group chỉ mở SSH từ IP công ty, không có inbound khác
3. **Updates**: unattended-upgrades enabled, auto security patches
4. **Logging**: CloudWatch agent, auditd enabled
5. **Monitoring**: node_exporter + alerting
6. **Fail2ban**: Brute-force protection
7. **No app workload**: Bastion chỉ dùng để SSH, không install app

### 4.5. Common Pitfalls (Production Incidents)

#### Pitfall 1: Race Condition - SSH not ready

```hcl
# ❌ Terraform apply xong → Ansible chạy ngay
resource "null_resource" "ansible_run" {
  provisioner "local-exec" {
    command = "ansible-playbook bastion.yml"
    # Không depends_on → Ansible chạy khi EC2 chưa SSH-ready
  }
}
```

**Fix**: Thêm `sleep 30` hoặc dùng `ansible_wait_for` trong playbook.

#### Pitfall 2: Hard-code IP trong static inventory

```ini
# ❌ STATIC INVENTORY - hard-code IP
[bastion]
54.123.45.67 ansible_user=ubuntu
```

**Fix**: Dùng dynamic inventory hoặc generate inventory từ Terraform output.

#### Pitfall 3: Quên gắn tag chuẩn → Dynamic inventory miss

```hcl
# ❌ Không có tag
tags = {
  Name = "bastion"  # Missing: Project, Role, ManagedBy
}

# ✅ Đủ tag chuẩn
tags = {
  Name        = "day16-bastion"
  Project     = "day16"
  Role        = "bastion"
  ManagedBy   = "terraform"
  Environment = "learning"
  Owner       = "devops-team"
}
```

#### Pitfall 4: Chạy Ansible song song với Terraform apply

```
Pipeline 1: terraform apply (thay đổi security group)
Pipeline 2: ansible-playbook (chạy song song, host unreachable)
```

**Fix**: Terraform apply phải complete trước khi Ansible chạy. Dùng pipeline stage dependency.

#### Pitfall 5: Ansible không retry khi host temporary unavailable

```yaml
# ❌ Mặc định Ansible không retry
ansible-playbook bastion.yml

# ✅ Thêm retry
ansible-playbook bastion.yml --retry-files-enabled yes
```

---

## 5. Hands-on Lab

### Lab Overview

**Mục tiêu:** Terraform tạo EC2 bastion + Ansible hardening bastion bằng decoupled pattern

**Mode A (Local - Free):** Docker container thay EC2, Terraform provider Docker
**Mode B (AWS - Chi phí):** Terraform tạo VPC + EC2 t3.micro, Ansible hardening qua SSH

Chọn mode phù hợp với context của bạn.

---

### Step 0: Cost Warning (Mode B - AWS)

```
⚠️  COST WARNING - Mode B AWS

Resources phát sinh chi phí:
  - EC2 t3.micro:              ~$7.50/tháng (free tier: $0)
  - EBS 8GB gp3:               ~$0.64/tháng
  - VPC/SG/IGW:                FREE
  - Data transfer:              ~$0 (nếu < 1GB)

Mode A (Local Docker):         $0 - không phát sinh chi phí

Cleanup (bắt buộc sau lab):
  cd terraform && terraform destroy -auto-approve
  (hoặc docker-compose down nếu dùng Mode A)

⚠️ KHÔNG để resource chạy qua đêm. Destroy ngay khi xong lab.
```

---

### Step 1: Project Structure

Tạo cấu trúc thư mục:

```
day-16-terraform-ansible/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   └── terraform.tfvars.example
├── ansible/
│   ├── ansible.cfg
│   ├── playbooks/
│   │   └── bastion-hardening.yml
│   ├── roles/
│   │   ├── node_exporter/        # REUSE từ Day 15
│   │   │   ├── tasks/main.yml
│   │   │   ├── handlers/main.yml
│   │   │   ├── templates/node_exporter.service.j2
│   │   │   ├── defaults/main.yml
│   │   │   └── meta/main.yml
│   │   └── bastion-hardening/   # MỚI - Day 16
│   │       ├── tasks/main.yml
│   │       ├── handlers/main.yml
│   │       ├── templates/sshd_config.j2
│   │       ├── defaults/main.yml
│   │       └── meta/main.yml
│   ├── inventory/
│   │   ├── aws_ec2.yml           # Dynamic plugin (từ Day 15)
│   │   └── from-terraform.py     # Script generate inventory
│   └── group_vars/
│       └── bastion/
│           └── main.yml
├── scripts/
│   └── tf-output-to-inventory.sh
└── README.md
```

Tạo thư mục:

```bash
mkdir -p terraform ansible/playbooks ansible/roles/node_exporter ansible/roles/bastion-hardening
mkdir -p ansible/inventory ansible/group_vars/bastion scripts
```

**Từ Day 15, cần copy các file đã tạo:**

```bash
# Kiểm tra Day 15 structure
ls ../day-15-ansible-roles-vault/inventory/
# → aws_ec2.yml (dynamic plugin)

ls ../day-15-ansible-roles-vault/roles/node_exporter/
# → tasks/main.yml, handlers/main.yml, templates/, defaults/, meta/
```

```bash
# Copy từ Day 15 (giả định có sẵn)
# Thực tế nếu không có, tạo mới theo cấu trúc bên dưới
```

Nếu chưa có `node_exporter` role từ Day 15, tạo nhanh:

```yaml
# ansible/roles/node_exporter/defaults/main.yml
---
node_exporter_version: "1.7.0"
node_exporter_port: 9100
```

```yaml
# ansible/roles/node_exporter/tasks/main.yml
---
- name: Download node_exporter binary
  get_url:
    url: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/node_exporter-{{ node_exporter_version }}.linux-amd64.tar.gz"
    dest: "/tmp/node_exporter.tar.gz"
    mode: '0644'

- name: Extract node_exporter
  ansible.builtin.unarchive:
    src: "/tmp/node_exporter.tar.gz"
    dest: "/usr/local/bin"
    remote_src: true
    creates: "/usr/local/bin/node_exporter"

- name: Create node_exporter user
  ansible.builtin.user:
    name: node_exporter
    system: true
    shell: /usr/sbin/nologin
    create_home: false

- name: Install systemd unit file
  template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
    mode: '0644'
  notify: restart node_exporter

- name: Enable and start node_exporter
  systemd:
    name: node_exporter
    state: started
    enabled: true
```

```yaml
# ansible/roles/node_exporter/handlers/main.yml
---
- name: restart node_exporter
  systemd:
    name: node_exporter
    state: restarted
```

```ini
# ansible/roles/node_exporter/templates/node_exporter.service.j2
[Unit]
Description=Node Exporter
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
ExecStart=/usr/local/bin/node_exporter --collector.systemd --collector.processes

[Install]
WantedBy=multi-user.target
```

---

### Step 2: Terraform Code (Mode B - AWS)

#### File: `terraform/versions.tf`

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

#### File: `terraform/variables.tf`

```hcl
variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "day16"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "learning"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH to bastion"
  type        = string
  default     = "0.0.0.0/0"  # ⚠️ Thay bằng IP thật trong production
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
  default     = ""  # Set trong terraform.tfvars
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "bastion_ami" {
  description = "AMI ID for bastion (Ubuntu 22.04 LTS)"
  type        = string
  default     = "ami-055a7d7781d73c004"  # us-east-1 Ubuntu 22.04 LTS amd64
}
```

#### File: `terraform/terraform.tfvars.example`

```hcl
region            = "us-east-1"
project_name      = "day16"
environment       = "learning"
allowed_ssh_cidr   = "203.0.113.42/32"  # ⚠️ Thay bằng IP của bạn
key_name          = "bastion-key"       # Tạo key pair trước: aws ec2 create-key-pair
instance_type     = "t3.micro"
bastion_ami       = "ami-055a7d7781d73c004"
```

#### File: `terraform/main.tf`

```hcl
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "tag:Type"
    values = ["public"]
  }
}

# Security Group cho bastion
resource "aws_security_group" "bastion" {
  name        = "${var.project_name}-bastion-sg"
  description = "SSH access to bastion host"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from allowed IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # Cho phép outbound để install package
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-bastion-sg"
    Role        = "bastion-sg"
    ManagedBy   = "terraform"
  }
}

# IAM Role cho bastion (SSM access - không cần SSH port 22)
data "aws_iam_policy" "ssm_core" {
  name = "AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bastion" {
  name = "${var.project_name}-bastion-profile"
  role = aws_iam_role.bastion.name
}

resource "aws_iam_role" "bastion" {
  name = "${var.project_name}-bastion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "bastion_ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = data.aws_iam_policy.ssm_core.arn
}

# EC2 Bastion Instance
resource "aws_instance" "bastion" {
  ami           = var.bastion_ami
  instance_type = var.instance_type
  key_name      = var.key_name != "" ? var.key_name : null

  vpc_security_group_ids = [aws_security_group.bastion.id]

  # Chọn subnet đầu tiên từ default VPC
  subnet_id = data.aws_subnets.public.ids[0]

  # Tags chuẩn - QUAN TRỌNG cho dynamic inventory
  tags = {
    Name        = "${var.project_name}-bastion"
    Project     = var.project_name
    Role        = "bastion"
    ManagedBy   = "terraform"
    Environment = var.environment
    Owner       = "devops-team"
  }

  # Output public IP sau khi tạo xong
  user_data = <<-EOF
              #!/bin/bash
              # Wait for SSH to be ready
              sleep 10
              EOF

  lifecycle {
    create_before_destroy = true
  }
}

# Elastic IP (optional - uncomment nếu cần fixed IP)
# resource "aws_eip" "bastion" {
#   instance = aws_instance.bastion.id
#   domain   = "vpc"
#   tags = {
#     Name        = "${var.project_name}-bastion-eip"
#     ManagedBy   = "terraform"
#   }
# }
```

#### File: `terraform/outputs.tf`

```hcl
output "bastion_public_ip" {
  description = "Public IP of bastion host"
  value       = aws_instance.bastion.public_ip
}

output "bastion_id" {
  description = "Instance ID of bastion host"
  value       = aws_instance.bastion.id
}

output "bastion_tags" {
  description = "Tags used for dynamic inventory"
  value = {
    Project     = var.project_name
    Role        = "bastion"
    ManagedBy   = "terraform"
    Environment = var.environment
  }
}

output "ssh_command" {
  description = "SSH command to connect to bastion"
  value = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${aws_instance.bastion.public_ip}" : "ssh ubuntu@${aws_instance.bastion.public_ip}"
}

output "region" {
  description = "AWS region"
  value       = var.region
}
```

#### Terraform Plan

```bash
cd terraform

# Khởi tạo
terraform init

# Xem plan (không apply)
terraform plan \
  -var="key_name=bastion-key" \
  -var="allowed_ssh_cidr=$(curl -s ifconfig.me)/32"
```

Expected output:

```
Terraform will perform the following actions:

  # aws_security_group.bastion will be created
  # aws_instance.bastion will be created
  # aws_iam_role.bastion will be created
  # aws_iam_instance_profile.bastion will be created

Plan: 4 to add, 0 to change, 0 to destroy.
```

---

### Step 2 Alternative: Terraform Code (Mode A - Local Docker)

Nếu dùng Mode A (Local), thay thế `main.tf`:

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

resource "docker_image" "ubuntu_ssh" {
  name         = "ubuntu:22.04"
  keep_locally = true
}

resource "docker_container" "bastion" {
  image = docker_image.ubuntu_ssh.image_id
  name  = "${var.project_name}-bastion"
  env   = ["HOSTNAME=${var.project_name}-bastion"]

  ports {
    internal = 22
    external = 2222
  }

  mounts {
    target = "/root/.ssh"
    source = "/home/user/.ssh"
    type   = "bind"
  }

  command = [
    "/usr/sbin/sshd",
    "-D",
    "-o", "PermitRootLogin=no",
    "-o", "PasswordAuthentication=no"
  ]

  privileged = false
}

output "bastion_ip" {
  value = "127.0.0.1"
}

output "bastion_port" {
  value = 2222
}
```

```hcl
# terraform/variables.tf (Mode A)
variable "project_name" {
  default = "day16"
}
```

---

### Step 3: Generate Inventory từ Terraform Output

#### Script: `scripts/tf-output-to-inventory.sh`

```bash
#!/usr/bin/env bash
#
# tf-output-to-inventory.sh
# Parse terraform output JSON → Ansible static inventory INI format
#
# Usage:
#   terraform output -json | ./tf-output-to-inventory.sh
#   ./tf-output-to-inventory.sh < tf-output.json
#

set -euo pipefail

INVENTORY_FILE="${INVENTORY_FILE:-/dev/stdout}"
SSH_USER="${SSH_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"

# Parse JSON từ stdin hoặc file argument
INPUT="${1:-/dev/stdin}"
TERRAFORM_JSON=$(cat "$INPUT")

# Extract values
BASTION_IP=$(echo "$TERRAFORM_JSON" | jq -r '.bastion_public_ip.value // empty')
PROJECT=$(echo "$TERRAFIN_JSON" | jq -r '.bastion_tags.value.Project // "unknown"')

if [[ -z "$BASTION_IP" ]] || [[ "$BASTION_IP" == "null" ]]; then
  echo "ERROR: bastion_public_ip not found in terraform output" >&2
  exit 1
fi

# Generate INI format inventory
cat > "$INVENTORY_FILE" <<EOF
# Ansible inventory generated from Terraform output
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Source: terraform output -json

[bastion]
${BASTION_IP} ansible_user=${SSH_USER} ansible_ssh_private_key_file=${SSH_KEY}

[bastion:vars]
ansible_port=22
project=${PROJECT}
ansible_python_interpreter=/usr/bin/python3
EOF

echo "Inventory written to $INVENTORY_FILE"
```

```bash
chmod +x scripts/tf-output-to-inventory.sh
```

**Sử dụng:**

```bash
# Generate inventory từ terraform output
cd terraform
terraform output -json > ../tf-output.json
cd ..
./scripts/tf-output-to-inventory.sh < tf-output.json > ansible/inventory/static.ini

# Kiểm tra
cat ansible/inventory/static.ini
```

Output:

```ini
# Ansible inventory generated from Terraform output
# Generated at: 2026-05-14T10:00:00Z
# Source: terraform output -json

[bastion]
54.123.45.67 ansible_user=ubuntu ansible_ssh_private_key_file=/home/user/.ssh/id_rsa

[bastion:vars]
ansible_port=22
project=day16
ansible_python_interpreter=/usr/bin/python3
```

#### Python Alternative: `ansible/inventory/from-terraform.py`

```python
#!/usr/bin/env python3
"""
from-terraform.py
Ansible dynamic inventory script từ Terraform output

Usage:
    ansible-inventory -i from-terraform.py --graph
    ansible-playbook -i from-terraform.py playbook.yml
"""

import json
import sys
import subprocess
from typing import Dict, Any


def get_terraform_output() -> Dict[str, Any]:
    """Chạy terraform output -json và parse kết quả"""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True,
            text=True,
            check=True,
            cwd="terraform"
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: terraform output failed: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def build_inventory() -> Dict[str, Any]:
    """Build Ansible inventory từ Terraform output"""
    tf_output = get_terraform_output()

    bastion_ip = tf_output.get("bastion_public_ip", {}).get("value", "")
    bastion_tags = tf_output.get("bastion_tags", {}).get("value", {})

    if not bastion_ip:
        print("ERROR: bastion_public_ip not found", file=sys.stderr)
        sys.exit(1)

    inventory = {
        "_meta": {
            "hostvars": {
                bastion_ip: {
                    "ansible_user": "ubuntu",
                    "ansible_ssh_private_key_file": "~/.ssh/id_rsa",
                    "project": bastion_tags.get("Project", "unknown"),
                    "role": bastion_tags.get("Role", "bastion"),
                }
            }
        },
        "bastion": {
            "hosts": [bastion_ip]
        },
        "all": {
            "children": ["bastion"]
        }
    }

    return inventory


def main():
    inventory = build_inventory()

    if "--list" in sys.argv:
        print(json.dumps(inventory))
    elif "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
        print(json.dumps(inventory["_meta"]["hostvars"].get(host, {})))
    else:
        # Default: list inventory
        print(json.dumps(inventory))


if __name__ == "__main__":
    main()
```

```bash
chmod +x ansible/inventory/from-terraform.py
```

**Sử dụng:**

```bash
# Test dynamic inventory
cd ansible
ansible-inventory -i inventory/from-terraform.py --graph

# Chạy playbook
ansible-playbook -i inventory/from-terraform.py playbooks/bastion-hardening.yml
```

---

### Step 4: Bastion Hardening Role

#### File: `ansible/roles/bastion-hardening/defaults/main.yml`

```yaml
---
# defaults for bastion-hardening role
bastion_ssh_port: 22
bastion_ssh AllowUsers: ""  # Comma-separated list of allowed users
bastion_ssh_permit_root_login: "no"
bastion_ssh_password_auth: "no"
bastion_ssh_max_auth_tries: 3
bastion_ssh_client_alive_interval: 300
bastion_ssh_client_alive_count_max: 2
bastion_ssh_pubkey_auth: "yes"
bastion_ssh_x11_forwarding: "no"
bastion_ssh_accept_env: "no"
bastion_ssh_use_pam: "yes"

# Unattended upgrades
bastion_unattended_automatic_reboot: false
bastion_unattended_mail_to: "devops@example.com"

# Fail2ban
bastion_fail2ban_bantime: 3600
bastion_fail2ban_findtime: 600
bastion_fail2ban_maxretry: 5

# UFW firewall
bastion_ufw_enabled: true
bastion_ufw_default_incoming: "deny"
bastion_ufw_default_outgoing: "allow"

# Auditd
bastion_auditd_enabled: true

# CloudWatch Agent
bastion_cloudwatch_enabled: false
bastion_cloudwatch_region: "us-east-1"
```

#### File: `ansible/roles/bastion-hardening/tasks/main.yml`

```yaml
---
# tasks for bastion-hardening role
- name: Ensure base packages are installed
  apt:
    name:
      - curl
      - wget
      - vim
      - git
      - unattended-upgrades
      - fail2ban
      - ufw
      - auditd
      - audispd-plugins
      - python3
      - jq
    state: present
    update_cache: true
  when: ansible_os_family == "Debian"

- name: Ensure base packages are installed (RHEL family)
  dnf:
    name:
      - curl
      - wget
      - vim
      - git
      - unattended-upgrades
      - fail2ban
      - ufw
      - audit
      - python3
    state: present
    update_cache: true
  when: ansible_os_family == "RedHat"

# ─── SSH Hardening ───────────────────────────────────────────────
- name: Deploy hardened sshd_config
  template:
    src: sshd_config.j2
    dest: /etc/ssh/sshd_config
    owner: root
    group: root
    mode: '0600'
    validate: '/usr/sbin/sshd -t -f %s'
  notify: restart sshd
  when: ansible_os_family == "Debian"

- name: Deploy hardened sshd_config (RHEL)
  template:
    src: sshd_config.j2
    dest: /etc/ssh/sshd_config
    owner: root
    group: root
    mode: '0600'
    validate: '/usr/sbin/sshd -t -f %s'
  notify: restart sshd
  when: ansible_os_family == "RedHat"

# ─── Fail2ban ────────────────────────────────────────────────────
- name: Configure fail2ban jail.local
  copy:
    dest: /etc/fail2ban/jail.local
    content: |
      [sshd]
      enabled = true
      port = {{ bastion_ssh_port }}
      filter = sshd
      logpath = /var/log/auth.log
      maxretry = {{ bastion_fail2ban_maxretry }}
      bantime = {{ bastion_fail2ban_bantime }}
      findtime = {{ bastion_fail2ban_findtime }}
      backend = auto
    mode: '0644'
  notify: restart fail2ban
  when: ansible_os_family == "Debian"

- name: Enable and start fail2ban
  systemd:
    name: fail2ban
    state: started
    enabled: true
  when: ansible_os_family == "Debian"

# ─── Unattended Upgrades ──────────────────────────────────────────
- name: Configure unattended-upgrades
  copy:
    dest: /etc/apt/apt.conf.d/50unattended-upgrades
    content: |
      Unattended-Upgrade::Allowed-Origins {
          "${distro_id}:${distro_codename}-security";
      };
      Unattended-Upgrade::Automatic-Reboot "{{ bastion_unattended_automatic_reboot | string | lower }}";
      Unattended-Upgrade::Mail "{{ bastion_unattended_mail_to }}";
    mode: '0644'
  when: ansible_os_family == "Debian"

- name: Enable periodic upgrades
  copy:
    dest: /etc/apt/apt.conf.d/20auto-upgrades
    content: |
      APT::Periodic::Update-Package-Lists "1";
      APT::Periodic::Download-Upgradeable-Packages "1";
      APT::Periodic::Unattended-Upgrade "1";
      APT::Periodic::AutocleanInterval "7";
    mode: '0644'
  when: ansible_os_family == "Debian"

# ─── UFW Firewall ─────────────────────────────────────────────────
- name: Ensure UFW is installed (Debian)
  apt:
    name: ufw
    state: present
  when: ansible_os_family == "Debian"

- name: Configure UFW default policies
  ufw:
    direction: "{{ item.direction }}"
    policy: "{{ item.policy }}"
  loop:
    - {direction: 'incoming', policy: '{{ bastion_ufw_default_incoming }}'}
    - {direction: 'outgoing', policy: '{{ bastion_ufw_default_outgoing }}'}
  when: bastion_ufw_enabled | bool

- name: Allow SSH through UFW
  ufw:
    rule: allow
    port: '{{ bastion_ssh_port }}'
    proto: tcp
  when: bastion_ufw_enabled | bool

- name: Enable UFW
  ufw:
    state: enabled
  when: bastion_ufw_enabled | bool

# ─── Auditd ──────────────────────────────────────────────────────
- name: Configure auditd rules for SSH access
  copy:
    dest: /etc/audit/rules.d/audit-bastion.rules
    content: |
      # Monitor SSH connections
      -w /etc/ssh/sshd_config -p wa -k sshd_config
      -w /usr/sbin/sshd -p x -k sshd_exec
      -a always,exit -F arch=b64 -S execve -F path=/usr/bin/ssh -k ssh_exec
    mode: '0640'
  when: bastion_auditd_enabled | bool

- name: Enable and start auditd
  systemd:
    name: auditd
    state: started
    enabled: true
  when: bastion_auditd_enabled | bool

# ─── System hardening ─────────────────────────────────────────────
- name: Disable core dumps
  systemd:
    name: systemd-coredump
    state: stopped
    enabled: false
  ignore_errors: true

- name: Set kernel hardening parameters
  sysctl:
    name: "{{ item.name }}"
    value: "{{ item.value }}"
    state: present
    reload: true
    sysctl_file: /etc/sysctl.d/99-bastion-hardening.conf
  loop:
    - {name: 'net.ipv4.conf.all.accept_redirects', value: '0'}
    - {name: 'net.ipv4.conf.default.accept_redirects', value: '0'}
    - {name: 'net.ipv4.conf.all.send_redirects', value: '0'}
    - {name: 'net.ipv4.conf.default.send_redirects', value: '0'}
    - {name: 'net.ipv4.conf.all.accept_source_route', value: '0'}
    - {name: 'net.ipv4.conf.default.accept_source_route', value: '0'}
    - {name: 'kernel.dmesg_restrict', value: '1'}
    - {name: 'kernel.kptr_restrict', value: '2'}

- name: Disable unused filesystems
  lineinfile:
    path: /etc/modprobe.d/blacklist.conf
    line: "install {{ item }} /bin/true"
    create: true
    mode: '0644'
  loop:
    - cramfs
    - freevxfs
    - hfs
    - hfsplus
    - jffs2
    - udf

# ─── Verification ────────────────────────────────────────────────
- name: Get SSH config syntax validation output
  command: /usr/sbin/sshd -t -f /etc/ssh/sshd_config
  changed_when: false
  register: sshd_check
  failed_when: sshd_check.rc != 0

- name: Display hardening status
  debug:
    msg: |
      Bastion hardening complete.
      SSH port: {{ bastion_ssh_port }}
      Fail2ban: enabled
      UFW: {{ 'enabled' if bastion_ufw_enabled else 'disabled' }}
      Auditd: {{ 'enabled' if bastion_auditd_enabled else 'disabled' }}
      Unattended upgrades: enabled
```

#### File: `ansible/roles/bastion-hardening/handlers/main.yml`

```yaml
---
- name: restart sshd
  systemd:
    name: sshd
    state: restarted

- name: restart fail2ban
  systemd:
    name: fail2ban
    state: restarted
```

#### File: `ansible/roles/bastion-hardening/templates/sshd_config.j2`

```
# Managed by Ansible - DO NOT EDIT MANUALLY
# Template: sshd_config.j2
# Role: bastion-hardening

Port {{ bastion_ssh_port }}
Protocol 2

HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

PermitRootLogin {{ bastion_ssh_permit_root_login }}
{% if bastion_ssh_allow_users %}
AllowUsers {{ bastion_ssh_allow_users }}
{% endif %}

PasswordAuthentication {{ bastion_ssh_password_auth }}
PubkeyAuthentication {{ bastion_ssh_pubkey_auth }}
AuthorizedKeysFile .ssh/authorized_keys

ChallengeResponseAuthentication no
KerberosAuthentication no
GSSAPIAuthentication no

X11Forwarding {{ bastion_ssh_x11_forwarding }}
AcceptEnv {{ bastion_ssh_accept_env }}

PrintMotd no
{% if bastion_ssh_use_pam %}
UsePAM yes
{% endif %}

ClientAliveInterval {{ bastion_ssh_client_alive_interval }}
ClientAliveCountMax {{ bastion_ssh_client_alive_count_max }}

MaxAuthTries {{ bastion_ssh_max_auth_tries }}
MaxSessions 10

LoginGraceTime 60

Banner /etc/ssh/banner

AllowTcpForwarding no
AllowAgentForwarding no

Subsystem sftp /usr/lib/openssh/sftp-server
```

#### File: `ansible/roles/bastion-hardening/meta/main.yml`

```yaml
---
galaxy_info:
  author: devops-team
  description: Hardening role for bastion hosts
  company: learning
  license: MIT
  min_ansible_version: "2.10"
  platforms:
    - name: Ubuntu
      versions:
        - focal
        - jammy
    - name: Amazon
      versions:
        - all
  galaxy_tags:
    - hardening
    - ssh
    - bastion
    - security
    - fail2ban
    - ufw
dependencies: []
```

---

### Step 5: Bastion Hardening Playbook

#### File: `ansible/playbooks/bastion-hardening.yml`

```yaml
---
# bastion-hardening.yml
# Apply bastion hardening + node_exporter to bastion hosts
#
# Usage:
#   # Dynamic inventory (recommended)
#   ansible-playbook -i inventory/aws_ec2.yml playbooks/bastion-hardening.yml
#
#   # Static inventory from Terraform output
#   ansible-playbook -i inventory/static.ini playbooks/bastion-hardening.yml
#
#   # Python dynamic inventory
#   ansible-playbook -i inventory/from-terraform.py playbooks/bastion-hardening.yml

- name: Bastion host hardening + observability
  hosts: role_bastion        # Group from aws_ec2.yml keyed_groups
  gather_facts: true

  pre_tasks:
    - name: Wait for SSH to be ready
      ansible.builtin.wait_for:
        host: "{{ ansible_host }}"
        port: 22
        delay: 5
        timeout: 120
        state: started
      vars:
        ansible_connection: local
      delegate_to: localhost

    - name: Display target host info
      ansible.builtin.debug:
        msg: |
          Applying hardening to: {{ ansible_host }}
          Distribution: {{ ansible_distribution }} {{ ansible_distribution_version }}
          Python: {{ ansible_python_version }}

  roles:
    - role: bastion-hardening
      tags: [security, ssh, firewall]

    - role: node_exporter
      tags: [monitoring, observability]
      # Override defaults nếu cần:
      # node_exporter_version: "1.7.0"
      # node_exporter_port: 9100

  post_tasks:
    - name: Verify SSH configuration
      ansible.builtin.command: /usr/sbin/sshd -t -f /etc/ssh/sshd_config
      changed_when: false
      register: sshd_verify
      failed_when: sshd_verify.rc != 0

    - name: Verify node_exporter is running
      ansible.builtin.uri:
        url: "http://{{ ansible_host }}:9100/metrics"
        method: GET
        status_code: [200]
      register: node_exporter_check
      retries: 3
      delay: 10
      until: node_exporter_check.status == 200
      ignore_errors: true
      changed_when: false

    - name: Display hardening summary
      ansible.builtin.debug:
        msg: |
          ========================================
          Bastion Hardening Complete
          ========================================
          Host: {{ ansible_host }}
          node_exporter: http://{{ ansible_host }}:9100/metrics
          SSH config: OK
          ========================================
```

---

### Step 6: Chạy End-to-End

#### 6.1. Terraform Apply (Mode B)

```bash
cd terraform

# Khởi tạo provider
terraform init

# Plan
terraform plan \
  -var="key_name=bastion-key" \
  -var="allowed_ssh_cidr=$(curl -s ifconfig.me)/32"

# Apply
terraform apply -auto-approve \
  -var="key_name=bastion-key" \
  -var="allowed_ssh_cidr=$(curl -s ifconfig.me)/32"

# Ghi nhớ output
TERRAFORM_OUTPUT=$(terraform output -json)
echo "$TERRAFORM_OUTPUT"
```

Expected output:

```
Outputs:

bastion_id = "i-0abc123def456"
bastion_public_ip = "54.123.45.67"
ssh_command = "ssh -i ~/.ssh/bastion-key.pem ubuntu@54.123.45.67"
```

#### 6.2. Verify Dynamic Inventory (Mode B)

```bash
cd ../ansible

# Kiểm tra dynamic inventory thấy bastion
ansible-inventory -i inventory/aws_ec2.yml --graph

# Expected output:
# @all:
#   |--@role_bastion:
#   |  |--54.123.45.67
#   |--@ungrouped:
```

Nếu không thấy host, kiểm tra:

```bash
# 1. Kiểm tra tags trên EC2
aws ec2 describe-instances \
  --filters "Name=tag:Role,Values=bastion" \
  --query 'Reservations[].Instances[].[{IP:PublicIpAddress,Tags:Tags}]'

# 2. Kiểm tra IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::123456789:role/day16-bastion-role" \
  --action-names "ec2:DescribeInstances" \
  --resource-arns "*"

# 3. Kiểm tra region
aws configure get region
```

#### 6.3. Ping hosts

```bash
# Test connectivity
ansible all -i inventory/aws_ec2.yml -m ping

# Expected:
# 54.123.45.67 | SUCCESS => {
#     "ansible_facts": {
#         "discovered_interpreter_python": "/usr/bin/python3"
#     },
#     "changed": false,
#     "ping": "pong"
# }
```

#### 6.4. Chạy Playbook

```bash
# Dry-run trước
ansible-playbook -i inventory/aws_ec2.yml \
  playbooks/bastion-hardening.yml \
  --check

# Chạy thật
ansible-playbook -i inventory/aws_ec2.yml \
  playbooks/bastion-hardening.yml
```

Expected output (abbreviated):

```
PLAY [Bastion host hardening + observability] *********************

TASK [Gathering Facts] ********************************************
ok: [54.123.45.67]

TASK [bastion-hardening : Ensure base packages are installed] *****
changed: [54.123.45.67]

TASK [bastion-hardening : Deploy hardened sshd_config] ************
changed: [54.123.45.67]

TASK [bastion-hardening : Configure fail2ban jail.local] *********
changed: [54.123.45.67]

TASK [bastion-hardening : Enable and start fail2ban] *************
ok: [54.123.45.67]

TASK [bastion-hardening : Configure UFW firewall] ****************
changed: [54.123.45.67]

TASK [node_exporter : Download node_exporter binary] *************
changed: [54.123.45.67]

TASK [node_exporter : Install systemd unit] *********************
changed: [54.123.45.67]

TASK [node_exporter : Enable and start node_exporter] *************
ok: [54.123.45.67]

PLAY RECAP ********************************************************
54.123.45.67 : ok=15  changed=8  unreachable=0  failed=0
```

---

### Step 7: Troubleshooting

#### Problem 1: SSH Timeout

```
fatal: [54.123.45.67]: UNREACHABLE! => {
    "msg": "Failed to connect to the host via ssh:...",
    "unreachable": true
}
```

**Nguyên nhân & Fix:**

1. Security Group chưa mở SSH:
```bash
# Kiểm tra SG rules
aws ec2 describe-security-groups \
  --group-ids sg-xxxxx \
  --query 'SecurityGroups[].IpPermissions'
```

2. EC2 chưa boot xong (user_data chạy):
```bash
# Đợi thêm
sleep 30
# Hoặc kiểm tra System Log
aws ec2 get-console-output --instance-id i-xxxxx
```

3. Wrong key hoặc wrong user:
```bash
# Thử ssh thủ công
ssh -v -i ~/.ssh/bastion-key.pem ubuntu@54.123.45.67
```

#### Problem 2: Dynamic Inventory Misses Host

```
[WARNING]: No inventory was parsed from aws_ec2.yml
@all:
  |--@ungrouped:
```

**3 nguyên nhân phổ biến nhất:**

1. **Tag missing**: Terraform chưa set đúng tag
```bash
aws ec2 describe-instances \
  --instance-ids i-xxxxx \
  --query 'Reservations[].Instances[].Tags'
```

2. **IAM permission missing**: Inventory plugin không đọc được EC2
```bash
# Kiểm tra boto3
python3 -c "import boto3; print(boto3.__version__)"
pip install boto3 botocore
```

3. **Region mismatch**: Inventory config khác region với EC2
```bash
# Trong aws_ec2.yml
regions:
  - us-east-1  # Phải đúng region của EC2
```

#### Problem 3: Ansible boto3 Missing

```
ERROR! the Python boto3 module is required by the aws_ec2 plugin.
python3 required json query engine.
""" import boto3 """
"""

# Fix:
pip3 install boto3 botocore
ansible-inventory -i inventory/aws_ec2.yml --list
```

#### Problem 4: Windows Docker Desktop (Mode A)

```
Error: Unable to connect to Docker daemon
```

**Fix:**

```powershell
# Ensure Docker Desktop is running
docker version

# Enable WSL2 integration hoặc set DOCKER_HOST
$env:DOCKER_HOST = "tcp://localhost:2375"

# Hoặc dùng Docker context
docker context ls
docker context use default
```

---

### Step 8: Cleanup (Bắt buộc)

```bash
# Destroy Terraform resources
cd terraform
terraform destroy -auto-approve

# Verify all resources removed
aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=day16" \
  --query 'Reservations[].Instances[].InstanceId'

# Remove generated files
rm -f ../tf-output.json
rm -f ../ansible/inventory/static.ini

# Optional: Stop Docker containers (Mode A)
docker stop day16-bastion 2>/dev/null || true
```

---

## 6. Kiểm tra hiểu bài

### Câu 1: Packer vs Ansible-on-EC2

**Câu hỏi:** Khi nào dùng Packer build AMI thay vì Ansible apply trên EC2 đang chạy?

**Trả lời:**

| Scenario | Tool | Lý do |
|----------|------|-------|
| ASG 50+ instances, scale nhanh | Packer | Boot từ AMI đã config sẵn = nhanh hơn Ansible bootstrap |
| Config thay đổi hàng ngày | Ansible | Rebuild AMI mỗi ngày = cost + time lãng phí |
| Compliance yêu cầu auditable image | Packer | Immutable, reproducible, có checksum |
| Dev environment, iterate nhanh | Ansible | Không cần build image |
| Golden image policy (certified OS) | Packer | IS (Information Security) team yêu cầu |
| Multi-cloud deployment | Ansible | Packer cần builder riêng cho từng cloud |

---

### Câu 2: Tại sao `local-exec` provisioner gọi ansible-playbook là anti-pattern?

**Trả lời:**

1. **Race condition**: Terraform không biết EC2 SSH service đã ready chưa → Ansible fail
2. **No idempotency**: Nếu Terraform re-run, Ansible re-run không kiểm soát
3. **No retry logic**: Provisioner fail → toàn bộ Terraform apply fail
4. **No inventory management**: Output của provisioner không đi vào Ansible inventory
5. **Debug hell**: Lỗi Ansible trong Terraform log rất khó đọc
6. **Security**: Ansible chạy từ máy local → phải mở Security Group SSH rộng hơn

---

### Câu 3: Trade-off decoupled pattern vs bake-image (Packer)

| Aspect | Decoupled (Terraform + Ansible) | Bake Image (Packer + Terraform) |
|--------|----------------------------------|-------------------------------|
| **Time to boot** | ~3-5 phút (Ansible bootstrap) | ~30-60 giây (từ AMI) |
| **Iteration speed** | Nhanh (sửa playbook → re-run) | Chậm (rebuild AMI 5-15 phút) |
| **Determinism** | Ansible có thể drift | 100% deterministic |
| **Storage cost** | Không có | AMI storage tốn chi phí |
| **Rollback** | Re-run Ansible | Launch từ AMI cũ |
| **Compliance** | Khó audit image | Dễ sign và audit |
| **Complexity** | 2 pipeline stages | Packer + Terraform |

---

### Câu 4: Debug dynamic inventory không thấy host

**Câu hỏi:** Dynamic inventory aws_ec2.yml không thấy 2/5 host mới. Kiểm tra những gì?

**Trả lời (3 nguyên nhân phổ biến):**

1. **Tag không match filter:**
   ```bash
   aws ec2 describe-instances \
     --instance-ids i-host1 i-host2 \
     --query 'Reservations[].Instances[].Tags'
   # Kiểm tra tag:Project, tag:Role có đúng như filter trong aws_ec2.yml
   ```

2. **IAM permission không đủ:**
   ```bash
   ansible-inventory -i inventory/aws_ec2.yml --list --debug
   # Cần: ec2:DescribeInstances trong IAM Role của máy chạy Ansible
   ```

3. **Region không khớp:**
   ```bash
   aws ec2 describe-instances --region us-east-1
   aws configure get region  # vs region trong aws_ec2.yml
   ```

---

### Câu 5: Refactor static inventory → dynamic inventory

**Câu hỏi:** Hiện tại team dùng static inventory với hard-code IP. Làm sao migrate sang dynamic inventory mà không break production?

**Trả lời (migration strategy):**

```
Phase 1: Parallel run (1-2 tuần)
  1. Terraform thêm tags chuẩn vào tất cả EC2
  2. Tạo aws_ec2.yml với filter mới
  3. Chạy cả static inventory và dynamic inventory song song
  4. So sánh kết quả: ansible-inventory -i aws_ec2.yml --graph vs cat static.ini

Phase 2: Switchover
  1. Cập nhật CI/CD pipeline dùng dynamic inventory
  2. Remove static inventory (hoặc giữ làm backup)

Phase 3: Cleanup
  1. Xóa static inventory files
  2. Commit aws_ec2.yml vào git
```

---

## 7. Tóm tắt cuối ngày

### 3 nguyên tắc quan trọng nhất

1. **Decoupled là default**: Terraform + Ansible chạy riêng, Terraform output làm inventory cho Ansible. Không dùng `local-exec` provisioner trong production.

2. **Immutable thắng mutable ở scale**: Khi fleet > 50 hosts hoặc compliance yêu cầu, dùng Packer bake AMI. Ansible-on-EC2 tốt cho dev, iteration nhanh, và fleet < 50 hosts.

3. **Tags là cầu nối**: Tất cả resources từ Terraform phải có tags chuẩn (Project, Role, ManagedBy, Environment, Owner). Dynamic inventory dựa 100% vào tags.

### Output đã tạo

```
terraform/
├── main.tf          # EC2 bastion + SG + IAM + VPC
├── variables.tf     # Reusable variables
├── outputs.tf       # bastion_public_ip, ssh_command, tags
└── versions.tf     # Provider constraints

ansible/
├── ansible.cfg     # Config với dynamic inventory plugin
├── playbooks/
│   └── bastion-hardening.yml  # Main playbook
├── roles/
│   ├── node_exporter/         # Reused từ Day 15
│   └── bastion-hardening/     # NEW: SSH, fail2ban, UFW, auditd
└── inventory/
    ├── aws_ec2.yml            # Dynamic plugin
    └── from-terraform.py      # Python dynamic inventory script

scripts/
└── tf-output-to-inventory.sh  # Bash script generate static inventory
```

### Chuẩn bị Day 17

Day 16 hoàn thành **infrastructure-level automation**: Terraform quản lý infrastructure lifecycle, Ansible quản lý configuration drift. Day 17 chuyển sang **application-level GitOps** với ArgoCD — từ "infrastructure as code" sang "application delivery as code".

---

## 8. Tham khảo thêm

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Ansible amazon.aws Collection](https://clouddocs.to/ansible-ibmcloud/2/collections/amazon/aws/aws_ec2_inventory.html)
- [HashiCorp Blog: Terraform vs. Configuration Management](https://www.hashicorp.com/blog/terraform-vs-configuration-management)
- [AWS SSM Session Manager Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
- [Packer Documentation](https://developer.hashicorp.com/packer/docs)
- [CIS Benchmarks for Ubuntu](https://www.cisecurity.org/benchmark/ubuntu)
