# Day 29: Document — IaC Tool Comparison Reference

## Comprehensive Feature Comparison Matrix

| Feature | Terraform | OpenTofu | Pulumi | AWS CDK | CDKTF |
|---------|-----------|----------|--------|---------|-------|
| **General** |
| First release | 2014 | 2023 (fork) | 2018 | 2019 | 2020 |
| License | BSL 1.1 | MPL 2.0 | Apache 2.0 | Apache 2.0 | MPL 2.0 |
| Maintainer | HashiCorp | Linux Foundation | Pulumi Inc | AWS | HashiCorp |
| **Language** |
| Config language | HCL | HCL | TS/Py/Go/Java/C#/YAML | TS/Py/Java/Go/C# | TS/Py/Java/Go/C# |
| Type system | Limited | Limited | Full | Full | Full |
| IDE support | Good | Good | Excellent | Excellent | Excellent |
| **Infrastructure** |
| Multi-cloud | ✅ Native | ✅ Native | ✅ Supported | ❌ AWS only | ✅ (via TF providers) |
| Provider count | 3000+ | 3000+ (compatible) | 100+ native, TF bridges | AWS only | TF providers |
| K8s support | Provider | Provider | Provider | EKS constructs | Provider |
| **State** |
| State format | JSON file | JSON file | JSON (encrypted) | CloudFormation | JSON file |
| Default backend | Local file | Local file | Pulumi Cloud | AWS CFN | Local file |
| Remote backends | S3/GCS/Azure/TF Cloud | S3/GCS/Azure | Pulumi Cloud/S3/local | CloudFormation | S3/GCS/Azure |
| State locking | Via backend | Via backend | Built-in | CloudFormation | Via backend |
| Secret in state | Plaintext | Plaintext | Encrypted ✅ | AWS managed | Plaintext |
| **Operations** |
| Preview | `terraform plan` | `tofu plan` | `pulumi preview` | `cdk diff` | `cdktf diff` |
| Deploy | `terraform apply` | `tofu apply` | `pulumi up` | `cdk deploy` | `cdktf deploy` |
| Destroy | `terraform destroy` | `tofu destroy` | `pulumi destroy` | `cdk destroy` | `cdktf destroy` |
| Import | `terraform import` | `tofu import` | `pulumi import` | CFN import | `cdktf import` |
| Drift detection | Plan-based | Plan-based | Preview-based | CFN drift | Plan-based |
| **Testing** |
| Unit tests | Limited (TF test) | Limited | Native (Jest/pytest) | Native (assertions) | Native |
| Integration | Terratest (Go) | Terratest | Standard frameworks | integ-tests | Standard |
| Policy | Sentinel/OPA | OPA | CrossGuard | CFN Guard/SCP | OPA |
| **Governance** |
| RBAC | TF Cloud/Enterprise | DIY | Pulumi Cloud | IAM | DIY |
| Audit trail | TF Cloud | DIY | Pulumi Cloud | CloudTrail | DIY |
| Cost estimation | TF Cloud/Infracost | Infracost | Pulumi Cloud | AWS pricing | Infracost |
| Approval workflow | TF Cloud runs | CI/CD | Pulumi deployments | CFN change sets | CI/CD |
| **Community** |
| GitHub stars | 42k+ | 23k+ | 21k+ | 11k+ | 5k+ |
| Stack Overflow | Very large | Growing | Medium | Medium | Small |
| Hiring pool | Very large | Growing | Small-medium | Medium | Small |

---

## Decision Framework Flowchart

```
START: Chọn IaC tool cho team
│
├─ Q1: Multi-cloud là requirement?
│  ├─ YES ──────────────────────────────────────┐
│  │                                             │
│  │  ├─ Q2: Team skill?                        │
│  │  │  ├─ DevOps/Ops-heavy → TERRAFORM        │
│  │  │  ├─ Dev-heavy (TS/Py) → PULUMI          │
│  │  │  └─ Mixed → TERRAFORM (hiring pool)     │
│  │  │                                         │
│  │  └─ Q3: License concern?                   │
│  │     ├─ YES → OPENTOFU hoặc PULUMI          │
│  │     └─ NO → TERRAFORM                      │
│  │                                             │
│  └─ NO (single cloud) ───────────────────────┐│
│     │                                         ││
│     ├─ AWS?                                   ││
│     │  ├─ Deep AWS integration needed?        ││
│     │  │  ├─ YES → AWS CDK                    ││
│     │  │  └─ NO → TERRAFORM or PULUMI         ││
│     │  │                                      ││
│     │  └─ GovCloud/regulated?                 ││
│     │     ├─ YES → AWS CDK + CFN Guard        ││
│     │     └─ NO → Any tool fits               ││
│     │                                         ││
│     ├─ GCP? → TERRAFORM (best GCP provider)   ││
│     └─ Azure? → TERRAFORM or PULUMI           ││
│                                               ││
└───────────────────────────────────────────────┘│
                                                 │
Q4: Budget constraint?                           │
├─ Free only → TERRAFORM OSS / OPENTOFU / PULUMI OSS
├─ Mid budget → TF Cloud Free / Pulumi Individual
└─ Enterprise → TF Enterprise / Pulumi Business / CDK + AWS Support
```

---

## Code Comparison: Same Resource, 4 Ways

### Scenario: Create S3 Bucket with Versioning + Encryption

**Terraform:**
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-app-data-${var.environment}"
  
  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}
```

**Pulumi (TypeScript):**
```typescript
const bucket = new aws.s3.Bucket("data", {
  bucket: `my-app-data-${environment}`,
  versioning: { enabled: true },
  serverSideEncryptionConfiguration: {
    rule: {
      applyServerSideEncryptionByDefault: {
        sseAlgorithm: "aws:kms",
      },
    },
  },
  tags: {
    Environment: environment,
    ManagedBy: "pulumi",
  },
});
```

**AWS CDK (TypeScript):**
```typescript
const bucket = new s3.Bucket(this, 'Data', {
  bucketName: `my-app-data-${environment}`,
  versioned: true,
  encryption: s3.BucketEncryption.KMS_MANAGED,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
  // CDK automatically adds best-practice defaults:
  // - Block public access
  // - Enforce SSL
});
cdk.Tags.of(bucket).add('Environment', environment);
cdk.Tags.of(bucket).add('ManagedBy', 'cdk');
```

**OpenTofu:**
```hcl
# Identical to Terraform (compatible syntax)
resource "aws_s3_bucket" "data" {
  bucket = "my-app-data-${var.environment}"
  tags = {
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}
# ... same as Terraform
```

### Lines of Code Comparison

| Tool | Lines | Resources Created | Defaults Included |
|------|-------|-------------------|-------------------|
| Terraform | 22 | 3 (explicit) | Manual |
| Pulumi | 15 | 1 (combined) | Manual |
| CDK | 8 | 1 (with defaults) | Auto (public block, SSL) |
| OpenTofu | 22 | 3 (identical to TF) | Manual |

---

## Migration Guide

### Terraform → Pulumi

```bash
# Official migration tool
pulumi convert --from terraform --out pulumi-project

# Or import state
pulumi import --from terraform ./terraform.tfstate

# Steps:
# 1. Install Pulumi
# 2. Convert HCL → TypeScript/Python
# 3. Import state
# 4. Verify: pulumi preview (should show no changes)
# 5. Delete old Terraform files
# 6. Update CI/CD pipeline
```

### Terraform → OpenTofu

```bash
# Drop-in replacement (currently)
# 1. Replace terraform binary with tofu
brew install opentofu

# 2. Rename commands
tofu init    # instead of terraform init
tofu plan    # instead of terraform plan
tofu apply   # instead of terraform apply

# 3. State is compatible (no migration needed)
# 4. .tf files are compatible
# 5. Lock file: .terraform.lock.hcl → still used

# ⚠️ May diverge in future versions
```

### CDK → Terraform

```
NO official migration path!

Manual migration:
1. Export CloudFormation template: cdk synth > template.json
2. Write equivalent Terraform by hand
3. Ưu tiên Terraform `import` block cho configuration-driven import trong PR/CI; chỉ dùng `terraform import <addr> <id>` như fallback thủ công
4. Verify: `terraform plan -out=migration.tfplan`, review, rồi `terraform apply migration.tfplan`
5. Delete CDK stack (without deleting resources)

Estimated effort: 1-2 weeks per 100 resources
```

---

## Vendor Lock-in Assessment

| Tool | Lock-in Level | Lock-in Type | Mitigation |
|------|--------------|--------------|------------|
| Terraform | LOW | HCL syntax | OpenTofu fork, providers portable |
| OpenTofu | VERY LOW | Same as TF | Community-driven, MPL license |
| Pulumi | LOW-MEDIUM | SDK API + Pulumi Cloud default | Self-managed state option |
| CDK | HIGH | AWS CloudFormation | Only mitigated by CDKTF |
| CDKTF | LOW-MEDIUM | TF backend, but CDKTF API | Can drop to raw TF |

### Lock-in Risk Matrix

```
             LOW risk ◄──────────────────────── HIGH risk
             │                                         │
Cloud lock   │ TF/OT ─── Pulumi ──── CDKTF ──── CDK  │
             │                                         │
Tool lock    │ OT ─── TF ─── Pulumi ──── CDK ──── CDKTF│
             │                                         │
State lock   │ TF/OT ─── CDKTF ─── Pulumi ──── CDK   │
             │                                         │
```

---

## Cost Comparison (Team of 10 Engineers)

| Cost Category | Terraform OSS | TF Cloud (Team) | Pulumi (Team) | CDK |
|---------------|--------------|-----------------|---------------|-----|
| Tool license | Free | ~$70/user/mo | ~$50/user/mo | Free |
| State storage | ~$1/mo (S3) | Included | Included | Free (CFN) |
| Training | $2-5K | $2-5K | $3-7K | $2-5K |
| Hiring premium | Baseline | Baseline | +10-20% | Baseline |
| Annual total | ~$1K | ~$8.4K | ~$6K + hiring | ~$1K |

*Note: Prices approximate, check official pricing pages for current rates.*

---

## Quick Start Commands

### Terraform

```bash
# Install
brew install terraform  # macOS
# or: choco install terraform  # Windows

# New project
mkdir my-infra && cd my-infra
cat > main.tf << 'EOF'
terraform {
  required_providers {
    local = { source = "hashicorp/local", version = "~> 2.4" }
  }
}
resource "local_file" "hello" {
  filename = "/tmp/hello.txt"
  content  = "Hello Terraform!"
}
EOF

terraform init && terraform apply -auto-approve
cat /tmp/hello.txt
terraform destroy -auto-approve
```

### Pulumi

```bash
# Install
curl -fsSL https://get.pulumi.com | sh

# New project (TypeScript)
mkdir my-infra && cd my-infra
pulumi new typescript --yes
npm install @pulumi/docker

# Edit index.ts, then:
pulumi up
pulumi destroy
```

### AWS CDK

```bash
# Install
npm install -g aws-cdk

# New project (TypeScript)
mkdir my-infra && cd my-infra
cdk init app --language typescript

# Edit lib/my-infra-stack.ts, then:
cdk synth    # Generate CloudFormation
cdk diff     # Preview changes
cdk deploy   # Deploy
cdk destroy  # Cleanup
```

### OpenTofu

```bash
# Install
brew install opentofu  # macOS

# Same workflow as Terraform
tofu init
tofu plan
tofu apply
tofu destroy
```

