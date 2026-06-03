# Day 15: Extended Exercises - Roles, Vault, Dynamic Inventory

**Level:** Intermediate-Advanced | **Thời gian ước tính:** 3-4 giờ (ngoài lab chính)

---

## Exercise 1: Role Skeleton & Structure Mastery

### Mục tiêu
Thành thạo `ansible-galaxy role init` và hiểu từng thư mục.

### Bài tập

**1.1 - Tạo role skeleton cho `nginx`:**

```bash
cd ~/ansible-training/roles
ansible-galaxy role init nginx

# Kết quả:
# - nginx/
#   ├── defaults/main.yml
#   ├── files/
#   ├── handlers/main.yml
#   ├── meta/main.yml
#   ├── README.md
#   ├── tasks/main.yml
#   ├── templates/
#   ├── tests/
#   │   ├── inventory
#   │   └── test.yml
#   └── vars/main.yml
```

**1.2 - Điền nội dung vào `defaults/main.yml` cho role nginx:**

Tạo defaults cho các biến: version (`1.24.0`), port (`80`), worker_processes (`auto`), worker_connections (`1024`), server_name (`localhost`), document_root (`/var/www/html`).

**1.3 - Viết `tasks/main.yml` với 3 tasks:**
- Install nginx package
- Ensure nginx service is enabled and started
- Verify nginx is responding (dùng `uri` module)

**1.4 - Viết handler `restart nginx` và `reload nginx` (sự khác biệt giữa restart và reload là gì trong context nginx?)**

**Kết quả mong đợi:**
```bash
ansible-playbook -i inventory/staging/ playbooks/nginx.yml --check
# Phải không có lỗi syntax, chỉ có changed tasks
```

---

## Exercise 2: Vault Deep Dive

### Mục tiêu
Nắm vững tất cả operations của Ansible Vault, kể cả multiple vault IDs.

### Bài tập

**2.1 - Tạo 2 vault password files riêng cho staging và production:**

```bash
echo "StagingVaultPass2024!" > ~/.vault_pass_staging
echo "ProductionVaultPass2024!" > ~/.vault_pass_prod
chmod 600 ~/.vault_pass_staging ~/.vault_pass_prod
```

**2.2 - Tạo 2 vault files riêng với ID:**

```bash
# Staging vault
ansible-vault encrypt group_vars/staging/vault.yml \
  --vault-id staging@~/.vault_pass_staging

# Production vault
ansible-vault encrypt group_vars/production/vault.yml \
  --vault-id prod@~/.vault_pass_prod
```

**2.3 - Viết playbook chạy được với cả 2 vault IDs:**

```bash
ansible-playbook site.yml \
  --vault-id staging@~/.vault_pass_staging \
  --vault-id prod@~/.vault_pass_prod
```

**2.4 - Thực hành inline vault encryption:**

Encrypt 3 strings sau và paste vào `group_vars/all/main.yml`:
- `MyDatabasePassword2024!` → biến `db_password`
- `redis://user:pass@localhost:6379` → biến `redis_url`
- `sk-prod-anthropic-key-abc123` → biến `ai_api_key`

**2.5 - Challenge: Rotate vault password**

Đổi password của `group_vars/all/vault.yml` từ password cũ sang password mới mà không decrypt/re-encrypt thủ công. Lệnh nào giải quyết việc này trong một bước?

**Câu hỏi suy nghĩ:**
- Tại sao `ansible-vault rekey` an toàn hơn là decrypt → encrypt lại bằng tay?
- Trong CI/CD pipeline (GitHub Actions), bạn sẽ store vault password ở đâu và truyền vào Ansible như thế nào?

---

## Exercise 3: Galaxy Role Integration

### Mục tiêu
Thực hành dùng Galaxy roles trong production workflow.

### Bài tập

**3.1 - Tạo `requirements.yml` với các dependencies sau (pin versions):**
- `cloudalchemy.node_exporter` version `2.1.0`
- `geerlingguy.java` version `2.0.0`
- Collection `amazon.aws` version `6.5.0`
- Collection `community.general` version `7.3.0`

**3.2 - Cài đặt và verify:**

```bash
# Cài tất cả
ansible-galaxy install -r requirements.yml -p ./roles
ansible-galaxy collection install -r requirements.yml

# Verify
ansible-galaxy list
ansible-galaxy collection list
```

**3.3 - Tạo playbook dùng Galaxy role `cloudalchemy.node_exporter` bên cạnh custom role `node_exporter` của bạn:**

Khi nào bạn sẽ dùng Galaxy version? Khi nào dùng custom version bạn đã viết trong lab?

**3.4 - Đọc source code của `cloudalchemy.node_exporter` trên GitHub:**

So sánh với role bạn viết. Liệt kê 3 điểm khác biệt và giải thích tại sao they made those design choices.

---

## Exercise 4: Dynamic Inventory Advanced

### Mục tiêu
Thiết lập dynamic inventory hoàn chỉnh và test local simulation.

### Bài tập

**4.1 - Local simulation với Docker:**

Nếu không có AWS, dùng Docker để tạo môi trường local:

```bash
# Tạo docker-compose.yml
cat > ~/ansible-training/docker-compose.yml << 'EOF'
version: "3"
services:
  node1:
    image: ubuntu:22.04
    container_name: ansible_node1
    command: /bin/bash -c "apt-get update && apt-get install -y openssh-server python3 && service ssh start && tail -f /dev/null"
    ports:
      - "2221:22"
    labels:
      ansible.role: "monitoring"
      ansible.env: "staging"

  node2:
    image: ubuntu:22.04
    container_name: ansible_node2
    command: /bin/bash -c "apt-get update && apt-get install -y openssh-server python3 && service ssh start && tail -f /dev/null"
    ports:
      - "2222:22"
    labels:
      ansible.role: "webserver"
      ansible.env: "staging"
EOF

docker-compose up -d
```

**4.2 - Viết dynamic inventory script cho Docker:**

```python
#!/usr/bin/env python3
# inventory/docker_inventory.py
import json
import subprocess

def get_docker_containers():
    result = subprocess.run(
        ["docker", "ps", "--format", "json"],
        capture_output=True, text=True
    )
    containers = []
    for line in result.stdout.strip().split('\n'):
        if line:
            containers.append(json.loads(line))
    return containers

def build_inventory(containers):
    inventory = {
        "_meta": {"hostvars": {}},
        "all": {"hosts": [], "children": []}
    }

    for container in containers:
        name = container.get("Names", "").strip("/")
        # Get container IP
        ip_result = subprocess.run(
            ["docker", "inspect", "-f",
             "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name],
            capture_output=True, text=True
        )
        ip = ip_result.stdout.strip()

        inventory["all"]["hosts"].append(name)
        inventory["_meta"]["hostvars"][name] = {
            "ansible_host": ip,
            "ansible_user": "root",
            "ansible_port": 22
        }

    return inventory

if __name__ == "__main__":
    containers = get_docker_containers()
    print(json.dumps(build_inventory(containers), indent=2))
```

```bash
# Test script
chmod +x inventory/docker_inventory.py
python3 inventory/docker_inventory.py
ansible-inventory -i inventory/docker_inventory.py --list
```

**4.3 - Viết `aws_ec2.yml` với các requirements:**
- Chỉ lấy instances trong `ap-southeast-1` và `ap-southeast-2`
- Filter: tag `Environment=production` VÀ `ManagedBy=terraform`
- Group by tag `Role`, `Environment`, `Application`
- Hostname = tag `Name`
- Kết nối qua `private_ip_address`
- Cache 10 phút

**4.4 - Giải thích cấu trúc JSON output của dynamic inventory:**

Chạy `ansible-inventory --list` và giải thích cấu trúc:
- `_meta.hostvars` chứa gì?
- `all.children` là gì?
- Một host có thể thuộc nhiều groups không?

---

## Exercise 5: Production-Grade Role Enhancement

### Mục tiêu
Nâng cấp role `node_exporter` lên production-grade.

### Bài tập

**5.1 - Thêm TLS support vào role:**

```yaml
# Thêm vào defaults/main.yml
node_exporter_tls_enabled: false
node_exporter_tls_cert_path: "/etc/node_exporter/tls.crt"
node_exporter_tls_key_path: "/etc/node_exporter/tls.key"

# Thêm vào templates/node_exporter.service.j2
{% if node_exporter_tls_enabled %}
  --web.config.file="{{ node_exporter_config_dir }}/web-config.yml" \
{% endif %}
```

**5.2 - Thêm web-config.yml template cho TLS + Basic Auth:**

```yaml
# templates/web-config.yml.j2
tls_server_config:
  cert_file: "{{ node_exporter_tls_cert_path }}"
  key_file: "{{ node_exporter_tls_key_path }}"

basic_auth_users:
  prometheus: "{{ node_exporter_basic_auth_password_hash }}"
```

**5.3 - Thêm molecule testing (optional - nếu có thời gian):**

```bash
pip install molecule molecule-docker

cd roles/node_exporter
molecule init scenario --driver-name docker

# Chạy test
molecule test
```

**5.4 - Thêm Ansible lint:**

```bash
pip install ansible-lint

# Lint role
ansible-lint roles/node_exporter/

# Fix phổ biến:
# [yaml] trailing spaces
# [fqcn] use FQCN for module names: ansible.builtin.copy instead of copy
# [name] task name should start with uppercase
```

**5.5 - Fix tất cả ansible-lint warnings và rerun cho clean output.**

---

## Exercise 6: Secret Management Comparison

### Mục tiêu
Hiểu và thực hành các approaches khác nhau cho secret management.

### Bài tập

**6.1 - Implement Ansible Vault lookup từ environment variable:**

```yaml
# playbooks/secrets_test.yml
- hosts: localhost
  tasks:
    - name: Read secret from environment variable
      set_fact:
        api_key: "{{ lookup('env', 'MY_API_KEY') }}"

    - name: Fail if secret not set
      assert:
        that: api_key != ""
        fail_msg: "MY_API_KEY environment variable is not set"
```

**6.2 - Implement lookup từ file (không vault):**

```yaml
- name: Read password from secure file
  set_fact:
    db_password: "{{ lookup('file', '~/.secrets/db_pass') }}"
```

So sánh 3 cách: Ansible Vault, env variable, file lookup. Khi nào dùng cái nào?

**6.3 - Nếu có HashiCorp Vault (hoặc Vault dev server):**

```bash
# Start Vault dev server local
vault server -dev -dev-root-token-id="root" &

# Set env
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN="root"

# Write secret
vault kv put secret/myapp/db password="SuperSecret2024!" username="myapp"

# Read từ Ansible
ansible localhost -m debug \
  -a "msg={{ lookup('community.hashi_vault.hashi_vault', 'secret/data/myapp/db:password', token='root', url='http://127.0.0.1:8200') }}"
```

**6.4 - Decision framework:**

Điền vào bảng sau cho scenario của bạn:

| Scenario | Tool đề xuất | Lý do |
|---|---|---|
| Solo developer, local lab | | |
| Team 5 người, startup, AWS | | |
| Công ty 100 người, on-premise | | |
| Fintech startup, MAS compliance | | |
| Bank, SOC2 Type II required | | |

---

## Exercise 7: End-to-End Integration

### Mục tiêu
Kết hợp tất cả kiến thức Day 13-15 trong một workflow hoàn chỉnh.

### Bài tập - Mini Project

**Scenario:** Bạn là DevOps engineer tại một startup. Cần deploy monitoring stack (Node Exporter) lên 3 servers (web, db, cache).

**Requirements:**
1. Role `node_exporter` tái sử dụng được (đã làm trong lab)
2. Secrets mã hóa bằng Vault (dashboard password, Slack webhook)
3. Inventory dynamic (dùng file YAML groups, không hardcode IP)
4. Playbook hỗ trợ staging và production environments
5. Tags để chạy selective (chỉ install, chỉ configure, chỉ verify)
6. Pre-task: update package cache
7. Post-task: gửi notification (Slack hoặc log message)

**Structure cuối cùng:**
```
mini-project/
├── ansible.cfg
├── requirements.yml
├── site.yml               # Top-level playbook include các playbook khác
├── playbooks/
│   └── monitoring.yml
├── inventory/
│   ├── staging/
│   │   └── hosts.yml
│   └── production/
│       └── aws_ec2.yml   # (hoặc hosts.yml nếu không có AWS)
├── group_vars/
│   ├── all/
│   │   ├── main.yml
│   │   └── vault.yml     # ENCRYPTED
│   ├── staging/
│   │   └── main.yml
│   └── production/
│       └── main.yml
└── roles/
    └── node_exporter/    # Role đã tạo trong lab
```

**Deliverables:**
- [ ] `requirements.yml` với pinned versions
- [ ] `group_vars/all/vault.yml` đã encrypt ít nhất 2 secrets
- [ ] `group_vars/all/main.yml` reference vault vars
- [ ] Playbook chạy được với `--check` trên staging
- [ ] Output sạch (0 warnings từ ansible-lint)

---

## Câu hỏi Review - Day 13 đến Day 15

Trả lời các câu hỏi sau để củng cố kiến thức phase Ansible:

**Về Mental Model (Day 13):**
1. Khi nào Ansible kết nối SSH và khi nào nó không cần SSH?
2. `gather_facts: false` có tác dụng gì và khi nào nên dùng?

**Về Variables và Control Flow (Day 14):**
3. Viết task chỉ chạy trên Ubuntu 22.04 VÀ khi biến `deploy_monitoring` là `true`.
4. Handler khác task bình thường như thế nào? Nếu một handler được notify 5 lần trong cùng một play, nó chạy mấy lần?

**Về Roles và Vault (Day 15):**
5. `ansible-galaxy role init myapp` tạo ra những thư mục gì?
6. Bạn đang pair programming với teammate. Teammate commit `group_vars/all/vault.yml` lên git, nhưng quên encrypt. Hậu quả là gì và bạn xử lý như thế nào (ngay lập tức + dài hạn)?
7. EC2 instance có tags `Role=webserver`, `Environment=production`, `App=frontend`. Dynamic inventory tạo ra những groups nào (dựa trên config `keyed_groups` tiêu chuẩn)?

---

## Challenge Problems

### Challenge 1: Role Dependency Chain

Tạo role `monitoring_stack` phụ thuộc vào `node_exporter` (dùng `meta/main.yml` dependencies). Khi gọi `monitoring_stack`, Ansible tự động chạy `node_exporter` trước.

```yaml
# roles/monitoring_stack/meta/main.yml
dependencies:
  - role: node_exporter
    vars:
      node_exporter_version: "1.7.0"
```

Verify bằng cách thêm một task vào `monitoring_stack` và chạy playbook - `node_exporter` phải chạy trước.

### Challenge 2: Idempotency Test

Chạy playbook `monitoring.yml` 3 lần liên tiếp. Lần đầu tiên `changed` tasks là bao nhiêu? Lần 2 và 3?

Nếu lần 2 vẫn có `changed`, tìm task nào không idempotent và fix nó.

```bash
for i in 1 2 3; do
  echo "=== Run $i ==="
  ansible-playbook playbooks/monitoring.yml -i inventory/staging/ \
    --vault-password-file ~/.vault_pass \
    | grep -E "ok=|changed=|failed="
done
```

### Challenge 3: Role Testing với Molecule

Setup Molecule với Docker driver để test role `node_exporter`:
- Converge: chạy role trên Docker container Ubuntu 22.04
- Verify: curl `localhost:9100/metrics` trả về HTTP 200
- Idempotency: chạy 2 lần, lần 2 phải có 0 changed tasks

```bash
pip install molecule molecule-docker
cd roles/node_exporter
molecule init scenario default --driver-name docker
molecule test
```

### Challenge 4: Custom Dynamic Inventory từ Terraform State

Viết Python script đọc `terraform.tfstate` và generate Ansible inventory:

```python
#!/usr/bin/env python3
# inventory/terraform_inventory.py

import json
import sys

def read_tfstate(state_file):
    with open(state_file) as f:
        return json.load(f)

def build_inventory(tfstate):
    inventory = {"_meta": {"hostvars": {}}}

    for resource in tfstate.get("resources", []):
        if resource["type"] == "aws_instance":
            for instance in resource["instances"]:
                attrs = instance["attributes"]
                name = attrs.get("tags", {}).get("Name", attrs["id"])
                role = attrs.get("tags", {}).get("Role", "ungrouped")

                if role not in inventory:
                    inventory[role] = {"hosts": []}

                inventory[role]["hosts"].append(name)
                inventory["_meta"]["hostvars"][name] = {
                    "ansible_host": attrs.get("private_ip"),
                    "ansible_user": "ubuntu",
                }

    return inventory

if __name__ == "__main__":
    state_file = sys.argv[1] if len(sys.argv) > 1 else "terraform.tfstate"
    tfstate = read_tfstate(state_file)
    print(json.dumps(build_inventory(tfstate), indent=2))
```

Test với mock tfstate file và verify inventory output đúng format.

---

## Tự đánh giá

Sau khi hoàn thành exercises, tự chấm điểm:

| Kỹ năng | Chưa làm được | Làm được với tham khảo | Làm được không cần tham khảo |
|---|---|---|---|
| Tạo role structure từ đầu | | | |
| Phân biệt defaults vs vars | | | |
| Encrypt/decrypt vault file | | | |
| Inline vault encryption | | | |
| Cài Galaxy roles từ requirements.yml | | | |
| Viết aws_ec2.yml dynamic inventory | | | |
| Debug inventory với --graph | | | |
| Chạy playbook với vault password | | | |
| Tạo idempotent tasks | | | |
| Debug failed vault decryption | | | |

**Nếu còn ô "Chưa làm được":** Quay lại lesson.md phần tương ứng và thực hành lại.

**Nếu tất cả "Không cần tham khảo":** Bạn sẵn sàng cho Day 16 - Terraform + Ansible Integration.
