# Day 14: Variables, Facts, Conditionals, Loops, Handlers

**Thời gian:** 2 giờ | **Level:** Intermediate | **Phase:** 3 - Ansible Practical, Day 2

---

## 1. Mục tiêu ngày học

Sau ngày học này, bạn có thể:

- Giải thích **variable precedence** trong Ansible và biết tại sao nó quan trọng trong production
- Thu thập và sử dụng **facts** để viết playbook adaptive theo OS/environment
- Viết **conditionals** (`when`) và **loops** (`loop`) đúng cách, tránh các anti-pattern phổ biến
- Implement **handler** để restart service chỉ khi có thay đổi thực sự (idempotent)
- Tạo **Jinja2 template** config file động và deploy qua Ansible

---

## 2. Bối cảnh thực tế

### Vấn đề: "Works on my machine" ở cấp độ infrastructure

Bạn đang manage 3 môi trường: `dev`, `staging`, `production`. Mỗi môi trường có:
- Ports khác nhau (nginx listen 8080 ở dev, 443 ở prod)
- Resource limits khác nhau (worker_processes khác nhau)
- OS khác nhau (Ubuntu 20.04, Ubuntu 22.04, CentOS 7)

**Nếu không có variable management tốt:**

```
# Hardcode → disaster
- name: Configure nginx
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  # Config có worker_processes: 4 hardcoded
  # Dev server chỉ có 2 CPU → performance issues
  # Prod server 32 CPU → under-utilized
```

**Nếu không có handler:**

```
# Restart mỗi lần run → downtime không cần thiết
- name: Deploy config
  template: ...
- name: Restart nginx       # ← Luôn restart, dù config không thay đổi
  service:
    name: nginx
    state: restarted
```

**Kết quả:** Production restart 3 lần mỗi ngày khi chạy CI/CD, dù không có gì thay đổi. Users gặp downtime.

**Handler giải quyết:** Chỉ restart khi config thực sự thay đổi. Đây là idempotency ở cấp service lifecycle.

---

## 3. Kiến thức nền tảng - 30 phút

### 3.1 Variables và Precedence

Ansible có **22 levels of variable precedence**. Bạn không cần nhớ hết, nhưng cần nắm quy tắc cốt lõi:

```
THẤP nhất → CAO nhất (cao hơn overrides thấp hơn)

[1]  role defaults          (roles/myrole/defaults/main.yml)
[2]  inventory file vars    (group_vars/, host_vars/)
[3]  playbook group_vars
[4]  playbook host_vars
[5]  host facts / cached facts
[6]  play vars              (vars: trong play)
[7]  play vars_prompt
[8]  play vars_files
[9]  role vars              (roles/myrole/vars/main.yml)
[10] block vars
[11] task vars
[12] include_vars
[13] set_facts / registered vars
[14] role (and include_role) params
[15] include params
[16] extra vars             (ansible-playbook -e "key=val")  ← HIGHEST
```

**Analogy với programming:** Nghĩ như function scope trong JavaScript:
- `role defaults` = default parameter values
- `group_vars` = module-level constants
- `play vars` = function-local variables
- `-e extra_vars` = `process.env` - override everything

**Quy tắc thực tế (áp dụng 90% cases):**

```
role/defaults/main.yml      → Defaults, luôn được override
group_vars/all.yml          → Shared across all hosts
group_vars/production.yml   → Production-specific
host_vars/web01.yml         → Host-specific overrides
play vars:                  → Explicit trong playbook
ansible-playbook -e         → Emergency override, dùng sparingly
```

**Ví dụ cụ thể:**

```yaml
# group_vars/all.yml
nginx_port: 80
nginx_worker_processes: "auto"

# group_vars/production.yml
nginx_worker_processes: 8   # Override cho production

# host_vars/web01-prod.yml
nginx_port: 8080            # Host-specific override

# Trong template nginx.conf.j2:
# worker_processes {{ nginx_worker_processes }};
# listen {{ nginx_port }};
```

**Khi chạy trên web01-prod:**
- `nginx_port` = 8080 (từ host_vars - cao hơn group_vars)
- `nginx_worker_processes` = 8 (từ group_vars/production - cao hơn all)

### 3.2 Facts - System Information Gathering

**Facts** là thông tin Ansible tự động thu thập về managed host trước khi chạy tasks.

```
Ansible connects → Runs setup module → Gathers facts → Available as variables
```

**Xem facts của một host:**

```bash
ansible web01 -m setup
ansible web01 -m setup -a "filter=ansible_os_family"
ansible web01 -m setup | grep -i memory
```

**Facts quan trọng nhất:**

```yaml
ansible_os_family        # "Debian", "RedHat"
ansible_distribution     # "Ubuntu", "CentOS"
ansible_distribution_version  # "22.04", "7"
ansible_architecture     # "x86_64", "aarch64"
ansible_processor_count  # Số CPU cores
ansible_memtotal_mb      # Total RAM in MB
ansible_default_ipv4.address  # Primary IP
ansible_hostname         # Hostname
ansible_fqdn             # Fully qualified domain name
ansible_env              # Environment variables dict
```

**Sử dụng facts trong task:**

```yaml
- name: Show system info
  debug:
    msg: |
      OS: {{ ansible_distribution }} {{ ansible_distribution_version }}
      CPU: {{ ansible_processor_count }} cores
      RAM: {{ ansible_memtotal_mb }}MB
      IP: {{ ansible_default_ipv4.address }}

- name: Set worker processes based on CPU
  set_fact:
    nginx_worker_processes: "{{ ansible_processor_count }}"
```

**Custom facts** - đặt file `.ini` hoặc `.json` trong `/etc/ansible/facts.d/` trên managed host:

```ini
# /etc/ansible/facts.d/app.fact
[application]
version = 2.1.0
deploy_date = 2025-01-15
environment = production
```

Sau đó access qua: `{{ ansible_local.app.application.version }}`

**Tắt fact gathering khi không cần (tăng tốc):**

```yaml
- hosts: all
  gather_facts: false     # Tắt - tiết kiệm 1-3 giây per host
  tasks:
    - name: Just install a package
      apt:
        name: curl
        state: present
```

### 3.3 Conditionals với `when`

**Syntax cơ bản:**

```yaml
- name: Install Apache on Debian
  apt:
    name: apache2
    state: present
  when: ansible_os_family == "Debian"

- name: Install Apache on RedHat
  yum:
    name: httpd
    state: present
  when: ansible_os_family == "RedHat"
```

**Analogy:** `when` = `if` statement trong Python, nhưng evaluated AFTER task definition.

**Multiple conditions:**

```yaml
# AND
when:
  - ansible_os_family == "Debian"
  - ansible_distribution_version is version("20.04", ">=")

# OR
when: ansible_os_family == "Debian" or ansible_os_family == "RedHat"

# NOT
when: not ansible_check_mode

# Variable defined/undefined
when: my_variable is defined
when: my_variable is undefined
```

**Điều kiện với registered variables:**

```yaml
- name: Check if nginx is installed
  command: which nginx
  register: nginx_check
  ignore_errors: true

- name: Install nginx if not found
  apt:
    name: nginx
    state: present
  when: nginx_check.rc != 0
```

**Jinja2 filters trong when:**

```yaml
when: "'production' in group_names"
when: inventory_hostname in groups['webservers']
when: my_list | length > 0
when: my_string | lower == "enabled"
```

### 3.4 Loops với `loop` và `with_items`

**Modern syntax (`loop` - Ansible 2.5+):**

```yaml
- name: Install multiple packages
  apt:
    name: "{{ item }}"
    state: present
  loop:
    - nginx
    - curl
    - vim
    - htop
```

**Loop với dictionaries:**

```yaml
- name: Create multiple users
  user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
    state: present
  loop:
    - { name: "alice", groups: "sudo,docker" }
    - { name: "bob", groups: "docker" }
    - { name: "charlie", groups: "sudo" }
```

**Loop với index:**

```yaml
- name: Print items with index
  debug:
    msg: "Item {{ ansible_loop.index }}: {{ item }}"
  loop:
    - alpha
    - beta
    - gamma
  loop_control:
    label: "{{ item }}"  # Control display output
```

**`with_items` (legacy, vẫn hoạt động nhưng `loop` được prefer):**

```yaml
# Old style - still works
- name: Create directories
  file:
    path: "{{ item }}"
    state: directory
  with_items:
    - /opt/myapp
    - /opt/myapp/logs
    - /opt/myapp/config
```

**Loop với `until` (retry loop):**

```yaml
- name: Wait for port 80 to be open
  wait_for:
    port: 80
    delay: 5
  register: port_check
  until: port_check is success
  retries: 10
  delay: 5
```

**Anti-pattern - đừng dùng loop cho apt với list:**

```yaml
# BAD: N separate apt calls
- apt:
    name: "{{ item }}"
  loop: [nginx, curl, vim]

# GOOD: Single apt call
- apt:
    name:
      - nginx
      - curl
      - vim
    state: present
```

### 3.5 Handlers và Notify Mechanism

**Handler là gì?** Là task đặc biệt chỉ chạy khi được "notify" VÀ khi có ít nhất một task đã changed.

```
Task changed → notify handler → Handler runs once at end of play
Task no change → handler NOT notified → Handler does NOT run
```

**Analogy với programming:** Handler giống như event listener trong JavaScript:
- `notify: restart nginx` = `emitter.emit('restart-nginx')`
- Handler chỉ fire một lần dù được emit nhiều lần = debounced event

```yaml
---
- hosts: webservers
  tasks:
    - name: Deploy nginx config
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
      notify: restart nginx        # Notify nếu config thay đổi

    - name: Deploy nginx vhost
      template:
        src: vhost.conf.j2
        dest: /etc/nginx/sites-available/myapp.conf
      notify: restart nginx        # Cùng notify - handler chỉ chạy 1 lần

    - name: Enable vhost
      file:
        src: /etc/nginx/sites-available/myapp.conf
        dest: /etc/nginx/sites-enabled/myapp.conf
        state: link
      notify:
        - reload nginx             # Notify multiple handlers
        - check nginx config       # Handlers run in order defined

  handlers:
    - name: restart nginx
      service:
        name: nginx
        state: restarted

    - name: reload nginx
      service:
        name: nginx
        state: reloaded

    - name: check nginx config
      command: nginx -t
```

**Handler execution flow:**

```
Play starts
├── Task 1: Deploy nginx.conf → CHANGED → notify "restart nginx"
├── Task 2: Deploy vhost.conf → CHANGED → notify "restart nginx" (dup, ignored)
├── Task 3: Enable vhost → CHANGED → notify "reload nginx", "check nginx config"
└── All tasks done → Run handlers (in definition order)
    ├── restart nginx → runs
    ├── reload nginx → runs
    └── check nginx config → runs
```

**Force handler execution với `meta: flush_handlers`:**

```yaml
tasks:
  - name: Update config
    template:
      src: app.conf.j2
      dest: /etc/app/app.conf
    notify: restart app

  - meta: flush_handlers    # Restart ngay, không đợi cuối play

  - name: Run health check
    uri:
      url: http://localhost:8080/health
```

**Listen keyword - handler group:**

```yaml
handlers:
  - name: restart webstack
    listen: "web services change"
    service:
      name: nginx
      state: restarted

  - name: restart php-fpm
    listen: "web services change"
    service:
      name: php8.1-fpm
      state: restarted

tasks:
  - name: Update app config
    template:
      src: app.conf.j2
      dest: /etc/app.conf
    notify: "web services change"   # Triggers both handlers
```

---

## 4. Deep Dive & Trade-offs - 30 phút

### 4.1 Jinja2 Templates

Ansible sử dụng **Jinja2** làm templating engine. Nếu bạn biết Python/Django/Flask, Jinja2 rất quen thuộc.

<div v-pre>

**File template được đặt trong `templates/` directory:**

```
playbook.yml
templates/
  nginx.conf.j2
  app.env.j2
group_vars/
  all.yml
```

**Cú pháp Jinja2 cơ bản:**

```jinja2
{# Comment - không xuất hiện trong output #}

{# Variables #}
{{ variable_name }}
{{ dict_var.key }}
{{ list_var[0] }}

{# Filters #}
{{ name | upper }}
{{ name | lower }}
{{ name | default('anonymous') }}
{{ list | join(', ') }}
{{ number | int }}
{{ string | bool }}

{# Conditionals #}
{% if environment == "production" %}
worker_processes {{ ansible_processor_count }};
{% else %}
worker_processes 1;
{% endif %}

{# Loops #}
{% for server in upstream_servers %}
    server {{ server.host }}:{{ server.port }} weight={{ server.weight | default(1) }};
{% endfor %}
```

**Ví dụ thực tế - nginx.conf.j2:**

```jinja2
user www-data;
worker_processes {{ nginx_worker_processes | default('auto') }};
pid /run/nginx.pid;

events {
    worker_connections {{ nginx_worker_connections | default(1024) }};
    use epoll;
    multi_accept on;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout {{ nginx_keepalive_timeout | default(65) }};
    types_hash_max_size 2048;
    server_tokens off;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 10240;

    {% if nginx_upstream_servers is defined %}
    upstream backend {
        {% for server in nginx_upstream_servers %}
        server {{ server.host }}:{{ server.port }};
        {% endfor %}
    }
    {% endif %}

    server {
        listen {{ nginx_port | default(80) }};
        server_name {{ nginx_server_name | default('_') }};

        {% if environment == "production" %}
        listen 443 ssl;
        ssl_certificate /etc/ssl/certs/{{ nginx_server_name }}.crt;
        ssl_certificate_key /etc/ssl/private/{{ nginx_server_name }}.key;
        {% endif %}

        location / {
            {% if nginx_upstream_servers is defined %}
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            {% else %}
            root {{ nginx_root | default('/var/www/html') }};
            index index.html;
            {% endif %}
        }
    }
}
```

**Sử dụng template module:**

```yaml
- name: Deploy nginx configuration
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
    validate: nginx -t -c %s    # Validate trước khi deploy
  notify: reload nginx
```

**Filters hữu ích nhất:**

| Filter | Ví dụ | Kết quả |
|--------|-------|---------|
| `default` | `{{ port \| default(80) }}` | 80 nếu port undefined |
| `upper/lower` | `{{ env \| upper }}` | "PRODUCTION" |
| `int/float` | `{{ "42" \| int }}` | 42 |
| `bool` | `{{ "true" \| bool }}` | True |
| `join` | `{{ list \| join(',') }}` | "a,b,c" |
| `length` | `{{ list \| length }}` | 3 |
| `first/last` | `{{ list \| first }}` | first element |
| `min/max` | `{{ nums \| max }}` | largest number |
| `unique` | `{{ list \| unique }}` | deduplicated list |
| `sort` | `{{ list \| sort }}` | sorted list |
| `to_yaml` | `{{ dict \| to_yaml }}` | YAML string |
| `to_json` | `{{ dict \| to_json }}` | JSON string |

</div>

### 4.2 Tags Strategy

Tags cho phép chạy subset của playbook:

```yaml
---
- hosts: webservers
  tasks:
    - name: Install packages
      apt:
        name: "{{ item }}"
      loop: [nginx, curl]
      tags:
        - install
        - packages

    - name: Deploy config
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
      tags:
        - config
        - nginx

    - name: Start services
      service:
        name: nginx
        state: started
      tags:
        - services
        - nginx
```

**Chạy với tags:**

```bash
# Chỉ chạy tasks với tag "config"
ansible-playbook site.yml --tags config

# Chạy nhiều tags
ansible-playbook site.yml --tags "config,services"

# Bỏ qua tags
ansible-playbook site.yml --skip-tags install

# List tất cả tags
ansible-playbook site.yml --list-tags
```

**Special tags:**

```yaml
tags: always    # Always runs, even khi --tags chỉ định tag khác
tags: never     # Never runs trừ khi explicitly specified
```

**Strategy thực tế:**

```
install     → First-time setup
config      → Configuration changes
deploy      → Application deployment
services    → Service management
debug       → Debug tasks (dùng với tag: never)
```

### 4.3 Check Mode và Diff Mode

**Check mode (dry-run):**

```bash
# Simulate without making changes
ansible-playbook site.yml --check
```

```yaml
# Task chỉ chạy khi KHÔNG ở check mode
- name: Restart service
  service:
    name: nginx
    state: restarted
  when: not ansible_check_mode
```

**Diff mode - hiện thị thay đổi:**

```bash
# Show what would change in files
ansible-playbook site.yml --diff

# Combine check + diff (most useful)
ansible-playbook site.yml --check --diff
```

**Output của `--check --diff`:**

```
TASK [Deploy nginx config] ****
--- before: /etc/nginx/nginx.conf
+++ after: /tmp/nginx.conf.j2
@@ -1,5 +1,5 @@
 user www-data;
-worker_processes 2;
+worker_processes 4;
 pid /run/nginx.pid;

changed: [web01]
```

**Đây là cách review changes trước khi apply vào production - CI/CD pipeline thường dùng `--check --diff` trước.**

### 4.4 Variable Precedence Pitfalls

**Pitfall 1: role/vars overrides group_vars**

```yaml
# roles/nginx/vars/main.yml
nginx_port: 80         # Precedence 9

# group_vars/production.yml
nginx_port: 443        # Precedence 2
```

→ Role vars (9) > group_vars (2) → Port sẽ là 80 dù bạn muốn 443.

**Fix:** Dùng `role/defaults/` thay vì `role/vars/` cho values muốn được override.

**Pitfall 2: `-e` override không thể bị override**

```bash
ansible-playbook site.yml -e "environment=production"
# Dù trong host_vars hay bất kỳ đâu set environment=staging
# Extra vars luôn win
```

→ Dùng `-e` cẩn thận trong CI/CD.

**Pitfall 3: Magic variables không thể override**

```yaml
# KHÔNG THỂ override
inventory_hostname    # Always the ansible inventory hostname
groups               # Always the group structure
hostvars             # Always host variables dict
```

### 4.5 Facts vs Variables - Khi nào dùng cái nào?

| Tiêu chí | Facts | Variables |
|----------|-------|-----------|
| Nguồn | Auto-gathered từ system | Defined bởi bạn |
| Scope | Per-host | Configurable |
| Thay đổi | Reflects actual state | Static (trừ set_fact) |
| Performance | Costs ~1-3s per host | Free |
| Use case | OS info, IP, hardware | App config, versions |

**Khi nào dùng facts:**
- Branch theo OS: `when: ansible_os_family == "Debian"`
- Set resources dựa vào hardware: `worker_processes: {{ ansible_processor_count }}`
- Dynamic config based on IP: `bind_address: {{ ansible_default_ipv4.address }}`

**Khi nào dùng variables:**
- Application config values
- Environment-specific settings
- Credentials (qua vault - Day 15)
- Feature flags

---

## 5. Hands-on Lab - 60 phút

### Lab Overview

Bạn sẽ build một **complete nginx deployment** với:
1. Multi-environment configuration (dev/staging/prod)
2. Jinja2 template config
3. Handler cho restart/reload
4. Facts-based configuration
5. Conditionals cho multi-OS support

### Chuẩn bị (5 phút)

**Directory structure:**

```
day-14-lab/
├── inventory/
│   ├── hosts.ini
│   ├── group_vars/
│   │   ├── all.yml
│   │   ├── development.yml
│   │   └── production.yml
│   └── host_vars/
│       └── web01.yml
├── templates/
│   ├── nginx.conf.j2
│   └── index.html.j2
├── files/
│   └── (static files if needed)
└── deploy-nginx.yml
```

```bash
mkdir -p day-14-lab/{inventory/{group_vars,host_vars},templates,files}
cd day-14-lab
```

### Step 1: Inventory và Variables (10 phút)

**`inventory/hosts.ini`:**

```ini
[development]
localhost ansible_connection=local

[production]
# Thêm production hosts khi có
# web01 ansible_host=192.168.1.10

[webservers:children]
development
production

[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

**`inventory/group_vars/all.yml`:**

```yaml
---
# Shared variables across all environments
app_name: myapp
app_owner: www-data
app_group: www-data

nginx_user: www-data
nginx_keepalive_timeout: 65
nginx_worker_connections: 1024

# Default to closed features
ssl_enabled: false
gzip_enabled: true
```

**`inventory/group_vars/development.yml`:**

```yaml
---
environment: development
nginx_port: 8080
nginx_worker_processes: 1
nginx_server_name: localhost
nginx_root: /var/www/html

# Debug settings
nginx_access_log: /var/log/nginx/access.log
nginx_error_log: /var/log/nginx/error.log debug
```

**`inventory/group_vars/production.yml`:**

```yaml
---
environment: production
nginx_port: 80
nginx_worker_processes: "{{ ansible_processor_count }}"
nginx_server_name: "{{ ansible_fqdn }}"
nginx_root: /var/www/production

# Production settings
ssl_enabled: true
nginx_access_log: /var/log/nginx/access.log combined
nginx_error_log: /var/log/nginx/error.log warn
```

**`inventory/host_vars/web01.yml`:**

```yaml
---
# Host-specific overrides
nginx_port: 8888    # Override production port for this specific host
```

### Step 2: Jinja2 Templates (10 phút)

**`templates/nginx.conf.j2`:**

```jinja2
{# nginx.conf - managed by Ansible, do not edit manually #}
{# Generated on: {{ ansible_date_time.iso8601 }} #}
{# Host: {{ inventory_hostname }} | Environment: {{ environment }} #}

user {{ nginx_user }};
worker_processes {{ nginx_worker_processes | default('auto') }};
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections {{ nginx_worker_connections }};
    use epoll;
    multi_accept on;
}

http {
    ##
    # Basic Settings
    ##
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout {{ nginx_keepalive_timeout }};
    types_hash_max_size 2048;
    server_tokens off;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    ##
    # Logging Settings
    ##
    access_log {{ nginx_access_log }};
    error_log {{ nginx_error_log }};

    ##
    # Gzip Settings
    ##
    {% if gzip_enabled %}
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json
               application/javascript application/xml+rss
               application/atom+xml image/svg+xml;
    {% else %}
    gzip off;
    {% endif %}

    ##
    # Virtual Host Configs
    ##
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;

    server {
        listen {{ nginx_port }} default_server;
        listen [::]:{{ nginx_port }} default_server;

        server_name {{ nginx_server_name }};
        root {{ nginx_root }};
        index index.html index.htm;

        {% if ssl_enabled %}
        listen 443 ssl;
        ssl_certificate /etc/ssl/certs/{{ app_name }}.crt;
        ssl_certificate_key /etc/ssl/private/{{ app_name }}.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers on;
        {% endif %}

        location / {
            try_files $uri $uri/ =404;
        }

        location /health {
            access_log off;
            return 200 'OK';
            add_header Content-Type text/plain;
        }

        # Environment-specific settings
        {% if environment == "development" %}
        location /stub_status {
            stub_status;
            allow 127.0.0.1;
            deny all;
        }
        {% endif %}
    }
}
```

**`templates/index.html.j2`:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ app_name | upper }} - {{ environment | capitalize }}</title>
    <style>
        body { font-family: monospace; padding: 2rem; background: #1a1a1a; color: #00ff00; }
        h1 { color: #00ffaa; }
        .info { background: #2a2a2a; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    </style>
</head>
<body>
    <h1>{{ app_name | upper }}</h1>
    <div class="info">
        <p><strong>Environment:</strong> {{ environment }}</p>
        <p><strong>Hostname:</strong> {{ ansible_hostname }}</p>
        <p><strong>OS:</strong> {{ ansible_distribution }} {{ ansible_distribution_version }}</p>
        <p><strong>CPU:</strong> {{ ansible_processor_count }} cores</p>
        <p><strong>RAM:</strong> {{ ansible_memtotal_mb }}MB</p>
        <p><strong>IP:</strong> {{ ansible_default_ipv4.address }}</p>
        <p><strong>Deployed:</strong> {{ ansible_date_time.iso8601 }}</p>
    </div>
    {% if environment == "development" %}
    <div class="info" style="border: 1px solid #ff6600;">
        <p>&#9888; Development Environment - Not for production use</p>
    </div>
    {% endif %}
</body>
</html>
```

### Step 3: Main Playbook (15 phút)

**`deploy-nginx.yml`:**

```yaml
---
- name: Deploy Nginx Web Server
  hosts: webservers
  become: true
  gather_facts: true

  pre_tasks:
    - name: Validate required variables
      assert:
        that:
          - environment is defined
          - nginx_port is defined
          - nginx_root is defined
        fail_msg: "Required variables missing. Check group_vars configuration."

    - name: Display deployment info
      debug:
        msg: |
          ==========================================
          Deploying to: {{ inventory_hostname }}
          Environment: {{ environment }}
          OS: {{ ansible_distribution }} {{ ansible_distribution_version }}
          CPU cores: {{ ansible_processor_count }}
          RAM: {{ ansible_memtotal_mb }}MB
          ==========================================

  tasks:
    # ─── Package Installation ─────────────────────
    - name: Update apt cache
      apt:
        update_cache: true
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"
      tags: [install, packages]

    - name: Install nginx (Debian/Ubuntu)
      apt:
        name: nginx
        state: present
      when: ansible_os_family == "Debian"
      tags: [install, packages]

    - name: Install nginx (RedHat/CentOS)
      yum:
        name: nginx
        state: present
      when: ansible_os_family == "RedHat"
      tags: [install, packages]

    # ─── Directory Setup ──────────────────────────
    - name: Create web root directory
      file:
        path: "{{ nginx_root }}"
        state: directory
        owner: "{{ app_owner }}"
        group: "{{ app_group }}"
        mode: '0755'
      tags: [config]

    - name: Create log directory
      file:
        path: /var/log/nginx
        state: directory
        owner: root
        group: adm
        mode: '0755'
      tags: [config]

    # ─── Configuration Deployment ─────────────────
    - name: Deploy nginx main configuration
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: '0644'
        validate: nginx -t -c %s
        backup: true
      notify:
        - reload nginx
        - verify nginx running
      tags: [config, nginx]

    - name: Deploy index page
      template:
        src: index.html.j2
        dest: "{{ nginx_root }}/index.html"
        owner: "{{ app_owner }}"
        group: "{{ app_group }}"
        mode: '0644'
      tags: [config, deploy]

    # ─── Service Management ───────────────────────
    - name: Ensure nginx is started and enabled
      service:
        name: nginx
        state: started
        enabled: true
      tags: [services]

    # ─── Verification ─────────────────────────────
    - name: Wait for nginx to be ready
      wait_for:
        port: "{{ nginx_port }}"
        host: "{{ ansible_default_ipv4.address }}"
        delay: 2
        timeout: 30
      tags: [verify]

    - name: Verify nginx responds to health check
      uri:
        url: "http://{{ ansible_default_ipv4.address }}:{{ nginx_port }}/health"
        method: GET
        status_code: 200
        timeout: 10
      register: health_check
      tags: [verify]

    - name: Display health check result
      debug:
        msg: "Health check: {{ health_check.status }} - Nginx is running on port {{ nginx_port }}"
      tags: [verify]

  handlers:
    - name: reload nginx
      service:
        name: nginx
        state: reloaded
      listen: reload nginx

    - name: restart nginx
      service:
        name: nginx
        state: restarted

    - name: verify nginx running
      command: nginx -t
      changed_when: false

  post_tasks:
    - name: Deployment summary
      debug:
        msg: |
          ==========================================
          Deployment Complete!
          URL: http://{{ ansible_default_ipv4.address }}:{{ nginx_port }}
          Health: http://{{ ansible_default_ipv4.address }}:{{ nginx_port }}/health
          Environment: {{ environment }}
          Config: /etc/nginx/nginx.conf
          Logs: /var/log/nginx/
          ==========================================
```

### Step 4: Chạy và Kiểm tra (15 phút)

**Syntax check trước:**

```bash
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini --syntax-check
```

**Check mode (dry-run):**

```bash
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini --check --diff
```

**Expected output của `--check --diff`:**

```
PLAY [Deploy Nginx Web Server] ****

TASK [Gathering Facts] ****
ok: [localhost]

TASK [Validate required variables] ****
ok: [localhost]

TASK [Display deployment info] ****
ok: [localhost] => {
    "msg": "==========================================\nDeploying to: localhost\nEnvironment: development\nOS: Ubuntu 22.04\nCPU cores: 2\nRAM: 4096MB\n==========================================\n"
}

TASK [Update apt cache] ****
ok: [localhost]

TASK [Install nginx (Debian/Ubuntu)] ****
ok: [localhost]

TASK [Deploy nginx main configuration] ****
--- before: /etc/nginx/nginx.conf
+++ after: /root/.ansible/tmp/.../source
@@ -1,4 +1,8 @@
+{# nginx.conf - managed by Ansible #}
 user www-data;
-worker_processes auto;
+worker_processes 1;
...

changed: [localhost]

PLAY RECAP ****
localhost: ok=8 changed=1 unreachable=0 failed=0 skipped=2
```

**Chạy thật:**

```bash
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini -v
```

**Chỉ chạy config tasks:**

```bash
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini --tags config
```

**Chỉ verify:**

```bash
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini --tags verify
```

### Step 5: Test Handler Behavior (5 phút)

```bash
# Chạy lần 1 - config changed, handler triggers
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini

# Chạy lần 2 - không thay đổi, handler KHÔNG trigger
ansible-playbook deploy-nginx.yml -i inventory/hosts.ini

# Output lần 2:
# TASK [Deploy nginx main configuration]
# ok: [localhost]   ← ok, không changed
# ...
# RUNNING HANDLERS ← Không có handler nào chạy
```

### Troubleshooting thường gặp

**Error: `nginx: [emerg] bind() to 0.0.0.0:8080 failed (98: Address already in use)`**

```bash
# Check port
sudo ss -tlnp | grep 8080
# Kill process hoặc change port trong group_vars/development.yml
```

**Error: `template error while templating string: 'ansible_processor_count' is undefined`**

```bash
# Fact chưa được gather. Check
ansible localhost -m setup -a "filter=ansible_processor_count"
# Đảm bảo gather_facts: true trong play
```

**Error: `Handler 'reload nginx' notified but handler not found`**

```bash
# Handler name phải match EXACTLY (case-sensitive)
# Trong task: notify: reload nginx
# Trong handlers: name: reload nginx
```

**Error: `The conditional check 'ansible_os_family == "Debian"' failed`**

```bash
# Gather facts trước
ansible localhost -m setup | grep os_family
# Check spelling: "Debian" không phải "debian"
```

---

## 6. Kiểm tra hiểu bài

**Câu 1:** Bạn có `nginx_port: 80` trong `group_vars/all.yml`, `nginx_port: 443` trong `group_vars/production.yml`, và `nginx_port: 8080` trong `host_vars/web01.yml`. Khi chạy trên host `web01` thuộc group `production`, `nginx_port` sẽ có giá trị là bao nhiêu? Giải thích tại sao.

**Câu 2:** Viết một task kiểm tra nếu RAM của host > 4096MB thì set `nginx_worker_connections: 2048`, ngược lại set `nginx_worker_connections: 512`.

```yaml
# Gợi ý: dùng set_fact + when
- name: Set worker connections based on RAM
  set_fact:
    # Điền vào đây
```

**Câu 3:** Handler chạy bao nhiêu lần nếu 5 tasks cùng `notify: restart nginx`? Khi nào handler KHÔNG chạy dù có notify?

**Câu 4:** Điền vào chỗ trống trong Jinja2 template để hiển thị tất cả servers trong list `upstream_servers`:

```jinja2
upstream backend {
    _______ server in upstream_servers _______
    server {{ _______ }}:{{ _______ }};
    _______ endfor _______
}
```

**Câu 5:** Lệnh nào để chạy playbook dưới dạng dry-run VÀ hiện thị sự thay đổi trong files?

---

## 7. Tóm tắt cuối ngày

### 3 điểm quan trọng nhất

1. **Variable precedence là linear:** `extra_vars > task_vars > role/vars > group_vars > role/defaults`. Dùng `role/defaults` cho values muốn override được, `role/vars` cho values muốn lock.

2. **Handler = idempotent service restart:** Handler chỉ chạy khi có CHANGED task notify nó. Đây là cơ chế cốt lõi để tránh restart service không cần thiết trong production.

3. **Jinja2 template + facts = adaptive config:** Kết hợp facts (số CPU, OS type, IP) với Jinja2 để tạo config file phù hợp từng host mà không cần hardcode.

### Output đã tạo

- `deploy-nginx.yml` - Production-ready nginx deployment playbook
- `templates/nginx.conf.j2` - Adaptive nginx config template
- `templates/index.html.j2` - Dynamic status page template
- `inventory/group_vars/` - Environment-specific variables

### Chuẩn bị cho Day 15

Day 15 sẽ học **Roles, Vault, Dynamic Inventory**. Bạn cần nắm:
- Playbook structure hiện tại của Day 14 (sẽ refactor thành Role)
- Khái niệm về organizing code thành reusable units
- Tại sao cần encrypt secrets thay vì hardcode trong group_vars

---

## 8. Tham khảo thêm

- **Ansible Variable Precedence:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#understanding-variable-precedence
- **Ansible Facts:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_vars_facts.html
- **Handlers:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html
- **Loops:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_loops.html
- **Jinja2 Docs:** https://jinja.palletsprojects.com/en/3.1.x/templates/
- **Ansible Filters:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_filters.html
- **Check Mode:** https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html
