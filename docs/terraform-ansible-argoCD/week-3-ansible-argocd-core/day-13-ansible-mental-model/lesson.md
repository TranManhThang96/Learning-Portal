# Day 13: Ansible Mental Model & Idempotency

**Thời gian:** 2 giờ | **Level:** Beginner-Intermediate | **Phase:** 3 - Ansible Practical, Day 1

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Giải thích Ansible là gì và tại sao nó tồn tại song song với Terraform trong một production stack
- Phân biệt agentless architecture của Ansible so với agent-based tools và hiểu trade-off
- Ánh xạ các khái niệm Ansible (inventory, playbook, task, module) sang mental model từ Terraform và Kubernetes
- Giải thích idempotency là gì, tại sao nó quan trọng, và cách kiểm tra một task có idempotent hay không
- Cài đặt Ansible, viết inventory local, và chạy playbook hardening cơ bản thành công

---

## 2. Bối cảnh thực tế

### Vấn đề: "Terraform xong rồi, còn thiếu gì?"

Giả sử bạn vừa dùng Terraform để provision một EC2 instance hoặc một VM trên GCP. Infrastructure đã có — nhưng đó chỉ là một cái máy trần. Bạn cần:

- Cài `nginx`, `docker`, `node_exporter`
- Tạo user `deploy` với SSH key riêng
- Disable root login, configure firewall rules (ufw/iptables)
- Đặt kernel parameters (`/etc/sysctl.conf`)
- Deploy application code, restart service khi config thay đổi

Terraform **không làm được những thứ này một cách tự nhiên**. Terraform biết về cloud resources (VM, VPC, S3), không biết về OS-level configuration bên trong máy. Bạn có thể dùng `remote-exec` provisioner trong Terraform, nhưng đó là anti-pattern — Terraform's own documentation khuyến cáo tránh dùng provisioner khi có thể.

### Vậy trước Ansible, người ta làm gì?

```
Bash scripts + SSH manual   →  không track state, dễ drift
cloud-init                  →  chỉ chạy 1 lần khi boot, không idempotent
Chef/Puppet                 →  cần agent cài trên từng máy, heavy
Fabric/Capistrano           →  focused vào deploy, không phải configuration management
```

### Ansible giải quyết bài toán này như thế nào?

Ansible là **configuration management + automation tool** chạy qua SSH, không cần cài agent trên target machine. Bạn viết YAML mô tả trạng thái mong muốn, Ansible tìm cách đưa hệ thống về trạng thái đó — và quan trọng hơn, **running nó nhiều lần vẫn safe**.

### Trong microservices system, Ansible xuất hiện ở đâu?

```
Developer push code
       │
       ▼
CI/CD pipeline (GitHub Actions / Jenkins)
       │
       ├──► Terraform: provision infra (VM, DB, Load Balancer, Network)
       │
       ├──► Ansible: configure OS, install dependencies, harden server
       │
       └──► ArgoCD/Helm: deploy application containers vào Kubernetes
```

Ba tầng này bổ sung cho nhau, không thay thế nhau.

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 Ansible là gì? (và tại sao lại là YAML?)

Ansible là một **automation platform** cho phép bạn:

1. **Configuration Management** — đảm bảo server luôn ở trạng thái đúng
2. **Application Deployment** — deploy code, restart services
3. **Orchestration** — điều phối nhiều server theo thứ tự
4. **Ad-hoc tasks** — chạy lệnh trên nhiều server cùng lúc

Tại sao YAML? Vì Ansible muốn playbook đọc như **documentation** — một senior admin không biết code vẫn hiểu playbook đang làm gì. So sánh:

```yaml
# Ansible playbook - readable như prose
- name: Ensure nginx is installed
  apt:
    name: nginx
    state: present
```

```bash
# Bash equivalent - không self-documenting
if ! dpkg -l | grep -q nginx; then
  apt-get install -y nginx
fi
```

Tương tự lý do Terraform dùng HCL thay vì shell script.

### 3.2 Agentless Architecture

Đây là điểm khác biệt lớn nhất của Ansible so với Chef, Puppet, Salt (agent-based):

```
Agent-based (Chef/Puppet):
┌─────────────┐         ┌─────────────┐
│  Chef Server│◄────────│  Chef Agent │  ← agent phải running trên mỗi server
│  (central)  │  pull   │  (target)   │
└─────────────┘         └─────────────┘
                         Port 443 open
                         Agent process chiếm RAM
                         Agent version phải match

Agentless (Ansible):
┌─────────────┐   SSH   ┌─────────────┐
│Control Node │────────►│Managed Node │  ← chỉ cần SSH + Python
│  (bạn)      │         │  (target)   │
└─────────────┘         └─────────────┘
                         Port 22 already open
                         Không có process nào chạy nền
                         Python 3 thường đã có sẵn
```

**Trade-off:**

| | Agentless (Ansible) | Agent-based (Puppet) |
|---|---|---|
| Setup | Nhanh, SSH là đủ | Phải install và manage agent |
| Scale | OK đến ~thousands | Better ở tens of thousands |
| Real-time | Pull/push manual | Agent tự check-in định kỳ |
| Security surface | SSH only | Agent port + cert management |
| State drift detection | Khi bạn chạy | Continuous (agent tự phát hiện) |

Với team dưới 500 servers, Ansible agentless là đủ và ít overhead hơn nhiều.

### 3.3 Control Node vs Managed Node

```
Control Node                    Managed Node(s)
─────────────                   ─────────────
Máy bạn chạy ansible            Server mà Ansible quản lý
Cần Python + Ansible installed  Chỉ cần Python 3 + SSH daemon
Thường là laptop hoặc CI runner Có thể là VM, bare metal, container
Giữ inventory, playbooks        Không cần biết về Ansible
```

**Lưu ý quan trọng:** Ansible không có "server" như Terraform Cloud hay Jenkins master. Control node là bất kỳ máy nào bạn muốn chạy Ansible từ đó.

### 3.4 Mapping khái niệm: Terraform → Ansible → Kubernetes

Bạn đã biết Terraform và Kubernetes, hãy dùng chúng để neo mental model:

| Terraform | Ansible | Kubernetes | Ý nghĩa |
|-----------|---------|------------|---------|
| `main.tf` | `playbook.yml` | `deployment.yaml` | File mô tả desired state |
| `provider` | `module` | `controller` | Component thực thi action |
| `resource` | `task` | `resource` | Đơn vị cấu hình nhỏ nhất |
| `terraform.tfvars` | `inventory` | `values.yaml` | Nơi chứa biến/target |
| `module` (reusable) | `role` | `Helm chart` | Unit tái sử dụng |
| `output` | `fact` | `status.conditions` | Thông tin read-back từ resource |
| `terraform plan` | `--check mode` | `kubectl diff` | Dry run |
| `state file` | *(không có)* | `etcd` | Lưu trạng thái hiện tại |

> **Key insight:** Terraform có state file để track những gì đã tạo. Ansible **không có state file** — mỗi lần chạy, nó kiểm tra trực tiếp trên target machine xem hiện state là gì, rồi so sánh với desired state. Đây vừa là điểm mạnh (đơn giản) vừa là điểm yếu (không biết "drift" xảy ra khi nào nếu không chạy).

### 3.5 Các khái niệm core

#### Inventory

Inventory là **danh sách các target machines** Ansible sẽ quản lý. Tương tự Terraform's `provider "aws"` block định nghĩa where to connect — inventory định nghĩa which machines to connect to.

```ini
# inventory/hosts.ini (INI format)
[webservers]
web1.example.com
web2.example.com ansible_host=192.168.1.10

[databases]
db1.example.com ansible_user=ubuntu ansible_port=2222

[production:children]  # group of groups
webservers
databases
```

```yaml
# inventory/hosts.yml (YAML format - preferred)
all:
  children:
    webservers:
      hosts:
        web1.example.com: {}
        web2.example.com:
          ansible_host: 192.168.1.10
    databases:
      hosts:
        db1.example.com:
          ansible_user: ubuntu
          ansible_port: 2222
```

#### Playbook

Playbook là **file YAML mô tả automation workflow**. Một playbook chứa một hoặc nhiều "play". Mỗi play áp dụng một tập tasks lên một nhóm hosts.

```yaml
# site.yml - một playbook đơn giản
---
- name: Configure web servers          # ← play
  hosts: webservers                    # ← target group từ inventory
  become: true                         # ← sudo escalation
  
  tasks:                               # ← list of tasks
    - name: Install nginx
      apt:
        name: nginx
        state: present
    
    - name: Start and enable nginx
      service:
        name: nginx
        state: started
        enabled: true
```

So sánh với Kubernetes:

```yaml
# Kubernetes Deployment
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: nginx
        image: nginx:1.25       # desired state: container running

# Ansible Playbook  
- name: Install nginx
  apt:
    name: nginx
    state: present              # desired state: package installed
```

Cả hai đều khai báo desired state, không phải steps.

#### Task

Task là **đơn vị nhỏ nhất** trong Ansible. Mỗi task gọi một module với các parameters.

```yaml
tasks:
  - name: Create deploy user          # human-readable description
    user:                             # ← module name
      name: deploy                    # ← module parameters
      shell: /bin/bash
      create_home: true
      groups: docker
      state: present
```

#### Module

Module là **code thực thi logic** của một task — tương tự như Terraform provider resource type (`aws_instance`, `google_compute_instance`). Ansible có 3000+ built-in modules:

```
apt / yum / dnf       → package management
service               → systemd/upstart control
file                  → file/directory/symlink
copy / template       → file transfer
user / group          → OS user management
firewalld / ufw       → firewall
sysctl                → kernel parameters
git                   → git operations
docker_container      → Docker management
k8s                   → Kubernetes resources
```

Mỗi module đều **idempotent by design** — đây là khác biệt lớn với shell commands.

### 3.6 Idempotency — Khái niệm quan trọng nhất

#### Định nghĩa

Một operation là **idempotent** nếu chạy nó nhiều lần cho kết quả giống như chạy một lần.

Bạn đã biết khái niệm này từ HTTP: `PUT /users/123` là idempotent, `POST /users` thì không. Và từ Terraform: `terraform apply` nhiều lần trên unchanged config không tạo thêm resource.

#### Tại sao idempotency quan trọng trong configuration management?

```
Scenario: CI/CD pipeline chạy Ansible mỗi khi có deployment

Lần 1: nginx chưa có → install
Lần 2: nginx đã có   → skip (không chạy lại apt-get install)
Lần 3: config thay đổi → update config, restart service
Lần 4: config unchanged → skip

Nếu KHÔNG idempotent:
Lần 1: install nginx → OK
Lần 2: install nginx lại → có thể fail, hoặc corrupt config
```

#### Idempotent vs Non-idempotent

```yaml
# ✅ IDEMPOTENT - dùng Ansible module
- name: Create directory
  file:
    path: /opt/myapp
    state: directory
    mode: '0755'
# Kết quả: directory tồn tại với đúng permissions
# Chạy lần 2: kiểm tra → đã tồn tại → skip

# ❌ NON-IDEMPOTENT - dùng shell command
- name: Create directory  
  shell: mkdir /opt/myapp
# Chạy lần 2: "mkdir: cannot create directory '/opt/myapp': File exists"
# → FAIL

# ✅ FIX với creates parameter (workaround, không preferred)
- name: Create directory
  shell: mkdir /opt/myapp
  args:
    creates: /opt/myapp    # chỉ chạy nếu /opt/myapp chưa tồn tại
```

#### Cách nhận biết một task có idempotent không

| Module | Idempotent? | Ghi chú |
|--------|-------------|---------|
| `apt`, `yum` | ✅ | `state: present` check trước khi install |
| `service` | ✅ | Check running state trước |
| `file` | ✅ | Compare mode/owner/content |
| `copy`, `template` | ✅ | Compare checksum |
| `user`, `group` | ✅ | Check existence trước |
| `command`, `shell` | ❌ | Chạy mù, không check |
| `raw` | ❌ | Thuần SSH command |
| `script` | ❌ | Chạy shell script |

**Rule of thumb:** Nếu bạn thấy mình viết `command:` hoặc `shell:`, hãy tự hỏi "có module nào làm việc này không?" — thường là có.

---

## 4. Deep Dive & Trade-offs - 30 phút

### 4.1 So sánh toàn diện: Ansible vs Terraform vs Bash vs cloud-init vs Packer

```
┌─────────────┬──────────────────┬────────────────┬──────────────────┐
│  Tool       │  Best For        │  State         │  When to Use     │
├─────────────┼──────────────────┼────────────────┼──────────────────┤
│ Terraform   │ Cloud infra      │ State file     │ VMs, DBs, VPCs   │
│             │ provision        │ (explicit)     │ Network topology  │
├─────────────┼──────────────────┼────────────────┼──────────────────┤
│ Ansible     │ OS config        │ Target machine │ Package install  │
│             │ App deploy       │ (implicit)     │ File config      │
│             │ Orchestration    │                │ Service mgmt     │
├─────────────┼──────────────────┼────────────────┼──────────────────┤
│ Bash        │ One-off scripts  │ None           │ Quick automation │
│             │ Glue code        │                │ Local tasks      │
├─────────────┼──────────────────┼────────────────┼──────────────────┤
│ cloud-init  │ First boot setup │ None (once)    │ Base OS setup    │
│             │ (userdata)       │                │ AMI baking       │
├─────────────┼──────────────────┼────────────────┼──────────────────┤
│ Packer      │ Image building   │ None           │ AMI/Docker image │
│             │ AMI/OVA          │                │ Golden image     │
└─────────────┴──────────────────┴────────────────┴──────────────────┘
```

### 4.2 Khi nào dùng Ansible, khi nào KHÔNG dùng?

#### Dùng Ansible khi:

- Cần configure OS trên existing servers (package install, user management, firewall)
- Deploy application lên bare metal hoặc VM (không phải container)
- Orchestrate multi-server operations theo thứ tự (rolling deploy, database migration trước, app deploy sau)
- Bootstrap Kubernetes nodes (cài kubeadm, kubelet)
- Ad-hoc tasks: "restart nginx trên tất cả web servers"
- Khi bạn cần audit trail của changes (playbooks là code, commit vào Git)

#### KHÔNG dùng Ansible khi:

- **Provisioning cloud resources** → dùng Terraform (Ansible có modules cho AWS/GCP nhưng inferior so với Terraform)
- **Containerized applications** → dùng Kubernetes + Helm/ArgoCD
- **Immutable infrastructure pattern** → dùng Packer để build image, Terraform để deploy, không configure server sau khi bake
- **Real-time monitoring/remediation** → dùng Kubernetes operators hoặc dedicated tools
- **Secret management** → dùng Vault, AWS Secrets Manager (Ansible có thể integrate với chúng)

### 4.3 Best solution by context

| Context | Recommended Stack | Rationale |
|---------|------------------|----|
| Cá nhân/Side project | Bash + docker-compose | Overhead của Ansible không worth it |
| Small team (2-5 devs) | Ansible + Terraform | Đủ structure, không quá complex |
| Startup (5-50 servers) | Terraform + Ansible + basic CI | Automation bắt đầu thực sự cần thiết |
| Scale-up / k8s migration | Terraform + Ansible (k8s nodes) + ArgoCD | Ansible chỉ cho OS layer |
| Enterprise (k8s-first) | Terraform + Ansible (barebones) + ArgoCD | Ansible minimal vì workload trên k8s |
| Bank / Regulated | Ansible Tower / AWX + Terraform + Vault | Audit trail, role-based access cần thiết |

### 4.4 Common Pitfalls

#### Pitfall 1: Dùng `shell:` khi có module

```yaml
# ❌ Bad
- shell: systemctl enable --now nginx

# ✅ Good
- service:
    name: nginx
    state: started
    enabled: true
```

#### Pitfall 2: Hardcode paths và giá trị

```yaml
# ❌ Bad
- copy:
    src: /home/john/myapp.conf
    dest: /etc/myapp/config.conf

# ✅ Good - dùng variables (Day 14)
- copy:
    src: "{{ config_source }}"
    dest: "{{ config_dest }}"
```

#### Pitfall 3: Không dùng `become` khi cần root

```yaml
# ❌ Task sẽ fail vì không có permission
- apt:
    name: nginx
    state: present

# ✅ 
- apt:
    name: nginx
    state: present
  become: true
```

#### Pitfall 4: Không test với `--check` trước khi apply

```bash
# Luôn dry-run trước
ansible-playbook playbook.yml --check --diff
# Sau đó mới apply
ansible-playbook playbook.yml
```

#### Pitfall 5: Không dùng `--limit` khi test trên production

```bash
# ❌ Nguy hiểm - apply lên toàn bộ production group
ansible-playbook site.yml -i inventory/production/

# ✅ Test trên một host trước
ansible-playbook site.yml -i inventory/production/ --limit web1.prod.example.com
```

---

## 5. Hands-on Lab - 60 phút

### Mục tiêu Lab

Cuối lab, bạn sẽ có:
- Ansible hoạt động trên control node (laptop/WSL/VM)
- Inventory local với localhost làm managed node
- Playbook hardening cơ bản chạy thành công và idempotent

### 5.1 Cài đặt Ansible

#### Trên Ubuntu/Debian (hoặc WSL2 Ubuntu):

```bash
# Cập nhật package list
sudo apt update

# Install Python pip nếu chưa có
sudo apt install -y python3-pip python3-venv

# Cách 1: Install qua pip (recommended - version mới nhất)
pip3 install --user ansible

# Verify PATH (thêm vào ~/.bashrc nếu cần)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
ansible --version
```

Expected output:
```
ansible [core 2.17.x]
  config file = None
  configured module search path = ['/home/user/.ansible/plugins/modules', ...]
  ansible python module location = /home/user/.local/lib/python3.x/site-packages/ansible
  ansible collection location = /home/user/.ansible/collections:/usr/share/ansible/collections
  executable location = /home/user/.local/bin/ansible
  python version = 3.x.x
  ...
```

#### Trên macOS:

```bash
# Cài Homebrew nếu chưa có
brew install ansible

# Hoặc dùng pip
pip3 install ansible
```

#### Verify Python trên localhost (managed node):

```bash
# Ansible cần Python trên managed node
python3 --version
# Python 3.x.x
```

### 5.2 Tạo project structure

```bash
# Tạo project directory
mkdir -p ~/ansible-labs/day-13
cd ~/ansible-labs/day-13

# Tạo structure
mkdir -p inventory group_vars host_vars roles

# Kiểm tra structure
tree .
# .
# ├── group_vars/
# ├── host_vars/
# ├── inventory/
# └── roles/
```

### 5.3 Tạo ansible.cfg

File này config các defaults cho project — tương tự `terraform.tf` với `backend` và `required_providers`:

```bash
cat > ~/ansible-labs/day-13/ansible.cfg << 'EOF'
[defaults]
# Inventory file mặc định
inventory = ./inventory/hosts.ini

# Không check SSH host key (OK cho lab, KHÔNG dùng production)
host_key_checking = False

# Hiển thị output đẹp hơn
stdout_callback = yaml

# Số parallel connections
forks = 10

# Retry file location
retry_files_enabled = False

[ssh_connection]
# Tăng tốc SSH với pipelining
pipelining = True
EOF
```

### 5.4 Tạo inventory local

```bash
cat > ~/ansible-labs/day-13/inventory/hosts.ini << 'EOF'
# Group: local - dùng để test trên chính máy này
[local]
localhost ansible_connection=local

# Group: webservers (sẽ dùng ở bài sau khi có VM)
# web1.example.com ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
# web2.example.com ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa

# [webservers:vars]
# ansible_ssh_common_args='-o StrictHostKeyChecking=no'
EOF
```

Verify inventory:

```bash
cd ~/ansible-labs/day-13

# List tất cả hosts
ansible all --list-hosts

# Expected output:
#   hosts (1):
#     localhost

# Ping test (kiểm tra connectivity)
ansible all -m ping

# Expected output:
# localhost | SUCCESS => {
#     "changed": false,
#     "ping": "pong"
# }
```

### 5.5 Viết Playbook Hardening Cơ Bản

Playbook này sẽ thực hiện một số bước hardening cơ bản cho Linux server:

```bash
cat > ~/ansible-labs/day-13/hardening.yml << 'EOF'
---
# hardening.yml - Basic Linux Server Hardening Playbook
# Day 13 - Ansible Mental Model & Idempotency Lab
#
# Chạy: ansible-playbook hardening.yml
# Dry-run: ansible-playbook hardening.yml --check --diff

- name: Basic Linux Server Hardening
  hosts: local
  become: false  # localhost lab: set false vì không cần sudo cho local connection
                 # Production: set true

  vars:
    # Các biến sẽ học chi tiết Day 14
    app_user: "labuser"
    app_dir: "/opt/labapp"
    sysctl_settings:
      - key: net.ipv4.ip_forward
        value: "0"
      - key: net.ipv4.conf.all.send_redirects
        value: "0"
      - key: net.ipv4.conf.default.send_redirects
        value: "0"

  tasks:
    # ─── SECTION 1: Verify Python ───────────────────────────────────────────

    - name: "Check 1.1 | Verify Python3 is available"
      command: python3 --version
      register: python_version
      changed_when: false  # command luôn report changed, ta override về false

    - name: "Check 1.2 | Display Python version"
      debug:
        msg: "Python version: {{ python_version.stdout }}"

    # ─── SECTION 2: Directory Management ────────────────────────────────────

    - name: "Dir 2.1 | Create application base directory"
      file:
        path: "{{ app_dir }}"
        state: directory
        mode: "0755"
      # Idempotent: nếu đã tồn tại với đúng mode → skip (changed: false)
      # Nếu chưa tồn tại → tạo mới (changed: true)

    - name: "Dir 2.2 | Create application subdirectories"
      file:
        path: "{{ app_dir }}/{{ item }}"
        state: directory
        mode: "0750"
      loop:
        - logs
        - config
        - data
      # loop: tương tự for-loop, tạo 3 directories

    # ─── SECTION 3: File Management ─────────────────────────────────────────

    - name: "File 3.1 | Deploy hardening configuration file"
      copy:
        content: |
          # Hardening Config - Generated by Ansible
          # Do not edit manually - managed by automation
          
          APP_NAME=labapp
          APP_ENV=development
          LOG_LEVEL=info
          MAX_CONNECTIONS=100
          
          # Security settings
          DISABLE_DEBUG=true
          FORCE_HTTPS=true
        dest: "{{ app_dir }}/config/app.conf"
        mode: "0640"
      # Idempotent: so sánh checksum, chỉ update nếu content thay đổi

    - name: "File 3.2 | Create .gitkeep in empty directories"
      file:
        path: "{{ app_dir }}/{{ item }}/.gitkeep"
        state: touch
        modification_time: preserve
        access_time: preserve
      loop:
        - logs
        - data
      # modification_time: preserve → idempotent (không update timestamp nếu file đã tồn tại)

    # ─── SECTION 4: Permissions & Security ──────────────────────────────────

    - name: "Sec 4.1 | Verify directory permissions are restrictive"
      file:
        path: "{{ app_dir }}/config"
        mode: "0750"
      # Nếu mode đã đúng → skip
      # Nếu mode sai (ai đó chmod 777) → fix lại → changed: true

    - name: "Sec 4.2 | Check if sensitive files have correct permissions"
      file:
        path: "{{ app_dir }}/config/app.conf"
        mode: "0640"

    # ─── SECTION 5: Idempotency Demonstration ───────────────────────────────

    - name: "Demo 5.1 | Idempotent: Create marker file (first run)"
      copy:
        content: "Hardening applied at {{ ansible_date_time.iso8601 }}\n"
        dest: "{{ app_dir }}/config/hardening.marker"
        force: false  # IMPORTANT: false = không overwrite nếu đã tồn tại
      # Lần 1: file chưa có → tạo với timestamp hiện tại → changed: true
      # Lần 2: file đã có → skip (force: false) → changed: false

    - name: "Demo 5.2 | Non-idempotent example (DEMONSTRATION ONLY)"
      debug:
        msg: |
          LEARNING NOTE: task dưới đây dùng 'shell' để demo non-idempotency.
          Trong production, TRÁNH dùng shell: nếu có module tương đương.
          
          Ví dụ non-idempotent (đừng dùng):
            shell: echo "{{ ansible_date_time.iso8601 }}" >> /opt/labapp/logs/access.log
          
          Vấn đề: mỗi lần chạy APPEND thêm một dòng vào file.
          Ansible không biết task này đã chạy hay chưa.

    # ─── SECTION 6: Gather & Display Facts ──────────────────────────────────

    - name: "Fact 6.1 | Display system information (Ansible Facts)"
      debug:
        msg:
          - "Hostname: {{ ansible_hostname }}"
          - "OS: {{ ansible_distribution }} {{ ansible_distribution_version }}"
          - "Architecture: {{ ansible_architecture }}"
          - "Total RAM: {{ ansible_memtotal_mb }} MB"
          - "CPU cores: {{ ansible_processor_vcpus }}"
          - "Python: {{ ansible_python_version }}"

    # ─── SECTION 7: Validation ──────────────────────────────────────────────

    - name: "Val 7.1 | Verify all directories exist"
      stat:
        path: "{{ app_dir }}/{{ item }}"
      register: dir_check
      loop:
        - logs
        - config
        - data

    - name: "Val 7.2 | Assert all directories are present"
      assert:
        that:
          - item.stat.exists
          - item.stat.isdir
        fail_msg: "Directory {{ item.item }} is missing!"
        success_msg: "Directory {{ item.item }} exists ✓"
      loop: "{{ dir_check.results }}"

    - name: "Val 7.3 | Final summary"
      debug:
        msg:
          - "============================================"
          - "  Hardening Lab Complete!"
          - "============================================"
          - "  App directory: {{ app_dir }}"
          - "  Config file: {{ app_dir }}/config/app.conf"
          - "  Marker file: {{ app_dir }}/config/hardening.marker"
          - "============================================"
          - "  Run again to verify idempotency:"
          - "  ansible-playbook hardening.yml"
          - "============================================"
EOF
```

### 5.6 Chạy Playbook

#### Lần 1: Run với `--check --diff` (dry-run):

```bash
cd ~/ansible-labs/day-13

ansible-playbook hardening.yml --check --diff
```

Expected output (tóm tắt):
```yaml
PLAY [Basic Linux Server Hardening] ***************************************

TASK [Gathering Facts] ****************************************************
ok: [localhost]

TASK [Check 1.1 | Verify Python3 is available] ****************************
ok: [localhost]

TASK [Dir 2.1 | Create application base directory] ************************
--- before
+++ after
@@ -1,4 +1,4 @@
 {
     "path": "/opt/labapp",
-    "state": "absent"
+    "state": "directory"
 }
changed: [localhost]

... (more tasks)

PLAY RECAP ****************************************************************
localhost    : ok=X   changed=Y   unreachable=0   failed=0   skipped=0
```

#### Lần 1: Run thực sự:

```bash
ansible-playbook hardening.yml
```

Ghi lại số `changed` trong PLAY RECAP.

#### Lần 2: Run lại để kiểm tra idempotency:

```bash
ansible-playbook hardening.yml
```

Expected output của PLAY RECAP lần 2:
```
PLAY RECAP ****************************************************************
localhost    : ok=XX   changed=0   unreachable=0   failed=0   skipped=0
                              ^^^^
                        Phải là 0!
```

`changed=0` xác nhận playbook của bạn **hoàn toàn idempotent**.

### 5.7 Khám phá Ansible Facts

```bash
# Xem tất cả facts của localhost
ansible localhost -m setup

# Filter facts theo keyword
ansible localhost -m setup -a "filter=ansible_distribution*"
ansible localhost -m setup -a "filter=ansible_memory*"
ansible localhost -m setup -a "filter=ansible_python*"

# Chạy ad-hoc command (không cần playbook)
ansible all -m command -a "uptime"
ansible all -m file -a "path=/tmp/ansible-test state=directory"
ansible all -m debug -a "msg='Hello from Ansible'"
```

### 5.8 Troubleshooting

#### Lỗi: `ansible: command not found`

```bash
# Kiểm tra pip install location
pip3 show ansible

# Thêm vào PATH
export PATH="$HOME/.local/bin:$PATH"
# Hoặc thêm vào ~/.bashrc
```

#### Lỗi: `Permission denied` khi tạo `/opt/labapp`

```bash
# Cách 1: Tạo thư mục trước với sudo
sudo mkdir -p /opt/labapp
sudo chown $USER:$USER /opt/labapp

# Cách 2: Đổi app_dir trong playbook sang thư mục home
# vars:
#   app_dir: "{{ ansible_env.HOME }}/labapp"  # Dùng home directory thay thế
```

#### Lỗi: `Python was not found` trên Windows (non-WSL)

Ansible cần chạy trên Linux/macOS hoặc WSL2. Trên Windows thuần túy, dùng WSL2:

```bash
wsl --install  # Install WSL2 với Ubuntu
wsl            # Vào WSL shell
# Sau đó follow Ubuntu instructions ở trên
```

#### Lỗi: `[WARNING]: provided hosts list is empty`

```bash
# Kiểm tra ansible.cfg và inventory path
cat ansible.cfg | grep inventory
ansible-inventory --list  # Debug inventory
```

#### Verify kết quả sau lab:

```bash
# Kiểm tra files đã tạo
ls -la /opt/labapp/
# hoặc
ls -la ~/labapp/  # nếu dùng home dir

cat /opt/labapp/config/app.conf
cat /opt/labapp/config/hardening.marker
```

---

## 6. Kiểm tra hiểu bài

### Câu hỏi lý thuyết:

**Q1.** Giải thích tại sao Ansible được gọi là "agentless". Điều này có ưu điểm gì so với Puppet? Và nhược điểm gì?

**Q2.** Một team đang dùng Terraform để provision EC2 instances. Senior engineer đề nghị dùng Terraform `remote-exec` provisioner để install packages thay vì Ansible. Bạn sẽ phản biện như thế nào?

**Q3.** Xem task sau:

```yaml
- name: Add line to /etc/hosts
  shell: echo "192.168.1.100 myapp.internal" >> /etc/hosts
```

Task này có idempotent không? Nếu không, hãy viết lại dùng module phù hợp.

**Q4.** Trong Terraform bạn có `terraform.tfstate` để track current state. Ansible không có state file. Điều này ảnh hưởng như thế nào đến cách Ansible detect "đã làm việc này rồi hay chưa"?

### Bài tập ngắn:

**Q5.** Thêm một task vào `hardening.yml` để tạo file `/opt/labapp/config/README.txt` với nội dung:

```
This directory is managed by Ansible.
Do not edit files manually.
```

Đảm bảo task này idempotent. Chạy lại playbook 2 lần và xác nhận `changed=0` ở lần 2.

---

## 7. Tóm tắt cuối ngày

### 3 điểm quan trọng nhất:

1. **Ansible lấp khoảng trống mà Terraform và Kubernetes không cover**: OS-level configuration, package management, user management trên VMs/bare metal. Cả ba tool tồn tại cùng nhau trong production stack.

2. **Agentless via SSH là double-edged sword**: Đơn giản hơn, zero overhead, nhưng không có continuous drift detection. Chấp nhận trade-off này và compensate bằng cách chạy playbooks định kỳ (scheduled CI/CD).

3. **Idempotency không phải magic — nó là discipline**: Luôn ưu tiên module (apt, service, file, user) thay vì shell/command. Khi buộc phải dùng shell, dùng `creates:`, `removes:`, hoặc `changed_when:` để control idempotency manually. Test bằng cách chạy playbook 2 lần và verify `changed=0`.

### Output đã tạo:

```
~/ansible-labs/day-13/
├── ansible.cfg
├── hardening.yml
└── inventory/
    └── hosts.ini

/opt/labapp/ (hoặc ~/labapp/)
├── config/
│   ├── app.conf
│   ├── hardening.marker
│   └── README.txt (sau Q5)
├── logs/
│   └── .gitkeep
└── data/
    └── .gitkeep
```

### Chuẩn bị cho Day 14: Variables, Facts, Conditionals, Loops, Handlers

Ngày mai bạn sẽ học các tính năng làm cho Ansible playbooks thực sự mạnh mẽ:

- **Variables**: Parameterize playbooks (như Terraform variables)
- **Facts**: Auto-discovered system information (như Terraform data sources)
- **Conditionals**: `when:` clause (if/else trong Ansible)
- **Loops**: `loop:`, `with_items:` — đã preview hôm nay
- **Handlers**: Tasks chỉ chạy khi được notify (e.g., restart nginx chỉ khi config thay đổi)

Trước ngày mai, hãy thử thêm một vài tasks vào `hardening.yml` và chạy thử để làm quen với YAML structure và module syntax.

---

## 8. Tham khảo thêm

### Official Documentation:

- [Ansible Documentation - Getting Started](https://docs.ansible.com/ansible/latest/getting_started/index.html) — Tài liệu chính thức, rất đầy đủ
- [Ansible Module Index](https://docs.ansible.com/ansible/latest/collections/index_module.html) — Danh sách tất cả built-in modules
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html) — Production tips từ Ansible team

### Quality Resources:

- [Jeff Geerling's Ansible for DevOps](https://www.ansiblefordevops.com/) — Book bởi top Ansible contributor, có free sample chapters
- [Jeff Geerling's YouTube Channel](https://www.youtube.com/@JeffGeerling) — Practical Ansible tutorials
- [Red Hat Ansible Blog](https://www.ansible.com/blog) — Use cases và advanced patterns
- [Ansible Galaxy](https://galaxy.ansible.com/) — Community roles (như npm registry cho Ansible)

### Comparison & Architecture:

- [Ansible vs Terraform - HashiCorp Blog](https://www.hashicorp.com/resources/ansible-terraform-better-together) — Official perspective từ HashiCorp về việc dùng cả hai
- [CNCF Landscape - Configuration Management](https://landscape.cncf.io/card-mode?category=automation-configuration&grouping=category) — Overview ecosystem
