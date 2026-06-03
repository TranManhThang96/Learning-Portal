# Day 13: Ansible Mental Model & Idempotency — Exercises

**Extended exercises và challenges cho Day 13**

---

## Exercise 1 — Inventory Expansion (Beginner)

**Mục tiêu:** Làm quen với inventory structure và cách Ansible resolve groups.

### Yêu cầu:

Tạo file `inventory/hosts-extended.yml` với cấu trúc sau:

```
all
├── staging
│   ├── webservers
│   │   ├── staging-web1 (ansible_host=127.0.0.1)
│   │   └── staging-web2 (ansible_host=127.0.0.2)
│   └── databases
│       └── staging-db1  (ansible_host=127.0.0.3)
└── production
    ├── webservers
    │   ├── prod-web1    (ansible_host=10.0.0.1)
    │   └── prod-web2    (ansible_host=10.0.0.2)
    └── databases
        └── prod-db1     (ansible_host=10.0.1.1, ansible_port=5432)
```

Variables:
- Tất cả hosts trong `staging`: `env=staging`, `log_level=debug`
- Tất cả hosts trong `production`: `env=production`, `log_level=error`
- Tất cả `webservers`: `http_port=80`, `app_port=8080`
- Tất cả `databases`: `db_port=5432`

### Câu hỏi sau khi tạo:

```bash
# Chạy các lệnh này và giải thích output
ansible-inventory -i inventory/hosts-extended.yml --list
ansible-inventory -i inventory/hosts-extended.yml --graph

# Câu hỏi:
# 1. Lệnh nào sẽ target cả staging-web1 và prod-web1?
#    ansible -i inventory/hosts-extended.yml ??? -m ping
# 2. Lệnh nào chỉ target tất cả database hosts?
# 3. Làm thế nào để target tất cả staging hosts?
```

### Đáp án tham khảo:

```bash
# 1. Tất cả webservers
ansible -i inventory/hosts-extended.yml webservers -m ping

# 2. Tất cả databases
ansible -i inventory/hosts-extended.yml databases -m ping

# 3. Tất cả staging
ansible -i inventory/hosts-extended.yml staging -m ping
```

---

## Exercise 2 — Idempotency Debugging (Beginner-Intermediate)

**Mục tiêu:** Identify và fix non-idempotent tasks.

### Code có vấn đề:

Playbook dưới đây có **4 tasks không idempotent**. Tìm và fix tất cả.

```yaml
---
# broken-playbook.yml - Tìm và fix các vấn đề idempotency
- name: Setup Application Server
  hosts: local
  become: false

  tasks:
    # Task 1
    - name: Create app directory
      shell: mkdir -p /opt/brokenapp

    # Task 2
    - name: Set permissions
      command: chmod 755 /opt/brokenapp

    # Task 3
    - name: Create config file
      shell: |
        cat > /opt/brokenapp/config.ini << 'EOF'
        [app]
        debug=false
        port=8080
        EOF

    # Task 4  
    - name: Add log entry
      shell: echo "$(date): Server configured" >> /opt/brokenapp/setup.log

    # Task 5 (này đúng rồi - giữ nguyên)
    - name: Ensure python3-pip is available
      apt:
        name: python3-pip
        state: present
      become: true
      ignore_errors: true  # bỏ qua nếu không có apt (MacOS)

    # Task 6
    - name: Create symlink
      shell: ln -s /opt/brokenapp /opt/app

    # Task 7 (này đúng rồi - giữ nguyên)
    - name: Verify directory exists
      stat:
        path: /opt/brokenapp
      register: dir_stat

    # Task 8 (này đúng rồi - giữ nguyên)
    - name: Display result
      debug:
        msg: "Directory exists: {{ dir_stat.stat.exists }}"
```

### Yêu cầu:

1. Chạy playbook lần 1 → ghi lại số `changed`
2. Chạy playbook lần 2 → `changed` có về 0 không?
3. Identify 4 tasks không idempotent
4. Viết lại `fixed-playbook.yml` với tất cả tasks đã fix

### Đáp án tham khảo:

```yaml
---
# fixed-playbook.yml
- name: Setup Application Server (Fixed)
  hosts: local
  become: false

  tasks:
    # Fix Task 1: shell mkdir → file module
    - name: Create app directory
      file:
        path: /opt/brokenapp
        state: directory
        mode: "0755"          # Fix Task 2 cũng ở đây

    # Fix Task 3: shell cat → copy module với force: false
    - name: Create config file
      copy:
        content: |
          [app]
          debug=false
          port=8080
        dest: /opt/brokenapp/config.ini
        force: false          # Không overwrite nếu đã tồn tại

    # Fix Task 4: shell echo append → copy với modification_time: preserve
    # Approach 1: Dùng copy với force: false (tạo 1 lần)
    - name: Create setup marker (idempotent)
      copy:
        content: "Server configured by Ansible\n"
        dest: /opt/brokenapp/setup.log
        force: false

    # Task 5 giữ nguyên
    - name: Ensure python3-pip is available
      apt:
        name: python3-pip
        state: present
      become: true
      ignore_errors: true

    # Fix Task 6: shell ln -s → file module với state: link
    - name: Create symlink
      file:
        src: /opt/brokenapp
        dest: /opt/app
        state: link

    # Task 7 & 8 giữ nguyên
    - name: Verify directory exists
      stat:
        path: /opt/brokenapp
      register: dir_stat

    - name: Display result
      debug:
        msg: "Directory exists: {{ dir_stat.stat.exists }}"
```

---

## Exercise 3 — Hardening Playbook Extension (Intermediate)

**Mục tiêu:** Mở rộng `hardening.yml` từ lab với các tasks thực tế hơn.

### Yêu cầu:

Tạo `hardening-extended.yml` với các sections sau:

#### Section A: Kernel Security Parameters

Thêm các sysctl settings hardening sau:

```
net.ipv4.ip_forward = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.log_martians = 1
kernel.randomize_va_space = 2
```

*Hint: Dùng `loop` để apply nhiều sysctl settings từ một list variables.*

#### Section B: File Permission Hardening

Đảm bảo các files/directories có permissions đúng:

```
/etc/crontab          → 0600, root:root
/etc/cron.d           → 0700, root:root
/tmp                  → 1777 (sticky bit)
/var/tmp              → 1777 (sticky bit)
```

*Hint: Dùng `file` module. Với `become: false` trên localhost lab, set `ignore_errors: true` hoặc đổi sang thư mục bạn có permission.*

#### Section C: Application User Setup

Tạo một application user với:
- Username: `appuser`
- Shell: `/bin/bash`
- Home: `/opt/appuser`
- Không có password (service account)
- Groups: không có sudo

Sau đó tạo directory structure cho user:
```
/opt/appuser/
├── app/
├── logs/
└── config/
```

#### Section D: Validation Report

Thêm play cuối tạo file `/opt/labapp/hardening-report.txt` với nội dung tóm tắt những gì đã được apply. Dùng `copy` module với `content` chứa Jinja2 template đơn giản:

```
Hardening Report
================
Date: {{ ansible_date_time.date }}
Hostname: {{ ansible_hostname }}
OS: {{ ansible_distribution }} {{ ansible_distribution_version }}

Applied:
- Kernel security parameters: YES
- Application user (appuser): YES
- Directory permissions: YES
```

### Kiểm tra:

```bash
# Phải pass tất cả
ansible-playbook hardening-extended.yml --check --diff
ansible-playbook hardening-extended.yml
ansible-playbook hardening-extended.yml  # Lần 2: changed must be 0
```

---

## Exercise 4 — Multi-Play Playbook (Intermediate)

**Mục tiêu:** Hiểu cách tổ chức nhiều "plays" trong một playbook, mỗi play target group khác nhau.

### Scenario:

Bạn cần deploy một ứng dụng web đơn giản với kiến trúc:
- `load_balancers` group: cài nginx làm reverse proxy
- `applications` group: setup app directory và config
- `databases` group: verify database connectivity

Với local lab, tất cả đều là `localhost` nhưng bạn sẽ thực hành cấu trúc multi-play.

### Yêu cầu:

Tạo `multi-play.yml`:

```yaml
---
# Play 1: Áp dụng cho load balancers
- name: Configure Load Balancers
  hosts: local              # Trong thực tế: hosts: load_balancers
  gather_facts: true
  tasks:
    # Tạo nginx upstream config structure (simulate)
    - name: Create nginx config directory
      file:
        path: "{{ ansible_env.HOME }}/lab-nginx/conf.d"
        state: directory
        mode: "0755"
    
    - name: Create upstream configuration
      copy:
        content: |
          # Upstream config - managed by Ansible
          # upstream backend {
          #     server app1.internal:8080;
          #     server app2.internal:8080;
          # }
        dest: "{{ ansible_env.HOME }}/lab-nginx/conf.d/upstream.conf"
        force: false

---
# Play 2: Áp dụng cho application servers
- name: Configure Application Servers
  hosts: local
  gather_facts: false       # Skip facts gathering (tăng tốc)
  tasks:
    # Tạo app structure
    # TODO: Hoàn thiện các tasks ở đây

---
# Play 3: Verify toàn bộ deployment
- name: Verify Deployment
  hosts: local
  gather_facts: false
  tasks:
    - name: Check all expected directories exist
      stat:
        path: "{{ item }}"
      register: check_results
      loop:
        - "{{ ansible_env.HOME }}/lab-nginx/conf.d"
        # TODO: Thêm các paths cần check

    - name: Assert everything is in place
      assert:
        that: item.stat.exists
        fail_msg: "Missing: {{ item.item }}"
        success_msg: "OK: {{ item.item }}"
      loop: "{{ check_results.results }}"
```

### Câu hỏi:

1. `gather_facts: false` ảnh hưởng gì? Khi nào nên dùng?
2. Nếu Play 1 fail, Play 2 có chạy không? Làm thế nào để thay đổi behavior này?
3. Trong thực tế, tại sao multi-play trong một file thường không được khuyến khích cho large codebases?

### Gợi ý trả lời:

1. `gather_facts: false` skip việc collect system info (OS, IP, RAM...) → nhanh hơn ~1-2s mỗi host. Dùng khi play không cần `ansible_*` variables.
2. Mặc định Ansible stop toàn bộ file nếu một play fail. Dùng `any_errors_fatal: false` để tiếp tục, hoặc `ignore_errors: true` trên từng task.
3. Khó maintain, khó test riêng lẻ, khó reuse. Best practice: một file một responsibility, kết hợp bằng `import_playbook:`.

---

## Exercise 5 — Register & Conditional (Intermediate-Advanced)

**Mục tiêu:** Dùng `register` để capture task output và `when` để branch logic.

### Scenario:

Bạn cần viết playbook tự động detect OS và install package manager phù hợp:
- Ubuntu/Debian: dùng `apt`
- RHEL/CentOS/Amazon Linux: dùng `dnf`
- macOS: output message hướng dẫn dùng Homebrew

### Yêu cầu:

Tạo `os-detect.yml`:

```yaml
---
- name: OS-aware Package Installation Demo
  hosts: local
  gather_facts: true

  vars:
    packages_to_install:
      - curl
      - git

  tasks:
    # Step 1: Display detected OS
    - name: Display OS information
      debug:
        msg:
          - "OS Family: {{ ansible_os_family }}"
          - "Distribution: {{ ansible_distribution }}"
          - "Version: {{ ansible_distribution_version }}"

    # Step 2: Install packages based on OS
    # TODO: Viết 3 tasks với when condition:
    # Task A: Install via apt (khi ansible_os_family == "Debian")
    # Task B: Install via dnf (khi ansible_os_family == "RedHat")  
    # Task C: Print manual instruction (khi ansible_os_family == "Darwin")

    # Step 3: Verify installation
    - name: Check if git is available
      command: git --version
      register: git_check
      changed_when: false
      ignore_errors: true

    - name: Report git status
      debug:
        msg: "Git status: {{ 'Available: ' + git_check.stdout if git_check.rc == 0 else 'NOT FOUND' }}"
```

### Đáp án tham khảo:

```yaml
    - name: Install packages on Debian/Ubuntu
      apt:
        name: "{{ packages_to_install }}"
        state: present
        update_cache: true
      when: ansible_os_family == "Debian"
      become: true

    - name: Install packages on RHEL/CentOS
      dnf:
        name: "{{ packages_to_install }}"
        state: present
      when: ansible_os_family == "RedHat"
      become: true

    - name: Manual instruction for macOS
      debug:
        msg: |
          macOS detected. Install manually với Homebrew:
          brew install {{ packages_to_install | join(' ') }}
      when: ansible_os_family == "Darwin"
```

---

## Exercise 6 — Challenge: Production-Grade Hardening Playbook (Advanced)

**Mục tiêu:** Viết một playbook hardening hoàn chỉnh, production-grade, fully idempotent.

### Context:

Đây là exercise tổng hợp. Bạn sẽ viết playbook có thể dùng như starting point cho real production servers.

### Yêu cầu:

Tạo `production-hardening.yml` với các đặc điểm:

#### 1. Tổ chức tốt với sections rõ ràng
Dùng `tags` để có thể chạy từng section độc lập:
```
tags: [always]     → System facts và pre-checks
tags: [packages]   → Package updates và installs
tags: [files]      → File và directory setup
tags: [security]   → Security hardening
tags: [verify]     → Validation tasks
```

#### 2. Fail-fast với pre-flight checks
```yaml
- name: Pre-flight | Verify control node requirements
  assert:
    that:
      - ansible_version.full is version('2.14', '>=')
    fail_msg: "Requires Ansible 2.14+, found {{ ansible_version.full }}"
  tags: [always]

- name: Pre-flight | Verify target OS
  assert:
    that:
      - ansible_os_family in ['Debian', 'RedHat', 'Darwin']
    fail_msg: "Unsupported OS: {{ ansible_os_family }}"
  tags: [always]
```

#### 3. Idempotent application directory setup
```
/opt/production-app/
├── bin/           (0750)
├── config/        (0700)
├── logs/          (0750)
├── data/          (0750)
└── tmp/           (1777, sticky bit)
```

#### 4. Security hardening (local-safe)
- Tạo file `/opt/production-app/config/security.conf` với security settings
- Verify file permissions sau khi tạo
- Tạo hardening audit log: `/opt/production-app/logs/hardening-audit.log` với timestamp (chỉ ghi 1 lần, idempotent)

#### 5. Reporting
Task cuối tạo report file `/opt/production-app/hardening-report.json`:

```json
{
  "timestamp": "{{ ansible_date_time.iso8601 }}",
  "hostname": "{{ ansible_hostname }}",
  "os": "{{ ansible_distribution }} {{ ansible_distribution_version }}",
  "ansible_version": "{{ ansible_version.full }}",
  "status": "completed"
}
```

#### 6. Error handling
Dùng `block/rescue/always` ít nhất một lần:

```yaml
- block:
    - name: Risky operation
      ...
  rescue:
    - name: Handle failure
      debug:
        msg: "Operation failed, performing cleanup"
  always:
    - name: Always run this (cleanup, logging)
      ...
```

### Acceptance criteria:

```bash
# Tất cả phải pass
ansible-playbook production-hardening.yml --syntax-check
ansible-playbook production-hardening.yml --check --diff
ansible-playbook production-hardening.yml                    # Lần 1
ansible-playbook production-hardening.yml                    # Lần 2: changed=0
ansible-playbook production-hardening.yml --tags verify      # Chỉ chạy verify
ansible-playbook production-hardening.yml --tags security    # Chỉ chạy security
```

---

## Self-Assessment Checklist

Sau khi hoàn thành các exercises, tự đánh giá:

### Phần 1 — Lý thuyết (không cần code)

- [ ] Tôi có thể giải thích agentless architecture của Ansible và khi nào nên chọn agent-based thay thế
- [ ] Tôi có thể vẽ sơ đồ Control Node → Managed Nodes và mô tả quá trình Ansible thực thi một task
- [ ] Tôi có thể map các khái niệm Ansible sang Terraform tương ứng (ít nhất 6 cặp)
- [ ] Tôi có thể giải thích idempotency bằng ngôn ngữ non-technical cho một PM
- [ ] Tôi biết khi nào KHÔNG dùng Ansible (ít nhất 3 scenarios)

### Phần 2 — Thực hành

- [ ] Tôi đã cài Ansible thành công và `ansible --version` hoạt động
- [ ] Tôi đã tạo inventory file và `ansible all -m ping` trả về SUCCESS
- [ ] Tôi đã chạy `hardening.yml` từ lab và xác nhận `changed=0` ở lần 2
- [ ] Tôi đã hoàn thành ít nhất Exercise 1 và Exercise 2
- [ ] Tôi đã dùng `--check --diff` trước khi apply ít nhất một lần

### Phần 3 — Advanced (optional nhưng recommended)

- [ ] Tôi đã hoàn thành Exercise 3 (Hardening Extension)
- [ ] Tôi đã hoàn thành Exercise 5 (Register & Conditional)
- [ ] Tôi đã thử Exercise 6 (Production-Grade Challenge)
- [ ] Tôi đã đọc qua `ansible-lint` output và hiểu ít nhất 3 warning messages

---

## Một số câu hỏi phỏng vấn thường gặp về Ansible

*(Để chuẩn bị cho technical discussions, không nhất thiết phải trả lời ngay hôm nay)*

**Q:** "Ansible không có state file như Terraform. Đây là ưu điểm hay nhược điểm? Team bạn xử lý vấn đề drift detection như thế nào?"

**Q:** "Khi nào bạn dùng `command:` module thay vì một module cụ thể? Trade-off là gì?"

**Q:** "Giải thích sự khác biệt giữa `import_tasks` và `include_tasks` trong Ansible."

**Q:** "Trong một rolling deployment với 10 web servers, làm thế nào để Ansible update từng server một, và rollback nếu có lỗi?"

**Q:** "Team bạn đang dùng Ansible Tower / AWX. Tại sao cần Tower thay vì chỉ chạy `ansible-playbook` từ CI/CD?"

---

## Tài nguyên cho bài tập thêm

- [Ansible Playground](https://www.katacoda.com/ansible) — Browser-based environment không cần setup
- [Jeff Geerling's Molecule Testing](https://molecule.readthedocs.io/) — Test Ansible roles trong containers
- [Ansible Galaxy - Linux hardening roles](https://galaxy.ansible.com/ui/search/?keywords=hardening) — Xem professional hardening roles để học cấu trúc
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks) — Tiêu chuẩn hardening thực tế (reference, không cần mua)
