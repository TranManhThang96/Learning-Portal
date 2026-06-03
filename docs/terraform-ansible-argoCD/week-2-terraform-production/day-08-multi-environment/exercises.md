# Day 8 - Exercises: Multi-Environment Strategy

**Prerequisites:** Hoan thanh lab chinh trong lesson.md (2 environments dev + staging da co)

---

## Exercise 1 - Environment Promotion Pipeline (Trung binh, ~45 phut)

### Boi canh

Ban la Platform Engineer tai mot startup. Team vua hop va quyet dinh: bat ky thay doi nao vao Terraform code phai di qua process: `dev -> staging -> prod`. Hien tai quy trinh hoan toan manual va khong co guardrail nao ca.

Viet mot shell script don gian de enforce quy trinh nay, bao gom safety checks truoc khi allow apply.

### Yeu cau

Viet script `promote.sh` voi cac tinh nang sau:

1. Nhan argument: `./promote.sh <from_env> <to_env> [--auto-approve]`
2. Truoc khi chay plan/apply, kiem tra:
   - Thu muc target environment ton tai
   - `terraform.tfvars` ton tai trong target environment
   - Neu `to_env` la `prod`, yeu cau xac nhan bang cach nhap ten environment truoc khi proceed
3. Chay `terraform plan` va luu plan file
4. Hien thi summary cua plan (so resource se add/change/destroy)
5. Yeu cau xac nhan truoc khi apply (tru khi co `--auto-approve`)
6. Chay `terraform apply` voi saved plan file
7. Hien thi outputs sau apply

### Starter

```bash
#!/usr/bin/env bash
set -euo pipefail

# Usage: ./promote.sh <from_env> <to_env> [--auto-approve]
FROM_ENV="${1:-}"
TO_ENV="${2:-}"
AUTO_APPROVE="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENTS_DIR="${SCRIPT_DIR}/environments"
COMMON_TFVARS="${SCRIPT_DIR}/common.tfvars"

# --- TODO: Implement cac ham sau ---

validate_args() {
  # Kiem tra FROM_ENV va TO_ENV duoc truyen vao
  # Kiem tra FROM_ENV va TO_ENV phai la dev, staging, hoac prod
  # Kiem tra FROM_ENV != TO_ENV
  # Kiem tra thu muc environment ton tai
  echo "TODO: implement validate_args"
}

safety_check_for_prod() {
  # Neu TO_ENV = prod, yeu cau user nhap "prod" de xac nhan
  # Neu nhap sai, exit voi loi
  echo "TODO: implement safety_check_for_prod"
}

run_plan() {
  # cd vao environments/$TO_ENV
  # Chay terraform plan voi common.tfvars va terraform.tfvars
  # Luu output vao file plan (dung -out flag)
  # Parse va hien thi dong "Plan: X to add, Y to change, Z to destroy"
  echo "TODO: implement run_plan"
}

run_apply() {
  # Neu khong co --auto-approve, hoi user co muon apply khong
  # Chay terraform apply voi saved plan file
  # Hien thi terraform output sau apply
  echo "TODO: implement run_apply"
}

# Main
validate_args
safety_check_for_prod
run_plan
run_apply
```

### Expected behavior

```bash
# Promote tu dev sang staging
./promote.sh dev staging

# Output expected:
# [INFO] Promoting from dev -> staging
# [INFO] Running terraform plan for staging...
# ...
# Plan: 2 to add, 1 to change, 0 to destroy.
# [INFO] Apply the above plan to staging? (yes/no): yes
# [INFO] Applying...
# Apply complete! Resources: 2 added, 1 changed, 0 destroyed.
# [INFO] Outputs:
# ...

# Promote sang prod voi safety check
./promote.sh staging prod

# Output expected:
# [WARNING] You are about to apply to PRODUCTION environment.
# [WARNING] Type "prod" to confirm: prod
# [INFO] Running terraform plan for prod...
# ...
```

### Bonus

Them check: truoc khi promote tu staging len prod, kiem tra xem staging co `terraform plan` ra "No changes" khong (nghia la staging co state match voi code). Neu co changes chua apply tren staging, warn va yeu cau confirm.

---

## Exercise 2 - Workspace Migration (Kho, ~60 phut)

### Boi canh

Ban moi join mot team. Ho dang dung Terraform workspace cho dev va staging (chu khong phai folder-based). Co nghia la tat ca environments trong cung thu muc, phan biet bang workspace `dev` va `staging`. Sau khi tro chuyen voi team, ca team dong y chuyen sang folder-based approach vi qua nhieu incident "apply sai workspace".

Nhiem vu cua ban: migrate tu workspace-based sang folder-based **ma khong destroy va recreate bat ky resource nao**.

### Cau truc hien tai (workspace-based)

```bash
# Trong thu muc workspace-based/
terraform workspace list
# * default
#   dev
#   staging

terraform workspace show
# dev

terraform state list
# module.vpc.aws_vpc.main
# module.vpc.aws_subnet.public[0]
# ...
```

### Yeu cau

1. **Tao folder structure moi:** `environments/dev/` va `environments/staging/` voi day du config files.

2. **Khai thac state hien tai:**
   ```bash
   # Doc state cua workspace dev
   terraform workspace select dev
   terraform state pull > dev-state.json

   # Doc state cua workspace staging
   terraform workspace select staging
   terraform state pull > staging-state.json
   ```

3. **Push state sang backend moi:** Moi environment folder co backend rieng voi key moi. Can push state cu vao key moi ma khong lam mat resource mapping.
   ```bash
   # Hint: terraform state push
   # Hint: phai update state serial va lineage
   ```

4. **Verify:** Sau migration, `terraform plan` trong moi environment folder phai ra "No changes" (khong co resource nao bi tao lai hoac destroy).

5. **Cleanup:** Xoa cac workspaces cu.
   ```bash
   terraform workspace delete dev
   terraform workspace delete staging
   ```

### Huong dan state migration

```bash
# Buoc 1: Setup thu muc moi (cac environment folders)
mkdir -p environments/dev environments/staging

# Buoc 2: Copy config files
# Tao main.tf, variables.tf, outputs.tf, backend.tf, terraform.tfvars
# cho moi environment (cung content structure, khac backend key va tfvars)

# Buoc 3: Init environments moi
cd environments/dev && terraform init
cd environments/staging && terraform init

# Buoc 4: Pull state cu tu workspace
cd workspace-based/
terraform workspace select dev
terraform state pull > /tmp/dev-workspace-state.json

# Buoc 5: Push state vao folder backend moi
cd environments/dev/
# Chinh sua /tmp/dev-workspace-state.json:
# - Bump "serial" len mot gia tri cao hon (vi du: current + 1)
# - Dam bao "version" dung
terraform state push /tmp/dev-workspace-state.json

# Buoc 6: Verify - MUST be "No changes"
terraform plan -var-file="../../common.tfvars" -var-file="terraform.tfvars"
# Expected: No changes. Your infrastructure matches the configuration.

# Lap lai cho staging
```

### Cac gotcha phai chu y

- **State serial:** Phai tang `serial` khi push, Terraform reject state co serial thap hon.
- **Lineage:** `lineage` la unique ID cua state. Neu change lineage, Terraform bao loi. Giu nguyen lineage tu workspace state.
- **Resource address:** Moi resource trong state co dia chi. Neun cau truc module giong nhat, dia chi giu nguyen, `terraform plan` se ra "No changes". Neu kha cau truc, can `terraform state mv`.
- **Backup truoc khi push:** `cp /tmp/dev-workspace-state.json /tmp/dev-workspace-state.json.bak`

---

## Exercise 3 - Multi-Account AWS Strategy (Kho, ~45 phut - Thiet ke truoc, implement sau)

### Boi canh

Company ban dang scale len. Security team yeu cau: **moi environment phai nam trong AWS account rieng biet** (khong phai chi khac VPC hay folder). Ly do:

- Blast radius: loi IAM trong dev khong anh huong prod
- Billing visibility: chi phi per environment ro rang
- Compliance: prod account co audit logging dat, dev account linh hoat hon
- Phan quyen: developer co full access dev account, chi read-only prod account

Day la "AWS multi-account strategy" - industry standard cho enterprises.

### Phan 1: Thiet ke (khong can AWS account that)

Thiet ke folder structure va backend strategy cho multi-account setup:

```
Accounts:
  - Account A: dev     (ID: 111111111111)
  - Account B: staging (ID: 222222222222)
  - Account C: prod    (ID: 333333333333)

Moi account co S3 bucket rieng de chua state:
  - tf-state-111111111111 (dev state bucket)
  - tf-state-222222222222 (staging state bucket)
  - tf-state-333333333333 (prod state bucket)
```

Yeu cau thiet ke:

1. Ve folder structure (text diagram)
2. Viet `backend.tf` cho moi environment (khac bucket, khac region co the)
3. Viet `provider.tf` co su dung `assume_role` de switch sang dung account khi apply
4. Giai thich cach CI/CD se cau hinh credentials cho tung account

### Phan 2: Provider assume_role pattern

Trong multi-account, thay vi hard-code credentials, dung IAM Role Assumption:

```hcl
# environments/prod/provider.tf

provider "aws" {
  region = var.aws_region

  # Assume role trong prod account
  # CI/CD runner co permission assume sang role nay
  assume_role {
    role_arn     = "arn:aws:iam::333333333333:role/TerraformDeployRole"
    session_name = "terraform-deploy-${var.environment}"
    # external_id = var.external_id  # Them bao mat khi can
  }

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

**Viet config tuong tu cho dev va staging** nhung voi Account ID tuong ung.

### Phan 3: Tao IAM role (trong dev account that, neu co)

```hcl
# Tao TerraformDeployRole trong moi account
resource "aws_iam_role" "terraform_deploy" {
  name = "TerraformDeployRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          # Chi cho phep CI/CD account assume role nay
          AWS = "arn:aws:iam::<CICD_ACCOUNT_ID>:role/CICDRunnerRole"
        }
        # Them condition de them bao mat
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.external_id
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "terraform_deploy" {
  role       = aws_iam_role.terraform_deploy.name
  # Trong prod: custom policy chi cho phep nhung action can thiet
  # Trong dev: AdministratorAccess cho tinh linh hoat
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```

### Cau hoi phan tich

Sau khi thiet ke, tra loi:

1. S3 state bucket cua prod account co nen cho dev account read khong? Tai sao hoac tai sao khong?
2. Neu developer can xem prod state de debug, nen giai quyet bang cach nao ma van an toan?
3. Neu company co 10 microservices, moi service co 3 environments (dev/staging/prod) = 30 accounts, co nhat thiet phai 30 accounts khong? Alternative la gi?
4. AWS Organizations va Service Control Policies (SCP) giup gi trong multi-account setup?

---

## Exercise 4 - tfvars Validation Tool (Python, ~30 phut)

### Boi canh

Team ban hay gap loi "Forgot to update staging.tfvars after changing dev.tfvars". Mot teammate propose viet tool de kiem tra xem ca hai file tfvars co cung set of keys khong (gia tri co the khac, nhung keys phai giong nhau).

### Yeu cau

Viet script Python `validate-tfvars.py` nhan 2 (hoac nhieu hon) `.tfvars` file va:

1. Parse tung file (luu y: `.tfvars` la HCL, khong phai JSON, nhung co the dung regex don gian de extract keys)
2. So sanh set of top-level keys
3. Bao loi neu co key trong file A nhung khong co trong file B (hoac nguoc lai)
4. Output ro rang: file nao thieu key nao

### Starter code

```python
#!/usr/bin/env python3
"""
Validate that multiple tfvars files have consistent keys.
Usage: python validate-tfvars.py dev/terraform.tfvars staging/terraform.tfvars [prod/terraform.tfvars]
"""

import sys
import re
from pathlib import Path
from typing import Set, Dict


def parse_tfvars_keys(file_path: str) -> Set[str]:
    """
    Parse top-level keys tu tfvars file.
    Simple approach: tim tat ca "key = value" patterns o column 0.
    
    Luu y: Day la simplified parser, khong handle tat ca HCL syntax.
    Production-grade nen dung python-hcl2 library.
    """
    keys = set()
    content = Path(file_path).read_text()
    
    # TODO: Implement parsing logic
    # Hint: regex de match "identifier = " o dau dong
    # Goi y regex: r'^(\w+)\s*='
    # Phai skip comment lines (bat dau bang #)
    
    return keys


def compare_tfvars_files(files: list[str]) -> Dict[str, Set[str]]:
    """
    So sanh keys giua nhieu files.
    Return: dict mapping file -> set of keys missing in that file compared to union
    """
    # TODO: Implement comparison logic
    # 1. Parse keys tu tung file
    # 2. Tao union cua tat ca keys
    # 3. Voi moi file, tim keys co trong union nhung khong co trong file do
    pass


def main():
    if len(sys.argv) < 3:
        print("Usage: python validate-tfvars.py <file1.tfvars> <file2.tfvars> [file3.tfvars ...]")
        sys.exit(1)
    
    files = sys.argv[1:]
    
    # Kiem tra files ton tai
    for f in files:
        if not Path(f).exists():
            print(f"ERROR: File not found: {f}")
            sys.exit(1)
    
    # TODO: Goi compare_tfvars_files va hien thi ket qua
    # Neu co issues: exit voi code 1 (de dung trong CI/CD)
    # Neu clean: exit voi code 0


if __name__ == "__main__":
    main()
```

### Expected output

```bash
python validate-tfvars.py environments/dev/terraform.tfvars environments/staging/terraform.tfvars

# Neu tat ca keys match:
# [OK] All tfvars files have consistent keys.
# Files checked: environments/dev/terraform.tfvars, environments/staging/terraform.tfvars
# Keys found: environment, vpc_cidr, availability_zones, public_subnet_cidrs, private_subnet_cidrs, enable_nat_gateway, single_nat_gateway

# Neu co inconsistency:
# [ERROR] Key inconsistencies found:
# 
#   environments/staging/terraform.tfvars is MISSING:
#     - enable_flow_logs
# 
#   environments/dev/terraform.tfvars is MISSING:
#     - db_instance_class
# 
# Exit code: 1
```

### Bonus

- Them support cho `--ignore` flag de bo qua mot so keys (vi du: `--ignore=tags,owner`)
- Integrate script nay vao `promote.sh` tu Exercise 1: kiem tra tfvars consistency truoc khi promote
- Them support parse HCL object va list (complex types), khong chi scalar values

---

## Exercise 5 - Environment Config Matrix (Analysis, ~20 phut)

### Boi canh

Day la bai tap thiet ke, khong can code. Ban duoc giao nhiem vu plan Terraform structure cho mot company co:

- 3 products: `api`, `worker`, `dashboard`
- 4 environments: `dev`, `staging`, `uat`, `prod`
- 2 AWS regions: `ap-southeast-1` (primary), `ap-east-1` (DR cho prod only)
- Moi product co: VPC rieng, RDS rieng, EKS shared (chia se trong cung environment)

### Yeu cau

1. **Ve folder structure** cho toan bo setup tren. Moi product/environment/region combination phai co Terraform state rieng biet. Chi viet folder structure, khong can code.

2. **Liet ke tat ca state files** se ton tai. Format: `s3://terraform-state/<path>`. Dem tong so state files.

3. **Chia se EKS:** EKS duoc share giua `api`, `worker`, `dashboard` trong cung environment. Ai se own state file cho EKS? Lam the nao de api VPC co the reference EKS cluster trong cung environment? Viet pseudocode cho `terraform_remote_state` data source.

4. **DR strategy:** `ap-east-1` chi deploy cho prod. Thiet ke hau het code co the reuse, chi override region va co the CIDR. Goi y: co the dung layer nao trong tfvars layering cho region config?

5. **Trade-off analysis:** Voi 4 environments x 3 products = 12 environment combinations (chua tinh region va shared EKS), du thay structure nay co nen dung Terragrunt khong? Giai thich dua tren nhung gi ban hoc duoc hom nay.

---

## Ghi chu chung

- Exercise 1-2: Thuc hanh tren code that, co the chay duoc
- Exercise 3-5: Ket hop thiet ke va phan tich, hay lam truoc khi co AWS account that
- Phan 2 cua Exercise 3 (IAM role) co the lam neu ban co the tao 2 AWS account (hoac dung 2 IAM user khac nhau de simulate)
- Tat ca exercises la open-ended: khong co mot dap an duy nhat dung. Quan trong la kha nang lap luan trade-off
