# Day 30: Exercises — Ansible for Configuration Management

## Exercise 1: Easy — Playbook Basics trên localhost

### Context

Bạn cần viết Ansible playbook đầu tiên để tự động hóa setup development environment trên máy local.

### Yêu cầu

1. Viết playbook `setup-dev.yml` thực hiện trên localhost:
   - Tạo directory structure: `/tmp/dev-env/{bin,config,logs,data}`
   - Tạo file `/tmp/dev-env/config/settings.json` từ template với nội dung:
     ```json
     { "app": "dev-tools", "version": "1.0", "debug": true }
     ```
   - Tạo script `/tmp/dev-env/bin/start.sh` có nội dung echo "Starting..."
   - Tạo file `/tmp/dev-env/logs/.gitkeep`

2. Viết cleanup playbook `cleanup.yml` xóa toàn bộ `/tmp/dev-env/`.

3. Chứng minh idempotency:
   - Chạy `setup-dev.yml` lần 1 → ghi lại output (changed count)
   - Chạy `setup-dev.yml` lần 2 → ghi lại output (phải là 0 changed)

### Expected Outcome

```bash
ansible-playbook -i "localhost," -c local setup-dev.yml
# PLAY RECAP: ok=5  changed=5

ansible-playbook -i "localhost," -c local setup-dev.yml
# PLAY RECAP: ok=5  changed=0  ← Idempotent!

ls -la /tmp/dev-env/
# bin/  config/  data/  logs/

ansible-playbook -i "localhost," -c local cleanup.yml
# Cleanup complete
```

### Hint

- Dùng `ansible_connection=local` trong inventory hoặc `-c local` flag.
- Module `file` với `state: directory` cho folders.
- Module `copy` với `content:` cho inline file content.
- Module `template` nếu dùng Jinja2 variables.

### Acceptance Criteria

- [ ] Playbook tạo đúng 4 directories
- [ ] 3 files tạo đúng nội dung
- [ ] Chạy lần 2 → 0 changed (idempotent)
- [ ] Cleanup playbook xóa sạch
- [ ] Không dùng `shell` hoặc `command` modules

### Bonus Challenge

Thêm variable `env_name` (default: "dev") và thay đổi directory path + config content theo environment.

<details>
<summary>Solution</summary>

**setup-dev.yml:**
```yaml
---
- name: Setup development environment
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    base_dir: /tmp/dev-env
    app_name: dev-tools
    app_version: "1.0"
    debug_mode: true

  tasks:
    - name: Create directory structure
      ansible.builtin.file:
        path: "{{ base_dir }}/{{ item }}"
        state: directory
        mode: '0755'
      loop:
        - bin
        - config
        - logs
        - data

    - name: Create settings config
      ansible.builtin.copy:
        content: |
          {
            "app": "{{ app_name }}",
            "version": "{{ app_version }}",
            "debug": {{ debug_mode | lower }}
          }
        dest: "{{ base_dir }}/config/settings.json"
        mode: '0644'

    - name: Create start script
      ansible.builtin.copy:
        content: |
          #!/bin/bash
          echo "Starting {{ app_name }} v{{ app_version }}..."
          echo "Config: {{ base_dir }}/config/settings.json"
        dest: "{{ base_dir }}/bin/start.sh"
        mode: '0755'

    - name: Create gitkeep for logs
      ansible.builtin.copy:
        content: ""
        dest: "{{ base_dir }}/logs/.gitkeep"
        mode: '0644'
        force: false

    - name: Verify setup
      ansible.builtin.command: "ls -la {{ base_dir }}"
      register: verify
      changed_when: false

    - name: Show result
      ansible.builtin.debug:
        msg: "{{ verify.stdout_lines }}"
```

**cleanup.yml:**
```yaml
---
- name: Cleanup development environment
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Remove dev environment
      ansible.builtin.file:
        path: /tmp/dev-env
        state: absent
```

**Run:**
```bash
ansible-playbook -i "localhost," -c local setup-dev.yml
ansible-playbook -i "localhost," -c local setup-dev.yml   # Should show changed=0
ansible-playbook -i "localhost," -c local cleanup.yml
```

</details>

---

## Exercise 2: Medium — Multi-role Playbook với Variables

### Context

Bạn cần tạo Ansible project cấu hình một web application stack trên localhost, sử dụng roles và variable overrides cho multiple environments.

### Yêu cầu

1. Tạo 2 Ansible roles:
   - `webserver`: tạo NGINX config files, HTML pages, health check script
   - `monitoring`: tạo monitoring config, log rotation config, metrics script

2. Tạo group variables cho 2 environments:
   - `dev`: debug=true, port=8080, log_level=debug, replicas=1
   - `prod`: debug=false, port=80, log_level=warn, replicas=3

3. Playbook `site.yml` áp dụng cả 2 roles.

4. Sử dụng:
   - Jinja2 templates (ít nhất 2)
   - Handlers (ít nhất 1)
   - Tags cho selective execution
   - `--check` mode hoạt động đúng

5. Base directory: `/tmp/ansible-stack/&#123;&#123; env_name &#125;&#125;/`

### Expected Outcome

```bash
# Deploy dev
ansible-playbook -i inventory/localhost.ini site.yml -e "env_name=dev"
ls /tmp/ansible-stack/dev/
# nginx/  monitoring/  health-check.sh

# Deploy prod  
ansible-playbook -i inventory/localhost.ini site.yml -e "env_name=prod"
ls /tmp/ansible-stack/prod/
# nginx/  monitoring/  health-check.sh

# Run only webserver role
ansible-playbook -i inventory/localhost.ini site.yml -e "env_name=dev" --tags webserver

# Dry run
ansible-playbook -i inventory/localhost.ini site.yml -e "env_name=dev" --check --diff
```

### Hint

- Role directory structure: `roles/<name>/{tasks,handlers,templates,defaults}/main.yml`.
- Group vars: `group_vars/all.yml` hoặc inline vars.
- Tags: `tags: [webserver]` trên tasks hoặc role include.

### Acceptance Criteria

- [ ] 2 roles hoạt động độc lập
- [ ] Templates render đúng theo environment
- [ ] Handler triggered khi config thay đổi
- [ ] Tags cho phép chạy selective
- [ ] `--check` mode không thay đổi gì
- [ ] Idempotent (chạy 2 lần, 0 changed lần 2)

### Bonus Challenge

Thêm role `security` cài đặt: firewall rules file, SSH config, ban list. Encrypt sensitive vars bằng `ansible-vault`.

<details>
<summary>Solution</summary>

**Project structure:**
```
ansible-stack/
├── site.yml
├── inventory/
│   └── localhost.ini
├── group_vars/
│   └── all.yml
└── roles/
    ├── webserver/
    │   ├── tasks/main.yml
    │   ├── handlers/main.yml
    │   ├── templates/
    │   │   └── nginx.conf.j2
    │   └── defaults/main.yml
    └── monitoring/
        ├── tasks/main.yml
        ├── templates/
        │   └── monitoring.conf.j2
        └── defaults/main.yml
```

**site.yml:**
```yaml
---
- name: Configure application stack
  hosts: localhost
  connection: local
  gather_facts: true

  vars:
    env_name: "dev"
    base_dir: "/tmp/ansible-stack/{{ env_name }}"

  vars_files:
    - "group_vars/all.yml"

  pre_tasks:
    - name: Set environment-specific variables
      ansible.builtin.set_fact:
        app_config: "{{ environments[env_name] }}"

  roles:
    - role: webserver
      tags: [webserver]
    - role: monitoring
      tags: [monitoring]
```

**group_vars/all.yml:**
```yaml
environments:
  dev:
    debug: true
    port: 8080
    log_level: debug
    replicas: 1
  prod:
    debug: false
    port: 80
    log_level: warn
    replicas: 3
```

**roles/webserver/defaults/main.yml:**
```yaml
nginx_worker_processes: auto
```

**roles/webserver/tasks/main.yml:**
```yaml
---
- name: Create webserver directories
  ansible.builtin.file:
    path: "{{ base_dir }}/nginx/{{ item }}"
    state: directory
  loop: [conf.d, html, logs]

- name: Generate NGINX config
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: "{{ base_dir }}/nginx/conf.d/default.conf"
  notify: config changed

- name: Create index page
  ansible.builtin.copy:
    content: |
      <h1>{{ env_name }} environment</h1>
      <p>Port: {{ app_config.port }}</p>
      <p>Debug: {{ app_config.debug }}</p>
    dest: "{{ base_dir }}/nginx/html/index.html"

- name: Create health check
  ansible.builtin.copy:
    content: |
      #!/bin/bash
      echo "Environment: {{ env_name }}"
      echo "Port: {{ app_config.port }}"
      [ -f "{{ base_dir }}/nginx/conf.d/default.conf" ] && echo "HEALTHY" || echo "UNHEALTHY"
    dest: "{{ base_dir }}/health-check.sh"
    mode: '0755'
```

**roles/webserver/handlers/main.yml:**
```yaml
- name: config changed
  ansible.builtin.debug:
    msg: "NGINX config changed — would reload in production"
```

**roles/webserver/templates/nginx.conf.j2:**
```
server {
    listen {{ app_config.port }};
    
    {% if app_config.debug %}
    error_log {{ base_dir }}/nginx/logs/error.log debug;
    access_log {{ base_dir }}/nginx/logs/access.log;
    {% else %}
    error_log {{ base_dir }}/nginx/logs/error.log warn;
    access_log off;
    {% endif %}
    
    location / {
        root {{ base_dir }}/nginx/html;
    }
}
```

**roles/monitoring/tasks/main.yml:**
```yaml
---
- name: Create monitoring directories
  ansible.builtin.file:
    path: "{{ base_dir }}/monitoring/{{ item }}"
    state: directory
  loop: [config, scripts]

- name: Generate monitoring config
  ansible.builtin.template:
    src: monitoring.conf.j2
    dest: "{{ base_dir }}/monitoring/config/monitoring.conf"

- name: Create metrics collection script
  ansible.builtin.copy:
    content: |
      #!/bin/bash
      echo "timestamp=$(date +%s)"
      echo "environment={{ env_name }}"
      echo "log_level={{ app_config.log_level }}"
    dest: "{{ base_dir }}/monitoring/scripts/collect-metrics.sh"
    mode: '0755'
```

</details>

---

## Exercise 3: Hard — Production Ansible Project Design

### Context

Bạn là DevOps engineer tại một company đang chuyển từ manual server management sang Ansible. Hệ thống gồm:

- 10 web servers (NGINX + Node.js)
- 3 database servers (PostgreSQL)
- 2 monitoring servers (Prometheus + Grafana)
- 3 environments: dev (3 servers), staging (5 servers), prod (15 servers)

### Yêu cầu

1. **Thiết kế Ansible project structure:**
   - Inventory cho 3 environments
   - Roles cho: common, webserver, database, monitoring
   - Group variables per environment
   - Vault cho secrets

2. **Viết role `common`** (chạy trên localhost) gồm:
   - Tạo standard directories
   - Generate SSH config
   - Setup log rotation
   - Create backup script
   - Security baseline (sysctl params file, SSH hardening config)

3. **Viết deployment playbook** với:
   - Pre-tasks: health check trước deploy
   - Roles applied theo host groups
   - Post-tasks: verify deployment
   - Serial execution strategy (rolling deploy)
   - Error handling (block/rescue/always)

4. **Viết CI/CD integration:**
   - `ansible-lint` configuration
   - `--check` mode cho PR validation
   - Deploy script cho CD pipeline

### Expected Outcome

```
ansible-project/
├── ansible.cfg
├── site.yml
├── deploy.yml
├── inventory/
│   ├── dev/hosts.ini
│   ├── staging/hosts.ini
│   └── prod/hosts.ini
├── group_vars/
│   ├── all/
│   │   ├── vars.yml
│   │   └── vault.yml (encrypted)
│   ├── webservers.yml
│   ├── databases.yml
│   └── monitoring.yml
├── roles/
│   ├── common/
│   ├── webserver/
│   ├── database/
│   └── monitoring/
├── .ansible-lint
└── scripts/
    └── deploy.sh
```

### Acceptance Criteria

- [ ] Project structure follows Ansible best practices
- [ ] `common` role functional trên localhost
- [ ] Playbook sử dụng serial, error handling, tags
- [ ] Vault encrypted secrets
- [ ] CI/CD integration scripts
- [ ] README with usage instructions
- [ ] Idempotent — chạy 2 lần, 0 changed

### Bonus Challenge

Thêm `molecule` test configuration cho role `common` — automated role testing.

<details>
<summary>Solution</summary>

**ansible.cfg:**
```ini
[defaults]
inventory = inventory/dev/hosts.ini
roles_path = roles
retry_files_enabled = false
stdout_callback = yaml
callbacks_enabled = profile_tasks
forks = 20

[ssh_connection]
pipelining = True

[privilege_escalation]
become = false
```

**deploy.yml (với rolling deploy + error handling):**
```yaml
---
- name: Pre-deploy checks
  hosts: localhost
  connection: local
  gather_facts: false
  tags: [pre-check]
  tasks:
    - name: Verify inventory is loaded
      ansible.builtin.debug:
        msg: "Deploying to {{ groups.keys() | list }}"

- name: Deploy common baseline
  hosts: localhost
  connection: local
  tags: [common]
  roles:
    - common

- name: Deploy web servers (rolling)
  hosts: localhost
  connection: local
  serial: 2  # 2 servers at a time
  tags: [webserver]
  
  pre_tasks:
    - name: Pre-deploy health check
      ansible.builtin.command: "{{ app_base_dir | default('/tmp/ansible-prod') }}/health-check.sh"
      register: pre_health
      changed_when: false
      ignore_errors: true

  tasks:
    - block:
        - name: Apply webserver role
          include_role:
            name: webserver
      rescue:
        - name: Deployment failed - notify
          ansible.builtin.debug:
            msg: "DEPLOY FAILED on {{ inventory_hostname }}! Rolling back..."
        - name: Fail play
          fail:
            msg: "Deployment failed, stopped rolling deploy"
      always:
        - name: Post-deploy health check
          ansible.builtin.command: "{{ app_base_dir | default('/tmp/ansible-prod') }}/health-check.sh"
          register: post_health
          changed_when: false
          ignore_errors: true

- name: Post-deploy verification
  hosts: localhost
  connection: local
  gather_facts: false
  tags: [verify]
  tasks:
    - name: Final verification
      ansible.builtin.debug:
        msg: "Deployment complete!"
```

**scripts/deploy.sh:**
```bash
#!/bin/bash
set -euo pipefail

ENV=${1:?Usage: $0 <dev|staging|prod>}
ACTION=${2:-deploy}

INVENTORY="inventory/${ENV}/hosts.ini"

case $ACTION in
  check)
    echo "=== Dry run for $ENV ==="
    ansible-playbook -i "$INVENTORY" deploy.yml --check --diff
    ;;
  deploy)
    echo "=== Deploying to $ENV ==="
    ansible-playbook -i "$INVENTORY" deploy.yml
    ;;
  lint)
    echo "=== Linting playbooks ==="
    ansible-lint site.yml deploy.yml
    ;;
  *)
    echo "Usage: $0 <env> [check|deploy|lint]"
    exit 1
    ;;
esac
```

</details>

