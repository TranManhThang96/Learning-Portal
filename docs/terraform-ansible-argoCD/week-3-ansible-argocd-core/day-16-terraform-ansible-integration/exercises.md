# Day 16 - Terraform + Ansible Integration: Exercises

**Độ khó:** Intermediate → Advanced
**Thời gian ước tính:** 30-60 phút mỗi challenge
**Prerequisites:** Hoàn thành lesson.md Day 16, có AWS account với free tier

---

## Challenge 1: Static Inventory → Dynamic Inventory Migration

**Mức độ:** Intermediate
**Thời gian:** 30 phút

### Mô tả

Team đang dùng static inventory với hard-code IP, đã commit vào git. Bạn cần migrate sang dynamic inventory mà không break production pipeline.

### Starter Code (Có vấn đề)

```ini
# ansible/inventory/hosts.ini - FILE CẦN REFACTOR
# ❌ PROBLEM: Hard-code IP, outdated, committed vào git

[webservers]
54.210.123.45 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-web.pem
54.211.234.56 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-web.pem

[appservers]
54.220.135.67 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-app.pem

[dbservers]
54.230.246.78 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-db.pem
54.240.257.89 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-db.pem

[monitoring]
54.250.268.90 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/prod-mon.pem
```

### Terraform Infrastructure (Đã có)

```hcl
# terraform/main.tf - Infrastructure đã tạo
# Web tier
resource "aws_instance" "web" {
  count         = 2
  ami           = var.web_ami
  instance_type = var.instance_type
  tags = {
    Name        = "prod-web-${count.index + 1}"
    Project     = "day16"
    Role        = "web"
    ManagedBy   = "terraform"
    Environment = "production"
    Owner       = "platform-team"
  }
}

# App tier
resource "aws_instance" "app" {
  count         = 1
  ami           = var.app_ami
  instance_type = var.instance_type
  tags = {
    Name        = "prod-app-1"
    Project     = "day16"
    Role        = "app"
    ManagedBy   = "terraform"
    Environment = "production"
    Owner       = "platform-team"
  }
}

# DB tier
resource "aws_instance" "db" {
  count         = 2
  ami           = var.db_ami
  instance_type = "r6i.xlarge"
  tags = {
    Name        = "prod-db-${count.index + 1}"
    Project     = "day16"
    Role        = "database"
    ManagedBy   = "terraform"
    Environment = "production"
    Owner       = "data-team"
  }
}

# Monitoring
resource "aws_instance" "monitoring" {
  count         = 1
  ami           = var.monitoring_ami
  instance_type = "t3.medium"
  tags = {
    Name        = "prod-monitoring-1"
    Project     = "day16"
    Role        = "monitoring"
    ManagedBy   = "terraform"
    Environment = "production"
    Owner       = "platform-team"
  }
}
```

### Yêu cầu

**1. Tạo `ansible/inventory/aws_ec2.yml`**

```yaml
# ansible/inventory/aws_ec2.yml
# TODO: Viết dynamic inventory config
# Hints:
# - plugin: amazon.aws.aws_ec2
# - Regions: us-east-1
# - Filters: tag:Project=day16, instance-state-name=running
# - keyed_groups: theo Role tag
# - Compose: ansible_user từ tag (hoặc hardcode ubuntu)
# - Hostnames: tag:Name
```

**2. Tạo `ansible/inventory/legacy-migration.yml`**

```yaml
# ansible/inventory/legacy-migration.yml
# Script migration: static inventory vẫn hoạt động
# trong khi dynamic inventory được verify
# TODO: Implement
```

**3. Migration verification playbook**

```yaml
# ansible/playbooks/migration-verify.yml
# TODO:
# - Chạy ping trên cả static và dynamic inventory
# - So sánh kết quả
# - Report hosts có trong static nhưng không có trong dynamic
# - Report hosts mới trong dynamic không có trong static
```

**4. Git commit strategy**

```bash
# TODO: Viết script migration
# Step 1: Commit aws_ec2.yml (chưa xóa hosts.ini)
# Step 2: Chạy pipeline với cả 2 inventory
# Step 3: Verify dynamic inventory thấy đủ host
# Step 4: Xóa hosts.ini, commit
# Step 5: Cleanup legacy files
```

### Expected Output

```bash
# Sau khi migration hoàn thành:
ansible-inventory -i inventory/aws_ec2.yml --graph

# @all:
#   |--@role_database:
#   |  |--prod-db-1
#   |  |--prod-db-2
#   |--@role_monitoring:
#   |  |--prod-monitoring-1
#   |--@role_web:
#   |  |--prod-web-1
#   |  |--prod-web-2
#   |--@role_app:
#   |  |--prod-app-1
#   |--@ungrouped:
```

### Hints

- Dùng `keyed_groups` để tự động tạo groups theo tag Role
- `compose` block để set `ansible_user` mặc định
- Test với `ansible-inventory --list` trước khi chạy playbook

---

## Challenge 2: Packer Build AMI với Ansible Provisioner

**Mức độ:** Advanced
**Thời gian:** 60 phút

### Mô tả

Build production AMI bằng Packer, dùng Ansible role `node_exporter` (từ Day 15) làm provisioner. Sau đó deploy AMI bằng Terraform, so sánh boot time với Day 16 approach.

### Cấu trúc project

```
day-16-ex2-packer/
├── packer/
│   ├── bastion-ami.pkr.hcl
│   └──.pkrvars.hcl/
│       └── us-east-1.pkrvars.hcl
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── ansible/
    └── playbooks/
        └── bastion-hardening.yml  # (từ Day 16)
```

### Yêu cầu

**1. Tạo Packer template `packer/bastion-ami.pkr.hcl`**

```hcl
# packer/bastion-ami.pkr.hcl
# TODO: Implement
#
# Hints:
# - Source: amazon-ebs
# - ami_name: bastion-hardened-${formatdate("YYYY-MM-DD", timestamp())}
# - instance_type: t3.micro
# - source_ami: Ubuntu 22.04 LTS AMI (tìm ami-055a7d7781d73c004)
# - ssh_username: ubuntu
# - tags: Name, Project, Role, ManagedBy, BuiltAt
#
# Build provisioner:
# - provisioner "ansible" {
#     playbook_file   = "../ansible/playbooks/bastion-hardening.yml"
#     ansible_env_vars = ["ANSIBLE_CONFIG=../ansible/ansible.cfg"]
#   }
#
# Post-processors:
# - tag: thêm build metadata
# - manifest: xuất AMI ID ra file
```

**2. Tạo `packer/us-east-1.pkrvars.hcl`**

```hcl
# packer/us-east-1.pkrvars.hcl
# TODO: Variables cho packer
# Hints: aws_region, source_ami, instance_type
```

**3. Tạo Terraform `terraform/main.tf` dùng Packer AMI**

```hcl
# terraform/main.tf
# TODO:
# - data "aws_ami" "bastion" để lấy AMI từ Packer
# - Filter: tag:Name=bastion-hardened-*, most_recent=true
# - aws_instance dùng AMI từ data source
# - Không cần Ansible post-provision (đã bake trong AMI)
```

**4. Benchmark comparison**

```bash
# Script đo boot time
# Deploy 1 instance từ Packer AMI
# Deploy 1 instance từ base AMI + Ansible
# So sánh:
# - Time from "terraform apply" → SSH ready
# - Time from "terraform apply" → node_exporter responding

echo "=== Boot Time Benchmark ==="
echo "Packer AMI:"
# TODO: Measure time
echo "Base AMI + Ansible:"
# TODO: Measure time
```

**5. Viết analysis document**

```markdown
# boot-time-analysis.md

## Methodology
- [ ] Describe test setup
- [ ] Number of iterations: 3
- [ ] Measurement tool

## Results

| Approach | Avg Boot Time | Std Dev | node_exporter Ready |
|----------|---------------|---------|---------------------|
| Packer AMI | ~45s | ±5s | Yes (baked-in) |
| Base AMI + Ansible | ~4 min | ±30s | Yes (bootstrap) |

## Analysis
- Boot time difference: ___
- Cost difference: ___
- When to use each approach: ___

## Recommendation
```

### Hints

- Packer build mất 5-15 phút lần đầu
- Dùng `amazon-ebs` builder, không phải `amazon-ebssurrogate`
- Ansible provisioner trong Packer chạy trên temporary instance
- AMI được copy vào account tự động sau khi build
- Cleanup: `packer-tools delete` hoặc AWS Console

---

## Challenge 3: Multi-tier Infrastructure với Dynamic Inventory

**Mức độ:** Advanced
**Thời gian:** 60 phút

### Mô tả

Thiết kế 3-tier infrastructure (web + app + db) với 3 Ansible roles khác nhau. Dùng dynamic inventory `keyed_groups` để auto-group hosts theo tags.

### Infrastructure Design

```
┌─────────────────────────────────────────────────────────────┐
│  VPC (10.0.0.0/16)                                         │
│                                                             │
│  ┌── Web Tier (public subnet) ──────────────────────────┐  │
│  │  ASG: 2-5 instances (t3.micro)                      │  │
│  │  Tags: Role=web, Environment=staging                │  │
│  │  Ports: 80, 443 from ALB SG only                    │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌── App Tier (private subnet) ─────────────────────────┐  │
│  │  ASG: 2-4 instances (t3.small)                      │  │
│  │  Tags: Role=app, Environment=staging                 │  │
│  │  Ports: 8080 from Web SG only                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌── DB Tier (private subnet, isolated) ───────────────┐  │
│  │  RDS Aurora PostgreSQL (db.t3.medium)               │  │
│  │  Tags: Role=database, Environment=staging            │  │
│  │  Port: 5432 from App SG only                         │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌── Bastion (public subnet) ───────────────────────────┐  │
│  │  1 instance (t3.micro)                              │  │
│  │  Tags: Role=bastion, Environment=staging            │  │
│  │  Ports: 22 from MY_IP only                          │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Yêu cầu

**1. Terraform: `terraform/multi-tier.tf`**

```hcl
# terraform/multi-tier.tf
# TODO: Implement
#
# Resources cần tạo:
# - aws_vpc (hoặc dùng default VPC)
# - aws_security_group per tier
# - aws_instance cho bastion
# - aws_db_instance cho RDS Aurora
#
# IMPORTANT: Tag schema chuẩn:
# {
#   Project     = "day16-ex3"
#   Role        = "web" | "app" | "database" | "bastion"
#   ManagedBy   = "terraform"
#   Environment = "staging"
#   Owner       = "platform-team"
# }
```

**2. Ansible: `ansible/inventory/multi-tier.yml`**

```yaml
# ansible/inventory/multi-tier.yml
# Dynamic inventory với advanced keyed_groups
#
# TODO:
# - plugin: amazon.aws.aws_ec2
# - Filters: tag:Project=day16-ex3
# - keyed_groups:
#     - prefix: role (key: tags.Role)
#     - prefix: env (key: tags.Environment)
#     - prefix: tier (key: tags.Role) # Alias cho role
#     - key: tags.Owner → prefix: owner
# - compose:
#     - ansible_user: "'ubuntu'"
#     - environment: "tags.Environment"
```

**3. Ansible Roles cho từng tier**

**`ansible/roles/web-server/tasks/main.yml`**

```yaml
# ansible/roles/web-server/tasks/main.yml
# TODO:
# - Install nginx
# - Configure nginx reverse proxy (app:8080)
# - Setup health check endpoint /health
# - Install node_exporter (reuse từ Day 15)
# - Handler: restart nginx on config change
```

**`ansible/roles/app-server/tasks/main.yml`**

```yaml
# ansible/roles/app-server/tasks/main.yml
# TODO:
# - Install python3 + pip
# - Install gunicorn + flask (sample app)
# - Create systemd service
# - Config: DATABASE_URL từ variable
# - Install node_exporter
# - Handler: restart gunicorn
```

**`ansible/roles/db-client/tasks/main.yml`**

```yaml
# ansible/roles/db-client/tasks/main.yml
# TODO:
# - Install postgresql-client
# - Test connection đến RDS endpoint
# - Create application database user
# - Store RDS endpoint trong /etc/environment
# - Install node_exporter
```

**4. Playbook: `ansible/playbooks/multi-tier-deploy.yml`**

```yaml
# ansible/playbooks/multi-tier-deploy.yml
#
# TODO:
# - hosts: role_web → role app-server
# - hosts: role_app → role app-server
# - hosts: role_database → db-client
# - hosts: role_bastion → bastion-hardening
#
# Pre-task: Wait for SSH
# Post-task: Smoke test mỗi tier
```

**5. Smoke test playbook: `ansible/playbooks/smoke-test.yml`**

```yaml
# ansible/playbooks/smoke-test.yml
#
# TODO:
# - Web tier: curl http://<web-ip>/health
# - App tier: curl http://<app-ip>:8080/health
# - DB tier: psql -h <rds-endpoint> -U postgres -c "SELECT 1"
# - Bastion: Verify fail2ban, UFW active
# - All: Verify node_exporter on :9100
```

### Expected Inventory Structure

```bash
ansible-inventory -i inventory/multi-tier.yml --graph

# @all:
#   |--@env_staging:
#   |  |--prod-web-1
#   |  |--prod-web-2
#   |  |--prod-app-1
#   |  |--prod-app-2
#   |  |--prod-db-1
#   |  |--prod-bastion-1
#   |--@role_app:
#   |  |--prod-app-1
#   |  |--prod-app-2
#   |--@role_bastion:
#   |  |--prod-bastion-1
#   |--@role_database:
#   |  |--prod-db-1
#   |--@role_web:
#   |  |--prod-web-1
#   |  |--prod-web-2
#   |--@ungrouped:
```

### Hints

- Dùng `ansible_host` variable trong inventory để override hostname resolution
- RDS không có SSH → db-client role chỉ test connection từ bastion hoặc app tier
- Web tier cần security group cho phép traffic từ ALB

---

## Challenge 4: Debug Dynamic Inventory (Có lỗi cài sẵn)

**Mức độ:** Intermediate
**Thời gian:** 45 phút

### Mô tả

5 host đã được Terraform tạo nhưng dynamic inventory chỉ thấy 3/5. Bạn cần debug và fix.

### Buggy Terraform Code (Có 3 bugs cố ý)

```hcl
# terraform/main.tf - CÓ 3 BUGS CỐ Ý

# Bug 1: Thiếu tag Role trên bastion
resource "aws_instance" "bastion" {
  ami           = var.bastion_ami
  instance_type = var.instance_type
  tags = {
    Name        = "prod-bastion-1"
    Project     = "day16-ex4"   # ✓
    # Role tag: THIẾU! ← Bug 1
    ManagedBy   = "terraform"   # ✓
    Environment = "staging"     # ✓
  }
}

# Bug 2: Thiếu tag Project trên app-2
resource "aws_instance" "app" {
  count         = 2
  ami           = var.app_ami
  instance_type = var.instance_type
  tags = {
    Name        = "prod-app-${count.index + 1}"
    Project     = count.index == 0 ? "day16-ex4" : ""  # ← Bug 2: app-2 không có Project
    Role        = "app"
    ManagedBy   = "terraform"
    Environment = "staging"
  }
}

# Bug 3: Region trong Terraform khác với inventory config
# Terraform đang chạy region: us-west-2 ← Bug 3
# aws_ec2.yml config region: us-east-1 ← Bug 3
```

### Buggy Dynamic Inventory Config

```yaml
# ansible/inventory/aws_ec2.yml - CÓ BUG
plugin: amazon.aws.aws_ec2

# Bug: Region mismatch (Terraform tạo ở us-west-2)
regions:
  - us-east-1    # ← Bug: phải là us-west-2

filters:
  tag:Project: day16-ex4
  instance-state-name: running

keyed_groups:
  - prefix: role
    key: tags.Role

hostnames:
  - tag:Name
```

### Ansible Inventory Debug Script

```bash
#!/usr/bin/env bash
# debug-inventory.sh
# Debug dynamic inventory issues

set -e

echo "=== Debug Dynamic Inventory ==="

echo ""
echo "1. Check Python dependencies"
python3 -c "import boto3; import json; print('boto3 OK')" || echo "boto3 MISSING"

echo ""
echo "2. Check AWS credentials"
aws sts get-caller-identity --query Account || echo "AWS credentials INVALID"

echo ""
echo "3. List ALL EC2 instances with Project=day16-ex4 tag"
aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=day16-ex4" \
  --query 'Reservations[].Instances[].[InstanceId,State.Name,Tags[?Key==`Role`].Value|[0],Tags[?Key==`Project`].Value|[0],PrivateIpAddress]' \
  --output table

echo ""
echo "4. List instances filtered by aws_ec2.yml criteria"
# Simulate what the plugin does
aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=day16-ex4" \
          "Name=instance-state-name,running" \
  --query 'length(Reservations[].Instances[])'

echo ""
echo "5. Compare: Expected hosts vs Actual hosts"
# Expected: bastion, app-1, app-2, web-1, web-2 = 5 hosts
# Actual: chỉ 3 host →找出哪 2 host bị miss

echo ""
echo "6. IAM permissions check"
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/day16-ex4-bastion-role" \
  --action-names "ec2:DescribeInstances" \
  --resource-arns "*" \
  --query 'EvaluationResults[].EvalDecision'
```

### Yêu cầu

**1. Chạy debug script và phân tích output**

```bash
# Chạy và capture output
./debug-inventory.sh 2>&1 | tee debug-output.txt

# Phân tích:
# - Bug 1: bastion không có Role tag → missing từ role_bastion group
# - Bug 2: app-2 không có Project tag → không match filter
# - Bug 3: Region mismatch → us-west-2 vs us-east-1
```

**2. Fix Terraform code để tất cả 5 hosts đều có đủ tags**

```hcl
# Fix terraform/main.tf
# - Bastion: thêm Role=bastion tag
# - App-2: thêm Project=day16-ex4 tag
```

**3. Fix aws_ec2.yml inventory config**

```yaml
# Fix ansible/inventory/aws_ec2.yml
# - Đổi region thành us-west-2
# - Thêm fallback filter hoặc verbose logging
```

**4. Verify fix**

```bash
# Sau khi fix:
# 1. terraform apply (update tags)
# 2. Chạy lại ansible-inventory --graph
# 3. Verify 5/5 hosts xuất hiện

ansible-inventory -i inventory/aws_ec2.yml --graph
# Expected: 5 hosts trong groups
```

### Expected Fixes

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Bastion missing | Thiếu `Role=bastion` tag | Thêm vào tags block |
| app-2 missing | `Project=""` tag | Fix ternary: `"day16-ex4"` |
| 2 hosts missing | Region mismatch | Đổi `us-east-1` → `us-west-2` |

### Hints

- Dùng `terraform apply` sau khi fix để update tags
- AWS tags update cần vài giây → đợi hoặc force refresh
- `aws ec2 describe-instances` không cache nhưng boto3 SDK có thể cache

---

## Challenge 5: Production Incident - Ansible Race Condition

**Mức độ:** Advanced
**Thời gian:** 60 phút

### Mô tả

Production incident: 2 CI/CD pipelines chạy `ansible-playbook` đồng thời trên cùng fleet gây race condition. Bạn cần thiết kế và implement giải pháp.

### Incident Scenario

```
Timeline:
────────────────────────────────────────────────────────────────►

Pipeline A: terraform apply (thay đổi SG) ────────►
Pipeline B: terraform apply (thay đổi user-data) ──►

Pipeline A: ansible-playbook --tags=security ───────►
Pipeline B: ansible-playbook --tags=monitoring ─────►

    ↓                          ↓
    Host A: fail2ban restart   Host A: sshd_config thay đổi
    (Ansible A)                (Ansible B)
    ↓                          ↓
    Host A: SSH broken         Host A: SSH broken
    (both pipelines)           (both pipelines)

ERROR: ansible-playbook FAILED
fatal: [host-1]: UNREACHABLE! => {
  "msg": "Failed to connect to the host via ssh"
}
```

### Current (Broken) CI/CD Configuration

```yaml
# .github/workflows/deploy.yml - BROKEN
name: Infrastructure Deploy

on:
  push:
    paths:
      - 'terraform/**'
      - 'ansible/**'

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Terraform Apply
        run: |
          cd terraform
          terraform apply -auto-approve

  ansible:
    needs: terraform
    runs-on: ubuntu-latest
    # BUG: Có thể chạy song song với pipeline khác
    # nếu trigger từ 2 different commits
    steps:
      - uses: actions/checkout@v4
      - name: Run Ansible
        run: |
          ansible-playbook \
            -i inventory/aws_ec2.yml \
            playbooks/bastion-hardening.yml
```

### Yêu cầu

**1. Phân tích root cause**

```markdown
# INCIDENT-ANALYSIS.md

## Timeline
- [ ] Chi tiết timeline từ lúc xảy ra đến khi phát hiện

## Root Cause Analysis
- [ ] Tại sao 2 pipeline chạy đồng thời?
- [ ] Tại sao race condition gây SSH break?
- [ ] Thứ tự events dẫn đến incident

## Impact
- [ ] Bao nhiêu host bị ảnh hưởng
- [ ] Downtime
- [ ] Services affected

## Lessons Learned
- [ ] 3 điều cần cải thiện
```

**2. Thiết kế giải pháp**

```yaml
# SOLUTION-DESIGN.md
## Option A: Ansible Lock File (file-based mutex)
## Option B: Terraform/Ansible Lock (state-based)
## Option C: Pipeline Serialization (GitHub Actions concurrency)
## Option D: Ansible Async + Retry + Idempotency

# Chọn Option C (simplest, most effective):
# - GitHub Actions concurrency group
# - Auto-cancel pending runs
# - Chỉ 1 pipeline chạy tại 1 thời điểm per environment
```

**3. Implement GitHub Actions concurrency lock**

```yaml
# .github/workflows/deploy.yml - FIXED
name: Infrastructure Deploy

# FIX: Concurrency group prevents parallel runs
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Cancel in-progress khi có run mới

on:
  push:
    branches:
      - main
    paths:
      - 'terraform/**'
      - 'ansible/**'

env:
  ANSIBLE_CONFIG: ansible/ansible.cfg

jobs:
  # === Single pipeline: Terraform + Ansible serial ===
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Terraform Init
        run: |
          cd terraform
          terraform init -backend-config=bucket=${{ secrets.TF_BUCKET }}

      - name: Terraform Plan
        id: plan
        run: |
          terraform plan -out=tfplan
          echo "changed=$(terraform show -json tfplan | jq '.changes != null')" >> $GITHUB_OUTPUT

      - name: Terraform Apply
        if: steps.plan.outputs.changed == 'true'
        run: |
          terraform apply -auto-approve tfplan

      # === Wait for SSH ===
      - name: Wait for instances SSH ready
        run: |
          # Ansible inventory check
          ansible-inventory -i inventory/aws_ec2.yml --graph
          # Wait up to 5 minutes
          for i in $(seq 1 30); do
            if ansible all -i inventory/aws_ec2.yml -m ping --timeout 10 2>/dev/null; then
              echo "All hosts reachable"
              break
            fi
            echo "Waiting for hosts... attempt $i/30"
            sleep 10
          done

      # === Ansible Apply ===
      - name: Install Ansible dependencies
        run: |
          pip install ansible amazon-ec2-ansible-inventory boto3

      - name: Run Ansible Playbook
        run: |
          ansible-playbook \
            -i inventory/aws_ec2.yml \
            playbooks/bastion-hardening.yml \
            --vault-id ${{ secrets.VAULT_ID }}@prompt

      # === Verify ===
      - name: Post-deploy verification
        run: |
          ansible all -i inventory/aws_ec2.yml -m uri \
            -a "url=http://{{ '{{' }} ansible_host {{ '}}' }}:9100/metrics" \
            --fork 5
```

**4. Implement Ansible lock (dùng lock file)**

```yaml
# ansible/roles/ansible-lock/tasks/main.yml
---
# Role để acquire/release Ansible lock trước khi chạy playbook

- name: Create lock directory
  file:
    path: /var/tmp/ansible-locks
    state: directory
    mode: '0755'

- name: Acquire lock (fail if locked)
  shell: |
    LOCKFILE="/var/tmp/ansible-locks/{{ inventory_hostname }}.lock"
    if mkdir "$LOCKFILE" 2>/dev/null; then
      echo "$$" > "$LOCKFILE"
      exit 0
    else
      LOCKPID=$(cat "$LOCKFILE" 2>/dev/null)
      if kill -0 "$LOCKPID" 2>/dev/null; then
        echo "Host is locked by PID $LOCKPID"
        exit 1
      else
        # Stale lock, remove and retry
        rm -f "$LOCKFILE"
        mkdir "$LOCKFILE" && echo "$$" > "$LOCKFILE"
      fi
    fi
  args:
    executable: /bin/bash
  register: lock_acquire
  failed_when: lock_acquire.rc != 0

- name: Set lock fact
  set_fact:
    ansible_lock_file: "/var/tmp/ansible-locks/{{ inventory_hostname }}.lock"
```

**5. Implement Terraform state lock (dùng DynamoDB)**

```hcl
# terraform/backend.tf
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "day16/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    # State lock qua DynamoDB
    # (tự động bởi S3 backend)
  }
}
```

**6. Write runbook cho incident tương lai**

```markdown
# RUNBOOK-ANSIBLE-RACE.md

## Symptom
Ansible unreachable error khi 2 pipeline chạy song song

## Diagnosis
```bash
# Kiểm tra có pipeline nào đang chạy
gh run list --workflow=deploy.yml --status in_progress

# Kiểm tra Ansible lock
ansible all -i inventory/aws_ec2.yml -m file \
  -a "path=/var/tmp/ansible-locks state=directory"

# Kiểm tra Terraform state lock
terraform force-unlock <LOCK_ID>
```

## Resolution
1. Cancel pending CI/CD runs
2. Chờ current run complete
3. Verify all hosts SSH-able
4. Retry failed pipeline

## Prevention
- [x] GitHub Actions concurrency group
- [ ] Terraform workspace lock (future)
- [ ] Ansible lock file role (optional enhancement)
```

### Hints

- GitHub Actions `concurrency` là cách nhanh nhất và hiệu quả nhất
- Ansible không có built-in lock → cần external coordination
- Terraform S3 backend tự động lock qua DynamoDB
- Incident review nên có trong CI/CD post-mortem template

---

## Challenge 6: Hybrid Approach - Packer + Ansible + Terraform + ADR

**Mức độ:** Expert
**Thời gian:** 90 phút

### Mô tả

Thiết kế hybrid architecture: Packer build base AMI (OS + hardening), Ansible apply post-provision config (app-specific), Terraform deploy. Viết ADR đầy đủ phân tích trade-off.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Build Pipeline (Packer)                                   │
│                                                             │
│  Base AMI (Ubuntu 22.04 LTS)                              │
│       ↓                                                     │
│  Packer + Ansible (provisioner)                           │
│  ├── OS hardening (bastion-hardening role)                │
│  ├── CloudWatch Agent                                     │
│  ├── SSM Agent                                            │
│  └── node_exporter                                        │
│       ↓                                                     │
│  Golden AMI: bastion-hardened-2026-05-14                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                    ↓ Deploy Pipeline
┌─────────────────────────────────────────────────────────────┐
│  Terraform                                                  │
│                                                             │
│  ├── data "aws_ami" "bastion" (from Packer)               │
│  ├── aws_instance (from Golden AMI)                        │
│  └── aws_iam_role + aws_ssm_session                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                    ↓ Post-Provision Pipeline
┌─────────────────────────────────────────────────────────────┐
│  Ansible (chỉ cho app-specific config)                     │
│                                                             │
│  ├── Special hardening rules cho app tier                  │
│  ├── App-specific secrets (Vault)                          │
│  └── One-off operations không bake vào AMI                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Yêu cầu

**1. Packer Template: `packer/hardened-bastion.pkr.hcl`**

```hcl
# packer/hardened-bastion.pkr.hcl
#
# TODO: Full Packer template với:
# - Source: amazon-ebs ubuntu
# - Build provisioner: ansible (dùng bastion-hardening role)
# - Post-processor: tag + manifest
# - Variables cho region, ami_name_prefix
# - Validation blocks
#
# Best practices:
# - Dùng variable cho tất cả hard-coded values
# - IMDSv2 required
# - Encrypted snapshot (default: true)
# - tpm-support (for Nitro instances)
```

**2. Terraform Module: `terraform/modules/bastion/`**

```
terraform/modules/bastion/
├── main.tf        # EC2 từ Golden AMI
├── variables.tf   # ami_id, instance_type, etc.
├── outputs.tf     # bastion info
└── versions.tf    # Provider constraints
```

```hcl
# terraform/modules/bastion/main.tf
# TODO:
# - data "aws_ami" lookup Golden AMI
# - aws_instance từ Golden AMI
# - aws_security_group
# - aws_iam_instance_profile cho SSM
# - Tags chuẩn (Project, Role, ManagedBy, Environment, Owner)
# - No Ansible post-provision (hardening đã bake trong AMI)
```

**3. Ansible Post-Provision Playbook: `ansible/playbooks/bastion-post-provision.yml`**

```yaml
# ansible/playbooks/bastion-post-provision.yml
#
# Ansible chỉ chạy cho config KHÔNG bake được vào AMI:
# TODO:
# - App-specific SSL certificates (Vault)
# - One-time setup scripts
# - Monitoring integration (Vault credentials)
# - không nên có trong AMI vì:
#   + Secrets có thể rotate
#   + Environment-specific config
```

**4. Pipeline: `terraform/modules/pipeline/`**

```yaml
# terraform/modules/pipeline/build.yml
# GitHub Actions workflow cho:
# - Packer build (on AMI config change)
# - Terraform plan (on tf change)
# - Terraform apply + Ansible (on Ansible change)
# - Artifact: Packer AMI ID → Terraform
```

**5. ADR Document: `docs/ADR-0001-hybrid-bastion-strategy.md`**

```markdown
# ADR-0001: Bastion Configuration Strategy

**Date:** 2026-05-14
**Status:** Proposed
**Deciders:** Platform Team

## Context

Team platform (5 engineers) cần config bastion hosts cho:
- 3 environments: dev, staging, production
- 15 bastion hosts total (5 per env)
- Compliance: SOC2 audit yêu cầu auditable image
- Cost: < $50/month cho bastion infrastructure
- Multi-cloud future roadmap (AWS + GCP)

## Decision Drivers

1. **Compliance**: SOC2 requires immutable, auditable infrastructure
2. **Iteration speed**: Dev team cần iterate nhanh trong dev env
3. **Cost**: Minimize EC2 cost, prefer spot instances
4. **Multi-cloud**: Avoid AWS-specific lock-in cho bastion config
5. **Security**: Fail2ban, UFW, auditd, MFA mandatory

## Options

### Option A: Pure Ansible (Decoupled)
- Ansible post-provision tất cả config
- Terraform chỉ tạo infrastructure

**Pros:**
- Iterate nhanh: sửa playbook → re-run
- No build time
- Multi-cloud: Ansible works everywhere

**Cons:**
- Not immutable: config có thể drift
- SOC2 audit khó: không có golden image
- SSH vào mỗi host: 5-10 phút bootstrap time

### Option B: Pure Packer (Immutable)
- Packer bake tất cả config vào AMI
- Terraform deploy AMI

**Pros:**
- Immutable: 100% deterministic
- SOC2 compliant: auditable image
- Fast boot: ~30s từ AMI

**Cons:**
- Iterate chậm: rebuild AMI 5-15 phút mỗi lần
- Storage cost: AMI snapshots
- Secrets baked in AMI (rotation problem)
- Không multi-cloud (Packer builder per cloud)

### Option C: Hybrid (Packer + Ansible) ← RECOMMENDED

**Pros:**
- Base OS + hardening = immutable (Packer)
- App-specific = flexible (Ansible)
- Fast iteration: Ansible re-run < 2 phút
- SOC2: golden image auditable
- Multi-cloud ready: Ansible layer

**Cons:**
- 2 pipeline stages
- Phức tạp hơn Option A hoặc B
- Secrets trong Ansible (cần Vault)

## Decision

Chọn **Option C: Hybrid (Packer + Ansible)**

## Implementation

### Phase 1: Packer (Week 1)
- Build hardened base AMI
- Include: OS hardening, SSM agent, CloudWatch, node_exporter
- Trigger: thay đổi security config

### Phase 2: Terraform (Week 1)
- Deploy AMI qua Terraform module
- Trigger: infrastructure change

### Phase 3: Ansible (Week 2)
- Post-provision playbook cho app-specific config
- Trigger: application config change

## Consequences

### Positive
- Immutable base: audit-friendly, SOC2 compliant
- Fast iteration: Ansible layer re-run nhanh
- Separation of concerns: OS vs app config

### Negative
- 2 pipeline stages = slightly more complex
- AMI lifecycle management needed
- Ansible vẫn cần secrets management

### Risks
- **Risk**: AMI sprawl nếu không có lifecycle policy
  - **Mitigation**: Lambda + EventBridge auto-delete AMI > 30 days
- **Risk**: Ansible re-run overwrite Packer config
  - **Mitigation**: Ansible idempotent, không re-apply baked config
- **Risk**: Multi-cloud Packer complexity
  - **Mitigation**: Dùng Ansible cho non-AWS clouds, Packer chỉ cho AWS

## Cost Analysis

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| EC2 bastion (t3.micro × 3) | $22.50 | Production: $0, Dev/Staging: $7.50 each |
| AMI snapshots (3 AMIs × 8GB) | $1.92 | gp3 × 3 |
| Packer build (CI/CD) | ~$0.50 | 1 build/week × 5 phút |
| **Total** | **~$25/month** | |
```

**6. Cost optimization comparison table**

```markdown
| Approach | EC2 Cost | AMI Storage | CI/CD Cost | Total Monthly |
|----------|----------|-------------|------------|---------------|
| Pure Ansible | $22.50 | $0 | ~$1 | ~$23.50 |
| Pure Packer | $22.50 | $1.92 | ~$5 | ~$29.42 |
| Hybrid | $22.50 | $1.92 | ~$2 | ~$26.42 |
```

**7. Timeline và milestones**

```markdown
## Implementation Timeline

Week 1 (Day 16-20):
- [ ] Day 16: Setup Packer template, build first AMI
- [ ] Day 17: Create Terraform bastion module
- [ ] Day 18: CI/CD pipeline for Packer build
- [ ] Day 19: CI/CD pipeline for Terraform deploy
- [ ] Day 20: Testing, security scan, peer review

Week 2 (Day 21-25):
- [ ] Day 21: Ansible post-provision playbook
- [ ] Day 22: Vault integration cho secrets
- [ ] Day 23: Full pipeline integration test
- [ ] Day 24: Documentation, runbook
- [ ] Day 25: Staging deployment, go-live

Success Metrics:
- [ ] AMI build time < 10 phút
- [ ] Bastion bootstrap time < 2 phút
- [ ] Zero manual SSH vào bastion
- [ ] 100% automated, audit-logged operations
```

### Hints

- Packer build nên chạy trong CI/CD, không local
- Golden AMI nên có tag `Immutable: true` và `BuiltBy: packer`
- Lambda cleanup script cho AMI lifecycle:
  ```python
  # lambda/ami-cleanup/lambda_function.py
  import boto3
  from datetime import datetime, timedelta

  def lambda_handler(event, context):
      ec2 = boto3.client('ec2')
      cutoff = datetime.now() - timedelta(days=30)
      amis = ec2.describe_images(Owners=['self'])['Images']
      for ami in amis:
          built = ami.get('CreationDate', '')
          # Delete AMIs older than 30 days
          ...
  ```
- ADR nên được commit vào `docs/` folder và review trong PR

---

## Submission Checklist

Sau khi hoàn thành challenges, đảm bảo:

```bash
# Challenge 1
[ ] aws_ec2.yml filter đúng tags
[ ] ansible-inventory --graph hiển thị đúng groups
[ ] Static hosts.ini đã remove hoặc deprecated

# Challenge 2
[ ] Packer build thành công, AMI ID in output
[ ] Terraform deploy từ Packer AMI
[ ] Boot time benchmark hoàn thành

# Challenge 3
[ ] 5 hosts trong dynamic inventory
[ ] Playbook chạy đúng tier theo group
[ ] Smoke test pass

# Challenge 4
[ ] Debug script output đầy đủ
[ ] 3 bugs đã được identify và fix
[ ] 5/5 hosts xuất hiện sau fix

# Challenge 5
[ ] GitHub Actions concurrency configured
[ ] Terraform state lock enabled
[ ] Ansible lock role tùy chọn

# Challenge 6
[ ] Packer template production-ready
[ ] Terraform module reusable
[ ] ADR document complete với all sections
[ ] Cost analysis accurate
[ ] Implementation timeline realistic
```

---

## Bonus Challenges

### Bonus A: Terragrunt + Ansible Integration

Dùng Terragrunt (wrapper cho Terraform) để quản lý multi-environment:

```hcl
# environments/
#   dev/
#     terragrunt.hcl
#   staging/
#     terragrunt.hcl
#   prod/
#     terragrunt.hcl
```

### Bonus B: Ansible Pull vs Push

Thiết kế alternative architecture với `ansible-pull` thay vì `ansible-pull`:

```yaml
# user_data cloud-init
runcmd:
  - ansible-pull \
    -U https://github.com/org/ansible-playbooks.git \
    -i inventory \
    site.yml
```

So sánh push vs pull:
- **Push**: Centralized, easier to audit, requires SSH
- **Pull**: Self-healing, no central access needed, harder to control

### Bonus C: GitOps cho Ansible

Dùng ArgoCD (Day 17) để sync Ansible inventory và config như một GitOps approach.
