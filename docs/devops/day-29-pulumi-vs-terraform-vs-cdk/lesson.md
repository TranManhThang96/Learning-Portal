# Day 29: Pulumi vs Terraform vs CDK

## 1. Mục tiêu bài học

Sau bài học này, bạn sẽ:

1. So sánh được **Terraform**, **Pulumi**, **AWS CDK** trên ít nhất 10 tiêu chí: language, state, testing, ecosystem, governance, cost.
2. Giải thích được trade-off giữa **DSL** (HCL) và **general-purpose language** (TypeScript/Python/Go) cho IaC.
3. Viết được cùng một infrastructure bằng cả 3 tools và nhận diện ưu/nhược điểm mỗi cách.
4. Đưa ra được **decision matrix** chọn IaC tool phù hợp cho 3 scenarios: startup, mid-size SaaS, enterprise regulated.
5. Đánh giá được rủi ro **migration** và **vendor lock-in** khi chọn IaC tool.

---

## 2. Bối cảnh & Động lực

### Vì sao cần biết nhiều IaC tools?

Day 27-28 bạn đã deep dive vào Terraform — tool phổ biến nhất. Nhưng Terraform không phải lựa chọn duy nhất, và không phải lúc nào cũng là lựa chọn tốt nhất.

**Câu hỏi thực tế mà team engineering phải trả lời:**

- Team toàn TypeScript developer → học HCL có đáng không?
- Cần test infrastructure code bằng unit test → Terraform test ecosystem đủ chưa?
- Enterprise cần governance + policy + audit → tool nào hỗ trợ tốt nhất?
- AWS-only shop → dùng CDK native có lợi gì?

### IaC Evolution Timeline

```
2006 ─── AWS CloudFormation (JSON/YAML, AWS-only)
2011 ─── Ansible (YAML, config management)
2013 ─── Docker (container image as code)
2014 ─── Terraform (HCL, multi-cloud)
2015 ─── AWS CDK v0 (internal)
2018 ─── Pulumi (general-purpose languages)
2019 ─── AWS CDK GA (TypeScript/Python/Java/Go)
2020 ─── Terraform CDK (use languages with TF backend)
2023 ─── Terraform BSL license change → OpenTofu fork
2024 ─── Wing, SST, và nhiều alternatives khác
```

---

## 3. Kiến thức nền tảng

### Hai triết lý IaC

**DSL-first (Domain Specific Language):**
- Terraform (HCL), CloudFormation (YAML/JSON), Ansible (YAML)
- Ngôn ngữ thiết kế riêng cho infrastructure
- Giới hạn cố ý → dễ review, dễ govern, ít bug logic

**GPL-first (General Purpose Language):**
- Pulumi (TypeScript, Python, Go, Java, C#)
- AWS CDK (TypeScript, Python, Java, Go, C#)
- Dùng ngôn ngữ lập trình quen thuộc
- Mạnh mẽ hơn → nhưng cũng dễ phức tạp hơn

### Analogy

```
DSL = SQL
  → Thiết kế cho 1 việc (query data)
  → Ai cũng đọc được
  → Không thể viết business logic phức tạp
  → Rất khó viết sai cách nguy hiểm

GPL = Python
  → Làm được mọi thứ
  → Cần skill lập trình
  → Có thể viết beautiful code hoặc spaghetti code
  → Cần discipline để giữ clean
```

---

## 4. Deep Dive

### Terraform

```
┌──────────────────────────────────────────┐
│              TERRAFORM                    │
│                                          │
│  Language: HCL (HashiCorp Config Lang)   │
│  State:    terraform.tfstate (JSON)      │
│  Backend:  S3, GCS, TF Cloud, etc.      │
│  Providers: 3000+ (registry.terraform.io)│
│  License:  BSL 1.1 (since Aug 2023)     │
│  Fork:     OpenTofu (MPL 2.0)           │
│                                          │
│  Strengths:                              │
│  ✅ Largest ecosystem & community        │
│  ✅ Multi-cloud native                   │
│  ✅ Mature state management              │
│  ✅ Extensive documentation              │
│  ✅ Huge hiring pool                     │
│                                          │
│  Weaknesses:                             │
│  ❌ HCL learning curve for developers    │
│  ❌ Limited testing capabilities         │
│  ❌ No real programming constructs       │
│  ❌ BSL license concerns                 │
│  ❌ State management complexity          │
└──────────────────────────────────────────┘
```

### Pulumi

```
┌──────────────────────────────────────────┐
│              PULUMI                       │
│                                          │
│  Languages: TypeScript, Python, Go,      │
│             Java, C#, YAML               │
│  State:     Pulumi Cloud (default),      │
│             S3, local file               │
│  Providers: 100+ (many bridged from TF)  │
│  License:   Apache 2.0                   │
│                                          │
│  Strengths:                              │
│  ✅ Real programming languages           │
│  ✅ Full type system & IDE support       │
│  ✅ Standard testing frameworks          │
│  ✅ Familiar for developers              │
│  ✅ Apache 2.0 license                   │
│  ✅ Component model for abstraction      │
│                                          │
│  Weaknesses:                             │
│  ❌ Smaller community than Terraform     │
│  ❌ Fewer native providers               │
│  ❌ Can write overly complex code        │
│  ❌ Pulumi Cloud default = vendor risk   │
│  ❌ Hiring pool smaller                  │
└──────────────────────────────────────────┘
```

### AWS CDK

```
┌──────────────────────────────────────────┐
│              AWS CDK                      │
│                                          │
│  Languages: TypeScript, Python, Java,    │
│             Go, C#                       │
│  State:     CloudFormation stack         │
│  Backend:   AWS CloudFormation (only)    │
│  Constructs: L1 (raw), L2 (opinionated),│
│              L3 (patterns)               │
│  License:   Apache 2.0                   │
│                                          │
│  Strengths:                              │
│  ✅ Deep AWS integration                 │
│  ✅ High-level constructs (L3)           │
│  ✅ Full programming language            │
│  ✅ AWS-maintained, always up-to-date    │
│  ✅ CloudFormation drift detection       │
│                                          │
│  Weaknesses:                             │
│  ❌ AWS-ONLY (no multi-cloud)            │
│  ❌ CloudFormation limits (500 resources)│
│  ❌ Vendor lock-in                       │
│  ❌ Generated CFN templates unreadable   │
│  ❌ Slower adoption outside AWS shops    │
└──────────────────────────────────────────┘
```

### Architecture Comparison

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  TERRAFORM  │     │   PULUMI    │     │   AWS CDK   │
│             │     │             │     │             │
│  .tf (HCL)  │     │  .ts/.py/.go│     │  .ts/.py    │
│      │      │     │      │      │     │      │      │
│      ▼      │     │      ▼      │     │      ▼      │
│  TF Core    │     │  Pulumi SDK │     │  CDK Core   │
│  (plan/diff)│     │  (plan/diff)│     │  (synth)    │
│      │      │     │      │      │     │      │      │
│      ▼      │     │      ▼      │     │      ▼      │
│  Provider   │     │  Provider   │     │  CloudFmt   │
│  Plugins    │     │  (bridged   │     │  Template   │
│  (gRPC)     │     │   from TF)  │     │  (JSON)     │
│      │      │     │      │      │     │      │      │
│      ▼      │     │      ▼      │     │      ▼      │
│  Cloud APIs │     │  Cloud APIs │     │  CloudFmt   │
│  (direct)   │     │  (direct)   │     │  Service    │
│             │     │             │     │      │      │
│             │     │             │     │      ▼      │
│             │     │             │     │  Cloud APIs │
└─────────────┘     └─────────────┘     └─────────────┘

State storage:       State storage:       State storage:
- .tfstate file     - Pulumi Cloud       - CloudFormation 
- S3/GCS/TF Cloud   - S3/local           - (managed by AWS)
```

### Same Infrastructure, 3 Ways

**Scenario**: Tạo Docker container NGINX exposed port 8080.

**Terraform (HCL):**
```hcl
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

resource "docker_image" "nginx" {
  name = "nginx:alpine"
}

resource "docker_container" "web" {
  name  = "web-server"
  image = docker_image.nginx.image_id

  ports {
    internal = 80
    external = 8080
  }
}

output "url" {
  value = "http://localhost:8080"
}
```

**Pulumi (TypeScript):**
```typescript
import * as docker from "@pulumi/docker";

const image = new docker.RemoteImage("nginx", {
  name: "nginx:alpine",
});

const container = new docker.Container("web", {
  name: "web-server",
  image: image.imageId,
  ports: [{
    internal: 80,
    external: 8080,
  }],
});

export const url = "http://localhost:8080";
export const containerId = container.id;
```

**AWS CDK (TypeScript) — chỉ cho AWS resources:**
```typescript
import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';

export class WebStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string) {
    super(scope, id);

    new ecsPatterns.ApplicationLoadBalancedFargateService(this, 'Web', {
      taskImageOptions: {
        image: ecs.ContainerImage.fromRegistry('nginx:alpine'),
      },
      publicLoadBalancer: true,
    });
  }
}

// CDK tự tạo: VPC, ECS cluster, ALB, security groups,
// IAM roles, CloudWatch logs — ~30 CloudFormation resources
// từ 10 dòng code
```

---

## 5. Trade-offs & Best Practices ⭐

### Comprehensive Comparison Matrix

| Criteria | Terraform | Pulumi | AWS CDK |
|----------|-----------|--------|---------|
| **Language** | HCL (DSL) | TS/Py/Go/Java/C# | TS/Py/Go/Java/C# |
| **Multi-cloud** | ✅ Native | ✅ Supported | ❌ AWS only |
| **State management** | Remote file (S3/GCS) | Pulumi Cloud/S3 | CloudFormation |
| **State visibility** | JSON file, inspectable | JSON via API | CFN console |
| **Provider ecosystem** | 3000+ providers | 100+ (many TF bridges) | AWS services only |
| **Learning curve (DevOps)** | Medium | Low | Low-Medium |
| **Learning curve (Dev)** | Medium-High | Low | Low |
| **IDE support** | Good (TF extension) | Excellent (native lang) | Excellent (native lang) |
| **Type safety** | Limited (validation) | Full type system | Full type system |
| **Testing** | Terratest (Go), plan check | Standard test frameworks | CDK assertions, jest |
| **Code reuse** | Modules (registry) | Components (npm/pip) | Constructs (npm/pip) |
| **Abstraction level** | Low-medium | Medium-high | High (L3 constructs) |
| **Policy as code** | Sentinel, OPA | CrossGuard | CloudFormation Guard |
| **Drift detection** | Plan (manual/CI) | Preview | CFN drift detection |
| **Governance** | TF Cloud/Enterprise | Pulumi Cloud | AWS Organizations |
| **Cost (tool)** | Free (OSS), paid cloud | Free (OSS), paid cloud | Free (AWS service) |
| **License** | BSL 1.1 | Apache 2.0 | Apache 2.0 |
| **Community size** | Very large | Growing | Large (AWS users) |
| **Hiring pool** | Very large | Small-medium | Medium |
| **Maturity** | Very mature (2014) | Mature (2018) | Mature (2019) |
| **Lock-in risk** | Low (multi-cloud) | Low-medium | High (AWS only) |

### Decision Framework

```
Chọn IaC tool: START
│
├── Multi-cloud bắt buộc?
│   ├── CÓ → Terraform hoặc Pulumi
│   │   ├── Team chủ yếu là Ops/DevOps? → Terraform
│   │   └── Team chủ yếu là Developers? → Pulumi
│   │
│   └── KHÔNG (single cloud)
│       ├── AWS? → CDK hoặc Terraform hoặc Pulumi
│       │   ├── Deep AWS integration cần? → CDK
│       │   ├── Team biết Terraform? → Terraform
│       │   └── Team muốn TypeScript? → Pulumi hoặc CDK
│       ├── GCP? → Terraform hoặc Pulumi
│       └── Azure? → Terraform hoặc Pulumi
│
├── Team skill?
│   ├── Strong DevOps/Ops → Terraform (HCL OK, ecosystem lớn)
│   ├── Strong Dev (TS/Py) → Pulumi (ngôn ngữ quen)
│   └── Mixed → Terraform (hiring pool lớn nhất)
│
├── Testing requirement?
│   ├── Standard unit tests → Pulumi/CDK (native test frameworks)
│   └── Plan-based validation → Terraform (plan check + Terratest)
│
└── Governance requirement?
    ├── Enterprise → Terraform Enterprise / Pulumi Enterprise
    ├── AWS-native → CDK + CloudFormation + AWS Organizations
    └── Startup → Any (complexity thấp)
```

### Recommendations theo Scenario

#### Scenario 1: Startup — 5 Engineers

```
Recommendation: Terraform

Lý do:
✅ Largest hiring pool — dễ hire DevOps
✅ Massive community — mọi vấn đề đều có answer
✅ Simple to start — local state, ít ceremony
✅ Multi-cloud option — không bị lock-in sớm
✅ Many ready-made modules (terraform-aws-modules)

Alternative: Pulumi nếu team toàn TypeScript developers
  → Faster onboarding, nhưng smaller community

KHÔNG chọn CDK:
  → Lock-in AWS quá sớm
  → Startup có thể đổi cloud
```

#### Scenario 2: Mid-size SaaS — 30 Engineers

```
Recommendation: Terraform + Terragrunt (hoặc Pulumi nếu dev-heavy)

Terraform path:
✅ Proven at scale
✅ Terragrunt giảm duplication
✅ Module registry cho standardization
✅ OPA/Sentinel cho policy
✅ Many CI/CD integrations

Pulumi path (nếu team >70% developers):
✅ TypeScript/Python familiar
✅ Better testing story
✅ Component model cho abstraction
✅ Pulumi Cloud cho governance

Decision factor: DevOps team size
  → ≥ 3 dedicated DevOps → Terraform
  → < 3 DevOps, dev-owned infra → Pulumi
```

#### Scenario 3: Enterprise Regulated — 200+ Engineers

```
Recommendation: Terraform Enterprise + Sentinel

Lý do:
✅ Proven enterprise track record
✅ Sentinel policies cho compliance
✅ Private module registry
✅ SSO, audit logging, cost estimation
✅ Largest talent pool
✅ Most consultants/partners available

Alternative: CDK nếu 100% AWS + strong AWS relationship
  → AWS Enterprise Support + CFN
  → Organizations, Control Tower, Service Catalog

Consideration: BSL license
  → Enterprise legal team nên review
  → OpenTofu là backup plan nếu license concern
```

---

## 6. Performance & Scalability ⭐

### Performance Comparison

| Metric | Terraform | Pulumi | CDK |
|--------|-----------|--------|-----|
| Init time (fresh) | 5-30s (download providers) | 2-10s (npm install) | 2-10s (npm install) |
| Plan time (100 res) | 30-60s | 20-40s | 10-20s (synth) + CFN |
| Apply time | Direct API calls | Direct API calls | CFN orchestration (slower) |
| Parallelism | Configurable (default 10) | Automatic | CFN manages |
| Large state | Degrades >500 resources | Similar | CFN limit: 500/stack |

### Scaling Challenges per Tool

**Terraform:**
- State file grows → plan slows → split state.
- Provider version management across teams.
- HCL becomes verbose for complex logic → Terragrunt.

**Pulumi:**
- npm/pip dependency management overhead.
- Code complexity can grow unchecked.
- Pulumi Cloud dependency for state (unless self-managed).

**CDK:**
- CloudFormation 500 resource limit per stack → nested stacks.
- Synth time grows with construct complexity.
- Generated CFN templates can be huge and hard to debug.

---

## 7. Security & Reliability Considerations

### State Security per Tool

| Tool | State Location | Encryption | Secret Handling |
|------|---------------|-----------|-----------------|
| Terraform | S3/GCS/TF Cloud | SSE, KMS | Marked sensitive, still in state |
| Pulumi | Pulumi Cloud/S3 | Encrypted by default | Pulumi secrets (encrypted in state) |
| CDK | CloudFormation | AWS managed | SSM/Secrets Manager native |

**Pulumi advantage**: Secrets encrypted BY DEFAULT in state — Terraform stores sensitive values in plaintext state.

```typescript
// Pulumi: secrets encrypted automatically
const dbPassword = new pulumi.Config().requireSecret("dbPassword");
// → Encrypted in state file, never plaintext
```

```hcl
# Terraform: sensitive values in state as plaintext
variable "db_password" {
  sensitive = true  # Hidden from output, but STILL in state file
}
```

### Governance Comparison

| Feature | Terraform | Pulumi | CDK |
|---------|-----------|--------|-----|
| Policy as Code | Sentinel, OPA | CrossGuard | CFN Guard, SCP |
| RBAC | TF Cloud | Pulumi Cloud | IAM |
| Audit trail | TF Cloud logs | Pulumi Cloud logs | CloudTrail |
| Cost estimation | TF Cloud, Infracost | Pulumi Cloud | AWS Cost Explorer |
| Approval workflow | TF Cloud runs | Pulumi deployments | CFN change sets |

---

## 8. Hands-on Example

### Code Comparison: Local File Management

Cùng 1 task — quản lý config files — viết bằng cả Terraform và Pulumi.

#### Terraform Version

```bash
mkdir -p iac-compare/terraform && cd iac-compare/terraform
```

**main.tf:**
```hcl
terraform {
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "services" {
  type = map(object({
    port     = number
    replicas = number
  }))
  default = {
    api = {
      port     = 8080
      replicas = 2
    }
    worker = {
      port     = 0
      replicas = 3
    }
  }
}

locals {
  base_dir = "/tmp/iac-compare/terraform"
}

resource "local_file" "service_config" {
  for_each = var.services

  filename = "${local.base_dir}/${each.key}/config.json"
  content = jsonencode({
    name        = each.key
    environment = var.environment
    port        = each.value.port
    replicas    = each.value.replicas
    version     = "1.0.0"
  })
}

resource "local_file" "main_config" {
  filename = "${local.base_dir}/main.json"
  content = jsonencode({
    environment = var.environment
    services    = [for name, config in var.services : name]
    generated   = timestamp()
  })
}

output "config_files" {
  value = [for f in local_file.service_config : f.filename]
}
```

```bash
terraform init && terraform apply -auto-approve
cat /tmp/iac-compare/terraform/api/config.json | python3 -m json.tool
terraform destroy -auto-approve
```

#### Pulumi Version (TypeScript)

Nếu bạn muốn thử Pulumi:

```bash
# Install Pulumi
curl -fsSL https://get.pulumi.com | sh

# Tạo project
mkdir -p iac-compare/pulumi && cd iac-compare/pulumi
pulumi new typescript --name iac-compare --yes

# Install local provider
npm install @pulumi/command
```

**index.ts:**
```typescript
import * as pulumi from "@pulumi/pulumi";
import * as fs from "fs";
import * as path from "path";

interface ServiceConfig {
  port: number;
  replicas: number;
}

const config = new pulumi.Config();
const environment = config.get("environment") || "dev";

const services: Record<string, ServiceConfig> = {
  api: { port: 8080, replicas: 2 },
  worker: { port: 0, replicas: 3 },
};

const baseDir = "/tmp/iac-compare/pulumi";

// Type-safe configuration generation
Object.entries(services).forEach(([name, svc]) => {
  const configContent = JSON.stringify({
    name,
    environment,
    port: svc.port,
    replicas: svc.replicas,
    version: "1.0.0",
  }, null, 2);

  const dir = path.join(baseDir, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "config.json"), configContent);
});

// Main config
const mainConfig = JSON.stringify({
  environment,
  services: Object.keys(services),
  generated: new Date().toISOString(),
}, null, 2);

fs.mkdirSync(baseDir, { recursive: true });
fs.writeFileSync(path.join(baseDir, "main.json"), mainConfig);

export const configFiles = Object.keys(services).map(
  name => path.join(baseDir, name, "config.json")
);
```

#### So sánh Code

| Aspect | Terraform | Pulumi (TypeScript) |
|--------|-----------|---------------------|
| Lines of code | ~45 | ~40 |
| Type safety | Runtime validation | Compile-time types |
| IDE experience | TF extension | Full TypeScript support |
| Loop syntax | `for_each` (HCL specific) | Standard `forEach` |
| JSON handling | `jsonencode()` | `JSON.stringify()` |
| Readability | Clear for infra | Clear for developers |
| Testing | Plan check | Jest/Mocha |

### Decision Matrix Exercise

Tạo file `decision-matrix.md`:

```markdown
# IaC Tool Decision Matrix

Chấm điểm 1-5 cho mỗi tiêu chí (5 = tốt nhất):

## Scenario 1: Startup 5 Engineers (AWS, TypeScript stack)

| Criteria (Weight) | Terraform | Pulumi | CDK |
|-------------------|-----------|--------|-----|
| Learning curve (20%) | 3 | 5 | 4 |
| Community/support (20%) | 5 | 3 | 4 |
| Multi-cloud (10%) | 5 | 5 | 1 |
| Developer experience (15%) | 3 | 5 | 5 |
| Hiring ease (15%) | 5 | 2 | 3 |
| Cost (10%) | 5 | 4 | 5 |
| Governance features (10%) | 3 | 3 | 4 |
| **Weighted Score** | **4.0** | **3.8** | **3.6** |

→ Recommendation: Terraform (balanced) hoặc Pulumi (dev-focused)

## Scenario 2: Mid-size SaaS 30 Engineers (Multi-cloud)

| Criteria (Weight) | Terraform | Pulumi | CDK |
|-------------------|-----------|--------|-----|
| Learning curve (10%) | 3 | 4 | 4 |
| Community/support (15%) | 5 | 3 | 3 |
| Multi-cloud (25%) | 5 | 5 | 1 |
| Developer experience (10%) | 3 | 5 | 5 |
| Hiring ease (15%) | 5 | 2 | 2 |
| Cost (10%) | 4 | 3 | 5 |
| Governance features (15%) | 4 | 4 | 3 |
| **Weighted Score** | **4.4** | **3.6** | **2.8** |

→ Recommendation: Terraform (multi-cloud + hiring)

## Scenario 3: Enterprise Regulated 200+ Engineers (AWS primary)

| Criteria (Weight) | Terraform | Pulumi | CDK |
|-------------------|-----------|--------|-----|
| Learning curve (5%) | 3 | 4 | 4 |
| Community/support (10%) | 5 | 3 | 5 |
| Multi-cloud (10%) | 5 | 5 | 1 |
| Developer experience (10%) | 3 | 5 | 5 |
| Hiring ease (10%) | 5 | 2 | 3 |
| Cost (10%) | 3 | 3 | 5 |
| Governance features (25%) | 5 | 4 | 5 |
| Compliance/audit (20%) | 5 | 4 | 5 |
| **Weighted Score** | **4.4** | **3.6** | **4.1** |

→ Recommendation: Terraform Enterprise hoặc CDK (nếu AWS-only)
```

#### Cleanup

```bash
rm -rf /tmp/iac-compare
cd ../..
rm -rf iac-compare
```

---

## 9. Common Pitfalls & Debugging

### Pitfall 1: Chọn tool vì hype, không vì fit

```
"Pulumi dùng TypeScript, cool hơn Terraform!"
→ Nhưng team toàn Ops, không ai biết TypeScript
→ Kết quả: 6 tháng struggle, chuyển lại Terraform

"CDK tạo L3 construct, 10 dòng = 30 resources!"
→ Nhưng cần multi-cloud sau 1 năm
→ Kết quả: rewrite toàn bộ IaC
```

**Fix**: Dùng decision matrix, đánh giá team skill + requirements trước.

### Pitfall 2: Migration giữa IaC tools

```
Terraform → Pulumi: 
  Pulumi có `pulumi import` và `tf2pulumi` converter
  Nhưng: state migration phức tạp, không 1:1

Terraform → CDK:
  Không có official converter
  Phải viết lại hoàn toàn
  State migration: manual (CloudFormation import)

CDK → Terraform:
  former-cdk tool experimental
  Hầu hết phải rewrite
```

**Fix**: Chọn đúng từ đầu. Migration cost rất cao (thường 2-6 tháng cho medium project).

### Pitfall 3: Over-engineering với GPL

```typescript
// ❌ Pulumi over-engineering:
class AbstractInfrastructureFactory<T extends CloudProvider> {
  abstract createNetwork(config: NetworkConfig): Promise<VPC>;
  // ...20 more abstract methods
}

class AwsInfrastructureFactory extends AbstractInfrastructureFactory<AWS> {
  // ...200 lines of abstraction
}

// ✅ Keep it simple:
const vpc = new aws.ec2.Vpc("main", {
  cidrBlock: "10.0.0.0/16",
  tags: { Name: "main-vpc" },
});
```

**Fix**: IaC code nên SIMPLE. Abstraction chỉ khi thực sự reuse across >3 teams.

### Pitfall 4: Ignoring License Implications

```
Terraform BSL 1.1 (since Aug 2023):
- Vẫn free cho end users
- KHÔNG free cho competitors (hosting Terraform as a service)
- Ảnh hưởng: Spacelift, env0, Scalr phải thương lượng
- KHÔNG ảnh hưởng: bạn dùng TF để quản lý infra

OpenTofu (MPL 2.0):
- Fork của Terraform trước BSL
- 100% compatible (hiện tại)
- Linux Foundation backing
- Có thể diverge theo thời gian
```

---

## 10. Kết nối với bài trước & bài sau

### Kết nối với Day 27-28

- Day 27-28 deep dive Terraform → hiểu strengths và limitations.
- Day 29 broadener perspective → alternatives có thể tốt hơn cho team bạn.
- Knowledge about Terraform giúp hiểu Pulumi (nhiều concepts tương đồng).

### Bài sau: Day 30 — Ansible for Configuration Management

- Day 26-29: **provisioning** (tạo infrastructure).
- Day 30: **configuration management** (configure machines) — concern khác.
- Ansible bổ sung cho Terraform: TF tạo VM, Ansible configure VM.

---

## 11. Tài liệu tham khảo

### Must-read

- [Pulumi vs Terraform — Official Comparison](https://www.pulumi.com/docs/concepts/vs/terraform/) — Pulumi's perspective (biased but informative).
- [AWS CDK Developer Guide](https://docs.aws.amazon.com/cdk/v2/guide/home.html) — Official CDK documentation.
- [OpenTofu Documentation](https://opentofu.org/docs/) — Terraform alternative.

### Nice-to-have

- [CDK Patterns](https://cdkpatterns.com/) — Well-architected CDK patterns.
- [Pulumi Examples](https://github.com/pulumi/examples) — Code examples in multiple languages.
- [Terraform vs Pulumi vs CDK — Community Comparison](https://blog.gruntwork.io/pulumi-vs-terraform-4e345e04e0d0) — Balanced analysis.

### Deep-dive

- [Infrastructure as Code — Kief Morris](https://www.oreilly.com/library/view/infrastructure-as-code/9781098114664/) — Tool-agnostic IaC principles.
- [The BSL License and What It Means — HashiCorp Blog](https://www.hashicorp.com/blog/hashicorp-adopts-business-source-license) — License context.
- [Thoughtworks Technology Radar — IaC tools assessment](https://www.thoughtworks.com/radar) — Industry trends.

