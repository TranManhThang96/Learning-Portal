# Day 14: Cheat Sheet & Reference

**Variables, Facts, Conditionals, Loops, Handlers, Jinja2, Tags, Check/Diff Mode**

---

## Variable Precedence - Quick Reference

```
LOWEST                                                    HIGHEST
   │                                                         │
   ▼                                                         ▼
[1] role defaults       →  roles/myrole/defaults/main.yml
[2] inventory vars      →  INI/YAML inventory file
[3] inventory group_vars from inventory dir
[4] playbook group_vars →  group_vars/*.yml
[5] inventory host_vars from inventory dir
[6] playbook host_vars  →  host_vars/*.yml
[7] host facts
[8] play vars           →  vars: in play
[9] play vars_prompt
[10] play vars_files
[11] role vars          →  roles/myrole/vars/main.yml     ← OVERRIDES group_vars!
[12] block vars
[13] task vars          →  vars: in task
[14] include_vars
[15] set_facts / register
[16] role params
[17] include params
[18] extra vars         →  -e "key=val"                  ← ALWAYS WINS
```

**Thực tế - 3 levels thường dùng:**

```
role/defaults/  →  Fallback defaults (can be overridden by anything)
group_vars/     →  Environment config (dev/staging/prod)
-e extra_vars   →  Emergency/pipeline override
```

---

## Facts - Quick Reference

### Gather và filter

```bash
# All facts for a host
ansible <host> -m setup

# Filter by pattern
ansible <host> -m setup -a "filter=ansible_os*"
ansible <host> -m setup -a "filter=ansible_memory*"
ansible <host> -m setup -a "filter=ansible_processor*"
ansible <host> -m setup -a "filter=ansible_default_ipv4"
```

### Facts hay dùng nhất

```yaml
# OS
ansible_os_family              # "Debian" | "RedHat" | "Darwin"
ansible_distribution           # "Ubuntu" | "CentOS" | "Debian"
ansible_distribution_version   # "22.04" | "7" | "11"
ansible_distribution_major_version  # "22" | "7" | "11"

# Hardware
ansible_processor_count        # Number of CPU cores
ansible_processor_vcpus        # Number of vCPUs
ansible_memtotal_mb            # Total RAM in MB
ansible_swaptotal_mb           # Swap size in MB

# Network
ansible_default_ipv4.address   # Primary IP
ansible_default_ipv4.interface # Interface name (eth0, ens3)
ansible_default_ipv4.gateway   # Default gateway
ansible_hostname               # Short hostname
ansible_fqdn                   # Fully qualified domain name
ansible_domain                 # Domain portion

# Time
ansible_date_time.iso8601      # "2025-01-15T10:30:00Z"
ansible_date_time.date         # "2025-01-15"
ansible_date_time.time         # "10:30:00"
ansible_date_time.epoch        # Unix timestamp

# Python
ansible_python_version         # "3.10.12"
ansible_python.executable      # "/usr/bin/python3"

# Env
ansible_env.HOME               # "/root"
ansible_env.PATH               # Current PATH
```

### Custom facts

```bash
# Trên managed host - tạo file
mkdir -p /etc/ansible/facts.d
cat > /etc/ansible/facts.d/app.fact << 'EOF'
[application]
version = 2.1.0
environment = production
EOF
```

```yaml
# Trong playbook
- debug:
    msg: "App version: {{ ansible_local.app.application.version }}"
```

---

## Conditionals - Quick Reference

```yaml
# Basic equality
when: ansible_os_family == "Debian"
when: environment != "production"
when: nginx_port == 80

# Version comparison
when: ansible_distribution_version is version("20.04", ">=")
when: ansible_distribution_version is version("18.04", "<")

# Boolean
when: ssl_enabled
when: not ssl_enabled
when: ssl_enabled | bool

# Defined/undefined
when: my_var is defined
when: my_var is undefined
when: my_var | default(false)

# String contains
when: "'web' in group_names"
when: "'production' in inventory_hostname"

# Multiple (AND) - list syntax
when:
  - ansible_os_family == "Debian"
  - ansible_distribution_version is version("20.04", ">=")

# OR - inline syntax
when: ansible_os_family == "Debian" or ansible_os_family == "RedHat"

# NOT
when: not ansible_check_mode

# Registered variable
when: my_command.rc == 0
when: my_command.rc != 0
when: my_command.stdout | length > 0
when: '"error" not in my_command.stdout'

# Host in group
when: inventory_hostname in groups['webservers']
when: inventory_hostname not in groups['dbservers']
```

---

## Loops - Quick Reference

```yaml
# Simple list
loop:
  - nginx
  - curl
  - vim

# Dict items
loop:
  - { name: alice, uid: 1001, groups: sudo }
  - { name: bob, uid: 1002, groups: docker }
# Access: item.name, item.uid, item.groups

# Loop over dict with dict2items
loop: "{{ my_dict | dict2items }}"
# Access: item.key, item.value

# Loop with index
loop: [a, b, c]
loop_control:
  index_var: idx      # 0-based index
  label: "{{ item }}" # Control display

# Loop over range
loop: "{{ range(1, 6) | list }}"  # [1, 2, 3, 4, 5]

# Nested loops (subelements)
loop: "{{ users | subelements('ssh_keys') }}"
# Access: item.0 (user), item.1 (ssh_key)

# Until (retry)
register: result
until: result.status == 200
retries: 5
delay: 10

# with_items (legacy, still works)
with_items:
  - item1
  - item2

# with_dict (legacy)
with_dict:
  key1: val1
  key2: val2
```

**Performance note:**

```yaml
# SLOW: N separate calls
- apt:
    name: "{{ item }}"
  loop: [nginx, curl, vim]

# FAST: Single call
- apt:
    name: [nginx, curl, vim]
    state: present
```

---

## Handlers - Quick Reference

```yaml
# Single notify
- task:
  notify: handler name

# Multiple notify
- task:
  notify:
    - handler one
    - handler two

# Handler definition
handlers:
  - name: handler name
    service:
      name: nginx
      state: reloaded

# Listen (group trigger)
handlers:
  - name: restart nginx
    listen: "web stack changed"
    service: { name: nginx, state: restarted }

  - name: restart php-fpm
    listen: "web stack changed"
    service: { name: php8.1-fpm, state: restarted }

- task:
  notify: "web stack changed"   # Both handlers fire

# Flush handlers immediately
- meta: flush_handlers

# Force handler (always run)
- name: Always restart
  service:
    name: nginx
    state: restarted
  changed_when: true    # Tricks Ansible into always notifying
  notify: handler name
```

**Handler execution rules:**
- Handlers chạy SAU KHI tất cả tasks trong play hoàn thành
- Handler chỉ chạy nếu notify từ task có `changed` status
- Handler chạy MỘT LẦN dù được notify nhiều lần
- Handler chạy theo THỨ TỰ DEFINED, không theo thứ tự notify
- `meta: flush_handlers` chạy handlers ngay lập tức

---

## Jinja2 - Quick Reference

### Syntax

```jinja2
{{ variable }}              {# Output variable #}
{{ dict.key }}              {# Dict access #}
{{ list[0] }}               {# List access #}
{% if ... %} {% endif %}     {# Conditional block #}
{% for ... %} {% endfor %}   {# Loop block #}
{# comment #}               {# Comment - not in output #}
```

### Filters - Complete Reference

#### String Filters

```jinja2
{{ "hello" | upper }}           → "HELLO"
{{ "HELLO" | lower }}           → "hello"
{{ "hello world" | title }}     → "Hello World"
{{ "  hello  " | trim }}        → "hello"
{{ "hello" | replace("l","r") }} → "herro"
{{ hostname | regex_replace("^web", "app") }}
{{ text | truncate(50) }}
{{ name | quote }}              → 'alice' (shell-safe)
```

#### Type Filters

```jinja2
{{ "42" | int }}                → 42
{{ "3.14" | float }}            → 3.14
{{ "true" | bool }}             → True
{{ 42 | string }}               → "42"
{{ my_list | join(', ') }}      → "a, b, c"
{{ my_dict | to_json }}         → JSON string
{{ my_dict | to_yaml }}         → YAML string
{{ json_str | from_json }}      → dict
{{ yaml_str | from_yaml }}      → dict
```

#### Default / Fallback

```jinja2
{{ var | default('fallback') }}
{{ var | default(omit) }}           # Omit param if undefined
{{ var | default(false) | bool }}
```

#### List Filters

```jinja2
{{ list | length }}             → count
{{ list | first }}              → first element
{{ list | last }}               → last element
{{ list | min }}                → minimum value
{{ list | max }}                → maximum value
{{ list | sort }}               → sorted list
{{ list | unique }}             → deduplicated
{{ list | reverse | list }}     → reversed
{{ list | flatten }}            → flattened nested list
{{ list | select("match", "^web") | list }}
{{ list | reject("match", "^db") | list }}
{{ list | map(attribute="name") | list }}
```

#### Dict Filters

```jinja2
{{ dict | dict2items }}         → list of {key, value}
{{ list | items2dict }}         → dict from key/value list
{{ dict.keys() | list }}        → list of keys
{{ dict.values() | list }}      → list of values
{{ dict | combine(other) }}     → merge dicts
```

#### Math Filters

```jinja2
{{ 10 | pow(2) }}               → 100
{{ 10 | abs }}                  → 10
{{ 3.7 | round }}               → 4.0
{{ 3.7 | round(0, 'floor') }}   → 3.0
{{ value | log(10) }}
```

#### Ansible-specific Filters

```jinja2
{{ path | basename }}           → "file.txt"
{{ path | dirname }}            → "/etc/nginx"
{{ path | expanduser }}         → expand ~
{{ path | realpath }}           → absolute path
{{ string | hash('sha1') }}
{{ string | b64encode }}
{{ b64_string | b64decode }}
{{ list | random }}             → random element
{{ value | ternary("yes", "no") }}  # Inline if-else
```

### Control Structures

```jinja2
{# If/elif/else #}
{% if env == "prod" %}
  worker_processes {{ cpu_count }};
{% elif env == "staging" %}
  worker_processes 2;
{% else %}
  worker_processes 1;
{% endif %}

{# For loop #}
{% for item in my_list %}
  {{ item }};
{% endfor %}

{# For with condition #}
{% for server in servers if server.active %}
  server {{ server.host }};
{% endfor %}

{# For with index #}
{% for item in items %}
  # Item {{ loop.index }}: {{ item }}   {# 1-based #}
  # Item {{ loop.index0 }}: {{ item }}  {# 0-based #}
  {% if loop.first %}# First item{% endif %}
  {% if loop.last %}# Last item{% endif %}
{% endfor %}

{# Set local variable #}
{% set myvar = "value" %}
{{ myvar }}
```

### Template module options

```yaml
- template:
    src: nginx.conf.j2          # Relative to templates/ dir
    dest: /etc/nginx/nginx.conf
    owner: root
    group: root
    mode: '0644'
    backup: true                # Backup before replacing
    validate: nginx -t -c %s   # Validate command (%s = temp file)
    force: true                 # Always replace (default: true)
```

---

## Tags - Quick Reference

```yaml
# Assign tags to task
- name: My task
  apt: ...
  tags:
    - install
    - packages

# Special tags
tags: always    # Always runs
tags: never     # Never runs (unless explicitly --tags never)

# Run CLI
ansible-playbook site.yml --tags install
ansible-playbook site.yml --tags "install,config"
ansible-playbook site.yml --skip-tags install
ansible-playbook site.yml --list-tags    # List all tags
ansible-playbook site.yml --list-tasks  # List all tasks
```

**Recommended tag strategy:**

```
install     → Package installation
config      → Configuration file changes
deploy      → Application code deployment
services    → Service state management
verify      → Health checks and verification
debug       → Debug tasks (tag: never by default)
always      → Setup/teardown that must always run
```

---

## Check Mode & Diff Mode

```bash
# Dry-run (no changes)
ansible-playbook site.yml --check

# Show file diffs
ansible-playbook site.yml --diff

# Both (recommended for pre-production review)
ansible-playbook site.yml --check --diff

# Check specific hosts
ansible-playbook site.yml --check --limit web01

# Check with extra vars
ansible-playbook site.yml --check --diff -e "environment=production"
```

**In playbook - check_mode awareness:**

```yaml
# Skip task during check mode
- name: Restart service (not in check mode)
  service:
    name: nginx
    state: restarted
  when: not ansible_check_mode

# Always run in check mode
- name: Must always check this
  command: some-read-only-command
  check_mode: false

# Mark task as always changed (force handler fire)
- name: Always triggers handler
  shell: echo "force"
  changed_when: true
```

---

## set_fact - Quick Reference

```yaml
# Static set_fact
- set_fact:
    my_var: "hello"
    my_number: 42
    my_list: [1, 2, 3]

# Dynamic set_fact (using Jinja2)
- set_fact:
    worker_count: "{{ ansible_processor_count * 2 }}"

# Conditional set_fact (ternary)
- set_fact:
    env_class: "{{ 'high' if ansible_memtotal_mb > 8192 else 'low' }}"

# From registered output
- command: cat /etc/app/version.txt
  register: version_raw

- set_fact:
    app_version: "{{ version_raw.stdout | trim }}"

# Cacheable facts (persist between plays)
- set_fact:
    my_fact: value
    cacheable: true
```

---

## register - Quick Reference

```yaml
- name: Run command
  command: /path/to/script
  register: script_result

# Fields of registered variable
script_result.rc          # Return code (int)
script_result.stdout      # Standard output (str)
script_result.stderr      # Standard error (str)
script_result.stdout_lines  # stdout as list
script_result.stderr_lines  # stderr as list
script_result.changed     # Boolean
script_result.failed      # Boolean
script_result.skipped     # Boolean

# For uri module
result.status             # HTTP status code
result.json               # Parsed JSON body
result.content            # Raw response body
result.headers            # Response headers dict

# For stat module
stat_result.stat.exists   # Boolean
stat_result.stat.isdir    # Boolean
stat_result.stat.size     # File size bytes
stat_result.stat.mode     # Octal mode string
stat_result.stat.md5      # MD5 hash
```

---

## assert Module - Validation

```yaml
- name: Validate configuration
  assert:
    that:
      - nginx_port is defined
      - nginx_port | int > 1024 or ansible_user == "root"
      - environment in ["development", "staging", "production"]
      - app_name | length > 0
    fail_msg: "Configuration validation failed!"
    success_msg: "All checks passed."
```

---

## Debug Module

```yaml
# Print message
- debug:
    msg: "Value is {{ my_var }}"

# Print variable directly
- debug:
    var: my_variable

# Print all variables (verbose)
- debug:
    var: hostvars[inventory_hostname]

# Only in verbose mode
- debug:
    msg: "Debug info"
    verbosity: 2    # Needs -vv to show
```

---

## Variable Files

```yaml
# In play - load variable files
vars_files:
  - vars/common.yml
  - "vars/{{ environment }}.yml"   # Dynamic file loading

# Conditional variable files
- include_vars: "{{ item }}"
  with_first_found:
    - "vars/{{ ansible_distribution }}-{{ ansible_distribution_version }}.yml"
    - "vars/{{ ansible_distribution }}.yml"
    - "vars/default.yml"
```

---

## Common Patterns

### Pattern 1: OS-adaptive installation

```yaml
- name: Install packages (Debian)
  apt:
    name: "{{ packages }}"
    state: present
  when: ansible_os_family == "Debian"
  vars:
    packages:
      - nginx
      - python3-pip

- name: Install packages (RedHat)
  yum:
    name: "{{ packages }}"
    state: present
  when: ansible_os_family == "RedHat"
  vars:
    packages:
      - nginx
      - python3-pip
```

### Pattern 2: Idempotent service deploy

```yaml
- name: Deploy config
  template:
    src: app.conf.j2
    dest: /etc/app/app.conf
  notify: restart app

handlers:
  - name: restart app
    service:
      name: myapp
      state: restarted
```

### Pattern 3: Fact-based resource allocation

```yaml
- name: Set resources based on hardware
  set_fact:
    db_connections: "{{ (ansible_memtotal_mb / 10) | int | min(500) }}"
    worker_threads: "{{ ansible_processor_count * 2 }}"
```

### Pattern 4: Environment branching

```yaml
# group_vars/all.yml
debug_mode: false
log_level: warn

# group_vars/development.yml
debug_mode: true
log_level: debug
```

### Pattern 5: Required variable validation

```yaml
pre_tasks:
  - name: Ensure required vars
    assert:
      that:
        - db_password is defined
        - db_password | length > 0
      fail_msg: "db_password is required. Set in vault or -e flag."
```

---

## Ansible Ad-hoc Fact Commands

```bash
# Get specific fact
ansible web01 -m setup -a "filter=ansible_os_family"

# Get memory info
ansible all -m setup -a "filter=ansible_memory_mb"

# Get IP address
ansible all -m setup -a "filter=ansible_default_ipv4"

# Format as JSON
ansible all -m setup | python3 -m json.tool

# Save facts to file
ansible all -m setup --tree /tmp/facts/
```
