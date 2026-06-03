# Day 16 - Terraform + Ansible Integration: Cheatsheet & Reference

---

## 1. Comparison Matrix: 5 Server Configuration Approaches

| Approach | Paradigm | Idempotent | SSH Required | Lock-in | Boot Time | Best For |
|----------|----------|-----------|--------------|---------|-----------|---------|
| **Ansible (post-provision)** | Procedural | Yes | Yes | None | ~3-5 min | Config phức tạp, fleet nhỏ-vừa |
| **cloud-init / user_data** | Declarative | No | No | AWS-only | ~2-3 min | ASG bootstrap đơn giản |
| **Packer (bake image)** | Declarative | Yes (build-time) | No (build) | Multi | ~30-60 sec | Scale lớn, immutable, compliance |
| **AWS SSM** | Command-based | Partial | No | AWS-only | N/A | AWS-only, no-SSH policy |
| **Terraform provisioner** | Procedural | No | Yes | None | N/A | **Chỉ dùng cho PoC** |

---

## 2. Decision Tree: Tool Chọn Cho Server Configuration

```
Tôi cần config server (hoặc container image):

│
├─► Đây là container image, không phải VM?
│     ├─► Yes: Dùng Dockerfile / Packer Docker builder
│     └─► No: Tiếp tục ↓
│
├─► Hệ thống có AWS-only không?
│     ├─► Yes + không muốn SSH + cần audit: Dùng AWS SSM
│     └─► No: Tiếp tục ↓
│
├─► Config thay đổi thường xuyên (daily/weekly)?
│     ├─► Yes: Tiếp tục ↓
│     └─► No (stable trong tháng+): ↓ → Packer section
│
├─► Bao nhiêu server?
│     ├─► 1-50 servers: Ansible (post-provision)
│     └─► 50+ servers: Packer (bake AMI)
│
├─► Boot time có critical không (ASG scale < 2 phút)?
│     ├─► Yes: Packer (bake AMI)
│     └─► No: Ansible
│
└─► Compliance / Security yêu cầu golden image?
      ├─► Yes: Packer (mandatory)
      └─► No: Ansible hoặc cloud-init

═══════════════════════════════════════════════
QUICK ANSWER (8 câu hỏi):
═══════════════════════════════════════════════
  Q1: Immutable required?      → Yes = Packer
  Q2: Multi-cloud?             → Yes = Ansible (Packer + builder)
  Q3: Fleet > 50 nodes?       → Yes = Packer (hoặc Ansible async)
  Q4: Config changes daily?    → Yes = Ansible
  Q5: AWS-only + no SSH?       → Yes = SSM
  Q6: ASG scale fast (<2min)?  → Yes = Packer
  Q7: Compliance audit image? → Yes = Packer
  Q8: Dev / iterate fast?     → Yes = Ansible hoặc cloud-init
═══════════════════════════════════════════════
  Default: Decoupled Terraform + Ansible
```

---

## 3. ADR Template: Terraform + Ansible Integration Decision

```markdown
# ADR-0016: Server Configuration Strategy

**Date:** 2026-05-14
**Status:** Accepted
**Context:** Team cần quyết định tool cho server configuration

## Decision Drivers

- Số lượng server dự kiến: ___
- Tần suất thay đổi config: ___
- Compliance yêu cầu: ___
- Multi-cloud hay AWS-only: ___
- Boot time requirement: ___
- Team Ansible expertise: ___

## Options Considered

1. **Decoupled (Terraform + Ansible)**
   - Pros: Flexible, iterate nhanh, mạnh mẽ
   - Cons: Boot time chậm hơn Packer, SSH required

2. **Bake Image (Packer + Ansible builder + Terraform deploy)**
   - Pros: Immutable, boot nhanh, auditable
   - Cons: Build time, storage cost, iteration chậm

3. **AWS SSM (AWS-only)**
   - Pros: Không SSH, IAM-based, audit tốt
   - Cons: AWS lock-in, learning curve

4. **cloud-init (ASG user_data)**
   - Pros: Native, không extra cost
   - Cons: Không idempotent, khó debug

## Decision

Chọn **[Option X]** cho context hiện tại.

## Consequences

### Positive
- ___

### Negative
- ___

### Risks
- ___
```

---

## 4. Tag Taxonomy Chuẩn Cho Dynamic Inventory

Tất cả AWS resources phải có các tags sau (IaC-enforced):

```hcl
tags = {
  # === REQUIRED TAGS (for dynamic inventory) ===
  Name        = "{project}-{env}-{role}-{sequence}"   # Ví dụ: day16-learning-bastion-01
  Project     = "day16"                                # Dự án / workload
  Role        = "bastion"                             # Chức năng: bastion, web, app, db, worker
  ManagedBy   = "terraform"                            # Tool quản lý: terraform, ansible, manual
  Environment = "learning"                             # Môi trường: dev, staging, production
  Owner       = "devops-team"                         # Team chịu trách nhiệm

  # === OPTIONAL TAGS (for cost/allocation) ===
  CostCenter  = "platform"                            # Phân bổ chi phí
  TTL         = "30d"                                 # Resource expiry (nếu có)
}
```

**IAM Policy enforce tags:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": ["ec2:RunInstances"],
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "Null": {
          "aws:RequestTag/Project": "true",
          "aws:RequestTag/Role": "true",
          "aws:RequestTag/ManagedBy": "true",
          "aws:RequestTag/Environment": "true"
        }
      }
    }
  ]
}
```

**Ansible dynamic inventory query:**

```yaml
# aws_ec2.yml - filter theo tags
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
filters:
  tag:Project: day16
  tag:ManagedBy: terraform
  instance-state-name: running
keyed_groups:
  - prefix: role
    key: tags.Role
  - prefix: env
    key: tags.Environment
  - prefix: owner
    key: tags.Owner
```

---

## 5. Bastion Hardening Checklist (CIS-style, 20 items)

### SSH Security (6 items)

```yaml
# 1. SSH key-only authentication
PasswordAuthentication no

# 2. SSH public key authentication
PubkeyAuthentication yes

# 3. PermitRootLogin disabled
PermitRootLogin no

# 4. MaxAuthTries limit
MaxAuthTries 3

# 5. SSH idle timeout
ClientAliveInterval 300
ClientAliveCountMax 2

# 6. SSH port (option: non-standard)
Port 22  # hoặc Port 2222 (security through obscurity, not primary defense)
```

### System Updates (3 items)

```yaml
# 7. Unattended upgrades enabled
# 8. Auto security kernel updates
# 9. Fail2ban brute-force protection
```

### Firewall (3 items)

```yaml
# 10. UFW default deny incoming
# 11. UFW allow SSH from known IP only
# 12. No other inbound ports allowed
```

### Logging & Audit (4 items)

```yaml
# 13. auditd enabled - SSH access logging
# 14. auditd enabled - /etc/ssh/sshd_config changes
# 15. CloudWatch Agent for centralized logging
# 16. Logrotate configured
```

### Kernel Hardening (4 items)

```yaml
# 17. IP forwarding disabled (nếu không cần)
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0

# 18. ICMP redirect ignore
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0

# 19. Source route packets reject
net.ipv4.conf.all.accept_source_route = 0

# 20. Core dump disabled
kernel.core_pattern = |/bin/false
```

---

## 6. Snippet Library

### 6.1. Terraform Output → Static Inventory (Bash + jq)

```bash
#!/usr/bin/env bash
# tf-output-to-inventory.sh
# Usage: terraform output -json | ./tf-output-to-inventory.sh > inventory.ini

set -euo pipefail

SSH_USER="${SSH_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
OUTPUT="${1:-/dev/stdin}"

TERRAFORM_JSON=$(cat "$OUTPUT")

# Extract values
BASTION_IP=$(echo "$TERRAFORM_JSON" | jq -r '.bastion_public_ip.value // empty')
PROJECT=$(echo "$TERRAFORM_JSON" | jq -r '.bastion_tags.value.Project // "unknown")
ENV=$(echo "$TERRAFORM_JSON" | jq -r '.bastion_tags.value.Environment // "unknown')

[[ -z "$BASTION_IP" ]] && { echo "ERROR: bastion_public_ip not found"; exit 1; }

cat <<INVENTORY
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
[all:vars]
ansible_user=${SSH_USER}
ansible_ssh_private_key_file=${SSH_KEY}

[bastion]
${BASTION_IP}

[bastion:vars]
project=${PROJECT}
environment=${ENV}
ansible_python_interpreter=/usr/bin/python3
INVENTORY
```

### 6.2. Terraform Output → Static Inventory (Python)

```python
#!/usr/bin/env python3
"""
from-terraform.py
Ansible dynamic inventory từ Terraform output JSON

Usage:
  ansible-inventory -i from-terraform.py --list
  ansible-playbook -i from-terraform.py playbook.yml
"""
import json
import subprocess
import sys
from pathlib import Path


def get_tf_output() -> dict:
    tf_dir = Path(__file__).parent.parent / "terraform"
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True, text=True, cwd=tf_dir, check=True
    )
    return json.loads(result.stdout)


def build_inventory(tf_output: dict) -> dict:
    ip = tf_output.get("bastion_public_ip", {}).get("value", "")
    tags = tf_output.get("bastion_tags", {}).get("value", {})

    return {
        "_meta": {
            "hostvars": {
                ip: {
                    "ansible_user": "ubuntu",
                    "ansible_ssh_private_key_file": str(Path.home() / ".ssh" / "id_rsa"),
                    "project": tags.get("Project", "unknown"),
                    "role": tags.get("Role", "bastion"),
                }
            }
        },
        "all": {"children": ["bastion"]},
        "bastion": {"hosts": [ip] if ip else []},
    }


if __name__ == "__main__":
    tf_out = get_tf_output()
    inv = build_inventory(tf_out)

    if "--list" in sys.argv:
        print(json.dumps(inv))
    elif "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
        print(json.dumps(inv["_meta"]["hostvars"].get(host, {})))
```

### 6.3. aws_ec2.yml Advanced Filters

```yaml
# ansible/inventory/aws_ec2.yml
plugin: amazon.aws.aws_ec2

# Regions - có thể list nhiều
regions:
  - us-east-1
  - us-west-2

# Strict host matching
strict: false

# Filters - AND logic giữa các filter
filters:
  # Instance state
  instance-state-name: running
  # Required tags
  tag:Project: day16
  tag:ManagedBy: terraform
  # Instance type
  instance-type: t3.micro
  # Non-terminated
  tag:TTL: "!null"

# Hostname strategy
hostnames:
  - tag:Name                    # Ưu tiên: dùng tag Name
  - private-ip-address          # Fallback: private IP
  - public-ip-address           # Fallback: public IP

# Tự động tạo groups từ tags
keyed_groups:
  - prefix: role
    key: tags.Role
    separator: ""
  - prefix: env
    key: tags.Environment
  - prefix: project
    key: tags.Project
  - prefix: owner
    key: tags.Owner
  - prefix: instance_type
    key: instance_type

# Include mapa (map variables)
compose:
  ansible_port: 22
  ansible_user: "'ubuntu'"
  project: tags.Project
```

### 6.4. Packer Template Skeleton (HCL2)

```hcl
# bastion-ami.pkr.hcl
source "amazon-ebs" "ubuntu" {
  ami_name      = "bastion-hardened-${formatdate("YYYY-MM-DD", timestamp())}"
  instance_type = "t3.micro"
  region        = "us-east-1"
  source_ami    = "ami-055a7d7781d73c004"  # Ubuntu 22.04 LTS

  ssh_username = "ubuntu"

  tags = {
    Name        = "bastion-hardened"
    Project     = "day16"
    Role        = "bastion"
    ManagedBy   = "packer"
    BuiltAt     = formatdate("YYYY-MM-DD HH:mm:ss Z", timestamp())
  }

  # Lifecycle policy
  ami_users = var.account_ids  # Share với account khác
}

build {
  name = "bastion-hardening"

  sources = ["source.amazon-ebs.ubuntu"]

  # Ansible provisioner - dùng role đã có
  provisioner "ansible" {
    playbook_file = "../ansible/playbooks/bastion-hardening.yml"
    ansible_env_vars = [
      "ANSIBLE_CONFIG=../ansible/ansible.cfg"
    ]
    extra_arguments = [
      "--tags", "hardening",
      "--become"
    ]
  }

  # Post-processor: copy AMI sang region khác (optional)
  post-processor "tag" {
    tags = {
      BuildDate = timestamp()
    }
  }
}
```

### 6.5. cloud-init user_data Example

```yaml
# user_data.yml - cho ASG launch template
# Content-Type: text/cloud-config

#cloud-config
package_update: true
package_upgrade: true

packages:
  - curl
  - wget
  - vim
  - git
  - unattended-upgrades
  - fail2ban
  - node_exporter

# Write files
write_files:
  - path: /etc/ssh/sshd_config
    permissions: '0600'
    owner: root:root
    content: |
      Port 22
      PermitRootLogin no
      PasswordAuthentication no
      PubkeyAuthentication yes
      MaxAuthTries 3
      ClientAliveInterval 300

# Run commands
runcmd:
  - systemctl enable --now unattended-upgrades
  - systemctl enable --now fail2ban
  - systemctl enable --now sshd
  - curl -s http://localhost:9100/metrics | head -1

# Set hostname
hostname: bastion
manage_etc_hosts: true

# Final message
final_message: "Bastion host ready after $UPTIME seconds"
```

### 6.6. Provisioner Anti-pattern vs Alternatives

```hcl
# ❌ ANTI-PATTERN: local-exec gọi ansible
resource "aws_instance" "bastion" {
  provisioner "local-exec" {
    command = <<-EOT
      ansible-playbook \
        -i "${self.public_ip}," \
        ../ansible/bastion.yml
    EOT
  }
}

# ❌ ANTI-PATTERN: remote-exec (harder to debug)
resource "aws_instance" "bastion" {
  provisioner "remote-exec" {
    inline = [
      "curl -sL https://get.docker.com | sh",
      "docker run -d nginx"
    ]
  }
}
```

**Alternatives:**

| Anti-pattern | Alternative | Code |
|-------------|-------------|------|
| local-exec ansible | Decoupled pipeline | Stage 1: terraform apply → Stage 2: ansible-playbook |
| remote-exec docker | user_data cloud-init | user_data with docker install |
| local-exec script | null_resource + triggers | Terraform state-driven execution |
| remote-exec config | Ansible post-provision | Run ansible sau khi terraform xong |

---

## 7. Cost Optimization Checklist

### Bastion Host Options

| Option | Monthly Cost | SSH Required | Notes |
|--------|-------------|--------------|-------|
| EC2 t3.micro + NAT Gateway | ~$40/month | Yes | Traditional approach |
| EC2 t3.micro + SSM | ~$8/month | No | **Recommended** |
| EC2 Spot t3.micro + SSM | ~$2-3/month | No | Non-production |
| Fargate Task (bastion) | ~$5-10/month | No | Serverless option |

### SSM Session Manager Setup

```hcl
# Terraform - IAM Role cho SSM
data "aws_iam_policy" "ssm_core" {
  name = "AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = data.aws_iam_policy.ssm_core.arn
}

# Security Group - KHÔNG cần mở port 22
resource "aws_security_group" "bastion" {
  # Ingress: KHÔNG cần SSH inbound!
  # Chỉ cần outbound để install packages
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

```bash
# SSH vào bastion qua SSM (không cần IP, không cần key)
aws ssm start-session \
  --target i-0abc123def456

# Copy file qua SSM
aws ssm put-file \
  --local-path ./config.yml \
  --remote-path /tmp/config.yml \
  --target i-0abc123def456

# SCP-like via SSM
aws ssm get-file \
  --remote-path /var/log/app.log \
  --local-path ./app.log \
  --target i-0abc123def456
```

### AMI Storage Cost Optimization

| AMI Type | Storage | Monthly Cost (50 AMIs) |
|----------|---------|----------------------|
| gp3 30GB | 1500 GB | ~$114/month |
| gp3 30GB + lifecycle policy | ~300 GB (retained) | ~$23/month |
| gp3 30GB + cross-region copy | ~150 GB | ~$11/month |

**Lifecycle policy cho AMI:**

```hcl
resource "aws_lifecycle_policy" "ami_cleanup" {
  name        = "ami-cleanup-policy"
  description = "Delete AMIs older than 30 days"

  policy = jsonencode({
    Rules = [{
      Description  = "Expire AMIs older than 30 days"
      RuleId      = "expire-old-amis"
      Target      = { ResourceType = "IMAGE" }
      Timing = {
        NoncurrentDays = 1
        DaysUntilExpiring = 30
      }
    }]
  })
}
```

---

## 8. Ansible Vault trong Terraform-Ansible Pipeline

```bash
# Mã hóa sensitive variables
ansible-vault encrypt ansible/group_vars/bastion/secrets.yml
# → group_vars/bastion/secrets.yml.vault

# Commit encrypted file
git add ansible/group_vars/bastion/secrets.yml.vault
git commit -m "Add encrypted secrets for bastion"

# CI/CD pipeline
ansible-playbook \
  -i inventory/aws_ec2.yml \
  playbooks/bastion-hardening.yml \
  --vault-id vault-pass.txt@password-source
```

**CI/CD secrets management:**

```yaml
# GitHub Actions example
# .github/workflows/bastion.yml
name: Bastion Hardening

on:
  push:
    paths:
      - 'ansible/**'
      - 'terraform/**'

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Terraform Apply
        run: |
          cd terraform
          terraform init -backend-config=bucket=${{ secrets.TF_BUCKET }}
          terraform apply -auto-approve -var="key_name=${{ secrets.SSH_KEY_NAME }}"
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

  ansible:
    needs: terraform
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Ansible
        run: |
          pip install ansible amazon-ec2-ansible-inventory boto3
          ansible-playbook \
            -i inventory/aws_ec2.yml \
            playbooks/bastion-hardening.yml \
            --vault-id ${{ secrets.VAULT_ID }}@prompt
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          ANSIBLE_VAULT_PASSWORD: ${{ secrets.VAULT_PASSWORD }}
```

---

## 9. Terraform Ansible Provisioner: When It's Acceptable

`local-exec` / `remote-exec` chỉ acceptable trong 3 trường hợp:

### Case 1: One-off bootstrap script (dev only)

```hcl
# Chỉ dùng trong -dev workspace
resource "null_resource" "bootstrap_dev" {
  count = terraform.workspace == "dev" ? 1 : 0

  provisioner "local-exec" {
    command = "echo 'Dev only: initial setup complete'"
  }
}
```

### Case 2: Generate inventory file (acceptable)

```hcl
# Tạo inventory từ Terraform output - ĐƯỢC
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/inventory.tpl", {
    bastion_ip = aws_instance.bastion.public_ip
  })
  filename = "${path.module}/../ansible/inventory/from-tf.ini"
}
```

### Case 3: Notify external system (webhook, Slack)

```hcl
# Notify Slack khi infrastructure ready - ĐƯỢC
resource "null_resource" "notify_ready" {
  provisioner "local-exec" {
    command = <<-EOT
      curl -X POST ${var.slack_webhook} \
        -H 'Content-type: application/json' \
        --data '{"text":"Bastion ready: ${aws_instance.bastion.public_ip}"}'
    EOT
  }
}
```

---

## 10. Quick Reference Commands

```bash
# Terraform
terraform init
terraform plan -var="key_name=bastion-key"
terraform apply -auto-approve -var="key_name=bastion-key"
terraform output -json
terraform output -raw bastion_public_ip
terraform destroy -auto-approve

# Ansible Inventory
ansible-inventory -i inventory/aws_ec2.yml --graph
ansible-inventory -i inventory/aws_ec2.yml --list
ansible-inventory -i inventory/aws_ec2.yml --host <ip>
ansible-inventory -i inventory/from-terraform.py --list

# Ansible Execution
ansible all -i inventory/aws_ec2.yml -m ping
ansible-playbook -i inventory/aws_ec2.yml playbooks/bastion-hardening.yml
ansible-playbook -i inventory/aws_ec2.yml playbooks/bastion-hardening.yml --check
ansible-playbook -i inventory/aws_ec2.yml playbooks/bastion-hardening.yml --start-at-task="Deploy hardened sshd_config"

# Vault
ansible-vault encrypt group_vars/all/secrets.yml
ansible-vault decrypt group_vars/all/secrets.yml
ansible-vault view group_vars/all/secrets.yml
ansible-playbook --vault-id @prompt playbook.yml

# SSM
aws ssm start-session --target i-xxxxx
aws ssm describe-instance-information
aws ssm send-command --document-name AWS-RunShellScript --targets "InstanceIds=[i-xxxxx]" --parameters commands=["uptime"]
```
