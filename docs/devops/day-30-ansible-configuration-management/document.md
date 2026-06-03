# Day 30: Document — Ansible Configuration Management Reference

## Ansible Command Cheat Sheet

### Core Commands

| Command | Mục đích | Example |
|---------|----------|---------|
| `ansible-playbook` | Chạy playbook | `ansible-playbook -i inventory/production/hosts.ini site.yml` |
| `ansible` | Ad-hoc command | `ansible -i inventory/production/hosts.ini all -m ansible.builtin.ping` |
| `ansible-inventory` | Show inventory | `ansible-inventory --list` |
| `ansible-vault` | Manage secrets | `ansible-vault encrypt vars.yml` |
| `ansible-galaxy` | Manage roles/collections | `ansible-galaxy install geerlingguy.docker` |
| `ansible-lint` | Lint playbooks | `ansible-lint site.yml` |
| `ansible-doc` | Module documentation | `ansible-doc ansible.builtin.apt` |
| `ansible-config` | Show config | `ansible-config dump` |

### Playbook Execution Flags

```bash
# Dry run (check mode) — preview changes
ansible-playbook -i inventory/production/hosts.ini site.yml --check

# Show differences
ansible-playbook -i inventory/production/hosts.ini site.yml --diff

# Check + diff (best for PR review)
ansible-playbook -i inventory/production/hosts.ini site.yml --check --diff

# Limit to specific hosts
ansible-playbook -i inventory/production/hosts.ini site.yml --limit web-1

# Run specific tags only
ansible-playbook -i inventory/production/hosts.ini site.yml --tags "nginx,ssl"

# Skip specific tags
ansible-playbook -i inventory/production/hosts.ini site.yml --skip-tags "monitoring"

# Extra variables (highest priority)
ansible-playbook -i inventory/production/hosts.ini site.yml -e "env=prod version=2.0"

# Step through tasks one by one
ansible-playbook -i inventory/production/hosts.ini site.yml --step

# Start at specific task
ansible-playbook -i inventory/production/hosts.ini site.yml --start-at-task "Install nginx"

# Verbose output (-v, -vv, -vvv, -vvvv)
ansible-playbook -i inventory/production/hosts.ini site.yml -vvv

# List tasks without executing
ansible-playbook -i inventory/production/hosts.ini site.yml --list-tasks

# List hosts without executing
ansible-playbook -i inventory/production/hosts.ini site.yml --list-hosts

# Syntax check only
ansible-playbook -i inventory/production/hosts.ini site.yml --syntax-check

# Vault password
ansible-playbook -i inventory/production/hosts.ini site.yml --ask-vault-pass
ansible-playbook -i inventory/production/hosts.ini site.yml --vault-password-file ~/.vault_pass
```

### Ad-hoc Commands

```bash
# Ping all hosts
ansible -i inventory/production/hosts.ini all -m ansible.builtin.ping

# Run command on specific group
ansible -i inventory/production/hosts.ini webservers -m ansible.builtin.command -a "uptime"

# Install package
ansible -i inventory/production/hosts.ini webservers -m ansible.builtin.apt -a "name=nginx state=present" --become

# Copy file
ansible -i inventory/production/hosts.ini all -m ansible.builtin.copy -a "src=/local/file dest=/remote/file"

# Gather facts
ansible -i inventory/production/hosts.ini web-1 -m ansible.builtin.setup

# Gather specific facts
ansible -i inventory/production/hosts.ini web-1 -m ansible.builtin.setup -a "filter=ansible_os_family"
```

---

## Module Quick Reference

### Package Management

```yaml
# APT (Debian/Ubuntu)
- name: Install packages
  ansible.builtin.apt:
    name: ['nginx', 'curl', 'jq']
    state: present
    update_cache: true
    cache_valid_time: 3600

# YUM (RHEL/CentOS)
- name: Install packages
  ansible.builtin.yum:
    name: ['httpd', 'curl']
    state: present

# Package (auto-detect)
- name: Install package (generic)
  ansible.builtin.package:
    name: git
    state: present

# PIP
- name: Install Python package
  ansible.builtin.pip:
    name: docker
    state: present
```

### File Management

```yaml
# Create directory
- name: Create directory
  ansible.builtin.file:
    path: /opt/app
    state: directory
    owner: appuser
    group: appgroup
    mode: '0755'

# Create file
- name: Create empty file
  ansible.builtin.file:
    path: /opt/app/config.yml
    state: touch
    mode: '0644'

# Copy file from control node
- name: Copy file
  ansible.builtin.copy:
    src: files/app.conf
    dest: /etc/app/config.conf
    owner: root
    mode: '0644'
    backup: true

# Copy inline content
- name: Write content
  ansible.builtin.copy:
    content: |
      key=value
      debug=false
    dest: /etc/app/settings.conf

# Template (Jinja2)
- name: Render template
  ansible.builtin.template:
    src: templates/nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    validate: "nginx -t -c %s"
  notify: restart nginx

# Line in file
- name: Ensure line in config
  ansible.builtin.lineinfile:
    path: /etc/ssh/sshd_config
    regexp: '^PermitRootLogin'
    line: 'PermitRootLogin no'
  notify: restart sshd

# Block in file
- name: Add config block
  ansible.builtin.blockinfile:
    path: /etc/hosts
    block: |
      192.168.1.10 web-1
      192.168.1.11 web-2
    marker: "# {mark} ANSIBLE MANAGED BLOCK"

# Delete file/directory
- name: Remove file
  ansible.builtin.file:
    path: /tmp/old-file
    state: absent
```

### Service Management

```yaml
# Manage service
- name: Start and enable nginx
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true

# Systemd specific
- name: Reload systemd and start service
  ansible.builtin.systemd:
    name: myapp
    state: started
    enabled: true
    daemon_reload: true
```

### User & Group Management

```yaml
# Create user
- name: Create application user
  ansible.builtin.user:
    name: appuser
    shell: /bin/bash
    groups: sudo
    append: true
    create_home: true

# Add SSH key
- name: Add authorized key
  ansible.builtin.authorized_key:
    user: deploy
    key: "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"

# Create group
- name: Create group
  ansible.builtin.group:
    name: appgroup
    state: present
```

### Command Execution

```yaml
# Command (simple, no shell features)
- name: Check version
  ansible.builtin.command: nginx -v
  register: nginx_version
  changed_when: false

# Shell (supports pipes, redirects)
- name: Count processes
  ansible.builtin.shell: ps aux | grep nginx | wc -l
  register: process_count
  changed_when: false

# Script
- name: Run script
  ansible.builtin.script: scripts/setup.sh
  args:
    creates: /opt/app/.initialized  # Skip if file exists
```

---

## Inventory Patterns

### INI Format

```ini
# inventory/production/hosts.ini

[webservers]
web-1 ansible_host=10.0.1.10 http_port=8080
web-2 ansible_host=10.0.1.11 http_port=8081
web-3 ansible_host=10.0.1.12 http_port=8082

[databases]
db-primary ansible_host=10.0.2.10 db_role=primary
db-replica ansible_host=10.0.2.11 db_role=replica

[monitoring]
prometheus ansible_host=10.0.3.10
grafana ansible_host=10.0.3.11

# Group of groups
[production:children]
webservers
databases
monitoring

# Group variables
[production:vars]
ansible_user=deploy
ansible_ssh_private_key_file=~/.ssh/prod_key
env_name=production

[webservers:vars]
nginx_worker_processes=4

[databases:vars]
postgres_version=15
```

### YAML Format

```yaml
# inventory/production/hosts.yml
all:
  children:
    production:
      children:
        webservers:
          hosts:
            web-1:
              ansible_host: 10.0.1.10
              http_port: 8080
            web-2:
              ansible_host: 10.0.1.11
              http_port: 8081
          vars:
            nginx_worker_processes: 4
        databases:
          hosts:
            db-primary:
              ansible_host: 10.0.2.10
              db_role: primary
          vars:
            postgres_version: 15
      vars:
        ansible_user: deploy
        env_name: production
```

### Dynamic Inventory

```bash
# AWS EC2
ansible-inventory -i aws_ec2.yml --list

# aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions:
  - us-east-1
filters:
  tag:Environment: production
keyed_groups:
  - key: tags.Role
    prefix: role
```

---

## Role Directory Structure

```
roles/
└── webserver/                    # Role name
    ├── tasks/
    │   ├── main.yml              # Entry point — always loaded
    │   ├── install.yml           # Sub-tasks (included from main)
    │   └── configure.yml
    ├── handlers/
    │   └── main.yml              # Handlers
    ├── templates/
    │   ├── nginx.conf.j2         # Jinja2 templates
    │   └── vhost.conf.j2
    ├── files/
    │   ├── index.html            # Static files
    │   └── ssl/
    ├── vars/
    │   └── main.yml              # Role variables (high priority)
    ├── defaults/
    │   └── main.yml              # Default variables (low priority, override-able)
    ├── meta/
    │   └── main.yml              # Role metadata + dependencies
    ├── tests/
    │   ├── inventory
    │   └── test.yml
    └── README.md
```

### Role Meta Example

```yaml
# roles/webserver/meta/main.yml
---
galaxy_info:
  role_name: webserver
  author: devops-team
  description: Configure NGINX web server
  min_ansible_version: "2.14"
  platforms:
    - name: Ubuntu
      versions: [22.04, 24.04]
    - name: Debian
      versions: [12]

dependencies:
  - role: common
  - role: security_baseline
```

---

## Jinja2 Template Reference

### Variables

```jinja2
{{ variable_name }}
{{ server.hostname }}
{{ hostvars[inventory_hostname]['ansible_default_ipv4']['address'] }}
```

### Filters

```jinja2
{{ name | upper }}                    {# UPPERCASE #}
{{ name | lower }}                    {# lowercase #}
{{ name | capitalize }}               {# Capitalize #}
{{ list | join(', ') }}              {# Join list #}
{{ value | default('N/A') }}         {# Default value #}
{{ password | hash('sha512') }}      {# Hash #}
{{ dict | to_json }}                 {# To JSON #}
{{ dict | to_yaml }}                 {# To YAML #}
{{ path | basename }}                {# File basename #}
{{ path | dirname }}                 {# Directory name #}
{{ list | length }}                  {# List length #}
{{ number | int }}                   {# To integer #}
{{ items | selectattr('active') }}   {# Filter objects #}
{{ items | map(attribute='name') }}  {# Extract attribute #}
{{ value | regex_replace('old', 'new') }}  {# Regex replace #}
```

### Control Structures

```jinja2
{# Conditional #}
{% if environment == 'production' %}
debug = false
{% elif environment == 'staging' %}
debug = true
log_level = info
{% else %}
debug = true
log_level = debug
{% endif %}

{# Loop #}
{% for server in groups['webservers'] %}
upstream {{ server }} {
    server {{ hostvars[server]['ansible_host'] }}:{{ http_port }};
}
{% endfor %}

{# Loop with index #}
{% for item in items %}
server_{{ loop.index }} = {{ item }}
{% endfor %}

{# Comment #}
{# This is a Jinja2 comment #}
```

---

## Variable Precedence (Simplified)

```
LOWEST PRIORITY (easily overridden)
────────────────────────────────────
1.  role defaults (defaults/main.yml)
2.  inventory group_vars/all
3.  inventory group_vars/<group>
4.  inventory host_vars/<host>
5.  playbook group_vars/all
6.  playbook group_vars/<group>
7.  playbook host_vars/<host>
8.  host facts / registered vars
9.  play vars
10. play vars_prompt
11. play vars_files
12. role vars (vars/main.yml)
13. block vars
14. task vars
15. include_vars
16. set_facts / registered vars
17. role parameters
18. include parameters
19. extra vars (-e) ← ALWAYS WIN
────────────────────────────────────
HIGHEST PRIORITY (hardest to override)
```

**Best practice:**
- Put defaults in `defaults/main.yml` (levels 1)
- Override per-environment in `group_vars/` (levels 2-7)
- Emergency override with `-e` (level 19)

---

## Ansible vs Other Config Management Tools

| Feature | Ansible | Puppet | Chef | Salt |
|---------|---------|--------|------|------|
| **Architecture** | Agentless | Agent + Server | Agent + Server | Agent + Master |
| **Transport** | SSH/WinRM | HTTPS (agent→server) | HTTPS (agent→server) | ZeroMQ |
| **Language** | YAML + Jinja2 | Puppet DSL (Ruby-like) | Ruby DSL | YAML + Jinja2 |
| **Model** | Push (default) | Pull (30 min interval) | Pull (30 min interval) | Push + Pull |
| **Idempotency** | Module-dependent | Built-in (resource model) | Recipe-dependent | Built-in |
| **Learning curve** | Low | Medium | High | Medium |
| **Performance** | Medium (SSH overhead) | High (agent compiled) | High | Very High (ZeroMQ) |
| **Scale** | ~500 hosts easy | 10,000+ hosts | 10,000+ hosts | 10,000+ hosts |
| **Community** | Very large | Large | Declining | Medium |
| **Use in 2024+** | Config + orchestration | Large enterprise fleets | Legacy | Event-driven infra |
| **K8s relevance** | Node bootstrapping | Node config enforcement | Low | Event automation |

---

## ansible.cfg Reference

```ini
[defaults]
# Inventory
inventory = inventory/production/hosts.ini

# Roles path
roles_path = roles:~/.ansible/roles:/etc/ansible/roles

# Performance
forks = 20                              # Parallel hosts (default: 5)
gathering = smart                       # Cache facts
fact_caching = jsonfile
fact_caching_connection = /tmp/facts_cache
fact_caching_timeout = 86400            # 24 hours

# Output
stdout_callback = yaml                  # Readable output
callbacks_enabled = profile_tasks       # Show task timing

# Misc
retry_files_enabled = false
host_key_checking = true                # Keep true in production!
timeout = 30
remote_tmp = /tmp/.ansible/tmp

[ssh_connection]
pipelining = True                       # Major performance boost
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=yes
control_path_dir = /tmp/.ansible/cp

[privilege_escalation]
become = false                          # Don't sudo by default
become_method = sudo
become_ask_pass = false
```

---

## Ansible Vault Quick Reference

```bash
# Create encrypted file
ansible-vault create secrets.yml

# Encrypt existing file
ansible-vault encrypt vars/credentials.yml

# Decrypt file
ansible-vault decrypt vars/credentials.yml

# Edit encrypted file (decrypts in memory)
ansible-vault edit vars/credentials.yml

# View encrypted file
ansible-vault view vars/credentials.yml

# Change vault password
ansible-vault rekey vars/credentials.yml

# Encrypt single string
ansible-vault encrypt_string 'super-secret' --name 'db_password'
# Output:
# db_password: !vault |
#   $ANSIBLE_VAULT;1.1;AES256
#   30653...

# Use in playbook
ansible-playbook -i inventory/production/hosts.ini site.yml --ask-vault-pass
ansible-playbook -i inventory/production/hosts.ini site.yml --vault-password-file ~/.vault_pass

# Multiple vault IDs (multi-environment)
ansible-playbook -i inventory/production/hosts.ini site.yml \
  --vault-id dev@~/.vault_dev \
  --vault-id prod@~/.vault_prod
```

---

## Troubleshooting Decision Tree

```
Playbook fails
│
├── Connection error?
│   ├── Check SSH: ssh user@host
│   ├── Check inventory: ansible-inventory --host <host>
│   ├── Check ansible.cfg: host_key_checking
│   └── Check firewall: port 22 open?
│
├── Permission error?
│   ├── Need sudo? → become: true
│   ├── Wrong user? → ansible_user
│   ├── Key auth fails? → ansible_ssh_private_key_file
│   └── Vault password? → --ask-vault-pass
│
├── Module error?
│   ├── Wrong module? → ansible-doc <module>
│   ├── Missing parameter? → Check required params
│   ├── Wrong state? → present/absent/latest
│   └── Package not found? → update_cache: true
│
├── Template error?
│   ├── Variable undefined? → {{ var | default('') }}
│   ├── Jinja2 syntax? → Check {% %} vs {{ }}
│   └── Filter error? → ansible-doc -t filter <filter>
│
├── Idempotency issue?
│   ├── Using shell/command? → Switch to proper module
│   ├── Missing changed_when? → Add changed_when: false
│   └── creates/removes? → Add creates: /path/to/flag
│
└── Performance issue?
    ├── Slow SSH? → Enable pipelining
    ├── Too serial? → Increase forks
    ├── Gathering facts? → gathering: smart + caching
    └── Many hosts? → Consider ansible-pull or Tower
```

