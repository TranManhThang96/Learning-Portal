# Week 5 - Capstone Production-Grade (Day 28-35)

## Tổng quan

Week 5 là phase cuối cùng — Capstone Production-Grade. Học viên ráp tất cả kiến thức 27 ngày để build một platform end-to-end cho hệ microservices: 3 service (`api-service`, `worker-service`, `frontend-service`) + PostgreSQL + Redis + GitOps deploy + Observability + CI/CD + Disaster Recovery.

Capstone hỗ trợ 2 mode:
- **Mode A — Local/Low-cost**: kind/minikube + Docker Compose + LocalStack + GHCR + nginx-ingress + cert-manager local + ESO local provider + kube-prometheus-stack local. Mode mặc định, miễn phí.
- **Mode B — AWS Production-like**: VPC + EKS + ECR + RDS + ElastiCache + IRSA + ALB Controller + Route53 + ACM + AWS Secrets Manager. Optional, có chi phí ước tính ~$150-280/tháng (eu-west-1, tháng 5/2026).

> **Trạng thái:** Day 28-35 đã hoàn tất. Week 5 capstone đã đủ 8 ngày với `lesson.md`, `document.md`, `exercises.md`.

## Lộ trình học

| Ngày | Chủ đề | Thời lượng | Files |
|------|--------|------------|-------|
| Day 28 | Capstone Architecture, Repo Strategy, Cost Strategy | 2h | [lesson](day-28-capstone-architecture/lesson.md) · [document](day-28-capstone-architecture/document.md) · [exercises](day-28-capstone-architecture/exercises.md) |
| Day 29 | Infrastructure Network Layer | 2h | [lesson](day-29-infra-network-layer/lesson.md) · [document](day-29-infra-network-layer/document.md) · [exercises](day-29-infra-network-layer/exercises.md) |
| Day 30 | Kubernetes & IAM Layer | 2h | [lesson](day-30-kubernetes-iam-layer/lesson.md) · [document](day-30-kubernetes-iam-layer/document.md) · [exercises](day-30-kubernetes-iam-layer/exercises.md) |
| Day 31 | Data Layer: PostgreSQL, Redis, Secrets | 2h | [lesson](day-31-data-layer-secrets/lesson.md) · [document](day-31-data-layer-secrets/document.md) · [exercises](day-31-data-layer-secrets/exercises.md) |
| Day 32 | Platform Bootstrap Layer | 2h | [lesson](day-32-platform-bootstrap/lesson.md) · [document](day-32-platform-bootstrap/document.md) · [exercises](day-32-platform-bootstrap/exercises.md) |
| Day 33 | GitOps Apps Layer & Promotion Strategy | 2h | [lesson](day-33-gitops-apps-promotion/lesson.md) · [document](day-33-gitops-apps-promotion/document.md) · [exercises](day-33-gitops-apps-promotion/exercises.md) |
| Day 34 | CI/CD, Observability, Reliability | 2h | [lesson](day-34-cicd-observability-reliability/lesson.md) · [document](day-34-cicd-observability-reliability/document.md) · [exercises](day-34-cicd-observability-reliability/exercises.md) |
| Day 35 | Disaster Recovery, Final Demo, Runbook | 2h | [lesson](day-35-disaster-recovery-demo/lesson.md) · [document](day-35-disaster-recovery-demo/document.md) · [exercises](day-35-disaster-recovery-demo/exercises.md) |

## Chi tiết từng ngày đã hoàn thành

### Day 28 - Capstone Architecture, Repo Strategy, Cost Strategy

**Mục tiêu:** Thiết kế kiến trúc tổng thể Capstone (Mode A + Mode B), tách 3 repo (`capstone-infra` / `capstone-platform` / `capstone-apps`) với ownership rõ ràng, ra quyết định cost strategy + security baseline + environment strategy (dev / staging / production-like), viết ADR đầu tiên cho platform.

- **Kiến thức:** Capstone target (3 microservice + DB + cache + GitOps + observability + CI/CD + DR), 2 architecture diagram ASCII (Mode A local-stack vs Mode B AWS-stack với từng layer), 3-repo strategy (infra-repo Terraform / platform-repo Helm + ApplicationSet / apps-repo manifest + image tag), 5-layer breakdown (Network → Cluster + IAM → Data → Platform Bootstrap → Apps), environment strategy (dev auto-sync, staging PR-gated, prod manual approval).
- **Deep dive:** Cost strategy Mode B (~$277/tháng full, ~$153/tháng cost-optimized với single-AZ NAT + Spot + t3.small + free tier endpoint), security baseline (IRSA thay long-lived key, OIDC GitHub Actions, RDS private subnet, ESO + ASM, image scanning), repo strategy 3-repo polyrepo vs monorepo trade-off, ADR template Markdown chuẩn (Status / Context / Decision / Consequences), 10 anti-patterns capstone (scope creep, không cleanup AWS → bill, hardcode account ID, mix infra + app concerns).
- **Lab (7 bước):** Tạo 3 repo (hoặc 3 folder mô phỏng) skeleton với README ownership + CODEOWNERS, viết `docs/architecture.md` với ASCII diagram, ADR-0001 chọn Mode A mặc định + Mode B optional, `docs/cost-estimate.md` table dịch vụ × cost × cleanup, `docs/security-baseline.md` checklist, `Makefile` shortcut (`make local-up/down`, `make aws-plan/destroy`), verify cleanup `make local-down`.
- **Document:** ASCII diagram đầy đủ Mode A + Mode B, repo structure template chi tiết 3 repo, ADR template + 5 ADR draft (mode, repo-split, secrets, promotion, DR), cost matrix Mode B eu-west-1 tháng 5/2026 + 5 cost optimization strategies, 20-bullet security baseline (MUST/SHOULD/NICE), AWS cleanup runbook (Terraform destroy + manual cleanup ECR/S3/RDS snapshot + budget alert), environment strategy table.
- **Exercises:** 5 challenges + 1 bonus (cost-optimized Mode B < $200/tháng cho startup 10 dev — final ~$153; refactor 1-repo monorepo → 3 polyrepo migration plan 2 tuần; 4 ADR cho production 50 service: managed vs self-managed K8s + RDS vs Aurora + multi-region + ApplicationSet; PCI/HIPAA security baseline bổ sung; Mode C hybrid on-prem + cloud feasibility; bonus on-call runbook 4 scenario P1-P3).

### Day 29 - Infrastructure Network Layer

**Mục tiêu:** Thiết kế VPC production-grade (3 AZ, public/private/intra subnet), cân nhắc trade-off NAT Gateway vs VPC endpoint, cấu hình security group theo tier, viết Terraform module VPC reuse được cho dev/staging/prod, output đầy đủ network config làm input cho Day 30 (cluster + IAM).

- **Kiến thức:** VPC + CIDR block, public subnet (route IGW) vs private subnet (route NAT) vs intra subnet (chỉ internal), multi-AZ design (2-3 AZ HA), route table per subnet group, NAT Gateway pricing (~$32/AZ/tháng + $0.045/GB → cost cảnh báo), security group (stateful, default deny inbound) vs NACL (stateless), VPC endpoint Gateway (S3/DynamoDB free) vs Interface (per-AZ ~$7/tháng), DNS (`enable_dns_hostnames` + `enable_dns_support`, Route53 private hosted zone), Mode A kind dùng Docker bridge — không cần VPC.
- **Deep dive:** 3 cách dùng module VPC (`terraform-aws-modules/vpc/aws` recommended vs custom from scratch vs cloudposse), NAT alternatives (VPC endpoint cho ECR/S3/Secrets Manager/STS/Logs, single NAT 1 AZ tiết kiệm 2/3 cost, NAT instance EC2 legacy), subnet sizing (/20 cho EKS pod density, /24 cho RDS, /28 cho intra), security group strategy (per-tier vs per-service), cost trade-off NAT 2 AZ ~$66/tháng vs VPC endpoint 5 service × 2 AZ ~$70/tháng (giảm NAT traffic), pitfalls (CIDR overlap khi peering, subnet hết IP cho EKS pod, public DB subnet nhầm).
- **Lab:** Mode A — verify Docker bridge + viết `local/network.md` document mapping. Mode B — `terraform/modules/vpc/` dùng `terraform-aws-modules/vpc/aws ~> 5.0` với 3 AZ + public/private/intra subnet + single NAT cost-optimized, VPC endpoint Gateway (S3 + DynamoDB free) + Interface (ECR-api / ECR-dkr / STS / Secrets Manager / Logs), 5 security group (eks-cluster, eks-nodes, rds, elasticache, vpc-endpoints), `envs/dev/main.tf` CIDR `10.0.0.0/16` AZ `[a,b,c]`, full outputs (`vpc_id`, `private_subnet_ids`, all SGs, endpoint IDs) cho Day 30, **CLEANUP `terraform destroy`** bắt buộc.
- **Document:** VPC design cheat sheet (CIDR sizing formula), subnet sizing for EKS (VPC CNI vs custom CNI, IP requirement matrix), NAT alternatives comparison table, VPC endpoint catalog (Gateway free vs Interface paid + recommended set), security group strategy templates (3-tier, per-service), module input/output reference, cost optimization checklist 10 bullet, 10-12 anti-patterns, common Terraform errors VPC.
- **Exercises:** 6 challenges (multi-region VPC peering us-east-1 + ap-southeast-1; cost reduction $300 → < $50/tháng giữ HA; refactor flat VPC → tier-based không downtime; debug "EKS pod ENI exhaustion" VPC CNI hết IP; Transit Gateway hub-spoke 4 VPC shared services; bonus IPv6 dual-stack migration plan).

### Day 30 - Kubernetes & IAM Layer

**Mục tiêu:** Provision EKS hoặc kind cluster, hiểu trade-off managed node group / self-managed / Karpenter / Fargate, cấu hình IRSA (IAM Role for Service Account) qua OIDC provider thay long-lived AWS key, push image vào ECR/GHCR với lifecycle policy, output cluster config cho Day 31-32.

- **Kiến thức:** EKS managed control plane $73/tháng, node tự quản; managed node group vs self-managed (Bottlerocket, full control) vs Karpenter (modern, recommended cho production); On-Demand vs Spot (interruption 2 phút notice cho stateless workload) vs Reserved/Savings Plan; IRSA = pod assume role qua OIDC provider, fine-grained per workload (vs node IAM = all-pods-on-node giống nhau); OIDC provider gắn vào EKS cluster, trust policy `oidc.eks...:sub` = `system:serviceaccount:NAMESPACE:SA`; ECR (IAM-based auth, per-region, IRSA pull) vs GHCR (free public, paid private bandwidth); kind config 1 control + N worker với port mapping cho ingress.
- **Deep dive:** Managed vs Karpenter vs Fargate matrix theo use case, Spot strategy (mixed instances policy, capacity-optimized allocation, instance diversification, pod tolerations + node selectors), IRSA vs Pod Identity (AWS mới 2023, không cần OIDC mounting, recommended từ EKS 1.27+), ECR vs GHCR cho capstone (ECR có IRSA pull / GHCR free for OSS), cost EKS $73 + Spot t3.medium ~$10/node/tháng × 2 = ~$93/tháng tối thiểu cho dev cluster; Mode A kind 0 cost nhưng IRSA không có (mock kube2iam/kiam hoặc skip); pitfalls (forget OIDC provider, IRSA trust policy sai namespace, Spot không có toleration → evict storm, ECR không lifecycle policy → cost tăng).
- **Lab:** Mode A — `local/kind-config.yaml` 1 control + 2 worker + port mapping 80/443, `kind create cluster`, label node, optional MetalLB, push `hello-app:0.1.0` lên GHCR, tạo `imagePullSecret`. Mode B — module `terraform/modules/eks/` dùng `terraform-aws-modules/eks/aws ~> 20.0` + managed node group Spot, OIDC provider tự động, 3 IAM Role IRSA placeholder (cluster-autoscaler / ALB Controller / ESO), 3 ECR repo (`capstone/api`, `capstone/worker`, `capstone/frontend`) với lifecycle policy giữ 10 image, `terraform apply`, `aws eks update-kubeconfig`, build + tag + push image, **CLEANUP `terraform destroy`** bắt buộc nếu Mode B.
- **Document:** EKS module input/output reference, node group decision tree (managed / self-managed / Karpenter / Fargate), IRSA setup checklist (OIDC + trust policy template), 5 IRSA YAML template (ESO, ALB, Autoscaler, S3 reader, EBS CSI), Pod Identity vs IRSA comparison, Spot strategy reference (mixed instances, allocation strategy, toleration YAML), ECR vs GHCR matrix + lifecycle policy JSON template, kind config template, cost optimization checklist, 12 anti-patterns, 5 common error + fix flow.
- **Exercises:** 6 challenges (migrate node group On-Demand → 70% Spot diversified với HA + PDB; refactor 5 pod node IAM → IRSA per workload; multi-tenancy cluster 3 team share EKS với namespace + IRSA + ECR per team; debug "pod CrashLoopBackOff: NoCredentialProviders" IRSA fail; Karpenter migration plan + cost saving estimate; bonus ECR cross-account replication multi-region).

### Day 31 - Data Layer: PostgreSQL, Redis, Secrets

**Mục tiêu:** Xây dựng data layer cho capstone với PostgreSQL/RDS, Redis/ElastiCache, backup strategy, secret storage và connection string management an toàn cho cả Mode A và Mode B.

- **Kiến thức:** PostgreSQL local Helm/Docker Compose vs RDS, Redis local vs ElastiCache, backup strategy theo RPO/RTO, secret storage patterns (Kubernetes Secret, External Secrets Operator, AWS Secrets Manager, local store), connection string lifecycle và cách inject vào workload qua ExternalSecret.
- **Deep dive:** Decision matrix PostgreSQL/Redis theo cá nhân, small team, startup, enterprise, bank/regulated; env var vs volume mount; backup/restore architecture; cost breakdown Mode A $0 vs Mode B RDS + ElastiCache + Secrets Manager; security baseline tránh secret trong Git, public database, plaintext connection string.
- **Lab:** Mode A cài PostgreSQL + Redis bằng Helm và cấu hình ESO local secret store. Mode B tạo RDS + ElastiCache + AWS Secrets Manager bằng Terraform, cấu hình ESO ClusterSecretStore qua IRSA, test connection string, verify secret sync, cleanup resource cloud.
- **Document/Exercises:** Data layer cheat sheet, backup decision guide, ASM/SSM/ESO reference, Terraform module reference, security checklist, debug RDS timeout/ESO sync/Redis migration/secret rotation/PITR scenarios.

### Day 32 - Platform Bootstrap Layer

**Mục tiêu:** Bootstrap platform layer theo đúng dependency order: ArgoCD trước, sau đó External Secrets Operator, cert-manager, Ingress/ALB Controller và Prometheus stack.

- **Kiến thức:** Bootstrap dependency graph, ArgoCD bootstrap bằng Helm, App of Apps root application, ESO flow `ClusterSecretStore → ExternalSecret → Kubernetes Secret`, cert-manager issuer local/ACM path, NGINX Ingress Controller vs AWS Load Balancer Controller, kube-prometheus-stack components.
- **Deep dive:** So sánh Terraform `helm_release`, ArgoCD quản lý Helm và hybrid bootstrap; App of Apps vs ApplicationSet cho platform apps; sync wave cho dependency order; security baseline cho repo credentials, RBAC, IRSA, cert issuance; common pitfalls như Terraform và ArgoCD cùng quản lý một release.
- **Lab:** Cài ArgoCD, tạo AppProject + root Application, bootstrap cert-manager/ESO/ingress/prometheus qua App of Apps với sync waves, verify CRD/controller/health, tùy chọn Mode B cấu hình ALB Controller + ACM + IRSA.
- **Document/Exercises:** Bootstrap order checklist, Terraform vs ArgoCD decision matrix, ESO/cert-manager/ingress reference, Prometheus values reference, challenge refactor sang ApplicationSet, debug ESO/certificate/Prometheus OOM, design multi-cluster bootstrap.

### Day 33 - GitOps Apps Layer & Promotion Strategy

**Mục tiêu:** Deploy 3 microservices qua GitOps apps repo, dùng Helm chart + Kustomize overlay, ApplicationSet auto-discovery, immutable image tag, promotion dev → staging → production-like và rollback bằng Git.

- **Kiến thức:** Apps repo structure production-like, Helm chart cho microservice, Kustomize overlay theo env, ApplicationSet git generator auto-detect service, image tag strategy (`git sha`, semver, immutable tag; tránh `latest` cho production), promotion workflow và rollback workflow.
- **Deep dive:** Helm-only vs Kustomize-only vs Helm + Kustomize, ApplicationSet generator selection, dev auto-sync vs staging PR-gated vs production manual approval, rollback bằng Git revert vs ArgoCD sync previous revision, security baseline cho image tag và environment separation.
- **Lab:** Tạo chart base, overlay dev/staging/prod-like, ApplicationSet deploy `api-service`, `worker-service`, `frontend-service`, thực hiện promotion dev → staging qua PR-style change, simulate rollback và troubleshoot OutOfSync/drift/image mismatch.
- **Document/Exercises:** GitOps repo/promotion reference, full chart/overlay/ApplicationSet templates, PR template, rollback playbook, challenge multi-service release, migration khỏi `latest`, drift debugging, canary promotion, multi-cluster promotion design.

### Day 34 - CI/CD, Observability, Reliability

**Mục tiêu:** Hoàn thiện delivery pipeline và production readiness cho capstone: lint/test/build/scan/push image, update GitOps repo bằng PR, metrics/logging/alerting và reliability manifests.

- **Kiến thức:** GitHub Actions pipeline với quality gates, GHCR/ECR push, OIDC/least privilege cho AWS, Trivy image scan, PR-based image tag update, Prometheus/Grafana/Loki, readiness/liveness probes, resource requests/limits, HPA và PodDisruptionBudget.
- **Deep dive:** Trade-off GHCR vs ECR, direct push vs PR update GitOps repo, alert severity strategy, resource sizing, Spot node + PDB/HPA interaction, cost/capacity impact của observability stack, best solution theo team size và compliance context.
- **Lab:** Tạo GitHub Actions workflow production-like, build/push immutable image, mở PR update image tag trong apps repo, tạo PrometheusRule + Grafana dashboard cơ bản, thêm probes/resources/HPA/PDB vào microservices, verify pipeline và alert behavior.
- **Document/Exercises:** CI/CD checklist, observability/reliability templates, ServiceMonitor/PrometheusRule/Grafana snippets, AWS cost controls, debug Trivy failure/Dockerfile CVE, alert tuning, reliability design review, OOM/HPA/PDB incident simulation.

### Day 35 - Disaster Recovery, Final Demo, Runbook, Retrospective

**Mục tiêu:** Chạy final demo end-to-end, mô phỏng sự cố production, thực hành restore/rollback, export runbook và cleanup toàn bộ resource.

- **Kiến thức:** DR scenarios gồm mất cluster, mất ArgoCD, sai secret, deployment lỗi, Terraform state lỗi, rollback app; RTO/RPO; backup hierarchy; GitOps restore mental model; Terraform state safety và ArgoCD backup/restore.
- **Deep dive:** Active-active vs active-passive vs backup-restore, Velero vs ArgoCD export vs Git-based recovery, DR matrix theo component, khi rollback app bằng Git revert vs rollback image vs restore secret/state, production-ready vs simulation boundaries của capstone.
- **Lab:** Backup ArgoCD config, xóa app khỏi cluster và để ArgoCD self-heal/restore, simulate bad deployment và rollback, simulate Terraform state issue an toàn, export runbook, chạy final demo checklist, cleanup Mode A và Mode B.
- **Document/Exercises:** Runbook template, 6 runbook hoàn chỉnh cho cluster/ArgoCD/secret/deployment/state/rollback, DR checklist, final demo script, retrospective template, GameDay exercises, cost cleanup analysis và on-call rotation design.

## Cấu trúc folder

```
week-5-capstone/
├── README.md
├── day-28-capstone-architecture/      lesson + document + exercises
├── day-29-infra-network-layer/        lesson + document + exercises
├── day-30-kubernetes-iam-layer/       lesson + document + exercises
├── day-31-data-layer-secrets/         lesson + document + exercises
├── day-32-platform-bootstrap/         lesson + document + exercises
├── day-33-gitops-apps-promotion/      lesson + document + exercises
├── day-34-cicd-observability-reliability/ lesson + document + exercises
└── day-35-disaster-recovery-demo/     lesson + document + exercises
```

## Cách sử dụng

1. **Chọn mode trước:** Mode A (free, recommended cho học viên muốn tránh chi phí) hoặc Mode B (có cost cảnh báo, cleanup bắt buộc sau mỗi lab)
2. Học tuần tự Day 28 → Day 35 — capstone là chuỗi liên tục, output ngày trước là input ngày sau
3. Mỗi ngày bắt đầu bằng `lesson.md`: 30 phút theory → 30 phút deep dive → 60 phút lab
4. Tra cứu nhanh trong `document.md` (cheat sheet, ADR, runbook, decision tree, anti-patterns)
5. Làm thêm `exercises.md` nếu muốn nâng cao

## Yêu cầu môi trường

- **Mode A (default, free):**
  - Docker Desktop / Docker Engine
  - kind >= 0.20 hoặc minikube
  - kubectl >= 1.28, Helm >= 3.13, Kustomize >= 5.x
  - argocd CLI, kubectl argo rollouts
  - GitHub account (cho GHCR + apps repo)
  - Optional: LocalStack (nếu mock AWS service)

- **Mode B (optional, có cost):**
  - AWS account với quyền tạo VPC/EKS/RDS/ElastiCache/IAM/Route53
  - AWS CLI v2 + credentials cấu hình OIDC GitHub Actions (theo Day 11)
  - Terraform >= 1.6
  - Domain Route53 (hoặc subdomain) cho ACM certificate
  - **Bắt buộc:** AWS Budget alert cấu hình trước khi apply (recommended < $50/tháng cho dev)

## Cảnh báo chi phí (Mode B)

Các resource phát sinh chi phí (eu-west-1, tháng 5/2026, ước tính):

| Resource | Cost/tháng (full) | Cost/tháng (cost-optimized) |
|----------|-------------------|------------------------------|
| EKS control plane | $73 | $73 |
| Node group (2× t3.medium On-Demand) | ~$60 | Spot 2× t3.small ~$10 |
| NAT Gateway × 3 AZ + traffic | ~$100 | Single NAT 1 AZ ~$32 |
| RDS db.t3.micro Multi-AZ | ~$30 | db.t3.micro Single-AZ ~$13 |
| ElastiCache cache.t3.micro | ~$13 | t3.micro ~$13 |
| ALB | ~$18 | ~$18 |
| VPC endpoint Interface × 5 × 2 AZ | ~$70 | × 1 AZ ~$35 |
| Misc (S3, ECR storage, Logs) | ~$10 | ~$10 |
| **Tổng** | **~$277** | **~$153** |

> Disclaimer: pricing có thể thay đổi. Luôn check AWS Pricing Calculator trước khi apply.

**Cách giảm cost:**
- Mặc định Mode A. Chỉ apply Mode B trong session ngắn (1-2 giờ) rồi destroy
- Single-AZ cho dev (chấp nhận downtime khi AZ fail)
- Spot node group 70-100% cho dev workload
- VPC endpoint chỉ cho service thực sự dùng (ECR + STS + Logs đủ cho EKS)
- Stop RDS khi không dùng (`aws rds stop-db-instance` — chỉ giữ được 7 ngày, sau đó tự start lại)

**Cleanup bắt buộc sau mỗi lab Mode B:**
```bash
cd capstone-infra/terraform/envs/dev
terraform destroy -auto-approve
# Verify trong AWS Console
aws ec2 describe-vpcs --filters Name=tag:Project,Values=capstone
```

## Tính liên tục

**Input từ Week 1-4:**
- Terraform foundations + production (Day 1-12): module design, multi-env, state strategy, CI/CD, OIDC, drift detection
- Ansible (Day 13-16): playbook hardening, role, vault, dynamic inventory (dùng cho bastion nếu Mode B)
- ArgoCD core (Day 17-19): Application, AppProject, Helm/Kustomize
- ArgoCD advanced (Day 20-27): repo structure, App of Apps, ApplicationSet, sync waves, secrets/RBAC, Argo Rollouts, observability + DR

**Trong Week 5 — chuỗi build:**
- Day 28 → Day 29: 3 repo skeleton + ADR-0001 mode → Day 29 vào `capstone-infra/terraform/modules/vpc`
- Day 29 → Day 30: VPC outputs (`private_subnet_ids`, security groups) → Day 30 EKS module
- Day 30 → Day 31: EKS cluster + IRSA role placeholder → Day 31 RDS/ElastiCache + ESO IRSA cụ thể
- Day 31 → Day 32: data layer + secret store → Day 32 platform bootstrap (ESO + cert-manager + Ingress + Prometheus)
- Day 32 → Day 33: platform ready → Day 33 deploy 3 microservice qua ApplicationSet
- Day 33 → Day 34: GitOps apps → Day 34 CI/CD pipeline + observability stack
- Day 34 → Day 35: full platform → Day 35 disaster recovery scenarios + final demo + retrospective

## Kết quả hoàn thành

- **Day 31** — Data Layer: PostgreSQL local vs RDS, Redis local vs ElastiCache, backup strategy, secret storage và connection string management.
- **Day 32** — Platform Bootstrap: ArgoCD, ESO, cert-manager, Ingress Controller, Prometheus stack, Terraform `helm_release` vs ArgoCD bootstrap trade-off.
- **Day 33** — GitOps Apps Layer & Promotion: 3 microservice Helm chart, Kustomize overlay, ApplicationSet, image tag strategy, dev auto-sync / staging PR / prod manual approval.
- **Day 34** — CI/CD + Observability + Reliability: GitHub Actions pipeline, image scanning, PR-based GitOps update, Prometheus + Grafana + Loki, alert rules, probes, HPA, PDB.
- **Day 35** — Disaster Recovery + Final Demo: disaster scenarios, recovery checklist, runbook, rollback, Terraform state safety, cleanup và retrospective.

Sau Day 35, học viên có một platform end-to-end production-grade chạy được cả Mode A và Mode B, với đầy đủ ADR, runbook, observability, CI/CD, và DR procedures.
