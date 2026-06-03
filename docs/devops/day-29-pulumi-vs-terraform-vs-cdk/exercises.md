# Day 29: Exercises — Pulumi vs Terraform vs CDK

## Exercise 1: Easy — IaC Tool Terminology & Concepts

### Context

Team lead yêu cầu bạn chuẩn bị một presentation so sánh 3 IaC tools cho engineering team. Bước đầu tiên là nắm vững terminology mapping giữa các tools.

### Yêu cầu

1. Hoàn thành bảng terminology mapping:

   | Concept | Terraform | Pulumi | AWS CDK |
   |---------|-----------|--------|---------|
   | Định nghĩa resource | ? | ? | ? |
   | Input parameters | ? | ? | ? |
   | Return values | ? | ? | ? |
   | Reusable package | ? | ? | ? |
   | State storage | ? | ? | ? |
   | Preview changes | ? | ? | ? |
   | Execute changes | ? | ? | ? |
   | Delete all | ? | ? | ? |

2. Với mỗi tool, viết 3 **strengths** và 3 **weaknesses** dựa trên lesson.

3. Trả lời câu hỏi: "Nếu team bạn chỉ dùng AWS và toàn bộ codebase là TypeScript, tool nào phù hợp nhất? Giải thích tại sao."

### Expected Outcome

- Bảng terminology đầy đủ 8 rows × 3 tools.
- 3 strengths + 3 weaknesses mỗi tool.
- Câu trả lời có reasoning rõ ràng, không chỉ nêu kết luận.

### Hint

- Terraform: resource, variable, output, module, .tfstate, plan, apply, destroy.
- Pulumi: Resource class, Config, export, ComponentResource, state, preview, up, destroy.
- CDK: Construct, props, CfnOutput, Construct L3, CloudFormation stack, diff, deploy, destroy.

### Acceptance Criteria

- [ ] Terminology mapping chính xác
- [ ] Strengths/weaknesses balanced (không bias 1 tool)
- [ ] Recommendation có reasoning dựa trên team context

### Bonus Challenge

Thêm column cho **OpenTofu** và **CDKTF** (CDK for Terraform) vào bảng.

<details>
<summary>Solution</summary>

**1. Terminology Mapping:**

| Concept | Terraform | Pulumi | AWS CDK |
|---------|-----------|--------|---------|
| Định nghĩa resource | `resource "type" "name"` | `new aws.Resource("name", {})` | `new Construct(this, "name", {})` |
| Input parameters | `variable` | `pulumi.Config` | Constructor `props` |
| Return values | `output` | `export const` | `new CfnOutput()` |
| Reusable package | Module | ComponentResource / package | Construct (L2/L3) |
| State storage | `.tfstate` (S3/GCS/TF Cloud) | Pulumi Cloud / S3 / local | CloudFormation stack |
| Preview changes | `terraform plan` | `pulumi preview` | `cdk diff` |
| Execute changes | `terraform apply` | `pulumi up` | `cdk deploy` |
| Delete all | `terraform destroy` | `pulumi destroy` | `cdk destroy` |

**2. Strengths/Weaknesses:**

Terraform:
- ✅ Largest ecosystem (3000+ providers)
- ✅ Multi-cloud native
- ✅ Biggest hiring pool
- ❌ HCL learning curve for devs
- ❌ Limited testing
- ❌ BSL license concerns

Pulumi:
- ✅ Real programming languages
- ✅ Full type system + testing
- ✅ Secrets encrypted by default
- ❌ Smaller community
- ❌ Fewer native providers
- ❌ Smaller hiring pool

CDK:
- ✅ Deep AWS integration
- ✅ High-level L3 constructs
- ✅ AWS-maintained, always current
- ❌ AWS-only (no multi-cloud)
- ❌ CloudFormation 500 resource limit
- ❌ Vendor lock-in

**3. AWS + TypeScript team:**

Best choice: **CDK** hoặc **Pulumi**, tùy context.

CDK nếu:
- 100% AWS, không plan multi-cloud
- Muốn L3 constructs (10 lines = 30 resources)
- AWS Enterprise Support available

Pulumi nếu:
- Có thể cần multi-cloud trong tương lai
- Muốn better testing story
- Team values open-source (Apache 2.0)

Không chọn Terraform vì team đã có TypeScript expertise — learning HCL là overhead không cần thiết.

</details>

---

## Exercise 2: Medium — Decision Matrix cho Organization

### Context

Bạn là DevOps consultant được thuê để recommend IaC tool cho 3 teams khác nhau trong cùng tổ chức:

- **Team Alpha**: Startup product team, 5 engineers, full-stack TypeScript, deploying to AWS, moving fast.
- **Team Beta**: Platform team, 15 engineers, mixed languages (Go/Python), multi-cloud (AWS primary + GCP for ML), cần governance.
- **Team Gamma**: Enterprise compliance team, 8 engineers, Java background, AWS GovCloud, strict regulatory requirements.

### Yêu cầu

1. Tạo **weighted decision matrix** cho mỗi team với ít nhất 8 tiêu chí:
   - Chọn weights phù hợp context mỗi team
   - Chấm điểm 1-5 cho mỗi tool
   - Tính weighted score

2. Viết **recommendation memo** cho CTO:
   - Recommendation cho mỗi team
   - Reasoning dựa trên matrix
   - Migration path nếu teams cần converge sau này
   - Risk assessment

3. Trả lời câu hỏi: "Có nên dùng chung 1 tool cho cả tổ chức không?"
   - Pros/cons of standardization
   - Recommendation

### Expected Outcome

- 3 decision matrices với weighted scores.
- 1-page memo cho CTO.
- Standardization analysis.

### Hint

- Weights phải reflect team priorities: startup cần speed, platform cần multi-cloud, compliance cần audit.
- Điểm số dựa trên lesson comparison matrix.
- Standardization trade-off: consistency vs flexibility.

### Acceptance Criteria

- [ ] 3 matrices với ≥8 tiêu chí mỗi matrix
- [ ] Weights sum to 100%
- [ ] Scores justified (không random)
- [ ] Memo professional, concise
- [ ] Standardization analysis balanced
- [ ] Migration path realistic

### Bonus Challenge

Thêm **TCO (Total Cost of Ownership) analysis** cho mỗi option: tool cost + training cost + hiring cost + migration cost.

<details>
<summary>Solution</summary>

**Team Alpha (Startup, 5 eng, TS, AWS):**

| Criteria (Weight) | Terraform | Pulumi | CDK |
|---|---|---|---|
| Time to first deploy (25%) | 3 | 4 | 5 |
| Developer experience (20%) | 3 | 5 | 5 |
| Learning curve (15%) | 3 | 5 | 4 |
| Community/docs (15%) | 5 | 3 | 4 |
| Multi-cloud option (5%) | 5 | 5 | 1 |
| Cost (10%) | 5 | 4 | 5 |
| Hiring (5%) | 5 | 2 | 3 |
| Testing (5%) | 2 | 5 | 4 |
| **Weighted** | **3.6** | **4.2** | **4.3** |

→ **CDK** (AWS + TS native) hoặc **Pulumi** (multi-cloud option)

**Team Beta (Platform, 15 eng, multi-cloud):**

| Criteria (Weight) | Terraform | Pulumi | CDK |
|---|---|---|---|
| Multi-cloud (30%) | 5 | 5 | 1 |
| Governance (20%) | 5 | 4 | 3 |
| Hiring/community (15%) | 5 | 3 | 3 |
| Developer experience (10%) | 3 | 5 | 5 |
| Module ecosystem (10%) | 5 | 3 | 3 |
| Testing (5%) | 3 | 5 | 4 |
| Cost (5%) | 4 | 3 | 5 |
| Learning curve (5%) | 3 | 4 | 4 |
| **Weighted** | **4.6** | **4.0** | **2.5** |

→ **Terraform** (multi-cloud + governance + hiring)

**Team Gamma (Compliance, 8 eng, Java, GovCloud):**

| Criteria (Weight) | Terraform | Pulumi | CDK |
|---|---|---|---|
| Compliance/audit (30%) | 5 | 4 | 5 |
| AWS integration (20%) | 4 | 3 | 5 |
| Governance (20%) | 5 | 4 | 5 |
| Java support (10%) | 3 | 4 | 5 |
| Community (10%) | 5 | 3 | 4 |
| Cost (5%) | 4 | 3 | 5 |
| Testing (5%) | 3 | 5 | 4 |
| **Weighted** | **4.5** | **3.7** | **4.9** |

→ **CDK** (AWS GovCloud native + Java + compliance)

**CTO Memo:**

```
RECOMMENDATION:
- Team Alpha: CDK (AWS + TypeScript alignment)
- Team Beta: Terraform (multi-cloud requirement)
- Team Gamma: CDK (AWS GovCloud + compliance)

STANDARDIZATION:
Không recommend 1 tool cho cả org:
- Team Beta CẦN multi-cloud → CDK không phù hợp
- Team Alpha/Gamma CẦN deep AWS → Terraform overhead
- Recommend: Terraform cho platform, CDK cho AWS-specific teams

MIGRATION PATH:
- Phase 1: Each team adopts recommended tool
- Phase 2: Share patterns/templates cross-team
- Phase 3: Evaluate convergence after 12 months
```

</details>

---

## Exercise 3: Hard — Proof of Concept với 2 Tools

### Context

CTO yêu cầu bạn tạo proof of concept: triển khai cùng một infrastructure bằng Terraform và 1 tool khác (Pulumi hoặc pseudo-CDK) để team đánh giá trực tiếp.

### Yêu cầu

1. Viết Terraform code tạo:
   - Docker network
   - 2 NGINX containers (web-1, web-2) trên cùng network
   - Custom NGINX config trả về tên container
   - Outputs: URLs, container names

2. Viết **equivalent pseudo-code** bằng Pulumi TypeScript hoặc CDK TypeScript cho cùng infrastructure.

3. So sánh 2 implementations trên ít nhất 6 dimensions:
   - Lines of code
   - Readability
   - Type safety
   - Testing approach
   - IDE experience
   - Error messages

4. Viết **PoC evaluation report** bao gồm:
   - Setup experience (cài đặt, init)
   - Development experience (viết code, debug)
   - Operational experience (plan, apply, destroy)
   - Team feedback (simulate)
   - Final recommendation

### Expected Outcome

- Working Terraform code (deploy + verify + destroy).
- Pulumi/CDK pseudo-code (có thể không chạy nếu không cài tool).
- Comparative analysis document.
- PoC evaluation report.

### Acceptance Criteria

- [ ] Terraform code works end-to-end
- [ ] Alternative tool code logically correct
- [ ] Comparison covers ≥6 dimensions
- [ ] PoC report structured and professional
- [ ] Recommendation based on evidence, not opinion

### Bonus Challenge

Nếu có thể, cài Pulumi và chạy thật cả 2 implementations. So sánh actual plan/apply output.

<details>
<summary>Solution</summary>

**Terraform:**
```hcl
terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}
provider "docker" {}

resource "docker_network" "app" { name = "poc-network" }
resource "docker_image" "nginx" { name = "nginx:alpine" }

resource "docker_container" "web" {
  for_each = { "web-1" = 8080, "web-2" = 8081 }
  name     = "poc-${each.key}"
  image    = docker_image.nginx.image_id
  ports {
    internal = 80
    external = each.value
  }
  networks_advanced { name = docker_network.app.name }
  upload {
    content = "server { listen 80; location / { return 200 '${each.key}\\n'; } }"
    file    = "/etc/nginx/conf.d/default.conf"
  }
  must_run = true
}

output "urls" {
  value = { for k, c in docker_container.web : k => "http://localhost:${c.ports[0].external}" }
}
```

**Pulumi TypeScript equivalent:**
```typescript
import * as docker from "@pulumi/docker";

const network = new docker.Network("app", { name: "poc-network" });
const image = new docker.RemoteImage("nginx", { name: "nginx:alpine" });

const services = { "web-1": 8080, "web-2": 8081 };

const containers = Object.entries(services).map(([name, port]) =>
  new docker.Container(`poc-${name}`, {
    name: `poc-${name}`,
    image: image.imageId,
    networksAdvanced: [{ name: network.name }],
    ports: [{ internal: 80, external: port }],
    uploads: [{
      content: `server { listen 80; location / { return 200 '${name}\\n'; } }`,
      file: "/etc/nginx/conf.d/default.conf",
    }],
    mustRun: true,
  })
);

export const urls = Object.fromEntries(
  Object.entries(services).map(([name, port]) => [name, `http://localhost:${port}`])
);
```

**Comparative Analysis:**

| Dimension | Terraform | Pulumi TS |
|-----------|-----------|-----------|
| Lines of code | 25 | 22 |
| Readability | Good (declarative) | Good (familiar JS) |
| Type safety | Runtime (plan) | Compile-time (tsc) |
| Testing | `terraform plan` check | Jest unit tests |
| IDE autocomplete | Good (TF extension) | Excellent (native TS) |
| Error messages | Plan output | Compiler + runtime |
| Setup time | 2 min (init) | 5 min (npm + init) |
| Learning curve | HCL syntax | Pulumi SDK API |

</details>

