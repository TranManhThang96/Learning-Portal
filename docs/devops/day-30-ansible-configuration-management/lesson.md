# Day 30: Ansible for Configuration Management

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. Phân biệt được **configuration management** vs **provisioning** và giải thích khi nào cần Ansible trong thế giới Kubernetes/cloud-native.
2. Viết được **playbook** hoàn chỉnh với **tasks**, **handlers**, **variables**, **templates** và **roles**.
3. Chứng minh được **idempotency** — chạy playbook nhiều lần không gây side effect.
4. Thiết kế được **inventory** cho multi-environment (dev/staging/prod) với group variables.
5. Đánh giá được khi nào dùng Ansible, khi nào dùng Terraform, khi nào dùng container image, khi nào dùng Kubernetes operator.

---

## 2. Bối cảnh & Động lực

### Configuration Management vs Provisioning

Day 26-29 bạn học **provisioning** — tạo infrastructure (VPC, server, database, cluster). Nhưng sau khi tạo server, ai cài software? Ai tạo user? Ai copy config files? Ai quản lý service?

```
┌────────────────────────────────────────────────────────────┐
│                Infrastructure Lifecycle                     │
│                                                             │
│  PROVISIONING              CONFIGURATION                    │
│  (Terraform/Pulumi)        (Ansible/Chef/Puppet)           │
│                                                             │
│  ┌─────────────┐           ┌──────────────────┐            │
│  │ Tạo VPC     │           │ Cài Docker        │           │
│  │ Tạo EC2     │──────────>│ Tạo user          │           │
│  │ Tạo RDS     │           │ Copy config       │           │
│  │ Tạo SG      │           │ Start services    │           │
│  │ Tạo DNS     │           │ Setup monitoring  │           │
│  └─────────────┘           └──────────────────┘            │
│                                                             │
│  "TẠO infrastructure"      "CẤU HÌNH infrastructure"      │
└────────────────────────────────────────────────────────────┘
```

### Vì sao Ansible vẫn relevant trong thế giới Kubernetes?

```
"Kubernetes replaces Ansible!" ← KHÔNG HOÀN TOÀN ĐÚNG

Kubernetes quản lý:
✅ Container workloads
✅ Service discovery
✅ Scaling, rolling updates

Kubernetes KHÔNG quản lý:
❌ Node OS configuration
❌ Bare-metal server setup
❌ Network device config (switches, routers)
❌ Legacy VM-based applications
❌ Initial K8s cluster bootstrap
❌ On-premise hardware setup
❌ Security hardening (CIS benchmarks)
❌ Certificate management on hosts
```

**Use cases thực tế cho Ansible ngày nay:**

| Use Case | Ví dụ |
|----------|-------|
| Node bootstrapping | Cài Docker, kubelet, cấu hình OS trước khi join K8s cluster |
| Bare-metal provisioning | Setup server từ zero: BIOS, RAID, OS, network |
| Network automation | Configure Cisco/Juniper switches, firewalls |
| Legacy migration | Cấu hình VM apps chưa containerize được |
| Security hardening | Apply CIS benchmarks, patch management |
| Multi-platform | Config cả Linux, Windows, network devices |
| Day-2 operations | Certificate rotation, log rotation, cleanup jobs |

### Analogy cho developer

```
Terraform = CREATE DATABASE        → Tạo server/infrastructure
Ansible   = CREATE TABLE, INSERT   → Cấu hình software trên server
Docker    = Package application    → Bundle app + dependencies
K8s       = Run & manage packages  → Orchestrate containers

Mỗi tool giải quyết layer khác nhau.
```

---

## 3. Kiến thức nền tảng

### Ansible Architecture

```
┌────────────────────────────────────────────────────────┐
│                     CONTROL NODE                        │
│                   (máy bạn, CI/CD)                     │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │
│  │ Playbook │  │ Inventory│  │ ansible.cfg       │     │
│  │ (YAML)   │  │ (hosts)  │  │ (settings)        │     │
│  └────┬─────┘  └────┬─────┘  └──────────────────┘     │
│       │              │                                   │
│       └──────┬───────┘                                   │
│              │                                           │
│       ┌──────┴──────┐                                    │
│       │ Ansible     │                                    │
│       │ Engine      │                                    │
│       └──────┬──────┘                                    │
│              │ SSH (Linux) / WinRM (Windows)              │
└──────────────┼───────────────────────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───┴───┐ ┌───┴───┐ ┌───┴───┐
│ web-1 │ │ web-2 │ │ db-1  │    MANAGED NODES
│       │ │       │ │       │    (target servers)
└───────┘ └───────┘ └───────┘
```

**Key characteristics:**

- **Agentless**: không cần cài agent trên managed nodes — chỉ cần SSH.
- **Push model**: control node push configuration tới managed nodes.
- **YAML-based**: playbooks viết bằng YAML — dễ đọc, dễ review.
- **Idempotent**: chạy nhiều lần, kết quả giống nhau (nếu dùng đúng modules).
- **Declarative intent**: mô tả trạng thái mong muốn, Ansible tìm cách đạt được.

### Core Concepts

#### Inventory

Inventory định nghĩa **target hosts** và **groups**:

```ini
# inventory/hosts.ini

[webservers]
web-1 ansible_host=192.168.1.10
web-2 ansible_host=192.168.1.11

[databases]
db-1 ansible_host=192.168.1.20

[monitoring]
monitor-1 ansible_host=192.168.1.30

[production:children]
webservers
databases
monitoring

[production:vars]
ansible_user=deploy
ansible_ssh_private_key_file=~/.ssh/prod_key
```

#### Playbook

Playbook là file YAML mô tả **desired state** của hosts:

```yaml
---
- name: Configure web servers
  hosts: webservers
  become: true  # sudo

  vars:
    app_port: 8080
    app_user: appuser

  tasks:
    - name: Install required packages
      ansible.builtin.apt:
        name:
          - nginx
          - curl
          - jq
        state: present
        update_cache: true

    - name: Create application user
      ansible.builtin.user:
        name: "{{ app_user }}"
        shell: /bin/bash
        create_home: true

    - name: Copy NGINX config
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-available/default
        owner: root
        group: root
        mode: '0644'
      notify: restart nginx

  handlers:
    - name: restart nginx
      ansible.builtin.service:
        name: nginx
        state: restarted
```

#### Task

Task là đơn vị công việc nhỏ nhất, sử dụng **module**:

```yaml
# Module: apt (install packages)
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present    # present = install, absent = remove

# Module: copy (copy file)
- name: Copy config
  ansible.builtin.copy:
    src: files/app.conf
    dest: /etc/app/config.conf
    owner: root
    mode: '0644'

# Module: template (Jinja2 template)
- name: Render config from template
  ansible.builtin.template:
    src: templates/app.conf.j2
    dest: /etc/app/config.conf

# Module: service (manage service)
- name: Ensure nginx is running
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true     # start on boot

# Module: user (manage users)
- name: Create deploy user
  ansible.builtin.user:
    name: deploy
    groups: sudo
    shell: /bin/bash
```

#### Handler

Handler chỉ chạy khi được **notify** và chỉ chạy **1 lần cuối play**:

```yaml
tasks:
  - name: Update nginx config
    ansible.builtin.template:
      src: nginx.conf.j2
      dest: /etc/nginx/nginx.conf
    notify: restart nginx          # Trigger handler nếu file thay đổi

  - name: Update SSL cert
    ansible.builtin.copy:
      src: ssl/cert.pem
      dest: /etc/ssl/cert.pem
    notify: restart nginx          # Cùng handler, chỉ restart 1 lần

handlers:
  - name: restart nginx
    ansible.builtin.service:
      name: nginx
      state: restarted
```

#### Role

Role là package tái sử dụng — giống module trong Terraform:

```
roles/
└── webserver/
    ├── tasks/
    │   └── main.yml          # Tasks chính
    ├── handlers/
    │   └── main.yml          # Handlers
    ├── templates/
    │   └── nginx.conf.j2     # Jinja2 templates
    ├── files/
    │   └── index.html        # Static files
    ├── vars/
    │   └── main.yml          # Role variables
    ├── defaults/
    │   └── main.yml          # Default values (override-able)
    └── meta/
        └── main.yml          # Role metadata + dependencies
```

Sử dụng role:

```yaml
---
- name: Setup web servers
  hosts: webservers
  become: true
  roles:
    - webserver
    - monitoring
    - security_hardening
```

---

## 4. Deep Dive

### Ansible Execution Flow

```
1. Parse playbook.yml
   │
2. Load inventory → identify target hosts
   │
3. Gather facts (system info từ managed nodes)
   │
4. For each play:
   │
   ├── For each task:
   │   │
   │   ├── Generate Python module code
   │   ├── Copy module to managed node via SSH
   │   ├── Execute module on managed node
   │   ├── Collect result (changed/ok/failed)
   │   └── Report status
   │
   └── Run triggered handlers (once, at end of play)
   
5. Display recap summary
```

### Variable Precedence (quan trọng!)

Ansible có **22 levels** of variable precedence. Quan trọng nhất:

```
Lowest priority                              Highest priority
─────────────────────────────────────────────────────────────
role defaults          ← defaults/main.yml
inventory vars         ← inventory/group_vars/
playbook vars          ← vars: in playbook
role vars              ← vars/main.yml
task vars              ← vars: in task
extra vars (-e)        ← command line: -e "var=value"
```

**Rule of thumb**: đặt defaults trong role defaults, override trong inventory group_vars, emergency override bằng `-e`.

### Jinja2 Templates

```jinja2
{# templates/nginx.conf.j2 #}

worker_processes {{ ansible_processor_vcpus }};

http {
    upstream app {
        {% for host in groups['webservers'] %}
        server {{ hostvars[host]['ansible_host'] }}:{{ app_port }};
        {% endfor %}
    }

    server {
        listen 80;
        server_name {{ server_name | default('localhost') }};

        {% if enable_ssl | default(false) %}
        listen 443 ssl;
        ssl_certificate /etc/ssl/{{ ssl_cert_name }}.pem;
        ssl_certificate_key /etc/ssl/{{ ssl_key_name }}.key;
        {% endif %}

        location / {
            proxy_pass http://app;
        }
    }
}
```

### Idempotency Deep Dive

```yaml
# ✅ IDEMPOTENT — dùng đúng module
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present
  # Lần 1: install nginx → changed
  # Lần 2: nginx đã có → ok (no change)

# ✅ IDEMPOTENT — file module check trước khi copy
- name: Copy config
  ansible.builtin.copy:
    src: app.conf
    dest: /etc/app/config.conf
  # Lần 1: copy file → changed
  # Lần 2: file giống nhau → ok (no change)

# ❌ NON-IDEMPOTENT — shell/command modules
- name: Add line to config
  ansible.builtin.shell: echo "OPTION=true" >> /etc/app.conf
  # Lần 1: append line → changed
  # Lần 2: append AGAIN → duplicate line! ❌

# ✅ FIX: dùng lineinfile module
- name: Ensure option in config
  ansible.builtin.lineinfile:
    path: /etc/app.conf
    line: "OPTION=true"
    state: present
  # Lần 1: add line → changed
  # Lần 2: line exists → ok (no change) ✅
```

---

## 5. Trade-offs & Best Practices ⭐

### Configuration Management Tools Comparison

| Feature | Ansible | Puppet | Chef | Salt |
|---------|---------|--------|------|------|
| Architecture | Agentless (SSH) | Agent + Server | Agent + Server | Agent + Master |
| Language | YAML | Puppet DSL | Ruby DSL | YAML/Python |
| Learning curve | Low | Medium | High | Medium |
| Push/Pull | Push (default) | Pull | Pull | Push + Pull |
| Scalability | Medium (SSH) | High | High | Very High |
| Idempotency | Module-dependent | Built-in | Recipe-dependent | Built-in |
| Community | Very large | Large | Medium | Medium |
| Cloud-native fit | Good | Fair | Fair | Good |
| Best for | Config + orchestration | Large fleet mgmt | Complex configs | Event-driven |

### Khi nào dùng Ansible vs Alternatives

```
Use Ansible:
✅ Server bootstrapping (1-100 machines)
✅ Network device configuration
✅ Ad-hoc operations (patch, restart)
✅ Legacy VM management
✅ K8s node preparation
✅ Multi-platform (Linux + Windows + Network)
✅ Team không muốn install agents

Use Puppet/Chef:
✅ Large fleet (1000+ machines)
✅ Continuous enforcement (pull model)
✅ Complex dependency modeling
✅ Strict compliance requirements

Use container image + K8s:
✅ Application deployment
✅ Stateless services
✅ Rapid scaling
✅ Immutable infrastructure

Use Terraform:
✅ Infrastructure provisioning
✅ Cloud resource management
✅ State tracking for infrastructure
```

### Ansible in Kubernetes World

```
┌─────────────────────────────────────────────────┐
│             Modern Infrastructure Stack          │
│                                                  │
│  Layer 4: Applications                           │
│  Tool: Helm/Kustomize + ArgoCD                   │
│  ──────────────────────────────────              │
│  Layer 3: Kubernetes Cluster                     │
│  Tool: Terraform/Pulumi (EKS/GKE/AKS)          │
│  ──────────────────────────────────              │
│  Layer 2: Node Configuration                     │
│  Tool: Ansible / cloud-init / Packer            │
│  ──────────────────────────────────              │
│  Layer 1: Infrastructure                         │
│  Tool: Terraform/Pulumi (VPC, subnets, SG)      │
│  ──────────────────────────────────              │
│  Layer 0: Bare Metal (if on-premise)             │
│  Tool: Ansible / PXE / MAAS                     │
└─────────────────────────────────────────────────┘
```

### Best Practices

1. **Dùng modules, không dùng shell/command** (trừ khi module không tồn tại).
2. **Luôn dùng `become: true`** chỉ khi cần (least privilege).
3. **Variables trong `defaults/`**, không hardcode trong tasks.
4. **Encrypt secrets** bằng `ansible-vault`.
5. **Test playbooks** bằng `--check` (dry-run) và `--diff` (show changes).
6. **Idempotency test**: chạy 2 lần, lần 2 phải `ok` không `changed`.
7. **Tag tasks** để chạy subset: `ansible-playbook -i inventory/production/hosts.ini site.yml --tags nginx`.

---

## 6. Performance & Scalability ⭐

### SSH Connection Overhead

```
Ansible performance bottleneck #1: SSH connections

Mỗi task = 1 SSH connection (mặc định)
10 tasks × 50 hosts = 500 SSH connections

Optimizations:
1. Pipelining (giảm SSH roundtrips):
   [ssh_connection]
   pipelining = True

2. Forks (parallel execution):
   [defaults]
   forks = 20    # Default: 5

3. Mitogen plugin (3-7x faster):
   strategy_plugins = path/to/mitogen/ansible_mitogen/plugins/strategy
   strategy = mitogen_linear
```

### Scaling Patterns

| Scale | Hosts | Pattern | Tool |
|-------|-------|---------|------|
| Small | 1-10 | Direct SSH, serial | Ansible |
| Medium | 10-100 | Parallel (forks=20+), pipelining | Ansible + optimizations |
| Large | 100-500 | ansible-pull, AWX/Tower | Ansible Tower |
| Very Large | 500+ | Consider Puppet/Salt agent model | Puppet/Salt |

### Async Tasks

```yaml
# Long-running task: don't wait for completion
- name: Run database backup (takes 30 minutes)
  ansible.builtin.shell: /usr/local/bin/backup.sh
  async: 1800    # Max runtime: 30 minutes
  poll: 0        # Don't wait (fire and forget)
  register: backup_job

# Check status later
- name: Check backup status
  async_status:
    jid: "{{ backup_job.ansible_job_id }}"
  register: job_result
  until: job_result.finished
  retries: 60
  delay: 30
```

---

## 7. Security & Reliability Considerations

### Ansible Vault (Secret Management)

```bash
# Encrypt a file
ansible-vault encrypt secrets.yml

# Decrypt
ansible-vault decrypt secrets.yml

# Edit encrypted file
ansible-vault edit secrets.yml

# View encrypted file
ansible-vault view secrets.yml

# Run playbook with vault
ansible-playbook -i inventory/production/hosts.ini site.yml --ask-vault-pass
# Or with password file:
ansible-playbook -i inventory/production/hosts.ini site.yml --vault-password-file ~/.vault_pass
```

```yaml
# secrets.yml (encrypted)
---
db_password: "super-secret-password"
api_key: "sk-12345678"
```

### SSH Security

```ini
# ansible.cfg
[defaults]
host_key_checking = True        # DON'T disable in production

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=yes
```

### Privilege Escalation

```yaml
# Least privilege: only become when needed
- name: Read-only task (no sudo needed)
  ansible.builtin.command: cat /etc/hostname
  # No become

- name: Install package (needs sudo)
  ansible.builtin.apt:
    name: nginx
    state: present
  become: true
  become_user: root
```

### Audit Trail

```bash
# Enable logging
export ANSIBLE_LOG_PATH=./ansible.log

# Or in ansible.cfg
[defaults]
log_path = /var/log/ansible/ansible.log

# Callback plugin for structured logging
[defaults]
callbacks_enabled = ansible.posix.json
```

---

## 8. Hands-on Example

### Project: Ansible Playbook chạy trên localhost

Bài hands-on sử dụng `localhost` connection — không cần remote server.

**Prerequisites:**
- Ansible installed (`pip install ansible` hoặc `brew install ansible`)

#### Bước 1: Tạo project

```bash
mkdir -p ansible-demo/{roles/webapp/{tasks,handlers,templates,files,defaults},inventory}
cd ansible-demo
```

#### Bước 2: Tạo inventory

**inventory/localhost.ini:**
```ini
[local]
localhost ansible_connection=local

[local:vars]
ansible_python_interpreter=auto_silent
```

#### Bước 3: Tạo role

**roles/webapp/defaults/main.yml:**
```yaml
---
app_name: "demo-app"
app_user: "appuser"
app_port: 8080
app_env: "development"
app_log_level: "info"
app_base_dir: "/tmp/ansible-demo"
app_packages:
  - curl
  - jq
```

**roles/webapp/tasks/main.yml:**
```yaml
---
- name: Create application directory structure
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    mode: '0755'
  loop:
    - "{{ app_base_dir }}"
    - "{{ app_base_dir }}/config"
    - "{{ app_base_dir }}/logs"
    - "{{ app_base_dir }}/data"

- name: Generate application config from template
  ansible.builtin.template:
    src: app-config.json.j2
    dest: "{{ app_base_dir }}/config/app-config.json"
    mode: '0644'
  notify: reload application config

- name: Generate environment file
  ansible.builtin.template:
    src: env.j2
    dest: "{{ app_base_dir }}/config/.env"
    mode: '0600'
  notify: reload application config

- name: Copy static files
  ansible.builtin.copy:
    content: |
      <!DOCTYPE html>
      <html>
      <head><title>{{ app_name }}</title></head>
      <body>
        <h1>{{ app_name }}</h1>
        <p>Environment: {{ app_env }}</p>
        <p>Port: {{ app_port }}</p>
        <p>Managed by Ansible</p>
      </body>
      </html>
    dest: "{{ app_base_dir }}/data/index.html"
    mode: '0644'

- name: Create health check script
  ansible.builtin.copy:
    content: |
      #!/bin/bash
      CONFIG="{{ app_base_dir }}/config/app-config.json"
      if [ -f "$CONFIG" ]; then
        echo "healthy: config exists"
        exit 0
      else
        echo "unhealthy: config missing"
        exit 1
      fi
    dest: "{{ app_base_dir }}/health-check.sh"
    mode: '0755'

- name: Run health check
  ansible.builtin.command: "{{ app_base_dir }}/health-check.sh"
  register: health_result
  changed_when: false

- name: Display health check result
  ansible.builtin.debug:
    msg: "Health check: {{ health_result.stdout }}"

- name: Create log rotation config
  ansible.builtin.copy:
    content: |
      # Log rotation for {{ app_name }}
      {{ app_base_dir }}/logs/*.log {
        daily
        rotate 7
        compress
        delaycompress
        missingok
        notifempty
      }
    dest: "{{ app_base_dir }}/config/logrotate.conf"
    mode: '0644'
```

**roles/webapp/handlers/main.yml:**
```yaml
---
- name: reload application config
  ansible.builtin.debug:
    msg: "Application config reloaded for {{ app_name }}"
```

**roles/webapp/templates/app-config.json.j2:**
```json
{
  "name": "{{ app_name }}",
  "version": "1.0.0",
  "environment": "{{ app_env }}",
  "port": {{ app_port }},
  "logging": {
    "level": "{{ app_log_level }}",
    "directory": "{{ app_base_dir }}/logs"
  },
  "features": {
    "debug": {{ 'true' if app_env == 'development' else 'false' }},
    "metrics": {{ 'true' if app_env == 'production' else 'false' }}
  },
  "managed_by": "ansible",
  "generated_at": "{{ ansible_date_time.iso8601 | default('unknown') }}"
}
```

**roles/webapp/templates/env.j2:**
```
APP_NAME={{ app_name }}
APP_ENV={{ app_env }}
APP_PORT={{ app_port }}
LOG_LEVEL={{ app_log_level }}
BASE_DIR={{ app_base_dir }}
```

#### Bước 4: Tạo playbook

**site.yml:**
```yaml
---
- name: Configure web application
  hosts: local
  gather_facts: true

  vars:
    app_name: "my-webapp"
    app_env: "development"
    app_port: 8080

  roles:
    - webapp

  post_tasks:
    - name: Verify deployment
      ansible.builtin.command: cat {{ app_base_dir }}/config/app-config.json
      register: config_content
      changed_when: false

    - name: Show deployed config
      ansible.builtin.debug:
        msg: "{{ config_content.stdout | from_json }}"

    - name: List all created files
      ansible.builtin.find:
        paths: "{{ app_base_dir }}"
        recurse: true
      register: created_files

    - name: Display file list
      ansible.builtin.debug:
        msg: "{{ created_files.files | map(attribute='path') | list }}"
```

#### Bước 5: Chạy playbook

```bash
# Dry run (check mode) — preview changes without executing
ansible-playbook -i inventory/localhost.ini site.yml --check --diff

# Expected output: shows what WOULD change (yellow = would change, green = ok)

# Apply
ansible-playbook -i inventory/localhost.ini site.yml

# Expected output:
# PLAY [Configure web application] *****
# TASK [Gathering Facts] *****
# ok: [localhost]
# TASK [webapp : Create application directory structure] *****
# changed: [localhost] => (item=/tmp/ansible-demo)
# ...
# PLAY RECAP *****
# localhost: ok=10  changed=7  unreachable=0  failed=0

# Idempotency test — chạy lại lần 2
ansible-playbook -i inventory/localhost.ini site.yml

# Expected output:
# localhost: ok=10  changed=0  unreachable=0  failed=0
#                   ^^^^^^^^^ ZERO changes = idempotent ✅
```

#### Bước 6: Thử thay đổi

```bash
# Đổi environment sang production
ansible-playbook -i inventory/localhost.ini site.yml \
  -e "app_env=production app_port=9090 app_log_level=warn"

# Verify
cat /tmp/ansible-demo/config/app-config.json | python3 -m json.tool
# debug: false, metrics: true, port: 9090

# Show diff
ansible-playbook -i inventory/localhost.ini site.yml \
  -e "app_env=production" --diff
```

#### Bước 7: Cleanup

```bash
# Cleanup playbook
cat > cleanup.yml << 'EOF'
---
- name: Cleanup demo
  hosts: local
  tasks:
    - name: Remove demo directory
      ansible.builtin.file:
        path: /tmp/ansible-demo
        state: absent
EOF

ansible-playbook -i inventory/localhost.ini cleanup.yml

# Remove project
cd ..
rm -rf ansible-demo
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: shell/command thay vì module

```yaml
# ❌ Non-idempotent
- name: Install nginx
  ansible.builtin.shell: apt-get install -y nginx
  # Luôn "changed" dù nginx đã installed

# ✅ Idempotent
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present
  # "ok" nếu đã installed, "changed" nếu mới install
```

### Pitfall 2: Variable precedence confusion

```yaml
# Role defaults: app_port = 8080
# Group vars:    app_port = 9090
# Playbook vars: app_port = 3000
# Extra vars:    -e "app_port=4000"

# Kết quả: app_port = 4000 (extra vars thắng)
# Confusion: "Tôi đã set trong playbook mà sao không apply?"
```

**Fix:** Hiểu rõ variable precedence. Dùng `ansible -m debug -a "var=app_port"` để check.

### Pitfall 3: Handler không chạy khi expect

```yaml
# Handler chỉ chạy khi task "changed"
# Nếu task "ok" (không thay đổi) → handler KHÔNG trigger

# Handler chỉ chạy 1 LẦN cuối play, dù notify nhiều lần
```

### Pitfall 4: Quên `changed_when` cho command tasks

```yaml
# ❌ Luôn "changed" dù không thay đổi gì
- name: Check nginx status
  ansible.builtin.command: nginx -t

# ✅ Mark as not changed (read-only command)
- name: Check nginx status
  ansible.builtin.command: nginx -t
  changed_when: false
```

### Production Case Study: Ansible Playbook chạy 2 giờ cho 200 servers

#### Context
E-commerce company, 200 servers, Ansible playbook deploy application. Mỗi deploy mất 2+ giờ.

#### Symptom
Deploy window 2 giờ, thường bị timeout. Zero-downtime deploy không khả thi vì quá chậm.

#### Investigation
1. Default forks = 5 → chỉ 5 servers parallel.
2. Gathering facts mỗi server = 15 giây.
3. SSH connection setup mỗi task = overhead.
4. Không có pipelining.

#### Root Cause
- Default Ansible settings không optimize cho large fleet.
- Mỗi task establish new SSH connection.

#### Fix
```ini
# ansible.cfg
[defaults]
forks = 50
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
```

Kết quả: deploy giảm từ 2 giờ xuống 15 phút.

#### Lesson Learned
- Ansible defaults cho small scale — phải tune cho production.
- Pipelining + forks = biggest performance wins.
- Fact caching tránh gather facts lặp lại.
- >500 hosts → cân nhắc pull model (ansible-pull) hoặc agent-based tools.

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Phase 4

- Day 26-29: **Provisioning** (tạo infrastructure) bằng Terraform/Pulumi/CDK.
- Day 30: **Configuration Management** (cấu hình software trên infrastructure) bằng Ansible.
- Tổng hợp: Terraform tạo server → Ansible cấu hình server → Kubernetes chạy apps.

### Bài sau: Day 31 — GitOps with ArgoCD & Flux

- Day 30 hoàn thành khối kiến thức IaC tools.
- Day 31 sẽ học **GitOps** — kết hợp Git + Kubernetes + automated deployment.
- GitOps dùng Git repo (chứa manifests) làm source of truth, ArgoCD/Flux reconcile cluster về desired state.
- Đây là bước cuối Phase 4 trước khi sang Phase 5 (CI/CD).

### Roadmap Phase 4 recap

```
Day 26: IaC Principles           ✅
Day 27: Terraform Fundamentals   ✅
Day 28: Terraform Advanced       ✅
Day 29: Pulumi vs Terraform vs CDK ✅
Day 30: Ansible                  ✅ BẠN ĐANG Ở ĐÂY
Day 31: GitOps (ArgoCD & Flux)   → Bài tiếp theo
```

---

## 11. Tài liệu tham khảo

### Must-read

- [Ansible Documentation — Getting Started](https://docs.ansible.com/ansible/latest/getting_started/index.html) — Official starter guide.
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html) — Official best practices.
- [Ansible Vault Documentation](https://docs.ansible.com/ansible/latest/vault_guide/index.html) — Secret management.

### Nice-to-have

- [Ansible Galaxy](https://galaxy.ansible.com/) — Community roles and collections.
- [Ansible Lint](https://ansible.readthedocs.io/projects/lint/) — Linting cho playbooks.
- [Jeff Geerling — Ansible for DevOps](https://www.ansiblefordevops.com/) — Best practical book.

### Deep-dive

- [Ansible Module Index](https://docs.ansible.com/ansible/latest/collections/index_module.html) — Tất cả built-in modules.
- [Ansible Performance Tuning](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_strategies.html) — Scaling Ansible.
- [Mitogen for Ansible](https://mitogen.networkgenomics.com/ansible_detailed.html) — 3-7x performance improvement.

