# Day 15: Reference Document - Roles, Vault, Dynamic Inventory

---

## 1. Role Directory Structure - Quick Reference

```
roles/
└── <role_name>/
    ├── tasks/
    │   └── main.yml        # REQUIRED - auto-loaded entry point
    ├── handlers/
    │   └── main.yml        # Auto-loaded, triggered by notify:
    ├── templates/
    │   └── *.j2            # Jinja2 templates, referenced by template: module
    ├── files/
    │   └── *               # Static files, referenced by copy: module
    ├── vars/
    │   └── main.yml        # High-priority vars (override khó)
    ├── defaults/
    │   └── main.yml        # Low-priority vars (override dễ - DÙNG CÁI NÀY cho config)
    ├── meta/
    │   └── main.yml        # Dependencies, Galaxy metadata
    └── README.md           # Bắt buộc nếu publish Galaxy
```

### Variable Priority (Thấp → Cao)

```
defaults/main.yml
    ↓
inventory vars (group_vars, host_vars)
    ↓
vars/main.yml
    ↓
playbook vars:
    ↓
role vars (khi gọi role với vars:)
    ↓
extra-vars (-e "key=val")    ← HIGHEST, không gì override được
```

### Auto-loading Rules

| Thư mục | Auto-loaded khi | Ghi chú |
|---|---|---|
| `tasks/main.yml` | Luôn luôn | Entry point bắt buộc |
| `handlers/main.yml` | Luôn luôn | Chỉ execute khi được notify |
| `defaults/main.yml` | Luôn luôn | Lowest priority vars |
| `vars/main.yml` | Luôn luôn | High priority vars |
| `meta/main.yml` | Luôn luôn | Dependencies auto-resolved |
| `templates/` | Khi `template:` module gọi | Tìm file theo tên |
| `files/` | Khi `copy:` module gọi | Tìm file theo tên |

---

## 2. Ansible Galaxy - Cheat Sheet

### Cài đặt

```bash
# Single role
ansible-galaxy role install <namespace>.<role> --version <ver>

# Single role vào project-level thư mục
ansible-galaxy role install <namespace>.<role> -p ./roles

# Single collection
ansible-galaxy collection install <namespace>.<collection>:<ver>

# Từ requirements file
ansible-galaxy install -r requirements.yml
ansible-galaxy collection install -r requirements.yml

# Update role
ansible-galaxy role install <namespace>.<role> --force
```

### requirements.yml Format

```yaml
---
roles:
  - name: cloudalchemy.node_exporter
    version: "2.1.0"
  - name: geerlingguy.java
    version: "2.0.0"
  - name: internal_role           # Custom name
    src: https://github.com/yourorg/ansible-role-internal
    version: "main"

collections:
  - name: amazon.aws
    version: ">=6.0.0,<7.0.0"    # Version range
  - name: community.general
    version: "7.0.0"
  - name: community.docker
    version: "*"                   # Latest (không recommended cho production)
```

### Quản lý

```bash
# List roles đã cài
ansible-galaxy list

# Remove role
ansible-galaxy role remove <namespace>.<role>

# Search Galaxy
ansible-galaxy search <keyword> --author <author>

# Info về role
ansible-galaxy info <namespace>.<role>

# Init role skeleton mới
ansible-galaxy role init <role_name>
# Creates: tasks/, handlers/, templates/, files/, vars/, defaults/, meta/, README.md
```

### Galaxy Role vs Collection

| | Role | Collection |
|---|---|---|
| Format | Single automation unit | Bundle của roles + modules + plugins |
| Namespace | `namespace.role_name` | `namespace.collection_name` |
| Install path | `~/.ansible/roles/` | `~/.ansible/collections/` |
| Usage trong playbook | `roles:` section | `collections:` + module name |
| Trend | Legacy (vẫn dùng nhiều) | Hiện đại (AWS, GCP dùng collection) |

---

## 3. Ansible Vault - Cheat Sheet

### Tất cả lệnh Vault

```bash
# === FILE OPERATIONS ===

# Encrypt file mới (prompt password)
ansible-vault encrypt <file>

# Encrypt với password file
ansible-vault encrypt <file> --vault-password-file ~/.vault_pass

# Decrypt file (plaintext - KHÔNG commit)
ansible-vault decrypt <file>

# View nội dung mà không decrypt ra disk
ansible-vault view <file>

# Edit (decrypt → open $EDITOR → encrypt lại)
ansible-vault edit <file>

# Đổi password
ansible-vault rekey <file>
ansible-vault rekey <file> \
  --new-vault-password-file ~/.new_vault_pass

# Encrypt file mới với content từ stdout
echo "my_var: secret" | ansible-vault encrypt_string


# === STRING OPERATIONS (inline vault) ===

# Encrypt single string
ansible-vault encrypt_string '<value>' --name '<var_name>'

# Encrypt từ stdin (ẩn input)
ansible-vault encrypt_string --stdin-name '<var_name>'

# Output:
# db_password: !vault |
#   $ANSIBLE_VAULT;1.1;AES256
#   66386439653236336662386566343236...


# === MULTIPLE VAULT IDS (advanced) ===

# Encrypt với ID cụ thể
ansible-vault encrypt secrets.yml --vault-id prod@~/.vault_pass_prod

# Chạy playbook với nhiều vault IDs
ansible-playbook site.yml \
  --vault-id dev@~/.vault_pass_dev \
  --vault-id prod@~/.vault_pass_prod
```

### Vault Best Practices

```bash
# 1. Luôn dùng password file (không --ask-vault-pass trong CI/CD)
echo "your-strong-password" > ~/.vault_pass
chmod 600 ~/.vault_pass

# 2. Thêm vào .gitignore
echo ".vault_pass" >> .gitignore
echo "*.vault_pass" >> .gitignore

# 3. ansible.cfg để không cần --vault-password-file mỗi lần
# ansible.cfg
# [defaults]
# vault_password_file = ~/.vault_pass

# 4. Naming convention: vault_ prefix
# vault.yml: vault_db_password, vault_api_key
# main.yml: db_password: "{{ vault_db_password }}"

# 5. CI/CD: dùng environment variable
export ANSIBLE_VAULT_PASSWORD_FILE=/path/to/vault_pass
# Hoặc store vault password trong CI/CD secret (GitHub Actions Secret, GitLab CI Variable)
```

### File Structure Convention

```
group_vars/
├── all/
│   ├── main.yml       # Plaintext - commit bình thường
│   └── vault.yml      # Encrypted - commit encrypted version
├── production/
│   ├── main.yml
│   └── vault.yml      # Production-specific secrets
└── staging/
    ├── main.yml
    └── vault.yml      # Staging secrets (khác password với production)
```

```yaml
# group_vars/all/vault.yml (sau khi decrypt)
---
vault_db_password: "SuperSecretProd2024!"
vault_redis_password: "RedisPass2024!"
vault_slack_webhook: "https://hooks.slack.com/..."

# group_vars/all/main.yml (plaintext)
---
db_password: "{{ vault_db_password }}"
redis_password: "{{ vault_redis_password }}"
slack_webhook: "{{ vault_slack_webhook }}"
```

---

## 4. Dynamic Inventory - AWS EC2 Plugin Reference

### Full aws_ec2.yml Config

```yaml
plugin: amazon.aws.aws_ec2

# AWS credentials (ưu tiên dùng IAM role, không hardcode)
# aws_access_key: "{{ lookup('env', 'AWS_ACCESS_KEY_ID') }}"
# aws_secret_key: "{{ lookup('env', 'AWS_SECRET_ACCESS_KEY') }}"

# Regions
regions:
  - ap-southeast-1
  - ap-southeast-2

# Filters - chỉ lấy instances match
filters:
  tag:Environment:
    - production
    - staging
  tag:ManagedBy: ansible
  instance-state-name: running
  # instance-type: t3.medium  # Filter theo instance type

# Grouping - tạo inventory groups từ attributes
keyed_groups:
  # Group by tag value
  - key: tags.Role
    prefix: role
    separator: "_"
    # EC2 tag Role=monitoring → group: role_monitoring
  - key: tags.Environment
    prefix: env
    separator: "_"
  - key: tags.Application
    prefix: app
    separator: "_"
  # Group by instance attribute
  - key: instance_type
    prefix: type
    separator: "_"
  - key: placement.availability_zone
    prefix: az
    separator: "_"
  # Group by OS
  - key: platform
    prefix: platform
    separator: "_"

# Compose ansible variables từ EC2 attributes
compose:
  # Dùng private IP để connect (trong VPC)
  ansible_host: private_ip_address
  # Hoặc public IP nếu cần
  # ansible_host: public_ip_address

# Hostname display name
hostnames:
  - tag:Name             # Tên EC2 instance
  - private-dns-name     # private-ip.region.compute.internal
  - private-ip-address   # Fallback về IP

# Caching (tránh gọi AWS API quá nhiều)
cache: true
cache_plugin: jsonfile
cache_timeout: 300        # 5 phút
cache_connection: /tmp/aws_ec2_cache

# Strict mode (fail nếu plugin error, không silently return empty)
strict: true
```

### Commands

```bash
# List inventory dạng JSON
ansible-inventory -i inventory/aws_ec2.yml --list

# Graph view (dễ đọc hơn)
ansible-inventory -i inventory/aws_ec2.yml --graph

# Xem vars của một host cụ thể
ansible-inventory -i inventory/aws_ec2.yml --host <hostname>

# Clear cache
rm -rf /tmp/aws_ec2_cache

# Test ping (cần SSH access)
ansible all -i inventory/aws_ec2.yml -m ping

# Chạy ad-hoc command trên group
ansible role_monitoring -i inventory/aws_ec2.yml -m shell -a "uptime"
```

### AWS IAM Policy cho Dynamic Inventory

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags",
        "ec2:DescribeRegions",
        "ec2:DescribeAvailabilityZones"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 5. Node Exporter Role - Quick Reference

### Default Variables

| Variable | Default | Description |
|---|---|---|
| `node_exporter_version` | `1.7.0` | Version to install |
| `node_exporter_port` | `9100` | Listening port |
| `node_exporter_user` | `node_exporter` | System user |
| `node_exporter_group` | `node_exporter` | System group |
| `node_exporter_install_dir` | `/usr/local/bin` | Binary location |
| `node_exporter_config_dir` | `/etc/node_exporter` | Config directory |
| `node_exporter_log_level` | `info` | Log level |
| `node_exporter_enabled_collectors` | `[cpu, diskstats, ...]` | Enabled collectors |
| `node_exporter_disabled_collectors` | `[]` | Disabled collectors |

### Override trong playbook

```yaml
- hosts: monitoring
  roles:
    - role: node_exporter
      vars:
        node_exporter_version: "1.7.0"
        node_exporter_port: 9200          # Non-default port
        node_exporter_enabled_collectors:
          - cpu
          - meminfo
        node_exporter_disabled_collectors:
          - netdev                          # Disable net collector
```

### Tags

```bash
# Chỉ validate
ansible-playbook site.yml --tags validate

# Chỉ install (download + binary)
ansible-playbook site.yml --tags install

# Chỉ configure (systemd service)
ansible-playbook site.yml --tags configure

# Verify endpoint
ansible-playbook site.yml --tags verify

# Full role
ansible-playbook site.yml --tags node_exporter
```

### Verify Installation

```bash
# Trên target host
systemctl status node_exporter
curl http://localhost:9100/metrics | head -20

# Từ Ansible
ansible monitoring -m uri \
  -a "url=http://{{ ansible_host }}:9100/metrics return_content=no"
```

---

## 6. ansible.cfg - Production Template

```ini
[defaults]
# Inventory
inventory = inventory/

# Roles
roles_path = roles/

# Performance
host_key_checking = False
pipelining = True
forks = 20

# Output
stdout_callback = yaml
bin_ansible_callbacks = True

# Vault
vault_password_file = ~/.vault_pass

# SSH
remote_user = ubuntu
private_key_file = ~/.ssh/id_rsa

# Retry
retry_files_enabled = False

# Timeout
timeout = 30

[inventory]
enable_plugins = amazon.aws.aws_ec2, ini, yaml, auto

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no
pipelining = True
control_path = /tmp/ansible-ssh-%%h-%%p-%%r

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

---

## 7. Common Patterns

### Pattern 1: Role với conditional OS support

```yaml
# tasks/main.yml
- name: Include OS-specific variables
  include_vars: "{{ ansible_os_family }}.yml"
  # Loads vars/Debian.yml hoặc vars/RedHat.yml

- name: Include OS-specific tasks
  include_tasks: "install_{{ ansible_os_family | lower }}.yml"
  # Loads tasks/install_debian.yml hoặc tasks/install_redhat.yml
```

### Pattern 2: Delegate secrets fetch về localhost

```yaml
- name: Get TLS cert from Vault
  community.hashi_vault.vault_read:
    path: "secret/data/tls/myapp"
  delegate_to: localhost
  register: tls_secret
  no_log: true   # QUAN TRỌNG: ẩn output trong log

- name: Deploy TLS cert to server
  copy:
    content: "{{ tls_secret.data.data.cert }}"
    dest: /etc/ssl/myapp.crt
    mode: "0644"
```

### Pattern 3: Reuse role với loop

```yaml
# Cài nhiều packages bằng một role
- hosts: all
  tasks:
    - name: Install multiple services
      include_role:
        name: "{{ item.role }}"
      vars: "{{ item.vars }}"
      loop:
        - role: node_exporter
          vars:
            node_exporter_port: 9100
        - role: nginx
          vars:
            nginx_port: 80
```

### Pattern 4: Wait for service trước khi continue

```yaml
- name: Wait for node_exporter to be ready
  wait_for:
    host: "{{ ansible_host }}"
    port: "{{ node_exporter_port }}"
    timeout: 60
    state: started
  delegate_to: localhost
```

---

## 8. Comparison Tables

### Secret Management Comparison

| Tool | Complexity | Cost | Rotation | Audit | Compliance |
|---|---|---|---|---|---|
| Ansible Vault | Thấp | Free | Manual | Không | Basic |
| HashiCorp Vault | Cao | Free/Enterprise | Auto | Đầy đủ | SOC2, PCI |
| AWS Secrets Manager | Trung bình | $0.40/secret/mo | Auto | CloudTrail | AWS compliance |
| GCP Secret Manager | Trung bình | $0.06/10K access | Manual | Cloud Audit | GCP compliance |
| Azure Key Vault | Trung bình | Per-op pricing | Auto | Azure Monitor | Azure compliance |

### Inventory Type Comparison

| | Static | Dynamic (AWS) | Dynamic (Terraform state) |
|---|---|---|---|
| Update frequency | Manual | Auto per run | Auto per run |
| Source of truth | File | AWS API | Terraform state |
| Works offline | Yes | No | No |
| Scale | Tốt đến ~100 hosts | Không giới hạn | Không giới hạn |
| Setup complexity | Thấp | Trung bình | Cao |
| Best for | Lab, on-premise | Cloud-only | Terraform-managed infra |
