# Day 13: Ansible Mental Model & Idempotency — Reference Document

**Cheat sheets, comparison matrices, quick reference cho Day 13**

---

## 1. Ansible CLI Quick Reference

### Lệnh hay dùng nhất

```bash
# ── Inventory ──────────────────────────────────────────────────────────────
ansible-inventory --list                     # JSON dump toàn bộ inventory
ansible-inventory --list --yaml              # YAML format
ansible-inventory --graph                    # Hiển thị dạng cây
ansible all --list-hosts                     # List hosts

# ── Ping & Connectivity ────────────────────────────────────────────────────
ansible all -m ping                          # Test connection tới tất cả hosts
ansible webservers -m ping                   # Test connection tới group
ansible web1.example.com -m ping             # Test connection tới 1 host

# ── Ad-hoc Commands ────────────────────────────────────────────────────────
ansible all -m command -a "uptime"           # Chạy command
ansible all -m shell -a "df -h | grep /dev" # Chạy shell pipeline
ansible all -m setup                         # Xem tất cả facts
ansible all -m setup -a "filter=ansible_os*" # Filter facts

# ── Playbook Execution ─────────────────────────────────────────────────────
ansible-playbook site.yml                    # Chạy playbook
ansible-playbook site.yml --check           # Dry-run (check mode)
ansible-playbook site.yml --check --diff    # Dry-run + hiện diff
ansible-playbook site.yml --limit web1      # Chỉ chạy trên web1
ansible-playbook site.yml --tags "install"  # Chỉ chạy tasks có tag "install"
ansible-playbook site.yml --skip-tags "security" # Skip tasks có tag
ansible-playbook site.yml -v                # Verbose (thêm v để tăng level: -vvv)
ansible-playbook site.yml --start-at-task "Install nginx"  # Bắt đầu từ task cụ thể

# ── Variable Override ──────────────────────────────────────────────────────
ansible-playbook site.yml -e "env=production"      # Override variable
ansible-playbook site.yml -e "@vars.yml"           # Load từ file
ansible-playbook site.yml -e '{"version":"1.2.3"}' # JSON format

# ── Syntax & Lint ──────────────────────────────────────────────────────────
ansible-playbook site.yml --syntax-check    # Check YAML syntax
ansible-lint site.yml                       # Best practices lint (pip install ansible-lint)
```

---

## 2. Ansible Concept → Terraform Concept Mapping

| Ansible Concept | Terraform Equivalent | Kubernetes Equivalent | Mô tả |
|----------------|---------------------|----------------------|-------|
| `inventory` | `provider` config | kubeconfig context | Định nghĩa target(s) để connect |
| `playbook` | `main.tf` | `kustomization.yaml` | File mô tả desired state |
| `play` | resource group trong file | một `kustomize` overlay | Nhóm tasks áp dụng lên hosts |
| `task` | `resource` block | individual manifest | Đơn vị nhỏ nhất |
| `module` | provider resource type | kind (Deployment, Service) | Implements logic của task |
| `role` | Terraform `module` | Helm chart | Reusable unit |
| `handler` | *(không có)*| livenessProbe restart | Task chạy khi được notify |
| `fact` | `data` source | `status` fields | Read-back info từ system |
| `group_vars` | `.tfvars` file | `values.yaml` | Variables cho nhóm |
| `host_vars` | workspace variables | per-env values | Variables cho host cụ thể |
| `--check` mode | `terraform plan` | `kubectl diff` | Dry-run |
| `register` | `output` value | `${resource.field}` | Capture result |
| `ansible-vault` | Terraform sensitive var / Vault | Secret resource | Secret management |
| *(no state file)* | `terraform.tfstate` | etcd | Tracking current state |

---

## 3. Module Cheat Sheet — Nhóm theo chức năng

### 3.1 Package Management

```yaml
# apt (Debian/Ubuntu)
- apt:
    name: "{{ item }}"
    state: present        # present | absent | latest
    update_cache: true    # apt update trước khi install
  loop: [nginx, curl, git]

# yum/dnf (RHEL/CentOS/Amazon Linux)
- dnf:
    name: nginx
    state: present

# pip (Python packages)
- pip:
    name: flask
    version: "2.3.0"
    state: present
    executable: pip3
```

### 3.2 Service Management

```yaml
- service:
    name: nginx
    state: started      # started | stopped | restarted | reloaded
    enabled: true       # start on boot
```

### 3.3 File & Directory

```yaml
# Tạo directory
- file:
    path: /opt/myapp
    state: directory    # directory | file | link | absent | touch
    mode: "0755"
    owner: deploy
    group: deploy

# Tạo symlink
- file:
    src: /opt/myapp/current
    dest: /opt/myapp/live
    state: link

# Xóa
- file:
    path: /tmp/old-file
    state: absent
```

### 3.4 File Copy & Template

```yaml
# Copy static file
- copy:
    src: files/nginx.conf         # relative to playbook
    dest: /etc/nginx/nginx.conf
    mode: "0644"
    backup: true                  # backup file cũ trước khi overwrite

# Copy với inline content
- copy:
    content: "Hello World\n"
    dest: /tmp/hello.txt
    force: false                  # không overwrite nếu đã tồn tại → idempotent

# Template (Jinja2)
- template:
    src: templates/app.conf.j2    # .j2 file với {{ variables }}
    dest: /etc/myapp/app.conf
    mode: "0640"
```

### 3.5 User & Group

```yaml
- user:
    name: deploy
    shell: /bin/bash
    groups: [docker, sudo]
    append: true            # append vào groups, không replace
    create_home: true
    state: present

- authorized_key:
    user: deploy
    key: "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"
    state: present
```

### 3.6 System & Kernel

```yaml
# Kernel parameters
- sysctl:
    name: net.ipv4.ip_forward
    value: "0"
    sysctl_set: true
    state: present
    reload: true

# Hostname
- hostname:
    name: web1.example.com
```

### 3.7 Command & Shell (dùng khi không có module)

```yaml
# command: không dùng shell operators (|, >, &&)
- command: /usr/bin/myapp --init
  args:
    creates: /opt/myapp/.initialized   # skip nếu file exists → idempotent workaround
    chdir: /opt/myapp

# shell: dùng full shell
- shell: "ps aux | grep nginx | grep -v grep"
  register: nginx_process
  changed_when: false        # đây là check command, không "change" gì

# Khi nào changed_when hợp lý:
- shell: /opt/myapp/migrate.sh
  register: migrate_result
  changed_when: "'no changes' not in migrate_result.stdout"
```

### 3.8 Debug & Assert

```yaml
- debug:
    msg: "Value is: {{ my_var }}"

- debug:
    var: my_dict              # dump toàn bộ variable

- assert:
    that:
      - result.rc == 0
      - "'Error' not in result.stderr"
    fail_msg: "Migration failed!"
    success_msg: "Migration OK"
```

---

## 4. Inventory Format Reference

### INI Format

```ini
# Hosts đơn lẻ
server1.example.com
server2.example.com ansible_host=10.0.0.2

# Groups
[webservers]
web1.example.com
web2.example.com

[databases]
db1.example.com ansible_user=postgres ansible_port=5432

# Group variables
[webservers:vars]
http_port=80
max_connections=200

# Group of groups
[production:children]
webservers
databases

# All variables áp dụng cho mọi hosts
[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

### YAML Format (recommended cho complex inventories)

```yaml
all:
  vars:
    ansible_python_interpreter: /usr/bin/python3
  
  children:
    production:
      children:
        webservers:
          vars:
            http_port: 80
          hosts:
            web1.example.com:
              ansible_host: 10.0.0.11
            web2.example.com:
              ansible_host: 10.0.0.12
        
        databases:
          hosts:
            db1.example.com:
              ansible_user: postgres
              ansible_port: 5432
    
    staging:
      hosts:
        staging.example.com:
          ansible_host: 10.0.1.10
```

### Connection Variables (hay dùng nhất)

```ini
ansible_host=192.168.1.10          # IP address hoặc hostname khác với inventory name
ansible_port=2222                  # SSH port (default: 22)
ansible_user=ubuntu                # SSH user (default: current user)
ansible_ssh_private_key_file=~/.ssh/mykey  # SSH private key
ansible_connection=local           # local | ssh | docker | winrm
ansible_python_interpreter=/usr/bin/python3  # Python path trên managed node
ansible_become=true                # Auto sudo
ansible_become_method=sudo         # sudo | su | pbrun
ansible_become_user=root           # user để become
```

---

## 5. Idempotency Decision Tree

```
Tôi cần thực hiện X trên server...
│
├─► Có Ansible module cho X không?
│   (search: https://docs.ansible.com/ansible/latest/collections/index_module.html)
│   │
│   ├─► CÓ → Dùng module đó. Mặc định idempotent.
│   │         Ví dụ: apt, service, file, user, copy, template, sysctl
│   │
│   └─► KHÔNG → Dùng command: hoặc shell:
│               │
│               ├─► Có file/thư mục nào chứng tỏ đã chạy rồi không?
│               │   └─► CÓ → Dùng `creates:` parameter
│               │   
│               ├─► Command chỉ READ không WRITE?
│               │   └─► CÓ → Dùng `changed_when: false`
│               │
│               └─► Output của command cho biết "no change" hay "changed"?
│                   └─► CÓ → Parse output và dùng `changed_when:`
│
└─► Sau khi xong: CHẠY PLAYBOOK 2 LẦN
    Lần 2 phải có changed=0
```

---

## 6. ansible.cfg Reference

```ini
[defaults]
# ── Inventory ──────────────────────────────────────────────────────────────
inventory          = ./inventory/hosts.ini      # Default inventory file
# inventory        = /etc/ansible/hosts         # System-wide default

# ── Connection ─────────────────────────────────────────────────────────────
remote_user        = ubuntu                     # Default SSH user
private_key_file   = ~/.ssh/id_rsa              # Default SSH key
host_key_checking  = True                       # Set False chỉ cho lab
timeout            = 30                         # SSH connection timeout (seconds)

# ── Execution ──────────────────────────────────────────────────────────────
forks              = 10                         # Parallel connections
any_errors_fatal   = False                      # Stop tất cả hosts khi 1 host fail
gather_facts       = True                       # Auto gather facts (tốn ~1-2s)

# ── Output ─────────────────────────────────────────────────────────────────
stdout_callback    = yaml                       # yaml | json | minimal | debug
nocows             = True                       # Tắt cowsay

# ── Roles & Collections ────────────────────────────────────────────────────
roles_path         = ./roles:~/.ansible/roles
collections_path   = ~/.ansible/collections

# ── Retry & Logging ────────────────────────────────────────────────────────
retry_files_enabled = False
log_path           = ./ansible.log              # Log to file

[ssh_connection]
pipelining         = True                       # Giảm SSH roundtrips, tăng tốc ~30%
ssh_args           = -o ControlMaster=auto -o ControlPersist=60s  # Connection multiplexing
control_path       = %(directory)s/%%h-%%r      # Control socket path

[privilege_escalation]
become             = False                      # Default không sudo
become_method      = sudo
become_user        = root
become_ask_pass    = False
```

---

## 7. Playbook Structure — Full Template

```yaml
---
# playbook-template.yml
# Sử dụng làm starting point cho playbooks mới

- name: Descriptive play name                  # Required, meaningful name
  hosts: webservers                            # Group từ inventory
  gather_facts: true                           # true (default) | false (tăng tốc nếu không cần facts)
  become: true                                 # Sudo escalation
  become_user: root

  # Variables (override bằng -e, group_vars, host_vars)
  vars:
    app_version: "1.0.0"
    deploy_user: deploy

  # Variables từ files bên ngoài
  vars_files:
    - vars/common.yml
    - vars/{{ env }}.yml                       # Dynamic based on variable

  # Pre-tasks chạy trước khi roles
  pre_tasks:
    - name: Update apt cache
      apt:
        update_cache: true
        cache_valid_time: 3600                 # Chỉ update nếu cache > 1 giờ

  # Roles (Day 16)
  roles:
    - common
    - nginx
    - { role: app, app_env: production }

  # Tasks chính
  tasks:
    - name: Task name                          # Required
      module_name:                             # Module
        param1: value1
        param2: value2
      become: true                             # Override per-task
      when: ansible_os_family == "Debian"     # Conditional
      notify: Restart nginx                   # Trigger handler
      register: task_result                   # Capture output
      loop: "{{ list_variable }}"             # Iterate
      tags: [install, setup]                  # Tag for selective run
      ignore_errors: false                    # Dừng nếu fail (default)
      no_log: true                            # Không log output (cho sensitive data)

  # Post-tasks chạy sau roles và tasks
  post_tasks:
    - name: Verify deployment
      uri:
        url: http://localhost/health
        status_code: 200

  # Handlers: chỉ chạy khi được notify
  handlers:
    - name: Restart nginx
      service:
        name: nginx
        state: restarted
```

---

## 8. Ansible Architecture Diagram — Full Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONTROL NODE                            │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Inventory│  │ Playbooks  │  │  Roles   │  │ansible.cfg  │  │
│  │hosts.ini │  │site.yml    │  │ /common  │  │             │  │
│  │hosts.yml │  │deploy.yml  │  │ /nginx   │  │             │  │
│  └──────────┘  └────────────┘  └──────────┘  └─────────────┘  │
│                       │                                        │
│              ansible-playbook                                  │
│                       │                                        │
└───────────────────────┼────────────────────────────────────────┘
                        │ SSH (Port 22)
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Managed    │ │ Managed    │ │ Managed    │
   │ Node 1     │ │ Node 2     │ │ Node 3     │
   │            │ │            │ │            │
   │ Python 3   │ │ Python 3   │ │ Python 3   │
   │ SSH daemon │ │ SSH daemon │ │ SSH daemon │
   │            │ │            │ │            │
   │ web1       │ │ web2       │ │ db1        │
   └────────────┘ └────────────┘ └────────────┘

Quá trình thực thi mỗi task:
1. Control node đọc playbook
2. Kết nối SSH tới managed node
3. Copy Python module code lên managed node (/tmp/.ansible/...)
4. Execute module trên managed node
5. Module kiểm tra current state
6. Nếu current != desired → thực hiện thay đổi
7. Trả về JSON result (changed: true/false, stderr, stdout)
8. Cleanup temp files
```

---

## 9. Comparison: Ansible vs Alternatives

### Khi nào chọn cái nào

```
Task: Install packages, configure files, manage users, OS hardening
→ ANSIBLE ✅ (đây là use case chính của Ansible)

Task: Provision VM, VPC, Load Balancer, Database trên cloud
→ TERRAFORM ✅ (Ansible có thể nhưng Terraform tốt hơn nhiều)

Task: Deploy containerized app vào Kubernetes
→ ARGOCD / HELM ✅ (Ansible có k8s module nhưng không phải best tool)

Task: Build immutable server image (AMI, OVA)
→ PACKER ✅ (có thể dùng Ansible làm provisioner bên trong Packer)

Task: One-time first boot setup
→ CLOUD-INIT ✅ (đơn giản hơn Ansible cho trường hợp này)

Task: Complex pipeline, build system, test automation
→ MAKEFILE / TASKFILE / BASH ✅ (overhead của Ansible không worth it)
```

### Feature Matrix

| Feature | Ansible | Terraform | Chef | Puppet | Salt |
|---------|---------|-----------|------|--------|------|
| Agent required | No | No | Yes | Yes | Optional |
| Language | YAML | HCL | Ruby DSL | Puppet DSL | YAML/Jinja2 |
| State tracking | Implicit | Explicit (file) | Server | Server | Master |
| Push/Pull | Push | Push | Pull | Pull | Both |
| Cloud provisioning | Limited | Excellent | Limited | Limited | Limited |
| OS config mgmt | Excellent | Poor | Excellent | Excellent | Good |
| Learning curve | Low | Medium | High | High | Medium |
| Agentless | Yes | Yes | No | No | Optional |
| Windows support | WinRM | Yes | Yes | Yes | Yes |
| Community size | Very Large | Large | Medium | Medium | Medium |

---

## 10. Jinja2 Template Basics (Preview cho Day 14-15)

Ansible dùng Jinja2 templating trong cả task parameters và `.j2` template files:

```jinja2
{# Variable substitution #}
{{ variable_name }}
{{ ansible_hostname }}
{{ app_version | default('1.0.0') }}    {# default filter #}
{{ my_list | length }}                  {# length filter #}
{{ my_string | upper }}                 {# string filter #}

{# Conditionals trong template file #}
{% if env == 'production' %}
log_level = error
{% else %}
log_level = debug
{% endif %}

{# Loops trong template file #}
{% for server in groups['webservers'] %}
upstream {{ server }} {
    server {{ hostvars[server]['ansible_host'] }}:8080;
}
{% endfor %}

{# Comments (không xuất hiện trong output) #}
{# This is a Jinja2 comment #}
```

---

## 11. Quick Troubleshooting Reference

| Triệu chứng | Nguyên nhân thường gặp | Fix |
|-------------|------------------------|-----|
| `SSH connection refused` | SSH daemon không chạy, sai port | Kiểm tra `ansible_port`, firewall |
| `Permission denied (publickey)` | Sai SSH key hoặc user | Kiểm tra `ansible_user`, `ansible_ssh_private_key_file` |
| `Python not found` | Python không installed hoặc sai path | Set `ansible_python_interpreter=/usr/bin/python3` |
| `[WARNING] No inventory was parsed` | ansible.cfg không tìm thấy inventory | Kiểm tra path trong `ansible.cfg` |
| `changed=X` ở lần 2 | Playbook không idempotent | Tìm tasks dùng `shell:` hoặc `command:` không có guard |
| `Timeout waiting for privilege escalation` | `become: true` nhưng sudo cần password | Thêm `-K` flag hoặc config NOPASSWD |
| `UNREACHABLE` | Host không accessible | Check network, SSH, firewall |
| `fatal: [host]: FAILED!` với JSON | Xem `msg` field trong output | Chạy với `-v` để xem detail |
