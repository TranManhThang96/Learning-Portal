# Day 26: Document — Infrastructure as Code Reference

## IaC Tool Landscape Comparison

| Tool | Type | Language | State | Agent | Best For |
|------|------|----------|-------|-------|----------|
| Terraform | Provisioning | HCL | Remote file | Agentless | Multi-cloud infrastructure |
| Pulumi | Provisioning | TS/Python/Go/Java | Cloud service | Agentless | Dev-centric teams |
| AWS CDK | Provisioning | TS/Python/Java | CloudFormation | Agentless | AWS-only shops |
| Crossplane | Provisioning | YAML (K8s CRDs) | etcd (K8s) | Controller | K8s-native infra |
| Ansible | Config Mgmt | YAML | Stateless | Agentless (SSH) | Server configuration |
| Puppet | Config Mgmt | Puppet DSL | PuppetDB | Agent | Large fleet management |
| Chef | Config Mgmt | Ruby DSL | Chef Server | Agent | Complex config logic |
| SaltStack | Config Mgmt | YAML/Python | Salt Master | Agent/Agentless | Event-driven automation |

---

## Declarative vs Imperative Comparison Matrix

| Aspect | Declarative | Imperative |
|--------|------------|------------|
| Mô tả | WHAT (trạng thái cuối) | HOW (từng bước) |
| Idempotency | Tự động | Phải tự đảm bảo |
| State tracking | Tool quản lý | Tự quản lý |
| Parallelism | Tool tối ưu tự động | Phải code explicit |
| Error recovery | Retry từ state hiện tại | Phải handle từng step |
| Learning curve | Cần học DSL/syntax mới | Dùng ngôn ngữ quen thuộc |
| Flexibility | Giới hạn bởi DSL | Không giới hạn |
| Debugging | Xem plan/state/diff | Debug script line by line |
| Ví dụ | Terraform, K8s manifests, SQL DDL | Bash scripts, AWS CLI, Ansible ad-hoc |
| Analogy | React component | jQuery manipulation |

---

## IaC Workflow Decision Tree

```
Cần thay đổi infrastructure?
│
├── Đã có trong IaC code?
│   ├── CÓ → Sửa code → PR → Review → Plan → Apply
│   └── KHÔNG → Import resource → Viết code → PR → ...
│
├── Resource type?
│   ├── Networking (VPC, subnet, SG) → Blast radius LỚN → Extra review
│   ├── Compute (EC2, EKS) → Blast radius TB → Standard review
│   ├── Database (RDS) → Data at risk → Senior review + backup verify
│   └── Application (S3, SQS) → Blast radius NHỎ → Standard review
│
├── Environment?
│   ├── Dev → Auto-apply after merge OK
│   ├── Staging → Manual approve, auto-apply
│   └── Prod → 2 approvals + manual apply
│
└── Emergency?
    ├── CÓ → Apply direct + retroactive PR within 24h
    └── KHÔNG → Standard PR workflow
```

---

## State Management Cheat Sheet

### State Backend Options

| Backend | Locking | Encryption | Cost | Best For |
|---------|---------|-----------|------|----------|
| Local file | ❌ | ❌ | Free | Solo dev, learning |
| AWS S3 + DynamoDB | ✅ | ✅ (SSE) | ~$1/month | AWS teams |
| GCS | ✅ (built-in) | ✅ | ~$1/month | GCP teams |
| Azure Blob | ✅ (lease) | ✅ | ~$1/month | Azure teams |
| Terraform Cloud | ✅ | ✅ | Free tier available | Any team |
| GitLab Managed | ✅ | ✅ | Included | GitLab users |
| Consul | ✅ | ✅ | Self-hosted | On-premise |

### State Split Strategy

```
# BY ENVIRONMENT (minimum)
states/
├── dev.tfstate
├── staging.tfstate
└── prod.tfstate

# BY ENVIRONMENT + LAYER (recommended)
states/
├── dev/
│   ├── networking.tfstate
│   ├── compute.tfstate
│   └── application.tfstate
├── staging/
│   └── ...
└── prod/
    ├── networking.tfstate      # Ít thay đổi, blast radius lớn
    ├── kubernetes.tfstate      # Thay đổi monthly
    ├── database.tfstate        # Critical, ít thay đổi
    ├── application.tfstate     # Thay đổi thường xuyên
    └── global.tfstate          # DNS, CDN, IAM
```

### State Operations Reference

| Operation | Command | Khi nào dùng | Risk |
|-----------|---------|--------------|------|
| List resources | `terraform state list` | Kiểm tra state | LOW |
| Show resource | `terraform state show <addr>` | Debug resource | LOW |
| Remove from state | `terraform state rm <addr>` | Unmanage resource | MEDIUM |
| Move resource | `terraform state mv <from> <to>` | Refactor code | MEDIUM |
| Import resource | `import` block + `terraform plan` | Adopt existing resource qua PR/CI | MEDIUM |
| Import thủ công dự phòng | `terraform import <addr> <id>` | Break-glass hoặc migration thủ công | MEDIUM |
| Pull remote state | `terraform state pull` | Backup/inspect | LOW |
| Push state | `terraform state push` | Recovery | HIGH |
| Replace provider | `terraform state replace-provider` | Provider migration | HIGH |

---

## IaC PR Review Checklist (Printable)

- [ ] `terraform plan -out=<file>` output reviewed nếu apply sau approval
- [ ] Apply dùng đúng saved plan đã review: `terraform apply <file>`
- [ ] No unexpected `destroy` or `replace` actions
- [ ] Resource naming follows convention: `{project}-{env}-{resource}`
- [ ] Tags present: `Environment`, `Team`, `ManagedBy`, `CostCenter`
- [ ] Dependencies explicit when needed (`depends_on`)
- [ ] Outputs defined for cross-module references
- [ ] Variables have descriptions and validation

### Security 🔒
- [ ] No hardcoded credentials/secrets in code
- [ ] No hardcoded credentials in `*.tfvars` committed to Git
- [ ] Encryption at rest enabled (databases, S3, EBS)
- [ ] Network access restricted (no `0.0.0.0/0` for non-public ports)
- [ ] IAM policies follow least privilege
- [ ] Security groups have minimal ingress rules
- [ ] Sensitive outputs marked as `sensitive = true`

### Reliability 🛡️
- [ ] High availability for production (multi-AZ)
- [ ] Backup configured with appropriate retention
- [ ] `lifecycle { prevent_destroy = true }` for critical resources
- [ ] Health checks / monitoring mentioned
- [ ] Rollback plan documented in PR description

### Cost 💰
- [ ] Instance sizes appropriate for environment (dev < staging < prod)
- [ ] Auto-scaling configured with reasonable min/max
- [ ] Storage sizes reasonable (not over-provisioned)
- [ ] Consider reserved instances / savings plans notation
- [ ] No forgotten resources (all resources have purpose)

### Operations 🔧
- [ ] DNS records correct
- [ ] Networking routes logical
- [ ] Logging enabled
- [ ] Monitoring/alerting considered
- [ ] State impact understood (add/change/destroy counts)

### Blast Radius 💥
- [ ] Changes scoped to minimum necessary resources
- [ ] No cross-cutting changes (networking + database in same PR)
- [ ] Downtime impact assessed and documented
- [ ] Affected environments clearly listed
- [ ] Breaking changes communicated to stakeholders

---

## Drift Detection Patterns

### Manual Drift Check

```bash
# Check drift cho specific state
terraform plan -detailed-exitcode
# Exit code 0 = no drift
# Exit code 2 = drift detected

# Check tất cả states
for env in dev staging prod; do
  echo "=== Checking $env ==="
  cd environments/$env
  terraform plan -detailed-exitcode
  cd ../..
done
```

### Automated Drift Detection (CI Schedule)

```yaml
# .github/workflows/drift-check.yml
name: Drift Detection
on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am
  workflow_dispatch: {}

jobs:
  drift-check:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, prod]
        layer: [networking, kubernetes, database, application]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3

      - name: Terraform Init
        run: terraform init
        working-directory: environments/${{ matrix.environment }}/${{ matrix.layer }}

      - name: Drift Check
        id: plan
        run: |
          terraform plan -detailed-exitcode -no-color 2>&1 | tee plan.txt
          echo "exitcode=$?" >> $GITHUB_OUTPUT
        working-directory: environments/${{ matrix.environment }}/${{ matrix.layer }}
        continue-on-error: true

      - name: Create Issue on Drift
        if: steps.plan.outputs.exitcode == '2'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Drift detected: ${{ matrix.environment }}/${{ matrix.layer }}`,
              body: `Drift detected in ${{ matrix.environment }}/${{ matrix.layer }}.\n\nCheck plan output in workflow run.`,
              labels: ['drift', 'infrastructure']
            })
```

---

## IaC Maturity Model

| Level | Tên | Đặc điểm | State Management | Review Process |
|-------|-----|-----------|-----------------|----------------|
| 0 | ClickOps | Console clicks, no code | None | None |
| 1 | Script | Bash/Python scripts | Manual tracking | Informal |
| 2 | IaC Basic | Terraform/Pulumi, local state | Local file | PR review |
| 3 | IaC Collaborative | Remote state, locking | S3/GCS + lock | PR + plan review |
| 4 | IaC Governed | Policy-as-code, drift detection | Terraform Cloud | PR + plan + policy |
| 5 | IaC Platform | Self-service, modules, automation | Platform service | Automated + human |

### Self-Assessment

```markdown
Đánh giá team hiện tại:

□ Level 0: Tất cả infrastructure tạo bằng console/CLI manual
□ Level 1: Có scripts nhưng không version control, không idempotent
□ Level 2: Dùng Terraform/Pulumi, state ở local, 1 người manage
□ Level 3: Remote state, CI/CD pipeline, team collaboration
□ Level 4: Policy checks, drift detection, cost gates, audit trail
□ Level 5: Self-service portal, module marketplace, full automation

Target: Hầu hết teams nên aim cho Level 3-4 trong 3-6 tháng.
```

---

## Common IaC Terminology Glossary

| Term | Định nghĩa | Ví dụ |
|------|-----------|-------|
| **Desired State** | Trạng thái infrastructure mong muốn, mô tả trong code | `instance_type = "t3.medium"` |
| **Actual State** | Trạng thái thực tế trên cloud/infra | EC2 instance đang chạy t3.large |
| **Drift** | Chênh lệch giữa desired state và actual state | Manual resize → code và cloud khác nhau |
| **Reconciliation** | Quá trình đưa actual state về desired state | `terraform apply` |
| **Idempotency** | Chạy nhiều lần, kết quả như nhau | Apply 2 lần → không thay đổi |
| **Plan** | Preview changes trước khi apply | `terraform plan` output |
| **State** | File lưu mapping giữa code và cloud resources | `terraform.tfstate` |
| **State Locking** | Ngăn nhiều người modify state cùng lúc | DynamoDB lock table |
| **Remote State** | State lưu ở shared location (không local) | S3 bucket |
| **Module** | Reusable package of IaC code | `module "vpc" { ... }` |
| **Provider** | Plugin kết nối IaC tool với cloud API | `provider "aws" { ... }` |
| **Backend** | Nơi lưu state file | S3, GCS, Terraform Cloud |
| **Blast Radius** | Phạm vi ảnh hưởng nếu thay đổi gây lỗi | VPC change → ảnh hưởng toàn bộ |
| **Import** | Đưa existing resource vào IaC management | `import { to = aws_vpc.main, id = "vpc-xxx" }`; fallback thủ công: `terraform import aws_vpc.main vpc-xxx` |
| **Destroy** | Xóa resource được quản lý bởi IaC | `terraform destroy` |

