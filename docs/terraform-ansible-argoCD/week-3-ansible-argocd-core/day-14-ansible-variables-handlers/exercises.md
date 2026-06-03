# Day 14: Extended Exercises & Challenges

**Variables, Facts, Conditionals, Loops, Handlers, Jinja2**

---

## Hướng dẫn sử dụng

- **Level 1 - Basic:** Nên hoàn thành sau lesson chính (~15 phút)
- **Level 2 - Intermediate:** Mở rộng lab chính (~30 phút)
- **Level 3 - Advanced:** Production-grade challenges (~45-60 phút)
- **Boss Challenge:** Integrate tất cả concepts

---

## Level 1 - Basic Exercises

### Exercise 1.1: Variable Precedence Quiz

Cho cấu hình sau, hãy xác định giá trị cuối cùng của mỗi variable:

```yaml
# roles/webserver/defaults/main.yml
app_port: 3000
debug: false
log_level: "info"

# group_vars/all.yml
app_port: 8080
environment: "development"

# group_vars/production.yml
environment: "production"
log_level: "warn"

# host_vars/web01.yml
app_port: 9090
```

**Câu hỏi:** Khi chạy trên host `web01` thuộc group `production`:

| Variable | Giá trị | Nguồn |
|----------|---------|-------|
| `app_port` | ? | ? |
| `environment` | ? | ? |
| `log_level` | ? | ? |
| `debug` | ? | ? |

**Đáp án (flip để xem):**

```
app_port   = 9090         (host_vars > group_vars > role defaults)
environment = "production" (group_vars/production > group_vars/all)
log_level   = "warn"      (group_vars/production > role defaults)
debug       = false        (chỉ có trong role defaults, không ai override)
```

### Exercise 1.2: Write Conditional Tasks

Viết tasks để install `node_exporter` theo OS:
- Debian/Ubuntu: dùng `apt`
- RedHat/CentOS: dùng `yum`

```yaml
# Điền vào chỗ trống
- name: Install node_exporter (Debian)
  apt:
    name: prometheus-node-exporter
    state: present
  when: _______________

- name: Install node_exporter (RedHat)
  yum:
    name: node_exporter
    state: present
  when: _______________
```

### Exercise 1.3: Loop Rewrite

Refactor task sau để dùng `loop` thay vì `with_items`:

```yaml
# Old style
- name: Create required directories
  file:
    path: "{{ item }}"
    state: directory
    mode: '0755'
  with_items:
    - /opt/myapp
    - /opt/myapp/logs
    - /opt/myapp/config
    - /opt/myapp/tmp
```

### Exercise 1.4: Add Handler

Thêm handler vào playbook sau để service chỉ restart khi config thay đổi:

```yaml
# Hiện tại - luôn restart (sai)
tasks:
  - name: Deploy app config
    template:
      src: app.conf.j2
      dest: /etc/myapp/app.conf

  - name: Restart app
    service:
      name: myapp
      state: restarted

# Viết lại đúng với handler:
tasks:
  - name: Deploy app config
    template:
      src: app.conf.j2
      dest: /etc/myapp/app.conf
    notify: _____________

handlers:
  - name: _____________
    service:
      name: myapp
      state: _____________
```

### Exercise 1.5: Jinja2 Template Basics

Hoàn thiện template `.env.j2` cho một Node.js application:

```jinja2
# .env file - managed by Ansible
# Environment: {{ environment }}

NODE_ENV={{ _____________ }}
PORT={{ _____________ | default(3000) }}
LOG_LEVEL={{ _____________ | upper }}

{% if database_url is defined %}
DATABASE_URL={{ _____________ }}
{% endif %}

{% if environment == "production" %}
DEBUG=false
NODE_OPTIONS=--max-old-space-size=512
{% else %}
DEBUG=true
{% endif %}
```

---

## Level 2 - Intermediate Exercises

### Exercise 2.1: node_exporter Deployment Playbook

Viết playbook hoàn chỉnh deploy **Prometheus node_exporter** với:

**Requirements:**
- Download binary từ GitHub releases (dùng URL có version variable)
- Tạo system user `node_exporter` (no shell, no home)
- Tạo systemd service file từ template
- Handler để restart service khi config thay đổi
- Verify service đang listen trên port 9100
- Tags: `install`, `config`, `services`, `verify`

**Gợi ý structure:**

```yaml
---
- name: Deploy node_exporter
  hosts: all
  become: true
  vars:
    node_exporter_version: "1.7.0"
    node_exporter_port: 9100
    node_exporter_user: node_exporter

  tasks:
    # TODO: Create user
    # TODO: Download binary
    # TODO: Extract and install binary
    # TODO: Deploy systemd service template
    # TODO: Enable and start service
    # TODO: Verify port is open

  handlers:
    # TODO: Restart handler
```

**Template `/templates/node_exporter.service.j2`:**

```jinja2
[Unit]
Description=Prometheus Node Exporter
Documentation=https://prometheus.io/docs/guides/node-exporter/
Wants=network-online.target
After=network-online.target

[Service]
User={{ node_exporter_user }}
Group={{ node_exporter_user }}
Type=simple
ExecStart=/usr/local/bin/node_exporter \
    --web.listen-address=":{{ node_exporter_port }}" \
    --collector.systemd \
    {% if node_exporter_textfile_dir is defined %}
    --collector.textfile.directory={{ node_exporter_textfile_dir }} \
    {% endif %}
    --web.telemetry-path="/metrics"

[Install]
WantedBy=multi-user.target
```

**Đáp án mẫu:**

```yaml
---
- name: Deploy node_exporter
  hosts: all
  become: true
  vars:
    node_exporter_version: "1.7.0"
    node_exporter_port: 9100
    node_exporter_user: node_exporter
    node_exporter_install_dir: /usr/local/bin

  tasks:
    - name: Create node_exporter user
      user:
        name: "{{ node_exporter_user }}"
        system: true
        shell: /bin/false
        create_home: false
        comment: "Prometheus Node Exporter"
      tags: [install]

    - name: Set architecture fact
      set_fact:
        node_exporter_arch: >-
          {{ 'amd64' if ansible_architecture == 'x86_64'
             else 'arm64' if ansible_architecture == 'aarch64'
             else ansible_architecture }}
      tags: [install]

    - name: Download node_exporter
      get_url:
        url: "https://github.com/prometheus/node_exporter/releases/download/v{{ node_exporter_version }}/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}.tar.gz"
        dest: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
        mode: '0644'
      tags: [install]

    - name: Extract node_exporter
      unarchive:
        src: "/tmp/node_exporter-{{ node_exporter_version }}.tar.gz"
        dest: /tmp/
        remote_src: true
      tags: [install]

    - name: Install node_exporter binary
      copy:
        src: "/tmp/node_exporter-{{ node_exporter_version }}.linux-{{ node_exporter_arch }}/node_exporter"
        dest: "{{ node_exporter_install_dir }}/node_exporter"
        owner: root
        group: root
        mode: '0755'
        remote_src: true
      notify: restart node_exporter
      tags: [install]

    - name: Deploy systemd service file
      template:
        src: node_exporter.service.j2
        dest: /etc/systemd/system/node_exporter.service
        owner: root
        group: root
        mode: '0644'
      notify:
        - daemon reload
        - restart node_exporter
      tags: [config]

    - name: Enable and start node_exporter
      service:
        name: node_exporter
        state: started
        enabled: true
      tags: [services]

    - name: Wait for node_exporter port
      wait_for:
        port: "{{ node_exporter_port }}"
        timeout: 30
      tags: [verify]

    - name: Verify metrics endpoint
      uri:
        url: "http://localhost:{{ node_exporter_port }}/metrics"
        status_code: 200
      register: metrics_check
      tags: [verify]

    - name: Show status
      debug:
        msg: "node_exporter v{{ node_exporter_version }} running on :{{ node_exporter_port }}"
      tags: [verify]

  handlers:
    - name: daemon reload
      systemd:
        daemon_reload: true

    - name: restart node_exporter
      service:
        name: node_exporter
        state: restarted
```

### Exercise 2.2: Multi-environment Config Template

Tạo Jinja2 template cho một application config file có:
- Database connection strings khác nhau per environment
- Redis config với optional clustering
- Feature flags từ dictionary variable
- Comments tự động với thông tin deploy

**Setup variables:**

```yaml
# group_vars/all.yml
app_name: myapi
app_version: "2.1.0"

database:
  host: localhost
  port: 5432
  name: "{{ app_name }}_{{ environment }}"
  pool_size: 5

redis:
  host: localhost
  port: 6379
  cluster_enabled: false

feature_flags:
  new_ui: false
  beta_api: false
  maintenance_mode: false

# group_vars/production.yml
database:
  host: db-primary.internal
  port: 5432
  name: myapi_prod
  pool_size: 20

redis:
  host: redis-cluster.internal
  port: 6379
  cluster_enabled: true
  cluster_nodes:
    - host: redis-1.internal
      port: 6379
    - host: redis-2.internal
      port: 6379
    - host: redis-3.internal
      port: 6379

feature_flags:
  new_ui: true
  beta_api: false
  maintenance_mode: false
```

**Viết template `app.config.j2` để output:**

```ini
# Application Configuration
# Generated by Ansible on {{ ansible_date_time.iso8601 }}
# Host: {{ inventory_hostname }}
# Environment: {{ environment }}
# DO NOT EDIT MANUALLY

[app]
name = {{ app_name }}
version = {{ app_version }}
environment = {{ environment }}
debug = {{ (environment != "production") | lower }}

[database]
host = {{ database.host }}
port = {{ database.port }}
name = {{ database.name }}
pool_size = {{ database.pool_size }}
url = postgresql://{{ database.host }}:{{ database.port }}/{{ database.name }}

[redis]
host = {{ redis.host }}
port = {{ redis.port }}
{% if redis.cluster_enabled %}
mode = cluster
nodes = {% for node in redis.cluster_nodes %}{{ node.host }}:{{ node.port }}{% if not loop.last %},{% endif %}{% endfor %}

{% else %}
mode = single
{% endif %}

[features]
{% for flag, enabled in feature_flags.items() %}
{{ flag }} = {{ enabled | lower }}
{% endfor %}
```

### Exercise 2.3: Facts-based Tuning

Viết playbook tự động tune PostgreSQL `postgresql.conf` dựa vào hardware facts:

**Tuning formulas (simplified):**
- `shared_buffers` = 25% of total RAM
- `effective_cache_size` = 75% of total RAM
- `max_connections` = min(200, RAM_MB / 10)
- `work_mem` = RAM_MB / max_connections / 2 (in MB)

```yaml
---
- name: Auto-tune PostgreSQL
  hosts: dbservers
  become: true
  gather_facts: true

  pre_tasks:
    - name: Calculate PostgreSQL tuning parameters
      set_fact:
        pg_shared_buffers_mb: "{{ (ansible_memtotal_mb * 0.25) | int }}"
        pg_effective_cache_size_mb: "{{ (ansible_memtotal_mb * 0.75) | int }}"
        pg_max_connections: "{{ [200, (ansible_memtotal_mb / 10) | int] | min }}"
        # Điền công thức work_mem:
        pg_work_mem_mb: "{{ _______________ }}"

  tasks:
    - name: Deploy postgresql.conf
      template:
        src: postgresql.conf.j2
        dest: /etc/postgresql/14/main/postgresql.conf
        validate: "pg_conftool %s check"
        backup: true
      notify: restart postgresql

  handlers:
    - name: restart postgresql
      service:
        name: postgresql
        state: restarted
```

**Template `postgresql.conf.j2`:**

```jinja2
# PostgreSQL Configuration
# Auto-tuned by Ansible for {{ ansible_hostname }}
# CPU: {{ ansible_processor_count }} cores
# RAM: {{ ansible_memtotal_mb }}MB

#------------------------------------------------------------------------------
# CONNECTIONS AND AUTHENTICATION
#------------------------------------------------------------------------------
max_connections = {{ pg_max_connections }}

#------------------------------------------------------------------------------
# RESOURCE USAGE (except WAL)
#------------------------------------------------------------------------------
shared_buffers = {{ pg_shared_buffers_mb }}MB
work_mem = {{ pg_work_mem_mb }}MB
effective_cache_size = {{ pg_effective_cache_size_mb }}MB

{% if ansible_processor_count >= 4 %}
# Multi-core tuning
max_worker_processes = {{ ansible_processor_count }}
max_parallel_workers = {{ (ansible_processor_count / 2) | int }}
max_parallel_workers_per_gather = {{ (ansible_processor_count / 4) | int | max(1) }}
{% endif %}
```

---

## Level 3 - Advanced Challenges

### Challenge 3.1: Dynamic Inventory Groups in Playbook

Bạn có một playbook cần deploy config khác nhau tùy vào:
- Host thuộc group `primary` hay `replica`
- Environment là `production` hay không
- Host có fact `ansible_memtotal_mb` > 8192

**Viết tasks với conditionals phức tạp:**

```yaml
---
- name: Complex conditional deployment
  hosts: databases
  become: true

  tasks:
    - name: Deploy primary database config
      template:
        src: pg-primary.conf.j2
        dest: /etc/postgresql/14/main/postgresql.conf
      when:
        - inventory_hostname in groups['primary']
        - environment == "production"
      notify: restart postgresql

    - name: Deploy replica config
      template:
        src: pg-replica.conf.j2
        dest: /etc/postgresql/14/main/postgresql.conf
      when:
        - inventory_hostname in groups['replica']
      notify: restart postgresql

    - name: Enable connection pooling (high-memory hosts only)
      service:
        name: pgbouncer
        state: started
        enabled: true
      when:
        - ansible_memtotal_mb > 8192
        - environment == "production"

    - name: Set aggressive maintenance vacuum (production primaries)
      postgresql_conf:
        name: autovacuum_vacuum_scale_factor
        value: "0.05"
      when:
        - inventory_hostname in groups['primary']
        - environment == "production"
        - ansible_memtotal_mb > 16384
```

### Challenge 3.2: Handler Ordering và flush_handlers

Bạn cần deploy một stack với thứ tự dependencies:
1. Deploy config → validate config → reload service → run smoke test

**Vấn đề:** Nếu validation fail, không nên reload service. Viết playbook sử dụng `meta: flush_handlers` đúng cách:

```yaml
---
- name: Safe config deployment
  hosts: webservers
  become: true

  tasks:
    - name: Deploy new config
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf.new
      notify: validate config
      tags: [config]

    - name: Flush to run validation before reload
      meta: flush_handlers
      # Nếu validation fail, play dừng ở đây

    - name: Deploy validated config
      copy:
        src: /etc/nginx/nginx.conf.new
        dest: /etc/nginx/nginx.conf
        remote_src: true
      notify: reload nginx
      tags: [config]

    - name: Flush to reload before smoke test
      meta: flush_handlers

    - name: Smoke test (sau khi reload)
      uri:
        url: "http://localhost/health"
        status_code: 200
      tags: [verify]

  handlers:
    - name: validate config
      command: nginx -t -c /etc/nginx/nginx.conf.new
      changed_when: false

    - name: reload nginx
      service:
        name: nginx
        state: reloaded
```

**Thêm vào:** Viết rollback handler nếu smoke test fail.

### Challenge 3.3: Template với Logic Phức tạp

Tạo Jinja2 template cho **HAProxy** load balancer config với:
- Health checks
- Weighted round-robin dựa trào `server.weight`
- Backend selection dựa vào server tags
- ACL rules cho rate limiting
- Stats page chỉ ở non-production

**Variables:**

```yaml
haproxy_frontends:
  - name: http_front
    port: 80
    backend: web_back
  - name: https_front
    port: 443
    ssl: true
    backend: web_back

haproxy_backends:
  - name: web_back
    balance: roundrobin
    servers:
      - name: web01
        host: 10.0.1.1
        port: 8080
        weight: 5
        check: true
      - name: web02
        host: 10.0.1.2
        port: 8080
        weight: 3
        check: true
      - name: web03
        host: 10.0.1.3
        port: 8080
        weight: 2
        check: true
        backup: true    # Backup server
```

**Viết `haproxy.cfg.j2`:**

```jinja2
# HAProxy Configuration
# Generated by Ansible - {{ ansible_date_time.iso8601 }}

global
    log /dev/log local0
    maxconn 50000
    user haproxy
    group haproxy
    daemon

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5s
    timeout client 30s
    timeout server 30s

{% for frontend in haproxy_frontends %}
frontend {{ frontend.name }}
    bind *:{{ frontend.port }}{% if frontend.ssl | default(false) %} ssl crt /etc/ssl/certs/{{ app_name }}.pem{% endif %}

    default_backend {{ frontend.backend }}

{% endfor %}

{% for backend in haproxy_backends %}
backend {{ backend.name }}
    balance {{ backend.balance | default('roundrobin') }}
    option httpchk GET /health
    http-check expect status 200

{% for server in backend.servers %}
    server {{ server.name }} {{ server.host }}:{{ server.port }} \
        weight {{ server.weight | default(1) }} \
        {% if server.check | default(false) %}check inter 5s rise 2 fall 3{% endif %} \
        {% if server.backup | default(false) %}backup{% endif %}

{% endfor %}

{% endfor %}

{% if environment != "production" %}
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats auth admin:admin
{% endif %}
```

### Challenge 3.4: Custom Facts và Conditional Logic

Viết playbook:
1. Detect ứng dụng đang chạy phiên bản nào (từ binary hoặc file)
2. Lưu version vào custom fact
3. Skip download nếu version đã up-to-date
4. Log deploy history vào file

```yaml
---
- name: Smart application deployment
  hosts: appservers
  become: true
  vars:
    target_version: "3.2.1"
    app_binary: /usr/local/bin/myapp
    deploy_log: /var/log/myapp/deploys.log

  tasks:
    - name: Check current version
      command: "{{ app_binary }} --version"
      register: current_version_raw
      ignore_errors: true
      changed_when: false

    - name: Parse current version
      set_fact:
        current_version: "{{ current_version_raw.stdout | regex_search('([0-9]+\\.[0-9]+\\.[0-9]+)') | default('0.0.0') }}"
      when: current_version_raw.rc == 0

    - name: Set current version for fresh installs
      set_fact:
        current_version: "0.0.0"
      when: current_version_raw.rc != 0

    - name: Show version status
      debug:
        msg: |
          Current: {{ current_version }}
          Target: {{ target_version }}
          Action: {{ 'SKIP (up to date)' if current_version == target_version else 'UPGRADE' }}

    - name: Download new version
      get_url:
        url: "https://releases.myapp.io/v{{ target_version }}/myapp-linux-amd64"
        dest: "{{ app_binary }}.new"
        mode: '0755'
      when: current_version != target_version
      notify: deploy new version

    - name: Log deployment
      lineinfile:
        path: "{{ deploy_log }}"
        line: "{{ ansible_date_time.iso8601 }} | {{ inventory_hostname }} | {{ current_version }} -> {{ target_version }} | {{ ansible_user }}"
        create: true
      when: current_version != target_version

  handlers:
    - name: deploy new version
      block:
        - name: Stop application
          service:
            name: myapp
            state: stopped

        - name: Replace binary
          copy:
            src: "{{ app_binary }}.new"
            dest: "{{ app_binary }}"
            remote_src: true
            mode: '0755'

        - name: Start application
          service:
            name: myapp
            state: started

        - name: Health check after deploy
          uri:
            url: "http://localhost:8080/health"
            status_code: 200
            timeout: 30
          retries: 5
          delay: 5
```

---

## Boss Challenge: Complete Infrastructure Setup

### Mục tiêu

Viết một **complete playbook suite** deploy LAMP-like stack (Nginx + PHP-FPM + MySQL) với:

### Requirements

**Inventory structure:**

```
inventory/
├── hosts.ini
│   ├── [webservers] - web01, web02
│   └── [databases] - db01
├── group_vars/
│   ├── all.yml
│   ├── webservers.yml
│   └── databases.yml
└── host_vars/
    └── web01.yml (primary web - different config)
```

**Playbook requirements:**

1. **Common tasks** (chạy trên tất cả hosts):
   - Install base packages: `curl`, `vim`, `htop`, `fail2ban`
   - Configure timezone từ variable `server_timezone`
   - Set hostname từ `inventory_hostname`
   - Tag: `common`

2. **Web server tasks** (chỉ hosts trong `webservers` group):
   - Install nginx + php8.1-fpm
   - Deploy nginx vhost config từ template (port từ variable)
   - Deploy PHP-FPM pool config từ template
   - Handlers: reload nginx, restart php-fpm
   - Verify: curl localhost returns 200
   - Tag: `web`

3. **Database tasks** (chỉ hosts trong `databases` group):
   - Install mysql-server
   - Configure mysql từ template dựa vào RAM
   - Create database và user từ `db_config` variable
   - Handler: restart mysql
   - Tag: `db`

4. **Deployment tasks** (chạy sau khi infra ready):
   - Deploy app index.php từ template
   - Set permissions
   - Run smoke test
   - Tag: `deploy`

**Facts phải được dùng:**
- `ansible_processor_count` → nginx worker_processes, php-fpm pm.max_children
- `ansible_memtotal_mb` → mysql innodb_buffer_pool_size
- `ansible_os_family` → conditional install commands
- `ansible_default_ipv4.address` → bind addresses

**Variables:**

```yaml
# group_vars/all.yml
server_timezone: Asia/Ho_Chi_Minh
admin_email: ops@company.com
environment: development

# group_vars/webservers.yml
nginx_port: 80
php_version: "8.1"

php_fpm_config:
  pm: dynamic
  pm_max_children: "{{ ansible_processor_count * 4 }}"
  pm_start_servers: "{{ ansible_processor_count }}"
  pm_min_spare_servers: 2
  pm_max_spare_servers: "{{ ansible_processor_count * 2 }}"

# group_vars/databases.yml
mysql_bind_address: "{{ ansible_default_ipv4.address }}"
mysql_innodb_buffer_pool_size: "{{ (ansible_memtotal_mb * 0.7) | int }}M"
mysql_max_connections: "{{ [500, (ansible_memtotal_mb / 4) | int] | min }}"

db_config:
  name: myapp
  user: app_user
  # Password sẽ học Vault ở Day 15
  password: "changeme_use_vault"
```

**Checklist khi hoàn thành:**

- [ ] Playbook chạy idempotent (chạy 2 lần - lần 2 không có changes ngoài ok)
- [ ] `--check --diff` chạy không error
- [ ] `--tags web` chỉ chạy web tasks
- [ ] Handler chỉ trigger khi config thực sự thay đổi
- [ ] Tất cả templates dùng facts
- [ ] `assert` validate required variables ở `pre_tasks`

---

## Đáp án tham khảo - Exercise 1

### 1.2

```yaml
when: ansible_os_family == "Debian"
when: ansible_os_family == "RedHat"
```

### 1.3

```yaml
- name: Create required directories
  file:
    path: "{{ item }}"
    state: directory
    mode: '0755'
  loop:
    - /opt/myapp
    - /opt/myapp/logs
    - /opt/myapp/config
    - /opt/myapp/tmp
```

### 1.4

```yaml
tasks:
  - name: Deploy app config
    template:
      src: app.conf.j2
      dest: /etc/myapp/app.conf
    notify: restart myapp

handlers:
  - name: restart myapp
    service:
      name: myapp
      state: restarted
```

### 1.5

```jinja2
NODE_ENV={{ environment }}
PORT={{ app_port | default(3000) }}
LOG_LEVEL={{ log_level | upper }}

{% if database_url is defined %}
DATABASE_URL={{ database_url }}
{% endif %}
```

---

## Câu hỏi Review Cuối

**Q: Khi nào dùng `state: reloaded` vs `state: restarted` cho nginx?**

```
reload  = SIGHU  → Graceful, không drop connections đang có
restart = restart → Drop tất cả connections, dùng khi thay đổi server block binding
```

→ Dùng `reload` cho config changes, `restart` khi thay đổi listen ports/SSL certs.

**Q: Tại sao `role/vars/main.yml` nguy hiểm hơn `role/defaults/main.yml`?**

```
vars/main.yml     = Precedence 11 → Overrides group_vars (2-4)
defaults/main.yml = Precedence 1  → Bị override bởi group_vars

Nếu đặt nginx_port vào vars/main.yml, group_vars/production.yml
không thể override nó → Breaking change.
```

**Q: Handler có chạy nếu play fail ở task thứ 3 (sau 2 tasks đã changed)?**

```
Không. Nếu play fail, handlers KHÔNG chạy (default).
Dùng --force-handlers flag để force run handlers dù play fail.
ansible-playbook site.yml --force-handlers
```

**Q: Làm sao biết facts available cho host mà không connect?**

```bash
# Dùng cached facts (nếu đã enable fact_caching)
ansible web01 -m setup --cached

# Hoặc từ fact file saved
cat /tmp/facts/web01
```
