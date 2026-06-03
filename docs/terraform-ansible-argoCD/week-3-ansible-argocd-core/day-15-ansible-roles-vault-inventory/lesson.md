# Day 15: Roles, Vault, Dynamic Inventory

**Thời gian:** 2 giờ | **Level:** Intermediate-Advanced | **Phase:** 3 - Ansible Practical, Day 3

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Thiết kế và tạo Ansible role với cấu trúc chuẩn production, áp dụng cho role `node_exporter`
- Sử dụng Ansible Galaxy để tìm, cài đặt và quản lý community roles trong project
- Encrypt secrets bằng Ansible Vault ở cả file-level và variable-level, tích hợp vào playbook
- Cấu hình dynamic inventory với AWS EC2 plugin để tự động discover hosts từ cloud
- So sánh các chiến lược secret management và chọn đúng approach cho từng bối cảnh (cá nhân, startup, enterprise, bank)

---

## 2. Bối cảnh thực tế

### Tại sao Role, Vault, Dynamic Inventory không phải optional?

Giả sử bạn đang onboard vào một startup đã có 3 môi trường: dev, staging, production. Infrastructure gồm 40 EC2 instances, chia làm nhiều application tiers. Team infra hiện tại dùng playbook monolithic - một file YAML 800 dòng cho mọi thứ.

**Vấn đề thực tế:**

```
# Hiện trạng - playbook monolithic
site.yml (800 dòng)
├── Install nginx trên web servers
├── Configure MySQL trên DB servers
├── Deploy Node Exporter trên tất cả servers
├── Hardcode credentials:
│     db_password: "P@ssw0rd123"   # <- đây là vấn đề
│     api_key: "sk-prod-abc123"    # <- và đây
└── Static inventory:
      [web]
      10.0.1.5   # <- IP thay đổi sau mỗi deployment
      10.0.1.6   # <- phải update tay
```

**Hậu quả:**
- Junior dev commit playbook lên GitHub - credentials bị lộ, phải rotate toàn bộ production secrets
- Thêm EC2 instance mới phải update inventory tay - deployment lag 30 phút
- Không thể tái sử dụng logic cài đặt Node Exporter cho project khác
- Không có cách test role độc lập trước khi apply lên production

**Giải pháp sau Day 15:**
- Role structure: tái sử dụng, test độc lập, version-controlled
- Ansible Vault: zero plaintext secrets trong git
- Dynamic Inventory: tự động sync với AWS state, không cần update tay

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 Role Directory Structure

Role là đơn vị tái sử dụng trong Ansible, tương đương Terraform module. Thay vì import/export variables, role dùng convention over configuration - Ansible tự load đúng file theo tên thư mục.

```
roles/
└── node_exporter/              # Tên role
    ├── tasks/
    │   ├── main.yml            # Entry point - LUÔN được load
    │   └── install.yml         # Sub-task, include từ main.yml
    ├── handlers/
    │   └── main.yml            # Handlers - notify từ tasks
    ├── templates/
    │   └── node_exporter.service.j2   # Jinja2 templates
    ├── files/
    │   └── node_exporter.conf  # Static files (không render template)
    ├── vars/
    │   └── main.yml            # High-priority vars (khó override)
    ├── defaults/
    │   └── main.yml            # Low-priority vars (dễ override - dùng cái này)
    ├── meta/
    │   └── main.yml            # Dependencies, metadata cho Galaxy
    └── README.md               # Bắt buộc nếu publish lên Galaxy
```

**So sánh với Terraform module:**

| Terraform Module | Ansible Role |
|---|---|
| `variables.tf` | `defaults/main.yml` (override được) |
| `variables.tf` với `default = null` | `vars/main.yml` (khó override) |
| `outputs.tf` | Không có equivalent trực tiếp (dùng `set_fact`) |
| `main.tf` | `tasks/main.yml` |
| `modules/` directory | `roles/` directory |
| `source = "./modules/vpc"` | `roles:` trong playbook |

**ASCII Diagram - Role Loading Flow:**

```
playbook.yml
    │
    ▼
roles: node_exporter
    │
    ├──► defaults/main.yml    (loaded first, lowest priority)
    ├──► vars/main.yml        (loaded after defaults, higher priority)
    ├──► tasks/main.yml       (main execution entry point)
    │         │
    │         ├── include_tasks: install.yml
    │         └── include_tasks: configure.yml
    ├──► handlers/main.yml    (triggered by notify:)
    └──► templates/           (referenced by template: module)
         files/               (referenced by copy: module)
```

### 3.2 Variable Priority trong Role

```
Thấp nhất ◄────────────────────────────────────► Cao nhất

defaults/    vars/    playbook vars    extra-vars (-e)
main.yml    main.yml    vars:          ansible -e "key=val"

→ Luôn để default values vào defaults/main.yml
→ Chỉ dùng vars/main.yml cho constants không muốn ai override
```

### 3.3 Ansible Galaxy

Galaxy là package registry cho Ansible roles và collections. Tương đương npm cho Node.js, Terraform Registry cho Terraform.

**Cấu trúc Galaxy:**
```
# roles (legacy format - vẫn dùng nhiều)
namespace.role_name
# Ví dụ: geerlingguy.nodejs

# collections (format mới, gom nhiều roles + modules + plugins)
namespace.collection_name
# Ví dụ: amazon.aws, community.general
```

**Workflow cơ bản:**

```bash
# Tìm kiếm role
ansible-galaxy search node_exporter

# Cài đặt role
ansible-galaxy role install cloudalchemy.node_exporter

# Cài đặt vào thư mục cụ thể (project-level)
ansible-galaxy role install cloudalchemy.node_exporter -p ./roles

# Cài đặt từ requirements file (cách chuẩn cho team)
ansible-galaxy install -r requirements.yml

# List các role đã cài
ansible-galaxy list
```

**requirements.yml - cách quản lý dependencies cho team:**

```yaml
# requirements.yml
---
roles:
  - name: cloudalchemy.node_exporter
    version: "2.1.0"         # Pin version - quan trọng cho production
  - name: geerlingguy.java
    version: "2.0.0"
  - src: https://github.com/yourorg/custom-role  # Private repo

collections:
  - name: amazon.aws
    version: "6.0.0"
  - name: community.general
    version: "7.0.0"
```

### 3.4 Ansible Vault

Vault là built-in encryption system của Ansible, dùng AES-256. Không cần external service.

**Hai mode encryption:**

```
Mode 1: File-level encryption
─────────────────────────────
Encrypt toàn bộ file YAML
Dùng khi: toàn bộ file là secrets (vault_vars.yml)

Mode 2: Variable-level encryption (inline)
──────────────────────────────────────────
Encrypt từng value trong file YAML thường
Dùng khi: file vừa có vars bình thường vừa có secrets
Format: !vault |
          $ANSIBLE_VAULT;1.1;AES256
          ...encrypted_string...
```

**ASCII Diagram - Vault Workflow:**

```
Developer                    Git Repo              Ansible Engine
    │                           │                       │
    │  ansible-vault encrypt     │                       │
    │  secrets.yml              │                       │
    │──────────────────────────►│                       │
    │  (ciphertext in repo)     │                       │
    │                           │                       │
    │                           │ ansible-playbook       │
    │                           │ --vault-pass-file      │
    │                           │──────────────────────►│
    │                           │                       │ decrypt in memory
    │                           │                       │ (never written to disk)
    │                           │                       │
    │                           │                       │ use plaintext vars
```

**Các lệnh vault quan trọng:**

```bash
# Encrypt file mới
ansible-vault encrypt secrets.yml

# Decrypt để xem/edit
ansible-vault decrypt secrets.yml

# Edit trực tiếp (encrypt → decrypt → open editor → encrypt lại)
ansible-vault edit secrets.yml

# Encrypt một string (inline vault)
ansible-vault encrypt_string 'MySecretPassword' --name 'db_password'

# Xem nội dung file đã encrypt
ansible-vault view secrets.yml

# Re-key (đổi password)
ansible-vault rekey secrets.yml
```

**Chạy playbook với vault:**

```bash
# Nhập password khi chạy (yêu cầu interactive input)
ansible-playbook site.yml --ask-vault-pass

# Dùng vault password file (CI/CD-friendly)
ansible-playbook site.yml --vault-password-file ~/.vault_pass

# Dùng environment variable
export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass
ansible-playbook site.yml
```

### 3.5 Dynamic Inventory

Static inventory là file text với IP/hostname hardcode. Dynamic inventory là script/plugin tự query nguồn data (AWS, GCP, Azure, Kubernetes, database) và trả về JSON theo format Ansible.

**So sánh Static vs Dynamic:**

```
Static Inventory              Dynamic Inventory (AWS EC2)
─────────────────             ───────────────────────────
[web]                         Query AWS API → get EC2 instances
10.0.1.5                      Filter by tags (Environment=prod)
10.0.1.6                      Auto-group by tag values
                              Refresh every playbook run

Phù hợp:                      Phù hợp:
- Lab environment             - Cloud infrastructure
- On-premise fixed IP         - Auto-scaling groups
- Small team, ít servers      - Multiple environments
- Không có AWS access         - Teams > 5 người
```

**AWS EC2 Dynamic Inventory - cấu trúc:**

```yaml
# inventory/aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions:
  - ap-southeast-1
filters:
  tag:Environment: production
  instance-state-name: running
keyed_groups:
  - key: tags.Role           # Group by tag "Role"
    prefix: role
  - key: tags.Environment    # Group by tag "Environment"
    prefix: env
hostnames:
  - private-ip-address       # Dùng private IP (trong VPC)
  - public-ip-address        # Hoặc public IP
compose:
  ansible_host: private_ip_address
```

**Verify dynamic inventory hoạt động:**

```bash
# List tất cả hosts từ dynamic inventory
ansible-inventory -i inventory/aws_ec2.yml --list

# Xem dạng graph
ansible-inventory -i inventory/aws_ec2.yml --graph

# Test ping tất cả hosts
ansible all -i inventory/aws_ec2.yml -m ping
```

---

## 4. Deep Dive & Trade-offs - 30 phút

### 4.1 Role Design Best Practices

**Nguyên tắc Single Responsibility:**

```yaml
# BAD: Role làm quá nhiều việc
roles/application_server/tasks/main.yml:
  - Install nginx
  - Install PHP
  - Install MySQL
  - Configure SSL
  - Deploy application code
  - Setup monitoring

# GOOD: Mỗi role làm một việc
roles/
├── nginx/          # Chỉ install và configure nginx
├── php/            # Chỉ install PHP runtime
├── mysql/          # Chỉ install MySQL
├── ssl_cert/       # Chỉ manage SSL certificates
└── node_exporter/  # Chỉ install Node Exporter
```

**Idempotency là bắt buộc:**

```yaml
# BAD: Không idempotent
- name: Add user to sudoers
  shell: echo "deploy ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# GOOD: Idempotent
- name: Add user to sudoers
  lineinfile:
    path: /etc/sudoers
    line: "deploy ALL=(ALL) NOPASSWD:ALL"
    validate: visudo -cf %s
    state: present
```

**Luôn dùng defaults thay vì vars cho configurable values:**

```yaml
# defaults/main.yml - user có thể override
node_exporter_version: "1.7.0"
node_exporter_port: 9100
node_exporter_user: "node_exporter"
node_exporter_install_dir: "/usr/local/bin"

# vars/main.yml - internal constants, không override
_node_exporter_binary: "node_exporter"
_node_exporter_download_url: >-
  https://github.com/prometheus/node_exporter/releases/download/
  v{{ node_exporter_version }}/
  node_exporter-{{ node_exporter_version }}.linux-amd64.tar.gz
```

**Tags cho selective execution:**

```yaml
- name: Install node_exporter binary
  get_url:
    url: "{{ _node_exporter_download_url }}"
    dest: "/tmp/node_exporter.tar.gz"
  tags:
    - node_exporter
    - install
    - never   # Không chạy trừ khi explicitly gọi tag này

- name: Configure node_exporter service
  template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
  tags:
    - node_exporter
    - configure
```

### 4.2 Galaxy Roles vs Custom Roles

| Tiêu chí | Galaxy Role | Custom Role |
|---|---|---|
| Time to implement | Nhanh (install xong dùng ngay) | Chậm (phải viết từ đầu) |
| Customization | Hạn chế (bị ràng buộc bởi role design) | Hoàn toàn |
| Maintenance burden | Thấp (community maintain) | Cao (team tự maintain) |
| Security audit | Khó (phải đọc toàn bộ code) | Dễ (bạn biết mọi dòng code) |
| Version stability | Phụ thuộc maintainer | Bạn kiểm soát |
| Enterprise compliance | Thường không đáp ứng được | Có thể customize |

**Quyết định:**
- **Dùng Galaxy role khi:** Standard software (nginx, mysql, redis), không có requirement đặc biệt, team nhỏ
- **Viết custom role khi:** Internal tooling, security-sensitive, complex business logic, enterprise compliance requirements

### 4.3 Vault Strategies

**Strategy 1: File-level encryption**

```bash
# Toàn bộ file được encrypt
ansible-vault encrypt group_vars/all/vault.yml

# File structure:
group_vars/
└── all/
    ├── main.yml          # Plaintext vars (commit bình thường)
    └── vault.yml         # ENCRYPTED (commit encrypted file)
```

```yaml
# group_vars/all/main.yml (plaintext - commit được)
db_host: "postgres.internal"
db_port: 5432
db_name: "myapp"
db_user: "app_user"
db_password: "{{ vault_db_password }}"   # Reference tới vault var

# group_vars/all/vault.yml (sau khi decrypt - KHÔNG commit plaintext)
vault_db_password: "SuperSecretP@ss!"
vault_api_key: "sk-prod-abc123"
```

**Strategy 2: Variable-level encryption (inline)**

```bash
# Encrypt một string
ansible-vault encrypt_string 'SuperSecretP@ss!' --name 'db_password'
```

```yaml
# group_vars/all/main.yml - file duy nhất, plaintext và encrypted trộn lẫn
db_host: "postgres.internal"
db_port: 5432
db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  66386439653236336662386566343236333962313230316334303937303634353635323539303366
  3430666639626436643637323464326635613635363638310a653561316232653633316535616230
  ...
```

**So sánh:**

| | File-level | Variable-level |
|---|---|---|
| Readability | Không đọc được file | Vẫn đọc được structure |
| Granularity | Cả file | Từng variable |
| Git diff | Mất (toàn bộ file là ciphertext) | Còn (plaintext vars hiển thị diff) |
| Complexity | Đơn giản | Phức tạp hơn |

**Recommendation:** Dùng file-level cho production, variable-level cho dev/test khi cần readability.

### 4.4 Khi nào dùng Vault vs External Secret Managers

```
Ansible Vault
├── PRO: Zero additional infrastructure, built-in, simple
├── PRO: Perfect cho team nhỏ, on-premise
├── CON: Secret rotation phức tạp (phải rekey tất cả files)
├── CON: Không có audit log chi tiết
└── CON: Không có secret versioning

HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager
├── PRO: Dynamic secrets (auto-rotate)
├── PRO: Audit log đầy đủ
├── PRO: Fine-grained access control
├── PRO: Secret versioning
├── CON: Thêm infrastructure cần manage
└── CON: Thêm cost (AWS Secrets Manager: $0.40/secret/month)
```

**Ansible Vault: đọc secrets từ external manager:**

```yaml
# lookup plugin - kết nối Vault với external secret managers
- name: Get secret from AWS Secrets Manager
  set_fact:
    db_password: "{{ lookup('amazon.aws.aws_secret', 'prod/myapp/db_password') }}"

- name: Get secret from HashiCorp Vault
  set_fact:
    api_key: "{{ lookup('hashi_vault.hashi_vault.hashi_vault', 'secret/myapp/api_key') }}"
```

### 4.5 Chiến lược theo bối cảnh

| Bối cảnh | Secret Strategy | Inventory | Role Strategy |
|---|---|---|---|
| Cá nhân / Lab | Ansible Vault (local pass file) | Static | Mix Galaxy + custom |
| Small Team (< 10) | Ansible Vault + git-crypt | Static hoặc dynamic | Galaxy roles, pin version |
| Startup (10-50) | Ansible Vault + CI/CD vault pass | Dynamic (cloud) | Custom roles, internal Galaxy |
| Enterprise (50+) | HashiCorp Vault / AWS SM | Dynamic (cloud) | Custom roles, private registry |
| Bank / Regulated | HSM + approved secret manager | Static (audit controlled) | Custom roles, security scan bắt buộc |

---

## 5. Hands-on Lab - 60 phút

### Prerequisites

Đảm bảo environment từ Day 13-14 đang hoạt động:

```bash
# Kiểm tra Ansible
ansible --version  # >= 2.14

# Kiểm tra Docker (dùng cho local testing)
docker --version

# Kiểm tra cấu trúc project từ Day 13-14
ls ~/ansible-training/
# Phải có: inventory/, playbooks/, ansible.cfg
```

### Lab Setup - Cấu trúc project hoàn chỉnh

```bash
cd ~/ansible-training

# Tạo cấu trúc thư mục
mkdir -p roles/node_exporter/{tasks,handlers,templates,files,vars,defaults,meta}
mkdir -p group_vars/{all,webservers,monitoring}
mkdir -p inventory/{production,staging}
```

**Cấu trúc cuối cùng:**

```
~/ansible-training/
├── ansible.cfg
├── requirements.yml
├── site.yml
├── inventory/
│   ├── production/
│   │   ├── hosts.yml           # Static inventory (fallback)
│   │   └── aws_ec2.yml         # Dynamic inventory
│   └── staging/
│       └── hosts.yml
├── group_vars/
│   ├── all/
│   │   ├── main.yml            # Common vars
│   │   └── vault.yml           # ENCRYPTED secrets
│   └── monitoring/
│       └── main.yml            # Monitoring-specific vars
├── playbooks/
│   └── monitoring.yml
└── roles/
    └── node_exporter/
        ├── defaults/main.yml
        ├── vars/main.yml
        ├── tasks/main.yml
        ├── tasks/install.yml
        ├── tasks/configure.yml
        ├── handlers/main.yml
        ├── templates/node_exporter.service.j2
        └── meta/main.yml
```

### Step 1: Tạo Role node_exporter

**defaults/main.yml - configurable defaults:**

```yaml
# roles/node_exporter/defaults/main.yml
---
node_exporter_version: "1.7.0"
node_exporter_port: 9100
node_exporter_user: "node_exporter"
node_exporter_group: "node_exporter"
node_exporter_install_dir: "/usr/local/bin"
node_exporter_config_dir: "/etc/node_exporter"
node_exporter_log_level: "info"
node_exporter_enabled_collectors:
  - cpu
  - diskstats
  - filesystem
  - loadavg
  - meminfo
  - netdev
  - netstat
  - stat
  - time
  - uname
node_exporter_disabled_collectors: []
```

**vars/main.yml - internal constants:**

```yaml
# roles/node_exporter/vars/main.yml
---
_node_exporter_arch: "amd64"
_node_exporter_os: "linux"
_node_exporter_binary_name: "node_exporter"
_node_exporter_service_name: "node_exporter"
_node_exporter_download_url: >-
  https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/node_exporter-{{ node_exporter_version }}.{{ _node_exporter_os }}-{{ _node_exporter_arch }}.tar.gz
_node_exporter_checksum_url: >-
  https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/sha256sums.txt
```

**tasks/main.yml - entry point:**

```yaml
# roles/node_exporter/tasks/main.yml
---
- name: Validate OS is supported
  assert:
    that:
      - ansible_os_family in ['Debian', 'RedHat']
    fail_msg: "OS {{ ansible_os_family }} is not supported by this role"
    success_msg: "OS {{ ansible_os_family }} is supported"
  tags: [node_exporter, validate]

- name: Include install tasks
  include_tasks: install.yml
  tags: [node_exporter, install]

- name: Include configure tasks
  include_tasks: configure.yml
  tags: [node_exporter, configure]
```

**tasks/install.yml - installation logic:**

```yaml
# roles/node_exporter/tasks/install.yml
---
- name: Create node_exporter system group
  group:
    name: "{{ node_exporter_group }}"
    system: true
    state: present

- name: Create node_exporter system user
  user:
    name: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    system: true
    shell: /usr/sbin/nologin
    create_home: false
    state: present

- name: Create node_exporter config directory
  file:
    path: "{{ node_exporter_config_dir }}"
    state: directory
    owner: "{{ node_exporter_user }}"
    group: "{{ node_exporter_group }}"
    mode: "0750"

- name: Check if node_exporter binary exists
  stat:
    path: "{{ node_exporter_install_dir }}/{{ _node_exporter_binary_name }}"
  register: node_exporter_binary_stat

- name: Check existing node_exporter version
  command: "{{ node_exporter_install_dir }}/{{ _node_exporter_binary_name }} --version"
  changed_when: false
  failed_when: false
  register: node_exporter_current_version
  when: node_exporter_binary_stat.stat.exists

- name: Download node_exporter archive
  get_url:
    url: "{{ _node_exporter_download_url }}"
    dest: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
    mode: "0644"
    timeout: 60
  when: >-
    not node_exporter_binary_stat.stat.exists or
    node_exporter_version not in node_exporter_current_version.stdout | default('')
  register: node_exporter_download

- name: Extract node_exporter archive
  unarchive:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
    dest: "/tmp"
    remote_src: true
    creates: "/tmp/node_exporter-{{ node_exporter_version }}.{{ _node_exporter_os }}-{{ _node_exporter_arch }}"
  when: node_exporter_download is changed

- name: Install node_exporter binary
  copy:
    src: "/tmp/node_exporter-{{ node_exporter_version }}.{{ _node_exporter_os }}-{{ _node_exporter_arch }}/{{ _node_exporter_binary_name }}"
    dest: "{{ node_exporter_install_dir }}/{{ _node_exporter_binary_name }}"
    owner: root
    group: root
    mode: "0755"
    remote_src: true
  notify: restart node_exporter
  when: node_exporter_download is changed

- name: Remove node_exporter archive
  file:
    path: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
    state: absent
```

**tasks/configure.yml - configuration:**

```yaml
# roles/node_exporter/tasks/configure.yml
---
- name: Configure node_exporter systemd service
  template:
    src: node_exporter.service.j2
    dest: /etc/systemd/system/node_exporter.service
    owner: root
    group: root
    mode: "0644"
  notify:
    - systemd daemon reload
    - restart node_exporter

- name: Enable and start node_exporter service
  systemd:
    name: "{{ _node_exporter_service_name }}"
    enabled: true
    state: started
    daemon_reload: true

- name: Configure firewall for node_exporter (UFW)
  ufw:
    rule: allow
    port: "{{ node_exporter_port }}"
    proto: tcp
    comment: "Allow Prometheus Node Exporter"
  when:
    - ansible_os_family == "Debian"
    - node_exporter_configure_firewall | default(false)

- name: Verify node_exporter is accessible
  uri:
    url: "http://localhost:{{ node_exporter_port }}/metrics"
    method: GET
    status_code: 200
  register: node_exporter_health
  retries: 3
  delay: 5
  until: node_exporter_health.status == 200
  tags: [node_exporter, verify]
```

**handlers/main.yml:**

```yaml
# roles/node_exporter/handlers/main.yml
---
- name: systemd daemon reload
  systemd:
    daemon_reload: true

- name: restart node_exporter
  systemd:
    name: "{{ _node_exporter_service_name }}"
    state: restarted
    enabled: true

- name: stop node_exporter
  systemd:
    name: "{{ _node_exporter_service_name }}"
    state: stopped
```

**templates/node_exporter.service.j2:**

```jinja2
{# roles/node_exporter/templates/node_exporter.service.j2 #}
[Unit]
Description=Prometheus Node Exporter
Documentation=https://github.com/prometheus/node_exporter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={{ node_exporter_user }}
Group={{ node_exporter_group }}
EnvironmentFile=-{{ node_exporter_config_dir }}/node_exporter.env
ExecStart={{ node_exporter_install_dir }}/{{ _node_exporter_binary_name }} \
  --web.listen-address=":{{ node_exporter_port }}" \
  --log.level={{ node_exporter_log_level }} \
{% for collector in node_exporter_enabled_collectors %}
  --collector.{{ collector }} \
{% endfor %}
{% for collector in node_exporter_disabled_collectors %}
  --no-collector.{{ collector }} \
{% endfor %}
  --web.telemetry-path="/metrics"

Restart=on-failure
RestartSec=5s
SendSIGKILL=no

[Install]
WantedBy=multi-user.target
```

**meta/main.yml:**

```yaml
# roles/node_exporter/meta/main.yml
---
galaxy_info:
  author: "your-name"
  description: "Install and configure Prometheus Node Exporter"
  company: "Your Company"
  license: "MIT"
  min_ansible_version: "2.10"
  platforms:
    - name: Ubuntu
      versions:
        - "20.04"
        - "22.04"
    - name: EL
      versions:
        - "8"
        - "9"
  galaxy_tags:
    - monitoring
    - prometheus
    - node_exporter

dependencies: []
```

### Step 2: Setup Ansible Vault

```bash
cd ~/ansible-training

# Tạo vault password file (KHÔNG commit vào git)
echo "MyVaultMasterPassword2024!" > ~/.vault_pass
chmod 600 ~/.vault_pass

# Thêm vào .gitignore
echo ".vault_pass" >> .gitignore
echo "*.vault_pass" >> .gitignore
```

**Tạo encrypted secrets file:**

```bash
# Tạo file secrets trước
cat > /tmp/vault_content.yml << 'EOF'
---
vault_monitoring_basic_auth_password: "PrometheusSecure2024!"
vault_node_exporter_tls_cert: |
  -----BEGIN CERTIFICATE-----
  (your TLS cert here for production)
  -----END CERTIFICATE-----
vault_slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
vault_pagerduty_key: "your-pagerduty-integration-key"
EOF

# Encrypt file
ansible-vault encrypt /tmp/vault_content.yml --vault-password-file ~/.vault_pass

# Copy vào group_vars
cp /tmp/vault_content.yml group_vars/all/vault.yml

# Verify nó đã được encrypt
head -3 group_vars/all/vault.yml
# Output phải là:
# $ANSIBLE_VAULT;1.1;AES256
# ...encrypted content...
```

**group_vars/all/main.yml - reference vault vars:**

```yaml
# group_vars/all/main.yml
---
# Common configuration
ansible_user: ubuntu
ansible_ssh_private_key_file: "~/.ssh/id_rsa"

# Monitoring configuration (reference vault vars with vault_ prefix convention)
monitoring_basic_auth_password: "{{ vault_monitoring_basic_auth_password }}"
slack_webhook_url: "{{ vault_slack_webhook_url }}"
pagerduty_key: "{{ vault_pagerduty_key }}"

# Node Exporter defaults (override per group if needed)
node_exporter_version: "1.7.0"
node_exporter_port: 9100
```

**Kiểm tra vault hoạt động:**

```bash
# View encrypted file
ansible-vault view group_vars/all/vault.yml --vault-password-file ~/.vault_pass

# Debug: kiểm tra var đã được load đúng chưa
ansible localhost \
  --vault-password-file ~/.vault_pass \
  -m debug \
  -a "var=monitoring_basic_auth_password"
```

### Step 3: Dynamic Inventory với AWS EC2

**Cài AWS collection:**

```bash
# Cài ansible collection cho AWS
ansible-galaxy collection install amazon.aws

# Cài boto3 (Python library AWS SDK)
pip install boto3 botocore
```

**inventory/production/aws_ec2.yml:**

```yaml
# inventory/production/aws_ec2.yml
---
plugin: amazon.aws.aws_ec2
regions:
  - ap-southeast-1

# Filter chỉ lấy instances đang chạy với correct environment tag
filters:
  tag:Environment: production
  tag:ManagedBy: ansible
  instance-state-name: running

# Group hosts by tags
keyed_groups:
  - key: tags.Role
    prefix: role
    separator: "_"
  - key: tags.Environment
    prefix: env
    separator: "_"
  - key: placement.availability_zone
    prefix: az
    separator: "_"

# Compose ansible_host từ IP
compose:
  ansible_host: private_ip_address

# Hostname dùng private DNS (dễ đọc hơn IP)
hostnames:
  - tag:Name
  - private-dns-name

# Cache inventory 5 phút (tránh gọi API quá nhiều)
cache: true
cache_plugin: jsonfile
cache_timeout: 300
cache_connection: /tmp/ansible_aws_cache
```

**Simulate local nếu không có AWS credentials:**

```yaml
# inventory/staging/hosts.yml - Static inventory để test local
---
all:
  children:
    monitoring:
      hosts:
        node1:
          ansible_host: "127.0.0.1"
          ansible_port: 2222
          ansible_user: vagrant
          tags:
            Role: monitoring
            Environment: staging
    webservers:
      hosts:
        web1:
          ansible_host: "127.0.0.1"
          ansible_port: 2223
          ansible_user: vagrant
```

**Test dynamic inventory:**

```bash
# Set AWS credentials (hoặc dùng IAM role nếu chạy từ EC2)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="ap-southeast-1"

# List inventory
ansible-inventory -i inventory/production/aws_ec2.yml --list | python3 -m json.tool

# Xem dạng graph
ansible-inventory -i inventory/production/aws_ec2.yml --graph

# Output mẫu:
# @all:
#   |--@role_monitoring:
#   |  |--monitoring-server-01
#   |  |--monitoring-server-02
#   |--@env_production:
#   |  |--monitoring-server-01
#   |  |--web-server-01
#   |--@ungrouped:
```

### Step 4: Tạo Playbook tích hợp tất cả

**ansible.cfg:**

```ini
# ansible.cfg
[defaults]
inventory = inventory/
roles_path = roles/
host_key_checking = False
stdout_callback = yaml
vault_password_file = ~/.vault_pass
remote_user = ubuntu

[inventory]
enable_plugins = amazon.aws.aws_ec2, ini, yaml, auto

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
```

**playbooks/monitoring.yml:**

```yaml
# playbooks/monitoring.yml
---
- name: Deploy Node Exporter to monitoring servers
  hosts: role_monitoring          # Group từ dynamic inventory (tag Role=monitoring)
  become: true
  gather_facts: true

  pre_tasks:
    - name: Update apt cache
      apt:
        update_cache: true
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"
      tags: [always]

  roles:
    - role: node_exporter
      vars:
        node_exporter_version: "1.7.0"
        node_exporter_port: 9100
        node_exporter_enabled_collectors:
          - cpu
          - diskstats
          - filesystem
          - loadavg
          - meminfo
          - netdev

  post_tasks:
    - name: Send Slack notification
      uri:
        url: "{{ slack_webhook_url }}"
        method: POST
        body_format: json
        body:
          text: "Node Exporter deployed on {{ inventory_hostname }} ({{ ansible_default_ipv4.address }})"
      delegate_to: localhost
      when: slack_webhook_url is defined
      tags: [notify]
```

**Chạy playbook:**

```bash
# Chạy với static inventory (staging - local testing)
ansible-playbook playbooks/monitoring.yml \
  -i inventory/staging/ \
  --vault-password-file ~/.vault_pass \
  -v

# Dry-run trước khi apply production
ansible-playbook playbooks/monitoring.yml \
  -i inventory/production/ \
  --vault-password-file ~/.vault_pass \
  --check --diff

# Chạy production
ansible-playbook playbooks/monitoring.yml \
  -i inventory/production/ \
  --vault-password-file ~/.vault_pass \
  -v

# Chạy chỉ install tasks (không configure)
ansible-playbook playbooks/monitoring.yml \
  -i inventory/staging/ \
  --vault-password-file ~/.vault_pass \
  --tags install
```

**Expected output:**

```
PLAY [Deploy Node Exporter to monitoring servers] ******************************

TASK [Gathering Facts] *********************************************************
ok: [monitoring-server-01]

TASK [node_exporter : Validate OS is supported] ********************************
ok: [monitoring-server-01] => {
    "changed": false,
    "msg": "OS Debian is supported"
}

TASK [node_exporter : Create node_exporter system group] ***********************
changed: [monitoring-server-01]

TASK [node_exporter : Create node_exporter system user] ************************
changed: [monitoring-server-01]

TASK [node_exporter : Download node_exporter archive] **************************
changed: [monitoring-server-01]

TASK [node_exporter : Install node_exporter binary] ****************************
changed: [monitoring-server-01]

RUNNING HANDLERS ***************************************************************
TASK [node_exporter : systemd daemon reload] ***********************************
ok: [monitoring-server-01]

TASK [node_exporter : restart node_exporter] ***********************************
changed: [monitoring-server-01]

TASK [node_exporter : Verify node_exporter is accessible] **********************
ok: [monitoring-server-01]

PLAY RECAP *********************************************************************
monitoring-server-01       : ok=9    changed=5    unreachable=0    failed=0
```

### Step 5: Troubleshooting phổ biến

**Error 1: Vault password wrong hoặc file không tồn tại**

```
ERROR! Decryption failed (no vault secrets would decrypt) on group_vars/all/vault.yml
```

```bash
# Fix: Kiểm tra vault password file
cat ~/.vault_pass          # Xem password có đúng không
ls -la ~/.vault_pass       # Kiểm tra permissions (phải là 600)
chmod 600 ~/.vault_pass

# Verify file có thể decrypt
ansible-vault view group_vars/all/vault.yml --vault-password-file ~/.vault_pass
```

**Error 2: Dynamic inventory không tìm thấy hosts**

```
[WARNING]: provided hosts list is empty, only localhost is available
```

```bash
# Debug: Xem raw inventory output
ansible-inventory -i inventory/production/aws_ec2.yml --list

# Kiểm tra AWS credentials
aws sts get-caller-identity

# Kiểm tra tags trên EC2 instance
aws ec2 describe-instances \
  --filters "Name=tag:Environment,Values=production" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,Tags]'
```

**Error 3: Role không tìm thấy**

```
ERROR! the role 'node_exporter' was not found
```

```bash
# Kiểm tra ansible.cfg có đúng roles_path không
grep roles_path ansible.cfg

# Kiểm tra cấu trúc thư mục
ls roles/node_exporter/tasks/main.yml

# Chạy với debug
ansible-playbook playbooks/monitoring.yml -vvv 2>&1 | grep "role"
```

**Error 4: Template lỗi Jinja2**

```
fatal: [host]: FAILED! => {"msg": "template error while templating string: ..."}
```

```bash
# Debug: kiểm tra variable có được set không
ansible monitoring-server-01 -m debug -a "var=node_exporter_version"

# Test template locally
ansible localhost \
  -m template \
  -a "src=roles/node_exporter/templates/node_exporter.service.j2 dest=/tmp/test.service"
cat /tmp/test.service
```

---

## 6. Kiểm tra hiểu bài

**Q1:** Trong role structure, sự khác biệt giữa `defaults/main.yml` và `vars/main.yml` là gì? Khi nào dùng cái nào?

**Q2:** Bạn có một file `secrets.yml` chứa 5 biến, 3 biến là thông tin thường (host, port, database name), 2 biến là sensitive (password, API key). Bạn nên dùng encryption strategy nào (file-level hay variable-level)? Giải thích lý do.

**Q3:** Dynamic inventory group tên `role_monitoring` được tạo ra bằng cách nào từ AWS EC2 tags? Viết lại phần config trong `aws_ec2.yml` tạo ra group này.

**Q4:** Lệnh nào dùng để verify role `node_exporter` đã install đúng version mà không thực sự chạy playbook (dry-run)?

**Q5:** Một file đã encrypted bằng vault, bạn cần đổi password vault (rekey). Lệnh nào thực hiện việc này? Và tại sao không nên decrypt rồi encrypt lại bằng password mới?

---

## 7. Tóm tắt cuối ngày

### 3 điều quan trọng nhất hôm nay:

1. **Role = Terraform module cho Ansible**: Directory convention (defaults, vars, tasks, handlers, templates) tạo ra đơn vị code tái sử dụng. `defaults/main.yml` là nơi đặt configurable values, `vars/main.yml` là constants nội bộ.

2. **Vault là zero-trust secret management tối thiểu**: Không bao giờ commit plaintext credentials. Dùng naming convention `vault_*` cho encrypted vars, reference chúng trong plaintext vars. Vault password file phải ở ngoài git repo.

3. **Dynamic inventory giải quyết cloud infrastructure mutable**: Hosts không còn hardcode, tự động sync với AWS state qua tags. `keyed_groups` tạo ra inventory groups từ EC2 tags - đây là cầu nối giữa Terraform (tạo EC2 với tags) và Ansible (deploy lên EC2 theo tags).

### Output đã tạo:

- Role `node_exporter` đầy đủ production-grade tại `~/ansible-training/roles/node_exporter/`
- Vault-encrypted secrets tại `group_vars/all/vault.yml`
- Dynamic inventory config tại `inventory/production/aws_ec2.yml`
- Playbook tích hợp tại `playbooks/monitoring.yml`

### Chuẩn bị cho Day 16 - Terraform + Ansible Integration:

Day 16 sẽ kết nối Terraform và Ansible thành một workflow hoàn chỉnh:
- Terraform tạo EC2 instances với tags chuẩn
- Terraform output EC2 IPs cho Ansible inventory
- Ansible role `node_exporter` (tạo hôm nay) deploy lên EC2 vừa tạo
- `null_resource` + `local-exec` trigger Ansible từ Terraform
- `terraform_state` làm dynamic inventory source

Quan trọng: **Role `node_exporter` bạn tạo hôm nay sẽ được reuse nguyên vẹn trong Day 16.** Đảm bảo nó đã tested và idempotent trước khi sang Day 16.

---

## 8. Tham khảo thêm

- [Ansible Roles Documentation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html)
- [Ansible Galaxy Documentation](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html)
- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/vault_guide/index.html)
- [Amazon AWS Inventory Plugin](https://docs.ansible.com/ansible/latest/collections/amazon/aws/aws_ec2_inventory.html)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html)
- [Prometheus Node Exporter GitHub](https://github.com/prometheus/node_exporter)
